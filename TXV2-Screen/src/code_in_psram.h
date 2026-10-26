// THE FIRMWARE'S CODE IN THE PSRAM (1.11.131, 26 Oct 2026).
//
// The twin's panel reads its picture from the PSRAM, and the PSRAM shares its SPI bus with the flash the firmware runs from.
// Every cache miss on code or constants is a read of 32 bytes from the flash that holds that bus about a microsecond (quad,
// 80 MHz): the cold code of a page just changed to is hundreds of them in a row, and the panel's DMA, starved, slips the rest
// of that frame sideways. Measured 26 Oct (/stall?kind=mmap, the firmware streamed through the cache): 512 kB cost 3-4 us a
// frame, 4 MB made the panel miss a frame's end; the page draws carried 2-3 us a frame when nothing else did; and no pacing
// of our own movers changed the residual (Malcolm: "one in eight screen swaps", 1.11.129).
//
// The same 32 bytes from the octal PSRAM (DDR, 80 MHz) take the bus a fifth as long. So at start, before the panel runs,
// the firmware copies its own code (.flash.text, 1.4 MB) and its constants (.flash.rodata, 0.4 MB) into the PSRAM and
// points the chip's MMU at the copies: what ESP-IDF calls CONFIG_SPIRAM_FETCH_INSTRUCTIONS and CONFIG_SPIRAM_RODATA, which
// the prebuilt Arduino core (2.0.14 = IDF 4.4.6) was built without - done here by the firmware itself, by the book of
// components/esp_hw_support/port/esp32s3/spiram.c (esp_spiram_enable_instruction_access) and spi_flash/flash_mmap.c:
//   - the MMU is one table of 512 entries (DR_REG_MMU_TABLE), one 64 kB page each, shared by the instruction bus (0x42000000)
//     and the data bus (0x3C000000). The code holds entries 0..T-1 and the constants T..T+R-1 (the linker leaves a gap the
//     size of the code before the constants for exactly this: .flash_rodata_dummy); the PSRAM heap holds 384..511. An entry
//     is a flash page (bit 15 clear) or a PSRAM page (bit 15 set).
//   - the copy: the flash pages mapped as data (spi_flash_mmap), copied into a page-aligned block of the PSRAM heap, written
//     back out of the cache and read back from the chip against the flash. Then, with the other core parked and both caches
//     suspended (spi_flash_disable_interrupts_caches_and_other_cpu, as the flash map itself does when it writes the table),
//     the entries are rewritten to the PSRAM pages and the cache lines of those addresses dropped. The block is never freed:
//     it IS the code from then on.
//   - what the system might not notice: spi_flash_cache2phys (a function's address -> its flash offset) reads the table and
//     would now answer a PSRAM page. Its one user at run time is esp_ota_get_running_partition, which remembers its first
//     answer: asked once BEFORE the switch. A flash write's cache flush (spi_flash_check_and_flush_cache) matches entries with
//     the flash bit clear only, so the PSRAM entries are left alone (and the running slot is never written anyway). The ROM is
//     told the offsets as cpu_start.c tells it when IDF does this (Cache_Set_IDROM_MMU_Info).
//
// The pref "xip" (-1): -1 the board's choice (the twin: the code; the CrowPanel: nothing, its 10 MHz panel has room), 0 off,
// 1 the code, 2 the code and its constants. /stall?kind=xip&kb=N sets it for the next start. A start that switched and died
// within 20 s by a panic or a watchdog counts a strike (prefs "xiparm"/"xipbad", main.cpp setup and loop); two strikes turn
// it off until the pref is set again or the next firmware. /status "xip"; /stall?kind=mmu&kb=N shows the table.
// MEASURED on the desk twin, 26 Oct, 30 page rotations a run (scratchpad campaign.sh, slips over the 7 us bar with a mover in
// the frame): code in flash 8, 6, 5 (one of them a 21-29 ms frame miss each run); the code in PSRAM 1, 1 (both 7 us); code and
// constants 2, 2. The write-backs' and copies' excess halved too (their code came from the flash as well). The constants
// buy nothing more and cost 0.4 MB, so the board's choice is the code alone: 1.4 MB of the PSRAM, paid for by one resident
// picture fewer (main.cpp bgCacheMax) and by the films giving up a picture when short (psMallocRoom).
#pragma once
#include <Arduino.h>
#include <string>
#include <esp_spi_flash.h>
#include <esp_heap_caps.h>
#include <esp_ota_ops.h>
#include <soc/soc.h>
#include <soc/cache_memory.h>                            // FLASH_MMU_TABLE, MMU_ACCESS_SPIRAM, MMU_INVALID, MMU_ADDRESS_MASK, MMU_PAGE_SIZE, the bus addresses
#include <esp32s3/rom/cache.h>                           // Cache_Invalidate_Addr, Cache_WriteBack_Addr
#include "board.h"

