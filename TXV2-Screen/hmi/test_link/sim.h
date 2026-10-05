// The make-believe world the host tests run in (test_link and test_update share it): two memory cards,
// a wire that loses and damages bytes, a clock, and a make-believe Teensy that runs the REAL LinkServer.
#ifndef LDRC_TEST_SIM_H
#define LDRC_TEST_SIM_H
#include "LdrcLink.h"
#include "LinkServer.h"
#include "LinkMaster.h"
#include <map>
#include <set>
#include <deque>
#include <string>
#include <vector>
#include <cstdio>
#include <cstdlib>
#include <cstring>

using namespace ldrc;

static uint32_t nowMs = 0;
static uint32_t rngState = 12345;
static uint32_t rnd() { rngState = rngState * 1664525u + 1013904223u; return rngState >> 8; }
static bool chance(double p) { return p > 0 && (rnd() % 1000000) < (uint32_t) (p * 1000000); }

// ------------------------------------------------------------------ a memory card
struct MemCard {
    std::map<std::string, std::vector<uint8_t> > files;
    std::vector<std::string> dirs;
    struct Open { std::string path; uint32_t pos; bool writing; bool used; };
    std::vector<Open> open_;
    bool present; int failWriteAfter;                 // fail the n-th write from now (-1 = never)
    std::string unreadableDir;                        // this folder cannot be read (a card error)
    int failRenameNo;                                 // the n-th rename from now fails (1 = the next), 0 = never
    uint32_t loseAtClose;                             // bytes of a written file's tail that never reach the card (its last buffer, at close: a full card)
    MemCard() : present(true), failWriteAfter(-1), failRenameNo(0), loseAtClose(0) {}
    bool isDir(const std::string &p) const { for (size_t i = 0; i < dirs.size(); ++i) if (dirs[i] == p) return true; return false; }
    bool exists(const char *p) const {
        if (files.count(p) || isDir(p)) return true;
        const std::string d = std::string(p) + "/";          // a folder that was never made, but holds files
        for (std::map<std::string, std::vector<uint8_t> >::const_iterator it = files.begin(); it != files.end(); ++it) if (it->first.compare(0, d.size(), d) == 0) return true;
        return false;
    }
    int open(const char *p, bool w) {
        if (w) files[p].clear(); else if (!files.count(p)) return -1;
        Open o; o.path = p; o.pos = 0; o.writing = w; o.used = true;
        for (size_t i = 0; i < open_.size(); ++i) if (!open_[i].used) { open_[i] = o; return (int) i; }
        open_.push_back(o); return (int) open_.size() - 1;
    }
    int read(int h, uint8_t *b, size_t n) {
        if (h < 0 || h >= (int) open_.size() || !open_[h].used) return -1;
        std::vector<uint8_t> &f = files[open_[h].path];
        size_t left = f.size() > open_[h].pos ? f.size() - open_[h].pos : 0; if (n > left) n = left;
        if (n) memcpy(b, &f[open_[h].pos], n);
        open_[h].pos += (uint32_t) n; return (int) n;
    }
    int write(int h, const uint8_t *b, size_t n) {
        if (h < 0 || h >= (int) open_.size() || !open_[h].used || !open_[h].writing) return -1;
        if (failWriteAfter == 0) { failWriteAfter = -1; return -1; }
        if (failWriteAfter > 0) failWriteAfter--;
        std::vector<uint8_t> &f = files[open_[h].path];
        f.insert(f.end(), b, b + n); open_[h].pos += (uint32_t) n; return (int) n;
    }
    bool seek(int h, uint32_t pos) { if (h < 0 || h >= (int) open_.size() || !open_[h].used) return false; open_[h].pos = pos; return true; }
    uint32_t size(int h) { if (h < 0 || h >= (int) open_.size() || !open_[h].used) return 0; return (uint32_t) files[open_[h].path].size(); }
    void close(int h) {
        if (h < 0 || h >= (int) open_.size() || !open_[h].used) return;
        if (open_[h].writing && loseAtClose) { std::vector<uint8_t> &f = files[open_[h].path]; if (f.size() > loseAtClose) f.resize(f.size() - loseAtClose); }
        open_[h].used = false;
    }
    bool remove(const char *p) { return files.erase(p) > 0; }
    bool rename(const char *a, const char *b) {
        if (failRenameNo > 0 && --failRenameNo == 0) return false;
        if (!files.count(a) || files.count(b)) return false;
        files[b] = files[a]; files.erase(a); return true;
    }
    bool mkdir(const char *p) { if (!isDir(p)) dirs.push_back(p); return true; }
    int openCount() const { int n = 0; for (size_t i = 0; i < open_.size(); ++i) if (open_[i].used) n++; return n; }
};
struct CardFs : public LinkFs {                      // the Teensy's view
    MemCard &c; CardFs(MemCard &card) : c(card) {}
    bool present() { return c.present; }
    bool exists(const char *p) { return c.exists(p); }
    bool remove(const char *p) { return c.remove(p); }
    bool rename(const char *a, const char *b) { return c.rename(a, b); }
    bool mkdir(const char *p) { return c.mkdir(p); }
    int open(const char *p, bool w) { return c.open(p, w); }
    int read(int h, uint8_t *b, size_t n) { return c.read(h, b, n); }
    int write(int h, const uint8_t *b, size_t n) { return c.write(h, b, n); }
    bool seek(int h, uint32_t pos) { return c.seek(h, pos); }
    uint32_t size(int h) { return c.size(h); }
    void close(int h) { c.close(h); }
    int entry(const char *dir, uint32_t index, char *name, size_t nameSize, uint32_t &size, bool &isDir) {
        if (!c.unreadableDir.empty() && c.unreadableDir == dir) return -1;
        std::string d = dir; if (d != "/") d += "/";
        std::vector<std::pair<std::string, int> > found;
        for (std::map<std::string, std::vector<uint8_t> >::iterator it = c.files.begin(); it != c.files.end(); ++it) {
            if (it->first.compare(0, d.size(), d) != 0) continue;
            std::string rest = it->first.substr(d.size());
            if (rest.find('/') == std::string::npos) found.push_back(std::make_pair(rest, (int) it->second.size()));
        }
        for (size_t i = 0; i < c.dirs.size(); ++i) {
            if (c.dirs[i].compare(0, d.size(), d) != 0) continue;
            std::string rest = c.dirs[i].substr(d.size());
            if (!rest.empty() && rest.find('/') == std::string::npos) found.push_back(std::make_pair(rest, -1));
        }
        if (index >= found.size()) return 0;
        snprintf(name, nameSize, "%s", found[index].first.c_str());
        isDir = found[index].second < 0; size = isDir ? 0 : (uint32_t) found[index].second;
        return 1;
    }
};
struct CardFiles : public MasterFiles {              // the screen's view
    MemCard &c; CardFiles(MemCard &card) : c(card) {}
    int open(const char *p, bool w) { return c.open(p, w); }
    int read(int h, uint8_t *b, size_t n) { return c.read(h, b, n); }
    int write(int h, const uint8_t *b, size_t n) { return c.write(h, b, n); }
    bool seek(int h, uint32_t pos) { return c.seek(h, pos); }
    uint32_t size(int h) { return c.size(h); }
    void close(int h) { c.close(h); }
    bool remove(const char *p) { return c.remove(p); }
    bool rename(const char *a, const char *b) { return c.rename(a, b); }
};

