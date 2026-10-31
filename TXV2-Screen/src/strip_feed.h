// THE STRIPS (26 Oct 2026, evening) - the panel reads the chip's own RAM; a DMA copy feeds it from the PSRAM picture.
//
// Everything of 24-26 Oct tamed the PSRAM traffic that starves the panel's DMA (paced copies, gentle write-backs, the
// flip, the code moved into the PSRAM), and the flicker went from half the page changes to "very rare" - but every
// picture the CPU draws still shares the bus with the panel, and any hold over ~7 us shifts a frame sideways. Nothing
// paced can reach zero. What can: the panel never reading the PSRAM at all. This is Espressif's "bounce buffer" scheme
// (esp_lcd's RGB driver since IDF 5.0, bounce_buffer_size_px), done on our own frame ring (src/frame_ring.h):
//   - the panel's DMA runs round a ring of STRIP_K strips of STRIP_L lines each, in INTERNAL RAM (3 x 12.8 kB): slot 0, 1,
//     2, 0, 1, 2 ... with an EOF interrupt at the end of every slot. The engine chains the frames (auto next frame) as before,
//     60 strips a frame, 20 turns of the ring, strip s always in slot s % 3. The frame end re-syncs it at slot 0, as the ring
//     re-synced at the frame buffer's head.
//   - at each slot's EOF the strip just shown is replaced: a GDMA memory-to-memory pair (src/dma_copy.h's kind, its own
//     channels) copies strip s + 3 of the frame from the PSRAM picture into that slot - 12.8 kB in ~0.3 ms, with 0.9 ms in
//     hand before the panel comes round to it. The copy may be held off the PSRAM by the CPU's drawing as long as it likes
//     within that; the panel reads its RAM meanwhile and nothing shifts. (A fill that is NOT done when its slot comes round
//     is counted: strips "late" - the panel shows the slot's old lines for one pass, a repeated band, not a shift.)
//   - the flip (page_flip.h) costs nothing: the next frame's first strips are fetched from the buffer WANTED when the ring
//     fetches strip 60 (the next frame's 0), and the frame boundary is the switch - never half a frame from each.
//   - the pacing rests of the twin (psram_pace.h) are off while the strips run: the CPU may draw at full speed.
// Costs: ~39 kB of internal RAM, ~2000 small interrupts a second (two per strip), the pair's channels. What it cannot cure:
// a flash write (NVS, an update) stops the PSRAM for everyone, the feeder too - the panel then repeats its three strips
// for the duration (the quiet-time scheduling of NVS writes stands).
// The pref "strips" (0): /stall?kind=strips&kb=1 for the next start; /status "strips"; kind=stripstat.
#pragma once
#include <Arduino.h>
#include <esp_heap_caps.h>
#include "esp_private/gdma.h"
#include "hal/dma_types.h"
#include "hal/gdma_ll.h"
#include "hal/lcd_ll.h"
#include "soc/gdma_struct.h"
#include "soc/lcd_cam_struct.h"
#include "rom/cache.h"

static const int STRIP_L = 4;                            // lines a strip (4: 6.4 kB a slot, 19.2 kB of internal RAM in all - 8 lines took 38 kB and left the films and TLS short)
static const int STRIP_K = 3;                            // slots in the ring (must divide the 60 strips of a frame)
static const int STRIP_N = 480 / STRIP_L;                // strips a frame
static const size_t STRIP_BYTES = (size_t) 800 * STRIP_L * 2;   // 12,800
static const int STRIP_NODES = 2;                        // descriptors a slot: 3200 bytes = 2 lines each (a node holds 4095 at most)
static const size_t STRIP_NODE_BYTES = STRIP_BYTES / STRIP_NODES;

