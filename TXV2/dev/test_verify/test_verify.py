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
import re
FLOOR = re.search(r'^#define RF_SAVE_HOLD_FLOOR_MS (\d+)', open(os.path.join(ROOT, 'TransmitterCode', 'include', '1Definitions.h'), encoding='utf-8', errors='replace').read(), re.M).group(1)   # (e101b)
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
#define RFGOVERNORVIEW_GLOBAL 55
#define ROTORFLIGHTVIEW 44
#define BEEPCOMPLETE 2
#define WHAHWHAHMSG 1
#define Gray 33840
#define Red 63488
#define RF_VERIFY_WAIT_MS 4000
#define RF_SAVE_HOLD_FLOOR_MS @FLOOR@   // (e101b: 1Definitions.h's own value - RF_Verify.h's static_assert holds it)
#define RF_VERIFY_GOVCFG_WAIT_MS 8000
#define MSP_WAIT_TIME 2500           // (e99d, 18 Nov 2026: RF_Verify.h's static_assert - 1Definitions.h's values)
#define GOV_PROFILE_WAIT_TIME 2500
enum { VK_NONE = 0, VK_RATES, VK_RATES_ADV, VK_PID, VK_PID_ADV, VK_GOV, VK_GOV_CFG };
static uint32_t nowMs = 1000; static uint32_t millis() { return nowMs; }
static bool bigScreen = false; static bool ScreenIsBig() { return bigScreen; }   // B195
static int CurrentView = RATESVIEW_RF;
static uint8_t Bank = 1, DualRateInUse = 1;   // (e99b, 17 Nov 2026: RfVerifyArm notes the bank and the rate a save was made on - VfBank, VfRate)
static uint8_t PipeState = 2; static bool BoundFlag = true, ModelMatched = true, bakOffline = false; static bool BakOffline() { return bakOffline; }
static bool BlockShown = false;   // (e99e, 18 Nov 2026: RfVerifyEnd's one more ask looks at it - transceiver.h's)
static bool BlockBankChanges = false, RfValueWasCut = false, GOVS_GLOBAL_Were_Edited = false;
static bool Reading_PIDS_Now = false, Reading_RATES_Now = false, Reading_RATES_Advanced_Now = false, Reading_PIDS_Advanced_Now = false, Reading_GOV_Now = false, Reading_GOV_Config_Now = false;
static uint32_t RATES_Start_Time = 0, RATES_Advanced_Start_Time = 0, PID_Start_Time = 0, PID_Advanced_Start_Time = 0, GOV_Start_Time = 0, GOV_Global_Start_Time = 0;
static uint16_t RATES_Send_Duration = 0, PID_Send_Duration = 0, Rates_Advanced_Send_Duration = 0, PID_Advanced_Send_Duration = 0; static uint32_t GOV_Send_Duration = 0, GOV_Config_Send_Duration = 0;
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
static bool mayFly = false; static int quiet = 0;   // (10 Nov 2026) PipeHttp.h's: no box while the model may fly, a line in the log instead
static bool RfMayFly() { return mayFly; }
static void RfSayQuietly(const char *) { ++quiet; }
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
// B165: the governor's global page - its message line is t4, its hide the quiet one, its display the config bytes
static void ShowGOVConfigMsg(const char *m, uint16_t) { msgs.push_back(std::string("govcfg:") + m); }
static void HideGOVConfigMsgQuiet() { hides.push_back("govcfg"); BlockBankChanges = false; }
static void DisplayGovConfigValues(uint8_t a, uint8_t b) { displays.push_back("govcfg " + std::to_string(a) + "-" + std::to_string(b)); }
static void Gov_Global_Were_Edited() { edited.push_back("govcfg"); GOVS_GLOBAL_Were_Edited = true; }
static void GovCfgAskValues() { ++asks; GOV_Config_Send_Duration = 4000; Reading_GOV_Config_Now = true; GOV_Global_Start_Time = millis(); }
// the pages' own reads (their AskValues) as they are: the kind's flag, window and start time
static void RatesAskValues() { ++asks; RATES_Send_Duration = 2500; Reading_RATES_Now = true; RATES_Start_Time = millis(); }
static void RatesAdvAskValues() { ++asks; Rates_Advanced_Send_Duration = 2500; Reading_RATES_Advanced_Now = true; RATES_Advanced_Start_Time = millis(); }
static void PidAskValues() { ++asks; PID_Send_Duration = 2500; Reading_PIDS_Now = true; PID_Start_Time = millis(); }
static void PidAdvAskValues() { ++asks; PID_Advanced_Send_Duration = 2500; Reading_PIDS_Advanced_Now = true; PID_Advanced_Start_Time = millis(); }
static void GovAskValues() { ++asks; GOV_Send_Duration = 2500; Reading_GOV_Now = true; GOV_Start_Time = millis(); }
static void RefusedAsk() { ++asks; }   // (the queue refused it: no pipe after all - the flag stays down)
bool RfVerifyArm(uint8_t kind, void (*ask)()); bool RfVerifyPending(); bool RfVerifyFollows(); bool RfSaveHoldsBank(); int RfVerifySet(); bool RfVerifyEnd(uint8_t kind); void RfVerifyTick();
'''.replace('@FLOOR@', FLOOR) + open(HDR).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void reset() { cmds.clear(); msgs.clear(); hides.clear(); displays.clear(); edited.clear(); reds.clear(); sounds.clear(); texts.clear(); boxes = leaves = cutNotes = asks = 0; lastBox.clear(); BlockBankChanges = false; BlockShown = false; RfValueWasCut = false;
    Reading_PIDS_Now = Reading_RATES_Now = Reading_RATES_Advanced_Now = Reading_PIDS_Advanced_Now = Reading_GOV_Now = Reading_GOV_Config_Now = false; }
static bool has(const std::vector<std::string> &v, const char *s) { for (auto &x : v) if (x == s) return true; return false; }
static int count(const std::vector<std::string> &v, const char *s) { int n = 0; for (auto &x : v) if (x == s) ++n; return n; }
// B177: the verdict comes after three asks. EndDiffer: the stream brings the (differing) set again in each new window, as the
// receiver does; EndNothing: nothing comes in any window.
static bool EndDiffer(uint8_t k) { for (int i = 0; i < 3; ++i) { if (!RfVerifyEnd(k)) return false; if (!RfVerifyPending()) return true; RfVerifySet(); } return false; }
static bool EndNothing(uint8_t k) { for (int i = 0; i < 3; ++i) { if (!RfVerifyEnd(k)) return false; if (!RfVerifyPending()) return true; } return false; }
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
    CHECK(EndDiffer(VK_RATES) && !RfVerifyPending() && !RfValueWasCut && has(hides, "rates") && boxes == 1 && lastBoxPage == "page RatesView");
    CHECK(lastBox.find("NOT SAVED: the flight controller holds\r\nother values for 1 box, shown in red.") == 0 && Rate_Values[1] == 11 && has(displays, "rates 0-13") && reds.size() == 1 && reds[0] == "tn0" && has(edited, "rates") && sounds.size() == 1 && sounds[0] == "whah" && leaves == 0 && cutNotes == 0);
    // two boxes differ, the type among them (its box is t10)
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); Rate_Values[0] = 4; Rate_Values[12] = 99; CHECK(RfVerifySet() == 2); CHECK(EndDiffer(VK_RATES) && lastBox.find("other values for 2 boxes") != std::string::npos && reds.size() == 2 && reds[0] == "t10" && reds[1] == "tn11" && Rate_Values[0] == 10 && Rate_Values[12] == 22);
    // 4. nothing came in the window: "NOT CONFIRMED", Save shown, the page left as it is
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CHECK(EndNothing(VK_RATES) && boxes == 1 && lastBox.find("NOT CONFIRMED") == 0 && displays.empty() && reds.empty() && has(edited, "rates") && has(hides, "rates") && sounds.size() == 1 && sounds[0] == "whah" && !RfVerifyPending());
    // (10 Nov 2026, the code review) the safety turned off since the Save: no box (it would freeze the switches), a line in the log, the page as it is
    reset(); mayFly = true; quiet = 0; nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CHECK(EndNothing(VK_RATES) && boxes == 0 && quiet == 1 && has(edited, "rates")); mayFly = false;
    // 5. a bank change read afresh (a new start time) or the page left: nothing compared, nothing said, the page's own hide runs as ever
    // (e99b, 17 Nov 2026: a read asked afresh on the SAME bank and rate is now followed - below. This row is the bank change it names: the bank really changed)
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; Bank = 2; RatesAskValues(); Rate_Values[1] = 0; CHECK(RfVerifySet() == 0 && !RfVerifyPending() && boxes == 0 && hides.empty() && !RfVerifyEnd(VK_RATES)); Rate_Values[1] = 11; Bank = 1;
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; DualRateInUse = 2; RatesAskValues(); Rate_Values[1] = 0; CHECK(RfVerifySet() == 0 && !RfVerifyPending() && boxes == 0 && hides.empty() && !RfVerifyEnd(VK_RATES)); Rate_Values[1] = 11; DualRateInUse = 1;
    // 5b. (e99b) A SAVE FOLLOWED BEHIND A FRESH ASK OF ITS OWN PAGE, the same bank and rate: a set that differs is no set (held, nothing said, pending);
    //     what was sent ends it as a plain set (0: marked, freed, nothing said); the fresh read's window end drops it with nothing said
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); Rate_Values[1] = 0; CHECK(RfVerifySet() == 2 && RfVerifyPending() && boxes == 0 && hides.empty() && sounds.empty());
    Rate_Values[1] = 11; CHECK(RfVerifySet() == 0 && !RfVerifyPending() && boxes == 0 && sounds.empty());
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); Rate_Values[1] = 0; CHECK(RfVerifySet() == 2); nowMs = 7700; Reading_RATES_Now = false; CHECK(RfVerifyEnd(VK_RATES) && asks == 3 && VfKind == VK_RATES && RfVerifyPending() && boxes == 0 && sounds.empty()); Rate_Values[1] = 11;   // (e99e: the fresh read's window end no longer drops it with nothing: it asks ONCE more - G3; nothing said. e99f: the save 2.7 s old - that ask is FOLLOWED too)
    // (e99d, 18 Nov 2026: G6) the page left, what was sent comes back: THE READ ENDS THERE - 1, its flag down, its Hide routine called (it frees the bank
    // switch), nothing said, no sound, no "Saved" line, the page not closed. (Before e99d this row read 0 with nothing hidden: the flag stayed up.)
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CurrentView = ROTORFLIGHTVIEW; BlockBankChanges = true;
    CHECK(RfVerifySet() == 1 && !RfVerifyPending() && !Reading_RATES_Now && has(hides, "rates") && !BlockBankChanges && boxes == 0 && sounds.empty() && texts["busy"] != "Saved, and confirmed by reading it back." && leaves == 0 && edited.empty()); CurrentView = RATESVIEW_RF;
    // ... a set that differs off the page: no set (2), the read and the bank switch kept, nothing said
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CurrentView = ROTORFLIGHTVIEW; Rate_Values[1] = 0; CHECK(RfVerifySet() == 2 && RfVerifyPending() && Reading_RATES_Now && hides.empty() && BlockBankChanges && boxes == 0); Rate_Values[1] = 11; CurrentView = RATESVIEW_RF;
    // (e99e, 18 Nov 2026 - replaces e99d's "flag down: let go" and its 1.5 s rows) ONE RULE: a save left behind is followed for RF_VERIFY_WAIT_MS (4 s) from the
    // save. Its flag down (another page's ask): NOT pending (no read open), but KEPT (VfKind) until the save is 4 s old - then let go by RfVerifyPending, nothing said
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CurrentView = ROTORFLIGHTVIEW; Reading_RATES_Now = false; CHECK(!RfVerifyPending() && VfKind == VK_RATES && boxes == 0 && hides.empty() && sounds.empty());
    nowMs = 8999; CHECK(!RfVerifyPending() && VfKind == VK_RATES); nowMs = 9000; CHECK(!RfVerifyPending() && VfKind == VK_NONE && boxes == 0 && hides.empty() && sounds.empty()); CurrentView = RATESVIEW_RF;
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); Reading_RATES_Now = false; CHECK(!RfVerifyPending() && VfKind == VK_RATES && boxes == 0 && hides.empty()); nowMs = 9000; CHECK(!RfVerifyPending() && VfKind == VK_NONE);
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); Reading_PIDS_Now = true; CHECK(RfVerifyPending()); Reading_PIDS_Now = false;   // (another kind's flag is not its own)
    // its OWN read still open off its page: kept past 4 s (to that read's window: RfVerifyEnd), not let go by the time
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CurrentView = ROTORFLIGHTVIEW; nowMs = 9050; CHECK(RfVerifyPending() && VfKind == VK_RATES); CurrentView = RATESVIEW_RF;
    // kept on another page, its page asked afresh within the 4 s (PID + behind the PIDs page): followed again - a set that differs is no set
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CurrentView = PIDVIEW; PidAskValues(); Reading_RATES_Now = false; nowMs = 6000; CHECK(!RfVerifyPending() && VfKind == VK_RATES);
    Reading_PIDS_Now = false; CurrentView = RATESVIEW_RF; nowMs = 6500; RatesAskValues(); Rate_Values[1] = 0; CHECK(RfVerifyPending() && RfVerifySet() == 2 && boxes == 0 && sounds.empty()); Rate_Values[1] = 11;
    CHECK(RfVerifySet() == 0 && VfKind == VK_NONE && boxes == 0 && sounds.empty());   // (what was sent: the write landed - a plain set)
    // ... kept on another page, a bank change there: let go at once
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CurrentView = PIDVIEW; PidAskValues(); Reading_RATES_Now = false; Bank = 2; CHECK(RfVerifySet() == 0 && VfKind == VK_NONE); Bank = 1; Reading_PIDS_Now = false; CurrentView = RATESVIEW_RF;
    // behind a fresh ask of its own page: followed while the save is younger than 4 s - a set that differs at 3.999 s is no set (2); at 4 s a plain set (0), let go, nothing said
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); Rate_Values[1] = 0; nowMs = 6599; CHECK(RfVerifySet() == 2 && RfVerifyPending()); nowMs = 8999; CHECK(RfVerifySet() == 2 && RfVerifyPending());
    nowMs = 9000; CHECK(RfVerifySet() == 0 && !RfVerifyPending() && VfKind == VK_NONE && Reading_RATES_Now && boxes == 0 && sounds.empty() && hides.empty()); Rate_Values[1] = 11;
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); nowMs = 6599; CHECK(RfVerifySet() == 0 && !RfVerifyPending() && boxes == 0 && sounds.empty());   // (what was sent, early: a plain set, the write landed)
    // (e99e: G3) THE ONE MORE ASK: a fresh read answered whole, never with what was sent, its window over -> the page's own read once more, plain (one ask, true);
    // that read's end asks nothing more; nothing said
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); Rate_Values[1] = 0; CHECK(RfVerifySet() == 2); CHECK(asks == 2);
    nowMs = 7700; Reading_RATES_Now = false; CHECK(RfVerifyEnd(VK_RATES) && asks == 3 && Reading_RATES_Now && VfAfresh == VK_NONE && boxes == 0 && sounds.empty());
    // (e99f, 18 Nov 2026: e99e's own tests) the save only 2.7 s old: the read-back is KEPT (VfKind) and followed through this ask - pending, its window looked at
    CHECK(VfKind == VK_RATES && RfVerifyPending());
    // ... and THAT ask answered with the old block before the save is 4 s old: no set again (2) and the note again - a SECOND more ask at its window's end
    nowMs = 7800; CHECK(RfVerifySet() == 2 && VfAfresh == VK_RATES && VfKind == VK_RATES && boxes == 0 && sounds.empty());
    nowMs = 10300; Reading_RATES_Now = false; CHECK(RfVerifyEnd(VK_RATES) && asks == 4 && Reading_RATES_Now && VfKind == VK_NONE && VfAfresh == VK_NONE && boxes == 0 && sounds.empty());   // (the save 5.3 s old: let go, the ask plain)
    CHECK(RfVerifySet() == 0); BlockShown = true;   // (the plain read: the old set shown, whole)
    nowMs = 12900; Reading_RATES_Now = false; CHECK(!RfVerifyEnd(VK_RATES) && asks == 4 && boxes == 0 && sounds.empty());   // (no third: the note is gone, the save let go)
    BlockShown = false; Rate_Values[1] = 11;
    // ... the more ask's old block coming AFTER the save's 4 s: a plain set, the note gone - one more ask only
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); Rate_Values[1] = 0; CHECK(RfVerifySet() == 2); nowMs = 7700; Reading_RATES_Now = false; CHECK(RfVerifyEnd(VK_RATES) && asks == 3);
    nowMs = 9050; CHECK(RfVerifySet() == 0 && VfKind == VK_NONE && VfAfresh == VK_NONE); BlockShown = true; nowMs = 10300; Reading_RATES_Now = false; CHECK(!RfVerifyEnd(VK_RATES) && asks == 3 && boxes == 0); BlockShown = false; Rate_Values[1] = 11;
    // ... the write LANDING inside that more ask's window (before the save's 4 s): what was sent - the read-back ends, a plain set from here (shown), no more ask
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); Rate_Values[1] = 0; CHECK(RfVerifySet() == 2); nowMs = 7700; Reading_RATES_Now = false; CHECK(RfVerifyEnd(VK_RATES) && asks == 3);
    Rate_Values[1] = 11; nowMs = 8200; CHECK(RfVerifySet() == 0 && VfKind == VK_NONE && VfAfresh == VK_NONE && boxes == 0 && sounds.empty()); BlockShown = true; nowMs = 10300; Reading_RATES_Now = false; CHECK(!RfVerifyEnd(VK_RATES) && asks == 3); BlockShown = false;
    // ... the more ask NOT answered at all (the controller fell silent): its window's end, the save 5.3 s old - let go, nothing asked, nothing said
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); Rate_Values[1] = 0; CHECK(RfVerifySet() == 2); nowMs = 7700; Reading_RATES_Now = false; CHECK(RfVerifyEnd(VK_RATES) && asks == 3);
    nowMs = 10300; Reading_RATES_Now = false; CHECK(!RfVerifyEnd(VK_RATES) && asks == 3 && boxes == 0 && sounds.empty()); RfVerifyPending(); CHECK(VfKind == VK_NONE && VfAfresh == VK_NONE); Rate_Values[1] = 11;
    // ... not when the block was shown (BlockShown), not off its page, not when nothing came (no whole set: silent - the plain "nothing came back" line)
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); Rate_Values[1] = 0; RfVerifySet(); BlockShown = true; nowMs = 7700; Reading_RATES_Now = false; CHECK(!RfVerifyEnd(VK_RATES) && asks == 2 && VfKind == VK_RATES); nowMs = 9000; RfVerifyPending(); CHECK(VfKind == VK_NONE); BlockShown = false; Rate_Values[1] = 11;   // (e99f: kept to the save's 4 s, then let go by RfVerifyPending)
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); Rate_Values[1] = 0; RfVerifySet(); CurrentView = ROTORFLIGHTVIEW; nowMs = 7700; Reading_RATES_Now = false; CHECK(!RfVerifyEnd(VK_RATES) && asks == 2); CurrentView = RATESVIEW_RF; Rate_Values[1] = 11;
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); nowMs = 7700; Reading_RATES_Now = false; CHECK(!RfVerifyEnd(VK_RATES) && asks == 2 && boxes == 0);
    // ... the save's 4 s over inside the fresh window: the next set is plain (shown), the note gone - no extra ask at the window's end
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 7000; RatesAskValues(); Rate_Values[1] = 0; nowMs = 8000; CHECK(RfVerifySet() == 2); nowMs = 9100; CHECK(RfVerifySet() == 0); BlockShown = true;
    nowMs = 9600; Reading_RATES_Now = false; CHECK(!RfVerifyEnd(VK_RATES) && asks == 2); Rate_Values[1] = 11;
    // (round 25) the one more ask's note is taken away: by the write landing, by a plain set, by a new save - none asks at the window's end (BlockShown false: the asking condition left to the note alone)
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); Rate_Values[1] = 0; RfVerifySet(); Rate_Values[1] = 11; CHECK(RfVerifySet() == 0 && VfAfresh == VK_NONE); nowMs = 7700; Reading_RATES_Now = false; CHECK(!RfVerifyEnd(VK_RATES) && asks == 2);
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 7000; RatesAskValues(); Rate_Values[1] = 0; nowMs = 8000; RfVerifySet(); nowMs = 9100; CHECK(RfVerifySet() == 0 && VfAfresh == VK_NONE); nowMs = 9600; Reading_RATES_Now = false; CHECK(!RfVerifyEnd(VK_RATES) && asks == 2); Rate_Values[1] = 11;
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); Rate_Values[1] = 0; RfVerifySet(); nowMs = 5200; CHECK(RfVerifyArm(VK_RATES, RatesAskValues) && VfAfresh == VK_NONE); nowMs = 9300; Reading_RATES_Now = false; CHECK(RfVerifyEnd(VK_RATES) && has(msgs, "rates:Reading back again (2 of 3) ...")); Rate_Values[1] = 11;
    // (e99e) RfVerifyFollows: a bank page's read-back with its read open - not the Governor global page's
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CHECK(RfVerifyFollows()); Reading_RATES_Now = false; CHECK(!RfVerifyFollows());
    CurrentView = RFGOVERNORVIEW_GLOBAL; reset(); nowMs = 5000; RfVerifyArm(VK_GOV_CFG, GovCfgAskValues); CHECK(RfVerifyPending() && !RfVerifyFollows()); CurrentView = RATESVIEW_RF;
    // (e99g, 18 Nov 2026: e99f's tests, finding 1) ONLY THE READ THE READ-BACK ITSELF ASKED is followed at the motor switch: its own read off its page - yes;
    // its own ask again on its page (B177, "Reading back again") - yes; a FRESH ask of the page behind the save (the pilot's) - no, though pending; the one more ask - no
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CurrentView = ROTORFLIGHTVIEW; nowMs = 6000; CHECK(RfVerifyPending() && RfVerifyFollows()); CurrentView = RATESVIEW_RF;
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 9000; Reading_RATES_Now = false; Rate_Values[1] = 0; CHECK(RfVerifyEnd(VK_RATES) && Reading_RATES_Now && RfVerifyPending() && RfVerifyFollows()); Rate_Values[1] = 11;
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); CHECK(RfVerifyPending() && VfKind == VK_RATES && !RfVerifyFollows());
    nowMs = 8999; CHECK(RfVerifyPending() && !RfVerifyFollows());
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 5100; RatesAskValues(); Rate_Values[1] = 0; CHECK(RfVerifySet() == 2); nowMs = 7700; Reading_RATES_Now = false; CHECK(RfVerifyEnd(VK_RATES) && asks == 3 && VfKind == VK_RATES && RfVerifyPending() && !RfVerifyFollows()); Rate_Values[1] = 11;
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CurrentView = ROTORFLIGHTVIEW; nowMs = 9001; Reading_RATES_Now = false; CHECK(!RfVerifyEnd(VK_RATES) && !RfVerifyPending() && VfKind == VK_NONE && boxes == 0); CurrentView = RATESVIEW_RF;   // (e99e: its own window's end off its page - the flag lowered first, as Hide_msg_if_needed does; before e99e the row called it at 0 s with the flag up)
    reset(); nowMs = 5000; RfVerifyArm(VK_RATES, RatesAskValues); CHECK(!RfVerifyEnd(VK_PID) && RfVerifyPending());   // (another kind's window: not ours)
    // 6. the PIDs: 17 words - the twelve, three boosts, two HSI offsets - on n0..n16; a boost that differs is n13
    CurrentView = PIDVIEW; for (int i = 0; i < MAX_PID_WORDS; ++i) PID_Values[i] = 100 + i; PID_Boost_Values[0] = 1; PID_Boost_Values[1] = 2; PID_Boost_Values[2] = 3; PID_HSI_Offset_Values[0] = 4; PID_HSI_Offset_Values[1] = 5;
    reset(); nowMs = 6000; CHECK(RfVerifyArm(VK_PID, PidAskValues) && Reading_PIDS_Now && PID_Send_Duration == 4000 && msgs[0].find("pid:Sent") == 0);
    PID_Boost_Values[1] = 7; PID_HSI_Offset_Values[1] = 9; CHECK(RfVerifySet() == 2); CHECK(EndDiffer(VK_PID) && lastBoxPage == "page PIDView" && reds.size() == 2 && reds[0] == "n13" && reds[1] == "n16" && PID_Boost_Values[1] == 2 && PID_HSI_Offset_Values[1] == 5);
    CHECK(count(displays, "pid 0") == 1 && count(displays, "pid 10") == 1 && count(displays, "boost") == 1 && displays.size() == 7 && has(edited, "pid") && has(hides, "pid"));
    reset(); nowMs = 6000; RfVerifyArm(VK_PID, PidAskValues); CHECK(RfVerifySet() == 1 && has(hides, "pid") && leaves == 1 && !Reading_PIDS_Now);
    // 7. the governor's bank page: what was sent is GovWritePayload 1..17 (byte 0 is never written), the read fills GovAckPayload; the headspeed's two bytes are n0, byte 3 is n1, byte 15 n13, the flags have no box
    CurrentView = RFGOVERNORVIEW_PROFILE; for (int i = 0; i < 18; ++i) { GovWritePayload[i] = (uint8_t)(50 + i); GovAckPayload[i] = (uint8_t)(50 + i); } GovWritePayload[0] = 0; GovAckPayload[0] = 1;
    reset(); nowMs = 7000; CHECK(RfVerifyArm(VK_GOV, GovAskValues) && Reading_GOV_Now && GOV_Send_Duration == 4000 && msgs[0].find("gov:Sent") == 0);
    CHECK(RfVerifySet() == 1 && has(hides, "gov") && leaves == 1);   // (byte 0 differs, and does not matter)
    reset(); nowMs = 7000; RfVerifyArm(VK_GOV, GovAskValues); GovAckPayload[2] = 0; GovAckPayload[3] = 0; GovAckPayload[15] = 0; GovAckPayload[17] = 0; CHECK(RfVerifySet() == 2);
    CHECK(EndDiffer(VK_GOV) && lastBoxPage == "page RFGovView" && lastBox.find("other values for 4 boxes") != std::string::npos && reds.size() == 3 && reds[0] == "n0" && reds[1] == "n1" && reds[2] == "n13" && GovAckPayload[2] == 52 && GovAckPayload[17] == 67 && has(displays, "gov 1-18") && has(edited, "gov"));
    // 8. the advanced pages: their own boxes
    CurrentView = RATESADVANCEDVIEW; for (int i = 0; i < MAX_RATES_ADVANCED_BYTES; ++i) Rate_Advanced_Values[i] = (uint8_t)(30 + i);
    reset(); nowMs = 8000; CHECK(RfVerifyArm(VK_RATES_ADV, RatesAdvAskValues) && Reading_RATES_Advanced_Now && Rates_Advanced_Send_Duration == 4000 && msgs[0].find("ratesadv:Sent") == 0);
    Rate_Advanced_Values[14] = 1; CHECK(RfVerifySet() == 2 && EndDiffer(VK_RATES_ADV) && lastBoxPage == "page Rates_A_View" && reds.size() == 1 && reds[0] == "t14" && Rate_Advanced_Values[14] == 44 && has(displays, "ratesadv 0-15") && has(edited, "ratesadv") && has(hides, "ratesadv"));
    CurrentView = PIDADVANCEDVIEW; for (int i = 0; i < MAX_PIDS_ADVANCED_BYTES; ++i) PID_Advanced_Values[i] = (uint8_t)(60 + i);
    reset(); nowMs = 9000; CHECK(RfVerifyArm(VK_PID_ADV, PidAdvAskValues) && Reading_PIDS_Advanced_Now && PID_Advanced_Send_Duration == 4000 && msgs[0].find("pidadv:Sent") == 0);
    PID_Advanced_Values[0] = 0; PID_Advanced_Values[25] = 0; CHECK(RfVerifySet() == 2 && EndDiffer(VK_PID_ADV) && lastBoxPage == "page PID_A_View" && reds.size() == 2 && reds[0] == "sw0" && reds[1] == "t25" && PID_Advanced_Values[0] == 60 && has(displays, "pidadv 0-26") && has(edited, "pidadv") && has(hides, "pidadv"));
    reset(); nowMs = 9000; RfVerifyArm(VK_PID_ADV, PidAdvAskValues); CHECK(RfVerifySet() == 1 && leaves == 1 && !Reading_PIDS_Advanced_Now);
    // 9. B165 the governor's global page: the 24 bytes 18..41 (what was sent is GovWritePayload[18..41], the read fills GovAckPayload[18..41]), an
    //    8 s window, the word on t4, and the page's edited flag let go only when the read-back matches (OK's "Save now?" waits for the verdict)
    CurrentView = RFGOVERNORVIEW_GLOBAL; for (int i = 18; i < 42; ++i) { GovWritePayload[i] = (uint8_t)i; GovAckPayload[i] = (uint8_t)i; }
    reset(); nowMs = 10000; GOVS_GLOBAL_Were_Edited = true;
    CHECK(RfVerifyArm(VK_GOV_CFG, GovCfgAskValues) && asks == 1 && Reading_GOV_Config_Now && GOV_Config_Send_Duration == 8000 && GOV_Global_Start_Time == 10000 && msgs[0].find("govcfg:Sent") == 0 && has(cmds, "vis b3,0") && BlockBankChanges);
    CHECK(RfVerifySet() == 1 && !RfVerifyPending() && !Reading_GOV_Config_Now && has(hides, "govcfg") && texts["t4"] == "Saved, and confirmed by reading it back." && has(cmds, "vis t4,1") && !has(cmds, "vis busy,1") && !GOVS_GLOBAL_Were_Edited && leaves == 1 && sounds.size() == 1 && sounds[0] == "done");
    cmds.clear(); nowMs = 13000; RfVerifyTick(); CHECK(has(cmds, "vis t4,0") && !has(cmds, "vis busy,0"));
    // different: the spool-up's high byte (23 = n17), the throttle type (39 = n28) and an off-page byte (20: counted, no box) - the verdict at the window's end
    reset(); nowMs = 20000; GOVS_GLOBAL_Were_Edited = true; RfVerifyArm(VK_GOV_CFG, GovCfgAskValues); GovAckPayload[23] = 0; GovAckPayload[39] = 9; GovAckPayload[20] = 1;
    CHECK(RfVerifySet() == 2 && RfVerifyPending() && Reading_GOV_Config_Now && GOVS_GLOBAL_Were_Edited && boxes == 0 && hides.empty());
    CHECK(EndDiffer(VK_GOV_CFG) && lastBoxPage == "page RFGovViewGlbl" && lastBox.find("other values for 3 boxes") != std::string::npos && reds.size() == 2 && reds[0] == "n17" && reds[1] == "n28");
    CHECK(GovAckPayload[23] == 23 && GovAckPayload[39] == 39 && GovAckPayload[20] == 20 && has(displays, "govcfg 18-42") && has(edited, "govcfg") && has(hides, "govcfg") && GOVS_GLOBAL_Were_Edited && !RfVerifyPending());
    // B195: on a 16 MB screen the start-up time (20 = n16) and the filters (34-38 = n23..n27) are on the page: they turn red too
    bigScreen = true;
    reset(); nowMs = 21000; GOVS_GLOBAL_Were_Edited = true; RfVerifyArm(VK_GOV_CFG, GovCfgAskValues); GovAckPayload[20] = 1; GovAckPayload[36] = 7; GovAckPayload[39] = 9;
    CHECK(RfVerifySet() == 2 && EndDiffer(VK_GOV_CFG) && reds.size() == 3 && reds[0] == "n16" && reds[1] == "n25" && reds[2] == "n28");
    bigScreen = false;
    // nothing came back: NOT CONFIRMED, Save shown, the edits kept
    reset(); nowMs = 30000; GOVS_GLOBAL_Were_Edited = true; RfVerifyArm(VK_GOV_CFG, GovCfgAskValues);
    CHECK(EndNothing(VK_GOV_CFG) && boxes == 1 && lastBox.find("NOT CONFIRMED") == 0 && has(edited, "govcfg") && has(hides, "govcfg") && GOVS_GLOBAL_Were_Edited && !RfVerifyPending() && displays.empty());
    // another kind's window end is not ours; the page left drops it with nothing said
    reset(); nowMs = 31000; RfVerifyArm(VK_GOV_CFG, GovCfgAskValues); CHECK(!RfVerifyEnd(VK_GOV) && RfVerifyPending());
    CurrentView = ROTORFLIGHTVIEW; CHECK(!RfVerifyEnd(VK_GOV_CFG) && !RfVerifyPending() && boxes == 0); CurrentView = RFGOVERNORVIEW_GLOBAL;
    // 14. B177: the block is asked for again before any verdict - nothing in the first window asks again (2 of 3), then (3 of 3), then NOT CONFIRMED
    CurrentView = RATESVIEW_RF; reset(); nowMs = 40000; RfVerifyArm(VK_RATES, RatesAskValues); CHECK(asks == 1 && RATES_Send_Duration == 4000);
    uint32_t t1 = RATES_Start_Time; nowMs = 44100; Reading_RATES_Now = false;   // (Hide_msg_if_needed lowers the flag before it asks for the verdict)
    CHECK(RfVerifyEnd(VK_RATES) && RfVerifyPending() && asks == 2 && Reading_RATES_Now && RATES_Start_Time != t1 && RATES_Send_Duration == 4000 && boxes == 0 && has(msgs, "rates:Reading back again (2 of 3) ...") && hides.empty());
    nowMs = 48200; Reading_RATES_Now = false; CHECK(RfVerifyEnd(VK_RATES) && RfVerifyPending() && asks == 3 && has(msgs, "rates:Reading back again (3 of 3) ...") && boxes == 0);
    nowMs = 52300; Reading_RATES_Now = false; CHECK(RfVerifyEnd(VK_RATES) && !RfVerifyPending() && asks == 3 && boxes == 1 && lastBox.find("NOT CONFIRMED after 3 read-backs") == 0 && has(edited, "rates") && has(hides, "rates"));
    // the same set in the second window: confirmed there, no third ask
    reset(); nowMs = 60000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 64100; Reading_RATES_Now = false; CHECK(RfVerifyEnd(VK_RATES) && asks == 2);
    CHECK(RfVerifySet() == 1 && !RfVerifyPending() && texts["busy"] == "Saved, and confirmed by reading it back." && leaves == 1 && boxes == 0);
    CHECK(!RfVerifyEnd(VK_RATES) && boxes == 0);   // (the window's end says nothing more)
    // a different set in the first window, the right one in the second: saved
    reset(); nowMs = 70000; RfVerifyArm(VK_RATES, RatesAskValues); Rate_Values[0] = 4; CHECK(RfVerifySet() == 2); nowMs = 74100; Reading_RATES_Now = false; CHECK(RfVerifyEnd(VK_RATES) && asks == 2 && boxes == 0 && Rate_Values[0] == 4);
    Rate_Values[0] = 10; CHECK(RfVerifySet() == 1 && leaves == 1 && boxes == 0);
    // the page left between asks: nothing more said
    reset(); nowMs = 80000; RfVerifyArm(VK_RATES, RatesAskValues); nowMs = 84100; Reading_RATES_Now = false; CHECK(RfVerifyEnd(VK_RATES) && asks == 2); CurrentView = ROTORFLIGHTVIEW; nowMs = 88200; CHECK(!RfVerifyEnd(VK_RATES) && !RfVerifyPending() && boxes == 0); CurrentView = RATESVIEW_RF;
    // the queue refusing the second ask (the pipe went): the verdict comes at once
    reset(); nowMs = 90000; RfVerifyArm(VK_RATES, RatesAskValues); VfAskFn = RefusedAsk; nowMs = 94100; Reading_RATES_Now = false; CHECK(RfVerifyEnd(VK_RATES) && !RfVerifyPending() && boxes == 1 && lastBox.find("NOT CONFIRMED") == 0);
    // the governor's global page: its longer window at every ask
    reset(); CurrentView = RFGOVERNORVIEW_GLOBAL; nowMs = 100000; RfVerifyArm(VK_GOV_CFG, GovCfgAskValues); CHECK(GOV_Config_Send_Duration == 8000); nowMs = 108100; Reading_GOV_Config_Now = false; CHECK(RfVerifyEnd(VK_GOV_CFG) && asks == 2 && GOV_Config_Send_Duration == 8000 && has(msgs, "govcfg:Reading back again (2 of 3) ...")); CurrentView = RATESVIEW_RF;
    // e101 (18 Nov 2026, the twenty-first review): THE SAVE ITSELF HOLDS THE BANK SWITCH (RfSaveHoldsBank; Switches.h asks it at the three places that move the bank)
    Bank = 1; DualRateInUse = 1; CurrentView = PIDVIEW; for (int i = 0; i < MAX_PID_WORDS; ++i) PID_Values[i] = 100 + i;
    reset(); nowMs = 300000; CHECK(!RfSaveHoldsBank());                                              // no save: nothing held
    // a save of what the flight controller already holds: "what was sent" comes back at once (the old block) - held its 1.5 s all the same
    nowMs = 310000; CHECK(RfVerifyArm(VK_PID, PidAskValues) && RfSaveHoldsBank()); nowMs = 310200; CHECK(RfVerifySet() == 1 && !RfVerifyPending() && RfSaveHoldsBank());
    nowMs = 311499; CHECK(RfSaveHoldsBank()); nowMs = 311500; CHECK(!RfSaveHoldsBank()); nowMs = 313999; CHECK(!RfSaveHoldsBank());
    // what was sent has not come back: held past the 1.5 s, to the save's own 4 s - and no longer
    reset(); nowMs = 320000; RfVerifyArm(VK_PID, PidAskValues); PID_Values[0] = 55; CHECK(RfVerifySet() == 2); nowMs = 321600; CHECK(RfSaveHoldsBank()); nowMs = 323999; CHECK(RfSaveHoldsBank());
    nowMs = 324000; CHECK(!RfSaveHoldsBank()); nowMs = 324001; CHECK(!RfSaveHoldsBank()); PID_Values[0] = 100;
    // ... and it comes back at 2 s: free then
    reset(); nowMs = 330000; RfVerifyArm(VK_PID, PidAskValues); PID_Values[0] = 55; CHECK(RfVerifySet() == 2); nowMs = 332000; CHECK(RfSaveHoldsBank()); PID_Values[0] = 100; CHECK(RfVerifySet() == 1 && !RfSaveHoldsBank());
    // the page left (the menu, Help, another page): nothing is compared there - held to the save's 4 s wherever he is; the read's flag down changes nothing
    reset(); nowMs = 340000; RfVerifyArm(VK_PID, PidAskValues); CurrentView = ROTORFLIGHTVIEW; Reading_PIDS_Now = false; nowMs = 342900; RfVerifyPending(); CHECK(RfSaveHoldsBank()); BlockBankChanges = false; CHECK(RfSaveHoldsBank());
    nowMs = 343999; CHECK(RfSaveHoldsBank()); nowMs = 344000; RfVerifyPending(); CHECK(!RfSaveHoldsBank() && VfKind == VK_NONE); CurrentView = PIDVIEW;
    // left, and what was sent comes back off its page (its own read still open): free after the 1.5 s
    reset(); nowMs = 350000; RfVerifyArm(VK_PID, PidAskValues); CurrentView = ROTORFLIGHTVIEW; nowMs = 350400; CHECK(RfVerifySet() == 1 && RfSaveHoldsBank()); nowMs = 351500; CHECK(!RfSaveHoldsBank()); CurrentView = PIDVIEW;
    // a second save begins its own time
    reset(); nowMs = 360000; RfVerifyArm(VK_PID, PidAskValues); RfVerifySet(); nowMs = 361400; RfVerifyArm(VK_PID, PidAskValues); RfVerifySet(); nowMs = 361600; CHECK(RfSaveHoldsBank()); nowMs = 362900; CHECK(!RfSaveHoldsBank());
    // a save that is not read back (no pipe) holds nothing; an earlier save's hold is not cut short by it
    reset(); nowMs = 370000; PipeState = 1; CHECK(!RfVerifyArm(VK_PID, PidAskValues) && !RfSaveHoldsBank()); PipeState = 2;
    reset(); nowMs = 380000; RfVerifyArm(VK_PID, PidAskValues); PID_Values[0] = 55; RfVerifySet(); nowMs = 380500; PipeState = 1; RfVerifyArm(VK_PID, PidAskValues); PipeState = 2; CHECK(RfSaveHoldsBank()); nowMs = 384000; CHECK(!RfSaveHoldsBank()); PID_Values[0] = 100;
    // NOT the Governor global page: nothing of it is a bank's
    reset(); CurrentView = RFGOVERNORVIEW_GLOBAL; nowMs = 390000; CHECK(RfVerifyArm(VK_GOV_CFG, GovCfgAskValues) && !RfSaveHoldsBank()); nowMs = 390100; CHECK(!RfSaveHoldsBank()); Reading_GOV_Config_Now = false;
    // (e101b) a Governor global save does not take a bank page's hold away - inside the 1.5 s, and after them with nothing come back
    reset(); CurrentView = PIDVIEW; nowMs = 400000; RfVerifyArm(VK_PID, PidAskValues); RfVerifySet(); CurrentView = RFGOVERNORVIEW_GLOBAL; nowMs = 400800; CHECK(RfVerifyArm(VK_GOV_CFG, GovCfgAskValues) && RfSaveHoldsBank()); nowMs = 401499; CHECK(RfSaveHoldsBank()); nowMs = 401500; CHECK(!RfSaveHoldsBank()); Reading_GOV_Config_Now = false;
    reset(); CurrentView = PIDVIEW; nowMs = 410000; RfVerifyArm(VK_PID, PidAskValues); PID_Values[0] = 55; RfVerifySet(); PID_Values[0] = 100; CurrentView = RFGOVERNORVIEW_GLOBAL; nowMs = 412000; RfVerifyArm(VK_GOV_CFG, GovCfgAskValues); CHECK(RfSaveHoldsBank()); nowMs = 413999; CHECK(RfSaveHoldsBank()); nowMs = 414000; CHECK(!RfSaveHoldsBank()); Reading_GOV_Config_Now = false;
    // (e101c; review 23, B) nor does the Governor global save's OWN MATCHING ANSWER: the bank page's write has not landed - held until its 4 s end
    reset(); CurrentView = PIDVIEW; nowMs = 420000; RfVerifyArm(VK_PID, PidAskValues); PID_Values[0] = 55; RfVerifySet(); PID_Values[0] = 100; CurrentView = RFGOVERNORVIEW_GLOBAL; Reading_PIDS_Now = false; nowMs = 422000; RfVerifyArm(VK_GOV_CFG, GovCfgAskValues); CHECK(RfSaveHoldsBank()); nowMs = 422300; CHECK(RfVerifySet() == 1 && !RfVerifyPending() && RfSaveHoldsBank()); nowMs = 423999; CHECK(RfSaveHoldsBank()); nowMs = 424000; CHECK(!RfSaveHoldsBank()); Reading_GOV_Config_Now = false;
    // ... while a bank page's own matching answer does end its hold after the 1.5 s (the row that keeps the guard from being "never")
    reset(); CurrentView = PIDVIEW; nowMs = 430000; RfVerifyArm(VK_PID, PidAskValues); nowMs = 430400; CHECK(RfVerifySet() == 1 && RfSaveHoldsBank()); nowMs = 431500; CHECK(!RfSaveHoldsBank());
    // the clock's wrap: a save 1 s before it is held across it, and let go
    reset(); CurrentView = PIDVIEW; nowMs = 0xFFFFFC18u; RfVerifyArm(VK_PID, PidAskValues); PID_Values[0] = 55; RfVerifySet(); nowMs = 500; CHECK(RfSaveHoldsBank()); nowMs = 3001; CHECK(!RfSaveHoldsBank()); PID_Values[0] = 100;
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
