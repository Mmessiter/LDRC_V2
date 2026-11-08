// (1.11.188) THE LAST MOMENTS - what the screen was doing when it died, kept where a watchdog's reset cannot reach.
//
// Malcolm, 8 Nov 2026: "After editing an aileron curve, on returning to the front screen the screen crashed. It did this
// twice." The Teensy's log: the interrupt watchdog (rst 5), twice, a second after the front page - and no core dump, nothing
// on the wire, as on 6 Nov (1.11.185's "before" record was made for it, but a power-off loses RTC memory, and the record
// was lost before it was read). A watchdog that leaves no core dump and no "Guru Meditation" on the wire is one whose panic
// handler never ran: the chip's caches were off (a flash operation under way - every flash write and erase turns them off and
// stalls the other core in a level-5 interrupt, where the watchdog's own interrupt cannot be served), or a core sat in an
// interrupt too long. So this file keeps, in RTC memory (which outlives any reset but a power cut):
//   - every flash operation's beginning and end, through the esp_flash driver's own start/end hooks, wrapped: the task, what
//     the loop was doing, how long it took - and whether one was UNDER WAY when the chip died;
//   - the loop's last pass;
//   - the heap check's verdict (below).
// At the next start the "before" record (main.cpp, /status "before") says all of it, is kept in NVS as well (/status
// "before_kept": the last three, through power-offs) and is sent to the Teensy, whose day log keeps it ("LDRCLOG", B198).
//
// THE HEAP CHECK: the 5 Nov core dump (1.11.180) died at a page change destroying the old page's components, a vector's
// pointer zeroed in the PSRAM - something had written over the heap. The heap's structure and every block's canaries
// (light poisoning) are checked at each page change on a 16 MB board, ON THE OTHER CORE: the check holds the heap's lock
// with that core's interrupts off for some milliseconds, and the panel's interrupt lives on this one. The loop waits for it
// without allocating. The heap's own words about a bad block are caught (the ROM's print hook) and kept.
#pragma once
#include <Arduino.h>
#include <string>
#include <esp_attr.h>
#include <esp_flash.h>
#include <esp_heap_caps.h>
#include <esp_timer.h>
#include <esp_rom_sys.h>
#include <esp32s3/rom/ets_sys.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/semphr.h>
#include <driver/uart.h>                                 // (1.11.191) the watch shouts straight into UART0's FIFO
#include "busy_what.h"

#define LM_MAGIC 0x4C444C4Du
RTC_NOINIT_ATTR static uint32_t lmMagic;
RTC_NOINIT_ATTR static volatile uint32_t lmFlashN;         // flash operations since this start
RTC_NOINIT_ATTR static volatile uint32_t lmFlashBusy;      // 1 from a flash operation's start to its end (the caches are off)
RTC_NOINIT_ATTR static volatile int64_t lmFlashStartUs;    // when the one under way (or the last) began, us since start
RTC_NOINIT_ATTR static volatile uint32_t lmFlashLastUs, lmFlashMaxUs, lmFlashEndMs;
RTC_NOINIT_ATTR static char lmFlashTask[12], lmFlashMaxTask[12];
RTC_NOINIT_ATTR static volatile uint8_t lmFlashWhat, lmFlashMaxWhat;   // the loop's tag (busy_what.h) at its start
RTC_NOINIT_ATTR static volatile uint32_t lmLoopMs;         // the loop's last pass, ms since start
RTC_NOINIT_ATTR static volatile uint32_t lmLoopN;
RTC_NOINIT_ATTR static char lmHeapBad[120];                // the heap's words about a bad block, if the check found one
RTC_NOINIT_ATTR static volatile uint32_t lmHeapBadN;
// (1.11.191) THE SCAN CRASH (Malcolm, 8 Nov 2026: "returning from scanning the 2.4 wave band also crashes the screen"; the records: rst 5,
// the loop at idle on TXSetupView, no flash operation under way, nothing on the wire) - finer traces, all in RTC memory:
RTC_NOINIT_ATTR static char lmCmd[12][32];                 // the last twelve display commands handled (their first 31 characters) ...
RTC_NOINIT_ATTR static volatile uint32_t lmCmdMs[12];      // ... and when, ms since start
RTC_NOINIT_ATTR static volatile uint8_t lmCmdAt;           // the slot the next one goes in
RTC_NOINIT_ATTR static char lmPart[16];                    // the loop's finer position (main.cpp Part): "-" between parts
RTC_NOINIT_ATTR static volatile uint32_t lmRadioMs;        // the radios' last switch (main.cpp applyRadios): when ...
RTC_NOINIT_ATTR static volatile uint8_t lmRadioOn, lmRadioN;   // ... on or off, and how many switches this run
RTC_NOINIT_ATTR static volatile uint32_t lmStallN, lmStallMaxMs;   // a core seen silent for 200 ms and more: how often, the longest
RTC_NOINIT_ATTR static char lmStuck[200];                  // the last such verdict, from the core that could still speak

