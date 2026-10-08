#!/usr/bin/env python3
"""Host test of the main board's reading of the screen (B69): the functions of include/Nextion.h that collect a "get"
reply frame by frame and keep the touch words that arrive in between - StashFrame, StashPendingEventBytes, CollectReply,
getvalue, GetButtonPress - compiled on the Mac over a fake serial port. The case that found it (8 Oct 2026): the Models
page's Receive code (C1 00 00 00) landing just ahead of a "get MMems.val" reply was lost, so Receive had to be pressed again.
   python3 dev/test_nextion/test_nextion.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'Nextion.h')).read()
def fn(sig):
    m = re.search(re.escape(sig) + r'[^\n;]*\n\{.*?\n\}\n', src, re.S)   # the definition (a line ending in "{"), not a forward declaration
    assert m, sig
    return m.group(0)
parts = [fn('void StashFrame(const uint8_t *f, uint16_t n)'), fn('void StashPendingEventBytes()'), fn('bool CollectReply(uint8_t expected, uint16_t &k)'),
         fn('void GetTextIn()'), fn('bool GetButtonPress()'), fn('uint32_t getvalue(char *nbox)')]
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
char PendingEvent[128]; uint16_t PendingEventLen = 0;
static uint32_t fakeMs = 1000, fakeUs = 0;
static uint32_t millis() { return fakeMs; }
static uint32_t micros() { return fakeUs; }
static void delayMicroseconds(unsigned) { fakeUs += 20; }
static void KickTheDog() { fakeMs += 1; }   // (each pass of a wait costs a millisecond: the 100 ms timeout is reachable)
struct FakeSerial {
    std::deque<uint8_t> in, onGet; std::string out;   // onGet: what the screen answers once a "get" has been sent (the reply, and whatever lands ahead of it)
    int available() { return (int) in.size(); }
    int read() { if (in.empty()) return -1; uint8_t b = in.front(); in.pop_front(); return b; }
    int peek() { return in.empty() ? -1 : in.front(); }
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
    printf("test_nextion: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++11', '-Wall', '-Wno-unused-function', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
