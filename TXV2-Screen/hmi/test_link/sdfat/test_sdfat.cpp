// The restore of models.dat as the TEENSY carries it out (see run.sh).
//   - the REAL LinkServer (TXV1B/TransmitterCode/lib/LdrcLink/LinkServer.cpp), asked by frames as the screen sends them;
//   - the REAL SdFat of Teensyduino (FatLib, built for the Mac with the Teensy's settings) on a FAT32 volume in memory;
//   - TeensyCard as in include/LinkMode.h, and the firmware's own use of models.dat as in include/SDcard.h and
//     SDFiles.h: OpenModelsFile(), CloseModelsFile(), SDUpdate8BITS() (seek, write one byte), SaveAllParameters().
// Nothing here is the transmitter's hardware: what is shown is what SdFat does with that sequence of calls.
//
// Two ways of doing it are run:
//   AS IT WAS  (2.5.6 B7): LinkMode() closed nothing, and the power-off save wrote what was in memory.
//   AS IT IS   (2.5.6 B8): memory is saved on the way into the link, models.dat is closed for as long as the link is
//              open, nothing is saved once a file of the pilot's has been replaced, and the transmitter restarts.
// The first MUST show the damage (or this test sees nothing), the second must show none.
#include "FatLib/FatLib.h"
#include "LdrcLink.h"
#include "LinkServer.h"
#include <unordered_map>
#include <array>
#include <vector>
#include <string>
#include <cstdio>
#include <cstring>
#include <cstdlib>

unsigned long millis(void) { return 1234; }
using namespace ldrc;
typedef std::vector<uint8_t> Bytes;

static int failures = 0, checks = 0;
#define CHECK(cond, what) do { checks++; if (!(cond)) { failures++; printf("   FAIL: %s  (line %d)\n", what, __LINE__); } } while (0)

// ------------------------------------------------------------------ a card in memory (only the sectors written are kept)
class RamDisk : public FsBlockDeviceInterface {
public:
    std::unordered_map<uint32_t, std::array<uint8_t, 512> > sec; uint32_t count;
    explicit RamDisk(uint32_t sectors) : count(sectors) {}
    bool isBusy() { return false; }
    bool readSector(uint32_t s, uint8_t *dst) { std::unordered_map<uint32_t, std::array<uint8_t, 512> >::iterator it = sec.find(s); if (it == sec.end()) memset(dst, 0, 512); else memcpy(dst, it->second.data(), 512); return s < count; }
    bool readSectors(uint32_t s, uint8_t *dst, size_t ns) { for (size_t i = 0; i < ns; ++i) if (!readSector(s + (uint32_t) i, dst + 512 * i)) return false; return true; }
    uint32_t sectorCount() { return count; }
    bool syncDevice() { return true; }
    bool writeSector(uint32_t s, const uint8_t *src) { if (s >= count) return false; memcpy(sec[s].data(), src, 512); return true; }
    bool writeSectors(uint32_t s, const uint8_t *src, size_t ns) { for (size_t i = 0; i < ns; ++i) if (!writeSector(s + (uint32_t) i, src + 512 * i)) return false; return true; }
};
static void stamp(uint16_t *date, uint16_t *time) { *date = FS_DATE(2026, 9, 29); *time = FS_TIME(21, 0, 0); }

static FatVolume *vol = 0;                           // for a FAT card, this is what Teensy's SD.sdfs comes down to

// ------------------------------------------------------------------ Teensy's SD (libraries/SD/src/SD.h)
#define FILE_READ 0
#define FILE_WRITE 1
struct SDish {
    File32 open(const char *path, uint8_t mode = FILE_READ) { oflag_t flags = O_RDONLY; if (mode == FILE_WRITE) flags = O_RDWR | O_CREAT | O_AT_END; return vol->open(path, flags); }
    bool exists(const char *p) { return vol->exists(p); }
    bool remove(const char *p) { return vol->remove(p); }
    bool rename(const char *a, const char *b) { return vol->rename(a, b); }
    bool mkdir(const char *p) { return vol->mkdir(p); }
} SD;
static void KickTheDog() {}

