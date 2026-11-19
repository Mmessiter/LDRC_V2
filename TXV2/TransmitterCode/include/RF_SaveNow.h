// B102: OK'S "SAVE NOW?" (Malcolm, 15 Oct 2026: "If a user forgets to hit save and instead hits OK, I think the message box,
// which already recognises unsaved edits, should offer the option save now? To save clicks."). Each Rotorflight page's OK
// with unsaved edits calls RfSaveFirst: Save saves, and the page closes once the save has worked (the page's save calls
// RfSavedThenLeave where it says "Saved"); Discard leaves without saving, as the old question's OK did. A refusal or a
// failure (any message box), or a No to the save's own question, keeps the page open with its edits (Utilities.h MsgBox and
// GetConfirmation clear RfLeaveAfterSave; so does the Rotorflight page, RotorFlightStart). Needs: CurrentView,
// RfLeaveAfterSave, RfLeaveView, RfLeaveFn (1Definitions.h) and GetSaveOrDiscard (Utilities.h) - in the host tests, theirs.
#ifndef RF_SAVENOW_H
#define RF_SAVENOW_H
void RfSavedThenLeave(int view) // a page's save has worked: if OK's "Save now?" asked for it, the page closes
{
    (void)view;
    if (!RfLeaveAfterSave || CurrentView != RfLeaveView)
        return;
    RfLeaveAfterSave = false;
    if (RfLeaveFn)
        RfLeaveFn();
}
// B211 (the sixteenth review; released code): WHAT A SAVE'S FAILURE SAYS IS WHAT STANDS IN THE FLIGHT CONTROLLER. A page's save is several writes and
// a store, each a step of its poll. "Not written (an input)" was said with the mixer block and the first input already in the flight controller's
// memory - not stored: the model flew so until its next restart, and nothing said so. Now every write step BEHIND a page's first says "PART WRITTEN,
// NOT STORED (... failed) - try again, or switch the model off and on", and every store step "Written, but NOT STORED - try again, or ...". (A
// page's FIRST write refused is still "Not written": nothing of the save stands there.) The words only: no step does anything else than it did.
// (The seventeenth review.) "NO ANSWER" AT A WRITE OR STORE STEP OF A SAVE: this write may have landed or not - and the ones before it have. One of the two
// things a save meets when the safety goes off under it (the screen clears its queue). At any other step: "No answer", as ever.
#define RF_NO_ANSWER_SAVING "No answer - PART MAY BE WRITTEN, NOT STORED: try again, or switch the model off and on"
static inline const char *RfNoAnswerWords(bool savingStep) { return savingStep ? RF_NO_ANSWER_SAVING : "No answer"; }
bool RfSaveFirst(const char *page, const char *what, void (*save)(), void (*leave)(), bool *edited)
{ // true: Discard was chosen - the caller leaves now, as it did; false: the save runs, and closes the page when it has worked
    char q[160];
    snprintf(q, sizeof(q), "%s not saved.\r\nSave now?", what);
    if (!GetSaveOrDiscard((char *)page, q))
        return !QuestionClosedItself; // B211 (the ninth review): Discard was CHOSEN. A question that this board closed by itself (the screen restarted, stopped
                                      // answering, another page came over it) is not the pilot's "Discard": nothing is saved, nothing thrown away, the page stays
    RfLeaveAfterSave = true;
    RfLeaveView = CurrentView;
    RfLeaveFn = leave;
    const uint32_t lost = BoxesLost; // (its own count: what the save's gather loses, not what stood before it)
    save();
    if (BoxesLost != lost)
        RfLeaveAfterSave = false; // B211 (the twelfth review): the save stopped on a box with no answer and put up no box of its own (the Easy page, the knobs
                                  // page): nothing was saved, the page stays - and "close when saved" does not wait on for some LATER Save to close it
    if (RfLeaveAfterSave && !*edited)
    { // (saved at once by a page that does not call RfSavedThenLeave: the backup file, a queued write)
        RfLeaveAfterSave = false;
        if (RfLeaveFn)
            RfLeaveFn();
    }
    return false;
}
// B211 (the fifteenth review; released code): A PAGE WHOSE READ FAILED IS LEFT - as the switches page has always been (RF_Switches.h SwFail). Basics,
// Filters, Travel, Rescue and Servos stayed up, with the numbers of the read BEFORE still in hand and Save open on them - another model's, another
// bank's, an edit he had discarded: Save wrote those into this flight controller, "Saved, and read back the same.". Each of the five now forgets what
// it has as a read begins (BasHave, FltHave, TravHave, RescueHave, ServoHave), and its failure routine comes here while nothing is in hand.
// True: the page was left - the menu is up (or the guide it was opened from), or another page came over the box and stands. False: the menu would
// not open (RotorFlightStart: the motor switch on, the safety off) - the caller puts its own page up again, empty: nothing can be saved from it.
// (The sixteenth review.) THE LINE THAT STANDS ON A PAGE THAT COULD NOT BE LEFT: the menu does not open with the motor on or the safety off
// (RotorFlightStart - without a word when a model is connected), which is the one way to stay here. It said "Press OK." - where OK does nothing.
#define RF_NOT_READ_LINE "NOT READ. Safety on, motor off - then OK."
// ... and the line of a SAVE that failed on the quiet road (no box: the model may fly) - on the page for six seconds; the log has the reason
#define RF_NOT_SAVED_LINE "NOT CONFIRMED. Safety on, then Save again."   // (the eighteenth review: it said "NOT SAVED." behind a failure of the read-back too - all written and stored)
// The menu from a page's OK: a page with nothing in hand could not be read - the guide does not tick its step (the seventeenth review: the flag was up
// only round the call inside RfLeaveNotRead; OK on the page that STOOD "NOT READ" ticked it).
void RotorFlightStart();
extern bool RfHomeNotRead;
inline void RfMenuFromPage(bool have)
{
    RfHomeNotRead = !have;
    RotorFlightStart();
    RfHomeNotRead = false;
}
// ... AND NO BOX THAT WAITS WHILE THE MODEL MAY FLY (the safety off; with none, the motor on; the flight controller armed - PipeHttp.h RfMayFly): a
// box's wait reads no switch. Then the reason is a line in the log, and the page stands under its line - the menu would not open either.
static bool RfMayFly();
static void RfSayQuietly(const char *why);
bool RfLeaveNotRead(char *msg)
{
    const uint8_t was = CurrentView;
    if (RfMayFly())
    {
        RfSayQuietly(msg);
        return false;
    }
    MsgBox((char *)"page RFView", msg);
    if (QuestionOvertaken)
        return true; // (another page was put up over the box: no menu over that page)
    RfHomeNotRead = true; // (RF_Tools.h RfHomeBack: back to the guide it was opened from - with its step NOT ticked)
    RotorFlightStart();
    RfHomeNotRead = false;
    return CurrentView != was || QuestionOvertaken; // (... nor this page over one that came over RotorFlightStart's own box)
}
#endif // RF_SAVENOW_H
