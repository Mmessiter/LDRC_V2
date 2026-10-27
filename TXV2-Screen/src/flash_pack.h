// flash_pack.h - (1.11.138, 27 Oct 2026) THE PACK: on the 16 MB boards the pages, the fonts, the index, the web page and
// as many of the sounds as fit live in the 3.4 MB data partition the 16 MB layout carries and nothing used (default_16MB.csv,
// label "spiffs", 0xC90000). Malcolm, 27 Oct 2026: "let's store pictures, fonts, etc ... as this will probably read faster
// than sd. Then the 4 meg versions can be similar but a bit slower."
//
//   - READ through the chip's cache, memory-mapped (esp_partition_mmap), the way the firmware's own constants are read: a
//     page is a memcpy from flash (about 1 ms for the biggest, 27 kB) where the card took 16-20 ms, the fonts come up in
//     a few tens of ms where the card took 350, a sound clip is there at once. A memory-mapped read is NOT a flash
//     transaction through the driver (esp_partition_read), which holds the cache - and so the PSRAM, the strips' feeder,
//     the panel - for its whole duration (that is what a flash WRITE does, src/strip_feed.h); it is cache misses, 32 bytes
//     at a time, arbitrated like everything else.
//   - THERE WHEN THE CARD IS NOT: a card that dies, pops out or corrupts leaves every page, every font and the sounds; only
//     the pictures and films (35 MB and 180 MB, the card's for ever) go missing, and the code already lets them.
//   - The card stays the SOURCE: the update writes the card as it always did (one path for both boards); the pack is COPIED
//     from the card at start-up when it is missing or stale (a line on the panel, 15-30 s, after an update's restart) -
//     never in the loop, where flash writes would hold the panel. Stale = the updater or /put replaced a packed file (the
//     flag "packstale" in the preferences), or the card's index.json or a page's or font's size differs from the pack's
//     (a card swapped by hand). The build writes its header LAST: a power cut leaves no header, and no header = no pack.
//   - The 4 MB boards (STANDARD build) have no such partition: assetOpen() is the card, as before.
//
// Format (all little-endian, in the partition): Head at 0 (its own crc last), the table of Entry at 4096 (64 bytes each,
// up to 192), the files from 16384, each padded to 4 bytes. Nothing is kept in RAM: lookups scan the mapped table (161
// names, microseconds), a File over the pack is a pointer and a position.
#pragma once

static File assetOpen(const char *path);                 // the pack's copy when there is one, else the card's
static bool assetsOk();                                  // pages and sounds can be had (the card, or the pack)
static bool packCovers(const char *path);                // a path the pack mirrors: a change to it makes the pack stale
static void packMarkStale();
static std::string packJson();                           // /status "pack"

// (1.11.138) A card that goes while the screen runs. The first failed open costs the driver's timeout - 1.2 s measured on
// the twin with its card out - and so would every ask after it: the sound warm-up every 25 ms, every picture on every
// page (Malcolm: "instead of being faster, I think it's slower. Quite a lot slower"). So a failed open of a card file is
// followed, at most every 5 s, by one probe of a file every card holds; if that fails too the card is given up (sdOk
// false) until the next start: the pack carries on with the pages, fonts and sounds, pictures and films stand aside.
static uint32_t sdGoneMs = 0, sdProbeAt = 0;
static void sdGoneMaybe() {
    if (!sdOk) return;
    const uint32_t now = millis(); if (sdProbeAt && now - sdProbeAt < 5000) return; sdProbeAt = now;
    File f = SD.open("/hmi/index.json");
    if (f) { f.close(); return; }
    sdOk = false; sdGoneMs = now ? now : 1;
    blog("card", "gone: no answer to a probe (the pack carries on; pictures and films wait for the next start)");
}
static File sdOpenChecked(const char *path) {            // the card's file; a card that has gone is given up
    if (!sdOk) return File();
    File f = SD.open(path); if (!f) sdGoneMaybe(); return f;
}

#ifdef LDRC_FULL
#include <FS.h>
#include <FSImpl.h>                                      // fs::FileImpl, the shape a File reads through
#include <esp_partition.h>
#include <esp_spi_flash.h>

namespace pack {
static const uint32_t TABLE_AT = 4096, DATA_AT = 16384, ENTRY_MAX = (DATA_AT - TABLE_AT) / 64, BUILD_TRIES = 2;
struct Head { char magic[8]; uint32_t count, dataBytes, tableCrc, built, indexCrc, flags, nonce; uint32_t headCrc; };
struct Entry { char name[48]; uint32_t off, size, crc, pad; };
static const char MAGIC[9] = "LDRCPK01";
}

