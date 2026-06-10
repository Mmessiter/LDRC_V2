// SimUsb.h — present the receiver as a USB composite HID device for a PC flight
// sim: a flight-sim GAMEPAD (8 axes + 8 buttons, driven by the received channels)
// PLUS a standard KEYBOARD (camera/view shortcuts, sent from the web UI). The
// gamepad descriptor + axis mapping are proven against neXt / RX2SIM / RealFlight.
//
// Both HID collections live on ONE TinyUSB HID interface (shared g_usbhid),
// distinguished by report ID:  gamepad = ID 1 (UNCHANGED), keyboard = ID 2.
// The gamepad's report format/axes/buttons are byte-for-byte unchanged, so
// RealFlight's controller profile maps identically (a one-time re-detect of the
// now-composite device aside).
//
// Only built in TinyUSB mode (ARDUINO_USB_MODE==0, the S3 production envs). On
// MODE==1 (C3 prototype) every entry point below is a harmless no-op stub.
//
// Usage from main.cpp:
//   if (simEnabled) SimUSB::begin(g_effectiveName.c_str());   // once, in setup()
//   if (simEnabled) SimUSB::sendChannels(channelMicros);      // each loop()
//   if (simEnabled) SimUSB::keyboardTick();                   // each loop()
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
constexpr uint8_t  REPORT_ID   = 1;            // gamepad report ID (UNCHANGED — RealFlight maps off this collection)
constexpr uint8_t  KB_REPORT_ID = 2;           // keyboard report ID (second collection, same HID interface)
constexpr uint32_t MIN_SEND_US = 1000;         // cap the gamepad report rate at <= 1 kHz
constexpr uint16_t BTN_THRESH  = 1600;         // received channel µs above which a switch counts as "pressed"
constexpr uint32_t BTN_PULSE_MS = 250;         // how long a web-page tap holds its button down
// Up & Down (buttons 4 & 5) auto-repeat while held — bits 3 and 4 -> 0x18.
constexpr uint8_t  REPEAT_MASK     = 0x18;
constexpr uint32_t REP_DELAY_MS    = 350;
constexpr uint32_t REP_INTERVAL_MS = 160;
constexpr uint32_t REP_ON_MS       = 70;
constexpr uint32_t KEY_HOLD_MS     = 50;       // keystroke press -> release hold
constexpr uint32_t KEY_DEBOUNCE_MS = 120;      // collapse the web page's redundant re-sends into ONE keystroke

// ONE shared HID interface; the gamepad and keyboard register as two collections.
USBHID g_usbhid;

// RC channel (microseconds, centre 1500) -> signed 16-bit HID axis.
inline int16_t usToAxis(uint16_t us) {
    int32_t v = ((int32_t)us - 1500) * 32767 / 512;
    if (v >  32767) v =  32767;
    if (v < -32767) v = -32767;
    return (int16_t)v;
}

// Hidden "RX2SIM / neXt" baseline (throttle/rudder swap + rudder reverse), applied
// invisibly so the user-facing /map can stay a tidy 1:1.
const uint8_t BASE_MAP[NUM_AXES] = { 0, 1, 3, 2, 4, 5, 6, 7 };
const bool    BASE_REV[NUM_AXES] = { false, false, true, false, false, false, false, false };
const uint8_t MAP_ROT            = 2;
uint8_t USER_MAP[NUM_AXES] = { 0, 1, 2, 3, 4, 5, 6, 7 };
bool    USER_REV[NUM_AXES] = { false, false, false, false, false, false, false, false };

