#!/usr/bin/env python3
"""The films' flow on the Mac (screen 1.11.87): src/film_device.h itself - the Films button, the menu, a film playing and
stopping - compiled with a stand-in screen (touch, clock, card = this project's sd folder, layer, sound) and the real
decoder (JPEGDEC from .pio/libdeps), and driven as a pilot would: Help, Films, a film, a tap, OK; the safety off; the
page gone; a film's end.
   python3 hmi/test_film/flow_test.py"""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
LIB = os.path.join(ROOT, '.pio', 'libdeps', 'ota', 'JPEGDEC', 'src')
if not os.path.isdir(LIB): sys.exit('JPEGDEC not found in .pio/libdeps/ota (build the screen once: pio run -e ota)')
PROG = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cctype>
#include <string>
#include <vector>
#include <algorithm>
#include <JPEGDEC.h>
static const int W = 800, H = 480;
static uint32_t nowMs = 1000;
static uint32_t millis() { return nowMs; }
static uint32_t micros() { return nowMs * 1000; }
static void *ps_malloc(size_t n) { return malloc(n); }
static std::string SDROOT = "@SD@";
struct File {
    FILE *fp = nullptr; long sz = 0;
    explicit operator bool() const { return fp != nullptr; }
    long size() { return sz; }
    int read(uint8_t *b, size_t n) { return fp ? (int) fread(b, 1, n, fp) : -1; }
    int read() { int c = fp ? fgetc(fp) : -1; return c; }
    int available() { if (!fp) return 0; long p = ftell(fp); return p < sz ? (int) (sz - p) : 0; }
    bool seek(uint32_t p) { return fp && fseek(fp, (long) p, SEEK_SET) == 0; }
    void close() { if (fp) fclose(fp); fp = nullptr; }
};
struct SDClass {
    File open(const char *p) { File f; f.fp = fopen((SDROOT + p).c_str(), "rb"); if (f.fp) { fseek(f.fp, 0, SEEK_END); f.sz = ftell(f.fp); fseek(f.fp, 0, SEEK_SET); } return f; }
    bool exists(const char *p) { FILE *f = fopen((SDROOT + p).c_str(), "rb"); if (f) fclose(f); return f != nullptr; }
} SD;
static bool sdOk = true, touchPainted = false;
static bool topOn = false; static int topWho = 0, topX = 0, topY = 0, topW = 0, topH = 0;
static uint16_t *topFb = nullptr;
static bool topReady() { if (!topFb) topFb = (uint16_t *) calloc(W * H, 2); return true; }
struct FakeGfx { void fillRect(int x, int y, int w, int h, uint16_t c) { for (int j = y; j < y + h && j < H; ++j) for (int i = x; i < x + w && i < W; ++i) topFb[j * W + i] = c; }
                 void drawFastHLine(int x, int y, int w, uint16_t c) { fillRect(x, y, w, 1, c); } void drawFastVLine(int x, int y, int h, uint16_t c) { fillRect(x, y, 1, h, c); }
                 void fillRoundRect(int x, int y, int w, int h, int, uint16_t c) { fillRect(x, y, w, h, c); }
                 void fillCircle(int cx, int cy, int r, uint16_t c) { for (int j = -r; j <= r; ++j) for (int i = -r; i <= r; ++i) if (i * i + j * j <= r * r) fillRect(cx + i, cy + j, 1, 1, c); } } fakeGfx, *gfx = &fakeGfx;
