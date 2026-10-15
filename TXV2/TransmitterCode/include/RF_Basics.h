// B99 (Malcolm, 15 Oct: "Perhaps now I'll be able to complete the Havoc setup without using my phone or the configurator?"
// - "Yes if we have available flash!"): the model's BASICS on the transmitter - the values the Mixer pages only tell and
// the phone app's First-time basics set. The configurator's Mixer tab selects (MSP 42 read / 43 write, 21 bytes: main
// rotor direction byte 0, tail rotor type byte 1, swashplate type byte 5), its Motor tab (MSP 131 read, 29 bytes / 222
// write, 28: the write has no motor-count byte 6; protocol 9/8, poles 13/12, main gear ratio 21-24/20-23, tail gear ratio
// 25-28/24-27) and the ESC telemetry protocol (MSP 123 read / 216 write, 14 bytes, byte 0 - a flight controller built
// without ESC telemetry has none: the row then says "?"). Two pages: BasicsView (the screen's page 77) and Basics2View
// (78, the gear ratios), reached from the Rotorflight settings page. A save writes 43, 222, 216, stores (250), RESTARTS
// the flight controller (68: motors.c reads the poles and the ratios at init, the mixer its type and the ESC port its
// protocol - the configurator restarts after these tabs too) and reads it all back once it answers, as RF_Filters.h does.
// Without the model the pages edit its backup on the card (RF_Backup.h: a 222 patches the 131 image); no restart then.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_BASICS_H
#define RF_BASICS_H

static const int BAS_MIX_BYTES = 21, BAS_MOT_BYTES = 29, BAS_ESC_BYTES = 14;
static uint8_t BasMix[BAS_MIX_BYTES], BasMixWant[BAS_MIX_BYTES];
static uint8_t BasMot[BAS_MOT_BYTES], BasMotWant[BAS_MOT_BYTES];
static uint8_t BasEsc[BAS_ESC_BYTES], BasEscWant[BAS_ESC_BYTES];
static bool BasHave = false, BasEscHave = false, Bas_Was_Edited = false;
enum { BAS_IDLE = 0, BAS_READ_MIX, BAS_READ_MOT, BAS_READ_ESC, BAS_WRITE_MIX, BAS_WRITE_MOT, BAS_WRITE_ESC, BAS_STORE, BAS_REBOOT, BAS_WAIT, BAS_VERIFY_MIX, BAS_VERIFY_MOT, BAS_VERIFY_ESC };
static int BasStep = BAS_IDLE, BasReq = 0, BasTries = 0;
static uint32_t BasMsgUntil = 0, BasWaitUntil = 0;
static const char *const BasSwashWords[7] PROGMEM = {"None", "Direct", "CCPM 120 deg", "CCPM 135 deg", "CCPM 140 deg", "FPM 90 deg L", "FPM 90 deg V"};   // (the configurator's, as RF_Travel.h tells them)
static const char *const BasTailWords[3] PROGMEM = {"Variable pitch", "Motorised", "Bi-directional"};
static const uint8_t BasProtoCodes[6] PROGMEM = {0, 1, 5, 6, 7, 10};   // Rotorflight's motorPwmProtocol: PWM, ONESHOT125, DSHOT150, DSHOT300, DSHOT600, DISABLED (the phone's list)
static const char *const BasProtoWords[6] PROGMEM = {"PWM (most heli ESCs)", "OneShot125", "DShot150", "DShot300", "DShot600", "Off"};
static const char *const BasEscWords[14] PROGMEM = {"None", "BLHeli32", "Hobbywing V4", "Hobbywing V5", "Scorpion", "Kontronik", "OMP Hobby", "ZTW", "APD", "OpenYGE", "FLYROTOR", "Graupner", "XDFly", "Record"};   // esc_sensor_protocol 0-13

