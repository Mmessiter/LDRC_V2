// *************************************** LinkMode.h *****************************************
//
// TRANSMITTER VERSION 1B ONLY. The screen is an ESP32 with WiFi, and this file lets it
//   - read and write files on this Teensy's SD card (help texts, backups of the models), and
//   - replace this Teensy's firmware,
// over the wire that carries the display protocol, so the case need never be opened for USB.
// The protocol is LdrcLink (lib/LdrcLink, shared with the screen's firmware and tested on the Mac).
//
// HOW FIRMWARE IS REPLACED, AND WHY IT IS SAFE TO TRY
//   1. The new firmware arrives as an ordinary file on the SD card, checked by CRC-32.
//   2. The firmware now running is copied to /FW/PREVIOUS.BIN.
//   3. The new image is written to the UPPER HALF of the flash (0x60400000) and read back.
//      Up to here nothing is lost if power fails or anything goes wrong.
//   4. With every interrupt off, a routine in RAM copies it over the program and restarts. This takes
//      about two seconds and is the only moment at which a power cut means "connect USB".
//   5. The new firmware is ON TRIAL: if it restarts three times without staying up for 30 seconds
//      (a crash, the watchdog), the start-up code puts PREVIOUS.BIN back by itself.
//
// NEVER while a model is connected, or was a minute ago, or with the motor enabled or the safety off: the link is
// refused (LinkRefusal() in FlightGuard.h), and the radio is idle throughout.
//
// THE PILOT'S FILES. While the link is open this firmware holds NONE of them open (models.dat is closed on the way
// in: a file replaced under an open handle is written through that handle later, into clusters that now belong to
// other files - found by review, 29-9-2026, on the real SdFat). What is in memory is saved first, as at power-off,
// so that a copy taken through the link is the settings as they are now. And if one of the pilot's files has been
// REPLACED or REMOVED through the link (a restore), the transmitter saves nothing more and restarts when the link
// closes: what it holds in memory is no longer what its card holds, and the card is what was asked for.

#ifndef LINKMODE_H
#define LINKMODE_H

#include <Arduino.h>
#include <SD.h>
#include "1Definitions.h"
#include "LdrcLink.h"
#include "LinkServer.h"

extern "C" {
    void eepromemu_flash_write(void *addr, const void *data, uint32_t len);   // cores/teensy4/eeprom.c (they live in RAM)
    void eepromemu_flash_erase_sector(void *addr);
    extern unsigned long _flashimagelen;                                       // the linker's: how long the running image is
}

#define FW_TARGET "fw_teensy41"
#define FW_FLASH_BASE 0x60000000u
#define FW_STAGE_ADDR 0x60400000u // the upper half of the 8 MB: the new image waits here
#define FW_STAGE_MAX 0x003C0000u  // ... up to 0x607C0000, where the core keeps its EEPROM emulation
#define FW_PREVIOUS "/FW/PREVIOUS.BIN"
#define FW_STATE "/FW/STATE.TXT"
#define FW_TRIAL_BOOTS 3      // starts allowed before the firmware on trial is given up
#define FW_CONFIRM_MS 30000   // up this long = accepted
#define FW_MIN_VOLTS 7.0f     // 2S: 3.5 V per cell

bool LinkChangedUserData = false;   // see above: SaveTransmitterParameters() and SaveOneModel() do nothing while this is set
char FwStateName[16] = "confirmed"; // what LK_HELLO reports: confirmed | trial | rolledback
bool FwTrialRunning = false;
int FwTrialStarts = 0;         // how many times the firmware on trial has started (1 = it has never fallen over)
uint32_t FwTrialUpMs = 0;      // how long it has run AS A TRANSMITTER (time spent serving files proves nothing)
uint8_t LinkRxMemory[4096]; // extra room for Serial1's receive buffer