static const esp_partition_t *packPart = nullptr;
static const uint8_t *packMap = nullptr; static spi_flash_mmap_handle_t packMapH = 0;
static const pack::Entry *packTable = nullptr; static uint32_t packCount = 0;
static bool packOk = false; static std::string packWhy = "not mounted";
static uint32_t packBytes = 0, packBuilt = 0, packMountMs = 0, packBuildMs = 0, packOpens = 0, packSkipped = 0;
static uint32_t packSeen[(pack::ENTRY_MAX + 31) / 32] = {}, packBadMask[(pack::ENTRY_MAX + 31) / 32] = {};   // each file's checksum is read at its first use (a whole-pack check at start cost 290 ms)
static uint32_t packBadN = 0, packSweepAt = 0, packSweepPos = 0; static bool packSweepDone = false;   // the idle sweep of the card against the pack (packTick)

static bool packCovers(const char *p) {
    return !strncmp(p, "/hmi/pages/", 11) || !strncmp(p, "/hmi/font", 9) || !strcmp(p, "/hmi/index.json")
        || !strncmp(p, "/hmi/audio/", 11) || !strncmp(p, "/hmi/web/", 9);
}
static void packMarkStale() {                            // (a fresh change deserves fresh tries)
    if (prefs.getInt("packstale", 0) != 1) prefs.putInt("packstale", 1);
    if (prefs.getInt("packtries", 0) != 0) prefs.putInt("packtries", 0);
}

// A File over the pack: the mapped bytes, a position. Read-only; the rest of the FileImpl is the honest "no".
class PackFileImpl : public fs::FileImpl {
    const pack::Entry *e; size_t pos = 0; bool isOpen = true;
public:
    explicit PackFileImpl(const pack::Entry *entry) : e(entry) {}
    size_t write(const uint8_t *, size_t) override { return 0; }
    size_t read(uint8_t *buf, size_t n) override {
        if (!isOpen || pos >= e->size) return 0;
        const size_t k = min(n, (size_t) e->size - pos); memcpy(buf, packMap + e->off + pos, k); pos += k; return k;
    }
    void flush() override {}
    bool seek(uint32_t p, SeekMode mode) override {
        const size_t to = mode == SeekSet ? p : mode == SeekCur ? pos + p : (size_t) e->size - min((size_t) p, (size_t) e->size);
        if (to > e->size) return false;
        pos = to; return true;
    }
    size_t position() const override { return pos; }
    size_t size() const override { return e->size; }
    bool setBufferSize(size_t) override { return false; }
    void close() override { isOpen = false; }
    time_t getLastWrite() override { return 0; }
    const char *path() const override { return e->name; }
    const char *name() const override { const char *s = strrchr(e->name, '/'); return s ? s + 1 : e->name; }
    boolean isDirectory() override { return false; }
    fs::FileImplPtr openNextFile(const char *) override { return fs::FileImplPtr(); }
    boolean seekDir(long) override { return false; }
    String getNextFileName() override { return String(); }
    String getNextFileName(bool *) override { return String(); }
    void rewindDirectory() override {}
    operator bool() override { return isOpen; }
};

static const pack::Entry *packFind(const char *path) {
    if (!packOk || !packTable) return nullptr;
    for (uint32_t i = 0; i < packCount; ++i) {
        if (strncmp(packTable[i].name, path, sizeof(packTable[i].name))) continue;
        const uint32_t w = i >> 5, b = 1u << (i & 31);
        if (packBadMask[w] & b) return nullptr;            // found damaged once: the card's from then on
        if (!(packSeen[w] & b)) {                          // its first use: the checksum against the table's (a 27 kB page: well under a millisecond)
            if (ldrc::crc32(packMap + packTable[i].off, packTable[i].size) != packTable[i].crc) { packBadMask[w] |= b; ++packBadN; return nullptr; }
            packSeen[w] |= b;
        }
        return &packTable[i];
    }
    return nullptr;
}
static File assetOpen(const char *path) {
    if (const pack::Entry *e = packFind(path)) { ++packOpens; return File(std::make_shared<PackFileImpl>(e)); }
    if (packOk && packCovers(path)) ++packSkipped;         // a packed kind of file the pack has not got (a sound that did not fit): the card's
    return sdOpenChecked(path);
}
static bool assetsOk() { return sdOk || packOk; }

