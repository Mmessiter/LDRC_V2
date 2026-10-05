// V1B: two things the screen is told, so that nothing it does can ever cost a model.
// (Malcolm, 29-9-2026: "Priority One is no interruption to control when flying! That is - ZERO crashes! This extends
//  to preserving parameters so that a control works as set rather than backwards.")
//
// 1. WHAT THE TRANSMITTER IS DOING - TellScreen()
//    Once a second, and at once when it changes, the screen is told whether the motor is enabled, whether the safety
//    is off, and whether a model is connected. Until now the screen read this off the front page's "Motor is ON"
//    text, so it only learned of a change while the front page was showing: with another page up, its WiFi stayed
//    on in flight.
//
//    THE RULE FOR THE SCREEN'S RADIOS (Malcolm, 29-9-2026): "Motor ON to kill wifi only if no safety switch was
//    defined. If safety switch is defined then safety off should kill wifi and ble irrespective of motor status."
//    It is decided HERE (RadiosMustBeOff) and sent as one bit, so that the screen never has to know the rule: a
//    rule that changes, changes in this file. The same rule decides whether the file link may open, and the screen
//    offers no update while it holds, nor while a model is connected or was a minute ago.
//
// 2. HOW THIS FIRMWARE READS THE PILOT'S SETTINGS - ControlFingerprint()
//    One number made of everything that decides what the sticks and switches do to the servos, AS THIS FIRMWARE HAS
//    IT IN MEMORY after reading models.dat: end points and curves, mixes, trims, sub-trims, the reversed channels,
//    which stick and which output is which, rates and expo, failsafe, the motor and arming channels, servo pulses,
//    the sticks' calibration, the sticks mode and which switch does what. The screen compares the number given by
//    the firmware that WAS running with the number given by the firmware it has just installed. If they differ, the
//    new firmware reads the pilot's settings differently - a servo reversed, a mix gone, a switch on another
//    channel - and it is not kept: the previous firmware is put back, and the screen says why.
//
//    The values are fed one by one, in a fixed order, each as a 32-bit number: the fingerprint does not depend on
//    how the variables are laid out in memory, only on what they hold. The order below is version 1 and must NEVER
//    change. A firmware that reads MORE settings adds them to a version 2 and says so (the screen compares only
//    fingerprints of the same version, and says when it could not compare).
#ifndef FLIGHT_GUARD_H
#define FLIGHT_GUARD_H

#include <Arduino.h>
#include <EEPROM.h>
#include "1Definitions.h"
#include "LdrcLink.h"

// ---------------------------------------------------------------------------------------------------------------
// 3. WHY THE TRANSMITTER WENT OFF, LAST TIME - NoteWhyOff() / ReadWhyOff()
//    On 30-9-2026 the transmitter switched itself off twice while idle, long before its inactivity time was up,
//    and nothing said why. Now every way out writes one byte to the chip's EEPROM first (the power button, the
//    inactivity power-off, a restart after a restore, a firmware swap), and at the next start that byte is read
//    and cleared. The chip's own record of what reset it (SRC_SRSR: power-on, watchdog, software) is read too.
//    Both go out with the hello (off=, rst=): "off=0 rst=0x1" after an unexplained switch-off means that NONE of
//    the firmware's ways out was taken - the power itself went.
#define OFF_REASON_ADDR 4200 // (the transmitter uses no other EEPROM; the Teensy 4.1 has 4284 bytes)
// (the reasons OFF_... and the prototype of NoteWhyOff() are in 1Definitions.h: transceiver.h needs them before this file)
uint8_t LastOffReason = OFF_NONE;
uint32_t LastResetCause = 0;
void NoteWhyOff(uint8_t why)
{
    if (EEPROM.read(OFF_REASON_ADDR) != why)
        EEPROM.write(OFF_REASON_ADDR, why);
}
// ---------------------------------------------------------------------------------------------------------------
// 4. WHERE THE FIRMWARE WAS WHEN IT LAST STOPPED - the breadcrumb (B14, 30-9-2026)
//    Twice today the transmitter stood still with its power button dead, and the pilot pulled the battery: after
//    that nothing above can say where the code was. Three registers of the chip's SNVS domain live on the clock's
//    coin cell and outlast a pulled battery: LPGPR0 holds a number for the long or blocking place the code is in
//    (a CrumbGuard sets it on the way in and puts the previous one back on the way out - after a hang it still says
//    where), LPGPR1 the uptime at the last kick of the watchdog (so: when it hung), LPGPR2 the page showing. Read at
//    the next start, said in the hello (crumb=N;crumbup=S;crumbview=V) and to the screen, then cleared.
// (the Crumb numbers, CrumbGuard, CRUMB(), CrumbKick and CrumbView live in 1Definitions.h: every header uses them)

