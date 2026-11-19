// B50: Rotorflight's Rescue, on the transmitter (two pages: RescueView, Rescue2View on the screen's card, made by the
// screen project's hmi/rescue_pages.py). The bytes are Rotorflight 2.3's rescue profile (MSP 146 read, 147 write, 28
// bytes, one per PID bank), as the receiver's own rescue page reads them (RXV2 data/rotorflight-rescue.html): the
// transmitter asks the receiver's raw Rotorflight line through the screen's Bluetooth pipe (PipeHttp.h) and does the
// thinking here. A read: select the bank (210), read (146), show. A save: the fields as typed, select, write (147),
// store (250), select, read back, compare.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_RESCUE_H
#define RF_RESCUE_H

static const int RESCUE_BYTES = 28;
static uint8_t RescueRaw[RESCUE_BYTES];    // as last read
static bool RescueHave = false;
static bool Rescue_Was_Edited = false;
static int RescueMode = 0, RescueFlip = 0; // the two choices (the rest live in the page's fields)
enum
{
    RSC_IDLE = 0,
    RSC_SELECT,     // 210 before a read
    RSC_READ,       // 146
    RSC_W_SELECT,   // 210 before a write
    RSC_WRITE,      // 147
    RSC_STORE,      // 250
    RSC_V_SELECT,   // 210 before the read-back
    RSC_VERIFY      // 146 again (B51: a step of its own; B50 took the select's empty answer for the read-back and showed the old values)
};
static int RescueStep = RSC_IDLE, RescueReq = 0;
// B211 (the sixteenth review; released code): THE BANK SWITCH IS HELD WHILE A SAVE RUNS - from the select that begins it to its read-back's end.
// Nothing held it: the save chooses the bank (MSP 210) and writes behind it (147), each step from the poll - and a bank switch that moved in between
// took the flight controller to the other bank: bank 1's values were written into bank 2, stored, and read back "the same"; bank 1 was not written.
// (Moved while "Save now?" waited, or while the Save button gathered its boxes - no switch is read there, the main loop saw it a moment behind the
// select - or while the save ran.) Held as the PIDs' and Easy tuning's pages hold it (Switches.h ReadBankSwitch): the bank's channel stays where it
// was, the save lands in the bank the page shows, and the switch is read again when the save has ended - the new bank is then read, as at any change.
// It cannot outlast the page (the poll ends the step when the page goes; no answer ends it in nine seconds - PipeHttp.h PipeReplyLate).
bool RescueHoldsBanks() { return RescueStep >= RSC_W_SELECT && RescueStep <= RSC_VERIFY && (CurrentView == RESCUEVIEW || CurrentView == RESCUE2VIEW); }
static uint32_t RescueMsgUntil = 0;        // a message shown over the fields goes by itself
static uint8_t RescueWant[RESCUE_BYTES];   // what a save asked for

static const char *RescueModeWords[3] = {"Off", "Level & climb", "Level & hold height"};   // the mode on the height page (15 Oct: the phone app's words); page 1's "Enable rescue" is Off / On

