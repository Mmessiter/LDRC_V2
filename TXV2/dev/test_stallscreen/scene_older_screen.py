#!/usr/bin/env python3
"""EXP O8 (review 12, reviewer A): A SCENE THAT TELLS THE RULE "a page command from inside a get's radio turn lets go what stood open" FROM ITS ABSENCE.
The author's O8 scene (dev/test_stallscreen/scene_zero_rules.py) runs the moment on a screen that says markers - there the frame that closes without
the rule is a press read between a page command and its marker, dropped anyway. On a screen that says NO markers and frames nothing (one "older than
them": three markers never came - Nextion.h SCREEN_MARK_MISSES; presses are then "only purged") nothing else lets it go:
  four bytes stand open in a number box's wait; the radio's turn puts a box up and its own look for a press leaves the box's "Yes" in TextIn (which
  it has obeyed); the end of what stood open comes in. WITH the rule: nothing is kept. WITHOUT it: the four bytes now in TextIn - the "Yes" - are
  kept as a press and OBEYED A SECOND TIME by the main loop, on whatever page is then up.
(The reviewer's own scene, taken as it came: the author's O8 in scene_zero_rules.py is masked - on a screen that says markers the frame is dropped anyway.)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
static int o8Step = 0, o8Calls = 0, o8OnWire = -1;
static void o8Hook()   // (the author's own, scene_zero_rules.py)
{
    ++o8Calls;
    if (o8Step == 1 && o8Calls == 2)
    {
        for (int i = 0; i < 4; ++i) screen.emit(nowUs + 18400 + (uint64_t) i * 400, { (uint8_t) (i ? 0x00 : 0xC1) });
        o8Step = 2;
        return;
    }
    if (o8Step != 2) return;
    o8Step = 3; o8OnWire = (int) NEXTION.available();
    SendCommand((char *) "page FrontView");
    TextIn[0] = (char) 0x81; TextIn[1] = TextIn[2] = TextIn[3] = 0;   // (what that look left in TextIn: the box's own "Yes", which it has obeyed)
    screen.emit(nowUs + 100, END9);                                    // ... and the end of what stood open comes in during this turn
}
'''
SCENES = r'''
    {
      more(); screen.realUart = true; tapAt(5, "setup"); loopFor(900); screen.deaf = true; holdCatchUp = true; obeyed.clear(); ghosts.clear();
      // a screen that frames nothing and says no markers: three of them never came (Nextion.h: "presses are only purged until one comes")
      ScreenFramesBursts = false; ScreenSaysMarks = false; ScreenMarkMisses = SCREEN_MARK_MISSES; ScreenMarkAwaited = 0; ScreenAnswerOwed = false; ScreenSaysPage = false; ScreenPageId = 0xFF;
      FrameEnableSentMs = millis();
      const int pend0 = PendingCount;
      o8Step = 1; o8Calls = 0; o8OnWire = -1; flyHook = o8Hook;
      const uint32_t v = GetValue((char *) "n3"); flyHook = nullptr;
      const int kept = PendingCount - pend0;
      int yes = 0; for (int i = 0; i < 400; ++i) { LoopPass(); nowUs += 500; } for (int c : obeyed) yes += c == 1;
      printf("O8 (a screen that says no markers and frames nothing). a page command and a box's own read from inside a get's radio turn, four bytes standing open: the get gave %lu; frames kept from that wait %d; the box's 'Yes' obeyed again %d time(s); step %d\n",
             (unsigned long) v, kept, yes, o8Step);
      CHECK(o8Step == 3 && o8OnWire == 0);      // (the scene is the one meant)
      CHECK(v == 65535);
      CHECK(kept == 0);                          // nothing of what stood open is kept as a press
      CHECK(yes == 0);                           // ... and the box's "Yes" is not obeyed a second time
    }
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('older_screen', SCENES, EXTRA, sanitize=False))