// ------------------------------------------------------------------ TeensyCard, as in TXV1B/TransmitterCode/include/LinkMode.h
class TeensyCard : public ldrc::LinkFs {
public:
    TeensyCard() { for (int i = 0; i < SLOTS; ++i) used_[i] = false; }
    bool present() override { return true; }
    bool exists(const char *path) override { return SD.exists(path); }
    bool remove(const char *path) override { return SD.remove(path); }
    bool rename(const char *from, const char *to) override { return SD.rename(from, to); }
    bool mkdir(const char *path) override { return SD.mkdir(path); }
    int open(const char *path, bool forWriting) override {
        for (int i = 0; i < SLOTS; ++i) {
            if (used_[i]) continue;
            if (forWriting) SD.remove(path);
            file_[i] = SD.open(path, forWriting ? FILE_WRITE : FILE_READ);
            if (!file_[i]) return -1;
            used_[i] = true; return i;
        }
        return -1;
    }
    int read(int h, uint8_t *buf, size_t n) override { return good(h) ? (int) file_[h].read(buf, n) : -1; }
    int write(int h, const uint8_t *buf, size_t n) override { return good(h) ? (int) file_[h].write(buf, n) : -1; }
    bool seek(int h, uint32_t pos) override { return good(h) && file_[h].seekSet(pos); }
    uint32_t size(int h) override { return good(h) ? (uint32_t) file_[h].fileSize() : 0; }
    void close(int h) override { if (good(h)) { file_[h].close(); used_[h] = false; } }
    int entry(const char *dir, uint32_t index, char *name, size_t nameSize, uint32_t &size, bool &isDir) override {
        File32 d = SD.open(dir);
        if (!d) return -1;
        if (!d.isDir()) { d.close(); return -1; }
        uint32_t i = 0; bool found = false;
        for (;;) {
            File32 e; e.openNext(&d, O_RDONLY);
            if (!e) break;
            if (i++ == index) {
                char full[256]; e.getName(full, sizeof full);        // (SDFile::name(): MAX_FILENAME_LEN 256)
                strlcpy(name, full, nameSize); size = (uint32_t) e.fileSize(); isDir = e.isDir(); found = true;
            }
            e.close();
            if (found) break;
            if ((i & 15) == 0) KickTheDog();
        }
        d.close();
        return found ? 1 : 0;
    }
private:
    enum { SLOTS = 3 };
    bool good(int h) const { return h >= 0 && h < SLOTS && used_[h]; }
    File32 file_[SLOTS]; bool used_[SLOTS];
};
struct Chip : public LinkPlatform {
    const char *firmwareVersion() { return "2.5.6 B8 29/09/26"; } const char *target() { return "fw_teensy41"; } const char *updateState() { return "confirmed"; }
    uint8_t stageFirmware(const char *) { return LE_UNSUPPORTED; } uint8_t stagePrevious() { return LE_UNSUPPORTED; } void confirmFirmware() {} void busy() {}
};

// ------------------------------------------------------------------ the firmware's own use of models.dat (SDFiles.h, SDcard.h)
static const uint32_t TXSIZE = 512, MODELSIZE = 1024 * 3, MODELS = 90;
static const uint32_t TX_WRITTEN = 400, MODEL_WRITTEN = 2500;        // how much of each SaveAllParameters() writes: assumed ("most of it")
static File32 ModelsFileNumber; static bool ModelsFileOpen = false, FileError = false;
static bool LinkChangedUserData = false;                            // (LinkMode.h, 2.5.6 B8)
static bool guarded = true;                                         // false: the saves as they were in 2.5.6 B7
static void OpenModelsFile() { if (!ModelsFileOpen) { ModelsFileNumber = SD.open("models.dat", FILE_WRITE); if (!ModelsFileNumber) FileError = true; else ModelsFileOpen = true; } }
static void CloseModelsFile() { if (ModelsFileOpen) { ModelsFileNumber.close(); ModelsFileOpen = false; } }
static int writeFails = 0, seekFails = 0, savesDone = 0;
static void SDUpdate8BITS(int a, uint8_t v) { if (!ModelsFileNumber.seekSet((uint32_t) a)) seekFails++; if (ModelsFileNumber.write(&v, 1) != 1) writeFails++; }
static uint8_t SDRead8BITS(int a) { ModelsFileNumber.seekSet((uint32_t) a); return (uint8_t) ModelsFileNumber.read(); }
static uint8_t ramTx[TX_WRITTEN], ramModel[MODEL_WRITTEN]; static uint32_t ModelNumber = 3;
static void LoadAllParameters() {                     // ... and ReadOneModel(ModelNumber): the file is left OPEN (no CloseModelsFile() at their end)
    if (!ModelsFileOpen) OpenModelsFile();
    for (uint32_t i = 0; i < TX_WRITTEN; ++i) ramTx[i] = SDRead8BITS((int) i);
    for (uint32_t i = 0; i < MODEL_WRITTEN; ++i) ramModel[i] = SDRead8BITS((int) (TXSIZE + (ModelNumber - 1) * MODELSIZE + i));
}
static void SaveTransmitterParameters() { if (guarded && LinkChangedUserData) return; if (!ModelsFileOpen) OpenModelsFile(); for (uint32_t i = 0; i < TX_WRITTEN; ++i) SDUpdate8BITS((int) i, ramTx[i]); CloseModelsFile(); }
static void SaveOneModel(uint32_t n) { if (guarded && LinkChangedUserData) return; if (!ModelsFileOpen) OpenModelsFile(); for (uint32_t i = 0; i < MODEL_WRITTEN; ++i) SDUpdate8BITS((int) (TXSIZE + (n - 1) * MODELSIZE + i), ramModel[i]); CloseModelsFile(); }
static void SaveAllParameters() { if (guarded && LinkChangedUserData) return; if (!ModelsFileOpen) OpenModelsFile(); SaveTransmitterParameters(); SaveOneModel(ModelNumber); savesDone++; }   // Close_TX_Down() calls this at every power-off

