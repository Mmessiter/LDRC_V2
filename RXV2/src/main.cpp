// LockDownRadioControl — Receiver V2  ::  main.cpp
//
// This is the single compilation unit for the RXV2 firmware. It includes the
// per-subsystem headers (1Defs.h must always come first so globals are
// declared), then defines setup() / loop().
//
// Module layout (mirrors v1's single-cpp + many-h pattern):
//   1Defs.h        — pin map, version, enums, structs, all globals
//   Storage.h      — NVS bind + WiFi-credential helpers
//   Channels.h     — 16-channel decompression + decode
//   Output.h       — SBUS/CRSF/IBUS/PPM/FBUS frame builders + drivers
//   Telemetry.h    — CRSF/FBUS/IBUS2 inbound parsers
//   Radio.h        — nRF24L01+ self-test, dual-radio, bind, ack rotation
//   Network.h      — STA/AP state machine, OTA, mDNS, heartbeat
//   WebPages.h     — HTTP handlers + page chrome
//
// Web pages serve their shared stylesheet from LittleFS at /style.css; an
// embedded fallback exists in WebPages.h in case the filesystem doesn't mount.
// Edit data/style.css and push with `pio run -e xiao_ota -t uploadfs`.
//
//*********************************************************************

#include "1Defs.h"
#include "Storage.h"
#include "Channels.h"
#include "Output.h"
#include "Telemetry.h"
#include "Radio.h"
#include "FlightLog.h"
#include "Network.h"
#include "MspBridge.h"
#include "MspFc.h"
#include "SimUsb.h"         // before WebPages.h — the firmware web pages call SimUSB::getMap/setMap
#include "BleConfig.h"      // before WebPages.h — WebPages routes through the BLE/WiFi router
#include "WebPages.h"

//*********************************************************************
//  D4 external status LED  (2-radio boards only)
//*********************************************************************
// A user LED on the D4 pad shows link state at a glance:
//   OFF       = bound but no link (receiver not hearing the transmitter)
//   ON        = bound + receiving  (connected, ready to fly)
//   2 Hz flash= binding (unbound, listening for a transmitter)
// D4 is Radio3's CE on the triple-radio PCB, so we only take the pad over when
// radio 3 is ABSENT (auto-detected) — triple-radio boards are left untouched.
static bool statusLedEnabled = false;

static inline void statusLedWrite(bool on) {
    digitalWrite(PIN_STATUS_LED, (on == STATUS_LED_ACTIVE_HIGH) ? HIGH : LOW);
}

static void statusLedBegin() {                     // call after detectAllRadios()
    statusLedEnabled = !radioPresent[2];           // D4 is free only when radio 3 is gone
    if (statusLedEnabled) { pinMode(PIN_STATUS_LED, OUTPUT); statusLedWrite(false); }
}

static void statusLedTick() {                      // call every loop()
    if (!statusLedEnabled) return;
    static uint32_t nextEdge = 0;
    static bool     flashOn  = false;
    const uint32_t now = millis();
    if (!bindState.bound) {                        // binding — 2 Hz square wave
        if ((int32_t)(now - nextEdge) >= 0) {
            flashOn = !flashOn;
            statusLedWrite(flashOn);
            nextEdge = now + 250;                  // 250 ms half-period = 2 Hz
        }
        return;
    }
    nextEdge = 0; flashOn = false;                 // reset flash phase for the next unbind
    const bool linkAlive = rx.lastMillis && (uint32_t)(now - rx.lastMillis) < 500;
    statusLedWrite(linkAlive);                     // ON = connected, OFF = disconnected
}

//*********************************************************************
//  setup() — one-time boot sequence
//*********************************************************************

