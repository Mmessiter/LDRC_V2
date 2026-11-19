#!/usr/bin/env python3
"""B211, TAKEN INTO THE SUITE from the nineteenth review (reviewer B's exp_erase_help.py; reviewer A's exp_erase_saver.py found the screen saver's half).
THE WATCH OF A BLACK-BOX ERASE, AND THE PAGES THAT COME OVER IT. An erase is the flight controller's own job: nothing of it is cut when its page
goes, so HELP IS FREE during it (the eighteenth review: it was dead for the erase's two minutes). But the page's poll dropped its watch with its
page: Help's way back brought the page with "Erasing the flight logs: 7 s ..." standing for good, "Erased ..." never said, and Erase pressed again
started the erase again (the nineteenth review). Now (RF_FcSetup.h BlackboxPoll, e98): THE WATCH GOES ON WHEN THE PAGE IS BACK - and the SCREEN
SAVER, which puts another page up with no press, WAITS for it (main.cpp RfPageWatchRuns, Utilities.h HideScreenAgain: dev/test_pagejob holds that
line by a run of the real routine).
The REAL RF_FcSetup.h (over dev/test_beeper's harness), main.cpp RfPageJobRuns, RfPageWatchRuns and HelpWordCame.
   python3 test_erasewatch.py"""
