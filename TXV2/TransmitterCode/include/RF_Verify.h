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
// B165 (Malcolm, 1 Nov 2026: "check and confirm that after writing new values to the flight controller, the transmitter
// and the app both read back the values"): the governor's GLOBAL page was the one page that did not - its three write
// packets were queued and the page said done. Now it is VK_GOV_CFG here: the 24 config bytes (18-41) are read back
// through the page's own read (GovCfgAskValues) with a longer window (RF_VERIFY_GOVCFG_WAIT_MS: the receiver writes,
// checks, saves and RESTARTS the flight controller, and answers from its verified copy meanwhile), compared with
// GovWritePayload, told on the page's own line (t4), and the page's edited flag stays up until the read-back says saved,
// so OK's "Save now?" waits for the verdict as on the other pages.
// B177 (Malcolm, 4 Nov 2026, after a flight: "I had to reduce P on bank 2 and the transmitter failed to confirm it, but had
// indeed written it"): one window was one chance. The read request rides in one radio packet, never resent, and the
// receiver's own write takes five exchanges with the flight controller - a lost request, or a slow one (the receiver was
// saving flight data in 100-700 ms pauses that day), and the window ended with nothing, or with the receiver's older
// copy. Now the block is asked for again, up to three times (RF_VERIFY_ASKS), each with its own window, before any verdict:
// "Reading back again (2 of 3) ..." on the page's line. A match in any window is a save confirmed. (The receiver, from
// 0.9.915, also keeps the written block streaming for three seconds after its own confirmation, request or no request.)
#ifndef RF_VERIFY_H
#define RF_VERIFY_H
#include <Arduino.h>
#include "1Definitions.h"

static uint8_t  VfBank = 0, VfRate = 0;            // B211 (e99b): the bank and the rate the save was made on (RfVerifyArm)
static uint32_t VfArmMs = 0;                       // B211 (e99e): when the save was sent - a save left behind is followed RF_VERIFY_WAIT_MS from here
static uint32_t VfHoldMs = 0;                      // B211 (e101): THE SAVE'S OWN HOLD ON THE BANK SWITCH (RfSaveHoldsBank): when it was sent,
static bool     VfHold = false, VfHoldLanded = false; // that it stands, and that what was sent has come back
static uint8_t  VfAfresh = VK_NONE;                // B211 (e99e): the kind whose FRESH read saw whole blocks, none of them what the save left behind had sent
static uint8_t  VfKind = VK_NONE;                  // the kind being read back (VK_NONE: none)
static uint32_t VfReadStart = 0;                   // the read it belongs to (the kind's start time)
static uint16_t VfSent[MAX_PIDS_ADVANCED_BYTES];   // what was sent (26: the biggest block; the PIDs are 17 words)
static bool     VfSetSeen = false;                 // a whole set came, and differed
static uint32_t VfBannerUntil = 0;                 // the "Saved" line goes at this time
static int      VfBannerView = -1;
static const char *VfBannerLine = "busy";          // the box the "Saved" line was put in (B165: the governor's global page says it on t4)
#define RF_VERIFY_ASKS 3                           // B177: how many times the block is asked for before a verdict
static uint8_t  VfAsks = 0;                        // B177: asks made so far in this read-back
static void   (*VfAskFn)() = nullptr;              // B177: the page's own read, to ask again

