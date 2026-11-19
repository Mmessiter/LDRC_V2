#!/usr/bin/env python3
"""THE RESCUE PAGE AND THE BANK SWITCH (B211, the sixteenth review - reviewer B's runs E2, E2b, E3 and E10, taken into the suite; 16 Nov 2026).
 E2  (RELEASED CODE had it, HIGH) a SAVE under way when the bank switch moves: the save chooses its bank (MSP 210) and writes behind it (147) -
     the switch moved in between took the flight controller to the other bank, and bank 1's edited values were written into BANK 2, stored and
     read back "the same". Now THE BANK SWITCH IS HELD WHILE THE SAVE RUNS (RescueHoldsBanks; Switches.h ReadBankSwitch): the save lands in the
     bank the page shows, the switch is read when it has ended, and the new bank is then read.
 E2b the same by OK's "Save now?": the switch was moved WHILE THE QUESTION WAS UP (no switch is read there).
 E3  a READ under way when the switch moves is dropped: its answer put "in hand" back with the old bank's block under the new bank's name.
 E10 "< Previous" on the standing "NOT READ" page 2: nothing is drawn from the block of the read before - page 1 reads.
 B10 with nothing in hand nothing is an edit, and a Save refused for it does not leave "close when saved" standing.
The REAL RF_Rescue.h and RF_SaveNow.h, and Switches.h's own ReadBankSwitch, over dev/test_basics' pretend screen and a pretend flight controller
that keeps a rescue block for each bank and is on the bank last chosen - by MSP 210, or by the bank's channel (which follows the transmitter's
bank: RF_Adjust.h B83)."""
import os, re, subprocess, sys, tempfile, shutil, atexit
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src = open(os.path.join(ROOT, 'dev', 'test_basics', 'test_basics.py'), encoding='utf-8').read()
head = src[:src.index("d = tempfile.mkdtemp()")].replace("ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))", "ROOT = %r" % ROOT)
ns = {}; exec(head, ns); prog = ns['prog']
inc = lambda f: open(os.path.join(ROOT, 'TransmitterCode', 'include', f), encoding='utf-8').read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '')
basics = inc('RF_Basics.h')
assert prog.count(basics) == 1
def rep(a, b):
    global prog
    assert prog.count(a) == 1, (a, prog.count(a))
    prog = prog.replace(a, b)
rep("static long FieldNumber(const char *name, long lo, long hi) { char t[24] = \"\"; GetText((char *)name, t, sizeof(t) - 1); long v = strtol(t, nullptr, 10); return v < lo ? lo : v > hi ? hi : v; }", "")
rep("bool PipeReplyLate() { return false; }", "bool PipeReplyLate() { return now - PipeReqSentMs > 9000; }")   # (PipeHttp.h's own rule: nine seconds)
rep("static void SendText(char *n, char *t) { fields[n] = t; }", "static std::vector<std::string> said;\nstatic void SendText(char *n, char *t) { fields[n] = t; if (!strcmp(n, \"busy\")) said.push_back(t); }")
rep("int MspAsk(uint8_t fn, const uint8_t *data, int len) {", "static uint8_t rescue[6][28]; static int fcBank = 0, fail210 = 0; static bool fcMute = false;\nint MspAsk(uint8_t fn, const uint8_t *data, int len) {")
rep('    fcReply(404, "unknown"); return PipeReqId;\n}', '''    if (fcMute && (fn == 210 || fn == 146 || fn == 147)) return PipeReqId;   // (no answer at all)
    if (fn == 210) { if (fail210 > 0) { --fail210; fcReply(503, "the receiver did not answer"); return PipeReqId; } fcBank = data[0] & 7; fcReply(200, ""); return PipeReqId; }
    if (fn == 146) { fcReply(200, hexOf(rescue[fcBank], 28)); return PipeReqId; }
    if (fn == 147) { memcpy(rescue[fcBank], data, 28); fcReply(200, ""); return PipeReqId; }
    fcReply(404, "unknown"); return PipeReqId;\n}''')
