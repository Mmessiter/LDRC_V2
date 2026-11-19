#!/usr/bin/env python3
"""Review 17, reviewer B. THE QUIET ROAD ON THE FIVE PAGES (no box while the model may fly: RfBoxOrQuiet in the failure routines, RfMayFly first in
RfLeaveNotRead). What stands afterwards - on the Basics pages, with the REAL RF_Basics.h and RF_SaveNow.h over dev/test_basics' harness (its
stand-ins for PipeHttp.h RfMayFly / RfSayQuietly / RfBoxOrQuiet are those routines' own lines: the quiet branch says a line for the log and
returns; a box clears "close when saved" - Utilities.h MsgBox).
   python3 exp_quiet_road.py [tree]"""
import os, subprocess, sys, tempfile, shutil, atexit
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (taken into the suite: this file's own tree)
src = open(os.path.join(ROOT, 'dev', 'test_basics', 'test_basics.py'), encoding='utf-8').read()
head = src[:src.index("d = tempfile.mkdtemp()")].replace("ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))", "ROOT = %r" % ROOT)
ns = {}; exec(head, ns); prog = ns['prog']
i = prog.index("static int checks = 0, fails = 0;")
j = prog.index("int main()", i)
k = prog.rindex("return fails ? 1 : 0;")
main = r'''
static std::string busyNow() { return (cmdCount("vis busy,1") && cmds.size()) ? fields["busy"] : std::string(""); }
static bool busyShown() { bool on = false; for (auto &x : cmds) { if (x == "vis busy,1") on = true; else if (x == "vis busy,0") on = false; } return on; }
static bool saveShown() { bool on = false; for (auto &x : cmds) { if (x == "vis b3,1") on = true; else if (x == "vis b3,0") on = false; } return on; }
int main() {
    // A. A SAVE THAT FAILS IN ITS MIDDLE WHILE THE MODEL MAY FLY. OK with an edit - "Save now?" - Save - "Save the basics?" - Yes. The mixer block
    //    is written; the safety is turned off (the screen shuts the pipe at once - Parameters.h PipeTick, B49) and the motor block's write fails.
    fakeFc(); offline = false; armed = false; rfMayFlyNow = false; quietSaid = 0; boxes = 0; CurrentView = RFSETUPVIEW; StartBasicsView(); run();
    CHECK(BasHave && CurrentView == BASICSVIEW);
    BasicsDirectionTapped(); CHECK(Bas_Was_Edited);
    saveNowAnswer = 1; confirmAnswer = true; failWrite = 222; fcLog.clear(); cmds.clear(); rfStarts = 0;
    EndBasicsView();                                                             // OK: "Save now?" - Save - Yes: the save runs
    CHECK(RfLeaveAfterSave && BasStep == BAS_WRITE_MIX);
    rfMayFlyNow = true;                                                          // the safety goes off while it runs
    boxes = 0; sounds = 0; run(8);
    printf("A. a save failed at its second write with the safety off: boxes %d, lines for the log %d ('%.60s ...'), sounds %d\n   the page: its line %s; Save %s; the mixer block IS in the flight controller (direction %d, was 0), nothing stored (250 asked %d times)\n   'close when saved' still stands: %d\n",
           boxes, quietSaid, lastQuiet.c_str(), sounds, busyShown() ? ("'" + fields["busy"] + "'").c_str() : "hidden - NOTHING on the page says the save failed", saveShown() ? "shown" : "hidden", mix[0], writes(250), (int) RfLeaveAfterSave);
    CHECK(boxes == 0 && quietSaid == 1 && BasStep == BAS_IDLE && Bas_Was_Edited);
    CHECK(busyShown());                                                          // (a word on the page - as the word pages give: PipeHttp.h RfWordPageSays)
    CHECK(!RfLeaveAfterSave);                                                    // (as a box does, and RfWordPageSays: no "close when saved" behind a save that was not made)
    // ... the safety on again, he presses the Save BUTTON (not OK): the save works - and the page shuts by itself
    rfMayFlyNow = false; failWrite = 0; fcLog.clear(); rfStarts = 0; SaveBasics(); run(120);
    printf("   then the safety on, the Save button: stored %d; the page %s\n", writes(250), CurrentView == BASICSVIEW ? "stays, as a Save button's save does" : "WAS CLOSED BY ITSELF (the OK of a minute ago)");
    CHECK(CurrentView == BASICSVIEW);
    // B. A READ THAT FAILS WHILE THE MODEL MAY FLY: the page stands under its line; what is in hand, what OK does
    fakeFc(); rfMayFlyNow = false; quietSaid = 0; boxes = 0; CurrentView = RFSETUPVIEW; fail42 = 1; cmds.clear(); StartBasicsView(); rfMayFlyNow = true; menuShut = true; run();
    printf("B. a read failed with the safety off: boxes %d, lines for the log %d; the page's line '%s'; in hand %d; Save %s; view %d\n", boxes, quietSaid, busyShown() ? fields["busy"].c_str() : "", (int) BasHave, saveShown() ? "shown" : "hidden", CurrentView);
    CHECK(boxes == 0 && quietSaid == 1 && !BasHave && CurrentView == BASICSVIEW && busyShown() && !saveShown());
    BasicsDirectionTapped(); fields["tn5"] = "14"; BasicsWasEdited(); CHECK(!Bas_Was_Edited && !saveShown());        // nothing is an edit
    fcLog.clear(); SaveBasics(); run(4); CHECK(fcLog.empty());                                                         // Save writes nothing
    rfStarts = 0; EndBasicsView(); CHECK(rfStarts == 0 && CurrentView == BASICSVIEW);                                  // OK with the safety still off: the menu will not open (RotorFlightStart, without a word)
    StartBasics2View(); run(2); CHECK(CurrentView == BASICS2VIEW && BasStep != BAS_IDLE);                              // "Next >" reads again (the pipe is shut: it will fail again, quietly)
    menuShut = false; rfMayFlyNow = false; CurrentView = BASICSVIEW; BasStep = BAS_IDLE; rfStarts = 0; EndBasicsView(); CHECK(rfStarts == 1);   // the safety on: OK leaves, as the line says
    // C. THE GUIDE'S TICK. The page is opened from the guide (RF_Tools.h RfOpenFrom: the guide on the way-back stack); its read fails and the page cannot
    //    be left (the safety off - the quiet road; or the menu refusing without a word): it stands under its line. Safety on, OK.
    for (int quiet = 0; quiet < 2; ++quiet) {
        fakeFc(); rfMayFlyNow = false; menuShut = false; quietSaid = 0; boxes = 0; guideTicks = guideBacks = 0;
        CurrentView = GUIDEVIEW; RfHomeN = 0; RfHome[RfHomeN++] = GUIDEVIEW; RfOpening = true; fail42 = 1; StartBasicsView(); RfOpening = false;   // (RfOpenFrom's own lines)
        CHECK(CurrentView == BASICSVIEW && RfHomeN == 1);
        if (quiet) rfMayFlyNow = true; menuShut = true;                          // the safety off: the model may fly / the menu will not open (RotorFlightStart, without a word, the model connected)
        run(); CHECK(!BasHave && CurrentView == BASICSVIEW && guideTicks == 0);  // NOT READ: the page stands, nothing ticked
        rfMayFlyNow = false; menuShut = false; EndBasicsView();                  // the safety on, OK - as the line says
        printf("C%d. a page opened from the guide, NOT READ (%s), then safety on and OK: back at the guide %d, its step TICKED %d\n", quiet + 1, quiet ? "the quiet road" : "the menu would not open", guideBacks, guideTicks);
        CHECK(guideBacks == 1 && guideTicks == 0);                               // (B11: the guide does not tick a page that could not be read)
    }
    //    ... the control: the read fails with the safety on - the box, and back to the guide at once: not ticked
    fakeFc(); rfMayFlyNow = false; menuShut = false; guideTicks = guideBacks = 0; boxes = 0;
    CurrentView = GUIDEVIEW; RfHomeN = 0; RfHome[RfHomeN++] = GUIDEVIEW; RfOpening = true; fail42 = 1; StartBasicsView(); RfOpening = false; run();
    printf("C3. (control) NOT READ with the safety on: boxes %d, back at the guide %d, ticked %d\n", boxes, guideBacks, guideTicks);
    CHECK(boxes == 1 && guideBacks == 1 && guideTicks == 0 && CurrentView == GUIDEVIEW);
    printf("exp_quiet_road: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
TOOLS = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Tools.h'), encoding='utf-8').read()
def lift(text, head):
    i = text.index(head); jj = text.index('{', i); dd = 0
    for kk in range(jj, len(text)):
        if text[kk] == '{': dd += 1
        elif text[kk] == '}':
            dd -= 1
            if dd == 0: return text[i:kk + 1] + '\n'
old = "static void RotorFlightStart() { homeNotReadAtMenu = RfHomeNotRead; if (menuShut) { if (menuSaysWhy) MsgBox((char *) \"page RXSetupView\", \"The motor is ON.\\r\\nSwitch it off first.\"); return; } ++rfStarts; CurrentView = ROTORFLIGHTVIEW; }"
assert prog.count(old) == 1, prog.count(old)
new = r"""#define RXSETUPVIEW 30
#define FRONTVIEW 0
#define TOOLSVIEW 85
#define GUIDEVIEW 89
#define CHECKVIEW 86
static uint8_t RfHome[2]; static uint8_t RfHomeN = 0; static bool RfOpening = false;
static int guideTicks = 0, guideBacks = 0;
static void RfShowHome(uint8_t v, bool cameBack) { ++guideBacks; if (cameBack) ++guideTicks; CurrentView = v; }   // (RF_Tools.h RfShowHome -> RF_Guide.h GuideShowAgain(tick): the step ticked, the card written)
""" + lift(TOOLS, 'FLASHMEM bool RfHomeBack()') + r"""
static void RotorFlightStart() { homeNotReadAtMenu = RfHomeNotRead; RfLeaveAfterSave = false; if (menuShut) { if (menuSaysWhy) MsgBox((char *) "page RXSetupView", "The motor is ON.\r\nSwitch it off first."); return; } if (RfHomeBack()) return; ++rfStarts; CurrentView = ROTORFLIGHTVIEW; }   // (RF_RotorFlight.h RotorFlightStart: its refusal, then RfHomeBack, then the menu)
"""
prog = prog.replace(old, new)
j = prog.index("int main()", prog.index("static int checks = 0, fails = 0;"))
prog = prog[:j] + main[main.index('static std::string busyNow'):]
d = tempfile.mkdtemp(); atexit.register(shutil.rmtree, d, True)
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-const-variable', '-g', '-fsanitize=address,undefined', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:8000]); sys.exit('exp_quiet_road: DID NOT COMPILE')
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