void setup() {
    pinMode(LED_PIN, OUTPUT);
    ledOff();

    Serial.begin(115200);
    // Make USB-CDC writes non-blocking when no host is attached — otherwise
    // every printf can stall up to 20 s waiting for a reader, which delays
    // the entire boot sequence (radio self-test, WiFi, AP fallback all push back).
    // Only the USB-CDC `Serial` has setTxTimeoutMs(); under TinyUSB builds
    // (ARDUINO_USB_CDC_ON_BOOT=0, the S3 sim-capable envs) `Serial` is UART0,
    // which has no such method — and a hardware UART never blocks on a reader.
#if ARDUINO_USB_CDC_ON_BOOT
    Serial.setTxTimeoutMs(0);
#endif
    delay(200);
    Serial.printf("\n\n=== %s ===\n", FW_VERSION);
    bootMillis = millis();

    buildDays = computeBuildDays();
    Serial.printf("[id] build %s -> %u days since 2020-01-01\n", __DATE__, (unsigned)buildDays);

    // Pre-link channel defaults — what we output BEFORE a transmitter has ever
    // connected (e.g. the receiver powered up on the bench with the TX off).
    // NOT all-1500: to an FC that reads as a centred, *armed* link (AUX/arm
    // switches sitting at mid), so a heli FC tries to stabilise and the
    // swashplate dances unhappily. Instead boot into a SAFE / disarmed posture:
    //   ch1-5 (idx 0-4) = 1500  → cyclic/yaw centred, throttle/collective mid
    //   ch6-16 (idx 5-15) = 500 → all AUX low, so any arm/mode switch reads OFF
    // Being disarmed, nothing spins regardless of the throttle channel. Once a
    // TX connects these are overwritten by real values; on signal loss AFTER a
    // link the channels HOLD their last value instead (see Channels.h/Output.h).
    for (uint8_t i = 0; i < 16; ++i) channelMicros[i] = (i < 5) ? 1500 : 500;
    // SAFETY: never boot with the throttle at mid-stick. Until the TX is
    // heard, the throttle channel is pinned low (Output.h keeps it there).
    throttleChannel = prefs.isKey(NVS_KEY_THR_CH) ? prefs.getUChar(NVS_KEY_THR_CH, 3) : 3;
    if (throttleChannel > 16) throttleChannel = 3;
    if (throttleChannel >= 1)
        channelMicros[throttleChannel - 1] = THROTTLE_SAFE_US;

    // Log WHY we booted — the blackbox story starts here. Distinguishes a
    // normal power-up from the silent self-reboots that matter: BROWNOUT
    // (supply sagged — suspect the BEC/wiring), PANIC/WDT (firmware crash),
    // SW (deliberate ESP.restart). Diagnosing the 2026-07-02 "receiver fell
    // off WiFi when the TX came on" incident needed exactly this line.
    {
        esp_reset_reason_t rr = esp_reset_reason();
        const char* rs = rr == ESP_RST_POWERON  ? "power-on"
                       : rr == ESP_RST_SW       ? "software restart"
                       : rr == ESP_RST_PANIC    ? "CRASH (panic)"
                       : rr == ESP_RST_INT_WDT  ? "CRASH (int watchdog)"
                       : rr == ESP_RST_TASK_WDT ? "CRASH (task watchdog)"
                       : rr == ESP_RST_WDT      ? "CRASH (other watchdog)"
                       : rr == ESP_RST_BROWNOUT ? "BROWNOUT (supply sagged!)"
                       : rr == ESP_RST_DEEPSLEEP? "deep-sleep wake"
                       : "other";
        char b[64];
        snprintf(b, sizeof(b), "Boot (%s)", rs);
        events.add(b);
        Serial.printf("[boot] reset reason: %s (%d)\n", rs, (int)rr);
    }

    prefs.begin(NVS_NAMESPACE, false);

    // Boot ALWAYS comes up on the guaranteed-disarmed generic default above
    // (ch1-5=1500, AUX low) — NEVER the captured failsafe values, which may have
    // the arm/safety switch in the OFF (armed) position and would make the FC
    // unhappy / unsafe at power-up. The captured failsafe is for in-flight signal
    // loss only (loaded here so it's available if/when we wire that path).
    loadFailsafeFromNvs();

    // Head-speed gear ratio (motor:head). 1.0 = direct drive.
    gearRatio = prefs.getFloat(NVS_KEY_GEAR_RATIO, 1.0f);
    vbatPin      = prefs.isKey(NVS_KEY_VBAT_PIN)   ? prefs.getUChar(NVS_KEY_VBAT_PIN, 0)      : 0;
    vbatRatio    = prefs.isKey(NVS_KEY_VBAT_RATIO) ? prefs.getFloat(NVS_KEY_VBAT_RATIO, 23.0f) : 23.0f;
    vbatCellsCfg = prefs.isKey(NVS_KEY_VBAT_CELLS) ? prefs.getUChar(NVS_KEY_VBAT_CELLS, 0)    : 0;
    if (vbatPin != 0 && vbatPin != 9) vbatPin = 0;   // D9 only — the sole free pad (D4 is the status LED)
    vbatInit();
    armingChannel = prefs.isKey(NVS_KEY_ARM_CH) ? prefs.getUChar(NVS_KEY_ARM_CH, 0) : 0;
    autoFlyEnabled = prefs.isKey(NVS_KEY_AUTOFLY) ? (prefs.getUChar(NVS_KEY_AUTOFLY, 1) != 0) : true;
    gapMinMs = prefs.isKey(NVS_KEY_GAP_MIN) ? prefs.getUChar(NVS_KEY_GAP_MIN, 5) : 5;
    tzOffsetMin = prefs.isKey(NVS_KEY_TZ_MIN) ? prefs.getShort(NVS_KEY_TZ_MIN, 0) : 0;
    tuneEditGen      = prefs.isKey(NVS_KEY_EDIT_GEN) ? prefs.getUShort(NVS_KEY_EDIT_GEN, 0) : 0;
    tuneFlightsSince = prefs.isKey(NVS_KEY_FLT_SINCE_EDIT) ? prefs.getULong(NVS_KEY_FLT_SINCE_EDIT, 0) : 0;
    txClockOffKnown = prefs.isKey(NVS_KEY_TX_OFF_S);
    txClockOffS     = txClockOffKnown ? prefs.getInt(NVS_KEY_TX_OFF_S, 0) : 0;
    if (armingChannel > 16) armingChannel = 0;
    waveChannelMask = prefs.isKey(NVS_KEY_WAVE_CHS) ? prefs.getUShort(NVS_KEY_WAVE_CHS, 1) : 1;
    apAutoEnabled = prefs.isKey(NVS_KEY_AP_AUTO) && prefs.getBool(NVS_KEY_AP_AUTO, false);
    if (gearRatio < 0.1f || gearRatio > 100.0f) gearRatio = 1.0f;

    //*****************************************************************
    // NVS state report — surfaces silent data loss the moment it
    // happens. WiFi creds, bind state and proto should all survive
    // OTA/uploadfs; if any of them show "(none)" right after an
    // update, the OTA disturbed NVS rather than just the firmware/FS
    // partitions and the user shouldn't have to guess why the chip
    // is in AP mode.
    //*****************************************************************
    {
        String ssid     = prefs.isKey(NVS_KEY_SSID) ? prefs.getString(NVS_KEY_SSID, "") : "";
        bool   haveSsid = ssid.length() > 0;
        bool   havePass = prefs.isKey(NVS_KEY_PASS) && prefs.getString(NVS_KEY_PASS, "").length() > 0;
        size_t pipeLen  = prefs.isKey(NVS_KEY_PIPE) ? prefs.getBytesLength(NVS_KEY_PIPE) : 0;
        bool   haveProto = prefs.isKey(NVS_KEY_PROTO);
        Serial.printf("[nvs] ssid=%s pass=%s bind_pipe=%s proto=%s\n",
                      haveSsid   ? ssid.c_str() : "(none)",
                      havePass   ? "set" : "(none)",
                      pipeLen == 5 ? "stored" : "(none)",
                      haveProto  ? "set" : "(default)");
        // Also push the same summary to the in-RAM event log so it shows
        // up on /blackbox without needing a USB serial cable. Users can
        // confirm at a glance whether WiFi creds and bind state survived
        // a reboot instead of guessing from the chip's mode.
        char buf[80];
        snprintf(buf, sizeof(buf), "NVS: ssid=%s pass=%s bind=%s",
                 haveSsid  ? ssid.c_str() : "NONE",
                 havePass  ? "yes" : "NO",
                 pipeLen == 5 ? "yes" : "NO");
        events.add(buf);
        if (!haveSsid) {
            events.add("Boot: no WiFi SSID in NVS — AP mode");
        }
    }

    //*****************************************************************
    // Mount LittleFS so web pages can serve assets from /data
    //*****************************************************************
    if (LittleFS.begin(true)) {     // formatOnFail=true — wipes & formats if corrupt
        littleFsMounted = true;
        Serial.printf("[fs] LittleFS mounted, %u/%u bytes used\n",
                      (unsigned)LittleFS.usedBytes(), (unsigned)LittleFS.totalBytes());
        // Flight-ring head (2026-08-01). First boot on ring firmware migrates
        // the legacy rotation layout (flt0=newest, fltN older) into ring
        // positions for head=0 (older flights live at 19,18,...). Boot-time
        // renames are harmless — no link exists yet.
        // Previous boot's persisted event tail becomes /evprev.txt.
        if (LittleFS.exists("/evcur.txt")) {
            LittleFS.remove("/evprev.txt");
            LittleFS.rename("/evcur.txt", "/evprev.txt");
        }
        if (prefs.isKey(NVS_KEY_FLT_HEAD)) {
            fltHead = prefs.getUChar(NVS_KEY_FLT_HEAD, 0) % FLIGHT_KEEP;
        } else {
            for (uint8_t i = 1; i < FLIGHT_KEEP; ++i) {
                char mig[16]; snprintf(mig, sizeof(mig), "/mig%u.bin", i);
                if (LittleFS.exists(flightPath(i))) LittleFS.rename(flightPath(i), mig);
            }
            for (uint8_t i = 1; i < FLIGHT_KEEP; ++i) {
                char mig[16]; snprintf(mig, sizeof(mig), "/mig%u.bin", i);
                if (LittleFS.exists(mig))
                    LittleFS.rename(mig, flightPath((uint8_t)(FLIGHT_KEEP - i)));
            }
            fltHead = 0;
            prefs.putUChar(NVS_KEY_FLT_HEAD, fltHead);
            Serial.println("[fs] flight slots migrated to ring layout");
        }
    } else {
        littleFsMounted = false;
        Serial.println("[fs] LittleFS mount failed — using embedded fallback assets");
        events.add("LittleFS mount failed");
    }

    //*****************************************************************
    // Config-reboot fast path — one-shot flag set by the web UI when it
    // reboots to apply a setting (protocol, sim, WiFi, name…). The user is
    // at the phone in config mode, NOT flying, so come straight back to WiFi:
    // skip the 1 s RF window and never drop to fly-mode on a stray packet.
    // This is the "reboot takes forever to come back" fix.
    // MUST be consumed BEFORE the quick-boot counter below: a deliberate web
    // reboot is proof the firmware ran fine, so it must not count towards the
    // crash-loop threshold (three fast "save & reboot" taps used to trip
    // recovery and silently overwrite the user's protocol with SBUS).
    //*****************************************************************
    bool cfgReboot = prefs.isKey(NVS_KEY_CFG_REBOOT) && prefs.getUChar(NVS_KEY_CFG_REBOOT, 0);
    if (cfgReboot) {
        prefs.putUChar(NVS_KEY_CFG_REBOOT, 0);   // consume the one-shot
        forceWifiMode = true;
        Serial.println("[boot] config reboot — bringing WiFi up immediately (no RF window)");
    }

    //*****************************************************************
    // Quick-boot escape hatch — three quick reboots forces WiFi + SBUS
    //*****************************************************************
    // Recovers cleanly from a protocol selection that's crashing the chip in
    // a reboot loop.
    bool protoSafeBoot = false;
    if (!cfgReboot) {
        uint8_t cnt = prefs.isKey(NVS_KEY_BOOT_COUNT) ? prefs.getUChar(NVS_KEY_BOOT_COUNT, 0) : 0;
        cnt++;
        prefs.putUChar(NVS_KEY_BOOT_COUNT, cnt);
        if (cnt >= QUICK_BOOT_THRESHOLD) {
            forceWifiMode = true;
            prefs.putUChar(NVS_KEY_BOOT_COUNT, 0);
            // RAM-ONLY safe protocol for THIS boot — never rewrite the user's
            // saved choice (Malcolm 2026-08-05: bench battery-pulls added up
            // to a silent CRSF→SBUS flip on Black-Thunder-2). If a protocol
            // driver truly crash-loops, every boot re-trips this and stays
            // usable; a false alarm costs one odd boot, not a setting.
            protoSafeBoot = true;
            Serial.printf("[boot] %u quick boots — WiFi forced, CRSF this boot (saved protocol kept)\n", cnt);
            events.add("Recovery: WiFi forced, CRSF this boot (saved protocol kept)");
        } else {
            Serial.printf("[boot] quick-boot counter: %u/%u\n", cnt, QUICK_BOOT_THRESHOLD);
        }
    }

    //*****************************************************************
    // Load saved output protocol (fresh NVS defaults to CRSF)
    //*****************************************************************
    {
        uint8_t p = prefs.isKey(NVS_KEY_PROTO) ? prefs.getUChar(NVS_KEY_PROTO, PROTO_DEFAULT) : PROTO_DEFAULT;
        if (p > PROTO_MAX) p = PROTO_DEFAULT;
        // Recovery boot: RAM-only fall-back to the DEFAULT protocol — CRSF,
        // the fleet's language (Malcolm 2026-08-05: "the ultimate default
        // should be CRSF"). WiFi being forced up is the actual rescue.
        if (protoSafeBoot) p = PROTO_DEFAULT;
        currentProtocol = (Protocol)p;
        ppmInverted = prefs.isKey(NVS_KEY_PPM_INV) ? (prefs.getUChar(NVS_KEY_PPM_INV, 0) != 0) : false;
        uint8_t chz = prefs.isKey(NVS_KEY_CRSF_HZ) ? prefs.getUChar(NVS_KEY_CRSF_HZ, 250) : 250;
        crsfRateHz = (chz == 50 || chz == 100) ? chz : 250;
        fcTelemetryEnabled = !prefs.isKey(NVS_KEY_FC_TELEM) || prefs.getUChar(NVS_KEY_FC_TELEM, 1) != 0;
        if (!fcTelemetryEnabled)
            Serial.printf("[out] FC telemetry DISABLED — ignoring telemetry-line input, no Rotorflight probes\n");
        if (currentProtocol == PROTO_CRSF)
            Serial.printf("[out] CRSF frame rate = %u Hz\n", crsfRateHz);
        Serial.printf("[out] protocol = %s — %s  (PPM polarity: %s)\n",
                      protocolName(currentProtocol), protocolDesc(currentProtocol),
                      ppmInverted ? "negative (idle HIGH)" : "positive (idle LOW)");
    }
    // Sim mode (driving a PC simulator over USB) must NOT also drive a real
    // flight controller — so when it's on we skip output-driver setup entirely:
    // nothing is ever configured or sent on the D6 output pin. Read the flag
    // here, before any output init, so the decision is made once.
    simEnabled = prefs.isKey(NVS_KEY_SIM) ? (prefs.getUChar(NVS_KEY_SIM, 0) != 0) : false;
    simSpoolEnabled  = prefs.isKey(NVS_KEY_SIM_SPOOL)   ? (prefs.getUChar(NVS_KEY_SIM_SPOOL, 0) != 0) : false;
    simSpoolSeconds  = prefs.isKey(NVS_KEY_SIM_SPOOL_S) ? prefs.getUChar(NVS_KEY_SIM_SPOOL_S, 8) : 8;
    simTorqueUs      = prefs.isKey(NVS_KEY_SIM_TORQUE)  ? prefs.getShort(NVS_KEY_SIM_TORQUE, -120) : -120;
    simRudderChannel = prefs.isKey(NVS_KEY_SIM_RUD_CH)  ? prefs.getUChar(NVS_KEY_SIM_RUD_CH, 4) : 4;
    simMotorChannel  = prefs.isKey(NVS_KEY_SIM_MOT_CH)  ? prefs.getUChar(NVS_KEY_SIM_MOT_CH, 0) : 0;
    simMotorInverted = prefs.isKey(NVS_KEY_SIM_MOT_INV) ? (prefs.getUChar(NVS_KEY_SIM_MOT_INV, 0) != 0) : false;
    simSpoolPulse    = prefs.isKey(NVS_KEY_SIM_PULSE)   ? (prefs.getUChar(NVS_KEY_SIM_PULSE, 0) != 0) : false;
    simSpoolPulseMs  = prefs.isKey(NVS_KEY_SIM_PULSEMS) ? prefs.getUShort(NVS_KEY_SIM_PULSEMS, 250) : 250;
    if (simSpoolPulseMs < 50)   simSpoolPulseMs = 50;
    if (simSpoolPulseMs > 1000) simSpoolPulseMs = 1000;
    if (simSpoolSeconds < 1) simSpoolSeconds = 1;
    if (simSpoolSeconds > 60) simSpoolSeconds = 60;
    if (simEnabled) {
        Serial.println("[sim] simulator mode — flight-controller output DISABLED (D6 stays silent)");
        events.add("Sim mode: FC output disabled");
    } else {
        configureOutputDriver(currentProtocol);
    }

    //*****************************************************************
    // Bind state — restore from NVS if previously bound
    //*****************************************************************
    loadBindFromNvs();
    if (bindState.bound) {
        char buf[80];
        snprintf(buf, sizeof(buf), "Restored bind %02X %02X %02X %02X %02X from NVS",
                 bindState.pipe[0], bindState.pipe[1], bindState.pipe[2], bindState.pipe[3], bindState.pipe[4]);
        events.add(buf);
    }

    //*****************************************************************
    // Board ID — captured once on first boot, persisted forever
    //*****************************************************************
    // Guarantees the MAC bytes we report to the TX during bind never change
    // between reboots, so the transmitter's auto-model-select can be left ON.
    if (prefs.isKey(NVS_KEY_BOARD_ID) && prefs.getBytesLength(NVS_KEY_BOARD_ID) == 6) {
        prefs.getBytes(NVS_KEY_BOARD_ID, boardMac, 6);
        Serial.println("[id] board MAC loaded from NVS (stable across reboots)");
    } else {
        esp_read_mac(boardMac, ESP_MAC_WIFI_STA);
        prefs.putBytes(NVS_KEY_BOARD_ID, boardMac, 6);
        Serial.println("[id] board MAC captured from chip and saved to NVS");
    }
    Serial.printf("[id] board MAC %02X:%02X:%02X:%02X:%02X:%02X\n",
                  boardMac[0], boardMac[1], boardMac[2],
                  boardMac[3], boardMac[4], boardMac[5]);

    //*****************************************************************
    // Model name → AP SSID, mDNS hostname, page titles
    //*****************************************************************
    // Defaults to "RXV2-XXXX" using last-4-hex of the board MAC so
    // every receiver out of the box has a unique, non-colliding name.
    // The user can override via the front page; their friendly name
    // then drives both the WiFi visibility (AP SSID + hostname) and
    // the page titles right across the web UI.
    g_effectiveName = effectiveName();
    g_hostname      = hostnameFromName(g_effectiveName);
    Serial.printf("[id] model name = '%s'  hostname = '%s.local'\n",
                  g_effectiveName.c_str(), g_hostname.c_str());

    //*****************************************************************
    // "Drive simulator over USB" — bring up the USB HID joystick fed from the
    // channels we receive (S3/TinyUSB builds only; a no-op on the C3). simEnabled
    // was read above (where it also gated the FC output). Sim mode PERSISTS across
    // reboots — it's a deliberate choice toggled from the home page, not reset by
    // a power-cycle. Uses the per-unit model name as the USB serial so the sim
    // keeps its calibration.
    //*****************************************************************
    if (simEnabled) {
        SimUSB::begin(g_effectiveName.c_str());
        // Apply any saved channel remap (from the /map page); the default stands otherwise.
        uint8_t sm[8]; bool sr[8] = { false };
        if (prefs.isKey(NVS_KEY_SIM_MAP) && prefs.getBytes(NVS_KEY_SIM_MAP, sm, 8) == 8) {
            uint8_t rb[8] = { 0 };
            bool haveR = prefs.isKey(NVS_KEY_SIM_REV) && prefs.getBytes(NVS_KEY_SIM_REV, rb, 8) == 8;
            for (uint8_t i = 0; i < 8; i++) sr[i] = haveR ? (rb[i] != 0) : false;
            SimUSB::setMap(sm, sr);
        }
        Serial.println("[sim] USB joystick ON — driving the simulator from received channels");
        events.add("Sim-over-USB: joystick active");
    }

    //*****************************************************************
    // Radio bring-up
    //*****************************************************************
    runRadioSelfTest();
    detectAllRadios();       // probes slots 1/2/3 independently; sets radioPresent[]
    radioBeginListenV1();
    statusLedBegin();        // D4 status LED — only if radio 3 is absent

    //*****************************************************************
    // Register HTTP routes (server.begin() is deferred to onWifiConnected()
    // or startApMode() — calling it before WiFi is up panics LwIP).
    //*****************************************************************
    registerWebRoutes();

    //*****************************************************************
    // BLE stack up-front (silent — no advertising until WiFi config
    // mode). Igniting the BT controller later, while WiFi is mid-
    // connect, aborts in the IDF coexistence layer (0.9.207 bootloop).
    //*****************************************************************
    bleInitOnce();
    // ...and START ADVERTISING now, before any TX link exists. The BT
    // radio's first keying (one-shot calibration burst) deafens the
    // nRF24s for ~1 s — done lazily at "TX heard" it landed mid-session
    // and was every blackbox's mystery 1 s longest gap (convicted by the
    // gap breadcrumbs, 2026-07-23). Paid here it happens before the
    // first packet. The boot-window/fly rules are unchanged: netStep
    // still closes this window 30 s after a TX is heard (bleStop, or
    // fly-quiet for a connected client), and later bleStart() calls are
    // no-ops while already advertising.
    bleStart();

    //*****************************************************************
    // Net state machine — RF discovery window unless forced to WiFi
    //*****************************************************************
    if (forceWifiMode) {
        Serial.println("[net] force-WiFi requested, skipping RF window");
        startWifiStation();
    } else if (DEV_KEEP_WIFI || simEnabled) {
        // Keep WiFi on (skip the RF-detect window) for development (DEV_KEEP_WIFI)
        // OR whenever we're driving a simulator — sim sessions want the web UI
        // reachable the whole time, and the ~5% frame-rate cost of WiFi coexistence
        // doesn't matter on the bench. Real flight (not sim) falls through to the
        // RF window below, so it gets WiFi-off / 501 Hz automatically.
        Serial.printf("[net] %s — skipping RF window, WiFi on\n",
                      simEnabled ? "sim mode" : "DEV_KEEP_WIFI");
        events.add(simEnabled ? "Sim mode: WiFi kept on" : "DEV mode: WiFi forced on");
        startWifiStation();
    } else if (numRadiosPresent == 0) {
        // No radios at all (bare chip / dev board / unpopulated PCB): it can
        // never hear a real TX, so never sit in the RF window waiting — bring
        // WiFi up immediately so the board is always reachable for config/OTA.
        Serial.println("[net] no radios present — WiFi on immediately");
        events.add("No radios — WiFi on");
        startWifiStation();
    } else {
        netMode       = NET_WAITING_RF;
        netStateStart = millis();
        Serial.printf("[net] waiting up to %u ms for TX before bringing up WiFi\n",
                      (unsigned)RF_WINDOW_MS);
        events.add("Boot window: listening for TX...");
    }
}

