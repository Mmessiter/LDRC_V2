// (From the review of 29-9-2026, kept as a host test: hmi/test_device/run.sh.)
// A make-believe ESP32 for src/wifi_device.h: the Arduino WiFi library as its SOURCE reads (2.0.17: WiFiSTA.cpp,
// WiFiScan.cpp, WiFiGeneric.cpp::_eventCallback), a radio driver that takes time, a flash store whose power can be cut,
// a display that checks every rectangle, and the hooks of main.cpp copied from main.cpp.
#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <string>
#include <vector>
#include <map>
#include <deque>
#include <functional>
#include <algorithm>
#include "nextion_fonts.h"
#include "TxState.h"
using std::min; using std::max;

// ------------------------------------------------------------------ time
static uint32_t simNow = 5000;
static uint32_t millis() { return simNow; }

// ------------------------------------------------------------------ String, as much of it as is used
struct String {
    std::string s;
    String() {} String(const char *c) : s(c ? c : "") {} String(const std::string &c) : s(c) {}
    const char *c_str() const { return s.c_str(); }
    bool operator!=(const char *o) const { return s != (o ? o : ""); }
    bool operator==(const char *o) const { return s == (o ? o : ""); }
};

// ------------------------------------------------------------------ the chip's store (NVS), and a power cut in the middle of writing
struct SimNvs { std::map<std::string, std::string> kv; long writes = 0, cutAfter = -1; bool dead = false; std::vector<std::string> journal; };
static SimNvs nvs;
struct Preferences {
    bool begin(const char *, bool) { return true; }
    bool write(const std::string &what) { if (nvs.dead) return false; if (nvs.cutAfter >= 0 && nvs.writes >= nvs.cutAfter) { nvs.dead = true; return false; } nvs.writes++; nvs.journal.push_back(what); return true; }
    bool isKey(const char *k) { return nvs.kv.count(k) != 0; }
    uint8_t getUChar(const char *k, uint8_t d) { auto it = nvs.kv.find(k); return it == nvs.kv.end() || it->second.empty() ? d : (uint8_t) it->second[0]; }
    size_t putUChar(const char *k, uint8_t v) { if (!write(std::string("put ") + k)) return 0; nvs.kv[k] = std::string(1, (char) v); return 1; }
    String getString(const char *k, const char *d) { auto it = nvs.kv.find(k); return it == nvs.kv.end() ? String(d) : String(it->second); }
    size_t putString(const char *k, const char *v) { if (!write(std::string("put ") + k)) return 0; nvs.kv[k] = v; return strlen(v); }
    bool remove(const char *k) { if (!write(std::string("remove ") + k)) return false; nvs.kv.erase(k); return true; }
    size_t getBytesLength(const char *k) { auto it = nvs.kv.find(k); return it == nvs.kv.end() ? 0 : it->second.size(); }
    size_t getBytes(const char *k, void *buf, size_t max) { auto it = nvs.kv.find(k); if (it == nvs.kv.end()) return 0; const size_t n = min(max, it->second.size()); memcpy(buf, it->second.data(), n); return n; }
    size_t putBytes(const char *k, const void *buf, size_t len) { if (!write(std::string("put ") + k)) return 0; nvs.kv[k] = std::string((const char *) buf, len); return len; }
    bool getBool(const char *k, bool d) { auto it = nvs.kv.find(k); return it == nvs.kv.end() || it->second.empty() ? d : it->second[0] != 0; }
    size_t putBool(const char *k, bool v) { if (!write(std::string("put ") + k)) return 0; nvs.kv[k] = std::string(1, v ? '\1' : '\0'); return 1; }
};