static uint8_t *stripBuf[STRIP_K] = { nullptr, nullptr, nullptr };
static FlipNode *stripNodes = nullptr;                   // the panel's ring: STRIP_K * STRIP_NODES nodes, closed
static gdma_channel_handle_t sfTx = nullptr, sfRx = nullptr; static int sfTxCh = -1, sfRxCh = -1;
static dma_descriptor_t *sfTxD = nullptr, *sfRxD = nullptr;
static const char *stripWhy = "off";
static int stripWant = 0;                                // the pref, resolved (main.cpp setup)
static bool stripArmed = false; static uint32_t stripStrikes = 0;   // (main.cpp) this start's strike stands until 20 s have passed
static volatile int stripCur = 0;                        // the strip the panel's DMA is on (its EOF comes next)
static const uint16_t *volatile stripFrameFb = nullptr;  // this frame's picture
static const uint16_t *volatile stripNextFb = nullptr;   // the next frame's (latched when its first strip is fetched)
static volatile uint8_t stripNextIdx = 0;
static volatile bool sfBusy = false;                     // a fill is running
static volatile bool sfFilled[STRIP_K] = { true, true, true };
static volatile int sfQSlot[STRIP_K]; static const uint16_t *volatile sfQSrc[STRIP_K]; static volatile int sfQn = 0, sfQi = 0;   // fills waiting (the pair takes one at a time)
static volatile int sfSlot = -1;                         // the slot being filled
static volatile uint32_t stripFills = 0, stripLate = 0, stripQMax = 0, stripEofs = 0, stripFrames = 0, stripResyncs = 0, stripDrops = 0, stripFillUsMax = 0, sfStartUs = 0;
// (1.11.152) A late strip is a band repeated for one pass - a flicker the eye sees. By what the loop was doing at that
// moment (busy_what.h), and the last eight with their time: 31 Oct, the yellow transmitter's scrolling session showed
// strips late 7 and Malcolm "just a few flickers" - the same number; which activity it is decides the next cure.
static volatile uint32_t stripLateBy[BUSY_N] = { 0 };
struct StripLateMark { uint8_t what; uint32_t ms; uint32_t seen; };
static StripLateMark stripLateLog[8]; static volatile uint32_t stripLateLogN = 0;

// The fill of one slot from the PSRAM: STRIP_NODES descriptor pairs, both channels reset and started by the registers (IRAM).
static void IRAM_ATTR sfStart(int slot, const uint16_t *src) {
    for (int i = 0; i < STRIP_NODES; ++i) {
        const bool last = i == STRIP_NODES - 1;
        sfTxD[i].dw0.size = STRIP_NODE_BYTES; sfTxD[i].dw0.length = STRIP_NODE_BYTES; sfTxD[i].dw0.suc_eof = last; sfTxD[i].dw0.owner = DMA_DESCRIPTOR_BUFFER_OWNER_DMA;
        sfTxD[i].buffer = (void *) ((const uint8_t *) src + i * STRIP_NODE_BYTES); sfTxD[i].next = last ? nullptr : &sfTxD[i + 1];
        sfRxD[i].dw0.size = STRIP_NODE_BYTES; sfRxD[i].dw0.length = 0; sfRxD[i].dw0.suc_eof = 0; sfRxD[i].dw0.owner = DMA_DESCRIPTOR_BUFFER_OWNER_DMA;
        sfRxD[i].buffer = stripBuf[slot] + i * STRIP_NODE_BYTES; sfRxD[i].next = last ? nullptr : &sfRxD[i + 1];
    }
    sfSlot = slot; sfFilled[slot] = false; sfBusy = true; sfStartUs = (uint32_t) esp_timer_get_time();
    gdma_ll_rx_reset_channel(&GDMA, sfRxCh); gdma_ll_tx_reset_channel(&GDMA, sfTxCh);
    gdma_ll_rx_set_desc_addr(&GDMA, sfRxCh, (uint32_t) sfRxD); gdma_ll_rx_start(&GDMA, sfRxCh);
    gdma_ll_tx_set_desc_addr(&GDMA, sfTxCh, (uint32_t) sfTxD); gdma_ll_tx_start(&GDMA, sfTxCh);
}
static void IRAM_ATTR sfQueue(int slot, const uint16_t *src) {
    if (!sfBusy) { sfStart(slot, src); return; }
    if (sfQn >= STRIP_K) { stripDrops++; return; }        // (cannot happen with three slots; counted if it does)
    const int at = (sfQi + sfQn) % STRIP_K; sfQSlot[at] = slot; sfQSrc[at] = src; sfQn = sfQn + 1;
    if ((uint32_t) sfQn > stripQMax) stripQMax = sfQn;
}
static bool IRAM_ATTR sfOnRxEof(gdma_channel_handle_t, gdma_event_data_t *, void *) {   // a fill done
    const uint32_t us = (uint32_t) esp_timer_get_time() - sfStartUs; if (us > stripFillUsMax) stripFillUsMax = us;
    if (sfSlot >= 0) sfFilled[sfSlot] = true;
    sfBusy = false; stripFills = stripFills + 1;
    if (sfQn > 0) { const int slot = sfQSlot[sfQi]; const uint16_t *src = sfQSrc[sfQi]; sfQi = (sfQi + 1) % STRIP_K; sfQn = sfQn - 1; sfStart(slot, src); }
    return false;
}
// The panel's DMA at the end of a slot: strip s shown; that slot gets strip s + 3 - of this frame, or of the next frame's
// picture (the buffer wanted, latched at its first strip). At strip 59 the frame's EOF is stamped for the watch
// (dma_watch.h: once a frame, as before), and the next frame's picture becomes this frame's.
static volatile uint32_t stripFixes = 0;                   // the counter corrected by the DMA's own register
static void IRAM_ATTR stripOnLcdEof() {                   // (dma_watch.h dispatches every EOF of the panel's channel here while the strips run)
    stripEofs = stripEofs + 1;
    int s = stripCur;
    // The slot just emptied is read from the DMA itself (the EOF descriptor's address): a counter alone could drift by one if
    // an EOF were served late, and then every strip of the frame would land in the wrong slot. The counter gives the turn.
    if (ringCh >= 0) {
        const uint32_t a = gdma_ll_tx_get_eof_desc_addr(&GDMA, ringCh), b = (uint32_t) stripNodes;
        if (a >= b && a < b + STRIP_K * STRIP_NODES * sizeof(FlipNode)) {
            const int hw = (int) ((a - b) / sizeof(FlipNode)) / STRIP_NODES;
            if (hw != s % STRIP_K) { stripFixes = stripFixes + 1; s = (s == 0 && hw == STRIP_K - 1) ? STRIP_N - 1 : (s / STRIP_K) * STRIP_K + hw; }   // (strip 59's EOF served after the frame end's re-sync: still strip 59)
        }
    }
    const int slot = s % STRIP_K;
    stripCur = (s + 1) % STRIP_N;
    int t = s + STRIP_K; const uint16_t *fb = stripFrameFb;
    if (t >= STRIP_N) {
        t -= STRIP_N;
        if (t == 0) { const uint8_t w = flipWant; stripNextFb = flipFb[w] ? flipFb[w] : stripFrameFb; stripNextIdx = flipFb[w] ? w : flipShown; }
        fb = stripNextFb ? stripNextFb : stripFrameFb;
    }
    if (!sfFilled[slot]) {                                 // (its fill was not done by the time the panel came round: a band repeated)
        stripLate++;
        const uint8_t w = busyWhat < BUSY_N ? busyWhat : BUSY_N - 1; stripLateBy[w] = stripLateBy[w] + 1;
        StripLateMark &m = stripLateLog[stripLateLogN % 8]; m.what = w; m.ms = (uint32_t) (esp_timer_get_time() / 1000); m.seen = busySeen; stripLateLogN = stripLateLogN + 1;
    }
    if (fb) sfQueue(slot, fb + (size_t) t * STRIP_L * 800);
    if (s == STRIP_N - 1) {
        stripFrames = stripFrames + 1;
        if (stripNextFb) { stripFrameFb = stripNextFb; if (flipShown != stripNextIdx) { flipShown = stripNextIdx; flipDoneN++; } }
        dmaOnEofFrame();                                   // (the frame's EOF to the watch, once a frame as before)
    }
}

