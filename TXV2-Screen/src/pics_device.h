// The model pictures (screen 1.5.0): the chooser that covers the Teensy's "Choose image" page, its thumbnails, and
// photos sent from a phone. The thinking is lib/LdrcPics (tested on the Mac: hmi/test_pics); this is the card, the
// drawing and the web. Included by main.cpp after update_device.h.
//
// Malcolm, 2026-10-03: "Can we add a feature that allows a user to add a photograph of a model easily, and adjust it
// on arrival so that the dimensions and pixel count are ok?" ... "I put those images onto both discs, because the
// teensy was not able to give me the directory from the Nextion and the Nextion could not display quickly from the
// teensy! ... you might be able to find an altogether better way of managing the pictures."
// So: the pictures live on the screen's card only, the screen shows them as a grid of thumbnails, and the Teensy is
// told the chosen NAME ("LDRCIMG <name>"). A phone sends a photo already made 320 x 200 (hmi/web/photo.html).
#include "LdrcPics.h"

extern "C" {   // the QR encoder that is in the framework already (ESP-IDF's qrcode component: Project Nayuki's qrcodegen)
enum qrcodegen_Ecc { qrcodegen_Ecc_LOW = 0, qrcodegen_Ecc_MEDIUM, qrcodegen_Ecc_QUARTILE, qrcodegen_Ecc_HIGH };
enum qrcodegen_Mask { qrcodegen_Mask_AUTO = -1 };
bool qrcodegen_encodeText(const char *text, uint8_t tempBuffer[], uint8_t qrcode[], enum qrcodegen_Ecc ecl, int minVersion, int maxVersion, enum qrcodegen_Mask mask, bool boostEcl);
int qrcodegen_getSize(const uint8_t qrcode[]);
bool qrcodegen_getModule(const uint8_t qrcode[], int x, int y);
}

static const char PIC_MINE_DIR[] = "/images/mine";               // the pilot's own photos: never in a release, found first
static const char PIC_PAGE_FILE[] = "/hmi/web/photo.html";       // the phone's page, on the card (it comes with the release)

// ------------------------------------------------------------------ the card
static bool picEndsWith565(const std::string &n) { return n.size() > 4 && strcasecmp(n.c_str() + n.size() - 4, ".565") == 0; }
static bool picLess(const ldrc::PicEntry &a, const ldrc::PicEntry &b) { return strcasecmp(a.name.c_str(), b.name.c_str()) < 0; }
// The names only (getNextFileName opens no file: openNextFile opened every one, and the chooser waited 2/3 s for its
// list - Malcolm, 10-03). Read once, and again only after a photo has arrived or been deleted (a release that changes
// /images restarts the screen).
static void picScanNames(const char *dir, bool mine, std::vector<ldrc::PicEntry> &out) {
    File d = SD.open(dir);
    if (!d || !d.isDirectory()) return;
    for (int guard = 0; guard < 2000; ++guard) {
        boolean isDir = false;
        const String full = d.getNextFileName(&isDir);
        if (full.length() == 0) break;
        if (isDir) continue;
        std::string n = full.c_str();
        const size_t slash = n.find_last_of('/'); if (slash != std::string::npos) n = n.substr(slash + 1);
        if (picEndsWith565(n)) { ldrc::PicEntry e; e.name = n.substr(0, n.size() - 4); e.mine = mine; out.push_back(e); }
    }
    d.close();
}
static std::vector<ldrc::PicEntry> picCardList; static bool picCardListOk = false;
static std::string picFile(const std::string &name, bool mine) { return std::string(mine ? PIC_MINE_DIR : "/images") + "/" + name + ".565"; }

