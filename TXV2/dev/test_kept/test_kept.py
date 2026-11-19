#!/usr/bin/env python3
"""Host test of B180 (5 Nov 2026): the Rotorflight pages' KEPT COPIES carry a mark, and a copy without it is not shown as values.

Malcolm's Black Thunder 1 had never kept a copy; its record held whatever bytes lay in that place before the record grew, and
the Governor (global) page, with no model and no backup, showed them as settings ("mode 100, spool-up 25700, throttle type
127"). The real KeptCopy / MarkKept / ClearKept / KeptNoneText of RF_Kept.h are compiled on the Mac over the record's array;
then checks on the source text: every page's local show asks KeptCopy and says "No copy kept", every keep marks, the governor
restore asks the mark, a new model clears it.
   python3 dev/test_kept/test_kept.py"""
import re, os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, 'TransmitterCode')
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()

KEPT = src('include/RF_Kept.h')
body = KEPT[KEPT.index('enum : uint8_t { KEPT_PIDS'):KEPT.index('#endif')]
PROGRAM = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
#define FLASHMEM
#define GOV_CONFIG_PAYLOAD_SIZE 42
#define KEPT_BANKS_ON_CARD @KEPT_BANKS_ON_CARD@   // (1Definitions.h)
static uint8_t Saved_GOV_Config_Values[GOV_CONFIG_PAYLOAD_SIZE] = {0};
''' + body + r'''
static int checks = 0, fails = 0;
#define CHECK(c, what) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, what); } } while (0)
int main() {
    // Black Thunder 1's record, as fetched on 5 Nov 2026: nothing kept
    const uint8_t bt1[42] = { 0x64,0x64,0x64,0x64,0x64,0x64,0x64,0x64,0x64,0x64,0x64,0x64,0x64,0x64,0x64,0x64,0x64,0x64,
                              0x64,0x64,0x64,0x64,0x64,0x64,0x64,0x03,0x05,0x00,0x2a,0x01,0x7f,0x7f,0x7f,0x7f,0x7f,0x7f,0x7f,0x7f,0x7f,0x7f,0x7f,0x7f };
    memcpy(Saved_GOV_Config_Values, bt1, 42);
    for (uint8_t k = 1; k <= 6; ++k) for (uint8_t b = 0; b <= 7; ++b) CHECK(!KeptCopy(k, b), "junk in the record: nothing is kept");
    // Black Thunder 2's record: the next record's bytes - nothing kept either
    const uint8_t bt2[42] = { 0x8f,0x3b,0xd5,0x25,0xff,0x8f,0x3b,0xd5,0x25,0xff,0,0,0,0,0,0x96,0x78,0x5a,0x3c,0x1e,0x96,0x78,0x5a,0x3c,0x1e,0x96,0x78,0x5a,0x3c,0x1e,0x96,0x78,0x5a,0x3c,0x1e,0x96,0x78,0x5a,0x3c,0x1e,0x96,0x78 };
    memcpy(Saved_GOV_Config_Values, bt2, 42);
    for (uint8_t k = 1; k <= 6; ++k) CHECK(!KeptCopy(k, 1), "the next record's bytes: nothing is kept");
    // all zeros (a record never written): nothing kept
    memset(Saved_GOV_Config_Values, 0, 42);
    for (uint8_t k = 1; k <= 6; ++k) CHECK(!KeptCopy(k, 1), "zeros: nothing is kept");
    // the first keep: the junk in the mark's bytes goes, the values [18..41] stay
    memcpy(Saved_GOV_Config_Values, bt1, 42);
    MarkKept(KEPT_GOV_GLOBAL, 0);
    CHECK(KeptCopy(KEPT_GOV_GLOBAL, 0) && KeptCopy(KEPT_GOV_GLOBAL, 3), "the governor global copy is kept (any bank)");
    CHECK(Saved_GOV_Config_Values[0] == 0xA5 && Saved_GOV_Config_Values[18] == 0x64 && Saved_GOV_Config_Values[41] == 0x7f, "the mark is there and the values are untouched");
    for (uint8_t k = 1; k <= 5; ++k) for (uint8_t b = 1; b <= 6; ++b) CHECK(!KeptCopy(k, b), "the other kinds are not kept by it");
    // banks, one by one
    MarkKept(KEPT_PIDS, 4);
    CHECK(KeptCopy(KEPT_PIDS, 4) && !KeptCopy(KEPT_PIDS, 3) && !KeptCopy(KEPT_PIDS, 5) && !KeptCopy(KEPT_PIDS_ADV, 4), "PIDs bank 4 kept, nothing else by it");
    MarkKept(KEPT_RATES, 3); MarkKept(KEPT_RATES_ADV, 1); MarkKept(KEPT_PIDS_ADV, 2); MarkKept(KEPT_GOV_PROFILE, 1);
    CHECK(KeptCopy(KEPT_RATES, 3) && KeptCopy(KEPT_RATES_ADV, 1) && KeptCopy(KEPT_PIDS_ADV, 2) && KeptCopy(KEPT_GOV_PROFILE, 1) && KeptCopy(KEPT_PIDS, 4) && KeptCopy(KEPT_GOV_GLOBAL, 0), "six kinds, the four banks: each remembered");
    CHECK(!KeptCopy(KEPT_RATES, 2) && !KeptCopy(KEPT_RATES, 4) && !KeptCopy(KEPT_GOV_PROFILE, 2), "and no neighbour");
    // B211 (the fourteenth review): BANKS 5 AND 6 - the record holds no copy of theirs (SDcard.h writes four): never marked, never kept, and the words say so
    { uint8_t was[8]; memcpy(was, Saved_GOV_Config_Values, 8);
      for (uint8_t k = 1; k <= 5; ++k) for (uint8_t b = 5; b <= 6; ++b) { MarkKept(k, b); CHECK(!KeptCopy(k, b), "banks 5 and 6: never kept"); }
      CHECK(!memcmp(was, Saved_GOV_Config_Values, 8) && !KeptHasPlace(5) && !KeptHasPlace(6) && KeptHasPlace(4) && KeptHasPlace(1) && !KeptHasPlace(0), "... and the mark is as it was");
      for (uint8_t k = 1; k <= 5; ++k) Saved_GOV_Config_Values[k] |= 0x30;                    // (a card written by B180 to B210: their bits set)
      Saved_GOV_Config_Values[7] = KeptSum();
      for (uint8_t k = 1; k <= 5; ++k) for (uint8_t b = 5; b <= 6; ++b) CHECK(!KeptCopy(k, b), "a mark bit of bank 5 or 6 found on a card is not believed");
      CHECK(KeptCopy(KEPT_PIDS, 4) && KeptCopy(KEPT_RATES, 3), "... the four banks' bits are");
      memcpy(Saved_GOV_Config_Values, was, 8); }
    CHECK(strstr(KeptNoneText(5), "banks 1 to 4 only") && strstr(KeptNoneText(6), "bank 6") && strlen(KeptNoneText(5)) < 80, "the words for a bank the card keeps no copy of");
    // out of range
    CHECK(!KeptCopy(0, 1) && !KeptCopy(7, 1) && !KeptCopy(KEPT_PIDS, 0) && !KeptCopy(KEPT_PIDS, 7), "kind 0 / 7, bank 0 / 7: never kept");
    MarkKept(KEPT_PIDS, 7); MarkKept(0, 1); MarkKept(9, 1);
    CHECK(!KeptCopy(KEPT_PIDS, 7) && KeptCopy(KEPT_PIDS, 4), "a bad bank or kind marks nothing, and breaks nothing");
    // a byte flipped in the mark: nothing is believed
    Saved_GOV_Config_Values[3] ^= 0x40;
    CHECK(!KeptCopy(KEPT_PIDS, 4) && !KeptCopy(KEPT_GOV_GLOBAL, 0), "a flipped byte: the sum fails, nothing is kept");
    Saved_GOV_Config_Values[3] ^= 0x40;
    CHECK(KeptCopy(KEPT_PIDS, 4), "put back: kept again");
    // a new model
    ClearKept();
    CHECK(!KeptCopy(KEPT_PIDS, 4) && !KeptCopy(KEPT_GOV_GLOBAL, 0) && Saved_GOV_Config_Values[0] == 0, "a new model: nothing kept");
    MarkKept(KEPT_GOV_GLOBAL, 0);
    CHECK(KeptCopy(KEPT_GOV_GLOBAL, 0) && !KeptCopy(KEPT_PIDS, 4), "kept afresh: only what was kept");
    // the words
    CHECK(strcmp(KeptNoneText(0), "No copy kept on the card (Keep a copy with the model on)") == 0, "the global page's line");
    CHECK(strcmp(KeptNoneText(3), "No copy kept on the card for bank 3 (Keep a copy with the model on)") == 0 && strlen(KeptNoneText(6)) < 80, "a bank's line");
    printf("%d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''

def main():
    fails = 0
    with tempfile.TemporaryDirectory() as d:
        cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(PROGRAM.replace('@KEPT_BANKS_ON_CARD@', re.search(r'#define KEPT_BANKS_ON_CARD (\d+)', src('include/1Definitions.h')).group(1)))
        exe = os.path.join(d, 't')
        r = subprocess.run(['c++', '-std=c++17', '-fsanitize=address,undefined', '-g', cpp, '-o', exe], capture_output=True, text=True)
        if r.returncode: print(r.stderr); raise SystemExit('compile failed')
        r = subprocess.run([exe], capture_output=True, text=True)
        sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
        if r.returncode: fails += 1
    checks = 0
    def check(cond, what):
        nonlocal checks, fails
        checks += 1
        if not cond: fails += 1; print('FAIL: ' + what)
    pages = {   # file: (show function, its kind + bank, keep function)
        'include/RF_PIDs.h': ('ShowLocalBank', 'KeptCopy(KEPT_PIDS, Bank)', 'SaveToLocalBank', 'MarkKept(KEPT_PIDS, Bank);'),
        'include/RF_PID_Advanced.h': ('ShowLocalPIDsAdvancedBank', 'KeptCopy(KEPT_PIDS_ADV, Bank)', 'SaveToLocalABank', 'MarkKept(KEPT_PIDS_ADV, Bank);'),
        'include/RF_Rates.h': ('ShowRatesLocalBank', 'KeptCopy(KEPT_RATES, DualRateInUse)', 'SaveRatesLocalBank', 'MarkKept(KEPT_RATES, DualRateInUse);'),
        'include/RF_Rates_Advanced.h': ('ShowLocalRatesAdvancedBank', 'KeptCopy(KEPT_RATES_ADV, Bank)', 'SaveLocalRatesAdvancedBank', 'MarkKept(KEPT_RATES_ADV, Bank);'),
        'include/RF_Governor_Profile.h': ('ShowLocalGovBank', 'KeptCopy(KEPT_GOV_PROFILE, Bank)', 'SaveToLocalGovBank', 'MarkKept(KEPT_GOV_PROFILE, Bank);'),
        'include/RF_Governor_Global.h': ('ShowLocalGovConfigBank', 'KeptCopy(KEPT_GOV_GLOBAL, 0)', 'SaveToLocalGovGLOBAL', 'MarkKept(KEPT_GOV_GLOBAL, 0);'),
    }
    for rel, (show, ask, keep, mark) in pages.items():
        s = src(rel)
        fn = s[s.index('void ' + show + '()'):]; fn = fn[:fn.index('\n}\n') + 3]
        check('const bool kept = ' + ask + ';' in fn and 'KeptNoneText(' in fn and ('kept ?' in fn or 'if (!kept)\n        c = zero;' in fn), rel + ': ' + show + ' asks the mark and says "No copy kept" instead of showing values')
        kf = s[s.index('void ' + keep + '()'):]; kf = kf[:kf.index('\n}\n') + 3]
        check(mark in kf and kf.index(mark) < kf.index('SaveOneModel(ModelNumber);'), rel + ': ' + keep + ' marks the copy kept before it saves the model')
        if 'GOV_GLOBAL' not in mark:   # (B211: a bank's copy - refused at once for a bank the record has no place for, before anything is asked or put into memory)
            check(re.search(r'void ' + keep + r'\(\)\s*\{\s*if \(!KeptHasPlace\((?:Bank|DualRateInUse)\)\)\s*\{\s*PlaySound\(WHAHWHAHMSG\);\s*RfLeaveAfterSave = false;\s*\w+_Were_Edited = false;\s*' + show + r'\(\);\s*SendCommand\(\(char \*\)"vis b3,0"\);\s*return;\s*\}', re.sub(r'//[^\n]*', '', kf)) is not None, rel + ': ' + keep + ' refuses a bank the card keeps no copy of - and puts the page back as it showed (' + show + ')')
    g = src('include/RF_Governor_Global.h')
    rs = g[g.index('void RestoreFromSDGlobalGOV()'):]; rs = rs[:rs.index('\n}\n') + 3]
    check('if (!KeptCopy(KEPT_GOV_GLOBAL, 0))' in rs and 'No copy of the governor settings has' in rs, 'the governor restore sends only a copy that was kept (the mark, not "any byte non-zero")')
    m = src('src/main.cpp')
    sd = m[m.index('void SetDefaultValues(bool Calibrating)'):]; sd = sd[:sd.index('\n}\n') + 3]
    check('Saved_GOV_Config_Values[i] = 0;' in sd and 'Saved_GOV_Profiles_Values[i][j] = 0;' in sd, 'a new model clears the governor copies and the mark')
    check('#include "RF_Kept.h"' in m and m.index('#include "RF_Kept.h"') < m.index('#include "RF_PIDs.h"'), 'RF_Kept.h comes before the pages')
    b92 = m[m.index('FLASHMEM void ScreenHasRestarted()'):]; b92 = b92[:b92.index('GotoFrontView();')]   # (B211: the main loop's answer to the screen's restart - it was the word's own branch)
    nxr = src('include/Nextion.h')
    check('const int rst = ScreenRestartReason;' in b92 and 'a BROWN-OUT' in b92 and 'the screen restarted (rst=%d: %s)' in b92 and 'memcmp(w + 9, " rst=", 5)' in nxr and 'NoteScreenRestart(RestartReasonAt(' in nxr,
          'B185: the reason the screen gives for its restart goes in the log line')
    check('ScreenWarmup();' in b92 and 'FLASHMEM void ScreenWarmup()' in m and 'SendOtherValue((char *)"FrontView.pic", BackGroundSelection);' in m[m.index('FLASHMEM void ScreenWarmup()'):], 'B184: after the screen restarts, the background picture, colours and volume are sent again before the front page')
    sr = src('include/RF_Save_Restore.h')
    check(sr.count('MarkKept(') == 5, "the Version 1 picker's five saves mark too")
    import re as _re; _v = _re.search(r'#define TXVERSION_EXTRA "B(\d+) ', src('include/1Definitions.h'))
    check(_v is not None and int(_v.group(1)) >= 180, 'the version is B180 or later')
    print('%d source checks, %d failures' % (checks, fails))
    return fails

if __name__ == '__main__':
    sys.exit(1 if main() else 0)
