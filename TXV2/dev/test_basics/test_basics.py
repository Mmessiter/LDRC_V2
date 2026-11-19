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
#ifndef B211_HOST_STUBS   // (B211, Nextion.h / Utilities.h: NO ANSWER IS NOT A NUMBER; A PAGE'S FIELDS ARE TAKEN WHOLE - dev/test_noanswer and dev/test_wholepage are their tests)
#define B211_HOST_STUBS
#include <cstring>
#include <cstdint>
#include <cstddef>
uint32_t BoxesLost = 0;
uint32_t BoxesLostAtWork = 0; static bool WorkLostABox() { return BoxesLost != BoxesLostAtWork; }
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
#define RFSETUPVIEW 61
#define BASICSVIEW 77
#define BASICS2VIEW 78
#define PORTSVIEW 79
#define ESCCALVIEW 80
#include <cctype>
static int ecalStops = 0; void EscCalStop() { ++ecalStops; }
static int CurrentView = 0;
static bool offline = false, armed = false;
static char ModelName[20] = "Havoc";
static uint32_t now = 1000;
static uint32_t millis() { return now; }
static std::map<std::string, std::string> fields; static std::vector<std::string> cmds; static int boxes = 0; static std::string lastBox; static bool confirmAnswer = true; static int sounds = 0, rfStarts = 0, asked = 0, gathers = 0;
static void SendCommand(char *c) { cmds.push_back(c); }
static void SendText(char *n, char *t) { fields[n] = t; }
static bool RfLeaveAfterSave = false; static int RfLeaveView = -1; static void (*RfLeaveFn)() = nullptr;
#define FRONTVIEW_FOR_TEST 1
static bool overtakeNextBox = false;   // (the fifteenth review: another page - the front page - is put up over the box while it waits; Utilities.h says so in QuestionOvertaken)
static int overtakeBoxNo = 0;           // ... or the box of this number (counted from 1) is overtaken by ANOTHER BOX from inside its wait: this board's view stays what it was
static std::vector<std::string> boxPages;   // (each box's way back)
static void MsgBox(char *page, const char *msg) { ++boxes; lastBox = msg; boxPages.push_back(page); RfLeaveAfterSave = false; QuestionOvertaken = overtakeNextBox || boxes == overtakeBoxNo; if (overtakeNextBox) { overtakeNextBox = false; CurrentView = FRONTVIEW_FOR_TEST; } }   // (B102: as Utilities.h)
static bool RfHomeNotRead = false; static bool rfMayFlyNow = false; static int quietSaid = 0;   // (B211, the sixteenth review: PipeHttp.h RfMayFly / RfSayQuietly / RfBoxOrQuiet stood in for - no box that waits while the model may fly)
static std::string lastQuiet; static bool RfMayFly() { return rfMayFlyNow; } static void RfSayQuietly(const char *w) { ++quietSaid; lastQuiet = w; }
static void RfBoxOrQuiet(const char *page, const char *msg) { if (RfMayFly()) { RfLeaveAfterSave = false; RfSayQuietly(msg); return; } MsgBox((char *)page, (char *)msg); }
static bool GetConfirmation(char *page, char *prompt) { ++asked; lastBox = prompt; if (!confirmAnswer) RfLeaveAfterSave = false; return confirmAnswer; }   // (B102: a No keeps the page, as Utilities.h)
static void PlaySound(int) { ++sounds; }
static bool menuShut = false, menuSaysWhy = false;   // (RF_RotorFlight.h: the motor switch on - the menu will not open: without a word while the model is connected, else with its own box)
static void MsgBox(char *page, const char *msg);
static bool homeNotReadAtMenu = false;
static void RotorFlightStart() { homeNotReadAtMenu = RfHomeNotRead; if (menuShut) { if (menuSaysWhy) MsgBox((char *) "page RXSetupView", "The motor is ON.\r\nSwitch it off first."); return; } ++rfStarts; CurrentView = ROTORFLIGHTVIEW; }
static bool RFSettingsGather() { ++gathers; return true; }
static bool ModelSeemsArmed(char *why, size_t n) { if (!armed) return false; snprintf(why, n, "Model is armed"); return true; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static bool RfNeedsModel(char *, size_t) { return false; }
static bool BakOffline() { return offline; }
static void GetText(char *n, char *out, int len) { snprintf(out, len, "%s", fields[n].c_str()); }
bool NextionTextMissed = false; static bool RfFieldsMissed(const char *) { if (!NextionTextMissed) return false; NextionTextMissed = false; return true; }   // (B152)
char NextionMissedBox[12] = {0}; bool NextionSettledOk = false, NextionMissedNoNumber = false; static void RfGatherStart() { NextionTextMissed = false; }   // (B187)
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
static uint8_t ports[6 * 9]; static int portsN = 6; static bool portsMissing = false; static uint32_t feat = (1u << 3) | (1u << 26) | (1u << 29) | (1u << 30);
static uint8_t board[48]; static int boardLen = 0;
static void fcReply(int code, const std::string &body) { PipeRepCode = code; strncpy(PipeRepBody, body.c_str(), sizeof(PipeRepBody) - 1); PipeRepBody[sizeof(PipeRepBody) - 1] = 0; PipeRepId = PipeReqId; }
static unsigned u16(const uint8_t *b, int o) { return b[o] | (b[o + 1] << 8); }
static void w16(uint8_t *b, int o, unsigned v) { b[o] = v & 0xFF; b[o + 1] = v >> 8; }
static int fail42 = 0, fail43 = 0, failWrite = 0;   // (failWrite: the request of this number is refused - a save that fails at that step)
int MspAsk(uint8_t fn, const uint8_t *data, int len) {
    ++PipeReqId; PipeReqSentMs = now; fcLog.push_back({fn, hexOf(data, len)});
    if (failWrite && fn == failWrite) { fcReply(503, "the receiver did not answer"); return PipeReqId; }
    if (rebootLeft > 0) { --rebootLeft; fcReply(503, "the flight controller is restarting"); return PipeReqId; }
    switch (fn) {
    case 42: if (fail42 > 0) { --fail42; fcReply(503, "the receiver did not answer"); return PipeReqId; } fcReply(200, hexOf(mix, 21)); return PipeReqId;   // (the fifteenth review: a read that FAILS)
    case 43: if (fail43 > 0) { --fail43; fcReply(503, "the receiver did not answer"); return PipeReqId; } memcpy(mix, data, 21); fcReply(200, ""); return PipeReqId;
    case 131: fcReply(200, hexOf(mot, 29)); return PipeReqId;
    case 222: memcpy(mot, data, 6); memcpy(mot + 7, data + 6, 22); fcReply(200, ""); return PipeReqId;   // (Rotorflight: the motor count is not written)
    case 123: if (escMissing) { fcReply(404, "unknown"); return PipeReqId; } fcReply(200, hexOf(esc, 14)); return PipeReqId;
    case 216: memcpy(esc, data, 14); fcReply(200, ""); return PipeReqId;
    case 250: fcReply(200, ""); return PipeReqId;
    case 68: ++reboots; rebootLeft = rebootLen; fcReply(200, ""); return PipeReqId;   // (rebootLen requests fall into the restart)
    case 4: fcReply(200, hexOf(board, boardLen)); return PipeReqId;
    case 54: if (portsMissing) { fcReply(404, "unknown"); return PipeReqId; } fcReply(200, hexOf(ports, portsN * 9)); return PipeReqId;
    case 55: for (int o = 0; o + 9 <= len; o += 9) for (int k = 0; k < portsN; ++k) if (ports[k * 9] == data[o]) memcpy(ports + k * 9, data + o, 9); fcReply(200, ""); return PipeReqId;
    case 36: { uint8_t b[4] = {(uint8_t)feat, (uint8_t)(feat >> 8), (uint8_t)(feat >> 16), (uint8_t)(feat >> 24)}; fcReply(200, hexOf(b, 4)); return PipeReqId; }
    case 37: feat = (uint32_t)data[0] | ((uint32_t)data[1] << 8) | ((uint32_t)data[2] << 16) | ((uint32_t)data[3] << 24); fcReply(200, ""); return PipeReqId;
    }
    fcReply(404, "unknown"); return PipeReqId;
}
// B102: OK's "Save now?" - the real RfSaveFirst / RfSavedThenLeave (include/RF_SaveNow.h) over a fake question: Discard
// unless saveNowAnswer is 1; and the bank check (PipeHttp.h BankCheck) as without a pipe: the write goes
static int saveNowAnswer = 0, saveNowAsked = 0;
static bool GetSaveOrDiscard(char *, char *prompt) { ++saveNowAsked; lastBox = prompt; return saveNowAnswer == 1; }
static inline void BankCheck(bool, int, void (*then)(), const char *) { then(); }
''' + open(os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_SaveNow.h')).read() + r'''
''' + open(HDR).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void run(int n = 40) { for (int i = 0; i < n; ++i) { BasicsPoll(); now += 250; } }   // (10 s: through the restart's waits)
static int writes(int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; }
static std::string lastData(int fn) { for (int i = (int) fcLog.size() - 1; i >= 0; --i) if (fcLog[i].fn == fn) return fcLog[i].data; return "?"; }
static bool cmd(const char *c) { for (auto &x : cmds) if (x == c) return true; return false; }
static int cmdCount(const char *c) { int k = 0; for (auto &x : cmds) k += x == c; return k; }
static void fakeFc() {
    memset(mix, 0, sizeof mix); mix[5] = 2; w16(mix, 9, 1500);                       // CCPM 120, clockwise, variable-pitch tail
    memset(mot, 0, sizeof mot); w16(mot, 0, 1070); w16(mot, 2, 2000); w16(mot, 4, 1000); mot[6] = 1; mot[7] = 10; mot[9] = 0; w16(mot, 10, 250);
    mot[13] = 10; mot[14] = mot[15] = mot[16] = 10; w16(mot, 21, 10); w16(mot, 23, 102); w16(mot, 25, 19); w16(mot, 27, 85);
    memset(esc, 0, sizeof esc); esc[0] = 4; esc[1] = 1; w16(esc, 2, 50);              // Scorpion, half duplex
    // the board: "RDMS", revision, type, capabilities, target "NEXUS_X" (7), board "NEXUS_X" (7)
    memcpy(board, "RDMS", 4); board[4] = 1; board[5] = 0; board[6] = 2; board[7] = 0; board[8] = 7; memcpy(board + 9, "NEXUS_X", 7); board[16] = 7; memcpy(board + 17, "NEXUS_X", 7); boardLen = 24;
    // six ports: UART1 the receiver, UART2 ESC telemetry, UART3 and UART4 nothing, UART6 the dongle (MSP at 115200), the USB socket MSP
    memset(ports, 0, sizeof ports);
    const uint8_t ids[6] = {0, 1, 2, 3, 5, 20}; const uint32_t masks[6] = {64, 1024, 0, 0, 1, 1};
    for (int k = 0; k < 6; ++k) { uint8_t *p = ports + k * 9; p[0] = ids[k]; p[1] = masks[k] & 255; p[2] = (masks[k] >> 8) & 255; p[5] = k == 4 || k == 5 ? 5 : 0; p[6] = 1; p[7] = 1; p[8] = 5; }
    portsN = 6; portsMissing = false; feat = (1u << 3) | (1u << 26) | (1u << 29) | (1u << 30);
}
static uint32_t pmask(int k) { const uint8_t *p = ports + k * 9; return (uint32_t)p[1] | ((uint32_t)p[2] << 8) | ((uint32_t)p[3] << 16) | ((uint32_t)p[4] << 24); }
int main() {
    fakeFc();
    // ---- 1. from the settings page: its fields gathered, the three reads, the page
    CurrentView = RFSETUPVIEW; StartBasicsView();
    CHECK(gathers == 1 && CurrentView == BASICSVIEW && cmd("page BasicsView") && fields["t9"] == "All banks"); run();
    CHECK(BasHave && BasEscHave && writes(42) == 1 && writes(131) == 1 && writes(123) == 1 && writes(4) == 1 && writes(54) == 1 && cmd("vis b3,0"));
    CHECK(BasPortsHave && BasPortsN == 6 && !strcmp(BasBoard, "NEXUS_X"));
    CHECK(fields["tn0"] == "CCPM 120 deg" && fields["tn1"] == "Clockwise" && fields["tn2"] == "Variable pitch" && fields["tn3"] == "Normal PWM (most heli ESCs)" && fields["tn4"] == "Scorpion" && fields["tn5"] == "10");
    // ---- 2. the choices step round; the typed pole count is left alone by a tap
    fields["tn5"] = "14"; cmds.clear();
    BasicsSwashTapped(); CHECK(fields["tn0"] == "CCPM 135 deg" && BasMixWant[5] == 3 && Bas_Was_Edited && cmd("vis b3,1") && fields["tn5"] == "14");
    for (int i = 0; i < 6; ++i) BasicsSwashTapped(); CHECK(fields["tn0"] == "CCPM 120 deg" && BasMixWant[5] == 2);   // (round once: back where it was)
    BasicsDirectionTapped(); CHECK(fields["tn1"] == "Anticlockwise" && BasMixWant[0] == 1);
    BasicsTailTapped(); CHECK(fields["tn2"] == "Motorised" && BasMixWant[1] == 1); BasicsTailTapped(); BasicsTailTapped(); CHECK(fields["tn2"] == "Variable pitch");
    BasicsProtocolTapped(); CHECK(fields["tn3"] == "OneShot125" && BasMotWant[9] == 1);
    BasicsProtocolTapped(); CHECK(fields["tn3"] == "DShot150" && BasMotWant[9] == 5);
    for (int i = 0; i < 4; ++i) BasicsProtocolTapped(); CHECK(fields["tn3"] == "Normal PWM (most heli ESCs)" && BasMotWant[9] == 0);   // 6 -> 7 -> 10 (Off) -> 0
    BasMotWant[9] = 3; BasShowProtocol(); CHECK(fields["tn3"] == "Protocol 3"); BasicsProtocolTapped(); CHECK(BasMotWant[9] == 0 && fields["tn3"] == "Normal PWM (most heli ESCs)");
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
    // ---- 7. OK with an edit (B102): "Save now?" - Save saves and the page closes once it has; a No to the save's own question
    // keeps the page and its edit; Discard leaves without writing
    BasicsDirectionTapped(); saveNowAnswer = 1; confirmAnswer = false; saveNowAsked = 0; asked = 0; rfStarts = 0; fcLog.clear(); EndBasicsView();
    CHECK(saveNowAsked == 1 && asked == 1 && CurrentView == BASICS2VIEW && rfStarts == 0 && Bas_Was_Edited && !RfLeaveAfterSave && writes(43) == 0);
    confirmAnswer = true; EndBasicsView(); CHECK(saveNowAsked == 2 && rfStarts == 0 && RfLeaveAfterSave); run(120);   // (the restart and its waits)
    CHECK(writes(43) == 1 && rfStarts == 1 && CurrentView == ROTORFLIGHTVIEW && !Bas_Was_Edited && !RfLeaveAfterSave);
    CurrentView = BASICS2VIEW; BasicsDirectionTapped(); saveNowAnswer = 0; fcLog.clear(); rfStarts = 0; EndBasicsView();
    CHECK(saveNowAsked == 3 && rfStarts == 1 && CurrentView == ROTORFLIGHTVIEW && !Bas_Was_Edited && fcLog.empty());
    // ---- 8. < Previous shows page 1 again with the values as edited; a flight controller without ESC telemetry
    fakeFc(); escMissing = true; CurrentView = RFSETUPVIEW; fcLog.clear(); StartBasicsView(); run();
    CHECK(BasHave && !BasEscHave && fields["tn4"] == "?"); BasicsEscTapped(); CHECK(!Bas_Was_Edited);
    StartBasics2View(); EndBasics2View(); CHECK(CurrentView == BASICSVIEW && fields["tn0"] == "CCPM 120 deg");
    BasicsSwashTapped(); fcLog.clear(); SaveBasics(); run(60); CHECK(writes(43) == 1 && writes(222) == 1 && writes(216) == 0 && writes(68) == 1 && fields["busy"] == "Saved, and read back the same.");
    escMissing = false;
    // ---- 9. refused while armed: nothing read, the settings page kept
    armed = true; boxes = 0; CurrentView = RFSETUPVIEW; fcLog.clear(); StartBasicsView(); CHECK(boxes == 1 && lastBox == "Model is armed" && CurrentView == RFSETUPVIEW && fcLog.empty()); armed = false;
    // ---- 10. B100 the ports page: the rows named by the Nexus-X's sockets, the USB socket left out, the sixth row hidden
    fakeFc(); CurrentView = RFSETUPVIEW; StartBasicsView(); run(); CHECK(BasHave && BasPortsHave);
    StartBasics2View(); cmds.clear(); StartBasics3View();
    CHECK(CurrentView == PORTSVIEW && cmd("page PortsView") && fields["ltn0"] == "S.BUS (UART 1)" && fields["tn0"] == "Receiver" && fields["ltn1"] == "TELEM (UART 2)" && fields["tn1"] == "ESC telemetry");
    CHECK(fields["ltn2"] == "Port C (UART 3)" && fields["tn2"] == "Nothing" && fields["ltn3"] == "Port A (UART 4)" && fields["tn3"] == "Nothing" && fields["ltn4"] == "Port B (UART 6)" && fields["tn4"] == "Dongle on a wire (MSP)" && cmd("vis ltn5,0") && cmd("vis tn5,0"));
    // the receiver's port is locked; the others step round; a job the page does not know is told, and a tap takes it to None
    boxes = 0; BasicsPort1Tapped(); CHECK(boxes == 1 && lastBox.find("receiver's link") != std::string::npos && fields["tn0"] == "Receiver" && !BasPortsEdited && !Bas_Was_Edited);
    cmds.clear(); BasicsPort3Tapped(); CHECK(fields["tn2"] == "ESC telemetry" && BasPortsEdited && Bas_Was_Edited && cmd("vis b3,1"));
    BasicsPort3Tapped(); CHECK(fields["tn2"] == "GPS");
    BasicsPort4Tapped(); BasicsPort4Tapped(); BasicsPort4Tapped(); CHECK(fields["tn3"] == "Dongle on a wire (MSP)" && BasPortsWant[3 * 9 + 5] == 5);
    for (int i = 0; i < 3; ++i) BasicsPort4Tapped(); CHECK(fields["tn3"] == "Nothing");   // S.Port, Blackbox, None
    BasPortsWant[2 * 9 + 1] = 33; BasPortsWant[2 * 9 + 2] = 0; BasShowPortRow(2); CHECK(fields["tn2"] == "As it is"); BasicsPort3Tapped(); CHECK(fields["tn2"] == "Nothing"); BasicsPort3Tapped(); CHECK(fields["tn2"] == "ESC telemetry");
    // the save: 55 with all six ports, the features gaining ESC telemetry (27) and TELEMETRY (10), the restart, 54 read back
    fcLog.clear(); asked = 0; SaveBasics(); CHECK(asked == 1 && lastBox.find("ports") != std::string::npos); run(60);
    CHECK(writes(55) == 1 && lastData(55).size() == 108 && writes(36) == 2 && writes(37) == 1 && writes(250) == 1 && writes(68) == 1 && writes(54) == 1 && pmask(2) == 1024 && pmask(0) == 64 && pmask(5) == 1);   // (B165: 36 twice - before the write, and read back after the restart)
    CHECK(feat == ((1u << 3) | (1u << 26) | (1u << 29) | (1u << 30) | (1u << 27) | (1u << 10)) && !BasPortsEdited && !Bas_Was_Edited && fields["busy"] == "Saved, and read back the same." && fields["tn2"] == "ESC telemetry");
    // no feature write when nothing new is needed
    BasicsPort3Tapped(); BasicsPort3Tapped(); CHECK(fields["tn2"] == "Dongle on a wire (MSP)"); fcLog.clear(); SaveBasics(); run(60); CHECK(writes(55) == 1 && writes(36) == 1 && writes(37) == 0 && pmask(2) == 1);
    // offline: the ports page is refused (the backup keeps no ports)
    EndBasics3View(); CHECK(CurrentView == BASICS2VIEW); offline = true; boxes = 0; StartBasics3View(); CHECK(boxes == 1 && lastBox.find("need the model") != std::string::npos && CurrentView == BASICS2VIEW); offline = false;
    // a flight controller that answers no 54: the page says so
    fakeFc(); portsMissing = true; CurrentView = RFSETUPVIEW; StartBasicsView(); run(); CHECK(BasHave && !BasPortsHave); StartBasics2View(); StartBasics3View(); CHECK(fields["ltn0"] == "No ports read"); portsMissing = false;
    // OK from any page lets a throttle hold go first (RF_EscCal.h)
    ecalStops = 0; EndBasicsView(); CHECK(ecalStops == 1);
    // ---------------------------------------------------------------- B211 (the fifteenth review; reviewer B's experiments, adopted. Released code had it):
    // A READ THAT FAILS LEAVES NOTHING IN HAND, AND THE PAGE IS LEFT. BasHave was set by the first read that worked and never cleared: the page stayed
    // up with the block of the read BEFORE and Save open on it.
    // (1) MODEL A is read; MODEL B is connected in the same session and ITS read fails: he typed the pole count he came for and saved - model B's
    //     flight controller got A's swash type, rotor direction, tail type and gear ratio, "Saved, and read back the same."
    fakeFc(); strcpy(ModelName, "Model A"); CurrentView = RFSETUPVIEW; StartBasicsView(); CHECK(!BasHave);        // (nothing is in hand while the read runs)
    run(); CHECK(BasHave && fields["tn0"] == "CCPM 120 deg" && fields["tn5"] == "10"); EndBasicsView();
    strcpy(ModelName, "Other"); mix[5] = 4; mix[0] = 1; mix[1] = 1; mot[13] = 6; w16(mot, 21, 1); w16(mot, 23, 8);                        // model B: a 140-degree swash, anticlockwise, a motorised tail, 6 poles, 1 : 8
    boxes = 0; rfStarts = 0; fail42 = 1; fcLog.clear(); CurrentView = RFSETUPVIEW; StartBasicsView(); CHECK(!BasHave); run();
    CHECK(boxes == 1 && lastBox.find("Could not read the mixer") == 0 && !BasHave && BasStep == BAS_IDLE && rfStarts == 1 && CurrentView == ROTORFLIGHTVIEW);   // THE PAGE IS LEFT: its box, then the menu
    fields["tn5"] = "6"; confirmAnswer = true; fcLog.clear(); asked = 0; SaveBasics(); run(80);                                             // (a Save from anywhere: nothing is in hand - nothing asked, nothing written)
    CHECK(fcLog.empty() && asked == 0 && mix[5] == 4 && mix[0] == 1 && mix[1] == 1 && u16(mot, 21) == 1 && u16(mot, 23) == 8);
    BasicsSwashTapped(); BasicsDirectionTapped(); BasicsTailTapped(); CHECK(mix[5] == 4 && !Bas_Was_Edited);                                // (and no row turns: BasHave)
    // (2) THE SAME MODEL, an edit typed and DISCARDED (the gather in front of OK's question had put it in the block); the next visit's read fails
    fakeFc(); CurrentView = RFSETUPVIEW; StartBasicsView(); run(); CHECK(BasHave && fields["tn5"] == "10");
    fields["tn5"] = "14"; BasicsWasEdited(); saveNowAnswer = 0; EndBasicsView(); CHECK(CurrentView == ROTORFLIGHTVIEW && writes(222) == 0 && mot[13] == 10);
    boxes = 0; rfStarts = 0; fail42 = 1; fcLog.clear(); CurrentView = RFSETUPVIEW; StartBasicsView(); run();
    CHECK(boxes == 1 && !BasHave && rfStarts == 1 && CurrentView == ROTORFLIGHTVIEW);
    BasicsEscTapped(); confirmAnswer = true; fcLog.clear(); SaveBasics(); run(80); CHECK(fcLog.empty() && mot[13] == 10);                  // the discarded 14 is written by nothing
    // (3) THE MENU WILL NOT OPEN (the motor switch on): the page is put up again and SAYS that it was not read; nothing is in hand, Save writes nothing
    fakeFc(); menuShut = true; boxes = 0; rfStarts = 0; fail42 = 1; fcLog.clear(); cmds.clear(); CurrentView = RFSETUPVIEW; StartBasicsView(); run();
    CHECK(boxes == 1 && !BasHave && rfStarts == 0 && CurrentView == BASICSVIEW && cmd("page BasicsView") && fields["busy"] == "NOT READ. Safety on, motor off - then OK.");
    fields["tn5"] = "6"; BasicsWasEdited(); fcLog.clear(); SaveBasics(); run(80); CHECK(fcLog.empty() && mot[13] == 10);
    menuShut = false; Bas_Was_Edited = false;
    // (4) a box that another page was put up over: neither the menu nor this page is put over that page
    fakeFc(); boxes = 0; rfStarts = 0; fail42 = 1; cmds.clear(); CurrentView = RFSETUPVIEW; StartBasicsView(); overtakeNextBox = true; run();
    CHECK(boxes == 1 && rfStarts == 0 && !BasHave && CurrentView == FRONTVIEW_FOR_TEST && cmdCount("page BasicsView") == 1);               // (the one page command is StartBasicsView's own)
    QuestionOvertaken = false;
    // (4b) THE BOX BEHIND A FAILED READ GOES BACK TO THE MENU - not to the page that could not be read (RfLeaveNotRead)
    fakeFc(); boxes = 0; boxPages.clear(); rfStarts = 0; fail42 = 1; CurrentView = RFSETUPVIEW; StartBasicsView(); run();
    CHECK(boxes == 1 && boxPages.size() == 1 && boxPages[0] == "page RFView" && rfStarts == 1 && CurrentView == ROTORFLIGHTVIEW);
    // (4c) THE MENU WILL NOT OPEN AND SAYS WHY (its own box, which goes back to the model's setup page): this page is put up again, saying NOT READ
    fakeFc(); menuShut = menuSaysWhy = true; boxes = 0; boxPages.clear(); rfStarts = 0; fail42 = 1; cmds.clear(); CurrentView = RFSETUPVIEW; StartBasicsView(); run();
    CHECK(boxes == 2 && boxPages[1] == "page RXSetupView" && !BasHave && rfStarts == 0 && CurrentView == BASICSVIEW && cmdCount("page BasicsView") == 2 && fields["busy"] == "NOT READ. Safety on, motor off - then OK.");
    // (4d) ... and when ANOTHER BOX came over that box (from inside its wait: this board's view is what it was), the page is NOT put up over it
    fakeFc(); boxes = 0; boxPages.clear(); rfStarts = 0; fail42 = 1; cmds.clear(); fields["busy"] = ""; overtakeBoxNo = 2; CurrentView = RFSETUPVIEW; StartBasicsView(); run();
    CHECK(boxes == 2 && !BasHave && rfStarts == 0 && CurrentView == BASICSVIEW && cmdCount("page BasicsView") == 1 && fields["busy"] != "NOT READ. Safety on, motor off - then OK.");
    overtakeBoxNo = 0; menuShut = menuSaysWhy = false; QuestionOvertaken = false;
    // (5) a SAVE that fails stays on the page (what was typed is kept: scene_save_fails) - only a read leaves it
    fakeFc(); CurrentView = RFSETUPVIEW; StartBasicsView(); run(); CHECK(BasHave);
    BasicsSwashTapped(); confirmAnswer = true; boxes = 0; rfStarts = 0; fail43 = 1; fcLog.clear(); SaveBasics(); run(80);
    CHECK(boxes == 1 && lastBox.find("Not written (mixer)") == 0 && BasHave && rfStarts == 0 && CurrentView == BASICSVIEW && Bas_Was_Edited);
    // B10 (the sixteenth review): NOTHING IN HAND - nothing is an edit (OK asked "Save now?" for it, the save returned at once), and a Save refused
    // for it does not leave "close when saved" standing for a later Save
    { const bool h = BasHave, e = Bas_Was_Edited; BasHave = false; Bas_Was_Edited = false; BasicsWasEdited(); CHECK(!Bas_Was_Edited);
      RfLeaveAfterSave = true; SaveBasics(); CHECK(!RfLeaveAfterSave);
      BasHave = true; BasicsWasEdited(); CHECK(Bas_Was_Edited); BasHave = h; Bas_Was_Edited = e; }
    // (the sixteenth review) A FAILED READ WHILE THE MODEL MAY FLY (the safety off): NO BOX THAT WAITS - a line for the log, the page stands under its line
    fakeFc(); menuShut = false; menuSaysWhy = false; rfMayFlyNow = true; quietSaid = 0; boxes = 0; rfStarts = 0; fail42 = 1; cmds.clear(); CurrentView = RFSETUPVIEW; StartBasicsView(); run();
    CHECK(boxes == 0 && quietSaid == 1 && !BasHave && rfStarts == 0 && CurrentView == BASICSVIEW && fields["busy"] == "NOT READ. Safety on, motor off - then OK.");
    rfMayFlyNow = false;
    //     ... and on the bench the menu's opening is told "this page could not be read" for its length only (RF_Tools.h: the guide does not tick the step)
    fakeFc(); boxes = 0; rfStarts = 0; fail42 = 1; homeNotReadAtMenu = false; CurrentView = RFSETUPVIEW; StartBasicsView(); run();
    CHECK(boxes == 1 && rfStarts == 1 && homeNotReadAtMenu && !RfHomeNotRead);
    //     a SAVE'S failure while the model may fly: no box either, the page keeps its edits
    fakeFc(); CurrentView = RFSETUPVIEW; StartBasicsView(); run(); CHECK(BasHave);
    BasicsDirectionTapped(); confirmAnswer = true; failWrite = 222; rfMayFlyNow = true; quietSaid = 0; boxes = 0; lastQuiet.clear(); SaveBasics(); run(80);
    CHECK(boxes == 0 && quietSaid == 1 && Bas_Was_Edited && BasStep == BAS_IDLE);
    CHECK(lastQuiet.find("PART WRITTEN, NOT STORED (motor & ESC failed) - try again, or switch the model off and on") == 0);   // (THE WORDS SAY WHAT STANDS IN THE FLIGHT CONTROLLER: the mixer block is written - it said "Not written")
    rfMayFlyNow = false; failWrite = 0;
    //     ... and on the bench the same failure is a box, with the same words; the first write refused is still "Not written"
    fakeFc(); CurrentView = RFSETUPVIEW; StartBasicsView(); run(); BasicsDirectionTapped(); confirmAnswer = true; failWrite = 250; boxes = 0; SaveBasics(); run(80);
    CHECK(boxes == 1 && lastBox.find("Written, but NOT STORED - try again, or switch the model off and on") == 0);
    fakeFc(); CurrentView = RFSETUPVIEW; StartBasicsView(); run(); BasicsDirectionTapped(); confirmAnswer = true; failWrite = 43; boxes = 0; SaveBasics(); run(80);
    CHECK(boxes == 1 && lastBox.find("Not written (mixer)") == 0);
    failWrite = 0;
    printf("test_basics: %d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-const-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit(1)
if r.stderr.strip(): print(r.stderr[:3000])
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