// The frame end, strips on (from ringFrameEnd, a callback on time). The DMA reads the chip's RAM and cannot fall behind
// the engine, so nothing is restarted (the ring re-synced the PSRAM chain at every frame end; the first strips build
// tried the same and found the DMA already a slot ahead at every frame end - the restart was skipped 806 times in 806).
// What the frame end does is re-base the strip COUNTER from the DMA's own EOF register: the slot whose EOF came last tells
// which strip of the new frame comes next (strip 119's: 0; strip 0's, already past: 1) - an EOF interrupt lost to a flash
// write's interrupts-off would otherwise leave every fetch of the frame three strips out for good.
static volatile uint32_t stripResyncSkips = 0;
static void IRAM_ATTR stripResync() {
    int next = 0;
    if (ringCh >= 0) {
        const uint32_t a = gdma_ll_tx_get_eof_desc_addr(&GDMA, ringCh), b = (uint32_t) stripNodes;
        if (a >= b && a < b + STRIP_K * STRIP_NODES * sizeof(FlipNode)) next = ((int) ((a - b) / sizeof(FlipNode)) / STRIP_NODES + 1) % STRIP_K;
    }
    if (next != stripCur) stripResyncSkips = stripResyncSkips + 1;   // (counted: how often the counter was out when the frame ended)
    stripCur = next; stripResyncs = stripResyncs + 1;
}
// The change-over (the first frame end after stripSet): the ring started from slot 0 with the engine told to chain frames.
static void IRAM_ATTR stripStartNow() {
    lcd_ll_enable_auto_next_frame(&LCD_CAM, true);
    gdma_reset(ringDma); lcd_ll_stop(&LCD_CAM); lcd_ll_fifo_reset(&LCD_CAM);
    gdma_start(ringDma, (intptr_t) stripNodes);
    esp_rom_delay_us(1);
    lcd_ll_start(&LCD_CAM);
    stripCur = 0; stripOn = true; stripWhy = "on";
}
// STANDING DOWN (26 Oct, late): the update's secure connection to messiter.com wants ~70 kB of internal RAM in all, and
// with the strips' 19 kB gone from the pool its handshake failed ("the certificate was not accepted": the chain could not be
// parsed for want of memory; with the strips off the same check succeeded at once). So while the update page is up the
// strips stand down: at a frame end the panel goes back to the PSRAM chain (ringRestart), then the loop frees the buffers;
// they come back (stripBegin again) when the page has gone. The fresh start before a check or an install (LdrcUpdate
// freshStart -> beforeFreshStart) runs without them too (main.cpp "stripskip").
static volatile bool stripStopWanted = false, stripStopped = false; static uint32_t stripStops = 0;
static void IRAM_ATTR stripStopNow() { stripOn = false; ringRestart(); stripStopped = true; }
static void IRAM_ATTR stripFrameEnd(bool late) {         // (ringFrameEnd, strips on or armed)
    if (stripArm) { stripArm = false; stripStartNow(); return; }
    if (stripStopWanted) { stripStopWanted = false; stripStopNow(); return; }
    if (!late) stripResync();
}
static void stripRelease() {                             // (from the loop, once stopped) the buffers back to the heap; the pair's channels kept
    if (!stripStopped) return;
    stripStopped = false;
    const uint32_t t0 = millis(); while (sfBusy && millis() - t0 < 5) { }
    if (sfTx) { gdma_stop(sfTx); gdma_stop(sfRx); }
    sfBusy = false; sfQn = sfQi = 0;
    for (int i = 0; i < STRIP_K; ++i) { free(stripBuf[i]); stripBuf[i] = nullptr; }
    free(stripNodes); stripNodes = nullptr; free(sfTxD); sfTxD = nullptr; free(sfRxD); sfRxD = nullptr;
    stripStops++; stripWhy = "off (the update page)";
}