SW = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'Switches.h'), encoding='utf-8').read()
i = SW.index('void ReadBankSwitch()'); READBANK = SW[i:SW.index('\n}\n', i) + 3]
helpers = r'''
#define RESCUEVIEW 58
#define RESCUE2VIEW 59
#define BANKS_USED 6
#define NORMAL 0
static uint8_t Bank = 1, PreviousBank = 1, swBank = 1, BankSwitch = 1; static bool BlockBankChanges = false; static int ParametersToBeSentPointer = 0, CurrentMode = NORMAL;
static bool CopyBankRunning() { return false; } static bool EasyHoldsBanks() { return false; }
static uint8_t GetSwitchPosition(uint8_t) { return swBank; }                 // (the bank switch itself: this test's hand)
static char *Str(char *b, int v, int) { snprintf(b, 10, "%d", v); return b; }
static void SendValue(char *n, int v) { fields[n] = std::to_string(v); }
bool RescueHoldsBanks();
static bool RfSaveHoldsBank() { return false; }   // (B211, e101: RF_Verify.h - a bank page's save holds the bank switch itself; dev/test_bankblock and dev/test_savehold run the real one)
'''
main = READBANK + r'''
// one pass of the main loop: the switches (main.cpp GetBank: ReadBankSwitch, then BankHasChanged), then the page's poll. The flight controller's bank
// follows the bank's channel - that is, the transmitter's bank.
static void loopPass() { ReadBankSwitch(); if (Bank != PreviousBank) { fcBank = Bank - 1; RescueBankChanged(); PreviousBank = Bank; } RescuePoll(); now += 20; }
static void run(int n = 1) { for (int i = 0; i < n; ++i) loopPass(); }
static void block(int b, int mode, int pull, int climb, int hover) { uint8_t *r = rescue[b]; memset(r, 0, 28); r[0] = mode; r[1] = 0; r[2] = 30; r[3] = 40; r[4] = 5; r[5] = 10; r[6] = 100; r[7] = 5; w16(r, 8, pull); w16(r, 10, climb); w16(r, 12, hover); w16(r, 14, 2000); w16(r, 16, 20); w16(r, 18, 20); w16(r, 20, 20); w16(r, 22, 100); }
static void fresh() { block(0, 1, 650, 450, 350); block(1, 0, 500, 400, 300); swBank = 1; Bank = PreviousBank = 1; fcBank = 0; CurrentView = ROTORFLIGHTVIEW; Rescue_Was_Edited = false; RescueRereadWanted = false; RescueStep = RSC_IDLE;
                      RfLeaveAfterSave = false; menuShut = false; fail210 = 0; fcMute = false; boxes = 0; said.clear(); fcLog.clear(); }
static int askedFn(int fn) { int n = 0; for (auto &r : fcLog) n += r.fn == fn; return n; }
static bool bank1Edited() { return rescue[0][0] == 1 && u16(rescue[0], 12) == 420; }                         // bank 1 took the edit (hover collective 42 %)
static bool bank2AsItWas() { return rescue[1][0] == 0 && u16(rescue[1], 12) == 300 && u16(rescue[1], 8) == 500; }
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
int main() {
    // E2. A SAVE UNDER WAY WHEN THE BANK SWITCH MOVES - at every moment of the save
    for (int when = 0; when < 12; ++when)
    {
        fresh(); StartRescueView(); run(10);
        CHECK(RescueHave && !RescueHoldsBanks());
        fields["tn6"] = "42"; RescueWasEdited(); fcLog.clear(); SaveRescue();          // he types 42 % for the hover collective, and presses Save
        CHECK(RescueStep == RSC_W_SELECT && RescueHoldsBanks());
        run(when); swBank = 2;                                                           // the bank switch moves: before the select's answer is looked at, or a step or more on
        const bool heldThen = RescueHoldsBanks();
        run(3); if (heldThen && RescueHoldsBanks()) CHECK(Bank == 1 && fcBank == 0);    // held: the transmitter's bank, and so the flight controller's, stays
        run(120);
        if (when == 0) printf("E2. Save on bank 1, the bank switch moved at once: bank 1 holds mode %d and hover collective %u (the edit: 420), bank 2 mode %d and %u (its own: 300); the page now shows '%s'\n",
                              rescue[0][0], u16(rescue[0], 12), rescue[1][0], u16(rescue[1], 12), fields["t9"].c_str());
        CHECK(bank1Edited() && bank2AsItWas());                                          // (it was: bank 2 held bank 1's edited block - rescue switched ON there - and bank 1 was not written)
        CHECK(askedFn(147) == 1 && askedFn(250) == 1 && !RescueHoldsBanks() && Bank == 2 && fcBank == 1);
        CHECK(RescueHave && fields["t9"] == "Bank 2" && fields["tn0"] == "0" && boxes == 0);   // ... then the switch is read: bank 2 is read and shown (Enable off, as bank 2 has it)
    }
    // E2b. OK - "Save now?" is up - the bank switch moves - Save (no switch is read while a question waits: the main loop sees it behind the select)
    fresh(); StartRescueView(); run(10); fields["tn6"] = "42"; RescueWasEdited(); fcLog.clear(); saveNowAnswer = 1; rfStarts = 0;
    swBank = 2; EndRescueView();
    CHECK(RescueHoldsBanks() && Bank == 1);
    run(120);
    printf("E2b. the switch moved while 'Save now?' was up: bank 1 took the edit %d, bank 2 as it was %d; the page %s\n", (int) bank1Edited(), (int) bank2AsItWas(), CurrentView == RESCUEVIEW ? "stays" : "was left");
    CHECK(bank1Edited() && bank2AsItWas() && askedFn(147) == 1 && CurrentView != RESCUEVIEW && Bank == 2 && !RfLeaveAfterSave);
    saveNowAnswer = 0;
    // ... THE HOLD ENDS: with the save (above), with a step refused, with no answer (nine seconds), with the page gone
    fresh(); StartRescueView(); run(10); fields["tn6"] = "42"; RescueWasEdited(); fail210 = 1; SaveRescue(); swBank = 2; run(3);
    CHECK(!RescueHoldsBanks() && boxes == 2 && Bank == 2 && !bank1Edited() && bank2AsItWas());                        // "Could not select the bank": nothing written, the switch read again (and its box: "... edited but not saved")
    fresh(); StartRescueView(); run(10); fields["tn6"] = "42"; RescueWasEdited(); fcMute = true; SaveRescue(); swBank = 2; run(200);
    CHECK(RescueHoldsBanks() && Bank == 1);                                                                           // (four seconds, no answer: still held)
    run(300); CHECK(!RescueHoldsBanks() && Bank == 2 && boxes >= 1 && !bank1Edited() && bank2AsItWas());              // (past nine: "No answer" - and the switch is read again)
    fresh(); StartRescueView(); run(10); fields["tn6"] = "42"; RescueWasEdited(); fcMute = true; SaveRescue(); CurrentView = ROTORFLIGHTVIEW;
    CHECK(!RescueHoldsBanks()); swBank = 2; run(2); CHECK(Bank == 2 && RescueStep == RSC_IDLE);                       // the page gone: nothing is held
    // E3. A READ UNDER WAY WHEN THE BANK SWITCH MOVES: dropped - nothing is in hand until the new bank has been read
    fresh(); StartRescueView(); CHECK(!RescueHoldsBanks());                              // (a read holds nothing)
    run(1); swBank = 2; run(1);
    CHECK(Bank == 2 && !RescueHave && fields["t9"] == "Bank 2");
    run(2); CHECK(!RescueHave);                                                          // (it was: the old read's answer put "in hand" back - bank 1's block under "Bank 2")
    RescueFlipTapped(); fcLog.clear(); SaveRescue(); run(5); CHECK(askedFn(147) == 0 && askedFn(250) == 0 && !Rescue_Was_Edited);   // a tap and Save inside the 0.4 s: nothing
    run(60);
    printf("E3. a read under way when the switch moved: then bank 2 read - in hand %d, the page shows '%s' with Enable '%s' (bank 2 has it off)\n", (int) RescueHave, fields["t9"].c_str(), fields["tn0"].c_str());
    CHECK(RescueHave && fields["tn0"] == "0" && rescue[0][0] == 1 && bank2AsItWas());
    // E10. "< Previous" on the standing "NOT READ" page 2 (the bank moved there, the new bank's read failed, the menu would not open: the safety off)
    fresh(); StartRescueView(); run(10); StartRescue2View(); menuShut = true; fail210 = 1; swBank = 2; run(40);
    CHECK(boxes == 1 && !RescueHave && CurrentView == RESCUE2VIEW && fields["busy"].find("NOT READ") == 0);
    fields["tn6"] = "?"; fields["tn0"] = "?"; fcLog.clear(); EndRescue2View();
    CHECK(CurrentView == RESCUEVIEW && !RescueHave && askedFn(210) == 1 && fields["tn0"] == "?");   // page 1: nothing drawn from the block of the read before (it was: bank 1's, under "Bank 2") - it reads
    run(10);
    printf("E10. '< Previous' on the standing NOT READ page 2: page 1 read bank 2 - in hand %d, Enable '%s'\n", (int) RescueHave, fields["tn0"].c_str());
    CHECK(RescueHave && fields["tn0"] == "0" && fields["t9"] == "Bank 2");
    //      ... and "Next >" with nothing in hand gathers nothing (a read under way): page 2 reads
    fresh(); StartRescueView(); fields["tn6"] = "77"; fcLog.clear(); StartRescue2View(); CHECK(CurrentView == RESCUE2VIEW && !RescueHave && askedFn(210) == 1);
    run(10); CHECK(RescueHave && u16(RescueWant, 12) == 350);                            // (what stood in page 1's box while it read is not in the block)
    // B10. NOTHING IN HAND: nothing is an edit - and a Save refused for it does not leave "close when saved" standing
    fresh(); StartRescueView(); cmds.clear(); RescueWasEdited(); CHECK(!Rescue_Was_Edited);   // a field touched while the page reads
    rfStarts = 0; saveNowAnswer = 1; EndRescueView(); CHECK(rfStarts == 1 && !RfLeaveAfterSave && askedFn(147) == 0);   // OK: no question - the page is left
    saveNowAnswer = 0;
    fresh(); StartRescueView(); RfLeaveAfterSave = true; SaveRescue(); CHECK(!RfLeaveAfterSave);
    printf("test_rescuebank: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
i = prog.index(basics)
prog = prog[:i] + helpers + inc('RF_Rescue.h') + main
d = tempfile.mkdtemp(); atexit.register(shutil.rmtree, d, True)
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-const-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:5000]); sys.exit('test_rescuebank: DID NOT COMPILE')
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
