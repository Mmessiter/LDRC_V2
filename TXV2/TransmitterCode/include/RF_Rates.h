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
        GetText(RatesWindows[i], temp, sizeof(temp));  // ClaudeFix-2-7-2026
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
    ReadEditedRateValues();
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
    ReadEditedRateValues();                             // read the edited RATES from the screen;
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
    AddParameterstoQueue(GET_SECOND_6_RATES_VALUES);    // SECOND MUST BE QUEUED FIRST!!! Send RATES 7-12 values from TX to RX
    AddParameterstoQueue(GET_FIRST_7_RATES_VALUES);     // SECOND MUST BE QUEUED FIRST!!! Send RATES 1-6 values from TX to RX
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
static uint8_t RatesTypeBank = 0;   // the rates bank the picker was opened on
FLASHMEM void RatesTypeTapped() // the type tapped: the picker, at the bank's own type
{
    if (CurrentView != RATESVIEW_RF || Reading_RATES_Now || ParametersToBeSentPointer)
        return; // (reading or sending: the page's note covers the type)
    ReadEditedRateValues(); // what the page shows (typed or not), kept through the picker - Cancel brings it back
    RatesTypeBank = DualRateInUse;
    SendCommand((char *)"page RatesTypeView");
    CurrentView = RATESTYPEVIEW;
    char b[16];
    snprintf(b, sizeof(b), "Rate %u", (unsigned)DualRateInUse);
    SendText((char *)"t9", b);
    SendText((char *)"t11", ModelName);
    SendValue((char *)"list", RatesTypeKnown(Rate_Values[0]) ? Rate_Values[0] : (RotorFlight_V == 1 ? 4 : 6));
}
FLASHMEM static void RatesTypeBack() // back to the Rates page: everything on it sent again, Save shown if there is anything to save
{
    SendCommand((char *)"page RatesView");
    CurrentView = RATESVIEW_RF;
    if (DualRateInUse != RatesTypeBank)
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
    if (DualRateInUse == RatesTypeBank && t >= 0 && t <= 6 && RatesTypeKnown((uint8_t)t))
    {
        Rate_Values[0] = (uint8_t)t;
        for (int i = 1; i < MAX_RATES_BYTES; ++i)
            Rate_Values[i] = RatesStart[t][i - 1];
        Rates_Were_Edited = true;
    }
    RatesTypeBack();
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
    RatesTypeBack();
}
#endif // RATESRF_H

// ************************************************************************************************************/