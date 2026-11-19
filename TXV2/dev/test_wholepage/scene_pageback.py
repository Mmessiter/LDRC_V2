#!/usr/bin/env python3
"""R10-B exp 3: A PAGE'S OWN WORD OBEYED WHILE A QUESTION BOX IS UP reads the page's boxes FROM THE BOX'S PAGE.
"ldrcadj" (AdjustView's postinitialize) is no press: it passes at any time, and outlives a page command (PurgeKeptPresses keeps it).
A button's work that puts the Switches-and-knobs page back up and then puts up a box (the picker's OK on the arm switch's row:
"The arm switch stays ..."; OK's "Save now?" -> Save -> a refusal's box) has the word served INSIDE that box's wait: the REAL
JobsPageBack -> the REAL AdjGather asks the row's fields - the screen is showing PopupView, answers "" for each, and says page 41,
which IS the last page command's page: the box's-page check passes. "" -> 0, held to its range: the row's values are zeros.

(The tenth review's experiment, as reviewer B wrote it. THE CURES, each pinned by a pass of its own: (1) the word is NOT OBEYED
while a question waits - the handler's own lines are lifted out of src/main.cpp; (2) and were it obeyed (the second pass obeys it
whatever waits, as B210 did): NO PAGE BOX HAS AN ANSWER INSIDE A QUESTION (Nextion.h BoxesHaveNoPage) - the row is kept whole.)"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
MAINC = m.release(m.src('src/main.cpp'))
def word_body(word):
    """What src/main.cpp does when the page says `word`: the handler's own lines (to its ClearText), comments out."""
    i = MAINC.index('if (InStrng((char *)"%s", TextIn) > 0)' % word); j = MAINC.index('ClearText();', i)
    body = re.sub(r'//[^\n]*', '', MAINC[MAINC.index('{', i) + 1:j]).strip()
    if 'JobsPageBack();' not in body or '{' in body or '}' in body: raise SystemExit('the "ldrcadj" handler of main.cpp has changed its shape: ' + body)
    return body
ADJ, JOBS, RES = (m.release(m.src('include/' + f)) for f in ('RF_Adjust.h', 'RF_Jobs.h', 'RF_Rescue.h'))
def block(text, a, b): i = text.index(a); return text[i:text.index(b, i) + len(b)]
REAL = (m.lift(RES, 'FLASHMEM static long FieldNumber(') + 'enum { AK_SWITCH = 0, AK_KNOB = 1, AK_NUDGE = 2 };\nstatic const int ADJ_POS_MAX = 6;\n' + block(ADJ, 'struct AdjRow', '};') + '\n'
        + 'static AdjRow AdjRows[42]; static int AdjN = 0, AdjAt = 0; static bool AdjHave = false, Adj_Was_Edited = false, SwHave = false;\n'
        + 'static int AdjShownAt = -1;   // (RF_Adjust.h: the row whose boxes are on the screen - AdjShow sets it)\n'
        + m.lift(ADJ, 'FLASHMEM static int32_t AdjSwitchValue(') + m.lift(ADJ, 'FLASHMEM static void AdjGather()')
        + 'static void JobsHead(); static void JobsShow();\n'
        + JOBS[JOBS.index('static uint16_t JobsBarToken = 0;'):JOBS.index('FLASHMEM static void JobsBarOwn()')]   # (the eleventh review: the page is due until drawn - its variables, JobsIsDue, JobsDue)
        + m.lift(JOBS, 'FLASHMEM static void JobsBarOwn()') + m.lift(JOBS, 'FLASHMEM static bool JobsDrawDue()') + m.lift(JOBS, 'FLASHMEM static bool JobsDuePoll()')
        + m.lift(JOBS, 'FLASHMEM void JobsPageBack()')
        + m.lift(m.UTIL, 'bool GetSaveOrDiscard(char *goback, char *Prompt)'))
