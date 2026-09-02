// LockDownRadioControl — RXV2  ::  1Defs.h
//
// This is the single global-storage header for the receiver. It is named with a
// numeric prefix so that #include order forces it FIRST — every other module
// header in the project assumes the types, enums, constants, and global objects
// declared here already exist.
//
// Mirrors the v1 receiver convention (utilities/1Definitions.h).
//
//*********************************************************************

#ifndef _SRC_1DEFS_H
#define _SRC_1DEFS_H

#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <ArduinoOTA.h>
#include <WebServer.h>
#include <SPI.h>
#include <RF24.h>
#include <Preferences.h>
#include <LittleFS.h>
#include <esp_ota_ops.h>
#include <esp32-hal-rmt.h>
#include <Update.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <esp_task_wdt.h>

//*********************************************************************
//  Firmware version
//*********************************************************************

constexpr const char* FW_VERSION = "RXV2-0.9.541-esc-read-honest-button";

//*********************************************************************
//  Auto-update manifest URLs
//*********************************************************************
// Two sources are consulted by /api/firmware/check:
//   - "local"  : a user-configurable URL stored in NVS (NVS_KEY_FW_MANIFEST,
//                see below). Typically the dev Mac's firmware_server.py on
//                the LAN. Falls back to FW_DEFAULT_LOCAL_MANIFEST_URL when
//                NVS holds no override, so a dev machine running the
//                server is auto-discovered without per-chip configuration.
//   - "public" : the hardcoded messiter.com mirror. Always HTTPS. Available
//                wherever the receiver has internet access, so a chip that
//                never sees the dev Mac can still pull official releases.
constexpr const char* FW_DEFAULT_LOCAL_MANIFEST_URL =
    "http://m4macmini.local:8000/manifest.json";
constexpr const char* FW_PUBLIC_MANIFEST_URL =
    "https://messiter.com/rxv2/release/manifest.json";

//*********************************************************************
//  WiFi / network defaults
//*********************************************************************
// WiFi credentials live ONLY in NVS — never compiled into the firmware. On a
// fresh chip (no NVS entry) the boot flow goes directly to AP mode so the user
// can enter their network details via the web UI.

constexpr const char* WIFI_DEFAULT_SSID     = "";
constexpr const char* WIFI_DEFAULT_PASSWORD = "";
constexpr const char* AP_SSID               = "LDRC_RX";    // fallback AP if STA fails
constexpr const char* OTA_HOSTNAME          = "LDRC_RX";    // -> http://LDRC_RX.local/
constexpr const char* OTA_PASSWORD          = nullptr;      // set to a string to require auth

enum NetMode : uint8_t {
    NET_INIT,
    NET_WAITING_RF,           // initial 10 s window
    NET_NO_WIFI,              // TX found in boot window — or user disabled WiFi
    NET_WIFI_CONNECTING,
    NET_WIFI_UP,
    NET_AP
};
inline NetMode  netMode       = NET_INIT;
inline uint32_t netStateStart = 0;
inline bool     otaStarted    = false;

// STA attempt counter. Lives outside netStep() so onWifiConnected() can
// zero it on success — otherwise a flaky mid-session reconnect would
// inherit a stale count from a much earlier boot-time retry and trip
// the AP fallback after one extra failure.
inline uint8_t  staAttempts   = 0;
// Set once the home network has proved ABSENT (repeated STA-join failures — the
// classic flying-field case: creds saved, but home WiFi nowhere in range). We
// then run a STABLE pure-AP (STA interface dropped, so it stops hopping the
// radio's channel and disrupting the phone) and only re-probe home WiFi rarely.
inline bool     staGaveUp     = false;
// Landing auto-recovery (WiFi/BLE revive 10 s after link loss) is ARMED by a
// LIVE link. "Fly now" disarms it — pressing it with no TX must not bring the
// radios (and the wave!) back 10 s later; they return only after a real
// fly-then-land cycle (or a reboot). Default true so boot paths are unchanged.
inline bool     wifiRecoveryArmed = true;
inline bool     apAutoEnabled = false;    // true when AP-only was AUTO-enabled (home net not found) — front page shows a notice; user clears it in WiFi settings

// Wall clock, courtesy of the phone (the RX has no RTC). Every page load
// POSTs the phone's Date.now() to /api/time; until that happens the clock
// is simply unknown (0) and flights save undated.
inline int64_t epochOffsetMs = 0;         // phone epoch_ms minus millis(); 0 = no sync yet
inline uint32_t epochNowS() {
    return epochOffsetMs ? (uint32_t)((epochOffsetMs + (int64_t)millis()) / 1000) : 0;
}
// The V1 transmitter's battery-backed RTC also tells us the time (param ID 34)
// so flights get dated with no phone present at all. The phone remains the
// better source when available: it outranks the TX for the rest of the boot,
// and it teaches us the timezone (the TX clock shows LOCAL wall time; stamps
// are UTC epoch) — remembered in NVS so field days work in local time too.
inline bool    epochFromPhone = false;    // a phone has synced this boot → ignore TX time
inline int16_t tzOffsetMin    = 0;        // local = UTC + tzOffsetMin (phone-taught, NVS "tzmin")

// Flight-save gap pardon (ack item 38): FlightLog sets the counter before its
// flash work; Radio.h's ack loader consumes it. In 1Defs because Radio.h is
// compiled before FlightLog.h.
constexpr uint32_t FLT_PARDON_MS = 3000;   // safety ceiling — auto-expires even if the cancel is lost
inline uint8_t  fltPardonAnnounceLeft = 0;

// One wave per revival (Malcolm 2026-08-04: the tail announced Bluetooth,
// then announced it AGAIN seconds later — the landing recovery and the WiFi
// state machine each triggered one). Automatic wave sites debounce through
// this; the app's explicit wave request bypasses it (a human asking always
// gets an answer).
// Deferred Fly-now teardown: the WiFi/BLE shutdown stalls the loop ~700 ms
// (measured LOOP-STALL 707ms, 2026-08-04 — Malcolm felt the servo twitch).
// The pardon (item 38) must be on the air BEFORE the stall, and acks only
// flow while the loop runs — so Fly-now schedules the teardown ~300 ms out
// instead of delay()ing into it.
inline uint32_t flyTeardownAtMs = 0;

inline bool autoWaveAllowed();   // defined below rx (needs rx.lastMillis)
inline uint32_t fltPardonMsToSend = FLT_PARDON_MS;   // 0 = "unignore now" (Malcolm's explicit end)
// What the TX's clock face actually holds is anyone's guess — Malcolm's reads
// UTC plus six minutes of drift (set in winter, never adjusted). So we LEARN
// its offset from true UTC whenever a phone sync and a TX time packet occur in
// the same boot (every bench session), remember it in NVS, and apply it on
// phone-free field days. Self-calibrating: drift and DST both wash out.
inline int32_t txClockOffS     = 0;       // TX clock face minus true UTC, seconds (NVS "txoffs")
inline bool    txClockOffKnown = false;

// Proven-tune nudge (Malcolm 2026-08-07): a tune that has flown several
// flights with NO further edits has earned a deliberate backup. Any tuning
// write (app or TX) sets the RAM flag; each NEW flight save consumes it
// (gen++, counter reset) or increments the counter — persisted inside the
// flight save's already-pardoned flash window. state.json exposes both;
// the app's front page nudges at >= 6 flights, once per gen.
inline bool     tuneEditsPending = false;   // RAM only
inline uint16_t tuneEditGen      = 0;       // NVS "egen"
inline uint32_t tuneFlightsSince = 0;       // NVS "fse"
constexpr const char* NVS_KEY_EDIT_GEN       = "egen";
constexpr const char* NVS_KEY_FLT_SINCE_EDIT = "fse";

