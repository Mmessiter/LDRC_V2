// B70: Rotorflight backup and restore of EVERYTHING, over the Bluetooth pipe, to a file on the transmitter's card - and
// the same file as the flight controller's stand-in when no model is connected (Malcolm, 8 Oct 2026: "convert it to BLE
// and expand it to cover all the settings ... when the transmitter has that model selected but has not connected, if a
// backup has been made, accessing those pages should read the data in the backup file and even be capable of writing to
// it ... on a subsequent connection the user should be informed if the backup contains edits and offered the option to
// restore"). Modelled on the phone app's backup (RXV2App SessionCache.swift), whose restore map is proven byte for byte.
//
// THE FILE: /rfbak/<model>.rfb, text lines:
//   rfb=1  model=<name>  date=<when>  banks=<pid count>/<rates count>  edits=<keys edited without the model, comma-separated>
//   <key>=<hex>  where key is the Rotorflight function: "42"; "112.0" the function and the bank (0-5); "174.01" the function
//   and the index byte it was asked with (mixer inputs, RPM notches).
// BACK UP: the app's sweep. Every bank (selected with 210): 112 PIDs, 94 advanced PIDs, 148 governor profile, 146 rescue;
// every rates bank (210 with 0x80|r): 111; then the bankless list. The transmitter's own banks are put back at the end.
// RESTORE: the app's map - one servo, one mixer rule, one meter, one mode slot, one failsafe value per write; 222 built from
// 131 without its motor count; 81 from 80 without its first byte; each item read first and skipped when already the same,
// written and read back otherwise; the FC's own banks put back; 250 once something was written; 68 when the governor
// global or the motor block changed. WRITE EDITS: the same, for the keys the file says were edited without the model.
// OFFLINE: MspAsk (PipeHttp.h) hands a request to BakOfflineAnswer when no model is connected and this model's file is
// loaded: a read is answered from the file, a write (the pages' own: 93, 37, 147, 212, 43, 171, and the plain pairs) goes
// into the file and marks its key edited; 210 picks the bank the per-bank keys use; 250 and 68 are nods.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_BACKUP_H
#define RF_BACKUP_H

static const int BAK_MAX = 12000;
DMAMEM static char Bak[BAK_MAX];              // the file's text, while a model is selected (RAM2)
static bool BakLoaded = false;                // Bak holds the file of BakModel
static char BakModel[32] = "";
static bool BakDirty = false;
static uint8_t BakSelPid = 0, BakSelRate = 0; // what 210 chose, offline
static const char *BAK_DIR = "/rfbak";

// ---------------------------------------------------------------- the text store
static void BakPath(char *out, size_t n, const char *model)
{
    char safe[24];
    int j = 0;
    for (int i = 0; model[i] && j < 20; ++i)
    {
        const char c = model[i];
        safe[j++] = (isalnum((unsigned char)c) || c == '-' || c == '_') ? c : '_';
    }
    safe[j] = 0;
    snprintf(out, n, "%s/%s.rfb", BAK_DIR, safe);
}
static bool BakFileExists(const char *model)
{
    char p[48];
    BakPath(p, sizeof(p), model);
    return SD.exists(p);
}
// The line "key=" in Bak: a pointer to its value, or nullptr
static char *BakFind(const char *key)
{
    const size_t kl = strlen(key);
    char *p = Bak;
    while (*p)
    {
        if (strncmp(p, key, kl) == 0 && p[kl] == '=')
            return p + kl + 1;
        p = strchr(p, '\n');
        if (!p)
            break;
        ++p;
    }
    return nullptr;
}
static int BakGet(const char *key, char *out, size_t n) // the value (hex) of a key; its length, or -1
{
    const char *v = BakFind(key);
    if (!v)
        return -1;
    size_t i = 0;
    while (v[i] && v[i] != '\n' && v[i] != '\r' && i < n - 1)
    {
        out[i] = v[i];
        ++i;
    }
    out[i] = 0;
    return (int)i;
}
static bool BakSet(const char *key, const char *value) // replace the line, or append it
{
    char *v = BakFind(key);
    const size_t len = strlen(Bak), vl = strlen(value);
    if (v)
    {
        char *e = strchr(v, '\n');
        const size_t old = e ? (size_t)(e - v) : strlen(v);
        if (len - old + vl >= BAK_MAX - 1)
            return false;
        memmove(v + vl, v + old, len - (size_t)(v - Bak) - old + 1);
        memcpy(v, value, vl);
    }
    else
    {
        if (len + strlen(key) + vl + 3 >= BAK_MAX - 1)
            return false;
        snprintf(Bak + len, BAK_MAX - len, "%s=%s\n", key, value);
    }
    BakDirty = true;
    return true;
}
static bool BakLoad(const char *model)
{
    BakLoaded = false;
    Bak[0] = 0;
    strncpy(BakModel, model, sizeof(BakModel) - 1);
    char p[48];
    BakPath(p, sizeof(p), model);
    File f = SD.open(p, FILE_READ);
    if (!f)
        return false;
    const size_t n = f.read(Bak, BAK_MAX - 1);
    f.close();
    Bak[n] = 0;
    BakLoaded = strncmp(Bak, "rfb=", 4) == 0;
    BakDirty = false;
    return BakLoaded;
}
static bool BakSave()
{
    if (!SD.exists(BAK_DIR))
        SD.mkdir(BAK_DIR);
    char p[48];
    BakPath(p, sizeof(p), BakModel);
    SD.remove(p);
    File f = SD.open(p, FILE_WRITE);
    if (!f)
        return false;
    f.write(Bak, strlen(Bak));
    f.close();
    BakDirty = false;
    return true;
}
void BakForModel() // the file of the model in use, when it changes (ChangeModel): loaded, or none
{
    if (strcmp(BakModel, ModelName) == 0 && BakLoaded)
        return;
    BakLoad(ModelName);
}
bool BakHaveFile() { BakForModel(); return BakLoaded; }
// Edits made without the model: the "edits=" line, keys comma-separated
static bool BakEdited(const char *key)
{
    char e[400];
    if (BakGet("edits", e, sizeof(e)) <= 0)
        return false;
    const size_t kl = strlen(key);
    for (const char *p = e; *p;)
    {
        if (strncmp(p, key, kl) == 0 && (p[kl] == ',' || p[kl] == 0))
            return true;
        p = strchr(p, ',');
        if (!p)
            break;
        ++p;
    }
    return false;
}
static void BakMarkEdit(const char *key)
{
    if (BakEdited(key))
        return;
    char e[400] = "";
    BakGet("edits", e, sizeof(e));
    if (e[0])
        strncat(e, ",", sizeof(e) - strlen(e) - 1);
    strncat(e, key, sizeof(e) - strlen(e) - 1);
    BakSet("edits", e);
}
bool BakEditsWaiting()
{
    char e[8];
    return BakHaveFile() && BakGet("edits", e, sizeof(e)) > 0;
}
static void BakClearEdits() { BakSet("edits", ""); }
bool BakOffline() { return !(BoundFlag && ModelMatched) && BakHaveFile(); }

