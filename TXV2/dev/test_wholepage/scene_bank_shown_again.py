#!/usr/bin/env python3
"""THE MOTOR SWITCH IS NO BANK CHANGE - and the trims of SIX banks (the thirteenth review, reviewer B's list of what the RELEASED code already had:
B1, B2, B3; with what the author found looking for their kin; 15 Nov 2026).

main.cpp GetBank forced "PreviousBank = 254" behind the motor switch so that the bank would be shown again, and Switches.h BankHasChanged then
treated every page as LEFT FOR ANOTHER BANK: the Slow-servo page read "the bank that was left" into no bank and was drawn again from memory - what
was typed was gone without a word, and OK "saved" the old speeds; the Rotorflight pages read the flight controller again over their edits
("Rescue values for Bank 254 were edited ..."). And when that switch moved the bank as well (its far position is bank 4, 5 or 6), the bank really
left was forgotten. Now GetBank asks for the bank to be SHOWN AGAIN and PreviousBank stays the bank that was.
 W1 the motor switch on the Slow-servo page: nothing asked of the page, what was typed still stands, OK saves it.
 W2 the motor switch AND the bank in one pass: the bank that was left takes its typed speeds (as at any bank change), the page shows the new bank's.
 W3 the motor switch brings the front page up (the stub of MotorEnabledHasChanged does as the real one): the trims and the bank are shown.
 W4 every page BankHasChanged knows: shown again calls none of their routines, saves nothing; a bank that changed calls each as it always did.
 W5 the Rescue page, edited and not saved: the motor switch alone asks nothing and keeps the edit; with the bank changed the box names the bank
    that was left (it said 254); a number that is no bank is not named.
 W6 the bank's sound and the log's line are as they were.
 B1 int LastTrim[5][17] was indexed by bank 5 and 6: the REAL line of 1Definitions.h, UpdateTrimView, ForceDataRedisplay and BankHasChanged run in
    banks 5 and 6 under the address checker; and a trim that Trim setup gave channel 7 is shown again at every bank change.
 B2 "Move these trims into subtrim" on six banks: every bank's trim goes to centre (banks 5 and 6 kept theirs: flown twice).
 K  their kin: 'Trims: all banks' copies the channel each trim MOVES; "all trims to centre" reaches channel 16 in every bank; a model taken in with
    the other sticks mode swaps the elevator and throttle trims of ALL its banks.
The REAL GetBank (main.cpp), BankHasChanged (Switches.h), RescueBankChanged (RF_Rescue.h), the Slow-servo page's routines, and the trims' (Trims.h,
Utilities.h, ModelExchange.h's and main.cpp's own lines) run over the pretend screen."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
MAINC = m.MAIN_CPP
SWT = m.release(m.src('include/Switches.h')); SDC = m.release(m.src('include/SDcard.h')); TRM = m.release(m.src('include/Trims.h'))
RSC = m.release(m.src('include/RF_Rescue.h')); MEX = m.release(m.src('include/ModelExchange.h'))
def block(text, head):
    i = text.index(head); d = 0; j = text.index('{', i)
    for k in range(j, len(text)):
        if text[k] == '{': d += 1
        elif text[k] == '}':
            d -= 1
            if d == 0: return text[i:k + 1]
    raise SystemExit('no block ' + head)
LASTTRIM = [l for l in m.DEFS.split('\n') if l.startswith('int LastTrim[')]
if len(LASTTRIM) != 1: print('FAIL: 1Definitions.h: one line "int LastTrim[...]" was looked for, found %d' % len(LASTTRIM)); sys.exit(1)
TRIMS50 = block(MAINC, 'if (InStrng(TRIMS50, TextIn) > 0)'); TRIMS50 = TRIMS50[TRIMS50.index('{'):]
SWAP = block(MEX, 'if (SavedSticksMode != SticksMode)')
EXTRA = r'''
static uint8_t ServoSpeed[BANKS_USED + 1][CHANNELSUSED + 1];
static char BankNames[BANK_NAMES_N][16];
static int setups = 0; static void StartModelSetup() { ++setups; }
bool ReadSpeedsScreen(uint8_t bk, bool FromPage = false);
''' + m.lift(SDC, 'void CheckServoSpeeds()') + m.lift(MAINC, 'void UpdateSpeedScreen()') + m.lift(MAINC, 'bool ReadSpeedsScreen(uint8_t bk, bool FromPage)') + m.lift(MAINC, 'void EndSpeedsScreen()') + r'''
// ---- the trims: the real table's line, the real routines
int Trims[BANKS_USED + 1][CHANNELSUSED + 1]; uint8_t SubTrims[CHANNELSUSED + 1];
''' + LASTTRIM[0] + r'''
static uint8_t SticksMode = 1, SavedSticksMode = 1; static bool TrimClicks = false, ForceVoltDisplay = false; static uint16_t TrimRepeatSpeed = 0; static uint32_t LastShowTime = 0;
static char ChannelNames[CHANNELSUSED + 1][12]; static char pTrimView[] = "page TrimView";
''' + re.search(r'^#define SUBTRIM_MOST[ \t]+\d+', TRM, re.M).group(0) + r'''
void UpdateTrimView();
''' + m.lift(m.UTIL, 'void ForceDataRedisplay()') + m.lift(TRM, 'int GetTrimAmount(uint8_t InputChannel)') + m.lift(TRM, 'void UpdateTrimView()') + m.lift(TRM, 'void IncTrim(uint8_t t)') + m.lift(TRM, 'void DecTrim(uint8_t t)') \
  + m.lift(TRM, 'void MoveaTrim(uint8_t i)') + m.lift(TRM, 'FLASHMEM static uint8_t TrimSlotOfChannel(uint8_t c)') + m.lift(TRM, 'FLASHMEM static bool TrimsIntoSubtrims(int *over)') + r'''
static void trims50Lines() { int i; ''' + TRIMS50 + r''' }                       // main.cpp ButtonWasPressed's own lines behind "all trims to centre"
static void sticksModeSwapLines() { ''' + SWAP + r''' }                           // include/ModelExchange.h's own lines: a model taken in with the other sticks mode
// ---- what BankHasChanged calls on its pages: counted
static int cRates = 0, cLog = 0, cSound = 0, cShowBank = 0, cCurve = 0, cDual = 0, cPid = 0, cGov = 0, cPidAdv = 0, cEasy = 0, cRfBank = 0, cRfRate = 0;
static void ShowRatesBank() { ++cRates; } static void LogNewBank() { ++cLog; } static void SoundBank() { ++cSound; } static void ShowBank() { ++cShowBank; }
static void DisplayCurveAndServoPos() { ++cCurve; } static void DisplayNewDualRateBank() { ++cDual; } static void ShowPIDBank() { ++cPid; } static void ShowGOVBank() { ++cGov; }
static void ShowPIDAdvancedBank() { ++cPidAdv; } static void EasyBankChanged() { ++cEasy; } static void ShowRFBank() { ++cRfBank; } static void ShowRFRate() { ++cRfRate; }
static int pageCalls() { return cRates + cCurve + cDual + cPid + cGov + cPidAdv + cEasy + cRfBank + cRfRate; }
static void noCalls() { cRates = cLog = cSound = cShowBank = cCurve = cDual = cPid = cGov = cPidAdv = cEasy = cRfBank = cRfRate = 0; }
static uint8_t RotorFlight_V = 0, DualRateInUse = 1; static bool LinkRatesToBanks = false, AnnounceBanks = true, MotorWasEnabled = false;
// ---- the Rescue page's own
enum { RSC_IDLE = 0, RSC_SELECT, RSC_READ }; static int RescueStep = RSC_IDLE;   // (the sixteenth review: a bank change drops a read under way - dev/test_rescuebank runs it)
static bool Rescue_Was_Edited = false, RescueRereadWanted = false, RescueHave = true; static uint32_t RescueRereadAt = 0; static int rescueBusy = 0; static void RescueBusy(const char *) { ++rescueBusy; }
''' + m.lift(RSC, 'void RescueBankChanged()') + m.lift(SWT, 'void BankHasChanged()') + r'''
// ---- GetBank's own callees: the switches are this test's hand
static uint8_t swBank = 1; static bool swMotor = false, motorBringsFront = false, motorRefused = false, SafetyON = false, SafetyWasOn = false; static int motorChanges = 0;
static void SafetyHoldUpdate() {} static void ReadSafetySwitch() {} static void ReadBuddySwitch() {} static void ReadDualRateSwitch() {} static void SafetySwitchChanged() {} static void ReadChannelSwitches9to12() {}
static void ReadBankSwitch() { Bank = swBank; } static void ReadAutoAndMotorSwitch() { MotorEnabled = swMotor; }
static void MotorEnabledHasChanged()   // (Motor_sign.h: the motor on brings the front page up; "not connected: please turn it off" puts the motor back off)
{
    ++motorChanges;
    if (MotorEnabled && motorRefused) { MotorEnabled = false; return; }
    if (MotorEnabled && motorBringsFront && CurrentView != FRONTVIEW) GotoFrontView();
}
''' + m.lift(MAINC, 'void GetBank()').replace('void GetBank()', 'static void RealGetBank()', 1) + r'''
static void addBankPages()
{
    Page s; s.id = 64; for (int i = 0; i < 16; ++i) { char n[8]; snprintf(n, sizeof n, "n%d", i); s.boxes[n] = { false, 100, "" }; }
    s.boxes["Progress"] = { false, 0, "" }; s.boxes["change"] = { true, 0, "XX:" }; s.boxes["t14"] = { true, 0, "" };
    screen.pages["SlowServoView"] = s;
    Page t; t.id = 66; for (const char *n : { "ch1", "ch2", "ch3", "ch4", "n1", "n2", "n3", "n4" }) t.boxes[n] = { false, -1, "" }; for (const char *n : { "c1", "c2", "c3", "c4" }) t.boxes[n] = { true, 0, "" };
    screen.pages["TrimView"] = t;
    Page r; r.id = 69; r.boxes["t9"] = { true, 0, "" }; r.boxes["t11"] = { true, 0, "" }; screen.pages["RescueView"] = r;
    for (const char *n : { "ch1", "ch2", "ch3", "ch4", "n1", "n2", "n3", "n4" }) screen.pages["FrontView"].boxes[n] = { false, -1, "" };
    screen.pages0 = screen.pages;
    for (auto &b : ServoSpeed) for (uint8_t &x : b) x = 100;
    for (int i = 0; i < BANK_NAMES_N; ++i) snprintf(BankNames[i], sizeof BankNames[i], "Bank%d", i);
    for (auto &b : Trims) for (int &x : b) x = 80;
    for (uint8_t &x : SubTrims) x = 127;
    for (int i = 0; i < 4; ++i) InputTrim[i] = (uint8_t) i;
    memset(LastTrim, 0, sizeof LastTrim); SticksMode = SavedSticksMode = 1; TrimMultiplier = 5; CopyTrimsToAll = false;
    setups = 0; saves.clear(); noCalls(); motorChanges = 0; motorBringsFront = motorRefused = false; rescueBusy = 0; Rescue_Was_Edited = false; RescueRereadWanted = false;
    RotorFlight_V = 0; LinkRatesToBanks = false; AnnounceBanks = true; UseLog = true; UseMotorKill = true; BoundFlag = ModelMatched = false; BankSoundHeld = false; CurrentMode = NORMAL;
    BuddyPupilOnWireless = false; SendNoData = false; SafetyON = SafetyWasOn = false;
}
// the transmitter as it stands on a page: bank and motor as the switches say, nothing owed
static void stand(uint8_t bank, bool motor) { swBank = bank; swMotor = motor; Bank = PreviousBank = bank; MotorEnabled = MotorWasEnabled = motor; RealGetBank(); noCalls(); motorChanges = 0; }
static void openSlow(uint8_t bank, bool motor) { more(); addBankPages(); SendCommand((char *) "page SlowServoView"); CurrentView = SLOWSERVOVIEW; stand(bank, motor); UpdateSpeedScreen(); loopFor(600); BoxesLostAtWork = BoxesLost; }
static void openView(uint8_t view, uint8_t bank, bool motor) { more(); addBankPages(); CurrentView = view; stand(bank, motor); loopFor(300); BoxesLostAtWork = BoxesLost; }
static void edit(int box, int v) { char n[8]; snprintf(n, sizeof n, "n%d", box); Page &pg = screen.pages["SlowServoView"]; pg.boxes[n].val = v; pg.boxes["change"].txt += n; pg.boxes["change"].txt += " "; }
static bool allFull(uint8_t bank, std::initializer_list<int> but = {}) { for (int i = 0; i < 16; ++i) { bool skip = false; for (int k : but) skip |= k == i; if (!skip && ServoSpeed[bank - 1][i] != 100) return false; } return true; }
static void okPressed() { Page &pg = screen.pages["SlowServoView"]; snprintf(TextIn, 200, "SLOW%s", pg.boxes["change"].txt.c_str()); EndSpeedsScreen(); }
'''
SCENES = r'''
    // W1. the motor switch on the Slow-servo page, each way: nothing asked, what was typed stands; then OK saves it
    for (int way = 0; way < 3; ++way)
    {
        openSlow(2, way == 0); edit(3, 40); edit(7, 60);
        motorRefused = way == 2;                                                   // (way 2: not connected, "please turn it off" - the motor is put back off)
        { const int g0 = screen.gets, told0 = boxesLostTold; swMotor = way != 0; RealGetBank(); loopFor(600);
          Page &pg = screen.pages["SlowServoView"];
          say("W1. the motor switch %s on the Slow-servo page: asked of the page %d, the boxes show %d and %d, the page's list '%s', page routines called %d, told %d\n", way == 0 ? "OFF" : way == 1 ? "ON (the page stays: a question waits, or not the normal mode)" : "ON, refused",
              screen.gets - g0, (int) pg.boxes["n3"].val, (int) pg.boxes["n7"].val, pg.boxes["change"].txt.c_str(), pageCalls(), boxesLostTold - told0);
          CHECK(motorChanges == 1 && screen.gets == g0 && pg.boxes["n3"].val == 40 && pg.boxes["n7"].val == 60 && pg.boxes["change"].txt == "XX:n3 n7 ");   // (it was: 100 and 100, the list cleared)
          CHECK(allFull(2) && boxesLostTold == told0 && saves.empty() && PreviousBank == 2 && Bank == 2 && pageCalls() == 0); }
        okPressed(); loopFor(600);
        CHECK(ServoSpeed[1][3] == 40 && ServoSpeed[1][7] == 60 && allFull(2, { 3, 7 }) && saves.size() == 1 && setups == 1);   // (it was: OK "saved" 100 and 100)
    }
    // W2. the motor switch AND the bank in one pass (its near end to its far end: the motor off, bank 2 left for bank 5): bank 2 takes what was typed
    openSlow(2, true); edit(3, 40); edit(7, 60); ServoSpeed[4][3] = 30;
    { const int told0 = boxesLostTold; swMotor = false; swBank = 5; RealGetBank(); loopFor(600);
      Page &pg = screen.pages["SlowServoView"];
      say("W2. the motor switch and the bank in one pass (2 left for 5): bank 2 channel 4 %u, channel 8 %u; the page shows channel 4 at %d (bank 5 has 30), its list '%s'; told %d\n", (unsigned) ServoSpeed[1][3], (unsigned) ServoSpeed[1][7], (int) pg.boxes["n3"].val, pg.boxes["change"].txt.c_str(), boxesLostTold - told0);
      CHECK(ServoSpeed[1][3] == 40 && ServoSpeed[1][7] == 60 && allFull(2, { 3, 7 }));              // (it was: read into no bank - bank 2 kept 100 and 100, and nobody was told)
      CHECK(pg.boxes["n3"].val == 30 && pg.boxes["n7"].val == 100 && pg.boxes["change"].txt == "XX:" && boxesLostTold == told0 && PreviousBank == 5 && allFull(5, { 3 })); }
    //     ... and one box unanswered: nothing taken for bank 2 - and SAID (as at any bank change)
    openSlow(2, true); edit(3, 40); edit(7, 60);
    { const int told0 = boxesLostTold; swMotor = false; swBank = 4; screen.mute.insert("n7"); RealGetBank(); screen.mute.clear(); loopFor(3000);
      CHECK(allFull(2) && boxesLostTold == told0 + 1 && screen.pages["SlowServoView"].boxes["change"].txt == "XX:"); }
    // W3. the motor switch brings the front page up from the Slow-servo page: the trims and the bank are shown there, nothing asked of the page left
    openSlow(3, false); edit(3, 40); Trims[3][0] = 91; Trims[3][3] = 77; motorBringsFront = true;
    { const int g0 = screen.gets; swMotor = true; RealGetBank(); loopFor(600);
      Page &pg = screen.pages["FrontView"];
      say("W3. the motor on brings the front page up: the page is %s, the aileron trim shows %d, the rudder trim %d, the bank shown %d time(s), asked %d\n", screen.page.c_str(), (int) pg.boxes["ch1"].val, (int) pg.boxes["ch3"].val, cShowBank, screen.gets - g0);
      CHECK(screen.page == "FrontView" && CurrentView == FRONTVIEW && pg.boxes["ch1"].val == 91 && pg.boxes["n1"].val == 11 && pg.boxes["ch3"].val == 77 && pg.boxes["n3"].val == -3 && cShowBank == 1);
      CHECK(allFull(3) && pageCalls() == 0 && saves.empty()); }
    // W4. every page BankHasChanged knows: SHOWN AGAIN calls none of their routines and saves nothing; A BANK THAT CHANGED calls each as it always did
    {
        struct V { uint8_t view; int *count; const char *name; } views[] = {
            { GRAPHVIEW, &cCurve, "the curve page" }, { DUALRATESVIEW, &cDual, "Dual rates" }, { PIDVIEW, &cPid, "PIDs" }, { RFGOVERNORVIEW_PROFILE, &cGov, "Governor" },
            { PIDADVANCEDVIEW, &cPidAdv, "PID plus" }, { EASYVIEW, &cEasy, "Easy tuning" }, { ROTORFLIGHTVIEW, &cRfBank, "Rotorflight" }, { RFBACKUP_RESTOREVIEW, &cRfRate, "Backup" },
            { RATESVIEW_RF, &cRates, "Rates (linked to the banks)" } };
        for (const V &v : views)
            for (int way = 0; way < 2; ++way)
            {
                openView(v.view, 2, way == 0); RotorFlight_V = 2; LinkRatesToBanks = v.view == RATESVIEW_RF;
                swMotor = way != 0; RealGetBank();
                const int again = pageCalls(), savedAgain = (int) saves.size(); const int logAgain = cLog, soundAgain = cSound;
                CHECK(again == 0 && savedAgain == 0 && motorChanges == 1 && PreviousBank == 2);                                 // shown again: no page routine, nothing saved (it was: each of them, and the curve page's save)
                CHECK(logAgain == 1 && soundAgain == 0);                                                                          // (the log's line as it was; the motor switch never says the bank)
                noCalls(); swBank = 3; RealGetBank();
                CHECK(*v.count == 1 && pageCalls() == (v.view == ROTORFLIGHTVIEW || v.view == RFBACKUP_RESTOREVIEW ? 2 : 1) && cSound == 1 && cLog == 1);   // a bank that changed: as ever
                CHECK((int) saves.size() == (v.view == GRAPHVIEW ? 1 : 0) && PreviousBank == 3);
                if (way == 0) say("W4. %s: the motor switch alone called %d page routine(s) and saved %d; the bank switch called %d and saved %d\n", v.name, again, savedAgain, pageCalls(), (int) saves.size());
            }
        // (the two pages that only show the bank's number)
        for (uint8_t view : { (uint8_t) PICKBANKVIEW1, (uint8_t) PICKBANKVIEW2 }) { openView(view, 2, true); CHECK(screen.cmds.empty()); swMotor = false; RealGetBank(); CHECK(screen.cmds.empty() && motorChanges == 1); swBank = 3; RealGetBank(); CHECK(screen.cmds.size() == 2); }   // (shown again: nothing written; a bank that changed: its number, twice)
    }
    // W5. the Rescue page, edited and not saved
    openView(RESCUEVIEW, 2, true); SendCommand((char *) "page RescueView"); loopFor(400); Rescue_Was_Edited = true;
    { const int q0 = screen.loads; swMotor = false; RealGetBank(); loopFor(400);
      say("W5. the motor switch on the Rescue page, edited: boxes put up %d, the edit still stands %d, read again %d\n", screen.loads - q0, (int) Rescue_Was_Edited, (int) RescueRereadWanted);
      CHECK(screen.loads == q0 && Rescue_Was_Edited && !RescueRereadWanted && rescueBusy == 0 && screen.page == "RescueView"); }   // (it was: "Rescue values for Bank 254 were edited ... Too late now!", and the page read again)
    //     ... the motor switch and the bank in one pass (2 left for 4): the box names the bank that was left
    { tapAt(500, "yes"); swMotor = true; swBank = 4; motorBringsFront = false; RealGetBank(); loopFor(400);
      const std::string said = screen.pages["PopupView"].boxes["Dialog"].txt;
      say("     with the bank changed too, the box says: %s\n", said.substr(0, said.find('\r')).c_str());
      CHECK(said.find("Rescue values for Bank 2 were edited") == 0 && !Rescue_Was_Edited && RescueRereadWanted && rescueBusy == 1 && !RescueHave); }   // (the fifteenth review: what is in hand is the old bank's from this moment)
    //     ... a number that is no bank (250: the screen's restart; 42: the receiver options - neither can come on this page) is not named
    openView(RESCUEVIEW, 2, false); SendCommand((char *) "page RescueView"); loopFor(400); Rescue_Was_Edited = true;
    { tapAt(500, "yes"); PreviousBank = 250; RealGetBank(); loopFor(400);
      const std::string said = screen.pages["PopupView"].boxes["Dialog"].txt;
      CHECK(said.find("Rescue values were edited") == 0 && said.find("250") == std::string::npos && !Rescue_Was_Edited); }
    // W6. the bank's sound: never behind the motor switch - but behind the motor REFUSED (put back off: no change of the motor), as it was; held behind the screen's restart, as it was
    openView(FRONTVIEW, 2, false); swMotor = true; RealGetBank(); CHECK(cSound == 0 && cLog == 1 && cShowBank == 1);
    openView(FRONTVIEW, 2, false); motorRefused = true; swMotor = true; RealGetBank(); CHECK(cSound == 1 && cShowBank == 1 && !MotorEnabled);
    openView(FRONTVIEW, 2, false); PreviousBank = 250; BankSoundHeld = true; RealGetBank(); CHECK(cSound == 0 && cShowBank == 1 && !BankSoundHeld && PreviousBank == 2);
    openView(FRONTVIEW, 2, false); swBank = 3; RealGetBank(); CHECK(cSound == 1 && cShowBank == 1 && cLog == 1);
    openView(FRONTVIEW, 2, false); RealGetBank(); RealGetBank(); CHECK(cSound == 0 && cShowBank == 0 && cLog == 0 && motorChanges == 0);   // nothing moved: nothing done
    // B1. the trims of banks 5 and 6: the REAL table (1Definitions.h's own line), under the address checker
    CHECK(sizeof LastTrim == sizeof(int) * (BANKS_USED + 1) * (CHANNELSUSED + 1) && sizeof LastTrim == sizeof Trims);                // as wide as the trims it remembers (it was [5][17])
    for (uint8_t bank : { 5, 6 })
        for (uint8_t view : { (uint8_t) FRONTVIEW, (uint8_t) TRIM_VIEW })
        {
            openView(view, 1, false); if (view == TRIM_VIEW) { SendCommand((char *) "page TrimView"); loopFor(400); }
            Trims[bank][0] = 95; Trims[bank][1] = 70; Trims[bank][2] = 82; Trims[bank][3] = 101;
            swBank = bank; RealGetBank(); loopFor(300);                                // BankHasChanged: LastTrim[bank][..] = 0, UpdateTrimView
            Page &pg = screen.pages[view == TRIM_VIEW ? "TrimView" : "FrontView"];
            CHECK(pg.boxes["ch1"].val == 95 && pg.boxes["n1"].val == 15 && pg.boxes["ch4"].val == 70 && pg.boxes["ch2"].val == 82 && pg.boxes["ch3"].val == 101 && LastTrim[bank][3] == 101);   // (the sliders by trim: ch1, ch4, ch2, ch3)
            Trims[bank][3] = 102; UpdateTrimView(); loopFor(100); CHECK(pg.boxes["ch3"].val == 102 && LastTrim[bank][3] == 102);
            ForceDataRedisplay(); { bool zero = true; for (auto &b : LastTrim) for (int x : b) zero &= x == 0; CHECK(zero); }       // every bank, every channel (it was 5 by 17)
            if (bank == 6) say("B1. bank %u on the %s: the trims shown are %d %d %d %d\n", (unsigned) bank, view == TRIM_VIEW ? "Trim page" : "front page", (int) pg.boxes["ch1"].val, (int) pg.boxes["ch2"].val, (int) pg.boxes["ch3"].val, (int) pg.boxes["ch4"].val);
        }
    //     ... a trim that Trim setup gave channel 7: shown again at every bank change (BankHasChanged forgot the first four channels only)
    openView(FRONTVIEW, 1, false); InputTrim[0] = 6; Trims[1][6] = 90; Trims[2][6] = 70;
    { Page &pg = screen.pages["FrontView"];
      swBank = 2; RealGetBank(); loopFor(200); const long in2 = pg.boxes["ch1"].val;
      swBank = 1; RealGetBank(); loopFor(200); const long in1 = pg.boxes["ch1"].val;
      swBank = 2; RealGetBank(); loopFor(200); const long in2again = pg.boxes["ch1"].val;
      swBank = 1; RealGetBank(); loopFor(200);
      say("     the aileron trim set to move channel 7: bank 2 shows %ld, bank 1 %ld, bank 2 again %ld, bank 1 again %ld\n", in2, in1, in2again, (long) pg.boxes["ch1"].val);
      CHECK(in2 == 70 && in1 == 90 && in2again == 70 && pg.boxes["ch1"].val == 90); }                 // (it was: the slider stayed where the bank before left it)
    // B2. "Move these trims into subtrim" on six banks, in bank 5: every bank's trim goes to centre, the servos of bank 5 do not move
    for (uint8_t mode : { 1, 2 })
    {
        openView(TRIM_VIEW, 5, false); SticksMode = mode;
        for (int b = 1; b <= 6; ++b) for (int c = 0; c < 4; ++c) Trims[b][c] = 80 + b + c;       // (every bank has trims of its own)
        Trims[5][0] = 90; Trims[5][1] = 75; Trims[5][2] = 84; Trims[5][3] = 80;
        int flown[4]; for (int c = 0; c < 4; ++c) flown[c] = GetTrimAmount(InPutStick[c]) + (SubTrims[c] - 127) * 5;
        int over = -1; const bool moved = TrimsIntoSubtrims(&over);
        bool centred = true; for (int b = 1; b <= 6; ++b) for (int c = 0; c < 4; ++c) centred &= Trims[b][c] == 80;
        bool same = true; for (int c = 0; c < 4; ++c) same &= GetTrimAmount(InPutStick[c]) + (SubTrims[c] - 127) * 5 == flown[c];
        say("B2. sticks mode %u, bank 5 of six: moved %d, every bank's trims at centre %d (banks 5 and 6 kept theirs), the servos of bank 5 where they were %d; sub trims %d %d %d %d\n", (unsigned) mode, (int) moved, (int) centred, (int) same,
            (int) SubTrims[0] - 127, (int) SubTrims[1] - 127, (int) SubTrims[2] - 127, (int) SubTrims[3] - 127);
        CHECK(moved && over == 0 && centred && same && SubTrims[0] == 137 && SubTrims[3] == 127);
    }
    //     ... and more than the card keeps, in bank 6: NOTHING is changed, in no bank (the wording and the limits: dev/test_bugfixes)
    openView(TRIM_VIEW, 6, false); SubTrims[2] = 127 + 110; Trims[6][2] = 88; Trims[6][0] = 85; Trims[3][0] = 70;
    { int tBefore[BANKS_USED + 1][CHANNELSUSED + 1]; uint8_t sBefore[CHANNELSUSED + 1]; memcpy(tBefore, Trims, sizeof tBefore); memcpy(sBefore, SubTrims, sizeof sBefore);
      int over = -1; const bool moved = TrimsIntoSubtrims(&over);
      CHECK(!moved && over == 3 && !memcmp(tBefore, Trims, sizeof tBefore) && !memcmp(sBefore, SubTrims, sizeof sBefore)); }
    // K. their kin
    //  - 'Trims: all banks': a click of the aileron trim, set to move channel 7, reaches every bank (it copied channels 1 to 4 whatever the trims moved)
    openView(TRIM_VIEW, 2, false); CopyTrimsToAll = true; InputTrim[0] = 6; Trims[2][6] = 85; Trims[2][0] = 83;   // (channel 1 - which no lever moves now - stands at 83 in this bank alone)
    MoveaTrim(0);                                                                   // (aileron trim, one click up)
    { bool all = true; for (int b = 1; b <= 6; ++b) all &= Trims[b][6] == 86;
      say("K.  'Trims: all banks', the aileron trim moving channel 7: one click in bank 2 - every bank has it: %d\n", (int) all);
      CHECK(all); for (int b = 1; b <= 6; ++b) for (int c = 0; c < 4; ++c) CHECK(Trims[b][c] == (c == 0 ? 83 : 80)); }   // (... and channels 1 to 4 are made the same in every bank, as ever - channel 1 too, which no lever moves here)
    //     ... and with the trims on their own channels, as ever
    openView(TRIM_VIEW, 3, false); CopyTrimsToAll = true; MoveaTrim(7); MoveaTrim(7);                 // (rudder trim down, twice)
    { bool all = true; for (int b = 1; b <= 6; ++b) all &= Trims[b][3] == 78; CHECK(all); }
    openView(TRIM_VIEW, 3, false); CopyTrimsToAll = false; MoveaTrim(7);
    { bool only = true; for (int b = 1; b <= 6; ++b) only &= Trims[b][3] == (b == 3 ? 79 : 80); CHECK(only); }
    //  - "all trims to centre" with 'Trims: all banks': channel 16 too, in every bank (it stopped at channel 15 in the other banks)
    openView(TRIM_VIEW, 2, false); CopyTrimsToAll = true; for (int b = 1; b <= 6; ++b) for (int c = 0; c < 16; ++c) Trims[b][c] = 95;
    trims50Lines();
    { bool all = true; for (int b = 1; b <= 6; ++b) for (int c = 0; c < 16; ++c) all &= Trims[b][c] == 80; say("    all trims to centre, 'Trims: all banks': every channel of every bank at centre %d\n", (int) all); CHECK(all); }
    openView(TRIM_VIEW, 2, false); CopyTrimsToAll = false; for (int b = 1; b <= 6; ++b) for (int c = 0; c < 16; ++c) Trims[b][c] = 95;
    trims50Lines();
    { bool only = true; for (int b = 1; b <= 6; ++b) for (int c = 0; c < 16; ++c) only &= Trims[b][c] == (b == 2 ? 80 : 95); CHECK(only); }
    //  - a model taken in with the other sticks mode: the elevator and throttle trims of ALL its banks change places (banks 5 and 6 kept theirs)
    openView(FRONTVIEW, 1, false); for (int b = 1; b <= 6; ++b) { Trims[b][1] = 60 + b; Trims[b][2] = 100 + b; }
    SavedSticksMode = 2; SticksMode = 1; sticksModeSwapLines();
    { bool all = true; for (int b = 1; b <= 6; ++b) all &= Trims[b][1] == 100 + b && Trims[b][2] == 60 + b; say("    a model taken in with the other sticks mode: the two trims of every bank changed places %d\n", (int) all); CHECK(all); }
    SavedSticksMode = 1; sticksModeSwapLines(); { bool kept = true; for (int b = 1; b <= 6; ++b) kept &= Trims[b][1] == 100 + b; CHECK(kept); }   // the same mode: nothing swapped
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('bank_shown_again', SCENES, extra=EXTRA, more_defines=('SLOWSERVOVIEW', 'CHANNELSUSED', 'TRIM_VIEW', 'GRAPHVIEW', 'PIDVIEW', 'RFGOVERNORVIEW_PROFILE', 'PIDADVANCEDVIEW', 'RESCUEVIEW',
                                                                               'RESCUE2VIEW', 'EASYVIEW', 'ROTORFLIGHTVIEW', 'RFBACKUP_RESTOREVIEW', 'PICKBANKVIEW1', 'PICKBANKVIEW2', 'RATESVIEW_RF', 'LISTENMODE',
                                                                               'BEEPCOMPLETE', 'BEEPMIDDLE', 'CLICKZERO', 'DEFAULTTRIMREPEATSPEED')))