constexpr uint32_t RF_WINDOW_MS         = 1000;    // boot window: if a TX is heard within this 1 s, go RF-only (WiFi off). Short so WiFi comes up fast when there's no TX (dev); means the TX must be ON BEFORE the receiver to suppress WiFi — which is standard RC practice (TX on first) anyway.
// RF-only "fly mode" auto-recovery: if the TX link then stays lost this long,
// bring WiFi back up by itself so the user can reach the receiver after landing
// without a power-cycle. NB this only runs in real flight (not sim, where WiFi
// is kept on for convenience). A brief airborne dropout this long would also
// re-enable WiFi mid-air — bump it up if that worries you (you can't really fly
// 10 s with zero link, so it usually means you're down).
constexpr uint32_t WIFI_REENABLE_AFTER_LOST_MS = 10000;
// STA-join timeout per attempt. Stepped up from 12 s → 18 s → 25 s
// because users kept seeing "WiFi password lost" symptoms that were
// really slow router-side associations (stale DHCP leases, channel
// congestion at boot) tripping AP fallback while the credentials in
// NVS were still intact. With WIFI_STA_RETRY_MAX = 5, the chip now
// patiently retries STA for ~125 s before giving up — long enough to
// outlast any sane router hiccup. A real wifi-creds-gone case still
// surfaces immediately because we go straight to AP when NVS is empty
// (startWifiStation short-circuits when ssid is blank).
constexpr uint32_t WIFI_CONNECT_MS      = 25000;
constexpr uint32_t AP_STA_RETRY_MS      = 20000;   // in AP-only WITH saved creds, retry home WiFi this often (self-heal)
constexpr uint8_t  STA_GIVEUP_ATTEMPTS  = 4;       // after this many failed STA joins (~100 s), assume home WiFi is ABSENT (field) → stable pure-AP
constexpr uint32_t AP_RECHECK_MS        = 300000;  // once pure-AP (gave up), re-probe home WiFi only this often (one brief attempt) so the field AP stays stable
constexpr uint32_t LINK_STATS_GRACE_MS  = 3000;    // link stats start when the connection is this old — the V1 TX's bind/model-ID handshake pauses its RF for ~1-2 s after first contact (its own green light does the same)
constexpr uint32_t LINK_LIVE_MS         = 2000;    // a TX packet within this window = link live (defer blocking web work)
constexpr uint8_t  WIFI_STA_RETRY_MAX   = 5;

// *** DEV FLAG — set to false before shipping ***
// When true: skip the RF-discovery boot window and go straight to WiFi STA,
// even if the TX is on at boot. Lets us iterate without having to power-cycle
// the TX before every reflash. Now false: WiFi is auto-managed (RF-only when a
// TX is present at boot; auto-re-enabled after the link is lost — see netStep).
// Sim mode keeps WiFi on regardless (the boot decision in main.cpp ORs in
// simEnabled), so the develop-over-WiFi-while-simming workflow still works.
constexpr bool     DEV_KEEP_WIFI         = false;

//*********************************************************************
//  Pin map (XIAO ESP32-C3 / -S3, same pinout in either footprint)
//*********************************************************************
// PCB pads, GPIO numbers, and what they connect to. See PINOUT.md for the
// definitive table that goes with the PCB design.
//
//   D2  (GPIO 4)  -> Radio1 CE        D7  (GPIO 20) -> SPI MISO (shared)
//   D3  (GPIO 5)  -> Radio1 CSN       D8  (GPIO 8)  -> SPI SCK  (shared)
//   D0  (GPIO 2)  -> Radio2 CE        D10 (GPIO 10) -> SPI MOSI (shared)
//   D1  (GPIO 3)  -> Radio2 CSN       D4  (GPIO 6)  -> Radio3 CE  (triple-radio PCB only)
//                                     D9  (GPIO 9)  -> Radio3 CSN (triple-radio PCB only, S3 only)
//   LED -> LED_BUILTIN  (XIAO onboard, freed D4 from heartbeat duty)
//   D5  (GPIO 7)  -> UART RX (FC telemetry in — CRSF / FBUS / IBUS2 sensor)
//   D6  (GPIO 21) -> UART/RMT TX (RC out — SBUS / CRSF / IBUS / PPM)
//
// Note: Radio3 uses D9, which on the older ESP32-C3 is the BOOT strap pin (see
// next note). On the S3 (production target) D9 = GPIO 9 is a plain GPIO with
// no boot-strap meaning. The triple-radio PCB variant is therefore S3-only.
//
// Why MISO is NOT on D9 (GPIO 9):
//   GPIO 9 on the ESP32-C3 doubles as the BOOT strap pin sampled at every
//   reset. If LOW at reset, the chip enters USB-download mode instead of
//   running flash. With the nRF24's MISO output wired there, transient LOW
//   levels during the module's power-on-reset can drag GPIO 9 down at exactly
//   the wrong moment, making cold-boot unreliable. Routing MISO through the
//   GPIO matrix to D7 (GPIO 20) removes the conflict.

// Use the symbolic D-named pad constants (defined in the Seeed variant headers)
// rather than raw GPIO numbers, because the underlying GPIO assignments differ
// between the XIAO ESP32-C3 and ESP32-S3 even though the physical pad labels
// (D0..D10) are identical. Example: D6 = GPIO 21 on C3, GPIO 43 on S3.
// With Dx names the same firmware binary builds correctly for either chip.

// Heartbeat goes to the XIAO module's onboard user LED (active-LOW). On S3 the
// onboard LED is GPIO 21 (LED_BUILTIN from the Seeed variant). This frees the
// D4 pad on the PCB as a fully-free GPIO (ADC1_CH4 on S3) for future use.
constexpr uint8_t LED_PIN      = LED_BUILTIN;
constexpr uint8_t PIN_NRF_CE   = D2;   // Radio1 CE
constexpr uint8_t PIN_NRF_CSN  = D3;   // Radio1 CSN
constexpr uint8_t PIN_NRF_CE2  = D0;   // Radio2 CE   (dual-radio PCB or higher)
constexpr uint8_t PIN_NRF_CSN2 = D1;   // Radio2 CSN  (dual-radio PCB or higher)
constexpr uint8_t PIN_NRF_CE3  = D4;   // Radio3 CE   (triple-radio PCB only; S3 only)
constexpr uint8_t PIN_NRF_CSN3 = D9;   // Radio3 CSN  (triple-radio PCB only; S3 only)
constexpr int8_t  PIN_SPI_SCK  = D8;   // shared
constexpr int8_t  PIN_SPI_MISO = D7;   // shared — kept OFF D9 because D9 is the C3 BOOT strap
constexpr int8_t  PIN_SPI_MOSI = D10;  // shared
constexpr int8_t  PIN_SBUS_TX  = D6;   // RC output (UART/RMT)
constexpr int8_t  PIN_FC_RX    = D5;   // FC telemetry RX (UART)

// Optional external status LED on the D4 pad. D4 doubles as Radio3 CE on the
// triple-radio PCB; on a 2-radio board that pad is free, so when Radio3 is
// absent the firmware drives an LED here:  OFF = bound but no link ·
// ON = bound + receiving · 2 Hz flash = binding (unbound). Same physical pad as
// PIN_NRF_CE3, but only ever driven when radio 3 is absent — so the triple-radio
// variant is unaffected.
constexpr uint8_t PIN_STATUS_LED         = D4;
constexpr bool    STATUS_LED_ACTIVE_HIGH = true;   // LED wired pad -> resistor -> LED -> GND

