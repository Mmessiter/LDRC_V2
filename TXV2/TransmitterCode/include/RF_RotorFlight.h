// **********************************************************************************************************
// This file handles Rotorflight central functions
// **********************************************************************************************************

#ifndef RotorFlight_H
#define RotorFlight_H
#include <Arduino.h>
#include "1Definitions.h"

FLASHMEM void ShowRFRate()
{
    char NB[10];
    Str(NB, DualRateInUse, 0);
    char msg[70];
    strcpy(msg, "Rate ");
    strcat(msg, NB);
    SendText((char *)"t8", msg);
}

// **********************************************************************************************************/
FLASHMEM void ShowRFBank()
{
    char NB[10];
    Str(NB, Bank, 0);
    char msg[70];
    strcpy(msg, "Bank ");
    strcat(msg, NB);
    SendText((char *)"t14", msg);
}

// **********************************************************************************************************/
FLASHMEM void RotorFlightStart()
{
    RfLeaveAfterSave = false;   // B102: no page's "Save now?" is pending once the menu is open
    char Vbuf[15];

    // B191 (Malcolm, 6 Nov 2026, Mehul's RAW420: "the rotorflight button on this screen did nothing!"): the gate is the
    // radios' rule (FlightGuard.h). It was "motor on OR safety not on" - and with NO safety switch defined the safety
    // never reads on, so a model with only a motor switch could never open the menu while connected (silently, B02).
    // Now: a defined safety switch must be on; with none, the motor must be off. And a refusal now stops (it opened
    // the page anyway after the box when no model was connected).
    if (MotorEnabled || (SafetyIsDefined() && SafetyIsOff()))
    {
        if (LedWasGreen)
            return; // B02: with the model flying the touch is ignored - a box that waits for OK would stop the switches being read
        MsgBox(pRXSetupView, (char *)(MotorEnabled ? "The motor is ON.\r\nSwitch it off first." : "The safety is off.\r\nSafety on first.")); // (B45: which one, so a refusal explains itself)
        return;
    }

    UndoNewVisit();            // B196: a page's visit ends here - what Undo kept of its reads is let go (RF_Undo.h)
    if (RfHomeBack()) return;  // B196: a page opened from the guide or from Check my setup goes back there (RF_Tools.h)
    SendCommand((char *)"page RFView");
    CurrentView = ROTORFLIGHTVIEW;
    if (RxHasPipe()) // B47: only a receiver that can carry it (0.9.874+) is asked; a Version 1 receiver gets "By radio link" at once
    {
        PipeOn(); // B41: the screen joins the model's receiver over Bluetooth; while it is joined the Rotorflight packets go that way
        if (PipeState != 2)
            PipeState = 1; // (asked: joining, until the screen says)
    }
    else
        PipeOff();
    ShowPipeState();
    AddParameterstoQueue(MSP_INHIBIT_TELEMETRY); // Inhibit telemetry for a short time to allow MSP data to be sent without interference from telemetry data (for MSP data transmission)
    SendText((char *)"t11", ModelName);          // Show model name
    RotorFlight_Version = RFVersions[RotorFlight_V];
    (void)Vbuf; // (B56: the four settings have a page of their own, RFSetupView: StartRFSettingsView)
    ShowRFBank();
    ShowRFRate();
    if (PipeState == 2)
        BakOfferEdits(); // B70: edits made without the model, offered once per connection (B71: or by BakOfferTick once the pipe is ready)
}
// B56 (Malcolm, 7 Oct: the menu "will become a bit overcrowded ... redesign it slightly"): the four settings that were on
// the menu - link rates and banks, version, arming channel, main RPM ratio - on a page of their own, and the menu a grid
// of buttons. The fields keep their names (sw0, t5, Arming, Ratio), so the keypad and LinkRatesToBanksChanged work as before.
FLASHMEM void StartRFSettingsView()
{
    char Vbuf[15];
    SendCommand((char *)"page RFSetupView");
    CurrentView = RFSETUPVIEW;
    SendText((char *)"t11", ModelName);
    snprintf(Vbuf, sizeof(Vbuf), "%1.2f", GearRatio);       // 10.3 usually (ClaudeFix-2-7-2026 size 5 truncated 10.35 to "10.3" -- which RotorFlightEnd then read back and SAVED, silently degrading the ratio)
    SendText((char *)"Ratio", Vbuf);
    snprintf(Vbuf, sizeof(Vbuf), "%d", ArmingChannel);
    SendText((char *)"Arming", Vbuf);
    SendValue((char *)"sw0", LinkRatesToBanks);
    RotorFlight_Version = RFVersions[RotorFlight_V];
    snprintf(Vbuf, sizeof(Vbuf), "%1.1f", RotorFlight_Version);
    SendText((char *)"t5", Vbuf);
    ShowRFBank();
    ShowRFRate();
}