/*********************************************************************************************************************************/
// The version as one piece of text IN the image ("2.5.6 P 26/09/26"): dev/make_fw_package.py looks for it there,
// so a package can never claim a version its firmware will not report.
#define LDRC_TEXT2(x) #x
#define LDRC_TEXT(x) LDRC_TEXT2(x)
#define LDRC_FW_VERSION LDRC_TEXT(TXVERSION_MAJOR) "." LDRC_TEXT(TXVERSION_MINOR) "." LDRC_TEXT(TXVERSION_MINIMUS) " " TXVERSION_EXTRA
const char *LinkFirmwareVersion()
{
    return LDRC_FW_VERSION;
}
/*********************************************************************************************************************************/
uint32_t FwRunningSize() // rounded up to whole words
{
    return (((uint32_t)&_flashimagelen) + 3u) & ~3u;
}

/*********************************************************************************************************************************/
// The SD card, as LdrcLink wants to see it

class TeensyCard : public ldrc::LinkFs
{
public:
    TeensyCard()
    {
        for (int i = 0; i < SLOTS; ++i)
            used_[i] = false;
    }
    bool present() override { return SD_Card_Exists; }
    bool exists(const char *path) override { return SD.exists(path); }
    bool remove(const char *path) override { return SD.remove(path); }
    bool rename(const char *from, const char *to) override { return SD.rename(from, to); }
    bool mkdir(const char *path) override { return SD.mkdir(path); }
    int open(const char *path, bool forWriting) override
    {
        for (int i = 0; i < SLOTS; ++i)
        {
            if (used_[i])
                continue;
            if (forWriting)
                SD.remove(path); // FILE_WRITE appends: start from nothing
            file_[i] = SD.open(path, forWriting ? FILE_WRITE : FILE_READ);
            if (!file_[i])
                return -1;
            used_[i] = true;
            return i;
        }
        return -1;
    }
    int read(int h, uint8_t *buf, size_t n) override { return good(h) ? (int)file_[h].read(buf, n) : -1; }
    int write(int h, const uint8_t *buf, size_t n) override { return good(h) ? (int)file_[h].write(buf, n) : -1; }
    bool seek(int h, uint32_t pos) override { return good(h) && file_[h].seek(pos); }
    uint32_t size(int h) override { return good(h) ? (uint32_t)file_[h].size() : 0; }
    void close(int h) override
    {
        if (good(h))
        {
            file_[h].close();
            used_[h] = false;
        }
    }
    int entry(const char *dir, uint32_t index, char *name, size_t nameSize, uint32_t &size, bool &isDir) override
    {
        File d = SD.open(dir);
        if (!d)
            return -1; // it cannot be read (the server has seen that it is there)
        if (!d.isDirectory())
        {
            d.close();
            return -1;
        }
        uint32_t i = 0;
        bool found = false;
        for (;;)
        {
            File e = d.openNextFile();
            if (!e)
                break;
            if (i++ == index)
            {
                strlcpy(name, e.name(), nameSize);
                size = (uint32_t)e.size();
                isDir = e.isDirectory();
                found = true;
            }
            e.close();
            if (found)
                break;
            if ((i & 15) == 0)
                KickTheDog();
        }
        d.close();
        return found ? 1 : 0;
    }

private:
    enum
    {
        SLOTS = 3
    };
    bool good(int h) const { return h >= 0 && h < SLOTS && used_[h]; }
    File file_[SLOTS];
    bool used_[SLOTS];
};

/*********************************************************************************************************************************/
// FIRMWARE THAT HAS PROVED ITSELF HERE (B18; Malcolm, 1-10-2026: "testing new firmware is good - but only needed for
// the first installation. After that we can KNOW it's ok and not test that one again.")
// /FW/PROVEN.TXT lists the firmware that has run its 30-second trial on THIS transmitter and been accepted, one line
// each: the CRC-32 of its package image, then its version. Known by the CRC, not the name: a rebuilt firmware that kept
// the old name is a different program, and is tried like any other. Installing one that is on the list writes
// "confirmed" at once instead of "trial" (whatever its age: an older firmware reads "confirmed" and starts no trial),
// and the screen sees "confirmed" straight after the restart and does not wait. How it reads the model's settings is
// still compared after every install. /FW/STAGED.TXT says which package is being installed, so that the firmware on
// trial can put itself on the list when it is accepted.
#define FW_PROVEN "/FW/PROVEN.TXT"
#define FW_STAGED "/FW/STAGED.TXT"
#define FW_PROVEN_KEEP 16

