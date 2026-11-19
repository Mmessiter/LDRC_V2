#!/usr/bin/env python3
"""Host test of e100 (B211, Malcolm 18 Nov 2026): "I suggest that opening the models page while armed should be disabled. I.e. impossible,
not merely discouraged."
The screen's Models button is function 4 of main.cpp's NumberedFunctions: GotoModelsViewAsked (MenuOptions.h), which asks ModelsPageRefused:
refused while RadiosMustBeOff() (FlightGuard.h: the safety off - with no safety switch, the motor on) or ModelSeemsArmed() (Parameters.h) - the
warning sound, a kept line (KeepScreenNote), NO box, the page not opened. Otherwise GotoModelsView as before (its "Open Models anyway?" with a
model connected).
LIFTED AND RUN ON THE MAC: ModelsPageRefused, GotoModelsViewAsked, GotoModelsView (renamed, behind a counting stand-in), SafetyIsDefined,
SafetyIsOff, RadiosMustBeOff, ArmingManaged, ModelSeemsArmed, KeepScreenNote (with a stand-in DeferLogText that keeps "not the same line twice").
STOOD IN: PlaySound, MsgBox, GetConfirmation, GetYesOrNo, SendCommand and the Models page's drawing routines.
THEN THE SOURCES: entry 4 is GotoModelsViewAsked; every other road to the Models page is listed and must be one of the page's own.
And, if the screen's page file is found, the screen side: one button sends function 4 (the main menu's), no page sends "page ModelsView" itself.
e100b (18 Nov 2026): ModelSeemsArmed is asked only where a safety switch is defined (no safety switch: the motor switch decides) - the
lock-out (no safety switch, a Rotorflight model: refused at every start) is now a real assertion: OPENED. And THE MOTOR SWITCH ON THE MODELS
PAGE: Motor_sign.h MotorEnabledHasChanged LIFTED AND RUN (a second program): on the Models page with the wheel on another row the model that
was in use when the page was opened is put back (ModelNumber, ReadOneModel once) BEFORE the front page comes; nowhere else.
   python3 dev/test_modelsarmed/test_modelsarmed.py [TransmitterCode folder] [the screen's hmi/pages.json]
(The screen's page file is taken from the second word, or found beside the tree - NOT from the environment: dev/release_v1b.py's gate hands
the tests only the variables on its list, TEST_SWITCHES, and test_release_gate.py holds every test to that list.)"""
import os, re, subprocess, sys, tempfile, json
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'TransmitterCode')
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()
def lift(rel, pattern):
    s = src(rel); m = re.search(pattern, s)
    if not m: raise SystemExit('FAIL: not found in %s: %s' % (rel, pattern))
    i = m.start(); j = s.index('{', m.end() - 1); d = 0
    for k in range(j, len(s)):
        if s[k] == '{': d += 1
        elif s[k] == '}':
            d -= 1
            if d == 0: return s[i:k + 1] + '\n'
    raise SystemExit('unbalanced: ' + pattern)
D1 = src('include/1Definitions.h')
def define(n): return re.search(r'^#define %s[ \t]+\S+' % n, D1, re.M).group(0)

L_SAFEDEF = lift('include/FlightGuard.h', r'\nbool SafetyIsDefined\(\)\s*\{')
L_SAFEOFF = lift('include/FlightGuard.h', r'\nbool SafetyIsOff\(\)\s*\{')
L_RADIOS = lift('include/FlightGuard.h', r'\nbool RadiosMustBeOff\(\)\s*\{')
L_ARMMAN = lift('include/1Definitions.h', r'\nbool ArmingManaged\(\)\s*\{')
L_SEEMS = lift('include/Parameters.h', r'\nbool ModelSeemsArmed\(char \*why, size_t n\)\s*\{')
L_GOTO = lift('include/MenuOptions.h', r'\nvoid GotoModelsView\(\)\s*\{').replace('void GotoModelsView()', 'void GotoModelsView_real()', 1)
L_REFUSED = lift('include/MenuOptions.h', r'\n(?:FLASHMEM\s+)?bool ModelsPageRefused\(\)\s*\{')   # (e100b: FLASHMEM)
L_ASKED = lift('include/MenuOptions.h', r'\n(?:FLASHMEM\s+)?void GotoModelsViewAsked\(\)\s*\{')
L_MOTOR = lift('include/Motor_sign.h', r'\nvoid MotorEnabledHasChanged\(\)[^{;]*\{')   # (e100b: the motor switch on the Models page - run in the second program)
LF = src('include/LogFiles.h')
m = re.search(r'\n#define SCREEN_NOTES_MOST.*?\n(?=FLASHMEM void KeepScreenReason)', LF, re.S)
if not m: raise SystemExit('FAIL: KeepScreenNote and its budget not found in LogFiles.h')
L_KEEP = m.group(0)

