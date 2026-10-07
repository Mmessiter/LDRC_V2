#include "LdrcUpdate.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace ldrc {

static const char *STATE_FILE = "/update/state.txt";
static const char *LOG_FILE = "/update/log.txt";
static const char *SCREEN_MARK = "/update/screen_files.txt";        // the list of screen files last put in place completely (its CRC)
static const char *SCREEN_HAVE = "/update/screen_have.txt";         // ... and the list itself: what is on the card, file by file
static const char *TEENSY_MARK_LOCAL = "/update/teensy_files.txt";  // the same for the Teensy's files: kept on the TEENSY's card ...
static const char *TEENSY_MARK_REMOTE = "/FW/FILES.TXT";
static const char *TEENSY_MARK_NOW = "/update/teensy_files.now";    // ... and read from there at every check
static const char *TEENSY_PACKAGE = "/teensy/TXFW.BIN";
static const char *TEENSY_PACKAGE_REMOTE = "/FW/TXFW.BIN";
static const char *TEENSY_COPIES = "/teensy/sd";                    // the screen's copies of the Teensy's files live below this
static const char *SCREEN_IMAGE = "/update/screen.bin";
static const char *STAGING = "/update/new/";
static const char *LOGS_KEPT = "/teensy/backup/log";               // the pilot's logs: one store that grows, not a copy each time (they are many, and never change)
static const char *DO_NOT = "Do not switch off";
static const char *FLICKER = "The screen may flicker while this runs";      // (the main board repaints its page underneath, and restarts: Malcolm, 30-9-2026)

// ------------------------------------------------------------------ small things
std::string hex8(uint32_t v) { char b[12]; snprintf(b, sizeof b, "%08lX", (unsigned long) v); return b; }
static std::string num(uint32_t v) { char b[12]; snprintf(b, sizeof b, "%lu", (unsigned long) v); return b; }
static std::string trim(const std::string &s) {
    size_t a = 0, b = s.size();
    while (a < b && (s[a] == ' ' || s[a] == '\t' || s[a] == '\r' || s[a] == '\n')) a++;
    while (b > a && (s[b - 1] == ' ' || s[b - 1] == '\t' || s[b - 1] == '\r' || s[b - 1] == '\n')) b--;
    return s.substr(a, b - a);
}
static bool parseHex(const std::string &s, uint32_t &v) {
    if (s.empty() || s.size() > 8) return false;
    v = 0;
    for (size_t i = 0; i < s.size(); ++i) {
        const char c = s[i]; uint32_t d;
        if (c >= '0' && c <= '9') d = (uint32_t) (c - '0'); else if (c >= 'A' && c <= 'F') d = (uint32_t) (c - 'A' + 10); else if (c >= 'a' && c <= 'f') d = (uint32_t) (c - 'a' + 10); else return false;
        v = (v << 4) | d;
    }
    return true;
}
static bool parseNum(const std::string &s, uint32_t &v) {
    if (s.empty() || s.size() > 9) return false;                      // under a thousand million: no overflow
    v = 0;
    for (size_t i = 0; i < s.size(); ++i) { if (s[i] < '0' || s[i] > '9') return false; v = v * 10 + (uint32_t) (s[i] - '0'); }
    return true;
}
static std::string sizeText(uint32_t bytes) {
    char b[24];
    if (bytes < 1024u * 1024u) snprintf(b, sizeof b, "%lu kB", (unsigned long) ((bytes + 1023) / 1024));
    else snprintf(b, sizeof b, "%lu.%lu MB", (unsigned long) (bytes / (1024u * 1024u)), (unsigned long) ((bytes % (1024u * 1024u)) * 10 / (1024u * 1024u)));
    return b;
}
static std::string leaf(const std::string &path) { const size_t s = path.rfind('/'); return s == std::string::npos ? path : path.substr(s + 1); }
static std::string capital(std::string s) { if (!s.empty() && s[0] >= 'a' && s[0] <= 'z') s[0] = (char) (s[0] - 32); return s; }
static std::string sentence(std::string s) { s = capital(trim(s)); if (!s.empty() && s[s.size() - 1] != '.' && s[s.size() - 1] != '?' && s[s.size() - 1] != '!') s += "."; return s; }
static std::string blobName(uint32_t crc, uint32_t size) { return hex8(crc) + "-" + num(size) + ".bin"; }
static bool startsWith(const std::string &s, const char *p) { return s.compare(0, strlen(p), p) == 0; }
static bool startsWithNoCase(const std::string &s, const char *p) {
    const size_t n = strlen(p); if (s.size() < n) return false;
    for (size_t i = 0; i < n; ++i) { char a = s[i], b = p[i]; if (a >= 'a' && a <= 'z') a = (char) (a - 32); if (b >= 'a' && b <= 'z') b = (char) (b - 32); if (a != b) return false; }
    return true;
}
// One line at a time out of a text.
static bool nextLine(const std::string &text, size_t &at, std::string &out) {
    if (at >= text.size()) return false;
    size_t e = text.find('\n', at); if (e == std::string::npos) e = text.size();
    out = text.substr(at, e - at); at = e + 1;
    if (!out.empty() && out[out.size() - 1] == '\r') out.erase(out.size() - 1);
    return true;
}
// A path we are prepared to write to. The rule is the link's (plainPath): among other things no part of it begins
// with a space or ends with a space or a dot - FAT drops those, so "/models.dat." IS models.dat. And it is no
// longer than the Teensy firmware of before 2.5.6 B8 accepts (95), for that is what may be running.
static const size_t LONGEST_NAME = 95;
static bool goodName(const std::string &p) { return p.size() <= LONGEST_NAME && p.find('\0') == std::string::npos && plainPath(p.c_str()); }
static std::string shown(const std::string &name) { return name.size() > 60 ? name.substr(0, 57) + "..." : name; }   // (a bad name may be 200 kB long)

// ------------------------------------------------------------------ what the website says
bool parseRelease(const std::string &text, UpdRelease &r, std::string &why) {
    r = UpdRelease();
    bool head = false, end = false; size_t at = 0; std::string l;
    while (nextLine(text, at, l)) {
        l = trim(l);
        if (l.empty() || l[0] == '#') continue;
        if (end) { why = "there is text after its end"; return false; }
        const size_t eq = l.find('=');
        if (eq == std::string::npos) { why = "a line without '='"; return false; }
        const std::string k = trim(l.substr(0, eq)), v = trim(l.substr(eq + 1));
        if (k == "ldrc-release") { if (v != "1") { why = "it is for a newer screen than this one"; return false; } head = true; continue; }
        if (!head) { why = "it is not a release description"; return false; }
        if (k == "end") { end = true; continue; }
        if (k == "name") r.name = v; else if (k == "date") r.date = v; else if (k == "notes") r.notes = v; else if (k == "base") r.base = v;
        else {
            const size_t dot = k.find('.');
            if (dot == std::string::npos) continue;                     // a key from the future: not ours to judge
            const std::string part = k.substr(0, dot), field = k.substr(dot + 1);
            UpdPart *p = part == "teensy" ? &r.teensy : part == "teensy_files" ? &r.teensyFiles : part == "screen" ? &r.screen : part == "screen_files" ? &r.screenFiles : (UpdPart *) 0;
            if (!p) continue;
            bool ok = true;
            if (field == "version") p->version = v;
            else if (field == "file") { p->file = v; p->present = true; }
            else if (field == "size") ok = parseNum(v, p->size);
            else if (field == "crc") ok = parseHex(v, p->crc);
            else if (field == "count") ok = parseNum(v, p->count);
            else if (field == "bytes") ok = parseNum(v, p->bytes);
            if (!ok) { why = "a number in it cannot be read (" + k + ")"; return false; }
        }
    }
    if (!head) { why = "it is not a release description"; return false; }
    if (!end) { why = "it is incomplete"; return false; }
    if (r.name.empty()) { why = "the release has no name"; return false; }
    if (!startsWith(r.base, "https://") || r.base[r.base.size() - 1] != '/') { why = "its address is not an https:// folder"; return false; }
    UpdPart *parts[4] = { &r.teensy, &r.teensyFiles, &r.screen, &r.screenFiles };
    for (int i = 0; i < 4; ++i) {
        UpdPart &p = *parts[i];
        if (!p.present) continue;
        if (p.file.empty() || p.file[0] == '/' || p.file.find("..") != std::string::npos || p.file.find("://") != std::string::npos || p.size == 0) { why = "a part of it is not described properly"; return false; }
        if ((i == 0 || i == 2) && p.version.empty()) { why = "firmware without a version"; return false; }
        if ((i == 0 || i == 2) && p.version.size() > 31) { why = "a version text is too long"; return false; }
    }
    return true;
}

bool parseList(const std::string &text, bool forTeensy, std::vector<UpdEntry> &out, std::string &why) {
    out.clear();
    size_t at = 0; std::string l;
    while (nextLine(text, at, l)) {
        if (trim(l).empty() || l[0] == '#') continue;
        const size_t a = l.find(' '), b = a == std::string::npos ? a : l.find(' ', a + 1);
        if (b == std::string::npos) { why = "a line of the list cannot be read"; return false; }
        UpdEntry e; e.path = l.substr(b + 1);
        if (!parseHex(l.substr(0, a), e.crc) || a != 8 || !parseNum(l.substr(a + 1, b - a - 1), e.size) || e.size > 64u * 1024u * 1024u) { why = "a line of the list cannot be read"; return false; }
        if (!goodName(e.path)) { why = "the list names a file that cannot be written (" + shown(e.path) + ")"; return false; }
        if (forTeensy) {
            // Never the pilot's models or logs, never the firmware area, never the link's own files: those are not the website's to write.
            if (isUserData(e.path.c_str()) || startsWithNoCase(e.path, "/FW/") || startsWithNoCase(e.path, "/LINK.")) { why = "the list names a file that is the pilot's own (" + shown(e.path) + ")"; return false; }
        } else if (!startsWith(e.path, "/hmi/") && !startsWith(e.path, "/images/")) { why = "the list names a file outside the screen's folders (" + shown(e.path) + ")"; return false; }
        out.push_back(e);
        if (out.size() > 2000) { why = "the list is too long"; return false; }
    }
    if (out.empty()) { why = "the list is empty"; return false; }
    return true;
}

