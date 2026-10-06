// LDRC transmitter V1B screen: a Nextion emulator on the CrowPanel 5.0 (800x480).
//
// The Teensy 4.1 keeps talking Nextion on UART0 (page / vis / click / X.txt= /
// X.val= / get …, 921600 baud). The 58 pages of TX_NEXTION.HMI live on the TF
// card as decoded by hmi/extract_hmi.py + hmi/build_sd.py: geometry, colours,
// fonts, text, and the pages' own event code, which a small interpreter runs
// (lib/NextionScript) so buttons answer the Teensy with the very bytes the
// Nextion sent. Backgrounds are raw RGB565 files blitted straight in.
//
// Draw discipline for the RGB panel: 10 MHz pixel clock and never a whole-
// screen redraw except on a page change (PSRAM contention flickers otherwise).
#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <ArduinoJson.h>
#include <Arduino_GFX_Library.h>
#include <TouchDrvGT911.hpp>
#include <map>
#include <algorithm>
#include <string>
#include <vector>
#include "NextionScript.h"
#include "LinkMaster.h"
#include "TxState.h"
#include "LdrcTheme.h"
#include "nextion_fonts.h"
#include <WiFi.h>
#include <ArduinoOTA.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <Preferences.h>

#ifndef NEXTION_BAUD
#define NEXTION_BAUD 921600
#endif
// The screen's own version. "Check for update" compares it with the release on messiter.com: a release
// with different firmware for the screen MUST carry a different number here (TXV1B dev/release_v1b.py checks).
#ifndef SCREEN_VERSION                                   // (the test builds of platformio.ini name themselves)
#define SCREEN_VERSION "1.10.5"
#endif
constexpr int W = 800, H = 480, LCD_BL = 2, TP_SDA = 19, TP_SCL = 20;
constexpr int SD_MOSI = 11, SD_MISO = 13, SD_CLK = 12, SD_CS = 10;

Arduino_ESP32RGBPanel *panel = new Arduino_ESP32RGBPanel(40, 41, 39, 0, 45, 48, 47, 21, 14, 5, 6, 7, 15, 16, 4, 8, 3, 46, 9, 1,
                                                          0, 8, 4, 43, 0, 8, 4, 12, 1, 10000000);
Arduino_RGB_Display *screen = new Arduino_RGB_Display(W, H, panel, 0, true);
Arduino_Canvas *canvas = new Arduino_Canvas(W, H, screen);   // every draw lands here (PSRAM); present() copies finished rectangles to the panel
Arduino_GFX *gfx = screen;                                    // switched to the canvas at boot
static uint16_t *fbNow = nullptr, *screenFb = nullptr;        // what gfx draws into / what the panel shows
static uint16_t *pageFb = nullptr;                            // the canvas: the page, as the Teensy draws it
// Our own panel ("Check for update") has a layer of its own, laid over the page as rectangles go to the
// glass: the Teensy goes on drawing the page underneath, and nothing it draws can show through the panel
// or damage it. When the panel goes, the page is there as the Teensy last drew it.
static Arduino_Canvas *topCanvas = nullptr; static uint16_t *topFb = nullptr;
static bool topOn = false;
static int topWho = 0;                                        // whose it is: 1 the update panel (src/update_device.h), 2 the WiFi page (src/wifi_device.h), 3 the link's panel, 4 the picture chooser (src/pics_device.h), 5 the flight screen, 6 its setup page (src/flight_device.h)
static int topX = 40, topY = 36, topW = 720, topH = 408;      // the part of the screen it covers
// Copy a finished rectangle from the canvas to the panel: one move per component, so nothing is ever seen
// half-drawn (the help text flashed white on every scroll step), and the panel's PSRAM buffer is written
// back from the CPU cache for its DMA.
static void present(int x, int y, int w, int h) {
    if (!pageFb || !screenFb || pageFb == screenFb) return;
    if (x < 0) { w += x; x = 0; } if (y < 0) { h += y; y = 0; }
    if (x + w > W) w = W - x; if (y + h > H) h = H - y;
    if (w <= 0 || h <= 0) return;
    const bool over = topOn && topFb && x < topX + topW && x + w > topX && y < topY + topH && y + h > topY;
    for (int yy = 0; yy < h; ++yy) {
        const int row = y + yy;
        if (over && row >= topY && row < topY + topH) {                     // page | panel | page: no pixel under the panel is ever shown, not even for a frame
            const int a = max(x, topX), b = min(x + w, topX + topW);
            if (a > x) memcpy(screenFb + row * W + x, pageFb + row * W + x, (a - x) * 2);
            memcpy(screenFb + row * W + a, topFb + row * W + a, (b - a) * 2);
            if (x + w > b) memcpy(screenFb + row * W + b, pageFb + row * W + b, (x + w - b) * 2);
        } else memcpy(screenFb + row * W + x, pageFb + row * W + x, w * 2);
    }
    Cache_WriteBack_Addr((uint32_t) (screenFb + y * W + x), (uint32_t) (((h - 1) * W + w) * 2));
}
// What has changed on the canvas and is waiting to be shown: a short list of rectangles, merged only when
// merging wastes little (a number top-right and a bar bottom-left must not become one screen-sized copy).
// The panel is updated at most 40 times a second, at the end of a burst of commands where there is one:
// a curve is never seen between its clear and its redraw.
struct Rect16 { int16_t x, y, w, h; };
static Rect16 dirtyList[24]; static int dirtyN = 0;
static uint32_t lastPresentMs = 0, firstDirtyMs = 0;
static uint32_t perfPresentUs = 0, perfPresentN = 0, perfPresentPx = 0, perfHandleUs = 0, perfCmds = 0, perfFillFull = 0, perfFillInc = 0, perfSkipped = 0, perfLoopMaxMs = 0;
static int perfRxMax = 0;
static uint32_t phaseMax[8] = { 0, 0, 0, 0, 0, 0, 0, 0 };   // longest single pass of each part of loop(), in microseconds
static const char *phaseName[8] = { "serial", "audio", "prefs", "touch", "timers", "present", "net", "" };
static void dirty(int x, int y, int w, int h) {
    if (x < 0) { w += x; x = 0; } if (y < 0) { h += y; y = 0; }
    if (x + w > W) w = W - x; if (y + h > H) h = H - y;
    if (w <= 0 || h <= 0) return;
    if (!dirtyN) firstDirtyMs = millis();
    int best = -1; long bestWaste = 0;
    for (int i = 0; i < dirtyN; ++i) {
        Rect16 &r = dirtyList[i];
        const int ux = min(x, (int) r.x), uy = min(y, (int) r.y), ux1 = max(x + w, r.x + r.w), uy1 = max(y + h, r.y + r.h);
        const long waste = (long) (ux1 - ux) * (uy1 - uy) - (long) w * h - (long) r.w * r.h;
        if (waste <= 1500) { r = { (int16_t) ux, (int16_t) uy, (int16_t) (ux1 - ux), (int16_t) (uy1 - uy) }; return; }
        if (best < 0 || waste < bestWaste) { best = i; bestWaste = waste; }
    }
    if (dirtyN < 24) { dirtyList[dirtyN++] = { (int16_t) x, (int16_t) y, (int16_t) w, (int16_t) h }; return; }
    Rect16 &r = dirtyList[best];
    const int ux = min(x, (int) r.x), uy = min(y, (int) r.y), ux1 = max(x + w, r.x + r.w), uy1 = max(y + h, r.y + r.h);
    r = { (int16_t) ux, (int16_t) uy, (int16_t) (ux1 - ux), (int16_t) (uy1 - uy) };
}
static void dirtyLine(int x1, int y1, int x2, int y2) {   // a long slanted line is shown in strips, not as its whole box
    const int bw = abs(x2 - x1) + 1, bh = abs(y2 - y1) + 1, steps = max(1, min(bw, bh) / 40);
    for (int i = 0; i < steps; ++i) {
        const int ax = x1 + (x2 - x1) * i / steps, ay = y1 + (y2 - y1) * i / steps, bx = x1 + (x2 - x1) * (i + 1) / steps, by = y1 + (y2 - y1) * (i + 1) / steps;
        dirty(min(ax, bx) - 1, min(ay, by) - 1, abs(bx - ax) + 3, abs(by - ay) + 3);
    }
}
static void presentDirty(bool force = false) {
    if (!dirtyN) return;
    const uint32_t now = millis();
    if (!force) {
        if (now - lastPresentMs < 25) return;                                  // 40 frames a second at most
        if (Serial.available() > 0 && now - firstDirtyMs < 80) return;        // a burst is still arriving: show it whole
    }
    const uint32_t t0 = micros();
    for (int i = 0; i < dirtyN; ++i) { present(dirtyList[i].x, dirtyList[i].y, dirtyList[i].w, dirtyList[i].h); perfPresentPx += (uint32_t) dirtyList[i].w * dirtyList[i].h; }
    dirtyN = 0; lastPresentMs = millis(); perfPresentUs += micros() - t0; perfPresentN++;
}
// The Teensy redraws a curve by clearing its whole box (130,000 pixels) and drawing ~60 short lines, up to 25
// times a second. When the SAME clear comes again we undo only what was drawn in the box since the last one:
// the result is the same pixels for a hundredth of the work, and only the changed strips go to the panel.
struct DrawOp { uint8_t kind; int16_t a, b, c, d; };          // 0: area x,y,w,h   1: line x1,y1,x2,y2
static struct { int x = 0, y = 0, w = 0, h = 0, colour = -1; bool valid = false; std::vector<DrawOp> ops; } fillMemo;
static bool hitsMemo(int x, int y, int w, int h) { return fillMemo.valid && x < fillMemo.x + fillMemo.w && x + w > fillMemo.x && y < fillMemo.y + fillMemo.h && y + h > fillMemo.y; }
static void memoTouched(int x, int y, int w, int h) { if (hitsMemo(x, y, w, h)) fillMemo.valid = false; }   // something else painted there: the next clear is a whole one
static void memoOp(uint8_t kind, int a, int b, int c, int d, int bx, int by, int bw, int bh) {
    if (!hitsMemo(bx, by, bw, bh)) return;
    if (fillMemo.ops.size() >= 400) { fillMemo.valid = false; return; }
    fillMemo.ops.push_back({ kind, (int16_t) a, (int16_t) b, (int16_t) c, (int16_t) d });
}
static void eraseArea(int x, int y, int w, int h) {             // in the memo's colour, inside its box only
    const int x1 = min(x + w, fillMemo.x + fillMemo.w), y1 = min(y + h, fillMemo.y + fillMemo.h);
    x = max(x, fillMemo.x); y = max(y, fillMemo.y);
    if (x1 <= x || y1 <= y) return;
    gfx->fillRect(x, y, x1 - x, y1 - y, fillMemo.colour); dirty(x, y, x1 - x, y1 - y);
}
static void eraseLine(int x1, int y1, int x2, int y2) {
    const int bw = abs(x2 - x1) + 1, bh = abs(y2 - y1) + 1;
    if ((long) bw * bh <= 900) { eraseArea(min(x1, x2) - 1, min(y1, y2) - 1, bw + 2, bh + 2); return; }   // short: its box, a pixel wider
    const int mx0 = fillMemo.x, my0 = fillMemo.y, mx1 = fillMemo.x + fillMemo.w, my1 = fillMemo.y + fillMemo.h;
    int dx = abs(x2 - x1), sx = x1 < x2 ? 1 : -1, dy = -abs(y2 - y1), sy = y1 < y2 ? 1 : -1, err = dx + dy, x = x1, y = y1;
    gfx->startWrite();
    for (int guard = 0; guard < 2000; ++guard) {                 // long: walked with a 3x3 brush, so no crumb is left whatever the rounding
        for (int oy = -1; oy <= 1; ++oy) for (int ox = -1; ox <= 1; ++ox) { const int px = x + ox, py = y + oy; if (px >= mx0 && px < mx1 && py >= my0 && py < my1) gfx->writePixel(px, py, fillMemo.colour); }
        if (x == x2 && y == y2) break;
        const int e2 = 2 * err; if (e2 >= dy) { err += dy; x += sx; } if (e2 <= dx) { err += dx; y += sy; }
    }
    gfx->endWrite();
    dirtyLine(x1, y1, x2, y2);
}
TouchDrvGT911 touch;
SPIClass sdSPI(HSPI);
bool touchOk = false, sdOk = false;

