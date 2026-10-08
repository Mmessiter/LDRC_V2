// B58/B61: Rotorflight's gyro filters on the transmitter, laid out as the configurator 2.3's Gyro tab (hmi/filter_pages.py):
// page FilterView = its plain view (Lowpass Filter, Dynamic Filter, RPM Filter), page Filter2View = its expert-mode items
// (Lowpass Filter 2, the dynamic cutoff of lowpass 1, Notch Filters 1 and 2). Its names, order and units (Malcolm, 7 Oct:
// "use the same names in the same places"), and its Enable on every section:
//   - a lowpass is enabled when its type is not 0, a notch when its center and cutoff are not 0, the dynamic cutoff when
//     its min is not 0 and below its max: Enable = No zeroes them (the values are remembered for a Yes), as the configurator;
//   - the Dynamic Filter and the RPM Filter are Rotorflight FEATURES (bits 29 and 30 of MSP 36/37), which the flight
//     controller applies only when it boots: a save that changes one restarts it (MSP 68), as the configurator does.
// MSP 92 read / 93 write, 27 bytes (Rotorflight 4.6 msp.c MSP_FILTER_CONFIG): 0 hardware lpf | 1 lpf1 type | 2-3 lpf1 Hz |
// 4 lpf2 type | 5-6 lpf2 Hz | 7-8 notch1 center | 9-10 notch1 cutoff | 11-12 notch2 center | 13-14 notch2 cutoff |
// 15-16 lpf1 dynamic min | 17-18 max | 19 dyn notch count | 20 dyn notch Q x10 | 21-22 dyn notch min Hz | 23-24 max Hz |
// 25 rpm preset (0 custom, 1 low, 2 medium, 3 high) | 26 rpm min Hz. Read-modify-write; the write takes effect at once; 250 stores it.
// Lowpass types (common/filter.h): 0 none, 1 1st order, 2 2nd order, 3 PT1, 4 PT2, 5 PT3, 6 order1, 7 Butterworth, 8 Bessel,
// 9 damped. (B58 had them in the wrong order, so "1st order" read as PT2: Malcolm's comparison with the configurator, 7 Oct.)
// Filters are global, not per bank.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_FILTERS_H
#define RF_FILTERS_H

static const int FLT_BYTES = 27;
static uint8_t FltRaw[FLT_BYTES], FltWant[FLT_BYTES];
static uint32_t FeatRaw = 0, FeatWant = 0;   // the feature mask (MSP 36)
static const uint32_t FEAT_DYN_NOTCH = 1UL << 29, FEAT_RPM_FILTER = 1UL << 30;
static bool FltHave = false, Flt_Was_Edited = false;
enum { FLT_IDLE = 0, FLT_READ_FEAT, FLT_READ, FLT_WRITE, FLT_FEAT, FLT_STORE, FLT_REBOOT, FLT_WAIT, FLT_VERIFY_FEAT, FLT_VERIFY };
static int FltStep = FLT_IDLE, FltReq = 0, FltTries = 0;
static uint32_t FltMsgUntil = 0, FltWaitUntil = 0;
static const char *FltTypeWords[10] = {"Disabled", "1st order", "2nd order", "PT1", "PT2", "PT3", "Order1", "Butter", "Bessel", "Damped"};   // the configurator's words for Rotorflight's lowpass types
static const char *FltPresetWords[4] = {"Custom", "Low", "Medium", "High"};   // the configurator's "Strength"
// What a section had before its Enable went to No, for a Yes (the configurator's previousValues; 0 = nothing remembered)
static uint8_t PrevLpf1Type = 0, PrevLpf2Type = 0;
static uint16_t PrevLpf1Hz = 0, PrevLpf2Hz = 0, PrevDynMin = 0, PrevDynMax = 0, PrevN1Hz = 0, PrevN1Cut = 0, PrevN2Hz = 0, PrevN2Cut = 0;