import os, re, subprocess, sys, tempfile, shutil, atexit
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
assert src.count('bool PipeReplyLate() { return false; }') == 1
src = src.replace('bool PipeReplyLate() { return false; }', 'bool PipeReplyLate() { return now - PipeReqSentMs > 9000; }')
assert src.count('    if (holdReplies) return PipeReqId;') == 1
src = src.replace('    if (holdReplies) return PipeReqId;', '    if (holdReplies || (muteFn && fn == muteFn)) return PipeReqId;\n    if (refuseFn && fn == refuseFn) { fcReply(503, "the receiver did not answer"); return PipeReqId; }')
src = src.replace('int MspAsk(uint8_t fn, const uint8_t *data, int len) {', 'static int muteFn = 0, refuseFn = 0;\nint MspAsk(uint8_t fn, const uint8_t *data, int len) {', 1)
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
''' + lift(MAINC, 'bool RfPageWatchRuns()') + lift(MAINC, 'bool RfPageJobRuns()') + lift(MAINC, 'FLASHMEM void HelpWordCame()') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
#include <set>
static int asks(int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; }
// Help's button, pressed: true = Help was REFUSED (the page stays). When it opens, Help's way back puts the page's number back at once - the poll has not
// run in between, so the job goes on: the book is what Help WOULD have done at this step.
static bool helpRefused() { const int was = CurrentView; snprintf(TextIn, sizeof TextIn, "HelpView:X.TXT"); HelpWordCame(); const bool refused = CurrentView == was; CurrentView = was; return refused; }
struct Book { std::set<int> held, free_; int passes = 0, heldMs = 0; };
static Book walk(void (*poll)(), int *step, int most = 4000) {   // a job from where it stands to its end: Help pressed before every pass of the page's own poll
    Book b; int idle = 0;
    while (idle < 3 && b.passes < most) { const int st = *step; if (st) { idle = 0; if (helpRefused()) { b.held.insert(st); b.heldMs += 50; } else b.free_.insert(st); } else ++idle; poll(); now += 50; ++b.passes; }
    return b;
}
static std::string names(const std::set<int> &s, const char *const *n) { std::string t; for (int v : s) { t += (t.empty() ? "" : ", "); t += n[v]; } return t.empty() ? "-" : t; }
static bool is(const std::set<int> &s, std::initializer_list<int> want) { return s == std::set<int>(want); }
static const char *const BATN[] = {"IDLE", "READ", "READ_VM", "READ_CM", "WRITE", "WRITE_VM", "WRITE_CM", "STORE", "VERIFY", "VERIFY_VM", "VERIFY_CM"};
static const char *const BBN[] = {"IDLE", "STATUS", "READ", "MODES", "MEM", "WRITE", "STORE", "REBOOT", "WAIT", "VERIFY", "ERASE", "ERASE_WAIT", "ERASE_POLL"};
static const char *const CALN[] = {"IDLE", "READ", "ATT", "CAL", "CAL_WAIT", "CAL_STORE", "CAL_ATT", "WRITE", "STORE", "VERIFY"};
static const char *const BPN[] = {"IDLE", "READ_NAME", "READ", "WRITE_NAME", "WRITE", "STORE", "VERIFY_NAME", "VERIFY"};
static void fcFresh() {
    memset(bat, 0, sizeof bat); bat[0] = 0x88; bat[1] = 0x13; bat[2] = 6; bat[3] = 1; bat[4] = 1; bat[5] = 0x4A; bat[6] = 1; bat[7] = 0xAE; bat[8] = 1; bat[9] = 0xA4; bat[10] = 1; bat[11] = 0x5E; bat[12] = 1;
    memset(vm, 0, sizeof vm); vm[0] = 1; vm[1] = 7; vm[2] = 10; vm[3] = 1; vm[4] = 110; memset(cm, 0, sizeof cm); cm[0] = 1; cm[1] = 6; cm[2] = 10; cm[3] = 1; cm[4] = 144; cm[5] = 1;
    memset(bb, 0, sizeof bb); bb[0] = 1; bb[1] = 1; bb[2] = 2; bb[3] = 8; memset(mem, 0, sizeof mem); mem[0] = 3; put32(mem, 5, 16u << 20); put32(mem, 9, 4u << 20); memset(modes, 0, sizeof modes);
    memset(trims, 0, sizeof trims); memset(att, 0, sizeof att); memset(beep, 0, sizeof beep); beep[4] = 3;
    rebootLeft = 0; eraseLeft = -1; muteFn = refuseFn = 0; holdReplies = false; fcLog.clear(); boxes = 0; confirmAnswer = true;
}
static bool erasing() { return fields["busy"].find("Erasing") == 0; }
static bool erasedSaid() { return fields["busy"].find("Erased in ") == 0; }
static void looks(int n) { for (int p = 0; p < n; ++p) { BlackboxPoll(); now += 50; } }
// the page opened and read, Erase pressed and confirmed; 'looksToErase' = how many of the page's asks for the memory the flight controller still answers "erasing"
static void beginErase(int looksToErase) { fcFresh(); CurrentView = 47; StartBlackboxView(); walk(BlackboxPoll, &BbStep); fcLog.clear(); BlackboxErase(); eraseLeft = looksToErase; }
int main()
{
    // 1. HELP, 8 s INTO AN ERASE: it opens; five seconds away; back - the watch goes on and ends as ever
    {
        beginErase(30); looks(160); CHECK(BbStep >= BB_ERASE_WAIT && erasing());
        CHECK(!RfPageJobRuns() && RfPageWatchRuns());                                        // not a save: Help is free - but a job is watched: the screen saver waits (test_pagejob)
        const uint8_t was = (uint8_t) CurrentView; const int helps0 = helps; snprintf(TextIn, sizeof TextIn, "HelpView:BLACKBOX.TXT"); HelpWordCame(); CHECK(CurrentView == HELP_VIEW && helps == helps0 + 1);
        const int a70 = asks(70), a72 = asks(72); looks(100);                                // five seconds on Help's page
        CHECK(BbStep == BB_IDLE && asks(70) == a70 && asks(72) == a72);                      // away: nothing is asked (the pipe is the page's that shows)
        CHECK(!RfPageJobRuns() && !RfPageWatchRuns());                                       // (Help's own page: nothing of this page's holds anything there)
        CurrentView = was;                                                                   // Help's way back: the page as the screen kept it - "Erasing ...: 7 s" still on it
        CHECK(erasing());
        looks(2); CHECK(BbStep >= BB_ERASE_WAIT && asks(70) == a70 + 1);                     // the watch is taken up at once: asked again
        int said = 0, saidAt = -1; for (int p = 0; p < 3600 && !said; ++p) { BlackboxPoll(); now += 50; if (erasedSaid()) { said = 1; saidAt = p; } }
        CHECK(said == 1 && BbStep == BB_IDLE && asks(72) == a72);                            // "Erased in N s: ready to record." - and the erase was never asked for again
        unsigned secs = 0; sscanf(fields["busy"].c_str(), "Erased in %u s", &secs); CHECK(secs >= 13 && secs <= 120);   // counted from the button, the seconds on Help's page among them
        printf("1. Help 8 s into an erase, 5 s away: back on the page the watch went on - '%s' (%d looks later)\n", fields["busy"].c_str(), saidAt);
        looks(120); CHECK(!erasing() && BbStep == BB_IDLE);                                  // the line goes after its five seconds; nothing is left watching
        // ... and Erase pressed after that is a new erase, as it should be
        const int e0 = asks(72); BlackboxErase(); CHECK(asks(72) == e0 + 1);
    }
    // 2. HELP BEFORE THE FLIGHT CONTROLLER HAS ANSWERED THE ERASE ITSELF (the step "ERASE"): the watch has its start all the same (counted from the button)
    {
        beginErase(6); CHECK(BbStep == BB_ERASE);
        const uint8_t was = (uint8_t) CurrentView; snprintf(TextIn, sizeof TextIn, "HelpView:BLACKBOX.TXT"); HelpWordCame(); CHECK(CurrentView == HELP_VIEW);
        looks(60); CHECK(BbStep == BB_IDLE);
        CurrentView = was; int said = 0; for (int p = 0; p < 3600 && !said; ++p) { BlackboxPoll(); now += 50; said = erasedSaid(); }
        unsigned secs = 999; sscanf(fields["busy"].c_str(), "Erased in %u s", &secs); CHECK(said && secs >= 3 && secs <= 60 && asks(72) == 1);
        printf("2. Help before the erase was answered: '%s'\n", fields["busy"].c_str());
    }
    // 3. THE ERASE ENDS WHILE HELP IS UP: back on the page, the first ask says so
    {
        beginErase(30); looks(160); const uint8_t was = (uint8_t) CurrentView; snprintf(TextIn, sizeof TextIn, "HelpView:BLACKBOX.TXT"); HelpWordCame();
        looks(400); eraseLeft = 0;                                                           // twenty seconds on Help's page; the flight controller has finished meanwhile
        CurrentView = was; looks(4); CHECK(erasedSaid() && BbStep == BB_IDLE);
        printf("3. the erase ended while Help was up: '%s'\n", fields["busy"].c_str());
    }
    // 4. HELP UP FOR LONGER THAN THE TWO MINUTES, THE ERASE STILL RUNNING: back on the page it is said (once), and the watch ends
    {
        beginErase(100000); looks(160); const uint8_t was = (uint8_t) CurrentView; snprintf(TextIn, sizeof TextIn, "HelpView:BLACKBOX.TXT"); HelpWordCame();
        looks(2600);                                                                         // 130 s away
        CurrentView = was; looks(4); CHECK(fields["busy"].find("Still not erased after 2 minutes") == 0 && BbStep == BB_IDLE && sounds >= 1);
        printf("4. Help up for 130 s, the erase not done: '%s'\n", fields["busy"].c_str());
    }
    // 5. THE PAGE REALLY LEFT DURING AN ERASE (the motor switch's front page), AND OPENED AGAIN FROM THE MENU: a fresh visit - no watch is taken up, the page reads anew
    {
        beginErase(100000); looks(160); CurrentView = 0; looks(40); CHECK(BbStep == BB_IDLE);
        CurrentView = 47; const int a70 = asks(70); StartBlackboxView(); CHECK(BbStep == BB_STATUS && fields["busy"].find("Reading") == 0);
        walk(BlackboxPoll, &BbStep); CHECK(BbStep == BB_IDLE && !erasing() && asks(70) == a70 + 1 && asks(72) == 1);   // its read asks for the memory once, as ever - and nothing goes on asking
        looks(200); CHECK(BbStep == BB_IDLE && asks(70) == a70 + 1);
        printf("5. the page left for good during an erase and opened again: a fresh read, no watch (the line '%s')\n", fields["busy"].c_str());
    }
    // 6. A PAGE THAT WAS NEVER ERASING takes up no watch from a visit to Help
    {
        fcFresh(); CurrentView = 47; StartBlackboxView(); walk(BlackboxPoll, &BbStep); const int a70 = asks(70);
        const uint8_t was = (uint8_t) CurrentView; snprintf(TextIn, sizeof TextIn, "HelpView:BLACKBOX.TXT"); HelpWordCame(); looks(40); CurrentView = was; looks(200);
        CHECK(BbStep == BB_IDLE && asks(70) == a70 && asks(72) == 0);
    }
    // 7. A SAVE IS STILL HELD (Help refused, a sound), an erase is not
    {
        fcFresh(); CurrentView = 47; StartBlackboxView(); walk(BlackboxPoll, &BbStep);
        BbStep = BB_WRITE; CHECK(RfPageJobRuns() && !RfPageWatchRuns()); CHECK(helpRefused());
        BbStep = BB_ERASE_POLL; CHECK(!RfPageJobRuns() && RfPageWatchRuns()); CHECK(!helpRefused());
        BbStep = BB_IDLE; CHECK(!RfPageJobRuns() && !RfPageWatchRuns());
    }
    // 8. HELP DURING THE PAGE'S OWN READ (a read is not held): the read is let go, as ever - and NO erase's watch is taken up on the way back
    for (int look = 0; look < 6; ++look)
    {
        fcFresh(); CurrentView = 47; StartBlackboxView(); looks(look); if (BbStep == BB_IDLE) break;   // (at each step of the read: STATUS, READ, MODES, MEM)
        CHECK(BbStep >= BB_STATUS && BbStep <= BB_MEM);
        const uint8_t was = (uint8_t) CurrentView; snprintf(TextIn, sizeof TextIn, "HelpView:BLACKBOX.TXT"); HelpWordCame(); CHECK(CurrentView == HELP_VIEW);
        looks(40); const int a70 = asks(70); CurrentView = was; looks(200);
        CHECK(BbStep == BB_IDLE && asks(70) == a70 && asks(72) == 0 && !erasing() && !erasedSaid() && fields["busy"].find("Still not erased") != 0);
    }
    printf("test_erasewatch: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); atexit.register(shutil.rmtree, d, True)
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(src)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit('test_erasewatch: DID NOT COMPILE')
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
