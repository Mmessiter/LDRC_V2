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
static uint32_t RescueMsgUntil = 0;        // a message shown over the fields goes by itself
static uint8_t RescueWant[RESCUE_BYTES];   // what a save asked for

static const char *RescueModeWords[3] = {"Off", "Climb", "Hold height"};   // the mode on the height page; page 1's "Enable Rescue" is Off / On (B52: the configurator's names in its places)

static uint16_t RdU16(const uint8_t *b, int o) { return (uint16_t)(b[o] | (b[o + 1] << 8)); }
static void WrU16(uint8_t *b, int o, long v)
{
    if (v < 0)
        v = 0;
    if (v > 65535)
        v = 65535;
    b[o] = (uint8_t)(v & 0xFF);
    b[o + 1] = (uint8_t)(v >> 8);
}
static void RescueBusy(const char *msg)
{
    SendCommand((char *)(msg && *msg ? "vis busy,1" : "vis busy,0"));
    if (msg && *msg)
        SendText((char *)"busy", (char *)msg);
}
static void RescueField(const char *name, const char *text) { SendText((char *)name, (char *)text); }
static void RescueNumber(const char *name, long v)
{
    char b[16];
    snprintf(b, sizeof(b), "%ld", v);
    RescueField(name, b);
}
static void RescueTenths(const char *name, int tenths)
{
    char b[16];
    snprintf(b, sizeof(b), "%d.%d", tenths / 10, tenths % 10);
    RescueField(name, b);
}
static void RescuePercent(const char *name, int tenths) // a collective of 0..1000 as the configurator shows it: 450 = 45, 655 = 65.5
{
    char b[16];
    if (tenths % 10) snprintf(b, sizeof(b), "%d.%d", tenths / 10, tenths % 10); else snprintf(b, sizeof(b), "%d", tenths / 10);
    RescueField(name, b);
}
// The page's fields from the bytes (page 1: RescueView; page 2: Rescue2View)
static void RescueShowPage1()
{
    RescueMode = RescueRaw[0] <= 2 ? RescueRaw[0] : 0;
    RescueFlip = RescueRaw[1] ? 1 : 0;
    RescueField("tn0", RescueMode ? "On" : "Off");
    RescueField("tn1", RescueFlip ? "Flip" : "No-Flip");
    RescuePercent("tn2", RdU16(RescueRaw, 8));   // Pull-up Collective [%]
    RescueTenths("tn3", RescueRaw[4]);           // Pull-up Time [s]
    RescuePercent("tn4", RdU16(RescueRaw, 10));  // Climb Collective [%]
    RescueTenths("tn5", RescueRaw[5]);           // Climb Time [s]
    RescuePercent("tn6", RdU16(RescueRaw, 12));  // Hover Collective [%]
    RescueTenths("tn7", RescueRaw[6]);           // Flip Fail Time [s]
    RescueTenths("tn8", RescueRaw[7]);           // Exit Time [s]
    RescueNumber("tn9", RescueRaw[3]);           // Leveling Gain
    RescueNumber("tn10", RescueRaw[2]);          // Flip-to-Upright Gain
    RescueNumber("tn11", RdU16(RescueRaw, 24));  // Max Levelling Rate
    RescueNumber("tn12", RdU16(RescueRaw, 26));  // Max Leveling Acceleration
}
static void RescueShowPage2()
{
    char b[16];
    RescueMode = RescueRaw[0] <= 2 ? RescueRaw[0] : 0;
    RescueField("tn0", RescueModeWords[RescueMode]);
    const unsigned h = RdU16(RescueRaw, 14);
    snprintf(b, sizeof(b), "%u.%02u", h / 100, h % 100);
    RescueField("tn1", b);                       // Hover height [m]
    RescueNumber("tn2", RdU16(RescueRaw, 16));   // Height hold P
    RescueNumber("tn3", RdU16(RescueRaw, 18));   // I
    RescueNumber("tn4", RdU16(RescueRaw, 20));   // D
    RescuePercent("tn5", RdU16(RescueRaw, 22));  // Max Collective [%]
}
static void RescueShow()
{
    if (CurrentView == RESCUEVIEW)
        RescueShowPage1();
    else if (CurrentView == RESCUE2VIEW)
        RescueShowPage2();
}
static long FieldNumber(const char *name, long lo, long hi) // a field as typed, clamped
{
    char t[24] = "";
    GetText((char *)name, t, sizeof(t) - 1);
    long v = strtol(t, nullptr, 10);
    return v < lo ? lo : v > hi ? hi : v;
}
static int FieldTenths(const char *name, int lo, int hi) // "1.5" -> 15
{
    char t[24] = "";
    GetText((char *)name, t, sizeof(t) - 1);
    const float f = (float)atof(t);
    int v = (int)(f * 10.0f + (f >= 0 ? 0.5f : -0.5f));
    return v < lo ? lo : v > hi ? hi : v;
}
// The bytes to write: the page's fields over the last read (the other page's values stay as read, or as edited there)
static int FieldPercent(const char *name, int lo, int hi) // "45" or "65.5" -> 450 / 655
{
    return FieldTenths(name, lo, hi);
}
static void RescueGatherPage1()
{
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
static void RescueGatherPage2()
{
    RescueWant[0] = (uint8_t)RescueMode;
    char t[24] = "";
    GetText((char *)"tn1", t, sizeof(t) - 1);
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
static void RescueAskSelect(int next)
{
    uint8_t b = (uint8_t)(Bank >= 1 && Bank <= 6 ? Bank - 1 : 0);
    RescueReq = MspAsk(210, &b, 1);
    RescueStep = next;
}
static void RescueRead();
static void RescueFail(const char *what) // B54 (Malcolm: "the error banners should look more like message boxes"): a message box, with the whole of the receiver's words
{
    char msg[180];
    snprintf(msg, sizeof(msg), "%s:\r\n%.140s", what, PipeRepCode ? PipeRepBody : "the screen could not ask (no Bluetooth)");
    RescueStep = RSC_IDLE;
    RescueBusy("");
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)(CurrentView == RESCUE2VIEW ? "page Rescue2View" : "page RescueView"), msg);
    RescueShow(); // the page came back from the box: its fields again
}
static bool RescueRereadWanted = false;    // B54: the bank switch moved while a read or a save was under way
void RescueBankChanged()                   // from BankHasChanged (Switches.h): the values of the new bank, the edits of the old one let go
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
        strcpy(Wmsg, "Rescue values for Bank ");
        strcat(Wmsg, Str(NB, PreviousBank, 0));
        strcat(Wmsg, " were edited \r\nbut not saved. (Too late now!)\r\nSo you may want to check them.");
        MsgBox((char *)(CurrentView == RESCUE2VIEW ? "page Rescue2View" : "page RescueView"), Wmsg);
    }
    Rescue_Was_Edited = false;
    SendCommand((char *)"vis b3,0");
    if (RescueStep != RSC_IDLE)
    {
        RescueRereadWanted = true;
        return;
    }
    RescueRead();
}
// Each time round the loop (ManageTransmitter)
void RescuePoll()
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
        RescueBusy("");
        RescueShow(); // the fields the message lay over
    }
    if (RescueStep == RSC_IDLE)
    {
        if (RescueRereadWanted)
        {
            RescueRereadWanted = false;
            RescueRead();
        }
        return;
    }
    if (!PipeReplyReady(RescueReq))
    {
        if (PipeReplyLate())
            RescueFail("No answer");
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
        if (!ok) { RescueFail("Not stored"); return; }
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
        RescueBusy(same ? "Saved, and read back the same." : "Saved; the flight controller adjusted some values (shown).");
        RescueMsgUntil = millis() + 4000;
        PlaySound(BEEPCOMPLETE);
        return;
    }
    default:
        RescueStep = RSC_IDLE;
        return;
    }
}
static void RescueRead()
{
    RescueBusy("Reading from the flight controller ...");
    RescueAskSelect(RSC_SELECT);
}
void StartRescueView()
{
    char why[120];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
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
void EndRescueView() // OK, on either page (B53: page 2 has OK too; "< Previous" is EndRescue2View)
{
    if (Rescue_Was_Edited && !GetConfirmation((char *)(CurrentView == RESCUE2VIEW ? "page Rescue2View" : "page RescueView"), (char *)"Discard the edited rescue values?"))
        return;
    RescueStep = RSC_IDLE;
    Rescue_Was_Edited = false;
    RotorFlightStart();
}
void RescueWasEdited() // a number was typed
{
    SendCommand((char *)"vis b3,1");
    Rescue_Was_Edited = true;
}
static int RescueModeWhenOn = 1;       // what "On" means: Climb, or Hold height if that is what it was
void RescueModeTapped() // page 1, Enable Rescue: Off <-> On
{
    if (RescueMode)
    {
        RescueModeWhenOn = RescueMode;
        RescueMode = 0;
    }
    else
        RescueMode = RescueModeWhenOn >= 1 && RescueModeWhenOn <= 2 ? RescueModeWhenOn : 1;
    RescueField("tn0", RescueMode ? "On" : "Off");
    RescueWasEdited();
}
void RescueFlipTapped() // page 1: Flip <-> No-Flip
{
    RescueFlip = !RescueFlip;
    RescueField("tn1", RescueFlip ? "Flip" : "No-Flip");
    RescueWasEdited();
}
void RescueMode2Tapped() // page 2, Rescue mode: Off -> Climb -> Hold height -> Off
{
    RescueMode = (RescueMode + 1) % 3;
    if (RescueMode)
        RescueModeWhenOn = RescueMode;
    RescueField("tn0", RescueModeWords[RescueMode]);
    RescueWasEdited();
}
void SaveRescue()
{
    if (!RescueHave)
        return;
    char why[120];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)(CurrentView == RESCUEVIEW ? "page RescueView" : "page Rescue2View"), why);
        return;
    }
    if (CurrentView == RESCUEVIEW)
        RescueGatherPage1();
    else
        RescueGatherPage2();
    RescueBusy("Writing to the flight controller ...");
    RescueAskSelect(RSC_W_SELECT);
}
void StartRescue2View() // Next >
{
    if (CurrentView == RESCUEVIEW)
        RescueGatherPage1(); // page 1's edits travel with us, unsaved: a save on page 2 writes both
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
void EndRescue2View() // < Previous: back to page 1 (its fields from the bytes in hand, edits kept)
{
    RescueGatherPage2();
    memcpy(RescueRaw, RescueWant, RESCUE_BYTES); // (what page 1 shows next is the edited set; a save or a re-read settles it)
    SendCommand((char *)"page RescueView");
    CurrentView = RESCUEVIEW;
    SendText((char *)"t11", ModelName);
    char b[16];
    snprintf(b, sizeof(b), "Bank %d", Bank);
    SendText((char *)"t9", b);
    SendCommand((char *)(Rescue_Was_Edited ? "vis b3,1" : "vis b3,0"));
    RescueShowPage1();
}
#endif
