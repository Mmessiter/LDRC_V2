// B140: SWITCHES AND KNOBS - one page for what each channel of this transmitter makes the flight controller do.
//
// Rotorflight keeps these on two tabs: Modes (arm, rescue, self-level, the beeper, the black box ... : RF_Switches.h, MSP 34/35)
// and Adjustments (the bank and rates selectors, and a knob or switch that changes a setting in flight: RF_Adjust.h, MSP 52/53).
// Malcolm, 20 Oct 2026: "If selecting the channel/switch for banks selection is under switches on the app and under adjustments
// on the transmitter, many will find this confusing, including me! Do we need these two categories? Perhaps they can be
// combined into one?" - and, of "Switches and knobs": "I like your suggestion ... Let's do it."
//
// So: ONE page (AdjustView, 67, and its picker AdjPickView, 68 - the switches' pages 69 and 70 are no longer reached), one
// list of jobs - the switch jobs first, in slot order, then the selectors and knobs - one picker of everything ("What it
// does"), one Save that writes both tables, one OK. The two engines keep their tables and their MSP state machines
// (SwNow/SwShown and SwitchPoll; AdjRows and AdjustPoll); this layer walks them as one list (JobAt over SwN + AdjN rows) and
// routes every touch to the engine of the row showing. Opening reads the switches first (over the Bluetooth pipe, as ever),
// then the adjustments, which need the USB cable (Rotorflight will not send them over the receiver's lead): without it the
// page shows the switch jobs, says so, and the picker's selectors and knobs are refused with the same words.
//
// The row: "Does [Rescue - the safety net] [          ]" / "Switch on [Channel 8: AUX3]" for a switch job (the bar's one ON
// zone, the round ends to drag), and "Changes [Pitch P gain] [in bank 1]" / "Knob on [Channel 7: AUX2]" for a knob or a
// selector, exactly as the adjustments page drew them (ltn0 says Does or Changes). The title counts the jobs: "Job 3 of 12".
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_JOBS_H
#define RF_JOBS_H

static int JobAt = 0;                      // the row showing: 0 .. SwN-1 the switch jobs (SwShown order), then the adjustments (AdjRows order)
enum { JOBS_IDLE = 0, JOBS_READ_SW, JOBS_READ_ADJ, JOBS_SAVE_SW, JOBS_SAVE_ADJ };
static int JobsStep = JOBS_IDLE;           // the sequencer: a read or a save runs the switches' engine, then the adjustments'
static int JobsPickFor = 0;                // the picker: 0 = the row showing, 1 = a new job (Add)
static uint32_t JobsLiveMs = 0;
// B211 (the eleventh review, 15 Nov 2026): THE PAGE IS BACK ON THE SCREEN AND THIS BOARD HAS NOT DRAWN IT - AND THE BAR IS THE CARD'S.
// Whenever this page is loaded (opened; back from the keypad, the picker, a question, Help, the screen saver) the screen shows it as its
// card has it: the typed boxes keep their texts, but the bar is the card's - kind 0, its dividers at 1500 and 1700. The page says
// "ldrcadj" as it comes up, and JobsPageBack takes the typed values and draws the row and the bar again. B211 let JobsPageBack go back
// with nothing done when a box of its gather had no answer - and a page that is slow in coming up is served its word while the screen
// still owes an answer (no box has one); on a field screen the word itself can be cut by a line of the screen's other core. The bar
// stayed the card's; a touch on it was read as the row's own bar, and 1500 and 1700 became the knob's ends (or a switch's ON zone).
//  - THE BAR CARRIES THIS BOARD'S TOKEN: with every bar it draws, this board writes a number onto it ("bar.own": the screen keeps any
//    attribute written to its bar, and a page loaded afresh has none - 0). A touch on the bar asks for it first (JobsBarMoved): another
//    number, or no answer, and nothing of the bar is taken - the page is drawn instead (the values as typed first).
//  - THE PAGE IS DUE until this board has drawn it: after a page command of this board's that was not followed by a draw (the count of
//    page commands, as when the bar was last drawn), after a gather that lost a box, after a bar that was not ours. JobsPoll draws a due
//    page when the screen can be asked again - a few tries, a second apart - and ticks no live marker onto a page that is due.
static uint16_t JobsBarToken = 0;          // the number on the bar this board drew last (0: none drawn yet)
static uint16_t JobsDrawnAtMark = 0;       // Nextion.h ScreenMarkCount - the count of this board's page commands - when the bar was last drawn
static bool JobsPageDue = false;           // the page is not known to be as this board draws it (a gather lost a box, the bar was not ours)
static uint32_t JobsDueMs = 0;             // when the main loop first saw the page due, or last tried to draw it (0: not seen due)
static uint8_t JobsDueTries = 0;           // its tries so far
#define JOBS_DUE_TRIES 3
#define JOBS_DUE_EVERY_MS 1000
static bool JobsIsDue() { return JobsPageDue || JobsDrawnAtMark != ScreenMarkCount; }
static void JobsDue() { JobsPageDue = true; JobsDueMs = 0; }   // (the main loop's tries begin again)
FLASHMEM static void JobsBarOwn() // the row and its bar have just been drawn by this board (SwShow, AdjShow, JobsShow with no job)
{
    char c[24];
    JobsBarToken = ScreenCountAfter(JobsBarToken); // (never 0; the first from the clock: Utilities.h)
    snprintf(c, sizeof(c), "bar.own=%u", (unsigned)JobsBarToken);
    SendCommand(c);
    JobsDrawnAtMark = ScreenMarkCount;
    JobsPageDue = false;
}

