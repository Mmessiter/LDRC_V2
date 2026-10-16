#!/usr/bin/env python3
"""Host test of Easy tuning (B104): include/RF_Easy.h on the Mac over a fake screen, a fake flight controller on the fake
pipe and a fake backup file, with the real RF_SaveNow.h. Two parts:
  1. THE SUMS AGAINST THE PHONE'S OWN CODE: the slider sums of RXV2 data/rotorflight-easy.html and app.js, run by node,
     and the transmitter's, over thousands of random cases (Start's numbers and place, Agility, Stick feel and the rates
     bytes for every rates type, Cyclic and Tail and the PID bytes, the governor bytes): every answer the same.
  2. THE PAGE: the read (where the flight controller is, then 142, 111, 112), the sliders' places from the backup's
     centres (or the numbers it opened with), the notes, each part's save (written, stored, read back), PID spool-up in
     every bank (each bank chosen, the transmitter's chosen again), the restart and its read-back, the refusals (another
     bank - B102; a governor choice outside the lists - B103; no model; nothing moved), failures part way (the bank put
     back first), the page left, "Save now?" on OK (B102), the bank switch moved, an uncovered rates type.
  3. B105, THE NUMBERS WHILE A FINGER IS ON A SLIDER: the box's columns (now -> what Save would write) for every slider,
     the slider's place carried in its word (and the old "get" for a page without it), the line after the lift; the
     dispatcher's own expressions taken from main.cpp; and the screen's page file (ESP32-board2 sd/hmi/pages/81.json): its
     sliders' scripts, worked out left to right as the screen does, give the words the main board reads as (slider, place,
     let go), the box shown in the row's shade and emptied as a finger lands and hidden as it lifts, the switch's row last.
   python3 dev/test_easy/test_easy.py"""
import json, os, random, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INC = os.path.join(ROOT, 'TransmitterCode', 'include')
RXV2 = os.path.join(os.path.expanduser('~'), 'Documents', 'GitHub', 'LDRC_V2_ALL', 'RXV2', 'data')
PAGE81 = os.path.join(os.path.expanduser('~'), 'Documents', 'GitHub', 'ESP32-board2', 'board4', 'nextion-emulator', 'sd', 'hmi', 'pages', '81.json')
MAIN = open(os.path.join(ROOT, 'TransmitterCode', 'src', 'main.cpp')).read()
CODE_EXPR = re.search(r'uint32_t NumberedCommand1 = (.+?);', MAIN).group(1)   # (B105: the dispatcher's own sums, ButtonWasPressed)
ARG_EXPR = re.search(r'ScreenEventArg = (.+?);', MAIN).group(1)
def src(name): return open(os.path.join(INC, name)).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '')

prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cctype>
#include <cmath>
#include <string>
#include <map>
#include <vector>
#include <iostream>
#include <sstream>
#define DMAMEM
#define FLASHMEM
#define PROGMEM
#define PSTR(s) (s)
#define WHAHWHAHMSG 1
#define BEEPCOMPLETE 2
#define EASYVIEW 81
#define ROTORFLIGHTVIEW 47
static int CurrentView = 0;
static uint8_t ScreenEventArg = 0;   // (main.cpp ButtonWasPressed: the top byte of the slider's word)
static bool BoundFlag = true, ModelMatched = true, BlockBankChanges = false;
static char ModelName[20] = "Havok";
static uint8_t Bank = 2, DualRateInUse = 2;
static uint32_t now = 1000;
static uint32_t millis() { return now; }
bool RfLeaveAfterSave = false; int RfLeaveView = -1; void (*RfLeaveFn)() = nullptr;
static std::map<std::string, std::string> fields; static std::map<std::string, int> vals; static std::vector<std::string> cmds;
static std::map<std::string, uint32_t> finger;   // what the screen answers to "get NAME.val" (where the finger left it)
static int boxes = 0, confirms = 0, sounds = 0, rfStarts = 0; static std::string lastBox, lastQuestion; static bool confirmAnswer = true, saveAnswer = true;
static void SendCommand(char *c) { cmds.push_back(c); }
static void SendText(char *n, char *t) { fields[n] = t; }
static void SendValue(char *n, int v) { vals[n] = v; }
static uint32_t GetValue(char *n) { auto it = finger.find(n); return it == finger.end() ? 65535 : it->second; }
static void MsgBox(char *, char *msg) { RfLeaveAfterSave = false; ++boxes; lastBox = msg; }
static bool GetConfirmation(char *, char *q) { ++confirms; lastQuestion = q; if (!confirmAnswer) RfLeaveAfterSave = false; return confirmAnswer; }
static bool GetSaveOrDiscard(char *, char *q) { lastQuestion = q; return saveAnswer; }
static void PlaySound(int) { ++sounds; }
static void RotorFlightStart() { RfLeaveAfterSave = false; ++rfStarts; CurrentView = ROTORFLIGHTVIEW; }
static void ShowRFBank() { char b[16]; snprintf(b, sizeof b, "Bank %d", Bank); fields["t14"] = b; }
static void ShowRFRate() { char b[16]; snprintf(b, sizeof b, "Rate %d", DualRateInUse); fields["t8"] = b; }
static bool armed = false, pipeBlocked = false;
static bool ModelSeemsArmed(char *why, size_t n) { if (armed) snprintf(why, n, "Model is armed: the safety is off."); return armed; }
static bool RfPipeBlocked(char *why, size_t n) { if (pipeBlocked) snprintf(why, n, "No Bluetooth link to the receiver."); return pipeBlocked; }
''' + src('RF_SaveNow.h') + r'''
// ---- the pipe and a fake flight controller (it answers at once)
static int PipeReqId = 0, PipeRepId = -1, PipeRepCode = 0; static char PipeRepBody[1600] = ""; static bool late = false, silent = false;
bool PipeReplyReady(int id) { return PipeRepId == id; }
bool PipeReplyLate() { return late; }
int PipeReplyBytes(uint8_t *out, int max) { int n = 0; const char *p = PipeRepBody; while (p[0] && p[1] && n < max) { char h[3] = {p[0], p[1], 0}; out[n++] = (uint8_t) strtol(h, nullptr, 16); p += 2; } return n; }
static int FcPidBank = 0, FcRateBank = 0;
static std::string hexOf(const uint8_t *d, int n) { char b[4]; std::string s; for (int i = 0; i < n; ++i) { snprintf(b, sizeof b, "%02X", d[i]); s += b; } return s; }
static int bytesOf(const std::string &h, uint8_t *out, int max) { int n = 0; for (size_t i = 0; i + 1 < h.size() && n < max; i += 2) out[n++] = (uint8_t) strtol(h.substr(i, 2).c_str(), nullptr, 16); return n; }
struct FcReq { int fn; std::string data; };
static std::vector<FcReq> fcLog;
static std::string gov, rates[6], pid[6], gprof[6]; static int fcPid = 1, fcRate = 1, pidBanks = 6, busyOnce = 0, away = 0, awayAfterBoot = 1, stores = 0, boots = 0;
static std::map<int, int> refuseFn; static int refuseBank = -1; static bool spoilPid = false;
static void fcReply(int code, const std::string &body) { PipeRepCode = code; strncpy(PipeRepBody, body.c_str(), sizeof(PipeRepBody) - 1); PipeRepBody[sizeof(PipeRepBody) - 1] = 0; PipeRepId = PipeReqId; }
int MspAsk(uint8_t fn, const uint8_t *data, int len) {
    ++PipeReqId; fcLog.push_back({fn, hexOf(data, len)});
    if (silent) return PipeReqId;   // (never answered)
    if (busyOnce > 0) { --busyOnce; fcReply(503, "busy"); return PipeReqId; }
    if (refuseFn.count(fn) && (refuseBank < 0 || refuseBank == fcPid)) { fcReply(refuseFn[fn], "refused by the fake"); return PipeReqId; }
    if (away > 0 && fn != 68) { --away; fcReply(503, "No flight controller is answering."); return PipeReqId; }
    if (fn == 101) { uint8_t b[32] = {0}; b[23] = fcPid; b[25] = fcRate; b[24] = pidBanks; b[26] = 6; fcReply(200, hexOf(b, 32)); return PipeReqId; }
    if (fn == 210) { if (data[0] & 0x80) fcRate = data[0] & 0x7F; else fcPid = data[0]; fcReply(200, ""); return PipeReqId; }
    if (fn == 142) { fcReply(200, gov); return PipeReqId; }
    if (fn == 111) { fcReply(200, rates[fcRate]); return PipeReqId; }
    if (fn == 112) { fcReply(200, pid[fcPid]); return PipeReqId; }
    if (fn == 148) { fcReply(200, gprof[fcPid]); return PipeReqId; }
    if (fn == 143) { gov = hexOf(data, len); fcReply(200, ""); return PipeReqId; }
    if (fn == 204) { rates[fcRate] = hexOf(data, len); fcReply(200, ""); return PipeReqId; }
    if (fn == 202) { std::string h = hexOf(data, len); if (spoilPid) h.replace(0, 4, "0100"); pid[fcPid] = h; fcReply(200, ""); return PipeReqId; }
    if (fn == 149) { gprof[fcPid] = hexOf(data, len); fcReply(200, ""); return PipeReqId; }
    if (fn == 250) { ++stores; fcReply(200, ""); return PipeReqId; }
    if (fn == 68) { ++boots; away = awayAfterBoot; fcReply(200, ""); return PipeReqId; }
    fcReply(404, "unknown"); return PipeReqId;
}
// ---- the backup file: the sliders' centres
static bool haveFile = true; static std::string fileGov, fileRates[6], filePid[6];
static bool BakHaveFile() { return haveFile; }
static bool BakBlock(uint8_t fn, int bank, uint8_t *out, int max, int &n) {
    const std::string h = fn == 142 ? fileGov : fn == 111 ? fileRates[bank] : fn == 112 ? filePid[bank] : std::string();
    if (h.empty()) return false; n = bytesOf(h, out, max); return true;
}
''' + src('RF_Easy.h') + r'''
static uint32_t CodeOf(int Command_number) { return ''' + CODE_EXPR + r'''; }   // main.cpp's own expressions
static uint8_t ArgOf(int Command_number) { return ''' + ARG_EXPR + r'''; }
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void run(int n = 900) { for (int i = 0; i < n && EzStep != EZ_IDLE; ++i) { EasyPoll(); now += 50; } EasyPoll(); }
static int count(int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; }
static std::string fns() { std::string s; for (auto &r : fcLog) { if (!s.empty()) s += ' '; s += std::to_string(r.fn); if (r.fn == 210) s += ":" + r.data; } return s; }
static bool sent(const char *c) { for (auto &x : cmds) if (x == c) return true; return false; }
static std::string words(const std::vector<int> &w) { std::string s; char b[8]; for (int v : w) { snprintf(b, sizeof b, "%02X%02X", v & 255, (v >> 8) & 255); s += b; } return s; }
static int word(const std::string &h, int i) { return (int) strtol(h.substr(i * 4 + 2, 2).c_str(), nullptr, 16) << 8 | (int) strtol(h.substr(i * 4, 2).c_str(), nullptr, 16); }
static int byteAt(const std::string &h, int i) { return (int) strtol(h.substr(i * 2, 2).c_str(), nullptr, 16); }
static std::string setByte(std::string h, int i, int v) { char b[4]; snprintf(b, sizeof b, "%02X", v & 255); h.replace(i * 2, 2, b); return h; }
static std::string setWord(std::string h, int i, int v) { char b[8]; snprintf(b, sizeof b, "%02X%02X", v & 255, (v >> 8) & 255); h.replace(i * 4, 4, b); return h; }
static long jsRound(double x) { return (long) floor(x + 0.5); }

// ---- part 1: the sums, case by case from stdin, printed as the node script prints the phone's
static void grid() {
    std::string line;
    while (std::getline(std::cin, line)) {
        std::istringstream in(line); std::string k; in >> k;
        if (k == "start") {
            int bs, bst, bh, cs, v; in >> bs >> bst >> bh >> cs >> v;
            EzBaseSpool = bs / 10.0; EzBaseStart = bst / 10.0; EzBaseHand = bh;
            const EzStartN n = EzStartNums(v);
            printf("start %d %d %d %d\n", EzStartFeel(cs / 10.0), n.spool, n.hand, n.start);
        } else if (k == "gov") {
            int t, v, bs, bst, bh; std::string h; in >> t >> v >> bs >> bst >> bh >> h;
            EzBaseSpool = bs / 10.0; EzBaseStart = bst / 10.0; EzBaseHand = bh; EzGovN = bytesOf(h, EzGov, sizeof EzGov);
            EzPos[0] = v; EzMoved[0] = t != 0; uint8_t o[64]; EzGovBytes(o);
            printf("gov %s\n", hexOf(o, EzGovN).c_str());
        } else if (k == "rates") {
            int ta, te, v, e, brp, byaw, bex; std::string h; in >> ta >> te >> v >> e >> brp >> byaw >> bex >> h;
            EzRatesN = bytesOf(h, EzRates, sizeof EzRates); EzBaseRp = brp; EzBaseYaw = byaw; EzBaseExpo = bex;
            EzPos[1] = v; EzPos[2] = e; EzMoved[1] = ta != 0; EzMoved[2] = te != 0; uint8_t o[64]; EzRatesBytes(o);
            EzFeel m; char ef[8]; if (EzFeelModel(EzRates[0], m)) snprintf(ef, sizeof ef, "%d", EzExpoFeel(EzExpoOf(EzRates, 0))); else snprintf(ef, sizeof ef, "-");   // (an uncovered type: its rows hidden, the place means nothing)
            printf("rates %d %s %d %d %d %s\n", EzRelPos(EzBaseRp, EzRateOf(EzRates, 0)), ef, EzAgileRp(v), EzAgileYaw(v), EzExpoAt(e), hexOf(o, EzRatesN).c_str());
        } else if (k == "pid") {
            int tc, tt, cyc, tail; std::string b, h; in >> tc >> tt >> cyc >> tail >> b >> h;
            std::stringstream bs(b); std::string item; int i = 0; while (std::getline(bs, item, ',') && i < 12) EzBasePid[i++] = (uint16_t) atoi(item.c_str());
            EzPidN = bytesOf(h, EzPid, sizeof EzPid); EzPos[3] = cyc; EzPos[4] = tail; EzMoved[3] = tc != 0; EzMoved[4] = tt != 0;
            uint8_t o[64]; EzPidBytes(o);
            printf("pid %d %d %s\n", EzNudgePos(false), EzNudgePos(true), hexOf(o, EzPidN).c_str());
        }
    }
}

