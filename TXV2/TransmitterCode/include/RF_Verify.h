// B153 (Malcolm, 28 Oct 2026, the day after B152's zero-rate save: "It'd be good if the transmitter also read back
// immediately after writing to confirm"): A SAVE IS READ BACK. The Version 1 word pages - PIDs, PID +, Rates, Dynamics
// (the advanced rates) and the governor's bank page - write their block through the receiver, which checks the flight
// controller's answer byte for byte and saves it; but the transmitter said "done" the moment the packets were queued,
// and a write that failed in the receiver (the flight controller silent, a value it would not take, a second Save inside
// a second) was never heard of here: the pilot had to switch banks to see what the flight controller really holds. Now
// the block is asked for again straight after the write packets (queued first, so the LIFO stack sends it last), and
// what comes back is compared with what was sent:
//   - the same: "Saved, and confirmed by reading it back." on the page's line for three seconds, the done
//     sound, and OK's "Save now?" closes the page (RfSavedThenLeave) - usually within a second of Save;
//   - different, or nothing in the window (4 s): the values sent go back on the page with the boxes that differ in red,
//     Save is shown again, and a message says so. A different set does not decide at once but at the window's end: the
//     screen tells a block only when it changes and forgets it on a read, so the write packets' own answers (the old
//     block) are not told; but should one slip through, the block after the write still wins.
// Only with a live model over the pipe: a save into the backup file or the model file has nothing to read back. The
// read is the page's own (its AskValues), so the values come through the same parser and land on the page as on a bank
// change; the read-back belongs to that one read (the kind's start time): a bank change or a page left in the meantime
// ends it with nothing said. Needs: the blocks' arrays, the pages' Msg / Hide / Display / WereEdited functions and box
// names, BlockSeen / BlockShown, RfSavedThenLeave, RfCutNote (1Definitions.h prototypes). Host test: dev/test_verify.
#ifndef RF_VERIFY_H
#define RF_VERIFY_H
#include <Arduino.h>
#include "1Definitions.h"

static uint8_t  VfKind = VK_NONE;                  // the kind being read back (VK_NONE: none)
static uint32_t VfReadStart = 0;                   // the read it belongs to (the kind's start time)
static uint16_t VfSent[MAX_PIDS_ADVANCED_BYTES];   // what was sent (26: the biggest block; the PIDs are 17 words)
static bool     VfSetSeen = false;                 // a whole set came, and differed
static uint32_t VfBannerUntil = 0;                 // the "Saved" line goes at this time
static int      VfBannerView = -1;