// ---- the picker's rows (page 68's wheel, hmi/adjust_pages.py JOBS must agree): the two selectors, then the switch jobs
// (RF_Switches.h SwModes), then the settings in the adjustments' order (RF_Adjust.h AdjOrder: 5..25, 3, 4, 26..81)
static const int JOBS_PICK_SEL = 2;                           // 'Bank (Profile) selector', 'Rates selector'
static int JobsPickCount() { int n; AdjOrder(n); return JOBS_PICK_SEL + SW_MODES + (n - 2); }
// what wheel row idx means: true = a switch job (perm), false = an adjustment (fn); fn 0 / perm 255 = nothing
FLASHMEM static bool JobsPickAt(int idx, uint8_t &perm, uint8_t &fn)
{
    perm = 255; fn = 0;
    if (idx < 0) return false;
    if (idx == 0) { fn = 2; return false; }
    if (idx == 1) { fn = 1; return false; }
    if (idx < JOBS_PICK_SEL + SW_MODES) { perm = SwModes[idx - JOBS_PICK_SEL].id; return true; }
    int n; const uint8_t *seq = AdjOrder(n);
    const int k = idx - JOBS_PICK_SEL - SW_MODES + 2;         // (AdjOrder's rows 0 and 1 are the selectors)
    if (k >= 2 && k < n) fn = seq[k];
    return false;
}
FLASHMEM static int JobsPickIdxOfMode(uint8_t perm) { return JOBS_PICK_SEL + SwModeIdx(perm); }
FLASHMEM static int JobsPickIdxOfFn(uint8_t fn)
{
    if (fn == 2) return 0;
    if (fn == 1) return 1;
    const int k = AdjIdxOf(fn);                                // (0 for a setting not listed: the first selector then)
    return k < 2 ? 0 : JOBS_PICK_SEL + SW_MODES + (k - 2);
}

