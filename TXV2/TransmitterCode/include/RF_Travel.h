// B57: Rotorflight's travel extents on the transmitter (pages TravelView and Travel2View on the screen's card,
// hmi/travel_pages.py), with the configurator's Mixer tab's names, as the receiver's own travel page reads them (RXV2
// data/rotorflight-travel.html, spec RXV2/TRAVEL-EXTENTS-MSP-SPEC.md): the mixer config (MSP 42 read / 43 write, 21
// bytes) and the four mixer inputs roll, pitch, yaw, collective (MSP 174 read one, 171 write one: index, rate, min, max
// as signed words). Angles: 1000 raw = 12 deg on cyclic and collective, 24 deg on yaw; gains in 0.1 %, the sign the
// direction. A save writes 43, then 171 four times, stores (250), and reads it all back to compare.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_TRAVEL_H
#define RF_TRAVEL_H

static const int CFG_BYTES = 21;
static uint8_t TravCfg[CFG_BYTES], TravCfgWant[CFG_BYTES];
static int16_t TravIn[5][3], TravInWant[5][3];       // inputs 1..4 (index 0 unused): rate, min, max
static bool TravHave = false, Trav_Was_Edited = false;
static int TravRevAil = 0, TravRevEle = 0, TravRevColl = 0;
enum { TRV_IDLE = 0, TRV_READ_CFG, TRV_READ_IN, TRV_WRITE_CFG, TRV_WRITE_IN, TRV_STORE, TRV_VERIFY_CFG, TRV_VERIFY_IN };
static int TravStep = TRV_IDLE, TravReq = 0, TravIdx = 1;
static bool TravReadAgainWanted = false;
static uint32_t TravMsgUntil = 0;

static void TravBusy(const char *msg)
{
    SendCommand((char *)(msg && *msg ? "vis busy,1" : "vis busy,0"));
    if (msg && *msg)
        SendText((char *)"busy", (char *)msg);
}
static void TravTenths(const char *name, long tenths) // -12.5
{
    char b[16];
    const long a = tenths < 0 ? -tenths : tenths;
    snprintf(b, sizeof(b), "%s%ld.%ld", tenths < 0 ? "-" : "", a / 10, a % 10);
    SendText((char *)name, b);
}
static void TravNum(const char *name, long v)
{
    char b[16];
    snprintf(b, sizeof(b), "%ld", v);
    SendText((char *)name, b);
}
static long RawToDegTenths(long raw, int perThousand) { return (raw * perThousand * 10 + (raw < 0 ? -500 : 500)) / 1000; }   // 1000 raw = 12 (or 24) deg -> tenths
static long DegTenthsToRaw(long tenths, int perThousand) { return (tenths * 100 + (tenths < 0 ? -perThousand / 2 : perThousand / 2)) / perThousand; }
static int16_t S16At(const uint8_t *b, int o) { const int v = b[o] | (b[o + 1] << 8); return (int16_t)(v > 32767 ? v - 65536 : v); }
static void PutS16(uint8_t *b, int o, long v) { if (v < -32768) v = -32768; if (v > 32767) v = 32767; const uint16_t u = (uint16_t)(v & 0xFFFF); b[o] = u & 0xFF; b[o + 1] = u >> 8; }
static bool TailMotorised() { return TravCfg[1] != 0; }   // tail_rotor_mode: 0 variable pitch, else motorised / bidirectional
static int TailScale() { return TailMotorised() ? 1 : 24; } // motorised: 0.1 %; variable pitch: 1000 raw = 24 deg