// ------------------------------------------------------------------ fonts: the HMI's own .zi glyphs
// (hmi/fonts/decode_zi.py → nextion_fonts.h). 1-bpp rows, MSB = leftmost pixel;
// a glyph is blitted at pen − kern_left, then the pen advances by width.
static const NextionFont *fontFor(int id) { return (id >= 0 && id < 7) ? nextion_fonts[id] : nextion_fonts[6]; }
static int fontHeight(int id) { return fontFor(id)->height; }
static int textWidth(int fontId, const std::string &s) {
    const NextionFont *f = fontFor(fontId); int w = 0;
    for (unsigned char c : s) { if (c < f->first || c > f->last) continue; w += f->glyphs[c - f->first].width; }
    return w;
}
static int clipX0 = 0, clipY0 = 0, clipX1 = 800, clipY1 = 480;   // drawGlyphs paints inside this window only (a box's text must not spill)
// The .zi fonts are anti-aliased (alpha 0..7 per pixel). The 1-bpp tables in flash are the fallback; the
// 4-bpp alpha tables come off the card into PSRAM at boot and are blended over whatever is under the text,
// which is what the Nextion draws — the hard 1-bit version looked like a pen running out of ink.
static uint8_t *aaBits[7] = { nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr };
static uint32_t *aaOffset[7] = { nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr };
static int fontIdx(int id) { return (id >= 0 && id < 7) ? id : 6; }
static void loadAaFonts() {
    for (int f = 0; f < 7; ++f) {
        const NextionFont *nf = nextion_fonts[f];
        char path[32]; snprintf(path, sizeof(path), "/hmi/font%d_aa.bin", f);
        File file = SD.open(path); if (!file) continue;
        const size_t n = file.size();
        uint8_t *buf = (uint8_t *) ps_malloc(n); if (!buf) { file.close(); continue; }
        const bool ok = file.read(buf, n) == n; file.close();
        uint32_t *off = (uint32_t *) ps_malloc(nf->count * 4); uint32_t run = 0;
        for (int g = 0; g < nf->count; ++g) { off[g] = run; run += ((nf->glyphs[g].bitmap_width + 1) / 2) * nf->height; }
        if (!ok || run != n) { free(buf); free(off); continue; }           // not the table we expect
        aaBits[f] = buf; aaOffset[f] = off;
    }
}
static inline uint16_t blend565(uint16_t bg, uint16_t fg, int a) {   // a = 1..6 of 7
    const int br = (bg >> 11) & 31, bg6 = (bg >> 5) & 63, bb = bg & 31, fr = (fg >> 11) & 31, fg6 = (fg >> 5) & 63, fb = fg & 31;
    return (uint16_t) ((((br * (7 - a) + fr * a) / 7) << 11) | (((bg6 * (7 - a) + fg6 * a) / 7) << 5) | ((bb * (7 - a) + fb * a) / 7));
}
static void drawGlyphs(int x, int y, int fontId, uint16_t col, const std::string &s) {
    const NextionFont *f = fontFor(fontId);
    const int h = f->height, fi = fontIdx(fontId);
    if (y >= clipY1 || y + h <= clipY0) return;
    if (aaBits[fi]) {
        uint16_t *fb = fbNow;
        for (unsigned char c : s) {
            if (c < f->first || c > f->last) continue;
            const NextionGlyph &g = f->glyphs[c - f->first];
            const int bw = g.bitmap_width, rowBytes = (bw + 1) / 2, gx = x - g.kern_left;
            const uint8_t *src = aaBits[fi] + aaOffset[fi][c - f->first];
            for (int row = 0; row < h; ++row) {
                const int py = y + row; if (py < clipY0 || py >= clipY1) continue;
                const uint8_t *r = src + row * rowBytes;
                for (int col2 = 0; col2 < bw; ++col2) {
                    const int a = (col2 & 1) ? (r[col2 >> 1] & 15) : (r[col2 >> 1] >> 4);
                    if (!a) continue;
                    const int px = gx + col2; if (px < clipX0 || px >= clipX1) continue;
                    gfx->writePixel(px, py, a >= 7 ? col : blend565(fb[py * W + px], col, a));
                }
            }
            x += g.width;
        }
        return;
    }
    for (unsigned char c : s) {
        if (c < f->first || c > f->last) continue;
        const NextionGlyph &g = f->glyphs[c - f->first];
        const int bw = g.bitmap_width, rowBytes = (bw + 7) / 8;
        const uint8_t *bits = f->bits + g.offset;
        const int gx = x - g.kern_left;
        for (int row = 0; row < h; ++row) {
            const uint8_t *r = bits + row * rowBytes;
            const int py = y + row; if (py < clipY0 || py >= clipY1) continue;
            for (int col2 = 0; col2 < bw; ++col2)
                if (r[col2 >> 3] & (0x80 >> (col2 & 7))) { const int px = gx + col2; if (px >= clipX0 && px < clipX1) gfx->writePixel(px, py, col); }
        }
        x += g.width;
    }
}
// The same letters at another size (the flight screen: a number as big as its box, Malcolm 10-04: "Box size should be
// linked to font size"). s16: the size in 16ths. Each pixel's alpha is read from the font's own anti-aliased glyph
// between its pixels (bilinear), so the edges stay smooth. A glyph is made once for each size and kept: a number that
// changes ten times a second costs only the blending.
struct ScaledGlyph { uint8_t *a = nullptr; int16_t w = 0, h = 0, left = 0; };
static std::map<uint32_t, ScaledGlyph> scaledGlyphs; static size_t scaledBytes = 0;
static const ScaledGlyph *scaledGlyph(int fi, const NextionFont *f, unsigned char c, int s16) {
    const uint32_t key = (uint32_t) fi << 24 | (uint32_t) s16 << 8 | c;
    auto it = scaledGlyphs.find(key); if (it != scaledGlyphs.end()) return &it->second;
    if (scaledBytes > 640 * 1024) { for (auto &e : scaledGlyphs) free(e.second.a); scaledGlyphs.clear(); scaledBytes = 0; }   // (only a few sizes are in use at a time)
    const NextionGlyph &g = f->glyphs[c - f->first];
    const int bw = g.bitmap_width, h = f->height, rowBytes = (bw + 1) / 2;
    const uint8_t *src = aaBits[fi] + aaOffset[fi][c - f->first];
    ScaledGlyph sg; sg.w = (int16_t) ((bw * s16 + 15) / 16); sg.h = (int16_t) ((h * s16 + 15) / 16); sg.left = (int16_t) ((g.kern_left * s16 + (g.kern_left >= 0 ? 8 : -8)) / 16);
    if (sg.w > 0 && sg.h > 0 && (sg.a = (uint8_t *) ps_malloc((size_t) sg.w * sg.h)) != nullptr) {
        auto alpha = [&](int x, int y) -> int { if (x < 0 || y < 0 || x >= bw || y >= h) return 0; const uint8_t b = src[y * rowBytes + (x >> 1)]; return (x & 1) ? (b & 15) : (b >> 4); };
        auto floorDiv = [](int v) { return v >= 0 ? v >> 8 : -((-v + 255) >> 8); };
        for (int dy = 0; dy < sg.h; ++dy) {
            const int sy = (2 * dy + 1) * 2048 / s16 - 128, y0 = floorDiv(sy), fy = sy - y0 * 256;   // the source point under this pixel's centre, in 256ths
            for (int dx = 0; dx < sg.w; ++dx) {
                const int sx = (2 * dx + 1) * 2048 / s16 - 128, x0 = floorDiv(sx), fx = sx - x0 * 256;
                const int top = alpha(x0, y0) * (256 - fx) + alpha(x0 + 1, y0) * fx, bot = alpha(x0, y0 + 1) * (256 - fx) + alpha(x0 + 1, y0 + 1) * fx;
                sg.a[dy * sg.w + dx] = (uint8_t) (((top * (256 - fy) + bot * fy) / 256 * 255 + 7 * 128) / (7 * 256));   // 0..255
            }
        }
        scaledBytes += (size_t) sg.w * sg.h;
    }
    return &(scaledGlyphs[key] = sg);
}
static inline uint16_t blend565x(uint16_t bg, uint16_t fg, int a) {   // a = 0..255
    const int br = (bg >> 11) & 31, bg6 = (bg >> 5) & 63, bb = bg & 31, fr = (fg >> 11) & 31, fg6 = (fg >> 5) & 63, fb = fg & 31;
    return (uint16_t) ((((br * (255 - a) + fr * a) / 255) << 11) | (((bg6 * (255 - a) + fg6 * a) / 255) << 5) | ((bb * (255 - a) + fb * a) / 255));
}
static void drawGlyphsScaled(int x, int y, int fontId, uint16_t col, const std::string &s, int s16) {
    const NextionFont *f = fontFor(fontId); const int fi = fontIdx(fontId);
    if (s16 == 16 || !aaBits[fi] || s16 <= 0) { drawGlyphs(x, y, fontId, col, s); return; }   // (its own size, or no smooth letters: as it is)
    uint16_t *fb = fbNow; int pen = 0;                         // the pen, in the font's own pixels
    for (unsigned char c : s) {
        if (c < f->first || c > f->last) continue;
        const ScaledGlyph *g = scaledGlyph(fi, f, c, s16);
        const int gx = x + (pen * s16 + 8) / 16 - g->left;
        pen += f->glyphs[c - f->first].width;
        if (!g->a) continue;
        for (int dy = 0; dy < g->h; ++dy) {
            const int py = y + dy; if (py < clipY0 || py >= clipY1) continue;
            const uint8_t *row = g->a + dy * g->w;
            for (int dx = 0; dx < g->w; ++dx) {
                const int a = row[dx]; if (a < 8) continue;
                const int px = gx + dx; if (px < clipX0 || px >= clipX1) continue;
                gfx->writePixel(px, py, a >= 248 ? col : blend565x(fb[py * W + px], col, a));
            }
        }
    }
}
// Nextion component type codes (what the HMI's own code reads as `.type`).
static int typeCodeOf(const std::string &t) {
    static const struct { const char *name; int code; } tab[] = {
        { "text", 116 }, { "number", 54 }, { "button", 98 }, { "dual-state button", 53 }, { "picture", 112 }, { "progress bar", 106 },
        { "slider", 1 }, { "hotspot", 109 }, { "timer", 51 }, { "variable", 52 }, { "checkbox", 56 }, { "radio", 57 }, { "audio", 4 },
        { "external picture", 60 }, { "combobox", 61 }, { "sltext", 62 }, { "switch", 67 }, { "textselect", 68 }, { "scrolling text", 55 }, { "xfloat", 59 } };
    for (auto &e : tab) if (t == e.name) return e.code;
    return 0;
}
// ------------------------------------------------------------------ component model
struct Comp {
    std::string name, type;
    int id = 0; bool global = false;
    int x = 0, y = 0, w = 0, h = 0, font = 0, sta = 3;
    int pco = 65535, bco = 0, pco2 = 65535, bco2 = 0, borderc = 0, borderw = 0, pco1 = 0;
    int isbr = 0;                                          // word wrap
    int scroll = 0;                                        // sltext: val_y; textselect: the wheel's offset
    int key = 255, txtMaxl = 0, typeCode = 0, dis = 0;     // key: the keyboard page this box opens (1 = keybdA, 2 = keybdB)
    int dir = 1, bco1 = 65535, pco3 = 0x8410;              // combobox: list direction (1 = below), list row colour, arrow colour
    int style = 0;                                         // frame: 0 flat, 1 border, 2 3D down, 3 3D up, 4 3D auto
    bool open = false;                                     // combobox: its list is showing
    bool damaged = true;                                   // something painted over it (or it has never been drawn): the next set repaints even if the value is the same
    int xcen = 0, ycen = 0, pic = -1, pic2 = -1, lenth = 0, dez = 0, wid = 20, hig = 20, maxval = 100, minval = 0, mode = 0, tim = 0, en = 0;
    std::string txt; int32_t val = 0;
    bool vis = true, pressed = false;
    std::string need;                                      // "model" / "nomodel": greyed out and deaf unless a model is / is not connected (the main board's ldrcst)
    std::vector<std::string> options;
    std::string evPress, evRelease, evMove, evTimer;
    uint32_t lastTick = 0;
    std::map<std::string, int32_t> extra;                 // any other int attribute the scripts touch
    uint16_t roles = 0;                                    // which of its colours are the style's (lib/LdrcTheme): they follow the pilot's choice
    bool centre = false;                                   // a channel bar: it grows from the middle (page file "centre")
};
struct Page {
    std::string name; int id = -1;
    int bgMode = 1, bgPic = -1, bgColor = 0;
    std::string evPre, evPost, evPress, evRelease, evExit;
    std::vector<Comp> comps;
    std::map<std::string, int> byName;
};
static Page page;                                          // the page on screen
static std::string pageNameNow() { return page.name; }
static std::vector<std::string> pageNames;                 // by id
static std::map<std::string, int> pageIds;
// Values that outlive a page: global-scope components, and writes to pages not on screen.
struct Kept { std::map<std::string, int32_t> ints; std::map<std::string, std::string> txts; };
static std::map<std::string, Kept> kept;                   // key "Page.Comp"
struct Comp; static std::string pageNameNow();
// A value the FINGER changed (a switch flipped, a slider moved, a row picked) is remembered like one the main board wrote,
// so that the page comes back with it, as a Nextion's global components do. (Screen 1.8.9; Malcolm, 10-04: "on the
// Wireless buddy screen, on return from 'select channels to pass to buddy' master gets turned off even if it was on" -
// the main board reloads that page without sending the switches, and the remembered value was its last, 0.)
static std::string touchLog;                               // the last values the finger set, and the pages loaded (a workshop look: /kept)
static void touchNote(const std::string &s) { char b[16]; snprintf(b, sizeof(b), "%lu ", (unsigned long) millis()); touchLog += b; touchLog += s; touchLog += "\n"; if (touchLog.size() > 1500) touchLog.erase(0, touchLog.size() - 1500); }
template <typename C> static void keepTouched(const C &c) {
    Kept &k = kept[pageNameNow() + "." + c.name]; k.ints["val"] = c.val; if (c.type == "combobox" || c.type == "textselect") k.txts["txt"] = c.txt;
    touchNote("touch " + pageNameNow() + "." + c.name + " val=" + std::to_string(c.val) + (c.type == "combobox" ? " \"" + c.txt + "\"" : std::string()));
}
static uint16_t *bgBuf = nullptr;                          // current background, RGB565, in PSRAM (owned by the cache)
static int bgW = 0, bgH = 0;
static bool loadingPage = false;                           // true while a page's preinitialize runs: no repaints yet
struct BgEntry { int id; uint16_t *buf; uint32_t used; };
static std::vector<BgEntry> bgCache;                       // up to 4 backgrounds resident (most pages share one)
static uint32_t cmdCount = 0, badCount = 0;
static bool touchLockout = false;                      // set on a page change: ignore touches until the finger is off
static bool touchPainted = false;                      // a touch changed the picture: show it without waiting for the frame timer
static bool noDraw = false;                            // test: /nodraw?on=1
// The pilot's colours for the panels and their writing (screen 1.7.0: lib/LdrcTheme, src/theme_device.h), navy and white
// unless chosen otherwise. Every page and message of the screen's own is drawn in them (navy with white text was Malcolm's
// choice for those, 30-9-2026; the restyled pages took it everywhere, and on 10-04: "let's make these colours user-definable").
static ldrc::Theme theme;
#define OUR_PANEL (theme.panel())
#define OUR_STRIP (theme.strip())
#define OUR_INK (theme.ink())
#define OUR_SOFT (theme.soft())
// The style's colours as the pilot has chosen them: at every page load, and on the page showing when they are chosen.
static void themeComp(Comp &c) {
    if (!c.roles) return;
    int r;
    if ((r = ldrc::themeRole(c.roles, ldrc::TF_BCO))) c.bco = ldrc::themeColour(theme, ldrc::TF_BCO, r);
    if ((r = ldrc::themeRole(c.roles, ldrc::TF_BCO2))) c.bco2 = ldrc::themeColour(theme, ldrc::TF_BCO2, r);
    if ((r = ldrc::themeRole(c.roles, ldrc::TF_PCO))) c.pco = ldrc::themeColour(theme, ldrc::TF_PCO, r);
    if ((r = ldrc::themeRole(c.roles, ldrc::TF_PCO2))) c.pco2 = ldrc::themeColour(theme, ldrc::TF_PCO2, r);
    if ((r = ldrc::themeRole(c.roles, ldrc::TF_BORDER))) c.borderc = ldrc::themeColour(theme, ldrc::TF_BORDER, r);
}
static bool radiosOn = true;                           // the user's switch: hold the top-left corner 1.5 s
static bool radiosLive = true;                         // what the hardware is doing now
// What the transmitter is doing, and what follows from it for the radios and for everything that must not be begun
// while the pilot is flying: lib/LdrcUpdate/TxState.h (the rule is the pilot's, and the main board decides it).
static ldrc::TxState tx;
static bool &armedNow = tx.armed;                      // the radios must be off
static int &txStatus = tx.status;                      // what the main board said last ("ldrcst=<bits>"), -1 if it never has
static bool &radioHeld = tx.held;                      // at start-up the radios wait for the main board's word
using ldrc::TX_MOTOR; using ldrc::TX_SAFETY_OFF; using ldrc::TX_MODEL; using ldrc::TX_SAFETY_DEFINED; using ldrc::TX_MODEL_JUST_NOW; using ldrc::TX_RADIOS_OFF;
static int flyingNow() { return tx.flying(); }
static const char *flyingText(int why) { return ldrc::TxState::flyingText(why); }
// The receiver, through the main board (firmware B11 and later): "ldrcrx=..." once a second while a model is
// connected or an update of the receiver is on its way (lib/LdrcUpdate/TxState.h).
static ldrc::RxNews rxNews;
static bool rxNewsAny = false;
static int sysDim = 100;                               // backlight %, from the Teensy's dim= / the HMI's dim=h0.val
static bool quietActive = false;                       // the /quiet experiment has the backlight
// The backlight. From power-on it stays OFF until the Teensy says how bright ("dim="): the Teensy dims its opening page
// to 1 % and fades it in itself, so nothing shines before there is something to see. (Malcolm, 10-03: "When turning on
// the transmitter, it flashes brightly before the front screen appears ... start up with zero brightness and then fade
// in gently while the opening screen is in view". The screen used to light up fully at once, showing its own start-up
// text for a second or so before the Teensy's first "dim=1".) A screen restarted on its own (an update) comes back to
// the brightness it had, gently; a screen with no Teensy (the bench, a new card) lights up by itself after 6 s.
RTC_NOINIT_ATTR static int rtcDim; RTC_NOINIT_ATTR static uint32_t rtcDimMagic;
static const uint32_t RTC_DIM_MAGIC = 0x4C44494D;
static bool blDark = true;                             // power-on: dark until the Teensy's first "dim="
static int blWant = 255, blNow = 0, blFrom = 0, blTo = 0; static uint32_t blAt = 0, blMs = 1; static bool blFading = false;
static void blSet(int v) { blNow = constrain(v, 0, 255); ledcWrite(1, blNow); }
static void backlight(int v) { blWant = constrain(v, 0, 255); if (blDark) return; blFading = false; blSet(blWant); }
static void blFadeTo(int to, uint32_t ms) { blFrom = blNow; blTo = constrain(to, 0, 255); blAt = millis(); blMs = ms ? ms : 1; blFading = true; }
static void blPoll() {
    if (blDark && millis() > 6000) { blDark = false; blFadeTo(blWant, 800); }   // no word from a Teensy: a screen on its own
    if (!blFading) return;
    const uint32_t t = millis() - blAt;
    if (t >= blMs) { blFading = false; blSet(blTo); return; }
    const float f = (float) t / (float) blMs;
    blSet(blFrom + (int) ((blTo - blFrom) * f * f));   // (eased in: the eye notices the first steps most)
}
static void setRadios(bool on);
static void applyRadios(const char *why);
static void doorToggle();                              // the workshop door (see "over the air")
// "Check for update" (src/update_device.h, lib/LdrcUpdate)
static bool updRequested = false;                      // the button has been pressed: the panel opens at the next pass of loop()
static bool rxUpdRequested = false;                    // "Receiver update" on the Model setup page (screen 1.4.0)
static bool updWifi = false;                           // the panel needs the WiFi, whatever the user's switch says
static bool updPanelUp();                              // our panel has the screen: touches are for its buttons
static void updTouch(bool pressed, int x, int y, uint32_t now);
static bool updHoldsLight();                           // work is going on: the backlight stays up
static bool updHasLink();                              // the job on the link is the panel's: it tells the story itself
static bool updChanging();                             // an update is changing something: do not switch off, do not start another
static bool updShowing();
static bool updAtWork();                               // "Check for update" is doing something, seen or unseen: the link is its own
// The WiFi page (src/wifi_device.h, lib/LdrcWifi)
static bool wifiRequested = false;                     // the button has been pressed: the page opens at the next pass of loop()
static bool wifiPageUp();
static void wifiTouch(bool pressed, int x, int y, uint32_t now);
static bool wifiSecretShown();                         // a password can be read on the glass: no picture of the screen leaves the transmitter
static void wifiWeb();
static void updWeb();
// The model pictures (src/pics_device.h, lib/LdrcPics): the chooser over the Teensy's "Choose image" page, photos from a phone
static bool picWifi = false;                           // the chooser is waiting for a photo: it needs the WiFi, whatever the user's switch says
static bool picPanelUp();
static void picTouch(bool pressed, int x, int y, uint32_t now);
static void picPoll();
static void picWeb();
static void picPageLoaded();                           // loadPage(): the chooser covers its page before anything of that page is drawn
static void picSoon();                                 // "Model image..." touched: the chooser's frame at once
// The flight screen (src/flight_device.h, lib/LdrcFlight): what the pilot chose to see while flying, over the front page
static bool flightRequested = false;                   // "ldrc flight" (Transmitter setup > Flight screen): its setup page at the next pass of loop()
static bool flightUp();                                // the flight screen or its setup page has the glass: touches are for it
static void flightTouch(bool pressed, int x, int y, uint32_t now);
static bool flightDefinedRequested = false;            // "ldrc defined": the front page's "Use defined" (the flight screen, now)
static void flightPoll();
static void flightLoad();
static void flightPageLoaded();                        // loadPage(): over the front page while flying, the flight screen is there before the page is drawn
// The pilot's themes (src/theme_device.h, lib/LdrcTheme): the Themes page ("ldrc colours"), opened from the Appearance page
static bool coloursRequested = false;                  // "ldrc colours": the page at the next pass of loop()
static bool appearanceRequested = false;               // "ldrc appearance" (Transmitter setup > Appearance): its page at the next pass of loop()
static bool appearanceUp();
static void appearanceTouch(bool pressed, int x, int y, uint32_t now);
static void appearancePoll();
static void appearancePageLoaded();
static void pongCommand(const std::string &a);         // "pong=...": the main board's Pong, drawn by us (src/pong_device.h)
static void pongPoll();
static bool coloursUp();
static void coloursTouch(bool pressed, int x, int y, uint32_t now);
static void coloursPoll();
static void coloursPageLoaded();
static void themeLoad();
static uint32_t flightCountdownAt = 0;                 // when the main board last wrote its power-off countdown ("TURN OFF?! 3"): the flight screen stands aside for it
static std::string lastDateTime;                       // the Teensy has the clock: what it last showed, for our records
static uint32_t teensyCommands = 0;                    // display commands that came over the wire (not from the Mac)
static std::string sentTrace;                          // last bytes sent to the Teensy, hex, for GET /sent
static std::string outBuf; static int scriptDepth = 0;   // a script's prints, sent as ONE burst when it ends
static void flushOut();
static void audioStart(int id, bool loopIt);           // `play ch,id,loop`: a clip from /hmi/audio/<id>.wav
static void audioFill();
static void audioStop();
static int audioVolume = 50;                           // `volume=` 0..100
// The amplifier on this board runs out of room at about half of full scale. Malcolm, 2026-10-03, with the clips
// peaking at -1 dBFS: "If I turn down the volume to about 33% it's fine - but distorts if I go higher." (The Nextion's
// amplifier gives up to 1.5 W from 5 V; this NS4168 runs from 3.3 V, about 0.5 W.) So volume 100 now sends what 30
// sent in 1.4.7, and the whole slider is clean. A 4 ohm speaker gets twice the power at the same setting; an
// amplifier moved to 5 V (R10 -> R45) would have about 3.6 dB more room, and this could then go up to about 0.85.
static const float AUDIO_MAX_GAIN = 0.55f;
static int audioGain = 398;                            // x1024 (volume 50), never above AUDIO_MAX_GAIN
// Volume 100 plays the clip at AUDIO_MAX_GAIN, 50 at 0.71 of that, 20 at 0.45. Until 1.4.6 the gain went up to x3 into a
// limiter that squashed every sample that came out too big: that squashing WAS the distortion Malcolm heard as he
// turned the volume up (2026-10-03; 19 % of the sound bent at 20, 45 % at 100). The loudness now comes from the clips
// themselves, processed once on the Mac (hmi/loud_audio.py: phase rotator, compressor, look-ahead limiter), and the
// screen never bends a sample. The amplifier (NS4168) runs from 3.3 V on this board, so it has less power than the
// Nextion's; its own anti-clipping (NCN) does not keep it clean above about half of full scale: AUDIO_MAX_GAIN.
static void audioSetVolume(int v) { audioVolume = constrain(v, 0, 100); audioGain = (int) (AUDIO_MAX_GAIN * sqrt(audioVolume / 100.0) * 1024); }
static inline int16_t limit16(int32_t y) { return (int16_t) constrain(y, -32767, 32767); }   // (the gain is at most 1: never reached)
static int audioId = -1;                               // the clip playing, for /status
static uint32_t bootMs = 0;                            // when loop() first ran (ms after power), for /status
static std::string bootLog;                            // the first ~4 kB of traffic after power, timestamped: GET /bootlog
static void blog(const char *tag, const std::string &what) { if (bootLog.size() > 4000) return; char b[24]; snprintf(b, sizeof(b), "%lu %s ", (unsigned long) millis(), tag); bootLog += b; bootLog += what.substr(0, 60); bootLog += "\n"; }
static std::string oddTrace;                           // commands the parser did not understand, for GET /status
static std::string radioLog;                           // when the radio went on and off, and why: GET /radiolog (the last twenty lines)
static std::string recent[64]; static int recentN = 0;   // the last commands from the Teensy, for GET /recent
static Preferences prefs;
// Flash writes stall the chip for milliseconds and the UART's 128-byte FIFO overflows at 921600 baud in
// 1.1 ms: a preference saved during a page load mangled whatever the Teensy sent right then (its file
// lists, its findfile question at boot). Saves wait until the link has been quiet for half a second.
static uint32_t lastRxMs = 0;
static int pendingBg = INT32_MIN, pendingVol = INT32_MIN, pendingRadios = INT32_MIN;
static std::string pendingDoor; static bool pendingDoorSet = false;
static uint32_t pendingSince = 0;                          // the pilot's own switches (the radios, the workshop door): written when the wire is quiet, or after 3 s, quiet or not
// The page to come back to after our own restart (an update) is kept in RTC memory: it survives a restart,
// not a power cycle, and costs no flash write. (As a preference it was only saved when the link fell
// silent, which on a page with live telemetry is never.)
RTC_NOINIT_ATTR static char rtcPage[24];
RTC_NOINIT_ATTR static uint32_t rtcMagic;
// The model's picture as the main board last named it on the front page (exp0.path), kept the same way: after our own
// restart (an update) the flight screen's picture box has it at once, before the main board shows its front page again.
RTC_NOINIT_ATTR static char rtcPicture[40];
RTC_NOINIT_ATTR static uint32_t rtcPictureMagic;
// The main board's global variables (a Nextion "variable" of global scope: the front page's colours, flags between
// pages), as last written, kept through our own restart (an update restarts us; the main board writes them once, at
// its own power-on). Screen 1.9.7; Malcolm, 10-05: Pong's scores on blue - the front page's background variable had
// gone back to the page file's old blue when only the screen had restarted.
struct RtcGlobal { char name[28]; int32_t val; };
static const int RTC_GLOBALS_MAX = 40;
RTC_NOINIT_ATTR static RtcGlobal rtcGlobals[RTC_GLOBALS_MAX];
RTC_NOINIT_ATTR static uint8_t rtcGlobalN;
RTC_NOINIT_ATTR static uint32_t rtcGlobalsMagic;
static const uint32_t RTC_GLOBALS_MAGIC = 0x4C444756;
static void rtcGlobalNote(const std::string &key, int32_t v) {
    if (key.size() >= sizeof(RtcGlobal::name)) return;
    if (rtcGlobalsMagic != RTC_GLOBALS_MAGIC) { rtcGlobalsMagic = RTC_GLOBALS_MAGIC; rtcGlobalN = 0; }
    for (int i = 0; i < rtcGlobalN && i < RTC_GLOBALS_MAX; ++i) if (key == rtcGlobals[i].name) { rtcGlobals[i].val = v; return; }
    if (rtcGlobalN >= RTC_GLOBALS_MAX) return;              // (full: the first forty are the ones that matter, written at the main board's start)
    strlcpy(rtcGlobals[rtcGlobalN].name, key.c_str(), sizeof(RtcGlobal::name)); rtcGlobals[rtcGlobalN].val = v; ++rtcGlobalN;
}
static void prefsPoll() {
    if ((pendingRadios != INT32_MIN || pendingDoorSet) && ((int32_t) (millis() - lastRxMs) > 300 || millis() - pendingSince > 3000)) {
        if (pendingRadios != INT32_MIN) { if (prefs.getBool("radios", true) != (pendingRadios == 1)) prefs.putBool("radios", pendingRadios == 1); pendingRadios = INT32_MIN; }
        if (pendingDoorSet) { pendingDoorSet = false; if (pendingDoor.empty()) { if (prefs.isKey("door")) prefs.remove("door"); } else prefs.putString("door", pendingDoor.c_str()); }
    }
    if ((int32_t) (millis() - lastRxMs) < 500) return;
    if (pendingBg != INT32_MIN) { if (prefs.getInt("bg", -1) != pendingBg) prefs.putInt("bg", pendingBg); pendingBg = INT32_MIN; }
    if (pendingVol != INT32_MIN) { if (prefs.getInt("vol", -1) != pendingVol) prefs.putInt("vol", pendingVol); pendingVol = INT32_MIN; }
}

static Comp *find(const std::string &nm) { auto it = page.byName.find(nm); return it == page.byName.end() ? nullptr : &page.comps[it->second]; }

