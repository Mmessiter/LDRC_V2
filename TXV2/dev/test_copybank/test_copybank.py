#!/usr/bin/env python3
"""Host test of Copy a bank (B78): include/RF_CopyBank.h on the Mac over a fake screen and a fake flight controller on
the fake pipe. The whole procedure as the receiver's page does it: where the FC is, the source read, the target's
governor, Rotorflight's own copy (183), the governor put right (head speed kept), the rates copy, the head-speed
scaling of the gains, the store, the read-back, the transmitter's banks put back; the verdicts; a 503 answered again.
   python3 dev/test_copybank/test_copybank.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDR = os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_CopyBank.h')
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
#define COPYBANKVIEW 71
static int CurrentView = 0;
static bool BoundFlag = true, ModelMatched = true, BlockBankChanges = false;
static char ModelName[20] = "Goblin";
static uint8_t Bank = 2, DualRateInUse = 2;
static uint32_t now = 1000;
static uint32_t millis() { return now; }
static std::map<std::string, std::string> fields; static std::map<std::string, int> vals; static std::vector<std::string> cmds; static int boxes = 0; static std::string lastBox; static bool confirmAnswer = true; static int sounds = 0, rfStarts = 0;
static void SendCommand(char *c) { cmds.push_back(c); }
static void SendText(char *n, char *t) { fields[n] = t; }
static void SendValue(char *n, int v) { vals[n] = v; }
static void MsgBox(char *page, const char *msg) { ++boxes; lastBox = msg; }
static bool GetConfirmation(char *page, char *prompt) { lastBox = prompt; return confirmAnswer; }
static void PlaySound(int) { ++sounds; }
static void RotorFlightStart() { ++rfStarts; CurrentView = 47; }
static bool ModelSeemsArmed(char *, int) { return false; }
static bool RfPipeBlocked(char *, int) { return false; }
static bool RfNeedsModel(char *, int) { return false; }
static int PipeReqId = 0, PipeRepId = -1, PipeRepCode = 0; static char PipeRepBody[1600] = ""; static uint32_t PipeReqSentMs = 0;
bool PipeReplyReady(int id) { return PipeRepId == id; }
bool PipeReplyLate() { return false; }
int PipeReplyBytes(uint8_t *out, int max) { int n = 0; const char *p = PipeRepBody; while (p[0] && p[1] && n < max) { char h[3] = {p[0], p[1], 0}; out[n++] = (uint8_t) strtol(h, nullptr, 16); p += 2; } return n; }
struct FcReq { int fn; std::string data; };
static std::vector<FcReq> fcLog;
static std::string hexOf(const uint8_t *d, int n) { char b[4]; std::string s; for (int i = 0; i < n; ++i) { snprintf(b, sizeof b, "%02X", d[i]); s += b; } return s; }
static std::string pid[6], adv[6], resc[6], gov[6], rates[6]; static int fcPid = 1, fcRate = 1, busyOnce = 0;
static void fcReply(int code, const std::string &body) { PipeRepCode = code; strncpy(PipeRepBody, body.c_str(), sizeof(PipeRepBody) - 1); PipeRepBody[sizeof(PipeRepBody) - 1] = 0; PipeRepId = PipeReqId; }
int MspAsk(uint8_t fn, const uint8_t *data, int len) {
    ++PipeReqId; PipeReqSentMs = now; fcLog.push_back({fn, hexOf(data, len)});
    if (busyOnce > 0) { --busyOnce; fcReply(503, "busy"); return PipeReqId; }
    if (fn == 101) { uint8_t b[32] = {0}; b[23] = fcPid; b[25] = fcRate; b[24] = 4; b[26] = 4; fcReply(200, hexOf(b, 32)); return PipeReqId; }
    if (fn == 210) { if (data[0] & 0x80) fcRate = data[0] & 0x7F; else fcPid = data[0]; fcReply(200, ""); return PipeReqId; }
    if (fn == 112) { fcReply(200, pid[fcPid]); return PipeReqId; }
    if (fn == 94) { fcReply(200, adv[fcPid]); return PipeReqId; }
    if (fn == 146) { fcReply(200, resc[fcPid]); return PipeReqId; }
    if (fn == 148) { fcReply(200, gov[fcPid]); return PipeReqId; }
    if (fn == 111) { fcReply(200, rates[fcRate]); return PipeReqId; }
    if (fn == 183 && len == 3) { const int t = data[0], dst = data[1], src = data[2]; if (t == 0) { pid[dst] = pid[src]; adv[dst] = adv[src]; resc[dst] = resc[src]; gov[dst] = gov[src]; } else rates[dst] = rates[src]; fcReply(200, ""); return PipeReqId; }
    if (fn == 149) { gov[fcPid] = hexOf(data, len); fcReply(200, ""); return PipeReqId; }
    if (fn == 202) { pid[fcPid] = hexOf(data, len); fcReply(200, ""); return PipeReqId; }
    if (fn == 250) { fcReply(200, ""); return PipeReqId; }
    fcReply(404, "unknown"); return PipeReqId;
}
''' + open(HDR).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void run(int n = 80) { for (int i = 0; i < n && CbStep != CB_IDLE; ++i) { CopyBankPoll(); now += 50; } }
static int writes(int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; }
static std::string rep(const char *s, int n) { std::string o; for (int i = 0; i < n; ++i) o += s; return o; }
static std::string govHex(int hs, const char *rest17) { char b[8]; snprintf(b, sizeof b, "%02X%02X", hs & 255, hs >> 8); return std::string(b) + rest17; }
int main() {
    for (int b = 0; b < 4; ++b) { pid[b] = rep("1A", 34); adv[b] = rep("2B", 43); resc[b] = rep("05", 28); gov[b] = govHex(1800 + 100 * b, rep("11", 15).c_str()); rates[b] = rep("4D", 36); }
    // bank 1 (index 0): a tune to copy; the target bank 2 (index 1) differs everywhere
    { std::string p; for (int w = 0; w < 17; ++w) { char b[8]; const int v = 100 + w * 10; snprintf(b, sizeof b, "%02X%02X", v & 255, v >> 8); p += b; } pid[0] = p; }
    adv[0] = rep("3C", 43); resc[0] = "0101" + rep("07", 26); gov[0] = govHex(1800, (rep("22", 7) + rep("33", 8)).c_str()); rates[0] = rep("5E", 36);
    gov[1] = govHex(2000, rep("11", 15).c_str());
    // 1. open on the transmitter's bank (2), the target the first other one
    StartCopyBankView(); CHECK(CurrentView == COPYBANKVIEW && CbFrom == 1 && CbTo == 0 && fields["tn0"] == "Bank 2" && fields["tn1"] == "Bank 1" && fields["b3"] == "Copy bank 2 to bank 1");
    CopyBankFromTapped(); CHECK(CbFrom == 2 && CbTo == 0); CopyBankToTapped(); CHECK(CbTo == 1); CopyBankToTapped(); CHECK(CbTo == 3);   // (never the same as the source)
    // 2. copy bank 1 to bank 2: flight tuning, rates, governor gains with the target's head speed kept (the defaults)
    CbFrom = 0; CbTo = 1; CbShow(); CHECK(vals["tn2"] == 1 && vals["tn3"] == 1 && vals["tn4"] == 1 && vals["tn5"] == 0 && vals["tn6"] == 0);
    fcLog.clear(); confirmAnswer = true; busyOnce = 0; CopyBankNow(); CHECK(CbStep != CB_IDLE && BlockBankChanges);
    run();
    CHECK(CbStep == CB_IDLE && !BlockBankChanges && lastBox.find("Copied bank 1 to bank 2: flight tuning, rates, governor gains (head speed kept).") == 0 && lastBox.find("Read back the same.") != std::string::npos);
    CHECK(pid[1] == pid[0] && adv[1] == adv[0] && resc[1] == resc[0] && rates[1] == rates[0]);
    CHECK(gov[1] == govHex(2000, (rep("22", 7) + rep("33", 8)).c_str()));   // (the source's governor, the target's own head speed)
    { int k183 = 0, k250 = 0; std::string first183, second183; for (auto &r : fcLog) { if (r.fn == 183) { if (!k183) first183 = r.data; else second183 = r.data; ++k183; } if (r.fn == 250) ++k250; } CHECK(k183 == 2 && first183 == "000100" && second183 == "010100" && k250 == 1); }
    CHECK(fcPid == Bank - 1 && fcRate == DualRateInUse - 1);   // (the transmitter's own banks put back)
    CHECK(fcLog.back().fn == 210 && fcLog.back().data == "81");
    // 3. the head speed too, and the gains scaled: bank 1 (1800 rpm) to bank 3 (2000 rpm): faster -> (0.9)^1.5 = 0.854 -> gains down 15 %
    CbFrom = 0; CbTo = 2; CbHs = false; CbAdj = true; gov[2] = govHex(2000, rep("11", 15).c_str());
    fcLog.clear(); busyOnce = 1; CopyBankNow(); run();
    CHECK(lastBox.find("Copied bank 1 to bank 3") == 0 && lastBox.find("Gains down 15 % for bank 3's faster head speed (1800 to 2000 rpm).") != std::string::npos);
    { uint8_t b[40]; int n = 0; const char *p = pid[2].c_str(); while (p[0] && p[1]) { char h[3] = {p[0], p[1], 0}; b[n++] = (uint8_t) strtol(h, nullptr, 16); p += 2; }
      const int w0 = b[0] | (b[1] << 8), w14 = b[28] | (b[29] << 8), w15 = b[30] | (b[31] << 8);
      CHECK(w0 == 85 && w14 == 205 && w15 == 250); }   // 100*0.854=85.4->85; 240*0.854=205; word 15 (O) untouched
    CHECK(writes(202) == 1 && writes(101) == 2);   // (the 503 on the first ask answered again)
    // 4. slower: bank 3 (2000) to bank 1 (1800): up by the ratio, 11 %
    CbFrom = 2; CbTo = 0; CbAdj = true; fcLog.clear(); CopyBankNow(); run();
    CHECK(lastBox.find("Gains up 11 % for bank 1's slower head speed (2000 to 1800 rpm).") != std::string::npos);
    // 5. rates only
    CbFrom = 0; CbTo = 3; CbFlight = false; CbGov = false; CbRates = true; CbAdj = false; fcLog.clear(); CopyBankNow(); run();
    CHECK(lastBox.find("Copied bank 1 to bank 4: rates.") == 0 && writes(183) == 1 && writes(149) == 0 && writes(148) == 0 && rates[3] == rates[0]);
    // 6. nothing switched on, the same bank: refused before anything
    CbRates = false; boxes = 0; fcLog.clear(); CopyBankNow(); CHECK(boxes == 1 && fcLog.empty() && lastBox.find("Switch on at least one thing") == 0);
    CbRates = true; CbTo = CbFrom; boxes = 0; CopyBankNow(); CHECK(boxes == 1 && lastBox.find("The two banks are the same") == 0);
    // 7. the read-back differs: said so
    CbFrom = 0; CbTo = 1; CbFlight = true; CbGov = true; adv[0] = rep("3D", 43);
    fcLog.clear(); CopyBankNow();
    // (the FC "forgets" the copy of PID+: the fake copies, then we spoil the target after the copy)
    for (int i = 0; i < 80 && CbStep != CB_IDLE; ++i) { CopyBankPoll(); now += 50; if (CbStep == CB_STORE) adv[1] = rep("00", 43); }
    CHECK(lastBox.find("but read back DIFFERENT: PID+") != std::string::npos);
    printf("test_copybank: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:4000]); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
