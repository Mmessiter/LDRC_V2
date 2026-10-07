// The screen's WiFi: the networks it knows, joining the best one in range by itself, and the WiFi page
// (lib/LdrcWifi does the thinking; this is the radio, the store and the drawing).
//
// NO NETWORK NAME AND NO PASSWORD IS COMPILED INTO THE FIRMWARE. The firmware is published on messiter.com;
// what it knows of networks is typed on the screen by the pilot and kept in the chip (NVS). The first
// firmwares (1.0.x) had the house's WiFi compiled in and went to the website like that: never again.
// (A bench build with -DLDRC_SEED_WIFI puts the networks of include/secrets.h into the chip. It is for
// Malcolm's own boards and is never published: TXV1B dev/release_v1b.py refuses a file that holds a password.)
//
// Included by main.cpp just before netBegin().
#include <esp_wifi.h>
#include "LdrcWifi.h"
#ifdef LDRC_SEED_WIFI
#include "secrets.h"
#endif

// ------------------------------------------------------------------ the networks this transmitter knows
static Preferences wifiPrefs;
static std::vector<ldrc::WifiKnown> wifiKnown;                 // newest first
static bool wifiDirty = false; static uint32_t wifiDirtyAt = 0;

static void wifiKeys(int i, char *ks, char *kp) { snprintf(ks, 8, "s%d", i); snprintf(kp, 8, "p%d", i); }
static void wifiStoreLoad() {
    wifiKnown.clear();
    const size_t len = wifiPrefs.getBytesLength("all");
    if (len) {                                                  // name, 0, password, 0, name, 0, ...
        std::string raw(len, '\0'); wifiPrefs.getBytes("all", &raw[0], len);
        for (size_t at = 0; at < raw.size() && wifiKnown.size() < ldrc::WIFI_KNOWN_MAX;) {
            const size_t a = raw.find('\0', at), b = a == std::string::npos ? a : raw.find('\0', a + 1);
            if (b == std::string::npos) break;
            ldrc::WifiKnown k; k.ssid = raw.substr(at, a - at); k.pass = raw.substr(a + 1, b - a - 1); at = b + 1;
            if (!k.ssid.empty()) wifiKnown.push_back(k);
        }
        return;
    }
    const int n = wifiPrefs.getUChar("n", 0);                   // the store as 1.1.0 to 1.2.0 wrote it
    for (int i = 0; i < n && i < (int) ldrc::WIFI_KNOWN_MAX; ++i) {
        char ks[8], kp[8]; wifiKeys(i, ks, kp);
        ldrc::WifiKnown k; k.ssid = wifiPrefs.getString(ks, "").c_str(); k.pass = wifiPrefs.getString(kp, "").c_str();
        if (!k.ssid.empty()) wifiKnown.push_back(k);
    }
}
// Flash writes stall the chip and the wire loses bytes meanwhile (see prefsPoll): only what has changed is written.
static void wifiStoreWrite() {
    wifiDirty = false;
    // The whole list as ONE value, written first: the flash holds the old list or the new one, never a name with
    // another network's password (a power cut between the writes below did that). It is what wifiStoreLoad() believes.
    std::string raw;
    for (auto &k : wifiKnown) { raw += k.ssid; raw.push_back('\0'); raw += k.pass; raw.push_back('\0'); }
    if (raw.empty()) raw.push_back('\0');                       // (an empty list is a list too)
    if (wifiPrefs.putBytes("all", raw.data(), raw.size()) != raw.size()) { wifiDirty = true; wifiDirtyAt = millis(); return; }   // not written: tried again
    // The keys of 1.1.0 to 1.2.0 are kept up as well, for as long as "Earlier versions" can put one of those back.
    if (wifiPrefs.getUChar("n", 255) != (uint8_t) wifiKnown.size()) wifiPrefs.putUChar("n", (uint8_t) wifiKnown.size());
    for (int i = 0; i < (int) ldrc::WIFI_KNOWN_MAX; ++i) {
        char ks[8], kp[8]; wifiKeys(i, ks, kp);
        if (i < (int) wifiKnown.size()) {
            if (!wifiPrefs.isKey(ks) || wifiPrefs.getString(ks, "") != wifiKnown[i].ssid.c_str()) wifiPrefs.putString(ks, wifiKnown[i].ssid.c_str());
            if (!wifiPrefs.isKey(kp) || wifiPrefs.getString(kp, "") != wifiKnown[i].pass.c_str()) wifiPrefs.putString(kp, wifiKnown[i].pass.c_str());
        } else {                                               // a forgotten network's password does not stay behind
            if (wifiPrefs.isKey(ks)) wifiPrefs.remove(ks);
            if (wifiPrefs.isKey(kp)) wifiPrefs.remove(kp);
        }
    }
}
static void wifiStorePoll() {                                  // when the wire has been quiet for a moment; after 3 s, quiet or not
    if (wifiDirty && ((int32_t) (millis() - lastRxMs) > 300 || millis() - wifiDirtyAt > 3000)) wifiStoreWrite();
}
static void wifiChanged() { wifiDirty = true; wifiDirtyAt = millis(); }

