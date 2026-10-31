// LDRC transmitter V1B screen: a Nextion emulator on the CrowPanel 5.0 (800x480).
//
// The Teensy 4.1 keeps talking Nextion on UART0 (page / vis / click / X.txt= /
// X.val= / get …, 921600 baud). The 58 pages of TX_NEXTION.HMI live on the TF
// card as decoded by hmi/extract_hmi.py + hmi/build_sd.py: geometry, colours,
// fonts, text, and the pages' own event code, which a small interpreter runs
// (lib/NextionScript) so buttons answer the Teensy with the very bytes the
// Nextion sent. Backgrounds are raw RGB565 files blitted straight in.
//
// Draw discipline for the RGB panel: 10 MHz pixel clock (14.5 on the 16 MB twin,
// src/board.h) and never a whole-screen redraw except on a page change (PSRAM
// contention flickers otherwise).
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
#include <esp_wifi.h>                                   // (1.11.139) esp_wifi_sta_get_ap_info: joined by the driver's account (wifiUpNow)
#include <ArduinoOTA.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <Preferences.h>
#include <esp_log.h>
#include <esp_system.h>
#include <esp_core_dump.h>
#include "tooth_icon.h"
#include <esp_partition.h>
#include "board.h"                                      // (1.11.111) which of the two boards this is: the pins that differ, the update slot
#include "tls_memory.h"                                 // (1.11.146) the secure connection's ~70 kB come from the PSRAM, not the internal RAM

#ifndef NEXTION_BAUD
#define NEXTION_BAUD 921600
#endif
// The screen's own version. "Check for update" compares it with the release on messiter.com: a release
// with different firmware for the screen MUST carry a different number here (TXV1B dev/release_v1b.py checks).
#ifndef SCREEN_VERSION                                   // (the test builds of platformio.ini name themselves)
#define SCREEN_VERSION "1.11.150"
#endif
SET_LOOP_TASK_STACK_SIZE(16 * 1024);                  // (1.11.16) the main task had 2.5 kB of its 8 to spare at the worst moment seen: room. (23 Oct 2026: outside the #ifndef, so the bench builds - which name themselves - get it too; the published ones always had it)
constexpr int W = 800, H = 480, LCD_BL = 2, TP_SDA = 19, TP_SCL = 20;
constexpr int SD_MOSI = 11, SD_MISO = 13, SD_CLK = 12, SD_CS = 10;

