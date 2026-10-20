#!/usr/bin/env python3
"""Host test of B130 (Malcolm, 19 Oct 2026: "I have an idea for allowing the transmitter to support six banks rather than only
four ... the switch would select bank 4 only if the switch handling banks 1, 2 & 3 is in the Bank 1 position. Thus, it would
convert that switch in selecting banks 4, 5, 6" - and "using six or four banks could become an option").
  1. The model file. Banks 5 and 6 have no room in the record, so they live in a block of their own (SDcard.h BanksBlockBuild /
     BanksBlockTake): in-line in a .MOD, in /banks56/<slot>.b56 for models.dat, with a four-byte header in the record. Here the
     real ReadModelExtension / SaveModelExtension (and their helpers) run over a fake card beside B129's (git show HEAD), over
     random curves, both max ranges and both kinds of file:
       - a FOUR-bank model saves exactly the bytes B129 saved, and reads the same curves back (a firmware before B130 reads a
         B130 file, and B130 reads an old one: no change for a model that never chose six banks);
       - a six-bank .MOD carries banks 5 and 6 in-line and reads back whole; B129's reader takes its curves and ignores the rest;
       - a six-bank model in models.dat writes the banks file and the header; the file is taken only whole, sound and named
         for this model (a bad checksum, another model's name, no file: banks 5 and 6 are bank 4's twins, named after the four);
       - Six banks turned off keeps the file; turned on again takes it back (nothing lost).
  2. The switches (Switches.h ReadBankSwitch / ReadAutoAndMotorSwitch): with four banks, as ever; with six, the 'Bank 4 & Motor'
     switch's mid and near positions pick 4, 5 or 6 by the 'Banks 1 2 3' switch; a block on bank changes holds; the motor
     follows the switch regardless.
  3. The buddy byte (BuddyWireless.h): banks 1 to 6 and rates 1 to 4 travel and come back; a pupil on four banks takes 4 for 5
     and 6.
  4. The settings guard (FlightGuard.h ControlFingerprint): B129's and B130's, over the same random four-bank setups, give the
     same number (the update is compared and kept); with six banks on, a different one.
  5. Sources and pages: the file loops stay at four, the pages and help say six, the clips are on the card.
   python3 dev/test_banks/test_banks.py"""
import json, os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.environ.get('TXV1B_TC', os.path.join(ROOT, 'TransmitterCode'))
SCREEN = os.path.join(ROOT, '..', 'ESP32-board2', 'board4', 'nextion-emulator')
checks = fails = 0
def check(c, what):
    global checks, fails
    checks += 1
    if not c:
        fails += 1
        print('FAIL:', what)
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()
def lift_from(text, head, rename=None):
    lines = text.split('\n')
    for i, l in enumerate(lines):
        if l.startswith(head):
            for j in range(i + 1, len(lines)):
                if lines[j] == '}':
                    out = '\n'.join(lines[i:j + 1]) + '\n'
                    return out if not rename else out.replace(rename[0], rename[1])
    raise SystemExit('cannot lift ' + head)
def lift(rel, head, rename=None): return lift_from(src(rel), head, rename)
def one_liner(text, head):
    for l in text.split('\n'):
        if l.startswith(head): return l + '\n'
    raise SystemExit('cannot find ' + head)
def old_source(rel):
    r = subprocess.run(['git', 'show', 'HEAD:TransmitterCode/' + rel], cwd=ROOT, capture_output=True, text=True)
    if r.returncode: raise SystemExit('git show failed: ' + r.stderr)
    return r.stdout
def build_run(name, prog, defines=()):
    with tempfile.TemporaryDirectory() as d:
        cpp = os.path.join(d, name + '.cpp'); open(cpp, 'w').write(prog)
        r = subprocess.run(['clang++', '-std=c++17', '-O1', '-w'] + ['-D' + x for x in defines] + ['-o', os.path.join(d, name), cpp], capture_output=True, text=True)
        if r.returncode:
            print(r.stderr[:4000]); raise SystemExit(name + ' does not compile on the host')
        r = subprocess.run([os.path.join(d, name)], capture_output=True, text=True)
        sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
        return r.returncode, r.stdout

defs1 = src('include/1Definitions.h'); sdc = src('include/SDcard.h'); util = src('include/Utilities.h'); sw = src('include/Switches.h')
sdc_old = old_source('include/SDcard.h'); fg = src('include/FlightGuard.h'); fg_old = old_source('include/FlightGuard.h')
DEFS = '\n'.join(l for l in defs1.split('\n') if re.match(r'#define (TX_EXT_MAGIC|TX_EXT_MAGIC2|TX_EXT_MAGIC3|TX_EXT_MAGIC4|CURVE_POINTS_MAX|CURVE_STORE_MAX|CURVE_UNSET|BANKS_USED|BANKS_IN_FILE|BANK_NAMES_N|CHANNELSUSED|MAXMODELNUMBER|TXSIZE|MODELSIZE|DEFAULT_EXPO|EXPONENTIALCURVES|MAXMIXES|BYTESPERMACRO|MAXMACROS) ', l)) + '\n'
DEFS += '\n'.join(l for l in sdc.split('\n') if l.startswith('#define MODEL_EXT_OFFSET_B113 ') or l.startswith('#define MODEL_EXT2_') or l.startswith('#define TX_EXT_MAGIC7') or l.startswith('#define TX_EXT_MAGIC8') or l.startswith('#define BANKS_BLOCK_LEN')) + '\n'
for want in ('BANKS_USED 6', 'BANKS_IN_FILE 4', 'BANK_NAMES_N 38', 'BANKS_BLOCK_LEN', 'TX_EXT_MAGIC7 0xC7', 'TX_EXT_MAGIC8 0xC8', 'MODELSIZE 1024 * 3'):
    check(want in DEFS, 'the define ' + want)
