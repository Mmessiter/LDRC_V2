#!/usr/bin/env python3
"""Host test of the Mixer pages (B57/B66) and their bench measure (B98): include/RF_Travel.h on the Mac over a fake screen
and a fake flight controller on the fake pipe. The read (42, then 174 four times), the four pages' fields, a hold (191 to
inputs 1, 2 and 4: the axis at its angle in raw 1000 = 12 deg, the other two at zero), the axis changed while held, the
suggested calibration (calibration x angle / gauge) put in the box and saved (43, 171 x 4 with both cyclic rates, 250,
read back), the hold's own end after five minutes (also off the page, silently), OK and < Previous releasing first, a
release that fails, a hold that fails half way, and the refusals (armed, offline, nothing typed).
   python3 dev/test_travel/test_travel.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDR = os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Travel.h')
prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cmath>
#include <string>
#include <map>
#include <vector>
#define FLASHMEM
#ifndef B211_HOST_STUBS   // (B211, Nextion.h / Utilities.h: NO ANSWER IS NOT A NUMBER; A PAGE'S FIELDS ARE TAKEN WHOLE - dev/test_noanswer and dev/test_wholepage are their tests)
#define B211_HOST_STUBS
#include <cstring>
#include <cstdint>
#include <cstddef>
uint32_t BoxesLost = 0;
uint32_t BoxesLostAtWork = 0; static bool WorkLostABox() { return BoxesLost != BoxesLostAtWork; }
static int boxesLostTold = 0; static void NoteBoxesLost() { ++boxesLostTold; }   // (LogFiles.h: the sound and the log's line)
template <size_t N> struct BoxesWhole { uint8_t *what; uint32_t lost; uint8_t was[N]; explicit BoxesWhole(void *p) : what((uint8_t *)p), lost(BoxesLost) { memcpy(was, what, N); } ~BoxesWhole() { if (BoxesLost != lost) memcpy(what, was, N); } };
#define KEEP_WHOLE(id, thing) BoxesWhole<sizeof(thing)> keepWhole_##id(&(thing))
bool QuestionClosedItself = false, QuestionOvertaken = false;
bool RfKeepTyped = false;   // (Nextion.h: what the pilot typed stays on the page)
static bool TextMustBeNumber(const char *, char *text) { for (const char *p = text; *p; ++p) if (!((*p >= '0' && *p <= '9') || *p == ' ' || *p == '+' || *p == '-' || *p == '.')) { text[0] = 0; ++BoxesLost; return false; } return true; }   // (Nextion.h: A NUMBER FIELD'S TEXT THAT IS NO NUMBER IS NO ANSWER)
#endif
#define PROGMEM
#define WHAHWHAHMSG 1
#define BEEPCOMPLETE 2
#define ROTORFLIGHTVIEW 47
#define TRAVELVIEW 62
#define TRAVEL2VIEW 63
#define TRAVEL3VIEW 66
#define TRAVEL4VIEW 76
static int CurrentView = 0, Bank = 1;
static bool offline = false, armed = false;
static char ModelName[20] = "Goblin";
static uint32_t now = 1000;
static uint32_t millis() { return now; }
static std::map<std::string, std::string> fields; static std::map<std::string, int> vals; static std::vector<std::string> cmds; static int boxes = 0; static std::string lastBox; static bool confirmAnswer = true; static int sounds = 0, rfStarts = 0, asked = 0;
static void SendCommand(char *c) { cmds.push_back(c); }
static void SendText(char *n, char *t) { fields[n] = t; }
static void SendValue(char *n, int v) { vals[n] = v; }
static void MsgBox(char *page, const char *msg) { ++boxes; lastBox = msg; }
static bool RfHomeNotRead = false; static bool rfMayFlyNow = false; static int quietSaid = 0;   // (B211, the sixteenth review: PipeHttp.h RfMayFly / RfSayQuietly / RfBoxOrQuiet stood in for - no box that waits while the model may fly)
static bool RfMayFly() { return rfMayFlyNow; } static void RfSayQuietly(const char *) { ++quietSaid; }
static void RfBoxOrQuiet(const char *page, const char *msg) { if (RfMayFly()) { RfSayQuietly(msg); return; } MsgBox((char *)page, (char *)msg); }
static bool GetConfirmation(char *page, char *prompt) { ++asked; lastBox = prompt; return confirmAnswer; }
static void PlaySound(int) { ++sounds; }
static void RotorFlightStart() { ++rfStarts; CurrentView = ROTORFLIGHTVIEW; }
static bool ModelSeemsArmed(char *why, size_t n) { if (!armed) return false; snprintf(why, n, "Model is armed"); return true; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static bool RfNeedsModel(char *, size_t) { return false; }
static bool BakOffline() { return offline; }
static std::string loseBox;   // (B211: this box has NO ANSWER - "" comes back, and it is counted, as Nextion.h GetText does it)
static void GetText(char *n, char *out, int len) { if (!loseBox.empty() && loseBox == n) { ++BoxesLost; if (len > 0) out[0] = 0; return; } snprintf(out, len, "%s", fields[n].c_str()); }
bool NextionTextMissed = false; static bool RfFieldsMissed(const char *) { if (!NextionTextMissed) return false; NextionTextMissed = false; return true; }   // (B152)
char NextionMissedBox[12] = {0}; bool NextionSettledOk = false, NextionMissedNoNumber = false; static void RfGatherStart() { NextionTextMissed = false; }   // (B187)
static long FieldNumber(const char *name, long lo, long hi) { char t[24] = ""; GetText((char *)name, t, sizeof(t) - 1); long v = strtol(t, nullptr, 10); return v < lo ? lo : v > hi ? hi : v; }
void EndTravelView(); void StartTravel3View(); void StartTravel4View(); void TravelWasEdited();
// ---- the pipe and a fake flight controller
static int PipeReqId = 0, PipeRepId = -1, PipeRepCode = 0; static char PipeRepBody[1600] = ""; static uint32_t PipeReqSentMs = 0;
static bool late = false;   // (no reply at all: the request is late)
bool PipeReplyReady(int id) { return !late && PipeRepId == id; }
bool PipeReplyLate() { return late; }
int PipeReplyBytes(uint8_t *out, int max) { int n = 0; const char *p = PipeRepBody; while (p[0] && p[1] && n < max) { char h[3] = {p[0], p[1], 0}; out[n++] = (uint8_t) strtol(h, nullptr, 16); p += 2; } return n; }
struct FcReq { int fn; std::string data; };
static std::vector<FcReq> fcLog;
static std::string hexOf(const uint8_t *d, int n) { char b[4]; std::string s; for (int i = 0; i < n; ++i) { snprintf(b, sizeof b, "%02X", d[i]); s += b; } return s; }
static uint8_t cfg[21]; static int16_t ins[5][3]; static int16_t ov[5]; static int failFn = 0, failAfter = 0;   // failFn: that function answers 503 once failAfter more of it have gone through
static void fcReply(int code, const std::string &body) { PipeRepCode = code; strncpy(PipeRepBody, body.c_str(), sizeof(PipeRepBody) - 1); PipeRepBody[sizeof(PipeRepBody) - 1] = 0; PipeRepId = PipeReqId; }
static int rdS16(const uint8_t *b, int o) { const int v = b[o] | (b[o + 1] << 8); return v > 32767 ? v - 65536 : v; }
static void wrS16(uint8_t *b, int o, long v) { const uint16_t u = (uint16_t)(v & 0xFFFF); b[o] = u & 0xFF; b[o + 1] = u >> 8; }
int MspAsk(uint8_t fn, const uint8_t *data, int len) {
    ++PipeReqId; PipeReqSentMs = now; fcLog.push_back({fn, hexOf(data, len)});
    if (fn == failFn) { if (failAfter > 0) --failAfter; else { failFn = 0; fcReply(503, "busy"); return PipeReqId; } }
    switch (fn) {
    case 42: fcReply(200, hexOf(cfg, 21)); return PipeReqId;
    case 43: memcpy(cfg, data, 21); fcReply(200, ""); return PipeReqId;
    case 174: { uint8_t b[6]; const int i = data[0]; wrS16(b, 0, ins[i][0]); wrS16(b, 2, ins[i][1]); wrS16(b, 4, ins[i][2]); fcReply(200, hexOf(b, 6)); return PipeReqId; }
    case 171: { const int i = data[0]; ins[i][0] = rdS16(data, 1); ins[i][1] = rdS16(data, 3); ins[i][2] = rdS16(data, 5); fcReply(200, ""); return PipeReqId; }
    case 191: { const int i = data[0]; if (i >= 1 && i <= 4) ov[i] = rdS16(data, 1); fcReply(200, ""); return PipeReqId; }
    case 250: fcReply(200, ""); return PipeReqId;
    }
    fcReply(404, "unknown"); return PipeReqId;
}
// B102: OK's "Save now?" - the real RfSaveFirst / RfSavedThenLeave (include/RF_SaveNow.h) over a fake question: Discard
// unless saveNowAnswer is 1; and the bank check (PipeHttp.h BankCheck) as without a pipe: the write goes
static bool RfLeaveAfterSave = false; static int RfLeaveView = -1; static void (*RfLeaveFn)() = nullptr;
static int saveNowAnswer = 0, saveNowAsked = 0;
static bool GetSaveOrDiscard(char *, char *prompt) { ++saveNowAsked; lastBox = prompt; return saveNowAnswer == 1; }
static inline void BankCheck(bool, int, void (*then)(), const char *) { then(); }
''' + open(os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_SaveNow.h')).read() + r'''
''' + open(HDR).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void run(int n = 40) { for (int i = 0; i < n; ++i) { TravelPoll(); now += 50; } }
static int writes(int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; }
static std::vector<std::string> dataOf(int fn) { std::vector<std::string> v; for (auto &r : fcLog) if (r.fn == fn) v.push_back(r.data); return v; }
static bool cmd(const char *c) { for (auto &x : cmds) if (x == c) return true; return false; }
static bool overridesOff() { return ov[1] == 2501 && ov[2] == 2501 && ov[4] == 2501; }
int main() {
    // ---- the fake flight controller: CCPM 120, variable-pitch tail, cyclic calibration 86.5 % both axes, collective 100 %
    memset(cfg, 0, sizeof cfg); cfg[5] = 2; wrS16(cfg, 9, 1500);
    for (int i = 1; i <= 4; ++i) { ins[i][0] = i == 4 ? 1000 : i == 3 ? 1000 : 865; ins[i][1] = -1000; ins[i][2] = 1000; ov[i] = 2501; }
    // ---- 1. the read, and the way to page 4
    StartTravelView(); CHECK(CurrentView == TRAVELVIEW && fcLog.size() == 1 && fcLog[0].fn == 42); run();
    CHECK(TravHave && writes(174) == 4 && fields["tn9"] == "0.0" && fields["i0"] == "Swashplate type: CCPM 120 deg");
    StartTravel2View(); CHECK(CurrentView == TRAVEL2VIEW && fields["tn0"] == "86.5");
    StartTravel3View(); CHECK(CurrentView == TRAVEL3VIEW && cmd("page Travel3View"));
    cmds.clear(); StartTravel4View();
    CHECK(CurrentView == TRAVEL4VIEW && cmd("page Travel4View") && fields["tn0"] == "Roll (aileron)" && fields["tn1"] == "8.0" && fields["tn2"] == "" && fields["tn3"] == "86.5" && fields["tn4"] == "tap");
    CHECK(fields["i0"] == "Motor off, blades clear: it moves the swash" && fields["b2"] == "Hold swash" && !BenchHeld);
    // ---- 2. a hold: 191 to inputs 1, 2 and 4 in turn - roll at 8 deg = 667 raw, the other two at zero
    fcLog.clear(); cmds.clear(); BenchHoldTapped();
    CHECK(TravStep == TRV_HOLD && fields["busy"] == "Holding the swash ..." && cmd("vis busy,1"));
    run();
    { auto d = dataOf(191); CHECK(d.size() == 3 && d[0] == "019B02" && d[1] == "020000" && d[2] == "040000"); }
    CHECK(BenchHeld && ov[1] == 667 && ov[2] == 0 && ov[4] == 0 && TravStep == TRV_IDLE && cmd("vis busy,0"));
    CHECK(fields["i0"] == "SWASH HELD: Roll at 8.0 deg (gyros bypassed)" && fields["b2"] == "Release" && BenchHeldUntil == now - 50 * 1 + 5UL * 60 * 1000 - 0 || BenchHeldUntil > now);
    // a second tap while the hold runs is ignored; OK and < Previous while busy are ignored too
    fcLog.clear(); BenchHoldTapped(); run(); CHECK(writes(191) == 3 && overridesOff());   // (that tap was Release: the hold let go)
    CHECK(!BenchHeld && fields["b2"] == "Hold swash" && fields["i0"] == "Motor off, blades clear: it moves the swash");
    // ---- 3. the angle typed and the axis changed while held: the swash goes over at once (pitch at -12 deg = -1000)
    fcLog.clear(); BenchHoldTapped(); run(); CHECK(BenchHeld && ov[1] == 667);
    // (B211, the tenth review) ... the axis tapped while held, and the angle's box has NO ANSWER: the hold on the other axis is refused - the swash
    // stays held on Roll, and Roll is what the page goes on showing (it showed "Pitch" while the swash was still held on Roll)
    loseBox = "tn1"; fcLog.clear(); { const uint32_t l0 = BoxesLost; BenchAxisTapped(); run(); CHECK(BoxesLost != l0); } loseBox = ""; BoxesLostAtWork = BoxesLost;
    CHECK(BenchHeld && BenchAxis == 1 && BenchHeldAxis == 1 && fields["tn0"] == "Roll (aileron)" && writes(191) == 0 && ov[1] == 667 && ov[2] == 0 && TravStep == TRV_IDLE);
    fields["tn1"] = "-12"; fcLog.clear(); BenchAxisTapped();
    CHECK(fields["tn0"] == "Pitch (elevator)" && TravStep == TRV_HOLD); run();
    { auto d = dataOf(191); CHECK(d.size() == 3 && d[0] == "010000" && d[1] == "0218FC" && d[2] == "040000"); }
    CHECK(BenchHeld && ov[1] == 0 && ov[2] == -1000 && fields["i0"] == "SWASH HELD: Pitch at -12.0 deg (gyros bypassed)" && fields["tn1"] == "-12.0");
    // ---- 4. the suggested calibration: 86.5 x 8 / 5.6 = 123.6, into the box, Save shown
    fields["tn1"] = "8"; fields["tn2"] = "5.6"; cmds.clear(); boxes = 0;
    BenchSuggestTapped();
    CHECK(boxes == 0 && fields["tn4"] == "123.6" && fields["tn3"] == "123.6" && Trav_Was_Edited && TravPage4Edited && cmd("vis b3,1"));
    // nothing typed: asked for, no change
    fields["tn2"] = ""; fields["tn4"] = "tap"; BenchSuggestTapped(); CHECK(boxes == 1 && lastBox.find("Type the angle") != std::string::npos && fields["tn4"] == "tap");
    // ---- 5. the save, still held: 43, 171 x 4 with BOTH cyclic rates 1236 (the signs kept), 250, 42 + 174 x 4 read back; the hold untouched
    fcLog.clear(); asked = 0; SaveTravel(); CHECK(asked == 1 && TravStep == TRV_WRITE_CFG); run();
    CHECK(writes(43) == 1 && writes(171) == 4 && writes(250) == 1 && writes(42) == 1 && writes(174) == 4 && writes(191) == 0);
    CHECK(ins[1][0] == 1236 && ins[2][0] == 1236 && ins[3][0] == 1000 && ins[4][0] == 1000 && ins[1][2] == 1000 && !Trav_Was_Edited && !TravPage4Edited);
    CHECK(fields["busy"] == "Saved, and read back the same." && BenchHeld && ov[2] == -1000 && fields["tn3"] == "123.6");
    run(100);   // (the 4-s message gone, the page shown again, still held)
    CHECK(fields["i0"] == "SWASH HELD: Pitch at -12.0 deg (gyros bypassed)" && fields["b2"] == "Release");
    // ---- 6. the hold's own end: five minutes
    fcLog.clear(); now += 5UL * 60 * 1000; run();
    { auto d = dataOf(191); CHECK(d.size() == 3 && d[0] == "01C509" && d[1] == "02C509" && d[2] == "04C509"); }
    CHECK(!BenchHeld && overridesOff() && fields["b2"] == "Hold swash" && TravStep == TRV_IDLE);
    // ---- 7. OK while held: released first, then the page left (nothing edited: no question)
    BenchHoldTapped(); run(); CHECK(BenchHeld);
    fcLog.clear(); rfStarts = 0; asked = 0; EndTravelView();
    CHECK(TravStep == TRV_RELEASE && CurrentView == TRAVEL4VIEW && rfStarts == 0); run();
    CHECK(writes(191) == 3 && overridesOff() && !BenchHeld && rfStarts == 1 && asked == 0 && CurrentView == ROTORFLIGHTVIEW);
    // ---- 8. < Previous while held: released first, then page 3
    StartTravelView(); run(); StartTravel4View(); BenchHoldTapped(); run(); CHECK(BenchHeld && CurrentView == TRAVEL4VIEW);
    fcLog.clear(); cmds.clear(); StartTravel3View(); CHECK(CurrentView == TRAVEL4VIEW && TravStep == TRV_RELEASE); run();
    CHECK(!BenchHeld && overridesOff() && CurrentView == TRAVEL3VIEW && cmd("page Travel3View"));
    // ---- 9. off the page when the five minutes end (left some other way): released all the same, no box, no words to the page
    StartTravel4View(); BenchHoldTapped(); run(); CHECK(BenchHeld);
    CurrentView = ROTORFLIGHTVIEW; fcLog.clear(); cmds.clear(); boxes = 0; now += 5UL * 60 * 1000; run();
    CHECK(writes(191) == 3 && overridesOff() && !BenchHeld && boxes == 0 && cmds.empty() && TravStep == TRV_IDLE);
    // ---- 10. a release that fails: said, and the page goes on (OK then leaves)
    CurrentView = TRAVEL4VIEW; BenchHoldTapped(); run(); CHECK(BenchHeld);
    failFn = 191; failAfter = 1; boxes = 0; fcLog.clear(); BenchHoldTapped(); run();
    CHECK(boxes == 1 && lastBox.find("Could not release the swash") != std::string::npos && lastBox.find("busy") != std::string::npos && !BenchHeld && TravStep == TRV_IDLE && fields["b2"] == "Hold swash");
    rfStarts = 0; EndTravelView(); CHECK(rfStarts == 1);
    // ... and one that gets no answer at all
    StartTravelView(); run(); StartTravel4View(); BenchHoldTapped(); run(); CHECK(BenchHeld);
    late = true; boxes = 0; BenchHoldTapped(); run(); late = false;
    CHECK(boxes == 1 && lastBox.find("Could not release the swash") != std::string::npos && !BenchHeld && TravStep == TRV_IDLE);
    // ... and WHILE THE MODEL MAY FLY: no box that waits (B211, the seventeenth review - the last box of these pages that did; the break-it round of
    // 16 Nov 2026, mut19 QR14, found that nothing held it). A line for the log; the page goes on as on the bench.
    StartTravelView(); run(); StartTravel4View(); BenchHoldTapped(); run(); CHECK(BenchHeld);
    failFn = 191; failAfter = 1; boxes = 0; quietSaid = 0; rfMayFlyNow = true; BenchHoldTapped(); run(); rfMayFlyNow = false; failFn = 0;
    CHECK(boxes == 0 && quietSaid == 1 && !BenchHeld && TravStep == TRV_IDLE && fields["b2"] == "Hold swash");
    // ---- 11. a hold that fails half way: said, Release offered (a part may be held)
    failFn = 191; failAfter = 1; boxes = 0; fcLog.clear(); BenchHoldTapped(); run();
    CHECK(boxes == 1 && lastBox.find("Could not hold the swash") != std::string::npos && BenchHeld && fields["b2"] == "Release" && TravStep == TRV_IDLE);
    fcLog.clear(); BenchHoldTapped(); run(); CHECK(!BenchHeld && writes(191) == 3 && overridesOff());
    // ---- 12. the refusals: armed, and offline (the backup cannot move the swash); nothing sent
    armed = true; boxes = 0; fcLog.clear(); BenchHoldTapped(); CHECK(boxes == 1 && lastBox == "Model is armed" && fcLog.empty() && !BenchHeld); armed = false;
    offline = true; boxes = 0; BenchHoldTapped(); CHECK(boxes == 1 && lastBox.find("needs the model") != std::string::npos && fcLog.empty() && !BenchHeld); offline = false;
    // ---- 13. the calibration edited on page 4, then back to page 2: page 2 shows it (gathered on the way, both axes)
    fields["tn3"] = "90"; TravelWasEdited(); CHECK(TravPage4Edited);
    StartTravel3View(); CHECK(CurrentView == TRAVEL3VIEW && TravInWant[1][0] == 900 && TravInWant[2][0] == 900);
    StartTravel2View(); CHECK(CurrentView == TRAVEL2VIEW && fields["tn0"] == "90.0");
    // back on page 4 the box shows the edit (the flag stays until a save or a read, as page 2's); a page 4 only looked at keeps it
    StartTravel3View(); StartTravel4View(); CHECK(fields["tn3"] == "90.0" && TravPage4Edited); StartTravel3View(); CHECK(TravInWant[1][0] == 900 && TravInWant[2][0] == 900);
    fcLog.clear(); StartTravelView(); run(); CHECK(!TravPage4Edited && !Trav_Was_Edited && TravInWant[1][0] == 1236);   // (a fresh read: the FC's 123.6 again, the unsaved 90 gone)
    // ---- 14. B211 (the ninth review): A PAGE'S FIELDS ARE TAKEN WHOLE, OR NOT AT ALL. Each of the four pages' gathers, every field typed
    //      anew and its LAST field with no answer: nothing of what the gather writes into is changed - the settings to send, the
    //      inputs' rates and limits (also the signs the direction switches give them), the bench's two numbers. And with every box
    //      answered the same gather takes them.
    {
        uint8_t cfg0[sizeof TravCfgWant]; int16_t in0[5][3]; long deg0, gauge0;
        auto keep = [&] { memcpy(cfg0, TravCfgWant, sizeof cfg0); memcpy(in0, TravInWant, sizeof in0); deg0 = BenchDegTenths; gauge0 = BenchGaugeTenths; };
        auto same = [&] { return !memcmp(cfg0, TravCfgWant, sizeof cfg0) && !memcmp(in0, TravInWant, sizeof in0) && deg0 == BenchDegTenths && gauge0 == BenchGaugeTenths; };
        auto cfgSame = [&] { return !memcmp(cfg0, TravCfgWant, sizeof cfg0); }; auto inSame = [&] { return !memcmp(in0, TravInWant, sizeof in0); };
        // page 1: the three trims, and the direction switches
        fields["tn9"] = "1.5"; fields["tn10"] = "-2.5"; fields["tn11"] = "3.5"; TravRevAil = !TravRevAil; keep();
        loseBox = "tn11"; TravGatherPage1(); CHECK(same() && BoxesLost != BoxesLostAtWork);
        loseBox = ""; TravGatherPage1(); CHECK(!cfgSame() && !inSame());
        // page 2: gains, geometry, limits, phase, tilts (its last field: tn8)
        for (const char *f : { "tn0", "tn1" }) fields[f] = "77.0";
        fields["tn2"] = "4.0"; fields["tn3"] = "11.0"; fields["tn4"] = "12.0"; fields["tn5"] = "13.0"; fields["tn6"] = "14.0"; fields["tn7"] = "5"; fields["tn8"] = "6"; TravPage2Edited = true; keep();
        loseBox = "tn8"; TravGatherPage2(); CHECK(same());
        loseBox = ""; TravGatherPage2(); CHECK(!cfgSame() && !inSame());
        // page 3: the tail (its last field: tn2)
        fields["tn1"] = "2.0"; fields["tn3"] = "21.0"; fields["tn4"] = "22.0"; fields["tn2"] = "55.0"; keep();
        loseBox = "tn2"; TravGatherPage3(); CHECK(same());
        loseBox = ""; TravGatherPage3(); CHECK(!cfgSame() || !inSame()); CHECK(!inSame());
        // page 4: the bench's angle and reading, and the one calibration (its last field: tn3)
        fields["tn1"] = "6.0"; fields["tn2"] = "7.5"; fields["tn3"] = "66.0"; TravPage4Edited = true; keep();
        loseBox = "tn3"; TravGatherPage4(); CHECK(same());
        loseBox = "tn2"; TravGatherPage4(); CHECK(same());                           // (... and with the reading lost, the angle read before it goes back too)
        loseBox = ""; TravGatherPage4(); CHECK(!inSame() && BenchDegTenths == 60 && BenchGaugeTenths == 75);
        BoxesLostAtWork = BoxesLost;
    }
    // (B211, the eleventh review, reviewer B's low 8) THE PAGE'S OWN WORK FROM THE MAIN LOOP COUNTS ITS LOST BOXES FROM THERE. OK (or < Previous) while
    // the swash is held lets it go first - and the rest of OK's work runs from the main loop when it has: no button's work. It asked "was a box of
    // THIS BUTTON'S work unanswered?" against the count of an EARLIER button's work:
    //  (a) a box that an earlier button had lost (long since told) stopped the page being left - with nothing said;
    {
        StartTravelView(); run(); StartTravel4View(); run(); BenchHoldTapped(); run(); CHECK(BenchHeld && CurrentView == TRAVEL4VIEW);
        ++BoxesLost;                                       // (an earlier button's work lost a box: BoxesLost stands one above "as that work began" from here)
        CHECK(WorkLostABox());
        TravelWasEdited(); saveNowAnswer = 0; fcLog.clear(); rfStarts = 0; boxesLostTold = 0;
        EndTravelView(); CHECK(TravStep == TRV_RELEASE); run();
        CHECK(!BenchHeld && rfStarts == 1 && CurrentView == ROTORFLIGHTVIEW && boxesLostTold == 0);   // the swash let go, "Save now?" answered Discard: the page is left
    }
    //  (b) ... and a box lost in THAT work (the gather the main loop runs) was told by nothing: it is said now, and the page stays
    {
        StartTravelView(); run(); StartTravel4View(); run(); BenchHoldTapped(); run(); CHECK(BenchHeld && CurrentView == TRAVEL4VIEW);
        BoxesLostAtWork = BoxesLost; TravelWasEdited(); saveNowAnswer = 0; rfStarts = 0; boxesLostTold = 0;
        EndTravelView(); CHECK(TravStep == TRV_RELEASE); loseBox = "tn1"; run(); loseBox = "";
        CHECK(!BenchHeld && rfStarts == 0 && CurrentView == TRAVEL4VIEW && boxesLostTold == 1);
        BoxesLostAtWork = BoxesLost; EndTravelView(); run(); CHECK(rfStarts == 1 && CurrentView == ROTORFLIGHTVIEW);   // OK again: every box answers, and the page is left
    }
    // B211 (the twelfth review, reviewer B's experiment 3; released code had it): THE BENCH MEASURE - WHAT IS TYPED WHILE THE SWASH IS HELD STAYS AT THE
    // RELEASE. The hold is there to read a pitch gauge and type its reading; Release (by the button, by itself after five minutes) drew page 4 from what
    // is in hand, and the reading - and a calibration typed - were wiped; the suggestion row then worked from the OLD numbers
    {
        memset(cfg, 0, sizeof cfg); cfg[5] = 2; wrS16(cfg, 9, 1500);
        for (int i = 1; i <= 4; ++i) { ins[i][0] = i == 4 ? 1000 : i == 3 ? 1000 : 865; ins[i][1] = -1000; ins[i][2] = 1000; ov[i] = 2501; }
        BenchGaugeTenths = 0; BenchSuggestTenths = 0; BenchDegTenths = 80; BenchAxis = 1; BenchHeld = false; TravHave = false; Trav_Was_Edited = false;
        StartTravelView(); run(); StartTravel2View(); StartTravel3View(); StartTravel4View(); run();
        CHECK(CurrentView == TRAVEL4VIEW && fields["tn1"] == "8.0" && fields["tn2"] == "" && fields["tn3"] == "86.5");
        // 1. held (roll at 8 degrees); the gauge reads 5.6 - typed; Release; then the suggestion row
        BenchHoldTapped(); run(); CHECK(BenchHeld);
        fields["tn2"] = "5.6"; BenchWasEdited();
        BenchHoldTapped(); run(); CHECK(!BenchHeld);
        CHECK(fields["tn2"] == "5.6");                               // what he typed is still there (it was: empty again)
        CHECK(fields["b2"] == "Hold swash" && fields["i0"].find("HELD") == std::string::npos);   // ... and the told row and the button say the swash is free
        boxes = 0; BenchSuggestTapped(); CHECK(boxes == 0 && fields["tn4"] == "123.6");
        // 2. a second round with that reading in hand: held again, 7.0 read and typed, and a calibration of his own, 95.0; Release
        BenchHoldTapped(); run(); CHECK(BenchHeld);
        fields["tn2"] = "7.0"; BenchWasEdited(); fields["tn3"] = "95.0"; TravelWasEdited();
        BenchHoldTapped(); run(); CHECK(!BenchHeld);
        CHECK(fields["tn2"] == "7.0" && fields["tn3"] == "95.0");    // (it was: 5.6 and 123.6 again)
        BenchSuggestTapped(); CHECK(fields["tn4"] != "123.6");
        // 3. the hold lets go BY ITSELF after five minutes, a reading typed and not yet taken
        StartTravelView(); run(); StartTravel4View(); run(); BenchHoldTapped(); run(); CHECK(BenchHeld);
        fields["tn2"] = "6.5"; BenchWasEdited();
        now += 5UL * 60 * 1000; run(); CHECK(!BenchHeld);
        CHECK(fields["tn2"] == "6.5" && fields["b2"] == "Hold swash");
    }
    // (the break-it round: "a typed travel number is written over while typed fields are kept" passed every scene - the flows above draw page 4 alone)
    // THE DRAW'S OWN PROMISE, page by page: while what was typed is to stay (RfKeepTyped), a page's draw leaves EVERY field its keypad opens (the page
    // files' own lists) - and without it the same draw writes them from what is in hand
    {
        StartTravelView(); run();
        struct { void (*start)(); std::vector<const char *> typed; } pages[] = {
            { nullptr, { "tn9", "tn10", "tn11" } },
            { StartTravel2View, { "tn0", "tn1", "tn2", "tn3", "tn4", "tn5", "tn6", "tn7", "tn8" } },
            { StartTravel3View, { "tn1", "tn2", "tn3", "tn4", "tn5" } },
            { StartTravel4View, { "tn1", "tn2", "tn3" } } };
        for (auto &pg : pages)
        {
            if (pg.start) { pg.start(); run(); }
            for (const char *f : pg.typed) fields[f] = "7.7";
            RfKeepTyped = true; TravShow(); RfKeepTyped = false;
            bool kept = true; for (const char *f : pg.typed) kept = kept && fields[f] == "7.7";
            CHECK(kept);                                                             // every typed field as he left it
            TravShow();
            int written = 0; for (const char *f : pg.typed) written += fields[f] != "7.7";
            CHECK(written >= (int) pg.typed.size() - 1);                             // (the scene is the one meant: this draw DOES write them - all but one that may hold 7.7 or stay empty)
        }
    }
    // B10 (the sixteenth review): NOTHING IN HAND - nothing is an edit (OK asked "Save now?" for it, the save returned at once), and a Save refused
    // for it does not leave "close when saved" standing for a later Save
    { const bool h = TravHave, e = Trav_Was_Edited; TravHave = false; Trav_Was_Edited = false; TravelWasEdited(); CHECK(!Trav_Was_Edited);
      RfLeaveAfterSave = true; SaveTravel(); CHECK(!RfLeaveAfterSave);
      TravHave = true; TravelWasEdited(); CHECK(Trav_Was_Edited); TravHave = h; Trav_Was_Edited = e; }
    // ---- (the sixteenth review, reviewer B's runs E7 and E8, taken into the suite)
    {
        auto e7run = [&](int n) { for (int i = 0; i < n; ++i) { TravelPoll(); now += 50; } };
        auto e7writes = [&](int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; };
        auto e7fc = [&]() { memset(cfg, 0, sizeof cfg); cfg[5] = 2; wrS16(cfg, 9, 1500); ins[1][0] = 865; ins[1][1] = -1000; ins[1][2] = 1000; ins[2][0] = 865; ins[2][1] = -1000; ins[2][2] = 1000; ins[3][0] = 1000; ins[3][1] = -417; ins[3][2] = 417; ins[4][0] = 1000; ins[4][1] = -1000; ins[4][2] = 1000; };
        // E7. A SAVE THAT FAILS AFTER A PART OF IT WAS WRITTEN (released code said "Not written (an input)" - with the mixer block and the first input in the
        //     flight controller's memory, not stored): THE BOX SAYS WHAT STANDS THERE, the page keeps its edits, and Save again writes the whole
        e7fc(); failFn = 0; Trav_Was_Edited = false; RfLeaveAfterSave = false; CurrentView = ROTORFLIGHTVIEW; StartTravelView(); e7run(40);
        TravelAilTapped(); TravelEleTapped(); fields["tn9"] = "1.5"; TravelWasEdited();      // the aileron AND the elevator direction turned round, a swash trim typed
        failFn = 171; failAfter = 1; boxes = 0; fcLog.clear(); confirmAnswer = true; SaveTravel(); e7run(40);   // Save: 43, 171 for input 1 - the 171 for input 2 is refused
        CHECK(boxes == 1 && lastBox.find("PART WRITTEN, NOT STORED (an input failed) - try again, or switch the model off and on") == 0);
        CHECK(e7writes(43) == 1 && e7writes(250) == 0 && ins[1][0] == -865 && ins[2][0] == 865 && Trav_Was_Edited && CurrentView == TRAVELVIEW);   // (part IS written - and now it is said)
        failFn = 0; boxes = 0; fcLog.clear(); SaveTravel(); e7run(60);                          // "try again": the whole save, stored
        CHECK(boxes == 0 && e7writes(250) == 1 && ins[1][0] == -865 && ins[2][0] == -865 && !Trav_Was_Edited);
        // ... and the FIRST write refused is still "Not written": nothing of the save stands in the flight controller
        e7fc(); Trav_Was_Edited = false; CurrentView = ROTORFLIGHTVIEW; StartTravelView(); e7run(40); TravelAilTapped();
        failFn = 43; failAfter = 0; boxes = 0; fcLog.clear(); SaveTravel(); e7run(40);
        CHECK(boxes == 1 && lastBox.find("Not written (travel extents)") == 0 && ins[1][0] == 865);
        failFn = 0;
        // E8. A DIRECTION TAPPED WHILE A SAVE RUNS, "Next >" before it ends, the save ending on page 2 (no switch there): at a save's end the directions in
        //     hand are the block's, on whichever page - a calibration typed on page 2 and saved does not send the aileron reversed
        e7fc(); CurrentView = ROTORFLIGHTVIEW; Trav_Was_Edited = false; StartTravelView(); e7run(40);
        fields["tn9"] = "2.0"; TravelWasEdited(); fcLog.clear(); SaveTravel(); TravelPoll();
        TravelAilTapped(); StartTravel2View(); e7run(40);
        fields["tn1"] = "95.0"; TravelWasEdited(); fcLog.clear(); SaveTravel(); e7run(40);
        CHECK(ins[1][0] > 0);                                                                     // (with that line out: page 2's save wrote the aileron REVERSED)
        EndTravel2View(); CHECK(vals["tn6"] == 0);
    }
    printf("test_travel: %d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-const-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit(1)
if r.stderr.strip(): print(r.stderr[:3000])
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