FLASHMEM static uint8_t VfCount(uint8_t k)
{
    switch (k)
    {
    case VK_RATES: return MAX_RATES_BYTES;
    case VK_RATES_ADV: return MAX_RATES_ADVANCED_BYTES;
    case VK_PID: return MAX_PID_WORDS + 5;   // 12 PIDs, 3 boosts, 2 HSI offsets
    case VK_PID_ADV: return MAX_PIDS_ADVANCED_BYTES;
    case VK_GOV: return 18;                  // the profile's bytes 0..17 (0 a flag never written, 16-17 the flags as read)
    case VK_GOV_CFG: return 24;              // B165: the global settings, bytes 18..41 of the governor block (value i = byte 18 + i)
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
    case VK_GOV_CFG: return RFGOVERNORVIEW_GLOBAL;
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
    case VK_GOV_CFG: return "page RFGovViewGlbl";
    }
    return "page RFView";
}
FLASHMEM static const char *VfLine(uint8_t k) { return k == VK_GOV_CFG ? "t4" : "busy"; }   // the page's message line (B165)
FLASHMEM static uint32_t VfStart(uint8_t k)
{
    switch (k)
    {
    case VK_RATES: return RATES_Start_Time;
    case VK_RATES_ADV: return RATES_Advanced_Start_Time;
    case VK_PID: return PID_Start_Time;
    case VK_PID_ADV: return PID_Advanced_Start_Time;
    case VK_GOV: return GOV_Start_Time;
    case VK_GOV_CFG: return GOV_Global_Start_Time;
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
    case VK_GOV_CFG: return Reading_GOV_Config_Now;
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
    case VK_GOV_CFG: Reading_GOV_Config_Now = false; break;
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
    case VK_GOV_CFG: GOV_Config_Send_Duration = ms; break;
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
    case VK_GOV_CFG: return GovAckPayload[18 + i];
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
    case VK_GOV_CFG: GovAckPayload[18 + i] = (uint8_t)v; break;
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
        if (i == 16) return ScreenIsBig() ? "t42" : nullptr;             // B195: the flags' low byte = PID spool-up's label (a 16 MB screen; hidden on a 4 MB one)
        if (i < 1 || i > 15) return nullptr;   // (17: the flags' high byte, no box)
        snprintf(g, sizeof(g), "n%u", (unsigned)(i <= 2 ? 0 : i - 2));   // bytes 1-2 = n0 (the headspeed), 3 = n1 ... 15 = n13
        return g;
    case VK_GOV_CFG:
    { // B165: as DisplayGovConfigValues shows them - 18 n14 (mode), 19 n15 (handover), the six u16s 22-33 on n17..n22, 39 n28 (throttle type), 40 n29, 41 n30
        const uint8_t b = (uint8_t)(18 + i);
        if (b == 18) return "n14";
        if (b == 19) return "n15";
        if (b >= 22 && b <= 33) { snprintf(g, sizeof(g), "n%u", (unsigned)(17 + (b - 22) / 2)); return g; }
        if ((b == 20 || b == 21) && ScreenIsBig()) return "n16";   // B195: start-up (a 16 MB screen)
        if (b >= 34 && b <= 38 && ScreenIsBig()) { static const char *const f[5] = {"n23", "n24", "n25", "n26", "n27"}; return f[b - 34]; }   // B195: the Filters tab
        if (b == 39) return "n28";
        if (b == 40) return "n29";
        if (b == 41) return "n30";
        return nullptr;
    }
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
    case VK_GOV_CFG: ShowGOVConfigMsg(m, Gray); break;
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
    case VK_GOV_CFG: HideGOVConfigMsgQuiet(); break;   // (the plain hide: the page's own asks the read again when it finds the set incomplete)
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
    case VK_GOV_CFG: DisplayGovConfigValues(18, 42); break;
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
    case VK_GOV_CFG: Gov_Global_Were_Edited(); break;
    }
}
FLASHMEM static void VfSaved(uint8_t k) // the read-back matched: a page that kept its edited flag up for the verdict lets it go (B165)
{
    if (k == VK_GOV_CFG)
        GOVS_GLOBAL_Were_Edited = false;
}

