#!/usr/bin/env python3
"""NOTHING IS FLOWN FROM A MEMORY THAT IS BEING READ INTO (B211, the eleventh review, 15 Nov 2026; released code had the fault).
SDcard.h ReadOneModel waits 300 ms - in a wait that flies the model: the sticks read, the channels worked out from the model in memory,
a packet sent - when the models file would not open. At that moment the memory holds the model BEFORE it (another slot's, where a list
of all the models is being made) with its mixes already set aside. ReadOneModel now holds 1Definitions.h ModelMemoryBusy for as long as it
reads, and Utilities.h DelayWithDog flies nothing while that is set.
 1. the REAL DelayWithDog and the REAL ModelMemoryHold, run on the Mac: a wait under a hold flies nothing (the dog is fed, the power button
    looked at); the same wait with no hold flies; a hold inside a hold ends with the outer one; a wait with no model flies nothing either way;
 2. the sources: ReadOneModel takes the hold before anything else it does, and its wait stands behind it; both builds' condition in
    DelayWithDog asks ModelMemoryBusy; the two lists of all the models (MenuOptions.h LoadModelSelector, Model_IDs.h CheckAllModelIds) read
    the pilot's model back BEFORE they send anything (dev/test_wholepage/scene_models_memory runs them); the backup's rename no longer reads
    a model at all (dev/test_bugfixes runs it).
   python3 dev/test_modelmemory/test_modelmemory.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, 'TransmitterCode')
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()
def lift(text, start):
    i = text.index(start); j = text.index('{', i); d = 0
    for k in range(j, len(text)):
        if text[k] == '{': d += 1
        elif text[k] == '}':
            d -= 1
            if d == 0: return text[i:k + 1] + '\n'
    raise SystemExit('unbalanced: ' + start)
def release(text):   # the test build's lines out (ELRS_TEST not defined: the #else is the transmitter as released)
    out = []; skip = []
    for l in text.split('\n'):
        s = l.strip()
        if s.startswith('#ifdef ELRS_TEST'): skip.append('if'); continue
        if s.startswith('#else') and skip: skip[-1] = 'else'; continue
        if s.startswith('#endif') and skip: skip.pop(); continue
        if skip and skip[-1] == 'if': continue
        out.append(l)
    return '\n'.join(out)
DEFS, UTIL, SD, MENU, IDS, SDF = (src('include/' + f) for f in ('1Definitions.h', 'Utilities.h', 'SDcard.h', 'MenuOptions.h', 'Model_IDs.h', 'SDFiles.h'))
bad = []
# ---------------------------------------------------------------- 2. the sources
hold = DEFS[DEFS.index('uint8_t ModelMemoryBusy = 0;'):]; hold = hold[:hold.index('};') + 2]
if 'ModelMemoryHold() { ++ModelMemoryBusy; }' not in hold or '~ModelMemoryHold() { --ModelMemoryBusy; }' not in hold:
    bad.append('1Definitions.h: ModelMemoryHold counts ModelMemoryBusy up as it begins and down as it ends')
rom = re.sub(r'//[^\n]*', '', lift(SD, 'FLASHMEM bool ReadOneModel(uint32_t Mnum)'))
mo = re.match(r'FLASHMEM bool ReadOneModel\(uint32_t Mnum\)\s*\{\s*uint16_t j;\s*uint16_t i;\s*char NoModelYet\[\] = "File error\?";\s*ModelMemoryHold reading;', rom)
if not mo: bad.append('SDcard.h ReadOneModel: the hold (ModelMemoryHold reading;) is taken before anything else is done')
elif 'DelayWithDog(' not in rom[mo.end():] or 'DelayWithDog(' in rom[:mo.end()]: bad.append('SDcard.h ReadOneModel: its wait stands behind the hold')
if re.search(r'\bModelMemoryBusy\s*(?:=|\+\+|--)', re.sub(r'//[^\n]*', '', SD + UTIL + MENU + IDS + SDF + src('src/main.cpp'))):
    bad.append('ModelMemoryBusy is counted by ModelMemoryHold alone (a count set by hand can be left standing: the radio silent in every wait)')
dwd = re.sub(r'//[^\n]*', '', lift(UTIL, 'void DelayWithDog(uint32_t HowLong)'))
if 'if (((ModelMatched && BoundFlag) || ElrsFlies()) && !ModelMemoryBusy)' not in dwd or 'if (ModelMatched && BoundFlag && !ModelMemoryBusy)' not in dwd:
    bad.append('Utilities.h DelayWithDog: both builds fly the model in a wait only while no model is being read (ModelMemoryBusy)')
lms = re.sub(r'//[^\n]*', '', lift(MENU, 'void LoadModelSelector()'))
if not re.search(r'ModelNumber = SavedModelNumber;\s*ReadOneModel\(ModelNumber\);\s*SendOtherText\(MMemsp, buf\);', lms) or re.search(r'Send\w*\(', lms[:lms.index('ModelNumber = SavedModelNumber;')]):
    bad.append('MenuOptions.h LoadModelSelector: the pilot\'s model is read back BEFORE the list is sent - and nothing is sent before that')
ids = re.sub(r'//[^\n]*', '', lift(IDS, 'FLASHMEM void CheckAllModelIds()'))
first = ids.index('for (ModelNumber = 1;'); back = ids.index('ModelNumber = SavedModelNumber;')
if not re.search(r'ModelNumber = SavedModelNumber;\s*ReadOneModel\(ModelNumber\);\s*SendOtherText\(MMemsp, buf\);', ids) or re.search(r'Send\w*\(', ids[first:back]) or 'ReadOneModel(' in ids[ids.index('SendOtherText(MMemsp, buf);'):]:
    bad.append('Model_IDs.h CheckAllModelIds: the pilot\'s model is read back BEFORE the report is sent; nothing is sent while the slots are read, and no slot is read after')
ren = re.sub(r'//[^\n]*', '', lift(SDF, 'FLASHMEM void RenameFile()'))
if re.search(r'ReadOneModel|SaveOneModel|WriteBackup|SingleModelFlag|LoadModelForRenaming|RestoreCurrentModel', ren) or 'TINYCARD.rename(from, SearchFile)' not in ren:
    bad.append('SDFiles.h RenameFile: the file is renamed on the card - no model is read into memory or written from it')
if re.search(r'\b(?:LoadModelForRenaming|RestoreCurrentModel)\s*\(', re.sub(r'//[^\n]*', '', DEFS + UTIL + MENU + SDF + src('src/main.cpp'))):
    bad.append('LoadModelForRenaming / RestoreCurrentModel (a backup file read into memory in place of the pilot\'s model) are gone')
for b in bad: print('FAIL: ' + b)
# ---------------------------------------------------------------- 1. the real wait
PROG = r'''
#include <cstdio>
#include <cstdint>
#define FASTRUN
#define FLASHMEM
#define CRUMB(x)
#define CRUMB_DELAY 0
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static uint32_t nowMs = 1000; static uint32_t millis() { return nowMs; }
static bool InsideDelayWithDog = false, ModelMatched = false, BoundFlag = false;
static int dogs = 0, powerLooks = 0, sticks = 0, motorFixes = 0, packets = 0;
static void KickTheDog() { ++dogs; ++nowMs; }   // (a millisecond a round)
void DelayWithDog(uint32_t HowLong);
static int nestAt = 0, nestedRounds = -1;   // (the power button's look, inside a wait, puts the front page up - and a page command waits: a wait INSIDE a wait)
static void CheckPowerOffButton() { ++powerLooks; if (nestAt && powerLooks == nestAt) { const int d0 = dogs; DelayWithDog(100); nestedRounds = dogs - d0; } }
static void GetNewChannelValues() { ++sticks; } static void FixMotorChannel() { ++motorFixes; } static void SendData() { ++packets; }
''' + hold + '\n' + release(lift(UTIL, 'void DelayWithDog(uint32_t HowLong)')) + r'''
static void none() { dogs = powerLooks = sticks = motorFixes = packets = 0; }
static void readOneModelsWait() { ModelMemoryHold reading; DelayWithDog(300); }   // as SDcard.h ReadOneModel waits for the models file
int main()
{
    // a model connected: a wait flies it
    ModelMatched = BoundFlag = true; none(); DelayWithDog(50);
    CHECK(dogs == 50 && powerLooks == 50 && sticks == 50 && motorFixes == 50 && packets == 50 && !InsideDelayWithDog);
    // ... but not while a model is being read into the memory: the dog fed, the power button looked at, NOTHING flown
    none(); readOneModelsWait();
    printf("a wait of 300 ms inside a model's read, the model connected: the sticks read %d times, %d packets (the dog fed %d times)\n", sticks, packets, dogs);
    CHECK(dogs == 300 && powerLooks == 300 && sticks == 0 && motorFixes == 0 && packets == 0);
    CHECK(ModelMemoryBusy == 0);                                                  // (the hold ended with the read)
    // ... and afterwards the next wait flies again
    none(); DelayWithDog(20); CHECK(sticks == 20 && packets == 20);
    // a hold inside a hold (a list being made: every slot's read inside it) ends with the outer one
    { ModelMemoryHold list; { ModelMemoryHold slot; CHECK(ModelMemoryBusy == 2); } CHECK(ModelMemoryBusy == 1); none(); DelayWithDog(10); CHECK(packets == 0 && dogs == 10); }
    CHECK(ModelMemoryBusy == 0); none(); DelayWithDog(10); CHECK(packets == 10);
    // (the thirteenth review: no test held it - every scene of the screen's tests has a wait of its own) A WAIT INSIDE A WAIT GOES STRAIGHT BACK: the power
    // button's look, at the wait's tenth round, asks for 100 ms more - none of it is waited (it would fly the model from inside flying the model, and
    // end the outer wait's "inside a wait" for every page command sent behind it)
    none(); nestAt = 10; nestedRounds = -1; DelayWithDog(50);
    printf("a wait of 100 ms asked from inside a wait of 50 ms: %d rounds of it ran; the outer wait fed the dog %d times\n", nestedRounds, dogs);
    CHECK(nestedRounds == 0 && dogs == 50 && packets == 50 && !InsideDelayWithDog);
    nestAt = 0;
    // no model connected: nothing is flown in any wait
    ModelMatched = false; none(); DelayWithDog(10); CHECK(packets == 0 && dogs == 10);
    printf("test_modelmemory: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp()
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(PROG)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-fsanitize=address,undefined', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: sys.exit(r.stderr[-5000:] + '\ncompile failed')
rc = subprocess.run([os.path.join(d, 't')]).returncode
print('test_modelmemory source checks: %d failures' % len(bad))
if not rc and not bad: print('ALL GOOD')
sys.exit(1 if (rc or bad) else 0)