bool FwIsProven(uint32_t crc)
{
    File f = SD.open(FW_PROVEN, FILE_READ);
    if (!f)
        return false;
    char line[80];
    int n = 0;
    bool found = false;
    while (!found && f.available())
    {
        const int c = f.read();
        if (c == '\n' || c < 0 || n >= (int)sizeof(line) - 1)
        {
            line[n] = 0;
            if (n >= 8 && strtoul(line, nullptr, 16) == crc)
                found = true;
            n = 0;
            continue;
        }
        line[n++] = (char)c;
    }
    if (!found && n >= 8)
    {
        line[n] = 0;
        found = strtoul(line, nullptr, 16) == crc;
    }
    f.close();
    return found;
}

void FwWriteStaged(uint32_t crc, const char *version)
{
    if (!SD.exists("/FW"))
        SD.mkdir("/FW");
    SD.remove(FW_STAGED);
    File f = SD.open(FW_STAGED, FILE_WRITE);
    if (!f)
        return;
    char line[64];
    snprintf(line, sizeof line, "%08lX %s\n", (unsigned long)crc, version);
    f.write((const uint8_t *)line, strlen(line));
    f.close();
}

// The firmware on trial has been accepted: if it is the package last staged here, it goes on the list.
void FwRememberProven()
{
    File f = SD.open(FW_STAGED, FILE_READ);
    if (!f)
        return;
    char staged[64];
    const int n = f.read(staged, sizeof(staged) - 1);
    f.close();
    if (n < 10)
        return;
    staged[n] = 0;
    char *end = strpbrk(staged, "\r\n");
    if (end)
        *end = 0;
    if (strcmp(staged + 9, LinkFirmwareVersion()) != 0)
        return; // (not this firmware: it came some other way, by USB)
    const uint32_t crc = strtoul(staged, nullptr, 16);
    if (FwIsProven(crc))
        return;
    // keep the last FW_PROVEN_KEEP lines, then add this one
    static char keep[FW_PROVEN_KEEP][64];
    int count = 0;
    File old = SD.open(FW_PROVEN, FILE_READ);
    if (old)
    {
        char line[64];
        int k = 0;
        while (old.available())
        {
            const int c = old.read();
            if (c == '\n' || k >= (int)sizeof(line) - 1)
            {
                line[k] = 0;
                if (k >= 10)
                {
                    if (count == FW_PROVEN_KEEP - 1)
                    { // full: the oldest goes
                        for (int i = 1; i < count; ++i)
                            strcpy(keep[i - 1], keep[i]);
                        --count;
                    }
                    strlcpy(keep[count++], line, sizeof(keep[0]));
                }
                k = 0;
                continue;
            }
            line[k++] = (char)c;
        }
        old.close();
    }
    SD.remove(FW_PROVEN);
    File out = SD.open(FW_PROVEN, FILE_WRITE);
    if (!out)
        return;
    for (int i = 0; i < count; ++i)
    {
        out.write((const uint8_t *)keep[i], strlen(keep[i]));
        out.write((const uint8_t *)"\n", 1);
    }
    out.write((const uint8_t *)staged, strlen(staged));
    out.write((const uint8_t *)"\n", 1);
    out.close();
}

/*********************************************************************************************************************************/
// The little file that says whether the firmware is on trial:   trial 2 2.5.7 A 30/09/26

void FwWriteState(const char *kind, int tries, const char *version)
{
    if (!SD_Card_Exists)
        return;
    if (!SD.exists("/FW"))
        SD.mkdir("/FW");
    SD.remove(FW_STATE);
    File f = SD.open(FW_STATE, FILE_WRITE);
    if (!f)
        return;
    char line[80]; // (the radio library turns the word printf into Serial.printf: not used here)
    snprintf(line, sizeof(line), "%s %d %s\n", kind, tries, version);
    f.write((const uint8_t *)line, strlen(line));
    f.close();
    strlcpy(FwStateName, kind, sizeof(FwStateName));
}
bool FwReadState(char *kind, size_t kindSize, int &tries, char *version, size_t versionSize)
{
    File f = SD.open(FW_STATE, FILE_READ);
    if (!f)
        return false;
    char line[80];
    int n = f.read(line, sizeof(line) - 1);
    f.close();
    if (n <= 0)
        return false;
    line[n] = 0;
    char *end = strpbrk(line, "\r\n");
    if (end)
        *end = 0;
    char *sp1 = strchr(line, ' ');
    if (!sp1)
        return false;
    *sp1 = 0;
    char *sp2 = strchr(sp1 + 1, ' ');
    if (!sp2)
        return false;
    *sp2 = 0;
    strlcpy(kind, line, kindSize);
    tries = atoi(sp1 + 1);
    strlcpy(version, sp2 + 1, versionSize);
    return true;
}

