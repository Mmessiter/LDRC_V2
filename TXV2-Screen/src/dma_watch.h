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
static bool IRAM_ATTR dmaOnEof(gdma_channel_handle_t, gdma_event_data_t *, void *) {
    const uint32_t now = (uint32_t) esp_timer_get_time();
    if (dmaEofUs) {
        const uint32_t gap = now - dmaEofUs;
        if (gap < dmaGapMin) dmaGapMin = gap; if (gap > dmaGapMax) dmaGapMax = gap;
        if (gap > 20000 && gap < 40000) {              // (a frame's gap, not a stopped engine's or a restart's)
            if (!dmaGapBase) dmaGapBase = gap;
            else {                                     // the base follows the usual gap slowly (one early stamp must not set it for good: it did, 28859 against 28920)
                const int32_t d = (int32_t) (gap - dmaGapBase);
                if (d > -300 && d < 300) dmaGapBase = (uint32_t) ((int32_t) dmaGapBase + d / 32);
                if (d > (int32_t) DMA_SLIP_US) { const uint32_t s = (uint32_t) d; dmaSlips++; dmaSlipsAll++; dmaSlipSum += s; if (s > dmaSlipMax) dmaSlipMax = s; }
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