constexpr uint32_t NRF_SPI_HZ = 4000000;     // 4 MHz — conservative, eliminates marginal timing

//*********************************************************************
//  v1 protocol constants (mirror v1's utilities/1Definitions.h)
//*********************************************************************

constexpr uint8_t V1_DEFAULT_PIPE[5] = { 0x23, 0x94, 0x3e, 0xbe, 0xb7 };
constexpr uint8_t V1_RECOVERY_CH     = 82;     // FHSS_Recovery_Channels[2] — v1 starts Reconnect here
constexpr uint8_t V1_PIPE_NUMBER     = 1;

// v1 FHSS hop table — UK-friendly channels, in hop order.
constexpr uint8_t FHSS_CHANNELS[83] = {
    51, 28, 24, 61, 64, 55, 66, 19, 76, 21, 59, 67, 15, 71, 82, 32, 49, 69, 13,  2,
    34, 47, 20, 16, 72, 35, 57, 45, 29, 75,  3, 41, 62, 11,  9, 77, 37,  8, 31, 36,
    18, 17, 50, 78, 73, 30, 79,  6, 23, 40, 54, 12, 80, 53, 22,  1, 74, 39, 58, 63,
    70, 52, 42, 25, 43, 26, 14, 38, 48, 68, 33, 27, 60, 44, 46, 56,  7, 81,  5, 65,
     4, 10,  0
};
constexpr uint8_t  HOP_TIME_MS         = 8;   // v1 HOPTIME → ~100 Hz FHSS
constexpr uint16_t MAC_ACK_THRESHOLD   = 200; // MAC on the first N acks of each connection (dense, a half per ack), then telemetry. v1 used 20; bumped so both MAC halves land reliably even if a radio swap fires during the opening burst, while still handing over to telemetry within ~0.4 s so the TX never starves (see loadNextAck)
constexpr uint16_t MAC_STICK_DEADBAND  = 200;
constexpr uint8_t  MAC_MOVE_CONFIRM    = 3;    // a channel must exceed the deadband on this many packets before "being flown" latches (rejects single-packet glitches)  // 12-bit counts a channel must move from its settled baseline to count as "being flown" → end ID broadcast (well above gimbal jitter, well below a real stick move)
constexpr uint8_t  MAX_TELEMETRY_ITEM  = 37;  // 36 = RX3 active time; 37 = phone-true local time for the TX RTC

// v1 channel 82 lives at index 14 of FHSS_CHANNELS. We bind there, then increment.
constexpr uint8_t  CHAN82_INDEX        = 14;

// RXV2 version stamp (RX board uniquely identifies itself to v1 TX).
constexpr uint8_t  RXV2_THIS_RADIO     = 1;
constexpr uint8_t  RXV2_V_MAJOR        = 2;
constexpr uint8_t  RXV2_V_MINOR        = 5;
constexpr uint8_t  RXV2_V_MINIMUS      = 6;       // must match TX's required version exactly — TX rejects any other value
constexpr char     RXV2_V_EXTRA        = 'R';     // R = RXV2 prototype
constexpr uint32_t RXV2_RECEIVER_TYPE  = 0x52580200;   // 'RX' 0x02 0x00 — sentinel

//*********************************************************************
//  Output protocol enum + persistence keys
//*********************************************************************
// FBUS and IBUS2 enum values are kept (so their parsers and case branches still
// compile) but are not user-selectable — PROTO_MAX gates the menu and the save
// validator. To re-enable them in the UI, raise PROTO_MAX.

enum Protocol : uint8_t {
    PROTO_SBUS  = 0,
    PROTO_CRSF  = 1,
    PROTO_IBUS  = 2,
    PROTO_PPM   = 3,
    PROTO_FBUS  = 4,
    PROTO_IBUS2 = 5,
};
constexpr uint8_t PROTO_MAX     = PROTO_PPM;
constexpr uint8_t PROTO_DEFAULT = PROTO_CRSF;   // CRSF is the common case (Rotorflight) — a fresh board talks to the FC out of the box

inline Protocol  currentProtocol = (Protocol)PROTO_DEFAULT;
inline bool      ppmInverted     = false;
inline bool      simEnabled      = false;    // "Drive simulator over USB" — present as a USB HID joystick (S3/TinyUSB only)
inline uint32_t  g_loopHz        = 0;        // diag: main-loop iterations/sec (radioPoll runs once per loop)
inline uint32_t  g_loopMaxUs     = 0;        // diag: worst single-loop duration in the last second (µs)

//*********************************************************************
//  NVS keys (Preferences namespace = "rxv2")
//*********************************************************************

