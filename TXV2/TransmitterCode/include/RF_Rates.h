// **********************************************************************************************************
// This file handles basic rates editing for Rotorflight
// It uses a factors' table to convert between screen display values and the actual byte values needed by Rotorflight
// **********************************************************************************************************

#ifndef RATESRF_H
#define RATESRF_H
#include <Arduino.h>
#include "1Definitions.h"
FLASHMEM void Modify_Labels_For_RATES_View();

// B08: the scales and the headings come from the BANK'S rates type (byte 0), not from the firmware version. Rotorflight
// 2.3's own type (6, "Rotorflight 2.3") has Rate / Shape / Expo columns (rate x5, x0.125 on the collective); every other
// type (Actual, Betaflight, ...) keeps the Centre / Max / Expo scales of 2.2, whatever the firmware. Before, every bank on
// a 2.3 flight controller got the type-6 scales: an Actual bank showed half its centre rate and a tenth of its max rate,
// and typing 200 wrote a value the flight controller read as 400 deg/s.
FLASHMEM bool RatesTypeIsRf23(uint8_t type) { return RotorFlight_V >= 2 && type == 6; }
FLASHMEM const float *RatesFactors(uint8_t type) { return RatesTypeIsRf23(type) ? FactorTableRF2_3 : FactorTableRF2_2; }
// ************************************************************************************************************/
float GetFactoredValue(uint8_t i) // this function gets the value to show
{
    return Rate_Values[i] * RatesFactors(Rate_Values[0])[i]; // MULTIPLY BY factor to get display value
}
// B07: a typed value too big for its byte wrapped round (a rate of 1300 went as 20 deg/s, a collective of 40 deg as 8 deg),
// and the screen kept showing what was typed. Now it is cut to what the byte holds, the pilot is told, and the page shows
// what was written. (Rounded to the nearest byte too: 0.3 / 0.01 came out 29, not 30.)
FLASHMEM uint8_t RfByteOf(float v)
{
    if (v < 0.0f)
    {
        RfValueWasCut = true;
        return 0;
    }
    if (v > 255.0f)
    {
        RfValueWasCut = true;
        return 255;
    }
    return (uint8_t)(v + 0.5f);
}
FLASHMEM void RfCutNote(const char *page) // after a save whose values were cut: the page shows them as written (the caller), the pilot told
{
    if (!RfValueWasCut)
        return;
    RfValueWasCut = false;
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)page, (char *)"A value was too big for Rotorflight and\r\nwas cut to the largest it can hold.\r\nThe page shows what was saved: check it.");
}

// ************************************************************************************************************/
FLASHMEM void ReadEditedRateValues()
{
    const float *f = RatesFactors(Rate_Values[0]);
    for (int i = 1; i < MAX_RATES_BYTES; ++i) // start at 1 because 0 is Rates Type and not yet edited here
    {
        char temp[10];
        if (GetText(RatesWindows[i], temp, sizeof(temp)) == 0) continue;   // B152: a box the screen did not answer for keeps the value in hand (NextionTextMissed: a save stops)
        Rate_Values[i] = RfByteOf((float)atof(temp) / f[i]); // DIVIDE BY factor to get byte value (B07: cut, never wrapped)
    }
}

// ************************************************************************************************************/
FLASHMEM void SaveRatesLocalBank()
{
    RatesMsg((char *)"Saving edited rates ...", Gray); // Show sending message
    Rates_Were_Edited = false;
    // (B08 took the saved bank's own type here - before, every local save made it "Actual". B106: the page's type, which
    // ShowRatesLocalBank set from the saved bank and the picker may have changed; one Rotorflight does not have is refused
    // by SendEditedRates. NONE (0) is kept: a never-filled bank was made "Actual" with zero rates, NONE flies 500 deg/s.)
    NextionTextMissed = false;
    ReadEditedRateValues();
    if (RfFieldsMissed("page RatesView")) { Rates_Were_Edited = true; HideRATESMsg(); return; }   // B152: a box unanswered: nothing saved
    for (int i = 0; i < MAX_RATES_BYTES; ++i)
    {
        Saved_Rate_Values[i][DualRateInUse - 1] = Rate_Values[i];
    }
    SaveOneModel(ModelNumber);       // save all to SD card
    HideRATESMsg();                  // ...because this queue is a LIFO stack
    SendCommand((char *)"vis b3,0"); // hide "Send" button
    PlaySound(BEEPCOMPLETE);         // let user know we're done
    if (RfValueWasCut)
    { // B07
        DisplayRatesValues(1, MAX_RATES_BYTES);
        RfCutNote("page RatesView");
    }
}
// ************************************************************************************************************/
FLASHMEM static void RatesQueueWrite();   // (B102: below)
FLASHMEM bool RatesTypeBad(const char *page);   // (B106: below)
FLASHMEM void SendEditedRates()
{
    if (RatesTypeBad("page RatesView")) // B106: a type Rotorflight does not have is never sent, nor kept
        return;
    if (!RfLive()) // Model not connected so save to local RATES
    {
        SaveRatesLocalBank();
        return;
    }
    {
        char why[120];
        if (RfPipeBlocked(why, sizeof(why))) // B48: the pipe went while the page was open
        {
            MsgBox((char *)"page RatesView", why);
            return;
        }
    }
    BlockBankChanges = true;
    PlaySound(BEEPMIDDLE);
    DelayWithDog(100);                                  // allow LOTS of time for screen to update BEFORE sending another Nextion command
    RatesMsg((char *)"Sending edited rates ...", Gray); // Show sending message
    NextionTextMissed = false;
    ReadEditedRateValues();                             // read the edited RATES from the screen
    if (RfFieldsMissed("page RatesView")) { BlockBankChanges = false; HideRATESMsg(); return; }   // B152: a box unanswered: nothing sent
    BankCheck(true, DualRateInUse, RatesQueueWrite, "page RatesView");   // B102: into this rates bank, or not at all (the edited flag stays until then)
}
// ************************************************************************************************************/
FLASHMEM char *FixDecimalDisplay(char *temp, float ThisValue, uint8_t i, size_t tempSize) // this function removes trailing zeros and decimal point if not needed and also rounds to 2 decimal places if needed
{
    const bool rf23 = RatesTypeIsRf23(Rate_Values[0]); // B08: the decimals follow the scale table in use
    if (!rf23)
    {
        if (ThisValue == int(ThisValue))
        {
            if (i < 10)
            {
                snprintf(temp, tempSize, "%.0f", ThisValue);
            }
            else
            {
                snprintf(temp, tempSize, "%.1f", ThisValue);
            }
        }
        else
        {
            snprintf(temp, tempSize, "%.2f", ThisValue);
        }
    }

    if (rf23)
    {
        if (ThisValue == int(ThisValue))
        {
            if (i != 10)
            {
                snprintf(temp, tempSize, "%.0f", ThisValue);
            }
            else
            {
                snprintf(temp, tempSize, "%.2f", ThisValue);
            }
        }
        else
        {
            snprintf(temp, tempSize, "%.2f", ThisValue);
        }
    }

    return temp;
}

