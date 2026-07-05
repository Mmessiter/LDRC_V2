// LockDownRadioControl — RXV2  ::  Wifi.h
//
// WiFi state machine + ArduinoOTA + mDNS. The boot flow is:
//   1. Listen for the TX for ~10 s on a fixed channel.
//   2. If a packet arrives in that window, skip WiFi (RF-only flight mode).
//   3. Otherwise try saved STA credentials; on failure fall back to AP mode.
// The user can also force WiFi off mid-session via /fly_arm, or force WiFi on
// via the triple-power-cycle escape hatch in setup().
//
//*********************************************************************

#ifndef _SRC_WIFI_H
#define _SRC_WIFI_H

#include "1Defs.h"
#include "Storage.h"

// Defined in BleConfig.h (included later in this translation unit).
// BLE strictly mirrors the WiFi lifecycle: same on switches, same off switch.
inline void bleStart();
inline void bleStop();

//*********************************************************************
//  Net-mode name (for UI + serial)
//*********************************************************************

inline const char* netModeName() {
    switch (netMode) {
        case NET_INIT:             return "init";
        case NET_WAITING_RF:       return "waiting for TX";
        case NET_NO_WIFI:          return "RF-only (no WiFi)";
        case NET_WIFI_CONNECTING:  return "connecting WiFi";
        case NET_WIFI_UP:          return "WiFi up";
        case NET_AP:               return "AP mode";
    }
    return "?";
}

//*********************************************************************
//  LED helpers (used by both this module and Web/main)
//*********************************************************************
// Active-low: writing LOW turns the LED on.

inline void ledOn()  { digitalWrite(LED_PIN, LOW);  }
inline void ledOff() { digitalWrite(LED_PIN, HIGH); }

//*********************************************************************
//  Uptime as "Xh Ym Zs" (for /diagnostics)
//*********************************************************************

inline String uptimeString() {
    uint32_t s = (millis() - bootMillis) / 1000;
    uint32_t h = s / 3600; s %= 3600;
    uint32_t m = s / 60;   s %= 60;
    char buf[24];
    snprintf(buf, sizeof(buf), "%luh %lum %lus", (unsigned long)h, (unsigned long)m, (unsigned long)s);
    return String(buf);
}

//*********************************************************************
//  ArduinoOTA setup
//*********************************************************************
// Called once we have a working WiFi interface (STA or AP).

inline void setupOTA() {
    if (otaStarted) return;
    ArduinoOTA.setHostname(g_hostname.c_str());
    if (OTA_PASSWORD) ArduinoOTA.setPassword(OTA_PASSWORD);

    ArduinoOTA
        .onStart([]() {
            Serial.printf("[ota] start (%s)\n",
                          ArduinoOTA.getCommand() == U_FLASH ? "flash" : "fs");
            ledOn();
        })
        .onEnd([]() {
            Serial.println("\n[ota] complete");
            ledOff();
        })
        .onProgress([](unsigned int p, unsigned int t) {
            Serial.printf("[ota] %u%%\r", (p * 100) / t);
        })
        .onError([](ota_error_t e) {
            Serial.printf("[ota] error %u\n", e);
        });
    ArduinoOTA.begin();
    otaStarted = true;
    Serial.printf("[ota] ready as %s.local:3232\n", OTA_HOSTNAME);
}

//*********************************************************************
//  mDNS + OTA bring-up
//*********************************************************************

inline void startMdnsAndOta() {
    if (!MDNS.begin(OTA_HOSTNAME)) {
        Serial.println("[mdns] failed");
    } else {
        MDNS.addService("http", "tcp", 80);
        Serial.printf("[mdns] http://%s.local/\n", OTA_HOSTNAME);
    }
    setupOTA();
}

//*********************************************************************
//  HTTP server start (deferred until WiFi is up)
//*********************************************************************
// server.begin() touches LwIP — calling it before WiFi STA or AP is up
// panics the chip ("assert failed: tcpip_send_msg_wait_sem ... Invalid mbox").

inline void startHttpServerIfNeeded() {
    if (httpServerStarted) return;
    server.begin();
    httpServerStarted = true;
    Serial.println("[http] listening on :80");
}

//*********************************************************************
//  STA connect attempt
//*********************************************************************