// ------------------------------------------------------------------ the radio
enum wl_status_t { WL_NO_SHIELD = 255, WL_IDLE_STATUS = 0, WL_NO_SSID_AVAIL = 1, WL_SCAN_COMPLETED = 2, WL_CONNECTED = 3, WL_CONNECT_FAILED = 4, WL_CONNECTION_LOST = 5, WL_DISCONNECTED = 6 };
enum wifi_auth_mode_t { WIFI_AUTH_OPEN = 0, WIFI_AUTH_WPA2_PSK = 3 };
enum wifi_mode_t { WIFI_OFF = 0, WIFI_STA = 1 };
enum { WIFI_IF_STA = 0 }; enum { ESP_OK = 0 }; typedef int esp_err_t;
enum wifi_storage_t { WIFI_STORAGE_FLASH = 0, WIFI_STORAGE_RAM = 1 };
// The pilot's colours (main.cpp: theme.panel() and so on): navy and white, as on a screen that has not been told otherwise
#define OUR_PANEL ((uint16_t) 0x114A)
#define OUR_STRIP ((uint16_t) 0x08A6)
#define OUR_INK ((uint16_t) 0xFFFF)
#define OUR_SOFT ((uint16_t) 0xC618)
#define WIFI_SCAN_RUNNING (-1)
#define WIFI_SCAN_FAILED (-2)
enum arduino_event_id_t { ARDUINO_EVENT_WIFI_SCAN_DONE = 1, ARDUINO_EVENT_WIFI_STA_START, ARDUINO_EVENT_WIFI_STA_STOP, ARDUINO_EVENT_WIFI_STA_CONNECTED, ARDUINO_EVENT_WIFI_STA_DISCONNECTED, ARDUINO_EVENT_WIFI_STA_GOT_IP };
typedef arduino_event_id_t WiFiEvent_t;
struct WiFiEventInfo_t { struct { int reason; } wifi_sta_disconnected; };
struct wifi_config_t { struct { uint8_t ssid[32]; uint8_t password[64]; } sta; };

struct SimAp { std::string ssid; int rssi; bool locked; std::string pass; bool weak = false, hidden = false; };   // weak: heard, but every handshake times out; hidden: not in a look's results, joinable all the same (a phone's hotspot, a look that missed it)
struct SimWiFi {
    // the air, and what the OLD firmware's driver left in its own store (nvs.net80211)
    std::vector<SimAp> air; std::string driverNvsSsid, driverNvsPass;
    int stumble = 0;                             // so many tries with the RIGHT password time out first (a weak signal)
    bool scanDoneOnStop = false;                 // does the driver say SCAN_DONE when it is stopped in the middle of a look? (not known: both can be tried)
    int eventDelay = 0;                          // passes of loop() before the event task has dealt with an event (0: at once)
    // driver
    bool started = false; enum { IDLE, CONNECTING, CONNECTED } st = IDLE;
    std::string cfgSsid, cfgPass, conSsid; int conRssi = 0; uint32_t outAt = 0, ipAt = 0; int outcome = 0;
    bool drvScanning = false; uint32_t scanEnd = 0; std::vector<SimAp> found, results;
    // library
    wl_status_t status_ = WL_NO_SHIELD; bool persistent_ = true, autoReconnect_ = true, firstConnect = true, sleep_ = true;
    bool bitScanning = false, bitScanDone = false; uint32_t scanStarted = 0, scanTimeout = 10000; int scanCount = 0;
    std::function<void(WiFiEvent_t, WiFiEventInfo_t)> user;
    struct Ev { int id, reason, due; }; std::deque<Ev> q;
    std::vector<std::string> log; bool logging = false;
    long begins = 0, scansStarted = 0, scansRefused = 0, connectsSkipped = 0;
    void say(const std::string &t) { if (logging) { char b[32]; snprintf(b, sizeof b, "%7.1f s  ", (simNow - 5000) / 1000.0); log.push_back(b + t); } }

