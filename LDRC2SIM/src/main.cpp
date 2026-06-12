// LDRC2SIM — RC receiver to USB flight-sim adapter
// ------------------------------------------------------------------
// Seeed XIAO ESP32-S3, native USB (TinyUSB). Auto-detects a CRSF / SBUS /
// IBUS / PPM receiver on pin D7 and presents it as an 8-axis USB HID joystick
// that neXt (CGM) reads in RX2SIM-compatible channel order. With no receiver
// connected (or on link loss) it holds the last known channel positions.
//
// Build flags (see platformio.ini) MUST set ARDUINO_USB_MODE=0 so TinyUSB
// is compiled in; the XIAO board default (=1) disables it.

#include <Arduino.h>
#include "USB.h"
#include "USBHID.h"
#include "USBCDC.h"
#include "rc_input.h"
#include "web_portal.h"

#if ARDUINO_USB_MODE
#error "Build with ARDUINO_USB_MODE=0 (USB-OTG/TinyUSB). See platformio.ini."
#endif

// ---- Tunables ----------------------------------------------------------
// Change to 20 (or a composite layout) later; descriptor + report scale
// automatically. NUM_AXES is limited to 255 by the single-byte Report
// Count item, and to ~ the HID FS report-size budget in practice.
// neXt (and the whole RC-sim USB-HID ecosystem: RX2SIM, XSR-SIM, rcstick-f...)
// reads a maximum of 8 PROPORTIONAL axes. 16 axes enumerate fine at the OS level
// (proven in Phase 1) but neXt only binds the first 8 — so we ship 8.
static const uint8_t  NUM_AXES   = 8;
// Reporting is EVENT-DRIVEN: we ship a HID report the instant a fresh RC frame
// is decoded, so receiver->USB latency is just the loop spin time (sub-ms)
// instead of waiting for a fixed timer. Two guards bound it:
//   MIN_SEND_US  — floor between sends (1 kHz cap) so we never out-run the USB
//                  full-speed HID poll interval (bInterval = 1 ms in the core).
//   HEARTBEAT_US — ceiling: resend at least this often even with no new frame,
//                  so the joystick stays alive and failsafe-hold keeps feeding.
static const uint32_t MIN_SEND_US  = 1000;         // >= 1 ms between sends (<=1 kHz)
static const uint16_t HEARTBEAT_HZ = 200;          // fallback resend rate (no new frame)
static const uint32_t HEARTBEAT_US = 1000000UL / HEARTBEAT_HZ;
static const uint8_t  REPORT_ID  = 1;              // Report ID 1 (core's no-ID path is buggy)

// ---- Buttons + keyboard (ported from RXV2's proven composite) -----------
// 8 HID buttons ride in the same joystick report (1 byte after the axes):
// fired from the phone (/api/sim/button) for RealFlight's UI functions
// (Select/Cancel/Up/Down/Reset), or by receiver channels 9-16 (ch9->btn1 ...
// ch16->btn8, >=1600us = pressed) so a transmitter switch can work them.
// A separate KEYBOARD collection (report ID 2) on the same HID interface
// sends camera/view keystrokes — the exact layout flying daily on RXV2.
static const uint8_t  NUM_BUTTONS     = 8;
static const uint8_t  KB_REPORT_ID    = 2;
static const uint32_t BTN_PULSE_MS    = 250;       // a web tap = one clean press
static const uint16_t BTN_THRESH_US   = 1600;      // channel >= this = pressed
static const uint32_t KEY_HOLD_MS     = 50;        // press ... release spacing
static const uint32_t KEY_DEBOUNCE_MS = 120;       // merge the page's double-POST

// RC receiver signal input. XIAO ESP32-S3 pin D7 (silk "RX") = GPIO44.
// Auto-detects CRSF / SBUS / IBUS / PPM on this one pin.
static const int8_t   RC_PIN     = 44;             // D7