static bool packRoom() {
    if (!packPart) packPart = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_SPIFFS, nullptr);
    return packPart && packPart->size >= 2u * 1024u * 1024u;
}
// The pack as the flash holds it: mapped, its header and table checked (each file's checksum at its first use). packOk says.
static void packMount() {
    const uint32_t t0 = millis();
    packOk = false; packTable = nullptr; packCount = 0; packBytes = 0;
    memset(packSeen, 0, sizeof(packSeen)); memset(packBadMask, 0, sizeof(packBadMask)); packBadN = 0; packSweepPos = 0; packSweepDone = false;
    if (!packRoom()) { packWhy = "no partition"; return; }
    if (!packMap) {
        const void *p = nullptr;
        if (esp_partition_mmap(packPart, 0, packPart->size, SPI_FLASH_MMAP_DATA, &p, &packMapH) != ESP_OK || !p) { packWhy = "mmap failed"; return; }
        packMap = (const uint8_t *) p;
    }
    const pack::Head *h = (const pack::Head *) packMap;
    if (memcmp(h->magic, pack::MAGIC, 8)) { packWhy = "empty"; return; }
    if (ldrc::crc32((const uint8_t *) h, offsetof(pack::Head, headCrc)) != h->headCrc) { packWhy = "header damaged"; return; }
    if (!h->count || h->count > pack::ENTRY_MAX || pack::DATA_AT + h->dataBytes > packPart->size) { packWhy = "header odd"; return; }
    const pack::Entry *t = (const pack::Entry *) (packMap + pack::TABLE_AT);
    if (ldrc::crc32((const uint8_t *) t, h->count * sizeof(pack::Entry)) != h->tableCrc) { packWhy = "table damaged"; return; }
    uint32_t bytes = 0;
    for (uint32_t i = 0; i < h->count; ++i) {
        const pack::Entry &e = t[i];
        if (!memchr(e.name, 0, sizeof(e.name)) || e.off < pack::DATA_AT || e.off + e.size > pack::DATA_AT + h->dataBytes) { packWhy = "table odd"; return; }
        bytes += e.size;
    }
    packTable = t; packCount = h->count; packBytes = bytes; packBuilt = h->built; packOk = true; packWhy = "ok";
    packMountMs = millis() - t0;
}
static uint32_t packCrcOfCardFile(const char *path, bool &found) {
    File f = SD.open(path); found = (bool) f; if (!f) return 0;
    uint32_t c = 0; static uint8_t b[1024];
    while (f.available()) { const int n = f.read(b, sizeof(b)); if (n <= 0) break; c = ldrc::crc32(b, n, c); }
    f.close(); return c;
}
// Is the pack behind the card? (With no card there is nothing to be behind.) At start-up: the flag, and the card's
// index.json against the pack's (7 kB). The sizes of the files follow in the loop, one every two seconds (packTick):
// at start-up the 91 opens of the pages and fonts cost 1.1 s.
static const char *packStaleWhy() {
    if (!packOk) return "no pack";
    if (prefs.getInt("packstale", 0)) return "files replaced";
    if (!sdOk) return nullptr;
    bool found = false; const uint32_t c = packCrcOfCardFile("/hmi/index.json", found);
    if (found && c != ((const pack::Head *) packMap)->indexCrc) return "index differs";
    return nullptr;
}
static void packTick(bool idle) {                        // the card against the pack, one file every two seconds while idle: a card changed by hand
    if (!packOk || !sdOk || packSweepDone || !idle) return;
    const uint32_t now = millis(); if (now - packSweepAt < 2000) return; packSweepAt = now;
    if (packSweepPos >= packCount) { packSweepDone = true; return; }
    const pack::Entry &e = packTable[packSweepPos++];
    File f = SD.open(e.name); if (!f) { packSweepDone = true; return; }   // (the card gone, or the file: the pack keeps it; no more opens of a card that may be out)
    const uint32_t s = f.size(); f.close();
    if (s != e.size) { packMarkStale(); packOk = false; packWhy = std::string("the card differs: ") + e.name + " (the card until the next start)"; }
}

