#!/usr/bin/env python3
"""Host test of the adjustments page's flow (B72): include/RF_Adjust.h compiled on the Mac over a fake screen and a fake
flight controller on the fake pipe. The read (rates type, then 52) and what the page shows; the USB refusal (409) which
sends the pilot back to the menu with the receiver's words; Add with the present value read into the new row; a save that
writes only the lines that differ (503 answered again), stores, reads back; Remove; the bank field.
   python3 dev/test_adjust/test_adjust_page.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDR = os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Adjust.h')
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
#define CHANNELSUSED 16
static int CurrentView = 0;
static bool BoundFlag = true, ModelMatched = true;
static char ModelName[20] = "Goblin";
static char ChannelNames[16][11] = {{"Aileron"}, {"Elevator"}, {"Throttle"}, {"Rudder"}, {"Gear"}, {"AUX1"}, {"AUX2"}, {"AUX3"}, {"AUX4"}, {"AUX5"}, {"AUX6"}, {"AUX7"}, {"AUX8"}, {"AUX9"}, {"AUX10"}, {"AUX11"}};
static uint16_t SendBuffer[17] = {1500, 1500, 1000, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 0};
static uint32_t now = 1000;
static uint32_t millis() { return now; }
// ---- this transmitter's outputs per bank (B83: the bank switch is matched to them). The curve is a stub table of
// microseconds per bank and channel; trims, subtrims and reversal are the real formulas with neutral values
#define BANKS_USED 4
#define MINMICROS 1000
#define MAXMICROS 2000
static uint8_t Bank = 2;
static uint8_t ChannelOutPut[17] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15};
static uint8_t DualRateValue = 100;
static uint8_t InterpolationTypes[5][17] = {{0}};
static uint16_t InputsBuffer[17] = {0};
static uint8_t InPutStick[16] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15};
static uint8_t SubTrims[16] = {127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127};
static uint16_t ReversedChannelBITS = 0;
static int GetTrimAmount(uint8_t) { return 0; }
static void GetCurveDots(uint16_t, uint16_t) {}
static uint16_t txUs[5][16];   // [bank][channel 0-based]: what the stub curve gives
static uint16_t stubInterp(uint16_t, uint16_t, uint16_t ch) { return txUs[Bank][ch]; }
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
static bool BakOffline() { return false; }   // (the backup's stand-in: not in this test)
static long FieldNumber(const char *name, long lo, long hi) { long v = atol(fields[name].c_str()); return v < lo ? lo : v > hi ? hi : v; }
static std::map<std::string, int> attrs; static int GetOtherValue(char *n) { return attrs.count(n) ? attrs[n] : 0; }
static std::map<std::string, int> vals; static void SendValue(char *n, int v) { vals[n] = v; } static uint32_t GetValue(char *n) { return (uint32_t) (vals.count(n) ? vals[n] : 0); }
#define ADJPICKVIEW 68   // the bar's handles, as the screen holds them
static int cmdValue(const char *attr) { for (int i = (int) cmds.size() - 1; i >= 0; --i) { const std::string pre = std::string(attr) + "="; if (cmds[i].rfind(pre, 0) == 0) return atoi(cmds[i].c_str() + pre.size()); } return -9999; }
// ---- the pipe and a fake flight controller
static int PipeReqId = 0, PipeRepId = -1, PipeRepCode = 0; static char PipeRepBody[1600] = ""; static uint32_t PipeReqSentMs = 0;
bool PipeReplyReady(int id) { return PipeRepId == id; }
bool PipeReplyLate() { return false; }
int PipeReplyBytes(uint8_t *out, int max) { int n = 0; const char *p = PipeRepBody; while (p[0] && p[1] && n < max) { char h[3] = {p[0], p[1], 0}; out[n++] = (uint8_t) strtol(h, nullptr, 16); p += 2; } return n; }
struct FcReq { int fn; std::string data; };
static std::vector<FcReq> fcLog;
static std::string hexOf(const uint8_t *d, int n) { char b[4]; std::string s; for (int i = 0; i < n; ++i) { snprintf(b, sizeof b, "%02X", d[i]); s += b; } return s; }
static uint8_t adj[588]; static bool usb = true; static int busyOnce = 0; static uint8_t pidImg[34], ratesImg[40]; static int pidBank = 1, rateBank = 0;
static void fcReply(int code, const std::string &body) { PipeRepCode = code; strncpy(PipeRepBody, body.c_str(), sizeof(PipeRepBody) - 1); PipeRepBody[sizeof(PipeRepBody) - 1] = 0; PipeRepId = PipeReqId; }
int MspAsk(uint8_t fn, const uint8_t *data, int len) {
    ++PipeReqId; PipeReqSentMs = now; fcLog.push_back({fn, hexOf(data, len)});
    if (busyOnce > 0) { --busyOnce; fcReply(503, "busy with a transmitter edit"); return PipeReqId; }
    if (fn == 52) { if (!usb) { fcReply(409, "refused: Rotorflight 4.6 cannot send its adjustments list over the receiver link ... Plug the flight controller's USB into the dongle or receiver"); return PipeReqId; } fcReply(200, hexOf(adj, 588)); return PipeReqId; }
    if (fn == 53 && len == 15) { const int i = data[0]; if (i < 42) memcpy(adj + i * 14, data + 1, 14); fcReply(200, ""); return PipeReqId; }
    if (fn == 250) { fcReply(200, ""); return PipeReqId; }
    if (fn == 111) { fcReply(200, hexOf(ratesImg, 40)); return PipeReqId; }
    if (fn == 112) { fcReply(200, hexOf(pidImg, 34)); return PipeReqId; }
    if (fn == 101) { uint8_t b[32] = {0}; b[23] = pidBank; b[25] = rateBank; fcReply(200, hexOf(b, 32)); return PipeReqId; }
    fcReply(404, "unknown"); return PipeReqId;
}
''' + open(HDR).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void run(int n = 20) { for (int i = 0; i < n; ++i) { AdjustPoll(); now += 50; } }
static int writes(int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; }
static uint8_t stp(int us) { int st = (int) floorf((us - 1500) / 5.0f + 0.5f); return (uint8_t) (st < 0 ? st + 256 : st); }
static void putLine(int i, int fn, int ena, int enaLo, int enaHi, int ch, int a1Lo, int a1Hi, int a2Lo, int a2Hi, int mn, int mx, int st) {
    uint8_t *o = adj + i * 14; o[0] = fn; o[1] = ena; o[2] = stp(enaLo); o[3] = stp(enaHi); o[4] = ch; o[5] = stp(a1Lo); o[6] = stp(a1Hi); o[7] = stp(a2Lo); o[8] = stp(a2Hi); o[9] = mn & 255; o[10] = mn >> 8; o[11] = mx & 255; o[12] = mx >> 8; o[13] = st;
}
int main() {
    memset(adj, 0, sizeof adj); for (int i = 0; i < 42; ++i) putLine(i, 0, 0, 1500, 1500, 0, 1500, 1500, 1500, 1500, 0, 0, 0);
    // this transmitter: channel 6 (AUX1) carries the bank as a value, Black Thunder 2's way (13, 54, 90, 151 degrees in
    // banks 1 to 4); every other channel sits at 1500 in every bank
    for (int b = 0; b <= 4; ++b) for (int c = 0; c < 16; ++c) txUs[b][c] = 1500;
    txUs[1][5] = 1072; txUs[2][5] = 1300; txUs[3][5] = 1500; txUs[4][5] = 1839;
    const int fc1 = AdjFcUs(1072), fc2 = AdjFcUs(1300), fc3 = AdjFcUs(1500), fc4 = AdjFcUs(1839);   // 1062, 1296, 1500, 1847
    CHECK(fc1 == 1062 && fc2 == 1296 && fc3 == 1500 && fc4 == 1847);
    Bank = 2; SendBuffer[5] = 1300;
    // the flight controller: a PID-bank switch on AUX1 in the OLD form (3 lines, one per zone: applied once only), a Yaw P
    // knob on AUX3 in bank 2 (the old zone 2), a Pitch rate nudge
    putLine(0, 2, 0, 875, 1300, 0, 875, 1300, 1500, 1500, 1, 1, 0); putLine(1, 2, 0, 1300, 1700, 0, 1300, 1700, 1500, 1500, 2, 2, 0); putLine(2, 2, 0, 1700, 2125, 0, 1700, 2125, 1500, 1500, 3, 3, 0);
    putLine(3, 22, 0, 1300, 1700, 2, 1000, 2000, 1500, 1500, 60, 120, 0);
    putLine(4, 8, 4, 875, 2125, 4, 875, 1300, 1700, 2125, 20, 100, 2);
    ratesImg[0] = 6; for (int i = 1; i < 40; ++i) ratesImg[i] = i; ratesImg[7] = 48;   // Pitch Rate stored 48 -> shown 240
    for (int i = 0; i < 34; ++i) pidImg[i] = 0; pidImg[16] = 95; pidImg[8] = 55;       // Yaw P 95 (bytes 16-17), Pitch P 55 (bytes 8-9)
    // 1. open: the read; the old-form bank switch is put into Rotorflight's own form AND matched to this transmitter's
    // banks (its ends bank 1's and bank 4's values), said in the banner, to be saved
    StartAdjustView(); CHECK(CurrentView == ADJUSTVIEW && fcLog.size() == 1 && fcLog[0].fn == 111);
    run(4);
    CHECK(AdjHave && AdjN == 3 && AdjAt == 0 && fields["t0"] == "Adjustment 1 of 3" && fields["tn0"] == "PID bank switch (1 to 6)" && fields["tn1"] == "Channel 6: AUX1" && fields["tn3"] == "in any bank");
    if (fields["tn2"] != "Banks 1 to 4 of this transmitter") fprintf(stderr, "tn2 = '%s' busy = '%s' lo %d hi %d n %d\n", fields["tn2"].c_str(), fields["busy"].c_str(), AdjRows[0].lo, AdjRows[0].hi, AdjRows[0].n);
    CHECK(fields["tn2"] == "Banks 1 to 4 of this transmitter" && AdjRows[0].legacy && AdjRows[0].kind == AK_SWITCH && AdjRows[0].n == 4 && AdjRows[0].lo == 1060 && AdjRows[0].hi == 1845);   // (the ends in Rotorflight's 5 us steps)
    CHECK(Adj_Was_Edited && fields["busy"] == "1 switch in the old once-only form: put right, press Save");
    CHECK(fields["tp0"] == "1" && fields["tp1"] == "2" && fields["tp2"] == "3" && fields["tp3"] == "4");   // (the boxes the keypad edits, out of sight)
    CHECK(cmds.size() && std::find(cmds.begin(), cmds.end(), "vis tn3,0") != cmds.end());   // (a bank switch: no bank box)
    CHECK(cmdValue("bar.kind") == 4 && cmdValue("bar.n") == 4 && cmdValue("bar.d0") == 1060 && cmdValue("bar.d1") == 1845 && fields["bar"] == "1|2|3|4" && cmdValue("bar.mk") == fc2);
    if (fields["tn8"] != "Bank 2: 1296 us") fprintf(stderr, "tn8 = '%s'\n", fields["tn8"].c_str());
    CHECK(fields["tn8"] == "Bank 2: 1296 us");   // (this transmitter's bank, and Rotorflight picks the same from the channel)
    { int t[6]; AdjThresholds(1060, 1845, 4, t); CHECK(t[0] == 1191 && t[1] == 1453 && t[2] == 1715); }
    // the second row: the knob in bank 2 - the old zone 2 (1300..1700) became the new bank 2 - with its present value read from the PIDs (bank 2 is the bank in use)
    cmds.clear(); AdjustNext(); run(6);
    CHECK(std::find(cmds.begin(), cmds.end(), "vis tn3,1") != cmds.end());   // (a gain: the bank box shows)
    if (fields["tn3"] != "in bank 2") fprintf(stderr, "tn3 = '%s' ena %d %d-%d regions 2: %d-%d\n", fields["tn3"].c_str(), AdjRows[1].ena, AdjRows[1].enaLo, AdjRows[1].enaHi, AdjBk.lo[2], AdjBk.hi[2]);
    CHECK(AdjAt == 1 && fields["tn0"] == "Yaw P gain" && fields["tn1"] == "Channel 8: AUX3" && fields["tn2"] == "Knob" && fields["tn3"] == "in bank 2" && fields["tk0"] == "60" && fields["tk1"] == "120");
    CHECK(cmdValue("bar.kind") == 1 && cmdValue("bar.d0") == 1000 && cmdValue("bar.d1") == 2000 && fields["bar"] == "|60 to 120|" && fields["tn8"] == "Knob 1500 us: 90");
    CHECK(AdjNowKnown && AdjNow == 95);
    // the third: the nudge, a Rate shown x5
    AdjustNext(); run(6);
    CHECK(AdjAt == 2 && fields["tn0"] == "Pitch top rotation speed (Rate)" && fields["tn2"] == "Step up / down" && fields["ts0"] == "2" && fields["ts1"] == "100" && fields["ts2"] == "500");
    CHECK(cmdValue("bar.kind") == 2 && fields["bar"] == "down 2|100 to 500|up 2" && fields["tn8"] == "Holding: 1500 us");
    CHECK(AdjNow == 240);
    // 2. save as it stands: the bank switch's three lines become one, and the lines close up (the knob to slot 1 with its
    // bank condition on the new divisions, the nudge to slot 2, slots 3 and 4 blanked: five writes); then the store and the read-back
    fcLog.clear(); SaveAdjustments(); run(40);
    if (writes(53) != 5) { fprintf(stderr, "writes 53 %d 250 %d 52 %d step %d edited %d boxes %d last '%s' busy '%s'\n", writes(53), writes(250), writes(52), AdjStep_, Adj_Was_Edited, boxes, lastBox.c_str(), fields["busy"].c_str()); for (auto &r : fcLog) fprintf(stderr, "  fn %d %s\n", r.fn, r.data.c_str()); }
    CHECK(writes(53) == 5 && writes(250) == 1 && writes(52) == 1 && AdjStep_ == ADJ_IDLE && !Adj_Was_Edited);
    { AdjLine L[42]; AdjParseLines(adj, 588, L);
      CHECK(L[0].fn == 2 && L[0].adj == 0 && L[0].ena == 0 && L[0].enaLo == 875 && L[0].enaHi == 2125 && L[0].a1Lo == 1060 && L[0].a1Hi == 1845 && L[0].min == 1 && L[0].max == 4 && L[0].stp == 0);
      CHECK(L[1].fn == 22 && L[1].ena == 0 && L[2].fn == 8 && L[3].fn == 0 && L[4].fn == 0);
      AdjBanks bk; AdjBankRegions(AdjRows, AdjN, bk); CHECK(bk.have && L[1].enaLo == bk.lo[2] && L[1].enaHi == bk.hi[2] && bk.lo[2] > 1150 && bk.hi[2] < 1500); }
    if (fields["busy"].find("Saved, and read back the same") != 0) fprintf(stderr, "busy '%s' legacy %d lo %d tn3 '%s' tn2 '%s' at %d\n", fields["busy"].c_str(), AdjRows[0].legacy, AdjRows[0].lo, fields["tn3"].c_str(), fields["tn2"].c_str(), AdjAt);
    CHECK(fields["busy"].find("Saved, and read back the same") == 0 && !AdjRows[0].legacy && AdjRows[0].lo == 1060);
    // the matched bank switch, read back, stays matched (no banner): every bank in its own zone
    CHECK(AdjBankRowRight(AdjRows[0]) && AdjBankFitted[0]);
    // 3. edit the knob's high end, save: only its line (1) is written
    AdjustPrevious(); run(6); CHECK(AdjAt == 1 && fields["tn0"] == "Yaw P gain" && fields["tn3"] == "in bank 2");
    // a tap on the knob's zone, right half: the high end's box is clicked (the keypad opens); the page comes back with 130 typed
    attrs["bar.tap"] = 1800; cmds.clear(); AdjustBarMoved(); CHECK(cmds.size() == 1 && cmds[0] == "click tk1,0");
    attrs["bar.tap"] = -1; fields["tk1"] = "130"; AdjustWasEdited(); AdjustPageBack(); CHECK(Adj_Was_Edited && AdjRows[1].v[1] == 130 && fields["bar"] == "|60 to 130|");
    attrs["bar.d0"] = 1100; attrs["bar.d1"] = 2000; attrs["bar.tap"] = -1; AdjustBarMoved(); CHECK(AdjRows[1].lo == 1100 && AdjRows[1].hi == 2000 && fields["tn8"] == "Knob 1500 us: 91");   // (a handle dragged: the knob's travel)
    fcLog.clear(); busyOnce = 1; SaveAdjustments(); run(30);
    CHECK(writes(53) == 2 && fcLog[0].fn == 53 && fcLog[1].fn == 53 && fcLog[0].data == fcLog[1].data && fcLog[0].data.substr(0, 2) == "01");   // (the 503 answered again)
    CHECK(writes(250) == 1 && writes(52) == 1 && AdjStep_ == ADJ_IDLE && !Adj_Was_Edited && adj[1 * 14 + 11] == 130 && adj[1 * 14 + 12] == 0 && adj[1 * 14 + 5] == stp(1100));
    CHECK(fields["busy"].find("Saved, and read back the same") == 0 && fields["tk1"] == "130");
    // the nudge's Rate goes back /5
    AdjustNext(); run(6); fields["ts2"] = "600"; AdjustWasEdited(); fcLog.clear(); SaveAdjustments(); run(30);
    CHECK(writes(53) == 1 && adj[2 * 14 + 11] == 120 && fields["ts2"] == "600");
    // 4. Add: a knob on the same channel, Pitch P gain, its values from the present value
    fcLog.clear(); AdjustAdd(); run(8);
    CHECK(AdjN == 4 && AdjAt == 3 && fields["tn0"] == "Pitch P gain" && fields["tn2"] == "Knob" && fields["tn3"] == "in any bank" && fields["tk0"] == "55" && fields["tk1"] == "55" && AdjNow == 55);
    AdjustBankTapped(); run(2); CHECK(fields["tn3"] == "in bank 1" && AdjNowBank == 1);   // (bank 1 is not the bank in use: not read)
    AdjustBankTapped(); run(6); CHECK(fields["tn3"] == "in bank 2" && AdjNow == 55);
    // the kind: a 2-position switch over a switch's travel, then 3, then 4 positions (the values evenly between the ends)
    AdjustKindTapped(); CHECK(fields["tn2"] == "Switch, 2 positions" && fields["tp0"] == "55" && fields["tp1"] == "56" && cmdValue("bar.kind") == 3 && cmdValue("bar.d0") == 988 && cmdValue("bar.d1") == 2012);
    AdjustKindTapped(); CHECK(fields["tn2"] == "Switch, 3 positions" && fields["tp2"] == "56");
    // the picker: Pitch P gain is first in its wheel; Yaw P gain chosen
    AdjustSettingNext(); CHECK(CurrentView == ADJPICKVIEW && vals["list"] == 9);
    vals["list"] = 17; AdjustPickOk(); CHECK(CurrentView == ADJUSTVIEW && fields["tn0"] == "Yaw P gain" && AdjRows[3].fn == 22);
    AdjustSettingNext(); AdjustPickCancel(); CHECK(CurrentView == ADJUSTVIEW && AdjRows[3].fn == 22);
    AdjustSettingNext(); vals["list"] = 9; AdjustPickOk(); CHECK(fields["tn0"] == "Pitch P gain" && AdjRows[3].fn == 14); run(6);
    // the first and last positions typed (50 and 60): the middle one is 55, evenly between; a tap on the middle zone types nothing
    fields["tp0"] = "50"; fields["tp2"] = "60"; AdjustChannelNext(); CHECK(fields["tn1"] == "Channel 11: AUX6" && fields["tp1"] == "55");   // (Add took the channel of the row showing, the nudge on AUX5)
    attrs["bar.tap"] = 1500; cmds.clear(); AdjustBarMoved();
    CHECK(std::find_if(cmds.begin(), cmds.end(), [](const std::string &c) { return c.rfind("click", 0) == 0; }) == cmds.end() && fields["busy"].find("Type the first and last") == 0);
    attrs["bar.tap"] = 2000; cmds.clear(); AdjustBarMoved(); CHECK(cmds.size() == 1 && cmds[0] == "click tp2,0"); attrs["bar.tap"] = -1;
    // a save refused while the last position is not above the first; then the switch saved as ONE line, 50 to 60 over 988..2012
    fields["tp2"] = "40"; boxes = 0; fcLog.clear(); SaveAdjustments(); CHECK(boxes == 1 && lastBox.find("Pitch P gain") != std::string::npos && lastBox.find("last position") != std::string::npos && fcLog.empty());
    fields["tp2"] = "60"; AdjustPageBack(); fcLog.clear(); SaveAdjustments(); run(40);
    CHECK(writes(53) == 1 && writes(250) == 1 && AdjN == 4);
    { AdjLine L[42]; AdjParseLines(adj, 588, L); int k = 0; for (int i = 0; i < 42; ++i) if (L[i].fn == 14) ++k; CHECK(k == 1);
      AdjBanks bk; AdjBankRegions(AdjRows, AdjN, bk);
      if (L[3].fn != 14) fprintf(stderr, "L[3] fn %d adj %d ena %d %d-%d min %d max %d a1 %d-%d\n", L[3].fn, L[3].adj, L[3].ena, L[3].enaLo, L[3].enaHi, L[3].min, L[3].max, L[3].a1Lo, L[3].a1Hi);
      CHECK(L[3].fn == 14 && L[3].adj == 5 && L[3].ena == 0 && L[3].enaLo == bk.lo[2] && L[3].enaHi == bk.hi[2] && L[3].min == 50 && L[3].max == 60 && L[3].a1Lo == 990 && L[3].a1Hi == 2010 && L[3].stp == 0); }
    if (fields["tp1"] != "55") fprintf(stderr, "after save: tn2 '%s' tp0 '%s' tp1 '%s' tp2 '%s' at %d n %d\n", fields["tn2"].c_str(), fields["tp0"].c_str(), fields["tp1"].c_str(), fields["tp2"].c_str(), AdjAt, AdjN);
    CHECK(fields["tn2"] == "Switch, 3 positions" && fields["tp0"] == "50" && fields["tp1"] == "55" && fields["tp2"] == "60");   // (read back as the same switch)
    // 5. Remove it
    confirmAnswer = true; fcLog.clear(); AdjustRemove(); run(4); CHECK(AdjN == 3 && AdjAt == 2 && Adj_Was_Edited);
    SaveAdjustments(); run(40); CHECK(writes(53) == 1 && AdjN == 3);   // (the one line blanked)
    // 6. a rates-bank line in Rotorflight's own form on AUX2 (channel 7, 1500 in every bank here): it cannot be matched to this
    // transmitter's banks (the channel tells no banks apart), so it is shown as it is, with handles, and the kind tap says why
    putLine(8, 1, 1, 875, 2125, 1, 875, 2125, 1500, 1500, 1, 4, 0);
    confirmAnswer = true; StartAdjustView(); run(6); AdjustNext(); AdjustNext(); AdjustNext(); run(4);
    CHECK(AdjN == 4 && fields["tn0"] == "Rates bank switch (1 to 6)" && fields["tn2"] == "Switch, 4 positions" && fields["bar"] == "1|2|3|4" && cmdValue("bar.kind") == 3 && cmdValue("bar.d0") == 875 && cmdValue("bar.d1") == 2125 && !Adj_Was_Edited);
    boxes = 0; AdjustKindTapped();
    CHECK(boxes == 1 && lastBox.find("Channel 7 has no value of its own") == 0 && !Adj_Was_Edited);
    // moved to channel 6 it is matched at once
    AdjustChannelPrev(); CHECK(fields["tn1"] == "Channel 6: AUX1" && fields["tn2"] == "Banks 1 to 4 of this transmitter" && cmdValue("bar.kind") == 4 && AdjRows[3].lo == 1060 && Adj_Was_Edited);
    // 7. the bank in use is measured: bank 3's value seen on the channel beats the computed one; a bank 3 that now sits in
    // bank 2's zone has the ends re-fitted (the live line says so first)
    AdjustPrevious(); AdjustPrevious(); AdjustPrevious(); run(4); CHECK(AdjAt == 0 && fields["tn2"] == "Banks 1 to 4 of this transmitter");
    Bank = 3; SendBuffer[5] = 1500; run(8); CHECK(fields["tn8"] == "Bank 3: 1500 us" && AdjSeenUs[3][5] == 1500);
    // 8. no USB cable: the refusal, in the receiver's words, and back to the menu
    usb = false; boxes = 0; rfStarts = 0; StartAdjustView(); run(6);
    CHECK(boxes == 1 && rfStarts == 1 && lastBox.find("Adjustments need the USB cable") == 0 && lastBox.find("Plug the flight controller's USB") != std::string::npos && CurrentView == 47);
    // 9. no model: refused before anything
    usb = true; BoundFlag = false; boxes = 0; fcLog.clear(); StartAdjustView(); CHECK(boxes == 1 && fcLog.empty() && lastBox.find("Adjustments need the model connected") == 0);
    printf("test_adjust_page: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:4000]); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