// ------------------------------------------------------------------ thumbnails: 160 x 100, in PSRAM, made a few rows at a time
struct PicThumb { std::string key; uint16_t *px = nullptr; uint32_t used = 0; bool bad = false; };
static std::vector<PicThumb> picThumbs;
static const size_t PIC_THUMBS_MAX = 24;                         // 24 x 32 kB: three pages' worth
static std::string picKey(const std::string &name, bool mine) { std::string k = mine ? "*" : "-"; for (char c : name) k.push_back((char) tolower((unsigned char) c)); return k; }
static PicThumb *picThumbFind(const std::string &key) { for (auto &t : picThumbs) if (t.key == key) { t.used = millis(); return &t; } return nullptr; }
struct PicJob;
static void picJobAbandon(const std::string &name);
static void picThumbDrop(const std::string &name) {
    picJobAbandon(name);                                         // (one being made of the old picture would come back stale)
    for (size_t i = 0; i < picThumbs.size();) {
        if (picThumbs[i].key == picKey(name, true) || picThumbs[i].key == picKey(name, false)) { free(picThumbs[i].px); picThumbs.erase(picThumbs.begin() + i); }
        else ++i;
    }
}
static void picThumbsFree() { for (auto &t : picThumbs) free(t.px); picThumbs.clear(); }
static void picThumbKeep(const std::string &key, uint16_t *px, bool bad) {
    while (picThumbs.size() >= PIC_THUMBS_MAX) {                  // the one not looked at for longest makes room
        size_t old = 0; for (size_t i = 1; i < picThumbs.size(); ++i) if (picThumbs[i].used < picThumbs[old].used) old = i;
        free(picThumbs[old].px); picThumbs.erase(picThumbs.begin() + old);
    }
    PicThumb t; t.key = key; t.px = px; t.bad = bad; t.used = millis(); picThumbs.push_back(t);
}
static inline uint16_t picAvg4(uint16_t a, uint16_t b, uint16_t c, uint16_t d) {
    const uint32_t r = ((a >> 11) & 31) + ((b >> 11) & 31) + ((c >> 11) & 31) + ((d >> 11) & 31);
    const uint32_t g = ((a >> 5) & 63) + ((b >> 5) & 63) + ((c >> 5) & 63) + ((d >> 5) & 63);
    const uint32_t bl = (a & 31) + (b & 31) + (c & 31) + (d & 31);
    return (uint16_t) ((((r + 2) >> 2) << 11) | (((g + 2) >> 2) << 5) | ((bl + 2) >> 2));
}
struct PicJob { bool on = false; std::string key; File f; uint16_t *px = nullptr; int w = 0, h = 0, row = 0, tw = 0, th = 0, ox = 0, oy = 0; };
static PicJob picJob;
static void picJobEnd(bool ok) {
    if (picJob.f) picJob.f.close();
    if (!ok && picJob.px) { free(picJob.px); picJob.px = nullptr; }
    picThumbKeep(picJob.key, picJob.px, !ok);
    picJob = PicJob();
}
static void picJobStart(const std::string &name, bool mine) {
    picJob = PicJob(); picJob.key = picKey(name, mine);
    picJob.f = SD.open(picFile(name, mine).c_str(), FILE_READ);
    uint16_t wh[2] = { 0, 0 };
    if (!picJob.f || picJob.f.read((uint8_t *) wh, 4) != 4 || !wh[0] || !wh[1] || wh[0] > 1024 || wh[1] > 1024) { picJob.on = true; picJobEnd(false); return; }
    picJob.px = (uint16_t *) ps_malloc(ldrc::PIC_THUMB_W * ldrc::PIC_THUMB_H * 2);
    if (!picJob.px) { picJob.on = true; picJobEnd(false); return; }
    for (int i = 0; i < ldrc::PIC_THUMB_W * ldrc::PIC_THUMB_H; ++i) picJob.px[i] = 0;
    picJob.w = wh[0]; picJob.h = wh[1];
    // The whole picture, as large as fits in 160 x 100, centred (a 320 x 200 one fills it exactly).
    if ((long) picJob.w * ldrc::PIC_THUMB_H >= (long) picJob.h * ldrc::PIC_THUMB_W) { picJob.tw = ldrc::PIC_THUMB_W; picJob.th = std::max(1, (int) ((long) picJob.h * ldrc::PIC_THUMB_W / picJob.w)); }
    else { picJob.th = ldrc::PIC_THUMB_H; picJob.tw = std::max(1, (int) ((long) picJob.w * ldrc::PIC_THUMB_H / picJob.h)); }
    picJob.ox = (ldrc::PIC_THUMB_W - picJob.tw) / 2; picJob.oy = (ldrc::PIC_THUMB_H - picJob.th) / 2;
    picJob.on = true;
}
static void picJobAbandon(const std::string &name) {
    if (!picJob.on || (picJob.key != picKey(name, true) && picJob.key != picKey(name, false))) return;
    if (picJob.f) picJob.f.close();
    free(picJob.px); picJob = PicJob();
}
static void picJobStep() {                                       // up to 12 rows of the thumbnail (24 of the picture): a few ms
    if (!picJob.on) return;
    static std::vector<uint16_t> two;
    const bool exact = picJob.w == 2 * ldrc::PIC_THUMB_W && picJob.h == 2 * ldrc::PIC_THUMB_H;
    for (int n = 0; n < 12 && picJob.row < picJob.th; ++n, ++picJob.row) {
        uint16_t *out = picJob.px + (picJob.oy + picJob.row) * ldrc::PIC_THUMB_W + picJob.ox;
        if (exact) {                                             // every 2 x 2 block, averaged
            two.resize(2 * picJob.w);
            if (picJob.f.read((uint8_t *) two.data(), 4 * picJob.w) != (size_t) (4 * picJob.w)) { picJobEnd(false); return; }
            const uint16_t *a = two.data(), *b = two.data() + picJob.w;
            for (int x = 0; x < picJob.tw; ++x) out[x] = picAvg4(a[2 * x], a[2 * x + 1], b[2 * x], b[2 * x + 1]);
        } else {                                                 // any other size: the nearest pixel
            const int sy = (int) ((long) picJob.row * picJob.h / picJob.th);
            two.resize(picJob.w);
            if (!picJob.f.seek(4 + (uint32_t) sy * picJob.w * 2) || picJob.f.read((uint8_t *) two.data(), 2 * picJob.w) != (size_t) (2 * picJob.w)) { picJobEnd(false); return; }
            for (int x = 0; x < picJob.tw; ++x) out[x] = two[(long) x * picJob.w / picJob.tw];
        }
    }
    if (picJob.row >= picJob.th) picJobEnd(true);
}

