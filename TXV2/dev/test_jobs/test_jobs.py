#!/usr/bin/env python3
"""Host test of the SWITCHES AND KNOBS page (B140): include/RF_Jobs.h over include/RF_Adjust.h and include/RF_Switches.h,
compiled on the Mac over a fake screen and a fake flight controller on the fake pipe, built with the sanitizers. One page
for both of Rotorflight's tables: the switch jobs (Modes, MSP 34/35) first, then the selectors and knobs (Adjustments, MSP
52/53); one picker; one Save (the switches, then the adjustments); OK's "Save now?". The scenarios of the two pages' own
tests before it (dev/test_adjust/test_adjust_page.py and dev/test_switches/test_switches.py, retired) ported to the one
page, plus what is new: the read without the USB cable (switch jobs only, said), Add through the picker, a job changing
kind, both tables saved in one go.
   python3 dev/test_jobs/test_jobs.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INC = os.path.join(ROOT, 'TransmitterCode', 'include')
def hdr(name): return open(os.path.join(INC, name)).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '')
RFMAP = (lambda d: d[d.index('// RFMAP-BEGIN'):d.index('// RFMAP-END')])(open(os.path.join(INC, '1Definitions.h'), encoding='utf-8', errors='replace').read())   # (B210: the channel map's block, the real one)
prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cmath>
#include <string>
#include <map>
#include <set>
#include <vector>
#include <algorithm>
#define DMAMEM
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
static bool NextionTextMissed = false;   // (B156: every box answers here; dev/test_missed_reply has the misses)
char NextionMissedBox[12] = {0}; bool NextionSettledOk = false, NextionMissedNoNumber = false; static void RfGatherStart() { NextionTextMissed = false; }   // (B187)
static bool RfFieldsMissed(const char *) { const bool m = NextionTextMissed; NextionTextMissed = false; return m; }
#define PROGMEM
#define WHAHWHAHMSG 1
#define BEEPCOMPLETE 2
#define ADJUSTVIEW 67
#define ADJPICKVIEW 68
#define SWITCHVIEW 69
#define SWITCHPICKVIEW 70
#define CHANNELSUSED 16
static int CurrentView = 0;
static bool BoundFlag = true, ModelMatched = true;
static char ModelName[20] = "Goblin";
static uint8_t ArmingChannel = 6, RotorFlight_V = 2;
static bool ArmingManaged() { return RotorFlight_V && ArmingChannel >= 1 && ArmingChannel <= 16; }   // (B209: as 1Definitions.h's ARMRULE)
''' + RFMAP + r'''
static char ChannelNames[16][11] = {{"Aileron"}, {"Elevator"}, {"Throttle"}, {"Rudder"}, {"Gear"}, {"AUX1"}, {"AUX2"}, {"AUX3"}, {"AUX4"}, {"AUX5"}, {"AUX6"}, {"AUX7"}, {"AUX8"}, {"AUX9"}, {"AUX10"}, {"AUX11"}};
static uint16_t SendBuffer[17] = {1500, 1500, 1000, 1500, 1500, 667, 1500, 1900, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 0};
static uint32_t now = 1000;
static uint32_t millis() { return now; }
// ---- this transmitter's outputs per bank (B83: the bank switch is matched to them). The curve is flat in each bank at its
// first point (CurvePoint, degrees: B141 - the real range, 500 to 2500 us or 945 to 2055, and the Teensy's rounding map,
// so what the flight controller sees of a height is what the transmitter would send); trims, subtrims and reversal are
// the real formulas with neutral values
#define BANKS_USED 6
#define CURVE_POINTS_MAX 9
#define CURVE_STORE_MAX 13
#define CURVE_UNSET 255
static uint8_t banksN = 4; static uint8_t BanksCount() { return banksN; }
static bool LinkRatesToBanks = false;
#define MINMICROS 500
#define MAXMICROS 2500
static uint8_t MaxRangeNarrow = 0;
static inline uint16_t RangeLo() { return MaxRangeNarrow ? 945 : MINMICROS; }
static inline uint16_t RangeHi() { return MaxRangeNarrow ? 2055 : MAXMICROS; }
static uint32_t ModelNumber = 1; static int modelSaves = 0; static void SaveOneModel(uint32_t) { ++modelSaves; }
static uint8_t CurvePoint[BANKS_USED + 1][CHANNELSUSED + 1][CURVE_POINTS_MAX], CurveStore[BANKS_USED + 1][CHANNELSUSED + 1][CURVE_STORE_MAX];
static int curveDeg[BANKS_USED + 1][16];   // (what CurveSetStraight last set flat, per bank and channel: -1 none)
static void CurveSetStraight(uint8_t b, uint8_t ch, uint8_t lo, uint8_t hi) { if (b > BANKS_USED || ch > CHANNELSUSED) return; for (int k = 0; k < CURVE_POINTS_MAX; ++k) CurvePoint[b][ch][k] = (uint8_t)(lo + ((hi - lo) * k + 2) / 4); memset(CurveStore[b][ch], CURVE_UNSET, CURVE_STORE_MAX); if (ch < 16) curveDeg[b][ch] = lo == hi ? lo : -1; }
static inline uint16_t CurveMicros(uint8_t d) { return (uint16_t)(RangeLo() + ((uint32_t)d * (RangeHi() - RangeLo()) + 90) / 180); }   // (the Teensy's map rounds)
static void setDeg(int b, int ch, int deg) { for (int k = 0; k < CURVE_POINTS_MAX; ++k) CurvePoint[b][ch][k] = (uint8_t)deg; }
static void twin(int ch) { for (int b = 5; b <= 6; ++b) memcpy(CurvePoint[b][ch], CurvePoint[4][ch], CURVE_POINTS_MAX); }   // (banks 5 and 6 bank 4's, as SixBanksSet makes them)
static uint8_t Bank = 2;
static uint16_t usOf(int b, int ch) { return CurveMicros(CurvePoint[b][ch][0]); }   // the transmitter's output on the channel in that bank
static uint8_t ChannelOutPut[17] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15};
static uint8_t SourceOfOutput(uint8_t out) { for (uint8_t k = 0; k < 16; ++k) if (ChannelOutPut[k] == out) return k; return out; }
static uint8_t DualRateValue = 100;
static uint8_t InterpolationTypes[BANKS_USED + 1][17] = {{0}};
static uint16_t InputsBuffer[17] = {0};
static uint8_t InPutStick[16] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15};
static uint8_t SubTrims[16] = {127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127};
static uint16_t ReversedChannelBITS = 0;
static int GetTrimAmount(uint8_t) { return 0; }
static void GetCurveDots(uint16_t, uint16_t) {}
static uint16_t stubInterp(uint16_t, uint16_t, uint16_t ch) { return Bank <= BANKS_USED && ch <= CHANNELSUSED ? usOf(Bank, ch) : 1500; }
uint16_t (*Interpolate[3])(uint16_t InputValue, uint16_t InputChannel, uint16_t OutputChannel) = {stubInterp, stubInterp, stubInterp};
// ---- the fake screen
static std::map<std::string, std::string> fields; static std::vector<std::string> cmds; static int boxes = 0; static std::string lastBox; static bool confirmAnswer = true; static int sounds = 0, rfStarts = 0;
static std::map<std::string, int> attrs;
static void SendCommand(char *c) { cmds.push_back(c); if (!strncmp(c, "bar.own=", 8)) attrs["bar.own"] = atoi(c + 8); }   // (the screen keeps the bar's token: any attribute written to its bar)
// (B211, the eleventh review: what RF_Jobs.h now uses of Nextion.h / Utilities.h)
static uint16_t ScreenMarkCount = 1; static uint16_t ScreenCountAfter(uint16_t c) { if (!c) return 4711; ++c; return c ? c : 1; }
static bool noPage = false; static bool BoxesHaveNoPage() { return noPage; }
static int boxesLostTold = 0; static void NoteBoxesLost() { ++boxesLostTold; }
static void SendText(char *n, char *t) { fields[n] = t; }
static void MsgBox(char *page, const char *msg) { ++boxes; lastBox = msg; }
static bool RfHomeNotRead = false; static bool rfMayFlyNow = false; static int quietSaid = 0;   // (B211, the sixteenth review: PipeHttp.h RfMayFly / RfSayQuietly / RfBoxOrQuiet stood in for - no box that waits while the model may fly)
static bool RfMayFly() { return rfMayFlyNow; } static void RfSayQuietly(const char *) { ++quietSaid; }
static void RfBoxOrQuiet(const char *page, const char *msg) { if (RfMayFly()) { RfSayQuietly(msg); return; } MsgBox((char *)page, (char *)msg); }
static bool GetConfirmation(char *page, char *prompt) { lastBox = prompt; return confirmAnswer; }
static void PlaySound(int) { ++sounds; }
static void RotorFlightStart() { ++rfStarts; CurrentView = 47; }
static bool ModelSeemsArmed(char *, int) { return false; }
static bool RfPipeBlocked(char *, int) { return false; }
static bool needModel = false; static bool RfNeedsModel(char *why, int n) { if (needModel) snprintf(why, n, "Switches and knobs need the model connected, or a backup on the card."); return needModel; }
static bool BakOffline() { return false; }
static std::set<std::string> fieldsLost;   // (the fields that have no answer just now: counted, as the real FieldNumber's GetText counts them)
static long FieldNumber(const char *name, long lo, long hi) { if (fieldsLost.count(name)) { ++BoxesLost; return lo; } long v = atol(fields[name].c_str()); return v < lo ? lo : v > hi ? hi : v; }
static std::set<std::string> attrsLost;   // (the bar's attributes that have no answer just now: 0 and counted, as the real GetOtherValue)
static int GetOtherValue(char *n) { if (attrsLost.count(n)) { ++BoxesLost; return 0; } return attrs.count(n) ? attrs[n] : 0; }
static std::map<std::string, int> vals; static void SendValue(char *n, int v) { vals[n] = v; } static uint32_t GetValue(char *n) { return (uint32_t) (vals.count(n) ? vals[n] : 0); }
static int cmdValue(const char *attr) { for (int i = (int) cmds.size() - 1; i >= 0; --i) { const std::string pre = std::string(attr) + "="; if (cmds[i].rfind(pre, 0) == 0) return atoi(cmds[i].c_str() + pre.size()); } return -9999; }
static bool cmdSeen(const char *c) { return std::find(cmds.begin(), cmds.end(), std::string(c)) != cmds.end(); }
// ---- the pipe and a fake flight controller: the modes (34/35) and the adjustments (52/53), the rates and PIDs for the present value
static int PipeReqId = 0, PipeRepId = -1, PipeRepCode = 0; static char PipeRepBody[1600] = ""; static uint32_t PipeReqSentMs = 0;
bool PipeReplyReady(int id) { return PipeRepId == id; }
bool PipeReplyLate() { return false; }
int PipeReplyBytes(uint8_t *out, int max) { int n = 0; const char *p = PipeRepBody; while (p[0] && p[1] && n < max) { char h[3] = {p[0], p[1], 0}; out[n++] = (uint8_t) strtol(h, nullptr, 16); p += 2; } return n; }
struct FcReq { int fn; std::string data; };
static std::vector<FcReq> fcLog;
static std::string hexOf(const uint8_t *d, int n) { char b[4]; std::string s; for (int i = 0; i < n; ++i) { snprintf(b, sizeof b, "%02X", d[i]); s += b; } return s; }
static uint8_t rcmap[8] = {0, 1, 3, 2, 4, 5, 6, 7};   // (B210) MSP 64: LDRC's helis, AECRT123 - AUX1 is channel 6
static uint8_t adj[588]; static uint8_t modes[80]; static bool usb = true; static int busyOnce = 0; static uint8_t pidImg[34], ratesImg[40]; static int pidBank = 1, rateBank = 0;
static void fcReply(int code, const std::string &body) { PipeRepCode = code; strncpy(PipeRepBody, body.c_str(), sizeof(PipeRepBody) - 1); PipeRepBody[sizeof(PipeRepBody) - 1] = 0; PipeRepId = PipeReqId; }
int MspAsk(uint8_t fn, const uint8_t *data, int len) {
    ++PipeReqId; PipeReqSentMs = now; fcLog.push_back({fn, hexOf(data, len)});
    if (busyOnce > 0) { --busyOnce; fcReply(503, "busy with a transmitter edit"); return PipeReqId; }
    if (fn == 34) { fcReply(200, hexOf(modes, 80)); return PipeReqId; }
    if (fn == 64) { fcReply(200, hexOf(rcmap, 8)); return PipeReqId; }   // (B210: the channel map)
    if (fn == 35 && len == 5) { const int i = data[0]; if (i < 20) memcpy(modes + i * 4, data + 1, 4); fcReply(200, ""); return PipeReqId; }
    if (fn == 52) { if (!usb) { fcReply(409, "refused: Rotorflight 4.6 cannot send its adjustments list over the receiver link ... Plug the flight controller's USB into the dongle or receiver"); return PipeReqId; } fcReply(200, hexOf(adj, 588)); return PipeReqId; }
    if (fn == 53 && len == 15) { const int i = data[0]; if (i < 42) memcpy(adj + i * 14, data + 1, 14); fcReply(200, ""); return PipeReqId; }
    if (fn == 250) { fcReply(200, ""); return PipeReqId; }
    if (fn == 111) { fcReply(200, hexOf(ratesImg, 40)); return PipeReqId; }
    if (fn == 112) { fcReply(200, hexOf(pidImg, 34)); return PipeReqId; }
    if (fn == 101) { uint8_t b[32] = {0}; b[23] = pidBank; b[25] = rateBank; fcReply(200, hexOf(b, 32)); return PipeReqId; }
    fcReply(404, "unknown"); return PipeReqId;
}
// B102: OK's "Save now?" - the real RfSaveFirst / RfSavedThenLeave over a fake question: Discard unless saveNowAnswer is 1
static bool RfLeaveAfterSave = false; static int RfLeaveView = -1; static void (*RfLeaveFn)() = nullptr;
static int saveNowAnswer = 0, saveNowAsked = 0; static bool loseAtQuestion = false;   // (loseAtQuestion: from the question on, the knob's two fields have no answer)
static bool GetSaveOrDiscard(char *, char *prompt) { ++saveNowAsked; lastBox = prompt; if (loseAtQuestion) { fieldsLost.insert("tk0"); fieldsLost.insert("tk1"); } return saveNowAnswer == 1; }
static inline void BankCheck(bool, int, void (*then)(), const char *) { then(); }
''' + hdr('RF_SaveNow.h') + r'''
''' + hdr('RF_Adjust.h') + r'''
''' + hdr('RF_Switches.h') + r'''
''' + hdr('RF_Jobs.h') + r'''
static void dump(const char *tag) { fprintf(stderr, "[%s] t0='%s' ltn0='%s' tn0='%s' tn1='%s' tn2='%s' tn3='%s' tn8='%s' bar='%s' busy='%s' hint='%.30s' kind=%d d0=%d d1=%d mk=%d | JobsStep=%d JobAt=%d SwStep=%d AdjStep=%d SwN=%d AdjN=%d AdjAt=%d SwAt=%d edited %d/%d now %d known %d boxes %d last='%.50s'\n", tag, fields["t0"].c_str(), fields["ltn0"].c_str(), fields["tn0"].c_str(), fields["tn1"].c_str(), fields["tn2"].c_str(), fields["tn3"].c_str(), fields["tn8"].c_str(), fields["bar"].c_str(), fields["busy"].c_str(), fields["hint"].c_str(), cmdValue("bar.kind"), cmdValue("bar.d0"), cmdValue("bar.d1"), cmdValue("bar.mk"), JobsStep, JobAt, SwStep, AdjStep_, SwN, AdjN, AdjAt, SwAt, (int)Sw_Was_Edited, (int)Adj_Was_Edited, (int)AdjNow, (int)AdjNowKnown, boxes, lastBox.c_str()); }
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static int liveCh = -1;   // a channel whose output follows its curve in the bank in use (reversed if the channel is), as CalculateAllOutputs makes it
static void live() { if (liveCh < 0) return; uint16_t v = usOf(Bank, liveCh); if (ReversedChannelBITS & (1 << liveCh)) v = (uint16_t)(MAXMICROS - (v - MINMICROS)); SendBuffer[liveCh] = v; }
static void run(int n = 20) { for (int i = 0; i < n; ++i) { live(); AdjustPoll(); SwitchPoll(); JobsPoll(); now += 50; } }
static void line0(size_t from, int &mn, int &mx);
static int writes(int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; }
static uint8_t stp(int us) { int st = (int) floorf((us - 1500) / 5.0f + 0.5f); return (uint8_t) (st < 0 ? st + 256 : st); }
static void putLine(int i, int fn, int ena, int enaLo, int enaHi, int ch, int a1Lo, int a1Hi, int a2Lo, int a2Hi, int mn, int mx, int st) {
    uint8_t *o = adj + i * 14; o[0] = fn; o[1] = ena; o[2] = stp(enaLo); o[3] = stp(enaHi); o[4] = ch; o[5] = stp(a1Lo); o[6] = stp(a1Hi); o[7] = stp(a2Lo); o[8] = stp(a2Hi); o[9] = mn & 255; o[10] = mn >> 8; o[11] = mx & 255; o[12] = mx >> 8; o[13] = st;
}
static void slot(int i, int perm, int aux, int lo, int hi) { modes[i * 4] = perm; modes[i * 4 + 1] = aux; modes[i * 4 + 2] = stp(lo); modes[i * 4 + 3] = stp(hi); }
static void blankAdj() { memset(adj, 0, sizeof adj); for (int i = 0; i < 42; ++i) putLine(i, 0, 0, 1500, 1500, 0, 1500, 1500, 1500, 1500, 0, 0, 0); }
static void blankModes() { for (int i = 0; i < 20; ++i) slot(i, 0, 0, 1500, 1500); }
static int pickFn(int fn) { return JobsPickIdxOfFn((uint8_t)fn); }
static int pickMode(int perm) { return JobsPickIdxOfMode((uint8_t)perm); }
static void line0(size_t from, int &mn, int &mx)   // (the first adjustment's line as written to the flight controller from fcLog[from] on: its two values; -1: not written)
{
    mn = mx = -1;
    for (size_t i = from; i < fcLog.size(); ++i) if (fcLog[i].fn == 53 && fcLog[i].data.size() >= 28 && fcLog[i].data.substr(0, 2) == "00")
    { const std::string &d = fcLog[i].data; mn = (int) strtol(d.substr(20, 2).c_str(), nullptr, 16) | ((int) strtol(d.substr(22, 2).c_str(), nullptr, 16) << 8); mx = (int) strtol(d.substr(24, 2).c_str(), nullptr, 16) | ((int) strtol(d.substr(26, 2).c_str(), nullptr, 16) << 8); }
}
int main() {
    memset(curveDeg, -1, sizeof curveDeg);
    blankAdj(); blankModes();
    // this transmitter: channel 6 (AUX1) carries the bank as a value, Black Thunder 2's way (a height of its own in each of
    // banks 1 to 4: 51, 72, 90 and 120 degrees = 1067, 1300, 1500, 1833 us); every other channel sits at 90 degrees (1500 us)
    // in every bank. B141: those four are off the middle of even zones, so the first read spaces the channel (step 2)
    for (int b = 0; b <= BANKS_USED; ++b) for (int c = 0; c <= CHANNELSUSED; ++c) setDeg(b, c, 90);
    setDeg(1, 5, 51); setDeg(2, 5, 72); setDeg(3, 5, 90); setDeg(4, 5, 120);
    const int fc1 = AdjFcUs(usOf(1, 5)), fc2 = AdjFcUs(1300), fc3 = AdjFcUs(1500), fc4 = AdjFcUs(usOf(4, 5));   // 1057, 1296, 1500, 1840
    CHECK(usOf(1, 5) == 1067 && usOf(2, 5) == 1300 && usOf(4, 5) == 1833 && fc1 == 1057 && fc2 == 1296 && fc3 == 1500 && fc4 == 1840);
    Bank = 2; SendBuffer[5] = 1300;
    // the flight controller's switch jobs: ARM on AUX1 (channel 6) ON above 1500, RESCUE on AUX3 (channel 8), BLACKBOX on AUX2 (the middle)
    slot(0, 0, 0, 1500, 2125); slot(1, 53, 2, 1700, 2125); slot(3, 26, 1, 1300, 1700);
    // and its adjustments: a PID-bank switch on AUX1 in the OLD form (3 lines, one per zone: applied once only), a Yaw P knob
    // on AUX3 in bank 2 (the old zone 2), a Pitch rate nudge
    putLine(0, 2, 0, 875, 1300, 0, 875, 1300, 1500, 1500, 1, 1, 0); putLine(1, 2, 0, 1300, 1700, 0, 1300, 1700, 1500, 1500, 2, 2, 0); putLine(2, 2, 0, 1700, 2125, 0, 1700, 2125, 1500, 1500, 3, 3, 0);
    putLine(3, 22, 0, 1300, 1700, 2, 1000, 2000, 1500, 1500, 60, 120, 0);
    putLine(4, 8, 4, 875, 2125, 4, 875, 1300, 1700, 2125, 20, 100, 2);
    ratesImg[0] = 6; for (int i = 1; i < 40; ++i) ratesImg[i] = i; ratesImg[7] = 48;   // Pitch Rate stored 48 -> shown 240
    for (int i = 0; i < 34; ++i) pidImg[i] = 0; pidImg[16] = 95; pidImg[8] = 55;       // Yaw P 95 (bytes 16-17), Pitch P 55 (bytes 8-9)
    // 1. open: the switches read first (34), then the rates type and the adjustments (111, 52); six jobs, the arm switch first
    StartJobsView(); CHECK(CurrentView == ADJUSTVIEW && fcLog.size() == 1 && fcLog[0].fn == 34 && fields["t9"] == "Bluetooth");
    run(6);
    CHECK(SwHave && AdjHave && SwN == 3 && AdjN == 3 && JobsN() == 6 && JobAt == 0 && writes(111) == 1 && writes(52) == 1);
    CHECK(fields["t0"] == "Job 1 of 6" && fields["ltn0"] == "Does" && fields["tn0"] == "Arm - motor enable (ARM)" && fields["tn1"] == "Channel 6: AUX1" && fields["tn2"] == "Switch" && cmdSeen("vis tn3,0") && fields["t9"] == "USB cable");
    CHECK(cmdValue("bar.kind") == 1 && cmdValue("bar.d0") == 1500 && cmdValue("bar.d1") == 2125 && cmdValue("bar.mk") == 1296 && fields["tn8"] == "OFF: 1296 us" && fields["bar"] == "|ON|" && fields["hint"].find("Arm switch:") == 0);   // (channel 6 sits at 1300 here, the bank value: OFF below 1500)
    // the old-form bank switch was put into Rotorflight's own form and matched to this transmitter's banks: said, Save offered
    CHECK(Adj_Was_Edited && fields["busy"] == "Press Save: 1 switch put right (old once-only form)." && cmdSeen("vis b3,1"));
    // the rescue: its switch is up (1900 us -> 1910 as the FC sees it): ON
    JobsNext(); run(2); CHECK(JobAt == 1 && SwAt == 1 && fields["t0"] == "Job 2 of 6" && fields["tn0"] == "Rescue - the safety net (RESCUE)" && fields["tn1"] == "Channel 8: AUX3" && fields["tn8"] == "ON: 1909 us" && cmdValue("bar.d0") == 1700);
    JobsNext(); run(2); CHECK(JobAt == 2 && fields["tn0"] == "Black box recording (BLACKBOX)" && fields["tn8"] == "ON: 1500 us");
    // 2. the fourth job: the bank selector, matched - B141: the channel's banks were off the middle of their zones (1057, 1296,
    // 1500, 1840 us as the flight controller sees them), so the first read set them in the middle: 988, 1330, 1670, 2012; the
    // card is not written until Save (step 3)
    cmds.clear(); JobsNext(); run(6);
    CHECK(JobAt == 3 && AdjAt == 0 && fields["t0"] == "Job 4 of 6" && fields["ltn0"] == "Changes" && fields["tn0"] == "Bank (Profile) selector" && fields["tn1"] == "Channel 6: AUX1" && fields["tn3"] == "in any bank");
    CHECK(fields["tn2"] == "Banks 1 to 4 of this transmitter" && AdjRows[0].legacy && AdjRows[0].kind == AK_SWITCH && AdjRows[0].n == 4 && AdjBankRowRight(AdjRows[0]) && AdjRows[0].lo % 5 == 0 && AdjRows[0].hi % 5 == 0);
    CHECK(AdjModelDirty && modelSaves == 0 && curveDeg[1][5] == 0 && curveDeg[2][5] == 75 && curveDeg[3][5] == 105 && curveDeg[4][5] == 180 && AdjFcUs(usOf(2, 5)) == 1330 && AdjFcUs(usOf(3, 5)) == 1670);
    CHECK(strcmp(AdjBankWhy, "Channel 6 set bank by bank: 988, 1330, 1670, 2012 us, the middle of each zone (0, 75, 105, 180 degrees).") == 0);
    const int bankLo = AdjRows[0].lo, bankHi = AdjRows[0].hi;
    fprintf(stderr, "   (the stub's banks %d, %d, %d, %d us, spaced to %d, %d, %d, %d: ends %d..%d)\n", fc1, fc2, fc3, fc4, AdjFcUs(usOf(1, 5)), AdjFcUs(usOf(2, 5)), AdjFcUs(usOf(3, 5)), AdjFcUs(usOf(4, 5)), bankLo, bankHi);
    { int vals[7]; for (int b = 1; b <= 4; ++b) vals[b] = AdjFcUs(usOf(b, 5)); vals[2] = fc2;   // (bank 2 as measured: the switch sits at 1300)
      CHECK(AdjBankRoom(bankLo, bankHi, 4, vals, 4) >= AdjRoomWanted(bankLo, bankHi, 4)); }
    CHECK(fields["tp0"] == "1" && fields["tp1"] == "2" && fields["tp2"] == "3" && fields["tp3"] == "4");
    CHECK(cmdSeen("vis tn3,0") && cmdValue("bar.kind") == 4 && cmdValue("bar.n") == 4 && cmdValue("bar.d0") == bankLo && cmdValue("bar.d1") == bankHi && fields["bar"] == "1|2|3|4" && cmdValue("bar.mk") == fc2);
    CHECK(fields["tn8"] == "Bank 2: 1296 us");
    // the knob in bank 2 - the old zone 2 (1300..1700) became the new bank 2 - with its present value read from the PIDs (bank 2 is the bank in use)
    cmds.clear(); JobsNext(); run(6);
    CHECK(cmdSeen("vis tn3,1") && JobAt == 4 && AdjAt == 1 && fields["tn0"] == "Yaw P gain" && fields["tn1"] == "Channel 8: AUX3" && fields["tn2"] == "Knob" && fields["tn3"] == "in bank 2" && fields["tk0"] == "60" && fields["tk1"] == "120");
    CHECK(cmdValue("bar.kind") == 1 && cmdValue("bar.d0") == 1000 && cmdValue("bar.d1") == 2000 && fields["bar"] == "|60 to 120|" && fields["tn8"] == "Knob 1909 us: 115" && AdjNowKnown && AdjNow == 95);   // (channel 8 sits at 1900: the rescue is up)
    // the nudge, a Rate shown x5; the last job: Next stays
    JobsNext(); run(6);
    CHECK(JobAt == 5 && AdjAt == 2 && fields["t0"] == "Job 6 of 6" && fields["tn0"] == "Pitch top rotation speed (Rate)" && fields["tn2"] == "Step adjustment" && fields["ts0"] == "2" && fields["ts1"] == "100" && fields["ts2"] == "500");
    CHECK(cmdValue("bar.kind") == 2 && fields["bar"] == "down 2|100 to 500|up 2" && fields["tn8"] == "Holding: 1500 us" && AdjNow == 240);
    JobsNext(); run(2); CHECK(JobAt == 5);
    // 3. Save as it stands: the switches are not edited, so only the adjustments are written - the bank switch's three lines
    // become one, the lines close up (five writes), the store, the read-back; said once, by the page
    fcLog.clear(); SaveJobs(); run(40);
    CHECK(writes(35) == 0 && writes(53) == 5 && writes(250) == 1 && writes(52) == 1 && AdjStep_ == ADJ_IDLE && JobsStep == JOBS_IDLE && !Adj_Was_Edited && !Sw_Was_Edited);
    { AdjLine L[42]; AdjParseLines(adj, 588, L);
      CHECK(L[0].fn == 2 && L[0].adj == 0 && L[0].ena == 0 && L[0].enaLo == 875 && L[0].enaHi == 2125 && L[0].a1Lo == bankLo && L[0].a1Hi == bankHi && L[0].min == 1 && L[0].max == 4 && L[0].stp == 0);
      CHECK(L[1].fn == 22 && L[1].ena == 0 && L[2].fn == 8 && L[3].fn == 0 && L[4].fn == 0); }
    CHECK(fields["busy"].find("Saved, and read back the same") == 0 && !AdjRows[0].legacy && AdjRows[0].lo == bankLo && AdjBankRowRight(AdjRows[0]) && AdjBankFitted[0]);
    CHECK(modelSaves == 1 && !AdjModelDirty && curveDeg[2][5] == 75);   // (B141: the flight controller has the zones: the model, with the spaced channel, written once)
    CHECK(JobAt == 5 && fields["t0"] == "Job 6 of 6");   // (the page stayed where it was)
    // 4. edit the knob's high end (job 5), save: only its line is written; a 503 is answered again
    JobsPrevious(); run(6); CHECK(JobAt == 4 && fields["tn0"] == "Yaw P gain" && fields["tn3"] == "in bank 2");
    attrs["bar.tap"] = 1800; cmds.clear(); JobsBarMoved(); CHECK(cmds.size() >= 1 && cmds[0] == "click tk1,0");   // (the keypad opens on the high end's box)
    attrs["bar.tap"] = -1; fields["tk1"] = "130"; JobsWasEdited(); JobsPageBack(); CHECK(Adj_Was_Edited && AdjRows[1].v[1] == 130 && fields["bar"] == "|60 to 130|");
    attrs["bar.d0"] = 1100; attrs["bar.d1"] = 2000; attrs["bar.tap"] = -1; JobsBarMoved(); CHECK(AdjRows[1].lo == 1100 && AdjRows[1].hi == 2000 && fields["tn8"] == "Knob 1909 us: 123");
    fcLog.clear(); busyOnce = 1; SaveJobs(); run(30);
    CHECK(writes(53) == 2 && fcLog[0].fn == 53 && fcLog[1].fn == 53 && fcLog[0].data == fcLog[1].data && fcLog[0].data.substr(0, 2) == "01");
    CHECK(writes(250) == 1 && writes(52) == 1 && !Adj_Was_Edited && adj[1 * 14 + 11] == 130 && adj[1 * 14 + 12] == 0 && adj[1 * 14 + 5] == stp(1100));
    CHECK(fields["busy"].find("Saved, and read back the same") == 0 && fields["tk1"] == "130");
    // the nudge's Rate goes back /5
    JobsNext(); run(6); fields["ts2"] = "600"; JobsWasEdited(); fcLog.clear(); SaveJobs(); run(30);
    CHECK(writes(53) == 1 && adj[2 * 14 + 11] == 120 && fields["ts2"] == "600");
    // 5. Add: the picker first, from the top (the two selectors, the switch jobs, the settings); Pitch P gain chosen: a knob on
    // the channel after the job showing's (the nudge on AUX5: AUX6), its values from the present value
    JobsAdd(); CHECK(CurrentView == ADJPICKVIEW && vals["list"] == 0 && JobsPickFor == 1);
    CHECK(pickFn(2) == 0 && pickFn(1) == 1 && pickMode(0) == 2 && pickMode(53) == 3 && pickMode(1) == 4 && pickFn(5) == 26 && pickFn(14) == 35 && pickFn(22) == 43 && JobsPickCount() == 105);
    { uint8_t perm, fn; CHECK(!JobsPickAt(0, perm, fn) && fn == 2); CHECK(!JobsPickAt(1, perm, fn) && fn == 1); CHECK(JobsPickAt(2, perm, fn) && perm == 0); CHECK(JobsPickAt(25, perm, fn) && perm == 43); CHECK(!JobsPickAt(26, perm, fn) && fn == 5); CHECK(!JobsPickAt(104, perm, fn) && fn == 81); CHECK(!JobsPickAt(105, perm, fn) && fn == 0 && perm == 255); }
    vals["list"] = pickFn(14); fcLog.clear(); JobsPickOk(); run(8);
    CHECK(CurrentView == ADJUSTVIEW && AdjN == 4 && AdjAt == 3 && JobAt == 6 && fields["t0"] == "Job 7 of 7" && fields["ltn0"] == "Changes" && fields["tn0"] == "Pitch P gain" && fields["tn2"] == "Knob" && fields["tn3"] == "in any bank" && fields["tn1"] == "Channel 11: AUX6" && fields["tk0"] == "55" && fields["tk1"] == "55" && AdjNow == 55);
    JobsBankTapped(); run(2); CHECK(fields["tn3"] == "in bank 1" && AdjNowBank == 1);
    JobsBankTapped(); run(6); CHECK(fields["tn3"] == "in bank 2" && AdjNow == 55);
    // the kind: a 2-position switch over a switch's travel, then 3 positions (the values evenly between the ends)
    JobsKindTapped(); CHECK(fields["tn2"] == "Switch, 2 positions" && fields["tp0"] == "55" && fields["tp1"] == "56" && cmdValue("bar.kind") == 3 && cmdValue("bar.d0") == 988 && cmdValue("bar.d1") == 2012);
    JobsKindTapped(); CHECK(fields["tn2"] == "Switch, 3 positions" && fields["tp2"] == "56");
    // the picker on the row: opens at its own setting; Cancel keeps it; Yaw P gain chosen; a value the screen failed to give changes nothing
    vals["list"] = 5; JobsSettingTapped(); CHECK(CurrentView == ADJPICKVIEW && vals["list"] == pickFn(14) && JobsPickFor == 0);
    JobsPickCancel(); CHECK(CurrentView == ADJUSTVIEW && AdjRows[3].fn == 14 && fields["t0"] == "Job 7 of 7");
    vals["list"] = 5; JobsSettingTapped(); vals["list"] = pickFn(22); JobsPickOk(); CHECK(CurrentView == ADJUSTVIEW && fields["tn0"] == "Yaw P gain" && AdjRows[3].fn == 22); run(6);
    vals["list"] = 5; JobsSettingTapped(); CHECK(vals["list"] == pickFn(22)); JobsPickCancel();
    JobsSettingTapped(); vals["list"] = 65535; JobsPickOk(); CHECK(CurrentView == ADJUSTVIEW && fields["tn0"] == "Yaw P gain" && AdjRows[3].fn == 22 && AdjN == 4);
    vals["list"] = 5; JobsSettingTapped(); CHECK(vals["list"] == pickFn(22)); vals["list"] = pickFn(14); JobsPickOk(); CHECK(fields["tn0"] == "Pitch P gain" && AdjRows[3].fn == 14); run(6);
    // the first and last positions typed (50 and 60): the middle one is 55; the channel box steps on; a tap on the middle zone types nothing
    fields["tp0"] = "50"; fields["tp2"] = "60"; JobsChannelTapped(); CHECK(fields["tn1"] == "Channel 12: AUX7" && fields["tp1"] == "55");
    attrs["bar.tap"] = 1500; cmds.clear(); JobsBarMoved();
    CHECK(std::find_if(cmds.begin(), cmds.end(), [](const std::string &c) { return c.rfind("click", 0) == 0; }) == cmds.end() && fields["busy"].find("Type the first and last") == 0);
    attrs["bar.tap"] = 2000; cmds.clear(); JobsBarMoved(); CHECK(cmds.size() >= 1 && cmds[0] == "click tp2,0"); attrs["bar.tap"] = -1;
    // a save refused while the last position is not above the first (nothing written); then the switch saved as ONE line
    fields["tp2"] = "40"; boxes = 0; fcLog.clear(); SaveJobs(); run(4); CHECK(boxes == 1 && lastBox.find("Pitch P gain") != std::string::npos && lastBox.find("last position") != std::string::npos && fcLog.empty() && JobsStep == JOBS_IDLE);
    fields["tp2"] = "60"; JobsPageBack(); fcLog.clear(); SaveJobs(); run(40);
    CHECK(writes(53) == 1 && writes(250) == 1 && AdjN == 4 && !Adj_Was_Edited);
    { AdjLine L[42]; AdjParseLines(adj, 588, L); int k = 0; for (int i = 0; i < 42; ++i) if (L[i].fn == 14) ++k; CHECK(k == 1);
      AdjBanks bk; AdjBankRegions(AdjRows, AdjN, bk);
      CHECK(L[3].fn == 14 && L[3].adj == 6 && L[3].ena == 0 && L[3].enaLo == bk.lo[2] && L[3].enaHi == bk.hi[2] && L[3].min == 50 && L[3].max == 60 && L[3].a1Lo == 990 && L[3].a1Hi == 2010 && L[3].stp == 0); }
    CHECK(fields["tn2"] == "Switch, 3 positions" && fields["tp0"] == "50" && fields["tp1"] == "55" && fields["tp2"] == "60");
    // 6. Remove it: the page shows the job before it
    confirmAnswer = true; fcLog.clear(); JobsRemove(); run(4); CHECK(AdjN == 3 && JobsN() == 6 && JobAt == 5 && Adj_Was_Edited && fields["t0"] == "Job 6 of 6" && fields["tn0"] == "Pitch top rotation speed (Rate)");
    fcLog.clear(); SaveJobs(); run(40); CHECK(!Adj_Was_Edited && writes(53) == 1);
    // 7. the switch jobs: the rescue's blobs dragged; Save writes only its slot (a 503 answered again), stores, reads back - and nothing of the adjustments
    JobsPrevious(); JobsPrevious(); JobsPrevious(); JobsPrevious(); run(2); CHECK(JobAt == 1 && fields["tn0"] == "Rescue - the safety net (RESCUE)");
    attrs["bar.d0"] = 1600; attrs["bar.d1"] = 2125; JobsBarMoved(); CHECK(Sw_Was_Edited && SwNow[1].lo == 1600 && cmdValue("bar.d0") == 1600 && cmdSeen("vis b3,1"));
    fcLog.clear(); busyOnce = 1; SaveJobs(); run(30);
    CHECK(writes(35) == 2 && fcLog[0].data == fcLog[1].data && fcLog[0].data.substr(0, 2) == "01" && writes(250) == 1 && writes(34) == 1 && writes(53) == 0 && !Sw_Was_Edited && modes[1 * 4 + 2] == stp(1600));
    CHECK(fields["busy"].find("Saved, and read back the same") == 0 && JobsStep == JOBS_IDLE && fields["t0"] == "Job 2 of 6");
    // 8. the arm rules: the channel stays, the zone may not reach 988 or stop short of 2012, no removing; a kind tap says what a switch job is
    JobsPrevious(); run(2); boxes = 0; JobsChannelTapped(); CHECK(boxes == 1 && SwNow[0].aux == 0 && lastBox.find("The arm switch stays on this model") == 0);
    JobsKindTapped(); CHECK(fields["busy"].find("A switch job has one ON zone") == 0);
    attrs["bar.d0"] = 980; attrs["bar.d1"] = 2125; JobsBarMoved(); boxes = 0; fcLog.clear(); SaveJobs(); run(4); CHECK(boxes == 1 && lastBox.find("The arm zone reaches 988") == 0 && writes(35) == 0 && JobsStep == JOBS_IDLE && Sw_Was_Edited);
    attrs["bar.d0"] = 1200; attrs["bar.d1"] = 1900; JobsBarMoved(); boxes = 0; SaveJobs(); run(4); CHECK(boxes == 1 && lastBox.find("The arm zone stops short of 2012") == 0);
    attrs["bar.d0"] = 1500; attrs["bar.d1"] = 2125; JobsBarMoved(); boxes = 0; JobsRemove(); CHECK(boxes == 1 && lastBox.find("The arm switch cannot be removed") == 0 && SwN == 3);
    ArmingChannel = 3; boxes = 0; SaveJobs(); run(4); CHECK(boxes == 1 && lastBox.find("This model's arming channel is 3") == 0 && SwArmChannel() == 0);
    ArmingChannel = 6; fcLog.clear(); SaveJobs(); run(30); CHECK(!Sw_Was_Edited && writes(35) == 0 && writes(250) == 1);   // (the zone is back where it was: nothing to write, stored and read back all the same)
    // 9. Add a switch job: Self-level chosen: a free slot (slot 2), ON in the upper third of the channel after the one showing (the arm's, AUX1)
    JobsAdd(); CHECK(CurrentView == ADJPICKVIEW && vals["list"] == 0);
    vals["list"] = pickMode(1); JobsPickOk(); run(2);
    CHECK(CurrentView == ADJUSTVIEW && SwN == 4 && JobsN() == 7 && JobAt == 2 && fields["t0"] == "Job 3 of 7" && fields["ltn0"] == "Does" && fields["tn0"] == "Self-level (ANGLE)" && SwNow[2].perm == 1 && SwNow[2].aux == 1 && SwNow[2].lo == 1700 && SwNow[2].hi == 2125 && Sw_Was_Edited);
    // the job of a switch row changed through the picker (opens on its own); Cancel keeps it; the channel tapped: the next one
    vals["list"] = 0; JobsSettingTapped(); CHECK(CurrentView == ADJPICKVIEW && vals["list"] == pickMode(1)); vals["list"] = pickMode(47); JobsPickOk(); CHECK(SwNow[2].perm == 47 && fields["tn0"] == "Acro trainer (TRAINER)");
    JobsSettingTapped(); JobsPickCancel(); CHECK(CurrentView == ADJUSTVIEW && SwNow[2].perm == 47 && fields["t0"] == "Job 3 of 7");
    JobsChannelTapped(); CHECK(SwNow[2].aux == 2 && fields["tn1"] == "Channel 8: AUX3");
    // 10. a switch job becoming a knob: the row goes, a knob on its channel takes its place among the adjustments; and back
    vals["list"] = 0; JobsSettingTapped(); vals["list"] = pickFn(14); JobsPickOk(); run(8);
    CHECK(SwN == 3 && AdjN == 4 && JobsN() == 7 && !SwUsed(SwNow[2]) && AdjRows[AdjAt].fn == 14 && AdjRows[AdjAt].ch == 2 && JobAt == SwN + AdjAt && fields["ltn0"] == "Changes" && fields["tn0"] == "Pitch P gain" && fields["tn1"] == "Channel 8: AUX3");
    vals["list"] = 0; JobsSettingTapped(); vals["list"] = pickMode(47); JobsPickOk(); run(2);
    CHECK(SwN == 4 && AdjN == 3 && JobsN() == 7 && JobAt == SwAt && fields["ltn0"] == "Does" && fields["tn0"] == "Acro trainer (TRAINER)" && SwNow[SwShown[SwAt]].perm == 47 && SwNow[SwShown[SwAt]].aux == 2 && fields["tn1"] == "Channel 8: AUX3");   // (the knob's own channel)
    // the arm switch never becomes a knob
    JobAt = 0; JobsShow(); vals["list"] = 0; JobsSettingTapped(); vals["list"] = pickFn(14); boxes = 0; JobsPickOk(); CHECK(boxes == 1 && lastBox.find("The arm switch stays") == 0 && SwN == 4 && AdjN == 3);
    // 11. Remove the black box one, Save: both tables - two slots (the new one, the emptied one) and nothing of the adjustments
    JobsNext(); JobsNext(); JobsNext(); run(2); CHECK(fields["tn0"] == "Black box recording (BLACKBOX)" && JobAt == 3);
    confirmAnswer = true; JobsRemove(); CHECK(SwN == 3 && !SwUsed(SwNow[3]) && JobAt == 3 && fields["ltn0"] == "Changes");   // (the row after it: the first setting)
    // (B211, the tenth review: THIS SAVE WAS REFUSED IN HERE, UNSEEN, until 15 Nov 2026 - the Yaw P knob's row (60 to 130) had taken the
    //  keypad's boxes while a switch job was showing: "55" and "55", another row's, and Save said "2. Yaw P gain: ..." after the switches
    //  had gone. Only the row that is on the screen is gathered now (RF_Adjust.h AdjShownAt): the knob is as it was, the save runs
    //  through - the switches' two slots, stored; then the adjustments, which the job that became a knob and back had marked edited:
    //  no line of them differs, so none is written; stored, read back the same.)
    CHECK(AdjRows[1].kind == AK_KNOB && AdjRows[1].fn == 22 && AdjRows[1].v[0] == 60 && AdjRows[1].v[1] == 130);
    boxes = 0; fcLog.clear(); SaveJobs(); run(40);
    CHECK(writes(35) == 2 && writes(250) == 2 && writes(53) == 0 && writes(52) == 1 && modes[2 * 4] == 47 && modes[2 * 4 + 1] == 2 && modes[3 * 4 + 3] == stp(1500) && SwN == 3 && !Sw_Was_Edited);
    CHECK(boxes == 0 && !Adj_Was_Edited && fields["busy"] == "Saved, and read back the same." && AdjRows[1].v[0] == 60 && AdjRows[1].v[1] == 130);
    // 12. both tables edited, one Save: the switches first, then the adjustments, said once at the end
    attrs["bar.d0"] = 1650; attrs["bar.d1"] = 2125; JobAt = 1; JobsShow(); JobsBarMoved(); CHECK(Sw_Was_Edited);
    JobAt = SwN + 1; JobsShow(); run(6); CHECK(fields["tn0"] == "Yaw P gain"); fields["tk1"] = "140"; JobsWasEdited(); JobsPageBack(); CHECK(Adj_Was_Edited);
    fcLog.clear(); SaveJobs(); run(60);
    CHECK(writes(35) == 1 && writes(34) == 1 && writes(53) == 1 && writes(250) == 2 && writes(52) == 1 && !Sw_Was_Edited && !Adj_Was_Edited && JobsStep == JOBS_IDLE);
    CHECK(fields["busy"].find("Saved, and read back the same") == 0 && fields["tn0"] == "Yaw P gain" && fields["tk1"] == "140");
    // 13. OK with unsaved edits asks "Save now?": Discard leaves at once; Save saves both tables and then leaves
    attrs["bar.d0"] = 1600; attrs["bar.d1"] = 2125; JobAt = 1; JobsShow(); JobsBarMoved(); fields["tk1"] = "150"; JobAt = SwN + 1; JobsShow(); JobsWasEdited(); JobsPageBack(); CHECK(Sw_Was_Edited && Adj_Was_Edited);
    saveNowAnswer = 0; saveNowAsked = 0; rfStarts = 0; EndJobsView(); CHECK(saveNowAsked == 1 && lastBox.find("The edited switches and knobs are not saved") == 0 && rfStarts == 1 && CurrentView == 47 && !Sw_Was_Edited && !Adj_Was_Edited);
    // (back on the page with the same edits)
    CurrentView = ADJUSTVIEW; JobAt = 1; JobsShow(); attrs["bar.d0"] = 1620; JobsBarMoved(); CHECK(Sw_Was_Edited);
    saveNowAnswer = 1; saveNowAsked = 0; rfStarts = 0; fcLog.clear(); EndJobsView(); CHECK(saveNowAsked == 1 && rfStarts == 0 && JobsStep == JOBS_SAVE_SW);
    run(60); CHECK(writes(35) == 1 && writes(250) == 1 && !Sw_Was_Edited && rfStarts == 1 && CurrentView == 47);   // (saved, then left)
    // 13b (the twelfth review, reviewer B's finding 11). OK, "Save now?", Save - and the save STOPS on a box with no answer, putting up no box of its own:
    //     nothing is written, the page stays - and "close when saved" is not left standing: a LATER Save, by its own button, saves and does NOT close
    //     the page under him (it did)
    CurrentView = ADJUSTVIEW; fields["tk1"] = "160"; JobAt = SwN + 1; JobsShow(); JobsWasEdited(); JobsPageBack(); CHECK(Adj_Was_Edited);
    fields["tk1"] = "170"; BoxesLostAtWork = BoxesLost; loseAtQuestion = true;                    // (OK's own gather is answered; the SAVE's, behind the question, is not)
    saveNowAnswer = 1; saveNowAsked = 0; rfStarts = 0; fcLog.clear(); EndJobsView(); loseAtQuestion = false;
    CHECK(saveNowAsked == 1 && BoxesLost != BoxesLostAtWork);                                    // (the scene is the one meant: asked, Save, a box of the save's gather lost)
    CHECK(rfStarts == 0 && CurrentView == ADJUSTVIEW && JobsStep == JOBS_IDLE && Adj_Was_Edited && fcLog.empty());
    CHECK(!RfLeaveAfterSave);                                                                    // "close when saved" does not stand
    fieldsLost.clear(); BoxesLostAtWork = BoxesLost; SaveJobs(); run(60);
    CHECK(!Adj_Was_Edited && JobsStep == JOBS_IDLE && rfStarts == 0 && CurrentView == ADJUSTVIEW);   // saved by its own button: the page is still open
    saveNowAnswer = 0;
    // 14. no USB cable: the switches read, the adjustments refused - the switch jobs stand, the page says so; a setting cannot be added, a switch job can
    usb = false; StartJobsView(); run(8);
    CHECK(CurrentView == ADJUSTVIEW && SwHave && !AdjHave && AdjMissing && JobsN() == SwN && SwN == 3 && fields["t0"] == "Job 1 of 3" && fields["t9"] == "Bluetooth" && fields["busy"].find("need the USB cable") != std::string::npos && JobsStep == JOBS_IDLE);
    JobsAdd(); CHECK(CurrentView == ADJPICKVIEW); vals["list"] = pickFn(14); JobsPickOk(); run(2); CHECK(CurrentView == ADJUSTVIEW && JobsN() == 3 && fields["busy"].find("need the USB cable") != std::string::npos);
    JobsAdd(); vals["list"] = pickMode(13); JobsPickOk(); run(2); CHECK(SwN == 4 && JobsN() == 4 && fields["tn0"] == "Beeper on (BEEPER)" && Sw_Was_Edited);
    fcLog.clear(); SaveJobs(); run(40); CHECK(writes(35) == 1 && writes(250) == 1 && writes(53) == 0 && !Sw_Was_Edited && fields["busy"].find("Saved, and read back the same") == 0);
    usb = true;
    // 15. no arm switch at all is refused; B97: the flight controller's arm switch on another channel follows this model's arming channel
    blankModes(); slot(0, 53, 2, 1700, 2125);
    StartJobsView(); run(8); boxes = 0; SwNow[0].lo = 1600; SwEdited(); SaveJobs(); run(4); CHECK(boxes == 1 && lastBox.find("Rotorflight needs an arm switch") == 0 && JobsStep == JOBS_IDLE);
    blankModes(); slot(0, 0, 2, 1500, 2125); slot(1, 53, 3, 1700, 2125);   // ARM on AUX3 (channel 8); the model's arming channel is 6
    ArmingChannel = 6; cmds.clear(); StartJobsView(); run(8);
    CHECK(SwN == 2 && SwNow[0].perm == 0 && SwNow[0].aux == 0 && Sw_Was_Edited && fields["tn1"] == "Channel 6: AUX1" && fields["hint"].find("Arm moved from channel 8 to 6") == 0 && fields["hint"].size() <= 90 && cmdSeen("vis b3,1"));
    fcLog.clear(); SaveJobs(); run(30);
    CHECK(writes(35) == 1 && fcLog[0].data.substr(0, 6) == "000000" && modes[1] == 0 && modes[4] == 53 && modes[5] == 3 && !Sw_Was_Edited && fields["hint"].find("Arm switch:") == 0);
    boxes = 0; JobsChannelTapped(); CHECK(boxes == 1 && SwNow[0].aux == 0 && lastBox.find("The arm switch stays on this model") == 0);
    ArmingChannel = 9; boxes = 0; JobsChannelTapped(); CHECK(boxes == 0 && SwNow[0].aux == 3 && Sw_Was_Edited && fields["tn1"] == "Channel 9: AUX4" && fields["hint"].find("Arm moved from channel 6 to 9") == 0);
    boxes = 0; fcLog.clear(); SaveJobs(); run(30); CHECK(boxes == 0 && writes(35) == 1 && modes[1] == 3 && !Sw_Was_Edited);
    ArmingChannel = 3; StartJobsView(); run(8); CHECK(SwN == 2 && SwNow[0].aux == 3 && !Sw_Was_Edited && fields["hint"].find("Arm switch:") == 0);
    ArmingChannel = 6;
    // 15b. B210 (11 Nov 2026): THE CHANNEL MAP. Arming on channel 5 for ExpressLRS = map AECR1T23: AUX1 IS channel 5 and
    // channel 6 the throttle. The page reads the map (MSP 64) after the switches and names, moves and checks by it.
    {
        static const uint8_t ldrcMap[8] = {0, 1, 3, 2, 4, 5, 6, 7}, elrsMap[8] = {0, 1, 3, 2, 5, 4, 6, 7}, bad[8] = {0, 1, 3, 2, 4, 4, 6, 7};
        const uint16_t keep4 = SendBuffer[4], keep5 = SendBuffer[5];
        memcpy(rcmap, elrsMap, 8); blankModes(); slot(0, 0, 0, 1500, 2125);              // ARM on AUX1
        ArmingChannel = 5; cmds.clear(); fcLog.clear(); StartJobsView(); run(8);
        CHECK(writes(64) == 1 && RfMapLen == 8 && SwArmChannel() == 5 && SwN == 1 && SwNow[0].aux == 0 && !Sw_Was_Edited);   // 5 IS a switch channel now
        CHECK(fields["tn1"] == "Channel 5: Gear");                                      // named by its channel (this test's name for 5)
        SendBuffer[4] = 2233; SendBuffer[5] = 1000; SwLiveCh = -1; SwLive(); CHECK(fields["tn8"] == "ON: 2012 us");   // the marker reads 5, not 6
        ArmingChannel = 6; CHECK(SwArmChannel() == 0);                                  // 6 is the throttle under this map
        boxes = 0; SwNow[0].lo = 1600; SwEdited(); SaveJobs(); run(4);
        CHECK(boxes == 1 && lastBox.find("This model's arming channel is 6") == 0 && lastBox.find("not a switch channel") != std::string::npos);
        memcpy(rcmap, bad, 8); ArmingChannel = 6; blankModes(); slot(0, 0, 0, 1500, 2125); StartJobsView(); run(8);   // not a whole map: none
        CHECK(RfMapLen == 0 && SwArmChannel() == 6 && fields["tn1"] == "Channel 6: AUX1");
        memcpy(rcmap, ldrcMap, 8); ArmingChannel = 6; SendBuffer[4] = keep4; SendBuffer[5] = keep5;
    }
    // 16. no model, no backup: refused before anything
    needModel = true; boxes = 0; fcLog.clear(); rfStarts = 0; StartJobsView(); CHECK(boxes == 1 && fcLog.empty() && lastBox.find("need the model") != std::string::npos); needModel = false;
    // 17. SIX BANKS (B130/B138/B139): a bank selector added on channel 7, which tells six banks apart; the switch walks every bank;
    // then banks 5 and 6 as bank 4's twins (the channel spaced), plain and reversed
    banksN = 6; blankModes(); slot(0, 0, 0, 1500, 2125); blankAdj();
    for (int b = 1; b <= 6; ++b) setDeg(b, 6, 45 + (b - 1) * 18);   // (1000, 1200 ... 2000 us: 988, 1193 ... 2012 at the flight controller - the middle of six even zones already)
    Bank = 2; liveCh = 6; live(); memset(curveDeg, -1, sizeof curveDeg); modelSaves = 0;
    StartJobsView(); run(8); CHECK(SwN == 1 && AdjN == 0 && JobsN() == 1);
    JobsAdd(); vals["list"] = 0; JobsPickOk(); run(8);
    CHECK(AdjN == 1 && JobAt == 1 && fields["t0"] == "Job 2 of 2" && AdjRows[0].fn == 2 && AdjRows[0].kind == AK_SWITCH && AdjRows[0].n == 6 && AdjBankFitted[0] && fields["tn2"] == "Banks 1 to 6 of this transmitter" && fields["bar"] == "1|2|3|4|5|6" && cmdValue("bar.kind") == 4 && cmdValue("bar.n") == 6);
    CHECK(AdjRows[0].ch == 1 && fields["tn1"] == "Channel 7: AUX2" && curveDeg[2][6] == -1 && !AdjModelDirty);   // (the arm job showing was on AUX1: the new one on the channel after it; its banks already in the middle: left as they are)
    for (int b = 1; b <= 6; ++b) { Bank = (uint8_t)b; run(8); char e[40]; snprintf(e, sizeof e, "Bank %d: %d us", b, AdjFcUs(usOf(b, 6))); CHECK(fields["tn8"] == e); CHECK(cmdValue("bar.mk") == AdjFcUs(usOf(b, 6))); }
    fcLog.clear(); SaveJobs(); run(40); CHECK(writes(53) >= 1 && writes(250) == 1 && !Adj_Was_Edited && modelSaves == 0);
    { AdjLine L[42]; AdjParseLines(adj, 588, L); CHECK(L[0].fn == 2 && L[0].min == 1 && L[0].max == 6 && L[0].adj == 1); }
    confirmAnswer = true; JobsRemove(); run(4); CHECK(AdjN == 0 && JobsN() == 1 && JobAt == 0);
    twin(6); AdjSeenClear(); modelSaves = 0; Bank = 2; live(); memset(curveDeg, -1, sizeof curveDeg);
    JobsAdd(); vals["list"] = 0; JobsPickOk(); run(8);
    CHECK(AdjN == 1 && AdjRows[0].n == 6 && AdjBankFitted[0] && modelSaves == 0 && AdjModelDirty && curveDeg[1][6] == 0 && curveDeg[6][6] == 180);
    for (int b = 1; b <= 6; ++b) { Bank = (uint8_t)b; run(8); char e[40]; snprintf(e, sizeof e, "Bank %d: %d us", b, AdjFcUs(SendBuffer[6])); CHECK(fields["tn8"] == e); CHECK(abs(AdjFcUs(SendBuffer[6]) - (AdjRows[0].lo + ((AdjRows[0].hi - AdjRows[0].lo) * (b - 1) + 2) / 5)) <= 8); }
    fcLog.clear(); SaveJobs(); run(40); CHECK(writes(250) == 1 && !Adj_Was_Edited && modelSaves == 1 && !AdjModelDirty);   // (B141: the card written once the flight controller has the zones; the line itself is the one the flight controller holds)
    confirmAnswer = true; JobsRemove(); run(4); CHECK(AdjN == 0);
    ReversedChannelBITS = (uint16_t)(1 << 6); memset(curveDeg, -1, sizeof curveDeg); AdjSeenClear(); modelSaves = 0; Bank = 2; live();
    JobsAdd(); vals["list"] = 0; JobsPickOk(); run(8);
    CHECK(AdjN == 1 && AdjRows[0].n == 6 && AdjBankFitted[0] && modelSaves == 0 && AdjModelDirty && curveDeg[1][6] == 180 && curveDeg[6][6] == 0 && strstr(AdjBankWhy, "degrees, reversed)."));
    for (int b = 1; b <= 6; ++b) { Bank = (uint8_t)b; run(8); char e[40]; snprintf(e, sizeof e, "Bank %d: %d us", b, AdjFcUs(SendBuffer[6])); CHECK(fields["tn8"] == e); CHECK(abs(AdjFcUs(SendBuffer[6]) - (AdjRows[0].lo + ((AdjRows[0].hi - AdjRows[0].lo) * (b - 1) + 2) / 5)) <= 8); }
    // OK, "Save now?" answered Discard: the reversed spacing goes, the channel back as the card has it (the six saved above)
    saveNowAnswer = 0; saveNowAsked = 0; EndJobsView();
    CHECK(saveNowAsked == 1 && CurrentView == 47 && !AdjModelDirty && modelSaves == 0 && CurvePoint[1][6][0] == 0 && CurvePoint[2][6][0] == 63 && CurvePoint[5][6][0] == 117 && CurvePoint[6][6][0] == 180);
    ReversedChannelBITS = 0; banksN = 4;
    // 18. B141 (Malcolm, 20 Oct 2026: "I have set channel 7 to banks, and it has been initially set to four. And this is working,
    // but if I change to six, it does not get the channel positions into the centre of the zones"): the wide range, 500 to 2500.
    // Four banks spaced the old way, 0, 60, 120, 180 degrees - 988, 1160, 1840, 2012 as the flight controller sees them, bank 2
    // ONE microsecond inside its zone - and the line fitted to them: opening the page spaces the channel again, each bank in the
    // middle of its zone, and says so; the card is written at Save, not before. Six banks (5 and 6 bank 4's twins): six middles.
    // The old six-bank spacing on the narrow range (36 us off): spaced again. Discard on leaving: the curves go back.
    blankModes(); slot(0, 0, 0, 1500, 2125); blankAdj(); putLine(0, 2, 0, 875, 2125, 1, 988, 2012, 1500, 1500, 1, 4, 0);
    MaxRangeNarrow = 0; for (int b = 1; b <= 4; ++b) setDeg(b, 6, (b - 1) * 60);
    CHECK(AdjFcUs(usOf(2, 6)) == 1160 && AdjFcUs(usOf(3, 6)) == 1840);
    Bank = 1; live(); memset(curveDeg, -1, sizeof curveDeg); modelSaves = 0; AdjSeenClear();
    StartJobsView(); run(8);
    CHECK(SwN == 1 && AdjN == 1 && AdjRows[0].fn == 2 && AdjRows[0].n == 4 && AdjBankFitted[0] && Adj_Was_Edited && AdjModelDirty && modelSaves == 0);
    CHECK(fields["busy"] == "Press Save: the bank selector now matches this transmitter's banks." && cmdSeen("vis b3,1"));
    CHECK(curveDeg[1][6] == 0 && curveDeg[2][6] == 75 && curveDeg[3][6] == 105 && curveDeg[4][6] == 180 && strcmp(AdjBankWhy, "Channel 7 set bank by bank: 988, 1330, 1670, 2012 us, the middle of each zone (0, 75, 105, 180 degrees).") == 0);
    JobsNext(); run(2); CHECK(JobAt == 1 && fields["tn2"] == "Banks 1 to 4 of this transmitter" && cmdValue("bar.n") == 4);
    for (int b = 1; b <= 4; ++b) { Bank = (uint8_t)b; run(8); char e[40]; snprintf(e, sizeof e, "Bank %d: %d us", b, AdjFcUs(SendBuffer[6])); CHECK(fields["tn8"] == e); CHECK(abs(AdjFcUs(SendBuffer[6]) - (AdjRows[0].lo + ((AdjRows[0].hi - AdjRows[0].lo) * (b - 1) + 1) / 3)) <= 8); }
    fcLog.clear(); SaveJobs(); run(40); CHECK(writes(53) == 1 && writes(250) == 1 && !Adj_Was_Edited && modelSaves == 1 && !AdjModelDirty);
    // six banks on (Model options): banks 5 and 6 are bank 4's twins until the page sets them
    banksN = 6; twin(6); Bank = 1; live(); memset(curveDeg, -1, sizeof curveDeg); modelSaves = 0; AdjSeenClear();
    StartJobsView(); run(8); JobsNext(); run(2);
    CHECK(AdjN == 1 && AdjRows[0].n == 6 && AdjBankFitted[0] && AdjModelDirty && modelSaves == 0 && fields["tn2"] == "Banks 1 to 6 of this transmitter" && cmdValue("bar.n") == 6);
    CHECK(curveDeg[1][6] == 0 && curveDeg[2][6] == 63 && curveDeg[3][6] == 81 && curveDeg[4][6] == 99 && curveDeg[5][6] == 117 && curveDeg[6][6] == 180);
    CHECK(strcmp(AdjBankWhy, "Channel 7 set bank by bank: 988, 1193, 1398, 1602, 1807, 2012 us, the middle of each zone (0, 63, 81, 99, 117, 180 degrees).") == 0);
    for (int b = 1; b <= 6; ++b) { Bank = (uint8_t)b; run(8); char e[40]; snprintf(e, sizeof e, "Bank %d: %d us", b, AdjFcUs(SendBuffer[6])); CHECK(fields["tn8"] == e); CHECK(abs(AdjFcUs(SendBuffer[6]) - (AdjRows[0].lo + ((AdjRows[0].hi - AdjRows[0].lo) * (b - 1) + 2) / 5)) <= 8); }
    fcLog.clear(); SaveJobs(); run(40); CHECK(writes(53) == 1 && !Adj_Was_Edited && modelSaves == 1 && !AdjModelDirty);
    { AdjLine L[42]; AdjParseLines(adj, 588, L); CHECK(L[0].fn == 2 && L[0].min == 1 && L[0].max == 6 && L[0].a1Lo == AdjRows[0].lo && L[0].a1Hi == AdjRows[0].hi); }
    // the narrow range, 945 to 2055: the old even degrees (0, 36 ... 180) are within an eighth of a zone of the middles once the
    // line's ends are fitted (970..2030): the channel is left alone, the line re-fitted and Save asked for
    MaxRangeNarrow = 1; for (int b = 1; b <= 6; ++b) setDeg(b, 6, (b - 1) * 36);
    Bank = 1; live(); memset(curveDeg, -1, sizeof curveDeg); modelSaves = 0; AdjSeenClear();
    StartJobsView(); run(8); JobsNext(); run(2);
    CHECK(AdjN == 1 && AdjRows[0].n == 6 && AdjBankFitted[0] && !AdjModelDirty && modelSaves == 0 && curveDeg[1][6] == -1 && Adj_Was_Edited && fields["busy"] == "Press Save: the bank selector now matches this transmitter's banks.");
    fprintf(stderr, "   (narrow range, the old six: ends %d..%d, left alone)\n", AdjRows[0].lo, AdjRows[0].hi);
    for (int b = 1; b <= 6; ++b) { Bank = (uint8_t)b; run(8); CHECK(abs(AdjFcUs(SendBuffer[6]) - (AdjRows[0].lo + ((AdjRows[0].hi - AdjRows[0].lo) * (b - 1) + 2) / 5)) <= (AdjRows[0].hi - AdjRows[0].lo) / 40); }
    // six heights set by hand, Black Thunder 2's way (13, 54, 90, 120, 151, 170 degrees): off the middles, so spaced; then OK,
    // "Save now?" answered Discard: the channel goes back as the card has it, nothing written
    const int hand[7] = {0, 13, 54, 90, 120, 151, 170};
    for (int b = 1; b <= 6; ++b) setDeg(b, 6, hand[b]);
    Bank = 1; live(); memset(curveDeg, -1, sizeof curveDeg); modelSaves = 0; AdjSeenClear();
    StartJobsView(); run(8); JobsNext(); run(2);
    CHECK(AdjN == 1 && AdjRows[0].n == 6 && AdjBankFitted[0] && AdjModelDirty && modelSaves == 0 && curveDeg[1][6] == 0 && curveDeg[6][6] == 180 && strncmp(AdjBankWhy, "Channel 7 set bank by bank: 988, ", 33) == 0);
    fprintf(stderr, "   (narrow range, by hand: %s)\n", AdjBankWhy);
    for (int b = 1; b <= 6; ++b) { Bank = (uint8_t)b; run(8); CHECK(abs(AdjFcUs(SendBuffer[6]) - (AdjRows[0].lo + ((AdjRows[0].hi - AdjRows[0].lo) * (b - 1) + 2) / 5)) <= 8); }
    saveNowAnswer = 0; saveNowAsked = 0; EndJobsView();
    CHECK(saveNowAsked == 1 && CurrentView == 47 && !AdjModelDirty && modelSaves == 0);
    for (int b = 1; b <= 6; ++b) for (int k = 0; k < CURVE_POINTS_MAX; ++k) CHECK(CurvePoint[b][6][k] == hand[b]);
    MaxRangeNarrow = 0; banksN = 4; liveCh = -1;
    // 19. B211 (the tenth review, reviewer B's experiment; released code had the fault): ONLY THE ROW THAT IS ON THE SCREEN IS GATHERED.
    // THE FLIGHT CONTROLLER: the ARM switch job on AUX1 and a RESCUE job on AUX3 - and its adjustments: the first of the list a knob on
    // AUX2 that sets the Yaw P gain between 60 and 120, the second a knob on AUX4 for the Pitch P gain, 40 to 70. (No bank or rates
    // selector in front.) THE SCREEN keeps every box of a page as it was last written - also across visits: the keypad's boxes tk0/tk1
    // hold what the LAST knob shown on an earlier visit left there (another model's, say: 15 and 25); a screen just started has the
    // page file's "0" and "0". The page opens on the arm switch's job; Next > shows the second SWITCH job: the cursor of the knobs is
    // at their first row, whose boxes were never written on this visit - it took them (15 to 25, or 0 to 0), the page not marked
    // edited, and the next Save (of anything) wrote that to the flight controller.
    for (int stale = 0; stale < 2; ++stale)
    {
        Bank = 2; for (int b = 0; b <= BANKS_USED; ++b) for (int c = 0; c <= CHANNELSUSED; ++c) setDeg(b, c, 90);
        memset(curveDeg, -1, sizeof curveDeg); AdjSeenClear(); usb = true; needModel = false; busyOnce = 0; saveNowAnswer = 0;
        blankAdj(); blankModes();
        slot(0, 0, 0, 1500, 2125); slot(1, 53, 2, 1700, 2125);
        putLine(0, 22, 0, 875, 2125, 1, 1000, 2000, 1500, 1500, 60, 120, 0);
        putLine(1, 14, 0, 875, 2125, 3, 1000, 2000, 1500, 1500, 40, 70, 0);
        fields["tk0"] = stale ? "15" : "0"; fields["tk1"] = stale ? "25" : "0";
        fcLog.clear(); cmds.clear(); boxes = 0;
        StartJobsView(); run(8);
        CHECK(SwHave && AdjHave && SwN == 2 && AdjN == 2 && JobAt == 0 && AdjRows[0].kind == AK_KNOB && AdjRows[0].v[0] == 60 && AdjRows[0].v[1] == 120 && !Adj_Was_Edited);
        CHECK(AdjShownAt == -1);                                  // (a switch job shows: no knob's row is on the screen)
        JobsNext(); run(2);     // Next >: the rescue job - still a switch job on the screen
        CHECK(AdjRows[0].v[0] == 60 && AdjRows[0].v[1] == 120 && !Adj_Was_Edited && AdjShownAt == -1);   // a row that has not been on the screen is not gathered
        JobsNext(); run(8);     // Next >: the Yaw P knob's own row - its boxes written from what is in hand
        CHECK(AdjShownAt == 0 && AdjAt == 0 && fields["tk0"] == "60" && fields["tk1"] == "120");
        JobsNext(); run(8);     // Next >: the Pitch P knob: the pilot types 75 for its high end (the keypad), and saves
        CHECK(AdjShownAt == 1 && AdjAt == 1 && fields["tk0"] == "40" && fields["tk1"] == "70" && AdjRows[0].v[0] == 60 && AdjRows[0].v[1] == 120);
        fields["tk1"] = "75"; JobsWasEdited(); JobsPageBack(); run(2);
        CHECK(AdjRows[1].v[0] == 40 && AdjRows[1].v[1] == 75 && Adj_Was_Edited);
        const size_t w0 = fcLog.size(); SaveJobs(); run(400);
        int mn, mx; line0(w0, mn, mx);
        CHECK(mn == 60 && mx == 120);                             // line 0 (the Yaw P knob, never touched) goes as it was read: 60 to 120 (it went as 15 to 25, or 0 to 0)
        CHECK(writes(53) == 2 && boxes == 0 && !Adj_Was_Edited && fields["busy"] == "Saved, and read back the same.");   // (both lines are written: the page's own form of a line differs from this flight controller's)
        CHECK((adj[9] | (adj[10] << 8)) == 60 && (adj[11] | (adj[12] << 8)) == 120 && (adj[14 + 9] | (adj[14 + 10] << 8)) == 40 && (adj[14 + 11] | (adj[14 + 12] << 8)) == 75);
        // ... and back to a switch job with the knob's boxes now holding the Pitch P's "40" and "75": the cursor's row is not gathered from them either
        JobAt = 0; JobsShow(); run(2);
        CHECK(AdjShownAt == -1); JobsWasEdited(); JobsPageBack(); run(2);
        CHECK(AdjRows[0].v[0] == 60 && AdjRows[0].v[1] == 120 && AdjRows[1].v[0] == 40 && AdjRows[1].v[1] == 75);
        saveNowAnswer = 0; EndJobsView(); run(2);
    }
    // 20. B211 (the eleventh review, reviewer B's experiments 1 and 7): THE PAGE IS BACK ON THE SCREEN AND THIS BOARD HAS NOT DRAWN IT - AND THE BAR
    // IS THE CARD'S. Whenever the page is loaded the screen shows it as its card has it: the typed boxes keep their texts, the BAR is the card's
    // (kind 0, its dividers at 1500 and 1700 - and none of this board's attributes on it). The page says "ldrcadj" and JobsPageBack draws the
    // row and its bar again - but it went back with nothing done when a box of its gather had no answer (a page slow in coming up is served
    // its word while the screen owes an answer), and on a field screen the word itself can be lost. A touch on the card's bar was then read as
    // the row's own: 1500 and 1700 became the knob's ends.
    {
        auto setup = [&]() {
            Bank = 2; for (int b = 0; b <= BANKS_USED; ++b) for (int c = 0; c <= CHANNELSUSED; ++c) setDeg(b, c, 90);
            memset(curveDeg, -1, sizeof curveDeg); AdjSeenClear(); usb = true; needModel = false; busyOnce = 0; saveNowAnswer = 0;
            blankAdj(); blankModes();
            slot(0, 0, 0, 1500, 2125); slot(1, 53, 2, 1700, 2125);
            putLine(0, 22, 0, 875, 2125, 1, 1000, 2000, 1500, 1500, 60, 120, 0);
            putLine(1, 14, 0, 875, 2125, 3, 1000, 2000, 1500, 1500, 40, 70, 0);
            fcLog.clear(); cmds.clear(); boxes = 0; attrs.clear(); attrsLost.clear(); fieldsLost.clear(); noPage = false; boxesLostTold = 0; BoxesLostAtWork = BoxesLost;
            StartJobsView(); run(8);
            JobsNext(); run(2); JobsNext(); run(8);                // the Yaw P knob's row: 60 to 120, its ends at 1000 and 2000
            CHECK(AdjShownAt == 0 && AdjAt == 0 && AdjRows[0].lo == 1000 && AdjRows[0].hi == 2000 && AdjRows[0].v[0] == 60 && AdjRows[0].v[1] == 120 && !Adj_Was_Edited && !JobsIsDue());
            CHECK(attrs["bar.own"] != 0 && attrs["bar.own"] == (int) JobsBarToken);          // the bar carries the token of the last draw
        };
        auto reload = [&]() { ++ScreenMarkCount; attrs.clear(); attrs["bar.d0"] = 1500; attrs["bar.d1"] = 1700; attrs["bar.tap"] = -1; };   // a page command of this board's: the page as the card has it (the typed boxes keep their texts)
        auto asRead = [&]() { return AdjRows[0].lo == 1000 && AdjRows[0].hi == 2000 && AdjRows[0].v[0] == 60 && AdjRows[0].v[1] == 120; };
        // (a) every draw gives the bar a NEW token
        setup(); { const int t1 = attrs["bar.own"]; JobsShow(); CHECK(attrs["bar.own"] != t1 && attrs["bar.own"] == (int) JobsBarToken); }
        // (b) the page loaded again and its word NEVER COMES (lost); the pilot touches the card's bar at once: NOTHING of it is taken - the page is
        //     drawn instead, the row's own bar again - and his next touch is the row's
        setup(); reload(); cmds.clear(); BoxesLostAtWork = BoxesLost;
        JobsBarMoved();
        CHECK(asRead() && !Adj_Was_Edited);                                                 // (it was: ends 1500 and 1700, the page marked edited)
        CHECK(cmdValue("bar.d0") == 1000 && cmdValue("bar.d1") == 2000 && attrs["bar.own"] == (int) JobsBarToken && !JobsIsDue());   // ... the page drawn, the bar this board's again
        attrs["bar.d0"] = 1100; attrs["bar.d1"] = 2000; attrs["bar.tap"] = -1; BoxesLostAtWork = BoxesLost; JobsBarMoved();
        CHECK(AdjRows[0].lo == 1100 && AdjRows[0].hi == 2000 && Adj_Was_Edited);            // ... and a drag of the row's own bar is taken
        // (b2) ... loaded again BY THE SCREEN (its keypad closing: no page command of this board's - the count of them tells nothing), the word lost,
        //      the card's bar touched: the TOKEN alone says the bar is not ours - nothing taken, the page drawn
        setup(); attrs.clear(); attrs["bar.d0"] = 1500; attrs["bar.d1"] = 1700; attrs["bar.tap"] = -1; cmds.clear(); BoxesLostAtWork = BoxesLost;
        CHECK(!JobsIsDue());
        JobsBarMoved();
        CHECK(asRead() && !Adj_Was_Edited && cmdValue("bar.d0") == 1000 && cmdValue("bar.d1") == 2000 && attrs["bar.own"] == (int) JobsBarToken && !JobsIsDue());
        // (c) ... the same, and nobody touches anything: the main loop draws the page a second after it was put up
        setup(); reload(); cmds.clear();
        run(10); CHECK(JobsIsDue() && cmdValue("bar.d0") == -9999);                         // (half a second: its own word may yet come)
        run(15); CHECK(!JobsIsDue() && cmdValue("bar.d0") == 1000 && cmdValue("bar.d1") == 2000 && attrs["bar.own"] == (int) JobsBarToken && asRead() && boxesLostTold == 0);
        // (d) the page's word comes - and a box of its gather has NO ANSWER (the screen owes one: nothing can be asked): nothing is taken, nothing drawn,
        //     no live marker is ticked onto the page - and when the screen can be asked again the main loop draws it, the value he TYPED taken first
        setup(); reload(); fields["tk1"] = "130"; cmds.clear(); noPage = true; fieldsLost.insert("tk0"); BoxesLostAtWork = BoxesLost;
        JobsPageBack();
        CHECK(asRead() && JobsIsDue() && cmdValue("bar.d0") == -9999);
        uint16_t sent0[17]; memcpy(sent0, SendBuffer, sizeof sent0);
        for (int c = 4; c < 12; ++c) SendBuffer[c] = 1600;                                  // (the knob's channel moves meanwhile: a live marker would be ticked)
        { const uint32_t lost0 = BoxesLost; run(90);                                        // four and a half seconds - longer than the three tries would take:
          CHECK(asRead() && JobsIsDue() && cmdValue("bar.d0") == -9999 && boxesLostTold == 0);   //  nothing drawn, nothing said,
          CHECK(BoxesLost == lost0);                                                        //  nothing ASKED (no try is used up while the screen cannot be asked),
          CHECK(cmdValue("bar.mk") == -9999); }                                             //  and no live marker onto a page that is not drawn
        noPage = false; fieldsLost.clear(); run(25);
        CHECK(!JobsIsDue() && AdjRows[0].v[1] == 130 && AdjRows[0].v[0] == 60 && cmdValue("bar.d0") == 1000 && fields["bar"] == "|60 to 130|" && boxesLostTold == 0);
        CHECK(cmdValue("bar.mk") != -9999);                                                 // (... and the marker again, once the page is this board's)
        memcpy(SendBuffer, sent0, sizeof sent0);
        // (d2) ... loaded again BY THE SCREEN (its keypad closing - no page command of this board's: the count of them tells nothing), its word comes,
        //      and a box of its gather has no answer: THE WORD ITSELF makes the page due, and the main loop draws it when the screen can be asked
        setup(); attrs.clear(); attrs["bar.d0"] = 1500; attrs["bar.d1"] = 1700; attrs["bar.tap"] = -1; fields["tk1"] = "130"; cmds.clear(); noPage = true; fieldsLost.insert("tk0"); BoxesLostAtWork = BoxesLost;
        CHECK(!JobsIsDue());
        JobsPageBack();
        CHECK(asRead() && JobsIsDue() && cmdValue("bar.d0") == -9999);
        run(30); noPage = false; fieldsLost.clear(); run(25);
        CHECK(!JobsIsDue() && AdjRows[0].v[1] == 130 && cmdValue("bar.d0") == 1000 && attrs["bar.own"] == (int) JobsBarToken && boxesLostTold == 0);
        // (e) ... the screen CAN be asked and a box goes on having no answer: three tries, a second apart, the last one said - and then no more
        //     (the next touch of the page draws it)
        setup(); reload(); cmds.clear(); fieldsLost.insert("tk1"); BoxesLostAtWork = BoxesLost;
        { const uint32_t lost0 = BoxesLost; run(200);
          CHECK(JobsIsDue() && asRead() && BoxesLost - lost0 == 3 && boxesLostTold == 1 && cmdValue("bar.d0") == -9999); }
        fieldsLost.clear(); attrs["bar.tap"] = -1; BoxesLostAtWork = BoxesLost; JobsBarMoved();
        CHECK(!JobsIsDue() && asRead() && cmdValue("bar.d0") == 1000);
        // (f) the token itself has no answer: nothing of the bar is taken, the page is due, and the main loop draws it
        setup(); attrs["bar.d0"] = 1500; attrs["bar.d1"] = 1700; attrs["bar.tap"] = -1; attrsLost.insert("bar.own"); cmds.clear(); BoxesLostAtWork = BoxesLost;
        JobsBarMoved();
        CHECK(asRead() && !Adj_Was_Edited && JobsIsDue() && cmdValue("bar.d0") == -9999);
        attrsLost.clear(); run(25); CHECK(!JobsIsDue() && cmdValue("bar.d0") == 1000 && asRead());
        // (g) the bar is this board's and ONE OF ITS DIVIDERS has no answer: neither is taken (it was: the one that answered), and the bar is drawn
        //     again as it is in hand
        setup(); attrs["bar.d0"] = 1100; attrs["bar.d1"] = 1900; attrs["bar.tap"] = -1; attrsLost.insert("bar.d1"); cmds.clear(); BoxesLostAtWork = BoxesLost;
        JobsBarMoved();
        CHECK(asRead() && !Adj_Was_Edited && JobsIsDue());
        attrsLost.clear(); run(25); CHECK(!JobsIsDue() && cmdValue("bar.d0") == 1000 && cmdValue("bar.d1") == 2000);
        // (h) a SWITCH job's bar, the page loaded again and its word lost: the card's 1500 to 1700 is not made the switch's ON zone
        setup(); JobAt = 1; JobsShow(); run(2); CHECK(SwNow[SwShown[1]].lo == 1700 && SwNow[SwShown[1]].hi == 2125 && !JobsIsDue());
        reload(); cmds.clear(); BoxesLostAtWork = BoxesLost; JobsBarMoved();
        CHECK(SwNow[SwShown[1]].lo == 1700 && SwNow[SwShown[1]].hi == 2125 && !Sw_Was_Edited && cmdValue("bar.d0") == 1700 && !JobsIsDue());
        // (i) nothing is due on another page, and the count of this board's page commands does not make the page due while it is being read
        setup(); CurrentView = 47; ++ScreenMarkCount; cmds.clear(); run(60); CHECK(cmdValue("bar.d0") == -9999);
        CurrentView = ADJUSTVIEW; saveNowAnswer = 0;
        // (j) NOTHING HAS BEEN READ (the read failed - its box leaves the page; should this board still believe the page): the main loop draws nothing
        //     for a page that is "due" - there is nothing of this board's to draw (it would have drawn the rows of the visit before)
        setup(); SwHave = false; ++ScreenMarkCount; cmds.clear(); fields["tn0"] = "as it stood"; run(80);
        CHECK(JobsIsDue() && cmdValue("bar.d0") == -9999 && fields["tn0"] == "as it stood");
        SwHave = true;
        // (k) (the twelfth review; the author's own, found by a scene of the Sub-trim page) THE SECOND IS COUNTED WITH A SIGN. The moment the page was
        //     first seen due is kept as "now | 1" (0 means "not seen") - in an EVEN millisecond that is one millisecond AHEAD, and counted unsigned
        //     the next pass of the main loop in that same millisecond read "49 days gone": the first try came at once - on top of the page's own word
        setup(); now = (now | 1) + 1; ++ScreenMarkCount; cmds.clear();                      // (an even millisecond; the page put up again)
        JobsPoll(); CHECK(JobsIsDue() && JobsDueMs == now + 1 && JobsDueTries == 0);
        JobsPoll(); JobsPoll(); CHECK(JobsIsDue() && JobsDueTries == 0 && cmdValue("bar.d0") == -9999);   // the same millisecond: no try, nothing drawn
        now += 900; JobsPoll(); CHECK(JobsDueTries == 0 && cmdValue("bar.d0") == -9999);
        now += 110; JobsPoll(); CHECK(!JobsIsDue() && cmdValue("bar.d0") == 1000);          // a second on: drawn
    }
    printf("test_jobs: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
import atexit, shutil as _sh; atexit.register(_sh.rmtree, d, True)
r = subprocess.run(['clang++', '-std=c++14', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
