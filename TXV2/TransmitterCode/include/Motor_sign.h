#include <Arduino.h>
#include "1Definitions.h"
#ifndef MOTOR_SIGN_H
#define MOTOR_SIGN_H

/*********************************************************************************************************************************/
//                        MOTOR_SIGN and announcements functions
/*********************************************************************************************************************************/

/*********************************************************************************************************************************/
void SendColour(char *but, int Colour) // Set the colour of a button on the Nextion screen
{
    char lbut[60];
    char nb[10] = " ";
    strcpy(lbut, but);
    strcat(lbut, Str(nb, Colour, 0));
    SendCommand(lbut);
}
/*********************************************************************************************************************************/
void ShowSafety() // Show the state of the safety switch on the front view by changing the colour of the motor button and by playing a sound if it has just been turned on or off
{
    uint16_t Fg = GREEN;
    uint16_t Bg = BLACK;
    uint16_t AnnounceMent = SAFEOFF;

    char bco[] = "bt0.bco=";
    char bco2[] = "bt0.bco2=";
    char pco[] = "bt0.pco=";
    char pco2[] = "bt0.pco2=";

    if (SafetyON)
    {
        Fg = RED;
        Bg = WHITE;
        AnnounceMent = SAFEON;
    }
    if (AnnounceBanks && UseMotorKill && millis()>4000)// Don't want to hear this at power on because of the startup sounds etc.
    {
        PlaySound(AnnounceMent);
        if (UseLog)
            LogSafety();
    }
    if ((CurrentView == FRONTVIEW) && UseMotorKill)
    {
        SendColour(bco, Fg);
        SendColour(bco2, Fg);
        SendColour(pco, Bg);
        SendColour(pco2, Bg);
    }
}
// *********************************************************************************************************************************/
FASTRUN void ShowMotorTimer() // Show timer for the motor on the front view and play announcements if timer is running down
{
    CRUMB(CRUMB_MOTORTIMER);
    char FrontView_Hours[] = "Hours";
    char FrontView_Mins[] = "Mins";
    char FrontView_Secs[] = "Secs";

    if (TimesUp)
        return;

    uint8_t Recording[10] = {ONEMINUTE, TWOMINUTES, THREEMINUTES, FOURMINUTES, FIVEMINUTES, SIXMINUTES, SEVENMINUTES, EIGHTMINUTES, NINEMINUTES, TENMINUTES};

    uint8_t Cdown[10] = {TEN, NINE, EIGHT, SEVEN, SIX, FIVE, FOUR, THREE, TWO, ONE};

    const bool CountingDown = TimerDownwards && TimerStartTime > 0; // B27: a countdown of no minutes counts up (it sat at zero and said "stop flying" at once)
    if ((MotorEnabled && (!LostContactFlag)))
    {
        MotorOnSeconds = ((millis() - MotorStartTime) / 1000) + PausedSecs;
        Secs = MotorOnSeconds;
        if (CountingDown)
            Secs = (MotorOnSeconds >= TimerStartTime) ? 0 : TimerStartTime - MotorOnSeconds; // B27: never past zero (unsigned, it wrapped to 1,193,046 hours)
        Hours = Secs / 3600;
        Secs %= 3600;
        Mins = Secs / 60;
        Secs %= 60;
    }
    if (LastSeconds != Secs)
    {
        ClockSpoken = false;
        ClockSpoken1 = false;
        if (CurrentView == FRONTVIEW)
        {
            SendValue(FrontView_Secs, Secs);
            SendValue(FrontView_Mins, Mins);
            SendValue(FrontView_Hours, Hours);
        }
        LastSeconds = Secs;
    }
    if (CountingDown && MotorEnabled && !LostContactFlag && MotorOnSeconds >= TimerStartTime && MotorOnSeconds > 2)
    { // B27: time's up whether or not the clock speaks (it sat inside the spoken-clock test, where the zero second could be missed)
        PlaySound(STORAGECHARGE); // = Stop Flying!
        TimesUp = true;
        CountDownIndex = 0;
        return;
    }

    if (CountingDown)
    {
        if ((Secs < 11) && !Mins && !ClockSpoken1 && (MotorOnSeconds > 2))
        {
            PlaySound(Cdown[CountDownIndex]);
            ++CountDownIndex;
            ClockSpoken1 = true;
        }
    }

    if (!Secs && SpeakingClock && !ClockSpoken)
    {
        ClockSpoken = true;
        if ((Mins <= 10) && (Mins > 0))
        {
            PlaySound(Recording[Mins - 1]);
        }
        if (Mins)
        {
            if (UseLog)
            {
                LogTimer(Mins);
                LogRPM(RotorRPM);
            }
        }
    }
}
// ************************************************************************************************************/
void ShowMotor() // Show the state of the motor on the front view by changing the colour of the motor button and by playing a sound if it has just been turned on or off
{
    char bt0[] = "bt0";
    char OnMsg[] = "Motor is ON";
    char OffMsg[] = "Motor is OFF";
    if (MotorEnabled)
        SendText(bt0, OnMsg);
    else
        SendText(bt0, OffMsg);
}
// ************************************************************************************************************/
void MotorEnabledHasChanged() //
{
    if (MotorEnabled)
    {
        if (LedWasRed && !BuddyPupilOnWireless)
        {
            MotorEnabled = false;  // user has not turned on motor, so turn it back off
            PlaySound(PLSTURNOFF); // Tell the pilot to turn off motor before it will work
            SendNoData = true;     // send no data until motor is turned on again (so that pilot has to turn it on again before it will work)
            DelayWithDog(4000);    // allow time for sound to play and for pilot to react
            return;
        }
        // V1B B16 (Malcolm, 1-10-2026): "when motor moves from off to on, the screen should move to the front screen if
        // it was not there, so that we KNOW we are on front screen when flying." Only in the normal mode - never in the
        // middle of a calibration, a scan, a buddy session or a Rotorflight save or restore, which would be left half
        // done - and with no question waiting on screen. Edits not yet confirmed on the page that was showing are left
        // behind, never half-applied; a Rotorflight read in progress stops (its values would land on a page that is gone).
        if (CurrentView != FRONTVIEW && CurrentMode == NORMAL && !ModalWaits)
        {
            Reading_PIDS_Now = false;
            Reading_PIDS_Advanced_Now = false;
            Reading_RATES_Now = false;
            Reading_RATES_Advanced_Now = false;
            Reading_GOV_Now = false;
            Reading_GOV_Config_Now = false;
            LogFrontPageReason("the motor switch went on"); // B172
            GotoFrontView(); // (also wakes a blank screen)
        }
        ShowMotor();
        if (AnnounceBanks)
        {
            PlaySound(MOTORON); // Tell the pilot motor is on!
            DelayWithDog(750);  // allow time for sound to play as Bank change sound would be played at the same time and we don't want them to overlap
        } 
        if (UseLog)
            LogMotor(1);
        MotorStartTime = millis(); // Motor ON timerpause off
    }
    else
    {
        if (AnnounceBanks)
            PlaySound(MOTOROFF);
        SendNoData = false; // can send data!
        if (UseLog)
            LogMotor(0);
        SendCommand(WarnOff);
        ShowMotor(); // Tell the pilot motor is off
        if (SendNoData)
        {
            SendCommand(WarnOff);
            SendNoData = false; // user turned off motor
        }
        PausedSecs = MotorOnSeconds; //    Motor OFF timerpause started
    }
    LastSeconds = 0;
    ShowMotorTimer();
}
//************************************************************************************************************/
// B192 (Malcolm, 6 Nov 2026, Mehul's RAW420 with its safety switch the wrong way: "if we connect to a model ... and safety
// is off at connection time, we should warn the user clearly 'safety is off!!' ... safety requires that we connect
// disarmed every time, never armed."): a FRESH connection (this model not connected in the last minute - a drop-out
// in the air that comes back is not one) with a safety switch defined and OFF: "Safety off" is said (up to three times,
// 8 s apart) and the front page's box reads SAFETY IS OFF!! until the safety goes on, the motor goes on, or the model
// goes. A warning only: nothing waits, nothing is blocked (Priority One - the sticks are never held up).
bool SafetyOffWarning = false;
static uint32_t SafetyWarnNextSay = 0;
static uint8_t SafetyWarnSaid = 0;
static uint32_t LastGreenLostMs = 0;  // (RedLedOn: the moment the last connection was lost; 0 = none yet)
static int LastGreenModel = -1;
void NoteConnectionLost() { LastGreenLostMs = millis() | 1; }
void SafetyOffAtConnect() // GreenLedOn, once per connection
{
    const bool fresh = LastGreenModel != (int)ModelNumber || !LastGreenLostMs || (millis() - LastGreenLostMs) > 60000UL;
    LastGreenModel = (int)ModelNumber;
    if (!fresh || !SafetyIsOff())
        return;
    SafetyOffWarning = true;
    SafetyWarnSaid = 0;
    SafetyWarnNextSay = millis() + 2500; // (after "Model matched - connected")
    if (UseLog)
    {
        char t[] = "SAFETY WAS OFF AT CONNECTION";
        LogText(t, strlen(t), true);
    }
}
void SafetyOffWarningTick() // the main loop's regular round (beside CheckBatteryStates)
{
    if (!SafetyOffWarning)
        return;
    if (!LedWasGreen || !SafetyIsOff() || MotorEnabled)
    {
        SafetyOffWarning = false;
        if (CurrentView == FRONTVIEW && !(RotorFlight_V && LedWasGreen) && !BatteryWarningShown)
            SendCommand(WarnOff); // (a Rotorflight model's box goes back to the ESC temperature at its next second)
        return;
    }
    if (CurrentView == FRONTVIEW && !BatteryWarningShown)
    { // B193 (Malcolm: "Safety is off!! (Arming is on!!) for ultimate clarity"): the two in turn, a second each - the
      // box is one line of 190 px and "SAFETY IS OFF!!" alone is 199 (fontw.py 6): these are 168 and 158
        static bool second = false;
        second = !second;
        SendCommand(WarnNow);
        SendText((char *)"Warning", (char *)(second ? "ARMING ON!!" : "SAFETY OFF!!"));
    }
    if (SafetyWarnSaid < 3 && (int32_t)(millis() - SafetyWarnNextSay) >= 0)
    {
        Force_Early_Sound = true;
        PlaySound(SAFEOFF);
        ++SafetyWarnSaid;
        SafetyWarnNextSay = millis() + 8000;
    }
}
//************************************************************************************************************/
void SafetySwitchChanged()
{
    ShowSafety();
    if (SafetyON)
    {
        SendNoData = false;
        Armed = false;
    }
    else
    {
        Armed = true;
    }
    SafetyWasOn = SafetyON;
}

#endif
