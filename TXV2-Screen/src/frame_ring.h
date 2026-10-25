// THE RING (25 Oct 2026) - no software between one frame and the next.
//
// Measured on the twin with src/dma_watch.h: the panel's DMA is hardly ever starved (256 kB filled or copied in the PSRAM at
// full speed, 520 kB read off the card, a whole page drawn and rotated, a flash write, a 1 MB flash read: never out of
// step), yet a frame end whose restart was held back on purpose (/stall?kind=isr) Malcolm SAW as the flicker. IDF 4.4.7's
// RGB driver restarts the panel by software at EVERY frame's end (lcd_default_isr_handler ->
// lcd_rgb_panel_start_transmission: gdma_reset, lcd stop, fifo reset, gdma_start, 1 us, lcd start), so every delay of that
// interrupt - a flash write with the interrupts off (an NVS write: the background page's every tap, the front screen's
// switch before 1.11.69), a long critical section, another interrupt served first - stretches the blank between two
// frames, and the panel shows it. IDF 5.1's driver does what is done here (esp_lcd_panel_rgb.c, "stream mode"): the
// descriptors form a RING, lcd_ll_enable_auto_next_frame(true) is set before the one start, and the VSYNC interrupt
// restarts nothing unless asked. The bit is only latched by lcd_ll_start (lcd_update), so the change-over is a last
// software restart made in the frame-end callback itself, with the bit set and the ring closed; the driver's own restart
// is then switched off by clearing stream_mode in its struct (the word before dma_nodes, which chainFind located; checked
// to hold stream_mode|fb_in_psram and nothing above bit 2 first).
//
// The flip (page_flip.h) then no longer moves the descriptors under the DMA: each panel buffer has a ring of its own, and a
// flip points the ring on show at the other ring's head. The DMA follows that pointer when it reaches the last descriptor
// (0.6 ms before the frame's end); the frame end after sees it on the new ring (GDMA's current-descriptor register) and
// puts the old ring back on itself. Asked at one frame's end, shown from the second frame after: 58 ms at most on the twin.
//
// THE HEAL. Chained by the hardware, a frame whose DMA was kept from the PSRAM stays out of step for good: the whole picture
// shifted by lines, permanently (IDF 5's Kconfig: "permanent desyncs"; seen at the twin's boot, 25 lines). So at every
// frame end the GDMA's current descriptor is read: in step it is at the head of the ring on show (the next frame's first
// descriptors, prefetched: 0..2 seen); anywhere else - or the EOF's moment in the frame off the learned one by 80 us for
// three frames running - the panel is restarted as the driver used to restart it every frame (stop, fifo reset, DMA from
// the ring's head, start; the engine's chaining latched again): in the blank, as before, unseen; one frame showed the
// shift. Not from a callback that is itself late (the frame end long gone: a flash write's interrupts-off, the bench's
// /stall?kind=isr): the DMA is then rightly far into the next frame, and a restart from there would break that frame.
// (The first heal tried IDF 5's way - the DMA alone reset and started again from a node past the FIFO's pixels, the
// engine running on - and a late callback's one left the DMA dead: no EOF ever again, the frames empty.)
// If the frames stop, or the EOFs do, for 150 ms, the same restart from the loop (ringTick).
#pragma once
#include <Arduino.h>
#include <esp_heap_caps.h>
#include <esp_rom_sys.h>
#include "esp_private/gdma.h"
#include "hal/lcd_ll.h"
#include "soc/lcd_cam_struct.h"
#include "soc/gdma_struct.h"

static FlipNode *flipChain[3] = { nullptr, nullptr, nullptr };   // a ring per panel buffer; [0] is the driver's own chain
static volatile int8_t ringPending = -1;               // the ring on show points at this buffer's ring: the DMA follows it at the frame's end
static volatile bool ringArm = false;                  // the next frame end makes the change-over
static const char *ringWhy = "off";
static uint32_t *ringFlags = nullptr;                  // the driver's flags word (stream_mode is bit 1)
static gdma_channel_handle_t ringDma = nullptr;
static int ringCh = -1;                                // the GDMA channel: GDMA.channel[ringCh].out.dscr is the descriptor the DMA is on
static volatile uint32_t ringSwitches = 0, ringWaits = 0, ringStarts = 0, ringHeals = 0, ringHealsEof = 0, ringLateN = 0;
static uint32_t ringRescues = 0, ringSeenEnds = 0, ringSeenEof = 0, ringSeenAt = 0, ringEndsAt = 0, ringEofAt = 0;
static volatile bool ringHealAsk = false;              // (the loop asks a restart at the next frame end)
static const int RING_LOG_N = 48;                      // the EOF's offset in each of the first frames after the change-over (us): /status "ring".log
static volatile uint16_t ringLog[RING_LOG_N]; static volatile int ringLogN = RING_LOG_N;
static const int RING_HEAD_N = 3;                      // in step: the DMA on descriptor 0..3 of the ring on show at the frame's end (2 seen), plus one per 146 us the callback is late
static const uint32_t RING_LATE_US = 250;              // a callback this long after the frame's end is a late one: no re-sync from it (the picture begins 0.57 ms after the frame's end on the twin: 10 lines of back porch; 0.86 on the CrowPanel)
static const uint32_t RING_NODE_US = 146;              // what the DMA takes over one descriptor (4095 bytes, 2.56 lines at 57.4 us)
// The EOF rule - the EOF's moment in the frame off the learned one by 80 us for three frames running - is COUNTED ONLY
// (eof_off): it healed three times during Malcolm's page changes (25 Oct ~10:55, "a flicker just before the screen moves"),
// fooled by the interrupt stamps' jitter under a page draw; the GDMA's descriptor register is the judge.
static const uint32_t RING_OFF_US = 80; static const int RING_OFF_N = 3;
static volatile uint32_t ringExpectUs = 0; static volatile int ringOffN = 0, ringLearnN = 0;
static volatile int ringLastIdx = -1, ringLastOn = -1; // (/status) where the DMA was at the last frame end

