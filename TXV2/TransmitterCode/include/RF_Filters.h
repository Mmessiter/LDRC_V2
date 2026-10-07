// B58: Rotorflight's gyro filters on the transmitter (page FilterView, hmi/filter_pages.py), as the receiver's own
// filters page reads them (RXV2 data/rotorflight-filters.html): MSP 92 read / 93 write, 27 bytes - lowpass 1 type and
// Hz, lowpass 2 type and Hz, notch 1 and 2 (Hz, cutoff), the dynamic notches (count, Q, min, max Hz), the RPM filter
// preset and its minimum Hz. Read-modify-write: only these fields change, the rest of the 27 go back as they came.
// The write takes effect at once; 250 stores it; 92 again checks.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_FILTERS_H
#define RF_FILTERS_H

static const int FLT_BYTES = 27;
static uint8_t FltRaw[FLT_BYTES], FltWant[FLT_BYTES];
static bool FltHave = false, Flt_Was_Edited = false;
static int FltLpf1Type = 0, FltLpf2Type = 0, FltPreset = 0;
enum { FLT_IDLE = 0, FLT_READ, FLT_WRITE, FLT_STORE, FLT_VERIFY };
static int FltStep = FLT_IDLE, FltReq = 0;
static uint32_t FltMsgUntil = 0;
static const char *FltTypeWords[7] = {"PT1", "PT2", "PT3", "1st order", "Butterworth", "Bessel", "Damped"};   // Rotorflight's lowpass types, in its order
static const char *FltPresetWords[4] = {"Custom", "Low vib.", "Normal", "High vib."};

