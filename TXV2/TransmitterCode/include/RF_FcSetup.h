// B88: THE FLIGHT CONTROLLER'S SETUP on the transmitter, over the Bluetooth pipe: the last Rotorflight settings the
// transmitter can make (Malcolm, 9 Oct 2026: "please implement all the remaining possible Rotorflight configuration
// options"), worded as the receiver's own pages:
//  - BATTERY (page 72, the first-time page's battery): cells, capacity, where the volts and amps come from, the cell
//    voltages, and the FC pads' sensors when those are the source. MSP 32 read (27 bytes) / 33 write (the first 15:
//    the active battery profile's capacity, nothing of the other profiles' - Rotorflight 4.6 msp.c reads the list only
//    when 12 more bytes come), 56/57 the voltage meters, 40/41 the current meters (a frame each: length, id, type, ...).
//  - BLACK BOX (page 73, rotorflight-blackbox.html): when, where, how often, after disarm, overwrite the oldest; how full
//    and erase. MSP 80 read (13 bytes: supported, device, mode, denom, fields, erase KiB, rolling, grace) / 81 write (the
//    12 after "supported"; ignored by the flight controller while it records or erases, so every save is read back),
//    70 the memory (flags, sectors, size, used), 72 erase (asynchronous: 70 asked until it is empty), 34 the switches
//    (is a Black box switch set up?). Device and rate apply at boot: a save that changes them restarts it (68).
//  - CALIBRATE (page 74 "LevelView", rotorflight-calibrate.html): the level as the flight controller sees it (108, tenths of a
//    degree), Calibrate level (205, then 250 after 2.5 s), the level trims (240 read / 239 write: pitch, roll, signed
//    tenths of a degree, -30.0 to 30.0).
//  - WHY IT WILL NOT ARM (the menu's line, code 175 for the whole list): MSP 101's arming-disable flags (bytes 17-20,
//    Rotorflight 4.6 runtime_config.h's order, the most critical first) in plain words, every 2 s while the menu shows.
// All of it was in the backup already (32, 80, 240, 56, 40: the sweep and the restore); with no model the backup answers,
// with the patches these writes need (RF_Backup.h BakOfflineAnswer). Byte for byte release/4.6.0 src/main/msp/msp.c.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_FCSETUP_H
#define RF_FCSETUP_H

// ---------------------------------------------------------------- shared
FLASHMEM static void FsBusy(const char *msg)
{
    SendCommand((char *)(msg && *msg ? "vis busy,1" : "vis busy,0"));
    if (msg && *msg)
        SendText((char *)"busy", (char *)msg);
}
FLASHMEM static void FsNum(const char *name, long v) { char b[16]; snprintf(b, sizeof(b), "%ld", v); SendText((char *)name, b); }
FLASHMEM static void FsHundredths(const char *name, long v) { char b[16]; snprintf(b, sizeof(b), "%ld.%02ld", v / 100, v % 100); SendText((char *)name, b); }
FLASHMEM static void FsTenths(const char *name, long v) { char b[16]; snprintf(b, sizeof(b), "%s%ld.%ld", v < 0 ? "-" : "", labs(v) / 10, labs(v) % 10); SendText((char *)name, b); }
FLASHMEM static void FsVis(const char *name, bool on) { char c[28]; snprintf(c, sizeof(c), "vis %s,%d", name, on ? 1 : 0); SendCommand(c); }
FLASHMEM static int FieldHundredths(const char *name, int lo, int hi) // "4.2" -> 420
{
    char t[24] = "";
    GetText((char *)name, t, sizeof(t) - 1);
    const float f = (float)atof(t);
    int v = (int)(f * 100.0f + (f >= 0 ? 0.5f : -0.5f));
    return v < lo ? lo : v > hi ? hi : v;
}
// (RdS16, the signed reader, is RF_Servos.h's)
FLASHMEM static void WrS16(uint8_t *b, int o, long v) // (WrU16 clamps at 0: the trims and the current sensor are signed)
{
    if (v < -32768) v = -32768;
    if (v > 32767) v = 32767;
    const uint16_t u = (uint16_t)(int16_t)v;
    b[o] = (uint8_t)(u & 0xFF); b[o + 1] = (uint8_t)(u >> 8);
}
FLASHMEM static uint32_t RdU32(const uint8_t *b, int o) { return (uint32_t)b[o] | ((uint32_t)b[o + 1] << 8) | ((uint32_t)b[o + 2] << 16) | ((uint32_t)b[o + 3] << 24); }
FLASHMEM static void FsFail(const char *page, const char *what)
{
    char msg[180];
    snprintf(msg, sizeof(msg), "%s:\r\n%.130s", what, PipeRepCode ? PipeRepBody : "the screen could not ask (no Bluetooth)");
    FsBusy("");
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)page, msg);
}
FLASHMEM static bool FsRefused(const char *page, bool needsModel) // the guards every save and action passes
{
    char why[120];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)page, why);
        return true;
    }
    if (needsModel && !(BoundFlag && ModelMatched))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)page, (char *)"This needs the model connected.");
        return true;
    }
    return false;
}
FLASHMEM static bool FsEntryRefused() // the menu's guard for a page that reads (the backup stands in with no model)
{
    char why[120];
    if (RfNeedsModel(why, sizeof(why)) || ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFView", why);
        return true;
    }
    return false;
}

