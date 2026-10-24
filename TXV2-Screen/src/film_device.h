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
// are marked for the panel, so a still moment costs nothing and a moving finger a few rectangles. A tap pauses it (1.11.88:
// Back, Play, Next, Films; 1.11.89: a slider above them, to any moment; 1.11.90: Play, Films, Exit - the slider does what
// Back and Next did); the safety going off or the motor on, the page going, and the film's end stop it. The format and its sums: film_core.h (host-tested,
// hmi/test_film); the films are made by TXV1B dev/video (LDRC_TARGET=screen).
// 1.11.94 (18 Oct 2026). Malcolm: "Some of the animations begin without first clearing the screen which looks untidy" - a
// film started from its help page's button decoded its first picture into our layer, which still held an older picture
// (the last film's), and marked for the panel only the pixels that differed: wherever the two matched, the help page stayed
// in view. The first picture is now shown whole. And: "We might even include a sub menu that lists common rc heli flying
// issues linked to animations that can help correct that issue" - /hmi/films/problems.txt lists them ("<NAME>: <title>",
// as films.txt); every help page shows "Fix problems" top right (where other pages have Help), and the list of all the
// animations has it bottom left: it opens that list, whose own bottom left goes back to "Animations".
#pragma once
#include <JPEGDEC.h>
#include "film_core.h"

