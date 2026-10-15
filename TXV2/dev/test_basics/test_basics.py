#!/usr/bin/env python3
"""Host test of the Model basics pages (B99): include/RF_Basics.h on the Mac over a fake screen and a fake flight controller
on the fake pipe. The read (42, 131, 123 - the last optional), the five choices stepping round (an unlisted motor protocol
shown as "Protocol N", one tap to PWM), the pole count made even, the gear ratios as teeth or as turns with a decimal (1 and
10.2 -> 10 : 102), the save (43, a 28-byte 222 without the motor-count byte, 216, 250, 68, then 42 asked until the
restarted flight controller answers, 131 and 123 read back), the backwards-ratio warning, no restart and no 68 offline, the
discard question, and the refusal while armed.
   python3 dev/test_basics/test_basics.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDR = os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Basics.h')
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
#define RFSETUPVIEW 61
#define BASICSVIEW 77
#define BASICS2VIEW 78
static int CurrentView = 0;
static bool offline = false, armed = false;
static char ModelName[20] = "Havoc";
static uint32_t now = 1000;
static uint32_t millis() { return now; }
static std::map<std::string, std::string> fields; static std::vector<std::string> cmds; static int boxes = 0; static std::string lastBox; static bool confirmAnswer = true; static int sounds = 0, rfStarts = 0, asked = 0, gathers = 0;
static void SendCommand(char *c) { cmds.push_back(c); }
static void SendText(char *n, char *t) { fields[n] = t; }
static void MsgBox(char *page, const char *msg) { ++boxes; lastBox = msg; }
static bool GetConfirmation(char *page, char *prompt) { ++asked; lastBox = prompt; return confirmAnswer; }
static void PlaySound(int) { ++sounds; }
static void RotorFlightStart() { ++rfStarts; CurrentView = ROTORFLIGHTVIEW; }
static void RFSettingsGather() { ++gathers; }
static bool ModelSeemsArmed(char *why, size_t n) { if (!armed) return false; snprintf(why, n, "Model is armed"); return true; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static bool RfNeedsModel(char *, size_t) { return false; }
static bool BakOffline() { return offline; }
static void GetText(char *n, char *out, int len) { snprintf(out, len, "%s", fields[n].c_str()); }
static long FieldNumber(const char *name, long lo, long hi) { char t[24] = ""; GetText((char *)name, t, sizeof(t) - 1); long v = strtol(t, nullptr, 10); return v < lo ? lo : v > hi ? hi : v; }
// ---- the pipe and a fake flight controller
static int PipeReqId = 0, PipeRepId = -1, PipeRepCode = 0; static char PipeRepBody[1600] = ""; static uint32_t PipeReqSentMs = 0;
bool PipeReplyReady(int id) { return PipeRepId == id; }
bool PipeReplyLate() { return false; }
int PipeReplyBytes(uint8_t *out, int max) { int n = 0; const char *p = PipeRepBody; while (p[0] && p[1] && n < max) { char h[3] = {p[0], p[1], 0}; out[n++] = (uint8_t) strtol(h, nullptr, 16); p += 2; } return n; }
struct FcReq { int fn; std::string data; };
static std::vector<FcReq> fcLog;
static std::string hexOf(const uint8_t *d, int n) { char b[4]; std::string s; for (int i = 0; i < n; ++i) { snprintf(b, sizeof b, "%02X", d[i]); s += b; } return s; }
static uint8_t mix[21], mot[29], esc[14]; static bool escMissing = false; static int rebootLeft = 0, reboots = 0, rebootLen = 2;
static void fcReply(int code, const std::string &body) { PipeRepCode = code; strncpy(PipeRepBody, body.c_str(), sizeof(PipeRepBody) - 1); PipeRepBody[sizeof(PipeRepBody) - 1] = 0; PipeRepId = PipeReqId; }
static unsigned u16(const uint8_t *b, int o) { return b[o] | (b[o + 1] << 8); }
static void w16(uint8_t *b, int o, unsigned v) { b[o] = v & 0xFF; b[o + 1] = v >> 8; }
int MspAsk(uint8_t fn, const uint8_t *data, int len) {
    ++PipeReqId; PipeReqSentMs = now; fcLog.push_back({fn, hexOf(data, len)});
    if (rebootLeft > 0) { --rebootLeft; fcReply(503, "the flight controller is restarting"); return PipeReqId; }
    switch (fn) {
    case 42: fcReply(200, hexOf(mix, 21)); return PipeReqId;
    case 43: memcpy(mix, data, 21); fcReply(200, ""); return PipeReqId;
    case 131: fcReply(200, hexOf(mot, 29)); return PipeReqId;
    case 222: memcpy(mot, data, 6); memcpy(mot + 7, data + 6, 22); fcReply(200, ""); return PipeReqId;   // (Rotorflight: the motor count is not written)
    case 123: if (escMissing) { fcReply(404, "unknown"); return PipeReqId; } fcReply(200, hexOf(esc, 14)); return PipeReqId;
    case 216: memcpy(esc, data, 14); fcReply(200, ""); return PipeReqId;
    case 250: fcReply(200, ""); return PipeReqId;
    case 68: ++reboots; rebootLeft = rebootLen; fcReply(200, ""); return PipeReqId;   // (rebootLen requests fall into the restart)
    }
    fcReply(404, "unknown"); return PipeReqId;
}
''' + open(HDR).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void run(int n = 40) { for (int i = 0; i < n; ++i) { BasicsPoll(); now += 250; } }   // (10 s: through the restart's waits)
static int writes(int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; }
static std::string lastData(int fn) { for (int i = (int) fcLog.size() - 1; i >= 0; --i) if (fcLog[i].fn == fn) return fcLog[i].data; return "?"; }
static bool cmd(const char *c) { for (auto &x : cmds) if (x == c) return true; return false; }
static void fakeFc() {
    memset(mix, 0, sizeof mix); mix[5] = 2; w16(mix, 9, 1500);                       // CCPM 120, clockwise, variable-pitch tail
    memset(mot, 0, sizeof mot); w16(mot, 0, 1070); w16(mot, 2, 2000); w16(mot, 4, 1000); mot[6] = 1; mot[7] = 10; mot[9] = 0; w16(mot, 10, 250);
    mot[13] = 10; mot[14] = mot[15] = mot[16] = 10; w16(mot, 21, 10); w16(mot, 23, 102); w16(mot, 25, 19); w16(mot, 27, 85);
    memset(esc, 0, sizeof esc); esc[0] = 4; esc[1] = 1; w16(esc, 2, 50);              // Scorpion, half duplex
}
int main() {
    fakeFc();
    // ---- 1. from the settings page: its fields gathered, the three reads, the page
    CurrentView = RFSETUPVIEW; StartBasicsView();
    CHECK(gathers == 1 && CurrentView == BASICSVIEW && cmd("page BasicsView") && fields["t9"] == "All banks"); run();
    CHECK(BasHave && BasEscHave && writes(42) == 1 && writes(131) == 1 && writes(123) == 1 && cmd("vis b3,0"));
    CHECK(fields["tn0"] == "CCPM 120 deg" && fields["tn1"] == "Clockwise" && fields["tn2"] == "Variable pitch" && fields["tn3"] == "PWM (most heli ESCs)" && fields["tn4"] == "Scorpion" && fields["tn5"] == "10");
    // ---- 2. the choices step round; the typed pole count is left alone by a tap
    fields["tn5"] = "14"; cmds.clear();
    BasicsSwashTapped(); CHECK(fields["tn0"] == "CCPM 135 deg" && BasMixWant[5] == 3 && Bas_Was_Edited && cmd("vis b3,1") && fields["tn5"] == "14");
    for (int i = 0; i < 6; ++i) BasicsSwashTapped(); CHECK(fields["tn0"] == "CCPM 120 deg" && BasMixWant[5] == 2);   // (round once: back where it was)
    BasicsDirectionTapped(); CHECK(fields["tn1"] == "Anticlockwise" && BasMixWant[0] == 1);
    BasicsTailTapped(); CHECK(fields["tn2"] == "Motorised" && BasMixWant[1] == 1); BasicsTailTapped(); BasicsTailTapped(); CHECK(fields["tn2"] == "Variable pitch");
    BasicsProtocolTapped(); CHECK(fields["tn3"] == "OneShot125" && BasMotWant[9] == 1);
    BasicsProtocolTapped(); CHECK(fields["tn3"] == "DShot150" && BasMotWant[9] == 5);
    for (int i = 0; i < 4; ++i) BasicsProtocolTapped(); CHECK(fields["tn3"] == "PWM (most heli ESCs)" && BasMotWant[9] == 0);   // 6 -> 7 -> 10 (Off) -> 0
    BasMotWant[9] = 3; BasShowProtocol(); CHECK(fields["tn3"] == "Protocol 3"); BasicsProtocolTapped(); CHECK(BasMotWant[9] == 0 && fields["tn3"] == "PWM (most heli ESCs)");
    BasicsEscTapped(); CHECK(fields["tn4"] == "Kontronik" && BasEscWant[0] == 5);
    // ---- 3. Next >: the pole count gathered (13 -> 12: magnets come in pairs); page 2 shows the ratios
    fields["tn5"] = "13"; cmds.clear(); StartBasics2View();
    CHECK(CurrentView == BASICS2VIEW && cmd("page Basics2View") && BasMotWant[13] == 12 && fields["tn0"] == "10" && fields["tn1"] == "102" && fields["tn2"] == "19" && fields["tn3"] == "85");
    // the ratios typed as turns with a decimal, and as teeth
    fields["tn0"] = "1"; fields["tn1"] = "10.2"; fields["tn2"] = "25"; fields["tn3"] = "123"; BasGather();
    CHECK(u16(BasMotWant, 21) == 10 && u16(BasMotWant, 23) == 102 && u16(BasMotWant, 25) == 25 && u16(BasMotWant, 27) == 123);
    fields["tn0"] = "399"; fields["tn1"] = "4080"; BasGather(); CHECK(u16(BasMotWant, 21) == 399 && u16(BasMotWant, 23) == 4080);
    fields["tn0"] = "0"; fields["tn1"] = "0"; BasGather(); CHECK(u16(BasMotWant, 21) == 1 && u16(BasMotWant, 23) == 1);   // (nothing typed: 1 : 1, as Rotorflight treats a zero)
    fields["tn0"] = "399"; fields["tn1"] = "4080"; BasGather();
    // ---- 4. the save: 43, the 28-byte 222, 216, 250, 68; the restart ridden out (two 503s), everything read back
    fcLog.clear(); asked = 0; sounds = 0; SaveBasics();
    CHECK(asked == 1 && lastBox.find("restarts") != std::string::npos && BasStep == BAS_WRITE_MIX && fields["busy"] == "Writing to the flight controller ...");
    run(60);   // (15 s: the writes, the 5-s wait, two 2.5-s waits, the read-back)
    CHECK(writes(43) == 1 && writes(222) == 1 && writes(216) == 1 && writes(250) == 1 && writes(68) == 1 && reboots == 1);
    { const std::string d = lastData(222); CHECK(d.size() == 56 && d.substr(0, 12) == "2E04D007E803" && d.substr(12, 2) == "0A" && d.substr(16, 2) == "00" && d.substr(24, 2) == "0C" && d.substr(40, 16) == "8F01F00F19007B00"); }
    CHECK(lastData(43).size() == 42 && lastData(43).substr(0, 2) == "01" && lastData(43).substr(10, 2) == "02" && lastData(216).substr(0, 2) == "05");
    CHECK(mix[0] == 1 && mot[13] == 12 && mot[6] == 1 && u16(mot, 21) == 399 && u16(mot, 23) == 4080 && esc[0] == 5);   // (the fake FC has it; its motor count untouched)
    CHECK(writes(42) == 3 && writes(131) == 1 && writes(123) == 1);   // (42: the two that fell into the restart, then the one that answered)
    CHECK(BasStep == BAS_IDLE && !Bas_Was_Edited && fields["busy"] == "Saved, and read back the same." && sounds == 1 && cmd("vis b3,0"));
    run(); CHECK(fields["busy"] == "Saved, and read back the same." && fields["tn0"] == "399");   // (the 4-s message gone, the page shown again)
    // a restart that never comes back: five tries, then said
    fcLog.clear(); boxes = 0; rebootLen = 100; BasicsSwashTapped(); SaveBasics(); run(120); rebootLen = 2; rebootLeft = 0;
    CHECK(boxes == 1 && lastBox.find("has not come back") != std::string::npos && BasStep == BAS_IDLE && writes(42) == 5);
    // ---- 5. a backwards main ratio: warned, and not written when refused
    CurrentView = BASICS2VIEW; fields["tn0"] = "102"; fields["tn1"] = "10"; fields["tn2"] = "25"; fields["tn3"] = "123"; BasicsWasEdited();
    fcLog.clear(); confirmAnswer = false; asked = 0; SaveBasics();
    CHECK(asked == 1 && lastBox.find("backwards") != std::string::npos && lastBox.find("rotor 102 : motor 10") != std::string::npos && fcLog.empty() && Bas_Was_Edited);
    confirmAnswer = true;
    // ---- 6. offline: the backup is written, nothing restarts
    fields["tn0"] = "10"; fields["tn1"] = "102"; offline = true; fcLog.clear(); reboots = 0; SaveBasics();
    CHECK(lastBox.find("backup") != std::string::npos); run();
    CHECK(writes(43) == 1 && writes(222) == 1 && writes(216) == 1 && writes(250) == 1 && writes(68) == 0 && reboots == 0 && writes(42) == 1 && fields["busy"] == "Saved, and read back the same.");
    offline = false;
    // ---- 7. OK with an edit: asked; kept when refused, the menu when agreed
    BasicsDirectionTapped(); confirmAnswer = false; asked = 0; rfStarts = 0; EndBasicsView(); CHECK(asked == 1 && lastBox.find("Discard") != std::string::npos && CurrentView == BASICS2VIEW && rfStarts == 0);
    confirmAnswer = true; EndBasicsView(); CHECK(rfStarts == 1 && CurrentView == ROTORFLIGHTVIEW && !Bas_Was_Edited);
    // ---- 8. < Previous shows page 1 again with the values as edited; a flight controller without ESC telemetry
    fakeFc(); escMissing = true; CurrentView = RFSETUPVIEW; fcLog.clear(); StartBasicsView(); run();
    CHECK(BasHave && !BasEscHave && fields["tn4"] == "?"); BasicsEscTapped(); CHECK(!Bas_Was_Edited);
    StartBasics2View(); EndBasics2View(); CHECK(CurrentView == BASICSVIEW && fields["tn0"] == "CCPM 120 deg");
    BasicsSwashTapped(); fcLog.clear(); SaveBasics(); run(60); CHECK(writes(43) == 1 && writes(222) == 1 && writes(216) == 0 && writes(68) == 1 && fields["busy"] == "Saved, and read back the same.");
    escMissing = false;
    // ---- 9. refused while armed: nothing read, the settings page kept
    armed = true; boxes = 0; CurrentView = RFSETUPVIEW; fcLog.clear(); StartBasicsView(); CHECK(boxes == 1 && lastBox == "Model is armed" && CurrentView == RFSETUPVIEW && fcLog.empty()); armed = false;
    printf("test_basics: %d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-const-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit(1)
if r.stderr.strip(): print(r.stderr[:3000])
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