// ---- the flash operations
static const esp_flash_os_functions_t *lmOrig = nullptr;
static esp_flash_os_functions_t lmOps;
static void IRAM_ATTR lmCopyName(char *dst, const char *src, int n) { int i = 0; if (src) for (; i < n - 1 && src[i]; ++i) dst[i] = src[i]; dst[i] = 0; }
static esp_err_t IRAM_ATTR lmFlashStart(void *arg) {
    // the caches are still on here: the driver's own start turns them off, and nothing after it may run from flash
    lmCopyName(lmFlashTask, pcTaskGetName(NULL), sizeof(lmFlashTask));
    lmFlashWhat = busyWhat; lmFlashStartUs = esp_timer_get_time(); lmFlashN = lmFlashN + 1; lmFlashBusy = 1;
    return lmOrig->start(arg);
}
static esp_err_t IRAM_ATTR lmFlashEnd(void *arg) {
    const esp_err_t r = lmOrig->end(arg);                  // the caches come back here
    const uint32_t us = (uint32_t) (esp_timer_get_time() - lmFlashStartUs);
    lmFlashLastUs = us;
    if (us > lmFlashMaxUs) { lmFlashMaxUs = us; lmCopyName(lmFlashMaxTask, lmFlashTask, sizeof(lmFlashMaxTask)); lmFlashMaxWhat = lmFlashWhat; }
    lmFlashEndMs = (uint32_t) (esp_timer_get_time() / 1000); lmFlashBusy = 0;
    return r;
}
static inline void lmLoopTick() { lmLoopMs = (uint32_t) (esp_timer_get_time() / 1000); lmLoopN = lmLoopN + 1; }
static const char *lmWhatName(uint8_t w) { return w < BUSY_N ? BUSY_NAMES[w] : "?"; }
// (1.11.191) the finer traces
static inline void lmCmdNote(const char *s, size_t n) {
    const uint8_t i = lmCmdAt % 12; size_t k = 0;
    for (; k < 31 && k < n; ++k) lmCmd[i][k] = (s[k] >= 32 && s[k] < 127) ? s[k] : '.';
    lmCmd[i][k] = 0; lmCmdMs[i] = (uint32_t) (esp_timer_get_time() / 1000); lmCmdAt = (uint8_t) ((i + 1) % 12);
}
static inline void lmPartNote(const char *name) { lmCopyName(lmPart, name, sizeof(lmPart)); }
static inline void lmRadioNote(bool on) { lmRadioMs = (uint32_t) (esp_timer_get_time() / 1000); lmRadioOn = on ? 1 : 0; lmRadioN = lmRadioN + 1; }
static volatile bool lmQuiet = false;                      // a restart we asked for is coming: the watch says nothing of the silence that follows
static uint32_t lmHeapCheckAt = 0;                         // main.cpp: a heap check due (400 ms after a page load)
static volatile uint32_t lmWatchMs = 0;                    // the watch's (core 0) last pass, ms since start: the loop reads it to see that core 0 lives
static void lmShout(const char *s) {                       // from core 0, straight into UART0's FIFO: the loop, which owns Serial, may be the one that stopped
    char line[240]; const int n = snprintf(line, sizeof line, "LDRCLOG %s", s);
    for (int at = 0, tries = 0; at < n && tries < 80; ++tries) { const int w = uart_tx_chars(UART_NUM_0, line + at, n - at); if (w > 0) at += w; else esp_rom_delay_us(300); }
}
static void lmWatch() {                                    // on core 0, every 50 ms: has the loop (core 1) fallen silent? (the interrupt watchdog resets the chip at 300 ms)
    const uint32_t now = (uint32_t) (esp_timer_get_time() / 1000);
    lmWatchMs = now;
    if (lmQuiet || !lmLoopN) return;
    const uint32_t gone = now - lmLoopMs;
    static uint32_t saidFor = 0;
    if (gone < 200) { saidFor = 0; return; }
    if (saidFor == lmLoopMs) return;                        // this silence has been spoken of
    saidFor = lmLoopMs;
    lmStallN = lmStallN + 1; if (gone > lmStallMaxMs) lmStallMaxMs = gone;
    TaskHandle_t h = xTaskGetCurrentTaskHandleForCPU(1); const char *tn = h ? pcTaskGetName(h) : "?";
    const int i = (lmCmdAt + 11) % 12; lmPart[sizeof(lmPart) - 1] = 0; lmCmd[i][31] = 0;
    snprintf(lmStuck, sizeof lmStuck, "core 1 (the loop's) silent for %lu ms at %lu ms: task '%.15s' on it, part '%.15s', loop at '%s', last command %lu ms ago: %s",
             (unsigned long) gone, (unsigned long) now, tn, lmPart, lmWhatName(busyWhat), (unsigned long) (now - lmCmdMs[i]), lmCmd[i]);
    lmShout(lmStuck);
}