/*********************************************************************************************************************************/
// Flash, step 3: the image in the package at `path` into the upper half, then read back. Nothing is lost if this fails.

uint8_t FwStage(const char *path, const ldrc::FwHeader &h)
{
    static uint8_t page[256];
    File f = SD.open(path, FILE_READ);
    if (!f)
        return ldrc::LE_NO_FILE;
    if (!f.seek(ldrc::FW_HEADER_SIZE))
    {
        f.close();
        return ldrc::LE_IO;
    }
    const uint32_t sectors = (h.size + 4095u) / 4096u;
    for (uint32_t s = 0; s < sectors; ++s)
    {
        const uint32_t addr = FW_STAGE_ADDR + s * 4096u;
        bool erased = true;
        for (uint32_t i = 0; i < 4096u; i += 4)
            if (*(const uint32_t *)(addr + i) != 0xFFFFFFFFu)
            {
                erased = false;
                break;
            }
        if (!erased)
            eepromemu_flash_erase_sector((void *)addr); // (interrupts are off for the ~40 ms this takes: KickTheDog runs on real time)
        KickTheDog();
    }
    for (uint32_t off = 0; off < h.size; off += 256u)
    {
        const uint32_t n = (h.size - off) > 256u ? 256u : (h.size - off);
        memset(page, 0xFF, sizeof(page));
        if (f.read(page, n) != (int)n)
        {
            f.close();
            return ldrc::LE_IO;
        }
        eepromemu_flash_write((void *)(FW_STAGE_ADDR + off), page, (n + 3u) & ~3u);
        if ((off & 0x3FFFu) == 0)
            KickTheDog();
    }
    f.close();
    KickTheDog();
    if (ldrc::crc32((const uint8_t *)FW_STAGE_ADDR, h.size) != h.crc)
        return ldrc::LE_CRC; // what the FLASH holds is not what the file held
    return ldrc::LE_OK;
}

/*********************************************************************************************************************************/
// Flash, step 2: the firmware now running, kept on the card as a package like any other.

uint8_t FwKeepRunning()
{
    static uint8_t chunk[2048];
    const uint32_t size = FwRunningSize();
    if (!SD.exists("/FW"))
        SD.mkdir("/FW");
    SD.remove("/FW/PREVIOUS.TMP");
    File f = SD.open("/FW/PREVIOUS.TMP", FILE_WRITE);
    if (!f)
        return ldrc::LE_IO;
    ldrc::FwHeader h;
    memset(&h, 0, sizeof(h));
    h.size = size;
    h.crc = ldrc::crc32((const uint8_t *)FW_FLASH_BASE, size);
    strlcpy(h.version, LinkFirmwareVersion(), sizeof(h.version));
    strlcpy(h.target, FW_TARGET, sizeof(h.target));
    uint8_t raw[ldrc::FW_HEADER_SIZE];
    ldrc::fwHeaderBuild(h, raw);
    bool ok = f.write(raw, sizeof(raw)) == sizeof(raw);
    for (uint32_t off = 0; ok && off < size; off += sizeof(chunk))
    {
        const uint32_t n = (size - off) > sizeof(chunk) ? sizeof(chunk) : (size - off);
        memcpy(chunk, (const void *)(FW_FLASH_BASE + off), n); // the card's driver wants its data in RAM
        ok = f.write(chunk, n) == n;
        KickTheDog();
    }
    f.close();
    if (!ok)
    {
        SD.remove("/FW/PREVIOUS.TMP");
        return ldrc::LE_IO;
    }
    SD.remove(FW_PREVIOUS);
    if (!SD.rename("/FW/PREVIOUS.TMP", FW_PREVIOUS))
        return ldrc::LE_IO;
    return ldrc::LE_OK;
}

