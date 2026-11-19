#!/usr/bin/env python3
"""Review 17, reviewer B. "THE SET CAME WHOLE" ON THE ADVANCED RATES PAGE - reached the only way there is: through the Rates page.
The Rates page's read stays open for its whole window (MSP_WAIT_TIME, 2.5 s: Reading_RATES_Now); its 'Advanced' button is shown again as soon as
the set has come (HideRATESMsg). Tapped inside that window, the Advanced page begins ITS read (Reading_RATES_Advanced_Now) with the Rates page's
still open - and transceiver.h BlockItemSeen, whose two sets want the same four items (0x0F), gives the whole set to the FIRST of the two in its
chain: RATES_Loaded. RATES_ADV_Loaded stays false, BlockShown stands, and nothing sets it later.
The REAL routines: transceiver.h BlockMaskTick / BlockItemSeen / BlockSilence / Hide_msg_if_needed, Parameters.h AddParameterstoQueue,
RF_Rates.h (the page's read, its messages, its edit), RF_Rates_Advanced.h (the page's start, read, messages, edit), RF_PIDs.h RfBlockNotLoaded.
The items are fed as ParseTelemetryItem feeds them (BlockMaskTick, the bytes stored by whichever read is open, BlockItemSeen), the screen telling
the block again every 600 ms while the read is open (its bleTellItems, 1.11.179).
   python3 exp_adv_rates_flag.py [tree]"""