extern "C" {
void spi_flash_disable_interrupts_caches_and_other_cpu(void);   // spi_flash/cache_utils.c (exported, no public header)
void spi_flash_enable_interrupts_caches_and_other_cpu(void);
void Cache_Set_IDROM_MMU_Info(uint32_t instr_page_num, uint32_t rodata_page_num, uint32_t rodata_start, uint32_t rodata_end, int i_off, int ro_off);   // ROM (esp32s3.rom.ld)
extern int _rodata_reserved_start, _rodata_reserved_end;      // the linker's (sections.ld): the constants' span; the code ends where their page begins
}

static int xipMode = 0;                                   // what this start did: 0 nothing, 1 the code, 2 the code and its constants
static const char *xipWhy = "not tried";
static char xipWhyBuf[80];
static uint32_t xipTextPages = 0, xipRodataPages = 0, xipMs = 0, xipStrikes = 0, xipPsramBefore = 0;
static bool xipArmed = false;                             // (main.cpp) this start's strike stands until 20 s have passed
static void *xipTextBlock = nullptr, *xipRodataBlock = nullptr;   // never freed
static const uint32_t XIP_KEEP_PSRAM = 1024u * 1024u;    // the PSRAM that must stay free for the pictures, the films and the WiFi

static bool xipWanted(int want) { return want < 0 ? board->psramRestUs != 0 : want != 0; }

// The PSRAM page behind a heap address: what its entry says (the PSRAM is mapped page for page, but ask rather than assume).
static bool xipPsramPage(const void *p, uint32_t &page) {
    const uint32_t v = (uint32_t) p;
    if (v < DRAM0_CACHE_ADDRESS_LOW || v >= DRAM0_CACHE_ADDRESS_HIGH) return false;
    const uint32_t e = FLASH_MMU_TABLE[(v - DRAM0_CACHE_ADDRESS_LOW) >> 16];
    if ((e & MMU_INVALID) || !(e & MMU_ACCESS_SPIRAM)) return false;
    page = e & MMU_ADDRESS_MASK; return true;
}

// The switch itself. Nothing here may come from the flash or the PSRAM (both caches are suspended), so it lives in IRAM and
// touches only its arguments, the stack and the table.
static void IRAM_ATTR __attribute__((noinline)) xipSwitch(uint32_t entry0, uint32_t pages, uint32_t vaddr, const uint32_t *ppage) {
    spi_flash_disable_interrupts_caches_and_other_cpu();
    for (uint32_t i = 0; i < pages; ++i) FLASH_MMU_TABLE[entry0 + i] = MMU_ACCESS_SPIRAM | ppage[i];
    Cache_Invalidate_Addr(vaddr, pages * MMU_PAGE_SIZE);
    spi_flash_enable_interrupts_caches_and_other_cpu();
}
static void IRAM_ATTR __attribute__((noinline)) xipTellRom(uint32_t t, uint32_t r, uint32_t roStart, uint32_t roEnd, int iOff, int roOff) {
    spi_flash_disable_interrupts_caches_and_other_cpu();   // (six plain stores in the ROM's data; nobody reads them half done)
    Cache_Set_IDROM_MMU_Info(t, r, roStart, roEnd, iOff, roOff);
    spi_flash_enable_interrupts_caches_and_other_cpu();
}