// ------------------------------------------------------------------ the wire: 921600 baud, lossy on request
struct Line {
    std::deque<uint8_t> flying, arrived; double drop, flip; uint32_t sent, lost, hurt;
    Line() : drop(0), flip(0), sent(0), lost(0), hurt(0) {}
    void put(const uint8_t *b, size_t n) {
        for (size_t i = 0; i < n; ++i) {
            sent++;
            if (chance(drop)) { lost++; continue; }
            uint8_t v = b[i]; if (chance(flip)) { v ^= (uint8_t) (1u << (rnd() % 8)); hurt++; }
            flying.push_back(v);
        }
    }
    void deliver() { for (int i = 0; i < 92 && !flying.empty(); ++i) { arrived.push_back(flying.front()); flying.pop_front(); } }   // one millisecond's worth
    void clear() { flying.clear(); arrived.clear(); }
};
struct Wire { Line toTeensy, toScreen; void deliver() { toTeensy.deliver(); toScreen.deliver(); } };

// ------------------------------------------------------------------ a make-believe Teensy
// It runs the REAL LinkServer and LinkSession, and copies what include/LinkMode.h does around them: the link
// refused (but who-it-is given) when a model is connected or was a moment ago, or the motor is on, or the safety
// off; firmware on trial accepted after 30 s of running as a transmitter; the previous firmware put back when the
// new one has started three times without that; what is in memory saved on the way into the link (as at power-off),
// nothing saved once one of the pilot's files has been replaced, and a restart when such a link closes.
//
// Its "memory" is `settings` (what the sticks and switches do, as loaded from /models.dat at start-up: here the
// first 64 bytes of the file). How a firmware READS those bytes is `reads[version]`: a number mixed into the
// fingerprint it gives. Two versions with the same number read the settings alike.
struct FakeTeensy : public LinkPlatform {
    MemCard &card; Wire &wire; CardFs fs; LinkServer *server; LinkSession *session; Parser parser; Knock knock;
    std::string version, previous, state, pending;
    bool knowsLink, linkMode, restarting, swapPending, brokenNew, modelConnected, absent;
    bool motorOn, safetyOff, safetyDefined, modelJustNow, saysSettings, savesOnEntry, goingBack;
    std::map<std::string, uint32_t> reads;            // how each firmware reads the settings (none given: 1)
    std::map<std::string, bool> says;                 // whether a firmware says how it reads them (none given: saysSettings)
    std::vector<uint8_t> settings; bool loaded;
    uint32_t restartUntil, nextChatter, crashAt, bootedAt, normalUpMs;
    int framesInNormalMode, framesHandled, restarts, starts, rollbacks, restartsForFiles, saves, savesRefused;
    std::string extraText;
    std::set<uint32_t> proven; uint32_t pendingCrc = 0, runningCrc = 0;   // B18: packages that passed their trial here (FW/PROVEN.TXT)
    FakeTeensy(MemCard &c, Wire &w) : card(c), wire(w), fs(c), server(0), session(0), version("2.5.6 P 26/09/26"), state("confirmed"),
        knowsLink(true), linkMode(false), restarting(false), swapPending(false), brokenNew(false), modelConnected(false), absent(false),
        motorOn(false), safetyOff(false), safetyDefined(false), modelJustNow(false), saysSettings(true), savesOnEntry(true), goingBack(false), loaded(false), restartUntil(0), nextChatter(0), crashAt(0),
        bootedAt(0), normalUpMs(0), framesInNormalMode(0), framesHandled(0), restarts(0), starts(0), rollbacks(0), restartsForFiles(0), saves(0), savesRefused(0) { newServer(); }
    ~FakeTeensy() { delete session; delete server; }
    void newServer() { delete session; delete server; server = new LinkServer(fs, *this); session = new LinkSession(*server); }   // (LinkMode() makes them afresh each time)
    // ---- the transmitter's own use of /models.dat
    void load() { settings.clear(); if (card.files.count("/models.dat")) { const std::vector<uint8_t> &f = card.files["/models.dat"]; settings.assign(f.begin(), f.begin() + (f.size() < 64 ? f.size() : 64)); } loaded = true; }
    bool save() {                                     // SaveAllParameters(): memory goes over the start of the file
        if (server->userDataChanged()) { savesRefused++; return false; }
        if (!loaded || !card.files.count("/models.dat")) return false;
        std::vector<uint8_t> &f = card.files["/models.dat"];
        for (size_t i = 0; i < settings.size() && i < f.size(); ++i) f[i] = settings[i];
        saves++; return true;
    }
    uint32_t fingerprint() {
        if (!loaded) load();
        const uint32_t how = reads.count(version) ? reads[version] : 1;
        uint32_t c = crc32((const uint8_t *) &how, 4);
        return settings.empty() ? c : crc32(&settings[0], settings.size(), c);
    }
    // The rule is the pilot's (FlightGuard.h): with a safety switch defined, the safety decides and the motor does not
    // matter; with none, the motor decides.
    bool radiosMustBeOff() const { return safetyDefined ? safetyOff : motorOn; }
    uint8_t status() const { return (uint8_t) ((motorOn ? 1 : 0) | ((safetyDefined && safetyOff) ? 2 : 0) | (modelConnected ? 4 : 0) | (safetyDefined ? 8 : 0) | (modelJustNow ? 16 : 0) | (radiosMustBeOff() ? 32 : 0)); }
    uint8_t refusal() const { return modelConnected ? LE_BUSY : modelJustNow ? LE_MODEL_JUST_NOW : radiosMustBeOff() ? (safetyDefined ? LE_SAFETY_OFF : LE_MOTOR_ON) : (uint8_t) LE_OK; }
    const char *extra() {
        char b[64];
        if (says.count(version) ? says[version] : saysSettings) snprintf(b, sizeof b, "mfp=1.%08lX;st=%u", (unsigned long) fingerprint(), (unsigned) status()); else b[0] = 0;
        extraText = b; return extraText.c_str();
    }
    // LinkPlatform
    const char *firmwareVersion() { return version.c_str(); }
    const char *target() { return "fw_teensy41"; }
    const char *updateState() { return state.c_str(); }
    uint32_t uptimeSeconds() { return (nowMs - bootedAt) / 1000; }
    int startsOnTrial() { return starts; }
    uint8_t stageFirmware(const char *path) {
        FwHeader h; const uint8_t e = checkFirmwarePackage(fs, *this, path, target(), 0x3C0000, h);
        if (e != LE_OK) return e;
        pending = h.version; pendingCrc = h.crc; goingBack = false; return LE_OK;
    }
    uint8_t stagePrevious() { if (previous.empty()) return LE_NO_PREVIOUS; pending = previous; goingBack = true; return LE_OK; }
    void confirmFirmware() { if (state == "trial") proven.insert(runningCrc); state = "confirmed"; }
    void busy() {}