// A page's QueueWrite, before it queues its write packets: true = the block will be read back, and the page's read is
// queued here, first (the LIFO stack sends it after the write packets); the page then leaves its message up and returns.
// False: no pipe (the backup file, the model file, no model): the page finishes its save as it always did.
FLASHMEM bool RfVerifyArm(uint8_t kind, void (*ask)())
{
    VfKind = VK_NONE;
    VfAfresh = VK_NONE;
    if (PipeState != 2 || !BoundFlag || !ModelMatched || BakOffline() || CurrentView != VfView(kind) || !ask)
        return false;
    const uint8_t n = VfCount(kind);
    for (uint8_t i = 0; i < n; ++i)
        VfSent[i] = kind == VK_GOV ? GovWritePayload[i] : kind == VK_GOV_CFG ? GovWritePayload[18 + i] : VfLive(kind, i);
    ask();                                  // the page's own read
    if (!VfReading(kind))                   // (refused after all: the page saves as before)
        return false;
    VfWindow(kind, kind == VK_GOV_CFG ? RF_VERIFY_GOVCFG_WAIT_MS : RF_VERIFY_WAIT_MS);   // the receiver writes first, then answers: longer than a read's own window (B165: and restarts the flight controller for the governor's global settings)
    VfReadStart = VfStart(kind);
    VfBank = (uint8_t)Bank;                 // B211 (e99b): whose block was written
    VfRate = (uint8_t)DualRateInUse;
    VfArmMs = millis();
    if (kind != VK_GOV_CFG)                 // B211 (e101): the save itself holds the bank switch. Not the Governor global page: nothing of it is a bank's -
    {                                       // (e101b) and its save leaves an earlier bank page's hold standing (e101c: its matching answer too - RfVerifySet)
        VfHoldMs = VfArmMs;
        VfHold = true;
        VfHoldLanded = false;
    }
    VfSetSeen = false;
    VfAsks = 1;                             // B177
    VfAskFn = ask;
    VfKind = kind;
    VfMsg(kind, "Sent: reading back from the flight controller ...");
    SendCommand((char *)"vis b3,0");        // (no second Save until the first is known)
    BlockBankChanges = true;
    return true;
}
// B211 (the twentieth review, both reviewers: HIGH; e99 to e99e): A SAVE IS FOLLOWED WHEN ITS PAGE IS LEFT. The receiver answers every word of
// a save with the block it has in hand - the OLD one, until the last write word has landed. On the page that set "differs" and the read-back
// waits. But with the page left ("Save", then OK or Help at once) the read-back was dropped, the old block was taken for a plain read, and
// its Hide routine freed the bank switch - with the write still one or two round trips away: the bank switch moved in that quarter second,
// and the edit went into the OTHER bank with nothing said. So, while a save is being followed, a set that is not what was sent is NOT a set
// - not marked, not shown, the bank switch stays held - and the set that is what was sent ends it (the write has landed).
// HOW LONG, AND WHERE (e99e: the tests of e99b to e99d - each narrower rule let a slow write through, or held a page that had its answer):
//   - off its page, its own read still the one open: to that read's window (the read-back's own: RF_VERIFY_WAIT_MS from the save);
//   - its page asked AFRESH - "OK and the same page again", "Help and back", by way of another page (PID + lies behind the PIDs page) -
//     while the save is younger than RF_VERIFY_WAIT_MS, and only on the bank and the rate it was made on (a read asked afresh because the
//     bank has changed is another bank's block);
//   - on ANOTHER page nothing is compared (that page's sets are that page's, and its own read holds the bank switch): the read-back is
//     kept, for its page may be asked again, and let go when the save is RF_VERIFY_WAIT_MS old (it stood for half a minute: e99b's tests).
//     (e99e's tests: THAT page's own read freed the bank switch when its block had come, and a write of the first page landing later went
//     where the switch stood. Since e101 the save itself holds the bank switch there - RfSaveHoldsBank, below.)
// NOT the Governor global page: nothing of it is a bank's, and its window is 8 s (its save restarts the flight controller) - the bank
// switch must not be dead for seconds behind every save there.
FLASHMEM static bool VfExpired() { return (uint32_t)(millis() - VfArmMs) >= RF_VERIFY_WAIT_MS; }                 // the save is older than a read-back's own window
FLASHMEM static bool VfItsRead() { return VfReading(VfKind) && VfStart(VfKind) == VfReadStart; }                  // the read the read-back asked is still the one open
// "A read-back whose read is open": what its callers mean (transceiver.h BlockItemSeen - a set to compare; main.cpp - a window to look at;
// the Governor global page - one save at a time; Utilities.h - no blank screen over it). Asked every 50 ms on every view (main.cpp): here
// the read-back that was left behind and has had its time is let go, and a fresh read's note whose read is over.
bool RfVerifyPending()
{
    if (VfKind != VK_NONE && !VfItsRead() && VfExpired())
        VfKind = VK_NONE;
    if (VfAfresh != VK_NONE && !VfReading(VfAfresh))
        VfAfresh = VK_NONE;
    return VfKind != VK_NONE && VfReading(VfKind);
}
// Motor_sign.h asks, at the motor switch: is a save being followed (a bank page's) BY THE READ THE READ-BACK ITSELF ASKED? Then that read is
// not stopped there: its window is the save's own time, and main.cpp looks at it on the front page until it ends. (e99g: e99f's tests) NOT
// a fresh ask of the page behind the save - the pilot's, or the one more ask: its window ends after the save has been let go, nobody
// looked at it on the front page, and its flag stood there for good. It is stopped at the motor switch as every read is (the released
// firmware's six flags down; the five-second net frees the bank switch - and stands in front of a write still on its way).
// B211 (e101; the twenty-first review, both reviewers): THE SAVE ITSELF HOLDS THE BANK SWITCH - not only a read's flag. Every hold above hangs
// on a read: a fresh read that hears nothing (the receiver is SILENT while it writes) ends and frees the switch with the write still on its
// way; another bank page's own read frees it; and a save of what the flight controller ALREADY HOLDS is "what was sent" in the answer to
// its first write word - "landed" at 0.2 s, before its trigger word has gone (bank 1's whole block went into bank 2, nothing said).
// So, wherever the pilot is: held RF_SAVE_HOLD_FLOOR_MS behind every bank page's save THAT IS READ BACK (RfVerifyArm; a save it refuses is not
// held here: the queue, B19-B4), whatever has come back; after that until what was
// sent has come back; RF_VERIFY_WAIT_MS at most (the save's own time). It adds to BlockBankChanges and frees nothing. Asked by Switches.h.
// (e101b) the floor must clear the save's trigger word (it lands 0.3-0.75 s after Save, one lost round trip more: 0.4-0.6 s) and end before the save's own time
static_assert(RF_SAVE_HOLD_FLOOR_MS >= 1500 && RF_SAVE_HOLD_FLOOR_MS < RF_VERIFY_WAIT_MS, "RF_SAVE_HOLD_FLOOR_MS: at least 1.5 s, less than the read-back's window");
FLASHMEM bool RfSaveHoldsBank()
{
    if (!VfHold)
        return false;
    const uint32_t age = (uint32_t)(millis() - VfHoldMs);
    if (age >= RF_VERIFY_WAIT_MS)
    {
        VfHold = false;
        return false;
    }
    return age < RF_SAVE_HOLD_FLOOR_MS || !VfHoldLanded;
}
bool RfVerifyFollows() { return RfVerifyPending() && VfKind != VK_GOV_CFG && VfStart(VfKind) == VfReadStart; }
FLASHMEM static bool VfStillThisRead() // the read-back's read is the one open, on its page
{
    if (VfKind == VK_NONE)
        return false;
    if (CurrentView != VfView(VfKind) || VfStart(VfKind) != VfReadStart)
    { // the page left, or asked afresh: nothing to compare HERE, nothing said. Let go when it cannot be followed any more (VfSaveLeftBehind):
      // its time over, the Governor global page's, or another bank or rate by now. Else kept: its page may be asked again within its time.
        if (VfExpired() || VfKind == VK_GOV_CFG || (uint8_t)Bank != VfBank || (uint8_t)DualRateInUse != VfRate)
            VfKind = VK_NONE;
        return false;
    }
    return true;
}
FLASHMEM static bool VfSaveLeftBehind()
{
    if (VfKind == VK_NONE || VfKind == VK_GOV_CFG || !VfReading(VfKind))
        return false;
    const bool itsRead = VfStart(VfKind) == VfReadStart;
    if (CurrentView == VfView(VfKind) && itsRead)
        return false;                       // on its page, its own read: the read-back itself (RfVerifySet's second half)
    if (itsRead)
        return true;                        // off its page, its own read still the one open: to that read's window
    return (uint8_t)Bank == VfBank && (uint8_t)DualRateInUse == VfRate && !VfExpired();   // asked afresh: the same bank and rate, the save not yet RF_VERIFY_WAIT_MS old
}
// WHAT THIS HOLDS, THIS ENDS: the reads' windows were looked at only on the Rotorflight pages, and a save followed onto Help kept the bank
// switch held for as long as Help stood (e99's own tests: about 50 of 52 a page) - main.cpp looks at them while a read-back is pending
// (RfVerifyPending), on every view but the blank screen.
// transceiver.h BlockItemSeen, a whole set come: 0 = not a read-back (as ever); 1 = the same as sent (done, and said - or, off its page,
// done and nothing said); 2 = different (the window runs on, another set may follow)
FLASHMEM int RfVerifySet()
{
    if (VfSaveLeftBehind())
    {
        const uint8_t k = VfKind, n = VfCount(k);
        const bool onItsPage = CurrentView == VfView(k);
        for (uint8_t i = 0; i < n; ++i)
            if (VfWritten(k, i) && VfLive(k, i) != VfSent[i])
            {
                if (onItsPage)
                    VfAfresh = k;           // (e99e) this fresh read HAS been answered whole - with other values: at its window's end it asks once more, plain (RfVerifyEnd)
                return 2;                   // (the block as it was before the write: counted afresh, the bank switch held)
            }
        VfKind = VK_NONE;                   // what was sent: the write has landed
        VfHoldLanded = true;                // (e101: ... or the block was that already - the save's own hold stands its 1.5 s all the same)
        VfAfresh = VK_NONE;
        if (!onItsPage)
        { // (e99d) OFF ITS PAGE THE READ IS OVER HERE: its flag down and its Hide routine called (it frees the bank switch wherever it is called;
          // what it writes it writes on its own page only). No flag is left up on the menu, on Help, or on the front page behind the motor switch.
            VfReadDone(k);
            VfHide(k);
            return 1;
        }
        return 0;                           // on its page, asked afresh: a plain set from here (shown, marked, the bank switch freed)
    }
    if (!VfStillThisRead())
    {
        VfAfresh = VK_NONE;                 // (a plain set: the page shows it)
        return 0;
    }
    const uint8_t k = VfKind, n = VfCount(k);
    for (uint8_t i = 0; i < n; ++i)
        if (VfWritten(k, i) && VfLive(k, i) != VfSent[i])
        {
            VfSetSeen = true;
            return 2;
        }
    VfKind = VK_NONE;
    if (k != VK_GOV_CFG)                    // (e101c; review 23, B) not the Governor global page's own answer: an earlier bank page's hold stands until ITS time ends
        VfHoldLanded = true;                // (e101)
    VfReadDone(k);                          // (the window closes here: nothing more to parse)
    VfHide(k);
    VfSaved(k);
    SendCommand((char *)"vis b3,0");
    VfBannerLine = VfLine(k);
    SendText((char *)VfBannerLine, (char *)"Saved, and confirmed by reading it back.");   // (B154, Malcolm: "the flight controller holds what you sent" was "technically correct but ... phrased better for ordinary users")
    SendCommand((char *)(k == VK_GOV_CFG ? "vis t4,1" : "vis busy,1"));
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
    if (VfAfresh == kind)
    { // (e99e; e99b's tests, G3) A SAVE WAS FOLLOWED BEHIND THIS FRESH READ, the flight controller answered whole - never with what was sent - and
      // the read's window is over: the write did not land (lost on its way, refused). Every one of those sets was "not a set", so the page
      // stood not whole, every edit refused, and "only PART came back" was said over blocks that had come whole. The page's own read once
      // more, plain: what the flight controller holds is shown, whole - the truth. (Once: the note is taken away here.)
        VfAfresh = VK_NONE;
        if (VfKind == kind && VfExpired())
            VfKind = VK_NONE;               // (e99f: e99e's own tests) only when the save has had its time: younger, it is followed through this ask too -
                                            // a write that lands 3-4 s after the save found the plain ask's old block "whole" and the bank switch free
        if (!BlockShown && CurrentView == VfView(kind) && VfAskFn)
        {
            VfAskFn();
            if (VfReading(kind))
                return true;
        }
        return false;
    }
    if (VfKind != kind || !VfStillThisRead())
        return false;
    const uint8_t k = VfKind, n = VfCount(k);
    if (VfAsks < RF_VERIFY_ASKS && VfAskFn)
    { // B177: not a verdict yet - the block is asked for again, with a window of its own (the page's own read: its start
      // time is the read-back's identity afresh; the BlockSeen bits clear when the request is sent, Parameters.h)
        VfAskFn();
        if (VfReading(k))
        {
            VfWindow(k, k == VK_GOV_CFG ? RF_VERIFY_GOVCFG_WAIT_MS : RF_VERIFY_WAIT_MS);
            VfReadStart = VfStart(k);
            VfSetSeen = false;
            ++VfAsks;
            char again[56];
            snprintf(again, sizeof(again), "Reading back again (%u of %u) ...", (unsigned)VfAsks, (unsigned)RF_VERIFY_ASKS);
            VfMsg(k, again);
            return true;
        }
    }
    VfKind = VK_NONE;
    RfValueWasCut = false;                  // (B07's note is moot: the values go back on the page as they were sent)
    VfHide(k);
    PlaySound(WHAHWHAHMSG);
    if (!VfSetSeen)
    { // nothing came back in any window: the page still shows what was sent (B177: three asks; the write may well have landed)
        // (10 Nov 2026, the code review) no box while the model may fly (the safety turned off since the Save): a box that waits
        // does not read the switches. Then the sound, a line in the log, and the page keeps its edits (Save is still there).
        static const char notConfirmed[] = "NOT CONFIRMED after 3 read-backs: the\r\nflight controller did not answer. Leave the\r\npage and come back to check what it holds.";
        if (RfMayFly())
            RfSayQuietly(notConfirmed);
        else
            MsgBox((char *)VfPage(k), (char *)notConfirmed);
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
    if (RfMayFly())                         // (10 Nov 2026: as above - no box while the model may fly)
        RfSayQuietly(m);
    else
        MsgBox((char *)VfPage(k), m);       // (modal; the page comes back after it with its boxes as they were: they are global on the screen)
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
    if (Reading_PIDS_Now || Reading_RATES_Now || Reading_RATES_Advanced_Now || Reading_PIDS_Advanced_Now || Reading_GOV_Now || Reading_GOV_Config_Now)
        return;                             // (a new read has the line: its own hide clears it)
    SendCommand((char *)(VfBannerLine[0] == 't' ? "vis t4,0" : "vis busy,0"));
}
#endif // RF_VERIFY_H