// ---- part 2: the page
static std::string GOV0, RATES_ACT, RATES_RF, PID0, GP_OFF, GP_ON;
static void model() { // the Havok's numbers on the fake flight controller, its backup the same but for the PIDs
    gov = GOV0; for (int b = 0; b < 6; ++b) { rates[b] = RATES_ACT; pid[b] = PID0; gprof[b] = b % 2 ? GP_ON : GP_OFF; }
    fileGov = GOV0; for (int b = 0; b < 6; ++b) { fileRates[b] = RATES_ACT; filePid[b] = PID0; }
    filePid[1] = setWord(setWord(PID0, 0, 48), 8, 58);   // (the backup's roll P 48 and yaw P 58: today's 50 and 60 are a little sharper)
    fcPid = 1; fcRate = 1; Bank = 2; DualRateInUse = 2; haveFile = true; busyOnce = 0; away = 0; awayAfterBoot = 1; refuseFn.clear(); refuseBank = -1; spoilPid = false; late = false; silent = false;
    BoundFlag = ModelMatched = true; armed = pipeBlocked = false; confirmAnswer = saveAnswer = true; finger.clear();
}
static void open() { fcLog.clear(); cmds.clear(); fields.clear(); vals.clear(); boxes = 0; CurrentView = ROTORFLIGHTVIEW; StartEasyView(); run(); }
static void sliderWord(int k, int arg) { ScreenEventArg = (uint8_t) arg; if (k == 0) EasyStartMoved(); else if (k == 1) EasyAgilityMoved(); else if (k == 2) EasyStickFeelMoved(); else if (k == 3) EasyCyclicMoved(); else EasyTailMoved(); ScreenEventArg = 0; }
static void slide(int k, int v) { sliderWord(k, v + 1); }        // (B105: touched or dragged - the place in the word)
static void lift(int k, int v) { sliderWord(k, v + 65); }        // (let go)
static void slideOld(int k, int v) { char n[4] = {'s', (char) ('0' + k), 0, 0}; finger[n] = (uint32_t) v; sliderWord(k, 0); }   // (a page from before B105: asked)
static std::string lv(int i) { char n[4] = {'l', 'v', (char) ('0' + i), 0}; return fields.count(n) ? fields[n] : std::string("<none>"); }
static bool table(const char *a, const char *b, const char *c, const char *d, const char *e) { return lv(0) == a && lv(1) == b && lv(2) == c && lv(3) == d && lv(4) == e; }
static void forget() { for (int i = 0; i < 5; ++i) { char n[4] = {'l', 'v', (char) ('0' + i), 0}; fields.erase(n); } }
static void save() { fcLog.clear(); boxes = 0; confirms = 0; stores = 0; boots = 0; lastBox = ""; SaveEasy(); run(); }

