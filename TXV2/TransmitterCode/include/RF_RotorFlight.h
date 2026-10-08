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
    char Vbuf[15];

    if (MotorEnabled || !SafetyON) // (B45: which one, so a refusal explains itself)
        MsgBox(pRXSetupView, (char *)(MotorEnabled ? "The motor is enabled.\r\nDisarm first." : "The safety is off.\r\nSafety on first."));

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
    ZeroDataScreen();        // clear the screen data because editing Rotorflight parameters may have created misleading comms gaps
    GotoFrontView();
}
FLASHMEM void EndRFSettingsView() // OK on the settings page: the fields read back, the model saved, back to the menu
{
    char temp[15];
    // Nextion serial can carry stale bytes after heavy MSP traffic, so GetText may fail silently.
    // Only overwrite the globals if the read-back parses to a plausible value — otherwise keep the current one.
    GetText((char *)"Ratio", temp, sizeof(temp));  // ClaudeFix-2-7-2026
    float newRatio = atof(temp);
    if (newRatio > 0.0f)
        GearRatio = newRatio;

    GetText((char *)"Arming", temp, sizeof(temp));  // ClaudeFix-2-7-2026
    // ClaudeFix-2-7-2026 Digits ONLY: a desynced read-back once returned the Ratio box's "10.30"
    // here, and atoi turned it into a perfectly plausible channel 10. A real
    // channel number can never contain a dot (GetText is fixed too, but this
    // field guards a safety-critical value -- belt AND braces).
    bool armDigitsOnly = (strlen(temp) > 0);
    for (uint8_t adc = 0; adc < strlen(temp); ++adc)
        if (temp[adc] < '0' || temp[adc] > '9')
            armDigitsOnly = false;
    int newArming = atoi(temp);
    if (armDigitsOnly && newArming > 0 && newArming <= CHANNELSUSED)
        ArmingChannel = (uint8_t)newArming;

    {
        uint32_t sw = GetValue((char *)"sw0");
        if (sw <= 1)
            LinkRatesToBanks = (bool)sw; // ClaudeFix-2-7-2026 ignore a comms-error 65535 (would have saved as 'true')
    }
    SaveOneModel(ModelNumber); // save the model including gear ratio and arming channel
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