//*********************************************************************
//  loop() — main service loop
//*********************************************************************

//*********************************************************************
//  Low-battery guardian (Malcolm 2026-07-28, after the supper-and-a-film
//  pack fatality: the buck-boost kept the RX alive while the LiPo sank
//  beyond rescue). Two stages, crash-safety first:
//    <= 3.50 V/cell : the app shows a MASSIVE warning (page-side, from
//                     the vbat figures already in state.json).
//    <= 3.30 V/cell : IF the model is provably forgotten — channels
//                     dead-still for 2 minutes, not being flown, not
//                     armed — save the flight and DEEP SLEEP. A flying
//                     model always moves its channels, so sleep can
//                     never fire mid-air; wake = power-cycle.
//*********************************************************************
constexpr float    BATT_SLEEP_PER_CELL = 3.30f;
constexpr uint32_t BATT_STILL_MS       = 120000;   // channels still this long = forgotten
constexpr uint16_t BATT_MOVE_US        = 12;       // movement threshold per channel

static void batteryGuardTick() {
    static uint16_t snap[16] = {0};
    static uint32_t belowSinceMs = 0;
    const uint32_t now = millis();

    bool moved = false;
    for (uint8_t i = 0; i < 16; ++i) {
        uint16_t v = channelMicros[i];
        if ((v > snap[i] ? v - snap[i] : snap[i] - v) > BATT_MOVE_US) { moved = true; snap[i] = v; }
    }
    if (moved || !lastChMoveMs) lastChMoveMs = now;   // shared: battery guardian + quiet-moment flight save

    if (vbatVolts < 3.0f) { belowSinceMs = 0; return; }   // no/implausible sensor
    uint8_t cells = vbatCellsCfg ? vbatCellsCfg
                                 : (uint8_t)constrain((int)((vbatVolts + 1.9f) / 3.8f), 1, 6);
    float perCell = vbatVolts / cells;

    // The armed check reuses the flight-save definition of armed.
    bool armed = (armingChannel >= 1 && armingChannel <= 16) &&
                 (channelMicros[armingChannel - 1] > 1500);
    bool still = (uint32_t)(now - lastChMoveMs) >= BATT_STILL_MS;

    if (perCell <= BATT_SLEEP_PER_CELL && still && !beingFlown && !armed) {
        if (!belowSinceMs) belowSinceMs = now;
        if ((uint32_t)(now - belowSinceMs) >= 10000) {     // sustained, not a sag blip
            events.add("Battery guardian: deep sleep to save the pack");
            saveFlightToLittleFS();                        // keep the record (no-op if trivial)
            delay(50);
            esp_deep_sleep_start();                        // wake = power-cycle
        }
    } else belowSinceMs = 0;
}