static FlipNode *ringMake(uint8_t *fb) {               // a ring for fb, shaped like the driver's chain
    FlipNode *c = (FlipNode *) heap_caps_malloc(flipNodeN * sizeof(FlipNode), MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    if (!c) return nullptr;
    size_t sum = 0;
    for (uint32_t i = 0; i < flipNodeN; ++i) { c[i] = flipNodes[i]; c[i].buffer = fb + sum; c[i].next = &c[(i + 1) % flipNodeN]; sum += flipNodes[i].length; }
    return c;
}
static bool ringEnsure() {                             // (from the loop) a ring for every panel buffer there is
    for (int i = 0; i < 3; ++i) {
        if (!flipFb[i] || flipChain[i]) continue;
        flipChain[i] = i == 0 ? flipNodes : ringMake((uint8_t *) flipFb[i]);
        if (!flipChain[i]) return false;
        flipChain[i][flipNodeN - 1].next = &flipChain[i][0];
    }
    return true;
}
// The driver's own restart, with the engine told to chain the frames (latched by this lcd_ll_start) - from the ring on show.
static void IRAM_ATTR ringRestart() {
    if (!ringDma || !flipChain[flipShown]) return;
    lcd_ll_enable_auto_next_frame(&LCD_CAM, true);
    gdma_reset(ringDma); lcd_ll_stop(&LCD_CAM); lcd_ll_fifo_reset(&LCD_CAM);
    gdma_start(ringDma, (intptr_t) flipChain[flipShown]);
    esp_rom_delay_us(1);
    lcd_ll_start(&LCD_CAM);
    dmaBaseUs = 0; dmaEofUs = 0; ringExpectUs = 0; ringLearnN = 0; ringOffN = 0;
}
// From the loop. On: the rings made and closed, the change-over armed for the next frame end, the driver's restart switched
// off (in that order: a frame end between the two still gets a restart from both, and the bit is latched either way).
// Off (the bench's A/B): the driver's chain pointed at the buffer on show, its restart back, the engine's chaining off (the
// driver's next restart latches it).
static void ringSet(bool on) {
    if (on == (ringOn || ringArm)) return;
    if (on) {
        if (!flipNodes || !flipNodeN || !ringDma) { ringWhy = "no chain"; return; }
        // esp_rgb_panel_t (4.4.7): ... int x_gap; int y_gap; portMUX_TYPE spinlock; int lcd_clk_flags; struct { disp_en_level:1;
        // stream_mode:1; fb_in_psram:1; } flags; dma_descriptor_t dma_nodes[]; - seen on the twin: 0 0 0 7 (the spinlock never set).
        uint32_t *w = (uint32_t *) flipNodes;
        if (!((w[-1] & 6u) == 6u && w[-1] < 8u && w[-2] < 16u)) {
            static char why[80]; snprintf(why, sizeof why, "struct %08lx %08lx %08lx %08lx", (unsigned long) w[-4], (unsigned long) w[-3], (unsigned long) w[-2], (unsigned long) w[-1]); ringWhy = why; return;
        }
        if (!ringEnsure()) { ringWhy = "no memory"; return; }
        if (ringCh < 0) { int id = -1; if (gdma_get_channel_id(ringDma, &id) == ESP_OK && id >= 0 && id < 5) ringCh = id; }
        ringFlags = w - 1; ringPending = -1;
        ringArm = true;                                // (the frame end makes the change-over)
        *ringFlags &= ~2u;                             // (stream_mode off: the driver's interrupt restarts nothing from the next frame end on)
        ringWhy = "armed";
        ringSeenEnds = frameEnds; ringSeenEof = dmaEofUs; ringSeenAt = millis();
    } else {
        ringArm = false;
        const uint32_t f = frameEnds, t0 = micros(); while (frameEnds == f && micros() - t0 < 50000) { }
        if (flipShown != 0 && flipFb[flipShown]) { size_t sum = 0; for (uint32_t i = 0; i < flipNodeN; ++i) { flipNodes[i].buffer = (uint8_t *) flipFb[flipShown] + sum; sum += flipNodes[i].length; } }   // (the driver restarts from its own chain: the buffer on show)
        lcd_ll_enable_auto_next_frame(&LCD_CAM, false);
        if (ringFlags) *ringFlags |= 2u;
        ringOn = false; ringPending = -1; ringWhy = "off (asked)";
    }
}
// THE RE-SYNC (25 Oct ~11:00). A small slip - the DMA kept from the PSRAM for a few microseconds - stays for good under the
// hardware's chaining (Malcolm's photo: the picture 70 pixels to the right, junk down the left edge), and no stamp can see
// it. IDF 5's CONFIG_LCD_RGB_RESTART_IN_VSYNC is the cure: the DMA ALONE is reset and started again at every frame end,
// in the blank, the engine running on untouched - so a late interrupt stretches nothing (that was the flicker), and every
// frame begins exactly at the ring's head. Done here with the LCD's FIFO emptied too (no "pixels preserved" to skip: a
// 17-pixel skip left the buffer unaligned and the DMA dead), and only from a callback that is on time (RING_LATE_US): a
// late one lets the DMA run on, chained, and the next frame end sets it right. The flip rides on it: the restart takes the
// ring WANTED, so a flip shows from the very next frame and needs no pointer between the rings.
// THE SLIP COUNTER. Started by us at a known moment, the DMA meets the ring's EOF a fixed time later (768 kB at the
// engine's pace) unless it was kept from the PSRAM: then later by exactly the time it waited, and the frame on show was
// shifted by that (14 pixels a microsecond). The EOF interrupt's own jitter is ~5 us (EOF-to-EOF gaps), so slips from
// ~15 us (200 pixels) are counted (/status "ring": slips, slip_max_us, dur_min_us; /perf resets slips and the max).
static volatile uint32_t ringStartUs = 0, ringDurMin = 0, ringSlips = 0, ringSlipMax = 0, ringSlipsAll = 0;
static const uint32_t RING_SLIP_US = 15;
static void IRAM_ATTR ringResync(uint8_t want) {
    gdma_reset(ringDma);
    lcd_ll_fifo_reset(&LCD_CAM);
    gdma_start(ringDma, (intptr_t) flipChain[want]);
    ringStartUs = (uint32_t) esp_timer_get_time();
}
static volatile uint32_t ringResyncs = 0, ringSkipped = 0, ringOutN = 0;
static void IRAM_ATTR ringHealNow() { ringResync(flipShown); ringHeals++; }
// At the frame's end (before quietFrameEnd moves frameAtUs on, and in place of flipFrameEnd's descriptor move).
static void IRAM_ATTR ringFrameEnd() {
    if (ringArm) { ringArm = false; ringRestart(); ringOn = true; ringWhy = "on"; ringStarts++; ringLogN = 0; return; }   // the change-over
    if (!ringOn) return;
    if (ringHealAsk) { ringHealAsk = false; ringHealNow(); return; }   // (the loop saw the EOFs stop)
    const uint32_t now = (uint32_t) esp_timer_get_time();
    // How long after its frame's end this callback runs. From the callback before (its own latency in it: two late ones
    // running put a re-sync into the first visible line - "very occasional flickers after changing screens", 25 Oct 11:50)
    // AND from the DMA's EOF stamp, which is precise (+-5 us) and sits a known time before the frame's end: the later of the two.
    const int32_t late1 = frameAtUs ? (int32_t) (now - (frameAtUs + frameUs)) : 0;
    const int32_t late2 = (dmaWatchOn && dmaEofUs && ringExpectUs && frameUs > ringExpectUs) ? (int32_t) (now - (dmaEofUs + (frameUs - ringExpectUs))) : late1;
    const int32_t lateUs = late1 > late2 ? late1 : late2;
    const bool late = lateUs > (int32_t) RING_LATE_US;
    const int headMax = RING_HEAD_N + (lateUs > 0 ? (int) ((uint32_t) lateUs / RING_NODE_US) : 0);   // (a little late: the DMA that much further on, rightly)
    const uint32_t eof = dmaEofUs, start = frameAtUs;
    const bool have = eof && start && (int32_t) (eof - start) > 0 && eof - start < 65000;
    const uint32_t off = have ? eof - start : 0;
    if (ringLogN < RING_LOG_N) ringLog[ringLogN++] = (uint16_t) off;
    if (ringStartUs && eof && (int32_t) (eof - ringStartUs) > 0 && eof - ringStartUs < 65000) {   // the slip counter: this frame's DMA, from our start to its EOF
        const uint32_t dur = eof - ringStartUs;
        if (!ringDurMin || dur < ringDurMin) ringDurMin = dur;
        else if (dur - ringDurMin > RING_SLIP_US) { ringSlips++; ringSlipsAll++; if (dur - ringDurMin > ringSlipMax) ringSlipMax = dur - ringDurMin; }
    }
    // Where the DMA is (before the re-sync): which ring, which descriptor of it - the bench's view of the slips.
    int on = -1, idx = -1;
    if (ringCh >= 0) {
        const uint32_t cur = GDMA.channel[ringCh].out.dscr;
        for (int i = 0; i < 3 && on < 0; ++i) {
            if (!flipChain[i]) continue;
            const uint32_t b = (uint32_t) flipChain[i];
            if (cur >= b && cur < b + flipNodeN * sizeof(FlipNode)) { on = i; idx = (int) ((cur - b) / sizeof(FlipNode)); }
        }
        ringLastOn = on; ringLastIdx = idx;
        if (!(on == flipShown && idx >= 0 && idx <= headMax)) ringOutN++;
    }
    if (dmaWatchOn) {                                  // (the EOF rule: counted, not acted on)
        if (!ringExpectUs) { if (have && ++ringLearnN >= 2) ringExpectUs = off; }
        else {
            const bool out = !have || (off > ringExpectUs ? off - ringExpectUs : ringExpectUs - off) > RING_OFF_US;
            if (out) { if (++ringOffN == RING_OFF_N) ringHealsEof++; }
            else ringOffN = 0;
        }
    }
    if (late) { ringLateN++; ringSkipped++; return; }  // (the blank may be over: the DMA runs on, chained; the next frame end)
    uint8_t want = flipWant;
    if (!flipChain[want]) want = flipShown;
    ringResync(want); ringResyncs++;
    if (want != flipShown) { flipShown = want; flipDoneN++; ringSwitches++; }
}
// From the loop: rings for buffers made since; the panel restarted should the frames stop, or the EOFs, for 150 ms.
static void ringTick() {
    if (!ringOn) return;
    if (flipWant == flipShown) ringEnsure();
    const uint32_t now = millis();
    if (frameEnds != ringSeenEnds) { ringSeenEnds = frameEnds; ringEndsAt = now; }   // (each on its own clock: a pass may see one without the other)
    if (dmaEofUs != ringSeenEof) { ringSeenEof = dmaEofUs; ringEofAt = now; }
    if (!ringEndsAt || !ringEofAt) { ringEndsAt = ringEofAt = now; return; }
    const bool endsStopped = now - ringEndsAt > 150, eofStopped = dmaWatchOn && now - ringEofAt > 150;
    if (!endsStopped && !eofStopped) return;
    if (now - ringSeenAt < 150) return;
    ringSeenAt = now; ringRescues++;
    if (endsStopped) ringRestart();                    // (no frame ends: the engine itself has stopped - from here, now)
    else ringHealAsk = true;                           // (the frames run, the DMA does not: at the next frame end, in the blank)
}
static std::string ringStatusJson() {
    char b[360];
    snprintf(b, sizeof b, ",\"ring\":{\"on\":%d,\"why\":\"%s\",\"ch\":%d,\"starts\":%lu,\"resyncs\":%lu,\"skipped\":%lu,\"out\":%lu,\"switches\":%lu,\"rescues\":%lu,\"heals\":%lu,\"eof_off\":%lu,\"late\":%lu,\"expect_us\":%lu,\"slips_all\":%lu,\"gap_base\":%lu,\"isr_min_us\":%lu,\"at\":[%d,%d],\"log\":[",
             ringOn ? 1 : 0, ringWhy, ringCh, (unsigned long) ringStarts, (unsigned long) ringResyncs, (unsigned long) ringSkipped, (unsigned long) ringOutN, (unsigned long) ringSwitches, (unsigned long) ringRescues,
             (unsigned long) ringHeals, (unsigned long) ringHealsEof, (unsigned long) ringLateN, (unsigned long) ringExpectUs,
             (unsigned long) dmaSlipsAll, (unsigned long) dmaGapBase, (unsigned long) ringDurMin, (int) ringLastOn, (int) ringLastIdx);
    std::string out = b;
    const int n = ringLogN < RING_LOG_N ? ringLogN : RING_LOG_N;
    for (int i = 0; i < n; ++i) { char e[12]; snprintf(e, sizeof e, "%s%u", i ? "," : "", (unsigned) ringLog[i]); out += e; }
    out += "]}";
    return out;
}