FLASHMEM static const char *BasPageWord() { return CurrentView == BASICS2VIEW ? "page Basics2View" : "page BasicsView"; }
FLASHMEM static void BasBusy(const char *msg)
{
    SendCommand((char *)(msg && *msg ? "vis busy,1" : "vis busy,0"));
    if (msg && *msg)
        SendText((char *)"busy", (char *)msg);
}
FLASHMEM static unsigned BasU16(const uint8_t *b, int o) { return (unsigned)(b[o] | (b[o + 1] << 8)); }
FLASHMEM static void BasPutU16(uint8_t *b, int o, long v) { if (v < 0) v = 0; if (v > 65535) v = 65535; b[o] = (uint8_t)(v & 0xFF); b[o + 1] = (uint8_t)(v >> 8); }
FLASHMEM static int BasProtoIndex(uint8_t code) { for (int i = 0; i < 6; ++i) if (BasProtoCodes[i] == code) return i; return -1; }
FLASHMEM static void BasNum(const char *name, long v)
{
    char b[16];
    snprintf(b, sizeof(b), "%ld", v);
    SendText((char *)name, b);
}
FLASHMEM static long BasFieldTenths(const char *name, long lo, long hi) // "10.2" -> 102
{
    char t[24] = "";
    GetText((char *)name, t, sizeof(t) - 1);
    const float f = (float)atof(t);
    long v = (long)(f * 10.0f + (f >= 0 ? 0.5f : -0.5f));
    return v < lo ? lo : v > hi ? hi : v;
}
// the five told-and-tapped rows of page 1, one at a time (a tap changes one; the typed pole count is left alone)
FLASHMEM static void BasShowSwash() { SendText((char *)"tn0", (char *)(BasMixWant[5] < 7 ? BasSwashWords[BasMixWant[5]] : "?")); }
FLASHMEM static void BasShowDirection() { SendText((char *)"tn1", (char *)(BasMixWant[0] ? "Anticlockwise" : "Clockwise")); }
FLASHMEM static void BasShowTail() { SendText((char *)"tn2", (char *)(BasMixWant[1] < 3 ? BasTailWords[BasMixWant[1]] : "?")); }
FLASHMEM static void BasShowProtocol()
{
    const int pi = BasProtoIndex(BasMotWant[9]);
    if (pi >= 0) { SendText((char *)"tn3", (char *)BasProtoWords[pi]); return; }
    char b[24];
    snprintf(b, sizeof(b), "Protocol %d", BasMotWant[9]);   // (one this page does not list: a tap takes it to PWM)
    SendText((char *)"tn3", b);
}
FLASHMEM static void BasShowEsc() { SendText((char *)"tn4", (char *)(!BasEscHave ? "?" : BasEscWant[0] < 14 ? BasEscWords[BasEscWant[0]] : "?")); }
FLASHMEM static void BasShowPage1()
{
    BasShowSwash(); BasShowDirection(); BasShowTail(); BasShowProtocol(); BasShowEsc();
    BasNum("tn5", BasMotWant[13]);
}
FLASHMEM static void BasShowPage2()
{
    BasNum("tn0", BasU16(BasMotWant, 21)); BasNum("tn1", BasU16(BasMotWant, 23));   // main gear ratio: rotor : motor (the configurator's two numbers; 1 : 1 = direct drive)
    BasNum("tn2", BasU16(BasMotWant, 25)); BasNum("tn3", BasU16(BasMotWant, 27));   // tail gear ratio: rotor : tail
}
FLASHMEM static void BasShow()
{
    if (CurrentView == BASICSVIEW) BasShowPage1();
    else if (CurrentView == BASICS2VIEW) BasShowPage2();
}
FLASHMEM static void BasPageHead()
{
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)"All banks");   // (the basics are the model's, not a bank's - as the filters page says)
    SendCommand((char *)(Bas_Was_Edited ? "vis b3,1" : "vis b3,0"));
}
FLASHMEM static void BasGatherPage1()
{
    long p = FieldNumber("tn5", 2, 64);
    if (p & 1) --p;   // magnets come in pairs
    BasMotWant[13] = (uint8_t)p;
}
FLASHMEM static void BasPair(const char *na, const char *nb, int off) // two ratio numbers as typed - whole (teeth: 10 and 102), or with a decimal (turns: 1 and 10.2 -> 10 : 102, the whole numbers Rotorflight keeps)
{
    long a = BasFieldTenths(na, 0, 655350), b = BasFieldTenths(nb, 0, 655350);
    if (a % 10 == 0 && b % 10 == 0) { a /= 10; b /= 10; }
    if (a < 1) a = 1;
    if (b < 1) b = 1;
    BasPutU16(BasMotWant, off, a);
    BasPutU16(BasMotWant, off + 2, b);
}
FLASHMEM static void BasGatherPage2() { BasPair("tn0", "tn1", 21); BasPair("tn2", "tn3", 25); }
FLASHMEM static void BasGather()
{
    if (CurrentView == BASICSVIEW) BasGatherPage1();
    else if (CurrentView == BASICS2VIEW) BasGatherPage2();
}
FLASHMEM static void BasFail(const char *what)
{
    char msg[180];
    snprintf(msg, sizeof(msg), "%s:\r\n%.140s", what, PipeRepCode ? PipeRepBody : "the screen could not ask (no Bluetooth)");
    BasStep = BAS_IDLE;
    BasBusy("");
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)BasPageWord(), msg);
    BasPageHead();
    BasShow();
}
FLASHMEM static void BasRead()
{
    BasBusy("Reading from the flight controller ...");
    BasReq = MspAsk(42, nullptr, 0);
    BasStep = BAS_READ_MIX;
}
FLASHMEM static bool BasTake(uint8_t *dst, int need) // a reply's bytes, if enough came
{
    uint8_t b[40];
    const int n = PipeReplyBytes(b, sizeof(b));
    if (n < need) { snprintf(PipeRepBody, sizeof(PipeRepBody), "only %d bytes came (Rotorflight 2.3 sends %d)", n, need); return false; }
    memcpy(dst, b, need);
    return true;
}
FLASHMEM static void BasMotorFrame(uint8_t *w) { memcpy(w, BasMotWant, 6); memcpy(w + 6, BasMotWant + 7, 22); }   // the 28 bytes of a 222 from the 29 of a 131: no motor-count byte
FLASHMEM static void BasAskAgain() // after the restart: the flight controller is asked until it answers (5 s first, then every 2.5 s, five times)
{
    BasWaitUntil = millis() + (BasTries ? 2500 : 5000);
    BasStep = BAS_WAIT;
}
FLASHMEM void BasicsPoll()
{
    if (CurrentView != BASICSVIEW && CurrentView != BASICS2VIEW) { BasStep = BAS_IDLE; BasMsgUntil = 0; return; }
    if (BasMsgUntil && (int32_t)(millis() - BasMsgUntil) >= 0) { BasMsgUntil = 0; BasBusy(""); BasShow(); }
    if (BasStep == BAS_IDLE) return;
    if (BasStep == BAS_WAIT)
    {
        if ((int32_t)(millis() - BasWaitUntil) < 0) return;
        BasReq = MspAsk(42, nullptr, 0); BasStep = BAS_VERIFY_MIX; ++BasTries;
        return;
    }
    if (!PipeReplyReady(BasReq))
    {
        if (!PipeReplyLate()) return;
        if (BasStep == BAS_VERIFY_MIX && BasTries) { if (BasTries < 5) { BasAskAgain(); return; } BasFail("The flight controller has not come back"); return; }
        BasFail("No answer");
        return;
    }
    const bool ok = PipeRepCode == 200;
    switch (BasStep)
    {
    case BAS_READ_MIX:
        if (!ok || !BasTake(BasMix, BAS_MIX_BYTES)) { BasFail("Could not read the mixer"); return; }
        BasReq = MspAsk(131, nullptr, 0); BasStep = BAS_READ_MOT;
        return;
    case BAS_READ_MOT:
        if (!ok || !BasTake(BasMot, BAS_MOT_BYTES)) { BasFail("Could not read the motor setup"); return; }
        BasReq = MspAsk(123, nullptr, 0); BasStep = BAS_READ_ESC;
        return;
    case BAS_READ_ESC:
        BasEscHave = ok && BasTake(BasEsc, BAS_ESC_BYTES);   // (optional: a flight controller built without ESC telemetry has none)
        memcpy(BasMixWant, BasMix, BAS_MIX_BYTES); memcpy(BasMotWant, BasMot, BAS_MOT_BYTES); memcpy(BasEscWant, BasEsc, BAS_ESC_BYTES);
        BasHave = true; BasStep = BAS_IDLE; Bas_Was_Edited = false;
        BasBusy(""); SendCommand((char *)"vis b3,0"); BasShow();
        return;
    case BAS_WRITE_MIX:
    {
        if (!ok) { BasFail("Not written (mixer)"); return; }
        uint8_t w[28];
        BasMotorFrame(w);
        BasReq = MspAsk(222, w, 28); BasStep = BAS_WRITE_MOT;
        return;
    }
    case BAS_WRITE_MOT:
        if (!ok) { BasFail("Not written (motor setup)"); return; }
        if (BasEscHave) { BasReq = MspAsk(216, BasEscWant, BAS_ESC_BYTES); BasStep = BAS_WRITE_ESC; return; }
        BasReq = MspAsk(250, nullptr, 0); BasStep = BAS_STORE;
        return;
    case BAS_WRITE_ESC:
        if (!ok) { BasFail("Not written (ESC telemetry)"); return; }
        BasReq = MspAsk(250, nullptr, 0); BasStep = BAS_STORE;
        return;
    case BAS_STORE:
        if (!ok) { BasFail("Not stored"); return; }
        BasTries = 0;
        if (BakOffline()) { BasReq = MspAsk(42, nullptr, 0); BasStep = BAS_VERIFY_MIX; return; }   // (the backup on the card: nothing to restart)
        BasBusy("Restarting the flight controller to apply them ...");
        BasReq = MspAsk(68, nullptr, 0); BasStep = BAS_REBOOT;
        return;
    case BAS_REBOOT:
        if (!ok) { BasFail("Not restarted"); return; }
        BasAskAgain();
        return;
    case BAS_VERIFY_MIX:
        if (!ok || !BasTake(BasMix, BAS_MIX_BYTES)) { if (BasTries && BasTries < 5) { BasAskAgain(); return; } BasFail(BasTries ? "The flight controller has not come back" : "Could not read back"); return; }
        BasReq = MspAsk(131, nullptr, 0); BasStep = BAS_VERIFY_MOT;
        return;
    case BAS_VERIFY_MOT:
        if (!ok || !BasTake(BasMot, BAS_MOT_BYTES)) { BasFail("Could not read back the motor setup"); return; }
        BasReq = MspAsk(123, nullptr, 0); BasStep = BAS_VERIFY_ESC;
        return;
    case BAS_VERIFY_ESC:
    {
        const bool escOk = ok && BasTake(BasEsc, BAS_ESC_BYTES);
        const bool same = memcmp(BasMix, BasMixWant, BAS_MIX_BYTES) == 0 && memcmp(BasMot, BasMotWant, 6) == 0 && memcmp(BasMot + 7, BasMotWant + 7, 22) == 0 &&
                          (!BasEscHave || (escOk && memcmp(BasEsc, BasEscWant, BAS_ESC_BYTES) == 0));
        memcpy(BasMixWant, BasMix, BAS_MIX_BYTES); memcpy(BasMotWant, BasMot, BAS_MOT_BYTES);
        if (escOk) memcpy(BasEscWant, BasEsc, BAS_ESC_BYTES);
        BasStep = BAS_IDLE; Bas_Was_Edited = false;
        SendCommand((char *)"vis b3,0"); BasShow();
        BasBusy(same ? "Saved, and read back the same." : "Saved, but the flight controller adjusted some values.");
        BasMsgUntil = millis() + 4000;
        PlaySound(BEEPCOMPLETE);
        return;
    }
    default:
        BasStep = BAS_IDLE;
        return;
    }
}
FLASHMEM void StartBasicsView() // the settings page's "Model basics ..."
{
    char why[120];
    if (RfNeedsModel(why, sizeof(why)) || ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFSetupView", why);
        return;
    }
    if (CurrentView == RFSETUPVIEW) RFSettingsGather();   // the settings page's own edits kept, as its OK keeps them
    SendCommand((char *)"page BasicsView");
    CurrentView = BASICSVIEW;
    Bas_Was_Edited = false;
    BasPageHead();
    BasRead();
}
FLASHMEM void EndBasicsView() // OK on either page: back to the menu
{
    if (Bas_Was_Edited)
    {
        BasGather();   // (B59) before the question's page takes the fields away
        if (!GetConfirmation((char *)BasPageWord(), (char *)"Discard the edited basics?"))
        {
            BasPageHead();
            BasShow();
            return;
        }
    }
    BasStep = BAS_IDLE;
    Bas_Was_Edited = false;
    RotorFlightStart();
}
FLASHMEM void StartBasics2View() // Next > on page 1: the gear ratios
{
    BasGather();
    SendCommand((char *)"page Basics2View");
    CurrentView = BASICS2VIEW;
    BasPageHead();
    if (BasHave) BasShowPage2(); else BasRead();
}
FLASHMEM void EndBasics2View() // < Previous on page 2
{
    BasGather();
    SendCommand((char *)"page BasicsView");
    CurrentView = BASICSVIEW;
    BasPageHead();
    if (BasHave) BasShowPage1(); else BasRead();
}
FLASHMEM void BasicsWasEdited() { SendCommand((char *)"vis b3,1"); Bas_Was_Edited = true; }
FLASHMEM void BasicsSwashTapped() { if (!BasHave) return; BasMixWant[5] = (uint8_t)((BasMixWant[5] + 1) % 7); BasShowSwash(); BasicsWasEdited(); }
FLASHMEM void BasicsDirectionTapped() { if (!BasHave) return; BasMixWant[0] = BasMixWant[0] ? 0 : 1; BasShowDirection(); BasicsWasEdited(); }
FLASHMEM void BasicsTailTapped() { if (!BasHave) return; BasMixWant[1] = (uint8_t)((BasMixWant[1] + 1) % 3); BasShowTail(); BasicsWasEdited(); }
FLASHMEM void BasicsProtocolTapped() { if (!BasHave) return; const int i = BasProtoIndex(BasMotWant[9]); BasMotWant[9] = BasProtoCodes[i < 0 ? 0 : (i + 1) % 6]; BasShowProtocol(); BasicsWasEdited(); }
FLASHMEM void BasicsEscTapped() { if (!BasHave || !BasEscHave) return; BasEscWant[0] = (uint8_t)((BasEscWant[0] + 1) % 14); BasShowEsc(); BasicsWasEdited(); }
FLASHMEM void SaveBasics()
{
    if (!BasHave || BasStep != BAS_IDLE)   // (a Save while a read or a save runs is ignored)
        return;
    char why[120];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)BasPageWord(), why);
        return;
    }
    BasGather();   // (B59) the fields first: the question is a page of its own
    char q[180];
    const unsigned mr = BasU16(BasMotWant, 21), mm = BasU16(BasMotWant, 23);
    if (mr > mm)   // (the Goblin, 2 Sep: a backwards ratio put the governor at minimum throttle)
        snprintf(q, sizeof(q), "The main gear ratio looks backwards:\r\nrotor %u : motor %u - the rotor would turn\r\nfaster than the motor, and the governor\r\nwould sit at minimum throttle. Save anyway?", mr, mm);
    else
        snprintf(q, sizeof(q), "%s", BakOffline() ? "Save the basics to the backup?\r\nThey go to the model when it next connects." : "Save the basics?\r\nThe flight controller restarts to apply them:\r\nallow a few seconds.");
    if (!GetConfirmation((char *)BasPageWord(), q))
    {
        BasPageHead();
        BasShow();   // the page came back blank: the edited values again
        return;
    }
    BasPageHead();
    BasShow();
    BasBusy("Writing to the flight controller ...");
    BasReq = MspAsk(43, BasMixWant, BAS_MIX_BYTES);
    BasStep = BAS_WRITE_MIX;
}
#endif
