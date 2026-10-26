// THE DMA COPY (1.11.126, 26 Oct 2026) - the big moves between the panel's buffers made by a GDMA channel pair in
// memory-to-memory mode, not by the CPU through its cache.
//
// What the CPU writes to the PSRAM sits in the cache until it is written back, and a write-back of fresh rows is a burst
// of PSRAM writes that starves the panel's own DMA: the rest of that frame is shifted sideways - the flicker of 24-25 Oct
// (wbPaced's 256-byte pieces took it down to ~1 us a frame, "much more rare"). Measured on the twin (/stall, 26 Oct morning):
//   - a DMA copy PSRAM to PSRAM at 25 MB/s, the panel's channel at priority 5 (ours at 0): 0.25 us a frame, the idle floor;
//   - the canvas's rows to both panel buffers that way, 480 rows: 96 ms, 0-1 us a frame, worst frame 1 us
//     (the CPU's copy with its write-backs: 211 ms, 1.3-1.9 us a frame, worst 4-5 us);
//   - a clean write-back (the cache operation alone, no line dirty) costs the panel nothing: 100 000 of them, 0.36 us a frame;
//   - an SRAM to PSRAM stream at 46 MB/s starves the panel even at priority 5 (frames of 60 ms and more, 23 re-syncs):
//     the PSRAM's write path is the limit, not the arbiter. So the copies are PSRAM to PSRAM, which paces itself.
// The cache is touched by nothing: the source rows are written back first (the canvas's: mostly clean lines after a draw,
// a walk - the dirty ones are at most the cache's 64 kB, spread), the destination is written by the DMA alone. Where the
// CPU must still read a panel buffer (the canvas catching up after a rotation, by DMA too; a compose row's partial lines;
// /fb) the lines are invalidated first: a cached line of a DMA-written row is stale.
// The panel's GDMA channel is raised to priority 5 when the pair is made (gdma_ll_tx_set_priority): the panel is served
// first at every arbitration, our copy takes what is left. The CPU's copy is the fall-back of every DMA copy that does not
// come (a timeout, counted).
// 1.11.128 (26 Oct, midday): OFF BY DEFAULT. On the desk, with the DMA copy on, Malcolm saw MORE flicker than before ("rather
// worse"; with the panel's channel back at priority 0 "very badly, seldom stable for more than a moment"; off again: "much
// better, just the occasional flicker after changing screens"), while every counter here read clean - the bench's slip
// counters only look at frames whose EOF gap is under 20 ms, so a copy that holds the panel's DMA for longer than that is
// invisible to them (dmaHuge counts those since 1.11.128). The pref "dmacopy" (0) and /stall?kind=dmacopy&kb=1 switch it
// on at run time for the bench; everything below stays for the next experiments.
// Bench probes (/stall, the 16 MB builds): m2m (SRAM -> PSRAM), m2mp (PSRAM -> PSRAM), m2mrows (by way of a 16 kB SRAM
// staging buffer), m2mcanvas / m2mcanvasw (the canvas to both panel buffers, the band written back gently / in one call),
// wbnop (clean write-backs), lcdpri (the panel channel's priority), dcstat (everything above).
#pragma once
#include <Arduino.h>
#include <esp_heap_caps.h>
#include "esp_private/gdma.h"
#include "hal/dma_types.h"
#include "hal/gdma_ll.h"
#include "soc/gdma_struct.h"
#include "rom/cache.h"

static gdma_channel_handle_t dcTx = nullptr, dcRx = nullptr;
static int dcTxCh = -1, dcRxCh = -1, dcLcdCh = -1;
static const int DC_DESC_N = 32;                       // rows a start: 32 full rows = 51 kB, ~2 ms
static int dcRowsPerStart = DC_DESC_N;                 // (bench: /stall?kind=dcrows&kb=N - fewer rows a start, a breath for the panel between)
static uint32_t dcBlock = 64, dcBurst = 1;             // (bench: dcblock&kb=16|32|64 the PSRAM block of our channels; dcburst&kb=0|1 their data bursts)
static const uint32_t DC_LCD_PRI = 5;                  // the panel's channel: above ours (0)
static dma_descriptor_t *dcTxD = nullptr, *dcRxD = nullptr;
static volatile bool dcDone = true;
static volatile uint32_t dcCopies = 0, dcEofs = 0, dcTimeouts = 0, dcRows = 0, dcUsMax = 0;
static bool dcOn = true;                               // the pref "dmacopy" (1): the copies go by DMA
static uint32_t dcAlign = 64;                          // the PSRAM transfer block: every buffer is 64-aligned (checked at the start)
static const char *dcWhy = "off";
static uint8_t *dcStage = nullptr;                     // 16 kB in SRAM: the staging buffer of the bench's m2mrows
static uint8_t *dcPs = nullptr, *dcPs2 = nullptr;      // 256 kB each in PSRAM: the bench's destination and source
static const size_t DC_STAGE = 16384, DC_PS = 262144;