// ------------------------------------------------------------------ helpers
static Bytes blob(size_t n, uint32_t seed) { Bytes v(n); uint32_t s = seed * 2654435761u + 1; for (size_t i = 0; i < n; ++i) { s = s * 1664525u + 1013904223u; v[i] = (uint8_t) (s >> 16); } return v; }
static bool writeFile(const char *path, const Bytes &b) { vol->remove(path); File32 f = vol->open(path, O_RDWR | O_CREAT); if (!f) return false; const bool ok = b.empty() || f.write(&b[0], b.size()) == b.size(); f.close(); return ok; }
static bool readFile(FatVolume &v, const char *path, Bytes &out) {
    out.clear(); File32 f = v.open(path, O_RDONLY);
    if (!f) return false;
    const uint32_t size = (uint32_t) f.fileSize(); uint8_t buf[4096]; int n;
    while ((n = f.read(buf, sizeof buf)) > 0) out.insert(out.end(), buf, buf + n);
    f.close();
    return n >= 0 && out.size() == size;
}
static uint8_t ask(LinkServer &s, Frame &q, Frame &a) { s.handle(q, a); return a.len ? a.payload[0] : 0xFF; }
static uint8_t seqNo = 0;
// what LinkMaster sends for put(local, remote, LF_USER_DATA, onlyIfDifferent = true), as /teensy/restore queues it
static bool restoreOne(LinkServer &s, const char *remote, const Bytes &b) {
    Frame q, a; const uint32_t crc = crc32(b.empty() ? (const uint8_t *) "" : &b[0], b.size());
    q.clear(LK_STAT, ++seqNo); q.putText(remote);
    if (ask(s, q, a) != LE_OK) return false;
    if (a.get8(1) && a.get32(2) == b.size() && a.get32(6) == crc) return true;          // already the same
    q.clear(LK_WRITE_BEGIN, ++seqNo); q.put8(LF_USER_DATA); q.put32((uint32_t) b.size()); q.put32(crc); q.putText(remote);
    if (ask(s, q, a) != LE_OK) return false;
    for (uint32_t at = 0; at < b.size(); at += LINK_BLOCK) {
        const uint32_t n = (uint32_t) b.size() - at > LINK_BLOCK ? LINK_BLOCK : (uint32_t) b.size() - at;
        q.clear(LK_WRITE_DATA, ++seqNo); q.put32(at); q.putBytes(&b[at], n);
        if (ask(s, q, a) != LE_OK) return false;
    }
    q.clear(LK_WRITE_END, ++seqNo);
    return ask(s, q, a) == LE_OK;
}