// What the record says about the run that ended (called at the start, BEFORE lmBegin resets it). Empty if there is none.
static std::string lmBeforeText() {
    if (lmMagic != LM_MAGIC) return "";
    char t[320];
    std::string b;
    snprintf(t, sizeof t, "; the loop's last pass %lu ms after start (%lu passes)", (unsigned long) lmLoopMs, (unsigned long) lmLoopN); b += t;
    lmFlashTask[sizeof(lmFlashTask) - 1] = 0; lmFlashMaxTask[sizeof(lmFlashMaxTask) - 1] = 0;
    if (lmFlashBusy) {
        snprintf(t, sizeof t, "; A FLASH OPERATION WAS UNDER WAY (the caches off): begun at %lu ms by task '%s' while the loop was at '%s'",
                 (unsigned long) (lmFlashStartUs / 1000), lmFlashTask, lmWhatName(lmFlashWhat)); b += t;
    } else if (lmFlashN) {
        snprintf(t, sizeof t, "; %lu flash operations, the last ended at %lu ms (%lu us, task '%s')", (unsigned long) lmFlashN, (unsigned long) lmFlashEndMs, (unsigned long) lmFlashLastUs, lmFlashTask); b += t;
    } else b += "; no flash operation";
    if (lmFlashMaxUs) { snprintf(t, sizeof t, "; the longest %lu us by '%s' during '%s'", (unsigned long) lmFlashMaxUs, lmFlashMaxTask, lmWhatName(lmFlashMaxWhat)); b += t; }
    if (lmHeapBadN) { lmHeapBad[sizeof(lmHeapBad) - 1] = 0; snprintf(t, sizeof t, "; THE HEAP CHECK HAD FAILED %lu times, last: %s", (unsigned long) lmHeapBadN, lmHeapBad); b += t; }
    // (1.11.191)
    lmPart[sizeof(lmPart) - 1] = 0; snprintf(t, sizeof t, "; part '%s'", lmPart); b += t;
    if (lmRadioN) { snprintf(t, sizeof t, "; the radios went %s at %lu ms (%ld ms before the loop's last pass; %u switches)", lmRadioOn ? "ON" : "OFF", (unsigned long) lmRadioMs, (long) (int32_t) (lmLoopMs - lmRadioMs), (unsigned) lmRadioN); b += t; }
    if (lmStallN) { lmStuck[sizeof(lmStuck) - 1] = 0; snprintf(t, sizeof t, "; A CORE HAD FALLEN SILENT (%lu times, the longest %lu ms), last: %s", (unsigned long) lmStallN, (unsigned long) lmStallMaxMs, lmStuck); b += t; }
    b += "; the last commands (ms before the loop's last pass):";
    for (int k = 0; k < 12; ++k) { const int i = (lmCmdAt + k) % 12; if (!lmCmdMs[i] && !lmCmd[i][0]) continue; lmCmd[i][31] = 0; snprintf(t, sizeof t, " [%ld] %s", (long) (int32_t) (lmLoopMs - lmCmdMs[i]), lmCmd[i]); b += t; }
    return b;
}
// A fresh record for this run, and the flash driver's hooks wrapped. Called once, early in setup().
static void lmBegin() {
    lmMagic = LM_MAGIC; lmFlashN = 0; lmFlashBusy = 0; lmFlashStartUs = 0; lmFlashLastUs = lmFlashMaxUs = lmFlashEndMs = 0;
    lmFlashTask[0] = lmFlashMaxTask[0] = 0; lmFlashWhat = lmFlashMaxWhat = 0; lmLoopMs = 0; lmLoopN = 0; lmHeapBad[0] = 0; lmHeapBadN = 0;
    lmCmdAt = 0; for (int i = 0; i < 12; ++i) { lmCmd[i][0] = 0; lmCmdMs[i] = 0; } lmPart[0] = '-'; lmPart[1] = 0; lmRadioMs = 0; lmRadioOn = 0; lmRadioN = 0; lmStallN = 0; lmStallMaxMs = 0; lmStuck[0] = 0;   // (1.11.191)
    if (esp_flash_default_chip && esp_flash_default_chip->os_func && !lmOrig) {
        lmOrig = esp_flash_default_chip->os_func;
        lmOps = *lmOrig; lmOps.start = lmFlashStart; lmOps.end = lmFlashEnd;
        esp_flash_default_chip->os_func = &lmOps;
    }
}