// ---- Channel mapping: hidden baseline + user-facing map ----------------
//
// We work in three layers so the user's map can default to a clean, simple 1:1
// ("unmapped") yet still fly exactly like RX2SIM out of the box:
//
//  LOGICAL channel  — how the user thinks of their channels and how neXt
//                     calibrates them: 1=aileron, 2=elevator, 3=rudder,
//                     4=throttle, 5..8=aux. This is what the Map page shows.
//  BASELINE         — a fixed, hidden transform that turns a logical channel
//                     into the right physical RX stream slot (and reverse), so
//                     "logical 1:1" already behaves like RX2SIM. The radio's
//                     SBUS stream is A,E,T,R,5..8 on indices 0..7, and RX2SIM/
//                     neXt swap throttle/rudder — hence Out 3 (rudder) pulls
//                     stream idx 3 and Out 4 (throttle) pulls idx 2; rudder is
//                     reversed. All baked in here, never shown to the user.
//  USER MAP         — the editable layer (Map channels page). Defaults to
//                     identity (Out N <- logical Ch N, no reverse) so the page
//                     reads as a tidy 1:1. userRev XORs the baseline reverse.
static const uint8_t BASE_MAP[NUM_AXES] = { 0, 1, 3, 2, 4, 5, 6, 7 };
static const bool     BASE_REV[NUM_AXES] = { false, false, true, false, false, false, false, false };

// User map (edited from the web "Map channels" page; persisted to NVS).
//   userMap[out] = 0-based LOGICAL channel (0..15) feeding Output (out+1)
//   userRev[out] = reverse Output (out+1) relative to its normal direction
// GLOBALS (non-const) so the web portal can edit them live.
uint8_t userMap[NUM_AXES] = { 0, 1, 2, 3, 4, 5, 6, 7 };
bool    userRev[NUM_AXES] = { false, false, false, false, false, false, false, false };

// macOS/neXt enumerates THIS descriptor's 8 HID report positions rotated so
// our report position 0 (X) lands on neXt axis 6 — i.e. neXt axis number
// = (reportPos + 8 - MAP_ROT) % 8 with MAP_ROT = 2. We index userMap/userRev
// by neXt axis ("Output N"), so fillAxes converts report position -> output.
static const uint8_t MAP_ROT = 2;


// ---- HID device with a custom, NUM_AXES-wide report descriptor ---------
//
// Layout (Generic Desktop / Joystick):
//   Report ID 1
//   Logical Min -32768 .. Max 32767   (clean signed 16-bit encoding; the
//                                       sim calibrates, so range is moot)
//   Report Size 16, Report Count NUM_AXES
//   Usages: 16 DISTINCT Generic Desktop usages (see AXIS_USAGES). Distinct
//   usages matter: a usage-keyed reader (neXt, DirectInput-style mappers)
//   collapses repeated usages, so 10x Slider showed up as only ~2 channels.
//
// We use a Report ID (not a report-ID-less descriptor) because the
// arduino-esp32 2.0.14 descriptor parser has an explicit "todo: handle
// better when device has no report ID" branch — the report-ID path is the
// well-tested one.
// ONE shared HID interface; the joystick and keyboard are separate top-level
// collections on it, distinguished by report ID — the layout proven daily by
// RXV2 with RealFlight (Windows) and neXt (macOS).
static USBHID g_hid;

class SimRXHID : public USBHIDDevice {
public:
  SimRXHID() {
    buildDescriptor();
    g_hid.addDevice(this, _descLen);
  }

  void begin() { g_hid.begin(); }
  bool ready() { return g_hid.ready(); }

  // axes = NUM_AXES little-endian int16 values; buttons = 1 bit each (bit0=btn1)
  bool send(const int16_t* axes, uint8_t buttons) {
    uint8_t buf[NUM_AXES * sizeof(int16_t) + 1];
    memcpy(buf, axes, NUM_AXES * sizeof(int16_t));
    buf[NUM_AXES * sizeof(int16_t)] = buttons;
    return g_hid.SendReport(REPORT_ID, buf, sizeof buf);
  }

  // TinyUSB asks for our report descriptor at enumeration.
  uint16_t _onGetDescriptor(uint8_t* dst) override {
    memcpy(dst, _desc, _descLen);
    return _descLen;
  }

private:
  uint8_t _desc[160];
  uint16_t _descLen = 0;

  void put(uint8_t b) { _desc[_descLen++] = b; }

