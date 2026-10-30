// The screen's OWN pages for the renderer: the WiFi page and its keys, "Check for update" and "Receiver update",
// the picture chooser, the command line, the link's panel, the banner along the top and "Connecting Bluetooth".
// Their DRAWING is the screen's own, cut out of src/*.h by extract.py (gen/own_*.inc); their THINKING is the real
// lib/Ldrc* code, driven here by make-believe radios, card, receiver and Teensy into the states worth looking at
// (the update panel's by the host tests' bench: updscenes.cpp). Included by render.cpp after the main parts.
//
//   @wifi STATE      list looking nonets off many many2 known saved away keys keys_caps keys_symbols keys_hidden keys_empty
//                    keys_pressed joining joined refused notfound motor safety
//   @update STATE    checking uptodate offer fetching copying teensy screenfiles screenflash finishing done failed cardfull
//                    donotfly fellback noserver nowifi nowifiyet motor safety model modeljustnow room versions installed
//                    older picking again
//   @rxupdate STATE  checking offer working waiting done uptodate nomodel noversion armed nowifi failed noanswer safety
//   @pics STATE      choose first mine page2 pressed ask_delete deleted receive receive_nowifi receive_flying receiving (pick NAME: that picture touched)
//                    received upload_failed saving opening
//   @cli STATE       opening console scrolled longreply keys keys_empty keys_symbols leave nopipe armed refused refused_linked
//                    ... exec_pick exec_pick_next exec_pick_ask (1.11.74: the list of the model's diffs)
//                    diffcard diffcard_saved diffcard_failed exec_ask exec_running exec_done exec_refused exec_nofile gone
//   @link STATE      working done failed
//   @banner TEXT     the two-second banner along the top, saying TEXT
//   @pipe [late]     "Connecting Bluetooth" over the Rotorflight menu (late: after six seconds of trying)
//   @film menu | problems | NAME SECONDS [drag TO]   the films menu; the problems list (1.11.94); a film paused at SECONDS, its bar and slider (film.h)
//   @measure TEXT    prints TEXT's width in fonts 0, 2 and 6 (will a label fit its button?)
// Each is drawn over whatever is on the glass, as the screen lays its layer over the Teensy's page.
#pragma once
#include <dirent.h>
#include <set>
#include "LdrcWifi.h"
#include "LdrcCli.h"
#include "LdrcPics.h"
#include "LdrcUpdate.h"
#include "qrcodegen.h"

// ------------------------------------------------------------------ the layer (main.cpp): drawn on the one frame here
// (topOn, topWho, topX/Y/W/H: render.cpp, before main.cpp's parts - the page flip's code looks at them)
static const int TOP_TWIN_WHO = 12; static int top2X = 0, top2W = 0;   // (1.11.94: main.cpp's second stretch of the layer)
static bool topTwin() { return topWho == TOP_TWIN_WHO && top2W > 0; }
static bool topReady() { return true; }
struct TopDraw { TopDraw() {} };                         // (on the transmitter gfx draws on the layer meanwhile; here, over the page: what the glass shows)
static uint32_t bannerUntil = 0;
// The link (main.cpp's teensyLink, a LinkMaster) as its panel reads it.
struct RenderLink {
    bool bad = false; std::string stageNow, resultNow; uint32_t size = 0, done = 0; size_t step = 0, steps = 1;
    bool failed() const { return bad; }
    const std::string &stage() const { return stageNow; }
    const std::string &result() const { return resultNow; }
    uint32_t fileSize() const { return size; }
    uint32_t fileDone() const { return done; }
    size_t stepIndex() const { return step; }
    size_t stepCount() const { return steps; }
    bool running() const { return false; }
};
static RenderLink teensyLink;
#include "gen/own_base.inc"