static const int FILM_WHO = 11, FILM_BTN_WHO = 12, FILM_MENU_WHO = 13;   // the layer's owners (main.cpp topWho): a film; the help page's button; the films menu
static const int FILM_BTN_X = 10, FILM_BTN_Y = 4, FILM_BTN_W = 150, FILM_BTN_H = 50;
static const uint32_t FILM_HELP_WINDOW_MS = 4000;              // a Help tap this recent names the help page that appears
// (1.11.91) Malcolm: "change the word 'films' to 'videos' or 'animations' if there is room for the longer word" (there is:
// "Animations" is 126 px in the buttons' font); "a video button top left ... should bring up only the video which pertains to
// that particular help menu ... when we pause ... that button should offer all of the available help videos". So a help page
// with an animation of its own shows "Animation", which plays it; the paused bar's "Animations" opens the list of them all,
// ten to a page (there will be one for each help page). An animation returns to where it was started from.
static const int FILM_MAX = 96, FILM_OK = 99, FILM_PREV = 98, FILM_NEXT = 97, FILM_PER_PAGE = 10;   // the list: two columns of five a page; < Previous, Next >, OK
static const int FILM_SWAP = 100;                                // (1.11.94) the list's bottom left: "Fix problems" in the list of them all, "Animations" in the problems list
static const int FILM_FIX_X = 620, FILM_FIX_W = 170;            // (1.11.94) the help page's "Fix problems": top right, where other pages have Help (a help page has none)
static_assert(FILM_BTN_WHO == TOP_TWIN_WHO, "the help page's buttons are the layer's two stretches (main.cpp)");
static int filmMenuPage = 0;                                     // the list's page shown
static std::string filmListText, filmOwn;                        // films.txt as read; this help page's own animation ("": none)
static bool filmFromList = false;                                // the animation playing was chosen from the list (else: the help page's button)
static std::string filmTopic;                                   // the subject of the Help button last tapped ("EASY")
static uint32_t filmTopicAt = 0;
static bool filmLatched = false, filmHas = false;               // the help page is up (a Help tap named it); it has an animation of its own on the card
static bool filmBtnHeld = false, filmBtnDrawnDown = false; static uint32_t filmBtnSeen = 0;
static ldrcfilm::Entry filmList[FILM_MAX]; static int filmCount = 0;   // (1.11.87) the menu's films, in films.txt's order, those on the card
static ldrcfilm::Entry filmProb[FILM_MAX]; static int filmProbCount = 0;   // (1.11.94) the problems, in problems.txt's order, those whose animation is on the card
static int filmMenuList = 0;                                     // (1.11.94) the list shown: 0 every animation, 1 the problems
static bool filmBtnOwn = false, filmBtnFix = false; static int filmBtnWhich = 0;   // (1.11.94) the help page's buttons shown (Animation, Fix problems); the one held (0, 1)
static int filmMenuDown = -1; static uint32_t filmMenuSeen = 0; static bool filmMenuHeld = false;
static bool filmMenuDeaf = false;                               // the finger that stopped a film: the menu ignores it until it lifts
static File filmFile; static ldrcfilm::Header filmHead;
static uint8_t *filmTable = nullptr, *filmBuf = nullptr; static uint32_t filmBufSize = 0;
static uint8_t *filmSections = nullptr; static uint32_t filmSectionCount = 0;   // (version 3) each section's first frame
static uint8_t filmOneSection[4] = {0, 0, 0, 0};                 // (a film without sections: one, from the start)
// (1.11.88) Pause, Back, Play, Next: a tap pauses the film and shows these along its foot; what lay under them is kept
// (1.11.89) and above them a slider (Malcolm: "a bar with a slider so we could slide backwards or forwards a particular
// distance as we might with a video"): the time there, the track with a gap where each part starts, the film's length
// (1.11.90) Malcolm: "Now that we have this wonderful bar, I think we no longer need back, or next ... We do need play and
// we do need films, and I think we need exit too": Play, Films, Exit, in the system pages' last three slots - Exit, which
// leaves, bottom right as OK is on every page
static const int FILM_CTL_PLAY = 0, FILM_CTL_FILMS = 1, FILM_CTL_EXIT = 2, FILM_CTL_N = 3, FILM_BAR_Y = 368, FILM_BAR_H = 480 - 368, FILM_CTL_Y = 421;
static const int FILM_SEEK_X0 = 112, FILM_SEEK_W = 576, FILM_SEEK_MID = 394, FILM_SEEK_R = 13;   // the track (x0 to x0 + w) and its knob
static bool filmPaused = false, filmTapDeaf = false, filmCtlHeld = false, filmCtlOnBar = false; static int filmCtlDown = -1; static uint32_t filmTapSeen = 0, filmPosMs = 0;
static int32_t filmSeekWant = -1; static bool filmSeekHeld = false;   // the frame the slider asks for (-1: none) - the picture follows it - and a finger on it
static uint16_t *filmStrip = nullptr; static bool filmStripKept = false;
// (1.11.93, version 4) A page fading in: its picture, whole, kept here while the screen is blended into it a step a frame.
// The film kit used to send each step as a whole picture, eight a page change; the screen now makes them itself.
static uint16_t *filmFadeTo = nullptr;
static int32_t filmFadeK = -1; static uint32_t filmFadeN = 0, filmFadeShown = 0;   // its frame (-1: no fade), the fade's frames, how much of it the screen shows (of 256)
static std::string filmSound;                                      // (1.11.93) the film's sound: <name>.ima, or the 16-bit <name>.wav of before
static uint32_t filmAwakeAt = 0;                                   // when the main board was last told someone is watching
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
static int filmReadFile(const char *path, std::string &list, ldrcfilm::Entry *out) {   // a list's lines "<NAME>: <title>", those whose film is on the card
    list.clear(); int count = 0;
    File l = SD.open(path); if (l) { while (l.available() && list.size() < 16384) list += (char) l.read(); l.close(); }
    static ldrcfilm::Entry all[FILM_MAX * 2]; const int n = ldrcfilm::parseFilms(list.c_str(), all, FILM_MAX * 2);
    for (int i = 0; i < n && count < FILM_MAX; ++i) {
        const std::string film = std::string("/hmi/films/") + all[i].name + ".ldf";
        if (SD.exists(film.c_str())) out[count++] = all[i];
    }
    return count;
}
static void filmReadList() {                                     // the menu's films (films.txt) and (1.11.94) the problems (problems.txt)
    filmCount = filmProbCount = 0; filmListText.clear();
    if (!sdOk) return;
    filmCount = filmReadFile("/hmi/films/films.txt", filmListText, filmList);
    std::string problems; filmProbCount = filmReadFile("/hmi/films/problems.txt", problems, filmProb);
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
    { TopDraw td; filmBevel(FILM_BTN_X, FILM_BTN_Y, FILM_BTN_W, FILM_BTN_H, down, "Animation"); }
    filmBtnDrawnDown = down;
    dirty(FILM_BTN_X, FILM_BTN_Y, FILM_BTN_W, FILM_BTN_H); touchPainted = true;
}
static void filmDrawFix(bool down) {                             // (1.11.94) the help page's "Fix problems", top right
    if (!topReady()) return;
    { TopDraw td; filmBevel(FILM_FIX_X, FILM_BTN_Y, FILM_FIX_W, FILM_BTN_H, down, "Fix problems"); }
    dirty(FILM_FIX_X, FILM_BTN_Y, FILM_FIX_W, FILM_BTN_H); touchPainted = true;
}
static void filmButtonShow() {                                   // the help page's buttons: Animation (its own film), Fix problems (1.11.94): either or both
    if (!topReady()) return;
    filmBtnOwn = filmHas; filmBtnFix = filmProbCount > 0;
    if (!filmBtnOwn && !filmBtnFix) return;
    topY = FILM_BTN_Y; topH = FILM_BTN_H; top2X = 0; top2W = 0;
    if (filmBtnOwn) { topX = FILM_BTN_X; topW = FILM_BTN_W; if (filmBtnFix) { top2X = FILM_FIX_X; top2W = FILM_FIX_W; } }   // (two stretches of the layer: the title between them stays the page's)
    else { topX = FILM_FIX_X; topW = FILM_FIX_W; }
    topWho = FILM_BTN_WHO; topOn = true;
    if (filmBtnOwn) filmDrawButton(false);
    if (filmBtnFix) filmDrawFix(false);
}
static void filmButtonHide() {
    if (filmButtonUp()) { topOn = false; topWho = 0; dirty(FILM_BTN_X, FILM_BTN_Y, FILM_BTN_W, FILM_BTN_H); dirty(FILM_FIX_X, FILM_BTN_Y, FILM_FIX_W, FILM_BTN_H); touchPainted = true; }
    filmBtnHeld = false; top2W = 0;
}