  void buildDescriptor() {
    // Structure mirrors the RX2SIM (RCWARE) joystick that neXt reads cleanly:
    // axes live inside a Physical collection (Usage Pointer). Without that
    // wrapper neXt only grouped the first couple of axes.
    _descLen = 0;
    put(0x05); put(0x01);              // Usage Page (Generic Desktop)
    put(0x09); put(0x04);              // Usage (Joystick)
    put(0xA1); put(0x01);              // Collection (Application)
      put(0x85); put(REPORT_ID);       //   Report ID
      put(0xA1); put(0x00);            //   Collection (Physical)  (no Usage Pointer — that
                                       //   is a mouse idiom that reorders X,Y on macOS)
        put(0x16); put(0x00); put(0x80); //     Logical Minimum (-32768)
        put(0x26); put(0xFF); put(0x7F); //     Logical Maximum (32767)
        put(0x75); put(0x10);            //     Report Size (16)
        put(0x95); put(NUM_AXES);        //     Report Count (NUM_AXES)
        // First 8 axes use the standard Generic Desktop usages neXt/RX2SIM read:
        // X, Y, Z, Rx, Ry, Rz, Slider, Dial; spare entries continue the set.
        static const uint8_t AXIS_USAGES[16] = {
          0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x37,0x38, // X Y Z Rx Ry Rz Slider Dial Wheel
          0x40,0x41,0x42,0x43,0x44,0x45,0x46            // Vx Vy Vz Vbrx Vbry Vbrz Vno
        };
        for (uint8_t i = 0; i < NUM_AXES; i++) {
          put(0x09);
          put(i < 16 ? AXIS_USAGES[i] : 0x36);
        }
        put(0x81); put(0x02);          //     Input (Data,Var,Abs)
        // 8 buttons, 1 bit each — fired from the phone or receiver ch 9-16.
        // (RealFlight binds them as Button 1-8; neXt simply ignores them.)
        put(0x05); put(0x09);          //     Usage Page (Button)
        put(0x19); put(0x01);          //     Usage Minimum (1)
        put(0x29); put(NUM_BUTTONS);   //     Usage Maximum (8)
        put(0x15); put(0x00);          //     Logical Minimum (0)
        put(0x25); put(0x01);          //     Logical Maximum (1)
        put(0x75); put(0x01);          //     Report Size (1)
        put(0x95); put(NUM_BUTTONS);   //     Report Count (8)
        put(0x81); put(0x02);          //     Input (Data,Var,Abs)
      put(0xC0);                       //   End Collection (Physical)
    put(0xC0);                         // End Collection (Application)
  }
};

// Standard input-only keyboard (modifiers + reserved + 6 keycodes), report ID 2.
// Non-blocking press->50ms->release state machine; 120ms debounce merges the
// phone page's reliability double-POST into ONE keystroke. Port of RXV2's
// SimKeyboard, byte-for-byte descriptor.
class SimKeyboard : public USBHIDDevice {
public:
  SimKeyboard() {
    buildDescriptor();
    g_hid.addDevice(this, _descLen);
  }

  // Queue a keystroke (HID usage id + modifier bitmask Ctrl=1 Shift=2 Alt=4 Win=8).
  void sendKey(uint8_t code, uint8_t mods) {
    uint32_t now = millis();
    if (now - _lastAccept < KEY_DEBOUNCE_MS) return;   // double-POST -> one keystroke
    _lastAccept = now;
    uint8_t rep[8] = { mods, 0, code, 0, 0, 0, 0, 0 };
    if (g_hid.ready() && g_hid.SendReport(KB_REPORT_ID, rep, sizeof rep)) {
      _pressedAt = now;
      _down = true;
    }
  }

  // Call every loop: releases the key ~KEY_HOLD_MS after the press.
  void tick() {
    if (!_down || millis() - _pressedAt < KEY_HOLD_MS) return;
    uint8_t rep[8] = { 0 };
    if (g_hid.SendReport(KB_REPORT_ID, rep, sizeof rep)) _down = false;
  }

  uint16_t _onGetDescriptor(uint8_t* dst) override {
    memcpy(dst, _desc, _descLen);
    return _descLen;
  }

private:
  uint8_t  _desc[64];
  uint16_t _descLen = 0;
  bool     _down = false;
  uint32_t _pressedAt = 0, _lastAccept = 0;

  void put(uint8_t b) { _desc[_descLen++] = b; }