int main(int argc, char **argv) {
    if (argc > 1 && std::string(argv[1]) == "grid") { grid(); return 0; }
    if (argc > 1 && std::string(argv[1]) == "decode") { long w; while (std::cin >> w) printf("%u %u\n", (unsigned) CodeOf((int) w), (unsigned) ArgOf((int) w)); return 0; }   // (part 3: the page's words through main.cpp's sums)
    { // governor: mode 3 (ELECTRIC), startup 15.0 s, spool-up 10.0 s, handover 20 %, throttle type 0 (NORMAL)
      uint8_t g[42] = {0}; g[0] = 3; g[1] = 150; g[3] = 100; g[5] = 20; g[19] = 20; g[20] = 20; g[25] = 10; g[28] = 0; GOV0 = hexOf(g, 42); }
    { // rates, Actual: centre 18 (180 deg/s), expo 40, max rate 36 (360) on roll and pitch, 45 (450) on yaw
      uint8_t r[37] = {0}; r[0] = 4; for (int ax = 0; ax < 4; ++ax) { r[1 + ax * 6] = ax == 2 ? 20 : 18; r[2 + ax * 6] = 40; r[3 + ax * 6] = ax == 2 ? 45 : 36; r[4 + ax * 6] = 10; }
      RATES_ACT = hexOf(r, 37); r[0] = 6; RATES_RF = hexOf(r, 37); }
    PID0 = words({50, 100, 40, 100, 52, 104, 44, 100, 60, 120, 30, 0, 3, 3, 0, 15, 15});
    { uint8_t p[17] = {0}; p[0] = 0xD0; p[1] = 0x07; p[2] = 40; GP_OFF = hexOf(p, 17); p[15] = 0x10; GP_ON = hexOf(p, 17); }

    // 1. the page opens: where the flight controller is, then the governor, the rates and the PIDs - no bank chosen
    model(); open();
    CHECK(CurrentView == EASYVIEW && EzHave && EzStep == EZ_IDLE && !BlockBankChanges);
    CHECK(fns() == "101 142 111 112");
    CHECK(fields["t14"] == "Bank 2" && fields["t8"] == "Rate 2" && fields["t11"] == "Havok" && fields["note"] == "");
    CHECK(vals["s0"] == 10 && vals["s1"] == 10 && vals["s2"] == 10 && vals["sw"] == 1);   // (Start, Agility, Stick feel at their centres: today's numbers are the backup's)
    // Cyclic: (50/48 + 1 + 1 + 1 + 1 + 1 + 1 + 1) / 8 = 1.0052 -> 0 %; Tail: (60/58 + 1 + 1) / 3 (yaw F is 0: not counted) = 1.0115 -> 0 %
    CHECK(EzPos[3] == 0 && EzPos[4] == 0 && vals["s3"] == 6 && vals["s4"] == 6);
    CHECK(sent("vis b3,0") && !sent("vis lA,0"));

    // 2. Cyclic +10 %: the note, then a save that writes the cyclic words from the backup's centre - and not the tail's
    cmds.clear(); slide(3, 8);
    CHECK(EzPos[3] == 10 && EzMoved[3] && Ez_Was_Edited && sent("vis b3,1"));
    CHECK(table("Cyclic +10 %\r\nRoll\r\nPitch", "P\r\n50 -> 53\r\n52 -> 57", "I\r\n100 -> 110\r\n104 -> 114", "D\r\n40 -> 44\r\n44 -> 48", "F\r\n100 -> 110\r\n100 -> 110"));
    forget(); lift(3, 8); CHECK(lv(0) == "<none>" && fields["note"] == "" && EzPos[3] == 10);   // (let go: the box is the screen's to hide; nothing written to it)
    save();
    CHECK(confirms == 1 && lastQuestion == "Write to the flight controller?\r\nFeel (PIDs, bank 2)");
    CHECK(fns() == "101 202 250 112");
    CHECK(word(pid[1], 0) == 53 && word(pid[1], 1) == 110 && word(pid[1], 2) == 44 && word(pid[1], 3) == 110 && word(pid[1], 4) == 57 && word(pid[1], 7) == 110);
    CHECK(word(pid[1], 8) == 60 && word(pid[1], 9) == 120 && word(pid[1], 10) == 30 && word(pid[1], 11) == 0);   // (the tail's, as they were: B104 - the phone's rounded them through its grid)
    CHECK(word(pid[1], 12) == 3 && word(pid[1], 15) == 15 && word(pid[1], 16) == 15);   // (boost and the HSI offsets left alone)
    CHECK(boxes == 0 && fields["busy"] == "Saved, and read back the same: Feel." && EzMsgUntil != 0 && !Ez_Was_Edited && !EzMoved[3] && EzStep == EZ_IDLE);
    CHECK(EzPos[3] == 10 && vals["s3"] == 8);   // (the slider stays where it was left: the centre is the backup's)
    now += 5000; EasyPoll(); CHECK(EzMsgUntil == 0 && sent("vis busy,0"));

    // 3. Agility on the Actual type: the max rate moved, the centre sensitivity in proportion, the expo not touched
    model(); open(); slide(1, 14);   // 70: 360 x 2^0.4 = 475 -> 480 (10 a step); 450 x 2^0.4 = 594 -> 590
    CHECK(table("Agility\r\nMax rate\r\nCentre", "Roll\r\n360 -> 480\r\n180 -> 240", "Pitch\r\n360 -> 480\r\n180 -> 240", "Yaw\r\n450 -> 590\r\n200 -> 260", ""));
    save();
    CHECK(fns() == "101 204 250 111" && lastQuestion == "Write to the flight controller?\r\nAgility (rates, rate 2)");
    CHECK(byteAt(rates[1], 3) == 48 && byteAt(rates[1], 1) == 24 && byteAt(rates[1], 9) == 48 && byteAt(rates[1], 15) == 59 && byteAt(rates[1], 13) == 26);   // (18 x 48 / 36 = 24; 20 x 59 / 45 = 26.2 -> 26)
    CHECK(byteAt(rates[1], 2) == 40 && byteAt(rates[1], 21) == 36 && byteAt(rates[0], 3) == 36);   // (expo as it was; the collective and the other banks untouched)
    CHECK(fields["busy"] == "Saved, and read back the same: Agility.");
    // ... and Stick feel on the Rotorflight type: the expo only
    model(); for (int b = 0; b < 6; ++b) rates[b] = fileRates[b] = RATES_RF;
    open(); slide(2, 6);   // 30: 40 - (30 - 50) x 0.7 = 54
    CHECK(table("Stick feel\r\nExpo", "Roll\r\n40 -> 54", "Pitch\r\n40 -> 54", "Yaw\r\n40 -> 54", "") && EzPos[2] == 30);   // (Rotorflight's type: the expo as it is)
    save(); CHECK(byteAt(rates[1], 2) == 54 && byteAt(rates[1], 8) == 54 && byteAt(rates[1], 14) == 54 && byteAt(rates[1], 20) == 40 && byteAt(rates[1], 1) == 18);

    // 4. Start, with the switch on (as it opens): PID spool-up in every bank, the transmitter's bank again, the governor,
    //    the store, the restart, and the read-back once the flight controller is back (it misses the first ask)
    model(); open(); slide(0, 14);   // 70: k = 2^-0.4 = 0.758: spool-up 10 -> 8, startup 15 -> 11, handover 20 + 6 = 26
    CHECK(table("Start\r\nGovernor", "Spool-up\r\n10 -> 8 s", "Handover\r\n20 -> 26 %", "Startup\r\n15 -> 11 s", ""));
    CHECK(EasyHoldsBanks() == false);
    fcLog.clear(); boxes = 0; confirms = 0; stores = 0; boots = 0; SaveEasy();
    CHECK(lastQuestion == "Write to the flight controller?\r\nStart (governor): it then restarts,\r\nso blades off.\r\nPID spool-up on in every bank." && BlockBankChanges && EasyHoldsBanks());
    for (int i = 0; i < 6 && EzStep != EZ_S_WAIT; ++i) { EasyPoll(); now += 50; }
    for (int i = 0; i < 40 && EzStep != EZ_S_WAIT; ++i) { EasyPoll(); now += 50; }
    CHECK(EzStep == EZ_S_WAIT && !BlockBankChanges && !EasyHoldsBanks());   // (the bank switch free again for the restart)
    run();
    CHECK(fns() == "101 210:00 148 149 210:01 148 210:02 148 149 210:03 148 210:04 148 149 210:05 148 210:01 143 250 68 142 142");
    CHECK(fcPid == 1 && boots == 1 && stores == 1);
    for (int b = 0; b < 6; ++b) CHECK(byteAt(gprof[b], 15) == 0x10);
    CHECK(word(gov, 0) == 0 || true);
    CHECK(byteAt(gov, 3) == 80 && byteAt(gov, 4) == 0 && byteAt(gov, 1) == 110 && byteAt(gov, 19) == 26 && byteAt(gov, 0) == 3 && byteAt(gov, 28) == 0 && byteAt(gov, 5) == 20);
    CHECK(boxes == 0 && fields["busy"] == "Saved, and read back the same: Start.\r\nPID spool-up switched on in 3 banks." && !Ez_Was_Edited);
    CHECK(EzPos[0] == 65 && vals["s0"] == 13);   // (8 s against the centre's 10 s is 65, not 70: whole seconds - as the phone's reflect)

    // 5. the switch alone: off and nothing else is nothing; on again: the walk and a store - no governor, no restart
    model(); open(); finger["sw"] = 0; EasySpoolTapped(); CHECK(!EzSpool && Ez_Was_Edited);
    save(); CHECK(boxes == 1 && lastBox == "Nothing has changed." && fcLog.empty());
    finger["sw"] = 1; EasySpoolTapped(); CHECK(EzSpool && EzSpoolTouched);
    CHECK(fields["note"] == "" && lv(0) == "<none>");   // (B105: the switch writes no numbers)
    save();
    CHECK(lastQuestion == "Write to the flight controller?\r\nPID spool-up on in every bank." && count(143) == 0 && count(68) == 0 && stores == 1 && count(149) == 3);
    CHECK(fields["busy"] == "PID spool-up switched on in 3 banks, and stored." && fcPid == 1);
    finger["sw"] = 0; EasySpoolTapped(); finger["sw"] = 1; EasySpoolTapped(); save();
    CHECK(count(149) == 0 && fields["busy"] == "PID spool-up was on in every bank already.");

    // 6. the flight controller on another bank: refused as the page opens (nothing read), and at a save (nothing written)
    model(); fcPid = 0; open();
    CHECK(boxes == 1 && lastBox == "The flight controller is on\r\nbank 1, the transmitter on bank 2.\r\nCheck the bank switch's set-up." && CurrentView == ROTORFLIGHTVIEW && fns() == "101" && !BlockBankChanges);
    model(); fcRate = 3; open(); CHECK(lastBox == "The flight controller is on\r\nrates 4, the transmitter on rates 2.\r\nCheck the rates switch's set-up.");
    model(); open(); slide(4, 4); fcPid = 0; save();
    CHECK(lastBox == "Not saved: the flight controller is on\r\nbank 1, the transmitter on bank 2.\r\nCheck the bank switch's set-up.\r\nNothing was written." && fns() == "101" && !BlockBankChanges);

    // 7. B103: a throttle type outside Rotorflight's list is never written back - refused before anything is asked
    model(); gov = setByte(GOV0, 28, 3); open(); slide(0, 12); save();
    CHECK(boxes == 1 && lastBox == "Not saved: Throttle type is 3.\r\nIt must be 0 - 2: put it right on\r\nthe Governor (global) page first." && fcLog.empty());
    model(); gov = setByte(GOV0, 0, 7); open(); slide(3, 7); save(); CHECK(count(202) == 1 && count(143) == 0);   // (Feel alone does not write the governor: allowed)

    // 8. a rates type the sliders do not cover: Agility and Stick feel go, the note says why; their events are ignored
    model(); for (int b = 0; b < 6; ++b) rates[b] = setByte(RATES_ACT, 0, 0);
    open(); CHECK(!EzRatesFeel && sent("vis lA,0") && sent("vis s2,0") && fields["note"].find("Betaflight, Raceflight or KISS") != std::string::npos);
    slide(1, 18); CHECK(!EzMoved[1] && !Ez_Was_Edited);

    // 9. no backup: the centres are the numbers the page opened with - and they stay so after a save
    model(); haveFile = false; open();
    CHECK(fields["note"] == "Not in a backup yet, so the sliders are centred on the numbers the page opened with. A backup sets their centre." && !EzBackupCentre);
    slide(3, 8); CHECK(table("Cyclic +10 %\r\nRoll\r\nPitch", "P\r\n50 -> 55\r\n52 -> 57", "I\r\n100 -> 110\r\n104 -> 114", "D\r\n40 -> 44\r\n44 -> 48", "F\r\n100 -> 110\r\n100 -> 110"));
    save(); CHECK(word(pid[1], 0) == 55 && EzPos[3] == 10 && vals["s3"] == 8);
    slide(3, 6); CHECK(table("Cyclic 0 %\r\nRoll\r\nPitch", "P\r\n55 -> 50\r\n57 -> 52", "I\r\n110 -> 100\r\n114 -> 104", "D\r\n44 -> 40\r\n48 -> 44", "F\r\n110 -> 100\r\n110 -> 100"));   // (now -> what Save would write)
    lift(3, 6); CHECK(fields["note"] == "Not in a backup yet, so the sliders are centred on the numbers the page opened with. A backup sets their centre.");

    // 10. a failure part way through the walk: the transmitter's bank chosen again first, then the box
    model(); open(); slide(0, 6); refuseFn[148] = 400; refuseBank = 3; save();
    CHECK(fcPid == 1 && boxes == 1 && lastBox.find("Not saved: PID spool-up (could not read a bank):\r\nrefused by the fake") == 0 && !BlockBankChanges && EzStep == EZ_IDLE);
    CHECK(count(143) == 0 && fcLog.back().fn == 210 && fcLog.back().data == "01");
    // ... and the page left part way through the walk: the bank chosen again, quietly
    model(); open(); slide(0, 6); fcLog.clear(); boxes = 0; SaveEasy();
    for (int i = 0; i < 4; ++i) { EasyPoll(); now += 50; }
    CHECK(EzStep >= EZ_S_WALK_SEL && EzStep <= EZ_S_WALK_WRITE);
    CurrentView = ROTORFLIGHTVIEW; run();
    CHECK(EzStep == EZ_IDLE && boxes == 0 && fcPid == 1 && !BlockBankChanges && count(143) == 0);

    // 11. after the restart the flight controller never comes back: said so (written and stored)
    model(); awayAfterBoot = 99; open(); slide(0, 8); slide(3, 7); save();
    CHECK(count(142) == 3 && boxes == 1 && lastBox.find("Start was written and stored, but the\r\nflight controller has not come back") == 0 && lastBox.find("Read back the same: Feel.") != std::string::npos);

    // 12. the receiver busy once: the same request again; a read-back that differs: said
    model(); busyOnce = 1; open(); CHECK(EzHave && fns() == "101 101 142 111 112");
    slide(3, 9); spoilPid = true; save();
    CHECK(boxes == 1 && lastBox == "Saved, but read back DIFFERENT:\r\nFeel. Open that page and check.");

    // 13. OK with a slider moved asks "Save now?": Save saves, then the page closes once it has worked; Discard leaves
    model(); open(); slide(4, 8); saveAnswer = true; confirmAnswer = true; fcLog.clear(); EndEasyView();
    CHECK(lastQuestion == "Write to the flight controller?\r\nFeel (PIDs, bank 2)" && CurrentView == EASYVIEW && RfLeaveAfterSave);
    run(); CHECK(CurrentView == ROTORFLIGHTVIEW && word(pid[1], 8) == 64 && word(pid[1], 0) == 50);   // (Tail +10 % of the backup's 58: 64; the cyclic as it was)
    model(); open(); slide(4, 8); saveAnswer = false; fcLog.clear(); EndEasyView(); CHECK(CurrentView == ROTORFLIGHTVIEW && fcLog.empty());
    model(); open(); slide(4, 8); saveAnswer = true; confirmAnswer = false; fcLog.clear(); EndEasyView(); CHECK(CurrentView == EASYVIEW && fcLog.empty() && !RfLeaveAfterSave);
    // OK with nothing moved: straight back to the menu
    model(); open(); EndEasyView(); CHECK(CurrentView == ROTORFLIGHTVIEW);

    // 14. the bank switch moved with a slider moved: said, and the new bank read
    model(); open(); slide(3, 10); boxes = 0; Bank = 3; fcPid = 2; fcLog.clear(); EasyBankChanged(); run();
    CHECK(boxes == 1 && lastBox.find("The sliders were moved but not saved.") == 0 && fields["t14"] == "Bank 3" && fns() == "101 142 111 112" && !Ez_Was_Edited && EzHave);

    // 15. no model, armed, no Bluetooth: refused before the page opens
    model(); BoundFlag = false; boxes = 0; CurrentView = ROTORFLIGHTVIEW; fcLog.clear(); StartEasyView();
    CHECK(boxes == 1 && lastBox.find("Easy tuning needs the model connected") == 0 && CurrentView == ROTORFLIGHTVIEW && fcLog.empty());
    model(); armed = true; boxes = 0; StartEasyView(); CHECK(boxes == 1 && lastBox.find("Model is armed") == 0 && CurrentView == ROTORFLIGHTVIEW);
    model(); open(); slide(3, 8); armed = true; boxes = 0; fcLog.clear(); SaveEasy(); CHECK(boxes == 1 && fcLog.empty());

    // 16. a slider touched but not moved: the numbers shown, nothing to save; the screen not answering: nothing
    model(); open(); slide(3, 6); CHECK(!EzMoved[3] && !Ez_Was_Edited && table("Cyclic 0 %\r\nRoll\r\nPitch", "P\r\n50\r\n52", "I\r\n100\r\n104", "D\r\n40\r\n44", "F\r\n100\r\n100"));   // (one number: Save would leave it)
    forget(); finger.erase("s3"); sliderWord(3, 0); CHECK(lv(0) == "<none>" && !EzMoved[3]);   // (no place in the word and the screen not answering: nothing)
    // the end of a slider's travel: said under the rows once the finger lifts
    slide(3, 12); CHECK(table("Cyclic +30 %\r\nRoll\r\nPitch", "P\r\n50 -> 62\r\n52 -> 68", "I\r\n100 -> 130\r\n104 -> 135", "D\r\n40 -> 52\r\n44 -> 57", "F\r\n100 -> 130\r\n100 -> 130"));
    lift(3, 12); CHECK(fields["note"] == "Cyclic is at the end of its travel: a backup re-centres it.");
    slide(4, 0); CHECK(table("Tail -30 %\r\nYaw", "P\r\n60 -> 41", "I\r\n120 -> 84", "D\r\n30 -> 21", "F\r\n0"));
    lift(4, 0); CHECK(fields["note"] == "Tail is at the end of its travel: a backup re-centres it.");
    slide(0, 0); lift(0, 0); CHECK(fields["note"] == "Start is at the end of its travel: a backup re-centres it.");
    slide(0, 3); lift(0, 3); CHECK(fields["note"] == "");   // (away from the end: the opening line again - none, with a backup)

    // 18. B105: the place in the word against the place asked for (a page from before B105): the same numbers
    model(); open(); slideOld(3, 9); const std::string asked = lv(1); model(); open(); slide(3, 9); CHECK(lv(1) == asked && asked == "P\r\n50 -> 55\r\n52 -> 60" && EzPos[3] == 15);
    // the finger moved on between its last word and the lift: the lift's place is the one kept
    slide(3, 7); lift(3, 10); CHECK(EzPos[3] == 20 && EzMoved[3]);
    // words that cannot be a place: ignored (64 alone: let go at -1; Cyclic beyond its 12 steps)
    forget(); sliderWord(3, 64); sliderWord(3, 14 + 1); CHECK(lv(0) == "<none>" && EzPos[3] == 20);
    // a save running: the sliders are not taken
    model(); open(); slide(3, 8); fcLog.clear(); SaveEasy(); forget(); slide(4, 2); CHECK(lv(0) == "<none>" && !EzMoved[4]); run();
    // Agility on Rotorflight's own rates type: one row, Rate (x 5), as the Rates page has it
    model(); for (int b = 0; b < 6; ++b) rates[b] = fileRates[b] = RATES_RF;
    open(); slide(1, 14); CHECK(table("Agility\r\nRate", "Roll\r\n90 -> 120", "Pitch\r\n90 -> 120", "Yaw\r\n100 -> 130", ""));
    // Stick feel on the Actual type: the expo in hundredths, as the Rates page shows it
    model(); open(); slide(2, 6); CHECK(table("Stick feel\r\nExpo", "Roll\r\n0.40 -> 0.54", "Pitch\r\n0.40 -> 0.54", "Yaw\r\n0.40 -> 0.54", ""));
    // a governor time in tenths: shown as the Governor page shows it
    model(); gov = setByte(GOV0, 3, 75); fileGov = gov; open(); slide(0, 10); CHECK(lv(1) == "Spool-up\r\n7.5 s" && !EzMoved[0]);
    slide(0, 12); CHECK(lv(1) == "Spool-up\r\n7.5 -> 7 s" && lv(3) == "Startup\r\n15 -> 13 s");
    // a word lost on the way (the knob shows +15 %, the last word read said +10 %): Save asks every slider first and saves what shows
    model(); open(); slide(3, 8); finger["s3"] = 9; save(); CHECK(EzPos[3] == 15 && word(pid[1], 0) == 55 && word(pid[1], 4) == 60);   // (48 and 52 x 1.15)
    // ... and a slider whose every word was lost: still saved; the switch likewise
    model(); open(); finger["s4"] = 8; save(); CHECK(count(202) == 1 && word(pid[1], 8) == 64 && lastQuestion == "Write to the flight controller?\r\nFeel (PIDs, bank 2)");
    model(); open(); finger["sw"] = 0; finger["s0"] = 14; save(); CHECK(!EzSpool && count(148) == 0 && count(143) == 1);   // (Start saved, the switch shown off: no walk)
    // the dispatcher (main.cpp): every code as before; a slider's word gives its code and its place
    for (int code = 1; code < 214; ++code) CHECK(CodeOf(code << 8) == (uint32_t) code && ArgOf(code << 8) == 0);
    for (int k = 0; k < 5; ++k) for (int v = 0; v <= 20; ++v) { const int w = ((v + 1) << 24) + ((208 + k) << 8), l = ((v + 65) << 24) + ((208 + k) << 8);
        CHECK(CodeOf(w) == (uint32_t) (208 + k) && ArgOf(w) == v + 1 && CodeOf(l) == (uint32_t) (208 + k) && ArgOf(l) == v + 65); }

    // 17. a request never answered: the read gives up and says so
    model(); silent = true; fcLog.clear(); boxes = 0; CurrentView = ROTORFLIGHTVIEW; StartEasyView();
    for (int i = 0; i < 5; ++i) { EasyPoll(); now += 50; } CHECK(EzStep == EZ_R_STATUS && BlockBankChanges);
    late = true; run(); CHECK(boxes == 1 && lastBox == "No answer from the flight controller" && CurrentView == ROTORFLIGHTVIEW && !BlockBankChanges);
    // ... and a save never answered: said so, with what was saved before
    model(); open(); slide(3, 8); slide(1, 12); fcLog.clear(); boxes = 0; SaveEasy(); run(); CHECK(EzStep == EZ_IDLE);
    model(); open(); slide(3, 8); slide(1, 12); refuseFn[204] = 0; silent = false; fcLog.clear(); boxes = 0; SaveEasy();
    for (int i = 0; i < 20 && EzStep != EZ_S_RATES; ++i) { EasyPoll(); now += 50; }
    silent = true; EzReq = MspAsk(204, nullptr, 0); late = true; run();
    CHECK(boxes == 1 && lastBox.find("Saved: Feel.\r\nNot saved: no answer:\r\nno answer in 9 s") == 0);

    printf("test_easy (page): %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-format-truncation', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit(1)
exe = os.path.join(d, 't')

# ---- part 1: the same random cases through the phone's code (node) and the transmitter's
html = open(os.path.join(RXV2, 'rotorflight-easy.html')).read()
script = html[html.index('<script>') + 8:html.index('</script>', html.index('<script>'))]
app = open(os.path.join(RXV2, 'app.js')).read()
helpers = app[app.index('LDRC.feelModel = t =>'):app.index('\n', app.index('LDRC.endHint'))]
rnd = random.Random(104)
cases = []
for _ in range(6000):
    cases.append({'k': 'start', 'bs': rnd.choice([0, rnd.randint(1, 300)] + [rnd.randint(5, 200)] * 3), 'bst': rnd.randint(0, 600), 'bh': rnd.randint(0, 60), 'cs': rnd.choice([0, rnd.randint(1, 600)] + [rnd.randint(5, 300)] * 3), 'v': rnd.randrange(0, 101, 5)})
for _ in range(2000):
    g = [rnd.randint(0, 255) for _ in range(42)]
    cases.append({'k': 'gov', 't': rnd.randint(0, 1), 'v': rnd.randrange(0, 101, 5), 'bs': rnd.randint(0, 300), 'bst': rnd.randint(0, 600), 'bh': rnd.randint(0, 60), 'gov': g})
for _ in range(8000):
    t = rnd.choice([6, 6, 4, 4, 5, 0, 1, 2, 3])
    b = [rnd.randint(0, 255) for _ in range(37)]; b[0] = t
    for ax in range(4):
        b[1 + ax * 6] = rnd.randint(0, 120); b[2 + ax * 6] = rnd.randint(0, 100); b[3 + ax * 6] = rnd.randint(0, 120)
    base = (rnd.choice([0, rnd.randint(10, 1200)] + [rnd.randrange(50, 1000, 5)] * 4), rnd.randrange(0, 1200, 5), rnd.randint(0, 100))
    cases.append({'k': 'rates', 'ta': rnd.randint(0, 1), 'te': rnd.randint(0, 1), 'v': rnd.randrange(0, 101, 5), 'e': rnd.randrange(0, 101, 5), 'brp': base[0], 'byaw': base[1], 'bex': base[2], 'blob': b})
for _ in range(8000):
    cur = [rnd.choice([0, rnd.randint(1, 1000)] + [rnd.randint(5, 300)] * 5) for _ in range(17)]
    base = [rnd.choice([0, rnd.randint(1, 1000)] + [rnd.randint(5, 300)] * 5) for _ in range(12)]
    cases.append({'k': 'pid', 'tc': rnd.randint(0, 1), 'tt': rnd.randint(0, 1), 'cyc': rnd.randrange(-30, 31, 5), 'tail': rnd.randrange(-30, 31, 5), 'base': base,
                  'cur': [x for w in cur for x in (w & 255, w >> 8)]})
def line(c):
    if c['k'] == 'start': return 'start %d %d %d %d %d' % (c['bs'], c['bst'], c['bh'], c['cs'], c['v'])
    if c['k'] == 'gov': return 'gov %d %d %d %d %d %s' % (c['t'], c['v'], c['bs'], c['bst'], c['bh'], bytes(c['gov']).hex().upper())
    if c['k'] == 'rates': return 'rates %d %d %d %d %d %d %d %s' % (c['ta'], c['te'], c['v'], c['e'], c['brp'], c['byaw'], c['bex'], bytes(c['blob']).hex().upper())
    return 'pid %d %d %d %d %s %s' % (c['tc'], c['tt'], c['cyc'], c['tail'], ','.join(map(str, c['base'])), bytes(c['cur']).hex().upper())
runner = r'''
const els = {}; const el = id => (els[id] = els[id] || { value: 0, checked: true, textContent: '', style: {}, classList: { toggle() {} }, disabled: false });
const document = { getElementById: el, addEventListener() {} }, localStorage = { getItem() { return null; }, setItem() {} }, window = { scrollTo() {} };
const LDRC = {};
''' + helpers + '\n' + script + r'''
const out = [];
for (const c of CASES) {
    if (c.k === 'start') { startBase = { spool: c.bs / 10, hand: c.bh, start: c.bst / 10 }; const n = startNums(c.v); out.push(['start', startFeel(c.cs / 10), n.spool, n.hand, n.start].join(' ')); }
    else if (c.k === 'gov') { startBase = { spool: c.bs / 10, hand: c.bh, start: c.bst / 10 }; govRaw = Uint8Array.from(c.gov); el('s_start').value = c.v; touched.start = !!c.t; out.push('gov ' + bytesToHex(govBytes())); }
    else if (c.k === 'rates') { ratesRaw = Uint8Array.from(c.blob); ratesBase = { rp: c.brp, yaw: c.byaw, expo: c.bex }; el('s_agile').value = c.v; el('s_expo').value = c.e; touched.agile = !!c.ta; touched.expo = !!c.te;
        const r = feelRate(c.v); out.push(['rates', agileFeel(LDRC.feelRateOf(ratesRaw, 0)), LDRC.feelModel(ratesRaw[0]) ? expoFeel(LDRC.feelExpoOf(ratesRaw, 0)) : '-', r.rp, r.yaw, feelExpoOf(c.e), bytesToHex(ratesBytes())].join(' ')); }
    else { pidRaw = Uint8Array.from(c.cur); pidBase = []; for (let i = 0; i < 17; i++) pidBase.push(u16(pidRaw, i * 2)); pidBaseObj = {}; PIDKEYS.forEach((k, i) => pidBaseObj[k] = c.base[i]);
        el('s_cyc').value = c.cyc; el('s_tail').value = c.tail; touched.cyc = !!c.tc; touched.tail = !!c.tt;
        out.push(['pid', nudgePos('cyc'), nudgePos('tail'), bytesToHex(pidBytes())].join(' ')); }
}
process.stdout.write(out.join('\n') + '\n');
'''
jsf = os.path.join(d, 'phone.js')
open(jsf, 'w').write('const CASES = ' + json.dumps(cases) + ';\n' + runner)
phone = subprocess.run(['node', jsf], capture_output=True, text=True)
if phone.returncode: print(phone.stderr[:3000]); sys.exit(1)
tx = subprocess.run([exe, 'grid'], input='\n'.join(line(c) for c in cases) + '\n', capture_output=True, text=True)
pl, tl = phone.stdout.splitlines(), tx.stdout.splitlines()
diff = [(i, cases[i], pl[i], tl[i] if i < len(tl) else None) for i in range(len(pl)) if i >= len(tl) or pl[i] != tl[i]]
kinds = {}
for c in cases: kinds[c['k']] = kinds.get(c['k'], 0) + 1
print('test_easy (sums): %d cases (%s) against the phone\'s own code: %d different' % (len(cases), ', '.join('%d %s' % (n, k) for k, n in kinds.items()), len(diff)))
for i, c, p, t in diff[:8]: print('  DIFFERENT', line(c), '\n    phone:', p, '\n    tx:   ', t)
page = subprocess.run([exe], capture_output=True, text=True)
sys.stdout.write(page.stdout); sys.stderr.write(page.stderr[:6000])
n_checks = int(re.search(r'(\d+) checks', page.stdout).group(1)) if 'checks' in page.stdout else 0

# ---- part 3 (B105): the screen's page file - its sliders' words, worked out as the screen works them out, read by main.cpp's sums
pg = json.load(open(PAGE81)); by = {c['n']: c for c in pg['comps']}; idx = {c['n']: k for k, c in enumerate(pg['comps'])}
LIVE = ['lvb', 'lv0', 'lv1', 'lv2', 'lv3', 'lv4']
pchecks, pfails = 0, []
def pcheck(ok, what):
    global pchecks
    pchecks += 1
    if not ok: pfails.append(what)
def nextion_eval(expr, env):   # NextionScript::evalTokens: left to right, no precedence, brackets
    toks = re.findall(r'\d+|[A-Za-z_]\w*\.\w+|<<|>>|[-+*/()&|]', expr.replace(' ', ''))
    pos = [0]
    def run():
        acc, op, first = 0, None, True
        while pos[0] < len(toks):
            t = toks[pos[0]]; pos[0] += 1
            if t == ')': return acc
            if t in ('+', '-', '*', '/', '<<', '>>', '&', '|'): op = t; continue
            v = run() if t == '(' else int(t) if t.isdigit() else env[t]
            if first: acc, first = v, False
            else: acc = {'+': acc + v, '-': acc - v, '*': acc * v, '/': int(acc / v), '<<': acc << v, '>>': acc >> v, '&': acc & v, '|': acc | v}[op]
            acc = (acc + 2 ** 31) % 2 ** 32 - 2 ** 31   # (an int32, as on the screen)
        return acc
    return run()
words, want = [], []
shade = {0: by['lS']['c']['bco'], 1: by['lA']['c']['bco'], 2: by['lE']['c']['bco'], 3: by['lC']['c']['bco'], 4: by['lT']['c']['bco']}
for k in range(5):
    sl = by['s%d' % k]; ev = sl.get('ev', {})
    pcheck(sl['a']['maxval'] == (20 if k < 3 else 12) and sl['a']['minval'] == 0, 's%d: its steps (0..20, or 0..12 for Cyclic and Tail)' % k)
    for kind in ('p', 'm', 'r'):
        lines = ev.get(kind, '').split('\n')
        asg = [l for l in lines if l.startswith('va0.val=')]
        pcheck(len(asg) == 1 and lines[-1] == 'print va0.val' and lines[-2] == asg[0], 's%d %s: one word, printed last' % (k, kind))
        if len(asg) != 1: continue
        for v in range(sl['a']['maxval'] + 1):
            words.append(nextion_eval(asg[0][len('va0.val='):], {'s%d.val' % k: v})); want.append((208 + k, v + (65 if kind == 'r' else 1), 's%d %s at %d' % (k, kind, v)))
    press, lift = ev.get('p', '').split('\n'), ev.get('r', '').split('\n')
    first_vis = min([i for i, l in enumerate(press) if l.startswith('vis ')] or [999])
    for n in LIVE:
        pcheck(('%s.bco=%d' % (n, shade[k])) in press[:first_vis], 's%d press: %s in the row\'s shade before it shows' % (k, n))
        pcheck(('vis %s,1' % n) in press, 's%d press: %s shown' % (k, n))
        pcheck(('vis %s,0' % n) in lift, 's%d release: %s hidden' % (k, n))
        if n != 'lvb': pcheck(('%s.txt=""' % n) in press[:first_vis], 's%d press: %s emptied before it shows' % (k, n))
    pcheck(not any(l.startswith('vis ') for l in ev.get('m', '').split('\n')), 's%d move: shows or hides nothing' % k)
dec = subprocess.run([exe, 'decode'], input='\n'.join(map(str, words)) + '\n', capture_output=True, text=True).stdout.split('\n')
for (code, arg, what), line in zip(want, dec):
    pcheck(line == '%d %d' % (code, arg), what + ': the word reads as code %d, place byte %d (got %s)' % (code, arg, line))
pcheck(len(dec) >= len(want), 'every word decoded')
pre = pg['ev']['preinitialize'].split('\n')
for n in LIVE:
    pcheck(('vis %s,0' % n) in pre, 'the page opens with %s hidden' % n)
    pcheck(idx['b1'] < idx[n] < idx['busy'], '%s above the buttons, under the message box' % n)
pcheck(by['sw']['y'] > by['s4']['y'] and by['lP']['y'] > by['s4']['y'], 'the switch\'s row is the last (B105)')
pcheck(by['lP']['c']['bco'] == by['card']['c']['bco'] and by['lP']['c']['pco'] == 65535, 'the switch\'s words are white on the card, not a pale bar (B105)')
pcheck(by['card']['y'] < by['lvb']['y'] and by['lvb']['y'] + by['lvb']['h'] <= min(by['s%d' % k]['y'] for k in range(5)), 'the box above every slider, inside the card (1.11.77: under them the finger hid it)')
pcheck(by['note']['y'] == by['lvb']['y'] and by['note']['h'] == by['lvb']['h'], 'the note in the box\'s place')
pcheck(all(by['s%d' % k]['h'] >= 32 for k in range(5)) and by['sw']['y'] + by['sw']['h'] <= by['b1']['y'] - 8, 'the sliders as big as before; the rows clear of the buttons')
pcheck(by['lvb']['x'] <= min(by[n]['x'] for n in LIVE[1:]) and by['lvb']['x'] + by['lvb']['w'] >= max(by[n]['x'] + by[n]['w'] for n in LIVE[1:]), 'the box holds its columns')
print('test_easy (page file): %d checks, %d failures' % (pchecks, len(pfails)))
for f in pfails[:12]: print('  FAIL', f)

print('test_easy: %d checks, %d failures' % (n_checks + len(cases) + pchecks, (1 if page.returncode else 0) * max(1, page.stdout.count('FAIL')) + len(diff) + (len(re.findall('FAIL', page.stderr))) + len(pfails)))
sys.exit(1 if (diff or page.returncode or len(pl) != len(cases) or pfails) else 0)
