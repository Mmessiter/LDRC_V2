#!/usr/bin/env python3
"""Reviewer A (16): THE SUB-TRIM PAGE, A TOUCH LET GO BETWEEN THE TWO MARKERS (Nextion.h DropUnconfirmedPress, its second way out - the break-it round's RV9:
no RUN notices that call taken out). The page's FIRST marker is heard, its SECOND is lost on the wire: the page is up, its "done" heard, and until this
board has found the marker lost (1.5 s and a round trip) a touch's burst is let go WITHOUT A WORD (it is "what a page prints as it comes up").
 Y1. Help and its way back, the second marker lost, "+" half a second on: the page shows the touch, the model has not got it - is it owed its writing-out?
 Y2. ... and OK four quiet seconds on: does it leave with the page showing what is saved?
     usage: scene_subtrim_second_marker.py [TXV1B root]     (another root: a copy with a rule taken out)"""
import os, sys
ROOT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (taken into the suite: this file's own tree; another root - a copy with a rule taken out - as the first word)
sys.path.insert(0, os.path.join(ROOT, 'dev', 'test_wholepage'))
os.environ['LDRC_RUNS_ONLY'] = '1'
import lib
import scene_subtrim as base
os.environ.pop('LDRC_RUNS_ONLY', None)   # (it was set above for that one import only: the base scene's own text checks are its own business)
EXTRA = base.EXTRA + r'''
static int oksServed = 0, oksLeft = 0;
static void myOk(int n) { if (n != 21) return; ++oksServed; if (CurrentView != SUBTRIMVIEW) return; EndSubTrimView(); if (CurrentView != SUBTRIMVIEW) ++oksLeft; }
static bool loseSecond = false; static int muted = 0;
static bool myCmd(const char *c)   // the screen handles "page SubTrimView": from here its answer to "get ldrcsync" (the SECOND marker) is lost
{
    if (loseSecond && !strcmp(c, "page SubTrimView")) { screen.sysMute.insert("ldrcsync"); ++muted; }
    return stCmd(c);
}
'''
SCENES = r'''
    for (uint32_t late : { 1500u, 60000u, 300000u })
    {
        more(); addSubTrim(); P().buttons["ok"] = { 149, 0, 0, 0 }; screen.pages0 = screen.pages; extra7 = myOk; pageNew = true; oksServed = oksLeft = 0; muted = 0;
        screen.latencyUs = late; openSubTrim(); stLoop(late / 1000 + 300);
        CHECK(SubTrimSaysDone && SubTrimShown && pageIsModel());
        CurrentView = LOGVIEW; SendCommand((char *) "page LogView"); stLoop(late / 1000 + 600);            // Help ...
        cmdScript = myCmd; loseSecond = true;
        SendCommand((char *) "page SubTrimView"); CurrentView = SUBTRIMVIEW; pageBack();                     // ... and its way back (main.cpp "GOTO:"): the FIRST marker comes, the second never
        stLoop(late / 1000 + 400); loseSecond = false; screen.sysMute.clear();                               // (the page is up; from here the screen answers everything again)
        const bool oldPage = ScreenMarkOldPage; const uint32_t awaited = ScreenMarkAwaited; const int stale0 = stale; const uint16_t let0 = LoadPrintsLetGo;
        tapAt(5, "plus"); stLoop(late / 1000 + 300);
        say("Y1. the screen %3u ms behind; the page back from Help, its SECOND marker lost (muted %d): still the old page's %d, a marker awaited %d, 'done' heard %d; '+' made the page show %d - the model has %d; let go as the old page's %d, let go between the markers %d; a writing-out owed %d\n",
            late / 1000, muted, (int) oldPage, awaited != 0, (int) SubTrimShown, shown(1), trim(1), stale - stale0, (int) (uint16_t) (LoadPrintsLetGo - let0), (int) SubTrimSettleDue);
        CHECK(!oldPage && awaited != 0 && (uint16_t) (LoadPrintsLetGo - let0) == 1 && stale == stale0);         // the road meant: between the two markers, without a word
        stLoop(4000);
        const int pageBefore = shown(1), modelBefore = trim(1);
        tapAt(5, "ok"); stLoop(late / 1000 + 800);
        if (CurrentView == SUBTRIMVIEW) { tapAt(5, "ok"); stLoop(late / 1000 + 2300); }
        say("    four quiet seconds on the page shows %d, the model has %d; OK: served %d, left the page %d - saved with %d on channel 1\n", pageBefore, modelBefore, oksServed, oksLeft, trim(1));
        CHECK(pageBefore == modelBefore);                                                                     // a burst this board itself let go is owed a writing-out
        CHECK(oksLeft == 0 || pageBefore == trim(1));
        extra7 = nullptr; wordHook = nullptr; tapScript = nullptr; loadScript = nullptr; cmdScript = nullptr;
    }
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('subtrim_second_marker', SCENES, extra=EXTRA, more_defines=('SUBTRIMVIEW',), args=['--show'], sanitize=True, timeout=1200, label='reviewer A'))
