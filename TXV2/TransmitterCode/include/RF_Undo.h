// B196 (Malcolm, 8 Nov 2026: "Please do all five ... Take your time!"): UNDO THE LAST SAVE, on the Guide & checks page
// (RF_Tools.h, 16 MB screens). What a Rotorflight save replaced is kept, and one press puts it back: written by the backup's
// restore engine (RF_Backup.h, BAK_JOB_UNDO) - each item read first and written only where it differs, read back, stored
// (250), and the flight controller restarted when a setting it reads only at its start was among them.
//
// HOW THE "BEFORE" IS KEPT, with no change to any page's own save:
//  - THE MSP PAGES (rescue, servos, filters, battery, beeper & name, model basics, travel extents, black box, level trims,
//    Easy tuning, mounting): every read a page makes over the pipe is kept as it arrives (UndoCache - from this visit to the
//    menu on: RF_Tools.h UndoNewVisit), in the backup's own terms ("146.1", "174.02", "120"). A write takes the kept image of
//    what it changes (its read key: 147 -> 146 of the bank last selected with 210, 212 -> 120, 222 -> 131 ...). A store (250)
//    closes the save. Seen in PipeHttp.h's MspAsk and PipeReplyFromScreen; nothing is asked, nothing is delayed.
//  - THE VERSION 1 WORD PAGES (PIDs, PIDs +, rates, rates dynamics, governor): their bank check (PipeHttp.h BankCheck, B102)
//    reads the transmitter's bank of the block once more, just before the words go; the governor global page likewise
//    (UndoPreSave). On a 4 MB screen this read is never made: those saves go exactly as before.
// A save that cannot be undone says so: Switches & knobs (it changes this transmitter's switches too), Copy a bank, the
// ports, a level calibration - none of them has a "before" Rotorflight can be given back. Only the last save is kept; the
// backup's own jobs (back up, restore, put back) are not saves; another model, and the entry is let go.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_UNDO_H
#define RF_UNDO_H

static const int UNDO_IMG_MAX = 600;     // (52, the adjustments, is the longest Rotorflight sends: 588)
static const int UNDO_CACHE_N = 6, UNDO_KEEP_N = 8;
struct UndoImg { char key[12]; uint16_t n; uint8_t b[UNDO_IMG_MAX]; };
DMAMEM static UndoImg UndoCache[UNDO_CACHE_N];   // the reads of this visit (RAM2)
DMAMEM static UndoImg UndoKeep[UNDO_KEEP_N];     // the last save's "before"
static uint8_t UndoCacheN = 0, UndoCacheNext = 0, UndoKeepN = 0;
static bool UndoOpen = false, UndoReady = false, UndoBad = false;
static char UndoWhat[48] = "", UndoBadWhy[64] = "", UndoModel[32] = "";
static int UndoView = -1;
static uint32_t UndoAt = 0;
struct UndoRd { int id; char key[12]; };
static UndoRd UndoRds[4];               // the reads asked and not yet answered (a page asks one at a time; four, all the same)
static uint8_t UndoRdNext = 0;
static int UndoSelPid = -1, UndoSelRate = -1;   // the banks last chosen with 210 this visit (-1: not chosen)
static uint8_t UndoSelTxBank = 0, UndoSelTxRate = 0;   // this transmitter's banks when they were chosen (review, 8 Nov: the bank
// switch moves the flight controller's bank with no 210 of ours - Easy tuning reads the new bank after it - so a bank chosen
// before the switch moved is not known any more: what is read or written after that is not kept, and the save cannot be undone)

