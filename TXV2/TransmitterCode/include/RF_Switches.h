// B77: SWITCHES (the configurator's Modes tab) on the transmitter, over the Bluetooth pipe: what each switch of this
// transmitter makes the flight controller do - arm, rescue, self-level, the beeper, the black box and the rest. One
// switch action at a time, as the adjustments page: "Does [Rescue - the safety net] on [Channel 8: AUX3]" and the BAR,
// whose one zone is where the action is ON; the blobs set its ends, the marker is the switch now.
//
// Rotorflight keeps 20 slots (MSP 34, 4 bytes each: the mode's permanent id, the AUX index, the ends as signed 5 us
// steps about 1500 - NOT Betaflight's 25 us steps; a slot whose high end is not above its low end is unused); a slot
// is written with 35 (slot, id, aux, lo, hi) and stored with 250. The names are the phone page's (RXV2
// data/rotorflight-modes.html: plain English first, Rotorflight's own in brackets).
//
// THE ARM SWITCH IS THIS TRANSMITTER'S SAFETY SWITCH: with a Rotorflight model the safety drives the arming channel
// (FixArmingChannel: 667 us safe, 2233 us armed, which the flight controller sees as 988 and 2012). So the arm action
// stays on that channel, cannot be removed (Rotorflight requires one), and a save refuses an ON zone that would arm with
// the safety on (a zone reaching 988) or would not arm with it off (a zone stopping short of 2012).
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_SWITCHES_H
#define RF_SWITCHES_H

static const int SW_SLOTS = 20;
struct SwSlot { uint8_t perm, aux; int16_t lo, hi; };
DMAMEM static SwSlot SwRead[SW_SLOTS], SwNow[SW_SLOTS];   // as read from the flight controller, and as edited
static int SwShown[SW_SLOTS];                               // the slots in use, in order: what the arrows walk through
static int SwN = 0, SwAt = 0;
static bool SwHave = false, Sw_Was_Edited = false;
enum { SW_IDLE = 0, SW_READ, SW_WRITE, SW_STORE, SW_VERIFY };
static int SwStep = SW_IDLE, SwReq = 0, SwTries = 0, SwWriteAt = 0;
static uint32_t SwMsgUntil = 0, SwLiveMs = 0;
static int SwLiveCh = -1, SwLiveUs = -1;
static uint8_t SwPickPerm = 0;                              // what the picker is for: 0 the row showing, else a new action
struct SwMode { uint8_t id; const char *name; };
static const SwMode SwModes[] PROGMEM = {
    {0, "Arm - motor enable (ARM)"}, {53, "Rescue - the safety net (RESCUE)"}, {1, "Self-level (ANGLE)"}, {2, "Self-level, blended (HORIZON)"},
    {3, "Altitude hold (ALTHOLD)"}, {47, "Acro trainer (TRAINER)"}, {46, "GPS rescue (GPS RESCUE)"}, {27, "Failsafe test (FAILSAFE)"},
    {13, "Beeper on (BEEPER)"}, {52, "Beeper mute (BEEPER MUTE)"}, {26, "Black box recording (BLACKBOX)"}, {31, "Black box erase (BLACKBOX ERASE)"},
    {36, "Pre-arm safety (PREARM)"}, {45, "Lock the model - anti-tamper (PARALYZE)"}, {55, "Governor fallback (GOVERNOR FALLBACK)"},
    {56, "Governor suspend (GOVERNOR SUSPEND)"}, {57, "Governor bypass (GOVERNOR BYPASS)"}, {17, "Calibrate (CALIB)"}, {20, "Telemetry on/off (TELEMETRY)"},
    {51, "Stick commands off (STICK COMMANDS DISABLE)"}, {40, "User switch 1 (USER1)"}, {41, "User switch 2 (USER2)"}, {42, "User switch 3 (USER3)"}, {43, "User switch 4 (USER4)"}};