// ---- the list
static int  JobsN() { return SwN + (AdjHave ? AdjN : 0); }
static bool JobIsSw(int i) { return i < SwN; }
FLASHMEM static void JobsClamp() { const int n = JobsN(); if (JobAt >= n) JobAt = n ? n - 1 : 0; if (JobAt < 0) JobAt = 0; }
FLASHMEM static void JobsSync()  // the engines' own cursors from the row showing
{
    JobsClamp();
    if (JobIsSw(JobAt)) SwAt = JobAt;
    else if (AdjHave && AdjN) { AdjAt = JobAt - SwN; if (AdjAt < 0) AdjAt = 0; if (AdjAt >= AdjN) AdjAt = AdjN - 1; }
}
FLASHMEM static void JobsTitle()
{
    char b[48];
    const int n = JobsN();
    if (n) snprintf(b, sizeof(b), "Job %d of %d", JobAt + 1, n); else snprintf(b, sizeof(b), "No jobs yet");
    SendText((char *)"t0", b);
}
FLASHMEM static void JobsHead()
{
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)(AdjHave ? "USB cable" : "Bluetooth"));   // (the link the page reached the flight controller by)
    SendCommand((char *)((Sw_Was_Edited || Adj_Was_Edited) ? "vis b3,1" : "vis b3,0"));
}
FLASHMEM static void JobsNote(const char *msg, uint32_t ms) { AdjBusy(msg); AdjMsgUntil = millis() + ms; }
static const char *JOBS_NO_CABLE = "The selectors and knobs need the USB cable from the receiver to the flight controller: Rotorflight will not send them over the receiver's lead. The switch jobs are here.";
FLASHMEM static void JobsShow()
{
    JobsSync();
    AdjShownAt = -1;   // (B211: no adjustment's row is on the screen until AdjShow has put one there - RF_Adjust.h)
    if (!JobsN())
    {
        JobsTitle();
        SendText((char *)"ltn0", (char *)"Does");
        AdjText("tn0", (char *)"(none yet: press Add)"); AdjText("tn3", (char *)""); AdjVis("tn3", false); AdjText("tn2", (char *)""); AdjText("tn1", (char *)""); AdjText("tn8", (char *)""); AdjText("hint", (char *)"");
        SendCommand((char *)"bar.n=1"); SendCommand((char *)"bar.kind=0"); SendCommand((char *)"bar.mk=-1"); AdjText("bar", (char *)"");
        JobsBarOwn();   // (B211: the bar is this board's from here)
        return;
    }
    if (JobIsSw(JobAt)) SwShow(); else AdjShow();
    JobsTitle();
}
FLASHMEM static void JobsArrive() { JobsShow(); if (JobsN() && !JobIsSw(JobAt)) AdjAskNow(); }   // a row arrived at: a setting's present value is asked for
FLASHMEM static bool JobsDrawDue() // B211: a page that is due (above) - the values as typed, then the page. false: a box had no answer - nothing taken, nothing drawn, still due
{
    if (AdjHave) AdjGather();
    if (WorkLostABox()) return false;   // (still due: whoever calls this has said so - JobsDue, or the count of page commands)
    JobsHead(); JobsShow();
    return true;
}
// A present-value read (ADJ_NOW_*) is a nicety: anything the pilot does drops it rather than wait for it
static void JobsDropNowRead() { if (AdjStep_ == ADJ_NOW_STATUS || AdjStep_ == ADJ_NOW_READ) AdjStep_ = ADJ_IDLE; }
FLASHMEM static void JobsLive() { if (JobsStep != JOBS_IDLE || !JobsN()) return; if (JobIsSw(JobAt)) SwLive(); else AdjLive(); }

