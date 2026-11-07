#!/usr/bin/env python3
"""Host test of Beeper & name (B195, include/RF_Beeper.h, page 84): the real module over the fake screen, pipe and flight
controller of dev/test_fcsetup (taken from that test's source, so the two stay one), the fake extended with Rotorflight's
name (10 read / 11 write) and beeper (184 / 185, release/4.6.0 msp.c). Checked: the read fills the page (a switch ON =
its OFF flag clear); a save writes 11 then 185 then 250 and reads both back; only the page's ten bits change, every other
bit goes back as read; an empty name goes as one 0 byte; the tone is kept to 1-5; an unanswered box sends nothing; a
4 MB screen is refused; OK with edits asks "Save now?".
   python3 dev/test_beeper/test_beeper.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INC = os.path.join(ROOT, 'TransmitterCode', 'include')
base = open(os.path.join(ROOT, 'dev', 'test_fcsetup', 'test_fcsetup.py')).read()
prog = base[base.index("prog = r'''") + len("prog = r'''"):base.index("static int checks = 0, fails = 0;")]
cut = prog.index("''' + open(os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_SaveNow.h'))")
fakes = prog[:cut]
hook = '    case 250: fcReply(200, ""); return PipeReqId;'
assert hook in fakes, 'test_fcsetup changed: its fake flight controller has no 250'
fakes = fakes.replace(hook, hook + '''
    case 10: fcReply(200, hexOf((const uint8_t *)fcName.data(), (int)fcName.size())); return PipeReqId;
    case 11: fcName.assign((const char *)data, (size_t)len); while (!fcName.empty() && fcName.back() == 0) fcName.pop_back(); if (fcName.size() > 16) fcName.resize(16); fcReply(200, ""); return PipeReqId;
    case 184: fcReply(200, hexOf(beep, 9)); return PipeReqId;
    case 185: memcpy(beep, data, len < 9 ? len : 9); if (beep[4] < 1 || beep[4] > 5) beep[4] = 1; fcReply(200, ""); return PipeReqId;''')
fakes = fakes.replace('int MspAsk(uint8_t fn, const uint8_t *data, int len) {',
                      'static std::string fcName = "Goblin 700"; static uint8_t beep[9];\nint MspAsk(uint8_t fn, const uint8_t *data, int len) {')
src = (fakes.replace('#define RFSETUPVIEW 61', '#define RFSETUPVIEW 61\n#define BEEPERVIEW 84')
       + r'''
static bool bigScreen = true; static bool ScreenIsBig() { return bigScreen; }
static uint32_t GetValue(char *n) { if (!vals.count(n)) { NextionTextMissed = true; return 65535; } return (uint32_t)vals[n]; }
''' + open(os.path.join(INC, 'RF_SaveNow.h')).read()
       + open(os.path.join(INC, 'RF_FcSetup.h')).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '')
       + open(os.path.join(INC, 'RF_Beeper.h')).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '')
       + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void run(int n = 40) { for (int i = 0; i < n; ++i) { BeeperPoll(); now += 50; } }
static int asks(int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; }
static uint32_t U32(const uint8_t *b, int o) { return (uint32_t)b[o] | ((uint32_t)b[o + 1] << 8) | ((uint32_t)b[o + 2] << 16) | ((uint32_t)b[o + 3] << 24); }
static uint32_t F(int ev) { return 1u << (ev - 1); }
int main()
{
    // the flight controller: buzzer off for "armed" (16) and GPS (9, not on the page); beacon tone 3, its off flags = both (the default) + bit 20
    put32(beep, 0, F(16) | F(9)); beep[4] = 3; put32(beep, 5, F(10) | F(2) | (1u << 20));
    CurrentView = 47; StartBeeperView(); run();
    CHECK(CurrentView == BEEPERVIEW && asks(10) == 1 && asks(184) == 1 && fields["tn0"] == "Goblin 700" && fields["tn1"] == "3");
    CHECK(vals["sw1"] == 1 && vals["sw4"] == 0 && vals["sw5"] == 1 && vals["sw8"] == 1 && vals["sw9"] == 0 && vals["sw10"] == 0);
    // edits: armed beeps now (sw4 on), link lost silent (sw5 off), the beacon on the switch (sw9), tone 9 -> kept to 5, a new name
    vals["sw4"] = 1; vals["sw5"] = 0; vals["sw9"] = 1; fields["tn1"] = "9"; fields["tn0"] = "Goblin RAW";
    BeeperWasEdited(); CHECK(Bp_Was_Edited && cmds.back() == "vis b3,1");
    fcLog.clear(); SaveBeeper(); run();
    CHECK(fcLog.size() == 5 && fcLog[0].fn == 11 && fcLog[1].fn == 185 && fcLog[2].fn == 250 && fcLog[3].fn == 10 && fcLog[4].fn == 184);
    CHECK(fcName == "Goblin RAW" && beep[4] == 5);
    CHECK(U32(beep, 0) == (F(9) | F(2)));                       // armed now beeps (16 clear), link lost silent (2 set), GPS (9) as read
    CHECK(U32(beep, 5) == (F(2) | (1u << 20)));                // the beacon on the switch (10 clear); link lost and bit 20 as read
    CHECK(!Bp_Was_Edited && fields["busy"] == "Saved, and read back the same.");
    // an empty name: one 0 byte, and the flight controller has no name
    fields["tn0"] = ""; BeeperWasEdited(); fcLog.clear(); SaveBeeper(); run();
    CHECK(fcLog[0].fn == 11 && fcLog[0].data == "00" && fcName.empty() && fields["tn0"] == "");
    // an unanswered switch: nothing written
    vals.erase("sw3"); BeeperWasEdited(); fcLog.clear(); boxes = 0; SaveBeeper(); run();
    CHECK(fcLog.empty() && Bp_Was_Edited);
    vals["sw3"] = 1;
    // OK with edits asks "Save now?" (Discard: back to the menu, nothing written)
    saveNowAnswer = 0; saveNowAsked = 0; fcLog.clear(); EndBeeperView();
    CHECK(saveNowAsked == 1 && fcLog.empty() && CurrentView == 47);
    // a 4 MB screen (or one too old to say): refused at the menu, nothing asked
    bigScreen = false; fcLog.clear(); boxes = 0; StartBeeperView();
    CHECK(boxes == 1 && lastBox.find("16 MB") != std::string::npos && fcLog.empty() && CurrentView == 47);
    printf("test_beeper: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
''')
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(src)
import atexit, shutil as _sh; atexit.register(_sh.rmtree, d, True)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:4000]); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
