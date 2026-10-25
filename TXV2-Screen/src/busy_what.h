// WHAT THE LOOP IS DOING (25 Oct 2026, evening). Malcolm, scrolling the background pictures on the ring + phase-tracker
// build: "a little shimmy sideways just after pressing the button and just before the new image appeared - not every
// time, but quite often" - slips of 5-15 us (70-200 pixels for one frame), below the slip counter's 15 us. The EOF
// interrupt (dma_watch.h) reads this tag at every slip of 7 us or more and counts it by what the loop was doing (/perf
// "slipw": a count and a sum per tag, and the window's first 24 slips with their size and moment), so one run names the
// step. Set by Busy objects in the big movers; nested ones restore the tag they found.
#pragma once
#include <stdint.h>
enum : uint8_t { BUSY_IDLE = 0, BUSY_SD = 1, BUSY_WB = 2, BUSY_COPY = 3, BUSY_REST = 4, BUSY_DRAW = 5, BUSY_NVS = 6, BUSY_BG = 7, BUSY_PRESENT = 8, BUSY_HANDLE = 9, BUSY_N = 10 };
static volatile uint8_t busyWhat = BUSY_IDLE;
struct Busy { uint8_t was; explicit Busy(uint8_t w) : was(busyWhat) { busyWhat = w; } ~Busy() { busyWhat = was; } };
