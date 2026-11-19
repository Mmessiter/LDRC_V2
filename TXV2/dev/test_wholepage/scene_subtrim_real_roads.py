#!/usr/bin/env python3
"""THE REAL-PAGE STORM (scene_subtrim_real.py: the real page file, the screen's own interpreter, the real finger) WITH THE PAGE PUT UP AGAIN BY THE
REAL ROADS (B211, the fifteenth review: reviewer A's experiment, adopted) - Help by the page's own button (the real HelpWordCame), back by the help
page's own word (the real "GOTO:" lines of main.cpp); the screen saver (the real HideScreenAgain) and a touch on the blank page (its code 73: the real
ShowScreenAgain / SaveOrRestoreScreen) - where the suite's storm has three lines of its own. Two trials in three are "rough" here (one in three there).
   python3 scene_subtrim_real_roads.py [--n trials] [--seed first] [--san]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
import scene_subtrim as base
import scene_subtrim_real as realscene
import scene_subtrim_roads as rr
ROADS = rr.EXTRA[len(base.EXTRA):]            # (the two lifted roads and what they call - without the pretend page, which the real-page scene has already)
assert 'static void rrGotoWord()' in ROADS and 'void SaveOrRestoreScreen(bool Restore)' in ROADS
EXTRA = realscene.EXTRA + ROADS + r'''
static void rrOk2(int n) { if (n == 73) ShowScreenAgain(); else realOk(n); }             // main.cpp's table: 73 ShowScreenAgain; 21 EndSubTrimView (with the storm's book of what the page showed)
static void rrPagesStorm()
{
    P().buttons["help"] = { 'H', 'e', 'l', 'p', 'V', 'i', 'e', 'w', ':', 'S', 'U', 'B', 'T', 'R', 'I', 'M', '.', 'T', 'X', 'T' };
    { const char *w = "GOTO:SubTrimView"; screen.pages["LogView"].buttons["back"] = std::vector<uint8_t>(w, w + strlen(w)); }
    { Page blank; blank.id = 0; blank.buttons["wake"] = { 128 + 73, 0, 0, 0 }; screen.pages["BlankView"] = blank; }
    screen.pages0 = screen.pages; helpLive = true; wordHook = rrWords;
}
static long roadsHelp9 = 0, roadsSaver9 = 0, roadsBack9 = 0;
'''
S = realscene.SCENES
OLD = 'else if (pick < 93 && rough) { CurrentView = LOGVIEW; SendCommand((char *) "page LogView"); rLoop(20 + xr(400)); SendCommand((char *) "page SubTrimView"); CurrentView = SUBTRIMVIEW; pageBack(); okPresses.clear(); ++reloads9; note("Help and its way back: the page put up again, written out"); }'
NEW = r'''else if (pick < 93 && rough)
            {   // THE REAL ROADS
                const bool saver = xr(2) != 0;
                if (saver) { HideScreenAgain(); ++roadsSaver9; note("the screen saver blanks the screen (the real HideScreenAgain)"); }
                else { tapAt(1, "help"); ++roadsHelp9; note("Help is pressed (the page's own button)"); }
                rLoop(20 + xr(400) + screen.latencyUs / 1000);
                for (int tries = 0; tries < 8 && CurrentView != SUBTRIMVIEW; ++tries)
                {
                    if (CurrentView == BLANKVIEW) tapAt(1, "wake"); else if (CurrentView == LOGVIEW) tapAt(1, "back"); else break;   // (a help text shows: this board believes LOGVIEW)
                    rLoop(150 + screen.latencyUs / 1000 + xr(300));
                }
                if (CurrentView == SUBTRIMVIEW) { ++reloads9; ++roadsBack9; note("... and back on the page, by the real road"); }
            }'''
assert S.count(OLD) == 1 and S.count('extra7 = realOk;') == 1 and S.count('const bool rough = sd % 3 == 2;') == 1 and S.count('more(); addReal();') >= 4
S = S.replace(OLD, NEW).replace('extra7 = realOk;', 'extra7 = rrOk2;').replace('const bool rough = sd % 3 == 2;', 'const bool rough = sd % 3 != 0;').replace('more(); addReal();', 'more(); addReal(); rrPagesStorm();')
S = S.replace('    wordHook = nullptr;\n', '    printf("   the real roads: Help pressed %ld times, the screen saver %ld times; back on the page by the real road %ld times\\n", roadsHelp9, roadsSaver9, roadsBack9);\n    CHECK(roadsBack9 > N / 20);\n    wordHook = nullptr; helpLive = false;\n')
if __name__ == '__main__':
    nn = sys.argv[sys.argv.index('--n') + 1] if '--n' in sys.argv else '1000'
    sd = sys.argv[sys.argv.index('--seed') + 1] if '--seed' in sys.argv else '15150000'
    views = ['SUBTRIMVIEW'] + [v for v in rr.views if v != 'SUBTRIMVIEW']
    sys.exit(lib.build_run('subtrim_real_roads', S, extra=EXTRA, more_defines=tuple(views), args=['--x', nn, sd], sanitize='--san' in sys.argv, timeout=6000))