COMMON = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>
#include <map>
#define FLASHMEM
#define FASTRUN
#define DMAMEM
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
''' + DEFS + r'''
static uint32_t seed = 20261019;
static uint32_t rnd() { seed = seed * 1103515245u + 12345u; return seed >> 8; }
'''
# ------------------------------------------------------------------------------------------------------------ 1. the model file
P1 = COMMON + r'''
int Trims[BANKS_USED + 1][CHANNELSUSED + 1];
uint8_t Exponential[BANKS_USED + 1][CHANNELSUSED + 1], InterpolationTypes[BANKS_USED + 1][CHANNELSUSED + 1], ServoSpeed[BANKS_USED + 1][CHANNELSUSED + 1];
uint8_t CurvePointCount[CHANNELSUSED + 1], CurvePoint[BANKS_USED + 1][CHANNELSUSED + 1][CURVE_POINTS_MAX], CurveStore[BANKS_USED + 1][CHANNELSUSED + 1][CURVE_STORE_MAX];
uint8_t BanksInUse[BANKS_USED] = {0, 1, 2, 3, 32, 33}, DualRateRate[BANKS_USED + 1];
char ModelName[40] = "Havok"; uint32_t ModelNumber = 1;
bool SixBanks = false, SingleModelFlag = false; uint8_t MaxRangeNarrow = 0;
// the card, as SdFat behaves (test_curve_points): a seek beyond the end fails and the position stays; a write at the end appends
static std::vector<uint8_t> card; static long FileCheckSum = 0; static bool DoingCheckSm = false; static int StartLocation = 0, SDCardAddress = 0;
static size_t cardPos = 0; static int seekWriteFails = 0;
struct FakeFile { size_t size() { return card.size(); } };
static FakeFile ModelsFileNumber;
static bool cardSeek(size_t a) { if (a > card.size()) return false; cardPos = a; return true; }
static uint8_t SDRead8BITS(int a) { cardSeek((size_t) a); const uint8_t r = cardPos < card.size() ? card[cardPos++] : 255; if (!DoingCheckSm) FileCheckSum += r * (a + 1); return r; }
static void SDUpdate8BITS(int a, uint8_t v) { if (!cardSeek((size_t) a)) ++seekWriteFails; if (!DoingCheckSm) FileCheckSum += v * (a + 1); if (cardPos >= card.size()) card.resize(cardPos + 1, 0); card[cardPos++] = v; }
// the banks files
static std::map<int, std::vector<uint8_t>> bankFiles; static int bankWrites = 0, bankReads = 0;
bool BanksFileRead(uint8_t slot, uint8_t *blk, int n) { ++bankReads; auto it = bankFiles.find(slot); if (it == bankFiles.end() || (int) it->second.size() != n) return false; memcpy(blk, it->second.data(), n); return true; }
bool BanksFileWrite(uint8_t slot, const uint8_t *blk, int n) { ++bankWrites; bankFiles[slot] = std::vector<uint8_t>(blk, blk + n); return true; }
static bool CurveCountOk(uint8_t n) { return n == 3 || n == 5 || n == 7 || n == 9; }
''' + lift('include/Utilities.h', 'uint8_t CurveN(uint8_t ch)') + 'uint8_t CurveMid(uint8_t n) { return (n - 1) / 2; }\n' \
   + lift('include/Utilities.h', 'uint8_t CurveStorePos(uint8_t n, uint8_t k)') + lift('include/Utilities.h', 'void CurveStoreSync(uint8_t b, uint8_t ch)') + lift('include/Utilities.h', 'void CurveStoreClear(uint8_t b, uint8_t ch)') \
   + lift('include/SDcard.h', 'static uint8_t Ext2Sum(') + one_liner(sdc, 'static uint8_t BanksSlot()') \
   + lift('include/SDcard.h', 'FLASHMEM void BanksCopy(') + lift('include/SDcard.h', 'FLASHMEM static void BanksFromFour()') \
   + lift('include/SDcard.h', 'FLASHMEM static int BanksBlockBuild(') + lift('include/SDcard.h', 'FLASHMEM static bool BanksBlockTake(') \
   + lift('include/SDcard.h', 'FLASHMEM void SixBanksSet(') + lift('include/SDcard.h', 'void ReadModelExtension()') + lift('include/SDcard.h', 'void SaveModelExtension()') \
   + 'static uint8_t DualRateValue = 100; static uint16_t ReversedChannelBITS = 0; static int savesSeen = 0, seenClears = 0; static void SaveOneModel(uint32_t) { ++savesSeen; } static void GetCurveDots(uint8_t, uint16_t) {} static void AdjSeenClear() { ++seenClears; } static uint8_t BanksCount() { return SixBanks ? 6 : 4; }\n' + lift('include/Utilities.h', 'void CurveSetStraight(uint8_t b, uint8_t ch, uint8_t lo, uint8_t hi)') \
   + '#define MINMICROS 500\n#define MAXMICROS 2500\nstatic uint32_t millis() { return 0; }\nstatic uint8_t SourceOfOutput(uint8_t o) { return o; }\nstatic uint16_t CurveMicros(uint8_t d) { const uint32_t lo = MaxRangeNarrow ? 945 : 500, hi = MaxRangeNarrow ? 2055 : 2500; return (uint16_t)(lo + ((uint32_t)d * (hi - lo) + 90) / 180); }\n' \
   + lift('include/RF_Adjust.h', 'FLASHMEM static int AdjFcUs(') + 'static int AdjTxBankUs(int ch0, int bank) { int v = CurveMicros(CurvePoint[bank][ch0][0]); if (ReversedChannelBITS & (1 << ch0)) v = MAXMICROS - (v - MINMICROS); return AdjFcUs((uint16_t)v); }\n' \
   + one_liner(src('include/RF_Adjust.h'), 'static uint32_t AdjSeenHoldUntil') + one_liner(src('include/RF_Adjust.h'), 'struct AdjUndoRec') + one_liner(src('include/RF_Adjust.h'), '#define ADJ_UNDO_MAX') + one_liner(src('include/RF_Adjust.h'), 'DMAMEM static AdjUndoRec AdjUndo') + one_liner(src('include/RF_Adjust.h'), 'static int AdjUndoN') \
   + lift('include/RF_Adjust.h', 'FLASHMEM static void AdjUndoKeep(') + lift('include/RF_Adjust.h', 'FLASHMEM static void AdjModelRevert(') + lift('include/RF_Adjust.h', 'FLASHMEM static void AdjModelCommit(') \
   + lift('include/RF_Adjust.h', 'FLASHMEM static int AdjHeightUs(') + lift('include/RF_Adjust.h', 'FLASHMEM static int AdjHeightFor(') + lift('include/RF_Adjust.h', 'FLASHMEM static void AdjSpaceBanks(') \
   + lift_from(sdc_old, 'void ReadModelExtension()', ('void ReadModelExtension()', 'void ReadModelExtensionOld()')) \
   + lift_from(sdc_old, 'void SaveModelExtension()', ('void SaveModelExtension()', 'void SaveModelExtensionOld()')) + r'''