bool parseRecent(const std::string &text, std::vector<UpdRecent> &out, std::string &why) {
    out.clear();
    bool head = false, end = false; size_t at = 0; std::string l;
    while (nextLine(text, at, l)) {
        l = trim(l);
        if (l.empty() || l[0] == '#') continue;
        if (end) { why = "there is text after its end"; return false; }
        const size_t eq = l.find('=');
        if (eq == std::string::npos) { why = "a line without '='"; return false; }
        const std::string k = trim(l.substr(0, eq)), v = l.substr(eq + 1);
        if (k == "ldrc-recent") { if (trim(v) != "1") { why = "it is for a newer screen than this one"; return false; } head = true; continue; }
        if (!head) { why = "it is not a list of releases"; return false; }
        if (k == "end") { end = true; continue; }
        if (k != "release") continue;
        std::vector<std::string> f; size_t p = 0;
        for (int i = 0; i < 5; ++i) { const size_t bar = v.find('|', p); if (bar == std::string::npos) { why = "a release in it is not described properly"; return false; } f.push_back(trim(v.substr(p, bar - p))); p = bar + 1; }
        f.push_back(trim(v.substr(p)));
        UpdRecent r; r.name = f[0]; r.date = f[1]; r.teensy = f[2]; r.screen = f[3]; r.path = f[4]; r.notes = f[5];
        const bool good = !r.name.empty() && startsWith(r.path, "v/") && r.path.size() > 14 && r.path.compare(r.path.size() - 12, 12, "/release.txt") == 0 &&
                          r.path.find("..") == std::string::npos && r.path.find("://") == std::string::npos && r.path.find('\\') == std::string::npos;
        if (!good) { why = "a release in it is not described properly"; return false; }
        if (out.size() < 6) out.push_back(r);
    }
    if (!head) { why = "it is not a list of releases"; return false; }
    if (!end) { why = "it is incomplete"; return false; }
    return true;
}

// ------------------------------------------------------------------ the panel
Updater::Updater(UpdateHost &host, LinkMaster &link, const std::string &latestUrl)
    : host_(host), link_(link), latestUrl_(latestUrl), phase_(P_IDLE),
      since_(0), lastPoke_(0), shownAt_(0), linkAfter_(0), restartAt_(0), stageSince_(0),
      linkOurs_(false), linkWanted_(false), linkStarted_(false), changing_(false), silent_(false), waiting_(false), noteWifi_(false),
      shownFlying_(false), mustSee_(false), textTries_(0), textMax_(8192),
      teensyThere_(false), teensyFellBack_(false), choosing_(false), noteVersions_(false), freshDone_(false), freshChoosing_(false), needTeensyFw_(false), needTeensyFiles_(false), needScreenFw_(false), needScreenFiles_(false),
      listStep_(0), at_(0), sub_(0), tries_(0), fetchTotal_(0), fetchDone_(0), fetchCount_(0), fetchIndex_(0),
      placed_(0), trialSeen_(0), keptFiles_(0), stTeensyThere_(false), stTeensyChanged_(false), stScreenFw_(false), stFiles_(0), stKept_(0), trialStep_(0), resultGood_(false),
      rxFlow_(false), rxHave_(0), rxLatest_(0), rxPhaseSeen_(0), rxNewsAt_(0), rxQuietTotal_(0), again_(false) {}

void Updater::note(const std::string &line) {
    log_.push_back(line);
    if (log_.size() > 300) log_.erase(log_.begin());
    const std::string when = host_.stamp();
    host_.appendText(LOG_FILE, (when.empty() ? std::string() : when + "  ") + line + "\n");
}
void Updater::show(UpdView::Kind kind, const std::string &title) {
    const uint32_t s = view_.serial + 1;
    view_ = UpdView(); view_.kind = kind; view_.title = title; view_.serial = s;
    shownAt_ = host_.ms(); shownFlying_ = flyingNow() != UpdateHost::FLY_NO;
}
// A connected model bars an update of the transmitter, but it is the very thing the receiver's own update needs.
int Updater::flyingNow() const {
    const int f = host_.flying();
    return (rxFlow_ && f == UpdateHost::FLY_MODEL) ? UpdateHost::FLY_NO : f;
}
// Flying comes first. Whatever the pilot asked for is not begun, and the panel says why and what to do.
bool Updater::notNow() {
    switch (flyingNow()) {
    case UpdateHost::FLY_MOTOR:          message("The motor is on", "Switch the motor off,", "then check again."); return true;
    case UpdateHost::FLY_SAFETY:         message("The safety is off", "Put the safety on,", "then check again."); return true;
    case UpdateHost::FLY_MODEL:          message("A model is connected", "Switch the model off,", "then check again."); return true;
    case UpdateHost::FLY_MODEL_JUST_NOW: message("A model was connected", "less than a minute ago.", "Wait a minute, then check again."); return true;
    default: return false;
    }
}
static const char *flyingWords(int why) {
    return why == UpdateHost::FLY_MOTOR ? "the motor was switched on" : why == UpdateHost::FLY_SAFETY ? "the safety was taken off" :
           why == UpdateHost::FLY_MODEL ? "a model was connected" : why == UpdateHost::FLY_MODEL_JUST_NOW ? "a model was connected a moment ago" : "";
}
static std::string oneLine(std::string s) { for (size_t i = 0; i < s.size(); ++i) if (s[i] == '\n' || s[i] == '\r') s[i] = ' '; return s; }
void Updater::line(const std::string &text) { view_.lines.push_back(oneLine(text)); changed(); }
void Updater::row(const std::string &what, const std::string &now, const std::string &next) { UpdRow r; r.what = what; r.now = now; r.next = next; view_.rows.push_back(r); changed(); }
void Updater::buttons(const std::string &b1, const std::string &b2) { if (view_.button1 == b1 && view_.button2 == b2) return; view_.button1 = b1; view_.button2 = b2; changed(); }
void Updater::setLine(size_t index, const std::string &text) {
    if (view_.lines.size() <= index) view_.lines.resize(index + 1);
    if (view_.lines[index] == text) return;
    view_.lines[index] = text; changed();
}
void Updater::bar(uint32_t done, uint32_t total) { view_.bar = true; view_.barDone = done > total ? total : done; view_.barTotal = total; }
void Updater::message(const std::string &title, const std::string &l1, const std::string &l2) {
    note(title + (l1.empty() ? "" : ": " + l1) + (l2.empty() ? "" : " " + l2));
    show(UpdView::NOTE, title);
    if (!l1.empty()) line(l1);
    if (!l2.empty()) line(l2);
    buttons("OK", "");
    changing_ = false; noteWifi_ = false; noteVersions_ = false; phase_ = P_NOTE;
}
// No WiFi: the way out is offered with the news. The first button opens the WiFi page.
void Updater::noWifi(const std::string &title, const std::string &l1, const std::string &l2) {
    message(title, l1, l2);
    buttons("WiFi setup", "OK");
    noteWifi_ = true;
}
void Updater::close() {
    const uint32_t s = view_.serial + 1;
    view_ = UpdView(); view_.serial = s;
    phase_ = P_IDLE; changing_ = false; waiting_ = false; rxFlow_ = false; again_ = false; freshKind_.clear(); freshUrl_.clear(); freshChoosing_ = false; haveText_.clear();
    items_.clear(); teensyList_.clear(); screenList_.clear();
    host_.wifiWanted(false);
}
std::string Updater::url(const std::string &file) const { return rel_.base + file; }
std::string Updater::stagedOf(const Item &it) const {
    if (it.kind != 3) return it.path;
    std::string s = std::string(STAGING) + blobName(it.crc, it.size);
    if (it.twin) s += "." + num((uint32_t) it.twin - 1);
    return s;
}
std::string Updater::urlOf(const Item &it) const {
    if (it.kind == 0) return url(rel_.teensy.file);
    if (it.kind == 2) return url(rel_.screen.file);
    return url("files/" + blobName(it.crc, it.size));
}
std::string Updater::remoteOf(const Item &it) const {
    if (it.kind == 0) return TEENSY_PACKAGE_REMOTE;
    if (it.kind == 1) return it.path.substr(strlen(TEENSY_COPIES));
    return "";
}

// ------------------------------------------------------------------ what is kept across a restart
std::string Updater::stateText(const std::string &stage) const {
    std::string s = "stage=" + stage + "\n";
    s += "release=" + stRelease_ + "\n";
    s += "teensy=" + stTeensy_ + "\n";
    s += std::string("teensy_there=") + (stTeensyThere_ ? "1" : "0") + "\n";
    s += std::string("teensy_changed=") + (stTeensyChanged_ ? "1" : "0") + "\n";
    s += "screen_from=" + stFrom_ + "\n";
    s += "screen_to=" + stTo_ + "\n";
    s += std::string("screen_fw=") + (stScreenFw_ ? "1" : "0") + "\n";
    s += "files=" + num((uint32_t) stFiles_) + "\n";
    s += "kept=" + num((uint32_t) stKept_) + "\n";
    s += "settings=" + stSettings_ + "\n";
    if (mustSee_) s += "mustsee=1\n";
    for (size_t i = 0; i < stWarn_.size() && i < 4; ++i) s += "warn=" + stWarn_[i].substr(0, 160) + "\n";
    return s;
}
void Updater::saveState(const std::string &stage) { host_.writeText(STATE_FILE, stateText(stage)); }

