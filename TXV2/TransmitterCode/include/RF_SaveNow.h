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
bool RfSaveFirst(const char *page, const char *what, void (*save)(), void (*leave)(), bool *edited)
{ // true: Discard was chosen - the caller leaves now, as it did; false: the save runs, and closes the page when it has worked
    char q[160];
    snprintf(q, sizeof(q), "%s not saved.\r\nSave now?", what);
    if (!GetSaveOrDiscard((char *)page, q))
        return true;
    RfLeaveAfterSave = true;
    RfLeaveView = CurrentView;
    RfLeaveFn = leave;
    save();
    if (RfLeaveAfterSave && !*edited)
    { // (saved at once by a page that does not call RfSavedThenLeave: the backup file, a queued write)
        RfLeaveAfterSave = false;
        if (RfLeaveFn)
            RfLeaveFn();
    }
    return false;
}
#endif // RF_SAVENOW_H
