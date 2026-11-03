// LdrcCard: the card's own start, step by step, and what is on it (1.11.168, 3 Nov 2026).
//
// When the SD library cannot mount the card it says only "no". A builder needs to know which of two very different
// things went wrong: the slot never answered (a contact, the 3.3 V, one of the four lines), or the card answered and
// holds a format the screen cannot read (exFAT, a GPT table, nothing at all). Christoph in Germany, the first builder
// from the public repository, had "sd=0" with three cards, a 3 A supply and the right board, and no way to tell which.
//
// cardProbe() walks the card through its start in SPI mode at the slow clock the library also starts it at (CMD0,
// CMD8, ACMD41, CMD58, the CSD for its size), reads its first sector and the first FAT partition's boot sector, and
// says what it found in one line a person can act on. Use it only once the library has failed (or before it starts):
// its CMD0 resets the card, and a card in use would be pulled from under the library.
// The device gives it the wire (a byte each way, the select line, a clock); the host tests give it make-believe cards.
#pragma once
#include <stdint.h>
#include <string>

namespace ldrc {

struct CardWire {
    virtual uint8_t xfer(uint8_t out) = 0;         // one byte out on MOSI; the byte that came back on MISO
    virtual void select(bool on) = 0;               // the card's CS: low (on) or high
    virtual uint32_t ms() = 0;                      // a clock, for the time limits
    virtual ~CardWire() {}
};

struct CardReport {
    enum Step { NOTHING, ANSWERED, STARTED, READ, READABLE };
    Step step = NOTHING;         // how far it got: READABLE = a FAT the screen can read was found
    std::string kind;            // "SDHC/SDXC", "SDSC", "SDSC (v1)" once started
    uint64_t bytes = 0;          // its size from the CSD (0: not read)
    std::string what;            // what was found, for the glass and the boot log
    std::string advice;          // what to do about it ("" when the card holds a FAT the screen reads)
};

uint8_t cardCrc7(const uint8_t *d, int n);                        // a command's CRC byte (with its end bit)
std::string cardSector0(const uint8_t *s, uint32_t &partLba);     // what a first sector holds; partLba: the FAT partition to look in (0: none)
std::string cardBootSector(const uint8_t *s, bool &readable);     // what a partition's boot sector is; readable: a FAT the screen reads
uint64_t cardCsdBytes(const uint8_t *csd);                        // the size a CSD gives (0: a layout not known)
CardReport cardProbe(CardWire &w);

}