void Updater::versionRows() {
    if (!stTeensy_.empty()) row("Transmitter", stTeensy_, "");
    row("Screen", host_.screenVersion(), "");
}
void Updater::result(bool good, const std::string &title, const std::vector<std::string> &lines) {
    changing_ = false; resultGood_ = good; waiting_ = false;
    show(good ? UpdView::GOOD : UpdView::BAD, title);
    if (good) versionRows();
    for (size_t i = 0; i < lines.size(); ++i) if (!lines[i].empty()) line(lines[i]);
    buttons("OK", "");
    phase_ = P_RESULT;
    std::string s = stateText("result");                   // kept until OK is pressed: a verdict is never lost to a power cut
    s += std::string("good=") + (good ? "1" : "0") + "\n" + "title=" + title + "\n";
    for (size_t i = 0; i < view_.rows.size(); ++i) s += "row=" + view_.rows[i].what + "|" + view_.rows[i].now + "|" + view_.rows[i].next + "\n";
    for (size_t i = 0; i < view_.lines.size(); ++i) s += "line=" + view_.lines[i] + "\n";
    host_.writeText(STATE_FILE, s);
    std::string all = title;
    for (size_t i = 0; i < view_.rows.size(); ++i) all += " | " + view_.rows[i].what + " " + view_.rows[i].now;
    for (size_t i = 0; i < view_.lines.size(); ++i) all += " | " + view_.lines[i];
    note((good ? "DONE: " : "FAILED: ") + all);
}
void Updater::fail(const std::string &stage, const std::string &why) {
    std::vector<std::string> lines;
    lines.push_back("It stopped at: " + stage + ".");
    lines.push_back(sentence(why));
    if (!changing_) { lines.push_back("Nothing was changed."); restoreHave(); }
    else if (phase_ == P_TEENSY && !stTeensyChanged_) lines.push_back("The screen was not changed.");
    else if (phase_ == P_TEENSY || phase_ == P_PLACE) lines.push_back(std::string(stTeensyChanged_ ? "The main board was updated. " : "") + "Check for update again to finish.");
    else if (phase_ == P_FLASH) lines.push_back(stTeensyChanged_ ? "The main board was updated. The screen's firmware was not." : "The screen's firmware was not changed.");
    host_.stopWork();
    result(false, "Update failed", lines);
}
void Updater::finishGood() {
    std::vector<std::string> lines;
    host_.tidy(std::string(STAGING, strlen(STAGING) - 1));   // whatever earlier attempts fetched and this one did not need
    if (stKept_ > 0) lines.push_back("Your models, settings and logs were copied first: " + num((uint32_t) stKept_) + " files.");
    for (size_t i = 0; i < stWarn_.size() && i < 4; ++i) lines.push_back(sentence(stWarn_[i]));
    if (stSettings_ == "same") lines.push_back("The new firmware reads your model's settings exactly as the old one did.");
    else if (stSettings_ == "unknown") lines.push_back("How the new firmware reads your model's settings could not be compared with the old one. Check the controls before flying.");
    result(true, "Update complete", lines);
}

// ------------------------------------------------------------------ the link to the Teensy
// A job for the Teensy never starts within 0.4 s of a keep-awake: both are "touch events", and the Teensy
// takes bytes that arrive without a gap as one event.
void Updater::linkGo() {
    const uint32_t now = host_.ms();
    linkWanted_ = true; linkStarted_ = false; linkOurs_ = true;
    linkAfter_ = (int32_t) (lastPoke_ + 400 - now) > 0 ? lastPoke_ + 400 : now;
}
bool Updater::linkBusy() const { return linkWanted_ || (linkOurs_ && linkStarted_ && link_.running()); }

// ------------------------------------------------------------------ check
void Updater::begin() {
    if (phase_ != P_IDLE) return;
    log_.clear(); choosing_ = false; again_ = false;
    { const size_t cut = latestUrl_.rfind('/'); recentUrl_ = latestUrl_.substr(0, cut + 1) + "recent.txt"; }
    note("---- check for update (screen " + host_.screenVersion() + ")");
    if (notNow()) return;                          // (a connected model included: the receiver has a button of its own, on the Model setup page)
    if (link_.running() || host_.busy()) { message("Busy", "Another job is still running.", "Try again in a minute."); return; }
    if (host_.exists(STATE_FILE)) {               // news of the last update that nobody has seen (it stepped aside for the motor): that first
        resume();
        if (showing() || phase_ != P_IDLE) return;
        host_.remove(STATE_FILE);
    }
    if (!host_.wifiAny()) { noWifi("No WiFi yet", "The transmitter fetches its updates over WiFi.", "Choose a network and give its password, once."); return; }
    descrUrl_ = latestUrl_; freshUrl_.clear(); freshChoosing_ = false;
    host_.wifiWanted(true);
    host_.keepAwake(); lastPoke_ = host_.ms();
    show(UpdView::BUSY, "Checking for an update"); line("Joining the WiFi"); buttons("Cancel", "");
    phase_ = P_WIFI; since_ = host_.ms();
}
// The memory is in pieces (after a Bluetooth session it is: 7 Oct 2026, four updates in a row stopped at "fetching
// screen.bin, no connection to messiter.com (-1, -0x7F00) [largest 17396]" - mbedTLS could not get its two 16 kB
// buffers for a fresh connection, and nothing but a restart puts the memory back together). So: the screen restarts
// NOW, before anything is fetched, and the check or the install goes on by itself when it is back (resume()).
void Updater::freshStart(const std::string &kind) {
    note("fresh start before the " + kind + ": the memory is in pieces (largest " + num(host_.roomForTls()) + " bytes); the screen restarts and goes on by itself");
    std::string st = stateText("fresh");
    st += "resume=" + kind + "\n" + "descr=" + descrUrl_ + "\n" + std::string("again=") + (again_ ? "1" : "0") + "\n" + std::string("choosing=") + (choosing_ ? "1" : "0") + "\n";
    host_.writeText(STATE_FILE, st);
    show(UpdView::WORKING, "Making room"); line("The screen restarts, and carries on by itself.");
    changing_ = false; phase_ = P_FRESH; restartAt_ = host_.ms() + 1500;
}
// A job failed for want of memory (the screen says so: a secure connection could not be made, -0x7F00). Before anything
// is changed, the cure is a fresh start - once; a second shortage gets the usual verdict.
bool Updater::freshForMemory(const Work &w) {
    if (!w.memory || freshDone_ || changing_) return false;
    host_.stopWork();
    restoreHave();
    const bool installing = phase_ == P_LISTS || phase_ == P_COMPARE || phase_ == P_FETCH;
    if (phase_ == P_DESCR) choosing_ = true;                  // (the chosen version's description: fetched again after the restart)
    freshStart(installing ? "install" : "check");
    return true;
}
void Updater::restoreHave() {
    if (haveText_.empty()) return;
    host_.writeText(SCREEN_HAVE, haveText_);
    haveText_.clear();
}

void Updater::askTeensy() {
    if (link_.running()) { message("Busy", "Another job holds the link to the main board.", "Try again in a minute."); return; }   // (it began since we looked: from the Mac)
    setLine(0, "Asking the transmitter");
    host_.remove(TEENSY_MARK_NOW);
    link_.clear();
    link_.get(TEENSY_MARK_REMOTE, TEENSY_MARK_NOW, true);
    linkGo(); phase_ = P_ASK;
}
void Updater::asked() {
    const bool started = linkStarted_;
    linkOurs_ = false; lastPoke_ = host_.ms();
    teensyThere_ = false; teensyFellBack_ = false; teensyFw_.clear(); teensyMarker_.clear();
    if (started && link_.finished()) {
        teensyThere_ = true; teensyFw_ = link_.peerValue("fw");
        teensyFellBack_ = link_.peerValue("state") == "rolledback";      // its last new firmware did not stay up, and it put the previous one back
        std::string m; if (host_.readText(TEENSY_MARK_NOW, m, 64)) teensyMarker_ = trim(m);
        note("transmitter: " + link_.peer());
    } else if (started && !link_.peer().empty()) {
        switch (link_.refusal()) {
        case LE_OK: break;
        case LE_BUSY:           message("A model is connected", "Switch the model off,", "then check again."); return;
        case LE_MODEL_JUST_NOW: message("A model was connected", "less than a minute ago.", "Wait a minute, then check again."); return;
        case LE_MOTOR_ON:       message("The motor is on", "Switch the motor off,", "then check again."); return;
        case LE_SAFETY_OFF:     message("The safety is off", "Put the safety on,", "then check again."); return;
        default:                message("The transmitter is busy", "Finish what is on its screen,", "then check again."); return;
        }
        std::string r = link_.result(); if (startsWith(r, "FAILED at ")) r = r.substr(10);
        message("The transmitter did not answer", sentence(r)); return;
    } else if (notNow()) return;
    else note(host_.teensySeen() ? "the main board does not answer the link (its firmware may be older than this feature)" : "no main board is connected");
    decide();
}
void Updater::decide() {
    // again_: "Install again" (Malcolm, 2-10-2026: "a reinstall option, so that we can install the same update more than
    // once for our tests") - every part the release has goes in, even when it is the same. The files are still compared
    // one by one, and only those that differ are sent; firmware that has passed its trial here starts without one (B18).
    needTeensyFw_ = teensyThere_ && rel_.teensy.present && (again_ || teensyFw_ != rel_.teensy.version);
    needTeensyFiles_ = teensyThere_ && rel_.teensyFiles.present && (again_ || teensyMarker_ != hex8(rel_.teensyFiles.crc));
    needScreenFw_ = rel_.screen.present && (again_ || host_.screenVersion() != rel_.screen.version);
    std::string mark; host_.readText(SCREEN_MARK, mark, 64);
    needScreenFiles_ = rel_.screenFiles.present && (again_ || trim(mark) != hex8(rel_.screenFiles.crc));
    stRelease_ = rel_.name; stTeensy_ = teensyFw_; stTeensyThere_ = teensyThere_; stTeensyChanged_ = false;
    stFrom_ = host_.screenVersion(); stTo_ = needScreenFw_ ? rel_.screen.version : host_.screenVersion(); stScreenFw_ = false; stFiles_ = 0; stKept_ = 0;
    stSettings_.clear(); stWarn_.clear(); mustSee_ = false;
    if (!needTeensyFw_ && !needTeensyFiles_ && !needScreenFw_ && !needScreenFiles_) {
        freshKind_.clear();
        note(choosing_ ? "that version is the one installed (" + rel_.name + ")" : "up to date (release " + rel_.name + ")");
        show(UpdView::NOTE, choosing_ ? "This version is installed" : "Up to date"); versionRows();
        if (!teensyThere_) line(host_.teensySeen() ? "The main board does not answer." : "No main board is connected.");
        // Going back must be as easy as going forward: the few releases before this one can be put back.
        noteWifi_ = false; noteVersions_ = true;
        buttons("OK", choosing_ ? "Versions" : "Earlier versions"); phase_ = P_NOTE;
        view_.button3 = "Install again"; changed();
        return;
    }
    std::string what;
    show(UpdView::OFFER, again_ ? "Install this release again?" : choosing_ ? "Install this version?" : "Update available");
    if (choosing_) line(rel_.name + (rel_.date.empty() ? "" : ", " + rel_.date));
    if (needTeensyFw_) { row("Transmitter", teensyFw_, rel_.teensy.version); what += " main-board-firmware"; }
    if (needScreenFw_) { row("Screen", host_.screenVersion(), rel_.screen.version); what += " screen-firmware"; }
    if (needTeensyFiles_) { row("Help files", "", "new"); what += " help-files"; }
    if (needScreenFiles_) { row("Screen files", "", "new"); what += " screen-files"; }
    if (!rel_.notes.empty()) line(rel_.notes);
    if (needTeensyFw_ && teensyFellBack_) line("The main board undid its last update by itself.");
    if (!teensyThere_) line(host_.teensySeen() ? "The main board does not answer: only the screen is updated." : "No main board is connected: only the screen is updated.");
    buttons("Install now", choosing_ ? "Back" : "Later");
    if (!choosing_) { view_.button3 = "Earlier versions"; changed(); }
    note(std::string(choosing_ ? "chosen" : "update available") + ", release " + rel_.name + ":" + what);
    phase_ = P_OFFER;
    if (freshKind_ == "install") { freshKind_.clear(); note("fresh start: the install goes on by itself"); install(); }
}