// ************************************************************************************************************/
FLASHMEM void DisplayRatesValues(uint8_t startIndex, uint8_t stopIndex) // Displays RATES values on screen a few at a time as they arrive in Ack payloads
{
    for (uint8_t i = startIndex; i < stopIndex; ++i)
    {
        if (i < MAX_RATES_BYTES)
        {
            char temp[10];
            if (i == 0)
            {
                SendText(RatesWindows[0], (char *)(Rate_Values[0] <= 6 ? Rate_Types[Rate_Values[0]] : "?")); // the rates type (B106: tapped, its picker)
                Modify_Labels_For_RATES_View(); // B08: the headings follow the type
                continue;
            }
            float ThisValue = GetFactoredValue(i);
            FixDecimalDisplay(temp, ThisValue, i, sizeof(temp));
            SendText(RatesWindows[i], temp);
        }
    }
}

// ********************************************************************************************************
FLASHMEM void ForegroundColourRATESLabels(uint16_t Colour)
{
    for (int i = 1; i < 13; ++i)
    {
        SendForegroundColour(RatesWindows[i], Colour);
    }
}
// ********************************************************************************************************
FLASHMEM void RatesMsg(const char *msg, uint16_t Colour)
{
    if (CurrentView == RATESVIEW_RF) // Must be in RATES view
    {
        ForegroundColourRATESLabels(Colour);   // make text white so it isn't visible
        SendText((char *)"busy", (char *)msg); // Show RATES message
        SendCommand((char *)"vis busy,1");     // Make it visible
        SendCommand((char *)"vis b2,0");       // Make Advanced invisible
        SendCommand((char *)"vis b4,0");       // B107: and "Curves ..."
        SendCommand((char *)"vis b3,0");       // hide "Send" button
    }
}

// ************************************************************************************************************/
FLASHMEM void HideRATESMsg()
{
    if (CurrentView == RATESVIEW_RF) // Must be in RATES view
    {
        SendCommand((char *)"vis busy,0");  // Hide  message
        SendCommand((char *)"vis b2,1");    // Make Advanced visible
        SendCommand((char *)"vis b4,1");    // B107: and "Curves ..."
        ForegroundColourRATESLabels(Black); // make text black so it is visible again
    }
    BlockBankChanges = false; // ALWAYS clear — a view change before this call
                              // must never leave the bank switch dead (ClaudeFix 25-8-2026)
}

// ******************************************************************************************************************************/
FLASHMEM void ShowRatesLocalBank()
{
    Rate_Values[0] = Saved_Rate_Values[0][DualRateInUse - 1]; // B08: the saved bank's type chooses the scales (and the edits' later)
    const float *f = RatesFactors(Rate_Values[0]);
    Modify_Labels_For_RATES_View();
    for (int i = 0; i < MAX_RATES_BYTES; ++i)
    {
        float ThisValue;
        char temp[10];
        ThisValue = (Saved_Rate_Values[i][DualRateInUse - 1] * f[i]); // MULTIPLY BY factor to get display value
        FixDecimalDisplay(temp, ThisValue, i, sizeof(temp));
        if (i == 0)
            SendText(RatesWindows[0], (char *)(Rate_Values[0] <= 6 ? Rate_Types[Rate_Values[0]] : "?")); // the rates type (B106: tapped, its picker)
        else
            SendText(RatesWindows[i], temp);
    }
    HideRATESMsg();    
    SendCommand((char *)"vis b3,0"); // hide "Send" button
    BlockBankChanges = false;
}
// ******************************************************************************************************************************/