// (1.11.111) Made in setup(), once boardDetect() has said which board this is: the pixel clock pin and the panel's timing
// are the board's (board.h). The data pins, DE, VSYNC and HSYNC are the same on both.
Arduino_ESP32RGBPanel *panel = nullptr;
Arduino_RGB_Display *screen = nullptr;
class PacedCanvas;                                            // (src/psram_pace.h, included below)
PacedCanvas *canvas = nullptr;                                // every draw lands here (PSRAM); present() copies finished rectangles to the panel
Arduino_GFX *gfx = nullptr;                                   // the screen at first, switched to the canvas at boot
#include "psram_pace.h"                                // (1.11.116: the twin's big moves through the PSRAM, paced; the canvases' big fills)
// (1.11.120) A big read off the card into the PSRAM goes in slabs of 4 kB with the pace's rests between. The whole file in
// one read - a 768 kB background, a page's 30 kB of JSON, a 40 kB clip - was one unpaced burst of PSRAM writes (the card
// driver copies it in through a bounce buffer): a slip of the twin's picture at the first visit to each page and each
// background, and at every clip the quiet-page warm-up brought in.
static size_t sdReadPaced(File &f, uint8_t *dst, size_t n) {
    Busy busy_(BUSY_SD);
    size_t got = 0;
    while (got < n) {
        const int r = f.read(dst + got, std::min((size_t) 4096, n - got));
        if (r <= 0) break;
        got += (size_t) r; psramPace((uint32_t) r);          // (bytes counted as pixels: a rest every 6.4 kB)
    }
    return got;
}
static void panelMake() {
    const BoardPins &b = *board;
    panel = new Arduino_ESP32RGBPanel(40, 41, 39, b.pclk, 45, 48, 47, 21, 14, 5, 6, 7, 15, 16, 4, 8, 3, 46, 9, 1,
                                      0, b.hsFp, b.hsPw, b.hsBp, 0, b.vsFp, b.vsPw, b.vsBp, 1, b.pclkHz);
    screen = new Arduino_RGB_Display(W, H, panel, 0, true);
    canvas = new PacedCanvas(W, H, screen);
    gfx = screen;
}
static uint16_t *fbNow = nullptr, *screenFb = nullptr;        // what gfx draws into / what the panel shows
static uint16_t *pageFb = nullptr;                            // the canvas: the page, as the Teensy draws it
// (1.11.116) THE ROTATION, on the twin. Three buffers of a page each (src/page_flip.h flipFb[]): the one on show, a spare,
// and the canvas. A page change draws the new page INTO THE CANVAS, as ever, and then the panel is simply pointed at the
// canvas: no copy. The buffer that was on show becomes the canvas, and it still holds the page before - so it is caught
// up from the one on show in bands of 8 rows, each band before anything draws into it (canvasEnsureRows, called by every
// write into the canvas: PacedCanvas, drawGlyphs, restoreRect) and otherwise a couple of bands a pass (flipTick). Big
// changes that are not a page change (a film's picture under our layer, cls) go the other way, composed into the spare
// and flipped to (flipBigChange), as in 1.11.115.
static int flipCanvas = 2, flipSpare = 1;                     // which of flipFb[] is the canvas / the spare (the panel shows flipShown)
static uint64_t canvasStale = 0;                              // bands of 8 rows the canvas has not yet been caught up in (bit b: rows 8b..8b+7)
static bool flipRotating = false;                             // the flip asked for is a rotation (the canvas goes on show)
static int flipFrom = 0;                                      // the buffer on show when the flip was asked for
static int topDrawDepth = 0;                                  // (a rotation is completed only outside a TopDraw: it moves fbNow)
static uint32_t flipRotateN = 0, canvasEnsureN = 0;
// (1.11.116) THE FLIGHT SPARE. The flight screen (src/flight_device.h, topWho 5) covers the whole glass: on the front page the
// picture IS the layer, and coming back to the front page composed all 768 kB of it again (290 ms). While the pilot is away
// on another page the layer is not drawn on, so: when a rotation takes the flight composite off show, that buffer becomes
// the SPARE and is kept (nothing is presented into it, no catching up); the layer's canvas notes the box round anything
// drawn on it since; and the next compose for the flight screen copies only that box - usually nothing - and flips.
static const int FLIGHT_LAYER_WHO = 5;
static bool shownIsFlight = false;                            // the buffer on show is the flight composite
static bool spareHoldsFlight = false;                         // the spare is a kept flight composite (the layer's canvas tracks what changed since)
static bool flipKept = false;                                 // the flip in flight goes to a kept flight spare: the buffer it leaves lags by the whole page
// (1.11.116) Under a flight screen that covers the whole glass, the page itself is not seen: coming back to the front page
// its drawing (150 ms) is put off, and done only if something will show it - the layer going down, or a page drawn over it.
static bool pageDeferred = false;
static void drawDeferred();
static uint32_t benchSkip = 0;                                // (25 Oct, bench) /stall?kind=skip&kb=MASK: 1 no pictures after a rotation, 2 no catch-up copies, 4 no warm-ups - which of them slips the twin's picture?
static bool benchNoWb = false;                                // (bench) copyRows without its cache write-backs
// Our own panel ("Check for update") has a layer of its own, laid over the page as rectangles go to the
// glass: the Teensy goes on drawing the page underneath, and nothing it draws can show through the panel
// or damage it. When the panel goes, the page is there as the Teensy last drew it.
static PacedCanvas *topCanvas = nullptr; static uint16_t *topFb = nullptr;
static bool topOn = false;
static int topWho = 0;                                        // whose it is: 1 the update panel (src/update_device.h), 2 the WiFi page (src/wifi_device.h), 3 the link's panel, 4 the picture chooser (src/pics_device.h), 5 the flight screen, 6 its setup page (src/flight_device.h)
static int topX = 40, topY = 36, topW = 720, topH = 408;      // the part of the screen it covers
// (1.11.94) A second stretch of the layer, on the same rows as the first: the help page's "Fix problems" button, top right,
// beside "Animation" top left - with the page's title between them, showing. Used only while those buttons have the layer.
static const int TOP_TWIN_WHO = 12;                          // (film_device.h's FILM_BTN_WHO)
static int top2X = 0, top2W = 0;
static bool topTwin() { return topWho == TOP_TWIN_WHO && top2W > 0; }
// Copy a finished rectangle from the canvas to the panel: one move per component, so nothing is ever seen
// half-drawn (the help text flashed white on every scroll step), and the panel's PSRAM buffer is written
// back from the CPU cache for its DMA.
// The panel's quiet time (1.11.67; Malcolm 15 Oct: "When switching from defined screen to original screen, or back again,
// there is a little flicker", and of 1.11.66 "It's slightly worse"). A whole-screen change is a 768 kB copy that takes 43 ms
// (measured on his screen 29 Sep): longer than the panel's own scan of a frame (41 ms), which shares the PSRAM with it.
// Started at any moment - or at a frame's start (1.11.66) - the scan overtook it part-way down (the old picture below the
// new for a frame) and lost PSRAM time to it (the sideways slip). IDF 4.4's RGB driver stops the panel at every frame's
// end and starts it again from its interrupt, calling on_frame_trans_done just before. So the front screen's switch asks
// for a quiet frame: that frame's picture is followed by the longest blank the panel's registers allow (vt_height 1023:
// 528 lines, 45 ms - lines after the picture, so harmless whether the panel follows DE or the sync lines), and the change
// is drawn and copied in that blank, when nothing is being scanned at all. The next frame shows it whole. The copy goes
// top-down, so even one that runs past the blank stays ahead of the next scan. Nothing waits in a loop: the screen goes on
// answering the main board (it allows 100 ms for a reply) while the quiet frame comes round. The hook: Arduino_GFX 1.3.8
// keeps the panel private, so the standard explicit-instantiation route reaches the member (no change to the library;
// only the fields up to user_ctx match IDF 4.4.7's own struct - GFX's copy lacks lcd_clk_flags - so nothing after them
// is touched). Without the hook nothing waits: the copy is made at once, as before 1.11.66.
template <typename Tag, typename Tag::type M> struct PanelRob { friend typename Tag::type panelMember(Tag) { return M; } };
struct RgbPanelTag { typedef esp_rgb_panel_t *Arduino_ESP32RGBPanel::*type; friend type panelMember(RgbPanelTag); };
template struct PanelRob<RgbPanelTag, &Arduino_ESP32RGBPanel::_rgb_panel>;
#include "quiet_time.h"                                // (the quiet time's sums and jobs, host-tested: hmi/test_quiet)
#include "page_flip.h"                                 // (1.11.115: the twin's two panel buffers)
#include "dma_watch.h"                                 // (25 Oct 2026: the panel's DMA met its EOF late = the picture slipped; /perf "dma")
#include "frame_ring.h"                                // (25 Oct 2026: the frames chained by the hardware, no restart by software; /status "ring")
#include "dma_copy.h"                                  // (26 Oct 2026, bench: a GDMA memory-to-memory copy into the panel's buffers - no cache write-backs; /stall m2m, m2mrows, lcdpri)
#include "strip_feed.h"                                // (26 Oct 2026, evening: the panel reads internal RAM, fed by a DMA copy from the PSRAM picture; pref "strips", /status "strips")
static bool updShowing();                              // (update_device.h, included later: the strips stand down while the update page is up)
#include "layer_rows.h"                                // (1.11.94: the panel's rows with our layer over one or two stretches, host-tested: hmi/test_film)
static bool IRAM_ATTR onFrameEnd(esp_lcd_panel_handle_t, esp_lcd_rgb_panel_event_data_t *, void *) { dmaFrameTick(); dmaSpin(); ringFrameEnd(); quietFrameEnd(); flipFrameEnd(); return false; }
static void hookFrameEnd() {
    esp_rgb_panel_t *p = panel->*panelMember(RgbPanelTag());
    if (!p) return;
    const uint32_t vt = LCD_CAM.lcd_ctrl.lcd_vt_height, pic = (LCD_CAM.lcd_ctrl1.lcd_vb_front + 1) + (LCD_CAM.lcd_ctrl.lcd_va_height + 1);
    if (vt >= 400 && vt < 900 && pic < vt) {           // (anything odd: no quiet frames, the copies are made at once)
        vtNormal = vt; picLines = pic; picTop = LCD_CAM.lcd_ctrl1.lcd_vb_front + 1;
        const uint32_t ht = W + board->hsFp + board->hsPw + board->hsBp;   // (1.11.113) pixel clocks a line: 855 on the CrowPanel, 832 on the twin
        quietFrameLength((uint32_t) ((uint64_t) ht * (vt + 1) * 1000000u / board->pclkHz));   // the frame's length from this board's own timing
    }
    p->user_ctx = nullptr;
    p->on_frame_trans_done = onFrameEnd;
    dmaWatchStart(p->dma_chan);                        // (dma_chan lies before user_ctx: a field GFX's copy of the struct has right)
    ringDma = p->dma_chan;
    if (vtNormal) chainFind(&p->user_ctx, p->fb, p->fb_size, p->num_dma_nodes);   // (25 Oct) the descriptor chain: the flip's and the ring's
    if (board->flip && vtNormal) flipFind(p->fb, p->fb_size);   // (1.11.115)
    else flipWhy = board->flip ? "no frame ends" : "off";
}
// Rows y..y+h-1 of the canvas, caught up from the buffer on show where they have not been since the last rotation.
static void canvasEnsureRows(int y, int h) {
    Busy busy_(BUSY_ENSURE);
    if (!canvasStale || !pageFb) return;
    if (y < 0) { h += y; y = 0; } if (y + h > H) h = H - y;
    if (h <= 0) return;
    const uint16_t *from = flipFb[flipShown];
    if (!from || from == pageFb) return;
    for (int b = y >> 3, last = (y + h - 1) >> 3; b <= last; ++b) {
        if (!(canvasStale & (1ull << b))) continue;
        const int r0 = b << 3, r1 = min(H, r0 + 8);
        // (1.11.126) By DMA, PSRAM to PSRAM (src/dma_copy.h): the canvas's lines of the band are invalidated first - the
        // band is stale by definition (nothing has been drawn into it since the rotation: every draw comes here first), and
        // what the CPU reads of it afterwards must come from the memory the DMA wrote. The buffer on show is read by nobody
        // else; where the DMA is not there, the copy by hand, the source's lines invalidated (a DMA wrote them).
        Cache_Invalidate_Addr((uint32_t) (pageFb + r0 * W), (uint32_t) (r1 - r0) * W * 2);
        if (!dmaCopyRows(pageFb, from, 0, W, r0, r1 - r0)) {
            Cache_Invalidate_Addr((uint32_t) (from + r0 * W), (uint32_t) (r1 - r0) * W * 2);
            for (int r = r0; r < r1; ++r) { memcpy(pageFb + r * W, from + r * W, W * 2); psramPace(2u * W); }   // (1.11.119: a row at a time, counted double - a copy reads as much as it writes: a rest every four rows, not one burst of 25 kB)
        }
        canvasStale &= ~(1ull << b); canvasEnsureN++;
    }
}
// (1.11.116) The rows are written back from the cache 8 at a time, as they are copied - not the whole area at the end: that
// was one burst of up to 64 kB of PSRAM writes at full speed, outside the pacing (the rare flicker left on the twin).
// By hand (the CPU through its cache): the rows composed with the layer, and every row when the DMA is not there. (1.11.126)
// The destination's lines are invalidated first: a line the DMA wrote may still sit in the cache, stale, and a partial
// write into it (a row's two ends) would write the stale pixels back with the new ones.
static void copyRowsCpu(uint16_t *dst, int x, int y, int w, int h, bool over) {
    if (dcTx) for (int yy = 0; yy < h; ++yy) { const uintptr_t a = (uintptr_t) (dst + (y + yy) * W + x) & ~(uintptr_t) 63, e = ((uintptr_t) (dst + (y + yy) * W + x + w) + 63) & ~(uintptr_t) 63; Cache_Invalidate_Addr((uint32_t) a, (uint32_t) (e - a)); }
    for (int yy = 0; yy < h; ++yy) {
        const int row = y + yy;
        if (over && row >= topY && row < topY + topH) {                     // page | panel | page: no pixel under the panel is ever shown, not even for a frame
            const bool twin = topTwin();                                     // (1.11.94: page | button | title | button | page)
            ldrclayer::composeRow(dst + row * W, pageFb + row * W, topFb + row * W, x, w, topX, topX + topW, twin ? top2X : 0, twin ? top2X + top2W : 0);
        } else memcpy(dst + row * W + x, pageFb + row * W + x, w * 2);
        if (((yy & 7) == 7 || yy == h - 1) && !benchNoWb) {
            const int first = row - (yy & 7);
            wbPaced((uint32_t) (dst + first * W + x), (uint32_t) (((row - first) * W + w) * 2));   // (25 Oct: gently - src/psram_pace.h)
        }
        psramPace(w);                                      // (1.11.116: every copy, paced on the twin - src/psram_pace.h)
    }
}
// (1.11.126) The plain rows go by DMA, PSRAM to PSRAM (src/dma_copy.h): the canvas's rows written back first (gently; most
// of their lines are clean - a walk), then the DMA copies them, whole 64-byte lines (the ends rounded out to 32 pixels: the
// canvas holds the page there too). Only the rows under the layer are composed by the CPU, as before.
static void canvasWriteBack(int x, int y, int w, int h) {   // the canvas's rows of the area, whole lines, gently (most are clean: a walk)
    const int x0 = x & ~31, x1 = min((int) W, (x + w + 31) & ~31);
    for (int r = y; r < y + h; ++r) wbPaced((uint32_t) (pageFb + r * W + x0), (uint32_t) (x1 - x0) * 2);
}
static void copyRows(uint16_t *dst, int x, int y, int w, int h, bool over, bool wbDone = false) {   // wbDone: present() wrote the canvas back already, once for both buffers
    Busy busy_(BUSY_COPY);
    canvasEnsureRows(y, h);                                // (1.11.116: a band not yet caught up holds the page before)
    if (!dmaReady() || benchNoWb) { copyRowsCpu(dst, x, y, w, h, over); return; }
    const int x0 = x & ~31, x1 = min((int) W, (x + w + 31) & ~31);
    for (int yy = 0; yy < h; ) {
        const bool composed = over && y + yy >= topY && y + yy < topY + topH;
        int n = 1; while (yy + n < h && ((over && y + yy + n >= topY && y + yy + n < topY + topH) == composed)) ++n;   // the run of rows alike
        if (composed) { copyRowsCpu(dst, x, y + yy, w, n, true); yy += n; continue; }
        if (!wbDone) canvasWriteBack(x, y + yy, w, n);
        if (!dmaCopyRows(dst, pageFb, x0, x1, y + yy, n)) copyRowsCpu(dst, x, y + yy, w, n, false);
        yy += n;
    }
}
struct PresentArea { int x, y, w, h; bool over; };
static PresentArea presentArea(int x, int y, int w, int h) {   // the part of the screen a copy covers (w 0: nothing)
    if (!pageFb || !screenFb || pageFb == screenFb) return { 0, 0, 0, 0, false };
    if (x < 0) { w += x; x = 0; } if (y < 0) { h += y; y = 0; }
    if (x + w > W) w = W - x; if (y + h > H) h = H - y;
    if (w <= 0 || h <= 0) return { 0, 0, 0, 0, false };
    const bool over = topOn && topFb && y < topY + topH && y + h > topY && (ldrclayer::spans(x, w, topX, topX + topW) || (topTwin() && ldrclayer::spans(x, w, top2X, top2X + top2W)));
    return { x, y, w, h, over };
}
static bool spareSkip(int x, int y, int w, int h);     // (26 Oct, below flipTick) true: the spare is stale and this change is noted for the next compose
static void present(int x, int y, int w, int h) {
    const PresentArea a = presentArea(x, y, w, h);
    if (a.w <= 0) return;
    // (1.11.115) With the flip, EVERY buffer but the canvas, always: the interrupt may swap them at any moment, so "the shown
    // one" read here could already be the spare (the first test: small changes lost from the new page, a big flicker).
    bool wbDone = false;
    if (dmaReady() && !benchNoWb) { canvasEnsureRows(a.y, a.h); canvasWriteBack(a.x, a.y, a.w, a.h); wbDone = true; }   // (1.11.126) the canvas written back once, not once a buffer: the second walk cost 37 ms of a full screen
    for (int i = 0; i < (flipOk ? 3 : 1); ++i) {
        if (flipOk && (i == flipCanvas || !flipFb[i])) continue;
        if (flipOk && i == flipSpare && spareHoldsFlight) continue;   // (the flight spare is kept as it is)
        if (flipOk && i == flipSpare && spareSkip(a.x, a.y, a.w, a.h)) continue;   // (26 Oct) a stale spare is left alone: this change joins what the next compose must cover
        uint16_t *dst = flipOk ? flipFb[i] : screenFb;
        copyRows(dst, a.x, a.y, a.w, a.h, a.over, wbDone);
    }
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
static bool quietSwitch = false;                       // the front screen's switch is waiting to be shown in the panel's quiet time
static QuietJob quietCopy;
static uint32_t copyUsPerKpx = 120;                    // (1.11.82) what a copy to the panel costs, measured as it goes: microseconds a thousand pixels
static bool beamHeld = false;                          // (1.11.82) a rectangle was held back for the beam last pass: look again at once
// (1.11.115) The twin's page flip (src/page_flip.h): a big change is composed into the hidden buffer, slowly, and the panel
// is pointed at it at the next frame's end. Until then a second big change waits; small ones go to both buffers. After the
// flip the buffer now hidden lacks that change: it is brought up to date a few rows each pass (flipSync), small changes
// still going to both, and folded into the next big change if one comes first.
static bool flipPending = false, flipComposing = false;
static uint64_t slideStaleWait = 0; static int slideStaleY0 = 0, slideStaleY1 = 0;   // (1.11.143) the slide text's drag: the canvas's bands to mark stale once its flip has shown them (slideDrag, slideFlipDone)
static void slideFlipDone();
// (1.11.120) The pictures off the card (a model's photo: 128 kB read a row at a time, ~100 ms) are drawn AFTER a rotation,
// not inside the page's draw: the page shows that much sooner (Models: 280-400 ms after its command -> ~130), and the card
// is no longer read while the page before is still on show (on the twin anything the card or the code streams starves the
// panel's reads: a sideways slip at the page change). The names are kept; the draw follows the flip as an ordinary change.
static bool deferPics = false; static std::vector<std::string> picsLater;
static void drawPicsLater();
static void picsLaterDrop(const std::string &nm) { for (size_t i = 0; i < picsLater.size();) { if (picsLater[i] == nm) picsLater.erase(picsLater.begin() + i); else ++i; } }
static uint32_t pageT0 = 0, pageDrawMs = 0, pageComposeMs = 0, pageShownMs = 0;
static uint32_t pageSdUs = 0, pageParseUs = 0, pagePreUs = 0, pageBgUs = 0, pageCompsUs = 0;
static uint32_t pageTextUs = 0, pagePicUs = 0, pageOtherUs = 0, pageTextN = 0, pagePicN = 0, pageOtherN = 0;   // (bench) the components by kind: text and numbers, pictures off the card, the rest   // (bench) the drawing's parts: the card, the JSON, preinitialize + background load, the background painted, the components   // (1.11.116) the last page change: ms from its command to the canvas drawn, composed, shown
static Rect16 flipComp = { 0, 0, 0, 0 };              // the big change being composed into the hidden buffer
static int flipCompRow = 0;
static uint32_t flipComposeUs = 0, flipAskedMs = 0, flipComposeMax = 0, flipWaitMax = 0, flipSyncN = 0;
static Rect16 flipBig = { 0, 0, 0, 0 }, flipStale = { 0, 0, 0, 0 };
static int flipStaleRow = 0;                           // rows of flipStale already brought up to date
// (26 Oct 2026) THE EAGER SYNC IS OFF: after a flip the spare lagged by the whole page and flipTick copied it up, 8 rows every
// 2 ms, for 120 ms - 768 kB through the CPU's cache right after a page change, and each slice's write-back shifted the new
// picture a little (Malcolm: pages with a picture "flicker for the half second after moving to that screen"; text pages hide
// the same shifts). The spare is now left stale: every present that would have gone to it joins its rectangle to flipStale
// instead, and the next big change composes the union, as it always did for a stale spare. Bench: /stall?kind=sync&kb=1.
static bool flipSyncOn = false;
static Rect16 rectJoin(const Rect16 &a, const Rect16 &b) {
    if (a.w <= 0 || a.h <= 0) return b;
    if (b.w <= 0 || b.h <= 0) return a;
    const int x = min(a.x, b.x), y = min(a.y, b.y), x1 = max(a.x + a.w, b.x + b.w), y1 = max(a.y + a.h, b.y + b.h);
    return { (int16_t) x, (int16_t) y, (int16_t) (x1 - x), (int16_t) (y1 - y) };
}
static bool spareSkip(int x, int y, int w, int h) {   // (26 Oct) with the eager sync off, a stale spare is left alone: the change joins what the next compose must cover
    if (flipSyncOn || flipStale.w <= 0) return false;
    flipStale = rectJoin(flipStale, { (int16_t) x, (int16_t) y, (int16_t) w, (int16_t) h }); flipStaleRow = 0;
    return true;
}
static void flipTick() {
    Busy busy_(BUSY_FLIP);
    ringTick();                                        // (25 Oct) the engine started again should the frames stop
    if (stripOn && updShowing() && !stripStopWanted) stripStopWanted = true;   // (26 Oct, late) the update page: the strips stand down (their 19 kB of internal RAM to the secure connection)
    stripRelease();
    if (stripWant && ringOn && !stripOn && !stripArm && !stripStopWanted && !updShowing()) stripBegin();   // (26 Oct evening) the strips, once the ring runs (the pref "strips"), and back after the update page
    if (!flipOk) return;
    if (flipComposing) {                               // (the first test held the loop 59 ms for it: taps were missed) a few rows a pass
        const uint32_t t0 = micros();
        const int rows = min(32, flipComp.h - flipCompRow);
        const PresentArea a = presentArea(flipComp.x, flipComp.y + flipCompRow, flipComp.w, rows);
        uint16_t *back = flipFb[flipSpare];
        if (a.w > 0) copyRows(back, a.x, a.y, a.w, a.h, a.over);
        flipCompRow += rows; flipComposeUs += micros() - t0;
        if (flipCompRow >= flipComp.h) {
            flipComposing = false; flipBig = flipComp;
            if (pageT0) pageComposeMs = millis() - pageT0;
            flipComposeMax = max(flipComposeMax, flipComposeUs);
            flipAskedMs = millis(); flipPending = true; flipRotating = false; flipFrom = flipShown; flipWant = flipSpare;
        }
        return;
    }
    if (flipPending) {
        if (flipShown == flipWant) {
            if (flipRotating && topDrawDepth) return;          // (fbNow is the layer's just now: the rotation completes at the next call)
            flipPending = false; screenFb = flipFb[flipShown];
            if (pageT0) { pageShownMs = millis() - pageT0; pageT0 = 0; }
            flipWaitMax = max(flipWaitMax, (uint32_t) (millis() - flipAskedMs));
            if (flipRotating) slideStaleWait = 0; else slideFlipDone();   // (1.11.143) a drag step's flip: the canvas now lags in the box's bands
            if (flipRotating) {                                // the canvas is on show: the buffer that was becomes the canvas, every band to catch up
                flipRotating = false; flipRotateN++;
                if (shownIsFlight) {                           // (the flight spare: the flight composite is kept as the spare; the old spare becomes the canvas)
                    flipCanvas = flipSpare; flipSpare = flipFrom;
                    spareHoldsFlight = true; if (topCanvas) { topCanvas->touchedClear(); topCanvas->track = true; }
                    flipStale = { 0, 0, 0, 0 };
                } else {
                    flipCanvas = flipFrom;
                    flipStale = { 0, 0, (int16_t) W, (int16_t) H }; flipStaleRow = 0;   // (and the spare lags by the whole page)
                }
                shownIsFlight = false;
                pageFb = fbNow = flipFb[flipCanvas]; canvas->aim(pageFb);
                canvasStale = (1ull << ((H + 7) / 8)) - 1;
                if (!picsLater.empty()) drawPicsLater();       // (1.11.120) the page is on show: now its pictures off the card
            } else {
                flipSpare = flipFrom; flipStale = flipKept ? Rect16{ 0, 0, (int16_t) W, (int16_t) H } : flipBig; flipStaleRow = 0; flipKept = false;
                shownIsFlight = topOn && topWho == FLIGHT_LAYER_WHO && topX == 0 && topY == 0 && topW == W && topH == H;
                // (1.11.136) the layer may not exist yet: a flip that completed before any page of our own had drawn wrote through
                // the null here (StoreProhibited at 0x3d = PacedCanvas::track) - the new transmitter's two early crashes of 26 Oct,
                // which struck the code-in-PSRAM and the strips off and left it flickering on the old path (found 27 Oct).
                spareHoldsFlight = false; if (topCanvas) topCanvas->track = false;
            }
        } else if (millis() - flipAskedMs > 250) {   // the frame ends stopped: no more flips; the shown buffer gets the change
            flipOk = false; flipWhy = "flip never came"; flipWant = flipShown; flipPending = false; flipRotating = false; screenFb = flipFb[flipShown];
            canvasEnsureRows(0, H); dirty(0, 0, W, H);
            if (!picsLater.empty()) drawPicsLater();           // (1.11.120: the pictures a rotation would have drawn after itself)
        }
        return;
    }
    // (1.11.116) The catching up after a flip is unseen work: one band or slice at most every 2 ms, so that it never adds a
    // burst to the Teensy's own drawing right after a page change (flipTick runs after every command of its).
    static uint32_t lastCatchUpUs = 0;
    const uint32_t nowUs = micros();
    if (nowUs - lastCatchUpUs < 2000) return;
    if (benchSkip & 2) return;                             // (bench: no catch-up copies)
    if (canvasStale) {                                     // the canvas first: it is on the drawing's path
        for (int b = 0; b < 64; ++b) if (canvasStale & (1ull << b)) { canvasEnsureRows(b << 3, 8); break; }
        lastCatchUpUs = micros();
        return;
    }
    if (flipSyncOn && flipStale.w > 0 && flipStaleRow < flipStale.h && !spareHoldsFlight) {   // a few rows a pass: the spare catches up with the one on show, unseen (off since 26 Oct: see flipSyncOn)
        lastCatchUpUs = nowUs;
        const int rows = min(8, flipStale.h - flipStaleRow), y = flipStale.y + flipStaleRow, x = flipStale.x, w = flipStale.w;   // (1.11.119: eight rows a slice, was sixteen - 51 kB through the bus in one go)
        uint16_t *spare = flipFb[flipSpare]; const uint16_t *from = flipFb[flipShown];
        if (spare && from && spare != from) {
            const int x0 = x & ~31, x1 = min((int) W, (x + w + 31) & ~31);   // (1.11.126) by DMA, whole lines; neither buffer is the CPU's
            if (!dmaCopyRows(spare, from, x0, x1, y, rows)) {
                if (dcTx) { Cache_Invalidate_Addr((uint32_t) (from + y * W), (uint32_t) rows * W * 2); Cache_Invalidate_Addr((uint32_t) (spare + y * W), (uint32_t) rows * W * 2); }   // (lines a DMA wrote: stale in the cache)
                for (int r = y; r < y + rows; ++r) { memcpy(spare + r * W + x, from + r * W + x, w * 2); psramPace(2u * w); }   // (a row at a time, counted double: a rest every four full rows)
                wbPaced((uint32_t) (spare + y * W + x), (uint32_t) (((rows - 1) * W + w) * 2));
            }
        }
        flipStaleRow += rows;
        if (flipStaleRow >= flipStale.h) { flipStale = { 0, 0, 0, 0 }; flipSyncN++; }
    }
}
static bool flipBigChange(const Rect16 &r) {          // true: taken (composed and asked for), or waiting for the last flip
    if (!flipOk || (long) r.w * r.h < 100000) return false;
    if (flipPending || flipComposing) return true;
    Rect16 all = rectJoin(r, flipStale);               // what the hidden buffer lacks: this change, and any catching up not done
    if (spareHoldsFlight) {                            // (the flight spare) the flight screen back on show, whole: the spare has it but for what the layer drew since
        const bool flightNow = topOn && topWho == FLIGHT_LAYER_WHO && topX == 0 && topY == 0 && topW == W && topH == H;
        if (flightNow && (long) r.w * r.h >= (long) W * H * 9 / 10) {
            flipKept = true;
            if (!topCanvas || !topCanvas->touchedAny()) {   // nothing: the flip alone
                flipBig = { 0, 0, 0, 0 }; flipAskedMs = millis(); flipPending = true; flipRotating = false; flipFrom = flipShown; flipWant = flipSpare;
                return true;
            }
            const int x0 = max(0, topCanvas->tx0), y0 = max(0, topCanvas->ty0), x1 = min(W, topCanvas->tx1), y1 = min(H, topCanvas->ty1);
            all = { (int16_t) x0, (int16_t) y0, (int16_t) max(0, x1 - x0), (int16_t) max(0, y1 - y0) };
        } else { spareHoldsFlight = false; if (topCanvas) topCanvas->track = false; all = { 0, 0, (int16_t) W, (int16_t) H }; }   // (another use of the spare: composed whole)
    }
    const PresentArea a = presentArea(all.x, all.y, all.w, all.h);
    if (a.w <= 0) return false;
    flipStale = { 0, 0, 0, 0 }; flipComp = { (int16_t) a.x, (int16_t) a.y, (int16_t) a.w, (int16_t) a.h };
    flipCompRow = 0; flipComposeUs = 0; flipComposing = true;   // composed by flipTick, a few rows a pass; other changes wait for the flip (presentDirty)
    flipTick();
    return true;
}
// The whole new page (drawPage): composed unseen and flipped to, like any big change. A compose under way starts again
// (the page under it is new); one already waiting for its frame is followed by this one. false: no flip to be had.
static bool flipWholePage() {
    if (!flipOk) return false;
    dirtyN = 0;
    if (flipComposing) { flipComp = { 0, 0, (int16_t) W, (int16_t) H }; flipCompRow = 0; return true; }
    if (flipPending) { dirty(0, 0, W, H); return true; }
    return flipBigChange({ 0, 0, (int16_t) W, (int16_t) H });
}
static bool presentNoFlip = false, filmNoFlipWanted = false;   // (26 Oct evening, bench) a film's frames straight to the shown buffer instead of a compose and flip: /stall?kind=filmflip&kb=0 for the next film. MEASURED on the new twin: no better (7, 6 slips per 30 s against 8, 4), so the flip stays
static void presentDirty(bool force = false) {
    Busy busy_(BUSY_PRESENT);
    flipTick();
    // (1.11.116) While a new picture is composed or waits for its frame, NOTHING goes to the glass: a small change shown now
    // would land on the old page (the new page's values seen on the old one), so it waits and follows the flip.
    if (flipComposing || flipPending) return;
    if (!dirtyN) return;
    const uint32_t now = millis();
    bool quiet = false;
    if (quietSwitch) {                                 // (src/flight_device.h: the defined front screen shown or put away)
        for (int i = 0; i < dirtyN; ++i) if ((long) dirtyList[i].w * dirtyList[i].h >= (long) W * H * 9 / 10) quiet = true;
        if (quiet && !quietTurn(quietCopy)) return;    // (all of it waits: nothing of the new screen is seen before the rest)
        quietSwitch = false; if (quiet) force = true;
    }
    if (!force) {
        if (!beamHeld && now - lastPresentMs < 25) return;                     // 40 frames a second at most
        if (Serial.available() > 0 && now - firstDirtyMs < 80) return;        // a burst is still arriving: show it whole
    }
    // (1.11.82) Not while the panel's scan would catch a copy part-way: a frame with the rows above the beam new and the rows
    // below old (the curve page's marker "breaks into two with one part ahead of the other" - Malcolm, 17 Oct 2026). Each
    // rectangle goes when the beam has passed it, or will not reach it before its copy is done (beamClear, quiet_time.h):
    // a frame's wait at most, and after 60 ms it goes anyway. A finger's feedback (force) goes at once, as before.
    const uint32_t t0 = micros();
    int kept = 0; uint32_t px = 0;
    for (int i = 0; i < dirtyN; ++i) {
        const Rect16 r = dirtyList[i];
        const uint32_t copyUs = (uint32_t) ((uint64_t) r.w * r.h * copyUsPerKpx / 1000) + 30;
        if (flipComposing || flipPending) { dirtyList[kept++] = r; continue; }   // (1.11.116) begun in this pass: the rest follow the flip
        if (flipOk && !presentNoFlip && (long) r.w * r.h >= 100000 && flipBigChange(r)) continue;   // (1.11.115) the twin: composed unseen, then flipped to (not a film's frames: presentNoFlip)
        if (!force && now - firstDirtyMs < 60 && !beamClear(r.y, r.h, micros(), copyUs)) { dirtyList[kept++] = r; continue; }
        present(r.x, r.y, r.w, r.h); px += (uint32_t) r.w * r.h;
    }
    beamHeld = kept > 0; dirtyN = kept;
    if (px) {
        const uint32_t us = micros() - t0;
        if (px >= 4000) copyUsPerKpx = constrain((copyUsPerKpx * 7 + (uint32_t) ((uint64_t) us * 1000 / px)) / 8, 20u, 2000u);
        lastPresentMs = millis(); perfPresentUs += us; perfPresentPx += px; perfPresentN++;
    }
    if (quiet) quietDone(quietCopy, micros() - t0, false);
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
static File assetOpen(const char *path);                 // (1.11.138, flash_pack.h) the pack's copy on the 16 MB boards, else the card's
static bool assetsOk();                                  // pages, fonts and sounds can be had: the card, or the pack
static File sdOpenChecked(const char *path);             // the card's file; a card that has gone is given up, not asked again (1.2 s a time)
static void loadAaFonts() {
    for (int f = 0; f < 7; ++f) {
        if (aaBits[f]) { free(aaBits[f]); aaBits[f] = nullptr; }         // (1.11.138) read again after a pack was built: the old tables go first
        if (aaOffset[f]) { free(aaOffset[f]); aaOffset[f] = nullptr; }
        const NextionFont *nf = nextion_fonts[f];
        char path[32]; snprintf(path, sizeof(path), "/hmi/font%d_aa.bin", f);
        File file = assetOpen(path); if (!file) continue;
        const size_t n = file.size();
        uint8_t *buf = (uint8_t *) ps_malloc(n); if (!buf) { file.close(); continue; }
        const bool ok = file.read(buf, n) == n; file.close();
        uint32_t *off = (uint32_t *) ps_malloc(nf->count * 4); uint32_t run = 0;
        for (int g = 0; g < nf->count; ++g) { off[g] = run; run += ((nf->glyphs[g].bitmap_width + 1) / 2) * nf->height; }
        if (!ok || run != n) { free(buf); free(off); continue; }           // not the table we expect
        aaBits[f] = buf; aaOffset[f] = off;
    }
}
static int glyphBg = -1;                                   // (1.11.116) the colour under the letters being drawn, when it is one colour (a box with its own), else -1
static inline uint16_t blend565(uint16_t bg, uint16_t fg, int a) {   // a = 1..6 of 7
    const int br = (bg >> 11) & 31, bg6 = (bg >> 5) & 63, bb = bg & 31, fr = (fg >> 11) & 31, fg6 = (fg >> 5) & 63, fb = fg & 31;
    return (uint16_t) ((((br * (7 - a) + fr * a) / 7) << 11) | (((bg6 * (7 - a) + fg6 * a) / 7) << 5) | ((bb * (7 - a) + fb * a) / 7));
}
static void drawGlyphs(int x, int y, int fontId, uint16_t col, const std::string &s) {
    // (15 Oct 2026, 1.11.65: only font NEXTION_FONT_BITS_KEEP, 6, keeps its 1-bpp table in flash - nextion_fonts.h; ~120 kB
    // of the screen's flash back. A font whose smooth table did not come off the card draws in that one: legible, if not
    // its own size. Without the card there are no pages at all, so this is the boot line and the screen's own pages.)
    if (!aaBits[fontIdx(fontId)] && !fontFor(fontId)->bits) fontId = NEXTION_FONT_BITS_KEEP;
    const NextionFont *f = fontFor(fontId);
    const int h = f->height, fi = fontIdx(fontId);
    if (y >= clipY1 || y + h <= clipY0) return;
    if (aaBits[fi]) {
        uint16_t *fb = fbNow;
        if (fb == pageFb) canvasEnsureRows(y, h);              // (1.11.116: the rotation)
        else if (fb == topFb && topCanvas) topCanvas->touch(max(x - 8, 0), y, textWidth(fontId, s) + 16, h);   // (the flight spare: what the layer had drawn on it)
        const bool solid = glyphBg >= 0; uint16_t lut[8];
        if (solid) { lut[0] = (uint16_t) glyphBg; for (int a = 1; a < 8; ++a) lut[a] = a >= 7 ? col : blend565((uint16_t) glyphBg, col, a); }
        for (unsigned char c : s) {
            if (c < f->first || c > f->last) continue;
            const NextionGlyph &g = f->glyphs[c - f->first];
            const int bw = g.bitmap_width, rowBytes = (bw + 1) / 2, gx = x - g.kern_left;
            const uint8_t *src = aaBits[fi] + aaOffset[fi][c - f->first];
            // (1.11.116) Straight into the buffer: gfx->writePixel for every pixel of every letter (a virtual call, clipping,
            // the canvas's own checks) was most of the 3 ms a label took - 24 labels, 84 ms of a page change on the twin.
            // The rows are caught up above and the clip is kept here; the clip never leaves the screen.
            const int c0 = max(clipX0, 0), c1 = min(clipX1, W), r0 = max(clipY0, 0), r1 = min(clipY1, H);
            for (int row = 0; row < h; ++row) {
                const int py = y + row; if (py < r0 || py >= r1) continue;
                const uint8_t *r = src + row * rowBytes;
                uint16_t *dst = fb + py * W;
                if (solid) {                                   // (1.11.116) one colour under the letters: the eight shades are known before the first pixel
                    for (int col2 = 0; col2 < bw; ++col2) {
                        const int a = (col2 & 1) ? (r[col2 >> 1] & 15) : (r[col2 >> 1] >> 4);
                        if (!a) continue;
                        const int px = gx + col2; if (px < c0 || px >= c1) continue;
                        dst[px] = lut[a];
                    }
                    continue;
                }
                for (int col2 = 0; col2 < bw; ++col2) {
                    const int a = (col2 & 1) ? (r[col2 >> 1] & 15) : (r[col2 >> 1] >> 4);
                    if (!a) continue;
                    const int px = gx + col2; if (px < c0 || px >= c1) continue;
                    dst[px] = a >= 7 ? col : blend565(dst[px], col, a);
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
        if (fb == pageFb) canvasEnsureRows(y, g->h);           // (1.11.116: the rotation)
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
        { "external picture", 60 }, { "combobox", 61 }, { "sltext", 62 }, { "switch", 67 }, { "rangebar", 69 }, { "textselect", 68 }, { "scrolling text", 55 }, { "xfloat", 59 } };
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
// (1.11.137) The store's nodes live in the PSRAM. Every value the main board writes to a page is remembered here for the
// page's return, and a tour of the pages on the new transmitter grew it from 44 entries to 216 and the chip's own RAM from
// 75 kB free to 18 kB (27 Oct 2026: the web server stopped, the strips fell late). The keys and the code stay as they
// were: only the allocator changes, so the map's nodes - the bulk of it - come out of the 8 MB instead.
template <class T> struct PsAlloc {
    using value_type = T;
    PsAlloc() noexcept {}
    template <class U> PsAlloc(const PsAlloc<U> &) noexcept {}
    T *allocate(size_t n) { void *p = heap_caps_malloc(n * sizeof(T), MALLOC_CAP_SPIRAM); if (!p) p = malloc(n * sizeof(T)); if (!p) abort(); return (T *) p; }
    void deallocate(T *p, size_t) noexcept { free(p); }
    template <class U> bool operator==(const PsAlloc<U> &) const noexcept { return true; }
    template <class U> bool operator!=(const PsAlloc<U> &) const noexcept { return false; }
};
template <class K, class V> using PsMap = std::map<K, V, std::less<K>, PsAlloc<std::pair<const K, V>>>;
struct Kept { PsMap<std::string, int32_t> ints; PsMap<std::string, std::string> txts; };
static PsMap<std::string, Kept> kept;                      // key "Page.Comp"
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
static size_t bgCacheMax = 4;                              // (1.11.131) fewer when the firmware's code took its share of the PSRAM (setup)
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
#define OUR_GOOD(bg) (ldrc::themeIsLight(bg) ? 0x01E0 : 0x87F0)   // green words that read on bg: pale on a dark theme, dark on a light one (White, Yellow, Sky)
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
static int cliJobWanted = -1;                          // (1.11.41) "ldrc cli" 0 / "ldrc diff" 1 / "ldrc exec" 2: the command line page (src/cli_device.h) at the next pass of loop()
static bool cliPageUp = false;                         // (1.11.51) the command line page is showing: the pipe is its own (src/ble_device.h bleHttpCommand)
static bool cliUp();                                   // the command line page has the screen
static bool filmUp();                                  // (1.11.85, src/film_device.h) a film has the screen
static bool filmMenuUp();                              // (1.11.87) the films menu has the screen
static void filmMenuTouch(bool pressed, int x, int y, uint32_t now);
static void filmTouch(bool pressed, int x, int y, uint32_t now);
static void filmTouchCancel();
static bool filmButtonTouch(bool pressed, int x, int y, uint32_t now);   // the help page's Film button
static void filmNoteHelp(const std::string &script);
static void filmButtonCancel();
static uint32_t filmDecodeUs = 0, filmDecodeMax = 0, filmPictures = 0, filmSkipped = 0;   // (src/film_device.h: how the last film went, for /status)
static uint32_t filmFadeSteps = 0, filmFadeMax = 0;     // (1.11.93) the fades' steps made by the screen, and the longest (us)
static void cliTouch(bool pressed, int x, int y, uint32_t now);
static void cliPoll(); static void cliWeb();
// (B59) a corner held while one of our pages has the screen: that page forgets the finger (src/*_device.h)
static void wifiTouchCancel(); static void cliTouchCancel(); static void picTouchCancel(); static void flightTouchCancel();
static void coloursTouchCancel(); static void appearanceTouchCancel(); static void updTouchCancel();
static void wifiWeb();
static void updWeb();
// The model pictures (src/pics_device.h, lib/LdrcPics): the chooser over the Teensy's "Choose image" page, photos from a phone
static bool picWifi = false;                           // the chooser is waiting for a photo: it needs the WiFi, whatever the user's switch says
static bool picPanelUp();
static void picTouch(bool pressed, int x, int y, uint32_t now);
static void picPoll();
static void picWeb();
static void bleWeb(); static void blePoll(); static void blePipeCommand(const std::string &a); static void bleTxCommand(const std::string &words); static void bleHttpCommand(const std::string &a); static std::string bleStatusJson(); static unsigned bleStackSpare();
static bool bleIsOff();                                    // (1.11.20) the Bluetooth stack is down: the WiFi may stay awake
static void bleOffForTheUpdate();                          // (1.11.20) an update begins: the pipe is let go
// THE CRASH of 7 Oct, "clicking receiver update makes the screen reboot": task wifi, abort() in pm_set_sleep_type: the WiFi
// driver refuses to be kept awake (power save off) while Bluetooth is up - the one radio is shared, and modem sleep is
// what lets them share. So the WiFi is kept awake only when the Bluetooth stack is down; an update that wants it awake
// first lets the pipe go.
static void wifiApplySleep() { if (radiosLive) WiFi.setSleep(!(updWifi && bleIsOff())); }
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
static int16_t toneShape(int16_t x);                   // (1.11.116, below audioTask: the twin's tone)
static int audioId = -1;                               // the clip playing, for /status
static uint32_t bootMs = 0;                            // when loop() first ran (ms after power), for /status
static std::string bootLog;                            // the first ~4 kB of traffic after power, timestamped: GET /bootlog
static void blog(const char *tag, const std::string &what) { if (bootLog.size() > 4000) return; char b[24]; snprintf(b, sizeof(b), "%lu %s ", (unsigned long) millis(), tag); bootLog += b; bootLog += what.substr(0, 60); bootLog += "\n"; }
static std::string oddTrace;                           // commands the parser did not understand, for GET /status
static std::string radioLog;                           // when the radio went on and off, and why: GET /radiolog (the last twenty lines)
static std::string recent[64]; static int recentN = 0;   // the last commands from the Teensy, for GET /recent
// The system's own error lines (ESP-IDF's log: "E (12345) esp_image: Image hash failed - image is corrupt") went out on
// UART0 - the wire to the main board - until 1.11.5. They are kept here instead: the last eight at the end of GET /recent,
// the last one in /status ("sys"), and the ones logged while the flash checks a new firmware go into the update's
// failure message (update_device.h). Called from any task: a fixed ring, a short critical section, no heap.
static const int SYS_LINES = 8; static char sysLines[SYS_LINES][112]; static volatile uint32_t sysN = 0;
static portMUX_TYPE sysMux = portMUX_INITIALIZER_UNLOCKED;
static int sysLogHook(const char *fmt, va_list ap) {
    char b[160]; const int n = vsnprintf(b, sizeof(b), fmt, ap);
    if (n <= 0) return 0;
    int len = n < (int) sizeof(b) ? n : (int) sizeof(b) - 1;
    char c[160]; int k = 0;                                   // without colour codes (ESC [ ... m) and the line end
    for (int i = 0; i < len; ++i) { if (b[i] == 27) { while (i < len && b[i] != 'm') ++i; continue; } if (b[i] == '\n' || b[i] == '\r') continue; c[k++] = b[i]; }
    if (k == 0) return n;
    if (k > (int) sizeof(sysLines[0]) - 1) k = (int) sizeof(sysLines[0]) - 1;
    portENTER_CRITICAL(&sysMux);
    char *line = sysLines[sysN % SYS_LINES]; memcpy(line, c, k); line[k] = 0; sysN = sysN + 1;
    portEXIT_CRITICAL(&sysMux);
    return n;
}
static std::string sysLine(uint32_t i) { char b[112]; portENTER_CRITICAL(&sysMux); strlcpy(b, sysLines[i % SYS_LINES], sizeof(b)); portEXIT_CRITICAL(&sysMux); return b; }
static std::string sysText() { std::string out; const uint32_t n = sysN; for (uint32_t i = n > SYS_LINES ? n - SYS_LINES : 0; i < n; ++i) { out += sysLine(i); out += "\n"; } return out; }
static std::string sysLast() { const uint32_t n = sysN; return n ? sysLine(n - 1) : std::string(); }
// 1.11.15 (Malcolm, 7 Oct: "the tx screen went blank for a moment, and I think it rebooted" - rst said 4, a panic): the
// core dump the chip keeps in its flash after a crash, summarised: the task, the cause, the program counter and the
// backtrace, to be read against the firmware's ELF (dev/out/elf/screen-<version>.elf, kept by the release tool).
static std::string crashJson() {
    esp_core_dump_summary_t *sm = (esp_core_dump_summary_t *) malloc(sizeof(esp_core_dump_summary_t));
    if (!sm) return "null";
    std::string out = "null";
    if (esp_core_dump_image_check() == ESP_OK && esp_core_dump_get_summary(sm) == ESP_OK) {
        char b[160]; snprintf(b, sizeof b, "{\"task\":\"%.15s\",\"pc\":\"0x%08lx\",\"cause\":%lu,\"vaddr\":\"0x%08lx\",\"depth\":%lu,\"corrupt\":%s,\"bt\":[", sm->exc_task, (unsigned long) sm->exc_pc, (unsigned long) sm->ex_info.exc_cause, (unsigned long) sm->ex_info.exc_vaddr, (unsigned long) sm->exc_bt_info.depth, sm->exc_bt_info.corrupted ? "true" : "false");
        out = b;
        for (uint32_t i = 0; i < sm->exc_bt_info.depth && i < 16; ++i) { snprintf(b, sizeof b, "%s\"0x%08lx\"", i ? "," : "", (unsigned long) sm->exc_bt_info.bt[i]); out += b; }
        out += "]}";
    }
    free(sm);
    return out;
}
// The lines logged since `mark` (a value of sysN), their "E (12345) " prefixes dropped, joined with "; ": the reason the
// system's own code gives when something of ours fails.
static std::string sysSince(uint32_t mark) {
    std::string out; const uint32_t n = sysN;
    for (uint32_t i = (n > mark + SYS_LINES ? n - SYS_LINES : mark); i < n; ++i) {
        std::string l = sysLine(i);
        if (l.size() > 3 && l[1] == ' ' && l[2] == '(') { const size_t e = l.find(") "); if (e != std::string::npos) l = l.substr(e + 2); }
        if (l.empty()) continue;
        if (!out.empty()) out += "; ";
        out += l;
    }
    return out;
}
static Preferences prefs;
#include "flash_pack.h"                                 // (1.11.138, 27 Oct 2026: on the 16 MB boards the pages, fonts and sounds live in the spare 3.4 MB flash partition, memory-mapped, copied from the card at start-up when missing or stale: faster than the card, and there without one)
#include "code_in_psram.h"                             // (1.11.131, 26 Oct 2026: the firmware's own code and constants copied into the PSRAM at start, off the flash the panel's bus shares; pref "xip", /status "xip")
// Flash writes stall the chip for milliseconds and the UART's 128-byte FIFO overflows at 921600 baud in
// 1.1 ms: a preference saved during a page load mangled whatever the Teensy sent right then (its file
// lists, its findfile question at boot). Saves wait until the link has been quiet for half a second.
static uint32_t lastRxMs = 0;
static bool wireQuiet(uint32_t ms) { return (int32_t) (millis() - lastRxMs) > (int32_t) ms; }   // (1.11.140) nothing from the main board for ms
static int pendingBg = INT32_MIN, pendingVol = INT32_MIN, pendingRadios = INT32_MIN;
static uint32_t pendingBgAt = 0, pendingVolAt = 0;         // (25 Oct) when the value last changed: written once it has rested
// (25 Oct 2026) Every write to the flash (NVS) stalls the panel's DMA for its length - the picture slips sideways (1.11.69).
// So each is started just after a frame's end, in the blank before the next picture (quiet_time.h), and counted.
static uint32_t nvsN = 0, nvsMaxUs = 0;
template <typename F> static void nvsQuiet(F write) { quietAtFrameEnd(); const uint32_t t0 = micros(); { Busy busy_(BUSY_NVS); write(); } const uint32_t us = micros() - t0; nvsN++; if (us > nvsMaxUs) nvsMaxUs = us; }
static std::string pendingDoor; static bool pendingDoorSet = false;
static uint32_t pendingSince = 0;                          // the pilot's own switches (the radios, the workshop door): written when the wire is quiet, or after 30 s, quiet or not (1.11.140: was 3 s)
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
    // (1.11.140) A flash write masks the wire's interrupt for its whole length (the core's UART handler is not in IRAM), and the
    // 128-byte FIFO then overflows in 1.4 ms at 921600 baud whatever its threshold: the main board's bytes of that moment
    // are lost and two of its commands run into one (a stray line across the Rates curves page, Malcolm, 28 Oct 2026 -
    // its dots follow the sticks, so the wire is busy as long as they move, and after 3 s this write went regardless).
    // Now a quiet wire, or 30 s: on a page that streams without pause the loss is then a telemetry word, not a drawing.
    if ((pendingRadios != INT32_MIN || pendingDoorSet) && (wireQuiet(300) || millis() - pendingSince > 30000)) {
        if (pendingRadios != INT32_MIN) { if (prefs.getBool("radios", true) != (pendingRadios == 1)) nvsQuiet([&] { prefs.putBool("radios", pendingRadios == 1); }); pendingRadios = INT32_MIN; }
        if (pendingDoorSet) { pendingDoorSet = false; nvsQuiet([&] { if (pendingDoor.empty()) { if (prefs.isKey("door")) prefs.remove("door"); } else prefs.putString("door", pendingDoor.c_str()); }); }
    }
    if ((int32_t) (millis() - lastRxMs) < 500) return;
    // (25 Oct 2026) The background page's buttons set Screen_Background at EVERY tap (43 pictures to browse), and each tap
    // wrote the flash at once: "the screen flickers every time a new image is displayed" (Malcolm). Written once the choice
    // has rested 2.5 s with the page settled - and then in a frame's blank (nvsQuiet). The volume the same (its slider).
    const uint32_t now = millis();
    if (pendingBg != INT32_MIN && now - pendingBgAt > 2500 && now - lastPresentMs > 1500) { if (prefs.getInt("bg", -1) != pendingBg) nvsQuiet([&] { prefs.putInt("bg", pendingBg); }); pendingBg = INT32_MIN; }
    if (pendingVol != INT32_MIN && now - pendingVolAt > 2500 && now - lastPresentMs > 1500) { if (prefs.getInt("vol", -1) != pendingVol) nvsQuiet([&] { prefs.putInt("vol", pendingVol); }); pendingVol = INT32_MIN; }
}

static void openKeyboard(int key, int compId);   // (below: the keyboard pages)
static Comp *find(const std::string &nm) { auto it = page.byName.find(nm); return it == page.byName.end() ? nullptr : &page.comps[it->second]; }

// ------------------------------------------------------------------ background + drawing
// (1.11.131) The resident pictures are the PSRAM's elastic part: when something else needs room - our own pages' layer
// (topReady), a film's buffers - a background that is not on show is given up, the least recently used first.
static bool bgEvictOne() {
    int old = -1;
    for (size_t i = 0; i < bgCache.size(); ++i) if (bgCache[i].buf != bgBuf && (old < 0 || bgCache[i].used < bgCache[old].used)) old = (int) i;
    if (old < 0) return false;
    free(bgCache[old].buf); bgCache.erase(bgCache.begin() + old); return true;
}
static bool clipDropOne();                                 // (1.11.133) the sound clip cache, below: its least used clip let go
static void *psMallocRoom(size_t n) { for (;;) { void *p = ps_malloc(n); if (p) return p; if (!clipDropOne() && !bgEvictOne()) return nullptr; } }   // ps_malloc that makes room: sound clips first (40 kB each, back from the card in a moment), then backgrounds not on show
static const uint32_t PSRAM_FLOOR = 512u * 1024u; static uint32_t psramEvictions = 0;   // (1.11.132) loop() keeps this much PSRAM free (/status "xip" evictions)
static bool loadBackground(int picId) {                  // (1.11.138: its open is sdOpenChecked, below)
    Busy busy_(BUSY_BG);
    if (picId < 0 || !sdOk) return false;
    for (auto &e : bgCache) if (e.id == picId) { e.used = millis(); bgBuf = e.buf; bgW = W; bgH = H; return true; }
    char path[32]; snprintf(path, sizeof(path), "/hmi/pic/%d.565", picId);
    File f = sdOpenChecked(path);
    if (!f) return false;
    uint16_t wh[2]; f.read((uint8_t *) wh, 4);
    uint16_t *buf;
    buf = bgCache.size() < bgCacheMax ? (uint16_t *) ps_malloc(W * H * 2) : nullptr;   // 4 backgrounds resident (3 MB): the clip cache needs its share of PSRAM (1.11.131: fewer with the code in the PSRAM - setup)
    if (!buf && bgCache.empty()) { f.close(); return false; }
    if (!buf) { size_t old = 0; for (size_t i = 1; i < bgCache.size(); ++i) if (bgCache[i].used < bgCache[old].used) old = i; buf = bgCache[old].buf; bgCache.erase(bgCache.begin() + old); }
    if (wh[0] == W && wh[1] == H) sdReadPaced(f, (uint8_t *) buf, W * H * 2);   // (1.11.120: in slabs, paced - 768 kB in one read slipped the twin's picture)
    else { for (int y = 0; y < H; ++y) { memset(buf + y * W, 0, W * 2); psramPace(W); } for (int y = 0; y < wh[1] && y < H; ++y) sdReadPaced(f, (uint8_t *) (buf + y * W), min((int) wh[0], W) * 2); }
    f.close();
    if (dcTx) wbPaced((uint32_t) buf, W * H * 2);           // (1.11.127) the picture is in the memory itself from here on: the DMA paints the page's background from it (restoreRect)
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
        if (fb == pageFb) canvasEnsureRows(y, h);              // (1.11.116: the rotation)
        else if (fb == topFb && topCanvas) topCanvas->touch(x, y, w, h);   // (the flight spare)
        // (1.11.127) The whole lines inside the rectangle go by DMA from the picture (in the memory since it was loaded), the
        // cache's lines of them dropped first (src/dma_copy.h); the margins up to 31 pixels at each end by hand, as before.
        const int xi0 = (x + 31) & ~31, xi1 = (x + w) & ~31;
        if (fb != screenFb && dmaReady() && xi1 - xi0 >= 64 && h >= 4 && !((uintptr_t) fb & 63)) {
            dmaDropLines(fb, xi0, xi1, y, h);
            if (dmaCopyRows(fb, bgBuf, xi0, xi1, y, h)) {
                for (int yy = 0; yy < h; ++yy) { if (xi0 > x) memcpy(fb + (y + yy) * W + x, bgBuf + (y + yy) * W + x, (xi0 - x) * 2); if (x + w > xi1) memcpy(fb + (y + yy) * W + xi1, bgBuf + (y + yy) * W + xi1, (x + w - xi1) * 2); }
                return;
            }
        }
        for (int yy = 0; yy < h; ++yy) { memcpy(fb + (y + yy) * W + x, bgBuf + (y + yy) * W + x, w * 2); psramPace(w); }   // (1.11.116: paced)
        if (fb == screenFb) wbPaced((uint32_t) (fb + y * W + x), (uint32_t) (((h - 1) * W + w) * 2));   // no canvas: the panel's DMA reads PSRAM directly
    } else gfx->fillRect(x, y, w, h, page.bgColor);
}
// What lies under a component that does not fill its own rectangle (a switch's rounded ends, a radio's disc, a slider's
// track, a see-through text, a model picture's frame): the solid component it sits on, if one was drawn before it and
// covers it (the System pages' navy card: Malcolm saw the red of his background picture in the switches' corners,
// 10-03; screen 1.5.6: the same red showed behind the sliders and the empty picture frame), else the page's own picture.
static const Comp *cardUnder(const Comp &c) {
    const long me = (long) (&c - page.comps.data());
    if (me > 0 && me < (long) page.comps.size())
        for (long i = me - 1; i >= 0; --i) {
            const Comp &o = page.comps[i];
            if (!o.vis || o.sta != 1 || (o.type != "text" && o.type != "number")) continue;
            if (o.x <= c.x && o.y <= c.y && o.x + o.w >= c.x + c.w && o.y + o.h >= c.y + c.h) return &o;
        }
    return nullptr;
}
static void restoreUnder(const Comp &c) {
    if (const Comp *o = cardUnder(c)) { gfx->fillRect(c.x, c.y, c.w, c.h, o->bco); return; }
    restoreRect(c.x, c.y, c.w, c.h);
}
// The light themes (10-10). The pages were made on navy, so what is drawn on a theme's panel in a fixed colour - a
// slider's white knob, a radio button's white disc, the arming line's green - can vanish on White, Yellow or Sky. These
// keep each such colour exactly as it is wherever it already reads (lib/LdrcTheme: 3:1), so the dark themes look just as
// they did, and give it another only where it does not.
static bool themeFaceUnder(const Comp &c, uint16_t &face) {   // the theme's panel (or strip) colour that c sits on, if it sits on one
    const Comp *o = cardUnder(c);
    if (!o || !ldrc::themeRole(o->roles, ldrc::TF_BCO)) return false;
    face = (uint16_t) o->bco; return true;
}
// The colour of a box's words: a colour of the main board's (or the page's) that is not one of the style's, on a box in
// the theme's panel or strip colour, made to read there - RFView's arming line ("Ready to arm" green, "Armed" light red)
// on White, Yellow, Sky or Red - keeping its colour (a darker green, not black). The style's own colours follow the theme
// already (themeComp); what the main board wrote stays as it wrote it (c.pco), only the drawing differs.
static uint16_t inkOf(const Comp &c, bool second = false) {
    const uint16_t ink = (uint16_t) (second ? c.pco2 : c.pco);
    if (!ldrc::themeRole(c.roles, second ? ldrc::TF_BCO2 : ldrc::TF_BCO) || ldrc::themeRole(c.roles, second ? ldrc::TF_PCO2 : ldrc::TF_PCO)) return ink;
    return ldrc::themeInkOn(ink, (uint16_t) (second ? c.bco2 : c.bco));
}
static uint16_t shade(uint16_t c, int pct) {              // pct > 0 towards white, < 0 towards black
    int r = (c >> 11) & 31, g = (c >> 5) & 63, b = c & 31;
    if (pct > 0) { r += (31 - r) * pct / 100; g += (63 - g) * pct / 100; b += (31 - b) * pct / 100; }
    else { r += r * pct / 100; g += g * pct / 100; b += b * pct / 100; }
    return (uint16_t) ((r << 11) | (g << 5) | b);
}
// The Nextion's frame styles: 0 flat (nothing — the help page's boxes), 1 border in borderc, 2 3D down
// (sunk), 3 3D up (raised), 4 3D auto (raised, sunk while pressed). Drawn from the box's own colour.
// 1.11.40 (Malcolm, 9 Oct: "Information and warning banners should look like message boxes rather than yellow text
// stripes"): text style 5 is a MESSAGE BOX, as the yes/no question (PopupView) has it - a dark ring, a white frame inside
// it, the panel's colour, the words wrapped and kept clear of the frame (MSGBOX_PAD). The pages' "busy" banners use it.
static const int MSGBOX_RING = 3, MSGBOX_FRAME = 2, MSGBOX_PAD = 16;
static void drawFrame(const Comp &c, uint16_t bg, bool down) {
    const int x = c.x, y = c.y, w = c.w, h = c.h;
    if (c.style == 1) { for (int i = 0; i < max(1, c.borderw); ++i) gfx->drawRect(x + i, y + i, w - 2 * i, h - 2 * i, c.borderc); return; }
    if (c.style == 5) {
        for (int i = 0; i < MSGBOX_RING; ++i) gfx->drawRect(x + i, y + i, w - 2 * i, h - 2 * i, 0x08A6);
        for (int i = MSGBOX_RING; i < MSGBOX_RING + MSGBOX_FRAME; ++i) gfx->drawRect(x + i, y + i, w - 2 * i, h - 2 * i, c.borderc);
        return;
    }
    if (c.style < 2) return;
    const bool sunk = c.style == 2 || (c.style == 4 && down);
    const uint16_t tl = sunk ? shade(bg, -45) : shade(bg, 60);
    uint16_t br = sunk ? shade(bg, 60) : shade(bg, -45), face;
    // (a white entry box on White, Yellow or Sky: the box and its light lower edge both vanish on the panel, so only its top
    // and left lines showed; that edge takes the theme's outline colour, as a radio button's ring does. Where either one
    // already reads - every dark theme - nothing changes.)
    if (sunk && themeFaceUnder(c, face) && !ldrc::themeStandsOut(bg, face) && !ldrc::themeStandsOut(br, face)) br = theme.edge();
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
static int frameWidth(const Comp &c) { return c.style == 1 ? max(1, c.borderw) : (c.style >= 2 && c.style <= 4) ? 2 : c.style == 5 ? MSGBOX_RING + MSGBOX_FRAME : 0; }
// (1.11.142) The lines of a text in its box and where they go, laid out as the Nextion does: one place for drawTextIn and
// for the slide text under a finger (slideDrag), so that the two can only ever draw the same pixels.
struct TextLayout { std::vector<std::string> lines; int fh = 0, bx = 0, ty = 0; };   // the lines; a line's height; the block's x; the first line's y, scrolled
static const int TEXT_PAD = 2;
static TextLayout textLayout(int x, int y, int w, int h, int font, const std::string &s, int xcen, int ycen, bool wrap, int offY, int cutInset) {
    TextLayout L;
    L.fh = fontHeight(font);
    L.lines = textLines(s, font, w, wrap);
    // The Nextion lays the lines out as ONE BLOCK: lines left-aligned inside it, the block centred (or
    // not) in the box, and a block too tall or too wide for the box starts from the top / the left — the
    // switches page's six-line note shows its first four lines, not its middle four.
    // Blank lines at the END of the text do not count (the trim-direction boxes hold one line and up to four
    // blank ones: the V1 centres that one line in each box).
    while (L.lines.size() > 1 && L.lines.back().find_first_not_of(" \t") == std::string::npos) L.lines.pop_back();
    if (cutInset >= 0 && L.lines.size() == 1) {
        std::string ink = inkOf(L.lines[0]); const int room = w - 2 * cutInset - (xcen == 1 ? 0 : TEXT_PAD);   // (the room the words have: all of it when centred, after the margin otherwise)
        if (textWidth(font, ink) > room) { while (!ink.empty() && textWidth(font, ink + "...") > room) ink.pop_back(); L.lines[0] = inkOf(ink) + "..."; }
    }
    const int th = (int) L.lines.size() * L.fh;
    // Centred words are centred by their ink: trailing spaces do not push them aside (the Teensy pads "Not used" with
    // nine spaces on the switches page, which put it 31 px left of the middle).
    int bw = 0; for (auto &line : L.lines) bw = max(bw, textWidth(font, xcen == 1 ? inkOf(line) : line));
    int bx = xcen == 1 ? x + (w - bw) / 2 : xcen == 2 ? x + w - bw - TEXT_PAD : x + TEXT_PAD;
    if (bx < x) bx = x;
    int ty = ycen == 1 ? y + (h - th) / 2 : ycen == 2 ? y + h - th - 1 : y + 1;
    if (ty < y) ty = y;
    L.bx = bx; L.ty = ty - offY;
    return L;
}
static int textLineX(const TextLayout &L, int x, int w, int font, int xcen, const std::string &line) {   // where a line starts: right-aligned lines each by their own width
    return xcen == 2 ? max(x, x + w - textWidth(font, line) - TEXT_PAD) : L.bx;
}
static void drawTextIn(int x, int y, int w, int h, int font, uint16_t col, const std::string &s, int xcen, int ycen, bool wrap = false, int offY = 0, int cutInset = -1) {
    if (s.empty()) return;
    const TextLayout L = textLayout(x, y, w, h, font, s, xcen, ycen, wrap, offY, cutInset);
    clipX0 = max(0, x); clipY0 = max(0, y); clipX1 = min(W, x + w); clipY1 = min(H, y + h);
    gfx->startWrite();
    int ty = L.ty;
    for (auto &line : L.lines) {
        if (ty + L.fh > y && ty < y + h && !line.empty()) drawGlyphs(textLineX(L, x, w, font, xcen, line), ty, font, col, line);
        ty += L.fh;
    }
    gfx->endWrite();
    clipX0 = 0; clipY0 = 0; clipX1 = W; clipY1 = H;
}
// (1.11.142-144) THE SLIDE TEXT THROUGH A SLAB. The help/log viewer's box (747 x 370) is lettered eight rows at a time in
// a slab of the chip's own RAM - the background, then the glyphs with drawGlyphs' eight-shade table - and each slab is
// written ONCE into the PSRAM: the canvas (slideFill: every ordinary redraw), or, under a finger on the twin, the spare
// panel buffer that is then flipped to (slideDrag, after redraw()). A stale canvas band (the rotation, canvasEnsureRows) is
// caught up here by its margins only: the box's own rows and columns are about to be written whole. hmi/test_slide proves
// both against drawTextIn, pixel for pixel. The words of a slide text are shown when their position follows (the main
// board sends LogText.txt, waits 50 ms, then LogText.val_y: drawn at once they appeared at the top first, then jumped).
// (1.11.145) The slab is ONE ROW, static (1.6 kB of .bss): 1.11.142-144 asked the heap for eight rows, 12.8 kB of internal
// RAM, and Malcolm's twin had 12 kB free in pieces of 3.4 kB (minheap 608 B): the ask failed as often as not - those steps
// went the old slow way - and when it succeeded the web server starved. A row at a time costs nothing more: the glyph work
// is the same pixels, and each row is written back as it lands (1.5 kB a time, not a 12.8 kB burst: 235 of the twin's 236
// panel slips were counted inside a write-back), with a breath every eight rows for the strips' feeder.
static uint16_t slideRow[W];
static bool slideFillOn = true;                             // (the host tests: 0 = the old way, the reference the slab is proved against)
static uint32_t slideN = 0, slideFlipN = 0, slideWaitN = 0, slideUs = 0, slideUsMax = 0, slideDebtUs = 0, slideFillN = 0, slideFillUs = 0;   // (/perf "slide")
static std::string slideTxtPending; static uint32_t slideTxtAt = 0;   // the slide text whose words changed and whose position is yet to come
struct SlideBox { int ix, iy, iw, ih, x0, y0, x1, y1, cw; };   // the inner box (inside the border), and its part on the screen
static bool slideBox(const Comp &c, SlideBox &b) {
    const int bw = c.borderw;
    b.ix = c.x + bw; b.iy = c.y + bw; b.iw = c.w - 2 * bw; b.ih = c.h - 2 * bw;
    b.x0 = max(0, b.ix); b.y0 = max(0, b.iy); b.x1 = min((int) W, b.ix + b.iw); b.y1 = min((int) H, b.iy + b.ih); b.cw = b.x1 - b.x0;
    return b.x1 > b.x0 && b.y1 > b.y0;
}
static void slideDone() {}                                  // the finger is up (1.11.142-144 gave a heap slab back here; the row is static now)
static inline void slideBreath(int row) { if (board->psramRestUs && (row & 7) == 7) delayMicroseconds(20); }   // (the twin) a gap in our stream for the strips' feeder, every eight rows
static inline void slideSpan(uint16_t *dst, const uint16_t *src, int row, int a, int b) { if (b > a) memcpy(dst + row * W + a, src + row * W + a, (b - a) * 2); }
static void slideLut(const Comp &c, uint16_t *lut) { const uint16_t bg = (uint16_t) c.bco, ink = inkOf(c); lut[0] = bg; for (int a = 1; a < 8; ++a) lut[a] = a >= 7 ? ink : blend565(bg, ink, a); }
// One row of the box rendered into slideRow: the background, then the row's share of the line that crosses it, letter by
// letter, clipped to the box - the pixels drawGlyphs puts there on one colour. (The lines stand one under the other, L.fh
// each from L.ty: a row belongs to one line, found by division.)
static void slideRowRender(const SlideBox &b, const TextLayout &L, const uint16_t *lut, int font, int fi, int xcen, int row) {
    const int cw = b.cw; const uint16_t bg = lut[0];
    { uint32_t *p = (uint32_t *) slideRow; const uint32_t v = (uint32_t) bg << 16 | bg; for (int i = 0, n = (cw + 1) / 2; i < n; ++i) p[i] = v; }
    const int d = row - L.ty, k = d >= 0 && L.fh > 0 ? d / L.fh : -1;   // (a row above the first line belongs to none)
    if (k < 0 || k >= (int) L.lines.size()) return;
    const std::string &line = L.lines[k]; if (line.empty()) return;
    const NextionFont *f = fontFor(font); const int ly = L.ty + k * L.fh, gr = row - ly;
    int pen = textLineX(L, b.ix, b.iw, font, xcen, line);
    for (unsigned char ch : line) {
        if (ch < f->first || ch > f->last) continue;
        const NextionGlyph &g = f->glyphs[ch - f->first];
        const int gw = g.bitmap_width, rowBytes = (gw + 1) / 2, gx = pen - g.kern_left;
        const int ca = max(0, b.x0 - gx), cb = min(gw, b.x1 - gx);   // the glyph's columns inside the box
        if (cb > ca) {
            const uint8_t *r = aaBits[fi] + aaOffset[fi][ch - f->first] + gr * rowBytes;
            for (int col = ca; col < cb; ++col) { const int a = (col & 1) ? (r[col >> 1] & 15) : (r[col >> 1] >> 4); if (a) slideRow[gx - b.x0 + col] = lut[a]; }
        }
        pen += g.width;
    }
}
// The canvas's band, caught up from the buffer on show (the rotation) but for the box's rows [r0, r1) and columns, which
// are about to be written whole: the margins and the rows outside the box, not the whole 12.8 kB.
static void slideEnsureBand(int band, const SlideBox &box, int r0, int r1) {
    if (!(canvasStale & (1ull << band)) || !pageFb) return;
    if (dcTx) { canvasEnsureRows(band << 3, 8); return; }   // (the DMA copy, when it is on, may have left the canvas's lines stale in the cache: the usual way, whole)
    const uint16_t *from = flipFb[flipShown];
    if (!from || from == pageFb) return;
    const int b0 = band << 3, b1 = min((int) H, b0 + 8);
    for (int r = b0; r < b1; ++r) {
        if (r >= r0 && r < r1) { slideSpan(pageFb, from, r, 0, box.x0); slideSpan(pageFb, from, r, box.x1, W); }
        else slideSpan(pageFb, from, r, 0, W);
    }
    canvasStale &= ~(1ull << band); canvasEnsureN++;
}
// The whole slide text drawn (drawComp): the border by gfx, the inner box through the slab into the canvas. false: not this
// way - the old code draws it (a see-through box, a font without its smooth table, no slab, a layer's canvas).
static bool slideFill(Comp &c) {
    if (!slideFillOn || c.sta != 1 || !pageFb || fbNow != pageFb) return false;
    const int fi = fontIdx(c.font); if (!aaBits[fi]) return false;
    SlideBox b; const bool any = slideBox(c, b);
    const uint32_t t0 = micros();
    const int bw = c.borderw;
    if (bw > 0) {                                           // the border's ring, as the fill of the whole box did it
        gfx->fillRect(c.x, c.y, c.w, bw, c.bco); gfx->fillRect(c.x, c.y + c.h - bw, c.w, bw, c.bco);
        gfx->fillRect(c.x, c.y + bw, bw, c.h - 2 * bw, c.bco); gfx->fillRect(c.x + c.w - bw, c.y + bw, bw, c.h - 2 * bw, c.bco);
    }
    drawFrame(c, c.bco, false);
    if (any) {
        const TextLayout L = textLayout(b.ix, b.iy, b.iw, b.ih, c.font, c.txt, c.xcen, c.ycen, c.isbr != 0, c.scroll, -1);
        uint16_t lut[8]; slideLut(c, lut);
        for (int r0 = b.y0; r0 < b.y1; ) {
            const int band = r0 >> 3, r1 = min(b.y1, (band + 1) << 3);
            slideEnsureBand(band, b, r0, r1);
            for (int row = r0; row < r1; ++row) { slideRowRender(b, L, lut, c.font, fi, c.xcen, row); memcpy(pageFb + row * W + b.x0, slideRow, b.cw * 2); slideBreath(row); }
            r0 = r1;
        }
    }
    slideFillN++; slideFillUs += micros() - t0;
    return true;
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
// RANGE BAR (1.11.35, Malcolm 8 Oct: "On the iPhone, I like being able to drag the blob and see where the channel is"):
// the phone page's bar for an in-flight adjustment, as a component of the main board's pages. A scale lo..hi (microseconds,
// 875-2125) across the width; n regions divided at d0..d4, each coloured and labelled (txt: the labels, '|' between);
// kind 0 a switch (every region live), 1 a knob (the outer regions dead), 2 a nudge (the middle dead); a marker at mk
// (the channel now; -1 none); round handles on the dividers, which the finger drags (5 us steps, never past a neighbour).
// Set by the main board as attributes (bar.d0=1300, bar.mk=1512 ...) and read back the same way (get bar.d0).
// 1.11.38 (B83): kind 3 a SELECTOR - Rotorflight's own switch: the handles are the two ENDS d0 and d1 of its travel, and
// the n regions between are its even divisions (it changes to position q where ((u - d0) * (n - 1) + W / 2) / W reaches q),
// drawn as the flight controller will have them; kind 4 the same with no handles (the ends are the transmitter's own banks).
static void rbSelectorEdges(int d0, int d1, int n, int lo, int hi, int *edges) {
    edges[0] = lo; edges[n] = hi;
    const long W = d1 - d0;
    for (int q = 1; q < n; ++q) { const long num = q * W - W / 2; edges[q] = W > 0 ? constrain((int) (d0 + (num + (n - 1) - 1) / (n - 1)), lo, hi) : d0; }
}
static int rbPad(const Comp &c) { return min(14, c.h / 2); }
static int rbAt(const Comp &c, int us, int lo, int hi) { const int p = rbPad(c); return c.x + p + (int) ((long) (c.w - 2 * p) * (us - lo) / max(1, hi - lo)); }
static int rbUs(const Comp &c, int x, int lo, int hi) { const int p = rbPad(c); return lo + (int) ((long) (x - c.x - p) * (hi - lo) / max(1, c.w - 2 * p)); }
static int rbGet(const Comp &c, const char *k, int d) { auto it = c.extra.find(k); return it == c.extra.end() ? d : it->second; }
static void drawRangeBar(Comp &c) {
    const int lo = rbGet(c, "lo", 875), hi = rbGet(c, "hi", 2125), n = constrain(rbGet(c, "n", 2), 1, 6), kind = rbGet(c, "kind", 0), mk = rbGet(c, "mk", -1);
    int edges[7]; edges[0] = lo; edges[n] = hi;
    const int d0 = constrain(rbGet(c, "d0", lo), lo, hi), d1 = constrain(rbGet(c, "d1", hi), lo, hi);
    if (kind >= 3) rbSelectorEdges(d0, d1, n, lo, hi, edges);
    else for (int k = 0; k < n - 1 && k < 5; ++k) { char key[3] = {'d', (char) ('0' + k), 0}; edges[k + 1] = constrain(rbGet(c, key, lo), lo, hi); }
    gfx->fillRect(c.x, c.y, c.w, c.h, c.bco);
    if (n == 1 && kind == 0 && c.txt.empty() && mk < 0) return;  // (nothing to show - no adjustments or switches yet: no bar, not a full-width blue one)
    const int p = rbPad(c), th = max(12, c.h - 2 * 9), ty = c.y + (c.h - th) / 2, mid = c.y + c.h / 2;
    static const uint16_t cols[3] = { 0x4C7E, 0x4E69, 0xFC80 };   // blue, green, orange (the phone page's)
    std::vector<std::string> labels; { size_t a = 0; while (true) { size_t b = c.txt.find('|', a); labels.push_back(c.txt.substr(a, b == std::string::npos ? std::string::npos : b - a)); if (b == std::string::npos) break; a = b + 1; } }
    const int fh = fontHeight(c.font);
    for (int k = 0; k < n; ++k) {                                 // the zones
        const bool dead = (kind == 1 && k != 1) || (kind == 2 && k == 1);
        const int x0 = rbAt(c, edges[k], lo, hi), x1 = rbAt(c, edges[k + 1], lo, hi);
        if (x1 <= x0) continue;
        gfx->fillRoundRect(x0, ty, x1 - x0, th, 6, dead ? 0x9CD3 : cols[k % 3]);
    }
    // the marker (the channel now): a white line edged in black, seen on every zone (green on the green zone was not)
    if (mk >= lo && mk <= hi) { const int mx = rbAt(c, mk, lo, hi); gfx->fillRect(mx - 2, c.y + 1, 5, c.h - 2, 0x0000); gfx->fillRect(mx - 1, c.y + 1, 3, c.h - 2, 0xFFFF); }
    // the zones' words over it, black on every zone (white read poorly on green and orange); a selector's end zones' words
    // in the room beside their round ends, not under them
    for (int k = 0; k < n; ++k) {
        int x0 = rbAt(c, edges[k], lo, hi), x1 = rbAt(c, edges[k + 1], lo, hi);
        if (x1 <= x0 || k >= (int) labels.size() || labels[k].empty()) continue;
        if (kind == 3 && k == 0) x0 = max(x0, rbAt(c, d0, lo, hi) + p);
        if (kind == 3 && k == n - 1) x1 = min(x1, rbAt(c, d1, lo, hi) - p);
        std::string l = labels[k]; int tw = textWidth(c.font, l);
        while (tw > x1 - x0 - 6 && l.size() > 1) { l.erase(l.size() - 1); tw = textWidth(c.font, l); }
        if (tw <= x1 - x0 - 6) drawGlyphs((x0 + x1 - tw) / 2, mid - fh / 2, c.font, 0x0000, l);
    }
    if (kind == 3) { for (int k = 0; k < 2; ++k) { const int hx = rbAt(c, k ? d1 : d0, lo, hi); gfx->fillCircle(hx, mid, p - 1, 0xFFFF); gfx->fillCircle(hx, mid, p - 4, 0x2A5F); } }
    else if (kind < 3) for (int k = 0; k < n - 1; ++k) { const int hx = rbAt(c, edges[k + 1], lo, hi); gfx->fillCircle(hx, mid, p - 1, 0xFFFF); gfx->fillCircle(hx, mid, p - 4, 0x2A5F); }
    (void) p;
}
static void drawComp(Comp &c) {
    if (loadingPage || noDraw) return;
    c.damaged = false;
    if (!c.vis || c.w <= 0 || c.h <= 0) return;
    if (c.x + c.w <= 0 || c.y + c.h <= 0 || c.x >= W || c.y >= H) return;        // parked off-screen on purpose
    const std::string &t = c.type;
    if (t == "variable" || t == "timer" || t == "audio") return;
    if (t == "external picture") {                          // the model's photo: txt holds the path the Teensy sent
        if (deferPics) { picsLater.push_back(c.name); return; }   // (1.11.120) drawn after the rotation, over the page's own background
        if (c.txt.empty() || !sdOk) { restoreUnder(c); return; }
        std::string base = c.txt.substr(c.txt.find_last_of("/\\") == std::string::npos ? 0 : c.txt.find_last_of("/\\") + 1);
        size_t dot = base.find_last_of('.'); if (dot != std::string::npos) base = base.substr(0, dot);
        const std::string path = imagePath(base);
        File f = sdOpenChecked(path.c_str());
        if (!f) { restoreUnder(c); return; }
        uint16_t wh[2] = { 0, 0 }; f.read((uint8_t *) wh, 4);
        if (!wh[0] || !wh[1] || wh[0] > 1024 || wh[1] > 1024) { f.close(); restoreUnder(c); return; }
        const int ox = c.x + (c.w - (int) wh[0]) / 2, oy = c.y + (c.h - (int) wh[1]) / 2;   // centred in the frame
        if ((int) wh[0] < c.w || (int) wh[1] < c.h) restoreUnder(c);   // (1.11.120: a picture that fills its frame needs nothing put back under it - 64 000 pixels less through the PSRAM)
        // (1.11.120) Read in slabs of up to 8 kB into internal memory (one multi-sector read each), not a row at a time: 200
        // reads of 640 bytes each cost the card ~100 ms, with the loop and the panel waiting on it. Short of memory: a row.
        std::vector<uint16_t> one;
        int chunk = max(1, min((int) wh[1], 8192 / ((int) wh[0] * 2)));
        uint16_t *buf = chunk > 1 ? (uint16_t *) heap_caps_malloc((size_t) chunk * wh[0] * 2, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT) : nullptr;
        const bool own = buf != nullptr;
        if (!buf) { chunk = 1; one.resize(wh[0]); buf = one.data(); }
        for (int y0 = 0; y0 < (int) wh[1]; y0 += chunk) {
            const int n = min(chunk, (int) wh[1] - y0);
            if ((int) f.read((uint8_t *) buf, (size_t) n * wh[0] * 2) != n * (int) wh[0] * 2) break;
            for (int yy = 0; yy < n; ++yy) { const int y = oy + y0 + yy; if (y >= 0 && y < H) gfx->draw16bitRGBBitmap(ox, y, buf + yy * wh[0], wh[0], 1); }
        }
        if (own) free(buf);
        f.close();
        return;
    }
    if (t == "textselect") { drawList(c); return; }
    if (t == "combobox") { drawCombo(c); return; }
    if (t == "sltext") {                                    // slide text: the help/log viewer, val_y pixels scrolled
        if (slideFill(c)) return;                           // (1.11.144) through the slab, as a drag draws it
        if (c.sta == 1) gfx->fillRect(c.x, c.y, c.w, c.h, c.bco); else restoreUnder(c);
        drawFrame(c, c.bco, false);
        const int bw = c.borderw;
        glyphBg = c.sta == 1 ? (int) (uint16_t) c.bco : -1;
        drawTextIn(c.x + bw, c.y + bw, c.w - 2 * bw, c.h - 2 * bw, c.font, c.sta == 1 ? inkOf(c) : (uint16_t) c.pco, c.txt, c.xcen, c.ycen, c.isbr != 0, c.scroll);
        glyphBg = -1;
        return;
    }
    if (t == "text" || t == "number" || t == "combobox") {
        if (c.sta == 1) gfx->fillRect(c.x, c.y, c.w, c.h, c.bco); else restoreUnder(c);
        drawFrame(c, c.bco, false);
        if (t == "text" && page.id == 8 && c.name == "pipe" && c.txt == "By Bluetooth") {   // 1.11.17 (Malcolm: "remove By Bluetooth and replace it with the little icon ... of a tooth which happens to be blue"): the tooth, at the right, blended on the box's colour
            const int ox = c.x + c.w - TOOTH_W - 4, oy = c.y + (c.h - TOOTH_H) / 2;
            const uint16_t bg = c.sta == 1 ? (uint16_t) c.bco : (uint16_t) page.bgColor;
            gfx->startWrite();
            for (int yy = 0; yy < TOOTH_H; ++yy) for (int xx = 0; xx < TOOTH_W; ++xx) {
                const int i = yy * TOOTH_W + xx; const int a = TOOTH_A[i]; if (!a) continue;
                const uint16_t f = TOOTH_RGB[i];
                const int r = ((f >> 11) * a + (bg >> 11) * (255 - a)) / 255, g = (((f >> 5) & 63) * a + ((bg >> 5) & 63) * (255 - a)) / 255, b = ((f & 31) * a + (bg & 31) * (255 - a)) / 255;
                gfx->writePixel(ox + xx, oy + yy, (uint16_t) ((r << 11) | (g << 5) | b));
            }
            gfx->endWrite();
            return;
        }
        std::string s;
        if (t == "number") { char b[16]; if (c.lenth > 0) snprintf(b, sizeof(b), "%0*ld", c.lenth, (long) c.val); else snprintf(b, sizeof(b), "%ld", (long) c.val); s = b; }   // (one format string with two arguments printed the digit count — every free-length number read 0)
        else if (t == "combobox") s = (c.val >= 0 && c.val < (int) c.options.size()) ? c.options[c.val] : c.txt;
        else s = c.txt;
        if (t == "text" && c.style == 5) {   // (1.11.40: the message box's words, wrapped inside its padding, each line centred, the lines centred as a block)
            if (s.empty()) return;
            const int p = MSGBOX_PAD, fh = fontHeight(c.font), lineH = fh + 4;
            const std::vector<std::string> ls = textLines(s, c.font, c.w - 2 * p, true);
            int y0 = c.y + (c.h - ((int) ls.size() * lineH - 4)) / 2;
            if (y0 < c.y + p / 2) y0 = c.y + p / 2;
            gfx->startWrite();
            const uint16_t ink = c.sta == 1 ? inkOf(c) : (uint16_t) c.pco;
            for (const auto &l : ls) { if (y0 + fh > c.y + c.h - p / 2) break; drawGlyphs(c.x + (c.w - textWidth(c.font, l)) / 2, y0, c.font, ink, l); y0 += lineH; }
            gfx->endWrite();
            return;
        }
        glyphBg = c.sta == 1 ? (int) (uint16_t) c.bco : -1;    // (1.11.116: the box's own colour under the letters)
        drawTextIn(c.x, c.y, c.w, c.h, c.font, c.sta == 1 ? inkOf(c) : (uint16_t) c.pco, s, c.xcen, c.ycen, t == "text" && c.isbr != 0, 0, t == "number" || c.isbr ? -1 : frameWidth(c));
        glyphBg = -1;   // numbers never wrap ("-16" took two lines on the trims page), nor end in dots
        return;
    }
    if (t == "button" || t == "dual-state button") {
        const bool on = (t == "dual-state button") ? (c.val != 0) : c.pressed;
        const uint16_t bg = on ? c.bco2 : c.bco, fg = needUnmet(c) ? (uint16_t) 0x8410 : c.sta == 3 ? (uint16_t) (on ? c.pco2 : c.pco) : inkOf(c, on);   // greyed out: mid-grey text
        if (c.sta == 3) restoreUnder(c);
        else { gfx->fillRect(c.x, c.y, c.w, c.h, bg); drawFrame(c, bg, on); }
        // 1.11.80 (Malcolm, 16 Oct, of the Channels page: "the right-hand column of buttons has been centre aligned, but it should
        // be left aligned"): a button's own alignment, 0 = left. It was taken as "none given" and centred - the only buttons
        // that say 0 are those eight (the left column says 2, right; every other button 1).
        drawTextIn(c.x, c.y, c.w, c.h, c.font, fg, c.txt, c.xcen, c.ycen ? c.ycen : 1, false, 0, c.sta == 3 ? 0 : frameWidth(c));
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
    if (t == "rangebar") { drawRangeBar(c); return; }
    if (t == "slider") {
        // The Nextion draws these (psta 0, wid/hig 255) as a thin track in bco with a round knob in pco
        // whose diameter is the component's thickness — a small dot on the 15 px trims, a big blob on the
        // 45 px volume slider. The knob's travel keeps it inside the component.
        restoreUnder(c);
        const int range = max(1, c.maxval - c.minval);
        const int v = constrain((int) c.val - c.minval, 0, range);
        uint16_t knob = (uint16_t) c.pco, face;                // (white: on White, Yellow or Sky the theme's text colour)
        if (themeFaceUnder(c, face)) knob = ldrc::themeMarkOn(knob, face, theme.ink());
        if (c.mode == 0) {
            const int d = max(6, c.h), r = d / 2, track = max(3, c.h / 4);
            gfx->fillRoundRect(c.x, c.y + (c.h - track) / 2, c.w, track, track / 2, c.bco);
            gfx->fillCircle(c.x + r + (long) (c.w - d) * v / range, c.y + c.h / 2, r - 1, knob);
        } else {
            const int d = max(6, c.w), r = d / 2, track = max(3, c.w / 4);
            gfx->fillRoundRect(c.x + (c.w - track) / 2, c.y, track, c.h, track / 2, c.bco);
            gfx->fillCircle(c.x + c.w / 2, c.y + c.h - r - (long) (c.h - d) * v / range, r - 1, knob);
        }
        return;
    }
    if (t == "checkbox" || t == "radio" || t == "switch") {
        restoreUnder(c);                                     // (a switch's rounded ends show what it sits on: the card of a page, or its picture)
        const int s = min(c.w, c.h);
        if (t == "radio") {                                  // a disc in bco; chosen, a dot in pco at its centre (the V1's pale disc with a red dot)
            const int r = s / 2 - 1, cx = c.x + c.w / 2, cy = c.y + c.h / 2;
            uint16_t ring = shade(c.bco, -25), face;          // (a white disc on White, Yellow or Sky: outlined in the theme's outline colour)
            if (themeFaceUnder(c, face) && !ldrc::themeStandsOut((uint16_t) c.bco, face)) ring = theme.edge();
            gfx->fillCircle(cx, cy, r, c.bco); gfx->drawCircle(cx, cy, r, ring);
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
            File f = sdOpenChecked(path);
            if (f) { uint16_t wh[2]; f.read((uint8_t *) wh, 4); std::vector<uint16_t> row(wh[0]);
                     for (int yy = 0; yy < wh[1] && c.y + yy < H; ++yy) { f.read((uint8_t *) row.data(), wh[0] * 2); gfx->draw16bitRGBBitmap(c.x, c.y + yy, row.data(), min((int) wh[0], W - c.x), 1); }
                     f.close(); }
        }
        return;
    }
    if (t == "hotspot") return;
    restoreRect(c.x, c.y, c.w, c.h);                        // unknown: leave the background
}
// (1.11.116) The whole canvas at once - the page's picture, or one colour - paced on the twin (src/psram_pace.h): at full
// speed it slipped the picture as surely as a copy to the panel did. Unseen: its pace does not matter.
// skip: boxes the page's own solid components are about to cover (drawPage): the background under them is never seen, and
// not painting it is a third to a half of the 70 ms the whole picture took (1.11.116). Rows are painted in the gaps between.
static void canvasWhole(const uint16_t *src, uint16_t colour, bool forPanel = false, const std::vector<Rect16> *skip = nullptr) {
    if (fbNow == pageFb) { canvasStale = 0; pageDeferred = false; }   // (1.11.116: every row written, or about to be by the boxes: nothing left to catch up)
    int16_t sx0[64], sx1[64];
    for (int y = 0; y < H; ++y) {
        uint16_t *row = fbNow + y * W;
        int n = 0;
        if (skip) for (const Rect16 &r : *skip) { if (y >= r.y && y < r.y + r.h && n < 64) { sx0[n] = r.x; sx1[n] = r.x + r.w; n++; } }
        for (int i = 1; i < n; ++i) { int j = i; while (j > 0 && sx0[j - 1] > sx0[j]) { std::swap(sx0[j - 1], sx0[j]); std::swap(sx1[j - 1], sx1[j]); j--; } }   // (by x: a dozen at most)
        int at = 0; uint32_t px = 0;
        for (int i = 0; i <= n; ++i) {
            const int gapEnd = i < n ? sx0[i] : W;
            if (gapEnd > at) { if (src) memcpy(row + at, src + y * W + at, (gapEnd - at) * 2); else std::fill_n(row + at, gapEnd - at, colour); px += gapEnd - at; }
            if (i < n && sx1[i] > at) at = sx1[i];
        }
        if (forPanel && (y & 7) == 7) wbPaced((uint32_t) (row - 7 * W), 8 * W * 2);   // (the panel's DMA will read it: written back as it goes, not in one burst; gently since 25 Oct)
        if (px) psramPace(px);
    }
    if (fbNow == screenFb) wbPaced((uint32_t) fbNow, W * H * 2);   // no canvas: the panel's DMA reads PSRAM directly
}
// The page's solid, rectangular components: a text or number box with its own colour behind it (sta 1) - the cards and
// islands the pages are built of. Their fillRect covers every pixel of the box, so the background need not go under them.
static std::vector<Rect16> solidBoxes() {
    std::vector<Rect16> out;
    for (const Comp &c : page.comps) {
        if (!c.vis || c.w <= 0 || c.h <= 0 || c.sta != 1) continue;
        if (c.type != "text" && c.type != "number" && c.type != "combobox" && c.type != "sltext") continue;
        int x = c.x, y = c.y, w = c.w, h = c.h;
        if (x < 0) { w += x; x = 0; } if (y < 0) { h += y; y = 0; }
        if (x + w > W) w = W - x; if (y + h > H) h = H - y;
        if (w < 16 || h < 2) continue;
        out.push_back({ (int16_t) x, (int16_t) y, (int16_t) w, (int16_t) h });
    }
    return out;
}
// (1.11.116) A page change on the twin is a ROTATION: the page is drawn into the canvas and the panel pointed at it; no copy
// (the compose of 1.11.115 was 120 ms of it). Not while our layer is up (the canvas is the pure page; the glass needs the
// layer over it: composed and flipped to instead), nor while a flip is in flight, nor from inside a TopDraw.
static bool rotationNow() { return flipOk && flipFb[2] && !topOn && !flipPending && !flipComposing && topDrawDepth == 0 && fbNow == pageFb; }
static void drawPageNow(bool show);
static void drawDeferred() { if (!pageDeferred) return; pageDeferred = false; drawPageNow(false); }
static void drawPage() {
    const bool hidden = flipOk && topOn && topWho == FLIGHT_LAYER_WHO && topX == 0 && topY == 0 && topW == W && topH == H;
    pageDeferred = false;
    if (hidden) { pageDeferred = true; if (pageT0) pageDrawMs = millis() - pageT0; return; }   // (the layer's own whole-screen dirty brings the flight spare on show)
    drawPageNow(true);
}
static void drawPageNow(bool show) {
    Busy busy_(BUSY_DRAW);
    uint32_t tp = micros();
    const bool rotate = show && rotationNow();
    if (page.bgMode == 0 && (rotate || !show)) canvasEnsureRows(0, H);   // (drawn over the page as it is: all of it must be here)
    if (page.bgMode == 1 || (page.bgMode == 2 && bgBuf)) {
        const std::vector<Rect16> skip = solidBoxes();
        canvasWhole(page.bgMode == 2 ? bgBuf : nullptr, (uint16_t) page.bgColor, rotate, &skip);
    }
    /* bgMode 0: leave the screen as it is and draw over it */
    pageBgUs = micros() - tp; tp = micros();
    pageTextUs = pagePicUs = pageOtherUs = 0; pageTextN = pagePicN = pageOtherN = 0;
    picsLater.clear(); deferPics = rotate;                 // (1.11.120) a rotation: the pictures off the card follow it (flipTick)
    for (auto &c : page.comps) {
        const uint32_t t1 = micros(); drawComp(c); const uint32_t us = micros() - t1;
        if (!c.vis || c.w <= 0) continue;
        if (board->psramRestUs && us > 200) delayMicroseconds(board->psramRestUs / 3);   // (1.11.119) a breath after each component drawn: its letters are many small writes into the PSRAM, and its code streams from the flash on the same bus, while the page before is still on show (the twin; ~3 ms a page)
        if (c.type == "text" || c.type == "number" || c.type == "xfloat" || c.type == "scrolltext" || c.type == "button" || c.type == "dsbutton") { pageTextUs += us; pageTextN++; }
        else if (c.type == "picture" || c.type == "crop" || c.type == "external picture") { pagePicUs += us; pagePicN++; }
        else { pageOtherUs += us; pageOtherN++; }
    }
    deferPics = false;
    pageCompsUs = micros() - tp;
    fillMemo.valid = false; fillMemo.ops.clear(); fillMemo.colour = -1;   // (1.11.99: a page drawn whole has no crumbs to repair)
    if (!show) return;                                     // (the deferred drawing: into the canvas only)
    if (pageT0) pageDrawMs = millis() - pageT0;
    if (rotate) {                                          // (1.11.116) the rotation: the panel is pointed at the canvas at the next frame's end
        for (int y0 = 0; y0 < H; y0 += 16) {               // (what the components left in the cache: written back 16 rows at a time, a rest between - not one burst of 64 kB at the switch)
            wbPaced((uint32_t) (pageFb + y0 * W), (uint32_t) min(16, H - y0) * W * 2);   // (25 Oct: gently)
            if (board->psramRestUs) delayMicroseconds(board->psramRestUs / 2);
        }
        dirtyN = 0; lastPresentMs = millis();
        if (pageT0) pageComposeMs = millis() - pageT0;
        flipAskedMs = millis(); flipRotating = true; flipFrom = flipShown; flipPending = true; flipWant = flipCanvas;
        return;
    }
    // (1.11.115) Otherwise composed into the spare and flipped to (src/page_flip.h) - our layer is up, or a flip is in flight.
    if (flipWholePage()) { lastPresentMs = millis(); return; }
    dirtyN = 0; present(0, 0, W, H); lastPresentMs = millis();   // the whole page in one move, now
    if (pageT0) { pageComposeMs = pageShownMs = millis() - pageT0; pageT0 = 0; }
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
// (1.11.142) A SLIDE TEXT UNDER A FINGER. Dragging the help/log viewer redrew its whole box for every step: the box filled
// in the canvas (553 kB of PSRAM), some 900 letters blended into it pixel by pixel, and the box copied to the panel's
// buffer - three walks through the PSRAM, each with the panel's own reads in its way. On the 16 MB twin that was the
// best part of 100 ms a step, and the text moved in jerks (Malcolm, 30 Oct 2026: "while sliding the finger it doesn't
// scroll smoothly"). Now a step goes through the slab (above), written once.
// (1.11.143) ... and WITHOUT A TEAR. 1.11.142 wrote the step straight into the buffer the panel was scanning: a frame caught
// part-way showed the box half old, half new - Malcolm's "occasional flickers during scrolling". So, on the twin, each
// step is written into the SPARE buffer (nobody is looking at it) and the panel is flipped to it at the frame end: a
// frame is all old or all new. What the spare lacked of the page (flipStale: everything, after a rotation; the box, after
// each step) is copied from the buffer on show first, outside the box - the box is written whole. After the flip the
// buffer that was on show is the spare, short of this one step (flipStale = the box), and the canvas's bands of the box
// are marked stale unless the canvas has newer rows waiting there (slideFlipDone). One flip a frame paces the steps.
static void slideFlipDone() {                              // (flipTick: a flip completed) the canvas lags the buffer on show in the box's bands
    if (!slideStaleWait) return;
    bool waiting = false;                                  // a change of the canvas waiting to be shown in those rows: the catch-up would undo it - the canvas stays as it is
    for (int i = 0; i < dirtyN; ++i) if (dirtyList[i].y < slideStaleY1 && dirtyList[i].y + dirtyList[i].h > slideStaleY0) waiting = true;
    if (!waiting) canvasStale |= slideStaleWait;
    slideStaleWait = 0;
}
// (1.11.144) The words of a slide text are drawn when their position follows (setInt val_y clears the wait), or 120 ms on.
static void slideTxtTick(bool now) {
    if (slideTxtPending.empty() || (!now && millis() - slideTxtAt < 120)) return;
    Comp *c = find(slideTxtPending); slideTxtPending.clear();
    if (c) redraw(*c);
}
static int slideDrag(Comp &c, int want) {                  // 1: drawn at `want`; 0: not this way - the caller sets the scroll and redraws as before; -1: not yet (a flip in flight), ask again next pass
    if (loadingPage || noDraw) { c.scroll = want; return 1; }
    if (c.type != "sltext" || c.sta != 1 || !c.vis || !pageFb || fbNow != pageFb) return 0;
    const int fi = fontIdx(c.font); if (!aaBits[fi]) return 0;   // (the 1-bit letters go through gfx: the old path)
    SlideBox b; if (!slideBox(c, b)) { c.scroll = want; return 1; }
    const int idx = indexOf(c);
    for (int j = idx + 1; j < (int) page.comps.size(); ++j) if (showsIn(page.comps[j], b.ix, b.iy, b.iw, b.ih)) return 0;   // something is drawn over it: the old path repaints that too
    // The twin: the rotation on (a canvas apart from the two panel buffers), the step written into the spare and flipped to.
    const bool twin = flipOk && canvas->lazy && flipFb[flipSpare] && flipFb[flipShown] && flipFb[flipSpare] != flipFb[flipShown] && flipFb[flipSpare] != pageFb && flipFb[flipShown] != pageFb;
    if (twin) {
        flipTick();                                        // (a flip that has completed is taken in here, not a pass later)
        if (flipPending || flipComposing) { slideWaitN++; return -1; }
        if (dirtyN) { presentDirty(true); if (dirtyN) { slideWaitN++; return -1; } }   // nothing of the canvas may be left waiting: the spare is brought up from the buffer on show
    }
    slideTxtPending.clear();                               // (words that were waiting for their position are drawn here, where the finger has them)
    c.scroll = want;
    const uint32_t t0 = micros();
    const TextLayout L = textLayout(b.ix, b.iy, b.iw, b.ih, c.font, c.txt, c.xcen, c.ycen, c.isbr != 0, c.scroll, -1);
    uint16_t lut[8]; slideLut(c, lut);
    uint16_t *spare = twin ? flipFb[flipSpare] : nullptr; const uint16_t *shown = twin ? flipFb[flipShown] : nullptr;
    if (twin) {
        if (spareHoldsFlight) { spareHoldsFlight = false; if (topCanvas) topCanvas->track = false; flipStale = { 0, 0, (int16_t) W, (int16_t) H }; flipStaleRow = 0; }   // (a kept flight composite: this use of the spare claims it, as a big change would)
        if (flipStale.w > 0 && flipStale.h > 0) {         // the spare's debt, from the buffer on show, outside the box
            const uint32_t d0 = micros();
            const int rx0 = max(0, (int) flipStale.x), rx1 = min((int) W, flipStale.x + flipStale.w), ry0 = max(0, (int) flipStale.y), ry1 = min((int) H, flipStale.y + flipStale.h);
            for (int r = ry0; r < ry1; ++r) {
                if (r >= b.y0 && r < b.y1) { slideSpan(spare, shown, r, rx0, min(rx1, b.x0)); slideSpan(spare, shown, r, max(rx0, b.x1), rx1); }
                else slideSpan(spare, shown, r, rx0, rx1);
                if (rx1 > rx0) wbPaced((uint32_t) (spare + r * W + rx0), (uint32_t) ((rx1 - rx0) * 2));   // (a row at a time)
                slideBreath(r);
            }
            slideDebtUs += micros() - d0;
        }
    }
    uint64_t stale = 0;
    for (int r0 = b.y0; r0 < b.y1; ) {
        const int band = r0 >> 3, r1 = min(b.y1, (band + 1) << 3), rows = r1 - r0;
        const bool over = twin && presentArea(b.x0, r0, b.cw, rows).over;   // (the rows under our layer: a help page's buttons share the box's first rows)
        if (!twin || over) {                               // the canvas: the 4 MB boards (shown by present, as before); on the twin the rows composed with the layer into the spare
            slideEnsureBand(band, b, r0, r1);
            for (int row = r0; row < r1; ++row) { slideRowRender(b, L, lut, c.font, fi, c.xcen, row); memcpy(pageFb + row * W + b.x0, slideRow, b.cw * 2); slideBreath(row); }
            if (twin) copyRows(spare, b.x0, r0, b.cw, rows, true); else dirty(b.x0, r0, b.cw, rows);
        } else {                                           // the twin: into the spare, whole bands, to be caught up by the canvas once shown
            for (int row = r0; row < r1; ++row) { slideRowRender(b, L, lut, c.font, fi, c.xcen, row); memcpy(spare + row * W + b.x0, slideRow, b.cw * 2); wbPaced((uint32_t) (spare + row * W + b.x0), (uint32_t) (b.cw * 2)); slideBreath(row); }
            stale |= 1ull << band;
        }
        r0 = r1;
    }
    memoTouched(b.x0, b.y0, b.cw, b.y1 - b.y0);
    if (twin) {                                            // the flip: at the frame end the panel scans the spare; the buffer that was on show becomes the spare, short of the box
        slideStaleWait = stale; slideStaleY0 = b.y0; slideStaleY1 = b.y1;
        flipBig = { (int16_t) b.x0, (int16_t) b.y0, (int16_t) b.cw, (int16_t) (b.y1 - b.y0) };
        flipAskedMs = millis(); flipPending = true; flipRotating = false; flipKept = false; flipFrom = flipShown; flipWant = flipSpare;
        slideFlipN++;
    }
    const uint32_t us = micros() - t0; slideN++; slideUs += us; if (us > slideUsMax) slideUsMax = us;
    return 1;
}
static void needRedraw() { for (auto &c : page.comps) if (!c.need.empty() && c.vis) redraw(c); }
static void drawPicsLater() { if (benchSkip & 1) { picsLater.clear(); return; } std::vector<std::string> names; names.swap(picsLater); for (auto &nm : names) if (Comp *c = find(nm)) redraw(*c); }   // (1.11.120: after the rotation)
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
// (1.11.137) The page files are parsed in the PSRAM. A page's tree needs about twice its file - up to 50 kB for the biggest
// pages - and ArduinoJson took it from the chip's own RAM in small pieces, which left that RAM in fragments: after forty
// page changes on the new transmitter the internal heap stood at 7 kB, the web server stopped answering, and the strips
// began to fall late (27 Oct 2026). The PSRAM has megabytes; internal RAM is for the panel, the radio and the card.
struct PsJsonAlloc : ArduinoJson::Allocator {
    void *allocate(size_t n) override { void *p = heap_caps_malloc(n, MALLOC_CAP_SPIRAM); return p ? p : malloc(n); }
    void deallocate(void *p) override { free(p); }
    void *reallocate(void *p, size_t n) override { return heap_caps_realloc(p, n, MALLOC_CAP_SPIRAM) ?: realloc(p, n); }
};
static PsJsonAlloc psJsonAlloc;
struct CompInfo { int id; std::string name; int typeCode; int txtMaxl; bool global; int32_t val; std::string txt; };   // (val, txt: as the page file has them: a global's value before anything wrote it)
using CompInfoList = std::vector<CompInfo, PsAlloc<CompInfo>>;   // (1.11.137) in the PSRAM: four pages' worth took 18 kB of the chip's RAM
static PsMap<std::string, CompInfoList> pageInfo;
static const CompInfoList *infoFor(const std::string &pg) {
    auto it = pageInfo.find(pg); if (it != pageInfo.end()) return &it->second;
    auto pid = pageIds.find(pg); if (pid == pageIds.end() || !assetsOk()) return nullptr;
    char path[32]; snprintf(path, sizeof(path), "/hmi/pages/%d.json", pid->second);
    File f = assetOpen(path); if (!f) return nullptr;
    JsonDocument filter; filter["comps"][0]["n"] = true; filter["comps"][0]["i"] = true; filter["comps"][0]["t"] = true; filter["comps"][0]["a"]["txt_maxl"] = true;
    filter["comps"][0]["g"] = true; filter["comps"][0]["val"] = true; filter["comps"][0]["txt"] = true;
    JsonDocument doc(&psJsonAlloc); DeserializationError err = deserializeJson(doc, f, DeserializationOption::Filter(filter)); f.close();
    if (err) return nullptr;
    CompInfoList v;
    for (JsonObject j : doc["comps"].as<JsonArray>()) v.push_back({ j["i"] | 0, std::string(j["n"] | ""), typeCodeOf(j["t"] | ""), j["a"]["txt_maxl"] | 0, (j["g"] | "l")[0] == 'g', j["val"] | 0, std::string(j["txt"] | "") });
    pageInfo[pg] = v;
    return &pageInfo[pg];
}
static const CompInfo *infoOf(const std::string &pg, const std::string &nm) { const CompInfoList *v = infoFor(pg); if (v) for (auto &ci : *v) if (ci.name == nm) return &ci; return nullptr; }
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
        if (attr == "val" && c->type == "textselect" && !c->damaged && c->val == v) {   // (1.11.120) the row it shows already: nothing to draw (the main board writes the model's number at every entry, after the list that already sits on it)
            const int was = c->scroll; listShowSelected(*c);
            if (c->scroll == was) { perfSkipped++; return; }
        }
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
        else if (attr == "val_y") { c->scroll = c->type == "sltext" ? constrain((int) v, 0, (int) getInt(pg, nm, "maxval_y")) : max(0, (int) v); if (c->type == "sltext") slideTxtPending.clear(); }   // (1.11.96) never past the text: a sum on the main board's side once scrolled the log 96 px beyond its last line, and the box showed blank. (1.11.144: the position the words were waiting for)
        else if (attr == "en") { c->en = v; paint = false; } else if (attr == "tim") { c->tim = v; paint = false; }
        else if (c->type == "rangebar") { auto it = c->extra.find(attr); if (it != c->extra.end() && it->second == v && !c->damaged) { perfSkipped++; return; } c->extra[attr] = v; }   // (a divider, the marker, the kind: the bar is drawn again)
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
        if (!c->damaged && c->txt == s && c->type != "sltext") { perfSkipped++; return; }   // (1.11.120: a picture named again is not read off the card again - the main board names the model's picture at every entry to the Models page, right after the page that drew it)
        c->txt = s; if (c->type == "sltext") c->scroll = 0;
        if (c->type == "external picture") picsLaterDrop(nm);   // (drawn now with its new name: not again after the rotation)
        if (c->type == "sltext") { slideTxtPending = c->name; slideTxtAt = millis(); return; }   // (1.11.144) drawn when its position follows (the main board sends val_y 50 ms after the words), or 120 ms on - not at the top first
        redraw(*c);
    }
    void send(const uint8_t *b, size_t n) override {
        outBuf.append((const char *) b, n);
        char h[4]; for (size_t i = 0; i < n; ++i) { snprintf(h, sizeof(h), "%02X ", b[i]); sentTrace += h; }
        sentTrace += "| ";
        if (sentTrace.size() > 600) sentTrace.erase(0, sentTrace.size() - 600);
    }
    void click(const std::string &pg, const std::string &nm, bool press) override {
        bool off; Comp *c = get(pg, nm, off); if (off || !c) return;
        if (press && (c->type == "dual-state button" || c->type == "checkbox" || c->type == "switch" || c->type == "radio")) { c->val = c->type == "radio" ? 1 : !c->val; keepTouched(*c); redraw(*c); }   // (1.11.81) as a finger: it changes at the press, then the press event runs
        const int key = c->key, cid = c->id; const std::string pgName = page.name;
        runScript(press ? c->evPress : c->evRelease, nm);
        if (!press && key != 255 && page.name == pgName) openKeyboard(key, cid);   // (1.11.36) a box clicked by the main board opens its keyboard, as a finger would: the adjustments bar's zones edit their values that way
    }
    void vis(const std::string &pg, const std::string &nm, bool on) override {
        bool off; Comp *c = get(pg, nm, off);
        if (off || !c) return;
        if (c->vis && !on) { c->vis = false; repaintHole(c->x, c->y, c->w, c->h); }
        else if (!c->vis && on) { c->vis = true; redraw(*c); }
        // B52 (10 Oct 2026): the Backup page's busy box is the main board's word that its backup, restore or write is running
        // (RF_Backup.h "vis busy,1"); the two command-line buttons of ours beside it go with it, so neither job can be started
        // under the other (the command line page refuses too: ScreenCli::mainBoardBusy)
        if (nm == "busy" && page.name == "RFBackUpView") { vis(pg, "ldrcDiff", !on); vis(pg, "ldrcExec", !on); }
    }
    void gotoPage(const std::string &name) override;
    void delayMs(uint32_t ms) override { flushOut(); delay(ms); }
    void play(int id, int channel, int loop) override { (void) channel; audioStart(id, loop != 0); }
    std::string pageNameById(int32_t id) override { return id >= 0 && id < (int) pageNames.size() ? pageNames[id] : ""; }
    std::string compNameById(const std::string &pg, int32_t id) override {
        if (pg.empty() || pg == page.name) { for (auto &c : page.comps) if (c.id == id) return c.name; return ""; }
        const CompInfoList *v = infoFor(pg); if (v) for (auto &ci : *v) if (ci.id == id) return ci.name;
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
        if (name == "volume") { audioSetVolume((int) v); pendingVol = audioVolume; pendingVolAt = millis(); }   // sent once at the Teensy's boot: survive ours
        if (name == "Screen_Background") { pendingBg = v; pendingBgAt = millis(); }   // the Teensy sends it once at ITS boot (and the background page at every tap); survive OURS
        return true;
    }
    std::map<std::string, int32_t> sys;
    void unknownCommand(const std::string &line) override {
        // "ldrc <word>": a button of our own, added to a page by hmi/overrides.json. Nothing goes to the Teensy.
        if (line.rfind("ldrc ", 0) == 0) { if (line == "ldrc update") updRequested = true; else if (line == "ldrc rxupdate") rxUpdRequested = true; else if (line == "ldrc wifi") wifiRequested = true; else if (line == "ldrc flight") flightRequested = true; else if (line == "ldrc colours") coloursRequested = true; else if (line == "ldrc appearance") appearanceRequested = true; else if (line == "ldrc defined") flightDefinedRequested = true; else if (line == "ldrc cli") cliJobWanted = 0; else if (line == "ldrc diff") cliJobWanted = 1; else if (line == "ldrc exec") cliJobWanted = 2; else if (line == "ldrc door") doorToggle(); return; }   // (1.11.4: Transmitter setup's "Workshop door" button, Malcolm: "an ordinary button that switches it on")
        unknownFromTeensy(line);
    }
    void unknownFromTeensy(const std::string &line) { badCount++; oddTrace += "script:" + line + " | "; if (oddTrace.size() > 400) oddTrace.erase(0, oddTrace.size() - 400); }
};
static Host host;
static void flushOut() { if (!outBuf.empty()) { Serial.write((const uint8_t *) outBuf.data(), outBuf.size()); outBuf.clear(); } }
static void filmNoteHelp(const std::string &script);           // (src/film_device.h)
static void runScript(const std::string &code, const std::string &self) {
    if (code.empty()) return;
    // (1.11.109) A help page asked for, from wherever: its subject, so that the help page shows its Animation button. Until
    // now only a main board page's Help button was noted (at its lift), and the Help buttons of the screen's own pages -
    // Appearance, Themes, the design page, the defined front screen - opened their help with no Animation (Malcolm, 22 Oct:
    // "The help is there but I could not find the animations buttons yet"). Every page's help script is on a Help button's
    // release (68 of them, checked), so a script with HelpView: in it is a Help tap.
    if (code.find("HelpView:") != std::string::npos) filmNoteHelp(code);
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
    auto it = pageIds.find(name); if (it == pageIds.end() || !assetsOk()) return false;
    pageT0 = millis() ? millis() : 1; pageDrawMs = pageComposeMs = pageShownMs = 0;   // (1.11.116) timed: /status "flip" "last"
    // (the screen saver's memory: taken as the screen blanks, used only by the restore that follows it)
    const bool restoring = !saverPage.empty() && page.name == "BlankView" && name == saverPage;
    if (name == "BlankView" && page.name != "BlankView" && !page.name.empty()) saverRemember();
    else if (!restoring && page.name == "BlankView") { saverPage.clear(); saverComps.clear(); }
    if (!page.evExit.empty()) runScript(page.evExit, "");
    char path[32]; snprintf(path, sizeof(path), "/hmi/pages/%d.json", it->second);
    uint32_t tp = micros();
    // (1.11.116) A page's file is kept in PSRAM once read (eight of them, the least recently used making way): the card
    // took 16-20 ms of every page change, and OK goes back to a page just left. The parse copies what it keeps, so the
    // text can stay. An update of the files restarts the screen, and the memory with it.
    struct PageRaw { int id; char *buf; size_t len; uint32_t used; };
    static PageRaw rawCache[8] = {}; static size_t rawBytes = 0;
    char *raw = nullptr; size_t got = 0; PageRaw *slot = nullptr;
    for (auto &e : rawCache) if (e.buf && e.id == it->second) { slot = &e; break; }
    if (slot) { raw = slot->buf; got = slot->len; slot->used = millis(); }
    else {
        File f = assetOpen(path); if (!f) return false;
        const size_t n = f.size(); raw = (char *) psMallocRoom(n + 1); if (!raw) { f.close(); return false; }   // (1.11.132: a page must never fail for want of room - a resident picture goes first)
        got = sdReadPaced(f, (uint8_t *) raw, n); raw[got] = 0; f.close();   // read into memory (a File stream parses a byte at a time), in paced slabs (1.11.120), then parsed
        for (auto &e : rawCache) if (!e.buf) { slot = &e; break; }
        if (!slot) { slot = &rawCache[0]; for (auto &e : rawCache) if (e.used < slot->used) slot = &e; free(slot->buf); rawBytes -= slot->len; }
        *slot = { it->second, raw, got, millis() }; rawBytes += got;
        while (rawBytes > 600000) {                        // (never more than ~600 kB of PSRAM: the oldest goes)
            PageRaw *old = nullptr; for (auto &e : rawCache) if (e.buf && &e != slot && (!old || e.used < old->used)) old = &e;
            if (!old) break;
            free(old->buf); rawBytes -= old->len; *old = {};
        }
    }
    pageSdUs = micros() - tp; tp = micros();
    JsonDocument doc(&psJsonAlloc);                        // (1.11.137) the tree in the PSRAM, not the chip's RAM (PsJsonAlloc)
    DeserializationError err = deserializeJson(doc, (const char *) raw, got);
    if (err) return false;
    pageParseUs = micros() - tp;
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
        // (1.11.80: a button that gives no alignment is centred; one that says 0 is LEFT, as on the Nextion)
        JsonObject a = j["a"]; c.xcen = a["xcen"] | ((c.type == "button" || c.type == "dual-state button") ? 1 : 0); c.ycen = a["ycen"] | 0; c.borderw = a["borderw"] | 0; c.lenth = a["lenth"] | 0; c.dez = a["dez"] | 0;
        c.wid = a["wid"] | 20; c.hig = a["hig"] | 20; c.maxval = a["maxval"] | 100; c.minval = a["minval"] | 0; c.mode = a["mode"] | 0; c.tim = a["tim"] | 0; c.en = a["en"] | 0; c.isbr = a["isbr"] | 0;
        c.key = a["key"] | 255; c.txtMaxl = a["txt_maxl"] | 0; c.dis = a["dis"] | 0; c.typeCode = typeCodeOf(c.type);
        c.dir = a["dir"] | 1; c.bco1 = col["bco1"] | 65535; c.pco3 = col["pco3"] | 0x8410; c.style = a["style"] | 0;
        c.roles = ldrc::themeRoles(c.bco, c.bco2, c.pco, c.pco2, c.borderc);   // (from the page's own colours)
        c.centre = j["centre"] | false;
        if (c.type == "rangebar") { c.extra["lo"] = a["lo"] | 875; c.extra["hi"] = a["hi"] | 2125; c.extra["n"] = a["n"] | 2; c.extra["kind"] = a["kind"] | 0; c.extra["mk"] = a["mk"] | -1; c.extra["d0"] = a["d0"] | 1500; c.extra["d1"] = a["d1"] | 1700; c.extra["d2"] = a["d2"] | 1900; c.extra["d3"] = a["d3"] | 2000; c.extra["d4"] = a["d4"] | 2100; }
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
    if (pageDeferred) { if (np.bgMode == 0) drawDeferred(); else pageDeferred = false; }   // (1.11.116) a page drawn over this one needs it drawn; a whole new page does not
    page = std::move(np);                                  // (1.11.120: moved, not copied - the whole component set, strings and maps, was copied once more at every page change)
    touchNote("page " + name);
    touchLockout = true;
    strlcpy(rtcPage, name.c_str(), sizeof(rtcPage)); rtcMagic = 0x4C445243;   // our own restart comes back to this page
    picPageLoaded();                                       // (Malcolm, 10-03: the old picture page flashed up before the new chooser covered it)
    // Nextion order: preinitialize (may vis/colour things, choose the background) -> ONE paint -> postinitialize.
    tp = micros();
    loadingPage = true;
    runScript(page.evPre, "");
    loadingPage = false;
    if (page.bgMode == 2) loadBackground(page.bgPic);
    pagePreUs = micros() - tp;
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
// (1.11.99) The curve page's dots and rings sit ON the box's edges, so up to 10 px of them lie outside the box, on the cards
// around it. The clear (the fill) never reaches those pixels, and once the point had moved they stayed as white crumbs
// (Malcolm, 20 Oct 2026: "some edge points have moved, sometimes they leave behind little white marks on the background
// colour outside the box"; Version 1 hid them by repainting the whole page before every redraw, B135 stopped that). When the
// same clear comes again, every op that reached past the box has its outside pixels put back to what the page shows there:
// the topmost solid card (a text or number box with a background of its own) at that pixel, else the page's picture.
static void repairOutside(int x, int y, int w, int h) {
    if (x < 0) { w += x; x = 0; } if (y < 0) { h += y; y = 0; }
    if (x + w > W) w = W - x; if (y + h > H) h = H - y;
    if (w <= 0 || h <= 0) return;
    std::vector<const Comp *> cards;
    for (auto &c : page.comps)
        if (c.vis && c.sta == 1 && (c.type == "text" || c.type == "number") && c.x < x + w && c.x + c.w > x && c.y < y + h && c.y + c.h > y) cards.push_back(&c);
    gfx->startWrite();
    for (int yy = y; yy < y + h; ++yy)
        for (int xx = x; xx < x + w; ++xx) {
            const Comp *top = nullptr;
            for (auto *c : cards) if (xx >= c->x && xx < c->x + c->w && yy >= c->y && yy < c->y + c->h) top = c;   // (drawn later = on top)
            gfx->writePixel(xx, yy, top ? (uint16_t) top->bco : (page.bgMode != 1 && bgBuf) ? bgBuf[yy * W + xx] : (uint16_t) page.bgColor);
        }
    gfx->endWrite();
    dirty(x, y, w, h); damage(x, y, w, h);
}
static void repairOutsideOp(const DrawOp &op) {                  // the parts of an op's box that lie outside the memo's box
    int bx, by, bw, bh;
    if (op.kind == 1) { bx = min(op.a, op.c) - 1; by = min(op.b, op.d) - 1; bw = abs(op.c - op.a) + 3; bh = abs(op.d - op.b) + 3; }   // (eraseLine's 3x3 brush)
    else { bx = op.a; by = op.b; bw = op.c; bh = op.d; }
    const int mx0 = fillMemo.x, my0 = fillMemo.y, mx1 = fillMemo.x + fillMemo.w, my1 = fillMemo.y + fillMemo.h;
    if (bx < mx0) repairOutside(bx, by, min(bw, mx0 - bx), bh);                            // left of the box
    if (bx + bw > mx1) repairOutside(max(bx, mx1), by, bx + bw - max(bx, mx1), bh);        // right of it
    const int ix = max(bx, mx0), iw = min(bx + bw, mx1) - ix;                              // above and below, between those
    if (iw > 0 && by < my0) repairOutside(ix, by, iw, min(bh, my0 - by));
    if (iw > 0 && by + bh > my1) repairOutside(ix, max(by, my1), iw, by + bh - max(by, my1));
}
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
// (1.11.140, Malcolm, 28 Oct 2026, a photo of the Rates curves page: "Just a couple of stray lines outside the graph on
// this page" - one from the plot's corner off the bottom of the screen, one across the legend.) The main board draws
// with whole numbers inside the screen, five of them to a line. A command that is not that is two of its commands run
// into one: a flash write masks the wire's interrupt for its whole length (the core's UART handler is not in IRAM) and
// the 128-byte FIFO then overflows in 1.4 ms at 921600 baud, whatever its threshold (setup). Such a command is dropped
// and counted (/status "drawbad" and "odd", the text at /odd): a missing piece of a curve, never a line across the page.
// The writes that could land under the main board's stream wait for a quiet wire (prefsPoll, flight_device.h, loop).
static uint32_t drawDropped = 0;
static bool plainInt(const std::string &t, long lo, long hi) {   // digits only (a leading minus allowed), within lo..hi
    if (t.empty() || t.size() > 6) return false;
    size_t i = t[0] == '-' ? 1 : 0; if (i >= t.size()) return false;
    for (; i < t.size(); ++i) if (!isdigit((unsigned char) t[i])) return false;
    const long v = atol(t.c_str()); return v >= lo && v <= hi;
}
static bool colourToken(const std::string &t) {                 // a number, or a name colourOf() knows (letters only)
    if (plainInt(t, 0, 65535)) return true;
    if (t.empty()) return false;
    for (char ch : t) if (!isalpha((unsigned char) ch)) return false;
    return true;
}
static bool drawSane(const std::string a[], int n, int need) {  // exactly need args: coordinates within a screen's reach, the last a colour
    if (n != need) return false;
    for (int i = 0; i + 1 < need; ++i) if (!plainInt(a[i], -64, 1024)) return false;
    return colourToken(a[need - 1]);
}
static bool drawDrop(const std::string &cmd) {
    drawDropped++; badCount++;
    oddTrace += "draw:" + cmd.substr(0, 60) + " | "; if (oddTrace.size() > 400) oddTrace.erase(0, oddTrace.size() - 400);
    return true;
}
static bool drawVerb(const std::string &cmd) {
    const size_t sp = cmd.find(' '); if (sp == std::string::npos) return false;
    const std::string verb = cmd.substr(0, sp);
    if (verb != "line" && verb != "fill" && verb != "draw" && verb != "cir" && verb != "cirs" && verb != "cls" && verb != "pic" && verb != "xstr") return false;
    if (noDraw || loadingPage) return true;
    std::string a[12]; const int n = splitArgs(cmd.substr(sp + 1), a, 12);
    auto I = [&](int i) { return i < n ? atoi(a[i].c_str()) : 0; };
    if (verb == "line" || verb == "fill" || verb == "draw") { if (!drawSane(a, n, 5)) return drawDrop(cmd); }
    else if (verb == "cir" || verb == "cirs") { if (!drawSane(a, n, 4)) return drawDrop(cmd); }
    else if (verb == "pic") { if (n != 3 || !plainInt(a[0], -64, 1024) || !plainInt(a[1], -64, 1024) || !plainInt(a[2], 0, 9999)) return drawDrop(cmd); }
    if (verb == "line" && n >= 5) {
        const int x1 = I(0), y1 = I(1), x2 = I(2), y2 = I(3), bx = min(x1, x2), by = min(y1, y2), bw = abs(x2 - x1) + 1, bh = abs(y2 - y1) + 1;
        gfx->drawLine(x1, y1, x2, y2, colourOf(a[4]));
        dirtyLine(x1, y1, x2, y2); memoOp(1, x1, y1, x2, y2, bx, by, bw, bh); damage(bx, by, bw, bh);
    }
    else if (verb == "fill" && n >= 5) {
        const int x = I(0), y = I(1), w = I(2), h = I(3), col = colourOf(a[4]);
        const bool same = x == fillMemo.x && y == fillMemo.y && w == fillMemo.w && h == fillMemo.h && col == fillMemo.colour;
        if (same) for (auto &op : fillMemo.ops) repairOutsideOp(op);   // (1.11.99) what reached past the box since the last clear: its crumbs on the cards go too
        if (fillMemo.valid && same) {
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
    else if (verb == "cls" && n >= 1) { canvasWhole(nullptr, (uint16_t) colourOf(a[0])); fillMemo.valid = false; fillMemo.ops.clear(); fillMemo.colour = -1; dirty(0, 0, W, H); damage(0, 0, W, H); }
    else if (verb == "pic" && n >= 3 && sdOk) {
        char path[32]; snprintf(path, sizeof(path), "/hmi/pic/%d.565", I(2));
        File f = sdOpenChecked(path);
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
    Busy busy_(BUSY_HANDLE);
    cmdCount++;
    if (cmd.rfind("pong=", 0) == 0) { pongCommand(cmd.substr(5)); return; }
    if (cmd.rfind("ldrcpipe ", 0) == 0) { blePipeCommand(cmd.substr(9)); return; }   // the main board's Bluetooth pipe to the receiver (src/ble_device.h, 1.11.1)
    if (cmd.rfind("ldrctx ", 0) == 0) { bleTxCommand(cmd.substr(7)); return; }
    if (cmd.rfind("ldrcreq ", 0) == 0) { bleHttpCommand(cmd.substr(8)); return; }   // (1.11.18) the main board asks the receiver something over the pipe   // the main board's Pong, once a frame: ours to draw (src/pong_device.h), before the script sees it as a system variable
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
    if (!topCanvas) topCanvas = new PacedCanvas(W, H, screen);
    while (!topCanvas->begin(GFX_SKIP_OUTPUT_BEGIN)) {     // no room: give up a background picture that is not showing, and try again
        if (!bgEvictOne()) break;
    }
    topFb = topCanvas->getFramebuffer();
    return topFb != nullptr;
}
static uint32_t topEpoch = 0;                              // (1.11.68) drawings on the layer, counted: the defined front screen knows when another page of ours has drawn there
struct TopDraw {                                           // while one of these lives, gfx draws on our layer
    Arduino_GFX *g; uint16_t *f;
    TopDraw() : g(gfx), f(fbNow) { gfx = topCanvas; fbNow = topFb; ++topEpoch; ++topDrawDepth; }
    ~TopDraw() { gfx = g; fbNow = f; --topDrawDepth; }
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
    teensyLink.keepFolder("/banks56", folder + "/banks56", ".B56");   // 1.11.98: banks 5 and 6 of the models that use them (Teensy B130)
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
    gfx->fillRect(x, y, w, h, back);
    for (int i = 0; i < 3; ++i) gfx->drawRect(x + i, y + i, w - 2 * i, h - 2 * i, 0x08A6);   // (the message boxes' dress: a dark ring, a frame inside it)
    for (int i = 3; i < 5; ++i) gfx->drawRect(x + i, y + i, w - 2 * i, h - 2 * i, ink);
    const char *title = result ? (bad ? "Transmitter update failed" : "Transmitter updated") : "Updating the transmitter";   // (the red face says it failed: no capitals needed)
    clipX0 = x + 8; clipY0 = y + 4; clipX1 = x + w - 8; clipY1 = y + h - 4;
    gfx->startWrite();
    drawGlyphs(x + (w - textWidth(0, title)) / 2, y + 14, 0, ink, title);
    std::string line = result ? teensyLink.result() : teensyLink.stage();
    if (result && line.rfind("FAILED at ", 0) == 0) line = line.substr(10);
    if (!line.empty() && line[0] >= 'a' && line[0] <= 'z') line[0] = (char) (line[0] - 32);   // (shown as a sentence: "Sending /FW/TXFW.BIN", as the update panel says it)
    // two lines of 28-point text, broken at a space
    std::string l1 = line, l2;
    if (textWidth(6, l1) > w - 40) { size_t cut = l1.size(); while (cut > 0 && textWidth(6, l1.substr(0, cut)) > w - 40) cut = l1.rfind(' ', cut - 1) == std::string::npos ? 0 : l1.rfind(' ', cut - 1); if (cut) { l2 = l1.substr(cut + 1); l1 = l1.substr(0, cut); } }
    drawGlyphs(x + (w - textWidth(6, l1)) / 2, y + 66, 6, ink, l1);
    if (!l2.empty()) drawGlyphs(x + max(8, (w - textWidth(6, l2)) / 2), y + 98, 6, ink, l2);
    gfx->endWrite();
    if (!result) {
        const uint32_t size = teensyLink.fileSize(), done = teensyLink.fileDone();
        gfx->drawRect(x + 40, y + 140, w - 80, 22, ink);
        if (size) gfx->fillRect(x + 42, y + 142, (int) ((uint64_t) (w - 84) * min(done, size) / size), 18, ldrc::themeIsLight(back) ? 0x0320 : 0x07E0);   // (bright green does not show on a light theme)
        char b[64]; snprintf(b, sizeof(b), "Step %u of %u", (unsigned) min(teensyLink.stepIndex() + 1, teensyLink.stepCount()), (unsigned) teensyLink.stepCount());
        gfx->startWrite(); drawGlyphs(x + 40, y + 172, 2, dim, b);
        const char *warn = "Do not switch off";
        drawGlyphs(x + w - 40 - textWidth(2, warn), y + 172, 2, theme.accent(), warn); gfx->endWrite();   // (yellow, or on a light theme its text colour)
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
    if (flipRotating && flipPending && millis() - flipAskedMs < 80) return;   // (1.11.116) the canvas is about to go on show: nothing drawn into it until it has (a frame at most; the bytes wait in the 32 kB buffer)
    const uint32_t passT0 = micros();
    while (Serial.available()) {
        uint8_t b = Serial.read();
        const ldrc::Router::What what = router.push(b, millis(), frame);
        if (what == ldrc::Router::WHOLE_FRAME) { buf.clear(); ffs = 0; teensyLink.frameArrived(frame); continue; }
        if (what != ldrc::Router::TO_DISPLAY) continue;
        if (b == 0xFF) {
            if (++ffs == 3) {
                int bits = 0;
                if (ldrc::txStatusCommand(buf.data(), (unsigned) buf.size(), bits)) { const bool modelWas = txStatus >= 0 && (txStatus & TX_MODEL); const bool bindWas = tx.binding; const char *why = tx.said(bits); if (why) applyRadios(why); if (modelWas != ((bits & TX_MODEL) != 0) || bindWas != tx.binding) needRedraw(); teensyCommands++; teensyLink.sawDisplayTraffic(); }   // (from the wire only: nothing the Mac sends can say what the transmitter is doing)
                else if (ldrc::rxStatusCommand(buf.data(), (unsigned) buf.size(), rxNews)) { rxNews.atMs = millis(); rxNewsAny = true; teensyCommands++; teensyLink.sawDisplayTraffic(); }
                else if (!buf.empty()) { const uint32_t t0 = micros(); handle(buf); perfHandleUs += micros() - t0; perfCmds++; teensyCommands++; teensyLink.sawDisplayTraffic(); }
                buf.clear(); ffs = 0;
                flipTick();   // (1.11.116) the new page's compose goes on between commands: this loop runs as long as the main board streams (passes of 100-700 ms were measured), and the page showed 400 ms late (Malcolm, 24 Oct)
                // (1.11.120) The page command asked for a rotation: NOTHING more is drawn into the canvas until the panel shows it
                // (the wait above, a frame at most). Before, the commands right behind "page ModelsView" - its two lists - were
                // drawn into the very buffer about to go on show, and a switch that landed mid-draw showed a half-drawn list
                // for a frame: the flicker that stayed on that page. And a pass is at most 50 ms: the finger, the panel and
                // the catch-ups between (that same stream held the loop 320-420 ms; the bytes keep in the 32 kB buffer).
                if (flipRotating && flipPending) break;
                if (micros() - passT0 > 50000) break;
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
    in = true; pumpSerial(); teensyLink.poll(); audioFill(); flipTick(); in = false;
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
    // Hold the top-left corner for 1.5 s: radios on/off (a bench control, remembered across power cycles).
    // Hold the top-RIGHT corner for 3 s: the workshop door, open or shut on the network we are on.
    // On every page, ours included (1.11.3; Malcolm on the defined front screen: "After three seconds or more, no banner").
    // A corner that has been held is a corner, not a button: whatever lies under the finger (on most pages the Help
    // button) is let go without its release event, and nothing counts until the finger has lifted.
    static uint32_t cornerSince = 0; static bool cornerFired = false;
    static uint32_t doorSince = 0; static bool doorFired = false;
    static uint32_t upSince = 0;                                // when the finger was last seen up (0 while it is down)
    if (pressed) upSince = 0; else if (!upSince) upSince = now;
    const bool lifted = !pressed && now - upSince > 120;        // 1.11.5: a sample the GT911 dropped mid-press is not a lift (the holds began again at every dropped sample: "I held for three seconds, no banner"); the flight screen's long press learnt this in 1.10.3
    bool cornerHeld = false;
    if (pressed && x[0] < 48 && y[0] < 48) { if (!cornerSince) { cornerSince = now; cornerFired = false; } else if (!cornerFired && now - cornerSince > 1500) { cornerFired = true; cornerHeld = true; setRadios(!radiosOn); } }
    else if (lifted) cornerSince = 0;
    if (pressed && x[0] >= W - 48 && y[0] < 48) { if (!doorSince) { doorSince = now; doorFired = false; } else if (!doorFired && now - doorSince > 3000) { doorFired = true; cornerHeld = true; doorToggle(); } }
    else if (lifted) doorSince = 0;
    if (cornerHeld) {                                           // (our own pages: their handlers see no lift, the lockout holds until the finger is up)
        if (down && held >= 0 && held < (int) page.comps.size()) { Comp &c = page.comps[held]; c.pressed = false; if (c.type == "button" || c.type == "dual-state button") redraw(c); }
        // B59 (10 Oct 2026): a page of our own forgets the finger too - before, its press stayed (the lift never reached it), so
        // the button under the corner was still "down" and the next tap anywhere was swallowed (or pressed it, lifted on it)
        if (wifiPageUp()) wifiTouchCancel(); else if (cliUp()) cliTouchCancel(); else if (filmUp() || filmMenuUp()) filmTouchCancel(); else if (picPanelUp()) picTouchCancel(); else if (flightUp()) flightTouchCancel();
        else if (coloursUp()) coloursTouchCancel(); else if (appearanceUp()) appearanceTouchCancel(); else if (updPanelUp()) updTouchCancel();
        filmButtonCancel();
        down = false; held = -1; touchLockout = true; touchPainted = true;
        return;
    }
    static bool oursWasUp = false; static uint32_t oursWentAt = 0;
    if (!(updPanelUp() || wifiPageUp() || picPanelUp() || flightUp() || coloursUp() || appearanceUp() || cliUp() || filmUp() || filmMenuUp()) && oursWasUp) {   // our page has just gone: the finger that closed it, and the second tap of a double tap, are not for the page underneath
        oursWasUp = false; oursWentAt = now; touchLockout = true; lastSeen = now;
    }
    if (updPanelUp() || wifiPageUp() || picPanelUp() || flightUp() || coloursUp() || appearanceUp() || cliUp() || filmUp() || filmMenuUp()) {   // a page of our own has the screen
        oursWasUp = true;
        if (down && held >= 0 && held < (int) page.comps.size()) { page.comps[held].pressed = false; }
        down = false; held = -1;
        if (wifiPageUp()) wifiTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        else if (picPanelUp()) picTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        else if (flightUp()) flightTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        else if (coloursUp()) coloursTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        else if (appearanceUp()) appearanceTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        else if (cliUp()) cliTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        else if (filmUp()) filmTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        else if (filmMenuUp()) filmMenuTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        else updTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now);
        return;
    }
    // The page changed under the finger (the main board answers a press at once: a popup's Cancel loads the page it came
    // from while the finger is still down). The press belonged to the page that has gone: its component's place in the
    // list now names some other component on the new page, and the lift must not press that one. (Screen 1.9.2; Malcolm,
    // 10-05: Cancel on the Models page's questions "invokes an unasked for function" - the button at the same place in
    // the new page's list - and so on round, "an endless loop of more and more cancels".)
    if (touchLockout && down) { down = false; held = -1; dragged = false; }
    if (!down && !touchLockout && filmButtonTouch(pressed, pressed ? x[0] : 0, pressed ? y[0] : 0, now)) return;   // (1.11.85) the help page's Film button
    if (pressed) { lastSeen = now; lastX = x[0]; lastY = y[0]; host.sys["tch0"] = x[0]; host.sys["tch1"] = y[0]; touchPainted = true; }
    else if (down) touchPainted = true;
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
        if (held >= 0 && page.comps[held].type == "rangebar") {   // the handle nearest the finger, if it is near enough; else a tap on a zone (reported at the release)
            Comp &c = page.comps[held]; const int lo = rbGet(c, "lo", 875), hi = rbGet(c, "hi", 2125), n = constrain(rbGet(c, "n", 2), 1, 6), kind = rbGet(c, "kind", 0);
            int best = -1, bestD = 30;
            const int handles = kind == 3 ? 2 : kind >= 4 ? 0 : n - 1;   // (a selector: its two ends; its fixed form: none)
            for (int k = 0; k < handles && k < 5; ++k) { char key[3] = {'d', (char) ('0' + k), 0}; const int d = abs(x[0] - rbAt(c, rbGet(c, key, lo), lo, hi)); if (d < bestD) { bestD = d; best = k; } }
            c.extra["drag"] = best;
            c.extra["tap"] = best < 0 ? constrain(rbUs(c, x[0], lo, hi), lo, hi) : -1;
        }
        if (held >= 0) {
            Comp &c = page.comps[held]; c.pressed = true; dragS0 = c.scroll;
            // (1.11.81) As a Nextion does: a switch, dual-state button or checkbox flips as the finger LANDS, a radio turns on, and
            // the press event then sees the new value. They flipped at the lift, after the press event had run: the curve page's
            // switches clear the other two in their press event "if(Smooth.val==1)", which saw the old value, so after Straight
            // neither Smooth nor Exponential could be chosen - two stayed on and the main board kept Straight (Malcolm, 17 Oct 2026).
            const bool flips = c.type == "dual-state button" || c.type == "checkbox" || c.type == "switch" || c.type == "radio";
            if (flips) c.val = c.type == "radio" ? 1 : !c.val;
            if (c.type == "slider" && sliderTo(c, x[0], y[0])) keepTouched(c);
            if (c.type == "button" || c.type == "slider" || flips) redraw(c);
            runScript(c.evPress, c.name);
        }
        else runScript(page.evPress, "");
    } else if (pressed && down && held >= 0 && held < (int) page.comps.size() && page.comps[held].type == "rangebar") {
        Comp &c = page.comps[held]; const int k = rbGet(c, "drag", -1);   // dragging a handle: 5 us steps, never past its neighbours
        if (k >= 0 && now - lastDragDraw > 40) {
            const int lo = rbGet(c, "lo", 875), hi = rbGet(c, "hi", 2125);
            char key[3] = {'d', (char) ('0' + k), 0}, kp[3] = {'d', (char) ('0' + k - 1), 0}, kn[3] = {'d', (char) ('0' + k + 1), 0};
            const int n = constrain(rbGet(c, "n", 2), 1, 6), kind = rbGet(c, "kind", 0);
            int us = ((rbUs(c, x[0], lo, hi) + 2) / 5) * 5;
            const int handles = kind == 3 ? 2 : n - 1;   // (a selector's ends never pass each other either)
            const int minUs = k > 0 ? rbGet(c, kp, lo) + 5 : lo + 5, maxUs = k + 1 < handles ? rbGet(c, kn, hi) - 5 : hi - 5;
            us = constrain(us, minUs, maxUs);
            if (us != rbGet(c, key, lo)) { c.extra[key] = us; c.extra["tap"] = -1; lastDragDraw = now; redraw(c); runScript(c.evMove, c.name); }
        }
    } else if (pressed && down && held >= 0 && held < (int) page.comps.size() && page.comps[held].type == "slider") {
        Comp &c = page.comps[held];                          // dragging the knob
        if (now - lastDragDraw > 40 && sliderTo(c, x[0], y[0])) { lastDragDraw = now; keepTouched(c); redraw(c); runScript(c.evMove, c.name); }
    } else if (pressed && down && held >= 0 && held < (int) page.comps.size() && scrollable(page.comps[held])) {
        Comp &c = page.comps[held]; lastY = y[0];               // the finger drags the list / the text
        const int dy = y[0] - dragY0;
        if (abs(dy) > 8) dragged = true;
        if (dragged) {
            const int want = c.type == "sltext" ? constrain(dragS0 - dy, 0, (int) host.getInt("", c.name, "maxval_y")) : listWrap(c, dragS0 - dy);
            if (want != c.scroll && now - lastDragDraw > (c.type == "sltext" ? 30 : 40)) {   // (1.11.142) the text through the slab (1.11.143: and flipped to, one step a frame); a list as before
                const int r = c.type == "sltext" ? slideDrag(c, want) : 0;
                if (r == 0) { c.scroll = want; lastDragDraw = now; redraw(c); } else if (r > 0) lastDragDraw = now;
            }
        }
    } else if (up) {
        down = false; lastRelease = now; slideDone();         // (1.11.142: the slide text's slab given back)
        host.sys["tch2"] = lastX; host.sys["tch3"] = lastY; host.sys["tch0"] = 0; host.sys["tch1"] = 0;   // the curve page reads where the finger lifted
        if (held >= 0 && held < (int) page.comps.size()) {
            Comp &c = page.comps[held]; c.pressed = false;   // (a switch, dual-state button, checkbox or radio changed as the finger landed, above)
            if (c.type == "textselect") {
                if (!dragged) c.scroll = listWrap(c, floorDiv(lastY - listBandY(c) + c.scroll, listRowH(c)) * listRowH(c));   // a tap turns the wheel to that row
                listSnap(c);
            }
            if (c.type == "dual-state button" || c.type == "checkbox" || c.type == "switch" || c.type == "radio" || c.type == "textselect") keepTouched(c);   // (the page comes back with it)
            if (c.type == "button" || c.type == "dual-state button" || c.type == "checkbox" || c.type == "switch" || c.type == "radio" || c.type == "textselect") redraw(c);
            const int key = c.key, cid = c.id, idx = held; const std::string pgName = page.name, evRel = c.evRelease, nm = c.name;
            const bool combo = c.type == "combobox";
            if (evRel.find("=44<<8") != std::string::npos) picSoon();   // the Teensy's StartChooseImage: the chooser's frame now, its page in a moment
            runScript(evRel, nm);                             // (may load another page: c is not touched after this; 1.11.109: a Help button's subject is noted there, for the help page's Animation)
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
namespace ldrc { bool wifiSameName(const std::string &a, const std::string &b); }   // (LdrcWifi.h, which the WiFi page includes further down)
// (1.11.139, 28 Oct 2026) Joined, by the driver's own account. The library's WL_CONNECTED is set by its event task, and the
// door was seen SHUT for minutes while the web server answered on House and the door's network was House: the status it
// was judged by had gone stale after the Bluetooth pipe's stack came down and the WiFi joined again. The driver's record of
// the access point and an address of ours say whether we are joined; the network's name is compared as the WiFi page
// compares names (wifiSameName). /status "wifi" shows both accounts and both names, for the next time.
static bool wifiUpNow() {
    if (!radiosLive) return false;
    if (WiFi.status() == WL_CONNECTED) return true;
    wifi_ap_record_t ap; return esp_wifi_sta_get_ap_info(&ap) == ESP_OK && (uint32_t) WiFi.localIP() != 0;
}
static bool doorOpen() {
#ifdef LDRC_DOORS_OPEN
    return true;
#else
    return !doorSsid.empty() && wifiUpNow() && ldrc::wifiSameName(doorSsid, std::string(WiFi.SSID().c_str()));
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
static void banner(const char *msg, uint32_t ms = 2000);
// Open on the network we are on (and on no other), or shut. Remembered in the chip: the firmware that follows this
// one finds the door as it was left. (A bench build answers on every network whatever this says, but keeps it all
// the same: the door can be opened from the Mac BEFORE the transmitter updates itself to the published firmware.)
static bool doorSet(bool open) {
    if (open && !wifiUpNow()) return false;
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

static std::string psramJson();                        // (1.11.132) defined after the device headers (it names their buffers)
static std::string wifiDiagJson();                     // (1.11.147) wifi_device.h, included later: the access point, the IP, the drops and joins
static std::string iramJson();                         // (1.11.137) likewise
static bool filmProbe(const String &kind, int kb, uint32_t &us, char *extra, size_t extraN);   // (26 Oct evening, bench) src/film_device.h: a film played from the bench, stopped, its frames through the flip or not
static void webBegin() {
    web.on("/status", HTTP_GET, []() {                   // (the one page that answers when the workshop door is shut)
        char b[520]; snprintf(b, sizeof(b), "{\"fw\":\"" SCREEN_VERSION "\",\"door\":%s,\"door_kept\":%s,\"tx\":%d,\"flying\":%d,\"rx\":{\"phase\":%d,\"why\":%d,\"outcome\":%d,\"release\":\"%lX\",\"wanted\":\"%lX\",\"left\":%lu,\"flags\":%lu,\"age\":%ld},\"page\":\"%s\",\"id\":%d,\"cmds\":%lu,\"odd\":%lu,\"minheap\":%u,\"heap\":%u,\"psram\":%u,\"sd\":%d,\"touch\":%d,\"ip\":\"%s\",\"audio\":%d,\"boot\":%lu,\"up\":%lu}",
                 doorOpen() ? "true" : "false", doorSsid.empty() ? "false" : "true", txStatus, flyingNow(),
                 rxNews.phase, rxNews.why, rxNews.outcome, (unsigned long) rxNews.release, (unsigned long) rxNews.wanted, (unsigned long) rxNews.left, (unsigned long) rxNews.flags, rxNewsAny ? (long) ((millis() - rxNews.atMs) / 1000) : -1L,
                 page.name.c_str(), page.id, (unsigned long) cmdCount, (unsigned long) badCount, ESP.getMinFreeHeap(), ESP.getFreeHeap(), ESP.getFreePsram(), sdOk, touchOk, WiFi.localIP().toString().c_str(), audioId, (unsigned long) bootMs, (unsigned long) millis());
        std::string out = b;                                 // (1.11.3) the Bluetooth pipe's state, readable with the door shut
        out.pop_back(); out += ",\"ble\":" + bleStatusJson();
        out += ",\"rst\":" + std::to_string((int) esp_reset_reason());   // (1.11.7) why we last started: 1 power, 3 our own restart, 4 panic, 5/6/7 watchdogs, 9 brown-out
        out += ",\"stack\":{\"loop\":" + std::to_string((unsigned) uxTaskGetStackHighWaterMark(NULL)) + ",\"ble\":" + std::to_string(bleStackSpare()) + "}";   // (1.11.8) the least each task's stack has ever had to spare, in bytes
        out += ",\"largest\":" + std::to_string((unsigned) ESP.getMaxAllocHeap()) + ",\"rssi\":" + std::to_string((int) WiFi.RSSI());   // (1.11.11) the largest piece of free memory (a TLS connection wants ~45 kB), and the WiFi signal
        { std::string s = WiFi.SSID().c_str(), d = doorSsid; for (auto *t : {&s, &d}) for (auto &c : *t) if (c == '"' || c == '\\') c = '\'';
          out += ",\"wifi\":{\"st\":" + std::to_string((int) WiFi.status()) + ",\"up\":" + (wifiUpNow() ? "true" : "false") + ",\"ssid\":\"" + s + "\",\"door_ssid\":\"" + d + "\"" + wifiDiagJson() + "}"; }   // (1.11.139) the library's status (3 = joined) beside the driver's account, and the two names the door compares; (1.11.147) the access point, the IP, the drops and joins (wifi_device.h)
        out += ",\"board\":\"" + std::string(board->name) + "\",\"flash_mb\":" + std::to_string((unsigned) (flashChipBytes >> 20)) + ",\"image_mb\":" + std::to_string((unsigned) (flashImageBytes >> 20))
             + ",\"slot\":" + std::to_string((unsigned) boardSlotBytes()) + ",\"build\":\"" + (BUILD_FULL ? "full" : "standard") + "\"";   // (1.11.111) which board this is (its flash chip), what the firmware was built for, the slot the next firmware goes in
        out += ",\"crash\":" + crashJson();                     // (1.11.15) the last crash's summary from the core dump in flash, if there is one
        out += ",\"drawbad\":" + std::to_string((unsigned long) drawDropped);   // (1.11.140) drawing commands dropped as two run into one (bytes lost on the wire); their text at /odd
        { char q[340]; snprintf(q, sizeof(q), ",\"quiet\":{\"frames\":%lu,\"frame_us\":%lu,\"n\":%lu,\"late\":%lu,\"over\":%lu,\"wait_ms\":%lu,\"copy_us\":%lu,\"copy_max\":%lu,\"draw_us\":%lu,\"draw_max\":%lu,\"kept\":%lu,\"full\":%lu,\"warmed\":%lu,\"step_max\":%lu,\"stores\":%lu,\"store_max\":%lu}",
                                (unsigned long) frameEnds, (unsigned long) frameUs, (unsigned long) quietN, (unsigned long) quietLateN, (unsigned long) quietOverN, (unsigned long) quietWaitMs,
                                (unsigned long) quietCopyUs, (unsigned long) quietCopyMax, (unsigned long) quietDrawUs, (unsigned long) quietDrawMax,
                                (unsigned long) quietKeptN, (unsigned long) quietFullN, (unsigned long) quietWarmN, (unsigned long) quietStepMax, (unsigned long) quietStoreN, (unsigned long) quietStoreMax); out += q; }
        { char q[120]; snprintf(q, sizeof(q), ",\"dma\":{\"on\":%d,\"base_us\":%lu,\"late\":%lu,\"missed\":%lu}", dmaWatchOn ? 1 : 0, (unsigned long) dmaBaseUs, (unsigned long) dmaLateAll, (unsigned long) dmaMissedAll); out += q; }   // (25 Oct) since boot
        out += ringStatusJson();
        out += ","; dmaCopyJson(out);                      // (1.11.126) the DMA copy: on, copies, rows, timeouts, the panel channel's priority
        out += ","; xipJson(out);                          // (1.11.131) the code in the PSRAM: mode, pages, ms, strikes, why
        out += ","; stripJson(out);                        // (26 Oct evening) the strips: on, frames, fills, late
        out += ","; out += iramJson();
        out += ",\"sd_gone\":" + std::to_string((unsigned long) sdGoneMs);   // (1.11.138) when the card stopped answering and was given up (0: never)
        out += ","; out += packJson();                    // (1.11.138) the pack: pages, fonts and sounds in the chip's flash (16 MB boards)                    // (1.11.137) the chip's own RAM and our holders of it
        out += ","; out += psramJson();                   // (1.11.132) the PSRAM's holders: largest free block, resident pictures of the most allowed, the floor's evictions, the layer, the model picture, the film
        out += ","; out += tlsJson();                     // (1.11.146) the secure connection's memory: from the PSRAM, held now and at most, refused
        { char q[200]; snprintf(q, sizeof(q), ",\"film\":{\"pictures\":%lu,\"skipped\":%lu,\"decode_us\":%lu,\"decode_max\":%lu,\"fade_steps\":%lu,\"fade_max\":%lu}",
                                (unsigned long) filmPictures, (unsigned long) filmSkipped, (unsigned long) filmDecodeUs, (unsigned long) filmDecodeMax, (unsigned long) filmFadeSteps, (unsigned long) filmFadeMax); out += q; }   // (1.11.85) the last film: pictures shown, missed, decode time   // (1.11.67) the front screen's switch in the panel's quiet time; (1.11.68) shown as kept, drawn whole, drawn ahead, the longest piece
        { char q[480]; snprintf(q, sizeof(q), ",\"flip\":{\"why\":\"%s\",\"n\":%lu,\"shown\":%u,\"compose_max\":%lu,\"wait_max\":%lu,\"syncs\":%lu,\"rests\":%lu,\"rot\":%lu,\"stale\":%d,\"ensured\":%lu,\"fspare\":%d,\"fshown\":%d,\"last\":{\"draw\":%lu,\"compose\":%lu,\"shown\":%lu,\"sd\":%lu,\"parse\":%lu,\"pre\":%lu,\"bg\":%lu,\"comps\":%lu,\"text\":[%lu,%lu],\"pic\":[%lu,%lu],\"other\":[%lu,%lu]}}",
                                flipWhy, (unsigned long) flipDoneN, (unsigned) flipShown, (unsigned long) flipComposeMax, (unsigned long) flipWaitMax, (unsigned long) flipSyncN, (unsigned long) paceRests,
                                (unsigned long) flipRotateN, (int) __builtin_popcountll(canvasStale), (unsigned long) canvasEnsureN, (int) spareHoldsFlight, (int) shownIsFlight, (unsigned long) pageDrawMs, (unsigned long) pageComposeMs, (unsigned long) pageShownMs, (unsigned long) pageSdUs, (unsigned long) pageParseUs, (unsigned long) pagePreUs, (unsigned long) pageBgUs, (unsigned long) pageCompsUs,
                                (unsigned long) pageTextN, (unsigned long) pageTextUs, (unsigned long) pagePicN, (unsigned long) pagePicUs, (unsigned long) pageOtherN, (unsigned long) pageOtherUs); out += q; }   // (1.11.115) the twin's page flip: on or why not, flips, the longest compose (us) and wait (ms)
        { std::string l = sysLast(); for (size_t i = 0; i < l.size(); ++i) if (l[i] == '"' || l[i] == '\\') l[i] = '\''; out += ",\"sys\":\"" + l + "\"}"; }   // (1.11.5) the system's last error line
        web.send(200, "application/json", out.c_str());
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
        char b[600]; snprintf(b, sizeof(b), "{\"cmds\":%lu,\"handle_us\":%lu,\"presents\":%lu,\"present_us\":%lu,\"present_px\":%lu,\"fill_full\":%lu,\"fill_inc\":%lu,\"skipped\":%lu,\"rx_max\":%d,\"loop_max_ms\":%lu,\"odd\":%lu,\"frame_ends\":%lu,\"frame_us\":%lu}",
                              (unsigned long) perfCmds, (unsigned long) perfHandleUs, (unsigned long) perfPresentN, (unsigned long) perfPresentUs, (unsigned long) perfPresentPx,
                              (unsigned long) perfFillFull, (unsigned long) perfFillInc, (unsigned long) perfSkipped, perfRxMax, (unsigned long) perfLoopMaxMs, (unsigned long) badCount,
                              (unsigned long) frameEnds, (unsigned long) frameUs);   // (frame_ends grows 23 a second once the hook works, 34.6 on the twin; frame_us ~43090, ~28920 on the twin)
        perfCmds = perfHandleUs = perfPresentN = perfPresentUs = perfPresentPx = perfFillFull = perfFillInc = perfSkipped = perfLoopMaxMs = 0; perfRxMax = 0;
        std::string out = b; out.pop_back();
        { char s[160]; snprintf(s, sizeof(s), ",\"slide\":{\"n\":%lu,\"flips\":%lu,\"waits\":%lu,\"us\":%lu,\"max_us\":%lu,\"debt_us\":%lu,\"fills\":%lu,\"fill_us\":%lu}", (unsigned long) slideN, (unsigned long) slideFlipN, (unsigned long) slideWaitN, (unsigned long) slideUs, (unsigned long) slideUsMax, (unsigned long) slideDebtUs, (unsigned long) slideFillN, (unsigned long) slideFillUs); out += s; slideN = slideFlipN = slideWaitN = slideUs = slideUsMax = slideDebtUs = slideFillN = slideFillUs = 0; }   // (1.11.142) the slide text's drag steps: drawn, flipped to (the twin), put off for a flip in flight, their time, the spare's debt
        out += ",\"max_us\":{";
        for (int i = 0; i < 7; ++i) { char e[40]; snprintf(e, sizeof(e), "%s\"%s\":%lu", i ? "," : "", phaseName[i], (unsigned long) phaseMax[i]); out += e; phaseMax[i] = 0; }
        out += "},";
        out += dmaPerfJson();                              // (25 Oct) the panel's DMA: frames met late = the picture slipped
        out += ringPerfJson();
        out += slipwPerfJson();
        { char e[120]; snprintf(e, sizeof(e), ",\"wb\":{\"pieces\":%lu,\"slow\":%lu,\"cy_min\":%lu,\"cy_max\":%lu,\"clean_cy\":%lu}", (unsigned long) wbPieces, (unsigned long) wbSlow, (unsigned long) (wbCyMin == 0xFFFFFFFF ? 0 : wbCyMin), (unsigned long) wbCyMax, (unsigned long) wbCleanCy); out += e; wbPieces = wbSlow = 0; wbCyMin = 0xFFFFFFFF; wbCyMax = 0; }   // (25 Oct 21:00) the write-back pieces this window                            // (25 Oct evening) the slips by what the loop was doing (busy_what.h)                             // (25 Oct evening) the ring this window: re-syncs, skips, the DMA's furthest descriptor, both latenesses' worst, the EOF offsets' span
        { char e[60]; snprintf(e, sizeof(e), ",\"nvs\":{\"writes\":%lu,\"max_us\":%lu}", (unsigned long) nvsN, (unsigned long) nvsMaxUs); out += e; nvsN = nvsMaxUs = 0; }
        { char e[120]; snprintf(e, sizeof(e), ",\"slips\":{\"n\":%lu,\"max_us\":%lu,\"sum_us\":%lu,\"huge\":%lu,\"gap_base\":%lu}", (unsigned long) dmaSlips, (unsigned long) dmaSlipMax, (unsigned long) dmaSlipSum, (unsigned long) dmaHuge, (unsigned long) dmaGapBase); out += e; dmaSlips = dmaSlipMax = dmaSlipSum = dmaHuge = 0; }   // (25 Oct) the slip counter (dma_watch.h), this window; huge (1.11.128): frames the panel was held for 20 ms and more
        out += "}";
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
    doorOn("/stall", HTTP_POST, []() {                  // (25 Oct, bench) a KNOWN stall of the panel, to calibrate /perf "dma": kind=psram (kb of PSRAM written at full speed), nvs (one int written), read (kb off the card into the PSRAM, paced)
        const String kind = web.hasArg("kind") ? web.arg("kind") : "psram";
        const int kb = web.hasArg("kb") ? web.arg("kb").toInt() : 256;
        uint32_t us = 0; bool ok = true;
        const uint32_t slips0 = dmaSlipsAll, huge0 = dmaHugeAll; dmaProbePos = 0; dmaProbeFr = 0; dmaProbeMax = 0; char extra[300] = "";   // (26 Oct) what the panel's DMA saw during the probe: slips over the bar, frames held for 20 ms and more (huge), the excess summed over its frames, the worst frame
        if (kind == "psram") { uint8_t *m = (uint8_t *) ps_malloc((size_t) kb * 1024); if (!m) ok = false; else { const uint32_t t0 = micros(); memset(m, 0x55, (size_t) kb * 1024); us = micros() - t0; free(m); } }
        else if (kind == "nvs") { const uint32_t t0 = micros(); prefs.putInt("stallt", (int) millis()); us = micros() - t0; }
        else if (kind == "isr") { dmaSpinUs = (uint32_t) kb; us = (uint32_t) kb; }
        else if (kind == "slipwus") { dmaSlipwUs = (int32_t) kb; us = (uint32_t) kb; }   // the slip-by-cause counter's bar (dma_watch.h)   // the next frame's restart held back this many us (dma_watch.h)
        else if (kind == "ring") { ringSet(kb != 0); ok = (ringOn || ringArm) == (kb != 0); }   // the hardware's chaining of the frames on (1) or off (0): the A/B (frame_ring.h)
        else if (kind == "heal") { ringHealNow(); ok = ringOn; }   // the DMA started again in step, now (frame_ring.h)
        else if (kind == "skip") { benchSkip = (uint32_t) kb; us = benchSkip; }   // the bench switches (see benchSkip)
        else if (kind == "wbpiece") { if (kb >= 32 && kb <= 65536) wbPieceBytes = (uint32_t) kb; us = wbPieceBytes; }   // the gentle write-back's piece (src/psram_pace.h)
        else if (kind == "wbgap") { if (kb >= 0 && kb <= 1000) wbGapUs = (uint32_t) kb; us = wbGapUs; }
        else if (kind == "wbclean") { wbCleanCy = (uint32_t) kb; us = wbCleanCy; }   // the adaptive gap's bar in cycles (0 = a breath after every piece)
        else if (kind == "wbtime") { const uint32_t keep = wbPieceBytes; if (kb >= 32) wbPieceBytes = (uint32_t) kb; uint16_t *fb = flipOk ? flipFb[flipCanvas] : pageFb; if (!fb) ok = false; else { const uint32_t t0 = micros(); wbPaced((uint32_t) fb, W * H * 2); us = micros() - t0; } wbPieceBytes = keep; }   // the canvas (clean, mostly) written back whole in pieces of kb bytes: the cost of a call
        else if (kind == "rotate") { const uint32_t t0 = micros(); fillMemo.valid = false; drawPage(); us = micros() - t0; }   // the page drawn again and rotated to: no parsing, no card
        else if (kind == "fill") { const uint32_t t0 = micros(); gfx->fillRect(36, 36, 360, 360, 0); us = micros() - t0; }   // the bench's fill alone (the canvas)
        else if (kind == "present" || kind == "presentnowb") { benchNoWb = kind == "presentnowb"; const uint32_t t0 = micros(); present(0, 0, W, kb > 0 ? min(kb, (int) H) : H); us = micros() - t0; benchNoWb = false; }   // the bench's copy to the live buffers: kb = rows; nowb = without the cache write-backs
        else if (kind == "wbdirty" || kind == "wbgentle") {   // N kB written then written back as copyRows does, 8 rows (12.8 kB) at a time - or in 256-byte pieces with 8 us between (gentle)
            uint8_t *m = (uint8_t *) ps_malloc((size_t) kb * 1024); if (!m) ok = false;
            else {
                const uint32_t t0 = micros();
                for (size_t off = 0; off < (size_t) kb * 1024; off += 12800) {
                    const size_t n = std::min((size_t) 12800, (size_t) kb * 1024 - off);
                    memset(m + off, (int) off, n);
                    if (kind == "wbdirty") Cache_WriteBack_Addr((uint32_t) (m + off), (uint32_t) n);
                    else wbPaced((uint32_t) (m + off), (uint32_t) n);
                    delayMicroseconds(300);
                }
                us = micros() - t0; free(m);
            }
        }
        else if (kind == "mmap") {                      // N kB of the running firmware read THROUGH the cache, a line at a time: what cold code looks like to the bus the PSRAM shares
            const esp_partition_t *p = esp_ota_get_running_partition(); const void *map = nullptr; spi_flash_mmap_handle_t h = 0;
            const size_t n = std::min((size_t) kb * 1024, (size_t) p->size);
            if (!p || esp_partition_mmap(p, 0, n, SPI_FLASH_MMAP_DATA, &map, &h) != ESP_OK) ok = false;
            else { const volatile uint8_t *m = (const volatile uint8_t *) map; uint32_t sum = 0; const uint32_t t0 = micros(); for (size_t i = 0; i < n; i += 32) sum += m[i]; us = micros() - t0; spi_flash_munmap(h); if (sum == 0xFFFFFFFF) ok = false; }
        }
        else if (kind == "wb") { uint8_t *m = (uint8_t *) ps_malloc((size_t) kb * 1024); if (!m) ok = false; else { memset(m, 0x33, (size_t) kb * 1024); const uint32_t t0 = micros(); Cache_WriteBack_Addr((uint32_t) m, (uint32_t) kb * 1024); us = micros() - t0; free(m); } }   // a cache write-back of N kB in one call (the page draw's, 25 kB a piece)
        else if (kind == "nvsq") { nvsQuiet([&] { prefs.putInt("stallt", (int) millis()); }); us = nvsMaxUs; }
        else if (kind == "read") { File f = SD.open("/hmi/pic/1.565"); uint8_t *m = (uint8_t *) ps_malloc((size_t) kb * 1024); if (!f || !m) ok = false; else { const uint32_t t0 = micros(); sdReadPaced(f, m, (size_t) kb * 1024); us = micros() - t0; } if (m) free(m); if (f) f.close(); }
        else if (kind == "copy") { uint8_t *a = (uint8_t *) ps_malloc((size_t) kb * 1024), *c = (uint8_t *) ps_malloc((size_t) kb * 1024); if (!a || !c) ok = false; else { memset(a, 1, (size_t) kb * 1024); const uint32_t t0 = micros(); memcpy(c, a, (size_t) kb * 1024); us = micros() - t0; } if (a) free(a); if (c) free(c); }   // PSRAM to PSRAM at full speed
        else if (kind == "flash") { uint8_t *m = (uint8_t *) heap_caps_malloc(4096, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT); const esp_partition_t *p = esp_ota_get_running_partition(); if (!m || !p) ok = false; else { const uint32_t t0 = micros(); for (size_t off = 0; off + 4096 <= (size_t) kb * 1024 && off + 4096 <= p->size; off += 4096) esp_partition_read(p, off, m, 4096); us = micros() - t0; } if (m) free(m); }   // the flash read straight (not through the cache), 4 kB a transaction: the bus the PSRAM shares
        else if (kind == "dmacopy") { prefs.putInt("dmacopy", kb != 0 ? 1 : 0); ok = dmaCopyProbe(kind, kb, us, extra, sizeof extra); }   // the DMA copy on/off, now and at the next start
        else if (kind == "xip") { const int want = kb < -1 ? -1 : kb > 2 ? 2 : kb; prefs.putInt("xip", want); prefs.putInt("xipbad", 0); us = xipMode; snprintf(extra, sizeof extra, ",\"want\":%d,\"now\":\"%s\"", want, xipWhy); }   // (1.11.131) the code in the PSRAM at the NEXT start: -1 the board's choice, 0 off, 1 the code, 2 the code and its constants (the strikes forgiven)
        else if (kind == "mmu") { us = xipMode; xipMmuWords(kb > 0 ? kb : 32, extra, sizeof extra); }   // (1.11.131) the MMU's first N entries, hex (8xxx = a PSRAM page)
        else if (kind == "strips") { const int want = kb < -1 ? -1 : kb > 1 ? 1 : kb; prefs.putInt("strips", want); prefs.putInt("stripbad", 0); us = stripOn; snprintf(extra, sizeof extra, ",\"want\":%d,\"why\":\"%s\"", want, stripWhy); }   // (1.11.134) the strips at the next start: -1 the board's choice, 0 off, 1 on (the strikes forgiven)
        else if (kind == "film" || kind == "filmstop" || kind == "filmflip") ok = filmProbe(kind, kb, us, extra, sizeof extra);   // (26 Oct evening) film&kb=N plays the list's Nth film on the bench, filmstop ends it (us = pictures shown), filmflip&kb=1 sends its frames through the flip
        else if (kind == "pacepx") { if (kb >= 400 && kb <= 64000) paceQuantumPx = (uint32_t) kb; us = paceQuantumPx; }   // (26 Oct) the pacing's burst between rests, in pixels (src/psram_pace.h)
        else if (kind == "sync") { flipSyncOn = kb != 0; flipStaleRow = 0; us = flipSyncOn; }   // (26 Oct) the spare's eager catch-up after a flip: 1 = as before, 0 = left stale until the next compose
        else if (kind == "rest") { if (kb >= 0 && kb <= 20000) paceRestOverride = (uint32_t) kb; us = paceRestOverride ? paceRestOverride : board->psramRestUs; }   // (26 Oct) the pacing's rest after each quantum, us (0 = the board's)
        else ok = dmaCopyProbe(kind, kb, us, extra, sizeof extra);   // (26 Oct) m2m, m2mp, m2mrows, wbnop, lcdpri, dcstat - or an unknown kind (src/dma_copy.h)
        char b[460]; snprintf(b, sizeof b, "{\"kind\":\"%s\",\"kb\":%d,\"us\":%lu,\"ok\":%d,\"slips\":%lu,\"huge\":%lu,\"pos\":%lu,\"fr\":%lu,\"dmax\":%ld%s}", kind.c_str(), kb, (unsigned long) us, ok ? 1 : 0,
                 (unsigned long) (dmaSlipsAll - slips0), (unsigned long) (dmaHugeAll - huge0), (unsigned long) dmaProbePos, (unsigned long) dmaProbeFr, (long) dmaProbeMax, extra);
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
            if (path.startsWith("/hmi/") || path.startsWith("/images/")) SD.remove("/update/screen_have.txt");
            if (packCovers(path.c_str())) packMarkStale();   // (1.11.138) the pack follows at the next start   // the next install reads and checks every file ("Check for update")
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
    doorOn("/coredump", HTTP_GET, []() {                   // (1.11.15) the whole core dump partition, for espcoredump on the Mac
        const esp_partition_t *p = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_COREDUMP, NULL);
        if (!p) { web.send(404, "text/plain", "no core dump partition"); return; }
        web.setContentLength(p->size); web.send(200, "application/octet-stream", "");
        static uint8_t buf[1024];
        for (uint32_t at = 0; at < p->size; at += sizeof buf) { if (esp_partition_read(p, at, buf, sizeof buf) != ESP_OK) break; web.sendContent((const char *) buf, sizeof buf); }
    });
    doorOn("/pack", HTTP_GET, []() { web.send(200, "application/json", ("{" + packJson() + "}").c_str()); });   // (1.11.138) the pack's state
    doorOn("/pack/build", HTTP_POST, []() {               // (1.11.138) the pack built afresh from the card: at the next start, which this is
        packMarkStale();
        web.send(200, "text/plain", "the pack is marked stale: the screen restarts and copies the card's pages, fonts and sounds into the chip\n");
        flushOut(); delay(200); ESP.restart();
    });
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
        for (int y = 0; y < H; ++y) { if (dcTx) Cache_Invalidate_Addr((uint32_t) (fb + y * W), W * 2); client.write((const uint8_t *) (fb + y * W), W * 2); if ((y & 7) == 7) breathe(); }   // (1.11.126: rows the DMA wrote - the cache's copy may be stale)
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
        for (int pass = 0; pass < 3; ++pass) {              // the card's own folder, then mod, then banks56 (1.11.98)
            const std::string from = pass == 1 ? folder + "/mod" : pass == 2 ? folder + "/banks56" : folder, to = pass == 1 ? "/mod/" : pass == 2 ? "/banks56/" : "/";
            File d = SD.open(from.c_str());
            if (d && d.isDirectory()) {
                File f;
                while ((f = d.openNextFile())) {
                    const std::string name = f.name(); const bool dir = f.isDirectory(); f.close();
                    // Only the models and the settings: models.dat, and the model files (*.MOD). Not the logs (a log put
                    // back would take the place of the log as it is now), not a half file (*.part), not a copy moved aside.
                    const bool wanted = pass == 1 ? endsWith(name, ".mod") : pass == 2 ? endsWith(name, ".b56") : (name.size() == 10 && endsWith(name, "models.dat"));
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
        if (sysN) { out += "--- the system's own lines ---\n"; out += sysText(); }     // (1.11.5)
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
    // (1.11.33) The pilot's look, to copy from one transmitter to another: the six defined screens and the one in use, the
    // themes, the background. GET gives it as key=value lines; POST the same lines back on the other screen, which keeps
    // them and restarts to show them (Malcolm, 7 Oct: "copy all defined screens so that I need not set them all up again").
    static const char *LOOK_KEYS[] = { "theme", "flight", "flight2", "flight3", "flight4", "flight5", "flight6" };
    doorOn("/look", HTTP_GET, []() {
        std::string out;
        for (const char *k : LOOK_KEYS) out += std::string(k) + "=" + prefs.getString(k, "").c_str() + "\n";
        out += "flightSlot=" + std::to_string(prefs.getInt("flightSlot", 0)) + "\n";
        out += "bg=" + std::to_string(prefs.getInt("bg", 1)) + "\n";
        web.send(200, "text/plain", out.c_str());
    });
    doorOn("/look", HTTP_POST, []() {
        const std::string body = web.arg("plain").c_str();
        int kept = 0; size_t at = 0;
        while (at < body.size()) {
            size_t nl = body.find('\n', at); if (nl == std::string::npos) nl = body.size();
            std::string line = body.substr(at, nl - at); at = nl + 1;
            if (!line.empty() && line.back() == '\r') line.pop_back();
            const size_t eq = line.find('='); if (eq == std::string::npos) continue;
            const std::string key = line.substr(0, eq), val = line.substr(eq + 1);
            bool known = false; for (const char *k : LOOK_KEYS) if (key == k) known = true;
            if (known) { if (val.empty()) { if (prefs.isKey(key.c_str())) prefs.remove(key.c_str()); } else prefs.putString(key.c_str(), val.c_str()); ++kept; }
            else if (key == "flightSlot" || key == "bg" || key == "ring") { prefs.putInt(key.c_str(), atoi(val.c_str())); ++kept; }
        }
        if (!kept) { web.send(400, "text/plain", "nothing I know in that"); return; }
        web.send(200, "text/plain", (std::to_string(kept) + " settings kept; restarting to show them").c_str());
        blog("look", std::to_string(kept) + " settings came from another transmitter");
        delay(200); ESP.restart();
    });
    doorOn("/door", HTTP_POST, []() {                   // /door?on=1 : open on the network we are on, and remembered; /door?on=0 : shut (and this was the last request to be answered)
        const bool on = web.arg("on") != "0";
        if (!doorSet(on)) { web.send(409, "text/plain", "not on a network"); return; }
        web.send(200, "text/plain", on ? ("open on " + doorSsid).c_str() : "shut");
    });
    updWeb();
    wifiWeb(); cliWeb();
    picWeb();
    bleWeb();
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
static const size_t RING = 262144;                      // 5.9 s of audio ahead of the DMA (1.11.37: every clip fits whole, so a stall of the main loop - a page and its picture loading from the card - cannot starve the speaker; was 1.5 s)
static const int FRAMES = 256;                          // one DMA buffer
static uint8_t *audioRing = nullptr;
#include "audio_ring.h"                                 // (1.11.95) the ring's two ends, each written by one core: the stop/start race is gone
static ldrcring::Ends ringEnds;                         // head: loop() writes; tail: the task
static volatile bool audioDraining = false;             // nothing more is coming: play the tail, padded
static File audioFile; static bool audioPlaying = false, audioLoop = false;
static uint32_t audioDataStart = 0, audioDataSize = 0, audioDataLeft = 0, audioRate = 22050;
// (1.11.93) A film's sound may be IMA ADPCM (src/ima_adpcm.h): a quarter of the bytes to fetch. Made 16-bit here a block at
// a time, into the same ring. audioBlock 0: 16-bit samples as they are (every clip, and the films before 1.11.93).
#include "ima_adpcm.h"
static uint32_t audioBlock = 0, audioBlockSamples = 0, audioSkip = 0;   // a block's bytes and samples; samples not to play (a start part way into a block)
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
// (1.11.133) The clip cache fills to CLIP_BUDGET (1.5 MB) while the screen is idle (audioWarm): with the firmware's code in the PSRAM
// (1.11.131) that left a twin at 0.4 MB free. It is the PSRAM's most elastic part, so the floor (loop) and psMallocRoom let its
// least recently used clip go first. Never while a clip plays from memory: curClip points into the vector.
static bool clipDropOne() {
    if (curClip || audioPlaying || clips.empty()) return false;
    int old = 0;
    for (size_t i = 1; i < clips.size(); ++i) if (clips[i].used < clips[old].used) old = (int) i;
    free(clips[old].data); clipBytes -= clips[old].len; clips.erase(clips.begin() + old); return true;
}
static bool wavOpenPath(const char *path, uint32_t &rate, bool adpcmOk = false);
static bool wavOpen(int id, uint32_t &rate) {           // leaves audioFile at the samples; sets audioDataStart/Size/Left
    char path[32]; snprintf(path, sizeof(path), "/hmi/audio/%d.wav", id);
    return wavOpenPath(path, rate);
}
static bool wavOpenPath(const char *path, uint32_t &rate, bool adpcmOk) {   // (1.11.85: a film's sound too; 1.11.93: adpcmOk, a film's may be IMA ADPCM)
    audioFile = assetOpen(path); if (!audioFile) return false;   // (1.11.138) the pack's copy when there is one
    uint8_t h[12]; if (audioFile.read(h, 12) != 12 || memcmp(h, "RIFF", 4) || memcmp(h + 8, "WAVE", 4)) { audioFile.close(); return false; }
    rate = 22050; bool haveData = false; uint32_t tag = 1, chans = 1, bits = 16, align = 2;
    audioBlock = 0; audioBlockSamples = 0; audioSkip = 0;
    while (audioFile.available()) {
        uint8_t ch[8]; if (audioFile.read(ch, 8) != 8) break;
        const uint32_t sz = ch[4] | (ch[5] << 8) | (ch[6] << 16) | ((uint32_t) ch[7] << 24);
        if (!memcmp(ch, "fmt ", 4)) {
            uint8_t f[16]; audioFile.read(f, 16); rate = f[4] | (f[5] << 8) | (f[6] << 16) | ((uint32_t) f[7] << 24);
            tag = f[0] | (f[1] << 8); chans = f[2] | (f[3] << 8); align = f[12] | (f[13] << 8); bits = f[14] | (f[15] << 8);
            if (sz > 16) audioFile.seek(audioFile.position() + sz - 16);
        }
        else if (!memcmp(ch, "data", 4)) { audioDataStart = audioFile.position(); audioDataSize = audioDataLeft = sz; haveData = true; break; }
        else audioFile.seek(audioFile.position() + sz + (sz & 1));
    }
    if (haveData && tag == 0x11) {                          // IMA ADPCM: a film's, mono, 4 bits, blocks of up to 1 kB; else not played (never as noise)
        if (adpcmOk && chans == 1 && bits == 4 && align > 4 && align <= 1024) { audioBlock = align; audioBlockSamples = ldrcaudio::imaSamples(align); }
        else haveData = false;
    }
    if (!haveData) audioFile.close();
    return haveData;
}
static void audioTask(void *) {
    static int16_t frame[FRAMES * 2];
    for (;;) {
        size_t avail = ldrcring::begin(ringEnds, RING);  // (1.11.95: a stop from loop() is acted on here, by this task alone)
        const bool tail = audioDraining && avail > 0;
        if (avail < (size_t) FRAMES * 2 && !tail) { vTaskDelay(pdMS_TO_TICKS(3)); continue; }
        int n = 0;
        while (n < FRAMES && avail >= 2) {
            const size_t t = ringEnds.tail;
            int16_t v = (int16_t) (audioRing[t] | (audioRing[(t + 1) % RING] << 8));
            ldrcring::took(ringEnds, RING, 2); avail -= 2;
            if (board->tone) v = toneShape(v);               // (1.11.116) the twin's speaker: less bass, more top (Malcolm, 24 Oct: "sounds bassy ... not enough top")
            v = limit16(((int32_t) v * audioGain) >> 10);
            frame[2 * n] = v; frame[2 * n + 1] = v; n++;
        }
        for (; n < FRAMES; ++n) { frame[2 * n] = 0; frame[2 * n + 1] = 0; }   // a clip's last buffer: padded with silence, sent now
        size_t written = 0; i2s_write(I2S_PORT, frame, FRAMES * 4, &written, portMAX_DELAY);
    }
}
// (1.11.116) A tone shape for the twin, per sample at 22050 Hz, in fixed point: the clips carry the CrowPanel's mastering
// (bass lifted, top cut, for its small speaker - 1.4.7). The twin's speaker has bass of its own, so here the bass below
// ~200 Hz comes down 6 dB (half the one-pole low-passed part taken away) and the top above ~2.5 kHz goes up 4 dB (six tenths
// of the high-passed part added). Headroom: the boost is on the top only, and limit16 follows.
static int16_t toneShape(int16_t x) {
    static int32_t lp1 = 0, lp2 = 0;                       // x256
    const int32_t xs = (int32_t) x << 8;
    lp1 += ((xs - lp1) * 14) >> 8;                         // one pole at ~200 Hz (a = 0.055)
    int32_t y = xs - ((lp1 * 179) >> 8);                   // bass -10 dB (Malcolm on -6: "a bit better! More in the same direction")
    lp2 += ((y - lp2) * 131) >> 8;                         // one pole at ~2.5 kHz (a = 0.51)
    y += ((y - lp2) * 461) >> 8;                           // top +9 dB (on +6.5: "a little bit more top")
    y = (y * 180) >> 8;                                    // -3 dB overall: room for the louder top before limit16
    return limit16(y >> 8);
}
static void audioBegin() {
    i2s_config_t cfg = {};
    cfg.mode = (i2s_mode_t) (I2S_MODE_MASTER | I2S_MODE_TX); cfg.sample_rate = 22050; cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
    cfg.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT; cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
    cfg.dma_buf_count = 8; cfg.dma_buf_len = FRAMES; cfg.use_apll = false; cfg.tx_desc_auto_clear = true; cfg.intr_alloc_flags = 0;
    if (i2s_driver_install(I2S_PORT, &cfg, 0, nullptr) != ESP_OK) return;
    i2s_pin_config_t pins = {}; pins.mck_io_num = I2S_PIN_NO_CHANGE; pins.bck_io_num = board->i2sBclk; pins.ws_io_num = 18; pins.data_out_num = 17; pins.data_in_num = I2S_PIN_NO_CHANGE;   // (1.11.111) the bit clock is the board's: IO42 on the CrowPanel, IO0 on the twin
    i2s_set_pin(I2S_PORT, &pins);
    i2s_zero_dma_buffer(I2S_PORT);
    audioRing = (uint8_t *) ps_malloc(RING);
    if (audioRing) xTaskCreatePinnedToCore(audioTask, "audio", 4096, nullptr, 3, nullptr, 0);
}
static void audioStop() {
    if (audioFile) audioFile.close();
    audioPlaying = false; audioId = -1; curClip = nullptr; audioDraining = false; audioBlock = 0; audioSkip = 0;
    if (capture) { free(capture); capture = nullptr; }
    ldrcring::stop(ringEnds);                             // (1.11.95) a note for the task: it moves its own tail (loop() set head = tail here, and lost the race once)
}
static void ringPush(const uint8_t *src, size_t n) { ldrcring::push(ringEnds, audioRing, RING, src, n); }
static void ringPushSamples(const int16_t *s, uint32_t n) {   // (1.11.93) decoded samples, less those a start part way into a block leaves out
    const uint32_t skip = std::min(audioSkip, n); audioSkip -= skip;
    if (n > skip) ringPush((const uint8_t *) (s + skip), (size_t) (n - skip) * 2);
}
// (1.11.93) An IMA ADPCM block off the card, into the ring as 16-bit samples. False: the card or the block failed
static bool audioFillBlock(uint8_t *tmp) {
    const size_t want = std::min((size_t) audioBlock, (size_t) audioDataLeft);
    const int got = audioFile.read(tmp, want);
    if (got < 4 || (size_t) got != want) return false;
    audioDataLeft -= got;
    ldrcaudio::Ima ima; int16_t first;
    if (!ima.head(tmp, first)) return false;
    ringPushSamples(&first, 1);
    int16_t out[256];                                       // (a block's body in pieces: 128 bytes are 256 samples)
    for (int at = 4; at < got; at += 128) { const int n = std::min(128, got - at); ima.body(tmp + at, (size_t) n, out); ringPushSamples(out, (uint32_t) n * 2); }
    return true;
}
static void audioFill() {                               // called from loop(): keep the ring topped up
    Busy busy_(BUSY_AUDIO);
    if (!audioPlaying || !audioRing) return;
    const size_t used = ldrcring::used(ringEnds, RING), space = ldrcring::space(ringEnds, RING);
    if (curClip) {                                       // from memory: everything there is room for, at once
        if (curPos >= curClip->len) { if (audioLoop) curPos = 0; else { audioDraining = true; if (used == 0) audioStop(); } return; }
        size_t n = min(space, (size_t) (curClip->len - curPos)); if (!n) return;
        // (1.11.120) All of it, as before (a stall of the loop must not starve the speaker: the ring holds 5.9 s), but in 8 kB
        // pieces with the pace's rests between: one memcpy of a whole clip within the PSRAM slipped the twin's picture at
        // every announcement's start.
        while (n) { const size_t piece = min(n, (size_t) 8192); ringPush(curClip->data + curPos, piece); curPos += piece; n -= piece; psramPace((uint32_t) piece); }
        return;
    }
    if (audioDataLeft == 0) {
        if (capture && captureLen == audioDataSize) { clipAdd(audioId, capture, captureLen); capture = nullptr; }   // the copy is complete: keep it for next time
        if (audioLoop) { audioFile.seek(audioDataStart); audioDataLeft = audioDataSize; return; }
        audioDraining = true; if (used == 0) audioStop(); return;
    }
    if (space < 4096) return;
    static uint8_t tmp[4096];
    if (audioBlock) {                                       // (1.11.93) IMA ADPCM: up to two blocks a call (each some 93 ms of sound)
        for (int b = 0; b < 2 && audioDataLeft > 0; ++b) {
            if (ldrcring::space(ringEnds, RING) < audioBlockSamples * 2) return;
            if (!audioFillBlock(tmp)) { audioStop(); return; }
        }
        return;
    }
    const size_t want = min((size_t) 4096, min(space, (size_t) audioDataLeft));
    const int got = audioFile.read(tmp, want);
    if (got <= 0) { audioStop(); return; }
    audioDataLeft -= got; ringPush(tmp, got);
    if (capture) { memcpy(capture + captureLen, tmp, got); captureLen += got; }
    psramPace((uint32_t) got);                            // (1.11.120: the ring and the copy are both in the PSRAM)
}
static void audioStart(int id, bool loopIt) {
    audioStop();
    if (!audioRing) return;
    audioLoop = loopIt; audioId = id;
    if (Clip *c = clipFind(id)) { curClip = c; curPos = 0; audioPlaying = true; audioFill(); return; }
    uint32_t rate;
    if (!assetsOk() || !wavOpen(id, rate)) { audioId = -1; return; }
    if (rate != audioRate) { i2s_set_sample_rates(I2S_PORT, rate); audioRate = rate; }
    // (1.11.37) A clip not yet in memory is read WHOLE before a sample of it is played, and kept. It used to stream from
    // the card as the main loop found time, and "Model memory matched" (56 kB, above the size the idle warming keeps)
    // came out broken up: the loop was busy loading the front page and the model's picture from the same card at that
    // very moment (Malcolm, 8 Oct). The read takes some tens of milliseconds, once.
    if (audioDataSize <= CLIP_BUDGET / 2) {
        clipMakeRoom(audioDataSize);
        uint8_t *buf = (uint8_t *) psMallocRoom(audioDataSize);
        if (buf) {
            uint32_t got = 0;
            while (got < audioDataSize) { const int n = audioFile.read(buf + got, min((uint32_t) 4096, audioDataSize - got)); if (n <= 0) break; got += n; psramPace((uint32_t) n); }   // (26 Oct evening: paced into the PSRAM, as every other card read)
            audioFile.close();
            if (got == audioDataSize) { clipAdd(id, buf, audioDataSize); if (Clip *c = clipFind(id)) { curClip = c; curPos = 0; audioPlaying = true; audioFill(); return; } }
            free(buf);
            if (!wavOpen(id, rate)) { audioId = -1; return; }   // (the read fell short: streamed as before)
        }
    }
    audioPlaying = true;
    audioFill();
}
// (1.11.85) A film's sound, by its path: streamed off the card as it plays (it is minutes long: never kept in memory)
static const int FILM_AUDIO_ID = -2;
static void audioStartFile(const char *path, uint32_t fromMs = 0) {   // (1.11.88) fromMs: from that point in it (Back, Next, Play after a pause)
    audioStop();
    if (!audioRing) return;
    audioLoop = false; audioId = FILM_AUDIO_ID;
    uint32_t rate;
    if (!sdOk || !wavOpenPath(path, rate, true)) { audioId = -1; return; }
    if (rate != audioRate) { i2s_set_sample_rates(I2S_PORT, rate); audioRate = rate; }
    if (fromMs && audioBlock) {                         // (1.11.93) IMA ADPCM: from the block that holds that moment, its samples before it left out
        uint64_t skip; uint32_t samples; ldrcaudio::imaFrom(fromMs, rate, audioBlock, skip, samples);
        if (skip >= audioDataLeft) { audioStop(); return; }
        audioFile.seek(audioDataStart + (uint32_t) skip); audioDataLeft -= (uint32_t) skip; audioSkip = samples;
    } else if (fromMs) {                                // (a film's sound is mono, 16-bit: two bytes a sample)
        const uint64_t skip = (uint64_t) fromMs * rate / 1000 * 2;
        if (skip >= audioDataLeft) { audioStop(); return; }
        audioFile.seek(audioDataStart + (uint32_t) skip); audioDataLeft -= (uint32_t) skip;
    }
    audioPlaying = true;
    audioFill();
}
// loop(): while nothing is happening, bring the small clips into memory one at a time. (1.11.120) In slabs of 4 kB, one
// every 25 ms with the pace's rests, and only once the page has settled: a clip came in with one read of up to 40 kB into
// the PSRAM, and on a page quiet enough for this (the Models page between the main board's polls - the front page never
// is) that slipped the twin's picture at every clip, "every few seconds" after landing on the page (Malcolm, 24 Oct).
static void audioWarm() {
    Busy busy_(BUSY_AUDIO);
    static int next = 0; static uint32_t lastTry = 0;
    static File warmFile; static uint8_t *warmBuf = nullptr; static uint32_t warmGot = 0, warmSize = 0; static int warmId = -1;
    if (!assetsOk() || !audioRing) return;
    if (audioPlaying) { if (warmBuf) { free(warmBuf); warmBuf = nullptr; warmFile.close(); warmId = -1; } return; }   // (a sound: the clip half in is let go; played, audioFill's capture keeps it)
    if (next >= 128 && !warmBuf) return;
    if ((int32_t) (millis() - lastRxMs) < 300 || millis() - lastPresentMs < 1500 || millis() - lastTry < 25) return;
    lastTry = millis();
    if (!warmBuf) {                                      // the next clip: opened, its memory taken
        if (ESP.getFreePsram() < PSRAM_FLOOR + 256 * 1024) return;   // (1.11.133) warming never pushes the PSRAM under its floor (the code lives there since 1.11.131)
        const int id = next++;
        if (clipFind(id)) return;
        uint32_t rate; if (!wavOpen(id, rate)) return;
        if (!audioDataSize || audioDataSize > 40 * 1024) { audioFile.close(); return; }
        clipMakeRoom(audioDataSize);
        warmBuf = (uint8_t *) psMallocRoom(audioDataSize); if (!warmBuf) { audioFile.close(); return; }
        warmFile = audioFile; audioFile = File();          // (the handle is this warm-up's now; a sound meanwhile opens its own)
        warmSize = audioDataSize; warmGot = 0; warmId = id;
        return;
    }
    const int got = warmFile.read(warmBuf + warmGot, std::min((size_t) 4096, (size_t) (warmSize - warmGot)));
    if (got <= 0) { free(warmBuf); warmBuf = nullptr; warmFile.close(); warmId = -1; return; }
    warmGot += (uint32_t) got; psramPace((uint32_t) got);
    if (warmGot >= warmSize) { warmFile.close(); clipAdd(warmId, warmBuf, warmSize); warmBuf = nullptr; warmId = -1; }
}
// A 6x6 dot in the top-left corner: green = on the WiFi, red = not.
static void netDot(bool force = false) {
    static int last = -1; const int now = !radiosLive ? 2 : wifiUpNow() ? 1 : 0;
    if (now == last && !force) return; last = now;
    gfx->fillRect(0, 0, 6, 6, now == 1 ? 0x07E0 : now == 2 ? 0x8410 : 0xF800);
    memoTouched(0, 0, 6, 6); dirty(0, 0, 6, 6);
}
// Two seconds of text along the top, then the page repaints that strip. Navy with white text, like every message of
// the screen's own ("that should be your default for system messages, removing the white over black": Malcolm, 30-9-2026).
static const int BANNER_H = 34;
static void banner(const char *msg, uint32_t ms) {   // (1.11.141: for how long - the update notice stays twenty seconds)
    gfx->fillRect(0, 0, W, BANNER_H, OUR_PANEL); gfx->drawFastHLine(0, BANNER_H - 1, W, OUR_INK);
    gfx->startWrite(); drawGlyphs(max(12, (W - textWidth(2, msg)) / 2), 5, 2, OUR_INK, msg); gfx->endWrite();   // (centred, as every title and message of the screen's)
    memoTouched(0, 0, W, BANNER_H); dirty(0, 0, W, BANNER_H); damage(0, 0, W, BANNER_H);
    bannerUntil = millis() + ms;
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
#include "ble_device.h"
#include "cli_device.h"
#include "film_device.h"   // (1.11.85) films on the help pages

// (1.11.132) The PSRAM's big holders, for /status "mem": who has it when it runs short (twin #2 was seen at 71 kB free after its update).
// (1.11.137) /status "iram": the chip's own RAM, and what of ours holds it - the kept values (every write to a page not on
// show, and every value a finger set), the page-info cache, the logs. Read it after a page tour: what grew is the holder.
static std::string iramJson() {
    multi_heap_info_t hi = {}; heap_caps_get_info(&hi, MALLOC_CAP_INTERNAL);
    size_t keptBytes = 0, keptTxts = 0;
    for (auto &k : kept) { keptBytes += k.first.size() + 48 + k.second.ints.size() * 56; for (auto &t : k.second.txts) { keptBytes += t.first.size() + t.second.size() + 64; ++keptTxts; } }
    size_t infoBytes = 0; for (auto &p : pageInfo) { infoBytes += p.first.size() + 48; for (auto &c : p.second) infoBytes += sizeof(CompInfo) + c.name.size() + c.txt.size(); }
    char b[360];
    snprintf(b, sizeof b, "\"iram\":{\"free\":%u,\"allocated\":%u,\"largest\":%u,\"blocks_used\":%u,\"blocks_free\":%u,\"min\":%u,\"kept\":%u,\"kept_txts\":%u,\"kept_bytes\":%u,\"info_pages\":%u,\"info_bytes\":%u,\"touch_log\":%u,\"boot_log\":%u,\"radio_log\":%u,\"comps\":%u,\"glyphs\":%u}",
             (unsigned) hi.total_free_bytes, (unsigned) hi.total_allocated_bytes, (unsigned) hi.largest_free_block, (unsigned) hi.allocated_blocks, (unsigned) hi.free_blocks, (unsigned) hi.minimum_free_bytes,
             (unsigned) kept.size(), (unsigned) keptTxts, (unsigned) keptBytes, (unsigned) pageInfo.size(), (unsigned) infoBytes, (unsigned) touchLog.size(), (unsigned) bootLog.size(), (unsigned) radioLog.size(),
             (unsigned) page.comps.size(), (unsigned) scaledGlyphs.size());
    return b;
}
static std::string psramJson() {
    char b[300];
    snprintf(b, sizeof b, "\"mem\":{\"psram_largest\":%u,\"pictures\":\"%u/%u\",\"evictions\":%u,\"top\":%d,\"model\":%d,\"film\":%u,\"fade\":%d,\"audio\":%d,\"clips\":%u,\"clip_n\":%u}",
             (unsigned) heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM), (unsigned) bgCache.size(), (unsigned) bgCacheMax, (unsigned) psramEvictions,
             topFb ? 1 : 0, flPicPx ? 1 : 0, (unsigned) filmBufSize, filmFadeTo ? 1 : 0, audioRing ? 1 : 0, (unsigned) clipBytes, (unsigned) clips.size());
    return b;
}
void setup() {
    tlsMemoryBegin();                                      // (1.11.146) FIRST: mbedTLS draws on the PSRAM from here on (src/tls_memory.h)
    Serial.setRxBufferSize(32768);                        // BEFORE begin(): set afterwards it stayed at 256 bytes and telemetry bursts overran it
    Serial.begin(NEXTION_BAUD);
    esp_log_set_vprintf(sysLogHook);                      // 1.11.5: the system's own error lines come to us, not to the main board
    // Above 57600 baud the core raises the receive interrupt at 120 bytes of the 128-byte hardware FIFO: at
    // 921600 that leaves 87 microseconds before bytes are lost, and any brief interrupt delay mangled a command
    // (a stray line across the curve page). At 24 bytes there is over a millisecond in hand.
    Serial.setRxFIFOFull(24);
    boardDetect(); panelMake();                            // (1.11.111) which board, by its flash chip: the pixel clock pin differs, and the wrong one is a black screen
    prefs.begin("screen", false);                          // FIRST: the remembered page, background and volume are read below
    themeLoad();                                           // the pilot's colours, before anything is drawn
    {   // (1.11.131) THE CODE IN THE PSRAM (src/code_in_psram.h), before the panel runs. A start that switched and then died by a
        // panic or a watchdog before loop() reached 20 s counts a strike; two strikes turn it off until the pref is set again
        // (/stall?kind=xip) or the next firmware. A power cut or our own restart within those 20 s is not a strike.
        if (prefs.getString("xipver", "") != SCREEN_VERSION) { prefs.putString("xipver", SCREEN_VERSION); prefs.putInt("xipbad", 0); }
        int strikes = prefs.getInt("xipbad", 0);
        if (prefs.getInt("xiparm", 0)) {
            const esp_reset_reason_t r = esp_reset_reason();
            if (r == ESP_RST_PANIC || r == ESP_RST_INT_WDT || r == ESP_RST_TASK_WDT) prefs.putInt("xipbad", ++strikes);   // (not the RTC watchdog, 7: a quick restart of our own ends that way at times, bench 26 Oct)
            prefs.putInt("xiparm", 0);
        }
        xipStrikes = strikes;
        const int want = prefs.getInt("xip", -1);
        if (strikes >= 2) xipWhy = "off (two early crashes)";
        else if (!xipWanted(want)) xipWhy = want < 0 ? "off (board)" : "off (pref)";
        else { prefs.putInt("xiparm", 1); xipBegin(want); if (xipMode) xipArmed = true; else prefs.putInt("xiparm", 0); }
        if (xipMode) { const size_t pic = (size_t) W * H * 2, took = ((size_t) (xipTextPages + xipRodataPages) * MMU_PAGE_SIZE + pic - 1) / pic; bgCacheMax = took >= 3 ? 2 : 5 - took; }   // the code's share of the PSRAM (1.4 MB = two pictures' worth) comes out of the resident pictures, 4 -> 3 (2 at the least); a film short of room gives up another (psMallocRoom)
        blog("boot", std::string("xip ") + xipWhy);
    }
    pinMode(LCD_BL, OUTPUT); ledcSetup(1, 20000, 8); ledcAttachPin(LCD_BL, 1); blSet(0);   // dark: see "The backlight" above
    screen->begin(); screen->fillScreen(0); screenFb = screen->getFramebuffer();
    hookFrameEnd();   // (1.11.67: the front screen's switch drawn and copied in the panel's quiet time)
    { uint16_t *cb = (uint16_t *) heap_caps_aligned_calloc(64, 1, (size_t) W * H * 2, MALLOC_CAP_SPIRAM); if (cb) canvas->aim(cb); }   // (1.11.116) aligned as a panel buffer must be: the canvas is one of the three in turn
    if (canvas->begin(GFX_SKIP_OUTPUT_BEGIN)) { gfx = canvas; fbNow = canvas->getFramebuffer(); canvas->fillScreen(0); } else fbNow = screenFb;
    pageFb = fbNow;
    if (flipOk && pageFb && pageFb != screenFb && ((uintptr_t) pageFb & 63) == 0) { flipFb[2] = pageFb; canvas->lazy = true; }   // (the rotation is on)
    blog("boot", std::string("layer ") + (topReady() ? "ready" : "no room"));   // (1.11.136) our own layer made now, before any flip can complete (see flipTick)
    dcOn = prefs.getInt("dmacopy", 0) != 0; dmaCopyInit();
    {   // (1.11.134) THE STRIPS (src/strip_feed.h): the pref "strips" (-1 the board's choice = the twin; 0 off; 1 on). A start that armed
        // them and died by a panic or a watchdog before 20 s counts a strike (prefs striparm/stripbad); two turn them off until the pref is
        // set again (/stall?kind=strips) or the next firmware version (stripver).
        if (prefs.getString("stripver", "") != SCREEN_VERSION) { prefs.putString("stripver", SCREEN_VERSION); prefs.putInt("stripbad", 0); }
        int strikes = prefs.getInt("stripbad", 0);
        if (prefs.getInt("striparm", 0)) {
            const esp_reset_reason_t r = esp_reset_reason();
            if (r == ESP_RST_PANIC || r == ESP_RST_INT_WDT || r == ESP_RST_TASK_WDT) prefs.putInt("stripbad", ++strikes);
            prefs.putInt("striparm", 0);
        }
        stripStrikes = strikes;
        const int want = prefs.getInt("strips", -1);
        stripWant = want < 0 ? (board->psramRestUs != 0 ? 1 : 0) : want;
        const bool skip = prefs.getInt("stripskip", 0) != 0; if (skip) prefs.putInt("stripskip", 0);   // (the updater's fresh start before an install: this one start without them)
        if (strikes >= 2) { stripWant = 0; stripWhy = "off (two early crashes)"; }
        else if (skip && stripWant) { stripWant = 0; stripWhy = "off (the update's fresh start)"; }
        else if (!stripWant) stripWhy = want < 0 ? "off (board)" : "off (pref)";
        else { prefs.putInt("striparm", 1); stripArmed = true; }
    }   // (1.11.128) the DMA copy of 1.11.126 is OFF unless the pref says so (Malcolm, 26 Oct: more flicker on the desk than it cured, the bench's counters blind to it); /stall?kind=dmacopy&kb=1 for the bench
    blog("boot", std::string("dmacopy ") + dcWhy);
    if (prefs.getInt("ring", 1)) ringSet(true); else ringWhy = "off (pref)";   // (25 Oct) the frames chained by the hardware from here on (src/frame_ring.h); /look?key=ring&val=0 keeps the driver's own restarts
    blog("boot", std::string("ring ") + ringWhy);
    Wire.begin(TP_SDA, TP_SCL);
    touch.setPins(board->touchRst, board->touchInt);       // (1.11.111) the twin's touch chip has its reset on IO38: left floating it may never wake; the CrowPanel's is not wired (-1)
    touchOk = touch.begin(Wire, GT911_SLAVE_ADDRESS_L, TP_SDA, TP_SCL) || touch.begin(Wire, GT911_SLAVE_ADDRESS_H, TP_SDA, TP_SCL);
    if (touchOk) touch.setMaxCoordinates(W, H);
    sdSPI.begin(SD_CLK, SD_MISO, SD_MOSI, SD_CS);
    blog("boot", std::string("screen up ") + SCREEN_MARK + " " + BUILD_MARK + " on " + boardWords());   // (1.11.111: which board, and which build)
    ldrc::crc32((const uint8_t *) "", 0);                  // (its table is made now, by one task, not later by two at once)
    sdOk = SD.begin(SD_CS, sdSPI, 40000000) || SD.begin(SD_CS, sdSPI, 20000000);
    blog("boot", sdOk ? "sd ok" : "sd FAILED");
    updMend();                                             // a file that was being replaced when the power went is put back, before anything is read
    packMount();                                           // (1.11.138, flash_pack.h) the pack: pages, fonts and sounds in the chip's own flash, on the 16 MB boards
    if (assetsOk()) loadAaFonts();
    blog("boot", "fonts");
    if (packStartup()) loadAaFonts();                      // a pack missing or stale is copied from the card now (a line on the panel): then the fonts from it
    if (assetsOk()) {
        File f = assetOpen("/hmi/index.json");
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
    // After a restart mid-session (an OTA update, a fresh start to put the memory together, a look copied in) the
    // Teensy still thinks the screen is showing everything: nudge it to the front page, which it fills in by itself -
    // the word "FrontView" is one of its legacy text commands. (1.11.34: whatever page it was: a page put back from
    // the card alone has none of the words the Teensy wrote on it, and the Teensy would never write them again.)
    if (why == ESP_RST_SW && !pageNames.empty()) { delay(300); Serial.print("FrontView"); }
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
    { Busy b(BUSY_SERIAL); pumpSerial(); } { Busy b(BUSY_LINK); linkPoll(); updPoll(); } { Busy b(BUSY_WIFI); wifiPoll(); } { Busy b(BUSY_PICS); picPoll(); }
    { Busy b(BUSY_FLIGHT); flightPoll(); coloursPoll(); appearancePoll(); pongPoll(); } { Busy b(BUSY_FILM); filmPoll(); } { Busy b(BUSY_WIFI); blPoll(); blePoll(); } { Busy b(BUSY_CLI); cliPoll(); } PHASE(0)   // (25 Oct evening: Busy tags = who slipped the panel, /perf "slipw")
    { Busy b(BUSY_AUDIO); audioFill(); if (!teensyLink.running() && !(benchSkip & 4)) audioWarm(); } PHASE(1)
    { Busy b(BUSY_SD); packTick(!teensyLink.running() && (int32_t) (now - lastRxMs) >= 100 && now - lastPresentMs >= 300 && !flyingNow()); }   // (1.11.138) the card against the pack, a file at a time between the front page's clock ticks
    { Busy b(BUSY_PREFS); if (!teensyLink.running()) prefsPoll(); if (xipArmed && now > 20000 && !teensyLink.running() && (wireQuiet(300) || now > 90000)) { xipArmed = false; nvsQuiet([&] { prefs.putInt("xiparm", 0); }); } if (stripArmed && now > 20000 && !teensyLink.running() && (wireQuiet(300) || now > 90000)) { stripArmed = false; nvsQuiet([&] { prefs.putInt("striparm", 0); }); } } PHASE(2)   // (1.11.131) 20 s up with the code in the PSRAM: no strike for this start
    { static uint32_t floorAt = 0; if (now - floorAt > 500) { floorAt = now; if (ESP.getFreePsram() < PSRAM_FLOOR && (clipDropOne() || bgEvictOne())) psramEvictions++; } }   // (1.11.132/133: clips first) the PSRAM floor: under half a megabyte free, a resident picture not on show is given up (the code lives in the PSRAM since 1.11.131; twin #2 was seen at 71 kB free after its update)
    { Busy b(BUSY_TOUCH); pollTouch(); } PHASE(3)
    { Busy b(BUSY_TIMERS); pollTimers(); } PHASE(4)
    slideTxtTick(false); presentDirty(touchPainted); touchPainted = false; PHASE(5)   // a finger's feedback is shown at once; the Teensy's at the end of its burst (1.11.144: a slide text's words 120 ms on if their position never came)
    { Busy b(BUSY_WIFI); netPoll(); } PHASE(6)
    #undef PHASE
}