// ------------------------------------------------------------------ going back: the few releases before this one
void Updater::fetchAsked(const std::string &url, size_t maxBytes) {
    textUrl_ = url; textTries_ = 1; waiting_ = false; textMax_ = maxBytes;
    host_.fetchText(url, maxBytes); since_ = host_.ms();
}
// (P_LATEST, P_RECENT, P_DESCR) One answer that fails is not the end: a WiFi just joined often loses its first try.
bool Updater::textArrived() {
    const uint32_t now = host_.ms();
    if (waiting_) {
        if (now - since_ < 2000) return false;
        waiting_ = false; host_.fetchText(textUrl_, textMax_); since_ = now;
        return false;
    }
    if (host_.busy()) { if (now - since_ > 60000) { host_.stopWork(); message("messiter.com did not answer", "Check the WiFi, then try again."); } return false; }
    const Work &w = host_.done();
    if (w.ok) return true;
    note("asking messiter.com: " + w.error + (textTries_ < 3 ? " (it is asked again)" : ""));
    if (flyingNow() != UpdateHost::FLY_NO) { notNow(); return false; }
    if ((phase_ == P_LATEST || phase_ == P_DESCR) && freshForMemory(w)) return false;
    if (textTries_ >= 3) { message("messiter.com did not answer", sentence(w.error)); return false; }
    textTries_++; waiting_ = true; since_ = now;
    return false;
}

void Updater::versions() {
    if (notNow()) return;
    if (host_.busy()) { message("Busy", "Another job is still running.", "Try again in a minute."); return; }
    show(UpdView::BUSY, "Versions"); line("Asking messiter.com"); buttons("Cancel", "");
    if (!link_.running()) { host_.keepAwake(); lastPoke_ = host_.ms(); }
    fetchAsked(recentUrl_);
    phase_ = P_RECENT;
}
void Updater::gotRecent() {
    const Work &w = host_.done(); std::string why;
    if (!parseRecent(w.text, recent_, why)) { message("The answer was not understood", sentence(why)); return; }
    while (recent_.size() > 4) recent_.pop_back();
    if (recent_.empty()) { message("No other versions", "messiter.com offers none to go back to."); return; }
    show(UpdView::CHOOSE, "Choose a version");
    for (size_t i = 0; i < recent_.size(); ++i) {
        UpdChoice c; c.name = recent_[i].name; c.note = recent_[i].date;
        c.current = recent_[i].screen == host_.screenVersion() && (!teensyThere_ || recent_[i].teensy == teensyFw_);
        view_.choices.push_back(c);
    }
    buttons("OK", "");
    changed();
    note("versions on offer: " + num((uint32_t) recent_.size()));
    phase_ = P_PICK;
}
void Updater::pick(size_t i) {
    if (i >= recent_.size()) return;
    if (host_.busy()) return;
    note("chosen: " + recent_[i].name);
    show(UpdView::BUSY, recent_[i].name); line("Asking messiter.com"); buttons("Cancel", "");
    const size_t cut = latestUrl_.rfind('/');
    descrUrl_ = latestUrl_.substr(0, cut + 1) + recent_[i].path;
    fetchAsked(descrUrl_);
    phase_ = P_DESCR;
}
void Updater::gotDescription() {
    const Work &w = host_.done(); std::string why;
    if (!parseRelease(w.text, rel_, why)) { message("The answer was not understood", sentence(why)); return; }
    choosing_ = true;
    decide();
}

// ------------------------------------------------------------------ install: fetch everything first
void Updater::install() {
    if (notNow()) return;
    if (link_.running() || host_.busy()) { message("Busy", "Another job is still running.", "Try again in a minute."); return; }
    if (freshNeeded()) { freshStart("install"); return; }
    note("install " + rel_.name);
    changing_ = false; placed_ = 0;
    saveState("fetch");
    show(UpdView::WORKING, "Fetching the update"); line("Reading the lists"); buttons("Cancel", ""); bar(0, 1);
    host_.keepAwake(); lastPoke_ = host_.ms();
    teensyList_.clear(); screenList_.clear(); known_.clear(); screenListText_.clear(); listStep_ = 0; tries_ = 0; waiting_ = false;
    if (needScreenFiles_) {
        // What the last complete install put on the card, file by file. A file it names, of the size it names,
        // is taken as right without being read (40 MB read from the card take most of a minute). The memory is
        // taken OFF the card now and written again only when this install has put everything in place: after a
        // failure, a cut, or a file put on the card by hand (POST /put), everything is read and checked.
        std::string why;
        haveText_.clear();
        if (host_.readText(SCREEN_HAVE, haveText_, 300000) && !parseList(haveText_, false, known_, why)) { known_.clear(); haveText_.clear(); }
        host_.remove(SCREEN_HAVE);                            // (1.11.32: and put back by restoreHave if the fetching fails, so the next try compares quickly)
    }
    phase_ = P_LISTS; nextList();
}
void Updater::nextList() {
    for (; listStep_ < 2; ++listStep_) {
        if (!(listStep_ == 0 ? needTeensyFiles_ : needScreenFiles_)) continue;
        const UpdPart &p = listStep_ == 0 ? rel_.teensyFiles : rel_.screenFiles;
        host_.fetchText(url(p.file), 300000); since_ = host_.ms();
        return;
    }
    buildItems();
}
void Updater::gotList() {
    const Work &w = host_.done();
    const UpdPart &p = listStep_ == 0 ? rel_.teensyFiles : rel_.screenFiles;
    const char *stage = "fetching the list of files";
    if (!w.ok) {
        note(std::string(stage) + ": " + w.error);
        if (host_.flying() != UpdateHost::FLY_NO) { fail(stage, flyingWords(host_.flying())); return; }
        if (freshForMemory(w)) return;
        if (++tries_ >= 5) { fail(stage, w.error); return; }
        waiting_ = true; since_ = host_.ms();
        return;
    }
    tries_ = 0;
    if (w.size != p.size || w.crc != p.crc) { fail(stage, "the list is not the one the release names"); return; }
    std::string why;
    if (!parseList(w.text, listStep_ == 0, listStep_ == 0 ? teensyList_ : screenList_, why)) { fail(stage, why); return; }
    if (listStep_ == 1) screenListText_ = w.text;
    listStep_++; nextList();
}
void Updater::buildItems() {
    items_.clear();
    Item it; it.have = false; it.fetched = false; it.known = false; it.twin = 0;
    if (needTeensyFw_) { it.kind = 0; it.path = TEENSY_PACKAGE; it.size = rel_.teensy.size; it.crc = rel_.teensy.crc; items_.push_back(it); }
    for (size_t i = 0; i < teensyList_.size(); ++i) {
        const UpdEntry &e = teensyList_[i];
        it.kind = 1; it.path = std::string(TEENSY_COPIES) + e.path; it.size = e.size; it.crc = e.crc; items_.push_back(it);
    }
    if (needScreenFw_) { it.kind = 2; it.path = SCREEN_IMAGE; it.size = rel_.screen.size; it.crc = rel_.screen.crc; items_.push_back(it); }
    for (size_t i = 0; i < screenList_.size(); ++i) {
        const UpdEntry &e = screenList_[i];
        it.kind = 3; it.path = e.path; it.size = e.size; it.crc = e.crc; it.twin = 0;
        // Two files with the same content (two sounds that are the same sound) share a name on the website, but not
        // on our card: a staged file is MOVED to where it belongs, and the twin would find it gone.
        for (size_t k = 0; k < items_.size(); ++k) if (items_[k].kind == 3 && items_[k].crc == e.crc && items_[k].size == e.size) { it.twin = (uint16_t) (i + 1); break; }
        it.known = false;
        for (size_t k = 0; k < known_.size(); ++k) if (known_[k].path == e.path) { it.known = known_[k].size == e.size && known_[k].crc == e.crc; break; }
        items_.push_back(it);
    }
    std::vector<UpdEntry>().swap(known_); std::vector<UpdEntry>().swap(teensyList_); std::vector<UpdEntry>().swap(screenList_);   // (their memory back: items_ has what is needed)
    at_ = 0; sub_ = 0; waiting_ = false;
    setLine(0, "Checking what is already here");
    bar(0, (uint32_t) items_.size());
    phase_ = P_COMPARE;
}
// What is already on the card, and right, is not fetched again: first where the file belongs, then where an
// earlier attempt may have left it (a first fill of 40 MB that lost its WiFi carries on where it stopped).
void Updater::compareNext() {
    int budget = 6;                                           // card look-ups per call: the display must not stall
    while (at_ < items_.size()) {
        Item &it = items_[at_];
        if (sub_ == 1 && it.kind != 3) { at_++; sub_ = 0; continue; }      // (staged where it belongs: one look is enough)
        const std::string p = sub_ == 0 ? it.path : stagedOf(it);
        if (budget-- <= 0) return;
        if (sub_ == 0 && it.known) {                          // the last install put it there: its size is proof enough
            it.known = false;
            if (host_.sizeOf(p) == (int32_t) it.size) { it.have = true; at_++; bar((uint32_t) at_, (uint32_t) items_.size()); continue; }
        }
        if (!host_.exists(p)) { if (sub_ == 0) sub_ = 1; else { at_++; sub_ = 0; } continue; }
        host_.checkFile(p); waiting_ = true; since_ = host_.ms();
        return;
    }
    bar((uint32_t) items_.size(), (uint32_t) items_.size());
    startFetch();
}
void Updater::compared() {
    const Work &w = host_.done(); Item &it = items_[at_];
    const bool same = w.ok && w.size == it.size && w.crc == it.crc;
    waiting_ = false;
    if (sub_ == 0) { if (same) { it.have = true; at_++; } else sub_ = 1; }
    else { if (same) it.fetched = true; at_++; sub_ = 0; }
    bar((uint32_t) at_, (uint32_t) items_.size());
}
void Updater::startFetch() {
    fetchTotal_ = 0; fetchCount_ = 0;
    for (size_t i = 0; i < items_.size(); ++i) if (!items_[i].have && !items_[i].fetched) { fetchTotal_ += items_[i].size; fetchCount_++; }
    note(num((uint32_t) items_.size()) + " files in the update, " + num((uint32_t) fetchCount_) + " to fetch (" + sizeText(fetchTotal_) + ")");
    if (fetchCount_ && host_.freeKb() < fetchTotal_ / 1024 + 4096) { fail("making room", "the screen's card is full: " + sizeText(fetchTotal_) + " are needed"); return; }
    fetchDone_ = 0; fetchIndex_ = 0; at_ = 0; tries_ = 0; waiting_ = false;
    bar(0, fetchTotal_ ? fetchTotal_ : 1);
    phase_ = P_FETCH; fetchNext();
}
void Updater::fetchNext() {
    while (at_ < items_.size() && (items_[at_].have || items_[at_].fetched)) at_++;
    if (at_ >= items_.size()) { afterFetch(); return; }
    Item &it = items_[at_];
    setLine(0, "Fetching " + num((uint32_t) fetchIndex_ + 1) + " of " + num((uint32_t) fetchCount_));
    host_.fetchFile(urlOf(it), stagedOf(it), it.size, it.crc); since_ = host_.ms();
}
void Updater::fetched() {
    const Work &w = host_.done(); Item &it = items_[at_];
    if (w.ok) {
        it.fetched = true; if (it.kind != 3) it.have = true;
        fetchDone_ += it.size; fetchIndex_++; at_++; tries_ = 0;
        fetchNext(); return;
    }
    note("fetching " + it.path + ": " + w.error);
    if (host_.flying() != UpdateHost::FLY_NO) { fail("fetching " + leaf(it.path), flyingWords(host_.flying())); return; }
    if (freshForMemory(w)) return;
    if (++tries_ >= 5) { fail("fetching " + leaf(it.path), w.error); return; }
    setLine(0, "Fetching " + num((uint32_t) fetchIndex_ + 1) + " of " + num((uint32_t) fetchCount_) + " (again)");
    waiting_ = true; since_ = host_.ms();                     // a breath (and the WiFi back, if that is what went), then the same file again
}
void Updater::afterFetch() {
    buttons("", "");                                          // from here on there is no going back by Cancel
    note("everything the update needs is on the screen's card");
    if (needTeensyFw_ || needTeensyFiles_) startTeensy(); else startPlace();
}

