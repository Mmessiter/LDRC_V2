// Films on the help pages (screen 1.11.85). Malcolm, 17 Oct 2026, of the instructional film made for him (Easy tuning,
// from the transmitter): "I think the timing is now perfect! Can we run this animation on the screen of our transmitter?"
// 1.11.87 (Malcolm: "Presumably we could store several of these files and select between them with a small menu? ... let's
// do it now!"): every help page shows a "Films" button at its top left, mirroring Help at the top right, while there are
// films on the card - /hmi/films/<NAME>.ldf and its sound <NAME>.wav, listed with their titles in /hmi/films/films.txt
// ("<NAME>: <title>", the menu's order) - and it opens the films menu: a button a film, OK back to the help page. A film
// that ends, or is stopped by a tap, comes back to the menu. (1.11.85-86 offered one film, the help page's own.) Never shown
// right; never while the motor could run - the safety off, or the motor enabled where no safety switch is defined (the
// main board's own rule for the screen's radios, TxState flying() 1 and 2). A model merely connected, safety on, is
// allowed: Easy tuning itself needs the helicopter on, and its help is where its film is wanted. The film
// plays on our layer over the whole screen, its pictures decoded straight into the layer: only the pixels that changed
// are marked for the panel, so a still moment costs nothing and a moving finger a few rectangles. A tap anywhere stops
// it; so do the safety going off or the motor on, the page going, and the film's end. The format and its sums: film_core.h (host-tested,
// hmi/test_film); the films are made by TXV1B dev/video (LDRC_TARGET=screen).
#pragma once
#include <JPEGDEC.h>
#include "film_core.h"

static const int FILM_WHO = 11, FILM_BTN_WHO = 12, FILM_MENU_WHO = 13;   // the layer's owners (main.cpp topWho): a film; the help page's button; the films menu
static const int FILM_BTN_X = 10, FILM_BTN_Y = 4, FILM_BTN_W = 150, FILM_BTN_H = 50;
static const uint32_t FILM_HELP_WINDOW_MS = 4000;              // a Help tap this recent names the help page that appears
static const int FILM_MAX = 8, FILM_OK = 99;                    // the menu: up to 8 films, two columns of four; OK
static std::string filmTopic;                                   // the subject of the Help button last tapped ("EASY")
static uint32_t filmTopicAt = 0;
static bool filmLatched = false, filmHas = false;               // the help page is up (a Help tap named it); there are films on the card
static bool filmBtnHeld = false, filmBtnDrawnDown = false; static uint32_t filmBtnSeen = 0;
static ldrcfilm::Entry filmList[FILM_MAX]; static int filmCount = 0;   // (1.11.87) the menu's films, in films.txt's order, those on the card
static int filmMenuDown = -1; static uint32_t filmMenuSeen = 0; static bool filmMenuHeld = false;
static bool filmMenuDeaf = false;                               // the finger that stopped a film: the menu ignores it until it lifts
static File filmFile; static ldrcfilm::Header filmHead;
static uint8_t *filmTable = nullptr, *filmBuf = nullptr; static uint32_t filmBufSize = 0;
static uint32_t filmStartMs = 0; static int32_t filmLast = -1;
static JPEGDEC filmJpeg;
static bool filmUp() { return topOn && topWho == FILM_WHO; }
static bool filmButtonUp() { return topOn && topWho == FILM_BTN_WHO; }
static bool filmMenuUp() { return topOn && topWho == FILM_MENU_WHO; }
static bool filmPlaying = false;
static bool filmAllowed() { const int f = flyingNow(); return f == 0 || f >= 3; }   // not 1 (the motor on) or 2 (the safety off)

// The Help button just tapped (main.cpp, at the lift: its script "print "HelpView:EASY.TXT" ...")
static void filmNoteHelp(const std::string &script) {
    const size_t at = script.find("HelpView:");
    if (at == std::string::npos) return;
    std::string n;
    for (size_t i = at + 9; i < script.size() && n.size() < 12; ++i) { const char c = script[i]; if (c == '.' || c == '"' || c == '\n' || c == ' ') break; n += (char) toupper((unsigned char) c); }
    if (n.empty()) return;
    filmTopic = n; filmTopicAt = millis(); filmLatched = false;
}
static std::string filmName;                                     // the film playing
static std::string filmPath(const char *ext) { return "/hmi/films/" + filmName + ext; }   // (under /hmi: the folders every screen's updater takes - a /films of its own would have made an older screen refuse the release)
static void filmReadList() {                                     // the menu's films: films.txt's lines "<NAME>: <title>", those whose film is on the card
    filmCount = 0;
    if (!sdOk) return;
    std::string list;
    File l = SD.open("/hmi/films/films.txt"); if (l) { while (l.available() && list.size() < 4096) list += (char) l.read(); l.close(); }
    ldrcfilm::Entry all[FILM_MAX * 2]; const int n = ldrcfilm::parseFilms(list.c_str(), all, FILM_MAX * 2);
    for (int i = 0; i < n && filmCount < FILM_MAX; ++i) {
        const std::string path = std::string("/hmi/films/") + all[i].name + ".ldf";
        if (SD.exists(path.c_str())) filmList[filmCount++] = all[i];
    }
}

