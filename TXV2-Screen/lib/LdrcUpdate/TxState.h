// What the transmitter is doing, as the screen knows it - and what follows from it for the screen's radios and for
// everything that must not be begun while the pilot is flying. Portable, and tested on the Mac (hmi/test_update).
//
// The main board (TXV1B include/FlightGuard.h, firmware 2.5.6 B8 and later) says "ldrcst=<bits>" once a second and
// at once when anything changes:
//     1  the motor is enabled              8  a safety switch is defined
//     2  the safety is off                16  a model was connected less than a minute ago
//     4  a model is connected             32  THE SCREEN'S RADIOS MUST BE OFF
// The rule for the radios is the pilot's, and it is decided on the main board (Malcolm, 29-9-2026: "Motor ON to
// kill wifi only if no safety switch was defined. If safety switch is defined then safety off should kill wifi and
// ble irrespective of motor status."). The screen obeys bit 32 and has no rule of its own.
//
// A main board older than that says nothing of the kind. All there is then is the front page's "Motor is ON" /
// "Motor is OFF": the motor decides, as it did before.
//
// At start-up the radios stay OFF until the main board has spoken, or until 8 seconds have passed without a word
// from it (an older main board, or a screen on the bench): a screen that restarts in flight does not come up
// with its WiFi on.
#ifndef LDRC_TX_STATE_H
#define LDRC_TX_STATE_H

#include <stdint.h>

namespace ldrc {

enum { TX_MOTOR = 1, TX_SAFETY_OFF = 2, TX_MODEL = 4, TX_SAFETY_DEFINED = 8, TX_MODEL_JUST_NOW = 16, TX_RADIOS_OFF = 32 };
enum { TX_HOLD_MS = 8000 };

struct TxState {
    int status;                                   // the bits the main board said last; -1: it has never said any
    bool held;                                    // start-up: the radios wait for the main board's word
    bool armed;                                   // the radios must be off
    TxState() : status(-1), held(true), armed(false) {}

    // Each of these answers with the words for the banner when the radios are to be switched (the caller applies
    // radiosAllowed()), or with 0 when nothing has changed.
    const char *said(int bits) {                  // "ldrcst=<bits>" came over the wire
        const bool was = radiosAllowed(), first = held;
        status = bits & 63; held = false; armed = (bits & TX_RADIOS_OFF) != 0;
        if (radiosAllowed() == was) return 0;
        return armed ? ((bits & TX_SAFETY_DEFINED) ? "Safety off: WiFi and Bluetooth OFF" : "Motor on: WiFi and Bluetooth OFF") : first ? "WiFi ON - joining..." : "WiFi back ON";
    }
    const char *motorText(bool on) {              // the front page's text, from a main board that says no "ldrcst="
        if (status >= 0) return 0;                // (one that does is believed, and the text is not)
        const bool was = radiosAllowed();
        armed = on;
        if (radiosAllowed() == was) return 0;
        return armed ? "Motor on: WiFi and Bluetooth OFF" : "Motor off: WiFi back ON";
    }
    const char *tick(uint32_t sinceStartMs) {     // call often
        if (!held || sinceStartMs <= TX_HOLD_MS) return 0;
        held = false;
        return radiosAllowed() ? "WiFi ON - joining..." : 0;
    }
    bool radiosAllowed() const { return !armed && !held; }