void ReadWhyOff() // at start-up, once
{
    LastOffReason = EEPROM.read(OFF_REASON_ADDR);
    if (LastOffReason > OFF_FIRMWARE_SWAP)
        LastOffReason = OFF_NONE; // (an EEPROM never written reads 255)
    if (LastOffReason != OFF_NONE)
        EEPROM.write(OFF_REASON_ADDR, OFF_NONE);
    LastResetCause = SRC_SRSR; // bit 0 power-on, bit 1 a software reset (or a lock-up), bit 7 the watchdog (WDOG3)
    SRC_SRSR = LastResetCause; // (write one to clear: the next start sees only its own cause)
    LastCrumb = (uint8_t)SNVS_LPGPR0;
    if (LastCrumb > CRUMB_LAST)
        LastCrumb = CRUMB_NONE; // (never written: whatever the register held)
    LastCrumbUpMs = SNVS_LPGPR1;
    LastCrumbView = SNVS_LPGPR2;
    // (B20: three register writes timed with the cycle counter, said in the hello as snvs=. The CPU sees almost nothing:
    //  the writes are posted. The cost lands on the NEXT access to the peripheral bus - the serial port's interrupt
    //  among them - which waits for the slow clock domain. Proven by result, not by this number: B19 lost a third of
    //  the screen's link frames, B20 none - 2-10-2026, 348 kB in 128 s with 121 repeats against 6.9 s with 1.)
    const uint32_t t0 = ARM_DWT_CYCCNT;
    SNVS_LPGPR0 = CRUMB_NONE;
    SNVS_LPGPR1 = 0;
    SNVS_LPGPR2 = 0;
    SnvsWriteCycles = ARM_DWT_CYCCNT - t0;
}

#define CONTROL_FINGERPRINT_VERSION 1

static uint32_t FingerprintSoFar = 0;
static inline void Fp(int32_t v)
{
    const uint8_t b[4] = {(uint8_t)v, (uint8_t)(v >> 8), (uint8_t)(v >> 16), (uint8_t)(v >> 24)};
    FingerprintSoFar = ldrc::crc32(b, 4, FingerprintSoFar);
}