static void filmBevel(int x, int y, int w, int h, bool down, const std::string &label) {   // a button as the pages draw theirs (on our layer: TopDraw first)
    const uint16_t face = down ? 0x9CD3 : 0xD69A, hi = shade(face, 60), lo = shade(face, -45);
    gfx->fillRect(x, y, w, h, face);
    for (int k = 0; k < 3; ++k) {
        gfx->drawFastHLine(x + k, y + k, w - 2 * k, down ? lo : hi); gfx->drawFastVLine(x + k, y + k, h - 2 * k, down ? lo : hi);
        gfx->drawFastHLine(x + k, y + h - 1 - k, w - 2 * k, down ? hi : lo); gfx->drawFastVLine(x + w - 1 - k, y + k, h - 2 * k, down ? hi : lo);
    }
    const int font = textWidth(6, label) <= w - 20 ? 6 : 2;
    const std::string s = topCut(label, font, w - 16);
    drawGlyphs(x + (w - textWidth(font, s)) / 2 + (down ? 1 : 0), y + (h - fontHeight(font)) / 2 + (down ? 1 : 0), font, 0x0000, s);
}
static void filmDrawButton(bool down) {
    if (!topReady()) return;
    { TopDraw td; filmBevel(FILM_BTN_X, FILM_BTN_Y, FILM_BTN_W, FILM_BTN_H, down, "Films"); }
    filmBtnDrawnDown = down;
    dirty(FILM_BTN_X, FILM_BTN_Y, FILM_BTN_W, FILM_BTN_H); touchPainted = true;
}
static void filmButtonShow() {
    if (!topReady()) return;
    topX = FILM_BTN_X; topY = FILM_BTN_Y; topW = FILM_BTN_W; topH = FILM_BTN_H; topWho = FILM_BTN_WHO; topOn = true;
    filmDrawButton(false);
}
static void filmButtonHide() {
    if (filmButtonUp()) { topOn = false; topWho = 0; dirty(FILM_BTN_X, FILM_BTN_Y, FILM_BTN_W, FILM_BTN_H); touchPainted = true; }
    filmBtnHeld = false;
}

// ------------------------------------------------------------------ the films menu (1.11.87): the help page's look - its title bar, its navy card - and the pages' buttons
static void filmMenuRect(int i, int &x, int &y, int &w, int &h) {
    if (i == FILM_OK) { x = 596; y = 404; w = 180; h = 56; return; }
    x = 40 + (i % 2) * 366; y = 84 + (i / 2) * 76; w = 354; h = 62;
}
static int filmMenuAt(int px, int py) {
    for (int i = 0; i < filmCount; ++i) { int x, y, w, h; filmMenuRect(i, x, y, w, h); if (px >= x && px < x + w && py >= y && py < y + h) return i; }
    int x, y, w, h; filmMenuRect(FILM_OK, x, y, w, h); if (px >= x && px < x + w && py >= y && py < y + h) return FILM_OK;
    return -1;
}
static void filmMenuDrawButton(int i, bool down) {
    int x, y, w, h; filmMenuRect(i, x, y, w, h);
    { TopDraw td; filmBevel(x, y, w, h, down, i == FILM_OK ? std::string("OK") : std::string(filmList[i].title)); }
    dirty(x, y, w, h); touchPainted = true;
}
static void filmMenuDraw() {
    if (!topReady()) return;
    {
        TopDraw td;
        gfx->fillRect(0, 0, W, 58, 2214);                         // the title bar, as the help page's
        gfx->fillRect(0, 58, W, H - 58, 4426);                    // its navy card
        const std::string title = "Films";
        drawGlyphs((W - textWidth(0, title)) / 2, (58 - fontHeight(0)) / 2, 0, 0xFFFF, title);
        const std::string hint = "Tap a film to play it. Tap anywhere to stop.";
        drawGlyphs(40, 404 + (56 - fontHeight(2)) / 2, 2, 0xFFFF, topCut(hint, 2, 540));
        for (int i = 0; i < filmCount; ++i) { int x, y, w, h; filmMenuRect(i, x, y, w, h); filmBevel(x, y, w, h, false, filmList[i].title); }
        int x, y, w, h; filmMenuRect(FILM_OK, x, y, w, h); filmBevel(x, y, w, h, false, "OK");
    }
    dirty(0, 0, W, H); touchPainted = true;
}
static void filmMenuOpen() {
    if (!topReady() || !filmCount) return;
    topX = 0; topY = 0; topW = W; topH = H; topWho = FILM_MENU_WHO; topOn = true;
    filmMenuDown = -1; filmMenuHeld = false;
    filmMenuDraw();
}
static void filmMenuClose() {                                    // back to the help page (its Films button comes back)
    if (filmMenuUp()) { topOn = false; topWho = 0; dirty(0, 0, W, H); touchPainted = true; }
    filmMenuDown = -1; filmMenuHeld = false;
}

