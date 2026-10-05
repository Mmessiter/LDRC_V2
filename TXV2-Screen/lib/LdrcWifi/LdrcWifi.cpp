#include "LdrcWifi.h"
#include <stdio.h>
#include <string.h>

namespace ldrc {

// ------------------------------------------------------------------ names
// Network names are UTF-8; the screen's fonts are ISO 8859-1. What has a place there is shown as it is, the
// curly quotes of a phone's name ("Malcolm's iPhone") become straight ones, anything else a question mark.
static bool nextCode(const std::string &s, size_t &i, uint32_t &c) {
    if (i >= s.size()) return false;
    const unsigned char b = (unsigned char) s[i];
    int more = 0;
    if (b < 0x80) { c = b; } else if ((b & 0xE0) == 0xC0) { c = b & 0x1F; more = 1; } else if ((b & 0xF0) == 0xE0) { c = b & 0x0F; more = 2; } else if ((b & 0xF8) == 0xF0) { c = b & 0x07; more = 3; } else { c = b; i++; return true; }   // not UTF-8: taken as Latin-1
    if (i + (size_t) more >= s.size()) { c = b; i++; return true; }        // cut short: taken as Latin-1
    for (int k = 1; k <= more; ++k) { const unsigned char t = (unsigned char) s[i + (size_t) k]; if ((t & 0xC0) != 0x80) { c = b; i++; return true; } c = (c << 6) | (t & 0x3F); }
    i += (size_t) more + 1;
    return true;
}
static uint32_t plainQuote(uint32_t c) {
    if (c == 0x2018 || c == 0x2019 || c == 0x201B || c == 0x02BC || c == 0x60 || c == 0xB4) return '\'';
    if (c == 0x201C || c == 0x201D) return '"';
    return c;
}
std::string wifiShown(const std::string &ssid) {
    std::string out; size_t i = 0; uint32_t c;
    while (nextCode(ssid, i, c)) {
        if (c == 0x2018 || c == 0x2019 || c == 0x201B || c == 0x02BC) c = '\'';
        else if (c == 0x201C || c == 0x201D) c = '"';
        else if (c == 0x2013 || c == 0x2014) c = '-';
        out.push_back(c >= 32 && c < 256 && c != 127 ? (char) c : '?');
    }
    return out;
}
bool wifiSameName(const std::string &a, const std::string &b) {
    if (a == b) return true;
    size_t i = 0, j = 0; uint32_t x, y;
    for (;;) {
        const bool ma = nextCode(a, i, x), mb = nextCode(b, j, y);
        if (!ma || !mb) return ma == mb;
        if (plainQuote(x) != plainQuote(y)) return false;
    }
}
int wifiBars(int rssi) { return rssi >= -60 ? 4 : rssi >= -70 ? 3 : rssi >= -80 ? 2 : 1; }

int wifiBest(const std::vector<WifiKnown> &known, const std::vector<WifiNet> &seen, std::string &ssid) {
    int best = -1, bestRssi = -1000;
    for (size_t k = 0; k < known.size(); ++k)
        for (size_t s = 0; s < seen.size(); ++s) {
            if (seen[s].ssid.empty() || !wifiSameName(known[k].ssid, seen[s].ssid)) continue;
            if (seen[s].locked && known[k].pass.empty()) continue;         // it has a lock now and we hold no key
            if (seen[s].rssi > bestRssi + 5 || best < 0) { best = (int) k; bestRssi = seen[s].rssi; ssid = seen[s].ssid; }   // (5 dB: a newer one is not dropped for a hair's breadth)
        }
    return best;
}
void wifiRemember(std::vector<WifiKnown> &known, const std::string &ssid, const std::string &pass) {
    wifiForget(known, ssid);
    WifiKnown k; k.ssid = ssid; k.pass = pass;
    known.insert(known.begin(), k);
    while (known.size() > WIFI_KNOWN_MAX) known.pop_back();
}
bool wifiForget(std::vector<WifiKnown> &known, const std::string &ssid) {
    bool any = false;
    for (size_t i = 0; i < known.size();) if (wifiSameName(known[i].ssid, ssid)) { known.erase(known.begin() + (long) i); any = true; } else ++i;
    return any;
}

// ------------------------------------------------------------------ the pages: what is where
// The screen is 800 x 480. Ids: 1.. buttons, 100.. keys, 300.. rows.
enum { ID_DONE = 1, ID_LOOK, ID_SWITCH, ID_PREV, ID_NEXT, ID_BACK, ID_JOIN, ID_FORGET, ID_NEWPASS, ID_CANCEL, ID_GO, ID_HIDE, ID_NOTE1, ID_NOTE2,
       ID_FIELD = 50, ID_TITLE, ID_STATUS, ID_LINE1, ID_LINE2, ID_LINE3, ID_COUNT,
       ID_LOWER = 90, ID_UPPER, ID_SYMBOLS, ID_SPACE, ID_DELETE,
       ID_KEY = 100, ID_ROW = 300 };
static const int ROWS = 6, ROW_Y = 64, ROW_H = 58;
static const char *LAYERS[3][4] = {
    { "1234567890", "qwertyuiop", "asdfghjkl-", "zxcvbnm._@" },
    { "1234567890", "QWERTYUIOP", "ASDFGHJKL-", "ZXCVBNM._@" },
    { "!\"#$%&'()*", "+,-./:;<=>", "?@[\\]^_`{|", "}~        " } };

WifiSetup::WifiSetup(WifiHost &host)
    : host_(host), page_(PG_NONE), first_(0), looking_(false), looked_(false), lookSince_(0), lookTries_(0), layer_(0), hidden_(false), changing_(false), goingBack_(false),
      joinSince_(0), noteSince_(0), noteGood_(false), noteBad_(false), down_(false), pressed_(0), lastX_(0), lastY_(0), seenDown_(0), repeatAt_(0), repeated_(false), serial_(1), redo_(true), fresh_(false), noteMotor_(false) {}

std::string WifiSetup::pageName() const {
    static const char *names[] = { "none", "list", "known", "keys", "joining", "note" };
    return names[page_];
}
void WifiSetup::go(Page p) { page_ = p; redo_ = true; pressed_ = 0; build(); }

void WifiSetup::add(WifiItem::Kind kind, int id, int x, int y, int w, int h, const std::string &text) {
    WifiItem it; it.kind = kind; it.id = id; it.x = x; it.y = y; it.w = w; it.h = h; it.text = text; it.pressed = id != 0 && id == pressed_;
    next_.push_back(it);
}
std::string WifiSetup::statusText(bool &good) const {
    good = false;
    if (host_.armed()) return "The motor is on";
    if (!host_.radioOn()) return "WiFi is switched off";
    const std::string on = host_.joinedTo();
    if (on.empty()) return looking_ ? "Looking for networks" : "Not joined";
    good = true;
    return "Joined: " + wifiShown(on);
}

void WifiSetup::build() {
    next_.clear();
    switch (page_) {
    case PG_NONE: break;
    case PG_LIST: {
        bool good; const std::string st = statusText(good);
        add(WifiItem::TITLE, ID_TITLE, 16, 6, 200, 50, "WiFi");
        add(WifiItem::TEXT, ID_STATUS, 230, 6, 554, 50, st); last().good = good; last().strong = true;
        const bool on = host_.radioOn();
        if (!on) { add(WifiItem::TEXT, ID_LINE1, 40, 180, 720, 40, "WiFi is switched off."); add(WifiItem::TEXT, ID_LINE2, 40, 230, 720, 40, "Switch it on to see the networks in range."); }
        else if (rows_.empty()) { add(WifiItem::TEXT, ID_LINE1, 40, 200, 720, 40, looking_ || !looked_ ? "Looking for networks" : "No network found. Look again?"); }
        for (size_t i = 0; on && i < (size_t) ROWS && first_ + i < rows_.size(); ++i) {
            const Row &r = rows_[first_ + i];
            add(WifiItem::ROW, ID_ROW + (int) (first_ + i), 8, ROW_Y + (int) i * ROW_H, 784, ROW_H - 4, wifiShown(r.ssid));
            WifiItem &it = last();
            it.bars = r.inRange ? wifiBars(r.rssi) : 0; it.locked = r.locked; it.good = r.joined; it.strong = r.known; it.enabled = r.inRange || r.known;
            // "Not in range" is only said once the radio HAS looked: until then it is "Checking" (Malcolm, 29-9-2026:
            // his own network, which he was joined to, stood there as "Not in range" for the seconds the looking takes).
            it.note = r.joined ? "Joined" : r.checking ? "Checking" : !r.inRange ? "Not in range" : r.known ? "Saved" : "";
        }
        add(WifiItem::BUTTON, ID_SWITCH, 8, 420, 176, 54, on ? "WiFi off" : "WiFi on");
        if (on) { add(WifiItem::BUTTON, ID_LOOK, 192, 420, 186, 54, "Look again"); last().enabled = !looking_; }
        if (on && rows_.size() > (size_t) ROWS) {
            add(WifiItem::BUTTON, ID_PREV, 398, 420, 96, 54, "<"); last().enabled = first_ > 0;
            add(WifiItem::BUTTON, ID_NEXT, 502, 420, 96, 54, ">"); last().enabled = first_ + (size_t) ROWS < rows_.size();
        }
        add(WifiItem::BUTTON, ID_DONE, 622, 420, 170, 54, "OK"); last().strong = true;   // (OK at the bottom right, as on every page - Malcolm, 10-04)
        break;
    }
    case PG_KNOWN: {
        add(WifiItem::TITLE, ID_TITLE, 16, 6, 768, 50, wifiShown(target_.ssid));
        add(WifiItem::TEXT, ID_LINE1, 40, 130, 720, 40, target_.joined ? "The transmitter is joined to this network." : target_.inRange ? "The transmitter knows this network." : "The transmitter knows this network. It is not in range now.");
        if (target_.joined) { char b[64]; const int bars = wifiBars(host_.signal()); snprintf(b, sizeof b, "Signal: %s", bars >= 4 ? "strong" : bars == 3 ? "good" : bars == 2 ? "fair" : "weak"); add(WifiItem::TEXT, ID_LINE2, 40, 180, 720, 40, b); }
        const bool canJoin = target_.inRange && !target_.joined, canChange = target_.inRange && target_.locked;
        int x = (800 - ((canJoin ? 198 : 0) + (canChange ? 258 : 0) + 190)) / 2;          // the row of buttons, in the middle
        if (canJoin) { add(WifiItem::BUTTON, ID_JOIN, x, 290, 190, 64, "Join"); last().strong = true; x += 198; }
        if (canChange) { add(WifiItem::BUTTON, ID_NEWPASS, x, 290, 250, 64, "New password"); x += 258; }
        add(WifiItem::BUTTON, ID_FORGET, x, 290, 190, 64, "Forget");
        add(WifiItem::BUTTON, ID_BACK, 622, 420, 170, 54, "OK");
        break;
    }
    case PG_KEYS: {
        add(WifiItem::BUTTON, ID_CANCEL, 6, 6, 140, 48, "Cancel");
        add(WifiItem::TITLE, ID_TITLE, 154, 6, 360, 48, wifiShown(target_.ssid));
        add(WifiItem::BUTTON, ID_HIDE, 522, 6, 120, 48, hidden_ ? "Show" : "Hide");
        add(WifiItem::BUTTON, ID_GO, 650, 6, 144, 48, "Join"); last().strong = true; last().enabled = typed_.size() >= WIFI_PASS_MIN;
        add(WifiItem::FIELD, ID_FIELD, 6, 60, 788, 54, hidden_ ? std::string(typed_.size(), '*') : typed_);
        { char b[48]; snprintf(b, sizeof b, typed_.size() < WIFI_PASS_MIN ? "%u of at least %u" : "%u", (unsigned) typed_.size(), (unsigned) WIFI_PASS_MIN); last().note = b; }
        last().hint = "Password for " + wifiShown(target_.ssid);
        for (int r = 0; r < 4; ++r)
            for (int c = 0; c < 10; ++c) {
                const char ch = LAYERS[layer_][r][c];
                if (ch == ' ') continue;
                add(WifiItem::KEY, ID_KEY + r * 10 + c, c * 80 + 1, 120 + r * 72, 78, 70, std::string(1, ch));
            }
        add(WifiItem::KEY, ID_LOWER, 1, 408, 108, 70, "abc"); last().strong = true; last().good = layer_ == 0;
        add(WifiItem::KEY, ID_UPPER, 111, 408, 108, 70, "ABC"); last().strong = true; last().good = layer_ == 1;
        add(WifiItem::KEY, ID_SYMBOLS, 221, 408, 108, 70, "#+="); last().strong = true; last().good = layer_ == 2;
        add(WifiItem::KEY, ID_SPACE, 331, 408, 248, 70, "Space"); last().strong = true;
        add(WifiItem::KEY, ID_DELETE, 581, 408, 218, 70, "Delete"); last().strong = true; last().enabled = !typed_.empty();
        break;
    }
    case PG_JOINING:
        add(WifiItem::TITLE, ID_TITLE, 16, 6, 768, 50, "Joining " + wifiShown(target_.ssid));
        add(WifiItem::TEXT, ID_LINE1, 40, 190, 720, 40, "This takes a few seconds.");
        add(WifiItem::BUTTON, ID_CANCEL, 622, 420, 170, 54, "Cancel");
        break;
    case PG_NOTE:
        add(WifiItem::TITLE, ID_TITLE, 16, 6, 768, 50, noteTitle_); last().good = noteGood_; last().bad = noteBad_;
        if (!noteL1_.empty()) add(WifiItem::TEXT, ID_LINE1, 40, 150, 720, 40, noteL1_);
        if (!noteL2_.empty()) add(WifiItem::TEXT, ID_LINE2, 40, 200, 720, 40, noteL2_);
        if (!noteB2_.empty()) { add(WifiItem::BUTTON, ID_NOTE1, 120, 320, 270, 64, noteB1_); last().strong = true; add(WifiItem::BUTTON, ID_NOTE2, 410, 320, 270, 64, noteB2_); }
        else { add(WifiItem::BUTTON, ID_NOTE1, 265, 320, 270, 64, noteB1_); last().strong = true; }
        break;
    }
    // What is the same as before keeps its number and is not drawn again; a different set of things is a new layout.
    bool same = !redo_ && next_.size() == scene_.items.size();
    for (size_t i = 0; same && i < next_.size(); ++i) {
        const WifiItem &a = next_[i], &b = scene_.items[i];
        if (a.id != b.id || a.kind != b.kind || a.x != b.x || a.y != b.y || a.w != b.w || a.h != b.h) same = false;
    }
    for (size_t i = 0; i < next_.size(); ++i) {
        WifiItem &a = next_[i];
        if (same) {
            const WifiItem &b = scene_.items[i];
            const bool unchanged = a.text == b.text && a.note == b.note && a.hint == b.hint && a.bars == b.bars && a.locked == b.locked && a.strong == b.strong && a.pressed == b.pressed && a.enabled == b.enabled && a.good == b.good && a.bad == b.bad;
            a.serial = unchanged ? b.serial : ++serial_;
        } else a.serial = ++serial_;
    }
    if (!same) scene_.layout++;
    scene_.items.swap(next_);
    redo_ = false;
}

// ------------------------------------------------------------------ the list
void WifiSetup::look() {
    if (!host_.radioOn() || host_.armed()) { looking_ = false; return; }
    host_.scanStart(); looking_ = true; lookSince_ = host_.ms(); lookTries_ = 0;
}
void WifiSetup::list() {
    const std::string on = host_.joinedTo();
    rows_.clear();
    for (size_t s = 0; s < seen_.size(); ++s) {
        if (seen_[s].ssid.empty()) continue;
        Row r; r.ssid = seen_[s].ssid; r.rssi = seen_[s].rssi; r.locked = seen_[s].locked; r.inRange = true; r.known = false; r.checking = false;
        for (size_t k = 0; k < known_.size(); ++k) if (wifiSameName(known_[k].ssid, r.ssid)) r.known = true;
        r.joined = !on.empty() && on == r.ssid;
        bool dup = false;
        for (size_t i = 0; i < rows_.size(); ++i) if (rows_[i].ssid == r.ssid) { dup = true; if (r.rssi > rows_[i].rssi) { rows_[i].rssi = r.rssi; rows_[i].locked = r.locked; } }
        if (!dup) rows_.push_back(r);
    }
    // The network we are joined to is in range, whatever the looking found or has not found yet.
    bool have = on.empty();
    for (size_t i = 0; i < rows_.size(); ++i) if (rows_[i].joined) have = true;
    if (!have) {
        Row r; r.ssid = on; r.rssi = host_.signal(); r.inRange = true; r.joined = true; r.known = false; r.locked = false; r.checking = false;
        for (size_t k = 0; k < known_.size(); ++k) if (wifiSameName(known_[k].ssid, on)) { r.known = true; r.locked = !known_[k].pass.empty(); }
        rows_.push_back(r);
    }
    // joined first, then what we know, then the rest: each group with the strongest first
    for (size_t i = 1; i < rows_.size(); ++i)
        for (size_t j = i; j > 0; --j) {
            const Row &a = rows_[j - 1], &b = rows_[j];
            const int ra = a.joined ? 2 : a.known ? 1 : 0, rb = b.joined ? 2 : b.known ? 1 : 0;
            if (rb > ra || (rb == ra && b.rssi > a.rssi)) { const Row t = rows_[j - 1]; rows_[j - 1] = rows_[j]; rows_[j] = t; } else break;
        }
    for (size_t k = 0; k < known_.size(); ++k) {                 // what we know and cannot hear comes last: it can still be forgotten
        bool heard = false;
        for (size_t i = 0; i < rows_.size(); ++i) if (wifiSameName(rows_[i].ssid, known_[k].ssid)) heard = true;
        if (heard) continue;
        Row r; r.ssid = known_[k].ssid; r.rssi = -200; r.locked = !known_[k].pass.empty(); r.inRange = false; r.known = true; r.joined = false;
        r.checking = !looked_;                                   // the radio has not looked yet: we do not know
        rows_.push_back(r);
    }
    if (first_ >= rows_.size()) first_ = rows_.empty() ? 0 : ((rows_.size() - 1) / (size_t) ROWS) * (size_t) ROWS;
}

void WifiSetup::open() {
    if (page_ != PG_NONE) return;
    down_ = false; pressed_ = 0; first_ = 0; typed_.clear(); layer_ = 0; hidden_ = false; goingBack_ = false; looked_ = false; fresh_ = false;
    if (host_.armed()) { motorNote(); return; }
    host_.load(known_);
    seen_.clear(); list();
    look();
    go(PG_LIST);
}
void WifiSetup::close() {
    if (page_ == PG_NONE) return;
    typed_.clear(); joinPass_.clear();                             // a password does not lie about in memory
    page_ = PG_NONE; next_.clear(); scene_.items.clear(); scene_.layout++; looking_ = false; down_ = false; pressed_ = 0; fresh_ = false; noteMotor_ = false;
}
void WifiSetup::note(const std::string &title, const std::string &l1, const std::string &l2, const std::string &b1, const std::string &b2, bool good, bool bad) {
    noteTitle_ = title; noteL1_ = l1; noteL2_ = l2; noteB1_ = b1; noteB2_ = b2; noteGood_ = good; noteBad_ = bad; noteSince_ = host_.ms(); noteMotor_ = false;
    go(PG_NOTE);
}
void WifiSetup::motorNote() {
    if (host_.armedBySafety()) note("The safety is off", "Put the safety on,", "then set the WiFi up.", "OK", "", false, false);
    else note("The motor is on", "Switch the motor off,", "then set the WiFi up.", "OK", "", false, false);
    noteMotor_ = true;
}
void WifiSetup::choose(const Row &r) {
    target_ = r; changing_ = false;
    if (r.known) { go(PG_KNOWN); return; }
    if (!r.inRange) return;
    if (!r.locked) { tryJoin(r.ssid, ""); return; }
    typed_.clear(); layer_ = 0;
    go(PG_KEYS);
}
void WifiSetup::tryJoin(const std::string &ssid, const std::string &pass) {
    if (host_.armed()) { motorNote(); return; }
    // Where we are now is where we go back to if this does not work: a wrong password must not leave the
    // transmitter without its network.
    const std::string on = host_.joinedTo();
    if (!on.empty() || !goingBack_) {                              // (still on its way back from the last try: the way back stays what it was)
        before_ = on; beforePass_.clear();
        for (size_t k = 0; k < known_.size(); ++k) if (!before_.empty() && wifiSameName(known_[k].ssid, before_)) beforePass_ = known_[k].pass;
    }
    goingBack_ = false; joinPass_ = pass;
    host_.join(ssid, pass); joinSince_ = host_.ms();
    go(PG_JOINING);
}

// ------------------------------------------------------------------ touches
int WifiSetup::hit(int x, int y) const {
    for (size_t i = scene_.items.size(); i > 0; --i) {
        const WifiItem &it = scene_.items[i - 1];
        if (it.kind != WifiItem::BUTTON && it.kind != WifiItem::KEY && it.kind != WifiItem::ROW) continue;
        if (!it.enabled) continue;
        if (x >= it.x && x < it.x + it.w && y >= it.y && y < it.y + it.h) return it.id;
    }
    return 0;
}
void WifiSetup::touch(bool down, int x, int y) {
    if (page_ == PG_NONE) return;
    const uint32_t now = host_.ms();
    if (down) {
        seenDown_ = now; lastX_ = x; lastY_ = y;
        if (!down_) {
            down_ = true; repeated_ = false;
            pressed_ = hit(x, y); repeatAt_ = now + 600;
            if (pressed_) build();
        } else if (pressed_ == ID_DELETE && (int32_t) (now - repeatAt_) >= 0 && hit(x, y) == ID_DELETE) {   // held: it goes on deleting
            repeated_ = true; repeatAt_ = now + 110;
            key(ID_DELETE);
        }
        return;
    }
    if (!down_ || now - seenDown_ <= 80) return;                   // (the touch chip drops the odd sample: a release is 80 ms of nothing)
    down_ = false;
    const int id = pressed_; pressed_ = 0;
    if (!id) return;
    if (hit(lastX_, lastY_) == id && !repeated_) act(id);          // lifted where it was put down
    else build();
}
void WifiSetup::key(int id) {
    if (id == ID_DELETE) { if (!typed_.empty()) typed_.erase(typed_.size() - 1); }
    else if (id == ID_SPACE) { if (typed_.size() < WIFI_PASS_MAX) typed_.push_back(' '); }
    else if (id == ID_LOWER) layer_ = 0; else if (id == ID_UPPER) layer_ = 1; else if (id == ID_SYMBOLS) layer_ = 2;
    else if (id >= ID_KEY && id < ID_KEY + 40) {
        const char ch = LAYERS[layer_][(id - ID_KEY) / 10][(id - ID_KEY) % 10];
        if (ch != ' ' && typed_.size() < WIFI_PASS_MAX) typed_.push_back(ch);
    }
    build();
}
void WifiSetup::act(int id) {
    switch (page_) {
    case PG_LIST:
        if (id == ID_DONE) { close(); return; }
        if (id == ID_LOOK) { look(); build(); return; }
        if (id == ID_SWITCH) {
            const bool on = !host_.radioOn();
            host_.radioSwitch(on);
            seen_.clear(); looked_ = false; list();
            if (on) look(); else looking_ = false;
            redo_ = true; build(); return;
        }
        if (id == ID_PREV) { first_ = first_ >= (size_t) ROWS ? first_ - (size_t) ROWS : 0; redo_ = true; build(); return; }
        if (id == ID_NEXT) { if (first_ + (size_t) ROWS < rows_.size()) first_ += (size_t) ROWS; redo_ = true; build(); return; }
        if (id >= ID_ROW && (size_t) (id - ID_ROW) < rows_.size()) { const Row r = rows_[(size_t) (id - ID_ROW)]; choose(r); return; }
        break;
    case PG_KNOWN:
        if (id == ID_BACK) { go(PG_LIST); return; }
        if (id == ID_FORGET) {
            const bool was = target_.joined || wifiSameName(host_.joinedTo(), target_.ssid);      // (the row is a copy: the radio may have joined since)
            wifiForget(known_, target_.ssid); host_.save(known_);
            if (was) host_.leave();
            list(); go(PG_LIST); return;
        }
        if (id == ID_JOIN) {
            std::string pass;
            for (size_t k = 0; k < known_.size(); ++k) if (wifiSameName(known_[k].ssid, target_.ssid)) pass = known_[k].pass;
            tryJoin(target_.ssid, pass); return;
        }
        if (id == ID_NEWPASS) { changing_ = true; typed_.clear(); layer_ = 0; go(PG_KEYS); return; }
        break;
    case PG_KEYS:
        if (id == ID_CANCEL) { typed_.clear(); go(changing_ ? PG_KNOWN : PG_LIST); return; }
        if (id == ID_HIDE) { hidden_ = !hidden_; build(); return; }
        if (id == ID_GO) { if (typed_.size() >= WIFI_PASS_MIN) tryJoin(target_.ssid, typed_); return; }
        key(id); return;
    case PG_JOINING:
        if (id == ID_CANCEL) {
            host_.leave();
            if (!before_.empty()) { host_.join(before_, beforePass_); goingBack_ = true; }
            go(target_.locked && !typed_.empty() ? PG_KEYS : PG_LIST); return;
        }
        break;
    case PG_NOTE:
        if (noteMotor_) { close(); return; }
        if (id == ID_NOTE1 && !noteB2_.empty()) { go(target_.locked ? PG_KEYS : PG_LIST); return; }      // "Try again": the keys, with what was typed
        typed_.clear();
        list(); go(PG_LIST); return;
    default: break;
    }
    build();
}

// ------------------------------------------------------------------ the clockwork
void WifiSetup::poll() {
    if (page_ == PG_NONE) return;
    const uint32_t now = host_.ms();
    if (host_.armed()) {                                          // the pilot needs his front page, and the radio goes off
        if (page_ == PG_NOTE && noteMotor_ && now - noteSince_ < 4000) return;      // (he asked for the page: he is told why not, for four seconds)
        close(); return;
    }
    if (looking_) {
        const int st = host_.scanState();
        if (st == 1) { host_.scanResults(seen_); looking_ = false; looked_ = true; fresh_ = true; }
        else if (st < 0 && lookTries_ < 3) {                         // the radio was busy (joining, as a rule): asked again a little later, three times
            if (now - lookSince_ > 1500) { lookTries_++; host_.scanStart(); lookSince_ = now; }
        }
        else if (st < 0 || now - lookSince_ > 12000) { looking_ = false; looked_ = true; fresh_ = true; }
    }
    if (fresh_ && !down_) {                                         // never under a finger: what he lifts his finger from is what he put it on
        fresh_ = false; list();
        if (page_ == PG_KNOWN) { for (size_t i = 0; i < rows_.size(); ++i) if (wifiSameName(rows_[i].ssid, target_.ssid)) target_ = rows_[i]; redo_ = true; build(); }
        if (page_ == PG_LIST) { redo_ = true; build(); }
    }
    if (page_ == PG_JOINING) {
        const int st = host_.joinState();
        if (st == 1) {
            wifiRemember(known_, target_.ssid, joinPass_);         // to the front of what we know, with the key that worked
            host_.save(known_);
            typed_.clear(); joinPass_.clear(); goingBack_ = false;
            list();
            note("Joined", wifiShown(target_.ssid), "The transmitter will join it by itself from now on.", "OK", "", true, false);
        } else if (st < 0 || now - joinSince_ > 25000) {
            host_.leave();
            if (!before_.empty()) { host_.join(before_, beforePass_); goingBack_ = true; }      // back to where we were
            const char *why = st == -1 ? "The password was not accepted." : st == -2 ? "The network was not found. Is it still in range?" : "The network did not answer.";
            if (target_.locked && !typed_.empty()) note("Not joined", why, "", "Try again", "Back", false, true);
            else note("Not joined", why, "", "OK", "", false, true);
        }
    }
    if (page_ == PG_LIST && !down_) {                               // the line at the top follows what the radio does
        bool good; const std::string st = statusText(good);
        for (size_t i = 0; i < scene_.items.size(); ++i) if (scene_.items[i].id == ID_STATUS && (scene_.items[i].text != st || scene_.items[i].good != good)) { list(); build(); break; }
    }
}

}  // namespace ldrc
