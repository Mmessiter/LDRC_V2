#!/usr/bin/env python3
"""Host test of the flight controller's setup pages (B88): include/RF_FcSetup.h on the Mac over a fake screen and a fake
flight controller on the fake pipe. Battery (32 read, 33 written as its first 15 bytes, the FC pads' sensors 57 / 41 by
id, only when changed; the cell voltages must rise), black box (101 for the loop time, 80, the switches, 70; 81 the 12
bytes; a restart when where or how often changed, then read back; erase = one 72, then 70 until it is empty; the switch
warning), calibrate (240, the level 108 live, 205 then 250 after 2.5 s, the signed trims 239), and the menu's arming line
(101's flags in words, its colour, the whole list on a tap, nothing asked on top of another request).
   python3 dev/test_fcsetup/test_fcsetup.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDR = os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_FcSetup.h')
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
#define ROTORFLIGHTVIEW 47
#define BATTERYVIEW 72
#define BLACKBOXVIEW 73
#define CALIBRATEVIEW 74
static int CurrentView = 0, PipeState = 2;
static bool BoundFlag = true, ModelMatched = true, offline = false;
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
static void RotorFlightStart() { ++rfStarts; CurrentView = 47; }
static bool ModelSeemsArmed(char *, size_t) { return false; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static bool RfNeedsModel(char *, size_t) { return false; }
static bool BakOffline() { return offline; }
static void GetText(char *n, char *out, int len) { snprintf(out, len, "%s", fields[n].c_str()); }
// (the helpers the module shares with RF_Rescue.h and RF_Servos.h, as they are there)
static uint16_t RdU16(const uint8_t *b, int o) { return (uint16_t)(b[o] | (b[o + 1] << 8)); }
static void WrU16(uint8_t *b, int o, long v) { if (v < 0) v = 0; if (v > 65535) v = 65535; b[o] = (uint8_t)(v & 0xFF); b[o + 1] = (uint8_t)(v >> 8); }
static int RdS16(const uint8_t *b, int o) { const int v = b[o] | (b[o + 1] << 8); return v > 32767 ? v - 65536 : v; }
static long FieldNumber(const char *name, long lo, long hi) { char t[24] = ""; GetText((char *)name, t, sizeof(t) - 1); long v = strtol(t, nullptr, 10); return v < lo ? lo : v > hi ? hi : v; }
static int FieldTenths(const char *name, int lo, int hi) { char t[24] = ""; GetText((char *)name, t, sizeof(t) - 1); const float f = (float)atof(t); int v = (int)(f * 10.0f + (f >= 0 ? 0.5f : -0.5f)); return v < lo ? lo : v > hi ? hi : v; }
// ---- the pipe and a fake flight controller
static int PipeReqId = 0, PipeRepId = -1, PipeRepCode = 0; static char PipeRepBody[1600] = ""; static uint32_t PipeReqSentMs = 0;
static bool holdReplies = false;   // (a request left unanswered, to see that the arming line does not ask on top of it)
bool PipeReplyReady(int id) { return PipeRepId == id; }
bool PipeReplyLate() { return false; }
int PipeReplyBytes(uint8_t *out, int max) { int n = 0; const char *p = PipeRepBody; while (p[0] && p[1] && n < max) { char h[3] = {p[0], p[1], 0}; out[n++] = (uint8_t) strtol(h, nullptr, 16); p += 2; } return n; }
struct FcReq { int fn; std::string data; };
static std::vector<FcReq> fcLog;
static std::string hexOf(const uint8_t *d, int n) { char b[4]; std::string s; for (int i = 0; i < n; ++i) { snprintf(b, sizeof b, "%02X", d[i]); s += b; } return s; }
static uint8_t bat[27], vm[33], cm[8], bb[13], mem[13], modes[80], trims[4], att[6];
static uint32_t armFlags = 0; static int pidUs = 500, rebootLeft = 0, eraseLeft = -1;
static void fcReply(int code, const std::string &body) { PipeRepCode = code; strncpy(PipeRepBody, body.c_str(), sizeof(PipeRepBody) - 1); PipeRepBody[sizeof(PipeRepBody) - 1] = 0; PipeRepId = PipeReqId; }
static void put32(uint8_t *b, int o, uint32_t v) { b[o] = v; b[o + 1] = v >> 8; b[o + 2] = v >> 16; b[o + 3] = v >> 24; }
int MspAsk(uint8_t fn, const uint8_t *data, int len) {
    ++PipeReqId; PipeReqSentMs = now; fcLog.push_back({fn, hexOf(data, len)});
    if (holdReplies) return PipeReqId;
    if (rebootLeft > 0 && fn != 68) { --rebootLeft; fcReply(504, "no answer"); return PipeReqId; }
    switch (fn) {
    case 101: { uint8_t b[30] = {0}; b[0] = pidUs & 255; b[1] = pidUs >> 8; put32(b, 17, armFlags); b[16] = 27; fcReply(200, hexOf(b, 30)); return PipeReqId; }
    case 32: fcReply(200, hexOf(bat, 27)); return PipeReqId;
    case 33: memcpy(bat, data, len); fcReply(200, ""); return PipeReqId;   // (Rotorflight: the first 15, and the profiles' list only when 12 more come)
    case 56: fcReply(200, hexOf(vm, 33)); return PipeReqId;
    case 57: for (int i = 0; i < vm[0]; ++i) if (vm[1 + i * 8 + 1] == data[0]) memcpy(vm + 1 + i * 8 + 3, data + 1, 5); fcReply(200, ""); return PipeReqId;
    case 40: fcReply(200, hexOf(cm, 8)); return PipeReqId;
    case 41: if (cm[2] == data[0]) memcpy(cm + 4, data + 1, 4); fcReply(200, ""); return PipeReqId;
    case 80: fcReply(200, hexOf(bb, 13)); return PipeReqId;
    case 81: memcpy(bb + 1, data, 12); fcReply(200, ""); return PipeReqId;
    case 34: fcReply(200, hexOf(modes, 80)); return PipeReqId;
    case 70: if (eraseLeft > 0) { --eraseLeft; mem[0] = 2; } else if (eraseLeft == 0) { mem[0] = 3; put32(mem, 9, 0); eraseLeft = -1; } fcReply(200, hexOf(mem, 13)); return PipeReqId;
    case 72: eraseLeft = 3; fcReply(200, ""); return PipeReqId;
    case 68: rebootLeft = 1; fcReply(200, ""); return PipeReqId;
    case 240: fcReply(200, hexOf(trims, 4)); return PipeReqId;
    case 239: memcpy(trims, data, 4); fcReply(200, ""); return PipeReqId;
    case 108: fcReply(200, hexOf(att, 6)); return PipeReqId;
    case 205: att[0] = 2; att[1] = 0; att[2] = 0; att[3] = 0; fcReply(200, ""); return PipeReqId;   // (after it: roll 0.2, pitch 0.0)
    case 250: fcReply(200, ""); return PipeReqId;
    }
    fcReply(404, "unknown"); return PipeReqId;
}
''' + open(HDR).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void runBat(int n = 40) { for (int i = 0; i < n; ++i) { BatteryPoll(); now += 50; } }
static void runBb(int n = 40) { for (int i = 0; i < n; ++i) { BlackboxPoll(); now += 50; } }
static void runCal(int n = 40) { for (int i = 0; i < n; ++i) { CalibratePoll(); now += 50; } }
static int writes(int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; }
static std::string lastData(int fn) { for (int i = (int) fcLog.size() - 1; i >= 0; --i) if (fcLog[i].fn == fn) return fcLog[i].data; return "?"; }
static bool cmd(const char *c) { for (auto &x : cmds) if (x == c) return true; return false; }
int main() {
    // ---- the fake flight controller: 6S 2200 by the ESC, 2 voltage meters (ids 10, 20), 1 current meter (id 10)
    memset(bat, 0, sizeof bat); bat[0] = 0x98; bat[1] = 0x08; bat[2] = 6; bat[3] = 2; bat[4] = 2;
    WrU16(bat, 5, 330); WrU16(bat, 7, 430); WrU16(bat, 9, 410); WrU16(bat, 11, 350); bat[13] = 10; bat[14] = 20;
    for (int p = 0; p < 6; ++p) WrU16(bat, 15 + 2 * p, 1000 + 100 * p);   // the six profiles' capacities
    vm[0] = 2; for (int i = 0; i < 2; ++i) { uint8_t *f = vm + 1 + i * 8; f[0] = 7; f[1] = i ? 20 : 10; f[2] = 0; WrU16(f, 3, 110); WrU16(f, 5, 10); f[7] = 1; }
    cm[0] = 1; cm[1] = 6; cm[2] = 10; cm[3] = 0; WrU16(cm, 4, 400); WrU16(cm, 6, 0);
    // ---- 1. battery: the read, the page, the sensors hidden while the ESC is the source
    StartBatteryView(); CHECK(CurrentView == BATTERYVIEW && fcLog.size() == 1 && fcLog[0].fn == 32); runBat();
    CHECK(BatHave && writes(56) == 1 && writes(40) == 1 && fields["tn0"] == "6" && fields["tn1"] == "2200" && fields["tn2"] == "ESC telemetry" && fields["tn3"] == "ESC telemetry");
    CHECK(fields["tn4"] == "4.10" && fields["tn5"] == "3.50" && fields["tn6"] == "3.30" && fields["tn7"] == "4.30");
    CHECK(cmd("vis tn8,0") && cmd("vis h2,0") && cmd("vis tn10,0"));
    // the voltage from the FC pads: ESC -> None -> FC pads; its scale shows
    cmds.clear(); BatteryVoltageSourceTapped(); CHECK(fields["tn2"] == "None"); BatteryVoltageSourceTapped(); CHECK(fields["tn2"] == "FC pads" && cmd("vis tn8,1") && fields["tn8"] == "110" && Bat_Was_Edited);
    // the cell voltages must rise: a warning above full is refused, nothing written
    fields["tn5"] = "4.25"; fcLog.clear(); boxes = 0; SaveBattery(); CHECK(boxes == 1 && lastBox.find("must rise") != std::string::npos && fcLog.empty());
    // a save: 33 = the first 15 bytes only (the other profiles' capacities are not sent); 57 the changed scale by its id; no 41
    fields["tn5"] = "3.6"; fields["tn0"] = "12"; fields["tn1"] = "5000"; fields["tn7"] = "4.35"; fields["tn8"] = "115";
    fcLog.clear(); SaveBattery(); runBat();
    CHECK(writes(33) == 1 && lastData(33).size() == 30 && writes(57) == 1 && writes(41) == 0 && writes(250) == 1 && writes(32) == 1 && writes(56) == 1 && writes(40) == 1);
    CHECK(lastData(33).substr(0, 10) == "88130C0102" && bat[2] == 12 && RdU16(bat, 0) == 5000 && RdU16(bat, 11) == 360 && RdU16(bat, 7) == 435 && bat[3] == 1);
    CHECK(RdU16(bat, 15) == 1000 && RdU16(bat, 25) == 1500);   // (the profiles' capacities untouched)
    CHECK(lastData(57) == "0A73000A0001" && RdU16(vm, 4) == 115 && RdU16(vm, 12) == 110);   // (id 10's scale; id 20's kept)
    CHECK(!Bat_Was_Edited && fields["busy"] == "Saved, and read back the same.");
    // the current from the FC pads too: its scale and offset, signed
    BatteryCurrentSourceTapped(); BatteryCurrentSourceTapped(); CHECK(fields["tn3"] == "FC pads" && fields["tn9"] == "400" && fields["tn10"] == "0");
    fields["tn9"] = "390"; fields["tn10"] = "-25"; fcLog.clear(); SaveBattery(); runBat();
    CHECK(writes(41) == 1 && lastData(41) == "0A8601E7FF" && RdS16(cm, 6) == -25 && fields["tn10"] == "-25");
    // OK with nothing edited: back to the menu
    EndBatteryView(); CHECK(CurrentView == 47 && rfStarts == 1);
    // ---- 2. black box: 101 (the loop time), 80, the switches, the memory
    bb[0] = 1; bb[1] = 1; bb[2] = 2; WrU16(bb, 3, 8); put32(bb, 5, 0x7EE7F); WrU16(bb, 9, 0); bb[11] = 0; bb[12] = 5;
    mem[0] = 3; put32(mem, 1, 256); put32(mem, 5, 16777216); put32(mem, 9, 3355444);
    memset(modes, 0, sizeof modes);
    fcLog.clear(); StartBlackboxView(); runBb();
    CHECK(BbHave && fcLog.size() >= 4 && fcLog[0].fn == 101 && fcLog[1].fn == 80 && fcLog[2].fn == 34 && fcLog[3].fn == 70);
    CHECK(fields["tn0"] == "Whenever armed" && fields["tn1"] == "FC memory" && fields["tn2"] == "1 in 8 (250/s)" && fields["tn3"] == "5" && vals["tn4"] == 0);
    CHECK(fields["tn5"] == "3.2 of 16.0 MB used (20 %)" && fields["tn6"] == "Ready to record");
    // While switch on, with no Black box switch: asked first; No = nothing written
    BlackboxModeTapped(); CHECK(fields["tn0"] == "While switch on");
    confirmAnswer = false; asked = 0; fcLog.clear(); SaveBlackbox(); CHECK(asked == 1 && lastBox.find("No Black box switch") == 0 && fcLog.empty());
    confirmAnswer = true;
    // back to Whenever armed (3 more taps), Where to SD card, 1 in 16, overwrite on: saved, restarted (where and rate apply at boot), read back
    BlackboxModeTapped(); BlackboxModeTapped(); BlackboxModeTapped(); CHECK(fields["tn0"] == "Whenever armed");
    BlackboxDeviceTapped(); BlackboxRateTapped(); BlackboxRollTapped(); fields["tn3"] = "10";
    CHECK(fields["tn1"] == "SD card" && fields["tn2"] == "1 in 16 (125/s)" && vals["tn4"] == 1);
    fcLog.clear(); SaveBlackbox(); runBb(200);
    if (lastData(81) != "020210007FEE07000000010A" || writes(68) != 1) { fprintf(stderr, "81 %s  68 %d  250 %d  80 %d step %d\n", lastData(81).c_str(), writes(68), writes(250), writes(80), BbStep); for (auto &r : fcLog) fprintf(stderr, "  fn %d %s\n", r.fn, r.data.c_str()); }
    CHECK(writes(81) == 1 && lastData(81) == "020210007FEE07000000010A" && writes(250) == 1 && writes(68) == 1 && writes(80) >= 1);
    CHECK(bb[1] == 2 && RdU16(bb, 3) == 16 && bb[11] == 1 && bb[12] == 10 && BbStep == BB_IDLE && fields["busy"] == "Saved, and read back the same.");
    // where nowhere with recording on: refused
    BlackboxDeviceTapped(); BlackboxDeviceTapped(); CHECK(fields["tn1"] == "Nowhere");
    fcLog.clear(); boxes = 0; SaveBlackbox(); CHECK(boxes == 1 && lastBox.find("Where") != std::string::npos && fcLog.empty());
    BlackboxDeviceTapped(); CHECK(fields["tn1"] == "FC memory");
    // erase: asked, ONE 72, then 70 until the memory is empty
    fcLog.clear(); asked = 0; Bb_Was_Edited = false; BlackboxErase(); CHECK(asked == 1 && writes(72) == 1); runBb(200);
    CHECK(writes(72) == 1 && writes(70) >= 3 && BbStep == BB_IDLE && fields["busy"].find("Erased in") == 0 && fields["tn6"] == "Empty: ready to record");
    // ---- 3. calibrate: the trims, the level, calibrate, the trims saved signed
    WrU16(trims, 0, 0); trims[2] = 0xFB; trims[3] = 0xFF;   // pitch 0.0, roll -0.5
    att[0] = 3; att[1] = 0; att[2] = 0xF4; att[3] = 0xFF;  // roll 0.3, pitch -1.2
    fcLog.clear(); StartCalibrateView(); runCal(30);
    CHECK(CalHave && fields["tn2"] == "0.0" && fields["tn3"] == "-0.5" && writes(108) >= 2 && fields["tn0"] == "Roll 0.3   Pitch -1.2 deg" && fields["tn1"] == "Level");
    att[0] = 0x2C; att[1] = 0x01;  // roll 30.0: not level
    runCal(30); CHECK(fields["tn1"].find("Not level") == 0);
    fcLog.clear(); asked = 0; CalibrateNow(); CHECK(asked == 1 && writes(205) == 1);
    runCal(20); CHECK(writes(250) == 0);   // (not before 2.5 s)
    runCal(60); CHECK(writes(250) == 1 && fields["busy"].find("Calibrated: roll 0.2, pitch 0.0") == 0);
    fields["tn2"] = "1.5"; fields["tn3"] = "-2"; CalibrateWasEdited();
    fcLog.clear(); SaveLevelTrims(); runCal(30);
    CHECK(writes(239) == 1 && lastData(239) == "0F00ECFF" && RdS16(trims, 2) == -20 && fields["tn3"] == "-2.0" && !Cal_Was_Edited);
    // offline: no level asked, Calibrate refused
    offline = true; BoundFlag = false; fcLog.clear(); runCal(30); CHECK(writes(108) == 0 && fields["tn0"].find("Connect the model") == 0);
    boxes = 0; CalibrateNow(); CHECK(boxes == 1 && writes(205) == 0);
    offline = false; BoundFlag = true; EndCalibrateView();
    // ---- 4. the menu's arming line
    CurrentView = 47; PipeState = 2; armFlags = (1u << 7) | (1u << 26); now += 3000; fcLog.clear();
    for (int i = 0; i < 4; ++i) { ArmTick(); now += 50; }
    CHECK(writes(101) == 1 && fields["arm"] == "Will not arm: Throttle is not at idle (and 1 more)" && cmd("arm.pco=65504"));
    boxes = 0; ArmingWhy(); CHECK(boxes == 1 && lastBox.find("- Throttle is not at idle") != std::string::npos && lastBox.find("- Arm switch on too soon") != std::string::npos && fields["arm"].find("Will not arm") == 0);
    armFlags = 0; now += 2100; for (int i = 0; i < 4; ++i) { ArmTick(); now += 50; } CHECK(fields["arm"] == "Ready to arm" && cmd("arm.pco=2016"));
    // every 2 s, and never on top of another request
    fcLog.clear(); for (int i = 0; i < 50; ++i) { ArmTick(); now += 50; } CHECK(writes(101) == 1);
    holdReplies = true; MspAsk(80, nullptr, 0); fcLog.clear(); now += 3000; for (int i = 0; i < 10; ++i) { ArmTick(); now += 50; } CHECK(writes(101) == 0);
    holdReplies = false; PipeRepId = PipeReqId;
    // no model, or the pipe not joined: the line is empty
    PipeState = 1; ArmTick(); CHECK(fields["arm"] == "");
    printf("test_fcsetup: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:4000]); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