  void buildDescriptor() {
    _descLen = 0;
    put(0x05); put(0x01);              // Usage Page (Generic Desktop)
    put(0x09); put(0x06);              // Usage (Keyboard)
    put(0xA1); put(0x01);              // Collection (Application)
      put(0x85); put(KB_REPORT_ID);    //   Report ID
      put(0x05); put(0x07);            //   Usage Page (Key Codes)
      put(0x19); put(0xE0);            //   Usage Min (LeftControl)
      put(0x29); put(0xE7);            //   Usage Max (Right GUI)
      put(0x15); put(0x00);            //   Logical Min (0)
      put(0x25); put(0x01);            //   Logical Max (1)
      put(0x75); put(0x01);            //   Report Size (1)
      put(0x95); put(0x08);            //   Report Count (8)   — modifier bits
      put(0x81); put(0x02);            //   Input (Data,Var,Abs)
      put(0x95); put(0x01);            //   Report Count (1)   — reserved byte
      put(0x75); put(0x08);            //   Report Size (8)
      put(0x81); put(0x03);            //   Input (Const)
      put(0x95); put(0x06);            //   Report Count (6)   — 6 keycode slots
      put(0x75); put(0x08);            //   Report Size (8)
      put(0x15); put(0x00);            //   Logical Min (0)
      put(0x26); put(0xFF); put(0x00); //   Logical Max (255)
      put(0x05); put(0x07);            //   Usage Page (Key Codes)
      put(0x19); put(0x00);            //   Usage Min (0)
      put(0x2A); put(0xFF); put(0x00); //   Usage Max (255)
      put(0x81); put(0x00);            //   Input (Data,Array)
    put(0xC0);                         // End Collection
  }
};

static SimRXHID    simrx;
static SimKeyboard simkb;
static int16_t     axisBuf[NUM_AXES];
static RcInput     rcin;

// ---- Button state: web-tap pulses merged with receiver channels 9-16 ----
static uint32_t btnPulseUntil[NUM_BUTTONS] = { 0 };

// A web tap re-arms the pulse, so the page's triple-POST merges into one press.
void simPressButton(uint8_t n) {                 // n = 1..8
  if (n < 1 || n > NUM_BUTTONS) return;
  btnPulseUntil[n - 1] = millis() + BTN_PULSE_MS;
}

static uint8_t fillButtons() {
  uint8_t b = 0;
  uint32_t now = millis();
  for (uint8_t i = 0; i < NUM_BUTTONS; i++) {
    bool on = (int32_t)(btnPulseUntil[i] - now) > 0;                     // web pulse
    if (!on && rcin.linkUp() && rcin.channelCount() > 8 + i)
      on = rcin.channelUs(8 + i) >= BTN_THRESH_US;                       // TX switch via RX ch 9-16
    if (on) b |= (1 << i);
  }
  return b;
}

bool simButtonLit(uint8_t n) {                   // n = 1..8 (for the web page)
  if (n < 1 || n > NUM_BUTTONS) return false;
  return (fillButtons() >> (n - 1)) & 1;
}

void simSendKey(uint8_t code, uint8_t mods) { simkb.sendKey(code, mods); }

// RC channel (microseconds, ~988..2012) -> signed 16-bit HID axis.
// 1500us -> 0 (centre); ±512us -> full scale. neXt calibrates anyway.
static inline int16_t usToAxis(uint16_t us) {
  int32_t v = ((int32_t)us - 1500) * 32767 / 512;
  if (v >  32767) v =  32767;
  if (v < -32767) v = -32767;
  return (int16_t)v;
}

// Manual USB CDC for the debug heartbeat. With CDC_ON_BOOT=0 the global
// `Serial` is UART (not over USB), so we add our own USB CDC interface; the
// device enumerates as a CDC + HID composite. Just instantiating it enables
// the CDC interface in the descriptor. The CDC port also lets future
// `pio run -t upload` auto-reset from the running app (avoids the S3
// USB-Serial-JTAG download-mode stickiness).
static USBCDC USBSerial;

// XIAO ESP32-S3 user LED (active LOW) — heartbeat once USB is ready.
#ifndef LED_BUILTIN
#define LED_BUILTIN 21
#endif