static const int SW_MODES = sizeof(SwModes) / sizeof(SwModes[0]);   // (hmi/switch_pages.py lists them in this order)
FLASHMEM static const char *SwModeName(uint8_t id) { for (int i = 0; i < SW_MODES; ++i) if (SwModes[i].id == id) return SwModes[i].name; return "(unknown mode)"; }
FLASHMEM static int SwModeIdx(uint8_t id) { for (int i = 0; i < SW_MODES; ++i) if (SwModes[i].id == id) return i; return 0; }
static inline int SwUs(uint8_t b) { return 1500 + 5 * (b > 127 ? (int)b - 256 : (int)b); }
static inline uint8_t SwStepOf(int us) { int st = (int)floorf((float)(us - 1500) / 5.0f + 0.5f); if (st < -125) st = -125; if (st > 125) st = 125; return (uint8_t)(st < 0 ? st + 256 : st); }
static inline bool SwUsed(const SwSlot &s) { return s.hi > s.lo; }
static inline bool SwSame(const SwSlot &a, const SwSlot &b) { return a.perm == b.perm && a.aux == b.aux && SwStepOf(a.lo) == SwStepOf(b.lo) && SwStepOf(a.hi) == SwStepOf(b.hi); }
FLASHMEM static int SwArmChannel() { return (RotorFlight_V && ArmingChannel >= 1 && ArmingChannel <= CHANNELSUSED) ? ArmingChannel : 0; }   // 1-based, 0 = none set