// ------------------------------------------------------------------ the WiFi page
#include "gen/own_wifi.inc"
struct RenderWifi : public ldrc::WifiHost {
    uint32_t t = 1000; bool motor = false, safety = false, on = true; int scan = 1, joinSt = 0, sig = -48;
    std::vector<ldrc::WifiNet> nets; std::string joined; std::vector<ldrc::WifiKnown> known;
    uint32_t ms() override { return t; }
    bool armed() override { return motor || safety; }
    bool armedBySafety() override { return safety; }
    bool radioOn() override { return on; }
    void radioSwitch(bool o) override { on = o; }
    void scanStart() override {}
    int scanState() override { return scan; }
    void scanResults(std::vector<ldrc::WifiNet> &out) override { out = nets; }
    void join(const std::string &, const std::string &) override {}
    int joinState() override { return joinSt; }
    std::string joinedTo() override { return on ? joined : std::string(); }
    int signal() override { return sig; }
    void leave() override {}
    void load(std::vector<ldrc::WifiKnown> &out) override { out = known; }
    void save(const std::vector<ldrc::WifiKnown> &all) override { known = all; }
};
static RenderWifi wifiIdle; static ldrc::WifiSetup wifiPage(wifiIdle);       // (what the picture chooser asks: the WiFi page is not showing)
static const char *PHONE = "Malcolm\xE2\x80\x99s iPhone";                       // (a phone names itself with a curly apostrophe, in UTF-8)
static void wifiNets(RenderWifi &h, bool many) {
    auto net = [&](const char *s, int rssi, bool locked) { ldrc::WifiNet n; n.ssid = s; n.rssi = rssi; n.locked = locked; h.nets.push_back(n); };
    net("House", -48, true); net(PHONE, -63, true); net("BT-7XK2QF", -71, true); net("SKY8F3A2", -77, true); net("Guest", -84, false);
    if (many) { net("EE-Hub-6Q3M", -79, true); net("VM4471203", -81, true); net("DIRECT-4C-HP OfficeJet Pro 9010", -86, true); net("NETGEAR42-5G", -88, true); net("TALKTALK1A2B3C", -90, true); }
    h.known = { { "House", "(secret)" }, { PHONE, "(secret)" }, { "Club WiFi", "(secret)" } };
    h.joined = "House";
}
static bool wifiTap(ldrc::WifiSetup &p, RenderWifi &h, const std::string &text, bool lift = true) {
    for (auto &it : p.scene().items) {
        if (it.text != text || (it.kind != ldrc::WifiItem::ROW && it.kind != ldrc::WifiItem::BUTTON && it.kind != ldrc::WifiItem::KEY)) continue;
        p.touch(true, it.x + it.w / 2, it.y + it.h / 2); h.t += 40; p.touch(true, it.x + it.w / 2, it.y + it.h / 2);
        if (lift) { h.t += 200; p.touch(false, 0, 0); h.t += 100; p.poll(); }
        return true;
    }
    fprintf(stderr, "render: nothing called \"%s\" on the WiFi page\n", text.c_str());
    return false;
}
static void wifiType(ldrc::WifiSetup &p, RenderWifi &h, const std::string &s) { for (char c : s) wifiTap(p, h, std::string(1, c)); }
static void wifiShot(const std::string &state) {
    RenderWifi h; ldrc::WifiSetup p(h);
    const bool many = state == "many" || state == "many2";
    wifiNets(h, many);
    if (state == "looking") { h.scan = 0; h.joined.clear(); }
    if (state == "nonets") { h.nets.clear(); h.joined.clear(); }
    if (state == "off") h.on = false;
    if (state == "motor") h.motor = true;
    if (state == "safety") h.safety = true;
    p.open(); p.poll();
    if (state == "known") wifiTap(p, h, "House");
    else if (state == "saved") { h.joined.clear(); p.poll(); h.t += 100; p.poll(); wifiTap(p, h, ldrc::wifiShown(PHONE)); }
    else if (state == "away") wifiTap(p, h, "Club WiFi");
    else if (state == "many2") wifiTap(p, h, ">");
    else if (state.rfind("keys", 0) == 0 || state == "joining" || state == "joined" || state == "refused") {
        wifiTap(p, h, "BT-7XK2QF");
        if (state == "keys_empty") {}
        else if (state == "keys_pressed") { wifiType(p, h, "skylark"); wifiTap(p, h, "g", false); }
        else wifiType(p, h, "skylark-2026");
        if (state == "keys_caps") wifiTap(p, h, "ABC");
        if (state == "keys_symbols") wifiTap(p, h, "#+=");
        if (state == "keys_hidden") wifiTap(p, h, "Hide");
        if (state == "joining" || state == "joined" || state == "refused") {
            wifiTap(p, h, "Join");
            h.joinSt = state == "joined" ? 1 : state == "refused" ? -1 : 0; h.t += 3000; p.poll();
        }
    } else if (state == "notfound") { wifiTap(p, h, "Guest"); h.joinSt = -2; h.t += 3000; p.poll(); }
    else if (state != "list" && state != "looking" && state != "nonets" && state != "off" && state != "many" && state != "many2" && state != "motor" && state != "safety")
        fprintf(stderr, "render: no WiFi state %s\n", state.c_str());
    if (!p.showing()) { fprintf(stderr, "render: the WiFi page closed (%s)\n", state.c_str()); return; }
    wifiFrame(p.scene());
}