    const SimAp *strongest(const std::string &ssid) const { const SimAp *b = nullptr; for (auto &a : air) if (a.ssid == ssid && (!b || a.rssi > b->rssi)) b = &a; return b; }
    void post(int id, int reason = 0) { q.push_back({ id, reason, eventDelay }); if (eventDelay == 0) deliver(); }
    // ---- driver
    void drvStart() { if (started) return; started = true; st = IDLE; cfgSsid = driverNvsSsid; cfgPass = driverNvsPass; post(ARDUINO_EVENT_WIFI_STA_START); }     // esp_wifi_init() reads the driver's own store
    void drvStop() { if (!started) return; if (drvScanning) { drvScanning = false; if (scanDoneOnStop) { results.clear(); post(ARDUINO_EVENT_WIFI_SCAN_DONE); } } st = IDLE; started = false; post(ARDUINO_EVENT_WIFI_STA_STOP); }
    bool assoc = false;
    void drvDisconnect() { if (st != IDLE) { st = IDLE; assoc = false; conSsid.clear(); post(ARDUINO_EVENT_WIFI_STA_DISCONNECTED, 8); } }
    bool drvConnect() {
        if (st == CONNECTING) return false;
        if (st == CONNECTED) return true;
        st = CONNECTING; const SimAp *ap = strongest(cfgSsid);
        if (!ap || (ap->locked && cfgPass.empty()) || (!ap->locked && !cfgPass.empty())) { outcome = 201; outAt = simNow + 2400; }
        else if (ap->locked && ap->pass != cfgPass) { outcome = 15; outAt = simNow + 4000; }
        else if (ap->weak) { outcome = 15; outAt = simNow + 4000; }                   // too weak to finish the handshake, every time
        else if (stumble > 0) { stumble--; outcome = 15; outAt = simNow + 4000; }      // the right password, a weak signal: the handshake times out
        else { outcome = 1; outAt = simNow + 1200; ipAt = simNow + 2000; conRssi = ap->rssi; }
        say("radio: trying \"" + cfgSsid + "\"");
        return true;
    }
    bool drvScan() {
        if (!started) drvStart();
        if (st == CONNECTING) { scansRefused++; say("radio: look REFUSED (it is joining)"); return false; }
        drvScanning = true; scanEnd = simNow + (st == CONNECTED ? 4500 : 2600); found.clear(); for (auto &a : air) if (!a.hidden) found.push_back(a); scansStarted++; say("radio: looking");
        return true;
    }
    void lose(const std::string &ssid) { for (size_t i = 0; i < air.size();) if (air[i].ssid == ssid) air.erase(air.begin() + (long) i); else ++i; if (st == CONNECTED && conSsid == ssid) { st = IDLE; assoc = false; conSsid.clear(); say("radio: \"" + ssid + "\" has gone"); post(ARDUINO_EVENT_WIFI_STA_DISCONNECTED, 200); } }
    void tick() {
        if (st == CONNECTING && (int32_t) (simNow - outAt) >= 0) {
            if (outcome == 1) { if (!assoc) { assoc = true; conSsid = cfgSsid; post(ARDUINO_EVENT_WIFI_STA_CONNECTED); } if ((int32_t) (simNow - ipAt) >= 0) { st = CONNECTED; say("radio: JOINED \"" + cfgSsid + "\""); post(ARDUINO_EVENT_WIFI_STA_GOT_IP); } }
            else { st = IDLE; assoc = false; conSsid.clear(); say("radio: \"" + cfgSsid + "\" refused, reason " + std::to_string(outcome)); post(ARDUINO_EVENT_WIFI_STA_DISCONNECTED, outcome); }
        }
        if (drvScanning && (int32_t) (simNow - scanEnd) >= 0) { drvScanning = false; results = found; std::sort(results.begin(), results.end(), [](const SimAp &a, const SimAp &b) { return a.rssi > b.rssi; }); post(ARDUINO_EVENT_WIFI_SCAN_DONE); }
        for (auto &e : q) if (e.due > 0) e.due--;
        deliver();
    }
    // ---- library: WiFiGeneric.cpp 1034-1176
    static bool reconnectable(int r) { switch (r) { case 1: case 2: case 15: case 16: case 23: case 204: case 3: case 4: case 5: case 6: case 7: case 9: case 14: case 17: case 53: case 200: case 201: case 203: case 205: case 206: case 207: return true; default: return false; } }
    bool delivering = false;
    void deliver() {
        if (delivering) return; delivering = true;
        while (!q.empty() && q.front().due <= 0) {
            const Ev e = q.front(); q.pop_front();
            if (e.id == ARDUINO_EVENT_WIFI_SCAN_DONE) { scanCount = (int) results.size(); scanStarted = 0; bitScanDone = true; bitScanning = false; }
            else if (e.id == ARDUINO_EVENT_WIFI_STA_START) status_ = WL_DISCONNECTED;
            else if (e.id == ARDUINO_EVENT_WIFI_STA_STOP) status_ = WL_NO_SHIELD;
            else if (e.id == ARDUINO_EVENT_WIFI_STA_CONNECTED) status_ = WL_IDLE_STATUS;
            else if (e.id == ARDUINO_EVENT_WIFI_STA_GOT_IP) status_ = WL_CONNECTED;
            else if (e.id == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) {
                const int reason = e.reason ? e.reason : 1;
                if (reason == 201) status_ = WL_NO_SSID_AVAIL; else if (reason == 202 && !firstConnect) status_ = WL_CONNECT_FAILED; else if (reason == 200 || reason == 204) status_ = WL_CONNECTION_LOST; else if (reason == 2) { } else status_ = WL_DISCONNECTED;
                bool again = false;
                if (reason == 8) { } else if (firstConnect) { firstConnect = false; again = true; } else if (autoReconnect_ && reconnectable(reason)) again = true; else if (reason == 203) status_ = WL_CONNECT_FAILED;
                if (again) { disconnect(); begin(); }
            }
            if (user && e.id == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) { WiFiEventInfo_t info; info.wifi_sta_disconnected.reason = e.reason; user((WiFiEvent_t) e.id, info); }
        }
        delivering = false;
    }
    // ---- library: WiFiSTA.cpp 223-367, WiFiGeneric.cpp 1229-1341
    void persistent(bool p) { persistent_ = p; }
    bool mode(wifi_mode_t m) { if (m == WIFI_STA) drvStart(); else drvStop(); return true; }
    bool setSleep(bool s) { sleep_ = s; return true; }
    bool setAutoReconnect(bool a) { autoReconnect_ = a; return true; }
    void onEvent(void (*cb)(WiFiEvent_t, WiFiEventInfo_t)) { user = cb; }
    wl_status_t status() { return status_; }
    wl_status_t begin(const char *ssid, const char *pass = nullptr) {
        begins++;
        if (!started) drvStart();
        if (!ssid || !*ssid || strlen(ssid) > 32) return WL_CONNECT_FAILED;
        if (pass && strlen(pass) > 64) return WL_CONNECT_FAILED;
        const std::string s = ssid, p = pass ? pass : "";
        if (s != cfgSsid || p != cfgPass) { drvDisconnect(); cfgSsid = s; cfgPass = p; }
        else if (status() == WL_CONNECTED) { connectsSkipped++; say("library: begin() of the network in hand, status still says CONNECTED: no connect is made"); return WL_CONNECTED; }
        if (!drvConnect()) return WL_CONNECT_FAILED;
        return status();
    }
    wl_status_t begin() { if (!started) drvStart(); if (status() != WL_CONNECTED) { if (!drvConnect()) return WL_CONNECT_FAILED; } return status(); }
    bool disconnect(bool wifioff = false, bool = false) { if (!started) return false; drvDisconnect(); if (wifioff) drvStop(); return true; }
    String SSID() { return st == CONNECTED || (st == CONNECTING && assoc) ? String(conSsid) : String(); }
    int RSSI() { return st == CONNECTED ? conRssi : 0; }
    // ---- library: WiFiScan.cpp 57-171
    int16_t scanNetworks(bool, bool, bool, uint32_t maxMs) {
        if (bitScanning) return WIFI_SCAN_RUNNING;
        scanTimeout = maxMs * 20; if (!started) drvStart(); scanDelete();
        if (drvScan()) { scanStarted = simNow ? simNow : 1; bitScanDone = false; bitScanning = true; return WIFI_SCAN_RUNNING; }
        return WIFI_SCAN_FAILED;
    }
    int16_t scanComplete() {
        if (scanStarted && (simNow - scanStarted) > scanTimeout) { bitScanning = false; return WIFI_SCAN_FAILED; }
        if (bitScanDone) return (int16_t) scanCount;
        if (bitScanning) return WIFI_SCAN_RUNNING;
        return WIFI_SCAN_FAILED;
    }
    void scanDelete() { bitScanDone = false; results.clear(); scanCount = 0; }
    String SSID(int i) { return i >= 0 && i < (int) results.size() && i < scanCount ? String(results[i].ssid) : String(); }
    int32_t RSSI(int i) { return i >= 0 && i < (int) results.size() ? results[i].rssi : 0; }
    wifi_auth_mode_t encryptionType(int i) { return i >= 0 && i < (int) results.size() && results[i].locked ? WIFI_AUTH_WPA2_PSK : WIFI_AUTH_OPEN; }
};
static SimWiFi WiFi;
static const int WIFI_SCANNING_BIT = 1 << 11;
struct WiFiGenericClass { protected: static int clearStatusBits(int bits) { if (bits & WIFI_SCANNING_BIT) WiFi.bitScanning = false; return 0; } };
static int esp_wifi_connect() { return WiFi.drvConnect() ? 0 : 1; }
// The driver's own store: what it holds is written only while its storage is the flash.
static wifi_storage_t simStorage = WIFI_STORAGE_RAM;
static int esp_wifi_set_storage(wifi_storage_t s) { simStorage = s; return ESP_OK; }
static int esp_wifi_set_config(int, wifi_config_t *c) {
    const std::string ssid((const char *) c->sta.ssid, strnlen((const char *) c->sta.ssid, 32)), pass((const char *) c->sta.password, strnlen((const char *) c->sta.password, 64));
    if (simStorage == WIFI_STORAGE_FLASH) { WiFi.driverNvsSsid = ssid; WiFi.driverNvsPass = pass; }
    WiFi.cfgSsid = ssid; WiFi.cfgPass = pass;
    return ESP_OK;
}
static int esp_wifi_get_config(int, wifi_config_t *c) { memset(c, 0, sizeof *c); memcpy(c->sta.ssid, WiFi.cfgSsid.data(), min((size_t) 32, WiFi.cfgSsid.size())); memcpy(c->sta.password, WiFi.cfgPass.data(), min((size_t) 64, WiFi.cfgPass.size())); return ESP_OK; }