constexpr const char* NVS_NAMESPACE      = "rxv2";
constexpr const char* NVS_KEY_PIPE       = "pipe";
constexpr const char* NVS_KEY_PIPE_BAK   = "pipebak";    // stashed pairing while bind mode is active — restored by /api/bind/cancel
constexpr const char* NVS_KEY_SSID       = "ssid";
constexpr const char* NVS_KEY_PASS       = "pass";
constexpr const char* NVS_KEY_BOARD_ID   = "board_id";   // 6-byte board ID; captured first boot, never changes
constexpr const char* NVS_KEY_FAILSAFE   = "fs";         // 16 x uint16 failsafe channel values (us); absent = not configured
constexpr const char* NVS_KEY_GEAR_RATIO = "gear";       // float main-gear ratio (motor:head); head speed = motor RPM / gearRatio. 1.0 = direct drive
constexpr const char* NVS_KEY_ARM_CH     = "armch";      // uint8 arming channel (1..16, 0=off): flight saved on DISARM after a real flight
constexpr const char* NVS_KEY_GAP_MIN    = "gapmin";
constexpr const char* NVS_KEY_TZ_MIN     = "tzmin";     // minutes local is ahead of UTC (phone-taught)
constexpr const char* NVS_KEY_TX_OFF_S   = "txoffs";    // TX clock face minus true UTC, seconds (learned)
constexpr const char* NVS_KEY_FLT_HEAD   = "flthead";    // ring head: physical slot of the NEWEST saved flight (kills the 20-file rotation storm)     // uint8 ms: a packet must be at least this LATE (beyond expected spacing) to count as a gap
constexpr const char* NVS_KEY_WAVE_CHS   = "wavechs";    // uint16 bitmask of channels waved when Bluetooth comes up (bit0=ch1); default ch1, 0=off
constexpr const char* NVS_KEY_BOOT_COUNT = "qbc";        // quick-boot counter for escape hatch
constexpr const char* NVS_KEY_PROTO      = "proto";
constexpr const char* NVS_KEY_PPM_INV    = "ppm_inv";
constexpr const char* NVS_KEY_FW_MANIFEST = "fwurl";   // URL of dev firmware server's manifest.json
constexpr const char* NVS_KEY_MODEL_NAME  = "nm";      // user-set model name (e.g. "Goblin 700"); empty = use default
constexpr const char* NVS_KEY_FS_MD5      = "fsmd5";   // md5 of the last-flashed littlefs image: identical-release fs updates are SKIPPED (flights survive untouched)
constexpr const char* NVS_KEY_SIM         = "sim";     // 1 = drive flight simulator over USB (HID joystick)
// Spool-up realism (Malcolm 2026-08-17, for neXt autorotation practice):
// leaving the throttle-hold bank must NOT snap the sim to full head speed
// with infinite acceleration and no torque. The dongle rate-limits throttle
// RISES like a real governor (drops stay instant — entering the auto is
// unchanged) and stabs the rudder while the head is accelerating.
constexpr const char* NVS_KEY_SIM_SPOOL   = "simspool";  // uint8 1 = spool-up realism on (default 0)
constexpr const char* NVS_KEY_SIM_SPOOL_S = "simspls";   // uint8 seconds for a full 1000→2000 µs spool (1..60, default 8)
constexpr const char* NVS_KEY_SIM_TORQUE  = "simtorq";   // int16 rudder stab in µs while spooling (signed for direction, default -120)
constexpr const char* NVS_KEY_SIM_RUD_CH  = "simrudch";  // uint8 rudder channel 1..16 (default 4)
constexpr const char* NVS_KEY_AUTOFLY     = "autofly";   // uint8 1 = auto fly mode: radios off when armed+flying detected (default ON)
constexpr const char* NVS_KEY_SIM_MOT_INV = "simmotinv"; // uint8 1 = high µs means motor OFF (inverted channel)
constexpr const char* NVS_KEY_SIM_PULSE   = "simsplp";   // uint8 1 = pulse (PWM) mode while spooling
constexpr const char* NVS_KEY_SIM_PULSEMS = "simsplpms"; // uint16 PWM period ms (50..1000, default 250)
constexpr const char* NVS_KEY_SIM_MOT_CH  = "simmotch";  // uint8 MOTOR/governor channel 1..16 (0 = not set → feature inert). NEVER default to the throttle STICK: on a heli that is the collective (2026-08-17 hotfix — enabling spool froze Malcolm's collective)
constexpr const char* NVS_KEY_SIM_MAP     = "simmap";  // 8-byte map: which RX channel (0..15) feeds each sim output
constexpr const char* NVS_KEY_SIM_REV     = "simrev";  // 8-byte per-output reverse flags (0/1)
constexpr const char* NVS_KEY_AP_ONLY     = "aponly";  // 1 = skip home-WiFi STA, run AP-only (flying field: no waiting on an out-of-range home network)
constexpr const char* NVS_KEY_AP_AUTO     = "apauto";  // 1 = the AP-only above was set AUTOMATICALLY (home net not found), so the UI shows a notice + the user can undo it
constexpr const char* NVS_KEY_CFG_REBOOT  = "cfgrb";
constexpr const char* NVS_KEY_OTA_BUSY    = "otabusy";  // 1 while a WiFi update is downloading; still set at boot = the update stalled and the watchdog rebooted us
constexpr const char* NVS_KEY_ESC_CATCH   = "esccatch"; // 1 = one-shot: poll MSP 217 for the first ~14 s of the next boot (Scorpion settings capture)
constexpr const char* NVS_KEY_CRSF_HZ     = "crsfhz";
constexpr const char* NVS_KEY_FC_TELEM    = "fctelem";
constexpr const char* NVS_KEY_VBAT_PIN    = "vbatpin";  // uint8 GPIO of the battery divider (0=off; 6=D4, 9=D9 — the free radio-3 pins on 2-radio boards)
constexpr const char* NVS_KEY_VBAT_RATIO  = "vbatrat";  // float divider ratio ((Rtop+Rbot)/Rbot): 23.0 for 220k/10k (12S), 11.0 for 100k/10k (6S)
constexpr const char* NVS_KEY_VBAT_CELLS  = "vbatcel";
constexpr const char* NVS_KEY_THR_CH      = "thrch";    // uint8 throttle channel (1..16, 0=off); held at THROTTLE_SAFE_US until the TX is first heard  // uint8 cell count for per-cell display (0 = not set, show pack volts only)  // uint8 1=expect FC on telemetry line (default); 0=ignore it (plain PWM converters echo junk that parses as telemetry)  // uint8 CRSF frame rate in Hz (50/100/250); some CRSF-to-PWM converters misbehave above ~100 Hz   // one-shot: web-initiated reboot to apply a setting → next boot skips the RF window, WiFi comes straight back

// A flight "ends" (and is saved to flash) after the link has been gone this
// long. The SAME threshold decides when a returning link is a NEW flight:
// radioPoll only resets the link stats + telemetry ring for gaps ≥ this, so a
// brief mid-flight dropout — exactly the event the blackbox exists to record —
// stays part of one continuous flight instead of silently wiping it.
constexpr uint32_t FLIGHT_SAVE_AFTER_MS = 15000;

constexpr uint8_t     QUICK_BOOT_THRESHOLD = 3;
constexpr uint32_t    QUICK_BOOT_RESET_MS  = 5000;

inline Preferences prefs;
inline bool forceWifiMode = false;

// Cached effective name + DNS-safe hostname, computed once in setup()
// after the board MAC is loaded so the hostname suffix is stable. Used
// by Network.h for AP SSID, mDNS hostname, and Arduino-OTA hostname.
inline String g_effectiveName;
inline String g_hostname;

//*********************************************************************
//  Channel-data periods + frame buffers
//*********************************************************************

constexpr uint32_t SBUS_PERIOD_MS = 14;     // ~71 Hz
constexpr uint32_t CRSF_PERIOD_MS = 4;      // ~250 Hz
inline uint8_t crsfRateHz = 250;
inline bool    fcTelemetryEnabled = true;
inline uint8_t vbatPin      = 0;        // battery-divider ADC GPIO (0 = feature off)
inline float   vbatRatio    = 23.0f;    // divider ratio
inline uint8_t vbatCellsCfg = 0;        // user-set cell count (0 = unset)
inline float   vbatVolts    = 0.0f;     // smoothed pack voltage (V) — app + blackbox
inline float   vbatVoltsTx  = 0.0f;     // EXTRA-slow (~7 s) copy — ONLY the V1 TX screen (Malcolm 2026-08-21)
inline uint32_t channelPacketsRx = 0;   // CHANNEL packets decoded this session (throttle stays pinned until a stable stream)
inline bool    vbatAuto     = false;
inline uint8_t throttleChannel = 3;         // NVS_KEY_THR_CH — boot-safe low until the TX is heard
// Spool-up realism state (sim mode only — see NVS_KEY_SIM_SPOOL)
inline bool    simSpoolEnabled  = false;
inline uint8_t simSpoolSeconds  = 8;        // full 1000→2000 µs spool time
inline int16_t simTorqueUs      = -120;     // rudder stab while spooling (signed)
inline uint8_t simRudderChannel = 4;
inline bool autoFlyEnabled = true;   // radios off automatically once armed + flying (Malcolm 2026-08-24)
// With Rotorflight present, auto fly mode is FORCED on — not switchable.
// Born of the 2026-08-24 crash: flying with the config link alive lets a
// blocking MSP wait starve the CRSF stream; Rotorflight reads the silence
// as signal loss and cuts the motor. Updated every loop from FC detection.
inline bool autoFlyForcedNow = false;
inline bool autoFlyActive() { return autoFlyEnabled || autoFlyForcedNow; }
inline uint8_t simMotorChannel  = 0;        // 0 = unset: spool-up does nothing until chosen
// Pulse mode (Malcolm 2026-08-25, "manual PWM — is my plan nuts?!" — it is
// not): neXt thresholds the motor channel to pure on/off, so a ramped LEVEL
// is invisible to it. Pulsing the channel between full off and full on with
// a rising duty cycle uses the sim's own rotor inertia (its spool-down IS
// realistic) as the averaging filter — head speed then climbs through the
// spool like a real governor. The ramp's progress becomes the duty.
inline bool     simSpoolPulse    = false;    // pulse (PWM) the motor channel while spooling
inline uint16_t simSpoolPulseMs  = 250;      // PWM period in ms (50..1000)
inline bool    simMotorInverted = false;    // true = HIGH µs means motor OFF (Malcolm's ch6)
inline volatile uint16_t simSpoolDbgRaw  = 0;   // live: raw motor-channel µs in
inline volatile uint16_t simSpoolDbgOut  = 0;   // live: µs actually sent to the sim
inline volatile bool     simSpoolDbgRamp = false;
constexpr uint16_t THROTTLE_SAFE_US = 885;  // well below 900: any ESC reads this as motor OFF    // pin was found by the sniffer, not set by the user   // NVS_KEY_FC_TELEM: false = ignore telemetry-line input + no Rotorflight/MSP probes            // user-configurable (NVS_KEY_CRSF_HZ): 250 native, 100/50 for fussy CRSF-to-PWM converters
constexpr uint32_t IBUS_PERIOD_MS = 7;      // ~140 Hz
constexpr uint32_t PPM_PERIOD_MS  = 25;     // 40 Hz — leaves 2-3 ms over the ~22 ms frame
constexpr uint32_t FBUS_PERIOD_MS = 9;      // ~111 Hz

