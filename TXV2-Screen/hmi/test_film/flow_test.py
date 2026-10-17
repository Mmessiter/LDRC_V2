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
                 void drawFastHLine(int x, int y, int w, uint16_t c) { fillRect(x, y, w, 1, c); } void drawFastVLine(int x, int y, int h, uint16_t c) { fillRect(x, y, 1, h, c); } } fakeGfx, *gfx = &fakeGfx;
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
static const int FILM_AUDIO_ID = -2; static int audioId = -1; static std::string audioPath;
static void audioStartFile(const char *p) { audioId = FILM_AUDIO_ID; audioPath = p; }
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
static void helpTap(const char *topic) { std::string s = std::string("print \"HelpView:") + topic + ".TXT\"\nLogView.t0.txt=\"x\""; filmNoteHelp(s); nowMs += 50; page.name = "LogView"; }
int main() {
    // 1. Help on a page: the Films button appears on the help page, with the films of films.txt that are on the card
    page.name = "EasyView"; run(100); CHECK(!filmButtonUp());
    helpTap("EASY"); run(100);
    CHECK(filmButtonUp() && filmCount >= 3);
    CHECK(!strcmp(filmList[0].name, "CALIB") && !strcmp(filmList[1].name, "CURVES") && !strcmp(filmList[2].name, "EASY"));
    // 2. the log viewer (the same page, no Help tap): no button
    page.name = "FrontView"; run(5000); page.name = "LogView"; run(200); CHECK(!filmButtonUp());
    // 3. Help again, then the button: the menu
    page.name = "RFView"; run(100); helpTap("RFLIGHT"); run(100); CHECK(filmButtonUp());
    tap(80, 30); run(50); CHECK(filmMenuUp() && !filmUp());
    // 4. a tap on nothing: nothing; on the second film: it plays, with its sound
    tap(300, 30); run(50); CHECK(filmMenuUp());
    int x, y, w, h; filmMenuRect(1, x, y, w, h);
    tap(x + w / 2, y + h / 2); run(50);
    CHECK(filmUp() && filmPlaying && filmName == "CURVES" && audioId == FILM_AUDIO_ID && audioPath == "/hmi/films/CURVES.wav" && filmPictures >= 1);
    run(3000); CHECK(filmPlaying && filmPictures == 1);   // (the title card: still, nothing new to decode)
    run(7000); CHECK(filmPlaying && filmPictures > 1 && filmLast > 0);   // (past the title: the pages)
    // 5. a tap stops it: back to the menu - and that tap starts nothing, though it lands on a film's button
    filmMenuRect(0, x, y, w, h);
    tap(x + w / 2, y + h / 2); run(50);
    CHECK(!filmPlaying && filmMenuUp() && audioId == -1);
    run(500); CHECK(!filmPlaying && filmMenuUp());
    // 6. a film to its end: back to the menu
    filmMenuRect(2, x, y, w, h); tap(x + w / 2, y + h / 2); run(50); CHECK(filmPlaying && filmName == "EASY");
    const uint32_t len = ldrcfilm::lengthMs(filmHead); run(len + 1000);
    CHECK(!filmPlaying && filmMenuUp());
    printf("EASY played to its end: %u pictures shown, %u missed (a host this fast misses none)\n", (unsigned) filmPictures, (unsigned) filmSkipped);
    // 7. OK: the help page again, its button back
    filmMenuRect(FILM_OK, x, y, w, h); tap(x + w / 2, y + h / 2); run(100);
    CHECK(!filmMenuUp() && filmButtonUp());
    // 8. the safety off while a film plays: it stops, no menu, no button; on again: the button
    tap(80, 30); run(50); filmMenuRect(0, x, y, w, h); tap(x + w / 2, y + h / 2); run(500); CHECK(filmPlaying && filmName == "CALIB");
    flying = 2; run(50); CHECK(!filmPlaying && !filmMenuUp() && !filmButtonUp() && audioId == -1);
    flying = 3; run(50); CHECK(filmButtonUp());           // (a model connected, safety on: allowed)
    // 9. the menu open and the motor on: the menu goes
    tap(80, 30); run(50); CHECK(filmMenuUp()); flying = 1; run(50); CHECK(!filmMenuUp() && !filmButtonUp()); flying = 0; run(50);
    // 10. the help page left while a film plays: it stops and everything of ours goes
    tap(80, 30); run(50); filmMenuRect(1, x, y, w, h); tap(x + w / 2, y + h / 2); run(300); CHECK(filmPlaying);
    page.name = "RFView"; run(50); CHECK(!filmPlaying && !filmUp() && !filmMenuUp() && !filmButtonUp() && !topOn);
    printf("flow: %d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
'''.replace('@SD@', os.path.join(ROOT, 'sd')).replace('@DEV@', os.path.join(ROOT, 'src', 'film_device.h'))
with tempfile.TemporaryDirectory() as d:
    cpp = os.path.join(d, 'flow.cpp'); exe = os.path.join(d, 'flow')
    open(cpp, 'w').write(PROG)
    r = subprocess.run(['clang++', '-std=c++17', '-O1', '-w', '-I', LIB, '-I', os.path.join(ROOT, 'src'), '-o', exe, cpp, os.path.join(LIB, 'JPEGDEC.cpp')], capture_output=True, text=True)
    if r.returncode: print(r.stdout[-3000:], r.stderr[-4000:]); sys.exit('does not compile')
    r = subprocess.run([exe], capture_output=True, text=True)
    print(r.stdout.strip()); print(r.stderr.strip()[-2000:])
    sys.exit(r.returncode)