// ------------------------------------------------------------------ the display: every rectangle is checked
constexpr int W = 800, H = 480;
static std::string fieldOnLayer, fieldOnGlass;
struct SimGfx {
    long calls = 0, outside = 0, nonPositive = 0; std::string firstBad; bool wholeScreenCleared = false;
    void chk(const char *what, int x, int y, int w, int h) {
        calls++;
        const bool bad = w <= 0 || h <= 0, out = x < 0 || y < 0 || x + w > W || y + h > H;
        if (bad) nonPositive++; if (out) outside++;
        if ((bad || out) && firstBad.empty()) { char b[120]; snprintf(b, sizeof b, "%s(%d,%d,%d,%d)", what, x, y, w, h); firstBad = b; }
        if (x <= 0 && y <= 0 && x + w >= W && y + h >= H) wholeScreenCleared = true;
        if (!strcmp(what, "fillRect") && x <= 6 && y <= 60 && x + w >= 794 && y + h >= 114) fieldOnLayer.clear();
    }
    void fillRect(int x, int y, int w, int h, uint16_t) { chk("fillRect", x, y, w, h); }
    void drawRect(int x, int y, int w, int h, uint16_t) { chk("drawRect", x, y, w, h); }
    void drawRoundRect(int x, int y, int w, int h, int, uint16_t) { chk("drawRoundRect", x, y, w, h); }
    void drawFastHLine(int x, int y, int w, uint16_t) { chk("drawFastHLine", x, y, w, 1); }
    void drawFastVLine(int x, int y, int h, uint16_t) { chk("drawFastVLine", x, y, 1, h); }
    void startWrite() {} void endWrite() {}
};
static SimGfx simGfx; static SimGfx *gfx = &simGfx;
static int clipX0 = 0, clipY0 = 0, clipX1 = 800, clipY1 = 480;
// main.cpp 163-169
static const NextionFont *fontFor(int id) { return (id >= 0 && id < 7) ? nextion_fonts[id] : nextion_fonts[6]; }
static int fontHeight(int id) { return fontFor(id)->height; }
static int textWidth(int fontId, const std::string &s) { const NextionFont *f = fontFor(fontId); int w = 0; for (unsigned char c : s) { if (c < f->first || c > f->last) continue; w += f->glyphs[c - f->first].width; } return w; }
// main.cpp 382-387
static uint16_t shade(uint16_t c, int pct) { int r = (c >> 11) & 31, g = (c >> 5) & 63, b = c & 31; if (pct > 0) { r += (31 - r) * pct / 100; g += (63 - g) * pct / 100; b += (31 - b) * pct / 100; } else { r += r * pct / 100; g += g * pct / 100; b += b * pct / 100; } return (uint16_t) ((r << 11) | (g << 5) | b); }
// what the glass shows of the password box: on our layer (drawn) and on the panel (presented)
static bool clipLeftSet = false; static long textOutsideClip = 0, pixelsOutside = 0, clipOutsideScreen = 0; static std::vector<std::string> cutTexts;
// main.cpp 195-234 (the 1-bit branch): the same clipping, pixel by pixel, into nothing; a pixel outside 800x480 is counted
static void drawGlyphs(int x, int y, int fontId, uint16_t, const std::string &s) {
    const NextionFont *f = fontFor(fontId); const int h = f->height;
    if (clipX0 < 0 || clipY0 < 0 || clipX1 > W || clipY1 > H) clipOutsideScreen++;
    if (y >= clipY1 || y + h <= clipY0) return;
    for (unsigned char c : s) {
        if (c < f->first || c > f->last) continue;
        const NextionGlyph &g = f->glyphs[c - f->first]; const int bw = g.bitmap_width, gx = x - g.kern_left;
        for (int row = 0; row < h; ++row) { const int py = y + row; if (py < clipY0 || py >= clipY1) continue; for (int col = 0; col < bw; ++col) { const int px = gx + col; if (px < clipX0 || px >= clipX1) { continue; } if (px < 0 || px >= W || py < 0 || py >= H) pixelsOutside++; } }
        x += g.width;
    }
}
static void topText(int x, int y, int font, uint16_t col, const std::string &s) {
    if (font == 5) fieldOnLayer = s;
    const int w = textWidth(font, s); if (x < clipX0 || x + w > clipX1) { textOutsideClip++; if (cutTexts.size() < 12) cutTexts.push_back(s); }
    drawGlyphs(x, y, font, col, s);
}
// main.cpp 1210-1215
static std::string topCut(const std::string &s, int font, int maxW) { if (textWidth(font, s) <= maxW) return s; std::string t = s; while (!t.empty() && textWidth(font, t + "...") > maxW) t.erase(t.size() - 1); return t + "..."; }
static bool topOn = false; static int topWho = 0; static int topX = 40, topY = 36, topW = 720, topH = 408;
static bool touchLockout = false;                          // (1.11.3: a corner held is not a touch for the page)
static bool simTopReady = true; static bool topReady() { return simTopReady; }
struct TopDraw { TopDraw() {} ~TopDraw() {} };
static long dirtyCalls = 0; static bool anyDirty = false, touchPainted = false;
static void dirty(int, int, int, int) { dirtyCalls++; anyDirty = true; }
static void presentDirty() { if (!anyDirty) return; anyDirty = false; fieldOnGlass = topOn ? fieldOnLayer : std::string(); }

