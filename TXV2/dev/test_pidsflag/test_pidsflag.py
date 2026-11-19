#!/usr/bin/env python3
"""Review 17, reviewer B. "THE SET CAME WHOLE" ON THE ADVANCED PIDS PAGE ("PID + ...") - reached through the PIDs page, whose read is still open.
(The Rates / Dynamics pair is exp_adv_rates_flag.py, which this file was made from; the words below are that file's, the pages these two.)
Here the two sets want DIFFERENT items (the PIDs 0x3BF, the advanced PIDs 0xBF): while the PIDs page's read is open the advanced set is never "whole";
when that window ends the next telling of the block completes it - if the screen tells it again in time.
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
D1 = src('1Definitions.h'); TR = src('transceiver.h'); PM = src('Parameters.h'); RT = src('RF_PIDs.h'); RA = src('RF_PID_Advanced.h'); PD = src('RF_PIDs.h')
def define(n): return re.search(r'^#define %s[ \t]+(\S+)' % n, D1, re.M).group(0)
HAS_FLAGS = 'PIDS_ADV_Loaded' in RA          # (the tree as the sixteenth review saw it has none: the same run shows what HEAD does)
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
                                         'RATESVIEW_RF', 'RATESADVANCEDVIEW', 'PIDVIEW', 'PIDADVANCEDVIEW', 'RFGOVERNORVIEW_GLOBAL', 'ROTORFLIGHTVIEW', 'MAX_RATES_BYTES', 'MAX_RATES_ADVANCED_BYTES', 'MAX_PIDS_ADVANCED_BYTES', 'MAX_PID_WORDS',
                                         'PARAMETER_SEND_REPEATS', 'PARAMETER_QUEUE_MAXIMUM')) + '\n' \
  + re.search(r'enum \{ VK_NONE = 0[^\n]*', D1).group(0) + r'''
static int CurrentView = 0; static uint8_t Bank = 1, DualRateInUse = 1, PreviousBank = 1;
static bool live = true; static bool RfLive() { return live; }
static bool BlockBankChanges = false, Rates_Advanced_Were_Edited = false, Rates_Were_Edited = false, PIDS_Were_Edited = false, PIDS_Advanced_Were_Edited = false;
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
static void ShowLocalBank() {} static void ShowLocalPIDsAdvancedBank() {} static void ForegroundColourPIDLabels(uint16_t) {} static void ForegroundColourPIDAdvancedLabels(uint16_t) {}
static char BankNames[8][16] = {"-", "Bank 1", "Bank 2", "Bank 3", "Bank 4", "Bank 5", "Bank 6", ""}; static uint8_t BanksInUse[6] = {1, 2, 3, 4, 5, 6}; static uint16_t PID_Values[20]; static uint8_t PID_Advanced_Values[MAX_PIDS_ADVANCED_BYTES];
static void Modify_Labels_For_RATES_View() {}
static bool ModelSeemsArmed(char *, size_t) { return false; } static bool RfPipeBlocked(char *, size_t) { return false; }
static bool GetConfirmation(char *, char *) { return true; }
static void HideRATESMsgStub() {} static void HideGOVMsg() {} static void HideGOVConfigMsg() {}
static bool AllGlobalConfigBytesReceived() { return false; }   // (e99: the Governor global window's end asks it; that page is not opened here - its own count stays empty, as before)
static bool RfVerifyPending() { return false; } static int RfVerifySet() { return 0; } static bool RfVerifyEnd(uint8_t) { return false; } static void RfVerifyTick() {}
void HidePIDMsg(); void HidePID_Advanced_Msg(); static void HideRATESMsg() {} static void Hide_Advanced_Rates_Msg() {} static void BlockMaskTick();
''' + lift(PD, 'FLASHMEM bool RfBlockNotLoaded(bool loaded, const char *page, const char *what)') \
    + lift(PM, 'bool RfParamOverPipe(uint8_t id)') + lift(PM, 'void AddParameterstoQueue(uint8_t ID)') \
    + lift(RT, 'FLASHMEM void PIDMsg(const char *msg, uint16_t Colour)') + lift(RT, 'FLASHMEM void HidePIDMsg()') + lift(RT, 'FLASHMEM static void PidAskValues()') \
    + lift(RT, 'FLASHMEM void ShowPIDBank()') + lift(RT, 'FLASHMEM void StartPIDView()') \
    + lift(RA, 'FLASHMEM void HidePID_Advanced_Msg()') + lift(RA, 'FLASHMEM void PIDAdvancedMsg(const char *msg, uint16_t Colour)') + lift(RA, 'FLASHMEM void PIDsAdvancedWereEdited()') \
    + lift(RA, 'FLASHMEM static void PidAdvAskValues()') + lift(RA, 'FLASHMEM void ShowPIDAdvancedBank()') + lift(RA, 'FLASHMEM void StartPIDAdvancedView()') \
    + 'static uint32_t SilenceMsgUntil = 0;\nstatic int SilenceMsgView = -1;\n' + lift(TR, 'static void BlockSilence(const char *what)') + lift(TR, 'void Hide_msg_if_needed()') + mb + r'''
// the screen's side: the block the receiver holds for the request LAST sent, told when it has come and again every 600 ms while that read is open
static int fcKind = 0;                 // 0 nothing asked, 1 the rates block, 2 the advanced rates block
static uint32_t fcReadyAt = 0, fcUntil = 0, fcToldAt = 0; static int tellings = 0;
static void pipeFlush() { while (PipeStackN) { const uint8_t id = PipeStack[--PipeStackN]; if (id == SEND_PID_VALUES || id == SEND_PID_ADVANCED_VALUES) { fcKind = id == SEND_PID_VALUES ? 1 : 2; fcReadyAt = now_ + LATENCY; fcUntil = now_ + MSP_WAIT_TIME; fcToldAt = 0; } } }
// transceiver.h ParseTelemetryItem for items 25 to 28, as it is written: the mask tick, the bytes into the array of EVERY read that is open, then the count
static void item(uint8_t it, uint8_t fill) {
    BlockMaskTick();
    if (Reading_PIDS_Now) PID_Values[(it - 25) % 9] = fill;
    if (Reading_PIDS_Advanced_Now) PID_Advanced_Values[(it - 25) % 8] = fill;
    BlockItemSeen(it);
}
static void tick() {   // one 50 ms tick of the main loop on a Rotorflight page: the queue to the pipe, what the screen tells, the windows' ends
    pipeFlush();
    if (fcKind && (int32_t)(now_ - fcReadyAt) >= 0 && (int32_t)(now_ - fcUntil) < 0 && (!fcToldAt || now_ - fcToldAt >= 600)) { fcToldAt = now_; ++tellings; for (uint8_t it = 25; it <= 34; ++it) if (it != 31 && (fcKind == 1 || it <= 32)) item(it, fcKind == 1 ? 11 : 22); }
    if (CurrentView >= PIDVIEW && CurrentView <= RFGOVERNORVIEW_GLOBAL) Hide_msg_if_needed();
    now_ += 50;
}
static void run(uint32_t ms) { for (uint32_t t = 0; t < ms; t += 50) tick(); }
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
// The pilot opens Rates, waits until 'Advanced' shows (the set has come), and taps it 'afterMs' after the page opened. Then he types a number.
static bool trial(uint32_t afterMs, bool show) {
    live = true; CurrentView = ROTORFLIGHTVIEW; PIDS_Loaded = PIDS_ADV_Loaded = false; Reading_PIDS_Now = Reading_PIDS_Advanced_Now = false; SilenceMsgUntil = 0; BlockWasReading = false; BlockSeen = 0; BlockShown = false;
    Rates_Were_Edited = Rates_Advanced_Were_Edited = false; fields.clear(); cmds.clear(); boxes = 0; fcKind = 0; PipeStackN = 0; tellings = 0; now_ += 20000;
    const uint32_t t0 = now_;
    StartPIDView();
    while (fields["vis:b2"] != "1" && now_ - t0 < 5000) tick();                 // 'PID +' is shown again: the PIDs have come
    const uint32_t shownAt = now_ - t0;
    while (now_ - t0 < afterMs) tick();
    const bool ratesWindowOpen = Reading_PIDS_Now;
    StartPIDAdvancedView();                                                    // the button 'Advanced' (function 28)
    uint32_t refusedFor = 0; bool falseLine = false;                             // how long an edit is refused from the tap on; the line "PIDs: only PART came back" on this page
    for (uint32_t t = 0; t < 6000; t += 50) { tick(); if (!PIDS_ADV_Loaded) refusedFor = t + 50; if (fields["busy"].find("only PART") != std::string::npos && fields["vis:busy"] == "1") falseLine = true; }
    const bool numbersShown = fields["vis:busy"] == "0" && PID_Advanced_Values[0] == 22;
    boxes = 0; PIDsAdvancedWereEdited();                                         // he types a number into a box of the page
    const bool refused = boxes == 1;
    if (show) printf("  'PID +' shown %4u ms after PIDs opened, tapped at %4u ms (the PIDs read %s): edits refused for %4u ms from the tap%s; the line 'PIDs: only PART came back' shown on this page %d; in the end whole %s -> an edit %s\n",
                     (unsigned) shownAt, (unsigned) afterMs, ratesWindowOpen ? "STILL OPEN" : "over", (unsigned) refusedFor, refusedFor >= 6000 ? " - FOR GOOD" : "", (int) falseLine, HAS_FLAG ? (PIDS_ADV_Loaded ? "yes" : "NO") : "(no such rule)",
                     refused ? ("REFUSED: \"" + lastBox.substr(0, lastBox.find('\r')) + " ...\"").c_str() : "taken, Save shown");
    if (refused) {   // ... and is it for good? A minute on, the same; the box's own advice - leave and return - as quickly as before, the same again
        run(60000); boxes = 0; PIDsAdvancedWereEdited(); if (boxes != 1) printf("     (a minute on: taken)\n");
    }
    return !refused;
}
// (The author's, behind the break-it round of 16 Nov 2026 - mut19 RG4: nothing noticed "Reading_PIDS_Advanced_Now = false" taken out of RF_PIDs.h.)
// THE OTHER WAY: the PID + page, its set come, left for the PIDs page INSIDE ITS OWN READ'S WINDOW. A page's read is over with its page: the PIDs
// page's block, which comes now, is stored into the array of EVERY read that is open (transceiver.h ParseTelemetryItem) - with the PID + page's
// flag still up it went into the PID + page's numbers too, and at its window's end its "only PART came back" was said on the PIDs page.
static bool trialBack(uint32_t afterMs) {
    live = true; CurrentView = ROTORFLIGHTVIEW; PIDS_Loaded = PIDS_ADV_Loaded = false; Reading_PIDS_Now = Reading_PIDS_Advanced_Now = false; SilenceMsgUntil = 0; BlockWasReading = false; BlockSeen = 0; BlockShown = false;
    fields.clear(); cmds.clear(); boxes = 0; fcKind = 0; PipeStackN = 0; tellings = 0; now_ += 20000; memset(PID_Advanced_Values, 0, sizeof PID_Advanced_Values); memset(PID_Values, 0, sizeof PID_Values);
    const uint32_t t0 = now_;
    StartPIDView();
    while (fields["vis:b2"] != "1" && now_ - t0 < 5000) tick();
    run(2600);                                                                   // the PIDs page's own window is over
    StartPIDAdvancedView();
    const uint32_t t1 = now_;
    while (now_ - t1 < afterMs) tick();
    const bool advWhole = PIDS_ADV_Loaded && PID_Advanced_Values[0] == 22, advOpen = Reading_PIDS_Advanced_Now;
    StartPIDView();                                                              // the PID + page's way back to the PIDs page
    const bool downAtOnce = !Reading_PIDS_Advanced_Now;
    bool falseLine = false;
    for (uint32_t t = 0; t < 6000; t += 50) { tick(); if (fields["busy"].find("only PART") != std::string::npos && fields["vis:busy"] == "1") falseLine = true; }
    const bool ok = downAtOnce && !falseLine && PIDS_Loaded && PID_Values[0] == 11 && (!advWhole || PID_Advanced_Values[0] == 22);
    printf("  back to PIDs %4u ms after 'PID +' was tapped (its read %s, its set %s): the PID + read is over with its page %d; 'only PART came back' on the PIDs page %d; the PIDs whole %d; the PID + page's own numbers left alone %d\n",
           (unsigned) afterMs, advOpen ? "STILL OPEN" : "over", advWhole ? "come" : "not yet come", (int) downAtOnce, (int) falseLine, (int)(PIDS_Loaded && PID_Values[0] == 11), (int)(!advWhole || PID_Advanced_Values[0] == 22));
    return ok;
}
int main() {
    { int good = 0, m = 0; for (uint32_t after = 300; after <= 2700; after += 300) { good += trialBack(after); ++m; } CHECK(good == m); }
    printf("%s\n", HAS_FLAG ? "THE TREE UNDER REVIEW (PIDS_ADV_Loaded):" : "THE TREE AS THE SIXTEENTH REVIEW SAW IT (no such rule):");
    int taken = 0, n = 0;
    for (uint32_t after = 500; after <= 3200; after += 100) { const bool ok = trial(after, true); taken += ok; ++n; }
    printf("  an edit on the PID + page was taken in the end in %d of %d trials\n", taken, n);
    CHECK(taken == n);
    printf("exp_adv_pids_flag: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
prog = prog.replace('HAS_FLAG', '1' if HAS_FLAGS else '0').replace('LATENCY', '400')
if not HAS_FLAGS: prog = prog.replace('static bool RfVerifyPending()', 'static bool RfBlockNotLoadedUnused = false;\nstatic bool RfVerifyPending()')
d = tempfile.mkdtemp(); atexit.register(shutil.rmtree, d, True)
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-fsanitize=address,undefined', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit('exp_adv_pids_flag: DID NOT COMPILE')
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
