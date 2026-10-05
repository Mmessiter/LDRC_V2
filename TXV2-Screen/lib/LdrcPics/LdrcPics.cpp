// The model pictures' chooser: the thinking (see LdrcPics.h).
#include "LdrcPics.h"
#include <algorithm>
#include <cctype>
#include <cstdio>

namespace ldrc {

static bool nameChar(char c) { return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '-'; }

bool picSameName(const std::string &a, const std::string &b) {
    if (a.size() != b.size()) return false;
    for (size_t i = 0; i < a.size(); ++i) if (tolower((unsigned char) a[i]) != tolower((unsigned char) b[i])) return false;
    return true;
}

bool picNameOk(const std::string &n) {
    if (n.empty() || (int) n.size() > PIC_NAME_MAX) return false;
    for (char c : n) if (!nameChar(c)) return false;
    return !picSameName(n, PIC_NONE);
}

std::string picNameFromPath(const std::string &path) {
    const size_t s = path.find_last_of("/\\");
    std::string b = s == std::string::npos ? path : path.substr(s + 1);
    const size_t d = b.find_last_of('.');
    if (d != std::string::npos) b = b.substr(0, d);
    return b;
}

// The model's name, letters and digits only, 8 at most: "Goblin 700" -> "Goblin70". A photo sent again for the same
// model takes the same name and replaces the one before (the phone says so before it sends).
std::string picNameSuggest(const std::string &model) {
    std::string base;
    for (char c : model) {
        if (nameChar(c) && c != '_' && c != '-') base.push_back(c);
        if ((int) base.size() >= PIC_NAME_MAX) break;
    }
    if (base.empty() || picSameName(base, PIC_NONE)) base = "Photo";
    return base;
}

bool picHeaderOk(const uint8_t *b, size_t n) {
    if (!b || n < 4) return false;
    return (b[0] | (b[1] << 8)) == PIC_W && (b[2] | (b[3] << 8)) == PIC_H;
}

// ------------------------------------------------------------------ where things are (800 x 480)
PicRect picTile(int slot) {
    PicRect r; const int col = slot % PIC_COLS, row = slot / PIC_COLS;
    r.x = 49 + col * 178; r.y = 72 + row * 144; r.w = PIC_THUMB_W + 8; r.h = PIC_THUMB_H + 8;
    return r;
}
PicRect picLabel(int slot) { PicRect t = picTile(slot), r; r.x = t.x; r.y = t.y + t.h + 2; r.w = t.w; r.h = 28; return r; }
PicRect picButton(int i) { PicRect r; r.x = 22 + i * 192; r.y = 402; r.w = 180; r.h = 68; return r; }
PicRect picArrow(int dir) { PicRect r; r.x = dir < 0 ? 2 : 754; r.y = 110; r.w = 44; r.h = 190; return r; }
PicRect picStatus() { PicRect r; r.x = 16; r.y = 358; r.w = 768; r.h = 38; return r; }
PicRect picQr() { PicRect r; r.x = 36; r.y = 82; r.w = 256; r.h = 256; return r; }
PicRect picInfo() { PicRect r; r.x = 318; r.y = 82; r.w = 466; r.h = 256; return r; }
PicRect picHelp() { PicRect r; r.x = 630; r.y = 7; r.w = 160; r.h = 44; return r; }

// ------------------------------------------------------------------ the chooser
void picBuildList(const std::vector<PicEntry> &fromCard, std::vector<PicEntry> &out, int maxEntries) {
    out.clear();
    PicEntry none; none.name = PIC_NONE; out.push_back(none);
    for (auto &e : fromCard) {
        if (!picNameOk(e.name)) continue;                           // a name the Teensy could not keep is not offered
        bool dup = false;
        for (auto &x : out) if (picSameName(x.name, e.name)) { dup = true; break; }   // the pilot's own comes first and wins
        if (!dup) out.push_back(e);
        if ((int) out.size() >= maxEntries) break;
    }
}

int picIndexOf(const std::vector<PicEntry> &list, const std::string &name) {
    for (size_t i = 0; i < list.size(); ++i) if (picSameName(list[i].name, name)) return (int) i;
    return 0;
}

void Pictures::reload() {
    std::vector<PicEntry> got; host_.list(got);
    picBuildList(got, list_, MAX_ENTRIES);
}

void Pictures::select(int i) {
    if (list_.empty()) { sel_ = 0; page_ = 0; return; }
    sel_ = std::max(0, std::min(i, (int) list_.size() - 1));
    page_ = sel_ / PIC_PER_PAGE;
}

void Pictures::selectName(const std::string &name, bool mine) {
    int found = -1;
    for (size_t i = 0; i < list_.size(); ++i)
        if (picSameName(list_[i].name, name) && (!mine || list_[i].mine || picSameName(name, PIC_NONE))) { found = (int) i; break; }
    if (found < 0) for (size_t i = 0; i < list_.size(); ++i) if (picSameName(list_[i].name, name)) { found = (int) i; break; }
    select(found < 0 ? 0 : found);
}

void Pictures::open(const std::string &model, const std::string &current) {
    model_ = model; current_ = picNameFromPath(current);
    touched_ = false; gaveUp_ = false; key_.clear(); answer_.clear(); error_.clear(); uploadName_.clear();
    pressed_ = 0; upPercent_ = -1;
    reload(); selectName(current_, false);
    say("", 0); mode_ = CHOOSE; ++layout_;
    touchAt_ = host_.ms(); awakeAt_ = 0;
}

void Pictures::setModel(const std::string &model) { if (mode_ != CLOSED) model_ = model; }

void Pictures::setCurrent(const std::string &path) {
    const std::string name = picNameFromPath(path);
    if (mode_ != CHOOSE || touched_ || name.empty() || picSameName(name, current_)) return;
    current_ = name; selectName(name, false);                       // what the Teensy said just after its page, until the pilot chooses
}

void Pictures::pageGone() {
    if (mode_ == CLOSED) return;
    mode_ = CLOSED; key_.clear(); pressed_ = 0; upPercent_ = -1; wifi(false); ++layout_;
}

int Pictures::entryAt(int slot) const {
    if (slot < 0 || slot >= PIC_PER_PAGE) return -1;
    const int i = page_ * PIC_PER_PAGE + slot;
    return i < (int) list_.size() ? i : -1;
}

std::string Pictures::title() const {
    if (mode_ == RECEIVE) return model_.empty() ? "Add a photo" : "Add a photo for " + model_;
    return model_.empty() ? "Choose a picture" : "Picture for " + model_;
}

std::string Pictures::buttonText(int i) const {
    switch (mode_) {
    case CHOOSE: { static const char *t[] = { "Add photo", "Delete", "Cancel", "OK" }; return i >= 0 && i < 4 ? t[i] : ""; }
    case ASK_DELETE: return i == 1 ? "No" : i == 2 ? "Delete" : "";   // "No" where "Delete" was: a second tap keeps the photo
    case RECEIVE: return i == 1 ? (!host_.wifiUp() && !host_.flying() ? "WiFi setup" : "") : i == 3 ? "OK" : "";   // (OK at the bottom right, as on every page)
    default: return "";
    }
}

bool Pictures::buttonOn(int i) const {
    if (buttonText(i).empty()) return false;
    if (mode_ == CHOOSE && i == 1) return sel_ > 0 && sel_ < (int) list_.size() && list_[sel_].mine;   // only the pilot's own
    return true;
}

bool Pictures::arrowShown(int dir) const {
    if (mode_ != CHOOSE) return false;
    return dir < 0 ? page_ > 0 : page_ + 1 < pages();
}

int Pictures::at(int x, int y) const {
    for (int i = 0; i < 4; ++i) if (buttonOn(i) && picButton(i).has(x, y, 6)) return P_BUTTON + i;
    if (helpShown() && picHelp().has(x, y, 4)) return P_HELP;
    if (mode_ == CHOOSE) {
        for (int dir = -1; dir <= 1; dir += 2) if (arrowShown(dir) && picArrow(dir).has(x, y)) return dir < 0 ? P_BACK : P_ON;
        for (int s = 0; s < PIC_PER_PAGE; ++s) if (entryAt(s) >= 0 && (picTile(s).has(x, y, 4) || picLabel(s).has(x, y))) return P_TILE + s;
    }
    return P_NONE;
}

void Pictures::touchDown(int x, int y) {
    if (mode_ == CLOSED || mode_ == ANSWERED) { pressed_ = 0; return; }
    touchAt_ = host_.ms();
    pressed_ = at(x, y);
}

void Pictures::touchUp(int x, int y) {
    const int p = pressed_; pressed_ = 0;
    if (p && at(x, y) == p) act(p);                                 // lifted on what it was put down on
}

void Pictures::answer(const std::string &name) {
    answer_ = name; mode_ = ANSWERED; answeredAt_ = sentAt_ = host_.ms();
    host_.answer(name); say("Saving...", 0); wifi(false);
}

void Pictures::enterReceive() {
    if (key_.empty()) { char b[12]; snprintf(b, sizeof b, "%06u", (unsigned) (100000u + host_.random() % 900000u)); key_ = b; }   // one key for this chooser
    mode_ = RECEIVE; receiveAt_ = host_.ms(); upPercent_ = -1; error_.clear(); wifi(true); ++layout_;
    receiveStatus();
}

void Pictures::act(int what) {
    if (what >= P_TILE && what < P_TILE + PIC_PER_PAGE) {
        const int e = entryAt(what - P_TILE);
        if (e >= 0 && mode_ == CHOOSE) { sel_ = e; touched_ = true; say("", 0); }
        return;
    }
    if (what == P_HELP) { if (helpShown()) host_.help(); return; }   // the Teensy shows its help page: ours closes, and comes back with its page
    if (what == P_BACK) { if (page_ > 0) --page_; return; }
    if (what == P_ON) { if (page_ + 1 < pages()) ++page_; return; }
    const int b = what - P_BUTTON;
    switch (mode_) {
    case CHOOSE:
        if (b == 0) enterReceive();
        else if (b == 1 && buttonOn(1)) { mode_ = ASK_DELETE; say("Delete your photo " + list_[sel_].name + "?", -1); }
        else if (b == 2) answer("");
        else if (b == 3) answer(list_[sel_].name);
        break;
    case ASK_DELETE:
        if (b == 1) { mode_ = CHOOSE; say("", 0); }
        else if (b == 2) {
            const std::string n = list_[sel_].name; const int keep = sel_;
            const bool ok = host_.removeMine(n);
            reload(); select(std::min(keep, (int) list_.size() - 1)); touched_ = true;
            mode_ = CHOOSE; say(ok ? "Deleted: " + n : "Could not delete " + n, ok ? 1 : -1);
        }
        break;
    case RECEIVE:
        if (b == 1) host_.wifiSetup();
        else if (b == 3) { mode_ = CHOOSE; say("", 0); ++layout_; }
        break;
    default: break;
    }
}

void Pictures::receiveStatus() {
    if (mode_ != RECEIVE) return;
    if (upPercent_ >= 0) say("Receiving " + uploadName_ + ": " + std::to_string(upPercent_) + " %", 0);
    else if (!error_.empty()) say(error_, -1);
    else if (host_.flying()) say("The WiFi is off while the model can fly.", -1);
    else if (!host_.wifiUp()) say("The transmitter is not on WiFi yet.", 0);
    else say("Waiting for the photo...", 0);
}

void Pictures::poll() {
    if (mode_ == CLOSED) return;
    const uint32_t now = host_.ms();
    if (mode_ == ANSWERED) {
        if (now - answeredAt_ >= GIVE_UP_MS) { mode_ = CLOSED; gaveUp_ = true; key_.clear(); ++layout_; return; }   // a Teensy before B21: its own page is underneath
        if (now - sentAt_ >= RESEND_MS) { sentAt_ = now; host_.answer(answer_); }   // (a word that lands just after a display command can be lost)
        return;
    }
    if (mode_ == RECEIVE) {
        if (upPercent_ < 0 && now - std::max(receiveAt_, touchAt_) >= RECEIVE_IDLE_MS) { mode_ = CHOOSE; say("", 0); ++layout_; return; }
        receiveStatus();
    }
    // Someone is here (the Teensy sees no touches under our page): its screen saver and power-off timer are told so.
    const bool here = mode_ == RECEIVE || upPercent_ >= 0 || now - touchAt_ < AWAKE_FOR_MS;
    if (here && (awakeAt_ == 0 || now - awakeAt_ >= AWAKE_EVERY_MS)) { awakeAt_ = now; host_.keepAwake(); }
}

// ------------------------------------------------------------------ the phone
bool Pictures::keyOk(const std::string &k) const {
    return (mode_ == CHOOSE || mode_ == RECEIVE || mode_ == ASK_DELETE) && !key_.empty() && k == key_;
}
std::string Pictures::url() const { return "http://" + shortUrl(); }
std::string Pictures::shortUrl() const { return host_.address() + "/photo?k=" + key_; }

void Pictures::uploadBegun(const std::string &name) {
    uploadName_ = name; upPercent_ = 0; error_.clear(); receiveAt_ = host_.ms();
    say("Receiving " + name + "...", 0);
}

void Pictures::uploadBytes(uint32_t n) {
    if (upPercent_ < 0) return;
    const int pct = (int) std::min<uint64_t>(100, (uint64_t) n * 100u / PIC_FILE_BYTES);
    if (pct / 5 == upPercent_ / 5) return;
    upPercent_ = pct; receiveAt_ = host_.ms();
    say("Receiving " + uploadName_ + ": " + std::to_string(pct) + " %", 0);
}

void Pictures::uploadEnded(bool ok, const std::string &name, const std::string &why) {
    upPercent_ = -1; receiveAt_ = host_.ms();
    if (mode_ == CLOSED || mode_ == ANSWERED) return;
    if (!ok) { error_ = "Photo not saved: " + why; say(error_, -1); return; }
    reload(); selectName(name, true); touched_ = true;
    if (mode_ != CHOOSE) ++layout_;
    mode_ = CHOOSE; say("Photo received: " + name + ". Press OK to use it.", 1);
}

}  // namespace ldrc
