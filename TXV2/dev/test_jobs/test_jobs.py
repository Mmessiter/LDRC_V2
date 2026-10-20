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
prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cmath>
#include <string>
#include <map>
#include <vector>
#include <algorithm>
#define DMAMEM
#define FLASHMEM
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
static void SendCommand(char *c) { cmds.push_back(c); }
static void SendText(char *n, char *t) { fields[n] = t; }
static void MsgBox(char *page, const char *msg) { ++boxes; lastBox = msg; }
static bool GetConfirmation(char *page, char *prompt) { lastBox = prompt; return confirmAnswer; }
static void PlaySound(int) { ++sounds; }
static void RotorFlightStart() { ++rfStarts; CurrentView = 47; }
static bool ModelSeemsArmed(char *, int) { return false; }
static bool RfPipeBlocked(char *, int) { return false; }
static bool needModel = false; static bool RfNeedsModel(char *why, int n) { if (needModel) snprintf(why, n, "Switches and knobs need the model connected, or a backup on the card."); return needModel; }
static bool BakOffline() { return false; }
static long FieldNumber(const char *name, long lo, long hi) { long v = atol(fields[name].c_str()); return v < lo ? lo : v > hi ? hi : v; }
static std::map<std::string, int> attrs; static int GetOtherValue(char *n) { return attrs.count(n) ? attrs[n] : 0; }
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
static uint8_t adj[588]; static uint8_t modes[80]; static bool usb = true; static int busyOnce = 0; static uint8_t pidImg[34], ratesImg[40]; static int pidBank = 1, rateBank = 0;
static void fcReply(int code, const std::string &body) { PipeRepCode = code; strncpy(PipeRepBody, body.c_str(), sizeof(PipeRepBody) - 1); PipeRepBody[sizeof(PipeRepBody) - 1] = 0; PipeRepId = PipeReqId; }
int MspAsk(uint8_t fn, const uint8_t *data, int len) {
    ++PipeReqId; PipeReqSentMs = now; fcLog.push_back({fn, hexOf(data, len)});
    if (busyOnce > 0) { --busyOnce; fcReply(503, "busy with a transmitter edit"); return PipeReqId; }
    if (fn == 34) { fcReply(200, hexOf(modes, 80)); return PipeReqId; }
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
static int saveNowAnswer = 0, saveNowAsked = 0;
static bool GetSaveOrDiscard(char *, char *prompt) { ++saveNowAsked; lastBox = prompt; return saveNowAnswer == 1; }
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
    fcLog.clear(); SaveJobs(); run(40);
    CHECK(writes(35) == 2 && writes(250) == 1 && writes(53) == 0 && modes[2 * 4] == 47 && modes[2 * 4 + 1] == 2 && modes[3 * 4 + 3] == stp(1500) && SwN == 3 && !Sw_Was_Edited);
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
    printf("test_jobs: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
import atexit, shutil as _sh; atexit.register(_sh.rmtree, d, True)
r = subprocess.run(['clang++', '-std=c++14', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
