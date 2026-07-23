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
    if (!LittleFS.exists(path)) return false;
    File f = LittleFS.open(path, "r");
    if (!f) return false;
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

inline void handleRotorflightRates() {
    if (serveLittleFsFile("/rotorflight-rates.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-rates.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightGovProfile() {
    if (serveLittleFsFile("/rotorflight-gov-profile.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-gov-profile.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightGovGlobal() {
    if (serveLittleFsFile("/rotorflight-gov-global.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-gov-global.html missing — uploadfs the data/ folder");
}

inline void handleRotorflightBackups() {
    if (serveLittleFsFile("/rotorflight-backups.html", "text/html")) return;
    server.send(503, "text/plain", "/rotorflight-backups.html missing — uploadfs the data/ folder");
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

inline void handleMspApi() {
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
            protocolRx();       // feed CRSF RX so the async response can land
            txParamsLoop();     // advance the TX-param machine
            delay(1);
        }
        if (txParamBusy) {
            server.send(503, "text/plain", "receiver busy with a transmitter edit — try again");
            return;
        }
    }

    uint8_t  respBuf[256];
    uint16_t respLen = 0;
    // 400 ms timeout: was 150 ms but read-failed too often. FC normally
    // responds in <50 ms, but if a periodic mspFcPoll probe queued behind
    // our request, the FC processes it first and ours can take longer.
    // (mspFcPoll is now blocked while a sync wait is in flight, but this
    // also handles the case where the user starts a new wait while a
    // probe response is mid-flight on the wire.)
    bool ok = mspRequestAndWait(fn, reqBuf, reqLen, respBuf, &respLen, 400);
    if (!ok) { server.send(504, "text/plain", "flight controller did not respond within 400 ms"); return; }

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
        return http.begin(secure, url);
    }
    return http.begin(plain, url);
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
    String body = http.getString();
    http.end();
    // Guard against an oversized manifest. Versions accumulate, and proxying two
    // full manifests (~95 entries each, with notes = 76 KB) choked the response —
    // blocking the single-threaded server and failing the check. Skip a manifest
    // that's still too big rather than try to build a giant JSON. (Keep manifests
    // trimmed to recent versions — see dev/stage_website.py / firmware_server.py.)
    if (body.length() > 18000) {
        out += ",\"ok\":false,\"error\":\"manifest too large (";
        out += (int)body.length();
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

// Download `url` and flash it to the given Update target — U_FLASH (the app/OTA
// slot) or U_SPIFFS (the LittleFS data partition). Returns "" on success, else a
// short error string. Streamed: nothing is committed unless the full image lands.
inline String flashStreamToPartition(const String& url, int command) {
    HTTPClient       http;
    WiFiClient       plain;
    WiFiClientSecure secure;
    // Generous timeouts — a slow messiter.com TLS handshake on a weak WiFi link
    // can take a few seconds before the first bytes flow.
    http.setConnectTimeout(8000);
    http.setTimeout(15000);
    if (!httpBeginAny(http, plain, secure, url)) return "begin failed";
    int code = http.GET();
    if (code != HTTP_CODE_OK) {
        http.end();
        char m[40]; snprintf(m, sizeof m, "HTTP %d", code);
        return String(m);
    }
    int len = http.getSize();
    if (len <= 0) { http.end(); return "no content-length"; }
    if (!Update.begin((size_t)len, command)) { String e = Update.errorString(); http.end(); return e; }
    size_t written = Update.writeStream(*http.getStreamPtr());
    if (written != (size_t)len) {
        Update.end(); http.end();
        char m[48]; snprintf(m, sizeof m, "short write %u/%d", (unsigned)written, len);
        return String(m);
    }
    if (!Update.end(true)) { String e = Update.errorString(); http.end(); return e; }
    http.end();
    return "";
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

inline void safeOutputParkAndRestart();   // defined below (bind section)

//*********************************************************************
//  BLE OTA push — the app downloads with the PHONE's internet (5G!) and
//  streams raw chunks over the BLE link (see BleConfig.h's 0xA5 lane).
//*********************************************************************

inline void handleBleOtaBegin() {
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
        LittleFS.end();
        littleFsMounted = false;
    }
    if (!Update.begin(size, bleOtaCmd)) {
        String e = Update.errorString();
        if (bleOtaCmd == U_SPIFFS) {
            littleFsMounted = LittleFS.begin(false) || LittleFS.begin(true);
            restoreBackupsFromRam();
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
        littleFsMounted = LittleFS.begin(false) || LittleFS.begin(true);
        int restored = restoreBackupsFromRam();
        char m[64]; snprintf(m, sizeof(m), "BLE OTA web files: %s (%d backups kept)", ok ? "done" : "FAILED", restored);
        events.add(m);
    } else {
        events.add(ok ? "BLE OTA firmware: flashed OK" : "BLE OTA firmware: FAILED");
    }
    server.sendHeader("Cache-Control", "no-store");
    if (ok) server.send(200, "application/json", "{\"ok\":true}");
    else    server.send(500, "application/json", String("{\"ok\":false,\"error\":\"") + err + "\"}");
}

inline void handleBleOtaReboot() {
    prefs.putUChar(NVS_KEY_CFG_REBOOT, 1);   // config reboot: skip the RF window so BLE advertising returns and the app can reconnect + confirm
    server.send(200, "application/json", "{\"ok\":true,\"rebooting\":true}");
    bleEarlyPump();          // push the reply out over BLE before the radio dies
    delay(300);
    safeOutputParkAndRestart();   // throttle-low frames + parked pin — no prop blip
}

// Update the web/data filesystem (LittleFS) from fsUrl WITHOUT losing the user's
// /backups/*.json. The whole partition is overwritten by the new image, so we
// snapshot the backups (max 20 × ~1.5 KB — tiny) into RAM first, flash, re-mount,
// and write them back. Non-fatal: the firmware is already in place, so whatever
// happens here we still reboot. Returns a short status note for the reply/log.
inline String updateFilesystemKeepingBackups(const String& fsUrl) {
    // Open the FS image and confirm it's really there BEFORE touching anything — so
    // a release that ships no littlefs.bin (404) is a clean no-op that never disturbs
    // the live filesystem or the backups. (This is what makes deriving the URL safe.)
    HTTPClient       http;
    WiFiClient       plain;
    WiFiClientSecure secure;
    http.setConnectTimeout(8000);
    http.setTimeout(15000);
    if (!httpBeginAny(http, plain, secure, fsUrl)) return "";
    if (http.GET() != HTTP_CODE_OK) { http.end(); return ""; }   // no FS for this release
    int len = http.getSize();
    if (len <= 0) { http.end(); return ""; }

    // 1) Snapshot the user's backups (old FS still mounted).
    snapshotBackupsToRam();
    int n = g_fsBackupCount;

    // 2) Unmount + flash the new image straight from the open stream.
    LittleFS.end();
    bool ok = Update.begin((size_t)len, U_SPIFFS)
              && Update.writeStream(*http.getStreamPtr()) == (size_t)len
              && Update.end(true);
    String err = ok ? String("") : String(Update.errorString());
    http.end();

    // 3) Re-mount (format only if the freshly-written image won't mount), restore backups.
    bool mounted = LittleFS.begin(false) || LittleFS.begin(true);
    littleFsMounted = mounted;
    int restored = restoreBackupsFromRam();
    char m[96];
    if (err.length())
        snprintf(m, sizeof m, " (web files FAILED: %s; %d/%d backups kept)", err.c_str(), restored, n);
    else
        snprintf(m, sizeof m, " + web files (%d backups preserved)", restored);
    return String(m);
}

inline void handleFirmwareInstall() {
    if (netMode != NET_WIFI_UP) {
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

    // 1) Application firmware -> OTA app slot. A mid-stream failure just leaves the
    //    current firmware bootable, so report it and DON'T reboot.
    String err = flashStreamToPartition(url, U_FLASH);
    if (err.length()) {
        server.send(502, "text/plain", "firmware: " + err);
        return;
    }

    // 2) Matching web/data filesystem, if the release ships one (fs_url). Flashing
    //    it makes the web UI travel with the firmware — even on a jump up from an
    //    old version — while preserving the user's Rotorflight backups.
    String fsNote = "";
    if (fsUrl.length() && (fsUrl.startsWith("http://") || isHttpsUrl(fsUrl))) {
        fsNote = updateFilesystemKeepingBackups(fsUrl);
    }
    events.add((String("Firmware installed via auto-update") + fsNote + " — rebooting").c_str());
    server.send(200, "text/plain", String("ok — rebooting") + fsNote);
    bleEarlyPump();               // over BLE: deliver the reply before the reboot kills the link
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
    for (int i = 0; i < 12; ++i) { sbusTick(); delay(8); }     // ~100 ms of throttle-low frames
    Serial1.flush();
    Serial1.end();
    pinMode(PIN_SBUS_TX, INPUT_PULLUP); // idle-HIGH through the restart — silence, not noise
    delay(50);
    ESP.restart();
}

inline void handleBindDo() {
    clearBindNvs();
    String body = confirmPage("Rebooting",
        "<p>Bind cleared. The receiver is rebooting and will listen on DefaultPipe within ~5 seconds.</p>"
        "<p><a href='/'>Back to home</a> (reload after the chip is back)</p>");
    server.send(200, "text/html", body);
    delay(400);
    safeOutputParkAndRestart();
}

//*********************************************************************
//  POST /rollback — switch OTA slot and reboot
//*********************************************************************

inline void handleRollback() {
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
    ESP.restart();
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
    ESP.restart();
}

//*********************************************************************
//  POST /api/name — set the model name (e.g. "Goblin 700") and reboot
//*********************************************************************
// Empty name = clear the override and revert to the "RXV2-XXXX"
// default (last-4-hex of MAC). Limited to 30 characters so it fits in
// AP SSID + hostname budgets and stays readable in page titles.

inline void handleNameSet() {
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
    prefs.putUChar(NVS_KEY_CFG_REBOOT, 1);   // config reboot: come straight back to WiFi even if a TX is on
    delay(500);
    ESP.restart();
}

//*********************************************************************
//  POST /wifi — save WiFi credentials and reboot
//*********************************************************************

inline void handleWifiSet() {
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
    ESP.restart();
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
    saveFailsafeToNvs();
    events.add("Failsafe captured from current channels");
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", "{\"ok\":true,\"failsafe_set\":true}");
}

inline void handleFailsafeClear() {
    clearFailsafeNvs();
    events.add("Failsafe cleared");
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", "{\"ok\":true,\"failsafe_set\":false}");
}

//*********************************************************************
//  POST /api/gear?ratio=<float>  — set the head-speed gear ratio
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
        vbatVolts = 0.0f;          // restart smoothing on the new pin
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
        vbatVolts = 0.0f;
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
    safeOutputParkAndRestart();
}

//*********************************************************************
//  POST /api/sim — toggle "drive simulator over USB" and reboot
//*********************************************************************
// Persists the flag; it takes effect at boot in setup(). USB mode is fixed at
// compile time, so the HID joystick can only be brought up on a fresh boot —
// the same reboot-to-apply model the output-protocol setting uses.
inline void handleSimSet() {
    bool on = server.hasArg("on") ? (server.arg("on").toInt() != 0) : false;
    prefs.putUChar(NVS_KEY_SIM, on ? 1 : 0);
    prefs.putUChar(NVS_KEY_CFG_REBOOT, 1);   // come straight back to WiFi (skip RF window)
    events.add(on ? "Sim-over-USB enabled" : "Sim-over-USB disabled");
    server.send(200, "text/html", confirmPage("Saved & rebooting", on
        ? "<p>Simulator-over-USB <b>enabled</b>. The receiver is rebooting; plug it into your "
          "computer and it appears as a USB joystick driven by your sticks.</p>"
        : "<p>Simulator-over-USB <b>disabled</b>. The receiver is rebooting back to normal.</p>"));
    delay(250);
    safeOutputParkAndRestart();
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
    server.send(200, "text/plain", "ok — rebooting, radios return in ~15 s");
    bleEarlyPump();
    delay(300);
    ESP.restart();
}

//*********************************************************************
//  GET /reboot — soft reset
//*********************************************************************

inline void handleReboot() {
    server.send(200, "text/html", confirmPage("Rebooting",
        "<p>Back in ~5 s.</p>"));
    delay(400);
    safeOutputParkAndRestart();
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
//  /api/channels.json — tiny endpoint just for the live channel viewer
//*********************************************************************
// Polled at ~10 Hz by data/diagnostics.html. Returns the 16 decoded
// channel uS values plus the age of the most recent RC frame so the
// page can grey the bars out when the signal drops.

inline void handleApiChannels() {
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
    j += ",\"hostname\":\""; j += g_hostname; j += "\"";
    j += ",\"ip\":\""; j += WiFi.localIP().toString(); j += "\"";
    j += ",\"mac\":\""; j += WiFi.macAddress(); j += "\"";
    j += ",\"rssi\":"; j += (netMode == NET_WIFI_UP ? (int)WiFi.RSSI() : 0);
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
    // live armed state (so the config page can confirm the channel is right)
    { bool live = (rx.lastMillis != 0) && ((uint32_t)(millis() - rx.lastMillis) < 2000);
      bool armed = live && armingChannel >= 1 && armingChannel <= 16 && channelMicros[armingChannel - 1] > 1500;
      j += ",\"armed\":"; j += (armed ? "true" : "false"); }
    j += ",\"head_speed\":"; j += (uint32_t)((gearRatio > 0.1f ? fcTelem.fcMotorRPM / gearRatio : fcTelem.fcMotorRPM) + 0.5f);
    { char tb[48]; snprintf(tb, sizeof(tb), ",\"esc_temp_c\":%.1f", fcTelem.fcEscTempC); j += tb; }
    j += ",\"last_channel_ms\":";
    if (lastChannelDataMs) j += (uint32_t)(millis() - lastChannelDataMs); else j += "-1";

    // Per-flight link statistics (gaps in ms, frame rate derived on the client).
    {
        uint32_t durMs = (rx.lastMillis > linkStats.connStartMs) ? (rx.lastMillis - linkStats.connStartMs) : 0;
        uint32_t dMaxUs, dAvgUs, dHist[6];
        gapsForDisplay(dMaxUs, dAvgUs, dHist);   // shutdown artifact excluded once link is dead
        char lb[300];
        snprintf(lb, sizeof(lb),
                 ",\"link\":{\"conn_ms\":%u,\"packets\":%u,\"max_gap_ms\":%.1f,\"avg_gap_ms\":%.2f,\"hist\":[%u,%u,%u,%u,%u,%u]"
                 ",\"swaps\":%u,\"radio_ms\":[%u,%u,%u]}",
                 (unsigned)durMs, (unsigned)linkStats.packets,
                 dMaxUs / 1000.0f, dAvgUs / 1000.0f,
                 (unsigned)dHist[0], (unsigned)dHist[1], (unsigned)dHist[2],
                 (unsigned)dHist[3], (unsigned)dHist[4], (unsigned)dHist[5],
                 (unsigned)(radioSwaps - linkStats.swapsAtStart),
                 (unsigned)(radioActiveMs[0] - linkStats.radioMsAtStart[0]),
                 (unsigned)(radioActiveMs[1] - linkStats.radioMsAtStart[1]),
                 (unsigned)(radioActiveMs[2] - linkStats.radioMsAtStart[2]));
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
        snprintf(buf, sizeof(buf), ",\"v\":%.2f,\"a\":%.2f,\"mah\":%u,\"pct\":%u",
                 fcTelem.fcBattVolts, fcTelem.fcBattAmps,
                 (unsigned)fcTelem.fcBattMah, (unsigned)fcTelem.fcBattPct);
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
    server.on("/rotorflight-pidplus", handleRotorflightPidPlus);
    server.on("/rotorflight-rates",        handleRotorflightRates);
    server.on("/rotorflight-gov-profile",  handleRotorflightGovProfile);
    server.on("/rotorflight-gov-global",   handleRotorflightGovGlobal);
    server.on("/rotorflight-backups",      handleRotorflightBackups);
    server.on("/api/backup/list",          HTTP_GET,  handleBackupList);
    server.on("/api/backup/load",          HTTP_GET,  handleBackupLoad);
    server.on("/api/backup/save",          HTTP_POST, handleBackupSave);
    server.on("/api/backup/delete",        HTTP_POST, handleBackupDelete);
    server.on("/api/msp",         HTTP_GET, handleMspApi);

    // Auto-update endpoints.
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
    server.on("/three.min.js",      handleThreeJs);
    server.on("/flying-field.svg",  handleFlyingFieldSvg);
    server.on("/flying-field.jpg",  handleFlyingFieldJpg);

    // JSON APIs
    server.on("/api/state.json",    handleApiState);
    server.on("/api/channels.json", handleApiChannels);
    server.on("/api/channels.stream", HTTP_GET, handleChannelStream);
    server.on("/api/flightlog.json", handleApiFlightLog);
    server.on("/api/flights.json",   handleApiFlights);
    server.on("/api/events.json",   handleApiEvents);
    server.on("/map",               handleMap);          // sim channel-remap page
    server.on("/api/simmap.json",   handleApiSimMap);    // current sim channel map
    server.on("/simctl",               handleSimCtl);       // sim-function buttons page
    server.on("/views",                handleViews);        // camera/view keystroke page
    server.on("/api/sim/buttons.json", handleApiSimButtons);// live sim-button states

    // POSTs that reboot
    server.on("/bind",        HTTP_POST, handleBindDo);
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
    server.on("/api/map",     HTTP_POST, handleMapSave);   // save sim channel map (applies live, no reboot)
    server.on("/api/sim/button", HTTP_POST, handleSimButton); // pulse a sim-function button (1..8)
    server.on("/api/sim/key",    HTTP_POST, handleSimKey);    // send a camera/view keystroke
    server.on("/fly_arm",     HTTP_POST, handleFlyArm);

    // Misc
    server.on("/retest",      handleRetest);
    server.on("/reboot",      handleReboot);
    server.on("/ping", [](){
        // Tiny endpoint to keep iOS's TCP/WiFi state warm. No allocations.
        server.sendHeader("Cache-Control", "no-store");
        server.send(200, "text/plain", "ok");
    });
    server.onNotFound([]() { server.send(404, "text/plain", "not found"); });
}

#undef server

#endif // _SRC_WEBPAGES_H