// ------------------------------------------------------------------ background + drawing
static bool loadBackground(int picId) {
    if (picId < 0 || !sdOk) return false;
    for (auto &e : bgCache) if (e.id == picId) { e.used = millis(); bgBuf = e.buf; bgW = W; bgH = H; return true; }
    char path[32]; snprintf(path, sizeof(path), "/hmi/pic/%d.565", picId);
    File f = SD.open(path);
    if (!f) return false;
    uint16_t wh[2]; f.read((uint8_t *) wh, 4);
    uint16_t *buf;
    buf = bgCache.size() < 4 ? (uint16_t *) ps_malloc(W * H * 2) : nullptr;   // 4 backgrounds resident (3 MB): the clip cache needs its share of PSRAM
    if (!buf && bgCache.empty()) { f.close(); return false; }
    if (!buf) { size_t old = 0; for (size_t i = 1; i < bgCache.size(); ++i) if (bgCache[i].used < bgCache[old].used) old = i; buf = bgCache[old].buf; bgCache.erase(bgCache.begin() + old); }
    if (wh[0] == W && wh[1] == H) f.read((uint8_t *) buf, W * H * 2);
    else { memset(buf, 0, W * H * 2); for (int y = 0; y < wh[1] && y < H; ++y) f.read((uint8_t *) (buf + y * W), min((int) wh[0], W) * 2); }
    f.close();
    bgCache.push_back({picId, buf, millis()});
    bgBuf = buf; bgW = W; bgH = H;
    return true;
}
// Paint the page background under a rectangle (transparent components sit on it).
static void restoreRect(int x, int y, int w, int h) {
    if (x < 0) { w += x; x = 0; } if (y < 0) { h += y; y = 0; }
    if (x + w > W) w = W - x; if (y + h > H) h = H - y;
    if (w <= 0 || h <= 0 || loadingPage) return;          // during a page load the background is painted once, after preinit
    if (page.bgMode != 1 && bgBuf) {                        // image, or a popup over the previous page's image
        uint16_t *fb = fbNow;
        for (int yy = 0; yy < h; ++yy) memcpy(fb + (y + yy) * W + x, bgBuf + (y + yy) * W + x, w * 2);
        if (fb == screenFb) Cache_WriteBack_Addr((uint32_t) (fb + y * W + x), (uint32_t) (((h - 1) * W + w) * 2));   // no canvas: the panel's DMA reads PSRAM directly
    } else gfx->fillRect(x, y, w, h, page.bgColor);
}
// What lies under a component that does not fill its own rectangle (a switch's rounded ends, a radio's disc, a slider's
// track, a see-through text, a model picture's frame): the solid component it sits on, if one was drawn before it and
// covers it (the System pages' navy card: Malcolm saw the red of his background picture in the switches' corners,
// 10-03; screen 1.5.6: the same red showed behind the sliders and the empty picture frame), else the page's own picture.
static void restoreUnder(const Comp &c) {
    const long me = (long) (&c - page.comps.data());
    if (me > 0 && me < (long) page.comps.size())
        for (long i = me - 1; i >= 0; --i) {
            const Comp &o = page.comps[i];
            if (!o.vis || o.sta != 1 || (o.type != "text" && o.type != "number")) continue;
            if (o.x <= c.x && o.y <= c.y && o.x + o.w >= c.x + c.w && o.y + o.h >= c.y + c.h) { gfx->fillRect(c.x, c.y, c.w, c.h, o.bco); return; }
        }
    restoreRect(c.x, c.y, c.w, c.h);
}
static uint16_t shade(uint16_t c, int pct) {              // pct > 0 towards white, < 0 towards black
    int r = (c >> 11) & 31, g = (c >> 5) & 63, b = c & 31;
    if (pct > 0) { r += (31 - r) * pct / 100; g += (63 - g) * pct / 100; b += (31 - b) * pct / 100; }
    else { r += r * pct / 100; g += g * pct / 100; b += b * pct / 100; }
    return (uint16_t) ((r << 11) | (g << 5) | b);
}
// The Nextion's frame styles: 0 flat (nothing — the help page's boxes), 1 border in borderc, 2 3D down
// (sunk), 3 3D up (raised), 4 3D auto (raised, sunk while pressed). Drawn from the box's own colour.
static void drawFrame(const Comp &c, uint16_t bg, bool down) {
    const int x = c.x, y = c.y, w = c.w, h = c.h;
    if (c.style == 1) { for (int i = 0; i < max(1, c.borderw); ++i) gfx->drawRect(x + i, y + i, w - 2 * i, h - 2 * i, c.borderc); return; }
    if (c.style < 2) return;
    const bool sunk = c.style == 2 || (c.style == 4 && down);
    const uint16_t tl = sunk ? shade(bg, -45) : shade(bg, 60), br = sunk ? shade(bg, 60) : shade(bg, -45);
    for (int i = 0; i < 2; ++i) {
        gfx->drawFastHLine(x + i, y + i, w - 2 * i, tl); gfx->drawFastVLine(x + i, y + i, h - 2 * i, tl);
        gfx->drawFastHLine(x + i, y + h - 1 - i, w - 2 * i, br); gfx->drawFastVLine(x + w - 1 - i, y + i, h - 2 * i, br);
    }
}
// The display lines of a text: explicit \r\n or \n breaks (a final break adds no empty line), plus
// word-wrap at spaces when the component asks for it (isbr). Lines are what the Teensy sent — the
// help/log files arrive pre-wrapped, the lists one item per line.
static std::vector<std::string> textLines(const std::string &s, int font, int maxW, bool wrap) {
    std::vector<std::string> out;
    size_t i = 0;
    while (i < s.size()) {
        size_t e = s.find_first_of("\r\n", i);
        std::string line = s.substr(i, e == std::string::npos ? std::string::npos : e - i);
        if (e == std::string::npos) i = s.size(); else i = (s[e] == '\r' && e + 1 < s.size() && s[e + 1] == '\n') ? e + 2 : e + 1;
        if (!wrap || maxW <= 0 || textWidth(font, line) <= maxW) { out.push_back(line); continue; }
        while (!line.empty()) {                                // whole words only: a word (or a number) wider than the box stays in one piece
            if (textWidth(font, line) <= maxW) { out.push_back(line); break; }
            size_t cut = std::string::npos, pos = 0;
            for (;;) { const size_t sp = line.find(' ', pos); if (sp == std::string::npos) break; if (sp > 0 && textWidth(font, line.substr(0, sp)) > maxW) break; cut = sp; pos = sp + 1; }
            if (cut == std::string::npos || cut == 0) { const size_t sp = line.find(' ', 1); if (sp == std::string::npos) { out.push_back(line); break; } cut = sp; }
            out.push_back(line.substr(0, cut));
            line.erase(0, cut);
            while (!line.empty() && line[0] == ' ') line.erase(0, 1);
        }
    }
    if (out.empty()) out.push_back("");
    return out;
}
// Text inside a box: every line, clipped to the box, scrolled up by offY (sltext's val_y).
static std::string inkOf(const std::string &s) { size_t e = s.find_last_not_of(' '); return e == std::string::npos ? std::string() : s.substr(0, e + 1); }
// cutInset >= 0: a single line too wide for its box ends in "..." rather than in half a letter (screen 1.5.6, Malcolm's
// pages at night: a long model name, the owner's name); the frame's width is kept clear. -1: clipped, as the Nextion does.
static int frameWidth(const Comp &c) { return c.style == 1 ? max(1, c.borderw) : (c.style >= 2 && c.style <= 4) ? 2 : 0; }
static void drawTextIn(int x, int y, int w, int h, int font, uint16_t col, const std::string &s, int xcen, int ycen, bool wrap = false, int offY = 0, int cutInset = -1) {
    if (s.empty()) return;
    const int fh = fontHeight(font), pad = 2;
    std::vector<std::string> lines = textLines(s, font, w, wrap);
    // The Nextion lays the lines out as ONE BLOCK: lines left-aligned inside it, the block centred (or
    // not) in the box, and a block too tall or too wide for the box starts from the top / the left — the
    // switches page's six-line note shows its first four lines, not its middle four.
    // Blank lines at the END of the text do not count (the trim-direction boxes hold one line and up to four
    // blank ones: the V1 centres that one line in each box).
    while (lines.size() > 1 && lines.back().find_first_not_of(" \t") == std::string::npos) lines.pop_back();
    if (cutInset >= 0 && lines.size() == 1) {
        std::string ink = inkOf(lines[0]); const int room = w - 2 * cutInset - (xcen == 1 ? 0 : pad);   // (the room the words have: all of it when centred, after the margin otherwise)
        if (textWidth(font, ink) > room) { while (!ink.empty() && textWidth(font, ink + "...") > room) ink.pop_back(); lines[0] = inkOf(ink) + "..."; }
    }
    const int th = (int) lines.size() * fh;
    // Centred words are centred by their ink: trailing spaces do not push them aside (the Teensy pads "Not used" with
    // nine spaces on the switches page, which put it 31 px left of the middle).
    int bw = 0; for (auto &line : lines) bw = max(bw, textWidth(font, xcen == 1 ? inkOf(line) : line));
    int bx = xcen == 1 ? x + (w - bw) / 2 : xcen == 2 ? x + w - bw - pad : x + pad;
    if (bx < x) bx = x;
    int ty = ycen == 1 ? y + (h - th) / 2 : ycen == 2 ? y + h - th - 1 : y + 1;
    if (ty < y) ty = y;
    ty -= offY;
    clipX0 = max(0, x); clipY0 = max(0, y); clipX1 = min(W, x + w); clipY1 = min(H, y + h);
    gfx->startWrite();
    for (auto &line : lines) {
        if (ty + fh > y && ty < y + h && !line.empty()) {
            const int tx = xcen == 2 ? max(x, x + w - textWidth(font, line) - pad) : bx;
            drawGlyphs(tx, ty, font, col, line);
        }
        ty += fh;
    }
    gfx->endWrite();
    clipX0 = 0; clipY0 = 0; clipX1 = W; clipY1 = H;
}
// A TextSelect is the Nextion's cyclic spinner: the options (hig px each) slide through a selection
// band in the middle of the box — two lines in pco1 when dis is set — and whatever sits in the band is
// the value, drawn in pco2. Sliding turns the wheel; it settles on a row when the finger lifts.
static int listInnerH(const Comp &c) { return c.h - 2 * c.borderw; }
static int listRowH(const Comp &c) { return max(1, c.hig); }
static int listBandY(const Comp &c) { return c.y + c.borderw + (listInnerH(c) - listRowH(c)) / 2; }
static bool listCyclic(const Comp &c) { return (int) c.options.size() * listRowH(c) > listInnerH(c); }   // a short list does not wrap
static int floorDiv(int a, int b) { return a >= 0 ? a / b : -((-a + b - 1) / b); }
static int listWrap(const Comp &c, int scroll) {           // keep the offset within one turn of the wheel
    const int n = (int) c.options.size(); if (n <= 0) return 0;
    if (!listCyclic(c)) return constrain(scroll, 0, (n - 1) * listRowH(c));
    const int turn = n * listRowH(c); scroll %= turn; if (scroll < 0) scroll += turn; return scroll;
}
static void listSnap(Comp &c) {                             // settle on the nearest row: that row is the value
    const int n = (int) c.options.size(); if (n <= 0) { c.val = 0; c.scroll = 0; return; }
    const int rowH = listRowH(c);
    c.scroll = listWrap(c, floorDiv(c.scroll + rowH / 2, rowH) * rowH);
    c.val = (c.scroll / rowH) % n; c.txt = c.options[c.val];
}
static void listShowSelected(Comp &c) {                     // turn the wheel so the value sits in the band
    if (c.options.empty()) { c.val = 0; c.scroll = 0; return; }
    if (c.val < 0 || c.val >= (int) c.options.size()) c.val = 0;
    c.scroll = c.val * listRowH(c); c.txt = c.options[c.val];
}
// A ComboBox: a box showing the choice with a small arrow; tapped, its options drop down (dir 1 =
// below) one row of hig px each, the current choice on bco2 in pco2, the others on bco1.
static int comboRows(const Comp &c) { int n = 0; for (auto &o : c.options) if (!o.empty()) n++; return n; }
static void comboListRect(const Comp &c, int &x, int &y, int &w, int &h) {
    const int rowH = max(1, c.hig), n = comboRows(c);
    x = c.x; w = c.w; h = n * rowH; y = c.dir == 0 ? c.y - h : c.y + c.h;
}
static void drawComboList(Comp &c);
static void drawCombo(Comp &c) {
    gfx->fillRect(c.x, c.y, c.w, c.h, c.bco);
    drawFrame(c, c.bco, false);
    const int aw = max(6, c.wid);                            // the arrow's lane at the right
    const std::string s = (c.val >= 0 && c.val < (int) c.options.size()) ? c.options[c.val] : c.txt;
    drawTextIn(c.x, c.y, c.w - aw, c.h, c.font, c.pco, s, c.xcen, c.ycen, false, 0, frameWidth(c));
    const int ax = c.x + c.w - aw / 2 - 2, ay = c.y + c.h / 2;
    gfx->fillTriangle(ax - 4, ay - 2, ax + 4, ay - 2, ax, ay + 3, c.pco3);
    if (c.open) drawComboList(c);
}
static void drawComboList(Comp &c) {                      // the dropped list, on top of whatever is there
    int lx, ly, lw, lh; comboListRect(c, lx, ly, lw, lh);
    const int rowH = max(1, c.hig), fh = fontHeight(c.font);
    const int hl = c.extra.count("hl") ? c.extra["hl"] : c.val;   // the last real choice stays highlighted (the press event may park val at 255)
    int row = 0;
    for (int i = 0; i < (int) c.options.size(); ++i) {
        if (c.options[i].empty()) continue;
        const int ry = ly + row * rowH; const bool sel = i == hl;
        gfx->fillRect(lx, ry, lw, rowH, sel ? c.bco2 : c.bco1);
        gfx->drawRect(lx, ry, lw, rowH, c.borderc);
        const int tw = textWidth(c.font, c.options[i]);
        gfx->startWrite(); drawGlyphs(c.xcen == 1 ? lx + (lw - tw) / 2 : lx + 4, ry + (rowH - fh) / 2, c.font, sel ? c.pco2 : c.pco, c.options[i]); gfx->endWrite();
        row++;
    }
}
static void drawList(Comp &c) {
    const int bw = c.borderw;
    gfx->fillRect(c.x, c.y, c.w, c.h, c.bco);
    drawFrame(c, c.bco, false);
    const int ix = c.x + bw, iy = c.y + bw, iw = c.w - 2 * bw, ih = c.h - 2 * bw, rowH = listRowH(c), fh = fontHeight(c.font);
    const int n = (int) c.options.size(), by = listBandY(c);
    clipX0 = max(0, ix); clipY0 = max(0, iy); clipX1 = min(W, ix + iw); clipY1 = min(H, iy + ih);
    if (n > 0) {
        const bool cyc = listCyclic(c);
        const int kFirst = floorDiv(iy - by + c.scroll, rowH) - 1, kLast = floorDiv(iy + ih - by + c.scroll, rowH) + 1;
        // Each row centred, as the Nextion's wheel showed them (Malcolm, 10-05: "The model names and the back-up file names in
        // version one were centred rather than left justified, which I think I preferred"), with a margin at both ends, and
        // a name too long for the box ends in "..." rather than half a letter. (Whole rows: the page's box holds an odd
        // number of them.)
        const int pad = 14, room = iw - 2 * pad;
        for (int k = kFirst; k <= kLast; ++k) {              // k counts rows on the wheel; cyclic wheels repeat the list
            int i = k; if (cyc) i = ((k % n) + n) % n; else if (k < 0 || k >= n) continue;
            const int ry = by + k * rowH - c.scroll;
            if (ry + rowH <= iy || ry >= iy + ih) continue;
            const bool inBand = abs(ry - by) < rowH / 2;
            std::string s = c.options[i];
            if (textWidth(c.font, s) > room) { while (!s.empty() && textWidth(c.font, s + "...") > room) s.pop_back(); s += "..."; }
            gfx->startWrite(); drawGlyphs(ix + (iw - textWidth(c.font, s)) / 2, ry + (rowH - fh) / 2, c.font, inBand ? c.pco2 : c.pco, s); gfx->endWrite();
        }
    }
    if (c.dis) { gfx->drawFastHLine(ix, by, iw, c.pco1); gfx->drawFastHLine(ix, by + rowH - 1, iw, c.pco1); }
    clipX0 = 0; clipY0 = 0; clipX1 = W; clipY1 = H;
}
// A button with a rule ("need") is greyed out and deaf while the rule is unmet (Malcolm, 30-9-2026: the transmitter's
// update only with no model connected, the receiver's only with one). A main board that has never said what it is
// doing (older firmware, the bench) leaves every such button usable.
static bool needUnmet(const Comp &c) {
    if (c.need.empty() || txStatus < 0) return false;
    const bool model = (txStatus & TX_MODEL) != 0;
    if (c.need == "model") return !model;
    if (c.need == "nomodel") return model;
    return false;
}
static void needRedraw();                                  // the rule's answer changed: repaint the buttons it governs
// A model picture on the card: the pilot's own photo (/images/mine, sent from a phone) first, then the release's.
static std::string imagePath(const std::string &base) {
    const std::string mine = "/images/mine/" + base + ".565";
    if (sdOk && SD.exists(mine.c_str())) return mine;
    return "/images/" + base + ".565";
}
static void drawComp(Comp &c) {
    if (loadingPage || noDraw) return;
    c.damaged = false;
    if (!c.vis || c.w <= 0 || c.h <= 0) return;
    if (c.x + c.w <= 0 || c.y + c.h <= 0 || c.x >= W || c.y >= H) return;        // parked off-screen on purpose
    const std::string &t = c.type;
    if (t == "variable" || t == "timer" || t == "audio") return;
    if (t == "external picture") {                          // the model's photo: txt holds the path the Teensy sent
        restoreUnder(c);
        if (c.txt.empty() || !sdOk) return;
        std::string base = c.txt.substr(c.txt.find_last_of("/\\") == std::string::npos ? 0 : c.txt.find_last_of("/\\") + 1);
        size_t dot = base.find_last_of('.'); if (dot != std::string::npos) base = base.substr(0, dot);
        const std::string path = imagePath(base);
        File f = SD.open(path.c_str());
        if (!f) return;
        uint16_t wh[2]; f.read((uint8_t *) wh, 4);
        std::vector<uint16_t> row(wh[0]);
        const int ox = c.x + (c.w - (int) wh[0]) / 2, oy = c.y + (c.h - (int) wh[1]) / 2;   // centred in the frame
        for (int yy = 0; yy < wh[1]; ++yy) { f.read((uint8_t *) row.data(), wh[0] * 2); if (oy + yy >= 0 && oy + yy < H) gfx->draw16bitRGBBitmap(ox, oy + yy, row.data(), wh[0], 1); }
        f.close();
        return;
    }
    if (t == "textselect") { drawList(c); return; }
    if (t == "combobox") { drawCombo(c); return; }
    if (t == "sltext") {                                    // slide text: the help/log viewer, val_y pixels scrolled
        if (c.sta == 1) gfx->fillRect(c.x, c.y, c.w, c.h, c.bco); else restoreUnder(c);
        drawFrame(c, c.bco, false);
        const int bw = c.borderw;
        drawTextIn(c.x + bw, c.y + bw, c.w - 2 * bw, c.h - 2 * bw, c.font, c.pco, c.txt, c.xcen, c.ycen, c.isbr != 0, c.scroll);
        return;
    }
    if (t == "text" || t == "number" || t == "combobox") {
        if (c.sta == 1) gfx->fillRect(c.x, c.y, c.w, c.h, c.bco); else restoreUnder(c);
        drawFrame(c, c.bco, false);
        std::string s;
        if (t == "number") { char b[16]; if (c.lenth > 0) snprintf(b, sizeof(b), "%0*ld", c.lenth, (long) c.val); else snprintf(b, sizeof(b), "%ld", (long) c.val); s = b; }   // (one format string with two arguments printed the digit count — every free-length number read 0)
        else if (t == "combobox") s = (c.val >= 0 && c.val < (int) c.options.size()) ? c.options[c.val] : c.txt;
        else s = c.txt;
        drawTextIn(c.x, c.y, c.w, c.h, c.font, c.pco, s, c.xcen, c.ycen, t == "text" && c.isbr != 0, 0, t == "number" || c.isbr ? -1 : frameWidth(c));   // numbers never wrap ("-16" took two lines on the trims page), nor end in dots
        return;
    }
    if (t == "button" || t == "dual-state button") {
        const bool on = (t == "dual-state button") ? (c.val != 0) : c.pressed;
        const uint16_t bg = on ? c.bco2 : c.bco, fg = needUnmet(c) ? (uint16_t) 0x8410 : (on ? c.pco2 : c.pco);   // greyed out: mid-grey text
        if (c.sta == 3) restoreUnder(c);
        else { gfx->fillRect(c.x, c.y, c.w, c.h, bg); drawFrame(c, bg, on); }
        drawTextIn(c.x, c.y, c.w, c.h, c.font, fg, c.txt, c.xcen ? c.xcen : 1, c.ycen ? c.ycen : 1, false, 0, c.sta == 3 ? 0 : frameWidth(c));
        return;
    }
    if (t == "progress bar") {
        gfx->fillRect(c.x, c.y, c.w, c.h, c.bco);
        const int v = constrain((int) c.val, 0, 100);
        if (c.centre && c.dez == 0) {                      // a channel bar: from the middle out, its end where it always was (Malcolm, 10-04, after
            const int mid = c.x + c.w / 2, end = c.x + c.w * v / 100;   // the flight screen's bars: "should be imitated on the default front screen as well as the channels screen")
            if (end > mid) gfx->fillRect(mid, c.y, end - mid, c.h, c.pco); else if (end < mid) gfx->fillRect(end, c.y, mid - end, c.h, c.pco);
            gfx->drawFastVLine(mid, c.y, c.h, 0xC618);
        }
        else if (c.dez == 0) gfx->fillRect(c.x, c.y, c.w * v / 100, c.h, c.pco);
        else { const int hh = c.h * v / 100; gfx->fillRect(c.x, c.y + c.h - hh, c.w, hh, c.pco); }
        return;
    }
    if (t == "slider") {
        // The Nextion draws these (psta 0, wid/hig 255) as a thin track in bco with a round knob in pco
        // whose diameter is the component's thickness — a small dot on the 15 px trims, a big blob on the
        // 45 px volume slider. The knob's travel keeps it inside the component.
        restoreUnder(c);
        const int range = max(1, c.maxval - c.minval);
        const int v = constrain((int) c.val - c.minval, 0, range);
        if (c.mode == 0) {
            const int d = max(6, c.h), r = d / 2, track = max(3, c.h / 4);
            gfx->fillRoundRect(c.x, c.y + (c.h - track) / 2, c.w, track, track / 2, c.bco);
            gfx->fillCircle(c.x + r + (long) (c.w - d) * v / range, c.y + c.h / 2, r - 1, c.pco);
        } else {
            const int d = max(6, c.w), r = d / 2, track = max(3, c.w / 4);
            gfx->fillRoundRect(c.x + (c.w - track) / 2, c.y, track, c.h, track / 2, c.bco);
            gfx->fillCircle(c.x + c.w / 2, c.y + c.h - r - (long) (c.h - d) * v / range, r - 1, c.pco);
        }
        return;
    }
    if (t == "checkbox" || t == "radio" || t == "switch") {
        restoreUnder(c);                                     // (a switch's rounded ends show what it sits on: the card of a page, or its picture)
        const int s = min(c.w, c.h);
        if (t == "radio") {                                  // a disc in bco; chosen, a dot in pco at its centre (the V1's pale disc with a red dot)
            const int r = s / 2 - 1, cx = c.x + c.w / 2, cy = c.y + c.h / 2;
            gfx->fillCircle(cx, cy, r, c.bco); gfx->drawCircle(cx, cy, r, shade(c.bco, -25));
            if (c.val) gfx->fillCircle(cx, cy, max(3, r * 45 / 100), c.pco);
        }
        else if (t == "switch") { const int r = c.h / 2; gfx->fillRoundRect(c.x, c.y, c.w, c.h, r, c.val ? c.bco2 : c.bco); gfx->fillCircle(c.val ? c.x + c.w - r : c.x + r, c.y + r, max(2, r - 3), c.pco); }
        else {                                               // checkbox: a square in bco, framed by its style; ticked, a block in pco inside it
            gfx->fillRect(c.x, c.y, s, s, c.bco);
            if (c.style == 1) { for (int i = 0; i < max(1, c.borderw); ++i) gfx->drawRect(c.x + i, c.y + i, s - 2 * i, s - 2 * i, c.borderc); } else gfx->drawRect(c.x, c.y, s, s, shade(c.bco, -40));
            if (c.val) { const int in = max(3, s / 4); gfx->fillRect(c.x + in, c.y + in, s - 2 * in, s - 2 * in, c.pco); }
        }
        return;
    }
    if (t == "picture") {
        if (c.pic >= 0 && sdOk) {
            char path[32]; snprintf(path, sizeof(path), "/hmi/pic/%d.565", c.pic);
            File f = SD.open(path);
            if (f) { uint16_t wh[2]; f.read((uint8_t *) wh, 4); std::vector<uint16_t> row(wh[0]);
                     for (int yy = 0; yy < wh[1] && c.y + yy < H; ++yy) { f.read((uint8_t *) row.data(), wh[0] * 2); gfx->draw16bitRGBBitmap(c.x, c.y + yy, row.data(), min((int) wh[0], W - c.x), 1); }
                     f.close(); }
        }
        return;
    }
    if (t == "hotspot") return;
    restoreRect(c.x, c.y, c.w, c.h);                        // unknown: leave the background
}
static void drawPage() {
    if (page.bgMode == 2 && bgBuf) { memcpy(fbNow, bgBuf, W * H * 2); if (fbNow == screenFb) Cache_WriteBack_Addr((uint32_t) fbNow, W * H * 2); }
    else if (page.bgMode == 1) gfx->fillScreen(page.bgColor);
    /* bgMode 0: leave the screen as it is and draw over it */
    for (auto &c : page.comps) drawComp(c);
    fillMemo.valid = false;
    dirtyN = 0; present(0, 0, W, H); lastPresentMs = millis();   // the whole page in one move, now
}
// Nextion z-order: components paint in id order, so whatever was drawn AFTER a repainted one sits on
// top of it and must come back too (the popup's OK button lives inside the dialog box: repainting the
// box for its new text used to bury the button). The area grows as stacked components are redrawn.
static bool showsIn(const Comp &o, int x, int y, int w, int h) {
    if (!o.vis || o.w <= 0 || o.h <= 0) return false;
    if (o.type == "variable" || o.type == "timer" || o.type == "audio" || o.type == "hotspot") return false;
    return o.x < x + w && o.x + o.w > x && o.y < y + h && o.y + o.h > y;
}
static void drawAbove(int idx, int &x, int &y, int &w, int &h) {   // grows the area to what got repainted
    for (int j = idx + 1; j < (int) page.comps.size(); ++j) {
        Comp &o = page.comps[j];
        if (!showsIn(o, x, y, w, h)) continue;
        drawComp(o);
        const int nx = min(x, o.x), ny = min(y, o.y);
        w = max(x + w, o.x + o.w) - nx; h = max(y + h, o.y + o.h) - ny; x = nx; y = ny;
    }
}
static int indexOf(const Comp &c) { const long i = &c - page.comps.data(); return (i >= 0 && i < (long) page.comps.size()) ? (int) i : (int) page.comps.size(); }
static void redraw(Comp &c) {
    if (loadingPage || noDraw) return;
    drawComp(c);
    int x = c.x, y = c.y, w = c.w, h = c.h;
    drawAbove(indexOf(c), x, y, w, h);
    if (c.type == "combobox" && c.open) {                   // its list sits on top of everything
        int lx, ly, lw, lh; comboListRect(c, lx, ly, lw, lh);
        drawComboList(c);
        const int nx = min(x, lx), ny = min(y, ly); w = max(x + w, lx + lw) - nx; h = max(y + h, ly + lh) - ny; x = nx; y = ny;
    }
    memoTouched(x, y, w, h); dirty(x, y, w, h);
}
static void needRedraw() { for (auto &c : page.comps) if (!c.need.empty() && c.vis) redraw(c); }
static void repaintHole(int x, int y, int w, int h) { if (loadingPage || noDraw) return; restoreRect(x, y, w, h); drawAbove(-1, x, y, w, h); memoTouched(x, y, w, h); dirty(x, y, w, h); }
// A TextSelect's option list (its "path"): one option per line.
static void setOptions(Comp &c, const std::string &s) {
    c.options = textLines(s, c.font, 0, false);
    if (c.val < 0 || c.val >= (int) c.options.size()) c.val = 0;
    c.scroll = 0; listShowSelected(c);
}