FLASHMEM static uint16_t RdU16(const uint8_t *b, int o) { return (uint16_t)(b[o] | (b[o + 1] << 8)); }
FLASHMEM static void WrU16(uint8_t *b, int o, long v)
{
    if (v < 0)
        v = 0;
    if (v > 65535)
        v = 65535;
    b[o] = (uint8_t)(v & 0xFF);
    b[o + 1] = (uint8_t)(v >> 8);
}
FLASHMEM static void RescueBusy(const char *msg)
{
    SendCommand((char *)(msg && *msg ? "vis busy,1" : "vis busy,0"));
    if (msg && *msg)
        SendText((char *)"busy", (char *)msg);
}
FLASHMEM static void RescueField(const char *name, const char *text) { SendText((char *)name, (char *)text); }
FLASHMEM static void RescueNumber(const char *name, long v)
{
    char b[16];
    snprintf(b, sizeof(b), "%ld", v);
    RescueField(name, b);
}
FLASHMEM static void RescueTenths(const char *name, int tenths)
{
    char b[16];
    snprintf(b, sizeof(b), "%d.%d", tenths / 10, tenths % 10);
    RescueField(name, b);
}
FLASHMEM static void RescuePercent(const char *name, int tenths) // a collective of 0..1000 as the configurator shows it: 450 = 45, 655 = 65.5
{
    char b[16];
    if (tenths % 10) snprintf(b, sizeof(b), "%d.%d", tenths / 10, tenths % 10); else snprintf(b, sizeof(b), "%d", tenths / 10);
    RescueField(name, b);
}
// The page's fields from the bytes (page 1: RescueView; page 2: Rescue2View)
FLASHMEM static void RescueShowPage1()
{
    RescueMode = RescueWant[0] <= 2 ? RescueWant[0] : 0;
    RescueFlip = RescueWant[1] ? 1 : 0;
    SendValue((char *)"tn0", RescueMode ? 1 : 0);   // (B65: a switch)
    SendValue((char *)"tn1", RescueFlip ? 1 : 0);   // (B65: a switch)
    RescuePercent("tn2", RdU16(RescueWant, 8));   // Pull-up Collective [%]
    RescueTenths("tn3", RescueWant[4]);           // Pull-up Time [s]
    RescuePercent("tn4", RdU16(RescueWant, 10));  // Climb Collective [%]
    RescueTenths("tn5", RescueWant[5]);           // Climb Time [s]
    RescuePercent("tn6", RdU16(RescueWant, 12));  // Hover Collective [%]
    RescueTenths("tn7", RescueWant[6]);           // Flip Fail Time [s]
    RescueTenths("tn8", RescueWant[7]);           // Exit Time [s]
    RescueNumber("tn9", RescueWant[3]);           // Leveling Gain
    RescueNumber("tn10", RescueWant[2]);          // Flip-to-Upright Gain
    RescueNumber("tn11", RdU16(RescueWant, 24));  // Max Levelling Rate
    RescueNumber("tn12", RdU16(RescueWant, 26));  // Max Leveling Acceleration
}
FLASHMEM static void RescueShowPage2()
{
    char b[16];
    RescueMode = RescueWant[0] <= 2 ? RescueWant[0] : 0;
    RescueField("tn0", RescueModeWords[RescueMode]);
    const unsigned h = RdU16(RescueWant, 14);
    snprintf(b, sizeof(b), "%u.%02u", h / 100, h % 100);
    RescueField("tn1", b);                       // Hover height [m]
    RescueNumber("tn2", RdU16(RescueWant, 16));   // Height hold P
    RescueNumber("tn3", RdU16(RescueWant, 18));   // I
    RescueNumber("tn4", RdU16(RescueWant, 20));   // D
    RescuePercent("tn5", RdU16(RescueWant, 22));  // Max Collective [%]
}
FLASHMEM static void RescueShow()
{
    if (RfKeepTyped)
    { // B211 (the fourteenth review): THE NUMBERS TYPED ARE THE PILOT'S until Save takes them - none is drawn, and what is in hand is not put back to
      // what the last gather had (a switch tapped while a save ran was undone). The fifteenth review: THE PARTS THAT TURN BY THEMSELVES ARE WRITTEN
      // AS THEY ARE IN HAND - the two switches, page 2's word. Nothing at all was drawn: a switch tapped as the failure's box came up - its tap not
      // obeyed, its page gone - stayed turned on the screen and not in hand, and "Save again" wrote "rescue off" under a switch that showed ON.
        if (CurrentView == RESCUEVIEW)
        {
            SendValue((char *)"tn0", RescueMode ? 1 : 0);
            SendValue((char *)"tn1", RescueFlip ? 1 : 0);
        }
        else if (CurrentView == RESCUE2VIEW)
            RescueField("tn0", RescueModeWords[RescueMode <= 2 ? RescueMode : 0]);
        return;
    }
    if (CurrentView == RESCUEVIEW)
        RescueShowPage1();
    else if (CurrentView == RESCUE2VIEW)
        RescueShowPage2();
}
FLASHMEM static long FieldNumber(const char *name, long lo, long hi) // a field as typed, clamped
{
    char t[24] = "";
    GetText((char *)name, t, sizeof(t) - 1);
    TextMustBeNumber(name, t); // B211: A NUMBER FIELD'S TEXT THAT IS NO NUMBER IS NO ANSWER (Nextion.h)
    long v = strtol(t, nullptr, 10);
    return v < lo ? lo : v > hi ? hi : v;
}
FLASHMEM static int FieldTenths(const char *name, int lo, int hi) // "1.5" -> 15
{
    char t[24] = "";
    GetText((char *)name, t, sizeof(t) - 1);
    TextMustBeNumber(name, t); // B211: A NUMBER FIELD'S TEXT THAT IS NO NUMBER IS NO ANSWER (Nextion.h)
    const float f = (float)atof(t);
    int v = (int)(f * 10.0f + (f >= 0 ? 0.5f : -0.5f));
    return v < lo ? lo : v > hi ? hi : v;
}
// The bytes to write: the page's fields over the last read (the other page's values stay as read, or as edited there)
FLASHMEM static int FieldPercent(const char *name, int lo, int hi) // "45" or "65.5" -> 450 / 655
{
    return FieldTenths(name, lo, hi);
}
FLASHMEM static void RescueGatherPage1()
{
    KEEP_WHOLE(want, RescueWant); // B211: whole, or not at all (Nextion.h, A PAGE'S FIELDS ARE TAKEN WHOLE)
    RescueWant[0] = (uint8_t)RescueMode;
    RescueWant[1] = (uint8_t)RescueFlip;
    WrU16(RescueWant, 8, FieldPercent("tn2", 0, 1000));
    RescueWant[4] = (uint8_t)FieldTenths("tn3", 0, 250);
    WrU16(RescueWant, 10, FieldPercent("tn4", 0, 1000));
    RescueWant[5] = (uint8_t)FieldTenths("tn5", 0, 250);
    WrU16(RescueWant, 12, FieldPercent("tn6", 0, 1000));
    RescueWant[6] = (uint8_t)FieldTenths("tn7", 0, 250);
    RescueWant[7] = (uint8_t)FieldTenths("tn8", 0, 250);
    RescueWant[3] = (uint8_t)FieldNumber("tn9", 5, 250);
    RescueWant[2] = (uint8_t)FieldNumber("tn10", 5, 250);
    WrU16(RescueWant, 24, FieldNumber("tn11", 1, 1000));
    WrU16(RescueWant, 26, FieldNumber("tn12", 1, 10000));
}
FLASHMEM static void RescueGatherPage2()
{
    KEEP_WHOLE(want, RescueWant); // B211: whole, or not at all (Nextion.h, A PAGE'S FIELDS ARE TAKEN WHOLE)
    RescueWant[0] = (uint8_t)RescueMode;
    char t[24] = "";
    GetText((char *)"tn1", t, sizeof(t) - 1);
    TextMustBeNumber("tn1", t); // B211: A NUMBER FIELD'S TEXT THAT IS NO NUMBER IS NO ANSWER (Nextion.h)
    float h = (float)atof(t);
    if (h < 0)
        h = 0;
    if (h > 500)
        h = 500;
    WrU16(RescueWant, 14, (long)(h * 100.0f + 0.5f));
    WrU16(RescueWant, 16, FieldNumber("tn2", 0, 10000));
    WrU16(RescueWant, 18, FieldNumber("tn3", 0, 10000));
    WrU16(RescueWant, 20, FieldNumber("tn4", 0, 10000));
    WrU16(RescueWant, 22, FieldPercent("tn5", 10, 1000));
}
FLASHMEM static void RescueAskSelect(int next)
{
    uint8_t b = (uint8_t)(Bank >= 1 && Bank <= 6 ? Bank - 1 : 0);
    RescueReq = MspAsk(210, &b, 1);
    RescueStep = next;
}
static void RescueRead();
FLASHMEM static void RescueFail(const char *what) // B54 (Malcolm: "the error banners should look more like message boxes"): a message box, with the whole of the receiver's words
{
    char msg[180];
    snprintf(msg, sizeof(msg), "%s:\r\n%.140s", what, PipeRepCode ? PipeRepBody : "the screen could not ask (no Bluetooth)");
    RescueStep = RSC_IDLE;
    RescueBusy("");
    PlaySound(WHAHWHAHMSG);
    if (!RescueHave)
    { // B211 (the fifteenth review; released code): THE READ FAILED - THE PAGE IS LEFT (RF_SaveNow.h RfLeaveNotRead says why). Here it was another
      // BANK's numbers as well: the bank switch moved, the new bank's read failed, and the page said "Bank 2" over bank 1's values with Save open.
        if (!RfLeaveNotRead(msg))
        {
            char b[16];
            snprintf(b, sizeof(b), "Bank %d", Bank);
            SendCommand((char *)(CurrentView == RESCUE2VIEW ? "page Rescue2View" : "page RescueView"));
            SendText((char *)"t11", ModelName);
            SendText((char *)"t9", b);
            SendCommand((char *)"vis b3,0");
            RescueBusy(RF_NOT_READ_LINE); // (a standing line: whatever the screen still shows there is not in hand)
        }
        return;
    }
    const bool quiet = RfMayFly(); // (the seventeenth review: on the quiet road the page itself says that the save failed - below)
    RfBoxOrQuiet((CurrentView == RESCUE2VIEW ? "page Rescue2View" : "page RescueView"), msg); // (the sixteenth review: no box that waits while the model may fly - PipeHttp.h; then a line in the log)
    SendText((char *)"t11", ModelName);
    SendCommand((char *)(Rescue_Was_Edited ? "vis b3,1" : "vis b3,0"));
    RfKeepTyped = true; // B211 (the fourteenth review): the page came back from the box AS THE SCREEN HAS IT - a save runs for seconds, and what he typed
    RescueShow();       // meanwhile was drawn over with what the save had gathered ("Save again" then wrote the earlier numbers)
    RfKeepTyped = false;
    if (quiet)
    {
        RescueBusy(RF_NOT_SAVED_LINE);
        RescueMsgUntil = millis() + 6000;
    }
}
static bool RescueRereadWanted = false;    // B54: the bank switch moved while a read or a save was under way
static uint32_t RescueRereadAt = 0;        // B79: ... and not before this moment
FLASHMEM void RescueBankChanged()                   // from BankHasChanged (Switches.h): the values of the new bank, the edits of the old one let go
{
    if (CurrentView != RESCUEVIEW && CurrentView != RESCUE2VIEW)
        return;
    char b[16];
    snprintf(b, sizeof(b), "Bank %d", Bank);
    SendText((char *)"t9", b);
    if (Rescue_Was_Edited) // B56 (Malcolm): the warning the other pages give, "too late now"
    {
        char NB[10];
        char Wmsg[120];
        strcpy(Wmsg, "Rescue values");
        if (PreviousBank >= 1 && PreviousBank <= BANKS_USED)
        { // (B211: only a bank is named - the motor switch's forced "254" was said here: "Rescue values for Bank 254 were edited")
            strcat(Wmsg, " for Bank ");
            strcat(Wmsg, Str(NB, PreviousBank, 0));
        }
        strcat(Wmsg, " were edited \r\nbut not saved. (Too late now!)\r\nSo you may want to check them.");
        MsgBox((char *)(CurrentView == RESCUE2VIEW ? "page Rescue2View" : "page RescueView"), Wmsg);
        SendText((char *)"t11", ModelName);
        SendText((char *)"t9", b);
    }
    Rescue_Was_Edited = false;
    SendCommand((char *)"vis b3,0");
    RescueHave = false;                    // B211 (the fifteenth review; released code): what is in hand is the OLD bank's from this moment - not from
                                           // the moment the read begins, four tenths of a second on (a switch and Save tapped in between wrote it to the new bank)
    if (RescueStep == RSC_SELECT || RescueStep == RSC_READ)
        RescueStep = RSC_IDLE;             // (the sixteenth review) ... AND A READ UNDER WAY IS DROPPED: its answer - the old bank's block, or whichever the
                                           // flight controller was on as it answered - put "in hand" back under the new bank's name until the read below
    RescueRereadWanted = true;             // B79: read in a moment, when the flight controller has moved to the new bank (the switch's channel reaches it a few tens of milliseconds after the move)
    RescueRereadAt = millis() + 400;
    RescueBusy("Loading the new bank ...");
}
// Each time round the loop (ManageTransmitter)
FLASHMEM void RescuePoll()
{
    if (CurrentView != RESCUEVIEW && CurrentView != RESCUE2VIEW)
    {
        RescueStep = RSC_IDLE; // the page went
        RescueMsgUntil = 0;
        return;
    }
    if (RescueMsgUntil && (int32_t)(millis() - RescueMsgUntil) >= 0)
    {
        RescueMsgUntil = 0;
        RescueBusy(""); // (B211, the eleventh review: the message goes and NOTHING is drawn - what was typed since stays; the screen draws what lay under the message)
    }
    if (RescueStep == RSC_IDLE)
    {
        if (RescueRereadWanted && (int32_t)(millis() - RescueRereadAt) >= 0)
        {
            RescueRereadWanted = false;
            RescueRead();
        }
        return;
    }
    if (!PipeReplyReady(RescueReq))
    {
        if (PipeReplyLate())
            RescueFail(RfNoAnswerWords(RescueStep == RSC_WRITE || RescueStep == RSC_STORE));
        return;
    }
    const bool ok = PipeRepCode == 200;
    switch (RescueStep)
    {
    case RSC_SELECT:
        if (!ok) { RescueFail("Could not select the bank"); return; }
        RescueReq = MspAsk(146, nullptr, 0);
        RescueStep = RSC_READ;
        return;
    case RSC_READ:
    {
        if (!ok) { RescueFail("Could not read"); return; }
        uint8_t b[64];
        const int n = PipeReplyBytes(b, sizeof(b));
        if (n < RESCUE_BYTES) { PipeRepCode = 0; snprintf(PipeRepBody, sizeof(PipeRepBody), "only %d bytes came (Rotorflight 2.3 sends 28)", n); PipeRepCode = 200; RescueFail("Could not read"); return; }
        memcpy(RescueRaw, b, RESCUE_BYTES);
        memcpy(RescueWant, b, RESCUE_BYTES);
        RescueHave = true;
        RescueStep = RSC_IDLE;
        RescueBusy("");
        RescueShow();
        Rescue_Was_Edited = false;
        SendCommand((char *)"vis b3,0"); // Save waits for an edit
        return;
    }
    case RSC_W_SELECT:
        if (!ok) { RescueFail("Could not select the bank"); return; }
        RescueReq = MspAsk(147, RescueWant, RESCUE_BYTES);
        RescueStep = RSC_WRITE;
        return;
    case RSC_WRITE:
        if (!ok) { RescueFail("Not written"); return; }
        RescueReq = MspAsk(250, nullptr, 0);
        RescueStep = RSC_STORE;
        return;
    case RSC_STORE:
        if (!ok) { RescueFail("Written, but NOT STORED - try again, or switch the model off and on"); return; }
        RescueAskSelect(RSC_V_SELECT);
        return;
    case RSC_V_SELECT:
        if (!ok) { RescueFail("Could not select the bank"); return; }
        RescueReq = MspAsk(146, nullptr, 0);
        RescueStep = RSC_VERIFY;
        return;
    case RSC_VERIFY:
    {
        if (!ok) { RescueFail("Could not read back"); return; }
        uint8_t b[64];
        const int n = PipeReplyBytes(b, sizeof(b));
        const bool same = n >= RESCUE_BYTES && memcmp(b, RescueWant, RESCUE_BYTES) == 0;
        if (n >= RESCUE_BYTES)
            memcpy(RescueRaw, b, RESCUE_BYTES);
        RescueStep = RSC_IDLE;
        Rescue_Was_Edited = false;
        SendCommand((char *)"vis b3,0");
        RescueShow();
        RescueBusy(same ? "Saved, and read back the same." : "Saved, but the flight controller adjusted some values.");
        RescueMsgUntil = millis() + 4000;
        PlaySound(BEEPCOMPLETE);
        RfSavedThenLeave(CurrentView);   // B102: OK's "Save now?" closes the page once saved
        return;
    }
    default:
        RescueStep = RSC_IDLE;
        return;
    }
}
FLASHMEM static void RescueRead()
{
    RescueHave = false; // B211 (the fifteenth review; released code): NOTHING IS IN HAND UNTIL THIS READ HAS IT (RF_SaveNow.h RfLeaveNotRead)
    RescueBusy("Reading from the flight controller ...");
    RescueAskSelect(RSC_SELECT);
}
FLASHMEM void StartRescueView()
{
    char why[120];
    if (RfNeedsModel(why, sizeof(why)) || ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFView", why);
        return;
    }
    SendCommand((char *)"page RescueView");
    CurrentView = RESCUEVIEW;
    SendText((char *)"t11", ModelName);
    char b[16];
    snprintf(b, sizeof(b), "Bank %d", Bank);
    SendText((char *)"t9", b);
    SendCommand((char *)"vis b3,0");
    Rescue_Was_Edited = false;
    RescueRead();
}
void SaveRescue();
FLASHMEM static void RescueSaveNow() { SendText((char *)"t11", ModelName); SendCommand((char *)"vis b3,1"); RescueShow(); SaveRescue(); }   // B102: OK's "Save now?"
FLASHMEM void EndRescueView() // OK, on either page (B53: page 2 has OK too; "< Previous" is EndRescue2View)
{
    if (Rescue_Was_Edited)
    {
        RfGatherStart();   // B187 (was NextionTextMissed = false: now the screen is let finish its queue first)
        if (CurrentView == RESCUEVIEW) RescueGatherPage1(); else RescueGatherPage2();   // (B59) the edits, before the question's page takes the fields away
        if (RfFieldsMissed(CurrentView == RESCUE2VIEW ? "page Rescue2View" : "page RescueView")) return;   // B156: a box unanswered: the page is not left
        if (!RfSaveFirst(CurrentView == RESCUE2VIEW ? "page Rescue2View" : "page RescueView", "The edited rescue values are", RescueSaveNow, EndRescueView, &Rescue_Was_Edited)) return;   // B102
    }
    RescueStep = RSC_IDLE;
    Rescue_Was_Edited = false;
    RfMenuFromPage(RescueHave);
}
FLASHMEM void RescueWasEdited() // a number was typed
{
    if (!RescueHave)
        return; // B211 (the sixteenth review): with nothing in hand nothing is an edit - OK asked "Save now?" for it, the save returned at once, and "close when saved" stood
    SendCommand((char *)"vis b3,1");
    Rescue_Was_Edited = true;
}
static int RescueModeWhenOn = 1;       // what "On" means: Climb, or Hold height if that is what it was
FLASHMEM void RescueModeTapped() // page 1, Enable Rescue: Off <-> On
{
    if (RescueMode)
    {
        RescueModeWhenOn = RescueMode;
        RescueMode = 0;
    }
    else
        RescueMode = RescueModeWhenOn >= 1 && RescueModeWhenOn <= 2 ? RescueModeWhenOn : 1;
    SendValue((char *)"tn0", RescueMode ? 1 : 0);   // (B65: a switch)
    RescueWasEdited();
}
FLASHMEM void RescueFlipTapped() // page 1: Flip <-> No-Flip
{
    RescueFlip = !RescueFlip;
    SendValue((char *)"tn1", RescueFlip ? 1 : 0);   // (B65: a switch)
    RescueWasEdited();
}
FLASHMEM void RescueMode2Tapped() // page 2, Rescue mode: Off -> Climb -> Hold height -> Off
{
    RescueMode = (RescueMode + 1) % 3;
    if (RescueMode)
        RescueModeWhenOn = RescueMode;
    RescueField("tn0", RescueModeWords[RescueMode]);
    RescueWasEdited();
}
FLASHMEM void SaveRescue()
{
    if (!RescueHave)
    {
        RfLeaveAfterSave = false; // (the sixteenth review: ... and OK's "close when saved" does not stand on for a later Save - RF_SaveNow.h)
        return;
    }
    char why[120];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)(CurrentView == RESCUEVIEW ? "page RescueView" : "page Rescue2View"), why);
        return;
    }
    RfGatherStart();   // B187 (was NextionTextMissed = false: now the screen is let finish its queue first)
    if (CurrentView == RESCUEVIEW)
        RescueGatherPage1();
    else
        RescueGatherPage2();
    if (RfFieldsMissed(CurrentView == RESCUEVIEW ? "page RescueView" : "page Rescue2View")) return;   // B152: a box unanswered: nothing written
    RescueBusy("Writing to the flight controller ...");
    RescueAskSelect(RSC_W_SELECT);
}
FLASHMEM void StartRescue2View() // Next >
{
    if (CurrentView == RESCUEVIEW && RescueHave) // (the sixteenth review: with nothing in hand nothing is gathered - the page below reads)
    {
        RfGatherStart();   // B187 (was NextionTextMissed = false: now the screen is let finish its queue first)
        RescueGatherPage1(); // page 1's edits travel with us, unsaved: a save on page 2 writes both
        if (RfFieldsMissed("page RescueView")) return;   // B156: a box unanswered: the page is not left (a clamped value would have been saved from page 2)
    }
    SendCommand((char *)"page Rescue2View");
    CurrentView = RESCUE2VIEW;
    SendText((char *)"t11", ModelName);
    char b[16];
    snprintf(b, sizeof(b), "Bank %d", Bank);
    SendText((char *)"t9", b);
    SendCommand((char *)(Rescue_Was_Edited ? "vis b3,1" : "vis b3,0"));
    if (RescueHave)
        RescueShowPage2();
    else
        RescueRead();
}
FLASHMEM void EndRescue2View() // < Previous: back to page 1 (its fields from the bytes in hand, edits kept)
{
    if (RescueHave)
    { // (the sixteenth review: WITH NOTHING IN HAND - the standing "NOT READ" page, a read under way - nothing is gathered and nothing drawn: page 1
      //  was drawn from the block of the read BEFORE, another bank's, under this bank's name, with no line and no read asked. As "Next >": it reads.)
        RfGatherStart();   // B187 (was NextionTextMissed = false: now the screen is let finish its queue first)
        RescueGatherPage2();
        if (RfFieldsMissed("page Rescue2View")) return;   // B156: a box unanswered: the page is not left
        memcpy(RescueRaw, RescueWant, RESCUE_BYTES); // (what page 1 shows next is the edited set; a save or a re-read settles it)
    }
    SendCommand((char *)"page RescueView");
    CurrentView = RESCUEVIEW;
    SendText((char *)"t11", ModelName);
    char b[16];
    snprintf(b, sizeof(b), "Bank %d", Bank);
    SendText((char *)"t9", b);
    SendCommand((char *)(Rescue_Was_Edited && RescueHave ? "vis b3,1" : "vis b3,0"));
    if (RescueHave)
        RescueShowPage1();
    else
        RescueRead();
}
#endif
