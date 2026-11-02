// hold_watch.h - (1.11.164, 2 Nov 2026) THE HOLD WATCH: who holds this core's interrupts, and for how long.
//
// The update page lost whole frames while the files came down and before (33 in two minutes on the green transmitter,
// about one a second in bursts), and the touch poll stalled 47 ms in the same run - its interrupt timing out. So
// interrupts on the panel's core were held off a frame at a time, and nothing run alone from the loop (a secure fetch,
// 2 MB written to the card, a card read, a PSRAM burst, a preference written, 256 kB read from the flash) did it, with
// the strips on or off. Whatever it is happens in the install's own pattern of work: the updater's task on core 0 and
// the loop together. This watch catches it in the act: a hardware timer interrupt every millisecond on this core; a
// gap between two ticks of more than 4 ms means the interrupt could not run - interrupts held, or a longer interrupt
// ahead of it. Each hold is counted, binned, and the last sixteen kept with the moment, the loop's busy tag and the
// updater's phase (updPhase, set by update_device.h: 1 connecting, 3 reading the connection, 4 writing the card,
// 5 reading the card back, 6 writing the flash, 7 reading the flash back; 11-14 a job's kind with nothing finer).
// /status "holds".
#pragma once
#include <Arduino.h>
#include <esp_timer.h>
#include "busy_what.h"

static volatile uint8_t updPhase = 0;                    // what the updater's task is doing now (update_device.h)
static volatile uint32_t holdN = 0, holdMaxUs = 0, holdSumUs = 0, holdLastUs = 0;
static volatile uint32_t holdHist[6] = { 0, 0, 0, 0, 0, 0 };   // 4-8, 8-16, 16-32, 32-64, 64-128, 128+ ms
struct HoldLog { uint32_t ms, us; uint8_t busy, phase; };
static const int HOLD_LOG = 16;
static HoldLog holdLog[HOLD_LOG]; static volatile int holdLogN = 0, holdLogAt = 0;
static hw_timer_t *holdTimer = nullptr;

static void IRAM_ATTR holdTick() {
    const uint32_t now = (uint32_t) esp_timer_get_time();
    if (holdLastUs) {
        const uint32_t d = now - holdLastUs;
        if (d > 4000) {
            holdN++; holdSumUs += d; if (d > holdMaxUs) holdMaxUs = d;
            const int bin = d < 8000 ? 0 : d < 16000 ? 1 : d < 32000 ? 2 : d < 64000 ? 3 : d < 128000 ? 4 : 5;
            holdHist[bin]++;
            HoldLog &e = holdLog[holdLogAt]; e.ms = now / 1000; e.us = d; e.busy = busyWhat; e.phase = updPhase;
            holdLogAt = (holdLogAt + 1) % HOLD_LOG; if (holdLogN < HOLD_LOG) holdLogN++;
        }
    }
    holdLastUs = now;
}
static void holdWatchBegin() {                           // on the core that calls it (setup: the loop's), timer 3 of the groups, 1 ms
    holdTimer = timerBegin(3, 80, true);                 // 80 MHz / 80 = 1 us a count
    if (!holdTimer) return;
    timerAttachInterrupt(holdTimer, &holdTick, true);
    timerAlarmWrite(holdTimer, 1000, true);
    timerAlarmEnable(holdTimer);
}
static std::string holdJson() {
    char b[120];
    snprintf(b, sizeof b, "\"holds\":{\"on\":%d,\"n\":%lu,\"max_us\":%lu,\"sum_us\":%lu,\"hist\":[%lu,%lu,%lu,%lu,%lu,%lu],\"log\":[",
             holdTimer ? 1 : 0, (unsigned long) holdN, (unsigned long) holdMaxUs, (unsigned long) holdSumUs,
             (unsigned long) holdHist[0], (unsigned long) holdHist[1], (unsigned long) holdHist[2], (unsigned long) holdHist[3], (unsigned long) holdHist[4], (unsigned long) holdHist[5]);
    std::string out = b;
    const int n = holdLogN, start = (holdLogAt - n + HOLD_LOG) % HOLD_LOG;
    for (int i = 0; i < n; ++i) {
        const HoldLog e = holdLog[(start + i) % HOLD_LOG];
        snprintf(b, sizeof b, "%s[%lu,%lu,\"%s\",%u]", i ? "," : "", (unsigned long) e.ms, (unsigned long) e.us, e.busy < BUSY_N ? BUSY_NAMES[e.busy] : "?", (unsigned) e.phase);
        out += b;
    }
    out += "]}";
    return out;
}