// ---------------------------------------------------------------- hex helpers
static int Hex2(const char *h) { char t[3] = {h[0], h[1], 0}; return (int)strtol(t, nullptr, 16); }   // one byte of hex
static int HexToBytes(const char *h, uint8_t *out, int max)
{
    int n = 0;
    while (h[0] && h[1] && n < max)
    {
        char t[3] = {h[0], h[1], 0};
        char *e = nullptr;
        const long v = strtol(t, &e, 16);
        if (e != t + 2)
            break;
        out[n++] = (uint8_t)v;
        h += 2;
    }
    return n;
}
static void BytesToHex(const uint8_t *b, int n, char *out, size_t max)
{
    size_t j = 0;
    for (int i = 0; i < n && j + 2 < max; ++i)
        j += snprintf(out + j, max - j, "%02X", b[i]);
    out[j] = 0;
}
static void BakKey(char *out, size_t n, uint8_t fn, int bank, int idx) // "112.0", "174.01", "42"
{
    if (bank >= 0)
        snprintf(out, n, "%u.%d", (unsigned)fn, bank);
    else if (idx >= 0)
        snprintf(out, n, "%u.%02X", (unsigned)fn, idx);
    else
        snprintf(out, n, "%u", (unsigned)fn);
}

// ---------------------------------------------------------------- the flight controller's stand-in (offline)
static const uint8_t BAK_PER_BANK[] = {112, 94, 148, 146};    // read with the PID bank selected
static bool BakPerBank(uint8_t fn) { for (uint8_t f : BAK_PER_BANK) if (f == fn) return true; return false; }
static bool BakIndexed(uint8_t fn) { return fn == 174 || fn == 154; }
// A write's function -> the read key it changes (the plain pairs; nothing to patch)
static uint8_t BakReadOfWrite(uint8_t w)
{
    static const uint8_t pairs[][2] = {{93, 92}, {37, 36}, {147, 146}, {149, 148}, {202, 112}, {95, 94}, {204, 111}, {143, 142}, {43, 42}, {11, 10}, {39, 38}, {62, 61}, {239, 240}, {97, 96}, {220, 126}, {65, 64}, {45, 44}, {67, 66}, {76, 75}, {51, 50}, {74, 73}, {33, 32}, {216, 123}, {155, 154}, {171, 174}};
    for (auto &p : pairs)
        if (p[0] == w)
            return p[1];
    return 0;
}
static void BakReply(int code, const char *body)
{
    PipeRepCode = code;
    strncpy(PipeRepBody, body, sizeof(PipeRepBody) - 1);
    PipeRepBody[sizeof(PipeRepBody) - 1] = 0;
}
bool BakOfflineAnswer(uint8_t fn, const uint8_t *data, int len) // true: answered (PipeRep* set)
{
    char key[16], hex[700];
    if (fn == 210 && len >= 1)
    {
        if (data[0] & 0x80) BakSelRate = data[0] & 0x7F; else BakSelPid = data[0] & 0x7F;
        BakReply(200, "");
        return true;
    }
    if (fn == 250 || fn == 68)
    {
        if (fn == 250 && BakDirty) BakSave();
        BakReply(200, "");
        return true;
    }
    if (fn == 101)
    { // status: the banks chosen, for a page that asks (bytes 23 and 25 as Rotorflight 4.6 has them)
        uint8_t b[32] = {0};
        b[23] = BakSelPid; b[25] = BakSelRate;
        BytesToHex(b, 32, hex, sizeof(hex));
        BakReply(200, hex);
        return true;
    }
    const uint8_t rfn = BakReadOfWrite(fn);
    if (rfn && len > 0)
    { // a write: into the file
        const bool perBank = BakPerBank(rfn) || rfn == 111;
        const int bank = rfn == 111 ? BakSelRate : perBank ? BakSelPid : -1;
        int idx = -1;
        const uint8_t *val = data;
        int vlen = len;
        if (BakIndexed(rfn)) { idx = data[0]; val = data + 1; vlen = len - 1; }   // 171 and 155: the index first
        BakKey(key, sizeof(key), rfn, bank, idx);
        BytesToHex(val, vlen, hex, sizeof(hex));
        if (!BakSet(key, hex)) { BakReply(507, "the backup file is full"); return true; }
        BakMarkEdit(key);
        BakReply(200, "");
        return true;
    }
    if (fn == 212 && len >= 17)
    { // a servo: patched into the 120 image (count, then 16 bytes a servo)
        char img[700];
        if (BakGet("120", img, sizeof(img)) < 2) { BakReply(404, "no servos in the backup"); return true; }
        const int i = data[0];
        if ((int)strlen(img) < 2 + (i + 1) * 32) { BakReply(404, "no such servo in the backup"); return true; }
        BytesToHex(data + 1, 16, hex, sizeof(hex));
        memcpy(img + 2 + i * 32, hex, 32);
        BakSet("120", img); BakMarkEdit("120");
        BakReply(200, "");
        return true;
    }
    if (len == 0)
    { // a read
        BakKey(key, sizeof(key), fn, BakPerBank(fn) ? BakSelPid : fn == 111 ? BakSelRate : -1, -1);
        if (BakGet(key, hex, sizeof(hex)) < 0) { BakReply(404, "not in the backup"); return true; }
        BakReply(200, hex);
        return true;
    }
    if (BakIndexed(fn) && len == 1)
    { // a read with its index
        BakKey(key, sizeof(key), fn, -1, data[0]);
        if (BakGet(key, hex, sizeof(hex)) < 0) { BakReply(404, "not in the backup"); return true; }
        BakReply(200, hex);
        return true;
    }
    BakReply(405, "not editable without the model");
    return true;
}

