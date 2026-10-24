// THE TWO SCREENS THIS FIRMWARE RUNS ON (1.11.111, 23 Oct 2026), told apart at start-up.
//
//   CrowPanel 5.0 (Elecrow DIS07050H, ESP32-S3 N4R8: 4 MB flash, 8 MB PSRAM)  - the first two transmitters
//   The 16 MB twin (Elecrow DLE06050B "5 inch ESP32-S3 IPS display", N16R8)   - the three that came 23 Oct 2026
//
// Same panel size, same data pins, same touch chip, same card, same serial port, same backlight. Two pins are swapped
// between them (docs/dle06050b/5inch_ESP32-S3_Scehmeatic.pdf): the pixel clock is IO0 on the CrowPanel and IO42 on the
// twin; the speaker's bit clock is IO42 on the CrowPanel and IO0 on the twin. The twin's touch chip has its reset on
// IO38 (the CrowPanel leaves it unwired), and its interrupt on IO18, which is also the speaker's word clock: polled, never
// used as an interrupt. The wrong map is a black screen, so the firmware must know which board it is on before it draws:
// it asks the flash chip itself for its size (the JEDEC id, esp_flash_get_physical_size) - never the image header, which
// says what the firmware was BUILT for (a 4 MB build runs on a 16 MB chip and says 4 MB).
//
// Two builds of this one source (platformio.ini): STANDARD (env ota) fits the 4 MB boards' 1.9 MB slot and runs on both
// boards; FULL (env ota_full, -DLDRC_FULL) is for the 16 MB layout only (two 6.25 MB slots, default_16MB.csv). Which one
// a screen fetches is decided by the size of its own update slot, not its chip: see LdrcUpdate.cpp screenPart().
#pragma once
#include <Arduino.h>
#include <esp_flash.h>
#include <esp_ota_ops.h>

struct BoardPins {
    const char *name;                    // "crowpanel" | "ips16" (/status "board")
    int pclk, i2sBclk;                   // the swapped pair
    int touchRst, touchInt;              // -1: not wired (or not to be used)
    uint16_t hsFp, hsPw, hsBp, vsFp, vsPw, vsBp;   // the panel's timing (porches in pixel clocks / lines)
    uint32_t pclkHz;                     // 10 MHz on the CrowPanel: faster, and its DMA starves against our PSRAM writes (proven 28 Sep 2026); 14.5 on the twin (below)
    uint16_t psramRestUs;                // (1.11.116) every big move through the PSRAM rests this long each 6400 pixels (src/psram_pace.h; 0: full speed)
    bool flip;                           // (1.11.115) two panel buffers, a big change composed unseen and flipped to (src/page_flip.h)
    bool tone;                           // (1.11.116) the sound clips were mastered for the CrowPanel's small speaker (bass up, top down); the twin's bigger one undoes that in audioTask
};
static const BoardPins BOARD_CROWPANEL = { "crowpanel", 0, 42, -1, -1, 8, 4, 43, 8, 4, 12, 10000000, 0, false, false };
// (1.11.112) The twin's IPS panel shows only WHITE at 10 MHz (23 Oct 2026, first board on the bench: backlight on, no picture).
// Elecrow's own factory program for this board (factory-backup/factory_16MB_14c19f4966b8_first4MB.bin, disassembled: its
// Arduino_ESP32RGBPanel(40, 41, 39, 42, 45, 48, 47, 21, 14, 5, 6, 7, 15, 16, 4, 8, 3, 46, 9, 1, 0, 12, 4, 16, 0, 10, 4, 10, 1,
// 14500000) at 0x42001D8D) runs it at 14.5 MHz with these porches: 832 x 504 clocks a frame, 34.6 frames a second.
// (1.11.114) 12 MHz is no good either: the panel shows its own test pattern (black, blue, red, white in turn - 24 Oct 2026).
// So the twin keeps 14.5 MHz, and its whole-page copies rest 100 us every 8 rows instead (1.11.114, main.cpp copyRows):
// at full speed a page change sometimes slipped the picture sideways for a frame (the copy starves the panel's DMA of
// PSRAM time); 300 us cured that but spread the copy over two frames (a flicker); 100 us: "only the occasional flicker
// ... sometimes changing is completely perfect". (1.11.115) Still "a slight shake ... about half of the time": the twin flips
// between two panel buffers instead (src/page_flip.h). (1.11.116) And every big mover - not only the copies to the panel -
// rests 300 us each 6400 pixels (src/psram_pace.h): the page's background, big boxes, film pictures.
static const BoardPins BOARD_IPS16     = { "ips16",    42,  0, 38, -1, 12, 4, 16, 10, 4, 10, 14500000, 300, true, true };
static const BoardPins *board = &BOARD_CROWPANEL;
static uint32_t flashChipBytes = 0;      // what the chip says it is
static uint32_t flashImageBytes = 0;     // what the image header says the firmware was built for

#ifndef LDRC_BOARD_FORCE
#define LDRC_BOARD_FORCE 0               // a bench build may be pinned to a board: 1 the CrowPanel, 2 the twin
#endif
static void boardDetect() {
    uint32_t size = 0;
    if (esp_flash_get_physical_size(NULL, &size) != ESP_OK) size = 0;
    flashChipBytes = size;
    flashImageBytes = ESP.getFlashChipSize();
    board = size >= 16u * 1024u * 1024u ? &BOARD_IPS16 : &BOARD_CROWPANEL;    // in doubt (0): the CrowPanel, the board every screen was until now
    if (LDRC_BOARD_FORCE == 1) board = &BOARD_CROWPANEL;
    if (LDRC_BOARD_FORCE == 2) board = &BOARD_IPS16;
}
// The slot the next firmware would be written to: 1,966,080 bytes on the 4 MB layout, 6,553,600 on the 16 MB one.
static uint32_t boardSlotBytes() { const esp_partition_t *p = esp_ota_get_next_update_partition(NULL); return p ? p->size : 0; }
static const uint32_t BIG_SLOT = 4u * 1024u * 1024u;   // a slot this big or bigger: the 16 MB layout, which takes the FULL build
#ifdef LDRC_FULL
static const bool BUILD_FULL = true;
#else
static const bool BUILD_FULL = false;
#endif
static std::string boardWords() {         // for the boot log and /status: "ips16, flash 16 MB (image 16 MB), slot 6553600, build full"
    char b[120];
    snprintf(b, sizeof b, "%s, flash %lu MB (image %lu MB), psram %lu MB, slot %lu, build %s", board->name, (unsigned long) (flashChipBytes >> 20), (unsigned long) (flashImageBytes >> 20),
             (unsigned long) (ESP.getPsramSize() >> 20), (unsigned long) boardSlotBytes(), BUILD_FULL ? "full" : "standard");
    return b;
}
