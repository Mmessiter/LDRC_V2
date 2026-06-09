// SimUsb.h — present the receiver as a USB HID flight-sim joystick, driven
// straight from the channels it already receives over RF. Ported from the
// sibling LDRC2SIM project (identical XIAO ESP32-S3 chip), which proved the
// descriptor + axis mapping against neXt / RX2SIM.
//
// The joystick only exists when the firmware is built in TinyUSB mode
// (ARDUINO_USB_MODE==0, the S3 production envs). On the MODE==1 builds (the
// C3 prototype, which compiles TinyUSB out) every entry point below is a
// harmless no-op so the single source tree still builds — the joystick is
// simply unavailable on that chip.
//
// Usage from main.cpp:
//   if (simEnabled) SimUSB::begin(g_effectiveName.c_str());   // once, in setup()
//   if (simEnabled) SimUSB::sendChannels(channelMicros);      // each loop()
//
#pragma once
#include <Arduino.h>

namespace SimUSB {

#if (ARDUINO_USB_MODE == 0)
// ====================================================================
//  Real implementation (TinyUSB / USB-OTG)
// ====================================================================
} // namespace SimUSB  (reopened below after the includes)

#include "USB.h"
#include "USBHID.h"

namespace SimUSB {
namespace {

constexpr uint8_t  NUM_AXES    = 8;
constexpr uint8_t  NUM_BUTTONS = 8;            // sim-function buttons — fed by TX channels 9..16 AND the /simctl web page
constexpr uint8_t  REPORT_ID   = 1;            // Report ID 1 (core's no-ID path is buggy on 2.0.x)
constexpr uint32_t MIN_SEND_US = 1000;         // cap the report rate at <= 1 kHz
constexpr uint16_t BTN_THRESH  = 1600;         // received channel µs above which a switch counts as "pressed"
constexpr uint32_t BTN_PULSE_MS = 150;         // how long a web-page tap holds its button down
// Up & Down (buttons 4 & 5) auto-repeat while held — bits 3 and 4 -> 0x18.
constexpr uint8_t  REPEAT_MASK     = 0x18;
constexpr uint32_t REP_DELAY_MS    = 350;      // hold this long before auto-repeat starts
constexpr uint32_t REP_INTERVAL_MS = 160;      // then one press this often
constexpr uint32_t REP_ON_MS       = 70;       // each repeat press lasts this long

// RC channel (microseconds, centre 1500) -> signed 16-bit HID axis.
// RXV2's channelMicros carry the same ~1000..2000 µs domain LDRC2SIM fed its
// HID, so the proven scaling carries over: 1500 µs -> 0; ±512 µs -> full scale.
// neXt / RX2SIM calibrates anyway, so small range differences wash out.
inline int16_t usToAxis(uint16_t us) {
    int32_t v = ((int32_t)us - 1500) * 32767 / 512;
    if (v >  32767) v =  32767;
    if (v < -32767) v = -32767;
    return (int16_t)v;
}

// Hidden "RX2SIM / neXt" baseline — applied invisibly so the user-facing map can
// stay a tidy 1:1. The received stream needs throttle & rudder swapped and rudder
// reversed for neXt; BASE_MAP/BASE_REV do that under the hood. The user sees
// USER_MAP as identity (Output N <- Ch N) with nothing reversed, yet the sim
// flies correctly. MAP_ROT aligns our 8 HID report positions to neXt's
// "Output 1..8" numbering.
const uint8_t BASE_MAP[NUM_AXES] = { 0, 1, 3, 2, 4, 5, 6, 7 };
const bool    BASE_REV[NUM_AXES] = { false, false, true, false, false, false, false, false };
const uint8_t MAP_ROT            = 2;
// User-facing map (edited from /map, persisted to NVS). DEFAULT = tidy 1:1 with
// no reverse — the baseline above stays invisible to the user.
uint8_t USER_MAP[NUM_AXES] = { 0, 1, 2, 3, 4, 5, 6, 7 };
bool    USER_REV[NUM_AXES] = { false, false, false, false, false, false, false, false };

// HID joystick device. The report descriptor is built programmatically (same
// byte sequence LDRC2SIM uses) so neXt reads all 8 axes with distinct usages.
class SimHID : public USBHIDDevice {
public:
    SimHID() { buildDescriptor(); hid.addDevice(this, _descLen); }
    void begin() { hid.begin(); }
    bool ready() { return hid.ready(); }
    bool send(const int16_t* axes, uint8_t buttons) {
        uint8_t rep[NUM_AXES * sizeof(int16_t) + 1];          // 8 axes (16 bytes) + 1 button byte
        memcpy(rep, axes, NUM_AXES * sizeof(int16_t));
        rep[NUM_AXES * sizeof(int16_t)] = buttons;
        // BLOCKING send (default timeout). A non-blocking variant (timeout 0) was tried
        // in 0.9.96 to "free" the loop, but it spun the loop hot and HALVED the TX frame
        // rate while flying (492 → ~200, vs 500 with sim off) — the blocking wait yields
        // the CPU and paces the loop, which the radio link strongly prefers. Reverted.
        return hid.SendReport(REPORT_ID, rep, sizeof rep);
    }
    uint16_t _onGetDescriptor(uint8_t* dst) override { memcpy(dst, _desc, _descLen); return _descLen; }
private:
    USBHID   hid;
    uint8_t  _desc[160];
    uint16_t _descLen = 0;
    void put(uint8_t b) { _desc[_descLen++] = b; }
    void buildDescriptor() {
        _descLen = 0;
        put(0x05); put(0x01);                 // Usage Page (Generic Desktop)
        put(0x09); put(0x04);                 // Usage (Joystick)
        put(0xA1); put(0x01);                 // Collection (Application)
          put(0x85); put(REPORT_ID);          //   Report ID
          put(0xA1); put(0x00);               //   Collection (Physical)
            put(0x16); put(0x00); put(0x80);  //     Logical Minimum (-32768)
            put(0x26); put(0xFF); put(0x7F);  //     Logical Maximum (32767)
            put(0x75); put(0x10);             //     Report Size (16)
            put(0x95); put(NUM_AXES);         //     Report Count (NUM_AXES)
            // Distinct Generic Desktop usages: X Y Z Rx Ry Rz Slider Dial ...
            static const uint8_t AXIS_USAGES[16] = {
                0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x37,0x38,
                0x40,0x41,0x42,0x43,0x44,0x45,0x46 };
            for (uint8_t i = 0; i < NUM_AXES; i++) { put(0x09); put(i < 16 ? AXIS_USAGES[i] : 0x36); }
            put(0x81); put(0x02);             //     Input (Data,Var,Abs)
          put(0xC0);                          //   End Collection (Physical)
          // Buttons: sim functions, driven by TX channels 9..16 and the web page.
          // NUM_BUTTONS == 8 -> exactly one byte, byte-aligned (no padding needed).
          put(0x05); put(0x09);               //   Usage Page (Button)
          put(0x19); put(0x01);               //   Usage Minimum (Button 1)
          put(0x29); put(NUM_BUTTONS);        //   Usage Maximum (Button NUM_BUTTONS)
          put(0x15); put(0x00);               //   Logical Minimum (0)
          put(0x25); put(0x01);               //   Logical Maximum (1)
          put(0x75); put(0x01);               //   Report Size (1)
          put(0x95); put(NUM_BUTTONS);        //   Report Count (NUM_BUTTONS)
          put(0x81); put(0x02);               //   Input (Data,Var,Abs)
        put(0xC0);                            // End Collection (Application)
    }
};

SimHID*  g_hid      = nullptr;
int16_t  g_axis[NUM_AXES];                    // last report (centre/0 at boot; held on link loss)
uint8_t  g_buttons  = 0;                       // last button bitfield sent (mirror of ch9-16 | web pulses)
uint32_t g_btnUntil[NUM_BUTTONS] = {0};        // millis() until which a web-tapped button stays pressed
uint32_t g_repNext[NUM_BUTTONS]     = {0};     // auto-repeat: when the next repeat press begins
uint32_t g_repPressEnd[NUM_BUTTONS] = {0};     // auto-repeat: end of the current press window
bool     g_repHeld[NUM_BUTTONS]     = {false}; // auto-repeat: input held last cycle (rising-edge detect)
uint32_t g_lastSend = 0;
bool      g_started = false;

// Keyboard-style auto-repeat (Up/Down): an immediate press on the rising edge, then
// — if still held past REP_DELAY_MS — one press every REP_INTERVAL_MS. Driven by
// `raw` (TX switch high OR a live web hold), so it repeats from sticks and phone alike.
inline bool autoRepeatOn(uint8_t i, bool raw, uint32_t ms) {
    if (!raw) { g_repHeld[i] = false; return false; }
    if (!g_repHeld[i]) {                                    // rising edge — fire at once
        g_repHeld[i]     = true;
        g_repPressEnd[i] = ms + REP_ON_MS;
        g_repNext[i]     = ms + REP_DELAY_MS;
        return true;
    }
    if ((int32_t)(g_repPressEnd[i] - ms) > 0) return true;  // inside a press window
    if ((int32_t)(ms - g_repNext[i]) >= 0) {                // begin the next repeat press
        g_repPressEnd[i] = ms + REP_ON_MS;
        g_repNext[i]     = ms + REP_INTERVAL_MS;
        return true;
    }
    return false;                                           // gap between presses
}

}  // anonymous namespace

// Bring up the joystick. Call ONCE in setup(), before the main loop. The init
// order is load-bearing under CDC_ON_BOOT=0: set identity -> register/enable
// the HID interface -> USB.begin() (which starts TinyUSB exactly once).
inline void begin(const char* serial) {
    if (g_started) return;
    g_started = true;
    USB.VID(0x1209);                          // pid.codes open-source/hobby vendor
    USB.PID(0x525D);                          // distinct from LDRC2SIM dongle (0x525C)
    USB.manufacturerName("LDRC");
    USB.productName("RXV2-SIM");
    if (serial && *serial) USB.serialNumber(serial);   // per-unit (RXV2-XXXX) so the sim keeps calibration
    static SimHID hid;                        // ctor registers the HID device
    g_hid = &hid;
    g_hid->begin();                           // enable HID interface
    USB.begin();                              // start TinyUSB
}

inline bool ready() { return g_hid && g_hid->ready(); }

// Feed the latest received channels (microseconds). Rate-limited internally to
// <= 1 kHz. channelMicros already holds the last-known positions on link loss,
// so re-sending them is the failsafe-hold behaviour.
inline void sendChannels(const uint16_t ch[16]) {
    if (!g_hid || !g_hid->ready()) return;
    uint32_t now = micros();
    if ((uint32_t)(now - g_lastSend) < MIN_SEND_US) return;
    g_lastSend = now;
    for (uint8_t k = 0; k < NUM_AXES; k++) {
        uint8_t out  = (uint8_t)((k + NUM_AXES - MAP_ROT) % NUM_AXES);
        uint8_t L    = USER_MAP[out];                            // user's channel choice 0..15 (default = out)
        uint8_t phys = (L < NUM_AXES) ? BASE_MAP[L] : L;         // hidden baseline -> physical received channel
        bool    rev  = ((L < NUM_AXES) ? BASE_REV[L] : false) ^ USER_REV[out];
        int16_t v    = usToAxis(ch[phys < 16 ? phys : 0]);
        g_axis[k]    = rev ? (int16_t)-v : v;
    }
    // Buttons 1..8 <- received channels 9..16 (a switch past BTN_THRESH presses it),
    // OR'd with any still-active web-page tap. Bind each button to a sim function.
    uint32_t ms   = millis();
    uint8_t  btns = 0;
    for (uint8_t i = 0; i < NUM_BUTTONS; i++) {
        bool raw = (ch[8 + i] >= BTN_THRESH) || ((int32_t)(g_btnUntil[i] - ms) > 0);
        bool on  = (REPEAT_MASK & (1u << i)) ? autoRepeatOn(i, raw, ms) : raw;   // Up/Down auto-repeat
        if (on) btns |= (uint8_t)(1u << i);
    }
    g_buttons = btns;
    g_hid->send(g_axis, btns);
}

// Runtime channel remap (from the /map "Remap channels" web page). Clamped to
// valid channels; the default-with-baseline map stands until this is called.
inline void setMap(const uint8_t map[NUM_AXES], const bool rev[NUM_AXES]) {
    for (uint8_t i = 0; i < NUM_AXES; i++) {
        USER_MAP[i] = (map[i] < 16) ? map[i] : 0;
        USER_REV[i] = rev[i];
    }
}
inline void getMap(uint8_t map[NUM_AXES], bool rev[NUM_AXES]) {
    for (uint8_t i = 0; i < NUM_AXES; i++) { map[i] = USER_MAP[i]; rev[i] = USER_REV[i]; }
}

// Momentary press of sim-function button `n` (1..NUM_BUTTONS) from the web page.
// Held BTN_PULSE_MS; OR'd with the TX-channel mirror in sendChannels.
inline void pressButton(uint8_t n) {
    if (n >= 1 && n <= NUM_BUTTONS) g_btnUntil[n - 1] = millis() + BTN_PULSE_MS;
}
// Current button bitfield (bit0 = button 1), for the /simctl live indicators.
inline uint8_t getButtons() { return g_buttons; }
inline uint8_t buttonCount() { return NUM_BUTTONS; }

#else
// ====================================================================
//  Stub (ARDUINO_USB_MODE==1 — TinyUSB unavailable, e.g. C3 prototype)
// ====================================================================
inline void begin(const char* /*serial*/) {}
inline bool ready() { return false; }
inline void sendChannels(const uint16_t* /*ch*/) {}
inline void setMap(const uint8_t* /*map*/, const bool* /*rev*/) {}
inline void getMap(uint8_t map[8], bool rev[8]) { for (int i = 0; i < 8; i++) { map[i] = (uint8_t)i; rev[i] = false; } }
inline void pressButton(uint8_t /*n*/) {}
inline uint8_t getButtons() { return 0; }
inline uint8_t buttonCount() { return 8; }

#endif

}  // namespace SimUSB
