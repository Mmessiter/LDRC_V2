#!/usr/bin/env python3
"""Host test of B116: models.dat filled to its full size, so every model slot can be written where it belongs.
The card library (SdFat) refuses a seek beyond a file's end and leaves the position where it was - the end, after a
FILE_WRITE open - so a model saved into a slot beyond the end of models.dat was appended, record after record, and read
back as empty. Here FillModelsFile() (include/SDFiles.h) is lifted and run over a fake file that behaves as SdFat does,
with the per-byte seek-then-write of SDUpdate8BITS, through: Reset transmitter on an empty card (the fault, then the fix),
the example card's 186,407-byte models.dat (slot 70 lost, then kept), a full-size file (untouched), a short file (its
bytes kept), and the link's guard.
   python3 dev/test_models_file/test_models_file.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.environ.get('TXV1B_TC', os.path.join(ROOT, 'TransmitterCode'))
checks = fails = 0
def check(c, what):
    global checks, fails
    checks += 1
    if not c:
        fails += 1
        print('FAIL:', what)
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()
def lift(rel, head):
    lines = src(rel).split('\n')
    for i, l in enumerate(lines):
        if l.startswith(head):
            for j in range(i + 1, len(lines)):
                if lines[j] == '}':
                    return '\n'.join(lines[i:j + 1]) + '\n'
    raise SystemExit('cannot lift %s from %s' % (head, rel))
defs = src('include/1Definitions.h'); sdf = src('include/SDFiles.h')
DEFS = '\n'.join(l for l in defs.split('\n') if re.match(r'#define (TXSIZE|MODELSIZE|MAXMODELNUMBER)\b', l)) + '\n'
DEFS += '\n'.join(l for l in sdf.split('\n') if l.startswith('#define MODELS_FILE_SIZE ')) + '\n'
assert DEFS.count('#define') == 4, DEFS
example = os.path.join(TC, 'SD Examples', 'Teensy SD Example', 'models.dat')
EXAMPLE_SIZE = os.path.getsize(example) if os.path.exists(example) else 186407

PROGRAM = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <vector>
#define FLASHMEM
@DEFS@
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
// the card's file as SdFat behaves: a seek beyond the end fails and the position stays; a write at the end appends
struct FakeFile {
    std::vector<uint8_t> d; size_t pos = 0; long seekFails = 0, bytes = 0;
    uint64_t size() { return d.size(); }
    bool seek(uint64_t p) { if (p > d.size()) { ++seekFails; return false; } pos = (size_t) p; return true; }
    size_t write(uint8_t v) { if (pos >= d.size()) d.resize(pos + 1); d[pos++] = v; ++bytes; return 1; }
    size_t write(const void *b, size_t n) { const uint8_t *p = (const uint8_t *) b; for (size_t i = 0; i < n; ++i) write(p[i]); return n; }
    void flush() {}
    void open(size_t len) { d.assign(len, 0xEE); for (size_t i = 0; i < len; ++i) d[i] = (uint8_t) (i * 7 + 3); pos = len; seekFails = 0; bytes = 0; }   // FILE_WRITE: at the end, the old bytes a pattern
};
static FakeFile ModelsFileNumber;
bool LinkChangedUserData = false;
static int dogs = 0; static void KickTheDog() { ++dogs; }
@FILL@
// SDUpdate8BITS as SDcard.h has it: seek to the byte, then write it
static void SDUpdate8BITS(int a, uint8_t v) { ModelsFileNumber.seek(a); ModelsFileNumber.write(v); }
static const int RECORD = 2016;   // about what SaveOneModel writes
static int slotStart(int slot) { return TXSIZE + (slot - 1) * MODELSIZE; }
static void saveModel(int slot) { for (int k = 0; k < RECORD; ++k) SDUpdate8BITS(slotStart(slot) + k, k == 0 ? 42 : (uint8_t) (slot * 3 + k)); }
static bool slotOk(int slot) { const size_t a = slotStart(slot); if (a + RECORD > ModelsFileNumber.d.size()) return false; for (int k = 0; k < RECORD; ++k) if (ModelsFileNumber.d[a + k] != (k == 0 ? 42 : (uint8_t) (slot * 3 + k))) return false; return true; }
static void resetAll() { for (int pass = 1; pass < 5; ++pass) for (int m = 1; m <= MAXMODELNUMBER; ++m) saveModel(m); }   // ResetTransmitterSettings: "writes default four times!"
static int badSlots(int *firstBad) { int bad = 0; *firstBad = 0; for (int m = 1; m <= MAXMODELNUMBER; ++m) if (!slotOk(m)) { ++bad; if (!*firstBad) *firstBad = m; } return bad; }
int main()
{
    CHECK(MODELS_FILE_SIZE == (uint32_t) (512 + 91 * 3072));   // 280,064: the transmitter's block and 91 slots
    // 1. the fault: Reset transmitter on an empty card, no fill - the models go end to end; the last slots never land
    int firstBad = 0;
    ModelsFileNumber.open(0); resetAll();
    const int lostEmpty = badSlots(&firstBad);
    printf("empty card without the fill: %d slots lost, the first %d; file %zu bytes\n", lostEmpty, firstBad, ModelsFileNumber.d.size());
    CHECK(lostEmpty >= 2 && lostEmpty <= 4 && firstBad >= 88 && ModelsFileNumber.seekFails > 0);
    // 2. the fix: the file filled first - every slot where it belongs, the file its full size
    ModelsFileNumber.open(0); CHECK(FillModelsFile()); CHECK(ModelsFileNumber.d.size() == MODELS_FILE_SIZE && ModelsFileNumber.bytes == (long) MODELS_FILE_SIZE && dogs > 0);
    bool zeros = true; for (size_t i = 0; i < ModelsFileNumber.d.size(); ++i) if (ModelsFileNumber.d[i]) zeros = false;
    CHECK(zeros);                                                           // every slot an empty model (ModelDefined 0)
    ModelsFileNumber.seekFails = 0; resetAll();
    CHECK(badSlots(&firstBad) == 0 && ModelsFileNumber.seekFails == 0 && ModelsFileNumber.d.size() == MODELS_FILE_SIZE);
    CHECK(FillModelsFile() && ModelsFileNumber.bytes == (long) MODELS_FILE_SIZE + 4 * MAXMODELNUMBER * RECORD);   // full: nothing more written
    // 3. the example card's models.dat (@EXAMPLE@ bytes): a model saved in a high slot was lost ...
    ModelsFileNumber.open(@EXAMPLE@); saveModel(70);
    printf("example card without the fill: slot 70 %s; file %zu bytes\n", slotOk(70) ? "kept" : "LOST", ModelsFileNumber.d.size());
    CHECK(!slotOk(70) && ModelsFileNumber.d.size() == @EXAMPLE@ + RECORD);   // appended at the end instead
    int roomFor = 0; for (int m = 1; m <= MAXMODELNUMBER; ++m) if (slotStart(m) + RECORD <= @EXAMPLE@) roomFor = m;
    printf("the example file has room for %d models\n", roomFor);
    CHECK(roomFor >= 59 && roomFor <= 61);
    // ... and is kept with the fill, the old bytes untouched
    ModelsFileNumber.open(@EXAMPLE@); std::vector<uint8_t> before = ModelsFileNumber.d;
    CHECK(FillModelsFile() && ModelsFileNumber.d.size() == MODELS_FILE_SIZE && ModelsFileNumber.bytes == (long) (MODELS_FILE_SIZE - @EXAMPLE@));
    CHECK(std::equal(before.begin(), before.end(), ModelsFileNumber.d.begin()));
    bool tailZero = true; for (size_t i = @EXAMPLE@; i < ModelsFileNumber.d.size(); ++i) if (ModelsFileNumber.d[i]) tailZero = false;
    CHECK(tailZero);
    ModelsFileNumber.seekFails = 0; saveModel(70); saveModel(91); saveModel(1);
    CHECK(slotOk(70) && slotOk(91) && slotOk(1) && ModelsFileNumber.seekFails == 0 && ModelsFileNumber.d.size() == MODELS_FILE_SIZE);
    // 4. a full-size file: nothing written, nothing moved
    ModelsFileNumber.open(MODELS_FILE_SIZE); before = ModelsFileNumber.d;
    CHECK(FillModelsFile() && ModelsFileNumber.bytes == 0 && ModelsFileNumber.d == before);
    ModelsFileNumber.open(MODELS_FILE_SIZE + 5000); before = ModelsFileNumber.d;
    CHECK(FillModelsFile() && ModelsFileNumber.bytes == 0 && ModelsFileNumber.d == before);   // longer than full: left alone
    // 5. once the link has changed the pilot's files, nothing of theirs is written
    LinkChangedUserData = true; ModelsFileNumber.open(1000);
    CHECK(!FillModelsFile() && ModelsFileNumber.bytes == 0 && ModelsFileNumber.d.size() == 1000);
    LinkChangedUserData = false;
    // 6. the transmitter's own block (the first 512 bytes) is written the same way, from the start of a new file
    ModelsFileNumber.open(0); FillModelsFile(); ModelsFileNumber.seekFails = 0;
    for (int a = 0; a < TXSIZE; ++a) SDUpdate8BITS(a, (uint8_t) (a + 1));
    bool txOk = ModelsFileNumber.seekFails == 0; for (int a = 0; a < TXSIZE; ++a) if (ModelsFileNumber.d[a] != (uint8_t) (a + 1)) txOk = false;
    CHECK(txOk && ModelsFileNumber.d.size() == MODELS_FILE_SIZE);
    printf("%d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
'''
prog = PROGRAM.replace('@DEFS@', DEFS).replace('@FILL@', lift('include/SDFiles.h', 'FLASHMEM bool FillModelsFile()')).replace('@EXAMPLE@', str(EXAMPLE_SIZE))
with tempfile.TemporaryDirectory() as d:
    cpp = os.path.join(d, 't.cpp'); exe = os.path.join(d, 't')
    open(cpp, 'w').write(prog)
    r = subprocess.run(['clang++', '-std=c++17', '-Wall', '-Wextra', '-o', exe, cpp], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode:
        print(r.stdout); sys.exit('FillModelsFile does not compile on the host')
    r = subprocess.run([exe], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(r.stdout.strip())
    check(r.returncode == 0, 'FillModelsFile over the fake card')

# ---- as source
omf = lift('include/SDFiles.h', 'void OpenModelsFile()')
check('if (!SingleModelFlag)\n                FillModelsFile();' in omf and omf.index('ModelsFileOpen = true;') < omf.index('FillModelsFile();'), 'models.dat filled once open, never a .MOD')
check('extern bool LinkChangedUserData;' in sdf, "the link's guard reaches SDFiles.h (LinkMode.h comes later)")
upd = lift('include/SDcard.h', 'void SDUpdate8BITS(int p_address, uint8_t p_value)')
check('ModelsFileNumber.seek(p_address);' in upd and 'ModelsFileNumber.write(uint8_t(p_value));' in upd and upd.index('.seek(') < upd.index('.write('), "SDUpdate8BITS still seeks then writes a byte (what the fake card emulates)")
check(int(re.search(r'#define TXVERSION_EXTRA "B(\d+)', defs).group(1)) >= 116, 'B116 or later')
check(os.path.exists(example) and EXAMPLE_SIZE < 512 + 91 * 3072, 'the example card\'s models.dat is %d bytes: shorter than its slots (which is why B116 matters)' % EXAMPLE_SIZE)
print('%d source checks, %d failed' % (checks, fails))
sys.exit(1 if fails else 0)
