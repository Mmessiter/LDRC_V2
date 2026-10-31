#!/usr/bin/env python3
"""Host test of the main board's reading of the screen (B69): the functions of include/Nextion.h that collect a "get"
reply frame by frame and keep the touch words that arrive in between - StashFrame, StashPendingEventBytes, CollectReply,
getvalue, GetButtonPress - compiled on the Mac over a fake serial port. The case that found it (8 Oct 2026): the Models
page's Receive code (C1 00 00 00) landing just ahead of a "get MMems.val" reply was lost, so Receive had to be pressed again.
B160/B162 (31 Oct 2026): the Help button's word, and a press glued to a get's reply (the screen's bursts carry no terminator).
   python3 dev/test_nextion/test_nextion.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'Nextion.h')).read()
def fn(sig):
    m = re.search(re.escape(sig) + r'[^\n;]*\n\{.*?\n\}\n', src, re.S)   # the definition (a line ending in "{"), not a forward declaration
    assert m, sig
    return m.group(0)
parts = [fn('void StashFrame(const uint8_t *f, uint16_t n)'), fn('void StashPendingEventBytes()'), fn('bool CollectReply(uint8_t expected, uint16_t &k)'),
         fn('void GetTextIn()'), fn('bool GetButtonPress()'), fn('uint32_t getvalue(char *nbox)'),
         fn('bool HelpNameWhole(const char *name)'), fn('bool HelpNameFrom(char *name)'),   # (B160)
         fn('void GetReturnCode(char *tbox)')]   # (B162: keeps a press that arrives during a send)
prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <deque>
#include <string>
#define MAXTEXTIN 4096
#define CRUMB(x)
#define CRUMB_GETVALUE 0
#define CRUMB_GETTEXT 0
char TextIn[MAXTEXTIN + 2];
char PendingEvent[128]; uint16_t PendingEventLen = 0; bool TextInWasStashed = false;   // (B163)
uint32_t NextionReplyWaitMs = 100; bool NextionTextMissed = false;   // (B152)
static uint32_t fakeMs = 1000, fakeUs = 0;
static uint32_t millis() { return fakeMs; }
static uint32_t micros() { return fakeUs; }
static void delayMicroseconds(unsigned) { fakeUs += 20; }
static void KickTheDog() { fakeMs += 1; }   // (each pass of a wait costs a millisecond: the 100 ms timeout is reachable)
static uint64_t nowUs() { return (uint64_t) fakeMs * 1000 + fakeUs; }   // (B160) both clocks together: a late byte comes whichever one is waited on
struct FakeSerial {
    std::deque<uint8_t> in, onGet; std::string out;   // onGet: what the screen answers once a "get" has been sent (the reply, and whatever lands ahead of it)
    std::deque<uint8_t> late; uint64_t lateAt = 0;    // (B160) bytes that reach the port only later: a pause inside a word
    int lateAfterPolls = 0, emptyPolls = 0;           // ... or only after the port has been found empty so many times (the fake's clocks are coarse: a byte read costs a millisecond)
    void pump() { if (!late.empty() && (nowUs() >= lateAt || (lateAfterPolls && emptyPolls >= lateAfterPolls))) { for (uint8_t b : late) in.push_back(b); late.clear(); lateAfterPolls = 0; } }
    int available() { if (in.empty()) ++emptyPolls; pump(); return (int) in.size(); }
    void feedLatePolls(const char *w, int polls) { lateAt = ~(uint64_t) 0; lateAfterPolls = polls; emptyPolls = 0; for (const char *p = w; *p; ++p) late.push_back((uint8_t) *p); }
    int read() { pump(); if (in.empty()) return -1; uint8_t b = in.front(); in.pop_front(); return b; }
    int peek() { pump(); return in.empty() ? -1 : in.front(); }
    void feedRaw(const char *w) { for (const char *p = w; *p; ++p) in.push_back((uint8_t) *p); }                      // a touch word as the screen sends it: no terminator
    void feedRawL(const char *w) { for (const char *p = w; *p; ++p) onGet.push_back((uint8_t) *p); }                 // (B162) ... landing inside the next get's window, ahead of the reply
    void feedLate(const char *w, uint32_t afterUs) { lateAt = nowUs() + afterUs; for (const char *p = w; *p; ++p) late.push_back((uint8_t) *p); }
    void print(const char *s) { out += s; if (strncmp(s, "get ", 4) == 0) { for (uint8_t b : onGet) in.push_back(b); onGet.clear(); } }
    void write(uint8_t b) { out.push_back((char) b); }
    bool later = false;                                  // feeds go to onGet (after the next get) rather than straight into the port
    void feed(std::initializer_list<int> bytes) { for (int b : bytes) (later ? onGet : in).push_back((uint8_t) b); }
    void feedWord(const char *w) { for (const char *p = w; *p; ++p) in.push_back((uint8_t) *p); feed({0xFF, 0xFF, 0xFF}); }
    void feedCode7(int n) { feed({128 + n, 0, 0, 0, 0xFF, 0xFF, 0xFF}); }
    void feedCode24(int n) { feed({0, n, 0, 0, 0xFF, 0xFF, 0xFF}); }
    void feedQ(uint32_t v) { feed({'q', (int) (v & 255), (int) ((v >> 8) & 255), (int) ((v >> 16) & 255), (int) (v >> 24), 0xFF, 0xFF, 0xFF}); }
} NEXTION;
static void EndSend() { NEXTION.write(0xFF); NEXTION.write(0xFF); NEXTION.write(0xFF); }
static void LinkStrayFrame() {}
static void StashPrintableBytes(const char *, uint16_t) {}
void StashFrame(const uint8_t *f, uint16_t n);
''' + '\n'.join(parts) + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static int pendingCode7() { if (!GetButtonPress()) return -1; return ((uint8_t) TextIn[0] >= 128) ? ((uint8_t) TextIn[0] & 0x7F) : -2; }
int main() {
    char nbox[] = "MMems";
    NEXTION.later = true;                                    // the screen answers after the get, as it does
    // 1. a plain reply
    NEXTION.feedQ(3); CHECK(getvalue(nbox) == 3); CHECK(NEXTION.out.find("get MMems.val") == 0); CHECK(!GetButtonPress());
    // 2. THE CASE: the Receive code (128+65) lands ahead of the reply: the reply is still read, and the code is kept for GetButtonPress
    NEXTION.feedCode7(65); NEXTION.feedQ(3);
    CHECK(getvalue(nbox) == 3); CHECK(pendingCode7() == 65); CHECK(!GetButtonPress());
    // 3. a 24-bit code (va0.val=94<<8, a Save) ahead of the reply, likewise
    NEXTION.feedCode24(94); NEXTION.feedQ(0);
    CHECK(getvalue(nbox) == 0); CHECK(GetButtonPress() && TextIn[0] == 0 && (uint8_t) TextIn[1] == 94);
    // 4. a word ahead of the reply, as before
    NEXTION.feedWord("SendModel"); NEXTION.feedWord("BTHUNDR1.MOD"); NEXTION.feedQ(2);
    CHECK(getvalue(nbox) == 2); CHECK(GetButtonPress() && strncmp(TextIn, "SendModelBTHUNDR1.MOD", 21) == 0);
    // 5. return-code debris ahead of the reply is let go, and does not end the collecting
    NEXTION.feed({0x01, 0xFF, 0xFF, 0xFF}); NEXTION.feedQ(7);
    CHECK(getvalue(nbox) == 7); CHECK(!GetButtonPress());
    // 6. a code already waiting in the port BEFORE the get is sent (the pre-get rescue): kept too
    NEXTION.later = false; NEXTION.feedCode7(65); NEXTION.later = true;
    NEXTION.feedQ(5); CHECK(getvalue(nbox) == 5); CHECK(pendingCode7() == 65);
    // 7. no reply at all: the error value, nothing invented
    CHECK(getvalue(nbox) == 65535 && TextIn[0] == 0);
    // 8. a code AFTER the reply stays in the port for the next GetButtonPress (not swallowed)
    NEXTION.feedQ(1); NEXTION.feedCode7(65);
    CHECK(getvalue(nbox) == 1); CHECK(pendingCode7() == 65);
    // 9. GetButtonPress on a quiet port: nothing
    CHECK(!GetButtonPress());
    // --- B160 (31 Oct 2026): the Help button's word, "HelpView:MODELS.TXT", sent with no terminator and read by GetTextIn;
    // once read in two parts it opened today's log, the name being taken from a fixed place ---
    char name[16];
    // 10. whole, in one burst: the name follows the word (and the read zero-ends the text)
    NEXTION.feedRaw("HelpView:MODELS.TXT");
    CHECK(GetButtonPress() && strcmp(TextIn, "HelpView:MODELS.TXT") == 0);
    CHECK(HelpNameFrom(name) && strcmp(name, "MODELS.TXT") == 0);
    // 11. a pause inside the word shorter than the read's patience (the port found empty three times, ~60 us): waited out, the word whole
    NEXTION.feedRaw("HelpView:"); NEXTION.feedLatePolls("MODELS.TXT", 3);
    CHECK(GetButtonPress() && strcmp(TextIn, "HelpView:MODELS.TXT") == 0);
    // 12. a pause longer than the patience (fifteen empty looks): the read ends at the colon, and HelpNameFrom waits for the rest from the wire
    NEXTION.feedRaw("HelpView:"); NEXTION.feedLatePolls("MODELS.TXT", 15);
    CHECK(GetButtonPress() && strcmp(TextIn, "HelpView:") == 0);
    CHECK(HelpNameFrom(name) && strcmp(name, "MODELS.TXT") == 0); CHECK(!NEXTION.available());
    // 13. the rest set aside by a get-reply window (as the collector keeps it): taken from there, and only that
    NEXTION.feedRaw("HelpView:"); CHECK(GetButtonPress());
    StashFrame((const uint8_t *) "MODELS.TXT", 10);
    CHECK(HelpNameFrom(name) && strcmp(name, "MODELS.TXT") == 0 && PendingEventLen == 0);
    // 14. a code set aside is NOT eaten: no name, and the code still waits for GetButtonPress
    NEXTION.feedRaw("HelpView:"); CHECK(GetButtonPress());
    { const uint8_t code[4] = { 0xC1, 0, 0, 0 }; StashFrame(code, 4); }
    CHECK(!HelpNameFrom(name) && PendingEventLen == 4 && (uint8_t) PendingEvent[0] == 0xC1); CHECK(pendingCode7() == 65);
    // 15. another event ahead of it in the same read: the name is found wherever the word sits
    NEXTION.feedRaw("Export"); NEXTION.feedRaw("HelpView:MODELS.TXT");
    CHECK(GetButtonPress() && HelpNameFrom(name) && strcmp(name, "MODELS.TXT") == 0);
    // 16. the word cut, and nothing more ever comes: no name, and the wait is bounded (30 ms)
    NEXTION.feedRaw("HelpView:MOD"); CHECK(GetButtonPress());
    { const uint32_t t0 = fakeMs; CHECK(!HelpNameFrom(name)); CHECK(fakeMs - t0 >= 30 && fakeMs - t0 < 40); }
    // 17. a code on the wire after a cut word is not ours: left in the port for GetButtonPress
    NEXTION.feedRaw("HelpView:"); CHECK(GetButtonPress());
    NEXTION.later = false; NEXTION.feed({0xC1, 0, 0, 0}); NEXTION.later = true;
    CHECK(!HelpNameFrom(name) && NEXTION.available() == 4); CHECK(pendingCode7() == 65);
    // --- B162 (31 Oct 2026, the yellow transmitter: Help still opened "No log yet today" after B160): the screen's button
    // codes and words carry NO terminator (its print sends the raw bytes), so a press inside a get window is glued to the reply ---
    NEXTION.later = true;
    // 18. the Help word glued to the reply: the value is read, and the word comes whole
    NEXTION.feedRawL("HelpView:MODELS.TXT"); NEXTION.feedQ(5);
    CHECK(getvalue(nbox) == 5); CHECK(GetButtonPress() && strcmp(TextIn, "HelpView:MODELS.TXT") == 0 && HelpNameFrom(name) && strcmp(name, "MODELS.TXT") == 0);
    // 19. a 7-bit code glued to the reply: both kept
    NEXTION.feed({128 + 65, 0, 0, 0}); NEXTION.feedQ(6);
    CHECK(getvalue(nbox) == 6); CHECK(pendingCode7() == 65);
    // 20. a 24-bit code glued to the reply (lost until now: the stash knew a 24-bit code only as exactly 4 bytes)
    NEXTION.feed({0, 94, 0, 0}); NEXTION.feedQ(7);
    CHECK(getvalue(nbox) == 7); CHECK(GetButtonPress() && TextIn[0] == 0 && (uint8_t) TextIn[1] == 94); CHECK(!GetButtonPress());
    // 21. a value of 'q' (113) in the reply, behind a word: the split still falls at the reply's own q
    NEXTION.feedRawL("Export"); NEXTION.feedQ(113);
    CHECK(getvalue(nbox) == 113); CHECK(GetButtonPress() && strcmp(TextIn, "Export") == 0);
    // 22. a reply alone, as ever; and a code AFTER it still waits in the port
    NEXTION.feedQ(8); NEXTION.feedCode7(65); CHECK(getvalue(nbox) == 8); CHECK(pendingCode7() == 65); CHECK(!GetButtonPress());
    // 23. the name with a reply's bytes on its tail (a frame stashed whole by an older collector): cut at .TXT
    NEXTION.feedRaw("HelpView:MODELS.TXTq\x05"); CHECK(GetButtonPress()); CHECK(HelpNameFrom(name) && strcmp(name, "MODELS.TXT") == 0);
    // 24. GetReturnCode: a press that arrives while a command is being sent is kept, not drained ...
    NEXTION.later = false;
    NEXTION.feedRaw("HelpView:MODELS.TXT"); GetReturnCode(nbox); CHECK(NEXTION.available() == 0); CHECK(GetButtonPress() && strcmp(TextIn, "HelpView:MODELS.TXT") == 0);
    NEXTION.feedCode7(65); GetReturnCode(nbox); CHECK(pendingCode7() == 65);
    // 25. ... and debris is still let go: a return code, a late value reply, a late text reply
    NEXTION.feed({0x01, 0xFF, 0xFF, 0xFF}); NEXTION.feedQ(9); NEXTION.feedWord("pBTHUNDR1"); GetReturnCode(nbox); CHECK(!GetButtonPress());
    NEXTION.later = true;
    printf("test_nextion: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++11', '-Wall', '-Wno-unused-function', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