// How the card is after: a restore of models.dat and two model files, the power button pressed while the link is
// still open, the link closed, and the transmitter switched off and on again.
struct After { bool modelsWhole, modelsAreTheSet, opens, goblin, raw, help, log; int failedWrites; bool restarted; };
static After scenario(bool asItIs, bool handleOpen, bool modsDiffer) {
    After r; memset(&r, 0, sizeof r);
    RamDisk disk(8u * 1024u * 2048u);                                     // 8 GB: FAT32, 32 kB clusters
    { uint8_t buf[512]; FatFormatter fmt; if (!fmt.format(&disk, buf, 0)) { printf("format failed\n"); exit(2); } }
    FatVolume v; vol = &v; FsDateTime::setCallback(stamp);
    if (!v.begin(&disk)) { printf("no volume\n"); exit(2); }
    const Bytes oldModels = blob(TXSIZE + MODELS * MODELSIZE, 1), newModels = blob(TXSIZE + MODELS * MODELSIZE, 2);   // what is on the card now; what the set on the screen's card holds
    const Bytes oldGoblin = blob(1600, 3), newGoblin = modsDiffer ? blob(1600, 4) : oldGoblin, oldRaw = blob(1640, 5), newRaw = modsDiffer ? blob(1640, 6) : oldRaw, help = blob(3000, 7), log = blob(20000, 8);
    writeFile("/models.dat", oldModels);
    v.mkdir("/mod"); v.mkdir("/log"); v.mkdir("/help"); v.mkdir("/FW");
    writeFile("/mod/GOBLIN.MOD", oldGoblin); writeFile("/mod/RAW420.MOD", oldRaw); writeFile("/help/AUDIO.TXT", help); writeFile("/log/28-09-26.LOG", log);

    // ---- power-on
    guarded = asItIs; LinkChangedUserData = false; ModelsFileOpen = false; FileError = false; writeFails = seekFails = savesDone = 0;
    LoadAllParameters();
    if (!handleOpen) SaveAllParameters();                                 // (the pilot changed a setting: the saves close the file)

    // ---- the screen knocks: LinkMode()
    {
        TeensyCard card; Chip chip; LinkServer server(card, chip);
        if (asItIs) { if (!LinkChangedUserData) SaveAllParameters(); CloseModelsFile(); }
        bool ok = restoreOne(server, "/models.dat", newModels);
        if (asItIs && server.userDataChanged()) LinkChangedUserData = true;
        ok = restoreOne(server, "/mod/GOBLIN.MOD", newGoblin) && ok;
        ok = restoreOne(server, "/mod/RAW420.MOD", newRaw) && ok;
        if (asItIs && server.userDataChanged()) LinkChangedUserData = true;
        SaveAllParameters();                                              // the power button, pressed while the link is open ("Saving <model>")
        Frame q, a; q.clear(LK_BYE, ++seqNo); server.handle(q, a);
        if (!ok) { printf("   the restore itself failed\n"); exit(2); }
        if (asItIs && LinkChangedUserData) {                              // the link closes: the transmitter starts again, from its card
            CloseModelsFile(); LinkChangedUserData = false; ModelsFileOpen = false; FileError = false;
            LoadAllParameters(); r.restarted = true;
        }
    }
    // ---- later the pilot switches off: Close_TX_Down() -> SaveAllParameters()
    SaveAllParameters();
    r.failedWrites = writeFails + seekFails;
    CloseModelsFile();
    v.cacheClear();

    // ---- the next power-on: the card as it now is
    FatVolume next; if (!next.begin(&disk)) { printf("   the volume cannot be mounted\n"); exit(2); }
    Bytes now;
    r.modelsWhole = readFile(next, "/models.dat", now);
    r.modelsAreTheSet = r.modelsWhole && now == newModels;
    { File32 f = next.open("models.dat", O_RDWR | O_CREAT | O_AT_END); r.opens = (bool) f; if (f) f.close(); }
    r.goblin = readFile(next, "/mod/GOBLIN.MOD", now) && now == newGoblin;
    r.raw = readFile(next, "/mod/RAW420.MOD", now) && now == newRaw;
    r.help = readFile(next, "/help/AUDIO.TXT", now) && now == help;
    r.log = readFile(next, "/log/28-09-26.LOG", now) && now == log;
    vol = 0;
    return r;
}