// ---- open, poll, save, OK
FLASHMEM void StartJobsView() // the menu's Switches & knobs ...
{
    char why[120];
    if (RfNeedsModel(why, sizeof(why)) || ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFView", why);
        return;
    }
    SendCommand((char *)"page AdjustView");
    CurrentView = ADJUSTVIEW;
    JobAt = 0; JobsPickFor = 0;
    Sw_Was_Edited = false; SwHave = false; SwN = 0; SwAt = 0; SwArmFrom = 0;
    AdjReset();
    JobsHead();
    JobsShow();
    JobsStep = JOBS_READ_SW;
    SwRead_();
}
FLASHMEM static void JobsSaved() // both tables written and read back: say so, and close the page if OK's "Save now?" asked for it
{
    JobsHead(); JobsShow();
    JobsNote("Saved, and read back the same.", 4000);
    RfSavedThenLeave(ADJUSTVIEW);
}
FLASHMEM static bool JobsDuePoll() // B211 (the eleventh review): THE PAGE IS DUE (above) - from the main loop, the page idle. true: due (drawn now, if the screen can be asked)
{
    if (!SwHave || !JobsIsDue()) { JobsDueMs = 0; return false; }   // (nothing read - the read failed, and its box left the page: there is nothing of this board's to draw; as JobsPageBack)
    if (!JobsDueMs) { JobsDueMs = millis() | 1; JobsDueTries = 0; }   // (first seen: its own word may yet draw it - JobsPageBack)
    else if (JobsDueTries < JOBS_DUE_TRIES && (int32_t)(millis() - JobsDueMs) >= JOBS_DUE_EVERY_MS && !BoxesHaveNoPage())   // (signed: "| 1" may be a millisecond AHEAD - unsigned, that read as 49 days gone, and the first try came at once)
    {
        ++JobsDueTries; JobsDueMs = millis() | 1;
        const uint32_t lost = BoxesLost;
        BoxesLostAtWork = BoxesLost;   // (the main loop's own work, counted as a button's is: Utilities.h CheckForNextionButtonPress - no question waits here)
        JobsDrawDue();
        if (BoxesLost != lost && JobsDueTries >= JOBS_DUE_TRIES) NoteBoxesLost();   // (the last try: said. The next touch of the page draws it)
    }
    return true;
}
FLASHMEM void JobsPoll()
{
    if (CurrentView != ADJUSTVIEW) { if (CurrentView != ADJPICKVIEW) JobsStep = JOBS_IDLE; return; }
    switch (JobsStep)
    {
    case JOBS_READ_SW:
        if (SwStep != SW_IDLE) return;
        if (!SwHave) { JobsStep = JOBS_IDLE; return; }        // (the read failed: SwFail said so and left the page)
        JobsHead(); JobsShow();
        JobsStep = JOBS_READ_ADJ;
        AdjRead();
        return;
    case JOBS_READ_ADJ:
        if (AdjStep_ != ADJ_IDLE) return;
        JobsStep = JOBS_IDLE;
        JobsHead(); JobsArrive();
        if (!AdjHave) JobsNote(JOBS_NO_CABLE, 8000);
        else if (AdjTakeNote[0]) JobsNote(AdjTakeNote, 8000);
        return;
    case JOBS_SAVE_SW:
        if (SwStep != SW_IDLE) return;
        if (Sw_Was_Edited) { JobsStep = JOBS_IDLE; JobsHead(); JobsShow(); return; }   // (refused or failed: the message box said why; the edits stand)
        if (AdjHave && Adj_Was_Edited) { JobsStep = JOBS_SAVE_ADJ; JobsDropNowRead(); SaveAdjustments(); if (AdjStep_ == ADJ_IDLE) { JobsStep = JOBS_IDLE; JobsHead(); JobsShow(); } return; }
        JobsStep = JOBS_IDLE;
        JobsSaved();
        return;
    case JOBS_SAVE_ADJ:
        if (AdjStep_ != ADJ_IDLE) return;
        JobsStep = JOBS_IDLE;
        if (Adj_Was_Edited) { JobsHead(); JobsShow(); return; }   // (failed: said)
        JobsSaved();
        return;
    default:
        if (JobsDuePoll()) return;   // (B211: the page is due - no live marker onto a page that is not drawn)
        if ((int32_t)(millis() - JobsLiveMs) >= 300) { JobsLiveMs = millis(); JobsLive(); }
        return;
    }
}
FLASHMEM void SaveJobs() // Save: the switch jobs that changed, then the selectors and knobs that changed
{
    if (JobsStep != JOBS_IDLE || (SwStep != SW_IDLE) || (AdjStep_ != ADJ_IDLE && AdjStep_ != ADJ_NOW_STATUS && AdjStep_ != ADJ_NOW_READ)) return;
    if (!Sw_Was_Edited && !Adj_Was_Edited) return;
    JobsDropNowRead();
    if (AdjHave) AdjGather();
    if (WorkLostABox()) return; // B211: a box had no answer - nothing was taken, nothing is done (Nextion.h, A PAGE'S FIELDS ARE TAKEN WHOLE)
    if (Sw_Was_Edited)
    {
        JobsStep = JOBS_SAVE_SW;
        SaveSwitchActions();
        if (SwStep == SW_IDLE) { JobsStep = JOBS_IDLE; JobsHead(); JobsShow(); }   // (refused: the message box said why)
        return;
    }
    JobsStep = JOBS_SAVE_ADJ;
    SaveAdjustments();
    if (AdjStep_ == ADJ_IDLE) { JobsStep = JOBS_IDLE; JobsHead(); JobsShow(); }   // (refused: the message box said why)
}
static bool JobsEditedFlag = false;        // for RfSaveFirst: either table edited
FLASHMEM static void JobsSaveNow() { JobsHead(); JobsShow(); SaveJobs(); }   // (OK's "Save now?": the edits shown again, then saved)
FLASHMEM void EndJobsView() // OK
{
    if (JobsStep != JOBS_IDLE) return;
    if (AdjStep_ != ADJ_IDLE && AdjStep_ != ADJ_NOW_STATUS && AdjStep_ != ADJ_NOW_READ) return;
    JobsEditedFlag = Sw_Was_Edited || Adj_Was_Edited;
    if (JobsEditedFlag)
    {
        if (AdjHave) AdjGather();
        if (WorkLostABox()) return; // B211: a box had no answer - nothing was taken, nothing is done (Nextion.h, A PAGE'S FIELDS ARE TAKEN WHOLE)
        if (!RfSaveFirst("page AdjustView", "The edited switches and knobs are", JobsSaveNow, EndJobsView, &JobsEditedFlag)) return;   // B102
    }
    Sw_Was_Edited = false; Adj_Was_Edited = false; AdjStep_ = ADJ_IDLE;
    AdjModelRevert();   // (B141: Discard, or nothing to save: a bank channel spaced on this visit goes back as the card has it)
    RotorFlightStart();
}
FLASHMEM void JobsPageBack() // the page is back on the screen (its postinitialize prints "ldrcadj"): the values as typed, the bar again
{
    if (CurrentView != ADJUSTVIEW || !SwHave) return;
    JobsDue();       // (B211, the eleventh review: loaded afresh - the bar is the card's until this board has drawn it; THE PAGE IS DUE, above)
    JobsDrawDue();   // (a box with no answer: nothing was taken, nothing drawn - it stays due, and JobsPoll draws it when the screen can be asked)
}

