// The few Arduino, SD and Arduino_GFX pieces the screen's drawing code (src/main.cpp) uses, for a Mac build that
// renders a page to a picture with the SAME code that draws it on the transmitter (render.cpp).
// The shape algorithms are Arduino_GFX's own (Adafruit GFX, BSD licence), copied so the pixels match.
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <string>
#include <vector>
#include <map>
#include <algorithm>
using std::min; using std::max;
template <class T, class L, class H> static inline T constrain(T v, L lo, H hi) { return v < (T) lo ? (T) lo : v > (T) hi ? (T) hi : v; }
static inline uint32_t millis() { return 0; }
static inline uint32_t micros() { return 0; }
static inline void *ps_malloc(size_t n) { return malloc(n); }
#define Cache_WriteBack_Addr(a, b) ((void) 0)                     // (the panel's cache: nothing to do on the Mac)
#define PROGMEM
extern std::string sdRoot;                                 // the folder that stands for the screen's card (sd/)
struct File {
    FILE *f = nullptr; size_t n = 0;
    explicit operator bool() const { return f != nullptr; }
    size_t size() const { return n; }
    size_t read(uint8_t *b, size_t k) { return f ? fread(b, 1, k, f) : 0; }
    int read() { return f ? fgetc(f) : -1; }                                  // (ArduinoJson reads a File as a custom reader)
    size_t readBytes(char *b, size_t k) { return f ? fread(b, 1, k, f) : 0; }
    bool seek(uint32_t pos) { return f && fseek(f, (long) pos, SEEK_SET) == 0; }
    void close() { if (f) fclose(f); f = nullptr; }
};
struct SDClass {
    File open(const char *p) { File r; r.f = fopen((sdRoot + p).c_str(), "rb"); if (r.f) { fseek(r.f, 0, SEEK_END); r.n = ftell(r.f); fseek(r.f, 0, SEEK_SET); } return r; }
    bool exists(const char *p) { FILE *f = fopen((sdRoot + p).c_str(), "rb"); if (f) fclose(f); return f != nullptr; }
};
extern SDClass SD;
struct SerialStub { size_t write(const uint8_t *, size_t n) { return n; } size_t print(const char *) { return 0; } int available() { return 0; } };
extern SerialStub Serial;
#define _swap_int16_t(a, b) { int16_t t = a; a = b; b = t; }
struct Gfx {
    uint16_t *fb = nullptr; const int16_t _max_x = 799, _max_y = 479;
    void startWrite() {} void endWrite() {}
    void writePixel(int16_t x, int16_t y, uint16_t c) { if (x >= 0 && y >= 0 && x <= _max_x && y <= _max_y) fb[y * 800 + x] = c; }
    void writeFastVLine(int16_t x, int16_t y, int16_t h, uint16_t c) { for (int16_t i = y; i < y + h; i++) writePixel(x, i, c); }
    void writeFastHLine(int16_t x, int16_t y, int16_t w, uint16_t c) { for (int16_t i = x; i < x + w; i++) writePixel(i, y, c); }
    void writeFillRectPreclipped(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t c) { for (int16_t i = y; i < y + h; i++) writeFastHLine(x, i, w, c); }
    void writeFillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color) {
        if (w && h) { if (w < 0) { x += w + 1; w = -w; }
            if (x <= _max_x) { if (h < 0) { y += h + 1; h = -h; }
                if (y <= _max_y) { int16_t x2 = x + w - 1;
                    if (x2 >= 0) { int16_t y2 = y + h - 1;
                        if (y2 >= 0) { if (x < 0) { x = 0; w = x2 + 1; } if (y < 0) { y = 0; h = y2 + 1; }
                            if (x2 > _max_x) w = _max_x - x + 1; if (y2 > _max_y) h = _max_y - y + 1;
                            writeFillRectPreclipped(x, y, w, h, color); } } } } }
    }
    void fillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t c) { writeFillRect(x, y, w, h, c); }
    void fillScreen(uint16_t c) { fillRect(0, 0, 800, 480, c); }
    void drawFastHLine(int16_t x, int16_t y, int16_t w, uint16_t c) { writeFastHLine(x, y, w, c); }
    void drawFastVLine(int16_t x, int16_t y, int16_t h, uint16_t c) { writeFastVLine(x, y, h, c); }
    void drawRect(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t c) { writeFastHLine(x, y, w, c); writeFastHLine(x, y + h - 1, w, c); writeFastVLine(x, y, h, c); writeFastVLine(x + w - 1, y, h, c); }
    void draw16bitRGBBitmap(int16_t x, int16_t y, uint16_t *b, int16_t w, int16_t h) { for (int j = 0; j < h; ++j) for (int i = 0; i < w; ++i) writePixel(x + i, y + j, b[j * w + i]); }
    void drawEllipseHelper(int32_t x, int32_t y, int32_t rx, int32_t ry, uint8_t cornername, uint16_t color) {
        if (rx < 0 || ry < 0 || ((rx == 0) && (ry == 0))) return;
        if (ry == 0) { drawFastHLine(x - rx, y, (ry << 2) + 1, color); return; }
        if (rx == 0) { drawFastVLine(x, y - ry, (rx << 2) + 1, color); return; }
        int32_t xt, yt, s, i; int32_t rx2 = rx * rx; int32_t ry2 = ry * ry;
        i = -1; xt = 0; yt = ry; s = (ry2 << 1) + rx2 * (1 - (ry << 1));
        do { while (s < 0) s += ry2 * ((++xt << 2) + 2);
            if (cornername & 0x1) writeFastHLine(x - xt, y - yt, xt - i, color);
            if (cornername & 0x2) writeFastHLine(x + i + 1, y - yt, xt - i, color);
            if (cornername & 0x4) writeFastHLine(x + i + 1, y + yt, xt - i, color);
            if (cornername & 0x8) writeFastHLine(x - xt, y + yt, xt - i, color);
            i = xt; s -= (--yt) * rx2 << 2; } while (ry2 * xt <= rx2 * yt);
        i = -1; yt = 0; xt = rx; s = (rx2 << 1) + ry2 * (1 - (rx << 1));
        do { while (s < 0) s += rx2 * ((++yt << 2) + 2);
            if (cornername & 0x1) writeFastVLine(x - xt, y - yt, yt - i, color);
            if (cornername & 0x2) writeFastVLine(x + xt, y - yt, yt - i, color);
            if (cornername & 0x4) writeFastVLine(x + xt, y + i + 1, yt - i, color);
            if (cornername & 0x8) writeFastVLine(x - xt, y + i + 1, yt - i, color);
            i = yt; s -= (--xt) * ry2 << 2; } while (rx2 * yt <= ry2 * xt);
    }
    void fillEllipseHelper(int32_t x, int32_t y, int32_t rx, int32_t ry, uint8_t corners, int16_t delta, uint16_t color) {
        if (rx < 0 || ry < 0 || ((rx == 0) && (ry == 0))) return;
        if (ry == 0) { drawFastHLine(x - rx, y, (ry << 2) + 1, color); return; }
        if (rx == 0) { drawFastVLine(x, y - ry, (rx << 2) + 1, color); return; }
        int32_t xt, yt, i; int32_t rx2 = (int32_t) rx * rx; int32_t ry2 = (int32_t) ry * ry; int32_t s;
        writeFastHLine(x - rx, y, (rx << 1) + 1, color);
        i = 0; yt = 0; xt = rx; s = (rx2 << 1) + ry2 * (1 - (rx << 1));
        do { while (s < 0) s += rx2 * ((++yt << 2) + 2);
            if (corners & 1) writeFillRect(x - xt, y - yt, (xt << 1) + 1 + delta, yt - i, color);
            if (corners & 2) writeFillRect(x - xt, y + i + 1, (xt << 1) + 1 + delta, yt - i, color);
            i = yt; s -= (--xt) * ry2 << 2; } while (rx2 * yt <= ry2 * xt);
        xt = 0; yt = ry; s = (ry2 << 1) + rx2 * (1 - (ry << 1));
        do { while (s < 0) s += ry2 * ((++xt << 2) + 2);
            if (corners & 1) writeFastHLine(x - xt, y - yt, (xt << 1) + 1 + delta, color);
            if (corners & 2) writeFastHLine(x - xt, y + yt, (xt << 1) + 1 + delta, color);
            s -= (--yt) * rx2 << 2; } while (ry2 * xt <= rx2 * yt);
    }
    void writeLine(int16_t x0, int16_t y0, int16_t x1, int16_t y1, uint16_t color) {
        bool steep = abs(y1 - y0) > abs(x1 - x0);
        if (steep) { _swap_int16_t(x0, y0); _swap_int16_t(x1, y1); }
        if (x0 > x1) { _swap_int16_t(x0, x1); _swap_int16_t(y0, y1); }
        int16_t dx = x1 - x0, dy = abs(y1 - y0), err = dx >> 1, ystep = (y0 < y1) ? 1 : -1;
        for (; x0 <= x1; x0++) { if (steep) writePixel(y0, x0, color); else writePixel(x0, y0, color); err -= dy; if (err < 0) { err += dx; y0 += ystep; } }
    }
    void drawLine(int16_t x0, int16_t y0, int16_t x1, int16_t y1, uint16_t c) {
        if (x0 == x1) { if (y0 > y1) _swap_int16_t(y0, y1); drawFastVLine(x0, y0, y1 - y0 + 1, c); }
        else if (y0 == y1) { if (x0 > x1) _swap_int16_t(x0, x1); drawFastHLine(x0, y0, x1 - x0 + 1, c); }
        else writeLine(x0, y0, x1, y1, c);
    }
    void fillCircle(int16_t x, int16_t y, int16_t r, uint16_t c) { fillEllipseHelper(x, y, r, r, 3, 0, c); }
    void drawCircle(int16_t x, int16_t y, int16_t r, uint16_t c) { drawEllipseHelper(x, y, r, r, 0xf, c); }
    void drawRoundRect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r, uint16_t color) {
        int16_t max_radius = ((w < h) ? w : h) / 2; if (r > max_radius) r = max_radius;
        writeFastHLine(x + r, y, w - 2 * r, color); writeFastHLine(x + r, y + h - 1, w - 2 * r, color);
        writeFastVLine(x, y + r, h - 2 * r, color); writeFastVLine(x + w - 1, y + r, h - 2 * r, color);
        drawEllipseHelper(x + r, y + r, r, r, 1, color); drawEllipseHelper(x + w - r - 1, y + r, r, r, 2, color);
        drawEllipseHelper(x + w - r - 1, y + h - r - 1, r, r, 4, color); drawEllipseHelper(x + r, y + h - r - 1, r, r, 8, color);
    }
    void fillRoundRect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r, uint16_t color) {
        int16_t max_radius = ((w < h) ? w : h) / 2; if (r > max_radius) r = max_radius;
        writeFillRect(x, y + r, w, h - (r << 1), color);
        fillEllipseHelper(x + r, y + r, r, r, 1, w - 2 * r - 1, color);
        fillEllipseHelper(x + r, y + h - r - 1, r, r, 2, w - 2 * r - 1, color);
    }
    void fillTriangle(int16_t x0, int16_t y0, int16_t x1, int16_t y1, int16_t x2, int16_t y2, uint16_t color) {
        int16_t a, b, y, last;
        if (y0 > y1) { _swap_int16_t(y0, y1); _swap_int16_t(x0, x1); }
        if (y1 > y2) { _swap_int16_t(y2, y1); _swap_int16_t(x2, x1); }
        if (y0 > y1) { _swap_int16_t(y0, y1); _swap_int16_t(x0, x1); }
        if (y0 == y2) { a = b = x0; if (x1 < a) a = x1; else if (x1 > b) b = x1; if (x2 < a) a = x2; else if (x2 > b) b = x2; writeFastHLine(a, y0, b - a + 1, color); return; }
        int16_t dx01 = x1 - x0, dy01 = y1 - y0, dx02 = x2 - x0, dy02 = y2 - y0, dx12 = x2 - x1, dy12 = y2 - y1;
        int32_t sa = 0, sb = 0;
        if (y1 == y2) last = y1; else last = y1 - 1;
        for (y = y0; y <= last; y++) { a = x0 + sa / dy01; b = x0 + sb / dy02; sa += dx01; sb += dx02; if (a > b) _swap_int16_t(a, b); writeFastHLine(a, y, b - a + 1, color); }
        sa = (int32_t) dx12 * (y - y1); sb = (int32_t) dx02 * (y - y0);
        for (; y <= y2; y++) { a = x1 + sa / dy12; b = x0 + sb / dy02; sa += dx12; sb += dx02; if (a > b) _swap_int16_t(a, b); writeFastHLine(a, y, b - a + 1, color); }
    }
};