/*********************************************************************************************************************************/
// Flash, step 4: the point of no return. Runs from RAM, calls only RAM, and no interrupt can run.
// newSize bytes from the upper half go over the program; whatever is left of a longer old program is erased.

FASTRUN __attribute__((noinline)) void FwSwapAndRestart(uint32_t newSize, uint32_t oldSize, bool dogRunning)
{
    static uint8_t page[256];
    __disable_irq();
    NVIC_ICER0 = 0xFFFFFFFFu; // every interrupt source off: the code they would run is about to be replaced
    NVIC_ICER1 = 0xFFFFFFFFu;
    NVIC_ICER2 = 0xFFFFFFFFu;
    NVIC_ICER3 = 0xFFFFFFFFu;
    NVIC_ICER4 = 0xFFFFFFFFu;
    SYST_CSR = 0; // and the millisecond tick
    const uint32_t span = (((newSize > oldSize) ? newSize : oldSize) + 4095u) & ~4095u;
    const uint32_t feedEvery = (F_CPU_ACTUAL / 10u) * 6u; // 0.6 s: inside the watchdog's window (0.25 s .. 2.5 s)
    uint32_t lastFeed = LastDogKickCycles;
    for (uint32_t off = 0; off < span; off += 4096u)
    {
        eepromemu_flash_erase_sector((void *)(FW_FLASH_BASE + off));
        for (uint32_t p = 0; p < 4096u && (off + p) < newSize; p += 256u)
        {
            const uint8_t *src = (const uint8_t *)(FW_STAGE_ADDR + off + p);
            for (uint32_t i = 0; i < 256u; ++i)
                page[i] = src[i];
            eepromemu_flash_write((void *)(FW_FLASH_BASE + off + p), page, 256u);
        }
        if (dogRunning && (uint32_t)(ARM_DWT_CYCCNT - lastFeed) > feedEvery)
        {
            if (WDOG3_CS & WDOG_CS_CMD32EN)
                WDOG3_CNT = 0xB480A602u;
            else
            {
                WDOG3_CNT = 0xA602;
                WDOG3_CNT = 0xB480;
            }
            lastFeed = ARM_DWT_CYCCNT;
        }
    }
    SCB_AIRCR = 0x05FA0004u; // restart
    for (;;)
    {
    }
}

/*********************************************************************************************************************************/
// The chip, as LdrcLink wants to see it

class TeensyChip : public ldrc::LinkPlatform
{
public:
    explicit TeensyChip(TeensyCard &card) : card_(card), stagedSize(0) {}
    const char *firmwareVersion() override { return LinkFirmwareVersion(); }
    const char *target() override { return FW_TARGET; }
    const char *updateState() override { return FwStateName; }
    uint32_t uptimeSeconds() override { return millis() / 1000u; }
    int startsOnTrial() override { return FwTrialStarts; }
    void busy() override { KickTheDog(); }
    const char *extra() override { return LinkHelloExtra(); } // how the settings are read, and what the transmitter is doing
    void confirmFirmware() override
    {
        const bool wasOnTrial = FwTrialRunning;
        FwTrialRunning = false;
        FwWriteState("confirmed", 0, LinkFirmwareVersion());
        if (wasOnTrial)
            FwRememberProven();
    }
    uint8_t stageFirmware(const char *path) override { return stage(path, true); }
    uint8_t stagePrevious() override
    {
        if (!SD.exists(FW_PREVIOUS))
            return ldrc::LE_NO_PREVIOUS;
        return stage(FW_PREVIOUS, false);
    }
    uint32_t stagedSize;

private:
    uint8_t stage(const char *path, bool keepRunning)
    {
        if (TXVoltsTotal > 0.1f && TXVoltsTotal < FW_MIN_VOLTS)
            return ldrc::LE_BATTERY;
        ldrc::FwHeader h;
        uint8_t e = ldrc::checkFirmwarePackage(card_, *this, path, FW_TARGET, FW_STAGE_MAX, h);
        if (e != ldrc::LE_OK)
            return e;
        if (keepRunning)
        {
            e = FwKeepRunning(); // no way back, no update
            if (e != ldrc::LE_OK)
                return e;
        }
        e = FwStage(path, h);
        if (e != ldrc::LE_OK)
            return e;
        // B18: firmware that has passed its trial here before starts "confirmed": no trial, no wait.
        const bool proven = keepRunning && FwIsProven(h.crc);
        FwWriteState(keepRunning ? (proven ? "confirmed" : "trial") : "rolledback", 0, h.version);
        if (keepRunning)
            FwWriteStaged(h.crc, h.version);
        NoteWhyOff(OFF_FIRMWARE_SWAP);
        stagedSize = h.size;
        return ldrc::LE_OK;
    }
    TeensyCard &card_;
};

