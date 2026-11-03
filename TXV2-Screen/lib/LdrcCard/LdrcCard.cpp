// LdrcCard (see LdrcCard.h): the card's start in SPI mode, as the SD Association's simplified physical layer
// specification (chapter 7) and the SD library's own sd_diskio.cpp do it, then its first sectors read and named.
#include "LdrcCard.h"
#include <stdio.h>
#include <string.h>

namespace ldrc {

static std::string hex2(unsigned v) { char b[8]; snprintf(b, sizeof b, "%02X", v & 0xFF); return b; }
static uint32_t le32(const uint8_t *p) { return (uint32_t) p[0] | (uint32_t) p[1] << 8 | (uint32_t) p[2] << 16 | (uint32_t) p[3] << 24; }

uint8_t cardCrc7(const uint8_t *d, int n) {
    uint8_t crc = 0;
    for (int i = 0; i < n; ++i) {
        uint8_t b = d[i];
        for (int j = 0; j < 8; ++j) { crc <<= 1; if ((b ^ crc) & 0x80) crc ^= 0x09; b <<= 1; }
    }
    return (uint8_t) (crc << 1 | 1);
}

// One command: a byte of 0xFF first (time for the card), the six bytes, then up to nine bytes for the answer (R1, its
// top bit 0). The card checks the CRC of CMD0 and CMD8 only, until told otherwise; every command gets a right one.
static uint8_t command(CardWire &w, uint8_t cmd, uint32_t arg) {
    const uint8_t c[5] = { (uint8_t) (0x40 | cmd), (uint8_t) (arg >> 24), (uint8_t) (arg >> 16), (uint8_t) (arg >> 8), (uint8_t) arg };
    w.xfer(0xFF);
    for (int i = 0; i < 5; ++i) w.xfer(c[i]);
    w.xfer(cardCrc7(c, 5));
    uint8_t r = 0xFF;
    for (int i = 0; i < 9 && (r & 0x80); ++i) r = w.xfer(0xFF);
    return r;
}
static uint32_t word32(CardWire &w) { uint32_t v = 0; for (int i = 0; i < 4; ++i) v = v << 8 | w.xfer(0xFF); return v; }
static void letGo(CardWire &w) { w.select(false); w.xfer(0xFF); }      // a byte with CS high: the card lets go of MISO

// The block after CMD9 or CMD17: its start token (0xFE), the bytes, two CRC bytes. Returns 0xFE when read, the card's
// error token (0x0N), or 0xFF when none came in time.
static uint8_t block(CardWire &w, uint8_t *out, int n, uint32_t limitMs) {
    const uint32_t t0 = w.ms(); uint8_t t = 0xFF;
    for (long i = 0; i < 200000 && (t = w.xfer(0xFF)) == 0xFF && w.ms() - t0 < limitMs; ++i) {}
    if (t != 0xFE) return t;
    for (int i = 0; i < n; ++i) out[i] = w.xfer(0xFF);
    w.xfer(0xFF); w.xfer(0xFF);
    return 0xFE;
}

// A FAT boot sector, as FatFs's check_fs knows one: a jump first, then "FAT32" where FAT32 names itself, "FAT" where
// FAT12 and FAT16 do.
static bool fatBoot(const uint8_t *s, bool &fat32) {
    if (s[0] != 0xEB && s[0] != 0xE9 && s[0] != 0xE8) return false;
    if (s[510] != 0x55 || s[511] != 0xAA) return false;
    if (!memcmp(s + 82, "FAT32", 5)) { fat32 = true; return true; }
    if (!memcmp(s + 54, "FAT", 3)) { fat32 = false; return true; }
    return false;
}
static bool fatType(uint8_t t) { return t == 0x01 || t == 0x04 || t == 0x06 || t == 0x0E || t == 0x0B || t == 0x0C; }
static const char *typeName(uint8_t t) {
    switch (t) {
    case 0x01: return "FAT12";
    case 0x04: case 0x06: case 0x0E: return "FAT16";
    case 0x0B: case 0x0C: return "FAT32";
    case 0x07: return "exFAT or NTFS";
    case 0x83: return "Linux";
    case 0xAF: return "Mac";
    case 0xEF: return "EFI";
    default: return "not FAT";
    }
}

std::string cardSector0(const uint8_t *s, uint32_t &partLba) {
    partLba = 0;
    if (!memcmp(s + 3, "EXFAT   ", 8)) return "exFAT, with no partition table";
    if (!memcmp(s + 3, "NTFS    ", 8)) return "NTFS, with no partition table";
    bool fat32 = false;
    if (fatBoot(s, fat32)) return fat32 ? "FAT32, with no partition table" : "FAT16, with no partition table";
    if (s[510] != 0x55 || s[511] != 0xAA) {
        bool zeros = true, ones = true;
        for (int i = 0; i < 512; ++i) { zeros = zeros && s[i] == 0x00; ones = ones && s[i] == 0xFF; }
        return zeros || ones ? "blank (never formatted, or wiped)" : "no partition table (its first sector is neither a table nor a format)";
    }
    int first = -1, fat = -1;                              // the first partition of any kind, the first FAT one (FatFs looks at all four)
    for (int i = 0; i < 4; ++i) {
        const uint8_t *e = s + 446 + 16 * i;
        if (!e[4]) continue;
        if (first < 0) first = i;
        if (fat < 0 && fatType(e[4]) && le32(e + 8)) fat = i;
    }
    if (first < 0) return "a partition table with no partition in it";
    if (s[446 + 16 * first + 4] == 0xEE) return "a GPT partition table";
    const int i = fat >= 0 ? fat : first;
    const uint8_t t = s[446 + 16 * i + 4];
    if (fat >= 0) partLba = le32(s + 446 + 16 * i + 8);
    return "partition " + std::to_string(i + 1) + " of type " + hex2(t) + " (" + typeName(t) + ")";
}

std::string cardBootSector(const uint8_t *s, bool &readable) {
    readable = false;
    if (!memcmp(s + 3, "EXFAT   ", 8)) return "exFAT";
    if (!memcmp(s + 3, "NTFS    ", 8)) return "NTFS";
    bool fat32 = false;
    if (!fatBoot(s, fat32)) return "no format where it starts";
    const unsigned bps = s[11] | s[12] << 8;
    if (bps != 512) return "FAT with " + std::to_string(bps) + "-byte sectors";
    readable = true;
    return fat32 ? "FAT32" : "FAT16";
}

uint64_t cardCsdBytes(const uint8_t *csd) {
    switch (csd[0] >> 6) {
    case 0: {                                              // version 1 (SDSC): (C_SIZE + 1) x 2^(C_SIZE_MULT + 2) blocks of 2^READ_BL_LEN bytes
        const uint32_t cs = (uint32_t) (csd[6] & 0x03) << 10 | (uint32_t) csd[7] << 2 | csd[8] >> 6;
        const unsigned mult = (csd[9] & 0x03) << 1 | csd[10] >> 7, bl = csd[5] & 0x0F;
        return (uint64_t) (cs + 1) << (mult + 2 + bl);
    }
    case 1: {                                              // version 2 (SDHC, SDXC): (C_SIZE + 1) x 512 kB
        const uint32_t cs = (uint32_t) (csd[7] & 0x3F) << 16 | (uint32_t) csd[8] << 8 | csd[9];
        return (uint64_t) (cs + 1) * 512 * 1024;
    }
    default: return 0;
    }
}

static std::string gb(uint64_t b) { char t[24]; snprintf(t, sizeof t, "%.1f GB", (double) b / 1e9); return t; }

CardReport cardProbe(CardWire &w) {
    CardReport rep;
    // 1. Eighty clocks with the card not selected (it needs 74 to wake). Its data line rests high on the slot's pull-up.
    w.select(false);
    int low = 0;
    for (int i = 0; i < 10; ++i) if (w.xfer(0xFF) == 0x00) low++;
    // 2. CMD0, the reset, up to five times: a card answers 01 (idle, in SPI mode).
    uint8_t r = 0xFF;
    for (int i = 0; i < 5 && r != 0x01; ++i) { w.select(true); r = command(w, 0, 0); if (r != 0x01) letGo(w); }
    if (r != 0x01) {
        if (r == 0x00 && low == 10) { rep.what = "IO13, the card's data line, is held low"; rep.advice = "look for a short to ground on IO13 or on the slot's DO pin"; }
        else if (r == 0xFF) { rep.what = "no card answered: IO13, its data line, never moved"; rep.advice = "push the card in until it clicks; check 3.3 V at the slot, and its lines to IO10 (CS), IO11 (MOSI), IO12 (CLK) and IO13 (MISO)"; }
        else { rep.what = "a card answered its reset with " + hex2(r) + ", not 01"; rep.advice = "a poor contact in the slot, or a card that cannot work over SPI: try another card"; }
        return rep;
    }
    rep.step = CardReport::ANSWERED;
    // 3. CMD8, the voltage check: a card of version 2 or later (SDHC, SDXC: every card of the last fifteen years) echoes
    //    1AA; an older one does not know the command (05).
    bool v2 = false;
    r = command(w, 8, 0x1AA);
    if (r == 0x01) {
        const uint32_t echo = word32(w);
        if ((echo & 0xFFF) != 0x1AA) { letGo(w); rep.what = "the card answered, then failed its voltage check (" + hex2(echo >> 8) + hex2(echo) + ")"; rep.advice = "a poor contact in the slot, or a card that will not run on 3.3 V: try another card"; return rep; }
        v2 = true;
    } else if (!(r & 0x04)) { letGo(w); rep.what = "the card answered its reset, but not its voltage check (" + hex2(r) + ")"; rep.advice = "a poor contact in the slot: try another card"; return rep; }
    // 4. ACMD41 (CMD55, CMD41) until the card says it is ready: up to a second by the standard; most take 0.1 to 0.5 s.
    const uint32_t t0 = w.ms();
    do {
        r = command(w, 55, 0);
        if (r > 0x01) break;
        r = command(w, 41, v2 ? 0x40000000 : 0);
    } while (r == 0x01 && w.ms() - t0 < 1500);
    if (r != 0x00) {
        letGo(w);
        if (r == 0x01) { rep.what = "the card answered but never finished starting (still busy after 1.5 s)"; rep.advice = "its 3.3 V may sag as it starts: measure it at the slot; or try another card"; }
        else { rep.what = "the card answered but refused to start (" + hex2(r) + ")"; rep.advice = "try another card"; }
        return rep;
    }
    rep.step = CardReport::STARTED;
    // 5. CMD58, the OCR: bit 30 set = the card counts in sectors (SDHC, SDXC), not in bytes (SDSC).
    bool hc = false;
    if (v2 && command(w, 58, 0) == 0x00) hc = (word32(w) & 0x40000000) != 0;
    rep.kind = hc ? "SDHC/SDXC" : v2 ? "SDSC" : "SDSC (v1)";
    if (!hc) command(w, 16, 512);                          // (512-byte blocks: the default, but some want telling)
    // 6. CMD9, the CSD: its size.
    uint8_t csd[16];
    if (command(w, 9, 0) == 0x00 && block(w, csd, 16, 300) == 0xFE) rep.bytes = cardCsdBytes(csd);
    const std::string card = rep.kind + (rep.bytes ? " " + gb(rep.bytes) : std::string()) + " card";
    // 7. CMD17: the first sector, then the boot sector of the FAT partition it names.
    uint8_t s[512];
    r = command(w, 17, 0);
    uint8_t t = r == 0x00 ? block(w, s, 512, 500) : r;
    if (t != 0xFE) { letGo(w); rep.what = card + " started, but its first sector would not read (" + hex2(t) + ")"; rep.advice = "a poor contact in the slot, or a failing card: try another card"; return rep; }
    rep.step = CardReport::READ;
    uint32_t lba = 0;
    std::string fmt = cardSector0(s, lba);
    bool readable = fmt.rfind("FAT32,", 0) == 0 || fmt.rfind("FAT16,", 0) == 0;
    if (lba) {
        r = command(w, 17, hc ? lba : lba * 512);
        t = r == 0x00 ? block(w, s, 512, 500) : r;
        if (t != 0xFE) { letGo(w); rep.what = card + ": " + fmt + ", whose start would not read (" + hex2(t) + ")"; rep.advice = "a poor contact in the slot, or a failing card: try another card"; return rep; }
        fmt += ", formatted " + cardBootSector(s, readable);
    }
    letGo(w);
    rep.what = card + ": " + fmt;
    if (readable) rep.step = CardReport::READABLE;
    else if (fmt.find("GPT") != std::string::npos) rep.advice = "the screen reads only the older MBR table: format the card again with the SD Association's SD Card Formatter, or on Windows";
    else rep.advice = "the screen reads FAT32 only: format the card FAT32 (32 GB or less; the SD Association's SD Card Formatter does it right)";
    return rep;
}

}
