#!/usr/bin/env python3
"""Host test of the read-back after a save (B153): include/RF_Verify.h compiled on the Mac over fake pages. A Version 1
word page's save (PIDs, PID +, Rates, Dynamics, the governor's bank page) is read back from the flight controller and
compared with what was sent: the same = "Saved ..." on the page's line, the done sound, OK's "Save now?" closes the page;
different = at the window's end the values sent go back on the page with the boxes that differ in red, Save shown, a
message; nothing = "NOT CONFIRMED", Save shown. Not without the pipe (the backup file, no model); not after the page is
left or a bank change read afresh (the read's start time is the read-back's identity).
   python3 dev/test_verify/test_verify.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDR = os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Verify.h')
prog = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
#include <map>
#define FLASHMEM
#define MAX_PID_WORDS 12
#define MAX_RATES_BYTES 13
#define MAX_RATES_ADVANCED_BYTES 15
#define MAX_PIDS_ADVANCED_BYTES 26
#define GOV_ACK_PAYLOAD_SIZE 59
#define PIDVIEW 45
#define RATESVIEW_RF 46
#define RATESADVANCEDVIEW 48
#define PIDADVANCEDVIEW 49
#define RFGOVERNORVIEW_PROFILE 54
#define ROTORFLIGHTVIEW 44
#define BEEPCOMPLETE 2
#define WHAHWHAHMSG 1
#define Gray 33840
#define Red 63488
#define RF_VERIFY_WAIT_MS 4000
enum { VK_NONE = 0, VK_RATES, VK_RATES_ADV, VK_PID, VK_PID_ADV, VK_GOV };
static uint32_t nowMs = 1000; static uint32_t millis() { return nowMs; }
static int CurrentView = RATESVIEW_RF;
static uint8_t PipeState = 2; static bool BoundFlag = true, ModelMatched = true, bakOffline = false; static bool BakOffline() { return bakOffline; }
static bool BlockBankChanges = false, RfValueWasCut = false;
static bool Reading_PIDS_Now = false, Reading_RATES_Now = false, Reading_RATES_Advanced_Now = false, Reading_PIDS_Advanced_Now = false, Reading_GOV_Now = false;
static uint32_t RATES_Start_Time = 0, RATES_Advanced_Start_Time = 0, PID_Start_Time = 0, PID_Advanced_Start_Time = 0, GOV_Start_Time = 0;
static uint16_t RATES_Send_Duration = 0, PID_Send_Duration = 0, Rates_Advanced_Send_Duration = 0, PID_Advanced_Send_Duration = 0; static uint32_t GOV_Send_Duration = 0;
static uint8_t Rate_Values[MAX_RATES_BYTES], Rate_Advanced_Values[MAX_RATES_ADVANCED_BYTES], PID_Advanced_Values[MAX_PIDS_ADVANCED_BYTES], GovAckPayload[GOV_ACK_PAYLOAD_SIZE], GovWritePayload[GOV_ACK_PAYLOAD_SIZE];
static uint16_t PID_Values[MAX_PID_WORDS], PID_Boost_Values[3], PID_HSI_Offset_Values[2];
static char RatesWindows[MAX_RATES_BYTES][5] = {"t10", "tn0", "tn1", "tn2", "tn3", "tn4", "tn5", "tn6", "tn7", "tn8", "tn9", "tn10", "tn11"};
static char RatesAWindows[15][4] = {"n0", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9", "n10", "n11", "n12", "n13", "t14"};
static char PID_Labels[17][4] = {"n0", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9", "n10", "n11", "n12", "n13", "n14", "n15", "n16"};
static char PID_Advanced_Labels[26][4] = {"sw0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9", "t10", "t11", "t12", "t13", "t14", "t15", "t16", "t17", "t18", "t19", "t20", "t21", "t22", "t23", "t24", "t25"};
// what the pages were asked
static std::vector<std::string> cmds, msgs, hides, displays, edited, reds, sounds; static std::map<std::string, std::string> texts;
static int boxes = 0, leaves = 0, cutNotes = 0, asks = 0; static std::string lastBox, lastBoxPage;
static void SendCommand(char *c) { cmds.push_back(c); }
static void SendText(char *n, char *t) { texts[n] = t; }
static void SendForegroundColour(const char *l, uint16_t c) { if (c == Red) reds.push_back(l); }
static void PlaySound(uint16_t s) { sounds.push_back(s == BEEPCOMPLETE ? "done" : "whah"); }
static void MsgBox(char *page, char *m) { ++boxes; lastBox = m; lastBoxPage = page; }
static void RfSavedThenLeave(int) { ++leaves; }
static void RfCutNote(const char *) { if (!RfValueWasCut) return; RfValueWasCut = false; ++cutNotes; }
static void RatesMsg(const char *m, uint16_t) { msgs.push_back(std::string("rates:") + m); }
static void RatesAdvancedMsg(const char *m, uint16_t) { msgs.push_back(std::string("ratesadv:") + m); }
static void PIDMsg(const char *m, uint16_t) { msgs.push_back(std::string("pid:") + m); }
static void PIDAdvancedMsg(const char *m, uint16_t) { msgs.push_back(std::string("pidadv:") + m); }
static void ShowGOVMsg(const char *m, uint16_t) { msgs.push_back(std::string("gov:") + m); }
static void HideRATESMsg() { hides.push_back("rates"); BlockBankChanges = false; }
static void Hide_Advanced_Rates_Msg() { hides.push_back("ratesadv"); BlockBankChanges = false; }
static void HidePIDMsg() { hides.push_back("pid"); BlockBankChanges = false; }
static void HidePID_Advanced_Msg() { hides.push_back("pidadv"); BlockBankChanges = false; }
static void HideGOVMsg() { hides.push_back("gov"); BlockBankChanges = false; }
static void DisplayRatesValues(uint8_t a, uint8_t b) { displays.push_back("rates " + std::to_string(a) + "-" + std::to_string(b)); }
static void Display_Advanced_Rates_Values(uint8_t a, uint8_t b) { displays.push_back("ratesadv " + std::to_string(a) + "-" + std::to_string(b)); }
static void Display2PIDValues(uint8_t i) { displays.push_back("pid " + std::to_string(i)); }
static void DisplayBoostPidValues() { displays.push_back("boost"); }
static void Display_PID_Advanced_Values(uint8_t a, uint8_t b) { displays.push_back("pidadv " + std::to_string(a) + "-" + std::to_string(b)); }
static void DisplayGovValues(uint8_t a, uint8_t b) { displays.push_back("gov " + std::to_string(a) + "-" + std::to_string(b)); }
static void RatesWereEdited() { edited.push_back("rates"); }
static void RatesAdvancedWereEdited() { edited.push_back("ratesadv"); }
static void PIDs_Were_edited() { edited.push_back("pid"); }
static void PIDsAdvancedWereEdited() { edited.push_back("pidadv"); }
static void GOVS_P_Were_Edited() { edited.push_back("gov"); }
// the pages' own reads (their AskValues) as they are: the kind's flag, window and start time
static void RatesAskValues() { ++asks; RATES_Send_Duration = 2500; Reading_RATES_Now = true; RATES_Start_Time = millis(); }
static void RatesAdvAskValues() { ++asks; Rates_Advanced_Send_Duration = 2500; Reading_RATES_Advanced_Now = true; RATES_Advanced_Start_Time = millis(); }
static void PidAskValues() { ++asks; PID_Send_Duration = 2500; Reading_PIDS_Now = true; PID_Start_Time = millis(); }
static void PidAdvAskValues() { ++asks; PID_Advanced_Send_Duration = 2500; Reading_PIDS_Advanced_Now = true; PID_Advanced_Start_Time = millis(); }
static void GovAskValues() { ++asks; GOV_Send_Duration = 2500; Reading_GOV_Now = true; GOV_Start_Time = millis(); }
static void RefusedAsk() { ++asks; }   // (the queue refused it: no pipe after all - the flag stays down)
bool RfVerifyArm(uint8_t kind, void (*ask)()); bool RfVerifyPending(); int RfVerifySet(); bool RfVerifyEnd(uint8_t kind); void RfVerifyTick();
''' + open(HDR).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void reset() { cmds.clear(); msgs.clear(); hides.clear(); displays.clear(); edited.clear(); reds.clear(); sounds.clear(); texts.clear(); boxes = leaves = cutNotes = asks = 0; lastBox.clear(); BlockBankChanges = false; RfValueWasCut = false;
    Reading_PIDS_Now = Reading_RATES_Now = Reading_RATES_Advanced_Now = Reading_PIDS_Advanced_Now = Reading_GOV_Now = false; }
static bool has(const std::vector<std::string> &v, const char *s) { for (auto &x : v) if (x == s) return true; return false; }
static int count(const std::vector<std::string> &v, const char *s) { int n = 0; for (auto &x : v) if (x == s) ++n; return n; }
int main() {
    for (int i = 0; i < MAX_RATES_BYTES; ++i) Rate_Values[i] = (uint8_t)(10 + i);
    // 1. not without the pipe, not offline, not on another page, not when the queue refuses the read: nothing asked or said
    reset(); PipeState = 1; CHECK(!RfVerifyArm(VK_RATES, RatesAskValues) && asks == 0 && !RfVerifyPending() && msgs.empty());
    reset(); PipeState = 2; bakOffline = true; CHECK(!RfVerifyArm(VK_RATES, RatesAskValues) && asks == 0 && !RfVerifyPending()); bakOffline = false;
    reset(); CurrentView = PIDVIEW; CHECK(!RfVerifyArm(VK_RATES, RatesAskValues) && asks == 0); CurrentView = RATESVIEW_RF;
    reset(); CHECK(!RfVerifyArm(VK_RATES, RefusedAsk) && asks == 1 && !RfVerifyPending() && msgs.empty());
    reset(); CHECK(!RfVerifyArm(VK_RATES, nullptr) && asks == 0);
    // 2. armed: the page's read asked, a 4 s window, the message up, Save hidden, the bank switch held
    reset(); nowMs = 5000; CHECK(RfVerifyArm(VK_RATES, RatesAskValues) && asks == 1 && RfVerifyPending() && Reading_RATES_Now && RATES_Send_Duration == 4000 && RATES_Start_Time == 5000);
    CHECK(msgs.size() == 1 && msgs[0] == "rates:Sent: reading back from the flight controller ..." && has(cmds, "vis b3,0") && BlockBankChanges);
    // the same set back (the read filled the same values): done - hidden, "Saved ..." on the line, the done sound, the page may close, the window closed
    RfValueWasCut = true; CHECK(RfVerifySet() == 1 && !RfVerifyPending() && !Reading_RATES_Now && has(hides, "rates") && texts["busy"] == "Saved, and confirmed by reading it back." && has(cmds, "vis busy,1"));
    CHECK(sounds.size() == 1 && sounds[0] == "done" && leaves == 1 && cutNotes == 1 && boxes == 0 && edited.empty() && reds.empty());
    // the line goes after 3 s - not while another read has it
    cmds.clear(); nowMs = 7999; RfVerifyTick(); CHECK(!has(cmds, "vis busy,0")); nowMs = 8000; Reading_RATES_Now = true; RfVerifyTick(); CHECK(!has(cmds, "vis busy,0"));
    Reading_RATES_Now = false; RfVerifyTick(); CHECK(!has(cmds, "vis busy,0"));   // (the time was taken by the look above: once)
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); RfVerifySet(); cmds.clear(); nowMs = 8000; RfVerifyTick(); CHECK(has(cmds, "vis busy,0"));
    cmds.clear(); nowMs = 9000; RfVerifyTick(); CHECK(cmds.empty());   // (once)
    // ... and not on another page
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); RfVerifySet(); cmds.clear(); CurrentView = ROTORFLIGHTVIEW; nowMs = 8000; RfVerifyTick(); CHECK(cmds.empty()); CurrentView = RATESVIEW_RF;
    // the verdict ended it: the window's end says nothing more
    CHECK(!RfVerifyEnd(VK_RATES) && boxes == 0);
    // 3. a different set: the window runs on (the caller clears the set); at its end the values sent go back, the box in red, Save shown, a message
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues);
    Rate_Values[1] = 0;   // (the roll rate came back 0: what B152 was about)
    CHECK(RfVerifySet() == 2 && RfVerifyPending() && Reading_RATES_Now && boxes == 0 && hides.empty());
    CHECK(RfVerifySet() == 2);   // (the same again: still waiting)
    RfValueWasCut = true;
    CHECK(RfVerifyEnd(VK_RATES) && !RfVerifyPending() && !RfValueWasCut && has(hides, "rates") && boxes == 1 && lastBoxPage == "page RatesView");
    CHECK(lastBox.find("NOT SAVED: the flight controller holds\r\nother values for 1 box, shown in red.") == 0 && Rate_Values[1] == 11 && has(displays, "rates 0-13") && reds.size() == 1 && reds[0] == "tn0" && has(edited, "rates") && sounds.size() == 1 && sounds[0] == "whah" && leaves == 0 && cutNotes == 0);
    // two boxes differ, the type among them (its box is t10)
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); Rate_Values[0] = 4; Rate_Values[12] = 99; CHECK(RfVerifySet() == 2); CHECK(RfVerifyEnd(VK_RATES) && lastBox.find("other values for 2 boxes") != std::string::npos && reds.size() == 2 && reds[0] == "t10" && reds[1] == "tn11" && Rate_Values[0] == 10 && Rate_Values[12] == 22);
    // 4. nothing came in the window: "NOT CONFIRMED", Save shown, the page left as it is
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CHECK(RfVerifyEnd(VK_RATES) && boxes == 1 && lastBox.find("NOT CONFIRMED") == 0 && displays.empty() && reds.empty() && has(edited, "rates") && has(hides, "rates") && sounds.size() == 1 && sounds[0] == "whah" && !RfVerifyPending());
    // 5. a bank change read afresh (a new start time) or the page left: nothing compared, nothing said, the page's own hide runs as ever
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); Rate_Values[1] = 0; CHECK(RfVerifySet() == 0 && !RfVerifyPending() && boxes == 0 && hides.empty() && !RfVerifyEnd(VK_RATES)); Rate_Values[1] = 11;
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CurrentView = ROTORFLIGHTVIEW; CHECK(RfVerifySet() == 0 && !RfVerifyPending() && boxes == 0 && hides.empty()); CurrentView = RATESVIEW_RF;
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CurrentView = ROTORFLIGHTVIEW; CHECK(!RfVerifyEnd(VK_RATES) && !RfVerifyPending() && boxes == 0); CurrentView = RATESVIEW_RF;
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CHECK(!RfVerifyEnd(VK_PID) && RfVerifyPending());   // (another kind's window: not ours)
    // 6. the PIDs: 17 words - the twelve, three boosts, two HSI offsets - on n0..n16; a boost that differs is n13
    CurrentView = PIDVIEW; for (int i = 0; i < MAX_PID_WORDS; ++i) PID_Values[i] = 100 + i; PID_Boost_Values[0] = 1; PID_Boost_Values[1] = 2; PID_Boost_Values[2] = 3; PID_HSI_Offset_Values[0] = 4; PID_HSI_Offset_Values[1] = 5;
    reset(); nowMs = 6000; CHECK(RfVerifyArm(VK_PID, PidAskValues) && Reading_PIDS_Now && PID_Send_Duration == 4000 && msgs[0].find("pid:Sent") == 0);
    PID_Boost_Values[1] = 7; PID_HSI_Offset_Values[1] = 9; CHECK(RfVerifySet() == 2); CHECK(RfVerifyEnd(VK_PID) && lastBoxPage == "page PIDView" && reds.size() == 2 && reds[0] == "n13" && reds[1] == "n16" && PID_Boost_Values[1] == 2 && PID_HSI_Offset_Values[1] == 5);
    CHECK(count(displays, "pid 0") == 1 && count(displays, "pid 10") == 1 && count(displays, "boost") == 1 && displays.size() == 7 && has(edited, "pid") && has(hides, "pid"));
    reset(); nowMs = 6000; RfVerifyArm(VK_PID, PidAskValues); CHECK(RfVerifySet() == 1 && has(hides, "pid") && leaves == 1 && !Reading_PIDS_Now);
    // 7. the governor's bank page: what was sent is GovWritePayload 1..17 (byte 0 is never written), the read fills GovAckPayload; the headspeed's two bytes are n0, byte 3 is n1, byte 15 n13, the flags have no box
    CurrentView = RFGOVERNORVIEW_PROFILE; for (int i = 0; i < 18; ++i) { GovWritePayload[i] = (uint8_t)(50 + i); GovAckPayload[i] = (uint8_t)(50 + i); } GovWritePayload[0] = 0; GovAckPayload[0] = 1;
    reset(); nowMs = 7000; CHECK(RfVerifyArm(VK_GOV, GovAskValues) && Reading_GOV_Now && GOV_Send_Duration == 4000 && msgs[0].find("gov:Sent") == 0);
    CHECK(RfVerifySet() == 1 && has(hides, "gov") && leaves == 1);   // (byte 0 differs, and does not matter)
    reset(); nowMs = 7000; RfVerifyArm(VK_GOV, GovAskValues); GovAckPayload[2] = 0; GovAckPayload[3] = 0; GovAckPayload[15] = 0; GovAckPayload[17] = 0; CHECK(RfVerifySet() == 2);
    CHECK(RfVerifyEnd(VK_GOV) && lastBoxPage == "page RFGovView" && lastBox.find("other values for 4 boxes") != std::string::npos && reds.size() == 3 && reds[0] == "n0" && reds[1] == "n1" && reds[2] == "n13" && GovAckPayload[2] == 52 && GovAckPayload[17] == 67 && has(displays, "gov 1-18") && has(edited, "gov"));
    // 8. the advanced pages: their own boxes
    CurrentView = RATESADVANCEDVIEW; for (int i = 0; i < MAX_RATES_ADVANCED_BYTES; ++i) Rate_Advanced_Values[i] = (uint8_t)(30 + i);
    reset(); nowMs = 8000; CHECK(RfVerifyArm(VK_RATES_ADV, RatesAdvAskValues) && Reading_RATES_Advanced_Now && Rates_Advanced_Send_Duration == 4000 && msgs[0].find("ratesadv:Sent") == 0);
    Rate_Advanced_Values[14] = 1; CHECK(RfVerifySet() == 2 && RfVerifyEnd(VK_RATES_ADV) && lastBoxPage == "page Rates_A_View" && reds.size() == 1 && reds[0] == "t14" && Rate_Advanced_Values[14] == 44 && has(displays, "ratesadv 0-15") && has(edited, "ratesadv") && has(hides, "ratesadv"));
    CurrentView = PIDADVANCEDVIEW; for (int i = 0; i < MAX_PIDS_ADVANCED_BYTES; ++i) PID_Advanced_Values[i] = (uint8_t)(60 + i);
    reset(); nowMs = 9000; CHECK(RfVerifyArm(VK_PID_ADV, PidAdvAskValues) && Reading_PIDS_Advanced_Now && PID_Advanced_Send_Duration == 4000 && msgs[0].find("pidadv:Sent") == 0);
    PID_Advanced_Values[0] = 0; PID_Advanced_Values[25] = 0; CHECK(RfVerifySet() == 2 && RfVerifyEnd(VK_PID_ADV) && lastBoxPage == "page PID_A_View" && reds.size() == 2 && reds[0] == "sw0" && reds[1] == "t25" && PID_Advanced_Values[0] == 60 && has(displays, "pidadv 0-26") && has(edited, "pidadv") && has(hides, "pidadv"));
    reset(); nowMs = 9000; RfVerifyArm(VK_PID_ADV, PidAdvAskValues); CHECK(RfVerifySet() == 1 && leaves == 1 && !Reading_PIDS_Advanced_Now);
    printf("test_verify: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp()
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr); sys.exit(1)
run = subprocess.run([os.path.join(d, 't')], capture_output=True, text=True)
print(run.stdout, end=''); print(run.stderr, end='', file=sys.stderr)
sys.exit(run.returncode)