// ------------------------------------------------------------------ the films menu (1.11.87): the help page's look - its title bar, its navy card - and the pages' buttons
static int filmMenuCount() { return filmMenuList ? filmProbCount : filmCount; }   // (1.11.94) the list shown: the problems, or every animation
static const ldrcfilm::Entry &filmMenuEntry(int i) { return filmMenuList ? filmProb[i] : filmList[i]; }
static bool filmMenuSwaps() { return filmMenuList || filmProbCount > 0; }   // (the other list's button: in the problems list always; in the list of them all while there are problems)
static int filmMenuPages() { return filmMenuCount() > FILM_PER_PAGE ? (filmMenuCount() + FILM_PER_PAGE - 1) / FILM_PER_PAGE : 1; }
static void filmMenuRect(int i, int &x, int &y, int &w, int &h) {   // (1.11.91) the bottom row in the system pages' slots: the other list (1.11.94), < Previous, Next >, OK bottom right
    y = 414; w = 180; h = 52;
    if (i == FILM_OK) { x = 605; return; }
    if (i == FILM_SWAP) { x = 14; return; }
    if (i == FILM_NEXT) { x = 408; return; }
    if (i == FILM_PREV) { x = 211; return; }
    const int k = i % FILM_PER_PAGE; x = 40 + (k % 2) * 366; y = 68 + (k / 2) * 62; w = 354; h = 54;
}
static int filmMenuAt(int px, int py) {
    auto in = [&](int i) { int x, y, w, h; filmMenuRect(i, x, y, w, h); return px >= x && px < x + w && py >= y && py < y + h; };
    for (int i = filmMenuPage * FILM_PER_PAGE; i < filmMenuCount() && i < (filmMenuPage + 1) * FILM_PER_PAGE; ++i) if (in(i)) return i;
    if (in(FILM_OK)) return FILM_OK;
    if (filmMenuSwaps() && in(FILM_SWAP)) return FILM_SWAP;
    if (filmMenuPages() > 1) { if (in(FILM_PREV)) return FILM_PREV; if (in(FILM_NEXT)) return FILM_NEXT; }
    return -1;
}
static std::string filmMenuLabel(int i) { return i == FILM_OK ? "OK" : i == FILM_PREV ? "< Previous" : i == FILM_NEXT ? "Next >" : i == FILM_SWAP ? (filmMenuList ? "Animations" : "Fix problems") : std::string(filmMenuEntry(i).title); }
static void filmMenuDrawButton(int i, bool down) {
    int x, y, w, h; filmMenuRect(i, x, y, w, h);
    { TopDraw td; filmBevel(x, y, w, h, down, filmMenuLabel(i)); }
    dirty(x, y, w, h); touchPainted = true;
}
static void filmMenuDraw() {
    if (!topReady()) return;
    if (filmMenuPage >= filmMenuPages()) filmMenuPage = 0;
    {
        TopDraw td;
        gfx->fillRect(0, 0, W, 58, 2214);                         // the title bar, as the help page's
        gfx->fillRect(0, 58, W, H - 58, 4426);                    // its navy card
        const std::string title = filmMenuList ? "Fix problems" : "Animations";
        drawGlyphs((W - textWidth(0, title)) / 2, (58 - fontHeight(0)) / 2, 0, 0xFFFF, title);
        const std::string hint = "While an animation plays, tap it to pause.";
        drawGlyphs(40, 378 + (30 - fontHeight(2)) / 2, 2, 0xFFFF, topCut(hint, 2, 720));
        for (int i = filmMenuPage * FILM_PER_PAGE; i < filmMenuCount() && i < (filmMenuPage + 1) * FILM_PER_PAGE; ++i) { int x, y, w, h; filmMenuRect(i, x, y, w, h); filmBevel(x, y, w, h, false, filmMenuEntry(i).title); }
        int x, y, w, h; filmMenuRect(FILM_OK, x, y, w, h); filmBevel(x, y, w, h, false, "OK");
        if (filmMenuSwaps()) { filmMenuRect(FILM_SWAP, x, y, w, h); filmBevel(x, y, w, h, false, filmMenuLabel(FILM_SWAP)); }
        if (filmMenuPages() > 1) {
            for (int b : {FILM_PREV, FILM_NEXT}) { filmMenuRect(b, x, y, w, h); filmBevel(x, y, w, h, false, filmMenuLabel(b)); }
            char pg[24]; snprintf(pg, sizeof pg, "Page %d of %d", filmMenuPage + 1, filmMenuPages());   // (1.11.94: in the title bar, right - its old place, bottom left, is the other list's button)
            drawGlyphs(W - 20 - textWidth(2, pg), (58 - fontHeight(2)) / 2, 2, 0xFFFF, pg);
        }
    }
    dirty(0, 0, W, H); touchPainted = true;
}
static void filmMenuShowFilm(const std::string &name) {         // the list at the page that holds this animation (1.11.94: the problems list for a problem's)
    for (int pass = 0; pass < 2; ++pass) {
        for (int i = 0; i < filmMenuCount(); ++i) if (name == filmMenuEntry(i).name) { filmMenuPage = i / FILM_PER_PAGE; return; }
        if (!filmMenuSwaps()) return;
        filmMenuList = !filmMenuList; filmMenuPage = 0;
    }
}
static void filmMenuOpen(int list = 0) {                          // (1.11.94: list 1, the problems - the help page's "Fix problems")
    if (!topReady() || !(list ? filmProbCount : filmCount)) return;
    filmMenuList = list; filmMenuPage = 0;
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
    const int barTop = filmStripKept && filmStrip ? FILM_BAR_Y : H;        // (1.11.89: paused, the slider moving the picture - under the bar it goes to what the bar keeps)
    int x0 = W, x1 = -1;
    for (int r = 0; r < p->iHeight && y + r < H; ++r) {
        const uint16_t *src = p->pPixels + r * w;
        if (y + r >= barTop) { memcpy(filmStrip + (y + r - FILM_BAR_Y) * W + x, src, (size_t) n * 2); continue; }
        uint16_t *dst = topFb + (y + r) * W + x;
        int f, l; ldrcfilm::rowDiff(dst, src, n, f, l);
        if (l >= f) { memcpy(dst + f, src + f, (size_t) (l - f + 1) * 2); if (f < x0) x0 = f; if (l > x1) x1 = l; }
        psramPace(n);                                              // (1.11.116: a row read, and maybe written - paced on the twin, src/psram_pace.h)
    }
    if (x1 >= x0) dirty(x + x0, y, x1 - x0 + 1, std::min(p->iHeight, barTop - y));
    return 1;
}
// (1.11.93) A page to fade into: kept whole, not yet shown
static int filmDrawTo(JPEGDRAW *p) {
    if (!filmFadeTo) return 0;
    const int x = p->x, y = p->y, w = p->iWidth;
    if (x < 0 || x >= W) return 1;
    const int n = std::min(p->iWidthUsed > 0 ? p->iWidthUsed : w, W - x);
    for (int r = 0; r < p->iHeight && y + r < H; ++r) memcpy(filmFadeTo + (y + r) * W + x, p->pPixels + r * w, (size_t) n * 2);
    return 1;
}
// The screen moved a of 256 of the way to the page fading in (256: the page itself); only what changed is marked for the
// panel. Paused, under the bar, it is what the bar keeps that moves (as filmDraw does).
static void filmFadeMove(uint32_t a) {
    if (!filmFadeTo || !topFb || !a) return;
    const uint32_t t0 = micros();
    const int barTop = filmStripKept && filmStrip ? FILM_BAR_Y : H;
    int y0 = H, y1 = -1, x0 = W, x1 = -1;
    for (int y = 0; y < H; ++y) {                                  // (one pass: each pixel read once, written only if it moves)
        const uint16_t *to = filmFadeTo + y * W;
        uint16_t *dst = y >= barTop ? filmStrip + (y - FILM_BAR_Y) * W : topFb + y * W;
        int f = W, l = -1;
        for (int x = 0; x < W; ++x) {
            const uint16_t was = dst[x], want = to[x];
            if (was == want) continue;
            dst[x] = a >= 256 ? want : ldrcfilm::mix565(was, want, a);
            if (f == W) f = x;
            l = x;
        }
        if (l >= 0 && y < barTop) { if (y < y0) y0 = y; y1 = y; if (f < x0) x0 = f; if (l > x1) x1 = l; }
    }
    if (y1 >= y0) dirty(x0, y0, x1 - x0 + 1, y1 - y0 + 1);
    const uint32_t us = micros() - t0; filmFadeSteps++; if (us > filmFadeMax) filmFadeMax = us;
}
static void filmFadeEnd() { if (filmFadeK >= 0) { filmFadeMove(256); filmFadeK = -1; } }   // a fade not over: its page, whole, now
// Picture k on the screen. play (1.11.93): it is the film's turn for it, so a page that fades in (version 4) is kept whole and
// the screen blended into it a frame at a time (filmPoll); else - a jump, or no room for the page - it is drawn at once.
// (1.11.116) No fades: Malcolm, 24 Oct 2026: "in reality it jumps between screens and does not fade. Fading might be
// misunderstood by users." The films keep their fade lengths (version 4); the screen cuts at the fade's first frame - the
// moment the real one changes.
static const bool FILM_FADES = false;
static bool filmDecode(int32_t k, bool play = false) {
    const uint32_t off = ldrcfilm::rd32(filmTable + 8 * k), size = ldrcfilm::sizeOf(filmTable, k);
    if (!size || size > filmBufSize || !filmFile.seek(off) || filmFile.read(filmBuf, size) != (int) size) return false;
    uint16_t rx, ry, rw, rh; uint32_t jo;                     // (version 2: only the rectangle that changed, drawn where it belongs)
    if (!ldrcfilm::pictureAt(filmBuf, size, filmHead, rx, ry, rw, rh, jo)) return false;
    filmFadeEnd();                                              // (1.11.93: what comes next is drawn on the whole page)
    const uint32_t n = play && FILM_FADES ? ldrcfilm::fadeOf(filmTable, k) : 0;
    const bool whole = rx == 0 && ry == 0 && rw == W && rh == H;
    if (n && whole && !filmFadeTo) filmFadeTo = (uint16_t *) ps_malloc((size_t) W * H * 2);
    const bool fade = n && whole && filmFadeTo;
    const uint32_t t0 = micros();
    bool ok = filmJpeg.openRAM(filmBuf + jo, (int) (size - jo), fade ? filmDrawTo : filmDraw) != 0;
    if (ok) { filmJpeg.setPixelType(RGB565_LITTLE_ENDIAN); ok = filmJpeg.decode(rx, ry, 0) != 0; filmJpeg.close(); }
    const uint32_t us = micros() - t0; filmDecodeUs = us; if (us > filmDecodeMax) filmDecodeMax = us; filmPictures++;
    if (ok && fade) { filmFadeK = k; filmFadeN = n; filmFadeShown = 0; }
    return ok;
}