// From the loop, once the ring runs (ringOn): the strips made, the pair made, the slots pre-filled by the CPU, the panel's
// EOF callback taken over, the change-over armed for the next frame end.
static bool stripBegin() {
    if (stripOn || stripArm) return true;
    if (!ringOn || !ringDma || !flipNodes) { stripWhy = "no ring"; return false; }
    for (int i = 0; i < STRIP_K; ++i) if (!stripBuf[i] && !(stripBuf[i] = (uint8_t *) heap_caps_aligned_alloc(64, STRIP_BYTES, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL))) { stripWhy = "no internal RAM"; return false; }
    if (!stripNodes && !(stripNodes = (FlipNode *) heap_caps_calloc(STRIP_K * STRIP_NODES, sizeof(FlipNode), MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL))) { stripWhy = "no nodes"; return false; }
    if (!sfTxD && !(sfTxD = (dma_descriptor_t *) heap_caps_calloc(STRIP_NODES, sizeof(dma_descriptor_t), MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL))) { stripWhy = "no descriptors"; return false; }
    if (!sfRxD && !(sfRxD = (dma_descriptor_t *) heap_caps_calloc(STRIP_NODES, sizeof(dma_descriptor_t), MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL))) { stripWhy = "no descriptors"; return false; }
    for (int k = 0; k < STRIP_K; ++k) for (int i = 0; i < STRIP_NODES; ++i) {
        FlipNode &n = stripNodes[k * STRIP_NODES + i];
        n = flipNodes[0];                                  // (the driver's flags)
        n.size = STRIP_NODE_BYTES; n.length = STRIP_NODE_BYTES; n.sucEof = i == STRIP_NODES - 1; n.errEof = 0; n.owner = 1;
        n.buffer = stripBuf[k] + i * STRIP_NODE_BYTES;
        n.next = &stripNodes[(k * STRIP_NODES + i + 1) % (STRIP_K * STRIP_NODES)];
    }
    if (!sfTx) {
        gdma_channel_alloc_config_t tx = {}; tx.direction = GDMA_CHANNEL_DIRECTION_TX; tx.flags.reserve_sibling = 1;
        if (gdma_new_channel(&tx, &sfTx) != ESP_OK) { stripWhy = "no tx channel"; sfTx = nullptr; return false; }
        gdma_channel_alloc_config_t rx = {}; rx.direction = GDMA_CHANNEL_DIRECTION_RX; rx.sibling_chan = sfTx;
        if (gdma_new_channel(&rx, &sfRx) != ESP_OK) { stripWhy = "no rx channel"; gdma_del_channel(sfTx); sfTx = nullptr; sfRx = nullptr; return false; }
        gdma_trigger_t trig = GDMA_MAKE_TRIGGER(GDMA_TRIG_PERIPH_M2M, 0);
        uint32_t mask = 0; gdma_get_free_m2m_trig_id_mask(sfTx, &mask); if (mask) trig.instance_id = __builtin_ctz(mask);
        if (gdma_connect(sfRx, trig) != ESP_OK || gdma_connect(sfTx, trig) != ESP_OK) { stripWhy = "no m2m trigger"; gdma_del_channel(sfRx); gdma_del_channel(sfTx); sfTx = sfRx = nullptr; return false; }
        gdma_transfer_ability_t ab = {}; ab.sram_trans_align = 4; ab.psram_trans_align = 64;
        gdma_set_transfer_ability(sfTx, &ab); gdma_set_transfer_ability(sfRx, &ab);
        gdma_rx_event_callbacks_t cbs = {}; cbs.on_recv_eof = sfOnRxEof;
        if (gdma_register_rx_event_callbacks(sfRx, &cbs, nullptr) != ESP_OK) { stripWhy = "no rx callback"; gdma_del_channel(sfRx); gdma_del_channel(sfTx); sfTx = sfRx = nullptr; return false; }
        gdma_get_channel_id(sfTx, &sfTxCh); gdma_get_channel_id(sfRx, &sfRxCh);
    }
    // the first three strips of the frame on show, by the CPU (the picture is in the PSRAM already: lines invalidated first)
    const uint16_t *fb = flipFb[flipShown];
    if (!fb) { stripWhy = "no picture"; return false; }
    for (int k = 0; k < STRIP_K; ++k) { Cache_Invalidate_Addr((uint32_t) (fb + (size_t) k * STRIP_L * 800), STRIP_BYTES); memcpy(stripBuf[k], fb + (size_t) k * STRIP_L * 800, STRIP_BYTES); sfFilled[k] = true; }
    stripFrameFb = fb; stripNextFb = nullptr; stripNextIdx = flipShown; stripCur = 0; sfQn = sfQi = 0; sfBusy = false;
    stripArm = true; stripWhy = "armed";
    return true;
}
static void stripJson(std::string &out) {                // (/status "strips")
    char b[300];
    snprintf(b, sizeof b, "\"strips\":{\"on\":%d,\"why\":\"%s\",\"want\":%d,\"strikes\":%lu,\"stops\":%lu,\"frames\":%lu,\"fills\":%lu,\"late\":%lu,\"drops\":%lu,\"q_max\":%lu,\"fill_us_max\":%lu,\"rebases\":%lu,\"rebase_moves\":%lu,\"eofs\":%lu,\"fixes\":%lu,\"tx\":%d,\"rx\":%d}",
             stripOn ? 1 : 0, stripWhy, stripWant, (unsigned long) stripStrikes, (unsigned long) stripStops, (unsigned long) stripFrames, (unsigned long) stripFills, (unsigned long) stripLate, (unsigned long) stripDrops, (unsigned long) stripQMax, (unsigned long) stripFillUsMax,
             (unsigned long) stripResyncs, (unsigned long) stripResyncSkips, (unsigned long) stripEofs, (unsigned long) stripFixes, sfTxCh, sfRxCh);
    out += b;
    out.pop_back();                                        // (1.11.152) the late strips by what the loop was doing (busy_what.h's numbers), and the last eight [what, ms, seen]
    out += ",\"late_by\":[";
    for (int i = 0; i < BUSY_N; ++i) { char e[16]; snprintf(e, sizeof e, "%s%lu", i ? "," : "", (unsigned long) stripLateBy[i]); out += e; }
    out += "],\"late_log\":[";
    const uint32_t n = stripLateLogN, from = n > 8 ? n - 8 : 0;
    for (uint32_t i = from; i < n; ++i) { const StripLateMark &m = stripLateLog[i % 8]; char e[48]; snprintf(e, sizeof e, "%s[%u,%lu,%lu]", i > from ? "," : "", (unsigned) m.what, (unsigned long) m.ms, (unsigned long) m.seen); out += e; }
    out += "]}";
}
