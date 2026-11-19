#!/usr/bin/env python3
"""Review 17, reviewer B. THE RESCUE PAGE'S BANK HOLD AND THE OTHER SWITCH THAT MOVES THE BANK.
Switches.h ReadBankSwitch asks RescueHoldsBanks(); Switches.h ReadAutoAndMotorSwitch (the 'Bank 4 & Motor' switch: its middle and far positions
set Bank = UpperBank() - bank 4, or 4/5/6 by the 'Banks 1 2 3' switch with Six banks on) asks BlockBankChanges only. main.cpp GetBank calls one
behind the other. This run: the REAL RF_Rescue.h, RF_SaveNow.h, Switches.h's BanksCount / BankOf123 / UpperBank / ReadBankSwitch /
ReadAutoAndMotorSwitch and main.cpp's own GetBank (lifted by name), over dev/test_basics' pretend screen and dev/test_rescuebank's pretend
flight controller (a rescue block for each bank; it is on the bank last chosen - by MSP 210, or by the bank's channel, which follows the
transmitter's bank: RF_Adjust.h B83).
   python3 exp_rescue_autoswitch.py [path to the tree]      (default: the lean copy beside this folder)"""
import os, re, subprocess, sys, tempfile, shutil, atexit
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (taken into the suite: this file's own tree)
RESCUE_H = os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Rescue.h')
SWITCHES_H = os.path.join(ROOT, 'TransmitterCode', 'include', 'Switches.h')
src = open(os.path.join(ROOT, 'dev', 'test_basics', 'test_basics.py'), encoding='utf-8').read()
head = src[:src.index("d = tempfile.mkdtemp()")].replace("ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))", "ROOT = %r" % ROOT)
ns = {}; exec(head, ns); prog = ns['prog']
strip = lambda t: t.replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '')
inc = lambda f: strip(open(os.path.join(ROOT, 'TransmitterCode', 'include', f), encoding='utf-8').read())
basics = inc('RF_Basics.h')
assert prog.count(basics) == 1
def rep(a, b):
    global prog
    assert prog.count(a) == 1, (a, prog.count(a))
    prog = prog.replace(a, b)
rep("static long FieldNumber(const char *name, long lo, long hi) { char t[24] = \"\"; GetText((char *)name, t, sizeof(t) - 1); long v = strtol(t, nullptr, 10); return v < lo ? lo : v > hi ? hi : v; }", "")
rep("bool PipeReplyLate() { return false; }", "bool PipeReplyLate() { return now - PipeReqSentMs > 9000; }")
rep("static void SendText(char *n, char *t) { fields[n] = t; }", "static std::vector<std::string> said;\nstatic void SendText(char *n, char *t) { fields[n] = t; if (!strcmp(n, \"busy\")) said.push_back(t); }")
rep("int MspAsk(uint8_t fn, const uint8_t *data, int len) {", "static uint8_t rescue[6][28]; static int fcBank = 0, fail210 = 0; static bool fcMute = false;\nint MspAsk(uint8_t fn, const uint8_t *data, int len) {")
rep('    fcReply(404, "unknown"); return PipeReqId;\n}', '''    if (fcMute && (fn == 210 || fn == 146 || fn == 147)) return PipeReqId;
    if (fn == 210) { if (fail210 > 0) { --fail210; fcReply(503, "the receiver did not answer"); return PipeReqId; } fcBank = data[0] & 7; fcReply(200, ""); return PipeReqId; }
    if (fn == 146) { fcReply(200, hexOf(rescue[fcBank], 28)); return PipeReqId; }
    if (fn == 147) { memcpy(rescue[fcBank], data, 28); fcReply(200, ""); return PipeReqId; }
    fcReply(404, "unknown"); return PipeReqId;\n}''')
SW = open(SWITCHES_H, encoding='utf-8').read()
def lift(text, start):
    i = text.index(start); return text[i:text.index('\n}\n', i) + 3]
def one(text, start):
    i = text.index(start); return text[i:text.index('\n', i) + 1]
