// Films on the help pages (screen 1.11.85). Malcolm, 17 Oct 2026, of the instructional film made for him (Easy tuning,
// from the transmitter): "I think the timing is now perfect! Can we run this animation on the screen of our transmitter?"
// A help page whose subject has a film on the card - /hmi/films/<NAME>.ldf and its sound /hmi/films/<NAME>.wav, NAME as in the
// page's Help button ("HelpView:EASY.TXT" -> EASY) - shows a "Film" button at its top left, mirroring Help at the top
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

static const int FILM_WHO = 11, FILM_BTN_WHO = 12;              // the layer's owners (main.cpp topWho): the film; the help page's button
static const int FILM_BTN_X = 10, FILM_BTN_Y = 4, FILM_BTN_W = 150, FILM_BTN_H = 50;
static const uint32_t FILM_HELP_WINDOW_MS = 4000;              // a Help tap this recent names the help page that appears
static std::string filmTopic;                                   // the subject of the Help button last tapped ("EASY")
static uint32_t filmTopicAt = 0;
static bool filmLatched = false, filmHas = false;               // the help page is up for filmTopic; its film is on the card
static bool filmBtnHeld = false, filmBtnDrawnDown = false; static uint32_t filmBtnSeen = 0;
static File filmFile; static ldrcfilm::Header filmHead;
static uint8_t *filmTable = nullptr, *filmBuf = nullptr; static uint32_t filmBufSize = 0;
static uint32_t filmStartMs = 0; static int32_t filmLast = -1;
static JPEGDEC filmJpeg;
static bool filmUp() { return topOn && topWho == FILM_WHO; }
static bool filmButtonUp() { return topOn && topWho == FILM_BTN_WHO; }
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
static std::string filmPath(const char *ext) { return "/hmi/films/" + filmTopic + ext; }   // (under /hmi: the folders every screen's updater takes - a /films of its own would have made an older screen refuse the release)

static void filmDrawButton(bool down) {
    if (!topReady()) return;
    TopDraw td;
    const int x = FILM_BTN_X, y = FILM_BTN_Y, w = FILM_BTN_W, h = FILM_BTN_H;
    const uint16_t face = down ? 0x9CD3 : 0xD69A, hi = shade(face, 60), lo = shade(face, -45);
    gfx->fillRect(x, y, w, h, face);
    for (int k = 0; k < 3; ++k) {
        gfx->drawFastHLine(x + k, y + k, w - 2 * k, down ? lo : hi); gfx->drawFastVLine(x + k, y + k, h - 2 * k, down ? lo : hi);
        gfx->drawFastHLine(x + k, y + h - 1 - k, w - 2 * k, down ? hi : lo); gfx->drawFastVLine(x + w - 1 - k, y + k, h - 2 * k, down ? hi : lo);
    }
    const std::string label = "Film";
    drawGlyphs(x + (w - textWidth(6, label)) / 2 + (down ? 1 : 0), y + (h - fontHeight(6)) / 2 + (down ? 1 : 0), 6, 0x0000, label);
    filmBtnDrawnDown = down;
    dirty(x, y, w, h); touchPainted = true;
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

// A picture into our layer: only what changed is copied, and marked for the panel
static int filmDraw(JPEGDRAW *p) {
    if (!topFb) return 0;
    const int x = p->x, y = p->y, w = p->iWidth;
    if (x < 0 || x >= W) return 1;
    const int n = std::min(w, W - x);
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
    const uint32_t t0 = micros();
    bool ok = filmJpeg.openRAM(filmBuf, (int) size, filmDraw) != 0;
    if (ok) { filmJpeg.setPixelType(RGB565_LITTLE_ENDIAN); ok = filmJpeg.decode(0, 0, 0) != 0; filmJpeg.close(); }
    const uint32_t us = micros() - t0; filmDecodeUs = us; if (us > filmDecodeMax) filmDecodeMax = us; filmPictures++;
    return ok;
}

static void filmStop() {
    if (filmPlaying && audioId == FILM_AUDIO_ID) audioStop();
    filmPlaying = false;
    if (filmFile) filmFile.close();
    if (filmUp()) { topOn = false; topWho = 0; dirty(0, 0, W, H); touchPainted = true; }   // the help page again, as it was
}
static bool filmStart() {
    filmStop();
    if (!sdOk || !filmAllowed() || filmTopic.empty() || !topReady()) return false;
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
static void filmTouch(bool pressed, int, int, uint32_t) { if (pressed) filmStop(); }   // a tap anywhere: the film stops (the lift is the page's no more)
static void filmTouchCancel() {}
static void filmButtonCancel() { if (filmBtnHeld) { filmBtnHeld = false; if (filmButtonUp()) filmDrawButton(false); } }   // (a corner held on it: radios or the door, not the film)

// The help page's button: true while it has the finger (the page underneath sees none of it)
static bool filmButtonTouch(bool pressed, int x, int y, uint32_t now) {
    if (filmBtnHeld) {
        if (pressed) { filmBtnSeen = now; return true; }
        if (now - filmBtnSeen < 80) return true;              // (a sample the touch chip dropped is not a lift)
        filmBtnHeld = false;
        if (filmButtonUp()) { filmDrawButton(false); if (!filmStart()) filmHas = false; }   // (a film that will not play: its button goes)
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
        if (!filmUp() || !filmAllowed() || !helpPage) { filmStop(); return; }   // (another page of ours took the layer; the safety off or the motor on; the page went)
        const uint32_t ms = now - filmStartMs;
        if (ms >= ldrcfilm::lengthMs(filmHead) + 700) { filmStop(); return; }   // the end: the last picture held a moment
        const int32_t k = ldrcfilm::pictureFor(ldrcfilm::frameAt(ms, filmHead), filmLast, filmTable);
        if (k >= 0) {
            for (int32_t i = filmLast + 1; i < k; ++i) if (ldrcfilm::rd32(filmTable + 8 * i + 4)) filmSkipped++;
            if (!filmDecode(k)) { filmStop(); return; }
            filmLast = k;
        }
        return;
    }
    // the button: on the help page that a recent Help tap named, while its film is on the card and no model is connected
    if (!helpPage) { filmLatched = false; if (filmButtonUp()) filmButtonHide(); if (!filmTopic.empty() && now - filmTopicAt > FILM_HELP_WINDOW_MS) filmTopic.clear(); return; }
    if (!filmLatched) {
        if (filmTopic.empty() || now - filmTopicAt > FILM_HELP_WINDOW_MS) return;
        filmLatched = true; filmHas = sdOk && SD.exists(filmPath(".ldf").c_str());
    }
    const bool want = filmHas && filmAllowed() && (!topOn || topWho == FILM_BTN_WHO);
    if (want && !filmButtonUp()) filmButtonShow();
    else if (!want && filmButtonUp()) filmButtonHide();
}
