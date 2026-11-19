#!/usr/bin/env python3
"""HELP AND THE SCREEN SAVER DO NOT COME OVER A ROTORFLIGHT PAGE THAT IS READING OR SAVING (B211, the sixteenth review; released code had it).
Each of these pages' polls ends its job when its page goes: Help (or the screen saver) over a running save cut it in its middle - part written,
nothing stored, nothing said - and over a read left the page dead on the way back (the last visit's numbers, Save and the arrows dead).
The REAL RfPageJobRuns and HelpWordCame (main.cpp) and HideScreenAgain (Utilities.h) run here; the pages' steps are this test's hand."""
import os, re, subprocess, sys, tempfile, shutil, atexit
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, 'TransmitterCode')
def src(n): return open(os.path.join(TC, n), encoding='utf-8').read()
def lift(text, head):
    i = text.index(head); j = text.index('{', i); d = 0
    for k in range(j, len(text)):
        if text[k] == '{': d += 1
        elif text[k] == '}':
            d -= 1
            if d == 0: return text[i:k + 1] + '\n'
    raise SystemExit('no end: ' + head)
D1 = src('include/1Definitions.h'); MAINC = src('src/main.cpp'); UT = src('include/Utilities.h')
def steps(header, first):   # a page's own list of steps, as its header has it (their ORDER is what RfPageJobRuns leans on)
    t = re.sub(r'//[^\n]*', '', src('include/' + header)); i = t.index(first); a = t.rfind('enum', 0, i); return t[a:t.index('}', i) + 1] + ';\n'
STEPS = ''.join(steps(h, f) for h, f in (('RF_Basics.h', 'BAS_IDLE'), ('RF_Filters.h', 'FLT_IDLE'), ('RF_Travel.h', 'TRV_IDLE'), ('RF_Rescue.h', 'RSC_IDLE'), ('RF_Servos.h', 'SRV_IDLE'),
                                          ('RF_FcSetup.h', 'BAT_IDLE'), ('RF_FcSetup.h', 'BB_IDLE'), ('RF_FcSetup.h', 'CAL_IDLE'), ('RF_Beeper.h', 'BP_IDLE'), ('RF_Switches.h', 'SW_IDLE'),
                                          ('RF_Adjust.h', 'ADJ_IDLE'), ('RF_Easy.h', 'EZ_IDLE')))
VIEWS = ('BASICSVIEW', 'BASICS2VIEW', 'PORTSVIEW', 'ESCCALVIEW', 'FILTERVIEW', 'FILTER2VIEW', 'TRAVELVIEW', 'TRAVEL2VIEW', 'TRAVEL3VIEW', 'TRAVEL4VIEW', 'RESCUEVIEW', 'RESCUE2VIEW', 'SERVOVIEW',
         'BATTERYVIEW', 'BATSENSORSVIEW', 'BLACKBOXVIEW', 'LEVELVIEW', 'BEEPERVIEW', 'ADJUSTVIEW', 'EASYVIEW',
         'RXSETUPVIEW1', 'HELP_VIEW', 'BLANKVIEW', 'SCANVIEW', 'GRAPHVIEW', 'COLOURS_VIEW', 'AUDIOVIEW', 'PONGVIEW', 'CALIBRATEVIEW', 'FRONTVIEW', 'ROTORFLIGHTVIEW')
