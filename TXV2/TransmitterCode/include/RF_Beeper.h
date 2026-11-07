// B195 (Malcolm, 6 Nov 2026: the Rotorflight gap list, Phase 1 - "for 16meg screens only"): BEEPER & NAME, page 84
// (BeeperView, made by the screen project's hmi/beeper_pages.py), from the Rotorflight menu's "Beeper & name ...".
//  - NAME: Rotorflight's own name for the model (MSP 10 read: the name's bytes, none when it has none / 11 write, up to 16;
//    the receiver refuses a write with no bytes, so an empty name goes as one 0 byte - msp.c clears the name first).
//  - BEEPER: MSP 184 read (9 bytes: u32 the buzzer's OFF flags, u8 the DShot beacon's tone 1-5, u32 the beacon's OFF flags)
//    / 185 write. A flag is 1 << (event - 1), release/4.6.0 src/main/io/beeper.h; a switch ON = the event beeps = its OFF
//    flag clear. Only the eight buzzer events on the page and the beacon's two (RX_SET, RX_LOST: DSHOT_BEACON_ALLOWED_MODES)
//    change; every other bit goes back as read.
// A save writes 11 then 185, stores (250) and reads both back: "Saved, and read back the same." or the difference.
// With no model the backup answers (RF_Backup.h: 10 and, since B195, 184 in the sweep; 11 -> 10 and 185 -> 184 patched).
// Byte for byte release/4.6.0 src/main/msp/msp.c (MSP_NAME, MSP_SET_NAME, MSP_BEEPER_CONFIG, MSP_SET_BEEPER_CONFIG).
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_BEEPER_H
#define RF_BEEPER_H

static const int BP_BYTES = 9;
static const int BP_NAME_MAX = 16;
// the page's switches sw1..sw8 = these buzzer events (beeper.h's numbers), sw9/sw10 = the beacon's
static const uint8_t BP_BUZZ[8] = {17, 5, 4, 16, 2, 8, 7, 10};   // power on, arming, disarming, armed (motor stopped), link lost, battery low, battery very low, the Beeper switch
static const uint8_t BP_BEACON[2] = {10, 2};                       // the Beeper switch (RX_SET), link lost (RX_LOST)
static uint8_t BpRaw[16], BpWant[16];
static char BpNameRaw[BP_NAME_MAX + 1], BpNameWant[BP_NAME_MAX + 1];
static int BpN = 0;
static bool BpHave = false, Bp_Was_Edited = false, BpSame = true;
enum { BP_IDLE = 0, BP_READ_NAME, BP_READ, BP_WRITE_NAME, BP_WRITE, BP_STORE, BP_VERIFY_NAME, BP_VERIFY };
static int BpStep = BP_IDLE, BpReq = 0;
static uint32_t BpMsgUntil = 0;