static bool Lpf1On() { return FltWant[1] != 0; }
static bool Lpf2On() { return FltWant[4] != 0; }
static bool DynLpfOn() { return RdU16(FltWant, 15) > 0 && RdU16(FltWant, 15) < RdU16(FltWant, 17); }
static bool N1On() { return RdU16(FltWant, 7) > 0 && RdU16(FltWant, 9) > 0; }
static bool N2On() { return RdU16(FltWant, 11) > 0 && RdU16(FltWant, 13) > 0; }
static bool DynNotchOn() { return (FeatWant & FEAT_DYN_NOTCH) != 0; }
static bool RpmOn() { return (FeatWant & FEAT_RPM_FILTER) != 0; }
static const char *FltPageWord() { return CurrentView == FILTER2VIEW ? "page Filter2View" : "page FilterView"; }

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
static void FltYesNo(const char *name, bool on) { SendValue((char *)name, on ? 1 : 0); }   // B65: a switch on the screen (Malcolm, 8 Oct: "the yes/no boxes should be switches")
static void FltRows(bool on, int from, int to) // show or hide the value rows tn<from>..tn<to> and their labels
{
    char c[20];
    for (int i = from; i <= to; ++i)
    {
        snprintf(c, sizeof(c), "vis ltn%d,%d", i, on ? 1 : 0); SendCommand(c);
        snprintf(c, sizeof(c), "vis tn%d,%d", i, on ? 1 : 0); SendCommand(c);
    }
}
static void FltShowPage1()
{
    FltYesNo("tn0", Lpf1On()); FltRows(Lpf1On(), 1, 2);
    SendText((char *)"tn1", (char *)FltTypeWords[FltWant[1] < 10 ? FltWant[1] : 0]);
    FltNum("tn2", RdU16(FltWant, 2));
    FltYesNo("tn3", RpmOn()); FltRows(RpmOn(), 4, 5);
    SendText((char *)"tn4", (char *)FltPresetWords[FltWant[25] < 4 ? FltWant[25] : 0]);
    FltNum("tn5", FltWant[26]);
    FltYesNo("tn6", DynNotchOn()); FltRows(DynNotchOn(), 7, 10);
    FltNum("tn7", FltWant[19]);
    { char b[16]; snprintf(b, sizeof(b), "%d.%d", FltWant[20] / 10, FltWant[20] % 10); SendText((char *)"tn8", b); }   // Q: the configurator shows 25 as 2.5
    FltNum("tn9", RdU16(FltWant, 21));
    FltNum("tn10", RdU16(FltWant, 23));
}
static void FltShowPage2()
{
    FltYesNo("tn0", Lpf2On()); FltRows(Lpf2On(), 1, 2);
    SendText((char *)"tn1", (char *)FltTypeWords[FltWant[4] < 10 ? FltWant[4] : 0]);
    FltNum("tn2", RdU16(FltWant, 5));
    FltYesNo("tn3", DynLpfOn()); FltRows(DynLpfOn(), 4, 5);
    FltNum("tn4", RdU16(FltWant, 15));
    FltNum("tn5", RdU16(FltWant, 17));
    FltYesNo("tn6", N1On()); FltRows(N1On(), 7, 8);
    FltNum("tn7", RdU16(FltWant, 7));
    FltNum("tn8", RdU16(FltWant, 9));
    FltYesNo("tn9", N2On()); FltRows(N2On(), 10, 11);
    FltNum("tn10", RdU16(FltWant, 11));
    FltNum("tn11", RdU16(FltWant, 13));
}
static void FltShow()
{
    if (CurrentView == FILTERVIEW) FltShowPage1();
    else if (CurrentView == FILTER2VIEW) FltShowPage2();
}
// The typed numbers of the page showing, into FltWant (only the rows that show: a section at No keeps its zeros)
static void FltGather()
{
    if (CurrentView == FILTERVIEW)
    {
        if (Lpf1On()) WrU16(FltWant, 2, FieldNumber("tn2", 0, 1000));
        if (RpmOn()) FltWant[26] = (uint8_t)FieldNumber("tn5", 1, 100);
        if (DynNotchOn())
        {
            FltWant[19] = (uint8_t)FieldNumber("tn7", 0, 8);
            FltWant[20] = (uint8_t)FieldTenths("tn8", 10, 100);
            WrU16(FltWant, 21, FieldNumber("tn9", 10, 200));
            WrU16(FltWant, 23, FieldNumber("tn10", 100, 500));
        }
    }
    else if (CurrentView == FILTER2VIEW)
    {
        if (Lpf2On()) WrU16(FltWant, 5, FieldNumber("tn2", 0, 1000));
        if (DynLpfOn()) { WrU16(FltWant, 15, FieldNumber("tn4", 0, 1000)); WrU16(FltWant, 17, FieldNumber("tn5", 0, 1000)); }
        if (N1On()) { WrU16(FltWant, 7, FieldNumber("tn7", 0, 1000)); WrU16(FltWant, 9, FieldNumber("tn8", 0, 1000)); }
        if (N2On()) { WrU16(FltWant, 11, FieldNumber("tn10", 0, 1000)); WrU16(FltWant, 13, FieldNumber("tn11", 0, 1000)); }
    }
}
// The bytes the page NOT showing owns, compared with what was read: page 1 = lowpass 1 (1-3), dynamic filter (19-24),
// RPM filter (25-26) and the two feature bits; page 2 = lowpass 2 (4-6), notches (7-14), dynamic cutoff (15-18)
static bool FltOtherPageChanged()
{
    if (CurrentView == FILTERVIEW)
        return memcmp(FltWant + 4, FltRaw + 4, 15) != 0;
    return memcmp(FltWant + 1, FltRaw + 1, 3) != 0 || memcmp(FltWant + 19, FltRaw + 19, 8) != 0 || ((FeatWant ^ FeatRaw) & (FEAT_DYN_NOTCH | FEAT_RPM_FILTER)) != 0;
}
static void FltHead()
{
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)"All banks");   // the filters are not per bank
    SendCommand((char *)(Flt_Was_Edited ? "vis b3,1" : "vis b3,0"));
}
static void FltFail(const char *what)
{
    char msg[180];
    snprintf(msg, sizeof(msg), "%s:\r\n%.140s", what, PipeRepCode ? PipeRepBody : "the screen could not ask (no Bluetooth)");
    FltStep = FLT_IDLE;
    FltBusy("");
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)FltPageWord(), msg);
    FltHead();
    FltShow();
}
static void FltRead()
{
    FltBusy("Reading from the flight controller ...");
    FltReq = MspAsk(36, nullptr, 0);
    FltStep = FLT_READ_FEAT;
}
static bool FltTakeFeatures(uint32_t *m)
{
    uint8_t b[8];
    if (PipeReplyBytes(b, sizeof(b)) < 4) return false;
    *m = (uint32_t)b[0] | ((uint32_t)b[1] << 8) | ((uint32_t)b[2] << 16) | ((uint32_t)b[3] << 24);
    return true;
}
static void FltAskFeaturesAgain() // after the restart: the flight controller is asked until it answers
{
    FltWaitUntil = millis() + (FltTries ? 2500 : 5000);
    FltStep = FLT_WAIT;
}
void FilterPoll()
{
    if (CurrentView != FILTERVIEW && CurrentView != FILTER2VIEW) { FltStep = FLT_IDLE; FltMsgUntil = 0; return; }
    if (FltMsgUntil && (int32_t)(millis() - FltMsgUntil) >= 0) { FltMsgUntil = 0; FltBusy(""); FltShow(); }
    if (FltStep == FLT_IDLE) return;
    if (FltStep == FLT_WAIT)
    {
        if ((int32_t)(millis() - FltWaitUntil) < 0) return;
        FltReq = MspAsk(36, nullptr, 0); FltStep = FLT_VERIFY_FEAT; ++FltTries;
        return;
    }
    if (!PipeReplyReady(FltReq))
    {
        if (!PipeReplyLate()) return;
        if (FltStep == FLT_VERIFY_FEAT) { if (FltTries < 5) { FltAskFeaturesAgain(); return; } FltFail("The flight controller has not come back"); return; }
        FltFail("No answer");
        return;
    }
    const bool ok = PipeRepCode == 200;
    switch (FltStep)
    {
    case FLT_READ_FEAT:
        if (!ok || !FltTakeFeatures(&FeatRaw)) { FltFail("Could not read the features"); return; }
        FeatWant = FeatRaw;
        FltReq = MspAsk(92, nullptr, 0); FltStep = FLT_READ;
        return;
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
        if (FeatWant != FeatRaw)
        {
            uint8_t f[4] = {(uint8_t)FeatWant, (uint8_t)(FeatWant >> 8), (uint8_t)(FeatWant >> 16), (uint8_t)(FeatWant >> 24)};
            FltReq = MspAsk(37, f, 4); FltStep = FLT_FEAT;
            return;
        }
        FltReq = MspAsk(250, nullptr, 0); FltStep = FLT_STORE;
        return;
    case FLT_FEAT:
        if (!ok) { FltFail("Not written (the Enable)"); return; }
        FltReq = MspAsk(250, nullptr, 0); FltStep = FLT_STORE;
        return;
    case FLT_STORE:
        if (!ok) { FltFail("Not stored"); return; }
        if (FeatWant != FeatRaw)
        { // an Enable of the Dynamic or the RPM filter changed: it applies only when the flight controller boots (as the configurator, which restarts it on every save)
            FltBusy("Restarting the flight controller (an Enable applies at boot) ...");
            FltReq = MspAsk(68, nullptr, 0); FltStep = FLT_REBOOT;
            return;
        }
        FltReq = MspAsk(92, nullptr, 0); FltStep = FLT_VERIFY;
        return;
    case FLT_REBOOT:
        if (!ok) { FltFail("Not restarted"); return; }
        FltTries = 0;
        FltAskFeaturesAgain();
        return;
    case FLT_VERIFY_FEAT:
    {
        uint32_t m;
        if (!ok || !FltTakeFeatures(&m)) { if (FltTries < 5) { FltAskFeaturesAgain(); return; } FltFail("The flight controller has not come back"); return; }
        FeatRaw = m;
        FltReq = MspAsk(92, nullptr, 0); FltStep = FLT_VERIFY;
        return;
    }
    case FLT_VERIFY:
    {
        if (!ok) { FltFail("Could not read back"); return; }
        uint8_t b[40];
        const int n = PipeReplyBytes(b, sizeof(b));
        bool same = n >= FLT_BYTES && memcmp(b, FltWant, FLT_BYTES) == 0 && (FeatRaw & (FEAT_DYN_NOTCH | FEAT_RPM_FILTER)) == (FeatWant & (FEAT_DYN_NOTCH | FEAT_RPM_FILTER));
        if (n >= FLT_BYTES) { memcpy(FltRaw, b, FLT_BYTES); memcpy(FltWant, b, FLT_BYTES); }
        FeatWant = FeatRaw;
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
    Flt_Was_Edited = false;
    PrevLpf1Type = PrevLpf2Type = 0; PrevLpf1Hz = PrevLpf2Hz = PrevDynMin = PrevDynMax = PrevN1Hz = PrevN1Cut = PrevN2Hz = PrevN2Cut = 0;
    FltHead();
    FltRead();
}
void EndFilterView() // OK on either page
{
    if (Flt_Was_Edited)
    {
        FltGather(); // (B59) before the question's page takes the fields away
        if (!GetConfirmation((char *)FltPageWord(), (char *)"Discard the edited filter values?")) { FltHead(); FltShow(); return; }
    }
    FltStep = FLT_IDLE;
    Flt_Was_Edited = false;
    RotorFlightStart();
}
void StartFilter2View() // Next >
{
    if (CurrentView == FILTERVIEW) FltGather();
    SendCommand((char *)"page Filter2View");
    CurrentView = FILTER2VIEW;
    FltHead();
    if (FltHave) FltShowPage2(); else FltRead();
}
void EndFilter2View() // < Previous
{
    if (CurrentView == FILTER2VIEW) FltGather();
    SendCommand((char *)"page FilterView");
    CurrentView = FILTERVIEW;
    FltHead();
    if (FltHave) FltShowPage1(); else FltRead();
}
void FilterWasEdited() { SendCommand((char *)"vis b3,1"); Flt_Was_Edited = true; }
static void FltEdited() { FltGather(); FilterWasEdited(); }   // a tap on an Enable or a type: the typed numbers first, so none is lost
// A type: the configurator offers 1st order and 2nd order, and keeps another type only while it is the one set
static uint8_t FltNextType(uint8_t t, uint8_t orig)
{
    if (t == 1) return 2;
    if (t == 2) return (orig > 2) ? orig : 1;
    return 1;
}
void FilterLpf1Tapped() { if (!Lpf1On()) return; FltEdited(); FltWant[1] = FltNextType(FltWant[1], FltRaw[1]); FltShow(); }
void FilterLpf2Tapped() { if (!Lpf2On()) return; FltEdited(); FltWant[4] = FltNextType(FltWant[4], FltRaw[4]); FltShow(); }
void FilterPresetTapped() { FltEdited(); FltWant[25] = (uint8_t)((FltWant[25] + 1) % 4); FltShow(); }
// A Yes takes the value that is there if it is not 0, else what was remembered, else the configurator's default (its loadValue)
static uint16_t FltPick(uint16_t cur, uint16_t prev, uint16_t def) { return cur ? cur : prev ? prev : def; }
void FilterLpf1EnableTapped()
{
    FltEdited();
    if (Lpf1On())
    { // the configurator's No: type and cutoff to 0, and the dynamic cutoff with them
        PrevLpf1Type = FltWant[1]; PrevLpf1Hz = RdU16(FltWant, 2);
        if (DynLpfOn()) { PrevDynMin = RdU16(FltWant, 15); PrevDynMax = RdU16(FltWant, 17); }
        FltWant[1] = 0; WrU16(FltWant, 2, 0); WrU16(FltWant, 15, 0); WrU16(FltWant, 17, 0);
    }
    else
    { // Yes: what it had, or the configurator's defaults (1st order, 125 Hz)
        FltWant[1] = (uint8_t)FltPick(0, PrevLpf1Type, 1);
        WrU16(FltWant, 2, FltPick(RdU16(FltWant, 2), PrevLpf1Hz, 125));
        if (PrevDynMin && PrevDynMax) { WrU16(FltWant, 15, PrevDynMin); WrU16(FltWant, 17, PrevDynMax); }
    }
    FltShow();
}
void FilterLpf2EnableTapped()
{
    FltEdited();
    if (Lpf2On()) { PrevLpf2Type = FltWant[4]; PrevLpf2Hz = RdU16(FltWant, 5); FltWant[4] = 0; WrU16(FltWant, 5, 0); }
    else { FltWant[4] = (uint8_t)FltPick(0, PrevLpf2Type, 1); WrU16(FltWant, 5, FltPick(RdU16(FltWant, 5), PrevLpf2Hz, 500)); }
    FltShow();
}
void FilterDynCutoffTapped()
{
    FltEdited();
    if (DynLpfOn()) { PrevDynMin = RdU16(FltWant, 15); PrevDynMax = RdU16(FltWant, 17); WrU16(FltWant, 15, 0); WrU16(FltWant, 17, 0); }
    else
    {
        WrU16(FltWant, 15, FltPick(RdU16(FltWant, 15), PrevDynMin, 50)); WrU16(FltWant, 17, FltPick(RdU16(FltWant, 17), PrevDynMax, 150));
        if (RdU16(FltWant, 15) >= RdU16(FltWant, 17)) { WrU16(FltWant, 15, 50); WrU16(FltWant, 17, 150); }
    }
    FltShow();
}
void FilterNotch1Tapped()
{
    FltEdited();
    if (N1On()) { PrevN1Hz = RdU16(FltWant, 7); PrevN1Cut = RdU16(FltWant, 9); WrU16(FltWant, 7, 0); WrU16(FltWant, 9, 0); }
    else { WrU16(FltWant, 7, FltPick(RdU16(FltWant, 7), PrevN1Hz, 400)); WrU16(FltWant, 9, FltPick(RdU16(FltWant, 9), PrevN1Cut, 300)); }
    FltShow();
}
void FilterNotch2Tapped()
{
    FltEdited();
    if (N2On()) { PrevN2Hz = RdU16(FltWant, 11); PrevN2Cut = RdU16(FltWant, 13); WrU16(FltWant, 11, 0); WrU16(FltWant, 13, 0); }
    else { WrU16(FltWant, 11, FltPick(RdU16(FltWant, 11), PrevN2Hz, 200)); WrU16(FltWant, 13, FltPick(RdU16(FltWant, 13), PrevN2Cut, 100)); }
    FltShow();
}
void FilterDynNotchEnableTapped() { FltEdited(); FeatWant ^= FEAT_DYN_NOTCH; FltShow(); }
void FilterRpmEnableTapped() { FltEdited(); FeatWant ^= FEAT_RPM_FILTER; FltShow(); }
void SaveFilters()
{
    if (!FltHave)
        return;
    char why[120];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)FltPageWord(), why);
        return;
    }
    FltGather();
    if (DynNotchOn() && RdU16(FltWant, 23) <= RdU16(FltWant, 21))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)FltPageWord(), (char *)"Not saved: the dynamic filter's maximum frequency must be above its minimum.");
        FltHead(); FltShow();
        return;
    }
    // B65 (Malcolm, 8 Oct: four Enables touched on the expert page went to the flight controller with a save on page 1,
    // unseen): a save writes both pages, so a change on the OTHER page is said, and asked about, first.
    if (FltOtherPageChanged())
    {
        if (!GetConfirmation((char *)FltPageWord(), (char *)(CurrentView == FILTERVIEW ? "The expert page was changed too\r\n(lowpass 2, dynamic cutoff or notches).\r\nSave both pages?" : "The first page was changed too\r\n(lowpass, dynamic or RPM filter).\r\nSave both pages?")))
        {
            FltHead(); FltShow();
            return;
        }
        FltHead(); FltShow();
    }
    FltBusy("Writing to the flight controller ...");
    FltReq = MspAsk(93, FltWant, FLT_BYTES);
    FltStep = FLT_WRITE;
}
#endif
