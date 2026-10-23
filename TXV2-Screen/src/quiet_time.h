// The panel's quiet time (screen 1.11.67): the sums and the jobs, apart from the hardware so the Mac can test them
// (hmi/test_quiet). Why it exists: src/main.cpp, above hookFrameEnd(). The panel's frame-end interrupt calls
// quietFrameEnd() just before IDF 4.4's driver starts the next frame; a job (a whole-screen copy, the defined front
// screen's first drawing) asks quietTurn() each pass of the loop and is done when it says so.
#pragma once
#include <stdint.h>
#ifndef QT_MICROS                                       // (the host test brings its own clock and panel)
#define QT_MICROS() micros()
#define QT_MILLIS() millis()
#define QT_VT_SET(v) (LCD_CAM.lcd_ctrl.lcd_vt_height = (v))
#define QT_ISR IRAM_ATTR
#endif
static volatile uint32_t frameEnds = 0, frameAtUs = 0, frameUs = 43090;   // frames ended; when the one now showing began; a normal frame's length
// (1.11.113) A normal frame's length is measured only near the board's own (a frame a flash write held up is not one): set by
// quietFrameLength() from the board's timing (main.cpp hookFrameEnd) - 43.09 ms on the CrowPanel (855 x 504 clocks at 10 MHz),
// 28.92 ms on the 16 MB twin (832 x 504 at 14.5 MHz). Until 1.11.113 the window was the CrowPanel's alone (40-46 ms): on the
// twin no frame was ever measured, and the beam's sums ran at two-thirds of its scan (copies caught part-way: hmi/test_quiet).
static uint32_t frameLoUs = 40000, frameHiUs = 46000;
static void quietFrameLength(uint32_t us) { frameUs = us; frameLoUs = us - us / 14; frameHiUs = us + us / 15; }
static volatile bool quietAsked = false;                // the next frame is to be a quiet one
static volatile uint32_t quietFrame = 0;                // which frame is (or was) the quiet one: frameEnds while it lasts
static uint32_t vtNormal = 0, picLines = 496;           // the panel's lines a frame less one (503), and the lines up to the picture's last (16 + 480)
static const uint32_t VT_QUIET = 1023;                  // (the register's 10 bits: 1024 lines, 87.5 ms)
static void QT_ISR quietFrameEnd() {
    const uint32_t now = QT_MICROS(), next = frameEnds + 1;
    if (frameEnds && frameEnds != quietFrame && now - frameAtUs > frameLoUs && now - frameAtUs < frameHiUs) frameUs = now - frameAtUs;   // (a normal frame's length: the quiet time's sums follow the real clock; not one a flash write held up)
    frameAtUs = now;
    if (vtNormal) {                                     // (the driver starts the next frame as soon as we return: these lines are its)
        if (quietAsked) { quietAsked = false; quietFrame = next; QT_VT_SET(VT_QUIET); }
        else QT_VT_SET(vtNormal);
    }
    frameEnds = next;
}
// The quiet time now open, in microseconds left (0: none open): from the quiet frame's last line of picture to its end.
static uint32_t quietLinesUs(uint32_t lines) { return (uint32_t) ((uint64_t) frameUs * lines / (vtNormal + 1)); }   // (whole microseconds would be 0.5 us short a line)
// (1.11.82) The panel's scan - the beam - as the row of the picture it is on now, by the time since the frame began: below 0
// it is in the lines before the picture (VSYNC and the back porch, picTop of them), 480 and more past it. INT32_MIN: nothing
// is known (no hook, or the interrupt has stopped coming).
static uint32_t picTop = 16;                            // the lines before the picture (set from the registers by hookFrameEnd)
static int32_t beamRow(uint32_t nowUs) {
    if (!vtNormal || !frameEnds) return INT32_MIN;
    const uint32_t in = nowUs - frameAtUs;
    if (in > 2 * frameUs) return INT32_MIN;
    return (int32_t) ((uint64_t) in * (vtNormal + 1) / frameUs) - (int32_t) picTop;
}
// (1.11.82) May rows y .. y+h-1 be copied to the panel now, the copy taking copyUs, without the scan catching it part-way - a
// frame showing the rows above the beam new and those below old (the curve page's marker "breaks into two with one part
// ahead of the other": Malcolm, 17 Oct 2026)? Yes when the beam has passed them (a copy made top-down then stays ahead of
// the next frame's scan), or when it will not reach them before the copy is done. A margin of lines covers the estimate's
// error - more before the beam, where an interrupt held back (a flash write) would put it further on than we think. Rows
// with no window worth waiting for (the whole screen; a tall list to the bottom edge) go at once, as every copy did before:
// a window is worth it from 20 lines (1.7 ms, a few passes of the loop), and the window after the beam only when the copy
// is quicker than the scan, row for row (with a fifth to spare), so that it stays ahead of the next frame's scan.
static bool beamClear(int32_t y, int32_t h, uint32_t nowUs, uint32_t copyUs, int32_t marginBefore = 12, int32_t marginAfter = 4) {
    const int32_t beam = beamRow(nowUs);
    if (beam == INT32_MIN) return true;
    const int32_t copyLines = (int32_t) (((uint64_t) copyUs * (vtNormal + 1) + frameUs - 1) / frameUs);
    const int32_t top = -(int32_t) picTop, bottom = (int32_t) (vtNormal + 1) - (int32_t) picTop;   // the beam's first line, and one past its last
    const int32_t windowBefore = y - marginBefore - copyLines - top, windowAfter = bottom - (y + h) - marginAfter;
    const bool canBefore = windowBefore >= 20, canAfter = windowAfter >= 20 && copyLines * 5 < h * 4;
    if (!canBefore && !canAfter) return true;
    if (canAfter && beam - marginAfter >= y + h) return true;
    return canBefore && beam + marginBefore + copyLines < y;
}
static int32_t quietLeftUs() {
    if (!vtNormal || !quietFrame || frameEnds != quietFrame) return 0;
    const uint32_t in = QT_MICROS() - frameAtUs, end = quietLinesUs(VT_QUIET + 1);
    if (in < quietLinesUs(picLines + 1) || in >= end) return 0;
    return (int32_t) (end - in);
}
// A job for the quiet time (a whole-screen copy, the defined front screen's first drawing): true when it may be done now.
// Asked for each pass of the loop while it waits; one that is not asked again for 200 ms has gone (its wait starts afresh).
struct QuietJob { uint32_t since = 0, last = 0; bool inQuiet = false; };
static const uint32_t QUIET_NEED_US = 38000;            // (the copy takes ~36 ms with nothing else on the PSRAM; the blank is 45)
static uint32_t quietN = 0, quietLateN = 0, quietOverN = 0, quietWaitMs = 0, quietCopyUs = 0, quietCopyMax = 0, quietDrawUs = 0, quietDrawMax = 0;
static uint32_t quietSeenEnds = 0, quietSeenAt = 0;
static uint32_t quietKeptN = 0, quietFullN = 0, quietWarmN = 0, quietStepMax = 0;   // (1.11.68, src/flight_device.h) the defined screen: shown as kept, drawn whole, drawn ahead; its longest piece (us)
static uint32_t quietStoreN = 0, quietStoreMax = 0;      // (1.11.69) the front screen's choice written to the flash: how often, the longest (us)
// (1.11.69) The front screen's switch is copied at once, as every other page change is (Malcolm, of 1.11.67: "All of the
// other screen changes are just fine ... Maybe we should simply use the other method?"): no quiet frame. The quiet time
// stays here, unused, should it be wanted again. (1.11.113: on the 16 MB twin a quiet frame's blank is only 30 ms, short of
// QUIET_NEED_US: every job would go late. Its numbers are the CrowPanel's.)
static const bool QUIET_SWITCH = false;
// Wait for the panel's frame end (a frame at most): a short flash write started then is over in the blank before the next
// picture (16 lines, 1.4 ms), so the panel's DMA does not wait for the PSRAM in the middle of a picture.
static void quietAtFrameEnd() {
    if (!vtNormal || !frameEnds) return;
    const uint32_t f = frameEnds, t0 = QT_MICROS();
    while (frameEnds == f && QT_MICROS() - t0 < 50000) { }
}
static bool quietTurn(QuietJob &j, uint32_t needUs = QUIET_NEED_US) {
    const uint32_t now = QT_MILLIS();
    if (!j.since || now - j.last > 200) j.since = now;
    j.last = now;
    if (frameEnds != quietSeenEnds) { quietSeenEnds = frameEnds; quietSeenAt = now; }
    const bool ticking = vtNormal && frameEnds && now - quietSeenAt < 150;   // (the hook works and the panel is running)
    const bool running = ticking && quietFrame && frameEnds == quietFrame;
    const int32_t left = running ? quietLeftUs() : 0;
    bool go = left >= (int32_t) needUs;
    if (!go) {
        if (!running) quietAsked = true;                                    // (the next frame is the quiet one)
        else if (QT_MICROS() - frameAtUs >= quietLinesUs(picLines + 1)) quietAsked = true;   // (open, but too little left: the next one too)
        if (!ticking || now - j.since > 400) { go = true; if (ticking) quietLateN++; }   // (never longer than this: done at once, as before)
    }
    if (go) { quietWaitMs = now - j.since; j.since = 0; j.inQuiet = left > 0; quietN++; if (left <= 0) quietAsked = false; }
    return go;
}
static void quietDone(QuietJob &j, uint32_t us, bool draw) {   // (the perf line, and /status: how it went)
    if (draw) { quietDrawUs = us; if (us > quietDrawMax) quietDrawMax = us; }
    else { quietCopyUs = us; if (us > quietCopyMax) quietCopyMax = us; }
    if (j.inQuiet && quietLeftUs() <= 0) quietOverN++;                      // (it ran past the blank: the next frame's scan began while it ran)
    j.inQuiet = false;
}
