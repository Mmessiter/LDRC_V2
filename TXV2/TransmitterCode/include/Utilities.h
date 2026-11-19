// *********************************************** utilities.h for Transmitter code *******************************************

#include <Arduino.h>
#include "1Definitions.h"
#ifndef UTILITIES_H
#define UTILITIES_H

// ********************************************************************************************************************************

// Because data are only displayed when different, this sets all to zero so that they will be displayed on the first pass.
void ForceDataRedisplay()
{
    LastShowTime = 0; //
    ForceVoltDisplay = true;
    for (int i = 0; i <= BANKS_USED; ++i) // (B211: every bank the table has - it was "5" and "17")
    {
        for (int j = 0; j <= CHANNELSUSED; ++j)
        {
            LastTrim[i][j] = 0;
        }
    }
    return;
}

// ********************************************************************************************************************************

void SaveOrRestoreScreen(bool Restore)
{
    // V1B B17 (Malcolm, 1-10-2026): "When not flying, if the screen times out and goes blank, a touch should really
    // return to the screen that was in use at the timeout moment." Every page now comes back, not only the seventeen
    // that did before; the rest went to the front page. The screen (1.4.3 and later) remembers the page exactly as it
    // was when it went blank - values, texts, what was hidden, edits not yet confirmed - and puts it back when this
    // asks for the same page again, so nothing here re-reads, re-sends or re-starts anything: the page's own Start
    // function is NOT called (some reset things: StartTrimDefView zeroes the trims, the Rotorflight pages read the
    // flight controller afresh, GotoModelsView asks a question). Only what is drawn with lines is drawn again.
    // The screen saver never blanks in the middle of a calibration, a scan, trim setting or Pong (CheckScreenTime).
    static uint8_t LastScreen = 0;
    if (!Restore)
    {
        LastScreen = CurrentView; // Saved the ID of the screen we are leaving
        return;
    }
    if (LastScreen == FRONTVIEW)
    {
        GotoFrontView(); // (it fills itself in)
        return;
    }
    static const struct
    {
        uint8_t view;
        const char *page;
    } Pages[] = {
        {STICKSVIEW, "SticksView"}, {GRAPHVIEW, "GraphView"}, {MIXESVIEW, "MixesView"}, {MODELSVIEW, "ModelsView"},
        {CALIBRATEVIEW, "CalibrateView"}, {TXSETUPVIEW, "TXSetupView"}, {SUBTRIMVIEW, "SubTrimView"}, {DATAVIEW, "DataView"},
        {TRIM_VIEW, "TrimView"}, {MACROS_VIEW, "MacrosView"}, {SWITCHES_VIEW, "SwitchesView"}, {ONE_SWITCH_VIEW, "OneSwitchView"},
        {HELP_VIEW, "LogView"}, {OPTIONS_VIEW, "OptionsView"}, {INPUTS_VIEW, "InputsView"}, {FAILSAFE_VIEW, "FailSafeView"},
        {COLOURS_VIEW, "BackGroundView"}, {AUDIOVIEW, "AudioView"}, {REVERSEVIEW, "ReverseView"}, {BUDDYVIEW, "BuddyView"},
        {LOGVIEW, "LogView"}, {OPTIONVIEW2, "OptionView2"}, {OPTIONVIEW3, "OptionView3"}, {BUDDYCHVIEW, "BuddyChView"},
        {RXSETUPVIEW1, "RXOptionsView"}, {DUALRATESVIEW, "DualRatesView"}, {GPSVIEW, "GPSView"}, {RXSETUPVIEW, "RXSetupView"},
        {BANKSNAMESVIEW, "BankNameView"}, {SLOWSERVOVIEW, "SlowServoView"}, {RENAMEMODELVIEW, "RenameView"},
        {FILEEXCHANGEVIEW, "FileExchView"}, {IDCHECKVIEW, "IDsView"}, {TYPEVIEW, "TypeView"}, {SERVOTYPESVIEW, "ServosTypeView"},
        {LOGFILESLISTVIEW, "LogFiles"}, {GAPSVIEW, "GapsView"}, {PIDVIEW, "PIDView"}, {RATESVIEW_RF, "RatesView"},
        {ROTORFLIGHTVIEW, "RFView"}, {RATESADVANCEDVIEW, "Rates_A_View"}, {PIDADVANCEDVIEW, "PID_A_View"},
        {PICKBANKVIEW1, "PickBankView1"}, {PICKBANKVIEW2, "PickBankView2"}, {CHOOSEIMAGEVIEW, "ImageView"},
        {RFBACKUP_RESTOREVIEW, "RFBackUpView"}, {RFGOVERNORVIEW_PROFILE, "RFGovView"}, {RFGOVERNORVIEW_GLOBAL, "RFGovViewGlbl"},
        {MODELIDVIEW, "IDsStartView"},
        // B65 (Malcolm, 8 Oct: "when the screen times out, it would be helpful if it returned to the one I was editing"):
        // the Rotorflight pages of B50-B61, with their edits, as the screen kept them
        {RESCUEVIEW, "RescueView"}, {RESCUE2VIEW, "Rescue2View"}, {SERVOVIEW, "ServoView"}, {RFSETUPVIEW, "RFSetupView"},
        {TRAVELVIEW, "TravelView"}, {TRAVEL2VIEW, "Travel2View"}, {TRAVEL3VIEW, "Travel3View"}, {TRAVEL4VIEW, "Travel4View"}, {BASICSVIEW, "BasicsView"}, {BASICS2VIEW, "Basics2View"}, {PORTSVIEW, "PortsView"}, {ESCCALVIEW, "EscCalView"}, {EASYVIEW, "EasyView"}, {RATESTYPEVIEW, "RatesTypeView"}, {RATESCURVEVIEW, "RatesCurveView"}, {FILTERVIEW, "FilterView"}, {FILTER2VIEW, "Filter2View"}, {ADJUSTVIEW, "AdjustView"}, {ADJPICKVIEW, "AdjPickView"}, {SWITCHVIEW, "SwitchView"}, {SWITCHPICKVIEW, "SwitchPickView"}, {COPYBANKVIEW, "CopyBankView"}, {BATTERYVIEW, "BatteryView"}, {BATSENSORSVIEW, "BatSensorsView"}, {BLACKBOXVIEW, "BlackboxView"}, {LEVELVIEW, "LevelView"},
#ifdef ELRS_TEST // ELRS, TEST BUILDS ONLY: the page "ELRS settings" and its picker too (the screen remembers each as it was). The #else is the transmitter as it was
        {BEEPERVIEW, "BeeperView"}, {TOOLSVIEW, "RFToolsView"}, {CHECKVIEW, "RFCheckView"}, {DIRVIEW, "RFDirView"}, {CHANGESVIEW, "RFChangesView"}, {GUIDEVIEW, "RFGuideView"}, {ELRSVIEW, "ElrsView"}, {ELRSPICKVIEW, "ElrsPickView"}};
#else
        {BEEPERVIEW, "BeeperView"}, {TOOLSVIEW, "RFToolsView"}, {CHECKVIEW, "RFCheckView"}, {DIRVIEW, "RFDirView"}, {CHANGESVIEW, "RFChangesView"}, {GUIDEVIEW, "RFGuideView"}};   // (B196: Beeper & name, and Guide & checks' pages)
#endif
    for (const auto &p : Pages)
    {
        if (p.view != LastScreen)
            continue;
        char cmd[40];
        snprintf(cmd, sizeof cmd, "page %s", p.page);
        SendCommand(cmd);
        CurrentView = LastScreen; // (the old code set OPTIONS_VIEW for the inputs page)
        switch (LastScreen)
        {
        case DATAVIEW:
            ForceDataRedisplay(); // live values: all of them again at once
            break;
        case GPSVIEW:
        case GAPSVIEW:
            LastShowTime = 0; // filled in by ShowComms() at once
            break;
        case GRAPHVIEW:
            DisplayCurveAndServoPos(); // the curve is drawn with lines: the screen does not remember those
            break;
        case SUBTRIMVIEW:
            SubTrimPageBack(); // B211 (the fourteenth review): the page as the model has it - a writing-out owed when the screen went blank had been forgotten (Trims.h)
            break;
        default:
            break;
        }
        return;
    }
    GotoFrontView(); // a page the screen saver never blanks (a scan, a calibration under way, trim setting, Pong), or none
}

/*********************************************************************************************************************************/
void RestoreBrightness()
{
    char cmd[20];
    char dim[] = "dim=";
    char nb[10];
    if (Brightness < 10)
        Brightness = 10;
    strcpy(cmd, dim);
    Str(nb, Brightness, 0);
    strcat(cmd, nb);
    ScreenIsOff = false;
    SendCommand(cmd);
    ScreenTimeTimer = millis(); // reset screen counter
}