/*********************************************************************************************************************************/
void LinkSend(const ldrc::Frame &f)
{
    static uint8_t raw[ldrc::LINK_MAX_FRAME];
    NEXTION.write(raw, ldrc::encode(f, raw));
    NEXTION.flush();
}

/*********************************************************************************************************************************/
// The screen has knocked. Until it says goodbye (or falls silent for 30 s) this Teensy is a file server, not a transmitter.

void LinkMode()
{
    CRUMB(CRUMB_LINK);
    static TeensyCard card;
    static TeensyChip chip(card);
    static ldrc::Frame reply;
    ldrc::LinkServer server(card, chip);
    const uint8_t refusal = LinkRefusal();
    if (refusal != ldrc::LE_OK)
    { // A model is connected or was a moment ago (flying comes first), the motor is enabled, the safety is off, a
      // question is on screen, or the radio is calibrating / scanning: the link stays shut. We say who we are all
      // the same - one frame, and we remain a transmitter.
        server.hello(reply, 0);
        reply.payload[0] = refusal;
        LinkSend(reply);
        return;
    }
    BlueLedOn(); // busy, and not even trying to connect (Malcolm, 4-10-2026: red = trying to connect, green = connected,
                 // blue = busy and not trying). The main loop puts red back once the link has closed (transceiver.h).
    ldrc::LinkSession session(server);
    session.begin(millis(), reply); // (who we are, and how the settings are read: taken BEFORE anything below)
    LinkSend(reply);
    // As at power-off: what is in memory goes to the card, so that the copy the screen may take is the settings as
    // they are now, and so that new firmware reads exactly what this firmware held. Then every file of the pilot's
    // is closed, and stays closed for as long as the link is open.
    // (Not if the models file could not be read, or did not agree with its checksum: what is in memory then is not
    //  what the pilot set, and must not go over what his card holds.)
    if (!LinkChangedUserData && ErrorState == NOERROR && !FileError && strcmp(ModelName, "Not in use") != 0 && strcmp(ModelName, "File error?") != 0)
        SaveAllParameters();
    PerfWriteReport(false); // B15: where the time went while a model was connected (/PERF.TXT; Perf.h)
    CloseModelsFile();
    CloseLogFile();
    bool leave = false;
    while (!leave && !session.expired(millis()))
    {
        KickTheDog();
        CheckPowerOffButton(); // (its "Saving <model>" saves nothing once a file of the pilot's has been replaced)
        while (NEXTION.available() && !leave)
        {
            ldrc::LinkAction action;
            if (!session.byte((uint8_t)NEXTION.read(), millis(), reply, action))
                continue;
            if (server.userDataChanged())
                LinkChangedUserData = true; // before the answer goes out: from now on nothing is saved
            LinkSend(reply);
            session.touch(millis()); // (a long job must not count as silence)
            if (action == ldrc::LA_LEAVE)
                leave = true;
            if (action == ldrc::LA_SWAP_AND_RESTART)
            {
                delay(100); // the answer is on its way out of the wire
                FwSwapAndRestart(chip.stagedSize, FwRunningSize(), true);
            }
        }
    }
    server.abandon();
    ClearText();
    if (LinkChangedUserData)
    { // The card holds what was asked for; memory holds what was there before. Start again, from the card.
        NoteWhyOff(OFF_RESTORE_RESTART);
        NEXTION.flush();
        delay(100);
        SCB_AIRCR = 0x05FA0004u;
        for (;;)
        {
        }
    }
    // The pilot was here all the while (he asked for this), however long the files took: the screen saver
    // and the inactivity power-off begin to count again from now. Without this, a transmitter that had
    // served files for longer than the power-off time would switch itself off the moment it had finished.
    StartInactvityTimeout();
    ScreenTimeTimer = millis();
    CurrentView = 254; // whatever the screen shows now, the front page is drawn afresh
    GotoFrontView();
}