// ---- Gamepad: 8 axes + 8 buttons, report ID 1. DESCRIPTOR UNCHANGED. ----
class SimHID : public USBHIDDevice {
public:
    SimHID() { buildDescriptor(); g_usbhid.addDevice(this, _descLen); }
    bool send(const int16_t* axes, uint8_t buttons) {
        uint8_t rep[NUM_AXES * sizeof(int16_t) + 1];          // 8 axes (16 bytes) + 1 button byte
        memcpy(rep, axes, NUM_AXES * sizeof(int16_t));
        rep[NUM_AXES * sizeof(int16_t)] = buttons;
        // BLOCKING send (default timeout): the wait yields CPU and paces the loop,
        // which the radio link needs (a non-blocking variant halved the frame rate).
        return g_usbhid.SendReport(REPORT_ID, rep, sizeof rep);
    }
    uint16_t _onGetDescriptor(uint8_t* dst) override { memcpy(dst, _desc, _descLen); return _descLen; }
private:
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
            static const uint8_t AXIS_USAGES[16] = {
                0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x37,0x38,
                0x40,0x41,0x42,0x43,0x44,0x45,0x46 };
            for (uint8_t i = 0; i < NUM_AXES; i++) { put(0x09); put(i < 16 ? AXIS_USAGES[i] : 0x36); }
            put(0x81); put(0x02);             //     Input (Data,Var,Abs)
          put(0xC0);                          //   End Collection (Physical)
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

// ---- Keyboard: standard keyboard collection, report ID 2 (input-only). ----
// 8-byte report: [modifiers][reserved][keycode x6]. Sends one key at a time.
class SimKeyboard : public USBHIDDevice {
public:
    SimKeyboard() { buildDescriptor(); g_usbhid.addDevice(this, _descLen); }
    bool press(uint8_t mods, uint8_t code) {
        uint8_t rep[8] = { mods, 0, code, 0, 0, 0, 0, 0 };
        return g_usbhid.SendReport(KB_REPORT_ID, rep, sizeof rep);
    }
    bool release() {
        uint8_t rep[8] = { 0, 0, 0, 0, 0, 0, 0, 0 };
        return g_usbhid.SendReport(KB_REPORT_ID, rep, sizeof rep);
    }
    uint16_t _onGetDescriptor(uint8_t* dst) override { memcpy(dst, _desc, _descLen); return _descLen; }
private:
    uint8_t  _desc[80];
    uint16_t _descLen = 0;
    void put(uint8_t b) { _desc[_descLen++] = b; }
    void buildDescriptor() {
        _descLen = 0;
        put(0x05); put(0x01);                 // Usage Page (Generic Desktop)
        put(0x09); put(0x06);                 // Usage (Keyboard)
        put(0xA1); put(0x01);                 // Collection (Application)
          put(0x85); put(KB_REPORT_ID);       //   Report ID (2)
          put(0x05); put(0x07);               //   Usage Page (Keyboard/Keypad)
          put(0x19); put(0xE0);               //   Usage Minimum (Left Control)
          put(0x29); put(0xE7);               //   Usage Maximum (Right GUI)
          put(0x15); put(0x00);               //   Logical Minimum (0)
          put(0x25); put(0x01);               //   Logical Maximum (1)
          put(0x75); put(0x01);               //   Report Size (1)
          put(0x95); put(0x08);               //   Report Count (8)
          put(0x81); put(0x02);               //   Input (Data,Var,Abs)  — 8 modifier bits
          put(0x95); put(0x01);               //   Report Count (1)
          put(0x75); put(0x08);               //   Report Size (8)
          put(0x81); put(0x03);               //   Input (Const,Var,Abs) — reserved byte
          put(0x95); put(0x06);               //   Report Count (6)
          put(0x75); put(0x08);               //   Report Size (8)
          put(0x15); put(0x00);               //   Logical Minimum (0)
          put(0x25); put(0x65);               //   Logical Maximum (0x65)
          put(0x05); put(0x07);               //   Usage Page (Keyboard/Keypad)
          put(0x19); put(0x00);               //   Usage Minimum (0)
          put(0x29); put(0x65);               //   Usage Maximum (0x65)
          put(0x81); put(0x00);               //   Input (Data,Array)    — 6 keycodes
        put(0xC0);                            // End Collection
    }
};

SimHID*      g_hid = nullptr;
SimKeyboard* g_kb  = nullptr;
int16_t  g_axis[NUM_AXES];                     // last gamepad report (held on link loss)
uint8_t  g_buttons = 0;
uint32_t g_btnUntil[NUM_BUTTONS] = {0};
uint32_t g_repNext[NUM_BUTTONS]     = {0};
uint32_t g_repPressEnd[NUM_BUTTONS] = {0};
bool     g_repHeld[NUM_BUTTONS]     = {false};
uint32_t g_lastSend = 0;
bool     g_started = false;

// Keyboard keystroke state machine (non-blocking; driven from keyboardTick()).
enum KeyState { KEY_IDLE, KEY_PRESS, KEY_HOLD };
KeyState g_keyState = KEY_IDLE;
uint8_t  g_keyCode  = 0;
uint8_t  g_keyMods  = 0;
uint32_t g_keyUntil = 0;
uint32_t g_keyLastMs = 0;                      // last accepted keystroke (for debounce)

// Keyboard-style auto-repeat (Up/Down) for the gamepad buttons.
inline bool autoRepeatOn(uint8_t i, bool raw, uint32_t ms) {
    if (!raw) { g_repHeld[i] = false; return false; }
    if (!g_repHeld[i]) {
        g_repHeld[i]     = true;
        g_repPressEnd[i] = ms + REP_ON_MS;
        g_repNext[i]     = ms + REP_DELAY_MS;
        return true;
    }
    if ((int32_t)(g_repPressEnd[i] - ms) > 0) return true;
    if ((int32_t)(ms - g_repNext[i]) >= 0) {
        g_repPressEnd[i] = ms + REP_ON_MS;
        g_repNext[i]     = ms + REP_INTERVAL_MS;
        return true;
    }
    return false;
}

}  // anonymous namespace