// ------------------------------------------------------------------ the radio
static volatile int wifiBadKey = 0, wifiExpired = 0, wifiNoAp = 0;   // why the radio was turned away, counted by the WiFi task since the last begin()
static int wifiAutoStep = 0; static uint32_t wifiAutoAt = 0, wifiBeganAt = 0, wifiLookAt = 0;
static std::string wifiTrying;                                  // the network asked for last, by the page or by ourselves

static void wifiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
    if (event != ARDUINO_EVENT_WIFI_STA_DISCONNECTED) return;
    const int why = info.wifi_sta_disconnected.reason;
    if (why == 202) wifiBadKey += 2;                            // authentication failed: the password
    else if (why == 15 || why == 204) wifiBadKey++;             // a handshake that timed out: the password - or a weak signal, so it takes two of them
    else if (why == 2) wifiExpired++;                           // authentication expired: the password, or a weak signal
    else if (why == 201) wifiNoAp++;                            // no such network in range
}
static void wifiBeginWith(const std::string &ssid, const std::string &pass) {
    const bool was = WiFi.status() == WL_CONNECTED;
    WiFi.disconnect();
    wifiBadKey = 0; wifiExpired = 0; wifiNoAp = 0; wifiTrying = ssid; wifiBeganAt = millis();
    const wl_status_t said = pass.empty() ? WiFi.begin(ssid.c_str()) : WiFi.begin(ssid.c_str(), pass.c_str());
    if (was && said == WL_CONNECTED) esp_wifi_connect();        // the library's status had not caught up with our disconnect(): asked for the network in hand, it asks the radio for nothing
}
static void wifiCollect(int n, std::vector<ldrc::WifiNet> &out) {
    out.clear();
    for (int i = 0; i < n && i < 40; ++i) {
        ldrc::WifiNet net; net.ssid = WiFi.SSID(i).c_str(); net.rssi = WiFi.RSSI(i); net.locked = WiFi.encryptionType(i) != WIFI_AUTH_OPEN;
        if (!net.ssid.empty()) out.push_back(net);
    }
    WiFi.scanDelete();
}
static std::vector<std::string> wifiTried;                      // tried by ourselves since we were last joined, in vain: they wait their turn
static bool wifiLook(bool now = false) {                       // ask the radio to look around (it answers later); now: whatever it is trying has had its time
    // A radio in the middle of joining cannot look. One that has been at it for a quarter of a minute is told to
    // stop; one that has just begun is left to it (the looking is refused, and asked for again a little later).
    if (WiFi.status() != WL_CONNECTED && (now || millis() - wifiBeganAt > 5000)) WiFi.disconnect();
    WiFi.scanDelete();
    wifiLookAt = millis();
    return WiFi.scanNetworks(true, false, false, 300) != WIFI_SCAN_FAILED;
}
// 0 still looking, 1 done, -1 it could not. The library calls a look "failed" once twenty times the longest
// stay on one channel have passed (2.4 s as first written: no look made while joined to a network ever
// finished in that), although the radio is still at it and delivers a moment later. We wait for the radio.
static int wifiLookState() {
    if (WiFi.scanComplete() >= 0) return 1;
    return millis() - wifiLookAt < 12000 ? 0 : -1;
}
static void wifiStart() {                                      // the radio comes on: at start-up, by the pilot's switch, when the motor goes off
    WiFi.persistent(false);                                     // the networks are in OUR store: the driver writes nothing to the flash (it did, at every begin())
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(!(updWifi && bleIsOff()));                 // (1.11.20) awake only when Bluetooth is down
    WiFi.setAutoReconnect(true);
    wifiAutoStep = 0;
}
// The radio goes off (the motor, the safety, the pilot's switch). A look that was under way is over, and the
// library must be told: stopped in the middle, the driver never says "done", the library goes on believing that
// a look is running, and the next one asked for is not made (found by simulation: 43 s to join instead of 17).
struct WifiLookOver : public WiFiGenericClass { static void now() { clearStatusBits(WIFI_SCANNING_BIT); } };
static void wifiStop() { WiFi.disconnect(true); WiFi.mode(WIFI_OFF); WifiLookOver::now(); }
// Not joined, and the WiFi page is not showing: the newest network we know is tried at once (at home that is
// the one, joined in two seconds); if that does not come, the radio looks around and the strongest of the
// networks we know is tried; if none is in range it looks again every quarter of a minute.
// Screen 1.9.5 (Malcolm, 10-05: in the bedroom the house network is heard but too weak to join, and the screen
// "tried for ages to connect to house"): a network we know that the look did NOT show is tried all the same, by
// name, before the one that keeps failing is tried again - a quick look misses networks, and a phone's hotspot
// answers a direct call when it is on. Each step goes in the boot log.
static bool wifiTriedAlready(const std::string &ssid) { for (auto &t : wifiTried) if (ldrc::wifiSameName(t, ssid)) return true; return false; }
static void wifiAuto() {
    const uint32_t now = millis();
    if (wifiKnown.empty()) return;
    switch (wifiAutoStep) {
    case 0:
        wifiTried.clear(); wifiTried.push_back(wifiKnown[0].ssid);
        blog("wifi", "auto: trying " + ldrc::wifiShown(wifiKnown[0].ssid));
        wifiBeginWith(wifiKnown[0].ssid, wifiKnown[0].pass); wifiAutoAt = now; wifiAutoStep = 1;
        return;
    case 1:
        if (now - wifiAutoAt > 12000 || (wifiNoAp && now - wifiAutoAt > 4000)) {   // (the radio says "no such network": no need to wait the whole while)
            blog("wifi", "auto: " + ldrc::wifiShown(wifiTrying) + (wifiNoAp ? " not there" : wifiBadKey ? " refused" : " did not answer"));
            wifiAutoStep = wifiLook(true) ? 2 : 3; wifiAutoAt = now;
        }
        return;
    case 2: {
        const int st = wifiLookState();
        if (st == 0) return;
        if (st < 0) { wifiAutoStep = 3; wifiAutoAt = now; return; }
        std::vector<ldrc::WifiNet> seen; wifiCollect(WiFi.scanComplete(), seen);
        { std::string what; for (auto &kn : wifiKnown) { int rssi = 0; bool in = false; for (auto &n : seen) if (ldrc::wifiSameName(kn.ssid, n.ssid)) { in = true; rssi = n.rssi; } what += (what.empty() ? "" : ", ") + ldrc::wifiShown(kn.ssid) + (in ? " " + std::to_string(rssi) : " not seen"); }
          blog("wifi", "auto: look: " + what); }
        std::vector<ldrc::WifiNet> others;
        for (auto &n : seen) if (!wifiTriedAlready(n.ssid)) others.push_back(n);
        std::string ssid; int k = ldrc::wifiBest(wifiKnown, others, ssid);
        if (k < 0) for (size_t i = 0; i < wifiKnown.size(); ++i) if (!wifiTriedAlready(wifiKnown[i].ssid)) { k = (int) i; ssid = wifiKnown[i].ssid; blog("wifi", "auto: " + ldrc::wifiShown(ssid) + " not seen: trying it all the same"); break; }   // (the newest first)
        if (k < 0) { wifiTried.clear(); k = ldrc::wifiBest(wifiKnown, seen, ssid); }      // each has had its turn: from the best again
        if (k >= 0) { wifiTried.push_back(ssid); blog("wifi", "auto: trying " + ldrc::wifiShown(ssid)); wifiBeginWith(ssid, wifiKnown[k].pass); wifiAutoStep = 1; } else wifiAutoStep = 3;
        wifiAutoAt = now;
        return;
    }
    default:
        if (now - wifiAutoAt > 15000) { wifiAutoStep = wifiLook(true) ? 2 : 3; wifiAutoAt = now; }
        return;
    }
}
static void wifiJoined() {                                     // netPoll(): we are on a network. The one we are on is the newest we know.
    wifiAutoStep = 1; wifiAutoAt = millis(); wifiTried.clear();
    blog("wifi", "joined " + std::string(ldrc::wifiShown(WiFi.SSID().c_str())) + " " + std::to_string(WiFi.RSSI()));
    const std::string on = WiFi.SSID().c_str();
    if (on.empty() || wifiKnown.empty() || ldrc::wifiSameName(wifiKnown[0].ssid, on)) return;
    for (size_t k = 1; k < wifiKnown.size(); ++k)
        if (ldrc::wifiSameName(wifiKnown[k].ssid, on)) { const std::string pass = wifiKnown[k].pass; ldrc::wifiRemember(wifiKnown, on, pass); wifiChanged(); return; }
}
static void wifiBegin() {                                      // once, at start-up
    wifiPrefs.begin("wifi", false);
    const bool fresh = !wifiPrefs.isKey("n") && !wifiPrefs.isKey("all");
    wifiStoreLoad();
    WiFi.persistent(false);
    WiFi.mode(WIFI_STA);
    bool changed = false;
    if (fresh) {
        // The firmware before 1.1.0 had its networks compiled in, and let the radio's driver keep the one it
        // had joined last. That one is taken over, so a transmitter updated from 1.0.x stays on its network.
        wifi_config_t conf; memset(&conf, 0, sizeof conf);
        if (esp_wifi_get_config(WIFI_IF_STA, &conf) == ESP_OK && conf.sta.ssid[0]) {
            const std::string ssid((const char *) conf.sta.ssid, strnlen((const char *) conf.sta.ssid, sizeof conf.sta.ssid));
            const std::string pass((const char *) conf.sta.password, strnlen((const char *) conf.sta.password, sizeof conf.sta.password));
            ldrc::wifiRemember(wifiKnown, ssid, pass);
            blog("wifi", "one network taken over from the firmware before");
        }
        changed = true;
    }
#ifdef LDRC_SEED_WIFI
    {   // bench build: the networks of include/secrets.h, behind whatever is known already (the house's first among them)
        const char *seeds[3][2] = { { WIFI_SSID, WIFI_PASS }, { HOTSPOT_SSID, HOTSPOT_PASS }, { HOTSPOT_SSID_ASCII, HOTSPOT_PASS } };
        for (int i = 0; i < 3; ++i) {
            bool have = false;
            for (auto &k : wifiKnown) if (ldrc::wifiSameName(k.ssid, seeds[i][0])) have = true;
            if (have || !seeds[i][0][0] || wifiKnown.size() >= ldrc::WIFI_KNOWN_MAX) continue;
            ldrc::WifiKnown k; k.ssid = seeds[i][0]; k.pass = seeds[i][1]; wifiKnown.push_back(k); changed = true;
        }
    }
#endif
    if (changed) wifiStoreWrite();                             // (at start-up: the Teensy is not yet talking, or draws its page afresh in a moment)
    // The firmware before 1.1.0 let the radio's driver keep the network it had joined last, password and all, in a
    // corner of the flash of its own - and there it stayed. Once OUR store holds what there is to hold, the
    // driver's copy is erased: a password is kept in one place, and "Forget" forgets it.
    if (!wifiDirty && !wifiPrefs.getBool("clean", false)) {
        wifi_config_t none; memset(&none, 0, sizeof none);
        esp_wifi_set_storage(WIFI_STORAGE_FLASH);
        const esp_err_t e = esp_wifi_set_config(WIFI_IF_STA, &none);
        esp_wifi_set_storage(WIFI_STORAGE_RAM);
        if (e == ESP_OK) wifiPrefs.putBool("clean", true);
        blog("wifi", e == ESP_OK ? "the radio driver's own copy of the last network is erased" : "the radio driver's copy of the last network could NOT be erased");
    }
    WiFi.onEvent(wifiEvent);
}