// ---------------------------------------------------------------- BATTERY (page 72)
static const int BAT_BYTES = 15;                              // what a save writes (the active profile's capacity and on)
static uint8_t BatRaw[40], BatWant[40];
static int BatN = 0;
static uint8_t VmRaw[48], VmWant[48], CmRaw[48], CmWant[48];  // the meters: [0] count, then frames (voltage: 8 bytes, current: 7)
static int VmN = 0, CmN = 0;
static bool BatHave = false, Bat_Was_Edited = false, BatSame = true;
enum { BAT_IDLE = 0, BAT_READ, BAT_READ_VM, BAT_READ_CM, BAT_WRITE, BAT_WRITE_VM, BAT_WRITE_CM, BAT_STORE, BAT_VERIFY, BAT_VERIFY_VM, BAT_VERIFY_CM };
static int BatStep = BAT_IDLE, BatReq = 0;
static uint32_t BatMsgUntil = 0;
static const char *const BatSourceWords[4] = {"None", "FC pads", "ESC telemetry", "FBUS"};   // Rotorflight 4.6 battery.c: NONE, ADC, ESC, FBUS
FLASHMEM static bool BatVmThere() { return VmN >= 9 && VmWant[0] >= 1; }   // the first voltage meter whole: [1] 7, [2] id, [3] type, [4-5] scale, [6-7] divider, [8] divmul
FLASHMEM static bool BatCmThere() { return CmN >= 8 && CmWant[0] >= 1; }   // the first current meter whole: [1] 6, [2] id, [3] type, [4-5] scale, [6-7] offset
FLASHMEM static bool BatVmShown() { return BatWant[3] == 1 && BatVmThere(); }
FLASHMEM static bool BatCmShown() { return BatWant[4] == 1 && BatCmThere(); }
// B90: the FC pads' sensors (scale, offset) are on a page of their own, 75, reached by the battery page's "Sensors >",
// which shows only while a source is FC pads (Malcolm, 9 Oct: the battery page's boxes "more central ... a little
// larger" - with the sensors' rows gone it has five rows and lays out compact). Both pages are this one setup: the
// values are gathered from whichever page shows, kept in BatWant / VmWant / CmWant, and saved together.
FLASHMEM static bool BatOnPage() { return CurrentView == BATTERYVIEW || CurrentView == BATSENSORSVIEW; }
FLASHMEM static const char *BatPage() { return CurrentView == BATSENSORSVIEW ? "page BatSensorsView" : "page BatteryView"; }
FLASHMEM static void BatHead()
{
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)"All banks");
    SendCommand((char *)(Bat_Was_Edited ? "vis b3,1" : "vis b3,0"));
}
FLASHMEM static void BatShow()
{
    const bool v = BatVmShown(), c = BatCmShown();   // the FC pads' sensors only when they are the source
    if (CurrentView == BATTERYVIEW)
    {
        FsNum("tn0", BatWant[2]);
        FsNum("tn1", RdU16(BatWant, 0));
        SendText((char *)"tn2", (char *)BatSourceWords[BatWant[3] < 4 ? BatWant[3] : 0]);
        SendText((char *)"tn3", (char *)BatSourceWords[BatWant[4] < 4 ? BatWant[4] : 0]);
        FsHundredths("tn4", RdU16(BatWant, 9));    // full
        FsHundredths("tn5", RdU16(BatWant, 11));   // warning
        FsHundredths("tn6", RdU16(BatWant, 5));    // empty (Rotorflight's minimum)
        FsHundredths("tn7", RdU16(BatWant, 7));    // highest allowed (its maximum)
        FsVis("b2", BatHave && (v || c));          // Sensors >
        return;
    }
    if (CurrentView != BATSENSORSVIEW) return;
    FsVis("h2", v); FsVis("ltn8", v); FsVis("tn8", v);
    FsVis("h3", c); FsVis("ltn9", c); FsVis("tn9", c); FsVis("ltn10", c); FsVis("tn10", c);
    if (v) FsNum("tn8", RdU16(VmWant, 4));
    if (c) { FsNum("tn9", RdS16(CmWant, 4)); FsNum("tn10", RdS16(CmWant, 6)); }
}
FLASHMEM static void BatGather()
{
    if (!BatHave) return;
    if (CurrentView == BATTERYVIEW)
    {
        BatWant[2] = (uint8_t)FieldNumber("tn0", 0, 24);
        WrU16(BatWant, 0, FieldNumber("tn1", 0, 65000));
        WrU16(BatWant, 9, FieldHundredths("tn4", 100, 500));    // (Rotorflight's own range for a cell: 1.00 to 5.00 V)
        WrU16(BatWant, 11, FieldHundredths("tn5", 100, 500));
        WrU16(BatWant, 5, FieldHundredths("tn6", 100, 500));
        WrU16(BatWant, 7, FieldHundredths("tn7", 100, 500));
        return;
    }
    if (CurrentView != BATSENSORSVIEW) return;
    if (BatVmShown()) WrU16(VmWant, 4, FieldNumber("tn8", 0, 65535));
    if (BatCmShown()) { WrS16(CmWant, 4, FieldNumber("tn9", -32768, 32767)); WrS16(CmWant, 6, FieldNumber("tn10", -32768, 32767)); }
}
FLASHMEM static void BatFail(const char *what) { BatStep = BAT_IDLE; FsFail(BatPage(), what); BatHead(); BatShow(); }
FLASHMEM static void BatGoTo(int view) // B90: the other of the two pages, the edits in hand
{
    if (!BatHave || BatStep != BAT_IDLE) return;
    BatGather();
    SendCommand((char *)(view == BATSENSORSVIEW ? "page BatSensorsView" : "page BatteryView"));
    CurrentView = view;
    BatHead(); BatShow();
}
FLASHMEM void BatterySensorsView() { BatGoTo(BATSENSORSVIEW); }   // 176
FLASHMEM void BatterySensorsBack() { BatGoTo(BATTERYVIEW); }      // 177
FLASHMEM static void BatAfterWrites() { BatReq = MspAsk(250, nullptr, 0); BatStep = BAT_STORE; }
FLASHMEM static void BatWriteCm()
{
    if (BatCmThere() && memcmp(CmWant, CmRaw, 8) != 0)
    {
        const uint8_t d[5] = {CmWant[2], CmWant[4], CmWant[5], CmWant[6], CmWant[7]};
        BatReq = MspAsk(41, d, 5); BatStep = BAT_WRITE_CM;
        return;
    }
    BatAfterWrites();
}
FLASHMEM static void BatWriteVm()
{
    if (BatVmThere() && memcmp(VmWant, VmRaw, 9) != 0)
    {
        const uint8_t d[6] = {VmWant[2], VmWant[4], VmWant[5], VmWant[6], VmWant[7], VmWant[8]};
        BatReq = MspAsk(57, d, 6); BatStep = BAT_WRITE_VM;
        return;
    }
    BatWriteCm();
}
FLASHMEM void BatteryPoll()
{
    if (!BatOnPage()) { BatStep = BAT_IDLE; BatMsgUntil = 0; return; }
    if (BatMsgUntil && (int32_t)(millis() - BatMsgUntil) >= 0) { BatMsgUntil = 0; FsBusy(""); BatShow(); }
    if (BatStep == BAT_IDLE) return;
    if (!PipeReplyReady(BatReq))
    {
        if (!PipeReplyLate()) return;
        BatFail("No answer");
        return;
    }
    const bool ok = PipeRepCode == 200;
    switch (BatStep)
    {
    case BAT_READ:
    {
        if (!ok) { BatFail("Could not read the battery setup"); return; }
        BatN = PipeReplyBytes(BatRaw, sizeof(BatRaw));
        if (BatN < BAT_BYTES) { snprintf(PipeRepBody, sizeof(PipeRepBody), "only %d bytes came (Rotorflight 2.3 sends 27)", BatN); BatFail("Could not read the battery setup"); return; }
        memcpy(BatWant, BatRaw, sizeof(BatWant));
        BatReq = MspAsk(56, nullptr, 0); BatStep = BAT_READ_VM;
        return;
    }
    case BAT_READ_VM:   // (the sensors are a nicety: a flight controller that will not say leaves their rows hidden)
        VmN = ok ? PipeReplyBytes(VmRaw, sizeof(VmRaw)) : 0;
        memcpy(VmWant, VmRaw, sizeof(VmWant));
        BatReq = MspAsk(40, nullptr, 0); BatStep = BAT_READ_CM;
        return;
    case BAT_READ_CM:
        CmN = ok ? PipeReplyBytes(CmRaw, sizeof(CmRaw)) : 0;
        memcpy(CmWant, CmRaw, sizeof(CmWant));
        BatHave = true; Bat_Was_Edited = false; BatStep = BAT_IDLE;
        FsBusy(""); BatHead(); BatShow();
        return;
    case BAT_WRITE:
        if (!ok) { BatFail("Not written"); return; }
        BatWriteVm();
        return;
    case BAT_WRITE_VM:
        if (!ok) { BatFail("Not written (the voltage sensor)"); return; }
        BatWriteCm();
        return;
    case BAT_WRITE_CM:
        if (!ok) { BatFail("Not written (the current sensor)"); return; }
        BatAfterWrites();
        return;
    case BAT_STORE:
        if (!ok) { BatFail("Not stored"); return; }
        BatReq = MspAsk(32, nullptr, 0); BatStep = BAT_VERIFY;
        return;
    case BAT_VERIFY:
    {
        if (!ok) { BatFail("Could not read back"); return; }
        uint8_t b[40];
        const int n = PipeReplyBytes(b, sizeof(b));
        BatSame = n >= BAT_BYTES && memcmp(b, BatWant, BAT_BYTES) == 0;
        if (n >= BAT_BYTES) { memcpy(BatRaw, b, sizeof(BatRaw)); memcpy(BatWant, b, sizeof(BatWant)); BatN = n; }
        BatReq = MspAsk(56, nullptr, 0); BatStep = BAT_VERIFY_VM;
        return;
    }
    case BAT_VERIFY_VM:
    {
        uint8_t b[48];
        const int n = ok ? PipeReplyBytes(b, sizeof(b)) : 0;
        if (BatVmThere() && (n < 9 || memcmp(b, VmWant, 9) != 0)) BatSame = false;
        if (n > 0) { memcpy(VmRaw, b, sizeof(VmRaw)); memcpy(VmWant, b, sizeof(VmWant)); VmN = n; }
        BatReq = MspAsk(40, nullptr, 0); BatStep = BAT_VERIFY_CM;
        return;
    }
    case BAT_VERIFY_CM:
    {
        uint8_t b[48];
        const int n = ok ? PipeReplyBytes(b, sizeof(b)) : 0;
        if (BatCmThere() && (n < 8 || memcmp(b, CmWant, 8) != 0)) BatSame = false;
        if (n > 0) { memcpy(CmRaw, b, sizeof(CmRaw)); memcpy(CmWant, b, sizeof(CmWant)); CmN = n; }
        BatStep = BAT_IDLE; Bat_Was_Edited = false;
        BatHead(); BatShow();
        FsBusy(BatSame ? "Saved, and read back the same." : "Saved; the flight controller adjusted some values (shown).");
        BatMsgUntil = millis() + 4000;
        PlaySound(BEEPCOMPLETE);
        return;
    }
    default:
        BatStep = BAT_IDLE;
        return;
    }
}
FLASHMEM void StartBatteryView() // the menu's Battery ...
{
    if (FsEntryRefused()) return;
    SendCommand((char *)"page BatteryView");
    CurrentView = BATTERYVIEW;
    BatHave = false; Bat_Was_Edited = false; BatN = VmN = CmN = 0;
    FsVis("b2", false);   // (B90: Sensors > once the read says a source is FC pads)
    BatHead();
    FsBusy("Reading from the flight controller ...");
    BatReq = MspAsk(32, nullptr, 0); BatStep = BAT_READ;
}
FLASHMEM void EndBatteryView() // OK
{
    if (BatStep != BAT_IDLE) return;   // (a save runs: wait for it)
    if (Bat_Was_Edited)
    {
        BatGather();
        if (!GetConfirmation((char *)BatPage(), (char *)"Discard the edited battery values?")) { BatHead(); BatShow(); return; }
    }
    Bat_Was_Edited = false;
    RotorFlightStart();
}
FLASHMEM void BatteryWasEdited() { Bat_Was_Edited = true; SendCommand((char *)"vis b3,1"); }
FLASHMEM static void BatSource(int i) // 3 voltage, 4 current: None -> FC pads -> ESC telemetry -> (FBUS only if it was so) -> None
{
    if (!BatHave || BatStep != BAT_IDLE) return;
    BatGather();
    uint8_t s = BatWant[i];
    s = s == 0 ? 1 : s == 1 ? 2 : (s == 2 && BatRaw[i] == 3) ? 3 : 0;
    BatWant[i] = s;
    BatteryWasEdited();
    BatShow();
}
FLASHMEM void BatteryVoltageSourceTapped() { BatSource(3); }
FLASHMEM void BatteryCurrentSourceTapped() { BatSource(4); }
FLASHMEM void SaveBattery()
{
    if (!BatHave || BatStep != BAT_IDLE) return;
    if (FsRefused(BatPage(), false)) { BatHead(); BatShow(); return; }
    BatGather();
    const int full = RdU16(BatWant, 9), warn = RdU16(BatWant, 11), empty = RdU16(BatWant, 5), top = RdU16(BatWant, 7);
    if (!(empty < warn && warn < full && full <= top))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)BatPage(), (char *)"Not saved: each cell's voltages must rise,\r\nEmpty < Warning < Full, and Full no\r\nhigher than Highest allowed.");
        BatHead(); BatShow();
        return;
    }
    FsBusy("Writing to the flight controller ...");
    BatReq = MspAsk(33, BatWant, BAT_BYTES); BatStep = BAT_WRITE;
}

