#!/usr/bin/env python3
"""Host test of the Rates page's numbers (B07, B08): include/RF_Rates.h compiled on the Mac over a fake screen. The scale
table and the headings follow the BANK'S rates type (Rotorflight 2.3's own type 6 = Rate / Shape; Actual and the rest keep
the Centre / Max scales), a typed value too big for its byte is cut and said, never wrapped, and a local save keeps the
bank's own type.
   python3 dev/test_rates/test_rates.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDR = os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Rates.h')
prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <map>
#include <vector>
#define FLASHMEM
#define PROGMEM
#define MAX_RATES_BYTES 13
#define RATESVIEW_RF 46
#define WHAHWHAHMSG 1
#define BEEPCOMPLETE 2
#define BEEPMIDDLE 3
#define Gray 1
#define Black 0
#define SEND_RATES_VALUES 12
#define GET_FIRST_7_RATES_VALUES 13
#define GET_SECOND_6_RATES_VALUES 14
#define MSP_WAIT_TIME 2000
static int CurrentView = RATESVIEW_RF;
static uint8_t RotorFlight_V = 2, DualRateInUse = 1;
static uint8_t Rate_Values[MAX_RATES_BYTES], Saved_Rate_Values[MAX_RATES_BYTES][4];
static char RatesWindows[MAX_RATES_BYTES][5] = {"t10", "tn0", "tn1", "tn2", "tn3", "tn4", "tn5", "tn6", "tn7", "tn8", "tn9", "tn10", "tn11"};
static char Rate_Types[7][16] = {"0 - NONE", "1 - BETAFLIGHT", "2 - RACEFLIGHT", "3 - KISS", "4 - ACTUAL", "5 - QUICKRATES", "6 - ROTORFLIGHT"};
const float FactorTableRF2_2[13] = {1, 10, 10, .01, 10, 10, .01, 10, 10, .01, .25, .25, .01};
const float FactorTableRF2_3[13] = {1, 5, 1, 1, 5, 1, 1, 5, 1, 1, .125, 1, 1};
static bool RfValueWasCut = false, Rates_Were_Edited = false, Reading_RATES_Now = false, BlockBankChanges = false, Wait_for_Advanced_Rates_to_Be_Sent_Too = false, live = true;
static uint32_t RATES_Send_Duration = 0, RATES_Start_Time = 0; static uint32_t millis() { return 1000; }
static int ModelNumber = 1; static char ModelName[20] = "Goblin"; static int saves = 0, sounds = 0, boxes = 0; static std::string lastBox;
static std::map<std::string, std::string> fields; static std::vector<std::string> cmds; static std::vector<int> queued;
static void SendText(char *n, char *t) { fields[n] = t; }
static void SendCommand(char *c) { cmds.push_back(c); }
static void GetText(char *n, char *out, size_t sz) { strncpy(out, fields.count(n) ? fields[n].c_str() : "", sz - 1); out[sz - 1] = 0; }
static void SendForegroundColour(const char *, uint16_t) {}
static void MsgBox(char *page, char *msg) { ++boxes; lastBox = msg; }
static void PlaySound(int) { ++sounds; }
static bool RfLive() { return live; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static bool ModelSeemsArmed(char *, size_t) { return false; }
static void AddParameterstoQueue(uint8_t id) { queued.push_back(id); }
static void DelayWithDog(int) {}
static void SaveOneModel(int) { ++saves; }
static char *Str(char *b, int v, int) { snprintf(b, 10, "%d", v); return b; }
static bool GetConfirmation(char *, char *) { return true; } static void RotorFlightStart() {}
// (1Definitions.h gives these prototypes on the Teensy)
void RatesMsg(const char *msg, uint16_t Colour); void HideRATESMsg(); void DisplayRatesValues(uint8_t startIndex, uint8_t stopIndex);
// B102: OK's "Save now?" - the real RfSaveFirst / RfSavedThenLeave (include/RF_SaveNow.h) over a fake question: Discard
// unless saveNowAnswer is 1; and the bank check (PipeHttp.h BankCheck) as without a pipe: the write goes
static bool RfLeaveAfterSave = false; static int RfLeaveView = -1; static void (*RfLeaveFn)() = nullptr;
static int saveNowAnswer = 0, saveNowAsked = 0;
static bool GetSaveOrDiscard(char *, char *prompt) { ++saveNowAsked; lastBox = prompt; return saveNowAnswer == 1; }
static inline void BankCheck(bool, int, void (*then)(), const char *) { then(); }
''' + open(os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_SaveNow.h')).read() + r'''
''' + open(HDR).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void typed(const char *roll, const char *centre, const char *expo, const char *coll) { fields["tn0"] = roll; fields["tn1"] = centre; fields["tn2"] = expo; fields["tn9"] = coll; for (int i = 4; i <= 8; ++i) fields[RatesWindows[i]] = "1"; fields["tn10"] = "1"; fields["tn11"] = "1"; }
int main() {
    memset(Rate_Values, 0, sizeof Rate_Values); memset(Saved_Rate_Values, 0, sizeof Saved_Rate_Values);
    // 1. B08: the scale by the bank's type on a 2.3 flight controller: Actual = x10 (centre, max) and x0.01 (expo); type 6 = x5 / x1 / x1
    RotorFlight_V = 2; Rate_Values[0] = 4; Rate_Values[1] = 20; Rate_Values[2] = 36; Rate_Values[3] = 30; Rate_Values[10] = 50;
    CHECK(GetFactoredValue(1) == 200.0f && GetFactoredValue(2) == 360.0f && GetFactoredValue(3) > 0.299f && GetFactoredValue(3) < 0.301f && GetFactoredValue(10) == 12.5f);
    Rate_Values[0] = 6; CHECK(GetFactoredValue(1) == 100.0f && GetFactoredValue(2) == 36.0f && GetFactoredValue(3) == 30.0f && GetFactoredValue(10) == 6.25f);
    RotorFlight_V = 1; Rate_Values[0] = 6; CHECK(GetFactoredValue(1) == 200.0f);   // (2.2 has no type 6: the 2.2 scales)
    // 2. the headings follow the type when byte 0 arrives
    RotorFlight_V = 2; Rate_Values[0] = 6; DisplayRatesValues(0, 1); CHECK(fields["t10"] == "6 - ROTORFLIGHT" && fields["t5"] == "Rate" && fields["t6"] == "Shape");
    Rate_Values[0] = 4; DisplayRatesValues(0, 13); CHECK(fields["t10"] == "4 - ACTUAL" && fields["t5"] == "Centre" && fields["t6"] == "Max rate" && fields["tn0"] == "200" && fields["tn2"] == "0.30" && fields["tn9"] == "12.50");   // (the collective to two decimals, as ever)
    Rate_Values[0] = 9; DisplayRatesValues(0, 1); CHECK(fields["t10"] == "?");   // (a type we do not know: no read past the names)
    // 3. the edits read back with the same table: 200 typed on an Actual bank is 20 (x10), on a type-6 bank 40 (x5)
    Rate_Values[0] = 4; typed("200", "360", "0.3", "12.5"); RfValueWasCut = false; ReadEditedRateValues();
    CHECK(Rate_Values[1] == 20 && Rate_Values[2] == 36 && Rate_Values[3] == 30 && Rate_Values[10] == 50 && !RfValueWasCut);   // (0.3 / 0.01 rounds to 30: it came out 29)
    Rate_Values[0] = 6; typed("200", "360", "30", "12.5"); ReadEditedRateValues(); CHECK(Rate_Values[1] == 40 && Rate_Values[2] == 255 && Rate_Values[3] == 30 && Rate_Values[10] == 100 && RfValueWasCut);   // (360 as a Shape: cut to 255, and said)
    // 4. B07: a rate of 1300 on a type-6 bank was sent as 20 deg/s (1300/5 = 260 wrapped to 4); now 255 (1275 deg/s), and the pilot told
    RfValueWasCut = false; typed("1300", "40", "-5", "40"); ReadEditedRateValues();
    CHECK(Rate_Values[1] == 255 && Rate_Values[2] == 40 && Rate_Values[3] == 0 && Rate_Values[10] == 255 && RfValueWasCut);
    live = true; boxes = 0; queued.clear(); SendEditedRates();
    CHECK(boxes == 1 && lastBox.find("A value was too big for Rotorflight") == 0 && !RfValueWasCut && queued.size() == 2 && fields["tn0"] == "1275" && fields["tn9"] == "31.88");
    typed("250", "40", "20", "12.5"); boxes = 0; SendEditedRates(); CHECK(boxes == 0 && Rate_Values[1] == 50);   // (nothing cut: no box)
    // 5. a local save keeps the saved bank's own type (it was always made Actual, so a type-6 bank came back with Actual's scales)
    live = false; DualRateInUse = 1; Saved_Rate_Values[0][0] = 6; typed("250", "40", "20", "12.5"); saves = 0; SaveRatesLocalBank();
    CHECK(saves == 1 && Saved_Rate_Values[0][0] == 6 && Saved_Rate_Values[1][0] == 50 && Saved_Rate_Values[2][0] == 40 && Saved_Rate_Values[10][0] == 100);
    Saved_Rate_Values[0][1] = 0; DualRateInUse = 2; SaveRatesLocalBank(); CHECK(Saved_Rate_Values[0][1] == 4 && Saved_Rate_Values[1][1] == 25);   // (no type known: Actual, x10)
    DualRateInUse = 1; fields.clear(); ShowRatesLocalBank(); CHECK(fields["t10"] == "6 - ROTORFLIGHT" && fields["tn0"] == "250" && fields["tn9"] == "12.50" && fields["t5"] == "Rate" && Rate_Values[0] == 6);
    DualRateInUse = 2; fields.clear(); ShowRatesLocalBank(); CHECK(fields["t10"] == "4 - ACTUAL" && fields["tn0"] == "250" && fields["t5"] == "Centre");
    printf("test_rates: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:4000]); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