// ------------------------------------------------------------------ the chooser's host
struct ScreenPics : public ldrc::PicsHost {
    uint32_t ms() override { return millis(); }
    void list(std::vector<ldrc::PicEntry> &out) override {
        out.clear();
        if (!sdOk) return;
        if (!picCardListOk) {
            std::vector<ldrc::PicEntry> mine, rel;
            picScanNames(PIC_MINE_DIR, true, mine); picScanNames("/images", false, rel);
            std::sort(mine.begin(), mine.end(), picLess); std::sort(rel.begin(), rel.end(), picLess);
            picCardList = mine; picCardList.insert(picCardList.end(), rel.begin(), rel.end());
            picCardListOk = true;
        }
        out = picCardList;
    }
    bool removeMine(const std::string &name) override {
        if (!sdOk || !ldrc::picNameOk(name)) return false;
        picThumbDrop(name);
        const bool ok = SD.remove(picFile(name, true).c_str());
        picCardListOk = false;
        return ok;
    }
    void answer(const std::string &name) override {              // an ordinary touch-event text, as the receiver's order is
        if (teensyLink.running()) return;
        std::string b = std::string(LDRC_IMAGE_WORD) + (name.empty() ? "" : " " + name);
        flushOut(); Serial.write((const uint8_t *) b.data(), b.size());
    }
    bool wifiUp() override { return radiosLive && WiFi.status() == WL_CONNECTED; }
    int flying() override { return tx.radiosAllowed() ? 0 : std::max(1, flyingNow()); }
    std::string address() override { return WiFi.localIP().toString().c_str(); }
    uint32_t random() override { return esp_random(); }
    void wifiWanted(bool on) override {
        if (picWifi == on) return;
        picWifi = on;
        applyRadios(on ? "WiFi on for a photo" : "WiFi as the switch says");
    }
    void wifiSetup() override { wifiRequested = true; }
    void keepAwake() override { if (teensyLink.running()) return; flushOut(); Serial.write((const uint8_t *) "UKRULES", 7); }
    void help() override {                                       // the Teensy's Help button underneath, as if it had been touched
        Comp *h = find("b17");
        if (h && page.name == "ImageView" && !h->evRelease.empty() && !teensyLink.running()) runScript(h->evRelease, h->name);
    }
};
static ScreenPics picHost;
static ldrc::Pictures pictures(picHost);
static bool picPanelUp() { return topOn && topWho == 4; }

// ------------------------------------------------------------------ drawing
#define PIC_BACK OUR_PANEL                                      // (the pilot's colours: src/theme_device.h)
#define PIC_STRIP OUR_STRIP
#define PIC_INK OUR_INK
#define PIC_SOFT OUR_SOFT
static const uint16_t PIC_MINE_INK = 0x87F0, PIC_SEL = 0xFFE0;
static int picBtnFont = 6;
static void picText(int x, int y, int font, uint16_t col, const std::string &s) { gfx->startWrite(); drawGlyphs(x, y, font, col, s); gfx->endWrite(); }
static void picTextCentred(const ldrc::PicRect &r, int font, uint16_t col, const std::string &s) {
    const std::string t = topCut(s, font, r.w - 8);
    picText(r.x + (r.w - textWidth(font, t)) / 2, r.y + (r.h - fontHeight(font)) / 2 + 2, font, col, t);
}
static int picFit(const std::string &s, int w, int big, int small) { return textWidth(big, s) <= w ? big : small; }
static void picClip(const ldrc::PicRect &r) { clipX0 = std::max(0, r.x); clipY0 = std::max(0, r.y); clipX1 = std::min(W, r.x + r.w); clipY1 = std::min(H, r.y + r.h); }
static void picUnclip() { clipX0 = 0; clipY0 = 0; clipX1 = W; clipY1 = H; }

