// THE TWIN'S PSRAM PACE (1.11.116, 24 Oct 2026).
//
// The 16 MB twin's panel reads its picture from the PSRAM at 29 MB/s (14.5 MHz, the slowest clock its panel takes: at 12 MHz
// it shows its own test pattern). Anything else that moves more than ~13 kB through the PSRAM at full speed can starve the
// panel's DMA for long enough to lose a few pixels, and the rest of that frame is shifted sideways: a flicker. The copies to
// the panel were the big ones (1.11.114-115, cured by resting them and by the page flip), but the page's background painted
// into the canvas, a large box filled, a film picture decoded - each did it too (Malcolm, 24 Oct: "just the occasional
// flicker ... it usually seems to happen just before the pseudo finger pointer moves" - the film decoding its next page).
//
// So every big mover calls psramPace(pixels) as it goes: after each 6400 pixels (8 full rows, 12.8 kB) it rests the board's
// psramRestUs (300 us on the twin - the pace that never slipped on the bench; 0 on the CrowPanel, whose 10 MHz panel has
// room to spare). Calls that come with a gap of their own (the bus already rested) start the count afresh.
#pragma once
#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include <algorithm>

static uint32_t paceCount = 0, paceAt = 0, paceRests = 0;
static inline void psramPace(uint32_t px) {
    const uint32_t rest = board->psramRestUs;
    if (!rest) return;
    const uint32_t now = micros();
    if (now - paceAt > rest) paceCount = 0;               // (idle since the last call: the bus has had its rest)
    paceAt = now;
    if ((paceCount += px) >= 6400) { delayMicroseconds(rest); paceCount = 0; paceAt = micros(); paceRests++; }
}