struct TopDraw { TopDraw() {} };
static std::vector<std::string> texts;
static void drawGlyphs(int, int, int, uint16_t, const std::string &s) { texts.push_back(s); }
static int textWidth(int, const std::string &s) { return (int) s.size() * 14; }
static int fontHeight(int) { return 28; }
static std::string topCut(const std::string &s, int, int) { return s; }
static uint16_t shade(uint16_t c, int) { return c; }
static long dirtied = 0; static void dirty(int, int, int w, int h) { dirtied += (long) w * h; }
struct Page { std::string name = "FrontView"; } page;
static int flying = 0; static int flyingNow() { return flying; }
static const int FILM_AUDIO_ID = -2; static int audioId = -1; static std::string audioPath; static uint32_t audioFrom = 0;
static void audioStartFile(const char *p, uint32_t fromMs = 0) { audioId = FILM_AUDIO_ID; audioPath = p; audioFrom = fromMs; }
static std::string sentToTeensy; static void flushOut() {}
struct FakeSerial { size_t write(const uint8_t *b, size_t n) { sentToTeensy.append((const char *) b, n); return n; } } Serial;
static int awakes() { int n = 0; size_t at = 0; while ((at = sentToTeensy.find("LDRCAWAKE", at)) != std::string::npos) { ++n; at += 9; } return n; }
static void audioStop() { audioId = -1; audioPath.clear(); }
static uint32_t filmDecodeUs = 0, filmDecodeMax = 0, filmPictures = 0, filmSkipped = 0;
#include "@DEV@"
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void run(uint32_t ms) { for (uint32_t t = 0; t < ms; t += 10) { nowMs += 10; filmPoll(); } }
// a finger on the screen, as main.cpp's pollTouch hands it out: the film or the menu when they have the screen; the button otherwise
static void finger(bool pressed, int x, int y) {
    if (filmUp()) filmTouch(pressed, x, y, nowMs);
    else if (filmMenuUp()) filmMenuTouch(pressed, x, y, nowMs);
    else filmButtonTouch(pressed, x, y, nowMs);
}
static void tap(int x, int y) { for (int i = 0; i < 8; ++i) { finger(true, x, y); nowMs += 10; filmPoll(); } for (int i = 0; i < 12; ++i) { finger(false, 0, 0); nowMs += 10; filmPoll(); } }
static int filmIndex(const char *name) { for (int i = 0; i < filmCount; ++i) if (!strcmp(filmList[i].name, name)) return i; return -1; }
static void pickFilm(const char *name) {                    // (the list is up) turn to its page, tap it
    const int i = filmIndex(name); if (i < 0) return;
    for (int g = 0; g < 12 && filmMenuPage != i / FILM_PER_PAGE; ++g) { int x, y, w, h; filmMenuRect(FILM_NEXT, x, y, w, h); tap(x + w / 2, y + h / 2); }
    int x, y, w, h; filmMenuRect(i, x, y, w, h); tap(x + w / 2, y + h / 2);
}
static void helpTap(const char *topic) { std::string s = std::string("print \"HelpView:") + topic + ".TXT\"\nLogView.t0.txt=\"x\""; filmNoteHelp(s); nowMs += 50; page.name = "LogView"; }
int main() {
    // 1. (1.11.91) Help on a page with an animation of its own: "Animation" at its top left; the list (films.txt's, those on the card) read
    page.name = "EasyView"; run(100); CHECK(!filmButtonUp());
    texts.clear(); helpTap("EASY"); run(100);
    CHECK(filmButtonUp() && filmOwn == "EASY" && filmCount >= 3);
    CHECK(filmIndex("CALIB") >= 0 && filmIndex("CURVES") > filmIndex("CALIB") && filmIndex("EASY") > filmIndex("CURVES"));   // (films.txt's order)
    { bool lab = false; for (auto &s : texts) if (s == "Animation") lab = true; CHECK(lab); }
    // 1b. a help page with none of its own: no button
    page.name = "FrontView"; run(5000); helpTap("NOSUCH"); run(100); CHECK(!filmButtonUp() && filmOwn == "NOSUCH" && !filmHas);   // (a help page with no animation of its own: since 17 Oct every real one has one)
    page.name = "FrontView"; run(5000); helpTap("FRONT"); run(100); CHECK(filmButtonUp() && filmOwn == "FRONT");
    // 2. the log viewer (the same page, no Help tap): no button
    page.name = "FrontView"; run(5000); page.name = "LogView"; run(200); CHECK(!filmButtonUp());
    // 3. the Rotorflight menu's help (films.txt: RFLIGHT=EASY): its button plays Easy tuning's at once - no list - and the main
    // board is told at once that someone is watching (its screen timeout waits), then every 15 s
    page.name = "EasyView"; run(100); helpTap("EASY"); run(100); CHECK(filmButtonUp() && filmOwn == "EASY");   // (Easy tuning's help; RFLIGHT has its own animation since 17 Oct)
    sentToTeensy.clear();
    tap(80, 30); run(50); CHECK(filmUp() && filmPlaying && filmName == "EASY" && !filmMenuUp() && !filmFromList);
    CHECK(awakes() == 1);
    run(31000); CHECK(awakes() == 3);
    // 3b. paused: the bar's "Animations" opens the list of them all, at this one's page, with its title and hint
    texts.clear(); tap(400, 200); run(50); CHECK(filmPaused);
    { bool lab = false; for (auto &s : texts) if (s == "Animations") lab = true; CHECK(lab); }
    { int fx, fy, fw, fh; filmCtlRect(FILM_CTL_FILMS, fx, fy, fw, fh); texts.clear(); tap(fx + fw / 2, fy + fh / 2); run(50); }
    CHECK(filmMenuUp() && !filmPlaying && filmMenuPage == filmIndex("EASY") / FILM_PER_PAGE && filmMenuPages() == (filmCount + FILM_PER_PAGE - 1) / FILM_PER_PAGE);
    { bool title = false, hint = false; for (auto &s : texts) { if (s == "Animations") title = true; if (s.rfind("While an animation plays", 0) == 0) hint = true; } CHECK(title && hint); }
    // 4. a tap on nothing: nothing; on the second: it plays, with its sound from the start
    tap(300, 30); run(50); CHECK(filmMenuUp());
    int x, y, w, h;
    pickFilm("CURVES"); run(50);
    CHECK(filmUp() && filmPlaying && filmFromList && !filmPaused && filmName == "CURVES" && audioId == FILM_AUDIO_ID && audioPath == "/hmi/films/CURVES.wav" && audioFrom == 0 && filmPictures >= 1);
    CHECK(filmHead.version == 3 && filmSectionCount >= 10);
    run(3000); CHECK(filmPlaying && filmPictures == 1);   // (the title card: still, nothing new to decode)
    run(9000); CHECK(filmPlaying && filmPictures > 1 && filmLast > 0);
    // 5. never a picture skipped, however late: the clock jumps 10 s at once, and every picture in between is decoded in turn
    {
        const uint32_t before = filmPictures; const int32_t from = filmLast;
        nowMs += 10000; filmStartMs -= 0;                  // (the screen held up for 10 s)
        const int32_t want = ldrcfilm::frameAt(nowMs - filmStartMs, filmHead);
        int due = 0; for (int32_t i = from + 1; i <= want; ++i) if (ldrcfilm::sizeOf(filmTable, i)) ++due;
        for (int i = 0; i < 400 && filmLast < want; ++i) filmPoll();   // (no time passing: one picture a pass)
        int decoded = (int) (filmPictures - before);
        CHECK(due > 3 && decoded == due);
        printf("10 s late: %d pictures due, %d decoded in turn (none skipped)\n", due, decoded);
    }
    // 6. a tap pauses: the sound stops, the bar along the foot; that same tap presses nothing (it lands where Play is drawn)
    { const uint32_t awakeBefore = awakes(); int px, py, pw, ph; filmCtlRect(FILM_CTL_PLAY, px, py, pw, ph);
      tap(px + pw / 2, py + ph / 2); run(50);
      CHECK(filmPlaying && filmPaused && audioId == -1 && filmStripKept);
      const uint32_t posAtPause = filmPosMs; const int32_t lastAtPause = filmLast;
      run(20000); CHECK(filmPaused && filmLast == lastAtPause && awakes() > (int) awakeBefore);   // (held still; the main board still told)
      // 7. Play: on from where it was, the sound from there too, what lay under the bar put back
      tap(px + pw / 2, py + ph / 2); run(50);
      CHECK(!filmPaused && audioId == FILM_AUDIO_ID && audioFrom == posAtPause && !filmStripKept);
    }
    // 8. (1.11.90) the bar's buttons: Play, Films, Exit in the system pages' last three slots, Exit bottom right
    { int x0, y0, w0, h0, x2, y2, w2, h2; filmCtlRect(FILM_CTL_PLAY, x0, y0, w0, h0); filmCtlRect(FILM_CTL_EXIT, x2, y2, w2, h2);
      CHECK(FILM_CTL_N == 3 && x0 == 211 && x2 == 605 && x2 + w2 == 785 && y2 + h2 <= H); }
    // 9b. (1.11.89) the slider. A finger on the track asks for the frame there: the knob and the time at once, the picture
    // follows while paused, the bar stays drawn over it; dragged back (the finger wandering off the track), the picture
    // follows back; let go, still paused there; a tap between the bar's buttons does nothing. Then Play: the sound from
    // that moment - and the picture is the very one a straight play to that moment draws.
    { run(1500); tap(400, 200); run(50); CHECK(filmPaused && filmStripKept && topFb[(FILM_BAR_Y + 2) * W + 3] == 2214);
      const int xa = FILM_SEEK_X0 + FILM_SEEK_W * 3 / 4, xb = FILM_SEEK_X0 + FILM_SEEK_W / 5;
      const int32_t fa = ldrcfilm::seekFrame(xa, FILM_SEEK_X0, FILM_SEEK_W, filmHead.frames), fb2 = ldrcfilm::seekFrame(xb, FILM_SEEK_X0, FILM_SEEK_W, filmHead.frames);
      texts.clear(); finger(true, xa, FILM_SEEK_MID); nowMs += 10; filmPoll();
      CHECK(filmSeekHeld && filmSeekWant == fa && filmPaused);
      char clk[8]; ldrcfilm::clockText((uint32_t) ((uint64_t) fa * 1000 / filmHead.fps), clk);
      char len[8]; ldrcfilm::clockText(ldrcfilm::lengthMs(filmHead), len);
      bool timeShown = false, lenShown = false; for (auto &s : texts) { if (s == clk) timeShown = true; if (s == len) lenShown = true; }
      CHECK(timeShown && lenShown);
      for (int i = 0; i < 30; ++i) { finger(true, xa, FILM_SEEK_MID); nowMs += 10; filmPoll(); }
      CHECK(filmLast == fa && topFb[(FILM_BAR_Y + 2) * W + 3] == 2214);
      for (int x = xa; x >= xb; x -= 7) { finger(true, x, FILM_SEEK_MID + 40); nowMs += 10; filmPoll(); }
      for (int i = 0; i < 30; ++i) { finger(true, xb, FILM_SEEK_MID + 40); nowMs += 10; filmPoll(); }
      CHECK(filmSeekWant == fb2 && filmLast == fb2 && fb2 < fa);
      for (int i = 0; i < 12; ++i) { finger(false, 0, 0); nowMs += 10; filmPoll(); }
      CHECK(!filmSeekHeld && filmPaused && filmLast == fb2);
      int bx, by, bw, bh; filmCtlRect(FILM_CTL_PLAY, bx, by, bw, bh); tap(bx + bw + 8, by + bh / 2); run(50); CHECK(filmPaused);
      tap(100, by + bh / 2); run(50); CHECK(filmPaused);                // (the empty slot at the left: nothing either)
      std::vector<uint16_t> seen(topFb, topFb + W * H); memcpy(seen.data() + FILM_BAR_Y * W, filmStrip, (size_t) W * FILM_BAR_H * 2);
      int px, py, pw, ph; filmCtlRect(FILM_CTL_PLAY, px, py, pw, ph); tap(px + pw / 2, py + ph / 2);
      CHECK(!filmPaused && !filmStripKept && audioFrom == (uint32_t) ((uint64_t) fb2 * 1000 / filmHead.fps));
      const std::string name = filmName; CHECK(filmStartName(name.c_str()));
      while (ldrcfilm::frameAt(nowMs - filmStartMs, filmHead) < fb2) { nowMs += 10; filmPoll(); }
      for (int i = 0; i < 50; ++i) filmPoll();
      CHECK(memcmp(topFb, seen.data(), (size_t) W * H * 2) == 0);
      printf("slider: to frame %d and back to %d; the picture there the same as a straight play to it\n", (int) fa, (int) fb2);
    }
    // 10. (1.11.90) Exit: out of the films - no film, no menu - the help page as it was, its Films button back
    { tap(400, 200); run(50); CHECK(filmPaused);
      int ex, ey, ew, eh; filmCtlRect(FILM_CTL_EXIT, ex, ey, ew, eh); tap(ex + ew / 2, ey + eh / 2);
      CHECK(!filmPlaying && !filmUp() && !filmMenuUp() && audioId == -1);
      run(100); CHECK(filmButtonUp());
      tap(80, 30); run(300); tap(400, 200); run(50);                  // (the list again, for what follows: the page's own, paused, "Animations")
      { int fx, fy, fw, fh; filmCtlRect(FILM_CTL_FILMS, fx, fy, fw, fh); tap(fx + fw / 2, fy + fh / 2); run(50); }
      CHECK(filmMenuUp());
    }
    // 11. a film to its end: back to the menu
    pickFilm("EASY"); run(50); CHECK(filmPlaying && filmName == "EASY");
    const uint32_t len = ldrcfilm::lengthMs(filmHead); run(len + 1500);
    CHECK(!filmPlaying && filmMenuUp());
    printf("EASY played to its end: %u pictures shown, %u late\n", (unsigned) filmPictures, (unsigned) filmSkipped);
    // 12. "Animations" on the bar (one from the list): the list, at its page
    pickFilm("CALIB"); run(2000); tap(400, 200); run(50); CHECK(filmPaused && filmName == "CALIB");
    { int fx, fy, fw, fh; filmCtlRect(FILM_CTL_FILMS, fx, fy, fw, fh); tap(fx + fw / 2, fy + fh / 2); run(50); CHECK(!filmPlaying && filmMenuUp()); }
    // 13. OK: the help page again, its button back
    filmMenuRect(FILM_OK, x, y, w, h); tap(x + w / 2, y + h / 2); run(100);
    CHECK(!filmMenuUp() && filmButtonUp());
    // 13b. (1.11.91) started from the help page's button, the end comes back to the help page - its button - not the list
    tap(80, 30); run(50); CHECK(filmPlaying && !filmFromList && filmName == "EASY");
    run(ldrcfilm::lengthMs(filmHead) + 1500); CHECK(!filmPlaying && !filmMenuUp() && filmButtonUp());
    // 14. the safety off while a film plays (or is paused): it stops, no menu, no button; on again: the button
    tap(80, 30); run(500); CHECK(filmPlaying && filmName == "EASY");
    tap(400, 200); run(50); CHECK(filmPaused);
    flying = 2; run(50); CHECK(!filmPlaying && !filmPaused && !filmMenuUp() && !filmButtonUp() && audioId == -1);
    flying = 3; run(50); CHECK(filmButtonUp());           // (a model connected, safety on: allowed)
    // 15. the list open and the motor on: the list goes
    tap(80, 30); run(300); tap(400, 200); run(50);
    { int fx, fy, fw, fh; filmCtlRect(FILM_CTL_FILMS, fx, fy, fw, fh); tap(fx + fw / 2, fy + fh / 2); run(50); }
    CHECK(filmMenuUp()); flying = 1; run(50); CHECK(!filmMenuUp() && !filmButtonUp()); flying = 0; run(50);
    // 16. the help page left while a film plays: it stops and everything of ours goes
    tap(80, 30); run(300); CHECK(filmPlaying);
    page.name = "RFView"; run(50); CHECK(!filmPlaying && !filmUp() && !filmMenuUp() && !filmButtonUp() && !topOn);
    // 17. (1.11.91) the list, ten to a page: a card made up with 25 animations - three pages, the page shown, Next and
    // Previous going round, an empty place on the last page is nothing, a made-up animation that will not play leaves the list up
    SDROOT = "@SD2@"; page.name = "FrontView"; run(5000);
    helpTap("T01"); run(100); CHECK(filmButtonUp() && filmOwn == "T01" && filmCount == 25 && filmMenuPages() == 3);
    filmButtonHide(); filmMenuOpen(); run(50); CHECK(filmMenuUp() && filmMenuPage == 0);
    texts.clear(); filmMenuRect(FILM_NEXT, x, y, w, h); tap(x + w / 2, y + h / 2); run(50); CHECK(filmMenuPage == 1);
    { bool pg = false; for (auto &s : texts) if (s == "Page 2 of 3") pg = true; CHECK(pg); }
    filmMenuRect(FILM_PREV, x, y, w, h); tap(x + w / 2, y + h / 2); run(50); tap(x + w / 2, y + h / 2); run(50); CHECK(filmMenuPage == 2);
    filmMenuRect(25, x, y, w, h); CHECK(filmMenuAt(x + 5, y + 5) == -1);
    filmMenuRect(24, x, y, w, h); CHECK(filmMenuAt(x + 5, y + 5) == 24);
    tap(x + w / 2, y + h / 2); run(50); CHECK(filmMenuUp() && !filmPlaying);
    filmMenuRect(FILM_NEXT, x, y, w, h); tap(x + w / 2, y + h / 2); run(50); CHECK(filmMenuPage == 0);
    printf("flow: %d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
'''.replace('@SD@', os.path.join(ROOT, 'sd')).replace('@DEV@', os.path.join(ROOT, 'src', 'film_device.h'))
with tempfile.TemporaryDirectory() as d:
    sd2 = os.path.join(d, 'sd2'); os.makedirs(os.path.join(sd2, 'hmi', 'films'))   # (step 17's made-up card: 25 animations)
    open(os.path.join(sd2, 'hmi', 'films', 'films.txt'), 'w').write(''.join('T%02d: Made-up animation %d\n' % (i, i) for i in range(1, 26)))
    for i in range(1, 26): open(os.path.join(sd2, 'hmi', 'films', 'T%02d.ldf' % i), 'w').write('not a film')
    PROG = PROG.replace('@SD2@', sd2)
    cpp = os.path.join(d, 'flow.cpp'); exe = os.path.join(d, 'flow')
    open(cpp, 'w').write(PROG)
    r = subprocess.run(['clang++', '-std=c++17', '-O1', '-w', '-I', LIB, '-I', os.path.join(ROOT, 'src'), '-o', exe, cpp, os.path.join(LIB, 'JPEGDEC.cpp')], capture_output=True, text=True)
    if r.returncode: print(r.stdout[-3000:], r.stderr[-4000:]); sys.exit('does not compile')
    r = subprocess.run([exe], capture_output=True, text=True)
    print(r.stdout.strip()); print(r.stderr.strip()[-2000:])
    sys.exit(r.returncode)