static void picDrawButton(int i) {
    const ldrc::PicRect b = ldrc::picButton(i);
    const std::string label = pictures.buttonText(i);
    gfx->fillRect(b.x, b.y, b.w, b.h, PIC_BACK);
    if (label.empty()) return;
    const bool on = pictures.buttonOn(i), down = on && pictures.pressed() == ldrc::Pictures::P_BUTTON + i;
    const uint16_t face = !on ? 0x8410 : down ? 0x9CD3 : 0xD69A, hi = shade(face, 60), lo = shade(face, -45);
    gfx->fillRect(b.x, b.y, b.w, b.h, face);
    for (int k = 0; k < 3; ++k) {
        gfx->drawFastHLine(b.x + k, b.y + k, b.w - 2 * k, down ? lo : hi); gfx->drawFastVLine(b.x + k, b.y + k, b.h - 2 * k, down ? lo : hi);
        gfx->drawFastHLine(b.x + k, b.y + b.h - 1 - k, b.w - 2 * k, down ? hi : lo); gfx->drawFastVLine(b.x + b.w - 1 - k, b.y + k, b.h - 2 * k, down ? hi : lo);
    }
    picClip(b);
    picText(b.x + (b.w - textWidth(picBtnFont, label)) / 2 + (down ? 1 : 0), b.y + (b.h - fontHeight(picBtnFont)) / 2 + (down ? 1 : 0), picBtnFont, on ? 0x0000 : 0x4A69, topCut(label, picBtnFont, b.w - 12));
    picUnclip();
}
static void picChooseFont() {                                    // one font for every button of the panel, the largest that fits them all
    static const int fonts[] = { 0, 6, 2 };
    for (int f : fonts) {
        bool fits = true;
        for (int i = 0; i < 4; ++i) { const std::string t = pictures.buttonText(i); if (!t.empty() && textWidth(f, t) > ldrc::picButton(i).w - 20) fits = false; }
        if (fits) { picBtnFont = f; return; }
    }
    picBtnFont = 2;
}
static const int PIC_HELP_X = 626;                               // the strip: the title left of it, Help right of it
static void picDrawTitle() {
    const ldrc::PicRect r = { 0, 0, PIC_HELP_X, ldrc::PIC_STRIP_H };
    gfx->fillRect(r.x, r.y, r.w, r.h - 1, PIC_STRIP);
    std::string pg;
    if ((pictures.mode() == ldrc::Pictures::CHOOSE || pictures.mode() == ldrc::Pictures::ASK_DELETE) && pictures.pages() > 1)
        pg = std::to_string(pictures.page() + 1) + " / " + std::to_string(pictures.pages());
    const int pw = pg.empty() ? 0 : textWidth(6, pg) + 24;
    const std::string t = pictures.title();
    const int room = r.w - 28 - pw, font = picFit(t, room, 0, 6);
    picClip(r);
    picText(14, (r.h - fontHeight(font)) / 2 + 2, font, PIC_INK, topCut(t, font, room));
    if (!pg.empty()) picText(r.w - pw + 6, (r.h - fontHeight(6)) / 2 + 2, 6, PIC_SOFT, pg);
    picUnclip();
}
static void picDrawHelp() {
    gfx->fillRect(PIC_HELP_X, 0, W - PIC_HELP_X, ldrc::PIC_STRIP_H - 1, PIC_STRIP);
    if (!pictures.helpShown()) return;
    const ldrc::PicRect b = ldrc::picHelp();
    const bool down = pictures.pressed() == ldrc::Pictures::P_HELP;
    const uint16_t face = down ? 0x9CD3 : 0xD69A, hi = shade(face, 60), lo = shade(face, -45);
    gfx->fillRect(b.x, b.y, b.w, b.h, face);
    for (int k = 0; k < 2; ++k) {
        gfx->drawFastHLine(b.x + k, b.y + k, b.w - 2 * k, down ? lo : hi); gfx->drawFastVLine(b.x + k, b.y + k, b.h - 2 * k, down ? lo : hi);
        gfx->drawFastHLine(b.x + k, b.y + b.h - 1 - k, b.w - 2 * k, down ? hi : lo); gfx->drawFastVLine(b.x + b.w - 1 - k, b.y + k, b.h - 2 * k, down ? hi : lo);
    }
    picClip(b); picTextCentred(b, 6, 0x0000, "Help"); picUnclip();
}
static void picDrawArrow(int dir) {
    const ldrc::PicRect r = ldrc::picArrow(dir);
    gfx->fillRect(r.x, r.y, r.w, r.h, PIC_BACK);
    if (!pictures.arrowShown(dir)) return;
    const bool down = pictures.pressed() == (dir < 0 ? ldrc::Pictures::P_BACK : ldrc::Pictures::P_ON);
    const uint16_t col = down ? PIC_SOFT : PIC_INK;
    const int cy = r.y + r.h / 2, tip = dir < 0 ? r.x + 8 : r.x + r.w - 8, base = dir < 0 ? r.x + r.w - 8 : r.x + 8;
    gfx->fillTriangle(tip, cy, base, cy - 34, base, cy + 34, col);
}
static void picDrawTile(int slot) {
    const ldrc::PicRect r = ldrc::picTile(slot), l = ldrc::picLabel(slot);
    gfx->fillRect(r.x, r.y, r.w, r.h, PIC_BACK); gfx->fillRect(l.x, l.y, l.w, l.h, PIC_BACK);
    const int e = pictures.entryAt(slot);
    if (e < 0) return;
    const ldrc::PicEntry &en = pictures.entries()[e];
    const bool chosen = e == pictures.selected(), down = pictures.pressed() == ldrc::Pictures::P_TILE + slot;
    const uint16_t edge = down ? PIC_INK : chosen ? PIC_SEL : 0x4A69;
    const int bw = chosen ? 4 : 2;
    for (int k = 0; k < bw; ++k) gfx->drawRect(r.x + k, r.y + k, r.w - 2 * k, r.h - 2 * k, edge);
    const int ix = r.x + 4, iy = r.y + 4;
    if (ldrc::picSameName(en.name, ldrc::PIC_NONE)) {
        gfx->fillRect(ix, iy, ldrc::PIC_THUMB_W, ldrc::PIC_THUMB_H, 0x0000);
        picClip(r); picTextCentred({ ix, iy, ldrc::PIC_THUMB_W, ldrc::PIC_THUMB_H }, 6, PIC_SOFT, "No picture"); picUnclip();
    } else {
        PicThumb *t = picThumbFind(picKey(en.name, en.mine));
        if (t && t->px) gfx->draw16bitRGBBitmap(ix, iy, t->px, ldrc::PIC_THUMB_W, ldrc::PIC_THUMB_H);
        else {
            gfx->fillRect(ix, iy, ldrc::PIC_THUMB_W, ldrc::PIC_THUMB_H, 0x2104);
            picClip(r); picTextCentred({ ix, iy, ldrc::PIC_THUMB_W, ldrc::PIC_THUMB_H }, 6, PIC_SOFT, t && t->bad ? "?" : "..."); picUnclip();
        }
        picClip(l);
        const uint16_t ink = chosen ? PIC_SEL : en.mine ? PIC_MINE_INK : PIC_INK;
        picTextCentred(l, picFit(en.name, l.w - 8, 6, 2), ink, en.name);
        picUnclip();
    }
}
static void picDrawStatus() {
    const ldrc::PicRect r = ldrc::picStatus();
    gfx->fillRect(r.x, r.y, r.w, r.h, PIC_BACK);
    const std::string &s = pictures.status();
    if (s.empty()) return;
    const uint16_t ink = pictures.statusTone() > 0 ? PIC_MINE_INK : pictures.statusTone() < 0 ? PIC_SEL : PIC_INK;
    picClip(r); picTextCentred(r, picFit(s, r.w - 8, 6, 2), ink, s); picUnclip();
}
static void picDrawQr() {
    const ldrc::PicRect r = ldrc::picQr();
    gfx->fillRect(r.x, r.y, r.w, r.h, PIC_BACK);
    if (!picHost.wifiUp()) {
        gfx->fillRect(r.x, r.y, r.w, r.h, 0x4208);
        picClip(r); picTextCentred(r, 0, PIC_SOFT, "No WiFi"); picUnclip();
        return;
    }
    static uint8_t qr[420], tmp[420];                             // version 10 at most: ((10*4+17)^2+7)/8+1 = 408 bytes
    const std::string url = pictures.url();
    if (!qrcodegen_encodeText(url.c_str(), tmp, qr, qrcodegen_Ecc_MEDIUM, 1, 10, qrcodegen_Mask_AUTO, true)) {
        picClip(r); picTextCentred(r, 6, PIC_SOFT, "(no code: type the address)"); picUnclip();
        return;
    }
    const int n = qrcodegen_getSize(qr), quiet = 4, total = n + 2 * quiet, s = std::max(1, r.w / total);
    const int side = total * s, ox = r.x + (r.w - side) / 2, oy = r.y + (r.h - side) / 2;
    gfx->fillRect(ox, oy, side, side, 0xFFFF);
    for (int y = 0; y < n; ++y) for (int x = 0; x < n; ++x) if (qrcodegen_getModule(qr, x, y)) gfx->fillRect(ox + (quiet + x) * s, oy + (quiet + y) * s, s, s, 0x0000);
}
static void picDrawInfo() {
    const ldrc::PicRect r = ldrc::picInfo();
    gfx->fillRect(r.x, r.y, r.w, r.h, PIC_BACK);
    picClip(r);
    int y = r.y + 6;
    auto line = [&](const std::string &s, int big, int small, uint16_t col, int gap) {
        const int f = picFit(s, r.w - 8, big, small);
        picText(r.x + 4, y, f, col, topCut(s, f, r.w - 8)); y += fontHeight(f) + gap;
    };
    if (picHost.wifiUp()) {
        line("Scan the code with your phone.", 0, 6, PIC_INK, 18);
        line("Choose a photo, fit it in the frame,", 6, 2, PIC_INK, 6);
        line("then press Send.", 6, 2, PIC_INK, 26);
        line("Or type this address:", 6, 2, PIC_SOFT, 8);
        line(pictures.shortUrl(), 5, 2, PIC_INK, 0);
    } else {
        line("The transmitter needs WiFi", 0, 6, PIC_INK, 8);
        line("to receive a photo.", 0, 6, PIC_INK, 26);
        line("Press WiFi setup to join a network.", 6, 2, PIC_SOFT, 0);
    }
    picUnclip();
}

