// THE PANEL'S DMA WATCH (25 Oct 2026). Malcolm: "When selecting a background image under Appearance, the screen flickers
// every time a new image is displayed. This I thought might provide a clue about the cause of the flickering which seems
// elusive." Until now a slip could only be SEEN. The panel's DMA meets the frame buffer's last descriptor (its EOF) at a
// fixed moment of every frame: the picture's last line, less what its FIFO holds. Anything that keeps it from the PSRAM -
// a copy at full speed, code streaming from the flash, a flash write - delays that moment by exactly the time it was
// starved, and the rest of the picture is shifted by the same: the sideways slip (at 14.5 MHz, 1 us = 14 pixels). So the
// GDMA's EOF interrupt stamps the time, the frame-end hook measures it from the frame's start, and a frame later than the
// earliest ever seen by DMA_LATE_US is counted LATE. /perf "dma": frames, base_us (the undisturbed moment), max_us, late,
// late_max_us, missed (no EOF before the frame's end: starved past the blank after the picture), hist (16 bins of 10 us
// above base), gap (the EOF-to-EOF interval's min/max: the interrupt's own jitter, the frame being fixed by the hardware).
// /stall makes a known stall to calibrate it. The driver registers no EOF callback of its own (libesp_lcd.a: only
// lcd_default_isr_handler, which restarts the frame after our callback: gdma_reset, fifo reset, gdma_start, 1 us, start).
#pragma once
#include <Arduino.h>
#include "esp_private/gdma.h"

static volatile uint32_t dmaEofUs = 0, dmaEofPrevUs = 0;  // when the DMA met the frame's EOF (stamped in its interrupt), and the one before
static volatile uint32_t dmaGapMin = 0xFFFFFFFF, dmaGapMax = 0;   // EOF to EOF
static volatile uint32_t dmaFrames = 0, dmaBaseUs = 0, dmaMaxUs = 0, dmaLateN = 0, dmaLateMaxUs = 0, dmaMissedN = 0;   // (/perf: since the last read)
static volatile uint32_t dmaHist[16] = { 0 };
static volatile uint32_t dmaLateAll = 0, dmaMissedAll = 0;   // (/status: since boot)
static bool dmaWatchOn = false;
static const uint32_t DMA_LATE_US = 150;                  // (the two interrupts' own jitter is ~100 us at idle: above that it is real)

