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
#include <xtensa/hal.h>                                  // xthal_get_ccount: the write-back pieces' cost
#include "busy_what.h"                               // (25 Oct evening) the tag the EOF interrupt reads at a slip

static uint32_t paceCount = 0, paceAt = 0, paceRests = 0;
static uint32_t paceQuantumPx = 6400;                     // (bench, 26 Oct: /stall?kind=pacepx&kb=px - a shorter burst between rests, the rest scaled with it: the same duty, a smaller bite out of the panel)
static bool stripOn = false; static volatile bool stripArm = false;   // (26 Oct evening) src/strip_feed.h: the panel reads internal RAM - no pacing needed while it does
static uint32_t paceRestOverride = 0;                     // (bench, 26 Oct: /stall?kind=rest&kb=us - the rest after each quantum instead of the board's; 0 = the board's)
static inline void psramPace(uint32_t px) {
    const uint32_t rest = paceRestOverride ? paceRestOverride : board->psramRestUs;
    if (!rest || stripOn) return;
    const uint32_t now = micros();
    if (now - paceAt > rest) paceCount = 0;               // (idle since the last call: the bus has had its rest)
    paceAt = now;
    if ((paceCount += px) >= paceQuantumPx) { { Busy r(BUSY_REST); delayMicroseconds(paceQuantumPx >= 6400 ? rest : rest * paceQuantumPx / 6400); } paceCount = 0; paceAt = micros(); paceRests++; }
}