// Nothing here changes anything: every variable is only read.
uint32_t ControlFingerprint()
{
    int i, j;
    FingerprintSoFar = 0;
    Fp(CONTROL_FINGERPRINT_VERSION);

    // ---- the model (in the order, and over the ranges, in which ReadOneModel() reads them from the file)
    for (i = 0; i < CHANNELSUSED; ++i)
        for (j = 1; j <= 4; ++j)
        {
            Fp(MaxDegrees[j][i]);
            Fp(MidHiDegrees[j][i]);
            Fp(CentreDegrees[j][i]);
            Fp(MidLowDegrees[j][i]);
            Fp(MinDegrees[j][i]);
        }
    for (j = 0; j < MAXMIXES; ++j)
        for (i = 0; i < CHANNELSUSED + 1; ++i)
            Fp(Mixes[j][i]);
    for (j = 0; j < BANKS_USED + 1; ++j)
        for (i = 0; i < CHANNELSUSED + 1; ++i)
            Fp(Trims[j][i]);
    for (j = 0; j < BANKS_USED + 1; ++j)
        for (i = 0; i < CHANNELSUSED + 1; ++i)
            Fp(ServoSpeed[j][i]);
    Fp(TrimMultiplier);
    Fp(CopyTrimsToAll ? 1 : 0);
    for (i = 0; i < CHANNELSUSED; ++i)
        Fp(SubTrims[i]);
    Fp(ReversedChannelBITS); // which servos turn the other way
    for (i = 0; i < 4; ++i)
        Fp(InputTrim[i]);
    Fp(BuddyControlled);
    for (i = 0; i < CHANNELSUSED; ++i)
        Fp(InPutStick[i]); // which stick moves which channel
    for (i = 0; i < 4; ++i)
        Fp(DualRateRate[i]);
    Fp(ArmingChannel);
    for (i = 0; i < CHANNELSUSED; ++i)
        Fp(FailSafeChannel[i] ? 1 : 0);
    for (j = 0; j < BANKS_USED + 1; ++j)
        for (i = 0; i < CHANNELSUSED + 1; ++i)
            Fp(Exponential[j][i]);
    for (j = 0; j < BANKS_USED + 1; ++j)
        for (i = 0; i < CHANNELSUSED + 1; ++i)
            Fp(InterpolationTypes[j][i]);
    for (j = 0; j < BYTESPERMACRO; ++j)
        for (i = 0; i < MAXMACROS; ++i)
            Fp(MacrosBuffer[i][j]);
    Fp(UseMotorKill ? 1 : 0);
    Fp(MotorChannelZero);
    Fp(MotorChannel);
    Fp(Drate1);
    Fp(Drate2);
    Fp(Drate3);
    for (i = 0; i < 8; ++i)
        Fp(DualRateChannels[i]);
    for (i = 0; i < 4; ++i)
        Fp(BanksInUse[i]);
    for (i = 0; i < 16; ++i)
        Fp(ChannelOutPut[i]); // which channel goes out on which output
    for (i = 0; i < 11; ++i)
    {
        Fp(ServoFrequency[i]);
        Fp(ServoCentrePulse[i]);
    }
    Fp(LinkRatesToBanks ? 1 : 0);
    Fp(RotorFlight_V);

    // ---- the transmitter (as LoadAllParameters() reads them)
    for (i = 0; i < CHANNELSUSED; ++i)
    {
        Fp(ChannelMin[i]); // the sticks' calibration
        Fp(ChannelMidLow[i]);
        Fp(ChannelCentre[i]);
        Fp(ChannelMidHi[i]);
        Fp(ChannelMax[i]);
    }
    Fp(SticksMode);
    for (i = 0; i < 8; ++i)
        Fp(SwitchNumber[i]);
    for (i = 0; i < 8; ++i)
        Fp(TrimNumber[i]);
    Fp(BankSwitch); // which switch does what
    Fp(Autoswitch);
    for (i = 0; i < 4; ++i)
        Fp(TopChannelSwitch[i]);
    for (i = 0; i < 4; ++i)
        Fp(SwitchReversed[i] ? 1 : 0);
    Fp(BuddySwitch);
    Fp(DualRatesSwitch);
    Fp(SafetySwitch);
    return FingerprintSoFar;
}

// "mfp=1.89ABCDEF": part of what the Teensy says of itself when the screen knocks (LinkMode.h).
const char *ControlFingerprintText()
{
    static char text[24];
    snprintf(text, sizeof(text), "mfp=%d.%08lX", CONTROL_FINGERPRINT_VERSION, (unsigned long)ControlFingerprint());
    return text;
}

// ---------------------------------------------------------------------------------------------------------------
// A model that was connected two seconds ago and is not now may be IN THE AIR, out of contact (the red LED comes on
// after 2 s without an answer, and the transmitter then calls itself "not connected" while it tries to get the
// model back). For MODEL_JUST_NOW_MS after the last contact the transmitter could be treated as if the model were
// still there: no file link, no update. Malcolm, 30-9-2026, having tried it: "the additional pause of one minute
// after it disconnected is unnecessary and might be frustrating" - so it is 0, and the bit is never set. (The
// pilot who has just switched his model off is the one pressing the button; a pilot whose model is out of contact
// in the air is not.) The screen understands the bit still, should it ever be wanted again.
#define MODEL_JUST_NOW_MS 0
static bool ModelWasSeen = false;
static uint32_t ModelLastSeenMs = 0;