// ------------------------------------------------------------------ "Check for update" and "Receiver update"
#include "gen/own_update.inc"
bool updScene(const std::string &name, ldrc::UpdView &out, std::string &why);   // (updscenes.cpp)
std::string updSaid(const ldrc::UpdView &v);
static void updateShot(const std::string &state) {
    ldrc::UpdView v; std::string why;
    if (!updScene(state, v, why)) fprintf(stderr, "render: update state %s: %s\n", state.c_str(), why.c_str());
    if (v.kind == ldrc::UpdView::NONE) { fprintf(stderr, "render: update state %s: no panel\n", state.c_str()); return; }
    if (getenv("RENDER_SAID")) fprintf(stderr, "said %s: %s\n", state.c_str(), updSaid(v).c_str());
    updPressed = 0; updDrawPanel(v);
}

// ------------------------------------------------------------------ the picture chooser
#include "gen/own_pics_cache.inc"
struct RenderPics : public ldrc::PicsHost {
    uint32_t t = 1000; bool wifi = true; int fly = 0; std::set<std::string> gone; std::vector<ldrc::PicEntry> mine;
    uint32_t ms() override { return t; }
    void list(std::vector<ldrc::PicEntry> &out) override {      // the pilot's own first, then the release's, each sorted as the screen sorts them
        out.clear(); std::vector<ldrc::PicEntry> rel;
        if (DIR *d = opendir((sdRoot + "/images").c_str())) {
            while (dirent *e = readdir(d)) { std::string n = e->d_name; if (n.size() > 4 && strcasecmp(n.c_str() + n.size() - 4, ".565") == 0) { ldrc::PicEntry p; p.name = n.substr(0, n.size() - 4); rel.push_back(p); } }
            closedir(d);
        }
        auto less = [](const ldrc::PicEntry &a, const ldrc::PicEntry &b) { return strcasecmp(a.name.c_str(), b.name.c_str()) < 0; };
        std::vector<ldrc::PicEntry> m; for (auto &e : mine) if (!gone.count(e.name)) m.push_back(e);
        std::sort(m.begin(), m.end(), less); std::sort(rel.begin(), rel.end(), less);
        out = m; out.insert(out.end(), rel.begin(), rel.end());
    }
    bool removeMine(const std::string &name) override { gone.insert(name); return true; }
    void answer(const std::string &) override {}
    bool wifiUp() override { return wifi && !fly; }
    int flying() override { return fly; }
    std::string address() override { return "192.168.1.57"; }
    uint32_t random() override { return 382913; }
    void wifiWanted(bool) override {}
    void wifiSetup() override {}
    void keepAwake() override {}
    void help() override {}
};
static RenderPics picHost;
static ldrc::Pictures pictures(picHost);
static bool updShowing() { return false; }
#include "gen/own_pics.inc"
static void picThumbsMake() {                             // what picPoll makes a few rows at a time, all at once
    for (int s = 0; s < ldrc::PIC_PER_PAGE; ++s) {
        const int e = pictures.entryAt(s); if (e < 0) continue;
        const ldrc::PicEntry &en = pictures.entries()[e];
        if (ldrc::picSameName(en.name, ldrc::PIC_NONE) || picThumbFind(picKey(en.name, en.mine))) continue;
        picJobStart(en.name, en.mine);
        while (picJob.on) picJobStep();
    }
}
static void picTap(int x, int y) { pictures.touchDown(x, y); picHost.t += 150; pictures.touchUp(x, y); picHost.t += 100; pictures.poll(); }
static void picTapButton(int i) { const ldrc::PicRect b = ldrc::picButton(i); picTap(b.x + b.w / 2, b.y + b.h / 2); }
static void picTapName(const std::string &name) {
    for (int pg = 0; pg < 40 && pictures.arrowShown(-1); ++pg) { const ldrc::PicRect a = ldrc::picArrow(-1); picTap(a.x + a.w / 2, a.y + a.h / 2); }   // (from the first page)
    for (int pg = 0; pg < 40; ++pg) {
        for (int s = 0; s < ldrc::PIC_PER_PAGE; ++s) { const int e = pictures.entryAt(s); if (e >= 0 && pictures.entries()[e].name == name) { const ldrc::PicRect r = ldrc::picTile(s); picTap(r.x + r.w / 2, r.y + r.h / 2); return; } }
        if (!pictures.arrowShown(1)) break;
        const ldrc::PicRect a = ldrc::picArrow(1); picTap(a.x + a.w / 2, a.y + a.h / 2);
    }
    fprintf(stderr, "render: no picture called %s\n", name.c_str());
}
static void picsShot(const std::string &state) {
    // the pilot's own photos (/images/mine): two, read from pictures the card has under names the chooser does not offer
    SD.alias["/images/mine/RAW420MC.565"] = "/images/IMG_RAW420.565"; SD.alias["/images/mine/Goblin.565"] = "/images/Testheli.565";
    picHost = RenderPics(); { ldrc::PicEntry a; a.name = "RAW420MC"; a.mine = true; picHost.mine.push_back(a); a.name = "Goblin"; picHost.mine.push_back(a); }
    if (state == "opening") { pictures.pageGone(); topOn = false; picSoon(); return; }
    if (state == "receive_nowifi") picHost.wifi = false;
    if (state == "receive_flying") picHost.fly = 1;
    pictures.pageGone();
    pictures.open("RAW 420 MCM", state == "first" ? "sd0/images/Noimage.jpg" : "sd0/images/Raw420.jpg");
    if (state == "mine" || state == "ask_delete" || state == "deleted") picTapName("RAW420MC");
    if (state.rfind("pick ", 0) == 0) picTapName(state.substr(5));   // (17 Oct: the animations) a picture of the card touched by its name
    if (state == "ask_delete" || state == "deleted") picTapButton(1);
    if (state == "deleted") picTapButton(2);
    if (state == "page2") { const ldrc::PicRect a = ldrc::picArrow(1); picTap(a.x + a.w / 2, a.y + a.h / 2); }
    if (state == "pressed") { for (int s = 0; s < ldrc::PIC_PER_PAGE; ++s) if (pictures.entryAt(s) >= 0 && pictures.entries()[pictures.entryAt(s)].name == "Riot") { const ldrc::PicRect r = ldrc::picTile(s); pictures.touchDown(r.x + 20, r.y + 20); } }
    if (state.rfind("receiv", 0) == 0 || state == "upload_failed") picTapButton(0);
    if (state == "receiving") { pictures.uploadBegun("RAW420MC"); pictures.uploadBytes(ldrc::PIC_FILE_BYTES * 55 / 100); }
    if (state == "received") { pictures.uploadBegun("RAW420MC"); pictures.uploadEnded(true, "RAW420MC", ""); }
    if (state == "upload_failed") { pictures.uploadBegun("RAW420MC"); pictures.uploadEnded(false, "RAW420MC", "it was not 320 x 200"); }
    if (state == "saving") picTapButton(3);
    picThumbsMake();
    picFrame();
}