/******************************************************************************************************************************/
void ShowScreenAgain()
{
    SaveOrRestoreScreen(true);
    ScreenIsOff = false;
    RestoreBrightness();
}

/******************************************************************************************************************************/
void HideScreenAgain()
{
    char ScreenOff[] = "page BlankView";
    char NoBrightness[] = "dim=0";

    if (CurrentView == SCANVIEW)
        return; // recovery fails
    if (CurrentView == GRAPHVIEW)
        return;
    if (CurrentView == COLOURS_VIEW)
        return;
    if (CurrentView == AUDIOVIEW)
        return;
    if (CurrentView == HELP_VIEW)
        return;
    if (CurrentView == PONGVIEW)
        return;
    if (CurrentView == CALIBRATEVIEW)
        return;
    if (RfPageJobRuns() || RfPageWatchRuns() || RfVerifyPending()) // (e99e: ... nor over a save's read-back: the write landed under the blank and the page came back stuck in "Sent: reading back ..."; tried again a second later)
        return; // B211 (the sixteenth review): not over a Rotorflight page's read or save - its poll would end the job with the page (main.cpp)

    SaveOrRestoreScreen(false);
    SendCommand(ScreenOff);    // move to blank screen
    DelayWithDog(10);          // wait a moment for screen to change
    SendCommand(NoBrightness); // turn off backlight
    ScreenIsOff = true;
    CurrentView = BLANKVIEW;
}

/*********************************************************************************************************************************/
void CheckScreenTime() // turn off screen after a timeout
{
    CRUMB(CRUMB_SCREENTIME);
    if (CurrentMode != NORMAL && CurrentMode != LISTENMODE)
    { // B17: never in the middle of something - a calibration, a scan, trim setting, Pong, a Rotorflight save or
      // restore. Coming back from blank could not resume it. (The timeout starts again when it is over.)
        ScreenTimeTimer = millis();
        return;
    }
    if (((millis() - ScreenTimeTimer) > ScreenTimeout * 1000) && (ScreenIsOff == false))
        HideScreenAgain();
}

// ********************************************************************************************************************************

void CheckForNextionButtonPress()
{
    if (GetButtonPress())
    {
        const uint32_t lost = BoxesLost;
        if (!ModalWaits)
            BoxesLostAtWork = BoxesLost; // (a button's work begins here - a question's own buttons belong to the work that asked the question)
        ButtonWasPressed();
        if (BoxesLost != lost)
            NoteBoxesLost(); // B211 (the eighth review): a box this button's work asked for had no answer - what the page held there was not taken, and the pilot is told
    }
}

// **********************************************************************************************************************************

uint8_t Ascii(char c)
{
    return (uint8_t)c;
}

// **************************************************************** Play a sound from RAM *********************************************
// ──────────────────────────────────────────────────────────────
// Play a RAM-resident clip on the Nextion
// ──────────────────────────────────────────────────────────────
void PlaySound(uint16_t id)
{
    CRUMB(CRUMB_SOUND);
    if (millis() < 5000 && !Force_Early_Sound)
        return;                // don't play any sounds for the first 5 seconds of power up, except the forced early sound (e.g. for binding enabled)
    Force_Early_Sound = false; // reset this flag so that we don't play any more sounds for the first 5 seconds of power up
    // B161 (Malcolm, 31 Oct 2026, a V1 receiver on the green: "the announcements, such as connected, disconnected, model
    // memory found, etc, these often failed to be heard"): until now NO sound but a click was played while the Models page
    // was showing - a rule from the original Nextion, whose own audio and its long model lists did not mix. The V2 screen
    // plays from a ring of its own, whatever its page is doing, and the Models page is exactly where a pilot sorting a model
    // out stands when "Connected" or "Model memory found" is said. So the rule is gone.
    if (!SD_Card_Exists)
        return;
    char cmd[24];
    snprintf(cmd, sizeof(cmd), "play 0,%u,0", id); // loop = 0 (play once)
    SendCommand(cmd);                              // appends 0xFF³
}
/*********************************************************************************************************************************/

// This function converts an int to a char[] array, then adds a comma, a dot, or nothing at the end.
// It builds the char[] array at a pointer (*s) Where there MUST be enough space for all characters plus a zero terminator. (MAX 14)
// It dates for a very early time when I didn't know about standard library functions!
// But it works just fine, so it says in.

FASTRUN char *Str(char *s, int n, int comma) // comma = 0 for nothing, 1 for a comma, 2 for a dot.
{
    int r, i, m, flag;
    char cma[] = ",";
    char dot[] = ".";

    flag = 0;
    i = 0;
    m = 1000000000;
    if (n < 0)
    {
        s[0] = '-';
        i = 1;
        n = -n;
    }
    if (n == 0)
    {
        s[0] = 48;
        s[1] = 0;

        if (comma == 1)
        {
            strcat(s, cma);
        }
        if (comma == 2)
        {
            strcat(s, dot);
        }
        return s;
    }
    while (m >= 1)
    {
        r = n / m;
        if (r > 0)
        {
            flag = 1;
        } //  first digit
        if (flag == 1)
        {
            s[i] = 48 + r;
            ++i;
            s[i] = 0;
        }
        n -= (r * m);
        m /= 10;
    }
    if (comma == 1)
    {
        strcat(s, cma);
    }
    if (comma == 2)
    {
        strcat(s, dot);
    }
    return s;
}

/*********************************************************************************************************************************/

void SetAudioVolume(uint16_t v)
{ // sets audio volume v (0-100)
    char vol[] = "volume=";
    char cmd[20];
    char nb[6];
    strcpy(cmd, vol);
    Str(nb, v, 0);
    strcat(cmd, nb);
    SendCommand(cmd);
}

/*********************************************************************************************************************************/

void Reboot()
{
    while (true)
    {
        TeensyWatchDog.feed();
    }
}

/*********************************************************************************************************************************/
void InitializeCommsGapScreen()
{
    char tBox[11][4] = {
        "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9", "t10", "t11"};
    char txt[12];
    for (int i = 1; i < 11; ++i)
    {
        sprintf(txt, "< %u", GapThesholds[i]);
        SendText(tBox[i - 1], txt);
    }
    SendCommand((char *)"vis n0,0"); // hide the 0 count§");
    SendCommand((char *)"vis n1,0");
    SendCommand((char *)"vis n2,0");
    SendCommand((char *)"vis n3,0");
    SendCommand((char *)"vis n4,0");
    SendCommand((char *)"vis n5,0");
    SendCommand((char *)"vis n6,0");
    SendCommand((char *)"vis n7,0");
    SendCommand((char *)"vis n8,0");
    SendCommand((char *)"vis n9,0");
    SendCommand((char *)"vis n10,0");
    sprintf(txt, "> %u", GapThesholds[10]);
    SendText(tBox[10], txt);
}
/*********************************************************************************************************************************/
// V1B: timed by the CPU's cycle counter, not millis(). Writing or erasing flash (LinkMode.h) holds interrupts
// off for tens of milliseconds at a time, and millis() stands nearly still meanwhile: by millis() the dog would
// go unfed for seconds of real time. (The counter wraps every 7 s; this is called far more often than that.)
uint32_t LastDogKickCycles = 0;
void KickTheDog()
{
    if ((uint32_t)(ARM_DWT_CYCCNT - LastDogKickCycles) >= (F_CPU_ACTUAL / 1000u) * KICKRATE)
    {
        TeensyWatchDog.feed();
        LastDogKickCycles = ARM_DWT_CYCCNT;
    }
    CrumbKick(); // B14/B15: the breadcrumb to the clock's coin cell (at most every 50 ms)
}
// **********************************************************************************************************************************

void ConfigureStickMode()
{ // This sets stick mode without moving any wires. Must be wired as for Mode 1

    if (SticksMode == 1)
    {
        AnalogueInput[0] = A0;
        AnalogueInput[1] = A1;
        AnalogueInput[2] = A2;
        AnalogueInput[3] = A3;
        AnalogueInput[4] = A6;
        AnalogueInput[5] = A7;
        AnalogueInput[6] = A8;
        AnalogueInput[7] = A9;
    }

    if (SticksMode == 2)
    {
        AnalogueInput[0] = A0;
        AnalogueInput[1] = A2;
        AnalogueInput[2] = A1;
        AnalogueInput[3] = A3;
        AnalogueInput[4] = A6;
        AnalogueInput[5] = A7;
        AnalogueInput[6] = A8;
        AnalogueInput[7] = A9;
    }
}

/******************* DeltaGMT is a user defined representation of time zone. It should never exceed 24. Not on this planet. **********/
void FixDeltaGMTSign()
{
    if (DeltaGMT < -24)
        DeltaGMT = 0; // Undefined value?f
    if (DeltaGMT > 24)
    {                         // This fixes the sign bit if negative !!!! (There's surely a better way !!!)
        DeltaGMT ^= 0xffff;   // toggle every bit! :-)
        ++DeltaGMT;           // Add one
        DeltaGMT = -DeltaGMT; // it's definately meant to be negative!
    }
}
/*********************************************************************************************************************************/