// helpers
static const int SEQ = 2111;   // the checked sequence and its checksum, as measured on a real models.dat (19 Oct 2026)
static void randomCurve(int b, int ch, int n) { CurvePointCount[ch] = (uint8_t) n; for (int k = 0; k < CURVE_POINTS_MAX; ++k) CurvePoint[b][ch][k] = k < n ? (uint8_t) (rnd() % 181) : 0; CurveStoreClear(b, ch); CurveStoreSync(b, ch); for (int s = 0; s <= 8; s += 2) if (CurveStore[b][ch][s] == CURVE_UNSET) CurveStore[b][ch][s] = (uint8_t) (rnd() % 181); }   // (the five of old are always in the store: a model starts from them)
static void randomModel(bool six) {   // a model in memory: counts, curves in every bank, trims etc. of banks 5 and 6 random when six
    for (int ch = 0; ch < CHANNELSUSED; ++ch) {
        const int n = (int[]){3, 5, 5, 7, 9}[rnd() % 5];
        for (int b = 1; b <= BANKS_USED; ++b) randomCurve(b, ch, n);
        if (rnd() % 3 == 0) { const int b = 1 + rnd() % BANKS_USED; for (int tries = 0; tries < 40; ++tries) { const int s = rnd() % CURVE_STORE_MAX; if (CurveStore[b][ch][s] == CURVE_UNSET) { CurveStore[b][ch][s] = (uint8_t) (rnd() % 181); break; } } }   // (a height remembered for another count: a slot the count does not use)
    }
    for (int b = 0; b <= BANKS_USED; ++b) for (int i = 0; i < CHANNELSUSED + 1; ++i) {
        Trims[b][i] = 40 + rnd() % 81; ServoSpeed[b][i] = 1 + rnd() % 100; Exponential[b][i] = 1 + rnd() % 200; InterpolationTypes[b][i] = rnd() % 3;
    }
    for (int b = 0; b < BANKS_USED; ++b) { BanksInUse[b] = rnd() % BANK_NAMES_N; DualRateRate[b] = rnd() % 4; }
    MaxRangeNarrow = rnd() % 2; SixBanks = six;
}
struct Snap { int tr[2][CHANNELSUSED]; uint8_t sp[2][CHANNELSUSED], ex[2][CHANNELSUSED], it[2][CHANNELSUSED], st[2][CHANNELSUSED][CURVE_STORE_MAX], pt[2][CHANNELSUSED][CURVE_POINTS_MAX], nm[2], dr[2]; uint8_t four[4][CHANNELSUSED + 1][CURVE_POINTS_MAX]; uint8_t range; };
static Snap snap() { Snap s; for (int b = 0; b < 2; ++b) { s.nm[b] = BanksInUse[4 + b]; s.dr[b] = DualRateRate[4 + b]; for (int c = 0; c < CHANNELSUSED; ++c) { s.tr[b][c] = Trims[5 + b][c]; s.sp[b][c] = ServoSpeed[5 + b][c]; s.ex[b][c] = Exponential[5 + b][c]; s.it[b][c] = InterpolationTypes[5 + b][c]; memcpy(s.st[b][c], CurveStore[5 + b][c], CURVE_STORE_MAX); memcpy(s.pt[b][c], CurvePoint[5 + b][c], CURVE_POINTS_MAX); } } memcpy(s.four, &CurvePoint[1][0][0], sizeof(s.four)); s.range = MaxRangeNarrow; return s; }
static bool sameFiveSix(const Snap &s) { const Snap now = snap(); return memcmp(&s, &now, offsetof(Snap, four)) == 0; }
static bool sameFour(const Snap &s) { return memcmp(s.four, &CurvePoint[1][0][0], sizeof(s.four)) == 0 && s.range == MaxRangeNarrow; }
static void scramble56() { for (int b = 5; b <= 6; ++b) for (int c = 0; c < CHANNELSUSED + 1; ++c) { Trims[b][c] = 77; ServoSpeed[b][c] = 33; Exponential[b][c] = 44; InterpolationTypes[b][c] = 1; memset(CurveStore[b][c], 3, CURVE_STORE_MAX); memset(CurvePoint[b][c], 4, CURVE_POINTS_MAX); } BanksInUse[4] = BanksInUse[5] = 9; DualRateRate[4] = DualRateRate[5] = 2; }
static void record(int fileSize, int start) { card.assign(fileSize, 0); for (int i = 0; i < SEQ; ++i) card[start + i] = (uint8_t) rnd(); StartLocation = start; SDCardAddress = start + SEQ; FileCheckSum = 0; seekWriteFails = 0; }
static void freshMod() { card.clear(); for (int i = 0; i < SEQ; ++i) card.push_back((uint8_t) rnd()); StartLocation = 0; SDCardAddress = SEQ; FileCheckSum = 0; seekWriteFails = 0; SingleModelFlag = true; }
static bool fourTwins() { for (int b = 5; b <= 6; ++b) for (int c = 0; c < CHANNELSUSED + 1; ++c) if (Trims[b][c] != Trims[4][c] || ServoSpeed[b][c] != ServoSpeed[4][c] || Exponential[b][c] != Exponential[4][c] || InterpolationTypes[b][c] != InterpolationTypes[4][c] || memcmp(CurveStore[b][c], CurveStore[4][c], CURVE_STORE_MAX) || memcmp(CurvePoint[b][c], CurvePoint[4][c], CURVE_POINTS_MAX)) return false; return true; }
int main()
{
    CHECK(BANKS_BLOCK_LEN == 582);
    CHECK(SEQ + 3 + MODEL_EXT2_LEN + 4 <= MODELSIZE);                 // the header after the curves' block is still inside the record
    CHECK(SEQ + 3 + MODEL_EXT2_LEN + 4 + BANKS_BLOCK_LEN > MODELSIZE); // (and the block would not be: hence the file of its own)
    // ---- a. four banks: B130 writes what B129 wrote, in a fresh .MOD and in a models.dat record, once and again
    int same = 0, trials = 0;
    for (int t = 0; t < 120; ++t) {
        randomModel(false);
        const bool mod = t % 2 == 0;
        auto fill = [&]() { if (mod) freshMod(); else { SingleModelFlag = false; record(TXSIZE + MAXMODELNUMBER * MODELSIZE, TXSIZE + (t % 7) * MODELSIZE); } };
        const uint32_t s0 = seed;
        fill(); SaveModelExtensionOld(); if (t % 3 == 0) { SDCardAddress = StartLocation + SEQ; SaveModelExtensionOld(); } std::vector<uint8_t> a = card;
        seed = s0; fill(); SaveModelExtension(); if (t % 3 == 0) { SDCardAddress = StartLocation + SEQ; SaveModelExtension(); } std::vector<uint8_t> b = card;
        ++trials; if (a == b) ++same; else if (same + 3 > trials) fprintf(stderr, "differs: trial %d (%s), sizes %zu %zu\n", t, mod ? ".MOD" : "models.dat", a.size(), b.size());
        CHECK(seekWriteFails == 0 && bankWrites == 0);
        // and B130 reads B129's bytes as B129 does (what the extension holds is disturbed first: the range, banks 5 and 6, and
        // the curves when a curves' block follows the header - the five of old come from the sequence, not from here)
        Snap s = snap();
        const bool hasCurves = card.size() > (size_t) (StartLocation + SEQ + 4) && card[StartLocation + SEQ + 3] == TX_EXT_MAGIC;
        auto disturb = [&]() { MaxRangeNarrow = !s.range; scramble56(); if (hasCurves) memset(&CurvePoint[1][0][0], 0, sizeof(s.four)); };
        disturb(); SDCardAddress = StartLocation + SEQ; ReadModelExtension();
        if (!sameFour(s) && t < 6) { int d = 0, first = -1; for (int i = 0; i < (int) sizeof(s.four); ++i) if (((uint8_t *) s.four)[i] != (&CurvePoint[1][0][0])[i]) { ++d; if (first < 0) first = i; } fprintf(stderr, "trial %d %s hasCurves %d range %d/%d points differ %d first %d (bank %d ch %d k %d) count %d\n", t, mod ? ".MOD" : "models.dat", hasCurves, s.range, MaxRangeNarrow, d, first, first / (17 * 9) + 1, (first / 9) % 17, first % 9, CurveN((first / 9) % 17)); }
        CHECK(sameFour(s) && !SixBanks && fourTwins());
        disturb(); SDCardAddress = StartLocation + SEQ; ReadModelExtensionOld();
        CHECK(sameFour(s));
    }
    printf("four banks: %d of %d saves byte for byte B129's\n", same, trials);
    CHECK(same == trials);
    // ---- b. a six-bank .MOD: banks 5 and 6 in-line; back whole; B129 takes the curves and ignores the rest
    for (int t = 0; t < 60; ++t) {
        randomModel(true); freshMod();
        SaveModelExtension();
        const bool curves = card.size() > SEQ + 3 + 4 + BANKS_BLOCK_LEN;
        CHECK(card.size() == (size_t) (SEQ + 3 + (curves ? MODEL_EXT2_LEN : 0) + 4 + BANKS_BLOCK_LEN) && seekWriteFails == 0 && bankWrites == 0);
        Snap s = snap(); scramble56(); SixBanks = false;
        SDCardAddress = SEQ; ReadModelExtension();
        CHECK(SixBanks && sameFiveSix(s) && sameFour(s));
        scramble56(); MaxRangeNarrow = !s.range; if (curves) memset(&CurvePoint[1][0][0], 0, sizeof(s.four)); SDCardAddress = SEQ; ReadModelExtensionOld();
        CHECK(sameFour(s));   // (B129: the four banks' curves and the range, nothing else)
        // the in-line block damaged: the model is read with four banks' twins, not garbage
        const size_t at = card.size() - 1; card[at] ^= 1; SixBanks = false; scramble56(); SDCardAddress = SEQ; ReadModelExtension();
        CHECK(SixBanks && fourTwins()); card[at] ^= 1;
        // the header's sum damaged: four banks
        const size_t hdr = SEQ + 3 + (curves ? MODEL_EXT2_LEN : 0); CHECK(card[hdr] == TX_EXT_MAGIC && card[hdr + 1] == TX_EXT_MAGIC7 && card[hdr + 2] == 1);
        card[hdr + 3] ^= 0x40; SDCardAddress = SEQ; ReadModelExtension(); CHECK(!SixBanks && fourTwins()); card[hdr + 3] ^= 0x40;
    }
    // ---- c. a six-bank model in models.dat: the banks file and the header
    for (int t = 0; t < 40; ++t) {
        randomModel(true); SingleModelFlag = false; const int slot = 1 + rnd() % MAXMODELNUMBER;
        snprintf(ModelName, sizeof(ModelName), "Model %d", t);
        record(TXSIZE + MAXMODELNUMBER * MODELSIZE, TXSIZE + (slot - 1) * MODELSIZE);
        bankFiles.clear(); bankWrites = 0;
        SaveModelExtension();
        CHECK(bankWrites == 1 && bankFiles.count(slot) == 1 && bankFiles[slot].size() == BANKS_BLOCK_LEN && seekWriteFails == 0);
        CHECK(memcmp(bankFiles[slot].data() + 3, ModelName, strlen(ModelName) + 1) == 0);   // named inside
        const bool curves6 = card[StartLocation + SEQ + 3] == TX_EXT_MAGIC && card[StartLocation + SEQ + 4] == TX_EXT_MAGIC4;
        const size_t hdr = StartLocation + SEQ + 3 + (curves6 ? MODEL_EXT2_LEN : 0);   // the header: after the curves' block when there is one
        CHECK(card[hdr] == TX_EXT_MAGIC && card[hdr + 1] == TX_EXT_MAGIC7 && card[hdr + 2] == 1 && card[hdr + 3] == (uint8_t) (TX_EXT_MAGIC7 + 1));
        Snap s = snap();
        scramble56(); SixBanks = false; SDCardAddress = StartLocation + SEQ; ReadModelExtension();
        CHECK(SixBanks && sameFiveSix(s) && sameFour(s));
        const size_t size = card.size(); CHECK(size == (size_t) (TXSIZE + MAXMODELNUMBER * MODELSIZE));   // (never beyond the record)
        // the file's checksum wrong: twins of bank 4, named after the four's pattern
        bankFiles[slot][BANKS_BLOCK_LEN - 1] ^= 1; scramble56(); SDCardAddress = StartLocation + SEQ; ReadModelExtension();
        CHECK(SixBanks && fourTwins() && BanksInUse[4] == (BanksInUse[3] == 3 ? 32 : BanksInUse[3] == 31 ? 36 : 34) && BanksInUse[5] == BanksInUse[4] + 1 && DualRateRate[4] == 0);
        bankFiles[slot][BANKS_BLOCK_LEN - 1] ^= 1;
        // another model's name in the file: not taken
        char was[40]; strcpy(was, ModelName); strcpy(ModelName, "Someone else"); scramble56(); SDCardAddress = StartLocation + SEQ; ReadModelExtension();
        CHECK(SixBanks && fourTwins()); strcpy(ModelName, was);
        // no file: not taken
        auto keep = bankFiles[slot]; bankFiles.erase(slot); scramble56(); SDCardAddress = StartLocation + SEQ; ReadModelExtension();
        CHECK(SixBanks && fourTwins()); bankFiles[slot] = keep;
        // turned off: the header says four, the file stays; on again: taken back
        SDCardAddress = StartLocation + SEQ; ReadModelExtension(); CHECK(sameFiveSix(s));
        SixBanks = false; bankWrites = 0; SDCardAddress = StartLocation + SEQ; SaveModelExtension();
        CHECK(bankWrites == 0 && bankFiles.count(slot) == 1 && card[hdr + 2] == 0 && card[hdr + 3] == (uint8_t) (TX_EXT_MAGIC7 + 0));
        scramble56(); SDCardAddress = StartLocation + SEQ; ReadModelExtension(); CHECK(!SixBanks && fourTwins());
        ModelNumber = slot; SixBanksSet(true); CHECK(SixBanks && sameFiveSix(s));
        bankFiles.erase(slot); SixBanks = false; SixBanksSet(true); CHECK(SixBanks && fourTwins());
        SixBanksSet(false); CHECK(!SixBanks);
        (void) size;
    }
    // ---- d. the Adjust page's spacing (B132; B141: by what the flight controller sees): the bank line's channel flat in every
    // bank, each in the middle of its zone - on the wide range 0, 63, 81, 99, 117, 180 degrees for six (988, 1193 ... 2012 us
    // at the flight controller), 0, 75, 105, 180 for four; the card untouched until AdjModelCommit; AdjModelRevert puts the
    // channel back
    for (int six = 0; six < 2; ++six) {
        randomModel(six); SixBanks = six; MaxRangeNarrow = 0; const int ch = 6; savesSeen = seenClears = 0; AdjUndoN = 0; AdjModelDirty = false;
        uint8_t was[BANKS_USED + 1][CURVE_POINTS_MAX]; for (int b = 0; b <= BANKS_USED; ++b) memcpy(was[b], CurvePoint[b][ch], CURVE_POINTS_MAX);
        char note[200]; AdjSpaceBanks(ch, note, sizeof(note));
        CHECK(strcmp(note, six ? "Channel 7 set bank by bank: 988, 1193, 1398, 1602, 1807, 2012 us, the middle of each zone (0, 63, 81, 99, 117, 180 degrees)." : "Channel 7 set bank by bank: 988, 1330, 1670, 2012 us, the middle of each zone (0, 75, 105, 180 degrees).") == 0);
        const int n = six ? 6 : 4; const int want4[] = {0, 75, 105, 180}, want6[] = {0, 63, 81, 99, 117, 180};
        for (int b = 1; b <= n; ++b) for (uint8_t k = 0; k < CurveN(ch); ++k) CHECK(CurvePoint[b][ch][k] == (six ? want6 : want4)[b - 1]);
        CHECK(savesSeen == 0 && seenClears == 2 && AdjModelDirty && AdjUndoN == 1 && AdjUndo[0].ch == ch);
        if (!six) for (uint8_t k = 0; k < CurveN(ch); ++k) CHECK(CurvePoint[5][ch][k] == was[5][k] && CurvePoint[6][ch][k] == was[6][k]);   // (banks 5 and 6 untouched with four)
        // B139: a REVERSED channel is spaced the other way round (the reversal is applied after the curve), so the wire still rises from bank 1
        ReversedChannelBITS = (uint16_t)(1 << ch); savesSeen = seenClears = 0; AdjSpaceBanks(ch, note, sizeof(note));
        CHECK(strstr(note, six ? "(180, 117, 99, 81, 63, 0 degrees, reversed)." : "(180, 105, 75, 0 degrees, reversed).") != nullptr && strncmp(note, "Channel 7 set bank by bank: 988, ", 33) == 0);
        for (int b = 1; b <= n; ++b) for (uint8_t k = 0; k < CurveN(ch); ++k) CHECK(CurvePoint[b][ch][k] == 180 - (six ? want6 : want4)[b - 1]);
        CHECK(savesSeen == 0 && seenClears == 2 && AdjUndoN == 1);   // (kept once per channel and page)
        ReversedChannelBITS = 0;
        for (int c = 0; c < CHANNELSUSED; ++c) if (c != ch) for (uint8_t k = 0; k < CurveN(c); ++k) CHECK(CurvePoint[1][c][k] == CurvePoint[1][c][k]);
        // leaving without saving: the channel back as it was, in every bank; the card not written
        AdjModelRevert();
        for (int b = 0; b <= BANKS_USED; ++b) for (uint8_t k = 0; k < CurveN(ch); ++k) CHECK(CurvePoint[b][ch][k] == was[b][k]);
        CHECK(savesSeen == 0 && !AdjModelDirty && AdjUndoN == 0);
        // saved: the card written once, the undo forgotten
        AdjSpaceBanks(ch, note, sizeof(note)); CHECK(AdjModelDirty); AdjModelCommit(); CHECK(savesSeen == 1 && !AdjModelDirty && AdjUndoN == 0 && CurvePoint[2][ch][0] == (six ? 63 : 75));
        // another model loaded meanwhile: nothing of it is touched
        AdjSpaceBanks(ch, note, sizeof(note)); ModelNumber = 2; savesSeen = 0; AdjModelRevert(); CHECK(CurvePoint[2][ch][0] == (six ? 63 : 75) && AdjUndoN == 0); ModelNumber = 1;
        // the narrow range (945 to 2055): the middles by the same rule
        MaxRangeNarrow = 1; AdjSpaceBanks(ch, note, sizeof(note)); CHECK(strstr(note, six ? "(0, 41, 74, 106, 139, 180 degrees)." : "(0, 63, 117, 180 degrees).") != nullptr); MaxRangeNarrow = 0; AdjModelRevert();
    }
    printf("test_banks (file): %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
# ------------------------------------------------------------------------------------------------------------ 2. the switches
P2 = COMMON + r'''
static uint8_t pos[9]; static uint8_t GetSwitchPosition(uint8_t n) { return n >= 1 && n <= 8 ? pos[n] : 0; }
static uint8_t Bank = 1, BankSwitch = 4, Autoswitch = 1, CurrentMode = 0, ParametersToBeSentPointer = 0; static bool MotorEnabled = false, BlockBankChanges = false, SixBanks = false;
#define NORMAL 0
static bool CopyBankRunning() { return false; } static bool EasyHoldsBanks() { return false; } static uint32_t millis() { return 1000; }
''' + one_liner(sw, 'uint8_t BanksCount()') + lift('include/Switches.h', 'uint8_t BankOf123()') + one_liner(sw, 'static uint8_t UpperBank()') \
   + lift('include/Switches.h', 'void ReadBankSwitch()') + lift('include/Switches.h', 'void ReadAutoAndMotorSwitch()') + r'''
int main()
{
    for (int six = 0; six < 2; ++six) for (int a = 1; a <= 3; ++a) for (int bsw = 0; bsw <= 3; ++bsw) {
        SixBanks = six; BankSwitch = bsw ? 4 : 0; pos[4] = (uint8_t) bsw; pos[1] = (uint8_t) a; Autoswitch = 1; BlockBankChanges = false; Bank = 99; MotorEnabled = !(a != 3);
        ReadBankSwitch(); ReadAutoAndMotorSwitch();
        const int b123 = bsw ? bsw : 1;
        const int want = a == 1 ? b123 : (six ? 3 + b123 : 4);
        CHECK(Bank == want);
        CHECK(MotorEnabled == (a != 3));
        CHECK(BanksCount() == (six ? 6 : 4));
        // a block on bank changes (a transfer running): the bank stays, the motor still follows the switch
        BlockBankChanges = true; Bank = 2; MotorEnabled = (a == 3); ReadBankSwitch(); ReadAutoAndMotorSwitch();
        CHECK(Bank == 2 && MotorEnabled == (a != 3));
    }
    printf("test_banks (switches): %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
# ------------------------------------------------------------------------------------------------------------ 3. the buddy byte
bw = src('include/BuddyWireless.h')
enc = '\n'.join(l for l in bw.split('\n') if re.match(r'\s*\*C1 (=|\|=) ', l) and 'C1 = 1;' not in l)
dec = '\n'.join(l for l in bw.split('\n') if re.match(r'\s*(DualRateInUse|Bank|MotorEnabled|SafetyON) = .*C1', l))
check(enc.count('\n') == 4 and dec.count('\n') == 3, 'the buddy byte: five lines encode, four decode (%d, %d)' % (enc.count('\n'), dec.count('\n')))
P3 = COMMON + r'''
static uint8_t Bank = 1, DualRateInUse = 1; static bool MotorEnabled = false, SafetyON = false, SixBanks = false;
static uint8_t BanksCount() { return SixBanks ? 6 : 4; }
static void encode(uint8_t *C1) {
''' + enc + r'''
}
static void decode(uint8_t C1) {
''' + dec + r'''
    if (Bank > BanksCount())
        Bank = 4;
}
int main()
{
    for (int six = 0; six < 2; ++six) for (int b = 1; b <= 6; ++b) for (int r = 1; r <= 4; ++r) for (int m = 0; m < 2; ++m) for (int s = 0; s < 2; ++s) {
        SixBanks = true; Bank = (uint8_t) b; DualRateInUse = (uint8_t) r; MotorEnabled = m; SafetyON = s;
        uint8_t C1 = 0xFF; encode(&C1);
        CHECK((C1 & 1) == 0);   // (bit 0 = the pupil has the switches: never set here)
        SixBanks = six; Bank = 0; DualRateInUse = 0; MotorEnabled = !m; SafetyON = !s; decode(C1);
        CHECK(Bank == (six || b <= 4 ? b : 4) && DualRateInUse == r && MotorEnabled == (bool) m && SafetyON == (bool) s);
    }
    printf("test_banks (buddy): %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
# ------------------------------------------------------------------------------------------------------------ 4. the fingerprint
crc = lift('lib/LdrcLink/LdrcLink.cpp', 'uint32_t crc32(const uint8_t *data, size_t n, uint32_t crc)')
FP_DECL = r'''
namespace ldrc {
''' + crc + r'''
}
#define Ch9_SW 4
#define CONTROL_FINGERPRINT_VERSION 1
int Trims[7][CHANNELSUSED + 1]; uint8_t ServoSpeed[7][CHANNELSUSED + 1], Exponential[7][CHANNELSUSED + 1], InterpolationTypes[7][CHANNELSUSED + 1];
uint8_t CurvePoint[7][CHANNELSUSED + 1][CURVE_POINTS_MAX], CurvePointCount[CHANNELSUSED + 1], Mixes[MAXMIXES + 1][17], SubTrims[CHANNELSUSED + 1], InputTrim[4], InPutStick[CHANNELSUSED], DualRateRate[7];
uint8_t MacrosBuffer[MAXMACROS][BYTESPERMACRO], MotorChannelZero, MotorChannel, Drate1, Drate2, Drate3, DualRateChannels[8], BanksInUse[6], ChannelOutPut[16], ServoFrequency[11], ServoCentrePulse[11], RotorFlight_V, SticksMode, SwitchNumber[8], TrimNumber[8], BankSwitch, Autoswitch, TopChannelSwitch[12], BuddySwitch, DualRatesSwitch, SafetySwitch, FrontSwitchUnused, MaxRangeNarrow, ArmingChannel, BuddyControlled;
uint16_t ChannelMin[CHANNELSUSED], ChannelMidLow[CHANNELSUSED], ChannelCentre[CHANNELSUSED], ChannelMidHi[CHANNELSUSED], ChannelMax[CHANNELSUSED], ReversedChannelBITS, TrimMultiplier;
bool CopyTrimsToAll, FailSafeChannel[CHANNELSUSED], LinkRatesToBanks, UseMotorKill, SwitchReversed[8], SixBanks = false;
uint8_t CurveN(uint8_t ch) { const uint8_t n = CurvePointCount[ch]; return (n == 3 || n == 7 || n == 9) ? n : 5; }
uint8_t CurveMid(uint8_t n) { return (n - 1) / 2; }
''' + lift('include/Utilities.h', 'void CurveLegacyFive(uint8_t b, uint8_t ch, uint8_t *five)') + r'''
static void fill(uint32_t s, bool six) {   // the same setup from the same seed, whatever the firmware; banks 5 and 6 garbage unless six
    seed = s;
    auto r8 = [&]() { return (uint8_t) rnd(); };
    for (int b = 0; b < 7; ++b) for (int i = 0; i < CHANNELSUSED + 1; ++i) { Trims[b][i] = r8(); ServoSpeed[b][i] = r8(); Exponential[b][i] = r8(); InterpolationTypes[b][i] = r8(); for (int k = 0; k < CURVE_POINTS_MAX; ++k) CurvePoint[b][i][k] = r8(); }
    for (int i = 0; i < CHANNELSUSED + 1; ++i) CurvePointCount[i] = (uint8_t) ((int[]){3, 5, 7, 9}[rnd() % 4]);
    for (int j = 0; j <= MAXMIXES; ++j) for (int i = 0; i < 17; ++i) Mixes[j][i] = r8();
    for (int i = 0; i < CHANNELSUSED + 1; ++i) SubTrims[i] = r8();
    for (int i = 0; i < 4; ++i) InputTrim[i] = r8();
    for (int i = 0; i < CHANNELSUSED; ++i) { InPutStick[i] = r8(); FailSafeChannel[i] = rnd() & 1; ChannelMin[i] = (uint16_t) rnd(); ChannelMidLow[i] = (uint16_t) rnd(); ChannelCentre[i] = (uint16_t) rnd(); ChannelMidHi[i] = (uint16_t) rnd(); ChannelMax[i] = (uint16_t) rnd(); ChannelOutPut[i] = r8(); }
    for (int i = 0; i < 7; ++i) DualRateRate[i] = r8();
    for (int j = 0; j < MAXMACROS; ++j) for (int i = 0; i < BYTESPERMACRO; ++i) MacrosBuffer[j][i] = r8();
    MotorChannelZero = r8(); MotorChannel = r8(); Drate1 = r8(); Drate2 = r8(); Drate3 = r8(); for (int i = 0; i < 8; ++i) DualRateChannels[i] = r8();
    for (int i = 0; i < 6; ++i) BanksInUse[i] = r8();
    for (int i = 0; i < 11; ++i) { ServoFrequency[i] = r8(); ServoCentrePulse[i] = r8(); }
    RotorFlight_V = r8(); SticksMode = r8(); for (int i = 0; i < 8; ++i) { SwitchNumber[i] = r8(); TrimNumber[i] = r8(); SwitchReversed[i] = rnd() & 1; }
    BankSwitch = r8(); Autoswitch = r8(); for (int i = 0; i < 12; ++i) TopChannelSwitch[i] = r8(); BuddySwitch = r8(); DualRatesSwitch = r8(); SafetySwitch = r8();
    FrontSwitchUnused = r8(); MaxRangeNarrow = rnd() & 1; ArmingChannel = r8(); BuddyControlled = r8(); ReversedChannelBITS = (uint16_t) rnd(); TrimMultiplier = (uint16_t) (rnd() % 26);
    CopyTrimsToAll = rnd() & 1; LinkRatesToBanks = rnd() & 1; UseMotorKill = rnd() & 1;
    SixBanks = six;
}
'''
def fp_program(text, six_too):
    body = lift_from(text, 'uint32_t ControlFingerprint()')
    fpdef = '\n'.join(l for l in text.split('\n') if l.startswith('static uint32_t FingerprintSoFar') ) + '\n' + lift_from(text, 'static inline void Fp(int32_t v)')
    return COMMON + FP_DECL + fpdef + body + r'''
int main()
{
    for (uint32_t s = 1; s <= 8; ++s) { fill(s, false); printf("%u %08X\n", s, (unsigned) ControlFingerprint()); }
''' + (r'''    for (uint32_t s = 1; s <= 8; ++s) { fill(s, true); printf("six %u %08X\n", s, (unsigned) ControlFingerprint()); }
''' if six_too else '') + r'''
    return 0;
}
'''
# ------------------------------------------------------------------------------------------------------------ run
rc1, _ = build_run('t_file', P1); check(rc1 == 0, 'the file')
rc2, _ = build_run('t_switches', P2); check(rc2 == 0, 'the switches')
rc3, _ = build_run('t_buddy', P3); check(rc3 == 0, 'the buddy byte')
old_text = fg_old.replace('#define BANKS_USED', '#define BANKS_USED_unused')   # (B129's loops say BANKS_USED + 1: four there)
rc4, out_old = build_run('t_fp_old', fp_program(old_text, False).replace('#define BANKS_USED 6', '#define BANKS_USED 4'))   # (B129's world: four)
rc5, out_new = build_run('t_fp_new', fp_program(fg, True))
four_old = [l for l in out_old.split('\n') if l and not l.startswith('six')]
four_new = [l for l in out_new.split('\n') if l and not l.startswith('six')]
six_new = [l.split()[2] for l in out_new.split('\n') if l.startswith('six')]
check(rc4 == 0 and rc5 == 0 and len(four_old) == 8 and four_old == four_new, 'the fingerprint of a four-bank setup: B130 gives B129\'s number (%s vs %s)' % (four_old[:2], four_new[:2]))
check(len(six_new) == 8 and all(six_new[i] != four_new[i].split()[1] for i in range(8)), 'with six banks on, a different number')
print('fingerprint: 8 setups the same as B129\'s; 8 differ with six banks on')
# ------------------------------------------------------------------------------------------------------------ 5. sources and pages
main_cpp = src('src/main.cpp'); menu = src('include/MenuOptions.h')
check(sdc.count('for (j = 0; j < BANKS_IN_FILE + 1; ++j)') == 8 and 'BANKS_USED + 1; ++j)\n' not in sdc.replace('for (int j = 0; j < BANKS_USED + 1; ++j)', ''), 'SDcard.h: the eight file loops stay at four banks')
check(fg.count('for (j = 0; j < BANKS_IN_FILE + 1; ++j)') == 4 and fg.index('Fp(0x5EC5)') < fg.index('Fp(0x5EC6)') < fg.index('return FingerprintSoFar;'), 'FlightGuard.h: four file loops; banks 5 and 6 folded in last, only when used')
check('#define BANKS_USED 6' in defs1 and '#define BANKS_IN_FILE 4' in defs1 and '#define MAXFILELEN (1024 * 4)' in defs1 and defs1.count('{"Profile 6"}') == 1 and 'BANKFIVE,   // "Profile 5"' in defs1, '1Definitions.h: six banks, the file at four, a 4k .MOD, the names and sounds')
check(sw.count('Bank = UpperBank();') == 2 and 'Bank = 4;' not in sw.split('void ReadAutoAndMotorSwitch()')[1].split('/****')[0], 'Switches.h: the mid and near positions pick the upper bank')
check('SendValue((char *)"c3", SixBanks ? 1 : 0);' in menu and 'SixBanksSet(six == 1);' in menu, 'Model options: the Six banks switch sent and read')
check('b <= BanksCount() && found < 3' in main_cpp and '"vis BK%d,%d"' in main_cpp and 'SixBanks = false; // B130' in main_cpp and 'if (Bank >= 1 && Bank <= 4)\n        SendCommand(FMPress[Bank - 1]);' in main_cpp, 'main.cpp: the centre note, the Bank names page, the defaults and the old front marks')
adj = src('include/RF_Adjust.h'); kt = adj[adj.index('FLASHMEM void AdjustKindTapped()'):]; kt = kt[:kt.index('\n}\n')]
fit = adj[adj.index('FLASHMEM static bool AdjFitBankRow(int i)'):]; fit = fit[:fit.index('\n}\n')]
right = adj[adj.index('FLASHMEM static bool AdjBankRowRight(const AdjRow &r)'):]; right = right[:right.index('\n}\n')]
check('if (AdjBankLine(r) && (!fits || n < BanksCount() || room < AdjRoomWanted(lo, hi, n)))' in fit and 'AdjSpaceBanks(r.ch + 5, AdjBankWhy, sizeof(AdjBankWhy));' in fit and 'if (!spaced && r.kind == AK_SWITCH && r.n == n' in fit and 'if (!AdjBankLine(r) && !fits) { AdjBankFitted[i] = false; return false; }' in fit, "B133: a bank line that cannot tell every bank apart is spaced, no question asked, then fitted; a rates switch of its own is left alone")
check('AdjBankLine(r) ? (n < BanksCount() || r.n != BanksCount()) : r.n < n' in right and 'return r.fn == 2 || (r.fn == 1 && LinkRatesToBanks);' in adj, "B133: a bank line is right only with a zone for every bank of the model; the rates selector follows the banks only when the rates do")
check('GetConfirmation((char *)"page AdjustView", ask)' not in kt and '"Banks 1 to %d of %d"' not in adj, "B132's offer and its words are gone")
check('Press Save: the bank selector now matches this transmitter' in adj and 'AdjBankWhy[0] ? "\\r\\n" : ""' in adj, 'the live fit says what it set, then Press Save')
wnc = main_cpp[main_cpp.index('void WriteNewCurve()'):]; wnc = wnc[:wnc.index('\n}\n')]
check('for (int p = 1; p <= BanksCount(); ++p)' in wnc, "B131: the curve page's Copy to all banks reaches banks 5 and 6 (Malcolm, 19 Oct: 'omitted 5,6')")
check(main_cpp.count('for (int fm = 1; fm <= BanksCount(); ++fm)') == 1 and 'for (int fm = 1; fm < 5; ++fm)' not in main_cpp and 'for (j = 1; j <= 4; ++j)' not in main_cpp and 'for (int j = 1; j <= 4; ++j)' not in main_cpp, 'main.cpp: no four-bank loop left (trims to centre, the defaults, InitCentreDegrees)')
check('The trims of every bank' in src('include/Trims.h') and 'fm <= BanksCount()' in src('include/Trims.h'), 'Trims.h: every bank')
for f, want in (('BANKNAME.TXT', "'Six banks'"), ('ONESWICH.TXT', "'Six banks'"), ('RXSETUP1.TXT', 'SIX BANKS:')):
    t = open(os.path.join(ROOT, 'Help files for SD', f)).read()
    check(want in t and all(len(l) <= 70 for l in t.replace('|', '\n').split('\n')), f + ' says six banks, lines of 70 or fewer')
if os.path.exists(SCREEN):
    pg = json.load(open(os.path.join(SCREEN, 'sd', 'hmi', 'pages', '20.json'))); by = {c['n']: c for c in pg['comps']}
    check(all(k in by for k in ('BK5', 'BK6', 't5', 't6', 't7')) and all(len(by['BK%d' % k]['opt']) == 38 for k in range(1, 7)) and by['BK1']['opt'][34] == 'Bank 5' and by['b1']['ev']['r'].endswith('BK6.val=35'), 'page 20: six boxes, 38 names, the presets set six')
    pg9 = json.load(open(os.path.join(SCREEN, 'sd', 'hmi', 'pages', '9.json'))); by9 = {c['n']: c for c in pg9['comps']}
    check('c3' in by9 and by9['c3']['t'] == 'switch' and by9['l_t5']['txt'] == 'Six banks (off: four)', 'page 9: the Six banks switch (B142: says what off means)')
    for i in (105, 106, 107, 108):
        check(os.path.getsize(os.path.join(SCREEN, 'sd', 'hmi', 'audio', '%d.wav' % i)) > 20000, 'clip %d on the card' % i)
    res = json.load(open(os.path.join(SCREEN, 'hmi', 'resources.json')))
    check(all(str(i) in res['audio'] for i in (105, 106, 107, 108)), 'the clips in resources.json')
    sm = open(os.path.join(SCREEN, 'src', 'main.cpp')).read()
    check('keepFolder("/banks56"' in sm and 'endsWith(name, ".b56")' in sm, 'the screen keeps and puts back the banks files')
else:
    print('(ESP32-board2 is not here: the pages not checked)')
print('test_banks: %d checks, %d failures' % (checks, fails))
sys.exit(1 if fails else 0)
