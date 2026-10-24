// THE PAGE FLIP (1.11.115, 24 Oct 2026) - the 16 MB twin only.
//
// A whole-page copy into the buffer the panel is showing takes ~40 ms, longer than the twin's 29 ms frame, and it shares
// the PSRAM with the panel's DMA: about half the page changes slipped the picture sideways for a frame (Malcolm, 24 Oct:
// "a slight shake after changing screens about half of the time"). Resting the copy (1.11.114) cures the slip only when the
// rests are long, and a long copy into the shown buffer is seen half old, half new (a flicker). So the twin keeps TWO panel
// buffers: a big change is composed into the hidden one, slowly (rests every 8 rows), and the panel is pointed at it between
// two frames. Nothing half-drawn is ever scanned, and the copy's pace no longer matters.
//
// The pointing: IDF 4.4.7's RGB driver restarts the panel's DMA at every frame's end from its interrupt, at the start of
// its descriptor chain (lcd_rgb_panel_start_transmission), just after calling on_frame_trans_done. Each descriptor holds a
// buffer address; moving them all by (B - A) in that callback makes the next frame come from the other buffer. The chain
// (dma_nodes[], the struct's last member) lies beyond the fields Arduino_GFX's copy of the struct gets right, so it is
// FOUND, not assumed: the first candidate after user_ctx whose descriptors carry the frame buffer in order, end to end. Not
// found, or the frame ends not ticking: no flip, and the copies go straight to the shown buffer as in 1.11.114.
#pragma once
#include <Arduino.h>
#include <esp_heap_caps.h>

struct FlipNode {                        // IDF 4.4's dma_descriptor_t
    uint32_t size : 12, length : 12, reserved24 : 4, errEof : 1, reserved29 : 1, sucEof : 1, owner : 1;
    uint8_t *buffer;
    FlipNode *next;
};
static FlipNode *flipNodes = nullptr;
static uint32_t flipNodeN = 0;
static uint16_t *flipFb[2] = { nullptr, nullptr };    // [0] the driver's own buffer, [1] ours
static volatile uint8_t flipWant = 0, flipShown = 0;   // which buffer the panel should scan / scans
static volatile uint32_t flipDoneN = 0;               // flips made (in the interrupt)
static bool flipOk = false;
static const char *flipWhy = "off";                   // (/status: why there is no flip)

static void IRAM_ATTR flipFrameEnd() {
    const uint8_t want = flipWant;
    if (want == flipShown || !flipNodes) return;
    const intptr_t delta = (intptr_t) ((uint8_t *) flipFb[want] - (uint8_t *) flipFb[flipShown]);
    for (uint32_t i = 0; i < flipNodeN; ++i) flipNodes[i].buffer += delta;
    flipShown = want; flipDoneN++;
}

// Called once the panel runs: userCtxField = &panel->user_ctx, fb/fbSize/nodeN from the driver's struct (fields before
// user_ctx, which Arduino_GFX's copy has right).
static void flipFind(void **userCtxField, uint8_t *fb, size_t fbSize, size_t nodeN) {
    if (!fb || !fbSize || nodeN < 2 || nodeN > 4096) { flipWhy = "no panel"; return; }
    uint8_t *base = (uint8_t *) userCtxField + sizeof(void *);
    for (int off = 0; off <= 40; off += 4) {
        FlipNode *n = (FlipNode *) (base + off);
        if (n[0].buffer != fb) continue;
        size_t sum = 0; bool good = true;
        for (size_t i = 0; i < nodeN && good; ++i) {
            if (n[i].buffer != fb + sum || n[i].length == 0) good = false;
            if (i + 1 < nodeN && n[i].next != &n[i + 1]) good = false;
            sum += n[i].length;
        }
        if (!good || sum != fbSize) continue;
        flipNodes = n; flipNodeN = nodeN;
        break;
    }
    if (!flipNodes) { flipWhy = "chain not found"; return; }
    flipFb[0] = (uint16_t *) fb;
    flipFb[1] = (uint16_t *) heap_caps_aligned_calloc(64, 1, fbSize, MALLOC_CAP_SPIRAM);
    if (!flipFb[1]) { flipNodes = nullptr; flipWhy = "no memory"; return; }
    memcpy(flipFb[1], fb, fbSize);
    Cache_WriteBack_Addr((uint32_t) flipFb[1], fbSize);
    flipOk = true; flipWhy = "on";
}