inline uint16_t channelMicros[16];                       // initialised in setup() to 1500us
inline uint32_t lastChannelDataMs = 0;
// Failsafe (no-signal) channel values, captured from the live channels via the
// web UI and stored in NVS (NVS_KEY_FAILSAFE). When set, these are loaded as the
// pre-link defaults at boot so a receiver powered up without a transmitter sits
// in a SAFE posture (e.g. disarmed) instead of all-1500. failsafeSet=false => use
// the generic safe default (ch1-5=1500, aux low) instead.
inline uint16_t failsafeMicros[16] = {0};
inline bool     failsafeSet        = false;
// Main-gear ratio (motor turns : head turns). Head speed telemetry = motor RPM
// / gearRatio. 1.0 = direct drive. User-set on the View-channels page, NVS-backed.
inline float    gearRatio          = 1.0f;
inline uint8_t  armingChannel      = 0;    // 1..16 = save the flight on DISARM of this channel; 0 = off (use link-loss save)
// Gap accounting is LATENESS-based (Malcolm 2026-07-27): every packet arrives
// ~2 ms after the last (4 ms buddy-boxing) — that spacing is measured, not a
// gap. A packet only counts as a gap when it's at least this many ms LATER
// than the measured spacing, and it's billed only for the late part.
inline uint8_t  gapMinMs           = 5;    // definable via POST /api/gapmin
inline uint16_t waveChannelMask    = 0x0001; // channels waved when Bluetooth comes up (bit0=ch1); Malcolm's plane = 1+6
// Legal decoded-channel range (microseconds), == v1 MINMICROS/MAXMICROS. A
// decoded frame with any channel outside this isn't real channel data (a
// bind/MAC/parameter frame misread, or a corrupt decode); decodeChannelData()
// rejects it and holds the last good values — v1 CheckForCrazyValues parity.
constexpr uint16_t CH_MIN_MICROS = 500;
constexpr uint16_t CH_MAX_MICROS = 2500;
// Output failsafe timeout (ms): how long the link may be silent before the
// output stage treats it as lost. == v1 FAILSAFE_TIMEOUT (1500). The old 500 ms
// was short enough that a brief glitch detached the CRSF UART and the FC saw a
// momentary RX-loss (channels flashed to zero). Below this we keep streaming the
// held channel values, exactly as v1 keeps sending SbusChannels.
constexpr uint32_t OUTPUT_FAILSAFE_MS = 1500;
inline uint8_t  sbusFrame[25];
inline uint8_t  crsfFrame[26];
inline uint8_t  ibusFrame[32];
inline uint8_t  fbusFrame[26];
inline uint32_t lastSbusMs    = 0;
inline uint32_t sbusFramesOut = 0;          // legacy name — counts ALL output frames

// PPM via RMT
constexpr uint32_t PPM_SYNC_US     = 300;
constexpr uint32_t PPM_FRAME_US    = 22500;
constexpr uint8_t  PPM_CHANNELS    = 8;
inline rmt_data_t  ppmItems[PPM_CHANNELS + 1];
inline bool        ppmRmtReady = false;
inline rmt_obj_t*  ppmRmt      = nullptr;

//*********************************************************************
//  RX statistics, board MAC, bind state
//*********************************************************************

struct RxStats {
    uint32_t packets       = 0;
    uint32_t lastMillis    = 0;
    uint8_t  lastPayload   = 0;
    uint8_t  lastBytes[32] = {0};
    uint8_t  maxPayload    = 0;
    uint8_t  maxBytes[32]  = {0};
    uint32_t acksWritten   = 0;
};
inline RxStats rx;

// Keyed to the LANDING, not the clock: Malcolm reports the spurious second
// wave can come 1-2 MINUTES later (the field's STA-retry -> AP-fallback
// transition re-announces BLE after ~100-125s of hopeful WiFi retries), so a
// time window is the wrong tool. rx.lastMillis freezes at the last packet of
// a landing — a unique per-landing key. One wave per landing, unlimited
// flights per day, and internal WiFi/BLE restarts stay silent.
inline uint32_t lastWaveLinkEpoch = 1;   // rx.lastMillis we last waved for (1 = never)
inline bool autoWaveAllowed() {
    if (rx.lastMillis == lastWaveLinkEpoch) return false;
    lastWaveLinkEpoch = rx.lastMillis;
    return true;
}

// BLE-interference quarantine for the link statistics (Malcolm 2026-07-27,
// lodge test: TX-side perfect at 1 m, RX blackbox pessimistic). The ESP32's
// BT radio — a phone attached over BLE, or the connect/disconnect bursts —
// desenses the nRF24s centimetres away. Those deaf spells are OUR doing, not
// link quality, and never occur in real flight (fly mode kills BLE). While
// quarantined, gaps and swaps are not billed to the flight.
inline volatile bool bleStatsClientUp   = false;  // mirrors BLE client attach (set in BleConfig.h)
inline volatile bool bleStatsRadioOn    = false;  // mirrors BLE advertising/on (set in BleConfig.h)
inline uint32_t      bleStatsQuietUntilMs = 0;    // covers connect/disconnect/start/stop bursts
// Malcolm 2026-07-27 round 2: "nobody flies with Bluetooth switched on —
// that would be nuts." If the BT radio is on AT ALL, gap/swap figures are
// hearsay — don't count them, full stop. Stats accumulate only in genuine
// RF-only (fly-mode) conditions, which is the only regime that matters.
// Self-stall quarantine (Malcolm's field find 2026-07-31): the disarm-edge
// flight save writes flash from loop() — with 20 slots the save + rotation
// stalls the loop ~1 s, the nRF FIFO overflows, and the next packet was
// billed 808 ms late AT THE DISARM. Deliberate on-ground housekeeping must
// not be measured as link quality: the save announces itself here first.
inline uint32_t statsSelfStallUntilMs = 0;

// millis() of the last channel MOVEMENT (any channel changed >12 us).
// Shared by the battery guardian and the flight save: 'sticks still' means
// the pilot is provably not flying (an autorotation is never hands-still).
inline uint32_t lastChMoveMs = 0;

inline bool bleStatsQuarantine() {
    return bleStatsRadioOn || bleStatsClientUp ||
           (int32_t)(bleStatsQuietUntilMs   - millis()) > 0 ||
           (int32_t)(statsSelfStallUntilMs  - millis()) > 0;
}
// Fly-now stats zero (Malcolm 2026-07-28): set by the fly_arm path, fired
// from loop() ~3 s later — the flight record restarts once the radios are
// truly quiet, so the flight begins at Fly, not at the bench.
inline uint32_t statsZeroAtMs = 0;

