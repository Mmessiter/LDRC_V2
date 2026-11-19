#!/usr/bin/env python3
"""Reviewer A (16): THE DOORS OF OK ON THE SUB-TRIM PAGE, AT RANDOM - what the long storms do not reach with their book open (they serve an OK "past the two
seconds, the last click not said done" some 7 times in 20000 trials, never with I5 asked): a putting-right on its way, the screen standing still for 0.3 to 6 s
from a random moment, waking with or without a touch in front of its queued commands, OK pressed one to four times at random moments; the page back from Help
with one or both of its markers lost, a touch, OK.
 D5. WHAT OK SAVES IS WHAT THE PAGE SHOWED AT THE PRESS THAT WAS OBEYED - every press its own picture, served in their order (no page comes up in between that
     could throw one away; the presses let go under the marker's rule are counted off by the board's own count).
     usage: scene_subtrim_door_storm.py [TXV1B root] [--n trials] [--seed first]"""
import os, sys
ROOT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (taken into the suite: this file's own tree; another root - a copy with a rule taken out - as the first word)
sys.path.insert(0, os.path.join(ROOT, 'dev', 'test_wholepage'))
os.environ['LDRC_RUNS_ONLY'] = '1'
import lib
import scene_subtrim as base
os.environ.pop('LDRC_RUNS_ONLY', None)   # (it was set above for that one import only: the base scene's own text checks are its own business)
EXTRA = base.EXTRA + r'''
#include <map>
static uint32_t xs = 1; static uint32_t xr(uint32_t k) { xs = xs * 1664525u + 1013904223u; return k ? (xs >> 8) % k : 0; }
struct Pic { long shown[16]; uint64_t at; };
static std::map<int, Pic> pics; static int okTag = 0; static long oddServe = 0; static long oksServed = 0, oksLeft = 0, oksStayed = 0, d5Bad = 0, d5Looked = 0, late9 = 0, again9 = 0, letGo9 = 0; static std::string d5First; static std::deque<std::string> trail;
static void note(const char *f, ...) { char b[200]; va_list a; va_start(a, f); vsnprintf(b, sizeof b, f, a); va_end(a); char t[240]; snprintf(t, sizeof t, "%9.3f s  %s", nowUs / 1e6, b); trail.push_back(t); if (trail.size() > 60) trail.pop_front(); }
static int stale0 = 0; static uint16_t let0 = 0;
static void doorTap(const char *button)
{
    if (!strcmp(button, "ok"))
    {   // EVERY PRESS OF OK SAYS WHICH ONE IT IS (the code's top byte - main.cpp's ScreenEventArg; the page's own OK says 0 there): the book knows exactly which press the board obeys
        if (screen.page != "SubTrimView") return;
        Pic p; for (int c = 0; c < 16; ++c) p.shown[c] = shown(c + 1); p.at = screen.at; okTag = okTag % 250 + 1; pics[okTag] = p; P().buttons["ok"] = { 149, 0, 0, (uint8_t) okTag };
        note("OK is pressed (press %d; the page shows %ld on channel 1)", okTag, p.shown[0]); return;
    }
    stTap(button); note("touch %s: channel 1 shows %d", button, shown(1));
}
static void doorOk(int n)
{
    if (n != 21) return;
    ++oksServed;
    const int tag = (uint8_t) TextIn[3];
    if (CurrentView != SUBTRIMVIEW || !pics.count(tag)) { ++oddServe; return; }
    const Pic p = pics[tag]; pics.erase(tag);                                       // THIS press
    const bool due0 = SubTrimSettleDue; const uint32_t since0 = (uint32_t) (millis() - SubTrimAskedMs);
    const bool late = SubTrimSaysDone && SubTrimDone != SubTrimAsked && !SubTrimSettleDue && PendingDropped == SubTrimDropsSeen && (uint32_t) (millis() - SubTrimAskedMs) >= SUBTRIM_DONE_WAIT_MS; const uint8_t a0 = SubTrimAskedAgain;
    EndSubTrimView();
    if (late) { ++late9; if (SubTrimAskedAgain > a0) ++again9; }
    note("   (served with: a writing-out owed %d, said done %d of %d, %u ms since the last click, late %d)", (int) due0, (int) SubTrimDone, (int) SubTrimAsked, (unsigned) since0, (int) late);
    if (CurrentView == SUBTRIMVIEW) { ++oksStayed; note("OK %d served: the page STAYS", tag); return; }
    ++oksLeft; ++d5Looked; note("OK %d served: the model saved, the page left", tag);
    for (int c = 0; c < 16; ++c) if (p.shown[c] != (long) SubTrims[c] - 127) { ++d5Bad; if (d5First.empty()) { char t[200]; snprintf(t, sizeof t, "OK saved %d on channel %d - the page showed %ld there when that OK was pressed", (int) SubTrims[c] - 127, c + 1, p.shown[c]); d5First = t; } break; }
}
static int loseMarks = 0;                                                           // 1: the second marker of the next "page SubTrimView" is lost; 2: both
static bool doorCmd(const char *c)
{
    if (loseMarks == 1 && !strcmp(c, "page SubTrimView")) screen.sysMute.insert("ldrcsync");
    return stCmd(c);
}
static void doorLoop(uint32_t ms) { const uint64_t until = nowUs + (uint64_t) ms * 1000; while (nowUs < until) { LoopPass(); SubTrimPoll(); nowUs += 300 + xr(700); } }
'''
SCENES = r'''
    const int N = argc > 2 ? atoi(argv[2]) : 2000; const uint32_t seed0 = argc > 3 ? (uint32_t) atoi(argv[3]) : 500; int shownBad = 0; long kinds[4] = { 0, 0, 0, 0 }, unserved = 0;
    for (int trial = 0; trial < N; ++trial)
    {
        const uint32_t sd = seed0 + trial; xs = sd * 2654435761u + 12345u;
        more(); addSubTrim(); P().buttons["ok"] = { 149, 0, 0, 0 }; screen.pages0 = screen.pages; extra7 = doorOk; pageNew = true; pics.clear(); trail.clear(); d5First.clear(); const long bad0 = d5Bad;
        const uint32_t lates[] = { 1500, 20000, 60000, 150000, 300000 }; screen.latencyUs = lates[xr(5)];
        for (int i = 0; i < 16; ++i) SubTrims[i] = (uint8_t) (127 + (xr(3) ? 0 : (int) xr(201) - 100));
        openSubTrim(); tapScript = doorTap; cmdScript = doorCmd; doorLoop(screen.latencyUs / 1000 + 400);
        const int kind = xr(4); ++kinds[kind];
        // (the pretend screen sees no touch while its loop stands still - a real one neither: so the touch is made first, the loop goes on for a moment
        //  - the board's putting-right goes out, and may or may not have been read - and THEN the screen stands still)
        if (kind == 0)
        {   // a touch never heard, then one refused: its putting-right on its way
            tapAt(5, "plus!"); doorLoop(130 + xr(200)); tapAt(2, xr(2) ? "plus" : "minus"); doorLoop(3 + xr(screen.latencyUs / 1000 + 60));
        }
        else if (kind == 1)
        {   // another model read under the page, a touch before the page has said it done: not taken, its putting-right on its way
            for (int i = 0; i < 16; ++i) SubTrims[i] = (uint8_t) (127 + (xr(3) ? 0 : (int) xr(201) - 100));
            freshOut(); const uint32_t t = 1 + xr(30); tapAt(t, xr(2) ? "plus" : "minus"); doorLoop(t + 2 + xr(screen.latencyUs / 1000 + 60));
        }
        else
        {   // Help and its way back with the page's markers lost on the wire (kind 2: the second; kind 3: both), then a touch
            CurrentView = LOGVIEW; SendCommand((char *) "page LogView"); doorLoop(screen.latencyUs / 1000 + 300 + xr(300));
            loseMarks = kind == 2 ? 1 : 2; if (loseMarks == 2) screen.sysMute.insert("ldrcsync");
            SendCommand((char *) "page SubTrimView"); CurrentView = SUBTRIMVIEW; pageBack(); pics.clear();
            doorLoop(screen.latencyUs / 1000 + 200 + xr(300)); loseMarks = 0; screen.sysMute.clear();
            uint32_t t = 5 + xr(400); tapAt(t, xr(2) ? "plus" : "minus"); if (xr(2)) { t += 110 + xr(300); tapAt(t, "plus"); }
            doorLoop(t + 2 + xr(screen.latencyUs / 1000 + 60));
        }
        uint32_t stallMs = 0, wake = 0, at = 1 + xr(600);
        if (xr(4))
        {   // THE SCREEN STANDS STILL from now, for 0.3 to 6 s; two times in three it wakes with the rest of its loop's pass in front of its serial job
            // (what a finger does then is printed BEFORE the queued commands are read) - and the first OK is pressed in that round, or just behind it
            stallMs = 300 + xr(5700); wake = xr(3) ? 3000 + xr(40000) : 0;
            screen.stall(nowUs, stallMs, false, wake);
            at = stallMs + (wake ? 1 + xr(wake / 1000 + 20) : 1 + xr(60));
        }
        const int oks = 1 + xr(4);
        for (int k = 0; k < oks; ++k) { tapAt(at, "ok"); at += 20 + xr(2600); }
        doorLoop(at + stallMs + 9000);
        unserved += (long) pics.size();
        if (getenv("A16_TELL") && kind == 0 && stallMs >= 3000 && ++shownBad <= 2)
        {
            printf("==== trial %d (seed %u, kind %d, the screen %u ms behind, a stall of %u ms)\n", trial, sd, kind, (unsigned) (screen.latencyUs / 1000), (unsigned) stallMs);
            printf("       taps on nothing %d, touches %d, oks served %ld, the screen on %s, busy until %.3f, now %.3f, taps waiting %d, cmds waiting %d\n", screen.tapsOnNothing, (int) touches.size(), oksServed, screen.page.c_str(), screen.busyUntil / 1e6, nowUs / 1e6, (int) screen.taps.size(), (int) screen.cmds.size());
            for (auto &l : trail) printf("       %s\n", l.c_str());
        }
        if (d5Bad != bad0 && ++shownBad <= 3)
        {
            printf("---- trial %d (seed %u, kind %d, the screen %u ms behind, a stall of %u ms): %s\n", trial, sd, kind, (unsigned) (screen.latencyUs / 1000), (unsigned) stallMs, d5First.c_str());
            for (auto &l : trail) printf("       %s\n", l.c_str());
        }
        extra7 = nullptr; wordHook = nullptr; tapScript = nullptr; loadScript = nullptr; cmdScript = nullptr; screen.sysMute.clear();
    }
    printf("the doors of OK at random: %d trials (a touch refused %ld, behind a model's read %ld, the second marker lost %ld, both markers lost %ld); OK served %ld times: left %ld, stayed %ld; presses never served %ld\n"
           "   OK served past the two seconds with the last click not said done: %ld times (it clicked once more %ld times)\n   D5 (what OK saves is what the page showed at the press obeyed): broken %ld time(s) of %ld\n",
           N, kinds[0], kinds[1], kinds[2], kinds[3], oksServed, oksLeft, oksStayed, unserved, late9, again9, d5Bad, d5Looked);
    CHECK(d5Bad == 0);
    CHECK(oddServe == 0);
    if (N >= 1000) CHECK(late9 > N / 200 && oksLeft > N / 3);
'''
if __name__ == '__main__':
    nn = sys.argv[sys.argv.index('--n') + 1] if '--n' in sys.argv else '2000'
    sd = sys.argv[sys.argv.index('--seed') + 1] if '--seed' in sys.argv else '500'
    sys.exit(lib.build_run('subtrim_door_storm', SCENES, extra=EXTRA, more_defines=('SUBTRIMVIEW',), args=['--x', nn, sd], sanitize=False, timeout=3000, label='reviewer A'))