// B102: the read, and the write once the flight controller is known to be on this rates bank (PipeHttp.h BankCheck)
FLASHMEM static void RatesAskValues()
{
    if (CurrentView != RATESVIEW_RF) { BlockBankChanges = false; return; }
    RATES_Send_Duration = MSP_WAIT_TIME;     // how many milliseconds to await RATES values
    Reading_RATES_Now = true;                // This tells the Ack payload parser to get RATES values
    AddParameterstoQueue(SEND_RATES_VALUES); // Request RATES values from RX
    RATES_Start_Time = millis();             // record start time as it's not long
}
FLASHMEM static void RatesQueueWrite()
{
    Rates_Were_Edited = false;
    Wait_for_Advanced_Rates_to_Be_Sent_Too = false;     // this flag tells the Ack payload parser not to wait until these have been sent before allowing bank changes again because rates changes can cause problems if a bank change happens while they are being sent
    const bool readBack = RfVerifyArm(VK_RATES, RatesAskValues);   // B153: the block is read back after the write and compared with what was sent (the read queued first: the stack sends it last)
    AddParameterstoQueue(GET_SECOND_6_RATES_VALUES);    // SECOND MUST BE QUEUED FIRST!!! Send RATES 7-12 values from TX to RX
    AddParameterstoQueue(GET_FIRST_7_RATES_VALUES);     // SECOND MUST BE QUEUED FIRST!!! Send RATES 1-6 values from TX to RX
    if (readBack) return;                               // "reading back ..." stays up: the verdict does the rest (RF_Verify.h)
    if (CurrentView == RATESVIEW_RF)
    {
        HideRATESMsg();                                 // ...because this queue is a LIFO stack
        SendCommand((char *)"vis b3,0");                // hide "Send" button
    }
    PlaySound(BEEPCOMPLETE);                            // let user know we're done
    if (RfValueWasCut && CurrentView == RATESVIEW_RF)
    { // B07
        DisplayRatesValues(1, MAX_RATES_BYTES);
        RfCutNote("page RatesView");
    }
    RfSavedThenLeave(RATESVIEW_RF);                     // B102: OK's "Save now?" closes the page once saved
}
FLASHMEM void ShowRatesBank()
{
    if (CurrentView == RATESVIEW_RF) // Must be in RATES view
    {
        char buf[40];
        char Rmsg[50];
        char NB[10];

        snprintf(Rmsg, sizeof(Rmsg), "Rate %u", (unsigned)DualRateInUse);
        SendText((char *)"t9", Rmsg); // Show rate number etc

        if (RfLive())
        {
            strcpy(buf, "Loading rates for Rate ");
            strcat(buf, Str(NB, DualRateInUse, 0));
        }
        else
        {
            ShowRatesLocalBank(); // Model not connected so show local saved RATES
            return;
        }

        if (Rates_Were_Edited) // if RATES were edited but not sent and bank changed
        {
            char w1[] = "Values for last Rate were edited \r\nbut not saved. (Too late now!)\r\nSo you may want to check them.";
            MsgBox((char *)"page RatesView", w1); // Warn about unsaved edits
        }
        RatesMsg(buf, Gray);
        BlockBankChanges = true;
        Rates_Were_Edited = false;               // reset edited flag
        RatesAskValues();
    }
}
// ******************************************************************************************************************************/
FLASHMEM void Modify_Labels_For_RATES_View()
{ // make sure labels are correct for RATES view in Rotorflight because some are different than for Betaflight etc

    if (CurrentView != RATESVIEW_RF)
        return;
    if (RatesTypeIsRf23(Rate_Values[0])) // B08: by the bank's type, not the firmware
    {
        SendText((char *)"t4", (char *)""); // (15 Oct: the phone app's corner is empty; it said Axis)
        SendText((char *)"t5", (char *)"Rate");
        SendText((char *)"t6", (char *)"Shape");
    }else{
        SendText((char *)"t4", (char *)"");
        SendText((char *)"t5", (char *)"Centre");   // (the phone app's word)
        SendText((char *)"t6", (char *)"Max rate");
    }
}
// ******************************************************************************************************************************/
FLASHMEM void StartRFRatesView()
{
    char why[80];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why))) // B45: says what it saw; B47/B48: or the pipe is not ready (joining, or none)
    {
        PlaySound(WHAHWHAHMSG); // let user know we're in trouble
        MsgBox((char *)"page RFView", why);
        return;
    }
    SendCommand((char *)"page RatesView");
    CurrentView = RATESVIEW_RF;
    Modify_Labels_For_RATES_View();     // make sure labels are correct for RATES view
    ShowRatesBank();                    // Show the current bank's RATES
    SendText((char *)"t11", ModelName); // Show model name
    Rates_Were_Edited = false;
}
// ******************************************************************************************************************************/
FLASHMEM void EndRFRatesView()
{
    if (Rates_Were_Edited)
    {
        if (!RfSaveFirst("page RatesView", "The edited rates are", SendEditedRates, EndRFRatesView, &Rates_Were_Edited)) return;   // B102: "Save now?"
    }
    Rates_Were_Edited = false;
    RotorFlightStart();
    BlockBankChanges = false;
}
// ************************************************************************************************************/
FLASHMEM void RatesWereEdited()
{
    SendCommand((char *)"vis b3,1"); // show "Send" button
    Rates_Were_Edited = true;
}
// ************************************************************************************************************/
// B106 (Malcolm, 16 Oct 2026, a photo of this page: "On the transmitter, we can see the rates type, but we cannot edit it.
// Please can we add that in?" - he had changed the Havok's type to ACTUAL on the iPhone and kept its numbers: Rotorflight's
// own Rate 250 / Shape 12 / Expo 40 then read as Centre 500 / Max rate 120, a straight 500 deg/s, and the collective's
// 12.5 deg as 25). The type is tapped: a picker page (RatesTypeView) of Rotorflight's seven types; its OK puts the bank's
// rates to the chosen type's starting values - as Rotorflight's Configurator does ("If you change the rates type your
// rates will be set to a default curve") - and Save writes them; nothing is sent before Save. Cancel changes nothing.
// The starting values are the Configurator 2.3.0's (rates tab, initRatesSystem), as bytes in this page's order (per axis
// Centre or Rate, Max rate or Shape, Expo): each gives about 240 deg/s roll and pitch, 400 yaw and 12.5 deg of collective
// at full stick - but for the Configurator's QUICKRATES collective (its 500 is a 104, 26 deg in the firmware's formula):
// 50 here, 12.5 deg like the rest. The phone's Rates page has the same table (rotorflight-rates.html RATES_START; the
// receiver's dev/ratestype_test.js checks that they agree, and the full-stick rates in Rotorflight's own formulas).
static const uint8_t RatesStart[7][MAX_RATES_BYTES - 1] PROGMEM = {
    {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},              // 0 NONE (its numbers are not used: 500 deg/s, 12.5 deg)
    {120, 0, 0, 120, 0, 0, 200, 0, 0, 203, 1, 0},     // 1 BETAFLIGHT
    {24, 0, 0, 24, 0, 0, 40, 0, 0, 50, 0, 0},         // 2 RACEFLIGHT
    {120, 0, 0, 120, 0, 0, 200, 0, 0, 250, 0, 0},     // 3 KISS
    {18, 24, 0, 18, 24, 0, 18, 40, 0, 50, 50, 0},     // 4 ACTUAL: Centre 180, Max rate 240 (yaw 400), collective 12.5 / 12.5
    {120, 24, 0, 120, 24, 0, 200, 40, 0, 250, 50, 0}, // 5 QUICKRATES
    {50, 12, 40, 50, 12, 40, 80, 12, 50, 100, 12, 0}, // 6 ROTORFLIGHT: Rate 250 (yaw 400), Shape 12, Expo 40 (yaw 50), collective 12.5
};
FLASHMEM bool RatesTypeKnown(uint8_t t) { return t < 6 || (t == 6 && RotorFlight_V != 1); }   // (ROTORFLIGHT came with Rotorflight 2.3)
FLASHMEM bool RatesTypeBad(const char *page)
{
    if (RatesTypeKnown(Rate_Values[0]))
        return false;
    char m[150];
    snprintf(m, sizeof(m), "Not saved: the rates type is %u, which\r\nthis Rotorflight does not have.\r\nTap the type to choose one.", Rate_Values[0]);
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)page, m);
    return true;
}
static uint8_t RatesAwayBank = 0;   // the rates bank the picker (or the curves, B107) was opened on
FLASHMEM void RatesTypeTapped() // the type tapped: the picker, at the bank's own type
{
    if (CurrentView != RATESVIEW_RF || Reading_RATES_Now || ParametersToBeSentPointer)
        return; // (reading or sending: the page's note covers the type)
    ReadEditedRateValues(); // what the page shows (typed or not), kept through the picker - Cancel brings it back
    RatesAwayBank = DualRateInUse;
    SendCommand((char *)"page RatesTypeView");
    CurrentView = RATESTYPEVIEW;
    char b[16];
    snprintf(b, sizeof(b), "Rate %u", (unsigned)DualRateInUse);
    SendText((char *)"t9", b);
    SendText((char *)"t11", ModelName);
    SendValue((char *)"list", RatesTypeKnown(Rate_Values[0]) ? Rate_Values[0] : (RotorFlight_V == 1 ? 4 : 6));
}
FLASHMEM static void RatesAwayBack() // back to the Rates page: everything on it sent again, Save shown if there is anything to save
{
    SendCommand((char *)"page RatesView");
    CurrentView = RATESVIEW_RF;
    if (DualRateInUse != RatesAwayBank)
    { // the bank switch moved while choosing: that bank is shown (and an edit here is said to be lost), the type left as it was
        SendText((char *)"t11", ModelName);
        ShowRatesBank();
        return;
    }
    char b[16];
    snprintf(b, sizeof(b), "Rate %u", (unsigned)DualRateInUse);
    SendText((char *)"t9", b);
    SendText((char *)"t11", ModelName);
    DisplayRatesValues(0, MAX_RATES_BYTES); // the type, its headings, the numbers
    SendCommand(Rates_Were_Edited ? (char *)"vis b3,1" : (char *)"vis b3,0");
}
FLASHMEM void RatesTypePickOk()
{
    if (CurrentView != RATESTYPEVIEW)
        return;
    const int32_t t = (int32_t)GetValue((char *)"list");
    if (DualRateInUse == RatesAwayBank && t >= 0 && t <= 6 && RatesTypeKnown((uint8_t)t))
    {
        Rate_Values[0] = (uint8_t)t;
        for (int i = 1; i < MAX_RATES_BYTES; ++i)
            Rate_Values[i] = RatesStart[t][i - 1];
        Rates_Were_Edited = true;
    }
    RatesAwayBack();
    if (t == 6 && !RatesTypeKnown(6) && CurrentView == RATESVIEW_RF)
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RatesView", (char *)"ROTORFLIGHT came with Rotorflight 2.3:\r\nthis flight controller has 2.2.\r\nThe type was not changed.");
    }
}
FLASHMEM void RatesTypePickCancel()
{
    if (CurrentView != RATESTYPEVIEW)
        return;
    RatesAwayBack();
}
// ************************************************************************************************************/
// B107 (Malcolm, 16 Oct 2026, a photo of the phone's "Rates curves": "I wonder if it might be possible to have these curves
// on the transmitter!?"): "Curves ..." on the Rates page opens page 83 (RatesCurveView), this rate's four curves from the
// page's numbers (typed and not yet saved too), worked out with Rotorflight's own formulas (fc/rc_rates.c, 4.6) - the
// phone drew a sketch of them, and now uses the same formulas (rotorflight-rates.html rfRate). As on the phone: across,
// the stick from full one way to full the other; up, the turn rate; roll, pitch and yaw on one deg/s scale, the collective
// (degrees of pitch) on its own; a curve lying on an earlier one dashed, so both show. Drawn a few lines a pass, never
// more than the wire to the screen holds (RatesCurvePoll), so no packet waits and no touch is thrown away; drawn again
// whenever the page comes back (its postinitialize prints "ldrcrcv": opened, after Help, after the screen saver).
FLASHMEM float RfRatesCurve(uint8_t type, uint8_t rc, uint8_t sr, uint8_t ex, float x) // Rotorflight's rate at |stick| x (0..1), deg/s; a collective's is x 0.025 = degrees
{
    const float e = ex / 100.0f;
    float v;
    switch (type)
    {
    case 1: // BETAFLIGHT
    {
        float r = rc * 2.0f;
        if (r > 400.0f)
            r += 14.54f * (r - 400.0f);
        const float f = x * (1.0f - e) + x * x * x * x * e;
        v = r * f / constrain(1.0f - x * (sr / 100.0f), 0.01f, 1.0f);
        break;
    }
    case 2: // RACEFLIGHT
    {
        float f = x * (1.0f - e) + x * x * x * e;
        f += f * x * (sr / 100.0f);
        v = rc * 10.0f * f;
        break;
    }
    case 3: // KISS
    {
        const float f = x * (1.0f - e) + x * x * x * e;
        v = rc * 2.0f * f / constrain(1.0f - x * (sr / 100.0f), 0.01f, 1.0f);
        break;
    }
    case 4: // ACTUAL
    {
        const float r = rc * 10.0f, a = max(0.0f, sr * 10.0f - r);
        v = x * (r + a * (x * (1.0f - e) + x * x * x * x * x * e));
        break;
    }
    case 5: // QUICKRATES
    {
        const float r = rc * 2.0f, m = max(sr * 10.0f, r);
        if (m <= 0.0f)
            return 0.0f;
        const float f = x * (1.0f - e) + x * x * x * e;
        v = r * x / constrain(1.0f - f * (1.0f - r / m), 0.01f, 1.0f);
        break;
    }
    case 6: // ROTORFLIGHT: rfPow, the exponent 2 .. 8.25 from the shape's bits
    {
        const unsigned bits = sr < 127 ? sr : 127;
        float y = x * x, z = x;
        if (bits & 16) y *= z;
        z *= z;
        if (bits & 32) y *= z;
        z *= z;
        if (bits & 64) y *= z;
        z = sqrtf(x);
        if (bits & 8) y *= z;
        z = sqrtf(z);
        if (bits & 4) y *= z;
        z = sqrtf(z);
        if (bits & 2) y *= z;
        z = sqrtf(z);
        if (bits & 1) y *= z;
        v = rc * 5.0f * (x * (1.0f - e) + y * e);
        break;
    }
    default: // NONE, or a type Rotorflight does not have: its null rates
        v = 500.0f * x;
    }
    return v < 2000.0f ? v : 2000.0f; // (SETPOINT_RATE_LIMIT)
}
#define RC_PLOT_X 250 // the plot on page 83 (hmi/ratestype_pages.py PLOT; test_rates checks they agree)
#define RC_PLOT_Y 90
#define RC_PLOT_W 506
#define RC_PLOT_H 294
#define RC_SEGS 64                                  // the line pieces of a curve, end to end
#define RC_CURVES (17 + 4 * RC_SEGS * 2)             // the plot's things before the dot: its ground, 12 grid lines, 4 for the axes, 2 lines a piece
static const uint16_t RcInk[4] = {57798, 17672, 25046, 64608}; // roll red, pitch green, yaw purple, collective orange: the hues of the page's pale axis labels, deep enough to read on white
static int16_t RcY[4][RC_SEGS + 1]; // each curve's points on the screen
static uint8_t RcTwin[4];           // 0: drawn whole; n: lies on n earlier curves, so dashed in their gaps; 255: all zero, not drawn
static int16_t RcStep = -1;         // the next thing to draw; -1: nothing
static float RcScale[4];            // each curve's scale (B108: the dots use them)
FLASHMEM float RcFull(uint8_t a) { return RfRatesCurve(Rate_Values[0], Rate_Values[1 + 3 * a], Rate_Values[2 + 3 * a], Rate_Values[3 + 3 * a], 1.0f); }
FLASHMEM static void RcPrepare() // the four curves' points and the legend's words
{
    float full[4];
    float rpy = 1.0f;
    for (uint8_t a = 0; a < 4; ++a)
    {
        full[a] = RcFull(a);
        if (a < 3 && full[a] > rpy)
            rpy = full[a];
    }
    const int cy = RC_PLOT_Y + RC_PLOT_H / 2;
    for (uint8_t a = 0; a < 4; ++a)
    {
        const float scale = a == 3 ? (full[3] > 0.0f ? full[3] : 1.0f) : rpy; // (the collective on its own scale, as on the phone)
        RcScale[a] = scale;
        for (int k = 0; k <= RC_SEGS; ++k)
        {
            const float s = -1.0f + 2.0f * k / RC_SEGS;
            float v = RfRatesCurve(Rate_Values[0], Rate_Values[1 + 3 * a], Rate_Values[2 + 3 * a], Rate_Values[3 + 3 * a], fabsf(s));
            if (s < 0.0f)
                v = -v;
            int y = cy - (int)lroundf(v / scale * (RC_PLOT_H / 2) * 0.92f);
            RcY[a][k] = (int16_t)constrain(y, RC_PLOT_Y + 1, RC_PLOT_Y + RC_PLOT_H - 3);
        }
        RcTwin[a] = 0;
        if (full[a] <= 0.0f)
        {
            RcTwin[a] = 255;
            continue;
        }
        for (uint8_t b = 0; b < a; ++b)
        {
            if (RcTwin[b] == 255)
                continue;
            bool same = true;
            for (int k = 0; k <= RC_SEGS && same; ++k)
                same = abs(RcY[a][k] - RcY[b][k]) <= 1;
            if (same)
                ++RcTwin[a];
        }
    }
    static const char *const names[4] = {"Roll", "Pitch", "Yaw", "Collective"};
    for (uint8_t a = 0; a < 4; ++a)
    {
        char t[32], n[6];
        if (a == 3)
            snprintf(t, sizeof(t), "%s %.1f deg", names[a], full[a] * 0.025f);
        else
            snprintf(t, sizeof(t), "%s %d deg/s", names[a], (int)lroundf(full[a]));
        snprintf(n, sizeof(n), "lg%u", (unsigned)a);
        SendText(n, t);
    }
    SendText((char *)"tt", (char *)(Rate_Values[0] <= 6 ? Rate_Types[Rate_Values[0]] : "?")); // (the type the curves are of)
}
FLASHMEM bool RcPut(const char *c); // (B108: below)
FLASHMEM static bool RcDraw(int i) // one thing on the plot, straight onto the wire (never waits, never reads: a touch is never lost); false: no room yet
{
    char c[48];
    const int x0 = RC_PLOT_X, y0 = RC_PLOT_Y, cx = RC_PLOT_X + RC_PLOT_W / 2, cy = RC_PLOT_Y + RC_PLOT_H / 2;
    c[0] = 0;
    if (i == 0)
        snprintf(c, sizeof(c), "fill %d,%d,%d,%d,65535", x0, y0, RC_PLOT_W, RC_PLOT_H);
    else if (i <= 6) // the grid, a quarter of the way out each way: across ...
    {
        const int k = (i - 1) % 3 + 1, x = (i <= 3) ? cx - k * RC_PLOT_W / 8 : cx + k * RC_PLOT_W / 8;
        snprintf(c, sizeof(c), "line %d,%d,%d,%d,59164", x, y0, x, y0 + RC_PLOT_H - 1);
    }
    else if (i <= 12) // ... and up
    {
        const int k = (i - 7) % 3 + 1, y = (i <= 9) ? cy - k * RC_PLOT_H / 8 : cy + k * RC_PLOT_H / 8;
        snprintf(c, sizeof(c), "line %d,%d,%d,%d,59164", x0, y, x0 + RC_PLOT_W - 1, y);
    }
    else if (i <= 16) // the axes, two pixels each
    {
        if (i <= 14)
            snprintf(c, sizeof(c), "line %d,%d,%d,%d,16904", x0, cy + (i - 13), x0 + RC_PLOT_W - 1, cy + (i - 13));
        else
            snprintf(c, sizeof(c), "line %d,%d,%d,%d,16904", cx + (i - 15), y0, cx + (i - 15), y0 + RC_PLOT_H - 1);
    }
    else if (i < RC_CURVES) // a curve's piece, two pixels thick; a twin's only in its dashes
    {
        const int j = i - 17, a = j / (RC_SEGS * 2), k = (j / 2) % RC_SEGS, t = j % 2;
        const uint8_t tw = RcTwin[a];
        if (tw == 255 || ((k >> 1) % (tw + 1)) != tw)
            return true;
        const int xa = x0 + k * (RC_PLOT_W - 1) / RC_SEGS, xb = x0 + (k + 1) * (RC_PLOT_W - 1) / RC_SEGS;
        snprintf(c, sizeof(c), "line %d,%d,%d,%d,%u", xa, RcY[a][k] + t, xb, RcY[a][k + 1] + t, (unsigned)RcInk[a]);
    }
    else // the dot at the middle
        snprintf(c, sizeof(c), "cirs %d,%d,5,64937", cx, cy);
    return RcPut(c);
}
// ************************************************************************************************************/
// B108 (Malcolm, of the curves: "Looks very very good !" - and to a dot on each curve that moves with the sticks: "Yes
// please!!"): each curve carries a dot where Rotorflight has that stick now - from what this transmitter sends on the
// axis' channel, read as Rotorflight reads it (fc/rc.c updateRcCommands: the centre, the deadband, the deflection; the
// channel from its map). The flight controller is asked its map (MSP_RX_MAP) and its centre, deflection and deadbands
// (MSP_RC_CONFIG) as the page opens; until it answers, or with no model, Rotorflight's own defaults (AETRC: roll on
// channel 1, pitch 2, yaw 4, collective 5; 1500, 510, 5). A dot that moves is rubbed out - its little square filled
// again, and the grid, the axes, the curve pieces and the other dots through it drawn again - then drawn where it now
// is; only when its stick has moved, never more than the wire to the screen holds, as the curves are.
#define RC_DOT_R 6
#define RC_DOT_BOX (2 * RC_DOT_R + 3)      // the square a dot is rubbed out with
#define RC_DOT_OTHERS (RC_CURVES + 1)      // the ops: 0..RC_CURVES rub out (as RcDraw's, inside the square), then the other dots (2 each), then the dot
#define RC_DOT_NEW (RC_DOT_OTHERS + 8)
static uint8_t RcMap[4] = {0, 1, 3, 4};    // the channel (0-based) of roll, pitch, yaw, collective (Rotorflight's AETRC)
static int16_t RcCentre = 1500, RcDefl = 510;
static uint8_t RcDead[4] = {5, 5, 5, 0};   // (rc_deadband for roll and pitch, rc_yaw_deadband, the collective none)
static int16_t RcDotX[4] = {-1, -1, -1, -1}, RcDotY[4]; // where each dot is drawn (-1: not drawn)
static int8_t RcDotNow = -1;               // the dot being moved
static int16_t RcDotStep = 0, RcOldX = -1, RcOldY = -1;
static uint32_t RcDotLook = 0;             // when the sticks were last looked at
static int RcAskId = -1;
static uint8_t RcAskStep = 0;              // the questions: 0 none, 1 the map asked, 2 the centre etc. asked, 3 answered or given up
FLASHMEM bool RcPut(const char *c) // one command straight onto the wire, or nothing if it does not fit (never waits, never reads)
{
    const int n = (int)strlen(c);
    if (n == 0)
        return true;
    if (NEXTION.availableForWrite() < n + 3)
        return false;
    NEXTION.write((const uint8_t *)c, n);
    NEXTION.write((const uint8_t *)"\xFF\xFF\xFF", 3);
    return true;
}
FLASHMEM float RcDeflection(uint8_t a) // the stick as Rotorflight reads it: -1 .. 1
{
    float d = (float)SendBuffer[RcMap[a]] - RcCentre;
    const float db = RcDead[a], range = RcDefl - db;
    d = d > db ? d - db : (d < -db ? d + db : 0.0f);
    return range > 0.0f ? constrain(d / range, -1.0f, 1.0f) : 0.0f;
}
FLASHMEM static void RcDotWant(uint8_t a, int16_t &x, int16_t &y) // where its dot belongs: on its curve, kept wholly on the plot
{
    const float d = RcDeflection(a);
    float v = RfRatesCurve(Rate_Values[0], Rate_Values[1 + 3 * a], Rate_Values[2 + 3 * a], Rate_Values[3 + 3 * a], fabsf(d));
    if (d < 0.0f)
        v = -v;
    const int cy = RC_PLOT_Y + RC_PLOT_H / 2;
    x = (int16_t)constrain(RC_PLOT_X + (int)lroundf((d + 1.0f) * 0.5f * (RC_PLOT_W - 1)), RC_PLOT_X + RC_DOT_R + 1, RC_PLOT_X + RC_PLOT_W - RC_DOT_R - 2);
    y = (int16_t)constrain(cy - (int)lroundf(v / RcScale[a] * (RC_PLOT_H / 2) * 0.92f), RC_PLOT_Y + RC_DOT_R + 1, RC_PLOT_Y + RC_PLOT_H - RC_DOT_R - 2);
}
FLASHMEM static bool RcBoxesMeet(int ax, int ay, int bx, int by) { return abs(ax - bx) < RC_DOT_BOX && abs(ay - by) < RC_DOT_BOX; }
FLASHMEM static bool RcDotOp(int i) // one step of moving dot RcDotNow from (RcOldX, RcOldY) to where RcDotX/Y say; false: no room yet
{
    char c[48];
    c[0] = 0;
    const int a = RcDotNow, bx = RcOldX - RC_DOT_R - 1, by = RcOldY - RC_DOT_R - 1, bw = RC_DOT_BOX;
    const int cx = RC_PLOT_X + RC_PLOT_W / 2, cy = RC_PLOT_Y + RC_PLOT_H / 2;
    if (i == 0)
        snprintf(c, sizeof(c), "fill %d,%d,%d,%d,65535", bx, by, bw, bw);
    else if (i <= 6) // the grid's pieces in the square
    {
        const int k = (i - 1) % 3 + 1, x = (i <= 3) ? cx - k * RC_PLOT_W / 8 : cx + k * RC_PLOT_W / 8;
        if (x >= bx && x < bx + bw)
            snprintf(c, sizeof(c), "line %d,%d,%d,%d,59164", x, by, x, by + bw - 1);
    }
    else if (i <= 12)
    {
        const int k = (i - 7) % 3 + 1, y = (i <= 9) ? cy - k * RC_PLOT_H / 8 : cy + k * RC_PLOT_H / 8;
        if (y >= by && y < by + bw)
            snprintf(c, sizeof(c), "line %d,%d,%d,%d,59164", bx, y, bx + bw - 1, y);
    }
    else if (i <= 16) // the axes' pieces
    {
        const int r = (i <= 14) ? cy + (i - 13) : cx + (i - 15);
        if (i <= 14 && r >= by && r < by + bw)
            snprintf(c, sizeof(c), "line %d,%d,%d,%d,16904", bx, r, bx + bw - 1, r);
        else if (i > 14 && r >= bx && r < bx + bw)
            snprintf(c, sizeof(c), "line %d,%d,%d,%d,16904", r, by, r, by + bw - 1);
    }
    else if (i < RC_CURVES) // the curve pieces through the square, whole and in the plot's order (so a twin's dashes stay on top)
    {
        const int j = i - 17, ca = j / (RC_SEGS * 2), k = (j / 2) % RC_SEGS, t = j % 2;
        const uint8_t tw = RcTwin[ca];
        if (tw == 255 || ((k >> 1) % (tw + 1)) != tw)
            return true;
        const int xa = RC_PLOT_X + k * (RC_PLOT_W - 1) / RC_SEGS, xb = RC_PLOT_X + (k + 1) * (RC_PLOT_W - 1) / RC_SEGS;
        const int ya = min(RcY[ca][k], RcY[ca][k + 1]), yb = max(RcY[ca][k], RcY[ca][k + 1]) + 1;
        if (xb < bx || xa >= bx + bw || yb < by || ya >= by + bw)
            return true;
        snprintf(c, sizeof(c), "line %d,%d,%d,%d,%u", xa, RcY[ca][k] + t, xb, RcY[ca][k + 1] + t, (unsigned)RcInk[ca]);
    }
    else if (i == RC_CURVES) // the middle's dot
    {
        if (RcBoxesMeet(RcOldX, RcOldY, cx, cy))
            snprintf(c, sizeof(c), "cirs %d,%d,5,64937", cx, cy);
    }
    else if (i < RC_DOT_NEW) // the other dots it lay on, drawn again
    {
        const int b = (i - RC_DOT_OTHERS) / 2;
        if (b == a || RcDotX[b] < 0 || !RcBoxesMeet(RcOldX, RcOldY, RcDotX[b], RcDotY[b]))
            return true;
        if ((i - RC_DOT_OTHERS) % 2 == 0)
            snprintf(c, sizeof(c), "cirs %d,%d,%d,16904", RcDotX[b], RcDotY[b], RC_DOT_R);
        else
            snprintf(c, sizeof(c), "cirs %d,%d,%d,%u", RcDotX[b], RcDotY[b], RC_DOT_R - 2, (unsigned)RcInk[b]);
    }
    else if (i == RC_DOT_NEW) // the dot where it now is: a dark ring, its curve's colour inside
        snprintf(c, sizeof(c), "cirs %d,%d,%d,16904", RcDotX[a], RcDotY[a], RC_DOT_R);
    else
        snprintf(c, sizeof(c), "cirs %d,%d,%d,%u", RcDotX[a], RcDotY[a], RC_DOT_R - 2, (unsigned)RcInk[a]);
    return RcPut(c);
}
FLASHMEM static void RcAskPoll() // the flight controller's map, then its centre, deflection and deadbands
{
    if (RcAskStep != 1 && RcAskStep != 2)
        return;
    if (!PipeReplyReady(RcAskId))
    {
        if (PipeReplyLate())
            RcAskStep = 3; // (no answer: the defaults stay)
        return;
    }
    uint8_t b[16];
    const int n = PipeRepCode == 200 ? PipeReplyBytes(b, sizeof(b)) : 0;
    if (RcAskStep == 1)
    { // MSP_RX_MAP: for roll, pitch, yaw, collective, throttle ... the channel each reads
        if (n >= 4)
            for (uint8_t a = 0; a < 4; ++a)
                if (b[a] < 16)
                    RcMap[a] = b[a];
        RcAskId = MspAsk(66, nullptr, 0); // MSP_RC_CONFIG
        RcAskStep = 2;
        return;
    }
    if (n >= 12)
    { // centre, deflection (16 bits each), 0, the throttle's ends, then the deadbands
        const int ce = b[0] | (b[1] << 8), de = b[2] | (b[3] << 8);
        if (ce >= 1000 && ce <= 2000 && de >= 100 && de <= 1000 && b[10] < de && b[11] < de)
        {
            RcCentre = (int16_t)ce;
            RcDefl = (int16_t)de;
            RcDead[0] = RcDead[1] = b[10];
            RcDead[2] = b[11];
        }
    }
    RcAskStep = 3;
    RcDotLook = 0; // (the dots placed again, by the flight controller's own numbers)
}
FLASHMEM void RatesCurvePoll()
{
    if (CurrentView != RATESCURVEVIEW)
    {
        RcStep = -1;
        RcDotNow = -1;
        return;
    }
    RcAskPoll();
    if (RcStep >= 0) // the plot first
    {
        while (RcStep <= RC_CURVES && RcDraw(RcStep))
            ++RcStep;
        if (RcStep > RC_CURVES)
        {
            RcStep = -1;
            RcDotLook = 0;
        }
        return;
    }
    if (RcDotNow >= 0) // a dot on its way
    {
        while (RcDotStep <= RC_DOT_NEW + 1 && RcDotOp(RcDotStep))
            ++RcDotStep;
        if (RcDotStep > RC_DOT_NEW + 1)
        {
            RcDotNow = -1;
            RcDotLook = 0; // (the next that moved, at once)
        }
        return;
    }
    if (RcDotLook && millis() - RcDotLook < 50)
        return;
    RcDotLook = millis();
    for (uint8_t a = 0; a < 4; ++a)
    {
        if (RcTwin[a] == 255)
            continue; // (no curve, no dot)
        int16_t x, y;
        RcDotWant(a, x, y);
        if (RcDotX[a] >= 0 && abs(x - RcDotX[a]) < 2 && abs(y - RcDotY[a]) < 2)
            continue;
        RcOldX = RcDotX[a];
        RcOldY = RcDotY[a];
        RcDotX[a] = x;
        RcDotY[a] = y;
        RcDotNow = (int8_t)a;
        RcDotStep = RcOldX >= 0 ? 0 : RC_DOT_NEW; // (not drawn before: nothing to rub out)
        return;
    }
}
FLASHMEM void RatesCurvesTapped() // "Curves ...": the page, its curves from what the Rates page shows
{
    if (CurrentView != RATESVIEW_RF || Reading_RATES_Now || ParametersToBeSentPointer)
        return; // (reading or sending: the page's note says so)
    ReadEditedRateValues(); // the numbers shown, typed or not (kept: OK brings them back)
    RatesAwayBank = DualRateInUse;
    SendCommand((char *)"page RatesCurveView");
    CurrentView = RATESCURVEVIEW;
    char b[16];
    snprintf(b, sizeof(b), "Rate %u", (unsigned)DualRateInUse);
    SendText((char *)"t9", b);
    SendText((char *)"t11", ModelName);
    RcStep = -1; // (drawn when the page says it is there: RatesCurvesPageBack)
    // B108: the dots by Rotorflight's own defaults, until the flight controller says its own (asked only with a model)
    static const uint8_t aetrc[4] = {0, 1, 3, 4};
    memcpy(RcMap, aetrc, 4);
    RcCentre = 1500;
    RcDefl = 510;
    RcDead[0] = RcDead[1] = RcDead[2] = 5;
    RcDead[3] = 0;
    RcAskStep = 0;
    char why[80];
    if (RfLive() && !RfPipeBlocked(why, sizeof(why)))
    {
        RcAskId = MspAsk(64, nullptr, 0); // MSP_RX_MAP
        RcAskStep = 1;
    }
}
FLASHMEM void RatesCurvesPageBack() // "ldrcrcv": the page is on the screen (opened, back from Help or the screen saver): drawn afresh
{
    if (CurrentView != RATESCURVEVIEW)
        return;
    RcPrepare();
    RcStep = 0;
    RcDotNow = -1; // B108: the plot is drawn afresh, so are the dots after it
    for (uint8_t a = 0; a < 4; ++a)
        RcDotX[a] = -1;
}
FLASHMEM void RatesCurvesOk()
{
    if (CurrentView != RATESCURVEVIEW)
        return;
    RcStep = -1;
    RatesAwayBack();
}
#endif // RATESRF_H

// ************************************************************************************************************/