// ------------------------------------------------------------------ pages not on screen
// The keyboard pages address their caller's box as p[page].b[id]: name, type and txt_maxl come from
// the page file on the card, read once per page and kept.
struct CompInfo { int id; std::string name; int typeCode; int txtMaxl; bool global; int32_t val; std::string txt; };   // (val, txt: as the page file has them: a global's value before anything wrote it)
static std::map<std::string, std::vector<CompInfo>> pageInfo;
static const std::vector<CompInfo> *infoFor(const std::string &pg) {
    auto it = pageInfo.find(pg); if (it != pageInfo.end()) return &it->second;
    auto pid = pageIds.find(pg); if (pid == pageIds.end() || !sdOk) return nullptr;
    char path[32]; snprintf(path, sizeof(path), "/hmi/pages/%d.json", pid->second);
    File f = SD.open(path); if (!f) return nullptr;
    JsonDocument filter; filter["comps"][0]["n"] = true; filter["comps"][0]["i"] = true; filter["comps"][0]["t"] = true; filter["comps"][0]["a"]["txt_maxl"] = true;
    filter["comps"][0]["g"] = true; filter["comps"][0]["val"] = true; filter["comps"][0]["txt"] = true;
    JsonDocument doc; DeserializationError err = deserializeJson(doc, f, DeserializationOption::Filter(filter)); f.close();
    if (err) return nullptr;
    std::vector<CompInfo> v;
    for (JsonObject j : doc["comps"].as<JsonArray>()) v.push_back({ j["i"] | 0, std::string(j["n"] | ""), typeCodeOf(j["t"] | ""), j["a"]["txt_maxl"] | 0, (j["g"] | "l")[0] == 'g', j["val"] | 0, std::string(j["txt"] | "") });
    pageInfo[pg] = v;
    return &pageInfo[pg];
}
static const CompInfo *infoOf(const std::string &pg, const std::string &nm) { const std::vector<CompInfo> *v = infoFor(pg); if (v) for (auto &ci : *v) if (ci.name == nm) return &ci; return nullptr; }
// ------------------------------------------------------------------ script host
static void runScript(const std::string &code, const std::string &self);
struct Host : public NextionHost {
    Comp *get(const std::string &pg, const std::string &nm, bool &offPage) {
        offPage = !pg.empty() && pg != page.name;
        if (offPage) return nullptr;
        return find(nm);
    }
    int32_t getInt(const std::string &pg, const std::string &nm, const std::string &attr) override {
        bool off; Comp *c = get(pg, nm, off);
        if (off || !c) {
            if (attr == "type" || attr == "txt_maxl" || attr == "id") { const CompInfo *ci = infoOf(pg.empty() ? page.name : pg, nm); if (!ci) return 0; return attr == "type" ? ci->typeCode : attr == "id" ? ci->id : ci->txtMaxl; }
            auto &k = kept[(pg.empty() ? page.name : pg) + "." + nm]; auto it = k.ints.find(attr);
            if (it != k.ints.end()) return it->second;
            // never written: a global's value is what its page file gives it, as on a Nextion (screen 1.9.4: Pong's score boxes
            // take their colours from FrontView.ForeGround before the main board has said, and came out black on black)
            if (attr == "val") { const CompInfo *ci = infoOf(pg.empty() ? page.name : pg, nm); if (ci && ci->global) return ci->val; }
            return 0;
        }
        if (attr == "val") return c->val; if (attr == "pco") return c->pco; if (attr == "bco") return c->bco; if (attr == "pco2") return c->pco2; if (attr == "bco2") return c->bco2;
        if (attr == "x") return c->x; if (attr == "y") return c->y; if (attr == "w") return c->w; if (attr == "h") return c->h; if (attr == "pic") return c->pic; if (attr == "pic2") return c->pic2;
        if (attr == "font") return c->font; if (attr == "en") return c->en; if (attr == "tim") return c->tim; if (attr == "lenth") return c->lenth;
        if (attr == "val_y") return c->scroll;                                              // slide text: how far it is scrolled
        if (attr == "maxval_y") { if (c->type == "sltext") { const int fh = fontHeight(c->font); return max(0, (int) textLines(c->txt, c->font, c->w - 2 * c->borderw - 4, c->isbr != 0).size() * fh - (c->h - 2 * c->borderw)); } return 0; }
        if (attr == "type") return c->typeCode; if (attr == "txt_maxl") return c->txtMaxl; if (attr == "id") return c->id; if (attr == "dis") return c->dis; if (attr == "key") return c->key;
        auto it = c->extra.find(attr); return it == c->extra.end() ? 0 : it->second;
    }
    void setInt(const std::string &pg, const std::string &nm, const std::string &attr, int32_t v) override {
        // "FrontView.pic=Screen_Background": the page object itself — its background picture.
        if (nm == page.name && attr == "pic") {
            page.bgPic = v; page.bgMode = 2;
            if (!loadingPage) { loadBackground(v); drawPage(); }      // preinit sets it before the first paint: no extra repaint
            return;
        }
        bool off; Comp *c = get(pg, nm, off);
        kept[(pg.empty() ? page.name : pg) + "." + nm].ints[attr] = v;          // remembered for globals / off-page writes
        if (attr == "val") {                                                     // a global variable's value: through our own restart too
            static const int VAR_CODE = typeCodeOf("variable");
            bool globalVar = false;
            if (c) globalVar = c->global && c->typeCode == VAR_CODE;
            else { const CompInfo *ci = infoOf(pg.empty() ? page.name : pg, nm); globalVar = ci && ci->global && ci->typeCode == VAR_CODE; }
            if (globalVar) rtcGlobalNote((pg.empty() ? page.name : pg) + "." + nm, v);
        }
        if (off || !c) return;
        if (!c->damaged && c->type != "textselect" && c->type != "combobox" && c->type != "sltext" && c->type != "slider" &&
            ((attr == "val" && c->val == v) || (attr == "pco" && c->pco == v) || (attr == "bco" && c->bco == v) || (attr == "pco2" && c->pco2 == v) || (attr == "bco2" && c->bco2 == v) ||
             (attr == "font" && c->font == v) || (attr == "pic" && c->pic == v) || (attr == "x" && c->x == v) || (attr == "y" && c->y == v))) { perfSkipped++; return; }
        bool paint = true;
        if (attr == "val") { c->val = v; if (c->type == "textselect") { if (v >= 0 && v < (int) c->options.size()) c->txt = c->options[v]; listShowSelected(*c); }
                             if (c->type == "combobox" && v >= 0 && v < (int) c->options.size()) c->extra["hl"] = v; }
        else if (attr == "pco" || attr == "bco" || attr == "pco2" || attr == "bco2") {   // (white put back on a panel is the pilot's writing colour again)
            const int f = attr == "pco" ? ldrc::TF_PCO : attr == "bco" ? ldrc::TF_BCO : attr == "pco2" ? ldrc::TF_PCO2 : ldrc::TF_BCO2;
            (f == ldrc::TF_PCO ? c->pco : f == ldrc::TF_BCO ? c->bco : f == ldrc::TF_PCO2 ? c->pco2 : c->bco2) = v;
            c->roles = ldrc::themeRoleWritten(c->roles, f, (uint16_t) v); themeComp(*c);
        }
        else if (attr == "x") { repaintHole(c->x, c->y, c->w, c->h); c->x = v; } else if (attr == "y") { repaintHole(c->x, c->y, c->w, c->h); c->y = v; }
        else if (attr == "w") c->w = v; else if (attr == "h") c->h = v; else if (attr == "pic") c->pic = v; else if (attr == "pic2") c->pic2 = v; else if (attr == "font") c->font = v;
        else if (attr == "val_y") c->scroll = max(0, (int) v);
        else if (attr == "en") { c->en = v; paint = false; } else if (attr == "tim") { c->tim = v; paint = false; }
        else { c->extra[attr] = v; paint = false; }
        if (paint) redraw(*c);
    }
    std::string getTxt(const std::string &pg, const std::string &nm) override {
        bool off; Comp *c = get(pg, nm, off);
        if (off || !c) {
            auto &k = kept[(pg.empty() ? page.name : pg) + "." + nm]; auto it = k.txts.find("txt");
            if (it != k.txts.end()) return it->second;
            const CompInfo *ci = infoOf(pg.empty() ? page.name : pg, nm); return ci && ci->global ? ci->txt : std::string();   // (never written: as the page file has it)
        }
        if (c->type == "textselect" && c->val >= 0 && c->val < (int) c->options.size()) return c->options[c->val];   // the chosen item
        return c->txt;
    }
    // "MMems.path=..." — a list's options; for an external picture, the image file the Teensy wants shown.
    void setPath(const std::string &pg, const std::string &nm, const std::string &s) {
        bool off; Comp *c = get(pg, nm, off);
        kept[(pg.empty() ? page.name : pg) + "." + nm].txts["path"] = s;
        if (nm == "exp0" && (pg.empty() ? page.name : pg) == "FrontView") { strlcpy(rtcPicture, s.c_str(), sizeof(rtcPicture)); rtcPictureMagic = 0x4C444943; }   // (kept through our own restart)
        if (off || !c) return;
        if (c->type == "textselect" || c->type == "combobox") { setOptions(*c, s); redraw(*c); }
        else setTxt(pg, nm, s);
    }
    void setTxt(const std::string &pg, const std::string &nm, const std::string &s) override {
        // The motor's state, from a main board too old to say "ldrcst=" (before 2.5.6 B8). It says it ONCE, when it
        // changes, as "bt0.txt=" whatever page is showing (Motor_sign.h ShowMotor): it is heard here before anything
        // asks whether this page has a bt0. A main board that says "ldrcst=" is believed, and this is not.
        if (nm == "bt0" && (pg.empty() || pg == "FrontView") && s.rfind("Motor is ", 0) == 0) {
            kept["FrontView.bt0"].txts["txt"] = s;                        // (the front page shows it when it comes back)
            const char *why = tx.motorText(s.find(" ON") != std::string::npos);
            if (why) applyRadios(why);
        }
        bool off; Comp *c = get(pg, nm, off);
        kept[(pg.empty() ? page.name : pg) + "." + nm].txts["txt"] = s;
        if (nm == "DateTime" && s.size() > 8) lastDateTime = s;
        if (nm == "StillConnected" && s.find("TURN OFF") != std::string::npos) flightCountdownAt = millis() | 1;   // (the current is written into the same box: the countdown counts until it has stopped coming)
        if (off || !c) return;
        if (!c->damaged && c->txt == s && c->type != "sltext" && c->type != "external picture") { perfSkipped++; return; }
        c->txt = s; if (c->type == "sltext") c->scroll = 0; redraw(*c);
    }
    void send(const uint8_t *b, size_t n) override {
        outBuf.append((const char *) b, n);
        char h[4]; for (size_t i = 0; i < n; ++i) { snprintf(h, sizeof(h), "%02X ", b[i]); sentTrace += h; }
        sentTrace += "| ";
        if (sentTrace.size() > 600) sentTrace.erase(0, sentTrace.size() - 600);
    }
    void click(const std::string &pg, const std::string &nm, bool press) override {
        bool off; Comp *c = get(pg, nm, off); if (off || !c) return;
        if (c->type == "dual-state button" && !press) { c->val = !c->val; keepTouched(*c); redraw(*c); }
        runScript(press ? c->evPress : c->evRelease, nm);
    }
    void vis(const std::string &pg, const std::string &nm, bool on) override {
        bool off; Comp *c = get(pg, nm, off);
        if (off || !c) return;
        if (c->vis && !on) { c->vis = false; repaintHole(c->x, c->y, c->w, c->h); }
        else if (!c->vis && on) { c->vis = true; redraw(*c); }
    }
    void gotoPage(const std::string &name) override;
    void delayMs(uint32_t ms) override { flushOut(); delay(ms); }
    void play(int id, int channel, int loop) override { (void) channel; audioStart(id, loop != 0); }
    std::string pageNameById(int32_t id) override { return id >= 0 && id < (int) pageNames.size() ? pageNames[id] : ""; }
    std::string compNameById(const std::string &pg, int32_t id) override {
        if (pg.empty() || pg == page.name) { for (auto &c : page.comps) if (c.id == id) return c.name; return ""; }
        const std::vector<CompInfo> *v = infoFor(pg); if (v) for (auto &ci : *v) if (ci.id == id) return ci.name;
        return "";
    }
    int32_t getSys(const std::string &name) override { auto it = sys.find(name); return it == sys.end() ? 0 : it->second; }
    bool setSys(const std::string &name, int32_t v) override {                                 // Screen_Background, volume, dim …
        sys[name] = v;
        if (name == "dim" || name == "dims") {
            sysDim = constrain((int) v, 0, 100); rtcDim = sysDim; rtcDimMagic = RTC_DIM_MAGIC;   // (kept through a restart of ours)
            blDark = false;                                    // the Teensy has the light now (its opening page fades in from 1 %)
            if (!quietActive) backlight(updHoldsLight() ? 255 : sysDim * 255 / 100);
        }
        if (name == "volume") { audioSetVolume((int) v); pendingVol = audioVolume; }   // sent once at the Teensy's boot: survive ours
        if (name == "Screen_Background") pendingBg = v;    // the Teensy sends it once at ITS boot; survive OURS
        return true;
    }
    std::map<std::string, int32_t> sys;
    void unknownCommand(const std::string &line) override {
        // "ldrc <word>": a button of our own, added to a page by hmi/overrides.json. Nothing goes to the Teensy.
        if (line.rfind("ldrc ", 0) == 0) { if (line == "ldrc update") updRequested = true; else if (line == "ldrc rxupdate") rxUpdRequested = true; else if (line == "ldrc wifi") wifiRequested = true; else if (line == "ldrc flight") flightRequested = true; else if (line == "ldrc colours") coloursRequested = true; else if (line == "ldrc appearance") appearanceRequested = true; else if (line == "ldrc defined") flightDefinedRequested = true; return; }
        unknownFromTeensy(line);
    }
    void unknownFromTeensy(const std::string &line) { badCount++; oddTrace += "script:" + line + " | "; if (oddTrace.size() > 400) oddTrace.erase(0, oddTrace.size() - 400); }
};
static Host host;
static void flushOut() { if (!outBuf.empty()) { Serial.write((const uint8_t *) outBuf.data(), outBuf.size()); outBuf.clear(); } }
static void runScript(const std::string &code, const std::string &self) {
    if (code.empty()) return;
    NextionScript sc(host, page.name);
    scriptDepth++;
    sc.run(code, self);
    // The Teensy takes a touch event as the bytes that arrive with no gap over 20 us (GetTextIn), and the
    // Nextion emits an event's output in one burst. Three separate prints with interpreter work between
    // them split into three messages: the help page's scroll position 199 then read as button code 71,
    // "Reset clock?". One write per event keeps the bytes contiguous.
    if (--scriptDepth == 0) flushOut();
}

// ------------------------------------------------------------------ page loading
// THE SCREEN SAVER'S MEMORY (screen 1.4.3; Malcolm, 1-10-2026: "if the screen times out and goes blank, a touch should
// really return to the screen that was in use at the timeout moment"). When the main board blanks the screen (page
// BlankView), the page that was showing is remembered exactly as it was - every value, text, colour, position, what was
// shown or hidden, how far a list was scrolled, whether a timer ran - including what was changed by touch and not yet
// confirmed. If the very next page is that same page again (the main board's restore), it comes back as it was, before
// its init scripts run. Any other page throws the memory away: it is never applied to a later, ordinary visit.
struct SaverComp { std::string name, txt; int32_t val; int pco, bco, pco2, bco2, x, y, scroll, pic, en; bool vis; };
static std::string saverPage;                              // "" = nothing remembered
static std::vector<SaverComp> saverComps;
static void saverRemember() {
    saverPage = page.name; saverComps.clear();
    for (const auto &c : page.comps) {
        SaverComp k; k.name = c.name; k.txt = c.txt; k.val = c.val; k.pco = c.pco; k.bco = c.bco; k.pco2 = c.pco2; k.bco2 = c.bco2;
        k.x = c.x; k.y = c.y; k.scroll = c.scroll; k.pic = c.pic; k.en = c.en; k.vis = c.vis;
        saverComps.push_back(k);
    }
}
static void saverApply(Page &np) {
    for (const auto &k : saverComps) {
        auto b = np.byName.find(k.name); if (b == np.byName.end()) continue;
        Comp &c = np.comps[b->second];
        c.txt = k.txt; c.val = k.val; c.pco = k.pco; c.bco = k.bco; c.pco2 = k.pco2; c.bco2 = k.bco2;
        c.x = k.x; c.y = k.y; c.scroll = k.scroll; c.pic = k.pic; c.en = k.en; c.vis = k.vis;
    }
}
static bool loadPage(const std::string &name) {
    auto it = pageIds.find(name); if (it == pageIds.end() || !sdOk) return false;
    // (the screen saver's memory: taken as the screen blanks, used only by the restore that follows it)
    const bool restoring = !saverPage.empty() && page.name == "BlankView" && name == saverPage;
    if (name == "BlankView" && page.name != "BlankView" && !page.name.empty()) saverRemember();
    else if (!restoring && page.name == "BlankView") { saverPage.clear(); saverComps.clear(); }
    if (!page.evExit.empty()) runScript(page.evExit, "");
    char path[32]; snprintf(path, sizeof(path), "/hmi/pages/%d.json", it->second);
    File f = SD.open(path); if (!f) return false;
    const size_t n = f.size(); char *raw = (char *) ps_malloc(n + 1); if (!raw) { f.close(); return false; }
    const size_t got = f.read((uint8_t *) raw, n); raw[got] = 0; f.close();   // one read, then parse from memory (a File stream parses a byte at a time)
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, (const char *) raw, got); free(raw);
    if (err) return false;
    Page np; np.name = name; np.id = it->second;
    JsonObject bg = doc["bg"];
    if (!bg.isNull()) {
        std::string mode = bg["mode"] | "";
        np.bgPic = bg["picture"] | -1; np.bgColor = bg["rgb565"] | 0;
        np.bgMode = mode == "image" ? 2 : mode == "solid colour" ? 1 : 0;      // 0 = "no background": a popup over whatever is there
    }
    JsonObject ev = doc["ev"];
    np.evPre = ev["preinitialize"] | ""; np.evPost = ev["postinitialize"] | ""; np.evPress = ev["touch_press"] | ""; np.evRelease = ev["touch_release"] | ""; np.evExit = ev["page_exit"] | "";
    for (JsonObject j : doc["comps"].as<JsonArray>()) {
        Comp c; c.name = j["n"] | ""; c.id = j["i"] | 0; c.type = j["t"] | ""; c.global = (j["g"] | "l")[0] == 'g';
        c.x = j["x"] | 0; c.y = j["y"] | 0; c.w = j["w"] | 0; c.h = j["h"] | 0; c.font = j["font"] | 0; c.sta = j["sta"] | 3;
        JsonObject col = j["c"]; c.pco = col["pco"] | 65535; c.bco = col["bco"] | 0; c.pco2 = col["pco2"] | 65535; c.bco2 = col["bco2"] | 0; c.borderc = col["borderc"] | 0; c.pco1 = col["pco1"] | 0xC618;
        JsonObject pic = j["pic"]; c.pic = pic["pic"] | -1; c.pic2 = pic["pic2"] | -1;
        c.txt = j["txt"] | ""; c.val = j["val"] | 0;
        JsonObject a = j["a"]; c.xcen = a["xcen"] | 0; c.ycen = a["ycen"] | 0; c.borderw = a["borderw"] | 0; c.lenth = a["lenth"] | 0; c.dez = a["dez"] | 0;
        c.wid = a["wid"] | 20; c.hig = a["hig"] | 20; c.maxval = a["maxval"] | 100; c.minval = a["minval"] | 0; c.mode = a["mode"] | 0; c.tim = a["tim"] | 0; c.en = a["en"] | 0; c.isbr = a["isbr"] | 0;
        c.key = a["key"] | 255; c.txtMaxl = a["txt_maxl"] | 0; c.dis = a["dis"] | 0; c.typeCode = typeCodeOf(c.type);
        c.dir = a["dir"] | 1; c.bco1 = col["bco1"] | 65535; c.pco3 = col["pco3"] | 0x8410; c.style = a["style"] | 0;
        c.roles = ldrc::themeRoles(c.bco, c.bco2, c.pco, c.pco2, c.borderc);   // (from the page's own colours)
        c.centre = j["centre"] | false;
        for (JsonVariant o : j["opt"].as<JsonArray>()) c.options.push_back(o.as<std::string>());
        if (!c.options.empty() && c.options.back().empty()) c.options.pop_back();      // the editor keeps the final line break as an empty option
        JsonObject e = j["ev"]; c.evPress = e["p"] | ""; c.evRelease = e["r"] | ""; c.evMove = e["m"] | ""; c.evTimer = e["t"] | "";
        c.need = j["need"] | "";
        // Globals keep their values across page loads; so do writes made while the page was away.
        // A box marked "fresh" in its page file starts from the page's own text at every load, as a Nextion's local
        // boxes do: the Teensy fills it while the page shows and never puts the page's text back (screen 1.5.6: the
        // trim-direction page came back saying "Aileron trim is defined!" before any trim was pushed).
        if (j["fresh"] | false) kept.erase(name + "." + c.name);
        auto k = kept.find(name + "." + c.name);
        if (k != kept.end() && (c.global || true)) {
            auto &ki = k->second.ints;
            if (ki.count("val")) c.val = ki["val"];   // (vis is NOT kept: a page load shows everything again, as the Nextion does — MsgBox hides Cancel, the next confirmation needs it back)
            if (ki.count("bco")) { c.bco = ki["bco"]; c.roles = ldrc::themeRoleWritten(c.roles, ldrc::TF_BCO, (uint16_t) c.bco); }
            if (ki.count("pco")) { c.pco = ki["pco"]; c.roles = ldrc::themeRoleWritten(c.roles, ldrc::TF_PCO, (uint16_t) c.pco); }
            if (ki.count("bco2")) { c.bco2 = ki["bco2"]; c.roles = ldrc::themeRoleWritten(c.roles, ldrc::TF_BCO2, (uint16_t) c.bco2); }
            if (ki.count("pco2")) { c.pco2 = ki["pco2"]; c.roles = ldrc::themeRoleWritten(c.roles, ldrc::TF_PCO2, (uint16_t) c.pco2); }
            if (ki.count("x")) c.x = ki["x"]; if (ki.count("y")) c.y = ki["y"]; if (ki.count("pic")) c.pic = ki["pic"];
            if (k->second.txts.count("txt")) c.txt = k->second.txts["txt"];
            if (k->second.txts.count("path") && c.type == "external picture") c.txt = k->second.txts["path"];   // a picture named before its page was shown (B22: "ImageView.exp0.path=")
            if (k->second.txts.count("path") && (c.type == "textselect" || c.type == "combobox")) { setOptions(c, k->second.txts["path"]); if (ki.count("val")) { c.val = ki["val"]; listShowSelected(c); } }
        }
        themeComp(c);
        np.byName[c.name] = np.comps.size(); np.comps.push_back(c);
    }
    if (restoring) { saverApply(np); saverPage.clear(); saverComps.clear(); }
    page = np;
    touchNote("page " + name);
    touchLockout = true;
    strlcpy(rtcPage, name.c_str(), sizeof(rtcPage)); rtcMagic = 0x4C445243;   // our own restart comes back to this page
    picPageLoaded();                                       // (Malcolm, 10-03: the old picture page flashed up before the new chooser covered it)
    // Nextion order: preinitialize (may vis/colour things, choose the background) -> ONE paint -> postinitialize.
    loadingPage = true;
    runScript(page.evPre, "");
    loadingPage = false;
    if (page.bgMode == 2) loadBackground(page.bgPic);
    flightPageLoaded();                                    // (after preinitialize, which hides what the front page shows only with news)
    coloursPageLoaded();
    appearancePageLoaded();
    drawPage();
    runScript(page.evPost, "");
    return true;
}
void Host::gotoPage(const std::string &name) { loadPage(name); }