static void filmStop(bool toMenu = false) {
    if (filmPlaying && audioId == FILM_AUDIO_ID) audioStop();
    filmPlaying = false; filmPaused = false; filmCtlHeld = false; filmCtlDown = -1; filmStripKept = false; filmSeekWant = -1; filmSeekHeld = false;
    filmFadeK = -1; free(filmFadeTo); filmFadeTo = nullptr;        // (1.11.93: 750 kB back)
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
    uint32_t biggest = 0, extra = 0;
    if (!filmTable || filmFile.read(filmTable, 8 * filmHead.frames) != (int) (8 * filmHead.frames)) { filmFile.close(); return false; }
    free(filmSections); filmSections = nullptr; filmSectionCount = 1;
    if (filmHead.version >= 3) {                                  // (the sections, after the table)
        uint8_t nb[4];
        if (filmFile.read(nb, 4) != 4) { filmFile.close(); return false; }
        const uint32_t n = ldrcfilm::rd32(nb);
        if (n == 0 || n > ldrcfilm::MAX_SECTIONS || !(filmSections = (uint8_t *) ps_malloc(4 * n)) || filmFile.read(filmSections, 4 * n) != (int) (4 * n) || !ldrcfilm::sectionsSound(filmSections, n, filmHead)) { filmFile.close(); return false; }
        filmSectionCount = n; extra = 4 + 4 * n;
    }
    if (!ldrcfilm::tableSound(filmTable, filmHead, fileSize, biggest, extra)) { filmFile.close(); return false; }
    if (biggest > filmBufSize) { free(filmBuf); filmBuf = (uint8_t *) ps_malloc(biggest); filmBufSize = filmBuf ? biggest : 0; }
    if (!filmBuf) { filmFile.close(); return false; }
    filmBtnHeld = false;
    topX = 0; topY = 0; topW = W; topH = H; topWho = FILM_WHO; topOn = true;
    filmLast = -1; filmPictures = filmSkipped = 0; filmDecodeMax = 0; filmFadeSteps = filmFadeMax = 0; filmPlaying = true;
    filmPaused = false; filmTapDeaf = false; filmCtlHeld = false; filmCtlDown = -1; filmStripKept = false; filmSeekWant = -1; filmSeekHeld = false;
    if (!filmDecode(0)) { filmStop(); return false; }          // the first picture before the sound, so they start together
    dirty(0, 0, W, H); touchPainted = true;                    // (1.11.94) all of it shown: only what differed from the layer's old picture was marked, and the help page showed through the rest
    filmLast = 0;
    filmSound = filmPath(".ima"); if (!SD.exists(filmSound.c_str())) filmSound = filmPath(".wav");   // (1.11.93) the compressed sound, else the 16-bit one
    audioStartFile(filmSound.c_str());
    filmStartMs = millis();
    return true;
}
static const uint8_t *filmSecs() { return filmSections ? filmSections : filmOneSection; }
static void filmCtlRect(int i, int &x, int &y, int &w, int &h) { x = 211 + i * 197; y = FILM_CTL_Y; w = 180; h = 52; }   // (slots x 211, 408, 605)
static int filmCtlAt(int px, int py) { for (int i = 0; i < FILM_CTL_N; ++i) { int x, y, w, h; filmCtlRect(i, x, y, w, h); if (px >= x && px < x + w && py >= y && py < y + h) return i; } return -1; }
static void filmDrawCtl(int i, bool down) {
    static const char *const label[FILM_CTL_N] = {"Play", "Animations", "Exit"};
    int x, y, w, h; filmCtlRect(i, x, y, w, h);
    { TopDraw td; filmBevel(x, y, w, h, down, label[i]); }
    dirty(x, y, w, h); touchPainted = true;
}
static uint32_t filmFrameMs(int32_t f) { return (uint32_t) ((uint64_t) (f < 0 ? 0 : f) * 1000 / (filmHead.fps ? filmHead.fps : 1)); }
static int32_t filmShownFrame() {                                  // the paused film's frame: the slider's, or where it was paused
    if (filmSeekWant >= 0) return filmSeekWant;
    const int32_t f = ldrcfilm::frameAt(filmPosMs, filmHead); return f < 0 ? (int32_t) filmHead.frames - 1 : f;
}
static void filmDrawSeek() {                                       // (1.11.89) the slider's row: the time there, the track and its parts, the knob, the length
    const int32_t at = filmShownFrame();
    const int kx = ldrcfilm::seekX(at, FILM_SEEK_X0, FILM_SEEK_W, filmHead.frames), top = FILM_BAR_Y + 2, h = FILM_CTL_Y - 3 - top;   // (below the bar's top line)
    char here[8], len[8]; ldrcfilm::clockText(filmFrameMs(at), here); ldrcfilm::clockText(ldrcfilm::lengthMs(filmHead), len);
    {
        TopDraw td;
        gfx->fillRect(0, top, W, h, 2214);
        drawGlyphs(FILM_SEEK_X0 - 18 - textWidth(2, here), FILM_SEEK_MID - fontHeight(2) / 2, 2, 0xFFFF, here);
        drawGlyphs(FILM_SEEK_X0 + FILM_SEEK_W + 18, FILM_SEEK_MID - fontHeight(2) / 2, 2, 0xFFFF, len);
        gfx->fillRoundRect(FILM_SEEK_X0, FILM_SEEK_MID - 4, FILM_SEEK_W, 9, 4, 0x8410);                                   // the track
        if (kx > FILM_SEEK_X0) gfx->fillRoundRect(FILM_SEEK_X0, FILM_SEEK_MID - 4, kx - FILM_SEEK_X0 + 4, 9, 4, 0x5D9F);   // and the part played
        for (uint32_t s = 1; s < filmSectionCount; ++s) {          // a gap where each part starts: where Back and Next go
            const int gx = ldrcfilm::seekX((int32_t) ldrcfilm::rd32(filmSecs() + 4 * s), FILM_SEEK_X0, FILM_SEEK_W, filmHead.frames);
            gfx->fillRect(gx - 1, FILM_SEEK_MID - 5, 3, 11, 2214);
        }
        gfx->fillCircle(kx, FILM_SEEK_MID, FILM_SEEK_R, 0xFFFF);
    }
    dirty(0, top, W, h); touchPainted = true;
}
static void filmPause() {                                          // the film held where it is; the bar drawn over its foot (what lay there kept)
    const uint32_t len = ldrcfilm::lengthMs(filmHead);
    filmPosMs = std::min((uint32_t) (millis() - filmStartMs), len);
    if (audioId == FILM_AUDIO_ID) audioStop();
    if (!filmStrip) filmStrip = (uint16_t *) ps_malloc((size_t) W * FILM_BAR_H * 2);
    if (filmStrip) { memcpy(filmStrip, topFb + FILM_BAR_Y * W, (size_t) W * FILM_BAR_H * 2); filmStripKept = true; }
    filmSeekWant = -1; filmSeekHeld = false;
    { TopDraw td; gfx->fillRect(0, FILM_BAR_Y, W, FILM_BAR_H, 2214); gfx->fillRect(0, FILM_BAR_Y, W, 2, 0x8410); }   // (a line along its top: the bar apart from the film)
    filmDrawSeek();
    for (int i = 0; i < FILM_CTL_N; ++i) filmDrawCtl(i, false);
    dirty(0, FILM_BAR_Y, W, FILM_BAR_H); touchPainted = true;
    filmPaused = true;
}
static void filmBarDown() {                                        // the bar gone: what lay under it - kept, and kept up to date while paused - back
    if (filmStripKept) { memcpy(topFb + FILM_BAR_Y * W, filmStrip, (size_t) W * FILM_BAR_H * 2); filmStripKept = false; dirty(0, FILM_BAR_Y, W, FILM_BAR_H); touchPainted = true; }
}
static void filmPlayFrom(uint32_t ms) {                            // the sound and the clock from ms
    filmPosMs = ms; audioStartFile(filmSound.c_str(), ms);
    filmStartMs = millis() - ms; filmPaused = false;
}
static bool filmSeekStep(uint32_t budgetMs) {                      // (1.11.89) the picture nearer the slider's frame, for at most budgetMs; false: the film could not be read (stopped)
    const uint32_t t0 = millis();
    while (filmSeekWant >= 0 && filmLast != filmSeekWant) {
        const int32_t k = ldrcfilm::seekStep(filmSeekWant, filmLast, filmTable, filmHead.version);
        if (k < 0) { filmLast = filmSeekWant; break; }
        if (!filmDecode(k)) { filmStop(filmFromList); return false; }
        filmLast = k;
        if (millis() - t0 >= budgetMs) break;
    }
    return true;
}
static void filmSeekTo(int x) {                                    // the slider at x: the time and the knob at once; the picture as fast as it decodes (filmPoll)
    const int32_t f = ldrcfilm::seekFrame(x, FILM_SEEK_X0, FILM_SEEK_W, filmHead.frames);
    if (f == filmSeekWant) return;
    filmSeekWant = f; filmPosMs = filmFrameMs(f);
    filmDrawSeek();
}
static void filmResume() {
    while (filmSeekWant >= 0 && filmLast != filmSeekWant) if (!filmSeekStep(1000)) return;   // (the slider's frame complete before the film goes on)
    filmSeekWant = -1;
    filmBarDown();
    filmPlayFrom(filmPosMs);
}
static bool filmInSeekZone(int x, int y) { return y >= FILM_BAR_Y - 12 && y < FILM_CTL_Y - 2 && x >= FILM_SEEK_X0 - 30 && x <= FILM_SEEK_X0 + FILM_SEEK_W + 30; }
static void filmTouch(bool pressed, int x, int y, uint32_t now) {
    if (filmTapDeaf) { if (pressed) filmTapSeen = now; else if (now - filmTapSeen >= 80) filmTapDeaf = false; return; }   // (the finger that paused it)
    if (!filmPaused) { if (pressed) { filmPause(); filmTapDeaf = true; filmTapSeen = now; } return; }
    if (pressed) {                                                 // paused: the slider, the bar's buttons
        filmTapSeen = now;
        if (filmSeekHeld) { filmSeekTo(x); return; }               // (the knob follows the finger, wherever it wanders)
        if (!filmCtlHeld) {
            if (filmInSeekZone(x, y)) { filmSeekHeld = true; filmSeekTo(x); return; }
            filmCtlHeld = true; filmCtlDown = filmCtlAt(x, y); filmCtlOnBar = y >= FILM_BAR_Y;
            if (filmCtlDown >= 0) filmDrawCtl(filmCtlDown, true);
        }
        return;
    }
    if (filmSeekHeld) { if (now - filmTapSeen >= 80) filmSeekHeld = false; return; }   // (let go: still paused, at that moment)
    if (!filmCtlHeld || now - filmTapSeen < 80) return;
    filmCtlHeld = false;
    const int c = filmCtlDown; filmCtlDown = -1;
    if (c >= 0) filmDrawCtl(c, false);
    if (c == FILM_CTL_FILMS) { filmMenuShowFilm(filmName); filmStop(true); filmMenuDeaf = false; }   // (1.11.91) the list of them all, at this one's page
    else if (c == FILM_CTL_EXIT) filmStop(false);                  // (1.11.90) out of the films: the help page, as it was
    else if (c == FILM_CTL_PLAY || !filmCtlOnBar) filmResume();   // Play, or a tap on the picture: on from where it is
}   // (a tap on the bar between its buttons: nothing)
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
    if (i == FILM_PREV || i == FILM_NEXT) { const int n = filmMenuPages(); filmMenuPage = (filmMenuPage + (i == FILM_NEXT ? 1 : n - 1)) % n; filmMenuDraw(); return; }   // (round: Next from the last page is the first)
    if (i == FILM_SWAP) { filmMenuList = !filmMenuList; filmMenuPage = 0; filmMenuDraw(); return; }   // (1.11.94) the other list
    filmFromList = true;
    if (i < filmMenuCount()) { const std::string name = filmMenuEntry(i).name; if (!filmStartName(name.c_str()) && !filmUp()) filmMenuDraw(); }   // (a film that will not play: the menu stays)
}
static void filmButtonCancel() { if (filmBtnHeld) { filmBtnHeld = false; if (filmButtonUp()) { if (filmBtnWhich) filmDrawFix(false); else filmDrawButton(false); } } }   // (a corner held on it: radios or the door, not the film)