void setup() {
  // Distinctive identity. VID 0x1209 = pid.codes open-source/hobby vendor
  // ID (won't collide with a real vendor or a sim's HID blocklist).
  // PID 0x5258 = ASCII "RX".
  // Order matters: set identity and enable the HID + CDC interfaces BEFORE
  // USB.begin(), which builds the descriptor and starts TinyUSB exactly once
  // (guarded by _started). With CDC_ON_BOOT=0 there is no earlier boot-time
  // USB.begin() to race us.
  USB.VID(0x1209);
  USB.PID(0x525C);                     // keep ID/serial stable so neXt keeps
  USB.manufacturerName("LDRC");        // the (now-correct) calibration
  USB.productName("LDRC2SIM");
  USB.serialNumber("LDRC-P1-0005");

  simrx.begin();        // enable HID interface
  USBSerial.begin();    // enable CDC interface (debug heartbeat)
  USB.begin();          // start TinyUSB: CDC + HID composite

  rcin.begin(RC_PIN, &Serial1);   // auto-detect CRSF/SBUS/IBUS/PPM on D7

  // WiFi config portal + help + OTA. Non-blocking: AP "LDRC2SIM" comes up
  // instantly and home WiFi joins in the background, so the joystick is never
  // delayed at boot.
  WebPortal::begin(&rcin);

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);     // off (active low)
}

// Failsafe: when the RC link is up, copy the (remapped, reversed) channels into
// the axis report. When the link is lost, leave axisBuf untouched so the sim
// holds the LAST KNOWN positions rather than snapping. On a fresh boot with no
// link ever seen, axisBuf is zero-initialised = centred.
static void fillAxes() {
  if (!rcin.linkUp()) return;            // hold last known positions
  for (uint8_t k = 0; k < NUM_AXES; k++) {
    // k = HID report position; out = the neXt axis ("Output N") it becomes.
    uint8_t out  = (uint8_t)((k + NUM_AXES - MAP_ROT) % NUM_AXES);
    uint8_t L    = userMap[out];                                  // logical channel 0..15
    uint8_t phys = (L < NUM_AXES) ? BASE_MAP[L] : L;              // physical RX stream idx
    bool    rev  = ((L < NUM_AXES) ? BASE_REV[L] : false) ^ userRev[out];
    int16_t v = usToAxis(rcin.channelUs(phys));
    axisBuf[k] = rev ? (int16_t)-v : v;
  }
}

void loop() {
  static uint32_t nextHeartbeat = 0;
  static uint32_t lastSend      = 0;
  static uint32_t nextBeat      = 0;
  static uint32_t worstGapUs    = 0;   // max send-to-send gap in the last second

  bool fresh = rcin.update();                       // true if a new RC frame landed
  WebPortal::loop();                                // service captive DNS + web
  simkb.tick();                                     // release any pending keystroke (non-blocking)

  uint32_t now = micros();
  bool heartbeatDue = (int32_t)(now - nextHeartbeat) >= 0;

  // Send when a fresh frame arrives (low latency) or the heartbeat is due
  // (keep-alive / failsafe-hold), but never closer than MIN_SEND_US apart.
  if ((fresh || heartbeatDue) &&
      (int32_t)(now - lastSend) >= (int32_t)MIN_SEND_US &&
      simrx.ready()) {
    if (lastSend) { uint32_t gap = now - lastSend; if (gap > worstGapUs) worstGapUs = gap; }
    lastSend      = now;
    nextHeartbeat = now + HEARTBEAT_US;

    fillAxes();
    simrx.send(axisBuf, fillButtons());

    // 1 Hz heartbeat blink + concise log (protocol, worst send gap, first 8 ch).
    if ((int32_t)(now - nextBeat) >= 0) {
      nextBeat = now + 1000000UL;
      digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
      int8_t hw = WebPortal::homeWifi();
      const char* wifi = (hw < 0) ? "none" : (hw ? "up" : "DOWN");
      USBSerial.printf(
        "LDRC2SIM src=%-5s wifi=%-4s n=%2u worstGap=%4luus  ch1-8us=%4u %4u %4u %4u %4u %4u %4u %4u\n",
        rcin.linkUp() ? rcin.protocolName() : "hold", wifi, rcin.channelCount(), (unsigned long)worstGapUs,
        rcin.channelUs(0), rcin.channelUs(1), rcin.channelUs(2), rcin.channelUs(3),
        rcin.channelUs(4), rcin.channelUs(5), rcin.channelUs(6), rcin.channelUs(7));
      worstGapUs = 0;
    }
  }
}