/*********************************************************************************************************************************/
// A frame that arrives while this Teensy is a transmitter (the screen lost track): swallow it whole, so that not
// one byte of it is taken for a touch, and say so. Called with A5 already read and 5A waiting.

void LinkStrayFrame()
{
    static ldrc::Parser parser;
    static ldrc::Frame frame, reply;
    parser.reset();
    parser.push(ldrc::LINK_SOF0, frame, millis());
    uint32_t quietSince = millis();
    const uint32_t begun = millis();
    while (millis() - quietSince < ldrc::LINK_GAP_MS && millis() - begun < 500)
    {
        if (!NEXTION.available())
            continue;
        quietSince = millis();
        if (parser.push((uint8_t)NEXTION.read(), frame, millis()))
        {
            reply.clear((uint8_t)(ldrc::LK_REPLY | frame.type), frame.seq);
            reply.put8(ldrc::LE_SEQUENCE); // "I am not in the link"
            LinkSend(reply);
            return;
        }
    }
}

/*********************************************************************************************************************************/
// At start-up, straight after the SD card is found and BEFORE the watchdog runs.

void FwTrialAtBoot()
{
    strcpy(FwStateName, "confirmed");
    FwTrialRunning = false;
    if (!SD_Card_Exists)
        return;
    char kind[16], version[32];
    int tries = 0;
    if (!FwReadState(kind, sizeof(kind), tries, version, sizeof(version)))
        return;
    if (strcmp(kind, "rolledback") == 0)
    {
        strcpy(FwStateName, "rolledback");
        return;
    }
    if (strcmp(kind, "trial") != 0)
        return;
    if (strcmp(version, LinkFirmwareVersion()) != 0)
    { // the firmware on trial is not the one running (the swap never happened, or USB has been used since)
        FwWriteState("confirmed", 0, LinkFirmwareVersion());
        return;
    }
    tries++;
    if (tries > FW_TRIAL_BOOTS)
    { // it has not stayed up: the previous firmware comes back
        static TeensyCard card;
        static TeensyChip chip(card);
        ldrc::FwHeader h;
        if (SD.exists(FW_PREVIOUS) && ldrc::checkFirmwarePackage(card, chip, FW_PREVIOUS, FW_TARGET, FW_STAGE_MAX, h) == ldrc::LE_OK && FwStage(FW_PREVIOUS, h) == ldrc::LE_OK)
        {
            FwWriteState("rolledback", 0, h.version);
            FwSwapAndRestart(h.size, FwRunningSize(), false);
        }
        FwWriteState("confirmed", 0, LinkFirmwareVersion()); // nothing to go back to: carry on
        return;
    }
    FwWriteState("trial", tries, version);
    FwTrialRunning = true;
    FwTrialStarts = tries;
}

/*********************************************************************************************************************************/
// In the main loop: 30 seconds of running AS A TRANSMITTER = accepted. (Only the main loop counts: a firmware
// that answers the screen but whose radio loop falls over is not accepted because it answered.)

FASTRUN void FwTrialTick()
{
    static uint32_t last = 0;
    if (!FwTrialRunning)
        return;
    const uint32_t now = millis();
    if (last && (now - last) < 250)
        FwTrialUpMs += now - last; // (a long gap is time spent elsewhere - serving files - and is not counted)
    last = now;
    if (FwTrialUpMs > FW_CONFIRM_MS)
    {
        FwTrialRunning = false;
        FwWriteState("confirmed", 0, LinkFirmwareVersion());
        FwRememberProven(); // B18: it has proved itself here; installed again, it needs no trial
    }
}

#endif // LINKMODE_H
