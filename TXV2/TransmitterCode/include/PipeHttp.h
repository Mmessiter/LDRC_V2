// B50: the main board's own line to the receiver over the screen's Bluetooth pipe (screen 1.11.18), for the Rotorflight
// settings the parameter packets never carried (rescue, servos, travel, filters, the ESC): the receiver's raw
// Rotorflight line, /api/msp?fn=N[&data=HEX], which its own pages use. "ldrcreq <id> <path>" goes to the screen,
// "ldrcrep <id> <code> <body>\n" comes back; the body of a read is the reply's bytes as hex. One request at a time, never
// waited for: a page's state machine asks, goes on, and looks for the reply each time round (PipeReplyReady).
#include <Arduino.h>
#include "1Definitions.h"
#ifndef PIPE_HTTP_H
#define PIPE_HTTP_H

static int PipeReqId = 0;            // the last request's id
static int PipeRepId = -1;           // the reply in hand is to this request (-1: none)
static int PipeRepCode = 0;          // its HTTP code (0 = the screen could not ask: not joined, no answer)
static char PipeRepBody[1600];       // its body
static uint32_t PipeReqSentMs = 0;

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
}
// A Rotorflight request: fn, and the bytes to send with it (none for a read).
bool BakOffline();                                                  // RF_Backup.h (B70): no model, but this model's backup file
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
        return PipeReqId;
    }
    char path[360];
    int n = snprintf(path, sizeof(path), "/api/msp?fn=%u", (unsigned)fn);
    if (data && len > 0)
    {
        n += snprintf(path + n, sizeof(path) - n, "&data=");
        for (int i = 0; i < len && n < (int)sizeof(path) - 3; ++i)
            n += snprintf(path + n, sizeof(path) - n, "%02x", data[i]);
    }
    return PipeRequest(path);
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
void FcBankTick() // every 50 ms (ManageTransmitter)
{
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
void RfPipeBack() // the screen says the pipe is ready: a Rotorflight page left unread reads its block now
{
    if (!PipeReadRefused) return;
    PipeReadRefused = false;
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

#endif
