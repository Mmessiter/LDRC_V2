#!/usr/bin/env python3
"""Host test of B144, the transmitter's two status lines to the screen: the receiver's ("ldrcrx=", RxUpdate.h, between its
RXLINE-LOGIC markers) and the transmitter's own ("ldrcst=", FlightGuard.h, TELLSCREEN-LOGIC), compiled on the Mac with a
fake port whose free room the test sets, and a fake clock.
Malcolm, 22 Oct 2026, Mehul's RAW 420: "The transmitter did not answer ... older than B11". The receiver's line came just
after the front page's once-a-second burst (a Rotorflight model's ESC box), which left the port nearly full, and the line
was left out every second: the screen's status said its last word was 132 s old. Now a line left out is owed: the next
50 ms tick sends it when it fits, and after 200 ms it goes anyway. Then the wiring: main.cpp ticks it every 50 ms.
   python3 dev/test_rxline/test_rxline.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INC = os.path.join(ROOT, 'TransmitterCode', 'include')
def between(name, begin, end):
    src = open(os.path.join(INC, name)).read()
    m = re.search(r'// ' + begin + r'.*?\n(.*)// ' + end, src, re.S)
    assert m, 'the %s markers were not found in %s' % (begin, name)
    return m.group(1)
rxline = between('RxUpdate.h', 'RXLINE-LOGIC-BEGIN', 'RXLINE-LOGIC-END')
tellscreen = between('FlightGuard.h', 'TELLSCREEN-LOGIC-BEGIN', 'TELLSCREEN-LOGIC-END')

prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
#define CRUMB(x)
#define NORMAL 0
static uint32_t now = 100000;
static uint32_t millis() { return now; }
// the port: the room the test gives it, and what went out (a write with too little room waits for the wire, as Teensy's)
struct Port {
    int room = 63; std::vector<std::string> lines; int waited = 0;
    int availableForWrite() { return room; }
    size_t write(const uint8_t *b, size_t n) { if ((int)n > room) ++waited; std::string s((const char *)b, n); lines.push_back(s.substr(0, s.find('\xFF'))); return n; }
} NEXTION;
// RxUpdate.h's state, as the line reads it
enum { RXUP_IDLE = 0, RXUP_ORDERED = 1, RXUP_QUIET = 2 };
static uint8_t RxUpdPhaseNow = RXUP_IDLE, RxUpdWhyNow = 0, RxUpdOutcomeNow = 0, CurrentMode = NORMAL, ModalWaits = 0;
static uint32_t RxReleaseCode = 0x90387, RxReleaseCodeAtMs = 99000, RxUpdWantedCode = 0, RxUpdPhaseSince = 0, RxUpdQuietMs = 90000;
static bool BoundFlag = true, ModelMatched = true, ReceiverUpdateQuiet = false, SendNoData = false, LedWasGreen = true;
// FlightGuard.h's
static uint8_t Status = 12;
static void NoteModelContact() {}
static uint8_t ScreenStatusNow() { return Status; }
''' + rxline + tellscreen + r'''
static int checks = 0, failures = 0;
#define CHECK(c, what) do { ++checks; if (!(c)) { ++failures; printf("   FAIL: %s\n", what); } } while (0)
static size_t count(const char *head) { size_t k = 0; for (auto &l : NEXTION.lines) if (l.rfind(head, 0) == 0) ++k; return k; }
// ManageTransmitter's rhythm: the once-a-second chores (with the port as the front page's burst leaves it), and the
// 50 ms tick in between (with the port as it is then)
static void second(int roomAtTheSecond, int roomBetween) {
    NEXTION.room = roomAtTheSecond; RxReleaseCodeAtMs = now;
    TellScreen(true); TellScreenRx();
    NEXTION.room = roomBetween;
    for (int t = 0; t < 19; ++t) { now += 50; TellScreen(false); TellScreenRxTick(); }
    now += 50;
}
int main()
{
    printf("- a free port: both lines go at once, each once a second\n");
    for (int s = 0; s < 3; ++s) second(63, 63);
    CHECK(count("ldrcrx=") == 3 && count("ldrcst=") == 3, "three seconds, three of each");
    CHECK(NEXTION.lines[1] == "ldrcrx=0,0,0,90387,0,0,28", "the receiver's line as the screen reads it (0.9.903, model matched, bound, green)");
    CHECK(NEXTION.waited == 0, "nothing waited");
    printf("- THE FIELD CASE: the port nearly full at every second (the front page's burst), free between\n");
    NEXTION.lines.clear();
    for (int s = 0; s < 10; ++s) second(5, 63);
    CHECK(count("ldrcrx=") == 10, "the receiver's line every second all the same (B143: never, for as long as the front page showed)");
    CHECK(count("ldrcst=") == 10, "and the transmitter's own");
    CHECK(NEXTION.waited == 0, "sent at the next tick, when it fits: nothing waited");
    printf("- the port busy for longer: the line goes after 200 ms anyway\n");
    NEXTION.lines.clear();
    NEXTION.room = 5; RxReleaseCodeAtMs = now; TellScreenRx();
    for (int t = 0; t < 3; ++t) { now += 50; TellScreenRxTick(); }
    CHECK(count("ldrcrx=") == 0, "not in the first 150 ms");
    now += 50; TellScreenRxTick();
    CHECK(count("ldrcrx=") == 1 && NEXTION.waited == 1, "at 200 ms, waiting for the wire");
    now += 50; TellScreenRxTick(); CHECK(count("ldrcrx=") == 1, "once");
    printf("- a change of the transmitter's status, the port busy: sent within 200 ms; nothing new: nothing sent\n");
    NEXTION.lines.clear(); NEXTION.waited = 0;
    for (int t = 0; t < 5; ++t) { now += 50; TellScreen(false); }
    CHECK(count("ldrcst=") == 0, "unchanged, not owed: nothing");
    Status = 13; NEXTION.room = 5;
    now += 50; TellScreen(false); CHECK(count("ldrcst=") == 0, "the change waits for room");
    NEXTION.room = 63; now += 50; TellScreen(false); CHECK(count("ldrcst=") == 1 && NEXTION.lines[0] == "ldrcst=13", "and goes when there is");
    Status = 9; NEXTION.room = 5;
    for (int t = 0; t < 4; ++t) { now += 50; TellScreen(false); }
    CHECK(count("ldrcst=") == 1, "seen at the first tick, waiting 150 ms so far");
    now += 50; TellScreen(false);
    CHECK(count("ldrcst=") == 2 && NEXTION.lines[1] == "ldrcst=9" && NEXTION.waited == 1, "a busy port for 200 ms: the change goes anyway");
    printf("- no model, no update, nothing heard: no receiver's line, and none owed\n");
    NEXTION.lines.clear(); NEXTION.room = 63;
    BoundFlag = false; ModelMatched = false; RxReleaseCode = 0;
    TellScreenRx(); CHECK(count("ldrcrx=") == 0, "nothing to say");
    BoundFlag = true; ModelMatched = true; RxReleaseCode = 0x90387;
    now += 50; TellScreenRxTick(); CHECK(count("ldrcrx=") == 0, "and nothing owed from it");
    printf("- an update on its way: the phase and the silence left are in the owed line, as they are when it goes\n");
    NEXTION.lines.clear(); NEXTION.room = 5;
    RxUpdPhaseNow = RXUP_QUIET; RxUpdPhaseSince = now; RxUpdWantedCode = 0x90388; RxReleaseCodeAtMs = now;
    TellScreenRx(); now += 50; NEXTION.room = 63; TellScreenRxTick();
    CHECK(count("ldrcrx=") == 1 && NEXTION.lines[0] == "ldrcrx=2,0,0,90387,90388,90,28", "phase 2, 90 s to go");
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
'''
d = tempfile.mkdtemp()
c = os.path.join(d, 't.cpp'); x = os.path.join(d, 't')
open(c, 'w').write(prog)
r = subprocess.run(['c++', '-std=c++17', '-Wall', '-Wno-unused-function', '-fsanitize=address,undefined', '-o', x, c], capture_output=True, text=True)
if r.returncode:
    print(r.stderr[-3000:]); sys.exit(1)
r = subprocess.run([x], capture_output=True, text=True)
print(r.stdout, end=''); print(r.stderr[-2000:], end='')
bad = r.returncode != 0

# the wiring: the once-a-second chores still say both lines, and the 50 ms tick pays what is owed
main = open(os.path.join(ROOT, 'TransmitterCode', 'src', 'main.cpp')).read()
once = main[main.find('if (RightNow - LastTimeRead >= 1000)'):]
once = once[:once.find('return;                    // That')]
fifty = main[main.find('if (RightNow - TransmitterLastManaged >= 50)'):]
fifty = fifty[:fifty.find('TransmitterLastManaged = millis();')]
wiring = [('TellScreen(true)' in once, 'the once-a-second chores say the status'),
          ('TellScreenRx()' in once, '... and the receiver\'s line'),
          ('TellScreen(false)' in fifty, 'the 50 ms tick says a change, or an owed status'),
          ('TellScreenRxTick()' in fifty, '... and pays an owed receiver\'s line')]
for ok, what in wiring:
    if not ok: print('   FAIL (wiring): ' + what); bad = True
print('wiring: %d checks' % len(wiring))
sys.exit(1 if bad else 0)
