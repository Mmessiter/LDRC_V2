#!/usr/bin/env python3
"""Host test of B179 (5 Nov 2026): the file link stays shut while the pilot is on a page.

Malcolm, on the Rotorflight Governor page, 52 s after power-on: "I just saw it jump again to the front screen". The log said why:
the screen knocked for the file link (LDRCLINK), LinkMode() opened it (no model was connected), and the link's end draws the
front page afresh. Now LinkRefusal() (FlightGuard.h) answers a knock with LE_PAGE_OPEN unless the pilot is on the front page,
its screen saver, or Transmitter setup (where Check for update is - the one link asked for by hand). The real LinkRefusal() and
LinkPageAllows() are compiled on the Mac over fakes of the rest, with the real link library for the codes and their words.
Then checks on the source text: LinkMode.h logs a refused knock; a bank change on the curves page saves the edits first.
   python3 dev/test_linkpage/test_linkpage.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, 'TransmitterCode')
LIB = os.path.join(TC, 'lib', 'LdrcLink')
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()

def lift(text, head):
    """The function whose first line starts with `head` (column 0, Allman style): from there to the next line that is just '}'."""
    lines = text.split('\n')
    for i, l in enumerate(lines):
        if l.startswith(head) and not l.split('//')[0].rstrip().endswith(';'):
            for j in range(i + 1, len(lines)):
                if lines[j] == '}':
                    return '\n'.join(lines[i:j + 1]) + '\n'
            break
    raise SystemExit('cannot lift ' + head)

FG = src('include/FlightGuard.h')
PROGRAM = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
#include "LdrcLink.h"
#define FRONTVIEW 0
#define GRAPHVIEW 2
#define MODELSVIEW 5
#define TXSETUPVIEW 7
#define LOGVIEW 23
#define BLANKVIEW 39
#define NORMAL 0
#define CALIBRATELIMITS 3
static bool BoundFlag = false, ModelMatched = false, ModalWaits = false, ModelWasSeen = false, MotorEnabled = false;
static uint8_t CurrentMode = NORMAL, CurrentView = FRONTVIEW, SafetySwitch = 0;
static bool SafetyON = true;
static int contacts = 0;
static void NoteModelContact() { ++contacts; }
static bool ModelJustNow() { return ModelWasSeen && !(BoundFlag && ModelMatched); }
static bool SafetyIsDefined() { return SafetySwitch != 0; }
static bool SafetyIsOff() { return SafetyIsDefined() && !SafetyON; }
static bool RadiosMustBeOff() { return SafetyIsDefined() ? SafetyIsOff() : MotorEnabled; }
bool LinkPageAllows();
''' + lift(FG, 'uint8_t LinkRefusal()') + lift(FG, 'bool LinkPageAllows()') + r'''
static int checks = 0, fails = 0;
#define CHECK(c, what) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, what); } } while (0)
static void reset() { BoundFlag = ModelMatched = ModalWaits = ModelWasSeen = MotorEnabled = false; CurrentMode = NORMAL; CurrentView = FRONTVIEW; SafetySwitch = 0; SafetyON = true; }
int main() {
    // the pages that let the link open
    reset(); CHECK(LinkRefusal() == ldrc::LE_OK, "the front page: the link opens");
    reset(); CurrentView = TXSETUPVIEW; CHECK(LinkRefusal() == ldrc::LE_OK, "Transmitter setup (Check for update lives there): the link opens");
    reset(); CurrentView = BLANKVIEW; CHECK(LinkRefusal() == ldrc::LE_OK, "the screen saver: the link opens (it wakes to the front page anyway)");
    reset(); CurrentView = 254; CHECK(LinkRefusal() == ldrc::LE_OK, "no page yet (254): the link opens");
    // every other page keeps it shut
    const uint8_t pages[] = { GRAPHVIEW, MODELSVIEW, LOGVIEW, 45, 60, 83 };
    for (uint8_t p : pages) { reset(); CurrentView = p; CHECK(LinkRefusal() == ldrc::LE_PAGE_OPEN, "a page is open: the link stays shut"); }
    CHECK(contacts == 10, "every knock notes the model contact first");
    // flying comes first, in the old order, whatever the page
    reset(); CurrentView = GRAPHVIEW; BoundFlag = ModelMatched = true; CHECK(LinkRefusal() == ldrc::LE_BUSY, "a model connected: its reason, not the page's");
    reset(); CurrentView = GRAPHVIEW; ModelWasSeen = true; CHECK(LinkRefusal() == ldrc::LE_MODEL_JUST_NOW, "a model a moment ago: its reason first");
    reset(); CurrentView = GRAPHVIEW; MotorEnabled = true; CHECK(LinkRefusal() == ldrc::LE_MOTOR_ON, "the motor on (no safety switch): its reason first");
    reset(); CurrentView = GRAPHVIEW; SafetySwitch = 3; SafetyON = false; CHECK(LinkRefusal() == ldrc::LE_SAFETY_OFF, "the safety off: its reason first");
    reset(); CurrentView = GRAPHVIEW; ModalWaits = true; CHECK(LinkRefusal() == ldrc::LE_NOT_NOW, "a question on screen: its reason first");
    reset(); CurrentMode = CALIBRATELIMITS; CHECK(LinkRefusal() == ldrc::LE_NOT_NOW, "calibrating on the front page: not now");
    reset(); BoundFlag = ModelMatched = true; CHECK(LinkRefusal() == ldrc::LE_BUSY, "a model connected on the front page: busy, as before");
    // the words the screen will show
    const char *t = ldrc::errorText(ldrc::LE_PAGE_OPEN);
    CHECK(strstr(t, "page is open") && strstr(t, "front page"), "the refusal says a page is open, and where to go");
    CHECK(ldrc::LE_PAGE_OPEN == 18 && strcmp(ldrc::errorText(ldrc::LE_MODEL_JUST_NOW), "a model was connected less than a minute ago") == 0, "the codes before it are untouched");
    printf("%d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''

def main():
    fails = 0
    with tempfile.TemporaryDirectory() as d:
        cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(PROGRAM)
        exe = os.path.join(d, 't')
        r = subprocess.run(['c++', '-std=c++17', '-fsanitize=address,undefined', '-g', '-I', LIB, cpp, os.path.join(LIB, 'LdrcLink.cpp'), '-o', exe], capture_output=True, text=True)
        if r.returncode:
            print(r.stderr); raise SystemExit('compile failed')
        r = subprocess.run([exe], capture_output=True, text=True)
        sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
        if r.returncode: fails += 1
    # the source text: what the lifted code cannot show
    checks = 0
    def check(cond, what):
        nonlocal checks, fails
        checks += 1
        if not cond: fails += 1; print('FAIL: ' + what)
    lm = src('include/LinkMode.h')
    refused = lm[lm.index('if (refusal != ldrc::LE_OK)'):lm.index('BlueLedOn();')]
    check('LogLinkRefused(ldrc::errorText(refusal))' in refused and refused.index('LinkSend(reply)') < refused.index('LogLinkRefused'), 'LinkMode.h: a refused knock is answered first, then logged with its reason')
    lf = src('include/LogFiles.h')
    check('FLASHMEM void LogLinkRefused(const char *why)' in lf and '"Link knock refused (page %u): %s B179"' in lf, 'LogFiles.h: the line names the page and the reason')
    sw = src('include/Switches.h')
    bank = sw[sw.index('void BankHasChanged()'):]
    graph = bank[bank.index('if (CurrentView == GRAPHVIEW)'):bank.index('if (CurrentView == SLOWSERVOVIEW)')]
    check('if (!(BoundFlag && ModelMatched))' in graph and 'SaveOneModel(ModelNumber);' in graph and graph.index('SaveOneModel') < graph.index('DisplayCurveAndServoPos'),
          'Switches.h: a bank change on the curves page saves the edits first (not with a model connected), then draws the new bank')
    defs = src('include/1Definitions.h')
    check('bool LinkPageAllows();' in defs and 'void LogLinkRefused(const char *why);' in defs, '1Definitions.h: both prototypes')
    import re as _re; _v = _re.search(r'#define TXVERSION_EXTRA "B(\d+) ', defs)
    check(_v is not None and int(_v.group(1)) >= 179, 'the version is B179 or later')
    screen = os.path.expanduser('~/Documents/GitHub/ESP32-board2/board4/nextion-emulator/lib/LdrcLink')
    if os.path.isdir(screen):
        for f in ('LdrcLink.h', 'LdrcLink.cpp'):
            check(open(os.path.join(LIB, f), 'rb').read() == open(os.path.join(screen, f), 'rb').read(), "the screen's copy of the link library is the Teensy's, byte for byte: " + f)
    print('%d source checks, %d failures' % (checks, fails))
    return fails

if __name__ == '__main__':
    sys.exit(1 if main() else 0)
