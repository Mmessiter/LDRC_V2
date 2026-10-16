#!/usr/bin/env python3
"""Host tests of the bug-list fixes of 13 Oct 2026 (V2 B94/B95/B96): the functions that were changed, lifted out of
main.cpp and the headers by name and compiled on the Mac over fakes of the screen, the switches, the card and the clock.
Three programs (flight logic; the power button; logs and files) and a set of checks on the source text for the fixes
whose functions are too entangled to lift (the calibration flow, the model loader, the help return).
   python3 dev/test_bugfixes/test_bugfixes.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, 'TransmitterCode')
SRC = {}
def src(rel):
    if rel not in SRC: SRC[rel] = open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()
    return SRC[rel]
def lift(rel, head):
    """The function whose first line starts with `head` (column 0, Allman style): from there to the next line that is just '}'."""
    lines = src(rel).split('\n')
    for i, l in enumerate(lines):
        if l.startswith(head):
            for j in range(i + 1, len(lines)):
                if lines[j] == '}':
                    return '\n'.join(lines[i:j + 1]) + '\n'
            break
    raise SystemExit('cannot lift %s from %s' % (head, rel))

COMMON = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cmath>
#include <cctype>
#include <string>
#include <map>
#include <vector>
#define FASTRUN
#define FLASHMEM
#define PROGMEM
#define DMAMEM
#define constrain(a, l, h) ((a) < (l) ? (l) : ((a) > (h) ? (h) : (a)))
#define min(a, b) ((a) < (b) ? (a) : (b))
#define max(a, b) ((a) > (b) ? (a) : (b))
static long map(long x, long in_min, long in_max, long out_min, long out_max) { return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min; }
struct CrumbGuard { CrumbGuard(int) {} };
#define CRUMB_PASTE(a, b) a##b
#define CRUMB(c) CrumbGuard CRUMB_PASTE(crumbGuard_, __LINE__)(c)
enum { CRUMB_BANK = 1, CRUMB_MOTORTIMER, CRUMB_POWERBUTTON, CRUMB_MAXCURRENT, CRUMB_LOG, CRUMB_SWITCHES };
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static std::map<std::string, std::string> texts; static std::map<std::string, long> values; static std::vector<std::string> cmds; static std::vector<int> sounds;
static int boxes = 0; static std::string lastBox; static bool confirmAnswer = true; static int saves = 0;
static void SendText(char *n, char *t) { texts[n] = t; }
static void SendText(const char *n, const char *t) { texts[n] = t; }
static void SendValue(char *n, int v) { values[n] = v; }
static uint32_t GetValue(char *n) { return values.count(n) ? (uint32_t) values[n] : 0; }
static uint16_t GetText(char *n, char *out, uint16_t maxlen) { const std::string s = texts.count(n) ? texts[n] : ""; strncpy(out, s.c_str(), maxlen - 1); out[maxlen - 1] = 0; return (uint16_t) strlen(out); }
static void SendCommand(char *c) { cmds.push_back(c); }
static void PlaySound(int s) { sounds.push_back(s); }
static void MsgBox(char *, char *m) { ++boxes; lastBox = m; }
static bool GetConfirmation(char *, char *p) { lastBox = p; return confirmAnswer; }
#ifndef OWN_SAVE_ONE_MODEL
static void SaveOneModel(uint32_t) { ++saves; }
#endif
static int countCmd(const char *c) { int n = 0; for (auto &s : cmds) if (s == c) ++n; return n; }
static int countSound(int s) { int n = 0; for (int x : sounds) if (x == s) ++n; return n; }
static char *Str(char *b, int v, int) { snprintf(b, 8, "%d", v); return b; }
'''

# ------------------------------------------------------------------------------------------------------------ program A: flight
A_DEFS = r'''
#define CHANNELSUSED 16
#define BANKS_USED 4
#define MAXMIXES 32
#define MAXMACROS 8
#define BYTESPERMACRO 6
#define MAXDUALRATE 200
#define MINMICROS 500
#define MAXMICROS 2500
#define NORMAL 0
#define SCANWAVEBAND 3
#define LISTENMODE 6
#define FRONTVIEW 0
#define STICKSVIEW 1
#define MIXESVIEW 3
#define SCANVIEW 4
#define CALIBRATEVIEW 6
#define TXSETUPVIEW 7
#define SUBTRIMVIEW 8
#define SWITCHES_VIEW 12
#define INPUTS_VIEW 16
#define FAILSAFE_VIEW 17
#define REVERSEVIEW 21
#define BUDDYCHVIEW 27
#define RXSETUPVIEW1 28
#define DUALRATESVIEW 29
#define RXSETUPVIEW 31
#define SLOWSERVOVIEW 33
#define RATESVIEW_RF 46
#define ROTORFLIGHTVIEW 47
#define RATESADVANCEDVIEW 48
#define EASYVIEW 81
#define CLICKZERO 0
#define ONEMINUTE 2
#define TWOMINUTES 3
#define THREEMINUTES 4
#define FOURMINUTES 5
#define FIVEMINUTES 6
#define SIXMINUTES 7
#define SEVENMINUTES 8
#define EIGHTMINUTES 9
#define NINEMINUTES 10
#define TENMINUTES 11
#define BEEPCOMPLETE 17
#define WHAHWHAHMSG 25
#define MOTORON 31
#define MOTOROFF 32
#define STORAGECHARGE 33
#define PLSTURNOFF 37
#define TEN 62
#define NINE 63
#define EIGHT 64
#define SEVEN 65
#define SIX 66
#define FIVE 67
#define FOUR 68
#define THREE 69
#define TWO 70
#define ONE 71
#define RATE1 80
#define RATE2 81
#define RATE3 82
#define TRIM1A 34
#define TRIM1B 35
#define TRIM2A 36
#define TRIM2B 37
#define TRIM3A 38
#define TRIM3B 39
#define TRIM4A 40
#define TRIM4B 41
#define M_MIX_OUTPUTS 0
#define M_Bank 1
#define M_MasterChannel 2
#define M_SlaveChannel 3
#define M_Reversed 4
#define M_Percent 5
#define M_MIX_INPUTS 6
#define M_R2 7
#define M_ONEDIRECTION 8
#define M_OFFSET 9
#define MIXINPUT 0
#define MIXOUTPUT 1
#define BANK 2
#define MASTERCHANNEL 3
#define SLAVECHANNEL 4
#define ONEDIRECTION 5
#define REVERSED 6
#define OFFSET 7
#define PERCENT 8
#define MACROTRIGGERCHANNEL 0
#define MACROSTARTTIME 1
#define MACRODURATION 2
#define MACROMOVECHANNEL 3
#define MACROMOVETOPOSITION 4
#define MAXTEXTIN 300
static uint8_t Mixes[MAXMIXES + 1][17];
static int Trims[BANKS_USED + 1][CHANNELSUSED + 1];
static char TextIn[MAXTEXTIN + 2];
static uint8_t ServoSpeed[BANKS_USED + 1][CHANNELSUSED + 1];
static uint16_t SendBuffer[17], InputsBuffer[17], PreMixBuffer[17], ChannelMax[17], ChannelCentre[17], ChannelMin[17];
static uint8_t SubTrims[17];
static uint8_t Bank = 1, PreviousBank = 1, DualRateInUse = 1, PreviousDualRateInUse = 1, SticksMode = 1, CurrentMode = NORMAL, MixNumber = 1;
static char ChannelNames[CHANNELSUSED][11] = {{"Aileron"}, {"Elevator"}, {"Throttle"}, {"Rudder"}, {"Gear"}, {"AUX1"}, {"AUX2"}, {"AUX3"}, {"AUX4"}, {"AUX5"}, {"AUX6"}, {"AUX7"}, {"AUX8"}, {"AUX9"}, {"AUX10"}, {"AUX11"}};
static int CurrentView = FRONTVIEW;
static uint8_t TrimNumber[8] = {TRIM1A, TRIM1B, TRIM2A, TRIM2B, TRIM3A, TRIM3B, TRIM4A, TRIM4B};
static uint32_t MotorStartTime = 0, LastSeconds = 0, Secs = 0, MotorOnSeconds = 0, PausedSecs = 0, Mins = 0, Hours = 0, ModelNumber = 1, RotorRPM = 0, LastShowTime = 0, LastTimeRead = 0;
static bool LostContactFlag = false, BoundFlag = false, ModelMatched = false, Switch[8], SwitchReversed[8], BuddyHasAllSwitches = true, BuddyPupilOnWireless = false, LedWasGreen = false, LedWasRed = true;
static uint8_t Autoswitch = 0, SafetySwitch = 0, DualRatesSwitch = 0, FrontSwitchPos[4], InPutStick[17] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15}, ChannelOutPut[17] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15}, InputTrim[4] = {0, 1, 2, 3};
static uint16_t FrontSwitchRaw[4], TrimMultiplier = 5, ReversedChannelBITS = 0, ServoCentrePulse[11], ServoFrequency[11], SFV = 0, TimerStartTime = 300, ScreenData[50], Max_Safe_Amps = 0;
static bool FailSafeChannel[17], UseLog = false, TrimClicks = false, SpeakingClock = true, ClockSpoken = false, ClockSpoken1 = false, AnnounceBanks = false, CopyTrimsToAll = false, UseMotorKill = true, MotorEnabled = false, SendNoData = false, MotorWasEnabled = false, SafetyON = false, SafetyWasOn = false, TimerDownwards = false, TimesUp = false, UseMacros = false, BlockBankChanges = false, LinkRatesToBanks = false, Armed = false, BindingEnabled = false;
static short int RxVoltageCorrection = 0;
static float StopFlyingVoltsPerCell = 0;
static uint8_t MotorChannel = 2, MotorChannelZero = 30, Drate1 = 100, Drate2 = 75, Drate3 = 50, DualRateChannels[8] = {1, 2, 4, 0, 0, 0, 0, 0}, DualRateRate[5], DualRateValue = 100, CountDownIndex = 0, MacrosBuffer[MAXMACROS][BYTESPERMACRO], RotorFlight_V = 0, ModalWaits = 0;
static bool Reading_PIDS_Now = false, Reading_PIDS_Advanced_Now = false, Reading_RATES_Now = false, Reading_RATES_Advanced_Now = false, Reading_GOV_Now = false, Reading_GOV_Config_Now = false;
static char WarnNow[] = "vis Warning,1", WarnOff[] = "vis Warning,0", pTrimView[] = "page TrimView", pRXSetupView[] = "page RXSetupView", pTXSetupView[] = "page TXSetupView", pFhssView[] = "page FhssView";
static uint32_t now = 0; static uint32_t millis() { return now; }
static int motorChanges = 0, safetyChanges = 0, frontViews = 0, delays = 0;
static void ReadTheSwitchesAndTrims() {}
static void LogNewRateInUse() {} static void ShowRatesBank() {} static void ShowRatesAdvancedBank() {} static void ShowRFRate() {} static void EasyBankChanged() {}
static void ReadBuddySwitch() {} static void ReadBankSwitch() {} static void ReadChannelSwitches9to12() {} static void BankHasChanged() {}
static void SafetySwitchChanged() { ++safetyChanges; }
static void LogTimer(int) {} static void LogRPM(uint32_t) {} static void LogMotor(int) {}
static void ForceDataRedisplay() {} static void UpdateTrimView() {} static void FixCHNames() {} static void DualRatesRefresh() {} static void UpdateModelsNameEveryWhere() {}
static void DrawFhssBox() {} static void DoScanInit() {} static void BlueLedOn() {} static void ClearText() {}
static void GotoFrontView() { ++frontViews; CurrentView = FRONTVIEW; }
static void DelayWithDog(uint32_t) { ++delays; }
static bool safetyOff = false, safetyDefined = false, justNow = false, radiosOff = false;
static bool SafetyIsOff() { return safetyOff; } static bool SafetyIsDefined() { return safetyDefined; } static bool ModelJustNow() { return justNow; } static bool RadiosMustBeOff() { return radiosOff; }
// prototypes of what is lifted
void RerouteOutputs(); uint8_t SourceOfOutput(uint8_t out); int CheckRange(int v, int min, int max); void UpdateButtonLabels(); void CheckMotorOff(); void GetBank();
static void StickEndsShow() {} // (B111: the Channels page's switch, tested in dev/test_channel_us)
uint8_t GetSwitchPosition(uint8_t ThisSwitchNumber); void ReadAutoAndMotorSwitch(); void ReadSafetySwitch(); void ReadDualRateSwitch();
void ShowMotorTimer(); void ShowMotor(); void MotorEnabledHasChanged(); void TrimsToSubtrim(); int GetTrimAmount(uint8_t InputChannel); void ResetAllTrims();
void MixInputs(); void ReadDualRatesValues(); void CheckServoSpeeds(); void CheckServoType(); void ReadMixValues(); void ReceiveLotsofData();
void ExitMacrosView(); void ReadRXOptionsView(); void StartWifiScan(); uint8_t ScreenStatusNow(); void swap(uint8_t *a, uint8_t *b);
'''
A_LIFT = [
    ('src/main.cpp', 'void RerouteOutputs()'), ('src/main.cpp', 'uint8_t SourceOfOutput(uint8_t out)'), ('src/main.cpp', 'int CheckRange(int v, int min, int max)'),
    ('src/main.cpp', 'void UpdateButtonLabels()'), ('src/main.cpp', 'void CheckMotorOff()'), ('src/main.cpp', 'void GetBank()'),
    ('include/Utilities.h', 'void swap(uint8_t *a, uint8_t *b)'),
    ('include/Switches.h', 'uint8_t GetSwitchPosition(uint8_t ThisSwitchNumber)'), ('include/Switches.h', 'void ReadAutoAndMotorSwitch()'), ('include/Switches.h', 'void ReadSafetySwitch()'), ('include/Switches.h', 'void ReadDualRateSwitch()'),
    ('include/Motor_sign.h', 'FASTRUN void ShowMotorTimer()'), ('include/Motor_sign.h', 'void ShowMotor()'), ('include/Motor_sign.h', 'void MotorEnabledHasChanged()'),
    ('include/Trims.h', 'void TrimsToSubtrim()'), ('include/Trims.h', 'int GetTrimAmount(uint8_t InputChannel)'), ('include/Trims.h', 'void ResetAllTrims()'),
    ('include/Mixes.h', 'FASTRUN void MixInputs()'), ('include/DualRates.h', 'void ReadDualRatesValues()'),
    ('include/SDcard.h', 'void CheckServoSpeeds()'), ('include/SDcard.h', 'void CheckServoType()'),
    ('include/MenuOptions.h', 'void ReadMixValues()'), ('include/MenuOptions.h', 'void ReceiveLotsofData()'), ('include/MenuOptions.h', 'static uint8_t MacroValue('),
    ('include/MenuOptions.h', 'void ExitMacrosView()'), ('include/MenuOptions.h', 'void ReadRXOptionsView()'), ('include/MenuOptions.h', 'void StartWifiScan()'),
    ('include/FlightGuard.h', 'uint8_t ScreenStatusNow()'),
]
A_MAIN = r'''
static void switchAt(uint8_t sw, int pos) { // a top switch 1-4 (pins {7,6} {5,4} {1,0} {3,2}) put in position 1, 2 or 3 (not reversed)
    static const uint8_t Pin[4][2] = {{7, 6}, {5, 4}, {1, 0}, {3, 2}};
    Switch[Pin[sw - 1][0]] = pos == 3; Switch[Pin[sw - 1][1]] = pos == 1;
}
static void resetAll() { texts.clear(); values.clear(); cmds.clear(); sounds.clear(); boxes = 0; saves = 0; memset(Switch, 0, sizeof Switch); memset(SwitchReversed, 0, sizeof SwitchReversed); memset(FrontSwitchPos, 0, sizeof FrontSwitchPos); for (int i = 0; i < 17; ++i) { ChannelOutPut[i] = i; InPutStick[i] = i; ChannelMin[i] = 1000; ChannelCentre[i] = 1500; ChannelMax[i] = 2000; } for (int i = 0; i < 4; ++i) InputTrim[i] = i; }
int main() {
    // ---------------------------------------------------------------- B31: channel i goes OUT to output ChannelOutPut[i]
    resetAll();
    for (int i = 0; i < 16; ++i) PreMixBuffer[i] = 1000 + i * 10;
    RerouteOutputs(); bool same = true; for (int i = 0; i < 16; ++i) if (SendBuffer[i] != 1000 + i * 10) same = false; CHECK(same);
    ChannelOutPut[0] = 1; ChannelOutPut[1] = 2; ChannelOutPut[2] = 0;   // a ring of three: 1 -> 2 -> 3 -> 1
    for (int i = 0; i < 16; ++i) PreMixBuffer[i] = 1000 + i * 10;
    RerouteOutputs(); CHECK(SendBuffer[1] == 1000 && SendBuffer[2] == 1010 && SendBuffer[0] == 1020 && SendBuffer[3] == 1030);
    CHECK(SourceOfOutput(1) == 0 && SourceOfOutput(2) == 1 && SourceOfOutput(0) == 2 && SourceOfOutput(5) == 5);
    CurrentView = REVERSEVIEW; UpdateButtonLabels(); CHECK(texts["ch2"] == "Aileron" && texts["ch3"] == "Elevator" && texts["ch1"] == "Throttle" && texts["ch4"] == "Rudder");   // Reverse names the channel routed there
    CurrentView = INPUTS_VIEW; UpdateButtonLabels(); CHECK(texts["ch2"] == "Elevator" && values["n4"] == 2 && values["n5"] == 3 && values["n6"] == 1);                  // Inputs: the row is the channel, Out says where it goes
    resetAll(); ChannelOutPut[0] = 1; ChannelOutPut[1] = 0;   // a swap: the same either way round
    for (int i = 0; i < 16; ++i) PreMixBuffer[i] = 1000 + i * 10;
    RerouteOutputs(); CHECK(SendBuffer[0] == 1010 && SendBuffer[1] == 1000);
    resetAll(); ChannelOutPut[3] = 200;   // a corrupt entry: the channel keeps its own output, nothing written outside
    for (int i = 0; i < 16; ++i) PreMixBuffer[i] = 1000 + i * 10;
    RerouteOutputs(); CHECK(SendBuffer[3] == 1030 && SourceOfOutput(3) == 3);
    // ---------------------------------------------------------------- B12: the start-up motor check reads the switches as in flight
    resetAll(); UseMotorKill = true; Autoswitch = 3; SafetySwitch = 0;
    switchAt(3, 3); CheckMotorOff(); CHECK(!MotorEnabled && !MotorWasEnabled);     // position 3 = OFF
    switchAt(3, 1); CheckMotorOff(); CHECK(MotorEnabled && MotorWasEnabled);       // position 1 = ON
    switchAt(3, 2); CheckMotorOff(); CHECK(MotorEnabled);                          // middle = ON (bank 4)
    SwitchReversed[2] = true; switchAt(3, 1); CheckMotorOff(); CHECK(!MotorEnabled); // reversed: what was 1 is 3
    SwitchReversed[2] = true; switchAt(3, 3); CheckMotorOff(); CHECK(MotorEnabled);
    SwitchReversed[2] = false; SafetySwitch = 4; switchAt(3, 1);
    switchAt(4, 3); CheckMotorOff(); CHECK(MotorEnabled && !SafetyON);             // safety switch at 3 = safety off
    switchAt(4, 1); CheckMotorOff(); CHECK(!MotorEnabled && SafetyON);             // any other position = safety ON: the motor cannot be on
    switchAt(4, 2); CheckMotorOff(); CHECK(!MotorEnabled && SafetyON);
    // the same answers as the flight readers give for the same switches
    for (int a = 1; a <= 3; ++a) for (int s = 1; s <= 3; ++s) for (int r = 0; r < 2; ++r) {
        SwitchReversed[2] = r; switchAt(3, a); switchAt(4, s);
        CheckMotorOff(); const bool m1 = MotorEnabled, s1 = SafetyON;
        MotorEnabled = !m1; SafetyON = !s1; ReadSafetySwitch(); ReadAutoAndMotorSwitch(); if (SafetyON) MotorEnabled = false;
        CHECK(MotorEnabled == m1 && SafetyON == s1);
    }
    // a front switch (5-8) as the motor switch: from its calibrated analogue reading
    resetAll(); Autoswitch = 5; SafetySwitch = 0; ChannelMin[4] = 100; ChannelMax[4] = 1000;
    FrontSwitchRaw[0] = 950; CheckMotorOff(); CHECK(!MotorEnabled);   // high = position 3 = OFF
    FrontSwitchRaw[0] = 150; memset(FrontSwitchPos, 0, 4); CheckMotorOff(); CHECK(MotorEnabled);
    ChannelMin[4] = 500; ChannelMax[4] = 600; memset(FrontSwitchPos, 0, 4); CheckMotorOff(); CHECK(!MotorEnabled);   // not calibrated: no position, the motor is not ON
    UseMotorKill = false; MotorEnabled = true; CheckMotorOff(); CHECK(MotorEnabled);   // no motor kill: the check does nothing
    // ---------------------------------------------------------------- B10: the Rates page's "Bank N will use rate X"
    resetAll(); UseMotorKill = true; Bank = 1; DualRatesSwitch = 1; RotorFlight_V = 0; LinkRatesToBanks = false; memset(DualRateRate, 0, sizeof DualRateRate);
    switchAt(1, 2); ReadDualRateSwitch(); CHECK(DualRateInUse == 2 && DualRateValue == Drate2);         // the switch
    DualRateRate[0] = 3; ReadDualRateSwitch(); CHECK(DualRateInUse == 3 && DualRateValue == Drate3);    // the bank's own choice beats the switch
    Bank = 2; ReadDualRateSwitch(); CHECK(DualRateInUse == 2);                                          // another bank: back to the switch
    Bank = 1; DualRateRate[0] = 200; ReadDualRateSwitch(); CHECK(DualRateInUse == 2);                   // a corrupt choice is ignored (it is an index)
    DualRateRate[0] = 4; ReadDualRateSwitch(); CHECK(DualRateInUse == 2);
    DualRatesSwitch = 0; DualRateRate[0] = 0; ReadDualRateSwitch(); CHECK(DualRateInUse == 4 && DualRateValue == 100);   // no switch, no choice: 100 %
    DualRateRate[0] = 1; ReadDualRateSwitch(); CHECK(DualRateInUse == 1 && DualRateValue == Drate1);   // no switch, a choice
    RotorFlight_V = 2; LinkRatesToBanks = true; Bank = 3; ReadDualRateSwitch(); CHECK(DualRateInUse == 3 && DualRateValue == 100);   // linked to the banks: the bank
    RotorFlight_V = 0; LinkRatesToBanks = false; Bank = 1;
    // B34 the page's channels 9-16, B10 the choice box: never out of range
    memset(ScreenData, 0, sizeof ScreenData); ScreenData[0] = 100; ScreenData[1] = 75; ScreenData[2] = 50; ScreenData[3] = 1; ScreenData[10] = 16; ScreenData[11] = 2;
    ReadDualRatesValues(); CHECK(DualRateChannels[7] == 16 && DualRateChannels[0] == 1 && DualRateRate[0] == 2);
    ScreenData[10] = 17; DualRateChannels[7] = 3; ReadDualRatesValues(); CHECK(DualRateChannels[7] == 3);   // 17 = not updated yet: nothing read
    ScreenData[10] = 9; ScreenData[11] = 200; ReadDualRatesValues(); CHECK(DualRateChannels[7] == 9 && DualRateRate[0] == 0);   // a corrupt choice = the switch
    ScreenData[11] = 3; ReadDualRatesValues(); CHECK(DualRateRate[0] == 3);
    // ---------------------------------------------------------------- B27: the countdown stops at zero and says so, once
    resetAll(); TimerDownwards = true; TimerStartTime = 300; MotorEnabled = true; LostContactFlag = false; MotorStartTime = 0; PausedSecs = 0; TimesUp = false; CountDownIndex = 0; LastSeconds = 99; CurrentView = FRONTVIEW; SpeakingClock = false;
    now = 10000; ShowMotorTimer(); CHECK(Mins == 4 && Secs == 50 && Hours == 0 && countSound(STORAGECHARGE) == 0 && !TimesUp);
    now = 295000; ShowMotorTimer(); CHECK(Mins == 0 && Secs == 5 && countSound(SIX) == 0 && countSound(TEN) == 1 && !TimesUp);   // the spoken countdown starts
    now = 300000; ShowMotorTimer(); CHECK(Secs == 0 && Mins == 0 && TimesUp && countSound(STORAGECHARGE) == 1);
    now = 301000; ShowMotorTimer(); now = 400000; ShowMotorTimer(); CHECK(countSound(STORAGECHARGE) == 1 && Secs == 0);   // said once, and never past zero
    TimesUp = false; LastSeconds = 99; sounds.clear(); SpeakingClock = true; now = 300000; ShowMotorTimer(); CHECK(TimesUp && countSound(STORAGECHARGE) == 1);   // with the clock speaking too
    TimesUp = false; sounds.clear(); TimerStartTime = 0; LastSeconds = 99; now = 3000; ShowMotorTimer(); CHECK(!TimesUp && countSound(STORAGECHARGE) == 0 && Secs == 3);   // no minutes set: it counts up
    now = 65000; ShowMotorTimer(); CHECK(Mins == 1 && Secs == 5 && !TimesUp);
    TimerDownwards = false; TimerStartTime = 300; LastSeconds = 99; now = 65000; ShowMotorTimer(); CHECK(Mins == 1 && Secs == 5 && !TimesUp);   // counting up
    // ---------------------------------------------------------------- B09: Move to subtrim applies the stick mode 2 swap, as the trims are flown
    resetAll(); confirmAnswer = true; SticksMode = 2; Bank = 1; TrimMultiplier = 5;
    for (int b = 0; b < 5; ++b) for (int c = 0; c < 17; ++c) Trims[b][c] = 80;
    for (int c = 0; c < 17; ++c) SubTrims[c] = 127;
    Trims[1][1] = 90; Trims[1][2] = 70;   // the trim that flies channel 2 (throttle) is slot 1 in mode 2, and channel 1's is slot 2
    const int flown1 = GetTrimAmount(InPutStick[1]) + (SubTrims[1] - 127) * 5, flown2 = GetTrimAmount(InPutStick[2]) + (SubTrims[2] - 127) * 5;
    TrimsToSubtrim();
    CHECK(SubTrims[2] == 137 && SubTrims[1] == 117 && SubTrims[0] == 127 && SubTrims[3] == 127);
    CHECK(GetTrimAmount(InPutStick[1]) + (SubTrims[1] - 127) * 5 == flown1 && GetTrimAmount(InPutStick[2]) + (SubTrims[2] - 127) * 5 == flown2);   // the servos do not move
    bool centred = true; for (int b = 1; b < 5; ++b) for (int c = 0; c < 4; ++c) if (Trims[b][c] != 80) centred = false; CHECK(centred && saves == 1);
    SticksMode = 1; for (int c = 0; c < 17; ++c) SubTrims[c] = 127; Trims[1][1] = 90; Trims[1][2] = 70;
    TrimsToSubtrim(); CHECK(SubTrims[1] == 137 && SubTrims[2] == 117);   // mode 1: straight across
    confirmAnswer = false; Trims[1][1] = 90; TrimsToSubtrim(); CHECK(SubTrims[1] == 137 && Trims[1][1] == 90);   // cancelled: nothing moves
    // B38: the trim lever map follows the stick mode
    SticksMode = 2; ResetAllTrims(); CHECK(TrimNumber[2] == TRIM3A && TrimNumber[4] == TRIM2A);
    SticksMode = 1; ResetAllTrims(); CHECK(TrimNumber[2] == TRIM2A && TrimNumber[4] == TRIM3A);
    // ---------------------------------------------------------------- B11 / B32: the Mixes page's channels and offset
    resetAll(); MixNumber = 1; memset(Mixes, 0, sizeof Mixes); memset(ScreenData, 0, sizeof ScreenData);
    ScreenData[0] = 1; ScreenData[3] = 17; ScreenData[4] = 0; ScreenData[7] = (uint16_t)(int16_t)-50; ScreenData[8] = 100;
    ReadMixValues(); CHECK(Mixes[1][M_MasterChannel] == 16 && Mixes[1][M_SlaveChannel] == 1 && Mixes[1][M_OFFSET] == 77 && Mixes[1][M_Percent] == 100);
    ScreenData[7] = (uint16_t)(int16_t)-150; ReadMixValues(); CHECK(Mixes[1][M_OFFSET] == 27);    // -100 at most
    ScreenData[7] = 150; ReadMixValues(); CHECK(Mixes[1][M_OFFSET] == 227);                       // +100 at most
    ScreenData[7] = 0; ReadMixValues(); CHECK(Mixes[1][M_OFFSET] == 127);
    // ReceiveLotsofData: the Mixes page's nine fields, the offset negative
    CurrentView = MIXESVIEW; memset(TextIn, 0, sizeof TextIn);
    { const int32_t v[9] = {1, 1, 0, 2, 3, 0, 0, -40, 80}; for (int f = 0; f < 9; ++f) memcpy(TextIn + (f + 1) * 4, &v[f], 4); const uint32_t end = 0xFFFFFFFF; memcpy(TextIn + 40, &end, 4); }
    ReceiveLotsofData(); CHECK(ScreenData[7] == (uint16_t)(int16_t)-40 && ScreenData[8] == 80 && Mixes[1][M_OFFSET] == 87 && Mixes[1][M_Percent] == 80 && Mixes[1][M_MasterChannel] == 2 && Mixes[1][M_SlaveChannel] == 3);
    CurrentView = DUALRATESVIEW; memset(ScreenData, 0, sizeof ScreenData); ReceiveLotsofData(); CHECK(ScreenData[7] == 0 && ScreenData[8] == 0);   // on any other page a negative still ends the read
    // the mixer never writes outside the channel memory
    CurrentView = FRONTVIEW; memset(Mixes, 0, sizeof Mixes); Bank = 1;
    for (int c = 0; c < 17; ++c) { InputsBuffer[c] = 1500; ChannelMin[c] = 1000; ChannelCentre[c] = 1500; ChannelMax[c] = 2000; }
    Mixes[1][M_MIX_INPUTS] = 1; Mixes[1][M_Bank] = 0; Mixes[1][M_MasterChannel] = 1; Mixes[1][M_SlaveChannel] = 17; Mixes[1][M_Percent] = 100; Mixes[1][M_OFFSET] = 127;
    InputsBuffer[0] = 2000; MixInputs(); CHECK(InputsBuffer[16] == 1500);   // slave 17 (index 16): nothing written
    Mixes[1][M_SlaveChannel] = 0; MixInputs(); CHECK(InputsBuffer[0] == 2000);  // slave 0 (index -1): nothing written
    Mixes[1][M_SlaveChannel] = 2; MixInputs(); CHECK(InputsBuffer[1] == 2000);  // a real mix still mixes (100 % of a full stick)
    // ---------------------------------------------------------------- B33: macro values kept within their ranges
    resetAll(); memset(MacrosBuffer, 7, sizeof MacrosBuffer);
    values["Mno"] = 1; values["Tch"] = 20; values["Mch"] = 3; values["Pos"] = 250; values["Del"] = 65535; values["Dur"] = 300;
    ExitMacrosView(); CHECK(MacrosBuffer[0][MACROTRIGGERCHANNEL] == 16 && MacrosBuffer[0][MACROMOVECHANNEL] == 3 && MacrosBuffer[0][MACROMOVETOPOSITION] == 180 && MacrosBuffer[0][MACROSTARTTIME] == 7 && MacrosBuffer[0][MACRODURATION] == 255 && saves == 1 && UseMacros);
    values["Mno"] = 0; saves = 0; ExitMacrosView(); CHECK(saves == 0);   // no macro number: nothing written
    // ---------------------------------------------------------------- B35 / B51: servo speeds and types
    for (int b = 0; b < 5; ++b) for (int c = 0; c < 17; ++c) ServoSpeed[b][c] = 60;
    ServoSpeed[1][3] = 0; ServoSpeed[2][5] = 150; CheckServoSpeeds();
    { int reset = 0, kept = 0; for (int b = 0; b < 5; ++b) for (int c = 0; c < 17; ++c) { if (ServoSpeed[b][c] == 100) ++reset; if (ServoSpeed[b][c] == 60) ++kept; } CHECK(reset == 2 && kept == 5 * 17 - 2); }
    for (int i = 0; i < 11; ++i) { ServoFrequency[i] = 50; ServoCentrePulse[i] = 1500; }
    ServoFrequency[2] = 333; ServoFrequency[6] = 200; ServoFrequency[3] = 50; ServoFrequency[9] = 50; CheckServoType(); CHECK(ServoFrequency[3] == 333 && ServoFrequency[9] == 200 && ServoFrequency[0] == 50);
    // ---------------------------------------------------------------- B04: Motor off value clamped
    resetAll(); MotorChannelZero = 90; values["n0"] = (long)(uint32_t)-150; values["n1"] = 3; values["n4"] = 0; texts["t10"] = "3.5"; texts["t12"] = "40";
    ReadRXOptionsView(); CHECK(MotorChannelZero == 0 && TimerStartTime == 0 && Max_Safe_Amps == 40 && SFV == 350 && MotorChannel == 2);
    values["n0"] = (long)(uint32_t)-100; ReadRXOptionsView(); CHECK(MotorChannelZero == 0);
    values["n0"] = 50; ReadRXOptionsView(); CHECK(MotorChannelZero == 135);
    values["n0"] = 200; ReadRXOptionsView(); CHECK(MotorChannelZero == 180);
    MotorChannelZero = 90; values["n0"] = 65535; ReadRXOptionsView(); CHECK(MotorChannelZero == 90);   // a comms error keeps the old value
    // ---------------------------------------------------------------- B24: Scan RF refused while a model is connected
    resetAll(); CurrentMode = NORMAL; CurrentView = TXSETUPVIEW; ModelMatched = true; BoundFlag = true;
    StartWifiScan(); CHECK(boxes == 1 && CurrentMode == NORMAL && CurrentView == TXSETUPVIEW && lastBox.find("The model is connected") == 0);
    ModelMatched = false; StartWifiScan(); CHECK(boxes == 1 && CurrentMode == SCANWAVEBAND && CurrentView == SCANVIEW);
    CurrentMode = NORMAL; ModelMatched = true; BoundFlag = false;
    // ---------------------------------------------------------------- B95: the status word says binding is enabled
    MotorEnabled = false; BindingEnabled = true; CHECK((ScreenStatusNow() & 64) == 64 && (ScreenStatusNow() & 1) == 0);
    BindingEnabled = false; MotorEnabled = true; CHECK((ScreenStatusNow() & 64) == 0 && (ScreenStatusNow() & 1) == 1);
    MotorEnabled = false;
    // ---------------------------------------------------------------- B03: the motor switch seen OFF ends the silence after 'please turn it off'
    resetAll(); UseMotorKill = true; LedWasRed = true; LedWasGreen = false; Autoswitch = 1; SafetySwitch = 0; CurrentMode = NORMAL; CurrentView = FRONTVIEW; Bank = 1; PreviousBank = 1; DualRatesSwitch = 0; DualRateRate[0] = 0;
    MotorEnabled = false; MotorWasEnabled = false; SendNoData = false; SafetyON = false; SafetyWasOn = false;
    switchAt(1, 1); GetBank(); CHECK(SendNoData && !MotorEnabled && !MotorWasEnabled && countSound(PLSTURNOFF) == 1);   // switched on while not connected: told to turn it off, nothing sent
    GetBank(); CHECK(SendNoData && countSound(PLSTURNOFF) == 2);                                                             // still on: told again
    switchAt(1, 3); GetBank(); CHECK(!SendNoData && !MotorEnabled);                                                          // off: the silence ends
    GetBank(); CHECK(!SendNoData);
    switchAt(1, 1); LedWasRed = false; LedWasGreen = true; GetBank(); CHECK(MotorEnabled && !SendNoData);                    // connected: the motor may be on
    printf("test_bugfixes A (flight): %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''

# ------------------------------------------------------------------------------------------------------------ program B: the power button
B_DEFS = r'''
#define FRONTVIEW 0
#define RXSETUPVIEW 31
#define BUTTON_SENSE_PIN 33
#define POWERONOFFDELAY2 4000
#define CLICKZERO 0
#define BEEPCOMPLETE 17
#define WHAHWHAHMSG 25
#define BINDINGENABLED 98
static uint8_t PowerOffWarningSeconds = 2, AudioVolume = 50, RotorFlight_V = 0;
static uint32_t PreviousPowerOffTimer = 0, PowerCountdownShownAt = 0, ModelNumber = 1, VolumeRestoreAt = 0, CurrentWarningShownAt = 0;
static bool ButtonUpSinceBoot = false, BuddyMasterOnWireless = false, BuddyPupilOnWireless = false, SD_Card_Exists = true, BoundFlag = false, ModelMatched = false, LedWasGreen = false, TrimClicks = false, BindingEnabled = false, Force_Early_Sound = false, BatteryWarningShown = false;
static int CurrentView = FRONTVIEW;
static float Battery_Amps = 0; static uint16_t Max_Safe_Amps = 0;
static char WarnNow[] = "vis Warning,1", WarnOff[] = "vis Warning,0", Warning[] = "Warning", pFrontView[] = "page FrontView";
static uint32_t now = 0; static uint32_t millis() { return now; }
static bool buttonDown = false; static int digitalRead(int) { return buttonDown ? 0 : 1; }   // active low
static int closeDowns = 0, frontViews = 0, volumeSets = 0, lastVolume = -1, bindShown = 0;
static void Close_TX_Down() { ++closeDowns; }
static void GotoFrontView() { ++frontViews; CurrentView = FRONTVIEW; }
static void UpdateModelsNameEveryWhere() {}
static void SetAudioVolume(uint8_t v) { ++volumeSets; lastVolume = v; }
static void delay(uint32_t) {}
static void ShowBindingIsEnabled() { ++bindShown; }
void CheckPowerOffButton(); void CheckWhetherToEnableBinding(); void CheckMaxCurrent();
static void VolumeChore() { // the once-a-second chore of ManageTransmitter (main.cpp), as the source has it (the text is checked by this test too)
    if (VolumeRestoreAt && (int32_t)(millis() - VolumeRestoreAt) >= 0)
    {
        VolumeRestoreAt = 0;
        SetAudioVolume(AudioVolume);
    }
}
'''
B_LIFT = [('src/main.cpp', 'void CheckPowerOffButton()'), ('src/main.cpp', 'void CheckWhetherToEnableBinding()'), ('src/main.cpp', 'void CheckMaxCurrent()')]
B_MAIN = r'''
static void at(uint32_t t, bool down) { now = t; buttonDown = down; CheckPowerOffButton(); }
int main() {
    // ---------------------------------------------------------------- B01: the button released cancels the countdown and hides the box
    LedWasGreen = true; BoundFlag = true; ModelMatched = true; PowerOffWarningSeconds = 2;
    at(1000, false); CHECK(ButtonUpSinceBoot && cmds.empty());                       // up at the start: nothing happens, and a press may now switch off
    at(10000, true);  CHECK(countCmd("vis StillConnected,1") == 1 && closeDowns == 0 && texts["StillConnected"] == "TURN OFF?! 2");
    at(11000, true);  CHECK(texts["StillConnected"] == "TURN OFF?! 1" && closeDowns == 0);
    at(11500, false); CHECK(countCmd("vis StillConnected,0") == 1 && closeDowns == 0);   // let go: the box goes, nothing switched off
    at(12000, false); at(13000, false); CHECK(countCmd("vis StillConnected,0") == 1 && closeDowns == 0);   // and stays gone
    at(20000, true);  CHECK(countCmd("vis StillConnected,1") == 2 && texts["StillConnected"] == "TURN OFF?! 2");   // a new press starts the count afresh
    at(21000, true);  CHECK(texts["StillConnected"] == "TURN OFF?! 1" && closeDowns == 0);
    at(22000, true);  CHECK(texts["StillConnected"] == "TURN OFF?! 0" && closeDowns == 1);   // held through: off
    // not connected: a press switches off at once (after the first seconds)
    closeDowns = 0; LedWasGreen = false; at(30000, false); at(30100, true); CHECK(closeDowns == 1 && countCmd("vis StillConnected,1") == 2);
    // ---------------------------------------------------------------- B95: a hold from switch-on enables binding, however long, and never switches off
    cmds.clear(); sounds.clear(); texts.clear(); closeDowns = 0; ButtonUpSinceBoot = false; BindingEnabled = false; AudioVolume = 10; VolumeRestoreAt = 0; volumeSets = 0; LedWasGreen = false; BoundFlag = false; ModelMatched = false;
    at(500, true);  CHECK(!BindingEnabled && closeDowns == 0);
    at(1900, true); CHECK(!BindingEnabled);
    at(2500, true); CHECK(BindingEnabled && bindShown == 1 && countSound(BEEPCOMPLETE) == 1 && countSound(BINDINGENABLED) == 1 && countCmd("page FrontView") == 1);
    CHECK(volumeSets == 1 && lastVolume == 50 && VolumeRestoreAt == 7500);              // the announcement at half volume at least
    at(4500, true); at(6000, true); at(9000, true); CHECK(closeDowns == 0 && countSound(BINDINGENABLED) == 1);   // held past 4 s: NOT switched off, said once
    now = 7000; VolumeChore(); CHECK(volumeSets == 1); now = 7500; VolumeChore(); CHECK(volumeSets == 2 && lastVolume == 10 && VolumeRestoreAt == 0);   // the pilot's volume back 5 s later
    at(9500, false); CHECK(ButtonUpSinceBoot && closeDowns == 0);
    at(12000, true); CHECK(closeDowns == 1);                                          // let go once, a press switches off (not connected)
    // a short hold at switch-on, let go, pressed again: no binding, and no switch-off in the first 4 s
    cmds.clear(); sounds.clear(); closeDowns = 0; ButtonUpSinceBoot = false; BindingEnabled = false; bindShown = 0;
    at(500, true); at(1500, false); at(3000, true); CHECK(!BindingEnabled && closeDowns == 0);
    at(3900, true); CHECK(closeDowns == 0); at(4100, true); CHECK(closeDowns == 1 && !BindingEnabled);
    // a loud transmitter keeps its volume
    sounds.clear(); closeDowns = 0; ButtonUpSinceBoot = false; BindingEnabled = false; AudioVolume = 80; volumeSets = 0; VolumeRestoreAt = 0;
    at(500, true); at(2500, true); CHECK(BindingEnabled && volumeSets == 0 && VolumeRestoreAt == 0);
    // with a buddy session or no card the hold does nothing
    BindingEnabled = false; ButtonUpSinceBoot = false; BuddyPupilOnWireless = true; at(500, true); at(2500, true); CHECK(!BindingEnabled); BuddyPupilOnWireless = false;
    // ---------------------------------------------------------------- B02: the current warning is a line on the front page for six seconds, never a box
    cmds.clear(); sounds.clear(); texts.clear(); boxes = 0; LedWasGreen = true; CurrentView = FRONTVIEW; RotorFlight_V = 0; BatteryWarningShown = false; Battery_Amps = 50; Max_Safe_Amps = 40;
    now = 100000; CheckMaxCurrent(); CHECK(boxes == 0 && countCmd("vis Warning,1") == 1 && texts["Warning"] == "Current too high!" && countSound(WHAHWHAHMSG) == 1 && CurrentWarningShownAt == 100000);
    now = 103000; CheckMaxCurrent(); CHECK(countCmd("vis Warning,0") == 0 && countSound(WHAHWHAHMSG) == 1);
    now = 106100; CheckMaxCurrent(); CHECK(countCmd("vis Warning,0") == 1 && CurrentWarningShownAt == 0);
    now = 120000; CheckMaxCurrent(); CHECK(countSound(WHAHWHAHMSG) == 1 && boxes == 0);   // warned once per connection
    LedWasGreen = false; CheckMaxCurrent(); LedWasGreen = true; now = 130000; CheckMaxCurrent(); CHECK(countSound(WHAHWHAHMSG) == 2 && CurrentWarningShownAt == 130000);   // a new connection: warned again
    // a Rotorflight model: the box is not hidden at the end (the front page writes its ESC temperature into it by itself)
    cmds.clear(); RotorFlight_V = 1; now = 136100; CheckMaxCurrent(); CHECK(countCmd("vis Warning,0") == 0 && CurrentWarningShownAt == 0);
    // not on the front page: nothing is drawn, no box either; the timer still runs out
    cmds.clear(); texts.clear(); boxes = 0; LedWasGreen = false; CheckMaxCurrent(); LedWasGreen = true; CurrentView = RXSETUPVIEW; RotorFlight_V = 0; now = 140000; CheckMaxCurrent();
    CHECK(boxes == 0 && cmds.empty() && texts.count("Warning") == 0 && CurrentWarningShownAt == 140000);
    now = 146100; CheckMaxCurrent(); CHECK(CurrentWarningShownAt == 0 && cmds.empty());
    // a battery warning in the box is left alone when the current warning's six seconds end
    LedWasGreen = false; CheckMaxCurrent(); LedWasGreen = true; CurrentView = FRONTVIEW; cmds.clear(); now = 150000; CheckMaxCurrent(); BatteryWarningShown = true; now = 156100; CheckMaxCurrent(); CHECK(countCmd("vis Warning,0") == 0);
    printf("test_bugfixes B (power button): %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''

# ------------------------------------------------------------------------------------------------------------ program C: logs and files
C_DEFS = r'''
#define FILE_READ 0
#define FILE_WRITE 1
static std::map<std::string, std::string> card; static int removes = 0;
struct File { std::string name; bool ok = false; File() {} File(const std::string &n, bool o) : name(n), ok(o) {} size_t write(const char *d, size_t n) { if (!ok) return 0; card[name].append(d, n); return n; } int read(char *, int) { return 0; } void seek(long) {} void close() { ok = false; } operator bool() const { return ok; } };
struct Card { File open(const char *n, int mode) { if (mode == FILE_WRITE) { if (strstr(n, "NOROOM")) return File(n, false); if (!card.count(n)) card[n] = ""; return File(n, true); } return File(n, card.count(n) > 0); } bool remove(const char *n) { ++removes; return card.erase(n) > 0; } } TINYCARD;
struct tmElements_t { int Day, Month, Year; } tm;
static bool clockOk = true; struct Rtc { bool read(tmElements_t &) { return clockOk; } } RTC;
static uint8_t GmonthDay = 13, Gmonth = 10, Gyear = 26; static int rtcDay = 13, rtcMonth = 10, rtcYear = 26;
static void ReadTheRTC() { GmonthDay = rtcDay; Gmonth = rtcMonth; Gyear = rtcYear; }
static char TextFileName[40] = "", LogWriteName[40] = "", SearchFile[80] = "", SingleModelFile[40] = "", MOD[10] = "", Mfiles[10] = "", TheFilesList[150][24];
static File LogFileNumber, LogWriteFile; static bool LogFileOpen = false, LogWriteOpen = false, SingleModelFlag = false, FileError = false;
static uint16_t LastFileInView = 0;
static std::string stamp = "12:00:00"; static void CreateTimeStamp(char *d) { strcpy(d, stamp.c_str()); }
static int delays = 0; static void DelayWithDog(uint32_t) { ++delays; }
static void CloseModelsFile() {}
static int modelsSaved = 0; static void SaveOneModel(uint32_t) { ++modelsSaved; if (SingleModelFlag) { if (strstr(SingleModelFile, "NOROOM")) { FileError = true; return; } card[std::string("/mod/") + SingleModelFile] = "model"; } }
static char toUpperCase(char c) { return (char) toupper((unsigned char) c); }
static int restores = 0, saveCurrents = 0, loadsForRenaming = 0, selectors = 0; static void SaveCurrentModel() { ++saveCurrents; } static void LoadModelForRenaming() { ++loadsForRenaming; } static void RestoreCurrentModel() { ++restores; } static void BuildDirectory() {} static void LoadFileSelector() { ++selectors; }
static char pModelsView[] = "page ModelsView";
static std::string typedName; static bool nameGiven = true;
static bool GetBackupFilename(char *, char *tt1, char *, char *, char *) { if (!nameGiven) return false; strcpy(tt1, typedName.c_str()); return true; }
int InStrng(char *text1, char *text2); bool MayBeAddZero(uint8_t nn); void AddPath(char *filename); void MakeDatedLogName(char *Dest); void MakeTextFileName(); void MakeLogWriteName();
void CheckLogFileIsOpen(); void CloseLogFile(); void CloseLogWriteFile(); void WriteToLogFile(char *SomeData, uint16_t len); bool LogFilePreamble(); void LogText(char *TheText, uint16_t len, bool TimeStamp);
void OpenLogFileW(); void DeleteLogFile(); void DeleteThisLogFile(); bool WriteBackup(); void FixFileName(); void RenameFile(); void ShowFileErrorMsg();
static bool CheckFileExists(char *fl) { AddPath(fl); return card.count(SearchFile) > 0; }
'''
C_LIFT = [('src/main.cpp', 'int InStrng(char *text1, char *text2)'), ('include/Utilities.h', 'bool MayBeAddZero(uint8_t nn)'), ('include/SDFiles.h', 'void AddPath(char *filename)'),
          ('include/LogFiles.h', 'FASTRUN void MakeDatedLogName(char *Dest)'), ('include/LogFiles.h', 'FASTRUN void MakeTextFileName()'), ('include/LogFiles.h', 'FASTRUN void MakeLogWriteName()'),
          ('include/LogFiles.h', 'FASTRUN void CheckLogFileIsOpen()'), ('include/LogFiles.h', 'FASTRUN void CloseLogFile()'), ('include/LogFiles.h', 'FASTRUN void CloseLogWriteFile()'),
          ('include/LogFiles.h', 'FASTRUN void WriteToLogFile(char *SomeData, uint16_t len)'), ('include/LogFiles.h', 'FASTRUN bool LogFilePreamble()'), ('include/LogFiles.h', 'FASTRUN void LogText(char *TheText, uint16_t len, bool TimeStamp)'),
          ('include/SDFiles.h', 'FASTRUN void OpenLogFileW()'), ('include/SDFiles.h', 'FASTRUN void DeleteLogFile()'), ('include/SDFiles.h', 'void DeleteThisLogFile()'),
          ('src/main.cpp', 'bool WriteBackup()'), ('src/main.cpp', 'void FixFileName()'), ('src/main.cpp', 'void ShowFileErrorMsg()'), ('include/SDFiles.h', 'void RenameFile()')]
C_MAIN = r'''
static void logIt(const char *s) { char b[100]; strcpy(b, s); LogText(b, (uint16_t) strlen(b), true); }
int main() {
    // ---------------------------------------------------------------- B56: the logger has its own file name and handle
    char nm[40];
    clockOk = true; rtcDay = 13; rtcMonth = 10; rtcYear = 26; MakeDatedLogName(nm); CHECK(strcmp(nm, "13-10-26.LOG") == 0 || strcmp(nm, "13-10-2026.LOG") == 0);
    rtcDay = 5; rtcMonth = 3; MakeDatedLogName(nm); CHECK(strncmp(nm, "05-03-", 6) == 0);
    clockOk = false; MakeDatedLogName(nm); CHECK(strcmp(nm, "NO_CLOCK.LOG") == 0); clockOk = true; rtcDay = 13; rtcMonth = 10;
    MakeDatedLogName(nm); const std::string today = std::string("/log/") + nm;
    // the viewer is on a help text: a log line goes to today's log, never into the help file, and the viewer keeps its name
    card.clear(); strcpy(TextFileName, "FRONT.TXT"); strcpy(LogWriteName, ""); LogFileOpen = false; LogWriteOpen = false;
    logIt("Model found"); CHECK(card.count(today) == 1 && card[today].find("Model found") != std::string::npos && card.count("/help/FRONT.TXT") == 0 && strcmp(TextFileName, "FRONT.TXT") == 0 && !LogWriteOpen);
    // the viewer is on an old log: today's log still gets the line, the old one nothing
    strcpy(TextFileName, "01-10-26.LOG"); card["/log/01-10-26.LOG"] = "old";
    logIt("Model matched"); CHECK(card[today].find("Model matched") != std::string::npos && card["/log/01-10-26.LOG"] == "old");
    // nothing open: a write goes nowhere (and never into the viewer's file)
    LogWriteOpen = false; { char x[] = "stray"; WriteToLogFile(x, 5); } CHECK(card[today].find("stray") == std::string::npos && card["/log/01-10-26.LOG"] == "old");
    // a new day's name comes from the clock once the name is cleared
    strcpy(LogWriteName, ""); rtcDay = 14; MakeDatedLogName(nm); logIt("Next day"); CHECK(card.count(std::string("/log/") + nm) == 1 && card[std::string("/log/") + nm].find("Next day") != std::string::npos);
    rtcDay = 13; MakeDatedLogName(nm);
    // MakeTextFileName fills only an empty viewer name
    strcpy(TextFileName, "KEEP.LOG"); MakeTextFileName(); CHECK(strcmp(TextFileName, "KEEP.LOG") == 0);
    strcpy(TextFileName, ""); MakeTextFileName(); CHECK(std::string(TextFileName) == std::string(nm));
    // the card will not open the log: nothing is written, nothing breaks, the handle stays closed
    strcpy(LogWriteName, "NOROOM.LOG"); logIt("Lost"); CHECK(!LogWriteOpen && card.count("/log/NOROOM.LOG") == 0); strcpy(LogWriteName, "");
    // a deleted log is not the one OK opens next
    card["/log/01-10-26.LOG"] = "old"; strcpy(TheFilesList[0], "01-10-26.LOG"); values["FilesBox"] = 0; confirmAnswer = true;
    DeleteThisLogFile(); CHECK(card.count("/log/01-10-26.LOG") == 0 && strcmp(TextFileName, "") == 0 && selectors == 1);
    card["/log/02-10-26.LOG"] = "old"; strcpy(TheFilesList[0], "02-10-26.LOG"); confirmAnswer = false; DeleteThisLogFile(); CHECK(card.count("/log/02-10-26.LOG") == 1 && strcmp(TextFileName, "02-10-26.LOG") == 0);
    // ---------------------------------------------------------------- B21: a backup rename deletes the old file only after the new one is written
    card.clear(); cmds.clear(); FileError = false;
    strcpy(SingleModelFile, "newname"); CHECK(WriteBackup() && card.count("/mod/NEWNAME.MOD") == 1 && !FileError && !SingleModelFlag);
    strcpy(SingleModelFile, "VERYLONGNAME1"); CHECK(!WriteBackup() && card.size() == 1 && !FileError && countCmd("vis error,1") == 3);   // refused: too long for the card, said, nothing written
    strcpy(SingleModelFile, "NOROOM"); cmds.clear(); CHECK(!WriteBackup() && card.count("/mod/NOROOM.MOD") == 0 && countCmd("vis error,1") == 3);   // the card would not take it
    // RenameFile: OLD.MOD renamed to NEW
    card.clear(); card["/mod/OLD.MOD"] = "model"; texts["filename"] = "OLD.MOD"; typedName = "new"; nameGiven = true; confirmAnswer = true; restores = 0; removes = 0;
    RenameFile(); CHECK(card.count("/mod/NEW.MOD") == 1 && card.count("/mod/OLD.MOD") == 0 && restores == 1 && saveCurrents == 1);
    // a refused name: the old file stays, the live model still comes back
    card.clear(); card["/mod/OLD.MOD"] = "model"; typedName = "VERYLONGNAME1"; restores = 0;
    RenameFile(); CHECK(card.count("/mod/OLD.MOD") == 1 && card.size() == 1 && restores == 1);
    // the same name: nothing to do, nothing deleted, the live model back
    typedName = "OLD.MOD"; restores = 0; removes = 0; RenameFile(); CHECK(card.count("/mod/OLD.MOD") == 1 && removes == 0 && restores == 1);
    // the new name exists and the overwrite is declined: both stay
    card["/mod/NEW.MOD"] = "other"; typedName = "NEW"; confirmAnswer = false; restores = 0;
    RenameFile(); CHECK(card["/mod/NEW.MOD"] == "other" && card.count("/mod/OLD.MOD") == 1 && restores == 1 && lastBox.find("Overwrite NEW.MOD?") == 0);
    confirmAnswer = true; RenameFile(); CHECK(card["/mod/NEW.MOD"] == "model" && card.count("/mod/OLD.MOD") == 0);   // agreed: written over, the old one gone
    // the card would not take the new file: the old one stays
    card.clear(); card["/mod/OLD.MOD"] = "model"; typedName = "NOROOM"; restores = 0; RenameFile(); CHECK(card.count("/mod/OLD.MOD") == 1 && card.count("/mod/NOROOM.MOD") == 0 && restores == 1);
    // no name given: nothing changes, the live model back
    nameGiven = false; restores = 0; RenameFile(); CHECK(card.count("/mod/OLD.MOD") == 1 && card.size() == 1 && restores == 1);
    printf("test_bugfixes C (logs and files): %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''

def build_and_run(name, defs, lifts, main, pre=''):
    prog = pre + COMMON + defs + ''.join(lift(rel, head) for rel, head in lifts) + main
    d = tempfile.mkdtemp(); cpp = os.path.join(d, name + '.cpp'); open(cpp, 'w').write(prog)
    r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-but-set-variable', '-Wno-format', '-o', os.path.join(d, name), cpp], capture_output=True, text=True)
    if r.returncode:
        print('--- %s did not compile:\n%s' % (name, r.stderr[:6000])); return 1
    return subprocess.run([os.path.join(d, name)]).returncode

# ------------------------------------------------------------------------------------------------------------ the source text
def source_checks():
    n = f = 0
    def chk(ok, what):
        nonlocal n, f
        n += 1
        if not ok: f += 1; print('   FAIL (source):', what)
    m = src('src/main.cpp'); tr = src('include/transceiver.h'); lf = src('include/LogFiles.h'); lfd = src('include/LogFilesDisplay.h'); sd = src('include/SDcard.h'); mo = src('include/MenuOptions.h'); ci = src('include/ChooseImage.h')
    # B13: the ESC temperature is stored only after it has passed the check
    i = tr.find('case 24:'); seg = tr[i:i + 900]
    chk(0 < seg.find('if (!(t > -100.0f && t < 300.0f))') < seg.find('ESC_Temp = t;'), 'B13 the check comes before the store')
    chk('snprintf(ESC_Temperature, sizeof(ESC_Temperature)' in src('include/Telemetry.h') and 'sprintf(Max_Rotor_RPM,' not in src('include/Telemetry.h'), 'B13 bounded prints on the Data page')
    # B16 / B17: the calibration defaults only when a calibration starts, and nothing saved until Finish
    chk(m.count('SetDefaultValues(true)') == 1 and 'if (Calibrating)' in m and 'CurrentView == CALIBRATEVIEW)\n    {\n        UseMotorKill = false' not in m, 'B16 the calibration branch is taken only by a calibration')
    i = m.find('Look("Starting calibration")'); seg = m[i:m.find('CurrentMode = CALIBRATELIMITS', i)]
    chk('SaveTransmitterParameters' not in seg and 'SetDefaultValues(true)' in seg and 'ReduceLimits()' in seg, 'B17 nothing is saved when a calibration starts')
    i = m.find('if (CurrentView == CALIBRATEVIEW)\n            {\n                if (CurrentMode == CALIBRATELIMITS || CurrentMode == CENTRESTICKS)')
    chk(i > 0 and 'LoadAllParameters();' in m[i:i + 500] and 'CurrentMode = NORMAL;' in m[i:i + 500], 'B17 OK part way puts the card\'s values back')
    # B23: Model options' values go with Help, Model picture and Servos
    chk('if (CurrentView == RXSETUPVIEW1)\n                ReadRXOptionsView();' in m and 'if (CurrentView == RXSETUPVIEW1)\n                RXOptionsViewStart();' in m, 'B23 Help from Model options reads first and redraws after')
    chk('ReadRXOptionsView();\n        SaveOneModel(ModelNumber);' in ci and 'ReadRXOptionsView();\n        SaveOneModel(ModelNumber);' in mo, 'B23 Model picture and Servos read the page first')
    chk(mo.count('void ReadRXOptionsView()') == 1 and 'void RXOptionsViewEnd()\n{' in mo and 'ReadRXOptionsView();\n    SendValue(Progress, 100);' in mo, 'B23 RXOptionsViewEnd reads through ReadRXOptionsView')
    # B26
    chk('#define LOSTCONTACTTHRESHOLD 100 ' in src('include/BuddyWireless.h'), 'B26 the buddy threshold is 100')
    # B36 / B04 on a load
    chk('Drate1 < 10' not in sd and 'Drate2 < 10' not in sd and 'Drate3 < 10' not in sd and sd.count('> 200)\n        Drate') == 3, 'B36 rates 0-9 % survive a load')
    chk('if (MotorChannelZero > 180)\n        MotorChannelZero = 0;' in sd, 'B04 a wrapped motor-off value loads as the low end')
    # B56: no write through the viewer's handle anywhere; Close_TX_Down closes the logger's
    chk('LogFileNumber.write' not in lf and 'LogFileNumber.write' not in m and 'if (!LogWriteOpen)\n        return;' in lf, 'B56 the logger writes only through its own handle')
    chk('CloseLogWriteFile();\n        strcpy(LogWriteName, "");' in m and 'strcpy(LogWriteName, ""); // B56' in m, 'B56 the power-off and a new connection use the logger\'s name')
    chk('if (InStrng((char *)".TXT", TextFileName))\n                strcpy(TextFileName, "");' in m, 'B56 the help text is let go of on the way back')
    # B57
    chk(lfd.count('MAXSEEKPOSITIONS - 1') >= 3, 'B57 the log viewer stops at the end of its table')
    # B95
    chk('if (BindingEnabled)\n        s |= 64;' in src('include/FlightGuard.h'), 'B95 status bit 64')
    chk('!ButtonUpSinceBoot && (millis() >= 2000)' in m and '(millis() > POWERONOFFDELAY2) && ButtonUpSinceBoot' in m, 'B95 the hold from switch-on')
    chk('if (VolumeRestoreAt && (int32_t)(millis() - VolumeRestoreAt) >= 0)\n        {' in m and 'VolumeRestoreAt = 0;\n            SetAudioVolume(AudioVolume);' in m, 'B95 the volume comes back in the once-a-second chores (as the test\'s copy has it)')
    # B01
    chk('if (digitalRead(BUTTON_SENSE_PIN) || CheckingPowerButton)' not in m and 'if (digitalRead(BUTTON_SENSE_PIN) && !PowerOffTimer && !PowerWarningVisible)' in m, 'B01 a release reaches the cancel branch')
    # B02
    chk('if (LedWasGreen)\n            return; // B02' in src('include/RF_RotorFlight.h'), 'B02 the Rotorflight menu touch is ignored in flight')
    # B05 / B06
    chk('ScreenData[MIXOUTPUT] = Mixes[MixNumber][M_MIX_OUTPUTS];' in mo and 'ScreenData[MIXOUTPUT] = Mixes[MixNumber][M_MIX_INPUTS]' not in mo, 'B05 the output flag typo')
    i = m.find('New load of mix window'); chk('ReceiveLotsofData' not in m[i:i + 300], 'B05 no read-back when the page opens')
    i = m.find('void SetDefaultValues(bool Calibrating)'); seg = m[i:i + 9000]
    chk('RotorFlight_V = 0;' in seg and 'LinkRatesToBanks = false;' in seg, 'B06 defaults clear the Rotorflight flag and the linked rates')
    # B18, B30, B37, B38, B11, B31
    chk('v = GetValue(cb0); if (v <= 3) Buddy_Low_Position = v;' in mo, 'B18 a buddy list left at 255 keeps the old value')
    chk('Push every top switch fully AWAY' in m, 'B30 the calibration asks for the top switches pushed away')
    chk('ReadSpeedsScreen(PreviousBank - 1, true);' in src('include/Switches.h') and 'GetText(change, chgs, sizeof(chgs));' in m, 'B37 the servo speed edits are fetched from the page on a bank switch')
    chk('if (SticksMode != OldSticksMode)\n        ResetAllTrims();' in mo, 'B38 a stick mode change rebuilds the trim lever map')
    chk('if (SlaveChannel < 0 || SlaveChannel >= CHANNELSUSED) break;' in src('include/Mixes.h'), 'B11 the mixer guard')
    chk('SourceOfOutput((uint8_t)ch0)' in src('include/RF_Adjust.h') and 'SourceOfOutput(i) > 3' in m, 'B31 the other users of the routing map read it the same way round')
    # B10: the per-bank rate choice is an index: 0-3 everywhere it is read
    chk('DualRateRate[Bank - 1] >= 1 && DualRateRate[Bank - 1] <= 3' in src('include/Switches.h') and 'ScreenData[11] <= 3 ? ScreenData[11] : 0' in src('include/DualRates.h') and 'if (DualRateRate[i] > 3)\n            DualRateRate[i] = 0;' in sd, 'B10 the rate choice is 0-3 wherever it is read')
    # B27: a countdown of no minutes counts up
    chk('const bool CountingDown = TimerDownwards && TimerStartTime > 0;' in src('include/Motor_sign.h') and src('include/Motor_sign.h').count('if (TimerDownwards)') == 0, 'B27 the countdown with no minutes counts up')
    # the screen's side of B95 (the sister repo, when it is where the release script expects it)
    scr = os.path.join(os.path.dirname(ROOT), 'ESP32-board2', 'board4', 'nextion-emulator')
    if os.path.isdir(scr):
        ts = open(os.path.join(scr, 'lib', 'LdrcUpdate', 'TxState.h')).read(); fl = open(os.path.join(scr, 'lib', 'LdrcFlight', 'LdrcFlight.cpp')).read()
        chk('TX_BINDING = 64' in ts and 'binding = (bits & TX_BINDING) != 0;' in ts, 'B95 the screen reads bit 64')
        chk('if (src.binding()) return "BINDING ENABLED";' in fl, 'B95 every defined front screen says BINDING ENABLED')
    print('test_bugfixes source checks: %d checks, %d failures' % (n, f))
    return 1 if f else 0

rc = 0
rc |= build_and_run('flight', A_DEFS, A_LIFT, A_MAIN)
rc |= build_and_run('power', B_DEFS, B_LIFT, B_MAIN)
rc |= build_and_run('files', C_DEFS, C_LIFT, C_MAIN, pre='#define OWN_SAVE_ONE_MODEL\n')
rc |= source_checks()
sys.exit(rc)