    // Why nothing may be begun or changed just now (the numbers are UpdateHost::FLY_...): 0 nothing stands in the
    // way, 1 the motor is on, 2 the safety is off, 3 a model is connected, 4 one was a moment ago.
    int flying() const {
        if (status < 0) return armed ? 1 : 0;
        if (status & TX_RADIOS_OFF) return (status & TX_SAFETY_DEFINED) ? 2 : 1;
        if (status & TX_MODEL) return 3;
        if (status & TX_MODEL_JUST_NOW) return 4;
        return 0;
    }
    static const char *flyingText(int why) {
        return why == 1 ? "the motor is on" : why == 2 ? "the safety is off" : why == 3 ? "a model is connected" : why == 4 ? "a model was connected less than a minute ago" : "";
    }
};

// Is this display command the main board's word on what it is doing? ("ldrcst=" and a number, nothing else.)
inline bool txStatusCommand(const char *cmd, unsigned length, int &bits) {
    if (length < 8 || length > 10) return false;
    static const char word[] = "ldrcst=";
    for (int i = 0; i < 7; ++i) if (cmd[i] != word[i]) return false;
    int v = 0;
    for (unsigned i = 7; i < length; ++i) { if (cmd[i] < '0' || cmd[i] > '9') return false; v = v * 10 + (cmd[i] - '0'); }
    bits = v;
    return true;
}

// ---------------------------------------------------------------------------------------------------------------
// THE RECEIVER, through the main board (TXV1B include/RxUpdate.h, firmware B11 and later; receivers RXV2 0.9.864
// and later). Once a second while a model is connected, or an update of the receiver is on its way:
//     "ldrcrx=<phase>,<why>,<outcome>,<release hex>,<wanted hex>,<seconds left of the silence>"
// phase: 0 nothing, 1 the receiver is asked, 2 the transmitter is silent while the receiver updates itself,
//        3 waiting for the receiver to come back, 4 done, 5 failed (why says why; outcome is the receiver's word).
// release: major<<24 | minor<<16 | minimus, 0 = the receiver has not said (an older receiver, or none).
struct RxNews {
    int phase, why, outcome;
    uint32_t release, wanted, left;
    uint32_t flags;                               // B13: 1 silent for the update, 2 SendNoData, 4 model matched, 8 bound, 16 connected, 32 not normal mode, 64 a question waits
    uint32_t atMs;                                // when it was said (the host fills this in)
    RxNews() : phase(0), why(0), outcome(0), release(0), wanted(0), left(0), flags(0), atMs(0) {}
};
enum { RXUP_IDLE = 0, RXUP_ORDERED = 1, RXUP_QUIET = 2, RXUP_WAITING = 3, RXUP_DONE = 4, RXUP_FAILED = 5 };
enum { RXW_NONE = 0, RXW_NO_MODEL = 1, RXW_NOT_ALLOWED = 2, RXW_NO_ANSWER = 3, RXW_ARMED = 4, RXW_NO_WIFI_KNOWN = 5,
       RXW_NOT_BACK = 6, RXW_RX_SAID = 7, RXW_STILL_OLD = 8 };
enum { RXO_NONE = 0, RXO_DONE = 1, RXO_NO_WIFI = 2, RXO_NO_MANIFEST = 3, RXO_NOT_FOUND = 4, RXO_DOWNLOAD_FAILED = 5,
       RXO_DID_NOT_TAKE = 6, RXO_NOT_QUIET = 7, RXO_PAGES_FAILED = 8 };

inline bool rxStatusCommand(const char *cmd, unsigned length, RxNews &out) {
    if (length < 18 || length > 60) return false;
    static const char word[] = "ldrcrx=";
    for (int i = 0; i < 7; ++i) if (cmd[i] != word[i]) return false;
    uint32_t v[7] = {0, 0, 0, 0, 0, 0, 0};
    int field = 0; bool any = false;
    for (unsigned i = 7; i < length; ++i) {
        const char c = cmd[i];
        if (c == ',') { if (!any || ++field > 6) return false; any = false; continue; }
        int d;
        if (c >= '0' && c <= '9') d = c - '0';
        else if (field == 3 || field == 4) { if (c >= 'A' && c <= 'F') d = c - 'A' + 10; else if (c >= 'a' && c <= 'f') d = c - 'a' + 10; else return false; }
        else return false;
        v[field] = v[field] * ((field == 3 || field == 4) ? 16 : 10) + d; any = true;
    }
    if ((field != 5 && field != 6) || !any) return false;   // six fields (B11, B12), or seven (B13: the flags)
    if (v[0] > 5 || v[1] > 255 || v[2] > 255) return false;
    out.phase = (int) v[0]; out.why = (int) v[1]; out.outcome = (int) v[2]; out.release = v[3]; out.wanted = v[4]; out.left = v[5]; out.flags = v[6];
    return true;
}

}  // namespace ldrc
#endif