// ---- the arrows, the boxes, the bar
FLASHMEM static void JobsMove(int to)
{
    if (!JobsN()) return;
    JobsDropNowRead();
    if (AdjHave) AdjGather();
    if (WorkLostABox()) return; // B211: a box had no answer - nothing was taken, nothing is done (Nextion.h, A PAGE'S FIELDS ARE TAKEN WHOLE)
    JobAt = to;
    JobsArrive();
}
FLASHMEM void JobsPrevious() { JobsMove(JobAt - 1); }
FLASHMEM void JobsNext() { JobsMove(JobAt + 1); }
FLASHMEM void JobsChannelTapped()
{
    if (!JobsN() || JobsStep != JOBS_IDLE) return;
    JobsDropNowRead();
    if (JobIsSw(JobAt)) { JobsSync(); SwitchChannelTapped(); }
    else AdjustChannelNext();
    JobsHead(); JobsTitle();
}
FLASHMEM void JobsKindTapped()
{
    if (!JobsN() || JobsStep != JOBS_IDLE) return;
    if (JobIsSw(JobAt)) { JobsNote("A switch job has one ON zone: drag the round ends to set where the switch turns it on.", 4000); return; }
    JobsDropNowRead();
    AdjustKindTapped();
    JobsHead(); JobsTitle();
}
FLASHMEM void JobsBankTapped()
{
    if (!JobsN() || JobsStep != JOBS_IDLE || JobIsSw(JobAt)) return;
    JobsDropNowRead();
    AdjustBankTapped();
    JobsHead(); JobsTitle();
}
FLASHMEM void JobsBarMoved()
{
    if (!JobsN() || JobsStep != JOBS_IDLE) return;
    JobsDropNowRead();
    if (!JobsIsDue())
    { // B211 (the eleventh review): THE BAR CARRIES THIS BOARD'S TOKEN (above) - or it is not the bar this board drew, and nothing of it is taken
        const int own = GetOtherValue((char *)"bar.own");
        if (WorkLostABox() || !JobsBarToken || own != (int)JobsBarToken) JobsDue();
    }
    if (JobsIsDue())
    { // the page is drawn first (the values as typed, then the row and its bar): this touch took nothing. With no answer from the screen, later (JobsPoll)
        if (!WorkLostABox()) JobsDrawDue();
        return;
    }
    if (JobIsSw(JobAt)) { JobsSync(); SwitchBarMoved(); }
    else AdjustBarMoved();
    if (WorkLostABox()) { JobsDue(); return; }   // (a box of the bar had no answer: nothing was taken - and what the bar shows now is drawn again as it is in hand)
    JobsHead(); JobsTitle();
}
FLASHMEM void JobsRemove()
{
    if (!JobsN() || JobsStep != JOBS_IDLE) return;
    JobsDropNowRead();
    if (JobIsSw(JobAt)) { JobsSync(); SwitchRemove(); }
    else { AdjustRemove(); JobAt = SwN + AdjAt; }
    JobsClamp(); JobsHead(); JobsArrive();
}
FLASHMEM void JobsWasEdited() { if (AdjHave && !JobIsSw(JobAt)) AdjEdited(); }   // a number typed in a knob's or switch's box (the keypad)