static bool IRAM_ATTR dcOnRxEof(gdma_channel_handle_t, gdma_event_data_t *, void *) { dcDone = true; dcEofs = dcEofs + 1; return false; }

static bool dmaCopyInit() {
    if (dcTx) return true;
    if (!dcOn) { dcWhy = "off (pref)"; return false; }
    gdma_channel_alloc_config_t tx = {}; tx.direction = GDMA_CHANNEL_DIRECTION_TX; tx.flags.reserve_sibling = 1;
    if (gdma_new_channel(&tx, &dcTx) != ESP_OK) { dcWhy = "no tx channel"; dcTx = nullptr; return false; }
    gdma_channel_alloc_config_t rx = {}; rx.direction = GDMA_CHANNEL_DIRECTION_RX; rx.sibling_chan = dcTx;
    if (gdma_new_channel(&rx, &dcRx) != ESP_OK) { dcWhy = "no rx channel"; gdma_del_channel(dcTx); dcTx = nullptr; dcRx = nullptr; return false; }
    gdma_trigger_t trig = GDMA_MAKE_TRIGGER(GDMA_TRIG_PERIPH_M2M, 0);
    uint32_t mask = 0; gdma_get_free_m2m_trig_id_mask(dcTx, &mask); if (mask) trig.instance_id = __builtin_ctz(mask);
    if (gdma_connect(dcRx, trig) != ESP_OK || gdma_connect(dcTx, trig) != ESP_OK) { dcWhy = "no m2m trigger"; gdma_del_channel(dcRx); gdma_del_channel(dcTx); dcTx = dcRx = nullptr; return false; }
    gdma_transfer_ability_t ab = {}; ab.sram_trans_align = 4; ab.psram_trans_align = dcAlign;
    gdma_set_transfer_ability(dcTx, &ab); gdma_set_transfer_ability(dcRx, &ab);
    gdma_rx_event_callbacks_t cbs = {}; cbs.on_recv_eof = dcOnRxEof;
    if (gdma_register_rx_event_callbacks(dcRx, &cbs, nullptr) != ESP_OK) { dcWhy = "no rx callback"; gdma_del_channel(dcRx); gdma_del_channel(dcTx); dcTx = dcRx = nullptr; return false; }
    gdma_get_channel_id(dcTx, &dcTxCh); gdma_get_channel_id(dcRx, &dcRxCh);
    dcTxD = (dma_descriptor_t *) heap_caps_calloc(DC_DESC_N, sizeof(dma_descriptor_t), MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    dcRxD = (dma_descriptor_t *) heap_caps_calloc(DC_DESC_N, sizeof(dma_descriptor_t), MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    if (!dcTxD || !dcRxD) { dcWhy = "no descriptors"; gdma_del_channel(dcRx); gdma_del_channel(dcTx); dcTx = dcRx = nullptr; return false; }
    if (ringDma && gdma_get_channel_id(ringDma, &dcLcdCh) == ESP_OK && dcLcdCh >= 0) gdma_ll_tx_set_priority(&GDMA, dcLcdCh, DC_LCD_PRI); else dcLcdCh = -1;
    dcWhy = "on";
    return true;
}
static inline bool dmaReady() { return dcOn && dcTx != nullptr && dcDone; }   // (dcOn: switched at run time too - /stall?kind=dmacopy&kb=0|1, kept in the pref)
// One start: the descriptors are filled by the caller (count n), both channels started, the copy waited for (a 51 kB copy is
// ~2 ms). False = it did not come in 50 ms (counted; the pair is reset so the next copy can go).
static bool dcRun(int n) {
    dcDone = false;
    gdma_reset(dcRx); gdma_reset(dcTx);
    gdma_start(dcRx, (intptr_t) dcRxD); gdma_start(dcTx, (intptr_t) dcTxD);
    const uint32_t t0 = micros();
    while (!dcDone) { if (micros() - t0 > 50000) { dcTimeouts++; gdma_stop(dcTx); gdma_stop(dcRx); dcDone = true; return false; } }
    const uint32_t us = micros() - t0; if (us > dcUsMax) dcUsMax = us;
    dcCopies++;
    return true;
}
static inline void dcDesc(int i, void *dst, const void *src, size_t len, bool last) {
    dcTxD[i].dw0.size = len; dcTxD[i].dw0.length = len; dcTxD[i].dw0.suc_eof = last; dcTxD[i].dw0.owner = DMA_DESCRIPTOR_BUFFER_OWNER_DMA;
    dcTxD[i].buffer = (void *) src; dcTxD[i].next = last ? nullptr : &dcTxD[i + 1];
    dcRxD[i].dw0.size = len; dcRxD[i].dw0.length = 0; dcRxD[i].dw0.suc_eof = 0; dcRxD[i].dw0.owner = DMA_DESCRIPTOR_BUFFER_OWNER_DMA;
    dcRxD[i].buffer = dst; dcRxD[i].next = last ? nullptr : &dcRxD[i + 1];
}
// Rows y..y+h-1, pixels x0..x1-1 (both multiples of 32: whole 64-byte lines) of src to the same place in dst, both panel-sized
// buffers in the PSRAM, DC_DESC_N rows a start. The caller sees to the cache: the source's rows written back where the CPU
// drew them, the destination's lines invalidated where the CPU will read them. False = not done (no pair, or a copy that
// did not come): the caller copies by hand, the whole range.
static bool dmaCopyRows(uint16_t *dst, const uint16_t *src, int x0, int x1, int y, int h) {
    if (!dmaReady() || x1 <= x0 || h <= 0 || (x0 & 31) || (x1 & 31) || ((uintptr_t) dst & 63) || ((uintptr_t) src & 63)) return false;
    const size_t bytes = (size_t) (x1 - x0) * 2;
    if (bytes > 4032) return false;
    for (int r = y; r < y + h; ) {
        const int n = min(dcRowsPerStart, y + h - r);
        for (int i = 0; i < n; ++i) dcDesc(i, dst + (r + i) * W + x0, src + (r + i) * W + x0, bytes, i == n - 1);
        if (!dcRun(n)) return false;
        dcRows += n; r += n;
    }
    return true;
}
// (1.11.127) Rows y..y+h-1 of dst, pixels x0..x1-1, all from ONE row segment srcRow (a fill: its first row, filled by the CPU
// and written back) - one descriptor per row, the same source for each.
static bool dmaFillRows(uint16_t *dst, const uint16_t *srcRow, int x0, int x1, int y, int h) {
    if (!dmaReady() || x1 <= x0 || h <= 0 || (x0 & 31) || (x1 & 31) || ((uintptr_t) dst & 63) || ((uintptr_t) srcRow & 63)) return false;
    const size_t bytes = (size_t) (x1 - x0) * 2;
    if (bytes > 4032) return false;
    for (int r = y; r < y + h; ) {
        const int n = min(dcRowsPerStart, y + h - r);
        for (int i = 0; i < n; ++i) dcDesc(i, dst + (r + i) * W + x0, srcRow, bytes, i == n - 1);
        if (!dcRun(n)) return false;
        dcRows += n; r += n;
    }
    return true;
}
// (1.11.127) Before a DMA writes rows of a buffer the CPU draws into (the canvas, the layer): the cache's lines of pixels
// x0..x1-1 (whole 64-byte lines, every one entirely inside what is about to be overwritten) are dropped - a dirty one holds
// old content the DMA replaces, a clean one would be stale afterwards. Whole rows go in one call.
static void dmaDropLines(uint16_t *fb, int x0, int x1, int y, int h) {
    if (x0 == 0 && x1 == W) { Cache_Invalidate_Addr((uint32_t) (fb + y * W), (uint32_t) h * W * 2); return; }
    for (int r = y; r < y + h; ++r) Cache_Invalidate_Addr((uint32_t) (fb + r * W + x0), (uint32_t) (x1 - x0) * 2);
}
// A plain copy of n bytes (a multiple of 64; dst and src 64-aligned in the PSRAM, 4-aligned in SRAM), 4032 bytes a descriptor.
static bool dmaCopy(void *dst, const void *src, size_t n) {
    if (!dmaReady() || !n || (n & 63) || n > (size_t) DC_DESC_N * 4032) return false;
    int i = 0; size_t off = 0;
    while (off < n) { const size_t len = min((size_t) 4032, n - off); dcDesc(i, (uint8_t *) dst + off, (const uint8_t *) src + off, len, off + len >= n); off += len; ++i; }
    return dcRun(i);
}
static void dmaCopyJson(std::string &out) {           // (/status "dmacopy")
    char b[200]; snprintf(b, sizeof b, "\"dmacopy\":{\"why\":\"%s\",\"copies\":%lu,\"rows\":%lu,\"timeouts\":%lu,\"us_max\":%lu,\"lcd_pri\":%u}", dcWhy, (unsigned long) dcCopies, (unsigned long) dcRows, (unsigned long) dcTimeouts, (unsigned long) dcUsMax,
             dcLcdCh >= 0 ? (unsigned) GDMA.channel[dcLcdCh].out.pri.tx_pri : 0u);
    out += b;
}

#ifdef LDRC_FULL
static bool dcBuffers() {
    if (!dcStage) dcStage = (uint8_t *) heap_caps_aligned_alloc(64, DC_STAGE, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    if (!dcPs) { dcPs = (uint8_t *) heap_caps_aligned_alloc(64, DC_PS, MALLOC_CAP_SPIRAM); if (dcPs) { memset(dcPs, 0x11, DC_PS); Cache_WriteBack_Addr((uint32_t) dcPs, DC_PS); } }
    if (!dcPs2) { dcPs2 = (uint8_t *) heap_caps_aligned_alloc(64, DC_PS, MALLOC_CAP_SPIRAM); if (dcPs2) { memset(dcPs2, 0x22, DC_PS); Cache_WriteBack_Addr((uint32_t) dcPs2, DC_PS); } }
    if (dcStage) memset(dcStage, 0x5A, DC_STAGE);
    return dcStage && dcPs && dcPs2;
}
#endif
// The bench probes. `kb` is kilobytes for m2m/m2mp, rows for m2mrows/m2mcanvas, thousands of operations for wbnop, the priority for lcdpri.
static bool dmaCopyProbe(const String &kind, int kb, uint32_t &us, char *extra, size_t extraN) {
    extra[0] = 0;
    if (kind == "lcdpri") {                            // the panel channel's priority, with or without our pair
        if (dcLcdCh < 0) { int id = -1; if (ringDma && gdma_get_channel_id(ringDma, &id) == ESP_OK && id >= 0) dcLcdCh = id; }
        if (dcLcdCh < 0 || kb < 0 || kb > 15) return false;
        gdma_ll_tx_set_priority(&GDMA, dcLcdCh, (uint32_t) kb); us = kb; return true;
    }
    if (kind == "dmacopy") { dcOn = kb != 0; if (dcOn) dmaCopyInit(); us = dcOn; snprintf(extra, extraN, ",\"why\":\"%s\"", dcWhy); return true; }   // the A/B at run time: 0 = every copy by the CPU, as 1.11.125 (main.cpp keeps it in the pref)
    if (kind == "dcrows") { if (kb >= 1 && kb <= DC_DESC_N) dcRowsPerStart = kb; us = dcRowsPerStart; return true; }
    if (kind == "dcburst") { if (dcTxCh < 0) return false; dcBurst = kb != 0; gdma_ll_tx_enable_data_burst(&GDMA, dcTxCh, dcBurst); gdma_ll_rx_enable_data_burst(&GDMA, dcRxCh, dcBurst); us = dcBurst; return true; }
    if (kind == "dcblock") { if (dcTxCh < 0 || (kb != 16 && kb != 32 && kb != 64)) return false; dcBlock = kb; const uint32_t ix = kb == 64 ? GDMA_LL_EXT_MEM_BK_SIZE_64B : kb == 32 ? GDMA_LL_EXT_MEM_BK_SIZE_32B : GDMA_LL_EXT_MEM_BK_SIZE_16B; gdma_ll_tx_set_block_size_psram(&GDMA, dcTxCh, ix); gdma_ll_rx_set_block_size_psram(&GDMA, dcRxCh, ix); us = kb; return true; }
    if (kind == "dcstat") {
        snprintf(extra, extraN, ",\"why\":\"%s\",\"tx\":%d,\"rx\":%d,\"lcd\":%d,\"copies\":%lu,\"rows\":%lu,\"eofs\":%lu,\"timeouts\":%lu,\"us_max\":%lu,\"align\":%lu,\"fb\":[%lu,%lu,%lu],\"canvas\":%lu,\"lcdpri\":%u",
                 dcWhy, dcTxCh, dcRxCh, dcLcdCh, (unsigned long) dcCopies, (unsigned long) dcRows, (unsigned long) dcEofs, (unsigned long) dcTimeouts, (unsigned long) dcUsMax, (unsigned long) dcAlign,
                 (unsigned long) ((uintptr_t) flipFb[0] & 63), (unsigned long) ((uintptr_t) flipFb[1] & 63), (unsigned long) ((uintptr_t) flipFb[2] & 63), (unsigned long) ((uintptr_t) pageFb & 63),
                 dcLcdCh >= 0 ? (unsigned) GDMA.channel[dcLcdCh].out.pri.tx_pri : 0u);
        return true;
    }
#ifdef LDRC_FULL
    if (kind == "wbnop") {                             // clean write-backs of 256 bytes, kb thousand of them, over a buffer written back long ago
        if (!dcBuffers()) return false;
        const uint32_t t0 = micros();
        for (int i = 0; i < kb * 1000; ++i) Cache_WriteBack_Addr((uint32_t) (dcPs + ((size_t) i * 256) % DC_PS), 256);
        us = micros() - t0;
        return true;
    }
    if (!dmaCopyInit() || !dcBuffers()) return false;
    if (kind == "m2m" || kind == "m2mp") {              // kb kilobytes, 16 kB a copy
        const uint8_t *src = kind == "m2m" ? dcStage : dcPs2;
        size_t done = 0, off = 0; bool ok = true;
        const uint32_t t0 = micros();
        while (done < (size_t) kb * 1024 && ok) { ok = dmaCopy(dcPs + off, src + (kind == "m2m" ? 0 : off), DC_STAGE); off = (off + DC_STAGE) % DC_PS; done += DC_STAGE; }
        us = micros() - t0;
        snprintf(extra, extraN, ",\"kB_s\":%lu", us ? (unsigned long) ((uint64_t) done * 1000000 / us / 1024) : 0ul);
        return ok;
    }
    if (kind == "m2mrows") {                            // kb rows of the canvas to the buffer on show: the CPU reads 8 rows into the staging buffer, the DMA writes them
        uint16_t *dst = flipOk ? flipFb[flipShown] : nullptr;
        if (!dst || !pageFb || dst == pageFb) return false;
        const int rows = kb > 0 ? min(kb, (int) H) : H; bool ok = true;
        const uint32_t t0 = micros();
        for (int r = 0; r < rows && ok; r += 8) {
            const int n = min(8, rows - r);
            memcpy(dcStage, pageFb + r * W, (size_t) n * W * 2);
            ok = dmaCopy(dst + r * W, dcStage, (size_t) n * W * 2);
        }
        us = micros() - t0;
        snprintf(extra, extraN, ",\"rows\":%d", rows);
        return ok;
    }
    if (kind == "m2mcanvas" || kind == "m2mcanvasw") {   // kb rows of the canvas to every panel buffer but the canvas, as present does - the band written back first (gently, or in one call: m2mcanvasw), then the DMA copies it PSRAM to PSRAM
        if (!flipOk || !pageFb) return false;
        const int rows = kb > 0 ? min(kb, (int) H) : H; bool ok = true; int copies = 0;
        const uint32_t t0 = micros();
        for (int r = 0; r < rows && ok; r += 8) {
            const int n = min(8, rows - r); const size_t bytes = (size_t) n * W * 2;
            if (kind == "m2mcanvasw") Cache_WriteBack_Addr((uint32_t) (pageFb + r * W), bytes); else wbPaced((uint32_t) (pageFb + r * W), (uint32_t) bytes);
            for (int i = 0; i < 3 && ok; ++i) { if (i == flipCanvas || !flipFb[i] || flipFb[i] == pageFb) continue; ok = dmaCopy(flipFb[i] + r * W, pageFb + r * W, bytes); copies++; }
        }
        us = micros() - t0;
        snprintf(extra, extraN, ",\"rows\":%d,\"copies\":%d", rows, copies);
        return ok;
    }
#endif
    return false;
}
