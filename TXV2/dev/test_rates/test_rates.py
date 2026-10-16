#!/usr/bin/env python3
"""Host test of the Rates page's numbers (B07, B08): include/RF_Rates.h compiled on the Mac over a fake screen. The scale
table and the headings follow the BANK'S rates type (Rotorflight 2.3's own type 6 = Rate / Shape; Actual and the rest keep
the Centre / Max scales), a typed value too big for its byte is cut and said, never wrapped, and a local save keeps the
bank's own type. B106: the type is chosen on the picker (RatesTypeView): OK gives the chosen type's starting values (the
Configurator's, Rotorflight's own formulas giving about 240 / 400 deg/s and 12.5 deg at full stick), Cancel nothing, a bank
switch moved while choosing leaves the type; a type Rotorflight does not have (7 and up; 6 on a 2.2) is never saved, live
or kept; and the phone's Rates page has the same starting values (rotorflight-rates.html RATES_START, if LDRC_V2_ALL is here).
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
#define RATESTYPEVIEW 82
static int CurrentView = RATESVIEW_RF;
static uint8_t ParametersToBeSentPointer = 0; static uint32_t listVal = 0; static std::map<std::string, int> values;
static uint32_t GetValue(char *) { return listVal; }
static void SendValue(char *n, int v) { values[n] = v; }
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
    // 5. a local save keeps the bank's own type (it was always made Actual, so a type-6 bank came back with Actual's scales);
    // B106: the page's type, which ShowRatesLocalBank takes from the saved bank (and the picker may change)
    live = false; DualRateInUse = 1; Saved_Rate_Values[0][0] = 6; ShowRatesLocalBank(); typed("250", "40", "20", "12.5"); saves = 0; SendEditedRates();
    CHECK(saves == 1 && Saved_Rate_Values[0][0] == 6 && Saved_Rate_Values[1][0] == 50 && Saved_Rate_Values[2][0] == 40 && Saved_Rate_Values[10][0] == 100);
    Saved_Rate_Values[0][1] = 0; DualRateInUse = 2; ShowRatesLocalBank(); typed("250", "40", "20", "12.5"); SendEditedRates();
    CHECK(Saved_Rate_Values[0][1] == 0 && Saved_Rate_Values[1][1] == 25);   // (B106: NONE kept - it was made Actual with zero rates; x10 as before)
    DualRateInUse = 1; fields.clear(); ShowRatesLocalBank(); CHECK(fields["t10"] == "6 - ROTORFLIGHT" && fields["tn0"] == "250" && fields["tn9"] == "12.50" && fields["t5"] == "Rate" && Rate_Values[0] == 6);
    DualRateInUse = 2; fields.clear(); ShowRatesLocalBank(); CHECK(fields["t10"] == "0 - NONE" && fields["tn0"] == "250" && fields["t5"] == "Centre");   // (B106: NONE, as kept)
    // 6. B106: the type chosen on the picker
    {
        static const uint8_t want[7][12] = {{0,0,0, 0,0,0, 0,0,0, 0,0,0}, {120,0,0, 120,0,0, 200,0,0, 203,1,0}, {24,0,0, 24,0,0, 40,0,0, 50,0,0},
            {120,0,0, 120,0,0, 200,0,0, 250,0,0}, {18,24,0, 18,24,0, 18,40,0, 50,50,0}, {120,24,0, 120,24,0, 200,40,0, 250,50,0}, {50,12,40, 50,12,40, 80,12,50, 100,12,0}};
        CHECK(memcmp(want, RatesStart, sizeof want) == 0);   // (the Configurator's; QUICKRATES' collective 50, not its 104 = 26 deg)
        RotorFlight_V = 2; for (int t = 0; t <= 6; ++t) CHECK(RatesTypeKnown(t)); CHECK(!RatesTypeKnown(7) && !RatesTypeKnown(255));
        RotorFlight_V = 1; CHECK(RatesTypeKnown(5) && !RatesTypeKnown(6)); RotorFlight_V = 0; CHECK(RatesTypeKnown(6));   // (6 only where 2.2 is known)
        // the Havok (16 Oct 2026): ACTUAL with Rotorflight's numbers, read from the flight controller, bank 1
        live = true; RotorFlight_V = 2; DualRateInUse = 1; CurrentView = RATESVIEW_RF; Rates_Were_Edited = false; Reading_RATES_Now = false; ParametersToBeSentPointer = 0;
        const uint8_t havok[13] = {4, 50, 12, 40, 50, 12, 40, 80, 12, 50, 100, 12, 0};
        memcpy(Rate_Values, havok, 13); fields.clear(); DisplayRatesValues(0, 13);
        CHECK(fields["t10"] == "4 - ACTUAL" && fields["tn0"] == "500" && fields["tn1"] == "120" && fields["tn2"] == "0.40" && fields["tn9"] == "25.0");
        // tapped while reading, or while a write is queued: nothing (the page's note covers it)
        Reading_RATES_Now = true; cmds.clear(); RatesTypeTapped(); CHECK(cmds.empty() && CurrentView == RATESVIEW_RF); Reading_RATES_Now = false;
        ParametersToBeSentPointer = 2; RatesTypeTapped(); CHECK(cmds.empty() && CurrentView == RATESVIEW_RF); ParametersToBeSentPointer = 0;
        // tapped: the picker at the bank's own type, the page's numbers kept
        values.clear(); RatesTypeTapped();
        CHECK(!cmds.empty() && cmds.back() == "page RatesTypeView" && CurrentView == RATESTYPEVIEW && values["list"] == 4 && fields["t9"] == "Rate 1" && fields["t11"] == "Goblin");
        CHECK(memcmp(Rate_Values, havok, 13) == 0);   // (the boxes read back to the same bytes)
        // Cancel: back, nothing changed, Save not shown
        cmds.clear(); fields.clear(); RatesTypePickCancel();
        CHECK(CurrentView == RATESVIEW_RF && cmds.front() == "page RatesView" && cmds.back() == "vis b3,0" && !Rates_Were_Edited && memcmp(Rate_Values, havok, 13) == 0 && fields["tn0"] == "500" && fields["t10"] == "4 - ACTUAL");
        RatesTypePickCancel(); CHECK(cmds.back() == "vis b3,0");   // (not on the picker: nothing)
        // OK on 4 - ACTUAL: its starting values, Save shown - Centre 180, Max rate 240 (yaw 400), collective 12.5 / 12.5
        RatesTypeTapped(); listVal = 4; cmds.clear(); fields.clear(); RatesTypePickOk();
        CHECK(CurrentView == RATESVIEW_RF && Rates_Were_Edited && cmds.back() == "vis b3,1" && Rate_Values[0] == 4 && memcmp(Rate_Values + 1, want[4], 12) == 0);
        CHECK(fields["t10"] == "4 - ACTUAL" && fields["t5"] == "Centre" && fields["t6"] == "Max rate" && fields["tn0"] == "180" && fields["tn1"] == "240" && fields["tn2"] == "0" && fields["tn6"] == "180" && fields["tn7"] == "400" && fields["tn9"] == "12.50" && fields["tn10"] == "12.50" && fields["tn11"] == "0.0");
        // ... and saved: both batches queued, the type and the starting values in them
        queued.clear(); boxes = 0; SendEditedRates(); CHECK(boxes == 0 && queued.size() == 2 && Rate_Values[0] == 4 && memcmp(Rate_Values + 1, want[4], 12) == 0);
        // OK on 6 - ROTORFLIGHT: Rate 250 (yaw 400), Shape 12, Expo 40 (yaw 50), collective 12.5 - the heads follow
        RatesTypeTapped(); CHECK(values["list"] == 4); listVal = 6; fields.clear(); RatesTypePickOk();
        CHECK(Rate_Values[0] == 6 && memcmp(Rate_Values + 1, want[6], 12) == 0 && fields["t10"] == "6 - ROTORFLIGHT" && fields["t5"] == "Rate" && fields["t6"] == "Shape" && fields["tn0"] == "250" && fields["tn1"] == "12" && fields["tn2"] == "40" && fields["tn6"] == "400" && fields["tn8"] == "50" && fields["tn9"] == "12.50" && fields["tn10"] == "12");
        // every type: its own starting values; a choice out of the list (7, or what a lost reply gives) changes nothing
        for (int t = 0; t <= 6; ++t) { RatesTypeTapped(); listVal = t; RatesTypePickOk(); CHECK(Rate_Values[0] == t && memcmp(Rate_Values + 1, want[t], 12) == 0 && CurrentView == RATESVIEW_RF); }
        uint8_t before[13]; memcpy(before, Rate_Values, 13);
        RatesTypeTapped(); listVal = 7; RatesTypePickOk(); CHECK(memcmp(Rate_Values, before, 13) == 0 && CurrentView == RATESVIEW_RF);
        RatesTypeTapped(); listVal = 0xFFFFFFFFu; RatesTypePickOk(); CHECK(memcmp(Rate_Values, before, 13) == 0 && CurrentView == RATESVIEW_RF);
        // typed numbers before the tap are what Cancel brings back
        Rates_Were_Edited = true; fields["tn0"] = "260"; RatesTypeTapped(); RatesTypePickCancel(); CHECK(fields["tn0"] == "260" && Rate_Values[1] == 52 && cmds.back() == "vis b3,1");
        // the bank switch moved while choosing: the type left as it was, the new bank read (and the lost edit said)
        RatesTypeTapped(); memcpy(before, Rate_Values, 13); DualRateInUse = 2; listVal = 4; queued.clear(); boxes = 0; RatesTypePickOk();
        CHECK(Rate_Values[0] == before[0] && CurrentView == RATESVIEW_RF && Reading_RATES_Now && queued.size() == 1 && queued[0] == SEND_RATES_VALUES && boxes == 1 && fields["t9"] == "Rate 2");
        Reading_RATES_Now = false; BlockBankChanges = false; Rates_Were_Edited = false; DualRateInUse = 1;
        // a 2.2 flight controller: ROTORFLIGHT is not chosen, and said
        RotorFlight_V = 1; Rate_Values[0] = 4; RatesTypeTapped(); listVal = 6; boxes = 0; sounds = 0; RatesTypePickOk();
        CHECK(Rate_Values[0] == 4 && boxes == 1 && lastBox.find("ROTORFLIGHT came with Rotorflight 2.3") == 0 && sounds == 1 && CurrentView == RATESVIEW_RF);
        // a bank whose type Rotorflight does not have: shown "?", the picker opens at ROTORFLIGHT (ACTUAL on a 2.2), Save refused - live and kept
        RotorFlight_V = 2; Rate_Values[0] = 9; RatesTypeTapped(); CHECK(values["list"] == 6); RatesTypePickCancel(); CHECK(fields["t10"] == "?");
        RotorFlight_V = 1; RatesTypeTapped(); CHECK(values["list"] == 4); RatesTypePickCancel(); RotorFlight_V = 2;
        live = true; queued.clear(); boxes = 0; SendEditedRates(); CHECK(boxes == 1 && lastBox.find("Not saved: the rates type is 9") == 0 && queued.empty());
        live = false; saves = 0; boxes = 0; Saved_Rate_Values[0][0] = 4; SendEditedRates(); CHECK(boxes == 1 && saves == 0 && Saved_Rate_Values[0][0] == 4);
        RotorFlight_V = 1; Rate_Values[0] = 6; live = true; boxes = 0; SendEditedRates(); CHECK(boxes == 1 && lastBox.find("Not saved: the rates type is 6") == 0 && queued.empty());
        // OK's "Save now?" refused by the type: the page stays, its edits kept
        RotorFlight_V = 2; Rate_Values[0] = 9; Rates_Were_Edited = true; saveNowAnswer = 1; boxes = 0; RfLeaveAfterSave = false; EndRFRatesView();
        CHECK(boxes == 1 && Rates_Were_Edited && queued.empty()); saveNowAnswer = 0; RfLeaveAfterSave = false; Rates_Were_Edited = false;
        // a local (not connected) bank: the chosen type and its values kept on Save
        live = false; DualRateInUse = 3; Saved_Rate_Values[0][2] = 6; CurrentView = RATESVIEW_RF; ShowRatesLocalBank(); RatesTypeTapped(); listVal = 4; RatesTypePickOk(); saves = 0; SendEditedRates();
        CHECK(saves == 1 && Saved_Rate_Values[0][2] == 4 && Saved_Rate_Values[1][2] == 18 && Saved_Rate_Values[2][2] == 24 && Saved_Rate_Values[8][2] == 40 && Saved_Rate_Values[10][2] == 50);
    }
    printf("test_rates: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:4000]); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
