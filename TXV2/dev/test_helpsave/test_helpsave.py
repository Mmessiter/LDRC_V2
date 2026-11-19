#!/usr/bin/env python3
"""Review 17, reviewer B. HELP OVER A RUNNING SAVE ON A PAGE main.cpp RfPageJobRuns DOES NOT NAME. The sixteenth review's finding 4 named Basics,
Filters, Battery and Beeper as pages whose poll ends a save when the page goes; the cure holds Help (and the screen saver) off five pages - Basics,
Filters, Travel, Rescue, Servos. Here: Beeper & name (its poll: `if (CurrentView != BEEPERVIEW) { BpStep = BP_IDLE; ...}`).
The REAL RF_Beeper.h, RF_FcSetup.h, RF_SaveNow.h, main.cpp RfPageJobRuns and HelpWordCame, over dev/test_beeper's harness (dev/test_fcsetup's).
   python3 exp_help_in_save_other_pages.py [tree]"""
import os, re, subprocess, sys, tempfile, shutil, atexit
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (taken into the suite: this file's own tree)
INC = os.path.join(ROOT, 'TransmitterCode', 'include')
def lift(text, head):
    i = text.index(head); j = text.index('{', i); d = 0
    for k in range(j, len(text)):
        if text[k] == '{': d += 1
        elif text[k] == '}':
            d -= 1
            if d == 0: return text[i:k + 1] + '\n'
MAINC = open(os.path.join(ROOT, 'TransmitterCode', 'src', 'main.cpp'), encoding='utf-8').read()
D1 = open(os.path.join(INC, '1Definitions.h'), encoding='utf-8').read()
tb = open(os.path.join(ROOT, 'dev', 'test_beeper', 'test_beeper.py'), encoding='utf-8').read()
# test_beeper's own construction of its program, up to its checks (its lines, run as they stand)
build = tb[:tb.index("static int checks = 0, fails = 0;", tb.index("'RF_Beeper.h')).read()"))]
build = build.replace("ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))", "ROOT = %r" % ROOT)
ns = {}
exec(build + "''')\n", ns)
src = ns['src']
def _steps(header, first):
    t = re.sub(r'//[^\n]*', '', open(os.path.join(ROOT, 'TransmitterCode', 'include', header), encoding='utf-8').read()); i = t.index(first); return t[t.rfind('enum', 0, i):t.index('}', i) + 1] + ';\n'
views = ('BASICSVIEW', 'BASICS2VIEW', 'PORTSVIEW', 'FILTERVIEW', 'FILTER2VIEW', 'TRAVELVIEW', 'TRAVEL2VIEW', 'TRAVEL3VIEW', 'TRAVEL4VIEW', 'RESCUEVIEW', 'RESCUE2VIEW', 'SERVOVIEW', 'RXSETUPVIEW1', 'HELP_VIEW')
defs = ''.join('#ifndef %s\n%s\n#endif\n' % (v, re.search(r'^#define %s[ \t]+\d+' % v, D1, re.M).group(0)) for v in views)
src += defs + r'''
enum { BAS_IDLE = 0, FLT_IDLE = 0, TRV_IDLE = 0, RSC_IDLE = 0, SRV_IDLE = 0 };
static int BasStep = 0, FltStep = 0, TravStep = 0, RescueStep = 0, ServoStep = 0;
// (taken into the suite, the seventeenth review's cure in: RfPageJobRuns names every such page now - the machines this run does not hold, by their own lists)
''' + ''.join(_steps(h, f) for h, f in (('RF_Switches.h', 'SW_IDLE'), ('RF_Adjust.h', 'ADJ_IDLE'), ('RF_Easy.h', 'EZ_IDLE'))) + r'''
#ifndef EASYVIEW
''' + re.search(r'^#define EASYVIEW[ \t]+\d+', D1, re.M).group(0) + r'''
#endif
#ifndef ADJUSTVIEW
''' + re.search(r'^#define ADJUSTVIEW[ \t]+\d+', D1, re.M).group(0) + r'''
#endif
static int SwStep = 0, AdjStep_ = 0, EzStep = 0;
static bool RfSaveHoldsBank() { return false; }   // (B211, e101b: main.cpp's Help tap asks it - RF_Verify.h; dev/test_verify runs the real one)
static uint8_t SavedCurrentView = 0; static bool HelpTookRead = false; static char TextIn[200];
static bool Reading_PIDS_Now = false, Reading_RATES_Now = false, Reading_RATES_Advanced_Now = false, Reading_PIDS_Advanced_Now = false, Reading_GOV_Now = false, Reading_GOV_Config_Now = false;
static int helps = 0; static void SendHelp() { ++helps; } static void ReadRXOptionsView() {} static bool HelpNameFrom(char *n) { strcpy(n, "BEEPER"); return true; }
''' + lift(MAINC, 'bool RfPageJobRuns()') + lift(MAINC, 'FLASHMEM void HelpWordCame()') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void run(int n = 40) { for (int i = 0; i < n; ++i) { BeeperPoll(); now += 50; } }
static int asks(int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; }
int main()
{
    memset(beep, 0, sizeof beep); beep[4] = 3;
    CurrentView = 47; StartBeeperView(); run();
    CHECK(CurrentView == BEEPERVIEW && BpHave);
    fields["tn1"] = "5"; fields["tn0"] = "Goblin RAW"; BeeperWasEdited();          // a new name, another tone
    fcLog.clear(); const int soundsBefore = sounds; SaveBeeper(); run(1);         // Save: the name is written, the beeper's write is on its way
    CHECK(BpStep != BP_IDLE && asks(11) == 1);
    const bool jobSeen = RfPageJobRuns();
    snprintf(TextIn, sizeof TextIn, "HelpView:BEEPER.TXT"); const uint8_t was = (uint8_t) CurrentView; HelpWordCame();   // the page's Help button
    const bool helpOpened = CurrentView == HELP_VIEW;
    run(20);
    printf("Beeper & name: Save, then Help while the save runs: 'a job runs' said %d; Help opened %d; the step now %d (0 = nothing runs)\n   asked of the flight controller: the name (11) x%d, the beeper (185) x%d, THE STORE (250) x%d, the read-back x%d; boxes %d; its name in memory is now '%s' (stored: 'Goblin 700'), tone %d\n",
           (int) jobSeen, (int) helpOpened, BpStep, asks(11), asks(185), asks(250), asks(10) + asks(184), boxes, fcName.c_str(), beep[4]);
    CHECK(!helpOpened);                                                          // (Help does not come over a page that saves)
    CHECK(asks(250) == 1);                                                       // (a save that began is stored)
    CurrentView = was;                                                           // Help's way back: the page as the screen kept it
    run(20);
    printf("   back from Help: the page's line '%s' shown %d; Save shown (edits) %d; nothing said: boxes %d\n", fields["busy"].c_str(), (int)(!cmds.empty() && cmds.back() == "vis busy,1"), (int) Bp_Was_Edited, boxes);
    printf("exp_help_in_save_other_pages: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); atexit.register(shutil.rmtree, d, True)
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(src)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit('exp_help_in_save_other_pages: DID NOT COMPILE')
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
