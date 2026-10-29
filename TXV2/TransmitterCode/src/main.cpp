/** @file TransmitterCode/src/main.cpp
 * // Malcolm Messiter 2020 - 2026
 * @brief This is the main file for the transmitter code.
 *
 * @page TransmitterCode....
 * @section LockDown Radio Control Features list, so far:
 * - Uses Teensy 4.1 MCU (at 600 Mhz) with nRF24L01+ transceiver
 * - (Ebyte's ML01DP5 recommended for TX, two ML01SP4s for RX.)
 * - 16 channels
 * - 12 BIT servo resolution (11 BIT via SBUS)
 * - 32 Mixes
 * - 4 Flight modes with user definable and announced names.
 * - 90 Model memories.
 * - Unlimited model files for backup (32 Gig)
 * - "ModelMatch" plus automatic model memory selection. (Avoid flying with wrong memory loaded.)
 * - "ModelExchange" - share model memories wirelessly.
 * - Wireless or wired Buddyboxing with selectable channels.
 * - Voice messages and other audio prompts.
 * - User defined Channel names
 * - 2.4 Ghz FHSS ISM band licence free in UK and most other countries.
 * - > 2 Km range
 * - Telemetry including GPS, volts, temperature & barometric pressure.
 * - 64 editable 5-point curves (16 channels x 4 flight modes): straight, smoothed or exponential.
 * - FailSafe on any or all channel(s)
 * - 2.4 GHz RF scan
 * - Motor Timer
 * - Lossless data compression.
 * - Trims saved per bank and per model.
 * - Screen timeout to save battery.
 * - FHSS with very fast connect and reconnect
 * - Uses 32 GIG SD card for model memories and help files
 * - Binding - uses unique Mac address as pipe address.
 * - Four User definable three position switches
 * - Channels 5,6,7 & 8 can be switches or knobs.
 * - Input sources definable - any stick, switch or knob can be mapped to any function.
 * - Output channels definable - any channel can be mapped to any output channels
 * - Model memories export and import to backup files on SD card
 * - Model memory files alphabetically sorted
 * - Timer goes on and off with motor to keep track of motor use.
 * - DS1307 Real time clock auto synched to exact GPS time.
 * - Model memory sharing between transmitters - wirelessly.
 * - Sub-trim
 * - Servo reverse
 * - Macros - for snap rolls, heli rescue, etc.
 * - Hardware digital trims with accellerating repeat
 * - Capacitive touch screen GUI
 * - Hardware bug in nRF24L01+ worked-around: FIFO buffers crash the chip when they're full for > 4ms. So these are flushed often.
 * - Screen colours definable
 * - Data screen gives almost all possible telemetry
 * - Log files  (on SD 32 gig card)
 * - Help files display system from plain text files.
 * - Safety switch implemtented (Stops accidental motor starting)
 * - Rates (three rates) implemented
 * - Slow Servos implemented: Any channel can be slowed by almost any amount for realistic flaps, U/C etc,
 * - Support for external third party transmitter modules added (JR type).
 * - Variometer implemented (using a BMP280 or better still, a DPS310)
 * - Support for RotorFlight PID and RATES etc. parameters added via MSP protocol
 *
 *
 * | Teensy 4.1 Pins | Connections |
 * |-----------------|-------------|
 * | GND        | GND |
 * | Vin        | +5V power in  |
 * | 0  (RX1)   | NEXTION  (TX) | // RX1
 * | 1  (TX2)   | NEXTION  (RX) | // TX1
 * | 2  LED     | RED |
 * | 3  LED     | GREEN |
 * | 4  LED     | BLUE |
 * | 5  (POLOLU)| 2808 ALL POWER OFF SIGNAL (When high)|
 **| 6  SPARE   | <<<< *SPARE* (was PPM TX MODULE <<<<<<<<<<<<<<<
 * | 7  (CE)    | nRF24l01 (CE)   // RX2
 * | 8  (CSN)   | nRF24l01 (CSN)  // TX2
 **| 9  SPARE   | <<<< *SPARE* !
 **| 10 SPARE   | <<<< *SPARE* ! (WAS : Wired Buddy PPM IN or OUT (Could become a SPARE if PPM Buddy is not used)
 * | 11 (MOSI)  | nRF24l01 (MOSI) |
 * | 12 (MISO)  | nRF24l01 (MISO) |
 * | 13 (SCK)   | nRF24l01 (SCK) |
 * | 14 (A0)    | Joystick POT CH1 |
 * | 15 (A1)    | Joystick POT CH2 |
 * | 16 (A2)    | Joystick POT CH3 |
 * | 17 (A3)    | Joystick POT CH4 |
 * | 18 (I2C)   | I2C bus  SDA |
 * | 19 (I2C)   | I2C bus  SCL |
 * | 20 (A6)    | POT KNOB CH5 |// TX5
 * | 21 (A7)    | POT KNOB CH6 |// RX5
 * | 22 (A8)    | POT KNOB CH7 |
 * | 23 (A9)    | POT KNOB CH8 |
 **| 24 (A10)   | Spare  ADC!
 * | 26 (A12)   | Switch 1 |
 * | 27 (A13)   | Switch 2 |
 * | 28         | Switch 2 |    // RX7
 * | 29         | Switch 3 |    // TX7
 * | 30         | Switch 3 |
 * | 31         | Switch 4 |
 * | 32         | Switch 4 |
 * | 33         | Sensor for power button press while on
 * | 34         |TRIM (CH1a)|   // RX8  ********  Usable as serial while hardware trims are not used  (Best option)
 * | 35         |TRIM (CH1b)|   // TX8  ********  Usable as serial while hardware trims are not used  (Best option)
 * | 36         |TRIM (CH2a)|
 * | 37         |TRIM (CH2b)|
 * | 38 (A14)   |TRIM (CH3a)|
 * | 39 (A15)   |TRIM (CH3b)|
 * | 40 (A16)   |TRIM (CH4a)|
 * | 41 (A17)   |TRIM (CH4b)|
 * | 42         Built-in SD card
 * | 43         Built-in SD card
 * | 44         Built-in SD card
 * | 45         Built-in SD card
 * | 46         Built-in SD card
 * | 47         Built-in SD card
 * |  Solder pads on the back:
 * | 48<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< (SPARE)
 * | 49<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< (SPARE)
 * | 50<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< (SPARE)
 * | 51<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< (SPARE)
 * | 52<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< (SPARE)
 * | 53<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< (SPARE)
 * | 54<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< (SPARE)
 *
 *
 *  (11 spare GPIO PINS: 6,9,10,24,49,50,51,52,53,54 )
 *
 */
// ************************************************** TRANSMITTER CODE **************************************************

#include <Arduino.h>
#include <Watchdog_t4.h>
#include <PulsePosition.h>
#include <RF24.h>
#include <SPI.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <DS1307RTC.h>
#include <InterpolationLib.h>

#include "1Definitions.h" // must be here! (not higher or lower);

#include "Utilities.h"
#include "transceiver.h"
#include "ZPong.h"
#include "macros.h"
#include "Trims.h"
#include "ModelMatch.h"
#include "Nextion.h"
#include "ModelExchange.h"
#include "BuddyWireless.h"
#include "SDcard.h"
#include "Telemetry.h"
#include "LogFiles.h"
#include "DualRates.h"
#include "Mixes.h"
#include "MenuOptions.h"
#include "LogFilesList.h"
#include "Help.h"
#include "LogFilesDisplay.h"
#include "Switches.h"
#include "ADC-master/ADC.h"
#include "Parameters.h"
#include "PipeHttp.h" // B50: the main board's own requests to the receiver over the screen's Bluetooth pipe
#include "RF_PIDs.h"
#include "RF_Rates.h"
#include "RF_RotorFlight.h"
#include "RF_Rescue.h" // B50: Rotorflight rescue, over the pipe
#include "RF_Servos.h" // B55: Rotorflight servos, over the pipe
#include "RF_Travel.h" // B57: travel extents, over the pipe
#include "RF_Filters.h" // B58: the gyro filters, over the pipe
#include "RF_Adjust.h" // B72: the in-flight adjustments, over the pipe with the USB cable
#include "RF_Switches.h" // B77: the switches (modes), over the pipe
#include "RF_Jobs.h" // B140: Switches and knobs - the one page over both
#include "RF_CopyBank.h" // B78: copy a bank, over the pipe
#include "RF_FcSetup.h" // B88: battery, black box, calibrate, and why it will not arm, over the pipe
#include "RF_Basics.h" // B99: the model basics (swashplate type, rotor direction, tail type, motor protocol, ESC brand, poles, gear ratios), over the pipe; B100: the ports
#include "RF_EscCal.h" // B100: the ESC throttle calibration, over the pipe
#include "RF_Rates_Advanced.h"
#include "RF_PID_Advanced.h"
#include "RF_Save_Restore.h"
#include "RF_Backup.h" // B70: backup and restore of everything over the pipe, and the file as the FC's stand-in offline
#include "BankSync.h"  // B143: the bank count told to the receiver over the pipe (after RF_Backup.h: its page-of-view for the warning)
#include "SDFiles.h"
#include "ChooseImage.h"
#include "Calibrate.h"
#include "RF_Governor_Profile.h"
#include "RF_Governor_Global.h"
#include "RF_Verify.h" // B153: a save read back from the flight controller (after the pages: their arrays and box names)
#include "RF_Easy.h" // B104: Easy tuning, the phone app's sliders, over the pipe (after RF_Backup.h: the backup is the sliders' centre)
#include "Model_IDs.h"
#include "Motor_sign.h"
#include "FlightGuard.h" // V1B: the screen is told what the transmitter is doing; a fingerprint of how the settings are read
#include "Perf.h"        // V1B B15: where the time goes while flying
#include "LinkMode.h" // V1B: the screen's file link and firmware updates
#include "RxUpdate.h" // V1B: a receiver update through the transmitter

/*********************************************************************************************************************************/

/*********************************************************************************************************************************/

void ClearMostParameters()
{ // called from RED LED ON
    RXVoltsDetected = false;
    LedGreenMoment = 0;
    ModelsMacUnion.Val64 = 0;
    MacHalfSeen[0] = MacHalfSeen[1] = 0; MacHalfStable = 0;   // B73: the ID's halves are collected afresh
    LedWasGreen = false;
    ModelIdentified = false;
    ModelMatched = false;
    BoundFlag = false;
    LastShowTime = 0;
    TotalGoodPackets = 0;
    RecentGoodPacketsCount = 0;
    DontChangePipeAddress = false;
    UsingDefaultPipeAddress = true;
    VersionsCompared = false;
    LogLineNumber = 0;
    RXSuccessfulPackets = 0;
    TotalLostPackets += RecentPacketsLost;   // B155: the packets that failed in the two seconds before the model was given up are LOST packets: banked, not wiped
    RecentPacketsLost = 0;                   // (and nothing is counted while the model is gone: FailedPacket counts only with the green LED)
    TotalPacketsAttempted = 0;

    if (CurrentView == FRONTVIEW)
    {
        SendCommand((char *)"vis ams,1");
    }

    strcpy(TextFileName, "");
    for (int i = 0; i < CHANNELSUSED; ++i)
    {
        PreviousBuffer[i] = 0;
        SendBuffer[i] = 0;
        BuddyBuffer[i] = 0;
        ShownBuffer[i] = 0;
        RawDataBuffer[i] = 0;
        LastBuffer[i] = 0;
        PreMixBuffer[i] = 0;
    }
}
// *********************************************************************************************************************************/
void EnsureMotorIsOff()
{
    if (!UseMotorKill)
        return;
    if (BuddyPupilOnWireless)
        return;
    CheckMotorOff();
    CRUMB(CRUMB_MOTORWAIT);
    while (MotorEnabled) // disconnected now so stay here until motor switch really is off!
    {
        SendCommand(WarnNow);
        SendText(Warning, err_MotorOn);
        SendNoData = true;
        PlaySound(MOTORON);
        Force_Early_Sound = true; // Force sound to play
        DelayWithDog(1200);
        Force_Early_Sound = true; // Force sound to play
        PlaySound(PLSTURNOFF);
        MsgBox(pFrontView, (char *)"The motor switch is ON.\r\nSwitch it off, then press OK.");
        DelayWithDog(500); // allow time for sound to play and for pilot to react
        CheckMotorOff();
    }
    SendCommand(WarnOff);
    SendNoData = false;
}
/*********************************************************************************************************************************/

void RedLedOn() // heer
{
    const bool wasGreen = LedWasGreen;   // B90: the moment of the loss, once (the blinking LED calls this again and again)
    analogWrite(GREENLED, 0);
    analogWrite(BLUELED, 0);
    analogWrite(REDLED, GetLEDBrightness()); // Brightness is a function of maybe blinking
    if (LedWasGreen)
    {
        if (AnnounceConnected & !BuddyPupilOnWireless && !ReceiverUpdateBusy())
            PlaySound(DISCONNECTEDMSG); // (not during a receiver update: the comings and goings are ours - RxUpdate.h)
        if (UseLog && !ReceiverUpdateBusy())
            LogDisConnection();
        if (CurrentView == FRONTVIEW)
        {
            SendText((char *)"Connected", na);
            SendCommand(WarnOff);
            SendCommand((char *)"vis Quality,0");
        }
    }
    SendCommand((char *)"vis rpm,0"); // This will make the RPM display invisible
    SendCommand((char *)"vis StillConnected,0");
    if (!BindingEnabled)
        SendCommand((char *)"vis wb,0");
    SendText((char *)"Owner", TxName); // Put owner name back
    First_RPM_Data = true;             // ready to start RPM data ...
    ClearMostParameters();
    LedWasRed = true;
    EnsureMotorIsOff();
    if (wasGreen) RfModelGone();   // B90: a Rotorflight page in view goes over to the backup file (PipeHttp.h)
}

/*********************************************************************************************************************************/

void BlueLedOn()
{
    LedWasGreen = false;
    LedWasRed = false;
    analogWrite(REDLED, 0);
    analogWrite(GREENLED, 0);
    analogWrite(BLUELED, GetLEDBrightness()); // Brightness is a function of maybe blinking
}

/*********************************************************************************************************************************/

void GreenLedOn()
{
    if (!ModelMatched || UsingDefaultPipeAddress)
        return; // no green led for wrong model
    if (!LedWasGreen)
    {
        if (CurrentView == FRONTVIEW)
        {
            SendCommand((char *)"vis ams,0");
        }
        SendCommand((char *)"vis wb,0"); // Hide the binding button
        BindingEnabled = false;          // Disable new binding after successful bind
        LedIsBlinking = false;           // Stop blinking if it was blinking for binding
        LedGreenMoment = millis();
        LastShowTime = 0;
        ShowComms();
        if (AnnounceConnected && !ReceiverUpdateBusy()) // (during a receiver update RxUpdate.h says "Connected" once, when the new release is heard)
        {
            Force_Early_Sound = true; // Force sound to play
            PlaySound(CONNECTEDMSG);
            if (Connect_MMmsg) // this is set when Modelmatch is executed during binding.
            {
                DelayWithDog(1000);       // wait a second before playing the message (B156: packets keep going meanwhile - DelaySimple was a blind second on every reconnection)
                Force_Early_Sound = true; // Force sound to play
                PlaySound(Connect_MMmsg); // play the message that was set during ModelMatch  ("Model Found!" or "Model matched!" or "Model not found!")
                Connect_MMmsg = 0;        // reset the message to be played later
            }
        }
        if (UseLog && !ReceiverUpdateBusy())
        {
            LogConnection();
        }

        analogWrite(BLUELED, 0);
        analogWrite(REDLED, 0);
        analogWrite(GREENLED, GetLEDBrightness()); // Brightness is a function of maybe blinking
        LedWasGreen = true;
        LedWasRed = false;
        Reconnected = false;
        ForceVoltDisplay = true; // Force a battery check of the models battery
        SendInitialSetupParams();
        ResetMotorTimer();
        TotalPacketsAttempted = 0;
        strcpy(TextFileName, ""); // avoid logging to the wrong file
        strcpy(LogWriteName, ""); // B56: today's name again, from the clock
    }
    else
    {
        if (LedIsBlinking)
            analogWrite(GREENLED, GetLEDBrightness()); // Blink Led!
    }
}

/*********************************************************************************************************************************/
// B109 (Malcolm, 16 Oct 2026, of the Channels page: "I forgot to include the numeric indication of how many microseconds
// that channel is at"): beside each bar, by its own button, what the channel is sending, in microseconds (us1 .. us16,
// screen 1.11.80). Each one goes straight onto the wire, a whole command or nothing (RcPut, RF_Rates.h: it never waits and
// never reads, so the radio is not held up and no touch is lost); what has no room yet goes in a later pass, starting
// where this one stopped. A change of 3 or more shows at once; a smaller one once it has stood for half a second (else the
// last digit would flicker with a stick's own noise).
static uint16_t UsShown[CHANNELSUSED];   // what each box shows (0: nothing yet - Force_ReDisplay)
static uint32_t UsMovedAt[CHANNELSUSED]; // since when the channel has differed from it (0: it has not)
static uint8_t UsNext = 0;               // where the next pass starts
FLASHMEM bool UsSteadyChange(uint16_t v, uint16_t shown, uint32_t &movedAt, uint32_t now) // should a shown number become v now?
{
    if (v == shown)
    {
        movedAt = 0;
        return false;
    }
    if (!movedAt)
        movedAt = now ? now : 1; // (not now | 1: that can be a millisecond ahead of now, and now minus it a huge age)
    return abs((int)v - (int)shown) >= 3 || now - movedAt >= 500; // (an empty box, 0, is always 500 or more away)
}
FLASHMEM void ShowChannelMicros()
{
    const uint32_t now = millis();
    for (int k = 0; k < CHANNELSUSED; ++k)
    {
        const int i = (UsNext + k) % CHANNELSUSED;
        const uint16_t v = SendBuffer[i];
        if (!UsSteadyChange(v, UsShown[i], UsMovedAt[i], now))
            continue;
        char c[24];
        snprintf(c, sizeof(c), "us%d.txt=\"%u\"", i + 1, (unsigned)v);
        if (!RcPut(c))
        {
            UsNext = (uint8_t)i;
            return;
        }
        UsShown[i] = v;
        UsMovedAt[i] = 0;
    }
}
/*********************************************************************************************************************************/
// B110 (Malcolm, 16 Oct 2026, of the curve page: "we see on the right stick input and servo output and then numbers which
// are a percentage - not a very useful number. I think probably it should say more simply input and output, and probably
// the numbers should be microseconds"): Input is where the stick (or switch, or knob) is, on the usual scale - its
// calibrated low end 1000, its centre 1500, its high end 2000, each half by its own calibration, as the curve takes it
// (ExponentialInterpolation); Output is what the channel sends (SendBuffer, as on the Channels page). Steadied and sent as
// the Channels page's numbers are (UsSteadyChange, RcPut).
FLASHMEM int StickMicros(uint8_t dev, int raw)
{
    const int lo = ChannelMin[dev], mid = ChannelCentre[dev], hi = ChannelMax[dev];
    float f = 0.0f;
    if (raw >= mid && hi > mid)
        f = (float)(raw - mid) / (float)(hi - mid);
    else if (raw < mid && mid > lo)
        f = -(float)(mid - raw) / (float)(mid - lo);
    return constrain((int)lroundf(1500.0f + 500.0f * f), MINMICROS, MAXMICROS); // (past a calibrated end it goes on; not past the scale)
}
// B124 (Malcolm, 19 Oct 2026: two mornings of "the sticks need recalibrating again" were the Havok's Bank 4 aileron curve, its
// centre point left at 83 degrees after an experiment with the curve page; the calibration itself was sound every time). When a
// calibration is saved the outputs are looked at with the sticks where the pilot has just centred them: a channel whose stick
// reads centred but whose output does not is named, with what moves it - the page says where to look, instead of inviting
// another calibration. Nothing is said when they agree. Three lines of at most 28 characters: the Calibrate page's box.
FLASHMEM void CalibrationNote(char *out, size_t n)
{
    strlcpy(out, "Calibration saved.", n);
    for (uint8_t ch = 0; ch < CHANNELSUSED; ++ch)
    {
        const uint8_t dev = InPutStick[ch];
        if (dev > 3 || ch == MotorChannel || (ArmingChannel >= 1 && ch == ArmingChannel - 1))
            continue; // a knob or a switch feeds it, or the firmware forces it
        if (abs(StickMicros(dev, AnalogueReed(dev)) - 1500) > 10)
            continue; // its stick is not at the centre now
        if (abs((int)SendBuffer[ch] - 1500) <= 10)
            continue;
        snprintf(out, n, "Saved. %s is %d at\r\ncentre: its curve, trim or\r\nsubtrim moves it.", ChannelNames[ch], (int)SendBuffer[ch]);
        return;
    }
}
// B126 (Malcolm, 19 Oct 2026, the day after the Havok's Bank 4 aileron curve had him recalibrating twice: "when the
// transmitter boots up, if it sees Rotorflight is used for this model, and if it also sees that the centre position of
// Aileron, elevator, or rudder is not where it should be, 1500, then it should warn the user of this as well as which
// flight mode is not properly centred"). Every stick and knob is put at its calibrated centre and the outputs are worked
// out bank by bank through the stages of a frame (the curves, the mixes, the trims and subtrims, the routing, the
// reversing): a stick-fed channel that does not come out at 1500 is named with its bank. The throttle or collective
// stick's channels are left out, with the motor and arming channels: a collective curve has its own reasons. Nothing is
// said when all is well. The frame's buffers are worked out again from the sticks afterwards. The front page shows the
// note once, at power-up and when a model is chosen (CentreNoteTick, as the clock's message).
static void StagesAfterInputs() // a frame's stages after GetAllInputs, less the slow servos (they keep time)
{
    MixInputs();
    CalculateAllOutputs();
    MixOutputs();
    DoTrimsAndSubtrims();
    RerouteOutputs();
    ServoReverse();
}
FLASHMEM void CentreNote(char *out, size_t n) // out: "" when every bank is centred, or the model has no Rotorflight
{
    out[0] = 0;
    if (!RotorFlight_V)
        return;
    const uint8_t bankWas = Bank;
    const uint8_t collective = MotorChannel < CHANNELSUSED ? InPutStick[MotorChannel] : 255; // the stick that feeds the motor channel
    uint8_t found = 0;
    for (uint8_t b = 1; b <= BanksCount() && found < 3; ++b) // (B130: six banks when the model uses them)
    {
        Bank = b;
        for (uint8_t ch = 0; ch < CHANNELSUSED; ++ch)
        {
            const uint8_t dev = InPutStick[ch];
            InputsBuffer[ch] = (dev < 8 && !InputIsSwitch(dev)) ? ChannelCentre[dev] : ReadThreePositionSwitch(dev); // (as GetAllInputs, the sticks centred)
        }
        StagesAfterInputs();
        for (uint8_t ch = 0; ch < CHANNELSUSED && found < 3; ++ch)
        {
            const uint8_t dev = InPutStick[ch];
            if (dev > 3 || dev == collective || ch == MotorChannel || (ArmingChannel >= 1 && ch == ArmingChannel - 1))
                continue; // a knob or a switch feeds it, the throttle or collective stick does, or the firmware forces it
            const uint8_t at = ChannelOutPut[ch] < CHANNELSUSED ? ChannelOutPut[ch] : ch; // where RerouteOutputs put it
            const int v = SendBuffer[at];
            if (abs(v - 1500) <= 10)
                continue;
            char line[48];
            snprintf(line, sizeof(line), "%sBank %d: %s is %d", found ? "\r\n" : "", b, ChannelNames[ch], v);
            strlcat(out, line, n);
            ++found;
        }
    }
    Bank = bankWas;
    GetAllInputs();
    StagesAfterInputs(); // the frame's buffers as the sticks have them now
    if (found)
        strlcat(out, "\r\nwith the stick centred.\r\nPlease put it to the centre\r\nbefore flying.", n); // (three lines of names at most + these three: the popup's 180 characters. B127, Malcolm: "A curve, trim or subtrim moves it" is not needed; B128: his words)
}
static uint16_t GraphShown[2];   // what Input and Output show (0: nothing yet - DisplayCurveAndServoPos)
static uint32_t GraphMovedAt[2];
FLASHMEM void ShowGraphMicros(uint16_t in, uint16_t out)
{
    const uint16_t v[2] = {in, out};
    static const char *const box[2] = {"Input", "Output"};
    const uint32_t now = millis();
    for (int i = 0; i < 2; ++i)
    {
        if (!UsSteadyChange(v[i], GraphShown[i], GraphMovedAt[i], now))
            continue;
        char c[24];
        snprintf(c, sizeof(c), "%s.val=%u", box[i], (unsigned)v[i]);
        if (!RcPut(c))
            return; // (no room: next time)
        GraphShown[i] = v[i];
        GraphMovedAt[i] = 0;
    }
}
/*********************************************************************************************************************************/

FASTRUN void ShowServoPos()
{
    uint8_t MinimumDistance = 3; // if the change is small, don't re-display anything - to reduce flashing. :=)!!
    uint32_t Hertz = 25;         // Fast
    if (CurrentView == GRAPHVIEW)
        Hertz = 40; // Faster update rate for graph (was 200)
    if (millis() - ShowServoTimer < Hertz)
        return;
    ShowServoTimer = millis();
    CRUMB(CRUMB_SERVOPOS);

    char Ch_Lables[16][5] = {"Ch1", "Ch2", "Ch3", "Ch4", "Ch5", "Ch6", "Ch7", "Ch8", "Ch9", "Ch10", "Ch11", "Ch12", "Ch13", "Ch14", "Ch15", "Ch16"};
    uint16_t StickPosition = 54321;
    int InputDevice = 0;
    int InputAmount = 0;

    // The first 8 channels are displayed on all three of these screens
    if ((CurrentView == STICKSVIEW) || (CurrentView == FRONTVIEW) || (CurrentView == CALIBRATEVIEW))
    {
        for (int i = 0; i < 8; ++i)
        {
            if (SourceOfOutput(i) > 3) // (B31: output i shows the channel routed to it)
                MinimumDistance = 40; // coarse for pots & switches...
            else
                MinimumDistance = 3; // ...finer for sticks
            if (abs(SendBuffer[i] - ShownBuffer[i]) > MinimumDistance)
            { // no need to show tiny movements
                SendValue(Ch_Lables[i], IntoLowerRes(SendBuffer[i]));
                ShownBuffer[i] = SendBuffer[i];
            }
        }
    }
    MinimumDistance = 6;
    // The second 8 channels are displayed on only two screens
    if ((CurrentView == STICKSVIEW) || (CurrentView == FRONTVIEW))
    {
        for (int i = 8; i < 16; ++i)
        {
            if (abs(SendBuffer[i] - ShownBuffer[i]) > MinimumDistance)
            {
                SendValue(Ch_Lables[i], IntoLowerRes(SendBuffer[i]));
                ShownBuffer[i] = SendBuffer[i];
            }
        }
    }
    if (CurrentView == STICKSVIEW)
        ShowChannelMicros(); // B109: the numbers beside the bars
    if ((CurrentView == GRAPHVIEW))
    {
        if (ChanneltoSet < 1 || ChanneltoSet > 16)
            return; // ClaudeFix-2-7-2026 ChanneltoSet can still be 0 when the graph page appears by an unusual route -- InPutStick[-1] was read
        MinimumDistance = 2; // B117: a couple of pixels (it was 4, and the marker went in steps of 3.6)
        InputDevice = (InPutStick[ChanneltoSet - 1]);
        if (InputDevice < 8 && !InputIsSwitch(InputDevice)) // (B33)
            InputAmount = InputUnused(InputDevice) ? ChannelCentre[InputDevice] : AnalogueReed(InputDevice); // (B38)
        else
            InputAmount = ReadThreePositionSwitch(InputDevice);                                                   // not analogue
        const int InputUs = StickMicros(InputDevice, InputAmount);                                                // B110: the stick, 1000 .. 2000 (each half by its own calibration)
        ShowGraphMicros(InputUs, SendBuffer[ChanneltoSet - 1]);                                                   // B110: Input and Output in microseconds (Output: SendBuffer[ChanneltoSet - 1], ClaudeFix-2-7-2026 - not SendBuffer[InputDevice])
        StickPosition = constrain(map(InputUs, 1000, 2000, GRAPH_MARKER_FIRST, GRAPH_MARKER_LAST + 1), GRAPH_MARKER_FIRST, GRAPH_MARKER_LAST); // B117: the marker's column by the microsecond (it went in 2 % steps of 3.6 pixels)

        if (abs((int)StickPosition - (int)SavedLineX) >= MinimumDistance)
        {
            GraphMarkerMove(SavedLineX, StickPosition); // B117: only the marker moves; the curve stays (it was a full redraw each time: 1.5 kB and a flash of black)
            SavedLineX = StickPosition;
        }
    }
}