// ---- the build: from the card into the partition, at start-up only (setup), with a line on the panel
static void packSay(const std::string &s) {
    gfx->startWrite(); gfx->fillRect(0, 70, 800, 36, 0x0000); drawGlyphs(20, 76, 6, 0xFFFF, s); gfx->endWrite();
}
struct PackItem { std::string path; uint32_t size; };
static void packListDir(const char *dir, const char *ext, std::vector<PackItem> &out) {
    File d = SD.open(dir); if (!d || !d.isDirectory()) return;
    for (File f = d.openNextFile(); f; f = d.openNextFile()) {
        if (f.isDirectory()) { f.close(); continue; }
        std::string nm = f.name(); if (!nm.empty() && nm[0] != '/') nm = std::string(dir) + "/" + nm;   // (2.x's name() is the leaf)
        const size_t el = strlen(ext);
        if (nm.size() > el && nm.compare(nm.size() - el, el, ext) == 0 && nm.size() < sizeof(pack::Entry::name)) out.push_back({nm, (uint32_t) f.size()});
        f.close();
    }
    d.close();
}
static bool packBuild() {
    const uint32_t t0 = millis();
    packOk = false; packTable = nullptr;
    if (!packRoom() || !sdOk) { packWhy = "cannot build"; return false; }
    // 1. what goes in, in order: the index, the pages, the fonts, the web page, then the sounds smallest first while they fit
    std::vector<PackItem> items, pages, web, audio;
    { File f = SD.open("/hmi/index.json"); if (!f) { packWhy = "no index on the card"; return false; } items.push_back({"/hmi/index.json", (uint32_t) f.size()}); f.close(); }
    packListDir("/hmi/pages", ".json", pages);
    std::sort(pages.begin(), pages.end(), [](const PackItem &a, const PackItem &b) { return a.path < b.path; });
    for (auto &p : pages) items.push_back(p);
    for (int i = 0; i < 7; ++i) { char p[32]; snprintf(p, sizeof(p), "/hmi/font%d_aa.bin", i); File f = SD.open(p); if (f) { items.push_back({p, (uint32_t) f.size()}); f.close(); } }
    packListDir("/hmi/web", ".html", web); for (auto &p : web) items.push_back(p);
    packListDir("/hmi/audio", ".wav", audio);
    std::sort(audio.begin(), audio.end(), [](const PackItem &a, const PackItem &b) { return a.size != b.size ? a.size < b.size : a.path < b.path; });
    const uint32_t room = packPart->size - pack::DATA_AT;
    uint32_t total = 0; for (auto &it : items) total += (it.size + 3) & ~3u;
    if (items.size() > pack::ENTRY_MAX || total > room) { packWhy = "the pages and fonts alone do not fit"; return false; }
    for (auto &a : audio) { const uint32_t n = (a.size + 3) & ~3u; if (items.size() >= pack::ENTRY_MAX || total + n > room) break; items.push_back(a); total += n; }
    // 2. erase what will be written (the header's sector first of all: no header, no pack, from here on)
    char line[120];
    snprintf(line, sizeof(line), "Copying %u files (%lu kB) into the chip's own memory ...", (unsigned) items.size(), (unsigned long) (total >> 10)); packSay(line);
    const uint32_t end = (pack::DATA_AT + total + 4095u) & ~4095u;
    if (esp_partition_erase_range(packPart, 0, end) != ESP_OK) { packWhy = "erase failed"; return false; }
    // 3. the files, read from the card in slabs of the chip's own RAM, each checksummed as it goes
    uint8_t *buf = (uint8_t *) heap_caps_malloc(16384, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    pack::Entry *table = (pack::Entry *) heap_caps_calloc(pack::ENTRY_MAX, sizeof(pack::Entry), MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    if (!buf || !table) { free(buf); free(table); packWhy = "no memory"; return false; }
    uint32_t off = pack::DATA_AT, indexCrc = 0, count = 0; bool good = true; std::string bad;
    for (size_t i = 0; i < items.size() && good; ++i) {
        const PackItem &it = items[i];
        File f = SD.open(it.path.c_str()); if (!f) { good = false; bad = it.path; break; }
        uint32_t crc = 0, written = 0, left = it.size;
        while (left) {
            const size_t want = min((size_t) left, (size_t) 16384);
            const int n = f.read(buf, want); if (n <= 0) { good = false; break; }
            crc = ldrc::crc32(buf, n, crc);
            size_t w = (size_t) n; while (w & 3) buf[w++] = 0;
            if (esp_partition_write(packPart, off + written, buf, w) != ESP_OK) { good = false; break; }
            written += w; left -= n;
        }
        f.close();
        if (!good) { bad = it.path; break; }
        pack::Entry &e = table[count++]; memset(&e, 0, sizeof(e)); strlcpy(e.name, it.path.c_str(), sizeof(e.name)); e.off = off; e.size = it.size; e.crc = crc;
        if (i == 0) indexCrc = crc;
        off += written;
        if ((i & 7) == 7 || i + 1 == items.size()) { snprintf(line, sizeof(line), "Copying %u files (%lu kB) into the chip's own memory ... %u%%", (unsigned) items.size(), (unsigned long) (total >> 10), (unsigned) ((i + 1) * 100 / items.size())); packSay(line); }
        delay(1);
    }
    if (!good) { free(buf); free(table); packWhy = "build failed at " + bad; return false; }
    // 4. the table, then the header (last: until it is there, there is no pack)
    pack::Head h = {}; memcpy(h.magic, pack::MAGIC, 8); h.count = count; h.dataBytes = off - pack::DATA_AT;
    h.tableCrc = ldrc::crc32((const uint8_t *) table, count * sizeof(pack::Entry)); h.built = (uint32_t) time(nullptr); h.indexCrc = indexCrc; h.nonce = esp_random();
    h.headCrc = ldrc::crc32((const uint8_t *) &h, offsetof(pack::Head, headCrc));
    good = esp_partition_write(packPart, pack::TABLE_AT, table, count * sizeof(pack::Entry)) == ESP_OK
        && esp_partition_write(packPart, 0, &h, sizeof(h)) == ESP_OK;
    free(buf); free(table);
    if (!good) { packWhy = "table or header not written"; return false; }
    // 5. seen through the map? (the driver flushes the cache for the pages it wrote; if this chip's did not, map afresh)
    packMount();
    if (!packOk || ((const pack::Head *) packMap)->nonce != h.nonce) {
        spi_flash_munmap(packMapH); packMap = nullptr; packMapH = 0; packMount();
        if (!packOk || ((const pack::Head *) packMap)->nonce != h.nonce) { packOk = false; packWhy = "written but not yet seen (a restart will)"; return false; }
    }
    prefs.putInt("packstale", 0); prefs.putInt("packtries", 0);
    packBuildMs = millis() - t0;
    return true;
}
// At start-up, after the card and the fonts: a missing or stale pack is built, up to twice in a row (a third failure waits
// for the next change or /pack/build - the start must not be slowed for ever).
static bool packStartup() {                              // true: a pack was built now (the fonts want reading again, from it)
    const char *why = packStaleWhy();
    if (!why) { blog("boot", packOk ? "pack ok" : "pack " + packWhy); return false; }
    if (!sdOk || !packRoom()) { blog("boot", std::string("pack ") + packWhy); return false; }
    const int tries = prefs.getInt("packtries", 0);
    if (tries >= (int) pack::BUILD_TRIES) { blog("boot", std::string("pack not rebuilt (gave up): ") + why); packOk = false; return false; }
    prefs.putInt("packtries", tries + 1);
    blog("boot", std::string("pack rebuild: ") + why);
    const bool ok = packBuild();
    if (ok) { char b[120]; snprintf(b, sizeof(b), "pack built: %lu files, %lu kB in %lu ms", (unsigned long) packCount, (unsigned long) (packBytes >> 10), (unsigned long) packBuildMs); blog("boot", b); }
    else blog("boot", "pack FAILED: " + packWhy);
    return ok;
}
static std::string packJson() {
    char b[300];
    snprintf(b, sizeof(b), "\"pack\":{\"ok\":%s,\"why\":\"%s\",\"files\":%lu,\"kb\":%lu,\"part_kb\":%lu,\"built\":%lu,\"mount_ms\":%lu,\"build_ms\":%lu,\"opens\":%lu,\"skipped\":%lu,\"bad\":%lu,\"swept\":%lu,\"stale\":%d}",
             packOk ? "true" : "false", packWhy.c_str(), (unsigned long) packCount, (unsigned long) (packBytes >> 10), (unsigned long) (packPart ? packPart->size >> 10 : 0),
             (unsigned long) packBuilt, (unsigned long) packMountMs, (unsigned long) packBuildMs, (unsigned long) packOpens, (unsigned long) packSkipped, (unsigned long) packBadN, (unsigned long) packSweepPos, prefs.getInt("packstale", 0));
    return b;
}
#else   // the 4 MB boards: no partition to speak of (min_spiffs.csv keeps 192 kB) - the card, as always
static File assetOpen(const char *path) { return sdOpenChecked(path); }
static bool assetsOk() { return sdOk; }
static bool packCovers(const char *) { return false; }
static void packMarkStale() {}
static void packMount() {}
static bool packStartup() { return false; }
static void packTick(bool) {}
static std::string packJson() { return "\"pack\":{\"ok\":false,\"why\":\"not on this board\"}"; }
#endif
