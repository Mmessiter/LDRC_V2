// LDRC2SIM — RC receiver to USB flight-sim adapter
// ------------------------------------------------------------------
// Seeed XIAO ESP32-S3, native USB (TinyUSB). Auto-detects a CRSF / SBUS /
// IBUS / PPM receiver on pin D7 and presents it as an 8-axis USB HID joystick
// that neXt (CGM) reads in RX2SIM-compatible channel order. With no receiver
// connected it drives the axes with a sine self-test.
//
// Build flags (see platformio.ini) MUST set ARDUINO_USB_MODE=0 so TinyUSB
// is compiled in; the XIAO board default (=1) disables it.

#include <Arduino.h>
#include "USB.h"
#include "USBHID.h"
#include "USBCDC.h"
#include "rc_input.h"
#include "web_portal.h"
#include <math.h>

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
static const uint16_t REPORT_HZ  = 333;            // 250-500 Hz target
static const uint32_t REPORT_US  = 1000000UL / REPORT_HZ;
static const uint8_t  REPORT_ID  = 1;              // Report ID 1 (core's no-ID path is buggy)

// RC receiver signal input. XIAO ESP32-S3 pin D7 (silk "RX") = GPIO44.
// Auto-detects CRSF / SBUS / IBUS / PPM on this one pin.
static const int8_t   RC_PIN     = 44;             // D7

// Channel remap: AXIS_SOURCE[reportPos] = which 0-based RC stream channel goes
// into that HID report position. Tuned so neXt ends up showing the RX2SIM order
// (aileron=0, elevator=1, rudder=2, throttle=3, ch5..8=4..7) without touching
// the transmitter. Two effects are folded into this one table:
//   1. RX2SIM/neXt convention swaps throttle and rudder (A-E-R-T).
//   2. macOS/neXt enumerates THIS descriptor's 8 axes rotated by +2 (our X,Y
//      land on neXt axes 6,7), measured empirically and stable. We pre-rotate
//      the sources by -2 to cancel it.
// SBUS stream order for this radio is A,E,T,R,5,6,7,8 on indices 0..7.
static uint8_t AXIS_SOURCE[NUM_AXES] = { 6, 7, 0, 1, 3, 2, 4, 5 };

// Per-axis direction reverse, indexed by report position (same index as
// AXIS_SOURCE). With the map above the report positions carry:
//   0:ch7  1:ch8  2:aileron  3:elevator  4:rudder  5:throttle  6:ch5  7:ch6
// Rudder (position 4) reversed per request.
static const bool AXIS_REVERSE[NUM_AXES] = {
  false, false, false, false, true, false, false, false
};

// When no RC link is present, drive the axes with a sine self-test so the
// device is always visibly alive in a monitor.
// Sine periods stepped from MIN..MAX seconds across the channels so each
// axis sweeps at a visibly different rate.
static const float PERIOD_MIN_S = 2.0f;
static const float PERIOD_MAX_S = 6.0f;

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
class SimRXHID : public USBHIDDevice {
public:
  SimRXHID() {
    buildDescriptor();
    hid.addDevice(this, _descLen);
  }

  void begin() { hid.begin(); }
  bool ready() { return hid.ready(); }

  // data = NUM_AXES little-endian int16 axis values (32 bytes for 16 axes)
  bool send(const int16_t* axes) {
    return hid.SendReport(REPORT_ID, axes, NUM_AXES * sizeof(int16_t));
  }

  // TinyUSB asks for our report descriptor at enumeration.
  uint16_t _onGetDescriptor(uint8_t* dst) override {
    memcpy(dst, _desc, _descLen);
    return _descLen;
  }

private:
  USBHID  hid;
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
      put(0xC0);                       //   End Collection (Physical)
    put(0xC0);                         // End Collection (Application)
  }
};

static SimRXHID simrx;
static int16_t  axisBuf[NUM_AXES];
static RcInput  rcin;

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

// Fill axisBuf from the live RC channels (link up) or a sine self-test (no link).
static void fillAxes(uint32_t now) {
  if (rcin.linkUp()) {
    for (uint8_t i = 0; i < NUM_AXES; i++) {
      int16_t v = usToAxis(rcin.channelUs(AXIS_SOURCE[i]));
      axisBuf[i] = AXIS_REVERSE[i] ? (int16_t)-v : v;
    }
    return;
  }
  // No RC: independent sine per axis (period stepped MIN..MAX + phase offset).
  float t = now * 1e-6f;
  for (uint8_t i = 0; i < NUM_AXES; i++) {
    float frac   = (NUM_AXES > 1) ? (float)i / (NUM_AXES - 1) : 0.0f;
    float period = PERIOD_MIN_S + (PERIOD_MAX_S - PERIOD_MIN_S) * frac;
    float phase  = (2.0f * (float)M_PI) * (float)i / NUM_AXES;
    float s      = sinf((2.0f * (float)M_PI) * t / period + phase);
    axisBuf[i]   = (int16_t)lroundf(s * 32767.0f);
  }
}

void loop() {
  static uint32_t nextReport = 0;
  static uint32_t nextBeat   = 0;

  rcin.update();                                   // pump RC decoder every spin
  WebPortal::loop();                               // service captive DNS + web

  uint32_t now = micros();
  if ((int32_t)(now - nextReport) < 0) return;     // pace HID with micros()
  nextReport = now + REPORT_US;

  fillAxes(now);

  if (simrx.ready()) {
    simrx.send(axisBuf);

    // 1 Hz heartbeat blink + concise log (protocol + first 8 channels).
    if ((int32_t)(now - nextBeat) >= 0) {
      nextBeat = now + 1000000UL;
      digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
      USBSerial.printf(
        "LDRC2SIM src=%-5s n=%2u  ch1-8us=%4u %4u %4u %4u %4u %4u %4u %4u\n",
        rcin.linkUp() ? rcin.protocolName() : "sine", rcin.channelCount(),
        rcin.channelUs(0), rcin.channelUs(1), rcin.channelUs(2), rcin.channelUs(3),
        rcin.channelUs(4), rcin.channelUs(5), rcin.channelUs(6), rcin.channelUs(7));
    }
  }
}