// ------------------------------------------------------------------ install: the Teensy
void Updater::startTeensy() {
    if (host_.flying() != UpdateHost::FLY_NO) { fail("updating the transmitter", flyingWords(host_.flying())); return; }
    if (link_.running()) { fail("updating the transmitter", "another job holds the link to the main board. Try again in a minute"); return; }   // (from the Mac: nothing of ours may join it)
    changing_ = true; phase_ = P_TEENSY;
    saveState("teensy");
    show(UpdView::WORKING, "Updating the transmitter"); line("Opening the link"); view_.warning = DO_NOT; view_.hint = FLICKER; bar(0, 1);
    link_.clear();
    keepDir_.clear(); keptFiles_ = 0;
    if (needTeensyFw_) {
        // The pilot's own files, kept on OUR card first: everything in the card's own folder (models.dat holds the
        // models AND the transmitter's settings; whatever else is there is kept too, whatever it is called), and
        // every model file he has exported to /mod. If they cannot be kept, no firmware goes in.
        keepDir_ = host_.backupFolder(teensyFw_);
        link_.keepFolder("/", keepDir_, "");
        link_.mustHold("/models.dat", keepDir_ + "/models.dat");                   // the models and the settings: if the transmitter has them, we have them, or nothing goes in
        link_.keepFolder("/mod", keepDir_ + "/mod", ".MOD");
        link_.keepFolder("/log", LOGS_KEPT, ".LOG", 4u * 1024u * 1024u, true);     // the logs: only those we do not hold yet, or that have grown
    }
    for (size_t i = 0; i < items_.size(); ++i) if (items_[i].kind == 1) link_.put(items_[i].path, remoteOf(items_[i]), 0, true);
    if (needTeensyFiles_) {
        if (!host_.writeText(TEENSY_MARK_LOCAL, hex8(rel_.teensyFiles.crc) + "\n")) { changing_ = false; link_.clear(); fail("updating the transmitter", "the screen's card would not take a file"); return; }
        link_.put(TEENSY_MARK_LOCAL, TEENSY_MARK_REMOTE, 0, true);           // last of the files: it says the set is complete
    }
    if (needTeensyFw_) { link_.put(TEENSY_PACKAGE, TEENSY_PACKAGE_REMOTE, 0, true); link_.install(TEENSY_PACKAGE_REMOTE, rel_.teensy.version); }
    stage_.clear(); stageSince_ = host_.ms();
    linkGo();
}
void Updater::teensyShow() {
    const std::string s = link_.stage();
    const uint32_t now = host_.ms();
    if (s != stage_) { stage_ = s; stageSince_ = now; }
    std::string text = capital(s);
    if (s == "letting the new firmware run") {                // its trial: say how long
        const uint32_t gone = now - stageSince_, left = gone >= TRIAL_WAIT_MS ? 0 : (TRIAL_WAIT_MS - gone + 999) / 1000;
        text = "New firmware on trial: " + num(left) + " s";
    } else if (now - stageSince_ >= 3000) {
        // A step that takes a while shows the seconds going by, so that nobody takes it for a hang (Malcolm, 2-10-2026:
        // "it paused for a very long time and I thought it had hung").
        text += "  (" + num((now - stageSince_) / 1000) + " s)";
    }
    setLine(0, text);
    const uint32_t steps = (uint32_t) link_.stepCount(), step = (uint32_t) link_.stepIndex();
    uint32_t part = 0;
    if (link_.fileSize()) part = (uint32_t) ((uint64_t) 100 * (link_.fileDone() > link_.fileSize() ? link_.fileSize() : link_.fileDone()) / link_.fileSize());
    bar(step * 100 + part, steps ? steps * 100 : 1);
}
void Updater::teensyDone() {
    const bool ok = linkStarted_ && link_.finished();
    linkOurs_ = false; lastPoke_ = host_.ms();
    {                                                         // the link's own story, into the record in one go (one write to the card, not sixty)
        const std::vector<std::string> &story = link_.log(); std::string all;
        for (size_t i = 0; i < story.size(); ++i) { log_.push_back("   " + story[i]); all += "   " + story[i] + "\n"; }
        while (log_.size() > 300) log_.erase(log_.begin());
        if (!all.empty()) host_.appendText(LOG_FILE, all);
    }
    if (!ok && linkStarted_ && !keepDir_.empty() && link_.copiesDone()) {       // the copy of the pilot's files is whole, whatever became of the install
        host_.backupDone(keepDir_, "Kept before release " + rel_.name + " was to go in (it did not: " + link_.result() + ").\nThe main board ran " + teensyFw_ + ".\nHere: models.dat (the models and the transmitter's settings) and the model files of /mod.\nThe logs are in " + LOGS_KEPT + ".\n");
    }
    if (!ok) {
        std::string r = linkStarted_ ? link_.result() : std::string(host_.flying() != UpdateHost::FLY_NO ? flyingWords(host_.flying()) : "the link could not be started");
        if (startsWith(r, "FAILED at ")) r = r.substr(10);
        { const size_t colon = r.find(": "); if (link_.settingsRead() == "different" && colon != std::string::npos) r = r.substr(colon + 2); }   // (the reason is the whole story there)
        mustSee_ = r.find("DO NOT FLY") != std::string::npos;      // new firmware that reads the settings differently is RUNNING: the pilot must read this, whatever he is doing
        // It stopped while the pilot's files were being copied (or before): nothing had been sent to the Teensy yet.
        const std::string at = link_.stage();
        if (!linkStarted_ || startsWith(at, "fetching ") || startsWith(at, "looking into ") || startsWith(at, "opening the link")) changing_ = false;
        fail("updating the transmitter", r);
        return;
    }
    stTeensyChanged_ = true;
    stWarn_ = link_.warnings();
    if (needTeensyFw_) stSettings_ = link_.settingsRead() == "same" ? "same" : "unknown";
    if (!keepDir_.empty()) {
        keptFiles_ = link_.kept() + link_.held();
        host_.backupDone(keepDir_, "Kept before release " + rel_.name + " went in.\nThe main board ran " + teensyFw_ + ".\nHere: models.dat (the models and the transmitter's settings) and the model files of /mod.\nThe logs are in " + LOGS_KEPT + ": " +
                                   num((uint32_t) link_.held()) + " were held already, the others were fetched now.\n" + num((uint32_t) keptFiles_) + " files in all.\n");
        note(num((uint32_t) keptFiles_) + " of the pilot's files kept: models and settings in " + keepDir_ + ", logs in " + LOGS_KEPT + " (" + num((uint32_t) link_.held()) + " of them held already)");
        stKept_ = (int) keptFiles_;
    }
    if (needTeensyFw_) { teensyFw_ = link_.peerValue("fw"); stTeensy_ = teensyFw_; }
    startPlace();
}