// **********************************************************************************************************/
FLASHMEM void RotorFlightEnd() // OK on the menu: to the front page (B56: the fields are on the settings page; EndRFSettingsView reads them)
{
    ZeroGapStats();          // clear the comms gaps: editing Rotorflight parameters may have created misleading ones (B155: the gaps only - the lost packets and the rest stay)
    GotoFrontView();
}
FLASHMEM bool RFSettingsGather() // B99: the settings page's fields read back and the model saved (its OK, and the way on to Model basics). true: taken and saved
{
    // B211 (15 Nov 2026, found by the tenth review's check of what a gather writes): ALL THREE BOXES ARE ASKED BEFORE ANY IS TAKEN.
    // Each field was looked at for itself - a ratio above 0, digits only, 0 or 1 - so "no answer" changed none of them; but the
    // first could be taken and the next not (the gear ratio new, the arming channel as it was), the model saved so, and the page
    // left with no more than a sound. Now a box with no answer takes nothing: the box "The screen did not answer ..." says so,
    // and whoever asked stays on this page (Nextion.h: A PAGE'S FIELDS ARE TAKEN WHOLE, OR NOT AT ALL).
    char ratio[15], temp[15];
    RfGatherStart();
    GetText((char *)"Ratio", ratio, sizeof(ratio));  // ClaudeFix-2-7-2026
    TextMustBeNumber("Ratio", ratio); // B211: A NUMBER FIELD'S TEXT THAT IS NO NUMBER IS NO ANSWER (Nextion.h)
    GetText((char *)"Arming", temp, sizeof(temp));   // ClaudeFix-2-7-2026
    TextMustBeNumber("Arming", temp);
    const uint32_t sw = GetValue((char *)"sw0");
    if (RfFieldsMissed("page RFSetupView"))
        return false;
    // Nextion serial can carry stale bytes after heavy MSP traffic, so GetText may fail silently.
    // Only overwrite the globals if the read-back parses to a plausible value — otherwise keep the current one.
    float newRatio = atof(ratio);
    bool ratioFits = newRatio > 0.0f && newRatio < 1000.0f;
    if (ratioFits)
    { // (the fifteenth review) ... AND AS THIS PAGE WILL SHOW IT - to two places (StartRFSettingsView) - it must fit too: "999.999" was taken and shown as
      // "1000.00", "0.004" as "0.00", and the next OK on the untouched page was refused for a number he had not typed
        char as[16];
        snprintf(as, sizeof(as), "%1.2f", newRatio);
        const float shown = (float)atof(as);
        ratioFits = shown > 0.0f && shown < 1000.0f;
        if (ratioFits)
            newRatio = shown; // (the sixteenth review) ... AND IT IS KEPT AS SHOWN: "0.0051" was kept as typed and shown as 0.01 - the next OK kept 0.01
    }
    if (ratio[0] && !ratioFits)
    { // B211 (the fourteenth review; the released code had it): THE PAGE TAKES THE RATIOS THE CARD KEEPS. It took any ratio above 0 - and the card's
      // reader (SDcard.h) makes 10.3 of anything from 1000 up: "1030" typed for 10.30 was used today, and was 10.3 at the next switch-on, without a
      // word. Nothing is taken, the page stays, and the box says why.
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFSetupView", (char *)"The gear ratio must be more than 0\r\nand less than 1000 (10.3 is usual).\r\nNOTHING was changed.");
        return false;
    }
    if (newRatio > 0.0f)
        GearRatio = newRatio; // (an empty box: the ratio as it was)

    // ClaudeFix-2-7-2026 Digits ONLY: a desynced read-back once returned the Ratio box's "10.30"
    // here, and atoi turned it into a perfectly plausible channel 10. A real
    // channel number can never contain a dot (GetText is fixed too, but this
    // field guards a safety-critical value -- belt AND braces).
    bool armDigitsOnly = (strlen(temp) > 0);
    for (uint8_t adc = 0; adc < strlen(temp); ++adc)
        if (temp[adc] < '0' || temp[adc] > '9')
            armDigitsOnly = false;
    int newArming = atoi(temp);
    // B48: Rotorflight's switch channels start at 6 (5 is its collective), so 1-5 were refused: the Switches page would refuse
    // every save. B146 (Malcolm, 24 Oct 2026, setting up an OMP M2: "It insists its flight controller arming channel is 5 and
    // not changeable"): a flight controller that is not Rotorflight may want 5 - allowed once the pilot has said so. The
    // Switches page's own guard (RF_Switches.h SwArmOk) still explains itself to a Rotorflight pilot who chose 1-5.
    if (armDigitsOnly && newArming >= 1 && newArming <= 5 && newArming != ArmingChannel)
    {
        char q[120];
        snprintf(q, sizeof(q), "Rotorflight's switches start at channel 6,\r\nunless its channel map moves one there.\r\nUse channel %d for arming?", newArming);   // (B210: was "the collective on 5" - it is the throttle by default, and AUX1 when arming moves to 5 for ExpressLRS)
        if (GetConfirmation((char *)"page RFSetupView", q))
            ArmingChannel = (uint8_t)newArming;
    }
    else if (armDigitsOnly && newArming > 0 && newArming <= CHANNELSUSED)
        ArmingChannel = (uint8_t)newArming;

    if (sw <= 1)
        LinkRatesToBanks = (bool)sw; // ClaudeFix-2-7-2026 ignore a comms-error 65535 (would have saved as 'true')
    SaveOneModel(ModelNumber); // save the model including gear ratio and arming channel
    return true;
}
FLASHMEM void EndRFSettingsView() // OK on the settings page: the fields read back, the model saved, back to the menu
{
    if (!RFSettingsGather())
        return; // B211: a box had no answer - nothing was taken, the page stays (the box said so)
    RotorFlightStart();
}
// **********************************************************************************************************/
FLASHMEM void LinkRatesToBanksChanged()
{
    {
        uint32_t sw = GetValue((char *)"sw0");
        if (sw <= 1)
            LinkRatesToBanks = (bool)sw; // ClaudeFix-2-7-2026 ignore a comms-error 65535
    }
    SaveOneModel(ModelNumber); // save the model including LinkRatesToBanks
}

#endif // RotorFlight_H