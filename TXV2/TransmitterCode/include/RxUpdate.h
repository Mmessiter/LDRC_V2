// *************************************** RxUpdate.h *****************************************
// V1B: A RECEIVER UPDATE THROUGH THE TRANSMITTER (B11, 30-9-2026)
//
// Malcolm: "If a receiver is connected when I hit check for update, I think it would be wonderful if we could check
// for a receiver update! And we could install it without having to open the app."
//
// The receiver (RXV2 0.9.864 and later) says its release number in ack item 39. The screen compares it with
// messiter.com and, when the pilot presses Install, sends "LDRCRXUP maj min minimus" on the wire. This file then:
//   1. ORDERED  - sends parameter 35 (the exact version wanted, 321 at both ends) to the receiver, and waits for its
//                 answer in ack item 40: accepted, refused (armed / no WiFi network known), or nothing (an older
//                 receiver: 10 s and we give up).
//   2. QUIET    - accepted: the transmitter goes SILENT for the time the receiver asked (90 s). The receiver never
//                 installs anything under a live link; our silence is the consent. It joins the WiFi it already
//                 knows, downloads the release and restarts. Nothing of ours goes over the air but the version.
//   3. WAITING  - we transmit again and wait for the receiver to come back (up to 4 minutes). Its release number
//                 is the proof: the one wanted = DONE; the old one, with item 40 idle = FAILED, and item 40 says why.
// The screen is told once a second (ldrcrx=...), and shows it. Flying comes first, as ever: an order is refused
// unless a model is connected, the motor is off and the safety is on (RadiosMustBeOff() in FlightGuard.h); the
// receiver checks its own arming state twice more before it touches anything.
#ifndef RX_UPDATE_H
#define RX_UPDATE_H

#include <Arduino.h>
#include "1Definitions.h"
#include "FlightGuard.h"

// What the receiver tells us (RXV2 0.9.864+; older receivers never send these items).
static uint32_t RxReleaseCode = 0;      // item 39: major<<24 | minor<<16 | minimus (0 = never heard)
static uint32_t RxReleaseCodeAtMs = 0;  // when it was last heard
static uint32_t RxUpdateWord = 0;       // item 40: state<<28 | wanted minimus<<16 | quiet seconds<<8 | last outcome
static uint32_t RxUpdateWordAtMs = 0;

// The receiver's states in item 40 (RXV2 1Defs.h RxUpdState) and its outcomes (RxUpdOutcome).
#define RXU_IDLE 0
#define RXU_ACCEPTED 1
#define RXU_REFUSED_ARMED 2
#define RXU_REFUSED_NO_WIFI 3
#define RXU_WORKING 4

enum RxUpdPhase : uint8_t
{
    RXUP_IDLE = 0,
    RXUP_ORDERED = 1,
    RXUP_QUIET = 2,
    RXUP_WAITING = 3,
    RXUP_DONE = 4,
    RXUP_FAILED = 5
};
enum RxUpdWhy : uint8_t
{
    RXW_NONE = 0,
    RXW_NO_MODEL = 1,      // no model connected
    RXW_NOT_ALLOWED = 2,   // the motor is on, or the safety is off
    RXW_NO_ANSWER = 3,     // the receiver did not answer the order (an older receiver?)
    RXW_ARMED = 4,         // the receiver says the model is armed
    RXW_NO_WIFI_KNOWN = 5, // the receiver knows no WiFi network
    RXW_NOT_BACK = 6,      // the receiver did not come back within 4 minutes
    RXW_RX_SAID = 7,       // the receiver came back on the old version and said why (the outcome)
    RXW_STILL_OLD = 8      // the receiver came back on the old version and gave no reason
};

static uint8_t RxUpdPhaseNow = RXUP_IDLE;
static uint8_t RxUpdWhyNow = RXW_NONE;
static uint8_t RxUpdOutcomeNow = 0;      // the receiver's outcome code, when RXW_RX_SAID
static uint32_t RxUpdWantedCode = 0;
static uint32_t RxUpdPhaseSince = 0;
static uint32_t RxUpdQuietMs = 90000;

#define RXUP_ANSWER_MS 10000     // ORDERED: the receiver must answer within this
#define RXUP_COME_BACK_MS 240000 // WAITING: the receiver must be back within this
#define RXUP_SHOWN_MS 30000      // DONE / FAILED are said for this long, then forgotten

static inline uint32_t RxCodeOf(uint8_t maj, uint8_t min, uint16_t minimus)
{
    return ((uint32_t)maj << 24) | ((uint32_t)min << 16) | (uint32_t)(minimus & 0xFFF);
}