// The help page's button: true while it has the finger (the page underneath sees none of it)
static bool filmButtonTouch(bool pressed, int x, int y, uint32_t now) {
    if (filmBtnHeld) {
        if (pressed) { filmBtnSeen = now; return true; }
        if (now - filmBtnSeen < 80) return true;              // (a sample the touch chip dropped is not a lift)
        filmBtnHeld = false;
        if (!filmButtonUp()) return true;
        if (filmBtnWhich) { filmDrawFix(false); filmAwakeAt = 0; filmMenuOpen(1); return true; }   // (1.11.94) the problems list
        filmDrawButton(false); filmFromList = false; filmAwakeAt = 0; if (!filmStartName(filmOwn.c_str()) && !filmUp()) filmButtonShow();   // (1.11.91) this help page's own animation (1.11.88: the main board told at once that someone is here)
        return true;
    }
    if (!pressed || !filmButtonUp() || y < FILM_BTN_Y || y >= FILM_BTN_Y + FILM_BTN_H) return false;
    const bool own = filmBtnOwn && x >= FILM_BTN_X && x < FILM_BTN_X + FILM_BTN_W, fix = filmBtnFix && x >= FILM_FIX_X && x < FILM_FIX_X + FILM_FIX_W;
    if (!own && !fix) return false;
    filmBtnHeld = true; filmBtnWhich = fix ? 1 : 0; filmBtnSeen = now;
    if (fix) filmDrawFix(true); else filmDrawButton(true);
    return true;
}

