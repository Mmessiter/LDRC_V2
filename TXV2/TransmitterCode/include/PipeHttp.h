// B50: the main board's own line to the receiver over the screen's Bluetooth pipe (screen 1.11.18), for the Rotorflight
// settings the parameter packets never carried (rescue, servos, travel, filters, the ESC): the receiver's raw
// Rotorflight line, /api/msp?fn=N[&data=HEX], which its own pages use. "ldrcreq <id> <path>" goes to the screen,
// "ldrcrep <id> <code> <body>\n" comes back; the body of a read is the reply's bytes as hex. One request at a time, never
// waited for: a page's state machine asks, goes on, and looks for the reply each time round (PipeReplyReady).
#include <Arduino.h>
#include "1Definitions.h"
#ifndef PIPE_HTTP_H
#define PIPE_HTTP_H
// B196: Undo the last save (RF_Undo.h) sees each request and each answer - it keeps what was read, and a write's "before";
// it asks nothing and changes nothing here. The word pages' bank check reads their block once more for it (16 MB screens).
void UndoSeeAsk(uint8_t fn, const uint8_t *data, int len, int id);
void UndoSeeReply(int id, int code, const char *body);
uint8_t UndoFnOfView(int view);
void UndoPreGo(uint8_t fn, int bank, void (*then)(), const char *page, int view);
bool UndoPreBusy();

static int PipeReqId = 0;            // the last request's id
static int PipeRepId = -1;           // the reply in hand is to this request (-1: none)
static int PipeRepCode = 0;          // its HTTP code (0 = the screen could not ask: not joined, no answer)
static char PipeRepBody[1600];       // its body
static uint32_t PipeReqSentMs = 0;
static uint32_t PipeRepMs = 0;       // B143: when the reply in hand came (BankSync.h waits for a page to have read its answer)