FLASHMEM static uint8_t VfCount(uint8_t k)
{
    switch (k)
    {
    case VK_RATES: return MAX_RATES_BYTES;
    case VK_RATES_ADV: return MAX_RATES_ADVANCED_BYTES;
    case VK_PID: return MAX_PID_WORDS + 5;   // 12 PIDs, 3 boosts, 2 HSI offsets
    case VK_PID_ADV: return MAX_PIDS_ADVANCED_BYTES;
    case VK_GOV: return 18;                  // the profile's bytes 0..17 (0 a flag never written, 16-17 the flags as read)
    }
    return 0;
}
FLASHMEM static int VfView(uint8_t k)
{
    switch (k)
    {
    case VK_RATES: return RATESVIEW_RF;
    case VK_RATES_ADV: return RATESADVANCEDVIEW;
    case VK_PID: return PIDVIEW;
    case VK_PID_ADV: return PIDADVANCEDVIEW;
    case VK_GOV: return RFGOVERNORVIEW_PROFILE;
    }
    return -1;
}
FLASHMEM static const char *VfPage(uint8_t k)
{
    switch (k)
    {
    case VK_RATES: return "page RatesView";
    case VK_RATES_ADV: return "page Rates_A_View";
    case VK_PID: return "page PIDView";
    case VK_PID_ADV: return "page PID_A_View";
    case VK_GOV: return "page RFGovView";
    }
    return "page RFView";
}
FLASHMEM static uint32_t VfStart(uint8_t k)
{
    switch (k)
    {
    case VK_RATES: return RATES_Start_Time;
    case VK_RATES_ADV: return RATES_Advanced_Start_Time;
    case VK_PID: return PID_Start_Time;
    case VK_PID_ADV: return PID_Advanced_Start_Time;
    case VK_GOV: return GOV_Start_Time;
    }
    return 0;
}
FLASHMEM static bool VfReading(uint8_t k)
{
    switch (k)
    {
    case VK_RATES: return Reading_RATES_Now;
    case VK_RATES_ADV: return Reading_RATES_Advanced_Now;
    case VK_PID: return Reading_PIDS_Now;
    case VK_PID_ADV: return Reading_PIDS_Advanced_Now;
    case VK_GOV: return Reading_GOV_Now;
    }
    return false;
}
FLASHMEM static void VfReadDone(uint8_t k)
{
    switch (k)
    {
    case VK_RATES: Reading_RATES_Now = false; break;
    case VK_RATES_ADV: Reading_RATES_Advanced_Now = false; break;
    case VK_PID: Reading_PIDS_Now = false; break;
    case VK_PID_ADV: Reading_PIDS_Advanced_Now = false; break;
    case VK_GOV: Reading_GOV_Now = false; break;
    }
}
FLASHMEM static void VfWindow(uint8_t k, uint16_t ms) // how long the read waits (and the receiver answers)
{
    switch (k)
    {
    case VK_RATES: RATES_Send_Duration = ms; break;
    case VK_RATES_ADV: Rates_Advanced_Send_Duration = ms; break;
    case VK_PID: PID_Send_Duration = ms; break;
    case VK_PID_ADV: PID_Advanced_Send_Duration = ms; break;
    case VK_GOV: GOV_Send_Duration = ms; break;
    }
}
// the block's value i as the page holds it (what a read fills), and put back
FLASHMEM static uint16_t VfLive(uint8_t k, uint8_t i)
{
    switch (k)
    {
    case VK_RATES: return Rate_Values[i];
    case VK_RATES_ADV: return Rate_Advanced_Values[i];
    case VK_PID: return i < MAX_PID_WORDS ? PID_Values[i] : i < MAX_PID_WORDS + 3 ? PID_Boost_Values[i - MAX_PID_WORDS] : PID_HSI_Offset_Values[i - MAX_PID_WORDS - 3];
    case VK_PID_ADV: return PID_Advanced_Values[i];
    case VK_GOV: return GovAckPayload[i];
    }
    return 0;
}
FLASHMEM static void VfPut(uint8_t k, uint8_t i, uint16_t v)
{
    switch (k)
    {
    case VK_RATES: Rate_Values[i] = (uint8_t)v; break;
    case VK_RATES_ADV: Rate_Advanced_Values[i] = (uint8_t)v; break;
    case VK_PID:
        if (i < MAX_PID_WORDS) PID_Values[i] = v;
        else if (i < MAX_PID_WORDS + 3) PID_Boost_Values[i - MAX_PID_WORDS] = v;
        else PID_HSI_Offset_Values[i - MAX_PID_WORDS - 3] = v;
        break;
    case VK_PID_ADV: PID_Advanced_Values[i] = (uint8_t)v; break;
    case VK_GOV: GovAckPayload[i] = (uint8_t)v; break;
    }
}
FLASHMEM static bool VfWritten(uint8_t k, uint8_t i) { return k != VK_GOV || i >= 1; }   // (the governor's byte 0 is a flag never written)
FLASHMEM static const char *VfBox(uint8_t k, uint8_t i) // the box on the page that shows value i (none: nullptr)
{
    static char g[6];
    switch (k)
    {
    case VK_RATES: return RatesWindows[i];
    case VK_RATES_ADV: return RatesAWindows[i];
    case VK_PID: return PID_Labels[i];
    case VK_PID_ADV: return PID_Advanced_Labels[i];
    case VK_GOV:
        if (i < 1 || i > 15) return nullptr;   // (16-17: the flags, no box)
        snprintf(g, sizeof(g), "n%u", (unsigned)(i <= 2 ? 0 : i - 2));   // bytes 1-2 = n0 (the headspeed), 3 = n1 ... 15 = n13
        return g;
    }
    return nullptr;
}
FLASHMEM static void VfMsg(uint8_t k, const char *m)
{
    switch (k)
    {
    case VK_RATES: RatesMsg(m, Gray); break;
    case VK_RATES_ADV: RatesAdvancedMsg(m, Gray); break;
    case VK_PID: PIDMsg(m, Gray); break;
    case VK_PID_ADV: PIDAdvancedMsg(m, Gray); break;
    case VK_GOV: ShowGOVMsg(m, Gray); break;
    }
}
FLASHMEM static void VfHide(uint8_t k)
{
    switch (k)
    {
    case VK_RATES: HideRATESMsg(); break;
    case VK_RATES_ADV: Hide_Advanced_Rates_Msg(); break;
    case VK_PID: HidePIDMsg(); break;
    case VK_PID_ADV: HidePID_Advanced_Msg(); break;
    case VK_GOV: HideGOVMsg(); break;
    }
}
FLASHMEM static void VfDisplay(uint8_t k) // the whole block onto the page
{
    switch (k)
    {
    case VK_RATES: DisplayRatesValues(0, MAX_RATES_BYTES); break;
    case VK_RATES_ADV: Display_Advanced_Rates_Values(0, MAX_RATES_ADVANCED_BYTES); break;
    case VK_PID:
        for (uint8_t i = 0; i < MAX_PID_WORDS; i += 2) Display2PIDValues(i);
        DisplayBoostPidValues();
        break;
    case VK_PID_ADV: Display_PID_Advanced_Values(0, MAX_PIDS_ADVANCED_BYTES); break;
    case VK_GOV: DisplayGovValues(1, 18); break;
    }
}
FLASHMEM static void VfEdited(uint8_t k) // Save shown again, the page's edited flag set
{
    switch (k)
    {
    case VK_RATES: RatesWereEdited(); break;
    case VK_RATES_ADV: RatesAdvancedWereEdited(); break;
    case VK_PID: PIDs_Were_edited(); break;
    case VK_PID_ADV: PIDsAdvancedWereEdited(); break;
    case VK_GOV: GOVS_P_Were_Edited(); break;
    }
}

