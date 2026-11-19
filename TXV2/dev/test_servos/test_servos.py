#!/usr/bin/env python3
"""THE SERVOS PAGE AFTER A READ THAT FAILS, AND AFTER A SAVE THAT FAILS (B211, the fifteenth review; reviewer B's experiment, adopted).
ServoFail is the failure routine of the page's READ too. Since the eleventh review it draws no field ("what was typed stays") - and ServoHave was
never cleared: after a failed read the seven numbers and two switches of the servo LAST LOOKED AT stood under the title "Servo 1 of 4", Save open,
and Save wrote the tail servo's centre, limits, rate and reverse into swash servo 1. Now: nothing is in hand while a read runs, and a page whose read
failed is left for the menu behind its box (RF_SaveNow.h RfLeaveNotRead); behind a SAVE that failed the page stays, what was typed stays - and the
two switches are written as they are in hand (the screen turns a switch at the touch: a tap not obeyed left one turned that Save would not write).
The REAL RF_Servos.h and RF_SaveNow.h over dev/test_basics' fake screen and a fake flight controller with four servos.
   python3 dev/test_servos/test_servos.py [another RF_Servos.h]"""
import os, subprocess, sys, tempfile
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src = open(os.path.join(ROOT, 'dev', 'test_basics', 'test_basics.py'), encoding='utf-8').read()
HDR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Servos.h')
head = src[:src.index("d = tempfile.mkdtemp()")].replace("ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))", "ROOT = %r" % ROOT)
ns = {}; exec(head, ns); prog = ns['prog']
basics = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Basics.h'), encoding='utf-8').read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '')
assert prog.count(basics) == 1
servos = open(HDR, encoding='utf-8').read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '')
helpers = r'''
#define SERVOVIEW 60
static uint16_t RdU16(const uint8_t *b, int o) { return (uint16_t)(b[o] | (b[o + 1] << 8)); }
static void WrU16(uint8_t *b, int o, long v) { if (v < 0) v = 0; if (v > 65535) v = 65535; b[o] = (uint8_t)(v & 0xFF); b[o + 1] = (uint8_t)(v >> 8); }
static void SendValue(char *n, int v) { fields[n] = std::to_string(v); }
'''
a = '    fcReply(404, "unknown"); return PipeReqId;\n}'
assert prog.count(a) == 1
prog = prog.replace(a, '''    if (fn == 120) { if (fail120 > 0) { --fail120; fcReply(503, "the receiver did not answer"); return PipeReqId; } uint8_t b[1 + 4 * 16]; b[0] = 4; memcpy(b + 1, srv, 64); fcReply(200, hexOf(b, 65)); return PipeReqId; }
    if (fn == 212) { if (fail212 > 0) { --fail212; fcReply(503, "the receiver did not answer"); return PipeReqId; } memcpy(srv[data[0] & 3], data + 1, 16); fcReply(200, ""); return PipeReqId; }
    fcReply(404, "unknown"); return PipeReqId;\n}''')