// ------------------------------------------------------------------ the page: its radio and its store
struct ScreenWifi : public ldrc::WifiHost {
    bool looking = false; std::string asked;
    uint32_t ms() override { return millis(); }
    bool armed() override { return armedNow; }
    bool armedBySafety() override { return txStatus >= 0 && (txStatus & TX_SAFETY_DEFINED); }
    bool radioOn() override { return radiosOn; }
    void radioSwitch(bool on) override { setRadios(on); }
    void scanStart() override { looking = radiosLive && wifiLook(); }
    int scanState() override { return looking ? wifiLookState() : -1; }
    void scanResults(std::vector<ldrc::WifiNet> &out) override { const int n = WiFi.scanComplete(); if (n >= 0) wifiCollect(n, out); else out.clear(); looking = false; }
    void join(const std::string &ssid, const std::string &pass) override { asked = ssid; if (radiosLive) wifiBeginWith(ssid, pass); }
    int joinState() override {
        if (!radiosLive) return -3;
        if (WiFi.status() == WL_CONNECTED && asked == WiFi.SSID().c_str()) return 1;
        if (wifiBadKey >= 2 || wifiExpired >= 2) return -1;      // (the radio tries again by itself: a wrong password is refused twice within seconds)
        if (wifiNoAp >= 2) return -2;
        return 0;
    }
    std::string joinedTo() override { return radiosLive && WiFi.status() == WL_CONNECTED ? std::string(WiFi.SSID().c_str()) : std::string(); }
    int signal() override { return WiFi.RSSI(); }
    void leave() override { if (radiosLive) WiFi.disconnect(); }
    void load(std::vector<ldrc::WifiKnown> &out) override { out = wifiKnown; }
    void save(const std::vector<ldrc::WifiKnown> &all) override { wifiKnown = all; wifiChanged(); }
};
static ScreenWifi wifiHost;
static ldrc::WifiSetup wifiPage(wifiHost);
static uint32_t wifiTouchedAt = 0;