// ---- the heap check, on the other core
static TaskHandle_t lmHeapTask = nullptr; static SemaphoreHandle_t lmHeapDone = nullptr;
static volatile bool lmHeapOk = true; static volatile uint32_t lmHeapUs = 0;
static char lmHeapCap[200]; static volatile int lmHeapCapN = 0;
static uint32_t lmHeapChkN = 0, lmHeapChkMaxUs = 0, lmHeapChkLastUs = 0; static std::string lmHeapLast;   // for /status
static bool lmHeapOn = false;                               // set in setup(): a 16 MB board, unless the pref says no
static void lmHeapPutc(char c) {
    if (lmHeapCapN >= (int) sizeof(lmHeapCap) - 1) return;
    if (c == '\n' || c == '\r') { if (lmHeapCapN && lmHeapCap[lmHeapCapN - 1] != '|') lmHeapCap[lmHeapCapN++] = '|'; }
    else if (c >= 32 && c < 127) lmHeapCap[lmHeapCapN++] = c;
}
static void lmHeapTaskFn(void *) {
    for (;;) {
        if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(50)) == 0) { lmWatch(); continue; }   // (1.11.191) nothing to check: the watch on the loop's core, every 50 ms
        lmHeapCapN = 0;
        ets_install_putc1(lmHeapPutc);                      // the heap prints its findings with the ROM's printf: caught here
        const uint32_t t0 = micros();
        lmHeapOk = heap_caps_check_integrity_all(true);
        lmHeapUs = micros() - t0;
        esp_rom_install_uart_printf();                       // the ROM's printing back to the UART, as the system had it
        lmHeapCap[lmHeapCapN] = 0;
        xSemaphoreGive(lmHeapDone);
    }
}
// True = the heap is sound (or the check could not run). False = a block is bad: lmHeapLast / lmHeapBad say which, in the heap's words.
static bool lmHeapCheck(const char *when) {
    if (!lmHeapTask) {
        lmHeapDone = xSemaphoreCreateBinary();
        if (!lmHeapDone || xTaskCreatePinnedToCore(lmHeapTaskFn, "heapchk", 4096, nullptr, 20, &lmHeapTask, 0) != pdPASS) { lmHeapTask = nullptr; return true; }
    }
    xTaskNotifyGive(lmHeapTask);
    if (xSemaphoreTake(lmHeapDone, pdMS_TO_TICKS(1000)) != pdTRUE) return true;   // (never seen: the check takes milliseconds)
    lmHeapChkN++; lmHeapChkLastUs = lmHeapUs; if (lmHeapUs > lmHeapChkMaxUs) lmHeapChkMaxUs = lmHeapUs;
    if (lmHeapOk) return true;
    lmHeapBadN = lmHeapBadN + 1;
    snprintf(lmHeapBad, sizeof(lmHeapBad), "%.36s: %.78s", when, lmHeapCap);
    lmHeapLast = std::string(when) + ": " + lmHeapCap;
    return false;
}

