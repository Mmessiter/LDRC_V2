// LockDownRadioControl — RXV2  ::  WebPages.h
//
// HTTP request handlers. As of v0.6.0 the GET pages are static HTML files in
// data/ (served from LittleFS); each page fetches /api/state.json on load and
// populates placeholders via JS. POST handlers stay here in C++ because they
// send a one-shot confirmation and reboot the chip.
//
// Routes are registered in main.cpp setup() via registerWebRoutes() below so
// the server is ready the instant any net mode brings up an interface.
//
//*********************************************************************

#ifndef _SRC_WEBPAGES_H
#define _SRC_WEBPAGES_H

#include "1Defs.h"
#include "Storage.h"
#include "Output.h"        // protocolName(), protocolDesc()
#include "Network.h"       // netModeName(), uptimeString(), disableWifi()
#include "Radio.h"         // runRadioSelfTest(), dataRateName()
#include "BleConfig.h"     // ReqRouter: same handlers serve WiFi and BLE

// Within this file every `server.` call goes through the router, which
// forwards to the real WebServer normally and captures the response when a
// BLE request is being serviced. One config engine, two transports.
#define server g_bleRouter

//*********************************************************************
//  Embedded fallback CSS (used only if LittleFS mount failed)
//*********************************************************************
// The canonical stylesheet lives in data/style.css — this is the rescue
// version so a totally-broken FS still produces a readable page.