int PipeRequest(const char *path)
{
    ++PipeReqId;
    if (PipeReqId > 30000)
        PipeReqId = 1;
    char b[400];
    snprintf(b, sizeof(b), "ldrcreq %d %s", PipeReqId, path);
    SendCommand(b);
    PipeReqSentMs = millis();
    PipeRepId = -1;
    return PipeReqId;
}
bool PipeReplyReady(int id) { return PipeRepId == id; }
bool PipeReplyLate() { return millis() - PipeReqSentMs > 9000; } // the screen gives a request 6 s, and the receiver's own line waits up to a second or two
void PipeReplyFromScreen(const char *text) // "<id> <code> <body>" (up to the line's end)
{
    char *e = nullptr;
    const long id = strtol(text, &e, 10);
    if (e == text)
        return;
    const long code = strtol(e, &e, 10);
    while (*e == ' ')
        ++e;
    size_t n = 0;
    while (e[n] && e[n] != '\n' && e[n] != '\r' && n < sizeof(PipeRepBody) - 1)
        ++n;
    memcpy(PipeRepBody, e, n);
    PipeRepBody[n] = 0;
    PipeRepCode = (int)code;
    PipeRepId = (int)id;
    PipeRepMs = millis();
    UndoSeeReply((int)id, (int)code, PipeRepBody);   // B196: a read's answer kept for Undo (RF_Undo.h)
}
// A Rotorflight request: fn, and the bytes to send with it (none for a read).
bool BakOffline();                                                  // RF_Backup.h (B70): no model, but this model's backup file
// B90 (Malcolm, 9 Oct: "when I disconnected the receiver, I went immediately to the adjustments page, but it failed to
// give me the offline reading. After rebooting the transmitter, it succeeded"): the transmitter declares a model lost
// three seconds after its last packet (RED_LED_ON_TIME; two until B208). A page opened inside those seconds asks the receiver, which
// has gone, and waits nine seconds for nothing; by then the backup file could answer, but nothing asks it. The last
// read sent to the receiver is kept; when the model is declared lost with it unanswered, the file answers it, as it
// would have had the page been opened a moment later (PipeModelGoneTick). A write is left alone: it is reported as
// not done, as before.
static uint8_t PipeLastFn = 0, PipeLastIdx = 0;
static int PipeLastLen = -1;   // (-1: nothing kept)
bool BakOfflineRead(uint8_t fn, int len);   // RF_Backup.h: a request the file answers as a read
bool BakOfflineAnswer(uint8_t fn, const uint8_t *data, int len);    // ... which answers in the flight controller's stead
int MspAsk(uint8_t fn, const uint8_t *data, int len)
{
    if (BakOffline() && BakOfflineAnswer(fn, data, len))
    { // B70: answered from the backup file, at once; the page finds the reply at its next look
        ++PipeReqId;
        if (PipeReqId > 30000)
            PipeReqId = 1;
        PipeRepId = PipeReqId;
        PipeReqSentMs = millis();
        PipeLastLen = -1;
        return PipeReqId;
    }
    PipeLastFn = fn; PipeLastLen = len; PipeLastIdx = (data && len >= 1) ? data[0] : 0;   // B90
    char path[360];
    int n = snprintf(path, sizeof(path), "/api/msp?fn=%u", (unsigned)fn);
    if (data && len > 0)
    {
        n += snprintf(path + n, sizeof(path) - n, "&data=");
        for (int i = 0; i < len && n < (int)sizeof(path) - 3; ++i)
            n += snprintf(path + n, sizeof(path) - n, "%02x", data[i]);
    }
    const int id = PipeRequest(path);
    UndoSeeAsk(fn, data, len, id);   // B196: RF_Undo.h - a read kept as it arrives, a write's "before" taken (to the receiver only: never the backup's stand-in)
    return id;
}
// The reply's hex into bytes; how many.
int PipeReplyBytes(uint8_t *out, int max)
{
    int n = 0;
    const char *p = PipeRepBody;
    while (p[0] && p[1] && n < max)
    {
        char h[3] = {p[0], p[1], 0};
        char *e = nullptr;
        const long v = strtol(h, &e, 16);
        if (e != h + 2)
            break;
        out[n++] = (uint8_t)v;
        p += 2;
    }
    return n;
}
// B82: WHICH BANK IS THE FLIGHT CONTROLLER REALLY ON? After a block is asked for, the receiver is asked (MSP 101, bytes 23
// and 25) at 0.9 s and again at 2.2 s, and the page's bank word says so when it differs: "Bank 3 / FC 2". Malcolm, 9 Oct:
// after three bank changes the PIDs page kept showing the same numbers - the receiver answered, so the question is whether
// the flight controller moved. A mismatch goes to the log too.
static int FcBankReq = 0;
static bool FcBankPending = false;
static int FcPidBank = 0, FcRateBank = 0;   // 1-based, 0 unknown
void LogText(char *TheText, uint16_t len, bool TimeStamp);
static int FcUsOf(uint16_t txUs) { long v = 1500 + ((long)txUs - 1500) * 819L * 5L / (500L * 8L); return v < 988 ? 988 : v > 2012 ? 2012 : (int)v; }   // (this transmitter's microseconds as the FC sees them)
static bool FcBankPage() { return CurrentView == PIDVIEW || CurrentView == RATESVIEW_RF || CurrentView == RATESADVANCEDVIEW || CurrentView == PIDADVANCEDVIEW || CurrentView == RFGOVERNORVIEW_PROFILE; }
static void FcBankShow()
{
    char b[40];
    const bool rates = CurrentView == RATESVIEW_RF || CurrentView == RATESADVANCEDVIEW;
    const int tx = rates ? DualRateInUse : Bank, fc = rates ? FcRateBank : FcPidBank;
    if (!fc) return;
    if (fc == tx) snprintf(b, sizeof(b), "%s %d", rates ? "Rate" : "Bank", tx);
    else
    {
        snprintf(b, sizeof(b), "%s %d / FC %d", rates ? "Rate" : "Bank", tx, fc);
        char l[110];   // (with channels 6 to 8 as the flight controller sees them: the bank switch is usually among them)
        snprintf(l, sizeof(l), "Bank mismatch: transmitter %d, flight controller %d (ch6 %d, ch7 %d, ch8 %d us)", tx, fc, FcUsOf(SendBuffer[5]), FcUsOf(SendBuffer[6]), FcUsOf(SendBuffer[7]));
        LogText(l, strlen(l), false);
    }
    SendText((char *)((CurrentView == PIDADVANCEDVIEW || CurrentView == RFGOVERNORVIEW_PROFILE) ? "t26" : "t9"), b);
}
// B102: A SAVE GOES ONLY INTO THE TRANSMITTER'S BANK. The Version 1 word pages (PIDs, PID +, rates, dynamics and the
// governor) write through the receiver into whichever bank the flight controller is on, which need not be the transmitter's:
// with a bank switch set up wrongly, bank 2's values went into another bank, seen only as "Bank 2 / FC 1" (Malcolm, 15 Oct:
// "Setting a different headspeed for different banks on the transmitter successfully wrote banks one and three but not two"
// - his transmitter's set-up, since put right). Now before each write the flight controller is asked which bank it is on
// (MSP 101): the write goes only if that is the transmitter's; else it is refused, and says why. (It is not put on the
// transmitter's bank: that would hide the set-up's fault until the bank switch is flipped in flight.) With no model (the
// backup file) or no Bluetooth pipe the write goes as before.
static void (*BcThen)() = nullptr;
// B196 (review, 8 Nov 2026): a question that waits for OK stops the switches being read (Utilities.h GetYesOrNo pumps the
// radio, not the switches) - so never one while the model may fly: the safety off (or, with none, the motor on), the arming
// channel high, or the flight controller saying it is armed. Nor on a page the pilot has left (its page would come back over
// the one he is on). Then a refusal is a sound and a line in the log, and the page keeps its edits (Save is still there).
static bool RfMayFly() { char w[128]; return RadiosMustBeOff() || ModelSeemsArmed(w, sizeof(w)); }
static void RfSayQuietly(const char *why)
{
    char l[220];
    snprintf(l, sizeof(l), "Rotorflight (no box: it may fly): %s", why);
    for (char *p = l; *p; ++p) if (*p == '\r' || *p == '\n') *p = ' ';
    LogText(l, (uint16_t)strlen(l), true);
}
// The word page whose save was refused, if it is still the one showing: its "Sending ..." taken away (the labels, Advanced and
// Save back), and the reason on its own line for six seconds (Hide_msg_if_needed takes it away, as the "Saved" line) - seen,
// and nothing waits (review, 8 Nov: a quiet refusal left "Sending ..." up with Save hidden; and the flight controller's own
// ARMED was said by nothing at all on the bench). The page keeps its edits: Save again.
void HidePIDMsg(); void HideRATESMsg(); void Hide_Advanced_Rates_Msg(); void HidePID_Advanced_Msg(); void HideGOVMsg();
static void RfWordPageSays(int view, const char *why)
{
    RfLeaveAfterSave = false;   // (as a box does: OK's "Save now?" does not close the page after a save that was not made)
    if (CurrentView != view) return;   // (left meanwhile: the log has it)
    switch (view)
    {
    case PIDVIEW: HidePIDMsg(); break;
    case RATESVIEW_RF: HideRATESMsg(); break;
    case RATESADVANCEDVIEW: Hide_Advanced_Rates_Msg(); break;
    case PIDADVANCEDVIEW: HidePID_Advanced_Msg(); break;
    case RFGOVERNORVIEW_PROFILE: HideGOVMsg(); break;
    default: break;
    }
    SendCommand((char *)"vis b3,1");
    char one[160];
    snprintf(one, sizeof(one), "%s", why);
    for (char *p = one; *p; ++p) if (*p == '\r' || *p == '\n') *p = ' ';
    const bool glbl = view == RFGOVERNORVIEW_GLOBAL;
    SendText((char *)(glbl ? "t4" : "busy"), one);
    SendCommand((char *)(glbl ? "vis t4,1" : "vis busy,1"));
    SilenceMsgUntil = millis() + 6000; SilenceMsgView = view;
}
// A message from the loop or a state machine (not the pilot's own tap): a box on the bench, a log line while it may fly
static void RfBoxOrQuiet(const char *page, const char *msg)
{
    if (RfMayFly()) { RfSayQuietly(msg); return; }
    MsgBox((char *)page, (char *)msg);
}
static int BcReq = 0, BcStep = 0, BcWant = 0, BcView = -1;
static uint32_t BcAt = 0;   // (when the check began: one left unanswered while the pilot was elsewhere never resumes a save later)
static uint8_t BcUndoFn = 0;   // B196: the block read once more for Undo before the words go (0: none - a 4 MB screen, or not a word page)
static bool BcRates = false;
static const char *BcPage = "page RFView";
FLASHMEM static void BankCheckRefuse(const char *why, bool armed = false)
{
    BcStep = 0;
    BlockBankChanges = false;
    PlaySound(WHAHWHAHMSG);
    if (armed || RfMayFly() || CurrentView != BcView) { RfSayQuietly(why); RfWordPageSays(BcView, why); return; }   // (B196, review: no box that waits while it may fly, or on a page left - the page says it)
    MsgBox((char *)BcPage, (char *)why);
}
FLASHMEM void BankCheck(bool rates, int want, void (*then)(), const char *page)
{
    if (BcStep || UndoPreBusy())
    { // (B196, review: a save under way - its check or Undo's read is out. A second press on its page is the same save; a save
      //  on another page is not made, and that page says so - never two at once)
        if (CurrentView != BcView) { PlaySound(WHAHWHAHMSG); RfWordPageSays(CurrentView, "Not saved: the last save is still being checked. Save again in a moment."); }
        return;
    }
    if (PipeState != 2 || !(BoundFlag && ModelMatched) || BakOffline() || want < 1 || want > 6) { BcStep = 0; then(); return; }
    BcThen = then; BcRates = rates; BcWant = want; BcPage = page; BcView = CurrentView; BcAt = millis();
    BcUndoFn = UndoFnOfView(CurrentView);   // B196 (asked here, from the save: the screen's size is asked only on a save)
    FcBankPending = false;   // (one question at a time on the pipe: this one goes first)
    BcStep = 1;
    BcReq = MspAsk(101, nullptr, 0);
}
FLASHMEM static void BankCheckTick()
{
    if (!BcStep) return;
    if ((uint32_t)(millis() - BcAt) > 12000) { BankCheckRefuse("Not saved: the check of the bank did\r\nnot finish. Nothing was written."); return; }   // (B196, review: never a stale save resumed long after - this runs only on the word pages)
    if (!PipeReplyReady(BcReq))
    {
        if (PipeReplyLate()) BankCheckRefuse("Not saved: the flight controller did\r\nnot say which bank it is on.\r\nNothing was written. Try again.");
        return;
    }
    uint8_t b[40];
    const int n = PipeRepCode == 200 ? PipeReplyBytes(b, sizeof(b)) : 0;
    if (n < 26) { BankCheckRefuse("Not saved: the flight controller did\r\nnot say which bank it is on.\r\nNothing was written. Try again."); return; }
    FcPidBank = (b[23] & 0x0F) + 1; FcRateBank = (b[25] & 0x0F) + 1;
    FcBankShow();
    if (b[6] & 1) { BankCheckRefuse("Not saved: the flight controller says\r\nit is ARMED. Nothing was written.", true); return; }   // B156: its own word, a moment before the write
    const int fc = BcRates ? FcRateBank : FcPidBank;
    if (fc == BcWant)
    {
        BcStep = 0;
        if (BcUndoFn) { const uint8_t f = BcUndoFn; BcUndoFn = 0; UndoPreGo(f, BcWant - 1, BcThen, BcPage, BcView); return; }   // B196: the block as it is, for Undo, then the words (RF_Undo.h)
        BcThen();
        return;
    }
    char m[170];
    snprintf(m, sizeof(m), "Not saved: the flight controller is on\r\n%s %d, the transmitter on %s %d.\r\nCheck the %s switch's set-up.\r\nNothing was written.",
             BcRates ? "rates" : "bank", fc, BcRates ? "rates" : "bank", BcWant, BcRates ? "rates" : "bank");
    BankCheckRefuse(m);
}
void FcBankTick() // every 50 ms (ManageTransmitter)
{
    BankCheckTick();   // (B102)
    if (BcStep || UndoPreBusy()) return;   // (B196: nor while Undo's read before the words is out)
    if (!FcBankPage() || PipeState != 2 || !(BoundFlag && ModelMatched)) { FcBankPending = false; FcBankAskAt = FcBankAskAt2 = 0; return; }
    if (FcBankPending)
    {
        if (PipeReplyReady(FcBankReq))
        {
            uint8_t b[40];
            const int n = PipeRepCode == 200 ? PipeReplyBytes(b, sizeof(b)) : 0;
            FcBankPending = false;
            if (n >= 26) { FcPidBank = (b[23] & 0x0F) + 1; FcRateBank = (b[25] & 0x0F) + 1; FcBankShow(); }
        }
        else if (PipeReplyLate()) FcBankPending = false;
        return;
    }
    uint32_t *at = FcBankAskAt && (int32_t)(millis() - FcBankAskAt) >= 0 ? &FcBankAskAt : FcBankAskAt2 && (int32_t)(millis() - FcBankAskAt2) >= 0 ? &FcBankAskAt2 : nullptr;
    if (!at) return;
    *at = 0;
    FcBankReq = MspAsk(101, nullptr, 0);
    FcBankPending = true;
}
void ShowPIDBank(); void ShowRatesBank(); void ShowRatesAdvancedBank(); void ShowPIDAdvancedBank(); void ShowGOVBank(); void ShowGOV_Global_Bank();
static void RfReadBlockAgain() // the Version 1 word page in view reads its block afresh
{
    switch (CurrentView)
    {
    case PIDVIEW: ShowPIDBank(); break;
    case RATESVIEW_RF: ShowRatesBank(); break;
    case RATESADVANCEDVIEW: ShowRatesAdvancedBank(); break;
    case PIDADVANCEDVIEW: ShowPIDAdvancedBank(); break;
    case RFGOVERNORVIEW_PROFILE: ShowGOVBank(); break;
    case RFGOVERNORVIEW_GLOBAL: ShowGOV_Global_Bank(); break;
    default: break;
    }
}
void RfPipeBack() // the screen says the pipe is ready: a Rotorflight page left unread reads its block now
{
    if (!PipeReadRefused) return;
    PipeReadRefused = false;
    RfReadBlockAgain();
}
bool BakHaveFile();   // RF_Backup.h
void PipeModelGoneTick() // B90 (every 50 ms, ManageTransmitter): the model gone, a read of the receiver's left unanswered: the file answers it
{
    if (PipeRepId != -1 || !PipeReqId || PipeLastLen < 0 || PipeReplyLate()) return;
    if (CurrentMode == SAVE_RF_SETTINGS || CurrentMode == RESTORE_RF_SETTINGS) return;   // (a backup or restore says for itself that the model went)
    if (!BakOffline() || !BakOfflineRead(PipeLastFn, PipeLastLen)) return;
    const int len = PipeLastLen;
    PipeLastLen = -1;
    if (BakOfflineAnswer(PipeLastFn, &PipeLastIdx, len)) PipeRepId = PipeReqId;
}
void RfModelGone() // B90 (RedLedOn, once, as the model is declared lost): a Rotorflight page in view goes over to the backup file
{
    if (!BakHaveFile()) return;
    ShowPipeState();   // the menu's "From the backup file"
    // a Version 1 word page whose read is still open, or that was refused for want of the pipe (B80), reads the file now; one
    // that already shows the flight controller's numbers keeps them (its next save edits the file). A page that asked by
    // MspAsk has its read answered by PipeModelGoneTick.
    const bool reading = Reading_PIDS_Now || Reading_RATES_Now || Reading_RATES_Advanced_Now || Reading_PIDS_Advanced_Now || Reading_GOV_Now || Reading_GOV_Config_Now;
    if (!reading && !PipeReadRefused) return;
    PipeReadRefused = false;
    RfReadBlockAgain();
}

#endif