uint8_t decToBcd(uint8_t val)
{
    return ((val / 10 * 16) + (val % 10));
}

/*********************************************************************************************************************************/

uint8_t bcdToDec(uint8_t val)
{
    return ((val / 16 * 10) + (val % 16));
}

/*********************************************************************************************************************************/

FLASHMEM void SetTheRTC()
{
    uint8_t zero = 0x00;
    Wire.beginTransmission(DS1307_ADDRESS);
    Wire.write(zero); // Stop the oscillator
    Wire.write(decToBcd(Gsecond));
    Wire.write(decToBcd(Gminute));
    Wire.write(decToBcd(Ghour));
    Wire.write(decToBcd(GweekDay));
    Wire.write(decToBcd(GmonthDay));
    Wire.write(decToBcd(Gmonth));
    Wire.write(decToBcd(Gyear));
    Wire.write(zero); //  Re-start it
    Wire.endTransmission();
}
/*********************************************************************************************************************************/
// Epoch <-> calendar (Howard Hinnant's civil-days algorithms).
int64_t DaysFromCivil(int y, unsigned m, unsigned d)
{
    y -= m <= 2;
    const int era = (y >= 0 ? y : y - 399) / 400;
    const unsigned yoe = (unsigned)(y - era * 400);
    const unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return (int64_t)era * 146097 + (int64_t)doe - 719468;
}
void CivilFromDays(int64_t z, int &y, unsigned &m, unsigned &d)
{
    z += 719468;
    const int64_t era = (z >= 0 ? z : z - 146096) / 146097;
    const unsigned doe = (unsigned)(z - era * 146097);
    const unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    y = (int)(yoe) + (int)(era * 400);
    const unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    const unsigned mp = (5 * doy + 2) / 153;
    d = doy - (153 * mp + 2) / 5 + 1;
    m = mp + (mp < 10 ? 3 : -9);
    y += m <= 2;
}

/*********************************************************************************************************************************/
// V2 B30 (Malcolm, 5-10-2026: "the real-time clock ... occasionally simply refuses to give us any time and has to be
// reset"). A DS1307 that stops answering is nearly always an I2C bus left half-way through a byte (a brown-out, a
// glitch): it holds SDA low and nothing on the bus can speak until it has been clocked out of it. At power-on, a
// clock that does not answer gets the standard cure - nine clock pulses with the bus released, then a stop - and is
// asked again. The time itself is kept by the chip's own battery through all this; and from B30 the screen sends the
// true time from the internet whenever it has WiFi (TIME=, below), as a phone does through the receiver.
bool ClockRecovered = false, ClockDead = false; // at power-on: it had to be clocked back to life / it does not answer at all
void RecoverI2CBus()
{
    const uint8_t SCL = 19, SDA = 18; // Wire's pins on the Teensy 4.1
    pinMode(SDA, INPUT_PULLUP);
    pinMode(SCL, OUTPUT_OPENDRAIN);
    for (int i = 0; i < 9; ++i)
    {
        digitalWrite(SCL, LOW);
        delayMicroseconds(5);
        digitalWrite(SCL, HIGH);
        delayMicroseconds(5);
        if (digitalRead(SDA))
            break; // the slave has let go
    }
    pinMode(SDA, OUTPUT_OPENDRAIN); // a stop: SDA low to high while SCL is high
    digitalWrite(SDA, LOW);
    delayMicroseconds(5);
    digitalWrite(SCL, HIGH);
    delayMicroseconds(5);
    digitalWrite(SDA, HIGH);
    delayMicroseconds(5);
    Wire.begin(); // the pins back to the bus
}
void CheckTheClock() // at power-on, after Wire.begin()
{
    if (RTC.read(tm))
        return;
    RecoverI2CBus();
    delay(5);
    if (RTC.read(tm))
    {
        ClockRecovered = true;
        return;
    }
    ClockDead = true;
}
// The screen's word TIME=<local seconds since 1970> (from the internet, whenever it has WiFi): applied as a phone's time is
void TimeFromScreen(const char *digits)
{
    const uint32_t v = (uint32_t)strtoul(digits, nullptr, 10);
    if (v < 1700000000u)
        return;
    PhoneEpochLocal = v;
    PhoneEpochAtMs = millis();
}

/*********************************************************************************************************************************/
// Correct our drifty DS1307 from the phone-true LOCAL time RXV2 streams in
// ack item 37 (only when the receiver's clock came from a phone). Captured in
// the radio path, applied HERE — I2C writes must never run there. Corrections
// only when >= 10 s adrift, so the bus stays quiet in normal operation.
void CorrectRtcFromPhoneTime()
{
    if (!PhoneEpochLocal)
        return;
    const uint32_t nowEpoch = PhoneEpochLocal + (millis() - PhoneEpochAtMs) / 1000;
    PhoneEpochLocal = 0; // consumed — the next ack cycle refreshes it
    if (nowEpoch < 1700000000u)
        return; // insane value — ignore
    int32_t diff = 1000000;
    if (RTC.read(tm))
    { // (a clock that does not answer is written all the same: the write is what starts a halted one, B30)
        ReadTheRTC();
        const int64_t face = DaysFromCivil(2000 + Gyear, Gmonth, GmonthDay) * 86400LL + (int64_t)Ghour * 3600 + (int64_t)Gminute * 60 + Gsecond;
        diff = (int32_t)((int64_t)nowEpoch - face);
    }
    if (abs(diff) < 10)
        return; // close enough — leave the RTC alone
    int y;
    unsigned mo, da;
    const int64_t days = (int64_t)(nowEpoch / 86400u);
    CivilFromDays(days, y, mo, da);
    Gyear = (uint8_t)(y - 2000);
    Gmonth = (uint8_t)mo;
    GmonthDay = (uint8_t)da;
    GweekDay = (uint8_t)(((days + 4) % 7) + 1); // 1970-01-01 was a Thursday; 1 = Sunday
    Ghour = (uint8_t)((nowEpoch / 3600u) % 24);
    Gminute = (uint8_t)((nowEpoch / 60u) % 60);
    Gsecond = (uint8_t)(nowEpoch % 60);
    SetTheRTC();
    GPSTimeSynched = true; // phone truth is at least as good — don't let GPS fight it this session
}

/*********************************************************************************************************************************/
void SynchRTCwithGPSTime()
{ // This function corrects the time and the date.
    if (!GPSTimeSynched)
    {
        GPSTimeSynched = true;
        Gsecond = GPS_RX_SECS;
        Gminute = GPS_RX_Mins;
        Ghour = GPS_RX_Hours;
        GmonthDay = GPS_RX_DAY;
        Gmonth = GPS_RX_MONTH;
        Gyear = GPS_RX_YEAR;
        SetTheRTC();
        GPSTimeSynched = true;
    }
}
/*********************************************************************************************************************************/
void AdjustDateTime(uint8_t MinChange, uint8_t HourChange, uint8_t YearChange, uint8_t MonthChange, uint8_t DateChange)
{
    ReadTheRTC();
    Gminute += MinChange;
    if (Gminute > 59)
    {
        Gminute = 0;
        if (Ghour < 23)
        {
            ++Ghour;
        }
    }
    if (Gminute < 1)
    {
        Gminute = 0;
        if (Ghour > 0)
        {
            --Ghour;
        }
    }
    Ghour += HourChange;
    if (Ghour < 0)
        Ghour = 0;
    if (Ghour > 23)
        Ghour = 23;
    Gyear += YearChange;
    if (Gyear < 0)
        Gyear = 0;
    if (Gyear > 99)
        Gyear = 99;
    Gmonth += MonthChange;
    if (Gmonth < 1)
        Gmonth = 1;
    if (Gmonth > 12)
        Gmonth = 12;
    GmonthDay += DateChange;
    if (GmonthDay < 1)
        GmonthDay = 1;
    if (GmonthDay > 31)
        GmonthDay = 31;
    SetTheRTC();
}

/*********************************************************************************************************************************/
void ReadTheRTC()
{
    CRUMB(CRUMB_RTC);
    uint8_t second = tm.Second; // 0-59
    uint8_t minute = tm.Minute; // 0-59
    uint8_t hour = tm.Hour;     // 0-23
    uint8_t weekDay = tm.Wday;  // 1-7
    uint8_t monthDay = tm.Day;  // 1-31
    uint8_t month = tm.Month;   // 1-12
    uint8_t year = tm.Year;     // 0-99
    Gsecond = second;
    Gminute = minute;
    Ghour = hour;
    GweekDay = weekDay;
    GmonthDay = monthDay;
    Gmonth = month;
    Gyear = year - 30; // ???
    // B169: the Teensy's own clock follows the clock chip, so the card's files - backups, logs, models.dat - carry the right date
    // and time (the card's library dates every file it writes from the Teensy's clock, which started at 1 Jan 2019 at every
    // power-up: it has no battery). Only from a chip that is set (2024 or later), and only when the two differ.
    if (tm.Year >= 54) // (years since 1970)
    {
        const uint32_t chip = (uint32_t)makeTime(tm);
        const uint32_t own = Teensy3Clock.get();
        if ((own > chip ? own - chip : chip - own) > 2)
            Teensy3Clock.set(chip);
    }
}
/*********************************************************************************************************************************/