// ------------------------------------------------------------------ the command line
// A make-believe receiver: the flight controller's replies as the receiver passes them on (RXV2 /api/cli: no echo of
// the command, the prompt at the end), the card's /rfdiff, the clock.
static const char *RF_DIFF =
    "# version\r\n# Rotorflight / STM32F7X2 (S7X2) 4.6.0 Jun 30 2026 / 12:00:00 (d1a6b0c) MSP API: 12.9\r\n\r\n"
    "# start the command batch\r\nbatch start\r\n\r\nboard_name NEXUS_F7\r\nmanufacturer_id RADI\r\n\r\n# name: RAW 420 MCM\r\nname RAW 420 MCM\r\n\r\n"
    "# feature\r\nfeature -RX_PARALLEL_PWM\r\nfeature RX_SERIAL\r\nfeature TELEMETRY\r\nfeature GOVERNOR\r\n\r\n"
    "# serial\r\nserial 1 64 115200 57600 0 115200\r\n\r\n# aux\r\naux 0 0 0 1700 2100 0 0\r\naux 1 2 1 1300 2100 0 0\r\n\r\n"
    "# master\r\nset gyro_lpf1_static_hz = 150\r\nset serialrx_provider = CRSF\r\nset gov_mode = STANDARD\r\nset gov_spoolup_time = 12\r\n"
    "set gov_max_throttle = 100\r\nset gov_handover_throttle = 20\r\nset pilot_name = MALCOLM\r\n\r\nprofile 0\r\n\r\n# profile 0\r\n"
    "set pid_mode = 3\r\nset gov_headspeed = 2400\r\nset gov_gain = 50\r\nset gov_p_gain = 40\r\nset gov_i_gain = 50\r\nset gov_f_gain = 17\r\n"
    "set yaw_cw_stop_gain = 120\r\nset yaw_ccw_stop_gain = 100\r\n\r\nrateprofile 0\r\n\r\n# rateprofile 0\r\nset rates_type = ACTUAL\r\n"
    "set roll_rc_rate = 36\r\nset pitch_rc_rate = 36\r\nset yaw_rc_rate = 40\r\nset collective_rc_rate = 48\r\nset roll_srate = 50\r\nset pitch_srate = 50\r\n"
    "set yaw_srate = 60\r\nset collective_srate = 48\r\n\r\nsave\r\n# ";