FLASHMEM static void SwBusy(const char *msg)
{
    SendCommand((char *)(msg && *msg ? "vis busy,1" : "vis busy,0"));
    if (msg && *msg) SendText((char *)"busy", (char *)msg);
}
FLASHMEM static void SwText(const char *name, const char *t) { SendText((char *)name, (char *)t); }
FLASHMEM static void SwHead()
{
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)"Bluetooth");
    SendCommand((char *)(Sw_Was_Edited ? "vis b3,1" : "vis b3,0"));
}
FLASHMEM static void SwList() // the slots in use, in slot order
{
    SwN = 0;
    for (int i = 0; i < SW_SLOTS; ++i) if (SwUsed(SwNow[i])) SwShown[SwN++] = i;
    if (SwAt >= SwN) SwAt = SwN ? SwN - 1 : 0;
}
FLASHMEM static int SwFcUs(uint16_t txUs)
{
    long v = 1500 + ((long)txUs - 1500) * 819L * 5L / (500L * 8L);
    if (v < 988) v = 988;
    if (v > 2012) v = 2012;
    return (int)v;
}
FLASHMEM static void SwLive() // the switch's position now, from this transmitter's own output, on the bar and under it
{
    if (!SwN) { if (SwLiveCh != -1) { SwLiveCh = -1; SwText("tn8", ""); } return; }
    const SwSlot &s = SwNow[SwShown[SwAt]];
    const int ch = s.aux + 6;
    const int us = (ch >= 1 && ch <= CHANNELSUSED) ? SwFcUs(SendBuffer[ch - 1]) : -1;
    if (ch == SwLiveCh && us == SwLiveUs) return;
    SwLiveCh = ch; SwLiveUs = us;
    char c[24], b[48];
    snprintf(c, sizeof(c), "bar.mk=%d", us); SendCommand(c);
    if (us < 0) snprintf(b, sizeof(b), "Channel %d: ?", ch);
    else snprintf(b, sizeof(b), "%s: %d us", (us >= s.lo && us <= s.hi) ? "ON" : "OFF", us);
    SwText("tn8", b);
}
FLASHMEM static void SwShow()
{
    char b[64];
    if (SwN) snprintf(b, sizeof(b), "Switch %d of %d", SwAt + 1, SwN); else snprintf(b, sizeof(b), "Switches: none");
    SwText("t0", b);
    if (!SwN)
    {
        SwText("tn0", (char *)"(none: press Add)"); SwText("tn1", (char *)""); SwText("tn8", (char *)"");
        SendCommand((char *)"bar.n=1"); SendCommand((char *)"bar.kind=0"); SendCommand((char *)"bar.mk=-1"); SwText("bar", (char *)"");
        SwText("hint", (char *)"");
        return;
    }
    const SwSlot &s = SwNow[SwShown[SwAt]];
    SwText("tn0", SwModeName(s.perm));
    const int ch = s.aux + 6;
    snprintf(b, sizeof(b), "Channel %d: %s", ch, (ch >= 1 && ch <= CHANNELSUSED) ? ChannelNames[ch - 1] : "?");
    SwText("tn1", b);
    SendCommand((char *)"bar.kind=1"); SendCommand((char *)"bar.n=3");
    snprintf(b, sizeof(b), "bar.d0=%d", s.lo); SendCommand(b); snprintf(b, sizeof(b), "bar.d1=%d", s.hi); SendCommand(b);
    SwText("bar", (char *)"|ON|");
    SwText("hint", (char *)(s.perm == 0 ? "The arm switch is the safety switch: ON must reach 2012 us and stay above 988 us." : "Drag the blobs to set where the switch turns it on."));
    SwLiveCh = -1;
    SwLive();
}
FLASHMEM static void SwEdited() { Sw_Was_Edited = true; SendCommand((char *)"vis b3,1"); }
FLASHMEM static void SwFail(const char *what, bool leave)
{
    char msg[200];
    snprintf(msg, sizeof(msg), "%s:\r\n%.150s", what, PipeRepCode ? PipeRepBody : "the screen could not ask (no Bluetooth)");
    SwStep = SW_IDLE;
    SwBusy("");
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)(leave ? "page RFView" : "page SwitchView"), msg);
    if (leave) { RotorFlightStart(); return; }
    SwHead(); SwShow();
}
FLASHMEM static bool SwTake(const uint8_t *b, int n) // the 34 image -> the slots
{
    if (n < SW_SLOTS * 4) return false;
    for (int i = 0; i < SW_SLOTS; ++i) { SwRead[i].perm = b[i * 4]; SwRead[i].aux = b[i * 4 + 1]; SwRead[i].lo = (int16_t)SwUs(b[i * 4 + 2]); SwRead[i].hi = (int16_t)SwUs(b[i * 4 + 3]); SwNow[i] = SwRead[i]; }
    SwList();
    return true;
}
FLASHMEM static void SwRead_()
{
    SwBusy("Reading the switches ...");
    SwReq = MspAsk(34, nullptr, 0); SwStep = SW_READ; SwTries = 0;
}
FLASHMEM static void SwWriteNext() // the next slot that differs from what the flight controller has; none left: store
{
    while (SwWriteAt < SW_SLOTS && SwSame(SwNow[SwWriteAt], SwRead[SwWriteAt])) ++SwWriteAt;
    if (SwWriteAt >= SW_SLOTS) { SwBusy("Storing ..."); SwReq = MspAsk(250, nullptr, 0); SwStep = SW_STORE; return; }
    const SwSlot &s = SwNow[SwWriteAt];
    uint8_t d[5] = {(uint8_t)SwWriteAt, s.perm, s.aux, SwStepOf(s.lo), SwStepOf(s.hi)};
    char m[48];
    snprintf(m, sizeof(m), "Writing switch slot %d ...", SwWriteAt + 1);
    SwBusy(m);
    SwReq = MspAsk(35, d, 5); SwStep = SW_WRITE;
}
FLASHMEM void SwitchPoll()
{
    if (CurrentView != SWITCHVIEW) { SwStep = SW_IDLE; SwMsgUntil = 0; return; }
    if (SwMsgUntil && (int32_t)(millis() - SwMsgUntil) >= 0) { SwMsgUntil = 0; SwBusy(""); }
    if (SwStep == SW_IDLE)
    {
        if ((int32_t)(millis() - SwLiveMs) >= 300) { SwLiveMs = millis(); SwLive(); }
        return;
    }
    if (!PipeReplyReady(SwReq))
    {
        if (!PipeReplyLate()) return;
        SwFail("No answer", SwStep == SW_READ);
        return;
    }
    const bool ok = PipeRepCode == 200;
    const bool again = (PipeRepCode == 503 || PipeRepCode == 504) && SwTries < 5;
    switch (SwStep)
    {
    case SW_READ:
    {
        if (again) { ++SwTries; SwReq = MspAsk(34, nullptr, 0); return; }
        if (!ok) { SwFail("Could not read the switches", true); return; }
        uint8_t b[96];
        const int n = PipeReplyBytes(b, sizeof(b));
        if (!SwTake(b, n)) { snprintf(PipeRepBody, sizeof(PipeRepBody), "only %d bytes came (Rotorflight sends 80)", n); SwFail("Could not read the switches", true); return; }
        SwHave = true; Sw_Was_Edited = false; SwStep = SW_IDLE;
        SwBusy(""); SwHead(); SwShow();
        return;
    }
    case SW_WRITE:
        if (again) { ++SwTries; SwWriteNext(); return; }
        if (!ok) { char w[40]; snprintf(w, sizeof(w), "Slot %d was not written", SwWriteAt + 1); SwFail(w, false); return; }
        SwTries = 0; ++SwWriteAt;
        SwWriteNext();
        return;
    case SW_STORE:
        if (again) { ++SwTries; SwReq = MspAsk(250, nullptr, 0); return; }
        if (!ok) { SwFail("Not stored", false); return; }
        SwTries = 0;
        SwReq = MspAsk(34, nullptr, 0); SwStep = SW_VERIFY;
        return;
    case SW_VERIFY:
    {
        if (again) { ++SwTries; SwReq = MspAsk(34, nullptr, 0); return; }
        if (!ok) { SwFail("Could not read back", false); return; }
        uint8_t b[96];
        const int n = PipeReplyBytes(b, sizeof(b));
        SwSlot want[SW_SLOTS];
        memcpy(want, SwNow, sizeof(want));
        if (!SwTake(b, n)) { SwFail("Could not read back", false); return; }
        bool same = true;
        for (int i = 0; i < SW_SLOTS; ++i) if (!SwSame(want[i], SwNow[i])) same = false;
        Sw_Was_Edited = false; SwStep = SW_IDLE;
        SwHead(); SwShow();
        SwBusy(same ? "Saved, and read back the same." : "Saved; the flight controller changed some of it (shown).");
        SwMsgUntil = millis() + 4000;
        PlaySound(BEEPCOMPLETE);
        return;
    }
    default:
        SwStep = SW_IDLE;
        return;
    }
}
FLASHMEM void StartSwitchView() // the menu's Switches ...
{
    char why[120];
    if (RfNeedsModel(why, sizeof(why)) || ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFView", why);
        return;
    }
    SendCommand((char *)"page SwitchView");
    CurrentView = SWITCHVIEW;
    Sw_Was_Edited = false; SwHave = false; SwN = 0; SwAt = 0;
    SwHead();
    SwShow();
    SwRead_();
}
FLASHMEM void EndSwitchView() // OK
{
    if (SwStep != SW_IDLE) return;
    if (Sw_Was_Edited && !GetConfirmation((char *)"page SwitchView", (char *)"Discard the edited switches?")) { SwHead(); SwShow(); return; }
    Sw_Was_Edited = false;
    RotorFlightStart();
}
FLASHMEM static bool SwArmOk(const SwSlot &s, char *why, size_t n) // the arm action and this transmitter's safety switch agree
{
    if (s.perm != 0) return true;
    const int ac = SwArmChannel();
    if (ac && s.aux + 6 != ac) { snprintf(why, n, "The arm switch must be on channel %d,\r\nthis model's arming channel (Settings).", ac); return false; }
    if (s.lo <= 988) { snprintf(why, n, "The arm zone reaches 988 us: the model\r\nwould arm with the safety ON. Move the\r\nleft blob above 988."); return false; }
    if (s.hi < 2012) { snprintf(why, n, "The arm zone stops short of 2012 us: the\r\nsafety OFF would not arm. Move the right\r\nblob to the end."); return false; }
    return true;
}
FLASHMEM void SaveSwitchActions() // (SaveSwitches is the transmitter's own switches page, MenuOptions.h)
{
    if (!SwHave || SwStep != SW_IDLE) return;
    char why[140];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why))) { PlaySound(WHAHWHAHMSG); MsgBox((char *)"page SwitchView", why); SwHead(); SwShow(); return; }
    bool haveArm = false;
    for (int i = 0; i < SW_SLOTS; ++i)
    {
        if (!SwUsed(SwNow[i])) continue;
        if (SwNow[i].perm == 0) haveArm = true;
        if (!SwArmOk(SwNow[i], why, sizeof(why))) { PlaySound(WHAHWHAHMSG); MsgBox((char *)"page SwitchView", why); SwHead(); SwShow(); return; }
    }
    if (!haveArm) { PlaySound(WHAHWHAHMSG); MsgBox((char *)"page SwitchView", (char *)"Rotorflight needs an arm switch: add\r\n'Arm - motor enable' on this model's\r\narming channel first."); SwHead(); SwShow(); return; }
    SwWriteAt = 0; SwTries = 0;
    SwWriteNext();
}
FLASHMEM static void SwMove(int to)
{
    if (!SwN) return;
    if (to < 0) to = 0;
    if (to >= SwN) to = SwN - 1;
    SwAt = to;
    SwShow();
}
FLASHMEM void SwitchPrevious() { SwMove(SwAt - 1); }
FLASHMEM void SwitchNext() { SwMove(SwAt + 1); }
FLASHMEM void SwitchChannelTapped() // the next channel; the arm action keeps the arming channel
{
    if (!SwN) return;
    SwSlot &s = SwNow[SwShown[SwAt]];
    if (s.perm == 0 && SwArmChannel()) { MsgBox((char *)"page SwitchView", (char *)"The arm switch stays on this model's\r\narming channel (Settings)."); SwHead(); SwShow(); return; }
    int ch = s.aux + 1;
    if (ch > CHANNELSUSED - 6) ch = 0;
    s.aux = (uint8_t)ch;
    SwEdited(); SwShow();
}
FLASHMEM static void SwOpenPicker(uint8_t perm)
{
    SendCommand((char *)"page SwitchPickView");
    CurrentView = SWITCHPICKVIEW;
    SendText((char *)"t11", ModelName);
    SendValue((char *)"list", SwModeIdx(perm));
}
FLASHMEM void SwitchModeTapped() { if (!SwN) return; SwPickPerm = 0; SwOpenPicker(SwNow[SwShown[SwAt]].perm); }
FLASHMEM static void SwPickLeave()
{
    SendCommand((char *)"page SwitchView");
    CurrentView = SWITCHVIEW;
    SwHead(); SwShow();
}
FLASHMEM void SwitchPickOk()
{
    const int idx = (int)GetValue((char *)"list");
    const uint8_t perm = (idx >= 0 && idx < SW_MODES) ? SwModes[idx].id : 0;
    if (SwPickPerm == 1)
    { // a new action, in the first free slot: ON in the upper third of a channel after the one showing
        int freeSlot = -1;
        for (int i = 0; i < SW_SLOTS; ++i) if (!SwUsed(SwNow[i])) { freeSlot = i; break; }
        SwPickLeave();
        if (freeSlot < 0) { MsgBox((char *)"page SwitchView", (char *)"All 20 of Rotorflight's switch slots\r\nare in use."); SwHead(); SwShow(); return; }
        SwSlot &s = SwNow[freeSlot];
        s.perm = perm;
        const int ac = SwArmChannel();
        s.aux = perm == 0 && ac ? (uint8_t)(ac - 6) : SwN ? (uint8_t)((SwNow[SwShown[SwAt]].aux + 1) % (CHANNELSUSED - 5)) : 1;
        s.lo = perm == 0 ? 1500 : 1700; s.hi = 2125;
        SwList();
        for (int i = 0; i < SwN; ++i) if (SwShown[i] == freeSlot) SwAt = i;
        SwEdited(); SwShow();
        return;
    }
    SwPickLeave();
    if (!SwN) return;
    SwSlot &s = SwNow[SwShown[SwAt]];
    if (perm == s.perm) return;
    if (s.perm == 0) { MsgBox((char *)"page SwitchView", (char *)"The arm switch stays: Rotorflight needs it.\r\nAdd another action instead."); SwHead(); SwShow(); return; }
    s.perm = perm;
    SwEdited(); SwShow();
}
FLASHMEM void SwitchPickCancel() { SwPickLeave(); }
FLASHMEM void SwitchAdd() { if (!SwHave) return; SwPickPerm = 1; SwOpenPicker(53); }
FLASHMEM void SwitchRemove()
{
    if (!SwN) return;
    SwSlot &s = SwNow[SwShown[SwAt]];
    if (s.perm == 0) { MsgBox((char *)"page SwitchView", (char *)"The arm switch cannot be removed:\r\nRotorflight needs one."); SwHead(); SwShow(); return; }
    if (!GetConfirmation((char *)"page SwitchView", (char *)"Remove this switch action?")) { SwHead(); SwShow(); return; }
    s.perm = 0; s.aux = 0; s.lo = 1500; s.hi = 1500;   // (an empty zone = the slot unused)
    SwList();
    SwEdited(); SwHead(); SwShow();
}
FLASHMEM void SwitchBarMoved() // the blobs dragged: the zone's ends as the screen has them
{
    if (!SwN || SwStep != SW_IDLE) return;
    SwSlot &s = SwNow[SwShown[SwAt]];
    const int lo = GetOtherValue((char *)"bar.d0"), hi = GetOtherValue((char *)"bar.d1");
    if (lo < 875 || hi > 2125 || hi <= lo) return;
    if (lo == s.lo && hi == s.hi) return;
    s.lo = (int16_t)lo; s.hi = (int16_t)hi;
    SwEdited(); SwShow();
}
#endif