// ---------------------------------------------------------------- BLACK BOX (page 73)
static uint8_t BbRaw[16], BbWant[16];    // MSP 80: [0] supported, [1] device, [2] mode, [3-4] denom, [5-8] fields, [9-10] erase KiB, [11] rolling, [12] grace
static uint8_t BbMem[16];                // MSP 70: [0] flags (1 ready, 2 supported), [1-4] sectors, [5-8] size, [9-12] used
static int BbMemN = 0;
static uint16_t BbPidUs = 0;             // MSP 101's first word: the control loop's period, for "a second"
static bool BbHave = false, Bb_Was_Edited = false, BbSwitchKnown = false, BbSwitchSet = false, BbSame = true;
enum { BB_IDLE = 0, BB_STATUS, BB_READ, BB_MODES, BB_MEM, BB_WRITE, BB_STORE, BB_REBOOT, BB_WAIT, BB_VERIFY, BB_ERASE, BB_ERASE_WAIT, BB_ERASE_POLL };
static int BbStep = BB_IDLE, BbReq = 0, BbTries = 0;
static uint32_t BbMsgUntil = 0, BbWaitUntil = 0, BbEraseStart = 0;
static const uint8_t BB_MODE_ORDER[4] = {2, 3, 1, 0}, BB_DEV_ORDER[4] = {1, 2, 3, 0};
static const uint16_t BB_DENOMS[8] = {1, 2, 4, 8, 16, 32, 64, 128};
FLASHMEM static const char *BbModeWord(uint8_t m) { return m == 2 ? "Whenever armed" : m == 3 ? "While switch on" : m == 1 ? "Armed + switch" : "Never"; }
FLASHMEM static const char *BbDevWord(uint8_t d) { return d == 1 ? "FC memory" : d == 2 ? "SD card" : d == 3 ? "Serial logger" : "Nowhere"; }
FLASHMEM static void BbHead()
{
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)"All banks");
    SendCommand((char *)(Bb_Was_Edited ? "vis b3,1" : "vis b3,0"));
}
FLASHMEM static void BbShowMemory()
{
    char a[64], b[64];
    if (!(BoundFlag && ModelMatched)) { snprintf(a, sizeof(a), "Connect the model to see"); snprintf(b, sizeof(b), "how full its memory is"); }
    else if (BbMemN < 13) { snprintf(a, sizeof(a), "Memory: not known"); b[0] = 0; }
    else if (!(BbMem[0] & 2)) { snprintf(a, sizeof(a), "No memory chip on this board"); snprintf(b, sizeof(b), "SD card or serial logger only"); }
    else
    {
        const uint32_t size = RdU32(BbMem, 5), used = RdU32(BbMem, 9);
        const unsigned pct = size ? (unsigned)((uint64_t)used * 100 / size) : 0;
        snprintf(a, sizeof(a), "%lu.%lu of %lu.%lu MB used (%u %%)", (unsigned long)(used / 1048576), (unsigned long)(used % 1048576 * 10 / 1048576),
                 (unsigned long)(size / 1048576), (unsigned long)(size % 1048576 * 10 / 1048576), pct);
        snprintf(b, sizeof(b), "%s", !(BbMem[0] & 1) ? "Busy: erasing?" : pct >= 95 ? "Full: erase before flying" : used == 0 ? "Empty: ready to record" : "Ready to record");
    }
    SendText((char *)"tn5", a); SendText((char *)"tn6", b);
}
FLASHMEM static void BbShow()
{
    if (CurrentView != BLACKBOXVIEW) return;
    char b[40];
    SendText((char *)"tn0", (char *)BbModeWord(BbWant[2]));
    SendText((char *)"tn1", (char *)BbDevWord(BbWant[1]));
    const uint16_t d = RdU16(BbWant, 3);
    if (BbPidUs && d) snprintf(b, sizeof(b), "1 in %u (%lu/s)", (unsigned)d, (unsigned long)(1000000UL / BbPidUs / d));
    else snprintf(b, sizeof(b), "1 in %u loops", (unsigned)d);
    SendText((char *)"tn2", b);
    FsNum("tn3", BbWant[12]);
    SendValue((char *)"tn4", BbWant[11] ? 1 : 0);
    BbShowMemory();
}
FLASHMEM static void BbGather() { if (CurrentView == BLACKBOXVIEW && BbHave) BbWant[12] = (uint8_t)FieldNumber("tn3", 0, 60); }
FLASHMEM static void BbFail(const char *what) { BbStep = BB_IDLE; FsFail("page BlackboxView", what); BbHead(); BbShow(); }
FLASHMEM static void BbDone(const char *msg, bool good)
{
    BbStep = BB_IDLE;
    BbHead(); BbShow();
    FsBusy(msg);
    BbMsgUntil = millis() + 5000;
    PlaySound(good ? BEEPCOMPLETE : WHAHWHAHMSG);
}
FLASHMEM void BlackboxPoll()
{
    if (CurrentView != BLACKBOXVIEW) { BbStep = BB_IDLE; BbMsgUntil = 0; return; }
    if (BbMsgUntil && (int32_t)(millis() - BbMsgUntil) >= 0) { BbMsgUntil = 0; FsBusy(""); BbShow(); }
    if (BbStep == BB_IDLE) return;
    if (BbStep == BB_WAIT || BbStep == BB_ERASE_WAIT)
    {
        if ((int32_t)(millis() - BbWaitUntil) < 0) return;
        if (BbStep == BB_WAIT) { BbReq = MspAsk(80, nullptr, 0); BbStep = BB_VERIFY; ++BbTries; return; }
        char m[90];
        snprintf(m, sizeof(m), "Erasing the flight logs: %lu s (it beeps while it erases) ...", (unsigned long)((millis() - BbEraseStart) / 1000));
        FsBusy(m);
        BbReq = MspAsk(70, nullptr, 0); BbStep = BB_ERASE_POLL;
        return;
    }
    if (!PipeReplyReady(BbReq))
    {
        if (!PipeReplyLate()) return;
        if (BbStep == BB_VERIFY && BbTries < 5) { BbWaitUntil = millis() + 2500; BbStep = BB_WAIT; return; }   // (still restarting)
        if (BbStep == BB_ERASE_POLL) { BbWaitUntil = millis() + 1500; BbStep = BB_ERASE_WAIT; return; }
        BbFail("No answer");
        return;
    }
    const bool ok = PipeRepCode == 200;
    switch (BbStep)
    {
    case BB_STATUS:
    {
        uint8_t b[40];
        BbPidUs = (ok && PipeReplyBytes(b, sizeof(b)) >= 2) ? RdU16(b, 0) : 0;
        BbReq = MspAsk(80, nullptr, 0); BbStep = BB_READ;
        return;
    }
    case BB_READ:
    {
        if (!ok) { BbFail("Could not read the black box setup"); return; }
        const int n = PipeReplyBytes(BbRaw, sizeof(BbRaw));
        if (n < 13) { snprintf(PipeRepBody, sizeof(PipeRepBody), "only %d bytes came (Rotorflight 2.3 sends 13)", n); BbFail("Could not read the black box setup"); return; }
        memcpy(BbWant, BbRaw, sizeof(BbWant));
        BbReq = MspAsk(34, nullptr, 0); BbStep = BB_MODES;
        return;
    }
    case BB_MODES:
    { // is a Black box switch (mode 26) set up? (the switch choices of When need one)
        uint8_t b[96];
        const int n = ok ? PipeReplyBytes(b, sizeof(b)) : 0;
        BbSwitchKnown = n >= 80; BbSwitchSet = false;
        for (int i = 0; i + 3 < n; i += 4) if (b[i] == 26 && b[i + 3] != b[i + 2]) BbSwitchSet = true;
        BbReq = MspAsk(70, nullptr, 0); BbStep = BB_MEM;
        return;
    }
    case BB_MEM:
        BbMemN = ok ? PipeReplyBytes(BbMem, sizeof(BbMem)) : 0;
        BbHave = true; Bb_Was_Edited = false; BbStep = BB_IDLE;
        FsBusy(""); BbHead(); BbShow();
        if (!BbRaw[0]) { MsgBox((char *)"page BlackboxView", (char *)"This flight controller has no black box."); BbHead(); BbShow(); }
        return;
    case BB_WRITE:
        if (!ok) { BbFail("Not written"); return; }
        BbReq = MspAsk(250, nullptr, 0); BbStep = BB_STORE;
        return;
    case BB_STORE:
        if (!ok) { BbFail("Not stored"); return; }
        if (!BakOffline() && (BbWant[1] != BbRaw[1] || RdU16(BbWant, 3) != RdU16(BbRaw, 3)))
        { // where and how often apply when the flight controller boots (blackboxInit): restarted, as the filters' features are (not the backup's stand-in)
            FsBusy("Restarting the flight controller (where and how often apply at boot) ...");
            BbReq = MspAsk(68, nullptr, 0); BbStep = BB_REBOOT;
            return;
        }
        BbReq = MspAsk(80, nullptr, 0); BbStep = BB_VERIFY; BbTries = 0;
        return;
    case BB_REBOOT:
        if (!ok) { BbFail("Not restarted"); return; }
        BbTries = 0; BbWaitUntil = millis() + 5000; BbStep = BB_WAIT;
        return;
    case BB_VERIFY:
    {
        uint8_t b[16];
        const int n = ok ? PipeReplyBytes(b, sizeof(b)) : 0;
        if (n < 13) { if (BbTries < 5) { BbWaitUntil = millis() + 2500; BbStep = BB_WAIT; return; } BbFail("Could not read back"); return; }
        BbSame = memcmp(b + 1, BbWant + 1, 12) == 0;
        memcpy(BbRaw, b, sizeof(BbRaw)); memcpy(BbWant, b, sizeof(BbWant));
        Bb_Was_Edited = false;
        BbDone(BbSame ? "Saved, and read back the same." : "Not all saved: the flight controller keeps its setup while it records or erases.", BbSame);
        return;
    }
    case BB_ERASE:   // (asked once: a second 72 starts the erase again)
        if (!ok) { BbFail("Not erased"); return; }
        BbEraseStart = millis(); BbWaitUntil = millis() + 1500; BbStep = BB_ERASE_WAIT;
        return;
    case BB_ERASE_POLL:
    {
        BbMemN = ok ? PipeReplyBytes(BbMem, sizeof(BbMem)) : BbMemN;
        const uint32_t secs = (millis() - BbEraseStart) / 1000;
        if (ok && BbMemN >= 13 && (BbMem[0] & 1) && RdU32(BbMem, 9) == 0)
        {
            char m[60]; snprintf(m, sizeof(m), "Erased in %lu s: ready to record.", (unsigned long)secs);
            BbDone(m, true);
            return;
        }
        if (secs >= 120) { BbDone("Still not erased after 2 minutes: is Where set to FC memory, and restarted since?", false); return; }
        BbWaitUntil = millis() + 1500; BbStep = BB_ERASE_WAIT;
        return;
    }
    default:
        BbStep = BB_IDLE;
        return;
    }
}
FLASHMEM void StartBlackboxView() // the menu's Black box ...
{
    if (FsEntryRefused()) return;
    SendCommand((char *)"page BlackboxView");
    CurrentView = BLACKBOXVIEW;
    BbHave = false; Bb_Was_Edited = false; BbMemN = 0; BbPidUs = 0; BbSwitchKnown = false;
    BbHead();
    FsBusy("Reading from the flight controller ...");
    BbReq = MspAsk(101, nullptr, 0); BbStep = BB_STATUS;
}
FLASHMEM void EndBlackboxView() // OK
{
    if (BbStep != BB_IDLE) return;   // (a save or an erase runs: wait for it)
    if (Bb_Was_Edited)
    {
        BbGather();
        if (!GetConfirmation((char *)"page BlackboxView", (char *)"Discard the edited black box setup?")) { BbHead(); BbShow(); return; }
    }
    Bb_Was_Edited = false;
    RotorFlightStart();
}
FLASHMEM void BlackboxWasEdited() { Bb_Was_Edited = true; SendCommand((char *)"vis b3,1"); }
FLASHMEM static int BbIndexOf(const uint8_t *order, uint8_t v) { for (int i = 0; i < 4; ++i) if (order[i] == v) return i; return 3; }
FLASHMEM void BlackboxModeTapped() { if (!BbHave || BbStep != BB_IDLE) return; BbGather(); BbWant[2] = BB_MODE_ORDER[(BbIndexOf(BB_MODE_ORDER, BbWant[2]) + 1) % 4]; BlackboxWasEdited(); BbShow(); }
FLASHMEM void BlackboxDeviceTapped() { if (!BbHave || BbStep != BB_IDLE) return; BbGather(); BbWant[1] = BB_DEV_ORDER[(BbIndexOf(BB_DEV_ORDER, BbWant[1]) + 1) % 4]; BlackboxWasEdited(); BbShow(); }
FLASHMEM void BlackboxRateTapped()
{
    if (!BbHave || BbStep != BB_IDLE) return;
    BbGather();
    const uint16_t d = RdU16(BbWant, 3);
    int k = 0;
    while (k < 8 && BB_DENOMS[k] <= d) ++k;   // the next one up, round to 1 after 128 (and from an odd number, the next of the list)
    WrU16(BbWant, 3, BB_DENOMS[k % 8]);
    BlackboxWasEdited(); BbShow();
}
FLASHMEM void BlackboxRollTapped() { if (!BbHave || BbStep != BB_IDLE) return; BbGather(); BbWant[11] = BbWant[11] ? 0 : 1; BlackboxWasEdited(); BbShow(); }
FLASHMEM void SaveBlackbox()
{
    if (!BbHave || BbStep != BB_IDLE) return;
    if (FsRefused("page BlackboxView", false)) { BbHead(); BbShow(); return; }
    BbGather();
    if (BbWant[2] != 0 && BbWant[1] == 0)
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page BlackboxView", (char *)"Not saved: choose Where to record,\r\nor set When to Never.");
        BbHead(); BbShow();
        return;
    }
    if ((BbWant[2] == 3 || BbWant[2] == 1) && BbSwitchKnown && !BbSwitchSet)
    {
        if (!GetConfirmation((char *)"page BlackboxView", (char *)"No Black box switch is set up (Switches),\r\nso this would never record.\r\nSave anyway?")) { BbHead(); BbShow(); return; }
        BbHead(); BbShow();
    }
    FsBusy("Writing to the flight controller ...");
    BbReq = MspAsk(81, BbWant + 1, 12); BbStep = BB_WRITE;
}
FLASHMEM void BlackboxErase()
{
    if (!BbHave || BbStep != BB_IDLE) return;
    if (FsRefused("page BlackboxView", true)) { BbHead(); BbShow(); return; }
    if (BbMemN >= 13 && !(BbMem[0] & 2)) { MsgBox((char *)"page BlackboxView", (char *)"No memory chip on this board to erase."); BbHead(); BbShow(); return; }
    if (!GetConfirmation((char *)"page BlackboxView", (char *)"Erase every flight log on the flight\r\ncontroller? They cannot be recovered.")) { BbHead(); BbShow(); return; }
    BbHead(); BbShow();
    FsBusy("Erasing the flight logs ...");
    BbReq = MspAsk(72, nullptr, 0); BbStep = BB_ERASE;
}