// ------------------------------------------------------------------ drawing verbs (line, fill, draw, cir, cirs, xstr, pic, cls)
// The Teensy draws the curves, the scan display and the like itself. Each verb paints the canvas and
// grows a dirty rectangle; the panel gets it in one move when the burst has been read.
static void damage(int x, int y, int w, int h) {             // components under a drawing must repaint at their next set, same value or not
    for (auto &c : page.comps) if (c.x < x + w && c.x + c.w > x && c.y < y + h && c.y + c.h > y) c.damaged = true;
}
static void drewArea(int x, int y, int w, int h) { dirty(x, y, w, h); memoOp(0, x, y, w, h, x, y, w, h); damage(x, y, w, h); }
static int colourOf(const std::string &t) {
    static const struct { const char *n; int v; } names[] = { { "RED", 63488 }, { "BLUE", 31 }, { "GRAY", 33840 }, { "BLACK", 0 }, { "WHITE", 65535 }, { "GREEN", 2016 }, { "BROWN", 48192 }, { "YELLOW", 65504 } };
    for (auto &e : names) if (t == e.n) return e.v;
    return atoi(t.c_str());
}
static int splitArgs(const std::string &args, std::string out[], int maxN) {   // commas outside quotes
    int n = 0; std::string cur; bool q = false;
    for (char ch : args) {
        if (ch == '"') { q = !q; cur.push_back(ch); }
        else if (ch == ',' && !q && n < maxN - 1) { out[n++] = cur; cur.clear(); }
        else cur.push_back(ch);
    }
    out[n++] = cur;
    for (int i = 0; i < n; ++i) { size_t a = out[i].find_first_not_of(' '), b = out[i].find_last_not_of(' '); out[i] = a == std::string::npos ? "" : out[i].substr(a, b - a + 1); }
    return n;
}
static bool drawVerb(const std::string &cmd) {
    const size_t sp = cmd.find(' '); if (sp == std::string::npos) return false;
    const std::string verb = cmd.substr(0, sp);
    if (verb != "line" && verb != "fill" && verb != "draw" && verb != "cir" && verb != "cirs" && verb != "cls" && verb != "pic" && verb != "xstr") return false;
    if (noDraw || loadingPage) return true;
    std::string a[12]; const int n = splitArgs(cmd.substr(sp + 1), a, 12);
    auto I = [&](int i) { return i < n ? atoi(a[i].c_str()) : 0; };
    if (verb == "line" && n >= 5) {
        const int x1 = I(0), y1 = I(1), x2 = I(2), y2 = I(3), bx = min(x1, x2), by = min(y1, y2), bw = abs(x2 - x1) + 1, bh = abs(y2 - y1) + 1;
        gfx->drawLine(x1, y1, x2, y2, colourOf(a[4]));
        dirtyLine(x1, y1, x2, y2); memoOp(1, x1, y1, x2, y2, bx, by, bw, bh); damage(bx, by, bw, bh);
    }
    else if (verb == "fill" && n >= 5) {
        const int x = I(0), y = I(1), w = I(2), h = I(3), col = colourOf(a[4]);
        if (fillMemo.valid && x == fillMemo.x && y == fillMemo.y && w == fillMemo.w && h == fillMemo.h && col == fillMemo.colour) {
            for (auto &op : fillMemo.ops) { if (op.kind == 1) eraseLine(op.a, op.b, op.c, op.d); else eraseArea(op.a, op.b, op.c, op.d); }
            fillMemo.ops.clear(); perfFillInc++;
        } else {
            gfx->fillRect(x, y, w, h, col); dirty(x, y, w, h); perfFillFull++;
            if ((long) w * h >= 20000) { fillMemo.x = x; fillMemo.y = y; fillMemo.w = w; fillMemo.h = h; fillMemo.colour = col; fillMemo.valid = true; fillMemo.ops.clear(); }
            else memoOp(0, x, y, w, h, x, y, w, h);
        }
        damage(x, y, w, h);
    }
    else if (verb == "draw" && n >= 5) {                     // a box outline: its four edges, not its whole area
        const int x = min(I(0), I(2)), y = min(I(1), I(3)), w = abs(I(2) - I(0)) + 1, h = abs(I(3) - I(1)) + 1;
        gfx->drawRect(x, y, w, h, colourOf(a[4]));
        drewArea(x, y, w, 1); drewArea(x, y + h - 1, w, 1); drewArea(x, y, 1, h); drewArea(x + w - 1, y, 1, h);
    }
    else if (verb == "cirs" && n >= 4) { gfx->fillCircle(I(0), I(1), I(2), colourOf(a[3])); drewArea(I(0) - I(2) - 1, I(1) - I(2) - 1, 2 * I(2) + 3, 2 * I(2) + 3); }
    else if (verb == "cir" && n >= 4) { gfx->drawCircle(I(0), I(1), I(2), colourOf(a[3])); drewArea(I(0) - I(2) - 1, I(1) - I(2) - 1, 2 * I(2) + 3, 2 * I(2) + 3); }
    else if (verb == "cls" && n >= 1) { gfx->fillScreen(colourOf(a[0])); fillMemo.valid = false; dirty(0, 0, W, H); damage(0, 0, W, H); }
    else if (verb == "pic" && n >= 3 && sdOk) {
        char path[32]; snprintf(path, sizeof(path), "/hmi/pic/%d.565", I(2));
        File f = SD.open(path);
        if (f) { uint16_t wh[2]; f.read((uint8_t *) wh, 4); std::vector<uint16_t> row(wh[0]);
                 for (int yy = 0; yy < wh[1] && I(1) + yy < H; ++yy) { f.read((uint8_t *) row.data(), wh[0] * 2); gfx->draw16bitRGBBitmap(I(0), I(1) + yy, row.data(), min((int) wh[0], W - I(0)), 1); }
                 f.close(); drewArea(I(0), I(1), wh[0], wh[1]); }
    }
    else if (verb == "xstr" && n >= 11) {                  // xstr x,y,w,h,font,pco,bco,xcen,ycen,sta,"text"
        std::string t = a[10]; if (t.size() >= 2 && t.front() == '"' && t.back() == '"') t = t.substr(1, t.size() - 2);
        if (I(9) == 1) gfx->fillRect(I(0), I(1), I(2), I(3), colourOf(a[6])); else if (I(9) == 0 || I(9) == 2) restoreRect(I(0), I(1), I(2), I(3));
        drawTextIn(I(0), I(1), I(2), I(3), I(4), colourOf(a[5]), t, I(7), I(8));
        drewArea(I(0), I(1), I(2), I(3));
    }
    return true;
}

// ------------------------------------------------------------------ Nextion serial protocol (the Teensy side)
static void reply(uint8_t code) { const uint8_t f[4] = { code, 0xFF, 0xFF, 0xFF }; Serial.write(f, 4); }
static void splitRef(const std::string &ref, std::string &pg, std::string &nm) { size_t d = ref.find('.'); if (d == std::string::npos) { pg = ""; nm = ref; } else { pg = ref.substr(0, d); nm = ref.substr(d + 1); } }
static void handle(const std::string &cmd) {
    cmdCount++;
    if (cmd.rfind("pong=", 0) == 0) { pongCommand(cmd.substr(5)); return; }   // the main board's Pong, once a frame: ours to draw (src/pong_device.h), before the script sees it as a system variable
    recent[recentN++ % 64] = cmd;
    if (cmd.rfind("Ch", 0) != 0 && cmd.rfind("J", 0) != 0 && cmd.rfind("TXBV", 0) != 0 && cmd.rfind("RXBV", 0) != 0 && cmd.rfind("vis Warning", 0) != 0) blog("<", cmd);
#ifdef EMU_ECHO
    Serial.printf("[%lu:%s]\n", (unsigned long) cmdCount, cmd.c_str());
#endif
    if (cmd.rfind("page ", 0) == 0) {
        std::string p = cmd.substr(5);
        if (!p.empty() && isdigit((unsigned char) p[0])) { int n = atoi(p.c_str()); if (n < (int) pageNames.size()) p = pageNames[n]; }
        if (!loadPage(p)) badCount++;
        return;
    }
    if (cmd.rfind("vis ", 0) == 0) { size_t c = cmd.find(','); if (c == std::string::npos) { badCount++; return; } std::string pg, nm; splitRef(cmd.substr(4, c - 4), pg, nm); host.vis(pg, nm, cmd[c + 1] != '0'); return; }
    if (cmd.rfind("click ", 0) == 0) { size_t c = cmd.find(','); if (c == std::string::npos) { badCount++; return; } std::string pg, nm; splitRef(cmd.substr(6, c - 6), pg, nm); host.click(pg, nm, cmd[c + 1] == '1'); return; }
    if (cmd.rfind("findfile ", 0) == 0) {                 // findfile "sd0/images/Yak.jpg",sys0 -> 1 if that file is on our card (as .565)
        const size_t q1 = cmd.find('"'), q2 = q1 == std::string::npos ? std::string::npos : cmd.find('"', q1 + 1);
        const size_t c = q2 == std::string::npos ? std::string::npos : cmd.find(',', q2);
        if (c == std::string::npos) { badCount++; return; }
        std::string path = cmd.substr(q1 + 1, q2 - q1 - 1), var = cmd.substr(c + 1);
        if (path.rfind("sd0", 0) == 0) path = path.substr(3);
        if (!path.empty() && path[0] != '/') path = "/" + path;
        const size_t dotp = path.find_last_of('.');
        if (dotp != std::string::npos) { std::string ext = path.substr(dotp); for (auto &ch : ext) ch = tolower(ch); if (ext == ".jpg" || ext == ".jpeg" || ext == ".png" || ext == ".bmp") path = path.substr(0, dotp) + ".565"; }
        if (path.rfind("/images/", 0) == 0 && path.find('/', 8) == std::string::npos && path.size() > 12 && path.compare(path.size() - 4, 4, ".565") == 0)
            path = imagePath(path.substr(8, path.size() - 12));      // (the pilot's own photo first)
        host.setSys(var, (sdOk && SD.exists(path.c_str())) ? 1 : 0);
        blog("findfile", path + (host.getSys(var) ? " FOUND" : " missing"));
        return;
    }
    if (cmd.rfind("get ", 0) == 0) {
        std::string ref = cmd.substr(4); size_t dot = ref.rfind('.');
        if (dot == std::string::npos) {                    // get sys0 — a system variable
            const int32_t v = host.getSys(ref); const uint8_t f[8] = { 'q', (uint8_t) v, (uint8_t) (v >> 8), (uint8_t) (v >> 16), (uint8_t) (v >> 24), 0xFF, 0xFF, 0xFF }; Serial.write(f, 8);
            blog(">", ref + "=" + std::to_string((long) v));
            char b[24]; snprintf(b, sizeof(b), "q%ld | ", (long) v); sentTrace += b; if (sentTrace.size() > 600) sentTrace.erase(0, sentTrace.size() - 600);
            return;
        }
        std::string attr = ref.substr(dot + 1), pg, nm; splitRef(ref.substr(0, dot), pg, nm);
        if (attr == "txt") { std::string s = host.getTxt(pg, nm); std::string f = "p" + s; f += "\xFF\xFF\xFF"; Serial.write((const uint8_t *) f.data(), f.size()); sentTrace += "p\"" + s + "\" | "; }
        else { int32_t v = host.getInt(pg, nm, attr); const uint8_t f[8] = { 'q', (uint8_t) v, (uint8_t) (v >> 8), (uint8_t) (v >> 16), (uint8_t) (v >> 24), 0xFF, 0xFF, 0xFF }; Serial.write(f, 8); char b[24]; snprintf(b, sizeof(b), "q%ld | ", (long) v); sentTrace += b; }
        if (sentTrace.size() > 600) sentTrace.erase(0, sentTrace.size() - 600);
        return;
    }
    if (drawVerb(cmd)) return;
    if (cmd.rfind("play ", 0) == 0) { int ch = 0, id = 0, lp = 0; if (sscanf(cmd.c_str() + 5, "%d,%d,%d", &ch, &id, &lp) >= 2) host.play(id, ch, lp); return; }
    if (cmd == "sendme") { const uint8_t f[5] = { 0x66, (uint8_t) page.id, 0xFF, 0xFF, 0xFF }; Serial.write(f, 5); return; }
    static const char *ignored[] = { "ref", "bkcmd", "sleep", "thup", "thsp", "cle ", "add ", "rest", "tsw ", "printh", "prints", "print ", "ussp", "delay" };
    for (const char *k : ignored) if (cmd.rfind(k, 0) == 0) return;
    size_t eq = cmd.find('='); size_t dot = cmd.rfind('.', eq);
    if (eq != std::string::npos && dot == std::string::npos) {                       // "Screen_Background=39", "dim=80", "volume=20"
        std::string name = cmd.substr(0, eq), v = cmd.substr(eq + 1);
        if (!name.empty() && name.find(' ') == std::string::npos && (v.empty() || isdigit((unsigned char) v[0]) || v[0] == '-')) { host.setSys(name, atol(v.c_str())); return; }
    }
    if (eq == std::string::npos || dot == std::string::npos) { badCount++; oddTrace += cmd + " | "; if (oddTrace.size() > 400) oddTrace.erase(0, oddTrace.size() - 400); return; }
    std::string attr = cmd.substr(dot + 1, eq - dot - 1), pg, nm; splitRef(cmd.substr(0, dot), pg, nm);
    std::string v = cmd.substr(eq + 1);
    if (attr == "txt" || attr == "path") {
        if (v.size() >= 2 && v.front() == '"' && v.back() == '"') v = v.substr(1, v.size() - 2);
        if (attr == "path") host.setPath(pg, nm, v); else host.setTxt(pg, nm, v);
    }
    else host.setInt(pg, nm, attr, atol(v.c_str()));
}
// ------------------------------------------------------------------ pages of our own, on the layer above the Teensy's
static bool topReady() {
    if (topFb) return true;
    if (!topCanvas) topCanvas = new Arduino_Canvas(W, H, screen);
    while (!topCanvas->begin(GFX_SKIP_OUTPUT_BEGIN)) {     // no room: give up a background picture that is not showing, and try again
        int old = -1;
        for (size_t i = 0; i < bgCache.size(); ++i) if (bgCache[i].buf != bgBuf && (old < 0 || bgCache[i].used < bgCache[old].used)) old = (int) i;
        if (old < 0) break;
        free(bgCache[old].buf); bgCache.erase(bgCache.begin() + old);
    }
    topFb = topCanvas->getFramebuffer();
    return topFb != nullptr;
}
struct TopDraw {                                           // while one of these lives, gfx draws on our layer
    Arduino_GFX *g; uint16_t *f;
    TopDraw() : g(gfx), f(fbNow) { gfx = topCanvas; fbNow = topFb; }
    ~TopDraw() { gfx = g; fbNow = f; }
};
static void topText(int x, int y, int font, uint16_t col, const std::string &s) { gfx->startWrite(); drawGlyphs(x, y, font, col, s); gfx->endWrite(); }
static std::string topCut(const std::string &s, int font, int maxW) {                 // what fits, with dots if something had to go
    if (textWidth(font, s) <= maxW) return s;
    std::string t = s;
    while (!t.empty() && textWidth(font, t + "...") > maxW) t.erase(t.size() - 1);
    return t + "...";
}

// ------------------------------------------------------------------ the Teensy's card and firmware (LdrcLink)
// The screen can read and write files on the Teensy's SD card and replace the Teensy's firmware, over the
// wire that carries the display protocol (lib/LdrcLink; the Teensy's half is TXV1B include/LinkMode.h).
// The wire is shared: ldrc::Router sorts every byte that arrives into display commands and frames, so the
// display never loses a command while the screen knocks or waits.
struct LinkPort : public ldrc::MasterPort {
    void write(const uint8_t *b, size_t n) override { Serial.write(b, n); }
    uint32_t ms() override { return millis(); }
    void knock() override { Serial.write((const uint8_t *) LDRC_LINK_KNOCK, strlen(LDRC_LINK_KNOCK)); }
};
static void sdMakeFolders(const char *path) {
    char part[128];
    for (size_t i = 1; path[i] && i < sizeof(part) - 1; ++i) { if (path[i] != '/') continue; memcpy(part, path, i); part[i] = 0; if (!SD.exists(part)) SD.mkdir(part); }
}
struct LinkFiles : public ldrc::MasterFiles {
    File f[3]; bool used[3] = { false, false, false };
    bool good(int h) const { return h >= 0 && h < 3 && used[h]; }
    int open(const char *path, bool forWriting) override {
        if (!sdOk) return -1;
        for (int i = 0; i < 3; ++i) {
            if (used[i]) continue;
            if (forWriting) { sdMakeFolders(path); SD.remove(path); }
            f[i] = SD.open(path, forWriting ? FILE_WRITE : FILE_READ);
            if (!f[i] || f[i].isDirectory()) { if (f[i]) f[i].close(); return -1; }
            used[i] = true; return i;
        }
        return -1;
    }
    int read(int h, uint8_t *buf, size_t n) override { return good(h) ? (int) f[h].read(buf, n) : -1; }
    int write(int h, const uint8_t *buf, size_t n) override { return good(h) ? (int) f[h].write(buf, n) : -1; }
    bool seek(int h, uint32_t pos) override { return good(h) && f[h].seek(pos); }
    uint32_t size(int h) override { return good(h) ? (uint32_t) f[h].size() : 0; }
    void close(int h) override { if (good(h)) { f[h].close(); used[h] = false; } }
    bool remove(const char *path) override { return SD.remove(path); }
    bool rename(const char *from, const char *to) override { sdMakeFolders(to); return SD.rename(from, to); }
};
static LinkPort linkPort; static LinkFiles linkFiles;
static ldrc::LinkMaster teensyLink(linkPort, linkFiles);

// ---- The pilot's own files, kept on the screen's card before new firmware goes into the Teensy (and whenever asked):
// /teensy/backup/<number> <the firmware it ran>/  holds models.dat (the models AND the transmitter's settings: its first
// 512 bytes), whatever else is in the card's own folder, mod/*.MOD (the model files he has exported), and about.txt.
// A new folder each time: a copy is never written over an older copy. The newest KEEP_SETS are kept.
static const char KEEP_ROOT[] = "/teensy/backup";
static const int KEEP_SETS = 12;
// A set is a folder called "<four digits> <something>". It is WHOLE once it holds about.txt, which is written when
// every file of the copy has arrived and been read back. A set that is not whole is what a copy that failed left.
static bool keepIsSet(const std::string &name) { return name.size() > 5 && isdigit((unsigned char) name[0]) && isdigit((unsigned char) name[1]) && isdigit((unsigned char) name[2]) && isdigit((unsigned char) name[3]) && name[4] == ' '; }
static bool keepIsWhole(const std::string &name) { return SD.exists((std::string(KEEP_ROOT) + "/" + name + "/about.txt").c_str()); }
static std::vector<std::string> keepSets() {               // their names, the oldest first
    std::vector<std::string> out;
    File d = sdOk ? SD.open(KEEP_ROOT) : File();
    if (d && d.isDirectory()) { File f; while ((f = d.openNextFile())) { if (f.isDirectory() && keepIsSet(f.name())) out.push_back(f.name()); f.close(); } }
    if (d) d.close();
    std::sort(out.begin(), out.end(), [](const std::string &a, const std::string &b) { return atoi(a.c_str()) < atoi(b.c_str()); });
    return out;
}
static std::string keepNewFolder(const std::string &firmwareNow) {
    const std::vector<std::string> sets = keepSets();
    int next = sets.empty() ? 1 : atoi(sets.back().c_str()) + 1;
    std::string fw = firmwareNow.empty() ? std::string("unknown") : firmwareNow;
    for (auto &c : fw) if (c == '/' || c == '\\' || c == ':' || c == '*' || c == '?' || c == '"' || c == '<' || c == '>' || c == '|' || (unsigned char) c < 32) c = '-';
    while (!fw.empty() && (fw.back() == ' ' || fw.back() == '.')) fw.pop_back();      // (FAT drops them: the folder would not be found under its own name)
    if (fw.empty()) fw = "unknown";
    for (;; ++next) {                                         // never a folder that is there already: a copy is never written over a copy
        char b[16]; snprintf(b, sizeof(b), "/%04d ", next % 10000);
        const std::string folder = std::string(KEEP_ROOT) + b + fw.substr(0, 40);
        if (!SD.exists(folder.c_str()) || next > 20000) return folder;
    }
}
static void keepRemoveFolder(const std::string &folder) {   // its files, the files of its folders, then itself
    std::vector<std::string> files, dirs;
    File d = SD.open(folder.c_str());
    if (d && d.isDirectory()) { File f; while ((f = d.openNextFile())) { (f.isDirectory() ? dirs : files).push_back(folder + "/" + f.name()); f.close(); } }
    if (d) d.close();
    for (auto &p : files) SD.remove(p.c_str());
    for (auto &p : dirs) keepRemoveFolder(p);
    SD.rmdir(folder.c_str());
}
static void keepDone(const std::string &folder, const std::string &about) {
    if (!sdOk) return;
    File f = SD.open((folder + "/about.txt").c_str(), FILE_WRITE);
    if (f) { const std::string text = about + (lastDateTime.empty() ? std::string() : "The transmitter's clock said " + lastDateTime + ".\n"); f.write((const uint8_t *) text.data(), text.size()); f.close(); }
    // The oldest go: of the WHOLE sets all but the newest KEEP_SETS, of the others all but the newest three.
    // (Counted together, a dozen copies that failed would have pushed out every copy that had not.)
    std::vector<std::string> whole, half;
    for (auto &name : keepSets()) (keepIsWhole(name) ? whole : half).push_back(name);
    for (size_t i = 0; i + KEEP_SETS < whole.size(); ++i) keepRemoveFolder(std::string(KEEP_ROOT) + "/" + whole[i]);
    for (size_t i = 0; i + 3 < half.size(); ++i) keepRemoveFolder(std::string(KEEP_ROOT) + "/" + half[i]);
}
static std::string keepQueue(const std::string &firmwareNow) {   // the jobs that make a copy; returns where it goes
    const std::string folder = keepNewFolder(firmwareNow);
    teensyLink.keepFolder("/", folder, "");
    teensyLink.mustHold("/models.dat", folder + "/models.dat");      // the models and the settings: if the transmitter has them, we have them, or the job stops
    teensyLink.keepFolder("/mod", folder + "/mod", ".MOD");
    teensyLink.keepFolder("/log", std::string(KEEP_ROOT) + "/log", ".LOG", 4u * 1024u * 1024u, true);   // the logs: one store that grows; only what we do not hold yet
    return folder;
}
static bool linkWasRunning = false; static uint32_t linkResultAt = 0, linkResultUntil = 0, linkRunSince = 0;
static std::string keepPending, keepAbout;               // a copy asked for from the Mac is being made: its folder, and what to note in it

