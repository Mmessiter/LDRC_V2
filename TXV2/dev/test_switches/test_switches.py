#!/usr/bin/env python3
"""Host test of the Switches page (B77): include/RF_Switches.h compiled on the Mac over a fake screen and a fake flight
controller on the fake pipe. The read of the 20 slots and what the page shows; the blobs dragged; Add through the picker
(a free slot, ON in the upper third); Remove (an empty zone); the arm rules (the arming channel, the zone must not reach
988 and must reach 2012, never removed); a save that writes only the slots that differ, stores and reads back.
   python3 dev/test_switches/test_switches.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDR = os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Switches.h')
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
static std::map<std::string, std::string> fields; static std::vector<std::string> cmds; static int boxes = 0; static std::string lastBox; static bool confirmAnswer = true; static int sounds = 0, rfStarts = 0;
static void SendCommand(char *c) { cmds.push_back(c); }
static void SendText(char *n, char *t) { fields[n] = t; }
static void MsgBox(char *page, const char *msg) { ++boxes; lastBox = msg; }
static bool GetConfirmation(char *page, char *prompt) { lastBox = prompt; return confirmAnswer; }
static void PlaySound(int) { ++sounds; }
static void RotorFlightStart() { ++rfStarts; CurrentView = 47; }
static bool ModelSeemsArmed(char *, int) { return false; }
static bool RfPipeBlocked(char *, int) { return false; }
static bool RfNeedsModel(char *, int) { return false; }
static std::map<std::string, int> attrs; static int GetOtherValue(char *n) { return attrs.count(n) ? attrs[n] : 0; }
static std::map<std::string, int> vals; static void SendValue(char *n, int v) { vals[n] = v; } static uint32_t GetValue(char *n) { return (uint32_t) (vals.count(n) ? vals[n] : 0); }
static int cmdValue(const char *attr) { for (int i = (int) cmds.size() - 1; i >= 0; --i) { const std::string pre = std::string(attr) + "="; if (cmds[i].rfind(pre, 0) == 0) return atoi(cmds[i].c_str() + pre.size()); } return -9999; }
static int PipeReqId = 0, PipeRepId = -1, PipeRepCode = 0; static char PipeRepBody[1600] = ""; static uint32_t PipeReqSentMs = 0;
bool PipeReplyReady(int id) { return PipeRepId == id; }
bool PipeReplyLate() { return false; }
int PipeReplyBytes(uint8_t *out, int max) { int n = 0; const char *p = PipeRepBody; while (p[0] && p[1] && n < max) { char h[3] = {p[0], p[1], 0}; out[n++] = (uint8_t) strtol(h, nullptr, 16); p += 2; } return n; }
struct FcReq { int fn; std::string data; };
static std::vector<FcReq> fcLog;
static std::string hexOf(const uint8_t *d, int n) { char b[4]; std::string s; for (int i = 0; i < n; ++i) { snprintf(b, sizeof b, "%02X", d[i]); s += b; } return s; }
static uint8_t modes[80]; static int busyOnce = 0;
static void fcReply(int code, const std::string &body) { PipeRepCode = code; strncpy(PipeRepBody, body.c_str(), sizeof(PipeRepBody) - 1); PipeRepBody[sizeof(PipeRepBody) - 1] = 0; PipeRepId = PipeReqId; }
int MspAsk(uint8_t fn, const uint8_t *data, int len) {
    ++PipeReqId; PipeReqSentMs = now; fcLog.push_back({fn, hexOf(data, len)});
    if (busyOnce > 0) { --busyOnce; fcReply(503, "busy"); return PipeReqId; }
    if (fn == 34) { fcReply(200, hexOf(modes, 80)); return PipeReqId; }
    if (fn == 35 && len == 5) { const int i = data[0]; if (i < 20) memcpy(modes + i * 4, data + 1, 4); fcReply(200, ""); return PipeReqId; }
    if (fn == 250) { fcReply(200, ""); return PipeReqId; }
    fcReply(404, "unknown"); return PipeReqId;
}
''' + open(HDR).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void run(int n = 20) { for (int i = 0; i < n; ++i) { SwitchPoll(); now += 50; } }
static int writes(int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; }
static uint8_t stp(int us) { int st = (int) floorf((us - 1500) / 5.0f + 0.5f); return (uint8_t) (st < 0 ? st + 256 : st); }
static void slot(int i, int perm, int aux, int lo, int hi) { modes[i * 4] = perm; modes[i * 4 + 1] = aux; modes[i * 4 + 2] = stp(lo); modes[i * 4 + 3] = stp(hi); }
int main() {
    for (int i = 0; i < 20; ++i) slot(i, 0, 0, 1500, 1500);
    slot(0, 0, 0, 1500, 2125);      // ARM on AUX1 (channel 6), ON above 1500
    slot(1, 53, 2, 1700, 2125);     // RESCUE on AUX3 (channel 8)
    slot(3, 26, 1, 1300, 1700);     // BLACKBOX on AUX2, the middle
    // 1. open: the read, the first action shown (the arm switch), the marker where the safety switch has the channel
    StartSwitchView(); run(4);
    CHECK(CurrentView == SWITCHVIEW && SwHave && SwN == 3 && SwAt == 0 && fields["t0"] == "Switch 1 of 3" && fields["tn0"] == "Arm - motor enable (ARM)" && fields["tn1"] == "Channel 6: AUX1");
    CHECK(cmdValue("bar.kind") == 1 && cmdValue("bar.d0") == 1500 && cmdValue("bar.d1") == 2125 && cmdValue("bar.mk") == 988 && fields["tn8"] == "OFF: 988 us" && fields["bar"] == "|ON|");
    CHECK(fields["hint"].find("The arm switch is the safety switch") == 0);
    // the rescue: its switch is up (1900 us -> 1910 as the FC sees it): ON
    SwitchNext(); run(2); CHECK(SwAt == 1 && fields["tn0"] == "Rescue - the safety net (RESCUE)" && fields["tn1"] == "Channel 8: AUX3" && fields["tn8"] == "ON: 1909 us" && cmdValue("bar.d0") == 1700);
    SwitchNext(); run(2); CHECK(SwAt == 2 && fields["tn0"] == "Black box recording (BLACKBOX)" && fields["tn8"] == "ON: 1500 us");
    // 2. the blobs dragged on the rescue: the zone follows
    SwitchPrevious(); run(2); attrs["bar.d0"] = 1600; attrs["bar.d1"] = 2125; SwitchBarMoved(); CHECK(Sw_Was_Edited && SwNow[1].lo == 1600 && cmdValue("bar.d0") == 1600);
    // 3. save: only slot 1 is written (the 503 answered again), the store, the read-back
    fcLog.clear(); busyOnce = 1; SaveSwitchActions(); run(30);
    CHECK(writes(35) == 2 && fcLog[0].data == fcLog[1].data && fcLog[0].data.substr(0, 2) == "01" && writes(250) == 1 && writes(34) == 1 && !Sw_Was_Edited && modes[1 * 4 + 2] == stp(1600));
    CHECK(fields["busy"].find("Saved, and read back the same") == 0);
    // 4. the arm rules: the channel stays, the zone may not reach 988 or stop short of 2012, no removing
    SwitchPrevious(); run(2); boxes = 0; SwitchChannelTapped(); CHECK(boxes == 1 && SwNow[0].aux == 0 && lastBox.find("The arm switch stays on this model") == 0);
    attrs["bar.d0"] = 980; attrs["bar.d1"] = 2125; SwitchBarMoved(); boxes = 0; fcLog.clear(); SaveSwitchActions(); run(4); CHECK(boxes == 1 && lastBox.find("The arm zone reaches 988") == 0 && writes(35) == 0);
    attrs["bar.d0"] = 1200; attrs["bar.d1"] = 1900; SwitchBarMoved(); boxes = 0; SaveSwitchActions(); run(4); CHECK(boxes == 1 && lastBox.find("The arm zone stops short of 2012") == 0);
    attrs["bar.d0"] = 1500; attrs["bar.d1"] = 2125; SwitchBarMoved(); boxes = 0; SwitchRemove(); CHECK(boxes == 1 && lastBox.find("The arm switch cannot be removed") == 0 && SwN == 3);
    // 5. Add: the picker opens on Rescue; Self-level chosen: a free slot (slot 2), ON in the upper third of the next channel
    SwitchAdd(); CHECK(CurrentView == SWITCHPICKVIEW && vals["list"] == 1);
    vals["list"] = 2; SwitchPickOk(); run(2);
    CHECK(CurrentView == SWITCHVIEW && SwN == 4 && fields["tn0"] == "Self-level (ANGLE)" && SwNow[2].perm == 1 && SwNow[2].aux == 1 && SwNow[2].lo == 1700 && SwNow[2].hi == 2125 && Sw_Was_Edited);
    CHECK(fields["t0"] == "Switch 3 of 4");   // (slot 2 comes after the rescue in slot 1)
    // the action of an existing row changed through the picker
    SwitchModeTapped(); CHECK(CurrentView == SWITCHPICKVIEW && vals["list"] == 2); vals["list"] = 5; SwitchPickOk(); CHECK(SwNow[2].perm == 47 && fields["tn0"] == "Acro trainer (TRAINER)");
    SwitchModeTapped(); SwitchPickCancel(); CHECK(CurrentView == SWITCHVIEW && SwNow[2].perm == 47);
    // the channel tapped: the next one
    SwitchChannelTapped(); CHECK(SwNow[2].aux == 2 && fields["tn1"] == "Channel 8: AUX3");
    // 6. Remove the black box one, save: two slots written (the new one, the emptied one)
    SwitchNext(); SwitchNext(); run(2); CHECK(fields["tn0"] == "Black box recording (BLACKBOX)");
    confirmAnswer = true; SwitchRemove(); CHECK(SwN == 3 && !SwUsed(SwNow[3]));
    fcLog.clear(); SaveSwitchActions(); run(40);
    CHECK(writes(35) == 2 && writes(250) == 1 && modes[2 * 4] == 47 && modes[2 * 4 + 1] == 2 && modes[3 * 4 + 3] == stp(1500) && SwN == 3);
    // 7. no arm switch at all is refused
    for (int i = 0; i < 20; ++i) slot(i, 0, 0, 1500, 1500); slot(0, 53, 2, 1700, 2125);
    StartSwitchView(); run(4); boxes = 0; SwNow[0].lo = 1600; SwEdited(); SaveSwitchActions(); run(4); CHECK(boxes == 1 && lastBox.find("Rotorflight needs an arm switch") == 0);
    printf("test_switches: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:4000]); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