// ---- the big buffers, by name: a bad block's address is read against them (/status "lm" "bufs")
struct LmBuf { const char *name; uint32_t at, n; };
static LmBuf lmBufs[24]; static int lmBufN = 0;
static const char *const lmBgNames[6] = { "bg0", "bg1", "bg2", "bg3", "bg4", "bg5" };                        // the resident backgrounds
static const char *const lmRawNames[8] = { "raw0", "raw1", "raw2", "raw3", "raw4", "raw5", "raw6", "raw7" }; // the page files kept in PSRAM
static void lmBufNote(const char *name, const void *p, size_t n) {
    if (!p) return;
    for (int i = 0; i < lmBufN; ++i) if (strcmp(lmBufs[i].name, name) == 0) { lmBufs[i].at = (uint32_t) p; lmBufs[i].n = (uint32_t) n; return; }
    if (lmBufN < (int) (sizeof(lmBufs) / sizeof(lmBufs[0]))) lmBufs[lmBufN++] = { name, (uint32_t) p, (uint32_t) n };
}
static std::string lmJson() {
    char t[200];
    std::string out = "\"lm\":{";
    snprintf(t, sizeof t, "\"flash\":{\"n\":%lu,\"busy\":%lu,\"last_us\":%lu,\"last_task\":\"%.11s\",\"max_us\":%lu,\"max_task\":\"%.11s\",\"max_what\":\"%s\"}",
             (unsigned long) lmFlashN, (unsigned long) lmFlashBusy, (unsigned long) lmFlashLastUs, lmFlashTask, (unsigned long) lmFlashMaxUs, lmFlashMaxTask, lmWhatName(lmFlashMaxWhat));
    out += t;
    snprintf(t, sizeof t, ",\"heap\":{\"on\":%d,\"checks\":%lu,\"last_us\":%lu,\"max_us\":%lu,\"bad\":%lu,\"last\":\"", lmHeapOn ? 1 : 0, (unsigned long) lmHeapChkN, (unsigned long) lmHeapChkLastUs, (unsigned long) lmHeapChkMaxUs, (unsigned long) lmHeapBadN);
    out += t; for (char c : lmHeapLast) if (c != '"' && c != '\\') out += c; out += "\"}";
    out += ",\"bufs\":[";
    for (int i = 0; i < lmBufN; ++i) { snprintf(t, sizeof t, "%s{\"n\":\"%s\",\"at\":\"0x%08lx\",\"end\":\"0x%08lx\",\"kb\":%lu}", i ? "," : "", lmBufs[i].name, (unsigned long) lmBufs[i].at, (unsigned long) (lmBufs[i].at + lmBufs[i].n), (unsigned long) (lmBufs[i].n >> 10)); out += t; }
    out += "]";
    // (1.11.191)
    lmStuck[sizeof(lmStuck) - 1] = 0; lmPart[sizeof(lmPart) - 1] = 0;
    snprintf(t, sizeof t, ",\"stall\":{\"n\":%lu,\"max_ms\":%lu,\"last\":\"", (unsigned long) lmStallN, (unsigned long) lmStallMaxMs); out += t;
    for (const char *p = lmStuck; *p; ++p) if (*p != '"' && *p != '\\') out += *p;
    snprintf(t, sizeof t, "\"},\"part\":\"%.15s\",\"radio\":{\"n\":%u,\"on\":%u,\"ms\":%lu},\"cmds\":[", lmPart, (unsigned) lmRadioN, (unsigned) lmRadioOn, (unsigned long) lmRadioMs); out += t;
    bool firstCmd = true;
    for (int k = 0; k < 12; ++k) { const int i = (lmCmdAt + k) % 12; if (!lmCmdMs[i] && !lmCmd[i][0]) continue; lmCmd[i][31] = 0; snprintf(t, sizeof t, "%s{\"ms\":%lu,\"c\":\"", firstCmd ? "" : ",", (unsigned long) lmCmdMs[i]); out += t; firstCmd = false; for (const char *p = lmCmd[i]; *p; ++p) if (*p != '"' && *p != '\\') out += *p; out += "\"}"; }
    out += "]}";
    return out;
}