/*********************************************************************************************************************************/
// B118: the three shapes over the channel's CurveDotsN points (GetCurveDots: 3, 5, 7 or 9, with the rate applied); the stick's
// reading at each point from CurveX. With five points every one of these gives exactly what it gave before.
uint16_t CatmullSplineInterpolation(uint16_t InputValue, uint16_t InputChannel, uint16_t OutputChannel)
{ // B120: its own arrays - it used the curve page's xPoints/yPoints (the dots' places on the glass), and so, running 40 times a
  // second for every smooth channel, left them as stick readings and microseconds: the marker's repair (B117) then redrew the
  // wrong segments and a smooth curve broke up as the stick moved (Malcolm, 17 Oct 2026)
    const uint8_t n = CurveDotsN;
    double xs[CURVE_POINTS_MAX], ys[CURVE_POINTS_MAX];
    for (uint8_t k = 0; k < n; ++k)
    {
        xs[k] = CurveX(InputChannel, k, n);
        ys[k] = CurveMicros(CurveDots[k]);
    }
    return Interpolation::CatmullSpline(xs, ys, n, InputValue);
}
/*********************************************************************************************************************************/
uint16_t StraightLineInterpolation(uint16_t InputValue, uint16_t InputChannel, uint16_t OutputChannel)
{ // the segment whose right-hand point is the first at or beyond the stick (the last one runs on past the end, as the first does below it)
    const uint8_t n = CurveDotsN;
    uint8_t k = 0;
    while (k < n - 2 && InputValue > CurveX(InputChannel, k + 1, n))
        ++k;
    uint16_t v = map(InputValue, CurveX(InputChannel, k, n), CurveX(InputChannel, k + 1, n), CurveMicros(CurveDots[k]), CurveMicros(CurveDots[k + 1]));
    return v;
}
/*********************************************************************************************************************************/
uint16_t ExponentialInterpolation(uint16_t InputValue, uint16_t InputChannel, uint16_t OutputChannel)
{ // the ends and the centre, whatever the count
    const uint8_t n = CurveDotsN, mid = CurveMid(n), last = n - 1;
    uint16_t k = 0;
    if (InputValue >= ChannelCentre[InputChannel])
    {
        k = MapWithExponential(InputValue - ChannelCentre[InputChannel], 0, ChannelMax[InputChannel] - ChannelCentre[InputChannel], 0, CurveMicros(CurveDots[last]) - CurveMicros(CurveDots[mid]), Exponential[Bank][OutputChannel]) + CurveMicros(CurveDots[mid]);
    }
    else
    {
        k = MapWithExponential(ChannelCentre[InputChannel] - InputValue, 0, ChannelCentre[InputChannel] - ChannelMin[InputChannel], CurveMicros(CurveDots[mid]) - CurveMicros(CurveDots[0]), 0, Exponential[Bank][OutputChannel]) + CurveMicros(CurveDots[0]);
    }
    return k;
}

/*********************************************************************************************************************************/
// ************* Small function pointer array for interpolation types ************************************************************

uint16_t (*Interpolate[3])(uint16_t InputValue, uint16_t InputChannel, uint16_t OutputChannel){
    StraightLineInterpolation,  // 0
    CatmullSplineInterpolation, // 1
    ExponentialInterpolation    // 2
};

/*********************************************************************************************************************************/
/**************************** This function implements slowed servos for flaps, U/Cs etc. ****************************************/
/*********************************************************************************************************************************/

void SlowAnyServos() // This function implements slowed servos for flaps, U/Cs etc.
{
    static uint32_t SlowTime[16]; // TODO: Make it BY BANK and not every bank <<<<<<<<<<<<<<*****************************
    for (int i = 0; i < 16; ++i)
    { // Test every channel
        if (ServoSpeed[Bank - 1][i] < 100)
        { // If ServoSpeed = 100, use full speed. No slowing
            if ((millis() - SlowTime[i]) > 10)
            {                           // This next part runs only 100 times per second
                SlowTime[i] = millis(); // Store start time of this iteration
                if (CurrentPosition[i] == 0)
                    CurrentPosition[i] = SendBuffer[i];            // Must start somewhere
                int distance = SendBuffer[i] - CurrentPosition[i]; // Define how far to move
                int SSize = ServoSpeed[Bank - 1][i];               // Get step size
                if (SSize > abs(distance))
                    SSize = 1; // This avoids overshooting the limit
                if (distance < 0)
                    SSize = -SSize; // Negative?
                if (!distance)
                    SSize = 0;               // Already arrived?
                CurrentPosition[i] += SSize; // Move Current Position a little bit towards goal
            }
            SendBuffer[i] = CurrentPosition[i]; // Modify next servo position
            PreMixBuffer[i] = SendBuffer[i];    // Maybe mix the slowed version
        }
    }
}
/*********************************************************************************************************************************/
void RerouteOutputs()
{ // This function re-routes outputs to the defined channels

    uint16_t temp[CHANNELSUSED];
    for (int i = 0; i < CHANNELSUSED; ++i)
    {
        temp[i] = PreMixBuffer[i];
    }
    for (int i = 0; i < CHANNELSUSED; ++i)
    { // B31: channel i goes OUT to output ChannelOutPut[i], as the Inputs page says (it gathered the other way round: a ring of three sent channel 1 to output 3)
        const uint8_t out = ChannelOutPut[i] < CHANNELSUSED ? ChannelOutPut[i] : i;
        PreMixBuffer[out] = temp[i];
    }
    for (int i = 0; i < CHANNELSUSED; ++i)
        SendBuffer[i] = PreMixBuffer[i];
}
/*********************************************************************************************************************************/
uint8_t SourceOfOutput(uint8_t out) // B31: the channel that is routed to output 'out' (ChannelOutPut[channel] == out); itself when none is
{
    for (uint8_t k = 0; k < CHANNELSUSED; ++k)
        if (ChannelOutPut[k] == out)
            return k;
    return out;
}

/*********************************************************************************************************************************/

void DoTrimsAndSubtrims()
{

    for (uint16_t OutputChannel = 0; OutputChannel < CHANNELSUSED; ++OutputChannel)
    {
        uint16_t InputChannel = InPutStick[OutputChannel]; // Input sticks knobs & switches are mapped by user
        // ClaudeFix-2-7-2026 Signed maths! SendBuffer is uint16_t: a low curve value plus a negative
        // subtrim/trim used to wrap below zero to ~65000, and constrain then
        // clamped it to MAXMICROS -- FULL deflection in the WRONG direction.
        int TrimmedValue = (int)SendBuffer[OutputChannel];
        TrimmedValue += (SubTrims[OutputChannel] - 127) * 5;                       // ADD SUBTRIM to output channel, (Range 0 - 127 - 254) multiplier is always 5 otherwise subtrim might keep changing
        TrimmedValue += GetTrimAmount(InputChannel);                               // ADD TRIM to output channel
        SendBuffer[OutputChannel] = constrain(TrimmedValue, (int)RangeLo(), (int)RangeHi()); // Keep within limits (B113: this model's max range)
        PreMixBuffer[OutputChannel] = SendBuffer[OutputChannel];                   // premixbuffer will be needed again...
    }
}
//**************************************************************************************************************************************************************
void CalculateAllOutputs()
{
    for (uint16_t OutputChannel = 0; OutputChannel < CHANNELSUSED; ++OutputChannel)
    {
        GetCurveDots(OutputChannel, DualRateValue);                                                                                                                // This for the Dual Rates function
        PreMixBuffer[OutputChannel] = Interpolate[InterpolationTypes[Bank][OutputChannel]](InputsBuffer[OutputChannel], InPutStick[OutputChannel], OutputChannel); // Use function pointer array to invoke selected interpolation.
        SendBuffer[OutputChannel] = PreMixBuffer[OutputChannel];                                                                                                   // Copy now to SendBuffer in case no mixes are needed
    }
}
//**************************************************************************************************************************************************************
void GetAllInputs()
{
    for (uint16_t OutputChannel = 0; OutputChannel < CHANNELSUSED; ++OutputChannel)
    {
        if (InPutStick[OutputChannel] < 8 && !InputIsSwitch(InPutStick[OutputChannel])) // (B33: a switch given input 5-8 takes the place of the front switch or knob)
        {
            if (InputUnused(InPutStick[OutputChannel]))
                InputsBuffer[OutputChannel] = ChannelCentre[InPutStick[OutputChannel]]; // (B38) a front switch marked Not used: its channel's input sits at its centre
            else
                InputsBuffer[OutputChannel] = AnalogueReed(InPutStick[OutputChannel]); // Get values from sticks' pots (taking into account mode 1 and mode 2!)
        }
        else
        {
            InputsBuffer[OutputChannel] = ReadThreePositionSwitch(InPutStick[OutputChannel]); // Get values from switches (ClaudeFix-2-7-2026 via the user's input mapping, like the analogue branch above -- passing OutputChannel only worked when input == output)
        }
    }
}
/*********************************************************************************************************************************/
//                                               new version of GET NEW SERVO POSITIONS
/*********************************************************************************************************************************/
/** @brief GET NEW SERVO POSITIONS */
FASTRUN void GetNewChannelValues()
{
    CRUMB(CRUMB_CHANNELS);
    if (!NewCompressNeeded)
    {
        NewCompressNeeded = true;
        GetAllInputs();        // Get all user inputs from sticks, pots and switches
        MixInputs();           // Mixes InputsBuffer[] and returns results in InputsBuffer[] (All 16 channels)
        CalculateAllOutputs(); // Calculate all outputs
        SlowAnyServos();       // Some servos may need to be slowed down for flaps etc.
        MixOutputs();          // If needed, Mixes PremixBuffer and returns it in SendBuffer.
        DoTrimsAndSubtrims();  // Add trims to output after mixing.
        RerouteOutputs();      // This function might re-route outputs to user-defined channels.
        ServoReverse();        // This function reverses servos if needed.
    }
}
/*********************************************************************************************************************************/
void ResetSwitchNumbers()
{
    for (int i = 0; i < 8; ++i)
    {
        SwitchNumber[i] = DefaultSwitchNumber[i];
    }
}

/*********************************************************************************************************************************/

char I2cSeen[48] = "";   // B62: the addresses that answered at power-on ("0x50 0x68"), for the clock's message
FLASHMEM void ScanI2c()
{
    int ii;
    USE_INA219 = false;
    I2cSeen[0] = 0;
    for (ii = 1; ii < 127; ++ii)
    {
        Wire.beginTransmission(ii);
        if (Wire.endTransmission() == 0)
        {
            if (strlen(I2cSeen) < sizeof(I2cSeen) - 6) { char b[8]; snprintf(b, sizeof(b), "%s0x%02X", I2cSeen[0] ? " " : "", ii); strcat(I2cSeen, b); }
#ifdef DB_SENSORS
            Serial.print(ii, HEX); // in case new one shows up
            Serial.print("   ");
            if (ii == 0x40)
                Serial.println("INA219 voltage meter detected!");
#endif

            if (ii == 0x40)
            {
                USE_INA219 = true;
            }
        }
    }
}

/*********************************************************************************************************************************/
// V2 B30: a clock that did not answer at power-on is said once. B62 (a second transmitter whose clock never answered,
// 7 Oct): the message says what the I2C bus answered, so the fault is placed - nothing at all (power, SDA 18, SCL 19,
// pull-ups) or the module's memory (0x50, 0x57) but not its clock (0x68). B63: NOT while new firmware is on trial. The
// box waits for OK, and the trial counts only the main loop's running (FwTrialTick): the screen's updater waited for
// the confirmation that could not come, and called a good update failed. Said once the trial is over instead.
bool ClockMessagePending = false;
void ClockMessageTick()
{
    static bool asked = false;
    char pFront[] = "page FrontView";
    if (!asked) { asked = true; ClockMessagePending = ClockRecovered || ClockDead; }
    if (!ClockMessagePending || FwTrialRunning || CurrentView != FRONTVIEW || ModelMatched)
        return;
    ClockMessagePending = false;
    char dead[200];
    if (!I2cSeen[0]) snprintf(dead, sizeof(dead), "The clock does not answer.\r\nNothing answers on the I2C bus:\r\ncheck 5 V to the module, SDA to pin 18,\r\nSCL to pin 19, and its pull-up resistors.");
    else snprintf(dead, sizeof(dead), "The clock does not answer (0x68).\r\nOn the I2C bus: %s.\r\nThe time is set from WiFi or a phone\r\nuntil it does.", I2cSeen);
    MsgBox(pFront, ClockDead ? dead : (char *)"The clock had stopped answering\r\nand was started again.\r\n\r\nThe time is put right by itself\r\nfrom WiFi, or from a phone.");
    GotoFrontView();
}
/*********************************************************************************************************************************/

// B126: the centre note (CentreNote), once, on the front page, when nothing is connected, no question is waiting and no
// firmware is on trial (B63: a box at power-up would stall the trial's confirmation). CentreNotePending is set at
// power-up and when a model is chosen (ModelViewEnd).
void CentreNoteTick()
{
    char pFront[] = "page FrontView";
    if (!CentreNotePending || FwTrialRunning || CurrentView != FRONTVIEW || ModelMatched || ModalWaits)
        return;
    CentreNotePending = false;
    char note[200];
    CentreNote(note, sizeof(note));
    if (!note[0])
        return;
    PlaySound(WHAHWHAHMSG);
    MsgBox(pFront, note);
    GotoFrontView();
}
/*********************************************************************************************************************************/

void UpdateModelsNameEveryWhere()
{
    char Owner[] = "Owner";
    char TheModelName[] = "ModelName";
    char GraphView_Channel[] = "Channel";
    char TrimView_Bank[] = "t1";
    char GraphView_fmode[] = "fmode";
    char SticksView_t1[] = "t1";
    char NoName[40];
    char Ch[] = "Channel ";
    char Nbuf[7];
    char mn1[40]; // holds model name plus its number
    char lb[] = " (";
    char rb[] = ")";

    strcpy(mn1, ModelName);

    if (CurrentView == FRONTVIEW)
        SendText(Owner, TxName);

    if (!ModelsMacUnionSaved.Val64)
    {
        strcpy(lb, " [");
        strcpy(rb, "]");
    }
    else
    {
        strcpy(lb, " (");
        strcpy(rb, ")");
    }

    if (CurrentView != MODELSVIEW)
    {
        strcat(mn1, lb);
        strcat(mn1, Str(Nbuf, ModelNumber, 0)); // Add model number for extra clarity
        strcat(mn1, rb);
    }

    SendText(TheModelName, mn1);

    if (CurrentView == GRAPHVIEW)
    {
        if (strlen(ChannelNames[ChanneltoSet - 1]) < 2)
        { // if no name, just show the channel number
            strcpy(NoName, Ch);
            SendText(GraphView_Channel, strcat(NoName, Str(Nbuf, ChanneltoSet, 0)));
        }
        else
        {
            SendText(GraphView_Channel, ChannelNames[ChanneltoSet - 1]);
        }
    }
    if (CurrentView == STICKSVIEW)
        SendText(SticksView_t1, BankNames[BanksInUse[Bank - 1]]);
    if (CurrentView == GRAPHVIEW)
        SendText(GraphView_fmode, BankNames[BanksInUse[Bank - 1]]);
    if (CurrentView == TRIM_VIEW)
    {
        SendText(TrimView_Bank, BankNames[BanksInUse[Bank - 1]]);
        UpdateTrimView();
    }
}

/*********************************************************************************************************************************/

FLASHMEM void InitSwitchesAndTrims()
{
    for (int i = 0; i < 8; ++i)
    {
        pinMode(SwitchNumber[i], INPUT_PULLUP);
        pinMode(TrimNumber[i], INPUT_PULLUP);
    }
    pinMode(BUTTON_SENSE_PIN, INPUT_PULLUP); // New function to sense power button press
}

/*********************************************************************************************************************************/

FLASHMEM void InitCentreDegrees()
{

    for (int j = 1; j <= BANKS_USED; ++j) // (B131: every bank in memory)
    {
        for (int i = 0; i < CHANNELSUSED; ++i)
        {
            CurvePointCount[i] = 5;          // (B118)
            CurveSetStraight(j, i, 0, 180); // 0, 45, 90, 135, 180 degrees
        }
    }
}

/*********************************************************************************************************************************/