// A panel over whatever page is showing: what is happening, how far it has got, and the one thing not to do.
// It is drawn on our own layer (like the update panel and the WiFi page): the Teensy goes on repainting its page
// underneath, and the panel is whole all the same. (Drawn on the page, it was eaten from underneath in seconds:
// a green shape with a hole where the model's picture had been put back - Malcolm, 30-9-2026.)
static void linkPanel(bool result) {
    const int x = 90, y = 130, w = 620, h = 220;
    if (!topReady()) return;
    TopDraw on;
    const bool bad = teensyLink.failed();
    const uint16_t back = result ? (bad ? 0x8000 : 0x0320) : OUR_PANEL, ink = result ? 0xFFFF : OUR_INK, dim = result ? 0xC618 : OUR_SOFT;
    gfx->fillRect(x, y, w, h, back); gfx->drawRect(x, y, w, h, ink); gfx->drawRect(x + 1, y + 1, w - 2, h - 2, ink);
    const char *title = result ? (bad ? "Transmitter update FAILED" : "Transmitter updated") : "Updating the transmitter";
    clipX0 = x + 8; clipY0 = y + 4; clipX1 = x + w - 8; clipY1 = y + h - 4;
    gfx->startWrite();
    drawGlyphs(x + (w - textWidth(0, title)) / 2, y + 14, 0, ink, title);
    std::string line = result ? teensyLink.result() : teensyLink.stage();
    if (result && line.rfind("FAILED at ", 0) == 0) line = line.substr(10);
    // two lines of 28-point text, broken at a space
    std::string l1 = line, l2;
    if (textWidth(6, l1) > w - 40) { size_t cut = l1.size(); while (cut > 0 && textWidth(6, l1.substr(0, cut)) > w - 40) cut = l1.rfind(' ', cut - 1) == std::string::npos ? 0 : l1.rfind(' ', cut - 1); if (cut) { l2 = l1.substr(cut + 1); l1 = l1.substr(0, cut); } }
    drawGlyphs(x + (w - textWidth(6, l1)) / 2, y + 66, 6, ink, l1);
    if (!l2.empty()) drawGlyphs(x + max(8, (w - textWidth(6, l2)) / 2), y + 98, 6, ink, l2);
    gfx->endWrite();
    if (!result) {
        const uint32_t size = teensyLink.fileSize(), done = teensyLink.fileDone();
        gfx->drawRect(x + 40, y + 140, w - 80, 22, ink);
        if (size) gfx->fillRect(x + 42, y + 142, (int) ((uint64_t) (w - 84) * min(done, size) / size), 18, 0x07E0);
        char b[64]; snprintf(b, sizeof(b), "step %u of %u", (unsigned) min(teensyLink.stepIndex() + 1, teensyLink.stepCount()), (unsigned) teensyLink.stepCount());
        gfx->startWrite(); drawGlyphs(x + 40, y + 172, 2, dim, b);
        const char *warn = "Do not switch off";
        drawGlyphs(x + w - 40 - textWidth(2, warn), y + 172, 2, 0xFFE0, warn); gfx->endWrite();
    }
    clipX0 = 0; clipY0 = 0; clipX1 = W; clipY1 = H;
    topX = x; topY = y; topW = w; topH = h; topWho = 3; topOn = true;
    dirty(x, y, w, h); touchPainted = true;
}
static void linkPanelGone() { if (topOn && topWho == 3) { topOn = false; topWho = 0; dirty(90, 130, 620, 220); touchPainted = true; } }
static void drawPage();
static void linkPoll() {
    static uint32_t lastPanel = 0; static std::string lastStage;
    teensyLink.poll();
    const uint32_t now = millis();
    if (updHasLink()) { linkWasRunning = false; linkResultAt = 0; linkResultUntil = 0; linkPanelGone(); return; }   // "Check for update" has its own panel
    if (teensyLink.running()) {
        if (!linkWasRunning) linkRunSince = now;
        linkWasRunning = true; linkResultUntil = 0;
        // (a job that is over in a second - a hello, a look - shows nothing: only work that goes on)
        if (now - linkRunSince > 1500 && (now - lastPanel > 300 || teensyLink.stage() != lastStage)) { lastPanel = now; lastStage = teensyLink.stage(); linkPanel(false); presentDirty(true); }
        return;
    }
    if (linkWasRunning) {
        linkWasRunning = false; linkPanelGone();
        // The verdict: only when something was changed on the Teensy, or the job failed. A copy, a look, a hello that went well says nothing.
        linkResultAt = (teensyLink.failed() || teensyLink.changedTeensy()) ? now + 1500 : 0;   // the Teensy repaints its front page first; then the verdict goes on top
        if (!keepPending.empty()) {                          // a copy of the pilot's files was part of it
            // (whole = every file of it arrived and was read back, whatever became of the rest of the job)
            if (teensyLink.copiesDone()) { char b[120]; snprintf(b, sizeof(b), "%u files fetched; %u logs were held already. The logs are in %s/log.\n", (unsigned) teensyLink.kept(), (unsigned) teensyLink.held(), KEEP_ROOT); keepDone(keepPending, keepAbout + b); }
            keepPending.clear();
        }
    }
    if (linkResultAt && now >= linkResultAt) { linkResultAt = 0; linkPanel(true); presentDirty(true); linkResultUntil = now + 12000; }
    if (linkResultUntil && now >= linkResultUntil) { linkResultUntil = 0; linkPanelGone(); }
}
static bool linkStart() {                                  // the jobs are queued: go, unless flying
    if (flyingNow()) { teensyLink.clear(); return false; }
    return teensyLink.start();
}

static void pumpSerial() {
    static std::string buf; static int ffs = 0;
    static ldrc::Router router; static ldrc::Frame frame;
    const int waiting = Serial.available();
    if (waiting) { lastRxMs = millis(); if (waiting > perfRxMax) perfRxMax = waiting; }
    while (Serial.available()) {
        uint8_t b = Serial.read();
        const ldrc::Router::What what = router.push(b, millis(), frame);
        if (what == ldrc::Router::WHOLE_FRAME) { buf.clear(); ffs = 0; teensyLink.frameArrived(frame); continue; }
        if (what != ldrc::Router::TO_DISPLAY) continue;
        if (b == 0xFF) {
            if (++ffs == 3) {
                int bits = 0;
                if (ldrc::txStatusCommand(buf.data(), (unsigned) buf.size(), bits)) { const bool modelWas = txStatus >= 0 && (txStatus & TX_MODEL); const char *why = tx.said(bits); if (why) applyRadios(why); if (modelWas != ((bits & TX_MODEL) != 0)) needRedraw(); teensyCommands++; teensyLink.sawDisplayTraffic(); }   // (from the wire only: nothing the Mac sends can say what the transmitter is doing)
                else if (ldrc::rxStatusCommand(buf.data(), (unsigned) buf.size(), rxNews)) { rxNews.atMs = millis(); rxNewsAny = true; teensyCommands++; teensyLink.sawDisplayTraffic(); }
                else if (!buf.empty()) { const uint32_t t0 = micros(); handle(buf); perfHandleUs += micros() - t0; perfCmds++; teensyCommands++; teensyLink.sawDisplayTraffic(); }
                buf.clear(); ffs = 0;
            }
            continue;
        }
        while (ffs) { buf.push_back((char) 0xFF); ffs--; }
        buf.push_back((char) b);
        if (buf.size() > 8192) buf.clear();                   // the models list and a help window run to several kB
    }
}

// Work that takes the loop's time must not starve the wire: a screenshot fetched over a slow WiFi held
// loop() for 33 s, the Teensy heard nothing, left the link, and the job on it failed. Long jobs call
// this as they go: the Teensy's bytes are read and the link's clock is kept.
static void breathe() {
    static bool in = false;
    if (in) return;
    in = true; pumpSerial(); teensyLink.poll(); audioFill(); in = false;
}

// ------------------------------------------------------------------ touch
static uint32_t fakeTouchUntil = 0; static int fakeX = 0, fakeY = 0;   // POST /tap?x=&y=: a finger from the Mac
static void closeCombo(Comp &c) {                        // put back whatever the list covered
    if (!c.open) return;
    c.open = false;
    int lx, ly, lw, lh; comboListRect(c, lx, ly, lw, lh);
    repaintHole(lx, ly, lw, lh); redraw(c);
}
static int hit(int x, int y) {
    for (int i = (int) page.comps.size() - 1; i >= 0; --i) {           // an open drop-down list is on top of everything
        Comp &c = page.comps[i];
        if (c.type != "combobox" || !c.open) continue;
        int lx, ly, lw, lh; comboListRect(c, lx, ly, lw, lh);
        if (x >= lx && x < lx + lw && y >= ly && y < ly + lh) return i;
    }
    for (int i = (int) page.comps.size() - 1; i >= 0; --i) {           // topmost (last drawn) wins
        Comp &c = page.comps[i];
        if (!c.vis) continue;
        if (c.type == "variable" || c.type == "timer" || c.type == "audio") continue;   // (a model's photo IS a target: its release event opens the image chooser)
        if (x >= c.x && x < c.x + c.w && y >= c.y && y < c.y + c.h) return i;
    }
    return -1;
}
static bool scrollable(const Comp &c) { return c.type == "textselect" || c.type == "sltext"; }
static bool sliderTo(Comp &c, int fx, int fy) {           // move the knob to the finger; true when the value changed
    const int range = max(1, c.maxval - c.minval);
    int v;
    if (c.mode == 0) { const int d = max(6, c.h), r = d / 2; v = c.minval + (long) (fx - c.x - r) * range / max(1, c.w - d); }
    else { const int d = max(6, c.w), r = d / 2; v = c.minval + (long) (c.y + c.h - r - fy) * range / max(1, c.h - d); }
    v = constrain(v, c.minval, c.maxval);
    if (v == c.val) return false;
    c.val = v; return true;
}
// A box whose `key` names a keyboard page opens it after its release event, the way the Nextion Editor
// wires it: the keyboard learns the caller page + component ids, edits a copy, and writes back
// p[loadpageid].b[loadcmpid] before `page loadpageid.val` brings the caller back (values are kept).
static void openKeyboard(int key, int compId) {
    std::vector<std::string> kbds;
    for (auto &n : pageNames) if (n.rfind("keybd", 0) == 0) kbds.push_back(n);
    if (key < 1 || key > (int) kbds.size()) return;
    const std::string &kb = kbds[key - 1];
    kept[kb + ".loadpageid"].ints["val"] = page.id;
    kept[kb + ".loadcmpid"].ints["val"] = compId;
    loadPage(kb);
}
static void pollTouch() {
    static bool down = false; static int held = -1; static uint32_t lastSeen = 0, lastRelease = 0;
    static int dragY0 = 0, dragS0 = 0, lastY = 0, lastX = 0; static bool dragged = false; static uint32_t lastDragDraw = 0;
    int16_t x[2], y[2];
    const uint32_t now = millis();
    if (teensyLink.linkOpen() && (!topOn || topWho == 3)) return;   // the Teensy is serving files: a touch must not put bytes among the frames (our own pages send none; the link's panel has no buttons)
    bool pressed;
    if ((int32_t) (fakeTouchUntil - now) > 0) { pressed = true; x[0] = fakeX; y[0] = fakeY; }
    else pressed = touchOk && touch.getPoint(x, y, 2) > 0;
    static bool oursWasUp = false; static uint32_t oursWentAt = 0;
    if (!(updPanelUp() || wifiPageUp() || picPanelUp() || flightUp() || coloursUp() || appearanceUp()) && oursWasUp) {   // our page has just gone: the finger that closed it, and the second tap of a double tap, are not for the page underneath
        oursWasUp = false; oursWentAt = now; touchLockout = true; lastSeen = now;
    }
    if (updPanelUp() || wifiPageUp() || picPanelUp() || flightUp() || coloursUp() || appearanceUp()) {   // a page of our own has the screen
        oursWasUp = true;
        if (down && held >= 0 && held < (int) page.comps.size()) { page.comps[held].pressed = false; }
        down = false; held = -1;
        if (wifiPageUp()) wifiTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        else if (picPanelUp()) picTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        else if (flightUp()) flightTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        else if (coloursUp()) coloursTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        else if (appearanceUp()) appearanceTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        else updTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        return;
    }
    // The page changed under the finger (the main board answers a press at once: a popup's Cancel loads the page it came
    // from while the finger is still down). The press belonged to the page that has gone: its component's place in the
    // list now names some other component on the new page, and the lift must not press that one. (Screen 1.9.2; Malcolm,
    // 10-05: Cancel on the Models page's questions "invokes an unasked for function" - the button at the same place in
    // the new page's list - and so on round, "an endless loop of more and more cancels".)
    if (touchLockout && down) { down = false; held = -1; dragged = false; }
    if (pressed) { lastSeen = now; lastX = x[0]; lastY = y[0]; host.sys["tch0"] = x[0]; host.sys["tch1"] = y[0]; touchPainted = true; }
    else if (down) touchPainted = true;
    // Hold the top-left corner for 1.5 s: radios on/off (a bench control, remembered across power cycles).
    // Hold the top-RIGHT corner for 3 s: the workshop door, open or shut on the network we are on.
    // A corner that has been held is a corner, not a button: whatever lies under the finger (on most pages the Help
    // button) is let go without its release event, and nothing counts until the finger has lifted.
    static uint32_t cornerSince = 0; static bool cornerFired = false;
    static uint32_t doorSince = 0; static bool doorFired = false;
    bool cornerHeld = false;
    if (pressed && x[0] < 48 && y[0] < 48) { if (!cornerSince) { cornerSince = now; cornerFired = false; } else if (!cornerFired && now - cornerSince > 1500) { cornerFired = true; cornerHeld = true; setRadios(!radiosOn); } }
    else if (!pressed) cornerSince = 0;
    if (pressed && x[0] >= W - 48 && y[0] < 48) { if (!doorSince) { doorSince = now; doorFired = false; } else if (!doorFired && now - doorSince > 3000) { doorFired = true; cornerHeld = true; doorToggle(); } }
    else if (!pressed) doorSince = 0;
    if (cornerHeld) {
        if (down && held >= 0 && held < (int) page.comps.size()) { Comp &c = page.comps[held]; c.pressed = false; if (c.type == "button" || c.type == "dual-state button") redraw(c); }
        down = false; held = -1; touchLockout = true; touchPainted = true;
        return;
    }
    // The touch chip drops the odd sample mid-press: a release is only real after 80 ms of nothing.
    const bool up = !pressed && down && now - lastSeen > 80;
    if (pressed && !down) {
        if (touchLockout) return;                             // the finger that changed the page is still down
        if (now - lastRelease < 150) return;                  // a bounce, not a second tap
        if (oursWentAt && now - oursWentAt < 400) return;     // our own page closed a moment ago
        down = true; held = hit(x[0], y[0]); dragY0 = lastY = y[0]; dragged = false;
        // A tap on an open drop-down list picks that row; a tap anywhere else closes any open list.
        if (held >= 0 && page.comps[held].type == "combobox" && page.comps[held].open) {
            Comp &c = page.comps[held];
            int lx, ly, lw, lh; comboListRect(c, lx, ly, lw, lh);
            if (y[0] >= ly && y[0] < ly + lh) {
                int row = (y[0] - ly) / max(1, c.hig), k = 0;
                for (int i = 0; i < (int) c.options.size(); ++i) { if (c.options[i].empty()) continue; if (k++ == row) { c.val = i; c.txt = c.options[i]; c.extra["hl"] = i; keepTouched(c); break; } }
                closeCombo(c); held = -1; return;
            }
        }
        for (auto &o : page.comps) if (o.type == "combobox" && o.open && (int) (&o - page.comps.data()) != held) closeCombo(o);
        if (held >= 0 && needUnmet(page.comps[held])) held = -1;   // greyed out: deaf, and the touch goes to the page (a keep-awake, nothing more)
        if (held >= 0) { Comp &c = page.comps[held]; c.pressed = true; dragS0 = c.scroll; if (c.type == "slider" && sliderTo(c, x[0], y[0])) keepTouched(c); if (c.type == "button" || c.type == "slider") redraw(c); runScript(c.evPress, c.name); }
        else runScript(page.evPress, "");
    } else if (pressed && down && held >= 0 && held < (int) page.comps.size() && page.comps[held].type == "slider") {
        Comp &c = page.comps[held];                          // dragging the knob
        if (now - lastDragDraw > 40 && sliderTo(c, x[0], y[0])) { lastDragDraw = now; keepTouched(c); redraw(c); runScript(c.evMove, c.name); }
    } else if (pressed && down && held >= 0 && held < (int) page.comps.size() && scrollable(page.comps[held])) {
        Comp &c = page.comps[held]; lastY = y[0];               // the finger drags the list / the text
        const int dy = y[0] - dragY0;
        if (abs(dy) > 8) dragged = true;
        if (dragged) {
            const int want = c.type == "sltext" ? constrain(dragS0 - dy, 0, (int) host.getInt("", c.name, "maxval_y")) : listWrap(c, dragS0 - dy);
            if (want != c.scroll && now - lastDragDraw > 40) { c.scroll = want; lastDragDraw = now; redraw(c); }
        }
    } else if (up) {
        down = false; lastRelease = now;
        host.sys["tch2"] = lastX; host.sys["tch3"] = lastY; host.sys["tch0"] = 0; host.sys["tch1"] = 0;   // the curve page reads where the finger lifted
        if (held >= 0 && held < (int) page.comps.size()) {
            Comp &c = page.comps[held]; c.pressed = false;
            if (c.type == "dual-state button") c.val = !c.val;
            if (c.type == "checkbox" || c.type == "switch") c.val = !c.val;
            if (c.type == "radio") c.val = 1;
            if (c.type == "textselect") {
                if (!dragged) c.scroll = listWrap(c, floorDiv(lastY - listBandY(c) + c.scroll, listRowH(c)) * listRowH(c));   // a tap turns the wheel to that row
                listSnap(c);
            }
            if (c.type == "dual-state button" || c.type == "checkbox" || c.type == "switch" || c.type == "radio" || c.type == "textselect") keepTouched(c);   // (the page comes back with it)
            if (c.type == "button" || c.type == "dual-state button" || c.type == "checkbox" || c.type == "switch" || c.type == "radio" || c.type == "textselect") redraw(c);
            const int key = c.key, cid = c.id, idx = held; const std::string pgName = page.name, evRel = c.evRelease, nm = c.name;
            const bool combo = c.type == "combobox";
            if (evRel.find("=44<<8") != std::string::npos) picSoon();   // the Teensy's StartChooseImage: the chooser's frame now, its page in a moment
            runScript(evRel, nm);                             // (may load another page: c is not touched after this)
            if (page.name == pgName) {
                if (key != 255) openKeyboard(key, cid);
                else if (combo && idx < (int) page.comps.size()) { Comp &cb = page.comps[idx]; if (cb.open) closeCombo(cb); else { cb.open = true; redraw(cb); } }
            }
        } else runScript(page.evRelease, "");
        held = -1;
    } else if (!pressed && touchLockout && now - lastSeen > 80) {
        touchLockout = false; down = false; held = -1;        // finger is off: touches count again
    }
}
static void pollTimers() {
    if (teensyLink.linkOpen()) return;
    for (auto &c : page.comps)
        if (c.type == "timer" && c.en && c.tim > 0 && millis() - c.lastTick >= (uint32_t) c.tim) { c.lastTick = millis(); runScript(c.evTimer, c.name); }
}

// ------------------------------------------------------------------ over the air (28-9-2026, Malcolm: "at a very early stage")
// Joins the house WiFi (or the phone hotspot) and offers:
//   firmware      ArduinoOTA — `pio run -e ota -t upload` pushes a build straight in
//   GET  /status  page, command counts, heap
//   POST /cmd     body = a Nextion command (no FF FF FF needed): bench tests without the cable
//   POST /put?path=/hmi/pages/13.json   multipart file upload onto the card: no more card swaps
//   GET  /fb      the framebuffer, raw RGB565 800x480: a screenshot for the developer
//   GET  /ls?path=/hmi                  directory listing
// FLIGHT NOTE: WiFi is a radio next to the nRF24; gate it later (boot window / a menu option).
//
// THE WORKSHOP DOOR. All of the above is for the workshop. The firmware that is published has it SHUT: on a
// club's network, or an open one, anyone could otherwise push firmware into the screen (and read the networks
// it knows), put files on the card, replace the main board's firmware, or type on the page. The pilot opens it
// by holding the TOP RIGHT corner of the screen for three seconds, while joined to a network: it is then open
// on THAT network (its name is remembered), and on no other, until the corner is held again. Only GET /status
// answers while it is shut. A request that changes anything must also carry the header "X-LDRC: 1" (a web page
// open in a browser on the same network cannot send that). Bench builds (-DLDRC_DOORS_OPEN: ota_dev, ota_seed
// and the test builds, none of them ever published) have it open on every network.
static WebServer web(80);
static bool otaReady = false;
static std::string doorSsid;                               // the network on which the door is open ("" = on none)
static bool otaListening = false;
static bool doorOpen() {
#ifdef LDRC_DOORS_OPEN
    return true;
#else
    return !doorSsid.empty() && radiosLive && WiFi.status() == WL_CONNECTED && doorSsid == WiFi.SSID().c_str();
#endif
}
static bool doorPass(bool changes) {
    if (!doorOpen()) { web.send(403, "text/plain", "the workshop door is shut: hold the top right corner of the screen for three seconds"); return false; }
    if (changes && web.header("X-LDRC") != "1") { web.send(403, "text/plain", "a request that changes something must carry the header  X-LDRC: 1"); return false; }
    return true;
}
// Every page but /status goes through the door.
static void doorOn(const char *path, HTTPMethod method, std::function<void()> fn) {
    web.on(path, method, [fn, method]() { if (doorPass(method != HTTP_GET)) fn(); });
}
static void banner(const char *msg);
// Open on the network we are on (and on no other), or shut. Remembered in the chip: the firmware that follows this
// one finds the door as it was left. (A bench build answers on every network whatever this says, but keeps it all
// the same: the door can be opened from the Mac BEFORE the transmitter updates itself to the published firmware.)
static bool doorSet(bool open) {
    if (open && (!radiosLive || WiFi.status() != WL_CONNECTED)) return false;
    doorSsid = open ? std::string(WiFi.SSID().c_str()) : std::string();
    pendingDoor = doorSsid; pendingDoorSet = true; pendingSince = millis(); otaReady = false;
    return true;
}
static void doorToggle() {                                 // the corner was held
    if (!doorSsid.empty()) { doorSet(false); banner("Workshop door SHUT"); return; }
    if (!doorSet(true)) { banner("Workshop door: join a WiFi first"); return; }
    banner(("Workshop door OPEN on " + doorSsid).c_str());
}
static uint32_t bannerUntil = 0;                           // the user's switch: hold the top-left corner 1.5 s
static uint32_t quietUntil = 0; static bool quietBacklightOff = false, quietWifiOff = false;
static File uploadFile; static bool uploadGood = false; static uint32_t uploadBytes = 0;