// Bring up the composite device. Call ONCE in setup(). Register both HID
// collections with the shared interface, THEN g_usbhid.begin(), THEN USB.begin().
inline void begin(const char* serial) {
    if (g_started) return;
    g_started = true;
    USB.VID(0x1209);                          // pid.codes open-source/hobby vendor
    USB.PID(0x525D);
    USB.manufacturerName("LDRC");
    USB.productName("RXV2-SIM");
    if (serial && *serial) USB.serialNumber(serial);
    static SimHID      gp;                    // ctor registers gamepad  (report ID 1)
    static SimKeyboard kb;                    // ctor registers keyboard (report ID 2)
    g_hid = &gp;
    g_kb  = &kb;
    g_usbhid.begin();                         // ONE begin for the shared interface
    USB.begin();                              // start TinyUSB
}

inline bool ready() { return g_usbhid.ready(); }

// Feed the latest received channels (microseconds). Rate-limited to <= 1 kHz.
inline void sendChannels(const uint16_t ch[16]) {
    if (!g_hid || !g_usbhid.ready()) return;
    uint32_t now = micros();
    if ((uint32_t)(now - g_lastSend) < MIN_SEND_US) return;
    g_lastSend = now;
    for (uint8_t k = 0; k < NUM_AXES; k++) {
        uint8_t out  = (uint8_t)((k + NUM_AXES - MAP_ROT) % NUM_AXES);
        uint8_t L    = USER_MAP[out];
        uint8_t phys = (L < NUM_AXES) ? BASE_MAP[L] : L;
        bool    rev  = ((L < NUM_AXES) ? BASE_REV[L] : false) ^ USER_REV[out];
        int16_t v    = usToAxis(ch[phys < 16 ? phys : 0]);
        g_axis[k]    = rev ? (int16_t)-v : v;
    }
    uint32_t ms   = millis();
    uint8_t  btns = 0;
    for (uint8_t i = 0; i < NUM_BUTTONS; i++) {
        bool raw = (ch[8 + i] >= BTN_THRESH) || ((int32_t)(g_btnUntil[i] - ms) > 0);
        bool on  = (REPEAT_MASK & (1u << i)) ? autoRepeatOn(i, raw, ms) : raw;
        if (on) btns |= (uint8_t)(1u << i);
    }
    g_buttons = btns;
    g_hid->send(g_axis, btns);
}

inline void setMap(const uint8_t map[NUM_AXES], const bool rev[NUM_AXES]) {
    for (uint8_t i = 0; i < NUM_AXES; i++) {
        USER_MAP[i] = (map[i] < 16) ? map[i] : 0;
        USER_REV[i] = rev[i];
    }
}
inline void getMap(uint8_t map[NUM_AXES], bool rev[NUM_AXES]) {
    for (uint8_t i = 0; i < NUM_AXES; i++) { map[i] = USER_MAP[i]; rev[i] = USER_REV[i]; }
}

inline void pressButton(uint8_t n) {
    if (n >= 1 && n <= NUM_BUTTONS) g_btnUntil[n - 1] = millis() + BTN_PULSE_MS;
}
inline uint8_t getButtons() { return g_buttons; }
inline uint8_t buttonCount() { return NUM_BUTTONS; }

// ---- Keyboard (camera/view shortcuts) ----
// Queue a momentary keystroke.  code = HID Usage ID (e.g. 0x04='a', 0x3A=F1),
// mods = modifier bitmask (bit0 LCtrl, bit1 LShift, bit2 LAlt, bit3 LGUI, ...).
// NON-BLOCKING: only sets state; the press/release reports are sent from
// keyboardTick() in the loop, so this never stalls the caller or the gamepad rate.
inline void sendKey(uint8_t code, uint8_t mods) {
    if (g_keyState != KEY_IDLE) return;
    uint32_t now = millis();
    if ((uint32_t)(now - g_keyLastMs) < KEY_DEBOUNCE_MS) return;   // de-dup the page's redundant re-sends
    g_keyLastMs = now;
    g_keyCode = code; g_keyMods = mods; g_keyState = KEY_PRESS;
}
// Drive the keystroke state machine — press, ~KEY_HOLD_MS hold, release. Call
// once per loop() in sim mode. Does nothing (fast return) when no key is pending.
inline void keyboardTick() {
    if (g_keyState == KEY_IDLE || !g_kb || !g_usbhid.ready()) return;
    uint32_t now = millis();
    if (g_keyState == KEY_PRESS) {
        g_kb->press(g_keyMods, g_keyCode);
        g_keyUntil = now + KEY_HOLD_MS;
        g_keyState = KEY_HOLD;
    } else if ((int32_t)(now - g_keyUntil) >= 0) {       // KEY_HOLD elapsed
        g_kb->release();
        g_keyState = KEY_IDLE;
    }
}

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
inline void sendKey(uint8_t /*code*/, uint8_t /*mods*/) {}   // BLE/keyboard stub — USB-only for now
inline void keyboardTick() {}

#endif

}  // namespace SimUSB
