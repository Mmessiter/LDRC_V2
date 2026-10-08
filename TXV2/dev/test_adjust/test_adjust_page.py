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
static uint16_t SendBuffer[17] = {1500, 1500, 1000, 1500, 1500, 1500, 1700, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 0};
static uint32_t now = 1000;
static uint32_t millis() { return now; }
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
static long FieldNumber(const char *name, long lo, long hi) { long v = atol(fields[name].c_str()); return v < lo ? lo : v > hi ? hi : v; }
static std::map<std::string, int> attrs; static int GetOtherValue(char *n) { return attrs.count(n) ? attrs[n] : 0; }   // the bar's handles, as the screen holds them
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
    // the flight controller: a PID-bank switch on AUX1 (3 positions), a Yaw P knob on AUX3 in bank 2, a Pitch rate nudge
    putLine(0, 2, 0, 875, 1300, 0, 875, 1300, 1500, 1500, 1, 1, 0); putLine(1, 2, 0, 1300, 1700, 0, 1300, 1700, 1500, 1500, 2, 2, 0); putLine(2, 2, 0, 1700, 2125, 0, 1700, 2125, 1500, 1500, 3, 3, 0);
    putLine(3, 22, 0, 1300, 1700, 2, 1000, 2000, 1500, 1500, 60, 120, 0);
    putLine(4, 8, 4, 875, 2125, 4, 875, 1300, 1700, 2125, 20, 100, 2);
    ratesImg[0] = 6; for (int i = 1; i < 40; ++i) ratesImg[i] = i; ratesImg[7] = 48;   // Pitch Rate stored 48 -> shown 240
    for (int i = 0; i < 34; ++i) pidImg[i] = 0; pidImg[16] = 95; pidImg[8] = 55;       // Yaw P 95 (bytes 16-17), Pitch P 55 (bytes 8-9)
    // 1. open: the read, the first row shown
    StartAdjustView(); CHECK(CurrentView == ADJUSTVIEW && fcLog.size() == 1 && fcLog[0].fn == 111);
    run(4);
    CHECK(AdjHave && AdjN == 3 && AdjAt == 0 && fields["t0"] == "Adjustment 1 of 3" && fields["tn0"] == "PID bank switch (1 to 6)" && fields["tn1"] == "Channel 6: AUX1" && fields["tn2"] == "Switch 3" && fields["tn3"] == "Any");
    CHECK(fields["tn4"] == "1" && fields["tn5"] == "2" && fields["tn6"] == "3");
    CHECK(fields["tn8"] == "Now 1500 us: position 2 = 2" && cmdValue("bar.mk") == 1500 && cmdValue("bar.n") == 3 && cmdValue("bar.d0") == 1300 && cmdValue("bar.d1") == 1700 && fields["bar"] == "1 = 1|2 = 2|3 = 3");
    // the second row: the knob in bank 2, with its present value read from the PIDs (bank 2 is the bank in use)
    AdjustNext(); run(6);
    CHECK(AdjAt == 1 && fields["tn0"] == "Yaw P gain" && fields["tn1"] == "Channel 8: AUX3" && fields["tn2"] == "Knob" && fields["tn3"] == "Bank 2" && fields["tn4"] == "60" && fields["tn5"] == "120");
    CHECK(cmdValue("bar.kind") == 1 && cmdValue("bar.d0") == 1000 && cmdValue("bar.d1") == 2000 && fields["bar"] == "|60 to 120|" && fields["tn8"] == "Now 1500 us: about 90");
    CHECK(fields["tn7"] == "Now: 95");
    // the third: the nudge, a Rate shown x5
    AdjustNext(); run(6);
    CHECK(AdjAt == 2 && fields["tn0"] == "Pitch top rotation speed (Rate)" && fields["tn2"] == "Up/down" && fields["tn4"] == "2" && fields["tn5"] == "100" && fields["tn6"] == "500");
    CHECK(cmdValue("bar.kind") == 2 && fields["bar"] == "down 2||up 2" && fields["tn8"] == "Now 1500 us: holding");
    CHECK(fields["tn7"] == "Now: 240");
    // 2. edit the knob's high end, save: only line 3 is written, then the store, then the read-back
    AdjustPrevious(); run(6); fields["tn5"] = "130"; AdjustWasEdited(); CHECK(Adj_Was_Edited);
    attrs["bar.d0"] = 1100; attrs["bar.d1"] = 2000; AdjustBarMoved(); CHECK(AdjRows[1].lo == 1100 && AdjRows[1].hi == 2000 && fields["tn8"] == "Now 1500 us: about 91");   // (a handle dragged: the knob's travel)
    fcLog.clear(); busyOnce = 1; SaveAdjustments(); run(30);
    CHECK(writes(53) == 2 && fcLog[0].fn == 53 && fcLog[1].fn == 53 && fcLog[0].data == fcLog[1].data && fcLog[0].data.substr(0, 2) == "03");   // (the 503 answered again)
    CHECK(writes(250) == 1 && writes(52) == 1 && AdjStep_ == ADJ_IDLE && !Adj_Was_Edited && adj[3 * 14 + 11] == 130 && adj[3 * 14 + 12] == 0 && adj[3 * 14 + 5] == stp(1100));
    CHECK(fields["busy"].find("Saved, and read back the same") == 0 && fields["tn5"] == "130");
    // the nudge's Rate goes back /5
    AdjustNext(); run(6); fields["tn6"] = "600"; AdjustWasEdited(); fcLog.clear(); SaveAdjustments(); run(30);
    CHECK(writes(53) == 1 && adj[4 * 14 + 11] == 120 && fields["tn6"] == "600");
    // 3. Add: a knob on the same channel, Pitch P gain, its values from the present value
    fcLog.clear(); AdjustAdd(); run(8);
    CHECK(AdjN == 4 && AdjAt == 3 && fields["tn0"] == "Pitch P gain" && fields["tn2"] == "Knob" && fields["tn3"] == "Any" && fields["tn4"] == "55" && fields["tn5"] == "55" && fields["tn7"] == "Now: 55");
    AdjustBankTapped(); run(2); CHECK(fields["tn3"] == "Bank 1" && fields["tn7"] == "Now: in bank 1 only");   // (bank 1 is not the bank in use: not read)
    AdjustBankTapped(); run(6); CHECK(fields["tn3"] == "Bank 2" && fields["tn7"] == "Now: 55");
    AdjustKindTapped(); CHECK(fields["tn2"] == "Switch 2" && fields["tn4"] == "55" && fields["tn5"] == "55");
    AdjustKindTapped(); CHECK(fields["tn2"] == "Switch 3" && fields["tn6"] == "55");
    fields["tn4"] = "50"; fields["tn6"] = "60"; AdjustChannelNext(); CHECK(fields["tn1"] == "Channel 11: AUX6");   // (Add took the channel of the row showing, the nudge on AUX5)
    fcLog.clear(); SaveAdjustments(); run(40);
    CHECK(writes(53) == 3 && writes(250) == 1 && AdjN == 4);
    { AdjLine L[42]; AdjParseLines(adj, 588, L); int k = 0; for (int i = 0; i < 42; ++i) if (L[i].fn == 14) ++k; CHECK(k == 3); CHECK(L[5].fn == 14 && L[5].adj == 5 && L[5].ena == 0 && L[5].enaLo == 1300 && L[5].enaHi == 1700 && L[5].min == 50 && L[7].min == 60 && L[6].min == 55); }
    // 4. Remove it
    confirmAnswer = true; fcLog.clear(); AdjustRemove(); run(4); CHECK(AdjN == 3 && AdjAt == 2 && Adj_Was_Edited);
    SaveAdjustments(); run(40); CHECK(writes(53) == 3 && AdjN == 3);   // (the three lines blanked)
    // 5. no USB cable: the refusal, in the receiver's words, and back to the menu
    usb = false; boxes = 0; rfStarts = 0; StartAdjustView(); run(6);
    CHECK(boxes == 1 && rfStarts == 1 && lastBox.find("Adjustments need the USB cable") == 0 && lastBox.find("Plug the flight controller's USB") != std::string::npos && CurrentView == 47);
    // 6. no model: refused before anything
    usb = true; BoundFlag = false; boxes = 0; fcLog.clear(); StartAdjustView(); CHECK(boxes == 1 && fcLog.empty() && lastBox.find("Adjustments need the model connected") == 0);
    printf("test_adjust_page: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:4000]); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