// THE GENTLE WRITE-BACK (25 Oct 2026). The panel's DMA reads the PSRAM; what the CPU drew sits in the cache until written
// back, and Cache_WriteBack_Addr over a freshly written region (8 rows = 12.8 kB, 16 rows = 25.6 kB) writes it all out in
// one burst that holds the bus 100-200 us: the DMA starves for that long and the rest of that frame is shifted sideways -
// Malcolm's "part of the image shifts sideways then back again, usually the lower part", the last flicker left on the twin
// once the frames were chained by the hardware (src/frame_ring.h). Measured with the slip counter (dma_watch.h): a
// whole-screen copy with its write-backs slipped 2 frames in 3 runs, the same copy without them none, 256-byte pieces
// 8 us apart none in 3000 pieces. So on the twin every write-back the panel will read goes in pieces of 256 bytes (8 cache
// lines, ~4 us of bus) with an 8 us breath between - the DMA's FIFO rides out 4 us. The CrowPanel (psramRestUs 0) as before.
static uint32_t wbPieceBytes = 256, wbGapUs = 8, wbCleanCy = 0;   // (bench: /stall?kind=wbpiece&kb=bytes, wbgap&kb=us, wbclean&kb=cycles. 25 Oct morning at a 15 us bar: 256-2048 B slip-free, 1024 chosen; 25 Oct EVENING at a 7 us bar, three whole-screen presents each: 1024 B 4 slips (Malcolm's "little shimmy sideways" before each new background), 512 B one, 256 B none (209 ms a present against 157), 128 B none (277 ms). 256 B shipped in 1.11.125; his run on it still had 7-10 us slips in the catch-up copies' write-backs ("a sideways shift, usually of the lower screen, much more rare now") -> 128 B tried 21:05: the fine estimator 0.9-1.2 us a frame against 1.3-1.4 at 256 B, a full-screen present 279 ms against 211 - not worth 68 ms; 256 B stays. The adaptive gap below is a dead end (wbCleanCy 0): the ROM routine returns before the bus transfer, so a clean piece and a dirty one cost the same cycles.)
// THE ADAPTIVE GAP (25 Oct 21:00). The breath after a piece is only needed when the piece WROTE something; a clean piece
// (no dirty line in it - most of a 768 kB sweep) holds the bus for nothing. The ROM routine's cost tells them apart: the
// cycle count of each call, against wbCleanCy (0 = a breath after every piece; calibrated on the bench with /perf "wb":
// pieces, slow, cy_min, cy_max - /stall?kind=wbtime on a clean canvas gives the clean cost, present&kb=480 the dirty one).
static volatile uint32_t wbPieces = 0, wbSlow = 0, wbCyMin = 0xFFFFFFFF, wbCyMax = 0;
// (31 Oct 2026) WITH THE STRIPS ON the panel reads internal RAM, but the feeder's DMA reads the PSRAM - 6.4 kB every 240 us -
// and a long write-back starves it: the bench showed every repeated band and lost frame of a scroll OUTSIDE the slide's own
// rows (which write back 1.5 kB at a time): in the canvas catch-up (12.8 kB a band) and in present's write-back of a dirty
// box (hundreds of kB in one call). So with the strips on too a long write-back goes in pieces, with a breath between
// (bench: /stall?kind=wbspiece&kb=bytes, kind=wbsgap&kb=us).
static uint32_t wbStripPiece = 1024, wbStripGapUs = 10;
static inline void wbPaced(uint32_t addr, uint32_t len) {
    Busy busy_(BUSY_WB);
    if (!board->psramRestUs || len <= 2 * wbPieceBytes) { Cache_WriteBack_Addr(addr, len); return; }
    if (stripOn) {
        if (len <= 2 * wbStripPiece) { Cache_WriteBack_Addr(addr, len); return; }
        for (uint32_t off = 0; off < len; off += wbStripPiece) { const uint32_t n = len - off < wbStripPiece ? len - off : wbStripPiece; Cache_WriteBack_Addr(addr + off, n); wbPieces++; if (wbStripGapUs) delayMicroseconds(wbStripGapUs); }
        return;
    }
    for (uint32_t off = 0; off < len; off += wbPieceBytes) {
        const uint32_t n = len - off < wbPieceBytes ? len - off : wbPieceBytes;
        const uint32_t c0 = xthal_get_ccount();
        Cache_WriteBack_Addr(addr + off, n);
        const uint32_t cy = xthal_get_ccount() - c0;
        wbPieces++; if (cy < wbCyMin) wbCyMin = cy; if (cy > wbCyMax) wbCyMax = cy;
        if (!wbCleanCy || cy > wbCleanCy) { wbSlow++; delayMicroseconds(wbGapUs); }
    }
}
// The canvases (the page and our layer) fill big boxes a row at a time, paced. Everything else is Arduino_Canvas's own.
// (1.11.116) The page's canvas is one of the three panel buffers in turn (main.cpp, "the rotation"): aim() points it at the
// buffer that is the canvas now, and with lazy set every write first makes sure the rows it touches have been caught up
// from the buffer on show (canvasEnsureRows, main.cpp) - the buffer a rotation leaves behind still holds the page before.
static void canvasEnsureRows(int y, int h);
static inline bool dmaReady();                            // (1.11.127) src/dma_copy.h, included after this: a big fill goes by DMA
static bool dmaFillRows(uint16_t *dst, const uint16_t *srcRow, int x0, int x1, int y, int h);
static void dmaDropLines(uint16_t *fb, int x0, int x1, int y, int h);
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
        // (1.11.127) A big fill by DMA: the first row filled by the CPU and written back, every other row's whole lines copied
        // from it by the DMA (PSRAM to PSRAM, the panel served first - src/dma_copy.h), the margins up to 31 pixels at each
        // end filled by hand. The cache's lines of the rows the DMA writes are dropped first.
        const int xi0 = (x + 31) & ~31, xi1 = (x + w) & ~31;
        if (dmaReady() && xi1 - xi0 >= 64 && h >= 8 && !((uintptr_t) _framebuffer & 63)) {
            std::fill_n(row, w, color);
            wbPaced((uint32_t) (_framebuffer + (int32_t) y * _width + xi0), (uint32_t) (xi1 - xi0) * 2);
            dmaDropLines(_framebuffer, xi0, xi1, y + 1, h - 1);
            if (dmaFillRows(_framebuffer, _framebuffer + (int32_t) y * _width + xi0, xi0, xi1, y + 1, h - 1)) {
                uint16_t *r2 = row + _width;
                for (int j = 1; j < h; ++j, r2 += _width) { if (xi0 > x) std::fill_n(r2, xi0 - x, color); if (x + w > xi1) std::fill_n(r2 + (xi1 - x), x + w - xi1, color); }
                return;
            }
            row += _width; --h;                                // (the DMA did not come: the rows left, by hand)
        }
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