// ------------------------------------------------------------------ install: the screen
void Updater::startPlace() {
    if (!needScreenFiles_) { startFlash(); return; }
    if (host_.flying() != UpdateHost::FLY_NO) { fail("updating the screen", flyingWords(host_.flying())); return; }
    changing_ = true; phase_ = P_PLACE;
    saveState("place");
    show(UpdView::WORKING, "Updating the screen"); line("Putting the new files in place"); view_.warning = DO_NOT; view_.hint = FLICKER;
    at_ = 0; placed_ = 0;
    bar(0, (uint32_t) items_.size());
}
void Updater::placeSome() {
    int budget = 3;
    if (host_.flying() != UpdateHost::FLY_NO) { fail("placing the files", flyingWords(host_.flying())); return; }
    while (at_ < items_.size() && budget > 0) {
        Item &it = items_[at_];
        if (it.kind == 3 && !it.have) {
            if (!it.fetched || !host_.rename(stagedOf(it), it.path)) { fail("placing " + leaf(it.path), "the screen's card would not take it"); return; }
            it.have = true; placed_++; budget--;
        }
        at_++;
    }
    bar((uint32_t) at_, (uint32_t) items_.size());
    if (at_ < items_.size()) return;
    if (!host_.writeText(SCREEN_MARK, hex8(rel_.screenFiles.crc) + "\n") || !host_.writeText(SCREEN_HAVE, screenListText_)) { fail("placing the files", "the screen's card would not take a file"); return; }
    haveText_.clear();                                        // (the card's memory is the new list now)
    stFiles_ = (int) placed_;
    note(num((uint32_t) placed_) + " of the screen's files replaced");
    startFlash();
}
void Updater::startFlash() {
    if (!needScreenFw_) { afterAll(); return; }
    if (host_.flying() != UpdateHost::FLY_NO) { fail("writing the screen's firmware", flyingWords(host_.flying())); return; }
    changing_ = true; phase_ = P_FLASH;
    saveState("flash");
    show(UpdView::WORKING, "Updating the screen"); line("Writing the screen's firmware"); view_.warning = DO_NOT; view_.hint = FLICKER; bar(0, rel_.screen.size);
    host_.flashScreen(SCREEN_IMAGE, rel_.screen.size, rel_.screen.crc); since_ = host_.ms();
}
void Updater::afterAll() {
    if (stScreenFw_ || stFiles_ > 0) {                        // new firmware, or new pages and fonts: the screen starts afresh
        saveState("restart");
        changing_ = true; phase_ = P_RESTART;
        show(UpdView::WORKING, "Updating the screen"); line("Restarting the screen"); view_.warning = DO_NOT; view_.hint = FLICKER;
        note("restarting the screen");
        restartAt_ = host_.ms() + 1500;
        return;
    }
    finishGood();
}

// ------------------------------------------------------------------ after a restart
static std::string valueOf(const std::string &text, const char *key) {
    size_t at = 0; std::string l; const std::string k = std::string(key) + "=";
    while (nextLine(text, at, l)) if (startsWith(l, k.c_str())) return l.substr(k.size());
    return "";
}
void Updater::resume() {
    if (phase_ != P_IDLE) return;
    std::string text;
    if (!host_.readText(STATE_FILE, text, 4096) || text.empty()) {
        if (host_.onTrial()) {                                // pushed from the Mac: it earns its place quietly
            silent_ = true; trialStep_ = 0; since_ = trialSeen_ = host_.ms(); phase_ = P_TRIAL;
            host_.wifiWanted(true);
            note("---- screen firmware " + host_.screenVersion() + " has started for the first time: on trial");
        }
        return;
    }
    const std::string stage = valueOf(text, "stage");
    if (host_.onTrial() && stage != "restart" && stage != "flash") {
        // The firmware that runs is on trial, and it is not the update's doing (it was pushed from the Mac while news
        // of an update waited on the card, or an install was cut short): it earns its place quietly FIRST. Nobody
        // else would ever accept it, and the next restart would put the previous firmware back without a word.
        silent_ = true; trialStep_ = 0; since_ = trialSeen_ = host_.ms(); phase_ = P_TRIAL;
        host_.wifiWanted(true);
        note("---- screen firmware " + host_.screenVersion() + " has started for the first time: on trial (the news of the last update waits)");
        return;
    }
    stRelease_ = valueOf(text, "release"); stTeensy_ = valueOf(text, "teensy");
    stTeensyThere_ = valueOf(text, "teensy_there") == "1"; stTeensyChanged_ = valueOf(text, "teensy_changed") == "1";
    stFrom_ = valueOf(text, "screen_from"); stTo_ = valueOf(text, "screen_to"); stScreenFw_ = valueOf(text, "screen_fw") == "1";
    stFiles_ = atoi(valueOf(text, "files").c_str());
    stKept_ = atoi(valueOf(text, "kept").c_str());
    stSettings_ = valueOf(text, "settings"); stWarn_.clear(); mustSee_ = valueOf(text, "mustsee") == "1";
    { size_t at = 0; std::string l; while (nextLine(text, at, l)) if (startsWith(l, "warn=") && stWarn_.size() < 4) stWarn_.push_back(l.substr(5)); }
    note("---- start-up with an update in hand (" + stage + ", release " + stRelease_ + ", screen " + host_.screenVersion() + ")");

    if (stage == "fresh") {                                   // the screen restarted to put its memory together: the check, or the install, goes on by itself
        host_.remove(STATE_FILE);                             // (first: whatever happens next, no second restart)
        freshDone_ = true; freshKind_ = valueOf(text, "resume"); freshUrl_ = valueOf(text, "descr");
        again_ = valueOf(text, "again") == "1"; freshChoosing_ = valueOf(text, "choosing") == "1"; choosing_ = false;
        if (freshUrl_.empty() || freshUrl_ == latestUrl_) { freshUrl_.clear(); freshChoosing_ = false; }
        descrUrl_ = freshUrl_.empty() ? latestUrl_ : freshUrl_;
        { const size_t cut = latestUrl_.rfind('/'); recentUrl_ = latestUrl_.substr(0, cut + 1) + "recent.txt"; }
        note("---- fresh start: the " + freshKind_ + " goes on by itself (largest piece of memory now " + num(host_.roomForTls()) + " bytes)");
        if (!host_.wifiAny()) { noWifi("No WiFi yet", "The transmitter fetches its updates over WiFi.", "Choose a network and give its password, once."); return; }
        host_.wifiWanted(true);
        host_.keepAwake(); lastPoke_ = host_.ms();
        show(UpdView::BUSY, freshKind_ == "install" ? "Installing the update" : "Checking for an update"); line("Joining the WiFi"); buttons("Cancel", "");
        phase_ = P_WIFI; since_ = host_.ms();
        return;
    }
    if (stage == "result") {                                  // a verdict nobody has acknowledged: show it again
        resultGood_ = valueOf(text, "good") == "1";
        show(resultGood_ ? UpdView::GOOD : UpdView::BAD, valueOf(text, "title"));
        size_t at = 0; std::string l;
        while (nextLine(text, at, l)) {
            if (startsWith(l, "line=")) line(l.substr(5));
            else if (startsWith(l, "row=")) {
                const std::string r = l.substr(4); const size_t a = r.find('|'), b = a == std::string::npos ? a : r.find('|', a + 1);
                if (b != std::string::npos) row(r.substr(0, a), r.substr(a + 1, b - a - 1), r.substr(b + 1));
            }
        }
        buttons("OK", ""); phase_ = P_RESULT;
        return;
    }
    std::vector<std::string> lines;
    if (stage == "rejected") {
        lines.push_back(sentence(valueOf(text, "why")));
        lines.push_back("The previous screen firmware (" + host_.screenVersion() + ") is back.");
        if (stTeensyChanged_) lines.push_back("The main board was updated.");
        result(false, "Update failed", lines);
        return;
    }
    const bool flashed = stScreenFw_ || (stage == "flash" && stTo_ != stFrom_ && host_.screenVersion() == stTo_);
    if (stage == "restart" || (stage == "flash" && flashed)) {
        stScreenFw_ = flashed;
        if (flashed && host_.screenVersion() != stTo_) {
            lines.push_back("The screen's new firmware (" + stTo_ + ") did not start.");
            lines.push_back("The previous one (" + host_.screenVersion() + ") is back.");
            if (stTeensyChanged_) lines.push_back("The main board was updated.");
            result(false, "Update failed", lines);
            return;
        }
        if (host_.onTrial()) {
            silent_ = false; trialStep_ = 0; since_ = trialSeen_ = host_.ms(); phase_ = P_TRIAL; changing_ = true;
            host_.wifiWanted(true);
            show(UpdView::WORKING, "Finishing the update"); line("Checking the screen's new firmware"); view_.warning = DO_NOT; view_.hint = FLICKER;
            return;
        }
        finishGood();
        return;
    }
    // A power cut, or the power button, in the middle of it.
    const std::string what = stage == "teensy" ? "updating the main board" : stage == "place" ? "putting the screen's files in place" : stage == "flash" ? "writing the screen's firmware" : "fetching the update";
    lines.push_back("The last update was interrupted while " + what + ".");
    lines.push_back(stage == "fetch" ? "Nothing was changed." : "Check for update again to finish.");
    result(false, "Update not finished", lines);
}
void Updater::rejectWith(const std::string &why) {
    note("REJECTED: " + why);
    host_.writeText(STATE_FILE, stateText("rejected") + "why=" + why + "\n");
    if (host_.reject()) { phase_ = P_IDLE; changing_ = false; return; }      // restarting into the previous firmware, which reports
    host_.accept();
    std::vector<std::string> lines;
    lines.push_back(sentence(why));
    lines.push_back("There is no previous screen firmware to go back to.");
    silent_ = false;
    result(false, "Update failed", lines);
}
// The screen's new firmware earns its place: it must talk to the main board (if there was one to talk to)
// and join the WiFi again, which is what the next update will need. Until then a restart of any kind
// brings the previous firmware back.
void Updater::trialPoll() {
    const uint32_t now = host_.ms();
    if (host_.armed()) { since_ += now - trialSeen_; trialSeen_ = now; return; }      // the motor is on: the trial waits (no WiFi then, and nobody restarts a screen in flight)
    trialSeen_ = now;
    switch (trialStep_) {
    case 0:
        if (now - since_ < 8000) return;                      // after a power cut the main board is starting up too
        if (!silent_ && stTeensyThere_) {
            if (link_.running()) return;                      // a job from the Mac holds the link: ours waits its turn
            link_.clear(); link_.hello(); linkGo(); trialStep_ = 1;
        } else trialStep_ = 2;
        return;
    case 1:
        if (linkBusy()) return;
        if (!linkStarted_) { linkOurs_ = false; trialStep_ = 0; return; }     // it never began (the motor went on in that very pass): that is not silence. Again.
        {
            const bool answered = linkStarted_ && (link_.finished() || !link_.peer().empty());
            linkOurs_ = false; lastPoke_ = now;
            if (!answered) { rejectWith("the screen's new firmware could not talk to the main board"); return; }
            if (!link_.peerValue("fw").empty()) stTeensy_ = link_.peerValue("fw");
        }
        trialStep_ = 2;
        return;
    default:
        if (host_.wifiUp()) {
            host_.accept();
            note("screen firmware " + host_.screenVersion() + " accepted");
            if (silent_) { silent_ = false; phase_ = P_IDLE; host_.wifiWanted(false); if (host_.exists(STATE_FILE)) resume(); return; }   // (news that waited on the card is shown now)
            finishGood();
        } else if (now - since_ > 75000) rejectWith("the screen's new firmware could not join the WiFi");
        return;
    }
}