// Ack items 39 and 40 (called from ParseAckPayload).
void RxHeardRelease(uint32_t code)
{
    RxReleaseCode = code;
    RxReleaseCodeAtMs = millis();
}
void RxHeardUpdateWord(uint32_t word)
{
    RxUpdateWord = word;
    RxUpdateWordAtMs = millis();
}

// While an update is ordered, running or awaited: no "Connected" / "Disconnected" voices and no log lines for the
// comings and goings the update causes.
bool ReceiverUpdateBusy()
{
    return RxUpdPhaseNow == RXUP_ORDERED || RxUpdPhaseNow == RXUP_QUIET || RxUpdPhaseNow == RXUP_WAITING;
}

static void RxUpdFail(uint8_t why, uint8_t outcome = 0)
{
    ReceiverUpdateQuiet = false;
    RxUpdPhaseNow = RXUP_FAILED;
    RxUpdWhyNow = why;
    RxUpdOutcomeNow = outcome;
    RxUpdPhaseSince = millis();
}

// The screen's "LDRCRXUP maj min minimus". Nothing is sent unless a model is connected and it may be updated.
void OrderReceiverUpdate(uint8_t maj, uint8_t min, uint16_t minimus)
{
    if (ReceiverUpdateBusy())
        return; // one at a time
    RxUpdWantedCode = RxCodeOf(maj, min, minimus);
    RxUpdOutcomeNow = 0;
    if (!(BoundFlag && ModelMatched))
    {
        RxUpdFail(RXW_NO_MODEL);
        return;
    }
    if (RadiosMustBeOff())
    {
        RxUpdFail(RXW_NOT_ALLOWED);
        return;
    }
    RxUpdWantMaj = maj; // Parameters.h reads these into parameter 35
    RxUpdWantMin = min;
    RxUpdWantMinimus = minimus & 0xFFF;
    RxUpdateWordAtMs = 0; // only an answer from now on counts
    AddParameterstoQueue(RX_UPDATE_ORDER);
    RxUpdPhaseNow = RXUP_ORDERED;
    RxUpdWhyNow = RXW_NONE;
    RxUpdPhaseSince = millis();
}

// "LDRCRXUP 0 9 870" as it arrives in TextIn.
void OrderReceiverUpdateFromText(const char *text)
{
    const char *p = strstr(text, LDRC_RX_UPDATE_WORD);
    if (!p)
        return;
    unsigned a = 0, b = 0, c = 0;
    if (sscanf(p + strlen(LDRC_RX_UPDATE_WORD), " %u %u %u", &a, &b, &c) != 3)
        return;
    if (a > 255 || b > 255 || c > 4095)
        return;
    OrderReceiverUpdate((uint8_t)a, (uint8_t)b, (uint16_t)c);
}