FLASHMEM static uint32_t BpFlag(uint8_t ev) { return 1UL << (ev - 1); }
FLASHMEM static void BpPutU32(uint8_t *b, int o, uint32_t v) { b[o] = v & 0xFF; b[o + 1] = (v >> 8) & 0xFF; b[o + 2] = (v >> 16) & 0xFF; b[o + 3] = (v >> 24) & 0xFF; }
FLASHMEM static void BpNameFrom(const uint8_t *b, int n, char *out) // the bytes as a name: printable only, at most 16
{
    int k = 0;
    for (int i = 0; i < n && k < BP_NAME_MAX; ++i)
        if (b[i] >= 32 && b[i] < 127) out[k++] = (char)b[i];
    out[k] = 0;
}
FLASHMEM static void BpHead()
{
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)"All banks");
    SendCommand((char *)(Bp_Was_Edited ? "vis b3,1" : "vis b3,0"));
}
FLASHMEM static void BpShow()
{
    if (CurrentView != BEEPERVIEW || !BpHave) return;
    SendText((char *)"tn0", BpNameWant);
    const uint32_t off = RdU32(BpWant, 0), boff = RdU32(BpWant, 5);
    char n[6];
    for (int k = 0; k < 8; ++k) { snprintf(n, sizeof(n), "sw%d", k + 1); SendValue(n, (off & BpFlag(BP_BUZZ[k])) ? 0 : 1); }
    for (int k = 0; k < 2; ++k) { snprintf(n, sizeof(n), "sw%d", k + 9); SendValue(n, (boff & BpFlag(BP_BEACON[k])) ? 0 : 1); }
    FsNum("tn1", BpWant[4]);
}
FLASHMEM static void BpGather() // the page into BpWant / BpNameWant (an unanswered box: GetValue / GetText mark it missed)
{
    if (CurrentView != BEEPERVIEW || !BpHave) return;
    char t[BP_NAME_MAX + 8] = "";
    GetText((char *)"tn0", t, sizeof(t) - 1);
    BpNameFrom((const uint8_t *)t, (int)strlen(t), BpNameWant);
    uint32_t off = RdU32(BpWant, 0), boff = RdU32(BpWant, 5);
    char n[6];
    for (int k = 0; k < 8; ++k)
    {
        snprintf(n, sizeof(n), "sw%d", k + 1);
        const uint32_t v = GetValue(n);
        if (v <= 1) off = v ? (off & ~BpFlag(BP_BUZZ[k])) : (off | BpFlag(BP_BUZZ[k]));
    }
    for (int k = 0; k < 2; ++k)
    {
        snprintf(n, sizeof(n), "sw%d", k + 9);
        const uint32_t v = GetValue(n);
        if (v <= 1) boff = v ? (boff & ~BpFlag(BP_BEACON[k])) : (boff | BpFlag(BP_BEACON[k]));
    }
    BpPutU32(BpWant, 0, off);
    BpPutU32(BpWant, 5, boff);
    BpWant[4] = (uint8_t)FieldNumber("tn1", 1, 5);
}
FLASHMEM static void BpFail(const char *what) { BpStep = BP_IDLE; FsFail("page BeeperView", what); BpHead(); BpShow(); }
FLASHMEM static void BpWriteName()
{
    uint8_t d[BP_NAME_MAX];
    int n = (int)strlen(BpNameWant);
    memcpy(d, BpNameWant, (size_t)n);
    if (n == 0) { d[0] = 0; n = 1; }   // (the receiver refuses a write with nothing in it: one 0 byte = no name)
    BpReq = MspAsk(11, d, n); BpStep = BP_WRITE_NAME;
}
FLASHMEM void BeeperPoll()
{
    if (CurrentView != BEEPERVIEW) { BpStep = BP_IDLE; BpMsgUntil = 0; return; }
    if (BpMsgUntil && (int32_t)(millis() - BpMsgUntil) >= 0) { BpMsgUntil = 0; FsBusy(""); BpShow(); }
    if (BpStep == BP_IDLE) return;
    if (!PipeReplyReady(BpReq))
    {
        if (!PipeReplyLate()) return;
        BpFail("No answer");
        return;
    }
    const bool ok = PipeRepCode == 200;
    switch (BpStep)
    {
    case BP_READ_NAME:
    {
        if (!ok) { BpFail("Could not read the name"); return; }
        uint8_t b[40];
        const int n = PipeReplyBytes(b, sizeof(b));
        BpNameFrom(b, n, BpNameRaw);
        strcpy(BpNameWant, BpNameRaw);
        BpReq = MspAsk(184, nullptr, 0); BpStep = BP_READ;
        return;
    }
    case BP_READ:
        if (!ok) { BpFail("Could not read the beeper setup"); return; }
        BpN = PipeReplyBytes(BpRaw, sizeof(BpRaw));
        if (BpN < BP_BYTES) { snprintf(PipeRepBody, sizeof(PipeRepBody), "only %d bytes came (Rotorflight 2.3 sends 9)", BpN); BpFail("Could not read the beeper setup"); return; }
        memcpy(BpWant, BpRaw, sizeof(BpWant));
        BpHave = true; Bp_Was_Edited = false; BpStep = BP_IDLE;
        FsBusy(""); BpHead(); BpShow();
        return;
    case BP_WRITE_NAME:
        if (!ok) { BpFail("Not written (the name)"); return; }
        BpReq = MspAsk(185, BpWant, BP_BYTES); BpStep = BP_WRITE;
        return;
    case BP_WRITE:
        if (!ok) { BpFail("Not written (the beeper)"); return; }
        BpReq = MspAsk(250, nullptr, 0); BpStep = BP_STORE;
        return;
    case BP_STORE:
        if (!ok) { BpFail("Not stored"); return; }
        BpReq = MspAsk(10, nullptr, 0); BpStep = BP_VERIFY_NAME;
        return;
    case BP_VERIFY_NAME:
    {
        if (!ok) { BpFail("Could not read back"); return; }
        uint8_t b[40];
        char got[BP_NAME_MAX + 1];
        BpNameFrom(b, PipeReplyBytes(b, sizeof(b)), got);
        BpSame = strcmp(got, BpNameWant) == 0;
        strcpy(BpNameRaw, got); strcpy(BpNameWant, got);
        BpReq = MspAsk(184, nullptr, 0); BpStep = BP_VERIFY;
        return;
    }
    case BP_VERIFY:
    {
        if (!ok) { BpFail("Could not read back"); return; }
        uint8_t b[16];
        const int n = PipeReplyBytes(b, sizeof(b));
        if (n < BP_BYTES || memcmp(b, BpWant, BP_BYTES) != 0) BpSame = false;
        if (n >= BP_BYTES) { memcpy(BpRaw, b, sizeof(BpRaw)); memcpy(BpWant, b, sizeof(BpWant)); BpN = n; }
        BpStep = BP_IDLE; Bp_Was_Edited = false;
        BpHead(); BpShow();
        FsBusy(BpSame ? "Saved, and read back the same." : "Saved, but the flight controller adjusted some values.");
        BpMsgUntil = millis() + 4000;
        PlaySound(BEEPCOMPLETE);
        RfSavedThenLeave(BEEPERVIEW);   // (OK's "Save now?" closes the page once saved)
        return;
    }
    default:
        BpStep = BP_IDLE;
        return;
    }
}
FLASHMEM void StartBeeperView() // 232: the menu's "Beeper & name ..." (shown on a 16 MB screen only)
{
    if (!ScreenIsBig())
    { // (the menu hides the button on a 4 MB screen: this is for an older screen that has the page but not the answer)
        MsgBox((char *)"page RFView", (char *)"Beeper & name needs the 16 MB screen.");
        return;
    }
    if (FsEntryRefused()) return;
    SendCommand((char *)"page BeeperView");
    CurrentView = BEEPERVIEW;
    BpHave = false; Bp_Was_Edited = false; BpN = 0; BpNameRaw[0] = BpNameWant[0] = 0;
    BpHead();
    FsBusy("Reading from the flight controller ...");
    BpReq = MspAsk(10, nullptr, 0); BpStep = BP_READ_NAME;
}
void SaveBeeper();
FLASHMEM static void BpSaveNow() { BpHead(); BpShow(); SaveBeeper(); }
FLASHMEM void EndBeeperView() // 233: OK
{
    if (BpStep != BP_IDLE) return;   // (a save runs: wait for it)
    if (Bp_Was_Edited)
    {
        BpGather();
        if (!RfSaveFirst("page BeeperView", "The edited beeper and name are", BpSaveNow, EndBeeperView, &Bp_Was_Edited)) return;
    }
    Bp_Was_Edited = false;
    RotorFlightStart();
}
FLASHMEM void BeeperWasEdited() // 235: a switch, the name or the tone
{
    if (!BpHave) return;
    Bp_Was_Edited = true;
    SendCommand((char *)"vis b3,1");
}
FLASHMEM void SaveBeeper() // 234
{
    if (!BpHave || BpStep != BP_IDLE) return;
    if (FsRefused("page BeeperView", false)) { BpHead(); BpShow(); return; }
    RfGatherStart();
    BpGather();
    if (RfFieldsMissed("page BeeperView")) return;   // a box unanswered: nothing written
    FsBusy("Writing to the flight controller ...");
    BpWriteName();
}

#endif // RF_BEEPER_H