// What each part shows now, as a key: a part is drawn again only when its key changes.
static std::string picKeyOf(int id) {
    using P = ldrc::Pictures;
    const int m = pictures.mode();
    if (id == 1) return pictures.title() + "|" + std::to_string(pictures.page()) + "/" + std::to_string(pictures.pages()) + "|" + std::to_string(m);
    if (id == 2 || id == 3) { const int dir = id == 2 ? -1 : 1; return std::to_string(pictures.arrowShown(dir)) + std::to_string(pictures.pressed() == (dir < 0 ? P::P_BACK : P::P_ON)); }
    if (id == 4) return std::to_string(pictures.helpShown()) + std::to_string(pictures.pressed() == P::P_HELP);
    if (id >= 10 && id < 10 + ldrc::PIC_PER_PAGE) {
        if (m == P::RECEIVE) return "-";
        const int slot = id - 10, e = pictures.entryAt(slot);
        if (e < 0) return "empty";
        const ldrc::PicEntry &en = pictures.entries()[e];
        PicThumb *t = picThumbFind(picKey(en.name, en.mine));
        return en.name + (en.mine ? "*" : "") + "|" + std::to_string(e == pictures.selected()) + std::to_string(pictures.pressed() == P::P_TILE + slot) + (t ? (t->px ? "T" : "B") : "-");
    }
    if (id == 20) return pictures.status() + "|" + std::to_string(pictures.statusTone());
    if (id >= 30 && id < 34) { const int i = id - 30; return pictures.buttonText(i) + "|" + std::to_string(pictures.buttonOn(i)) + std::to_string(pictures.pressed() == P::P_BUTTON + i) + "|" + std::to_string(picBtnFont); }
    if (id == 40) return m == P::RECEIVE ? pictures.url() + "|" + std::to_string(picHost.wifiUp()) : "-";
    if (id == 41) return m == P::RECEIVE ? pictures.shortUrl() + "|" + std::to_string(picHost.wifiUp()) : "-";
    return "";
}
static ldrc::PicRect picRectOf(int id) {
    if (id == 1) return { 0, 0, PIC_HELP_X, ldrc::PIC_STRIP_H - 1 };
    if (id == 4) return { PIC_HELP_X, 0, W - PIC_HELP_X, ldrc::PIC_STRIP_H - 1 };
    if (id == 2) return ldrc::picArrow(-1);
    if (id == 3) return ldrc::picArrow(1);
    if (id >= 10 && id < 10 + ldrc::PIC_PER_PAGE) { const ldrc::PicRect t = ldrc::picTile(id - 10), l = ldrc::picLabel(id - 10); return { t.x, t.y, t.w, l.y + l.h - t.y }; }
    if (id == 20) return ldrc::picStatus();
    if (id >= 30 && id < 34) return ldrc::picButton(id - 30);
    if (id == 40) return ldrc::picQr();
    if (id == 41) return ldrc::picInfo();
    return { 0, 0, 0, 0 };
}
static void picDrawPart(int id) {
    const bool rx = pictures.mode() == ldrc::Pictures::RECEIVE;
    if (id == 1) picDrawTitle();
    else if (id == 4) picDrawHelp();
    else if (id == 2 || id == 3) { if (!rx) picDrawArrow(id == 2 ? -1 : 1); }
    else if (id >= 10 && id < 10 + ldrc::PIC_PER_PAGE) { if (!rx) picDrawTile(id - 10); }
    else if (id == 20) picDrawStatus();
    else if (id >= 30 && id < 34) picDrawButton(id - 30);
    else if (id == 40) { if (rx) picDrawQr(); }
    else if (id == 41) { if (rx) picDrawInfo(); }
}
static const int PIC_PARTS[] = { 1, 4, 2, 3, 10, 11, 12, 13, 14, 15, 16, 17, 20, 30, 31, 32, 33, 40, 41 };