// A picture into our layer: only what changed is copied, and marked for the panel
static int filmDraw(JPEGDRAW *p) {
    if (!topFb) return 0;
    const int x = p->x, y = p->y, w = p->iWidth;
    if (x < 0 || x >= W) return 1;
    const int n = std::min(p->iWidthUsed > 0 ? p->iWidthUsed : w, W - x);   // (a picture's right edge: only its own pixels)
    int x0 = W, x1 = -1;
    for (int r = 0; r < p->iHeight && y + r < H; ++r) {
        uint16_t *dst = topFb + (y + r) * W + x; const uint16_t *src = p->pPixels + r * w;
        int f, l; ldrcfilm::rowDiff(dst, src, n, f, l);
        if (l >= f) { memcpy(dst + f, src + f, (size_t) (l - f + 1) * 2); if (f < x0) x0 = f; if (l > x1) x1 = l; }
    }
    if (x1 >= x0) dirty(x + x0, y, x1 - x0 + 1, std::min(p->iHeight, H - y));
    return 1;
}
static bool filmDecode(int32_t k) {
    const uint32_t off = ldrcfilm::rd32(filmTable + 8 * k), size = ldrcfilm::rd32(filmTable + 8 * k + 4);
    if (!size || size > filmBufSize || !filmFile.seek(off) || filmFile.read(filmBuf, size) != (int) size) return false;
    uint16_t rx, ry, rw, rh; uint32_t jo;                     // (version 2: only the rectangle that changed, drawn where it belongs)
    if (!ldrcfilm::pictureAt(filmBuf, size, filmHead, rx, ry, rw, rh, jo)) return false;
    const uint32_t t0 = micros();
    bool ok = filmJpeg.openRAM(filmBuf + jo, (int) (size - jo), filmDraw) != 0;
    if (ok) { filmJpeg.setPixelType(RGB565_LITTLE_ENDIAN); ok = filmJpeg.decode(rx, ry, 0) != 0; filmJpeg.close(); }
    const uint32_t us = micros() - t0; filmDecodeUs = us; if (us > filmDecodeMax) filmDecodeMax = us; filmPictures++;
    return ok;
}

static void filmStop(bool toMenu = false) {
    if (filmPlaying && audioId == FILM_AUDIO_ID) audioStop();
    filmPlaying = false;
    if (filmFile) filmFile.close();
    if (filmUp()) {
        if (toMenu && filmCount) { topWho = FILM_MENU_WHO; filmMenuDown = -1; filmMenuHeld = false; filmMenuDraw(); }   // the films menu again
        else { topOn = false; topWho = 0; dirty(0, 0, W, H); touchPainted = true; }   // the help page, as it was
    }
}
static bool filmStart() {
    filmStop();
    if (!sdOk || !filmAllowed() || filmName.empty() || !topReady()) return false;
    filmMenuDown = -1; filmMenuHeld = false;
    filmFile = SD.open(filmPath(".ldf").c_str());
    if (!filmFile) return false;
    uint8_t head[ldrcfilm::HEADER_BYTES];
    const uint32_t fileSize = (uint32_t) filmFile.size();
    if (filmFile.read(head, sizeof head) != (int) sizeof head || !ldrcfilm::parseHeader(head, sizeof head, filmHead, W, H)) { filmFile.close(); return false; }
    free(filmTable); filmTable = (uint8_t *) ps_malloc(8 * filmHead.frames);
    uint32_t biggest = 0;
    if (!filmTable || filmFile.read(filmTable, 8 * filmHead.frames) != (int) (8 * filmHead.frames) || !ldrcfilm::tableSound(filmTable, filmHead, fileSize, biggest)) { filmFile.close(); return false; }
    if (biggest > filmBufSize) { free(filmBuf); filmBuf = (uint8_t *) ps_malloc(biggest); filmBufSize = filmBuf ? biggest : 0; }
    if (!filmBuf) { filmFile.close(); return false; }
    filmBtnHeld = false;
    topX = 0; topY = 0; topW = W; topH = H; topWho = FILM_WHO; topOn = true;
    filmLast = -1; filmPictures = filmSkipped = 0; filmDecodeMax = 0; filmPlaying = true;
    if (!filmDecode(0)) { filmStop(); return false; }          // the first picture before the sound, so they start together
    filmLast = 0;
    audioStartFile(filmPath(".wav").c_str());
    filmStartMs = millis();
    return true;
}
static void filmTouch(bool pressed, int, int, uint32_t now) { if (pressed) { filmStop(true); filmMenuDeaf = true; filmMenuSeen = now; } }   // a tap anywhere: the film stops, back to the menu (the lift is the menu's no more: main.cpp's lockout)
static void filmTouchCancel() { if (filmMenuDown >= 0 && filmMenuUp()) filmMenuDrawButton(filmMenuDown, false); filmMenuDown = -1; filmMenuHeld = false; }
static bool filmStartName(const char *name) { filmName = name; return filmStart(); }
// The menu's buttons: a press shows it pressed, the lift on the same button acts (a sample the touch chip dropped is no lift)
static void filmMenuTouch(bool pressed, int x, int y, uint32_t now) {
    if (filmMenuDeaf) { if (pressed) filmMenuSeen = now; else if (now - filmMenuSeen >= 80) filmMenuDeaf = false; return; }   // (the tap that stopped the film starts nothing)
    if (pressed) {
        filmMenuSeen = now;
        if (!filmMenuHeld) { filmMenuHeld = true; filmMenuDown = filmMenuAt(x, y); if (filmMenuDown >= 0) filmMenuDrawButton(filmMenuDown, true); }
        return;
    }
    if (!filmMenuHeld || now - filmMenuSeen < 80) return;
    filmMenuHeld = false;
    const int i = filmMenuDown; filmMenuDown = -1;
    if (i < 0) return;
    filmMenuDrawButton(i, false);
    if (i == FILM_OK) { filmMenuClose(); return; }
    if (i < filmCount && !filmStartName(filmList[i].name)) { if (!filmUp()) filmMenuDraw(); }   // (a film that will not play: the menu stays)
}
static void filmButtonCancel() { if (filmBtnHeld) { filmBtnHeld = false; if (filmButtonUp()) filmDrawButton(false); } }   // (a corner held on it: radios or the door, not the film)

