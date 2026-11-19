#!/usr/bin/env python3
"""THE KEPT ROTORFLIGHT COPIES OF BANKS 5 AND 6 (the fourteenth review, reviewer B's B1 - his run, taken into the suite; 16 Nov 2026).
PIDs, advanced PIDs, rates, advanced rates and the governor's profile are six banks wide in memory and FOUR on the card (SDcard.h's loops). The MARK
that says "a copy is kept" (RF_Kept.h, a bit a bank) went to the card for banks 5 and 6 too:
 - a six-bank model, PIDs kept in bank 5, off and on: the page showed 0 0 0 as "the kept copy", with no "No copy kept" line;
 - model A's bank 5 kept in a session, model B read: B showed A's numbers as its own.
Now: no copy of banks 5 and 6 is marked, shown or said "kept" (KeptHasPlace); a mark bit of theirs found on a card is not believed; the record's
read and a new model clear banks 5 and 6 in memory; the five "keep" routines refuse at once for such a bank.
The REAL loops of SDcard.h (the record's read and write of these copies), main.cpp's (a new model) and RF_Kept.h run here over a pretend card."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
SD = m.release(m.src('include/SDcard.h')); D1 = m.DEFS; KP = m.release(m.src('include/RF_Kept.h')); MAINC = m.MAIN_CPP
def between(t, a, b):
    i = t.index(a); return t[i:t.index(b, i)]
READ1 = between(SD, '    for (j = 0; j < 4; ++j)\n    {\n        for (i = 0; i < MAX_PID_WORDS + 5; ++i)\n        {\n            Saved_PID_Values[i][j] = SDRead16BITS', '    for (i = 0; i < 8; ++i)\n    {\n        ModelImageFileName[i] = SDRead8BITS')
READ2 = between(SD, '    for (j = 0; j < 4; ++j)\n        for (i = 0; i < GOV_PROFILE_PAYLOAD_SIZE; ++i)\n        {\n            Saved_GOV_Profiles_Values[i][j] = SDRead8BITS', '    CheckOutPutChannels();')
WRITE1 = between(SD, '    for (j = 0; j < 4; ++j)\n    {\n        for (i = 0; i < MAX_PID_WORDS + 5; ++i)\n        {\n            SDUpdate16BITS(SDCardAddress, Saved_PID_Values[i][j]);', '    for (i = 0; i < 8; ++i)\n    {\n        SDUpdate8BITS(SDCardAddress, ModelImageFileName[i]);')
WRITE2 = between(SD, '    for (uint32_t jj = 0; jj < 4; ++jj)\n        for (uint32_t ii = 0; ii < GOV_PROFILE_PAYLOAD_SIZE; ++ii)', '    SaveCheckSum32();')
NEWMODEL = between(MAINC, '    for (j = 0; j < BANKS_USED; ++j) // (B211, the fourteenth review: all six banks', '    strcpy(ModelImageFileName, "Noimage");')
decl = '\n'.join(l for l in D1.split('\n') if re.match(r'uint(8|16)_t Saved_(PID|Rate|Rate_Advanced|PID_Advanced|GOV_Profiles|GOV_Config)_Values\[', l))
bad = []
if len(re.findall(r'j < 4; \+\+j|jj < 4; \+\+jj', READ1 + READ2 + WRITE1 + WRITE2)) != 4 or m.define('KEPT_BANKS_ON_CARD') != '4':
    bad.append('SDcard.h / 1Definitions.h: the record holds the kept copies of KEPT_BANKS_ON_CARD banks - four, as its four loops have it')
if 'for (j = KEPT_BANKS_ON_CARD; j < BANKS_USED; ++j)' not in READ2: bad.append('SDcard.h, the record\'s read: banks 5 and 6 of the kept copies are cleared in memory (the model before left them there)')
# the five "keep" routines refuse at once for a bank the record has no place for - before anything is asked of the screen or put into memory
# (the fifteenth review: ... and the page is put back as it showed - no values, greyed, under its standing line; the refusal's own line took both away)
for f, fn, bank, flag, show in (('RF_PIDs.h', 'SaveToLocalBank', 'Bank', 'PIDS_Were_Edited', 'ShowLocalBank'), ('RF_PID_Advanced.h', 'SaveToLocalABank', 'Bank', 'PIDS_Advanced_Were_Edited', 'ShowLocalPIDsAdvancedBank'),
                                ('RF_Rates_Advanced.h', 'SaveLocalRatesAdvancedBank', 'Bank', 'Rates_Advanced_Were_Edited', 'ShowLocalRatesAdvancedBank'),
                                ('RF_Rates.h', 'SaveRatesLocalBank', 'DualRateInUse', 'Rates_Were_Edited', 'ShowRatesLocalBank'), ('RF_Governor_Profile.h', 'SaveToLocalGovBank', 'Bank', 'GOVS_PROFILE_Were_Edited', 'ShowLocalGovBank')):
    t = re.sub(r'//[^\n]*', '', m.release(m.src('include/' + f)))
    if not re.search(r'void %s\(\)\s*\{\s*if \(!KeptHasPlace\(%s\)\)\s*\{\s*PlaySound\(WHAHWHAHMSG\);\s*RfLeaveAfterSave = false;\s*%s = false;\s*%s\(\);\s*SendCommand\(\(char \*\)"vis b3,0"\);\s*return;\s*\}' % (fn, bank, flag, show), t):
        bad.append('%s %s: a copy of a bank the record has no place for is refused at once - a sound, the page put back as it showed (%s) and its edits let go; nothing asked, nothing put into memory, nothing marked' % (f, fn, show))
    sh = t[t.index('void %s()' % show):]; sh = sh[:sh.index('\n}\n')]
    if not re.search(r'const bool kept = KeptCopy\(\w+, %s\);' % bank, sh) or not re.search(r'if \(kept\)\s*\w+\(\);\s*else\s*\w+\(KeptNoneText\(%s\), Gray\);' % bank, sh):
        bad.append('%s %s: a bank with no kept copy shows no values, greyed, under the line KeptNoneText(%s)' % (f, show, bank))
    if len(re.findall(r'\bMarkKept\(', t)) != 1: bad.append('%s: one MarkKept, in %s' % (f, fn))
for b in bad: print('FAIL: ' + b)
if bad: sys.exit(1)
EXTRA = 'namespace k56 {\n' + decl.replace(' = {0}', '') + r'''
static uint8_t card[8192]; static uint32_t SDCardAddress = 0;
static uint16_t SDRead16BITS(uint32_t a) { return (uint16_t) (card[a] | (card[a + 1] << 8)); } static uint8_t SDRead8BITS(uint32_t a) { return card[a]; }
static void SDUpdate16BITS(uint32_t a, uint16_t v) { card[a] = (uint8_t) v; card[a + 1] = (uint8_t) (v >> 8); } static void SDUpdate8BITS(uint32_t a, uint8_t v) { card[a] = v; }
''' + KP[KP.index('enum : uint8_t { KEPT_PIDS'):KP.index('#endif')].replace('static inline', 'static') + r'''
static void saveRecord() { int i, j; (void) i; (void) j; SDCardAddress = 100; ''' + WRITE1 + WRITE2 + r''' }   // SDcard.h SaveOneModel's own loops for these copies (the mark is in the governor's global copy: it goes with them)
static void readRecord() { int i, j; SDCardAddress = 100; ''' + READ1 + READ2 + r''' }                         // ... and ReadOneModel's
static void newModel() { int i, j; ''' + NEWMODEL + r''' }                                                     // main.cpp SetDefaultValues' own lines
static void wipeMemory() { memset(Saved_PID_Values, 0, sizeof Saved_PID_Values); memset(Saved_Rate_Values, 0, sizeof Saved_Rate_Values); memset(Saved_Rate_Advanced_Values, 0, sizeof Saved_Rate_Advanced_Values);
                           memset(Saved_PID_Advanced_Values, 0, sizeof Saved_PID_Advanced_Values); memset(Saved_GOV_Profiles_Values, 0, sizeof Saved_GOV_Profiles_Values); memset(Saved_GOV_Config_Values, 0, sizeof Saved_GOV_Config_Values); }
static long bank56Sum() { long s = 0; for (int j = 4; j < BANKS_USED; ++j) { for (int i = 0; i < MAX_PID_WORDS + 5; ++i) s += Saved_PID_Values[i][j]; for (int i = 0; i < MAX_RATES_BYTES; ++i) s += Saved_Rate_Values[i][j];
    for (int i = 0; i < MAX_RATES_ADVANCED_BYTES; ++i) s += Saved_Rate_Advanced_Values[i][j]; for (int i = 0; i < MAX_PIDS_ADVANCED_BYTES; ++i) s += Saved_PID_Advanced_Values[i][j]; for (int i = 0; i < GOV_PROFILE_PAYLOAD_SIZE; ++i) s += Saved_GOV_Profiles_Values[i][j]; } return s; }
static void fill(int bank, int base) { const int j = bank - 1; for (int i = 0; i < MAX_PID_WORDS + 5; ++i) Saved_PID_Values[i][j] = (uint16_t) (base + i); for (int i = 0; i < MAX_RATES_BYTES; ++i) Saved_Rate_Values[i][j] = (uint8_t) (base + i);
    for (int i = 0; i < MAX_RATES_ADVANCED_BYTES; ++i) Saved_Rate_Advanced_Values[i][j] = (uint8_t) (base + 1 + i); for (int i = 0; i < MAX_PIDS_ADVANCED_BYTES; ++i) Saved_PID_Advanced_Values[i][j] = (uint8_t) (base + 2 + i); for (int i = 0; i < GOV_PROFILE_PAYLOAD_SIZE; ++i) Saved_GOV_Profiles_Values[i][j] = (uint8_t) (base + 3 + i); }
static bool holds(int bank, int base) { const int j = bank - 1; for (int i = 0; i < MAX_PID_WORDS + 5; ++i) if (Saved_PID_Values[i][j] != (uint16_t) (base + i)) return false; for (int i = 0; i < MAX_RATES_BYTES; ++i) if (Saved_Rate_Values[i][j] != (uint8_t) (base + i)) return false;
    for (int i = 0; i < MAX_RATES_ADVANCED_BYTES; ++i) if (Saved_Rate_Advanced_Values[i][j] != (uint8_t) (base + 1 + i)) return false; for (int i = 0; i < MAX_PIDS_ADVANCED_BYTES; ++i) if (Saved_PID_Advanced_Values[i][j] != (uint8_t) (base + 2 + i)) return false;
    for (int i = 0; i < GOV_PROFILE_PAYLOAD_SIZE; ++i) if (Saved_GOV_Profiles_Values[i][j] != (uint8_t) (base + 3 + i)) return false; return true; }
}
'''
SCENES = r'''
    using namespace k56;
    // T1. banks 1 to 4: a copy kept is on the card, comes back, and counts as kept
    {
        wipeMemory(); memset(card, 0xEE, sizeof card);
        for (int bank = 1; bank <= 4; ++bank) { CHECK(KeptHasPlace((uint8_t) bank)); fill(bank, 10 * bank); for (uint8_t kind = KEPT_PIDS; kind <= KEPT_GOV_PROFILE; ++kind) MarkKept(kind, (uint8_t) bank); }
        MarkKept(KEPT_GOV_GLOBAL, 0); saveRecord(); wipeMemory(); readRecord();
        bool all = KeptCopy(KEPT_GOV_GLOBAL, 0); for (int bank = 1; bank <= 4; ++bank) { all = all && holds(bank, 10 * bank); for (uint8_t kind = KEPT_PIDS; kind <= KEPT_GOV_PROFILE; ++kind) all = all && KeptCopy(kind, (uint8_t) bank); }
        say("T1. banks 1 to 4 kept, the transmitter off and on: every copy is back and counts as kept: %d\n", (int) all);
        CHECK(all && bank56Sum() == 0);
    }
    // T2. BANK 5 (and 6): nothing is marked, nothing counts as kept - and the page's line says why
    {
        wipeMemory(); memset(card, 0xEE, sizeof card);
        CHECK(!KeptHasPlace(5) && !KeptHasPlace(6) && !KeptHasPlace(0) && !KeptHasPlace(7));
        MarkKept(KEPT_PIDS, 2);                                                              // (a mark is there: bank 2's PIDs)
        const uint8_t before[8] = { Saved_GOV_Config_Values[0], Saved_GOV_Config_Values[1], Saved_GOV_Config_Values[2], Saved_GOV_Config_Values[3], Saved_GOV_Config_Values[4], Saved_GOV_Config_Values[5], Saved_GOV_Config_Values[6], Saved_GOV_Config_Values[7] };
        for (int bank = 5; bank <= 6; ++bank) for (uint8_t kind = KEPT_PIDS; kind <= KEPT_GOV_PROFILE; ++kind) { MarkKept(kind, (uint8_t) bank); CHECK(!KeptCopy(kind, (uint8_t) bank)); }
        CHECK(!memcmp(before, Saved_GOV_Config_Values, 8) && KeptCopy(KEPT_PIDS, 2));          // the mark is as it was
        CHECK(strstr(KeptNoneText(5), "banks 1 to 4 only") && strstr(KeptNoneText(6), "bank 6") && strstr(KeptNoneText(3), "No copy kept on the card for bank 3"));
        CHECK(strlen(KeptNoneText(6)) < 80);
        // A CARD FROM B180 TO B210 with the mark's bits of banks 5 and 6 set (it was written so): not believed - the page shows no numbers as "the kept copy"
        for (uint8_t kind = KEPT_PIDS; kind <= KEPT_GOV_PROFILE; ++kind) Saved_GOV_Config_Values[kind] |= 0x30;
        Saved_GOV_Config_Values[7] = KeptSum(); CHECK(KeptMarked());
        saveRecord(); wipeMemory(); readRecord();
        bool none = true; for (int bank = 5; bank <= 6; ++bank) for (uint8_t kind = KEPT_PIDS; kind <= KEPT_GOV_PROFILE; ++kind) none = none && !KeptCopy(kind, (uint8_t) bank);
        say("T2. a card whose mark says banks 5 and 6 are kept (B180 to B210 wrote it so): counted as kept after the read: %d; bank 2's PIDs still kept: %d\n", (int) !none, (int) KeptCopy(KEPT_PIDS, 2));
        CHECK(none && KeptCopy(KEPT_PIDS, 2) && KeptMarked());
    }
    // T3. MODEL A's bank 5 and 6 in memory (a flight controller's values shown there, or B210's "kept" copy); MODEL B is read: nothing of A's is left
    {
        wipeMemory(); memset(card, 0, sizeof card); saveRecord();                               // model B's record: nothing kept
        fill(5, 90); fill(6, 120); fill(2, 30); CHECK(bank56Sum() > 0);
        readRecord();
        say("T3. model A's banks 5 and 6 in memory, then model B read from the card: what is left of A's there: %ld\n", bank56Sum());
        CHECK(bank56Sum() == 0 && holds(2, 0) == false);
        fill(5, 90); fill(6, 120); fill(1, 7); newModel(); CHECK(bank56Sum() == 0 && Saved_PID_Values[0][0] == 0 && !KeptMarked());   // ... and a new model (main.cpp SetDefaultValues): all six banks cleared
    }
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('kept_copies', SCENES, extra=EXTRA, more_defines=('MAX_PID_WORDS', 'MAX_RATES_BYTES', 'MAX_RATES_ADVANCED_BYTES', 'MAX_PIDS_ADVANCED_BYTES', 'GOV_PROFILE_PAYLOAD_SIZE', 'GOV_CONFIG_PAYLOAD_SIZE', 'KEPT_BANKS_ON_CARD')))
