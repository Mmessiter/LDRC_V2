#!/usr/bin/env python3
"""Host test of the gyro filters pages (B61): include/RF_Filters.h compiled on the Mac over a fake screen and a fake
pipe, driven as the pages drive it. Checks the words shown for the flight controller's bytes (the lowpass type order,
Strength, Q in tenths), the Enables (a lowpass off = type 0, the feature bits), and the save sequence - 93, 37 only when
an Enable changed, 250, then 68 and a patient read-back - with the bytes that went out.
   python3 dev/test_filters/test_filters.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDR = os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Filters.h')
prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
#include <map>
#define FILTERVIEW 64
#define FILTER2VIEW 65
#define WHAHWHAHMSG 1
#define BEEPCOMPLETE 2
static int CurrentView = FILTERVIEW;
static char ModelName[20] = "Goblin";
static uint32_t now = 1000;
static uint32_t millis() { return now; }
// ---- the fake screen: every text field, every vis, every command
static std::map<std::string, std::string> fields; static std::map<std::string, int> vis; static std::vector<std::string> cmds;
static int boxes = 0; static std::string lastBox; static bool confirmAnswer = true; static int sounds = 0;
static void SendCommand(char *c) { std::string s(c); cmds.push_back(s); if (s.rfind("vis ", 0) == 0) { size_t k = s.find(','); vis[s.substr(4, k - 4)] = atoi(s.c_str() + k + 1); } }
static void SendText(char *n, char *t) { fields[n] = t; }
static void SendValue(char *n, int v) { fields[n] = v ? "Yes" : "No"; }   // (a switch: its val, read back here as the word it stands for)
static void GetText(char *n, char *buf, int max) { strncpy(buf, fields[n].c_str(), max); buf[max] = 0; }
static void MsgBox(char *page, const char *msg) { ++boxes; lastBox = msg; }
static bool GetConfirmation(char *page, char *prompt) { return confirmAnswer; }
static void PlaySound(int) { ++sounds; }
static int rfStarts = 0; static void RotorFlightStart() { ++rfStarts; }
static bool RfNeedsModel(char *, int) { return false; }
static bool ModelSeemsArmed(char *, int) { return false; }
static bool RfPipeBlocked(char *, int) { return false; }
// ---- the fake pipe: requests are logged; the test sets the reply
struct Req { int fn; std::vector<uint8_t> data; };
static std::vector<Req> reqs; static int reqId = 0;
static int PipeRepCode = 0; static char PipeRepBody[400] = ""; static std::vector<uint8_t> repBytes; static bool repReady = false, repLate = false;
static int MspAsk(int fn, const uint8_t *d, int n) { Req r; r.fn = fn; if (d) r.data.assign(d, d + n); reqs.push_back(r); repReady = false; repLate = false; return ++reqId; }
static bool PipeReplyReady(int id) { return repReady; }
static bool PipeReplyLate() { return repLate; }
static int PipeReplyBytes(uint8_t *out, int max) { int n = (int)repBytes.size() < max ? (int)repBytes.size() : max; memcpy(out, repBytes.data(), n); return n; }
static void reply(int code, std::vector<uint8_t> b) { PipeRepCode = code; repBytes = b; repReady = true; }
// ---- the helpers RF_Rescue.h gives the filters
static uint16_t RdU16(const uint8_t *b, int o) { return (uint16_t)(b[o] | (b[o + 1] << 8)); }
static void WrU16(uint8_t *b, int o, long v) { if (v < 0) v = 0; if (v > 65535) v = 65535; b[o] = (uint8_t)(v & 0xFF); b[o + 1] = (uint8_t)(v >> 8); }
static long FieldNumber(const char *name, long lo, long hi) { char t[24] = ""; GetText((char *)name, t, 23); long v = strtol(t, nullptr, 10); return v < lo ? lo : v > hi ? hi : v; }
static int FieldTenths(const char *name, int lo, int hi) { char t[24] = ""; GetText((char *)name, t, 23); const float f = (float)atof(t); int v = (int)(f * 10.0f + (f >= 0 ? 0.5f : -0.5f)); return v < lo ? lo : v > hi ? hi : v; }
#define RF_FILTERS_TEST
''' + open(HDR).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static std::vector<uint8_t> fc27() {   // Malcolm's Goblin as the configurator showed it: 1st order 100 Hz, lowpass 2 off, no notches, dyn 6 / Q 2.5 / 20-240, rpm medium / 20
    std::vector<uint8_t> b(27, 0);
    b[1] = 1; b[2] = 100; b[4] = 0; b[5] = 50;   // (a stale 50 Hz on the disabled lowpass 2, as the photo had)
    b[19] = 6; b[20] = 25; b[21] = 20; b[23] = 240; b[23] = 240 & 255; b[24] = 0; b[25] = 2; b[26] = 20;
    return b;
}
static std::vector<uint8_t> feat(uint32_t m) { return {(uint8_t)m, (uint8_t)(m >> 8), (uint8_t)(m >> 16), (uint8_t)(m >> 24)}; }
static void openPage(uint32_t mask) {
    reqs.clear(); fields.clear(); vis.clear(); boxes = 0;
    StartFilterView();
    CHECK(reqs.size() == 1 && reqs[0].fn == 36);
    reply(200, feat(mask)); FilterPoll();
    CHECK(reqs.size() == 2 && reqs[1].fn == 92);
    reply(200, fc27()); FilterPoll();
    CHECK(FltHave);
}
int main() {
    const uint32_t BOTH = (1UL << 29) | (1UL << 30) | (1UL << 3);
    // 1. the words for the bytes
    openPage(BOTH);
    CHECK(fields["tn0"] == "Yes"); CHECK(fields["tn1"] == "1st order"); CHECK(fields["tn2"] == "100");
    CHECK(fields["tn3"] == "Yes"); CHECK(fields["tn4"] == "Medium"); CHECK(fields["tn5"] == "20");
    CHECK(fields["tn6"] == "Yes"); CHECK(fields["tn7"] == "6"); CHECK(fields["tn8"] == "2.5"); CHECK(fields["tn9"] == "20"); CHECK(fields["tn10"] == "240");
    CHECK(fields["t9"] == "All banks");
    CHECK(vis["tn1"] == 1 && vis["ltn2"] == 1 && vis["tn7"] == 1 && vis["tn4"] == 1);
    CHECK(vis["b3"] == 0);
    // the expert page: lowpass 2 off (its rows hidden), notches off, dynamic cutoff off
    StartFilter2View();
    CHECK(CurrentView == FILTER2VIEW);
    CHECK(fields["tn0"] == "No"); CHECK(vis["tn1"] == 0 && vis["ltn1"] == 0 && vis["tn2"] == 0);
    CHECK(fields["tn3"] == "No"); CHECK(fields["tn6"] == "No"); CHECK(fields["tn9"] == "No");
    EndFilter2View();
    CHECK(CurrentView == FILTERVIEW && fields["tn1"] == "1st order");
    // 2. the Enables and the type
    FilterLpf1Tapped(); CHECK(fields["tn1"] == "2nd order" && FltWant[1] == 2); CHECK(vis["b3"] == 1);
    FilterLpf1Tapped(); CHECK(fields["tn1"] == "1st order" && FltWant[1] == 1);   // (orig was 1: no third word)
    FilterLpf1EnableTapped(); CHECK(fields["tn0"] == "No" && FltWant[1] == 0 && RdU16(FltWant, 2) == 0); CHECK(vis["tn1"] == 0 && vis["tn2"] == 0);
    FilterLpf1EnableTapped(); CHECK(fields["tn0"] == "Yes" && FltWant[1] == 1 && RdU16(FltWant, 2) == 100);   // what it had
    FilterPresetTapped(); CHECK(fields["tn4"] == "High" && FltWant[25] == 3);
    FilterPresetTapped(); CHECK(fields["tn4"] == "Custom" && FltWant[25] == 0);
    FilterPresetTapped(); FilterPresetTapped(); CHECK(fields["tn4"] == "Medium");
    // 3. a save with nothing but numbers: 93, 250, 92 - no 37, no 68
    fields["tn2"] = "90"; fields["tn8"] = "3.0"; FilterWasEdited();
    reqs.clear(); SaveFilters();
    CHECK(reqs.size() == 1 && reqs[0].fn == 93 && reqs[0].data.size() == 27 && reqs[0].data[2] == 90 && reqs[0].data[20] == 30 && reqs[0].data[1] == 1);
    reply(200, {}); FilterPoll(); CHECK(reqs.size() == 2 && reqs[1].fn == 250);
    reply(200, {}); FilterPoll(); CHECK(reqs.size() == 3 && reqs[2].fn == 92);
    { auto b = fc27(); b[2] = 90; b[20] = 30; reply(200, b); } FilterPoll();
    CHECK(FltStep == FLT_IDLE && fields["busy"] == "Saved, and read back the same." && fields["tn2"] == "90" && fields["tn8"] == "3.0");
    // 4. an Enable off: 93, 37 (bit 30 clear), 250, 68, then 36 asked until the flight controller answers, then 92
    FilterRpmEnableTapped(); CHECK(fields["tn3"] == "No" && vis["tn4"] == 0 && vis["tn5"] == 0);
    reqs.clear(); SaveFilters();
    CHECK(reqs.size() == 1 && reqs[0].fn == 93);
    reply(200, {}); FilterPoll(); CHECK(reqs.size() == 2 && reqs[1].fn == 37 && reqs[1].data.size() == 4);
    { uint32_t m = reqs[1].data[0] | (reqs[1].data[1] << 8) | (reqs[1].data[2] << 16) | ((uint32_t)reqs[1].data[3] << 24); CHECK(m == ((1UL << 29) | (1UL << 3))); }
    reply(200, {}); FilterPoll(); CHECK(reqs.size() == 3 && reqs[2].fn == 250);
    reply(200, {}); FilterPoll(); CHECK(reqs.size() == 4 && reqs[3].fn == 68); CHECK(fields["busy"].find("Restarting") == 0);
    reply(200, {}); FilterPoll(); CHECK(FltStep == FLT_WAIT && reqs.size() == 4);
    now += 4000; FilterPoll(); CHECK(reqs.size() == 4);          // (not yet: five seconds of patience first)
    now += 1100; FilterPoll(); CHECK(reqs.size() == 5 && reqs[4].fn == 36);
    reply(504, {}); FilterPoll(); CHECK(FltStep == FLT_WAIT && boxes == 0);   // (still booting: ask again)
    now += 2600; FilterPoll(); CHECK(reqs.size() == 6 && reqs[5].fn == 36);
    repReady = false; repLate = true; FilterPoll(); CHECK(FltStep == FLT_WAIT && boxes == 0);   // (no answer at all: ask again)
    now += 2600; FilterPoll(); CHECK(reqs.size() == 7 && reqs[6].fn == 36);
    reply(200, feat((1UL << 29) | (1UL << 3))); FilterPoll(); CHECK(reqs.size() == 8 && reqs[7].fn == 36 + 56);   // 92
    { auto b = fc27(); b[2] = 90; b[20] = 30; reply(200, b); } FilterPoll();
    CHECK(FltStep == FLT_IDLE && fields["busy"] == "Saved, and read back the same." && fields["tn3"] == "No" && boxes == 0);
    CHECK(FeatRaw == ((1UL << 29) | (1UL << 3)) && FeatWant == FeatRaw);
    // 5. the flight controller never comes back: one message, not a hang
    FilterDynNotchEnableTapped(); reqs.clear(); SaveFilters();
    reply(200, {}); FilterPoll(); reply(200, {}); FilterPoll(); reply(200, {}); FilterPoll(); reply(200, {}); FilterPoll();
    CHECK(FltStep == FLT_WAIT);
    for (int i = 0; i < 8 && FltStep != FLT_IDLE; ++i) { now += 6000; FilterPoll(); if (FltStep == FLT_VERIFY_FEAT) { repReady = false; repLate = true; FilterPoll(); } }
    CHECK(FltStep == FLT_IDLE && boxes == 1 && lastBox.find("has not come back") != std::string::npos);
    // 6. OK with an edit asks; No keeps the page, Yes leaves
    openPage(BOTH); fields["tn2"] = "80"; FilterWasEdited();
    confirmAnswer = false; rfStarts = 0; EndFilterView(); CHECK(rfStarts == 0 && fields["tn2"] == "80" && Flt_Was_Edited);
    confirmAnswer = true; EndFilterView(); CHECK(rfStarts == 1 && !Flt_Was_Edited);
    // 7. the expert page's Enables: a notch on gets the configurator's defaults, off zeroes it; the dynamic cutoff likewise
    openPage(BOTH); StartFilter2View();
    FilterNotch1Tapped(); CHECK(fields["tn6"] == "Yes" && RdU16(FltWant, 7) == 400 && RdU16(FltWant, 9) == 300 && vis["tn7"] == 1);
    fields["tn7"] = "350"; FilterNotch1Tapped(); CHECK(fields["tn6"] == "No" && RdU16(FltWant, 7) == 0 && PrevN1Hz == 350);
    FilterNotch1Tapped(); CHECK(RdU16(FltWant, 7) == 350 && fields["tn7"] == "350");
    FilterDynCutoffTapped(); CHECK(fields["tn3"] == "Yes" && RdU16(FltWant, 15) == 50 && RdU16(FltWant, 17) == 150);
    FilterLpf2EnableTapped(); CHECK(fields["tn0"] == "Yes" && FltWant[4] == 1 && RdU16(FltWant, 5) == 50);   // (the stale 50 Hz it had)
    FilterLpf2Tapped(); CHECK(fields["tn1"] == "2nd order");
    // a type the configurator does not offer stays reachable while it is the one set
    FltWant[4] = 7; FltRaw[4] = 7; FltShow(); CHECK(fields["tn1"] == "Butter");
    FilterLpf2Tapped(); CHECK(fields["tn1"] == "1st order"); FilterLpf2Tapped(); CHECK(fields["tn1"] == "2nd order"); FilterLpf2Tapped(); CHECK(fields["tn1"] == "Butter");
    // 8b. a change on the expert page is asked about before a save from page 1 (B65): No = nothing goes out
    openPage(BOTH); StartFilter2View(); FilterNotch1Tapped(); EndFilter2View(); CHECK(CurrentView == FILTERVIEW);
    confirmAnswer = false; reqs.clear(); SaveFilters(); CHECK(reqs.empty() && Flt_Was_Edited);
    confirmAnswer = true; reqs.clear(); SaveFilters(); CHECK(reqs.size() == 1 && reqs[0].fn == 93 && RdU16(reqs[0].data.data(), 7) == 400);
    // 8. a dynamic range upside down is refused before anything goes out
    openPage(BOTH); fields["tn9"] = "300"; fields["tn10"] = "200"; FilterWasEdited(); reqs.clear(); boxes = 0; SaveFilters();
    CHECK(reqs.empty() && boxes == 1 && lastBox.find("Not saved") == 0);
    printf("test_filters: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++11', '-Wall', '-Wno-unused-function', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
