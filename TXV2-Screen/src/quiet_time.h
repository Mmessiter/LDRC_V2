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
static volatile bool quietAsked = false;                // the next frame is to be a quiet one
static volatile uint32_t quietFrame = 0;                // which frame is (or was) the quiet one: frameEnds while it lasts
static uint32_t vtNormal = 0, picLines = 496;           // the panel's lines a frame less one (503), and the lines up to the picture's last (16 + 480)
static const uint32_t VT_QUIET = 1023;                  // (the register's 10 bits: 1024 lines, 87.5 ms)
static void QT_ISR quietFrameEnd() {
    const uint32_t now = QT_MICROS(), next = frameEnds + 1;
    if (frameEnds && frameEnds != quietFrame && now - frameAtUs > 40000 && now - frameAtUs < 46000) frameUs = now - frameAtUs;   // (a normal frame's length: the quiet time's sums follow the real clock; not one a flash write held up)
    frameAtUs = now;
    if (vtNormal) {                                     // (the driver starts the next frame as soon as we return: these lines are its)
        if (quietAsked) { quietAsked = false; quietFrame = next; QT_VT_SET(VT_QUIET); }
        else QT_VT_SET(vtNormal);
    }
    frameEnds = next;
}
// The quiet time now open, in microseconds left (0: none open): from the quiet frame's last line of picture to its end.
static uint32_t quietLinesUs(uint32_t lines) { return (uint32_t) ((uint64_t) frameUs * lines / (vtNormal + 1)); }   // (whole microseconds would be 0.5 us short a line)
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