void NoteModelContact() // called every 50 ms, from TellScreen()
{
    if (BoundFlag && ModelMatched)
    {
        ModelWasSeen = true;
        ModelLastSeenMs = millis();
    }
    else if (ModelWasSeen && (millis() - ModelLastSeenMs) >= (uint32_t)MODEL_JUST_NOW_MS)
    {
        ModelWasSeen = false;
    }
}
bool ModelJustNow() { return ModelWasSeen && !(BoundFlag && ModelMatched); }

// (SafetyON is read from the switch every 50 ms. Armed is NOT used: it is set when the switch MOVES, so a transmitter
//  switched on with its safety already off would not count as armed.)
bool SafetyIsDefined() { return SafetySwitch != 0; }
bool SafetyIsOff() { return SafetyIsDefined() && !SafetyON; }
// Malcolm's rule, in one place:
bool RadiosMustBeOff() { return SafetyIsDefined() ? SafetyIsOff() : MotorEnabled; }

// bit 0 (1):  the motor is enabled
// bit 1 (2):  the safety is off (a safety switch is defined, and it is off)
// bit 2 (4):  a model is connected
// bit 3 (8):  a safety switch is defined
// bit 4 (16): a model was connected less than a minute ago
// bit 5 (32): THE SCREEN'S RADIOS MUST BE OFF (the rule above)
uint8_t ScreenStatusNow()
{
    uint8_t s = 0;
    if (MotorEnabled)
        s |= 1;
    if (SafetyIsOff())
        s |= 2;
    if (BoundFlag && ModelMatched)
        s |= 4;
    if (SafetyIsDefined())
        s |= 8;
    if (ModelJustNow())
        s |= 16;
    if (RadiosMustBeOff())
        s |= 32;
    return s;
}

// Why the file link stays shut, or LE_OK. Flying comes first: the Teensy is a file server OR a transmitter.
uint8_t LinkRefusal()
{
    NoteModelContact();
    if (BoundFlag && ModelMatched)
        return ldrc::LE_BUSY; // a model is connected
    if (ModelJustNow())
        return ldrc::LE_MODEL_JUST_NOW; // ... or was, a moment ago
    if (RadiosMustBeOff())
        return SafetyIsDefined() ? ldrc::LE_SAFETY_OFF : ldrc::LE_MOTOR_ON;
    if (ModalWaits || CurrentMode != NORMAL)
        return ldrc::LE_NOT_NOW; // a question is on screen, or the radio is calibrating or scanning
    return ldrc::LE_OK;
}

// "mfp=1.89ABCDEF;st=8;off=0;rst=0x1": what the Teensy adds when it says who it is (LinkServer::hello).
const char *LinkHelloExtra()
{
    static char text[176];
    snprintf(text, sizeof(text), "%s;st=%u;off=%u;rst=0x%lX;crumb=%u;crumbup=%lu;crumbview=%lu;snvs=%lu;%s", ControlFingerprintText(), (unsigned)ScreenStatusNow(), (unsigned)LastOffReason, (unsigned long)LastResetCause,
             (unsigned)LastCrumb, (unsigned long)(LastCrumbUpMs / 1000), (unsigned long)LastCrumbView, (unsigned long)(SnvsWriteCycles / (F_CPU_ACTUAL / 1000000u)), PerfHelloText());
    return text;
}

// Twelve bytes, written straight to the wire. It never waits (a busy wire: next time), and unlike SendCommand() it
// throws nothing away that may be arriving from the screen at that moment.
void TellScreen(bool evenIfUnchanged)
{
    CRUMB(CRUMB_TELLSCREEN);
    static uint8_t Told = 255;
    NoteModelContact();
    const uint8_t Now = ScreenStatusNow();
    if ((Now == Told) && !evenIfUnchanged)
        return;
    if (NEXTION.availableForWrite() < 16)
        return;
    char b[20];
    snprintf(b, sizeof(b), "ldrcst=%u\xFF\xFF\xFF", (unsigned)Now);
    NEXTION.write((const uint8_t *)b, strlen(b));
    Told = Now;
}

#endif