    void send(const Frame &f) { uint8_t raw[LINK_MAX_FRAME]; wire.toScreen.put(raw, encode(f, raw)); }
    void restart(uint32_t forMs) { restarting = true; restartUntil = nowMs + forMs; linkMode = false; server->abandon(); newServer(); parser.reset(); knock.reset(); restarts++; loaded = false; }
    void leaveLink() {                                // the end of LinkMode()
        linkMode = false; server->abandon();
        if (server->userDataChanged()) { restartsForFiles++; restart(3000); }
    }
    void tick() {
        if (absent) { wire.toTeensy.arrived.clear(); return; }      // a screen on the bench, no main board
        if (crashAt && nowMs >= crashAt) { crashAt = 0; restart(1500); }
        if (restarting) {
            wire.toTeensy.arrived.clear();                          // deaf while it restarts
            if (nowMs < restartUntil) return;
            restarting = false; bootedAt = nowMs; normalUpMs = 0; load();
            if (swapPending) {
                swapPending = false;
                if (goingBack) { version = pending; state = "rolledback"; starts = 0; goingBack = false; }      // (PREVIOUS.BIN stays what it is)
                else { previous = version; version = pending; runningCrc = pendingCrc; state = proven.count(pendingCrc) ? "confirmed" : "trial"; starts = 0; }   // (B18: proven here before = no trial)
                load();
            }
            if (state == "trial") {                                 // the start-up code
                starts++;
                if (starts > 3) { const std::string bad = version; version = previous; previous = bad; state = "rolledback"; starts = 0; rollbacks++; restart(5000); return; }
            }
            nextChatter = nowMs;
        }
        if (!linkMode) {
            normalUpMs++;
            if (state == "trial" && normalUpMs > 30000) { state = "confirmed"; proven.insert(runningCrc); }
            if (brokenNew && state == "trial" && normalUpMs >= 5000) { restart(3000); return; }      // the watchdog
            if (nowMs >= nextChatter) {                             // a transmitter talks to its display all the time
                const char *c = "Connected.txt=\"Not connected\"\xFF\xFF\xFF";
                wire.toScreen.put((const uint8_t *) c, strlen(c)); nextChatter = nowMs + 400;
            }
        }
        while (!wire.toTeensy.arrived.empty()) {
            const uint8_t b = wire.toTeensy.arrived.front(); wire.toTeensy.arrived.pop_front();
            Frame req, rep;
            if (linkMode) {
                LinkAction a;
                if (!session->byte(b, nowMs, rep, a)) continue;
                framesHandled++;
                send(rep);
                if (a == LA_LEAVE) { leaveLink(); if (restarting) return; }
                if (a == LA_SWAP_AND_RESTART) { swapPending = true; restart(3500); return; }
                continue;
            }
            // as a transmitter: the words that open the link, or (new firmware only) a frame that must be swallowed and refused
            if (knowsLink && parser.push(b, req, nowMs)) { framesInNormalMode++; rep.clear((uint8_t) (LK_REPLY | req.type), req.seq); rep.put8(LE_SEQUENCE); send(rep); knock.reset(); continue; }
            if (knowsLink && !parser.midFrame() && knock.push(b)) {
                parser.reset();
                if (refusal() != LE_OK) { server->hello(rep, 0); rep.payload[0] = refusal(); send(rep); continue; }
                newServer();
                linkMode = true;
                session->begin(nowMs, rep); send(rep);
                if (savesOnEntry) save();             // as at power-off: what is in memory goes to the card, THEN the files are the link's
            }
        }
        if (linkMode && session->expired(nowMs)) leaveLink();
    }
};