// THE SLIP COUNTER (25 Oct ~11:15). EOF to EOF is the hardware's own frame (28.97 ms on the twin): both stamps carry the
// same interrupt latency, and that varies by only ~5 us (the gaps' min to max at idle). A frame whose DMA was kept from the
// PSRAM meets its EOF later by exactly the time it waited - the picture shifted by 14 pixels a microsecond for that frame
// - and the gap before it is longer by that much (the re-sync at the frame's end puts the next one back). So a gap longer
// than the shortest seen by DMA_SLIP_US is a slip, counted with its size. (A first try measured our start of the DMA to its
// EOF: that only measured the frame-end interrupt's own latency, 0-250 us - the EOF comes when the engine has drawn the
// picture, whenever the DMA was started.)
static const uint32_t DMA_SLIP_US = 15;
static volatile uint32_t dmaGapBase = 0, dmaSlips = 0, dmaSlipMax = 0, dmaSlipsAll = 0, dmaSlipSum = 0;
static volatile uint32_t dmaGapBase16 = 0;               // (the base in sixteenths: d/32 in whole microseconds never moved it for |d| < 32 - it sat 10 us high)
static volatile int32_t dmaLastD = 0;                     // the last gap against the base (a slip in the frame just ended: +S)
// THE PERIOD (25 Oct evening): the mean of 32 undisturbed gaps, the hardware's frame to within a microsecond - the frame ring's
// phase tracker steps by it (frame_ring.h: a callback is late by how far it runs after the frame's end predicted from the
// earliest callbacks, whatever the DMA's state - the EOF's own moment moves with every slip, and read as a clock it kept
// the picture shifted for good).
static volatile uint32_t dmaGapMean = 0, dmaGapSum = 0, dmaGapCnt = 0;
// THE SLIP'S CULPRIT (25 Oct evening): every gap longer than the base by DMA_SLIPW_US or more is counted under the loop's
// busy tag of the moment (busy_what.h) - /perf "slipw" {n[], sum[], log[[us, tag, ms]...]}, the window's first 24 logged.
// (The EOF stamps' own jitter is +-6 us at idle: the idle tag's count is the noise floor to read the others against.)
static volatile int32_t dmaSlipwUs = 7; static const int SLIPW_LOG = 24;   // (bench: /stall?kind=slipwus&kb=us lowers the bar - the idle noise floor is +-6 us)
static volatile uint32_t slipwN[BUSY_N] = { 0 }, slipwSum[BUSY_N] = { 0 }, slipwSeenN[BUSY_N] = { 0 };   // by the tag at the EOF; by every tag seen in the frame
// THE FINE ESTIMATOR (25 Oct 20:50). A slip smaller than the stamps' jitter cannot be told apart frame by frame, but it can
// be averaged out: for EVERY frame the gap's excess over the base (its positive part) is added to each MOVER tag seen in
// that frame (sd, wb, copy, rest, draw, nvs, bg, present, handle, flip, ensure - the loop's phases are seen in every
// frame and say nothing), and to a baseline of frames with no mover at all. /perf "slipw".pos[] / .fr[] against .idle:
// the mean excess per frame for each mover, the noise floor being the baseline's (~3 us).
static const uint32_t BUSY_MOVERS = (1u << 1) | (1u << 2) | (1u << 3) | (1u << 4) | (1u << 5) | (1u << 6) | (1u << 7) | (1u << 8) | (1u << 9) | (1u << 20) | (1u << 21);
static volatile uint32_t slipwPos[BUSY_N] = { 0 }, slipwFr[BUSY_N] = { 0 }, slipwIdlePos = 0, slipwIdleFr = 0;
static volatile uint32_t dmaProbePos = 0, dmaProbeFr = 0; static volatile int32_t dmaProbeMax = 0;   // (26 Oct, bench) a /stall probe's own frames: the excess summed, their number, the worst
static volatile uint32_t dmaHuge = 0, dmaHugeAll = 0;    // (1.11.128) EOF gaps of 60 ms and more, or 20 ms over the base: a frame the panel's DMA was held from for longer than a slip - the counters above never saw these (the DMA copy of 1.11.126)
struct SlipW { uint16_t us; uint8_t what; uint32_t seen; uint32_t ms; };
static SlipW slipwLog[SLIPW_LOG]; static volatile int slipwLogN = 0;
static bool IRAM_ATTR dmaOnEof(gdma_channel_handle_t, gdma_event_data_t *, void *) {
    const uint32_t now = (uint32_t) esp_timer_get_time();
    if (dmaEofUs) {
        const uint32_t gap = now - dmaEofUs;
        if (gap < dmaGapMin) dmaGapMin = gap; if (gap > dmaGapMax) dmaGapMax = gap;
        if (gap >= 60000 && gap < 2000000) {           // (1.11.128) two frames and more between EOFs: the panel held, not a stopped engine (ringTick restarts that after 150 ms)
            dmaHuge++; dmaHugeAll++;
            if (slipwLogN < SLIPW_LOG) { SlipW &e = slipwLog[slipwLogN]; e.us = 65535; e.what = busyWhat < BUSY_N ? busyWhat : BUSY_N - 1; e.seen = busySeen; e.ms = now / 1000; slipwLogN = slipwLogN + 1; }   // (us 65535 = a gap of 60 ms and more; the gap itself in dmaGapMax)
        }
        if (gap > 20000 && gap < 60000) {              // (a frame's gap - 28.9 ms on the twin, 43.1 on the CrowPanel - not a stopped engine's or a restart's)
            if (!dmaGapBase16) { dmaGapBase16 = gap * 16; dmaGapBase = gap; }
            else {                                     // the base follows the usual gap slowly (one early stamp must not set it for good: it did, 28859 against 28920)
                const int32_t d = (int32_t) (gap - dmaGapBase);
                if (d > -300 && d < 300) { dmaGapBase16 = (uint32_t) ((int32_t) dmaGapBase16 + ((int32_t) (gap * 16) - (int32_t) dmaGapBase16) / 32); dmaGapBase = (dmaGapBase16 + 8) / 16; }
                if (d > -100 && d < 100) { dmaGapSum += gap; if (++dmaGapCnt >= 32) { dmaGapMean = dmaGapSum / 32; dmaGapSum = 0; dmaGapCnt = 0; } }
                dmaLastD = d;
                const uint32_t seen = busySeen; busySeen = 0;   // (this frame's tags; the mask starts again)
                if (d < 20000) {                           // the fine estimator: this frame's excess under every mover seen, or under the baseline
                    const uint32_t pos = d > 0 ? (uint32_t) d : 0;
                    dmaProbePos += pos; dmaProbeFr = dmaProbeFr + 1; if (d > dmaProbeMax) dmaProbeMax = d;
                    if (seen & BUSY_MOVERS) { for (int i = 0; i < BUSY_N; ++i) if ((seen & BUSY_MOVERS) & (1u << i)) { slipwPos[i] += pos; slipwFr[i]++; } }
                    else { slipwIdlePos += pos; slipwIdleFr++; }
                }
                if (d >= dmaSlipwUs) {                     // (1.11.128: the huge ones too - logged with their size, up to 65534 us)
                    const uint8_t w = busyWhat < BUSY_N ? busyWhat : BUSY_N - 1;
                    slipwN[w]++; slipwSum[w] += (uint32_t) d;
                    for (int i = 0; i < BUSY_N; ++i) if (seen & (1u << i)) slipwSeenN[i]++;
                    if (slipwLogN < SLIPW_LOG) { SlipW &e = slipwLog[slipwLogN]; e.us = (uint16_t) (d > 65534 ? 65534 : d); e.what = w; e.seen = seen; e.ms = now / 1000; slipwLogN = slipwLogN + 1; }
                }
                if (d > (int32_t) DMA_SLIP_US && d < 20000) { const uint32_t s = (uint32_t) d; dmaSlips++; dmaSlipsAll++; dmaSlipSum += s; if (s > dmaSlipMax) dmaSlipMax = s; }   // (a whole frame more is an EOF interrupt missed, not a slip)
                if (d >= 20000) { dmaHuge++; dmaHugeAll++; }   // (1.11.128) ... or the panel held for most of a frame: counted apart, no longer dropped
            }
        }
    }
    dmaEofPrevUs = dmaEofUs; dmaEofUs = now;
    return false;
}
static void dmaWatchStart(gdma_channel_handle_t ch) {
    if (!ch) return;
    gdma_tx_event_callbacks_t cbs = {};
    cbs.on_trans_eof = dmaOnEof;
    dmaWatchOn = gdma_register_tx_event_callbacks(ch, &cbs, nullptr) == ESP_OK;
}
// At the frame's end, BEFORE quietFrameEnd moves frameAtUs on to this moment: how late the DMA met the ending frame's EOF.
static void IRAM_ATTR dmaFrameTick() {
    if (!dmaWatchOn) return;
    const uint32_t eof = dmaEofUs, start = frameAtUs;
    if (!eof || !start) return;
    if ((int32_t) (eof - start) < 0 || eof - start > 200000) { dmaMissedN++; dmaMissedAll++; return; }   // no EOF inside this frame
    const uint32_t off = eof - start;
    dmaFrames++;
    if (!dmaBaseUs || off < dmaBaseUs) dmaBaseUs = off;
    if (off > dmaMaxUs) dmaMaxUs = off;
    const uint32_t late = off - dmaBaseUs;
    dmaHist[late / 10 < 15 ? late / 10 : 15]++;
    if (late > DMA_LATE_US) { dmaLateN++; dmaLateAll++; if (late > dmaLateMaxUs) dmaLateMaxUs = late; }
}
// (bench) /stall?kind=isr&kb=N: the NEXT frame end's callback spins N us before the driver restarts the frame - a late
// restart on purpose (what a flash write, with the interrupts off, does to the frame end it straddles). Seen as a slip?
static volatile uint32_t dmaSpinUs = 0;
static void IRAM_ATTR dmaSpin() {
    const uint32_t n = dmaSpinUs;
    if (!n) return;
    dmaSpinUs = 0;
    const uint32_t t0 = (uint32_t) esp_timer_get_time();
    while ((uint32_t) esp_timer_get_time() - t0 < n) { }
}
static std::string dmaPerfJson() {                       // the /perf block; the window's counters start again
    char b[200];
    snprintf(b, sizeof b, "\"dma\":{\"on\":%d,\"frames\":%lu,\"base_us\":%lu,\"max_us\":%lu,\"late\":%lu,\"late_max_us\":%lu,\"missed\":%lu,\"gap\":[%lu,%lu],\"hist\":[",
             dmaWatchOn ? 1 : 0, (unsigned long) dmaFrames, (unsigned long) dmaBaseUs, (unsigned long) dmaMaxUs, (unsigned long) dmaLateN, (unsigned long) dmaLateMaxUs, (unsigned long) dmaMissedN,
             (unsigned long) (dmaGapMin == 0xFFFFFFFF ? 0 : dmaGapMin), (unsigned long) dmaGapMax);
    std::string out = b;
    for (int i = 0; i < 16; ++i) { char e[16]; snprintf(e, sizeof e, "%s%lu", i ? "," : "", (unsigned long) dmaHist[i]); out += e; dmaHist[i] = 0; }
    out += "]}";
    dmaFrames = dmaMaxUs = dmaLateN = dmaLateMaxUs = dmaMissedN = 0; dmaGapMin = 0xFFFFFFFF; dmaGapMax = 0;
    dmaBaseUs = 0;                                     // (each window learns its own earliest: one odd early stamp at a boot or a restart would skew every later one)
    return out;
}
static std::string slipwPerfJson() {                     // the /perf block; the window starts again
    std::string out = ",\"slipw\":{\"n\":[";
    for (int i = 0; i < BUSY_N; ++i) { char e[16]; snprintf(e, sizeof e, "%s%lu", i ? "," : "", (unsigned long) slipwN[i]); out += e; }
    out += "],\"sum\":[";
    for (int i = 0; i < BUSY_N; ++i) { char e[16]; snprintf(e, sizeof e, "%s%lu", i ? "," : "", (unsigned long) slipwSum[i]); out += e; }
    out += "],\"seen\":[";
    for (int i = 0; i < BUSY_N; ++i) { char e[16]; snprintf(e, sizeof e, "%s%lu", i ? "," : "", (unsigned long) slipwSeenN[i]); out += e; }
    out += "],\"log\":[";
    const int n = slipwLogN < SLIPW_LOG ? slipwLogN : SLIPW_LOG;
    for (int i = 0; i < n; ++i) { char e[56]; snprintf(e, sizeof e, "%s[%u,%u,%lu,%lu]", i ? "," : "", (unsigned) slipwLog[i].us, (unsigned) slipwLog[i].what, (unsigned long) slipwLog[i].seen, (unsigned long) slipwLog[i].ms); out += e; }
    out += "],\"pos\":[";
    for (int i = 0; i < BUSY_N; ++i) { char e[16]; snprintf(e, sizeof e, "%s%lu", i ? "," : "", (unsigned long) slipwPos[i]); out += e; }
    out += "],\"fr\":[";
    for (int i = 0; i < BUSY_N; ++i) { char e[16]; snprintf(e, sizeof e, "%s%lu", i ? "," : "", (unsigned long) slipwFr[i]); out += e; }
    { char e[48]; snprintf(e, sizeof e, "],\"idle\":[%lu,%lu]}", (unsigned long) slipwIdlePos, (unsigned long) slipwIdleFr); out += e; }
    for (int i = 0; i < BUSY_N; ++i) { slipwN[i] = 0; slipwSum[i] = 0; slipwSeenN[i] = 0; slipwPos[i] = 0; slipwFr[i] = 0; }
    slipwIdlePos = 0; slipwIdleFr = 0;
    slipwLogN = 0;
    return out;
}

