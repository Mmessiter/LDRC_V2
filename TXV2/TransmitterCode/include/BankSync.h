// B143: THE BANK COUNT, TOLD TO THE RECEIVER. The phone app's pages and this transmitter must agree on how many banks a
// model has (Malcolm, 21 Oct 2026: "it's important that the app and the transmitter are set to the same settings ... if
// one of them changes the number of banks without saving the switches and knob settings afterwards, the other does not
// know"). The transmitter decides: Model options' 'Six banks' (BanksCount(): 4 or 6). It tells the receiver over the pipe
// - GET /api/tx/banks?n=N&rates=F (F: the rates follow the banks, so the Rates selector is the Bank selector) - a moment
// after the pipe comes up, and again whenever the count changes; the receiver keeps it (RAM at once, flash at a quiet
// moment) and its pages follow: the tuning pages draw that many banks, the Bank selector on the Switches page is locked
// to that many positions. The receiver answers with the position count of the flight controller's bank line as last
// seen through it ("selector"); when that is known and differs, the pilot is told at once - a message box, on the
// Rotorflight menu (B145), with the motor off: the bank switch would put the flight controller on the wrong bank. An
// older receiver (404) is told nothing more that session. Never while another request waits on the pipe: a page's own
// read goes first, and the pipe carries one answer at a time (PipeHttp.h).
#include <Arduino.h>
#include "1Definitions.h"
#ifndef BANK_SYNC_H
#define BANK_SYNC_H
// BANKSYNC-LOGIC-BEGIN (dev/test_banksync: compiled on the Mac with stubs round it)
static int BsReq = 0;                       // the request waiting for its answer (0: none)
static uint8_t BsTold = 0;                  // the count the receiver was told this pipe session (0: not yet)
static bool BsToldFollow = false;           // ... and whether the rates follow the banks
static uint8_t BsTries = 0;                 // asks this session without an answer (a few, then it is left for the session)
static uint32_t BsNextAt = 0;               // not before this (a moment after the pipe comes up; a pause after a lost answer)
static uint8_t BsWarnSel = 0, BsWarnN = 0;  // a warning owed: the flight controller's selector positions, the transmitter's banks
static uint32_t BsWarnAt = 0;               // B145: when the answer that owes it came
static const uint32_t BS_SETTLE_MS = 1500, BS_AGAIN_MS = 3000, BS_FRESH_MS = 5000;
static const uint8_t BS_TRIES = 4;
static int BsJsonInt(const char *body, const char *key) // the number after "key": in a reply; -1 when it is not there
{
    const char *p = strstr(body, key);
    if (!p) return -1;
    p += strlen(key);
    while (*p == ' ') ++p;
    char *e = nullptr;
    const long v = strtol(p, &e, 10);
    return e == p ? -1 : (int)v;
}
static bool BsPipeFree() // nothing of anyone's is waiting on the pipe
{
    if (PipeReqId == 0 || PipeReplyLate()) return true;                       // never asked, or the last ask was given up on
    return PipeRepId == PipeReqId && (uint32_t)(millis() - PipeRepMs) > 300;  // the last ask answered, and its page has had time to read the answer
}
// B145 (Malcolm, 22 Oct: "the transmitter failed to read governor values - but after a reboot it succeeded"): B143 let
// the warning out on any page from the PIDs' to the governor's. A message box over a page whose block is still being
// read loses the read: the values come while the box is up, and the page is drawn afresh, empty, when it goes. (The
// backup page and the bank pickers were in that range too, and the box's return took the screen to the menu.) Nor the
// front view: the pipe is let go there (GotoFrontView), so a box could only come as the page changes. So the Rotorflight
// menu alone: nothing is read there, the pipe is up, and the bank line is put right from it (Switches & knobs).
static bool BsCanWarnHere() // the Rotorflight menu, the motor off, no other question open
{
    if (MotorEnabled || ModalWaits) return false;
    return CurrentView == ROTORFLIGHTVIEW;
}
FLASHMEM static void BsWarnNow()
{
    char m[230];
    snprintf(m, sizeof(m), "The flight controller's bank selector\r\nhas %d positions; this model has %d\r\nbanks. USB cable, then 'Switches & knobs'\r\n(here or on the phone) and Save the bank\r\nline, or the switch picks the wrong bank.", BsWarnSel, BsWarnN);
    char l[120];
    snprintf(l, sizeof(l), "Bank count: the transmitter has %d banks, the flight controller's selector %d positions", BsWarnN, BsWarnSel);
    LogText(l, strlen(l), true);
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)BakPageOf(CurrentView), m);   // (the menu: "page RFView")
    ShowPipeState(); SendText((char *)"t11", ModelName); ShowRFBank(); ShowRFRate();   // the menu drawn afresh by the box's return: its words again, as RotorFlightStart wrote them
    BsWarnSel = 0;
}
void BankSyncTick() // every 50 ms (ManageTransmitter)
{
    if (PipeState != 2 || !(BoundFlag && ModelMatched))
    { // (no pipe: a new pipe session tells afresh)
        BsTold = 0; BsToldFollow = false; BsReq = 0; BsTries = 0; BsNextAt = 0;
        return;
    }
    const uint8_t n = BanksCount();
    const bool f = LinkRatesToBanks;
    if (BsWarnSel && BsCanWarnHere())
    { // B145: only on a fresh answer. One that came while the pilot was on another page may be out of date - the bank line
      // put right on Switches & knobs meanwhile - so the receiver is asked again from here, and its answer decides.
        if ((uint32_t)(millis() - BsWarnAt) <= BS_FRESH_MS) BsWarnNow();
        else { BsWarnSel = 0; BsTold = 0; BsReq = 0; BsTries = 0; BsNextAt = 0; return; }
    }
    if (BsReq)
    {
        if (PipeReplyReady(BsReq))
        {
            BsReq = 0; BsTold = n; BsToldFollow = f; BsTries = 0;
            if (PipeRepCode == 200)
            {
                const int sel = BsJsonInt(PipeRepBody, "\"selector\":");
                if (sel > 0 && sel != n) { BsWarnSel = (uint8_t)sel; BsWarnN = n; BsWarnAt = millis(); }
                else BsWarnSel = 0;   // (B145: put right since an earlier answer: nothing owed)
            }
            return; // (404 or anything else: an older receiver - told nothing more this session)
        }
        if (PipeReqId != BsReq || PipeReplyLate()) { BsReq = 0; BsNextAt = millis() + BS_AGAIN_MS; }   // (another ask went after ours, or no answer: again in a moment)
        return;
    }
    if (BsTold == n && BsToldFollow == f) return;
    if (!BsNextAt) BsNextAt = millis() + BS_SETTLE_MS;
    if ((int32_t)(millis() - BsNextAt) < 0 || !BsPipeFree()) return;
    if (BsTries >= BS_TRIES) { BsTold = n; BsToldFollow = f; return; }   // (left for the session: the pipe never answered)
    ++BsTries;
    char p[48];
    snprintf(p, sizeof(p), "/api/tx/banks?n=%u&rates=%u", (unsigned)n, f ? 1u : 0u);
    BsReq = PipeRequest(p);
    BsNextAt = 0;
}
// BANKSYNC-LOGIC-END
#endif