// ------------------------------------------------------------------ the page: drawing
#define WF_BACK OUR_PANEL                                       // (the pilot's colours: src/theme_device.h)
#define WF_STRIP OUR_STRIP
#define WF_INK OUR_INK
#define WF_SOFT OUR_SOFT
static uint16_t wifiStrip = WF_STRIP;
static void wifiErase(const ldrc::WifiItem &it) {               // what is behind it: the strip along the top, or the page
    const int strip = 58;
    if (it.y < strip) { const int h = min(it.h, strip - it.y); gfx->fillRect(it.x, it.y, it.w, h, wifiStrip); if (it.y + it.h > strip) gfx->fillRect(it.x, strip, it.w, it.y + it.h - strip, WF_BACK); }
    else gfx->fillRect(it.x, it.y, it.w, it.h, WF_BACK);
}
static void wifiFace(const ldrc::WifiItem &it, uint16_t face, bool down) {
    const uint16_t hi = shade(face, 60), lo = shade(face, -45);
    gfx->fillRect(it.x, it.y, it.w, it.h, face);
    for (int k = 0; k < 2; ++k) {
        gfx->drawFastHLine(it.x + k, it.y + k, it.w - 2 * k, down ? lo : hi); gfx->drawFastVLine(it.x + k, it.y + k, it.h - 2 * k, down ? lo : hi);
        gfx->drawFastHLine(it.x + k, it.y + it.h - 1 - k, it.w - 2 * k, down ? hi : lo); gfx->drawFastVLine(it.x + it.w - 1 - k, it.y + k, it.h - 2 * k, down ? hi : lo);
    }
}
static void wifiDrawItem(const ldrc::WifiItem &it) {
    using ldrc::WifiItem;
    clipX0 = max(0, it.x); clipY0 = max(0, it.y); clipX1 = min(W, it.x + it.w); clipY1 = min(H, it.y + it.h);
    switch (it.kind) {
    case WifiItem::TITLE: {
        wifiErase(it);
        const int font = textWidth(0, it.text) <= it.w - 8 ? 0 : 6;
        topText(it.x + 4, it.y + (it.h - fontHeight(font)) / 2 + 2, font, WF_INK, topCut(it.text, font, it.w - 8));
        break;
    }
    case WifiItem::TEXT: {
        wifiErase(it);
        const int font = textWidth(6, it.text) <= it.w - 8 ? 6 : 2;
        const std::string s = topCut(it.text, font, it.w - 8);
        const int tw = textWidth(font, s);
        topText(it.strong ? it.x + it.w - tw - 4 : it.x + (it.w - tw) / 2, it.y + (it.h - fontHeight(font)) / 2 + 2, font, it.good ? 0x87F0 : it.strong ? WF_SOFT : WF_INK, s);
        break;
    }
    case WifiItem::ROW: {
        const uint16_t face = it.pressed ? 0x4C9A : it.good ? 0x0320 : it.strong ? 0x2A72 : 0x19CE;
        gfx->fillRect(it.x, it.y, it.w, it.h, face);
        gfx->drawRect(it.x, it.y, it.w, it.h, shade(face, 35));
        const uint16_t ink = it.bars || it.good ? WF_INK : WF_SOFT;
        const int right = it.x + it.w - 14;
        int nx = right;
        if (it.bars) {                                          // four bars, as many of them lit as the signal is strong
            for (int b = 0; b < 4; ++b) { const int bh = 7 + 5 * b, bx = right - 33 + b * 9; gfx->fillRect(bx, it.y + it.h - 14 - bh, 6, bh, b < it.bars ? WF_INK : shade(face, 30)); }
            nx = right - 33 - 14;
        }
        if (it.locked && it.bars) {                             // a padlock: a body and a shackle
            const int lx = nx - 14, ly = it.y + it.h / 2 - 2;
            gfx->fillRect(lx, ly, 14, 11, ink); gfx->drawRoundRect(lx + 2, ly - 8, 10, 12, 4, ink); gfx->drawRoundRect(lx + 3, ly - 7, 8, 10, 3, ink);
            nx = lx - 14;
        }
        int nameW = nx - (it.x + 14);
        if (!it.note.empty()) { const int nw = textWidth(2, it.note); topText(nx - nw, it.y + (it.h - fontHeight(2)) / 2 + 2, 2, it.good ? 0x87F0 : WF_SOFT, it.note); nameW -= nw + 16; }
        clipX1 = min(W, it.x + 14 + max(0, nameW));
        topText(it.x + 14, it.y + (it.h - fontHeight(6)) / 2 + 2, 6, ink, topCut(it.text, 6, nameW));
        break;
    }
    case WifiItem::BUTTON: case WifiItem::KEY: {
        const bool key = it.kind == WifiItem::KEY;
        uint16_t face = key ? (it.good ? 0x9FF3 : it.strong ? 0xB5B6 : 0xEF7D) : (it.strong ? 0xFFF3 : 0xD69A);
        if (!it.enabled) face = 0x8410; else if (it.pressed) face = shade(face, -30);
        wifiFace(it, face, it.pressed);
        const int font = (key && it.text.size() == 1) || textWidth(0, it.text) <= it.w - 16 ? 0 : 6;
        const std::string s = topCut(it.text, font, it.w - 8);
        topText(it.x + (it.w - textWidth(font, s)) / 2 + (it.pressed ? 1 : 0), it.y + (it.h - fontHeight(font)) / 2 + 2 + (it.pressed ? 1 : 0), font, it.enabled ? 0x0000 : 0x4A69, s);
        break;
    }
    case WifiItem::FIELD: {
        gfx->fillRect(it.x, it.y, it.w, it.h, 0xFFFF);
        gfx->drawRect(it.x, it.y, it.w, it.h, 0x0000); gfx->drawRect(it.x + 1, it.y + 1, it.w - 2, it.h - 2, 0x0000);
        const int nw = it.note.empty() ? 0 : textWidth(2, it.note) + 18, room = it.w - 28 - nw;
        if (nw) topText(it.x + it.w - nw - 2, it.y + (it.h - fontHeight(2)) / 2 + 2, 2, 0x8410, it.note);
        if (it.text.empty() && !it.hint.empty()) {              // nothing typed yet: what is wanted, in grey
            const int font = textWidth(6, it.hint) <= room ? 6 : 2;
            topText(it.x + 24, it.y + (it.h - fontHeight(font)) / 2 + 2, font, 0x9CF3, topCut(it.hint, font, room));
        }
        std::string s = it.text;                                // (in the typewriter face: l, 1 and I, O and 0 are told apart)
        while (!s.empty() && textWidth(5, s) > room) s.erase(0, 1);   // too long for the box: its end is what is shown
        clipX1 = min(W, it.x + it.w - nw - 4);
        topText(it.x + 12, it.y + (it.h - fontHeight(5)) / 2 + 2, 5, 0x0000, s);
        gfx->fillRect(it.x + 14 + textWidth(5, s), it.y + 9, 3, it.h - 18, 0x001F);
        break;
    }
    }
    clipX0 = 0; clipY0 = 0; clipX1 = W; clipY1 = H;
}
static bool wifiPageUp() { return topOn && topWho == 2; }
static bool wifiKeysOnGlass = false;                           // the keys are what wifiPoll() drew last (the glass follows the page by one pass of loop())
static bool wifiSecretShown() {                                // the keys are up, or still on the glass: no picture of them leaves the transmitter
    return wifiKeysOnGlass || wifiPage.typing();               // (the whole page: a key lights up as it is pressed, whatever the box shows)
}
static void wifiTouch(bool pressed, int x, int y, uint32_t now) {
    { static uint32_t lastDownHere = 0; if (pressed) lastDownHere = now;   // a corner held (the door, the radios): that finger is not for this page (1.11.3)
      if (touchLockout) { if (!pressed && (int32_t) (now - lastDownHere) > 80) touchLockout = false; return; } }
    static bool waking = false;
    if (pressed) wifiTouchedAt = now;
    if (pressed && page.name == "BlankView") {                  // the Teensy has blanked the screen: this touch wakes it, and does no more
        if (!waking && !teensyLink.running()) runScript(page.evPress, "");
        waking = true; return;
    }
    if (waking) { if (!pressed) waking = false; wifiPage.touch(false, x, y); return; }
    wifiPage.touch(pressed, x, y);
}
static void wifiPoll() {
    static uint32_t drawnLayout = 0, lastPoke = 0; static bool wasUp = false; static std::map<int, uint32_t> drawn;
    if (wifiRequested && !radioHeld) { wifiRequested = false; if (!updShowing() && !wifiPage.showing()) { wifiTouchedAt = millis(); wifiPage.open(); } }   // (in the first seconds the radio waits for the main board's word: so does the page)
    wifiPage.poll();
    if (!teensyLink.running()) wifiStorePoll();                 // (a flash write stalls the chip: not while files travel on the wire)
    if (wifiPage.showing() && !topReady()) wifiPage.close();     // no memory for its layer: a page nobody can see or close must not hold the radio
    const bool up = wifiPage.showing() && !updShowing() && topReady();
    if (up) {
        const ldrc::WifiScene &sc = wifiPage.scene();
        if (!wasUp || sc.layout != drawnLayout) {
            TopDraw on;
            wifiStrip = WF_STRIP;
            for (auto &it : sc.items) if (it.kind == ldrc::WifiItem::TITLE) wifiStrip = it.good ? 0x0320 : it.bad ? 0x8000 : WF_STRIP;
            gfx->fillRect(0, 0, W, H, WF_BACK); gfx->fillRect(0, 0, W, 58, wifiStrip); gfx->drawFastHLine(0, 58, W, WF_INK);
            drawn.clear();
            for (auto &it : sc.items) { wifiDrawItem(it); drawn[it.id] = it.serial; }
            drawnLayout = sc.layout;
            topX = 0; topY = 0; topW = W; topH = H; topWho = 2; topOn = true;
            dirty(0, 0, W, H); touchPainted = true;
        } else {
            for (auto &it : sc.items) {
                auto d = drawn.find(it.id);
                if (d != drawn.end() && d->second == it.serial) continue;
                { TopDraw on; wifiDrawItem(it); }
                drawn[it.id] = it.serial;
                dirty(it.x, it.y, it.w, it.h); touchPainted = true;
            }
        }
        // Someone is here: the Teensy cannot see touches on this page. While it is being used (a touch within the last
        // three minutes) its screen saver and its power-off timer are told so, as the update panel tells them.
        wifiKeysOnGlass = wifiPage.typing();
        const uint32_t now = millis();
        if (now - wifiTouchedAt < 180000 && now - lastPoke > 20000 && !teensyLink.running() && page.name != "BlankView") { lastPoke = now; flushOut(); Serial.write((const uint8_t *) "UKRULES", 7); }
    } else if (wasUp) {
        topOn = false; topWho = 0; drawn.clear(); wifiKeysOnGlass = false;
        dirty(0, 0, W, H); touchPainted = true;                 // the page, as the Teensy has drawn it meanwhile
        if (WiFi.status() != WL_CONNECTED) wifiAutoStep = 0;    // not joined: the newest network we know, at once
        if (sdOk && pageNames.empty() && !armedNow) updRequested = true;   // a new screen: now that there is WiFi, the files
    }
    wasUp = up;
}
static void wifiWeb() {
    doorOn("/wifi/open", HTTP_POST, []() { wifiRequested = true; web.send(200, "text/plain", "opening"); });
    doorOn("/wifi/close", HTTP_POST, []() { wifiPage.close(); web.send(200, "text/plain", "closed"); });
    // What the page shows and what the transmitter knows: names, never a password (of the box only the length).
    doorOn("/wifi/status", HTTP_GET, []() {
        auto esc = [](const std::string &t) { std::string o; for (char c : t) { if (c == '"' || c == '\\') o.push_back('\\'); if ((unsigned char) c >= 32) o.push_back(c); } return o; };
        static const char *kinds[] = { "title", "text", "row", "button", "key", "field" };
        std::string out = "{\"page\":\"" + wifiPage.pageName() + "\",\"radio\":" + (radiosLive ? "true" : "false") + ",\"joined\":\"" + esc(ldrc::wifiShown(wifiHost.joinedTo())) + "\"";
        char n[64]; snprintf(n, sizeof n, ",\"rssi\":%d,\"unsaved\":%s,\"known\":[", WiFi.status() == WL_CONNECTED ? (int) WiFi.RSSI() : 0, wifiDirty ? "true" : "false"); out += n;
        for (size_t i = 0; i < wifiKnown.size(); ++i) out += std::string(i ? "," : "") + "\"" + esc(ldrc::wifiShown(wifiKnown[i].ssid)) + "\"";
        out += "],\"items\":[";
        bool first = true;
        for (auto &it : wifiPage.scene().items) {
            char g[120]; snprintf(g, sizeof g, "%s{\"id\":%d,\"kind\":\"%s\",\"x\":%d,\"y\":%d,\"w\":%d,\"h\":%d,\"on\":%s,", first ? "" : ",", it.id, kinds[it.kind], it.x, it.y, it.w, it.h, it.enabled ? "true" : "false");
            out += g; first = false;
            if (it.kind == ldrc::WifiItem::FIELD) { snprintf(g, sizeof g, "\"len\":%u}", (unsigned) it.text.size()); out += g; }
            else out += "\"text\":\"" + esc(it.text) + "\",\"note\":\"" + esc(it.note) + "\"}";
        }
        out += "]}";
        web.send(200, "application/json", out.c_str());
    });
}
