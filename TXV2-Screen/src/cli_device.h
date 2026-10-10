// The command line page (screen 1.11.41, 10 Oct 2026; lib/LdrcCli does the thinking): Rotorflight's command line
// through the receiver's USB cable, over the screen's Bluetooth pipe. Opened by "ldrc cli" (the Backup page's
// "Command line ..." button) or "ldrc diff" ("Diff to card": diff all, written to /rfdiff on the screen's card, and
// out again). The items are the WiFi page's kind and are drawn by its code; the console is drawn here.
// Included by main.cpp after ble_device.h (it asks the receiver through bleAsk).
#include "LdrcCli.h"

static const int CLI_WHO = 10;                                  // the layer's owner (main.cpp topWho)
struct ScreenCli : public ldrc::CliHost {
    bool asked = false;
    uint32_t ms() override { return millis(); }
    bool pipeReady() override { return bleState == BLE_READY; }
    bool armed() override { return armedNow; }
    bool ask(const std::string &method, const std::string &path) override { asked = bleAsk(method, path, "", "", 12000); return asked; }   // (a diff takes the flight controller a few seconds)
    int askState() override { if (!asked) return -1; if (bleReqPending || !bleReqDone) return 0; asked = false; return bleReqError.empty() ? 1 : -1; }
    int askCode() override { return bleLast.code; }
    std::string askBody() override { return bleLast.body; }
    std::string askError() override { return bleReqError; }
    std::string modelName() override { Comp *c = find("t11"); return c ? c->txt : std::string(); }   // (the Backup page's model name: the main board writes it)
    std::string stamp() override {
        const time_t t = time(nullptr);
        if (t < 1700000000) return "";                           // (no time from the internet this session)
        struct tm lt; localtime_r(&t, &lt); char b[24]; strftime(b, sizeof b, "%Y-%m-%d_%H%M", &lt); return b;
    }
    bool exists(const std::string &p) override { return sdOk && SD.exists(p.c_str()); }
    bool save(const std::string &p, const std::string &text, std::string &err) override {
        if (!sdOk) { err = "no card"; return false; }
        sdMakeFolders(p.c_str());
        File f = SD.open(p.c_str(), FILE_WRITE);
        if (!f) { err = "the card would not take it"; return false; }
        const size_t n = f.write((const uint8_t *) text.data(), text.size()); f.close();
        if (n != text.size()) { SD.remove(p.c_str()); err = "the card is full"; return false; }
        blog("cli", "diff saved: " + p + " (" + std::to_string(text.size()) + " bytes; " + (SD.exists(p.c_str()) ? "there" : "NOT there") + " on reading back)");
        return true;
    }
    void listDiffs(std::vector<std::string> &out) override {   // every file of /rfdiff (the choosing is lib/LdrcCli cliNewest's)
        out.clear();
        if (!sdOk) return;
        File d = SD.open("/rfdiff");
        if (!d || !d.isDirectory()) { blog("cli", "no /rfdiff folder"); return; }
        for (File f = d.openNextFile(); f && out.size() < 500; f = d.openNextFile()) {   // (as the door's /ls lists: openNextFile and name)
            if (!f.isDirectory()) { std::string n = f.name(); if (n.rfind("/rfdiff/", 0) != 0) { const size_t slash = n.find_last_of('/'); n = "/rfdiff/" + (slash == std::string::npos ? n : n.substr(slash + 1)); } out.push_back(n); }
            f.close();
        }
        d.close();
        blog("cli", "/rfdiff holds " + std::to_string(out.size()) + " file(s)" + (out.empty() ? "" : ", the first " + out[0]) + "; the model is \"" + modelName() + "\"");
    }
    bool load(const std::string &p, std::string &text) override {
        if (!sdOk) return false;
        File f = SD.open(p.c_str(), FILE_READ);
        if (!f) return false;
        text.clear();
        char b[256];
        while (f.available() && text.size() < 60000) { const int n = f.read((uint8_t *) b, sizeof b); if (n <= 0) break; text.append(b, (size_t) n); }
        f.close();
        return true;
    }
};
static ScreenCli cliHost;
static ldrc::CliPage cliPage(cliHost);
static uint32_t cliTouchedAt = 0;   // (cliJobWanted, the page to open at the next pass of loop(), is main.cpp's: CLI_CONSOLE, CLI_TO_CARD or CLI_EXECUTE from "ldrc cli" / "ldrc diff" / "ldrc exec")
static bool cliUp() { return topOn && topWho == CLI_WHO; }
static void cliDrawConsole(const ldrc::WifiItem &it) {
    const uint16_t back = shade(WF_BACK, -35);
    gfx->fillRect(it.x, it.y, it.w, it.h, back);
    gfx->drawRect(it.x, it.y, it.w, it.h, WF_SOFT);
    clipX0 = it.x + 2; clipY0 = it.y + 2; clipX1 = it.x + it.w - 2; clipY1 = it.y + it.h - 2;
    const std::vector<std::string> &ls = cliPage.lines();
    const int pitch = 26;
    for (int k = 0; k < ldrc::CLI_VISIBLE; ++k) {
        const int i = cliPage.top() + k;
        if (i < 0 || i >= (int) ls.size()) break;
        const std::string &l = ls[i];
        const bool ours = !l.empty() && l[0] == '#' && l.size() > 1 && l[1] == ' ';   // "# command": what was typed, in the soft colour
        topText(it.x + 8, it.y + 4 + k * pitch, 2, ours ? WF_SOFT : WF_INK, topCut(l, 2, it.w - 16));
    }
    clipX0 = 0; clipY0 = 0; clipX1 = W; clipY1 = H;
}
static void cliTouch(bool pressed, int x, int y, uint32_t now) {
    { static uint32_t lastDownHere = 0; if (pressed) lastDownHere = now;
      if (touchLockout) { if (!pressed && (int32_t) (now - lastDownHere) > 80) touchLockout = false; return; } }
    static bool waking = false;
    if (pressed) cliTouchedAt = now;
    if (pressed && page.name == "BlankView") { if (!waking && !teensyLink.running()) runScript(page.evPress, ""); waking = true; return; }
    if (waking) { if (!pressed) waking = false; cliPage.touch(false, x, y); return; }
    cliPage.touch(pressed, x, y);
}
static void cliPoll() {
    static uint32_t drawnLayout = 0, lastPoke = 0; static bool wasUp = false; static std::map<int, uint32_t> drawn;
    if (cliJobWanted >= 0 && !radioHeld) {
        const int job = cliJobWanted; cliJobWanted = -1;
        if (!updShowing() && !wifiPage.showing() && !cliPage.showing() && topReady()) { cliTouchedAt = millis(); cliPage.open(job); }
    }
    cliPage.poll();
    if (cliPage.showing() && !topReady()) cliPage.close();
    const bool up = cliPage.showing() && !updShowing() && topReady();
    if (up) {
        const ldrc::WifiScene &sc = cliPage.scene();
        if (!wasUp || sc.layout != drawnLayout) {
            TopDraw on;
            wifiStrip = WF_STRIP;
            for (auto &it : sc.items) if (it.kind == ldrc::WifiItem::TITLE) wifiStrip = it.bad ? 0x8000 : WF_STRIP;
            gfx->fillRect(0, 0, W, H, WF_BACK); gfx->fillRect(0, 0, W, 58, wifiStrip); gfx->drawFastHLine(0, 58, W, WF_INK);
            drawn.clear();
            for (auto &it : sc.items) { if (it.id == ldrc::CLI_ID_CONSOLE) cliDrawConsole(it); else wifiDrawItem(it); drawn[it.id] = it.serial; }
            drawnLayout = sc.layout;
            topX = 0; topY = 0; topW = W; topH = H; topWho = CLI_WHO; topOn = true;
            dirty(0, 0, W, H); touchPainted = true;
        } else {
            for (auto &it : sc.items) {
                auto d = drawn.find(it.id);
                if (d != drawn.end() && d->second == it.serial) continue;
                { TopDraw on; if (it.id == ldrc::CLI_ID_CONSOLE) cliDrawConsole(it); else wifiDrawItem(it); }
                drawn[it.id] = it.serial;
                dirty(it.x, it.y, it.w, it.h); touchPainted = true;
            }
        }
        const uint32_t now = millis();                          // (the Teensy cannot see touches on this page: its screen saver is told someone is here)
        if (now - cliTouchedAt < 180000 && now - lastPoke > 20000 && !teensyLink.running() && page.name != "BlankView") { lastPoke = now; flushOut(); Serial.write((const uint8_t *) "UKRULES", 7); }
    } else if (wasUp) {
        if (topWho == CLI_WHO) { topOn = false; topWho = 0; }
        drawn.clear();
        dirty(0, 0, W, H); touchPainted = true;                 // the page, as the Teensy has drawn it meanwhile
    }
    wasUp = up;
}
static void cliWeb() {                                          // the bench, through the workshop door
    doorOn("/cli/open", HTTP_POST, []() { cliJobWanted = web.hasArg("job") ? atoi(web.arg("job").c_str()) : 0; web.send(200, "text/plain", "opening"); });
    doorOn("/cli/close", HTTP_POST, []() { cliPage.close(); web.send(200, "text/plain", "closed"); });
    doorOn("/cli/status", HTTP_GET, []() {
        auto esc = [](const std::string &t) { std::string o; for (char c : t) { if (c == '"' || c == '\\') o.push_back('\\'); if ((unsigned char) c >= 32) o.push_back(c); } return o; };
        std::string out = "{\"page\":\"" + cliPage.pageName() + "\",\"open\":" + (cliPage.cliOpen() ? "true" : "false") + ",\"busy\":" + (cliPage.busy() ? "true" : "false") + ",\"saved\":\"" + esc(cliPage.savedAs()) + "\",\"top\":" + std::to_string(cliPage.top()) + ",\"lines\":[";
        bool first = true;
        for (auto &l : cliPage.lines()) { out += std::string(first ? "" : ",") + "\"" + esc(l) + "\""; first = false; }
        out += "],\"items\":[";
        first = true;
        for (auto &it : cliPage.scene().items) {
            char g[120]; snprintf(g, sizeof g, "%s{\"id\":%d,\"x\":%d,\"y\":%d,\"w\":%d,\"h\":%d,\"on\":%s,\"text\":\"", first ? "" : ",", it.id, it.x, it.y, it.w, it.h, it.enabled ? "true" : "false");
            out += g; out += esc(it.text) + "\"}"; first = false;
        }
        out += "]}";
        web.send(200, "application/json", out.c_str());
    });
}