// Per-connection (per-flight) link statistics — inter-packet gaps, frame rate,
// and a gap histogram. Reset when a fresh connection starts (a >500 ms gap), so
// after landing these hold the just-completed flight's figures — post-flight
// analysis without the transmitter. Gaps in microseconds (micros() gives the
// resolution the ~500 Hz frame needs; a flight is well under the ~71 min wrap).
struct LinkStats {
    uint32_t connStartMs = 0;    // when this connection began
    uint32_t paramOps = 0;       // Rotorflight edits/reads via the TX this session — explains bigger gaps
    uint32_t packets     = 0;    // packets received this connection
    uint32_t lastPktUs   = 0;    // micros() of the last packet
    uint32_t maxGapUs    = 0;    // longest LATENESS (interval minus expected spacing)
    uint64_t gapSumUs    = 0;    // sum of counted lateness (for the average)
    uint32_t gapCount    = 0;
    // Expected packet spacing (~2 ms solo, ~4 ms buddy-box), derived the
    // V1 TX's way: packets counted over ~1-second windows (Malcolm's
    // design — his TX counts acks per second). Interval-based estimators
    // failed twice: a mean absorbed retry delays (read 483 on a 503 link)
    // and a floor tracker collapsed into FIFO read-bursts (near-0 "gaps"
    // when the loop drains two packets in one gulp).
    uint32_t expectedGapUs = 0;
    uint32_t secWindowStartMs = 0;   // rate window opened (0 = not counting)
    uint16_t secWindowCount   = 0;   // packets in the current window
    // lateness histogram (ms buckets): 0:<8  1:8-16  2:16-32  3:32-64  4:64-150  5:>=150
    uint32_t hist[6]     = {0};
    // Ring of the most recent recorded gaps. The TX's power-off routine stalls
    // its RF loop (shutdown screen / countdown) and then sends a few dying
    // packets, which records one or two HUGE gaps in the flight's final
    // seconds — shutdown artifacts, not link quality. maybeSaveFlight uses
    // this ring to trim them out of the saved record (Malcolm 2026-07-23:
    // "the final gap — switching off the transmitter — might be worrying").
    struct TrailGap { uint32_t us; uint32_t atMs; uint8_t bucket; };
    TrailGap recent[6]   = {};
    uint8_t  recentIdx   = 0;
    // Per-flight transceiver accounting (Malcolm 2026-07-23): radioSwaps and
    // radioActiveMs[] accrue for the LIFETIME of the boot — snapshot them at
    // flight start so the flight record can report this flight's share.
    uint32_t swapsAtStart      = 0;
    uint32_t radioMsAtStart[3] = {0, 0, 0};
    // Continuously refreshed while the link is LIVE, frozen at signal loss:
    // per-flight radio time reads (AtLive - AtStart) so the flight's split
    // stops at the last packet instead of growing while the radios keep
    // listening on the bench (R1+R2 exceeded the flight duration before).
    uint32_t radioMsAtLive[3]  = {0, 0, 0};
    // Same freeze for the SWAP count (Malcolm 2026-07-27): the radios hunt
    // (and swap) endlessly while the TX is off — those bench swaps must not
    // be billed to the flight. Refreshed while live, frozen at signal loss.
    uint32_t swapsAtLive       = 0;
    // The flight's OWN swap counter (same day, round 2): incremented at the
    // swap site only when the link is live, grace has passed, and we're not
    // in BLE quarantine — so bench hunting AND BLE-desense swaps never land
    // in the flight record at all.
    uint32_t flightSwaps       = 0;
    uint32_t maxGapAtMs = 0;   // millis() when maxGapUs was recorded (0 = unknown)
    // False until the connection outlives LINK_STATS_GRACE_MS — the V1 TX's
    // connect handshake pauses its RF, so stats/baselines start after it.
    bool     graceDone         = false;
};
inline LinkStats linkStats;

// Shutdown-artifact trim: a gap this big, recorded this close to the link's
// death, is treated as the TX switching off rather than flight link quality.
constexpr uint32_t SHUTDOWN_TRIM_WINDOW_MS = 8000;
constexpr uint32_t SHUTDOWN_TRIM_MIN_US    = 150000;   // < real jitter never reaches this; failsafe class

// Gap figures with the shutdown artifact removed — non-destructive copies.
// While the link is LIVE this returns the honest raw stats (an ongoing real
// dropout must show). Once the link has been dead a few seconds, the trailing
// failsafe-class gaps (the TX's power-off stall) are excluded, so neither the
// live "Current" view nor the saved record shows a scary bogus longest-gap
// (Malcolm's lodge test, 2026-07-23). Single code path for save + display.
inline void gapsForDisplay(uint32_t& maxUs, uint32_t& avgUs, uint32_t hist[6], uint32_t& maxAtMs) {
    maxUs   = linkStats.maxGapUs;
    maxAtMs = linkStats.maxGapAtMs;
    for (uint8_t i = 0; i < 6; ++i) hist[i] = linkStats.hist[i];
    uint64_t sum = linkStats.gapSumUs;
    uint32_t cnt = linkStats.gapCount;
    bool linkDead = rx.lastMillis != 0 && (uint32_t)(millis() - rx.lastMillis) >= 3000;
    if (linkDead) {
        bool trimmedMax = false; uint32_t survivorMax = 0, survivorAt = 0;
        for (const auto &g : linkStats.recent) {
            if (!g.us) continue;
            // ANY counted gap in the trailing window is a shutdown artifact
            // candidate — the V1 TX's power-off ritual also hesitates in the
            // tens-of-ms class, not just the failsafe class (0.9.275).
            if ((uint32_t)(rx.lastMillis - g.atMs) <= SHUTDOWN_TRIM_WINDOW_MS) {
                if (hist[g.bucket]) hist[g.bucket]--;
                if (cnt) cnt--;
                sum -= (sum >= g.us) ? g.us : sum;
                if (g.us == maxUs) trimmedMax = true;
            } else if (g.us > survivorMax) { survivorMax = g.us; survivorAt = g.atMs; }
        }
        if (trimmedMax) {
            maxUs = survivorMax;   // best surviving estimate of the real max
            maxAtMs = survivorAt;
            if (!maxUs) {          // else: ceiling of the highest populated bucket
                static const uint32_t ceilUs[6] = {8000, 16000, 32000, 64000, 150000, 150000};
                for (int8_t b = 5; b >= 0; --b)
                    if (hist[b]) { maxUs = ceilUs[b]; break; }
                maxAtMs = 0;       // position unknown for a bucket-ceiling estimate
            }
        }
    }
    avgUs = cnt ? (uint32_t)(sum / cnt) : 0;
}

// Once the link has been dead a few seconds, make the shutdown trim
// PERMANENT: a quick TX-on again (same flight continuing) would otherwise
// resurrect the power-off artifact into the live stats — gapsForDisplay
// only trims while the link is dead. One shot per loss episode; called
// every loop from main.cpp.
inline void scrubShutdownGapsTick() {
    static uint32_t scrubbedForLoss = 0;
    if (rx.lastMillis == 0 || (uint32_t)(millis() - rx.lastMillis) < 3000) return;
    if (scrubbedForLoss == rx.lastMillis) return;
    scrubbedForLoss = rx.lastMillis;
    bool trimmedMax = false; uint32_t survivorMax = 0, survivorAt = 0;
    for (auto &g : linkStats.recent) {
        if (!g.us) continue;
        // ANY counted gap in the trailing window is a shutdown artifact
        // candidate — the V1 TX's power-off ritual also hesitates in the
        // tens-of-ms class, not just the failsafe class (0.9.275).
        if ((uint32_t)(rx.lastMillis - g.atMs) <= SHUTDOWN_TRIM_WINDOW_MS) {
            if (linkStats.hist[g.bucket]) linkStats.hist[g.bucket]--;
            if (linkStats.gapCount) linkStats.gapCount--;
            linkStats.gapSumUs -= (linkStats.gapSumUs >= g.us) ? g.us : linkStats.gapSumUs;
            if (g.us == linkStats.maxGapUs) trimmedMax = true;
            g = {};                     // gone for good
        } else if (g.us > survivorMax) { survivorMax = g.us; survivorAt = g.atMs; }
    }
    if (trimmedMax) {
        linkStats.maxGapUs   = survivorMax;
        linkStats.maxGapAtMs = survivorAt;
        if (!linkStats.maxGapUs) {
            static const uint32_t ceilUs[6] = {8000, 16000, 32000, 64000, 150000, 150000};
            for (int8_t b = 5; b >= 0; --b)
                if (linkStats.hist[b]) { linkStats.maxGapUs = ceilUs[b]; break; }
            linkStats.maxGapAtMs = 0;
        }
    }
}

