// *************************************** RF_Kept.h *****************************************
// B180 (5 Nov 2026): which of the model's KEPT COPIES are real - the copies the Rotorflight pages keep on the card ("Keep a
// copy", or Save with no model: PIDs, advanced PIDs, rates, advanced rates, governor profile, governor global), shown by the
// pages when there is neither a model nor a backup to read from (RfLive() false).
//
// Malcolm's Black Thunder 1 had never kept one, and its record held whatever bytes lay in that place before the record grew
// (0x64 0x64 ... 0x7F 0x7F): the Governor (global) page showed them as settings - "mode 100, handover 100, spool-up 25700,
// throttle type 127" - and he asked how such corrupted settings could be checked and corrected. They were never the flight
// controller's; the flight controller was fine. A copy that was kept now leaves a MARK, and a copy without the mark is shown
// as "No copy kept".
//
// THE MARK lives in the record's governor-global copy, in the 18 bytes before the values the page uses - Saved_GOV_Config_Values
// [0..17], written to the card with the rest of the record and read by nothing else (the page, its keep, its restore and the
// write packets use [18..41] only): [0] 0xA5, [1..6] a byte a kind with a bit a bank (bit 0 = bank 1 ... bit 5 = bank 6; the
// global kind uses bit 0), [7] a sum. A record from before B180 has no mark - the bytes there are junk or zero - so nothing is
// kept until the pilot keeps it again, with the model connected or with its backup loaded (which is where the pages read from
// then anyway). A new model (SetDefaultValues) starts with no mark. Nothing in the record's layout changes.
// *********************************************************************************************

#ifndef RF_KEPT_H
#define RF_KEPT_H
#include <Arduino.h>
#include "1Definitions.h"

enum : uint8_t { KEPT_PIDS = 1, KEPT_PIDS_ADV = 2, KEPT_RATES = 3, KEPT_RATES_ADV = 4, KEPT_GOV_PROFILE = 5, KEPT_GOV_GLOBAL = 6 };
#define KEPT_MARK 0xA5
#define KEPT_KINDS 6

static inline uint8_t KeptSum()
{
    uint8_t s = KEPT_MARK;
    for (int k = 1; k <= KEPT_KINDS; ++k)
        s = (uint8_t)(s + Saved_GOV_Config_Values[k]);
    return s;
}
static inline bool KeptMarked() { return Saved_GOV_Config_Values[0] == KEPT_MARK && Saved_GOV_Config_Values[7] == KeptSum(); }
static inline uint8_t KeptBit(uint8_t kind, uint8_t bank) // 0..5, or 7 for a bank that is none
{
    if (kind == KEPT_GOV_GLOBAL)
        return 0;
    return (bank >= 1 && bank <= 6) ? (uint8_t)(bank - 1) : 7;
}
// True when that copy was kept since B180 (bank 1..6; the global kind takes any bank)
bool KeptCopy(uint8_t kind, uint8_t bank)
{
    if (kind < 1 || kind > KEPT_KINDS || !KeptMarked())
        return false;
    const uint8_t bit = KeptBit(kind, bank);
    return bit < 7 && (Saved_GOV_Config_Values[kind] & (1 << bit)) != 0;
}
// The copy is kept now: the mark (the caller saves the model after this, as it always did)
void MarkKept(uint8_t kind, uint8_t bank)
{
    if (kind < 1 || kind > KEPT_KINDS)
        return;
    if (!KeptMarked())
    { // the first copy kept since B180: whatever was in these bytes goes
        for (int k = 1; k <= KEPT_KINDS; ++k)
            Saved_GOV_Config_Values[k] = 0;
        Saved_GOV_Config_Values[0] = KEPT_MARK;
    }
    const uint8_t bit = KeptBit(kind, bank);
    if (bit < 7)
        Saved_GOV_Config_Values[kind] |= (uint8_t)(1 << bit);
    Saved_GOV_Config_Values[7] = KeptSum();
}
// Nothing kept (a new model)
void ClearKept()
{
    for (int k = 0; k <= 7; ++k)
        Saved_GOV_Config_Values[k] = 0;
}
// The gray line a page shows in place of a copy it never kept (bank 0: no bank in the words)
const char *KeptNoneText(uint8_t bank)
{
    static char line[80];
    if (bank)
        snprintf(line, sizeof(line), "No copy kept on the card for bank %u (Keep a copy with the model on)", (unsigned)bank);
    else
        snprintf(line, sizeof(line), "No copy kept on the card (Keep a copy with the model on)");
    return line;
}
#endif