// ------------------------------------------------------------------ the buttons
void Updater::cancel() {
    note("cancelled");
    host_.stopWork();
    if (linkOurs_ && linkStarted_ && link_.running()) link_.cancel("cancelled");
    linkWanted_ = false; linkOurs_ = false; lastPoke_ = host_.ms();
    host_.remove(STATE_FILE);
    if (!changing_) restoreHave();
    close();
}
void Updater::press(int button) {
    switch (phase_) {
    case P_WIFI: case P_LATEST: case P_ASK: case P_LISTS: case P_COMPARE: case P_FETCH: case P_RECENT: case P_DESCR:
        if (button == 1 && !view_.button1.empty()) cancel();
        return;
    case P_NOTE:
        if (noteWifi_ && button == 1) { note("WiFi setup"); close(); host_.wifiSetup(); return; }
        if (noteVersions_ && button == 2) { versions(); return; }
        if (noteVersions_ && button == 3 && !view_.button3.empty()) { note("install again"); again_ = true; decide(); return; }
        if (button == 1 || (noteWifi_ && button == 2)) close();
        return;
    case P_OFFER:
        if (button == 1) install();
        else if (button == 2 && choosing_) versions();        // Back: the list again
        else if (button == 2) { note("later"); close(); }
        else if (button == 3 && !view_.button3.empty()) versions();
        return;
    case P_PICK:
        if (button == 1) close();
        else if (button >= 10) pick((size_t) (button - 10));
        return;
    case P_RESULT:
        if (button == 1) { host_.remove(STATE_FILE); mustSee_ = false; close(); }
        return;
    case P_RX_WIFI: case P_RX_LATEST:
        if (button == 1 && !view_.button1.empty()) cancel();
        return;
    case P_RX_OFFER:
        if (button == 1) rxInstall();
        else if (button == 2) { note("later"); close(); }
        return;
    default:
        return;
    }
}

// ------------------------------------------------------------------ the clockwork
void Updater::poll() {
    const uint32_t now = host_.ms();
    // Someone is here. While work is going on the main board must neither blank the screen nor switch the
    // transmitter off for want of a touch (it cannot see the touches on our own buttons). A panel that only
    // waits for OK keeps it awake for three minutes, no longer: a transmitter left on must still go off.
    const bool busyPanel = view_.kind == UpdView::BUSY || view_.kind == UpdView::WORKING || phase_ == P_TRIAL;
    const bool waitingPanel = showing() && !busyPanel && now - shownAt_ < 180000;
    if ((busyPanel || waitingPanel) && !linkWanted_ && !linkOurs_ && !link_.running() && now - lastPoke_ > 20000 && flyingNow() == UpdateHost::FLY_NO) { host_.keepAwake(); lastPoke_ = now; }   // (and nothing at all is sent to a transmitter that flies)   // (never next to a job for the Teensy: linkOurs_ stays set until its ending has been dealt with)

    // A panel that waits for a finger steps aside when flying begins: the pilot needs his front page. One that came
    // up to SAY why nothing can be done ("The motor is on") stays four seconds first, or nobody would ever read it.
    if (showing() && !mustSee_ && (phase_ == P_NOTE || phase_ == P_OFFER || phase_ == P_RESULT || phase_ == P_PICK || phase_ == P_RX_OFFER) && flyingNow() != UpdateHost::FLY_NO && (!shownFlying_ || now - shownAt_ > 4000)) {
        note(std::string(flyingWords(flyingNow())) + ": the panel steps aside");       // (a verdict stays on the card and is shown again at the next start, or at the next check)
        close();
        return;
    }

    if (linkWanted_ && (int32_t) (now - linkAfter_) >= 0) {
        linkWanted_ = false;
        linkStarted_ = host_.flying() == UpdateHost::FLY_NO && link_.start();
    }

    switch (phase_) {
    case P_WIFI:
        if (host_.wifiUp()) {
            if (freshNeeded()) { freshStart("check"); return; }    // (looked at now, with the WiFi's own memory taken: a fresh start has 90 kB and more to spare)
            setLine(0, "Asking messiter.com"); fetchAsked(freshUrl_.empty() ? latestUrl_ : freshUrl_); phase_ = P_LATEST;
        }
        else if (now - since_ > 45000) noWifi("No WiFi", "None of the networks the transmitter knows could be joined.", "A phone's hotspot: open its hotspot page, then try again.");
        return;
    case P_LATEST:
        if (!textArrived()) return;
        {
            const Work &w = host_.done();
            std::string why;
            if (!parseRelease(w.text, rel_, why)) { message("The answer was not understood", sentence(why)); return; }
            note((freshChoosing_ ? "chosen release: " : "latest release: ") + rel_.name + " (" + rel_.date + ")");
            choosing_ = freshChoosing_;
        }
        askTeensy();
        return;
    case P_ASK:
        if (!linkBusy()) asked();
        return;
    case P_RECENT: case P_DESCR:
        if (!textArrived()) return;
        if (phase_ == P_RECENT) gotRecent(); else gotDescription();
        return;
    case P_LISTS:
        if (waiting_) { if (now - since_ < 3000 || (!host_.wifiUp() && now - since_ < 45000)) return; waiting_ = false; nextList(); return; }
        if (host_.busy()) { if (now - since_ > 60000) fail("fetching the list of files", "messiter.com did not answer"); return; }
        gotList();
        return;
    case P_COMPARE:
        if (waiting_) { if (host_.busy()) { if (now - since_ > 120000) fail("checking the screen's card", "a file could not be read"); return; } compared(); }
        compareNext();
        return;
    case P_FETCH:
        if (waiting_) {
            if (now - since_ < 3000 || (!host_.wifiUp() && now - since_ < 45000)) return;
            waiting_ = false; Item &it = items_[at_]; host_.fetchFile(urlOf(it), stagedOf(it), it.size, it.crc); since_ = now;
            return;
        }
        if (host_.busy()) {
            bar(fetchDone_ + host_.progress(), fetchTotal_ ? fetchTotal_ : 1);
            if (now - since_ > 600000) fail("fetching " + leaf(items_[at_].path), "it took more than ten minutes");
            return;
        }
        fetched();
        return;
    case P_TEENSY:
        if (linkBusy()) { if (!linkWanted_) teensyShow(); return; }
        teensyDone();
        return;
    case P_PLACE:
        placeSome();
        return;
    case P_FLASH:
        if (host_.busy()) { bar(host_.progress(), rel_.screen.size); if (now - since_ > 300000) fail("writing the screen's firmware", "it took more than five minutes"); return; }
        {
            const Work &w = host_.done();
            if (!w.ok) { fail("writing the screen's firmware", w.error); return; }
            stScreenFw_ = true;
            note("the screen's firmware " + rel_.screen.version + " is written");
        }
        afterAll();
        return;
    case P_RESTART: case P_FRESH:
        if (host_.flying() != UpdateHost::FLY_NO) { restartAt_ = now + 1500; return; }     // nobody restarts a screen in flight: it waits
        if ((int32_t) (now - restartAt_) >= 0) { restartAt_ = now + 600000; host_.restart(); }
        return;
    case P_TRIAL:
        trialPoll();
        return;
    case P_RX_WIFI:
        if (host_.wifiUp()) { setLine(0, "Asking messiter.com"); fetchAsked(rxManifestUrl_, 20000); phase_ = P_RX_LATEST; }
        else if (now - since_ > 45000) noWifi("No WiFi", "None of the networks the transmitter knows could be joined.", "A phone's hotspot: open its hotspot page, then try again.");
        return;
    case P_RX_LATEST:
        if (!textArrived()) return;
        rxGotLatest();
        return;
    case P_RX_RUN:
        rxPoll();
        return;
    default:
        return;
    }
}