// A page's QueueWrite, before it queues its write packets: true = the block will be read back, and the page's read is
// queued here, first (the LIFO stack sends it after the write packets); the page then leaves its message up and returns.
// False: no pipe (the backup file, the model file, no model): the page finishes its save as it always did.
FLASHMEM bool RfVerifyArm(uint8_t kind, void (*ask)())
{
    VfKind = VK_NONE;
    if (PipeState != 2 || !BoundFlag || !ModelMatched || BakOffline() || CurrentView != VfView(kind) || !ask)
        return false;
    const uint8_t n = VfCount(kind);
    for (uint8_t i = 0; i < n; ++i)
        VfSent[i] = kind == VK_GOV ? GovWritePayload[i] : VfLive(kind, i);
    ask();                                  // the page's own read
    if (!VfReading(kind))                   // (refused after all: the page saves as before)
        return false;
    VfWindow(kind, RF_VERIFY_WAIT_MS);      // the receiver writes first, then answers: longer than a read's own window
    VfReadStart = VfStart(kind);
    VfSetSeen = false;
    VfKind = kind;
    VfMsg(kind, "Sent: reading back from the flight controller ...");
    SendCommand((char *)"vis b3,0");        // (no second Save until the first is known)
    BlockBankChanges = true;
    return true;
}
bool RfVerifyPending() { return VfKind != VK_NONE; }
FLASHMEM static bool VfStillThisRead() // the read-back's read is the one open, on its page
{
    if (VfKind == VK_NONE)
        return false;
    if (CurrentView != VfView(VfKind) || VfStart(VfKind) != VfReadStart)
    { // the page left, or a bank change read afresh: nothing to compare, nothing said
        VfKind = VK_NONE;
        return false;
    }
    return true;
}
// transceiver.h BlockItemSeen, a whole set come: 0 = not a read-back (as ever); 1 = the same as sent (done, and said);
// 2 = different (the window runs on, another set may follow)
FLASHMEM int RfVerifySet()
{
    if (!VfStillThisRead())
        return 0;
    const uint8_t k = VfKind, n = VfCount(k);
    for (uint8_t i = 0; i < n; ++i)
        if (VfWritten(k, i) && VfLive(k, i) != VfSent[i])
        {
            VfSetSeen = true;
            return 2;
        }
    VfKind = VK_NONE;
    VfReadDone(k);                          // (the window closes here: nothing more to parse)
    VfHide(k);
    SendCommand((char *)"vis b3,0");
    SendText((char *)"busy", (char *)"Saved, and confirmed by reading it back.");   // (B154, Malcolm: "the flight controller holds what you sent" was "technically correct but ... phrased better for ordinary users")
    SendCommand((char *)"vis busy,1");
    VfBannerUntil = millis() + 3000;
    VfBannerView = CurrentView;
    PlaySound(BEEPCOMPLETE);
    RfCutNote(VfPage(k));                   // (B07: a value cut to its byte - the page shows what was saved)
    RfSavedThenLeave(VfView(k));            // (B102: OK's "Save now?" closes the page, now that the save is known good)
    return 1;
}
// transceiver.h Hide_msg_if_needed, the read's window ended: true = a read-back's verdict (the page's message hidden here)
FLASHMEM bool RfVerifyEnd(uint8_t kind)
{
    if (VfKind != kind || !VfStillThisRead())
        return false;
    const uint8_t k = VfKind, n = VfCount(k);
    VfKind = VK_NONE;
    RfValueWasCut = false;                  // (B07's note is moot: the values go back on the page as they were sent)
    VfHide(k);
    PlaySound(WHAHWHAHMSG);
    if (!VfSetSeen)
    { // nothing came back: the page still shows what was sent
        MsgBox((char *)VfPage(k), (char *)"NOT CONFIRMED: the flight controller did\r\nnot answer when the values were read\r\nback. Press Save again, and check them.");
        VfEdited(k);
        return true;
    }
    uint8_t nd = 0;
    bool differ[MAX_PIDS_ADVANCED_BYTES];
    for (uint8_t i = 0; i < n; ++i)
    {
        differ[i] = VfWritten(k, i) && VfLive(k, i) != VfSent[i];
        if (differ[i])
            ++nd;
    }
    char m[170];
    snprintf(m, sizeof(m), "NOT SAVED: the flight controller holds\r\nother values for %u box%s, shown in red.\r\nThe values you sent are back: press Save again.", (unsigned)nd, nd == 1 ? "" : "es");
    MsgBox((char *)VfPage(k), m);           // (modal; the page comes back after it with its boxes as they were: they are global on the screen)
    for (uint8_t i = 0; i < n; ++i)
        VfPut(k, i, VfSent[i]);
    VfDisplay(k);
    for (uint8_t i = 0; i < n; ++i)
        if (differ[i] && VfBox(k, i))
            SendForegroundColour(VfBox(k, i), Red);
    VfEdited(k);
    return true;
}
// every 50 ms on a Rotorflight page (transceiver.h Hide_msg_if_needed): the "Saved" line goes after its time
FLASHMEM void RfVerifyTick()
{
    if (!VfBannerUntil || (int32_t)(millis() - VfBannerUntil) < 0)
        return;
    VfBannerUntil = 0;
    if (CurrentView != VfBannerView)
        return;
    if (Reading_PIDS_Now || Reading_RATES_Now || Reading_RATES_Advanced_Now || Reading_PIDS_Advanced_Now || Reading_GOV_Now)
        return;                             // (a new read has the line: its own hide clears it)
    SendCommand((char *)"vis busy,0");
}
#endif // RF_VERIFY_H
