#!/usr/bin/env python3
"""Host test of the screen's FRAMED BURSTS (B177, 4 Nov 2026): the real reading code of Nextion.h (ReadFramedRest, PendingPush,
StashFramed, StashFrame, StashPendingEventBytes, CollectReply, GetTextIn, GetButtonPress, TextInIsGenuine) compiled on the Mac
over a fake screen whose bytes can arrive with pauses among them.

The fault: a page's event prints its bytes raw, and the screen's port is fed by an interrupt that a busy moment holds back; a
pause of over 200 us inside a burst ended the frame on the Teensy, and the tail was obeyed as a command - 00 03 00 00 (the log
text's height) is the Sounds page's OK, B0 is GotoFrontView. Now a screen told "ldrcframe=1" wraps every burst 7E 7E len_lo
len_hi bytes; the Teensy reads it to its length, waits out a pause inside it, and once it has seen one framed burst drops an
unframed binary frame (a split tail, a late reply split from its q).
   python3 dev/test_frames/test_frames.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INC = os.path.join(ROOT, 'TransmitterCode', 'include')
NEXTION = open(os.path.join(INC, 'Nextion.h'), encoding='utf-8', errors='replace').read()

def lift(text, head):
    """The function whose first line starts with `head` (column 0, Allman style): from there to the next line that is just '}'."""
    lines = text.split('\n')
    for i, l in enumerate(lines):
        if l.startswith(head) and not l.split('//')[0].rstrip().endswith(';'):
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
#include <vector>
#define FLASHMEM
#define CRUMB(x)
#define MAXTEXTIN 1024 * 4
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)

// ---- time and the dog
static uint32_t fakeMs = 100000, fakeUs = 0;
static uint32_t millis() { return ++fakeMs; }
static uint32_t micros() { return fakeUs += 50; }             // (50 us a look: a 200 us quiet is four looks, a 20 ms gap four hundred)
static void KickTheDog() {}
static void delayMicroseconds(int) {}
static void LinkStrayFrame() {}

// ---- the screen's wire: bytes, with pauses where the test puts them (a pause = that many looks with nothing there)
struct FakeLink
{
    std::vector<uint8_t> rx; size_t rd = 0; std::map<size_t, int> pauseAt;
    int available() { auto it = pauseAt.find(rd); if (it != pauseAt.end() && it->second > 0) { --it->second; return 0; } return (int) (rx.size() - rd); }
    int read() { return rd < rx.size() ? rx[rd++] : -1; }
    int peek() { return rd < rx.size() ? rx[rd] : -1; }
} NEXTION;
static std::vector<std::string> sent, ghosts;
static void SendCommand(char *c) { sent.push_back(c); }
static void LogGhostFrame(const char *why, const uint8_t *f, uint16_t n) { char b[200]; int p = snprintf(b, sizeof b, "%s:", why); for (uint16_t i = 0; i < n && i < 8; ++i) p += snprintf(b + p, sizeof b - p, " %02X", f[i]); ghosts.push_back(b); }

// ---- the Teensy's globals the lifted code uses
char TextIn[MAXTEXTIN + 2];
uint32_t NextionReplyWaitMs = 100;
'''

MAIN = r'''
static void feed(std::initializer_list<int> bytes) { for (int b : bytes) NEXTION.rx.push_back((uint8_t) b); }
static void feedWord(const char *w) { for (const char *p = w; *p; ++p) NEXTION.rx.push_back((uint8_t) *p); }
static void framed(std::initializer_list<int> payload) { const int n = (int) payload.size(); feed({0x7E, 0x7E, n & 0xFF, n >> 8}); feed(payload); }
static bool is(const char *bytes, int n) { return memcmp(TextIn, bytes, n) == 0; }
static bool pressSoon() { for (int i = 0; i < 200; ++i) if (GetButtonPress()) return true; return false; }   // (the loop comes round again until the bytes are there)
static void fresh() { NEXTION.rx.clear(); NEXTION.rd = 0; NEXTION.pauseAt.clear(); sent.clear(); ghosts.clear(); PendingEventLen = 0; PendingCount = 0; TextInFramed = false; ScreenFramesBursts = false; FrameEnableSentMs = 0; memset(TextIn, 0x55, 64); }
int main()
{
    // 1. an older screen (never frames): an unframed code is read and obeyed as ever, and the screen is asked to frame - once in 2 s
    fresh(); feed({0x00, 0x03, 0x00, 0x00});
    CHECK(GetButtonPress() && !TextInFramed && is("\0\3\0\0", 4) && TextIn[4] == 0 && TextInIsGenuine() && sent.size() == 1 && sent[0] == "ldrcframe=1" && !ScreenFramesBursts);
    feed({0xB0, 0x00, 0x00, 0x00}); CHECK(GetButtonPress() && TextInIsGenuine() && sent.size() == 1);   // (asked already)
    fakeMs += 3000; feed({0xB0, 0x00, 0x00, 0x00}); CHECK(GetButtonPress() && TextInIsGenuine() && sent.size() == 2);   // (2 s on: asked again)
    // 2. a framed code: read to its length, unwrapped, obeyed; the screen is known to frame from then on
    fresh(); framed({0x00, 0x03, 0x00, 0x00});
    CHECK(GetButtonPress() && TextInFramed && ScreenFramesBursts && is("\0\3\0\0", 4) && TextIn[4] == 0 && TextInIsGenuine() && sent.empty() && NEXTION.available() == 0);
    // 3. the log page's twelve bytes with a pause after the eighth (the interpreter at work): one frame, whole
    fresh(); size_t at = NEXTION.rx.size(); framed({0x00, 0x0E, 0x00, 0x00, 0x90, 0x01, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00}); NEXTION.pauseAt[at + 4 + 8] = 60;
    CHECK(GetButtonPress() && TextInFramed && is("\0\x0e\0\0\x90\1\0\0\0\3\0\0", 12) && TextIn[12] == 0 && ghosts.empty());
    // 4. ... whereas the same twelve bytes unframed, with the pause, split as they did: the tail 00 03 00 00 came as a frame
    fresh(); at = NEXTION.rx.size(); feed({0x00, 0x0E, 0x00, 0x00, 0x90, 0x01, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00}); NEXTION.pauseAt[at + 8] = 60;
    CHECK(GetButtonPress() && !TextInFramed && is("\0\x0e\0\0\x90\1\0\0", 8) && TextIn[8] == 0);
    CHECK(pressSoon() && !TextInFramed && is("\0\3\0\0", 4) && TextInIsGenuine());   // (an older screen: still obeyed - nothing else to go by)
    // 5. once a framed burst has come, an unframed code is a ghost: logged, not obeyed; words still pass
    fresh(); framed({0xC1, 0x00, 0x00, 0x00}); CHECK(GetButtonPress() && TextInIsGenuine() && ScreenFramesBursts);
    feed({0x00, 0x03, 0x00, 0x00}); CHECK(GetButtonPress() && !TextInFramed && !TextInIsGenuine() && ghosts.size() == 1 && ghosts[0] == "an unframed code: 00 03 00 00");
    fakeMs += 3000; feed({0xB0, 0x00, 0x00, 0x00}); CHECK(GetButtonPress() && !TextInIsGenuine() && ghosts.size() == 2 && ghosts[1] == "an unframed code: B0 00 00 00");
    feedWord("FrontView"); CHECK(GetButtonPress() && !TextInFramed && is("FrontView", 9) && TextInIsGenuine() && sent.empty());
    feedWord("LDRCAWAKE"); CHECK(GetButtonPress() && TextInIsGenuine());
    feed({0xB0, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF}); CHECK(GetButtonPress() && !TextInIsGenuine());   // (a late reply split from its q: B0 00 00 00 FF FF FF)
    // 6. a framed burst that never completes (the screen went away): dropped, logged, nothing obeyed; the next frame is read whole
    fresh(); feed({0x7E, 0x7E, 0x0C, 0x00, 0x00, 0x0E, 0x00, 0x00, 0x90, 0x01, 0x00, 0x00});
    CHECK(GetButtonPress() && TextIn[0] == 0 && !TextInFramed && ghosts.size() == 1 && ghosts[0].rfind("an incomplete framed burst:", 0) == 0);
    framed({0xC2, 0x00, 0x00, 0x00}); CHECK(GetButtonPress() && TextInFramed && is("\xc2\0\0\0", 4));
    // 7. a lone 7E begins a word, as ever
    fresh(); feedWord("~x"); CHECK(GetButtonPress() && !TextInFramed && is("~x", 2) && TextIn[2] == 0 && TextInIsGenuine());
    // 8. in a reply's window (CollectReply): a framed burst ahead of the reply is kept whole and served afterwards; the reply is the reply
    fresh(); framed({0xC1, 0x00, 0x00, 0x00}); feed({'q', 0x05, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF});
    uint16_t k = 0; CHECK(CollectReply('q', k) && k == 8 && TextIn[0] == 'q' && TextIn[1] == 5 && PendingCount == 1);
    CHECK(GetButtonPress() && TextInFramed && TextInWasStashed && is("\xc1\0\0\0", 4) && TextIn[4] == 0 && PendingCount == 0 && PendingEventLen == 0);
    // 9. a framed burst with FF FF FF inside it (a page's -100 printed raw) ahead of the reply: whole, not cut at the FFs
    fresh(); framed({0x00, 0x10, 0x00, 0x00, 0x9C, 0xFF, 0xFF, 0xFF, 0x05, 0x00, 0x00, 0x00}); feed({'q', 0x07, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF});
    k = 0; CHECK(CollectReply('q', k) && k == 8 && TextIn[1] == 7 && PendingCount == 1 && PendingLens[0] == 12);
    CHECK(GetButtonPress() && TextInFramed && is("\0\x10\0\0\x9c\xff\xff\xff\5\0\0\0", 12) && TextIn[12] == 0);
    // 10. two framed bursts in the window: served one at a time, in order
    fresh(); framed({0xC1, 0x00, 0x00, 0x00}); framed({0x00, 0x15, 0x00, 0x00}); feed({'q', 0x01, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF});
    k = 0; CHECK(CollectReply('q', k) && PendingCount == 2);
    CHECK(GetButtonPress() && TextInFramed && is("\xc1\0\0\0", 4) && PendingCount == 1);
    CHECK(GetButtonPress() && TextInFramed && is("\0\x15\0\0", 4) && PendingCount == 0 && !GetButtonPress());
    // 11. the pre-get drain (StashPendingEventBytes, GetReturnCode's): a framed burst kept whole, an unframed word too, debris let go
    fresh(); framed({0xC3, 0x00, 0x00, 0x00}); feed({0x1A, 0xFF, 0xFF, 0xFF}); feedWord("UKRULES");
    StashPendingEventBytes(); CHECK(PendingCount == 2 && PendingLens[0] == 4 && PendingFramedFlags[0] && PendingLens[1] == 7 && !PendingFramedFlags[1]);
    CHECK(GetButtonPress() && TextInFramed && is("\xc3\0\0\0", 4)); CHECK(GetButtonPress() && !TextInFramed && is("UKRULES", 7) && TextInIsGenuine());
    // 12. a framed burst in the drain with a pause inside it: still whole
    fresh(); at = NEXTION.rx.size(); framed({0x00, 0x0E, 0x00, 0x00, 0x90, 0x01, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00}); NEXTION.pauseAt[at + 4 + 8] = 60;
    StashPendingEventBytes(); CHECK(PendingCount == 1 && PendingLens[0] == 12 && ghosts.empty());
    // 13. an empty frame of zeros (the screen's power-on 00 00 00 FF FF FF 88 FF FF FF) says nothing, framed or not
    fresh(); ScreenFramesBursts = true; feed({0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x88, 0xFF, 0xFF, 0xFF}); CHECK(GetButtonPress() && TextInIsGenuine() && ghosts.empty());
    // 14. B181: a PIPE LINE ("ldrctel 25:... 26:...") with a pause inside it (an interrupt held on the screen's side, a hold):
    //     read whole, to its newline - before, the pause ended the word and the second half, with no name, was lost ("PIDs:
    //     only PART came back in 2 s", Malcolm, 5 Nov 2026)
    fresh(); size_t at14 = NEXTION.rx.size(); feedWord("ldrctel 25:AABBCCDD 26:EEFF0011 27:22334455\n"); NEXTION.pauseAt[at14 + 20] = 40;   // (2 ms after "25:AABBCCDD ")
    CHECK(pressSoon() && strcmp(TextIn, "ldrctel 25:AABBCCDD 26:EEFF0011 27:22334455\n") == 0);
    // 15. ... an older screen's items line, without the newline: whole after 5 ms of quiet
    fresh(); size_t at15 = NEXTION.rx.size(); feedWord("ldrctel 25:AABBCCDD 26:EEFF0011"); NEXTION.pauseAt[at15 + 20] = 40;
    CHECK(pressSoon() && strcmp(TextIn, "ldrctel 25:AABBCCDD 26:EEFF0011") == 0);
    // 16. ... whereas a touch word still ends at a 200 us pause, as B160 had it: what follows is a word of its own
    fresh(); size_t at16 = NEXTION.rx.size(); feedWord("HelpView:MODELS.TXT"); NEXTION.pauseAt[at16 + 9] = 40;
    CHECK(pressSoon() && strcmp(TextIn, "HelpView:") == 0); CHECK(pressSoon() && strcmp(TextIn, "MODELS.TXT") == 0);
    // 17. a reply line from the pipe ("ldrcrep <id> <code> <body>\n") with the pause: whole too
    fresh(); size_t at17 = NEXTION.rx.size(); feedWord("ldrcrep 12 200 0102030405060708\n"); NEXTION.pauseAt[at17 + 16] = 40;
    CHECK(pressSoon() && strcmp(TextIn, "ldrcrep 12 200 0102030405060708\n") == 0);
    // 18. B186 (PID plus: "The screen did not answer for one of the boxes", the screen's log showing every answer sent): a pipe line
    //     told again while a get waits (screen 1.11.179: every 600 ms in the read window) comes ahead of the reply, with no FF FF FF -
    //     the reply is still the reply, and the line is kept and served whole afterwards
    fresh(); feedWord("ldrctel 25:AABBCCDD 26:EEFF0011\n"); feed({'p', '2', '.', '5', 0xFF, 0xFF, 0xFF});
    k = 0; CHECK(CollectReply('p', k) && TextIn[0] == 'p' && memcmp(TextIn, "p2.5", 4) == 0 && PendingCount == 1);
    CHECK(GetButtonPress() && strcmp(TextIn, "ldrctel 25:AABBCCDD 26:EEFF0011\n") == 0 && PendingCount == 0);
    // 19. ... and before a value reply (the Piro switch's q)
    fresh(); feedWord("ldrcrep 12 200 0102\n"); feed({'q', 0x01, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF});
    k = 0; CHECK(CollectReply('q', k) && TextIn[0] == 'q' && TextIn[1] == 1 && PendingCount == 1);
    CHECK(GetButtonPress() && strcmp(TextIn, "ldrcrep 12 200 0102\n") == 0);
    // 20. the pre-get drain meets a pipe line half there (a pause inside it): it waits for the newline and keeps the line whole,
    //     and the reply that follows the ask is not glued to its tail
    fresh(); at = NEXTION.rx.size(); feedWord("ldrctel 25:AABBCCDD 26:EEFF0011 27:22334455 28:66778899 29:AABBCCDD 30:EEFF0011 31:22334455 32:66778899 33:AABBCCDD\n");
    NEXTION.pauseAt[at + 20] = 40;
    StashPendingEventBytes(); CHECK(PendingCount == 1 && PendingLens[0] == 116 && NEXTION.available() == 0);
    feed({'p', '1', '0', 0xFF, 0xFF, 0xFF}); k = 0; CHECK(CollectReply('p', k) && memcmp(TextIn, "p10", 3) == 0);
    CHECK(GetButtonPress() && memcmp(TextIn, "ldrctel 25:", 11) == 0 && TextIn[115] == '\n');
    printf("test_frames: %d checks, %d failures\n", checks, fails);
    if (fails == 0) printf("ALL GOOD\n");
    return fails ? 1 : 0;
}
'''

def main():
    # the declarations between StashPrintableBytes' old place and PendingPush: PendingEvent and its companions, the frame globals
    decl_start = NEXTION.index('#define MAXPENDINGFRAME')
    decl_end = NEXTION.index('void PendingPush(')
    decls = '\n'.join(l for l in NEXTION[decl_start:decl_end].split('\n') if not l.startswith('//'))
    body = (decls + lift(NEXTION, 'void PendingPush(') + lift(NEXTION, 'int ReadFramedRest(') + lift(NEXTION, 'void StashFramed(') + lift(NEXTION, 'void PendingShrinkFirst()')
            + lift(NEXTION, 'void StashFrame(const uint8_t *f, uint16_t n)')
            + lift(NEXTION, 'static bool PipeLineDone(') + lift(NEXTION, 'static bool PipeLineOpen(') + lift(NEXTION, 'void StashPendingEventBytes()')
            + lift(NEXTION, 'bool CollectReply(uint8_t expected, uint16_t &k)')
            + lift(NEXTION, 'void GetTextIn()') + lift(NEXTION, 'bool GetButtonPress()') + lift(NEXTION, 'bool TextInIsGenuine()'))
    d = tempfile.mkdtemp()
    cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(PRE + body + MAIN)
    r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-format', '-Wno-unused-but-set-variable',
                        '-fsanitize=address,undefined', '-o', os.path.join(d, 'test_frames'), cpp], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stderr[-4000:] + '\ncompile failed')
    return subprocess.run([os.path.join(d, 'test_frames')]).returncode

if __name__ == '__main__': sys.exit(main())
