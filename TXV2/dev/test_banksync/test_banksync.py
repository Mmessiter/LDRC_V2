#!/usr/bin/env python3
"""Host test of B143, the bank count told to the receiver (include/BankSync.h): the logic between its BANKSYNC-LOGIC
markers compiled on the Mac with a fake pipe (PipeHttp.h's variables, a PipeRequest that records the path, replies given
by hand), a fake clock, and the view, motor and question stubs round it. Then the wiring: PipeHttp.h stamps the reply's
time, main.cpp ticks it every 50 ms, after RF_Backup.h.
   python3 dev/test_banksync/test_banksync.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INC = os.path.join(ROOT, 'TransmitterCode', 'include')
src = open(os.path.join(INC, 'BankSync.h')).read()
m = re.search(r'// BANKSYNC-LOGIC-BEGIN.*?\n(.*)// BANKSYNC-LOGIC-END', src, re.S)
assert m, 'the BANKSYNC-LOGIC markers were not found in BankSync.h'
logic = m.group(1)

prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
#define FLASHMEM
#define FRONTVIEW 0
#define PIDVIEW 45
#define RFGOVERNORVIEW_GLOBAL 55
#define WHAHWHAHMSG 25
static uint32_t now = 100000;
static uint32_t millis() { return now; }
static uint8_t PipeState = 0, ModalWaits = 0, CurrentView = FRONTVIEW, Banks = 4;
static bool BoundFlag = true, ModelMatched = true, MotorEnabled = false, LinkRatesToBanks = false;
static uint8_t BanksCount() { return Banks; }
// the pipe as PipeHttp.h has it
static int PipeReqId = 0, PipeRepId = -1, PipeRepCode = 0;
static char PipeRepBody[1600];
static uint32_t PipeReqSentMs = 0, PipeRepMs = 0;
static std::vector<std::string> sent;
static int PipeRequest(const char *path) { ++PipeReqId; sent.push_back(path); PipeReqSentMs = now; PipeRepId = -1; return PipeReqId; }
static bool PipeReplyReady(int id) { return PipeRepId == id; }
static bool PipeReplyLate() { return now - PipeReqSentMs > 9000; }
static void Reply(int id, int code, const char *body) { snprintf(PipeRepBody, sizeof(PipeRepBody), "%s", body); PipeRepCode = code; PipeRepId = id; PipeRepMs = now; }
static std::vector<std::string> boxes, logs; static int sounds = 0;
static void LogText(char *t, uint16_t, bool) { logs.push_back(t); }
static void PlaySound(uint16_t) { ++sounds; }
static void MsgBox(char *goback, char *prompt) { boxes.push_back(std::string(goback) + " | " + prompt); }
static const char *BakPageOf(uint8_t) { return "page RFView"; }
''' + logic + r'''
static int checks = 0, failures = 0;
#define CHECK(c, what) do { ++checks; if (!(c)) { ++failures; printf("   FAIL: %s\n", what); } } while (0)
static void tick(uint32_t ms) { for (uint32_t t = 0; t < ms; t += 50) { now += 50; BankSyncTick(); } }
static const char *OK4 = "{\"ok\":true,\"tx\":4,\"rates_follow\":false,\"selector\":4,\"rates_selector\":3,\"pid\":6,\"rate\":6}";
static const char *OK6 = "{\"ok\":true,\"tx\":6,\"rates_follow\":false,\"selector\":6,\"rates_selector\":0,\"pid\":6,\"rate\":6}";
static void pipeDownUp() { PipeState = 0; tick(500); PipeState = 2; }
int main()
{
    printf("- no pipe: nothing is sent\n");
    tick(5000); CHECK(sent.empty(), "nothing sent with the pipe down");
    printf("- the pipe comes up: told a moment later, once, and left alone when the count is right\n");
    PipeState = 2; tick(1000); CHECK(sent.empty(), "not in the first second (a page's own read goes first)");
    tick(1000); CHECK(sent.size() == 1 && sent[0] == "/api/tx/banks?n=4&rates=0", "told four banks, rates free");
    Reply(PipeReqId, 200, OK4); tick(500);
    CHECK(boxes.empty() && logs.empty() && sounds == 0, "four banks, a four-position line: no warning");
    tick(30000); CHECK(sent.size() == 1, "told once a session");
    printf("- Six banks turned on: told again; the line has four positions: the pilot is told\n");
    Banks = 6; tick(1400); CHECK(sent.size() == 1, "a moment to settle");
    tick(200); CHECK(sent.size() == 2 && sent[1] == "/api/tx/banks?n=6&rates=0", "told six");
    Reply(PipeReqId, 200, "{\"ok\":true,\"tx\":6,\"rates_follow\":false,\"selector\":4,\"rates_selector\":0,\"pid\":6,\"rate\":6}");
    tick(100);
    CHECK(boxes.size() == 1 && boxes[0].find("page FrontView") == 0 && boxes[0].find("has 4 positions; this model has 6") != std::string::npos, "the warning, back to the front view");
    CHECK(logs.size() == 1 && logs[0].find("6 banks") != std::string::npos && logs[0].find("4 positions") != std::string::npos, "logged");
    CHECK(sounds == 1, "the sound");
    tick(30000); CHECK(boxes.size() == 1 && sent.size() == 2, "said once");
    printf("- the warning waits for the motor to be off, a page it can be shown on, and no other question\n");
    Banks = 4; MotorEnabled = true; tick(2000); CHECK(sent.size() == 3 && sent[2] == "/api/tx/banks?n=4&rates=0", "told four again");
    Reply(PipeReqId, 200, "{\"ok\":true,\"tx\":4,\"selector\":6}"); tick(1000); CHECK(boxes.size() == 1, "not with the motor on");
    MotorEnabled = false; CurrentView = 10; tick(1000); CHECK(boxes.size() == 1, "not on another page");
    CurrentView = 50; ModalWaits = 1; tick(1000); CHECK(boxes.size() == 1, "not over another question");
    ModalWaits = 0; tick(100); CHECK(boxes.size() == 2 && boxes[1].find("page RFView") == 0 && boxes[1].find("has 6 positions; this model has 4") != std::string::npos, "on a Rotorflight page, back to it");
    CurrentView = FRONTVIEW;
    printf("- an older receiver (404): told nothing more that session\n");
    pipeDownUp(); tick(2000); CHECK(sent.size() == 4, "told afresh after the pipe came back");
    Reply(PipeReqId, 404, "not found"); tick(30000); CHECK(sent.size() == 4 && boxes.size() == 2, "no retry, no warning");
    printf("- no answer at all: a few tries, then left for the session\n");
    pipeDownUp(); tick(2000); CHECK(sent.size() == 5, "asked");
    tick(60000); CHECK(sent.size() == 8, "four asks in all, then no more");
    printf("- never while a page's own request waits on the pipe\n");
    pipeDownUp(); const int pageReq = PipeRequest("/api/msp?fn=101"); tick(3000); CHECK(sent.size() == 9 && sent.back() == "/api/msp?fn=101", "the page's ask stands alone");
    Reply(pageReq, 200, "00"); tick(200); CHECK(sent.size() == 9, "its answer has just come: the page reads it first");
    tick(300); CHECK(sent.size() == 10 && sent.back() == "/api/tx/banks?n=4&rates=0", "then ours");
    printf("- a page asks after us: ours is let go and asked again when the pipe is free\n");
    const int ours = PipeReqId; const int theirs = PipeRequest("/api/msp?fn=101"); (void)ours; tick(100);
    CHECK(sent.size() == 11, "theirs went");
    Reply(theirs, 200, "00"); tick(3600); CHECK(sent.size() == 12 && sent.back() == "/api/tx/banks?n=4&rates=0", "ours again after the pause");
    Reply(PipeReqId, 200, OK4); tick(500);
    printf("- the rates following the banks is told too, and a change of it tells again\n");
    LinkRatesToBanks = true; tick(2000); CHECK(sent.size() == 13 && sent.back() == "/api/tx/banks?n=4&rates=1", "rates follow");
    Reply(PipeReqId, 200, OK4); tick(500);
    printf("- the pipe down and up again: told afresh\n");
    pipeDownUp(); tick(2000); CHECK(sent.size() == 14, "told after the pipe came back");
    Reply(PipeReqId, 200, OK6); tick(500); CHECK(boxes.size() == 3 && boxes[2].find("has 6 positions; this model has 4") != std::string::npos, "a six-position line with four banks: warned");
    printf("- a reply without the selector (an unknown line): no warning\n");
    Banks = 6; tick(2000); Reply(PipeReqId, 200, "{\"ok\":true,\"tx\":6,\"selector\":0}"); tick(500); CHECK(boxes.size() == 3, "selector 0 is unknown");
    printf("\n%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
'''
failures = 0
with tempfile.TemporaryDirectory() as tmp:
    cpp = os.path.join(tmp, 't.cpp'); open(cpp, 'w').write(prog)
    exe = os.path.join(tmp, 't')
    r = subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Wno-unused-function', '-fsanitize=address,undefined', '-o', exe, cpp], capture_output=True, text=True)
    if r.returncode: print(r.stderr); sys.exit(1)
    r = subprocess.run([exe], capture_output=True, text=True); print(r.stdout, end=''); failures += r.returncode != 0
# the wiring
pipe = open(os.path.join(INC, 'PipeHttp.h')).read()
mainc = open(os.path.join(ROOT, 'TransmitterCode', 'src', 'main.cpp')).read()
def check(ok, what):
    global failures
    if not ok: failures += 1; print('   FAIL:', what)
print('- the wiring')
check('PipeRepMs = millis();' in pipe and 'static uint32_t PipeRepMs' in pipe, "PipeHttp.h stamps the reply's time (PipeRepMs)")
check(re.search(r'PipeModelGoneTick\(\);[^\n]*\n\s*BankSyncTick\(\);', mainc), 'main.cpp ticks BankSyncTick after PipeModelGoneTick in the 50 ms block')
check(mainc.index('#include "RF_Backup.h"') < mainc.index('#include "BankSync.h"'), 'BankSync.h is included after RF_Backup.h (BakPageOf)')
check('void BankSyncTick();' in open(os.path.join(INC, '1Definitions.h')).read(), 'BankSyncTick is declared in 1Definitions.h')
print('ok' if not failures else f'{failures} FAILED')
sys.exit(1 if failures else 0)