void UpdateButtonLabels()
{
    char InputStick_Labels[16][4] = {"c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "c10", "c11", "c12", "c13", "c14", "c15", "c16"};
    char OutputStick_Labels[16][4] = {"n4", "n5", "n6", "n7", "n8", "n9", "n10", "n11", "n12", "n13", "n14", "n15", "n16", "n17", "n18", "n19"};
    char Subtrim_Labels[16][4] = {"n00", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9", "n10", "n11", "n12", "n13", "n14", "n15"};
    char fsch_labels[16][5] = {"ch1", "ch2", "ch3", "ch4", "ch5", "ch6", "ch7", "ch8", "ch9", "ch10", "ch11", "ch12", "ch13", "ch14", "ch15", "ch16"};
    char fs[16][5] = {"fs1", "fs2", "fs3", "fs4", "fs5", "fs6", "fs7", "fs8", "fs9", "fs10", "fs11", "fs12", "fs13", "fs14", "fs15", "fs16"};
    char ChannelLabels[16][6] = {"Sch1", "Sch2", "Sch3", "Sch4", "Sch5", "Sch6", "Sch7", "Sch8", "Sch9", "Sch10", "Sch11", "Sch12", "Sch13", "Sch14", "Sch15", "Sch16"};
    char ChannelNumber[16][6] = {" (1)", "(2) ", " (3)", "(4) ", " (5)", "(6) ", " (7)", "(8) ", " (9)", "(10) ", " (11)", "(12) ", " (13)", "(14) ", " (15)", "(16) "};
    char ArrowRh[] = " >";
    char ArrowLh[] = "< ";
    char TrimLabels[4][4] = {"n0", "n1", "n2", "n3"};
    char LabelText[20];

    if (CurrentView == STICKSVIEW)
    {
        for (int i = 0; i < 16; ++i)
        {
            if ((float)i / 2 != (int)i / 2)
            { // Odd and even labels are formatted differnently here
                strcpy(LabelText, ArrowLh);
                strcat(LabelText, ChannelNumber[i]);
                strcat(LabelText, ChannelNames[i]);
            }
            else
            {
                strcpy(LabelText, ChannelNames[i]);
                strcat(LabelText, ChannelNumber[i]);
                strcat(LabelText, ArrowRh);
            }
            SendText(ChannelLabels[i], LabelText);
        }
        MaxRangeShow(); // B113: "Max range:" 500 to 2500 or 945 to 2055
    }
    if (CurrentView == FAILSAFE_VIEW)
    {
        for (int i = 0; i < 16; ++i)
        {
            SendValue(fs[i], FailSafeChannel[i]);
        }
    }
    if (CurrentView == INPUTS_VIEW || CurrentView == FAILSAFE_VIEW || CurrentView == REVERSEVIEW || CurrentView == BUDDYCHVIEW || CurrentView == SLOWSERVOVIEW)
    {
        for (int i = 0; i < 16; ++i)
        {
            const uint8_t src = CurrentView == REVERSEVIEW ? SourceOfOutput(i) : i; // B31: Reverse acts on OUTPUT i, after routing: name it by the channel that is routed there
            SendText(fsch_labels[i], ChannelNames[src]);
            SendValue(InputStick_Labels[i], InPutStick[i] + 1);
            SendValue(OutputStick_Labels[i], ChannelOutPut[i] + 1);
            if (CurrentView != SLOWSERVOVIEW)
            {
                if (i < 4)
                    SendValue(TrimLabels[i], InputTrim[i] + 1); //
            }
        }
    }
    if (CurrentView == SUBTRIMVIEW)
    {
        for (int i = 0; i < 16; ++i)
        {
            SendText(fsch_labels[i], ChannelNames[i]);
            SendValue(Subtrim_Labels[i], SubTrims[i] - 127);
        }
    }
}

/*********************************************************************************************************************************/
// B113 (Malcolm, 17 Oct 2026, of B111/B112's "Stick ends": "I think here we have confused 'stick ends' with 'max range'.
// We need to control MAX RANGE, but this doesn't necessarily mean stick ends because the curve might not go to the top and
// bottom of the available range"): the Channels page's "Max range:" - 500 to 2500 (as ever) or 945 to 2055 (just past the
// 1000 to 2000 Rotorflight reads on CRSF: Malcolm's sticks stop about 5 % short). The range is what a curve's 0 .. 180
// degrees span (CurveMicros), and a macro's place; the curves are not stretched to it. On a change every point of every
// curve, in every bank, and every macro's place keeps its microseconds where the new range has them - a point outside it
// goes to its edge - so nothing moves but what the new range cannot hold. Never with the motor live; asked first; saved.
FLASHMEM static uint8_t RangeDegrees(int us, uint16_t lo, uint16_t hi) // microseconds -> the nearest degree of the range lo .. hi
{
    us = constrain(us, (int)lo, (int)hi);
    return (uint8_t)constrain((int)lroundf((float)(us - lo) * 180.0f / (float)(hi - lo)), 0, 180);
}
FLASHMEM void MaxRangeConvert(uint8_t narrow) // every curve point into the new range, keeping its microseconds (MaxRangeNarrow still the old one)
{
    const uint16_t lo = narrow ? RANGE_NARROW_LO : MINMICROS, hi = narrow ? RANGE_NARROW_HI : MAXMICROS;
    for (int b = 1; b <= BANKS_USED; ++b) // (B130: banks 5 and 6 too, used or not: they are kept in step)
        for (int ch = 0; ch < CHANNELSUSED; ++ch)
        {
            for (int k = 0; k < CurveN(ch); ++k) // (B118: every point of the curve)
                CurvePoint[b][ch][k] = RangeDegrees(CurveMicros(CurvePoint[b][ch][k]), lo, hi);
            for (int s = 0; s < CURVE_STORE_MAX; ++s) // (B121: and every height remembered for the other counts)
                if (CurveStore[b][ch][s] != CURVE_UNSET)
                    CurveStore[b][ch][s] = RangeDegrees(CurveMicros(CurveStore[b][ch][s]), lo, hi);
        }
    for (int m = 0; m < MAXMACROS; ++m) // (a macro's place is a point of the range too: macros.h RunMacro)
        MacrosBuffer[m][MACROMOVETOPOSITION] = RangeDegrees(CurveMicros(MacrosBuffer[m][MACROMOVETOPOSITION]), lo, hi);
    MaxRangeNarrow = narrow;
}
FLASHMEM void MaxRangeShow() // the choice as it is
{
    SendValue((char *)"mr1", MaxRangeNarrow ? 0 : 1);
    SendValue((char *)"mr2", MaxRangeNarrow ? 1 : 0);
}
FLASHMEM static void MaxRangeChosen(uint8_t narrow) // a choice touched: the question, then the change (or nothing)
{
    char prompt[260];
    if (narrow != MaxRangeNarrow) // (the one already chosen: nothing to do)
    {
        if (MotorEnabled)
        {
            snprintf(prompt, sizeof(prompt), "Switch the motor off first:\r\na new max range can move channels.");
            MsgBox(pSticksView, prompt);
        }
        else
        {
            if (narrow)
                snprintf(prompt, sizeof(prompt), "Set this model's max range to\r\n945 to 2055? Each point keeps its value;\r\n"
                                                 "any beyond that range moves to its edge.\r\nCheck every channel before flying.");
            else
                snprintf(prompt, sizeof(prompt), "Set this model's max range to\r\n500 to 2500? Each point keeps its value:\r\n"
                                                 "the curves can then go further.");
            if (GetConfirmation(pSticksView, prompt))
            {
                MaxRangeConvert(narrow);
                SaveOneModel(ModelNumber);
                snprintf(prompt, sizeof(prompt), "Done: this model's max range is\r\nnow %s. The curve pages run\r\nfrom one end to the other.",
                         narrow ? "945 to 2055" : "500 to 2500");
                MsgBox(pSticksView, prompt);
            }
        }
    }
    Force_ReDisplay(); // (the Channels page is back from the question: everything on it again, the choice as it now is)
    CurrentView = STICKSVIEW;
    UpdateModelsNameEveryWhere();
    UpdateButtonLabels();
    ClearText();
}
FLASHMEM void MaxRangeWideTapped() { MaxRangeChosen(0); }   // 219: "500 to 2500"
FLASHMEM void MaxRangeNarrowTapped() { MaxRangeChosen(1); } // 220: "945 to 2055"
/*********************************************************************************************************************************/
void Force_ReDisplay()
{
    for (int i = 0; i < CHANNELSUSED; ++i)
    {
        ShownBuffer[i] = 242; // to force a re-show of servo positions
        UsShown[i] = 0;       // B109: and of their numbers on the Channels page
        UsMovedAt[i] = 0;
    }
    UsNext = 0;
}

/*********************************************************************************************************************************/

void WatchDogCallBack()
{
    // Serial.println("RESETTING ...");
}

/*********************************************************************************************************************************/

FLASHMEM void SetDS1307ToCompilerTime()
{
    if (getDate(__DATE__) && getTime(__TIME__))
    {
        RTC.write(tm);
    } // only useful when connected to compiler
}

/************************************************************************************************************/

FLASHMEM void GetTXVersionNumber()
{
    char nbuf[5];
    uint8_t Txv1 = TXVERSION_MAJOR;
    uint8_t Txv2 = TXVERSION_MINOR;
    uint8_t Txv3 = TXVERSION_MINIMUS;
    Str(TransmitterVersionNumber, Txv1, 2);
    Str(nbuf, Txv2, 2);
    strcat(TransmitterVersionNumber, nbuf);
    Str(nbuf, Txv3, 0);
    strcat(TransmitterVersionNumber, nbuf);
    strcat(TransmitterVersionNumber, TXVERSION_EXTRA);
}
/************************************************************************************************************/

FASTRUN void BufferTeensyMACAddPipe()
{
    for (int q = 1; q < 6; ++q)
    {
        SendBuffer[q] = MacAddress[q];
    }
}

// *********************************************************************************************************************************/
void teensyMAC(uint8_t *mac) // only works on Teensy 4.1 and 4.0
{                            // there are 2 MAC addresses each 48bit
    uint32_t m1 = HW_OCOTP_MAC1;
    uint32_t m2 = HW_OCOTP_MAC0;
    mac[0] = m1 >> 8;
    mac[1] = m1 >> 0;
    mac[2] = m2 >> 24;
    mac[3] = m2 >> 16;
    mac[4] = m2 >> 8;
    mac[5] = m2 >> 0;
}

/*********************************************************************************************************************************/
// This function gets the unique MAC address of the Teensy 4.1
// And also fixes it so that it's a more suitable Pipe address for the nRF24L01

void GetTeensyMacAddress() //
{
    teensyMAC(MacAddress); // Get MAC address
    for (int i = 1; i < 6; ++i)
    {
        // Look1(MacAddress[i], HEX); // Show MAC address in HEX
        // Look1(" -> ");
        MacAddress[i] = CheckPipeNibbles(MacAddress[i]); // Fix PIPE if needed !
                                                         // MacAddress[i] += 42;                             // test another random pipe address
                                                         //  Look(MacAddress[i], HEX);                        // Show MAC address in HEX
    }

    TeensyMACAddPipe = (uint64_t)MacAddress[0] << 40;
    TeensyMACAddPipe += (uint64_t)MacAddress[1] << 32;
    TeensyMACAddPipe += (uint64_t)MacAddress[2] << 24;
    TeensyMACAddPipe += (uint64_t)MacAddress[3] << 16;
    TeensyMACAddPipe += (uint64_t)MacAddress[4] << 8;
    TeensyMACAddPipe += (uint64_t)MacAddress[5];
}

/*********************************************************************************************************************************/

void ConvertBuddyPipeTo64BITS()
{
    BuddyMACAddPipe = (uint64_t)BuddyMacAddress[0] << 40;
    BuddyMACAddPipe += (uint64_t)BuddyMacAddress[1] << 32;
    BuddyMACAddPipe += (uint64_t)BuddyMacAddress[2] << 24;
    BuddyMACAddPipe += (uint64_t)BuddyMacAddress[3] << 16;
    BuddyMACAddPipe += (uint64_t)BuddyMacAddress[4] << 8;
    BuddyMACAddPipe += (uint64_t)BuddyMacAddress[5];
    BuddyMACAddPipe >>= 8;
}

/*********************************************************************************************************************************/

void WarnUserIfBuddyBoxIsOn() // This function warns the user if the buddy box is on
{
    if (BuddyPupilOnWireless)
    {
        DelayWithDog(4000);
        Force_Early_Sound = true; // Force sound to play
        PlaySound(BUDDYPUPILON);
        DelayWithDog(1500);                     // allow sound to finish
        FHSS_data::PaceMaker = PACEMAKER_BUDDY; // only 200Hz
    }
    if (BuddyMasterOnWireless)
    {
        DelayWithDog(4000);
        Force_Early_Sound = true; // Force sound to play
        PlaySound(BUDDYMASTERON);
        DelayWithDog(1500);                     // allow sound to finish
        FHSS_data::PaceMaker = PACEMAKER_BUDDY; // only 200Hz
    }
}

/*********************************************************************************************************************************/

void initADC() //
{
    // #define MAXRESOLUTION 4095  // 12 BIT
    adc->setResolution(12); // 8, 10, 12 or 16 bits
    adc->setAveraging(4);   // 0, 4, 8, 16 or 32.
    adc->setConversionSpeed(ADC_CONVERSION_SPEED::MED_SPEED);
    adc->setSamplingSpeed(ADC_SAMPLING_SPEED::MED_SPEED);
}
//*********************************************************************************************************************************/
void SetBrightness(uint8_t B) // 0 to 100
{
    char cmd[20];
    char dim[] = "dim=";
    char nb[10];
    strcpy(cmd, dim);
    Str(nb, B, 0);
    strcat(cmd, nb);
    ScreenIsOff = false;
    SendCommand(cmd);
    ScreenTimeTimer = millis(); // reset screen counter
}

/*********************************************************************************************************************************/
// SETUP
/*********************************************************************************************************************************/
FLASHMEM void setup()
{
    char FrontView_BackGround[] = "FrontView.BackGround";
    char FrontView_ForeGround[] = "FrontView.ForeGround";
    char FrontView_Special[] = "FrontView.Special";
    char FrontView_Highlight[] = "FrontView.Highlight";
    char err_chksm[] = "File checksum?";
    char err_404[] = "SD card error!";
    char FrontView_Connected[] = "Connected";
    char FrontView_Hours[] = "Hours";
    char FrontView_Mins[] = "Mins";
    char FrontView_Secs[] = "Secs";
    char ModelsFile[] = "models.dat";

    pinMode(REDLED, OUTPUT);
    pinMode(GREENLED, OUTPUT);
    pinMode(BLUELED, OUTPUT);
    pinMode(POWER_OFF_PIN, OUTPUT);
    digitalWrite(POWER_OFF_PIN, LOW); // default is LOW anyway. HIGH to turn off
    BlueLedOn();
    NEXTION.begin(921600); // BAUD rate also set in display code THIS IS THE MAX
    NEXTION.addMemoryForRead(LinkRxMemory, sizeof(LinkRxMemory)); // V1B: room for a whole frame of the file link
    InitMaxMin();
    InitCentreDegrees();
    SetBrightness(1);
    ResetSubTrims();
    CentreTrims();
    strcpy(TextFileName, "");
    ErrorState = NOERROR;

    CheckSDCard(); // Check if SD card is present and working and initialise it
    if (SD_Card_Exists)
        TidyLogFolder(); // V2 B29: more than 90 log files, and the oldest go (down to 80), before the radio starts
    ReadWhyOff();  // V1B: why the transmitter went off last time, and what reset the chip (FlightGuard.h)
    FwTrialAtBoot(); // V1B: firmware on trial that has not stayed up is replaced by the previous one, here, before the watchdog runs

    WatchDogConfig.window = WATCHDOGMAXRATE;  //  = MINIMUM RATE in milli seconds, (32ms to 522.232s) must be MUCH smaller than timeout
    WatchDogConfig.timeout = WATCHDOGTIMEOUT; //  = MAX TIMEOUT in milli seconds, (32ms to 522.232s)
    WatchDogConfig.callback = WatchDogCallBack;
    TeensyWatchDog.begin(WatchDogConfig);
    delay(300); // <<********************* MUST ALLOW DOG TO INITIALISE

    DelayWithDog(WARMUPDELAY);

    if (CheckFileExists(ModelsFile))
    {
        if (!LoadAllParameters())
        { // if file not good ..
            ErrorState = CHECKSUMERROR;
        }
    }
    else
    {
        ErrorState = MODELSFILENOTFOUND; // if no file ... or no SD
    }

    SetBrightness(1);         // Set low brightness for splash screen
    SendCommand(pSplashView); // show splash screen **************************
    CurrentView = SPLASHVIEW; // while loading ...
    GetTeensyMacAddress();
    ConvertBuddyPipeTo64BITS();
    Wire.begin();
    ScanI2c();
    CheckTheClock(); // V2 B30: a clock that does not answer is clocked back to life
    if (USE_INA219)
        ina219.begin();
    InitSwitchesAndTrims();
    InitRadio(DefaultPipe);
    delay(WARMUPDELAY); // Allow Nextion time to warm up
    BackGroundColour = Black;
    ForeGroundColour = White;
    SpecialColour = Red;
    HighlightColour = Yellow;
    SendValue(FrontView_BackGround, BackGroundColour); // Get colours ready
    SendValue(FrontView_ForeGround, ForeGroundColour);
    SendValue(FrontView_Special, SpecialColour);
    SendValue(FrontView_Highlight, HighlightColour);
    CurrentView = 254;
    SetAudioVolume(AudioVolume);
    SendOtherValue((char *)"Screen_Background", BackGroundSelection); // also set screen background
    SendOtherValue((char *)"FrontView.pic", BackGroundSelection);
    if (PlayFanfare)
    {
        Force_Early_Sound = true; // Force sound to play
        PlaySound(WINDOWS1);
    }
    for (int i = 1; i < 100; ++i) // fade in screen brightness
    {
        SetBrightness(i);
        DelayWithDog(15);
    }
    if (PlayFanfare)
        DelayWithDog(1000);
    SendValue(FrontView_Hours, 0);
    SendValue(FrontView_Mins, 0);
    SendValue(FrontView_Secs, 0);
    //  ***************************************************************************************
    //  SetDS1307ToCompilerTime();    //  **   Uncomment this line to set DS1307 clock to compiler's (Computer's) time.        **
    // **   BUT then re-comment it!! Otherwise it will reset to same time on every boot up! **
    //  ***************************************************************************************
    BoundFlag = false;
    StartInactvityTimeout();
    GetTXVersionNumber();
    ScreenTimeTimer = millis();
    SendText(FrontView_Connected, na);
    UpdateModelsNameEveryWhere();
    ConfigureStickMode();
    WarningTimer = millis();
    EnsureMotorIsOff();

    if (!BuddyPupilOnWireless)
    { // when pupil is buddying wirelessly, these potential errors are ignored

        if (!UseMotorKill)
            ShowMotor();
        if (SafetyON)
            ShowSafety();
        if (ErrorState)
        {
            SendCommand(WarnNow);
            if (ErrorState == CHECKSUMERROR)
            {
                SendText(Warning, err_chksm);
            }
            if (ErrorState == MODELSFILENOTFOUND)
            {
                SendText(Warning, err_404);
            }
        }
    }
    // not ko

    initADC();
    FHSS_data::PaceMaker = PACEMAKER;
    RationaliseBuddy();

    WarnUserIfBuddyBoxIsOn();
    ClearMostParameters();
    DelayWithDog(500);
    GotoFrontView();
    RedLedOn();
    ClockMessageTick(); // V2 B30/B62/B63: a clock that did not answer, said once - but not while new firmware is on trial (below)
    CentreNotePending = true; // B126: a Rotorflight model's cyclic and tail at stick centre, bank by bank
    CentreNoteTick();
    TXBuildAge = GetBuildDaysSince2020(); // days since 1st Jan 2020 for this build
    Look(BUILD_ID_STR);
    Look(TXBuildAge);
}
// **************************************************************************************************************************************************************
void RationaliseBuddy()
{
    PupilIsAlive = 0;
    MasterIsAlive = 0;
    CurrentMode = NORMAL;
    WirelessBuddy = true;

    if (!BuddyPupilOnWireless && !BuddyMasterOnWireless)
        WirelessBuddy = false;

    if (WasBuddyPupilOnWireless && !BuddyPupilOnWireless)
    {                     // Pupil has just gone off buddy mode
        ConfigureRadio(); // Very like InitRadio but without Radio1.begin() !
        WasBuddyPupilOnWireless = false;
        DontChangePipeAddress = false;
    }

    if (BuddyPupilOnWireless)
    {
        CurrentMode = LISTENMODE; // set the mode to listen only
        ModelMatched = false;
        BoundFlag = false;
        Connected = false;
        StartBuddyListen();
    }
    if (BuddyMasterOnWireless)
    {
        FHSS_data::PaceMaker = PACEMAKER_BUDDY;
        LinkRatesToBanks = true;
    }
}
/*********************************************************************************************************************************/
void GetFrameRate()
{
    CRUMB(CRUMB_FRAMERATE); // This function calculates the frame rate and the average frame rate
    if (RecentGoodPacketsCount)
        PacketsPerSecond = RecentGoodPacketsCount;
    RecentGoodPacketsCount = 0;
    TotalFrameRate += PacketsPerSecond;
    AverageFrameRate = TotalFrameRate / ++FrameRateCounter;
    if (CurrentView == FRONTVIEW && LedWasGreen)
    { // V1B B26: the front screen's "Frame rate" box (Malcolm, 4-10-2026). The front page has no such box: the 5-inch
      // screen keeps the value all the same, and its own front screen reads it. Once a second, while a model is connected.
        char pps[] = "pps";
        SendValue(pps, PacketsPerSecond);
    }
    // Look(TXBuildAge); // days since 1st Jan 2020 for this build
}

/*********************************************************************************************************************************/
/** @returns position of text1 within text2 or 0 if not found */
int InStrng(char *text1, char *text2)
{
    for (uint16_t j = 0; j < strlen(text2); ++j)
    {
        bool flag = false;
        for (uint16_t i = 0; i < strlen(text1); ++i)
        {
            if (text1[i] != text2[i + j])
            {
                flag = true;
                break;
            }
        }
        if (!flag)
            return j + 1; // Found match
    }
    return 0; // Found no match
}

/***********************************************************************************************************/

int GetDateAsInt(int f)
{ // dates are in format 23-08-24.LOG ie 23rd August '24
  // DateInt is 23 + (8 * 31)  + (24 * 31 * 12) =  23 + 248 + 8768 = 9019
    int DateInt = 0;
    char Date[10];
    for (int i = 0; i < 2; ++i)
        Date[i] = TheFilesList[f][i];
    Date[2] = 0;
    DateInt = atoi(Date); // the DAY
    for (int i = 3; i < 5; ++i)
        Date[i - 3] = TheFilesList[f][i];
    Date[2] = 0;
    DateInt += atoi(Date) * 31; // the MONTH
    for (int i = 6; i < 8; ++i)
        Date[i - 6] = TheFilesList[f][i];
    Date[2] = 0;
    DateInt += atoi(Date) * 31 * 12; // the YEAR
    return DateInt;
}

/***********************************************************************************************************/
void SortByDateInDescendingOrder()
{
    int f = 0;
    bool flag = true;
    int Scount = 0;
    char TempArray[18];
    int d1, d2;
    while (flag && Scount < 10000)
    {
        flag = false;
        for (f = 0; f < ExportedFileCounter - 1; ++f)
        {
            d1 = GetDateAsInt(f);
            d2 = GetDateAsInt(f + 1);
            if (d1 < d2)
            { // Sort by date in descending order so recent log files are at the top
                strcpy(TempArray, TheFilesList[f]);
                strcpy(TheFilesList[f], TheFilesList[f + 1]);
                strcpy(TheFilesList[f + 1], TempArray);
                flag = true;
                ++Scount;
            }
        }
    }
}
/****************************************************************************************************************************/

/** Bubble sort */
void SortDirectory() // Bubble sort for alphabetising the files. Not ideal for dates but OK for names.
                     // TODO: Make a version that sorts by date in reverse order
{
    int f = 0;
    bool flag = true;
    int Scount = 0;
    char TempArray[18];

    if (strcmp(MOD, ".LOG") == 0)
    { // if it's a log file, sort by date in descending order
        SortByDateInDescendingOrder();
        return;
    }

    while (flag && Scount < 10000)
    {
        flag = false;
        for (f = 0; f < ExportedFileCounter - 1; ++f)
        {
            if (strcmp(TheFilesList[f], TheFilesList[f + 1]) > 0)
            {
                strcpy(TempArray, TheFilesList[f]);
                strcpy(TheFilesList[f], TheFilesList[f + 1]);
                strcpy(TheFilesList[f + 1], TempArray);
                flag = true;
                ++Scount;
            }
        }
    }
}

/*********************************************************************************************************************************/
/** @brief Discover which channel to setup */
int GetChannel()
{
    unsigned int i;
    for (i = 0; i < sizeof(TextIn); ++i)
    {
        if (isdigit(TextIn[i]))
            break;
    }
    return atoi(&TextIn[i]);
}

/*********************************************************************************************************************************/

void ShowSwitchNameWithReversed(char *Sw, uint8_t n, char *text)
{ // this removes the R from switch name if it's not reversed

    char NotReversed[30] = " ";
    if (n >= 1 && n <= 8 && SwitchReversed[n - 1]) // (B32: eight switches)
    {
        SendText(Sw, text);
        return;
    }
    for (uint8_t i = 0; i < strlen(text) - 1; ++i)
        NotReversed[i] = text[i];

    if (n >= 1 && n <= 8 && !SwitchReversed[n - 1])
    {
        SendText(Sw, NotReversed);
        return;
    }
}

/*********************************************************************************************************************************/

// B39 (Malcolm: "it is possible that channel 5, 6, 7 or 8 might have been renamed flaps or gear. In which case, let's display
// that instead"): a channel's label on the switch pages is its name if the pilot has renamed it, else "Channel N". The
// names a model starts with ("Ch 5", "AUX1", and the old "Gear" of channel 5) count as not renamed.
static bool ChannelRenamed(uint8_t ch) // ch 1-16
{
    char name[12], generic[12];
    uint8_t j = 0;
    for (uint8_t i = 0; ChannelNames[ch - 1][i] && j < 11; ++i)
        if (ChannelNames[ch - 1][i] != ' ')
            name[j++] = (char)tolower((unsigned char)ChannelNames[ch - 1][i]);
    name[j] = 0;
    if (!name[0])
        return false;
    snprintf(generic, sizeof(generic), "ch%u", (unsigned)ch);
    if (!strcmp(name, generic))
        return false;
    snprintf(generic, sizeof(generic), "channel%u", (unsigned)ch);
    if (!strcmp(name, generic))
        return false;
    if (!strncmp(name, "aux", 3))
        return false;
    if (ch == 5 && !strcmp(name, "gear"))
        return false;
    return true;
}
static void ChannelLabel(uint8_t ch, char *out, size_t size) // "Flaps", or "Channel 6"
{
    if (ChannelRenamed(ch))
        snprintf(out, size, "%s", ChannelNames[ch - 1]);
    else
        snprintf(out, size, "Channel %u", (unsigned)ch);
}

void DoOneSwitch(char *Sw, uint8_t n)
{
    char NotUsed[] = "Not used         ";
    char Banks123[] = "Banks 1 2 3  R";
    char Auto[] = "Bank 4 & Motor  R";
    char Safety_Switch[] = "Safety  R";
    char Buddy_Switch[] = "Buddy  R";
    char DualRates_Switch[] = "Rates  R";

    SendText(Sw, NotUsed);

    if (Autoswitch == n)
    {
        ShowSwitchNameWithReversed(Sw, n, Auto);
        return;
    }
    if (BankSwitch == n)
    {
        ShowSwitchNameWithReversed(Sw, n, Banks123);
        return;
    }
    for (uint8_t d = 0; d < SWITCH_INPUTS; ++d) // B33: "<channel name> (Ch N) R", N = 5..16
    {
        if (TopChannelSwitch[d] != n)
            continue;
        char c[32], label[16];
        ChannelLabel((uint8_t)(d + 5), label, sizeof(label)); // (B34: by number; B39: or its name, if the pilot has renamed it)
        snprintf(c, sizeof(c), "%s  R", label);
        ShowSwitchNameWithReversed(Sw, n, c);
        return;
    }
    if (SafetySwitch == n)
    {
        ShowSwitchNameWithReversed(Sw, n, Safety_Switch);
        return;
    }
    if (DualRatesSwitch == n)
    {
        ShowSwitchNameWithReversed(Sw, n, DualRates_Switch);
        return;
    }
    if (BuddySwitch == n)
    {
        ShowSwitchNameWithReversed(Sw, n, Buddy_Switch);
        return;
    }
    if (FrontSwitchIsDefault(n)) // B38: a front switch with no job is its channel's input, and says so
    {
        char c[32], label[16];
        ChannelLabel(n, label, sizeof(label));
        snprintf(c, sizeof(c), "%s  R", label);
        ShowSwitchNameWithReversed(Sw, n, c);
    }
}

/*********************************************************************************************************************************/

void UpdateSwitchesView()
{ // now optimised! (B32: eight switches - the top edge's four and the front four)
    char sw[8][4] = {"sw1", "sw2", "sw3", "sw4", "sw5", "sw6", "sw7", "sw8"};
    for (int i = 1; i <= 8; ++i)
        DoOneSwitch(sw[i - 1], i);
    ShowSwitchPositions();
}

/*********************************************************************************************************************************/
// B32: beside each switch on the Switches page, where it is now: up, mid or down (the front four are told apart by moving them).
// Sent only when a position changes, a few times a second at most.
void ShowSwitchPositions()
{
    static uint8_t shown[8] = {9, 9, 9, 9, 9, 9, 9, 9};
    static uint32_t last = 0;
    static const char *words[4] = {"", "away", "mid", "near"}; // (B37: position 3 is near, towards you; 1 is away)
    char p[8][3] = {"p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"};
    if (CurrentView != SWITCHES_VIEW)
    {
        for (uint8_t i = 0; i < 8; ++i)
            shown[i] = 9; // (shown afresh when the page comes back)
        return;
    }
    if (millis() - last < 150)
        return;
    last = millis();
    for (uint8_t i = 1; i <= 8; ++i)
    {
        uint8_t pos = GetSwitchPosition(i);
        if (pos > 3)
            pos = 0;
        if (pos == shown[i - 1])
            continue;
        shown[i - 1] = pos;
        SendText(p[i - 1], (char *)words[pos]);
    }
}

/*********************************************************************************************************************************/
int CheckRange(int v, int min, int max)
{
    if (v > max)
        v = max;
    if (v < min)
        v = min;
    return v;
}
/*********************************************************************************************************************************/

void DoNewChannelName(int ch, int k)
{
    int j = 0;
    if (ch < 1 || ch > 16)
        return; // ChannelNames is [16][11]
    ChannelNames[ch - 1][0] = 32;
    ChannelNames[ch - 1][1] = 0;             // remove old name
    while (uint8_t(TextIn[k]) > 0 && j < 10) // ClaudeFix-2-7-2026 names are 10 chars max -- longer input overflowed into the next name (channel 16: past the array)
    {
        ChannelNames[ch - 1][j] = TextIn[k];
        ++j;
        ++k;
        ChannelNames[ch - 1][j] = 0;
    }
    SaveOneModel(ModelNumber);
}

/*********************************************************************************************************************************/

/** @brief updates display in textbox */
void ShowFileNumber()
{
    char dflt[] = "DEFAULT.MOD";
    char ModelsView_filename[] = "filename";
    char newfname[27];

    strcpy(newfname, dflt);
    if (FileNumberInView >= ExportedFileCounter)
        FileNumberInView = 0;
    if (FileNumberInView < 0)
        FileNumberInView = ExportedFileCounter - 1;
    if (ExportedFileCounter)
    {
        for (int i = 0; i < 12; ++i)
        {
            newfname[i] = TheFilesList[FileNumberInView][i];
            newfname[i + 1] = 0;
            if (newfname[i] <= 32 || newfname[i] > 127)
                break;
        }
    }
    SendText(ModelsView_filename, newfname);
}

/*********************************************************************************************************************************/

void ShowFileErrorMsg()
{
    char ErrorOn[] = "vis error,1";
    char ErrorOff[] = "vis error,0";
    for (int pp = 0; pp < 3; ++pp)
    {
        SendCommand(ErrorOn);
        DelayWithDog(200);
        SendCommand(ErrorOff);
        DelayWithDog(100);
    }
    FileError = false;
}

/*********************************************************************************************************************************/

// This function takes account of the fact one gimbal is upside down ... and some people use mode 2.
// Aileron is always reversed, plus either throttle or elevator according to mode 1 or 2
// It reverses some pins

int AnalogueReed(uint8_t InputChannel)
{

    int value = adc->analogRead(AnalogueInput[InputChannel]); //
    if (SticksMode == 2)
    {
        if ((InputChannel == 0) || (InputChannel == 2))
        {
            value = map(value, ChannelMin[InputChannel], ChannelMax[InputChannel], ChannelMax[InputChannel], ChannelMin[InputChannel]);
        }
    }
    else
    {
        if ((InputChannel == 0) || (InputChannel == 1))
        {
            value = map(value, ChannelMin[InputChannel], ChannelMax[InputChannel], ChannelMax[InputChannel], ChannelMin[InputChannel]);
        }
    }
    return value;
}

/*********************************************************************************************************************************/

FLASHMEM void SetDefaultValues(bool Calibrating) // B16: the calibration branch only when a calibration starts (Reset transmitter ran from the Calibrate page and took it)
{
    uint16_t j = 0;
    uint16_t i = 0;
    char empty[33] = "Not in use";

    CloseModelsFile();
    OpenModelsFile();

    while ((empty[i]) && (i < 29))
    {
        ModelName[i] = empty[i];
        ModelName[i + 1] = 0;
        ++i;
    }

    char DefaultChannelNames[CHANNELSUSED][11] = {{"Aileron"}, {"Elevator"}, {"Throttle"}, {"Rudder"}, {"Ch 5"}, {"Ch 6"}, {"Ch 7"}, {"Ch 8"}, {"Ch 9"}, {"Ch 10"}, {"Ch 11"}, {"Ch 12"}, {"Ch 13"}, {"Ch 14"}, {"Ch 15"}, {"Ch 16"}};

    for (i = 0; i < CHANNELSUSED; ++i)
    {
        CurvePointCount[i] = 5; // (B118: five points, as ever)
        for (j = 1; j <= BANKS_USED; ++j) // (B131: banks 5 and 6 too)
            CurveSetStraight(j, i, 30, 150); // 30, 60, 90, 120, 150
    }
    MaxRangeNarrow = 0; // B113: 500 to 2500, as ever

    for (j = 0; j < MAXMIXES; ++j)
    {
        for (i = 0; i < CHANNELSUSED; ++i)
        {
            Mixes[j][i] = 0;
        }
    }

    for (j = 0; j < BANKS_USED + 1; ++j)
    { // must have fudged this somewhere.... Probably 1-5 instead of 0-4
        for (i = 0; i < CHANNELSUSED; ++i)
        {
            Trims[j][i] = 80; // MIDPOINT is 80 !
        }
    }
    RXCellCount = 3;

    for (i = 0; i < CHANNELSUSED; ++i)
    {
        InPutStick[i] = i;
        ChannelOutPut[i] = i;
    }

    for (i = 0; i < CHANNELSUSED; ++i)
    {
        FailSafeChannel[i] = false;
    }

    for (i = 0; i < CHANNELSUSED; ++i)
    {
        for (j = 0; j < 10; ++j)
        {
            ChannelNames[i][j] = DefaultChannelNames[i][j];
        }
    }
    for (j = 1; j <= BANKS_USED; ++j)
    {
        for (i = 0; i < CHANNELSUSED; ++i)
        {
            Exponential[j][i] = DEFAULT_EXPO; // 0% (50) expo = default
        }
    }
    for (j = 1; j <= BANKS_USED; ++j) // ClaudeFix-2-7-2026 banks are 1-based at runtime (matches the Exponential loop above); 0..3 left bank 4 inheriting the previous model's curve types
    {
        for (i = 0; i < CHANNELSUSED; ++i)
        {
            InterpolationTypes[j][i] = EXPONENTIALCURVES; // Expo is default
        }
    }
    for (i = 0; i < CHANNELSUSED; ++i)
    {
        SubTrims[i] = 127; // centre (0 - 254)
    }
    for (j = 0; j < BYTESPERMACRO; ++j)
    {
        for (i = 0; i < MAXMACROS; ++i)
        {
            MacrosBuffer[i][j] = 0;
        }
    }
    for (int i = 0; i < 4; ++i)
    {
        InputTrim[i] = i;
    }

    if (Calibrating)
    {
        UseMotorKill = false;
        MotorChannelZero = 50;
        MotorChannel = 15;
    }
    else
    {
        UseMotorKill = true;
        MotorChannelZero = 30;
        MotorChannel = 2;
    }

    ReversedChannelBITS = 0; //  No channel reversed
    RxVoltageCorrection = 0;
    ModelsMacUnionSaved.Val64 = 0;
    UseDualRates = false;
    Drate1 = 100;
    Drate2 = 75;
    Drate3 = 50;
    DualRateChannels[0] = 1;
    DualRateChannels[1] = 2;
    DualRateChannels[2] = 4;
    DualRateChannels[3] = 0;
    DualRateChannels[4] = 0;
    DualRateChannels[5] = 0;
    DualRateChannels[6] = 0;
    DualRateChannels[7] = 0;

    for (int i = 0; i < BANKS_USED; ++i)
    {
        BanksInUse[i] = i < 4 ? i + 4 : 30 + i; // "Bank 1" .. "Bank 4"; B130: "Bank 5", "Bank 6" (34, 35)
    }
    SixBanks = false; // B130: four banks until Model options says six
    for (int j = 0; j <= BANKS_USED; ++j)
    {
        for (int i = 0; i < 16; ++i)
        {
            ServoSpeed[j][i] = 100;
        }
    }
    for (i = 0; i < BANKS_USED; ++i)
    {
        DualRateRate[i] = 0;
    }
    TrimMultiplier = 5;
    for (int i = 0; i < 11; ++i)
    {
        ServoFrequency[i] = 50;
        ServoCentrePulse[i] = 1500;
    }
    ArmingChannel = 6; // for Rotorflight
    RotorFlight_V = 0;        // B06: not a Rotorflight model until it is set up as one (a reused or reset slot kept the old flag)
    LinkRatesToBanks = false; // B06
    GearRatio = 10.3;  // for helicopters with swash plates. This is the ratio between servo movement and blade pitch change. 10.3 is a typical value for a 700 size heli
    for (j = 0; j < 4; ++j)
    {
        for (i = 0; i < MAX_PID_WORDS + 5; ++i)
            Saved_PID_Values[i][j] = 0;
        for (i = 0; i < MAX_RATES_BYTES; ++i)
            Saved_Rate_Values[i][j] = 0;
        for (i = 0; i < MAX_RATES_ADVANCED_BYTES; ++i)
            Saved_Rate_Advanced_Values[i][j] = 0;
        for (i = 0; i < MAX_PIDS_ADVANCED_BYTES; ++i)
            Saved_PID_Advanced_Values[i][j] = 0;
    }
    strcpy(ModelImageFileName, "Noimage");
    ShowModelImage();
    ModelDefined = 42;
}

/*********************************************************************************************************************************/

/** @brief Uses servo degrees to position dots */
FASTRUN void GetDotPositions()
{ // where the points sit on the glass: across the box in equal steps (B118: 180, 90, 60 or 45 pixels for 3, 5, 7 or 9), up by degrees
    const uint8_t ch = ChanneltoSet - 1, n = CurveN(ch);
    for (uint8_t k = 0; k < n; ++k)
    {
        xPoints[k] = BOXLEFT + (360 * k) / (n - 1);
        const int p = map(CurvePoint[Bank][ch][k], 0, 180, BOXWIDTH, BOXLEFT);
        yPoints[k] = constrain(p, 39, 391);
    }
}

/*********************************************************************************************************************************/

FLASHMEM static void GraphCmd(char *Buffer, const char *Cmd)
{ // appends a command and its end marker, sending the buffer first when the command would not fit
    if (strlen(Buffer) + strlen(Cmd) + 3 >= 500)
    {
        NEXTION.print(Buffer);
        Buffer[0] = 0;
    }
    strcat(Buffer, Cmd);
    strcat(Buffer, "\xFF\xFF\xFF");
}
FASTRUN void updateInterpolationTypes()
{
    char ExpR[] = "Exp";
    char Smooth[] = "Smooth";
    char Lines[] = "Lines";
    char Expon[] = "Expo";          // number display
    char Ex1[] = "Ex1";             // slider
    char t3on[] = "vis t3,1";       // expo value lable
    char b13on[] = "vis b13,1";     // expo -
    char b12on[] = "vis b12,1";     // expo +
    char ExponOn[] = "vis Expo,1";  // number display
    char Ex1On[] = "vis Ex1,1";     // slider
    char t3off[] = "vis t3,0";      // expo value lable
    char b13off[] = "vis b13,0";    // expo -
    char b12off[] = "vis b12,0";    // expo +
    char ExponOff[] = "vis Expo,0"; // number display
    char Ex1Off[] = "vis Ex1,0";    // slider

    switch (InterpolationTypes[Bank][ChanneltoSet - 1])
    {
    case STRAIGHTLINES:
        SendValue(Lines, 1);
        SendValue(Smooth, 0);
        SendValue(ExpR, 0);
        SendCommand(t3off);
        SendCommand(b13off);
        SendCommand(b12off);
        SendCommand(ExponOff);
        SendCommand(Ex1Off);
        break;
    case SMOOTHEDCURVES:
        SendValue(Lines, 0);
        SendValue(Smooth, 1);
        SendValue(ExpR, 0);
        SendCommand(t3off);
        SendCommand(b13off);
        SendCommand(b12off);
        SendCommand(ExponOff);
        SendCommand(Ex1Off);
        break;
    case EXPONENTIALCURVES:
        SendValue(Lines, 0);
        SendValue(Smooth, 0);
        SendValue(ExpR, 1);
        SendCommand(t3on);
        SendCommand(b13on);
        SendCommand(b12on);
        SendCommand(ExponOn);
        SendCommand(Ex1On);
        SendValue(Ex1, (Exponential[Bank][ChanneltoSet - 1]));        // The slider
        SendValue(Expon, (Exponential[Bank][ChanneltoSet - 1]) - 50); // the number
        break;
    default:
        break;
    }
    { // B118: the Points row (3 5 7 9) shows with Straight and Smooth, where the Expo controls are otherwise
        static const char *const PTS[9] = {"lpt", "pt3", "lpt3", "pt5", "lpt5", "pt7", "lpt7", "pt9", "lpt9"};
        const bool pts = InterpolationTypes[Bank][ChanneltoSet - 1] != EXPONENTIALCURVES;
        char Buffer[512] = "", Cmd[24];
        for (uint8_t i = 0; i < 9; ++i)
        {
            snprintf(Cmd, sizeof(Cmd), "vis %s,%d", PTS[i], pts ? 1 : 0);
            GraphCmd(Buffer, Cmd);
        }
        NEXTION.print(Buffer);
    }
}

/*********************************************************************************************************************************/

// B118 (Malcolm, 17 Oct 2026: "Might it be possible for us now to allow the user to choose 3 points, 5 points, 7 points, or 9
// points?"). A channel's curve has CurveN(ch) points, the same in every bank; five as ever. Changing the count puts the new
// points ON the curve as it is, bank by bank (the shape's own interpolation at the new stick positions), so nothing moves:
// the ends and the centre are copied, never re-rounded; Exponential has only those three anyway.
FLASHMEM static void CurveResample(uint8_t ch, uint8_t n)
{
    const uint8_t was = CurveN(ch), in = InPutStick[ch], SavedBank = Bank;
    for (uint8_t b = 1; b <= BANKS_USED; ++b) // (B130: banks 5 and 6 too, used or not: the count is the same in every bank)
    {
        uint8_t fresh[CURVE_POINTS_MAX];
        Bank = b;
        GetCurveDots(ch, 100); // this bank's points at full rate (CurveDots, CurveDotsN = was)
        const uint8_t it = InterpolationTypes[b][ch] < 3 ? InterpolationTypes[b][ch] : 0;
        for (uint8_t k = 0; k < CURVE_POINTS_MAX; ++k)
        {
            if (k >= n)
                fresh[k] = 0;
            else if (CurveStore[b][ch][CurveStorePos(n, k)] != CURVE_UNSET)
                fresh[k] = CurveStore[b][ch][CurveStorePos(n, k)]; // B121: its height as it was left
            else if (k == 0)
                fresh[k] = CurvePoint[b][ch][0];
            else if (k == CurveMid(n))
                fresh[k] = CurvePoint[b][ch][CurveMid(was)];
            else if (k == n - 1)
                fresh[k] = CurvePoint[b][ch][was - 1];
            else
                fresh[k] = RangeDegrees(Interpolate[it](CurveX(in, k, n), in, ch), RangeLo(), RangeHi());
        }
        for (uint8_t k = 0; k < CURVE_POINTS_MAX; ++k)
            CurvePoint[b][ch][k] = fresh[k];
    }
    Bank = SavedBank;
    CurvePointCount[ch] = n;
    for (uint8_t b = 1; b <= BANKS_USED; ++b)
        CurveStoreSync(b, ch);           // B121: the new count's points remembered (the never-set ones just placed)
    GetCurveDots(ch, DualRateValue); // (the dots are a global: the bank in use back)
}
FLASHMEM void CurvePointsChosen(uint8_t n)
{
    if (ChanneltoSet < 1 || ChanneltoSet > 16)
        return;
    if (n != CurveN(ChanneltoSet - 1))
    {
        CurveResample(ChanneltoSet - 1, n);
        if (CurrentPoint > n)
            CurrentPoint = 1;
        CheckInvisiblePoint();
        SaveOneModel(ModelNumber);
    }
    DisplayCurve(); // (the radios as they are, either way)
    ClearText();
}
FLASHMEM void CurvePoints3Tapped() { CurvePointsChosen(3); }
FLASHMEM void CurvePoints5Tapped() { CurvePointsChosen(5); }
FLASHMEM void CurvePoints7Tapped() { CurvePointsChosen(7); }
FLASHMEM void CurvePoints9Tapped() { CurvePointsChosen(9); }
// B135 (Malcolm, 20 Oct 2026): two more buttons on the curve page. "Reset ... should put expo to zero and put all points onto
// a straight line (x=y) as though it had never been edited": this bank's curve for the channel as a new model has it - every
// point on the line from bottom left to top right (0 .. 180 degrees, whatever the count, nothing remembered for the other
// counts), no expo; the shape and the count stay as chosen. "Flat ... should take the height of the currently selected point
// and adjust all others to the same height creating a flat horizontal line": every point the ringed point's height (a governed
// throttle at full, for instance). Neither is saved until OK, like a moved point; with Copy to all banks on, OK copies it.
FLASHMEM void CurveResetTapped()
{
    if (ChanneltoSet < 1 || ChanneltoSet > 16)
        return;
    CurveSetStraight(Bank, ChanneltoSet - 1, 0, 180);
    Exponential[Bank][ChanneltoSet - 1] = DEFAULT_EXPO;
    DisplayCurveAndServoPos(); // (updateInterpolationTypes puts the slider and its number at 0)
}
FLASHMEM void CurveFlatTapped()
{
    if (ChanneltoSet < 1 || ChanneltoSet > 16)
        return;
    CheckInvisiblePoint(); // (the ring is always on a point that is shown; this makes sure)
    const uint8_t h = CurvePoint[Bank][ChanneltoSet - 1][CurrentPoint - 1];
    CurveSetStraight(Bank, ChanneltoSet - 1, h, h);
    DisplayCurveAndServoPos();
}
// The numbers along the top of the curve page: which boxes show them (n1-n5 for 3 and 5 points - 3 uses n1, n3, n5, as an
// exponential curve does; n1 k2 k3 n3 k5 k6 n5 for 7; m1-m9, smaller, for 9), their values in microseconds, and the Points
// radios. One write.
FLASHMEM void CurveLayoutShow()
{
    static const char *const ALL[18] = {"n1", "n2", "n3", "n4", "n5", "k2", "k3", "k5", "k6", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9"};
    static const char *const N3[3] = {"n1", "n3", "n5"};
    static const char *const N5[5] = {"n1", "n2", "n3", "n4", "n5"};
    static const char *const N7[7] = {"n1", "k2", "k3", "n3", "k5", "k6", "n5"};
    static const char *const N9[9] = {"m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9"};
    if (ChanneltoSet < 1 || ChanneltoSet > 16)
        return;
    const uint8_t ch = ChanneltoSet - 1, n = CurveN(ch);
    const bool expo = InterpolationTypes[Bank][ch] == EXPONENTIALCURVES;
    const uint8_t shown = expo ? 3 : n;
    const char *const *names = shown == 3 ? N3 : shown == 7 ? N7 : shown == 9 ? N9 : N5;
    char Buffer[512] = "", Cmd[40];
    for (uint8_t i = 0; i < 18; ++i)
    {
        bool on = false;
        for (uint8_t k = 0; k < shown; ++k)
            if (!strcmp(names[k], ALL[i]))
                on = true;
        snprintf(Cmd, sizeof(Cmd), "vis %s,%d", ALL[i], on ? 1 : 0);
        GraphCmd(Buffer, Cmd);
    }
    for (uint8_t k = 0; k < shown; ++k)
    {
        const uint8_t idx = expo ? (k == 0 ? 0 : k == 1 ? CurveMid(n) : n - 1) : k;
        snprintf(Cmd, sizeof(Cmd), "%s.val=%d", names[k], CurveMicros(CurvePoint[Bank][ch][idx]));
        GraphCmd(Buffer, Cmd);
    }
    // B150 (Malcolm, 27 Oct 2026: "my arithmetic is not very good when I'm trying to make a symmetrical curve ... it's
    // not immediately obvious when the distance above the centre and below the centre are the same"): a point and its
    // twin across the centre that stand the same distance above and below the centre POINT show their two numbers in
    // green; the centre's number, and a point whose twin does not match, stay white. Judged in the degrees the points are
    // kept in (one press of + or - is one degree), so a matched pair may still show microseconds a unit apart: that is
    // the display's rounding (CurveMicros truncates), not the curve's.
    for (uint8_t k = 0; k < shown; ++k)
    {
        const uint8_t idx = expo ? (k == 0 ? 0 : k == 1 ? CurveMid(n) : n - 1) : k;
        const uint8_t mid = CurveMid(n);
        const bool matched = idx != mid && (int)CurvePoint[Bank][ch][idx] + (int)CurvePoint[Bank][ch][n - 1 - idx] == 2 * (int)CurvePoint[Bank][ch][mid];
        snprintf(Cmd, sizeof(Cmd), "%s.pco=%u", names[k], matched ? 2016u : 65535u); // (green, white: the page's own)
        GraphCmd(Buffer, Cmd);
    }
    snprintf(Cmd, sizeof(Cmd), "pt3.val=%d", n == 3 ? 1 : 0);
    GraphCmd(Buffer, Cmd);
    snprintf(Cmd, sizeof(Cmd), "pt5.val=%d", n == 5 ? 1 : 0);
    GraphCmd(Buffer, Cmd);
    snprintf(Cmd, sizeof(Cmd), "pt7.val=%d", n == 7 ? 1 : 0);
    GraphCmd(Buffer, Cmd);
    snprintf(Cmd, sizeof(Cmd), "pt9.val=%d", n == 9 ? 1 : 0);
    GraphCmd(Buffer, Cmd);
    if (Buffer[0])
        NEXTION.print(Buffer);
}

/*********************************************************************************************************************************/

// B117 (Malcolm, 17 Oct 2026: "as I move the stick the line moves in occasional jumps"). The curve is a run of line
// commands; here they are worked out once, in the order and with the arithmetic DisplayCurve has always used, so that the
// stick's marker can be moved by redrawing only the segments through the column it covered (GraphMarkerMove) instead of
// the whole curve. Each segment is the command "line x1,y1,x2,y2": for the smoothed and exponential curves (x1,y1) is
// the newer point and (x2,y2) the one before it, as it was always drawn. Returns how many there are.
FLASHMEM uint8_t CurveSegments(int16_t *x1, int16_t *y1, int16_t *x2, int16_t *y2)
{
    uint8_t n = 0;
    int xDot1, yDot1, xDot2 = 0, yDot2 = 0;
    double xPoint, yPoint;
    const uint8_t pts = CurveN(ChanneltoSet - 1), mid = CurveMid(pts), last = pts - 1; // (B118: 3, 5, 7 or 9 points)
    if (InterpolationTypes[Bank][ChanneltoSet - 1] == STRAIGHTLINES)
    { // straight lines, point to point
        for (int i = 0; i < last; ++i)
        {
            x1[n] = (int)xPoints[i];
            y1[n] = (int)yPoints[i];
            x2[n] = (int)xPoints[i + 1];
            y2[n] = (int)yPoints[i + 1];
            ++n;
        }
        return n;
    }
    if (InterpolationTypes[Bank][ChanneltoSet - 1] == SMOOTHEDCURVES)
    { // CatmullSpline: through every point exactly, with a vertex every 12 pixels or fewer between them. (B122: it was a vertex every
      // 12 pixels from the left end, so most points fell between two and the chord cut just inside them - a curve seen "going close
      // to the point but missing it by a small amount", Malcolm, 17 Oct 2026, with nine points and the kinks remembered heights can make.)
        int px = (int)xPoints[0], py = (int)yPoints[0];
        for (int i = 0; i < last; ++i)
        {
            const int xa = (int)xPoints[i], xb = (int)xPoints[i + 1];
            const int steps = xb > xa ? (xb - xa + 11) / 12 : 1;
            for (int s = 1; s <= steps; ++s)
            {
                const int x = xa + (xb - xa) * s / steps;
                const int y = s == steps ? (int)yPoints[i + 1] : (int)lround(Interpolation::CatmullSpline(xPoints, yPoints, pts, (double)x));
                if (n < CURVE_SEGMENTS_MAX)
                {
                    x1[n] = x;
                    y1[n] = y;
                    x2[n] = px;
                    y2[n] = py;
                    ++n;
                }
                px = x;
                py = y;
            }
        }
        return n;
    }
    // EXPONENTIALCURVES: the lower half from the left end to the centre, then the upper half from the right end back to the centre
    const float HalfXRange = xPoints[last] - xPoints[mid];
    const float TopHalfYRange = yPoints[last] - yPoints[mid];
    const float BottomHalfYRange = yPoints[mid] - yPoints[0];
    int adaptiveStep = 14;
    for (xPoint = 0; xPoint <= HalfXRange; xPoint += adaptiveStep)
    {
        yPoint = MapWithExponential(HalfXRange - xPoint, HalfXRange, 0, 0, BottomHalfYRange, Exponential[Bank][ChanneltoSet - 1]);
        if (adaptiveStep > HalfXRange - xPoint)
            adaptiveStep = HalfXRange - xPoint;
        if (adaptiveStep < 1)
            adaptiveStep = 1;
        yDot1 = yPoint + yPoints[0];
        xDot1 = xPoint + xPoints[0];
        if (yDot2 == 0)
        {
            xDot2 = xDot1;
            yDot2 = yDot1;
            continue;
        }
        if (n < CURVE_SEGMENTS_MAX)
        {
            x1[n] = xDot1;
            y1[n] = yDot1;
            x2[n] = xDot2;
            y2[n] = yDot2;
            ++n;
        }
        xDot2 = xDot1;
        yDot2 = yDot1;
    }
    adaptiveStep = 14;
    yDot2 = 0;
    for (xPoint = HalfXRange; xPoint >= 0; xPoint -= adaptiveStep)
    {
        yPoint = MapWithExponential(xPoint, 0, HalfXRange, 0, TopHalfYRange, Exponential[Bank][ChanneltoSet - 1]);
        if (adaptiveStep > xPoint)
            adaptiveStep = xPoint;
        if (adaptiveStep < 1)
            adaptiveStep = 1;
        yDot1 = yPoint + yPoints[mid];
        xDot1 = xPoint + xPoints[mid];
        if (yDot2 == 0)
        {
            xDot2 = xDot1;
            yDot2 = yDot1;
            continue;
        }
        if (n < CURVE_SEGMENTS_MAX)
        {
            x1[n] = xDot1;
            y1[n] = yDot1;
            x2[n] = xDot2;
            y2[n] = yDot2;
            ++n;
        }
        xDot2 = xDot1;
        yDot2 = yDot1;
    }
    return n;
}

/*********************************************************************************************************************************/

FLASHMEM void DisplayCurve()
{

    char cmdBuffer[512] = "";          // Buffer for commands
    char tempCmd[80];                  // Temporary buffer for individual commands
    char endMarker[] = "\xFF\xFF\xFF"; // Nextion end marker

    int xDot1;
    int yDot1;
    int xDot2 = 0;
    int yDot2 = 0;
    int DotSize = 4;
    int DotColour = 65535; // White

    // Constrain degrees values (B118: every point of the curve)
    for (uint8_t k = 0; k < CurveN(ChanneltoSet - 1); ++k)
        CurvePoint[Bank][ChanneltoSet - 1][k] = constrain(CurvePoint[Bank][ChanneltoSet - 1][k], 0, 180);

    GetDotPositions();

    // 1. First batch: Clear box and send top row values

    // Clear the box

    sprintf(tempCmd, "fill %d,%d,%d,%d,%d", 36, 36, 360, 360, 0);

    strcat(cmdBuffer, tempCmd);
    strcat(cmdBuffer, endMarker);

    // (B118: the numbers along the top, and which boxes show them, go at the end: CurveLayoutShow)

    // Send first batch of commands
    NEXTION.print(cmdBuffer);
    cmdBuffer[0] = '\0'; // Reset buffer

    // 2. Second batch: Draw box and reference lines

    // Draw the box
    sprintf(tempCmd, "draw %d,%d,%d,%d,%d", BOXLEFT, BOXTOP, BOXWIDTH, BOXHEIGHT, HighlightColour);
    strcat(cmdBuffer, tempCmd);
    strcat(cmdBuffer, endMarker);

    // Horizontal reference line
    xDot1 = xPoints[0];
    yDot1 = (BOXHEIGHT / 2) + 20;
    xDot2 = BOXWIDTH;
    yDot2 = yDot1;
    sprintf(tempCmd, "line %d,%d,%d,%d,%d", xDot1, yDot1, xDot2, yDot1, SpecialColour);
    strcat(cmdBuffer, tempCmd);
    strcat(cmdBuffer, endMarker);

    // Vertical reference line (B119: the box's centre, whatever the count - it was the third point, the centre of five only)
    xDot1 = BOXLEFT + 180;
    yDot1 = BOXTOP;
    xDot2 = xDot1;
    yDot2 = BOXHEIGHT;
    sprintf(tempCmd, "line %d,%d,%d,%d,%d", xDot1, yDot1, xDot2, yDot2, SpecialColour);
    strcat(cmdBuffer, tempCmd);
    strcat(cmdBuffer, endMarker);

    // Send the second batch of commands
    NEXTION.print(cmdBuffer);
    cmdBuffer[0] = '\0'; // Reset buffer

    // 4. Draw the curve: its segments (B117: CurveSegments - the same lines as always, worked out in one place)
    if (InterpolationTypes[Bank][ChanneltoSet - 1] == EXPONENTIALCURVES)
        CheckInvisiblePoint();
    {
        int16_t sx1[CURVE_SEGMENTS_MAX], sy1[CURVE_SEGMENTS_MAX], sx2[CURVE_SEGMENTS_MAX], sy2[CURVE_SEGMENTS_MAX];
        const uint8_t Segments = CurveSegments(sx1, sy1, sx2, sy2);
        for (uint8_t i = 0; i < Segments; ++i)
        {
            sprintf(tempCmd, "line %d,%d,%d,%d,%d", sx1[i], sy1[i], sx2[i], sy2[i], ForeGroundColour);
            strcat(cmdBuffer, tempCmd);
            strcat(cmdBuffer, endMarker);
            if (strlen(cmdBuffer) > 400)
            { // Send if buffer getting full
                NEXTION.print(cmdBuffer);
                cmdBuffer[0] = '\0';
            }
        }
    }

    // Send any remaining curve drawing commands
    if (strlen(cmdBuffer) > 0)
    {
        NEXTION.print(cmdBuffer);
        cmdBuffer[0] = '\0'; // Reset buffer
    }

    // 5. Draw the control points (dots)

    { // every point (B118: 3, 5, 7 or 9); an exponential curve shows its three: the ends and the centre
        const uint8_t pts = CurveN(ChanneltoSet - 1);
        for (uint8_t i = 0; i < pts; i++)
        {
            if (!CurveDotShown(i))
                continue;
            sprintf(tempCmd, "cirs %d,%d,%d,%d", (int)xPoints[i], (int)yPoints[i], DotSize, DotColour);
            strcat(cmdBuffer, tempCmd);
            strcat(cmdBuffer, endMarker);
            if (strlen(cmdBuffer) > 400)
            {
                NEXTION.print(cmdBuffer);
                cmdBuffer[0] = '\0';
            }
        }
    }

    // Send the dots batch
    NEXTION.print(cmdBuffer);
    cmdBuffer[0] = '\0'; // Reset buffer

    // Create a special command to highlight the selected point with a filled circle
    char fill_cmd[100];
    int selected_x = (int)xPoints[CurrentPoint - 1];
    int selected_y = (int)yPoints[CurrentPoint - 1];

    // Create a circular highlight with concentric circles
    // Draw a large outer circle with white color for visibility on any background
    sprintf(fill_cmd, "cirs %d,%d,%d,%d",
            selected_x, selected_y, 10, White);
    SendCommand(fill_cmd);

    // Draw a medium circle with highlight color
    sprintf(fill_cmd, "cirs %d,%d,%d,%d",
            selected_x, selected_y, 8, HighlightColour);
    SendCommand(fill_cmd);

    // Draw another inner circle with highlight color
    sprintf(fill_cmd, "cirs %d,%d,%d,%d",
            selected_x, selected_y, 6, HighlightColour);
    SendCommand(fill_cmd);

    // Then redraw the selected dot over the highlight in a contrasting color
    sprintf(fill_cmd, "cirs %d,%d,%d,%d",
            selected_x, selected_y, DotSize + 3, Black);
    SendCommand(fill_cmd);

    CurveLayoutShow();      // B118: the numbers along the top, in the boxes for this many points, and the Points radios
    SavedLineX = NO_MARKER; // B117: a full redraw has no marker on it; ShowServoPos draws it afresh (and then only moves it)

    // Update interpolation types UI
    updateInterpolationTypes();
}

/*********************************************************************************************************************************/
// B117. The stick's marker on the curve page (the vertical line) moves without redrawing the curve: the column it covered
// is painted black, what lay there is put back - the reference lines' pixels, the curve's segments through that column
// (the very line commands DisplayCurve sends, so the pixels are the same), any dot those segments pass through - and the
// marker is drawn at its new place. A dozen short commands in one write, where a full redraw was 1.5 kB and a flash of
// black, so the marker follows the stick smoothly (ShowServoPos, 25 times a second, a pixel at a time).
FLASHMEM void GraphMarkerMove(uint16_t From, uint16_t To)
{
    char Buffer[512] = "";
    char Cmd[80];
    GetDotPositions(); // B120: the dots' places afresh (xPoints/yPoints are globals: nothing may be trusted to have left them alone)
    if (From >= GRAPH_MARKER_FIRST && From <= GRAPH_MARKER_LAST)
    { // the old marker's column, then what it covered, in the order DisplayCurve draws
        snprintf(Cmd, sizeof(Cmd), "line %d,%d,%d,%d,%d", From, GRAPH_MARKER_TOP, From, GRAPH_MARKER_BOTTOM, Black);
        GraphCmd(Buffer, Cmd);
        const int RefY = (BOXHEIGHT / 2) + 20; // the horizontal reference line's pixel
        snprintf(Cmd, sizeof(Cmd), "line %d,%d,%d,%d,%d", From, RefY, From, RefY, SpecialColour);
        GraphCmd(Buffer, Cmd);
        if (From == BOXLEFT + 180)
        { // the vertical reference line (B119: the box's centre, as DisplayCurve draws it)
            snprintf(Cmd, sizeof(Cmd), "line %d,%d,%d,%d,%d", BOXLEFT + 180, BOXTOP, BOXLEFT + 180, BOXHEIGHT, SpecialColour);
            GraphCmd(Buffer, Cmd);
        }
        int16_t sx1[CURVE_SEGMENTS_MAX], sy1[CURVE_SEGMENTS_MAX], sx2[CURVE_SEGMENTS_MAX], sy2[CURVE_SEGMENTS_MAX];
        const uint8_t Segments = CurveSegments(sx1, sy1, sx2, sy2);
        int Left = From, Right = From; // how far the redrawn segments reach
        for (uint8_t i = 0; i < Segments; ++i)
        {
            const int lo = sx1[i] < sx2[i] ? sx1[i] : sx2[i], hi = sx1[i] < sx2[i] ? sx2[i] : sx1[i];
            if (lo <= From && From <= hi)
            {
                snprintf(Cmd, sizeof(Cmd), "line %d,%d,%d,%d,%d", sx1[i], sy1[i], sx2[i], sy2[i], ForeGroundColour);
                GraphCmd(Buffer, Cmd);
                if (lo < Left)
                    Left = lo;
                if (hi > Right)
                    Right = hi;
            }
        }
        for (int i = 0; i < CurveN(ChanneltoSet - 1); ++i)
        { // the dots those lines pass through, as DisplayCurve draws them (B118: 3, 5, 7 or 9; three for an exponential curve)
            if (!CurveDotShown(i))
                continue;
            const int dx = (int)xPoints[i];
            if (dx + 4 >= Left && dx - 4 <= Right)
            {
                snprintf(Cmd, sizeof(Cmd), "cirs %d,%d,%d,%d", dx, (int)yPoints[i], 4, White);
                GraphCmd(Buffer, Cmd);
            }
        }
        const int SelX = (int)xPoints[CurrentPoint - 1], SelY = (int)yPoints[CurrentPoint - 1];
        if (SelX + 10 >= Left && SelX - 10 <= Right)
        { // the chosen dot's rings
            snprintf(Cmd, sizeof(Cmd), "cirs %d,%d,%d,%d", SelX, SelY, 10, White);
            GraphCmd(Buffer, Cmd);
            snprintf(Cmd, sizeof(Cmd), "cirs %d,%d,%d,%d", SelX, SelY, 8, HighlightColour);
            GraphCmd(Buffer, Cmd);
            snprintf(Cmd, sizeof(Cmd), "cirs %d,%d,%d,%d", SelX, SelY, 6, HighlightColour);
            GraphCmd(Buffer, Cmd);
            snprintf(Cmd, sizeof(Cmd), "cirs %d,%d,%d,%d", SelX, SelY, 7, Black);
            GraphCmd(Buffer, Cmd);
        }
    }
    if (To >= GRAPH_MARKER_FIRST && To <= GRAPH_MARKER_LAST)
    {
        snprintf(Cmd, sizeof(Cmd), "line %d,%d,%d,%d,%d", To, GRAPH_MARKER_TOP, To, GRAPH_MARKER_BOTTOM, HighlightColour);
        GraphCmd(Buffer, Cmd);
    }
    if (Buffer[0])
        NEXTION.print(Buffer);
}

/*********************************************************************************************************************************/

void BindNow()
{
    BoundFlag = true;
    ModelMatched = true;
    // Connected = true;
    if (CurrentView == FRONTVIEW)
    {
        ShowModelImage(); // (no question to the screen: a model just back after a lost link must not wait for one)
    }
    else
    {
        GotoFrontView();
    }
#ifdef DB_BIND
    Serial.println("");
    Serial.println("Remote (model) ID saved:");
    for (int i = 0; i < 6; ++i)
    {
        Serial.print(ModelsMacUnionSaved.Val8[i], HEX);
        Serial.print(" ");
    }
    Serial.println(" ");
    Serial.println("(All 6 bytes of Teensy MAC ID used without modification.) ");
#endif
}

/*********************************************************************************************************************************/
int GetDifference(int YtouchPlace, int oldy)
{
    int dd;
    dd = (YtouchPlace - oldy) / 2;
    if (dd < 0)
        dd = -dd;
    return dd;
}
/*********************************************************************************************************************************/
void MoveCurrentPointUp()
{ // (B118: the current point of up to nine)
    if (CurrentPoint >= 1 && CurrentPoint <= CurveN(ChanneltoSet - 1) && CurvePoint[Bank][ChanneltoSet - 1][CurrentPoint - 1] < 180)
        ++CurvePoint[Bank][ChanneltoSet - 1][CurrentPoint - 1];
    CurveStoreSync(Bank, ChanneltoSet - 1); // (B121: remembered)
    DisplayCurve();
}

/*********************************************************************************************************************************/
void MoveCurrentPointDown()
{
    if (CurrentPoint >= 1 && CurrentPoint <= CurveN(ChanneltoSet - 1) && CurvePoint[Bank][ChanneltoSet - 1][CurrentPoint - 1])
        --CurvePoint[Bank][ChanneltoSet - 1][CurrentPoint - 1];
    CurveStoreSync(Bank, ChanneltoSet - 1); // (B121: remembered)
    DisplayCurve();
}

/*********************************************************************************************************************************/

/** @brief moves point very close to where user hit screen */
void MovePoint()
{ // the point nearest the finger across the box (of those shown) becomes the current one and moves to the finger's height (B118: any count)
    GetDotPositions(); // current
    if (XtouchPlace > BOXWIDTH)
        return; // out of range
    if (XtouchPlace < BOXLEFT)
        return; // out of range
    if (YtouchPlace < BOXTOP)
        return; // out of range
    if (YtouchPlace > BOXHEIGHT)
        return; // out of range
    const uint8_t ch = ChanneltoSet - 1, n = CurveN(ch);
    int best = -1, bestDistance = 0;
    for (uint8_t k = 0; k < n; ++k)
    {
        if (!CurveDotShown(k))
            continue;
        const int d = abs(XtouchPlace - (int)xPoints[k]);
        if (best < 0 || d < bestDistance)
        {
            best = k;
            bestDistance = d;
        }
    }
    if (best < 0)
        return;
    CurrentPoint = best + 1;
    const int rjump = GetDifference(YtouchPlace, yPoints[best]);
    uint8_t &deg = CurvePoint[Bank][ch][best];
    if (YtouchPlace > yPoints[best])
    {
        if (deg >= rjump)
            deg -= rjump;
    }
    else
    {
        if (deg <= 180 - rjump)
            deg += rjump;
    }
    CurveStoreSync(Bank, ch); // (B121: remembered)
}

/*********************************************************************************************************************************/

void SoundBank()
{
    if (millis() < 10000)
        return; // don't announce bank if booted < 10 seconds ago
    PlaySound(BankSounds[BanksInUse[Bank - 1]]);
    ScreenTimeTimer = millis(); // reset screen counter to make sure its updated soon
}
/*********************************************************************************************************************************/
void ShowBank()
{
    char FMPress[4][12] = {"click fm1,1", "click fm2,1", "click fm3,1", "click fm4,1"};
    if (Bank >= 1 && Bank <= 4)
        SendCommand(FMPress[Bank - 1]); // (the old front page's four marks, parked off its edge; B130: none for banks 5 and 6)
    if (Bank >= 1 && Bank <= BANKS_USED)
        SendText((char *)"t4", BankNames[BanksInUse[Bank - 1]]);
}

/*********************************************************************************************************************************/

void DoOneSwitchView(uint8_t n) // n is 1-4  = number for switch to edit
{
    // B33: twelve channel jobs (5-16). Their radios and labels on the page, by channel: 9-12 keep r3-r6 / t3-t6, the
    // others are r10-r17 / t10-t17 (5, 6, 7, 8, 13, 14, 15, 16).
    static const char *chRadio[SWITCH_INPUTS] = {"r10", "r11", "r12", "r13", "r3", "r4", "r5", "r6", "r14", "r15", "r16", "r17"};
    static const char *chLabel[SWITCH_INPUTS] = {"t10", "t11", "t12", "t13", "t3", "t4", "t5", "t6", "t14", "t15", "t16", "t17"};
    char Rlabels[10][3] = {"r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9"};
    char OneSwitchViewc_revd[] = "c_revd"; // Reversed

    for (int i = 0; i < 10; ++i)
        SendValue(Rlabels[i], 0); // clear all
    for (int d = 0; d < SWITCH_INPUTS; ++d)
        SendValue((char *)chRadio[d], 0);

    ValueSent = false; // If no setting, = 'Not Used'

    if ((BankSwitch == n) && (!ValueSent))
        SendValue(Rlabels[1], 1); // No duplicates allowed!
    if ((Autoswitch == n) && (!ValueSent))
        SendValue(Rlabels[2], 1); // No duplicates allowed!
    for (int d = 0; d < SWITCH_INPUTS; ++d)
        if ((TopChannelSwitch[d] == n) && (!ValueSent))
            SendValue((char *)chRadio[d], 1); // No duplicates allowed! (B33: channels 5-16)
    if ((SafetySwitch == n) && (!ValueSent))
        SendValue(Rlabels[7], 1); // No duplicates allowed!
    if ((DualRatesSwitch == n) && (!ValueSent))
        SendValue(Rlabels[8], 1); // No duplicates allowed!
    if ((BuddySwitch == n) && (!ValueSent))
        SendValue(Rlabels[9], 1); // No duplicates allowed!

    if (!ValueSent)
    {
        if (FrontSwitchIsDefault(n))
            SendValue((char *)chRadio[n - 5], 1); // B38: a front switch with no job is its own channel's input: that is its marking
        else
            SendValue(Rlabels[0], 1); // nothing yet, so 'not used' is selected
    }

    SendValue(OneSwitchViewc_revd, 0);

    if (n >= 1 && n <= 8 && SwitchReversed[n - 1]) // shows the Reversed check box on the one switch screen (B32: eight)
        SendValue(OneSwitchViewc_revd, 1);
    else
        SendValue(OneSwitchViewc_revd, 0); // ... or not

    for (int d = 0; d < SWITCH_INPUTS; ++d)
    { // the channels by number (B34), or by name where the pilot has renamed one (B39)
        char v[24];
        ChannelLabel((uint8_t)(d + 5), v, sizeof(v));
        SendText((char *)chLabel[d], v);
    }
}

/*********************************************************************************************************************************/
void UpdateOneSwitchView()
{
    char SwNum[] = "Sw";
    SendValue(SwNum, SwitchEditNumber); // show switch number
    DoOneSwitchView(SwitchEditNumber);
}

/*********************************************************************************************************************************/

void ZeroGapStats()
{ // B155: the comms gaps alone (leaving the Rotorflight menu: its edits pause the main board, and those pauses are not the link's)
    GapLongest = 0;
    GapSum = 0;
    GapAverage = 0;
    GapCount = 0;
    GapStart = 0;
    ThisGap = 0;
}
void ZeroDataScreen()
{ // ZERO Those parameters that are zeroable

    TotalGoodPackets = 0;
    RecentPacketsLost = 0;
    TotalLostPackets = 0;
    ZeroGapStats();
    RXMAXModelAltitude = 0;
    MaxRateOfClimb = 0;
    RXModelAltitude = 0;
    GroundModelAltitude = 0;
    GPS_RX_MaxDistance = 0;
    GPS_RX_MaxSpeed = 0;
    LastShowTime = 0;
    TotalFrameRate = 0;
    FrameRateCounter = 0;
    PacketsPerSecond = 0;
    MaxBin = 100;
    GapShortest = 1000;
    for (int i = 0; i < 11; ++i)
    {
        GapSets[i] = 0;
        PrevGapSets[i] = 0xffff;
    }
}
/***************************************************** ReadNewSwitchFunction ****************************************************************************/

FLASHMEM void ReadNewSwitchFunction()
{
    char OneSwitchView_r0[] = "r0"; // Not used (B38: a real choice for a front switch)
    char OneSwitchView_r1[] = "r1"; // Flight modes
    char OneSwitchView_r2[] = "r2"; // Auto
    char OneSwitchView_r7[] = "r7"; // Safety
    char OneSwitchView_r8[] = "r8"; // Dual Rates
    char OneSwitchView_r9[] = "r9"; // Buddy
    char ProgressStart[] = "vis Progress,1";
    char ProgressEnd[] = "vis Progress,0";
    char PageSwitchView[] = "page SwitchesView";
    char OneSwitchViewc_revd[] = "c_revd"; // Reversed
    char Progress[] = "Progress";

    SendCommand(ProgressStart);
    SendValue(Progress, 10);

    if (GetValue(OneSwitchView_r1))
    {
        BankSwitch = SwitchEditNumber;
    }
    else
    {
        if (BankSwitch == SwitchEditNumber)
            BankSwitch = 0;
    }

    SendValue(Progress, 15);
    if (GetValue(OneSwitchView_r2))
    {
        Autoswitch = SwitchEditNumber;
    }
    else
    {
        if (Autoswitch == SwitchEditNumber)
            Autoswitch = 0;
    }
    SendValue(Progress, 25);
    { // B33: the twelve channel jobs (5-16), each its own radio on the page
        static const char *chRadio[SWITCH_INPUTS] = {"r10", "r11", "r12", "r13", "r3", "r4", "r5", "r6", "r14", "r15", "r16", "r17"};
        for (uint8_t d = 0; d < SWITCH_INPUTS; ++d)
        {
            if (GetValue((char *)chRadio[d]))
                TopChannelSwitch[d] = SwitchEditNumber;
            else if (TopChannelSwitch[d] == SwitchEditNumber)
                TopChannelSwitch[d] = 0;
            if (d == 3 || d == 7)
                SendValue(Progress, d == 3 ? 40 : 50);
        }
    }
    if (SwitchEditNumber >= 5 && SwitchEditNumber <= 8) // B38
    {
        const uint8_t bit = (uint8_t)(1 << (SwitchEditNumber - 5));
        if (TopChannelSwitch[SwitchEditNumber - 5] == SwitchEditNumber)
            TopChannelSwitch[SwitchEditNumber - 5] = 0; // its own channel: the default, not a job
        if (GetValue(OneSwitchView_r0))
            FrontSwitchUnused |= bit; // Not used, chosen on purpose: the channel's input sits at its centre
        else
            FrontSwitchUnused &= (uint8_t)~bit;
    }
    SendValue(Progress, 60);
    if (GetValue(OneSwitchView_r7))
    {
        SafetySwitch = SwitchEditNumber;
    }
    else
    {
        if (SafetySwitch == SwitchEditNumber)
            SafetySwitch = 0;
    }
    SendValue(Progress, 70);
    if (GetValue(OneSwitchView_r8))
    {
        DualRatesSwitch = SwitchEditNumber;
    }
    else
    {
        if (DualRatesSwitch == SwitchEditNumber)
            DualRatesSwitch = 0;
    }
    SendValue(Progress, 80);
    if (GetValue(OneSwitchView_r9))
    {
        BuddySwitch = SwitchEditNumber;
    }
    else
    {
        if (BuddySwitch == SwitchEditNumber)
            BuddySwitch = 0;
    }

    SendValue(Progress, 90);

    if (SwitchEditNumber >= 1 && SwitchEditNumber <= 8) // (B32: eight)
    {
        {
            const uint32_t gv = GetValue(OneSwitchViewc_revd);
            if (gv != 65535)   // B156: a reply that never came (65535) must not reverse a switch - the safety switch least of all
                SwitchReversed[SwitchEditNumber - 1] = gv;
        }
        if (SwitchEditNumber == 2)
            SendValue(Progress, 95);
    }

    SendValue(Progress, 100);
    SaveOneModel(ModelNumber);
    SaveTransmitterParameters(); // B32: the jobs and the reversed flags are the transmitter's, not the model's: kept now, not at the next switch-off
    SendCommand(PageSwitchView); // change to all switches screen
    CurrentView = SWITCHES_VIEW;
    UpdateSwitchesView(); // update its info
    ClearText();
    SendCommand(ProgressEnd);
    return;
}

/*********************************************************************************************************************************/
FASTRUN void DisplayCurveAndServoPos()
{
    // B135 (Malcolm, 20 Oct 2026: "if I move a point and it must redraw, it briefly displays the background image before
    // redrawing. I think it should simply clear; which might be quicker too"): this began by setting the page's picture
    // again (GraphView.pic - the screen repaints the whole page, the picture showing in the box), waited 50 ms, cleared the
    // box, waited again, and only then drew. The picture was Version 1's way of rubbing out the old curve. DisplayCurve's own
    // fill clears the box, in the same burst as the redraw: the screen shows nothing between the two (and the +, - and Next
    // point buttons always came this way).
    DisplayCurve(); // B117: the curve (ShowServoPos used to redraw it all for the marker; now it only moves the marker)
    for (int i = 0; i < 2; ++i)
    {
        GraphShown[i] = 0; // B110: Input and Output shown afresh
        GraphMovedAt[i] = 0;
    }
    ShowServoPos(); // the stick's marker, when its moment comes
    ClearText();
}

/******************************************************************************************************************************/

void UpdateLED()
{ // LED Brightness has changed so this ensures it is redisplayed
    char n1[] = "n1";
    uint32_t gv = GetValue(n1);
    if (gv != 65535) // ClaudeFix-16-7-2026 comms error must not become a brightness
        LEDBrightness = CheckRange(gv, 1, 254);
    LedWasGreen = false; // Forces a redisplay if brightness has changed
}

/******************************************************************************************************************************/
void ResetTransmitterSettings()
{ // This function resets all transmitter parameters to the default state.
  // Calibration should  be done next.

    const char Tn[32] = "Unknown";

    char prompt[] = "Delete every model and all settings?\r\nThis cannot be undone.";
    int sofar = 0;
    char ProgressStart[] = "vis Progress,1";
    char Progress[] = "Progress";

    if (!GetConfirmation(pCalibrateView, prompt))
        return;
    SendCommand(ProgressStart);
    SendValue(Progress, 2);
    ModelNumber = 1;
    ScreenTimeout = 120;
    Inactivity_Timeout = INACTIVITYTIMEOUT;
    strcpy(TxName, Tn);
    Qnh = 1009;
    DeltaGMT = 0;
    BackGroundColour = 0;
    ForeGroundColour = White;
    SpecialColour = Red;
    HighlightColour = Yellow;
    SticksMode = 2;
    AudioVolume = 20;
    Brightness = 100;
    PlayFanfare = false;
    TrimClicks = true;
    UseVariometer = false;
    SpeakingClock = true;
    AnnounceBanks = true;
    ResetSwitchNumbers();
    MinimumGap = 50;
    LogRXSwaps = true;
    UseLog = false;
    AnnounceConnected = true;
    ResetAllTrims();
    TxVoltageCorrection = 0;
    PowerOffWarningSeconds = DEFAULTPOWEROFFWARNING;
    LEDBrightness = DEFAULTLEDBRIGHTNESS;
    ConnectionAssessSeconds = 1;
    AutoModelSelect = false;
    MotorChannel = 2; // = 3 really
    MotorChannelZero = 0;
    TimerDownwards = false;
    char ProgressEnd[] = "vis Progress,0";

    SetDS1307ToCompilerTime();
    for (int k = 1; k < 5; ++k)
    { // writes default four times!
        for (ModelNumber = 1; ModelNumber <= MAXMODELNUMBER; ++ModelNumber)
        {
            ++sofar;
            SetDefaultValues();
            SaveOneModel(ModelNumber);
            SendValue(Progress, (sofar * (100 / MAXMODELNUMBER)) / 4);
            KickTheDog();
        }
        CloseModelsFile();
    }

    Autoswitch = 1;
    SafetySwitch = 2;
    BuddySwitch = 3;
    BankSwitch = 4;
    for (int i = 0; i < SWITCH_INPUTS; ++i)
        TopChannelSwitch[i] = 0; // (B33: twelve)
    FrontSwitchUnused = 0;       // (B38)
    for (int i = 0; i < 8; ++i)
        SwitchReversed[i] = false; // (B32: eight)

    SendValue(Progress, 100);
    ModelNumber = 1;
    SaveTransmitterParameters();
    SaveTransmitterParameters();
    SendCommand(ProgressEnd);
}

/*********************************************************************************************************************************/

void PointUp()
{
    MoveCurrentPointUp();
}
/******************************************************************************************************************************/

void PointDown()
{
    MoveCurrentPointDown();
}

/******************************************************************************************************************************/

bool CurveDotShown(uint8_t k) // B118: is point k of the current channel's curve on the glass? (an exponential curve shows its ends and centre)
{
    const uint8_t n = CurveN(ChanneltoSet - 1);
    if (k >= n)
        return false;
    if (InterpolationTypes[Bank][ChanneltoSet - 1] != EXPONENTIALCURVES)
        return true;
    return k == 0 || k == CurveMid(n) || k == n - 1;
}
void CheckInvisiblePoint()
{ // the current point must be one that is shown: on to the next that is (B118: for any count)
    const uint8_t n = CurveN(ChanneltoSet - 1);
    if (CurrentPoint < 1 || CurrentPoint > n)
        CurrentPoint = 1;
    for (uint8_t tries = 0; tries < n && !CurveDotShown(CurrentPoint - 1); ++tries)
        CurrentPoint = CurrentPoint >= n ? 1 : CurrentPoint + 1;
}

/******************************************************************************************************************************/

void PointSelect()
{
    ++CurrentPoint;
    if (CurrentPoint > CurveN(ChanneltoSet - 1)) // (B118: round the points there are)
        CurrentPoint = 1;
    CheckInvisiblePoint();
    DisplayCurve();
}

/******************************************************************************************************************************/

void GotoGPSView()
{
    char NoFixMsg[] = "Continue without GPS fix?";

    if (!GPS_RX_FIX)
    {
        if (!GetConfirmation(pRXSetupView, NoFixMsg))
            return;
    }
    char GotoGPSView[] = "page GPSView";
    SendCommand(GotoGPSView);
    CurrentView = GPSVIEW;
}

/******************************************************************************************************************************/

void StartBankNames()
{

    char GotoBankNames[] = "page BankNameView";
    char BKS[BANKS_USED][4] = {{"BK1"}, {"BK2"}, {"BK3"}, {"BK4"}, {"BK5"}, {"BK6"}};

    SendCommand(GotoBankNames);
    CurrentView = BANKSNAMESVIEW;

    for (int i = 0; i < BANKS_USED; ++i)
    {
        SendValue(BKS[i], BanksInUse[i]);
    }
    // B130: the page has six name boxes; banks 5 and 6's show only when the model uses them ('Six banks', Model options)
    for (int i = 5; i <= 6; ++i)
    {
        char v[16];
        snprintf(v, sizeof(v), "vis BK%d,%d", i, SixBanks ? 1 : 0); SendCommand(v);
        snprintf(v, sizeof(v), "vis t%d,%d", i, SixBanks ? 1 : 0); SendCommand(v);
    }
    SendCommand((char *)(SixBanks ? "vis t7,0" : "vis t7,1")); // ("Six banks: Model options" where the two boxes would be)
    UpdateModelsNameEveryWhere();
}

/******************************************************************************************************************************/

FLASHMEM static uint8_t BankNameFromPage(int i) // B130: box i's choice, kept in the list (a comms error, 65535, keeps the name as it was)
{
    char BKS[BANKS_USED][4] = {{"BK1"}, {"BK2"}, {"BK3"}, {"BK4"}, {"BK5"}, {"BK6"}};
    const int v = GetValue(BKS[i]);
    return (v >= 0 && v < BANK_NAMES_N) ? (uint8_t)v : BanksInUse[i];
}
void EndBankNames()
{
    for (int i = 0; i < BanksCount(); ++i)
    {
        BanksInUse[i] = BankNameFromPage(i);
    }
    SaveOneModel(ModelNumber);
    StartModelSetup();
}

/******************************************************************************************************************************/

void ListenToBanks()
{
    for (int i = 0; i < BanksCount(); ++i)
    {
        BanksInUse[i] = BankNameFromPage(i);
        PlaySound(BankSounds[BanksInUse[i]]);
        DelayWithDog(1200);
    }
}
// ******************************************************************************************************************************/
void SaveFailSafeChannels()
{
    char fs[16][5] = {"fs1", "fs2", "fs3", "fs4", "fs5", "fs6", "fs7", "fs8", "fs9", "fs10", "fs11", "fs12", "fs13", "fs14", "fs15", "fs16"};
    char ProgressStart[] = "vis Progress,1";
    char ProgressEnd[] = "vis Progress,0";
    char Progress[] = "Progress";
    char chgs[512];
    char change[] = "change";
    char cleared[] = "XX:";
    for (uint16_t i = 0; i < 500; ++i)
    { // get copy of any changes
        chgs[i] = TextIn[i + 4];
        chgs[i + 1] = 0;
    }
    SendCommand(ProgressStart);
    for (int i = 0; i < 16; ++i)
    {
        if (InStrng(fs[i], chgs)) // if this channel has been changed
        {
            {
                const uint32_t gv = GetValue(fs[i]);
                if (gv != 65535)   // B156: a reply that never came is not a failsafe setting
                    FailSafeChannel[i] = gv;
            }
        }
        SendValue(Progress, i * (100 / 16));
    }
    SendText(change, cleared);
    SendCommand(ProgressEnd);
}

/******************************************************************************************************************************/
void StartModelSetup()
{

    if (CurrentView == FAILSAFE_VIEW)
    { //  read failsafe blobs
        SaveFailSafeChannels();
    }

    if (CurrentView == MIXESVIEW)
    { //  read mixes
        ReadMixValues();
    }

    SendCommand(pRXSetupView);
    CurrentView = RXSETUPVIEW;
    SaveOneModel(ModelNumber);
    UpdateModelsNameEveryWhere();
    LastTimeRead = 0;
}

/******************************************************************************************************************************/
void EndModelSetup()
{
    GotoFrontView();
}

/******************************************************************************************************************************/
void UpdateSpeedScreen()
{
    char ns[16][4] = {{"n0"}, {"n1"}, {"n2"}, {"n3"}, {"n4"}, {"n5"}, {"n6"}, {"n7"}, {"n8"}, {"n9"}, {"n10"}, {"n11"}, {"n12"}, {"n13"}, {"n14"}, {"n15"}};
    char t14[] = "t14";
    CheckServoSpeeds();
    for (int i = 0; i < 16; ++i)
    {
        SendValue(ns[i], ServoSpeed[Bank - 1][i]);
    }
    SendText(t14, BankNames[BanksInUse[Bank - 1]]);
}

/******************************************************************************************************************************/
void StartSlowView()
{
    char GoSlowServoScreen[] = "page SlowServoView";
    SendCommand(GoSlowServoScreen);
    CurrentView = SLOWSERVOVIEW;
    UpdateButtonLabels();
    UpdateModelsNameEveryWhere();
    UpdateSpeedScreen();
}

/******************************************************************************************************************************/
void ReadSpeedsScreen(uint8_t bk, bool FromPage)
{
    if (bk > 3)
        return; // ClaudeFix-2-7-2026 ServoSpeed is [5][17]; the motor-switch "force bank change" sentinel (254) used to arrive here and write 4 KB past it

    char ns[16][4] = {{"n0"}, {"n1"}, {"n2"}, {"n3"}, {"n4"}, {"n5"}, {"n6"}, {"n7"}, {"n8"}, {"n9"}, {"n10"}, {"n11"}, {"n12"}, {"n13"}, {"n14"}, {"n15"}};
    char Progress[] = "Progress";
    char ProgressStart[] = "vis Progress,1";
    char ProgressEnd[] = "vis Progress,0";
    char chgs[512];
    char change[] = "change";
    char cleared[] = "XX:";
    if (FromPage)
        GetText(change, chgs, sizeof(chgs)); // B37: the bank switch moved before OK - the list of edited boxes is still on the page
    else
        for (uint16_t i = 0; i < 500; ++i)
        { // get copy of any changes
            chgs[i] = TextIn[i + 4];
            chgs[i + 1] = 0;
        }
    SendCommand(ProgressStart);
    for (int i = 0; i < 16; ++i)
    {
        if (InStrng(ns[i], chgs)) // if this channel has been changed
        {
            {
                const uint32_t gv = GetValue(ns[i]);
                if (gv != 65535)   // B156: a reply that never came is not a servo speed
                    ServoSpeed[bk][i] = gv;
            }
        }
        SendValue(Progress, i * (100 / 16));
    }
    SendText(change, cleared);
    SendValue(Progress, 100);
    SendCommand(ProgressEnd);
}

/******************************************************************************************************************************/
void EndSpeedsScreen()
{
    ReadSpeedsScreen(Bank - 1);
    CheckServoSpeeds();
    SaveOneModel(ModelNumber);
    StartModelSetup();
}
/******************************************************************************************************************************/
void WriteNewCurve()
{
    char CopyToAllBanks[] = "callfm";
    char pSticksView[] = "page SticksView";

    if (GetValue(CopyToAllBanks))
    {
        for (int p = 1; p <= BanksCount(); ++p) // (B131: banks 5 and 6 too when the model uses them - Malcolm, 19 Oct: "Copy to all banks omitted 5, 6")
        {
            if (p != Bank)
            {
                for (uint8_t k = 0; k < CURVE_POINTS_MAX; ++k) // (B118: every point; the count is the channel's, the same in every bank)
                    CurvePoint[p][ChanneltoSet - 1][k] = CurvePoint[Bank][ChanneltoSet - 1][k];
                for (uint8_t s = 0; s < CURVE_STORE_MAX; ++s) // (B121: with every height remembered for the other counts)
                    CurveStore[p][ChanneltoSet - 1][s] = CurveStore[Bank][ChanneltoSet - 1][s];
                InterpolationTypes[p][ChanneltoSet - 1] = InterpolationTypes[Bank][ChanneltoSet - 1];
                Exponential[p][ChanneltoSet - 1] = Exponential[Bank][ChanneltoSet - 1];
            }
        }
    }
    ChanneltoSet = 0;
    SaveOneModel(ModelNumber);
    Force_ReDisplay();
    SendCommand(pSticksView); // Set to SticksView
    CurrentView = STICKSVIEW;
    UpdateModelsNameEveryWhere();
    ClearText();
}

/******************************************************************************************************************************/
void StartRenameModel()
{

    char GoRenameModelScreen[] = "page RenameView";
    char NewName[] = "NewName";
    SendCommand(GoRenameModelScreen);
    CurrentView = RENAMEMODELVIEW;
    SendText(NewName, ModelName);
}

/******************************************************************************************************************************/

void GetDefaultFilename()
{ // Build filename from ModelName as best we can using first 8 chars upper cased
    uint8_t j = 0;
    uint8_t i = 0;
    char mod[] = ".MOD";
    while (i < 8)
    {
        if (ModelName[j] > 32)
        {
            SingleModelFile[i] = toUpperCase(ModelName[j]);
            ++i;
            SingleModelFile[i] = 0;
        }
        if (ModelName[j] < 32)
            break;
        ++j;
        if (i >= 8)
            break;
    }
    strcat(SingleModelFile, mod);
}

/******************************************************************************************************************************/

void FixFileName()
{
    char ModExt[] = ".MOD";
    for (uint8_t i = 0; i < strlen(SingleModelFile); ++i)
        SingleModelFile[i] = toUpperCase(SingleModelFile[i]);
    if (!InStrng(ModExt, SingleModelFile) && (strlen(SingleModelFile) <= 8))
        strcat(SingleModelFile, ModExt);
}

/******************************************************************************************************************************/
bool WriteBackup() // B21: true when the file was written (a name too long, or with no .MOD, is refused)
{
    bool ok = false;
    char ModExt[] = ".MOD";
    uint8_t Iterations = 4;
    char ProgressStart[] = "vis Progress,1";
    char ProgressEnd[] = "vis Progress,0";
    char Progress[] = "Progress";
    SendValue(Progress, 1);
    FixFileName();
    if ((strlen(SingleModelFile) <= 12) && (InStrng(ModExt, SingleModelFile) > 0))
    {
        SendCommand(ProgressStart);
        for (int i = 0; i < Iterations; i++)
        {
            CloseModelsFile();
            SingleModelFlag = true;
            SaveOneModel(1);
            SendValue(Progress, i * (100 / Iterations)); // write several times is needed!! :-)
        }
        CloseModelsFile();
        SingleModelFlag = false;
        ok = !FileError;
    }
    else
    {
        FileError = true;
    }
    if (FileError)
        ShowFileErrorMsg();
    SendValue(Progress, 100);
    DelayWithDog(100);
    SendCommand(ProgressEnd);
    LastFileInView = 120;
    return ok;
}

/******************************************************************************************************************************/
void EndRenameModel()
{
    char NewName[31] = "NewName";
    GetText(NewName, ModelName, sizeof(ModelName)); // ClaudeFix-2-7-2026
    SaveOneModel(ModelNumber);
    GotoModelsView();
}

/******************************************************************************************************************************/

void LoadModelForRenaming()
{
    CloseModelsFile();
    SingleModelFlag = true;
    ReadOneModel(1);
}
/******************************************************************************************************************************/

void RestoreCurrentModel()
{
    CloseModelsFile();
    ModelNumber = SavedModelNumber;
    SingleModelFlag = false;
    ReadOneModel(ModelNumber);
    SaveAllParameters();
}

// ******************************** Global Array1 of numbered function pointers OK up the **********************************

// This new list can be huge - up to 24 BITS unsigned!  ( Use "NUMBER<<8" )
#define LASTFUNCTION1 227 // One more than final one

void (*NumberedFunctions1[LASTFUNCTION1])(){
    Blank,                   // 0 Cannot be used
    DeleteModel,             // 1
    StartAudioVisualView,    // 2
    EndAudioVisualView,      // 3
    StartTXSetupView,        // 4
    InputsViewEnd,           // 5
    SystemPage1End,          // 6
    SystemPage1Start,        // 7
    StartWifiScan,           // 8
    EndWifiScan,             // 9
    StartServosTypeView,     // 10
    EndServoTypeView,        // 11
    LoadNewLogFile,          // 12
    DeleteThisLogFile,       // 13
    LogReleasedNEW,          // 14   // new version
    LogTouched,              // 15   // this does nothing, yet ...
    RefreshDualRatesNew,     // 16
    StartGapsView,           // 17
    StartPIDView,            // 18
    SendEditedPIDs,          // 19
    PIDs_Were_edited,        // 20
    EndPIDView,              // 21
    StartRFRatesView,        // 22
    EndRFRatesView,          // 23
    RatesWereEdited,         // 24
    SendEditedRates,         // 25
    RotorFlightStart,        // 26
    RotorFlightEnd,          // 27
    StartRatesAdvancedView,  // 28
    StartPIDAdvancedView,    // 29
    RatesAdvancedWereEdited, // 30
    EndRatesAdvancedView,    // 31
    SendEditedRatesAdvanced, // 32
    PIDsAdvancedWereEdited,  // 33
    SendEditedPID_Advanced,  // 34
    EndPIDsAdvancedView,     // 35
    SaveRFParameters,        // 36
    RestoreRFParameters,     // 37
    Start_RESTORE,           // 38
    Cancel_RESTORE,          // 39
    Start_SAVE,              // 40
    Cancel_SAVE,             // 41
    ChooseBackGround,        // 42
    Save_BackGround,         // 43
    StartChooseImage,        // 44
    EndChooseImage,          // 45
    ImageScrollStop,         // 46
    LinkRatesToBanksChanged, // 47
    StartBackupView,         // 48 B70: the menu's Backup/Restore (was Start_RF_Backup_Restore, the Version 1 picker)
    EndBackupView,           // 49
    Start_RF_Governor,       // 50
    End_RF_Governor,         // 51
    Save_RF_Governor,        // 52
    GOVS_P_Were_Edited,      // 53
    Start_Gov_Global,        // 54
    End_Gov_Global,          // 55
    Save_Gov_Global,         // 56
    Gov_Global_Were_Edited,  // 57
    AddWords,                // 58
    StartModelIDView,        // 59
    EndModelIDView,          // 60
    SaveToLocalGovGLOBAL,    // 61
    RestoreFromSDGlobalGOV,  // 62
    Enable_Binding,          // 63
    StartRescueView,         // 64 B50: the Rotorflight menu's Rescue ...
    EndRescueView,           // 65 OK
    SaveRescue,              // 66 Save (either page)
    RescueWasEdited,         // 67 a number typed
    RescueModeTapped,        // 68 Off / Climb / Hold height
    RescueFlipTapped,        // 69 Roll upright first: Off / On
    StartRescue2View,        // 70 Height ...
    EndRescue2View,          // 71 OK on page 2: back to page 1
    RescueMode2Tapped,       // 72 B52: the mode on the height page (Off / Climb / Hold height)
    StartServoView,          // 73 B55: the Rotorflight menu's Servos ...
    EndServoView,            // 74 OK
    SaveServo,               // 75 Save
    ServoWasEdited,          // 76 a number typed
    ServoReverseTapped,      // 77 Reverse
    ServoGeometryTapped,     // 78 Geometry Corr.
    ServoPrevious,           // 79 < Servo
    ServoNext,               // 80 Servo >
    StartRFSettingsView,     // 81 B56: the menu's Settings ...
    EndRFSettingsView,       // 82 OK on the settings page
    StartTravelView,         // 83 B57: the menu's Travel extents ...
    EndTravelView,           // 84 OK (either page)
    SaveTravel,              // 85 Save (either page)
    TravelWasEdited,         // 86 a number typed
    TravelAilTapped,         // 87 Aileron reversed
    TravelEleTapped,         // 88 Elevator reversed
    TravelCollTapped,        // 89 Collective reversed
    StartTravel2View,        // 90 Next >
    EndTravel2View,          // 91 < Previous
    StartFilterView,         // 92 B58: the menu's Filters ...
    EndFilterView,           // 93 OK
    SaveFilters,             // 94 Save
    FilterWasEdited,         // 95 a number typed
    FilterLpf1Tapped,        // 96 Lowpass 1 type
    FilterLpf2Tapped,        // 97 Lowpass 2 type
    FilterPresetTapped,      // 98 RPM filter strength
    FilterLpf1EnableTapped,  // 99 B61: Lowpass Filter: Enable
    FilterRpmEnableTapped,   // 100 RPM Filter: Enable (a feature bit: the save restarts the flight controller)
    FilterDynNotchEnableTapped, // 101 Dynamic Filter: Enable (ditto)
    StartFilter2View,        // 102 Next > (the expert page)
    EndFilter2View,          // 103 < Previous
    FilterLpf2EnableTapped,  // 104 Lowpass Filter 2: Enable
    FilterDynCutoffTapped,   // 105 Dynamic Cutoff (lowpass 1): Enable
    FilterNotch1Tapped,      // 106 Notch Filter 1: Enable
    FilterNotch2Tapped,      // 107 Notch Filter 2: Enable
    TravelYawTapped,         // 108 B66: Mixer page 3, Yaw reversed
    StartTravel3View,        // 109 Next > (page 2 to the tail rotor page)
    StartTravel2View,        // 110 < Previous (page 3 back to page 2)
    BackupNow,               // 111 B70: the backup page's Back up
    RestoreAll,              // 112 Restore all
    WriteEdits,              // 113 Write edits
    DiscardEdits,            // 114 Forget edits
    EndBackupView,           // 115 OK
    StartJobsView,           // 116 B140: the menu's Switches & knobs ... (was B72 Adjustments)
    EndJobsView,             // 117 OK
    SaveJobs,                // 118 Save: the switch jobs, then the selectors and knobs
    JobsWasEdited,           // 119 a number typed
    JobsSettingTapped,       // 120 the job box: the picker
    JobsSettingTapped,       // 121 (both codes open the picker)
    JobsChannelTapped,       // 122 the channel box
    JobsChannelTapped,       // 123 (as 122)
    JobsKindTapped,          // 124 the kind box
    JobsBankTapped,          // 125 the bank box
    JobsPrevious,            // 126 < Prev
    JobsNext,                // 127 Next >
    JobsAdd,                 // 128 Add: the picker first
    JobsRemove,              // 129 Remove
    JobsBarMoved,            // 130 the bar touched
    JobsPickOk,              // 131 the picker's OK
    JobsPickCancel,          // 132 Cancel
    StartJobsView,           // 133 (B77 Switches: the page is gone - its codes open the one page)
    EndJobsView,             // 134 (was Switches OK)
    SaveJobs,                // 135 (was Switches Save)
    JobsSettingTapped,       // 136 (was the action picker)
    JobsChannelTapped,       // 137 (was the switches' channel)
    JobsPrevious,            // 138 (was <)
    JobsNext,                // 139 (was >)
    JobsAdd,                 // 140 (was Switches Add)
    JobsRemove,              // 141 (was Switches Remove)
    JobsBarMoved,            // 142 (was the blobs dragged)
    JobsPickOk,              // 143 (was the action picker's OK)
    JobsPickCancel,          // 144 (was its Cancel)
    StartCopyBankView,       // 145 B78: the menu's Copy a bank ...
    EndCopyBankView,         // 146 OK
    CopyBankNow,             // 147 Copy bank A to bank B
    CopyBankFromTapped,      // 148 the source bank
    CopyBankToTapped,        // 149 the target bank
    CopyBankFlightTapped,    // 150 Flight tuning
    CopyBankRatesTapped,     // 151 Rates
    CopyBankGovTapped,       // 152 Governor gains
    CopyBankHsTapped,        // 153 Head speed too
    CopyBankAdjTapped,       // 154 Adjust gains for head speed
    StartBatteryView,        // 155 B88: the menu's Battery ...
    EndBatteryView,          // 156 OK
    SaveBattery,             // 157 Save
    BatteryWasEdited,        // 158 a number typed
    BatteryVoltageSourceTapped, // 159 Voltage from
    BatteryCurrentSourceTapped, // 160 Current from
    StartBlackboxView,       // 161 the menu's Black box ...
    EndBlackboxView,         // 162 OK
    SaveBlackbox,            // 163 Save
    BlackboxWasEdited,       // 164 a number typed
    BlackboxModeTapped,      // 165 When
    BlackboxDeviceTapped,    // 166 Where
    BlackboxRateTapped,      // 167 How often
    BlackboxRollTapped,      // 168 Overwrite the oldest
    BlackboxErase,           // 169 Erase all logs
    StartCalibrateView,      // 170 the menu's Calibrate ...
    EndCalibrateView,        // 171 OK
    CalibrateNow,            // 172 Calibrate level
    SaveLevelTrims,          // 173 Save
    CalibrateWasEdited,      // 174 a trim typed
    ArmingWhy,               // 175 the menu's arming line tapped
    BatterySensorsView,      // 176 B90: the battery page's Sensors > (the FC pads' sensors, a page of their own)
    BatterySensorsBack,      // 177 B90: its < Battery
    StartTravel4View,        // 178 B98: Next > (the Mixer's tail page to the bench measure page)
    BenchAxisTapped,         // 179 the axis tapped (roll / pitch)
    BenchWasEdited,          // 180 the angle or the gauge's reading tapped (the keypad)
    BenchHoldTapped,         // 181 Hold swash / Release
    BenchSuggestTapped,      // 182 the suggested calibration tapped
    StartBasicsView,         // 183 B99: the settings page's Model basics ...
    EndBasicsView,           // 184 OK (either page)
    SaveBasics,              // 185 Save
    BasicsSwashTapped,       // 186 Swash type
    BasicsDirectionTapped,   // 187 Rotor turns
    BasicsTailTapped,        // 188 Tail type
    BasicsProtocolTapped,    // 189 ESC signal (the motor protocol)
    BasicsEscTapped,         // 190 ESC brand (the telemetry protocol)
    BasicsWasEdited,         // 191 a number typed (poles, the gear ratios)
    StartBasics2View,        // 192 Next > (the gear ratios)
    EndBasics2View,          // 193 < Previous
    StartBasics3View,        // 194 B100: Next > (the ports)
    EndBasics3View,          // 195 < Previous (the gear ratios)
    BasicsPort1Tapped,       // 196 a port's function stepped (rows 1-6)
    BasicsPort2Tapped,       // 197
    BasicsPort3Tapped,       // 198
    BasicsPort4Tapped,       // 199
    BasicsPort5Tapped,       // 200
    BasicsPort6Tapped,       // 201
    StartEscCalView,         // 202 Next > (the ESC throttle calibration)
    EndEscCalView,           // 203 < Previous (the ports)
    EscCalTapped,            // 204 Full throttle / Minimum
    StartEasyView,           // 205 B104: the menu's Easy tuning ...
    EndEasyView,             // 206 OK
    SaveEasy,                // 207 Save
    EasyStartMoved,          // 208 the Start slider touched, dragged, let go (B105: its place in the word's top byte)
    EasyAgilityMoved,        // 209 Agility
    EasyStickFeelMoved,      // 210 Stick feel
    EasyCyclicMoved,         // 211 Cyclic
    EasyTailMoved,           // 212 Tail
    EasySpoolTapped,         // 213 the switch: PID spool-up in every bank
    RatesTypeTapped,         // 214 B106: the Rates page's type tapped (its picker)
    RatesTypePickOk,         // 215 the picker's OK: the chosen type, with its starting values
    RatesTypePickCancel,     // 216 the picker's Cancel
    RatesCurvesTapped,       // 217 B107: the Rates page's "Curves ..." (page 83)
    RatesCurvesOk,           // 218 the curves page's OK: back to the Rates page
    MaxRangeWideTapped,      // 219 B113: the Channels page's "Max range:" 500 to 2500 (B111/B112: the stick ends)
    MaxRangeNarrowTapped, // 220
    CurvePoints3Tapped,   // 221 (B118: the curve page's Points 3 5 7 9)
    CurvePoints5Tapped,   // 222
    CurvePoints7Tapped,   // 223
    CurvePoints9Tapped,   // 224 B113: ... 945 to 2055
    CurveResetTapped,     // 225 B135: the curve page's Reset (a straight line from corner to corner, no expo)
    CurveFlatTapped       // 226 B135: its Flat (every point the ringed point's height)
};

// This list migth become MUCH longer as it limit is 24 bits big

// ******************************** Global Array of numbered function pointers - OK up to 127 functions ... **********************************

// This list can be only up to 127 (7 BITS) functions long

#define LASTFUNCTION 80 // One more than final one, because first is number zero

void (*NumberedFunctions[LASTFUNCTION])(){
    Blank,                    // 0  Cannot be used
    DoMFName,                 // 1
    ModelViewEnd,             // 2
    DoLastTimeRead,           // 3
    GotoModelsView,           // 4
    GotoMacrosView,           // 5
    PopulateMacrosView,       // 6
    ExitMacrosView,           // 7
    ShowChannelName,          // 8
    StartReverseView,         // 9
    EndReverseView,           // 10
    StartBuddyView,           // 11
    EndBuddyView,             // 12
    Blank,                    // 13  // spare
    Blank,                    // 14  //spare
    BottomOfLogFileNEW,       // 15  // goto bottom of log file
    LogEND,                   // 16
    StartLogFilesListScreen,  // 17  // was DelLOG. not now though.
    StartLogFileView,         // 18 // revised log view ****************************************************
    SetupViewFM,              // 19
    StartSubTrimView,         // 20
    EndSubTrimView,           // 21
    StartTrimDefView,         // 22
    Options2End,              // 23
    DefineTrimsEnd,           // 24
    OptionView2Start,         // 25
    OptionView3Start,         // 26
    OptionView3End,           // 27
    BuddyChViewStart,         // 28
    BuddyChViewEnd,           // 29
    RudderLeftTrim,           // 30
    RudderRightTrim,          // 31
    AileronRightTrim,         // 32
    AileronLeftTrim,          // 33
    ElevatorUpTrim,           // 34
    ElevatorDownTrim,         // 35
    ThrottleDownTrim,         // 36
    ThrottleUpTrim,           // 37
    RXOptionsViewStart,       // 38
    RXOptionsViewEnd,         // 39
    ResetTransmitterSettings, // 40
    Blank,                    // 41 Not CALLED FrOM Here now
    PointUp,                  // 42
    PointDown,                // 43
    PointSelect,              // 44
    DualRatesStart,           // 45
    DualRatesEnd,             // 46
    DualRatesRefresh,         // 47
    GotoFrontView,            // 48
    GotoGPSView,              // 49
    StartModelSetup,          // 50
    EndModelSetup,            // 51
    StartBankNames,           // 52
    EndBankNames,             // 53
    ListenToBanks,            // 54
    StartSlowView,            // 55
    EndSpeedsScreen,          // 56
    WriteNewCurve,            // 57
    StartRenameModel,         // 58
    EndRenameModel,           // 59
    YesPressed,               // 60
    NoPressed,                // 61
    RenameFile,               // 62
    CheckAllModelIds,         // 63
    Blank,                    // 64  // spare ****************************************************
    ReceiveModelFile,         // 65
    Blank,                    // 66  // spare ****************************************************
    Blank,                    // 67  // spare ****************************************************
    DeleteModelID,            // 68
    StartPong,                // 69
    StoreModelID,             // 70
    ResetClock,               // 71
    SaveSwitches,             // 72 (NOW SAVED FROM TX SETUP MENU GLOBALLY FOR ALL MODELS)
    ShowScreenAgain,          // 73 End of screen timeout when someone touched screen
    HideScreenAgain,          // 74 Force immediate 'screen timeout'
    TrimsToSubtrim,           // 75
    ReceiveLotsofData,        // 76
    SetNewDualRate,           // 77 // when the DualRate behavior scrollable thingy is changed
    EndLogFilesListScreen,    // 78
    TopOfLogFileNEW           // 79 // goto top of log file NEW

    // must stop at 126
}; // This list might become longer but a new one is now started above without the 127 limit

/*********************************************************************************************************************************
 *                          BUTTON WAS PRESSED (DEAL WITH INPUT FROM NEXTION DISPLAY)                                            *
 *********************************************************************************************************************************/
// ClaudeFix-16-7-2026 A channel-name event ("CH3NAME=Gear") can share one serial read
// with another touch event (e.g. leaving the Inputs screen). The dispatcher
// matched the OTHER event first and its ClearText() discarded the freshly
// typed name — "sometimes the new name disappears". Handle every name event
// up front, then blank it from TextIn so normal dispatch continues with
// whatever else arrived in the same read.
void HandleChannelNameEvents()
{
    char pat[12];
    for (int ch = 1; ch <= 16; ++ch)
    {
        snprintf(pat, sizeof(pat), "CH%dNAME=", ch);
        int p = InStrng(pat, TextIn);
        if (p <= 0)
            continue;
        int start = p - 1;                // InStrng positions are 1-based
        int k = start + (int)strlen(pat); // the typed name begins here
        DoNewChannelName(ch, k);
        int j = k, cnt = 0; // blank exactly what was consumed
        while (uint8_t(TextIn[j]) > 0 && cnt < 10)
        {
            ++j;
            ++cnt;
        }
        for (int b = start; b < j; ++b)
            TextIn[b] = ' ';
    }
}

FASTRUN void ButtonWasPressed()
{
    CRUMB(CRUMB_BUTTON);
    HandleChannelNameEvents(); // ClaudeFix-16-7-2026 names first — see comment above

    int Command_number = GetIntFromTextIn(0);
    if (Command_number)
    { // is there anything ?
        StartInactvityTimeout();
        ScreenTimeTimer = millis();                       // reset screen timeout counter
        uint32_t NumberedCommand = Command_number & 0x7F; // NextionCommand.FirstDWord & 0x7F; // Just clear the hi BIT ( i.e. -128)
        uint32_t NumberedCommand1 = ((uint32_t)Command_number >> 8) & 0xFFFF; // the function's number (B105: 16 bits now) ...
        ScreenEventArg = (uint8_t)((uint32_t)Command_number >> 24);            // ... and the top byte a value the page sends with it (0: none)

#ifdef DB_NEXTION
        if ((TextIn[0] < 128) && (TextIn[0] > 28))
        {
            Look1("Command WORD: ");
            Look(TextIn);
        }

        if ((TextIn[0] > 128) && (TextIn[0] < 255))
        {
            Look1("7 BIT Command NUMBER: ");
            Look(NumberedCommand);
        }

        if (TextIn[0] == 0)
        {
            Look1("24 BIT command NUMBER: ");
            Look(NumberedCommand1);
        }
#endif
        if (!TextIn[0])
        { //  Now expanded to handle FAR more than 127 functions
            if (NumberedCommand1 < LASTFUNCTION1)
            {
                NumberedFunctions1[NumberedCommand1](); // Call the needed 24 BIT function -- with a function pointer
            }
            ClearText();
            return;
        }

        if (TextIn[0] >= 128)
        {
            if (NumberedCommand < LASTFUNCTION)
            {
                NumberedFunctions[NumberedCommand](); // Call the needed 7 BIT function -- with a function pointer
            }
            ClearText();
            return;
        }
        // By here, TextIn[0] must be start of a character based command

        if (InStrng((char *)"LDRCAWAKE", TextIn) > 0)
        { // B123 (Malcolm, 17 Oct 2026: "the screen timeout should be disabled while we play these videos because it went black
          // in the middle of one!"): the screen's films (screen 1.11.88) say this every 15 s while one plays or the films menu
          // is up - its touches are the screen's own, so nothing else would tell this board that someone is watching
            ScreenTimeTimer = millis();
            ClearText();
            return;
        }
        if (InStrng((char *)LDRC_LINK_KNOCK, TextIn) > 0)
        { // V1B: the screen asks for the file link
            ClearText();
            LinkMode();
            return;
        }
        if (InStrng((char *)LDRC_RX_UPDATE_WORD, TextIn) > 0)
        { // V1B: the screen asks for the connected receiver to update itself (RxUpdate.h)
            OrderReceiverUpdateFromText(TextIn);
            ClearText();
            return;
        }
        if (InStrng((char *)LDRC_IMAGE_WORD, TextIn) > 0)
        { // V1B: the screen's own picture chooser answers for the "Choose image" page (ChooseImage.h, B21)
            ChooseImageFromScreen(TextIn);
            ClearText();
            return;
        }

        // The very old code below here is gradually and carefully being replaced by new code in multiple functions - it works fine but is not as efficient as the new code

        int i = 0;
        int j = 0;
        int p = 0;
        char Setup[] = "Setup";
        char ClickX[] = "ClickX";
        char ClickY[] = "ClickY";
        char Reset[] = "Reset";
        char Front_View[] = "FrontView";
        char Sticks_View[] = "SticksView";
        char Graph_View[] = "GraphView";
        char SetupView[] = "MainSetup";
        char DataEnd[] = "DataEnd";
        char Data_View[] = "DataView";
        char CalibrateView[] = "CalibrateView";
        char TrimView[] = "TrimView";
        char TRIMS50[] = "TRIMS50";
        char MIXES_VIEW[] = "MIXESVIEW"; // first call
        char Mixes_View[] = "MixesView";
        char FM1[] = "FM 1";
        char FM2[] = "FM 2";
        char FM3[] = "FM 3";
        char FM4[] = "FM 4";
        char ReScan[] = "ReScan";
        char MixesView_MixNumber[] = "MixNumber";
        char ModelsView_ModelNumber[] = "ModelNumber";
        char SvT11[] = "t11";
        char CMsg1[] = "Move all controls to their full\r\nextent several times,\r\nthen press Next.";
        char SvB0[] = "b0";
        char CMsg2[] = "Next";
        char Cmsg3[] = "Centre all channels.\r\nPush every top switch fully AWAY\r\nfrom you, then press Finish."; // B30: the position held becomes "away"
        char Cmsg4[] = "Finish";
        char Cmsg5[] = "Calibrate again"; // (B124: "Calibration saved." and what else there is to say come from CalibrationNote)
        char TypeView[] = "TypeView";
        char CopyToAllBanks[] = "callfm";
        char RXBAT[] = "RXBAT";
        char r2s[] = "r2s";
        char r3s[] = "r3s";
        char r4s[] = "r4s";
        char r5s[] = "r5s";
        char r6s[] = "r6s";
        char r12s[] = "r12s";
        char r0[] = "r0";
        char r1[] = "r1";
        char SwitchesView[] = "SwitchesView";
        char SwitchesView1[] = "SwitchesView1";
        char OneSwitchView[] = "OneSwitchView";
        char PageOneSwitchView[] = "page OneSwitchView";
        char InputsView[] = "InputsView";
        char Export[] = "Export";
        char Import[] = "Import";
        char DelFile[] = "DelFile";
        char ModExt[] = ".MOD";
        char FailSAVE[] = "FailSAVE";
        char FailSafe[] = "FailSafe";
        char fs[16][5] = {"fs1", "fs2", "fs3", "fs4", "fs5", "fs6", "fs7", "fs8", "fs9", "fs10", "fs11", "fs12", "fs13", "fs14", "fs15", "fs16"};
        char CH1NAME[] = "CH1NAME=";
        char CH2NAME[] = "CH2NAME=";
        char CH3NAME[] = "CH3NAME=";
        char CH4NAME[] = "CH4NAME=";
        char CH5NAME[] = "CH5NAME=";
        char CH6NAME[] = "CH6NAME=";
        char CH7NAME[] = "CH7NAME=";
        char CH8NAME[] = "CH8NAME=";
        char CH9NAME[] = "CH9NAME=";
        char CH10NAME[] = "CH10NAME=";
        char CH11NAME[] = "CH11NAME=";
        char CH12NAME[] = "CH12NAME=";
        char CH13NAME[] = "CH13NAME=";
        char CH14NAME[] = "CH14NAME=";
        char CH15NAME[] = "CH15NAME=";
        char CH16NAME[] = "CH16NAME=";
        char HelpView[] = "HelpView";
        char SendModel[] = "SendModel";
        char Exrite[] = "Exrite";
        char ExpR[] = "Exp";
        char Smooth[] = "Smooth";
        char Lines[] = "Lines";
        char GOTO[] = "GOTO:";
        char WhichPage[] = "page                                 "; // excessive spaces for page name
        char AddMinute[] = "IncMinute";
        char Dec_Minute[] = "DecMinute";
        char Dec_Hour[] = "DecHour";
        char Inc_Hour[] = "IncHour";
        char Inc_Year[] = "IncYear";
        char Dec_Year[] = "DecYear";
        char Inc_Date[] = "IncDate";
        char Dec_Date[] = "DecDate";
        char Inc_Month[] = "IncMonth";
        char Dec_Month[] = "DecMonth";
        char DataView_Clear[] = "Clear";
        char DataView_AltZero[] = "AltZero";
        char Mark[] = "Mark";
        char SetupCol[] = "SetupCol";
        char Fm_pco[] = "Fm.pco";
        char FrontView_BackGround[] = "FrontView.BackGround";
        char FrontView_ForeGround[] = "FrontView.ForeGround";
        char FrontView_Special[] = "FrontView.Special";
        char FrontView_Highlight[] = "FrontView.Highlight";
        char n0[] = "n0";
        char Expo[] = "Expo";
        char h0[] = "h0";
        char StCH[] = "StCH";
        char s0[] = "s0";
        char StEDIT[] = "StEDIT";
        char Prompt[60];
        char overwr[] = "Overwrite ";
        char ques[] = "?";
        char hhead[] = "Create backup file for";
        char fprompt[] = "File name";
        char ProgressStart[] = "vis Progress,1";
        char ProgressEnd[] = "vis Progress,0";
        char Progress[] = "Progress";

        char NotConnected[] = "No model is connected.\r\nSwitch it on, then press Save.";
        char IsConnected[] = "The model is connected.\r\nChanges here move its controls.\r\n\r\nOpen Inputs anyway?";
        char invisb1[] = "vis b1,0";
        char invisb0[] = "vis b0,0";
        char visb1[] = "vis b1,1";
        char visb0[] = "vis b0,1";
        char LOG[] = ".LOG";
        char PromtBeforeSendingModelFile[100];

        // ************************* test many input words from Nextion *****************

        if (InStrng(StCH, TextIn))
        { // select sub trim channel
            SubTrimToEdit = GetValue(s0) - 1;
            if (SubTrimToEdit > 15)
                SubTrimToEdit = 0; // ClaudeFix-2-7-2026 0 or comms-error 65535 indexed SubTrims[254]
            SendValue(n0, SubTrims[SubTrimToEdit] - 127);
            SendValue(h0, SubTrims[SubTrimToEdit]);
            ClearText();
            return;
        }

        if (InStrng(StEDIT, TextIn))
        {                                                 // edit sub trim value
            SubTrims[SubTrimToEdit] = GetValue(n0) + 127; // 127 is mid point in 8 bit value 0 - 254
            ClearText();
            return;
        }

        if (InStrng(SetupView, TextIn) > 0)
        { //  goto main TX setup screen
            ClearText();
            bool abandoned = false;
            if (CurrentView == CALIBRATEVIEW)
            {
                if (CurrentMode == CALIBRATELIMITS || CurrentMode == CENTRESTICKS)
                { // B17: OK part way through: nothing half-swept is kept - the limits and switch directions come back from the card, normal mode again
                    CurrentMode = NORMAL;
                    LoadAllParameters();
                    RedLedOn();
                    abandoned = true;
                }
                ReadOneModel(ModelNumber); // because it was cleared for calibration
            }
            SaveAllParameters();
            CurrentView = TXSETUPVIEW;
            SendCommand(pTXSetupView);
            LastTimeRead = 0;
            CurrentView = TXSETUPVIEW;
            ClearText();
            UpdateModelsNameEveryWhere();
            if (abandoned)
                MsgBox(pTXSetupView, (char *)"Calibration NOT saved.\r\nNext time press Finish first."); // B124: OK beside Finish said nothing when it threw the new calibration away
            return;
        }

        if (InStrng(Mark, TextIn) > 0)
        {
            GPSMarkHere = 255; // Mark this at RX
            GPS_RX_MaxDistance = 0;
            AddParameterstoQueue(GPS_MARK_LOCATION); // 3 is the ID of the MARK HERE parameter
            ClearText();
            return;
        }

        if (InStrng(DataEnd, TextIn) > 0)
        { //  Exit from Data screen
            SendCommand(pRXSetupView);
            CurrentView = RXSETUPVIEW;
            UpdateModelsNameEveryWhere();
            ClearText();
            return;
        }

        if (InStrng(DataView_Clear, TextIn) > 0)
        { //  Clear Data screen
            ZeroDataScreen();
            ClearSuccessRate();
            ClearText();
            return;
        }

        if (InStrng(DataView_AltZero, TextIn) > 0)
        { //  Set zero altitude on data screen by recording current altitude for subraction later
            GroundModelAltitude = RXModelAltitudeBMP280;
            GPS_RX_GroundAltitude = GPS_RX_Altitude;
            GPS_RX_Maxaltitude = 0;
            RXMAXModelAltitude = 0;
            ClearText();
            return;
        }

        if (InStrng(HelpView, TextIn) > 0)
        { // Display Help screen(s)
            if (CurrentView == RXSETUPVIEW1)
                ReadRXOptionsView(); // B23: what was typed on Model options is kept (the page is drawn afresh on the way back)
            SavedCurrentView = CurrentView;
            HelpTookRead = Reading_PIDS_Now || Reading_RATES_Now || Reading_RATES_Advanced_Now || Reading_PIDS_Advanced_Now || Reading_GOV_Now || Reading_GOV_Config_Now; // B19
            CurrentView = HELP_VIEW;
            SendHelp();
            ClearText();
            return;
        }
        if (InStrng(Dec_Minute, TextIn) > 0)
        {
            DecMinute();
            ClearText();
            return;
        }
        if (InStrng(AddMinute, TextIn) > 0)
        {
            IncMinute();
            ClearText();
            return;
        }

        if (InStrng(Dec_Hour, TextIn) > 0)
        {
            DecHour();
            ClearText();
            return;
        }
        if (InStrng(Inc_Hour, TextIn) > 0)
        {
            IncHour();
            ClearText();
            return;
        }

        if (InStrng(Dec_Year, TextIn) > 0)
        {
            DecYear();
            ClearText();
            return;
        }
        if (InStrng(Inc_Year, TextIn) > 0)
        {
            IncYear();
            ClearText();
            return;
        }

        if (InStrng(Dec_Date, TextIn) > 0)
        {
            DecDate();
            ClearText();
            return;
        }
        if (InStrng(Inc_Date, TextIn) > 0)
        {
            IncDate();
            ClearText();
            return;
        }

        if (InStrng(Dec_Month, TextIn) > 0)
        {
            DecMonth();
            ClearText();
            return;
        }
        if (InStrng(Inc_Month, TextIn) > 0)
        {
            IncMonth();
            ClearText();
            return;
        }

        if (InStrng(GOTO, TextIn) > 0)
        { // Return from Help screen returns here to relevent config screen
            i = 5;
            while (uint8_t(TextIn[i]) && i < 30)
            {
                WhichPage[i] = TextIn[i];
                ++i;
                WhichPage[i] = 0;
            }
            // Look1("Returned from help: ");
            // Look(TextFileName);
            // Look(WhichPage);
            // Look(SavedCurrentView);

            if (InStrng(LOG, TextFileName))
            {
                CurrentView = DATAVIEW;
                SavedCurrentView = DATAVIEW;
                strcpy(WhichPage, pDataView);
                //  Look(WhichPage);
            }
            // Get page name to which to return

            SendCommand(WhichPage); // this sends nextion back to last screen

            CurrentView = SavedCurrentView;
            if (InStrng((char *)".TXT", TextFileName))
                strcpy(TextFileName, ""); // B56: the help text is closed - the viewer must not keep its name (OK on the Files page brought the help back)
            if (CurrentView == RXSETUPVIEW1)
                RXOptionsViewStart(); // B23: Model options drawn afresh, with the values read before Help

            if (CurrentView == GRAPHVIEW)
            {
                DisplayCurveAndServoPos();
                SendValue(CopyToAllBanks, 0);
            }
            if (CurrentView == SWITCHES_VIEW)
                UpdateSwitchesView();
            if (CurrentView == ONE_SWITCH_VIEW)
                UpdateOneSwitchView();
            if (CurrentView == MODELSVIEW)
                SendValue(ModelsView_ModelNumber, ModelNumber);
            if (CurrentView == REVERSEVIEW)
                StartReverseView();
            if (CurrentView == DATAVIEW)
                ForceDataRedisplay();
            if (CurrentView == PONGVIEW)
                StartPong();

            if (CurrentView == MIXESVIEW)
            {
                if (MixNumber == 0)
                    MixNumber = 1;
                LastMixNumber = 33;                        // just to be differernt
                SendValue(MixesView_MixNumber, MixNumber); // New load of mix window
                ShowMixValues();
            }

            if (CurrentView == CALIBRATEVIEW)
            {
                Force_ReDisplay();
                ShowServoPos();
            }

            if ((CurrentView == STICKSVIEW) || (CurrentView == FRONTVIEW))
            {
                Force_ReDisplay();
                ShowServoPos();
                if (CurrentView == FRONTVIEW)
                {
                    ForceVoltDisplay = true;
                    LastConnectionQuality = 0;
                    GotoFrontView(); // (it shows the picture)
                }
            }

            if (CurrentView == LOGVIEW)
            {
                GotoFrontView(); // otherwise it goes round for ever ... might fix later
            }

            if (CurrentView == CHOOSEIMAGEVIEW)
            {
                StartChooseImage();
                ClearText();
                return;
            }
            if (CurrentView == RXSETUPVIEW)
            {
                SendCommand(pRXSetupView);
                return;
            }
            if (HelpTookRead)
            { // B19: a Rotorflight page was still reading when Help was tapped: what came went to a page not showing, and the
              // screen brought the old numbers back as if they were fresh (Save would have written them). Read again.
                HelpTookRead = false;
                if (CurrentView == PIDVIEW)
                    ShowPIDBank();
                else if (CurrentView == RATESVIEW_RF)
                    ShowRatesBank();
                else if (CurrentView == PIDADVANCEDVIEW)
                    ShowPIDAdvancedBank();
                else if (CurrentView == RATESADVANCEDVIEW)
                    ShowRatesAdvancedBank();
                else if (CurrentView == RFGOVERNORVIEW_PROFILE)
                    ShowGOVBank();
                else if (CurrentView == RFGOVERNORVIEW_GLOBAL)
                    ShowGOV_Global_Bank();
            }
            // B43 (Malcolm, 6 Oct 2026: "on returning from help, it goes all the way back to the front screen, which it
            // should not do"): every other page stays where help was opened. The page has been sent back already, and the
            // screen gives it every value it had (the Rotorflight pages' included). Only an unknown view goes to the front.
            if (CurrentView > 0 && CurrentView < 90)
            {
                ClearText();
                return;
            }
            GotoFrontView(); // (a view we do not know: the front page rather than going round for ever)
            ClearText();
            return;
        }

        if (InStrng(Exrite, TextIn) > 0)
        { // ******************* the curve page: one of its three switches tapped, or its expo slider moved
            // B115 (Malcolm, 17 Oct 2026: "after selecting Straight, I cannot afterwards select Smooth or Exponential"): the
            // tapped switch is the one now ON that is not the type already chosen. Before, the last switch asked (Lines) won
            // whenever two were on - which the screen left so until 1.11.81 - and a read that failed (65535) counted as on.
            static_assert(STRAIGHTLINES == 0 && SMOOTHEDCURVES == 1 && EXPONENTIALCURVES == 2, "the switches are asked in that order");
            uint8_t &Type = InterpolationTypes[Bank][ChanneltoSet - 1];
            const bool On[3] = {GetValue(Lines) == 1, GetValue(Smooth) == 1, GetValue(ExpR) == 1};
            for (uint8_t t = 0; t < 3; ++t)
            {
                if (On[t] && t != Type)
                {
                    Type = t;
                    break;
                }
            }
            const uint32_t Ex = GetValue(Expo); // the number shown (-50 to 150: the slider less 50)
            if (Ex != 65535)                    // (a read that failed leaves the expo as it was)
                Exponential[Bank][ChanneltoSet - 1] = Ex + 50; // Note: Getting this value from slider was not reliable (could not return 36!)
            ClearText();
            DisplayCurveAndServoPos();
            return;
        }

        if (InStrng(SendModel, TextIn) > 0)
        {
            i = strlen(SendModel);
            j = 0;
            while (uint8_t(TextIn[i]) > 0)
            {
                SingleModelFile[j] = TextIn[i];
                ++j;
                ++i;
                SingleModelFile[j] = 0;
            }

            strcpy(PromtBeforeSendingModelFile, "Send '");
            strcat(PromtBeforeSendingModelFile, SingleModelFile);
            strcat(PromtBeforeSendingModelFile, "' now?\r\n\r\nIf the model has changed,\r\nback it up first.");

            if (!GetConfirmation(pModelsView, PromtBeforeSendingModelFile))
            {
                ClearText();
                return;
            }
            else // OK was pressed
            {
                SendModelFile();
                ClearText();
                return;
            }
        }
        if (InStrng(FailSAVE, TextIn) > 0)
        { //  the FAILSAFE setup is sent to receiver ************** FAILSAFE SETUP **************

            if (!BoundFlag || !ModelMatched)
            {
                MsgBox(pFailSafe, NotConnected);
                ClearText();
                SendCommand(ProgressEnd);
                return;
            }

            SendCommand(ProgressStart);
            for (int i = 0; i < 16; ++i)
            {
                {
                    const uint32_t gv = GetValue(fs[i]);
                    if (gv != 65535)   // B156: a reply that never came is not a failsafe setting
                        FailSafeChannel[i] = gv;
                }
                SendValue(Progress, i * 100 / 16);
            }
            SendValue(Progress, 100);
            AddParameterstoQueue(FAILSAFE_SETTINGS); // 1 is the ID for the FAILSAFE parameters
            ClearText();
            SendCommand(ProgressEnd);
            return;
        }

        if (InStrng(FailSafe, TextIn) > 0)
        {
            SendCommand(pFailSafe);
            CurrentView = FAILSAFE_VIEW;
            UpdateButtonLabels();
            UpdateModelsNameEveryWhere();
            ClearText();
            return;
        }

        if (InStrng(OneSwitchView, TextIn) > 0)
        {
            SwitchEditNumber = GetChannel(); // which switch?
            CurrentView = ONE_SWITCH_VIEW;
            SendCommand(PageOneSwitchView);
            UpdateOneSwitchView();
            UpdateModelsNameEveryWhere();
            ClearText();
            return;
        }

        if (InStrng(SwitchesView1, TextIn) > 0)
        { //  read switch values from screen (could be 1-4)
            ReadNewSwitchFunction();
        }

        if (InStrng(InputsView, TextIn) > 0)
        {
            if (ModelMatched) //  model is connected warning
            {
                if (!GetConfirmation(pRXSetupView, IsConnected))
                {
                    ClearText();
                    return;
                }
            }
            SendCommand(pInputsView);
            CurrentView = INPUTS_VIEW;
            UpdateButtonLabels();
            UpdateModelsNameEveryWhere();
            ClearText();
            return;
        }

        if (InStrng(CH1NAME, TextIn) > 0)
        {
            p = InStrng(CH1NAME, TextIn);
            i = p + 7;
            DoNewChannelName(1, i);
            ClearText();
            return;
        }
        if (InStrng(CH2NAME, TextIn) > 0)
        {
            p = InStrng(CH2NAME, TextIn);
            i = p + 7;
            DoNewChannelName(2, i);
            ClearText();
            return;
        }
        if (InStrng(CH3NAME, TextIn) > 0)
        {
            p = InStrng(CH3NAME, TextIn);
            i = p + 7;
            DoNewChannelName(3, i);
            ClearText();
            return;
        }
        if (InStrng(CH4NAME, TextIn) > 0)
        {
            p = InStrng(CH4NAME, TextIn);
            i = p + 7;
            DoNewChannelName(4, i);
            ClearText();
            return;
        }
        if (InStrng(CH5NAME, TextIn) > 0)
        {
            p = InStrng(CH5NAME, TextIn);
            i = p + 7;
            DoNewChannelName(5, i);
            ClearText();
            return;
        }
        if (InStrng(CH6NAME, TextIn) > 0)
        {
            p = InStrng(CH6NAME, TextIn);
            i = p + 7;
            DoNewChannelName(6, i);
            ClearText();
            return;
        }
        if (InStrng(CH7NAME, TextIn) > 0)
        {
            p = InStrng(CH7NAME, TextIn);
            i = p + 7;
            DoNewChannelName(7, i);
            ClearText();
            return;
        }
        if (InStrng(CH8NAME, TextIn) > 0)
        {
            p = InStrng(CH8NAME, TextIn);
            i = p + 7;
            DoNewChannelName(8, i);
            ClearText();
            return;
        }
        if (InStrng(CH9NAME, TextIn) > 0)
        {
            p = InStrng(CH9NAME, TextIn);
            i = p + 7;
            DoNewChannelName(9, i);
            ClearText();
            return;
        }
        if (InStrng(CH10NAME, TextIn) > 0)
        {
            p = InStrng(CH10NAME, TextIn);
            i = p + 8;
            DoNewChannelName(10, i);
            ClearText();
            return;
        }
        if (InStrng(CH11NAME, TextIn) > 0)
        {
            p = InStrng(CH11NAME, TextIn);
            i = p + 8;
            DoNewChannelName(11, i);
            ClearText();
            return;
        }
        if (InStrng(CH12NAME, TextIn) > 0)
        {
            p = InStrng(CH12NAME, TextIn);
            i = p + 8;
            DoNewChannelName(12, i);
            ClearText();
            return;
        }
        if (InStrng(CH13NAME, TextIn) > 0)
        {
            p = InStrng(CH13NAME, TextIn);
            i = p + 8;
            DoNewChannelName(13, i);
            ClearText();
            return;
        }
        if (InStrng(CH14NAME, TextIn) > 0)
        {
            p = InStrng(CH14NAME, TextIn);
            i = p + 8;
            DoNewChannelName(14, i);
            ClearText();
            return;
        }
        if (InStrng(CH15NAME, TextIn) > 0)
        {
            p = InStrng(CH15NAME, TextIn);
            i = p + 8;
            DoNewChannelName(15, i);
            ClearText();
            return;
        }
        if (InStrng(CH16NAME, TextIn) > 0)
        {
            p = InStrng(CH16NAME, TextIn);
            i = p + 8;
            DoNewChannelName(16, i);
            ClearText();
            return;
        }

        if (InStrng(DelFile, TextIn) > 0)
        { // Delete a MOD file
            p = InStrng(DelFile, TextIn);
            DeleteMODfile(p);
            return;
        }
        if (InStrng((char *)"TIME=", TextIn) > 0)
        { // V2 B30: the screen's true time, from the internet (local seconds since 1970): set the clock by it, as by a phone's
            p = InStrng((char *)"TIME=", TextIn);
            TimeFromScreen(TextIn + p + 4);
            ClearText();
            return;
        }
        if (InStrng((char *)"ldrcpipe=", TextIn) > 0)
        { // B41: the screen's Bluetooth pipe to the receiver: 0 off, 1 joining, 2 ready, 3 failed
            p = InStrng((char *)"ldrcpipe=", TextIn);
            {
                const uint8_t was = PipeState;
                PipeState = (uint8_t)CheckRange(atoi(TextIn + p + 8), 0, 3);
                ShowPipeState();
                if (PipeState == 2 && was != 2) RfPipeBack();   // B80: a page left unread reads now
            }
            ClearText();
            return;
        }
        if (InStrng((char *)"ldrctel ", TextIn) > 0)
        { // B41: the block the receiver holds, by the pipe, as telemetry items
            p = InStrng((char *)"ldrctel ", TextIn);
            TelemetryFromPipe(TextIn + p + 7);
            ClearText();
            return;
        }
        if (InStrng((char *)"ldrcadj", TextIn) > 0)
        { // B75: the adjustments page is on the screen again (from the keypad, a question, or just opened): its bar drawn afresh
            JobsPageBack();   // (B140)
            ClearText();
            return;
        }
        if (InStrng((char *)"ldrcrcv", TextIn) > 0)
        { // B107: the rates curves page is on the screen (opened, back from Help or the screen saver): its curves drawn afresh
            RatesCurvesPageBack();
            ClearText();
            return;
        }
        if (InStrng((char *)"ldrcrep ", TextIn) > 0)
        { // B50: the receiver's answer to one of our own requests over the pipe (PipeHttp.h)
            p = InStrng((char *)"ldrcrep ", TextIn);
            PipeReplyFromScreen(TextIn + p + 7);
            ClearText();
            return;
        }

        if (InStrng(SwitchesView, TextIn))
        {
            SendCommand(pSwitchesView);
            UpdateSwitchesView(); // display saved values
            CurrentView = SWITCHES_VIEW;
            UpdateModelsNameEveryWhere();
            ClearText();
            return;
        }

        if (InStrng(CalibrateView, TextIn))
        {
            if (LedWasGreen)
            {
                MsgBox(pTXSetupView, (char *)"The model is connected.\r\nSwitch it off, then press Calibrate.");
                ClearText();
                return;
            }

            SendCommand(pCalibrateView);
            Force_ReDisplay();
            CurrentView = CALIBRATEVIEW;
            ClearText();
            return;
        }

        if (InStrng(Export, TextIn))
        {
            GetDefaultFilename();
            if (GetBackupFilename(pModelsView, SingleModelFile, ModelName, hhead, fprompt))
            {
                FixFileName();
                if (CheckFileExists(SingleModelFile))
                {
                    strcpy(Prompt, overwr);
                    strcat(Prompt, SingleModelFile);
                    strcat(Prompt, ques);
                    if (GetConfirmation(pModelsView, Prompt))
                    {
                        WriteBackup();
                    }
                }
                else
                {
                    WriteBackup();
                }
            }
            strcpy(MOD, ".MOD");
            BuildDirectory();
            strcpy(Mfiles, "Mfiles");
            LoadFileSelector();
            ClearText();
            return;
        }

        p = InStrng(Import, TextIn);
        if (p > 0)
        {
            j = 0;
            i = p + 5;
            while (TextIn[i] > 0)
            {
                SingleModelFile[j] = toUpperCase(TextIn[i]);
                ++j;
                ++i;
                SingleModelFile[j] = 0;
            }
            strcpy(Prompt, overwr);
            strcat(Prompt, ModelName);
            strcat(Prompt, ques);
            if (GetConfirmation(pModelsView, Prompt))
            {
                SendCommand(ProgressStart);
                DelayWithDog(10);
                SendValue(Progress, 5);
                DelayWithDog(10);
                if (InStrng(ModExt, SingleModelFile) == 0)
                    strcat(SingleModelFile, ModExt);
                SingleModelFlag = true;
                SendValue(Progress, 10);
                DelayWithDog(10);
                CloseModelsFile();
                ReadOneModel(1);
                SendValue(Progress, 50);
                DelayWithDog(10);
                SingleModelFlag = false;
                CloseModelsFile();
                SendValue(Progress, 75);
                DelayWithDog(10);
                SaveAllParameters();
                CloseModelsFile();
                UpdateModelsNameEveryWhere();
                SendValue(Progress, 100);
                DelayWithDog(10);
                SendCommand(ProgressEnd);
                DisplayModelImage();
                if (FileError)
                    ShowFileErrorMsg();
                DelayWithDog(150); // ClaudeFix-14-7-2026 let the display finish the image redraw before the big list command
                LoadModelSelector();
            }
            ClearText();
            // Look1("Importing model file: "); //here import.
            // Look(SingleModelFile);
            return;
        }

        if (InStrng(SetupCol, TextIn) > 0)
        { // This is  return fr Colours setup
            HighlightColour = GetOtherValue((char *)"High.pco");
            ForeGroundColour = GetOtherValue((char *)"Example.pco");
            BackGroundColour = GetOtherValue((char *)"Fm.bco");
            SpecialColour = GetOtherValue(Fm_pco);
            SendValue(FrontView_BackGround, BackGroundColour);
            SendValue(FrontView_ForeGround, ForeGroundColour);
            SendValue(FrontView_Special, SpecialColour);
            SendValue(FrontView_Highlight, HighlightColour);
            SaveTransmitterParameters();
            CurrentView = TXSETUPVIEW;
            SendCommand(pTXSetupView);
            LastTimeRead = 0;
            UpdateModelsNameEveryWhere();
            ClearText();
            return;
        }

        if (InStrng(TypeView, TextIn) > 0)
        {
            SendCommand(pTypeView);
            SendValue(r2s, 0); // Zero all RX batt cell count
            SendValue(r3s, 0);
            SendValue(r4s, 0);
            SendValue(r5s, 0);
            SendValue(r6s, 0);
            SendValue(r12s, 0);
            SendValue(r0, 0);
            SendValue(r1, 0);
            if (RXCellCount == 2)
                SendValue(r2s, 1); // Then update RX batt cell count
            if (RXCellCount == 3)
                SendValue(r3s, 1);
            if (RXCellCount == 4)
                SendValue(r4s, 1);
            if (RXCellCount == 5)
                SendValue(r5s, 1);
            if (RXCellCount == 6)
                SendValue(r6s, 1);
            if (RXCellCount == 12)
                SendValue(r12s, 1);
            if (TXLiPo)
                SendValue(r1, 1);
            else
                SendValue(r0, 1);

            ClearText();
            UpdateModelsNameEveryWhere();
            return;
        }

        if (InStrng(RXBAT, TextIn) > 0)
        { // UPdate RX batt cell count
            if (GetValue(r2s) == 1)
                RXCellCount = 2;
            if (GetValue(r3s) == 1)
                RXCellCount = 3;
            if (GetValue(r4s) == 1)
                RXCellCount = 4;
            if (GetValue(r5s) == 1)
                RXCellCount = 5;
            if (GetValue(r6s) == 1)
                RXCellCount = 6;
            if (GetValue(r12s) == 1)
                RXCellCount = 12;
            if (GetValue(r0) == 1)
                TXLiPo = false; // TX LIFE
            if (GetValue(r1) == 1)
                TXLiPo = true; // TX LIPO
            SaveAllParameters();
            ClearText();
            return;
        }

        if (InStrng(TrimView, TextIn) > 0)
        { // TrimView just appeared, so update it.
            StartTrimView();
            return;
        }

        if (InStrng(TRIMS50, TextIn) > 0)
        {
            for (i = 0; i < 16; ++i) // ClaudeFix-2-7-2026 was < 15: channel 16's trim never reset
            {
                Trims[Bank][i] = 80; // Mid value is 80
            }
            if (CopyTrimsToAll)
            {
                for (i = 0; i < 15; ++i)
                {
                    for (int fm = 1; fm <= BanksCount(); ++fm) // (B131: six when the model uses them)
                    {
                        Trims[fm][i] = 80;
                    }
                }
            }
            ClearText();
            return;
        }

        if (InStrng(Setup, TextIn) > 0)
        { // Which channel to setup ... Goes to GraphView
            ChanneltoSet = GetChannel();
            CurrentView = GRAPHVIEW;
            SendCommand(pGraphView); // Set to GraphView
            DisplayCurve();
            updateInterpolationTypes();
            UpdateModelsNameEveryWhere();
            SendValue(CopyToAllBanks, 0);
            ClearText();
            return;
        }

        if (InStrng(Front_View, TextIn))
        {
            // B92 (Malcolm, 10 Oct, after an update: "it returned to the front screen but without the image of the model"):
            // no page says "FrontView" - the screen does, after its own restart (an update with new card files restarts it),
            // having put its last page back from its card. That page has none of what this board wrote on it, and the front
            // page's own preinitialize hides the picture (vis exp0,0). So: the whole front page, as GotoFrontView makes it -
            // the picture, the trims, the bank, the names - and the page itself, should the screen have put back another.
            PreviousBank = 250; // sure to be different
            BankSoundHeld = true; // B147: the redraw must not SAY the bank - nothing changed (Malcolm, 27 Oct: "Bank 4!" after every update)
            GotoFrontView();
            return;
        }

        if (InStrng(Sticks_View, TextIn))
        {
            SendCommand(pSticksView);
            Force_ReDisplay();
            CurrentView = STICKSVIEW;
            SendCommand(pSticksView); // Set to SticksView
            UpdateModelsNameEveryWhere();
            UpdateButtonLabels();
            ClearText();
            return;
        }

        if (InStrng(ReScan, TextIn))
        {
            DrawFhssBox();
            DoScanInit();
            ClearText();
            return;
        }

        if (InStrng(MIXES_VIEW, TextIn))
        { // First call to load screen
            SendCommand(pMixesView);
            CurrentView = MIXESVIEW;
            UpdateModelsNameEveryWhere();
            if (MixNumber == 0)
                MixNumber = 1;
            LastMixNumber = MixNumber;
            SendValue(MixesView_MixNumber, MixNumber); // New load of mix window
            ShowMixValues(); // B05: the values were just SENT to the page - reading them back here took the touch word for data and changed the mix
            FixCHNames();
            ClearText();
            return;
        }
        if (InStrng(Mixes_View, TextIn))
        { // Mix number OR a parameter has changed
            CurrentView = MIXESVIEW;
            uint8_t ThisMixNumber = MixNumber; // save it
            {
                const uint32_t gv = GetValue(MixesView_MixNumber);
                if (gv != 65535)   // B156: a reply that never came is not a mix number (it indexes the mixes)
                    MixNumber = gv;
            }
            if (LastMixNumber != MixNumber) // Did number change?
            {
                SendCommand(invisb1);
                SendCommand(invisb0);
                LastMixNumber = MixNumber; // save new mix number
                MixNumber = ThisMixNumber; // Force back to old number to grab last lot before doing new one
                ReadMixValues();           // Read them from screen
                SaveOneModel(ModelNumber); // Save them to SD card
                MixNumber = LastMixNumber; // back to new one
                ShowMixValues();           // show new lot
                SendCommand(visb1);
                SendCommand(visb0);
            }
            else
            {
                ReadMixValues(); //
            }
            FixCHNames();
            ClearText();
            return;
        }

        if (InStrng(Graph_View, TextIn))
        {
            CurrentView = GRAPHVIEW;
            ClearText();
            return;
        }

        if (InStrng(Data_View, TextIn))
        {
            CurrentView = DATAVIEW;
            LastShowTime = 0;
            ForceDataRedisplay();
            SendCommand(pDataView);
            ClearText();
            return;
        }

        if (InStrng(FM1, TextIn))
        {
            Bank = 1;
            PreviousBank = 1;
            UpdateModelsNameEveryWhere();
            ClearText();
            return;
        }

        if (InStrng(FM2, TextIn))
        {
            Bank = 2;
            PreviousBank = 2;
            UpdateModelsNameEveryWhere();
            ClearText();
            return;
        }

        if (InStrng(FM3, TextIn))
        {
            Bank = 3;
            PreviousBank = 3;
            UpdateModelsNameEveryWhere();
            ClearText();
            return;
        }

        if (InStrng(FM4, TextIn))
        {
            Bank = 4;
            PreviousBank = 4;
            UpdateModelsNameEveryWhere();
            ClearText();
            return;
        }

        if (InStrng(Reset, TextIn)) // Now zeros EXPO only (the curve page's "Zero expo"; B135: its Reset and Flat are CurveResetTapped / CurveFlatTapped)
        {
            Exponential[Bank][ChanneltoSet - 1] = DEFAULT_EXPO;
            InterpolationTypes[Bank][ChanneltoSet - 1] = EXPONENTIALCURVES; // expo = default
            DisplayCurveAndServoPos();
            return;
        }

        p = (InStrng(ClickX, TextIn)); // Clicked to move point?
        if (p > 0)
        {
            XtouchPlace = GetNextNumber(p + 7, TextIn);
            // This drops through to get Y as well before moving the point
        }
        p = (InStrng(ClickY, TextIn)); // Clicked to move point?
        if (p > 0)
        {
            YtouchPlace = GetNextNumber(p + 7, TextIn);
            MovePoint();
            DisplayCurveAndServoPos();
            return;
        }
        if (CurrentMode == NORMAL)
        {
            if (strcmp(TextIn, "Calibrate1") == 0)
            {
                Look("Starting calibration");
                BlueLedOn();
                SetDefaultValues(true);
                ResetSwitchNumbers();
                ReduceLimits(); // Get setup for sticks calibration (B17: nothing is saved until Finish, so OK part way can put the card's values back)
                CurrentMode = CALIBRATELIMITS;
                CurrentView = CALIBRATEVIEW;
                SendText1(SvT11, CMsg1);
                SendText(SvB0, CMsg2);
                ClearText();
                BlueLedOn();
                return;
            }
        }

        if (CurrentMode == CALIBRATELIMITS)
        {
            if (strcmp(TextIn, "Calibrate1") == 0)
            {
                CurrentMode = CENTRESTICKS;
                CurrentView = CALIBRATEVIEW;
                SendText1(SvT11, Cmsg3);
                SendText(SvB0, Cmsg4);
                ClearText();
                return;
            }
        }
        if (CurrentMode == CENTRESTICKS)
        {
            if (strcmp(TextIn, "Calibrate1") == 0)
            {
                CurrentMode = NORMAL;
                RedLedOn();
                SaveTransmitterParameters(); // Save calibrations
                LoadAllParameters();         // Restore all current model settings
                SendText(SvB0, Cmsg5);
                {
                    char note[100];
                    NewCompressNeeded = false; // (as ChannelCentres: nothing is being sent)
                    GetNewChannelValues();     // B124: the outputs as the model, read back, makes them now
                    CalibrationNote(note, sizeof(note));
                    SendText(SvT11, note);
                }
                LastTimeRead = 0;
                ClearText();
                return;
            }
        }
    }
    ClearText(); // Let's have cleared text for next one!
} // end ButtonWasPressed() (... at last!!!)

/*************************************************************************************************************
 *************************************************************************************************************
 *************************************************************************************************************
 *************************************************************************************************************
 *************************************************************************************************************
 *************************************************************************************************************
 *************************************************************************************************************
 *************************************************************************************************************
 *************************************************************************************************************
 *************************************************************************************************************
 *************************************************************************************************************
 *************************************************************************************************************
 *************************************************************************************************************
 ************************************************************************************************************/

uint16_t MakeTwobytes(bool *f)
{                    // Pass arraypointer. Returns the two bytes
    uint16_t tb = 0; // all false is default
    for (int i = 0; i < 16; ++i)
    {
        if (f[15 - i] == true)
        {
            tb |= 1 << (i);
        } // sets a bit if true
    }
    return tb;
}

/************************************************************************************************************/

void CheckMotorOff()
{ // For Safety

    if (!UseMotorKill)
        return;

    ReadTheSwitchesAndTrims();
    MotorEnabled = false;
    SafetyON = false;

    // B12: the same reading as in flight (GetSwitchPosition: both contacts, reversal included) for all eight switches. The old
    // private pin table was wrong for switches 3 and 4 and for a reversed 1 or 2: a false "motor still ON", or a false pass.
    if (Autoswitch >= 1 && Autoswitch <= 8)
    {
        const uint8_t p = GetSwitchPosition(Autoswitch);
        if (p == 1 || p == 2) // as ReadAutoAndMotorSwitch(): positions 1 and 2 are motor ON, 3 is OFF
            MotorEnabled = true;
    }
    if (SafetySwitch >= 1 && SafetySwitch <= 8 && GetSwitchPosition(SafetySwitch) != 3)
        SafetyON = true; // as ReadSafetySwitch(): any position but 3 is safety ON

    if (SafetyON)
        MotorEnabled = false;

    MotorWasEnabled = MotorEnabled;
}

/************************************************************************************************************/
void ResetMotorTimer()
{
    char FrontView_Hours[] = "Hours";
    char FrontView_Mins[] = "Mins";
    char FrontView_Secs[] = "Secs";

    TimesUp = false;
    PausedSecs = 0;
    CountDownIndex = 0;
    if (CurrentView == FRONTVIEW)
    {
        if (TimerDownwards)
        {
            Mins = TimerStartTime / 60;
        }
        else
        {
            Mins = 0;
        }
        SendValue(FrontView_Secs, 0);
        SendValue(FrontView_Mins, Mins);
        SendValue(FrontView_Hours, 0);
    }
}

/************************************************************************************************************/
void GetBank() // ... and the other three switches
{
    CRUMB(CRUMB_BANK);
    if ((CurrentMode != NORMAL) && (CurrentMode != LISTENMODE))
        return; // not needed if calibrating

    if ((!BuddyPupilOnWireless) || (BuddyHasAllSwitches))
    { // if BuddyPupilOnWireless is not using switches
        ReadSafetySwitch();
        ReadBuddySwitch();
        ReadBankSwitch();
        ReadAutoAndMotorSwitch();
        if (SendNoData && !MotorEnabled && !BuddyPupilOnWireless)
            SendNoData = false; // B03: the motor switch is seen OFF: the silence after "please turn it off" ends here (the forced-off left no change for MotorEnabledHasChanged to notice)
    }

    ReadDualRateSwitch(); // only actually read hardware switches if not using wireless buddy box or if buddy has all switches

    if (SafetyWasOn != SafetyON)
        SafetySwitchChanged();
    if (SafetyON)
        MotorEnabled = false;
    if ((MotorEnabled != MotorWasEnabled) && (UseMotorKill))
    {
        MotorEnabledHasChanged();
        PreviousBank = 254; // Force bank change to make sure it redisplays
    }
    ReadChannelSwitches9to12();
    if (Bank != PreviousBank) /// BANK HAS CHANGED ******************************************************************
        BankHasChanged();
    MotorWasEnabled = MotorEnabled; // Remember motor state
    PreviousBank = Bank;            // Remember BANK
}

/************************************************************************************************************/

void GotoFrontView()
{
    char FrontView_Connected[] = "Connected";
    PupilIsAlive = 0;
    MasterIsAlive = 0;
    PipeOff(); // B41: the Rotorflight pages are left: the screen lets go of the receiver's Bluetooth
    AddParameterstoQueue(MSP_ENABLE_TELEMETRY); // 26 = ENABLE telemetry after MSP data has been sent (for MSP data transmission)
    LastAutoModelSelect = true;
    LastCopyTrimsToAll = true;
    OldRate = 235;             // forced different
    ForceVoltDisplay = true;   // force redisplay of voltage
    LastConnectionQuality = 0; // force redisplay of connection quality
                               // if (CurrentView != FRONTVIEW)
                               // {
    if (CurrentView == SCANVIEW)
        DoScanEnd(); // Put transceiver back to normal mode
    if (CurrentView == PONGVIEW)
        ReadOneModel(ModelNumber); // Return to current model
    if (CurrentMode != LISTENMODE)
        CurrentMode = NORMAL;     // Return to normal mode unless in BUDDY listen mode
    SendCommand(pFrontView);      // Set to FrontView
    CurrentView = FRONTVIEW;      // Set to FrontView
    UpdateModelsNameEveryWhere(); // Update model name
    ShowBank();
    LastTimeRead = 0;
    Reconnected = false; // this is to make '** Connected! **' redisplay (in ShowComms())
    LastSeconds = 0;     // This forces redisplay of timer...
    Force_ReDisplay();
    ShowMotorTimer();
    ClearText();
    LastShowTime = 0; // this is to make redisplay sooner (in ShowComms())
    SendText(FrontView_Connected, na);
    SendText((char *)"t4", BankNames[BanksInUse[Bank - 1]]); // show current bank name on front view
    ForceDataRedisplay();
    ShowAMS();
    UpdateTrimView();
    if (BuddyPupilOnWireless)
        StartBuddyListen();
    CurrentView = FRONTVIEW;
    First_RPM_Data = true;
    RestoreBrightness();

    if (TrimMultiplier == 0)
    {

        SendCommand((char *)"vis ch1,0");
        SendCommand((char *)"vis ch2,0");
        SendCommand((char *)"vis ch3,0");
        SendCommand((char *)"vis ch4,0");
        SendCommand((char *)"vis trall,0");
    }
    else
    {
        SendCommand((char *)"vis ch1,1");
        SendCommand((char *)"vis ch2,1");
        SendCommand((char *)"vis ch3,1");
        SendCommand((char *)"vis ch4,1");
        SendCommand((char *)"vis trall,1");
    }
    ShowModelImage(); // the name it has: the question was asked when the model was loaded (V2 B29)
    SendCommand((char *)"vis exp0,1");
    ShowBindingIsEnabled(); // Show binding enabled if it is...
}

/************************************************************************************************************/
bool CheckModelName()
{ // In ModelsView, this function checks correct name is displayed.
  // it returns true if it has changed
    char MMems[] = "MMems";
    char Mfiles[] = "Mfiles";
    char mn[] = "modelname";

    if (NEXTION.available())
        return false; // ClaudeFix-14-7-2026 a button press is waiting -- let it be handled before polling

    {
        const uint32_t mm = GetValue(MMems), mf = GetValue(Mfiles);
        if (mm == 65535 || mf == 65535)   // B156: a reply that never came is not a model number
            return false;
        ModelNumber = mm + 1;
        FileNumberInView = mf;
    }
    if (FileNumberInView != LastFileInView)
    {
        ShowFileNumber();
        LastFileInView = FileNumberInView;
    }
    if (LastModelLoaded != ModelNumber)
    {
        if ((ModelNumber >= MAXMODELNUMBER) || (ModelNumber < 1))
        {
            ModelNumber = 1;
            SendValue(MMems, ModelNumber - 1);
        }
        ReadOneModel(ModelNumber);
        SendText(mn, ModelName);
        LastModelLoaded = ModelNumber;
        UpdateModelsNameEveryWhere();
        DisplayModelImage();
        return true;
    }
    ClearText();
    return false;
}

/************************************************************************************************************/
void Close_TX_Down()
{
    char NotInUse[] = "Not in use";
    char ClosingDown[] = "Switching off ...";
    char Saving[] = "Saving ";
    char msg1[80];
    char t0[] = "t0";
    char msgvis[] = "vis t0,1";
    NoteWhyOff(LedWasGreen ? OFF_BUTTON_CONNECTED : OFF_BUTTON); // V1B: said at the next start (FlightGuard.h)
    PerfWriteReport(true); // V1B B19: the timing of this session survives the power-off (/PERF.TXT and a dated copy in /PERF)
    CrumbClear();          // V1B B20: a clean power-off - the next start must not report a hang
    analogWrite(GREENLED, 0);
    analogWrite(BLUELED, 0);
    analogWrite(REDLED, 0);
    RestoreBrightness();
    SendCommand(pBlankView); // Set to BlankView
    SendCommand(msgvis);     // Make it visible
    if (PlayFanfare)
    {
        PlaySound(WINDOWS2);
    } // Play the fanfare
    if (strcmp(ModelName, NotInUse) != 0)
    { // If model is in use
        strcpy(msg1, Saving);
        strcat(msg1, ModelName); // Build up the message
        SendText(t0, msg1);      // Show 'Saving <model> ' on screen
        SaveAllParameters();     // Save the model if it's not 'Not in use'
        DelayWithDog(500);       // Wait for 0.5 seconds to allow the message to be displayed
    }
    if (UseLog && LedWasGreen)
    { // Powering off with the receiver STILL CONNECTED (the warning countdown
      // path): the log's end-of-session summary would otherwise never be
      // written — and that's the interesting bit (Malcolm, 2026-08-02).
      // Written BEFORE the screen fade so the SD writes happen while
      // everything is still healthy.
        char PoweredOffMsg[] = "Transmitter powered off while still connected";
        LogText(PoweredOffMsg, strlen(PoweredOffMsg), true);
        LogDisConnection(); // the end-of-session summary + LogEndLine
        CloseLogWriteFile();
        strcpy(LogWriteName, ""); // no further logging to this file (B56: the logger's own name)
    }
    SendText(t0, ClosingDown);    // Show 'Switching off ...' on screen
    for (int i = 0; i < 100; ++i) // fade in screen brightness
    {
        SetBrightness(100 - i);
        DelayWithDog(25);
    }
    DelayWithDog(POWERONOFFDELAY);     // 2 seconds delay in case button held down too long
    digitalWrite(POWER_OFF_PIN, HIGH); // Power off the transmitter
    delay(100);                 // Wait for a short time to ensure power off
}
/// ************************************************************************************************************/
void ShowBindingIsEnabled()
{
    if (BindingEnabled)
    {
        char Mfound[] = "Binding enabled";
        char wb[] = "wb"; // wb is the name of the label on front view
        char YesVisible[] = "vis wb,1";
        SendText(wb, Mfound);    // Show binding enabled
        SendCommand(YesVisible); // Show binding enabled
        LedIsBlinking = true;    // Start blinking LED to show binding enabled
        SendText((char *)"OptionsView.b0", (char *)"Stop binding");
    }
}

// ************************************************************************************************************/
void CheckWhetherToEnableBinding()
{
    // This function checks whether binding is being enabled for this transmitter.
    // This is done by holding down the power button for two seconds at the start up.

    if (!digitalRead(BUTTON_SENSE_PIN) && !ButtonUpSinceBoot && (millis() >= 2000)) // To initiate Binding, keep the ON button held from switch-on for 2 s (B95: however long it stays held)
    {
        if (!BindingEnabled)
        {
            SendCommand(pFrontView);      // Go to front view
            CurrentView = FRONTVIEW;      // Set to FrontView
            UpdateModelsNameEveryWhere(); // Update model name
            if (AudioVolume < 50)
            { // B95 (Malcolm): "if sound volume is zero we hear nothing" - this announcement plays at half volume at least; the pilot's volume comes back 5 s later (the once-a-second chores)
                SetAudioVolume(50);
                VolumeRestoreAt = millis() + 5000;
            }
            Force_Early_Sound = true;     // Force sound to play
            PlaySound(BEEPCOMPLETE);      // Play sound to indicate binding enabled
            delay(500);                   // Wait for chirp to finish
            Force_Early_Sound = true;     // Force sound to play
            PlaySound(BINDINGENABLED);    // Play sound to indicate binding enabled
            BindingEnabled = true;        // Set binding enabled flag
            ShowBindingIsEnabled();       // Show binding enabled
        }
        return;
    }
}

/************************************************************************************************************/
void CheckPowerOffButton()
{
    CRUMB(CRUMB_POWERBUTTON);
    static bool CheckingPowerButton = false;
    static bool PowerWarningVisible = false;
    static uint32_t PowerOffTimer = 0;
    static uint8_t TurnOffSecondToGo = PowerOffWarningSeconds;
    char PowerMsg[30];
    char PowerPre[] = "TURN OFF?! ";
    char nb[8];
    char HideStillConnected[] = "vis StillConnected,0";
    char ShowStillConnected[] = "vis StillConnected,1";
    char StillConnectedBox[] = "StillConnected";

    if (CheckingPowerButton) // already checking power button
        return;
    if (digitalRead(BUTTON_SENSE_PIN))
        ButtonUpSinceBoot = true; // B95: let go at least once since switch-on - only then can a press switch off
    if (digitalRead(BUTTON_SENSE_PIN) && !PowerOffTimer && !PowerWarningVisible)
        return; // button not even pressed, and nothing to put back (B01: a release must reach the branch below that cancels the countdown and hides the box)
    CheckingPowerButton = true; // set flag to prevent re-entry
    if (!BuddyMasterOnWireless && !BuddyPupilOnWireless && SD_Card_Exists)
        CheckWhetherToEnableBinding(); // Check if binding is enabled Which is done by holding the start button for more than two seconds

    if ((!digitalRead(BUTTON_SENSE_PIN)) && (millis() > POWERONOFFDELAY2) && ButtonUpSinceBoot) // no power off in the first seconds, nor while the button has been held since switch-on (B95: that hold enables binding, however long - it used to switch off at 4 s, often before 'Binding enabled' had been heard)
    {                                                                      // power button is pressed!
        if (BoundFlag && ModelMatched && CurrentView != FRONTVIEW)
            GotoFrontView();

        if (!LedWasGreen)
            Close_TX_Down(); // if not connected power off immediately

        if (LedWasGreen)
        {
            if (!PowerOffTimer)
            {
                PowerOffTimer = millis(); // Start a timer for power off button down
                TurnOffSecondToGo = PowerOffWarningSeconds;
            }
        }
    }
    else
    {
        PowerOffTimer = 0;
        TurnOffSecondToGo = PowerOffWarningSeconds;
    }

    if (PowerOffTimer)
    { // count down started
        if (!PowerWarningVisible)
        {
            SendCommand(ShowStillConnected);
            SaveOneModel(ModelNumber); // in case any trim change etc wasn't saved (not really needed)
            PowerWarningVisible = true;
        }
    }
    else
    {
        if (PowerWarningVisible)
        {
            SendCommand(HideStillConnected);
            PowerWarningVisible = false;
            TurnOffSecondToGo = PowerOffWarningSeconds;
        }
        CheckingPowerButton = false;
        return;
    }

    if (PowerWarningVisible)
    {
        if ((millis() - PreviousPowerOffTimer) >= 1000)
        {
            strcpy(PowerMsg, PowerPre);
            Str(nb, TurnOffSecondToGo, 0);
            strcat(PowerMsg, nb);
            SendText(StillConnectedBox, PowerMsg);
            PowerCountdownShownAt = millis(); // V1B B24: ShowAmpsBeingUsed() writes into the same box: not over the countdown
            if (TurnOffSecondToGo <= 0)
            { // Time's up!
                Close_TX_Down();
            }
            --TurnOffSecondToGo;
            if (TrimClicks)
                PlaySound(CLICKZERO);
            PreviousPowerOffTimer = millis();
        }
    }
    CheckingPowerButton = false;
}
// /************************************************************************************************************/
// This function checks if the model name has changed in ModelsView
void CheckModelsScreen(uint32_t RightNow)
{
    static uint32_t LastModelScreenCheck = 0;
    if (RightNow - LastModelScreenCheck < 500)
        return; // Only check once every 500 ms
    LastModelScreenCheck = RightNow;
    if (CheckModelName())
        LastModelScreenCheck = RightNow;
}
//************************************************************************************************************/
void CheckMaxCurrent() // heer
{
    CRUMB(CRUMB_MAXCURRENT);
    static bool warned = false;
    if (!LedWasGreen)
    {
        warned = false;
        CurrentWarningShownAt = 0;
        return;
    }
    if (CurrentWarningShownAt && (millis() - CurrentWarningShownAt) > 6000)
    { // B02: the warning is a line in the front page's box for six seconds - never a box that waits for OK while flying (the switches were not read meanwhile)
        CurrentWarningShownAt = 0;
        if (!RotorFlight_V && !BatteryWarningShown && CurrentView == FRONTVIEW)
            SendCommand(WarnOff); // (a Rotorflight model writes its ESC temperature into the box again by itself)
    }
    if (Battery_Amps && Max_Safe_Amps && !warned) // is the current current currently excessive?
    {
        if (Battery_Amps > Max_Safe_Amps)
        {
            PlaySound(WHAHWHAHMSG); // Play sound to indicate there is a Problem.
            if (CurrentView == FRONTVIEW)
            {
                SendCommand(WarnNow);
                SendText(Warning, (char *)"Current too high!");
            }
            CurrentWarningShownAt = millis();
            warned = true;
        }
    }
}

/************************************************************************************************************/
void FASTRUN ManageTransmitter()
{
    static uint32_t TransmitterLastManaged = 0;
    uint32_t RightNow = millis();
    int32_t TXPacketElapsed = RightNow - LastPacketSentTime;
    CheckForNextionButtonPress(); // must be done very frequently to avoid missing button presses. It updates the TextIn string which is used for button press processing.
    KickTheDog();                 // Watchdog ... ALWAYS!

    if ((FHSS_data::PaceMaker - TXPacketElapsed < TIMEFORTXMANAGMENT) && ModelMatched && (RightNow - LastTimeRead) < 3000)
    {
        return; // If it's almost time to send data, then do not start some other task which might easily take longer.
                // (V1B: never for more than 3 s on end - whatever has stopped the packets, the switches, the power
                //  button and the once-a-second chores must go on. See SendData().)
    }
    if (ThisGap)
    {
        ProcessRecentCommsGap();
        return;
    }
    CheckPowerOffButton();

    DoTheVariometer(); // Do the variometer
    RescuePoll();      // B50: a Rotorflight rescue read or save in progress, over the pipe
    ServoPoll();       // B55: the servos page, likewise
    TravelPoll();      // B57: the travel extents pages
    BasicsPoll();      // B99: the model basics pages
    EscCalPoll();      // B100: the ESC throttle calibration page (the hold renewed)
    FilterPoll();      // B58: the filters page
    AdjustPoll();      // B72: the adjustments' MSP state machine (on the Switches and knobs page, B140)
    SwitchPoll();      // B77: the switches'
    JobsPoll();        // B140: the page itself - the read and save sequence, the live marker
    CopyBankPoll();    // B78: a bank being copied
    BatteryPoll();     // B88: the battery page
    BlackboxPoll();    // B88: the black box page
    CalibratePoll();   // B88: the calibrate page
    EasyPoll();        // B104: the Easy tuning page
    RatesCurvePoll();  // B107: the rates curves, a few lines a pass

    if (RightNow - LastTimeRead >= 1000)
    { // Only once a second for these..
        CRUMB(CRUMB_HOUSEKEEPING);
        CrumbView(CurrentView); // B14: the page showing, on the clock's coin cell

        if (VersionMismatch)
        {
            ShowMismatchMsg(); // Show version mismatch message if needed
        }
        if (((millis() - LedGreenMoment) <= 6000) && ((millis() - LedGreenMoment) >= 4000))
        {
            ZeroDataScreen(); // this will clear the long gaps that might occur while binding.
        }
        GetFrameRate();       // Get the frame rate
        CheckScreenTime();    // Check if screen needs to be turned off
        CheckBatteryStates(); // Check battery states
        if (CurrentView != BLANKVIEW)
        {
            ReadTime();
            UpdateTrimView();
            ShowComms();
        } // Show time and trim positions
        CorrectRtcFromPhoneTime(); // apply any phone-true time from ack item 37 (RXV2)
        ShowMotorTimer();          // Show motor timer and send any queued parameters
        TellScreen(true);          // V1B: motor enabled? armed? a model connected? - once a second, whatever page is showing
        if (VolumeRestoreAt && (int32_t)(millis() - VolumeRestoreAt) >= 0)
        { // B95: the binding announcement played at half volume at least; the pilot's own volume comes back
            VolumeRestoreAt = 0;
            SetAudioVolume(AudioVolume);
        }
        TellScreenRx();            // V1B: the receiver's release number, and how its update is going (RxUpdate.h)
        PipeTick();                // B44: the Rotorflight menu's ask for the receiver's Bluetooth, renewed (Parameters.h)
        ClockMessageTick();        // B63: the clock's word, once a trial is over
        CentreNoteTick();          // B126: the centre note, once a trial is over or the model is chosen
        LastTimeRead = millis();   // Reset this timer
        return;                    // That's enough housekeeping for this time around
    }
    PipeFlush();                          // B71: the Rotorflight words, in the queue's order, to the pipe or the backup file
    if (ParametersToBeSentPointer)        // Any parameters to be sent?
        ActuallySendParameters(RightNow); // yes, send them
    if (CurrentView == MODELSVIEW)
        CheckModelsScreen(RightNow);
    if (CurrentView == DUALRATESVIEW)
        CheckDualRatesScreen(RightNow); // live channel names — no Refresh needed

    if (RightNow - TransmitterLastManaged >= 50)
    {                      // 50 = 20 times a second
        CheckMaxCurrent(); // Check if max current has been exceeded
        ReadTheSwitchesAndTrims();
        CheckHardwareTrims();
        GetBank(); // Check switch positions 20 times a second
        TellScreen(false); // V1B: ... and at once when any of it changes
        RxUpdateTick();    // V1B: a receiver update through the transmitter (RxUpdate.h)
        TellScreenRxTick(); // B144: the receiver's line, when the once-a-second one found the port busy
        if (LedIsBlinking && LedWasRed)
            RedLedOn();
        PipeModelGoneTick(); // B90: the model gone, a page's read of the receiver left unanswered: the backup file answers it
        BankSyncTick();      // B143: the bank count told to the receiver, and the warning when the flight controller's selector differs

        if (CurrentView >= PIDVIEW && CurrentView <= RFGOVERNORVIEW_GLOBAL)
        {
            Hide_msg_if_needed(); // Hide any message in rotoflight config area
            FcBankTick();         // B82: which bank the flight controller is really on
            ArmTick();            // B88: why it will not arm, on the Rotorflight menu
        }
        TransmitterLastManaged = millis();
    }
}

/************************************************************************************************************/
void FixMotorChannel()
{
    if (MotorChannel > 15)
        return; // ClaudeFix-2-7-2026 never index SendBuffer OOB, whatever state the config is in
    if (!MotorEnabled && !BuddyState && !BindingEnabled && !BuddyPupilOnWireless)
    {
        SendBuffer[MotorChannel] = IntoHigherRes(MotorChannelZero); // If safety is on, throttle will be zero whatever was shown.
    }
}
//************************************************************************************************************/
void FixArmingChannel()
{
    uint16_t ArmValue[2] = {667, 2233}; // these are the values at the arming switch would give
    // ArmingChannel is range-checked here: it starts life as 0 (and an old or
    // garbled model file can hand back anything), and SendBuffer[0 - 1] wrote
    // 667/2233 into whatever global the linker happened to place just before
    // SendBuffer — EVERY loop pass. Out-of-range now means "do nothing".
    if (RotorFlight_V && !BindingEnabled && !BuddyPupilOnWireless &&
        ArmingChannel >= 1 && ArmingChannel <= CHANNELSUSED)
        SendBuffer[ArmingChannel - 1] = ArmValue[(uint8_t)Armed]; // If safety is on, arming is off UNLESS BINDING!!
}
/************************************************************************************************************/
// LOOP
/************************************************************************************************************/

FASTRUN void loop()
{
    FwTrialTick();         // V1B: firmware on trial is accepted once it has run for 30 seconds
#ifdef LDRC_TEST_FALL_OVER
    if (millis() > 8000)   // TEST BUILDS ONLY (-DLDRC_TEST_FALL_OVER): a firmware that falls over, to prove that the previous one comes back
        for (;;)
        {
        }
#endif
    ManageTransmitter();   // Do the needed chores ... (if there's time)
    GetNewChannelValues(); // Load SendBuffer with new servo positions very frequently

    if (CurrentMode == NORMAL)
    {
        if (UseMacros)
            ExecuteMacro(); // Modify channels if macro is running
        GetBuddyData();     // Only if master
        FixMotorChannel();  // Maybe force motor low BEFORE Binding data is added
        FixArmingChannel(); // Be sure to show correct arming channel value if using RotorFlight options
        ShowServoPos();     // Show servo positions to user
        ShowSwitchPositions(); // B32: the Switches page's up / mid / down (nothing unless that page shows)
        if (BindingEnabled && !BoundFlag)
            SendBindingPipe(); // Only if binding and not bound yet - override low throttle setting
    }

    switch (CurrentMode)
    {
    case NORMAL:    // 0
        SendData(); // local TX
        break;
    case CALIBRATELIMITS: // 1
        CalibrateSticks();
        break;
    case CENTRESTICKS: // 2
        ChannelCentres();
        break;
    case SCANWAVEBAND: // 3
        ScanAllChannels(false);
        break;
    case SENDNOTHING: // 4
        break;
    case PONGMODE: // 5
        PlayPong();
        break;
    case LISTENMODE: // 6 for wireless buddy
        DoWirelessBuddyListen();
        break;
    case SAVE_RF_SETTINGS: // 7 B70: a backup or a restore over the pipe (RF_Backup.h), the link kept going
    case RESTORE_RF_SETTINGS: // 8
        BackupRun();
        SendData();
        break;
    default:
        break;
    }
} // end loop()

/************************************************************************************************************/