prog = r'''
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
#define FLASHMEM
#define WHAHWHAHMSG 1
''' + '\n'.join(re.search(r'^#define %s[ \t]+\d+' % v, D1, re.M).group(0) for v in VIEWS) + r'''
''' + STEPS + r'''static int BasStep = 0, FltStep = 0, TravStep = 0, RescueStep = 0, ServoStep = 0;   // (each page's own step, its poll's: 0 = nothing runs)
static int BatStep = 0, BbStep = 0, CalStep = 0, BpStep = 0, SwStep = 0, AdjStep_ = 0, EzStep = 0;   // (the seventeenth review: the other pages whose poll ends its job with its page)
static bool RfSaveHoldsBank() { return false; }   // (B211, e101b: main.cpp's Help tap asks it - RF_Verify.h; dev/test_verify runs the real one)
static uint8_t CurrentView = FRONTVIEW, SavedCurrentView = 0; static bool HelpTookRead = false, ScreenIsOff = false;
static bool Reading_PIDS_Now = false, Reading_RATES_Now = false, Reading_RATES_Advanced_Now = false, Reading_PIDS_Advanced_Now = false, Reading_GOV_Now = false, Reading_GOV_Config_Now = false;
static char TextIn[200];
static int sounds = 0, helps = 0, readsOptions = 0; static std::vector<std::string> cmds;
static void PlaySound(int) { ++sounds; } static void SendHelp() { ++helps; } static void ReadRXOptionsView() { ++readsOptions; }
static bool HelpNameFrom(char *name) { strcpy(name, "RESCUE"); return true; }
static void SendCommand(char *c) { cmds.push_back(c); } static void DelayWithDog(int) {} static void SaveOrRestoreScreen(bool) {}
static bool vfPending = false; static bool RfVerifyPending() { return vfPending; }   // (e99e, 18 Nov 2026: HideScreenAgain also waits for a save's read-back - RF_Verify.h)
''' + lift(MAINC, 'bool RfPageWatchRuns()') + lift(MAINC, 'bool RfPageJobRuns()') + lift(MAINC, 'FLASHMEM void HelpWordCame()') + lift(UT, 'void HideScreenAgain()') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
struct P { uint8_t view; int *step; const char *name; };
int main()
{
    const P pages[] = { { BASICSVIEW, &BasStep, "Basics 1" }, { BASICS2VIEW, &BasStep, "Basics 2" }, { PORTSVIEW, &BasStep, "Ports" }, { FILTERVIEW, &FltStep, "Filters 1" }, { FILTER2VIEW, &FltStep, "Filters 2" },
                        { TRAVELVIEW, &TravStep, "Travel 1" }, { TRAVEL2VIEW, &TravStep, "Travel 2" }, { TRAVEL3VIEW, &TravStep, "Travel 3" }, { TRAVEL4VIEW, &TravStep, "Travel 4" },
                        { RESCUEVIEW, &RescueStep, "Rescue 1" }, { RESCUE2VIEW, &RescueStep, "Rescue 2" }, { SERVOVIEW, &ServoStep, "Servos" } };
    int *const all[] = { &BasStep, &FltStep, &TravStep, &RescueStep, &ServoStep, &BatStep, &BbStep, &CalStep, &BpStep, &SwStep, &AdjStep_, &EzStep };
    for (const P &p : pages)
    {
        // 1. the page's own job, and no other page's, says "a job runs"
        for (int *s : all) *s = 0;
        CurrentView = p.view; CHECK(!RfPageJobRuns());
        for (int *s : all) if (s != p.step) *s = 3;
        CHECK(!RfPageJobRuns());                                                // (the other pages' steps - left over, or not: not this page's business)
        *p.step = 1; CHECK(RfPageJobRuns()); *p.step = 7; CHECK(RfPageJobRuns());
        // 2. HELP: a sound, the page goes on as it was - nothing opens, nothing is noted; with the job over it opens as ever
        for (int *s : all) *s = 0; *p.step = 2;
        sounds = helps = 0; SavedCurrentView = 0; strcpy(TextIn, "HelpView:RESCUE"); HelpWordCame();
        CHECK(sounds == 1 && helps == 0 && CurrentView == p.view && SavedCurrentView == 0);
        *p.step = 0; sounds = 0; HelpWordCame();
        CHECK(sounds == 0 && helps == 1 && CurrentView == HELP_VIEW && SavedCurrentView == p.view);
        // 3. THE SCREEN SAVER: not now - it comes when the job is over (CheckScreenTime asks again every pass)
        CurrentView = p.view; *p.step = 4; cmds.clear(); ScreenIsOff = false; HideScreenAgain();
        CHECK(cmds.empty() && CurrentView == p.view && !ScreenIsOff);
        *p.step = 0; HideScreenAgain();
        CHECK(cmds.size() == 2 && cmds[0] == "page BlankView" && CurrentView == BLANKVIEW && ScreenIsOff);
    }
    // 4. no other page is held: the front page, the menu, the ESC calibration page - whatever the five steps say
    for (int *s : all) *s = 5;
    for (uint8_t v : { (uint8_t) FRONTVIEW, (uint8_t) ROTORFLIGHTVIEW, (uint8_t) ESCCALVIEW, (uint8_t) HELP_VIEW, (uint8_t) BLANKVIEW }) { CurrentView = v; CHECK(!RfPageJobRuns()); }
    CurrentView = FRONTVIEW; helps = 0; HelpWordCame(); CHECK(helps == 1 && CurrentView == HELP_VIEW);
    // 5. (the seventeenth review) THE OTHER PAGES WHOSE POLL ENDS ITS JOB WITH ITS PAGE: their SAVES are held (and what follows a save: its store, its
    //    read-back, a restart) - their reads and their live readings are not
    {
        struct Q { uint8_t view; int *step; int notHeld[4]; int held[4]; const char *name; };
        const Q more[] = {
            { BATTERYVIEW, &BatStep, { BAT_READ, BAT_READ_VM, BAT_READ_CM, 0 }, { BAT_WRITE, BAT_WRITE_CM, BAT_STORE, BAT_VERIFY_CM }, "Battery" },
            { BATSENSORSVIEW, &BatStep, { BAT_READ, BAT_READ_VM, BAT_READ_CM, 0 }, { BAT_WRITE, BAT_WRITE_VM, BAT_STORE, BAT_VERIFY }, "Battery's sensors" },
            { BLACKBOXVIEW, &BbStep, { BB_STATUS, BB_READ, BB_MODES, BB_MEM }, { BB_WRITE, BB_STORE, BB_WAIT, BB_VERIFY }, "Black box" },
            // (the eighteenth review: AN ERASE IS NOT HELD - nothing of it is cut when its page goes, and Help was dead for its two minutes; the restart behind the store IS a step of the save)
            { BLACKBOXVIEW, &BbStep, { BB_ERASE, BB_ERASE_WAIT, BB_ERASE_POLL, 0 }, { BB_REBOOT, BB_WAIT, BB_VERIFY, BB_VERIFY }, "Black box (its erase; its restart)" },
            { LEVELVIEW, &CalStep, { CAL_READ, CAL_ATT, 0, 0 }, { CAL_CAL, CAL_CAL_STORE, CAL_WRITE, CAL_VERIFY }, "Level" },
            { BEEPERVIEW, &BpStep, { BP_READ_NAME, BP_READ, 0, 0 }, { BP_WRITE_NAME, BP_WRITE, BP_STORE, BP_VERIFY }, "Beeper & name" },
            { ADJUSTVIEW, &SwStep, { SW_READ, SW_MAP, 0, 0 }, { SW_WRITE, SW_STORE, SW_VERIFY, SW_VERIFY }, "Switches & knobs (the switches)" },
            { ADJUSTVIEW, &AdjStep_, { ADJ_READ_RATES, ADJ_READ, ADJ_NOW_STATUS, ADJ_NOW_READ }, { ADJ_WRITE, ADJ_STORE, ADJ_VERIFY, ADJ_VERIFY }, "Switches & knobs (the knobs)" },
            { EASYVIEW, &EzStep, { EZ_R_STATUS, EZ_R_GOV, EZ_R_RATES, EZ_R_PID }, { EZ_S_STATUS, EZ_S_PID_STORE, EZ_S_WALK_WRITE, EZ_PUT_BACK }, "Easy tuning" } };
        for (const Q &q : more)
        {
            for (int *s : all) *s = 0;
            CurrentView = q.view; CHECK(!RfPageJobRuns());
            for (int st : q.notHeld) { *q.step = st; if (RfPageJobRuns()) fprintf(stderr, "%s: step %d should not hold Help\n", q.name, st); CHECK(!RfPageJobRuns()); }
            for (int st : q.held)
            {
                *q.step = st; CurrentView = q.view; if (!RfPageJobRuns()) fprintf(stderr, "%s: step %d should hold Help\n", q.name, st); CHECK(RfPageJobRuns());
                sounds = helps = 0; HelpWordCame(); CHECK(sounds == 1 && helps == 0 && CurrentView == q.view);          // Help: a sound, the page goes on
                cmds.clear(); ScreenIsOff = false; HideScreenAgain(); CHECK(cmds.empty() && CurrentView == q.view);        // the screen saver: not now
            }
            *q.step = 0; helps = 0; HelpWordCame(); CHECK(helps == 1 && CurrentView == HELP_VIEW);                         // the save over: Help opens
        }
        for (int *s : all) *s = 0;
    }
    // 6. (the nineteenth review) A JOB THAT IS ONLY WATCHED - the black box's erase. The flight controller erases by itself and nothing of it is cut
    //    when its page goes: HELP IS FREE. But the page's poll ends its watch with its page ("Erased in N s" was never said), and the screen saver
    //    puts another page up with no press: THE SCREEN SAVER WAITS (the real HideScreenAgain). What becomes of the watch behind Help: dev/test_erasewatch.
    for (int *s : all) *s = 0;
    for (int st : { (int) BB_ERASE, (int) BB_ERASE_WAIT, (int) BB_ERASE_POLL })
    {
        CurrentView = BLACKBOXVIEW; BbStep = st; CHECK(!RfPageJobRuns() && RfPageWatchRuns());
        cmds.clear(); ScreenIsOff = false; HideScreenAgain(); CHECK(cmds.empty() && CurrentView == BLACKBOXVIEW && !ScreenIsOff);            // the screen saver: not now
        helps = sounds = 0; strcpy(TextIn, "HelpView:BLACKBOX"); HelpWordCame(); CHECK(helps == 1 && sounds == 0 && CurrentView == HELP_VIEW);   // Help: it opens
        CHECK(!RfPageWatchRuns());                                                                                                          // (on Help's own page nothing is watched)
    }
    for (int st = BB_IDLE; st < BB_ERASE; ++st) { CurrentView = BLACKBOXVIEW; BbStep = st; CHECK(!RfPageWatchRuns()); }                    // no other step of the page is "watched"
    BbStep = BB_ERASE_POLL; for (uint8_t v : { (uint8_t) FRONTVIEW, (uint8_t) ROTORFLIGHTVIEW, (uint8_t) HELP_VIEW, (uint8_t) BLANKVIEW }) { CurrentView = v; CHECK(!RfPageWatchRuns()); }   // nor any other page, whatever the step says
    BbStep = BB_IDLE; CurrentView = BLACKBOXVIEW; cmds.clear(); ScreenIsOff = false; HideScreenAgain(); CHECK(cmds.size() == 2 && CurrentView == BLANKVIEW && ScreenIsOff);   // the erase over: the screen saver comes
    // 7. (e99e) A SAVE'S READ-BACK PENDING: the screen saver waits for it too; when it is over, the screen saver comes
    BbStep = BB_IDLE; CurrentView = ROTORFLIGHTVIEW; vfPending = true; cmds.clear(); ScreenIsOff = false; HideScreenAgain(); CHECK(cmds.empty() && CurrentView == ROTORFLIGHTVIEW && !ScreenIsOff);
    vfPending = false; cmds.clear(); ScreenIsOff = false; HideScreenAgain(); CHECK(cmds.size() == 2 && CurrentView == BLANKVIEW && ScreenIsOff);
    for (int *s : all) *s = 0;
    printf("test_pagejob: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); atexit.register(shutil.rmtree, d, True)
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-fsanitize=address,undefined', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:5000]); sys.exit('test_pagejob: DID NOT COMPILE')
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