// ---------------------------------------------------------------- the jobs: back up, restore, write the edits
enum { BAK_JOB_NONE = 0, BAK_JOB_BACKUP, BAK_JOB_RESTORE, BAK_JOB_EDITS };
static int BakJob = BAK_JOB_NONE, BakStep = 0, BakReq = 0, BakTries = 0, BakIdx = 0, BakSub = 0;
static int BakDone = 0, BakTotal = 0, BakFails = 0, BakWritten = 0, BakUnchanged = 0;
static char BakFailed[160] = "";
static bool BakWroteAny = false, BakWroteGov = false, BakWroteMotor = false, BakItemWrote = false;
static uint8_t BakPidBanks = 6, BakRateBanks = 6, BakOrigPid = 0, BakOrigRate = 0;
static uint32_t BakWaitUntil = 0;
// The bankless reads, in the app's order (optional: an older Rotorflight may refuse it; that is not a failure)
struct BakReadItem { uint8_t fn; int8_t idx; bool optional; };
static const BakReadItem BAK_READS[] = {
    {142, -1, false}, {42, -1, false}, {174, 1, false}, {174, 2, false}, {174, 3, false}, {174, 4, false}, {120, -1, false}, {172, -1, false},
    {131, -1, false}, {80, -1, false}, {10, -1, false}, {36, -1, false}, {38, -1, false}, {61, -1, false}, {240, -1, false}, {96, -1, false},
    {126, -1, false}, {64, -1, false}, {44, -1, false}, {66, -1, false}, {75, -1, false}, {50, -1, false}, {73, -1, false}, {92, -1, false},
    {32, -1, false}, {123, -1, true}, {154, 0, true}, {154, 1, true}, {154, 2, true}, {56, -1, false}, {40, -1, false}, {34, -1, false},
    {238, -1, false}, {77, -1, false}};
static const int BAK_READS_N = sizeof(BAK_READS) / sizeof(BAK_READS[0]);
// The restore map: what to write for a key, how, and how to check it
enum { BK_WHOLE = 0, BK_INDEXED, BK_SERVOS, BK_RULES, BK_MOTOR, BK_BLACKBOX, BK_METERS, BK_MODES, BK_FAILSAFE, BK_TELEM };
struct BakRestoreItem { const char *label; uint8_t readFn; int8_t bank; int8_t idx; uint8_t writeFn; uint8_t kind; };
static const BakRestoreItem BAK_RESTORE[] = {
    // (the per-bank ones are made in code: 112->202, 94->95, 148->149, 146->147 per PID bank; 111->204 per rates bank)
    {"governor global", 142, -1, -1, 143, BK_WHOLE},
    {"mixer", 42, -1, -1, 43, BK_WHOLE},
    {"mixer input roll", 174, -1, 1, 171, BK_INDEXED}, {"mixer input pitch", 174, -1, 2, 171, BK_INDEXED},
    {"mixer input yaw", 174, -1, 3, 171, BK_INDEXED}, {"mixer input collective", 174, -1, 4, 171, BK_INDEXED},
    {"servos", 120, -1, -1, 212, BK_SERVOS},
    {"mixer rules", 172, -1, -1, 173, BK_RULES},
    {"motor and gear ratio", 131, -1, -1, 222, BK_MOTOR},
    {"blackbox", 80, -1, -1, 81, BK_BLACKBOX},
    {"name", 10, -1, -1, 11, BK_WHOLE}, {"features", 36, -1, -1, 37, BK_WHOLE}, {"board alignment", 38, -1, -1, 39, BK_WHOLE},
    {"arming", 61, -1, -1, 62, BK_WHOLE}, {"level trims", 240, -1, -1, 239, BK_WHOLE}, {"sensors", 96, -1, -1, 97, BK_WHOLE},
    {"gyro alignment", 126, -1, -1, 220, BK_WHOLE}, {"channel map", 64, -1, -1, 65, BK_WHOLE}, {"receiver setup", 44, -1, -1, 45, BK_WHOLE},
    {"stick centre and travel", 66, -1, -1, 67, BK_WHOLE}, {"failsafe", 75, -1, -1, 76, BK_WHOLE}, {"RSSI", 50, -1, -1, 51, BK_WHOLE},
    {"telemetry sensors", 73, -1, -1, 74, BK_TELEM}, {"gyro filters", 92, -1, -1, 93, BK_WHOLE}, {"battery", 32, -1, -1, 33, BK_WHOLE},
    {"ESC telemetry", 123, -1, -1, 216, BK_WHOLE},
    {"RPM notches roll", 154, -1, 0, 155, BK_INDEXED}, {"RPM notches pitch", 154, -1, 1, 155, BK_INDEXED}, {"RPM notches yaw", 154, -1, 2, 155, BK_INDEXED},
    {"voltage meters", 56, -1, -1, 57, BK_METERS}, {"current meters", 40, -1, -1, 41, BK_METERS},
    {"modes", 34, -1, -1, 35, BK_MODES},
    {"failsafe values", 77, -1, -1, 78, BK_FAILSAFE}};