// ------------------------------------------------------------------ the rest of main.cpp that the header leans on
static uint32_t lastRxMs = 0;
static std::vector<std::string> blogLines; static void blog(const char *tag, const std::string &what) { blogLines.push_back(std::string(tag) + " " + what.substr(0, 60)); }
static bool radiosOn = true, radiosLive = true, updWifi = false, otaReady = false;
static ldrc::TxState tx;                                          // (main.cpp's)
static bool &armedNow = tx.armed; static int &txStatus = tx.status; static bool &radioHeld = tx.held;
using ldrc::TX_SAFETY_DEFINED;
static bool wifiRequested = false, updRequested = false, sdOk = true; static std::vector<std::string> pageNames = { "FrontView" };
static bool simUpdShowing = false; static bool updShowing() { return simUpdShowing; }
struct SimPage { std::string name = "TXSetupView", evPress; }; static SimPage page;
struct SimLink { bool busy = false; bool running() { return busy; } }; static SimLink teensyLink;
static std::string wire;                                          // every byte that went to the Teensy
static void runScript(const std::string &, const std::string &) {}
static void flushOut() {}
struct SimSerial { size_t write(const uint8_t *b, size_t n) { wire.append((const char *) b, n); return n; } }; static SimSerial Serial;
enum { HTTP_GET = 1, HTTP_POST = 2 };
struct SimWeb { std::map<std::string, std::function<void()>> routes; std::string sent; int code = 0; void on(const char *p, int, std::function<void()> f) { routes[p] = f; } void send(int c, const char *, const char *body) { code = c; sent = body; } void stop() {} }; static SimWeb web;
static void doorOn(const char *p, int m, std::function<void()> f) { web.on(p, m, f); }      // (the workshop door itself is main.cpp's)
static Preferences prefs;
static void setRadios(bool on);
static void applyRadios(const char *why);