// ------------------------------------------------------------------ the finger
static void picTouch(bool pressed, int x, int y, uint32_t now) {
    { static uint32_t lastDownHere = 0; if (pressed) lastDownHere = now;   // a corner held (the door, the radios): that finger is not for this page (1.11.3)
      if (touchLockout) { if (!pressed && (int32_t) (now - lastDownHere) > 80) touchLockout = false; return; } }
    static bool down = false; static uint32_t seen = 0; static int lastX = 0, lastY = 0;
    if (pressed) {
        seen = now; lastX = x; lastY = y;
        if (down) return;
        down = true; pictures.touchDown(x, y);
        return;
    }
    if (!down || now - seen <= 80) return;                       // the touch chip drops the odd sample mid-press
    down = false;
    pictures.touchUp(lastX, lastY);
}

// ------------------------------------------------------------------ the moment "Model image..." is touched
// The Teensy needs a moment to get its page ready: the chooser's frame is shown at once, and the chooser draws itself
// over it when the page arrives (Malcolm, 10-03: "perhaps during this brief pause, we should show a little please
// wait banner?"). Any button whose script orders the Teensy's command 44 (StartChooseImage): the model's picture on
// FrontView, ModelsView and RXOptionsView, and "Model image..." on RXOptionsView.
static uint32_t picSoonUntil = 0; static std::string picSoonFrom;
static void picSoon() {
    if (pictures.mode() != ldrc::Pictures::CLOSED || topOn || updShowing() || wifiPage.showing() || !sdOk || !topReady()) return;
    {
        TopDraw on;
        gfx->fillRect(0, 0, W, H, PIC_BACK);
        gfx->fillRect(0, 0, W, ldrc::PIC_STRIP_H - 1, PIC_STRIP); gfx->drawFastHLine(0, ldrc::PIC_STRIP_H - 1, W, PIC_INK);
        picText(14, (ldrc::PIC_STRIP_H - fontHeight(0)) / 2 + 2, 0, PIC_INK, "Pictures");
        picTextCentred({ 0, 190, W, 60 }, 0, PIC_SOFT, "Opening...");
    }
    topX = 0; topY = 0; topW = W; topH = H; topWho = 4; topOn = true;
    dirty(0, 0, W, H); touchPainted = true;
    picSoonUntil = millis() + 2500; picSoonFrom = page.name;
}
static void picSoonPoll() {
    if (!picSoonUntil) return;
    const bool arrived = page.name == "ImageView";
    if (!arrived && page.name == picSoonFrom && (int32_t) (millis() - picSoonUntil) < 0) return;
    picSoonUntil = 0;                                            // the chooser is here, or the Teensy went elsewhere, or never came
    if (!arrived && topWho == 4 && pictures.mode() == ldrc::Pictures::CLOSED) { topOn = false; topWho = 0; dirty(0, 0, W, H); touchPainted = true; }
}

// On the setup pages one touch away from the chooser, its list and the thumbnails of the page it will open on are made
// in the background, a few rows at a time (never on the front page: that one is for flying).
static void picWarm() {
    if (!sdOk) return;
    if (picJob.on) { picJobStep(); return; }
    static std::vector<ldrc::PicEntry> raw, list;
    picHost.list(raw); ldrc::picBuildList(raw, list);
    Comp *ex = find("exp0");
    const int at = ldrc::picIndexOf(list, ex ? ldrc::picNameFromPath(ex->txt) : ""), first = at / ldrc::PIC_PER_PAGE * ldrc::PIC_PER_PAGE;
    for (int i = first; i < first + ldrc::PIC_PER_PAGE && i < (int) list.size(); ++i) {
        const ldrc::PicEntry &en = list[i];
        if (ldrc::picSameName(en.name, ldrc::PIC_NONE) || picThumbFind(picKey(en.name, en.mine))) continue;
        picJobStart(en.name, en.mine); return;
    }
}

