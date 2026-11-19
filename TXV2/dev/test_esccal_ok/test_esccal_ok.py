#!/usr/bin/env python3
"""OK ON THE ESC THROTTLE-CALIBRATION PAGE WITH UNSAVED BASICS EDITS (B211, the sixteenth review - reviewer B's run, taken into the suite; released
code had it). That page's OK is the basics' own; the question's way back, the save and its poll knew three pages: the screen went to BasicsView
while the board believed in the ESC page, the first write went out and the poll dropped the save. Now the page before is put up first.
The REAL RF_Basics.h, RF_EscCal.h and RF_SaveNow.h over dev/test_basics' pretend screen and flight controller.
(The ESC calibration page's own test, B100, is dev/test_esccal.)"""
import os, subprocess, sys, tempfile
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src = open(os.path.join(ROOT, 'dev', 'test_basics', 'test_basics.py'), encoding='utf-8').read()
head = src[:src.index("d = tempfile.mkdtemp()")].replace("ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))", "ROOT = %r" % ROOT)
ns = {}; exec(head, ns); prog = ns['prog']
esccal = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_EscCal.h'), encoding='utf-8').read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '')

def rep(a, b, n=1):
    global prog
    assert prog.count(a) == n, (a, prog.count(a))
    prog = prog.replace(a, b)

# the real EscCalStop, not the stub
rep("static int ecalStops = 0; void EscCalStop() { ++ecalStops; }", "void EscCalStop();")
# the screen's page: a page command, and the way back of a box or a question
rep("static void SendCommand(char *c) { cmds.push_back(c); }",
    "static std::string screenPage = \"?\";\nstatic void SendCommand(char *c) { cmds.push_back(c); if (!strncmp(c, \"page \", 5)) screenPage = c + 5; }")
rep("static void MsgBox(char *page, const char *msg) { ++boxes; lastBox = msg; boxPages.push_back(page); RfLeaveAfterSave = false;",
    "static void MsgBox(char *page, const char *msg) { ++boxes; lastBox = msg; boxPages.push_back(page); RfLeaveAfterSave = false; SendCommand(page);")
rep("static bool GetConfirmation(char *page, char *prompt) { ++asked; lastBox = prompt;",
    "static bool GetConfirmation(char *page, char *prompt) { ++asked; lastBox = prompt; SendCommand(page);")
rep("static bool GetSaveOrDiscard(char *, char *prompt) { ++saveNowAsked; lastBox = prompt; return saveNowAnswer == 1; }",
    "static bool GetSaveOrDiscard(char *page, char *prompt) { ++saveNowAsked; lastBox = prompt; SendCommand(page); return saveNowAnswer == 1; }")