// Called every 50 ms.
void RxUpdateTick()
{
    CRUMB(CRUMB_RXUPDATE);
    const uint32_t now = millis();
    switch (RxUpdPhaseNow)
    {
    case RXUP_IDLE:
        return;
    case RXUP_ORDERED:
        if (RadiosMustBeOff())
        { // the pilot armed while we were asking: the receiver refuses on its own too
            RxUpdFail(RXW_NOT_ALLOWED);
            return;
        }
        if (RxUpdateWordAtMs && (RxUpdateWordAtMs - RxUpdPhaseSince) < 0x80000000u)
        {
            const uint8_t state = (uint8_t)(RxUpdateWord >> 28);
            const uint16_t wanted = (uint16_t)((RxUpdateWord >> 16) & 0xFFF);
            if (wanted == RxUpdWantMinimus)
            {
                if (state == RXU_ACCEPTED || state == RXU_WORKING)
                {
                    uint32_t secs = (RxUpdateWord >> 8) & 0xFF;
                    if (secs < 20 || secs > 240)
                        secs = 90;
                    RxUpdQuietMs = secs * 1000;
                    ReceiverUpdateQuiet = true; // SendData() sends nothing from here on
                    RxUpdPhaseNow = RXUP_QUIET;
                    RxUpdPhaseSince = now;
                    return;
                }
                if (state == RXU_REFUSED_ARMED)
                {
                    RxUpdFail(RXW_ARMED);
                    return;
                }
                if (state == RXU_REFUSED_NO_WIFI)
                {
                    RxUpdFail(RXW_NO_WIFI_KNOWN);
                    return;
                }
            }
        }
        if (now - RxUpdPhaseSince > RXUP_ANSWER_MS)
            RxUpdFail(RXW_NO_ANSWER);
        return;
    case RXUP_QUIET:
        if (now - RxUpdPhaseSince >= RxUpdQuietMs)
        {
            ReceiverUpdateQuiet = false; // transmit again: the receiver will be found when it is back
            RxUpdPhaseNow = RXUP_WAITING;
            RxUpdPhaseSince = now;
            RxReleaseCodeAtMs = 0; // only what is heard from now on counts
            RxUpdateWordAtMs = 0;
        }
        return;
    case RXUP_WAITING:
    {
        const bool fresh39 = RxReleaseCodeAtMs && (RxReleaseCodeAtMs - RxUpdPhaseSince) < 0x80000000u;
        const bool fresh40 = RxUpdateWordAtMs && (RxUpdateWordAtMs - RxUpdPhaseSince) < 0x80000000u;
        if (fresh39 && RxReleaseCode == RxUpdWantedCode)
        { // the number wanted: the receiver is back on the new release
            ReceiverUpdateQuiet = false;
            RxUpdPhaseNow = RXUP_DONE;
            RxUpdWhyNow = RXW_NONE;
            RxUpdPhaseSince = now;
            if (AnnounceConnected)
            {
                Force_Early_Sound = true;
                PlaySound(CONNECTEDMSG);
            }
            return;
        }
        // The old number, AND item 40 saying the receiver has nothing on its hands: it gave up, and says why.
        // (A receiver still busy downloading answers with the radio chip's own acks, which can carry a stale
        //  item 39 or 40 loaded before our silence: those say ACCEPTED, never IDLE. Only IDLE with the old
        //  number is a verdict; anything else is waited out, up to four minutes.)
        if (fresh39 && fresh40 && (uint8_t)(RxUpdateWord >> 28) == RXU_IDLE)
        {
            const uint8_t outcome = (uint8_t)(RxUpdateWord & 0xFF);
            if (outcome)
                RxUpdFail(RXW_RX_SAID, outcome);
            else
                RxUpdFail(RXW_STILL_OLD);
            return;
        }
        if (now - RxUpdPhaseSince > RXUP_COME_BACK_MS)
            RxUpdFail(RXW_NOT_BACK);
        return;
    }
    case RXUP_DONE:
    case RXUP_FAILED:
        if (now - RxUpdPhaseSince > RXUP_SHOWN_MS)
        {
            RxUpdPhaseNow = RXUP_IDLE;
            RxUpdWhyNow = RXW_NONE;
        }
        return;
    }
}

// Once a second: "ldrcrx=phase,why,outcome,<release hex>,<wanted hex>,<seconds left of the quiet>", whenever a model
// is connected or an update is on its way. The screen's Check for update reads the release number from this.
void TellScreenRx()
{
    CRUMB(CRUMB_TELLSCREEN);
    if (RxUpdPhaseNow == RXUP_IDLE && !(BoundFlag && ModelMatched) && !RxReleaseCode)
        return;
    uint32_t left = 0;
    if (RxUpdPhaseNow == RXUP_QUIET)
    {
        const uint32_t gone = millis() - RxUpdPhaseSince;
        left = gone < RxUpdQuietMs ? (RxUpdQuietMs - gone + 999) / 1000 : 0;
    }
    // A number heard more than 5 s ago is stale: the receiver may be gone (or restarting). Say 0.
    const uint32_t code = (RxReleaseCodeAtMs && (millis() - RxReleaseCodeAtMs) < 5000) ? RxReleaseCode : 0;
    // A seventh field, for the bench (B13): what could be silencing the radio, and the state the main loop is in.
    // 1 silent for the receiver's update, 2 SendNoData (the motor-switch rule), 4 model matched, 8 bound,
    // 16 connected (green), 32 not in the normal mode, 64 a question waits on screen.
    unsigned flags = (ReceiverUpdateQuiet ? 1 : 0) | (SendNoData ? 2 : 0) | (ModelMatched ? 4 : 0) | (BoundFlag ? 8 : 0) |
                     (LedWasGreen ? 16 : 0) | (CurrentMode != NORMAL ? 32 : 0) | (ModalWaits ? 64 : 0);
    char b[64];
    snprintf(b, sizeof(b), "ldrcrx=%u,%u,%u,%lX,%lX,%lu,%u\xFF\xFF\xFF", (unsigned)RxUpdPhaseNow, (unsigned)RxUpdWhyNow,
             (unsigned)RxUpdOutcomeNow, (unsigned long)code, (unsigned long)RxUpdWantedCode, (unsigned long)left, flags);
    // The port's outgoing buffer holds 40 bytes (Teensy 4.1 Serial: SERIAL2_TX_BUFFER_SIZE), and the line is up to
    // 35: B11 asked for 64 free and so never sent a word (found on the bench, 30-9-2026). Only a buffer that is
    // still busy with something else is left alone; the write itself waits a few hundred microseconds at most.
    if (NEXTION.availableForWrite() < 8)
        return;
    NEXTION.write((const uint8_t *)b, strlen(b));
}

#endif