// BLE-ready servo announce: when the config radios come back up after the TX
// went quiet, wave the ailerons (ch1) so the user knows — then settle back to
// the failsafe posture. Non-blocking; driven from Output.h.
inline uint32_t bleWaveStartMs = 0;                    // != 0 → wave in progress
constexpr uint32_t BLE_WAVE_MS      = 1600;            // total wave duration
constexpr float    BLE_WAVE_HZ     = 2.5f;             // wiggle rate
constexpr int16_t  BLE_WAVE_AMPL_US = 150;             // gentle: ±150 µs around failsafe

// Flight telemetry time-series — one sample/second of ESC temp, head speed and
// battery, into a ring holding the last ~20 min. Reset on a fresh connection so
// it captures the immediately-preceding flight; plotted on the Black box page so
// you can watch (e.g.) ESC temp track head speed. ~6 bytes/sample × 1200 ≈ 7 kB.
struct TeleSample {
    uint8_t  escC   = 0;     // ESC temperature, °C
    uint16_t headRpm = 0;    // head speed, rpm
    uint16_t cV     = 0;     // battery, centivolts (V × 100)
    uint16_t dA     = 0;     // current, deci-amps (A × 10)
};
constexpr uint16_t TELE_RING = 1200;
inline TeleSample teleRing[TELE_RING];
inline uint16_t   teleCount = 0;         // valid samples (<= TELE_RING)
inline uint16_t   teleHead  = 0;         // next write index (ring)
inline uint32_t   teleLastSampleMs = 0;

inline uint8_t boardMac[8] = {0};      // v1 sends our 8-byte board ID in early acks

struct BindStateT {
    bool     bound          = false;
    uint8_t  pipe[5]        = {0};
    uint32_t boundMillis    = 0;
    uint32_t attempts       = 0;
};
inline BindStateT bindState;

//*********************************************************************
//  Dual-radio state
//*********************************************************************
// Both radios share SCK/MOSI/MISO, each with its own CE/CSN. Radio1 is primary;
// Radio2 is optional (probed at boot). Both configured identically so we can
// swap CE between them on packet loss — same pattern as v1 on the Teensy.

inline RF24 radio1(PIN_NRF_CE,  PIN_NRF_CSN,  NRF_SPI_HZ);
inline RF24 radio2(PIN_NRF_CE2, PIN_NRF_CSN2, NRF_SPI_HZ);
inline RF24 radio3(PIN_NRF_CE3, PIN_NRF_CSN3, NRF_SPI_HZ);
inline RF24* radios[3]    = { &radio1, &radio2, &radio3 };
inline RF24* currentRadio = &radio1;

// Independent per-slot presence — probed at boot. radioPresent[i] is true
// iff the chip at slot i+1 responds on SPI. swapRadios() rotates only
// through present slots, so a missing or failed radio is skipped.
inline bool     radioPresent[3]      = { false, false, false };
inline uint8_t  numRadiosPresent     = 0;        // 0..3
inline uint8_t  activeRadioIdx       = 1;       // for UI display: 1, 2, or 3
inline uint32_t radioSwaps           = 0;
inline uint32_t lastRadioSwapMs      = 0;

// Per-radio active-time accumulators. radioActiveMs[i] counts ms that slot
// i+1 has spent as the currently-listening radio (across all swaps). The
// time accumulating for the active radio right now is held separately in
// radioActiveStartMs and is added in by radioElapsedSec() when read.
inline uint32_t radioActiveMs[3]     = { 0, 0, 0 };
inline uint32_t radioActiveStartMs   = 0;

// Stepped down from 200 ms → 50 ms each after the prototype test
// showed swaps were sluggish during real fades. At the V1 protocol's
// ~125 Hz packet rate, 50 ms = about 6 missed packets — quick enough
// to find a working slot during real antenna shadowing without
// thrashing on the routine 1–2-packet gaps. The 50 ms cooldown is
// enough for the incoming radio to wake out of standby and start
// receiving before we'd consider swapping again.
constexpr uint32_t RADIO_SWAP_PACKET_TIMEOUT_MS = 50;
constexpr uint32_t RADIO_SWAP_COOLDOWN_MS       = 50;
// Once we've cycled through every present radio without a single packet coming
// back, the TX is simply gone — swapping again at the 50 ms cooldown just storms
// (~20 swaps/s: floods the event log + serial, blocks the loop ~13 ms each, and
// the burst tears down CRSF output → channels flash to zero in the FC). After
// trying all radios we back off to this slow dead-link probe; the instant a real
// packet lands, fast failover re-arms.
constexpr uint32_t RADIO_SWAP_DEAD_RETRY_MS     = 1000;

//*********************************************************************
//  Ack-payload rotation state
//*********************************************************************

constexpr uint8_t ACK_PAYLOAD_BYTES = 6;     // v1 PAYLOADSIZE
inline uint8_t  ackByteZero    = 1;
// Run the MAC broadcast phase like v1 does — the v1 TX uses ack[0]==0 / ack[0]==1
// frames to capture the receiver's 8-byte MAC and decide bind success. With this
// initialised at 0 (not MAC_ACK_THRESHOLD), the first MAC_ACK_THRESHOLD acks of
// each connection send the real chip boardMac in two halves so the TX recognises
// the receiver, then loadNextAck() hands over to the telemetry rotation. Reset to
// 0 on every reconnect (a >500 ms ack gap), so the MAC is re-delivered each time.
inline uint32_t macAcksSent    = 0;
inline bool     idBroadcasting = false;      // true while we're putting the board ID on ack slots 0/1 (diagnostic, surfaced in state.json)
inline bool     beingFlown     = false;      // latched once a control channel moves past MAC_STICK_DEADBAND on the current connection
inline uint8_t  telemetryItem  = 0;
inline uint8_t  nextChannelIdx = CHAN82_INDEX;
inline uint32_t lastHopMs      = 0;
inline bool     hopPending     = false;
inline bool     fhssEnabled    = false;      // off until link is proven on a fixed channel

//*********************************************************************
//  Radio self-test result
//*********************************************************************

struct RadioSelfTest {
    bool    ran           = false;
    bool    beginOk       = false;
    bool    chipConnected = false;
    bool    channelOk     = false;
    bool    dataRateOk    = false;
    uint8_t channelRead   = 0xFF;
    uint8_t dataRateRead  = 0xFF;
    const char* verdict   = "not run";
};
inline RadioSelfTest rfTest;

//*********************************************************************
//  FC telemetry (CRSF inbound)
//*********************************************************************