static void webBegin() {
    web.on("/status", HTTP_GET, []() {                   // (the one page that answers when the workshop door is shut)
        char b[520]; snprintf(b, sizeof(b), "{\"fw\":\"" SCREEN_VERSION "\",\"door\":%s,\"door_kept\":%s,\"tx\":%d,\"flying\":%d,\"rx\":{\"phase\":%d,\"why\":%d,\"outcome\":%d,\"release\":\"%lX\",\"wanted\":\"%lX\",\"left\":%lu,\"flags\":%lu,\"age\":%ld},\"page\":\"%s\",\"id\":%d,\"cmds\":%lu,\"odd\":%lu,\"minheap\":%u,\"heap\":%u,\"psram\":%u,\"sd\":%d,\"touch\":%d,\"ip\":\"%s\",\"audio\":%d,\"boot\":%lu,\"up\":%lu}",
                 doorOpen() ? "true" : "false", doorSsid.empty() ? "false" : "true", txStatus, flyingNow(),
                 rxNews.phase, rxNews.why, rxNews.outcome, (unsigned long) rxNews.release, (unsigned long) rxNews.wanted, (unsigned long) rxNews.left, (unsigned long) rxNews.flags, rxNewsAny ? (long) ((millis() - rxNews.atMs) / 1000) : -1L,
                 page.name.c_str(), page.id, (unsigned long) cmdCount, (unsigned long) badCount, ESP.getMinFreeHeap(), ESP.getFreeHeap(), ESP.getFreePsram(), sdOk, touchOk, WiFi.localIP().toString().c_str(), audioId, (unsigned long) bootMs, (unsigned long) millis());
        web.send(200, "application/json", b);
    });
    doorOn("/cmd", HTTP_POST, []() {
        std::string body = web.arg("plain").c_str();
        if (web.arg("one") == "1") { handle(body); presentDirty(true); web.send(200, "text/plain", "ok"); return; }   // ?one=1: the body is ONE command (it may hold \r\n line breaks)
        size_t pos = 0;                                    // several commands separated by newlines
        while (pos <= body.size()) { size_t nl = body.find('\n', pos); std::string one = body.substr(pos, nl == std::string::npos ? std::string::npos : nl - pos); if (!one.empty() && one.back() == '\r') one.pop_back(); if (!one.empty()) handle(one); if (nl == std::string::npos) break; pos = nl + 1; }
        presentDirty(true);
        web.send(200, "text/plain", "ok");
    });
    doorOn("/perf", HTTP_GET, []() {                     // counters since the last read
        char b[600]; snprintf(b, sizeof(b), "{\"cmds\":%lu,\"handle_us\":%lu,\"presents\":%lu,\"present_us\":%lu,\"present_px\":%lu,\"fill_full\":%lu,\"fill_inc\":%lu,\"skipped\":%lu,\"rx_max\":%d,\"loop_max_ms\":%lu,\"odd\":%lu}",
                              (unsigned long) perfCmds, (unsigned long) perfHandleUs, (unsigned long) perfPresentN, (unsigned long) perfPresentUs, (unsigned long) perfPresentPx,
                              (unsigned long) perfFillFull, (unsigned long) perfFillInc, (unsigned long) perfSkipped, perfRxMax, (unsigned long) perfLoopMaxMs, (unsigned long) badCount);
        perfCmds = perfHandleUs = perfPresentN = perfPresentUs = perfPresentPx = perfFillFull = perfFillInc = perfSkipped = perfLoopMaxMs = 0; perfRxMax = 0;
        std::string out = b; out.pop_back(); out += ",\"max_us\":{";
        for (int i = 0; i < 7; ++i) { char e[40]; snprintf(e, sizeof(e), "%s\"%s\":%lu", i ? "," : "", phaseName[i], (unsigned long) phaseMax[i]); out += e; phaseMax[i] = 0; }
        out += "}}";
        web.send(200, "application/json", out.c_str());
    });
    doorOn("/bench", HTTP_POST, []() {                  // raw speeds: clear the curve box on the canvas, copy it to the panel
        const uint32_t t0 = micros(); gfx->fillRect(36, 36, 360, 360, 0);
        const uint32_t t1 = micros(); present(36, 36, 360, 360);
        const uint32_t t2 = micros(); present(0, 0, W, H);
        const uint32_t t3 = micros();
        fillMemo.valid = false; drawPage();
        char b[120]; snprintf(b, sizeof(b), "{\"fill_360_us\":%lu,\"present_360_us\":%lu,\"present_full_us\":%lu}", (unsigned long) (t1 - t0), (unsigned long) (t2 - t1), (unsigned long) (t3 - t2));
        web.send(200, "application/json", b);
    });
    // A file for the screen's card. Folders on the way are made; a file that could not be written is an ERROR
    // (it used to answer "done" all the same, and files for folders that did not exist vanished silently).
    web.on("/put", HTTP_POST, []() {
        if (!doorPass(true)) return;
        if (uploadGood) web.send(200, "text/plain", String("written ") + uploadBytes + " bytes");
        else web.send(500, "text/plain", "could not write that file on the card");
    }, []() {
        HTTPUpload &up = web.upload();
        if (up.status == UPLOAD_FILE_START) {
            uploadGood = false; uploadBytes = 0;
            if (!doorOpen() || web.header("X-LDRC") != "1") return;     // (the answer above says why)
            String path = web.arg("path"); if (!path.startsWith("/")) path = "/" + path;
            sdMakeFolders(path.c_str()); SD.remove(path);
            if (path.startsWith("/hmi/") || path.startsWith("/images/")) SD.remove("/update/screen_have.txt");   // the next install reads and checks every file ("Check for update")
            uploadFile = SD.open(path, FILE_WRITE); uploadGood = (bool) uploadFile; uploadBytes = 0;
        }
        else if (up.status == UPLOAD_FILE_WRITE) { if (uploadFile && uploadGood) { if (uploadFile.write(up.buf, up.currentSize) != up.currentSize) uploadGood = false; else uploadBytes += up.currentSize; } breathe(); }
        else if (up.status == UPLOAD_FILE_END) { if (uploadFile) uploadFile.close(); }
        else if (up.status == UPLOAD_FILE_ABORTED) { if (uploadFile) uploadFile.close(); uploadGood = false; }
    });
    doorOn("/tap", HTTP_POST, []() {                    // /tap?x=&y=[&ms=] : press there for ms (default 120), then release
        fakeX = web.arg("x").toInt(); fakeY = web.arg("y").toInt();
        fakeTouchUntil = millis() + (web.hasArg("ms") ? web.arg("ms").toInt() : 120);
        web.send(200, "text/plain", "ok");
    });
    doorOn("/bootlog", HTTP_GET, []() { web.send(200, "text/plain", bootLog.c_str()); });
    doorOn("/kept", HTTP_GET, []() {                    // /kept[?page=Name]: the values that outlive a page, as the screen holds them (a workshop look)
        const std::string want = web.hasArg("page") ? std::string(web.arg("page").c_str()) + "." : std::string();
        std::string out = "page now: " + page.name + "\n";
        for (auto &k : kept) {
            if (!want.empty() && k.first.compare(0, want.size(), want) != 0) continue;
            out += k.first;
            for (auto &i : k.second.ints) out += " " + i.first + "=" + std::to_string(i.second);
            for (auto &t : k.second.txts) out += " " + t.first + "=\"" + t.second.substr(0, 40) + "\"";
            out += "\n";
        }
        if (page.name == (want.empty() ? page.name : want.substr(0, want.size() - 1))) { out += "on the glass:\n"; for (auto &c : page.comps) if (c.type == "combobox" || c.type == "switch" || c.type == "dual-state button" || c.type == "checkbox") out += "  " + c.name + " val=" + std::to_string(c.val) + " txt=\"" + c.txt + "\"" + (c.vis ? "" : " hidden") + "\n"; }
        out += "lately:\n" + touchLog;
        web.send(200, "text/plain", out.c_str());
    });
    doorOn("/radiolog", HTTP_GET, []() { web.send(200, "text/plain", radioLog.c_str()); });
    doorOn("/fb", HTTP_GET, []() {
        if (wifiSecretShown()) { web.send(423, "text/plain", "a password is on the screen"); return; }
        uint16_t *fb = screenFb;                            // what the panel shows
        WiFiClient client = web.client();
        web.setContentLength(W * H * 2);
        web.send(200, "application/octet-stream", "");
        for (int y = 0; y < H; ++y) { client.write((const uint8_t *) (fb + y * W), W * 2); if ((y & 7) == 7) breathe(); }
    });
    // ---- the Teensy's card and firmware. Every POST queues a job and answers at once; GET /teensy/status tells the story.
    doorOn("/teensy/status", HTTP_GET, []() {
        auto esc = [](const std::string &t) { std::string o; for (char c : t) { if (c == '"' || c == '\\') o.push_back('\\'); if ((unsigned char) c >= 32) o.push_back(c); } return o; };
        std::string out = "{\"running\":"; out += teensyLink.running() ? "true" : "false";
        out += ",\"finished\":"; out += teensyLink.finished() ? "true" : "false";
        out += ",\"failed\":"; out += teensyLink.failed() ? "true" : "false";
        out += ",\"stage\":\"" + esc(teensyLink.stage()) + "\",\"result\":\"" + esc(teensyLink.result()) + "\",\"peer\":\"" + esc(teensyLink.peer()) + "\"";
        out += ",\"settings\":\"" + esc(teensyLink.settingsRead()) + "\",\"warnings\":[";
        const auto &warned = teensyLink.warnings();
        for (size_t i = 0; i < warned.size(); ++i) { if (i) out += ","; out += "\"" + esc(warned[i]) + "\""; }
        out += "]";
        char n[160]; snprintf(n, sizeof(n), ",\"step\":%u,\"steps\":%u,\"done\":%lu,\"size\":%lu,\"repeats\":%lu,\"noted\":%lu,\"log\":[", (unsigned) teensyLink.stepIndex(), (unsigned) teensyLink.stepCount(),
                              (unsigned long) teensyLink.fileDone(), (unsigned long) teensyLink.fileSize(), (unsigned long) teensyLink.resends(), (unsigned long) teensyLink.noted());
        out += n;
        const auto &log = teensyLink.log();
        for (size_t i = 0; i < log.size(); ++i) { if (i) out += ","; out += "\"" + esc(log[i]) + "\""; }
        out += "],\"entries\":[";                          // what a look into a folder found (POST /teensy/list)
        const auto &ent = teensyLink.entries();
        for (size_t i = 0; i < ent.size(); ++i) { char e[32]; snprintf(e, sizeof(e), "\",\"size\":%lu,\"dir\":%d}", (unsigned long) ent[i].size, ent[i].dir ? 1 : 0); out += std::string(i ? "," : "") + "{\"name\":\"" + esc(ent[i].name) + e; }
        out += "]}";
        web.send(200, "application/json", out.c_str());
    });
    auto linkBusy = []() {
        if (teensyLink.running()) { web.send(409, "text/plain", "a job is running"); return true; }
        if (flyingNow()) { web.send(409, "text/plain", flyingText(flyingNow())); return true; }
        if (updAtWork()) { web.send(409, "text/plain", "\"Check for update\" is at work on the screen: the link is its own"); return true; }   // (its install went in behind a job from here, once)
        teensyLink.clear(); return false;
    };
    doorOn("/teensy/hello", HTTP_POST, [linkBusy]() { if (linkBusy()) return; teensyLink.hello(); web.send(linkStart() ? 200 : 500, "text/plain", "asked"); });
    doorOn("/teensy/put", HTTP_POST, [linkBusy]() {             // ?local=/teensy/sd/help/AUDIO.TXT&remote=/help/AUDIO.TXT[&user=1][&always=1]
        if (linkBusy()) return;
        teensyLink.put(web.arg("local").c_str(), web.arg("remote").c_str(), web.arg("user") == "1" ? ldrc::LF_USER_DATA : 0, web.arg("always") != "1");
        web.send(linkStart() ? 200 : 500, "text/plain", "queued");
    });
    doorOn("/teensy/get", HTTP_POST, [linkBusy]() {             // ?remote=/MODELS.DAT&local=/teensy/fetched/MODELS.DAT
        if (linkBusy()) return;
        const String local = web.arg("local");                // what is fetched goes below /teensy, and never into the sets of copies
        if (!local.startsWith("/teensy/") || local.startsWith("/teensy/backup/") || !ldrc::plainPath(local.c_str())) { web.send(403, "text/plain", "what is fetched goes below /teensy (and not into /teensy/backup: POST /teensy/keep makes a copy there)"); return; }
        teensyLink.get(web.arg("remote").c_str(), web.arg("local").c_str());
        web.send(linkStart() ? 200 : 500, "text/plain", "queued");
    });
    doorOn("/teensy/delete", HTTP_POST, [linkBusy]() {          // ?remote=/help/OLD.TXT[&user=1]
        if (linkBusy()) return;
        teensyLink.del(web.arg("remote").c_str(), web.arg("user") == "1" ? ldrc::LF_USER_DATA : 0);
        web.send(linkStart() ? 200 : 500, "text/plain", "queued");
    });
    doorOn("/teensy/list", HTTP_POST, [linkBusy]() {            // ?dir=/mod : what is in that folder of the Teensy's card (names and sizes, in /teensy/status)
        if (linkBusy()) return;
        String dir = web.arg("dir"); if (dir.isEmpty()) dir = "/";
        teensyLink.list(dir.c_str());
        web.send(linkStart() ? 200 : 500, "text/plain", "asked");
    });
    doorOn("/teensy/sync", HTTP_POST, [linkBusy]() {            // ?dir=/teensy/sd : every file below it goes to the same place on the Teensy's card, if it differs
        if (linkBusy()) return;
        String root = web.arg("dir"); if (root.isEmpty()) root = "/teensy/sd";
        std::vector<String> todo; todo.push_back(root); int files = 0;
        while (!todo.empty()) {
            const String dir = todo.back(); todo.pop_back();
            File d = SD.open(dir); if (!d || !d.isDirectory()) continue;
            File f;
            while ((f = d.openNextFile())) {
                const String full = dir + "/" + f.name();
                if (f.isDirectory()) todo.push_back(full);
                else { const String remote = full.substring(root.length()); if (!ldrc::isUserData(remote.c_str()) || web.arg("user") == "1") { teensyLink.put(full.c_str(), remote.c_str(), web.arg("user") == "1" ? ldrc::LF_USER_DATA : 0, true); files++; } }
                f.close();
            }
        }
        if (!files) { web.send(404, "text/plain", "nothing to send below that folder"); return; }
        web.send(linkStart() ? 200 : 500, "text/plain", String(files) + " files queued");
    });
    doorOn("/teensy/install", HTTP_POST, [linkBusy]() {         // ?package=/teensy/TXFW.BIN : keep the models, send the package, install, wait, check, confirm
        if (linkBusy()) return;
        String pkg = web.arg("package"); if (pkg.isEmpty()) pkg = "/teensy/TXFW.BIN";
        File f = SD.open(pkg); uint8_t raw[ldrc::FW_HEADER_SIZE]; ldrc::FwHeader h;
        if (!f || f.read(raw, sizeof(raw)) != (int) sizeof(raw) || !ldrc::fwHeaderParse(raw, h)) { if (f) f.close(); web.send(400, "text/plain", "that is not a firmware package"); return; }
        f.close();
        if (web.arg("backup") != "0") { keepPending = keepQueue("before " + std::string(h.version)); keepAbout = "Kept before " + std::string(h.version) + " went in, from the Mac.\n"; }   // the pilot's files, kept on OUR card first
        teensyLink.put(pkg.c_str(), "/FW/TXFW.BIN", 0, true);
        teensyLink.install("/FW/TXFW.BIN", h.version);
        web.send(linkStart() ? 200 : 500, "text/plain", String("installing ") + h.version);
    });
    // The pilot's own files: a copy now (POST /teensy/keep), the copies there are (GET /teensy/sets), one of them put back
    // (POST /teensy/restore?set=<its folder's name>: models.dat and every *.MOD of that copy replace what is on the Teensy's card).
    doorOn("/teensy/keep", HTTP_POST, [linkBusy]() {
        if (linkBusy()) return;
        keepPending = keepQueue("asked for"); keepAbout = "Kept because it was asked for, from the Mac.\n";
        web.send(linkStart() ? 200 : 500, "text/plain", keepPending.c_str());
    });
    doorOn("/teensy/sets", HTTP_GET, []() {
        std::string out;
        for (auto &s : keepSets()) out += s + "\n";
        web.send(200, "text/plain", out.c_str());
    });
    doorOn("/teensy/restore", HTTP_POST, [linkBusy]() {
        if (linkBusy()) return;
        const std::string set = web.arg("set").c_str(), folder = std::string(KEEP_ROOT) + "/" + set;
        if (!keepIsSet(set) || set.find("..") != std::string::npos || set.find('/') != std::string::npos || set.find('\\') != std::string::npos || !SD.exists(folder.c_str())) { web.send(404, "text/plain", "no such copy"); return; }
        if (!keepIsWhole(set) && web.arg("half") != "1") { web.send(409, "text/plain", "that copy is not whole (the job that made it failed). Add half=1 to put back what it holds all the same"); return; }
        int n = 0;
        auto endsWith = [](const std::string &name, const char *end) { const size_t m = strlen(end); if (name.size() < m) return false; for (size_t i = 0; i < m; ++i) if (tolower((unsigned char) name[name.size() - m + i]) != tolower((unsigned char) end[i])) return false; return true; };
        for (int pass = 0; pass < 2; ++pass) {              // the card's own folder, then mod
            const std::string from = pass ? folder + "/mod" : folder, to = pass ? "/mod/" : "/";
            File d = SD.open(from.c_str());
            if (d && d.isDirectory()) {
                File f;
                while ((f = d.openNextFile())) {
                    const std::string name = f.name(); const bool dir = f.isDirectory(); f.close();
                    // Only the models and the settings: models.dat, and the model files (*.MOD). Not the logs (a log put
                    // back would take the place of the log as it is now), not a half file (*.part), not a copy moved aside.
                    const bool wanted = pass ? endsWith(name, ".mod") : (name.size() == 10 && endsWith(name, "models.dat"));
                    if (dir || !wanted || !ldrc::plainPath((to + name).c_str())) continue;
                    teensyLink.put(from + "/" + name, to + name, ldrc::LF_USER_DATA, true); n++;
                }
            }
            if (d) d.close();
        }
        if (!n) { web.send(404, "text/plain", "that copy holds none of the pilot's files"); return; }
        web.send(linkStart() ? 200 : 500, "text/plain", (String(n) + " files to put back").c_str());
    });
    doorOn("/teensy/rollback", HTTP_POST, [linkBusy]() { if (linkBusy()) return; teensyLink.rollback(); web.send(linkStart() ? 200 : 500, "text/plain", "asked"); });
    doorOn("/teensy/confirm", HTTP_POST, [linkBusy]() { if (linkBusy()) return; teensyLink.confirm(); teensyLink.hello(); web.send(linkStart() ? 200 : 500, "text/plain", "asked"); });
    doorOn("/teensy/cancel", HTTP_POST, []() { teensyLink.cancel("cancelled"); web.send(200, "text/plain", "cancelled"); });
    doorOn("/file", HTTP_GET, []() {                     // a file from the screen's own card
        File f = SD.open(web.arg("path"));
        if (!f || f.isDirectory()) { web.send(404, "text/plain", "no such file"); return; }
        web.setContentLength(f.size()); web.send(200, "application/octet-stream", "");
        WiFiClient client = web.client(); static uint8_t buf[2048]; int n;
        while ((n = f.read(buf, sizeof(buf))) > 0) { if (client.write(buf, n) != (size_t) n) break; breathe(); }
        f.close();
    });
    doorOn("/rm", HTTP_POST, []() {                      // a file of the screen's own card, below /teensy or /update only
        const String path = web.arg("path");
        if (!(path.startsWith("/teensy/") || path.startsWith("/update/")) || path.indexOf("..") >= 0 || path.indexOf('\\') >= 0) { web.send(403, "text/plain", "only below /teensy and /update"); return; }
        if (path.startsWith("/teensy/backup/") && web.arg("copies") != "1") { web.send(403, "text/plain", "that is a copy of the pilot's files. Add copies=1 if it is really to go"); return; }
        web.send(SD.remove(path) ? 200 : 404, "text/plain", SD.exists(path) ? "still there" : "gone");
    });
    doorOn("/ls", HTTP_GET, []() {
        String path = web.arg("path"); if (path.isEmpty()) path = "/";
        File d = SD.open(path); String out;
        if (d && d.isDirectory()) { File f; while ((f = d.openNextFile())) { out += f.name(); out += f.isDirectory() ? "/\n" : " " + String(f.size()) + "\n"; f.close(); } }
        web.send(200, "text/plain", out);
    });
    doorOn("/sent", HTTP_GET, []() { web.send(200, "text/plain", sentTrace.c_str()); sentTrace.clear(); });
    doorOn("/recent", HTTP_GET, []() {
        std::string out;
        for (int i = max(0, recentN - 64); i < recentN; ++i) { out += recent[i % 64]; out += "\n"; }
        web.send(200, "text/plain", out.c_str());
    });
    doorOn("/odd", HTTP_GET, []() { web.send(200, "text/plain", oddTrace.c_str()); oddTrace.clear(); });
    // Radio experiment: /quiet?ms=60000&bl=0&wifi=0 — backlight and/or WiFi off for a while, then back.
    // (The Teensy keeps sending the telemetry counters; they are read afterwards.)
    doorOn("/quiet", HTTP_POST, []() {
        quietUntil = millis() + (uint32_t) web.arg("ms").toInt();
        quietBacklightOff = web.arg("bl") == "0"; quietWifiOff = web.arg("wifi") == "0";
        web.send(200, "text/plain", "quiet");
    });
    doorOn("/awake", HTTP_POST, []() { if (teensyLink.running()) { web.send(409, "text/plain", "a job is on the link"); return; } flushOut(); Serial.print("UKRULES"); web.send(200, "text/plain", "poked"); });   // resets the Teensy's screen timeout
    doorOn("/radios", HTTP_POST, []() { const bool on = web.arg("on") != "0"; web.send(200, "text/plain", on ? "on" : "off"); delay(50); setRadios(on); });
    doorOn("/nodraw", HTTP_POST, []() { noDraw = web.arg("on") == "1"; web.send(200, "text/plain", noDraw ? "drawing off" : "drawing on"); });
    doorOn("/reboot", HTTP_POST, []() { web.send(200, "text/plain", "rebooting"); delay(100); ESP.restart(); });
    doorOn("/door", HTTP_POST, []() {                   // /door?on=1 : open on the network we are on, and remembered; /door?on=0 : shut (and this was the last request to be answered)
        const bool on = web.arg("on") != "0";
        if (!doorSet(on)) { web.send(409, "text/plain", "not on a network"); return; }
        web.send(200, "text/plain", on ? ("open on " + doorSsid).c_str() : "shut");
    });
    updWeb();
    wifiWeb();
    picWeb();
    static const char *wanted[] = { "X-LDRC" };
    web.collectHeaders(wanted, 1);
    web.begin();
}
#include "wifi_device.h"

