// WHAT THE LOOP IS DOING (25 Oct 2026, evening). Malcolm, scrolling the background pictures on the ring + phase-tracker
// build: "a little shimmy sideways just after pressing the button and just before the new image appeared - not every
// time, but quite often" - slips of 5-15 us (70-200 pixels for one frame), below the slip counter's 15 us. The EOF
// interrupt (dma_watch.h) reads this tag at every slip of 7 us or more and counts it by what the loop was doing (/perf
// "slipw": a count and a sum per tag, and the window's first 24 slips with their size and moment), so one run names the
// step. Set by Busy objects in the big movers; nested ones restore the tag they found.
#pragma once
#include <stdint.h>
enum : uint8_t { BUSY_IDLE = 0, BUSY_SD = 1, BUSY_WB = 2, BUSY_COPY = 3, BUSY_REST = 4, BUSY_DRAW = 5, BUSY_NVS = 6, BUSY_BG = 7, BUSY_PRESENT = 8, BUSY_HANDLE = 9,
                 BUSY_SERIAL = 10, BUSY_LINK = 11, BUSY_WIFI = 12, BUSY_PICS = 13, BUSY_FLIGHT = 14, BUSY_FILM = 15, BUSY_AUDIO = 16, BUSY_PREFS = 17, BUSY_TOUCH = 18, BUSY_TIMERS = 19, BUSY_FLIP = 20, BUSY_ENSURE = 21, BUSY_CLI = 22, BUSY_N = 23 };
static const char *const BUSY_NAMES[BUSY_N] = { "idle", "sd", "wb", "copy", "rest", "draw", "nvs", "bg", "present", "handle", "serial", "link", "wifi", "pics", "flight", "film", "audio", "prefs", "touch", "timers", "flip", "ensure", "cli" };
static volatile uint8_t busyWhat = BUSY_IDLE;
static volatile uint32_t busySeen = 0;                 // every tag entered since the EOF interrupt last looked (a short mover that ended before the EOF still shows here)
struct Busy { uint8_t was; explicit Busy(uint8_t w) : was(busyWhat) { busyWhat = w; busySeen |= 1u << w; } ~Busy() { busyWhat = was; } };