// ------------------------------------------------------------------ the screen's end
struct ScreenPort : public MasterPort {
    Wire &wire; uint32_t framesWritten, knocks; std::vector<uint32_t> knockTimes;
    ScreenPort(Wire &w) : wire(w), framesWritten(0), knocks(0) {}
    void write(const uint8_t *b, size_t n) { framesWritten++; wire.toTeensy.put(b, n); }
    uint32_t ms() { return nowMs; }
    void knock() { knocks++; knockTimes.push_back(nowMs); wire.toTeensy.put((const uint8_t *) LDRC_LINK_KNOCK, strlen(LDRC_LINK_KNOCK)); }
};

struct World {
    MemCard screenCard, teensyCard; Wire wire; FakeTeensy teensy; ScreenPort port; CardFiles files; LinkMaster master;
    Router router; int ff; uint32_t displayCommands, displayBytes;
    World() : teensy(teensyCard, wire), port(wire), files(screenCard), master(port, files), ff(0), displayCommands(0), displayBytes(0) {}
    // the screen's serial pump: every byte sorted, display commands counted, frames handed to the master
    void pump() {
        Frame f;
        while (!wire.toScreen.arrived.empty()) {
            const uint8_t b = wire.toScreen.arrived.front(); wire.toScreen.arrived.pop_front();
            const Router::What w = router.push(b, nowMs, f);
            if (w == Router::WHOLE_FRAME) { master.frameArrived(f); continue; }
            if (w != Router::TO_DISPLAY) continue;
            displayBytes++;
            if (b == 0xFF) { if (++ff == 3) { ff = 0; displayCommands++; master.sawDisplayTraffic(); } } else ff = 0;
        }
    }
    // run until the master stops or the time is up; returns true if it finished well
    bool run(uint32_t limitMs) {
        const uint32_t end = nowMs + limitMs;
        while (master.running() && nowMs < end) {
            nowMs++;
            wire.deliver();
            teensy.tick();
            pump();
            master.poll();
        }
        return master.finished();
    }
};

static std::vector<uint8_t> blob(size_t n, uint32_t seed) { std::vector<uint8_t> v(n); uint32_t s = seed * 2654435761u + 1; for (size_t i = 0; i < n; ++i) { s = s * 1664525u + 1013904223u; v[i] = (uint8_t) (s >> 16); } return v; }
static std::vector<uint8_t> package(const char *version, const char *target, size_t imageSize, bool nameInside = true, bool spoil = false) {
    std::vector<uint8_t> image = blob(imageSize, 99);
    if (nameInside) memcpy(&image[1000], "fw_teensy41", 11);
    FwHeader h; memset(&h, 0, sizeof h); h.size = (uint32_t) imageSize; h.crc = crc32(&image[0], image.size());
    snprintf(h.version, sizeof h.version, "%s", version); snprintf(h.target, sizeof h.target, "%s", target);
    std::vector<uint8_t> out(FW_HEADER_SIZE); fwHeaderBuild(h, &out[0]);
    if (spoil) image[5000] ^= 0x10;
    out.insert(out.end(), image.begin(), image.end());
    return out;
}

#endif