void IncMinute()
{
    uint8_t zero = 0x00;
    uint8_t c = 1;
    if (RTC.read(tm))
    {
        AdjustDateTime(c, zero, zero, zero, zero);
    }
}

/*********************************************************************************************************************************/

void DecMinute()
{
    uint8_t zero = 0x00;
    uint8_t c = -1;
    if (RTC.read(tm))
    {
        AdjustDateTime(c, zero, zero, zero, zero);
    }
}

/*********************************************************************************************************************************/

void IncHour()
{
    uint8_t c = 1;
    uint8_t zero = 0x00;
    if (RTC.read(tm))
    {
        AdjustDateTime(zero, c, zero, zero, zero);
    }
}

/*********************************************************************************************************************************/

void DecHour()
{
    uint8_t c = -1;
    uint8_t zero = 0x00;
    if (RTC.read(tm))
    {
        AdjustDateTime(zero, c, zero, zero, zero);
    }
}

/*********************************************************************************************************************************/

void IncYear()
{
    uint8_t c = 1;
    uint8_t zero = 0x00;
    if (RTC.read(tm))
    {
        AdjustDateTime(zero, zero, c, zero, zero);
    }
}

/*********************************************************************************************************************************/

void DecYear()
{
    uint8_t c = -1;
    uint8_t zero = 0x00;
    if (RTC.read(tm))
    {
        AdjustDateTime(zero, zero, c, zero, zero);
    }
}

/*********************************************************************************************************************************/

void IncMonth()
{
    uint8_t c = 1;
    uint8_t zero = 0x00;
    if (RTC.read(tm))
    {
        AdjustDateTime(zero, zero, zero, c, zero);
    }
}

/*********************************************************************************************************************************/

void DecMonth()
{
    uint8_t c = -1;
    uint8_t zero = 0x00;
    if (RTC.read(tm))
    {
        AdjustDateTime(zero, zero, zero, c, zero);
    }
}

/*********************************************************************************************************************************/

void IncDate()
{
    uint8_t c = 1;
    uint8_t zero = 0x00;
    if (RTC.read(tm))
    {
        AdjustDateTime(zero, zero, zero, zero, c);
    }
}

/*********************************************************************************************************************************/

void DecDate()
{
    uint8_t c = -1;
    uint8_t zero = 0x00;
    if (RTC.read(tm))
    {
        AdjustDateTime(zero, zero, zero, zero, c);
    }
}

/*********************************************************************************************************************************/

bool getTime(const char *str)
{
    int Hour, Min, Sec;
    if (sscanf(str, "%d:%d:%d", &Hour, &Min, &Sec) != 3)
        return false;
    tm.Hour = Hour;
    tm.Minute = Min;
    tm.Second = Sec;
    return true;
}

/*********************************************************************************************************************************/