static void FltBusy(const char *msg)
{
    SendCommand((char *)(msg && *msg ? "vis busy,1" : "vis busy,0"));
    if (msg && *msg)
        SendText((char *)"busy", (char *)msg);
}
static void FltNum(const char *name, long v)
{
    char b[16];
    snprintf(b, sizeof(b), "%ld", v);
    SendText((char *)name, b);
}
static void FltShow()
{
    FltLpf1Type = FltWant[1] < 7 ? FltWant[1] : 0;
    FltLpf2Type = FltWant[4] < 7 ? FltWant[4] : 0;
    FltPreset = FltWant[25] < 4 ? FltWant[25] : 0;
    SendText((char *)"tn0", (char *)FltTypeWords[FltLpf1Type]);
    FltNum("tn1", RdU16(FltWant, 2));
    SendText((char *)"tn2", (char *)FltTypeWords[FltLpf2Type]);
    FltNum("tn3", RdU16(FltWant, 5));
    FltNum("tn4", RdU16(FltWant, 7));
    FltNum("tn5", RdU16(FltWant, 9));
    FltNum("tn6", RdU16(FltWant, 11));
    FltNum("tn7", RdU16(FltWant, 13));
    FltNum("tn8", FltWant[19]);
    FltNum("tn9", FltWant[20]);
    FltNum("tn10", RdU16(FltWant, 21));
    FltNum("tn11", RdU16(FltWant, 23));
    SendText((char *)"tn12", (char *)FltPresetWords[FltPreset]);
    FltNum("tn13", FltWant[26]);
}
static void FltGather()
{
    FltWant[1] = (uint8_t)FltLpf1Type;
    WrU16(FltWant, 2, FieldNumber("tn1", 0, 1000));
    FltWant[4] = (uint8_t)FltLpf2Type;
    WrU16(FltWant, 5, FieldNumber("tn3", 0, 1000));
    WrU16(FltWant, 7, FieldNumber("tn4", 0, 1000));
    WrU16(FltWant, 9, FieldNumber("tn5", 0, 1000));
    WrU16(FltWant, 11, FieldNumber("tn6", 0, 1000));
    WrU16(FltWant, 13, FieldNumber("tn7", 0, 1000));
    FltWant[19] = (uint8_t)FieldNumber("tn8", 0, 8);
    FltWant[20] = (uint8_t)FieldNumber("tn9", 10, 100);
    WrU16(FltWant, 21, FieldNumber("tn10", 10, 200));
    WrU16(FltWant, 23, FieldNumber("tn11", 100, 500));
    FltWant[25] = (uint8_t)FltPreset;
    FltWant[26] = (uint8_t)FieldNumber("tn13", 1, 255);
}
static void FltHead();
static void FltFail(const char *what)
{
    char msg[180];
    snprintf(msg, sizeof(msg), "%s:\r\n%.140s", what, PipeRepCode ? PipeRepBody : "the screen could not ask (no Bluetooth)");
    FltStep = FLT_IDLE;
    FltBusy("");
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)"page FilterView", msg);
    FltHead();
    FltShow();
}
static void FltRead()
{
    FltBusy("Reading from the flight controller ...");
    FltReq = MspAsk(92, nullptr, 0);
    FltStep = FLT_READ;
}
void FilterPoll()
{
    if (CurrentView != FILTERVIEW) { FltStep = FLT_IDLE; FltMsgUntil = 0; return; }
    if (FltMsgUntil && (int32_t)(millis() - FltMsgUntil) >= 0) { FltMsgUntil = 0; FltBusy(""); FltShow(); }
    if (FltStep == FLT_IDLE) return;
    if (!PipeReplyReady(FltReq)) { if (PipeReplyLate()) FltFail("No answer"); return; }
    const bool ok = PipeRepCode == 200;
    switch (FltStep)
    {
    case FLT_READ:
    {
        if (!ok) { FltFail("Could not read the filters"); return; }
        uint8_t b[40];
        const int n = PipeReplyBytes(b, sizeof(b));
        if (n < FLT_BYTES) { snprintf(PipeRepBody, sizeof(PipeRepBody), "only %d bytes came (Rotorflight 2.3 sends 27)", n); FltFail("Could not read the filters"); return; }
        memcpy(FltRaw, b, FLT_BYTES); memcpy(FltWant, b, FLT_BYTES);
        FltHave = true; FltStep = FLT_IDLE; Flt_Was_Edited = false;
        FltBusy(""); SendCommand((char *)"vis b3,0"); FltShow();
        return;
    }
    case FLT_WRITE:
        if (!ok) { FltFail("Not written"); return; }
        FltReq = MspAsk(250, nullptr, 0); FltStep = FLT_STORE;
        return;
    case FLT_STORE:
        if (!ok) { FltFail("Not stored"); return; }
        FltReq = MspAsk(92, nullptr, 0); FltStep = FLT_VERIFY;
        return;
    case FLT_VERIFY:
    {
        if (!ok) { FltFail("Could not read back"); return; }
        uint8_t b[40];
        const int n = PipeReplyBytes(b, sizeof(b));
        const bool same = n >= FLT_BYTES && memcmp(b, FltWant, FLT_BYTES) == 0;
        if (n >= FLT_BYTES) { memcpy(FltRaw, b, FLT_BYTES); memcpy(FltWant, b, FLT_BYTES); }
        FltStep = FLT_IDLE; Flt_Was_Edited = false;
        SendCommand((char *)"vis b3,0"); FltShow();
        FltBusy(same ? "Saved, and read back the same." : "Saved; the flight controller adjusted some values (shown).");
        FltMsgUntil = millis() + 4000;
        PlaySound(BEEPCOMPLETE);
        return;
    }
    default:
        FltStep = FLT_IDLE;
        return;
    }
}
void StartFilterView()
{
    char why[120];
    if (RfNeedsModel(why, sizeof(why)) || ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFView", why);
        return;
    }
    SendCommand((char *)"page FilterView");
    CurrentView = FILTERVIEW;
    SendText((char *)"t11", ModelName);
    char b[16];
    snprintf(b, sizeof(b), "Bank %d", Bank);
    SendText((char *)"t9", b);
    SendCommand((char *)"vis b3,0");
    Flt_Was_Edited = false;
    FltRead();
}
static void FltHead()
{
    SendText((char *)"t11", ModelName);
    char b[16];
    snprintf(b, sizeof(b), "Bank %d", Bank);
    SendText((char *)"t9", b);
    SendCommand((char *)(Flt_Was_Edited ? "vis b3,1" : "vis b3,0"));
}
void EndFilterView()
{
    if (Flt_Was_Edited)
    {
        FltGather(); // (B59) before the question's page takes the fields away
        if (!GetConfirmation((char *)"page FilterView", (char *)"Discard the edited filter values?")) { FltHead(); FltShow(); return; }
    }
    FltStep = FLT_IDLE;
    Flt_Was_Edited = false;
    RotorFlightStart();
}
void FilterWasEdited() { SendCommand((char *)"vis b3,1"); Flt_Was_Edited = true; }
void FilterLpf1Tapped() { FltLpf1Type = (FltLpf1Type + 1) % 7; SendText((char *)"tn0", (char *)FltTypeWords[FltLpf1Type]); FilterWasEdited(); }
void FilterLpf2Tapped() { FltLpf2Type = (FltLpf2Type + 1) % 7; SendText((char *)"tn2", (char *)FltTypeWords[FltLpf2Type]); FilterWasEdited(); }
void FilterPresetTapped() { FltPreset = (FltPreset + 1) % 4; SendText((char *)"tn12", (char *)FltPresetWords[FltPreset]); FilterWasEdited(); }
void SaveFilters()
{
    if (!FltHave)
        return;
    char why[120];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page FilterView", why);
        return;
    }
    FltGather();
    FltBusy("Writing to the flight controller ...");
    FltReq = MspAsk(93, FltWant, FLT_BYTES);
    FltStep = FLT_WRITE;
}
#endif