static void filmPoll() {
    const uint32_t now = millis();
    const bool helpPage = page.name == "LogView";
    if ((filmPlaying || filmMenuUp()) && (!filmAwakeAt || now - filmAwakeAt >= 15000)) {   // (1.11.88) the main board's screen timeout waits: someone is watching (Teensy B123)
        filmAwakeAt = now ? now : 1; flushOut(); Serial.write((const uint8_t *) "LDRCAWAKE", 9);
    }
    if (filmPlaying) {
        if (!filmUp() || !filmAllowed() || !helpPage) { filmStop(false); return; }   // (another page of ours took the layer; the safety off or the motor on; the page went)
        if (filmPaused) { if (filmSeekWant >= 0 && filmSeekWant != filmLast) filmSeekStep(25); return; }   // (1.11.89: the picture follows the slider)
        const uint32_t ms = now - filmStartMs;
        const int32_t want = ldrcfilm::frameAt(ms, filmHead) < 0 ? (int32_t) filmHead.frames - 1 : ldrcfilm::frameAt(ms, filmHead);
        if (filmFadeK >= 0) {                                      // (1.11.93) a page fading in: as far as this frame's share of it
            const uint32_t share = ldrcfilm::fadeShare(want - filmFadeK, filmFadeN);
            if (share >= 256) filmFadeEnd();
            else if (share > filmFadeShown) { filmFadeMove(ldrcfilm::fadeStepOf(filmFadeShown, share)); filmFadeShown = share; }
        }
        // From version 2 every picture is decoded in its turn, however late (a changed rectangle skipped would leave the old
        // finger drawn where it was - Malcolm: "the indication of the pointer hitting a button was frequently rather
        // inaccurate"); the sound runs on, and the pictures catch up while the voice speaks over a still page.
        const int32_t k = filmHead.version >= 2 ? ldrcfilm::nextPicture(want, filmLast, filmTable) : ldrcfilm::pictureFor(want, filmLast, filmTable);
        if (k >= 0) {
            if (filmHead.version < 2) { for (int32_t i = filmLast + 1; i < k; ++i) if (ldrcfilm::sizeOf(filmTable, i)) filmSkipped++; }
            else if ((want - k) * 1000 > 300 * (int32_t) filmHead.fps) filmSkipped++;   // (version 2 on: a picture shown more than 0.3 s late)
            if (!filmDecode(k, true)) { filmStop(); return; }
            filmLast = k;
        } else if (ms >= ldrcfilm::lengthMs(filmHead) + 700) { filmStop(filmFromList); return; }   // the end: every picture shown, the last held a moment; then back where it was started (1.11.91: the list, or the help page)
        return;
    }
    if (filmMenuUp()) { if (!helpPage || !filmAllowed()) filmMenuClose(); return; }   // (the menu: the help page gone, or the motor could run)
    // the button: on a help page (one a recent Help tap opened - not the log viewer) that has an animation of its own on the card, while the motor is safe
    if (!helpPage) { filmLatched = false; if (filmButtonUp()) filmButtonHide(); if (!filmTopic.empty() && now - filmTopicAt > FILM_HELP_WINDOW_MS) filmTopic.clear(); return; }
    if (!filmLatched) {
        if (filmTopic.empty() || now - filmTopicAt > FILM_HELP_WINDOW_MS) return;
        filmLatched = true; filmMenuList = 0;                      // (1.11.94: a new help page's list starts as the list of them all)
        filmReadList();                                            // (1.11.87) the list of them all
        char own[16]; ldrcfilm::filmFor(filmListText.c_str(), filmTopic.c_str(), own, sizeof own);   // (1.11.91) this help page's own: its name, or films.txt's "<HELP>=<NAME>"
        filmOwn = own; filmHas = !filmOwn.empty() && SD.exists(("/hmi/films/" + filmOwn + ".ldf").c_str());
    }
    const bool want = (filmHas || filmProbCount > 0) && filmAllowed() && (!topOn || topWho == FILM_BTN_WHO);   // (1.11.94: Fix problems on every help page)
    if (want && !filmButtonUp()) filmButtonShow();
    else if (!want && filmButtonUp()) filmButtonHide();
}