bool getDate(const char *str)
{
    char Month[12];
    int Day, Year;
    uint8_t monthIndex;
    const char *monthName[12] = {
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"};
    if (sscanf(str, "%s %d %d", Month, &Day, &Year) != 3)
        return false;
    for (monthIndex = 0; monthIndex < 12; ++monthIndex)
    {
        if (strcmp(Month, monthName[monthIndex]) == 0)
            break;
    }
    if (monthIndex >= 12)
        return false;
    tm.Day = Day;
    tm.Month = monthIndex + 1;
    tm.Year = CalendarYrToTm(Year);
    return true;
}

/*********************************************************************************************************************************/

bool MayBeAddZero(uint8_t nn)
{
    if (nn >= 0 && nn < 10)
    {
        return true;
    }
    return false;
}

/*********************************************************************************************************************************/

void ReadTime()
{
    CRUMB(CRUMB_TIME);

    static char month[12][15] = {"January", "February", "March", "April", "May", "June", "July", "August", "Sept", "October", "November", "December"};
    static char ShortMonth[12][7] = {"Jan.", "Feb.", "Mar.", "Apr.", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."};

    char NB[10];
    char TimeString[80];
    char Space[] = " ";
    char colon[] = ":";
    char zero[] = "0";
    char DateTime[] = "DateTime";

    uint8_t DisplayedHour;
    FixDeltaGMTSign();
    if (CurrentView == FRONTVIEW || CurrentView == OPTIONVIEW2)
    {
        if (RTC.read(tm))
        {
            strcpy(TimeString, Str(NB, tm.Day + DateFix, 0));
            if (CurrentView == OPTIONVIEW2)
            {
                if ((tm.Day) < 10)
                {
                    strcat(TimeString, Space); // to align better the rest of the data
                    strcat(TimeString, Space);
                }
            }
            strcat(TimeString, Space);
            if (CurrentView == OPTIONVIEW2)
            {
                strcat(TimeString, ShortMonth[tm.Month - 1]);
            }
            else
            {
                strcat(TimeString, month[tm.Month - 1]);
            }
            strcat(TimeString, Space);
            strcat(TimeString, (Str(NB, tmYearToCalendar(tm.Year), 0)));
            strcat(TimeString, Space);
            int LocalHour = (int)tm.Hour + DeltaGMT; // ClaudeFix-2-7-2026 signed: DisplayedHour is uint8_t, so a negative GMT wrapped it to ~251 and the <0 fix never ran
            DateFix = 0;
            if (LocalHour >= 24)
            {
                LocalHour -= 24;
                DateFix = 1;
            }
            if (LocalHour < 0)
            {
                LocalHour += 24;
                DateFix = -1;
            }
            DisplayedHour = (uint8_t)LocalHour;
            if (MayBeAddZero(DisplayedHour))
                strcat(TimeString, zero);
            strcat(TimeString, Str(NB, DisplayedHour, 0));
            strcat(TimeString, colon);
            if (MayBeAddZero(tm.Minute))
                strcat(TimeString, zero);
            strcat(TimeString, Str(NB, tm.Minute, 0));
            strcat(TimeString, colon);
            if (MayBeAddZero(tm.Second))
                strcat(TimeString, zero);
            strcat(TimeString, Str(NB, tm.Second, 0));
            SendText(DateTime, TimeString);
        }
    }
}
/************************************************************************************************************/
FLASHMEM void ResetSubTrims()
{
    for (int i = 0; i < 16; ++i)
    {
        SubTrims[i] = 127;
    }
}
/**************************** Clear Macros if junk was loaded from SD ********************************************************************************/
void CheckMacrosBuffer()
{

    bool junk = false;
    for (uint8_t i = 0; i < MAXMACROS; ++i)
    {
        if (MacrosBuffer[i][MACROTRIGGERCHANNEL] > 16)
            junk = true;
        if (MacrosBuffer[i][MACROMOVECHANNEL] > 16)
            junk = true;
        if (MacrosBuffer[i][MACROMOVETOPOSITION] > 180)
            junk = true;
        if (MacrosBuffer[i][MACROTRIGGERCHANNEL] > 0)
            UseMacros = true;
    }
    if (junk == false)
        return;
    UseMacros = false;
    for (uint8_t j = 0; j < BYTESPERMACRO; ++j)
    {
        for (uint8_t i = 0; i < MAXMACROS; ++i)
        {
            MacrosBuffer[i][j] = 0;
        }
    }
}

/*********************************************************************************************************************************/

void StartInactvityTimeout()
{
    Inactivity_Start = millis();
}

/*********************************************************************************************************************************/

uint8_t GetLEDBrightness()
{
    static uint8_t BlinkOnPhase = 1;
    static uint32_t BlinkTimer = 0;

    if (LEDBrightness < 15)
    {
        LEDBrightness = DEFAULTLEDBRIGHTNESS;
        SaveTransmitterParameters();
    }

    if (LedIsBlinking)
    {
        if ((millis() - BlinkTimer) > (1000 / BlinkHertz))
        {
            BlinkOnPhase ^= 1;
            BlinkTimer = millis();
        }
    }
    else
    {
        BlinkOnPhase = 1;
    }
    if (BlinkOnPhase)
    {
        return LEDBrightness; // 0 - 254 (= brightness)
    }
    else
    {
        return 0;
    }
}

/*********************************************************************************************************************************/
uint8_t IntoDegrees(uint16_t HiRes) // convert to lower resolution for screen display
{
    return (map(HiRes, MINMICROS, MAXMICROS, 0, 180));
}
/*********************************************************************************************************************************/
// B113 (Malcolm, 17 Oct 2026: "We need to control MAX RANGE, but this doesn't necessarily mean stick ends because the
// curve might not go to the top and bottom of the available range"): each model has a max range, 500 to 2500 or 945 to
// 2055 (MaxRangeNarrow, set on the Channels page). A curve's 0 .. 180 degrees span it - the curve page's bottom to top -
// so every curve, mix limit and curve-page number goes through CurveMicros, and every channel ends inside it (the trims'
// clamp, main.cpp DoTrimsAndSubtrims). IntoHigherRes stays 500 to 2500 for what is NOT a curve: the motor's safe value
// (MotorChannelZero) must never move with the range.
inline uint16_t RangeLo() { return MaxRangeNarrow ? RANGE_NARROW_LO : MINMICROS; }
inline uint16_t RangeHi() { return MaxRangeNarrow ? RANGE_NARROW_HI : MAXMICROS; }
inline uint16_t CurveMicros(uint8_t deg) { return map(deg, 0, 180, RangeLo(), RangeHi()); } // (500 to 2500: exactly IntoHigherRes)
// B118: a channel's curve points (1Definitions.h CurvePoint). How many (3, 5, 7 or 9; anything else reads as 5), the middle
// one's index, and the stick's calibrated reading at point k of n: the ends and the centre as calibrated, the quarters as
// calibrated too (so a 5-point curve reads exactly as it always did, and a 9-point one keeps the five of old), the eighths
// half way between, the thirds (7 points) shared out evenly.
uint8_t CurveN(uint8_t ch)
{
    const uint8_t n = CurvePointCount[ch];
    return (n == 3 || n == 7 || n == 9) ? n : 5;
}
uint8_t CurveMid(uint8_t n) { return (n - 1) / 2; }
uint16_t CurveX(uint8_t in, uint8_t k, uint8_t n)
{
    const uint8_t half = CurveMid(n);
    const int lo = ChannelMin[in], ql = ChannelMidLow[in], mid = ChannelCentre[in], qh = ChannelMidHi[in], hi = ChannelMax[in];
    if (k == 0)
        return lo;
    if (k == half)
        return mid;
    if (k >= n - 1)
        return hi;
    if (n == 5)
        return k == 1 ? ql : qh;
    if (n == 9)
    {
        switch (k)
        {
        case 1: return lo + (ql - lo) / 2;
        case 2: return ql;
        case 3: return ql + (mid - ql) / 2;
        case 5: return mid + (qh - mid) / 2;
        case 6: return qh;
        default: return qh + (hi - qh) / 2; // 7
        }
    }
    if (k < half)
        return lo + (mid - lo) * k / half;
    return mid + (hi - mid) * (k - half) / half;
}
// The five of old (Min, MidLow, Centre, MidHi, Max), as a sampling of the curve: what the file keeps for a firmware before
// B118, and what the fingerprint folds in first. For 5 and 9 points they ARE points; for 3 and 7 the quarters are half
// way between the points either side.
void CurveLegacyFive(uint8_t b, uint8_t ch, uint8_t *five)
{
    const uint8_t n = CurveN(ch);
    const uint8_t *p = CurvePoint[b][ch];
    five[0] = p[0];
    five[2] = p[CurveMid(n)];
    five[4] = p[n - 1];
    switch (n)
    {
    case 3: five[1] = (p[0] + p[1] + 1) / 2; five[3] = (p[1] + p[2] + 1) / 2; break;
    case 7: five[1] = (p[1] + p[2] + 1) / 2; five[3] = (p[4] + p[5] + 1) / 2; break;
    case 9: five[1] = p[2]; five[3] = p[6]; break;
    default: five[1] = p[1]; five[3] = p[3]; break;
    }
}
// B121: the store's place of point k of a curve of n points (1Definitions.h CurveStore)
uint8_t CurveStorePos(uint8_t n, uint8_t k)
{
    static const uint8_t Seven[7] = {0, 9, 10, 4, 11, 12, 8}; // the ends and the centre are eighths too; the sixths are the store's last four
    switch (n)
    {
    case 3: return k * 4;                  // 0, 4, 8
    case 7: return k < 7 ? Seven[k] : 0;
    case 9: return k;
    default: return k * 2;                 // 5: 0, 2, 4, 6, 8
    }
}
void CurveStoreSync(uint8_t b, uint8_t ch) // the active points into the store (after an edit, or a change of count)
{
    const uint8_t n = CurveN(ch);
    for (uint8_t k = 0; k < n; ++k)
        CurveStore[b][ch][CurveStorePos(n, k)] = CurvePoint[b][ch][k];
}
void CurveStoreClear(uint8_t b, uint8_t ch) // nothing remembered
{
    for (uint8_t s = 0; s < CURVE_STORE_MAX; ++s)
        CurveStore[b][ch][s] = CURVE_UNSET;
}
void CurveSetStraight(uint8_t b, uint8_t ch, uint8_t lo, uint8_t hi) // the points on the straight line lo .. hi (and nothing else remembered)
{
    const uint8_t n = CurveN(ch);
    for (uint8_t k = 0; k < CURVE_POINTS_MAX; ++k)
        CurvePoint[b][ch][k] = k < n ? lo + ((hi - lo) * k + (n - 1) / 2) / (n - 1) : 0;
    CurveStoreClear(b, ch);
    CurveStoreSync(b, ch);
}
uint8_t IntoLowerRes(uint16_t HiRes) // convert to lower resolution for screen display (B113: a bar spans this model's max range)
{
    return (uint8_t)constrain(map(HiRes, RangeLo(), RangeHi(), 0, 100), 0, 100);
}

/*********************************************************************************************************************************/
uint16_t IntoHigherRes(uint8_t LowRes) // This returns the main curve-points at the higher resolution for Servo output
{
    return map(LowRes, 0, 180, MINMICROS, MAXMICROS);
}
// B129 (Malcolm, 19 Oct 2026: "the value which is usually attributed to motor off of -67 is not in helpful units! ... change
// this to microseconds"). The byte stays what it was (0..180 over 500..2500, never moved by the model's range, so the model
// file keeps its shape); the Model options page shows and takes microseconds. -67 was 30: 833 microseconds.
uint16_t MotorOffMicros() { return IntoHigherRes(MotorChannelZero); }
uint8_t MotorOffFromMicros(int32_t us) { return (uint8_t)map(constrain(us, (int32_t)MINMICROS, (int32_t)MAXMICROS), MINMICROS, MAXMICROS, 0, 180); }
/*********************************************************************************************************************************/
void ClearText()
{
    for (int i = 0; i < MAXTEXTIN; ++i)
    {
        TextIn[i] = 0;
    }
    //   memset(TextIn, 0, sizeof(TextIn)); // Clear the text input buffer
}

/*********************************************************************************************************************************/

/** Send 13 joined together char arrays to NEXTION */
void SendCharArray(char *ch0, char *ch1, char *ch2, char *ch3, char *ch4, char *ch5, char *ch6, char *ch7, char *ch8, char *ch9, char *ch10, char *ch11, char *ch12)
{
    strcpy(ch0, ch1);
    strcat(ch0, ch2);
    strcat(ch0, ch3);
    strcat(ch0, ch4);
    strcat(ch0, ch5);
    strcat(ch0, ch6);
    strcat(ch0, ch7);
    strcat(ch0, ch8);
    strcat(ch0, ch9);
    strcat(ch0, ch10);
    strcat(ch0, ch11);
    strcat(ch0, ch12);
    SendCommand(ch0);
}

// /*********************************************************************************************************************************/
int GetNextNumber(int p1, char text1[CHARSMAX])
{
    int i = p1 - 1;
    int result = 0;

    while (i < CHARSMAX && isdigit(text1[i]))
    {
        result = result * 10 + (text1[i] - '0');
        ++i;
    }

    return result;
}
/*********************************************************************************************************************************/

void ClearSuccessRate()
{
    for (int i = 0; i < (PACKET_HISTORY_WINDOW * (uint16_t)ConnectionAssessSeconds); ++i)
    { // 126 packets per second start off good
        if (i < PACKET_HISTORY_WINDOW)
            PacketsHistoryBuffer[i] = 1;
    }
}

/*********************************************************************************************************************************/

FASTRUN void DrawDot(int xx, int yy, int rad, int colr)
{
    char cirs[] = "cirs ";
    char nb[12];
    char cb[60];
    char comma[] = ",";
    strcpy(cb, cirs);
    strcat(cb, Str(nb, xx, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, yy, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, rad, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, colr, 0));
    SendCommand(cb);
}

/*********************************************************************************************************************************/

/**
 * @param x1
 * @param y1
 * @param x2
 * @param y2
 * @param color
 */
FASTRUN void DrawBox(int x1, int y1, int x2, int y2, int c)
{
    char line[] = "draw ";
    char nb[12];
    char cb[60];
    char comma[] = ",";
    strcpy(cb, line);
    strcat(cb, Str(nb, x1, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, y1, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, x2, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, y2, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, c, 0));
    SendCommand(cb);
}

/*********************************************************************************************************************************/
/**
 * @param x1
 * @param y1
 * @param x2
 * @param y2
 * @param color
 */
void FillBox(int x1, int y1, int w, int h, int c)
{
    char line[] = "fill ";
    char nb[12];
    char cb[60];
    char comma[] = ",";
    strcpy(cb, line);
    strcat(cb, Str(nb, x1, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, y1, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, w, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, h, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, c, 0));
    SendCommand(cb);
}

/*********************************************************************************************************************************/

/**
 * @param x1
 * @param y1
 * @param x2
 * @param y2
 * @param color
 */
void DrawLine(int x1, int y1, int x2, int y2, int c)
{
    char line[] = "line ";
    char nb[12];
    char cb[60];
    char comma[] = ",";
    strcpy(cb, line);
    strcat(cb, Str(nb, x1, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, y1, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, x2, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, y2, 0));
    strcat(cb, comma);
    strcat(cb, Str(nb, c, 0));
    SendCommand(cb);
}


/*********************************************************************************************************************************/
// (B135: ClearBox, which set the curve page's picture again before every redraw - the flash of the background in the box -
// is gone; DisplayCurve clears the box itself.)
void DelaySimple(uint32_t ms)
{
    uint32_t ThisMoment = millis();
    while (millis() - ThisMoment < ms)
    {
        KickTheDog(); // keep the dog happy and its tail wagging so it doesn't bite us!
        delay(10);    // this is needed to allow the dog to wag its tail!
    }
}

/*********************************************************************************************************************************/
uint16_t GetSuccessRate()
{
#ifdef ELRS_TEST // ELRS, TEST BUILDS ONLY: a model set to ELRS shows the module's own figure (ElrsCrsf.h)
    if (ElrsCarries())
        return ElrsQuality();
#endif
    uint32_t Total = 0; // Accumulates number of successful packets
    uint16_t SuccessRate;
    for (uint16_t i = 0; i < PACKET_HISTORY_WINDOW; ++i)
        Total += PacketsHistoryBuffer[i]; // Sum successes from ring buffer

    SuccessRate = (Total * 100) / PACKET_HISTORY_WINDOW; // Percentage of successful packets
    return SuccessRate;
}
/*********************************************************************************************************************************/
//                  My new version of the the traditional "map()" function -- but here with exponential added.
/*********************************************************************************************************************************/

FASTRUN float MapWithExponential(float xx, float Xxmin, float Xxmax, float Yymin, float Yymax, float Expo)
{
    Expo = map(Expo, -100, 100, -0.25, 0.75);
    if (Xxmax == Xxmin)
        return Yymin; // B124: an input whose centre IS its calibrated end (never swept): nothing to divide by
    xx = pow(xx * xx, Expo);
    Xxmin = pow(Xxmin * Xxmin, Expo);
    Xxmax = pow(Xxmax * Xxmax, Expo);
    return map(xx, Xxmin, Xxmax, Yymin, Yymax);
}

// ******************************************************************************************************************************
bool AnyMatches(uint8_t a, uint8_t b, uint8_t c)
{
    if (a == b)
        return true;
    if (a == c)
        return true;
    if (b == c)
        return true;
    return false;
}

/******************************************** CHANNEL REVERSE FUNCTION **********************************************************/

FASTRUN void ServoReverse()
{
    for (uint8_t i = 0; i < 16; i++)
    {
        if (ReversedChannelBITS & 1 << i)
        {                                                                                     // Is this channel reversed?
            PreMixBuffer[i] = map(SendBuffer[i], MINMICROS, MAXMICROS, MAXMICROS, MINMICROS); // Yes so reverse the channel
            SendBuffer[i] = PreMixBuffer[i];
        }
    }
}

/************************************************************************************************************/
bool InsideDelayWithDog = false; // (B211: was a static in the routine. Nextion.h BeforePageCommand looks at it: a page command sent from in here was sent from
                                 //  INSIDE a wait of some button's work - the power button's way to the front page, a box put up when the link is lost)
void DelayWithDog(uint32_t HowLong)
{ // Implements delay() while kicking the dog (very cruelly) and checking for power-off button and sending data to RX.
    CRUMB(CRUMB_DELAY);
    uint32_t ThisMoment = millis();
    if (InsideDelayWithDog)
        return; // Guard against possible recursivity which would be disastrous
    InsideDelayWithDog = true;
    while ((millis() - ThisMoment) < HowLong)
    {
        KickTheDog();
        CheckPowerOffButton();
#ifdef ELRS_TEST // ELRS, TEST BUILDS ONLY: a model set to ELRS is sent its sticks through every wait, heard or not (ElrsCrsf.h: nothing sent depends on what is heard)
        if (((ModelMatched && BoundFlag) || ElrsFlies()) && !ModelMemoryBusy)
#else
        if (ModelMatched && BoundFlag && !ModelMemoryBusy) // (B211: not from a memory that is being read into - 1Definitions.h, at ModelMemoryBusy)
#endif
        {
            GetNewChannelValues(); // these might have changed while we were waiting
            FixMotorChannel();     // ensure motor channel is off if that's needed
            SendData();            // send new data to RX
        }
    }
    InsideDelayWithDog = false;
}

// ********************************************************************************************************************
void SpeedTest()
{

    // calculate how many prime numbers are there between 1 and 100000
    // and also how long it takes to calculate them
    Look("Calculating prime numbers between 1 and 100000 ...");
    int count = 0;
    unsigned long start = millis();
    for (int i = 1; i < 100000; i++)
    {
        KickTheDog();
        bool isPrime = true;
        for (int j = 2; j <= i / 2; j++)
        {
            if (i % j == 0)
            {
                isPrime = false;
                break;
            }
        }
        if (isPrime)
        {
            count++;
        }
    }
    unsigned long end = millis();
    Look1("There are ");
    Look1(count);
    Look(" prime numbers between 1 and 100000");
    Look1("Time taken to calculate them is ");
    Look1(end - start);
    Look(" milliseconds");
    DelayWithDog(1000);
}

/******************************************************************************************************************************/
// Gets Windows style confirmation (FILE OVERWRITE ETC.)
// params:
// Prompt is the prompt
// goback is the command needed to return to calling page

// B211 (the tenth review, 15 Nov 2026): THE COUNT OF THE PAGE COMMAND THAT PUTS A QUESTION UP, taken before that command goes. The question
// took "the last page command sent" for its own when its wait BEGAN - behind the box's page command and that command's own 20 ms wait,
// which flies the model: the power button's front page (or the motor box) put up in THAT wait was taken for the question's page, and
// the question waited on, unseen, with the switches unread, until some press came.
// (the tenth review) THE COUNTS BEGIN WHERE THE CLOCK STANDS, not at 1 with every start of this board - a page's markers, the session's
// number, the number said back when an answer is owed. A screen that still owed an answer to this board's LAST life (this board started
// again while the screen stood still) could say the very number the new life's first page command waits for.
static uint16_t ScreenCountSeed()
{
    static uint16_t seed = 0;
    if (!seed)
    {
        const uint32_t us = micros();
        seed = (uint16_t)(us ^ (us >> 16));
        if (!seed)
            seed = 1;
    }
    return seed;
}
static uint16_t ScreenCountAfter(uint16_t c) // the count that follows c (0: none yet - the first, from the clock); never 0
{
    if (!c)
        return ScreenCountSeed();
    ++c;
    return c ? c : 1;
}
static uint16_t NextPageMark()
{
    return ScreenCountAfter(ScreenMarkCount); // (as Nextion.h BeforePageCommand counts)
}
// ... AND A QUESTION'S OWN TEXTS GO ONTO ITS OWN PAGE ONLY (15 Nov 2026, the author's, after the tenth review). The page that came over a question
// in that first wait - the front page - has parts of the same names as the question's page (b0, b1, t0, t1, t3): "vis b1,0" hid one of the
// front page's buttons, "Save" and "Discard" were written onto two others, the backup's file name into its text boxes - until that page was
// next drawn. Each of a question's writes is made only while the question's page command is still the last one sent.
static bool QuestionIsUp(uint16_t mine)
{
    return ScreenMarkCount == mine;
}
FLASHMEM bool GetConfirmation(char *goback, char *Prompt) // (B211: the questions wait for a person - in flash, the fast memory's last kilobytes are not for them)
{
    char GoPopupView[] = "page PopupView";
    char Dialog[] = "Dialog";
    const uint16_t mine = NextPageMark();
    SendCommand(GoPopupView);
    if (QuestionIsUp(mine))
        SendText(Dialog, Prompt);
    GetYesOrNo(mine);
    const bool yes = Confirmed[0] == 'Y', over = QuestionOvertaken, closed = QuestionClosedItself;
                                                                    // B211 (the ninth review): THE ANSWER IS TAKEN HERE, before the way back - which waits
                                                                    // (flying the model), and a box put up in that wait (the link lost with the motor
                                                                    // switch on) wrote ITS answer over this one: "No" came back as Yes
    if (!over)
        SendCommand(goback); // (not over a page that took this question's place: that page is the one this board now believes in)
    QuestionOvertaken = over; // (the tenth review: ... and how THIS question ended is what its asker is told - a box in the way back's wait had said its own)
    QuestionClosedItself = closed;
    LastFileInView = 120;
    if (yes)
        return true; // tell caller OK to continue
    RfLeaveAfterSave = false; // B102: a No to a save's own question keeps the page open
    return false;    // tell caller STOP!
}

/******************************************************************************************************************************/
// B102 (Malcolm, 15 Oct: "If a user forgets to hit save and instead hits OK, I think the message box, which already
// recognises unsaved edits, should offer the option save now? To save clicks."): OK with unsaved edits asks "Save them
// now?" on the message box's two buttons, Save (right) and Discard (left). Save saves, and the page closes once the save
// has worked (RfSavedThenLeave, from each page's save); Discard leaves without saving, as before. A refusal or a failure
// (any message box), or a No to the save's own question, keeps the page open with the edits.
FLASHMEM bool GetSaveOrDiscard(char *goback, char *Prompt) // true: Save
{
    char GoPopupView[] = "page PopupView";
    char Dialog[] = "Dialog";
    const uint16_t mine = NextPageMark();
    SendCommand(GoPopupView);
    if (QuestionIsUp(mine))
        SendText((char *)"b0", (char *)"Save");
    if (QuestionIsUp(mine))
        SendText((char *)"b1", (char *)"Discard");
    if (QuestionIsUp(mine))
        SendText(Dialog, Prompt);
    GetYesOrNo(mine);
    const bool yes = Confirmed[0] == 'Y', over = QuestionOvertaken, closed = QuestionClosedItself; // B211: (as GetConfirmation: the answer first, then the way back)
    if (!over)
        SendCommand(goback);
    QuestionOvertaken = over; // (the tenth review: this question's own - RfSaveFirst asks "did it close itself?" behind the way back, in whose wait a box had said "no" of itself: Discard)
    QuestionClosedItself = closed;
    LastFileInView = 120;
    return yes;
}
#include "RF_SaveNow.h" // B102: RfSavedThenLeave, RfSaveFirst (a file of their own, so the host tests run the real ones)

/******************************************************************************************************************************/
// Windows style MSGBOX
// params:
// Prompt is the prompt
// goback is the command needed to return to calling page

FLASHMEM void MsgBox(char *goback, char *Prompt)
{
    RfLeaveAfterSave = false; // B102: a refusal or a failure keeps the page open (OK's "Save now?")
    char GoPopupView[] = "page PopupView";
    char Dialog[] = "Dialog";
    char NoCancel[] = "vis b1,0"; // hide cancel button
    const uint16_t mine = NextPageMark();
    SendCommand(GoPopupView);
    if (QuestionIsUp(mine))
        SendCommand(NoCancel);
    if (QuestionIsUp(mine))
        SendText(Dialog, Prompt);
    GetYesOrNo(mine);
    const bool over = QuestionOvertaken, closed = QuestionClosedItself;
    if (!over) // B211: (as GetConfirmation: no way back over a page that took this box's place)
        SendCommand(goback);
    QuestionOvertaken = over; // (this box's own, as GetConfirmation's)
    QuestionClosedItself = closed;
    LastFileInView = 120;
    return;
}

/******************************************************************************************************************************/
void YesPressed() { Confirmed[0] = 'Y'; }
/******************************************************************************************************************************/
void NoPressed() { Confirmed[0] = 'N'; }
/******************************************************************************************************************************/

/******************************************************************************************************************************/

uint8_t ModalWaits = 0; // V1B: how many questions are waiting for an answer (the file link is refused meanwhile)
#define QUESTION_ASK_MS 1000    // B211: while a question waits, the screen is asked which page it shows so often ...
#define QUESTION_SILENT_MS 3500 // ... and a screen that has left such a question unanswered for so long is not waited for any longer
bool QuestionClosedItself = false; // B211: the last question was closed as "No" by this board, not answered by the pilot (the screen restarted, stopped answering, another page over it)
bool QuestionOvertaken = false;    // ... because another page was put up over it: whoever asked does not send its own way back over that page
FLASHMEM void GetYesOrNo(uint16_t asked) // asked: the count of the page command that put THIS question up (NextPageMark, taken before it went; 0: the last one sent)
{ // on return from here, Confirmed[0] will be Y or N
    if (!asked)
        asked = ScreenMarkCount;
    uint32_t askedAt = millis(), unanswered = 0; // (unanswered: when the oldest "which page?" still without an answer went out; 0: none)
    uint16_t said = ScreenPageSaidCount;
    bool closed = false, overtaken = false;
    Confirmed[0] = '?';
    if (ScreenMarkCount != asked)
        Confirmed[0] = 'N'; // B211 (the tenth review): another page was put up between this question's own page command and here (from inside that command's
                            // wait): the question is not on the screen - it is closed below, without one look for a press
    ++ModalWaits;
    CRUMB(CRUMB_QUESTION);
    while (Confirmed[0] == '?')
    { // await user response
        KickTheDog(); // (B211, the eighth review: FIRST. It came last, and the round that closed the question at once never reached it - see EnsureMotorIsOff)
        CheckForNextionButtonPress();
        if (ScreenAnswerOwed)
            ScreenOwedStep(); // (the ninth review: an answer owed - this question's own page marker, come late - is caught up with from in here too, as the
                              //  main loop does it: left owed, every box of the work that follows a "Yes" had no answer. It never waits.)
        if (ScreenPageSaidCount != said)
        {
            said = ScreenPageSaidCount;
            unanswered = 0;
        }
        if ((millis() - askedAt) >= QUESTION_ASK_MS)
        {
            askedAt = millis();
            ScreenAskPage(); // (nothing waits for the answer: it is noted when the look for a press reads it)
            if (!unanswered)
                unanswered = askedAt ? askedAt : 1;
        }
        // (the ninth review: the silence is counted from a "which page?" the screen was really asked and has not answered - it was
        //  counted from the question's own beginning, a second before the first was asked: a screen still for 2.6 s lost the question)
        const bool silent = ScreenSaysPage && unanswered && (millis() - unanswered) > QUESTION_SILENT_MS;
        if (ScreenRestartSeen || ScreenMarkCount != asked || silent)
        { // B211: THE QUESTION IS NO LONGER ON THE SCREEN - or nobody can answer it - so it is closed as "No".
          // - The screen has STARTED AGAIN while it waited (Nextion.h): it shows its last page as the card has it, and the main
          //   loop draws the front page afresh. (It waited on: a tap on whatever the screen then showed was obeyed in here.)
          // - Or ANOTHER PAGE WAS PUT UP OVER IT from inside this wait (the eighth review, 15 Nov 2026; released code had it):
          //   the link lost with the motor switch on puts up "The motor switch is ON" from in here, and the OK pressed on
          //   THAT box was taken for the answer to this question - "Delete every model and all settings?": Yes, by itself.
          // - Or THE SCREEN HAS STOPPED ANSWERING (the eighth review): it is asked "which page?" once a second while a question
          //   waits, and has said nothing for three and a half. In here the model is flown but THE SWITCHES ARE NOT READ: a
          //   screen that died under a box held them until its first word came back - 1.2 to 18 seconds on, or never.
            Confirmed[0] = 'N';
            closed = true;
            overtaken = ScreenMarkCount != asked;
            NoteQuestionClosed(ScreenRestartSeen ? 1 : silent ? 2 : 0);
            if (silent && !ScreenRestartSeen)
                ScreenOwesAnswer(); // (what it was asked may come yet: nothing more is asked until it has caught up)
            break;
        }
        CheckPowerOffButton();
#ifdef ELRS_TEST // ELRS, TEST BUILDS ONLY: a model set to ELRS is sent its sticks through every box on the screen, heard or not (as in DelayWithDog; ElrsCrsf.h)
        if ((BoundFlag && ModelMatched) || ElrsFlies())
#else
        if (BoundFlag && ModelMatched)
#endif
        {
            GetNewChannelValues();
            FixMotorChannel();
            SendData();
        }
    }
    --ModalWaits;
    if (ScreenMarkCount != asked)
    { // B211: ... and an answer given while another page stood over this question (a box from inside its wait: that box's own
      // answer is what is in Confirmed now) was not given to THIS question
        if (!closed)
            NoteQuestionClosed(0);
        Confirmed[0] = 'N';
        closed = true;
        overtaken = true;
    }
    QuestionClosedItself = closed; // (set here, at the very end: a box inside this question has set them for itself meanwhile)
    QuestionOvertaken = overtaken;
}
/******************************************************************************************************************************/
FLASHMEM bool GetBackupFilename(char *goback, char *tt1, char *MMname, char *heading, char *pprompt)
{ // HERE THE USER CAN REPLACE DEFAULT FILENAME IF HE WANTS TO

    char GoBackupView[] = "page BackupView";
    char t0[] = "t0";           // prompt
    char t1[] = "t1";           // default filename
    char t3[] = "t3";           // heading
    char Mname[] = "Modelname"; // model name
    const uint16_t mine = NextPageMark();
    SendCommand(GoBackupView);
    if (QuestionIsUp(mine))
        SendText(t0, pprompt);   // prompt
    if (QuestionIsUp(mine))
        SendText(t1, tt1);       // filename
    if (QuestionIsUp(mine))
        SendText(Mname, MMname); // Model name
    if (QuestionIsUp(mine))
        SendText(t3, heading);   // heading
    GetYesOrNo(mine);
    const bool yes = Confirmed[0] == 'Y', over = QuestionOvertaken, closed = QuestionClosedItself; // B211: (as GetConfirmation: the answer first, then the way back)
    const uint32_t lost = BoxesLost;
    if (!over)
        GetText(t1, SingleModelFile, 40); // ClaudeFix-2-7-2026 (B211: not from a page that came over this one - its t1 is another box)
    const bool gone = !over && !QuestionIsUp(mine); // B211 (the eleventh review): another page was put up from inside THAT wait (the front page: the power button,
                                                    // the link) - this question's way back would put its caller's page over it. (The name has no answer then.)
    if (!over && !gone)
        SendCommand(goback);
    QuestionOvertaken = over || gone; // (this question's own, as GetConfirmation's)
    QuestionClosedItself = closed;
    if (yes && BoxesLost == lost) // (B211: ... and the name was read: no answer from the screen is not a file's name)
        return true;
    return false;
}

// ************************************************************************
// This function looks at the TextIn for an int and returns it as an integer
int GetIntFromTextIn(uint8_t offset)
{
    union
    {
        uint8_t F4Bytes[4];
        int FDWord;
    } NextionCommand;

    for (uint8_t i = 0; i < 4; i++)
        NextionCommand.F4Bytes[i] = TextIn[i + offset];
    return NextionCommand.FDWord;
}
// ************************************************************************************************************/
void ShowMismatchMsg()
{
    if (CurrentView != FRONTVIEW)
        GotoFrontView(); // if needed

    char prompt[200];
    char TDetails[40];
    char RDetails[40];
    strcpy(RDetails, (char *)"Versions mismatch!\r\n\r\nRX:");
    strcat(RDetails, ReceiverVersionNumber);
    strcpy(TDetails, (char *)"TX:");
    strcat(TDetails, TransmitterVersionNumber);
    strcpy(prompt, RDetails);
    strcat(prompt, (char *)"\r\n");
    strcat(prompt, TDetails);
    MsgBox((char *)"page FrontView", prompt);
}

/************************************************************************************************************/

void WarnUserOfVersionsMismatch()
{ // (10 Nov 2026, the code review) this runs inside the ack parser (transceiver.h): no box here - the once-a-second housekeeping
  // (main.cpp) shows it ONCE (it showed it here and then again every second, for ever, and a box that waits does not read the
  // switches), and not at all while the model may fly: then the sound and a line in the log are all.
    VersionMismatch = true;
    PlaySound(WHAHWHAHMSG); // Play warning sound
}

/************************************************************************************************************/

void CompareVersionNumbers()
{ // Warn  user if TX and RX versions don't match - but ignore final letter

    if (VersionsCompared)
        return;
    if ((strlen(ReceiverVersionNumber) > 11) || (ReceiverVersionNumber[1] != '.'))
        return; // Too long etc for a version number. Probably binding data !
    VersionsCompared = true;
    for (int i = 0; i < 5; ++i)
    {
        if (ReceiverVersionNumber[i] != TransmitterVersionNumber[i])
        { // Compare the two version numbers, but not the letter
            WarnUserOfVersionsMismatch();
            return;
        }
    }
}
/************************************************************************************************************/
void swap(uint8_t *a, uint8_t *b)
{ // Just swap over two bytes, a & b :-)
    uint8_t c;
    c = *a;
    *a = *b;
    *b = c;
}
// ************************************************************************************************************/
void ChooseBackGround()
{
    SendCommand(pColoursView); // go to colours page
    CurrentView = COLOURS_VIEW;
}
// ************************************************************************************************************/
void Save_BackGround()
{
    {
        const uint32_t gv = GetValue((char *)"n0");
        if (gv != 65535) // B211: no answer from the screen is not a background (it was saved as picture 255)
            BackGroundSelection = gv;
    }
    SaveTransmitterParameters();
    StartTXSetupView();
}
// ************************************************************************************************************/
/// BUILD_ID_STR should be: __DATE__ " " __TIME__   e.g. "Feb 14 2026 13:31:06"

static int monthFrom3(const char mmm[4])
{
    // mmm is "Jan".."Dec"
    if (mmm[0] == 'J' && mmm[1] == 'a' && mmm[2] == 'n')
        return 1;
    if (mmm[0] == 'F' && mmm[1] == 'e' && mmm[2] == 'b')
        return 2;
    if (mmm[0] == 'M' && mmm[1] == 'a' && mmm[2] == 'r')
        return 3;
    if (mmm[0] == 'A' && mmm[1] == 'p' && mmm[2] == 'r')
        return 4;
    if (mmm[0] == 'M' && mmm[1] == 'a' && mmm[2] == 'y')
        return 5;
    if (mmm[0] == 'J' && mmm[1] == 'u' && mmm[2] == 'n')
        return 6;
    if (mmm[0] == 'J' && mmm[1] == 'u' && mmm[2] == 'l')
        return 7;
    if (mmm[0] == 'A' && mmm[1] == 'u' && mmm[2] == 'g')
        return 8;
    if (mmm[0] == 'S' && mmm[1] == 'e' && mmm[2] == 'p')
        return 9;
    if (mmm[0] == 'O' && mmm[1] == 'c' && mmm[2] == 't')
        return 10;
    if (mmm[0] == 'N' && mmm[1] == 'o' && mmm[2] == 'v')
        return 11;
    if (mmm[0] == 'D' && mmm[1] == 'e' && mmm[2] == 'c')
        return 12;
    return 0;
}

// Howard Hinnant's days-from-civil (public domain style; widely used)
static int32_t daysFromCivil(int32_t y, uint32_t m, uint32_t d)
{
    y -= (m <= 2);
    const int32_t era = (y >= 0 ? y : y - 399) / 400;
    const uint32_t yoe = (uint32_t)(y - era * 400);                        // [0, 399]
    const uint32_t doy = (153 * (m + (m > 2 ? -3u : 9u)) + 2) / 5 + d - 1; // [0, 365]
    const uint32_t doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;            // [0, 146096]
    return era * 146097 + (int32_t)doe;                                    // days relative to an arbitrary origin
}

uint32_t GetBuildDaysSince2020()
{
    const char *s = BUILD_ID_STR;

    // Parse: "Feb 14 2026 13:31:06"
    char mmm[4] = {0};
    int dd = 0, yyyy = 0;

    // This ignores the time part safely.
    if (sscanf(s, "%3s %d %d", mmm, &dd, &yyyy) != 3)
        return 0;

    const int mm = monthFrom3(mmm);
    if (mm < 1 || mm > 12 || dd < 1 || dd > 31 || yyyy < 1970)
        return 0;

    const int32_t base = daysFromCivil(2020, 1, 1);
    const int32_t cur = daysFromCivil(yyyy, (uint32_t)mm, (uint32_t)dd);

    // cur >= base for your builds; clamp just in case.
    return (cur >= base) ? (uint32_t)(cur - base) : 0u;
}
// ************************************************************************************************************/
void Enable_Binding()
{
    if (!BindingEnabled)
    {
        BindingEnabled = true;
        LedIsBlinking = true;
        PlaySound(BINDINGENABLED);
        SendText((char *)"OptionsView.b0", (char *)"Stop binding");
    }
    else
    {
        BindingEnabled = false;
        LedIsBlinking = false;
        PlaySound(BEEPCOMPLETE);
        SendText((char *)"OptionsView.b0", (char *)"Bind");
        if (LedWasRed)
        {
            RedLedOn();
        }
        if (LedWasGreen)
        {
            GreenLedOn();
        }
    }
}
#endif