FLASHMEM static const char *UndoPageWords(int view) // the save, in the menu's words
{
    switch (view)
    {
    case PIDVIEW: return "PIDs";
    case PIDADVANCEDVIEW: return "PIDs +";
    case RATESVIEW_RF: case RATESTYPEVIEW: case RATESCURVEVIEW: return "Rates";
    case RATESADVANCEDVIEW: return "Rates dynamics";
    case RFGOVERNORVIEW_PROFILE: return "Governor";
    case RFGOVERNORVIEW_GLOBAL: return "Governor (global)";
    case RESCUEVIEW: case RESCUE2VIEW: return "Rescue";
    case SERVOVIEW: return "Servos";
    case TRAVELVIEW: case TRAVEL2VIEW: case TRAVEL3VIEW: case TRAVEL4VIEW: return "Travel extents";
    case FILTERVIEW: case FILTER2VIEW: return "Filters";
    case BATTERYVIEW: case BATSENSORSVIEW: return "Battery";
    case BLACKBOXVIEW: return "Black box";
    case LEVELVIEW: return "Level trims";
    case BASICSVIEW: case BASICS2VIEW: case PORTSVIEW: case ESCCALVIEW: return "Model basics";
    case EASYVIEW: return "Easy tuning";
    case BEEPERVIEW: return "Beeper & name";
    case COPYBANKVIEW: return "Copy a bank";
    case ADJUSTVIEW: case ADJPICKVIEW: return "Switches & knobs";
    case DIRVIEW: return "Mounting direction";
    default: return "Rotorflight";
    }
}
// (B196) Nothing waits on the pipe: no request since power-up, the last one answered, or given up (PipeHttp.h: one at a time)
FLASHMEM static bool RfPipeFree() { return PipeReqId == 0 || PipeRepId == PipeReqId || PipeReplyLate(); }
FLASHMEM static bool UndoPerBank(uint8_t fn) { return fn == 112 || fn == 94 || fn == 148 || fn == 146; }
FLASHMEM static bool UndoReadKey(uint8_t fn, int idx, char *out, size_t n) // a read of fn as the backup's key; false: not one kept
{
    if (UndoPerBank(fn)) { if (UndoSelPid < 0 || idx >= 0 || Bank != UndoSelTxBank) return false; snprintf(out, n, "%u.%d", (unsigned)fn, UndoSelPid); return true; }
    if (fn == 111) { if (UndoSelRate < 0 || idx >= 0 || DualRateInUse != UndoSelTxRate) return false; snprintf(out, n, "111.%d", UndoSelRate); return true; }
    if (fn == 174 || fn == 154) { if (idx < 0) return false; snprintf(out, n, "%u.%02X", (unsigned)fn, (unsigned)idx); return true; }
    if (idx >= 0) return false;
    snprintf(out, n, "%u", (unsigned)fn);
    return true;
}
FLASHMEM static bool UndoKeyOfWrite(uint8_t fn, const uint8_t *d, int len, char *out, size_t n) // what a write changes
{
    switch (fn)
    {
    case 202: return UndoReadKey(112, -1, out, n);
    case 95: return UndoReadKey(94, -1, out, n);
    case 149: return UndoReadKey(148, -1, out, n);
    case 147: return UndoReadKey(146, -1, out, n);
    case 204: return UndoReadKey(111, -1, out, n);
    case 171: return d && len >= 1 && UndoReadKey(174, d[0], out, n);
    case 155: return d && len >= 1 && UndoReadKey(154, d[0], out, n);
    case 222: return UndoReadKey(131, -1, out, n);
    case 81: return UndoReadKey(80, -1, out, n);
    case 212: return UndoReadKey(120, -1, out, n);
    case 173: return UndoReadKey(172, -1, out, n);
    case 35: return UndoReadKey(34, -1, out, n);
    case 53: return UndoReadKey(52, -1, out, n);
    case 57: return UndoReadKey(56, -1, out, n);
    case 41: return UndoReadKey(40, -1, out, n);
    case 78: return UndoReadKey(77, -1, out, n);
    default: { const uint8_t r = BakReadOfWrite(fn); return r && UndoReadKey(r, -1, out, n); }
    }
}
FLASHMEM static int UndoFind(UndoImg *set, int count, const char *key)
{
    for (int i = 0; i < count; ++i) if (strcmp(set[i].key, key) == 0) return i;
    return -1;
}
FLASHMEM static void UndoAge(char *out, size_t n) // how long ago the save was: "just now", "3 min ago", "2 h ago" (no clock needed)
{
    const uint32_t m = (uint32_t)(millis() - UndoAt) / 60000UL;
    if (m < 1) snprintf(out, n, "just now");
    else if (m < 120) snprintf(out, n, "%lu min ago", (unsigned long)m);
    else snprintf(out, n, "%lu h ago", (unsigned long)(m / 60));
}
FLASHMEM static void UndoMarkBad(const char *why)
{
    UndoBad = true; UndoReady = false;
    if (!UndoBadWhy[0]) snprintf(UndoBadWhy, sizeof(UndoBadWhy), "%s", why);
}
FLASHMEM static void UndoBeginNew(int view = -1) // a new save, of the page it is made on (view: the save's page when known - a word page's read before its words ends in the loop)
{
    const int v = view >= 0 ? view : CurrentView;
    UndoKeepN = 0; UndoOpen = true; UndoReady = false; UndoBad = false; UndoBadWhy[0] = 0;
    UndoView = v; UndoAt = millis();
    snprintf(UndoWhat, sizeof(UndoWhat), "%s", UndoPageWords(v));
    strncpy(UndoModel, ModelName, sizeof(UndoModel) - 1); UndoModel[sizeof(UndoModel) - 1] = 0;
    if (v == ADJUSTVIEW || v == ADJPICKVIEW) UndoMarkBad("it changes this transmitter's switches too");
}
FLASHMEM static void UndoBegin() // a write: part of the save under way (the same page, a moment ago), or a new save
{   // (review, 8 Nov: a save ends at its store (250) - except Easy tuning's, which stores more than once (its PIDs, then the
    //  governor's spool-up bank by bank) and must stay ONE save, its "before" whole: it ends 8 s after its last write or store.
    //  A bank switch moved within it is guarded where it matters, by the bank each read was made of - UndoReadKey)
    if (UndoOpen && UndoView == CurrentView && (uint32_t)(millis() - UndoAt) < 8000) { UndoAt = millis(); return; }
    UndoBeginNew();
}
FLASHMEM static void UndoNameBank(const char *key) // "Rescue" -> "Rescue (bank 2)", from the first per-bank key kept
{
    const int fn = atoi(key);
    const char *dot = strchr(key, '.');
    if (!dot || UndoKeepN != 1 || strstr(UndoWhat, "bank")) return;
    char b[48];
    if (UndoPerBank((uint8_t)fn)) snprintf(b, sizeof(b), "%s (bank %d)", UndoWhat, atoi(dot + 1) + 1);
    else if (fn == 111) snprintf(b, sizeof(b), "%s (rates bank %d)", UndoWhat, atoi(dot + 1) + 1);
    else return;
    snprintf(UndoWhat, sizeof(UndoWhat), "%s", b);
}
FLASHMEM static void UndoTake(const char *key) // the kept "before" of a key this save changes
{
    if (UndoFind(UndoKeep, UndoKeepN, key) >= 0) return;   // (once: its first write's before)
    const int c = UndoFind(UndoCache, UndoCacheN, key);
    if (c < 0) { UndoMarkBad("what it changed had not been read"); return; }
    if (UndoKeepN >= UNDO_KEEP_N) { UndoMarkBad("it changed too many settings at once"); return; }
    UndoKeep[UndoKeepN] = UndoCache[c];
    ++UndoKeepN;
    UndoNameBank(key);
    UndoCache[c].key[0] = 0;   // (used: a later save is kept only from a fresh read - its read-back - never from this, now stale)
}
FLASHMEM static void UndoCacheStore(const char *key, const uint8_t *b, int n)
{
    if (n <= 0 || n > UNDO_IMG_MAX) return;
    int i = UndoFind(UndoCache, UndoCacheN, key);
    if (i < 0) i = UndoFind(UndoCache, UndoCacheN, "");   // (a place a used image left)
    if (i < 0)
    {
        if (UndoCacheN < UNDO_CACHE_N) i = UndoCacheN++;
        else { i = UndoCacheNext; UndoCacheNext = (uint8_t)((UndoCacheNext + 1) % UNDO_CACHE_N); }
    }
    snprintf(UndoCache[i].key, sizeof(UndoCache[i].key), "%s", key);
    memcpy(UndoCache[i].b, b, (size_t)n);
    UndoCache[i].n = (uint16_t)n;
}
// ---- the hooks (PipeHttp.h)
FLASHMEM void UndoSeeAsk(uint8_t fn, const uint8_t *d, int len, int id) // MspAsk, to the receiver: a read remembered, a write taken
{
    if (BakJob != BAK_JOB_NONE) return;   // (the backup's own jobs are not saves)
    if (fn == 210 && d && len >= 1) { if (d[0] & 0x80) { UndoSelRate = d[0] & 0x7F; UndoSelTxRate = DualRateInUse; } else { UndoSelPid = d[0] & 0x7F; UndoSelTxBank = Bank; } return; }
    if (fn == 250) { if (UndoOpen) { UndoReady = !UndoBad && UndoKeepN > 0; if (UndoView == EASYVIEW) UndoAt = millis(); else UndoOpen = false; } return; }   // (stored: offered; only Easy tuning's save goes on after it)
    if (fn == 205) { UndoBegin(); UndoMarkBad("a level calibration: calibrate again"); return; }   // (review: it has no data - not a read)
    if (len == 0 || ((fn == 174 || fn == 154) && len == 1))
    { // a read: kept as it arrives, when it is a setting the restore can write back
        char k[12];
        BakTodo t;
        if (UndoReadKey(fn, len == 1 ? d[0] : -1, k, sizeof(k)) && BakTodoOf(k, t))
        {
            UndoRd &r = UndoRds[UndoRdNext];
            UndoRdNext = (uint8_t)((UndoRdNext + 1) % 4);
            r.id = id; snprintf(r.key, sizeof(r.key), "%s", k);
        }
        return;
    }
    if (fn == 68 || fn == 191 || fn == 195 || fn == 72) return;   // a restart, the live overrides, an erase: not settings
    UndoBegin();
    if (fn == 55) { UndoMarkBad("the ports cannot be put back here"); return; }
    if (fn == 183) { UndoMarkBad("a copied bank: copy it back instead"); return; }
    char k[12];
    if (!UndoKeyOfWrite(fn, d, len, k, sizeof(k)))
    {
        const bool banked = fn == 202 || fn == 95 || fn == 149 || fn == 147 || fn == 204;
        UndoMarkBad(banked ? "which bank it went into is not known" : "this setting cannot be put back here");
        return;
    }
    UndoTake(k);
}
FLASHMEM void UndoSeeReply(int id, int code, const char *body) // PipeReplyFromScreen: a read's answer, kept
{
    if (!id) return;
    int w = -1;
    for (int i = 0; i < 4; ++i) if (UndoRds[i].id == id) w = i;
    if (w < 0) return;
    UndoRds[w].id = 0;
    if (code != 200) return;
    const size_t hl = strlen(body);
    if (hl < 2 || hl / 2 > (size_t)UNDO_IMG_MAX) return;
    uint8_t b[UNDO_IMG_MAX];
    const int n = HexToBytes(body, b, UNDO_IMG_MAX);
    UndoCacheStore(UndoRds[w].key, b, n);
}
FLASHMEM void UndoNewVisit() // the menu, Guide & checks, the guide: a page visit ends - its reads are no longer the flight controller's for sure
{
    UndoCacheN = 0; UndoCacheNext = 0;
    for (int i = 0; i < 4; ++i) UndoRds[i].id = 0;
    UndoSelPid = UndoSelRate = -1;
    if (UndoOpen) { UndoOpen = false; UndoReady = !UndoBad && UndoKeepN > 0; }   // (a save with no store of its own: what it wrote is what it was)
}
// ---- the Version 1 word pages: the block read just before the words go (PipeHttp.h BankCheck; the governor global's UndoPreSave)
FLASHMEM uint8_t UndoFnOfView(int view) // the block a word page's save writes (0: none). Asked from a save, not from the loop.
{
    if (!ScreenIsBig()) return 0;   // (a 4 MB screen: no read before the words, exactly as before)
    switch (view)
    {
    case PIDVIEW: return 112;
    case PIDADVANCEDVIEW: return 94;
    case RATESVIEW_RF: case RATESADVANCEDVIEW: case RATESTYPEVIEW: case RATESCURVEVIEW: return 111;
    case RFGOVERNORVIEW_PROFILE: return 148;
    default: return 0;
    }
}
FLASHMEM void UndoBeforeWords(uint8_t fn, int bank, const char *hex, int view) // the block as it was (hex: nullptr = not read), of the save made on view
{
    UndoBeginNew(view);
    if (!hex || strlen(hex) < 2 || strlen(hex) / 2 > (size_t)UNDO_IMG_MAX) { UndoMarkBad("what it changed could not be read first"); UndoOpen = false; return; }
    char k[12];
    if (bank >= 0) snprintf(k, sizeof(k), "%u.%d", (unsigned)fn, bank); else snprintf(k, sizeof(k), "%u", (unsigned)fn);
    UndoKeep[0].n = (uint16_t)HexToBytes(hex, UndoKeep[0].b, UNDO_IMG_MAX);
    snprintf(UndoKeep[0].key, sizeof(UndoKeep[0].key), "%s", k);
    UndoKeepN = 1;
    UndoNameBank(k);
    UndoOpen = false;   // (the words write and store in the receiver: no 250 of ours closes it)
    UndoReady = true;
}
static void (*UpThen)() = nullptr;
static int UpReq = 0, UpStep = 0, UpBank = -1;
static uint8_t UpFn = 0;
static uint32_t UpAt = 0;
static const char *UpPage = "page RFView";
static int UpView = -1;
FLASHMEM bool UndoPreBusy() { return UpStep != 0; }
FLASHMEM static void UndoPreRefuse(const char *why, bool armed) // the save does not go (its page keeps its edits: Save again)
{
    UpStep = 0;
    BlockBankChanges = false;
    PlaySound(WHAHWHAHMSG);
    if (armed || RfMayFly() || CurrentView != UpView) { RfSayQuietly(why); RfWordPageSays(UpView, why); return; }   // (review, 8 Nov: never a box that waits while it may fly - the switches are not read during it - nor on a page left; the page says it)
    MsgBox((char *)UpPage, (char *)why);
}
FLASHMEM void UndoPreGo(uint8_t fn, int bank, void (*then)(), const char *page, int view) // read the block, keep it, then the save's words (then); view: the save's page
{
    if (UpStep || PipeState != 2 || !(BoundFlag && ModelMatched) || BakOffline()) { then(); return; }   // (no pipe or no model: the save as it always went)
    if (!RfPipeFree())
    { // (another request is out: no read on top of it - this save cannot be undone, and no older one is offered as "the last")
        UndoBeginNew(view); UndoMarkBad("what it changed could not be read first"); UndoOpen = false;
        then();
        return;
    }
    UpThen = then; UpFn = fn; UpBank = bank; UpPage = page; UpView = view; UpStep = 1; UpAt = millis();   // (review: the save's page, not the page in view when the bank check ended - the pilot may have left it)
    UpReq = MspAsk(fn, nullptr, 0);
}
FLASHMEM void UndoPreSave(uint8_t fn, int bank, void (*then)(), const char *page) // the governor global's save (from the save: the screen is asked its size here)
{
    if (!ScreenIsBig()) { then(); return; }   // (a 4 MB screen: the words at once, exactly as before)
    UndoPreGo(fn, bank, then, page, CurrentView);   // (asked from the save itself: this is its page)
}
FLASHMEM void UndoPreTick() // every pass (the loop's page polls)
{
    if (!UpStep) return;
    // (review, 8 Nov: the model gone while this read is out - B90's stand-in would answer it from the backup file and the words
    //  would follow into the file as an edit. Refused instead; and an ARMED answer refuses it as the bank check's 101 does.)
    if (!(BoundFlag && ModelMatched) || PipeState != 2 || BakOffline())
    {
        UndoPreRefuse(RadiosMustBeOff() ? "Not saved: the safety went off. Nothing\r\nwas written." : !(BoundFlag && ModelMatched) ? "Not saved: the model is no longer\r\nconnected. Nothing was written." : "Not saved: Bluetooth to the receiver\r\nwent. Nothing was written.", false);
        return;
    }
    const bool got = PipeReplyReady(UpReq);
    if (!got && (uint32_t)(millis() - UpAt) < 3000) return;
    if (got && PipeRepCode == 409 && strncmp(PipeRepBody, "ARMED", 5) == 0) { UndoPreRefuse("Not saved: the flight controller says\r\nit is ARMED. Nothing was written.", true); return; }
    UpStep = 0;
    UndoBeforeWords(UpFn, UpBank, (got && PipeRepCode == 200) ? PipeRepBody : nullptr, UpView);
    if (UpThen) UpThen();
}
// ---- the undo itself (the Guide & checks page's "Undo the last save")
FLASHMEM static int UndoImageOf(const char *key, char *out, size_t n) // BakToolImage for UNDO: the kept image, as hex
{
    const int i = UndoFind(UndoKeep, UndoKeepN, key);
    if (i < 0) return -1;
    BytesToHex(UndoKeep[i].b, UndoKeep[i].n, out, n);
    return (int)strlen(out);
}
FLASHMEM bool UndoOffered() { return UndoReady && strcmp(UndoModel, ModelName) == 0; }
FLASHMEM void UndoLine(char *out, size_t n) // the Guide & checks page's line under the button
{
    char age[16];
    UndoAge(age, sizeof(age));
    if (UndoOffered()) snprintf(out, n, "Last save: %s, %s", UndoWhat, age);
    else if (UndoBad && strcmp(UndoModel, ModelName) == 0) snprintf(out, n, "The last save (%s) cannot be undone", UndoWhat);
    else snprintf(out, n, "Nothing to undo yet");
}
FLASHMEM bool UndoStart() // true: the job is under way (the caller's page has the question asked already)
{
    if (!UndoOffered()) return false;
    BakToolKeysN = 0;
    for (int i = 0; i < UndoKeepN && BakToolKeysN < 10; ++i) snprintf(BakToolKeys[BakToolKeysN++], sizeof(BakToolKeys[0]), "%s", UndoKeep[i].key);
    BakToolImage = UndoImageOf;
    BakStart(BAK_JOB_UNDO);
    return BakJob == BAK_JOB_UNDO;
}
FLASHMEM void UndoUsed() { UndoReady = false; UndoKeepN = 0; }   // put back: nothing more to undo (a second press would do nothing)

#endif // RF_UNDO_H