// The help page's button: true while it has the finger (the page underneath sees none of it)
static bool filmButtonTouch(bool pressed, int x, int y, uint32_t now) {
    if (filmBtnHeld) {
        if (pressed) { filmBtnSeen = now; return true; }
        if (now - filmBtnSeen < 80) return true;              // (a sample the touch chip dropped is not a lift)
        filmBtnHeld = false;
        if (filmButtonUp()) { filmDrawButton(false); filmMenuOpen(); }   // (1.11.87) the films menu
        return true;
    }
    if (!pressed || !filmButtonUp()) return false;
    if (x < FILM_BTN_X || x >= FILM_BTN_X + FILM_BTN_W || y < FILM_BTN_Y || y >= FILM_BTN_Y + FILM_BTN_H) return false;
    filmBtnHeld = true; filmBtnSeen = now; filmDrawButton(true);
    return true;
}

static void filmPoll() {
    const uint32_t now = millis();
    const bool helpPage = page.name == "LogView";
    if (filmPlaying) {
        if (!filmUp() || !filmAllowed() || !helpPage) { filmStop(false); return; }   // (another page of ours took the layer; the safety off or the motor on; the page went)
        const uint32_t ms = now - filmStartMs;
        if (ms >= ldrcfilm::lengthMs(filmHead) + 700) { filmStop(true); return; }   // the end: the last picture held a moment, then the menu
        const int32_t k = ldrcfilm::pictureFor(ldrcfilm::frameAt(ms, filmHead), filmLast, filmTable);
        if (k >= 0) {
            for (int32_t i = filmLast + 1; i < k; ++i) if (ldrcfilm::rd32(filmTable + 8 * i + 4)) filmSkipped++;
            if (!filmDecode(k)) { filmStop(); return; }
            filmLast = k;
        }
        return;
    }
    if (filmMenuUp()) { if (!helpPage || !filmAllowed()) filmMenuClose(); return; }   // (the menu: the help page gone, or the motor could run)
    // the button: on every help page (one a recent Help tap opened - not the log viewer), while there are films on the card and the motor is safe
    if (!helpPage) { filmLatched = false; if (filmButtonUp()) filmButtonHide(); if (!filmTopic.empty() && now - filmTopicAt > FILM_HELP_WINDOW_MS) filmTopic.clear(); return; }
    if (!filmLatched) {
        if (filmTopic.empty() || now - filmTopicAt > FILM_HELP_WINDOW_MS) return;
        filmLatched = true;
        filmReadList();                                            // (1.11.87) the films menu's list
        filmHas = filmCount > 0;
    }
    const bool want = filmHas && filmAllowed() && (!topOn || topWho == FILM_BTN_WHO);
    if (want && !filmButtonUp()) filmButtonShow();
    else if (!want && filmButtonUp()) filmButtonHide();
}
