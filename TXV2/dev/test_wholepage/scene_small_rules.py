#!/usr/bin/env python3
"""SMALL RULES OF THE ELEVENTH REVIEW'S CURES, each run (15 Nov 2026):
 W. A BARE WORD OF THE SCREEN'S OWN ENDS WHERE ITS OWN TEXT ENDS (reviewer A's low 7): "ldrcpipe=2" with a late text reply glued behind it - a box's
    text, "Mark 2" - left the box's letters in TextIn, where main.cpp looks for the pages' words: the GPS position would have been marked.
 D. THE SAVE / RESTORE DIALOG chooses NOTHING when one of its ticks had no answer (it chose the ticks in front of it: the PIDs restored and not the
    rates he had ticked too).
 G. THE GOVERNOR PAGE'S WORDS (reviewer B's low 7): asked by the page's own timer twice a second - not while the screen cannot be asked (each asking was
    "a box with no answer": the sound and a line in the log, twice a second), and no answer writes no word ("0 - 4 only!").
 F. THE FILE NAME'S QUESTION (reviewer B's low 6): another page put up from inside the wait for the name (the front page: the power button) - the
    question's way back is NOT sent over it, and the name has no answer.
 M. THE MODELS PAGE'S LOOK AT ITSELF asks its two lists - and looks at the page's number AGAIN behind them (reviewer A's low 5): the number can be
    learned only WITH those answers (the opening work overtaken by the front page), and the front page's 0 was then row 0: model 1.
 M2. ... and asks nothing while a page's marker is still awaited (the page is not known to be up).
 E. THE EASY PAGE'S SLIDERS before a save: every slider and the switch, or nothing (and false: the save stops).
 E2. THE EASY PAGE'S SWITCH, tapped, its box unanswered: nothing is taken - and the screen's own switch, which turned under the finger, is put back.
 I. THE PICTURE CHOOSER'S WORD (the twelfth review, reviewer A's finding 5): "LDRCIMG <name>" with a late text answer glued behind it in the same read took
    the answer's letters into the name ("YakpMark"). A reply's end in the read: the picture is kept, as for "LDRCIMG" alone.
The REAL OwnWordCut (Nextion.h), Collect_data_from_dialog (RF_Save_Restore.h), AddWords (RF_Governor_Global.h), GetBackupFilename (Utilities.h),
CheckModelName (main.cpp), EzSyncSliders and EasySpoolTapped (RF_Easy.h) over the pretend screen."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
SR, GG, EZ, CI = (m.release(m.src('include/' + f)) for f in ('RF_Save_Restore.h', 'RF_Governor_Global.h', 'RF_Easy.h', 'ChooseImage.h'))
MAINC = re.sub(r'//[^\n]*', '', m.release(m.src('src/main.cpp')))
if not re.search(r'if \(!TextInFramed && ScreenFramesBursts\)\s*OwnWordCut\(TextIn\);\s*if \(!strncmp\(TextIn, "ldrctel ", 8\)\)', re.sub(r'//[^\n]*', '', MAINC)):   # (the fourteenth review: the pipe's lines are answered first now, the screen's own words behind them - scene_own_words)
    print('FAIL: main.cpp ButtonWasPressed: a bare word of the screen\'s own is ended where its own text ends (OwnWordCut) before any word is looked for in it'); sys.exit(1)
EXTRA = r'''
#define DO_PIDS 1
#define DO_PIDS_ADVANCED 2
#define DO_RATES 4
#define DO_RATES_ADVANCED 8
#define DO_GOV_PROFILES 16
static uint8_t LocalBank = 0, Which_Params = 0, SelectedItemCount = 0, OneProgressItem = 0; static float RotorFlight_Version = 2.3f;
static uint8_t CountSelectedParams(uint8_t w) { uint8_t n = 0; for (int b = 0; b < 5; ++b) n += (w >> b) & 1; return n; }
static int rfStarts = 0; static void RotorFlightStart() { ++rfStarts; }
static char Gov_Mode_types[5][24] = { "0 - OFF", "1 - PASSTHROUGH", "2 - STANDARD", "3 - MODE1", "4 - MODE2" };
static char Throttle_types[3][24] = { "0 - NORMAL", "1 - OFF_ON", "2 - OFF_IDLE_ON" };
static int EzPos[5] = { 50, 50, 50, 0, 0 }; static bool EzMoved[5] = { false, false, false, false, false }, EzRatesFeel = true, EzSpool = true, EzSpoolTouched = false, Ez_Was_Edited = false;
static void EzEdited() { Ez_Was_Edited = true; }
static bool EzHave = true; enum { EZ_IDLE = 0 }; static int EzStep = EZ_IDLE;
#define LDRC_IMAGE_WORD "LDRCIMG"
static char ModelImageFileName[9] = "Old"; static int imgEnds = 0; static void EndChooseImage() { ++imgEnds; }
static int cutLogLines = 0; static void LogScreenLine(const char *) { ++cutLogLines; }   // (the seventeenth review: a line for the log glued behind a bare word is handed on before the cut - dev/test_wholepage/scene_dying_behind_word runs the real one)
''' + m.lift(CI, 'FLASHMEM void ChooseImageFromScreen(const char *text)') + m.lift(m.NEXTION, 'B211_RARE static void OwnWordCut(char *t)') + m.lift(SR, 'FLASHMEM void Collect_data_from_dialog()') + m.lift(GG, 'FLASHMEM void AddWords()') + m.lift(EZ, 'FLASHMEM static bool EzSyncSliders()') + m.lift(EZ, 'FLASHMEM void EasySpoolTapped()') + r'''
static std::string cut9(const char *s) { char b[200]; memset(b, 0, sizeof b); memcpy(b, s, strlen(s)); OwnWordCut(b); return b; }
static bool frontNow = false; static void frontFromWait() { if (!frontNow || screen.page == "FrontView") return; frontNow = false; SendCommand((char *) "page FrontView"); CurrentView = FRONTVIEW; }
static void addSmall()
{
    Page d; d.id = 44; for (const char *t : { "n0", "n1", "sw0", "sw1", "sw2", "sw3", "sw4" }) d.boxes[t] = { false, 0, "" };
    screen.pages["PickBankView1"] = d;
    Page g; g.id = 5; g.boxes["n14"] = { false, 2, "" }; g.boxes["n28"] = { false, 1, "" }; g.boxes["GovMode"] = { true, 0, "-" }; g.boxes["ThrMode"] = { true, 0, "-" };
    screen.pages["RFGovViewGlbl"] = g;
    Page e; e.id = 81; for (const char *t : { "s0", "s1", "s2", "s3", "s4", "sw" }) e.boxes[t] = { false, 0, "" };
    screen.pages["EasyView"] = e;
    screen.pages0 = screen.pages;
}
'''
SCENES = r'''
    // W. the word ended where its own text ends
    CHECK(cut9("ldrcpipe=2pMark 2") == "ldrcpipe=2" && cut9("ldrcpipe=2") == "ldrcpipe=2" && cut9("ldrcpipe=3\xFF\xFF\xFFpStCH") == "ldrcpipe=3");
    CHECK(cut9("TIME=1731672000pSetup") == "TIME=1731672000" && cut9("TIME=17") == "TIME=17");
    CHECK(cut9("ldrctel 1,2,3\npMark 2") == "ldrctel 1,2,3\n" && cut9("ldrcrep 200 ok\npDelFile") == "ldrcrep 200 ok\n" && cut9("ldrctel 1,2") == "ldrctel 1,2");   // (a pipe line still coming: left as it is)
    CHECK(cut9("Mark 2") == "Mark 2" && cut9("LDRCLOG a line with TIME=5 in it") == "LDRCLOG a line with TIME=5 in it" && cut9("xTIME=5pq") == "xTIME=5pq");        // (only at the word's head)
    //    (the twelfth review, reviewer A's experiment U: "UKRULES" was not among them - the one own word that falls through to the pages' words)
    CHECK(cut9("UKRULESpMark 2\xFF\xFF\xFF") == "UKRULES" && cut9("UKRULES") == "UKRULES" && cut9("UKRULESpSetup") == "UKRULES" && cut9("xUKRULESpMark") == "xUKRULESpMark" && cut9("UKRULE") == "UKRULE");
    // I. the picture chooser's word: its name is taken; with a reply's end in the same read the picture is kept; alone, kept; on another page, nothing
    CurrentView = CHOOSEIMAGEVIEW; strcpy(ModelImageFileName, "Old"); imgEnds = 0;
    ChooseImageFromScreen("LDRCIMG Yak"); CHECK(!strcmp(ModelImageFileName, "Yak") && imgEnds == 1);
    strcpy(ModelImageFileName, "Old"); ChooseImageFromScreen("LDRCIMG YakpMark 2\xFF\xFF\xFF"); CHECK(!strcmp(ModelImageFileName, "Old") && imgEnds == 2);
    ChooseImageFromScreen("LDRCIMG Yak\xFF"); CHECK(!strcmp(ModelImageFileName, "Old") && imgEnds == 3);
    ChooseImageFromScreen("LDRCIMG"); CHECK(!strcmp(ModelImageFileName, "Old") && imgEnds == 4);
    ChooseImageFromScreen("LDRCIMG Sea_Fury-2"); CHECK(!strcmp(ModelImageFileName, "Sea_Fury") && imgEnds == 5);   // (eight characters, as ever)
    CurrentView = FRONTVIEW; ChooseImageFromScreen("LDRCIMG Yak"); CHECK(!strcmp(ModelImageFileName, "Sea_Fury") && imgEnds == 5);
    // D. the save / restore dialog: bank 3, the PIDs and the rates ticked. Every box answers: both chosen. One tick unanswered - each in turn: NOTHING chosen
    more(); addSmall(); SendCommand((char *) "page PickBankView1"); CurrentView = 44; loopFor(600);
    { Page &pg = screen.pages["PickBankView1"]; pg.boxes["n0"].val = 3; pg.boxes["sw0"].val = 1; pg.boxes["sw2"].val = 1;
      BoxesLostAtWork = BoxesLost; Collect_data_from_dialog();
      say("D. the dialog, bank 3, PIDs and rates ticked: bank %u, chosen %u (PIDs 1, rates 4), items %u\n", (unsigned) LocalBank, (unsigned) Which_Params, (unsigned) SelectedItemCount);
      CHECK(LocalBank == 3 && Which_Params == (DO_PIDS | DO_RATES) && SelectedItemCount == 2 && rfStarts == 1); }
    for (const char *lost : { "n0", "sw0", "sw1", "sw2", "sw3", "sw4" })
    {
        more(); addSmall(); SendCommand((char *) "page PickBankView1"); CurrentView = 44; loopFor(600);
        Page &pg = screen.pages["PickBankView1"]; pg.boxes["n0"].val = 3; pg.boxes["sw0"].val = 1; pg.boxes["sw2"].val = 1; pg.boxes["sw3"].val = 1;
        screen.mute.insert(lost); BoxesLostAtWork = BoxesLost; Which_Params = 0xFF; Collect_data_from_dialog(); screen.mute.clear();
        say("D (%s unanswered): chosen %u, items %u\n", lost, (unsigned) Which_Params, (unsigned) SelectedItemCount);
        CHECK(Which_Params == 0 && SelectedItemCount == 0);                       // (it was: the PIDs alone, when the rates' tick had no answer)
        loopFor(3000);
    }
    // G. the governor page's words
    more(); addSmall(); SendCommand((char *) "page RFGovViewGlbl"); CurrentView = 5; loopFor(600);
    { Page &pg = screen.pages["RFGovViewGlbl"];
      AddWords(); loopFor(200); CHECK(pg.boxes["GovMode"].txt == "2 - STANDARD" && pg.boxes["ThrMode"].txt == "1 - OFF_ON");
      pg.boxes["n14"].val = 3; AddWords(); loopFor(200); CHECK(pg.boxes["GovMode"].txt == "3 - MODE1");
      pg.boxes["n14"].val = 4; pg.boxes["n28"].val = 2;
      { const int g0 = screen.gets; const uint32_t lost0 = BoxesLost; ScreenAnswerOwed = true; holdCatchUp = true;       // the screen owes an answer: NOTHING is asked - and nothing counted as lost
        for (int k = 0; k < 6; ++k) AddWords();
        ScreenAnswerOwed = false; holdCatchUp = false;
        say("G. the governor's words asked six times while the screen owes an answer: boxes asked %d, counted as lost %u; the words '%s', '%s'\n", screen.gets - g0, (unsigned) (BoxesLost - lost0), pg.boxes["GovMode"].txt.c_str(), pg.boxes["ThrMode"].txt.c_str());
        CHECK(screen.gets == g0 && BoxesLost == lost0 && pg.boxes["GovMode"].txt == "3 - MODE1"); }
      screen.mute.insert("n14"); BoxesLostAtWork = BoxesLost; AddWords(); screen.mute.clear(); loopFor(3000);              // one box with no answer: the words stay (it was: "0 - 4 only!")
      CHECK(pg.boxes["GovMode"].txt == "3 - MODE1" && pg.boxes["ThrMode"].txt == "1 - OFF_ON");
      AddWords(); loopFor(200); CHECK(pg.boxes["GovMode"].txt == "4 - MODE2" && pg.boxes["ThrMode"].txt == "2 - OFF_IDLE_ON");
      pg.boxes["n14"].val = 9; AddWords(); loopFor(200); CHECK(pg.boxes["GovMode"].txt == "0 - 4 only!"); }
    // F. the file name's question: answered Yes - and from inside the wait for the NAME the front page is put up (the power button, the link)
    more(); tapAt(5, "setup"); loopFor(800); BoundFlag = ModelMatched = true;
    { screen.pages["BackupView"].boxes["t1"].txt = "GOBLIN.MOD"; strcpy(SingleModelFile, "before");
      tapAt(1500, "yes"); waitHook = nullptr; flyHook = [] { if (Confirmed[0] == 'Y') { frontNow = true; frontFromWait(); } };
      const bool go = GetBackupFilename((char *) "page RXOptionsView", (char *) "GOBLIN.MOD", (char *) "Goblin", (char *) "Backup", (char *) "File name");
      flyHook = nullptr; loopFor(1500);
      say("F. the file name's question, Yes - and the front page put up from inside the wait for the name: the answer %d; the screen shows %s; this board believes view %u; overtaken %d\n", (int) go, screen.page.c_str(), (unsigned) CurrentView, (int) QuestionOvertaken);
      CHECK(!go);                                                                // no name: no "yes"
      CHECK(screen.page == "FrontView" && CurrentView == FRONTVIEW);             // the question's way back did not go over the front page
      CHECK(QuestionOvertaken); }
    BoundFlag = ModelMatched = false;
    // M. the Models page's look at itself, the page's number not yet known, the screen on the FRONT page (whose own boxes of those names hold 5 and 0)
    more(); tapAt(5, "models"); loopForModels(2000); CHECK(CurrentView == MODELSVIEW && ModelNumber == 4);
    { screen.pages["FrontView"].boxes["MMems"] = { false, 5, "" }; screen.pages["FrontView"].boxes["Mfiles"] = { false, 0, "" };
      screen.page = "FrontView"; ScreenPageId = 0xFF; ScreenPageIdDue = true; modelsRead.clear();   // (the page's number is still to come: it is learned with the first box's own "which page?" answer)
      const bool changed = CheckModelName();
      say("M. the Models page's look, the page's number not known and the screen on the front page: changed %d, models read %d, model %u; the page's number learned: %u\n", (int) changed, (int) modelsRead.size(), (unsigned) ModelNumber, (unsigned) ScreenPageId);
      CHECK(ScreenPageId == 13);                                                 // (the scene is the one meant: the front page's number was learned with the answers)
      CHECK(!changed && modelsRead.empty() && ModelNumber == 4); }
    // M2. ... and while a page's marker is still awaited the page is not known to be up: NOTHING is asked (and nothing counted as lost)
    more(); tapAt(5, "models"); loopForModels(2000); CHECK(CurrentView == MODELSVIEW && ModelNumber == 4);
    { const int g0 = screen.gets; const uint32_t lost0 = BoxesLost; modelsRead.clear();
      ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | ScreenMarkCount; ScreenMarkAskedMs = millis();
      const bool changed = CheckModelName(); ScreenMarkAwaited = 0;
      say("M2. the Models page's look while a page's marker is awaited: boxes asked %d, counted as lost %u\n", screen.gets - g0, (unsigned) (BoxesLost - lost0));
      CHECK(!changed && screen.gets == g0 && BoxesLost == lost0 && modelsRead.empty() && ModelNumber == 4); }
    // E2. the Easy page's spool-up switch TAPPED - the screen's own switch has turned under the finger (off) - and its box has NO ANSWER: nothing
    //     is taken, and the switch is put back as it is in hand (on). Answered: taken
    more(); addSmall(); SendCommand((char *) "page EasyView"); CurrentView = EASYVIEW; loopFor(600);
    { Page &pg = screen.pages["EasyView"]; EzSpool = true; EzSpoolTouched = false; Ez_Was_Edited = false; EzHave = true; EzStep = EZ_IDLE;
      pg.boxes["sw"].val = 0;
      screen.mute.insert("sw"); BoxesLostAtWork = BoxesLost; EasySpoolTapped(); screen.mute.clear(); loopFor(3000);
      say("E2. the switch tapped, its box unanswered: spool-up in hand %d, touched %d; the screen's switch now %d\n", (int) EzSpool, (int) EzSpoolTouched, (int) pg.boxes["sw"].val);
      CHECK(EzSpool && !EzSpoolTouched && !Ez_Was_Edited);
      CHECK((int) pg.boxes["sw"].val == 1);
      pg.boxes["sw"].val = 0; BoxesLostAtWork = BoxesLost; EasySpoolTapped(); loopFor(300);
      CHECK(!EzSpool && EzSpoolTouched && Ez_Was_Edited && (int) pg.boxes["sw"].val == 0); }
    // E. the Easy page's sliders before a save: all asked; one unanswered - each in turn - and NOTHING is taken, false
    for (int which = -1; which < 6; ++which)
    {
        static const char *box[6] = { "s0", "s1", "s2", "s3", "s4", "sw" };
        more(); addSmall(); SendCommand((char *) "page EasyView"); CurrentView = 81; loopFor(600);
        Page &pg = screen.pages["EasyView"]; pg.boxes["s0"].val = 12; pg.boxes["s1"].val = 14; pg.boxes["s2"].val = 8; pg.boxes["s3"].val = 9; pg.boxes["s4"].val = 3; pg.boxes["sw"].val = 0;
        EzPos[0] = EzPos[1] = EzPos[2] = 50; EzPos[3] = EzPos[4] = 0; for (bool &b : EzMoved) b = false; EzSpool = true; EzSpoolTouched = false; Ez_Was_Edited = false; EzRatesFeel = true;
        if (which >= 0) screen.mute.insert(box[which]);
        BoxesLostAtWork = BoxesLost; const bool ok = EzSyncSliders(); screen.mute.clear();
        if (which < 0) CHECK(ok && EzPos[0] == 60 && EzPos[1] == 70 && EzPos[2] == 40 && EzPos[3] == 15 && EzPos[4] == -15 && !EzSpool && EzSpoolTouched && Ez_Was_Edited && EzMoved[0] && EzMoved[4]);
        else
        {
            say("E (%s unanswered): taken %d; start %d, agility %d, stick feel %d, cyclic %d, tail %d, spool-up %d, edited %d\n", box[which], (int) ok, EzPos[0], EzPos[1], EzPos[2], EzPos[3], EzPos[4], (int) EzSpool, (int) Ez_Was_Edited);
            CHECK(!ok && EzPos[0] == 50 && EzPos[1] == 50 && EzPos[2] == 50 && EzPos[3] == 0 && EzPos[4] == 0 && EzSpool && !EzSpoolTouched && !Ez_Was_Edited && !EzMoved[0] && !EzMoved[4]);
        }
        loopFor(3000);
    }
'''
sys.exit(lib.build_run('small_rules', SCENES, extra=EXTRA, more_defines=('MODELSVIEW', 'EASYVIEW', 'CHOOSEIMAGEVIEW'), sanitize=False))