inline void startWifiStation() {
    // From v0.9.51 the chip runs AP+STA simultaneously. The soft-AP
    // `LDRC_RX` is always live at 192.168.4.1 regardless of home WiFi
    // state, so the user can ALWAYS reach the chip — overnight router
    // hiccups, channel storms, ISP outages, none of it strands them in
    // a no-WiFi state any more. The web server, mDNS and MSP bridge
    // all come up immediately on the AP side; STA tries the home
    // network in the background and joins when it can.
    WiFi.persistent(false);
    // Decide pure-AP vs AP+STA UP FRONT. A pure softAP (STA interface off) stays
    // pinned to channel 1 and is far more reliably joinable. An AP+STA radio has
    // ONE PHY: whenever the STA side scans or (re)connects it hops channels, and
    // the softAP is dragged along — which knocks a phone off mid-join ("Unable to
    // join the network"). That's exactly the "had to try several times" symptom,
    // and it's worst at the field where the home net is absent so STA retries
    // forever. So only stand up STA when we actually intend to join a network.
    String ssid = getEffectiveSsid();
    bool apOnly = prefs.isKey(NVS_KEY_AP_ONLY) && prefs.getBool(NVS_KEY_AP_ONLY, false);
    bool staWanted = !apOnly && ssid.length() > 0;
    WiFi.mode(staWanted ? WIFI_AP_STA : WIFI_AP);
    // AP SSID is the user-friendly model name (or "RXV2" default).
    // Phones in the area see "Goblin 700" instead of a generic
    // name and can tell receivers apart at a glance. Fixed channel 1 so the
    // AP never moves under a connected client.
    WiFi.softAP(g_effectiveName.c_str(), nullptr, 1);
    WiFi.setSleep(false);
    // The WiFi radio sits right beside the nRF24. In sim mode the TX link is live the
    // whole time, and full WiFi power (~90 mW @ 19.5 dBm) desensitises the receiver —
    // that's the short range + dropped frames seen when driving the sim. A phone on the
    // same desk needs only a sliver of that, so dial WiFi down in sim mode; normal
    // (config) mode keeps full reach. 11 dBm (was 8.5): +2.5 dB makes the web UI
    // noticeably snappier while the TX is on, and the current PCBs have both
    // radios on separated u.FL whips so the desense margin is better than the
    // chip-antenna prototypes this limit was tuned on. If sim frame rate drops,
    // 8.5 dBm is the proven-safe fallback.
    WiFi.setTxPower(simEnabled ? WIFI_POWER_11dBm : WIFI_POWER_19_5dBm);
    Serial.printf("[wifi] soft-AP '%s' up at %s\n",
                  g_effectiveName.c_str(), WiFi.softAPIP().toString().c_str());

    // Bring the web server / mDNS up NOW on the AP side. Once STA
    // connects, the same handlers serve traffic at the LAN IP too —
    // startHttpServerIfNeeded() is idempotent.
    if (MDNS.begin(g_hostname.c_str())) {
        MDNS.addService("http", "tcp", 80);
    }
    setupOTA();
    startHttpServerIfNeeded();
    mspBridgeStart();

    if (!staWanted) {
        // Stay AP-only: either the user has chosen "AP mode only" (flying field —
        // don't burn time chasing an out-of-range home network) or there are no
        // saved creds. Everything (web/mDNS/OTA/bridge) is already up on the AP.
        if (apOnly) {
            Serial.println("[wifi] AP-only mode (field setting) — not trying home WiFi");
            events.add("AP-only mode (field setting)");
        } else {
            Serial.println("[wifi] no NVS SSID — AP-only");
            events.add("No SSID — AP-only");
        }
        netMode = NET_AP;
        bleStart();   // BLE config comes up whenever WiFi config does
        return;
    }
    Serial.printf("[wifi] STA connecting to '%s' (AP stays up)\n", ssid.c_str());
    WiFi.setHostname(g_hostname.c_str());
    WiFi.begin(ssid.c_str(), getEffectivePass().c_str());
    netMode       = NET_WIFI_CONNECTING;
    netStateStart = millis();

    char buf[80];
    snprintf(buf, sizeof(buf), "Trying STA WiFi '%s' (AP also up)", ssid.c_str());
    events.add(buf);
    bleStart();   // BLE config comes up whenever WiFi config does
}

//*********************************************************************
//  STA connected handler
//*********************************************************************
// Disables WiFi modem sleep — without this the first request after any idle
// period takes ~100-200 ms while the radio wakes up, which feels like UI lag.
// ~20 mA cost is irrelevant when we're powered by USB or BEC.

