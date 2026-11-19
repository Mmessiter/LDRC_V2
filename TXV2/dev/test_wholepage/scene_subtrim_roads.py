#!/usr/bin/env python3
"""THE TWO REAL ROADS BY WHICH THE SUB-TRIM PAGE IS PUT UP AGAIN WITHOUT ITS START (B211, the fifteenth review: reviewer A's experiment, adopted) - main.cpp ButtonWasPressed's
"GOTO:" branch (Help's way back) and Utilities.h SaveOrRestoreScreen (the screen saver's) - LIFTED FROM THE SOURCE AND RUN, with the real HelpWordCame,
HideScreenAgain and ShowScreenAgain around them. dev/test_wholepage's scenes (scene_subtrim G3, scene_subtrim_real R2, both storms) stand in for
these two roads with three lines of their own ("page SubTrimView", CurrentView, pageBack()), and hold the source to them by counting the call's text.

 A. Help with a writing-out owed, the way back by the page's own word "GOTO:SubTrimView" (as the help page's button prints it): the page as the model has it
 B. the screen saver with a writing-out owed, a touch on the blank page (its code 73): the same
A call in the wrong place - above "CurrentView = SavedCurrentView;", or the page command behind the switch - passed every test: the scenes counted the
call's TEXT. Here the lines are run.   python3 scene_subtrim_roads.py [--show]"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
import scene_subtrim as base
m = lib.m
UTIL = m.UTIL
SOR, HIDE, SHOW = m.lift(UTIL, 'void SaveOrRestoreScreen(bool Restore)'), m.lift(UTIL, 'void HideScreenAgain()'), m.lift(UTIL, 'void ShowScreenAgain()')
GOTO = base.block('if (InStrng(GOTO, TextIn) > 0)')
views = sorted(set(re.findall(r'\b([A-Z][A-Z0-9_]*VIEW[A-Z0-9_]*)\b', SOR + HIDE + SHOW + GOTO)))
STUBS = ('RXOptionsViewStart', 'DisplayCurveAndServoPos', 'UpdateSwitchesView', 'UpdateOneSwitchView', 'StartReverseView', 'ForceDataRedisplay', 'StartPong', 'ShowMixValues', 'Force_ReDisplay', 'ShowServoPos',
         'StartChooseImage', 'ShowPIDBank', 'ShowRatesBank', 'ShowPIDAdvancedBank', 'ShowRatesAdvancedBank', 'ShowGOVBank', 'ShowGOV_Global_Bank', 'RfToolsRedraw', 'RestoreBrightness')
VARS = (('TextFileName', 'static char rr_TextFileName[40] = "SUBTRIM.TXT";'), ('pDataView', 'static char rr_pDataView[] = "page DataView";'), ('pRXSetupView', 'static char rr_pRXSetupView[] = "page RXSetupView";'),
        ('ForceVoltDisplay', 'static bool rr_ForceVoltDisplay = false;'), ('LastConnectionQuality', 'static int rr_LastConnectionQuality = 0;'), ('MixNumber', 'static int rr_MixNumber = 1;'),
        ('LastMixNumber', 'static int rr_LastMixNumber = 0;'), ('LastShowTime', 'static uint32_t rr_LastShowTime = 0;'), ('ScreenIsOff', 'static bool rr_ScreenIsOff = false;'))
EXTRA = base.EXTRA + '\n// ---- what the two lifted roads call besides this page\'s own (each a stand-in under a name of its own; the names are given back below)\nstatic int rr_calls = 0;\n' \
    + ''.join('static void rr_%s() { ++rr_calls; }\n' % s for s in STUBS) + ''.join(d + '\n' for _, d in VARS) \
    + ''.join('#define %s rr_%s\n' % (s, s) for s in STUBS) + ''.join('#define %s rr_%s\n' % (v, v) for v, _ in VARS) \
    + ('static bool RfVerifyPending() { return false; }   // (e99e, 18 Nov 2026: HideScreenAgain also waits for a save\'s read-back - none in these scenes)\n' if 'RfVerifyPending()' in HIDE else '') \
    + '// Utilities.h, as it stands:\n' + SOR + SHOW + HIDE \
    + r'''static void rrGotoWord()   // src/main.cpp ButtonWasPressed: its own lines for the help page's word "GOTO:<page>", as they stand
{
    int i = 0; char GOTO[] = "GOTO:"; char WhichPage[] = "page                                 "; char LOG[] = ".LOG"; char CopyToAllBanks[] = "callfm"; char ModelsView_ModelNumber[] = "ModelNumber"; char MixesView_MixNumber[] = "MixNumber";
    (void) i; (void) CopyToAllBanks; (void) ModelsView_ModelNumber; (void) MixesView_MixNumber;
    ''' + GOTO + r'''
}
''' + ''.join('#undef %s\n' % s for s in STUBS) + ''.join('#undef %s\n' % v for v, _ in VARS) + r'''
static bool rrWords(const char *w) { if (!strncmp(w, "GOTO:", 5)) { rrGotoWord(); return true; } return stWords(w); }
static void rrCodes(int n) { if (n == 73) ShowScreenAgain(); else if (n == 21) EndSubTrimView(); }      // main.cpp's table: 73 ShowScreenAgain, 21 EndSubTrimView
static void rrPages()
{
    P().buttons["help"] = { 'H', 'e', 'l', 'p', 'V', 'i', 'e', 'w', ':', 'S', 'U', 'B', 'T', 'R', 'I', 'M', '.', 'T', 'X', 'T' };                      // the page's Help button: print "HelpView:SUBTRIM.TXT"
    P().buttons["ok"] = { 149, 0, 0, 0 };
    { const char *w = "GOTO:SubTrimView"; screen.pages["LogView"].buttons["back"] = std::vector<uint8_t>(w, w + strlen(w)); }                           // the help page's button: print "GOTO:" / print return.txt
    { Page blank; blank.id = 0; blank.buttons["wake"] = { 128 + 73, 0, 0, 0 }; screen.pages["BlankView"] = blank; }                                    // the blank page's touch: print 73+128
    screen.pages0 = screen.pages; helpLive = true; wordHook = rrWords; extra7 = rrCodes;
}
'''
SCENES = r'''
  pageNew = true;
  for (int road = 0; road < 2; ++road)
    for (uint32_t late : { 1500u, 60000u, 300000u })
    {
      more(); addSubTrim(); rrPages(); screen.latencyUs = late; openSubTrim(); tapCh(10, 4); stLoop(600);
      tapAt(10, "plus!"); stLoop(400);                                                       // a + never heard: the page one ahead on channel 4
      tapAt(10, "plus"); stLoop(late / 1000 + 150);                                          // a + refused: channel 4 put right, a writing-out owed when he has paused
      tapCh(10, 7); tapAt(60, "plus!"); stLoop(late / 1000 + 100);                           // channel 7, a + never heard: the page shows -29, the model has -30
      const bool owedThen = SubTrimSettleDue; const int shownThen = shown(7);
      if (road == 0)
      {   // HELP: the page's own button, served by the REAL HelpWordCame; then the help page's button "back": the REAL "GOTO:" lines
          tapAt(5, "help"); stLoop(late / 1000 + 900);
          CHECK(CurrentView == LOGVIEW && screen.page == "LogView" && SavedCurrentView == SUBTRIMVIEW);   // (LogVIEWNew sets LOGVIEW over HelpWordCame's HELP_VIEW in the same call)
          tapAt(5, "back"); stLoop(late / 1000 + 1200);
      }
      else
      {   // THE SCREEN SAVER: the REAL HideScreenAgain (Utilities.h CheckScreenTime calls it), then a touch on the blank page: its code 73 -> the REAL ShowScreenAgain
          HideScreenAgain(); stLoop(late / 1000 + 900);
          CHECK(CurrentView == BLANKVIEW && screen.page == "BlankView");
          tapAt(5, "wake"); stLoop(late / 1000 + 1200);
      }
      say("%s, the screen %3u ms behind: owed when the page was left %d (it showed %d on channel 7, the model has %d); back on %s (this board believes view %u): the page shows %d, every box the model's %d, shown %d, the channel %ld\n",
          road == 0 ? "A. HELP and its way back by the real GOTO lines" : "B. THE SCREEN SAVER and a touch, by the real SaveOrRestoreScreen", late / 1000, (int) owedThen, shownThen, trim(7), screen.page.c_str(), (unsigned) CurrentView, shown(7), (int) pageIsModel(), (int) SubTrimShown, B("s0"));
      CHECK(shownThen == -29 && trim(7) == -30);
      CHECK(CurrentView == SUBTRIMVIEW && screen.page == "SubTrimView" && pageIsModel() && sliderIsShown() && shown(7) == -30 && SubTrimShown && B("s0") == 1 && !SubTrimSettleDue);
      // ... and the page works on from there: a + on channel 7 is taken, OK saves and leaves
      tapCh(10, 7); tapAt(200, "plus"); stLoop(late / 1000 + 600); CHECK(trim(7) == -29 && pageIsModel());
      const int saves0 = (int) saves.size(); tapAt(5, "ok"); stLoop(late / 1000 + 600);
      if (CurrentView == SUBTRIMVIEW) { tapAt(5, "ok"); stLoop(late / 1000 + 2300); }      // (OK may ask to be pressed twice)
      CHECK((int) saves.size() == saves0 + 1 && CurrentView == RXSETUPVIEW);
    }
  wordHook = nullptr; tapScript = nullptr; loadScript = nullptr; cmdScript = nullptr; extra7 = nullptr; helpLive = false;
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('subtrim_roads', SCENES, extra=EXTRA, more_defines=tuple(['SUBTRIMVIEW'] + [v for v in views if v != 'SUBTRIMVIEW']), sanitize=True, timeout=1200))