int main() {
    printf("- the restore as it WAS (2.5.6 B7): this test must be able to see the damage\n");
    {
        const After open = scenario(false, true, true), closed = scenario(false, false, true);
        CHECK(!open.modelsWhole || !open.goblin || !open.opens, "with the handle open (as after every power-on) the card was damaged");
        CHECK(closed.modelsWhole && !closed.modelsAreTheSet, "with the handle closed the card was sound, but the settings of before the restore were written over it");
        printf("      handle open:   models.dat %s, opens %s, GOBLIN.MOD %s, %d writes or seeks failed\n", open.modelsWhole ? "can be read" : "CANNOT BE READ TO ITS END", open.opens ? "yes" : "NO", open.goblin ? "sound" : "DAMAGED", open.failedWrites);
        printf("      handle closed: models.dat %s\n", closed.modelsAreTheSet ? "is the set" : "is NOT the set that was restored");
    }
    printf("- the restore as it IS (2.5.6 B8): whatever the handle, whatever the model files\n");
    for (int i = 0; i < 4; ++i) {
        const bool handleOpen = i & 1, modsDiffer = i & 2;
        const After a = scenario(true, handleOpen, modsDiffer);
        CHECK(a.modelsWhole && a.modelsAreTheSet, "models.dat is the set that was restored, byte for byte, after the power button, a restart and a power cycle");
        CHECK(a.opens, "it opens at the next power-on");
        CHECK(a.goblin && a.raw, "both model files are the set's");
        CHECK(a.help && a.log, "the help text and the log are untouched");
        CHECK(a.failedWrites == 0 && a.restarted, "no write and no seek failed; the transmitter restarted when the link closed");
    }

    printf("- names that SdFat takes for the pilot's files, asked of the real server without the flag that says \"the pilot's data\"\n");
    {
        RamDisk disk(8u * 1024u * 2048u); { uint8_t buf[512]; FatFormatter fmt; fmt.format(&disk, buf, 0); }
        FatVolume v; vol = &v; v.begin(&disk);
        v.mkdir("/mod"); writeFile("/MODELS.DAT", blob(5000, 1)); writeFile("/mod/GOBLIN.MOD", blob(1600, 2));
        TeensyCard card; Chip chip; LinkServer server(card, chip);
        const char *names[] = { "/MODELS.DAT", "/MODELS.DAT.", "/MODELS.DAT ", "/mod/GOBLIN.MOD", "/ mod/GOBLIN.MOD.", "/mod./GOBLIN.MOD" };
        const char *real[] = { "/MODELS.DAT", "/MODELS.DAT", "/MODELS.DAT", "/mod/GOBLIN.MOD", "/mod/GOBLIN.MOD", "/mod/GOBLIN.MOD" };
        bool allThere = true, allRefused = true;
        for (int i = 0; i < 6; ++i) {
            Frame q, a; q.clear(LK_DELETE, ++seqNo); q.put8(0); q.putText(names[i]);
            if (ask(server, q, a) == LE_OK) allRefused = false;
            if (!v.exists(real[i])) { allThere = false; printf("      DELETE \"%s\" removed %s\n", names[i], real[i]); }
        }
        CHECK(allRefused && allThere, "not one is removed");
        Frame q, a; const Bytes evil = blob(1000, 77); const uint32_t crc = crc32(&evil[0], evil.size());
        q.clear(LK_WRITE_BEGIN, ++seqNo); q.put8(0); q.put32((uint32_t) evil.size()); q.put32(crc); q.putText("/MODELS.DAT.");
        CHECK(ask(server, q, a) != LE_OK, "a write to \"/MODELS.DAT.\" is refused at once");
        Bytes now; CHECK(readFile(v, "/MODELS.DAT", now) && now == blob(5000, 1), "and the models are as they were");
        CHECK(!server.userDataChanged(), "nothing of the pilot's counts as changed");

        const std::string longName = "Goblin 700 Kyle Stacy - the setup before the tail rebuild of August 2026.MOD";
        writeFile(("/mod/" + longName).c_str(), blob(2000, 9));
        q.clear(LK_LIST, ++seqNo); q.put32(0); q.putText("/mod");
        CHECK(ask(server, q, a) == LE_OK, "the folder is listed");
        const int count = a.get8(1); size_t at = 3; bool fetched = true, seen = false;
        for (int i = 0; i < count; ++i) {
            at += 5; std::string name; while (at < a.len && a.payload[at]) name.push_back((char) a.payload[at++]); at++;
            if (name == longName) seen = true;
            Frame r, b; r.clear(LK_READ_BEGIN, ++seqNo); r.putText(("/mod/" + name).c_str());
            if (ask(server, r, b) != LE_OK) fetched = false;
        }
        CHECK(seen && fetched, "a model file with a name of 76 characters is listed under its whole name, and can be fetched under it");
        q.clear(LK_LIST, ++seqNo); q.put32(0); q.putText("/nosuch");
        CHECK(ask(server, q, a) == LE_NO_FILE, "a folder that is not there: \"no such file\", not an empty list");
        vol = 0;
    }

    printf("\n%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