static const char *RF_STATUS =
    "MCU STM32F7X2 Clock=216MHz (PLLP-HSE), Vref=3.29V, Core temp=38degC\r\nStack size: 2048, Stack address: 0x2001fff0\r\n"
    "Configuration: CONFIGURED, size: 4096, max available: 16384\r\nDevices detected: SPI:1, I2C:1\r\nGyros detected: gyro 1 locked dma\r\n"
    "GYRO=ICM42688P, ACC=ICM42688P, BARO=NONE\r\nSystem Uptime: 187 seconds, Current Time: 2026-10-10T15:42:11.000+00:00\r\n"
    "CPU:21%, cycle time: 125, GYRO rate: 8000, RX rate: 148, System rate: 10\r\nVoltage: 2496 * 0.01V (6S battery - OK)\r\nI2C Errors: 0\r\n"
    "Arming disable flags: CLI MSP\r\n# ";
struct RenderCli : public ldrc::CliHost {
    uint32_t t = 1000; bool ready = true, armedV = false, asked = false, hold = false; int code = 200; std::string body, err;
    std::string refuse;                                   // the receiver refuses the command line, with these words
    int holdAfter = -1;                                   // the n-th command's reply has not come yet (-1: every reply comes)
    int commands = 0; std::map<std::string, std::string> card;
    static std::string dec(const std::string &s) { std::string o; for (size_t i = 0; i < s.size(); ++i) { if (s[i] == '%' && i + 2 < s.size()) { o.push_back((char) strtol(s.substr(i + 1, 2).c_str(), nullptr, 16)); i += 2; } else o.push_back(s[i] == '+' ? ' ' : s[i]); } return o; }
    uint32_t ms() override { return t; }
    bool pipeReady() override { return ready; }
    bool armed() override { return armedV; }
    bool mainBoardBusy() override { return false; }
    bool ask(const std::string &method, const std::string &path, uint32_t) override {
        asked = true; code = 200; body.clear(); err.clear();
        if (path.rfind("/api/cli/leave", 0) == 0) { body = "left"; return true; }
        if (path.rfind("/api/cli/out", 0) == 0) { code = 202; body = std::string(RF_DIFF).substr(0, 900); return true; }   // (a long reply still printing)
        if (path.find("cmd=") == std::string::npos) { code = 404; body = "not found"; return true; }
        std::string cmd = path; const size_t a = cmd.find("cmd="), b = cmd.find("&wait"); cmd = dec(cmd.substr(a + 4, b == std::string::npos ? std::string::npos : b - a - 4));
        (void) method;
        if (!refuse.empty()) { code = 409; body = refuse; return true; }
        if (holdAfter >= 0 && commands++ >= holdAfter) hold = true;
        if (cmd.empty()) body = "CLI open";
        else if (cmd == "status") body = RF_STATUS;
        else if (cmd == "diff all") { body = RF_DIFF; if (card.count("slow")) { code = 202; body = std::string(RF_DIFF).substr(0, 500); } }
        else if (cmd == "get gov_headspeed") body = "gov_headspeed = 2400\r\nAllowed range: 0 - 50000\r\nDefault value: 1000\r\n# ";
        else if (cmd.rfind("set ", 0) == 0) { const size_t eq = cmd.find('='); body = cmd.substr(4, eq == std::string::npos ? std::string::npos : eq - 5) + " set to " + (eq == std::string::npos ? "" : cmd.substr(eq + 2)) + "\r\n# ";
            if (cmd.find("yaw_cw_stop_gain") != std::string::npos && refuse.empty() && card.count("refuse_one")) body = "###ERROR IN set: INVALID VALUE###\r\n# "; }
        else body = "\r\n# ";
        return true;
    }
    int askState() override { if (!asked) return -1; if (hold) return 0; asked = false; return 1; }
    int askCode() override { return code; }
    std::string askBody() override { return body; }
    std::string askError() override { return err; }
    std::string modelName() override { return "RAW 420 MCM"; }
    std::string stamp() override { return "2026-10-10_1542"; }
    bool exists(const std::string &p) override { return card.count(p) > 0; }
    bool save(const std::string &p, const std::string &text, std::string &) override { card[p] = text; return true; }
    void listDiffs(std::vector<std::string> &out) override { out.clear(); for (auto &kv : card) if (kv.first.rfind("/rfdiff/", 0) == 0) out.push_back(kv.first); }
    bool load(const std::string &p, std::string &text) override { if (!card.count(p)) return false; text = card[p]; return true; }
};
static RenderCli cliHost;
static ldrc::CliPage cliPage(cliHost);
#include "gen/own_cli.inc"
static void cliRun(int ms) { for (int i = 0; i < ms; i += 50) { cliHost.t += 50; cliPage.poll(); } }
static bool cliTap(const std::string &text, bool console = false) {
    for (auto &it : cliPage.scene().items) {
        const bool want = console ? it.id == ldrc::CLI_ID_FIELD : it.text == text && (it.kind == ldrc::WifiItem::BUTTON || it.kind == ldrc::WifiItem::KEY || (it.kind == ldrc::WifiItem::ROW && it.id != ldrc::CLI_ID_CONSOLE));
        if (!want) continue;
        cliPage.touch(true, it.x + it.w / 2, it.y + it.h / 2); cliHost.t += 200; cliPage.touch(false, 0, 0); cliHost.t += 100; cliPage.poll();
        return true;
    }
    fprintf(stderr, "render: nothing called \"%s\" on the command line page\n", text.c_str());
    return false;
}
static void cliCommand(const std::string &cmd) { cliTap("", true); for (char c : cmd) cliTap(c == ' ' ? "Space" : std::string(1, c)); cliTap("Send"); cliRun(500); }
static void cliShot(const std::string &state) {
    cliPage.close(); cliHost = RenderCli();
    const std::string DIFF_FILE = "/rfdiff/RAW_420_MCM_2026-10-10_1542.txt";
    if (state == "nopipe") cliHost.ready = false;
    if (state == "armed") cliHost.armedV = true;
    if (state == "refused") cliHost.refuse = "needs the USB connection: plug the flight controller's USB socket into the dongle or receiver";
    if (state == "refused_linked") cliHost.refuse = "the transmitter is linked: the command line needs the safety on (arming channel 6 low) - the command line pauses the receiver's line to the flight controller, and save or exit restart it";
    if (state == "opening" || state == "diffcard") cliHost.hold = true;
    if (state.rfind("exec_", 0) == 0 && state != "exec_nofile") { std::string t = RF_DIFF; cliHost.card[DIFF_FILE] = t; }
    if (state == "exec_nofile") cliHost.card["/rfdiff/Goblin_700_2026-10-09_2010.txt"] = "# version\r\n";
    if (state.rfind("exec_pick", 0) == 0)                                 // (1.11.74) a fortnight of tuning: eight diffs of the model, one a day
        for (int d = 2; d <= 9; ++d) { char n[64]; snprintf(n, sizeof n, "/rfdiff/RAW_420_MCM_2026-10-%02d_%02d%02d.txt", d, 9 + d, 5 * d); cliHost.card[n] = RF_DIFF; }
    if (state == "exec_refused") cliHost.card["refuse_one"] = "1";
    if (state == "exec_running") cliHost.holdAfter = 14;
    if (state == "longreply") cliHost.card["slow"] = "1";
    if (state == "diffcard_failed") cliHost.refuse.clear();
    const int job = state.rfind("diffcard", 0) == 0 ? ldrc::CLI_TO_CARD : state.rfind("exec_", 0) == 0 ? ldrc::CLI_EXECUTE : ldrc::CLI_CONSOLE;
    cliPage.open(job);
    if (state == "diffcard_failed") { /* a reply that is not a whole diff */ cliHost.asked = true; cliHost.body = "###ERROR IN diff: CLI BUFFER OVERFLOW###\r\n# "; }
    cliRun(600);
    if (state == "console" || state == "scrolled" || state == "leave" || state == "gone") { cliCommand("status"); cliCommand("get gov_headspeed"); }
    if (state == "longreply") cliCommand("diff all");
    if (state == "scrolled") { for (auto &it : cliPage.scene().items) if (it.id == ldrc::CLI_ID_CONSOLE) { cliPage.touch(true, it.x + 100, it.y + 40); cliHost.t += 50; cliPage.touch(true, it.x + 100, it.y + 40 + 26 * 6); cliHost.t += 200; cliPage.touch(false, 0, 0); cliHost.t += 100; cliPage.poll(); } }
    if (state == "leave") { cliCommand("set gov_headspeed = 2450"); cliTap("OK"); }
    if (state == "gone") { cliHost.ready = false; cliRun(100); }
    if (state == "keys" || state == "keys_symbols" || state == "keys_empty") { cliTap("", true); if (state != "keys_empty") for (char c : std::string("set gov_headspeed = 24")) cliTap(c == ' ' ? "Space" : std::string(1, c)); }
    if (state == "keys_symbols") cliTap("#+=");
    if (state == "exec_running" || state == "exec_done" || state == "exec_refused") { cliTap("Execute"); cliRun(3000); }
    if (state == "exec_pick_next") cliTap(">");
    if (state == "exec_pick_ask") cliTap("8 Oct 2026  17:40");
    if (!cliPage.showing()) { fprintf(stderr, "render: the command line page closed (%s)\n", state.c_str()); return; }
    cliFrame(cliPage.scene());
}