static const int BAK_RESTORE_N = sizeof(BAK_RESTORE) / sizeof(BAK_RESTORE[0]);
static const int BAK_BANKED_N = 5;   // per bank: 112, 94, 148, 146; per rates bank: 111

static void BakBusy(const char *msg)
{
    SendCommand((char *)(msg && *msg ? "vis busy,1" : "vis busy,0"));
    if (msg && *msg)
        SendText((char *)"busy", (char *)msg);
}
static void BakShowPage();
static void BakProgress(const char *what)
{
    char m[90];
    snprintf(m, sizeof(m), "%s %d of %d: %s", BakJob == BAK_JOB_BACKUP ? "Reading" : "Writing", BakDone + 1, BakTotal, what);
    BakBusy(m);
}
static void BakFinish(const char *verdict)
{
    BakJob = BAK_JOB_NONE;
    CurrentMode = NORMAL;
    BlockBankChanges = false;
    BakBusy("");
    BakShowPage();
    PlaySound(BakFails ? WHAHWHAHMSG : BEEPCOMPLETE);
    MsgBox((char *)"page RFBackUpView", (char *)verdict);
    BakShowPage();
}
static void BakStart(int job)
{
    char why[120];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)) || RfNeedsModel(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFBackUpView", why);
        BakShowPage();
        return;
    }
    BakJob = job; BakStep = 0; BakIdx = 0; BakSub = 0; BakTries = 0; BakDone = 0; BakFails = 0; BakWritten = 0; BakUnchanged = 0; BakFailed[0] = 0;
    BakWroteAny = BakWroteGov = BakWroteMotor = false;
    BlockBankChanges = true;
    CurrentMode = job == BAK_JOB_BACKUP ? SAVE_RF_SETTINGS : RESTORE_RF_SETTINGS;
    BakBusy(job == BAK_JOB_BACKUP ? "Reading the flight controller ..." : "Checking the flight controller ...");
    BakReq = MspAsk(101, nullptr, 0);   // the banks it has, and the ones it is on
    BakStep = 1;
}
// ---- the sweep
static int BakSweepTotal() { return BakPidBanks * 4 + BakRateBanks + BAK_READS_N; }
static void BakSweepAsk() // BakIdx: 0.. the item in the sweep; BakSub 0 = select (banked), 1 = read
{
    const int perBank = BakPidBanks * 4;
    if (BakIdx < perBank)
    {
        const int b = BakIdx / 4, f = BAK_PER_BANK[BakIdx % 4];
        if (BakSub == 0) { uint8_t d = (uint8_t)b; BakReq = MspAsk(210, &d, 1); return; }
        char what[40]; snprintf(what, sizeof(what), "bank %d, %s", b + 1, f == 112 ? "PIDs" : f == 94 ? "advanced PIDs" : f == 148 ? "governor" : "rescue");
        BakProgress(what);
        BakReq = MspAsk((uint8_t)f, nullptr, 0);
        return;
    }
    if (BakIdx < perBank + BakRateBanks)
    {
        const int r = BakIdx - perBank;
        if (BakSub == 0) { uint8_t d = (uint8_t)(0x80 | r); BakReq = MspAsk(210, &d, 1); return; }
        char what[40]; snprintf(what, sizeof(what), "rates bank %d", r + 1);
        BakProgress(what);
        BakReq = MspAsk(111, nullptr, 0);
        return;
    }
    const BakReadItem &it = BAK_READS[BakIdx - perBank - BakRateBanks];
    char what[40]; snprintf(what, sizeof(what), "setting %u", (unsigned)it.fn);
    BakProgress(what);
    if (it.idx >= 0) { uint8_t d = (uint8_t)it.idx; BakReq = MspAsk(it.fn, &d, 1); }
    else BakReq = MspAsk(it.fn, nullptr, 0);
}
static void BakSweepTake(bool ok)
{
    const int perBank = BakPidBanks * 4;
    char key[16];
    if (BakIdx < perBank + BakRateBanks && BakSub == 0)
    { // the select: on to the read
        if (!ok) { if (++BakTries < 3) { BakSweepAsk(); return; } BakFinish("The bank could not be selected.\r\nNothing was written to the card."); return; }
        BakSub = 1; BakTries = 0; BakSweepAsk();
        return;
    }
    bool optional = false;
    if (BakIdx < perBank) BakKey(key, sizeof(key), BAK_PER_BANK[BakIdx % 4], BakIdx / 4, -1);
    else if (BakIdx < perBank + BakRateBanks) BakKey(key, sizeof(key), 111, BakIdx - perBank, -1);
    else { const BakReadItem &it = BAK_READS[BakIdx - perBank - BakRateBanks]; BakKey(key, sizeof(key), it.fn, -1, it.idx); optional = it.optional; }
    if (ok) BakSet(key, PipeRepBody);
    else
    {
        const bool transient = PipeRepCode == 0 || PipeRepCode >= 500;   // no answer, or the receiver busy: asked again; a refusal (4xx) is final
        if (transient && ++BakTries < 3) { BakSweepAsk(); return; }
        if (!optional) { ++BakFails; if (strlen(BakFailed) < 120) { strncat(BakFailed, key, sizeof(BakFailed) - strlen(BakFailed) - 1); strncat(BakFailed, " ", sizeof(BakFailed) - strlen(BakFailed) - 1); } }
    }
    ++BakIdx; ++BakDone; BakSub = 0; BakTries = 0;
    if (BakIdx < BakSweepTotal()) { BakSweepAsk(); return; }
    // all read: the transmitter's banks back, the file written
    { uint8_t d = (uint8_t)(Bank - 1); BakReq = MspAsk(210, &d, 1); }
    BakStep = 90;
}
// ---- the restore: the list of things to do, made from the file
struct BakTodo { uint8_t readFn, writeFn, kind; int8_t bank, idx; const char *label; };
static BakTodo BakList[80];
static int BakListN = 0;
static bool BakOnlyEdits() { return BakJob == BAK_JOB_EDITS; }
static void BakBuildList()
{
    BakListN = 0;
    char key[16], v[8];
    auto want = [&](uint8_t rfn, int bank, int idx) {
        BakKey(key, sizeof(key), rfn, bank, idx);
        if (BakGet(key, v, sizeof(v)) < 2) return false;      // not in the file
        return !BakOnlyEdits() || BakEdited(key);
    };
    static const char *bankedNames[4] = {"PIDs", "advanced PIDs", "governor profile", "rescue"};
    static const uint8_t bankedWrite[4] = {202, 95, 149, 147};
    for (int b = 0; b < 6 && BakListN < 80; ++b)
        for (int k = 0; k < 4 && BakListN < 80; ++k)
            if (want(BAK_PER_BANK[k], b, -1)) BakList[BakListN++] = {BAK_PER_BANK[k], bankedWrite[k], BK_WHOLE, (int8_t)b, -1, bankedNames[k]};
    for (int r = 0; r < 6 && BakListN < 80; ++r)
        if (want(111, r, -1)) BakList[BakListN++] = {111, 204, BK_WHOLE, (int8_t)(0x40 | r), -1, "rates"};   // (0x40 marks a rates bank)
    for (int i = 0; i < BAK_RESTORE_N && BakListN < 80; ++i)
    {
        const BakRestoreItem &it = BAK_RESTORE[i];
        if (want(it.readFn, -1, it.idx)) BakList[BakListN++] = {it.readFn, it.writeFn, it.kind, -1, it.idx, it.label};
        if (it.kind == BK_MODES && BakListN < 80 && want(238, -1, -1) && !want(34, -1, -1)) {}   // (238 goes with 34)
    }
}
// The write for a list item and its part (BakSub): the payload hex, the chunk to verify (offset and length in the read
// image, in hex characters; -1 = the whole), and whether there is another part after this one
static bool BakWritePayload(const BakTodo &t, int part, char *out, size_t n, int &verifyOff, int &verifyLen, bool &more)
{
    char key[16], img[700];
    const int bankNo = t.bank < 0 ? -1 : (t.bank & 0x3F);
    BakKey(key, sizeof(key), t.readFn, bankNo, t.idx);
    if (BakGet(key, img, sizeof(img)) < 2) return false;
    const int L = strlen(img);
    verifyOff = -1; verifyLen = -1; more = false;
    switch (t.kind)
    {
    case BK_WHOLE: snprintf(out, n, "%s", img); return true;
    case BK_TELEM: snprintf(out, n, "%s", img); return true;   // (bytes 8-11, the link speed, are the FC's own: not compared)
    case BK_INDEXED: snprintf(out, n, "%02X%s", (unsigned)t.idx, img); return true;
    case BK_BLACKBOX: if (L < 4) return false; snprintf(out, n, "%s", img + 2); return true;
    case BK_MOTOR: if (L < 58) return false; snprintf(out, n, "%.12s%s", img, img + 14); return true;
    case BK_SERVOS:
    { // count, then 16 bytes a servo: part i -> index + its 32 hex
        const int count = Hex2(img);
        if (part >= count || L < 2 + (part + 1) * 32) return false;
        snprintf(out, n, "%02X%.32s", (unsigned)part, img + 2 + part * 32);
        verifyOff = 2 + part * 32; verifyLen = 32; more = part + 1 < count; return true;
    }
    case BK_RULES:
    { // 7 bytes a rule
        const int count = L / 14;
        if (part >= count) return false;
        snprintf(out, n, "%02X%.14s", (unsigned)part, img + part * 14);
        verifyOff = part * 14; verifyLen = 14; more = part + 1 < count; return true;
    }
    case BK_METERS:
    { // count, then frames [len, id, type, values...]: 8 bytes a voltage meter, 7 a current one; the write is id + values
        const int frame = t.readFn == 56 ? 8 : 7;
        const int count = Hex2(img);
        if (part >= count || count > 4) return false;
        const int f = 2 + part * frame * 2;
        if (L < f + frame * 2) return false;
        snprintf(out, n, "%.2s%.*s", img + f + 2, (frame - 3) * 2, img + f + 6);
        verifyOff = f + 6; verifyLen = (frame - 3) * 2; more = part + 1 < count; return true;
    }
    case BK_MODES:
    { // 34: 4 bytes a slot; 238: count, then 3 bytes a slot (the last two go with the write)
        char extra[300];
        if (BakGet("238", extra, sizeof(extra)) < 2) return false;
        const int count = Hex2(extra);
        if (part >= count || count > 32 || L < count * 8 || (int)strlen(extra) < 2 + count * 6) return false;
        snprintf(out, n, "%02X%.8s%.4s", (unsigned)part, img + part * 8, extra + 2 + part * 6 + 2);
        verifyOff = part * 8; verifyLen = 8; more = part + 1 < count; return true;
    }
    case BK_FAILSAFE:
    { // 3 bytes a channel
        const int count = L / 6 < 18 ? L / 6 : 18;
        if (part >= count) return false;
        snprintf(out, n, "%02X%.6s", (unsigned)part, img + part * 6);
        verifyOff = part * 6; verifyLen = 6; more = part + 1 < count; return true;
    }
    }
    return false;
}
// Is the image read from the FC the same as the file's, for this part?
static bool BakSame(const BakTodo &t, int part, const char *fcHex)
{
    char key[16], img[700];
    const int bankNo = t.bank < 0 ? -1 : (t.bank & 0x3F);
    BakKey(key, sizeof(key), t.readFn, bankNo, t.idx);
    if (BakGet(key, img, sizeof(img)) < 2) return true;
    char payload[700]; int off, len; bool more;
    if (!BakWritePayload(t, part, payload, sizeof(payload), off, len, more)) return true;
    if (off >= 0) return strlen(fcHex) >= (size_t)(off + len) && strncmp(fcHex + off, img + off, len) == 0;
    if (t.kind == BK_TELEM) return strlen(fcHex) >= strlen(img) && strncmp(fcHex, img, 16) == 0 && strncmp(fcHex + 24, img + 24, strlen(img) - 24) == 0;
    if (t.kind == BK_MOTOR || t.kind == BK_BLACKBOX) return strncmp(fcHex, img, strlen(img)) == 0;
    return strncmp(fcHex, img, strlen(img)) == 0;   // (the reply may be longer: the prefix)
}
static int BakRestoreReadAsk(const BakTodo &t)
{
    if (t.idx >= 0) { uint8_t d = (uint8_t)t.idx; return MspAsk(t.readFn, &d, 1); }
    return MspAsk(t.readFn, nullptr, 0);
}
static void BakRestoreNext(); // forward
static void BakRestoreAskSelect(const BakTodo &t)
{
    uint8_t d = (uint8_t)((t.bank & 0x40) ? (0x80 | (t.bank & 0x3F)) : (t.bank & 0x3F));
    BakReq = MspAsk(210, &d, 1);
    BakStep = 10;   // selected -> read
}
static void BakRestoreNext() // BakIdx the item, BakSub the part
{
    if (BakIdx >= BakListN) { BakStep = 80; { uint8_t d = (uint8_t)(Bank - 1); BakReq = MspAsk(210, &d, 1); } return; }
    const BakTodo &t = BakList[BakIdx];
    char what[60];
    if (t.bank >= 0) snprintf(what, sizeof(what), "%s bank %d", t.label, (t.bank & 0x3F) + 1); else snprintf(what, sizeof(what), "%s", t.label);
    BakProgress(what);
    if (t.bank >= 0 && BakSub == 0) { BakRestoreAskSelect(t); return; }
    BakReq = BakRestoreReadAsk(t); BakStep = 11;
}
static void BakNoteFail(const BakTodo &t)
{
    ++BakFails; BakItemWrote = false;
    if (strlen(BakFailed) < 110) { strncat(BakFailed, t.label, sizeof(BakFailed) - strlen(BakFailed) - 1); strncat(BakFailed, ", ", sizeof(BakFailed) - strlen(BakFailed) - 1); }
}
static void BakRestoreTake(bool ok)
{
    BakTodo &t = BakList[BakIdx];
    char payload[700]; int off, len; bool more;
    switch (BakStep)
    {
    case 10: // the bank selected
        if (!ok) { if (++BakTries < 3) { BakRestoreAskSelect(t); return; } BakNoteFail(t); ++BakIdx; ++BakDone; BakSub = 0; BakTries = 0; BakRestoreNext(); return; }
        BakTries = 0; BakReq = BakRestoreReadAsk(t); BakStep = 11;
        return;
    case 11: // the FC's own image: the same already?
        if (!ok)
        {
            if (++BakTries < 3) { BakReq = BakRestoreReadAsk(t); return; }
            BakNoteFail(t); ++BakIdx; ++BakDone; BakSub = 0; BakTries = 0; BakRestoreNext(); return;
        }
        if (!BakWritePayload(t, BakSub, payload, sizeof(payload), off, len, more)) { ++BakIdx; ++BakDone; BakSub = 0; BakRestoreNext(); return; }
        if (BakSame(t, BakSub, PipeRepBody))
        { // this part is as the file has it
            if (more) { ++BakSub; BakReq = BakRestoreReadAsk(t); return; }
            if (BakItemWrote) ++BakWritten; else ++BakUnchanged;
            BakItemWrote = false; ++BakIdx; ++BakDone; BakSub = 0; BakTries = 0; BakRestoreNext(); return;
        }
        { uint8_t b[360]; const int n = HexToBytes(payload, b, sizeof(b)); BakReq = MspAsk(t.writeFn, b, n); }
        BakStep = 12;
        return;
    case 12: // written: read back
        if (!ok) { if (++BakTries < 3) { BakReq = BakRestoreReadAsk(t); BakStep = 11; return; } BakNoteFail(t); ++BakIdx; ++BakDone; BakSub = 0; BakTries = 0; BakRestoreNext(); return; }
        BakWroteAny = true; BakItemWrote = true;
        if (t.writeFn == 143) BakWroteGov = true;
        if (t.writeFn == 222) BakWroteMotor = true;
        BakReq = BakRestoreReadAsk(t); BakStep = 13;
        return;
    case 13: // the read-back
        BakWritePayload(t, BakSub, payload, sizeof(payload), off, len, more);
        if (!ok || !BakSame(t, BakSub, PipeRepBody))
        {
            if (++BakTries < 3) { BakReq = BakRestoreReadAsk(t); BakStep = 11; return; }
            BakNoteFail(t); ++BakIdx; ++BakDone; BakSub = 0; BakTries = 0; BakRestoreNext(); return;
        }
        if (more) { ++BakSub; BakTries = 0; BakReq = BakRestoreReadAsk(t); BakStep = 11; return; }
        ++BakWritten; BakItemWrote = false; ++BakIdx; ++BakDone; BakSub = 0; BakTries = 0; BakRestoreNext();
        return;
    }
}
// ---- the pump: from the main loop while CurrentMode is SAVE_RF_SETTINGS or RESTORE_RF_SETTINGS
void BackupRun()
{
    if (BakJob == BAK_JOB_NONE) { CurrentMode = NORMAL; return; }
    if (BakStep == 95)
    { // after the restart asked of the FC: a breath, then done
        if ((int32_t)(millis() - BakWaitUntil) < 0) return;
        BakStep = 99;
    }
    if (BakStep == 99)
    {
        char v[220];
        if (BakJob == BAK_JOB_BACKUP) snprintf(v, sizeof(v), BakFails ? "Backed up, but %d could not be read:\r\n%.100s" : "Backed up: %d settings on the card.", BakFails ? BakFails : BakDone, BakFailed);
        else snprintf(v, sizeof(v), "%d written, %d were the same already%s%s%.90s", BakWritten, BakUnchanged, BakFails ? ".\r\nNot restored: " : ".", BakFails ? "" : "", BakFails ? BakFailed : "");
        BakFinish(v);
        return;
    }
    if (!PipeReplyReady(BakReq)) { if (PipeReplyLate()) { PipeRepCode = 0; PipeRepBody[0] = 0; } else return; }
    const bool ok = PipeRepCode == 200;
    switch (BakStep)
    {
    case 1: // the status: bank counts (bytes 24, 26) and the banks it is on (23, 25)
    {
        uint8_t b[64];
        const int n = ok ? PipeReplyBytes(b, sizeof(b)) : 0;
        if (n >= 27) { BakPidBanks = b[24] >= 1 && b[24] <= 6 ? b[24] : 6; BakRateBanks = b[26] >= 1 && b[26] <= 6 ? b[26] : 6; BakOrigPid = b[23]; BakOrigRate = b[25]; }
        else { BakPidBanks = BakRateBanks = 6; BakOrigPid = Bank - 1; BakOrigRate = 0; }
        if (BakJob == BAK_JOB_BACKUP)
        {
            Bak[0] = 0; strncpy(BakModel, ModelName, sizeof(BakModel) - 1); BakLoaded = true;
            char line[80];
            snprintf(line, sizeof(line), "rfb=1\nmodel=%s\n", ModelName); strncpy(Bak, line, BAK_MAX - 1);
            if (RTC.read(tm)) { ReadTheRTC(); snprintf(line, sizeof(line), "%d-%02d-%02d %02d:%02d", Gyear + 2000, Gmonth, GmonthDay, Ghour, Gminute); } else strcpy(line, "no clock");
            BakSet("date", line);
            snprintf(line, sizeof(line), "%d/%d", BakPidBanks, BakRateBanks); BakSet("banks", line);
            BakSet("edits", "");
            BakTotal = BakSweepTotal(); BakIdx = 0; BakSub = 0; BakTries = 0;
            BakSweepAsk(); BakStep = 2;
        }
        else
        {
            BakBuildList();
            if (!BakListN) { BakFinish(BakOnlyEdits() ? "No edits are waiting." : "The backup file holds nothing to restore."); return; }
            BakTotal = BakListN; BakIdx = 0; BakSub = 0; BakTries = 0;
            BakRestoreNext();
        }
        return;
    }
    case 2: BakSweepTake(ok); return;
    case 90: // the sweep's bank put back: the file to the card
        { uint8_t d = (uint8_t)(0x80 | (DualRateInUse > 0 ? DualRateInUse - 1 : 0)); BakReq = MspAsk(210, &d, 1); }
        BakStep = 91;
        return;
    case 91:
        if (!BakSave()) { ++BakFails; strncpy(BakFailed, "the card would not take the file", sizeof(BakFailed) - 1); }
        BakStep = 99;
        return;
    case 10: case 11: case 12: case 13: BakRestoreTake(ok); return;
    case 80: // the restore's banks put back (PID done above): the rates bank, then the store
        { uint8_t d = (uint8_t)(0x80 | (DualRateInUse > 0 ? DualRateInUse - 1 : 0)); BakReq = MspAsk(210, &d, 1); }
        BakStep = 81;
        return;
    case 81:
        if (!BakWroteAny) { BakStep = 99; return; }
        BakBusy("Storing in the flight controller ...");
        BakReq = MspAsk(250, nullptr, 0); BakStep = 82;
        return;
    case 82:
        if (!ok) { if (++BakTries < 2) { BakReq = MspAsk(250, nullptr, 0); return; } ++BakFails; strncat(BakFailed, "the store (250): run the restore again", sizeof(BakFailed) - strlen(BakFailed) - 1); BakStep = 99; return; }
        if (BakOnlyEdits()) { BakClearEdits(); BakSave(); }
        if (BakWroteGov || BakWroteMotor)
        {
            BakBusy("Restarting the flight controller ...");
            BakReq = MspAsk(68, nullptr, 0); BakStep = 83;
            return;
        }
        BakStep = 99;
        return;
    case 83:
        BakWaitUntil = millis() + 4000; BakStep = 95;
        return;
    default:
        BakStep = 99;
        return;
    }
}
// ---------------------------------------------------------------- the page
static void BakEditsText(char *out, size_t n)
{ // the edited keys as words: "filters, rescue bank 2"
    char e[400] = "";
    out[0] = 0;
    if (BakGet("edits", e, sizeof(e)) <= 0) return;
    for (char *p = strtok(e, ","); p; p = strtok(nullptr, ","))
    {
        const int fn = atoi(p); const char *dot = strchr(p, '.');
        const char *name = fn == 92 ? "filters" : fn == 36 ? "features" : fn == 146 ? "rescue" : fn == 120 ? "servos" : fn == 42 ? "mixer" : fn == 174 ? "mixer input" : fn == 112 ? "PIDs" : fn == 94 ? "adv. PIDs" : fn == 111 ? "rates" : fn == 148 ? "governor" : fn == 142 ? "governor global" : p;
        char w[40];
        if (dot && fn != 174 && fn != 154) snprintf(w, sizeof(w), "%s bank %d", name, atoi(dot + 1) + 1); else snprintf(w, sizeof(w), "%s", name);
        if (out[0]) strncat(out, ", ", n - strlen(out) - 1);
        strncat(out, w, n - strlen(out) - 1);
    }
}
static void BakShowPage()
{
    char b[120], d[40], e[160];
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)((BoundFlag && ModelMatched) ? "Connected" : "No model"));
    if (BakHaveFile())
    {
        BakGet("date", d, sizeof(d));
        int items = 0; for (const char *p = Bak; (p = strchr(p, '\n')); ++p) ++items;
        snprintf(b, sizeof(b), "Backup on the card: %s (%d lines)", d, items - 5 > 0 ? items - 5 : items);
    }
    else snprintf(b, sizeof(b), "No backup of this model on the card yet");
    SendText((char *)"i0", b);
    BakEditsText(e, sizeof(e));
    if (e[0]) snprintf(b, sizeof(b), "Edits made without the model: %.80s", e); else snprintf(b, sizeof(b), "No edits waiting");
    SendText((char *)"i1", b);
    SendCommand((char *)(e[0] ? "vis b4,1" : "vis b4,0"));
    SendCommand((char *)(BakHaveFile() ? "vis b2,1" : "vis b2,0"));
}
void StartBackupView() // the menu's Backup/Restore
{
    SendCommand((char *)"page RFBackUpView");
    CurrentView = RFBACKUP_RESTOREVIEW;
    BakShowPage();
}
void EndBackupView()
{
    if (BakJob != BAK_JOB_NONE) return;   // (a run is on: wait for it)
    RotorFlightStart();
}
void BackupNow()
{
    if (BakJob != BAK_JOB_NONE) return;
    if (!GetConfirmation((char *)"page RFBackUpView", (char *)"Back up every Rotorflight setting\r\nof this model to the card?\r\n(Any backup there already is replaced.)")) { BakShowPage(); return; }
    BakShowPage();
    BakStart(BAK_JOB_BACKUP);
}
void RestoreAll()
{
    if (BakJob != BAK_JOB_NONE) return;
    if (!GetConfirmation((char *)"page RFBackUpView", (char *)"Write EVERY setting in the backup\r\nto the flight controller?\r\nWhat it has now is replaced.")) { BakShowPage(); return; }
    BakShowPage();
    BakStart(BAK_JOB_RESTORE);
}
void WriteEdits()
{
    if (BakJob != BAK_JOB_NONE) return;
    char e[160], q[220];
    BakEditsText(e, sizeof(e));
    snprintf(q, sizeof(q), "Write the edits made without the model\r\n(%.70s)\r\nto the flight controller?", e);
    if (!GetConfirmation((char *)"page RFBackUpView", q)) { BakShowPage(); return; }
    BakShowPage();
    BakStart(BAK_JOB_EDITS);
}
void DiscardEdits()
{
    if (BakJob != BAK_JOB_NONE || !BakEditsWaiting()) return;
    if (!GetConfirmation((char *)"page RFBackUpView", (char *)"Forget the edits made without the model?\r\nThe backup keeps them until they are written.")) { BakShowPage(); return; }
    BakLoad(ModelName);   // (the file again: the edits as read ... then they are let go with their values? No: the values stay, the marks go)
    BakClearEdits(); BakSave();
    BakShowPage();
}
// At the Rotorflight menu with a model connected: edits waiting are offered, once per connection
static bool BakOffered = false;
void BakOfferEdits()
{
    if (!(BoundFlag && ModelMatched)) { BakOffered = false; return; }
    if (BakOffered || !BakEditsWaiting()) return;
    BakOffered = true;
    char e[160], q[240];
    BakEditsText(e, sizeof(e));
    snprintf(q, sizeof(q), "The backup holds edits made without the model:\r\n%.80s.\r\nWrite them to the flight controller now?", e);
    if (!GetConfirmation((char *)"page RFView", q)) { SendCommand((char *)"page RFView"); return; }
    StartBackupView();
    BakStart(BAK_JOB_EDITS);
}
#endif