b = "int MspAsk(uint8_t fn, const uint8_t *data, int len) {"
assert prog.count(b) == 1
prog = prog.replace(b, "static uint8_t srv[4][16]; static int fail120 = 0, fail212 = 0;\n" + b)
i = prog.index(basics)
prog = prog[:i] + helpers + servos + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void run(int n = 40) { for (int i = 0; i < n; ++i) { ServoPoll(); now += 250; } }
static int writes(int fn) { int k = 0; for (auto &r : fcLog) if (r.fn == fn) ++k; return k; }
static int cmdCount(const char *c) { int k = 0; for (auto &x : cmds) k += x == c; return k; }
static void sv(int i, unsigned centre, int mn, int mx, unsigned rate, unsigned flags) { uint8_t *b = srv[i]; memset(b, 0, 16); w16(b, 0, centre); w16(b, 2, (unsigned) mn & 0xFFFF); w16(b, 4, (unsigned) mx); w16(b, 6, 500); w16(b, 8, 500); w16(b, 10, rate); w16(b, 12, 0); w16(b, 14, flags); }
static void model() { sv(0, 1520, -700, 700, 333, 0); sv(1, 1520, -700, 700, 333, 1); sv(2, 1520, -700, 700, 333, 0); sv(3, 760, -350, 350, 560, 1); }   // three swash servos (1520 us, 333 Hz; the second reversed) and the TAIL servo (760 us, 560 Hz, reversed)
static bool servo1AsItWas() { return u16(srv[0], 0) == 1520 && u16(srv[0], 10) == 333 && u16(srv[0], 14) == 0; }
int main() {
    model();
    // S1. Visit 1: the servos are read; he looks at the tail servo (Servo > three times), changes nothing, OK
    CurrentView = ROTORFLIGHTVIEW; StartServoView(); CHECK(!ServoHave);                 // (nothing is in hand while the read runs)
    run(); CHECK(ServoHave && fields["tn0"] == "1520" && fields["t0"] == "Servo 1 of 4 (swashplate)");
    ServoNext(); ServoNext(); ServoNext(); CHECK(fields["tn0"] == "760" && fields["tn5"] == "560" && fields["tn7"] == "1" && fields["t0"] == "Servo 4 of 4 (tail)");
    EndServoView(); CHECK(CurrentView == ROTORFLIGHTVIEW);
    // S2. Visit 2 (the same model): THE READ FAILS. The page is LEFT - its box, then the menu; nothing is in hand, and a Save writes nothing
    //     (the page stayed, titled "Servo 1 of 4", with the tail servo's 760 us and 560 Hz in its boxes and Save open: servo 1 got them)
    boxes = 0; rfStarts = 0; fail120 = 1; fcLog.clear(); StartServoView(); CHECK(!ServoHave); run();
    printf("S2. the read failed (boxes %d: '%s'): view %d, the menu opened %d time(s), ServoHave %d\n", boxes, lastBox.substr(0, 25).c_str(), CurrentView, rfStarts, (int) ServoHave);
    CHECK(boxes == 1 && lastBox.find("Could not read the servos") == 0 && !ServoHave && ServoStep == SRV_IDLE && rfStarts == 1 && CurrentView == ROTORFLIGHTVIEW);
    fields["tn6"] = "50"; ServoWasEdited(); fcLog.clear(); SaveServo(); run(); CHECK(fcLog.empty() && servo1AsItWas());
    ServoNext(); ServoPrevious(); CHECK(fcLog.empty());                                 // (and no stepping through servos that are not in hand)
    Servo_Was_Edited = false;
    // S3. THE MENU WILL NOT OPEN (the motor switch on): the page is put up again and SAYS that it was not read; Save writes nothing
    menuShut = true; boxes = 0; rfStarts = 0; fail120 = 1; fcLog.clear(); cmds.clear(); CurrentView = ROTORFLIGHTVIEW; StartServoView(); run();
    CHECK(boxes == 1 && !ServoHave && rfStarts == 0 && CurrentView == SERVOVIEW && cmdCount("page ServoView") == 2 && fields["busy"] == "NOT READ. Safety on, motor off - then OK.");
    fields["tn6"] = "50"; ServoWasEdited(); fcLog.clear(); SaveServo(); run(); CHECK(fcLog.empty() && servo1AsItWas());
    menuShut = false; Servo_Was_Edited = false;
    // S4. a box that another page came over: neither the menu nor this page is put over that page
    boxes = 0; rfStarts = 0; fail120 = 1; cmds.clear(); CurrentView = ROTORFLIGHTVIEW; StartServoView(); overtakeNextBox = true; run();
    CHECK(boxes == 1 && rfStarts == 0 && !ServoHave && CurrentView == FRONTVIEW_FOR_TEST && cmdCount("page ServoView") == 1);
    QuestionOvertaken = false;
    // S5. the next visit, the read works: servo 1's OWN numbers
    CurrentView = ROTORFLIGHTVIEW; StartServoView(); run(); CHECK(ServoHave && fields["tn0"] == "1520" && fields["tn5"] == "333" && fields["tn7"] == "0" && fields["t0"] == "Servo 1 of 4 (swashplate)");
    // S6. A SAVE THAT FAILS: the page STAYS, what was typed stays as the screen has it - and THE TWO SWITCHES ARE WRITTEN AS THEY ARE IN HAND. The screen
    //     turns a switch at the touch; a tap made as the failure's box came up is not obeyed (its page had gone): the switch stayed turned on the screen
    //     and not in hand, and "Save again" - which writes what is in hand - would not have written what the page showed
    fields["tn6"] = "50"; ServoWasEdited(); boxes = 0; rfStarts = 0; fail212 = 1; fcLog.clear(); SaveServo();
    fields["tn6"] = "70"; fields["tn7"] = "1"; fields["tn8"] = "1";                     // (while it runs: a number typed; the two switches turned by taps that are not obeyed)
    run();
    printf("S6. a save failed (boxes %d: '%s'): view %d; the speed box '%s'; the REVERSE switch shows %s, in hand %d\n", boxes, lastBox.substr(0, 11).c_str(), CurrentView, fields["tn6"].c_str(), fields["tn7"].c_str(), ServoRev);
    CHECK(boxes == 1 && lastBox.find("Not written") == 0 && ServoHave && rfStarts == 0 && CurrentView == SERVOVIEW && Servo_Was_Edited && servo1AsItWas());
    CHECK(fields["tn6"] == "70" && fields["tn7"] == "0" && fields["tn8"] == "0" && ServoRev == 0 && ServoGeo == 0 && fields["t0"] == "Servo 1 of 4 (swashplate)");
    fcLog.clear(); SaveServo(); run();                                                  // Save again: what the page shows
    CHECK(writes(212) == 1 && u16(srv[0], 12) == 70 && u16(srv[0], 14) == 0 && u16(srv[0], 0) == 1520 && fields["busy"] == "Saved, and read back the same.");
    // S7. ... and a switch tapped while a save runs IS obeyed: in hand and on the screen alike behind the failure's box, and Save again writes it
    ServoReverseTapped(); CHECK(ServoRev == 1 && fields["tn7"] == "1" && Servo_Was_Edited);
    fail212 = 1; boxes = 0; fcLog.clear(); SaveServo(); ServoGeometryTapped(); run();
    CHECK(boxes == 1 && fields["tn7"] == "1" && fields["tn8"] == "1" && ServoRev == 1 && ServoGeo == 1 && u16(srv[0], 14) == 0);
    fcLog.clear(); SaveServo(); run(); CHECK(writes(212) == 1 && u16(srv[0], 14) == 3);
    // B10 (the sixteenth review): NOTHING IN HAND - nothing is an edit (OK asked "Save now?" for it, the save returned at once), and a Save refused
    // for it does not leave "close when saved" standing for a later Save
    { const bool h = ServoHave, e = Servo_Was_Edited; ServoHave = false; Servo_Was_Edited = false; ServoWasEdited(); CHECK(!Servo_Was_Edited);
      RfLeaveAfterSave = true; SaveServo(); CHECK(!RfLeaveAfterSave);
      ServoHave = true; ServoWasEdited(); CHECK(Servo_Was_Edited); ServoHave = h; Servo_Was_Edited = e; }
    printf("test_servos: %d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-const-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit(1)
rc = subprocess.run([os.path.join(d, 't')]).returncode
if not rc: print('ALL GOOD')
sys.exit(rc)