static void TravShowPage1()
{
    TravTenths("tn0", RawToDegTenths(TravInWant[4][2], 12));        // Collective pitch limit: input 4's max
    TravTenths("tn1", RawToDegTenths(TravInWant[2][2], 12));        // Cyclic pitch limit: input 2's max
    TravTenths("tn2", RawToDegTenths(S16At(TravCfgWant, 9), 12));   // Total pitch limit
    TravNum("tn3", (labs(TravInWant[4][0]) + 5) / 10);              // Collective gain %
    TravNum("tn4", (labs(TravInWant[1][0]) + 5) / 10);              // Cyclic gain % (roll's; pitch gets the same on a save)
    TravNum("tn5", (labs(TravInWant[3][0]) + 5) / 10);              // Yaw gain %
    TravRevAil = TravInWant[1][0] < 0; TravRevEle = TravInWant[2][0] < 0; TravRevColl = TravInWant[4][0] < 0;
    SendText((char *)"tn6", (char *)(TravRevAil ? "Yes" : "No"));
    SendText((char *)"tn7", (char *)(TravRevEle ? "Yes" : "No"));
    SendText((char *)"tn8", (char *)(TravRevColl ? "Yes" : "No"));
    TravTenths("tn9", S16At(TravCfgWant, 11));                      // swash trims, 0.1 %
    TravTenths("tn10", S16At(TravCfgWant, 13));
    TravTenths("tn11", S16At(TravCfgWant, 15));
}
static void TravShowPage2()
{
    const int ts = TailScale();
    if (TailMotorised()) { TravTenths("tn0", labs(TravInWant[3][1])); TravTenths("tn1", TravInWant[3][2]); TravTenths("tn2", S16At(TravCfgWant, 3)); }
    else { TravTenths("tn0", RawToDegTenths(labs(TravInWant[3][1]), ts)); TravTenths("tn1", RawToDegTenths(TravInWant[3][2], ts)); TravTenths("tn2", RawToDegTenths(S16At(TravCfgWant, 3), ts)); }
    SendText((char *)"ltn0", (char *)(TailMotorised() ? "Tail min [%]" : "Tail yaw min [deg]"));
    SendText((char *)"ltn1", (char *)(TailMotorised() ? "Tail max [%]" : "Tail yaw max [deg]"));
    TravTenths("tn3", TravCfgWant[2]);                              // tail motor idle, 0.1 %
    TravTenths("tn4", S16At(TravCfgWant, 7));                       // phase angle, 0.1 deg
    TravNum("tn5", TravCfgWant[6]);                                 // swash ring %
    { const int geo = TravCfgWant[18] > 127 ? TravCfgWant[18] - 256 : TravCfgWant[18]; TravTenths("tn6", geo * 2); }   // geo correction: raw/5, shown to one decimal (raw 3 = 0.6)
    TravNum("tn7", TravCfgWant[19] > 127 ? TravCfgWant[19] - 256 : TravCfgWant[19]);
    TravNum("tn8", TravCfgWant[20] > 127 ? TravCfgWant[20] - 256 : TravCfgWant[20]);
}
static void TravShow()
{
    if (CurrentView == TRAVELVIEW) TravShowPage1();
    else if (CurrentView == TRAVEL2VIEW) TravShowPage2();
}
static long FieldTenthsL(const char *name, long lo, long hi) // "-12.5" -> -125
{
    char t[24] = "";
    GetText((char *)name, t, sizeof(t) - 1);
    const float f = (float)atof(t);
    long v = (long)(f * 10.0f + (f >= 0 ? 0.5f : -0.5f));
    return v < lo ? lo : v > hi ? hi : v;
}
static void TravGatherPage1()
{
    const long coll = DegTenthsToRaw(FieldTenthsL("tn0", 0, 300), 12), cyc = DegTenthsToRaw(FieldTenthsL("tn1", 0, 300), 12);
    TravInWant[4][1] = (int16_t)-coll; TravInWant[4][2] = (int16_t)coll;
    TravInWant[1][1] = TravInWant[2][1] = (int16_t)-cyc; TravInWant[1][2] = TravInWant[2][2] = (int16_t)cyc;
    PutS16(TravCfgWant, 9, DegTenthsToRaw(FieldTenthsL("tn2", 0, 360), 12));
    const long gColl = FieldNumber("tn3", 0, 1000) * 10, gCyc = FieldNumber("tn4", 0, 1000) * 10, gYaw = FieldNumber("tn5", 0, 1000) * 10;
    TravInWant[4][0] = (int16_t)(TravRevColl ? -gColl : gColl);
    TravInWant[1][0] = (int16_t)(TravRevAil ? -gCyc : gCyc);
    TravInWant[2][0] = (int16_t)(TravRevEle ? -gCyc : gCyc);
    TravInWant[3][0] = (int16_t)(TravIn[3][0] < 0 ? -gYaw : gYaw);   // the yaw direction stays as it is
    PutS16(TravCfgWant, 11, FieldTenthsL("tn9", -1000, 1000));
    PutS16(TravCfgWant, 13, FieldTenthsL("tn10", -1000, 1000));
    PutS16(TravCfgWant, 15, FieldTenthsL("tn11", -1000, 1000));
}
static void TravGatherPage2()
{
    const int ts = TailScale();
    long tmin, tmax, ctr;
    if (TailMotorised()) { tmin = FieldTenthsL("tn0", 0, 2500); tmax = FieldTenthsL("tn1", 0, 2500); ctr = FieldTenthsL("tn2", -1000, 1000); }
    else { tmin = DegTenthsToRaw(FieldTenthsL("tn0", 0, 600), ts); tmax = DegTenthsToRaw(FieldTenthsL("tn1", 0, 600), ts); ctr = DegTenthsToRaw(FieldTenthsL("tn2", -240, 240), ts); }
    TravInWant[3][1] = (int16_t)-tmin; TravInWant[3][2] = (int16_t)tmax;
    PutS16(TravCfgWant, 3, ctr);
    TravCfgWant[2] = (uint8_t)FieldTenthsL("tn3", 0, 250);
    PutS16(TravCfgWant, 7, FieldTenthsL("tn4", -1800, 1800));
    TravCfgWant[6] = (uint8_t)FieldNumber("tn5", 0, 100);
    { const long g = FieldTenthsL("tn6", -250, 250); const long raw = (g * 5 + (g < 0 ? -5 : 5)) / 10; TravCfgWant[18] = (uint8_t)(raw & 0xFF); }   // ui/5 -> raw: ui 0.6 (6 tenths) -> 3
    TravCfgWant[19] = (uint8_t)(FieldNumber("tn7", -100, 100) & 0xFF);
    TravCfgWant[20] = (uint8_t)(FieldNumber("tn8", -100, 100) & 0xFF);
}
static void TravPageHead();
static void TravFail(const char *what)
{
    char msg[180];
    snprintf(msg, sizeof(msg), "%s:\r\n%.140s", what, PipeRepCode ? PipeRepBody : "the screen could not ask (no Bluetooth)");
    TravStep = TRV_IDLE;
    TravBusy("");
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)(CurrentView == TRAVEL2VIEW ? "page Travel2View" : "page TravelView"), msg);
    TravPageHead();
    TravShow();
}
static void TravAskInput(int idx, int step)
{
    const uint8_t b = (uint8_t)idx;
    TravIdx = idx;
    TravReq = MspAsk(174, &b, 1);
    TravStep = step;
}
static void TravRead()
{
    TravBusy("Reading from the flight controller ...");
    TravReq = MspAsk(42, nullptr, 0);
    TravStep = TRV_READ_CFG;
}
static bool TravTakeInput(int16_t (*in)[3]) // the reply of a 174: rate, min, max
{
    uint8_t b[16];
    const int n = PipeReplyBytes(b, sizeof(b));
    if (n < 6) return false;
    in[TravIdx][0] = S16At(b, 0); in[TravIdx][1] = S16At(b, 2); in[TravIdx][2] = S16At(b, 4);
    return true;
}
void TravelPoll()
{
    if (CurrentView != TRAVELVIEW && CurrentView != TRAVEL2VIEW) { TravStep = TRV_IDLE; TravMsgUntil = 0; return; }
    if (TravMsgUntil && (int32_t)(millis() - TravMsgUntil) >= 0) { TravMsgUntil = 0; TravBusy(""); TravShow(); }
    if (TravStep == TRV_IDLE) { if (TravReadAgainWanted) { TravReadAgainWanted = false; TravRead(); } return; }
    if (!PipeReplyReady(TravReq)) { if (PipeReplyLate()) TravFail("No answer"); return; }
    const bool ok = PipeRepCode == 200;
    static int16_t check[5][3];
    switch (TravStep)
    {
    case TRV_READ_CFG:
    {
        if (!ok) { TravFail("Could not read the mixer"); return; }
        uint8_t b[32];
        const int n = PipeReplyBytes(b, sizeof(b));
        if (n < CFG_BYTES) { snprintf(PipeRepBody, sizeof(PipeRepBody), "only %d bytes came (Rotorflight 2.3 sends 21)", n); TravFail("Could not read the mixer"); return; }
        memcpy(TravCfg, b, CFG_BYTES);
        TravAskInput(1, TRV_READ_IN);
        return;
    }
    case TRV_READ_IN:
        if (!ok || !TravTakeInput(TravIn)) { TravFail("Could not read a mixer input"); return; }
        if (TravIdx < 4) { TravAskInput(TravIdx + 1, TRV_READ_IN); return; }
        memcpy(TravCfgWant, TravCfg, CFG_BYTES); memcpy(TravInWant, TravIn, sizeof(TravIn));
        TravHave = true; TravStep = TRV_IDLE; Trav_Was_Edited = false;
        TravBusy(""); SendCommand((char *)"vis b3,0"); TravShow();
        return;
    case TRV_WRITE_CFG:
        if (!ok) { TravFail("Not written (mixer)"); return; }
        TravIdx = 1;
        { uint8_t f[7]; f[0] = 1; PutS16(f, 1, TravInWant[1][0]); PutS16(f, 3, TravInWant[1][1]); PutS16(f, 5, TravInWant[1][2]); TravReq = MspAsk(171, f, 7); TravStep = TRV_WRITE_IN; }
        return;
    case TRV_WRITE_IN:
        if (!ok) { TravFail("Not written (an input)"); return; }
        if (TravIdx < 4) { ++TravIdx; uint8_t f[7]; f[0] = (uint8_t)TravIdx; PutS16(f, 1, TravInWant[TravIdx][0]); PutS16(f, 3, TravInWant[TravIdx][1]); PutS16(f, 5, TravInWant[TravIdx][2]); TravReq = MspAsk(171, f, 7); return; }
        TravReq = MspAsk(250, nullptr, 0); TravStep = TRV_STORE;
        return;
    case TRV_STORE:
        if (!ok) { TravFail("Not stored"); return; }
        TravReq = MspAsk(42, nullptr, 0); TravStep = TRV_VERIFY_CFG;
        return;
    case TRV_VERIFY_CFG:
    {
        if (!ok) { TravFail("Could not read back"); return; }
        uint8_t b[32];
        const int n = PipeReplyBytes(b, sizeof(b));
        if (n >= CFG_BYTES) memcpy(TravCfg, b, CFG_BYTES);
        TravAskInput(1, TRV_VERIFY_IN);
        return;
    }
    case TRV_VERIFY_IN:
    {
        if (!ok || !TravTakeInput(check)) { TravFail("Could not read back an input"); return; }
        if (TravIdx < 4) { TravAskInput(TravIdx + 1, TRV_VERIFY_IN); return; }
        memcpy(TravIn, check, sizeof(TravIn));
        bool same = memcmp(TravCfg + 2, TravCfgWant + 2, CFG_BYTES - 2) == 0;   // (the type bytes 0 and 1 are not ours)
        for (int i = 1; i <= 4 && same; ++i) for (int k = 0; k < 3; ++k) if (TravIn[i][k] != TravInWant[i][k]) same = false;
        memcpy(TravCfgWant, TravCfg, CFG_BYTES); memcpy(TravInWant, TravIn, sizeof(TravIn));
        TravStep = TRV_IDLE; Trav_Was_Edited = false;
        SendCommand((char *)"vis b3,0"); TravShow();
        TravBusy(same ? "Saved, and read back the same." : "Saved; the flight controller adjusted some values (shown).");
        TravMsgUntil = millis() + 4000;
        PlaySound(BEEPCOMPLETE);
        return;
    }
    default:
        TravStep = TRV_IDLE;
        return;
    }
}
static void TravPageHead()
{
    SendText((char *)"t11", ModelName);
    char b[16];
    snprintf(b, sizeof(b), "Bank %d", Bank);
    SendText((char *)"t9", b);
    SendCommand((char *)(Trav_Was_Edited ? "vis b3,1" : "vis b3,0"));
}
void StartTravelView()
{
    char why[120];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFView", why);
        return;
    }
    SendCommand((char *)"page TravelView");
    CurrentView = TRAVELVIEW;
    Trav_Was_Edited = false;
    TravPageHead();
    TravRead();
}
void EndTravelView() // OK on either page
{
    if (Trav_Was_Edited)
    {
        if (CurrentView == TRAVELVIEW) TravGatherPage1(); else TravGatherPage2();   // (B59) before the question's page takes the fields away
        if (!GetConfirmation((char *)(CurrentView == TRAVEL2VIEW ? "page Travel2View" : "page TravelView"), (char *)"Discard the edited travel extents?"))
        {
            TravPageHead();
            TravShow();
            return;
        }
    }
    TravStep = TRV_IDLE;
    Trav_Was_Edited = false;
    RotorFlightStart();
}
void TravelWasEdited() { SendCommand((char *)"vis b3,1"); Trav_Was_Edited = true; }
void TravelAilTapped() { TravRevAil = !TravRevAil; SendText((char *)"tn6", (char *)(TravRevAil ? "Yes" : "No")); TravelWasEdited(); }
void TravelEleTapped() { TravRevEle = !TravRevEle; SendText((char *)"tn7", (char *)(TravRevEle ? "Yes" : "No")); TravelWasEdited(); }
void TravelCollTapped() { TravRevColl = !TravRevColl; SendText((char *)"tn8", (char *)(TravRevColl ? "Yes" : "No")); TravelWasEdited(); }
void SaveTravel()
{
    if (!TravHave)
        return;
    char why[120];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)(CurrentView == TRAVEL2VIEW ? "page Travel2View" : "page TravelView"), why);
        return;
    }
    // B59: the fields FIRST. The question is a page of its own, and the travel page comes back from it reloaded, every
    // field blank: read after the question, they were zeros, and zeros were written (Malcolm, 7 Oct: "It wrote zero").
    if (CurrentView == TRAVELVIEW) TravGatherPage1(); else TravGatherPage2();
    if (!GetConfirmation((char *)(CurrentView == TRAVEL2VIEW ? "page Travel2View" : "page TravelView"), (char *)"Save the travel extents?\r\nThey change how FAR the swash and tail move:\r\ncheck them on the bench, blades off."))
    {
        TravPageHead();
        TravShow(); // the page came back blank: the edited values again
        return;
    }
    TravPageHead();
    TravShow();
    TravBusy("Writing to the flight controller ...");
    TravReq = MspAsk(43, TravCfgWant, CFG_BYTES);
    TravStep = TRV_WRITE_CFG;
}
void StartTravel2View() // Next >
{
    if (CurrentView == TRAVELVIEW) TravGatherPage1();
    SendCommand((char *)"page Travel2View");
    CurrentView = TRAVEL2VIEW;
    TravPageHead();
    if (TravHave) TravShowPage2(); else TravRead();
}
void EndTravel2View() // < Previous
{
    TravGatherPage2();
    SendCommand((char *)"page TravelView");
    CurrentView = TRAVELVIEW;
    TravPageHead();
    if (TravHave) TravShowPage1();
}
#endif
