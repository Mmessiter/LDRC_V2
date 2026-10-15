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
static bool GetConfirmation(char *page, char *prompt) { ++asked; lastBox = prompt; return confirmAnswer; }
static void PlaySound(int) { ++sounds; }
static void RotorFlightStart() { ++rfStarts; CurrentView = ROTORFLIGHTVIEW; }
static bool ModelSeemsArmed(char *why, size_t n) { if (!armed) return false; snprintf(why, n, "Model is armed"); return true; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static bool RfNeedsModel(char *, size_t) { return false; }
static bool BakOffline() { return offline; }
static void GetText(char *n, char *out, int len) { snprintf(out, len, "%s", fields[n].c_str()); }
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
    CHECK(fields["i0"] == "HELD: roll at 8.0 deg (gyros bypassed)" && fields["b2"] == "Release" && BenchHeldUntil == now - 50 * 1 + 5UL * 60 * 1000 - 0 || BenchHeldUntil > now);
    // a second tap while the hold runs is ignored; OK and < Previous while busy are ignored too
    fcLog.clear(); BenchHoldTapped(); run(); CHECK(writes(191) == 3 && overridesOff());   // (that tap was Release: the hold let go)
    CHECK(!BenchHeld && fields["b2"] == "Hold swash" && fields["i0"] == "Motor off, blades clear: it moves the swash");
    // ---- 3. the angle typed and the axis changed while held: the swash goes over at once (pitch at -12 deg = -1000)
    fcLog.clear(); BenchHoldTapped(); run(); CHECK(BenchHeld && ov[1] == 667);
    fields["tn1"] = "-12"; fcLog.clear(); BenchAxisTapped();
    CHECK(fields["tn0"] == "Pitch (elevator)" && TravStep == TRV_HOLD); run();
    { auto d = dataOf(191); CHECK(d.size() == 3 && d[0] == "010000" && d[1] == "0218FC" && d[2] == "040000"); }
    CHECK(BenchHeld && ov[1] == 0 && ov[2] == -1000 && fields["i0"] == "HELD: pitch at -12.0 deg (gyros bypassed)" && fields["tn1"] == "-12.0");
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
    CHECK(fields["i0"] == "HELD: pitch at -12.0 deg (gyros bypassed)" && fields["b2"] == "Release");
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
    printf("test_travel: %d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-const-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit(1)
if r.stderr.strip(): print(r.stderr[:3000])
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