import os, re, subprocess, sys, tempfile, shutil, atexit
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (taken into the suite: this file's own tree)
INC = os.path.join(ROOT, 'TransmitterCode', 'include')
def src(n): return open(os.path.join(INC, n), encoding='utf-8').read()
def lift(text, head):
    i = text.index(head); j = text.index('{', i); d = 0
    for k in range(j, len(text)):
        if text[k] == '{': d += 1
        elif text[k] == '}':
            d -= 1
            if d == 0: return text[i:k + 1] + '\n'
    raise SystemExit('no end: ' + head)
D1 = src('1Definitions.h'); TR = src('transceiver.h'); PM = src('Parameters.h'); RT = src('RF_Rates.h'); RA = src('RF_Rates_Advanced.h'); PD = src('RF_PIDs.h')
def define(n): return re.search(r'^#define %s[ \t]+(\S+)' % n, D1, re.M).group(0)
HAS_FLAGS = 'RATES_ADV_Loaded' in RA          # (the tree as the sixteenth review saw it has none: the same run shows what HEAD does)
mb = re.search(r'static bool BlockWasReading = false;.*?\nstatic void BlockItemSeen\(uint8_t item\)\n\{.*?\n\}\n', TR, re.S).group(0)
prog = r'''
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
#include <map>
#define FLASHMEM
#define FASTRUN
#define Gray 1
#define Black 0
#define WHAHWHAHMSG 1
#define BEEPMIDDLE 2
#define BEEPCOMPLETE 3
#define RFGOVERNORVIEW_PROFILE 54
''' + '\n'.join(define(n) for n in ('MSP_WAIT_TIME', 'SEND_PID_VALUES', 'SEND_RATES_VALUES', 'SEND_RATES_ADVANCED_VALUES', 'SEND_PID_ADVANCED_VALUES', 'SEND_GOV_VALUES', 'SEND_GOV_CONFIG_VALUES',
                                         'RATESVIEW_RF', 'RATESADVANCEDVIEW', 'PIDVIEW', 'PIDADVANCEDVIEW', 'RFGOVERNORVIEW_GLOBAL', 'ROTORFLIGHTVIEW', 'MAX_RATES_BYTES', 'MAX_RATES_ADVANCED_BYTES',
                                         'PARAMETER_SEND_REPEATS', 'PARAMETER_QUEUE_MAXIMUM')) + '\n' \
  + re.search(r'enum \{ VK_NONE = 0[^\n]*', D1).group(0) + r'''
static int CurrentView = 0; static uint8_t Bank = 1, DualRateInUse = 1, PreviousBank = 1;
static bool live = true; static bool RfLive() { return live; }
static bool BlockBankChanges = false, Rates_Advanced_Were_Edited = false, Rates_Were_Edited = false;
static bool RATES_Loaded = false, RATES_ADV_Loaded = false, PIDS_ADV_Loaded = false, PIDS_Loaded = false, GOV_Loaded = false;
static bool Reading_PIDS_Now = false, Reading_RATES_Now = false, Reading_RATES_Advanced_Now = false, Reading_PIDS_Advanced_Now = false, Reading_GOV_Now = false, Reading_GOV_Config_Now = false;
''' + re.search(r'^inline void RfOtherReadsOver\(\)[^\n]*', open(os.path.join(ROOT, 'TransmitterCode', 'include', '1Definitions.h'), encoding='utf-8').read(), re.M).group(0) + r'''   // (the nineteenth review: the REAL rule, lifted - a page's read is over when another page's begins)
static uint32_t RATES_Send_Duration = 0, RATES_Start_Time = 0, Rates_Advanced_Send_Duration = 0, RATES_Advanced_Start_Time = 0;
static uint32_t PID_Send_Duration = 0, PID_Start_Time = 0, PID_Advanced_Send_Duration = 0, PID_Advanced_Start_Time = 0, GOV_Send_Duration = 0, GOV_Start_Time = 0, GOV_Config_Send_Duration = 0, GOV_Global_Start_Time = 0;
static uint16_t BlockSeen = 0; static bool BlockShown = false;
static uint32_t FcBankAskAt = 0, FcBankAskAt2 = 0;
static bool ModelMatched = true, BoundFlag = true, PipeReadRefused = false; static int PipeState = 2; static bool BakOffline() { return false; }
static const uint8_t PIPE_STACK_MAX = 8; static uint8_t PipeStack[PIPE_STACK_MAX]; static uint8_t PipeStackN = 0;
static int ParametersToBeSentPointer = 0; static uint8_t ParametersToBeSent[PARAMETER_QUEUE_MAXIMUM + 2];
static uint32_t now_ = 1000; static uint32_t millis() { return now_; }
static std::vector<std::string> cmds; static std::map<std::string, std::string> fields;
static void SendCommand(char *c) { cmds.push_back(c); if (!strncmp(c, "vis ", 4)) { std::string s(c + 4); const size_t k = s.find(','); fields["vis:" + s.substr(0, k)] = s.substr(k + 1); } }
static void SendText(char *n, char *t) { fields[n] = t; } static void SendValue(char *n, int v) { fields[n] = std::to_string(v); }
static void SendForegroundColour(char *, uint16_t) {}
static int boxes = 0, sounds = 0; static std::string lastBox, lastBoxPage; static void MsgBox(char *p, char *m) { ++boxes; lastBox = m; lastBoxPage = p; }
static void PlaySound(int) { ++sounds; }
static char *Str(char *s, int n, int) { sprintf(s, "%d", n); return s; }
static char ModelName[20] = "Havoc";
static uint8_t Rate_Values[MAX_RATES_BYTES], Rate_Advanced_Values[MAX_RATES_ADVANCED_BYTES];
static char RatesWindows[13][5] = {"t0","n1","n2","n3","n4","n5","n6","n7","n8","n9","n10","n11","n12"};
static char RatesAWindows[15][4] = {"n0", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9", "n10", "n11", "n12", "n13", "t14"};
static void ShowRatesLocalBank() {} static void ShowLocalRatesAdvancedBank() {} static void ForegroundColourRATESLabels(uint16_t) {} static void ForegroundColourAdvancedRates(uint16_t) {}
static void Modify_Labels_For_RATES_View() {}
static bool ModelSeemsArmed(char *, size_t) { return false; } static bool RfPipeBlocked(char *, size_t) { return false; }
static bool GetConfirmation(char *, char *) { return true; }
static void HidePIDMsg() {} static void HidePID_Advanced_Msg() {} static void HideGOVMsg() {} static void HideGOVConfigMsg() {}
static bool AllGlobalConfigBytesReceived() { return false; }   // (e99: the Governor global window's end asks it; that page is not opened here - its own count stays empty, as before)
static bool RfVerifyPending() { return false; } static int RfVerifySet() { return 0; } static bool RfVerifyEnd(uint8_t) { return false; } static void RfVerifyTick() {}
void HideRATESMsg(); void Hide_Advanced_Rates_Msg(); static void BlockMaskTick();
''' + lift(PD, 'FLASHMEM bool RfBlockNotLoaded(bool loaded, const char *page, const char *what)') \
    + lift(PM, 'bool RfParamOverPipe(uint8_t id)') + lift(PM, 'void AddParameterstoQueue(uint8_t ID)') \
    + lift(RT, 'FLASHMEM void RatesMsg(const char *msg, uint16_t Colour)') + lift(RT, 'FLASHMEM void HideRATESMsg()') + lift(RT, 'FLASHMEM static void RatesAskValues()') \
    + lift(RT, 'FLASHMEM void ShowRatesBank()') + lift(RT, 'FLASHMEM void StartRFRatesView()') + lift(RT, 'FLASHMEM void RatesWereEdited()') \
    + lift(RA, 'FLASHMEM void Hide_Advanced_Rates_Msg()') + lift(RA, 'FLASHMEM void RatesAdvancedWereEdited()') + lift(RA, 'FLASHMEM void RatesAdvancedMsg(const char *msg, uint16_t Colour)') \
    + lift(RA, 'FLASHMEM static void RatesAdvAskValues()') + lift(RA, 'FLASHMEM void ShowRatesAdvancedBank()') + lift(RA, 'FLASHMEM void StartRatesAdvancedView()') \
    + 'static uint32_t SilenceMsgUntil = 0;\nstatic int SilenceMsgView = -1;\n' + lift(TR, 'static void BlockSilence(const char *what)') + lift(TR, 'void Hide_msg_if_needed()') + mb + r'''
// the screen's side: the block the receiver holds for the request LAST sent, told when it has come and again every 600 ms while that read is open
static int fcKind = 0;                 // 0 nothing asked, 1 the rates block, 2 the advanced rates block
static uint32_t fcReadyAt = 0, fcUntil = 0, fcToldAt = 0; static int tellings = 0;
static void pipeFlush() { while (PipeStackN) { const uint8_t id = PipeStack[--PipeStackN]; if (id == SEND_RATES_VALUES || id == SEND_RATES_ADVANCED_VALUES) { fcKind = id == SEND_RATES_VALUES ? 1 : 2; fcReadyAt = now_ + LATENCY; fcUntil = now_ + MSP_WAIT_TIME; fcToldAt = 0; } } }
// transceiver.h ParseTelemetryItem for items 25 to 28, as it is written: the mask tick, the bytes into the array of EVERY read that is open, then the count
static void item(uint8_t it, uint8_t fill) {
    BlockMaskTick();
    if (Reading_RATES_Now) for (int i = (it - 25) * 3 + 1; i < (it - 25) * 3 + 4 && i < MAX_RATES_BYTES; ++i) Rate_Values[i] = fill;
    if (Reading_RATES_Advanced_Now) for (int i = (it - 25) * 4; i < (it - 25) * 4 + 4 && i < MAX_RATES_ADVANCED_BYTES; ++i) Rate_Advanced_Values[i] = fill;
    BlockItemSeen(it);
}
static void tick() {   // one 50 ms tick of the main loop on a Rotorflight page: the queue to the pipe, what the screen tells, the windows' ends
    pipeFlush();
    if (fcKind && (int32_t)(now_ - fcReadyAt) >= 0 && (int32_t)(now_ - fcUntil) < 0 && (!fcToldAt || now_ - fcToldAt >= 600)) { fcToldAt = now_; ++tellings; for (uint8_t it = 25; it <= 28; ++it) item(it, fcKind == 1 ? 11 : 22); }
    if (CurrentView >= PIDVIEW && CurrentView <= RFGOVERNORVIEW_GLOBAL) Hide_msg_if_needed();
    now_ += 50;
}
static void run(uint32_t ms) { for (uint32_t t = 0; t < ms; t += 50) tick(); }
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
// The pilot opens Rates, waits until 'Advanced' shows (the set has come), and taps it 'afterMs' after the page opened. Then he types a number.
static bool trial(uint32_t afterMs, bool show) {
    live = true; CurrentView = ROTORFLIGHTVIEW; RATES_Loaded = RATES_ADV_Loaded = false; Reading_RATES_Now = Reading_RATES_Advanced_Now = false; BlockWasReading = false; BlockSeen = 0; BlockShown = false;
    Rates_Were_Edited = Rates_Advanced_Were_Edited = false; fields.clear(); cmds.clear(); boxes = 0; fcKind = 0; PipeStackN = 0; tellings = 0; now_ += 20000;
    const uint32_t t0 = now_;
    StartRFRatesView();
    while (fields["vis:b2"] != "1" && now_ - t0 < 5000) tick();                 // 'Advanced' is shown again: the rates have come
    const uint32_t shownAt = now_ - t0;
    while (now_ - t0 < afterMs) tick();
    const bool ratesWindowOpen = Reading_RATES_Now;
    StartRatesAdvancedView();                                                    // the button 'Advanced' (function 28)
    run(6000);                                                                   // both windows end; the screen has told the block four times
    const bool numbersShown = fields["vis:busy"] == "0" && Rate_Advanced_Values[0] == 22;
    boxes = 0; RatesAdvancedWereEdited();                                        // he types a number into a box of the page
    const bool refused = boxes == 1;
    if (show) printf("  'Advanced' shown %4u ms after Rates opened, tapped at %4u ms (the Rates read %s): the page shows its numbers %d, the set was told %d times, in hand whole %s -> an edit %s\n",
                     (unsigned) shownAt, (unsigned) afterMs, ratesWindowOpen ? "STILL OPEN" : "over", (int) numbersShown, tellings, HAS_FLAG ? (RATES_ADV_Loaded ? "yes" : "NO") : "(no such rule)",
                     refused ? ("REFUSED: \"" + lastBox.substr(0, lastBox.find('\r')) + " ...\"").c_str() : "taken, Save shown");
    if (refused) {   // ... and is it for good? A minute on, the same; the box's own advice - leave and return - as quickly as before, the same again
        run(60000); boxes = 0; RatesAdvancedWereEdited(); if (boxes != 1) printf("     (a minute on: taken)\n");
    }
    return !refused;
}
int main() {
    printf("%s\n", HAS_FLAG ? "THE TREE UNDER REVIEW (RATES_ADV_Loaded):" : "THE TREE AS THE SIXTEENTH REVIEW SAW IT (no such rule):");
    int taken = 0, n = 0;
    for (uint32_t after = 600; after <= 3200; after += 200) { const bool ok = trial(after, true); taken += ok; ++n; }
    printf("  an edit on the Advanced rates page was taken in %d of %d trials\n", taken, n);
    CHECK(taken == n);
    printf("exp_adv_rates_flag: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
prog = prog.replace('HAS_FLAG', '1' if HAS_FLAGS else '0').replace('LATENCY', '400')
if not HAS_FLAGS: prog = prog.replace('static bool RfVerifyPending()', 'static bool RfBlockNotLoadedUnused = false;\nstatic bool RfVerifyPending()')
d = tempfile.mkdtemp(); atexit.register(shutil.rmtree, d, True)
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-fsanitize=address,undefined', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit('exp_adv_rates_flag: DID NOT COMPILE')
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