// ------------------------------------------------------------------ every pass of loop()
static bool picDeclined = false;                                 // the Teensy did not answer (before B21): its own page, until it leaves it
static void picPoll() {
    static bool wasUp = false; static uint32_t drawnLayout = 0; static std::map<int, std::string> drawn;
    using P = ldrc::Pictures;
    picSoonPoll();
    if (page.name == "ImageView") {                              // the Teensy's "Choose image" page: ours covers it
        Comp *t0 = find("t0"), *ex = find("exp0");
        std::string model = t0 ? t0->txt : "";
        if (model == "Modelname") model.clear();                 // (the page's own text, before the Teensy has written the model's name)
        const std::string cur = ex ? ex->txt : "";
        if (pictures.mode() == P::CLOSED) { if (!picDeclined && sdOk) pictures.open(model, cur); }
        else { pictures.setModel(model); pictures.setCurrent(cur); }
    } else {
        if (pictures.mode() != P::CLOSED) pictures.pageGone();
        picDeclined = false;
        if ((page.name == "RXOptionsView" || page.name == "ModelsView") && !topOn) picWarm();
    }
    pictures.poll();
    if (pictures.gaveUp()) { picDeclined = true; banner("The main board did not answer: update the transmitter for the new chooser"); }
    const bool up = pictures.mode() != P::CLOSED && !updShowing() && !wifiPage.showing() && topReady();
    if (up) {
        if (pictures.mode() != P::RECEIVE && !picJob.on) {      // the next thumbnail this page lacks
            for (int s = 0; s < ldrc::PIC_PER_PAGE; ++s) {
                const int e = pictures.entryAt(s); if (e < 0) continue;
                const ldrc::PicEntry &en = pictures.entries()[e];
                if (ldrc::picSameName(en.name, ldrc::PIC_NONE) || picThumbFind(picKey(en.name, en.mine))) continue;
                picJobStart(en.name, en.mine); break;
            }
        }
        picJobStep();
        if (!wasUp || pictures.layout() != drawnLayout) {
            TopDraw on;
            picChooseFont();
            gfx->fillRect(0, 0, W, H, PIC_BACK);
            gfx->drawFastHLine(0, ldrc::PIC_STRIP_H - 1, W, PIC_INK);
            drawn.clear();
            for (int id : PIC_PARTS) { picDrawPart(id); drawn[id] = picKeyOf(id); }
            drawnLayout = pictures.layout();
            topX = 0; topY = 0; topW = W; topH = H; topWho = 4; topOn = true;
            dirty(0, 0, W, H); touchPainted = true;
        } else {
            for (int id : PIC_PARTS) {
                std::string k = picKeyOf(id);
                if (drawn[id] == k) continue;
                { TopDraw on; picDrawPart(id); }
                drawn[id] = k;
                const ldrc::PicRect r = picRectOf(id);
                dirty(r.x, r.y, r.w, r.h); touchPainted = true;
            }
        }
    } else if (wasUp) {
        if (topWho == 4) { topOn = false; topWho = 0; }
        drawn.clear();
        dirty(0, 0, W, H); touchPainted = true;                  // the page, as the Teensy has drawn it meanwhile
    }
    // Away from the pictures' pages, or short of memory: the thumbnails' memory goes back (they are kept while the
    // pilot is between the model's options and the chooser, so it opens with its pictures already there).
    const bool near = page.name == "ImageView" || page.name == "RXOptionsView" || page.name == "ModelsView";
    if (pictures.mode() == P::CLOSED && (!near || ESP.getFreePsram() < 1500000) && (picJob.on || !picThumbs.empty())) {
        if (picJob.on) { if (picJob.f) picJob.f.close(); free(picJob.px); picJob = PicJob(); }
        picThumbsFree();
    }
    wasUp = up;
}

// Called by loadPage() as the Teensy's page arrives, BEFORE anything of it is drawn: the chooser opens and draws itself
// on the layer above at once, so its page never reaches the glass. (Malcolm, 10-03: "when going to your new screen for
// selecting a photograph, it briefly displays my old screen".) The Teensy (B22) names the model and its picture
// BEFORE the page, so this first frame is right too.
static void picPageLoaded() { if (page.name == "ImageView") picPoll(); }