// ---------------------------------------------------------------- CALIBRATE (page 74)
static uint8_t CalRaw[8], CalWant[8];    // MSP 240: [0-1] pitch, [2-3] roll, signed tenths of a degree
static bool CalHave = false, Cal_Was_Edited = false, CalLevelKnown = false;
static int CalRoll = 0, CalPitch = 0;    // MSP 108: tenths of a degree
enum { CAL_IDLE = 0, CAL_READ, CAL_ATT, CAL_CAL, CAL_CAL_WAIT, CAL_CAL_STORE, CAL_CAL_ATT, CAL_WRITE, CAL_STORE, CAL_VERIFY };
static int CalStep = CAL_IDLE, CalReq = 0;
static uint32_t CalMsgUntil = 0, CalNextAtt = 0, CalWaitUntil = 0;
FLASHMEM static void CalHead()
{
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)"All banks");
    SendCommand((char *)(Cal_Was_Edited ? "vis b3,1" : "vis b3,0"));
}
FLASHMEM static void CalShowLevel()
{
    char a[64], b[64];
    if (!(BoundFlag && ModelMatched)) { snprintf(a, sizeof(a), "No model: level not known"); b[0] = 0; }   // (B90: within the compact card's column)
    else if (!CalLevelKnown) { snprintf(a, sizeof(a), "Reading the level ..."); b[0] = 0; }
    else
    {
        snprintf(a, sizeof(a), "Roll %s%d.%d   Pitch %s%d.%d deg", CalRoll < 0 ? "-" : "", abs(CalRoll) / 10, abs(CalRoll) % 10, CalPitch < 0 ? "-" : "", abs(CalPitch) / 10, abs(CalPitch) % 10);
        snprintf(b, sizeof(b), "%s", (abs(CalRoll) < 20 && abs(CalPitch) < 20) ? "Level" : "Not level: level it, then Calibrate");
    }
    SendText((char *)"tn0", a); SendText((char *)"tn1", b);
}
FLASHMEM static void CalShow()
{
    if (CurrentView != LEVELVIEW) return;
    CalShowLevel();
    if (CalHave) { FsTenths("tn2", RdS16(CalWant, 0)); FsTenths("tn3", RdS16(CalWant, 2)); }
}
FLASHMEM static void CalGather()
{
    if (CurrentView != LEVELVIEW || !CalHave) return;
    WrS16(CalWant, 0, FieldTenths("tn2", -300, 300));
    WrS16(CalWant, 2, FieldTenths("tn3", -300, 300));
}
FLASHMEM static void CalFail(const char *what) { CalStep = CAL_IDLE; FsFail("page LevelView", what); CalHead(); CalShow(); }
FLASHMEM static void CalTakeLevel(bool ok)
{
    uint8_t b[16];
    if (ok && PipeReplyBytes(b, sizeof(b)) >= 4) { CalRoll = RdS16(b, 0); CalPitch = RdS16(b, 2); CalLevelKnown = true; }
}
FLASHMEM void CalibratePoll()
{
    if (CurrentView != LEVELVIEW) { CalStep = CAL_IDLE; CalMsgUntil = 0; return; }
    if (CalMsgUntil && (int32_t)(millis() - CalMsgUntil) >= 0) { CalMsgUntil = 0; FsBusy(""); CalShow(); }
    if (CalStep == CAL_IDLE)
    { // the level, live, while the page is idle and the model is there (and no stale reading once it has gone)
        if (!(BoundFlag && ModelMatched) || BakOffline()) { if (CalLevelKnown) { CalLevelKnown = false; CalShowLevel(); } return; }
        if ((int32_t)(millis() - CalNextAtt) >= 0) { CalReq = MspAsk(108, nullptr, 0); CalStep = CAL_ATT; }
        return;
    }
    if (CalStep == CAL_CAL_WAIT)
    {
        if ((int32_t)(millis() - CalWaitUntil) < 0) return;
        CalReq = MspAsk(250, nullptr, 0); CalStep = CAL_CAL_STORE;
        return;
    }
    if (!PipeReplyReady(CalReq))
    {
        if (!PipeReplyLate()) return;
        if (CalStep == CAL_ATT) { CalStep = CAL_IDLE; CalNextAtt = millis() + 2000; return; }   // (the level is a nicety)
        CalFail("No answer");
        return;
    }
    const bool ok = PipeRepCode == 200;
    switch (CalStep)
    {
    case CAL_READ:
        if (!ok || PipeReplyBytes(CalRaw, sizeof(CalRaw)) < 4) { CalFail("Could not read the level trims"); return; }
        memcpy(CalWant, CalRaw, sizeof(CalWant));
        CalHave = true; Cal_Was_Edited = false; CalStep = CAL_IDLE; CalNextAtt = millis();
        FsBusy(""); CalHead(); CalShow();
        return;
    case CAL_ATT:
        CalTakeLevel(ok);
        CalStep = CAL_IDLE; CalNextAtt = millis() + 700;
        CalShowLevel();
        return;
    case CAL_CAL:
        if (!ok) { CalFail("Not calibrated"); return; }
        CalWaitUntil = millis() + 2500; CalStep = CAL_CAL_WAIT;   // (the flight controller takes its samples, then the result is stored)
        return;
    case CAL_CAL_STORE:
        if (!ok) { CalFail("Calibrated, but not stored"); return; }
        CalReq = MspAsk(108, nullptr, 0); CalStep = CAL_CAL_ATT;
        return;
    case CAL_CAL_ATT:
    {
        CalTakeLevel(ok);
        CalStep = CAL_IDLE; CalNextAtt = millis() + 700;
        CalHead(); CalShow();
        char m[90];
        snprintf(m, sizeof(m), "Calibrated: roll %s%d.%d, pitch %s%d.%d degrees.", CalRoll < 0 ? "-" : "", abs(CalRoll) / 10, abs(CalRoll) % 10, CalPitch < 0 ? "-" : "", abs(CalPitch) / 10, abs(CalPitch) % 10);
        FsBusy(m);
        CalMsgUntil = millis() + 5000;
        PlaySound(BEEPCOMPLETE);
        return;
    }
    case CAL_WRITE:
        if (!ok) { CalFail("Not written"); return; }
        CalReq = MspAsk(250, nullptr, 0); CalStep = CAL_STORE;
        return;
    case CAL_STORE:
        if (!ok) { CalFail("Not stored"); return; }
        CalReq = MspAsk(240, nullptr, 0); CalStep = CAL_VERIFY;
        return;
    case CAL_VERIFY:
    {
        uint8_t b[8];
        const int n = ok ? PipeReplyBytes(b, sizeof(b)) : 0;
        const bool same = n >= 4 && memcmp(b, CalWant, 4) == 0;
        if (n >= 4) { memcpy(CalRaw, b, sizeof(CalRaw)); memcpy(CalWant, b, sizeof(CalWant)); }
        CalStep = CAL_IDLE; Cal_Was_Edited = false; CalNextAtt = millis() + 700;
        CalHead(); CalShow();
        FsBusy(same ? "Saved, and read back the same." : "Saved; the flight controller adjusted some values (shown).");
        CalMsgUntil = millis() + 4000;
        PlaySound(BEEPCOMPLETE);
        return;
    }
    default:
        CalStep = CAL_IDLE;
        return;
    }
}
FLASHMEM void StartCalibrateView() // the menu's Calibrate ...
{
    if (FsEntryRefused()) return;
    SendCommand((char *)"page LevelView");
    CurrentView = LEVELVIEW;
    CalHave = false; Cal_Was_Edited = false; CalLevelKnown = false;
    CalHead();
    CalShowLevel();
    FsBusy("Reading from the flight controller ...");
    CalReq = MspAsk(240, nullptr, 0); CalStep = CAL_READ;
}
FLASHMEM void EndCalibrateView() // OK
{
    if (CalStep != CAL_IDLE && CalStep != CAL_ATT) return;   // (a calibration or a save runs: wait for it)
    if (Cal_Was_Edited)
    {
        CalGather();
        if (!GetConfirmation((char *)"page LevelView", (char *)"Discard the edited level trims?")) { CalHead(); CalShow(); return; }
    }
    CalStep = CAL_IDLE; Cal_Was_Edited = false;
    RotorFlightStart();
}
FLASHMEM void CalibrateWasEdited() { Cal_Was_Edited = true; SendCommand((char *)"vis b3,1"); }
FLASHMEM void CalibrateNow()
{
    if (!CalHave || (CalStep != CAL_IDLE && CalStep != CAL_ATT)) return;
    if (FsRefused("page LevelView", true)) { CalHead(); CalShow(); return; }
    if (!GetConfirmation((char *)"page LevelView", (char *)"Is the model level and perfectly still?\r\n(Best done on a flat desk, before\r\nthe board goes into the model.)")) { CalHead(); CalShow(); return; }
    CalHead(); CalShow();
    FsBusy("Calibrating: keep it still ...");
    CalReq = MspAsk(205, nullptr, 0); CalStep = CAL_CAL;
}
FLASHMEM void SaveLevelTrims()
{
    if (!CalHave || (CalStep != CAL_IDLE && CalStep != CAL_ATT)) return;
    if (FsRefused("page LevelView", false)) { CalHead(); CalShow(); return; }
    CalGather();
    FsBusy("Writing to the flight controller ...");
    CalReq = MspAsk(239, CalWant, 4); CalStep = CAL_WRITE;
}