// ------------------------------------------------------------------ the link's panel, the banner, the Bluetooth notice
#include "gen/own_ble.inc"
static void linkShot(const std::string &state) {
    teensyLink = RenderLink();
    if (state == "working") { teensyLink.stageNow = "sending /FW/TXFW.BIN"; teensyLink.size = 473152; teensyLink.done = 212918; teensyLink.step = 3; teensyLink.steps = 9; linkPanel(false); }
    else if (state == "done") { teensyLink.resultNow = "DONE: the transmitter runs 2.5.6 B93 11/10/26"; linkPanel(true); }
    else if (state == "failed") { teensyLink.bad = true; teensyLink.resultNow = "FAILED at sending /FW/TXFW.BIN: the transmitter stopped answering"; linkPanel(true); }
    else fprintf(stderr, "render: no link state %s\n", state.c_str());
}
#include "film.h"                                            // (1.11.89) the films: the menu, a film paused with its slider
static bool ownCommand(const std::string &s) {
    auto arg = [&](size_t n) { return s.size() > n ? s.substr(n) : std::string(); };
    // a page of our own replaces the one before it on the layer: the Teensy's page shows again first (banners are drawn ON the page)
    static const char *layer[] = { "@wifi ", "@update ", "@rxupdate ", "@pics ", "@cli ", "@link " };
    for (const char *l : layer) if (s.rfind(l, 0) == 0) { topOn = false; drawPage(); break; }
    if (s.rfind("@wifi ", 0) == 0) { wifiShot(arg(6)); return true; }
    if (s.rfind("@update ", 0) == 0) { updateShot(arg(8)); return true; }
    if (s.rfind("@rxupdate ", 0) == 0) { updateShot("rx_" + arg(10)); return true; }
    if (s.rfind("@pics ", 0) == 0) { picsShot(arg(6)); return true; }
    if (s.rfind("@cli ", 0) == 0) { cliShot(arg(5)); return true; }
    if (s.rfind("@link ", 0) == 0) { linkShot(arg(6)); return true; }
    if (s.rfind("@banner ", 0) == 0) { banner(arg(8).c_str(), 2000); return true; }   // (1.11.141: for how long)
    if (s.rfind("@film ", 0) == 0) { filmShot(arg(6)); return true; }
    if (s.rfind("@measure ", 0) == 0) { const std::string w = arg(9); printf("measure \"%s\": font0 %d, font2 %d, font6 %d px\n", w.c_str(), textWidth(0, w), textWidth(2, w), textWidth(6, w)); return true; }   // (a label's width in the screen's own fonts)
    if (s == "@pipe" || s == "@pipe late") { pipeNoticeLate = s == "@pipe late"; pipeNoticeDraw(); return true; }
    return false;
}
