#!/usr/bin/env python3
"""NO ANSWER IS NOT A NUMBER - and the rest of what the eighth review of B211 found (15 Nov 2026; two reviewers, fifteen findings).

Built on dev/test_stalepress: its pretend screen (now with a loop that can STAND STILL and a second core that says so), its real
routines lifted out of the headers - and more of the real ones here: MsgBox, GetConfirmation, EnsureMotorIsOff, the OK routines
of the older pages (Servo types, Buddy channels, Inputs, the transmitter's options, the curve), the Bank names page's Listen, the
Dual-rates page's own look at its boxes.

 1. NO ANSWER IS NOT A NUMBER. A box asked for can have no answer (65535, "", 0): the older pages' OK routines took that for the
    box's value - a servo's frequency 65535 saved and sent to the receiver, "the pupil has all switches", a stick on another
    channel, the pressure at sea level 65535 sent to the receiver. Each setting now stays as it is; the pilot is told.
 2. THE MOTOR SWITCH'S BOX AND THE SCREEN'S RESTART: the box "The motor switch is ON" closed at once, round and round, the dog
    unfed until it bit (5.8 s: the Teensy restarts at 2.5).
 3. A BOX INSIDE A BOX: the OK pressed on a box put up from inside a question's own wait was taken for that question's answer -
    "Delete every model and all settings?": Yes, by itself.
 4. A PAGE COMMAND FROM INSIDE A WAIT that is no get's (the power button's way to the front page): the boxes read afterwards came
    from the other page.
 5. EVERY SIGN OF THE SCREEN'S RESTART LOST: what a page asks by itself (the Models page's lists, twice a second) was answered
    by the page as the card has it - model 1 loaded by itself.
 6. AN ANSWER THAT NEVER CAME MAY COME YET: after a stall longer than a question's wait the old answer was the next question's.
 7. THE SCREEN'S SHOUT ("LDRCLOG core 1 (the loop's) silent for ...") in front of the very answer its silence made late.
 8. Bytes that trickle or flood without an end; an answer that comes at the last moment of its wait.
 9. The screen restarts during a calibration of the sticks.
10. A text box's letters are never a marker, a number or a page - by whatever way they are read; the pipe's state is no pipe line.

   python3 dev/test_noanswer/test_noanswer.py            (--show: the scenes' own account)"""