i = prog.index("static int checks = 0, fails = 0;")
main = r'''
static int writes(int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; }
static void fakeFc() {
    memset(mix, 0, sizeof mix); mix[5] = 2; w16(mix, 9, 1500);
    memset(mot, 0, sizeof mot); w16(mot, 0, 1070); w16(mot, 2, 2000); w16(mot, 4, 1000); mot[6] = 1; mot[7] = 10; mot[9] = 0; w16(mot, 10, 250);
    mot[13] = 10; mot[14] = mot[15] = mot[16] = 10; w16(mot, 21, 10); w16(mot, 23, 102); w16(mot, 25, 19); w16(mot, 27, 85);
    memset(esc, 0, sizeof esc); esc[0] = 4; esc[1] = 1; w16(esc, 2, 50);
    memcpy(board, "RDMS", 4); board[4] = 1; board[5] = 0; board[6] = 2; board[7] = 0; board[8] = 7; memcpy(board + 9, "NEXUS_X", 7); board[16] = 7; memcpy(board + 17, "NEXUS_X", 7); boardLen = 24;
    memset(ports, 0, sizeof ports);
    const uint8_t ids[6] = {0, 1, 2, 3, 5, 20}; const uint32_t masks[6] = {64, 1024, 0, 0, 1, 1};
    for (int k = 0; k < 6; ++k) { uint8_t *p = ports + k * 9; p[0] = ids[k]; p[1] = masks[k] & 255; p[2] = (masks[k] >> 8) & 255; p[5] = k == 4 || k == 5 ? 5 : 0; p[6] = 1; p[7] = 1; p[8] = 5; }
    portsN = 6; portsMissing = false; feat = (1u << 3) | (1u << 26) | (1u << 29) | (1u << 30);
}
static void run(int n = 60) { for (int i = 0; i < n; ++i) { BasicsPoll(); EscCalPoll(); now += 250; } }   // (main.cpp ManageTransmitter: both polls, every pass)
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void toEscPageEdited() {
    fakeFc(); fcLog.clear(); cmds.clear(); Bas_Was_Edited = false; RfLeaveAfterSave = false; BasStep = BAS_IDLE;
    CurrentView = RFSETUPVIEW; StartBasicsView(); run();
    BasicsDirectionTapped(); fields["tn5"] = "12"; BasicsWasEdited();            // page 1: the rotor direction turned round, 12 poles typed
    StartBasics2View(); StartBasics3View(); StartEscCalView();                     // Next >, Next >, Next >: the throttle calibration
}
int main() {
    // 1. OK on the throttle-calibration page, the edits of page 1 not yet saved; "Save now?" - Save; "Save the basics?" - Yes
    toEscPageEdited();
    CHECK(BasHave && Bas_Was_Edited && CurrentView == ESCCALVIEW && screenPage == "EscCalView");
    saveNowAnswer = 1; confirmAnswer = true; fcLog.clear(); saveNowAsked = 0; asked = 0; rfStarts = 0;
    EndBasicsView();
    CHECK(saveNowAsked == 1 && CurrentView == PORTSVIEW && screenPage == "PortsView");   // the page before came first: screen and board on the same page, one the save knows
    run(120);
    printf("1. OK on the ESC page with unsaved basics, Save: the screen '%s', the view %d; sent 43 x%d, 222 x%d, 250 (store) x%d; the flight controller holds direction %d and %d poles; the menu opened %d time(s)\n",
           screenPage.c_str(), CurrentView, writes(43), writes(222), writes(250), mix[0], mot[13], rfStarts);
    CHECK(writes(43) == 1 && writes(222) == 1 && writes(250) >= 1 && mix[0] == 1 && mot[13] == 12);   // the whole save, stored (it was: the first write, then nothing - "Writing ..." for ever)
    CHECK(BasStep == BAS_IDLE && !Bas_Was_Edited && rfStarts == 1 && !RfLeaveAfterSave);               // ... and the page closed, as OK's "Save now?" does
    // 2. the same, Discard: nothing written, the menu
    toEscPageEdited(); saveNowAnswer = 0; fcLog.clear(); rfStarts = 0; EndBasicsView(); run(20);
    CHECK(writes(43) == 0 && writes(222) == 0 && writes(250) == 0 && rfStarts == 1 && !Bas_Was_Edited && mix[0] == 0);
    // 3. nothing edited: OK on the ESC page goes to the menu at once, as ever
    fakeFc(); Bas_Was_Edited = false; CurrentView = RFSETUPVIEW; StartBasicsView(); run(); StartBasics2View(); StartBasics3View(); StartEscCalView();
    saveNowAsked = 0; rfStarts = 0; cmds.clear(); EndBasicsView(); CHECK(saveNowAsked == 0 && rfStarts == 1);
    // 4. a box's way back from the ESC page is the ESC page
    CurrentView = ESCCALVIEW; CHECK(!strcmp(BasPageWord(), "page EscCalView")); CurrentView = PORTSVIEW; CHECK(!strcmp(BasPageWord(), "page PortsView"));
    CurrentView = BASICS2VIEW; CHECK(!strcmp(BasPageWord(), "page Basics2View")); CurrentView = BASICSVIEW; CHECK(!strcmp(BasPageWord(), "page BasicsView"));
    printf("test_esccal_ok: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
prog = prog[:i] + esccal + main
import shutil, atexit
d = tempfile.mkdtemp(); atexit.register(shutil.rmtree, d, True); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-const-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:5000]); sys.exit('test_esccal_ok: DID NOT COMPILE')
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