inline void onWifiConnected() {
    // STA joined home WiFi. AP + web server are already up from
    // startWifiStation() so there's nothing to bring up here — we just
    // log, reset counters, and transition state.
    Serial.printf("[wifi] STA %s  RSSI %d dBm\n",
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
    char buf[80];
    snprintf(buf, sizeof(buf), "WiFi up: %s", WiFi.localIP().toString().c_str());
    events.add(buf);
    staAttempts = 0;
    staGaveUp   = false;   // home WiFi is here after all → back to normal AP+STA retry cadence
    netMode = NET_WIFI_UP;
    ledOff();

    // Re-announce mDNS on the STA interface. mDNS was first started in
    // startWifiStation() before STA had an IP, so it bound to the AP side and
    // <hostname>.local often won't resolve on the home network until we
    // re-register now that we have a real STA address. Without this the chip is
    // reachable by IP but not by name after every (re)connect — which looks
    // exactly like "it dropped to AP / lost WiFi" even though it didn't.
    MDNS.end();
    if (MDNS.begin(g_hostname.c_str())) {
        MDNS.addService("http", "tcp", 80);
        Serial.printf("[mdns] re-announced http://%s.local/ on STA\n", g_hostname.c_str());
    } else {
        Serial.println("[mdns] re-announce failed");
    }
}

//*********************************************************************
//  AP fallback
//*********************************************************************

// Kept for the quick-boot escape hatch / "no SSID" boot path. Tears
// STA down and stays in AP-only mode. In normal operation we run
// AP+STA via startWifiStation() so this is rarely called.
inline void startApMode() {
    Serial.printf("[wifi] AP-only mode, '%s'\n", g_effectiveName.c_str());
    WiFi.disconnect(true);
    delay(50);
    WiFi.mode(WIFI_AP);
    WiFi.softAP(g_effectiveName.c_str());
    WiFi.setSleep(false);
    delay(150);
    char buf[80];
    snprintf(buf, sizeof(buf), "AP-only mode: %s at %s",
             g_effectiveName.c_str(), WiFi.softAPIP().toString().c_str());
    events.add(buf);
    if (MDNS.begin(g_hostname.c_str())) {
        MDNS.addService("http", "tcp", 80);
    }
    startHttpServerIfNeeded();
    mspBridgeStart();
    netMode = NET_AP;
    bleStart();   // BLE config comes up whenever WiFi config does
}

//*********************************************************************
//  Force WiFi off (Fly mode)
//*********************************************************************

inline void disableWifi() {
    Serial.println("[wifi] turning off until reboot");
    bleStop();    // fly mode silences BLE too — same rule as WiFi
    if (otaStarted) {
        ArduinoOTA.end();
        otaStarted = false;
    }
    MDNS.end();
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
    netMode = NET_NO_WIFI;
    events.add("WiFi off (until reboot)");
}

//*********************************************************************
//  Periodic state-machine step (call from loop())
//*********************************************************************

inline void netStep() {
    // Non-blocking WiFi re-begin: a STA retry used to do WiFi.disconnect() +
    // delay(200) + WiFi.begin() inline, which BLOCKED the main loop for ~208 ms
    // every retry — long enough to pause CRSF/SBUS output and starve radioPoll,
    // so a flaky WiFi (desensed by the nRF24) made the FC flash to zero. We now
    // record when to re-begin and fire it on a later pass, never delaying.
    static uint32_t wifiRebeginAtMs = 0;
    if (wifiRebeginAtMs && (int32_t)(millis() - wifiRebeginAtMs) >= 0) {
        wifiRebeginAtMs = 0;
        WiFi.begin(getEffectiveSsid().c_str(), getEffectivePass().c_str());
        netStateStart = millis();
    }
    switch (netMode) {
        case NET_WAITING_RF:
            // If a real packet has arrived, the TX is on — stay RF-only this session.
            if (rx.packets > 0) {
                Serial.println("[net] TX heard during boot window — staying RF-only");
                events.add("TX heard at boot — WiFi stays OFF");
                netMode = NET_NO_WIFI;
                return;
            }
            if ((uint32_t)(millis() - netStateStart) >= RF_WINDOW_MS) {
                Serial.println("[net] boot window timed out, trying WiFi");
                events.add("No TX at boot — WiFi on");
                startWifiStation();
            }
            break;

        case NET_WIFI_CONNECTING:
        {
            // AP is already up from startWifiStation(), so we NEVER
            // fall back to AP-only from this state any more. Just
            // retry STA forever — the user can always reach the chip
            // via the AP side regardless of how STA is faring.
            wl_status_t s = WiFi.status();
            if (s == WL_CONNECTED) {
                onWifiConnected();
                break;
            }
            if ((uint32_t)(millis() - netStateStart) >= WIFI_CONNECT_MS) {
                // If a phone is on our softAP, DON'T churn the STA side now — a
                // disconnect+scan hops channels and boots that phone off mid-
                // session. Hold the retry until they're done (self-heal resumes
                // the moment the AP is idle again). This is the field fix.
                if (WiFi.softAPgetStationNum() > 0) { netStateStart = millis(); break; }
                staAttempts++;
                Serial.printf("[net] STA attempt %u timed out (status=%d)\n",
                              (unsigned)staAttempts, (int)s);

                // Home network is clearly ABSENT (the flying-field case): stop
                // hammering STA — every retry hops the shared radio's channel
                // and makes the AP slow/unjoinable. Drop the STA interface and
                // run a STABLE pure-AP (fixed channel 1). NET_AP re-probes home
                // WiFi rarely (AP_RECHECK_MS), so a real home comes back on its own.
                if (staAttempts >= STA_GIVEUP_ATTEMPTS) {
                    Serial.println("[net] home WiFi not found — auto-enabling AP-only");
                    { char b[80]; snprintf(b, sizeof(b), "Home WiFi '%s' not found — AP-only auto-enabled", getEffectiveSsid().c_str()); events.add(b); }
                    // PERSIST it: subsequent power-ups (next flight at the field)
                    // go straight to a stable AP with no 100 s of hunting for a
                    // home net that isn't there. apAuto marks it as automatic so
                    // the front page can say why and the user can undo it at home.
                    prefs.putBool(NVS_KEY_AP_ONLY, true);
                    prefs.putBool(NVS_KEY_AP_AUTO, true);
                    apAutoEnabled = true;
                    WiFi.disconnect(false, true);
                    WiFi.mode(WIFI_AP);                                 // drop STA entirely
                    WiFi.softAP(g_effectiveName.c_str(), nullptr, 1);   // re-pin AP to channel 1
                    staGaveUp = true;
                    netMode   = NET_AP;
                    break;
                }
                { char buf[64]; snprintf(buf, sizeof(buf), "STA retry %u (status=%d)", (unsigned)staAttempts, (int)s); events.add(buf); }
                // Restart the STA side only. AP stays up because we
                // pass `false` to WiFi.disconnect (don't turn WiFi off).
                WiFi.disconnect(false, true);   // disconnect STA, erase saved AP
                wifiRebeginAtMs = millis() + 200;  // non-blocking: begin() fires on a later pass — never delay() the loop
                netStateStart = millis();
                break;
            }
            // Still connecting — blink LED.
            static uint32_t lastBlink = 0;
            if (millis() - lastBlink > 150) {
                lastBlink = millis();
                digitalWrite(LED_PIN, !digitalRead(LED_PIN));
            }
            break;
        }

        case NET_WIFI_UP:
        {
            // 3-second debounce. ESP32's WiFi.status() can transiently
            // report not-connected during background scans even when
            // the link is fine, so we only treat a drop as real after
            // the radio has been disconnected for several seconds.
            static uint32_t disconnectedSinceMs = 0;
            if (WiFi.status() == WL_CONNECTED) {
                disconnectedSinceMs = 0;
                break;
            }
            if (disconnectedSinceMs == 0) {
                disconnectedSinceMs = millis();
                break;
            }
            if (millis() - disconnectedSinceMs < 3000) break;
            // Genuinely dropped — go back to NET_WIFI_CONNECTING and
            // re-try STA. AP stays up throughout.
            Serial.println("[wifi] STA dropped, retrying (AP still up)");
            events.add("WiFi dropped, retrying");
            disconnectedSinceMs = 0;
            WiFi.disconnect(false, true);
            wifiRebeginAtMs = millis() + 200;  // non-blocking re-begin — never delay() the loop
            netMode       = NET_WIFI_CONNECTING;
            netStateStart = millis();
            break;
        }

        case NET_AP:
            // AP-only is correct ONLY when there are no saved STA creds (first-
            // time setup). If creds DO exist we belong on the home network — so
            // periodically retry STA. This self-heals a receiver that fell to
            // AP-only from a transient failed connect, a router hiccup, or an NVS
            // read race during rapid reboots (e.g. toggling sim mode), instead of
            // stranding it off the home network until a manual power-cycle.
            {
                static uint32_t lastApRetry = 0;
                bool apOnlySet = prefs.isKey(NVS_KEY_AP_ONLY) && prefs.getBool(NVS_KEY_AP_ONLY, false);
                // NB when the home net proved absent we AUTO-SET "AP mode only"
                // (apOnlySet becomes true), so this self-heal retry stops firing —
                // the field AP stays rock-stable, and every later power-up is
                // instant AP-only. The user clears it from WiFi settings at home.
                if (!apOnlySet &&
                    getEffectiveSsid().length() > 0 &&
                    WiFi.softAPgetStationNum() == 0 &&   // don't disrupt a phone using the AP
                    (uint32_t)(millis() - lastApRetry) >= AP_STA_RETRY_MS) {
                    lastApRetry = millis();
                    staAttempts = 0;
                    Serial.println("[net] AP-only but creds exist — retrying home WiFi");
                    events.add("AP-only: retrying home WiFi");
                    startWifiStation();   // AP+STA → NET_WIFI_CONNECTING
                }
            }
            break;

        case NET_NO_WIFI: {
            // RF-only "fly mode" — WiFi was switched off because a TX was present
            // at boot. If the link then stays gone for WIFI_REENABLE_AFTER_LOST_MS
            // (landed, or TX switched off), bring WiFi back automatically so the
            // user can reach the receiver again without a power-cycle. Only fires
            // once we've actually had a link (rx.lastMillis != 0).
            if (rx.lastMillis != 0 &&
                (uint32_t)(millis() - rx.lastMillis) >= WIFI_REENABLE_AFTER_LOST_MS) {
                Serial.println("[net] TX link lost — bringing WiFi back up");
                events.add("TX lost — WiFi re-enabled");
                startWifiStation();   // → AP (+ STA if creds), reachable again
            }
            break;
        }
        case NET_INIT:
            break;
    }
}

//*********************************************************************
//  Status LED — encodes link state on the XIAO on-board LED
//*********************************************************************
// The on-board LED shares GPIO 21 with the protocol output pin, so the
// LED behaviour depends on which protocol is running and whether the
// peripheral is currently driving the pin:
//
//   UNBOUND           → 2 Hz blink (peripheral not running yet)
//   BOUND, idle-LOW   → LED solid on (SBUS/FBUS UART idle drives pin LOW)
//   BOUND, idle-HIGH  → LED dark while link is up (CRSF/IBUS idle HIGH),
//                       solid on when link is lost (Output.h has released
//                       the UART so heartbeat() can drive the pin LOW).
//
// In other words: across protocols, BLINKING always means "bind mode",
// LIT means "something needs attention" (either bind it or restore the
// link), DARK means "link is fine, carry on". Inverted from the literal
// "ON = connected" only on idle-HIGH protocols, which is the best the
// shared-pin physics allows.

constexpr uint32_t LED_BIND_HALF_PERIOD_MS = 250;   // 2 Hz square wave

inline void heartbeat() {
    static uint32_t nextEdge = 0;
    static bool     blinkOn  = false;
    const uint32_t now = millis();

    if (!bindState.bound) {
        // Unbound — 2 Hz square wave. No protocol output is running yet
        // (we don't have channel data to send), so digitalWrite has full
        // control of the pin.
        if (now >= nextEdge) {
            blinkOn = !blinkOn;
            if (blinkOn) ledOn(); else ledOff();
            nextEdge = now + LED_BIND_HALF_PERIOD_MS;
        }
        return;
    }
    nextEdge = 0; blinkOn = false;   // reset phase for next unbind

    // Bound. On idle-HIGH protocols Output.h drops the UART during
    // failsafe and parks the pin HIGH; we drive it LOW now so the LED
    // lights as a "no link" warning. On idle-LOW protocols (and any
    // bound+link-live state) we let the peripheral run the pin — our
    // writes are no-ops while the GPIO matrix is bound.
    if (outputDetachedForFailsafe) ledOn();
}

//*********************************************************************
//  Compute "days since 2020-01-01" from __DATE__
//*********************************************************************
// v1 reports the same quantity as telemetry item 35 (BuildAge); the TX
// subtracts the two and warns if they differ by more than a few days.
// Computed once at boot.

inline uint32_t computeBuildDays() {
    const char* d = __DATE__;                            // "Mmm dd yyyy"
    static const char* months = "JanFebMarAprMayJunJulAugSepOctNovDec";
    int month = 0;
    for (int i = 0; i < 12; ++i) {
        if (d[0] == months[i*3] && d[1] == months[i*3+1] && d[2] == months[i*3+2]) {
            month = i + 1;
            break;
        }
    }
    int day  = atoi(d + 4);
    int year = atoi(d + 7);

    auto isLeap = [](int y) {
        return (y % 4 == 0 && y % 100 != 0) || (y % 400 == 0);
    };
    static const int dim[12] = { 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };
    uint32_t total = 0;
    for (int y = 2020; y < year; ++y) total += isLeap(y) ? 366 : 365;
    for (int m = 0; m < month - 1; ++m) {
        total += dim[m];
        if (m == 1 && isLeap(year)) total += 1;
    }
    total += day - 1;
    return total;
}

#endif // _SRC_WIFI_H