// ---- the picker (page 68): the row's own job, or a new one
FLASHMEM static void JobsOpenPicker(int at)
{
    SendCommand((char *)"page AdjPickView");
    CurrentView = ADJPICKVIEW;
    SendText((char *)"t11", ModelName);
    SendValue((char *)"list", at);
}
FLASHMEM static void JobsPickLeave()
{
    SendCommand((char *)"page AdjustView");
    CurrentView = ADJUSTVIEW;
    JobsHead(); JobsShow();
}
FLASHMEM void JobsSettingTapped() // the job box: the picker, on the row's own job
{
    if (!JobsN() || JobsStep != JOBS_IDLE) return;
    JobsDropNowRead();
    if (AdjStep_ != ADJ_IDLE) return;
    if (AdjHave) AdjGather();
    if (WorkLostABox()) return; // B211: a box had no answer - nothing was taken, nothing is done (Nextion.h, A PAGE'S FIELDS ARE TAKEN WHOLE)
    JobsPickFor = 0;
    JobsSync();
    JobsOpenPicker(JobIsSw(JobAt) ? JobsPickIdxOfMode(SwNow[SwShown[SwAt]].perm) : JobsPickIdxOfFn(AdjRows[AdjAt].fn));
}
FLASHMEM void JobsAdd() // Add: choose what the new job does first (the picker, from the top), then the row is made for it
{
    if (!SwHave || JobsStep != JOBS_IDLE) return;
    JobsDropNowRead();
    if (AdjStep_ != ADJ_IDLE) return;
    if (AdjHave) AdjGather();
    if (WorkLostABox()) return; // B211: a box had no answer - nothing was taken, nothing is done (Nextion.h, A PAGE'S FIELDS ARE TAKEN WHOLE)
    JobsPickFor = 1;
    JobsOpenPicker(0);
}
FLASHMEM void JobsPickCancel() { JobsPickLeave(); }
FLASHMEM void JobsPickOk()
{
    const uint32_t raw = GetValue((char *)"list");
    const int idx = raw < 65535u ? (int)raw : -1;
    uint8_t perm, fn;
    const bool isSw = JobsPickAt(idx, perm, fn);
    JobsPickLeave();
    if (idx < 0 || idx >= JobsPickCount()) return;                     // (nothing the screen could give: the row stays)
    if (!isSw && !AdjHave) { JobsNote(JOBS_NO_CABLE, 8000); return; }  // (no USB cable: no selectors, no knobs)
    const int ch = JobsN() ? (JobIsSw(JobAt) ? SwNow[SwShown[SwAt]].aux : AdjRows[AdjAt].ch) : 0;   // the channel of the job showing (AUX index)
    if (JobsPickFor == 1)
    { // a new job: on the channel after the one showing (the arm job takes the arming channel)
        const int next = JobsN() ? (ch + 1) % (CHANNELSUSED - 5) : 1;
        if (isSw) { if (!SwPickApply(perm, true, next)) return; JobAt = SwAt; }
        else { if (!AdjAddWith(fn, next)) return; JobAt = SwN + AdjAt; }
        JobsHead(); JobsShow();
        return;
    }
    // the row showing changes its job
    if (!JobsN()) return;
    if (JobIsSw(JobAt) && isSw) { JobsSync(); if (perm != SwNow[SwShown[SwAt]].perm) SwPickApply(perm, false, ch); }
    else if (!JobIsSw(JobAt) && !isSw) { JobsSync(); if (fn != AdjRows[AdjAt].fn) AdjPickApply(fn); }
    else
    { // a switch job becoming a knob, or a knob becoming a switch job: the old row goes (the arm switch stays), the new one takes its channel
        JobsSync();
        if (JobIsSw(JobAt))
        {
            if (SwNow[SwShown[SwAt]].perm == 0) { MsgBox((char *)"page AdjustView", (char *)"The arm switch stays: Rotorflight needs it.\r\nAdd another job instead."); JobsHead(); JobsShow(); return; }
            SwDropAt(SwAt);
            if (!AdjAddWith(fn, ch)) { JobsClamp(); JobsHead(); JobsShow(); return; }
            JobAt = SwN + AdjAt;
        }
        else
        {
            AdjDropAt(AdjAt);
            if (!SwPickApply(perm, true, ch)) { JobsClamp(); JobsHead(); JobsShow(); return; }
            JobAt = SwAt;
        }
    }
    JobsHead(); JobsShow();
}
#endif