static void netBegin() {
    WiFi.setHostname("ldrc-screen");
    radiosOn = prefs.getBool("radios", true);
    doorSsid = prefs.getString("door", "").c_str();
    wifiBegin();                                           // the networks we know (none is compiled in), and the radio
    // The radio stays OFF until the main board has said what the transmitter is doing (a screen that restarts
    // in flight must not come up with its WiFi on), or until 8 s have passed without a word from it (an older
    // main board, or none): txStatusSaid() and netPoll() let it go.
    radiosLive = false; radioHeld = true; wifiStop();
    ArduinoOTA.setHostname("ldrc-screen");
    ArduinoOTA.onStart([]() { gfx->fillRect(0, 0, W, 30, 0xF800); gfx->startWrite(); drawGlyphs(8, 3, 4, 0xFFFF, "Updating firmware..."); gfx->endWrite(); });
}
// ------------------------------------------------------------------ audio: the HMI's clips through the NS4168 amp (SPK)
// Every clip in TX_NEXTION.HMI is PCM 16-bit mono 22.05 kHz. loop() feeds a ring buffer; a task on the other
// core feeds the I2S DMA from the ring in whole 256-frame buffers (the legacy driver only sends whole
// buffers: a 441-frame click used to leave its last 185 frames stranded until the next sound came along —
// the "stuttering" power-off chirps), padding a clip's last buffer with silence. The first play of a clip
// streams it off the card and keeps a copy in PSRAM; later plays come from memory, whole, so no page load
// or card access can interrupt them. Small clips are fetched in the background while the link is quiet.
#include <driver/i2s.h>
static const i2s_port_t I2S_PORT = I2S_NUM_0;
static const size_t RING = 65536;                       // 1.5 s of audio ahead of the DMA
static const int FRAMES = 256;                          // one DMA buffer
static uint8_t *audioRing = nullptr;
static volatile size_t ringHead = 0, ringTail = 0;      // head: loop() writes; tail: the task reads
static volatile bool audioDraining = false;             // nothing more is coming: play the tail, padded
static File audioFile; static bool audioPlaying = false, audioLoop = false;
static uint32_t audioDataStart = 0, audioDataSize = 0, audioDataLeft = 0, audioRate = 22050;
struct Clip { int id; uint8_t *data; uint32_t len; uint32_t used; };
static std::vector<Clip> clips; static size_t clipBytes = 0; static const size_t CLIP_BUDGET = 1500 * 1024;
static Clip *curClip = nullptr; static uint32_t curPos = 0;          // playing from memory
static uint8_t *capture = nullptr; static uint32_t captureLen = 0;   // a copy being made while streaming
static Clip *clipFind(int id) { for (auto &c : clips) if (c.id == id) { c.used = millis(); return &c; } return nullptr; }
static void clipMakeRoom(size_t need) {
    while (clipBytes + need > CLIP_BUDGET && !clips.empty()) {
        int old = -1;
        for (size_t i = 0; i < clips.size(); ++i) if (&clips[i] != curClip && (old < 0 || clips[i].used < clips[old].used)) old = (int) i;
        if (old < 0) return;
        free(clips[old].data); clipBytes -= clips[old].len; clips.erase(clips.begin() + old);
    }
}
static void clipAdd(int id, uint8_t *data, uint32_t len) { clips.push_back({ id, data, len, millis() }); clipBytes += len; }
static bool wavOpen(int id, uint32_t &rate) {           // leaves audioFile at the samples; sets audioDataStart/Size/Left
    char path[32]; snprintf(path, sizeof(path), "/hmi/audio/%d.wav", id);
    audioFile = SD.open(path); if (!audioFile) return false;
    uint8_t h[12]; if (audioFile.read(h, 12) != 12 || memcmp(h, "RIFF", 4) || memcmp(h + 8, "WAVE", 4)) { audioFile.close(); return false; }
    rate = 22050; bool haveData = false;
    while (audioFile.available()) {
        uint8_t ch[8]; if (audioFile.read(ch, 8) != 8) break;
        const uint32_t sz = ch[4] | (ch[5] << 8) | (ch[6] << 16) | ((uint32_t) ch[7] << 24);
        if (!memcmp(ch, "fmt ", 4)) { uint8_t f[16]; audioFile.read(f, 16); rate = f[4] | (f[5] << 8) | (f[6] << 16) | ((uint32_t) f[7] << 24); if (sz > 16) audioFile.seek(audioFile.position() + sz - 16); }
        else if (!memcmp(ch, "data", 4)) { audioDataStart = audioFile.position(); audioDataSize = audioDataLeft = sz; haveData = true; break; }
        else audioFile.seek(audioFile.position() + sz + (sz & 1));
    }
    if (!haveData) audioFile.close();
    return haveData;
}
static void audioTask(void *) {
    static int16_t frame[FRAMES * 2];
    for (;;) {
        size_t avail = (ringHead + RING - ringTail) % RING;
        const bool tail = audioDraining && avail > 0;
        if (avail < (size_t) FRAMES * 2 && !tail) { vTaskDelay(pdMS_TO_TICKS(3)); continue; }
        int n = 0;
        while (n < FRAMES && avail >= 2) {
            int16_t v = (int16_t) (audioRing[ringTail] | (audioRing[(ringTail + 1) % RING] << 8));
            ringTail = (ringTail + 2) % RING; avail -= 2;
            v = limit16(((int32_t) v * audioGain) >> 10);
            frame[2 * n] = v; frame[2 * n + 1] = v; n++;
        }
        for (; n < FRAMES; ++n) { frame[2 * n] = 0; frame[2 * n + 1] = 0; }   // a clip's last buffer: padded with silence, sent now
        size_t written = 0; i2s_write(I2S_PORT, frame, FRAMES * 4, &written, portMAX_DELAY);
    }
}
static void audioBegin() {
    i2s_config_t cfg = {};
    cfg.mode = (i2s_mode_t) (I2S_MODE_MASTER | I2S_MODE_TX); cfg.sample_rate = 22050; cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
    cfg.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT; cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
    cfg.dma_buf_count = 8; cfg.dma_buf_len = FRAMES; cfg.use_apll = false; cfg.tx_desc_auto_clear = true; cfg.intr_alloc_flags = 0;
    if (i2s_driver_install(I2S_PORT, &cfg, 0, nullptr) != ESP_OK) return;
    i2s_pin_config_t pins = {}; pins.mck_io_num = I2S_PIN_NO_CHANGE; pins.bck_io_num = 42; pins.ws_io_num = 18; pins.data_out_num = 17; pins.data_in_num = I2S_PIN_NO_CHANGE;
    i2s_set_pin(I2S_PORT, &pins);
    i2s_zero_dma_buffer(I2S_PORT);
    audioRing = (uint8_t *) ps_malloc(RING);
    if (audioRing) xTaskCreatePinnedToCore(audioTask, "audio", 4096, nullptr, 3, nullptr, 0);
}
static void audioStop() {
    if (audioFile) audioFile.close();
    audioPlaying = false; audioId = -1; curClip = nullptr; audioDraining = false;
    if (capture) { free(capture); capture = nullptr; }
    ringHead = ringTail;
}
static void ringPush(const uint8_t *src, size_t n) { for (size_t i = 0; i < n; ++i) { audioRing[ringHead] = src[i]; ringHead = (ringHead + 1) % RING; } }
static void audioFill() {                               // called from loop(): keep the ring topped up
    if (!audioPlaying || !audioRing) return;
    const size_t used = (ringHead + RING - ringTail) % RING, space = RING - 1 - used;
    if (curClip) {                                       // from memory: everything there is room for, at once
        if (curPos >= curClip->len) { if (audioLoop) curPos = 0; else { audioDraining = true; if (used == 0) audioStop(); } return; }
        const size_t n = min(space, (size_t) (curClip->len - curPos)); if (!n) return;
        ringPush(curClip->data + curPos, n); curPos += n; return;
    }
    if (audioDataLeft == 0) {
        if (capture && captureLen == audioDataSize) { clipAdd(audioId, capture, captureLen); capture = nullptr; }   // the copy is complete: keep it for next time
        if (audioLoop) { audioFile.seek(audioDataStart); audioDataLeft = audioDataSize; return; }
        audioDraining = true; if (used == 0) audioStop(); return;
    }
    if (space < 4096) return;
    static uint8_t tmp[4096];
    const size_t want = min((size_t) 4096, min(space, (size_t) audioDataLeft));
    const int got = audioFile.read(tmp, want);
    if (got <= 0) { audioStop(); return; }
    audioDataLeft -= got; ringPush(tmp, got);
    if (capture) { memcpy(capture + captureLen, tmp, got); captureLen += got; }
}
static void audioStart(int id, bool loopIt) {
    audioStop();
    if (!audioRing) return;
    audioLoop = loopIt; audioId = id;
    if (Clip *c = clipFind(id)) { curClip = c; curPos = 0; audioPlaying = true; audioFill(); return; }
    uint32_t rate;
    if (!sdOk || !wavOpen(id, rate)) { audioId = -1; return; }
    if (rate != audioRate) { i2s_set_sample_rates(I2S_PORT, rate); audioRate = rate; }
    if (audioDataSize <= CLIP_BUDGET / 2) { clipMakeRoom(audioDataSize); capture = (uint8_t *) ps_malloc(audioDataSize); captureLen = 0; }
    audioPlaying = true;
    audioFill();
}
static void audioWarm() {                               // loop(): while nothing is happening, bring the small clips into memory one at a time
    static int next = 0; static uint32_t lastTry = 0;
    if (audioPlaying || !sdOk || !audioRing || next >= 128 || (int32_t) (millis() - lastRxMs) < 300 || millis() - lastTry < 50) return;
    lastTry = millis();
    const int id = next++;
    if (clipFind(id)) return;
    uint32_t rate; if (!wavOpen(id, rate)) return;
    if (audioDataSize > 40 * 1024) { audioFile.close(); return; }
    clipMakeRoom(audioDataSize);
    uint8_t *buf = (uint8_t *) ps_malloc(audioDataSize); if (!buf) { audioFile.close(); return; }
    const int got = audioFile.read(buf, audioDataSize); audioFile.close();
    if (got == (int) audioDataSize) clipAdd(id, buf, audioDataSize); else free(buf);
}
// A 6x6 dot in the top-left corner: green = on the WiFi, red = not.
static void netDot(bool force = false) {
    static int last = -1; const int now = !radiosLive ? 2 : WiFi.status() == WL_CONNECTED ? 1 : 0;
    if (now == last && !force) return; last = now;
    gfx->fillRect(0, 0, 6, 6, now == 1 ? 0x07E0 : now == 2 ? 0x8410 : 0xF800);
    memoTouched(0, 0, 6, 6); dirty(0, 0, 6, 6);
}
// Two seconds of text along the top, then the page repaints that strip. Navy with white text, like every message of
// the screen's own ("that should be your default for system messages, removing the white over black": Malcolm, 30-9-2026).
static const int BANNER_H = 34;
static void banner(const char *msg) {
    gfx->fillRect(0, 0, W, BANNER_H, OUR_PANEL); gfx->drawFastHLine(0, BANNER_H - 1, W, OUR_INK);
    gfx->startWrite(); drawGlyphs(12, 5, 2, OUR_INK, msg); gfx->endWrite();
    memoTouched(0, 0, W, BANNER_H); dirty(0, 0, W, BANNER_H); damage(0, 0, W, BANNER_H);
    bannerUntil = millis() + 2000;
}
static void applyRadios(const char *why) {
    const bool want = (radiosOn || updWifi || picWifi) && tx.radiosAllowed();
    if (want == radiosLive) return;
    radiosLive = want;
    { char b[100]; snprintf(b, sizeof b, "%lu %s (tx=%d, page %s)\n", (unsigned long) millis(), why, txStatus, page.name.c_str()); radioLog += b; while (radioLog.size() > 1600) radioLog.erase(0, radioLog.find('\n') + 1); }
    if (want) { wifiStart(); banner(why); }
    else { web.stop(); wifiStop(); otaReady = false; banner(why); }
}
static void setRadios(bool on) {                       // the manual switch (remembered: written when the wire is quiet, see prefsPoll)
    radiosOn = on; pendingRadios = on ? 1 : 0; pendingSince = millis();
    applyRadios(on ? "WiFi ON - joining..." : "WiFi and Bluetooth OFF");
}
static void quietPoll() {
    if (quietUntil && !quietActive) {
        quietActive = true;
        if (quietBacklightOff) blSet(0);
        if (quietWifiOff) { web.stop(); wifiStop(); otaReady = false; }
    }
    if (quietActive && (int32_t) (millis() - quietUntil) >= 0) {
        quietActive = false; quietUntil = 0;
        backlight(sysDim * 255 / 100);
        if (quietWifiOff && radiosLive) wifiStart();
    }
}
// The true time, from the internet, for the main board's clock (screen 1.9.6; Malcolm, 10-05: "we could use our
// access to the Internet to set the time correctly automatically"). Whenever we are on a network, the time is asked
// for (SNTP) in the clock's own time zone - the UK's, summer time and all - and given to the main board once, as a
// phone gives it through the receiver: the word TIME=<local seconds since 1970>, which the main board writes into its
// clock when the clock is ten seconds or more adrift (B30). Again every hour while the network stays. Not while files
// travel on the wire, and never in flight.
#define TIME_ZONE_RULE "GMT0BST,M3.5.0/1,M10.5.0"              // (the UK: GMT, British Summer Time from the last Sunday of March to the last Sunday of October)
static long daysFromCivil(int y, int m, int d) {            // days since 1970-01-01 of a calendar date (Howard Hinnant's)
    y -= m <= 2; const long era = (y >= 0 ? y : y - 399) / 400; const unsigned yoe = (unsigned) (y - era * 400);
    const unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1, doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + (long) doe - 719468;
}
static void timePoll() {
    static bool configured = false; static uint32_t sentAt = 0; static int sentFor = -1;
    if (WiFi.status() != WL_CONNECTED) { configured = false; return; }
    const uint32_t now = millis();
    if (!configured) { configTzTime(TIME_ZONE_RULE, "pool.ntp.org", "time.google.com", "time.cloudflare.com"); configured = true; sentFor = -1; return; }
    if (sentAt && now - sentAt < 3600000UL) return;
    const time_t t = time(nullptr);
    if (t < 1700000000) return;                                 // (not had from the internet yet)
    if (teensyLink.running() || armedNow || (int32_t) (now - lastRxMs) < 200) return;   // (a quiet moment on the wire: the word goes alone)
    struct tm lt; localtime_r(&t, &lt);                         // the wall clock here, as a count of seconds (the main board's clock keeps local time)
    const long local = daysFromCivil(lt.tm_year + 1900, lt.tm_mon + 1, lt.tm_mday) * 86400L + lt.tm_hour * 3600L + lt.tm_min * 60L + lt.tm_sec;
    char b[48]; snprintf(b, sizeof(b), "TIME=%ld", local);
    flushOut(); Serial.write((const uint8_t *) b, strlen(b));
    sentAt = now;
    char when[40]; strftime(when, sizeof(when), "%Y-%m-%d %H:%M:%S %Z", &lt);
    if (sentFor != lt.tm_hour) { sentFor = lt.tm_hour; blog("time", std::string("from the internet: ") + when + ", to the main board"); }
}
static void netPoll() {
    static uint32_t downSince = 0;
    quietPoll();
    { const char *why = tx.tick(millis() - bootMs); if (why) applyRadios(why); }
    if (bannerUntil && (int32_t) (millis() - bannerUntil) >= 0) { bannerUntil = 0; restoreRect(0, 0, W, BANNER_H); for (auto &c : page.comps) if (c.y < BANNER_H) drawComp(c); memoTouched(0, 0, W, BANNER_H); dirty(0, 0, W, BANNER_H); netDot(true); }
    if (!radiosLive) { netDot(); return; }
    if (quietActive && quietWifiOff) return;
    netDot();
    if (WiFi.status() != WL_CONNECTED) {
        otaReady = false;
        if (!downSince) downSince = millis();
        if (!wifiPage.showing()) wifiAuto();                  // (while the WiFi page shows, the pilot chooses)
        return;
    }
    if (downSince || !otaReady) wifiJoined();
    downSince = 0;
    if (!otaReady) {                                        // (the handlers are made ONCE: every web.on() is a new one, and they were made afresh at every join)
        static bool made = false, otaBegun = false;
        otaReady = true; MDNS.begin("ldrc-screen");
        if (otaBegun) { ArduinoOTA.end(); otaBegun = false; }
        if (doorOpen()) { ArduinoOTA.begin(); otaBegun = true; }    // firmware pushed from the Mac: through the workshop door only
        otaListening = otaBegun;
        if (!made) { made = true; webBegin(); } else web.begin();
    }
    if (otaListening && doorOpen() && !updChanging() && !flyingNow()) ArduinoOTA.handle();   // (not while "Check for update" is changing something, and never in flight)
    web.handleClient();
    timePoll();
}

#include "update_device.h"
#include "pics_device.h"
#include "flight_device.h"
#include "theme_device.h"
#include "pong_device.h"

void setup() {
    Serial.setRxBufferSize(32768);                        // BEFORE begin(): set afterwards it stayed at 256 bytes and telemetry bursts overran it
    Serial.begin(NEXTION_BAUD);
    // Above 57600 baud the core raises the receive interrupt at 120 bytes of the 128-byte hardware FIFO: at
    // 921600 that leaves 87 microseconds before bytes are lost, and any brief interrupt delay mangled a command
    // (a stray line across the curve page). At 24 bytes there is over a millisecond in hand.
    Serial.setRxFIFOFull(24);
    prefs.begin("screen", false);                          // FIRST: the remembered page, background and volume are read below
    themeLoad();                                           // the pilot's colours, before anything is drawn
    pinMode(LCD_BL, OUTPUT); ledcSetup(1, 20000, 8); ledcAttachPin(LCD_BL, 1); blSet(0);   // dark: see "The backlight" above
    screen->begin(); screen->fillScreen(0); screenFb = screen->getFramebuffer();
    if (canvas->begin(GFX_SKIP_OUTPUT_BEGIN)) { gfx = canvas; fbNow = canvas->getFramebuffer(); canvas->fillScreen(0); } else fbNow = screenFb;
    pageFb = fbNow;
    Wire.begin(TP_SDA, TP_SCL);
    touchOk = touch.begin(Wire, GT911_SLAVE_ADDRESS_L, TP_SDA, TP_SCL) || touch.begin(Wire, GT911_SLAVE_ADDRESS_H, TP_SDA, TP_SCL);
    if (touchOk) touch.setMaxCoordinates(W, H);
    sdSPI.begin(SD_CLK, SD_MISO, SD_MOSI, SD_CS);
    blog("boot", std::string("screen up ") + SCREEN_MARK);
    ldrc::crc32((const uint8_t *) "", 0);                  // (its table is made now, by one task, not later by two at once)
    sdOk = SD.begin(SD_CS, sdSPI, 40000000) || SD.begin(SD_CS, sdSPI, 20000000);
    blog("boot", sdOk ? "sd ok" : "sd FAILED");
    updMend();                                             // a file that was being replaced when the power went is put back, before anything is read
    if (sdOk) loadAaFonts();
    blog("boot", "fonts");
    if (sdOk) {
        File f = SD.open("/hmi/index.json");
        if (f) { JsonDocument doc; if (!deserializeJson(doc, f)) for (JsonObject p : doc["pages"].as<JsonArray>()) { int id = p["id"] | 0; std::string nm = p["name"] | ""; if ((int) pageNames.size() <= id) pageNames.resize(id + 1); pageNames[id] = nm; pageIds[nm] = id; } f.close(); }
    }
    { char b[80]; snprintf(b, sizeof(b), "LDRC V2 screen  sd=%d pages=%d touch=%d", sdOk, (int) pageNames.size(), touchOk); gfx->startWrite(); drawGlyphs(20, 40, 6, 0xFF9C, b); gfx->endWrite(); present(0, 0, W, 80); }
    // Program.s: the globals, the power-on notice to the Teensy, then page 0.
    host.sys["sys0"] = 0; host.sys["sys1"] = 0; host.sys["sys2"] = 0; host.sys["sys3"] = 0;
    host.sys["Screen_Background"] = prefs.getInt("bg", 1); host.sys["Button_BackGround"] = 54938; host.sys["Button_ForeGround"] = 0;
#ifdef EMU_ECHO
    Serial.print("EMU READY\n");
#endif
    static const uint8_t powerOn[] = { 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x88, 0xFF, 0xFF, 0xFF };
    Serial.write(powerOn, sizeof(powerOn));
    // The Teensy's first "page FrontView" comes ~3 s after power-on and its image question (findfile, then
    // get sys0 with a 500 ms timeout) right behind it: the background must already be in memory by then.
    loadBackground(host.sys["Screen_Background"]);
    blog("boot", "background " + std::to_string((long) host.sys["Screen_Background"]));
    audioBegin(); audioSetVolume(prefs.getInt("vol", 50));
    flightLoad();                                          // what the pilot chose for the flight screen
    const esp_reset_reason_t why = esp_reset_reason();
    const bool warm = !(why == ESP_RST_POWERON || why == ESP_RST_BROWNOUT || why == ESP_RST_UNKNOWN);
    if (rtcMagic != 0x4C445243) rtcPage[0] = 0;
    rtcPage[sizeof(rtcPage) - 1] = 0;
    if (warm && rtcPictureMagic == 0x4C444943) {           // the model's picture, as named before our restart (the flight screen's picture box)
        rtcPicture[sizeof(rtcPicture) - 1] = 0;
        if (rtcPicture[0]) { kept["FrontView.exp0"].txts["path"] = rtcPicture; kept["FrontView.exp0"].txts["txt"] = rtcPicture; }
    }
    if (warm && rtcGlobalsMagic == RTC_GLOBALS_MAGIC && rtcGlobalN <= RTC_GLOBALS_MAX) {   // the main board's global variables, as last written before our restart
        int n = 0;
        for (int i = 0; i < rtcGlobalN; ++i) { rtcGlobals[i].name[sizeof(RtcGlobal::name) - 1] = 0; if (rtcGlobals[i].name[0]) { kept[rtcGlobals[i].name].ints["val"] = rtcGlobals[i].val; ++n; } }
        blog("boot", "globals kept through the restart: " + std::to_string(n));
    } else if (!warm) { rtcGlobalsMagic = RTC_GLOBALS_MAGIC; rtcGlobalN = 0; }
    const std::string last = rtcPage;
    if (warm && !pageNames.empty()) { if (!last.empty() && pageIds.count(last)) loadPage(last); else loadPage(pageNames[0]); }   // cold: the Teensy sends its page
    if (why != ESP_RST_POWERON && rtcDimMagic == RTC_DIM_MAGIC) { sysDim = constrain(rtcDim, 0, 100); blDark = false; blWant = sysDim * 255 / 100; blFadeTo(blWant, 500); }   // our own restart: back to the brightness it had, gently
    // After a restart mid-session (an OTA update) the Teensy still thinks the
    // screen is showing everything: nudge it to repaint the front page — the
    // word "FrontView" is one of its legacy text commands.
    if (page.name == "FrontView" && why == ESP_RST_SW) { delay(300); Serial.print("FrontView"); }
    bootMs = millis(); blog("boot", std::string("loop ") + (warm ? "(warm)" : "(cold)"));
    netBegin();
    updater.resume();                                      // a verdict nobody has seen, an update cut short, or new firmware on trial
    // A new screen: its card is there and has no pages on it, so there is no page to show and no button to
    // press. The one case in which the panel opens by itself: it offers to fetch the files, and waits.
    if (sdOk && pageNames.empty() && !updater.showing()) updRequested = true;
}

void loop() {
    static uint32_t lastLoop = 0; const uint32_t now = millis();
    if (lastLoop && now - lastLoop > perfLoopMaxMs) perfLoopMaxMs = now - lastLoop;
    lastLoop = now;
    uint32_t t = micros(), u;
    #define PHASE(i) u = micros(); if (u - t > phaseMax[i]) phaseMax[i] = u - t; t = u;
    pumpSerial(); linkPoll(); updPoll(); wifiPoll(); picPoll(); flightPoll(); coloursPoll(); appearancePoll(); pongPoll(); blPoll(); PHASE(0)
    audioFill(); if (!teensyLink.running()) audioWarm(); PHASE(1)
    if (!teensyLink.running()) prefsPoll(); PHASE(2)
    pollTouch(); PHASE(3)
    pollTimers(); PHASE(4)
    presentDirty(touchPainted); touchPainted = false; PHASE(5)   // a finger's feedback is shown at once; the Teensy's at the end of its burst
    netPoll(); PHASE(6)
    #undef PHASE
}