struct FcTelem {
    bool     valid          = false;
    float    fcBattVolts    = 0.0f;
    float    fcBattAmps     = 0.0f;
    uint32_t fcBattMah      = 0;
    uint8_t  fcBattPct      = 0;
    int8_t   fcUplinkRssi   = 0;
    uint8_t  fcUplinkLq     = 0;
    int8_t   fcUplinkSnr    = 0;
    int16_t  attitudePitch  = 0;        // mrad
    int16_t  attitudeRoll   = 0;
    int16_t  attitudeYaw    = 0;
    uint32_t fcMotorRPM     = 0;        // first value of the CRSF RPM frame (0x0C) — motor/rotor RPM from the FC
    float    fcEscTempC     = 0.0f;     // first value of the CRSF temperature frame (0x0D), deci-°C/10 — ESC temp
    char     flightMode[16] = {0};
    uint32_t framesParsed   = 0;
    uint32_t bytesIn        = 0;
    uint32_t crcErrors      = 0;
    uint32_t responsesSent  = 0;
    uint32_t lastFrameMs    = 0;
};
inline FcTelem fcTelem;

// Raw byte ring buffer — captures every byte received on D5 regardless of
// protocol. Lets us reverse-engineer FC traffic in modes where our parser is
// wrong or absent. Surfaced on /diagnostics as the "Recent raw" hex line.
constexpr size_t FC_RAW_RING_SIZE = 128;
inline uint8_t  fcRawRing[FC_RAW_RING_SIZE] = {0};
inline uint16_t fcRawHead   = 0;
inline uint16_t fcRawCount  = 0;
inline uint32_t fcRawTotal  = 0;

// Shared 128-byte byte-stream buffer used by all per-protocol parsers (one
// protocol is active at a time, so they don't collide).
inline uint8_t  fcRxBuf[128];
inline uint8_t  fcRxLen = 0;

// IBUS2 sensor protocol
struct IbusSlot {
    uint8_t type;       // FlySky sensor type code
    uint8_t dataLen;    // payload length in bytes (2 or 4)
};
constexpr IbusSlot IBUS_SLOTS[] = {
    { 0x03, 2 },   // slot 1: external voltage in 0.01 V units
    { 0x09, 2 },   // slot 2: RF link quality 0..100
};
constexpr uint8_t IBUS_NUM_SLOTS = sizeof(IBUS_SLOTS) / sizeof(IBUS_SLOTS[0]);
inline uint8_t ibusRxBuf[4];
inline uint8_t ibusRxIdx = 0;

//*********************************************************************
//  Event log (Black-box page)
//*********************************************************************
// ~2.5 KB in-RAM ring of textual events. Useful for "what happened in the last
// few seconds" debugging without serial.

struct EventLog {
    static constexpr size_t SIZE     = 128;
    static constexpr size_t MSG_LEN  = 80;
    char     msgs[SIZE][MSG_LEN] = {};
    uint32_t when[SIZE]          = {};
    size_t   head                = 0;
    size_t   count               = 0;

    void add(const char* msg) {
        when[head] = millis();
        strncpy(msgs[head], msg, MSG_LEN - 1);
        msgs[head][MSG_LEN - 1] = '\0';
        head = (head + 1) % SIZE;
        if (count < SIZE) count++;
    }
};
inline EventLog events;

//*********************************************************************
//  Web server, boot millis, build-days
//*********************************************************************

inline WebServer server(80);
inline uint32_t  bootMillis = 0;
inline uint32_t  buildDays  = 0;     // days since 2020-01-01, populated in setup()
inline bool      httpServerStarted = false;
inline volatile bool flyArmRequested = false;
inline bool      littleFsMounted = false;

//*********************************************************************
//  MSP bridge (TCP server on port 5760 → CRSF UART → FC)
//*********************************************************************
// When CRSF is the selected output protocol and a Rotorflight Configurator
// (or any MSP client) connects to port 5760, we become a transparent byte
// pipe: TCP bytes get written to Serial1 (D6 → FC), and bytes arriving on
// Serial1 from the FC (D5) get forwarded to the TCP client in addition to
// the local telemetry parser. RC frame transmission on D6 is suspended
// while a client is connected (you're configuring, not flying).
//
// Port 5760 is the Rotorflight / Betaflight standard for TCP-MSP.

constexpr uint16_t MSP_BRIDGE_PORT = 5760;

inline WiFiServer mspBridge(MSP_BRIDGE_PORT);
inline WiFiClient mspClient;
inline bool       mspBridgeStarted = false;     // server listening
inline bool       mspBridgeActive  = false;     // a client is connected RIGHT NOW
inline uint32_t   mspBridgeBytesIn  = 0;        // FC -> TCP (telemetry/MSP responses)
inline uint32_t   mspBridgeBytesOut = 0;        // TCP -> FC (MSP requests)
inline uint32_t   mspBridgeConnectMs = 0;       // when current client connected
inline uint32_t   mspBridgeConnections = 0;     // total connections since boot

//*********************************************************************
//  FC detection (MSP-over-CRSF probe)
//*********************************************************************

struct FcInfo {
    bool     detected         = false;
    bool     versionKnown     = false;
    char     variant[5]       = {0};     // e.g. "RTFL" / "BTFL" / "INAV"
    uint8_t  fwMajor          = 0;       // firmware semver (e.g. 2.3.0)
    uint8_t  fwMinor          = 0;
    uint8_t  fwPatch          = 0;
    uint8_t  mspProto         = 0;       // MSP protocol version
    uint8_t  apiMajor         = 0;       // MSP API version (separate from fw version)
    uint8_t  apiMinor         = 0;
    uint8_t  cells            = 0;       // battery cell count from MSP_BATTERY_STATE (0 = unknown)
    uint32_t probesSent       = 0;
    uint32_t lastProbeMs      = 0;
    uint32_t lastResponseMs   = 0;
};
inline FcInfo fcInfo;

//*********************************************************************
//  Cross-module forward declarations
//*********************************************************************
// Functions defined in one module header but called from another. Listed here
// so include-order between module headers doesn't matter.

void     loadNextAck();
void     decompress(uint16_t* out, const uint16_t* in, uint8_t outSize);
uint8_t  decompressedSize(uint8_t payloadBytes);
void     startApMode();
void     disableWifi();
void     saveBindToNvs();
void     clearBindNvs();
void     loadBindFromNvs();
String   getEffectiveSsid();
String   getEffectivePass();
bool     wifiCredsAreCustom();
const char* protocolName(Protocol p);
const char* protocolDesc(Protocol p);
const char* netModeName();
String   uptimeString();
void     mspBridgeStart();
void     mspBridgePoll();
void     mspBridgeOnFcByte(uint8_t b);
void     mspParseResponse(const uint8_t* body, uint8_t bodyLen);
void     mspFcPoll();
bool     fcIsRotorflightConfigCapable();
void     ledOn();
void     ledOff();

//*********************************************************************
//  Small helpers used everywhere
//*********************************************************************

// Pack a uint32 into bytes [1..4] of an ack-payload buffer, little-endian
// (matches v1's SendIntToAckPayload which uses a union { uint32_t; uint8_t[4]; }).
inline void packU32(uint8_t* ack, uint32_t v) {
    ack[1] = (uint8_t)(v       & 0xff);
    ack[2] = (uint8_t)((v >> 8)  & 0xff);
    ack[3] = (uint8_t)((v >> 16) & 0xff);
    ack[4] = (uint8_t)((v >> 24) & 0xff);
}
inline void packF32(uint8_t* ack, float f) {
    uint32_t v;
    memcpy(&v, &f, sizeof(v));
    packU32(ack, v);
}

#endif // _SRC_1DEFS_H