PROG = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
#define FLASHMEM
#define FASTRUN
#define CHANNELSUSED 16
''' + define('WHAHWHAHMSG') + '\n' + define('MODELSVIEW') + r'''
#define FRONTVIEW 1
#define RXSETUPVIEW 2
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)
// ---- the transmitter's state
static uint8_t SafetySwitch = 0, ArmingChannel = 0, RotorFlight_V = 0;
static bool SafetyON = false, MotorEnabled = false, BindingEnabled = false, BuddyPupilOnWireless = false, ModelMatched = false, BoundFlag = false;
static uint16_t SendBuffer[CHANNELSUSED + 1];
static uint32_t CurrentView = FRONTVIEW, ModelNumber = 3, PreviousModelNumber = 0;
static char MOD[8], Mfiles[8];
static char pModelsView[] = "page ModelsView", pRXSetupView[] = "page RXSetupView";
// ---- the stand-ins: what the routines say and do
static int sounds = 0, lastSound = -1, boxes = 0, gotoCalls = 0, pagesOpened = 0, deferred = 0;
static bool confirmAnswer = true;
static std::vector<std::string> keptCalls, deferredLines;
static void PlaySound(uint16_t s) { ++sounds; lastSound = s; }
static void MsgBox(char *, char *) { ++boxes; }
static bool GetConfirmation(char *, char *) { ++boxes; return confirmAnswer; }
static void GetYesOrNo(uint16_t = 0) { ++boxes; }
static void SendCommand(char *c) { if (!strcmp(c, "page ModelsView")) ++pagesOpened; }
static void CheckModelImageFileName() {}
static void ShowModelImage() {}
static void UpdateModelsNameEveryWhere() {}
static void BuildDirectory() {}
static void LoadFileSelector() {}
static void ShowFileNumber() {}
static void LoadModelSelector() {}
static char DeferredLastStandIn[48];
static void DeferLogText(const char *text, bool);
''' + L_SAFEDEF + L_SAFEOFF + L_RADIOS + L_ARMMAN + L_SEEMS + r'''
// KeepScreenNote, its budget and its "not the same line twice" - lifted from LogFiles.h
''' + L_KEEP.replace('DeferredLast', 'DeferredLastStandIn').replace('static char DeferredLastStandIn[48];', '') + r'''
// DeferLogText as LogFiles.h has it, without the card: "not the same thing twice", the line kept last remembered
static void DeferLogText(const char *text, bool) { if (!text || !*text || !strcmp(text, DeferredLastStandIn)) return; strncpy(DeferredLastStandIn, text, 47); deferredLines.push_back(text); ++deferred; }
static void KeepScreenNoteCounted(const char *line, bool reason) { keptCalls.push_back(line); KeepScreenNote(line, reason); }
#define KeepScreenNote KeepScreenNoteCounted
''' + L_GOTO + r'''
static void GotoModelsView() { ++gotoCalls; GotoModelsView_real(); }
''' + L_REFUSED + L_ASKED + r'''
#undef KeepScreenNote
static void Reset() {
    sounds = boxes = gotoCalls = pagesOpened = deferred = 0; lastSound = -1; keptCalls.clear(); deferredLines.clear(); DeferredLastStandIn[0] = 0;
    ScreenNotesKept = ScreenReasonsKept = 0; ScreenNotesNotKept = 0; CurrentView = FRONTVIEW; confirmAnswer = true;
}
static void Model(bool rotorflight, uint8_t armCh) { RotorFlight_V = rotorflight ? 2 : 0; ArmingChannel = armCh; for (auto &v : SendBuffer) v = 1500; }
static void Connected(bool c) { ModelMatched = BoundFlag = c; }
// the button pressed, and what came of it
static bool Refused() { Reset(); GotoModelsViewAsked(); return gotoCalls == 0; }
static void ExpectRefused(int line) {
    Reset(); GotoModelsViewAsked();
    const bool ok = gotoCalls == 0 && pagesOpened == 0 && CurrentView == FRONTVIEW && sounds == 1 && lastSound == WHAHWHAHMSG && boxes == 0
                    && keptCalls.size() == 1 && keptCalls[0] == "Models page not opened: it may fly";
    ++checks; if (!ok) { ++fails; printf("FAIL (scene at line %d): refusal expected - page calls %d, pages %d, view %u, sounds %d (last %d), boxes %d, kept %zu\n",
                                       line, gotoCalls, pagesOpened, (unsigned)CurrentView, sounds, lastSound, boxes, keptCalls.size()); }
}
static void ExpectOpened(int line, int questions) {
    Reset(); GotoModelsViewAsked();
    const bool ok = gotoCalls == 1 && pagesOpened == 1 && CurrentView == MODELSVIEW && sounds == 0 && keptCalls.empty() && boxes == questions;
    ++checks; if (!ok) { ++fails; printf("FAIL (scene at line %d): page expected - page calls %d, pages %d, view %u, sounds %d, boxes %d (want %d), kept %zu\n",
                                       line, gotoCalls, pagesOpened, (unsigned)CurrentView, sounds, boxes, questions, keptCalls.size()); }
}
int main() {
    // 1. A SAFETY SWITCH DEFINED. Safety OFF: refused - with a model connected or none, the motor on or off; Rotorflight or not
    SafetySwitch = 5; SafetyON = false;
    for (int rf = 0; rf < 2; ++rf) for (int con = 0; con < 2; ++con) for (int mot = 0; mot < 2; ++mot) {
        Model(rf, rf ? 6 : 0); Connected(con); MotorEnabled = mot; ExpectRefused(__LINE__);
    }
    // 2. Safety ON, motor off: opened - nothing said by the new routine; with a model connected the old question (one box), without none
    SafetyON = true; MotorEnabled = false;
    Model(false, 0); Connected(false); ExpectOpened(__LINE__, 0);
    Model(false, 0); Connected(true);  ExpectOpened(__LINE__, 1);
    Model(true, 6);  Connected(false); ExpectOpened(__LINE__, 0);   // a Rotorflight model whose arming the transmitter manages: the safety drives it
    Model(true, 6);  Connected(true);  ExpectOpened(__LINE__, 1);
    // ... and the old question answered No: the page stays shut (as before)
    Model(false, 0); Connected(true); Reset(); confirmAnswer = false; GotoModelsViewAsked(); CHECK(gotoCalls == 1 && pagesOpened == 0 && CurrentView == FRONTVIEW && sounds == 0);
    // 2b. Safety ON, MOTOR ON (a safety switch defined: the motor switch alone is not the rule): opened
    MotorEnabled = true; Model(false, 0); Connected(false); ExpectOpened(__LINE__, 0); MotorEnabled = false;
    // 3. NO SAFETY SWITCH: the motor switch on - refused; off - opened (a model that is not a Rotorflight one)
    SafetySwitch = 0; SafetyON = false; Model(false, 0);
    for (int con = 0; con < 2; ++con) { Connected(con); MotorEnabled = true; ExpectRefused(__LINE__); MotorEnabled = false; ExpectOpened(__LINE__, con); }
    // 3b. NO SAFETY SWITCH, a Rotorflight model with its arming channel in range (managed): SafetyON is false whenever no safety switch is
    //     defined (Switches.h), and ModelSeemsArmed read it as "the safety is off" - the page was refused at every start (the e100 test work's
    //     lock-out). e100b: ModelSeemsArmed is asked only where a safety switch is defined - OPENED with the motor off; refused with it on.
    Model(true, 6); Connected(false); MotorEnabled = false; ExpectOpened(__LINE__, 0);
    Model(true, 6); Connected(true);  MotorEnabled = false; ExpectOpened(__LINE__, 1);    // (connected: the old question, as ever)
    Model(true, 6); Connected(false); MotorEnabled = true;  ExpectRefused(__LINE__);
    Model(true, 6); Connected(true);  MotorEnabled = true;  ExpectRefused(__LINE__);
    Model(true, 16); Connected(false); MotorEnabled = false; ExpectOpened(__LINE__, 0);
    // 3c. NO SAFETY SWITCH, an arming channel the transmitter does NOT manage (binding / a buddy pupil) standing HIGH, the motor off: e100b asks
    //     ModelSeemsArmed only where a safety switch is defined - OPENED (with a model connected: the old question "Open Models anyway?" stands)
    for (int k = 0; k < 2; ++k) { BindingEnabled = (k == 0); BuddyPupilOnWireless = (k == 1);
        Model(true, 6); SendBuffer[5] = 2000; Connected(false); MotorEnabled = false; ExpectOpened(__LINE__, 0);
        Model(true, 6); SendBuffer[5] = 2000; Connected(true);  MotorEnabled = false; ExpectOpened(__LINE__, 1);
        Model(true, 6); SendBuffer[5] = 2000; Connected(false); MotorEnabled = true;  ExpectRefused(__LINE__); }
    BindingEnabled = BuddyPupilOnWireless = false; Connected(false); MotorEnabled = false;
    printf("NOTE (e100b): no safety switch - the motor switch alone decides; an unmanaged arming channel standing high is NOT a refusal then (connected: the old question)\n");
    // 4. ModelSeemsArmed's SECOND BRANCH: Rotorflight found, arming channel in range, but NOT managed (binding, or a buddy pupil):
    //    the channel's own value decides - 1800 and above refused, below opened. The safety ON throughout (RadiosMustBeOff false).
    SafetySwitch = 5; SafetyON = true; MotorEnabled = false; Connected(false);
    for (int k = 0; k < 2; ++k) {
        BindingEnabled = (k == 0); BuddyPupilOnWireless = (k == 1);
        Model(true, 6); SendBuffer[5] = 2000; ExpectRefused(__LINE__);
        Model(true, 6); SendBuffer[5] = 1800; ExpectRefused(__LINE__);
        Model(true, 6); SendBuffer[5] = 1799; ExpectOpened(__LINE__, 0);
        Model(true, 6); SendBuffer[5] = 1000; ExpectOpened(__LINE__, 0);
        Model(true, 16); SendBuffer[15] = 2000; ExpectRefused(__LINE__);         // the last channel
        // a model that is NOT a Rotorflight one: that branch never refuses, whatever the channel says
        Model(false, 6); SendBuffer[5] = 2000; ExpectOpened(__LINE__, 0);
        // an arming channel out of range: never asked
        Model(true, 0); SendBuffer[5] = 2000; ExpectOpened(__LINE__, 0);
        Model(true, 17); for (auto &v : SendBuffer) v = 2000; ExpectOpened(__LINE__, 0);
    }
    BindingEnabled = BuddyPupilOnWireless = false;
    // ... managed (not binding, no pupil), the safety ON and the channel high (a front switch's channel parked high): the safety decides, opened
    Model(true, 6); SendBuffer[5] = 2000; ExpectOpened(__LINE__, 0);
    // 5. THE REFUSAL TEN TIMES: ten sounds, ten notes asked to be kept, never a box, never the page
    SafetyON = false; Model(false, 0); Connected(true); Reset();
    for (int i = 0; i < 10; ++i) GotoModelsViewAsked();
    CHECK(sounds == 10); CHECK(keptCalls.size() == 10); CHECK(boxes == 0); CHECK(gotoCalls == 0); CHECK(pagesOpened == 0); CHECK(CurrentView == FRONTVIEW);
    // ... the REAL KeepScreenNote keeps the same line once (not the same thing twice): one place in the store, one in the budget
    CHECK(deferred == 1); CHECK(ScreenNotesKept == 1); CHECK(ScreenNotesNotKept == 0);
    // ... pressed between other kept lines (the motor switch going on and off: DeferLogText's own lines), each press is a new line - but within
    //     the screen notes' budget (SCREEN_NOTES_MOST), the rest counted: these presses alone never fill the store
    Reset();
    for (int i = 0; i < 20; ++i) { DeferLogText(i & 1 ? "Motor Off" : "Motor On", true); GotoModelsViewAsked(); }
    CHECK(sounds == 20); CHECK(boxes == 0); CHECK(ScreenNotesKept == SCREEN_NOTES_MOST); CHECK(ScreenNotesNotKept == 20 - SCREEN_NOTES_MOST);
    int presses = 0; for (auto &l : deferredLines) presses += l == "Models page not opened: it may fly";
    CHECK(presses == SCREEN_NOTES_MOST);
    printf("NOTE: refusals between other lines use the screen notes' whole budget (%d), then are counted; notes behind them that matter are counted, not kept\n", SCREEN_NOTES_MOST);
    printf("test_modelsarmed (run): %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
bad = False
d = tempfile.mkdtemp()
open(os.path.join(d, 't.cpp'), 'w').write(PROG)
r = subprocess.run(['c++', '-std=c++17', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-fsanitize=address,undefined',
                    '-o', os.path.join(d, 't'), os.path.join(d, 't.cpp')], capture_output=True, text=True)
if r.returncode:
    print(r.stderr[:3000]); print('FAIL: the lifted routines do not compile'); sys.exit(1)
r = subprocess.run([os.path.join(d, 't')], capture_output=True, text=True)
print(r.stdout.strip())
if r.stderr.strip(): print(r.stderr.strip()[:2000])
bad = r.returncode != 0
run_line = [l for l in r.stdout.splitlines() if l.startswith('test_modelsarmed (run)')]
run_checks = int(re.search(r'(\d+) checks', run_line[0]).group(1)) if run_line else 0
run_fails = int(re.search(r'(\d+) failures', run_line[0]).group(1)) if run_line else 1

# ---------------------------------------------------------------- (e100b) THE MOTOR SWITCH ON THE MODELS PAGE: Motor_sign.h MotorEnabledHasChanged, LIFTED AND RUN
PROG2 = r"""
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
#define FLASHMEM
#define FASTRUN
""" + '\n'.join(define(n) for n in ('NORMAL', 'FRONTVIEW', 'MODELSVIEW', 'MOTORON', 'MOTOROFF', 'PLSTURNOFF')) + r"""
#define PIDVIEW_STANDIN 77
#define CALIBRATING_STANDIN 9
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)
// ---- the transmitter's state the routine reads and writes
static bool MotorEnabled = false, LedWasRed = false, BuddyPupilOnWireless = false, FlightRestart = false, SendNoData = false, AnnounceBanks = false, UseLog = false;
static bool Reading_PIDS_Now, Reading_PIDS_Advanced_Now, Reading_RATES_Now, Reading_RATES_Advanced_Now, Reading_GOV_Now, Reading_GOV_Config_Now;
static uint32_t CurrentView = FRONTVIEW, ModelNumber = 3, PreviousModelNumber = 3, MotorStartTime = 0, PausedSecs = 0, MotorOnSeconds = 0, LastSeconds = 0;
static uint8_t CurrentMode = NORMAL, ModalWaits = 0;
static char WarnOff[] = "vis Warning,0";
static bool follows = false;
// ---- the stand-ins: everything said and done goes into one list, in order
static std::vector<std::string> ev;
static uint32_t modelInUse = 3;    // what ReadOneModel last read into the memory in use
static int reads = 0;
static void note(const std::string &e) { ev.push_back(e); }
static bool ReadOneModel(uint32_t m) { ++reads; modelInUse = m; note("ReadOneModel(" + std::to_string(m) + ") ModelNumber=" + std::to_string(ModelNumber) + " view=" + std::to_string(CurrentView)); return true; }
static bool RfVerifyFollows() { note(std::string("RfVerifyFollows=") + (follows ? "1" : "0")); return follows; }
static void LogFrontPageReason(const char *, const char *, const char * = nullptr) { note("LogFrontPageReason"); }
static void GotoFrontView() { note("GotoFrontView ModelNumber=" + std::to_string(ModelNumber) + " in use=" + std::to_string(modelInUse)); CurrentView = FRONTVIEW; }
static void PlaySound(int s) { note("PlaySound(" + std::to_string(s) + ")"); }
static void DelayWithDog(uint32_t) {}
static void ShowMotor() { note("ShowMotor"); }
static void ShowMotorTimer() {}
static void LogMotor(bool) {}
static void SendCommand(char *) {}
static uint32_t millis() { return 1000; }
""" + L_MOTOR + r"""
static void Scene(uint32_t view, uint32_t prev, uint32_t now, bool ledRed = false, uint8_t modal = 0, uint8_t mode = NORMAL) {
    ev.clear(); reads = 0; MotorEnabled = true; LedWasRed = ledRed; ModalWaits = modal; CurrentMode = mode; CurrentView = view; PreviousModelNumber = prev; ModelNumber = now; modelInUse = now;
    SendNoData = false; BuddyPupilOnWireless = false; FlightRestart = false;
    Reading_PIDS_Now = Reading_PIDS_Advanced_Now = Reading_RATES_Now = Reading_RATES_Advanced_Now = Reading_GOV_Now = Reading_GOV_Config_Now = false;
    MotorEnabledHasChanged();
}
static int at(const std::string &head) { for (size_t i = 0; i < ev.size(); ++i) if (ev[i].compare(0, head.size(), head) == 0) return (int) i; return -1; }
static int count(const std::string &head) { int n = 0; for (auto &e : ev) n += e.compare(0, head.size(), head) == 0; return n; }
static void dump(int line) { printf("   (scene at line %d) events:", line); for (auto &e : ev) printf(" [%s]", e.c_str()); printf("\n"); }
int main() {
    // M1. ON THE MODELS PAGE, THE WHEEL ON ANOTHER ROW (model 7 loaded by the wheel; the page was opened with model 3): model 3 put back -
    //     ModelNumber 3, ReadOneModel(3) once, BEFORE the front page comes; the front page then has model 3 in use
    for (int f = 0; f < 2; ++f) { follows = f; Scene(MODELSVIEW, 3, 7);
        const int r = at("ReadOneModel("), g = at("GotoFrontView"), l = at("LogFrontPageReason"), v = at("RfVerifyFollows");
        CHECK(ModelNumber == 3); CHECK(modelInUse == 3); CHECK(reads == 1); CHECK(at("ReadOneModel(3) ModelNumber=3 view=5") == r && r >= 0);
        CHECK(g >= 0 && r < g && r < l); CHECK(ev[g] == "GotoFrontView ModelNumber=3 in use=3"); CHECK(CurrentView == FRONTVIEW);
        CHECK(v >= 0 && v < r);   // (the read-back's question is asked first - its answer decides the reading flags only; the put-back follows either way)
        CHECK(count("GotoFrontView") == 1 && count("ShowMotor") == 1);
        if (fails) dump(__LINE__); }
    // ... with a save's read-back being followed (RfVerifyFollows): the reading flags it holds are NOT put down; without: they are (as before)
    follows = true; Scene(MODELSVIEW, 3, 7); { Reading_PIDS_Now = true; ev.clear(); reads = 0; CurrentView = MODELSVIEW; ModelNumber = 7; MotorEnabledHasChanged(); CHECK(Reading_PIDS_Now); CHECK(reads == 1 && ModelNumber == 3); }
    follows = false; Scene(MODELSVIEW, 3, 7); { Reading_PIDS_Now = true; ev.clear(); reads = 0; CurrentView = MODELSVIEW; ModelNumber = 7; MotorEnabledHasChanged(); CHECK(!Reading_PIDS_Now); CHECK(reads == 1 && ModelNumber == 3); }
    // M2. ON THE MODELS PAGE, NO OTHER ROW CHOSEN: nothing read; the front page comes
    follows = false; Scene(MODELSVIEW, 3, 3); CHECK(reads == 0); CHECK(ModelNumber == 3); CHECK(at("GotoFrontView") >= 0); CHECK(CurrentView == FRONTVIEW);
    // M3. ANY OTHER VIEW (a Rotorflight page, the menu ...), even with ModelNumber != PreviousModelNumber left from an earlier visit: nothing of it runs
    for (uint32_t v : {(uint32_t) PIDVIEW_STANDIN, (uint32_t) 2, (uint32_t) MODELSVIEW + 1}) { Scene(v, 3, 7); CHECK(reads == 0); CHECK(ModelNumber == 7); CHECK(at("GotoFrontView") >= 0); }
    Scene(FRONTVIEW, 3, 7); CHECK(reads == 0); CHECK(ModelNumber == 7); CHECK(at("GotoFrontView") < 0);   // (on the front page already: no front page asked for)
    // M4. A BOX WAITING, or OUTSIDE THE NORMAL MODE: the front page does not come, nothing put back (as before)
    Scene(MODELSVIEW, 3, 7, false, 1); CHECK(reads == 0); CHECK(ModelNumber == 7); CHECK(at("GotoFrontView") < 0); CHECK(CurrentView == MODELSVIEW);
    Scene(MODELSVIEW, 3, 7, false, 0, CALIBRATING_STANDIN); CHECK(reads == 0); CHECK(ModelNumber == 7); CHECK(at("GotoFrontView") < 0); CHECK(CurrentView == MODELSVIEW);
    // M5. THE MOTOR REFUSED (red light: "please turn off"): the motor put off again, nothing put back, no front page
    Scene(MODELSVIEW, 3, 7, true); CHECK(!MotorEnabled); CHECK(SendNoData); CHECK(reads == 0); CHECK(ModelNumber == 7); CHECK(at("GotoFrontView") < 0); CHECK(at("PlaySound(" + std::to_string(PLSTURNOFF) + ")") >= 0);
    // ... the same red light in a restart in flight (FlightRestart): not refused - the model put back as in M1
    ev.clear(); reads = 0; MotorEnabled = true; LedWasRed = true; FlightRestart = true; ModalWaits = 0; CurrentMode = NORMAL; CurrentView = MODELSVIEW; PreviousModelNumber = 3; ModelNumber = 7; MotorEnabledHasChanged();
    CHECK(reads == 1 && ModelNumber == 3 && at("GotoFrontView") > at("ReadOneModel(")); FlightRestart = false;
    // M6. THE MOTOR GOING OFF on the Models page: nothing of it runs
    ev.clear(); reads = 0; MotorEnabled = false; LedWasRed = false; CurrentView = MODELSVIEW; PreviousModelNumber = 3; ModelNumber = 7; MotorEnabledHasChanged(); CHECK(reads == 0 && ModelNumber == 7 && at("GotoFrontView") < 0);
    printf("test_modelsarmed (motor switch on the Models page, run): %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
"""
d2 = tempfile.mkdtemp()
open(os.path.join(d2, 'm.cpp'), 'w').write(PROG2)
r2 = subprocess.run(['c++', '-std=c++17', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-but-set-variable', '-fsanitize=address,undefined',
                     '-o', os.path.join(d2, 'm'), os.path.join(d2, 'm.cpp')], capture_output=True, text=True)
if r2.returncode:
    print(r2.stderr[:3000]); print('FAIL: MotorEnabledHasChanged lifted does not compile'); m_checks, m_fails = 0, 1; bad = True
else:
    r2 = subprocess.run([os.path.join(d2, 'm')], capture_output=True, text=True)
    print(r2.stdout.strip())
    if r2.stderr.strip(): print(r2.stderr.strip()[:2000])
    bad = bad or r2.returncode != 0
    ml = [l for l in r2.stdout.splitlines() if l.startswith('test_modelsarmed (motor switch')]
    m_checks = int(re.search(r'(\d+) checks', ml[0]).group(1)) if ml else 0
    m_fails = int(re.search(r'(\d+) failures', ml[0]).group(1)) if ml else 1
run_checks += m_checks; run_fails += m_fails

# ---------------------------------------------------------------- THE SOURCES
checks = fails = 0
def check(c, what):
    global checks, fails
    checks += 1
    if not c: fails += 1; print('FAIL (source):', what)
def blank(s):
    """comments and strings blanked (lengths kept), so that braces and words in them do not count"""
    out = list(s); i = 0; n = len(s)
    while i < n:
        if s.startswith('//', i):
            j = s.find('\n', i); j = n if j < 0 else j
            for k in range(i, j): out[k] = ' '
            i = j
        elif s.startswith('/*', i):
            j = s.find('*/', i + 2); j = n if j < 0 else j + 2
            for k in range(i, j):
                if out[k] != '\n': out[k] = ' '
            i = j
        elif s[i] == '"' or (s[i] == "'" and i + 2 < n):
            q = s[i]; j = i + 1
            while j < n and s[j] != q:
                j += 2 if s[j] == '\\' else 1
            for k in range(i + 1, min(j, n)): out[k] = ' '
            i = j + 1
        else: i += 1
    return ''.join(out)
HEAD = re.compile(r'(?:^|\n)[ \t]*(?:static\s+|FLASHMEM\s+|FASTRUN\s+|inline\s+)*[A-Za-z_][\w:<>\*\s]*?\b(\w+)\s*\([^;{}()]*(?:\([^()]*\)[^;{}()]*)*\)\s*(?:const\s*)?\{')
def functions(text):
    """(name, start, end) of every top-level function in a blanked text"""
    res = []; depth = 0; i = 0; n = len(text)
    while i < n:
        c = text[i]
        if c == '{':
            if depth == 0:
                k = text.rfind('\n', 0, max(0, text.rfind(')', 0, i)))
                hdr = text[max(0, k - 300):i + 1]
                ms = list(HEAD.finditer(hdr))
                name = ms[-1].group(1) if ms and ms[-1].end() == len(hdr) else None
                start = i
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0 and name: res.append((name, start, i)); name = None
        i += 1
    return res
def where(text, funcs, pos):
    for nme, a, b in funcs:
        if a <= pos <= b: return nme
    return '(file level)'
FILES = []
for sub in ('include', 'src'):
    for f in sorted(os.listdir(os.path.join(TC, sub))):
        if f.endswith(('.h', '.cpp')) and f != 'secrets.h':
            FILES.append(sub + '/' + f)
TEXT = {f: src(f) for f in FILES}
BLANK = {f: blank(t) for f, t in TEXT.items()}
FUNCS = {f: functions(b) for f, b in BLANK.items()}
def places(rx, raw=False):
    out = []
    for f in FILES:
        hay = TEXT[f] if raw else BLANK[f]
        for m in re.finditer(rx, hay):
            out.append((f, where(BLANK[f], FUNCS[f], m.start()), TEXT[f].count('\n', 0, m.start()) + 1))
    return out

# a) entry 4 of NumberedFunctions is GotoModelsViewAsked; no entry of either list is GotoModelsView
main = BLANK['src/main.cpp']
m = re.search(r'void\s*\(\s*\*\s*NumberedFunctions\s*\[\s*LASTFUNCTION\s*\]\s*\)\s*\(\s*\)\s*\{(.*?)\};', main, re.S)
check(m is not None, 'NumberedFunctions found')
entries = [e.strip() for e in m.group(1).split(',')] if m else []
check(len(entries) > 4 and entries[4] == 'GotoModelsViewAsked', 'entry 4 of NumberedFunctions is GotoModelsViewAsked (it is %r)' % (entries[4] if len(entries) > 4 else None))
check(entries.count('GotoModelsViewAsked') == 1, 'GotoModelsViewAsked is in the list once only')
check('GotoModelsView' not in entries, 'no entry of NumberedFunctions is GotoModelsView itself')
as_pointer = [(f, fn, ln) for f, fn, ln in places(r'\bGotoModelsView\b(?!\s*\()')]
check(not as_pointer, 'GotoModelsView is never taken as a function pointer (a list, a table): %s' % as_pointer)
# b) EVERY CALL OF GotoModelsView(): the button's own (behind the refusal), and the page's own returns to itself
calls = places(r'(?<!void )\bGotoModelsView\s*\(\s*\)\s*;')   # (calls, not the declaration)
callers = sorted(set(fn for f, fn, ln in calls))
for f, fn, ln in calls: print('  GotoModelsView() called in %s:%d  %s' % (f, ln, fn))
OWN = {'GotoModelsViewAsked': 'the button, behind the refusal',
       'EndRenameModel': 'function 59: OK on the Rename page - reached only from the Models page (its Rename button, function 58)',
       'ReceiveAbandoned': "Receive a model: the page's own button (function 65); refused while a model is connected (LedWasGreen)",
       'ReceiveModelFile': "Receive a model: the page's own button (function 65); refused while a model is connected (LedWasGreen)"}
for c in callers: check(c in OWN, 'GotoModelsView() is called only by the button or by the page\'s own work - NOT by %s' % c)
check('GotoModelsViewAsked' in callers, 'the button calls GotoModelsView')
ask = lift('include/MenuOptions.h', r'\n(?:FLASHMEM\s+)?void GotoModelsViewAsked\(\)\s*\{')
check(ask.index('ModelsPageRefused()') < ask.index('GotoModelsView();'), 'GotoModelsViewAsked asks the refusal BEFORE it opens the page')
ref = blank(lift('include/MenuOptions.h', r'\n(?:FLASHMEM\s+)?bool ModelsPageRefused\(\)\s*\{'))
check(re.search(r'\bMsgBox\b|\bGetConfirmation\b|\bGetYesOrNo\b|\bGetBackupFilename\b|DelayWithDog', ref) is None, 'the refusal asks no box and does not wait')
# c) EVERY "CurrentView = MODELSVIEW" and every "page ModelsView" sent - directly, or as the page a box goes back to
own_pages = {'GotoModelsView_real', 'GotoModelsView', 'SendModelFile', 'ReceiveModelFile', 'ReceiveAbandoned', 'EndRenameModel',
             'ModelViewEnd', 'ShowBackupFileDate', 'DeleteModel', 'RenameFile', 'DeleteMODfile',
             'ShowRemoteID'}   # (ShowRemoteID: called from nowhere today - a box back to the Models page if it ever is)
check(not places(r'(?<!void )\bShowRemoteID\s*\('), 'ShowRemoteID (a box whose way back is the Models page) is called from nowhere')
setv = places(r'\bCurrentView\s*=\s*MODELSVIEW\b')
for f, fn, ln in setv: print('  CurrentView = MODELSVIEW in %s:%d  %s' % (f, ln, fn))
for f, fn, ln in setv: check(fn in ('GotoModelsView', 'SendModelFile'), 'CurrentView = MODELSVIEW set only by GotoModelsView and by a model\'s sending (its own button) - NOT %s (%s:%d)' % (fn, f, ln))
# the page named by its text: pModelsView / "page ModelsView"
named = []
for f in FILES:
    for m2 in re.finditer(r'"page ModelsView"', TEXT[f]):
        if BLANK[f][m2.start()] == '"':   # (in code, not in a comment)
            named.append((f, where(BLANK[f], FUNCS[f], m2.start()), TEXT[f].count('\n', 0, m2.start()) + 1))
for f, fn, ln in named: print('  "page ModelsView" written in %s:%d  %s' % (f, ln, fn))
for f, fn, ln in named: check((f, fn) in {('include/1Definitions.h', '(file level)')}
                              or fn in own_pages, '"page ModelsView" named only for pModelsView and by the model exchange - NOT %s (%s:%d)' % (fn, f, ln))
uses = places(r'\bpModelsView\b')
for f, fn, ln in uses: print('  pModelsView used in %s:%d  %s' % (f, ln, fn))
TEXTCMD = 'the screen\'s text words "Export", "Import", "SendModel", "DelFile" (sent only by the Models page\'s buttons)'
for f, fn, ln in uses:
    ok = fn in own_pages or (f, fn) == ('include/1Definitions.h', '(file level)') or (f == 'src/main.cpp' and fn == 'ButtonWasPressed')   # (its text words: TEXTCMD)
    check(ok, 'pModelsView (a box\'s way back, or the page sent) used only by the Models page\'s own work - NOT %s (%s:%d)' % (fn, f, ln))
# d) the internal returns are deliberately not refused - and their roads start on the Models page
rn = lift('src/main.cpp', r'\nvoid EndRenameModel\(\)\s*\{')
check('GotoModelsView();' in rn, 'EndRenameModel ends on the Models page (not refused, by design)')
check(re.search(r'\bif \(LedWasGreen\)', lift('include/ModelExchange.h', r'\nFLASHMEM void ReceiveModelFile\(\)\s*\{')) is not None, 'Receive a model is refused with a model connected')

# ---------------------------------------------------------------- THE SCREEN'S PAGES (if found): who sends function 4, who puts the page up itself
cand = [sys.argv[2] if len(sys.argv) > 2 else '', os.path.join(os.path.dirname(ROOT), 'TXV2-Screen', 'hmi', 'pages.json'),
        os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/TXV2-Screen/hmi/pages.json')]
pj = next((p for p in cand if p and os.path.isfile(p)), None)
if not pj:
    print('SKIP (screen): the screen\'s hmi/pages.json not found - the screen side not looked at')
else:
    pages = json.load(open(pj, encoding='utf-8'))['pages']
    senders4, selfopen, helpret = [], [], []
    for pg in pages:
        objs = [(pg.get('name'), pg.get('events', {}))] + [(c.get('name'), c.get('events', {})) for c in pg.get('components', []) or []]
        for nm, ev in objs:
            for k, v in (ev or {}).items():
                code = '\n'.join(l.split('//')[0] for l in (v or '').split('\n'))
                if re.search(r'va0\.val\s*=\s*(128\s*\+\s*4|132)\b', code): senders4.append((pg['name'], nm))
                if re.search(r'\bpage\s+(ModelsView|15)\b', code): selfopen.append((pg['name'], nm))
                if re.search(r'return\.txt\s*=\s*"ModelsView"', code): helpret.append((pg['name'], nm))
    print('  screen (%s): function 4 sent by %s; "page ModelsView" put up by the screen itself: %s; help returning to it: %s' % (pj, senders4, selfopen, helpret))
    check(senders4 == [('RXSetupView', 'b12')], 'the screen: ONE button sends function 4 - the main menu\'s Models button')
    check(not selfopen, 'the screen: no page puts the Models page up by itself')
    check(all(p == 'ModelsView' for p, n in helpret), 'the screen: only the Models page\'s own Help returns to it')
print('test_modelsarmed (sources): %d checks, %d failures' % (checks, fails))
total, tf = run_checks + checks, run_fails + fails
print('test_modelsarmed: %d checks, %d failures' % (total, tf))
sys.exit(1 if (bad or fails) else 0)
