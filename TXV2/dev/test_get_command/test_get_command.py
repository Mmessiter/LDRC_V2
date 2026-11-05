#!/usr/bin/env python3
"""Host test of the Teensy's "get" exchange with the screen, and of the Models page's double tap (B169/B171, 2 Nov 2026).

B169 asked for tch2 (where the finger lifted) through GetValue, whose command is "get <name>.val": "get tch2.val" names a
COMPONENT the screen has not got, and the screen answers 0 for one of those - so every tap looked like the left list and no
double tap ever opened the date box. The source checks of the day passed: they looked at the words, not at the exchange.
This test compiles the real exchange code from Nextion.h (StashFrame, StashPendingEventBytes, CollectReply, EndSend,
GetNumberReply, getvalue, GetSysValue, GetValue) and the real BackupFileTapped from MenuOptions.h over a fake screen that
answers as the real one does: a system variable by its bare name, a component's val by "<name>.val", 0 for a component it
has not got, nothing at all for a name in `silent`.
   python3 dev/test_get_command/test_get_command.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INC = os.path.join(ROOT, 'TransmitterCode', 'include')
def src(name): return open(os.path.join(INC, name), encoding='utf-8', errors='replace').read()
NEXTION, MENU = src('Nextion.h'), src('MenuOptions.h')

def lift(text, head):
    """The function whose first line starts with `head` (column 0, Allman style): from there to the next line that is just '}'."""
    lines = text.split('\n')
    for i, l in enumerate(lines):
        if l.startswith(head) and not l.split('//')[0].rstrip().endswith(';'):   # (not its prototype)
            for j in range(i + 1, len(lines)):
                if lines[j] == '}':
                    return '\n'.join(lines[i:j + 1]) + '\n'
            break
    raise SystemExit('cannot lift ' + head)

PRE = r'''
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cstdlib>
#include <string>
#include <map>
#include <set>
#include <vector>
#include <sys/types.h>
#define FLASHMEM
#define CRUMB(x)
#define MAXTEXTIN 1024 * 4
#define SCREEN_X "tch2"
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)

// ---- time and the dog
static uint32_t fakeMs = 100000;
static uint32_t millis() { return ++fakeMs; }                   // (a millisecond a call: a loop that waits for nothing ends)
static void KickTheDog() {}
static void DelayWithDog(int ms) { fakeMs += ms; }
static void delayMicroseconds(int) {}

// ---- the screen: answers at the third FF of a command, as the real one does
static std::map<std::string, long> sysVars, compVals;          // "tch2" -> 517 ; "Mfiles" -> 7
static std::set<std::string> silent;                            // names that never answer
static std::vector<std::string> sent;                           // every command, in order
struct FakeLink
{
    std::string tx; int ffs = 0; std::vector<uint8_t> rx; size_t rd = 0;
    int available() { return (int) (rx.size() - rd); }
    int read() { return rd < rx.size() ? rx[rd++] : -1; }
    void print(const char *s) { tx += s; }
    void write(uint8_t b)
    {
        if (b != 0xFF) { tx += (char) b; ffs = 0; return; }
        if (++ffs < 3) return;
        ffs = 0; std::string cmd = tx; tx.clear(); sent.push_back(cmd); answer(cmd);
    }
    void reply(long v) { const uint8_t f[8] = { 'q', (uint8_t) v, (uint8_t) (v >> 8), (uint8_t) (v >> 16), (uint8_t) (v >> 24), 0xFF, 0xFF, 0xFF }; rx.insert(rx.end(), f, f + 8); }
    void answer(const std::string &cmd)
    {
        if (cmd.rfind("get ", 0) != 0) return;
        std::string ref = cmd.substr(4); size_t dot = ref.rfind('.');
        if (dot == std::string::npos) { if (!silent.count(ref)) reply(sysVars.count(ref) ? sysVars[ref] : 0); return; }   // a system variable: 0 when unknown, as the screen's getSys
        std::string nm = ref.substr(0, dot), attr = ref.substr(dot + 1);
        if (silent.count(nm)) return;
        if (attr == "val") reply(compVals.count(nm) ? compVals[nm] : 0);   // a component it has not got: 0 (that is what hid the bug)
    }
} NEXTION;

// ---- the Teensy's globals the lifted code uses
char TextIn[MAXTEXTIN + 2];
bool NextionTextMissed = false;
char NextionMissedBox[12] = {0}; bool NextionSettledOk = false; static void RfGatherStart() { NextionTextMissed = false; }   // (B187)
uint32_t NextionReplyWaitMs = 100;
static void DelayWithDog(uint32_t) {}   // (B188)
#define NEXTION_GET_WAIT_MS 2000
bool NextionGetPending = false;   // (B189)
static void NoteLateReply(const char *, uint32_t, bool) {}   // (B188)

void StashFrame(const uint8_t *f, uint16_t n);
static uint32_t micros() { static uint32_t us = 0; return us += 50; }   // B177
static void LogGhostFrame(const char *, const uint8_t *, uint16_t) {}

// ---- the Models page: the date box is recorded, not drawn
static std::vector<uint32_t> boxes;
static void ShowBackupFileDate(uint32_t row) { boxes.push_back(row); }
'''

MAIN = r'''
static void tap(uint32_t x, long row, uint32_t at) { sysVars["tch2"] = x; compVals["Mfiles"] = row; BackupFileTapped(at); }
int main()
{
    // ---- the exchange itself: what is sent, and what comes back
    sysVars["tch2"] = 517; compVals["Mfiles"] = 7; compVals["MMems"] = 2;
    CHECK(GetSysValue("tch2") == 517); CHECK(sent.back() == "get tch2");                 // B171: a system variable by its bare name
    CHECK(getvalue((char *) "Mfiles") == 7); CHECK(sent.back() == "get Mfiles.val");     // a component's val as before
    CHECK(GetValue((char *) "MMems") == 2); CHECK(!NextionTextMissed);
    CHECK(GetValue((char *) "tch2") == 0); CHECK(sent.back() == "get tch2.val");         // B169's ask: the screen answers 0 for a component it has not got (the bug)
    silent.insert("tch3"); CHECK(GetSysValue("tch3") == 65535); CHECK(!NextionTextMissed);   // no reply = 65535, and no page's save is failed for it
    silent.insert("n9"); CHECK(GetValue((char *) "n9") == 65535); CHECK(NextionTextMissed); NextionTextMissed = false;   // (B156, unchanged)
    CHECK(PendingEventLen == 0);                                                          // nothing stashed along the way
    // ---- the double tap, as BackupFileTapped sees it (the real function, over the fake screen)
    tap(100, 3, 1000); tap(100, 3, 1200); CHECK(boxes.empty());                            // the left list: never
    tap(600, 3, 2000); CHECK(boxes.empty()); tap(600, 3, 2300); CHECK(boxes.size() == 1 && boxes[0] == 3);   // the same backup file twice, 300 ms apart: the box
    tap(600, 3, 2500); CHECK(boxes.size() == 1);                                           // a third tap: the pair was spent
    tap(600, 4, 4000); tap(600, 5, 4200); CHECK(boxes.size() == 1);                        // two different files: no
    tap(600, 5, 6000); tap(600, 5, 7100); CHECK(boxes.size() == 1);                        // the same file, but 1.1 s apart: no
    tap(600, 5, 7300); CHECK(boxes.size() == 2 && boxes[1] == 5);                          // ... and 200 ms after that one: yes
    tap(600, 5, 9000); tap(100, 5, 9100); tap(600, 5, 9200); CHECK(boxes.size() == 2);     // a left-list tap between two clears the pair
    tap(600, 5, 9400); CHECK(boxes.size() == 3 && boxes[2] == 5);                          // (the two after it make one)
    silent.insert("tch2"); tap(600, 6, 11000); tap(600, 6, 11200); CHECK(boxes.size() == 3); silent.erase("tch2");   // the screen not answering tch2: never a box
    tap(600, 6, 13000); tap(600, 6, 13200); CHECK(boxes.size() == 4 && boxes[3] == 6);     // (and fine again once it answers)
    printf("test_get_command: %d checks, %d failures\n", checks, fails);
    if (fails == 0) printf("ALL GOOD\n");
    return fails ? 1 : 0;
}
'''

def main():
    decl_start = NEXTION.index('#define MAXPENDINGFRAME'); decl_end = NEXTION.index('void PendingPush(')   # B177: PendingEvent and the frame globals as they are
    decls = '\n'.join(l for l in NEXTION[decl_start:decl_end].split('\n') if not l.startswith('//'))
    body = (decls + lift(NEXTION, 'void PendingPush(') + lift(NEXTION, 'int ReadFramedRest(') + lift(NEXTION, 'void StashFramed(')
            + lift(NEXTION, 'void StashFrame(const uint8_t *f, uint16_t n)') + lift(NEXTION, 'static bool PipeLineDone(') + lift(NEXTION, 'static bool PipeLineOpen(') + lift(NEXTION, 'void StashPendingEventBytes()')
            + lift(NEXTION, 'bool CollectReply(uint8_t expected, uint16_t &k)') + lift(NEXTION, 'void EndSend()')
            + lift(NEXTION, 'static uint32_t GetNumberReply(const char *CB)') + lift(NEXTION, 'uint32_t getvalue(char *nbox)')
            + lift(NEXTION, 'uint32_t GetSysValue(const char *name)') + lift(NEXTION, 'uint32_t GetValue(char *nbox)')
            + lift(MENU, 'static void BackupFileTapped(uint32_t at)'))
    if '.val' in lift(NEXTION, 'uint32_t GetSysValue(const char *name)'): sys.exit('GetSysValue must ask by the bare name (B171)')
    if 'GetSysValue(SCREEN_X)' not in lift(MENU, 'static void BackupFileTapped(uint32_t at)'): sys.exit('BackupFileTapped must read tch2 through GetSysValue (B171)')
    d = tempfile.mkdtemp()
    cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(PRE + body + MAIN)
    r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-format', '-Wno-unused-but-set-variable',
                        '-fsanitize=address,undefined', '-o', os.path.join(d, 'test_get_command'), cpp], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stderr[-4000:] + '\ncompile failed')
    return subprocess.run([os.path.join(d, 'test_get_command')]).returncode

if __name__ == '__main__': sys.exit(main())