// One span of the image - entries entry0.., pages of them, seen by the CPU at vaddr - copied and switched. The block, or
// nullptr and why. *off = the flash page less the PSRAM page (INT32_MIN when the PSRAM pages did not come in a row).
static void *xipMove(uint32_t entry0, uint32_t pages, uint32_t vaddr, const char *&why, int32_t *off) {
    uint32_t ppage[64], flash0 = 0;
    if (pages == 0 || pages > 64) { why = "an odd page count"; return nullptr; }
    for (uint32_t i = 0; i < pages; ++i) {
        const uint32_t e = FLASH_MMU_TABLE[entry0 + i];
        if ((e & MMU_INVALID) || (e & MMU_ACCESS_SPIRAM)) { why = "not in the flash as expected"; return nullptr; }
        if (i == 0) flash0 = e & MMU_ADDRESS_MASK; else if ((e & MMU_ADDRESS_MASK) != flash0 + i) { why = "flash pages not in a row"; return nullptr; }
    }
    const size_t bytes = (size_t) pages * MMU_PAGE_SIZE;
    if (heap_caps_get_free_size(MALLOC_CAP_SPIRAM) < bytes + XIP_KEEP_PSRAM) { why = "no room in the PSRAM"; return nullptr; }
    uint8_t *blk = (uint8_t *) heap_caps_aligned_alloc(MMU_PAGE_SIZE, bytes, MALLOC_CAP_SPIRAM);
    if (!blk) { why = "no block in the PSRAM"; return nullptr; }
    for (uint32_t i = 0; i < pages; ++i) if (!xipPsramPage(blk + i * MMU_PAGE_SIZE, ppage[i])) { free(blk); why = "the PSRAM page unknown"; return nullptr; }
    const void *src = nullptr; spi_flash_mmap_handle_t h = 0;
    if (spi_flash_mmap((size_t) flash0 * MMU_PAGE_SIZE, bytes, SPI_FLASH_MMAP_DATA, &src, &h) != ESP_OK || !src) { free(blk); why = "the flash would not map"; return nullptr; }
    memcpy(blk, src, bytes);
    Cache_WriteBack_Addr((uint32_t) blk, bytes);          // out of the cache into the chip, where the fetches will read it
    Cache_Invalidate_Addr((uint32_t) blk, bytes);         // and read back from the chip, not the cache
    const bool same = memcmp(blk, src, bytes) == 0;
    spi_flash_munmap(h);
    if (!same) { free(blk); why = "the copy read back wrong"; return nullptr; }
    xipSwitch(entry0, pages, vaddr, ppage);
    *off = (int32_t) flash0 - (int32_t) ppage[0];
    for (uint32_t i = 1; i < pages; ++i) if (ppage[i] != ppage[0] + i) *off = INT32_MIN;
    return blk;
}

// Before the panel runs (main.cpp setup). want: the pref "xip" (-1 the board's choice = the code).
static void xipBegin(int want) {
    const uint32_t t0 = millis();
    const int mode = want < 0 ? 1 : want;
    xipPsramBefore = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    esp_ota_get_running_partition();                        // remembered by the system now, while a function's address still finds its flash page
    const uint32_t roStart = (uint32_t) &_rodata_reserved_start & ~(uint32_t) (MMU_PAGE_SIZE - 1), roEnd = (uint32_t) &_rodata_reserved_end;
    const uint32_t T = (roStart - DRAM0_CACHE_ADDRESS_LOW) / MMU_PAGE_SIZE, R = (roEnd - roStart + MMU_PAGE_SIZE - 1) / MMU_PAGE_SIZE;   // as cpu_start.c counts them
    int32_t iOff = INT32_MIN, roOff = INT32_MIN; const char *why = "";
    xipTextBlock = xipMove(0, T, IRAM0_CACHE_ADDRESS_LOW, why, &iOff);
    if (!xipTextBlock) { xipWhy = why; xipMs = millis() - t0; return; }
    xipTextPages = T; xipMode = 1; xipWhy = "code";
    if (mode >= 2) {
        xipRodataBlock = xipMove(T, R, roStart, why, &roOff);
        if (xipRodataBlock) { xipRodataPages = R; xipMode = 2; xipWhy = "code and constants"; }
        else { snprintf(xipWhyBuf, sizeof xipWhyBuf, "code (constants: %s)", why); xipWhy = xipWhyBuf; }
    }
    if (iOff != INT32_MIN && (!xipRodataBlock || roOff != INT32_MIN)) xipTellRom(T, R, (uint32_t) &_rodata_reserved_start, roEnd, iOff, xipRodataBlock ? roOff : 0);
    xipMs = millis() - t0;
}

static void xipJson(std::string &out) {                   // (/status "xip")
    char b[220];
    snprintf(b, sizeof b, "\"xip\":{\"mode\":%d,\"text\":%lu,\"rodata\":%lu,\"ms\":%lu,\"strikes\":%lu,\"psram_before\":%lu,\"why\":\"%s\"}",
             xipMode, (unsigned long) xipTextPages, (unsigned long) xipRodataPages, (unsigned long) xipMs, (unsigned long) xipStrikes, (unsigned long) xipPsramBefore, xipWhy);
    out += b;
}
static void xipMmuWords(int n, char *extra, size_t extraN) {   // (/stall?kind=mmu&kb=N) the first N entries, hex: 8xxx = a PSRAM page
    size_t at = snprintf(extra, extraN, ",\"mmu\":\"");
    for (int i = 0; i < n && i < 40 && at + 8 < extraN; ++i) at += snprintf(extra + at, extraN - at, "%s%lx", i ? " " : "", (unsigned long) FLASH_MMU_TABLE[i]);
    if (at + 2 < extraN) snprintf(extra + at, extraN - at, "\"");
}