// ------------------------------------------------------------------ the phone
// GET /photo?k=<key>: the page. GET /photo/info?k=: the model's name, a name for the photo, the names taken.
// POST /photo/put?k=&name= (a file of 128 004 bytes, multipart, header X-LDRC: 1): the photo, 320 x 200, RGB565.
// Nothing answers unless the chooser is open on the transmitter and the key is the one it shows.
static File picUpFile; static bool picUpGood = false; static uint32_t picUpBytes = 0; static std::string picUpName, picUpWhy; static uint8_t picUpHead[4];
static bool picUpAllowed(std::string &why) {
    if (!pictures.keyOk(web.arg("k").c_str())) { why = "This link has expired. On the transmitter, press Add photo again."; return false; }
    if (!pictures.acceptsUpload()) { why = "The transmitter is busy. Try again in a moment."; return false; }
    return true;
}
static void picWeb() {
    web.on("/photo", HTTP_GET, []() {
        if (!pictures.keyOk(web.arg("k").c_str())) {
            web.send(403, "text/html", "<!doctype html><meta name=viewport content='width=device-width'><body style='font:20px sans-serif;padding:20px'>"
                                       "<h2>This link has expired</h2><p>On the transmitter, open <b>Choose image</b> and press <b>Add photo</b>, then scan the new code.</p>");
            return;
        }
        File f = SD.open(PIC_PAGE_FILE, FILE_READ);
        if (!f) { web.send(500, "text/plain", "The photo page is not on the screen's card: update the transmitter."); return; }
        web.sendHeader("Cache-Control", "no-store");
        web.streamFile(f, "text/html");
        f.close();
    });
    web.on("/photo/info", HTTP_GET, []() {
        if (!pictures.keyOk(web.arg("k").c_str())) { web.send(403, "text/plain", "This link has expired. On the transmitter, press Add photo again."); return; }
        auto esc = [](const std::string &t) { std::string o; for (char c : t) { if (c == '"' || c == '\\') o.push_back('\\'); if ((unsigned char) c >= 32) o.push_back(c); } return o; };
        std::string out = "{\"model\":\"" + esc(pictures.model()) + "\",\"name\":\"" + esc(ldrc::picNameSuggest(pictures.model())) + "\",\"w\":" + std::to_string(ldrc::PIC_W) + ",\"h\":" + std::to_string(ldrc::PIC_H) + ",\"taken\":[";
        bool first = true;
        for (auto &e : pictures.entries()) {
            if (ldrc::picSameName(e.name, ldrc::PIC_NONE)) continue;
            out += std::string(first ? "" : ",") + "{\"n\":\"" + esc(e.name) + "\",\"m\":" + (e.mine ? "1" : "0") + "}"; first = false;
        }
        out += "]}";
        web.sendHeader("Cache-Control", "no-store");
        web.send(200, "application/json", out.c_str());
    });
    web.on("/photo/put", HTTP_POST, []() {
        if (picUpGood) web.send(200, "text/plain", ("saved " + picUpName).c_str());
        else web.send(picUpWhy.rfind("This link", 0) == 0 ? 403 : 400, "text/plain", picUpWhy.empty() ? "No photo came with that request." : picUpWhy.c_str());
        picUpGood = false; picUpName.clear(); picUpWhy.clear();   // (a request with no file must not be answered by the one before)
    }, []() {
        HTTPUpload &up = web.upload();
        if (up.status == UPLOAD_FILE_START) {
            picUpGood = false; picUpBytes = 0; picUpName.clear(); picUpWhy.clear(); memset(picUpHead, 0, sizeof picUpHead);
            std::string why;
            if (web.header("X-LDRC") != "1") { picUpWhy = "refused"; return; }
            if (!picUpAllowed(why)) { picUpWhy = why; return; }
            const std::string name = web.arg("name").c_str();
            if (!ldrc::picNameOk(name)) { picUpWhy = "The name must be 1 to 8 letters or digits."; return; }
            if (!sdOk) { picUpWhy = "The screen's card is not there."; return; }
            picUpName = name;
            const std::string path = std::string(PIC_MINE_DIR) + "/" + name + ".new";
            sdMakeFolders(path.c_str()); SD.remove(path.c_str());
            picUpFile = SD.open(path.c_str(), FILE_WRITE);
            if (!picUpFile) { picUpWhy = "The screen could not write on its card."; picUpName.clear(); return; }
            picUpGood = true;
            pictures.uploadBegun(name);
        } else if (up.status == UPLOAD_FILE_WRITE) {
            if (!picUpGood || !picUpFile) return;
            for (size_t i = 0; i < up.currentSize && picUpBytes + i < 4; ++i) picUpHead[picUpBytes + i] = up.buf[i];
            if (picUpBytes + up.currentSize > ldrc::PIC_FILE_BYTES) { picUpGood = false; picUpWhy = "it was too big"; }
            else if (picUpFile.write(up.buf, up.currentSize) != up.currentSize) { picUpGood = false; picUpWhy = "the card is full"; }
            picUpBytes += up.currentSize;
            pictures.uploadBytes(picUpBytes);
            breathe();                                           // the Teensy's display commands, the link and the sound go on
        } else if (up.status == UPLOAD_FILE_END || up.status == UPLOAD_FILE_ABORTED) {
            if (picUpFile) picUpFile.close();
            if (picUpName.empty()) return;
            if (up.status == UPLOAD_FILE_ABORTED) { picUpGood = false; picUpWhy = "the connection was lost"; }
            if (picUpGood && picUpBytes != ldrc::PIC_FILE_BYTES) { picUpGood = false; picUpWhy = "it was not a whole picture"; }
            if (picUpGood && !ldrc::picHeaderOk(picUpHead, 4)) { picUpGood = false; picUpWhy = "it was not 320 x 200"; }
            const std::string final = picFile(picUpName, true), tmp = std::string(PIC_MINE_DIR) + "/" + picUpName + ".new";
            if (picUpGood) {
                SD.remove(final.c_str());
                if (!SD.rename(tmp.c_str(), final.c_str())) { picUpGood = false; picUpWhy = "the screen could not write on its card"; }
            }
            if (!picUpGood) SD.remove(tmp.c_str());
            picThumbDrop(picUpName);
            if (picUpGood) picCardListOk = false;
            pictures.uploadEnded(picUpGood, picUpName, picUpWhy);
        }
    });
}