void loop() {
    // Diagnostic: loop frequency + worst-case iteration time, so we can tell a CPU /
    // servicing stall (low Hz, or a big max) from an RF problem (high Hz, frames just
    // not arriving). Folded into g_loopHz / g_loopMaxUs once a second.
    {
        static uint32_t loopCount = 0, lastRateMs = 0, lastLoopUs = 0, maxUs = 0;
        uint32_t nowUs = micros();
        if (lastLoopUs) {
            uint32_t dt = nowUs - lastLoopUs;
            if (dt > maxUs) maxUs = dt;
            // DIAG (0.9.145): a single loop iteration >50ms means the loop was
            // blocked (e.g. WiFi reconnect) — long enough to pause CRSF/SBUS
            // output and make the FC see RX-loss (the flash). Logged with the
            // duration so we can line it up against "WiFi dropped" etc.
            if (dt > 50000) {
                char b[48];
                snprintf(b, sizeof(b), "DIAG LOOP-STALL %lums", (unsigned long)(dt / 1000));
                events.add(b);
            }
        }
        lastLoopUs = nowUs;
        loopCount++;
        if ((uint32_t)(millis() - lastRateMs) >= 1000) {
            g_loopHz = loopCount; g_loopMaxUs = maxUs;
            loopCount = 0; maxUs = 0; lastRateMs = millis();
        }
    }

    if (otaStarted) ArduinoOTA.handle();
    // Server runs whenever the HTTP listener is bound, regardless of
    // STA state. From v0.9.51 the chip runs AP+STA in parallel, so
    // the web UI is reachable via the soft-AP even while STA is still
    // (re)connecting to home WiFi.
    if (httpServerStarted) {
        server.handleClient();
    }
    blePoll();   // execute + stream any pending BLE config request (same task as HTTP)

    radioPoll();
    if (simEnabled) {
        // Sim mode: the ONLY output is the USB composite device. Skip ALL flight-
        // controller work — no RC output frames, no telemetry, no MSP — so a real
        // model can't be flown from sim mode, and the loop stays lean.
        //
        // Failsafe posture must be applied HERE: sbusTick() — the only other
        // place the captured positions are driven — never runs in sim mode, so
        // the sim previously froze at the last stick values when the TX went
        // off (which looked exactly like "failsafe never saved"). Same
        // link-age rule as sbusTick, same everConnected gate (a no-TX boot
        // keeps the disarmed-safe defaults, never the captured posture).
        {
            static bool simFsPosture = false;
            uint32_t linkRef = (bindState.bound && rx.lastMillis) ? rx.lastMillis
                                                                  : lastChannelDataMs;
            bool lost = (lastChannelDataMs != 0) &&
                        (uint32_t)(millis() - linkRef) > OUTPUT_FAILSAFE_MS;
            if (lost && failsafeSet) {
                for (uint8_t i = 0; i < 16; ++i) channelMicros[i] = failsafeMicros[i];
                if (!simFsPosture) { simFsPosture = true;
                    events.add("Signal lost — sim driven to failsafe positions"); }
            } else if (simFsPosture && !lost) {
                simFsPosture = false;
                events.add("Link restored — sim left failsafe posture");
            }
        }
        // Spool-up realism (Malcolm 2026-08-17, for neXt autorotation
        // practice — "Klaus would be impressed"): leaving the throttle-hold
        // bank must not snap the sim to full head speed with infinite
        // acceleration and no torque. Throttle RISES are rate-limited like
        // a real governor; drops stay instant (entering the auto is
        // unchanged). While the head is accelerating, the rudder gets a
        // torque stab (signed, so it works for either rotor direction),
        // fading out over the last stretch of the spool as the governor
        // "catches up". All of it lives on a private copy — the real
        // channel data is untouched.
        static uint16_t simTx[16];
        for (uint8_t i = 0; i < 16; ++i) simTx[i] = channelMicros[i];
        if (simSpoolEnabled && simMotorChannel >= 1 && simMotorChannel <= 16) {
            static float    spoolThr    = -1.0f;    // -1 = take first commanded value
            static uint32_t lastSpoolMs = 0;
            static uint32_t cutStartMs  = 0;        // when the power was chopped (0 = not cut)
            static float    spoolRateUs = 0.0f;     // µs/s chosen when THIS spool began
            uint32_t nowMs = millis();
            float dt = lastSpoolMs ? (uint32_t)(nowMs - lastSpoolMs) / 1000.0f : 0.0f;
            if (dt > 0.25f) dt = 0.25f;             // clamp across stalls/boot
            lastSpoolMs = nowMs;
            // Work in POWER space: on an inverted channel (high µs = motor
            // OFF, Malcolm's ch6) leaving the hold is a FALL — mirroring via
            // (3000 - µs) makes "more power" always an increase here.
            float raw = (float)simTx[simMotorChannel - 1];
            float cmd = simMotorInverted ? (3000.0f - raw) : raw;
            if (spoolThr < 0.0f) spoolThr = cmd;
            bool ramping = false;
            // LDRC channels span 500-2500 µs (not 1000-2000): "seconds" means
            // the FULL 2000 µs swing, and the rudder clamp matches the range.
            if (cmd <= spoolThr) {
                if (cmd < spoolThr && !cutStartMs) cutStartMs = nowMs;   // chop begins
                spoolThr = cmd;                     // power cut = instant (throttle hold)
                spoolRateUs = 0.0f;                 // next rise picks its speed fresh
            } else {
                // The USB gamepad axis SATURATES outside 1500±512 µs
                // (usToAxis) — only 988..2012 is visible to the sim. Ramping
                // through the pegged zones produced Malcolm's "pause before
                // it starts to move" (2026-08-18): ~3 s of invisible ramping
                // from 2500 before the axis stirred. So the ramp JUMPS the
                // invisible zones instantly and spends the whole configured
                // time inside the window the sim can actually see. (The
                // window is symmetric about 1500, so it is the same span in
                // power space whichever way the channel is inverted.)
                const float WIN_LO = 988.0f, WIN_HI = 2012.0f;
                // Two-speed governor (Malcolm 2026-08-18): a BRIEF cut — the
                // mid-air autorotation bail-out — recovers on the fast rate
                // (real governors have a bail-out mode); a LONG cut (landed,
                // sat in the hold) restarts on the slow ground spool. The
                // choice is made ONCE, when the rise begins, from how long
                // the power had been off; simSpoolSeconds is the GROUND
                // time, the bail-out recovery runs 4× quicker.
                if (spoolRateUs <= 0.0f) {
                    uint32_t offMs = cutStartMs ? (nowMs - cutStartMs) : 0;
                    bool bailout = cutStartMs && offMs < 8000;   // <8 s off = mid-air
                    float secs = bailout ? (simSpoolSeconds / 4.0f) : (float)simSpoolSeconds;
                    if (secs < 0.5f) secs = 0.5f;
                    spoolRateUs = (WIN_HI - WIN_LO) / secs;      // whole time = VISIBLE sweep
                    cutStartMs = 0;
                }
                if (spoolThr < WIN_LO) spoolThr = WIN_LO;        // skip the pegged bottom
                float target = (cmd < WIN_HI) ? cmd : WIN_HI;
                float step = spoolRateUs * dt;                   // µs this tick
                if (spoolThr + step >= target) {
                    spoolThr = cmd;                              // snap the pegged top too
                } else { spoolThr += step; ramping = true; }
            }
            float sendThr = spoolThr;
            if (simSpoolPulse && ramping) {
                // Malcolm's manual PWM: while spooling, the channel is
                // either FULL ON (the pilot's command) or FULL OFF, with
                // the ON share of each period equal to the ramp's progress
                // through the visible window. neXt's threshold sees clean
                // on/off; its rotor inertia averages the rest into a climb.
                const float WIN_LO = 988.0f, WIN_HI = 2012.0f;
                float p = (spoolThr - WIN_LO) / (WIN_HI - WIN_LO);
                if (p < 0.0f) p = 0.0f;
                if (p > 1.0f) p = 1.0f;
                uint32_t period = simSpoolPulseMs;
                uint32_t phase  = nowMs % period;
                sendThr = (phase < (uint32_t)(p * period)) ? cmd : 500.0f;
            }
            float outUs = simMotorInverted ? (3000.0f - sendThr) : sendThr;
            simTx[simMotorChannel - 1] = (uint16_t)(outUs + 0.5f);
            if (ramping && simTorqueUs != 0 &&
                simRudderChannel >= 1 && simRudderChannel <= 16 &&
                simRudderChannel != simMotorChannel) {
                // Malcolm's physics (2026-08-17 bedtime note): the kick is
                // LARGEST at the start — the main blades' mass is accelerating
                // while the tail rotor is still too slow to fight back — and
                // dies away tangentially as the head approaches its stable
                // speed and tail authority grows with rpm². Quadratic in the
                // remaining spool: full stab at the bottom, flattening
                // asymptotically to zero at the top.
                float deficit = cmd - spoolThr;                   // µs still to spool
                float prog = deficit / 1024.0f;                   // vs the VISIBLE sweep
                if (prog > 1.0f) prog = 1.0f;
                float k = prog * prog;
                int32_t r = (int32_t)simTx[simRudderChannel - 1]
                          + (int32_t)((float)simTorqueUs * k);
                if (r < 500)  r = 500;
                if (r > 2500) r = 2500;
                simTx[simRudderChannel - 1] = (uint16_t)r;
            }
            // Live window for diagnosis (spool.json "live"): what the ramp
            // sees and what it is sending, updated every loop.
            simSpoolDbgRaw  = (uint16_t)raw;
            simSpoolDbgOut  = simTx[simMotorChannel - 1];
            simSpoolDbgRamp = ramping;
        }
        SimUSB::sendChannels(simTx);
        SimUSB::keyboardTick();   // send any pending camera/view keystroke (non-blocking)
    } else {
        protocolRx();          // pull any telemetry/MSP bytes the FC has sent back on D5
        mspBridgePoll();       // TCP/5760 ↔ FC for wireless Rotorflight config
        mspFcPoll();
    fcTelemWatch();           // periodic FC-variant / FC-version discovery
        txParamsLoop();        // TX Rotorflight edits: async MSP read/write state machine
    }
    vbatPoll();                // battery divider ADC (5 Hz, no-op when off)
    telemetrySampleTick();     // 1 Hz flight telemetry log (ESC temp / head speed / battery)
    flightSaveTick();          // save the flight to flash on DISARM — safe, on the ground (arming-channel idea)
    flightSaveAsyncTick();     // trickle any in-progress save out, ~64 samples per pass (10 ms doctrine)
    batteryGuardTick();        // low-battery warning + forgotten-model deep sleep (Malcolm 2026-07-28)

    // Dual-radio redundancy: if we've not received a packet on the active
    // radio for a while AND a swap cooldown has elapsed AND we have a second
    // radio populated, try the other radio (v1 TryTheOtherTransceiver).
    if (numRadiosPresent >= 2 && bindState.bound && rx.lastMillis != 0 &&
        (uint32_t)(millis() - rx.lastMillis)     >= RADIO_SWAP_PACKET_TIMEOUT_MS &&
        (uint32_t)(millis() - lastRadioSwapMs)   >= RADIO_SWAP_COOLDOWN_MS) {
        // Try the other radio once per failure — but once we've cycled through
        // all present radios with no packet returning, the TX is gone, so stop
        // storming (back off to a slow dead-link probe). A real packet arriving
        // resets the counter and re-arms instant failover. This kills the
        // ~20-swaps/s storm that was flooding the log and bursting CRSF output.
        static uint32_t pktsAtLastSwap = 0;
        static uint8_t  triesSincePkt  = 0;
        if (rx.packets != pktsAtLastSwap) triesSincePkt = 0;   // link responded → re-arm fast failover
        bool triedAllRadios = (triesSincePkt >= numRadiosPresent);
        bool deadProbeDue   = (uint32_t)(millis() - lastRadioSwapMs) >= RADIO_SWAP_DEAD_RETRY_MS;
        if (!triedAllRadios || deadProbeDue) {
            swapRadios();
            pktsAtLastSwap = rx.packets;
            triesSincePkt++;
        }
    }

    // Accrue dwell time on the currently-active radio every loop, so the
    // per-transceiver "active time" counters always tick once/second while
    // running (V1 behaviour). Independent of swaps; radioElapsedSec() reads it.
    {
        static uint32_t lastRadioTickMs = millis();
        uint32_t nowTick = millis();
        uint8_t  a = (uint8_t)(activeRadioIdx - 1);
        if (a < 3) radioActiveMs[a] += (nowTick - lastRadioTickMs);
        lastRadioTickMs = nowTick;
        // Refresh the per-flight freeze point while the link is live; it
        // stops at signal loss so the flight's R1/R2 split doesn't keep
        // growing while the radios listen on the bench afterwards.
        if (rx.lastMillis && (nowTick - rx.lastMillis) < 1000) {
            for (uint8_t i = 0; i < 3; ++i) linkStats.radioMsAtLive[i] = radioActiveMs[i];
            linkStats.swapsAtLive = radioSwaps;   // swap count freezes at loss too
        }
    }

    if (!simEnabled) sbusTick();   // no RC output frames at all while in sim mode
    heartbeat();
    statusLedTick();    // D4 connection-status LED (2-radio boards)
    netStep();

    // Periodic free-heap snapshot to the event log so we can spot leaks
    // (every 60 s; logs only when value drops to track downward trend).
    {
        static uint32_t lastHeapLogMs = 0;
        static uint32_t lastHeap      = 0xFFFFFFFF;
        if ((uint32_t)(millis() - lastHeapLogMs) >= 60000) {
            lastHeapLogMs = millis();
            uint32_t now = ESP.getFreeHeap();
            // Log on first sample, or if heap has dropped by >2 KB since the last log.
            if (lastHeap == 0xFFFFFFFF || (lastHeap > now && (lastHeap - now) > 2048)) {
                char buf[64];
                snprintf(buf, sizeof(buf), "Free heap: %u B (was %u)",
                         (unsigned)now, (unsigned)lastHeap);
                events.add(buf);
                lastHeap = now;
            } else if (now > lastHeap) {
                lastHeap = now;   // recovered (e.g. closed connections freed) — update baseline silently
            }
        }
    }

    // After 5 s of stable running, clear the quick-boot counter so an isolated
    // power-cycle doesn't accumulate toward the 3-trip threshold.
    static bool quickBootReset = false;
    static uint32_t qbcClearAtMs = 0;
    if (!quickBootReset && millis() > QUICK_BOOT_RESET_MS) {
        // NVS write = flash stall (both cores freeze; worst-case ~1 s with
        // page housekeeping). Fired at exactly t=5 s it blocked the loop
        // MID-SESSION whenever the TX was on from boot — the mystery 1 s
        // link gap in every bench blackbox (2026-07-23). Link quiet → write
        // at once. Link LIVE → the old code waited for a quiet moment that a
        // battery-pull-with-TX-on never provides, so bench sessions banked
        // "quick boots" until the third one tripped recovery and flipped the
        // protocol (Malcolm 2026-08-05, Black-Thunder-2). Now: disarmed with
        // the link up = healthy by definition — announce a gap pardon, then
        // clear ~300 ms later. NEVER while armed (the stall stops output).
        bool linkLive = rx.lastMillis && (uint32_t)(millis() - rx.lastMillis) < 2000;
        const bool armedNow = (armingChannel >= 1 && armingChannel <= 16 &&
                               rx.lastMillis && (uint32_t)(millis() - rx.lastMillis) < 1000 &&
                               channelMicros[armingChannel - 1] > 1500);
        if (!linkLive) {
            prefs.putUChar(NVS_KEY_BOOT_COUNT, 0);
            quickBootReset = true;
            events.add("Quick-boot counter cleared");
        } else if (!armedNow && !qbcClearAtMs) {
            fltPardonMsToSend = FLT_PARDON_MS;
            fltPardonAnnounceLeft = 25;
            qbcClearAtMs = millis() + 300;
        }
    }
    if (qbcClearAtMs && (int32_t)(millis() - qbcClearAtMs) >= 0) {
        qbcClearAtMs = 0;   // re-schedules itself if armed slipped in
        const bool armedNow = (armingChannel >= 1 && armingChannel <= 16 &&
                               rx.lastMillis && (uint32_t)(millis() - rx.lastMillis) < 1000 &&
                               channelMicros[armingChannel - 1] > 1500);
        if (!armedNow && !quickBootReset) {
            prefs.putUChar(NVS_KEY_BOOT_COUNT, 0);
            quickBootReset = true;
            events.add("Quick-boot counter cleared (pardoned)");
        }
    }

    // Learn the arming channel from Rotorflight itself (Malcolm 2026-08-23:
    // "Fly now should not appear if Rotorflight is detected because the
    // arming switch takes over its function"). With RF confirmed over MSP
    // and no channel configured, read the FC's mode ranges (MSP 34) and
    // adopt the ARM range's AUX channel — RAM only, never written to NVS,
    // so a user-set channel always wins and non-RF models are untouched.
    // Everything keyed on armingChannel follows for free: auto fly mode,
    // disarm revival, arm-based flight saves, and the front page hiding
    // the now-redundant Fly now button.
    {
        static uint32_t armLearnNextMs = 0;
        static bool     armLearnPending = false;
        static bool     armLearned = false;
        const bool rfConfirmed = fcInfo.detected && fcInfo.versionKnown &&
                                 strncmp(fcInfo.variant, "RTFL", 4) == 0;
        if (!armLearned && !armingChannel && rfConfirmed &&
            (int32_t)(millis() - armLearnNextMs) >= 0) {
            if (!armLearnPending) {
                if (txParamMspFree() && !txParamBusy && mspAsyncFunc == 0xFF) {
                    mspAsyncFunc = 34; mspAsyncReady = false;   // MSP_MODE_RANGES
                    mspSendRequest(34);
                    armLearnPending = true;
                    armLearnNextMs  = millis() + 1500;          // response window
                }
            } else {
                // window expired without a reply — release the slot, retry
                if (mspAsyncFunc == 34) mspAsyncFunc = 0xFF;
                armLearnPending = false;
                armLearnNextMs  = millis() + 10000;
            }
        }
        if (armLearnPending && mspAsyncReady && mspAsyncFunc == 34) {
            for (uint16_t o = 0; o + 3 < mspAsyncLen; o += 4) {
                // slot: permanentId, auxChannel, startStep, endStep — unused
                // slots read id 0 with an EMPTY range, so ARM (id 0) must
                // also have start != end to count.
                if (mspAsyncBuf[o] == 0 && mspAsyncBuf[o + 2] != mspAsyncBuf[o + 3]) {
                    uint8_t ch = mspAsyncBuf[o + 1] + 5;        // aux0 = channel 5
                    if (ch <= 16) {
                        armingChannel = ch;                     // RAM only — not NVS
                        armLearned = true;
                        char m[64];
                        snprintf(m, sizeof(m), "Arming channel found from Rotorflight: ch%u (AUX%u)",
                                 ch, ch - 4);
                        events.add(m);
                    }
                    break;
                }
            }
            mspAsyncFunc = 0xFF;
            armLearnPending = false;
            if (!armLearned) armLearnNextMs = millis() + 30000; // no ARM range yet — retry
        }
    }

    // Auto fly mode (Malcolm 2026-08-24: "there will be people, including
    // me, who forget to hit Fly now"). Triggered by ARMING, sustained 3 s —
    // deliberately BEFORE takeoff, not on flying detection: the WiFi/BLE
    // teardown stalls the loop ~700 ms (measured 707 ms, 2026-08-04), which
    // must land harmlessly during ground spool-up and NEVER mid-air with
    // frozen controls ("doubly sure the disabled functions ARE NOT THE
    // CONTROL FUNCTIONS" — Malcolm, quite rightly, 2026-08-24). Only the
    // config radios are touched; the nRF24 control link, channel decode and
    // FC output are a separate path and keep running throughout. The
    // existing landing recovery revives WiFi/Bluetooth after the flight;
    // the switch lives on the Receiver-settings page (default ON).
    autoFlyForcedNow = fcIsRotorflightConfigCapable();   // RF present = no opt-out
    if (autoFlyActive() && !simEnabled && !flyArmRequested && !flyTeardownAtMs) {
        static uint32_t armedSinceMs = 0;
        const bool radiosUp = (netMode != NET_NO_WIFI) || bleAdvertising() || bleHasClient();
        const bool linkLive = rx.lastMillis &&
                              (uint32_t)(millis() - rx.lastMillis) < 1000;
        const bool armedNow = armingChannel >= 1 && armingChannel <= 16 &&
                              linkLive && channelMicros[armingChannel - 1] > 1500;
        if (radiosUp && armedNow) {
            if (!armedSinceMs) armedSinceMs = millis();
            else if ((uint32_t)(millis() - armedSinceMs) > 3000) {
                armedSinceMs = 0;
                events.add("AUTO fly mode: armed — radios off before takeoff");
                eventsPersist();
                flyArmRequested = true;
            }
        } else {
            armedSinceMs = 0;
        }
    }

    // Deferred WiFi-off so the response to /fly_arm completes before the radio
    // dies — AND so the gap pardon reaches the TX first. delay(300) used to
    // block here, which stopped radioPoll and with it the very acks carrying
    // the pardon; now the loop keeps running for the 300 ms instead.
    if (flyArmRequested) {
        flyArmRequested = false;
        if (rx.lastMillis && (uint32_t)(millis() - rx.lastMillis) < 1000) {
            fltPardonMsToSend = FLT_PARDON_MS;     // the ~700 ms teardown stall
            fltPardonAnnounceLeft = 25;            // ~50 ms of acks at 500 Hz
        }
        flyTeardownAtMs = millis() + 300;
    }
    if (flyTeardownAtMs && (int32_t)(millis() - flyTeardownAtMs) >= 0) {
        flyTeardownAtMs = 0;
        disableWifi();
        statsZeroAtMs = millis() + 3000;   // Malcolm: zero EVERYTHING ~3 s after Fly now
    }

    // Fly-now stats zero (Malcolm 2026-07-28): the REAL flight starts a few
    // seconds after Fly — bench time, the BLE era and its dying bursts are
    // prehistory. Wipe the whole flight record: link stats AND the telemetry
    // graph ring. A fresh connStart means the arm-based save treats what
    // follows as its own session (its own saved slot), and the normal 3 s
    // grace re-baselines swaps/radio-times through the existing machinery.
    if (statsZeroAtMs && (int32_t)(millis() - statsZeroAtMs) >= 0) {
        statsZeroAtMs = 0;
        linkStats = LinkStats{};
        linkStats.connStartMs = millis();
        teleCount = 0;
        teleHead  = 0;
        events.add("Flight record zeroed (fly mode)");
    }
}