import glob, importlib.util, os, re, subprocess, sys, tempfile
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('stalepress_for_noanswer', os.path.join(os.path.dirname(HERE), 'test_stalepress', 'test_stalepress.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
DUAL = m.release(m.src('include/DualRates.h'))

EXTRA = r'''
// ================= what the real routines lifted below are given =================
bool RfLeaveAfterSave = false, BuddyPupilOnWireless = false, FlightRestart = false, MotorEnabled = false, SendNoData = false, Force_Early_Sound = false;
char WarnNow[] = "vis Warning,1", WarnOff[] = "vis Warning,0", Warning[] = "Warning", err_MotorOn[] = "MOTOR IS ON!", pFrontView[] = "page FrontView";
char pBuddyView[] = "page BuddyView", pRXSetupView[] = "page RXSetupView", pTXSetupView[] = "page TXSetupView";
static long motorChecks = 0; static uint64_t motorOffAtUs = UINT64_MAX;
static void CheckMotorOff() { ++motorChecks; if (nowUs >= motorOffAtUs) MotorEnabled = false; }   // (the pilot's hand on the motor switch, at a set moment)
uint8_t BanksInUse[BANKS_USED] = { 0, 1, 2, 3, 32, 33 }, BankSounds[BANK_NAMES_N]; static uint8_t BanksCount() { return 6; }
uint16_t ServoCentrePulse[11] = { 1500, 1500, 760, 760, 1500, 1500, 1500, 1500, 1500, 1500, 1500 };
uint16_t ServoFrequency[11] = { 50, 50, 333, 333, 50, 50, 50, 50, 50, 50, 50 };
static std::vector<int> queued; static void AddParameterstoQueue(uint8_t id) { queued.push_back(id); }
uint16_t BuddyControlled = 0; bool BuddyHasAllSwitches = false; static void CloseModelsFile() {}
uint8_t CurvePoint[BANKS_USED + 1][17][CURVE_POINTS_MAX], CurveStore[BANKS_USED + 1][17][CURVE_STORE_MAX], InterpolationTypes[BANKS_USED + 1][17], Exponential[BANKS_USED + 1][17];
uint8_t Bank = 1, ChanneltoSet = 3; static void Force_ReDisplay() {}
uint8_t InPutStick[17] = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 }, ChannelOutPut[17] = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 }, InputTrim[4] = { 0, 1, 2, 3 };
static int outputChecks = 0; static void CheckOutPutChannels() { ++outputChecks; } static void UpdateButtonLabels() {} uint32_t LastTimeRead = 0;
short int TxVoltageCorrection = 2, DeltaGMT = 1; uint8_t PowerOffWarningSeconds = 2, ConnectionAssessSeconds = 1, ScanSensitivity = 42, MinimumGap = 75, LEDBrightness = 100, BackGroundSelection = 1;
float Qnh = 1009; bool UseLog = false, LogRXSwaps = false, LedWasGreen = true; static int txSetupStarts = 0; static void StartTXSetupView() { ++txSetupStarts; }
uint8_t DualRateChannels[8] = { 1, 2, 4, 0, 0, 0, 0, 0 }; static int rateNamesShown = 0; static void ShowDualRateChannelsName(char *, uint8_t) { ++rateNamesShown; }
uint8_t DualRateRate[BANKS_USED + 1] = { 1, 1, 1, 1, 1, 1, 1 }; static int ratesSet = 0; static void SetNewDualRate() { ++ratesSet; DualRateRate[Bank - 1] = (uint8_t) TextIn[4]; }
char SingleModelFile[40] = "";
@LIFTS@
static void ListenAsItWas() { for (int i = 0; i < BanksCount(); ++i) { BanksInUse[i] = BankNameFromPage(i); PlaySound(BankSounds[BanksInUse[i]]); DelayWithDog(1200); } }   // (scene 4a: a box, a sound, a wait - as "Listen" was until the twelfth review)
// ---- what flying the model can do from inside a wait
static int waitsSeen = 0, powerAtWait = -1;
static void PowerButtonInWait()   // main.cpp CheckPowerOffButton's part that matters (connected, not on the front page): the front page - not under a get, not over a question
{
    if (NextionGetPending || ModalWaits) return;
    if (++waitsSeen != powerAtWait) return;
    GotoFrontView();
}
static int pageOverAfter = 0; static void PageOverQuestion() { if (pageOverAfter && --pageOverAfter == 0) SendCommand((char *) "page FrontView"); }   // (a page put up over a question, and nothing answered)
static uint64_t lostAtUs = 0; static bool lostDone = false;
static void LinkLost() { if (lostDone || nowUs < lostAtUs) return; lostDone = true; MotorEnabled = true; EnsureMotorIsOff(); }   // RedLedOn's part that matters: the link is lost with the motor switch on
static void LinkLostNow() { MotorEnabled = true; EnsureMotorIsOff(); }
// ---- more buttons for the loop's Dispatch
static void more24(int n) { if (n == 11) EndServoTypeView(); else if (n == 12) InputsViewEnd(); else if (n == 14) OptionView3End(); }
static void more7(int n) { if (n == 29) BuddyChViewEnd(); }
static void addPages()
{
    Page sv; sv.id = 34;   // Servo types: the frequencies (n0-n7, n16, n18, n20) and the centre pulses (n8-n15, n17, n19, n21)
    for (const char *f : { "n0", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n16", "n18", "n20" }) sv.boxes[f] = { false, 50, "" };
    for (const char *c : { "n8", "n9", "n10", "n11", "n12", "n13", "n14", "n15", "n17", "n19", "n21" }) sv.boxes[c] = { false, 1500, "" };
    sv.boxes["Progress"] = { false, 0, "" }; sv.boxes["change"] = { true, 0, "" }; sv.numberBoxes = { "n5box" };
    { std::vector<uint8_t> b = { 0x00, 11, 0x00, 0x00 }; const char *chg = "n0 n1 n2 n4 n8 n9 n10 n12 "; b.insert(b.end(), chg, chg + strlen(chg)); sv.buttons["OK"] = b; }
    screen.pages["ServosTypeView"] = sv;
    Page bc; bc.id = 18; bc.boxes["mSwitch"] = { false, 0, "" }; bc.boxes["Progress"] = { false, 0, "" }; bc.boxes["change"] = { true, 0, "" };
    for (int i = 1; i <= 16; ++i) { char n[8]; snprintf(n, sizeof n, "fs%d", i); bc.boxes[n] = { false, 0, "" }; }
    { std::vector<uint8_t> b = { 128 + 29, 0x00, 0x00, 0x00 }; const char *chg = "mSwitch fs1 fs3 fs5 "; b.insert(b.end(), chg, chg + strlen(chg)); bc.buttons["OK"] = b; }
    screen.pages["BuddyChView"] = bc; { Page bv; bv.id = 16; screen.pages["BuddyView"] = bv; }
    { Page gv; gv.id = 21; gv.boxes["callfm"] = { false, 0, "" }; screen.pages["GraphView"] = gv; Page st; st.id = 26; screen.pages["SticksView"] = st; }
    Page iv; iv.id = 22; iv.boxes["Progress"] = { false, 0, "" }; iv.boxes["change"] = { true, 0, "" };
    for (int i = 1; i <= 16; ++i) { char n[8]; snprintf(n, sizeof n, "c%d", i); iv.boxes[n] = { false, i, "" }; snprintf(n, sizeof n, "n%d", i + 3); iv.boxes[n] = { false, i, "" }; }
    for (int i = 0; i < 4; ++i) { char n[8]; snprintf(n, sizeof n, "n%d", i); iv.boxes[n] = { false, i + 1, "" }; }
    { std::vector<uint8_t> b = { 0x00, 12, 0x00, 0x00 }; const char *chg = "c1 c2 n4 n5 n0 "; b.insert(b.end(), chg, chg + strlen(chg)); iv.buttons["OK"] = b; }
    screen.pages["InputsView"] = iv; { Page rs; rs.id = 8; screen.pages["RXSetupView"] = rs; Page ts; ts.id = 7; screen.pages["TXSetupView"] = ts; }
    Page o3; o3.id = 28;
    o3.boxes["t2"] = { false, 5, "" }; o3.boxes["n2"] = { false, 4, "" }; o3.boxes["Qnh"] = { false, 1021, "" }; o3.boxes["n1"] = { false, 100, "" }; o3.boxes["n3"] = { false, 3, "" };
    o3.boxes["n4"] = { false, 60, "" }; o3.boxes["n0"] = { false, 90, "" }; o3.boxes["sw0"] = { false, 1, "" }; o3.boxes["sw1"] = { false, 1, "" }; o3.buttons["OK"] = { 0x00, 14, 0x00, 0x00 };
    screen.pages["OptionView3"] = o3;
    { Page o2; o2.id = 27; o2.boxes["dGMT"] = { false, 2, "" }; screen.pages["OptionView2"] = o2; Page cv; cv.id = 19; cv.boxes["n0"] = { false, 3, "" }; screen.pages["ColoursView"] = cv; }
    { Page bn; bn.id = 20; for (int i = 1; i <= 6; ++i) { char n[8]; snprintf(n, sizeof n, "BK%d", i); bn.boxes[n] = { false, 10 + i, "" }; } screen.pages["BankNameView"] = bn; }
    { Page dr; dr.id = 31; const char *names[8] = { "n2", "n0", "n1", "n3", "n6", "n4", "n5", "n7" }; const int now[8] = { 1, 2, 4, 0, 0, 0, 0, 0 }; for (int i = 0; i < 8; ++i) dr.boxes[names[i]] = { false, now[i], "" }; dr.boxes["rate"] = { false, 1, "" }; screen.pages["DualRatesView"] = dr; }
    { Page bk; bk.id = 23; bk.boxes["t0"] = { true, 0, "" }; bk.boxes["t1"] = { true, 0, "" }; bk.boxes["t3"] = { true, 0, "" }; bk.boxes["Modelname"] = { true, 0, "" }; bk.buttons["yes"] = { 0x81, 0x00, 0x00, 0x00 }; screen.pages["BackupView"] = bk; }
    screen.pages0 = screen.pages;
}
static void more()   // a fresh start of the test's world, with the pages and buttons of this file
{
    fresh(); addPages(); extra24 = more24; extra7 = more7; queued.clear(); motorChecks = 0; motorOffAtUs = UINT64_MAX; MotorEnabled = false; SendNoData = false; lostDone = false; lostAtUs = 0; waitsSeen = 0; powerAtWait = -1;
    static const uint16_t f0[11] = { 50, 50, 333, 333, 50, 50, 50, 50, 50, 50, 50 }, c0[11] = { 1500, 1500, 760, 760, 1500, 1500, 1500, 1500, 1500, 1500, 1500 };
    memcpy(ServoFrequency, f0, sizeof f0); memcpy(ServoCentrePulse, c0, sizeof c0); BuddyControlled = 0; BuddyHasAllSwitches = false; Bank = 1; ChanneltoSet = 3;
    for (int i = 0; i < 17; ++i) { InPutStick[i] = ChannelOutPut[i] = (uint8_t) i; } for (int i = 0; i < 4; ++i) InputTrim[i] = (uint8_t) i; outputChecks = 0;
    TxVoltageCorrection = 2; DeltaGMT = 1; PowerOffWarningSeconds = 2; ConnectionAssessSeconds = 1; ScanSensitivity = 42; MinimumGap = 75; LEDBrightness = 100; BackGroundSelection = 1; Qnh = 1009; UseLog = LogRXSwaps = false; LedWasGreen = true; txSetupStarts = 0;
    static const uint8_t b0[6] = { 0, 1, 2, 3, 32, 33 }, d0[8] = { 1, 2, 4, 0, 0, 0, 0, 0 }; memcpy(BanksInUse, b0, 6); memcpy(DualRateChannels, d0, 8); rateNamesShown = 0;
    memset(DualRateRate, 1, sizeof DualRateRate); ratesSet = 0; SingleModelFile[0] = 0; pageOverAfter = 0;
}
// ---- the screen's loop made to stand still at a chosen moment (from inside the wait that flies the model)
static bool planted = false, plantShout = false; static uint32_t plantStallMs = 0; static int plantAfterGets = 0; static const char *plantAfter = nullptr;
static void plantHook()
{
    if (planted || !plantStallMs) return;
    if (plantAfter)
    {   // ... when this get has gone out and the screen has not yet read it
        if (screen.cmds.size() < 2) return;
        const std::string &last = screen.cmds[screen.cmds.size() - 1].second, &prev = screen.cmds[screen.cmds.size() - 2].second;
        if (!(last == "sendme" && prev == plantAfter)) return;
        planted = true; screen.stall(nowUs, plantStallMs, plantShout);
    }
    else if (screen.gets >= plantAfterGets) { planted = true; screen.stall(nowUs + 1000, plantStallMs, plantShout); }   // ... or when so many boxes have been asked for
}
static uint64_t stallAtUs = 0; static uint32_t stallLenMs = 0;
static void stallWhenDue() { if (stallAtUs && nowUs >= stallAtUs) { screen.stall(nowUs, stallLenMs, true); stallAtUs = 0; } }
static const std::vector<uint8_t> POWER_ON = { 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x88, 0xFF, 0xFF, 0xFF };
static std::vector<uint8_t> bytes(const char *s) { return std::vector<uint8_t>(s, s + strlen(s)); }
static std::vector<uint8_t> glued(std::initializer_list<std::vector<uint8_t>> parts) { std::vector<uint8_t> v; for (auto &p : parts) v.insert(v.end(), p.begin(), p.end()); return v; }
static bool servosSane() { for (int i = 0; i < 11; ++i) if ((ServoFrequency[i] != 50 && ServoFrequency[i] != 333) || (ServoCentrePulse[i] != 1500 && ServoCentrePulse[i] != 760)) return false; return true; }
static bool mapsAsAtFirst() { for (int i = 0; i < 16; ++i) if (InPutStick[i] != i || ChannelOutPut[i] != i) return false; for (int i = 0; i < 4; ++i) if (InputTrim[i] != i) return false; return true; }
'''

SCENES_B = r'''
    // ================= 1. NO ANSWER IS NOT A NUMBER =================
    // (a) Servo types: OK, and 80 ms later a touch on one of the page's number boxes - the screen's keyboard comes up by itself, and
    //     the boxes still to be read have no answer. Nothing that is not a frequency or a pulse the page really held is stored - and
    //     (the twelfth review: a channel's frequency and centre pulse are a pair, the page's list is one change) the boxes read before it
    //     are NOT taken either: nothing is saved, nothing sent to the receiver, the page is not left, and the pilot is told once.
    more(); SendCommand((char *) "page ServosTypeView"); CurrentView = SERVOTYPESVIEW; loopFor(600);
    screen.pages["ServosTypeView"].boxes["n0"].val = 333; screen.pages["ServosTypeView"].boxes["n12"].val = 760;   // (typed: channel 1 at 333 Hz; channel 5's centre 760 us)
    tapAt(5, "OK"); tapAt(85, "n5box"); loopFor(4000);
    say("1a. Servo types, a number box touched 80 ms after OK: keyboards %d, boxes refused as off the page %d; frequencies", screen.keyboards, offPage); for (int i = 0; i < 11; ++i) say(" %u", (unsigned) ServoFrequency[i]);
    say("; centres"); for (int i = 0; i < 11; ++i) say(" %u", (unsigned) ServoCentrePulse[i]); say("; saved %d, told %d\n", (int) saves.size(), boxesLostTold);
    CHECK(screen.keyboards == 1 && servosSane() && boxesLostTold == 1 && BoxesLost > 0);
    CHECK(ServoFrequency[0] == 50 && ServoCentrePulse[4] == 1500);              // (it was: channel 1's 333 taken, saved and sent - half the page)
    CHECK(saves.empty() && queued.empty() && CurrentView == SERVOTYPESVIEW);     // nothing saved, nothing sent, the page not left
    //     ... and with nothing in the way, every box named in the change list is taken, saved and sent on; nobody is told anything
    more(); SendCommand((char *) "page ServosTypeView"); CurrentView = SERVOTYPESVIEW; loopFor(600);
    screen.pages["ServosTypeView"].boxes["n0"].val = 333; screen.pages["ServosTypeView"].boxes["n12"].val = 760;
    tapAt(5, "OK"); loopFor(4000);
    CHECK(ServoFrequency[0] == 333 && ServoCentrePulse[4] == 760 && saves.size() == 1 && queued.size() == 2 && boxesLostTold == 0 && screen.page == "FrontView");
    // (b) Buddy channels: OK with every box OFF on the page, and the screen does not say its page for one box (one "sendme" answer
    //     lost): no answer counted as "ticked" - the pupil had all switches, and the channels named in the change list
    more(); SendCommand((char *) "page BuddyChView"); CurrentView = BUDDYCHVIEW; loopFor(600); GetValue((char *) "fs2");   // (the screen has said its page once: from here an unsaid one is "no answer")
    screen.muteSendme = 1; tapAt(5, "OK"); loopFor(6000);
    say("1b. Buddy channels, one 'sendme' lost: all switches %d, mask 0x%04X, saved %d, told %d\n", (int) BuddyHasAllSwitches, (unsigned) BuddyControlled, (int) saves.size(), boxesLostTold);
    CHECK(!BuddyHasAllSwitches && BuddyControlled == 0 && saves.empty() && boxesLostTold == 1 && pageUnsaid == 1);
    more(); SendCommand((char *) "page BuddyChView"); CurrentView = BUDDYCHVIEW; loopFor(600);
    screen.pages["BuddyChView"].boxes["mSwitch"].val = 1; screen.pages["BuddyChView"].boxes["fs3"].val = 1; tapAt(5, "OK"); loopFor(6000);
    CHECK(BuddyHasAllSwitches && BuddyControlled == 0x0004 && saves.size() == 1 && boxesLostTold == 0);   // (ticked is ticked, as ever)
    // (c) the curve page's OK, "Copy to all banks" NOT ticked, one "sendme" lost: the curve went into every bank
    more(); memset(CurvePoint, 0, sizeof CurvePoint); for (int k = 0; k < CURVE_POINTS_MAX; ++k) { CurvePoint[1][2][k] = 10 + k; CurvePoint[2][2][k] = 90; CurvePoint[3][2][k] = 90; }
    SendCommand((char *) "page GraphView"); CurrentView = GRAPHVIEW; loopFor(600); GetValue((char *) "callfm");
    screen.muteSendme = 1; WriteNewCurve();
    CHECK(CurvePoint[2][2][0] == 90 && CurvePoint[2][2][1] == 90 && CurvePoint[3][2][0] == 90 && saves.size() == 1 && ChanneltoSet == 0);
    more(); memset(CurvePoint, 0, sizeof CurvePoint); for (int k = 0; k < CURVE_POINTS_MAX; ++k) { CurvePoint[1][2][k] = 10 + k; CurvePoint[2][2][k] = 90; }
    SendCommand((char *) "page GraphView"); CurrentView = GRAPHVIEW; loopFor(600); screen.pages["GraphView"].boxes["callfm"].val = 1; WriteNewCurve();
    CHECK(CurvePoint[2][2][0] == 10 && CurvePoint[2][2][1] == 11 && CurvePoint[4][2][8] == 18);   // (ticked: into every bank, as ever)
    // (d) Inputs: WHICH STICK DRIVES WHICH CHANNEL is taken whole or not at all. Five boxes in the change list; the fourth is not
    //     answered: nothing of the page is taken, nothing saved. All answered: all taken.
    more(); SendCommand((char *) "page InputsView"); CurrentView = INPUTS_VIEW; loopFor(600);
    { Page &p = screen.pages["InputsView"]; p.boxes["c1"].val = 2; p.boxes["c2"].val = 1; p.boxes["n4"].val = 3; p.boxes["n5"].val = 9; p.boxes["n0"].val = 2; }   // (typed: sticks 1 and 2 crossed, outputs moved, a trim moved)
    screen.mute.insert("n5"); tapAt(5, "OK"); loopFor(6000);
    say("1d. Inputs, the fourth box of five unanswered: maps as at first %d, saved %d, told %d, page %s\n", (int) mapsAsAtFirst(), (int) saves.size(), boxesLostTold, screen.page.c_str());
    CHECK(mapsAsAtFirst() && saves.empty() && outputChecks == 0 && boxesLostTold == 1 && screen.page == "RXSetupView");
    more(); SendCommand((char *) "page InputsView"); CurrentView = INPUTS_VIEW; loopFor(600);
    { Page &p = screen.pages["InputsView"]; p.boxes["c1"].val = 2; p.boxes["c2"].val = 1; p.boxes["n4"].val = 3; p.boxes["n5"].val = 9; p.boxes["n0"].val = 2; }
    tapAt(5, "OK"); loopFor(6000);
    CHECK(InPutStick[0] == 1 && InPutStick[1] == 0 && ChannelOutPut[0] == 2 && ChannelOutPut[1] == 8 && InputTrim[0] == 1 && InPutStick[2] == 2 && saves.size() == 1 && outputChecks == 1 && boxesLostTold == 0);
    // (e) the transmitter's third options page: every box with no answer went into its setting - the pressure at sea level 65535,
    //     and SENT TO THE RECEIVER; the log on; the gap 255. Here the third box (the pressure) is not answered: it and all behind
    //     it stay as they are; the two in front of it are taken
    more(); SendCommand((char *) "page OptionView3"); CurrentView = OPTIONVIEW3; loopFor(600);
    screen.mute.insert("Qnh"); tapAt(5, "OK"); loopFor(6000);
    say("1e. Options 3, the pressure's box unanswered: correction %d, warning %u s, Qnh %.0f, LED %u, assess %u, scan %u, gap %u, log %d/%d, told %d\n", (int) TxVoltageCorrection, (unsigned) PowerOffWarningSeconds, Qnh, (unsigned) LEDBrightness,
        (unsigned) ConnectionAssessSeconds, (unsigned) ScanSensitivity, (unsigned) MinimumGap, (int) UseLog, (int) LogRXSwaps, boxesLostTold);
    CHECK(TxVoltageCorrection == 5 && PowerOffWarningSeconds == 4 && Qnh == 1009 && ConnectionAssessSeconds == 1 && ScanSensitivity == 42 && MinimumGap == 75 && !UseLog && !LogRXSwaps && boxesLostTold == 1);
    more(); SendCommand((char *) "page OptionView3"); CurrentView = OPTIONVIEW3; loopFor(600); tapAt(5, "OK"); loopFor(6000);
    CHECK(TxVoltageCorrection == 5 && PowerOffWarningSeconds == 4 && Qnh == 1021 && ConnectionAssessSeconds == 3 && ScanSensitivity == 60 && MinimumGap == 90 && UseLog && LogRXSwaps && boxesLostTold == 0 && queued.size() == 2);
    //     ... the FIRST box unanswered: nothing of the page is taken
    more(); SendCommand((char *) "page OptionView3"); CurrentView = OPTIONVIEW3; loopFor(600); screen.mute.insert("t2"); tapAt(5, "OK"); loopFor(6000);
    CHECK(TxVoltageCorrection == 2 && PowerOffWarningSeconds == 2 && Qnh == 1009 && MinimumGap == 75 && !UseLog && boxesLostTold == 1);
    // (f) the time zone and the background's number: no answer is not one
    more(); SendCommand((char *) "page OptionView2"); CurrentView = OPTIONVIEW2; loopFor(600); screen.mute.insert("dGMT"); Options2End(); CHECK(DeltaGMT == 1);
    more(); SendCommand((char *) "page OptionView2"); CurrentView = OPTIONVIEW2; loopFor(600); Options2End(); CHECK(DeltaGMT == 2);
    more(); SendCommand((char *) "page ColoursView"); CurrentView = COLOURS_VIEW; loopFor(600); screen.mute.insert("n0"); Save_BackGround(); CHECK(BackGroundSelection == 1 && txSetupStarts == 1);
    more(); SendCommand((char *) "page ColoursView"); CurrentView = COLOURS_VIEW; loopFor(600); Save_BackGround(); CHECK(BackGroundSelection == 3);
    //     ... and a backup file's name: the pilot says Yes, the screen does not answer for the name - no name, nothing to be written
    //     (it was "", and a file of that name written)
    for (int lost = 0; lost < 2; ++lost)
    {
        more(); tapAt(5, "setup"); loopFor(800); tapAt(900, "yes"); if (lost) screen.mute.insert("t1");
        const bool go = GetBackupFilename((char *) "page RXOptionsView", (char *) "GOBLIN.MOD", (char *) "Goblin", (char *) "Backup", (char *) "File name");
        CHECK(Confirmed[0] == 'Y' && go == !lost && (lost ? SingleModelFile[0] == 0 : !strcmp(SingleModelFile, "GOBLIN.MOD")));
    }
    // (g) EVERY BOX WITH NO ANSWER IS COUNTED, whichever way it is asked and whyever it has none - and "the pilot is told" is said once
    //     for a button's work, however many boxes it lost: with THE FIRST of them by name (the tenth review: the name was written over
    //     at every box - the log named the last one that was not even asked, and "from there on" began nowhere)
    more(); tapAt(5, "setup"); loopFor(800);
    { const uint32_t c0 = BoxesLost; screen.mute.insert("n3"); CHECK(GetValue((char *) "n3") == 65535 && BoxesLost == c0 + 1 && !strcmp(BoxLostName, "n3"));
      char tx[20] = "x"; CHECK(GetText((char *) "t10", tx, sizeof tx) == 0 && BoxesLost == c0 + 2 && !strcmp(BoxLostName, "n3"));   // (not asked: the one before had no answer)
      CHECK(GetOtherValue((char *) "n4.val") == 0 && BoxesLost == c0 + 3 && !strcmp(BoxLostName, "n3"));
      CHECK(GetSysValue("sys0") == 65535 && BoxesLost == c0 + 3); }                // (a system variable is no page's box: not counted)
    more(); tapAt(5, "setup"); loopFor(800); screen.mute.insert("n4"); holdCatchUp = true;
    { const uint32_t c0 = BoxesLost; CHECK(GetOtherValue((char *) "n4.val") == 0 && BoxesLost == c0 + 1 && !strcmp(BoxLostName, "n4.val") && ScreenAnswerOwed); }   // (another attribute, itself the one with no answer)
    more(); tapAt(5, "setup"); loopFor(800); screen.mute.insert("t10"); holdCatchUp = true;
    { const uint32_t c0 = BoxesLost; char tx[20] = "x"; CHECK(GetText((char *) "t10", tx, sizeof tx) == 0 && BoxesLost == c0 + 1 && ScreenAnswerOwed); }             // (a text, itself the one with no answer - and owed)
    more(); tapAt(5, "setup"); loopFor(800);
    { const uint32_t c0 = BoxesLost; CHECK(GetValue((char *) "n3") == 5 && GetOtherValue((char *) "n4.val") == 6 && BoxesLost == c0);
      char tx[20] = "x"; CHECK(GetText((char *) "t10", tx, sizeof tx) == 4 && BoxesLost == c0); }
    more(); tapAt(5, "setup"); loopFor(800); screen.mute.insert("c1"); tapAt(5, "OK"); loopFor(4000); CHECK(boxesLostTold == 1 && count(obeyed, 39) == 1);   // (Model options' OK, its first box unanswered: told once)
    more(); tapAt(5, "setup"); loopFor(800); tapAt(5, "OK"); loopFor(4000); CHECK(boxesLostTold == 0 && count(obeyed, 39) == 1 && saves.size() == 1);
    // (h) MODEL OPTIONS AND THE ONE SWITCH PAGE ARE TAKEN WHOLE, OR NOT AT ALL (the ninth review). The motor-off value typed (1500 us)
    //     and the motor's channel typed with it: the channel's box has no answer - the value was taken without its channel. And a
    //     switch given the safety job, "Reversed" (read last) unanswered: the job was taken without its direction
    more(); tapAt(5, "setup"); loopFor(800); screen.pages["RXOptionsView"].boxes["n0"].val = 1500; screen.pages["RXOptionsView"].boxes["n1"].val = 7; screen.pages["RXOptionsView"].boxes["n3"].val = 9;
    screen.mute.insert("n1"); tapAt(5, "OK"); loopFor(4000); CHECK(count(obeyed, 39) == 1 && sameAsAtFirst() && boxesLostTold == 1);
    more(); tapAt(5, "setup"); loopFor(800); screen.pages["RXOptionsView"].boxes["n0"].val = 1500; screen.pages["RXOptionsView"].boxes["n1"].val = 7; screen.pages["RXOptionsView"].boxes["n3"].val = 9;
    tapAt(5, "OK"); loopFor(4000); CHECK(count(obeyed, 39) == 1 && MotorChannel == 6 && MotorChannelZero != 45 && TrimMultiplier == 9 && boxesLostTold == 0);
    //     ... EVERY box of Model options typed anew, and the LAST one asked for (six banks) with no answer: not one of the eleven settings read
    //     before it is taken (each has its keep) - and with every box answered, all of them are
    for (int lost = 1; lost >= 0; --lost)
    {
        more(); tapAt(5, "setup"); loopFor(800);
        { Page &p = screen.pages["RXOptionsView"]; p.boxes["c1"].val = 0; p.boxes["n3"].val = 9; p.boxes["t10"].txt = "3.70"; p.boxes["t12"].txt = "95"; p.boxes["n0"].val = 1500; p.boxes["n2"].val = 7;
          p.boxes["c0"].val = 0; p.boxes["n1"].val = 7; p.boxes["c2"].val = 0; p.boxes["n4"].val = 8; }
        if (lost) screen.mute.insert("c3");
        tapAt(5, "OK"); loopFor(6000);
        if (lost) CHECK(count(obeyed, 39) == 1 && sameAsAtFirst() && SFV == 350 && boxesLostTold == 1);
        else CHECK(count(obeyed, 39) == 1 && !CopyTrimsToAll && TrimMultiplier == 9 && StopFlyingVoltsPerCell > 3.69f && StopFlyingVoltsPerCell < 3.71f && Max_Safe_Amps == 95 && SFV == 370 && MotorChannelZero != 45
                       && RxVoltageCorrection == 7 && !UseMotorKill && MotorChannel == 6 && !TimerDownwards && TimerStartTime == 480 && boxesLostTold == 0);
    }
    more(); tapAt(5, "switch3"); loopFor(600); SwitchEditNumber = 2; screen.pages["OneSwitchView"].boxes["r7"].val = 1; screen.pages["OneSwitchView"].boxes["r2"].val = 0; screen.mute.insert("c_revd");
    tapAt(5, "OK"); loopFor(9000); CHECK(words.size() == 1 && switchesAsAtFirst() && SafetySwitch == 3 && Autoswitch == 2);
    more(); tapAt(5, "switch3"); loopFor(600); SwitchEditNumber = 2; screen.pages["OneSwitchView"].boxes["r7"].val = 1; screen.pages["OneSwitchView"].boxes["r2"].val = 0; screen.pages["OneSwitchView"].boxes["c_revd"].val = 1;
    tapAt(5, "OK"); loopFor(9000); CHECK(words.size() == 1 && SafetySwitch == 2 && Autoswitch == 0 && SwitchReversed[1]);   // (every box answering: the job and its direction, together)
    //     ... and what the real line for the log says (LogFiles.h NoteBoxesLost): once for each such work; short when it may fly
    more(); mayFly = false; strcpy(BoxLostName, "n12"); ++BoxesLost; real::NoteBoxesLost(); real::NoteBoxesLost();
    CHECK(logLines.size() == 1 && logLines[0].find("'n12'") != std::string::npos && logLines[0].find("NOT taken") != std::string::npos && soundsPlayed == 1);
    mayFly = true; ++BoxesLost; real::NoteBoxesLost(); CHECK(logLines.size() == 2 && logLines[1] == "(kept for later) Box unanswered: n12" && soundsPlayed == 2);
    //     ... (the thirteenth review, reviewer B's A6) and of a box that DID answer, with a text that is no number: the lines say THAT - "has no answer
    //     from the screen ... please look at it again" was said of it, and looking again does not help: the number wants typing again
    BoxLostNoNumber = true; strcpy(BoxLostName, "t10"); mayFly = false; ++BoxesLost; real::NoteBoxesLost();
    CHECK(logLines.size() == 3 && logLines[2].find("Box 't10' holds a text that is no number") == 0 && logLines[2].find("please type it again") != std::string::npos && logLines[2].find("no answer") == std::string::npos && soundsPlayed == 3);
    mayFly = true; ++BoxesLost; real::NoteBoxesLost(); CHECK(logLines.size() == 4 && logLines[3] == "(kept for later) Box holds no number: t10" && soundsPlayed == 4);
    BoxLostNoNumber = false; mayFly = false;
    //     ... and Nextion.h says which it was: a text that is no number marks the box so; a box with no answer does not (the first one lost names itself)
    more(); tapAt(5, "setup"); loopFor(800);
    { char tx[24] = "3.7p"; BoxesLostAtWork = BoxesLost; BoxLostNoNumber = false; NextionMissedNoNumber = false; NextionTextMissed = false;
      CHECK(!TextMustBeNumber("t10", tx) && BoxLostNoNumber && NextionMissedNoNumber && !strcmp(BoxLostName, "t10")); }
    more(); tapAt(5, "setup"); loopFor(800);
    { BoxesLostAtWork = BoxesLost; BoxLostNoNumber = true; NextionMissedNoNumber = false; screen.mute.insert("n3"); CHECK(GetValue((char *) "n3") == 65535); screen.mute.clear(); loopFor(1500);
      CHECK(!BoxLostNoNumber && !NextionMissedNoNumber && !strcmp(BoxLostName, "n3")); }

    // ================= 2. THE MOTOR SWITCH'S BOX, AND THE SCREEN'S RESTART =================
    // The link is lost with the motor switch on: the REAL EnsureMotorIsOff puts up "The motor switch is ON" (the REAL MsgBox, the REAL
    // GetYesOrNo) and stays until the switch is off. The screen dies 0.7 s after the box came up. The box was closed as "No" at once,
    // every time round - and noticed INSIDE a wait, nothing in that loop waits: 1451 rounds, the dog unfed for 5.8 s (2.5 s: the
    // Teensy restarts), the screen sent 25,000 commands. Now: the dog is fed, the rounds are few, nothing is put up until the screen
    // has caught up - then its front page is drawn afresh and the box comes back; the pilot switches off, presses OK, and it is over.
    for (int nested = 1; nested >= 0; --nested)
    {
        more(); BoundFlag = ModelMatched = true; tapAt(5, "setup"); loopFor(800);
        lastFeedUs = nowUs; maxUnfedUs = 0; dogWatch = true; const uint64_t t0 = nowUs; const int loads0 = screen.loads; nestedWaits = 0; boxSpins = 0;
        tapAt(700, "#restart"); motorOffAtUs = nowUs + 9000000; tapAt(12000, "yes");
        if (nested) { waitHook = LinkLostNow; NextionTextMissed = false; const uint32_t v = GetValue((char *) "n3"); CHECK(v == 65535 && NextionTextMissed); }   // (noticed inside a get's wait: that box has no answer)
        else LinkLostNow();
        dogLook(); dogWatch = false;
        say("2. the motor box and the screen's restart (%s): %ld rounds in %.1f s, the dog unfed %.2f s at most, questions closed %d, page commands the screen handled %d, in its queue %d, front pages afresh %d\n",
            nested ? "inside a wait" : "from the loop", motorChecks, (nowUs - t0) / 1e6, maxUnfedUs / 1e6, questionsClosed, screen.loads - loads0, (int) screen.cmds.size(), (int) frontReasons.size());
        CHECK(maxUnfedUs < 1300000 && motorChecks < 80 && !MotorEnabled && !ScreenRestartSeen && screen.restarts == 1 && warmups == 1);
        CHECK(frontReasons.size() == 2 && frontReasons[0].find("the screen restarted") == 0 && frontReasons[1] == "the box 'The motor switch is ON' is over");   // (each way to the front page is logged: the restart's, then the box's own - B172, and the tenth review)
        CHECK(questionsClosed >= 1 && Confirmed[0] == 'Y' && screen.page == "FrontView" && screen.loads - loads0 < 12 && screen.cmds.size() < 40 && nowUs - t0 > 11500000 && nowUs - t0 < 14600000);   // (inside a get's wait: that get then waits out its own two seconds - it has no answer)
        if (nested) CHECK(nestedWaits > 0);
    }
    //     ... and with the screen well, as ever: the box, the pilot's hand on the switch, OK
    more(); BoundFlag = ModelMatched = true; tapAt(5, "setup"); loopFor(800); motorOffAtUs = nowUs + 2000000; tapAt(3500, "yes"); LinkLostNow();
    CHECK(!MotorEnabled && motorChecks <= 3 && questionsClosed == 0 && screen.page == "FrontView");

    // ================= 3. A BOX INSIDE A BOX =================
    // A question waits ("Delete every model and all settings?"). The link is lost with the motor switch on: "The motor switch is ON
    // ... press OK" comes up from INSIDE the question's own wait. The pilot switches the motor off and presses that box's OK - which
    // was taken for the answer to the first question: YES. Now the first question is closed as "No": it was no longer on the screen.
    more(); tapAt(5, "setup"); loopFor(800); BoundFlag = ModelMatched = true; lostAtUs = nowUs + 1500000; sendDataHook = LinkLost;
    motorOffAtUs = nowUs + 3000000; tapAt(4000, "yes");
    { const bool answer = GetConfirmation((char *) "page RXOptionsView", (char *) "Delete every model and all settings?\r\nThis cannot be undone.");
      say("3. a box inside a box: the first question's answer %s; closed %d (%d of them because another page stood over it)\n", answer ? "YES" : "No", questionsClosed, questionsOvertaken);
      sendDataHook = nullptr;
      { const int g0 = screen.gets; CHECK(PageChangedUnderGet && GetValue((char *) "n3") == 65535 && screen.gets - g0 <= 2); }   // (... and the work that asked the question has no boxes any more: its page was taken away under it)
      CHECK(!answer && Confirmed[0] == 'N' && questionsOvertaken == 1 && ModalWaits == 0 && !MotorEnabled && QuestionClosedItself && QuestionOvertaken);
      loopFor(300); CHECK(screen.page == "FrontView" && CurrentView == FRONTVIEW); }   // (the ninth review: the motor box ends on the front page AS THIS BOARD'S PAGE, and the question
                                                                                //  it stood over does not send its own way back over it)
    //     ... a page put up over a question with NOTHING answered (what the power button's way to the front page did): the question
    //     does not wait on, unseen - it is closed at once
    more(); tapAt(5, "setup"); loopFor(800); SendCommand((char *) "page PopupView"); loopFor(300); pageOverAfter = 1500; powerButtonHook = PageOverQuestion;
    { const uint64_t t0 = nowUs; GetYesOrNo(); CHECK(Confirmed[0] == 'N' && questionsOvertaken == 1 && questionsClosed == 1 && nowUs - t0 < 1500000 && PageChangedUnderGet && ModalWaits == 0); }
    //     ... a question that nothing comes over is answered as ever (its own page command, and the one that takes it away, are its own)
    more(); tapAt(5, "setup"); loopFor(800); tapAt(900, "yes");
    CHECK(GetConfirmation((char *) "page RXOptionsView", (char *) "Save?") && questionsClosed == 0 && !PageChangedUnderGet);
    more(); tapAt(5, "setup"); loopFor(800); boxSpins = 399000;                  // (nobody answers: the test gives the box up, as 'T')
    CHECK(!GetConfirmation((char *) "page RXOptionsView", (char *) "Save?") && questionsClosed == 0);

    //     ... A QUESTION THAT NOBODY CAN ANSWER: the screen dies under the box and does not come back. In a question's wait the model
    //     is flown, but the switches are not read - it waited for the screen's first word (1.2 to 18 seconds on), or for ever. Now the
    //     screen is asked "which page?" once a second while a question waits, and one that has said nothing for three and a half
    //     seconds is not waited for: "No", the switches read again; what it was asked is owed
    more(); tapAt(5, "setup"); loopFor(800); BoundFlag = ModelMatched = true; GetValue((char *) "n4");   // (the screen has said its page: it is one that does)
    { SendCommand((char *) "page PopupView"); loopFor(300); screen.deaf = true; holdCatchUp = true; gapWatch = true; lastRadioUs = nowUs; lastFeedUs = nowUs; maxUnfedUs = 0; dogWatch = true;
      const uint64_t t0 = nowUs; GetYesOrNo(); dogLook();
      say("3b. a question under which the screen dies for good: closed after %.1f s as %c (silent %d), the radio's longest silence %.1f ms, the dog unfed %.2f s\n", (nowUs - t0) / 1e6, Confirmed[0], questionsSilent, radioGapUs() / 1e3, maxUnfedUs / 1e6);
      CHECK(Confirmed[0] == 'N' && questionsSilent == 1 && questionsClosed == 1 && nowUs - t0 > 3400000 && nowUs - t0 < 5000000 && ScreenAnswerOwed && ModalWaits == 0 && radioGapUs() < 60000 && maxUnfedUs < 1300000); }
    //     ... a screen that is well is asked, answers, and the question waits as long as the pilot likes (20 s here), then takes his Yes;
    //     and a screen that has never said its page (an older one) is not judged by its silence
    more(); tapAt(5, "setup"); loopFor(800); GetValue((char *) "n4"); SendCommand((char *) "page PopupView"); loopFor(300); boxSpins = -100000; tapAt(20000, "yes");
    { const int said0 = ScreenPageSaidCount; const uint64_t t0 = nowUs; GetYesOrNo(); CHECK(Confirmed[0] == 'Y' && questionsClosed == 0 && nowUs - t0 > 19000000 && ScreenPageSaidCount - said0 >= 15 && !ScreenAnswerOwed); }
    more(); tapAt(5, "setup"); loopFor(800); SendCommand((char *) "page PopupView"); loopFor(300); ScreenSaysPage = false; screen.knowsSendme = false; boxSpins = 380000;
    { const uint64_t t0 = nowUs; GetYesOrNo(); CHECK(Confirmed[0] == 'T' && questionsClosed == 0 && nowUs - t0 > 8000000); }   // (given up by the test itself, ten seconds on: not by the silence)

    // ================= 4. A PAGE COMMAND FROM INSIDE A WAIT THAT IS NO GET'S =================
    // (a) "Listen" on the Bank names page: a box read, a sound, a wait of 1.2 s - six times. The power button is pressed while
    //     connected during the second wait: the front page comes up from inside it (no get is pending), and the four boxes read
    //     afterwards were answered by the FRONT page - whose number was "the last page command's". Now they have no answer.
    //     (The twelfth review: "Listen" itself no longer waits - 4a2. The rule is Nextion.h's, for every such routine: the scene keeps the old shape as its own.)
    more(); SendCommand((char *) "page BankNameView"); CurrentView = 77; loopFor(600); BoundFlag = ModelMatched = true;
    powerAtWait = 2; flyHook = PowerButtonInWait; { const int off0 = screen.offPageAnswers; const int g0 = screen.gets; ListenAsItWas(); flyHook = nullptr;
      say("4a. Listen, the power button in the second wait: names"); for (int i = 0; i < 6; ++i) say(" %u", (unsigned) BanksInUse[i]); say("; answered off the page %d, asked %d\n", screen.offPageAnswers - off0, screen.gets - g0);
      CHECK(BanksInUse[0] == 11 && BanksInUse[1] == 12 && BanksInUse[2] == 2 && BanksInUse[3] == 3 && BanksInUse[4] == 32 && BanksInUse[5] == 33 && screen.offPageAnswers == off0 && screen.gets - g0 == 4 && PageChangedUnderGet); }   // (asked: two boxes, and the front page's two markers - no box after it)
    loopFor(5); CHECK(!PageChangedUnderGet);                                     // (the main loop's next look for a press: that work is over)
    // (a2) "LISTEN" AS IT IS NOW (the twelfth review; released code waited 1.2 s behind every name - seven seconds in which no switch was read): the six names
    //      are taken whole, the button's work is over in the time of its six questions, and the names are said by the main loop, 1.2 s apart
    more(); SendCommand((char *) "page BankNameView"); CurrentView = BANKSNAMESVIEW; loopFor(600); BoundFlag = ModelMatched = true;
    { const uint64_t t0 = nowUs; const int s0 = soundsPlayed; BoxesLostAtWork = BoxesLost; ListenToBanks();
      const uint32_t took = (uint32_t) ((nowUs - t0) / 1000);
      CHECK(BanksInUse[0] == 11 && BanksInUse[1] == 12 && BanksInUse[5] == 16 && soundsPlayed == s0 && took < 700);
      int said[10]; for (int s = 0; s < 10; ++s) { for (int k = 0; k < 1000; ++k) { BankListenPoll(); nowUs += 1000; } said[s] = soundsPlayed - s0; }
      say("4a2. Listen: the button's work took %u ms; names said by the main loop after 1..10 s: %d %d %d %d %d %d %d ... %d\n", (unsigned) took, said[0], said[1], said[2], said[3], said[4], said[5], said[6], said[9]);
      CHECK(said[0] == 1 && said[1] == 2 && said[2] == 3 && said[4] == 5 && said[6] == 6 && said[9] == 6); }   // (the first at once, then one every 1.2 s; six, and no more)
    //      ... a name with no answer: NOTHING is taken and nothing said
    { static const uint8_t b0[6] = { 0, 1, 2, 3, 32, 33 }; memcpy(BanksInUse, b0, 6); const int s0 = soundsPlayed; screen.mute.insert("BK4"); BoxesLostAtWork = BoxesLost; ListenToBanks(); screen.mute.clear();
      for (int k = 0; k < 3000; ++k) { BankListenPoll(); nowUs += 1000; }
      CHECK(!memcmp(BanksInUse, b0, 6) && soundsPlayed == s0); loopFor(3000); }
    //      ... and the page left while the names are being said: no more
    { const int s0 = soundsPlayed; BoxesLostAtWork = BoxesLost; ListenToBanks(); for (int k = 0; k < 1500; ++k) { BankListenPoll(); nowUs += 1000; } const int said = soundsPlayed - s0;
      CurrentView = 99; for (int k = 0; k < 6000; ++k) { BankListenPoll(); nowUs += 1000; }
      CHECK(said == 2 && soundsPlayed - s0 == 2); CurrentView = BANKSNAMESVIEW; }
    // (b) a Rotorflight page's Save as RF_PIDs.h has it - "Sending ..." on the page, a wait of 100 ms, THEN the look before its boxes
    //     and the boxes: the power button in those 100 ms. Nine zeros were "sent"; now nothing is asked, and the save is refused
    more(); for (int i = 0; i < 9; ++i) { char n[8]; snprintf(n, sizeof n, "pid%d", i); screen.pages["RXOptionsView"].boxes[n] = { false, 40 + i, "" }; }
    tapAt(5, "setup"); loopFor(800); BoundFlag = ModelMatched = true; powerAtWait = 1; flyHook = PowerButtonInWait;
    { const int off0 = screen.offPageAnswers, g0 = screen.gets; uint32_t pid[9]; const uint64_t t0 = nowUs;
      SendText((char *) "change", (char *) "Sending edited PIDs ..."); DelayWithDog(100); RfGatherStart();
      for (int i = 0; i < 9; ++i) { char n[8]; snprintf(n, sizeof n, "pid%d", i); pid[i] = GetValue(n); } flyHook = nullptr;
      CHECK(NextionTextMissed && pid[0] == 65535 && pid[8] == 65535 && screen.offPageAnswers == off0 && screen.gets - g0 == 2 && !NextionSettledOk && nowUs - t0 < 400000); }   // (asked: the front page's two markers, and not one box)
    // (c) the page's own commands change nothing of this: a page command sent by the button's work itself (not from inside a wait),
    //     and the boxes of the page it put up are read
    more(); tapAt(5, "setup"); loopFor(800); SendCommand((char *) "page RXOptionsView"); OptionsBoxes(); CHECK(!PageChangedUnderGet && GetValue((char *) "n3") == 5);
    //     ... and a question's own look for its answer does not un-void the boxes of the work it belongs to
    more(); tapAt(5, "setup"); loopFor(800); PageChangedUnderGet = true; ModalWaits = 1; GetButtonPress(); CHECK(PageChangedUnderGet); ModalWaits = 0;
    InsideDelayWithDog = true; GetButtonPress(); CHECK(PageChangedUnderGet); InsideDelayWithDog = false; GetButtonPress(); CHECK(!PageChangedUnderGet);
'''

SCENES_A = r'''
    // ================= 5. EVERY SIGN OF THE SCREEN'S RESTART LOST =================
    // The Models page; the screen restarts and says neither its power-on bytes nor its word (with and without its chip's own text;
    // a start of 1.2 s and of 6 s). The page's own look at its lists, twice a second, was answered by the page as the card has it
    // - row 0 - and MODEL 1 WAS LOADED BY ITSELF. Now, before another model is loaded for a row that changed with no press, the
    // screen is asked for the last marker it was told: it has forgotten it. Found (reason -3), the front page afresh, no model loaded.
    for (int garbage = 0; garbage < 2; ++garbage)
        for (uint64_t boot : { 1200000ull, 6000000ull })
        {
            more(); screen.restartReason = 5; screen.bootRecord = ""; screen.powerOnUs = boot; screen.restartPowerOnBytes = false; screen.restartSaysWord = false;
            if (garbage) screen.prelude = chipStart(5);
            tapAt(5, "models"); loopForModels(2000); tapAt(130, "#restart"); loopForModels((uint32_t) (boot / 1000) + 12000);
            say("5. every sign lost (%s, a start of %.1f s): model %u, loaded by themselves %d, restart answered %d (reason %d), owed caught up %d, page %s\n", garbage ? "chip text" : "silence", boot / 1e6, (unsigned) ModelNumber, (int) modelsRead.size(), restartsHandled, lastRestartReason, owedCaughtUp, screen.page.c_str());
            CHECK(ModelNumber == 4 && modelsRead.empty() && screen.restarts == 1 && restartsHandled == 1 && lastRestartReason == -3 && CurrentView == FRONTVIEW && screen.page == "FrontView" && !ScreenRestartSeen && !ScreenAnswerOwed);
            CHECK(frontReasons.size() == 1 && frontReasons[0].find("rst=-3") != std::string::npos && frontReasons[0].find("found by asking") != std::string::npos);
        }
    //     ... and the pilot's own turn of the list - the same screen - loads the model as ever, with one more question asked
    more(); tapAt(5, "models"); loopForModels(2000); screen.pages["ModelsView"].boxes["MMems"].val = 5; loopForModels(1500);
    CHECK(modelsRead.size() == 1 && modelsRead[0] == 6 && ModelNumber == 6 && restartsHandled == 0 && !ScreenRestartSeen && CurrentView == MODELSVIEW);
    //     ... not while the page's own marker is still awaited (the page may not be up); and a screen that says no markers (older
    //     than them) cannot be asked: with it, as it always was
    more(); tapAt(5, "models"); loopForModels(2000); screen.pages["ModelsView"].boxes["MMems"].val = 5; ScreenMarkAwaited = 1; CheckModelName(); CHECK(modelsRead.empty()); ScreenMarkAwaited = 0; CheckModelName(); CHECK(modelsRead.size() == 1);
    more(); tapAt(5, "models"); loopForModels(2000); screen.pages["ModelsView"].boxes["MMems"].val = 5; ScreenMarkMisses = SCREEN_MARK_MISSES; { const int g0 = screen.gets; CheckModelName(); CHECK(modelsRead.size() == 1 && screen.gets - g0 == 2); }
    //     ... A PAGE LOOKS AT ITS OWN BOXES ONLY WHILE THE SCREEN'S PAGE IS ITS OWN (the ninth review: a box had gone back to the front page
    //     with a bare page command, this board still believed the Models page - the front page's "0" for the list's row loaded model 1)
    more(); tapAt(5, "models"); loopForModels(2000); screen.pages["ModelsView"].boxes["MMems"].val = 5; ScreenPageId = 13;
    { const int g0 = screen.gets; CheckModelName(); CHECK(modelsRead.empty() && ModelNumber == 4 && screen.gets == g0); ScreenPageId = SCREEN_MODELS_PAGE; CheckModelName(); CHECK(modelsRead.size() == 1 && modelsRead[0] == 6); }
    more(); SendCommand((char *) "page DualRatesView"); CurrentView = DUALRATESVIEW; loopFor(600);
    { static uint32_t pollMs = 500000; screen.pages["DualRatesView"].boxes["n2"].val = 7; ScreenPageId = 13; pollMs += 700; CheckDualRatesScreen(pollMs); CHECK(DualRateChannels[0] == 1 && rateNamesShown == 0);
      ScreenPageId = SCREEN_DUALRATES_PAGE; pollMs += 700; CheckDualRatesScreen(pollMs); CHECK(DualRateChannels[0] == 7 && rateNamesShown == 1); }
    //     ... the question itself: the same screen (0), one that has forgotten (1: its restart is noted), one that does not answer
    //     (2: and its answer is owed - nothing is asked until it has caught up)
    more(); tapAt(5, "setup"); loopFor(800); CHECK(ScreenSessionCheck() == 0 && !ScreenRestartSeen && !ScreenAnswerOwed);
    //     (the ninth review: one that has forgotten is not called "restarted" by the question itself - it says "nothing is known", and the
    //      "say this back" that follows decides: the number said back twice and the session's not = it HAS started again, the front page afresh)
    more(); tapAt(5, "setup"); loopFor(800); CHECK(ScreenSaidSession && ScreenSessionSaidN >= 1);
    screen.sys.clear(); holdCatchUp = true; CHECK(ScreenSessionCheck() == 2 && !ScreenRestartSeen && ScreenAnswerOwed);
    holdCatchUp = false; loopFor(300); CHECK(restartsFoundByAsking == 1 && restartsHandled == 1 && lastRestartReason == -3 && !ScreenRestartSeen && !ScreenAnswerOwed && CurrentView == FRONTVIEW && ScreenSaidSession);
    //     ... A PAGE COMMAND OF THIS BOARD'S AFTER THE UNNOTICED RESTART tells the screen its page markers anew - not its session's number
    //     (the ninth review: the last PAGE MARKER was asked for, and the screen saver's own page command made the screen "the same" again)
    more(); tapAt(5, "setup"); loopFor(800); screen.sys.clear(); SendCommand((char *) "page RXOptionsView"); loopFor(600);
    CHECK(!ScreenMarkAwaited && screen.sys.count("ldrcsync") && !screen.sys.count("ldrcup") && ScreenSessionCheck() == 2); loopFor(300); CHECK(restartsFoundByAsking == 1 && restartsHandled == 1 && lastRestartReason == -3);
    //     ... the reviewer's own run: the Models page; the screen saver blanks it; the screen restarts and every sign is lost; a touch wakes the
    //     screen saver, which puts the Models page back as the screen "remembers" it - a restarted screen has the card's: row 0. MODEL 1 WAS LOADED
    more(); screen.restartPowerOnBytes = false; screen.restartSaysWord = false; screen.restartReason = 5;
    { Page blank; blank.id = 55; screen.pages["BlankView"] = blank; screen.pages0["BlankView"] = blank; }
    tapAt(5, "models"); loopForModels(2000); SendCommand((char *) "page BlankView"); CurrentView = 0; loopFor(500);
    tapAt(5, "#restart"); loopFor(6000); CHECK(!ScreenRestartSeen && restartsHandled == 0);                 // (no sign reached this board)
    SendCommand((char *) "page ModelsView"); CurrentView = MODELSVIEW; loopForModels(3000);
    CHECK(ModelNumber == 4 && modelsRead.empty() && restartsFoundByAsking == 1 && restartsHandled == 1 && lastRestartReason == -3 && CurrentView == FRONTVIEW);
    //     ... and ONE lost answer does not make a restart: the session's number unanswered once (the "say this back" came), then said
    more(); tapAt(5, "setup"); loopFor(800); CHECK(ScreenSaidSession);
    { static int n; n = 0; static long kept; kept = screen.sys["ldrcup"]; screen.sys.erase("ldrcup");               // (the first asking is answered 0 - as if that one answer had been lost ...)
      flyHook = [] { if (ScreenSessionUnsaid == 1 && !screen.sys.count("ldrcup")) screen.sys["ldrcup"] = kept; };   // (... and the second finds the number there)
      ScreenAnswerOwed = true; ScreenOwedSinceMs = millis(); ScreenEchoToldMs = 0; ScreenSaidEcho = false;
      for (int i = 0; i < 400 && ScreenAnswerOwed; ++i) { flyHook(); loopFor(1); }
      flyHook = nullptr; CHECK(!ScreenAnswerOwed && restartsFoundByAsking == 0 && restartsHandled == 0 && !ScreenRestartSeen && owedCaughtUp == 1 && ScreenSessionUnsaid == 0); }
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true; gapWatch = true; lastRadioUs = nowUs;
    { const uint64_t t0 = nowUs; CHECK(ScreenSessionCheck() == 2 && !ScreenRestartSeen && ScreenAnswerOwed && nowUs - t0 < 800000 && radioGapUs() < 60000); }
    //     ... (the thirteenth review: no scene held it) THE WIRE IS READ BEFORE THE QUESTION IS ASKED: a restart's sign standing there unread - the screen's
    //     power-on bytes - is noted, and NOTHING IS ASKED of a screen that has only just started (1, at once; its answer, come later, would be nobody's)
    more(); tapAt(5, "setup"); loopFor(800); holdCatchUp = true;
    { screen.emit(nowUs, { 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x88, 0xFF, 0xFF, 0xFF }); nowUs += 2000;
      const size_t said0 = screen.log.size(); const uint64_t t0 = nowUs; const uint8_t answer = ScreenSessionCheck(); const uint64_t took = nowUs - t0;
      nowUs += 100000; screen.run(nowUs); bool asked = false; for (size_t i = said0; i < screen.log.size(); ++i) asked |= screen.log[i].find("ldrcup") != std::string::npos;
      say("9c. the screen's power-on bytes unread on the wire, 'is it the same screen?': answer %u after %.1f ms, the screen asked %d\n", (unsigned) answer, took / 1e3, (int) asked);
      CHECK(answer == 1 && ScreenRestartSeen && took < 5000 && !asked); }
    //     ... a page command sent from INSIDE the asking (a box put up when the link is lost, and back - the reviewer's own run) says nothing
    //     against the screen: "nothing is known" this time (the page is not the one asked about) - never "it has started again", and nothing owed
    more(); tapAt(5, "setup"); loopFor(800); holdCatchUp = true;
    waitHook = [] { SendCommand((char *) "page PopupView"); SendCommand((char *) "page RXOptionsView"); };
    CHECK(ScreenSessionCheck() == 2 && !ScreenRestartSeen && !ScreenAnswerOwed && restartsFoundByAsking == 0);
    holdCatchUp = false; loopFor(600); CHECK(ScreenSessionCheck() == 0 && restartsHandled == 0);
    //     ... a screen that has not yet said its session's number (this board has just started) is not "the same" yet: nothing is known. One that
    //     never says it (told ten times) cannot be asked: with it, as it always was
    more(); tapAt(5, "setup"); loopFor(800); ScreenSaidSession = false; ScreenSessionTries = 1; holdCatchUp = true; CHECK(ScreenSessionCheck() == 2 && !ScreenAnswerOwed);
    ScreenSessionTries = SCREEN_SESSION_TRIES; CHECK(ScreenSessionCheck() == 0);
    //     ... THE HALF MINUTE of a screen that cannot say a number back is counted from the LAST sign of its restart (a second start,
    //     25 s after the first, was given five seconds)
    more(); screen.knowsSysGet = false; tapAt(5, "#restart"); loopFor(25000); CHECK(ScreenRestartSeen && restartsHandled == 0);
    tapAt(5, "#restart"); loopFor(20000); CHECK(screen.restarts == 2 && ScreenRestartSeen && restartsHandled == 0);
    loopFor(15000); CHECK(restartsHandled == 1 && !ScreenRestartSeen);
    //     ... the Dual-rates page's own look at its boxes (every 600 ms): a box that changed with no press is taken from the same
    //     screen only
    more(); SendCommand((char *) "page DualRatesView"); CurrentView = DUALRATESVIEW; loopFor(600);
    { static uint32_t pollMs = 100000; screen.pages["DualRatesView"].boxes["n2"].val = 7; pollMs += 700; CheckDualRatesScreen(pollMs); CHECK(DualRateChannels[0] == 7 && rateNamesShown == 1);   // (the pilot's own)
      screen.sys.clear(); screen.pages["DualRatesView"].boxes["n0"].val = 9; holdCatchUp = true; pollMs += 700; CheckDualRatesScreen(pollMs);                                                    // (a screen that has forgotten: the card's)
      CHECK(DualRateChannels[1] == 2 && rateNamesShown == 1 && !ScreenRestartSeen && ScreenAnswerOwed);
      holdCatchUp = false; loopFor(300); CHECK(DualRateChannels[1] == 2 && restartsFoundByAsking == 1 && restartsHandled == 1 && lastRestartReason == -3); }

    //     ... and the rate chosen on that page (looked at when the bank changes): another rate in the box with no press is believed
    //     from the same screen only
    more(); SendCommand((char *) "page DualRatesView"); CurrentView = DUALRATESVIEW; loopFor(600); Bank = 1;
    CheckSelectedRatesMode(); { const int first = ratesSet; screen.pages["DualRatesView"].boxes["rate"].val = 2; CheckSelectedRatesMode(); CHECK(ratesSet == first + 1 && DualRateRate[0] == 2);   // (the pilot's own)
      screen.sys.clear(); screen.pages["DualRatesView"].boxes["rate"].val = 3; holdCatchUp = true; CheckSelectedRatesMode(); CHECK(ratesSet == first + 1 && DualRateRate[0] == 2 && !ScreenRestartSeen && ScreenAnswerOwed);
      holdCatchUp = false; loopFor(300); CHECK(ratesSet == first + 1 && DualRateRate[0] == 2 && restartsFoundByAsking == 1 && lastRestartReason == -3); }

    // ================= 6. AN ANSWER THAT NEVER CAME MAY COME YET =================
    // The Models page asks for its two lists twice a second. The screen's loop stands still for longer than a question's two seconds
    // (no restart: nothing says so) and then answers everything it was asked, in order: the answer nobody waits for any more was the
    // next question's - the files' row taken for the model's: a model loaded by itself. Now an answer not come in its time is OWED,
    // and nothing is asked until the screen has caught up. (a) the stall begins with "get Mfiles.val" gone and unread, (b) with
    // "get MMems.val"; 1.5, 2.3 and 4.5 s
    for (const char *after : { "get Mfiles.val", "get MMems.val" })
        for (uint32_t stallMs : { 1500u, 2300u, 4500u })
        {
            more(); tapAt(5, "models"); loopForModels(2000);
            planted = false; plantShout = true; plantStallMs = stallMs; plantAfter = after; flyHook = plantHook; loopForModels(stallMs + 4000); flyHook = nullptr; plantAfter = nullptr;
            say("6. a stall of %u ms from '%s': model %u, read from the card %d, file row %u, owed caught up %d, shouts %d\n", stallMs, after, (unsigned) ModelNumber, (int) modelsRead.size(), (unsigned) FileNumberInView, owedCaughtUp, screen.shouts);
            CHECK(planted && ModelNumber == 4 && modelsRead.empty() && FileNumberInView == 2 && !ScreenRestartSeen && restartsHandled == 0 && !ScreenAnswerOwed && CurrentView == MODELSVIEW);
            if (stallMs > 2200) CHECK(owedCaughtUp >= 1);
        }
    //     (c) stalls of 2.1 to 6 s that begin at a random moment (nothing aimed): never a model loaded by itself, never the files'
    //     row moved (288 loads in 3000 such stalls, before)
    {
        uint32_t seed = 4711; auto rnd = [&](uint32_t n) { seed = seed * 1664525u + 1013904223u; return (seed >> 8) % n; };
        int loaded = 0, fileMoved = 0, restartsSeen = 0, caught = 0;
        for (int i = 0; i < 500; ++i)
        {
            more(); screen.latencyUs = 300 + rnd(4000); tapAt(5, "models"); loopForModels(1500 + rnd(700));
            stallAtUs = nowUs + rnd(600000); stallLenMs = 2100 + rnd(3900); flyHook = stallWhenDue;
            const uint64_t until = nowUs + (uint64_t) stallLenMs * 1000 + 5000000ull; bool moved = false;
            while (nowUs < until) { stallWhenDue(); loopForModels(3); if (FileNumberInView != 2) moved = true; }
            flyHook = nullptr; if (!modelsRead.empty() || ModelNumber != 4) ++loaded; if (moved) ++fileMoved; restartsSeen += restartsHandled; caught += owedCaughtUp;
            if (show && (!modelsRead.empty() || moved)) { printf("   6c, trial %d (a stall of %u ms): model %u, file row moved %d\n", i, stallLenMs, (unsigned) ModelNumber, (int) moved); for (auto &l : story) printf("      %s\n", l.c_str()); }
        }
        say("6c. 500 stalls of 2.1-6 s at random moments on the Models page: a model loaded by itself %d times, the files' row moved %d times, restarts 'found' %d, owed answers caught up with %d\n", loaded, fileMoved, restartsSeen, caught);
        CHECK(loaded == 0 && fileMoved == 0 && restartsSeen == 0 && caught > 300);
    }
    //     (d) what "owed" does: after an answer that never came NOTHING is asked - a box, a system variable - until the screen has
    //     said back the number it was then told; then all is asked again. A screen older than the markers cannot say one: with it, as before.
    more(); tapAt(5, "setup"); loopFor(800); screen.mute.insert("n3"); holdCatchUp = true;
    CHECK(GetValue((char *) "n3") == 65535 && ScreenAnswerOwed && ScreenEchoToldMs == 0 && !ScreenSaidEcho);
    { const int g0 = screen.gets; PageChangedUnderGet = false; CHECK(GetSysValue("sys0") == 65535 && GetValue((char *) "n4") == 65535 && GetOtherValue((char *) "n4.val") == 0 && screen.gets == g0 && ScreenSessionCheck() == 2);
      char tx[20] = "x"; CHECK(GetText((char *) "t10", tx, sizeof tx) == 0 && screen.gets == g0); RfGatherStart(); CHECK(screen.gets == g0 && !NextionSettledOk); }
    holdCatchUp = false; loopFor(200); CHECK(!ScreenAnswerOwed && owedCaughtUp == 1 && restartsHandled == 0 && ScreenSaidSession && GetValue((char *) "n4") == 6);
    more(); tapAt(5, "setup"); loopFor(800); screen.mute.insert("n3"); ScreenMarkMisses = SCREEN_MARK_MISSES; CHECK(GetValue((char *) "n3") == 65535 && !ScreenAnswerOwed);
    //     ... "caught up" is said of THIS debt: a number the screen said back for an earlier one (after its restart, say) does not pay it
    more(); tapAt(5, "setup"); loopFor(800); tapAt(5, "#restart"); loopFor(9000); CHECK(restartsHandled == 1 && ScreenSaidSession);
    tapAt(5, "setup"); loopFor(800); screen.deaf = true; CHECK(GetValue((char *) "n3") == 65535 && ScreenAnswerOwed && !ScreenSaidEcho && ScreenSaidSession);   // (its session's number stays said: it is the other number that pays)
    loopFor(1500); CHECK(ScreenAnswerOwed && owedCaughtUp == 0);                    // (a screen that hears nothing has not caught up)
    //     ... the page's number that never came is owed too (come late, it would say "the page was right" of another moment);
    //     and so is a Rotorflight page's look before its boxes
    more(); tapAt(5, "setup"); loopFor(800); GetValue((char *) "n4"); screen.muteSendme = 1; holdCatchUp = true; CHECK(GetValue((char *) "n3") == 65535 && ScreenAnswerOwed && pageUnsaid == 1);
    more(); tapAt(5, "setup"); loopFor(800); GetValue((char *) "n4"); screen.muteSendme = 1; holdCatchUp = true; RfGatherStart(); CHECK(!NextionSettledOk && ScreenAnswerOwed);
    //     ... and a button pressed while an answer is owed: its boxes have no answer, nothing is saved from them, the pilot is told
    more(); tapAt(5, "setup"); loopFor(800); screen.pages["RXOptionsView"].boxes["n3"].val = 9; ScreenAnswerOwed = true; ScreenOwedSinceMs = millis(); holdCatchUp = true;
    tapAt(5, "OK"); loopFor(3000); CHECK(count(obeyed, 39) == 1 && TrimMultiplier == 5 && sameAsAtFirst() && boxesLostTold == 1);
    //     ... A SYSTEM VARIABLE asked for while a page command goes out from inside its wait (a box put up by the link's loss): that
    //     box's own looks for a press read the wire - whatever stands there afterwards is not known to be this answer
    more(); tapAt(5, "setup"); loopFor(800); screen.sys["sys0"] = 1; holdCatchUp = true;
    waitHook = [] { SendCommand((char *) "page PopupView"); }; CHECK(GetSysValue("sys0") == 65535 && !ScreenAnswerOwed);   // (the answer came; it is not known to be this one: no answer, nothing owed)
    more(); tapAt(5, "setup"); loopFor(800); screen.sys["sys0"] = 1; CHECK(GetSysValue("sys0") == 1);
    //     (e) A LATE TEXT ANSWER IS A TEXT ANSWER, whatever letters it holds: "Seq 100" met in a number box's wait ended in q and
    //     four bytes - handed back as the number 808464672
    more(); tapAt(5, "setup"); loopFor(800); screen.mute.insert("n3"); holdCatchUp = true;
    screen.emit(nowUs + 70000, glued({ bytes("pSeq 100"), { 0xFF, 0xFF, 0xFF } })); CHECK(GetValue((char *) "n3") == 65535);

    // ================= 7. THE SCREEN'S SHOUT, in front of the very answer its silence made late =================
    // Model options: six boxes typed, OK. The screen's loop stands still for 300 ms while the third box (a text) is asked, and its
    // other core says so: "LDRCLOG core 1 (the loop's) silent for 213 ms ..." - bare, no end. The answer came behind that line,
    // glued to it, and was lost ("MISSING after 2000 ms") - and with it every box after it. A word that has stood quiet for 2 ms is
    // over (the eighth review) - a NUMBER behind it is read. But a TEXT behind a word with no end is not believed (the ninth: it may
    // be that word's second half with the answer glued to it): for half a second no text has an answer - nothing of the page is
    // taken, the pilot is told, and his next OK saves it. A screen from 1.11.198 on says its line in one piece with a newline at its
    // end - and that is the SAME to this board now (15 Nov 2026: "ends with a newline" was taken from the bytes, and a reply's own byte 0A behind
    // a field screen's line made such an end - scene 9d below): the line that comes inside the text box's own wait costs that box on either screen.
    for (int form : { 197, 198 })
        for (int shout = 0; shout < 2; ++shout)
            for (uint32_t stallMs : { 0u, 300u, 900u })
            {
                more(); if (form == 198) { screen.realUart = true; screen.shoutForm = 198; } tapAt(5, "setup"); loopFor(800);
                { Page &p = screen.pages["RXOptionsView"]; p.boxes["n3"].val = 9; p.boxes["t10"].txt = "3.70"; p.boxes["t12"].txt = "95"; p.boxes["n1"].val = 7; p.boxes["n4"].val = 8; p.boxes["c0"].val = 0; }
                planted = false; plantShout = shout != 0; plantStallMs = stallMs; plantAfterGets = screen.gets + 2; plantAfter = nullptr; flyHook = plantHook;
                tapAt(5, "OK"); loopFor(6000); flyHook = nullptr;
                say("7. Model options' OK (a screen of 1.11.%d), a stall of %u ms%s: saves %d, trim step %u, stop flying %.2f, most amps %d, motor channel %u, timer %u s, motor switch %d; missing %d; not believed %d; log lines from the screen %d\n", form, stallMs, shout ? " with the shout" : "",
                    (int) saves.size(), (unsigned) TrimMultiplier, StopFlyingVoltsPerCell, Max_Safe_Amps, (unsigned) MotorChannel, (unsigned) TimerStartTime, (int) UseMotorKill, (int) lateReplies.size(), textDoubted, (int) screenLogLines.size());
                const bool typed = TrimMultiplier == 9 && StopFlyingVoltsPerCell > 3.69f && StopFlyingVoltsPerCell < 3.71f && Max_Safe_Amps == 95 && MotorChannel == 6 && TimerStartTime == 480 && !UseMotorKill;
                if (shout && stallMs)
                {   // the text's answer 85 ms behind a line with no end: not believed - nothing taken, the pilot told; and his next OK saves what he typed.
                    // (The tenth review: and 685 ms behind it, the same. The line came INSIDE this text box's own wait: a word that opens during a
                    //  wait is open for all of it - half a second is a time, not a bound, and nothing says when the line's rest has come)
                    CHECK(saves.size() == 1 && sameAsAtFirst() && boxesLostTold == 1 && textDoubted == 1 && screen.page == "FrontView" && !ScreenAnswerOwed);   // (saved as it WAS; the front page; told)
                    tapAt(5, "setup"); loopFor(800);
                    { Page &p = screen.pages["RXOptionsView"]; p.boxes["n3"].val = 9; p.boxes["t10"].txt = "3.70"; p.boxes["t12"].txt = "95"; p.boxes["n1"].val = 7; p.boxes["n4"].val = 8; p.boxes["c0"].val = 0; }
                    tapAt(5, "OK"); loopFor(4000); CHECK(saves.size() == 2 && saves[1].step == 9 && saves[1].volts > 3.69f && saves[1].amps == 95 && saves[1].timer == 480 && !saves[1].kill && textDoubted == 1 && boxesLostTold == 1);
                }
                else CHECK(saves.size() == 1 && typed && boxesLostTold == 0 && textDoubted == 0);   // (no line)
                if (shout && stallMs >= 200) CHECK(screen.shouts == 1 && screenLogLines.size() == 1 && screenLogLines[0].find("silent for 2") != std::string::npos);
            }
    //     ... a word of the screen's own with no end, 3 ms, then the answer: a number below zero and the page's number are read (they
    //     were lost: -2 as -1 was, the page "not said"); A TEXT IS NOT BELIEVED (the ninth review) - unless the word ended with a
    //     newline (it was believed then - until 15 Nov 2026: the same now), or the screen is one that has never framed (an older one: its pages'
    //     own words come bare, and all is as it was)
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
    { char tx[20] = "x"; screen.emit(nowUs + 60000, bytes("UKRULES")); screen.emit(nowUs + 63000, glued({ bytes("p3.70"), { 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF } }));
      const uint64_t t0 = nowUs; CHECK(GetText((char *) "t10", tx, sizeof tx) == 0 && !tx[0] && textDoubted == 1 && ScreenAnswerOwed && NextionTextMissed && PendingCount == 1 && PendingLens[0] == 7 && nowUs - t0 < 200000); }
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
    { char tx[20] = "x"; screen.emit(nowUs + 60000, bytes("LDRCLOG core 1 (the loop's) silent for 213 ms: task loopTask, part web, at wifi, cmd 310 ms ago: Progress.val=5\n")); screen.emit(nowUs + 63000, glued({ bytes("p3.70"), { 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF } }));
      CHECK(GetText((char *) "t10", tx, sizeof tx) == 0 && !tx[0] && textDoubted == 1 && ScreenAnswerOwed && NextionTextMissed && PendingCount == 1); }
    //     ... such a line is over AT its newline - what stands behind it is a frame of its own: a number right behind it, with no pause at all, is read;
    //     a text is not believed (the half second), and the line is kept whole for the log
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
    { char tx[20] = "x"; screen.emit(nowUs + 60000, glued({ bytes("LDRCLOG core 1 (the loop's) silent for 213 ms: task loopTask, part web, at wifi, cmd 310 ms ago: page RXOptionsView\n"), bytes("p3.70"), { 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF } }));
      CHECK(GetText((char *) "t10", tx, sizeof tx) == 0 && !tx[0] && textDoubted == 1 && ScreenAnswerOwed && PendingCount == 1 && PendingLens[0] > 100 && WordOpenMs != 0); }
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
    screen.emit(nowUs + 60000, glued({ bytes("LDRCLOG core 0 silent for 300 ms at 81534 ms: task 'wifi' on it (the loop goes on)\n"), { 'q', 9, 0, 0, 0, 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF } }));
    CHECK(GetValue((char *) "n3") == 9 && PendingCount == 1 && WordOpenMs != 0);
    //     ... 9d (the author's, 15 Nov 2026; one storm trial in 24000 found it - the readers of every review had it). A FIELD SCREEN'S LINE HAS NO END OF
    //     ITS OWN, AND THE REPLY RIGHT BEHIND ITS FIRST PIECE CAN HOLD THE BYTE 0A: the page's marker, its count at 700A - "q 0A 70 45 4C" and its end. The
    //     line was ended at that 0A, taken for WHOLE (no half second), and the marker's remaining bytes - 70 45 4C FF FF FF, "p", "E", "L" and an end -
    //     were a TEXT REPLY to the box being asked: its text came back as "EL". Not believed now: no answer, said
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
    { char tx[20] = "x"; std::string piece = "LDRCLOG core 1 (the loop's) silent for 201 ms at 24648 ms: task 'loopTask' on it, part '-', loop at 'draw', last command 199 ms ago: page RXO";
      piece.resize(128, '.');
      screen.emit(nowUs + 60000, glued({ bytes(piece.c_str()), { 'q', 0x0A, 0x70, 0x45, 0x4C, 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF } }));
      const uint16_t k = GetText((char *) "t10", tx, sizeof tx);
      say("9d. a field screen's line, and right behind it the page's marker with its count at 700A: the text box asked got %u chars \"%s\"; not believed %d\n", (unsigned) k, tx, textDoubted);
      CHECK(k == 0 && !tx[0] && NextionTextMissed && textDoubted == 1 && WordOpenMs != 0); }
    //     ... the number of page 10 ("f 0A" and its end) behind the line's piece, and 0.2 s later the line's REST with a text answer glued on: the line
    //     was "whole" at that 0A, its rest unguarded - "ptionsView", which begins with p, and the answer: the box came back as "tionsViewp3.70"
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
    { char tx[24] = "x"; std::string piece = "LDRCLOG core 1 (the loop's) silent for 201 ms at 24648 ms: task 'loopTask' on it, part '-', loop at 'draw', last command 199 ms ago: page RXO";
      piece.resize(128, '.');
      screen.emit(nowUs + 60000, glued({ bytes(piece.c_str()), { 0x66, 0x0A, 0xFF, 0xFF, 0xFF } }));
      screen.emit(nowUs + 260000, glued({ bytes("ptionsViewp3.70"), { 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF } }));
      const uint16_t k = GetText((char *) "t10", tx, sizeof tx);
      say("9d. ... the number of page 10 behind the piece, the line's rest and a text answer 0.2 s later: the text box got %u chars \"%s\"; not believed %d\n", (unsigned) k, tx, textDoubted);
      CHECK(k == 0 && !tx[0] && NextionTextMissed && textDoubted == 1); }
    //     ... and read by the main loop (no get waits) it is a line for the log, whole - what stands behind it is not its tail
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true;
    screen.emit(nowUs + 1000, glued({ bytes("LDRCLOG core 0 silent for 300 ms at 81534 ms: task 'wifi' on it (the loop goes on)\n"), bytes("UKRULES") })); loopFor(50);
    CHECK(screenLogLines.size() == 1 && screenLogLines[0].find("UKRULES") == std::string::npos && ghosts.empty());
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true; ScreenFramesBursts = false;
    { char tx[20] = "x"; screen.emit(nowUs + 60000, bytes("UKRULES")); screen.emit(nowUs + 63000, glued({ bytes("p3.70"), { 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF } }));
      CHECK(GetText((char *) "t10", tx, sizeof tx) == 4 && !strcmp(tx, "3.70") && textDoubted == 0 && PendingCount == 1 && PendingLens[0] == 7); }
    //     ... half a second after the word with no end a text is believed again - ONCE THE SCREEN HAS ANSWERED "sendme" BEHIND THAT HALF SECOND (the
    //     twelfth review: the word is UNSETTLED until then - the box asked 520 ms behind it was asked the old way, and was handed the rest of a line
    //     still held with its answer glued on). The screen deaf here, what it says said by hand: the answer to "sendme", then the box's
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
    { char tx[20] = "x"; screen.emit(nowUs + 1000, bytes("UKRULES")); loopFor(520); CHECK(WordOpenMs != 0 && WordSettledFor != WordOpenMs);
      screen.emit(nowUs + 60000, { 0x66, 9, 0xFF, 0xFF, 0xFF }); screen.emit(nowUs + 200000, glued({ bytes("p3.70"), { 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF } }));
      const uint64_t t0 = nowUs;
      CHECK(GetText((char *) "t10", tx, sizeof tx) == 4 && !strcmp(tx, "3.70") && textDoubted == 0 && WordSettledFor == WordOpenMs && !ScreenAnswerOwed && nowUs - t0 < 400000);
      // ... and the next box, the word settled, is asked at once: no second "sendme" (its answer 60 ms behind the ask, as a screen's is)
      screen.emit(nowUs + 60000, glued({ bytes("p95"), { 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF } }));
      const uint64_t t1 = nowUs; CHECK(GetText((char *) "t12", tx, sizeof tx) == 2 && !strcmp(tx, "95") && textDoubted == 0 && nowUs - t1 < 130000); }
    //     ... the same word, and the screen answers the BOX only - no "sendme" answered behind the half second (it stands still: the rest of its line
    //     would come out with whatever it says next): the box's text, come as the old code waited for it, is NOT taken
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
    { char tx[20] = "x"; screen.emit(nowUs + 1000, bytes("UKRULES")); loopFor(520); CHECK(WordOpenMs != 0);
      screen.emit(nowUs + 60000, glued({ bytes("play 0,7,0p3.70"), { 0xFF, 0xFF, 0xFF } }));
      CHECK(GetText((char *) "t10", tx, sizeof tx) == 0 && !tx[0] && NextionTextMissed && BoxesLost == BoxesLostAtWork + 1); }
    //     ... and a screen that CANNOT say its page (an older one: no "sendme" is ever answered, and none is owed) is waited for two and a half
    //     seconds, then asked - and a text that comes with the word still unsettled is not believed (CollectReply: unsettled is doubted as open is)
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true; ScreenSaysPage = false;
    { char tx[20] = "x"; screen.emit(nowUs + 1000, bytes("UKRULES")); loopFor(520); CHECK(WordOpenMs != 0);
      const uint64_t t0 = nowUs; screen.emit(nowUs + 3400000, glued({ bytes("p3.70"), { 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF } }));
      CHECK(GetText((char *) "t10", tx, sizeof tx) == 0 && !tx[0] && textDoubted == 1 && NextionTextMissed && nowUs - t0 > 2400000);
      if (show) printf("   an unsettled word, a screen that cannot say its page: the box asked after %llu ms, its text doubted %d\n", (unsigned long long) ((nowUs - t0) / 1000), textDoubted); }
    //     ... a "sendme" answered INSIDE the half second settles nothing (a save's look in front of its boxes, 100 ms behind the word): the box asked
    //     550 ms behind the word settles first all the same - and the rest of the line, come with its answer glued on, is not handed back as its text
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
    { char tx[24] = "x"; screen.emit(nowUs + 1000, bytes("UKRULES")); loopFor(100); CHECK(WordOpenMs != 0);
      screen.emit(nowUs + 60000, { 0x66, 9, 0xFF, 0xFF, 0xFF }); RfGatherStart(); CHECK(NextionSettledOk && WordSettledFor != WordOpenMs);
      loopFor(450); screen.emit(nowUs + 60000, glued({ bytes("play 0,7,0p3.70"), { 0xFF, 0xFF, 0xFF } }));
      CHECK(GetText((char *) "t10", tx, sizeof tx) == 0 && !tx[0] && NextionTextMissed); }
    // 9b. A NUMBER FIELD'S TEXT THAT IS NO NUMBER IS NO ANSWER (the twelfth review; Nextion.h TextMustBeNumber). Every typed number field is asked as a
    //     text and made a number by atof / strtol, which make 0 of what they cannot read - and the rest of a line glued in front of an answer was
    //     read as 0, a number like any other. The routine itself: what a number is made of passes, untouched ...
    more(); tapAt(5, "setup"); loopFor(800);
    for (const char *ok : { "3.70", "-12.5", " 7", "+3", "", "0", "9", "1.2.3", "--5", "007 " })
    { char tx[24]; snprintf(tx, sizeof tx, "%s", ok); const uint32_t lost0 = BoxesLost; NextionTextMissed = false; const size_t lines0 = logLines.size();
      CHECK(TextMustBeNumber("tn1", tx) && !strcmp(tx, ok) && BoxesLost == lost0 && !NextionTextMissed && logLines.size() == lines0); }
    //     ... and anything else is no answer: the text emptied, the box counted and named (the FIRST one missed keeps its name), a line for the log.
    //     ("/" and ":" stand just outside the digits; the comma is no number's - "1,5" was read as 1; "1e5" and "0x10" are not typed on that keypad)
    for (const char *no : { "lay 0,7,0p3.70", "3.70p", "p3.70", "1,5", "12a", "\r\n3", "0x10", "1e5", "/", ":", "3.7\x1A", "\x88", "3;7", "~7" })
    { char tx[24]; snprintf(tx, sizeof tx, "%s", no); const uint32_t lost0 = BoxesLost; NextionTextMissed = false; NextionMissedBox[0] = 0; const size_t lines0 = logLines.size();
      CHECK(!TextMustBeNumber("tn1", tx) && !tx[0] && BoxesLost == lost0 + 1 && NextionTextMissed && !strcmp(NextionMissedBox, "tn1") && logLines.size() == lines0 + 1
            && logLines.back() == "(kept for later) Box tn1: text is no number");
      snprintf(tx, sizeof tx, "%s", no); CHECK(!TextMustBeNumber("tn2", tx) && !strcmp(NextionMissedBox, "tn1") && BoxesLost == lost0 + 2); }   // (a second one: the first keeps its name)
    //     ... Model options, the volts box handed back with the rest of a line in front ("lay 0,7,0p3.70" - what the three last reviews each found a
    //     timing for): NOTHING of the page is taken (it read 0 volts a cell - "stop flying" at every voltage), the pilot is told, the page is left
    //     as its OK always leaves it; the same of the amps box ("95" with a letter behind)
    for (int which = 0; which < 2; ++which)
    {
        more(); tapAt(5, "setup"); loopFor(800);
        { Page &p = screen.pages["RXOptionsView"]; p.boxes["n3"].val = 9; p.boxes["t10"].txt = which ? "3.70" : "lay 0,7,0p3.70"; p.boxes["t12"].txt = which ? "95p" : "95"; p.boxes["n1"].val = 7; p.boxes["n4"].val = 8; p.boxes["c0"].val = 0; }
        tapAt(5, "OK"); loopFor(4000);
        say("9b. Model options, the %s box handed back with letters in it: saved %d, as at first %d, told %d, page %s, volts %.2f, amps %d\n", which ? "amps" : "volts", (int) saves.size(), (int) sameAsAtFirst(), boxesLostTold, screen.page.c_str(), StopFlyingVoltsPerCell, Max_Safe_Amps);
        CHECK(saves.size() == 1 && sameAsAtFirst() && boxesLostTold == 1 && screen.page == "FrontView");
        bool said = false; for (const std::string &l : logLines) if (l == (which ? "(kept for later) Box t12: text is no number" : "(kept for later) Box t10: text is no number")) said = true;
        CHECK(said);
        // ... and typed again, his next OK saves it
        tapAt(5, "setup"); loopFor(800);
        { Page &p = screen.pages["RXOptionsView"]; p.boxes["n3"].val = 9; p.boxes["t10"].txt = "3.70"; p.boxes["t12"].txt = "95"; p.boxes["n1"].val = 7; p.boxes["n4"].val = 8; p.boxes["c0"].val = 0; }
        tapAt(5, "OK"); loopFor(4000); CHECK(saves.size() == 2 && saves[1].step == 9 && saves[1].volts > 3.69f && saves[1].amps == 95 && boxesLostTold == 1);
    }
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
    screen.emit(nowUs + 60000, bytes("TIME=1763200000")); screen.emit(nowUs + 63000, { 'q', 0xFE, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF });
    CHECK(GetValue((char *) "n2") == 0xFFFFFFFEu && PendingCount == 1);
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
    screen.emit(nowUs + 60000, { 'q', 5, 0, 0, 0, 0xFF, 0xFF, 0xFF }); screen.emit(nowUs + 62000, bytes("ldrcpipe=2")); screen.emit(nowUs + 65000, { 0x66, 9, 0xFF, 0xFF, 0xFF });
    CHECK(GetValue((char *) "n3") == 5 && pageUnsaid == 0 && PendingCount == 1 && PendingLens[0] == 10);
    //     ... glued to the word with no pause at all, a text answer cannot be told from the word: no answer (never a wrong one)
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
    { char tx[20] = "x"; screen.emit(nowUs + 60000, glued({ bytes("UKRULESp3.70"), { 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF } })); CHECK(GetText((char *) "t10", tx, sizeof tx) == 0 && tx[0] == 0 && NextionTextMissed); }

    // ================= 8. BYTES WITHOUT AN END; AN ANSWER AT THE LAST MOMENT =================
    // (a) while a box's answer is awaited the wire carries bytes with no end - one in a millisecond; a flood at the wire's own
    //     speed: the radio's packets go on every 20 ms (2.05 s without one, before), the dog is fed
    for (int kind = 0; kind < 2; ++kind)
    {
        more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
        const uint32_t stepUs = kind ? 11 : 1000; const uint64_t t0 = nowUs + 60000;
        for (uint64_t t = 0; t < 2600000; t += stepUs) screen.out.push_back({ t0 + t, (uint8_t) ('a' + (t / stepUs) % 26) });
        gapWatch = true; lastRadioUs = nowUs; maxRadioGapUs = 0; lastFeedUs = nowUs; maxUnfedUs = 0; dogWatch = true;
        const uint64_t g0 = nowUs; const uint32_t v = GetValue((char *) "n3"); radioService(); dogLook();
        say("8a. a box asked while the wire carries %s: answer %u after %.2f s, the radio's longest silence %.1f ms, the dog unfed %.2f s\n", kind ? "a flood" : "a byte a millisecond", (unsigned) v, (nowUs - g0) / 1e6, radioGapUs() / 1e3, maxUnfedUs / 1e6);
        CHECK(v == 65535 && radioGapUs() <= 45000 && maxUnfedUs < 1300000 && nowUs - g0 < 2400000);
    }
    // (b) four seconds of bytes at 66 kB a second, met by a write (its read of the wire) and by the loop's own read: each comes
    //     back (the write never did before the bytes ended; the loop's read held the model's packets all the while)
    for (int way = 0; way < 2; ++way)
    {
        more(); screen.deaf = true; holdCatchUp = true; const uint64_t t0 = nowUs + 1000;
        for (uint64_t t = 0; t < 4000000; t += 15) screen.out.push_back({ t0 + t, (uint8_t) ('a' + (t / 15) % 26) });
        nowUs += 2000; lastFeedUs = nowUs; maxUnfedUs = 0; dogWatch = true; const uint64_t g0 = nowUs;
        if (way) SendValue((char *) "Progress", 5); else LoopPass();
        dogLook(); say("8b. bytes without end met by %s: back after %.0f ms\n", way ? "a write" : "the loop's read", (nowUs - g0) / 1e3);
        CHECK(nowUs - g0 < (way ? 250000 : 60000) && maxUnfedUs < 1300000);   // (the thirteenth review: THE LOOP'S ONE READ HAS AN END - 40 ms, looked at once in 64 bytes.
    }                                                                        //  "A quarter second" passed with that rule taken out: its text's room, 4096 bytes, is 82 ms here)
    //     ... and at the wire's own speed - a byte in 87 us and no pause, a faulty screen that talks on: the loop's read is back in 40 ms, the model flown.
    //     (Its text's room would have held the loop for a third of a second, not one packet sent: Nextion.h GetTextIn - no scene held this end.)
    {
        more(); screen.deaf = true; holdCatchUp = true; const uint64_t t0 = nowUs + 1000;
        for (uint64_t t = 0; t < 1500000; t += 87) screen.out.push_back({ t0 + t, (uint8_t) ('a' + (t / 87) % 26) });
        nowUs += 2000; gapWatch = true; lastRadioUs = nowUs; maxRadioGapUs = 0; const uint64_t g0 = nowUs;
        LoopPass();
        say("8b. a byte in 87 us without end, met by the loop's read: back after %.0f ms, the radio's longest silence %.1f ms\n", (nowUs - g0) / 1e3, radioGapUs() / 1e3);
        CHECK(nowUs - g0 < 60000 && radioGapUs() < 60000);
    }
    // (c) AN ANSWER THAT COMES AT THE LAST MOMENT of its wait is taken: wherever in the wait's last half millisecond its first byte
    //     lands, the box has its answer (at its end, with nothing "open", what stood on the wire was left unread)
    {
        int lost = 0;
        for (uint32_t off = 99400; off <= 99980; off += 3)   // (its first byte is on the wire 11 us after that: before the time is up)
        {
            more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; nowUs = (nowUs / 1000 + 1) * 1000;
            uint16_t k = 0; NextionReplyWaitMs = 100; screen.emit(nowUs + off, { 'q', 7, 0, 0, 0, 0xFF, 0xFF, 0xFF });
            if (!(CollectReply('q', k) && TextIn[1] == 7)) ++lost;
        }
        say("8c. an answer in the last 0.6 ms of a wait of 100 ms, 194 moments: lost %d\n", lost); CHECK(lost == 0);
    }

    // (d) at the very end of a wait: an answer already on the wire when the time is up is read (a wait of no time at all shows it);
    //     and a word of the screen's own, or a button's code, that came in the wait's last millisecond is kept, not thrown away
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true;
    { uint16_t k = 0; screen.emit(nowUs, { 'q', 7, 0, 0, 0, 0xFF, 0xFF, 0xFF }); nowUs += 500; NextionReplyWaitMs = 0; CHECK(CollectReply('q', k) && TextIn[1] == 7); NextionReplyWaitMs = 100; }
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; nowUs = (nowUs / 1000 + 1) * 1000;
    { uint16_t k = 0; NextionReplyWaitMs = 100; screen.emit(nowUs + 99300, bytes("LDRCAWAKE")); CHECK(!CollectReply('q', k) && PendingCount == 1 && PendingLens[0] == 9); }
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; ScreenFramesBursts = false; nowUs = (nowUs / 1000 + 1) * 1000;
    { uint16_t k = 0; NextionReplyWaitMs = 100; screen.emit(nowUs + 99300, { 0xC1, 0x00, 0x00, 0x00 }); CHECK(!CollectReply('q', k) && PendingCount == 1 && PendingLens[0] == 4); }

    // ================= 9. THE SCREEN RESTARTS DURING A CALIBRATION OF THE STICKS =================
    // The model was cleared for it, the limits half swept: the front page left both in memory for the next save. Now, as an OK
    // part way through does (B17): the limits and the model come back from the card, normal mode again
    more(); CurrentView = CALIBRATEVIEW; CurrentMode = CALIBRATELIMITS; ModelNumber = 4; tapAt(5, "#restart"); loopFor(9000);
    CHECK(restartsHandled == 1 && CurrentMode == NORMAL && paramsLoaded == 1 && redLeds == 1 && modelsRead.size() == 1 && modelsRead[0] == 4 && CurrentView == FRONTVIEW);
    more(); CurrentView = CALIBRATEVIEW; CurrentMode = NORMAL; ModelNumber = 4; tapAt(5, "#restart"); loopFor(9000);
    CHECK(restartsHandled == 1 && paramsLoaded == 0 && redLeds == 0 && modelsRead.size() == 1);   // (the page, not yet sweeping: the model back)
    more(); tapAt(5, "setup"); loopFor(800); tapAt(5, "#restart"); loopFor(9000); CHECK(restartsHandled == 1 && paramsLoaded == 0 && modelsRead.empty());

    // ================= 10. A TEXT BOX'S LETTERS ARE NEVER A MARKER; THE PIPE'S STATE IS NO PIPE LINE =================
    // A late text answer whose text ends as the awaited marker does ("...q12EL"), read in by a write, and met in a get's wait: no
    // marker - the page is not "up" for it (dev/test_stalepress 59a has the loop's own read)
    for (int way = 0; way < 2; ++way)
    {
        more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
        ScreenMarkCount = 0x3231; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | ScreenMarkCount; ScreenMarkOldPage = true; ScreenMarkAskedMs = millis(); ScreenMarkMisses = 0;
        screen.emit(nowUs + (way ? 60000 : 0), { 'p', 'a', 'b', 'q', 0x31, 0x32, 0x45, 0x4C, 0xFF, 0xFF, 0xFF }); nowUs += 1000;
        if (way) { CHECK(GetValue((char *) "n3") == 65535); } else StashPendingEventBytes();
        CHECK(ScreenMarkAwaited != 0 && ScreenMarkOldPage);
    }
    //     ... the pipe's state has no newline: it is a word like any other (it was waited for as an open line - a reply within 5 ms
    //     was glued to it, and one that held a byte 0A was cut there)
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
    screen.emit(nowUs + 60000, bytes("ldrcpipe=2")); screen.emit(nowUs + 63000, { 'q', 0x0A, 0, 0, 0, 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF });
    CHECK(GetValue((char *) "n3") == 10 && PendingCount == 1 && PendingLens[0] == 10);
    more(); screen.emit(nowUs, bytes("ldrcpipe=2")); nowUs += 1000; StashPendingEventBytes(); CHECK(PendingCount == 1 && PendingLens[0] == 10 && nowUs % 1000000 < 999000);
    { const uint8_t a[] = "ldrctel 25:AA\n", b[] = "ldrcrep 1 200 x\n", c[] = "ldrcpipe=2\n", d[] = "ldrcte";
      CHECK(PipeLineDone(a, 14) && PipeLineDone(b, 16) && !PipeLineDone(c, 11) && PipeLineOpen(a, 10) && PipeLineOpen(d, 6) && !PipeLineOpen(c, 10) && !PipeLineOpen(a, 14)); }
    //     ... AND A WHOLE LINE OF THE PIPE OPENS NO HALF SECOND (every OTHER bare word does, since the thirteenth review - a line for the log with its
    //     newline too). The pipe's telemetry says several lines a second: a text box asked right behind one is asked at once - no settling look in
    //     front of it, nothing in doubt. (With "a pipe line is a word that may not be over" every text box of a Rotorflight page by Bluetooth would
    //     settle first, or be refused: no scene held it.)
    more(); tapAt(5, "setup"); loopFor(800);
    { const uint32_t open0 = WordOpenMs, settled0 = WordSettledFor; char tx[20] = "x";
      screen.emit(nowUs + 1000, bytes("ldrctel 25:AABBCCDD 26:EEFF0011\n")); loopFor(30);
      CHECK(WordOpenMs == open0);
      const uint64_t t0 = nowUs; const int n = GetText((char *) "t10", tx, sizeof tx);
      say("10. a text box asked 30 ms behind a whole line of the pipe: '%s' after %.0f ms\n", tx, (nowUs - t0) / 1e3);
      CHECK(n == 4 && !strcmp(tx, "3.50") && textDoubted == 0 && nowUs - t0 < 150000 && WordOpenMs == open0 && WordSettledFor == settled0);
      //   (... while a line for the log opens it, newline or not: 9d has what follows from that)
      screen.emit(nowUs + 1000, bytes("LDRCLOG core 0 silent 300 ms\n")); loopFor(30); CHECK(WordOpenMs != open0 && WordOpenMs != 0); }
'''

MAIN_HEAD = r'''
int main(int argc, char **argv)
{
    show = argc > 1 && !strcmp(argv[1], "--show");
'''
MAIN_TAIL = r'''
    printf("test_noanswer: %d checks, %d failures\n", checks, fails);
    if (!fails) printf("ALL GOOD\n");
    return fails ? 1 : 0;
}
'''

BANKLISTEN = m.MAIN_CPP[m.MAIN_CPP.index('static uint8_t BankListenCount = 0;'):m.MAIN_CPP.index('void ListenToBanks()')]   # ("Listen": its three counters, as main.cpp has them)
LIFTS = [(m.UTIL, 'static uint16_t NextPageMark()'), (m.UTIL, 'static bool QuestionIsUp(uint16_t mine)'), (m.UTIL, 'void MsgBox(char *goback, char *Prompt)'), (m.UTIL, 'bool GetConfirmation(char *goback, char *Prompt)'), (m.MAIN_CPP, 'FLASHMEM void EnsureMotorIsOff()'),
         (m.MAIN_CPP, 'FLASHMEM static uint8_t BankNameFromPage(int i)'), (m.MAIN_CPP, 'FLASHMEM static bool BankNamesFromPage()'), (BANKLISTEN, None), (m.MAIN_CPP, 'void ListenToBanks()'), (m.MAIN_CPP, 'FLASHMEM void BankListenPoll()'),
         (m.MENU, 'void EndServoTypeView()'), (m.MENU, 'void BuddyChViewEnd()'), (m.MAIN_CPP, 'void WriteNewCurve()'), (m.MENU, 'FLASHMEM void InputsViewEnd()'),
         (m.MAIN_CPP, 'void UpdateLED()'), (m.MENU, 'FLASHMEM void OptionView3End()'), (m.MENU, 'void Options2End()'), (m.UTIL, 'void Save_BackGround()'),
         (DUAL, 'void CheckDualRatesScreen(uint32_t RightNow)'), (DUAL, 'void CheckSelectedRatesMode()'), (m.UTIL, 'bool GetBackupFilename(char *goback, char *tt1, char *MMname, char *heading, char *pprompt)')]
DEFINES = ('BANKS_USED', 'BANK_NAMES_N', 'BANKSNAMESVIEW', 'QNH_SETTING', 'SERVO_FREQUENCIES', 'SERVO_PULSE_WIDTHS', 'STICKSVIEW', 'GRAPHVIEW', 'TXSETUPVIEW', 'INPUTS_VIEW', 'COLOURS_VIEW', 'BUDDYVIEW',
           'OPTIONVIEW2', 'OPTIONVIEW3', 'BUDDYCHVIEW', 'DUALRATESVIEW', 'SERVOTYPESVIEW', 'MOTORON', 'PLSTURNOFF', 'CURVE_POINTS_MAX', 'CURVE_STORE_MAX')

def program(scenes):
    text = m.program()
    head = text[:text.index('int main(int argc, char **argv)')]
    defs = ''.join('#define %s %s\n' % (d, m.define(d)) for d in DEFINES)
    lifts = ''.join(src if name is None else m.lift(src, name) for src, name in LIFTS)
    return head + defs + EXTRA.replace('@LIFTS@', lifts) + MAIN_HEAD + scenes + MAIN_TAIL

# ---- EVERY PLACE A PAGE'S BOX IS ASKED FOR, read out of the source: what comes back may be "no answer" (65535, "", 0; a row: -1), and
# must not be taken for the box's value. (The ninth review, 15 Nov 2026: the first form of this check let natural unsafe forms through -
# a local, then the setting, with no check; a tick compared "!= 0" or "> 0"; a local too narrow to keep 65535; a text into a buffer of
# the routine's own, then a number made of it; GetSysValue and ChosenFileRow, which it did not know; the old getter that read the wire
# blindly. Each of those is a line of LINT_SELFTEST below: the check is run on a copy of the source with that line in it, and must see it.)
# A read is in order when it has one of these SHAPES:
#   - compared where it stands with "!= 65535" / "== 65535", an upper bound ("<= 1", "< n"), or an equality with something that is not 0
#     ("== 1") - and the result not put straight into a setting;
#   - its answer goes into a variable of the routine's own, WIDE enough to keep 65535, whose FIRST mention behind the read is a look
#     ("!= 65535", an upper bound, "> n" with a way out, "< 0" for a row) - not a use;
#   - a text goes into a buffer of the routine's own that is looked at before it is used (its length, the count of unanswered boxes);
#   - or - for a variable or buffer of the routine's own only - the routine takes its page whole or not at all: a KEEP_WHOLE above the
#     read, the count of unanswered boxes kept above it and compared below it, or WorkLostABox() / RfFieldsMissed() asked below it.
# Anything else - straight into a setting, into an index, "if (GetValue(...))", a text straight into a setting's own buffer - fails here,
# unless it is on the list with its reason. A place on the list that is no longer there fails too.
ALLOW = [
    ('MenuOptions.h', 'in[i] = CheckRange((GetValue(InputStick_Labels[i]) - 1), 0, 15);', 1, 'a copy: the page is taken whole or not at all (InputsViewEnd)'),
    ('MenuOptions.h', 'out[i] = CheckRange((GetValue(OutputStick_Labels[i]) - 1), 0, 15);', 1, 'a copy, as above'),
    ('MenuOptions.h', 'trim[i] = CheckRange((GetValue(InputTrim_labels[i]) - 1), 0, 15);', 1, 'a copy, as above'),
    ('RF_Governor_Global.h', 'GovWritePayload[', 10, "a payload's byte: RfFieldsMissed refuses the send when a box had no answer (dev/test_missed_reply), and the payload is kept whole"),
    ('RF_Governor_Profile.h', 'GovWritePayload[', 13, "a payload's byte, as above"),
    ('RF_Easy.h', 'v[k] = GetValue(nm);', 1, 'a copy: every slider and the switch are asked first, and none is taken when one had no answer (EzSyncSliders: WorkLostABox right behind the asking - false, and the save stops)'),
    ('RF_Save_Restore.h', 'LocalBank = GetValue((char *)"n0");', 1, 'held to the banks there are on the next line - and after a box with no answer no tick reads 1: nothing is chosen, nothing done'),
    ('SDFiles.h', 'GetText(ModelsView_filename, SingleModelFile, 40);', 1, 'the count of unanswered boxes is looked at on the next line: no name, nothing renamed'),
    ('Utilities.h', 'GetText(t1, SingleModelFile, 40);', 1, 'the count of unanswered boxes is looked at before the name is used (GetBackupFilename)'),
]
LINT_NUM = r'(?:GetValue|getvalue|GetOtherValue|GetSysValue|ChosenFileRow)'
LINT_WIDE = r'(?:uint32_t|int32_t|uint16_t|int|long|unsigned|unsigned long|auto)'
LINT_NARROW = r'(?:uint8_t|int8_t|bool|char|u_int8_t|byte|short|short int|float|double)'
LINT_HEAD = re.compile(r'^(?:FLASHMEM\s+|FASTRUN\s+|static\s+|inline\s+|B211_RARE\s+)*(?:void|bool|int|long|uint8_t|uint16_t|uint32_t|float|char \*|const char \*)\s*\*?\s*([A-Za-z_]\w*)\s*\(')
LINT_HELPERS = r'(?:FieldNumber|FieldTenths|FieldHundredths|FieldTenthsL|BasFieldTenths|FieldPercent|BasPair|MacroValue)'   # (each reads ONE field for a gather that keeps: page_lint has them)
def lint_call_end(s, at):
    d = 0
    for i in range(at, len(s)):
        if s[i] == '(': d += 1
        elif s[i] == ')':
            d -= 1
            if d == 0: return i + 1
    return len(s)
def lint_number(tok):
    """A number written out (65535, 0xFFFF, 65536u): its value; anything else: None."""
    mo = re.fullmatch(r'(0[xX][0-9a-fA-F]+|\d+)[uUlL]*', tok)
    return int(mo.group(1), 0) if mo else None
def lint_first_mention(name, lines_after, getter=None):
    """The first line behind the read that names `name`: True - a look that bounds it; False - a use; None - nothing names it.
    (The tenth review: a look is one that REFUSES "no answer" whatever else is true - not "v != 65535 || x", not "if (v == 65535) v = 0",
    not "v < 65536"; and GetOtherValue's "no answer" is 0, so "!= 65535" says nothing about it.)"""
    n = re.escape(name); w = re.compile(r'\b' + n + r'\b')
    for l in lines_after:
        s = l.split('//')[0]
        m0 = w.search(s)
        if not m0: continue
        head, tail = s[:m0.start()], s[m0.end():]
        cond_before = re.split(r'\b(?:if|while)\s*\(', head)[-1]
        mo = re.match(r'\s*(!=|==)\s*65535u?\b(.*)', tail, re.S)
        if mo:                                                                                                # "no answer" asked for by name
            cond_after = mo.group(2).split(')')[0]
            if getter == 'GetOtherValue': return False, s                                                     # (its "no answer" is 0)
            if mo.group(1) == '!=' and ('||' in cond_before or '||' in cond_after): return False, s           # "... or something else": no answer gets through
            if mo.group(1) == '==' and ('&&' in cond_before or '&&' in cond_after): return False, s           # "... and something else": no answer is not always refused
            if mo.group(1) == '==' and re.match(r'\s*\)\s*\{?\s*' + n + r'\s*=[^=]', mo.group(2)): return False, s   # no answer made a number by hand
            return True, s
        mo = re.match(r'\s*(<=|<)\s*([\w\.]+|\()', tail)
        if mo:                                                                                                # an upper bound (a row: "< 0" is "none")
            v = lint_number(mo.group(2))
            if v is not None and ((mo.group(1) == '<=' and v >= 65535) or (mo.group(1) == '<' and v > 65535)): return False, s   # (a bound "no answer" passes)
            if '||' in cond_before: return False, s
            return True, s
        if re.match(r'\s*>=\s*[\w\(][^;?]*&&\s*' + n + r'\s*(?:<=|<)', tail): return True, s                  # held between two bounds
        if re.match(r'\s*>=?\s*[\w\(]', tail) and re.search(r'\bif\s*\(', head) and re.search(r'\)\s*(?:return|continue|break)\b', tail): return True, s   # too big: out
        if re.match(r'\s*==\s*[\w\(]', tail) and re.search(r'\bif\s*\([^;]*$', head) and not w.search(re.sub(r'^[^)]*\)', '', tail, count=1)):
            continue                                                                                          # a look that bounds nothing ("if (gv == 0) refuse"): the next mention is judged
        return False, s
    return None, ''
def lint_whole(lines_before, lines_after):
    """The routine takes its page whole or not at all, around this read."""
    if any('KEEP_WHOLE(' in x.split('//')[0] for x in lines_before): return True
    if any(re.search(r'\bWorkLostABox\(\)|\bRfFieldsMissed\(', x.split('//')[0]) for x in lines_after): return True
    kept = [mm.group(1) for x in lines_before for mm in [re.search(r'\b(\w+)\s*=\s*BoxesLost\s*;', x.split('//')[0])] if mm]
    if kept:
        k = re.escape(kept[-1])
        if any(re.search(r'\bBoxesLost\s*(?:==|!=)\s*' + k + r'\b|\b' + k + r'\s*(?:==|!=)\s*BoxesLost\b', x.split('//')[0]) for x in lines_after): return True
    return False
def box_flags(texts):
    """texts: {file name: its text}. Every read that has none of the shapes: (file, line, why, the line)."""
    flags = []
    for name in sorted(texts):
        if name == 'Nextion.h': continue                                       # (the getters themselves)
        lines = texts[name].split('\n')
        heads = [i for i, l in enumerate(lines) if LINT_HEAD.match(l) and not l.split('//')[0].rstrip().endswith(';')]
        for i, l in enumerate(lines):
            s = l.split('//')[0]
            if re.search(r'\bGet\w*FromTextBox\b', s): flags.append((name, i + 1, 'asked through an old getter, which read the wire blindly', s.strip())); continue   # (GetIntFromTextBox, GetFloatFromTextBox: both gone)
            if not re.search(r'\b' + LINT_NUM + r'\(|\bGetText\(', s): continue
            if re.match(r'\s*(?:FLASHMEM\s+)?(?:static\s+)?(?:uint32_t|uint16_t|int|bool|void)\s+(?:' + LINT_NUM + r'|GetText)\(', s): continue   # (a getter's own prototype - not a routine that hands a getter's answer on)
            a = max([h for h in heads if h <= i], default=0); b = min([h for h in heads if h > i], default=len(lines))
            fn = LINT_HEAD.match(lines[a]).group(1) if heads and a in heads else ''
            before, after = lines[a:i], lines[i + 1:b]
            whole = lint_whole(before, after)
            for mm in re.finditer(r'\b' + LINT_NUM + r'\(', s):
                getter = mm.group(0)[:-1]; end = lint_call_end(s, mm.end() - 1); rest = s[end:]; pre = s[:mm.start()]
                why = None
                op = re.match(r'\s*\)*\s*(==|!=|<=|>=|<|>)\s*([^\s;,)&|}]+)', rest)
                asg = re.search(r'(?:\b(?:const\s+)?(' + LINT_WIDE + r'|' + LINT_NARROW + r')\s+)?([A-Za-z_][\w\.]*(?:\[[^\]]*\])*)\s*[|&+\-]?=\s*(?:\{\s*)?(?:[^;{}]*,\s*)?(?:\([\w\s\*]+\)\s*)*(?:CheckRange\(\s*\(*\s*)?\(*\s*$', pre)
                if op:
                    o, x = op.group(1), op.group(2)
                    xv = lint_number(x)
                    ok = (o in ('==', '!=') and x == '65535' and getter != 'GetOtherValue') or (o in ('<=', '<') and not (xv is not None and xv >= 65535 + (o == '<'))) \
                         or (o == '==' and x not in ('0', 'false')) or (getter == 'ChosenFileRow' and o == '>=' and x == '0')
                    if not ok: why = 'compared "%s %s" where it stands ("no answer" then passes for a value)' % (o, x)
                    elif asg and not asg.group(1) and not re.fullmatch(r'[a-z]\w*(?:\[[^\]]*\])?', asg.group(2)) and not (o == '!=' and x == '65535'):
                        why = 'compared where it stands and the result put straight into ' + asg.group(2)
                elif asg:
                    typ, tgt = asg.group(1), asg.group(2)
                    if not typ and not re.fullmatch(r'[a-z]\w*', tgt): why = 'straight into ' + tgt
                    elif typ and re.fullmatch(LINT_NARROW, typ): why = 'into %s %s, too narrow to keep "no answer"' % (typ, tgt)
                    else:
                        if not typ:
                            decl = [x.split('//')[0] for x in before if re.search(r'\b(?:' + LINT_WIDE + r'|' + LINT_NARROW + r')\s+(?:\w+\s*(?:=[^,;]*)?,\s*)*' + re.escape(tgt) + r'\b', x.split('//')[0])]
                            if decl and re.search(r'\b' + LINT_NARROW + r'\s+(?:\w+\s*(?:=[^,;]*)?,\s*)*' + re.escape(tgt) + r'\b', decl[-1]): why = 'into %s, which is too narrow to keep "no answer"' % tgt
                        if not why and not whole:
                            ok, where = lint_first_mention(tgt, [s[end:]] + after[:14], getter)
                            if ok is False: why = 'into %s, which is used before it is looked at (%s)' % (tgt, where.strip()[:50])
                            elif ok is None: why = 'into %s, which nothing looks at' % tgt
                elif re.search(r'(?:if|while)\s*\(\s*!?\s*$', pre) and re.match(r'\s*\)', rest): why = 'taken for yes or no'
                elif re.search(r'\breturn\s+(?:\([\w\s\*]+\)\s*)?$', pre): why = 'handed back as it is'
                else: why = 'used where it stands'
                if why: flags.append((name, i + 1, why, s.strip()))
            g = re.search(r'\bGetText\(\s*[^,]+,\s*([A-Za-z_]\w*)', s)
            if g and not re.fullmatch(LINT_HELPERS, fn):
                buf = g.group(1); end = lint_call_end(s, s.index('GetText(') + 7)
                if buf[0].isupper():
                    flags.append((name, i + 1, 'a text straight into ' + buf, s.strip()))
                elif not whole:
                    # (the tenth review: the count GetText hands back is a look only as "any at all?" - "> 0", "!= 0", "if (GetText(..))" -
                    #  not ">= 0"; the buffer's own look is "is it empty?" - buf[0], or its length against 0 - not "strlen(buf) < 12";
                    #  and a buffer nothing names in the lines behind is not "looked at")
                    call = r'GetText\((?:[^()]|\([^()]*\))*\)'; bq = re.escape(buf)
                    counted = re.search(r'\b(?:if|while)\s*\(\s*!?\s*' + call + r'\s*\)', s) or re.search(call + r'\s*(?:>\s*0\b|>=\s*1\b|!=\s*0\b|==\s*0\b|<\s*1\b)', s)
                    if re.search(call + r'\s*(?:==|!=|>=|<=|>|<)', s) and not counted:
                        flags.append((name, i + 1, 'a text whose count is compared with something "no answer" passes', s.strip()))
                    elif not counted:
                        use = [x.split('//')[0] for x in [s[end:]] + after[:14] if re.search(r'\b' + bq + r'\b', x.split('//')[0])]
                        look = r'\bif\s*\([^;]*\b' + bq + r'\[0\]|\b' + bq + r'\[0\]\s*(?:==|!=)|strlen\(\s*' + bq + r'\s*\)\s*(?:>\s*0\b|>=\s*1\b|!=\s*0\b|==\s*0\b|<\s*1\b)|\bif\s*\(\s*!?\s*strlen\(\s*' + bq + r'\s*\)\s*\)'
                        if not use: flags.append((name, i + 1, 'a text into %s, which nothing looks at in the lines behind it' % buf, s.strip()))
                        elif not re.search(look, use[0]):
                            flags.append((name, i + 1, 'a text into %s, which is used with no look at "was the box answered?"' % buf, s.strip()))
    return flags
def lint_texts():
    return {os.path.basename(f): open(f, encoding='utf-8', errors='replace').read() for f in sorted(glob.glob(os.path.join(m.TC, 'include', '*.h'))) + [os.path.join(m.TC, 'src', 'main.cpp')]}
def lint_judge(flags):
    bad = []; used = [0] * len(ALLOW)
    for name, i, why, s in flags:
        for k, (af, frag, n, reason) in enumerate(ALLOW):
            if af == name and frag in s: used[k] += 1; break
        else: bad.append('%s:%d a box\'s answer is %s, with no look at "no answer" first: %s' % (name, i, why, s[:110]))
    for k, (af, frag, n, reason) in enumerate(ALLOW):
        if used[k] != n: bad.append('%s: "%s" was allowed in %d place(s) (%s) and stands in %d' % (af, frag[:60], n, reason, used[k]))
    return bad
def box_lint():
    flags = box_flags(lint_texts())
    return lint_judge(flags), len(flags)
# THE CHECK'S OWN TEST: each of these lines put into a copy of the source must be SEEN (the ninth review's own list, and more of the kind)
LINT_AT = 'gv = GetValue(lpm); if (gv != 65535) AutoModelSelect = gv;'
LINT_SELFTEST = [
    ('straight into a setting', 'MenuOptions.h', LINT_AT, 'AutoModelSelect = GetValue(lpm);'),
    ('into a local, then into the setting with no check', 'MenuOptions.h', LINT_AT, 'gv = GetValue(lpm); AutoModelSelect = gv;'),
    ('into a local, used on the next line with no check', 'MenuOptions.h', LINT_AT, 'gv = GetValue(lpm);\n    AutoModelSelect = gv;'),
    ('a tick compared "!= 0" (no answer, 65535, is then a tick)', 'RF_Save_Restore.h', 'if (GetValue((char *)"sw0") == 1)', 'if (GetValue((char *)"sw0") != 0)'),
    ('a tick compared "> 0"', 'main.cpp', 'const bool On[3] = {GetValue(Lines) == 1, GetValue(Smooth) == 1, GetValue(ExpR) == 1};', 'const bool On[3] = {GetValue(Lines) > 0, GetValue(Smooth) > 0, GetValue(ExpR) > 0};'),
    ('a tick compared ">= 1"', 'RF_Save_Restore.h', 'if (GetValue((char *)"sw0") == 1)', 'if (GetValue((char *)"sw0") >= 1)'),
    ('a tick compared "== 0" (no answer is then "not off")', 'RF_Save_Restore.h', 'if (GetValue((char *)"sw0") == 1)', 'if (!(GetValue((char *)"sw0") == 0))'),
    ('a text into a buffer of its own, then a number made of it with no check', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    { char tb[12]; GetText((char *)"t9", tb, sizeof(tb)); Qnh = atof(tb); }'),
    ('a text into a buffer of its own, used on the next line', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    char tb[12];\n    GetText((char *)"t9", tb, sizeof(tb));\n    Qnh = atof(tb);'),
    ('the old unguarded getter', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    LEDBrightness = GetIntFromTextBox((char *)"t9");'),
    ('through constrain()', 'MenuOptions.h', LINT_AT, 'AutoModelSelect = constrain(GetValue(lpm), 0, 1);'),
    ('a local of its own, too narrow, used as an index', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    { const uint8_t ix = GetValue(lpm); TopChannelSwitch[ix] = 1; }'),
    ('a bool of its own from "> 0", then the setting', 'MenuOptions.h', LINT_AT, '{ const bool on = GetValue(lpm) > 0; AutoModelSelect = on; }'),
    ('a bool of its own from "== 1" put straight into a setting', 'MenuOptions.h', LINT_AT, 'AutoModelSelect = GetValue(lpm) == 1;'),
    ('a system variable taken straight', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    LEDBrightness = GetSysValue("dim");'),
    ('a system variable into a local, used with no look', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    { const uint32_t d = GetSysValue("dim"); LEDBrightness = d; }'),
    ('a row taken through the file list\'s helper, straight', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    AutoModelSelect = ChosenFileRow("lpm");'),
    ('a row into a local, used as an index with no look', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    { const int r = ChosenFileRow("lpm"); strcpy(TxName, TheFilesList[r]); }'),
    ('taken for yes or no', 'MenuOptions.h', LINT_AT, 'if (GetValue(lpm)) AutoModelSelect = 1;'),
    ('a wide local looked at with "!= 0" only', 'MenuOptions.h', LINT_AT, 'gv = GetValue(lpm); if (gv != 0) AutoModelSelect = gv;'),
    ('a text straight into a setting\'s own buffer', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    GetText(TxNme, TxName, sizeof(TxName));'),
    # (the tenth review, reviewer B's probes - none of these was seen)
    ('no answer made 0 by hand, then the setting', 'MenuOptions.h', LINT_AT, '{ uint32_t v = GetValue(lpm); if (v == 65535) v = 0; AutoModelSelect = v; }'),
    ('a look that does not bound: "!= 65535 || something"', 'MenuOptions.h', LINT_AT, '{ const uint32_t v = GetValue(lpm); if (v != 65535 || AutoModelSelect) AutoModelSelect = v; }'),
    ('a look that does not always refuse: "== 65535 && something"', 'MenuOptions.h', LINT_AT, '{ const uint32_t v = GetValue(lpm); if (v == 65535 && AutoModelSelect) return; AutoModelSelect = v; }'),
    ('a wide local compared "< 65536" (always true)', 'MenuOptions.h', LINT_AT, '{ const uint32_t v = GetValue(lpm); if (v < 65536) AutoModelSelect = v; }'),
    ('a wide local compared "<= 0xFFFF" (no answer passes)', 'MenuOptions.h', LINT_AT, '{ const uint32_t v = GetValue(lpm); if (v <= 0xFFFF) ScreenTimeout = v; }'),
    ('compared "<= 65535" where it stands', 'MenuOptions.h', LINT_AT, 'if (GetValue(lpm) <= 65535) AutoModelSelect = 1;'),
    ('a text, its length looked at with a look that lets "" through', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    { char tb[12]; GetText((char *)"t9", tb, sizeof(tb)); if (strlen(tb) < 12) Qnh = atof(tb); }'),
    ('a text: the count handed back compared ">= 0" (always true)', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    { char tb[12]; if (GetText((char *)"t9", tb, sizeof(tb)) >= 0) Qnh = atof(tb); }'),
    ('a text into a local, used fifteen lines on', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    { char tb[12]; GetText((char *)"t9", tb, sizeof(tb));' + '\n    SendValue(Progress, 1);' * 15 + '\n    Qnh = atof(tb); }'),
    ('GetOtherValue: looked at "!= 65535" (its no answer is 0)', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    { const int c = GetOtherValue((char *)"High.pco"); if (c != 65535) HighlightColour = c; }'),
    ('GetOtherValue: compared "!= 65535" where it stands', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    if (GetOtherValue((char *)"High.pco") != 65535) HighlightColour = 1;'),
    ('the old float getter, by its name', 'MenuOptions.h', LINT_AT, LINT_AT + '\n    Qnh = GetFloatFromTextBox((char *)"t9");'),
    ('a new getter that hands the answer back as it is', 'MenuOptions.h', 'FLASHMEM void ReadRXOptionsView()', 'uint32_t BoxNow(char *n) { return GetValue(n); }\nFLASHMEM void ReadRXOptionsView()'),
]
def lint_selftest():
    texts = lint_texts(); base = set((n, s) for n, i, w, s in box_flags(texts)); bad = []
    for what, f, old, new in LINT_SELFTEST:
        if texts[f].count(old) < 1: bad.append('the lint\'s own test: the line to change is not in %s any more (%s)' % (f, what)); continue
        t2 = dict(texts); t2[f] = texts[f].replace(old, new, 1)
        more = [x for x in box_flags(t2) if (x[0], x[3]) not in base]
        if not more: bad.append('the check for unanswered boxes does NOT SEE this form any more: ' + what)
    return bad, len(LINT_SELFTEST)

# ---- THE ROTORFLIGHT PAGES (the ninth review): a page's fields are taken whole, or not at all (Nextion.h). Read out of the source:
# every routine that gathers has its keep (KEEP_WHOLE) - or is on the list with its reason; every call of a gather has the
# question behind it (RfFieldsMissed for a Save, WorkLostABox elsewhere) within its next lines; and a field read by a helper
# (GetText, a number, its range) stands inside a gather, or has the question behind it.
GATHERS_WITHOUT_KEEP = {
    'BasGather': "calls the page's own gathers, which keep", 'TravGather': "calls the page's own gathers, which keep",
    'TravGatherDirections': 'asks the screen for nothing',
    'RFSettingsGather': 'asks its three boxes FIRST and takes none of them when one had no answer (RfFieldsMissed inside it: false, and its callers stay on the page) - dev/test_wholepage/scene_rfsettings',
}
def rf_texts():
    return {os.path.basename(f): open(f, encoding='utf-8', errors='replace').read() for f in sorted(glob.glob(os.path.join(m.TC, 'include', 'RF_*.h')))}
QUESTION = r'if\s*\(\s*(?:WorkLostABox\(\)|RfFieldsMissed\()'
SELF_ASKING = {'RFSettingsGather': r'!RFSettingsGather\(\)\)\s*return\b',
               'EzSyncSliders': r'!EzSyncSliders\(\)\)\s*return\b'}   # (the eleventh review: the Easy page's sliders and switch before a save - all, or none and the save stops)   # (the gathers that ask "was every box answered?" by themselves: the shape every call of one must have)
SELF_BAD = []
def page_lint(texts=None):
    """(The tenth review: a gather is known BY WHAT IT DOES - its name says "Gather", or it holds a KEEP_WHOLE - not from a list of names;
    and the question behind its call must stand RIGHT behind it, a statement of its own: not inside another "if", not in another branch.)"""
    if texts is None: texts = rf_texts()
    FIELD = r'\b(?:FieldNumber|FieldTenths|FieldHundredths|FieldTenthsL|BasFieldTenths|FieldPercent|BasPair)\('
    funcs = kl_functions(texts)
    asks = lambda body: re.search(r'\bWorkLostABox\(\)|\bRfFieldsMissed\(', body) is not None
    gatherers = sorted(f for f, (_, p, body) in funcs.items() if ('Gather' in f or 'KEEP_WHOLE(' in body) and f not in SELF_ASKING)
    for f, how in SELF_ASKING.items():                                                                       # (a gather that asks by itself: every call of it must act on its answer)
        if f not in funcs or not asks(funcs[f][2]): bad_self = '%s is on the list of gathers that ask by themselves, and does not' % f
        else: bad_self = None
        for name in sorted(texts):
            ls = [l.split('//')[0] for l in texts[name].split('\n')]
            for i, s in enumerate(ls):
                two = s + ' ' + (ls[i + 1] if i + 1 < len(ls) else '')                                       # (the "return" may stand on the next line)
                if re.search(r'(?<![\w.>])' + re.escape(f) + r'\s*\(\s*\)', s) and not re.match(r'^(?:FLASHMEM\s+|static\s+)*(?:bool|void)\s+' + re.escape(f) + r'\b', s) and not re.search(how, two):
                    SELF_BAD.append('%s:%d a call of %s does not act on its answer: %s' % (name, i + 1, f, s.strip()[:90]))
        if bad_self: SELF_BAD.append(bad_self)
    GCALL = r'(?<![\w.>])(?:' + '|'.join(re.escape(g) for g in gatherers) + r')\s*\(\s*\)\s*;'
    ONE = r'\s*(?:else\s+)?(?:if\s*\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)\s*)?(?:else\s+)?' + GCALL[:-1].replace(r'\s*;', '') + r'\s*;'   # one more gather's call, under an "if" of its own or not
    head = re.compile(r'^(?:FLASHMEM\s+|static\s+|B211_RARE\s+)*(?:void|bool|int|long|uint8_t|uint16_t|uint32_t|float)\s+([A-Za-z_]\w*)\s*\(')
    bad = list(SELF_BAD); del SELF_BAD[:]; gathers = 0; calls = 0; seen = set()
    for name in sorted(texts):
        lines = texts[name].split('\n')
        fl = []; cur = None
        for i, l in enumerate(lines):
            h = head.match(l)
            if h and not l.split('//')[0].rstrip().endswith(';'):
                if cur: fl.append((cur[0], cur[1], i))
                cur = (h.group(1), i)
        if cur: fl.append((cur[0], cur[1], len(lines)))
        for fn, a, b in fl:
            body = lines[a:b]; text = '\n'.join(x.split('//')[0] for x in body)
            keeps = 'KEEP_WHOLE(' in text
            helper = re.match(r'(?:FieldNumber|FieldTenths|FieldHundredths|FieldTenthsL|BasFieldTenths|FieldPercent|BasPair)$', fn) is not None
            is_gather = fn in gatherers
            if 'Gather' in fn:
                gathers += 1
                if not keeps:
                    seen.add(fn)
                    if fn not in GATHERS_WITHOUT_KEEP: bad.append('%s %s gathers a page with no KEEP_WHOLE: what "no answer" made of a field would stay' % (name, fn))
            for k, l in enumerate(body):
                s = l.split('//')[0]
                if re.match(r'\s*(?:static )?void \w+\(\);\s*$', s): continue      # (a prototype)
                behind = ' '.join(x.split('//')[0] for x in body[k:k + 4])
                if not is_gather:
                    for mm in re.finditer(GCALL, s):
                        calls += 1
                        after = s[mm.end():] + '\n' + '\n'.join(x.split('//')[0] for x in body[k + 1:k + 5])
                        q = re.match(r'(?:' + ONE + r')*\s*' + QUESTION, after)   # right behind it: nothing between but other gathers' calls
                        if not q:
                            bad.append('%s:%d %s calls a gather and does not ask RIGHT BEHIND it whether a box had no answer: %s' % (name, a + k + 1, fn, s.strip()[:80]))
                if k > 0 and not keeps and not helper and re.search(FIELD, s) and 'WorkLostABox()' not in behind and 'RfFieldsMissed(' not in behind:
                    bad.append('%s:%d %s reads a field outside a gather and does not ask whether it had an answer: %s' % (name, a + k + 1, fn, s.strip()[:80]))
    for fn in GATHERS_WITHOUT_KEEP:
        if fn not in seen: bad.append('%s is on the list of gathers that need no keep, and is no longer one' % fn)
    if gathers < 15 or calls < 40: bad.append('the Rotorflight pages\' gathers were not found (%d gathers, %d calls)' % (gathers, calls))
    return bad, gathers, calls
PAGE_LINT_SELFTEST = [   # (what, header, the line, what it becomes): page_lint must speak of each (the tenth review's probes)
    ('a gather called with the question in another branch', 'RF_Filters.h', '    if (CurrentView == FILTER2VIEW) FltGather();\n    if (WorkLostABox()) return;', '    if (CurrentView == FILTER2VIEW) FltGather();\n    if (Flt_Was_Edited) { if (WorkLostABox()) return; }'),
    ('... under an "if" with no brackets', 'RF_Filters.h', '    if (CurrentView == FILTER2VIEW) FltGather();\n    if (WorkLostABox()) return;', '    if (CurrentView == FILTER2VIEW) FltGather();\n    if (Flt_Was_Edited)\n        if (WorkLostABox()) return;'),
    ('... with other work between the gather and the question', 'RF_Filters.h', '    if (CurrentView == FILTER2VIEW) FltGather();\n    if (WorkLostABox()) return;', '    if (CurrentView == FILTER2VIEW) FltGather();\n    FltShow();\n    if (WorkLostABox()) return;'),
    ('a gather called with no question at all', 'RF_Filters.h', '    if (CurrentView == FILTER2VIEW) FltGather();\n    if (WorkLostABox()) return;', '    if (CurrentView == FILTER2VIEW) FltGather();'),
    ('a new gather by another name, called with no question', 'RF_Filters.h', 'FLASHMEM void FilterWasEdited() { if (!FltHave) return; SendCommand((char *)"vis b3,1"); Flt_Was_Edited = true; }',
     'FLASHMEM static void FltTake()\n{\n    KEEP_WHOLE(want, FltWant);\n    WrU16(FltWant, 2, FieldNumber("tn2", 0, 1000));\n}\nFLASHMEM void FilterWasEdited() { SendCommand((char *)"vis b3,1"); Flt_Was_Edited = true; FltTake(); FltShow(); }'),
    ('a field helper of a Rotorflight page used outside a gather, no question', 'RF_Filters.h', 'FLASHMEM void FilterWasEdited() { if (!FltHave) return; SendCommand((char *)"vis b3,1"); Flt_Was_Edited = true; }',
     'FLASHMEM void FilterWasEdited() { if (!FltHave) return; SendCommand((char *)"vis b3,1"); Flt_Was_Edited = true; }\nFLASHMEM void FilterQuick()\n{\n    WrU16(FltWant, 2, FieldNumber("tn2", 0, 1000));\n    FltShow();\n}'),
    ('a gather with no keep at all', 'RF_FcSetup.h', '    KEEP_WHOLE(want, CalWant);', ''),
    ('the settings page\'s gather called with no look at its answer', 'RF_RotorFlight.h', '    if (!RFSettingsGather())\n        return;', '    RFSettingsGather();'),
    ('... its question taken out of it', 'RF_RotorFlight.h', '    if (RfFieldsMissed("page RFSetupView"))\n        return false;', ''),
]
def page_lint_selftest(texts):
    base = set(page_lint(texts)[0]); bad = []
    for what, f, old, new in PAGE_LINT_SELFTEST:
        if texts[f].count(old) != 1: bad.append('the page check\'s own test: the line to change is not in %s any more, or stands there twice (%s)' % (f, what)); continue
        t2 = dict(texts); t2[f] = texts[f].replace(old, new)
        if not (set(page_lint(t2)[0]) - base): bad.append('the page check does NOT SEE this any more: ' + what)
    return bad, len(PAGE_LINT_SELFTEST)

# ---- WHAT A GATHER WRITES IS KEPT WHOLE (the tenth review, 15 Nov 2026). page_lint looked for a KEEP_WHOLE in every gather - not
# for WHAT is kept: the Battery sensors page's gather kept one buffer and wrote two others, which "no answer" then left at the
# floor of their ranges. Read out of the source here: every name a gather writes to - left of an "=", counted up or down, or handed
# to a routine that writes through it (WrU16, PutS16, memcpy ... found by what they do), by itself or by a routine it calls - is a
# name of its own, or is held by a KEEP_WHOLE of that gather (or of the routine that wrote it). What is not: on KEEP_ALLOW, with
# its reason. The check is tried on changed copies of the headers (KEEP_SELFTEST): each change must be seen.
KL_TYPE = r'(?:unsigned\s+)?(?:int|long|char|bool|float|double|u?int(?:8|16|32|64)_t|size_t|auto|[A-Z]\w*)'
KL_LIB_WRITERS = {'memcpy': (0,), 'memmove': (0,), 'memset': (0,), 'strlcpy': (0,), 'strcpy': (0,), 'strncpy': (0,), 'snprintf': (0,), 'sprintf': (0,), 'strlcat': (0,), 'strcat': (0,)}
KL_WORDS = {'return', 'else', 'case', 'goto', 'new', 'delete', 'sizeof', 'if', 'for', 'while', 'switch', 'do', 'const', 'static', 'struct', 'typedef', 'break', 'continue'}

def kl_strip(text):
    """Comments and what stands between quotes taken out (the lengths kept: places stay places)."""
    text = re.sub(r'"(?:\\.|[^"\\\n])*"', lambda mo: '"' + ' ' * (len(mo.group(0)) - 2) + '"', text)
    text = re.sub(r"'(?:\\.|[^'\\\n])'", lambda mo: "'" + ' ' * (len(mo.group(0)) - 2) + "'", text)
    text = re.sub(r'//[^\n]*', lambda mo: ' ' * len(mo.group(0)), text)
    return re.sub(r'/\*.*?\*/', lambda mo: re.sub(r'[^\n]', ' ', mo.group(0)), text, flags=re.S)

def kl_match(text, i, open_, close):
    """text[i] is open_: the place of its partner (-1: none)."""
    depth = 0
    for j in range(i, len(text)):
        if text[j] == open_: depth += 1
        elif text[j] == close:
            depth -= 1
            if depth == 0: return j
    return -1

def kl_split(args):
    """A list between brackets, cut at its own commas."""
    out, depth, cur = [], 0, ''
    for ch in args:
        if ch in '([{': depth += 1
        elif ch in ')]}': depth -= 1
        if ch == ',' and depth == 0: out.append(cur); cur = ''
        else: cur += ch
    if cur.strip() or out: out.append(cur)
    return out

def kl_base(expr):
    """The name an expression stands on: casts, brackets, & and * in front taken off."""
    e = (expr or '').strip()
    while True:
        e2 = re.sub(r'^\(\s*(?:const\s+)?' + KL_TYPE + r'\s*[&*]*\s*\)\s*', '', e)          # (a cast)
        e2 = re.sub(r'^[&*]\s*', '', e2)
        if e2.startswith('(') and kl_match(e2, 0, '(', ')') == len(e2) - 1: e2 = e2[1:-1].strip()
        if e2 == e: break
        e = e2
    mo = re.match(r'[A-Za-z_]\w*', e)
    return mo.group(0) if mo else None

def kl_functions(texts):
    """Every function that begins in the first column, of every header given: name -> (file, its parameters, its body)."""
    head = re.compile(r'^(?:FLASHMEM\s+|static\s+|B211_RARE\s+|inline\s+)*(?:const\s+)?(?:unsigned\s+)?(?:void|bool|int|long|char|float|double|u?int(?:8|16|32|64)_t|size_t|[A-Z]\w*)\s*[&*]*\s*([A-Za-z_]\w*)\s*\(', re.M)
    funcs = {}
    for name in sorted(texts):
        t = kl_strip(texts[name]); pos = 0
        while True:
            mo = head.search(t, pos)
            if not mo: break
            p0 = mo.end() - 1; p1 = kl_match(t, p0, '(', ')')
            if p1 < 0: pos = mo.end(); continue
            rest = t[p1 + 1:]; k = len(rest) - len(rest.lstrip())
            if rest[k:k + 1] != '{': pos = p1 + 1; continue                             # (a prototype)
            b0 = p1 + 1 + k; b1 = kl_match(t, b0, '{', '}')
            if b1 < 0: pos = p1 + 1; continue
            funcs[mo.group(1)] = (name, t[p0 + 1:p1], t[b0:b1 + 1])
            pos = b1 + 1
    return funcs

def kl_decls(params, body):
    """The names a function has of its own: name -> (None: a value; 'ptr' / 'ref': another name for something else,
    what its first value stands on, is it a parameter)."""
    loc = {}
    for prm in kl_split(params):
        prm = prm.split('=')[0].strip()
        mo = re.search(r'([A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*$', prm)
        if not mo or prm == 'void': continue
        kind = None
        if not re.match(r'const\b', prm): kind = 'ref' if '&' in prm else 'ptr' if ('*' in prm or mo.group(2)) else None
        loc[mo.group(1)] = (kind, None, True)
    for mo in re.finditer(r'(?:^|[;{}(])\s*(?:static\s+)?(const\s+)?(' + KL_TYPE + r')\s+((?:[&*]\s*)*)([A-Za-z_]\w*)\s*(?=[=;,\[)])', body):
        if mo.group(2) in KL_WORDS or mo.group(4) in KL_WORDS: continue
        i = mo.start(3); depth = 0; cur = ''; parts = []                                # this name, and the others of the same statement
        for j in range(i, len(body)):
            ch = body[j]
            if ch in '([{': depth += 1
            elif ch in ')]}':
                if depth == 0: parts.append(cur); break                                 # (a for's head ends here)
                depth -= 1
            if ch == ';' and depth == 0: parts.append(cur); break
            if ch == ',' and depth == 0: parts.append(cur); cur = ''
            else: cur += ch
        for part in parts:
            pm = re.match(r'\s*((?:[&*]\s*)*)([A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*(?:=(.*))?$', part, re.S)
            if not pm: continue
            star = pm.group(1).replace(' ', '')
            kind = None if (pm.group(3) or not star or mo.group(1)) else ('ref' if star.startswith('&') else 'ptr')   # (to const: nothing is written through it)
            loc[pm.group(2)] = (kind, kl_base(pm.group(4)) if (kind and pm.group(4)) else None, False)
    return loc

KL_LV = r'(?<![\w.>\]])([A-Za-z_]\w*)((?:\s*\[(?:[^\[\]]|\[[^\[\]]*\])*\]|\s*(?:\.|->)\s*\w+)*)'
def kl_written(body, writers):
    """What a body writes to: (name, through it?) - left of an "=" (not where the name is made), counted up or down, or handed to
    a routine that writes through that place. "Through it": name[..] = , name.x = , name->x = , *name = , or handed on."""
    w = set()
    for mo in re.finditer(KL_LV + r'\s*(?:[-+|&^*/%]|<<|>>)?=(?!=)', body):
        before = body[max(0, mo.start() - 80):mo.start()]
        if re.search(r'(?:^|[;{}(,])\s*(?:static\s+)?(?:const\s+)?' + KL_TYPE + r'\s+(?:[&*]\s*)*$', before): continue      # (the name is made here: its first value)
        deref = re.search(r'(?:^|[;{})])\s*\*\s*$', before) is not None
        w.add((mo.group(1), bool(mo.group(2).strip()) or deref))
    for mo in re.finditer(r'(?:\+\+|--)\s*' + KL_LV, body): w.add((mo.group(1), bool(mo.group(2).strip())))
    for mo in re.finditer(KL_LV + r'\s*(?:\+\+|--)', body): w.add((mo.group(1), bool(mo.group(2).strip())))
    for mo in re.finditer(r'(?<![\w.>])([A-Za-z_]\w*)\s*\(', body):
        idxs = writers.get(mo.group(1))
        if not idxs: continue
        e = kl_match(body, mo.end() - 1, '(', ')')
        if e < 0: continue
        args = kl_split(body[mo.end():e])
        for i in idxs:
            if i < len(args) and kl_base(args[i]): w.add((kl_base(args[i]), True))
    return {x for x in w if x[0] not in KL_WORDS}

def kl_analyse(texts):
    """name of every function -> the names it writes to (by itself or by what it calls) that no KEEP_WHOLE on the way holds."""
    funcs = kl_functions(texts)
    decls = {f: kl_decls(p, b) for f, (_, p, b) in funcs.items()}
    pnames = {}
    for f, (_, p, b) in funcs.items():
        pnames[f] = []
        for x in kl_split(p):
            mo = re.search(r'([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*$', x.split('=')[0].strip())
            pnames[f].append(mo.group(1) if mo and x.strip() != 'void' else None)
    def targets(f, body, writers):
        """What the body really writes to: its own other-names followed to what they stand on."""
        out = set()
        for name, through in kl_written(body, writers):
            seen = set()
            while True:
                d = decls[f].get(name)
                if d is None: out.add(name); break                                      # not its own: a global
                kind, target, is_param = d
                if kind is None: break                                                  # a value of its own
                if kind == 'ptr' and not through: break                                 # (the pointer itself is set: nothing is written through it)
                if is_param or not target or target in seen: out.add(name); break       # through a parameter - or its own other-name whose target was not found
                seen.add(name); name = target; through = True
        return out
    writers = dict(KL_LIB_WRITERS)
    while True:                                                                         # the routines that write through a parameter (until nothing more is found)
        grew = False
        for f, (_, p, b) in funcs.items():
            wr = targets(f, b, writers)
            idxs = tuple(i for i, n in enumerate(pnames[f]) if n and n in wr)
            if idxs and writers.get(f) != idxs: writers[f] = idxs; grew = True
        if not grew: break
    own, keeps, calls = {}, {}, {}
    for f, (_, p, b) in funcs.items():
        own[f] = {n for n in targets(f, b, writers) if not (n in decls[f] and decls[f][n][2])}   # (what goes through a parameter is the caller's: found at the call)
        ks = set()
        for mo in re.finditer(r'KEEP_WHOLE\(\s*\w+\s*,', b):
            e = kl_match(b, b.index('(', mo.start()), '(', ')')
            base = kl_base(b[mo.end():e])
            while base:
                ks.add(base); d = decls[f].get(base)
                base = d[1] if (d and d[0] and d[1] and d[1] not in ks) else None
        keeps[f] = ks
        calls[f] = {mo.group(1) for mo in re.finditer(r'(?<![\w.>])([A-Za-z_]\w*)\s*\(', b) if mo.group(1) in funcs and mo.group(1) != f}
    def uncovered(f, stack):
        if f in stack: return set()
        u = set(own[f])
        for c in calls[f]: u |= uncovered(c, stack + (f,))
        return u - keeps[f]
    return {f: (funcs[f][0], uncovered(f, ()), keeps[f]) for f in funcs}, writers

KEEP_ALLOW = {   # (gather, name): why that write needs no keep
}
def keep_lint(texts):
    table, writers = kl_analyse(texts)
    bad = []; gathers = 0; names = 0; seen = set()
    funcs = kl_functions(texts)
    for f in sorted(table):
        if 'Gather' not in f and 'KEEP_WHOLE(' not in funcs[f][2]: continue             # (the eleventh review: a gather is known by what it does - "ReadEditedRateValues" keeps too)
        name, unc, keeps = table[f]
        gathers += 1; names += len(keeps)
        if f in GATHERS_WITHOUT_KEEP: continue                                          # (what it leaves unkept is asked of every gather that calls it: it is in their sums)
        for n in sorted(unc):
            if (f, n) in KEEP_ALLOW: seen.add((f, n)); continue
            bad.append('%s %s writes to %s and no KEEP_WHOLE holds it: what "no answer" made of a field would stay there' % (name, f, n))
    for k in KEEP_ALLOW:
        if k not in seen: bad.append('%s / %s is on the list of writes that need no keep, and is no longer one' % k)
    for w in ('WrU16', 'WrS16', 'PutS16', 'BasPutU16'):
        if writers.get(w) != (0,): bad.append('the keep check no longer finds that %s writes through its first parameter' % w)
    if gathers < 15 or names < 20: bad.append('the keep check did not find the gathers and their keeps (%d gathers, %d kept names)' % (gathers, names))
    return bad, gathers, names

def kl_change(texts, f, fn, old, new):
    """A copy of the headers with `old` made `new` inside routine fn of header f (None: the line is not there)."""
    t = texts[f]; mo = None
    for x in re.finditer(r'^[^\n(/]*\b' + re.escape(fn) + r'\s*\([^\n]*$', t, re.M):
        if not x.group(0).split('//')[0].rstrip().endswith(';'): mo = x; break          # (the routine itself, not its announcement)
    if not mo: return None
    a = mo.start(); b = t.find('\n}\n', a)
    one = t[a:t.index('\n', a)]
    if one.count('{') and one.count('{') == one.count('}'): b = t.index('\n', a)        # (a routine of one line)
    if b < 0 or t[a:b].count(old) != 1: return None
    t2 = dict(texts); t2[f] = t[:a] + t[a:b].replace(old, new) + t[b:]
    return t2

KEEP_SELFTEST = [   # (what, header, routine, the line, what it becomes): each must make the check speak
    ('the Battery sensors page: the voltage sensor\'s buffer not kept (the tenth review\'s finding)', 'RF_FcSetup.h', 'BatGather', 'KEEP_WHOLE(vm, VmWant);', ''),
    ('... the current sensor\'s', 'RF_FcSetup.h', 'BatGather', 'KEEP_WHOLE(cm, CmWant);', ''),
    ('a keep of the wrong thing', 'RF_FcSetup.h', 'BatGather', 'KEEP_WHOLE(vm, VmWant);', 'KEEP_WHOLE(vm, VmRaw);'),
    ('what a routine CALLED by the gather writes (the directions)', 'RF_Travel.h', 'TravGatherPage1', 'KEEP_WHOLE(in, TravInWant);', ''),
    ('what goes through two routines (BasPair, BasPutU16)', 'RF_Basics.h', 'BasGatherPage2', 'KEEP_WHOLE(want, BasMotWant);', ''),
    ('a row written through another name for it', 'RF_Adjust.h', 'AdjGather', 'KEEP_WHOLE(row, r);', ''),
    ('a new setting written straight from a field', 'RF_Filters.h', 'FltGather', 'KEEP_WHOLE(want, FltWant);', 'KEEP_WHOLE(want, FltWant); FeatWant = (uint32_t)FieldNumber("tn9", 0, 9);'),
    ('written through a pointer of the gather\'s own', 'RF_FcSetup.h', 'CalGather', 'KEEP_WHOLE(want, CalWant);', 'KEEP_WHOLE(want, CalWant); uint8_t *q = CalRaw; q[2] = (uint8_t)FieldNumber("tn9", 0, 9);'),
    ('handed to a routine that writes through it', 'RF_FcSetup.h', 'BbGather', 'KEEP_WHOLE(want, BbWant);', 'KEEP_WHOLE(want, BbWant); WrU16(BbRaw, 0, FieldNumber("tn9", 0, 9));'),
    ('counted up', 'RF_Rescue.h', 'RescueGatherPage1', 'KEEP_WHOLE(want, RescueWant);', 'KEEP_WHOLE(want, RescueWant); if (FieldNumber("tn9", 0, 9)) ++RescueStep;'),
    ('copied into', 'RF_Beeper.h', 'BpGather', 'KEEP_WHOLE(want, BpWant);', 'KEEP_WHOLE(want, BpWant); memcpy(BpRaw, BpWant, 4);'),
    ('a member of a structure set', 'RF_Servos.h', 'ServoGather', 'KEEP_WHOLE(want, ServoWant);', 'KEEP_WHOLE(want, ServoWant); AdjRows[0].v[1] = FieldNumber("tn9", 0, 9);'),
    ('written through a dereferenced pointer', 'RF_Servos.h', 'ServoGather', 'KEEP_WHOLE(want, ServoWant);', 'KEEP_WHOLE(want, ServoWant); uint8_t *q = ServoRaw; *q = (uint8_t)FieldNumber("tn9", 0, 9);'),
]
def keep_selftest(texts):
    base = set(keep_lint(texts)[0]); bad = []
    for what, f, fn, old, new in KEEP_SELFTEST:
        t2 = kl_change(texts, f, fn, old, new)
        if t2 is None: bad.append('the keep check\'s own test: the line to change is not in %s %s any more (%s)' % (f, fn, what)); continue
        if not (set(keep_lint(t2)[0]) - base): bad.append('the keep check does NOT SEE this any more: ' + what)
    return bad, len(KEEP_SELFTEST)

# ... and a routine of the OTHER files that keeps something whole (Model options, the switches page): every name it writes to BY
# ITSELF is one of its keeps, or on the list. (What the routines it calls write is not asked here: they fly the model.)
KEEP_ALLOW_OTHER = {
    ('ReadRXOptionsView', 'NextionTextMissed'): 'the flag "a text box had no answer", cleared before the page is read: not a setting',
    ('ReadNewSwitchFunction', 'CurrentView'): 'the page this board believes: the routine ends on the switches page - not read from a box',
    ('ExitMacrosView', 'CurrentView'): 'the page this board believes: written when the macro has been taken whole and the page is left - not read from a box',
    ('ExitMacrosView', 'UseMacros'): 'set once a macro has been taken whole (behind "was every box answered?") - not read from a box',
    ('PopulateMacrosView', 'PreviousMacroNumber'): 'which macro the page\'s boxes hold: set when this board has written them - behind "was every box answered?"',
}
def keep_lint_other(texts, rf):
    """texts: every file; rf: the Rotorflight headers (their writers through a parameter are known from there)."""
    writers = kl_analyse(rf)[1]
    bad = []; found = 0; seen = set()
    funcs = kl_functions({k: v for k, v in texts.items() if k not in rf})
    for f in sorted(funcs):
        name, p, body = funcs[f]
        if 'KEEP_WHOLE(' not in body: continue
        found += 1
        decl = kl_decls(p, body)
        keeps = set()
        for mo in re.finditer(r'KEEP_WHOLE\(\s*\w+\s*,', body):
            e = kl_match(body, body.index('(', mo.start()), '(', ')'); base = kl_base(body[mo.end():e])
            if base: keeps.add(base)
        for n_, through in sorted(kl_written(body, writers)):
            if n_ in decl or n_ in keeps: continue
            if (f, n_) in KEEP_ALLOW_OTHER: seen.add((f, n_)); continue
            bad.append('%s %s keeps its page whole - and writes to %s, which no KEEP_WHOLE of it holds' % (name, f, n_))
    for k in KEEP_ALLOW_OTHER:
        if k not in seen: bad.append('%s / %s is on the list of writes that need no keep, and is no longer one' % k)
    if found < 4: bad.append('the keep check did not find Model options, the switches page and the macros page\'s two routines (%d routines with a keep outside the Rotorflight pages)' % found)
    return bad, found
KEEP_OTHER_SELFTEST = [
    ('inside a routine with keeps of other things: a local, then a setting no keep holds', 'MenuOptions.h', '    SendCommand(ProgressStart);\n    {\n        const uint32_t v = GetValue(c1);', '    { const uint32_t q = GetValue(c1); LEDBrightness = q; }\n    SendCommand(ProgressStart);\n    {\n        const uint32_t v = GetValue(c1);'),
    ('a keep taken away from Model options', 'MenuOptions.h', 'KEEP_WHOLE(sfv, SFV);', ''),
]
def keep_other_selftest(texts, rf):
    base = set(keep_lint_other(texts, rf)[0]); bad = []
    for what, f, old, new in KEEP_OTHER_SELFTEST:
        if texts[f].count(old) != 1: bad.append('the keep check\'s own test: the line to change is not in %s any more, or stands there twice (%s)' % (f, what)); continue
        t2 = dict(texts); t2[f] = texts[f].replace(old, new)
        if not (set(keep_lint_other(t2, rf)[0]) - base): bad.append('the keep check does NOT SEE this any more: ' + what)
    return bad, len(KEEP_OTHER_SELFTEST)

# A GATHER IS KNOWN BY WHAT IT DOES (the eleventh review, reviewer B: "ReadEditedRateValues is a gather by another name" - no check saw a routine that
# takes a page box by box, "no answer keeps the value in hand", unless it was NAMED Gather or held a keep). Every routine, of every file, that asks the
# screen for more than one box - two asks, or one inside a loop - holds a KEEP_WHOLE (and is then a gather: page_lint asks for the question behind
# each call of it), or asks "was every box answered?" by itself (SELF_ASKING), or stands on this list with why it needs neither.
ASK_NAMES = ('GetText', 'GetValue', 'getvalue', 'GetOtherValue', 'FieldNumber', 'FieldTenths', 'FieldHundredths', 'FieldTenthsL', 'BasFieldTenths', 'FieldPercent', 'BasPair', 'MacroValue')
def ask_pattern(more=()): return r'(?<![\w.>])(?:' + '|'.join(list(ASK_NAMES) + sorted(more)) + r')\s*\('
ASK_CALL = ask_pattern()
ASK_HELPERS = ('FieldNumber', 'FieldTenths', 'FieldHundredths', 'FieldTenthsL', 'BasFieldTenths', 'FieldPercent', 'BasPair', 'MacroValue', 'GetValue')   # (each reads ONE field - BasPair the two halves of one - for a gather that keeps)
OLDER = "an older page's OK: each box is a setting of its own - one with no answer keeps what it had, the others are taken, and the pilot is told by the sound and the log (known and accepted: the residuals' 8)"
ASKERS = {
    'AddWords': 'writes no setting: the words beside two numbers of the governor page - both asked first, and with no answer the words stay',
    'AdjustBarMoved': "the bar's own numbers, behind its token (RF_Jobs.h JobsBarMoved): the tap, then both dividers asked before either is taken - neither, when one had no answer",
    'SwitchBarMoved': "the two ends of a switch's ON zone, behind the bar's token: no answer is 0, and a zone that begins at 0 is refused - both ends, or neither",
    'Collect_data_from_dialog': 'the save / restore dialog: all six asked, and NOTHING is chosen when one had no answer (WorkLostABox at its end)',
    'InputsViewEnd': 'read into copies, which become the map only when every box asked for has answered',
    'CheckDualRatesScreen': "a page's own look at itself, twice a second: each box by itself, and a change with no button pressed first asks whether the screen is the same one",
    'CheckModelName': 'as above: both lists or neither, and the same question before another model is loaded',
    'ButtonWasPressed': "main.cpp's word handlers, each a rule of its own: the colours page takes all four or none (pinned below); the curve page's three switches choose nothing without an answer and are drawn again as in hand; the receiver battery's eight boxes (\"RXBAT\": two choices) are all asked before either is taken - WorkLostABox; the failsafe set is FailSafeSetFromPage's, whole; the rest ask one box each (every one is in the box check above)",
    'ImageScrollStop': "the SAME one box (the list's row) asked five times in half a second while the picture comes up: each answer replaces the one before, and with no answer the picture's name stays as it was (ChosenFileRow)",
    'RenameFile': "two questions of different things, each looked at by itself: the file's name on the list (no answer: nothing is done), then the new name typed into the question (GetBackupFilename: no answer is no name)",
    'BuddyChViewEnd': OLDER, 'EndAudioVisualView': OLDER, 'EndBuddyView': OLDER, 'EndReverseView': OLDER, 'OptionView2Start': OLDER,
    'OptionView3End': OLDER, 'ReadDualRatesFromScreen': OLDER, 'SystemPage1End': OLDER,
}
def kl_loops(body):
    """the bodies of a routine's for and while loops: (from, to)"""
    out = []
    for mo in re.finditer(r'\b(?:for|while)\s*\(', body):
        e = kl_match(body, mo.end() - 1, '(', ')')
        if e < 0: continue
        rest = body[e + 1:]; k = len(rest) - len(rest.lstrip())
        if rest[k:k + 1] == '{':
            b1 = kl_match(body, e + 1 + k, '{', '}')
            if b1 > 0: out.append((e + 1 + k, b1))
        else:
            semi = body.find(';', e + 1)
            if semi > 0: out.append((e + 1, semi))
    return out
def askers_functions(texts):
    """kl_functions, and the routines kept in fast memory too (FASTRUN: main.cpp's ButtonWasPressed)"""
    return kl_functions({k: re.sub(r'(?m)^FASTRUN\s+', '', v) for k, v in texts.items()})
def ask_wrappers(funcs):
    """(the twelfth review: a box asked through a "read one field" helper of one's own was not seen - EndBankNames asks six through BankNameFromPage.)
    The routines that ask the screen for exactly ONE box, outside any loop, AND HAND IT BACK (they return a value, or fill a reference): a call of one
    of them IS an asking - and so on, wrapper of wrapper. (A whole page's routine that happens to ask one box is no such helper: it hands nothing back.)"""
    wr = set()
    while True:
        pat = ask_pattern(wr); new = set()
        for f, (name, params, body) in funcs.items():
            if f in ASK_NAMES or f in wr: continue
            if not (re.search(r'\breturn\s+[^;\s]', body) or '&' in params): continue
            asks = [mo.start() for mo in re.finditer(pat, body)]
            if len(asks) == 1 and not any(a <= asks[0] <= b for a, b in kl_loops(body)): new.add(f)
        if not new: return wr
        wr |= new
def askers_lint(texts):
    funcs = askers_functions(texts); bad = []; found = 0; seen = set()
    ASKS = ask_pattern(ask_wrappers(funcs))
    for f in sorted(funcs):
        name, params, body = funcs[f]
        asks = [mo.start() for mo in re.finditer(ASKS, body)]
        if not asks or f in ASK_HELPERS: continue
        loops = kl_loops(body)
        if len(asks) < 2 and not any(a <= x <= b for x in asks for a, b in loops): continue
        found += 1
        if 'KEEP_WHOLE(' in body or f in SELF_ASKING: continue
        if f in ASKERS: seen.add(f); continue
        bad.append('%s %s asks the screen for more than one box and holds no KEEP_WHOLE: it is a gather - whole, or not at all - or it goes on the list (ASKERS) with why it need not be' % (name, f))
    for f in ASKERS:
        if f not in seen: bad.append('%s is on the list of routines that ask for more than one box and need no keep, and is no longer one' % f)
    if found < 40: bad.append('the check of routines that ask for more than one box did not find them (%d)' % found)
    return bad, found
ASKERS_SELFTEST = [   # (what, file, the text, what it becomes): each must make the check speak
    ('a page taken box by box, "no answer keeps the value in hand", in a routine not named Gather (the reviewer\'s own probe)', 'RF_Filters.h',
     'FLASHMEM void FilterWasEdited() { if (!FltHave) return; SendCommand((char *)"vis b3,1"); Flt_Was_Edited = true; }',
     'FLASHMEM static void FltReadShown()\n{\n    char t[12];\n    if (GetText((char *)"tn2", t, sizeof(t)) == 0) return;\n    WrU16(FltWant, 2, atol(t));\n    if (GetText((char *)"tn5", t, sizeof(t)) == 0) return;\n    FltWant[26] = (uint8_t)atol(t);\n}\nFLASHMEM void FilterWasEdited() { if (!FltHave) return; SendCommand((char *)"vis b3,1"); Flt_Was_Edited = true; }'),
    ('one ask inside a loop', 'RF_Filters.h', 'FLASHMEM void FilterWasEdited() { if (!FltHave) return; SendCommand((char *)"vis b3,1"); Flt_Was_Edited = true; }',
     'FLASHMEM static void FltReadAll()\n{\n    for (int i = 0; i < 4; ++i)\n    {\n        const uint32_t v = GetValue(FltNames[i]);\n        if (v != 65535) FltWant[i] = (uint8_t)v;\n    }\n}\nFLASHMEM void FilterWasEdited() { if (!FltHave) return; SendCommand((char *)"vis b3,1"); Flt_Was_Edited = true; }'),
    ('the rates page\'s keep taken away again', 'RF_Rates.h', '    KEEP_WHOLE(rates, Rate_Values);\n    KEEP_WHOLE(cut, RfValueWasCut);\n    const float *f = RatesFactors(Rate_Values[0]);', '    const float *f = RatesFactors(Rate_Values[0]);'),
    ('the macros page\'s keep taken away', 'MenuOptions.h', '    KEEP_WHOLE(macros, MacrosBuffer);\n    const uint32_t shown = GetValue(MacroNumber);\n    if (shown == 65535)', '    const uint32_t shown = GetValue(MacroNumber);\n    if (shown == 65535)'),
]
def askers_selftest(texts):
    base = set(askers_lint(texts)[0]); bad = []
    for what, f, old, new in ASKERS_SELFTEST:
        if texts[f].count(old) != 1: bad.append('the askers check\'s own test: the text to change is not in %s any more, or stands there twice (%s)' % (f, what)); continue
        t2 = dict(texts); t2[f] = texts[f].replace(old, new)
        if not (set(askers_lint(t2)[0]) - base): bad.append('the askers check does NOT SEE this any more: ' + what)
    return bad, len(ASKERS_SELFTEST)

# WHAT THE PILOT TYPED STAYS ON THE PAGE, read from the source (the eleventh review, reviewer B: after the tenth review's cure for two Saves, the same
# redraw stood behind Battery's and Beeper's Save, Calibrate, Erase, and at the end of nine pages' messages - and no check looked for it).
#  (T) at the end of a page's message ("... MsgUntil") nothing is drawn: the message goes, the screen draws what lay under it;
#  (R) a routine that draws a page's TYPED fields (TYPED_SHOWS) behind a box does it with those fields left as the screen has them
#      (FsShowKeepingTyped, or between RfKeepTyped = true and = false) - unless a gather stands in front of it, so that what is in hand is what
#      was typed; and right behind "a box had NO ANSWER" (RfFieldsMissed) always so. The routines on TYPED_ALLOW draw behind a box of a state
#      machine's own, where nothing typed is waiting.
TYPED_BOX = r'(?<![\w.>])(?:FsRefused|FsFail|MsgBox|GetConfirmation|GetSaveOrDiscard|RfSaveFirst|RfBoxOrQuiet|RfFieldsMissed)\s*\('
TYPED_SHOWS = ('BatShow', 'BbShow', 'CalShow', 'BpShow', 'FltShow', 'RescueShow', 'ServoShow', 'ServoShowEdits', 'TravShow', 'BasShow', 'EzShowAll', 'EzShowSliders')
# (the fourteenth review: seven routines stood here with "a step of the page's own save failed: what is in hand is what the job gathered before it
#  began" - true, and no excuse: a save runs for seconds, the busy message covers the middle of the page only, and what he typed meanwhile was drawn
#  over. BatFail, BpFail, BasFail, FltFail, RescueFail, TravFail and EzFinish keep what was typed now, as BbFail and CalFail do.)
TYPED_ALLOW = {'BlackboxPoll': 'the read has just ended ("This flight controller has no black box"): nothing has been typed yet',
               'EzFinish': 'its FAILURE keeps the sliders as he left them (held by a check of its own, in main()); its GOOD end shows what was saved and read back - a Save\'s own end draws what the flight controller has (decided: it shows)'}
def typed_lint(texts):
    funcs = kl_functions(texts)
    gatherers = sorted(f for f, (_, p, body) in funcs.items() if ('Gather' in f or 'KEEP_WHOLE(' in body or f in SELF_ASKING))
    GCALL = r'(?<![\w.>])(?:' + '|'.join(re.escape(g) for g in gatherers) + r'|FieldNumber|FieldTenths|FieldHundredths|FieldTenthsL|BasFieldTenths|FieldPercent|BasPair)\s*\('
    # (the twelfth review: a redraw through a helper - "BbDone("", true)", a routine of one's own holding "CalHead(); CalShow();" - was not seen.)
    # A routine that calls a show with the typed fields NOT kept is itself a draw of them, and so on, helper of helper.
    def plain_show(body, pat):
        keeps = [(mo.start(), kl_match(body, body.index('(', mo.start()), '(', ')')) for mo in re.finditer(r'FsShowKeepingTyped\s*\(', body)]
        spans = [(mo.end(), body.find('RfKeepTyped = false', mo.end())) for mo in re.finditer(r'RfKeepTyped\s*=\s*true\s*;', body)]
        return any(not (any(a <= mo.start() <= b for a, b in keeps) or any(a <= mo.start() <= b for a, b in spans if b > 0)) for mo in re.finditer(pat, body))
    helpers = set()
    while True:
        pat = r'(?<![\w.>])(' + '|'.join(list(TYPED_SHOWS) + sorted(helpers)) + r')\s*\('
        new = set(f for f, (_, p, body) in funcs.items() if f not in TYPED_SHOWS and f not in helpers and 'Poll' not in f and plain_show(body, pat))
        if not new: break
        helpers |= new
    SHOWS = r'(?<![\w.>])(' + '|'.join(list(TYPED_SHOWS) + sorted(helpers)) + r')\s*\('
    bad = []; seen = set(); ends = 0; shows = 0
    for f in sorted(funcs):
        name, params, body = funcs[f]
        for mo in re.finditer(r'if\s*\(\s*\w+MsgUntil\s*&&', body):                 # (T)
            j = kl_match(body, body.index('(', mo.start()), '(', ')')
            rest = body[j + 1:]; s = rest.lstrip()
            blk = rest[rest.index('{'):kl_match(rest, rest.index('{'), '{', '}') + 1] if s.startswith('{') else rest[:rest.index(';') + 1]
            ends += 1
            if re.search(r'(?<![\w.>])[A-Z]\w*Show\w*\s*\(', blk):
                bad.append('%s %s: the end of its message draws the page - what was typed since is written over (the message goes; the screen draws what lay under it)' % (name, f))
        boxes = [mo.start() for mo in re.finditer(TYPED_BOX, body)]                      # (R)
        if not boxes: continue
        gathers = [mo.start() for mo in re.finditer(GCALL, body)]
        keeps = [(mo.start(), kl_match(body, body.index('(', mo.start()), '(', ')')) for mo in re.finditer(r'FsShowKeepingTyped\s*\(', body)]
        spans = [(mo.end(), body.find('RfKeepTyped = false', mo.end())) for mo in re.finditer(r'RfKeepTyped\s*=\s*true\s*;', body)]
        missed = []                                                                      # behind each "if (RfFieldsMissed(...))": the gather FAILED there
        for mo in re.finditer(r'if\s*\(\s*RfFieldsMissed\s*\(', body):
            j = kl_match(body, body.index('(', mo.start()), '(', ')')
            rest = body[j + 1:]; s = rest.lstrip(); off = j + 1 + (len(rest) - len(s))
            missed.append((off, kl_match(body, off, '{', '}') if s.startswith('{') else body.index(';', off)))
        for mo in re.finditer(SHOWS, body):
            pos = mo.start()
            if not any(b < pos for b in boxes): continue
            shows += 1
            if any(a <= pos <= b for a, b in keeps) or any(a <= pos <= b for a, b in spans if b > 0): continue
            lost = any(a <= pos <= b for a, b in missed)
            if not lost and any(g < pos for g in gathers): continue
            if f in TYPED_ALLOW: seen.add(f); continue
            bad.append('%s %s: %s() behind a box %s - what was typed and not yet taken is written over (FsShowKeepingTyped, or the gather first)' % (name, f, mo.group(1), 'that says a box had NO ANSWER' if lost else 'with no gather in front of it'))
    for f in TYPED_ALLOW:
        if f not in seen: bad.append('%s is on the list of routines that may draw typed fields behind a box, and no longer does' % f)
    if ends < 12 or shows < 20: bad.append('the "what was typed stays" check did not find its places (%d message ends, %d shows behind a box)' % (ends, shows))
    return bad, ends, shows
TYPED_SELFTEST = [
    ('the Level page\'s Save draws the page afresh behind its refusal again (the reviewer\'s own probe)', 'RF_FcSetup.h',
     '    if (FsRefused("page LevelView", false)) { FsShowKeepingTyped(CalHead, CalShow); return; }', '    if (FsRefused("page LevelView", false)) { CalHead(); CalShow(); return; }'),
    ('Battery\'s Save, the same', 'RF_FcSetup.h', '    if (FsRefused(BatPage(), false)) { FsShowKeepingTyped(BatHead, BatShow); return; }', '    if (FsRefused(BatPage(), false)) { BatHead(); BatShow(); return; }'),
    ('the page drawn afresh right behind "a box had no answer"', 'RF_FcSetup.h',
     '    if (RfFieldsMissed("page BlackboxView")) { FsShowKeepingTyped(BbHead, BbShow); return; }   // B211 (the ninth review)', '    if (RfFieldsMissed("page BlackboxView")) { BbHead(); BbShow(); return; }   // B211 (the ninth review)'),
    ('... the Filters page\'s, with its keeping taken out', 'RF_Filters.h', '        RfKeepTyped = true;\n        FltHead(); FltShow();\n        RfKeepTyped = false;\n        return;\n    }\n    if (DynNotchOn()', '        FltHead(); FltShow();\n        return;\n    }\n    if (DynNotchOn()'),
    ('the end of a message draws the page again', 'RF_Travel.h', '{ TravMsgUntil = 0; TravBusy(""); }', '{ TravMsgUntil = 0; TravBusy(""); TravShow(); }'),
    ('... in a block of its own', 'RF_Servos.h', '        ServoMsgUntil = 0;\n        ServoBusy("");', '        ServoMsgUntil = 0;\n        ServoBusy("");\n        ServoShow();'),
    ('Calibrate draws the page afresh behind its question, refused (no gather stands in front of it there)', 'RF_FcSetup.h',
     'the board goes into the model.)")) { FsShowKeepingTyped(CalHead, CalShow); return; }', 'the board goes into the model.)")) { CalHead(); CalShow(); return; }'),
    ('a redraw through a helper: Erase\'s question refused, and the page drawn by BbDone("", true) (reviewer B\'s probe)', 'RF_FcSetup.h',
     'They cannot be recovered.")) { FsShowKeepingTyped(BbHead, BbShow); return; }', 'They cannot be recovered.")) { BbDone("", true); return; }'),
    ('a failure box of the level page\'s with its routine off the list (a draw behind FsFail is a draw behind a box)', 'RF_FcSetup.h',
     'FLASHMEM static void CalFail(const char *what) { CalStep = CAL_IDLE; FsFail("page LevelView", what); FsShowKeepingTyped(CalHead, CalShow); }',
     'FLASHMEM static void CalFail(const char *what) { CalStep = CAL_IDLE; FsFail("page LevelView", what); CalHead(); CalShow(); }'),
    ('(the thirteenth review) the black box\'s failure box draws the page from what is in hand again', 'RF_FcSetup.h',
     'FLASHMEM static void BbFail(const char *what) { BbStep = BB_IDLE; FsFail("page BlackboxView", what); FsShowKeepingTyped(BbHead, BbShow); }',
     'FLASHMEM static void BbFail(const char *what) { BbStep = BB_IDLE; FsFail("page BlackboxView", what); BbHead(); BbShow(); }'),
    ('the bench release\'s failure box draws the page with its keeping taken out', 'RF_Travel.h', '    RfKeepTyped = true;\n    TravPageHead();\n    TravShow();\n    RfKeepTyped = false;\n}', '    TravPageHead();\n    TravShow();\n}'),
]
# EVERY JOB OF A PAGE WITH TYPED FIELDS BEGINS WITH THE PAGE'S GATHER (the twelfth review, reviewer B: Calibrate and Erase gathered nothing - the question in
# front of them kept what was typed, and the job's END drew the page from what is in hand; no check looked at a draw that has no box in its own routine).
# With the gather in front, what is in hand at any later draw of that job - its end, its failure box - IS what was typed: STEP above rests on this.
# Every routine of these pages that asks the flight controller (MspAsk) and is no poll has a gather in front of that asking, or stands here with why not.
JOB_READ = "a read - the page put up, or read again at the pilot's own word: what it brings REPLACES what the page shows"
JOB_STEP = "a later step of a job whose first step holds the gather (or of a read)"
JOB_NO_GATHER = {'BasRead': JOB_READ, 'StartBeeperView': JOB_READ, 'StartBatteryView': JOB_READ, 'StartBlackboxView': JOB_READ, 'FltRead': JOB_READ, 'ServoRead': JOB_READ, 'TravRead': JOB_READ,
                 'ArmTick': 'the "why it will not arm" line: a look at the flight controller\'s state - no field of the page is drawn from it',
                 'BasVerifyDone': JOB_STEP, 'BpWriteName': JOB_STEP, 'BatAfterWrites': JOB_STEP, 'BatWriteCm': JOB_STEP, 'BatWriteVm': JOB_STEP, 'EzAsk': JOB_STEP, 'RescueAskSelect': JOB_STEP, 'TravAskInput': JOB_STEP,
                 'BenchAskOverride': "the swash held or let go: Hold takes page 4 first (BenchHoldTapped); a release gathers nothing - its end and its failure box draw with the typed fields left as the screen has them (RfKeepTyped; typed_lint's own test holds that)"}
def job_lint(texts):
    funcs = kl_functions(texts)
    gatherers = sorted(f for f, (_, p, body) in funcs.items() if ('Gather' in f or 'KEEP_WHOLE(' in body or f in SELF_ASKING))
    GCALL = r'(?<![\w.>])(?:' + '|'.join(re.escape(g) for g in gatherers) + r')\s*\('
    typed_files = set(name for f, (name, p, b) in funcs.items() if f in TYPED_SHOWS)
    bad = []; seen = set(); found = 0
    for f in sorted(funcs):
        name, params, body = funcs[f]
        if name not in typed_files or 'Poll' in f: continue
        ask = re.search(r'(?<![\w.>])MspAsk\s*\(', body)
        if not ask: continue
        found += 1
        g = re.search(GCALL, body)
        if g and g.start() < ask.start(): continue
        if f in JOB_NO_GATHER: seen.add(f); continue
        bad.append('%s %s asks the flight controller with no gather in front: a job of a page with typed fields takes the page first (its end draws from what is in hand) - or it goes on the list (JOB_NO_GATHER) with why' % (name, f))
    for f in JOB_NO_GATHER:
        if f not in seen: bad.append('%s is on the list of routines that ask the flight controller with no gather in front, and is no longer one' % f)
    if found < 20: bad.append('the check of jobs that begin with their gather did not find them (%d)' % found)
    return bad, found
JOB_SELFTEST = [
    ('Calibrate with its gather taken out again', 'RF_FcSetup.h', '    RfGatherStart();\n    CalGather();\n    if (RfFieldsMissed("page LevelView")) { FsShowKeepingTyped(CalHead, CalShow); return; }   // (a box unanswered: nothing is begun', '    // (a box unanswered: nothing is begun'),
    ('the black box\'s Erase, the same', 'RF_FcSetup.h', '    RfGatherStart();\n    BbGather();\n    if (RfFieldsMissed("page BlackboxView")) { FsShowKeepingTyped(BbHead, BbShow); return; }   // (a box unanswered: nothing is begun', '    // (a box unanswered: nothing is begun'),
    ('a new job of the filters page that asks at once', 'RF_Filters.h', 'FLASHMEM void FilterWasEdited() { if (!FltHave) return; SendCommand((char *)"vis b3,1"); Flt_Was_Edited = true; }',
     'FLASHMEM void FilterWasEdited() { if (!FltHave) return; SendCommand((char *)"vis b3,1"); Flt_Was_Edited = true; }\nFLASHMEM void FilterResetNow() { if (FltStep != FLT_IDLE) return; FltReq = MspAsk(93, nullptr, 0); FltStep = FLT_WAIT; }'),
]
def job_selftest(texts):
    base = set(job_lint(texts)[0]); bad = []
    for what, f, old, new in JOB_SELFTEST:
        if texts[f].count(old) != 1: bad.append('the jobs check\'s own test: the text to change is not in %s any more, or stands there twice (%s)' % (f, what)); continue
        t2 = dict(texts); t2[f] = texts[f].replace(old, new)
        if not (set(job_lint(t2)[0]) - base): bad.append('the jobs check does NOT SEE this any more: ' + what)
    return bad, len(JOB_SELFTEST)

# A TYPED FIELD IS WRITTEN BY ITS PAGE'S OWN DRAW (the twelfth review, reviewer B's probe: the Beeper's name written back with a plain SendText("tn0",
# BpNameWant) passed - the checks above know the draws by their NAMES). The typed fields of a page are the boxes its gathers ask for, by name; a write of
# one of them by name stands in the page's draws (TYPED_SHOWS and what they call), or its routine stands on this list: the writers as they were at the
# twelfth review - each writes what a TAP has just chosen (or puts back what the tap could not change), or is the page's draw under an older name.
TYPED_WRITERS = {
    'RF_Adjust.h': ('AdjShow',),                                                        # the Switches-and-knobs page's own draw (RF_Jobs.h: the row gathered before every draw)
    'RF_Easy.h': ('EasySpoolTapped',),                                                  # the switch put back as it is in hand when its tap could not be taken
    'RF_Governor_Global.h': ('DisplayGovConfigValues', 'GovGlobalDefaults', 'ShowLocalGovConfigBank'),   # the page's draw (as read, or "Defaults" tapped), its bank's name
    'RF_Governor_Profile.h': ('DisplayGovValues', 'GovProfileDefaults', 'ShowGOVBank', 'ShowLocalGovBank'),
    'RF_Rescue.h': ('RescueFlipTapped',),                                               # the switch as its tap leaves it
    'RF_RotorFlight.h': ('StartRFSettingsView',),                                       # the page put up
    'RF_Travel.h': ('BenchAxisTapped', 'BenchSuggestTapped', 'BenchWasEdited', 'TravelAilTapped', 'TravelCollTapped', 'TravelEleTapped', 'TravelYawTapped'),   # taps: the axis chosen, the suggestion made (it goes into the calibration box: that is the tap), a direction switch as its tap leaves it
}
TYPED_ASKED = r'(?:GetText|GetValue|FieldNumber|FieldTenths|FieldHundredths|FieldTenthsL|BasFieldTenths|FieldPercent|BasPair)\s*\(\s*(?:\(char \*\)\s*)?"(\w+)"'
def typed_writers_lint(texts):
    funcs = kl_functions(texts); byfile = {}
    for f, (name, params, body) in funcs.items():
        i = kl_strip(texts[name]).find(body)
        byfile.setdefault(name, {})[f] = (body, texts[name][i:i + len(body)] if i >= 0 else '')
    bad = []; pages = 0; seen = set()
    for name in sorted(byfile):
        fs = byfile[name]; typed = set()
        for f, (body, raw) in fs.items():
            if 'Gather' in f or 'KEEP_WHOLE(' in body or f in SELF_ASKING: typed |= set(re.findall(TYPED_ASKED, raw))
        if not typed: continue
        pages += 1
        fam = set(s for s in TYPED_SHOWS if s in fs)
        while True:
            new = set(g for g in fs if g not in fam and any(re.search(r'(?<![\w.>])' + re.escape(g) + r'\s*\(', fs[s][0]) for s in fam))
            if not new: break
            fam |= new
        for f, (body, raw) in sorted(fs.items()):
            if f in fam: continue
            hit = sorted(set(mo.group(2) for mo in re.finditer(r'(?<![\w.>])(\w+)\s*\(\s*(?:\(char \*\)\s*)?"(\w+)"', raw)
                             if mo.group(2) in typed and not re.match(r'GetText|GetValue|Field|BasField|BasPair|strcmp|snprintf|RfFieldsMissed|FsRefused|GetOtherValue|AdjClickBox|TextMustBeNumber', mo.group(1))))
            if not hit: continue
            if f in TYPED_WRITERS.get(name, ()): seen.add((name, f)); continue
            bad.append('%s %s writes the typed field %s by name and is no draw of its page: a typed field is written by the page\'s draws (which keep what was typed where they must) - or the routine goes on the list (TYPED_WRITERS) with why' % (name, f, ', '.join(hit)))
    for name, fl in TYPED_WRITERS.items():
        for f in fl:
            if (name, f) not in seen: bad.append('%s %s is on the list of routines that write a typed field by name, and no longer does' % (name, f))
    if pages < 10: bad.append('the check of who writes a typed field did not find the pages (%d)' % pages)
    return bad, pages
WRITERS_SELFTEST = [
    ('the Beeper\'s name written back by a routine of its own (reviewer B\'s probe)', 'RF_Beeper.h', 'FLASHMEM static void BpShow()\n{', 'FLASHMEM static void BpNameBack() { SendText((char *)"tn0", BpNameWant); }\nFLASHMEM static void BpShow()\n{'),
    ('a level trim written back from what is in hand', 'RF_FcSetup.h', 'FLASHMEM void CalibrateNow()\n{', 'FLASHMEM static void CalTrimBack() { FsTenths("tn2", RdS16(CalWant, 0)); }\nFLASHMEM void CalibrateNow()\n{'),
]
def writers_selftest(texts):
    base = set(typed_writers_lint(texts)[0]); bad = []
    for what, f, old, new in WRITERS_SELFTEST:
        if texts[f].count(old) != 1: bad.append('the typed-writers check\'s own test: the text to change is not in %s any more, or stands there twice (%s)' % (f, what)); continue
        t2 = dict(texts); t2[f] = texts[f].replace(old, new)
        if not (set(typed_writers_lint(t2)[0]) - base): bad.append('the typed-writers check does NOT SEE this any more: ' + what)
    return bad, len(WRITERS_SELFTEST)

def typed_selftest(texts):
    base = set(typed_lint(texts)[0]); bad = []
    for what, f, old, new in TYPED_SELFTEST:
        if texts[f].count(old) != 1: bad.append('the "typed stays" check\'s own test: the text to change is not in %s any more, or stands there twice (%s)' % (f, what)); continue
        t2 = dict(texts); t2[f] = texts[f].replace(old, new)
        if not (set(typed_lint(t2)[0]) - base): bad.append('the "typed stays" check does NOT SEE this any more: ' + what)
    return bad, len(TYPED_SELFTEST)

# A NUMBER FIELD'S TEXT THAT IS NO NUMBER IS NO ANSWER (the twelfth review; Nextion.h TextMustBeNumber): every routine that asks a box for its text and
# makes a number of a text must look at each such text first - as many looks as it has askings. (A routine that asks for a text which is no number - a
# name beside its numbers - goes on the list with why.)
NUMBER_MAKERS = r'(?<![\w.>])(?:atof|atoi|atol|strtol|strtoul|strtof|strtod|sscanf)\s*\('
NUMBER_ALLOW = {}   # routine -> (how many of its texts are no numbers, why)
def number_lint(texts):
    funcs = kl_functions(texts); bad = []; n = 0
    for f, (name, params, body) in sorted(funcs.items()):
        if f in ('GetText', 'TextMustBeNumber'): continue
        asks = len(re.findall(r'(?<![\w.>])GetText\s*\(', body))
        if not asks or not re.search(NUMBER_MAKERS, body): continue
        n += 1
        looks = len(re.findall(r'(?<![\w.>])TextMustBeNumber\s*\(', body)); free = NUMBER_ALLOW.get(f, (0, ''))[0]
        if looks + free < asks:
            bad.append('%s %s asks %d box(es) for a text and makes a number of a text, and looks at %d of them with TextMustBeNumber: a text that is no number (the rest of a line glued to an answer) was read as 0, a number like any other' % (name, f, asks, looks))
    for f in NUMBER_ALLOW:
        if f not in funcs: bad.append('%s is on the list of routines whose text is no number, and is no routine any more' % f)
    if n < 11: bad.append('the check of the number fields did not find the routines that make a number of a text (%d)' % n)
    return bad, n
def number_selftest(texts):
    """Each call of TextMustBeNumber in the source, taken out by itself, must be seen."""
    base = set(number_lint(texts)[0]); bad = []; tried = 0
    for name in sorted(texts):
        lines = texts[name].split('\n')
        for i, l in enumerate(lines):
            code = l.split('//')[0]
            if 'TextMustBeNumber(' not in code or re.match(r'\s*(?:FLASHMEM\s+)?bool TextMustBeNumber\(', code): continue
            tried += 1
            t2 = dict(texts); t2[name] = '\n'.join(lines[:i] + lines[i + 1:])
            if not (set(number_lint(t2)[0]) - base): bad.append('the number-field check does NOT SEE this look taken out: %s:%d %s' % (name, i + 1, l.strip()[:80]))
    if tried < 13: bad.append('the number-field check\'s own test found %d looks to take out (13 and more are in the source)' % tried)
    return bad, tried

def main():
    scenes = SCENES_B + SCENES_A
    bad, flagged = box_lint()
    sbad, forms = lint_selftest(); bad += sbad
    rf = rf_texts(); pbad, gathers, gcalls = page_lint(rf); bad += pbad
    psb, pforms = page_lint_selftest(rf); bad += psb
    kbad, kgathers, knames = keep_lint(rf); bad += kbad
    ksb, kforms = keep_selftest(rf); bad += ksb
    everything = lint_texts(); obad, okeepers = keep_lint_other(everything, rf); bad += obad
    osb, oforms = keep_other_selftest(everything, rf); bad += osb
    abad, askers = askers_lint(everything); bad += abad                                  # (the eleventh review: a gather is known by what it does)
    asb, aforms = askers_selftest(everything); bad += asb
    tbad, tends, tshows = typed_lint(rf); bad += tbad                                    # (... and what was typed stays on the page)
    tsb, tforms = typed_selftest(rf); bad += tsb
    jbad, jobs = job_lint(rf); bad += jbad                                               # (the twelfth review: every job of such a page begins with its gather)
    jsb, jforms = job_selftest(rf); bad += jsb
    wbad, wpages = typed_writers_lint(rf); bad += wbad                                   # (... and a typed field is written by its page's own draw)
    wsb, wforms = writers_selftest(rf); bad += wsb
    nbad, nmakers = number_lint(everything); bad += nbad                                 # (the twelfth review: a number field's text that is no number is no answer)
    nsb, nlooks = number_selftest(everything); bad += nsb
    # ... and what the cures of the eighth review must still say, where no run reaches
    mc = re.sub(r'//[^\n]*', '', m.MAIN_CPP); nx = re.sub(r'//[^\n]*', '', m.NEXTION); ut = re.sub(r'//[^\n]*', '', m.UTIL)
    if not re.search(r'const uint32_t lost = BoxesLost;\s*const int hi = GetOtherValue\(\(char \*\)"High\.pco"\), fg = GetOtherValue\(\(char \*\)"Example\.pco"\), bg = GetOtherValue\(\(char \*\)"Fm\.bco"\), sp = GetOtherValue\(Fm_pco\);\s*if \(BoxesLost == lost\)\s*\{\s*HighlightColour = hi;', mc):
        bad.append('main.cpp, the colours page: all four colours are taken, or none (a colour with no answer read as black)')
    ez = re.sub(r'//[^\n]*', '', m.release(m.src('include/RF_Easy.h')))
    if not re.search(r'MsgBox\(\(char \*\)"page EasyView", \(char \*\)box\);\s*RfKeepTyped = true;\s*EzShowAll\(\);\s*RfKeepTyped = false;', ez) \
            or not re.search(r'if \(!RfKeepTyped\)\s*\{\s*for \(int k = 0; k < 5; \+\+k\)\s*\{\s*snprintf\(nm, sizeof\(nm\), "s%d", k\);\s*SendValue\(nm,[^;]*;\s*\}\s*SendValue\(\(char \*\)"sw", EzSpool \? 1 : 0\);\s*\}', ez):
        bad.append('RF_Easy.h: a save that FAILS leaves the sliders and the switch as he left them (EzFinish: its box, then EzShowAll with RfKeepTyped set; EzShowSliders writes them only when it is not)')
    tm = re.sub(r'//[^\n]*', '', m.release(m.src('include/Trims.h')))
    st = tm[tm.index('#define SUBTRIM_MOST'):tm.index('void EndSubTrimView()')]
    if re.search(r'\b(?:GetValue|GetText|GetOtherValue|GetSysValue|DelayWithDog|CollectReply)\s*\(', st) or len(re.findall(r'SubTrims\[[^\]]*\]\s*=[^=]', st)) != 1 \
            or not re.search(r'if \(made == again && SubTrimShown && stood == \(int32_t\)SubTrims\[c\] - 127 && made >= -SUBTRIM_MOST && made <= SUBTRIM_MOST\)\s*\{\s*SubTrims\[c\] = \(uint8_t\)\(made \+ 127\);\s*if \(SubTrimDone != SubTrimAsked\)\s*SubTrimSettleDue = true;\s*return;\s*\}\s*\{[^{}]*SubTrimNote\(kept, whole\);\s*\}\s*SubTrimBoxOut\(c\);\s*SubTrimResync\(\);\s*SubTrimSettleDue = true;', st) \
            or not re.search(r'if \(n == SUBTRIM_DONE_BYTES\)\s*\{\s*const int32_t done = SubTrimNumberAt\(w \+ 6\);\s*if \(framed && done == SubTrimNumberAt\(w \+ 10\) && done == \(int32_t\)SubTrimAsked\)\s*\{\s*SubTrimDone = SubTrimAsked;\s*SubTrimShown = true;\s*SubTrimSaysDone = true;\s*SubTrimAskedAgain = 0;\s*\}\s*return;\s*\}', st) \
            or not re.search(r'const int32_t ch = SubTrimNumberAt\(w \+ 6\), stood = SubTrimNumberAt\(w \+ 10\), made = SubTrimNumberAt\(w \+ 14\), again = SubTrimNumberAt\(w \+ 18\);', st) \
            or not re.search(r'if \(\+\+SubTrimAsked == 0\)\s*SubTrimAsked = 1;\s*SubTrimAskedAgain = 0;\s*SubTrimAskedMs = millis\(\);\s*SendValue\(\(char \*\)"rsn", SubTrimAsked\);\s*SendCommand\(\(char \*\)"click rs,0"\);', st) or len(re.findall(r'click rs,0', st)) != 1:
        bad.append('Trims.h, the Sub-trim page: it asks the screen NOTHING and waits for nothing; a sub trim is stored in ONE place - when the word\'s "as it stood" is what the model has for that channel, its two last numbers agree, the page has said this model\'s numbers done, and the number is one the card keeps; else the channel is put right on the page (and a line left in the log). '
                   'Every click of "rs" has a number of its own, given to the page in front of it (one place); only that number said back, framed, makes the click done; a change taken while it is not done owes the page\'s writing-out')
    for word, call in (('ldrcadj', 'JobsPageBack'), ('ldrcrcv', 'RatesCurvesPageBack')):   # (the tenth review: a page's own word is not obeyed while a question waits)
        if not re.search(r'if \(InStrng\(\(char \*\)"%s", TextIn\) > 0\)\s*\{\s*if \(!ModalWaits\)\s*%s\(\);\s*ClearText\(\);\s*return;\s*\}' % (word, call), mc):
            bad.append('main.cpp: the page\'s word "%s" is obeyed (%s) only while NO question waits - served inside one, the page\'s boxes were read from the question\'s page' % (word, call))
    if not re.search(r'if \(NextionGetPending \|\| InsideDelayWithDog \|\| ModalWaits\)\s*PageChangedUnderGet = true;', nx):
        bad.append('Nextion.h BeforePageCommand: a page command from inside a get\'s wait, a wait that flies the model, or a question\'s wait voids the boxes of the work it came under')
    if not re.search(r'if \(!ModalWaits && !InsideDelayWithDog\)\s*PageChangedUnderGet = false;', nx):
        bad.append('Nextion.h GetButtonPress: only the main loop\'s look for a press ends "no box has an answer"')
    if not re.search(r'if \(mm \+ 1 != LastModelLoaded && ScreenSessionCheck\(\) != 0\)\s*return false;', mc):
        bad.append('main.cpp CheckModelName: before another model is loaded for a row that changed with no press, the screen is asked whether it is still the same one')
    if not re.search(r'if \(BoundFlag && ModelMatched && CurrentView != FRONTVIEW && !NextionGetPending && !ModalWaits\)', mc):
        bad.append('main.cpp CheckPowerOffButton: no front page under a get, nor over a question')
    if not re.search(r'const uint32_t lost = BoxesLost;\s*if \(!ModalWaits\)\s*BoxesLostAtWork = BoxesLost;\s*ButtonWasPressed\(\);\s*if \(BoxesLost != lost\)\s*NoteBoxesLost\(\);', ut):
        bad.append('Utilities.h CheckForNextionButtonPress: a button\'s work that asked for a box with no answer says so')
    em = re.sub(r'//[^\n]*', '', m.lift(m.MAIN_CPP, 'FLASHMEM void EnsureMotorIsOff()'))
    if not re.search(r'while \(\(millis\(\) - round\) < 200\)\s*\{\s*KickTheDog\(\);', em) or 'if (ScreenRestartSeen)' not in em or not re.search(r'NextionGetPending = false;\s*StashPendingEventBytes\(\);\s*NextionGetPending = pending;', em):
        bad.append('main.cpp EnsureMotorIsOff: no box while the screen\'s restart is noted (what it says read in, also inside a get\'s wait), and no round shorter than a fifth of a second with the dog fed')
    nq = m.lift(m.release(m.src('include/LogFiles.h')), 'FLASHMEM void NoteQuestionClosed(uint8_t why)')
    if 'char line[120];' not in nq or 'strlcpy(line,' not in nq or 'LogText(line, strlen(line), true);' not in nq:
        bad.append('LogFiles.h NoteQuestionClosed: the line is a copy of this routine\'s own (LogText empties what it is given: given the words themselves, each line was written once only)')
    for f in sorted(glob.glob(os.path.join(m.TC, 'include', '*.h'))) + [os.path.join(m.TC, 'src', 'main.cpp')]:
        for i, l in enumerate(open(f, encoding='utf-8', errors='replace').read().split('\n'), 1):
            if re.search(r'\bLogText\(\s*\(char \*\)', l.split('//')[0]): bad.append('%s:%d LogText is given words that are not its caller\'s own copy (it empties what it is given): %s' % (os.path.basename(f), i, l.strip()[:90]))
    rs = re.sub(r'//[^\n]*', '', m.lift(m.MAIN_CPP, 'bool ReadSpeedsScreen(uint8_t bk, bool FromPage)'))
    if not re.search(r'const bool whole = BoxesLost == lost;\s*if \(whole \|\| FromPage\)\s*SendText\(change, cleared\);', rs) or 'KEEP_WHOLE(speeds, ServoSpeed[bk]);' not in rs or 'if (bk >= BANKS_USED)' not in rs:
        bad.append('main.cpp ReadSpeedsScreen: the speeds are taken whole by its OWN count (the bank switch calls it from the main loop), every bank the model has; OK with a box unanswered leaves the list of edited boxes on the page')
    sw = re.sub(r'//[^\n]*', '', m.release(m.src('include/Switches.h')))
    if not re.search(r'const uint32_t lost = BoxesLost;\s*BoxesLostAtWork = BoxesLost;\s*ReadSpeedsScreen\(PreviousBank - 1, true\);\s*if \(BoxesLost != lost\)\s*NoteBoxesLost\(\);\s*UpdateSpeedScreen\(\);', sw):
        bad.append('Switches.h, the bank switch on the Slow-servo page: the main loop\'s own work, counted as a button\'s is - and a box with no answer is said')
    for b in bad: print('FAIL: ' + b)
    d = tempfile.mkdtemp()
    cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(program(scenes))
    r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-format', '-Wno-unused-but-set-variable', '-funsigned-char',
                        '-fsanitize=address,undefined', '-o', os.path.join(d, 'test_noanswer'), cpp], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stderr[-7000:] + '\ncompile failed')
    rc = subprocess.run([os.path.join(d, 'test_noanswer')] + [a for a in sys.argv[1:] if a == '--show']).returncode
    print('test_noanswer source checks: %d places where a box\'s answer is not looked at first (all on the list); the check itself sees %d unsafe forms; %d gathers and their %d calls (%d unsafe forms seen); '
          'what %d gathers write is kept (%d names; %d unsafe forms seen), and what %d other routines with a keep write (%d forms seen); %d routines that ask for more than one box, each a gather or on the list (%d forms seen); '
          '%d message ends that draw nothing and %d draws behind a box that leave what was typed (%d forms seen); %d routines that make a number of a box\'s text, each text looked at first (%d looks, each seen when taken out); %d failures'
          % (flagged, forms, gathers, gcalls, pforms, kgathers, knames, kforms, okeepers, oforms, askers, aforms, tends, tshows, tforms, nmakers, nlooks, len(bad)))
    return 1 if (rc or bad) else 0

if __name__ == '__main__': sys.exit(main())