// ------------------------------------------------------------------ the receiver's update, through the main board
// (TXV1B include/RxUpdate.h and RXV2 0.9.864: the screen compares the receiver's release number with messiter.com;
//  the main board sends the order over the radio and then goes silent while the receiver updates itself over the
//  WiFi it already knows; the receiver's new number, heard when it is back, is the proof.)
std::string rxVersionText(uint32_t code) {
    if (!code) return "";
    return num(code >> 24) + "." + num((code >> 16) & 0xFF) + "." + num(code & 0xFFFF);
}
// One string value of a JSON object: `"key"`, then a colon and the opening quote, with any spaces or line breaks
// between (the website's list is written with spaces after the colons; the first version of this expected none, and
// the first test on the transmitter said "The receivers' release list could not be read" - 30-9-2026). Returns the
// position after the value, or npos.
static size_t jsonString(const std::string &json, size_t from, size_t upTo, const char *key, std::string &value) {
    const std::string k = std::string("\"") + key + "\"";
    for (size_t at = json.find(k, from); at != std::string::npos && at < upTo; at = json.find(k, at + 1)) {
        size_t i = at + k.size();
        while (i < json.size() && (json[i] == ' ' || json[i] == '\t' || json[i] == '\n' || json[i] == '\r')) ++i;
        if (i >= json.size() || json[i] != ':') continue;
        ++i;
        while (i < json.size() && (json[i] == ' ' || json[i] == '\t' || json[i] == '\n' || json[i] == '\r')) ++i;
        if (i >= json.size() || json[i] != '"') continue;
        value.clear();
        for (++i; i < json.size() && json[i] != '"'; ++i) {
            if (json[i] == '\\' && i + 1 < json.size()) { ++i; value.push_back(json[i] == 'n' ? ' ' : json[i]); continue; }
            value.push_back(json[i]);
        }
        return i < json.size() ? i + 1 : json.size();
    }
    return std::string::npos;
}
bool parseReceiverManifest(const std::string &json, uint32_t &code, std::string &name, std::string &notes) {
    code = 0; name.clear(); notes.clear();
    // The first entry whose name is a receiver release: the list is written the latest first.
    size_t from = 0;
    for (;;) {
        std::string v;
        const size_t after = jsonString(json, from, json.size(), "name", v);
        if (after == std::string::npos) return false;
        if (v.compare(0, 5, "RXV2-") == 0) { name = v; from = after; break; }
        from = after;
    }
    const size_t open = json.rfind('{', from);
    size_t close = json.find('}', from); if (close == std::string::npos) close = json.size();
    jsonString(json, open == std::string::npos ? 0 : open, close, "notes", notes);
    unsigned a = 0, b = 0, c = 0;
    if (sscanf(name.c_str(), "RXV2-%u.%u.%u", &a, &b, &c) != 3 || a > 255 || b > 255 || c > 4095) return false;
    code = ((uint32_t) a << 24) | ((uint32_t) b << 16) | c;
    return true;
}
// "Receiver update" on the Model setup page (screen 1.4.0; the button is greyed out without a model, but an older main
// board that says nothing of itself leaves it usable, so the model is asked for here too).
void Updater::beginReceiver() {
    if (phase_ != P_IDLE) return;
    log_.clear(); choosing_ = false;
    note("---- receiver update (screen " + host_.screenVersion() + ")");
    if (rxManifestUrl_.empty()) { message("No receivers' list", "This screen knows no list of receiver releases."); return; }
    if (host_.flying() != UpdateHost::FLY_MODEL) {
        if (notNow()) return;                      // the motor is on, or the safety is off
        message("No model is connected", "Switch the model on,", "then try again.");
        return;
    }
    rxFlow_ = true; rxHave_ = 0; rxLatest_ = 0; rxLatestName_.clear(); rxNotes_.clear();
    if (link_.running() || host_.busy()) { message("Busy", "Another job is still running.", "Try again in a minute."); return; }
    if (!host_.wifiAny()) { noWifi("No WiFi yet", "The transmitter fetches its updates over WiFi.", "Choose a network and give its password, once."); return; }
    host_.wifiWanted(true);
    host_.keepAwake(); lastPoke_ = host_.ms();
    show(UpdView::BUSY, "Checking the receiver"); line("Joining the WiFi"); buttons("Cancel", "");
    phase_ = P_RX_WIFI; since_ = host_.ms();
}
void Updater::rxGotLatest() {
    const Work &w = host_.done();
    if (!parseReceiverManifest(w.text, rxLatest_, rxLatestName_, rxNotes_)) { message("The answer was not understood", "The receivers' release list could not be read."); return; }
    RxNews n; const bool heard = host_.rxNews(n) && n.release != 0;
    rxHave_ = heard ? n.release : 0;
    note("receivers: latest " + rxLatestName_ + ", this receiver " + (heard ? rxVersionText(rxHave_) : std::string("did not say")));
    if (!heard) {
        show(UpdView::NOTE, "The receiver did not say its version");
        row("Latest", "", rxVersionText(rxLatest_));
        line("It needs receiver firmware 0.9.864 or later:");
        line("update it once with the phone app.");
        buttons("OK", ""); phase_ = P_NOTE; noteWifi_ = false; noteVersions_ = false;
        return;
    }
    if (rxHave_ >= rxLatest_) {
        show(UpdView::NOTE, "Receiver up to date");
        row("Receiver", rxVersionText(rxHave_), "");
        buttons("OK", ""); phase_ = P_NOTE; noteWifi_ = false; noteVersions_ = false;
        return;
    }
    show(UpdView::OFFER, "Receiver update available");
    row("Receiver", rxVersionText(rxHave_), rxVersionText(rxLatest_));
    if (!rxNotes_.empty()) line(rxNotes_);
    line("The receiver fetches it over the WiFi it knows. The transmitter is silent meanwhile: about 2 minutes.");
    buttons("Install now", "Later");
    phase_ = P_RX_OFFER;
}
void Updater::rxInstall() {
    if (host_.flying() != UpdateHost::FLY_MODEL) {
        if (notNow()) return;
        message("No model is connected", "Switch the model on,", "then check again."); return;
    }
    const std::string have = rxVersionText(rxHave_), want = rxVersionText(rxLatest_);
    note("receiver update ordered: " + have + " -> " + want);
    host_.rxOrder((int) (rxLatest_ >> 24), (int) ((rxLatest_ >> 16) & 0xFF), (int) (rxLatest_ & 0xFFF));
    show(UpdView::WORKING, "Receiver update");
    row("Receiver", have, want);
    line("Asking the receiver");
    view_.warning = "Keep the model on, safety on"; view_.hint = "The transmitter is silent while the receiver updates itself";
    buttons("", "");
    changing_ = true; rxPhaseSeen_ = RXUP_IDLE; since_ = host_.ms(); rxNewsAt_ = since_; rxQuietTotal_ = 0;
    phase_ = P_RX_RUN;
}
static std::string mmss(uint32_t s) { return num(s / 60) + ":" + (s % 60 < 10 ? "0" : "") + num(s % 60); }
void Updater::rxPoll() {
    const uint32_t now = host_.ms();
    RxNews n;
    const bool heard = host_.rxNews(n) && (int32_t) (n.atMs - since_) >= 0;
    if (!heard || n.phase == RXUP_IDLE) {
        // The main board throws away whatever the display sends during the moment after each of its own commands
        // (GetReturnCode), and one order in a hundred lands there (the bench, 30-9-2026: "The transmitter did not
        // answer"). So the order is said again every 700 ms until the main board's line shows it has it - the
        // number wanted, or a phase - as the knock for the file link is repeated. A repeat of an order in hand is
        // ignored by the main board.
        if (now - rxNewsAt_ >= 700) { rxNewsAt_ = now; host_.rxOrder((int) (rxLatest_ >> 24), (int) ((rxLatest_ >> 16) & 0xFF), (int) (rxLatest_ & 0xFFF)); }
        if (now - since_ > 15000) rxResult(false, "The transmitter did not answer", std::vector<std::string>(1, "Its firmware may be older than B11: update the transmitter first."));
        return;
    }
    if (n.phase != rxPhaseSeen_) {
        rxPhaseSeen_ = n.phase; rxNewsAt_ = now;
        note(std::string("receiver update: ") + (n.phase == RXUP_ORDERED ? "asked" : n.phase == RXUP_QUIET ? "the transmitter is silent" : n.phase == RXUP_WAITING ? "waiting for the receiver" : n.phase == RXUP_DONE ? "done" : "failed"));
    }
    switch (n.phase) {
    case RXUP_ORDERED: setLine(0, "Asking the receiver"); break;
    case RXUP_QUIET:
        // The bar is the silence counting down (Malcolm, 30-9-2026: "there is no progress bar"): nothing else can be
        // measured while the transmitter is silent. Its length is the largest "left" seen, which is the whole silence.
        if (n.left > rxQuietTotal_) rxQuietTotal_ = n.left;
        setLine(0, "The receiver is updating itself. Transmitter silent for " + mmss(n.left) + " more");
        if (rxQuietTotal_) bar(rxQuietTotal_ - (n.left > rxQuietTotal_ ? rxQuietTotal_ : n.left), rxQuietTotal_);
        break;
    case RXUP_WAITING:
        setLine(0, "Waiting for the receiver to come back");
        if (rxQuietTotal_) bar(rxQuietTotal_, rxQuietTotal_);
        break;
    case RXUP_DONE: case RXUP_FAILED: rxVerdict(n); return;
    }
    if (now - since_ > 480000) rxResult(false, "Receiver update: no news", std::vector<std::string>(1, "Nothing was heard for eight minutes. Check the receiver with the phone app."));
}
void Updater::rxVerdict(const RxNews &n) {
    std::vector<std::string> lines;
    if (n.phase == RXUP_DONE) {
        lines.push_back("Receiver " + rxVersionText(rxLatest_) + " is running.");
        rxHave_ = rxLatest_;
        rxResult(true, "Receiver updated", lines);
        return;
    }
    switch (n.why) {
    case RXW_NO_MODEL:      lines.push_back("No model is connected."); break;
    case RXW_NOT_ALLOWED:   lines.push_back("The motor is on, or the safety is off."); break;
    case RXW_NO_ANSWER:     lines.push_back("The receiver did not answer the order."); lines.push_back("It needs firmware 0.9.864 or later: update it once with the phone app."); break;
    case RXW_ARMED:         lines.push_back("The receiver says the model is armed. Disarm it, then try again."); break;
    case RXW_NO_WIFI_KNOWN: lines.push_back("The receiver knows no WiFi network. Give it one on the phone app's WiFi page."); break;
    case RXW_NOT_BACK:      lines.push_back("The receiver did not come back within four minutes. Check it with the phone app."); break;
    case RXW_STILL_OLD:     lines.push_back("The receiver came back on the old version and gave no reason."); break;
    case RXW_RX_SAID:
        switch (n.outcome) {
        case RXO_NO_WIFI:         lines.push_back("The receiver could not join its WiFi network."); lines.push_back("At the field, give it your phone's hotspot on the app's WiFi page."); break;
        case RXO_NO_MANIFEST:     lines.push_back("The receiver could not read the release list from messiter.com."); break;
        case RXO_NOT_FOUND:       lines.push_back("The release is not in the receiver's list."); break;
        case RXO_DOWNLOAD_FAILED: lines.push_back("The download failed. Try again."); break;
        case RXO_DID_NOT_TAKE:    lines.push_back("The new firmware did not take: the receiver is back on the old one."); break;
        case RXO_NOT_QUIET:       lines.push_back("The receiver gave up: the transmitter did not go silent in time."); break;
        case RXO_PAGES_FAILED:    lines.push_back("The receiver's pages could not be written."); break;
        default:                  lines.push_back("The receiver came back on the old version."); break;
        }
        break;
    default: lines.push_back("The receiver came back on the old version."); break;
    }
    lines.push_back("Nothing was changed.");
    rxResult(false, "Receiver not updated", lines);
}
// The verdict panel of the receiver's update: its rows are the receiver's, not the transmitter's.
void Updater::rxResult(bool good, const std::string &title, const std::vector<std::string> &lines) {
    changing_ = false; resultGood_ = good; waiting_ = false;
    show(good ? UpdView::GOOD : UpdView::BAD, title);
    if (rxHave_) row("Receiver", rxVersionText(rxHave_), "");
    for (size_t i = 0; i < lines.size(); ++i) if (!lines[i].empty()) line(lines[i]);
    buttons("OK", "");
    phase_ = P_RESULT;
    std::string all = title;
    for (size_t i = 0; i < view_.rows.size(); ++i) all += " | " + view_.rows[i].what + " " + view_.rows[i].now;
    for (size_t i = 0; i < view_.lines.size(); ++i) all += " | " + view_.lines[i];
    note((good ? "DONE: " : "FAILED: ") + all);
}

}  // namespace ldrc