inline const char PAGE_CSS_FALLBACK[] PROGMEM = R"CSS(
body{font-family:-apple-system,sans-serif;background:#f4e4c1;color:#2c3e50;padding:1em}
.container{max-width:500px;margin:0 auto}
.card{background:rgba(255,255,255,.65);border-radius:14px;padding:1.2em 1.4em;margin:.8em 0}
.btn{display:block;padding:1em;margin:.5em 0;background:#7d9eb0;color:#fff;text-decoration:none;border-radius:8px;text-align:center}
.muted{color:#7a8b95}
.footer{text-align:center;margin-top:2em;color:#5d7a8c;font-size:.85em}
)CSS";

//*********************************************************************
//  Embedded fallback home page (LittleFS broken / first-ever boot)
//*********************************************************************
// If we can't serve data/index.html, send this minimal recovery page that
// at least links to /wifi so the user can configure access.

inline const char FALLBACK_INDEX[] PROGMEM = R"HTML(
<!doctype html><html><head><meta charset=utf-8>
<title>LDRC RX V2 — recovery</title>
<style>body{font-family:-apple-system,sans-serif;background:#fff;color:#2c3e50;padding:1.5em;max-width:520px;margin:0 auto}
h1{color:#c97464}.card{background:#f4e4c1;border-radius:12px;padding:1em;margin:1em 0}
a{display:block;padding:.8em;margin:.5em 0;background:#7d9eb0;color:#fff;text-decoration:none;border-radius:8px;text-align:center}</style></head>
<body><h1>Recovery mode</h1>
<div class=card><p><b>LittleFS isn't mounted</b> &mdash; the web UI assets aren't available.
Re-flash the filesystem with <code>pio run -e xiao_ota -t uploadfs</code> from a development Mac.</p>
<p>Limited functions still work from this fallback:</p></div>
<a href="/wifi">WiFi settings (recovery form)</a>
<a href="/firmware">Firmware (OTA still works)</a>
<a href="/diagnostics">Diagnostics (JSON only)</a>
</body></html>
)HTML";

//*********************************************************************
//  Serve a file from LittleFS (returns false if not found / FS not mounted)
//*********************************************************************

inline bool serveLittleFsFile(const char* path, const char* mime) {
    if (!littleFsMounted) return false;
    // Pre-compressed twin (2026-08-29): big static assets live as
    // "<name>.gz" in LittleFS — three.min.js went 668 KB → 166 KB, which is
    // what let the wizard pages + logo fit. Browsers decode
    // Content-Encoding: gzip natively; the apps bundle plain copies.
    String gzPath = String(path) + ".gz";
    bool gz = LittleFS.exists(gzPath);
    if (!gz && !LittleFS.exists(path)) return false;
    File f = LittleFS.open(gz ? gzPath.c_str() : path, "r");
    if (!f) return false;
    if (gz) server.sendHeader("Content-Encoding", "gzip");
    // ETag revalidation. mklittlefs bakes each host file's mtime into the FS
    // image, so size+mtime uniquely identifies the exact build of every asset.
    // When the browser's copy matches we answer 304 (~100 B) instead of
    // re-streaming 10-30 kB — with a TX on, page loads over the contended
    // 2.4 GHz link were dominated by these pointless re-fetches (html + app.js
    // + style.css ≈ 30 kB per navigation under the old no-store policy).
    // Requires server.collectHeaders() in registerWebRoutes (or the request
    // header is never captured and this silently always re-sends).
    char etag[24];
    snprintf(etag, sizeof(etag), "\"%x-%x\"", (unsigned)f.size(), (unsigned)f.getLastWrite());
    server.sendHeader("ETag", etag);
    if (server.header("If-None-Match") == etag) {
        f.close();
        server.send(304, mime ? mime : "text/plain", "");
        return true;
    }
    // no-cache (NOT no-store): the browser MUST revalidate before using its
    // copy — a fresh uploadfs/OTA changes the ETag so staleness is impossible
    // (the old iOS-Safari stale-page bug came from max-age heuristics, i.e.
    // caching WITHOUT revalidation) — but an unchanged file costs one tiny
    // 304 round-trip instead of the whole transfer.
    if (mime && (strncmp(mime, "text/html", 9) == 0)) {
        server.sendHeader("Cache-Control", "no-cache");
    }
    server.streamFile(f, mime);
    f.close();
    return true;
}

//*********************************************************************
//  /style.css — try LittleFS first, fall back to embedded
//*********************************************************************

inline void handleStyleCss() {
    // Revalidate every load via ETag (serveLittleFsFile): a matching copy costs
    // a ~100 B 304 instead of re-streaming 12 kB per navigation, and an OTA/
    // uploadfs changes the ETag so the old day-long-stale-stylesheet bug can't
    // return. no-cache forces the revalidation.
    server.sendHeader("Cache-Control", "no-cache");
    if (serveLittleFsFile("/style.css", "text/css")) return;
    server.send_P(200, "text/css", PAGE_CSS_FALLBACK);
}

//*********************************************************************
//  /app.js — shared JS helpers used by every page
//*********************************************************************

inline void handleAppJs() {
    // Revalidate every load via ETag (serveLittleFsFile). A stale day-long cache
    // here once meant a freshly-OTA'd page called helpers (e.g. LDRC.alert) the
    // cached app.js didn't have — ETag revalidation keeps that fixed while an
    // unchanged 17 kB bundle now costs a ~100 B 304 instead of a re-download.
    server.sendHeader("Cache-Control", "no-cache");
    if (serveLittleFsFile("/app.js", "application/javascript")) return;
    server.send(503, "text/plain", "/app.js not in LittleFS — uploadfs the data/ folder");
}

inline void handleThreeJs() {
    // Three.js UMD bundle for the /diagnostics channel viewer. ~660 kB —
    // browsers must cache it aggressively or every page load re-streams it.
    server.sendHeader("Cache-Control", "public, max-age=604800, immutable");
    if (serveLittleFsFile("/three.min.js", "application/javascript")) return;
    server.send(503, "text/plain", "/three.min.js not in LittleFS — uploadfs the data/ folder");
}

inline void handleFlyingFieldSvg() {
    // Legacy hand-drawn backdrop, kept as a fallback. Live pages now
    // reference the .jpg below instead — switch CSS back here if the
    // photograph ever feels wrong.
    server.sendHeader("Cache-Control", "public, max-age=604800, immutable");
    if (serveLittleFsFile("/flying-field.svg", "image/svg+xml")) return;
    server.send(503, "text/plain", "/flying-field.svg not in LittleFS — uploadfs the data/ folder");
}

inline void handleFlyingFieldJpg() {
    // Photograph backdrop sourced from Unsplash (Wolfgang Hasselmann,
    // Unsplash License — free use, no attribution required). Cached
    // hard via `immutable` — the asset is content-addressed by ?v=
    // query string in style.css, which is the only knob that busts it.
    server.sendHeader("Cache-Control", "public, max-age=604800, immutable");
    if (serveLittleFsFile("/flying-field.jpg", "image/jpeg")) return;
    server.send(503, "text/plain", "/flying-field.jpg not in LittleFS — uploadfs the data/ folder");
}

//*********************************************************************
//  Static-page handlers — each just streams the corresponding HTML file
//*********************************************************************

inline void handleRoot() {
    if (serveLittleFsFile("/index.html", "text/html")) return;
    server.send_P(200, "text/html", FALLBACK_INDEX);
}

inline void handleFly() {
    if (serveLittleFsFile("/fly.html", "text/html")) return;
    server.send(503, "text/plain", "/fly.html missing — uploadfs the data/ folder");
}

inline void handleDiagnostics() {
    if (serveLittleFsFile("/diagnostics.html", "text/html")) return;
    server.send(503, "text/plain", "/diagnostics.html missing — uploadfs the data/ folder");
}

inline void handleRxSettings() {
    if (serveLittleFsFile("/rxsettings.html", "text/html")) return;
    server.send(503, "text/plain", "/rxsettings.html missing — uploadfs the data/ folder");
}

inline void handleBlackbox() {
    if (serveLittleFsFile("/blackbox.html", "text/html")) return;
    server.send(503, "text/plain", "/blackbox.html missing — uploadfs the data/ folder");
}

inline void handleBind() {
    if (serveLittleFsFile("/bind.html", "text/html")) return;
    server.send(503, "text/plain", "/bind.html missing — uploadfs the data/ folder");
}

inline void handleFirmware() {
    if (serveLittleFsFile("/firmware.html", "text/html")) return;
    server.send(503, "text/plain", "/firmware.html missing — uploadfs the data/ folder");
}

inline void handleWifi() {
    if (serveLittleFsFile("/wifi.html", "text/html")) return;
    server.send(503, "text/plain", "/wifi.html missing — uploadfs the data/ folder");
}

inline void handleProtocolPage() {
    if (serveLittleFsFile("/protocol.html", "text/html")) return;
    server.send(503, "text/plain", "/protocol.html missing — uploadfs the data/ folder");
}

inline void handleRotorflight() {
    if (serveLittleFsFile("/rotorflight.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight.html missing — uploadfs the data/ folder");
}

inline void handleSetupPage() {
    if (serveLittleFsFile("/setup.html", "text/html")) return;
    server.send(503, "text/plain", "/setup.html missing — uploadfs the data/ folder");
}

inline void handleSimPage() {
    if (serveLittleFsFile("/sim.html", "text/html")) return;
    server.send(503, "text/plain", "/sim.html missing — uploadfs the data/ folder");
}

inline void handleFlightPage() {
    if (serveLittleFsFile("/flight.html", "text/html")) return;
    server.send(503, "text/plain", "/flight.html missing — uploadfs the data/ folder");
}

inline void handleEventsPage() {
    if (serveLittleFsFile("/events.html", "text/html")) return;
    server.send(503, "text/plain", "/events.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightPid() {
    if (serveLittleFsFile("/rotorflight-pid.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-pid.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightPidPlus() {
    if (serveLittleFsFile("/rotorflight-pidplus.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-pidplus.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightModes() {
    if (serveLittleFsFile("/rotorflight-modes.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-modes.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightFirstTime() {
    if (serveLittleFsFile("/rotorflight-firsttime.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-firsttime.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightNewHeli() {
    if (serveLittleFsFile("/rotorflight-newheli.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-newheli.html missing — uploadfs the data/ folder");
}

// POST /api/fc/wake — wake a FACTORY-FRESH flight controller whose CRSF
// telemetry is off (Malcolm's first real Nexus X, 2026-08-29: with
// telemetry disabled the FC never transmits, so it cannot even be
// discovered — configurator chicken-and-egg). The FC still LISTENS, so we
// blind-write: feature mask = RX_SERIAL|TELEMETRY, save, reboot. REFUSED
// while an FC is already talking — a blind mask write would strip a
// configured board's features (the wizard's Features card re-ticks the
// rest on a fresh board anyway).
inline bool dongleDisarmedConfirmed();   // defined beside refuseIfArmed, below
inline bool refuseIfArmed(const char* what);   // ditto — refuses on an armed model
inline bool rxTxLinkedRecently();              // ditto — a live transmitter link
inline bool refuseIfTxLinked(const char* why);  // ditto — refuses while a TX link is live
inline void handleFcWake() {
    // A dongle port is MSP: if the flight controller is silent it is wiring or
    // the port, not a feature flag — and a dongle that cannot hear the FC also
    // cannot know whether it is armed. Never restart it blind (2026-09-16).
    if (dongleEnabled) {
        server.send(409, "application/json", "{\"ok\":false,\"err\":\"not from a dongle - if the flight controller is silent, check its port setting and the wiring\"}");
        return;
    }
    if (currentProtocol != PROTO_CRSF) {
        server.send(409, "application/json", "{\"ok\":false,\"err\":\"protocol is not CRSF\"}");
        return;
    }
    if (fcInfo.detected ||
        (fcTelem.lastFrameMs && (uint32_t)(millis() - fcTelem.lastFrameMs) < 3000)) {
        server.send(409, "application/json",
            "{\"ok\":false,\"err\":\"a flight controller is already talking — wake is only for silent factory-fresh boards\"}");
        return;
    }
    const uint8_t mask[4] = { 0x08, 0x04, 0x00, 0x00 };   // RX_SERIAL | TELEMETRY, LE
    // Blind by nature (a silent FC answers nothing), so no ACK waits — but
    // the gaps between the three frames keep the channel stream flowing
    // rather than sitting in delay() (0.9.563).
    auto pump = [](uint32_t ms) {
        for (uint32_t t0 = millis(); (uint32_t)(millis() - t0) < ms; ) { keepLinkTick(); delay(1); }
    };
    mspSendRequest(MSP_SET_FEATURE_CFG, mask, 4);
    pump(60);
    mspSendRequest(MSP_EEPROM_WRITE);
    pump(120);
    mspSendRequest(MSP_REBOOT);
    events.add("FC wake sent (telemetry on + save + reboot)");
    server.send(200, "application/json",
        "{\"ok\":true,\"message\":\"wake sent — watch for the Rotorflight button in ~10 s\"}");
}

// The gates every FC-restarting telemetry action shares: CRSF, a Rotorflight
// 2.3 FC answering, no transmitter talking (the restart would happen under
// a live model), no ESC catcher waiting. Sends the refusal itself.
inline bool fcTelemActionAllowed() {
    if (currentProtocol != PROTO_CRSF) {
        server.send(409, "application/json", "{\"ok\":false,\"err\":\"protocol is not CRSF\"}");
        return false;
    }
    if (dongleEnabled) {   // the sensor list belongs to the receiver that flies the model, not to a dongle
        server.send(409, "application/json", "{\"ok\":false,\"err\":\"not from a dongle: the telemetry sensors belong to the receiver that flies this model\"}");
        return false;
    }
    if (!fcInfo.detected || strncmp(fcInfo.variant, "RTFL", 4) != 0 ||
        (fcInfo.apiMajor * 100 + fcInfo.apiMinor) < 1209) {
        server.send(409, "application/json",
            "{\"ok\":false,\"err\":\"needs a Rotorflight 2.3 flight controller answering\"}");
        return false;
    }
    const bool txLive = rx.lastMillis && (uint32_t)(millis() - rx.lastMillis) < 3000;
    if (txLive) {
        server.send(409, "application/json",
            "{\"ok\":false,\"err\":\"turn the transmitter off first - the flight controller restarts to apply this\"}");
        return false;
    }
    if (escCatchArmed) {
        server.send(409, "application/json",
            "{\"ok\":false,\"err\":\"the ESC settings page is waiting for a power-up - finish or cancel that first\"}");
        return false;
    }
    return true;
}

// POST /api/fc/telemetry/restore — put Rotorflight's telemetry setup back
// (Goblin 770, 2026-09-03: the FC's sensor list and link rate were found
// all-zero after a bank copy — cause unknown — so the transmitter showed
// no volts and no RPM while every config page worked). Writes MSP 74 with
// the last good image the receiver cached (else Rotorflight's native mode
// and the seven native CRSF sensors the first-time page ticks) at the
// chosen telemetry speed, saves, and restarts the FC (sensors only apply
// at boot). Each step waits for the FC's answer (0.9.563 — the old
// fire-and-forget with delay() could lose a frame and restart an unsaved
// FC). Bench-only, see fcTelemActionAllowed.
inline void handleFcTelemRestore() {
    if (!fcTelemActionAllowed()) return;
    uint8_t cfg[52];
    const bool fast = fcInfo.telemSpeedPref != 0;
    telemBuildImage(cfg, fast);
    const bool fromCache = fcInfo.telemGoodValid;
    if (!telemWriteSync(cfg)) {
        server.send(504, "application/json",
            "{\"ok\":false,\"err\":\"the flight controller did not take the telemetry setup - nothing saved, try again\"}");
        return;
    }
    if (!telemSaveAndRestartSync()) {
        server.send(504, "application/json",
            "{\"ok\":false,\"err\":\"the flight controller did not confirm the save - not restarted, try again\"}");
        return;
    }
    telemRememberGood(cfg, 52);
    uint8_t n = 0;
    for (uint8_t i = 12; i < 52; i++) if (cfg[i]) n++;
    char m[EventLog::MSG_LEN];
    snprintf(m, sizeof(m), "Rotorflight telemetry setup restored (%u sensors%s, %s speed) - FC restarting",
             n, fromCache ? " from the cached copy" : "", fast ? "fast" : "standard");
    events.add(m);
    server.send(200, "application/json",
        "{\"ok\":true,\"message\":\"telemetry sensors restored - the flight controller is restarting; volts and RPM should be back in ~10 s\"}");
}

// GET /api/banks.json — {"pid":6,"rate":6,"shown":0}. Deliberately tiny:
// every tuning page needs these three numbers to draw its bank row, and
// /api/state.json is 4.4 kB, which over Bluetooth is a visible pause.
inline void handleBanksJson() {
    String j = "{\"pid\":";  j += (int)banks.pidCount;
    j += ",\"rate\":";       j += (int)banks.rateCount;
    j += ",\"shown\":";      j += (int)fcInfo.banksShown;
    j += ",\"fc\":";         j += (fcInfo.detected ? "true" : "false"); j += "}";
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", j);
}

// POST /api/fc/banks?show=N — how many tuning banks the pages offer
// (0.9.742). N = 0 means every bank this flight controller has; 1..6 shows
// only that many, for a pilot who uses fewer. Purely a display preference
// kept on the receiver so it follows the model from phone to phone: it
// writes NOTHING to the flight controller and changes nothing in the air.
// Still gated like any other setting — it is a flash write, and flash
// writes never happen near flight.
inline void handleFcBanksShown() {
    if (refuseIfArmed("bank count")) return;
    // A flash write, so like every other setting: not under a live link
    // (0.9.756 pre-flight review - it was the one config write without this).
    if (refuseIfTxLinked("turn the transmitter off first - this setting is saved to flash")) return;
    if (dongleEnabled && !dongleDisarmedConfirmed()) {
        server.sendHeader("Cache-Control", "no-store");
        server.send(409, "application/json",
                    "{\"ok\":false,\"message\":\"the flight controller has not confirmed it is disarmed\"}");
        return;
    }
    if (!server.hasArg("show")) {
        server.send(400, "application/json", "{\"ok\":false,\"err\":\"show=0..6 required\"}");
        return;
    }
    const long n = server.arg("show").toInt();
    if (n < 0 || n > 6) {
        server.send(400, "application/json", "{\"ok\":false,\"err\":\"show must be 0 (all) to 6\"}");
        return;
    }
    if (fcInfo.banksShown != (uint8_t)n) {
        fcInfo.banksShown = (uint8_t)n;
        prefs.putUChar(NVS_KEY_BANKS_SHOWN, fcInfo.banksShown);
        char e[64];
        snprintf(e, sizeof(e), "Banks shown: %s", n ? String((int)n).c_str() : "all");
        events.add(e);
    }
    server.sendHeader("Cache-Control", "no-store");
    String j = "{\"ok\":true,\"banks_shown\":"; j += (int)fcInfo.banksShown;
    j += ",\"pid_banks\":";  j += (int)banks.pidCount;
    j += ",\"rate_banks\":"; j += (int)banks.rateCount; j += "}";
    server.send(200, "application/json", j);
}

// POST /api/fc/telemetry/speed?mode=fast|standard — the receiver's
// Telemetry speed setting (0.9.563). Remembered in NVS (default fast) and
// applied to the FC now when the gates allow: read-modify-write of the
// link rate/ratio only, save, restart. When the FC cannot be touched
// right now (transmitter on, no FC), the preference is still saved and
// the page shows "apply" until the FC matches it. Reply: ok, applied
// (the FC is restarting with it), message.
inline void handleFcTelemSpeed() {
    const String mode = server.hasArg("mode") ? server.arg("mode") : String("");
    if (mode != "fast" && mode != "standard") {
        server.send(400, "application/json", "{\"ok\":false,\"err\":\"mode must be fast or standard\"}");
        return;
    }
    const bool fast = (mode == "fast");
    if (dongleEnabled) {      // 0.9.602: the link speed belongs to the receiver that flies the model
        server.sendHeader("Cache-Control", "no-store");
        server.send(403, "application/json", "{\"ok\":false,\"message\":\"not from a dongle - the telemetry link speed belongs to the receiver that flies this model\"}");
        return;
    }
    if ((fcInfo.telemSpeedPref != 0) != fast) {
        fcInfo.telemSpeedPref = fast ? 1 : 0;
        prefs.putUChar(NVS_KEY_FC_TELEM_SPEED, fcInfo.telemSpeedPref);   // on the ground: a page request
        events.add(fast ? "Telemetry speed preference: FAST (1000/1)" : "Telemetry speed preference: standard (250/8)");
    }
    if (!fcTelemActionAllowed()) return;      // preference kept; the 409 says why it was not applied
    char msg[160];
    bool changed = false;
    const bool ok = telemApplySpeedSync(fast, &changed, msg, sizeof(msg));
    String j = "{\"ok\":"; j += ok ? "true" : "false";
    j += ",\"applied\":"; j += (ok && changed) ? "true" : "false";
    j += ",\"message\":\""; j += msg; j += "\"}";
    server.send(ok ? 200 : 504, "application/json", j);
}

// Arm the one-shot Scorpion catcher for the next boot (see escCatchTick in
// MspFc.h). The page calls this right before telling the user to pull the
// battery; GET reports whether the last catch worked so the page can say
// "settings captured" the moment it reconnects.
// POST /api/esc/catch          → arm for the next power-on
// POST /api/esc/catch?arm=0    → cancel (page's "Cancel" on the battery card)
// POST /api/esc/catch?got=0    → forget "FC holds the settings" (the page sends
//                                this after Release: the FC reboots, cache gone)
inline void handleEscCatchArm() {
    if (server.hasArg("got") && server.arg("got") == "0") {
        escCatchGot = false;
        escCatchResult = "none";
    }
    if (server.hasArg("got") && !server.hasArg("arm")) {
        server.sendHeader("Cache-Control", "no-store");
        server.send(200, "application/json", "{\"ok\":true}");
        return;
    }
    const bool arm = !(server.hasArg("arm") && server.arg("arm") == "0");
    prefs.putUChar(NVS_KEY_ESC_CATCH, arm ? 1 : 0);
    if (!arm) { escCatchArmed = false; escCatchResult = "cancelled"; }
    else {
        // A fresh catch starts clean: a "FC holds the settings" flag left
        // over from an earlier session (FC rebooted without Release) would
        // otherwise make the page read 217 before the battery restart.
        escCatchResult = "none";
        escCatchGot = false;
    }
    events.add(arm ? "ESC catcher armed for next power-on" : "ESC catcher cancelled");
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", "{\"ok\":true}");
}

// pending = the NVS flag (survives software reboots; consumed by a power-on),
// armed/got = this boot's live state, result = how the last catch ended
// (captured | nothing | tx | cancelled | none), poweron = this boot restarted
// the ESC too (a software restart leaves the ESC's listen window untouched).
inline void handleEscCatchStatus() {
    char buf[160];
    const bool pending = prefs.isKey(NVS_KEY_ESC_CATCH) && prefs.getUChar(NVS_KEY_ESC_CATCH, 0);
    const esp_reset_reason_t rr = esp_reset_reason();
    const bool poweron = (rr == ESP_RST_POWERON || rr == ESP_RST_BROWNOUT || rr == ESP_RST_UNKNOWN);
    snprintf(buf, sizeof(buf),
             "{\"armed\":%s,\"got\":%s,\"pending\":%s,\"uptime_ms\":%lu,\"result\":\"%s\",\"poweron\":%s}",
             escCatchArmed ? "true" : "false", escCatchGot ? "true" : "false",
             pending ? "true" : "false", (unsigned long)millis(), escCatchResult,
             poweron ? "true" : "false");
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", buf);
}

inline void handleWizardJpg() {
    if (serveLittleFsFile("/wizard.jpg", "image/jpeg")) return;
    server.send(404, "text/plain", "/wizard.jpg missing");
}

inline void handleRotorflightEsc() {
    if (serveLittleFsFile("/rotorflight-esc.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-esc.html missing — uploadfs the data/ folder");
}

// Gear ratio — edits the FC's own main/tail ratio (MSP 131/222) via gear.js.
// The page existed in data/ since 0.9.5xx but never had a route: the
// à-la-carte link 404'd on the receiver (found 2026-09-02, the Goblin's
// backwards-ratio day).
inline void handleRotorflightGear() {
    if (serveLittleFsFile("/rotorflight-gear.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-gear.html missing — uploadfs the data/ folder");
}

// Flight recorder — Rotorflight's onboard Blackbox (MSP 70/72/80/81) in
// plain English: when/where/how often to log, which fields, flash usage and
// erase. Last wizard step before "blades on" (Malcolm 2026-09-03).
inline void handleRotorflightBlackbox() {
    if (serveLittleFsFile("/rotorflight-blackbox.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-blackbox.html missing — uploadfs the data/ folder");
}

inline void handleGearJs() {
    if (serveLittleFsFile("/gear.js", "application/javascript")) return;
    server.send(503, "text/plain", "/gear.js not in LittleFS — uploadfs the data/ folder");
}

inline void handleRotorflightComputer() {
    if (serveLittleFsFile("/rotorflight-computer.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-computer.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightWiring() {
    if (serveLittleFsFile("/rotorflight-wiring.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-wiring.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightWizards() {
    if (serveLittleFsFile("/rotorflight-wizards.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-wizards.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightAlaCarte() {
    if (serveLittleFsFile("/rotorflight-alacarte.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-alacarte.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightBackupPage() {
    if (serveLittleFsFile("/rotorflight-backup.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-backup.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightEasy() {
    if (serveLittleFsFile("/rotorflight-easy.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-easy.html missing — uploadfs the data/ folder");
}
// "Find a setting" (Malcolm 2026-09-07): the page and its index, built from
// the pages by dev/build_search_index.py.
inline void handleSearchPage() {
    if (serveLittleFsFile("/search.html", "text/html")) return;
    server.send(503, "text/plain", "/search.html missing — uploadfs the data/ folder");
}
inline void handleSearchJs() {
    if (serveLittleFsFile("/search.js", "application/javascript")) return;
    server.send(503, "text/plain", "/search.js missing — run dev/build_search_index.py and uploadfs");
}

inline void handleRotorflightCopyBank() {
    if (serveLittleFsFile("/rotorflight-copybank.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-copybank.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightTxChannels() {
    if (serveLittleFsFile("/rotorflight-txchannels.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-txchannels.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightTuning() {
    if (serveLittleFsFile("/rotorflight-tuning.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-tuning.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightRescue() {
    if (serveLittleFsFile("/rotorflight-rescue.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-rescue.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightServos() {
    if (serveLittleFsFile("/rotorflight-servos.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-servos.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightRates() {
    if (serveLittleFsFile("/rotorflight-rates.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-rates.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightEscProg() {
    if (serveLittleFsFile("/rotorflight-escprog.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-escprog.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightGovProfile() {
    if (serveLittleFsFile("/rotorflight-gov-profile.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-gov-profile.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightGovGlobal() {
    if (serveLittleFsFile("/rotorflight-gov-global.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-gov-global.html missing — uploadfs the data/ folder");
}

// Travel extents (Malcolm 2026-08-14, after Black Thunder II's first flight):
// RF 2.3 mixer limits — collective/cyclic/total swash pitch, swash trims,
// tail travel — editable over the link. Spec: TRAVEL-EXTENTS-MSP-SPEC.md.
inline void handleRotorflightTravel() {
    if (serveLittleFsFile("/rotorflight-travel.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-travel.html missing — uploadfs the data/ folder");
}

// The receiver-side named-backups PAGE retired 2026-08-06 (Malcolm: one
// backup system — the app's phone backup/restore). The /api/backup*
// endpoints below survive: dev tooling (preserve_backups.py) uses them.
inline void handleRotorflightBackups() {
    server.sendHeader("Location", "/rotorflight");
    server.send(303, "text/plain", "moved");
}

//*********************************************************************
//  Backups — JSON snapshots of every editable Rotorflight parameter
//*********************************************************************
// Stored at /backups/<name>.json on LittleFS. Each file ~1.5 KB. The JS
// page owns the snapshot format; the chip is just a key/value store.
// Backup names: alnum, '-', '_', '.', max 32 chars. Hard cap 20 files.

constexpr const char* BACKUP_DIR = "/backups";
constexpr uint8_t     BACKUP_MAX = 20;

inline bool backupNameOk(const String& n) {
    if (n.length() == 0 || n.length() > 32) return false;
    for (size_t i = 0; i < n.length(); i++) {
        char c = n[i];
        bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                  (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.';
        if (!ok) return false;
    }
    return true;
}

inline String backupPath(const String& name) {
    String p = BACKUP_DIR;
    p += '/'; p += name; p += ".json";
    return p;
}

// GET /api/backup/list  → JSON: {"names":[...], "max":20, "free_bytes":N}
inline void handleBackupList() {
    if (!littleFsMounted) { server.send(500, "text/plain", "FS not mounted"); return; }
    if (!LittleFS.exists(BACKUP_DIR)) LittleFS.mkdir(BACKUP_DIR);
    File dir = LittleFS.open(BACKUP_DIR);
    String j = "{\"names\":[";
    bool first = true;
    if (dir) {
        File f = dir.openNextFile();
        while (f) {
            String n = f.name();
            // Strip directory path + ".json" suffix
            int slash = n.lastIndexOf('/');
            if (slash >= 0) n = n.substring(slash + 1);
            if (n.endsWith(".json")) n = n.substring(0, n.length() - 5);
            if (!first) j += ',';
            j += '"'; j += n; j += "\"";
            first = false;
            f.close();
            f = dir.openNextFile();
        }
        dir.close();
    }
    j += "],\"max\":"; j += BACKUP_MAX;
    j += ",\"free_bytes\":"; j += (uint32_t)(LittleFS.totalBytes() - LittleFS.usedBytes());
    j += "}";
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", j);
}

// GET /api/backup/load?name=X  → the JSON file's raw content
inline void handleBackupLoad() {
    if (!server.hasArg("name")) { server.send(400, "text/plain", "missing name"); return; }
    String name = server.arg("name");
    if (!backupNameOk(name)) { server.send(400, "text/plain", "bad name"); return; }
    String path = backupPath(name);
    if (!LittleFS.exists(path)) { server.send(404, "text/plain", "no such backup"); return; }
    File f = LittleFS.open(path, "r");
    if (!f) { server.send(500, "text/plain", "open failed"); return; }
    server.sendHeader("Cache-Control", "no-store");
    server.streamFile(f, "application/json");
    f.close();
}

// POST /api/backup/save?name=X  with JSON body  → 200 ok / 4xx error
inline void handleBackupSave() {
    if (!server.hasArg("name"))  { server.send(400, "text/plain", "missing name"); return; }
    if (!server.hasArg("plain")) { server.send(400, "text/plain", "missing body"); return; }
    String name = server.arg("name");
    if (!backupNameOk(name)) { server.send(400, "text/plain", "bad name"); return; }
    // A real full backup is ~4 kB of JSON; anything much bigger is a runaway
    // client. Cap it so a bad POST can't fill LittleFS (which would then make
    // flight-log saves fail too).
    if (server.arg("plain").length() > 16384) { server.send(413, "text/plain", "backup too large (max 16 kB)"); return; }
    if (!LittleFS.exists(BACKUP_DIR)) LittleFS.mkdir(BACKUP_DIR);
    // Enforce hard cap. Allow overwrite of an existing name without counting it.
    String path = backupPath(name);
    bool replacing = LittleFS.exists(path);
    if (!replacing) {
        uint8_t count = 0;
        File dir = LittleFS.open(BACKUP_DIR);
        if (dir) {
            File f = dir.openNextFile();
            while (f) { count++; f.close(); f = dir.openNextFile(); }
            dir.close();
        }
        if (count >= BACKUP_MAX) {
            server.send(507, "text/plain", "backup limit reached — delete one first");
            return;
        }
    }
    File f = LittleFS.open(path, "w");
    if (!f) { server.send(500, "text/plain", "open for write failed"); return; }
    String body = server.arg("plain");
    f.print(body);
    f.close();
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "text/plain", "saved");
}

// POST /api/backup/delete?name=X
inline void handleBackupDelete() {
    if (!server.hasArg("name")) { server.send(400, "text/plain", "missing name"); return; }
    String name = server.arg("name");
    if (!backupNameOk(name)) { server.send(400, "text/plain", "bad name"); return; }
    String path = backupPath(name);
    if (!LittleFS.exists(path)) { server.send(404, "text/plain", "no such backup"); return; }
    if (!LittleFS.remove(path)) { server.send(500, "text/plain", "remove failed"); return; }
    server.send(200, "text/plain", "deleted");
}

//*********************************************************************
//  GET /api/msp?fn=N[&data=HEX]  — synchronous MSP request to the FC
//*********************************************************************
// Returns the response payload as a hex string. Empty body on no-data
// success. 504 if the FC doesn't reply within ~500 ms.

inline uint8_t hexNibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return 10 + (c - 'a');
    if (c >= 'A' && c <= 'F') return 10 + (c - 'A');
    return 0xFF;
}

// The Rotorflight SET commands that change the model's setup (the phone
// backup restores exactly these) — the proven-tune counter's definition of
// "an edit". 218 = ESC parameters (not in the backup, still an edit).
inline bool isSetupWriteFn(uint8_t fn) {
    switch (fn) {
        case 11:  case 33:  case 35:  case 37:  case 39:  case 41:  case 43:  case 45:
        case 51:  case 53:  case 57:  case 62:  case 65:  case 67:  case 74:  case 76:
        case 78:  case 81:  case 93:  case 95:  case 97:  case 143: case 147: case 149:
        case 155: case 171: case 173: case 202: case 204: case 212: case 216: case 218:
        case 220: case 222: case 239:
            return true;
        default:
            return false;
    }
}

inline void handleMspApi() {
    // ARMED = configuration locked, instantly (Malcolm 2026-08-24, after the
    // crash: "if arming is switched on, go directly to fly mode — without
    // passing Go"). A blocking MSP wait while flying starves the CRSF stream
    // and Rotorflight cuts the motor as failsafe. Auto fly mode kills the
    // radios ~3 s after arming; this closes the door for those 3 seconds
    // and for every other path: no config request touches the FC while the
    // model is armed with a live transmitter.
    {
        if (fcInfo.armed && fcInfo.armedMs && (uint32_t)(millis() - fcInfo.armedMs) < 5000) {   // the FC's own word, dongle or receiver (0.9.640)
            server.sendHeader("Cache-Control", "no-store");
            server.send(409, "text/plain", "ARMED - the flight controller says it is armed. Disarm first.");
            return;
        }
        const bool armLink = rx.lastMillis &&
                             (uint32_t)(millis() - rx.lastMillis) < 1000;
        if (armLink && armingChannel >= 1 && armingChannel <= 16 &&
            channelMicros[armingChannel - 1] > 1500) {
            static uint32_t lastArmRefuseLog = 0;
            if ((uint32_t)(millis() - lastArmRefuseLog) > 10000) {
                lastArmRefuseLog = millis();
                events.add("Config refused: model is ARMED");
            }
            server.sendHeader("Cache-Control", "no-store");
            server.send(409, "text/plain", "ARMED - configuration is locked in flight. Disarm first.");
            return;
        }
    }
    if (bbCheckActive) {                       // the vibration check is streaming the black box (0.9.661): one request at a time at the FC
        server.sendHeader("Cache-Control", "no-store");
        server.send(503, "text/plain", "busy: the vibration check is reading the black box - wait for it to finish, or cancel it on its page");
        return;
    }
    if (!server.hasArg("fn")) { server.send(400, "text/plain", "missing fn"); return; }
    uint8_t fn = (uint8_t)server.arg("fn").toInt();

    uint8_t reqBuf[128] = {0};
    uint8_t reqLen = 0;
    if (server.hasArg("data")) {
        String h = server.arg("data");
        if (h.length() % 2 != 0) { server.send(400, "text/plain", "data length odd"); return; }
        if (h.length() / 2 > sizeof(reqBuf)) { server.send(400, "text/plain", "data too long"); return; }
        for (size_t i = 0; i + 1 < h.length(); i += 2) {
            uint8_t hi = hexNibble(h[i]);
            uint8_t lo = hexNibble(h[i + 1]);
            if (hi == 0xFF || lo == 0xFF) { server.send(400, "text/plain", "bad hex"); return; }
            reqBuf[reqLen++] = (uint8_t)((hi << 4) | lo);
        }
    }
    // Requests the flight controller must never see (0.9.564, MspFc.h):
    //  - 52, the adjustments list: its 588-byte reply overflows the FC's
    //    320-byte link buffer and wipes the telemetry setup (RF 4.6 bug —
    //    the "no volts/RPM after a save" mystery);
    //  - a SET with no payload: the FC applies stale bytes from its buffer;
    //  - factory reset and motor test: never over the link, never from a phone.
    {
        const char* why = nullptr;
        if (mspReplyTooBigForFc(fn))
            why = "refused: Rotorflight 4.6 cannot send its adjustments list over the receiver link without "
                  "overwriting its own telemetry setup (588-byte reply, 320-byte buffer). Plug the flight controller's USB into the dongle or receiver";
        else if (fn == MSP_RESET_CONF && !UsbHostMsp::active()) why = "refused: factory reset needs the USB connection to the flight controller";
        else if (!dongleEnabled && !UsbHostMsp::active() && (currentProtocol != PROTO_CRSF || !fcTelemetryEnabled)) why = "needs the USB cable: this receiver's line to the flight controller carries no Rotorflight settings (not CRSF, or FC telemetry off)";
        else if (UsbHostMsp::cliMode) {
            // Left open and forgotten (Malcolm: "I frequently forget to press
            // exit"). 2026-09-17 it cost a whole backup - every read refused -
            // and then a reboot with the FC still in its command line, which
            // came back deaf. A page asking for MSP is the pilot having moved
            // on: if nobody has typed for 10 s, leave the command line for
            // them (without saving, exactly as the Leave button does). The FC
            // restarts on exit, so THIS request still fails - honestly.
            const bool idle = (uint32_t)(millis() - UsbHostMsp::cliTouchedMs) > 10000;
            const bool safe = !rxTxLinkedRecently() && !(fcInfo.armed && fcInfo.armedMs && (uint32_t)(millis() - fcInfo.armedMs) < 5000);
            if (idle && safe) {
                UsbHostMsp::cliLeave(false);
                why = "refused: the command line had been left open - it has been exited for you (no save); the flight controller is restarting, try again in a few seconds";
            } else {
                why = "refused: the command line is open - save or exit it first";
            }
        }
        else if (fn == MSP_SET_MOTOR)  why = "refused: motor test is never done from a phone";
        else if (reqLen == 0 && mspSetNeedsPayload(fn)) why = "refused: that is a write and it came with no data";
        if (why) {
            char m[EventLog::MSG_LEN];
            snprintf(m, sizeof(m), "MSP %u REFUSED (%u B): %.60s", fn, reqLen, why + 9);
            events.add(m);
            server.sendHeader("Cache-Control", "no-store");
            server.send(409, "text/plain", why);
            return;
        }
    }
    // Belt and braces for the 0.9.580 field fix: a phone request while the
    // FC UART is parked for failsafe re-attaches it first, whatever parked it.
    if (outputDetachedForFailsafe) {
        configureOutputDriver(currentProtocol);
        outputDetachedForFailsafe = false;
        events.add("DIAG CRSF-REATTACH for a phone request (UART was parked for failsafe)");
    }
    // Yield to the TX-param state machine first. It runs a multi-step MSP
    // transaction (GET → SET → EEPROM_WRITE); barging in mid-cycle puts two
    // outstanding requests on the FC (mutual timeouts), and a web SET landing
    // between the TX's GET and SET would be overwritten by the TX's stale
    // scratch and EEPROM-saved. TxParams yields to the web (txParamMspFree);
    // this is the missing other half of that mutex. Pump the machine to
    // completion (worst cycle ~250 ms); if it stays busy, the FC is wedged.
    {
        uint32_t busyDeadline = millis() + 300;
        while (txParamBusy && (int32_t)(busyDeadline - millis()) > 0) {
            radioPoll();        // keep channels fresh
            sbusTick();         // keep frames flowing to the FC (no failsafe flicker)
            protocolRx();       // feed CRSF RX so the async response can land
            txParamsLoop();     // advance the TX-param machine
            delay(1);
        }
        if (txParamBusy) {
            server.send(503, "text/plain", "receiver busy with a transmitter edit — try again");
            return;
        }
    }

    // NOBODY IS ANSWERING — say so at once (Malcolm 2026-09-16, Test1 with
    // the FC's port switched off: every read waited 1.2 s for the bank
    // bookkeeping below plus 1.2 s for itself, so the page sat on "Reading
    // from the flight controller… 8 s" while the receiver had known for
    // thirteen minutes that 785 probes had gone unanswered). fcInfo.detected
    // is false until the FC's first reply and drops after 10 s of silence;
    // the probesSent floor keeps a page opened in the first seconds after
    // boot from being refused before the receiver has even asked.
    if (!fcInfo.detected && fcInfo.probesSent >= 3) {
        server.sendHeader("Cache-Control", "no-store");
        if (UsbHostMsp::usbSilent) {   // 0.9.751: the cable is fine - the FC's USB came back deaf from a restart
            server.send(503, "text/plain", "The flight controller's USB stopped answering after the restart. Power the model off and on to bring it back.");
            return;
        }
        server.send(503, "text/plain", dongleEnabled
            ? "No flight controller is answering. Check it is powered, and that its port is set to MSP (dongle on a wire) or the USB cable is in."
            : "No flight controller is answering. Check it is powered, and that its port is set to serial receiver with telemetry on, or the USB cable is in.");
        return;
    }

    // On a dongle, a write, a save or a restart needs the flight controller's
    // FRESH "disarmed" word — silence is not consent (2026-09-16 review).
    if (dongleEnabled && fcInfo.detected && !dongleDisarmedConfirmed() &&
        ((reqLen > 0 && isSetupWriteFn(fn)) || fn == MSP_EEPROM_WRITE || fn == MSP_REBOOT)) {
        server.sendHeader("Cache-Control", "no-store");
        server.send(409, "text/plain", "Flight controller state unknown - it has not answered in the last few seconds. Try again.");
        return;
    }

    // Bank bookkeeping (0.9.567): note the switch's banks before a page's
    // first select, re-select the page's bank after a put-back. MspFc.h.
    bankBeforeClientRequest(fn, reqBuf, reqLen);

    // Telemetry setup guards (0.9.563). The FC's sensor list was found
    // empty twice (2026-09-03/04, cause unknown); the next save would have
    // carried it into flash. After the yield above — each guard is its own
    // MSP exchange.
    if (fn == MSP_SET_TELEMETRY_CONFIG) {
        // An image that would empty the FC's list is the fault itself.
        if (reqLen < 52 || !telemImageGood(reqBuf, reqLen)) {
            char m[EventLog::MSG_LEN];
            snprintf(m, sizeof(m), "MSP 74 REFUSED from a page: %u bytes, %s", reqLen,
                     reqLen < 52 ? "short" : "no sensors or zero link rate");
            events.add(m);
            server.sendHeader("Cache-Control", "no-store");
            server.send(409, "text/plain", "refused: that telemetry setup would leave the flight controller with no sensors (no volts, no RPM)");
            return;
        }
        // The link speed (bytes 8-11) belongs to the receiver's Telemetry
        // speed setting, not to a backup: keep the FC's live values so a
        // Restore of a backup taken at the old speed cannot drag it back.
        if (!fcInfo.telemCfgKnown || fcTelemCfgBad()) { uint8_t live[52]; telemReadSync(live); }   // fresh look first
        if (fcInfo.telemCfgKnown && !fcTelemCfgBad()) {
            reqBuf[8]  = (uint8_t)fcInfo.telemRate;  reqBuf[9]  = (uint8_t)(fcInfo.telemRate >> 8);
            reqBuf[10] = (uint8_t)fcInfo.telemRatio; reqBuf[11] = (uint8_t)(fcInfo.telemRatio >> 8);
        }
        // Who writes the telemetry setup? Logged with its header so the next
        // "all zeros" has a suspect; the FC's copy changes, so the watch
        // re-reads it.
        char m[EventLog::MSG_LEN];
        snprintf(m, sizeof(m), "MSP 74 from a page: %u B, hdr %02X%02X..%02X %02X %02X%02X %02X%02X",
                 reqLen, reqBuf[0], reqBuf[1], reqBuf[6], reqBuf[7], reqBuf[8], reqBuf[9], reqBuf[10], reqBuf[11]);
        events.add(m);
        fcInfo.telemCfgKnown = false;
        fcInfo.telemCfgTries = 0;
        fcInfo.telemRecheck  = true;
    }
    if (fn == MSP_EEPROM_WRITE) {
        // Never let a save carry the empty setup into flash: fresh read, put
        // the cached good copy back if needed, refuse only when nothing can.
        if (telemGuardBeforeSave("page save") == 1) {
            server.sendHeader("Cache-Control", "no-store");
            server.send(409, "text/plain", "not saved: the flight controller's telemetry setup is empty - restore telemetry sensors on the Rotorflight page first");
            return;
        }
    }
    if (fn == MSP_REBOOT) {
        // The FC never answers 68 — fire twice with the channels kept
        // flowing (a lost single frame once left a saved setup silently not
        // yet active), and answer the page at once instead of a 504.
        mspSendRequest(MSP_REBOOT);
        for (uint32_t t0 = millis(); (uint32_t)(millis() - t0) < 100; ) { keepLinkTick(); delay(1); }
        mspSendRequest(MSP_REBOOT);
        fcInfo.telemCfgKnown = false;      // re-read once the FC is back
        fcInfo.telemCfgTries = 0;
        fcInfo.telemRecheck  = true;
        events.add("Flight controller restart asked for by a page");
        server.sendHeader("Cache-Control", "no-store");
        server.send(200, "text/plain", "");
        return;
    }

    uint8_t  respBuf[640];   // jumbo-capable
    uint16_t respLen = 0;
    // 400 ms timeout: was 150 ms but read-failed too often. FC normally
    // responds in <50 ms, but if a periodic mspFcPoll probe queued behind
    // our request, the FC processes it first and ours can take longer.
    // (mspFcPoll is now blocked while a sync wait is in flight, but this
    // also handles the case where the user starts a new wait while a
    // probe response is mid-flight on the wire.)
    // 1200 ms: a CHUNKED response (e.g. servo config, 65 B over multiple
    // CRSF frames) needs several telemetry frame slots — 400 ms cut it off
    // mid-reassembly (2026-08-19, first fn-120 read).
    bool ok = mspRequestAndWait(fn, reqBuf, reqLen, respBuf, &respLen, 1200);
    bankAfterClientRequest(fn, reqBuf, reqLen, ok);
    if (!ok) {
        if (mspWaitRespError) { server.send(502, "text/plain", "flight controller rejected fn " + String(fn)); return; }
        server.send(504, "text/plain", "flight controller did not respond within 1200 ms"); return;
    }
    // Proven-tune tracking: any successful SETUP write — every Rotorflight
    // SET the phone backup covers, plus the ESC's own parameters — starts
    // a new tune generation at once (Malcolm 2026-09-04: "clear the flag
    // if any edit is made to the set up"). Not a bank select (210), EEPROM
    // save (250), reboot (68) or a read that carries its index in data=.
    if (reqLen > 0 && isSetupWriteFn(fn)) tuneNoteEdit(true);   // armed → refused above, so we are on the ground

    String s;
    s.reserve(respLen * 2 + 4);
    char tmp[4];
    for (uint16_t i = 0; i < respLen; ++i) {
        snprintf(tmp, sizeof(tmp), "%02X", respBuf[i]);
        s += tmp;
    }
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "text/plain", s);
}

//*********************************************************************
//  POST /api/firmware/seturl — store manifest URL in NVS
//*********************************************************************

//*********************************************************************
//  POST /api/time — the phone/browser tells us the wall clock
//*********************************************************************
// The receiver has no RTC, but every page load posts the phone's Date.now()
// here — so flights get real dates, including ones saved earlier this
// power-up (patched retroactively).
//*********************************************************************
//  POST /api/gapmin — lateness threshold for the gap statistics
//*********************************************************************
// A packet must be at least this many ms LATER than the measured spacing
// to count as a gap (Malcolm 2026-07-27: normal 2 ms intervals are not
// gaps; buddy-box 4 ms self-calibrates via linkStats.expectedGapUs).
//*********************************************************************
//  POST /api/flight/delete?i=<1..20> — delete the saved flight in view
//*********************************************************************
// Malcolm 2026-08-01: with 20 slots the diary collects brief boring tests
// too — let the user prune them. Ring stays consistent: a deleted slot is
// simply skipped by the listing, and the head is untouched.
inline void handleFlightDelete() {
    // Prefer the STABLE physical slot (Malcolm 2026-08-04: quick successive
    // deletions over BLE shifted the logical numbering under the page — one
    // flight seemed "reluctant" because the delete aimed at a hole). Logical
    // `i` kept for old pages.
    long physArg = server.hasArg("phys") ? server.arg("phys").toInt() : -1;
    long i = server.hasArg("i") ? server.arg("i").toInt() : 0;
    if (!littleFsMounted ||
        (physArg < 0 && (i < 1 || i > FLIGHT_KEEP)) ||
        (physArg >= 0 && physArg >= FLIGHT_KEEP)) {
        server.send(400, "text/plain", "bad flight index");
        return;
    }
    statsSelfStallUntilMs = millis() + 2000;   // flash op: stats look away
    const uint8_t phys = (physArg >= 0) ? (uint8_t)physArg : fltPhys((uint8_t)(i - 1));
    const bool existed = LittleFS.exists(flightPath(phys));
    if (existed) LittleFS.remove(flightPath(phys));
    fltPendingStampMs[phys] = 0;
    if (existed) events.add("Flight deleted from flash");
    server.send(200, "application/json", existed ? "{\"ok\":true}" : "{\"ok\":false}");
}

inline void handleGapMin() {
    if (server.hasArg("ms")) {
        long v = server.arg("ms").toInt();
        if (v < 1 || v > 100) { server.send(400, "text/plain", "1..100 ms"); return; }
        gapMinMs = (uint8_t)v;
        prefs.putUChar(NVS_KEY_GAP_MIN, gapMinMs);
        events.add("Gap threshold changed");
    }
    char b[48];
    snprintf(b, sizeof(b), "{\"ok\":true,\"gap_min_ms\":%u}", (unsigned)gapMinMs);
    server.send(200, "application/json", b);
}

inline void handleTimeSync() {
    if (!server.hasArg("epoch_ms")) { server.send(400, "text/plain", "missing epoch_ms"); return; }
    const int64_t epochMs = strtoll(server.arg("epoch_ms").c_str(), nullptr, 10);
    if (epochMs < 1600000000000LL) { server.send(400, "text/plain", "bad epoch_ms"); return; }
    epochOffsetMs = epochMs - (int64_t)millis();
    epochFromPhone = true;                 // phone outranks the TX clock this boot
    // The page also teaches us the phone's UTC offset. It converts the V1
    // TX's LOCAL wall-clock time (param ID 34) to UTC epoch, so field days
    // with no phone still stamp flights in the right timezone. Persisted —
    // the phone refreshes it each connect (DST changes heal themselves).
    if (server.hasArg("tz_min")) {
        int tz = server.arg("tz_min").toInt();
        if (tz >= -720 && tz <= 840 && tz != tzOffsetMin) {
            tzOffsetMin = (int16_t)tz;
            prefs.putShort(NVS_KEY_TZ_MIN, tzOffsetMin);
        }
    }
    patchFlightEpochs();
    server.send(200, "application/json", "{\"ok\":true}");
}

inline void handleFirmwareSetUrl() {
    if (!server.hasArg("url")) {
        server.send(400, "text/plain", "missing url");
        return;
    }
    String u = server.arg("url");
    u.trim();
    prefs.putString(NVS_KEY_FW_MANIFEST, u);
    events.add("Firmware manifest URL updated");
    server.send(200, "text/plain", "ok");
}

//*********************************************************************
//  Helpers shared by the auto-update endpoints
//*********************************************************************

inline bool isHttpsUrl(const String& u) {
    return u.startsWith("https://") || u.startsWith("HTTPS://");
}

// Pick the right WiFiClient implementation for `url`'s scheme so the
// same call works for both http:// (local dev server) and https://
// (messiter.com). setInsecure() skips CA verification — the .bin itself
// isn't signed today, so we wouldn't be earning end-to-end trust by
// pinning a CA bundle.
inline bool httpBeginAny(HTTPClient& http,
                         WiFiClient& plain,
                         WiFiClientSecure& secure,
                         const String& url) {
    if (isHttpsUrl(url)) {
        secure.setInsecure();
        secure.setHandshakeTimeout(20);   // default is 120 s — far too long for a blocked loop()
        return http.begin(secure, url);
    }
    return http.begin(plain, url);
}

// ---- Download guard (2026-09-02) -------------------------------------------
// The Goblin receiver went DEAF for 8 minutes mid-update: no TX, no app, no
// failsafe frames, HTTP connections reset — then it rebooted on its own with the
// update complete. Cause: every download here runs inside the HTTP handler with
// loop() blocked, and the framework never gives up — Update.writeStream retries a
// stalled stream 300× (≈75 min at our 15 s socket timeout) and getString() has no
// stall limit at all. Two layers now:
//   1) httpStreamBounded() copies the body itself and gives up after OTA_STALL_MS
//      without a byte (a partial firmware image is harmless — the OTA slot only
//      switches when Update.end() completes);
//   2) the loop task wears the task watchdog for the whole install — if anything
//      else wedges (DNS, handshake, LittleFS) the chip panics and reboots into the
//      firmware it already has, and the boot log says why (NVS_KEY_OTA_BUSY).
constexpr uint32_t OTA_WDT_S    = 60;      // > the longest single blocking call (TLS handshake 20 s + socket 15 s)
constexpr uint32_t OTA_STALL_MS = 25000;   // no bytes for this long = give up (≈2 socket timeouts)

inline void otaGuardBegin() {
    prefs.putUChar(NVS_KEY_OTA_BUSY, 1);
    esp_task_wdt_init(OTA_WDT_S, true);    // reconfigures the running TWDT (idle task on CPU0 stays subscribed)
    esp_task_wdt_add(NULL);
    esp_task_wdt_reset();
}
inline void otaGuardEnd() {
    esp_task_wdt_delete(NULL);
    esp_task_wdt_init(CONFIG_ESP_TASK_WDT_TIMEOUT_S, true);
    prefs.putUChar(NVS_KEY_OTA_BUSY, 0);
}

// Copy an open HTTP response body into `sink(buf, n)` (returns false to abort).
// `len` = Content-Length, or -1 to read until the server closes. Feeds the task
// watchdog every pass and returns "" on success or a short reason. NOTE: on a
// TLS stream available()/connected() each block up to the 15 s socket timeout
// when nothing arrives, so the stall is judged by wall clock, not by call count.
template <typename Sink>
inline String httpStreamBounded(HTTPClient& http, int len, Sink sink) {
    WiFiClient* s = http.getStreamPtr();
    if (!s) return "no stream";
    static uint8_t buf[2048];
    int got = 0;
    uint32_t lastData = millis();
    while (len < 0 || got < len) {
        esp_task_wdt_reset();
        int avail = s->available();
        if (avail <= 0) {
            if (!s->connected()) {
                if (len < 0) break;                       // unknown length: EOF is the end
                char m[48]; snprintf(m, sizeof m, "connection lost at %d/%d", got, len);
                return String(m);
            }
            if (millis() - lastData > OTA_STALL_MS) {
                char m[48]; snprintf(m, sizeof m, "download stalled at %d/%d", got, len);
                return String(m);
            }
            delay(10);
            continue;
        }
        int want = avail < (int)sizeof buf ? avail : (int)sizeof buf;
        if (len >= 0 && want > len - got) want = len - got;
        int n = s->read(buf, want);
        if (n <= 0) { delay(10); continue; }
        if (!sink(buf, (size_t)n)) return "write failed";
        got += n;
        lastData = millis();
    }
    return "";
}

// Fetch a manifest URL and append a `{"manifest_url":..., ...}` chunk
// to `out` describing the result. On success the manifest body is
// embedded verbatim under "manifest"; on failure an "error" string is
// included instead. Caller composes the surrounding JSON.
inline void fetchManifestInto(String& out, const String& url, uint32_t timeoutMs) {
    out += "{\"manifest_url\":\"";
    out += url;
    out += "\"";
    if (url.isEmpty()) {
        out += ",\"ok\":false,\"error\":\"no manifest URL configured\"}";
        return;
    }
    HTTPClient       http;
    WiFiClient       plain;
    WiFiClientSecure secure;
    http.setConnectTimeout(timeoutMs);
    http.setTimeout(timeoutMs);
    if (!httpBeginAny(http, plain, secure, url)) {
        out += ",\"ok\":false,\"error\":\"http.begin failed\"}";
        return;
    }
    int code = http.GET();
    if (code != HTTP_CODE_OK) {
        out += ",\"ok\":false,\"http_status\":";
        out += code;
        out += ",\"error\":\"manifest fetch failed\"}";
        http.end();
        return;
    }
    // Guard against an oversized manifest. Versions accumulate, and proxying two
    // full manifests (~95 entries each, with notes = 76 KB) choked the response —
    // blocking the single-threaded server and failing the check. Skip a manifest
    // that's still too big rather than try to build a giant JSON. (Keep manifests
    // trimmed to recent versions — see dev/stage_website.py / firmware_server.py.)
    // Bounded read (not getString(), which loops forever on a silent server) —
    // it stops at the cap, so an oversized manifest is refused without buffering it.
    constexpr size_t MANIFEST_MAX = 18000;
    String body;
    bool   tooBig = false;
    int    len    = http.getSize();
    if (len > (int)MANIFEST_MAX) tooBig = true;
    else {
        if (len > 0) body.reserve(len);
        String rerr = httpStreamBounded(http, len, [&](const uint8_t* b, size_t n) {
            if (body.length() + n > MANIFEST_MAX) { tooBig = true; return false; }
            body.concat((const char*)b, n);
            return true;
        });
        if (rerr.length() && !tooBig) {
            http.end();
            out += ",\"ok\":false,\"error\":\"manifest ";
            out += rerr;
            out += "\"}";
            return;
        }
    }
    http.end();
    if (tooBig) {
        out += ",\"ok\":false,\"error\":\"manifest too large (";
        out += len > 0 ? len : (int)body.length();
        out += " bytes); trim it to recent versions\"}";
        return;
    }
    out += ",\"ok\":true,\"manifest\":";
    out += body;
    out += "}";
}

//*********************************************************************
//  GET /api/firmware/check — fetch both local + public manifests
//*********************************************************************
// Single endpoint the page calls. Saves the page from having to know
// the messiter.com URL or from needing CORS access to either server —
// the chip is on the same origin as the page, so the page can always
// reach this. Returns:
//   {
//     "current": "RXV2-x.y.z-…",
//     "local":  { manifest_url, ok, manifest? | error },
//     "public": { manifest_url, ok, manifest? | error }
//   }

//*********************************************************************
//  Async firmware check — the manifest fetches (DNS + TLS to
//  messiter.com) can block for seconds. Run them on a one-shot
//  background task so loop() keeps feeding the servo output: a stalled
//  loop = CRSF frame gap = the PWM converter twitches the servos.
//*********************************************************************
inline volatile uint8_t fwCheckState = 0;      // 0 idle, 1 running, 2 done
inline String   fwCheckJson;                   // result, valid in state 2
inline String   fwCheckLocalUrl;               // resolved on the main task (NVS is not touched from the worker)
inline uint32_t fwCheckDoneMs = 0;

inline void fwCheckTask(void*) {
    String out;
    out.reserve(2048);
    out  = "{\"current\":\"";
    out += FW_VERSION;
    out += "\",\"local\":";
    fetchManifestInto(out, fwCheckLocalUrl, 2500);
    out += ",\"public\":";
    fetchManifestInto(out, String(FW_PUBLIC_MANIFEST_URL), 5000);
    out += "}";
    fwCheckJson   = out;
    fwCheckDoneMs = millis();
    fwCheckState  = 2;
    vTaskDelete(nullptr);
}

inline void handleFirmwareCheck() {
    if (netMode != NET_WIFI_UP) {
        // AP mode (or no-WiFi flight mode) can't reach either server.
        // Reply quickly with a clear "offline" payload so the UI can
        // explain instead of timing out.
        String j = "{\"current\":\"";
        j += FW_VERSION;
        j += "\",\"offline\":true,\"net_mode\":\"";
        j += netModeName();
        j += "\"}";
        server.sendHeader("Cache-Control", "no-store");
        server.send(200, "application/json", j);
        return;
    }
    // If the transmitter link is LIVE, skip the blocking manifest fetches — they
    // stall the single-threaded loop for seconds, starving radioPoll() so the
    // nRF24 RX FIFO fills and the TX misses acks (it can even disconnect). An
    // update check only matters when idle, so defer it while flying / driving the
    // sim and tell the UI why. (Keeps the transmitter happy.)
    if (lastChannelDataMs && (uint32_t)(millis() - lastChannelDataMs) < LINK_LIVE_MS) {
        String j = "{\"current\":\"";
        j += FW_VERSION;
        j += "\",\"link_active\":true}";
        server.sendHeader("Cache-Control", "no-store");
        server.send(200, "application/json", j);
        return;
    }
    // Serve a recent result straight from RAM — the front page checks on
    // EVERY visit, and re-fetching each time is pointless.
    if (fwCheckState == 2 && (uint32_t)(millis() - fwCheckDoneMs) < 10u * 60u * 1000u) {
        server.sendHeader("Cache-Control", "no-store");
        server.send(200, "application/json", fwCheckJson);
        return;
    }
    if (fwCheckState != 1) {
        // Resolve the local-manifest URL HERE (NVS on the main task), then
        // hand the slow network work to the background task. Fall back to
        // the compiled-in default so the dev Mac's firmware_server.py is
        // auto-discovered — production users simply see no local card.
        String localUrl = prefs.isKey(NVS_KEY_FW_MANIFEST)
                              ? prefs.getString(NVS_KEY_FW_MANIFEST, "")
                              : String("");
        localUrl.trim();
        if (localUrl.length() == 0)
            localUrl = FW_DEFAULT_LOCAL_MANIFEST_URL;
        fwCheckLocalUrl = localUrl;
        fwCheckState    = 1;
        // 12 KB stack: the TLS handshake (mbedtls) runs on this task's stack.
        if (xTaskCreatePinnedToCore(fwCheckTask, "fwchk", 12288, nullptr, 1, nullptr, 0) != pdPASS)
            fwCheckState = 0;   // couldn't start — report checking anyway; retried next poll
    }
    // Tell the page we're on it; it re-polls in a couple of seconds.
    String j = "{\"current\":\"";
    j += FW_VERSION;
    j += "\",\"checking\":true}";
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", j);
}

//*********************************************************************
//  POST /api/firmware/install?url=... — chip downloads .bin and applies
//*********************************************************************
// Synchronous — the HTTP response is returned only after the download
// completes (or fails), then the chip reboots. Accepts both http:// and
// https:// URLs (https:// is required for the messiter.com mirror).

// ---- Resume (2026-09-02) ----------------------------------------------------
// Three messiter.com installs in a row died with "download stalled" while the
// receiver's WiFi crawled at ~2 KB/s (kitchen, ping 500-700 ms). One stall used to
// throw the whole image away. Now a stalled or dropped connection is reopened with
// `Range: bytes=<got>-` and the download carries on where it stopped (LiteSpeed
// answers 206; a server that ignores Range sends 200 + the whole file and we skip
// the part we already hold). Only attempts that moved the download forward earn
// another go, so a dead link still gives up after ~two stall periods.
constexpr int OTA_RESUME_MAX = 8;   // reconnects per image (each must make progress)

// Open `url` for reading from byte `from`. Fills `total` (image size, learnt on the
// first open) and `skip` (bytes of this response to discard because the server
// sent the whole file again). Returns "" or a short reason; caller ends `http`.
inline String otaOpen(HTTPClient& http, WiFiClient& plain, WiFiClientSecure& secure,
                      const String& url, size_t from, int& total, size_t& skip) {
    // Generous timeouts — a slow messiter.com TLS handshake on a weak WiFi link
    // can take a few seconds before the first bytes flow.
    http.setConnectTimeout(8000);
    http.setTimeout(15000);
    if (!httpBeginAny(http, plain, secure, url)) return "begin failed";
    if (from) {
        char r[40]; snprintf(r, sizeof r, "bytes=%u-", (unsigned)from);
        http.addHeader("Range", r);
    }
    int code = http.GET();
    int len  = http.getSize();
    skip = 0;
    if (from && code == HTTP_CODE_PARTIAL_CONTENT) {
        if (len != total - (int)from) return "resume size mismatch";
    } else if (code == HTTP_CODE_OK) {
        if (from) {
            if (len != total) return "resume size mismatch";   // file changed under us
            skip = from;                                       // Range ignored: re-sent from 0
        } else {
            total = len;
        }
    } else {
        char m[40]; snprintf(m, sizeof m, "HTTP %d", code);
        return String(m);
    }
    if (total <= 0) return "no content-length";
    return "";
}

// Download `url` into the given Update target — U_FLASH (the app/OTA slot) or
// U_SPIFFS (the LittleFS data partition) — resuming across stalls. `beforeFlash`
// runs once, after the first response is confirmed and before the partition is
// touched (the FS path unmounts LittleFS there). Returns "" on success (image
// committed by Update.end) or a short reason (Update aborted, nothing committed).
inline size_t g_otaWritten = 0;   // bytes the last downloadToUpdate() handed to Update — a failed fs image with any is HALF WRITTEN (see fsFlashEnded)

template <typename BeforeFlash>
inline String downloadToUpdate(const String& url, int command, BeforeFlash beforeFlash) {
    const char* what = command == U_FLASH ? "firmware" : "web files";
    int      total = 0;
    size_t   got   = 0;
    g_otaWritten   = 0;
    int      idle  = 0;          // consecutive attempts that delivered nothing
    uint32_t t0    = millis();
    String   err;
    for (int attempt = 0;; attempt++) {
        HTTPClient       http;
        WiFiClient       plain;
        WiFiClientSecure secure;
        size_t           skip = 0;
        err = otaOpen(http, plain, secure, url, got, total, skip);
        if (err.length()) {
            http.end();
            // Reopening on a bad link can itself time out ("HTTP -11"): give it the
            // same patience as a stall, but only once the download has been moving.
            bool retry = got && err.startsWith("HTTP -") && ++idle < 2 && attempt < OTA_RESUME_MAX;
            if (!retry) break;
            char m[EventLog::MSG_LEN];
            snprintf(m, sizeof m, "%s: reopen failed (%s) at %u KB — retrying", what, err.c_str(), (unsigned)(got / 1024));
            events.add(m);
            esp_task_wdt_reset();
            continue;
        }
        if (attempt == 0) {
            beforeFlash();
            if (!Update.begin((size_t)total, command)) { err = Update.errorString(); http.end(); break; }
        }
        size_t before = got;
        err = httpStreamBounded(http, http.getSize(), [&](const uint8_t* b, size_t n) {
            if (skip) {                       // server re-sent from 0: drop what we already wrote
                size_t s = n < skip ? n : skip;
                skip -= s; b += s; n -= s;
                if (!n) return true;
            }
            if (Update.write((uint8_t*)b, n) != n) return false;
            got += n;
            return true;
        });
        http.end();
        if (err.isEmpty()) break;
        if (err == "write failed") { err = Update.errorString(); break; }
        bool transient = err.startsWith("download stalled") || err.startsWith("connection lost");
        idle = got > before ? 0 : idle + 1;
        if (!transient || idle >= 2 || attempt >= OTA_RESUME_MAX) break;
        char m[EventLog::MSG_LEN];
        snprintf(m, sizeof m, "%s: %s — resuming (RSSI %d)", what, err.c_str(), (int)WiFi.RSSI());
        events.add(m);
        esp_task_wdt_reset();
    }
    g_otaWritten = got;
    if (err.length()) {
        Update.abort();          // NOTE: keeps every byte already flashed — the fs caller wipes a half image
        char m[EventLog::MSG_LEN]; snprintf(m, sizeof m, "%s: %s", what, err.c_str());
        events.add(m);
        return err;
    }
    if (!Update.end(true)) return Update.errorString();
    char m[EventLog::MSG_LEN];
    snprintf(m, sizeof m, "%s downloaded: %d KB in %lu s", command == U_FLASH ? "Firmware" : "Web files",
             total / 1024, (unsigned long)((millis() - t0) / 1000));
    events.add(m);
    return "";
}

// Firmware image -> the OTA app slot. Streamed: nothing is committed unless the
// full image lands.
inline String flashStreamToPartition(const String& url, int command) {
    return downloadToUpdate(url, command, [] {});
}

// One preserved Rotorflight backup (held in RAM across a filesystem flash).
struct SavedBackup { String name; String data; };

// Snapshot/restore the user's /backups/*.json around a LittleFS reflash.
inline SavedBackup g_fsBackups[BACKUP_MAX];
inline int g_fsBackupCount = 0;

inline void snapshotBackupsToRam() {
    g_fsBackupCount = 0;
    if (littleFsMounted && LittleFS.exists(BACKUP_DIR)) {
        File dir = LittleFS.open(BACKUP_DIR);
        if (dir) {
            for (File f = dir.openNextFile(); f && g_fsBackupCount < BACKUP_MAX; f = dir.openNextFile()) {
                if (f.isDirectory()) { f.close(); continue; }
                String nm = f.name();
                int slash = nm.lastIndexOf('/'); if (slash >= 0) nm = nm.substring(slash + 1);
                g_fsBackups[g_fsBackupCount].name = nm;
                g_fsBackups[g_fsBackupCount].data = f.readString();
                g_fsBackupCount++;
                f.close();
            }
            dir.close();
        }
    }
}

// Flights are BINARY files — snapshot the three /fltN.bin too, so a pages
// update doesn't erase the flight history (Malcolm noticed every update
// tonight wiped it, 2026-07-23). ~7 kB each, heap-buffered around the flash.
inline uint8_t* g_fsFlights[FLIGHT_KEEP]   = {nullptr};
inline size_t   g_fsFlightLen[FLIGHT_KEEP] = {0};

inline void snapshotFlightsToRam() {
    for (uint8_t i = 0; i < FLIGHT_KEEP; ++i) {
        if (g_fsFlights[i]) { free(g_fsFlights[i]); g_fsFlights[i] = nullptr; }
        g_fsFlightLen[i] = 0;
    }
    // GENUINELY newest-first this time (2026-08-02 the loop walked PHYSICAL
    // slot order despite its comment, so under heap pressure it lifeboated
    // arbitrary OLD flights and drowned the new — Malcolm's first dated field
    // flights were lost to exactly that). Walk logical order via fltPhys so
    // whatever survives is the newest. Buffers go to PSRAM when the board has
    // it (8 MB on the XIAO S3 — the whole diary fits); heap is the fallback,
    // guarded so the fs update keeps working RAM (TLS / BLE buffers).
    uint8_t kept = 0, present = 0;
    for (uint8_t logical = 0; logical < FLIGHT_KEEP; ++logical) {
        const uint8_t phys = fltPhys(logical);
        if (!littleFsMounted || !LittleFS.exists(flightPath(phys))) continue;
        present++;
        File f = LittleFS.open(flightPath(phys), "r");
        if (!f) continue;
        size_t n = f.size();
        if (n > 0 && n <= 16384) {
            uint8_t* buf = (uint8_t*)heap_caps_malloc(n, MALLOC_CAP_SPIRAM);
            if (!buf && ESP.getFreeHeap() > 60000) buf = (uint8_t*)malloc(n);
            if (buf && f.read(buf, n) == (int)n) { g_fsFlights[phys] = buf; g_fsFlightLen[phys] = n; kept++; }
            else if (buf) free(buf);
        }
        f.close();
    }
    char m[56];
    snprintf(m, sizeof(m), "Lifeboat: %u of %u flights aboard", kept, present);
    events.add(m);
}

inline int restoreFlightsFromRam() {
    int restored = 0;
    for (uint8_t i = 0; i < FLIGHT_KEEP; ++i) {
        if (!g_fsFlights[i] || !g_fsFlightLen[i]) continue;
        if (littleFsMounted) {
            File w = LittleFS.open(flightPath(i), "w");
            if (w) { if (w.write(g_fsFlights[i], g_fsFlightLen[i]) == g_fsFlightLen[i]) restored++; w.close(); }
        }
        free(g_fsFlights[i]); g_fsFlights[i] = nullptr; g_fsFlightLen[i] = 0;
    }
    char m[48];
    snprintf(m, sizeof(m), "Lifeboat: %d flights ashore", restored);
    events.add(m);
    return restored;
}

inline int restoreBackupsFromRam() {
    int restored = 0;
    if (littleFsMounted && g_fsBackupCount > 0) {
        if (!LittleFS.exists(BACKUP_DIR)) LittleFS.mkdir(BACKUP_DIR);
        for (int i = 0; i < g_fsBackupCount; i++) {
            String path = BACKUP_DIR; path += '/'; path += g_fsBackups[i].name;
            File w = LittleFS.open(path, "w");
            if (w) { w.print(g_fsBackups[i].data); w.close(); restored++; }
        }
    }
    return restored;
}

// A web-files (LittleFS) flash that starts but does not finish leaves the
// partition HALF NEW, HALF OLD: the new superblock mounts fine, its directory
// names files whose data blocks are still the old image's, and the first
// read of one of those hung loop() for good — HTTP dead, ping alive, no
// watchdog, only a power cycle (Goblin 2026-09-03: the fs download stalled at
// 638 KB of 1.5 MB on RSSI -73, and Update.abort() keeps every byte already
// written). So: an NVS flag goes in BEFORE the first byte and comes out only
// once Update.end() has committed; boot finds it set → the partition is
// formatted before it is mounted (main.cpp); a failure the firmware sees
// itself formats right away and puts the lifeboat (backups + flights) ashore
// in the clean, page-less filesystem. Pages-less but alive beats deaf — the
// apps carry their own pages, and the next update restores the receiver's.
inline void fsFlashBegan() { prefs.putUChar(NVS_KEY_FS_DIRTY, 1); }

inline void fsFlashEnded(bool ok, size_t written) {
    if (ok) {
        prefs.putString(NVS_KEY_FS_MD5, Update.md5String());   // fingerprint: identical future images skip
    } else if (written) {
        LittleFS.format();                 // a half image must never be mountable
        prefs.remove(NVS_KEY_FS_MD5);      // no fingerprint → the next update flashes the pages again
        events.add("Web files: half-written image wiped — pages return with the next update");
    }
    prefs.putUChar(NVS_KEY_FS_DIRTY, 0);
}

inline void safeOutputParkAndRestart();   // defined below (bind section)
inline bool refuseIfTxLinked(const char* why);   // defined below — refuses while a TX link is live
inline bool refuseIfArmed(const char* what);     // defined below — refuses on an armed model

//*********************************************************************
//  BLE OTA push — the app downloads with the PHONE's internet (5G!) and
//  streams raw chunks over the BLE link (see BleConfig.h's 0xA5 lane).
//*********************************************************************

inline void handleBleOtaBegin() {
    // The Bluetooth twin of /api/firmware/install, which the 0.9.715 safety
    // review gated and this one escaped. Every chunk is a flash erase/write,
    // which stalls the CPU, so a transfer is minutes of repeated holes in the
    // control output. Refused before ANYTHING is touched (LittleFS included).
    // Pre-flight check 2026-09-15.
    if (refuseIfTxLinked("turn the transmitter off first - the receiver cannot keep sending control frames while it writes an update")) return;
    if (refuseIfArmed("Bluetooth update")) return;
    String type = server.hasArg("type") ? server.arg("type") : "fw";
    uint32_t size = server.hasArg("size") ? (uint32_t) server.arg("size").toInt() : 0;
    if (size == 0 || size > 4u * 1024u * 1024u) {
        server.send(400, "application/json", "{\"ok\":false,\"error\":\"bad size\"}");
        return;
    }
    if (bleOtaActive) { Update.abort(); bleOtaActive = false; }
    bleOtaCmd = (type == "fs") ? U_SPIFFS : U_FLASH;
    if (bleOtaCmd == U_SPIFFS) {
        snapshotBackupsToRam();      // whole partition is about to be replaced
        snapshotFlightsToRam();
        fsFlashBegan();              // NVS flag: a half-written image is wiped, never mounted
        LittleFS.end();
        littleFsMounted = false;
    }
    if (!Update.begin(size, bleOtaCmd)) {
        String e = Update.errorString();
        if (bleOtaCmd == U_SPIFFS) {
            fsFlashEnded(false, 0);  // nothing written: the old pages are intact, just clear the flag
            littleFsMounted = LittleFS.begin(false) || LittleFS.begin(true);
            restoreBackupsFromRam();
            restoreFlightsFromRam();
        }
        server.send(500, "application/json", String("{\"ok\":false,\"error\":\"") + e + "\"}");
        return;
    }
    bleOtaSize = size;
    bleOtaGot = 0;
    bleOtaError = "";
    bleOtaLastChunkMs = millis();
    bleOtaActive = true;
    events.add(bleOtaCmd == U_SPIFFS ? "BLE OTA: web files transfer started"
                                     : "BLE OTA: firmware transfer started");
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", "{\"ok\":true,\"chunk\":180}");
}

inline void handleBleOtaStatus() {
    char b[128];
    snprintf(b, sizeof(b), "{\"active\":%s,\"got\":%lu,\"size\":%lu,\"error\":\"%s\"}",
             bleOtaActive ? "true" : "false",
             (unsigned long) bleOtaGot, (unsigned long) bleOtaSize, bleOtaError.c_str());
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", b);
}

inline void handleBleOtaEnd() {
    if (!bleOtaActive) {
        server.send(409, "application/json", "{\"ok\":false,\"error\":\"no transfer\"}");
        return;
    }
    bleOtaActive = false;
    bool ok = (bleOtaGot == bleOtaSize) && bleOtaError.length() == 0 && Update.end(true);
    String err = ok ? "" : (bleOtaError.length() ? bleOtaError : String(Update.errorString()));
    if (!ok) Update.abort();
    if (bleOtaCmd == U_SPIFFS) {
        fsFlashEnded(ok, bleOtaGot);   // done: md5 fingerprint; failed: wipe the half image before mounting
        littleFsMounted = LittleFS.begin(false) || LittleFS.begin(true);
        int restored = restoreBackupsFromRam();
        restoreFlightsFromRam();
        char m[96]; snprintf(m, sizeof(m), "BLE OTA web files: %s (%d backups kept)", ok ? "done" : (bleOtaGot ? "FAILED — half image wiped" : "FAILED"), restored);
        events.add(m);
    } else {
        events.add(ok ? "BLE OTA firmware: flashed OK" : "BLE OTA firmware: FAILED");
    }
    server.sendHeader("Cache-Control", "no-store");
    if (ok) server.send(200, "application/json", "{\"ok\":true}");
    else    server.send(500, "application/json", String("{\"ok\":false,\"error\":\"") + err + "\"}");
}

inline void handleBleOtaReboot() {
    // Armed only, deliberately: begin already required the transmitter off,
    // and the app ignores this reply ("reply may die with the radio"), so a
    // refusal on a merely-live link would leave it waiting for a reboot that
    // never comes. The new image boots at the next power-up instead.
    if (refuseIfArmed("reboot after a Bluetooth update")) return;
    prefs.putUChar(NVS_KEY_OTA_BLE, 1);      // by definition over Bluetooth: hold the STA join after the reboot
    eventsPersist();                          // keep this boot's log
    prefs.putUChar(NVS_KEY_CFG_REBOOT, 1);   // config reboot: skip the RF window so BLE advertising returns and the app can reconnect + confirm
    server.send(200, "application/json", "{\"ok\":true,\"rebooting\":true}");
    bleEarlyPump();          // push the reply out over BLE before the radio dies
    delay(300);
    bleEarlyPump();               // over Bluetooth the reply must leave before the restart cuts the link (0.9.780)
    safeOutputParkAndRestart();   // throttle-low frames + parked pin — no prop blip
}

// Update the web/data filesystem (LittleFS) from fsUrl WITHOUT losing the user's
// /backups/*.json. The whole partition is overwritten by the new image, so we
// snapshot the backups (max 20 × ~1.5 KB — tiny) into RAM first, flash, re-mount,
// and write them back. Non-fatal: the firmware is already in place, so whatever
// happens here we still reboot. Returns a short status note for the reply/log.
inline String updateFilesystemKeepingBackups(const String& fsUrl) {
    // The FS image is confirmed to be really there BEFORE anything is touched — so
    // a release that ships no littlefs.bin (404) is a clean no-op that never disturbs
    // the live filesystem or the backups. (This is what makes deriving the URL safe.)
    bool touched = false;
    int  n       = 0;
    String err = downloadToUpdate(fsUrl, U_SPIFFS, [&] {
        // 1) First response confirmed: snapshot the user's backups (old FS still mounted).
        snapshotBackupsToRam();
        snapshotFlightsToRam();
        n = g_fsBackupCount;
        fsFlashBegan();            // NVS flag: a half-written image is wiped, never mounted (boot checks it too)
        // 2) Unmount; the image is flashed straight from the stream (bounded + resumed).
        LittleFS.end();
        touched = true;
    });
    if (!touched) return "";   // no FS for this release (404 / unreachable): nothing changed
    fsFlashEnded(err.isEmpty(), g_otaWritten);   // committed: fingerprint; died mid-image: format first

    // 3) Re-mount (format only if the freshly-written image won't mount), restore backups.
    bool mounted = LittleFS.begin(false) || LittleFS.begin(true);
    littleFsMounted = mounted;
    int restored = restoreBackupsFromRam();
    restoreFlightsFromRam();
    char m[160];
    if (err.length())
        snprintf(m, sizeof m, " (web files FAILED: %s — %s; %d/%d backups kept)", err.c_str(),
                 g_otaWritten ? "half image wiped, run the update again for the pages" : "old pages kept",
                 restored, n);
    else
        snprintf(m, sizeof m, " + web files (%d backups preserved)", restored);
    return String(m);
}

inline void handleFirmwareInstall() {
    // The download runs INSIDE this handler: loop() — and therefore radioPoll()
    // and sbusTick() — stops for its whole duration, seconds at best and tens of
    // seconds on a slow server. The event log already records where that led
    // once: "the Goblin receiver went DEAF for 8 minutes mid-update". Every
    // lesser reboot endpoint refuses while the transmitter is on; this, the most
    // loop-hostile one of all, did not (safety review, 2026-09-14).
    if (refuseIfTxLinked("turn the transmitter off first - the receiver stops sending control frames for the whole update")) return;
    if (refuseIfArmed("install firmware")) return;
    // Asked for over Bluetooth (0.9.779): the STA may be "up" yet deaf, or
    // mid-rejoin, because a Bluetooth link holds the one antenna (the zombie
    // WiFi of 0.9.728). Below, Bluetooth is PAUSED for the download; so a
    // receiver that has joined once this boot and is merely rejoining may
    // proceed too - it will be given a quiet radio to finish on.
    const bool fromBle = bleActive;
    const bool wifiUsable = (netMode == NET_WIFI_UP) ||
                            (fromBle && netMode == NET_WIFI_CONNECTING && staConnectedThisBoot);
    if (!wifiUsable) {
        // ClaudeFix-16-7-2026 the chip itself downloads the image, so without home WiFi
        // the install can only fail — say so plainly instead of "begin failed".
        server.send(409, "text/plain",
            "The receiver is not on home WiFi, so it cannot reach the update server. "
            "Wait for it to join (or connect it to WiFi on the WiFi page) and try again.");
        return;
    }
    if (!server.hasArg("url")) {
        server.send(400, "text/plain", "missing url");
        return;
    }
    String url = server.arg("url");
    url.trim();
    if (!(url.startsWith("http://") || isHttpsUrl(url))) {
        server.send(400, "text/plain", "url must start with http:// or https://");
        return;
    }
    String fsUrl = server.hasArg("fs_url") ? server.arg("fs_url") : String("");
    fsUrl.trim();
    // If the client (e.g. an older firmware.html) didn't send fs_url, DERIVE it from
    // the firmware URL — same folder, littlefs.bin — so the receiver fetches its own
    // web files even from a stale page. A release with no littlefs.bin is a clean
    // no-op (updateFilesystemKeepingBackups checks the URL exists before touching FS).
    if (fsUrl.length() == 0 && url.endsWith("/firmware.bin")) {
        fsUrl = url.substring(0, url.length() - 12) + "littlefs.bin";  // 12 = strlen("firmware.bin")
    }

    // PAUSE BLUETOOTH FOR THE DOWNLOAD (0.9.779). With a Bluetooth link open
    // the STA keeps reporting "connected" but passes no data, so the chip's
    // own download dies with HTTP -1 (Test1's page files, and DongleSim
    // "offering only Bluetooth" on the footstool, both 2026-09-18 - Malcolm:
    // "the idea we can only use WiFi when the app isn't running is weird!").
    // Reply first, then drop the link and re-associate on a quiet radio,
    // exactly as the app-leave heal does. The app rides out the drop (its
    // install window is 240 s) and reconnects after the reboot; if the
    // download fails, Bluetooth comes back so the page can report it.
    // Ground only: the TX-link and armed gates above have already passed.
    if (fromBle) {
        server.send(202, "text/plain", "downloading over WiFi - Bluetooth pauses until the receiver has rebooted");
        bleEarlyPump();
        bleStop();
        events.add("Install asked for over Bluetooth - Bluetooth paused, WiFi re-synced for the download");
        WiFi.disconnect(false, true);
        delay(200);
        WiFi.begin(getEffectiveSsid().c_str(), getEffectivePass().c_str());
        const uint32_t t0 = millis();
        while (WiFi.status() != WL_CONNECTED && (uint32_t)(millis() - t0) < 15000) delay(100);
        if (WiFi.status() != WL_CONNECTED) {
            events.add("WiFi did not come back for the download - Bluetooth restored, nothing changed");
            bleStart();
            return;   // the page judges by the version: unchanged = "did not complete", and it offers Bluetooth
        }
        netMode = NET_WIFI_UP; netStateStart = millis();
    }

    // 1) Application firmware -> OTA app slot. A mid-stream failure just leaves the
    //    current firmware bootable, so report it and DON'T reboot. The whole
    //    install runs under the download guard (see otaGuardBegin) so a stalled
    //    server can no longer hold loop() — and the receiver — hostage.
    // THE UPDATE RECORD (0.9.813): written as it happens so the next page to
    // ask can say plainly how far this got — no more working it out from
    // whether a poll answered (Malcolm 2026-09-19 and again 2026-09-20: "it
    // updated successfully, but stopped short of telling me so").
    {
        // What we are becoming. The page sends the release name; without it,
        // take the URL's DIRECTORY - .../release/v0.9.814/firmware.bin - since
        // the file itself is always called "firmware.bin" (0.9.815: the first
        // record read "to: firmware" and then judged a perfectly good install
        // a failure, which is the very thing this was built to prevent).
        String want = server.hasArg("name") ? server.arg("name") : String("");
        if (!want.length()) {
            // 0.9.826: the URL comes in two shapes, and the old code knew one.
            //   messiter.com:  .../release/v0.9.814/firmware.bin   -> version folder
            //   dev server:    http://192.168.1.193:8000/RXV2-0.9.825-slug.bin -> the FILE
            // On the second it took "192.168.1.193:8000" as the target, and the
            // boot judge then called a perfectly good install a FAILURE — the
            // exact false negative this record must never give (Malcolm's Sally
            // report, 2026-09-22). Prefer a release-named file; else the
            // version folder; else say nothing rather than something wrong.
            String u = url;
            int q = u.indexOf('?'); if (q >= 0) u = u.substring(0, q);
            int sl = u.lastIndexOf('/');
            String file = (sl >= 0) ? u.substring(sl + 1) : u;
            if (file.startsWith("RXV2-")) {
                if (file.endsWith(".bin")) file = file.substring(0, file.length() - 4);
                want = file;
            } else {
                String dir = (sl >= 0) ? u.substring(0, sl) : String("");
                int s2 = dir.lastIndexOf('/');
                String seg = (s2 >= 0) ? dir.substring(s2 + 1) : dir;
                if (seg.length() > 1 && seg[0] == 'v' && isDigit(seg[1])) want = seg.substring(1);
            }
        }
        prefs.putString(NVS_KEY_UPD_FROM, FW_VERSION);
        prefs.putString(NVS_KEY_UPD_TO, want);
        prefs.putUChar(NVS_KEY_UPD_STAGE, UPD_FIRMWARE);
        updFrom = FW_VERSION; updTo = want; updStage = UPD_FIRMWARE;
    }
    otaGuardBegin();
    String err = flashStreamToPartition(url, U_FLASH);
    if (err.length()) {
        otaGuardEnd();
        prefs.putUChar(NVS_KEY_UPD_STAGE, UPD_FAILED);
        updStage = UPD_FAILED;
        if (fromBle) {   // the reply has gone already; let the app back in to hear about it
            events.add((String("Firmware download failed: ") + err + " - Bluetooth restored, nothing changed").c_str());
            bleStart();
            return;
        }
        server.send(502, "text/plain", "firmware: " + err);
        return;
    }

    // 2) Matching web/data filesystem, if the release ships one (fs_url). Flashing
    //    it makes the web UI travel with the firmware — even on a jump up from an
    //    old version — while preserving the user's Rotorflight backups.
    String fsNote = "";
    // fs fingerprint skip (2026-07-31): when the client passes the release's
    // fs_md5 and it matches the image we already flashed, the web files are
    // identical — do not rewrite the filesystem. Saved flights (now 20) and
    // Rotorflight backups survive untouched, and field updates get faster.
    String wantMd5 = server.hasArg("fs_md5") ? server.arg("fs_md5") : String("");
    wantMd5.toLowerCase(); wantMd5.trim();
    String haveMd5 = prefs.getString(NVS_KEY_FS_MD5, ""); haveMd5.toLowerCase();
    if (wantMd5.length() == 32 && wantMd5 == haveMd5) {
        fsNote = " (web files identical — kept, flights preserved)";
        events.add("FS update skipped: image unchanged");
    } else if (fsUrl.length() && (fsUrl.startsWith("http://") || isHttpsUrl(fsUrl))) {
        prefs.putUChar(NVS_KEY_UPD_STAGE, UPD_PAGES);
        updStage = UPD_PAGES;
        fsNote = updateFilesystemKeepingBackups(fsUrl);
    }
    events.add((String("Firmware installed via auto-update") + fsNote + " — rebooting").c_str());
    prefs.putUChar(NVS_KEY_UPD_STAGE, UPD_REBOOTING);
    updStage = UPD_REBOOTING;
    otaGuardEnd();
    if (!fromBle) server.send(200, "text/plain", String("ok — rebooting") + fsNote);   // over Bluetooth the 202 went before the pause
    bleEarlyPump();               // over BLE: deliver the reply before the reboot kills the link (a no-op once paused)
    prefs.putUChar(NVS_KEY_OTA_BLE, fromBle ? 1 : 0);   // asked for from the app: hold the STA join after the reboot
    eventsPersist();              // this boot's log survives the reboot (it did not, and the first attempt's story was lost)
    UsbHostMsp::prepareForRestart();   // 0.9.706: give the FC a clean disconnect, or USB comes back dead
    delay(300);
    ESP.restart();
}

//*********************************************************************
//  Minimal POST-confirmation page (rendered inline, then chip reboots)
//*********************************************************************
// We don't load the full app shell here because the page lives ~500 ms before
// the chip resets. A tiny inline page is faster and survives even if
// LittleFS is broken.

inline String confirmPage(const char* title, const char* body, bool autoReload = true) {
    String s;
    s.reserve(autoReload ? 1400 : 480);
    s += F("<!doctype html><html><head><meta charset=utf-8>");
    s += F("<meta name=viewport content='width=device-width,initial-scale=1'>");
    s += F("<title>"); s += title; s += F(" &middot; LDRC RX V2</title>");
    s += F("<link rel=stylesheet href='/style.css'>");
    s += F("</head><body>");
    s += F("<div class=bg-photo aria-hidden=true></div>");
    s += F("<div class=bg-wash aria-hidden=true></div>");
    s += F("<div class=container><h1>"); s += title; s += F("</h1>");
    s += F("<div class=card>"); s += body;
    if (autoReload) {
        // Auto-recovery script. The chip is about to reboot — the page
        // polls /api/state.json until the chip answers (or 60 s elapses)
        // and then redirects to /. If the chip never comes back the user
        // sees a clear message pointing at AP-mode recovery, instead of
        // a frozen "Rebooting…" page that requires manual reload.
        s += F("<p id=__waitline class=muted style='margin-top:1em'>"
               "Waiting for receiver to come back (<span id=__secs>0</span>&thinsp;s)&hellip;"
               "</p>"
               // Manual escape hatch, shown from the start: if the auto-return is
               // ever defeated (iOS suspending the tab's timers, a stale pooled
               // connection after the reboot, an mDNS hiccup...), ONE tap goes
               // home — never "close the browser and reload".
               "<a class='btn btn-back' href='/' style='margin-top:.8em'>&#8617; Return to menu</a>"
               "<script>(()=>{"
               "const $=i=>document.getElementById(i);let n=0,ok=0;"
               "const ping=()=>{let sg;try{sg=AbortSignal.timeout(2000);}"
               "catch(e){const c=new AbortController();setTimeout(()=>c.abort(),2000);sg=c.signal;}"
               "return fetch('/api/state.json',{cache:'no-store',signal:sg});};"
               "const tick=async()=>{$('__secs').textContent=n;"
               // Require TWO consecutive good pings before redirecting: the chip answers
               // the tiny state.json the instant its server binds, but needs a moment more
               // before it can serve the full home page — redirecting on the first hit
               // loaded a blank '/'. location.replace keeps it out of history; the ?r=
               // cache-buster stops iOS resurrecting a stale cached copy of '/'.
               "if(n>=2){try{const r=await ping();"
               "if(r.ok){if(++ok>=2){location.replace('/?r='+Date.now());return;}}else ok=0;}catch(e){ok=0;}}"
               "if(n>=120){$('__waitline').innerHTML="
               "\"Receiver didn't come back by itself &mdash; tap <b>Return to menu</b> above. "
               "If a wrong WiFi password was entered it may be in AP mode &mdash; join the "
               "<b>LDRC_RX</b> WiFi and open <code>http://192.168.4.1</code>.\";return;}"
               "n++;setTimeout(tick,1000);};tick();"
               // iOS freezes timers while Safari is backgrounded/locked; when the tab
               // comes back, do ONE immediate check (no second loop) — by then the
               // chip has long rebooted, so a single good ping is enough to go home.
               "document.addEventListener('visibilitychange',()=>{if(!document.hidden)"
               "ping().then(r=>{if(r.ok)location.replace('/?r='+Date.now());}).catch(()=>{});});"
               "})();</script>");
    }
    s += F("</div>");
    s += F("<div class=footer>"); s += FW_VERSION; s += F("</div></div></body></html>");
    return s;
}

//*********************************************************************
//  POST /bind — clear bind and reboot
//*********************************************************************

// A clean restart for a receiver that may have a LIVE MODEL attached:
// push a burst of throttle-low frames, then park the output UART pin
// idle-high so the reboot glitch can't feed the converter/FC garbage
// (the propeller briefly spun during a reboot-into-bind, prop fitted).
inline void safeOutputParkAndRestart() {
    if (throttleChannel >= 1 && throttleChannel <= 16)
        channelMicros[throttleChannel - 1] = THROTTLE_SAFE_US;
    // Same guard loop() puts round sbusTick(): on a dongle D6 is the flight
    // controller's MSP port, and in sim mode nothing is listening. RC frames
    // belong on neither (pre-flight check 2026-09-15 — every dongle reboot was
    // pushing ~100 ms of CRSF into the FC's MSP parser on the way down).
    if (!dongleEnabled && !simEnabled)
        for (int i = 0; i < 12; ++i) { sbusTick(); delay(8); }     // ~100 ms of throttle-low frames
    Serial1.flush();
    Serial1.end();
    pinMode(PIN_SBUS_TX, INPUT_PULLUP); // idle-HIGH through the restart — silence, not noise
    UsbHostMsp::prepareForRestart();    // 0.9.706: and a clean USB disconnect for the FC
    delay(50);
    ESP.restart();
}

inline void handleBindDo() {
    if (refuseIfArmed("bind")) return;   // 2026-09-16 review: on a dongle the TX-link gates are no-ops
    // Stash the current pairing so a mistaken bind entry has a way back
    // (/api/bind/cancel restores it). Overwritten stash is fine — the
    // latest real pairing is the one worth restoring.
    if (bindState.bound)
        prefs.putBytes(NVS_KEY_PIPE_BAK, bindState.pipe, 5);
    clearBindNvs();
    String body = confirmPage("Rebooting",
        "<p>Bind cleared. The receiver is rebooting and will listen on DefaultPipe within ~5 seconds.</p>"
        "<p><a href='/'>Back to home</a> (reload after the chip is back)</p>");
    server.send(200, "text/html", body);
    delay(400);
    bleEarlyPump();               // over Bluetooth the reply must leave before the restart cuts the link (0.9.780)
    safeOutputParkAndRestart();
}

//*********************************************************************
//  POST /api/bind/cancel — leave bind mode, restore the stashed pairing
//*********************************************************************

inline void handleBindCancel() {
    if (refuseIfArmed("cancel bind")) return;   // 2026-09-16 review: on a dongle the TX-link gates are no-ops
    if (bindState.bound || !prefs.isKey(NVS_KEY_PIPE_BAK) ||
        prefs.getBytesLength(NVS_KEY_PIPE_BAK) != 5) {
        server.sendHeader("Cache-Control", "no-store");
        server.send(400, "application/json", "{\"ok\":false,\"error\":\"nothing to restore\"}");
        return;
    }
    uint8_t p[5];
    prefs.getBytes(NVS_KEY_PIPE_BAK, p, 5);
    prefs.putBytes(NVS_KEY_PIPE, p, 5);
    prefs.remove(NVS_KEY_PIPE_BAK);
    prefs.putUChar(NVS_KEY_CFG_REBOOT, 1);   // come straight back reachable
    events.add("Bind cancelled — previous pairing restored");
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", "{\"ok\":true}");
    delay(300);
    bleEarlyPump();               // over Bluetooth the reply must leave before the restart cuts the link (0.9.780)
    safeOutputParkAndRestart();
}

//*********************************************************************
//  POST /rollback — switch OTA slot and reboot
//*********************************************************************

inline void handleRollback() {
    if (refuseIfArmed("roll back")) return;   // 2026-09-16 review: on a dongle the TX-link gates are no-ops
    const esp_partition_t* other = esp_ota_get_next_update_partition(NULL);
    if (!other) {
        server.send(500, "text/plain", "no other partition");
        return;
    }
    esp_err_t err = esp_ota_set_boot_partition(other);
    if (err != ESP_OK) {
        String msg = "rollback failed: ";
        msg += esp_err_to_name(err);
        server.send(500, "text/plain", msg);
        return;
    }
    String msg = "<p>Switching boot to slot <code>";
    msg += other->label;
    msg += "</code> and restarting. If that slot is invalid, the bootloader will bring you back to the current firmware automatically.</p>"
           "<p><a href='/'>Back to home</a> (reload after the chip is back)</p>";
    server.send(200, "text/html", confirmPage("Rolling back", msg.c_str()));
    delay(400);
    bleEarlyPump();               // over Bluetooth the reply must leave before the restart cuts the link (0.9.780)
    safeOutputParkAndRestart();
}

//*********************************************************************
//  POST /api/factory-reset — wipe NVS + Rotorflight backups, reboot
//*********************************************************************
// For passing the receiver to a new owner. Clears every NVS key in our
// namespace (WiFi credentials, model name, bind pipe, saved protocol,
// boot counter, dev manifest URL, board MAC) so on next boot the chip
// behaves exactly like a fresh unit straight from the factory. Also
// removes /backups/*.json so the new owner doesn't inherit the
// previous owner's Rotorflight tuning history. LittleFS *page assets*
// (HTML/CSS/JS) are untouched so the UI still works on next boot.

inline void handleFactoryReset() {
    if (refuseIfArmed("factory reset")) return;   // 2026-09-16 review: on a dongle the TX-link gates are no-ops
    events.add("Factory reset requested via web UI");

    // 1. Wipe every NVS key in our namespace.
    prefs.clear();

    // 2. Remove the Rotorflight backups so the new owner starts clean.
    //    We delete the files but leave the directory itself in place
    //    so the existing /api/backup/* handlers still work afterwards.
    if (littleFsMounted && LittleFS.exists(BACKUP_DIR)) {
        File dir = LittleFS.open(BACKUP_DIR);
        if (dir) {
            File f = dir.openNextFile();
            while (f) {
                String path = f.path();
                f.close();
                LittleFS.remove(path);
                f = dir.openNextFile();
            }
            dir.close();
        }
    }

    String body = "<p>All saved settings have been cleared. The "
                  "receiver is rebooting and will come up as a "
                  "fresh unit at <code>RXV2.local</code>.</p>"
                  "<p>The new owner can set things up from scratch "
                  "on the welcome screen.</p>";
    server.send(200, "text/html",
                confirmPage("Factory reset", body.c_str(),
                            /*autoReload=*/false));
    delay(500);
    bleEarlyPump();               // over Bluetooth the reply must leave before the restart cuts the link (0.9.780)
    safeOutputParkAndRestart();   // closes the FC's USB handle first (0.9.706) — a bare restart left USB dead
}

//*********************************************************************
//  POST /api/firstrun — combined name + WiFi save for first connection
//*********************************************************************
// Saves model name (required) plus optional home-WiFi credentials in a
// single round-trip, then reboots once. Streamlines the first-time UX:
// instead of "set name → reboot → reconnect to new AP → set WiFi →
// reboot → join home WiFi" the user gets "set both → reboot → join
// home WiFi → done". The chip lands on the home network on the new
// hostname in one cycle.

inline void handleFirstRun() {
    if (refuseIfArmed("finish setup")) return;   // 2026-09-16 review: on a dongle the TX-link gates are no-ops
    String name = server.hasArg("name") ? server.arg("name") : String();
    name.trim();
    if (name.length() == 0 || name.length() > 30) {
        server.send(400, "text/plain", "name required (1-30 chars)");
        return;
    }
    // Same validation as /api/name: letters, digits, hyphens only.
    bool valid = true;
    for (size_t i = 0; i < name.length(); i++) {
        char c = name[i];
        bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                  (c >= '0' && c <= '9') || (i > 0 && c == '-');
        if (!ok) { valid = false; break; }
    }
    if (!valid) {
        server.send(400, "text/plain",
            "Invalid name. Letters, digits and hyphens only, "
            "must start with a letter or digit, no spaces.");
        return;
    }
    prefs.putString(NVS_KEY_MODEL_NAME, name);
    char ev[80];
    snprintf(ev, sizeof(ev), "First-run: name set to '%s'", name.c_str());
    events.add(ev);

    bool wifiSaved = false;
    if (server.hasArg("ssid") && server.arg("ssid").length() > 0) {
        String ssid = server.arg("ssid");
        ssid.trim();
        prefs.putString(NVS_KEY_SSID, ssid);
        if (server.hasArg("pass")) {
            prefs.putString(NVS_KEY_PASS, server.arg("pass"));
        }
        wifiSaved = true;
        snprintf(ev, sizeof(ev), "First-run: WiFi creds saved for '%s'", ssid.c_str());
        events.add(ev);
    }

    String body = "<p><b>Saved.</b> Receiver is rebooting as <code>";
    body += name;
    body += "</code>.</p>";
    if (wifiSaved) {
        body += "<p>It will join your home WiFi and become reachable at "
                "<code>";
        body += name;
        body += ".local</code>. Switch your phone back to your normal "
                "WiFi network and visit that address.</p>";
    } else {
        body += "<p>Reconnect to the <code>";
        body += name;
        body += "</code> WiFi network and reload this page to enter "
                "your home WiFi details next.</p>";
    }
    server.send(200, "text/html", confirmPage("Saved", body.c_str()));
    prefs.putUChar(NVS_KEY_CFG_REBOOT, 1);   // config reboot: come straight back to WiFi even if a TX is on
    delay(500);
    bleEarlyPump();               // over Bluetooth the reply must leave before the restart cuts the link (0.9.780)
    safeOutputParkAndRestart();   // closes the FC's USB handle first — a bare restart left USB dead
}

//*********************************************************************
//  POST /api/name — set the model name (e.g. "Goblin 700") and reboot
//*********************************************************************
// Empty name = clear the override and revert to the "RXV2-XXXX"
// default (last-4-hex of MAC). Limited to 30 characters so it fits in
// AP SSID + hostname budgets and stays readable in page titles.

inline void handleNameSet() {
    // A rename reboots. It had no transmitter or armed gate at all (pre-flight
    // check 2026-09-15), and was the last reboot here still on a bare
    // ESP.restart() — see below.
    if (refuseIfTxLinked("turn the transmitter off first - renaming restarts the receiver")) return;
    if (refuseIfArmed("rename")) return;
    String name = server.hasArg("name") ? server.arg("name") : server.arg("plain");
    name.trim();
    if (name.length() > 30) {
        server.send(400, "text/plain", "name too long (max 30)");
        return;
    }
    // Server-side validation. Only letters, digits, hyphens; must start
    // with alphanumeric. Empty name = revert to default. Anything else
    // would round-trip badly through mDNS / SSID, so reject rather than
    // silently sanitise — the form told the user the rules already.
    bool valid = name.length() == 0;
    if (!valid) {
        valid = true;
        for (size_t i = 0; i < name.length(); i++) {
            char c = name[i];
            bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                      (c >= '0' && c <= '9') || (i > 0 && c == '-');
            if (!ok) { valid = false; break; }
        }
    }
    if (!valid) {
        server.send(400, "text/plain",
            "Invalid name. Letters, digits and hyphens only, "
            "must start with a letter or digit, no spaces.");
        return;
    }
    if (name.length() == 0) {
        prefs.remove(NVS_KEY_MODEL_NAME);
        events.add("Model name cleared — reverting to default");
    } else {
        prefs.putString(NVS_KEY_MODEL_NAME, name);
        char buf[64];
        snprintf(buf, sizeof(buf), "Model name set to '%s'", name.c_str());
        events.add(buf);
    }
    String body = "<p>Model name updated. Receiver is rebooting so the "
                  "new name takes effect across the WiFi AP, mDNS, and "
                  "page titles.</p>";
    server.send(200, "text/html", confirmPage("Name saved", body.c_str()));
    bleEarlyPump();               // over BLE: give the reply a chance to leave before the reboot
    prefs.putUChar(NVS_KEY_CFG_REBOOT, 1);   // config reboot: come straight back to WiFi even if a TX is on
    delay(500);
    safeOutputParkAndRestart();   // throttle-low burst, pin parked — a bare ESP.restart() lets the output glitch
}

//*********************************************************************
//  POST /wifi — save WiFi credentials and reboot
//*********************************************************************

inline void handleWifiSet() {
    if (refuseIfArmed("save WiFi")) return;   // 2026-09-16 review: on a dongle the TX-link gates are no-ops
    if (server.hasArg("ssid")) {
        String ssid = server.arg("ssid");
        ssid.trim();   // an invisible trailing space breaks joining (firstrun trims; this path didn't)
        prefs.putString(NVS_KEY_SSID, ssid);
    }
    if (server.hasArg("pass") && server.arg("pass").length() > 0) {
        prefs.putString(NVS_KEY_PASS, server.arg("pass"));
    }
    // "AP mode only" — a checkbox only submits when ticked, so its presence is
    // the value. When on, next boot skips the home-WiFi STA and runs AP-only.
    bool apOnly = server.hasArg("aponly");
    prefs.putBool(NVS_KEY_AP_ONLY, apOnly);
    prefs.putBool(NVS_KEY_AP_AUTO, false);   // any manual WiFi save makes AP-only a deliberate choice → clear the "auto" notice
    apAutoEnabled = false;
    events.add(apOnly ? "AP-only mode enabled" : "WiFi credentials saved");

    if (apOnly) {
        // The receiver is about to come back on its OWN network, not the one the
        // phone is on now — so this page can't poll its way home. Turn off the
        // auto-reload and tell the user plainly to switch their phone's WiFi.
        String b = "<p><b>Saved.</b> The receiver is restarting as <b>its own WiFi "
                   "network</b> &mdash; no home router involved.</p>"
                   "<p style='font-size:1.05em'><b>Now, on your phone:</b></p>"
                   "<ol style='line-height:1.7;padding-left:1.2em'>"
                   "<li>Open your phone's <b>WiFi settings</b>.</li>"
                   "<li>Join the network called <b>";
        b += g_effectiveName;
        b += "</b>.</li>"
             "<li>Then open <a href='http://192.168.4.1'><code>http://192.168.4.1</code></a>.</li>"
             "</ol>"
             "<p class=muted>This page can't refresh itself, because your phone is "
             "still on your home WiFi until you switch it across.</p>";
        server.send(200, "text/html",
                    confirmPage("Switch your phone&rsquo;s WiFi", b.c_str(), /*autoReload=*/false));
    } else {
        String b = "<p>WiFi credentials saved. Receiver is rebooting and will attempt to join '";
        b += server.hasArg("ssid") ? server.arg("ssid") : getEffectiveSsid();
        b += "' on next boot.</p>";
        server.send(200, "text/html", confirmPage("Saved & rebooting", b.c_str()));
    }
    prefs.putUChar(NVS_KEY_CFG_REBOOT, 1);   // config reboot: come straight back to WiFi even if a TX is on
    delay(500);
    bleEarlyPump();               // over Bluetooth the reply must leave before the restart cuts the link (0.9.780)
    safeOutputParkAndRestart();   // closes the FC's USB handle first — a bare restart left USB dead
}

//*********************************************************************
//  POST /wifi_reset — DELIBERATELY removed (2026-05-27)
//*********************************************************************
// The "Forget & reboot" button was easy to tap accidentally and the same
// outcome (chip back in AP mode) is reachable by entering a wrong SSID/
// password through the normal /wifi form. The route is still registered
// below as a no-op so any cached bookmark or open tab that POSTs here
// just gets a 410 instead of silently wiping credentials.

inline void handleWifiResetGone() {
    server.send(410, "text/plain",
        "The 'forget WiFi' endpoint has been removed. Submit a different "
        "SSID/password via /wifi if you want to change the saved network.");
}

//*********************************************************************
//  POST /api/failsafe/save  — capture the CURRENT channels as failsafe
//  POST /api/failsafe/clear  — forget the saved failsafe
//*********************************************************************
// Stores the live channel values so a no-transmitter boot comes up in exactly
// this posture (see setup()). The user sets every switch/stick where they want
// the model to sit with no signal (e.g. disarmed), then taps Save.

inline void handleFailsafeSave() {
    if (refuseIfArmed("capture failsafe")) return;   // would store arm-high as the failsafe
    saveFailsafeToNvs();
    events.add("Failsafe captured from current channels");
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", "{\"ok\":true,\"failsafe_set\":true}");
}

inline void handleFailsafeClear() {
    if (refuseIfArmed("clear failsafe")) return;
    clearFailsafeNvs();
    events.add("Failsafe cleared");
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", "{\"ok\":true,\"failsafe_set\":false}");
}

//*********************************************************************
//  POST /api/gear?ratio=<float>  — extra head-speed divisor (normally 1:
//  Rotorflight already sends head speed; gear.js resets this to 1 on save)
//*********************************************************************
inline void handleVbatSet() {
    if (server.hasArg("pin")) {
        long pn = server.arg("pin").toInt();
        if (pn != 0 && pn != 9) {
            server.sendHeader("Cache-Control", "no-store");
            server.send(400, "application/json", "{\"ok\":false,\"error\":\"pin must be 0 (off) or 9 (D9)\"}");
            return;
        }
        vbatPin  = (uint8_t)pn;
        vbatAuto = false;
        prefs.putUChar(NVS_KEY_VBAT_PIN, vbatPin);
        vbatVolts = 0.0f; vbatVoltsTx = 0.0f;          // restart smoothing on the new pin
        vbatInit();
    }
    if (server.hasArg("ratio")) {
        float r = server.arg("ratio").toFloat();
        if (!(r > 0.0f)) {
            server.sendHeader("Cache-Control", "no-store");
            server.send(400, "application/json", "{\"ok\":false,\"error\":\"ratio must be a number > 0\"}");
            return;
        }
        if (r < 1.0f)  r = 1.0f;
        if (r > 50.0f) r = 50.0f;
        vbatRatio = r;
        vbatVolts = 0.0f; vbatVoltsTx = 0.0f;
        prefs.putFloat(NVS_KEY_VBAT_RATIO, vbatRatio);
    }
    if (server.hasArg("cells")) {
        long c = server.arg("cells").toInt();
        if (c < 0)  c = 0;
        if (c > 12) c = 12;
        vbatCellsCfg = (uint8_t)c;
        prefs.putUChar(NVS_KEY_VBAT_CELLS, vbatCellsCfg);
    }
    events.add(vbatPin ? "Battery ADC settings updated" : "Battery ADC off");
    char b[96];
    snprintf(b, sizeof(b), "{\"ok\":true,\"pin\":%u,\"volts\":%.2f,\"ratio\":%.2f,\"cells\":%u}",
             vbatPin, vbatVolts, vbatRatio, vbatCellsCfg);
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", b);
}

inline void handleGearSet() {
    if (server.hasArg("ratio")) {
        float r = server.arg("ratio").toFloat();
        // toFloat() returns 0.0 for garbage — reject instead of silently
        // clamping a typo to 0.1 (which would 10x the displayed head speed).
        if (!(r > 0.0f)) {
            server.sendHeader("Cache-Control", "no-store");
            server.send(400, "application/json", "{\"ok\":false,\"error\":\"ratio must be a number > 0\"}");
            return;
        }
        if (r < 0.1f)   r = 0.1f;
        if (r > 100.0f) r = 100.0f;
        gearRatio = r;
        prefs.putFloat(NVS_KEY_GEAR_RATIO, gearRatio);
        events.add("Gear ratio updated");
    }
    char b[64];
    snprintf(b, sizeof(b), "{\"ok\":true,\"gear_ratio\":%.3f}", gearRatio);
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", b);
}

//*********************************************************************
//  POST /api/armch?ch=<0..16>  — set the arming channel for flight-save
//*********************************************************************
inline void handleArmChSet() {
    if (server.hasArg("ch")) {
        long c = server.arg("ch").toInt();
        if (c < 0 || c > 16) {
            server.sendHeader("Cache-Control", "no-store");
            server.send(400, "application/json", "{\"ok\":false,\"error\":\"channel must be 0..16\"}");
            return;
        }
        armingChannel = (uint8_t)c;
        prefs.putUChar(NVS_KEY_ARM_CH, armingChannel);
        events.add(armingChannel ? "Arming channel set" : "Arming channel cleared");
    }
    char b[64];
    snprintf(b, sizeof(b), "{\"ok\":true,\"arming_channel\":%u}", (unsigned)armingChannel);
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", b);
}

//*********************************************************************
//  POST /protocol — save output protocol selection and reboot
//*********************************************************************

inline void handleProtocolSet() {
    if (refuseIfArmed("change the protocol")) return;   // 2026-09-16 review: on a dongle the TX-link gates are no-ops
    // Only a PROTOCOL (or PPM-polarity) change needs a reboot — the D6 pin
    // must be reconfigured as a different UART / RMT device. Everything else
    // (CRSF rate, FC-telemetry switch, throttle & arming channels) applies
    // LIVE; the page shows "Saved" and stays put.
    bool needReboot = false;

    if (server.hasArg("proto")) {
        long v = server.arg("proto").toInt();
        if (v >= PROTO_SBUS && v <= PROTO_MAX) {
            if ((Protocol)v != currentProtocol) needReboot = true;
            prefs.putUChar(NVS_KEY_PROTO, (uint8_t)v);
            char buf[60];
            snprintf(buf, sizeof(buf), "Output protocol set to %s", protocolName((Protocol)v));
            events.add(buf);
        }
    }
    bool wantInv = server.hasArg("ppm_inv");
    if (wantInv != ppmInverted && currentProtocol == PROTO_PPM) needReboot = true;
    prefs.putUChar(NVS_KEY_PPM_INV, wantInv ? 1 : 0);

    if (server.hasArg("crsf_hz")) {
        long hz = server.arg("crsf_hz").toInt();
        uint8_t v = (hz == 50 || hz == 100) ? (uint8_t)hz : 250;
        prefs.putUChar(NVS_KEY_CRSF_HZ, v);
        crsfRateHz = v;                                     // live: period is read every tick
    }
    {
        bool fcOn = server.hasArg("fc_telem");
        prefs.putUChar(NVS_KEY_FC_TELEM, fcOn ? 1 : 0);
        fcTelemetryEnabled = fcOn;                          // live: gates parser + probes
    }
    if (server.hasArg("thr_ch")) {
        long tc = server.arg("thr_ch").toInt();
        if (tc >= 0 && tc <= 16) {
            uint8_t old = throttleChannel;
            throttleChannel = (uint8_t)tc;
            prefs.putUChar(NVS_KEY_THR_CH, throttleChannel);
            // If the TX has never been heard, release the previously-pinned
            // channel back to centre and pin the new one at once.
            if (!lastChannelDataMs) {
                if (old >= 1 && old <= 16 && old != throttleChannel)
                    channelMicros[old - 1] = 1500;
                if (throttleChannel >= 1)
                    channelMicros[throttleChannel - 1] = THROTTLE_SAFE_US;
            }
        }
    }
    if (server.hasArg("arm_ch")) {
        long ac = server.arg("arm_ch").toInt();
        if (ac >= 0 && ac <= 16) {
            armingChannel = (uint8_t)ac;
            prefs.putUChar(NVS_KEY_ARM_CH, armingChannel);
        }
    }
    if (server.hasArg("wave_chs")) {
        // Comma list "1,6" → bitmask. Blank = no wave.
        String ws = server.arg("wave_chs");
        uint16_t m = 0;
        int start = 0;
        while (start < (int)ws.length()) {
            int comma = ws.indexOf(',', start);
            if (comma < 0) comma = ws.length();
            long ch = ws.substring(start, comma).toInt();
            if (ch >= 1 && ch <= 16) m |= (uint16_t)(1u << (ch - 1));
            start = comma + 1;
        }
        waveChannelMask = m;
        prefs.putUShort(NVS_KEY_WAVE_CHS, waveChannelMask);
    }

    if (!needReboot) {
        events.add("Output settings applied (no reboot needed)");
        server.sendHeader("Cache-Control", "no-store");
        server.send(200, "application/json", "{\"ok\":true,\"rebooting\":false}");
        return;
    }
    prefs.putUChar(NVS_KEY_CFG_REBOOT, 1);   // come straight back to WiFi (skip RF window)
    server.send(200, "text/html", confirmPage("Saved & rebooting",
        "<p>Output protocol updated. The receiver is rebooting to apply.</p>"));
    delay(250);
    bleEarlyPump();               // over Bluetooth the reply must leave before the restart cuts the link (0.9.780)
    safeOutputParkAndRestart();
}

//*********************************************************************
//  POST /api/sim — toggle "drive simulator over USB" and reboot
//*********************************************************************
// Persists the flag; it takes effect at boot in setup(). USB mode is fixed at
// compile time, so the HID joystick can only be brought up on a fresh boot —
// the same reboot-to-apply model the output-protocol setting uses.
// A receiver whose transmitter was linked within 3 s may be about to fly (the
// same window fcTelemActionAllowed uses): no reboot-to-apply setting and no
// command line then. A dongle has no transmitter to watch (0.9.640).
inline bool rxTxLinkedRecently() { return !dongleEnabled && rx.lastMillis && (uint32_t)(millis() - rx.lastMillis) < 3000; }
// Refuse anything that must not happen on an armed model. Same two tests
// handleMspApi already uses: the flight controller's OWN word if it is fresh,
// and the arming channel on a live transmitter link. Returns true if refused.
//
// Added 2026-09-14 after a safety review found POST /api/failsafe/save gated by
// NOTHING: capturing failsafe on an armed, spooling model stores the arming
// channel HIGH and the throttle wherever it happens to be, and that is what the
// receiver would then output on a real signal loss. The one stored position
// that must never say "armed".
// A dongle's ONLY flight signal is the flight controller's own armed word,
// fetched 4 times a second. "No fresh word" is not "disarmed": the poll stops
// behind a page's wait, the FC can fall silent, and a stale false would open
// every gate on an armed model (2026-09-16 review). Fresh = within 2.5 s.
inline bool dongleDisarmedConfirmed() {
    return fcInfo.detected && fcInfo.armedMs && !fcInfo.armed &&
           (uint32_t)(millis() - fcInfo.armedMs) < 2500;
}
inline bool refuseIfArmed(const char* what) {
    if (fcInfo.armed && fcInfo.armedMs && (uint32_t)(millis() - fcInfo.armedMs) < 5000) {
        server.sendHeader("Cache-Control", "no-store");
        server.send(409, "text/plain", "ARMED - the flight controller says it is armed. Disarm first.");
        return true;
    }
    const bool armLink = rx.lastMillis && (uint32_t)(millis() - rx.lastMillis) < 1000;
    if (armLink && armingChannel >= 1 && armingChannel <= 16 &&
        channelMicros[armingChannel - 1] > 1500) {
        { char m[96]; snprintf(m, sizeof m, "Refused while ARMED: %s", what); events.add(m); }
        server.sendHeader("Cache-Control", "no-store");
        server.send(409, "text/plain", "ARMED - disarm first.");
        return true;
    }
    // On a dongle that KNOWS a flight controller, insist on a fresh "disarmed"
    // — a silent or stale FC is refused, not trusted. A dongle that has never
    // heard an FC this power-up (bench, unwired) is left alone.
    //
    // EXCEPT while the command line is open (0.9.830). Opening it PAUSES MSP,
    // so the flight controller cannot give a fresh answer — and this clause
    // then refused the one action that would let it: leaving. Malcolm's
    // MyDongle, 2026-09-22: three "Refused, FC state unknown: leave the
    // command line" in a row, the app dead for the duration, until another
    // page's MSP call forced the exit. The last answer BEFORE the command
    // line opened stands: nothing can have armed the model since - the CLI is
    // the only thing talking to the FC, and it does not fly.
    if (dongleEnabled && fcInfo.detected && !UsbHostMsp::cliMode && !dongleDisarmedConfirmed()) {
        { char m[96]; snprintf(m, sizeof m, "Refused, FC state unknown: %s", what); events.add(m); }
        server.sendHeader("Cache-Control", "no-store");
        server.send(409, "text/plain", "Flight controller state unknown - it has not answered in the last few seconds. Try again.");
        return true;
    }
    return false;
}

inline bool refuseIfTxLinked(const char* why) {
    if (!rxTxLinkedRecently()) return false;
    server.send(409, "text/plain", why);
    return true;
}
// Rotorflight dongle mode (Malcolm 2026-09-08): POST /api/dongle on=0|1 [baud=N]
inline void handleDongleSet() {
    if (refuseIfArmed("change the dongle setting")) return;   // 2026-09-16 review: on a dongle the TX-link gates are no-ops
    if (refuseIfTxLinked("turn the transmitter off first - the receiver restarts to apply this")) return;
    // mode=0 automatic (default), 1 always a dongle, 2 always a receiver,
    // 3 simulator interface (0.9.757); `on` kept for older pages
    uint8_t mode = server.hasArg("mode") ? (uint8_t)server.arg("mode").toInt()
                 : server.hasArg("on")   ? (server.arg("on").toInt() != 0 ? 1 : 0) : 0;
    if (mode > 3) mode = 0;
    // A board WITH radios belongs in a model. Refuse to make it a simulator
    // interface by mistake - it would stop flying at the next power-up.
    if (mode == 3 && numRadiosPresent > 0) {
        server.send(409, "text/plain", "this board has transceivers fitted, so it is a receiver - the simulator interface is for a board with no radio. Use Simulator mode on the home page to fly a PC sim from your own transmitter.");
        return;
    }
    const bool on = (mode == 1) || (mode == 0 && numRadiosPresent == 0 && !simEnabled);
    uint32_t baud = server.hasArg("baud") ? (uint32_t)server.arg("baud").toInt() : dongleBaud;
    if (baud < 9600 || baud > 2000000) baud = 115200;
    prefs.putUChar(NVS_KEY_DONGLE, mode);
    prefs.putUInt(NVS_KEY_DONGLE_BAUD, baud);
    prefs.putUChar(NVS_KEY_CFG_REBOOT, 1);   // come straight back to WiFi
    { char m[96]; snprintf(m, sizeof(m), "Dongle setting: %s (%lu baud)", mode == 0 ? "automatic" : mode == 1 ? "always a dongle" : mode == 3 ? "simulator interface" : "always a receiver", (unsigned long)baud); events.add(m); }
    server.send(200, "text/html", confirmPage("Saved & rebooting", mode == 3
        ? "<p><b>Simulator interface</b>. Rebooting. Wire one of your receivers to this board: its signal output to <b>D5</b>, "
          "its 5 V to this board's <b>5V</b> pin, ground to ground - the same lead, with the flight-controller end moved to the receiver. "
          "Then plug this board into the computer, where it appears as a joystick. CRSF, SBUS, IBUS and PPM are recognised on their own.</p>"
        : on
        ? "<p>Rotorflight dongle mode <b>enabled</b>. Rebooting. Wire D5 to the flight controller's TX, D6 to its RX, "
          "5 V and GND, on a UART set to MSP in Rotorflight. No radio is used; any receiver can fly the model.</p>"
        : "<p>Dongle mode <b>disabled</b>. Rebooting back to a normal receiver.</p>"));
    delay(250);
    bleEarlyPump();               // over BLE the reply must leave before the reboot cuts the link
    safeOutputParkAndRestart();
}
inline void handleDonglePage() {
    if (serveLittleFsFile("/dongle.html", "text/html")) return;
    server.send(503, "text/plain", "/dongle.html missing — uploadfs the data/ folder");
}


inline void handleSimSet() {
    if (refuseIfArmed("change simulator mode")) return;   // 2026-09-16 review: on a dongle the TX-link gates are no-ops
    if (refuseIfTxLinked("turn the transmitter off first - the receiver restarts to apply this")) return;
    bool on = server.hasArg("on") ? (server.arg("on").toInt() != 0) : false;
    // A SIMULATOR INTERFACE board is in simulator mode by definition: boot
    // forces simEnabled from the role, so writing this setting changed
    // nothing while the page claimed it had (Malcolm 2026-09-19: "I turned
    // off Simulator mode to check it as Rotorflight dongle but it didn't go
    // off!"). Say so, and name the control that does work.
    if (simIfEnabled && !on) {
        server.send(409, "text/plain",
            "this board's role is Simulator interface, which IS simulator mode - turning it off here would change nothing. "
            "To make it a Rotorflight dongle instead, choose that role on the Dongle page.");
        return;
    }
    prefs.putUChar(NVS_KEY_SIM, on ? 1 : 0);
    prefs.putUChar(NVS_KEY_CFG_REBOOT, 1);   // come straight back to WiFi (skip RF window)
    events.add(on ? "Sim-over-USB enabled" : "Sim-over-USB disabled");
    server.send(200, "text/html", confirmPage("Saved & rebooting", on
        ? "<p>Simulator-over-USB <b>enabled</b>. The receiver is rebooting; plug it into your "
          "computer and it appears as a USB joystick driven by your sticks.</p>"
        : "<p>Simulator-over-USB <b>disabled</b>. The receiver is rebooting back to normal.</p>"));
    delay(250);
    bleEarlyPump();               // over Bluetooth the reply must leave before the restart cuts the link (0.9.780)
    safeOutputParkAndRestart();
}

//*********************************************************************
//  Spool-up realism — GET /api/sim/spool.json, POST /api/sim/spool
//*********************************************************************
// Live-applied (no reboot): the sim loop reads the globals every tick.
inline void handleSimSpoolGet() {
    // 192: the live{} block pushed the JSON past the old 128 and TRUNCATED it
    // (caught 2026-08-18 — clients saw broken JSON and silently failed).
    char b[256];
    snprintf(b, sizeof(b),
        "{\"on\":%s,\"seconds\":%u,\"torque_us\":%d,\"rudder_ch\":%u,\"motor_ch\":%u,\"motor_inv\":%s,"
        "\"pulse\":%s,\"pulse_ms\":%u,"
        "\"live\":{\"raw\":%u,\"out\":%u,\"ramping\":%s}}",
        simSpoolEnabled ? "true" : "false",
        (unsigned)simSpoolSeconds, (int)simTorqueUs, (unsigned)simRudderChannel,
        (unsigned)simMotorChannel, simMotorInverted ? "true" : "false",
        simSpoolPulse ? "true" : "false", (unsigned)simSpoolPulseMs,
        (unsigned)simSpoolDbgRaw, (unsigned)simSpoolDbgOut,
        simSpoolDbgRamp ? "true" : "false");
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", b);
}

inline void handleSimSpoolSet() {
    if (server.hasArg("on"))
        simSpoolEnabled = server.arg("on").toInt() != 0;
    if (server.hasArg("seconds")) {
        long s = server.arg("seconds").toInt();
        if (s < 1) s = 1;
        if (s > 60) s = 60;
        simSpoolSeconds = (uint8_t)s;
    }
    if (server.hasArg("torque_us")) {
        long t = server.arg("torque_us").toInt();
        if (t < -400) t = -400;
        if (t >  400) t =  400;
        simTorqueUs = (int16_t)t;
    }
    if (server.hasArg("rudder_ch")) {
        long c = server.arg("rudder_ch").toInt();
        if (c >= 1 && c <= 16) simRudderChannel = (uint8_t)c;
    }
    if (server.hasArg("motor_ch")) {
        long c = server.arg("motor_ch").toInt();
        if (c >= 0 && c <= 16) simMotorChannel = (uint8_t)c;   // 0 = unset (inert)
    }
    if (server.hasArg("motor_inv"))
        simMotorInverted = server.arg("motor_inv").toInt() != 0;
    if (server.hasArg("pulse"))
        simSpoolPulse = server.arg("pulse").toInt() != 0;
    if (server.hasArg("pulse_ms")) {
        long m = server.arg("pulse_ms").toInt();
        if (m < 50)   m = 50;
        if (m > 1000) m = 1000;
        simSpoolPulseMs = (uint16_t)m;
    }
    prefs.putUChar(NVS_KEY_SIM_PULSE,   simSpoolPulse ? 1 : 0);
    prefs.putUShort(NVS_KEY_SIM_PULSEMS, simSpoolPulseMs);
    prefs.putUChar(NVS_KEY_SIM_SPOOL,   simSpoolEnabled ? 1 : 0);
    prefs.putUChar(NVS_KEY_SIM_SPOOL_S, simSpoolSeconds);
    prefs.putShort(NVS_KEY_SIM_TORQUE,  simTorqueUs);
    prefs.putUChar(NVS_KEY_SIM_RUD_CH,  simRudderChannel);
    prefs.putUChar(NVS_KEY_SIM_MOT_CH,  simMotorChannel);
    prefs.putUChar(NVS_KEY_SIM_MOT_INV, simMotorInverted ? 1 : 0);
    events.add(simSpoolEnabled ? "Sim spool-up realism ON" : "Sim spool-up realism off");
    handleSimSpoolGet();
}

//*********************************************************************
//  Simulator channel remap — GET /map page, GET current map, POST new map
//*********************************************************************
// The map decides which received channel (0..15) feeds each of the 8 USB sim
// outputs, plus a per-output reverse. Applies LIVE (no reboot) and persists to
// NVS, re-read at the next sim boot. Mirrors the LDRC2SIM "Map channels" page;
// the live bars reuse /api/channels.json.
inline void handleMap() {
    if (serveLittleFsFile("/map.html", "text/html")) return;
    server.send(503, "text/plain", "/map.html missing — uploadfs the data/ folder");
}

inline void handleApiSimMap() {
    uint8_t m[8]; bool r[8];
    SimUSB::getMap(m, r);
    String j; j.reserve(96);
    j = "{\"map\":[";
    for (int i = 0; i < 8; i++) { if (i) j += ','; j += m[i]; }
    j += "],\"rev\":[";
    for (int i = 0; i < 8; i++) { if (i) j += ','; j += (r[i] ? 1 : 0); }
    j += "]}";
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", j);
}

inline void handleMapSave() {
    String m = server.arg("map"), r = server.arg("rev");
    uint8_t nm[8], nr[8], cm = 0, cr = 0;
    int start = 0;
    for (uint8_t i = 0; i < 8 && start <= (int)m.length(); i++) {
        int comma = m.indexOf(',', start);
        String tok = (comma < 0) ? m.substring(start) : m.substring(start, comma); tok.trim();
        if (tok.length()) { int v = tok.toInt(); if (v < 0) v = 0; if (v > 15) v = 15; nm[cm++] = (uint8_t)v; }
        if (comma < 0) break; start = comma + 1;
    }
    start = 0;
    for (uint8_t i = 0; i < 8 && start <= (int)r.length(); i++) {
        int comma = r.indexOf(',', start);
        String tok = (comma < 0) ? r.substring(start) : r.substring(start, comma); tok.trim();
        if (tok.length()) { nr[cr++] = (uint8_t)(tok.toInt() != 0); }
        if (comma < 0) break; start = comma + 1;
    }
    if (cm != 8 || cr != 8) { server.send(400, "text/plain", "expected 8 values"); return; }
    bool rb[8]; for (int i = 0; i < 8; i++) rb[i] = nr[i] != 0;
    SimUSB::setMap(nm, rb);
    prefs.putBytes(NVS_KEY_SIM_MAP, nm, 8);
    prefs.putBytes(NVS_KEY_SIM_REV, nr, 8);
    events.add("Sim channel map updated");
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "text/plain", "ok");
}

//*********************************************************************
//  Simulator function buttons — /simctl page, live states, button pulse
//*********************************************************************
// 8 HID joystick buttons, each fired by TX channel 9..16 (a switch past
// BTN_THRESH) AND by a tap on the /simctl page. Bind each button to a sim
// function (Reset, Pause, view…) in the sim's own controller setup — no keyboard.
inline void handleSimCtl() {
    if (serveLittleFsFile("/simctl.html", "text/html")) return;
    server.send(503, "text/plain", "/simctl.html missing — uploadfs the data/ folder");
}

inline void handleApiSimButtons() {
    uint8_t b = SimUSB::getButtons();
    String j; j.reserve(120);
    j = "{\"btn\":[";
    for (int i = 0; i < 8; i++) { if (i) j += ','; j += ((b >> i) & 1); }
    j += "],\"ch\":[";                                  // source channels 9..16 (µs)
    for (int i = 8; i < 16; i++) { if (i > 8) j += ','; j += channelMicros[i]; }
    j += "]}";
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", j);
}

inline void handleSimButton() {
    int n = server.hasArg("n") ? server.arg("n").toInt() : 0;
    if (n < 1 || n > 8) { server.send(400, "text/plain", "n must be 1..8"); return; }
    SimUSB::pressButton((uint8_t)n);
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "text/plain", "ok");
}

//*********************************************************************
//  Camera / view keystrokes — /views page + POST a keystroke
//*********************************************************************
// The composite USB device includes a standard keyboard; /api/sim/key sends one
// momentary keystroke (HID usage `code`, modifier bitmask `mods`) so the phone
// can drive RealFlight's view shortcuts. The label/keycode table lives in the
// /views page so it's easy to edit once the real shortcuts are confirmed.
inline void handleViews() {
    if (serveLittleFsFile("/views.html", "text/html")) return;
    server.send(503, "text/plain", "/views.html missing — uploadfs the data/ folder");
}

inline void handleSimKey() {
    int code = server.hasArg("code") ? server.arg("code").toInt() : 0;   // HID usage id
    int mods = server.hasArg("mods") ? server.arg("mods").toInt() : 0;   // modifier bitmask
    // 0x65 (Application key) is the keyboard descriptor's declared Usage/
    // Logical Maximum (SimUsb.h) — codes above it are outside the report's
    // range and hosts silently discard them, so reject rather than "send" one.
    if (code < 1 || code > 0x65) { server.send(400, "text/plain", "code must be 1..101 (0x65)"); return; }
    SimUSB::sendKey((uint8_t)code, (uint8_t)(mods & 0xFF));
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "text/plain", "ok");
}

//*********************************************************************
//  POST /fly_arm — disable WiFi until next reboot
//*********************************************************************

//*********************************************************************
//  GET/POST /api/autofly — the automatic fly-mode switch
//*********************************************************************
inline void handleAutoFlyGet() {
    server.sendHeader("Cache-Control", "no-store");
    char b[64];
    snprintf(b, sizeof(b), "{\"on\":%s,\"forced\":%s}",
             autoFlyActive() ? "true" : "false",
             autoFlyForcedNow ? "true" : "false");
    server.send(200, "application/json", b);
}
inline void handleAutoFlySet() {
    // With Rotorflight present the switch is locked ON — the preference is
    // still stored for non-RF models, but the effective state stays true.
    if (server.hasArg("on")) autoFlyEnabled = server.arg("on").toInt() != 0;
    prefs.putUChar(NVS_KEY_AUTOFLY, autoFlyEnabled ? 1 : 0);
    events.add(autoFlyActive() ? (autoFlyForcedNow ? "Auto fly mode ON (locked: Rotorflight)"
                                                   : "Auto fly mode ON")
                               : "Auto fly mode off");
    handleAutoFlyGet();
}

inline void handleFlyArm() {
    // Opt out of confirmPage's auto-reload — WiFi is about to be cut on
    // purpose, polling /api/state.json forever would just confuse the
    // user. They explicitly armed Fly mode; the static page is correct.
    server.send(200, "text/html", confirmPage("Flying",
        "<p>The receiver is now in <b>RF-only</b> mode. WiFi will return on the next power-cycle.</p>"
        "<p class=muted>SBUS keeps streaming. This page will stop responding the moment WiFi shuts down (any second now).</p>",
        /*autoReload=*/false));
    bleEarlyPump();               // over BLE the reply must go out before the radios quieten
    flyArmRequested = true;       // disableWifi() runs from loop() after this response flushes
}

//*********************************************************************
//  POST /fly_disarm — leave RF-only mode: reboot, radios return
//*********************************************************************
// Reachable only over the kept-alive BLE link (WiFi is already off).
// A reboot is the proven way back: WiFi + BLE come up as normal at
// boot, and the phone app auto-reconnects through it.

inline void handleFlyDisarm() {
    // This is the reboot a pilot presses AT THE FIELD, on a model still on its
    // flight pack — head coasting down, or idling for the next flight. A bare
    // ESP.restart() lets the output pin glitch on the way down, which is the
    // exact fault safeOutputParkAndRestart() exists to prevent ("the propeller
    // briefly spun during a reboot-into-bind, prop fitted"). It was the only
    // pilot-facing reboot still using the unsafe one (safety review 2026-09-14).
    if (refuseIfArmed("bring the radios back")) return;
    server.send(200, "text/plain", "ok — rebooting, radios return in ~15 s");
    bleEarlyPump();
    safeOutputParkAndRestart();     // throttle-low burst, pin parked idle-high
}

//*********************************************************************
//  GET /reboot — soft reset
//*********************************************************************

inline void handleReboot() {
    // Registered for any method, GET included, so a prefetch or a restored
    // browser tab can fire it. Pre-flight check 2026-09-15: it had no gate.
    if (refuseIfTxLinked("turn the transmitter off first - this restarts the receiver")) return;
    if (refuseIfArmed("reboot")) return;
    server.send(200, "text/html", confirmPage("Rebooting",
        "<p>Back in ~5 s.</p>"));
    delay(400);
    bleEarlyPump();               // over Bluetooth the reply must leave before the restart cuts the link (0.9.780)
    safeOutputParkAndRestart();
}

//*********************************************************************
//  POST /api/wave — fire the Bluetooth-ready wave on demand ("which
//  model is this?" finder, and a bench-test hook for the wave itself).
//  Refused while a TX link is live — never fight the pilot's sticks.
//*********************************************************************
inline void handleWaveNow() {
    bool linkLive = rx.lastMillis && (uint32_t)(millis() - rx.lastMillis) < 1000;
    if (linkLive) {
        server.sendHeader("Cache-Control", "no-store");
        server.send(409, "application/json", "{\"ok\":false,\"error\":\"transmitter link is live\"}");
        return;
    }
    bleWaveStartMs = millis();
    events.add("Wave requested from app");
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", "{\"ok\":true}");
}

//*********************************************************************
//  GET /retest — re-run self-test, redirect to /diagnostics
//*********************************************************************

inline void handleRetest() {
    runRadioSelfTest();
    server.sendHeader("Location", "/diagnostics", true);
    server.send(303, "text/plain", "retested");
}

//*********************************************************************
//  /api/events.json — black-box event log, newest-first
//*********************************************************************

inline void handleApiEvents() {
    String j;
    j.reserve(events.count * 100 + 8);
    j += '[';
    if (events.count > 0) {
        size_t n = events.count;
        size_t idx = (events.head + EventLog::SIZE - 1) % EventLog::SIZE;
        for (size_t k = 0; k < n; ++k) {
            if (k) j += ',';
            j += "{\"t\":"; j += events.when[idx];
            if (epochOffsetMs) {           // clock known → stamp time-of-day too
                j += ",\"e\":";
                j += (uint32_t)((epochOffsetMs + (int64_t)events.when[idx]) / 1000);
            }
            j += ",\"msg\":\"";
            // Minimal JSON escaping
            const char* m = events.msgs[idx];
            for (; *m; ++m) {
                if (*m == '"' || *m == '\\') j += '\\';
                j += *m;
            }
            j += "\"}";
            idx = (idx + EventLog::SIZE - 1) % EventLog::SIZE;
        }
    }
    j += ']';
    server.send(200, "application/json", j);
}

//*********************************************************************
//  /api/events-prev.json — the PREVIOUS boot's persisted event tail
//*********************************************************************
// Written by eventsPersist() at stall-pardoned moments; rotated to
// /evprev.txt at boot. The reboot-destroys-the-evidence problem
// (Malcolm 2026-08-07) ends here: the app's session save captures this.

inline void handleApiEventsPrev() {
    String j;
    j.reserve(4096);
    j += '[';
    File f = littleFsMounted ? LittleFS.open("/evprev.txt", "r") : File();
    bool first = true;
    if (f) {
        while (f.available()) {
            String line = f.readStringUntil('\n');
            if (!line.length()) continue;
            int sp = line.indexOf(' ');
            if (sp <= 0) continue;
            if (!first) j += ',';
            first = false;
            j += "{\"t\":"; j += line.substring(0, sp);
            j += ",\"msg\":\"";
            for (size_t i = (size_t)sp + 1; i < line.length(); ++i) {
                char c = line[i];
                if (c == '"' || c == '\\') j += '\\';
                if (c >= 32) j += c;
            }
            j += "\"}";
        }
        f.close();
    }
    j += ']';
    server.send(200, "application/json", j);
}

//*********************************************************************
//  /api/channels.json — tiny endpoint just for the live channel viewer
//*********************************************************************
// Polled at ~10 Hz by data/diagnostics.html. Returns the 16 decoded
// channel uS values plus the age of the most recent RC frame so the
// page can grey the bars out when the signal drops.

inline void handleApiChannels() {
    // A DONGLE has no radio, so channelMicros[] is never filled by a
    // transmitter — the page used to be hidden from it entirely. But the
    // flight controller on the other end of the cable knows exactly what its
    // own receiver is giving it, and MSP 105 hands those values over. So on a
    // dongle the bars (and the little helicopter) show what the FC is
    // actually seeing, which is arguably more useful than on a receiver:
    // it proves the whole chain, transmitter to flight controller.
    //
    // Read here, in the HTTP handler, and NOT from loop(): this is already a
    // request-scoped blocking context, it only happens while somebody has the
    // page open, and loop() stays untouched.
    // Stands down while the model is armed, per the standing rule that a
    // dongle-motivated poll must not compete for the link near flight.
    if (dongleEnabled && fcInfo.detected && !fcInfo.armed) {
        static uint32_t lastRcMs = 0;
        const uint32_t now = millis();
        if ((uint32_t)(now - lastRcMs) >= 60) {        // <= ~16 Hz, whatever the page asks
            lastRcMs = now;
            static uint8_t rc[64];
            uint16_t rcLen = 0;
            if (mspRequestAndWait(MSP_RC, nullptr, 0, rc, &rcLen, 120) && rcLen >= 2) {
                const int n = rcLen / 2 > 16 ? 16 : rcLen / 2;
                for (int i = 0; i < n; ++i) {
                    const uint16_t v = (uint16_t)(rc[i * 2] | (rc[i * 2 + 1] << 8));
                    if (v >= 800 && v <= 2200) channelMicros[i] = v;
                }
                if (n > 0) lastChannelDataMs = now;
            }
        }
    }
    String j;
    j.reserve(180);
    j += "{\"ch\":[";
    for (int i = 0; i < 16; ++i) {
        if (i) j += ',';
        j += channelMicros[i];
    }
    j += "],\"age_ms\":";
    if (lastChannelDataMs) j += (uint32_t)(millis() - lastChannelDataMs);
    else                   j += "-1";
    j += "}";
    server.send(200, "application/json", j);
}

// Arm/disarm the BLE channel stream (state lives in BleConfig.h — frames
// only ever flow to a connected Bluetooth client; over WiFi this simply
// parks the flags, and the JSON poll above keeps working everywhere).
inline void handleChannelStream() {
    bleStreamOn = !server.hasArg("on") || server.arg("on") == "1";
    if (server.hasArg("ms")) {
        long ms = server.arg("ms").toInt();
        bleStreamMs = (uint32_t)(ms < 20 ? 20 : (ms > 200 ? 200 : ms));
    }
    bleStreamArm = millis();
    server.send(200, "text/plain", bleStreamOn ? "stream on" : "stream off");
}

//*********************************************************************
//  /api/flightlog.json?f=N — flight time-series (0 = live, 1..3 = saved)
//  /api/flights.json — list of available flights (for the selector)
//*********************************************************************
inline void handleApiFlightLog() {
    uint8_t f = server.hasArg("f") ? (uint8_t)server.arg("f").toInt() : 0;
    String j;
    if (!buildFlightJson(f, j)) { server.send(404, "application/json", "{\"count\":0}"); return; }
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", j);
}
inline void handleApiFlights() {
    // Asking for the flight list ends any save's quiet-moment wait — the
    // pilot is demonstrably on the ground, phone in hand (Malcolm 2026-08-03).
    // The async writer does the actual work over the next loop passes; the
    // page's 5 s refresh then shows the freshly saved flight.
    fltSaveAsapMs = millis();
    String j; buildFlightsListJson(j);
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", j);
}

//*********************************************************************
//  /api/state.json — comprehensive single endpoint for all pages
//*********************************************************************

inline void handleApiState() {
    String j;
    j.reserve(2200);
    char buf[96];

    // JSON string escaper for USER-SUPPLIED text (model name, SSID). An SSID
    // may legally contain " or \ — embedding it raw makes state.json invalid
    // JSON, which kills EVERY page (they all fetch it on load), including the
    // wifi page needed to fix the SSID. Control chars → \u00XX for the same
    // reason.
    auto jsonEsc = [&j](const String& s) {
        for (size_t i = 0; i < s.length(); i++) {
            char c = s[i];
            if (c == '"' || c == '\\') { j += '\\'; j += c; }
            else if ((uint8_t)c < 0x20) {
                char u[8]; snprintf(u, sizeof(u), "\\u%04x", (unsigned)(uint8_t)c); j += u;
            } else j += c;
        }
    };

    // --- info ----------------------------------------------------------
    j += "{\"info\":{";
    j += "\"fw_version\":\""; j += FW_VERSION; j += "\"";
    j += ",\"build_date\":\""; j += __DATE__; j += ' '; j += __TIME__; j += "\"";
    j += ",\"name\":\""; jsonEsc(g_effectiveName); j += "\"";
    j += ",\"name_custom\":"; j += (nameIsCustom() ? "true" : "false");
    { String fm = prefs.getString(NVS_KEY_FS_MD5, ""); j += ",\"fs_md5\":\""; j += fm; j += "\""; }
    j += ",\"hostname\":\""; j += g_hostname; j += "\"";
    j += ",\"ip\":\""; j += WiFi.localIP().toString(); j += "\"";
    j += ",\"mac\":\""; j += WiFi.macAddress(); j += "\"";
    j += ",\"rssi\":"; j += (netMode == NET_WIFI_UP ? (int)WiFi.RSSI() : 0);
    // The receiver's notion of wall-clock time and where it came from —
    // Malcolm: "the RX is getting the TX time but not putting it on the
    // black box screen". epoch_s is UTC; the page renders it locally.
    j += ",\"epoch_s\":"; j += epochNowS();
    j += ",\"clock_src\":\"";
    j += (epochOffsetMs == 0 ? "none" : (epochFromPhone ? "phone" : "tx"));
    j += "\"";
    j += ",\"tx_off_known\":"; j += (txClockOffKnown ? "true" : "false");
    j += ",\"tx_off_s\":"; j += txClockOffS;
    j += ",\"uptime_s\":"; j += (uint32_t)((millis() - bootMillis) / 1000);
    j += ",\"uptime_str\":\""; j += uptimeString(); j += "\"";
    j += ",\"free_heap\":"; j += ESP.getFreeHeap();
    j += ",\"chip\":\""; j += ESP.getChipModel(); j += "\"";
    j += ",\"chip_rev\":"; j += ESP.getChipRevision();
    j += ",\"littlefs\":"; j += (littleFsMounted ? "true" : "false");
    j += ",\"ap_ssid\":\""; jsonEsc(g_effectiveName); j += "\"";   // the SSID actually broadcast (model name), not the legacy "LDRC_RX" constant
    // ap_ip reports the soft-AP address whenever the AP interface is
    // up — in v0.9.51 that's "always" because the chip runs AP+STA in
    // parallel. The wifi UI uses this to tell the user they can reach
    // the chip via 192.168.4.1 even when STA is connected.
    j += ",\"ap_ip\":\""; {
        IPAddress apIp = WiFi.softAPIP();
        if (apIp[0] || apIp[1] || apIp[2] || apIp[3]) j += apIp.toString();
    } j += "\"";

    const esp_partition_t* running = esp_ota_get_running_partition();
    const esp_partition_t* other   = esp_ota_get_next_update_partition(NULL);
    j += ",\"partition_running\":\""; j += (running ? running->label : ""); j += "\"";
    j += ",\"partition_other\":\""; j += (other ? other->label : ""); j += "\"";
    j += ",\"partition_other_kb\":"; j += (other ? other->size / 1024 : 0);
    j += "}";

    // --- net ----------------------------------------------------------
    j += ",\"net\":{";
    j += "\"mode\":\""; j += netModeName(); j += "\"";
    j += ",\"rf_only\":"; j += (netMode == NET_NO_WIFI) ? "true" : "false";
    j += ",\"ssid\":\""; jsonEsc(getEffectiveSsid()); j += "\"";
    j += ",\"ssid_custom\":"; j += (wifiCredsAreCustom() ? "true" : "false");
    j += ",\"ap_only\":"; j += ((prefs.isKey(NVS_KEY_AP_ONLY) && prefs.getBool(NVS_KEY_AP_ONLY, false)) ? "true" : "false");
    j += ",\"ap_auto\":"; j += (apAutoEnabled ? "true" : "false");   // AP-only was auto-enabled (home net not found)
    // Raw STA status while joining (wl_status_t): 1 = home SSID not in
    // range (the field) → the update pages stop waiting for WiFi and go
    // straight to Bluetooth; 6 = seen but not admitted yet → worth waiting.
    snprintf(buf, sizeof(buf), ",\"sta_status\":%d", netMode == NET_WIFI_CONNECTING ? (int)WiFi.status() : -1);
    j += buf;
    j += "}";

    // --- rf -----------------------------------------------------------
    j += ",\"rf\":{";
    snprintf(buf, sizeof(buf), "\"packets\":%u,\"acks_written\":%u,\"mac_acks_sent\":%u,\"mac_ack_threshold\":%u",
             (unsigned)rx.packets, (unsigned)rx.acksWritten, (unsigned)macAcksSent, (unsigned)MAC_ACK_THRESHOLD);
    j += buf;
    j += ",\"last_pkt_ms\":";
    if (rx.lastMillis) j += (uint32_t)(millis() - rx.lastMillis); else j += "-1";
    j += ",\"radios_count\":"; j += numRadiosPresent;
    j += ",\"radios_present\":["; j += (radioPresent[0] ? "true" : "false");
    j += ',';                     j += (radioPresent[1] ? "true" : "false");
    j += ',';                     j += (radioPresent[2] ? "true" : "false");
    j += "]";
    j += ",\"loop_hz\":";     j += g_loopHz;       // diag: loop rate (radioPoll/sec)
    j += ",\"loop_max_us\":"; j += g_loopMaxUs;    // diag: worst loop stall last second
    j += ",\"loop_max_op\":\""; j += g_loopMaxOpName; j += "\"";   // diag (0.9.551): slowest timed call inside that iteration
    j += ",\"loop_max_op_us\":"; j += g_loopMaxOpUs;
    // Legacy field — kept for any older diagnostics page that reads it.
    j += ",\"radios_dual\":"; j += (numRadiosPresent >= 2 ? "true" : "false");
    j += ",\"active_radio\":"; j += activeRadioIdx;
    j += ",\"radio_swaps\":"; j += radioSwaps;
    j += ",\"fhss_enabled\":"; j += (fhssEnabled ? "true" : "false");
    j += ",\"fhss_idx\":"; j += nextChannelIdx;
    j += ",\"fhss_channel\":"; j += FHSS_CHANNELS[nextChannelIdx];
    j += ",\"telemetry_item\":"; j += telemetryItem;
    j += ",\"id_broadcasting\":"; j += (idBroadcasting ? "true" : "false");
    j += ",\"being_flown\":"; j += (beingFlown ? "true" : "false");
    j += ",\"sbus_frames_out\":"; j += sbusFramesOut;
    j += ",\"failsafe_set\":"; j += (failsafeSet ? "true" : "false");
    { char gb[48]; snprintf(gb, sizeof(gb), ",\"gear_ratio\":%.3f", gearRatio); j += gb; }
    { char vb[112]; snprintf(vb, sizeof(vb), ",\"vbat\":{\"pin\":%u,\"volts\":%.2f,\"ratio\":%.2f,\"cells\":%u,\"auto\":%s}",
                            vbatPin, vbatVolts, vbatRatio, vbatCellsCfg, vbatAuto ? "true" : "false"); j += vb; }
    j += ",\"arming_channel\":"; j += armingChannel;
    j += ",\"autofly\":"; j += (autoFlyActive() ? "true" : "false");
    j += ",\"arm_auto\":"; j += ((armingChannel && !prefs.getUChar(NVS_KEY_ARM_CH, 0)) ? "true" : "false");
    // live armed state (so the config page can confirm the channel is right)
    { bool live = (rx.lastMillis != 0) && ((uint32_t)(millis() - rx.lastMillis) < 2000);
      bool armed = dongleEnabled ? (fcInfo.armed && fcInfo.armedMs && (uint32_t)(millis() - fcInfo.armedMs) < 5000)
                                 : (live && armingChannel >= 1 && armingChannel <= 16 && channelMicros[armingChannel - 1] > 1500);
      j += ",\"armed\":"; j += (armed ? "true" : "false"); }
    j += ",\"head_speed\":"; j += (uint32_t)((gearRatio > 0.1f ? fcTelem.fcMotorRPM / gearRatio : fcTelem.fcMotorRPM) + 0.5f);
    { char tb[48]; snprintf(tb, sizeof(tb), ",\"esc_temp_c\":%.1f", fcTelem.fcEscTempC); j += tb; }
    j += ",\"last_channel_ms\":";
    if (lastChannelDataMs) j += (uint32_t)(millis() - lastChannelDataMs); else j += "-1";

    // Per-flight link statistics (gaps in ms, frame rate derived on the client).
    {
        uint32_t durMs = (rx.lastMillis > linkStats.connStartMs) ? (rx.lastMillis - linkStats.connStartMs) : 0;
        uint32_t dMaxUs, dAvgUs, dHist[6], dAtMs;
        gapsForDisplay(dMaxUs, dAvgUs, dHist, dAtMs);   // shutdown artifact excluded once link is dead
        uint32_t dAtOff = (dAtMs > linkStats.connStartMs) ? (dAtMs - linkStats.connStartMs) : 0;
        char lb[300];
        snprintf(lb, sizeof(lb),
                 ",\"link\":{\"conn_ms\":%u,\"packets\":%u,\"max_gap_ms\":%.1f,\"avg_gap_ms\":%.2f,\"max_gap_at_ms\":%u,\"hist\":[%u,%u,%u,%u,%u,%u]"
                 ",\"expected_ms\":%.2f,\"gap_min_ms\":%u"
                 ",\"swaps\":%u,\"radio_ms\":[%u,%u,%u]}",
                 (unsigned)durMs, (unsigned)linkStats.packets,
                 dMaxUs / 1000.0f, dAvgUs / 1000.0f, (unsigned)dAtOff,
                 (unsigned)dHist[0], (unsigned)dHist[1], (unsigned)dHist[2],
                 (unsigned)dHist[3], (unsigned)dHist[4], (unsigned)dHist[5],
                 linkStats.expectedGapUs / 1000.0f, (unsigned)gapMinMs,
                 (unsigned)linkStats.flightSwaps,
                 (unsigned)(linkStats.radioMsAtLive[0] - linkStats.radioMsAtStart[0]),
                 (unsigned)(linkStats.radioMsAtLive[1] - linkStats.radioMsAtStart[1]),
                 (unsigned)(linkStats.radioMsAtLive[2] - linkStats.radioMsAtStart[2]));
        j += lb;
    }

    snprintf(buf, sizeof(buf), ",\"board_mac\":\"%02X%02X%02X%02X%02X%02X\"",
             boardMac[0], boardMac[1], boardMac[2], boardMac[3], boardMac[4], boardMac[5]);
    j += buf;

    // Last & max payload hex dumps (up to 32 bytes each)
    j += ",\"last_payload_len\":"; j += rx.lastPayload;
    j += ",\"last_payload\":\"";
    for (uint8_t i = 0; i < rx.lastPayload && i < 32; ++i) {
        snprintf(buf, sizeof(buf), "%02X ", rx.lastBytes[i]);
        j += buf;
    }
    j += "\"";
    j += ",\"max_payload_len\":"; j += rx.maxPayload;
    j += ",\"max_payload\":\"";
    for (uint8_t i = 0; i < rx.maxPayload && i < 32; ++i) {
        snprintf(buf, sizeof(buf), "%02X ", rx.maxBytes[i]);
        j += buf;
    }
    j += "\"";

    // Self-test
    j += ",\"self_test\":{";
    j += "\"verdict\":\""; j += rfTest.verdict; j += "\"";
    j += ",\"begin_ok\":"; j += (rfTest.beginOk ? "true" : "false");
    j += ",\"chip_connected\":"; j += (rfTest.chipConnected ? "true" : "false");
    j += ",\"channel_ok\":"; j += (rfTest.channelOk ? "true" : "false");
    j += ",\"data_rate_ok\":"; j += (rfTest.dataRateOk ? "true" : "false");
    j += ",\"channel_read\":"; j += rfTest.channelRead;
    j += ",\"data_rate_name\":\""; j += dataRateName(static_cast<rf24_datarate_e>(rfTest.dataRateRead)); j += "\"";
    j += "}}";

    // --- bind ---------------------------------------------------------
    j += ",\"bind\":{";
    j += "\"bound\":"; j += (bindState.bound ? "true" : "false");
    j += ",\"attempts\":"; j += bindState.attempts;
    snprintf(buf, sizeof(buf), ",\"pipe\":\"%02X %02X %02X %02X %02X\"",
             bindState.pipe[0], bindState.pipe[1], bindState.pipe[2], bindState.pipe[3], bindState.pipe[4]);
    j += buf;
    j += ",\"backup\":"; j += ((!bindState.bound && prefs.isKey(NVS_KEY_PIPE_BAK)) ? "true" : "false");
    j += ",\"bound_s_ago\":";
    if (bindState.bound && bindState.boundMillis) j += (uint32_t)((millis() - bindState.boundMillis) / 1000);
    else j += "0";
    j += "}";

    // --- protocol -----------------------------------------------------
    j += ",\"protocol\":{";
    j += "\"current\":\""; j += protocolName(currentProtocol); j += "\"";
    j += ",\"ppm_inverted\":"; j += (ppmInverted ? "true" : "false");
    j += ",\"crsf_hz\":"; j += crsfRateHz;
    j += ",\"fc_telem\":"; j += (fcTelemetryEnabled ? "true" : "false");
    j += ",\"thr_ch\":"; j += throttleChannel;
    j += ",\"wave_chs\":\"";
    {
        bool first = true;
        for (uint8_t c = 1; c <= 16; ++c)
            if (waveChannelMask & (1u << (c - 1))) {
                if (!first) j += ",";
                j += c; first = false;
            }
    }
    j += "\"";
    j += ",\"available\":[";
    // Display order — CRSF first (most-used), then the rest in enum order.
    static const Protocol DISPLAY_ORDER[] = { PROTO_CRSF, PROTO_SBUS, PROTO_IBUS, PROTO_PPM };
    for (size_t k = 0; k < sizeof(DISPLAY_ORDER) / sizeof(DISPLAY_ORDER[0]); ++k) {
        Protocol p = DISPLAY_ORDER[k];
        if (p > PROTO_MAX) continue;
        if (k > 0) j += ',';
        j += "{\"id\":"; j += (uint8_t)p;
        j += ",\"name\":\""; j += protocolName(p); j += "\"";
        j += ",\"desc\":\""; j += protocolDesc(p); j += "\"}";
    }
    j += "]}";

    // --- sim (drive simulator over USB) ------------------------------
    j += ",\"sim\":"; j += (simEnabled ? "true" : "false");
    j += ",\"dongle\":"; j += (dongleEnabled ? "true" : "false");
    // Simulator interface (0.9.757) - TOP LEVEL, beside dongle, which is where
    // dongle.html looks. It first went inside "fcinfo", where the page never
    // saw it, so the role could not display (found on DongleSim, 2026-09-18).
    // THE UPDATE RECORD (0.9.813): what the last install did, so a page can
    // SAY so instead of the pilot having to work it out.
    j += ",\"last_update\":{\"from\":\""; j += updFrom; j += "\",\"to\":\""; j += updTo;
    j += "\",\"stage\":\""; j += updStageName(updStage);
    j += "\",\"ok\":"; j += (updStage == UPD_DONE ? "true" : "false");
    j += ",\"fresh\":"; j += (updJustDone ? "true" : "false"); j += "}";
    j += ",\"role_auto\":";      j += (roleAuto ? "true" : "false");   // 0.9.812: the board chose this role itself
    j += ",\"sim_if\":";         j += (simIfEnabled ? "true" : "false");
    if (simIfEnabled) {
        j += ",\"sim_if_link\":\""; j += g_rcIn.protocolName(); j += "\"";
        j += ",\"sim_if_up\":";      j += (g_rcIn.linkUp() ? "true" : "false");
        j += ",\"sim_if_ch\":";      j += (int)g_rcIn.channelCount();
        j += ",\"sim_if_bytes\":";   j += (unsigned long)g_rcIn.bytesSeen();   // 0 = nothing on the wire (0.9.762)
        // 0.9.766: what each candidate saw, and the last bytes raw - so a
        // "not recognised" can be read from the phone instead of guessed at.
        j += ",\"sim_if_cand\":[";
        for (uint8_t i = 0; i < g_rcIn.candCount(); i++) {
            if (i) j += ',';
            j += "{\"p\":\""; j += g_rcIn.candName(i); j += "\",\"b\":"; j += (unsigned long)g_rcIn.candBytes(i);
            j += ",\"f\":"; j += (unsigned long)g_rcIn.candFrames(i); j += '}';
        }
        j += ']';
        { char hx[100]; g_rcIn.rawHex(hx, sizeof(hx)); j += ",\"sim_if_raw\":\""; j += hx; j += "\""; }
        // 0.9.767 wire finder: edges in 40 ms on D4, D5, D6 (see main.cpp).
        j += ",\"sim_if_edges\":["; j += (unsigned long)simIfEdges[0]; j += ','; j += (unsigned long)simIfEdges[1]; j += ','; j += (unsigned long)simIfEdges[2]; j += ']';
        j += ",\"sim_if_float\":["; j += (simIfFloat[0] ? "true" : "false"); j += ','; j += (simIfFloat[1] ? "true" : "false"); j += ','; j += (simIfFloat[2] ? "true" : "false"); j += ']';   // 0.9.772: pad open?
    }
    bleStateJson(j);
    UsbHostMsp::stateJson(j);   // dongle_link usb|uart, usb_fc, USB host counters (0.9.615/0.9.639)
    j += ",\"fc_link\":\""; j += UsbHostMsp::active() ? "usb" : dongleEnabled ? "uart" : (currentProtocol == PROTO_CRSF && fcTelemetryEnabled) ? "crsf" : "none"; j += "\"";   // which wire carries MSP now (0.9.640)
    { char db[200]; snprintf(db, sizeof(db), ",\"dongle_mode\":%u,\"dongle_auto\":%s,\"dongle_baud\":%lu,\"fc_armed\":%s,\"dongle_wire\":{\"bytes_in\":%lu,\"frames\":%lu,\"bad_crc\":%lu,\"dropped\":%lu,\"sends\":%lu}",
               (unsigned)dongleMode, dongleAuto ? "true" : "false", (unsigned long)dongleBaud,
               (fcInfo.armed && fcInfo.armedMs && (uint32_t)(millis() - fcInfo.armedMs) < 5000) ? "true" : "false",
               (unsigned long)mspSerBytes, (unsigned long)mspSer.frames, (unsigned long)mspSer.badCrc, (unsigned long)mspSer.dropped, (unsigned long)mspSendCount); j += db; }

    // --- proven-tune nudge (Malcolm 2026-08-07) -----------------------
    snprintf(buf, sizeof(buf), ",\"tune\":{\"gen\":%u,\"flights\":%u}",
             (unsigned)tuneEditGen, (unsigned)tuneFlightsSince);
    j += buf;

    // --- fc telemetry ------------------------------------------------
    j += ",\"fc\":{";
    j += "\"valid\":"; j += (fcTelem.valid ? "true" : "false");
    j += ",\"raw_total\":"; j += fcRawTotal;
    j += ",\"bytes\":"; j += fcTelem.bytesIn;
    j += ",\"frames\":"; j += fcTelem.framesParsed;
    j += ",\"crc_err\":"; j += fcTelem.crcErrors;
    j += ",\"responses\":"; j += fcTelem.responsesSent;
    j += ",\"last_frame_ms\":";
    if (fcTelem.lastFrameMs) j += (uint32_t)(millis() - fcTelem.lastFrameMs); else j += "-1";

    if (fcTelem.valid) {
        snprintf(buf, sizeof(buf), ",\"v\":%.2f,\"a\":%.2f,\"mah\":%u,\"pct\":%u,\"cells\":%u",
                 fcTelem.fcBattVolts, fcTelem.fcBattAmps,
                 (unsigned)fcTelem.fcBattMah, (unsigned)fcTelem.fcBattPct,
                 (unsigned)fcInfo.cells);   // 0 = unknown → page falls back to its guess
        j += buf;
        snprintf(buf, sizeof(buf), ",\"rssi\":%d,\"lq\":%u,\"snr\":%d",
                 (int)fcTelem.fcUplinkRssi, (unsigned)fcTelem.fcUplinkLq, (int)fcTelem.fcUplinkSnr);
        j += buf;
        snprintf(buf, sizeof(buf), ",\"pitch\":%d,\"roll\":%d,\"yaw\":%d",
                 fcTelem.attitudePitch, fcTelem.attitudeRoll, fcTelem.attitudeYaw);
        j += buf;
        j += ",\"flight_mode\":\"";
        for (const char* p = fcTelem.flightMode; *p; ++p) {
            if (*p == '"' || *p == '\\') j += '\\';
            j += *p;
        }
        j += "\"";
    } else {
        j += ",\"v\":0,\"a\":0,\"mah\":0,\"pct\":0,\"rssi\":0,\"lq\":0,\"snr\":0";
        j += ",\"pitch\":0,\"roll\":0,\"yaw\":0,\"flight_mode\":\"\"";
    }

    // Raw byte ring dump (oldest-to-newest)
    j += ",\"raw_dump\":\"";
    {
        uint16_t start = (fcRawCount < FC_RAW_RING_SIZE) ? 0 : fcRawHead;
        for (uint16_t i = 0; i < fcRawCount; ++i) {
            uint16_t idx = (uint16_t)((start + i) % FC_RAW_RING_SIZE);
            snprintf(buf, sizeof(buf), "%02X ", fcRawRing[idx]);
            j += buf;
        }
    }
    j += "\"";
    j += "}";

    // --- firmware (auto-update) --------------------------------------
    j += ",\"fw\":{";
    j += "\"manifest_url\":\""; {
        String u = prefs.isKey(NVS_KEY_FW_MANIFEST) ? prefs.getString(NVS_KEY_FW_MANIFEST, "") : "";
        for (size_t i = 0; i < u.length(); ++i) {
            char c = u[i];
            if (c == '"' || c == '\\') j += '\\';
            j += c;
        }
    } j += "\"";
    j += "}";

    // --- msp bridge --------------------------------------------------
    j += ",\"msp\":{";
    j += "\"started\":"; j += (mspBridgeStarted ? "true" : "false");
    j += ",\"active\":"; j += (mspBridgeActive ? "true" : "false");
    j += ",\"port\":"; j += MSP_BRIDGE_PORT;
    j += ",\"bytes_in\":"; j += mspBridgeBytesIn;
    j += ",\"bytes_out\":"; j += mspBridgeBytesOut;
    j += ",\"connections\":"; j += mspBridgeConnections;
    if (mspBridgeActive) {
        j += ",\"client_ip\":\""; j += mspClient.remoteIP().toString(); j += "\"";
        j += ",\"connected_s\":"; j += (uint32_t)((millis() - mspBridgeConnectMs) / 1000);
    }
    j += "}";

    // --- fc detection (MSP-over-CRSF probe) --------------------------
    j += ",\"fcinfo\":{";
    j += "\"detected\":"; j += (fcInfo.detected ? "true" : "false");
    j += ",\"variant\":\""; j += fcInfo.variant; j += "\"";
    j += ",\"version_known\":"; j += (fcInfo.versionKnown ? "true" : "false");
    j += ",\"fw_major\":"; j += fcInfo.fwMajor;
    j += ",\"fw_minor\":"; j += fcInfo.fwMinor;
    j += ",\"fw_patch\":"; j += fcInfo.fwPatch;
    j += ",\"msp_proto\":"; j += fcInfo.mspProto;
    j += ",\"api_major\":"; j += fcInfo.apiMajor;
    j += ",\"api_minor\":"; j += fcInfo.apiMinor;
    j += ",\"probes_sent\":"; j += fcInfo.probesSent;
    j += ",\"last_response_ms\":";
    if (fcInfo.lastResponseMs) j += (uint32_t)(millis() - fcInfo.lastResponseMs); else j += "-1";
    j += ",\"rotorflight_capable\":"; j += (fcIsRotorflightConfigCapable() ? "true" : "false");
    j += ",\"rf_major\":"; j += rotorflightMajor();
    j += ",\"rf_minor\":"; j += rotorflightMinor();
    // Governor throttle watch (0.9.551): what the FC's governor listens to
    // and the verdict of the last long armed spell (0 = fine).
    j += ",\"throttle_ch\":"; j += fcInfo.throttleCh;
    j += ",\"gov_mode\":"; j += fcInfo.govMode;
    j += ",\"gov_thr_parked\":"; j += govThrParkedPct;
    j += ",\"gov_thr_max\":"; j += govThrMaxPct;
    // Telemetry setup watch (0.9.556): what MSP 73 said, and the verdict.
    // Bank put-back (0.9.567): where the FC is, what the switch had, held?
    j += ",\"bank_fc_pid\":";     j += (banks.fcPid  == 0xFF ? -1 : (int)banks.fcPid);
    j += ",\"bank_fc_rate\":";    j += (banks.fcRate == 0xFF ? -1 : (int)banks.fcRate);
    j += ",\"bank_switch_pid\":"; j += (banks.switchPid  == 0xFF ? -1 : (int)banks.switchPid);
    j += ",\"bank_switch_rate\":";j += (banks.switchRate == 0xFF ? -1 : (int)banks.switchRate);
    j += ",\"bank_hold\":";       j += (bankHeld() ? "true" : "false");
    j += ",\"bank_put_backs\":";  j += banks.putBacks;
    // How many banks this flight controller REALLY has (0.9.742). Rotorflight
    // builds them from flash size, so the two counts can differ: >256 kB gives
    // 6 and 6, >128 kB gives 3 PID banks but still 6 rate banks, smaller still
    // 2 and 3 (upstream common_pre.h). The pages offered 4 of each for years,
    // which hid banks 5 and 6 on every full-size board. Read from MSP 101.
    j += ",\"sim_if\":";         j += (simIfEnabled ? "true" : "false");
    if (simIfEnabled) {
        j += ",\"sim_if_link\":\""; j += g_rcIn.protocolName(); j += "\"";
        j += ",\"sim_if_up\":";      j += (g_rcIn.linkUp() ? "true" : "false");
        j += ",\"sim_if_ch\":";      j += (int)g_rcIn.channelCount();
        j += ",\"sim_if_bytes\":";   j += (unsigned long)g_rcIn.bytesSeen();   // 0 = nothing on the wire (0.9.762)
    }
    j += ",\"pid_banks\":";       j += (int)banks.pidCount;
    j += ",\"rate_banks\":";      j += (int)banks.rateCount;
    j += ",\"banks_shown\":";     j += (int)fcInfo.banksShown;   // 0 = all of them
    j += ",\"telem_cfg_known\":"; j += (fcInfo.telemCfgKnown ? "true" : "false");
    j += ",\"telem_cfg_bad\":";   j += (fcTelemCfgBad() ? "true" : "false");
    j += ",\"telem_sensors\":";   j += fcInfo.telemSensors;
    j += ",\"telem_mode\":";      j += fcInfo.telemMode;
    j += ",\"telem_rate\":";      j += fcInfo.telemRate;
    j += ",\"telem_ratio\":";     j += fcInfo.telemRatio;
    // Telemetry speed (0.9.563): the receiver's setting vs what the FC runs,
    // plus the guard's state (a cached good copy, RAM repairs this boot).
    j += ",\"telem_speed_pref\":\""; j += (fcInfo.telemSpeedPref ? "fast" : "standard"); j += '"';
    j += ",\"telem_speed_live\":\""; j += (fcInfo.telemCfgKnown ? telemSpeedName(fcInfo.telemRate, fcInfo.telemRatio) : "unknown"); j += '"';
    j += ",\"telem_good_cached\":"; j += (fcInfo.telemGoodValid ? "true" : "false");
    j += ",\"telem_repairs\":";    j += fcInfo.telemRepairs;
    j += ",\"telem_checked_ago\":";
    if (fcInfo.telemCheckedMs) j += (uint32_t)(millis() - fcInfo.telemCheckedMs); else j += "-1";
    j += "}";

    // --- channels ----------------------------------------------------
    j += ",\"channels\":[";
    for (int i = 0; i < 16; ++i) {
        if (i) j += ',';
        j += channelMicros[i];
    }
    j += "]}";

    server.send(200, "application/json", j);
}

//*********************************************************************
//  Route registration (call from setup())
//*********************************************************************

// Rotorflight's command line over the dongle's USB link (Malcolm 2026-09-11:
// "add the options which were not possible without USB"). One command per
// request; the first request opens the CLI ('#'). Never over a UART or a
// radio link: the reply would be telemetry-shaped garbage and MSP would die.
inline void handleCliApi() {
    server.sendHeader("Cache-Control", "no-store");
    if (!UsbHostMsp::active()) { server.send(409, "text/plain", "needs the USB connection: plug the flight controller's USB socket into the dongle or receiver"); return; }
    if (refuseIfTxLinked("turn the transmitter off first - the command line pauses the receiver, and save or exit restarts the flight controller")) return;
    if (fcInfo.armed && fcInfo.armedMs && (uint32_t)(millis() - fcInfo.armedMs) < 5000) { server.send(409, "text/plain", "ARMED - disarm first"); return; }
    String cmd = server.hasArg("cmd") ? server.arg("cmd") : String("");
    cmd.trim();
    if (cmd.length() > 160) { server.send(400, "text/plain", "command too long"); return; }
    if (cmd.equalsIgnoreCase("save") || cmd.equalsIgnoreCase("exit") || cmd.equalsIgnoreCase("reboot") || cmd.equalsIgnoreCase("msc") || cmd.startsWith("dfu") || cmd.startsWith("bl")) {
        server.send(400, "text/plain", "use the Save / Leave buttons for that"); return;
    }
    if (!UsbHostMsp::cliMode && !UsbHostMsp::cliEnter(2500)) { server.send(504, "text/plain", "the flight controller did not open its command line"); return; }
    if (cmd.length() == 0) { server.send(200, "text/plain", "CLI open"); return; }
    String out;
    const bool ok = UsbHostMsp::cliExchange(cmd, out, 6000);
    if (!ok && out.length() == 0) { server.send(504, "text/plain", "no reply from the flight controller"); return; }
    server.send(200, "text/plain", out);
}
inline void handleCliLeave() {
    if (refuseIfArmed("leave the command line")) return;   // 2026-09-16 review: on a dongle the TX-link gates are no-ops
    server.sendHeader("Cache-Control", "no-store");
    if (!UsbHostMsp::cliMode) { server.send(200, "text/plain", "the command line was not open"); return; }
    if (refuseIfTxLinked("turn the transmitter off first - leaving the command line restarts the flight controller")) return;
    const bool save = server.hasArg("save") && server.arg("save") == "1";
    UsbHostMsp::cliLeave(save);
    fcInfo.telemCfgKnown = false;  fcInfo.telemCfgTries = 0;   // the FC restarts: fresh look at everything
    server.send(200, "text/plain", save ? "saved - the flight controller is restarting" : "left without saving - the flight controller is restarting");
}

inline void registerWebRoutes() {
    // WebServer only captures request headers it's told to collect. Without
    // this, If-None-Match never reaches serveLittleFsFile and the ETag/304
    // fast path silently never fires (every asset re-streams every load).
    static const char* collectHdrs[] = { "If-None-Match" };
    server.collectHeaders(collectHdrs, 1);

    // Static GET pages (served from LittleFS)
    server.on("/",            handleRoot);
    server.on("/fly",         handleFly);
    server.on("/fly_disarm",   HTTP_POST, handleFlyDisarm);
    server.on("/diagnostics", handleDiagnostics);
    server.on("/rxsettings",  handleRxSettings);
    server.on("/blackbox",    handleBlackbox);
    server.on("/bind",        HTTP_GET,  handleBind);
    server.on("/firmware",    handleFirmware);
    server.on("/wifi",        HTTP_GET,  handleWifi);
    server.on("/protocol",    HTTP_GET,  handleProtocolPage);
    server.on("/setup",       HTTP_GET,  handleSetupPage);
    server.on("/sim",         HTTP_GET,  handleSimPage);
    server.on("/flight",      HTTP_GET,  handleFlightPage);
    server.on("/events",      HTTP_GET,  handleEventsPage);
    server.on("/rotorflight",     handleRotorflight);
    server.on("/rotorflight-pid",     handleRotorflightPid);
    server.on("/rotorflight-servos",  handleRotorflightServos);
    server.on("/rotorflight-rescue",  handleRotorflightRescue);
    server.on("/rotorflight-modes",   handleRotorflightModes);
    server.on("/rotorflight-firsttime", handleRotorflightFirstTime);
    server.on("/rotorflight-newheli",   handleRotorflightNewHeli);
    server.on("/rotorflight-wiring",    handleRotorflightWiring);
    server.on("/rotorflight-computer",  handleRotorflightComputer);
    server.on("/rotorflight-esc",       handleRotorflightEsc);
    server.on("/rotorflight-gear",      handleRotorflightGear);
    server.on("/rotorflight-blackbox",  handleRotorflightBlackbox);
    server.on("/rotorflight-escprog",   handleRotorflightEscProg);
    server.on("/api/fc/wake", HTTP_POST, handleFcWake);
    server.on("/api/fc/telemetry/restore", HTTP_POST, handleFcTelemRestore);
    server.on("/api/fc/telemetry/speed",   HTTP_POST, handleFcTelemSpeed);
    server.on("/api/fc/banks",             HTTP_POST, handleFcBanksShown);
    server.on("/api/banks.json",           HTTP_GET,  handleBanksJson);
    server.on("/api/esc/catch", HTTP_POST, handleEscCatchArm);
    server.on("/api/esc/catch", HTTP_GET,  handleEscCatchStatus);
    server.on("/rotorflight-tuning",    handleRotorflightTuning);
    server.on("/rotorflight-txchannels", handleRotorflightTxChannels);
    server.on("/rotorflight-wizards",   handleRotorflightWizards);
    server.on("/rotorflight-alacarte",  handleRotorflightAlaCarte);
    server.on("/rotorflight-adjustments", []() { if (!serveLittleFsFile("/rotorflight-adjustments.html", "text/html")) server.send(503, "text/plain", "page missing - update the web files"); });
    server.on("/rotorflight-ports", []() { if (!serveLittleFsFile("/rotorflight-ports.html", "text/html")) server.send(503, "text/plain", "page missing - update the web files"); });
    server.on("/rotorflight-filters", []() { if (!serveLittleFsFile("/rotorflight-filters.html", "text/html")) server.send(503, "text/plain", "page missing - update the web files"); });
    server.on("/cli",                   []() { if (!serveLittleFsFile("/cli.html", "text/html")) server.send(503, "text/plain", "page missing - update the web files"); });
    server.on("/api/cli",               handleCliApi);          // USB only: one Rotorflight command, its printed reply
    server.on("/api/cli/leave",         HTTP_POST, handleCliLeave);
    server.on("/rotorflight-backup",    handleRotorflightBackupPage);
    server.on("/rotorflight-copybank",  handleRotorflightCopyBank);
    server.on("/rotorflight-easy",      handleRotorflightEasy);
    server.on("/search",                handleSearchPage);
    server.on("/search.js",             handleSearchJs);
    server.on("/rotorflight-pidplus", handleRotorflightPidPlus);
    server.on("/rotorflight-rates",        handleRotorflightRates);
    server.on("/rotorflight-gov-profile",  handleRotorflightGovProfile);
    server.on("/rotorflight-gov-global",   handleRotorflightGovGlobal);
    server.on("/rotorflight-travel",       handleRotorflightTravel);
    server.on("/rotorflight-backups",      handleRotorflightBackups);
    server.on("/api/backup/list",          HTTP_GET,  handleBackupList);
    server.on("/api/backup/load",          HTTP_GET,  handleBackupLoad);
    server.on("/api/backup/save",          HTTP_POST, handleBackupSave);
    server.on("/api/backup/delete",        HTTP_POST, handleBackupDelete);
    server.on("/api/msp",         HTTP_GET, handleMspApi);

    // Auto-update endpoints.
    server.on("/api/time",             HTTP_POST, handleTimeSync);
    server.on("/api/gapmin",           HTTP_POST, handleGapMin);
    server.on("/api/flight/delete",    HTTP_POST, handleFlightDelete);
    server.on("/api/firmware/seturl",  HTTP_POST, handleFirmwareSetUrl);
    server.on("/api/firmware/check",   HTTP_GET,  handleFirmwareCheck);
    server.on("/api/firmware/install", HTTP_POST, handleFirmwareInstall);
    server.on("/api/bleota/begin",   HTTP_POST, handleBleOtaBegin);
    server.on("/api/bleota/status",  HTTP_GET,  handleBleOtaStatus);
    server.on("/api/bleota/end",     HTTP_POST, handleBleOtaEnd);
    server.on("/api/bleota/reboot",  HTTP_POST, handleBleOtaReboot);

    // Shared assets
    server.on("/style.css",         handleStyleCss);
    server.on("/app.js",            handleAppJs);
    server.on("/gear.js",           handleGearJs);
    server.on("/three.min.js",      handleThreeJs);
    server.on("/flying-field.svg",  handleFlyingFieldSvg);
    server.on("/flying-field.jpg",  handleFlyingFieldJpg);
    server.on("/wizard.jpg",        handleWizardJpg);

    // JSON APIs
    server.on("/api/state.json",    handleApiState);
    server.on("/api/channels.json", handleApiChannels);
    server.on("/api/channels.stream", HTTP_GET, handleChannelStream);
    server.on("/api/flightlog.json", handleApiFlightLog);
    server.on("/api/flights.json",   handleApiFlights);
    server.on("/api/events.json",   handleApiEvents);
    server.on("/api/events-prev.json", handleApiEventsPrev);
    server.on("/map",               handleMap);          // sim channel-remap page
    server.on("/api/simmap.json",   handleApiSimMap);    // current sim channel map
    server.on("/simctl",               handleSimCtl);       // sim-function buttons page
    server.on("/views",                handleViews);        // camera/view keystroke page
    server.on("/api/sim/buttons.json", handleApiSimButtons);// live sim-button states

    // POSTs that reboot
    server.on("/bind",        HTTP_POST, handleBindDo);
    server.on("/api/bind/cancel", HTTP_POST, handleBindCancel);
    server.on("/rollback",    HTTP_POST, handleRollback);
    server.on("/wifi",        HTTP_POST, handleWifiSet);
    // /wifi_reset was the "Forget & reboot" button — removed 2026-05-27
    // because an accidental tap silently wiped saved credentials. Left
    // here as a 410 so stale bookmarks fail loudly instead of silently.
    server.on("/wifi_reset",      HTTP_POST, handleWifiResetGone);
    server.on("/api/name",        HTTP_POST, handleNameSet);
    server.on("/api/firstrun",      HTTP_POST, handleFirstRun);
    server.on("/api/factory-reset", HTTP_POST, handleFactoryReset);
    server.on("/api/failsafe/save",  HTTP_POST, handleFailsafeSave);
    server.on("/api/failsafe/clear", HTTP_POST, handleFailsafeClear);
    server.on("/api/gear",           HTTP_POST, handleGearSet);
    server.on("/api/vbat",           HTTP_POST, handleVbatSet);
    server.on("/api/armch",          HTTP_POST, handleArmChSet);
    server.on("/protocol",    HTTP_POST, handleProtocolSet);
    server.on("/api/sim",     HTTP_POST, handleSimSet);
    server.on("/api/dongle",  HTTP_POST, handleDongleSet);
    server.on("/dongle",      HTTP_GET,  handleDonglePage);
    server.on("/api/sim/spool.json", HTTP_GET,  handleSimSpoolGet);
    server.on("/api/sim/spool",      HTTP_POST, handleSimSpoolSet);
    server.on("/api/map",     HTTP_POST, handleMapSave);   // save sim channel map (applies live, no reboot)
    server.on("/api/sim/button", HTTP_POST, handleSimButton); // pulse a sim-function button (1..8)
    server.on("/api/sim/key",    HTTP_POST, handleSimKey);    // send a camera/view keystroke
    server.on("/fly_arm",     HTTP_POST, handleFlyArm);
    server.on("/api/autofly", HTTP_GET,  handleAutoFlyGet);
    server.on("/api/autofly", HTTP_POST, handleAutoFlySet);

    // Misc
    server.on("/retest",      handleRetest);
    server.on("/reboot",      handleReboot);
    server.on("/api/wave",    HTTP_POST, handleWaveNow);
    server.on("/ping", [](){
        // Tiny endpoint to keep iOS's TCP/WiFi state warm. No allocations.
        server.sendHeader("Cache-Control", "no-store");
        server.send(200, "text/plain", "ok");
    });
    server.onNotFound([]() { server.send(404, "text/plain", "not found"); });
}

#undef server

#endif // _SRC_WEBPAGES_H