// THE GENTLE WRITE-BACK (25 Oct 2026). The panel's DMA reads the PSRAM; what the CPU drew sits in the cache until written
// back, and Cache_WriteBack_Addr over a freshly written region (8 rows = 12.8 kB, 16 rows = 25.6 kB) writes it all out in
// one burst that holds the bus 100-200 us: the DMA starves for that long and the rest of that frame is shifted sideways -
// Malcolm's "part of the image shifts sideways then back again, usually the lower part", the last flicker left on the twin
// once the frames were chained by the hardware (src/frame_ring.h). Measured with the slip counter (dma_watch.h): a
// whole-screen copy with its write-backs slipped 2 frames in 3 runs, the same copy without them none, 256-byte pieces
// 8 us apart none in 3000 pieces. So on the twin every write-back the panel will read goes in pieces of 256 bytes (8 cache
// lines, ~4 us of bus) with an 8 us breath between - the DMA's FIFO rides out 4 us. The CrowPanel (psramRestUs 0) as before.
static uint32_t wbPieceBytes = 1024, wbGapUs = 8;      // (bench: /stall?kind=wbpiece&kb=bytes, wbgap&kb=us; measured 25 Oct: 256-2048 B pieces slip-free, 4096 slipped once in 1.5 MB; 1024 for margin: 20 us a kB against 30 at 256)
static inline void wbPaced(uint32_t addr, uint32_t len) {
    if (!board->psramRestUs || len <= 2 * wbPieceBytes) { Cache_WriteBack_Addr(addr, len); return; }
    for (uint32_t off = 0; off < len; off += wbPieceBytes) { Cache_WriteBack_Addr(addr + off, len - off < wbPieceBytes ? len - off : wbPieceBytes); delayMicroseconds(wbGapUs); }
}
// The canvases (the page and our layer) fill big boxes a row at a time, paced. Everything else is Arduino_Canvas's own.
// (1.11.116) The page's canvas is one of the three panel buffers in turn (main.cpp, "the rotation"): aim() points it at the
// buffer that is the canvas now, and with lazy set every write first makes sure the rows it touches have been caught up
// from the buffer on show (canvasEnsureRows, main.cpp) - the buffer a rotation leaves behind still holds the page before.
static void canvasEnsureRows(int y, int h);
class PacedCanvas : public Arduino_Canvas {
public:
    bool lazy = false;
    // (1.11.116) The layer's canvas keeps the box round everything drawn on it since touchedClear(): main.cpp's "flight
    // spare" composes only that much when the flight screen comes back on show.
    bool track = false; int tx0 = 0, ty0 = 0, tx1 = 0, ty1 = 0;
    void touchedClear() { tx0 = ty0 = 1 << 14; tx1 = ty1 = -1; }
    bool touchedAny() const { return tx1 >= tx0 && ty1 >= ty0; }
    inline void touch(int x, int y, int w, int h) { if (!track) return; if (x < tx0) tx0 = x; if (y < ty0) ty0 = y; if (x + w > tx1) tx1 = x + w; if (y + h > ty1) ty1 = y + h; }
    PacedCanvas(int16_t w, int16_t h, Arduino_G *output) : Arduino_Canvas(w, h, output) { touchedClear(); }
    void aim(uint16_t *fb) { _framebuffer = fb; }
    void writePixelPreclipped(int16_t x, int16_t y, uint16_t color) override { if (lazy) canvasEnsureRows(y, 1); touch(x, y, 1, 1); Arduino_Canvas::writePixelPreclipped(x, y, color); }
    void writeFastVLine(int16_t x, int16_t y, int16_t h, uint16_t color) override { if (lazy) canvasEnsureRows(y, h); touch(x, y, 1, h); Arduino_Canvas::writeFastVLine(x, y, h, color); }
    void writeFastHLine(int16_t x, int16_t y, int16_t w, uint16_t color) override { if (lazy) canvasEnsureRows(y, 1); touch(x, y, w, 1); Arduino_Canvas::writeFastHLine(x, y, w, color); }
    void writeFillRectPreclipped(int16_t x, int16_t y, int16_t w, int16_t h, uint16_t color) override {
        if (lazy) canvasEnsureRows(y, h);
        touch(x, y, w, h);
        if (!board->psramRestUs || (int32_t) w * h < 6400 || !_framebuffer) { Arduino_Canvas::writeFillRectPreclipped(x, y, w, h, color); return; }
        uint16_t *row = _framebuffer + (int32_t) y * _width + x;
        for (int j = 0; j < h; ++j, row += _width) { std::fill_n(row, w, color); psramPace(w); }
    }
    void drawIndexedBitmap(int16_t x, int16_t y, uint8_t *bitmap, uint16_t *color_index, int16_t w, int16_t h, int16_t x_skip = 0) override { if (lazy) canvasEnsureRows(y, h); touch(x, y, w, h); Arduino_Canvas::drawIndexedBitmap(x, y, bitmap, color_index, w, h, x_skip); }
    void drawIndexedBitmap(int16_t x, int16_t y, uint8_t *bitmap, uint16_t *color_index, uint8_t chroma_key, int16_t w, int16_t h, int16_t x_skip = 0) override { if (lazy) canvasEnsureRows(y, h); touch(x, y, w, h); Arduino_Canvas::drawIndexedBitmap(x, y, bitmap, color_index, chroma_key, w, h, x_skip); }
    void draw16bitRGBBitmap(int16_t x, int16_t y, uint16_t *bitmap, int16_t w, int16_t h) override {
        if (lazy) canvasEnsureRows(y, h);
        touch(x, y, w, h);
        Arduino_Canvas::draw16bitRGBBitmap(x, y, bitmap, w, h);
        psramPace((uint32_t) w * h);
    }
    void draw16bitRGBBitmapWithTranColor(int16_t x, int16_t y, uint16_t *bitmap, uint16_t transparent_color, int16_t w, int16_t h) override { if (lazy) canvasEnsureRows(y, h); touch(x, y, w, h); Arduino_Canvas::draw16bitRGBBitmapWithTranColor(x, y, bitmap, transparent_color, w, h); psramPace((uint32_t) w * h); }
    void draw16bitBeRGBBitmap(int16_t x, int16_t y, uint16_t *bitmap, int16_t w, int16_t h) override { if (lazy) canvasEnsureRows(y, h); touch(x, y, w, h); Arduino_Canvas::draw16bitBeRGBBitmap(x, y, bitmap, w, h); psramPace((uint32_t) w * h); }
};