MAIN = open(os.path.join(ROOT, 'TransmitterCode', 'src', 'main.cpp'), encoding='utf-8').read()
GETBANK = lift(MAIN, 'void GetBank()')
helpers = r'''
#define RESCUEVIEW 58
#define RESCUE2VIEW 59
#define BANKS_USED 6
#define NORMAL 0
#define LISTENMODE 7
#define CRUMB(x)
#define CRUMB_BANK 0
static uint8_t Bank = 1, PreviousBank = 1, BankSwitch = 4, Autoswitch = 1; static bool BlockBankChanges = false, SixBanks = false, MotorEnabled = false, MotorWasEnabled = false;
static int ParametersToBeSentPointer = 0, CurrentMode = NORMAL;
static bool BuddyPupilOnWireless = false, BuddyHasAllSwitches = false, SendNoData = false, SafetyON = true, SafetyWasOn = true, UseMotorKill = true;
static uint8_t pos[9];
static uint8_t GetSwitchPosition(uint8_t n) { return n >= 1 && n <= 8 ? pos[n] : 0; }
static bool CopyBankRunning() { return false; } static bool EasyHoldsBanks() { return false; }
static char *Str(char *b, int v, int) { snprintf(b, 10, "%d", v); return b; }
static void SendValue(char *n, int v) { fields[n] = std::to_string(v); }
bool RescueHoldsBanks();
static bool RfSaveHoldsBank() { return false; }   // (B211, e101: RF_Verify.h - a bank page's save holds the bank switch itself; dev/test_bankblock and dev/test_savehold run the real one)
static void SafetyHoldUpdate() {} static void ReadSafetySwitch() {} static void ReadBuddySwitch() {} static void ReadDualRateSwitch() {} static void SafetySwitchChanged() {}
static void ReadChannelSwitches9to12() {}
#define FRONTVIEW 0
static int motorChanges = 0; static bool ModalWaits = false; static int frontPages = 0;
static void MotorEnabledHasChanged() { ++motorChanges; if (MotorEnabled && CurrentView != FRONTVIEW && CurrentMode == NORMAL && !ModalWaits) { CurrentView = FRONTVIEW; ++frontPages; } }   // (Motor_sign.h: B16 - the motor going ON brings the front page)
void BankHasChanged();
'''
main = one(SW, 'uint8_t BanksCount()') + lift(SW, 'uint8_t BankOf123()') + one(SW, 'static uint8_t UpperBank()') + lift(SW, 'void ReadBankSwitch()') + lift(SW, 'void ReadAutoAndMotorSwitch()') + GETBANK + r'''
// Switches.h BankHasChanged, the part of it that matters here (its own words): nothing for a bank shown again; the Rescue page told of a new bank.
// The flight controller's bank follows the bank's channel - that is, the transmitter's bank.
static int bankChanges = 0;
void BankHasChanged() { if (Bank == PreviousBank) return; ++bankChanges; fcBank = Bank - 1; if (CurrentView == RESCUEVIEW || CurrentView == RESCUE2VIEW) RescueBankChanged(); }
static void loopPass() { GetBank(); RescuePoll(); now += 20; }
static void run(int n = 1) { for (int i = 0; i < n; ++i) loopPass(); }
static void block(int b, int mode, int pull, int climb, int hover) { uint8_t *r = rescue[b]; memset(r, 0, 28); r[0] = mode; r[1] = 0; r[2] = 30; r[3] = 40; r[4] = 5; r[5] = 10; r[6] = 100; r[7] = 5; w16(r, 8, pull); w16(r, 10, climb); w16(r, 12, hover); w16(r, 14, 2000); w16(r, 16, 20); w16(r, 18, 20); w16(r, 20, 20); w16(r, 22, 100); }
static void fresh(bool six, int autoPos, int bankPos) {
    for (int b = 0; b < 6; ++b) block(b, b == 0 || b == 3 ? 1 : 0, 650 - 10 * b, 450 - 10 * b, 300 + 10 * b);     // every bank its own block: hover collective 30.0 + b %
    SixBanks = six; pos[4] = (uint8_t) bankPos; pos[1] = (uint8_t) autoPos; BankSwitch = 4; Autoswitch = 1; SafetyON = SafetyWasOn = true; MotorEnabled = MotorWasEnabled = false;
    BlockBankChanges = false; CurrentView = ROTORFLIGHTVIEW; Rescue_Was_Edited = false; RescueRereadWanted = false; RescueStep = RSC_IDLE; RfLeaveAfterSave = false; menuShut = false; fail210 = 0; fcMute = false;
    boxes = 0; said.clear(); fcLog.clear(); motorChanges = 0; bankChanges = 0;
    Bank = PreviousBank = 0; GetBank(); PreviousBank = Bank; fcBank = Bank - 1;                                   // the switches as they stand
}
static int askedFn(int fn) { int n = 0; for (auto &r : fcLog) n += r.fn == fn; return n; }
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
// One trial: the page opened on the bank the switches give, hover collective typed 42 %, Save - and 'when' loop passes on one switch moves.
// Says which bank of the flight controller holds the edit at the end.
static int trial(const char *what, bool six, int auto0, int bank0, int auto1, int bank1, int when, bool viaQuestion, bool show) {
    fresh(six, auto0, bank0);
    const int shown = Bank;                                                              // the bank the page shows
    StartRescueView(); run(10);
    if (!RescueHave) { printf("  (%s: the page did not read)\n", what); return -1; }
    fields["tn6"] = "42"; RescueWasEdited(); fcLog.clear();
    if (viaQuestion) { saveNowAnswer = 1; pos[1] = (uint8_t) auto1; pos[4] = (uint8_t) bank1; EndRescueView(); saveNowAnswer = 0; }   // OK - "Save now?" is up - the switch moves - Save
    else { SaveRescue(); run(when); pos[1] = (uint8_t) auto1; pos[4] = (uint8_t) bank1; }                                              // Save - 'when' passes - the switch moves
    const bool heldAtMove = RescueHoldsBanks();
    run(150);
    int holder = -1, n = 0;
    for (int b = 0; b < 6; ++b) if (u16(rescue[b], 12) == 420) { holder = b + 1; ++n; }
    if (show) printf("  %-58s when %2d: the page showed Bank %d, held at the move %d; the edit is in bank %d of the flight controller (%d bank%s hold it); the 'too late' box came %d time(s); the transmitter is on Bank %d; motor changes %d\n",
                     what, when, shown, (int) heldAtMove, holder, n, n == 1 ? "" : "s", boxes, Bank, motorChanges);
    return holder == shown && n == 1 ? 1 : 0;
}
static int lastSelect() { for (int k = (int) fcLog.size() - 1; k >= 0; --k) if (fcLog[k].fn == 210) return (int) strtol(fcLog[k].data.c_str(), nullptr, 16) + 1; return 0; }
static void openAndEdit(bool six, int auto0, int bank0, bool safety) {
    fresh(six, auto0, bank0); SafetyON = SafetyWasOn = safety; frontPages = 0; ModalWaits = false; UseMotorKill = true;
    StartRescueView(); run(10); fields["tn6"] = "42"; RescueWasEdited(); fcLog.clear();
}
int main() {
    // (b) THE MOTOR SWITCH IS NEVER HELD. No safety switch (or the safety off): MotorEnabled is the switch's own word. The Rescue page's save is under way and
    //     gets no answer (the hold stands for nine seconds): the 'Bank 4 & Motor' switch is moved - every way - and MotorEnabled must follow IN THAT PASS.
    printf("b. the motor's own word under the hold (no safety switch; the save gets no answer, so the hold stands)\n");
    static const int moves[6][2] = {{3, 1}, {3, 2}, {1, 3}, {2, 3}, {2, 1}, {1, 2}};
    for (int kill = 1; kill >= 0; --kill) for (int m = 0; m < 6; ++m) {
        const int from = moves[m][0], to = moves[m][1];
        openAndEdit(false, 3, 1, true);                                 // (opened as it must be: the motor off, bank 4)
        pos[1] = (uint8_t) from; SafetyON = SafetyWasOn = false; UseMotorKill = false; run(1); UseMotorKill = kill; MotorWasEnabled = MotorEnabled;   // the switch as the move begins (no front page for this)
        CurrentView = RESCUEVIEW; run(40); fields["tn6"] = "42"; RescueWasEdited();   // (the move may have changed the bank: the page has read it again, and is edited again)
        const int shown = Bank;
        fcMute = true; SaveRescue(); run(2);
        const bool held0 = RescueHoldsBanks(); const bool wantMotor = to != 3; const int bankAtHold = Bank;
        pos[1] = (uint8_t) to; motorChanges = 0; frontPages = 0;
        GetBank();                                                       // ONE pass of the switches
        const bool followed = MotorEnabled == wantMotor;
        printf("   switch %d -> %d (motor kill %d): held before the move %d; in the pass of the move the motor is %s (the switch says %s), its change was served %d time(s), the front page came %d, the bank is %d (was %d)\n",
               from, to, kill, (int) held0, MotorEnabled ? "ON" : "off", wantMotor ? "ON" : "off", motorChanges, frontPages, Bank, bankAtHold);
        CHECK(held0); CHECK(followed);
        if (kill) CHECK(motorChanges == ((from != 3) != wantMotor ? 1 : 0));
        if (CurrentView == RESCUEVIEW) CHECK(Bank == bankAtHold);       // the page still up: the bank is held (the front page lets it go - next pass)
        (void) shown;
    }
    // ... and with the safety ON (the page's own state): the motor is off whatever the switch says - and stays the switch's servant the moment the safety goes off
    { openAndEdit(false, 1, 1, true); fcMute = true; SaveRescue(); run(2); CHECK(RescueHoldsBanks());
      pos[1] = 3; GetBank(); CHECK(!MotorEnabled); pos[1] = 1; GetBank(); CHECK(!MotorEnabled && Bank == 1);
      SafetyON = false; GetBank();                                      // the safety off under the hold: the motor switch (ON) counts at once - the front page
      printf("   the safety goes OFF under the hold with the motor switch ON: motor %s, front page %d, the hold now %d\n", MotorEnabled ? "ON" : "off", frontPages, (int) RescueHoldsBanks());
      CHECK(MotorEnabled && frontPages == 1 && !RescueHoldsBanks()); }
    // (c) WHEN THE HOLD ENDS: which bank, when, and is the flight controller told?
    printf("c. the hold's end\n");
    for (int way = 0; way < 3; ++way) {                                 // 0: the save works; 1: its write is refused (a box); 2: no answer for nine seconds
        openAndEdit(false, 1, 1, true);
        if (way == 1) failWrite = 147; if (way == 2) fcMute = true;
        SaveRescue(); run(1); CHECK(RescueHoldsBanks());
        pos[4] = 2;                                                      // the 'Banks 1 2 3' switch to 2 while it runs
        int passes = 0; while (RescueHoldsBanks() && passes < 1000) { CHECK(Bank == 1); loopPass(); ++passes; }
        const int bankAtEnd = Bank; const uint32_t tEnd = now;
        int more = 0; while (Bank != 2 && more < 50) { loopPass(); ++more; }
        fcLog.clear(); failWrite = 0; fcMute = false; boxes = 0; run(40);
        printf("   %s: held for %d passes (%d ms); at the pass that ended it the bank was %d; the switch's bank (2) %d pass(es) on; then the page read again: MSP 210 asked for bank %d, 146 asked %d time(s), in hand %d; boxes since %d\n",
               way == 0 ? "the save worked" : way == 1 ? "the write was refused" : "no answer", passes, passes * 20, bankAtEnd, more, lastSelect(), askedFn(146), (int) RescueHave, boxes);
        CHECK(more <= 1); CHECK(lastSelect() == 2 && askedFn(146) >= 1 && RescueHave); (void) tEnd;
    }
    // (a) third roads, by a run where there is one: the SAME hold seen from the two switches at every moment of a working save, four and six banks
    printf("a. both switches moved at every moment of a save (the bank the edit landed in)\n");
    int good = 0, total = 0;
    for (int six = 0; six < 2; ++six) for (int when = 0; when < 14; ++when) for (int mv = 0; mv < 4; ++mv) {
        const int auto0 = six ? 3 : 1, bank0 = 1; const int auto1 = mv == 0 ? (six ? 3 : 3) : mv == 1 ? 2 : auto0, bank1 = mv >= 2 ? (mv == 2 ? 2 : 3) : bank0;
        const int r = trial("", six, auto0, bank0, six && mv < 2 ? 2 : auto1, bank1, when, false, false); good += r == 1; ++total;
    }
    printf("   the save landed in the bank the page showed in %d of %d trials\n", good, total); CHECK(good == total);
    printf("exp_hold_motor: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
i = prog.index(basics)
prog = prog[:i] + helpers + strip(open(RESCUE_H, encoding='utf-8').read()) + main
d = tempfile.mkdtemp(); atexit.register(shutil.rmtree, d, True)
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-const-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit('exp_hold_motor: DID NOT COMPILE')
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