// ---------------------------------------------------------------- WHY IT WILL NOT ARM (the menu's line)
// Rotorflight 4.6 runtime_config.h armingDisableFlags_e, bit by bit, the most critical first, in plain words (each short:
// the whole list goes in one message box)
static const char *const ArmWhy[27] PROGMEM = {
    "No gyro: its sensor is not working", "Failsafe is active", "No signal from the receiver", "Link back with the arm switch on",
    "The failsafe switch is on", "Governor: no head-speed signal", "No RPM signal (ESC telemetry)", "Throttle is not at idle",
    "Tilted too far: stand it level", "Just switched on: wait a moment", "The prearm switch is off", "The flight controller is overloaded",
    "Calibrating: keep it still", "The command line (CLI) is open", "The on-screen menu is open", "Blocked (BST)",
    "Blocked by the configurator", "Paralyze is on: restart the FC", "GPS rescue needs a GPS fix", "The rescue switch is on",
    "RPM filter: no RPM signal", "Restart the flight controller", "DShot bitbang fault", "Calibrate the accelerometer",
    "No motor protocol chosen", "A servo or motor override is on", "Arm switch on too soon: off, then on"};
static int ArmReq = 0;
static bool ArmPending = false, ArmKnown = false, ArmFcArmed = false, ArmBlank = true;
static uint32_t ArmFlags = 0, ArmNextAt = 0;
FLASHMEM static int ArmCount() { int n = 0; for (int i = 0; i < 27; ++i) if (ArmFlags & (1UL << i)) ++n; return n; }
FLASHMEM static void ArmShow()
{
    char b[96];
    uint16_t colour = 2016;   // green
    if (ArmFcArmed) { snprintf(b, sizeof(b), "Armed"); colour = 63488; }
    else if (!ArmFlags) snprintf(b, sizeof(b), "Ready to arm");
    else
    {
        int first = 0;
        while (first < 27 && !(ArmFlags & (1UL << first))) ++first;
        const int more = ArmCount() - 1;
        char extra[24] = "";
        if (more > 0) snprintf(extra, sizeof(extra), " (and %d more)", more);
        snprintf(b, sizeof(b), "Will not arm: %s%s", first < 27 ? ArmWhy[first] : "a reason not known here", extra);
        colour = 65504;   // yellow
    }
    SendText((char *)"arm", b);
    char c[24]; snprintf(c, sizeof(c), "arm.pco=%u", (unsigned)colour); SendCommand(c);
    ArmBlank = false;
}
FLASHMEM void ArmTick() // every 50 ms (ManageTransmitter): MSP 101 every 2 s while the menu shows, the model is there and the pipe is ready
{
    const bool can = CurrentView == ROTORFLIGHTVIEW && PipeState == 2 && BoundFlag && ModelMatched && !BakOffline();
    if (!can)
    {
        if (CurrentView == ROTORFLIGHTVIEW && !ArmBlank) { SendText((char *)"arm", (char *)""); ArmBlank = true; }
        if (CurrentView != ROTORFLIGHTVIEW) ArmBlank = true;   // (the menu draws itself afresh with an empty line)
        ArmPending = false; ArmKnown = false;
        return;
    }
    if (ArmPending)
    {
        if (PipeReplyReady(ArmReq))
        {
            uint8_t b[40];
            const int n = PipeRepCode == 200 ? PipeReplyBytes(b, sizeof(b)) : 0;
            ArmPending = false; ArmNextAt = millis() + 2000;
            if (n >= 21) { ArmFlags = RdU32(b, 17) & 0x07FFFFFFUL; ArmFcArmed = (b[6] & 1) != 0; ArmKnown = true; ArmShow(); }
        }
        else if (PipeReplyLate()) { ArmPending = false; ArmNextAt = millis() + 2000; }
        return;
    }
    if ((int32_t)(millis() - ArmNextAt) < 0) return;
    if (PipeRepId != PipeReqId && !PipeReplyLate()) return;   // (another request is on its way: not one on top of it)
    ArmReq = MspAsk(101, nullptr, 0);
    ArmPending = true;
}
FLASHMEM void ArmingWhy() // the menu's line tapped (175): every reason, in one message box
{
    char m[200];
    if (!ArmKnown) snprintf(m, sizeof(m), "Not known yet: the model must be\r\nconnected, with Bluetooth joined.");
    else if (ArmFcArmed) snprintf(m, sizeof(m), "The flight controller says it is armed.");
    else if (!ArmFlags) snprintf(m, sizeof(m), "Nothing stops it arming.");
    else
    {
        snprintf(m, sizeof(m), "Why it will not arm:");
        int shown = 0;
        for (int i = 0; i < 27; ++i)
        {
            if (!(ArmFlags & (1UL << i))) continue;
            if (shown == 4) { char t[24]; snprintf(t, sizeof(t), "\r\n(and %d more)", ArmCount() - 4); strncat(m, t, sizeof(m) - strlen(m) - 1); break; }
            strncat(m, "\r\n- ", sizeof(m) - strlen(m) - 1);
            strncat(m, ArmWhy[i], sizeof(m) - strlen(m) - 1);
            ++shown;
        }
    }
    MsgBox((char *)"page RFView", m);
    RotorFlightStart();
    if (ArmKnown) ArmShow();   // (the menu came back with an empty line)
}
#endif