EXTRA = r'''
#include <cmath>
''' + REAL + r'''
static int pageBacks = 0, shows = 0, served = 0, backCalls = 0; static bool whateverWaits = false;
#define JobsPageBack() (++backCalls, JobsPageBack())   // (every call of the real one is counted: the handler's own lines, below, go through here)
static void JobsHead() { SendText((char *) "t11", (char *) "Goblin"); }
static void JobsShow()   // (RF_Adjust.h AdjShow's part that matters: a knob's two values into the boxes the keypad edits)
{
    ++shows; AdjShownAt = AdjAt; const AdjRow &r = AdjRows[AdjAt]; char b[16];
    snprintf(b, sizeof b, "%ld", (long) r.v[0]); SendText((char *) "tk0", b); snprintf(b, sizeof b, "%ld", (long) r.v[1]); SendText((char *) "tk1", b);
    JobsBarOwn();   // (as the real AdjShow and SwShow end their bar: the token, and the page is not due)
}
static void loopWithPoll(int ms) { for (int k = 0; k < ms; k += 25) { loopFor(25); if (CurrentView == ADJUSTVIEW) JobsDuePoll(); } }   // (the main loop with RF_Jobs.h JobsPoll's look at a due page)
static void asMainCpp() { ''' + word_body('ldrcadj') + r''' }                                  // (src/main.cpp's own lines for the word)
static bool myWords(const char *w)
{
    if (!strstr(w, "ldrcadj")) return false;
    ++pageBacks; const int g0 = screen.gets;
    if (whateverWaits) JobsPageBack(); else asMainCpp();                         // (whateverWaits: as B210 obeyed it - the second layer's pass)
    if (screen.gets != g0) ++served;
    return true;
}
static void addAdjust()
{
    Page a; a.id = 67; for (const char *t : { "tk0", "tk1", "t11" }) a.boxes[t] = { true, 0, "" };
    { const char *w = "ldrcadj"; a.loadPrint = std::vector<uint8_t>(w, w + strlen(w)); }   // (the card's page 67: postinitialize prints "ldrcadj")
    screen.pages["AdjustView"] = a; { Page pk; pk.id = 68; pk.boxes["list"] = { false, 3, "" }; screen.pages["AdjPickView"] = pk; }
    screen.pages0 = screen.pages;
    memset(AdjRows, 0, sizeof AdjRows); AdjN = 1; AdjAt = 0; AdjHave = true; SwHave = true; Adj_Was_Edited = false;
    AdjRows[0].kind = AK_KNOB; AdjRows[0].fn = 14; AdjRows[0].ch = 2; AdjRows[0].n = 2; AdjRows[0].lo = 988; AdjRows[0].hi = 2012; AdjRows[0].v[0] = 20; AdjRows[0].v[1] = 80;   // "Pitch P gain", a knob: 20 to 80
    pageBacks = 0; shows = 0; served = 0; backCalls = 0; wordHook = myWords;
}
static void openAdjust() { SendCommand((char *) "page AdjustView"); CurrentView = ADJUSTVIEW; JobsHead(); JobsShow(); }
'''
SCENES = r'''
  for (int pass = 0; pass < 2; ++pass)
  {
    whateverWaits = pass == 1;
    // (0) as it should be: the page opens, its word comes, the main loop serves it: the row is gathered from ITS page - 20 to 80
    more(); addAdjust(); openAdjust(); loopFor(600);
    say("P0. the page opened: 'ldrcadj' served %d time(s) by the main loop; the knob's values %ld to %ld; boxes lost %d\n", pageBacks, (long) AdjRows[0].v[0], (long) AdjRows[0].v[1], boxesLostTold);
    CHECK(pageBacks == 1 && served == 1 && AdjRows[0].v[0] == 20 && AdjRows[0].v[1] == 80);
    // (1) the picker's OK on the arm switch's row (RF_Jobs.h JobsPickOk -> JobsPickLeave -> RF_Switches.h SwPickApply): the page put back,
    //     its head and row drawn, and the box "The arm switch stays ..." - all in one button's work. The pilot presses the box's OK 3 s on.
    more(); addAdjust(); openAdjust(); loopFor(600); SendCommand((char *) "page AdjPickView"); CurrentView = 68; loopFor(600); pageBacks = 0; served = 0; backCalls = 0;
    { const int g0 = screen.gets, off0 = screen.offPageAnswers; tapAt(3000, "yes");
      SendCommand((char *) "page AdjustView"); CurrentView = ADJUSTVIEW; JobsHead(); JobsShow();                                      // JobsPickLeave
      MsgBox((char *) "page AdjustView", (char *) "The arm switch stays: Rotorflight needs it.\r\nAdd another job instead."); JobsHead(); JobsShow();   // SwPickApply's refusal
      const int inBox = pageBacks, servedInBox = served, callsInBox = backCalls, off1 = screen.offPageAnswers - off0; loopFor(1500);
      say("P1 (%s). the picker's OK, then the box 'The arm switch stays': 'ldrcadj' heard inside the box's wait %d time(s), its boxes asked there %d time(s); boxes asked %d, answered for boxes the SHOWING page has not got: %d;\n    the screen showed another page %d, boxes lost %d;  THE KNOB'S VALUES NOW %ld to %ld (they were 20 to 80); the page's boxes show '%s' to '%s'; edited flag %d; the word heard %d times in all, served %d\n",
          pass ? "the word obeyed whatever waits" : "as main.cpp has it", inBox, servedInBox, screen.gets - g0, screen.offPageAnswers - off0, offPage, (int) (BoxesLost != BoxesLostAtWork), (long) AdjRows[0].v[0], (long) AdjRows[0].v[1],
          screen.pages["AdjustView"].boxes["tk0"].txt.c_str(), screen.pages["AdjustView"].boxes["tk1"].txt.c_str(), (int) Adj_Was_Edited, pageBacks, served);
      CHECK(inBox >= 1);                                          // (the scene is the one meant: the word did come inside the box's wait)
      CHECK(AdjRows[0].v[0] == 20 && AdjRows[0].v[1] == 80);      // what should hold: the row is what the pilot typed
      CHECK(off1 == 0);                                           // ... and no box of the page was answered from the question's page
      if (!pass) CHECK(servedInBox == 0 && callsInBox == 0);      // (main.cpp: the word is not obeyed while a question waits - the page's routine is not even called)
      else CHECK(callsInBox >= 1 && servedInBox == 0);             // (the second layer by itself: called, and not one box asked from the question's page)
      CHECK(served >= 1 && !Adj_Was_Edited);                      // the box's way back put the page up again: its word again, served by the main loop - and nothing edited
      CHECK(screen.pages["AdjustView"].boxes["tk0"].txt == "20" && screen.pages["AdjustView"].boxes["tk1"].txt == "80"); }
    // (2) OK with unsaved edits: "... not saved. Save now?" - Save; the save is refused with a box (RF_Switches.h SaveSwitchActions: "The arm zone reaches 988 us ...")
    more(); addAdjust(); openAdjust(); loopFor(600); pageBacks = 0; served = 0; backCalls = 0;
    { const int off0 = screen.offPageAnswers; tapAt(1500, "yes"); tapAt(5000, "yes");
      AdjGather();                                                                                                                    // EndJobsView
      const bool save = GetSaveOrDiscard((char *) "page AdjustView", (char *) "The edited switches and knobs are not saved.\r\nSave now?");
      JobsHead(); JobsShow(); AdjGather();                                                                                            // JobsSaveNow, SaveJobs
      const long v0 = AdjRows[0].v[0], v1 = AdjRows[0].v[1];
      MsgBox((char *) "page AdjustView", (char *) "The arm zone reaches 988 us: the model\r\nwould arm with the safety ON. Move the\r\nleft end above 988."); JobsHead(); JobsShow();   // SaveSwitchActions' refusal
      loopFor(1500);
      say("P2 (%s). OK -> 'Save now?' -> Save (%d) -> the save's own gather read %ld to %ld -> a refusal's box: 'ldrcadj' heard %d time(s), served %d; answered for boxes the showing page has not got: %d;\n    THE KNOB'S VALUES NOW %ld to %ld; the page's boxes show '%s' to '%s'\n",
          pass ? "the word obeyed whatever waits" : "as main.cpp has it", (int) save, v0, v1, pageBacks, served, screen.offPageAnswers - off0, (long) AdjRows[0].v[0], (long) AdjRows[0].v[1], screen.pages["AdjustView"].boxes["tk0"].txt.c_str(), screen.pages["AdjustView"].boxes["tk1"].txt.c_str());
      CHECK(save && v0 == 20 && v1 == 80);
      CHECK(AdjRows[0].v[0] == 20 && AdjRows[0].v[1] == 80);
      CHECK(screen.offPageAnswers == off0); }
  }
  whateverWaits = false;
  // (3) THE PAGE COMES BACK AND IS NOT DRAWN - with no answer lost on the wire at all (the eleventh review, reviewer B's experiment 7). Back from Help or
  //     the screen saver nothing of this board's draws the page: it waits for the page's own word. A page more than a second and a half in coming up
  //     has its marker "late": the screen owes an answer, NOTHING is asked of it - and the word, which comes with the page, is served in exactly that
  //     state: every box of the gather has no answer. JobsPageBack went back with nothing done, and the page stayed as the card has it.
  //     Now the page is DUE, and the main loop draws it when the screen can be asked again (RF_Jobs.h JobsDuePoll) - the value typed taken first.
  for (int slow = 0; slow < 2; ++slow)
  {
    more(); addAdjust(); openAdjust(); loopFor(600);
    SendCommand((char *) "page BlankView"); CurrentView = 99; loopFor(900);                                       // the screen saver (or Help) takes the page away
    pageBacks = 0; shows = 0;
    screen.pages["AdjustView"].boxes["tk1"].txt = "95";                                                           // (a value he had typed, which no gather has taken yet)
    screen.loadUs = slow ? 1800000 : 250000;                                                                      // back: a quarter of a second in coming up - or 1.8 s
    SendCommand((char *) "page AdjustView"); CurrentView = ADJUSTVIEW;                                            // Utilities.h SaveOrRestoreScreen: the page command, and nothing drawn by this board
    loopWithPoll(6000); screen.loadUs = 90000;
    say("P3 (%s in coming up). its word 'ldrcadj' heard %d time(s); THE PAGE WAS DRAWN BY THIS BOARD %d time(s); due now %d; owed now %d; the knob's values %ld to %ld\n",
        slow ? "1.8 s" : "0.25 s", pageBacks, shows, (int) JobsIsDue(), (int) ScreenAnswerOwed, (long) AdjRows[0].v[0], (long) AdjRows[0].v[1]);
    CHECK(pageBacks >= 1);
    CHECK(shows >= 1 && !JobsIsDue());                                                                            // the page was drawn - by its word, or by the main loop after it
    CHECK(AdjRows[0].v[0] == 20 && AdjRows[0].v[1] == 95);                                                        // ... the typed value taken first, not written over
    CHECK(screen.pages["AdjustView"].boxes["tk1"].txt == "95");
  }
  // (4) ... and THE WORD NEVER COMES (on a field screen it can be cut by a line of the screen's other core): the main loop draws the page a second
  //     after it was put up
  {
    more(); addAdjust(); openAdjust(); loopFor(600);
    SendCommand((char *) "page BlankView"); CurrentView = 99; loopFor(900);
    screen.pages["AdjustView"].loadPrint.clear(); screen.pages0["AdjustView"].loadPrint.clear();                 // (the word lost)
    pageBacks = 0; shows = 0;
    SendCommand((char *) "page AdjustView"); CurrentView = ADJUSTVIEW;
    loopWithPoll(700); CHECK(shows == 0 && JobsIsDue());                                                          // (not yet: its own word may still come)
    loopWithPoll(1500);
    say("P4. the page back, its word never heard: drawn by the main loop %d time(s); due now %d\n", shows, (int) JobsIsDue());
    CHECK(pageBacks == 0 && shows == 1 && !JobsIsDue() && AdjRows[0].v[0] == 20 && AdjRows[0].v[1] == 80);
  }
  wordHook = nullptr;
'''
sys.exit(lib.build_run('pageback', SCENES, extra=EXTRA, more_defines=('ADJUSTVIEW',), sanitize=False))
