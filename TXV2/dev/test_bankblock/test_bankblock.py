#!/usr/bin/env python3
"""B211, TAKEN INTO THE SUITE from the nineteenth review (reviewer B's exp_bankblock.py, his text below; what was added to it is marked "(suite)"):
  - the tree is THIS one (or a TransmitterCode folder given as the first word; "r18" and "head" are his two older trees, for comparison:
    with them, or with --report, nothing is asserted);
  - (suite) THE RADIO'S OWN TELLING, which his model had not got: the receiver puts the block's items into its acknowledgements too, one item a
    packet in rotation (RXV2 Radio.h; a packet every PACEMAKER ms), while the block's read window is open - so the block of the page BEFORE
    goes on arriving item by item until the new page's request has reached the receiver. --noradio / --nopipe take one carrier away;
  - (suite) what each part must show is ASSERTED (the rows marked KNOWN are faults of the released firmware, in B212's queue: printed only);
  - (suite) never two reading flags up at once, looked at on every pass of the loop.
  - (suite) e99c work (17 Nov 2026): Motor_sign.h MotorEnabledHasChanged LIFTED (it was a hand copy of B16's lines); the screen's "ldrcpipe off"
    modelled (the words not yet sent dropped, the link let go); part n on all six pages, page and menu, with and without a safety switch, ASSERTED;
    part v: the motor switch behind a save (five roads, four write conditions, the safety switch or none) and behind a transfer - ASSERTED.
  - (suite) e99 (the twentieth review): part h is "what the block is for" ON EVERY PAGE THAT SAVES TO A BANK (PIDs, PID +, Governor, Dynamics;
    Rates KNOWN), by OK, by Help, by OK and the same page again, by OK and another page, by Help and back; the receiver's write landing at
    once / 30-120 / 80-250 ms after its trigger word (reviewer B's model); the switch moved 0.05-0.6 s on AND the moment it is free;
    asserted: never into the other bank, never free before the write has landed. Part w: HOW LONG the bank switch is held behind a save
    whose page was left (against the read-back's own window). Part l: the Governor global page's own LINE. Rows with no trial fail.
    --loss N (an acknowledgement lost in N of 100), --send31, --pace N (ms between packets), --seed N: reviewer A's switches; with --loss
    the "whose block" rows are KNOWN rows (printed, not asserted: the leak of "whole twice by radio" when the give-away item is lost, B212).
    The suite's run adds part h at the 2 ms and the 5 ms pace with three seeds, and parts h, w with 3 in 100 acknowledgements lost.
  - (suite) e99d test work (18 Nov 2026): e99c's "free at once" taken out - with no save on its way the motor road is the RELEASED firmware's
    (part n: the bank by the five-second net, asserted within 6.5 s; later than 0.2 s printed KNOWN, B212 B19-B5); a followed save: free by its
    window + 0.1 s (asserted). G5: no read-back pending more than 100 ms after its kind's flag went down, on every pass of every part
    (asserted). G1's class (the bank check out at OK, then the motor): no worse than without e99c, 5 % + 3 (asserted). G8 (B212 5a): part h's
    Dynamics "OK, the same page again" INTO THE OTHER BANK is a KNOWN row - printed with its count, NOT asserted (its "free before the write
    landed" stays asserted). Part x: a save whose write never lands, then its page asked afresh - WHOLE, edits taken, no false line (asserted),
    and how long until whole. Part y: the write landing LATE (0.5-2.5 s after the fresh ask). Part z: a followed save ended off its page (G6),
    Help and back at every delay, and the blank screen (G7). Part u: a save that stays on its page - its verdict as before e99d.
----------------------------------------------------------------------------------------------------------------------------------------------
Review 19, reviewer B.  THE BANK SWITCH'S BLOCK BEHIND A WORD PAGE THAT IS LEFT FOR THE MENU (e97: every read is over at the menu).
The REAL routines of a tree (now / r18 = as the eighteenth review saw it / head = git HEAD, B210), lifted by name:
  main.cpp        ManageTransmitter (WHOLE: its once-a-second round, its 50 ms round, its early ways out), GetBank, and SendData's own lines
                  for the parameter queue (transceiver.h)
  Switches.h      ReadBankSwitch (the self-heal), ReadAutoAndMotorSwitch, BanksCount, BankOf123, UpperBank, BankHasChanged
  Parameters.h    RfParamOverPipe, PipeOn, PipePageShowing, PipeTick, ShowPipeState, PipeOff, PipeFlush, RfLive, AddParameterstoQueue,
                  ActuallySendParameters
  transceiver.h   BlockMaskTick, BlockItemSeen, BlockSilence, Hide_msg_if_needed, TelemetryFromPipe, the Read...FromAckPayload routines,
                  ParseTelemetryItem's own cases 25-30, 32-34
  RF_Verify.h, RF_SaveNow.h, RF_PIDs.h, RF_PID_Advanced.h, RF_Rates_Advanced.h, RF_Governor_Profile.h, RF_Governor_Global.h   WHOLE
  RF_Rates.h      the page's message, hide, ask, write, show, start, end, edit and save routines
  RF_RotorFlight.h ShowRFRate, ShowRFBank, RfReadsOver (where the tree has it), RotorFlightStart, RotorFlightEnd
  PipeHttp.h      RfMayFly, RfWordPageSays, RfBoxOrQuiet, BankCheckRefuse, BankCheck, BankCheckTick, FcBankPage, FcBankShow, FcBankTick
over a clock in MICROSECONDS (millis() is its thousandth), a loop pass of some tens of microseconds, a packet every PACEMAKER ms that takes
half a millisecond, and my predecessor's model of the screen's Bluetooth task, the receiver and the flight controller (dev/test_flagsacross).
WHAT IS MINE AND NOT THE TREE'S: the times a pass, a packet and the once-a-second round take (--hk: the round's own time, in microseconds).
   python3 exp_bankblock.py now|r18|head [--hk 1500] [--n 40] [--seed 19] [--show] [--part a,b,c...]"""
import os, re, subprocess, sys, tempfile, shutil, atexit
sys.dont_write_bytecode = True
B = '/Volumes/2TB SSD/ClaudeScratch/review19/b'
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TREES = {'now': os.path.join(ROOT, 'TransmitterCode'),
         'r18': '/Volumes/2TB SSD/ClaudeScratch/review19/as_review18_saw_it',
         'head': os.path.join(B, 'head', 'TransmitterCode')}
tree = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else 'now'
ASSERT = tree not in ('r18', 'head') and '--report' not in sys.argv   # (suite)
TC = TREES.get(tree) or tree            # (or a path to a TransmitterCode folder: a mutant's)
def arg(name, dflt): return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else dflt
N = int(arg('--n', '60')); SEED = int(arg('--seed', '19')); HK = int(arg('--hk', '1500')); SHOW = '--show' in sys.argv; PART = arg('--part', 'all')
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8').read()
def strip(t): return t.replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '')
def lift(text, head, must=True):
    i = -1
    while True:   # (the routine itself, not a line that only names it ahead)
        i = text.find(head, i + 1)
        if i < 0: break
        j = text.find('{', i)
        if j >= 0 and ';' not in re.sub(r'//[^\n]*', '', text[i + len(head):j]) : break
    if i < 0:
        if must: raise SystemExit('cannot find: ' + head)
        return ''
    j = text.index('{', i); d = 0
    for k in range(j, len(text)):
        if text[k] == '{': d += 1
        elif text[k] == '}':
            d -= 1
            if d == 0: return text[i:k + 1] + '\n'
    raise SystemExit('no end: ' + head)
def one(text, head):
    i = text.index(head); return text[i:text.index('\n', i) + 1]
D1 = src('include/1Definitions.h'); TR = src('include/transceiver.h'); PM = src('include/Parameters.h'); SW = src('include/Switches.h'); MAIN = src('src/main.cpp')
RT = src('include/RF_Rates.h'); RF = src('include/RF_RotorFlight.h'); PH = src('include/PipeHttp.h')
MS = src('include/Motor_sign.h'); motor_part = lift(MS, 'void MotorEnabledHasChanged()')   # (suite, e99c work 17 Nov 2026) the routine itself, not a copy
WHOLE = [strip(src('include/' + f)) for f in ('RF_SaveNow.h', 'RF_PIDs.h', 'RF_PID_Advanced.h', 'RF_Rates_Advanced.h', 'RF_Governor_Profile.h', 'RF_Governor_Global.h', 'RF_Verify.h')]
defs = []
for l in D1.split('\n'):
    m = re.match(r'^#define ([A-Za-z_][A-Za-z_0-9]*)[ \t]+(\(?-?[0-9][0-9xXa-fA-F]*[uUlL]*\)?(?:[ \t]*[-+*/<>|&]+[ \t]*\(?[0-9][0-9xXa-fA-F]*[uUlL]*\)?)*)[ \t]*(//.*)?$', l)
    if m: defs.append('#define %s %s' % (m.group(1), m.group(2)))
defs = '\n'.join(defs)
def protos(text):   # a prototype for every routine a file defines at the left margin
    out = []
    text = re.sub(r'//[^\n]*', '', text)
    for m in re.finditer(r'^(?:FLASHMEM |FASTRUN )?((?:static )?(?:inline )?(?:void|bool|int|uint8_t|uint16_t|uint32_t|float|char \*|const char \*|const float \*) ?\**[A-Za-z_][A-Za-z_0-9]*\([^;{}=]*\))[ \t]*(?://[^\n]*)?\n?[ \t]*\{', text, re.M):
        out.append(m.group(1).replace('inline ', '') + ';')
    return '\n'.join(out) + '\n'
mb = re.search(r'static bool BlockWasReading = false;.*?\nstatic void BlockItemSeen\(uint8_t item\)\n\{.*?\n\}\n', TR, re.S).group(0)
i25 = TR.index('    case 25: // ROTORFLIGHT config'); i37 = TR.index('    case 37:', i25)
i32 = TR.index('    case 32:', i37); i35 = TR.index('    case 35:', i32)
cases = TR[i25:i37] + TR[i32:i35]
sd = lift(TR, 'FASTRUN void SendData()')
m_sd = re.search(r'    if \(ParametersToBeSentPointer && !ParamPause\)\n    \{\n        NumberOfChangedChannels = GetExtraParameters\(\);\n        --ParametersToBeSentPointer;\n        if \(!ParametersToBeSentPointer\)\n            ParamPause = true;[^\n]*\n    \}\n', sd)
if not m_sd: raise SystemExit('SendData: its lines for the parameter queue are not as I read them')
SD_LINES = m_sd.group(0)
if 'if ((millis() - LastPacketSentTime) < FHSS_data::PaceMaker)\n        return;' not in sd: raise SystemExit('SendData: its pace is not as I read it')
HAS_OVER = 'void RfReadsOver()' in RF
_m = re.search(r'^inline void RfOtherReadsOver\(\)[^\n]*', D1, re.M)   # (suite) the nineteenth review's rule: a page's read is over when another page's begins
OTHER_READS_OVER = _m.group(0) if _m else ''
rates_parts = ''.join(lift(RT, h) for h in (
    'FLASHMEM void SendEditedRates()', 'FLASHMEM void RatesMsg(const char *msg, uint16_t Colour)', 'FLASHMEM void HideRATESMsg()', 'FLASHMEM static void RatesAskValues()',
    'FLASHMEM static void RatesQueueWrite()', 'FLASHMEM void ShowRatesBank()', 'FLASHMEM void StartRFRatesView()', 'FLASHMEM void EndRFRatesView()', 'FLASHMEM void RatesWereEdited()'))
ph_parts = ''.join(lift(PH, h) for h in (
    'static bool RfMayFly()', 'static void RfWordPageSays(int view, const char *why)', 'static void RfBoxOrQuiet(const char *page, const char *msg)'))
ph_parts2 = ''.join(lift(PH, h) for h in (
    'FLASHMEM static void BankCheckRefuse(const char *why, bool armed', 'FLASHMEM void BankCheck(bool rates, int want, void (*then)(), const char *page)', 'FLASHMEM static void BankCheckTick()', 'void FcBankTick()'))
rf_parts = lift(RF, 'FLASHMEM void ShowRFRate()') + lift(RF, 'FLASHMEM void ShowRFBank()') + (lift(RF, 'FLASHMEM void RfReadsOver()') if HAS_OVER else '') + lift(RF, 'FLASHMEM void RotorFlightStart()') + lift(RF, 'FLASHMEM void RotorFlightEnd()')
pm_parts = ''.join(lift(PM, h) for h in ('bool RfParamOverPipe(uint8_t id)', 'void PipeOn()', 'bool PipePageShowing()', 'void PipeTick()', 'void ShowPipeState()', 'void PipeOff()', 'void PipeFlush()', 'bool RfLive()',
                                          'void AddParameterstoQueue(uint8_t ID)', 'void ActuallySendParameters(uint32_t RightNow)'))
sw_parts = one(SW, 'uint8_t BanksCount()') + lift(SW, 'uint8_t BankOf123()') + one(SW, 'static uint8_t UpperBank()') + lift(SW, 'void ReadBankSwitch()') + lift(SW, 'void ReadAutoAndMotorSwitch()') + lift(SW, 'void BankHasChanged()')
main_parts = lift(MAIN, 'void GetBank()') + lift(MAIN, 'void FASTRUN ManageTransmitter()')
tr_parts = lift(TR, 'uint16_t GetFirstWordFromAckPayload()') + lift(TR, 'uint16_t GetSecondWordFromAckPayload()') \
    + lift(TR, 'void ReadRatesBytesFromAckPayload(uint8_t n, uint8_t m)') + lift(TR, 'void ReadRates_Advanced_FromAckPayload(uint8_t n, uint8_t m)') \
    + lift(TR, 'void ReadPIDs_Advanced_FromAckPayload(uint8_t n, uint8_t m)') + lift(TR, 'void ReadGovBytesFromAckPayload(uint8_t n, uint8_t m)') \
    + ''
tr_parts2 = lift(TR, 'static void BlockSilence(const char *what)') + lift(TR, 'void Hide_msg_if_needed()') + mb
whole_text = '\n'.join(WHOLE)
prog = r'''
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cstdlib>
#include <cctype>
#include <string>
#include <vector>
#include <map>
#include <deque>
#include <algorithm>
#define FLASHMEM
#define FASTRUN
#define DMAMEM
#define PROGMEM
#define PSTR(x) x
#define CRUMB(x)
#define KEEP_WHOLE(id, thing)
''' + defs + '\n' + re.search(r'enum \{ VK_NONE = 0[^\n]*', D1).group(0) + r'''
// ------------------------------------------------------------------ the clock (mine): microseconds
static uint64_t us_ = 5000000ull; static uint32_t millis() { return (uint32_t)(us_ / 1000ull); }
static uint32_t rnd_ = 1; static uint32_t rnd() { rnd_ = rnd_ * 1664525u + 1013904223u; return rnd_ >> 8; } static int rr(int lo, int hi) { return lo + (int)(rnd() % (uint32_t)(hi - lo + 1)); }
static int HK_US = 1500;          // what the once-a-second round costs (mine)
static int FAST_US = 150;         // what the 50 ms round costs (mine)
static int PASS_LO = 30, PASS_HI = 90, RADIO_LO = 400, RADIO_HI = 700;   // a pass of loop(); a packet on the air (mine)
static int GET_US = 12000;        // one "get" of a box (mine)
static void world();
static void DelayWithDog(uint32_t ms) { const uint64_t end = us_ + (uint64_t) ms * 1000ull; while (us_ < end) { us_ += 1000; world(); } }
// ------------------------------------------------------------------ what the lifted routines need from the rest of the firmware
static int CurrentView = 0, CurrentMode = NORMAL; static uint8_t Bank = 1, DualRateInUse = 1, PreviousBank = 1, PreviousDualRateInUse = 1;
static bool BlockBankChanges = false, Rates_Advanced_Were_Edited = false, Rates_Were_Edited = false, PIDS_Were_Edited = false, PIDS_Advanced_Were_Edited = false, GOVS_PROFILE_Were_Edited = false, GOVS_GLOBAL_Were_Edited = false;
static bool RATES_Loaded = false, RATES_ADV_Loaded = false, PIDS_ADV_Loaded = false, PIDS_Loaded = false, GOV_Loaded = false;
static bool Reading_PIDS_Now = false, Reading_RATES_Now = false, Reading_RATES_Advanced_Now = false, Reading_PIDS_Advanced_Now = false, Reading_GOV_Now = false, Reading_GOV_Config_Now = false;
OTHER_READS_OVER_LINE
static uint32_t RATES_Start_Time = 0, RATES_Advanced_Start_Time = 0, PID_Start_Time = 0, PID_Advanced_Start_Time = 0, GOV_Start_Time = 0, GOV_Global_Start_Time = 0;
static uint16_t RATES_Send_Duration = 0, PID_Send_Duration = 0, Rates_Advanced_Send_Duration = 0, PID_Advanced_Send_Duration = 0; static uint32_t GOV_Send_Duration = 0, GOV_Config_Send_Duration = 0;
static uint16_t BlockSeen = 0; static bool BlockShown = false; static uint32_t FcBankAskAt = 0, FcBankAskAt2 = 0;
static bool ModelMatched = true, BoundFlag = true, LedWasGreen = true, LedWasRed = false, LedIsBlinking = false, Connected = true; static uint8_t PipeState = 2; static bool PipeWanted = false; static uint32_t PipeAskedMs = 0;
static bool bakOffline = false; static bool BakOffline() { return bakOffline; } static bool BakHaveFile() { return false; } static bool BakOfflineWords(uint8_t) { return true; } static void BakOfferTick() {} static void BakOfferEdits() {}
static uint8_t ParametersToBeSentPointer = 0; static uint16_t ParametersToBeSent[PARAMETER_QUEUE_MAXIMUM + 1]; static bool ParamPause = true; static uint32_t LedGreenMoment = 0; static uint8_t LastConnectionQuality = 0;
static bool MotorEnabled = false, MotorWasEnabled = false, SafetyON = true, SafetyWasOn = true, UseMotorKill = true, SixBanks = false, SendNoData = false, BuddyPupilOnWireless = false, BuddyHasAllSwitches = false;
static uint8_t SafetySwitch = 2, BankSwitch = 4, Autoswitch = 1; static uint8_t pos[9] = {0, 3, 1, 0, 1, 0, 0, 0, 0};
static uint8_t GetSwitchPosition(uint8_t n) { return n >= 1 && n <= 8 ? pos[n] : 0; }
static bool SafetyIsDefined() { return SafetySwitch != 0; } static bool SafetyIsOff() { return SafetyIsDefined() && !SafetyON; }
static bool RadiosMustBeOff() { return SafetyIsDefined() ? SafetyIsOff() : MotorEnabled; }
static bool LogMustWait() { return RadiosMustBeOff() || (!SafetyIsDefined() && BoundFlag && ModelMatched); }
static bool ModelSeemsArmed(char *, size_t) { return false; } static bool RfPipeBlocked(char *, size_t) { return false; }
static bool RxHasPipe() { return true; } static bool copyRun = false, easyHold = false; static bool CopyBankRunning() { return copyRun; } static bool EasyHoldsBanks() { return easyHold; }   // (suite, e99c work: a trial may set them)
static bool ScreenIsBig() { return false; } static bool RfLeaveAfterSave = false; static int RfLeaveView = -1; static void (*RfLeaveFn)() = nullptr; bool RfHomeNotRead = false;
static bool QuestionClosedItself = false, QuestionOvertaken = false, ModalWaits = false, RfValueWasCut = false; static uint32_t BoxesLost = 0, BoxesLostAtWork = 0;
static uint8_t RotorFlight_V = 2; static float RotorFlight_Version = 2.3f; static float RFVersions[3] = {0.0f, 2.2f, 2.3f}; static bool LinkRatesToBanks = false, UseLog = false, AnnounceBanks = false, BankSoundHeld = false;
static char ModelName[20] = "Havoc"; static char BankNames[40][12] = {"Bank 1", "Bank 2", "Bank 3", "Bank 4", "Bank 5", "Bank 6"}; static uint8_t BanksInUse[6] = {0, 1, 2, 3, 4, 5}; static uint32_t ModelNumber = 1;
static uint16_t PID_Values[MAX_PID_WORDS], PID_Boost_Values[3], PID_HSI_Offset_Values[2], SendBuffer[16];
static uint8_t Rate_Values[MAX_RATES_BYTES], Rate_Advanced_Values[MAX_RATES_ADVANCED_BYTES], PID_Advanced_Values[MAX_PIDS_ADVANCED_BYTES], GovAckPayload[GOV_ACK_PAYLOAD_SIZE], GovWritePayload[GOV_ACK_PAYLOAD_SIZE];
static uint16_t Saved_PID_Values[17][6]; static uint8_t Saved_PID_Advanced_Values[26][6], Saved_Rate_Advanced_Values[15][6], Saved_Rate_Values[13][6], Saved_GOV_Profiles_Values[GOV_PROFILE_PAYLOAD_SIZE][6], Saved_GOV_Config_Values[GOV_CONFIG_PAYLOAD_SIZE];
static char PID_Labels[17][5] = {"n0", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9", "n10", "n11", "n12", "n13", "n14", "n15", "n16"};
static char RatesWindows[MAX_RATES_BYTES][5] = {"t10", "tn0", "tn1", "tn2", "tn3", "tn4", "tn5", "tn6", "tn7", "tn8", "tn9", "tn10", "tn11"};
static int Trims[BANKS_USED + 1][CHANNELSUSED + 1], LastTrim[BANKS_USED + 1][CHANNELSUSED + 1];
static bool Wait_for_Advanced_Rates_to_Be_Sent_Too = false; static uint8_t DualRateRate[BANKS_USED + 1];
struct { uint8_t Ack_Payload_byte[8]; } AckPayload;
enum { KEPT_PIDS = 0, KEPT_PIDS_ADV, KEPT_RATES, KEPT_RATES_ADV, KEPT_GOV_PROFILE, KEPT_GOV_GLOBAL };
static bool KeptCopy(int, int) { return true; } static bool KeptHasPlace(int) { return true; } static void MarkKept(int, int) {} static const char *KeptNoneText(int) { return "no copy kept"; }
static void SaveOneModel(uint32_t) {}
// ---- the screen as this board writes it
struct Cmd { int kind; int id, w1, w2, snap; };   // 0: a page command (the screen loads a page: no pass of its loop meanwhile); 1: "ldrctx id,..."; 2: "ldrcpipe on"
static std::deque<Cmd> cmdQ; static std::map<std::string, std::string> fields; static std::vector<std::string> pagesSent;
static bool busyUp = false;
static bool watchFront = false; static std::vector<std::string> frontSent;   // (suite, e99c work) what is written to the front page after the motor switch
static void SendCommand(char *c) { if (!strncmp(c, "page ", 5)) { cmdQ.push_back({0, 0, 0, 0, 0}); busyUp = false; pagesSent.push_back(c + 5); } if (!strcmp(c, "vis busy,1")) busyUp = true; if (!strcmp(c, "vis busy,0")) busyUp = false;
                                   if (!strncmp(c, "ldrcpipe on", 11)) cmdQ.push_back({2, 0, 0, 0, 0});
                                   if (!strncmp(c, "ldrcpipe off", 12)) cmdQ.push_back({3, 0, 0, 0, 0});   // (suite, e99c work) the screen lets the pipe go: the words not yet sent are dropped
                                   if (watchFront && CurrentView == FRONTVIEW && strncmp(c, "page FrontView", 14) && strncmp(c, "ldrcpipe", 8) && strcmp(c, "vis Warning,0")) frontSent.push_back(c);
                                   if (!strncmp(c, "vis ", 4)) { std::string s(c + 4); const size_t k = s.find(','); fields["vis:" + s.substr(0, k)] = s.substr(k + 1); } }
static int savedSaid = 0, notSavedSaid = 0, notConfSaid = 0;   // (suite, e99d) the read-back's verdicts, by their words
static void SendText(char *n, char *t) { if (strstr(t, "Saved, and confirmed")) ++savedSaid; if (watchFront && CurrentView == FRONTVIEW && strcmp(n, "bt0")) frontSent.push_back(std::string("text ") + n); fields[n] = t; }
static void SendValue(char *n, int v) { if (watchFront && CurrentView == FRONTVIEW) frontSent.push_back(std::string("value ") + n); fields[n] = std::to_string(v); }
static uint32_t GetValue(char *n) { us_ += (uint64_t) GET_US; world(); auto it = fields.find(n); return it == fields.end() ? 0 : (uint32_t) atoi(it->second.c_str()); }
static int GetText(char *n, char *out, size_t size) { us_ += (uint64_t) GET_US; world(); auto it = fields.find(n); if (it == fields.end()) { out[0] = 0; return 0; } snprintf(out, size, "%s", it->second.c_str()); return (int) strlen(out); }
static bool TextMustBeNumber(const char *, char *) { return true; }
static void RfGatherStart() {} static bool RfFieldsMissed(const char *) { return false; } static bool WorkLostABox() { return false; } static bool BoxesHaveNoPage() { return false; }
static int boxes = 0, sounds = 0, quietSaid = 0; static std::string lastBox; static uint32_t BOX_MS = 1500;
static void MsgBox(char *, char *m) { ++boxes; lastBox = m; if (strstr(m, "NOT SAVED")) ++notSavedSaid; if (strstr(m, "NOT CONFIRMED")) ++notConfSaid; RfLeaveAfterSave = false; QuestionOvertaken = false; DelayWithDog(BOX_MS); }   // (the pilot reads it and presses OK: no switch is read meanwhile)
static void PlaySound(int) { ++sounds; }
static bool confirmAnswer = true, saveNowAnswer = false; static int questions = 0;
static bool GetConfirmation(char *, char *) { ++questions; RfLeaveAfterSave = false; DelayWithDog(BOX_MS); return confirmAnswer; }
static bool GetSaveOrDiscard(char *, char *) { ++questions; QuestionClosedItself = false; DelayWithDog(BOX_MS); return saveNowAnswer; }
static void RfSayQuietly(const char *m) { ++quietSaid; if (strstr(m, "NOT SAVED")) ++notSavedSaid; if (strstr(m, "NOT CONFIRMED")) ++notConfSaid; } static void KeepScreenNote(const char *, bool) {}
static void LogText(char *, uint16_t, bool) {} static void LogNewBank() {} static void SoundBank() {}
static char *Str(char *s, int n, int) { sprintf(s, "%d", n); return s; }
static void UndoNewVisit() {} static bool RfHomeBackAnswer = false; static int homeBacks = 0; static bool RfHomeBack() { if (RfHomeBackAnswer) { ++homeBacks; CurrentView = GUIDEVIEW; return true; } return false; }
static bool HelpTookRead = false; static int helpFrom = -1;   // (suite) e99: main.cpp HelpWordCame / the return from Help (below)
static bool UndoPreBusy() { return false; } static uint8_t UndoFnOfView(int) { return 0; } static void UndoPreGo(uint8_t, int, void (*then)(), const char *, int) { then(); }
static void UndoPreSave(uint8_t, int, void (*then)(), const char *) { then(); }
static void ZeroGapStats() {}
// the pages that are not lifted
static void DisplayRatesValues(uint8_t, uint8_t) {} static void ShowRatesLocalBank() { BlockBankChanges = false; } static void SaveRatesLocalBank() {} static void ReadEditedRateValues() {} static bool RatesTypeBad(const char *) { return false; }
static void ForegroundColourRATESLabels(uint16_t) {} static void Modify_Labels_For_RATES_View() {} static void RfCutNote(const char *) { RfValueWasCut = false; }
static void UpdateTrimView() {} static void ShowBank() {} static void UpdateModelsNameEveryWhere() {} static void DisplayCurveAndServoPos() {} static void ReadSpeedsScreen(int, bool) {} static void NoteBoxesLost() {} static void UpdateSpeedScreen() {}
static void DisplayNewDualRateBank() {} static int rescueBankChanges = 0; static void RescueBankChanged() { ++rescueBankChanges; } static void EasyBankChanged() {}
// ---- the pipe's own requests (PipeHttp.h MspAsk): MSP 101 answered by my flight controller after a Bluetooth round trip
static int PipeReqId = 0, PipeRepId = -1, PipeRepCode = 0; static char PipeRepBody[1600]; static uint32_t PipeReqSentMs = 0;
static bool PipeReplyReady(int id) { return PipeRepId == id; } static bool PipeReplyLate() { return millis() - PipeReqSentMs > 9000; }
static int PipeReplyBytes(uint8_t *out, int max) { int n = 0; const char *p = PipeRepBody; while (p[0] && p[1] && n < max) { char h[3] = {p[0], p[1], 0}; out[n++] = (uint8_t) strtol(h, nullptr, 16); p += 2; } return n; }
static int mspPendingId = 0; static uint32_t mspAnswerAt = 0; static bool mspMute = false; static int fcArmed = 0;
static int MspAsk(uint8_t fn, const uint8_t *, int) { ++PipeReqId; PipeRepId = -1; PipeReqSentMs = millis(); if (fn == 101 && !mspMute) { mspPendingId = PipeReqId; mspAnswerAt = millis() + (uint32_t) rr(60, 180); } return PipeReqId; }
static void mspWorld() { if (mspPendingId && (int32_t)(millis() - mspAnswerAt) >= 0) { uint8_t b[30]; memset(b, 0, sizeof b); b[6] = (uint8_t) fcArmed; b[23] = (uint8_t)(Bank - 1); b[25] = (uint8_t)(DualRateInUse - 1);
        char *q = PipeRepBody; for (int i = 0; i < 30; ++i) q += sprintf(q, "%02x", b[i]); PipeRepCode = 200; PipeRepId = mspPendingId; mspPendingId = 0; } }
static void ShowServoPos() {}
static uint32_t SilenceMsgUntil = 0; static int SilenceMsgView = -1; static char pRXSetupView[] = "page RXSetupView"; static void GotoFrontView();
union { uint32_t Val32[2]; } ModelsMacUnion;
void AddParameterstoQueue(uint8_t ID); void PipeOff(); void ShowPipeState();
static const uint8_t PIPE_STACK_MAX = 8; static uint8_t PipeStack[PIPE_STACK_MAX]; static uint8_t PipeStackN = 0; static bool PipeReadRefused = false;
''' + pm_parts.replace('SendParameterByPipe(id);', 'SendParameterByPipeModel(id);') .replace('void PipeFlush()', 'static void SendParameterByPipeModel(uint8_t id);\nvoid PipeFlush()') \
    .replace('    ShowSendingParameters();\n', '') + r'''
// ---- prototypes of everything the whole files define (1Definitions.h has them in the firmware)
void RatesMsg(const char *msg, uint16_t Colour); void HideRATESMsg(); void ShowRatesBank(); void RatesWereEdited(); void SendEditedRates(); void EndRFRatesView(); void StartRFRatesView();
void RotorFlightStart(); void Hide_msg_if_needed(); static void BlockMaskTick(); static void BlockItemSeen(uint8_t item);
void BankCheck(bool rates, int want, void (*then)(), const char *page); void SendForegroundColour(const char *label, uint16_t colour);
bool RfVerifyArm(uint8_t kind, void (*ask)()); bool RfVerifyPending(); int RfVerifySet(); bool RfVerifyEnd(uint8_t kind); void RfVerifyTick();
void Start_RF_Governor(); bool AllGlobalConfigBytesReceived(); void ForegroundColourAdvancedRates(uint16_t Colour);
static void RatesAskValues(); static void RatesQueueWrite(); static void PidAskValues(); static void PidAdvAskValues(); static void GovAskValues();
''' + protos(whole_text) + lift(RT, 'FLASHMEM uint8_t RfByteOf(float v)') + ph_parts + whole_text + rates_parts + tr_parts + r'''
static int FcBankReq = 0; static bool FcBankPending = false; static int FcPidBank = 0, FcRateBank = 0;
static bool FcBankPage() { return CurrentView == PIDVIEW || CurrentView == RATESVIEW_RF || CurrentView == RATESADVANCEDVIEW || CurrentView == PIDADVANCEDVIEW || CurrentView == RFGOVERNORVIEW_PROFILE; }
static void FcBankShow() {}
static void (*BcThen)() = nullptr; static int BcReq = 0, BcStep = 0, BcWant = 0, BcView = -1; static uint32_t BcAt = 0; static uint8_t BcUndoFn = 0; static bool BcRates = false; static const char *BcPage = "page RFView";
''' + ph_parts2 + tr_parts2 + r'''
static void ParseTelemetryItem()   // transceiver.h ParseTelemetryItem: its first line, ITS OWN cases 25-30 and 32-34, its last line
{
    BlockMaskTick();
    const uint8_t item = AckPayload.Ack_Payload_byte[0];
    switch (item)
    {
''' + cases + r'''
    default:
        break;
    }
    BlockItemSeen(item);
}
''' + lift(TR, 'void TelemetryFromPipe(const char *list)') + rf_parts + r'''
static int frontPages = 0;
// (suite, e99c work 17 Nov 2026) Motor_sign.h MotorEnabledHasChanged ITSELF, lifted (it was B16's lines copied by hand - and e99c changed them).
// LogFrontPageReason, called inside it right before GotoFrontView, notes what the routine left behind: the moment of the motor's front page.
static uint32_t PreviousModelNumber = 1; static long modelReads = 0; static bool ReadOneModel(uint32_t) { ++modelReads; return true; }   // (e100b, 18 Nov 2026: the Models page's earlier model put back at the motor switch - never here, no Models page: dev/test_modelsarmed runs it)
static bool FlightRestart = false; static char WarnOff[] = "vis Warning,0"; static uint32_t MotorStartTime = 0, MotorOnSeconds = 0, PausedSecs = 0;
static uint32_t LastSeconds = 0; static void ShowMotorTimer(); static void LogMotor(int) {} static void ShowMotor() { fields["bt0"] = MotorEnabled ? "Motor is ON" : "Motor is OFF"; }
static bool anyFlag() { return Reading_PIDS_Now || Reading_RATES_Now || Reading_RATES_Advanced_Now || Reading_PIDS_Advanced_Now || Reading_GOV_Now || Reading_GOV_Config_Now; }
struct MotorCall { bool seen; uint64_t at; bool pend; int kind; uint32_t readStart; int bc; bool blockAfter, flagsAfter; uint8_t radioQ; bool transfer, keepAlive; uint16_t q[4]; uint32_t winEnd; };
static MotorCall mcall;
static int sounds0 = 0, boxes0 = 0, questions0 = 0;
static bool followablePrev = false; static long followDropped = 0;   // (round 25, e99e) a bank page's read-back, its read open, on the pass before the motor's call
static bool freshPrev = false; static long freshKept = 0;   // (round 27, e99g) a bank page's save behind a FRESH ask of its page (not the read-back's own read), that read open, on the pass before the motor's call - and its flags kept up by the call
static void LogFrontPageReason(const char *, const char *, const char * = nullptr) { if (G5_E99E && followablePrev && !(VfKind != VK_NONE && VfReading(VfKind)) && !(VfKind != VK_NONE && VfStart(VfKind) != VfReadStart)) {   /* (round 27: not when a FRESH ask was made in the motor's own pass - e99g stops that one, rightly) */ ++followDropped; if (SHOWIT && followDropped < 40) printf("      [followDropped] VfKind %d flags %d own %d save age %u ms view %d pf %d\n", (int) VfKind, (int) anyFlag(), (int)(VfKind != VK_NONE && VfStart(VfKind) == VfReadStart), (unsigned)(millis() - SAVE_MS_OF_TREE), CurrentView, (int) followablePrev); } if (G5_E99E && freshPrev && anyFlag()) ++freshKept; mcall.seen = true; mcall.at = us_; mcall.pend = RfVerifyPending(); mcall.kind = VfKind; mcall.readStart = VfReadStart; mcall.bc = BcStep;
    mcall.blockAfter = BlockBankChanges; mcall.flagsAfter = anyFlag(); mcall.radioQ = ParametersToBeSentPointer; for (int i = 0; i < 4; ++i) mcall.q[i] = ParametersToBeSentPointer > i ? ParametersToBeSent[ParametersToBeSentPointer - i] : 0; bool realQ = false; for (int i = 1; i <= ParametersToBeSentPointer; ++i) realQ |= RfParamOverPipe((uint8_t) ParametersToBeSent[i]);
    mcall.keepAlive = ParametersToBeSentPointer && !realQ;   // (the radio queue holds no bank's words: every Rotorflight word goes by the pipe - Parameters.h RfParamOverPipe 9-21, 27-33; the radio's are BLUETOOTH_WANTED, MSP_INHIBIT/ENABLE_TELEMETRY, the servos', the clock's)
    mcall.transfer = realQ || CopyBankRunning() || EasyHoldsBanks();
    uint32_t we = mcall.pend ? VfReadStart + (VfKind == VK_GOV_CFG ? RF_VERIFY_GOVCFG_WAIT_MS : RF_VERIFY_WAIT_MS) : 0; auto w = [&](bool f, uint32_t st, uint32_t d) { if (f && st + d > we) we = st + d; };   // the latest window of what is still open at the call
    w(Reading_PIDS_Now, PID_Start_Time, PID_Send_Duration); w(Reading_PIDS_Advanced_Now, PID_Advanced_Start_Time, PID_Advanced_Send_Duration); w(Reading_RATES_Now, RATES_Start_Time, RATES_Send_Duration);
    w(Reading_RATES_Advanced_Now, RATES_Advanced_Start_Time, Rates_Advanced_Send_Duration); w(Reading_GOV_Now, GOV_Start_Time, GOV_Send_Duration); w(Reading_GOV_Config_Now, GOV_Global_Start_Time, GOV_Config_Send_Duration); mcall.winEnd = we; sounds0 = sounds; boxes0 = boxes; questions0 = questions; }
''' + motor_part + r'''
static void SafetyHoldUpdate() {} static void ReadSafetySwitch() { SafetyON = SafetySwitch ? pos[SafetySwitch] != 3 : false; } static void ReadBuddySwitch() {} void ShowRatesBank(); void ShowRatesAdvancedBank(); void ShowRFRate();
static void ReadDualRateSwitch() { if (LinkRatesToBanks && RotorFlight_V) DualRateInUse = Bank;
    if (PreviousDualRateInUse != DualRateInUse) { PreviousDualRateInUse = DualRateInUse; if (CurrentView == RATESVIEW_RF) ShowRatesBank(); if (CurrentView == RATESADVANCEDVIEW) ShowRatesAdvancedBank(); if (CurrentView == ROTORFLIGHTVIEW) ShowRFRate(); } }   // (suite, round 25: Switches.h ReadDualRateSwitch's "Respond to a change" - the Rates, Dynamics and menu pages read the new rate; it was missing, and a linked bank change left the Dynamics page on the old rate's numbers)
static void SafetySwitchChanged() { SafetyWasOn = SafetyON; } static void ReadChannelSwitches9to12() {}
static bool RescueHoldsBanks() { return false; }
''' + sw_parts + r'''
// ---- main.cpp GotoFrontView: its lines that touch what is looked at here (the pipe let go, the telemetry asked for again, the mode, the page)
static void GotoFrontView() { ++frontPages; PipeOff(); AddParameterstoQueue(MSP_ENABLE_TELEMETRY); if (CurrentMode != LISTENMODE) CurrentMode = NORMAL; SendCommand((char *)"page FrontView"); CurrentView = FRONTVIEW; }
// ---- ManageTransmitter's other callers (none of them looked at here): empty, but for the cost of the two rounds
namespace FHSS_data { uint8_t PaceMaker = PACEMAKER; }
static bool ScreenRestartSeen = false, ScreenAnswerOwed = false, ScreenSaidSession = true, VersionMismatch = false; static int ScreenPageId = -1; static uint32_t ScreenSessionNextMs = 0, LastPacketSentTime = 0, LastTimeRead = 0, ThisGap = 0, VolumeRestoreAt = 0;
#define SCREEN_FRONT_PAGE 13
static uint8_t AudioVolume = 50; static char ReceiverVersionNumber[20] = "", TransmitterVersionNumber[20] = "";
static void CheckForNextionButtonPress() {} static void ScreenKeepUp() {} static void KickTheDog() {} static void ProcessRecentCommsGap() {} static void CheckPowerOffButton() {} static void DoTheVariometer() {}
static void RescuePoll() {} static void ServoPoll() {} static void TravelPoll() {} static void BasicsPoll() {} static void EscCalPoll() {} static void FilterPoll() {} static void AdjustPoll() {} static void SwitchPoll() {} static void JobsPoll() {}
static void CopyBankPoll() {} static void BatteryPoll() {} static void BeeperPoll() {} static void ToolsPoll() {} static void BlackboxPoll() {} static void CalibratePoll() {} static void EasyPoll() {} static void RatesCurvePoll() {} static void SubTrimPoll() {} static void BankListenPoll() {}
static void CrumbView(uint32_t) {} static void LogRestartCause() {} static void FlightStampTick() {} static void FlushDeferredLog() {} static void ShowMismatchMsg() {} static void ZeroDataScreen() {}
static int ticks = 0; static void GetFrameRate() { ++ticks; us_ += (uint64_t) HK_US; }   // THE ONCE-A-SECOND ROUND'S OWN TIME (mine): everything in it, charged here
static void CheckScreenTime() {} static void CheckBatteryStates() {} static void SafetyOffWarningTick() {} static void RfRecordTick(bool) {} static void ReadTime() {} static void ShowComms() {} static void CorrectRtcFromPhoneTime() {}
static void ShowMotorTimer() {} static void TellScreen(bool) {} static void SetAudioVolume(int) {} static void TellScreenRx() {} static void ClockMessageTick() {} static void CentreNoteTick() {}
static void CheckModelsScreen(uint32_t) {} static void CheckDualRatesScreen(uint32_t) {} static void CheckMaxCurrent() { us_ += (uint64_t) FAST_US; }   // (the 50 ms round's own time)
static void ReadTheSwitchesAndTrims() {} static void CheckHardwareTrims() {} static void RxUpdateTick() {} static void TellScreenRxTick() {} static void RedLedOn() {} static void PipeModelGoneTick() {} static void BankSyncTick() {} static void ArmTick() {}
static bool RfMayFlyStub() { return false; }
''' + main_parts + r'''
// ---- transceiver.h SendData: its pace and ITS OWN LINES for the parameter queue (a packet on the air takes its time)
static int paramPackets = 0; static int GetExtraParameters() { ++paramPackets; return 12; }
static void radioAck();   // (suite) below, with the receiver
static void SendDataModel() {
    if ((millis() - LastPacketSentTime) < FHSS_data::PaceMaker)
        return;
    LastPacketSentTime = millis();
    int NumberOfChangedChannels = 0;
''' + SD_LINES + r'''
    (void) NumberOfChangedChannels;
    us_ += (uint64_t) rr(RADIO_LO, RADIO_HI);
    radioAck();   // (suite) the packet's acknowledgement, with its telemetry item
}
// =================================================================== the flight controller, the receiver, the screen (my predecessor's models, dev/test_flagsacross)
enum { K_NONE = 0, K_PID, K_RATES, K_RATESADV, K_PIDADV, K_GOVCFG, K_GOVPROF };
static int fcPidV[6][17], fcRatesV[6][13], fcAdvV[6][15], fcPidAdvV[6][26], fcGovV[6][60];
static int fcB() { return Bank - 1; } static int fcR() { return DualRateInUse - 1; }
static uint32_t now_ = 0;
static int rxSend = K_NONE; static uint32_t rxUntil = 0, rxLastFetch = 0; static bool rxRatesValid = false, rxPidValid = false, rxAdvPidValid = false, rxGovProfValid = false, rxGovCfgValid = false;
static bool rxReading = false; static int rxReadKind = 0; static uint32_t rxReadEnd = 0; static int fcMs = 25; static bool fcDead = false; static uint32_t rxWriteUntil = 0; static int writesDone = 0, writeBank = -1;
struct Snap { uint16_t pid[17]; uint8_t rates[13], adv[15], pidadv[26], gov[60]; }; static std::vector<Snap> snaps;
static int wrMs = 250;
// (suite) e99 (the twentieth review, reviewer B's model): THE WRITE'S OWN TIME. The receiver's write lands landLo to landHi ms after its trigger
// word reached it (0, 0: at once, as before), into the bank the flight controller is on THEN; writeLost: it never lands (the receiver's write
// failed - it answers on with the block it has). trigAtUs / landAtUs: the moments of this trial's first trigger word and first landing.
static int landLo = 0, landHi = 0; static bool writeLost = false, pendOn = false, landing = false; static Cmd pendW; static uint32_t pendAt = 0; static uint64_t trigAtUs = 0, landAtUs = 0;
static void rxWords(const Cmd &c) {
    const int id = c.id, w1 = c.w1, w2 = c.w2;
    const bool trig = id == GET_SECOND_11_PID_VALUES || id == GET_SECOND_6_RATES_VALUES || id == GET_RATES_ADVANCED_VALUES_SECOND_8 || id == GET_THIRD_8_ADVANCED_PID_VALUES || id == SEND_GOV_WRITE_PROFILE2 || id == SEND_GOV_WRITE_CONFIG3;
    if (trig && !landing) {   // (suite) e99: the write's own time
        if (!trigAtUs) trigAtUs = us_;
        if (writeLost || landHi > 0) { if (!writeLost) { pendW = c; pendAt = now_ + (uint32_t) rr(landLo, landHi); pendOn = true; } rxWriteUntil = now_ + (uint32_t)(id == SEND_GOV_WRITE_CONFIG3 ? 4 * wrMs : wrMs); return; }
        if (!landAtUs) landAtUs = us_; }
    if (id == GET_SECOND_11_PID_VALUES) { for (int i = 0; i < 17; ++i) fcPidV[fcB()][i] = snaps[c.snap].pid[i]; rxWriteUntil = now_ + wrMs; ++writesDone; writeBank = fcB() + 1; return; }       // the trigger word: the block written into the bank the flight controller is ON
    if (id == GET_SECOND_6_RATES_VALUES) { for (int i = 0; i < 13; ++i) fcRatesV[fcR()][i] = snaps[c.snap].rates[i]; rxWriteUntil = now_ + wrMs; ++writesDone; writeBank = fcR() + 1; return; }
    if (id == GET_RATES_ADVANCED_VALUES_SECOND_8) { for (int i = 0; i < 15; ++i) fcAdvV[fcR()][i] = snaps[c.snap].adv[i]; rxWriteUntil = now_ + wrMs; ++writesDone; writeBank = fcR() + 1; return; }
    if (id == GET_THIRD_8_ADVANCED_PID_VALUES) { for (int i = 0; i < 26; ++i) fcPidAdvV[fcB()][i] = snaps[c.snap].pidadv[i]; rxWriteUntil = now_ + wrMs; ++writesDone; writeBank = fcB() + 1; return; }
    if (id == SEND_GOV_WRITE_PROFILE2) { for (int i = 1; i < 18; ++i) fcGovV[fcB()][i] = snaps[c.snap].gov[i]; rxWriteUntil = now_ + wrMs; ++writesDone; writeBank = fcB() + 1; return; }
    if (id == SEND_GOV_WRITE_CONFIG3) { for (int b = 0; b < 6; ++b) for (int i = 18; i < 42; ++i) fcGovV[b][i] = snaps[c.snap].gov[i]; rxWriteUntil = now_ + 4 * wrMs; ++writesDone; writeBank = 0; return; }
    if (w1 != 321) return;
    if (id == SEND_RATES_VALUES) { rxSend = K_RATES; rxUntil = now_ + w2; rxLastFetch = 0; rxRatesValid = false; }
    if (id == SEND_RATES_ADVANCED_VALUES) { rxSend = K_RATESADV; rxUntil = now_ + w2; rxLastFetch = 0; rxRatesValid = false; }
    if (id == SEND_PID_VALUES) { rxSend = K_PID; rxUntil = now_ + w2; rxLastFetch = 0; rxPidValid = false; }
    if (id == SEND_PID_ADVANCED_VALUES) { rxSend = K_PIDADV; rxUntil = now_ + w2; rxLastFetch = 0; rxAdvPidValid = false; }
    if (id == SEND_GOV_VALUES) { rxSend = K_GOVPROF; rxUntil = now_ + w2; rxLastFetch = 0; rxGovProfValid = false; }
    if (id == SEND_GOV_CONFIG_VALUES) { rxSend = K_GOVCFG; rxUntil = now_ + w2; rxLastFetch = 0; rxGovCfgValid = false; }
}
static int rdBank = 0;
static void rxLoop() {
    if (pendOn && (int32_t)(now_ - pendAt) >= 0) { if (!landAtUs) landAtUs = us_; pendOn = false; landing = true; const uint32_t keep = rxWriteUntil; rxWords(pendW); rxWriteUntil = keep; landing = false; }   // (suite) e99: the write lands now
    if ((int32_t)(now_ - rxWriteUntil) < 0) return;   // (the receiver writes first - its read, write, check, save - then answers)
    if (rxReading) { if ((int32_t)(now_ - rxReadEnd) >= 0) { rxReading = false; if (!fcDead) { rdBank = fcB(); if (rxReadKind == K_RATES || rxReadKind == K_RATESADV) rxRatesValid = true; if (rxReadKind == K_PID) rxPidValid = true; if (rxReadKind == K_PIDADV) rxAdvPidValid = true;
                                                                             if (rxReadKind == K_GOVPROF) rxGovProfValid = true; if (rxReadKind == K_GOVCFG) rxGovCfgValid = true; } } return; }
    if (rxSend != K_NONE && (int32_t)(now_ - rxUntil) < 0 && (rxLastFetch == 0 || now_ - rxLastFetch >= 50)) { rxLastFetch = now_; rxReading = true; rxReadKind = rxSend; rxReadEnd = now_ + fcMs; }
}
static std::string hex4(int a, int b, int c, int d) { char s[12]; snprintf(s, sizeof s, "%02X%02X%02X%02X", a & 255, b & 255, c & 255, d & 255); return s; }
static std::string rxItems() {
    std::string t; const int b = fcB(), r = fcR();
    if ((int32_t)(now_ - rxWriteUntil) < 0) return t;   // (the receiver is writing: it tells nothing until its write, check and save are done)
    auto add = [&](int item, const std::string &h) { t += (t.empty() ? "ldrctel " : " ") + std::to_string(item) + ":" + h; };
    if (rxSend == K_RATES && rxRatesValid) { const int *v = fcRatesV[r]; add(25, hex4(v[0], v[1], v[2], v[3])); add(26, hex4(v[4], v[5], v[6], 0)); add(27, hex4(v[7], v[8], v[9], v[10])); add(28, hex4(v[11], v[12], 0, 0)); }
    else if (rxSend == K_RATESADV && rxRatesValid) { const int *v = fcAdvV[r]; for (int k = 0; k < 3; ++k) add(25 + k, hex4(v[4 * k], v[4 * k + 1], v[4 * k + 2], v[4 * k + 3])); add(28, hex4(v[12], v[13], v[14], 0)); }
    else if (rxSend == K_PID && rxPidValid) { const int *v = fcPidV[b]; for (int k = 0; k < 6; ++k) add(25 + k, hex4(v[2 * k], v[2 * k] >> 8, v[2 * k + 1], v[2 * k + 1] >> 8)); add(32, hex4(v[12], v[12] >> 8, v[13], v[13] >> 8)); add(33, hex4(v[14], v[14] >> 8, 0, 0)); add(34, hex4(v[15], v[15] >> 8, v[16], v[16] >> 8)); }
    else if (rxSend == K_PIDADV && rxAdvPidValid) { const int *v = fcPidAdvV[b]; for (int k = 0; k < 6; ++k) add(25 + k, hex4(v[4 * k], v[4 * k + 1], v[4 * k + 2], v[4 * k + 3])); add(32, hex4(v[24], v[25], 0, 0)); }
    else if (rxSend == K_GOVPROF && rxGovProfValid) { const int *v = fcGovV[b]; for (int k = 0; k < 4; ++k) add(25 + k, hex4(v[4 * k], v[4 * k + 1], v[4 * k + 2], v[4 * k + 3])); add(29, hex4(v[16], v[17], 0, 0)); }
    else if (rxSend == K_GOVCFG && rxGovCfgValid) { const int *v = fcGovV[b]; for (int k = 0; k < 6; ++k) add(25 + k, hex4(v[18 + 4 * k], v[19 + 4 * k], v[20 + 4 * k], v[21 + 4 * k])); }
    return t;
}
// ---- (suite) THE RADIO'S TELLING. RXV2 Radio.h: every acknowledgement carries ONE telemetry item, in rotation (0 to 40); the block's items
// (25-30, 32-34) only while the read window is open AND the block asked for has its bytes (TxParams.h fillParamAck) - otherwise the rotation
// steps past them (to 31, to 35). The same block, the same window, the same bytes as the Bluetooth answer (rxItems).
static bool radioOn = true, pipeTells = true; static int radioItem = 0; static long radioItemsTold = 0;
static int LOSS_PCT = 0; static bool SEND31 = false; static long acksLost = 0; static int radioBudget = -1;   // (suite) e99: reviewer A's --loss, --send31; part l's cut (-1: none)
static bool rxFill(int item, uint8_t *o) {
    if (rxSend == K_NONE || (int32_t)(now_ - rxUntil) >= 0) return false;
    const std::string t = rxItems(); char key[8]; snprintf(key, sizeof key, " %d:", item); const size_t k = t.find(key); if (k == std::string::npos) return false;
    const char *p = t.c_str() + k + strlen(key); for (int i = 0; i < 4; ++i) { char h[3] = {p[2 * i], p[2 * i + 1], 0}; o[i] = (uint8_t) strtol(h, nullptr, 16); } return true;
}
static void ParseTelemetryItem();
static void radioAck() {
    if (!radioOn || !LedWasGreen) return;
    if (++radioItem > 40) radioItem = 0;
    uint8_t o[4] = {0, 0, 0, 0}; const bool blockItem = (radioItem >= 25 && radioItem <= 30) || (radioItem >= 32 && radioItem <= 34);
    if (blockItem && !rxFill(radioItem, o)) { radioItem = radioItem <= 30 ? 31 : 35; if (SEND31 && radioItem == 31 && !(LOSS_PCT && (int)(rnd() % 100u) < LOSS_PCT)) { AckPayload.Ack_Payload_byte[0] = 31; AckPayload.Ack_Payload_byte[1] = 2; for (int i = 1; i < 4; ++i) AckPayload.Ack_Payload_byte[1 + i] = 0; ParseTelemetryItem(); } return; }
    if (LOSS_PCT && (int)(rnd() % 100u) < LOSS_PCT) { ++acksLost; return; }   // (suite) e99, reviewer A's model: this acknowledgement never reached the transmitter
    if (!blockItem) { if (SEND31 && radioItem == 31) { AckPayload.Ack_Payload_byte[0] = 31; AckPayload.Ack_Payload_byte[1] = 2; for (int i = 1; i < 4; ++i) AckPayload.Ack_Payload_byte[1 + i] = 0; ParseTelemetryItem(); } return; }   // (the other items are not this run's)
    if (radioBudget == 0) return; if (radioBudget > 0) --radioBudget;   // (suite) e99, part l: the telling cut after a few items
    AckPayload.Ack_Payload_byte[0] = (uint8_t) radioItem; for (int i = 0; i < 4; ++i) AckPayload.Ack_Payload_byte[1 + i] = o[i];
    ++radioItemsTold; ParseTelemetryItem();
}
static std::deque<Cmd> bleTxQueue; static std::deque<std::string> bleMail; static std::string bleTelLast; static uint32_t bleTelAt = 0, blePollUntil = 0, blePollLast = 0;
static bool bleIn = false, bleMidDone = false, blePost = false; static Cmd bleWords; static uint32_t bleMid = 0, bleEnd = 0, bleNextTick = 0; static std::string bleBody; static bool bleLinkDead = false;
static bool blePipeShut = false; static uint32_t pipeJoinAt = 0;   // (suite, e99c work) the screen's pipe let go; joined again at
static uint32_t screenBusyUntil = 0; static int bleRtLo = 40, bleRtHi = 120, pageLo = 120, pageHi = 380;
static int tellings = 0;
static void bleTellItems(const std::string &tel) { if (tel.empty() || !pipeTells) return; if (tel == bleTelLast && now_ - bleTelAt < 600) return; bleTelLast = tel; bleTelAt = now_; bleMail.push_back(tel); }
static void bleTask() {
    if (bleIn) {
        if (!bleMidDone && (int32_t)(now_ - bleMid) >= 0) { bleMidDone = true; if (!bleLinkDead) { if (blePost) rxWords(bleWords); bleBody = rxItems(); } else bleBody.clear(); }
        if ((int32_t)(now_ - bleEnd) < 0) return;
        bleIn = false; bleNextTick = now_ + 20;
        if (bleLinkDead) return;
        if (blePost) { const int id = bleWords.id; if (bleWords.w1 == 321 && (id == 9 || id == 12 || id == 15 || id == 18 || id == 27 || id == 28)) { int w = bleWords.w2 < 1000 ? 1000 : bleWords.w2 > 15000 ? 15000 : bleWords.w2; blePollUntil = now_ + (uint32_t) w; bleTelLast.clear(); } }
        bleTellItems(bleBody);
        return;
    }
    if ((int32_t)(now_ - bleNextTick) < 0) return;
    bleNextTick = now_ + 20;
    if (blePipeShut) return;   // (suite, e99c work) the link let go: nothing sent, nothing polled
    if (!bleTxQueue.empty()) { bleWords = bleTxQueue.front(); bleTxQueue.pop_front(); const int rt = rr(bleRtLo, bleRtHi); bleIn = true; bleMidDone = false; blePost = true; bleMid = now_ + rt / 2; bleEnd = now_ + rt; return; }
    if (blePollUntil && (int32_t)(now_ - blePollUntil) < 0 && now_ - blePollLast > 200) { blePollLast = now_; const int rt = rr(bleRtLo, bleRtHi); bleIn = true; bleMidDone = false; blePost = false; bleMid = now_ + rt / 2; bleEnd = now_ + rt; return; }
    if (blePollUntil && (int32_t)(now_ - blePollUntil) >= 0) blePollUntil = 0;
}
static void screenLoop() {
    if ((int32_t)(now_ - screenBusyUntil) < 0) return;
    if (!bleMail.empty()) { const std::string m = bleMail.front(); bleMail.pop_front(); ++tellings; TelemetryFromPipe(m.c_str() + 8); }
    while (!cmdQ.empty()) {
        const Cmd c = cmdQ.front(); cmdQ.pop_front();
        if (c.kind == 0) { screenBusyUntil = now_ + rr(pageLo, pageHi); return; }
        if (c.kind == 1) { if (!blePipeShut && bleTxQueue.size() < 16) bleTxQueue.push_back(c); }
        if (c.kind == 2) { bleTelLast.clear(); pipeJoinAt = now_ + (uint32_t) rr(400, 1500); }   // (suite, e99c work) joined again a moment later
        if (c.kind == 3) { bleTxQueue.clear(); blePollUntil = 0; blePipeShut = true; pipeJoinAt = 0; }   // (suite, e99c work) ble_device.h blePipeCommand "off": the queue cleared, the poll stopped, the link let go
    }
}
static void SendParameterByPipeModel(uint8_t id) {   // Parameters.h SendParameterByPipe / LoadOneParameter: the words as the screen is given them
    int w1 = 0, w2 = 0, snap = 0;
    if (id == SEND_PID_VALUES) { w1 = 321; w2 = PID_Send_Duration; } else if (id == SEND_RATES_VALUES) { w1 = 321; w2 = RATES_Send_Duration; } else if (id == SEND_RATES_ADVANCED_VALUES) { w1 = 321; w2 = Rates_Advanced_Send_Duration; }
    else if (id == SEND_PID_ADVANCED_VALUES) { w1 = 321; w2 = PID_Advanced_Send_Duration; } else if (id == SEND_GOV_VALUES) { w1 = 321; w2 = (int) GOV_Send_Duration; } else if (id == SEND_GOV_CONFIG_VALUES) { w1 = 321; w2 = (int) GOV_Config_Send_Duration; }
    else { Snap s; for (int i = 0; i < 12; ++i) s.pid[i] = PID_Values[i]; for (int i = 0; i < 3; ++i) s.pid[12 + i] = PID_Boost_Values[i]; for (int i = 0; i < 2; ++i) s.pid[15 + i] = PID_HSI_Offset_Values[i];
           memcpy(s.rates, Rate_Values, 13); memcpy(s.adv, Rate_Advanced_Values, 15); memcpy(s.pidadv, PID_Advanced_Values, 26); memcpy(s.gov, GovWritePayload, 59); snaps.push_back(s); snap = (int) snaps.size() - 1; }
    cmdQ.push_back({1, id, w1, w2, snap});
}
static uint32_t lastWorld = 0;
static void world() { const uint32_t m = millis(); while ((int32_t)(m - lastWorld) >= 5) { lastWorld += 5; now_ = lastWorld; rxLoop(); bleTask(); screenLoop(); mspWorld();
    if (pipeJoinAt && (int32_t)(now_ - pipeJoinAt) >= 0) { pipeJoinAt = 0; blePipeShut = false; if (PipeWanted && PipeState == 1) PipeState = 2; } } }   // (suite, e99c work) "ldrcpipe=2"
// ---- loop(): ManageTransmitter, then SendData; the pass takes its microseconds
static uint64_t blockSince = 0; static bool blockWas = false; static uint64_t longestBlock = 0;
static long twoFlags = 0;   // (suite) passes of the loop that found more than one reading flag up
static uint64_t vfDownSince = 0; static bool vfDownCounted = false; static long vfDownLong = 0; static uint64_t vfDownMost = 0; static long vfPendFlagDown = 0;   // (suite, e99d G5) a read-back pending with its kind's flag down: since when; episodes over 100 ms; the longest
#define NET_BOUND_MS 6500   // (suite, e99d) the released firmware's motor road: the bank switch freed by the five-second net (Switches.h ReadBankSwitch) - 5.0 s quiet + a pass of the once-a-second round + BLUETOOTH_WANTED's restarts (5.86 s the most measured)
static void loopPass() {
    world();
    ManageTransmitter();
    SendDataModel();
    us_ += (uint64_t) rr(PASS_LO, PASS_HI);
    if ((int) Reading_PIDS_Now + (int) Reading_RATES_Now + (int) Reading_RATES_Advanced_Now + (int) Reading_PIDS_Advanced_Now + (int) Reading_GOV_Now + (int) Reading_GOV_Config_Now > 1) ++twoFlags;
#if G5_E99E
    // (suite, e99e test work: G4/G5 under e99e's one rule) a read-back whose own read is not the one open (kept on another page, or behind a fresh ask) is gone
    // 4.1 s after its save at the latest (RF_VERIFY_WAIT_MS + two 50 ms rounds); an episode = a save still held past that; the most = its age at the oldest
    if (VfKind != VK_NONE && !(VfReading(VfKind) && VfStart(VfKind) == VfReadStart) && (uint32_t)(millis() - VfArmMs) > RF_VERIFY_WAIT_MS + 100)   /* (round 25: its own definition, not the tree's VfItsRead) */ { const uint64_t d = (uint64_t)(uint32_t)(millis() - VfArmMs) * 1000ull; if (d > vfDownMost) vfDownMost = d; if (!vfDownCounted) { ++vfDownLong; vfDownCounted = true; } }
    else if (VfKind == VK_NONE) vfDownCounted = false;
    if (VfKind != VK_NONE && !VfReading(VfKind) && RfVerifyPending()) ++vfPendFlagDown;   // (by definition none: pending = its flag up)
#else
    if (VfKind != VK_NONE && !VfReading(VfKind)) { if (!vfDownSince) vfDownSince = us_; else { const uint64_t d = us_ - vfDownSince; if (d > vfDownMost) vfDownMost = d; if (d > 100000ull && !vfDownCounted) { ++vfDownLong; vfDownCounted = true; } } }   // (suite, e99d G5)
    else { vfDownSince = 0; vfDownCounted = false; }
#endif
    followablePrev = VfKind != VK_NONE && VfKind != VK_GOV_CFG && VfReading(VfKind);
#if G5_E99E
    // (round 26, e99f test work) not "followable" in its last 100 ms when its read is not its own: RfVerifyPending lets it go at the save's 4 s, and the
    // motor's call that finds it gone puts the flags down - right (part X, the motor at the more ask, found this monitor's edge once)
    if (followablePrev && VfStart(VfKind) != VfReadStart && (uint32_t)(millis() - VfArmMs) + 100u >= RF_VERIFY_WAIT_MS) followablePrev = false;
    // (round 27, e99g test work) "followed" at the motor switch = the read the read-back ITSELF asked, only: a fresh ask of the page behind the save is
    // stopped there as the released firmware stops every read (its window ends after the save is let go - nobody looked at it on the front page: e99f's finding 1)
    freshPrev = VfKind != VK_NONE && VfKind != VK_GOV_CFG && VfReading(VfKind) && VfStart(VfKind) != VfReadStart;
    if (followablePrev && VfStart(VfKind) != VfReadStart) followablePrev = false;
#endif
}
static void runMs(uint32_t ms) { const uint64_t end = us_ + (uint64_t) ms * 1000ull; while (us_ < end) loopPass(); }
// run until the block is released, or 'most' ms: how long it took (-1: it stood to the end)
static long untilFree(uint32_t most) { const uint64_t t0 = us_, end = us_ + (uint64_t) most * 1000ull; while (us_ < end) { if (!BlockBankChanges) return (long)((us_ - t0) / 1000ull); loopPass(); } return BlockBankChanges ? -1 : (long) most; }
static int motorPos0 = 3;
static void fresh() {
    us_ += (uint64_t) rr(3000000, 3999999);                         // (every phase of the two rounds against the press)
    CurrentView = RXSETUPVIEW; CurrentMode = NORMAL; Bank = PreviousBank = 1; DualRateInUse = PreviousDualRateInUse = 1; pos[4] = 1; pos[1] = (uint8_t) motorPos0; pos[2] = 1; SafetyON = SafetyWasOn = true; MotorEnabled = MotorWasEnabled = false;
    BlockBankChanges = false; Reading_PIDS_Now = Reading_RATES_Now = Reading_RATES_Advanced_Now = Reading_PIDS_Advanced_Now = Reading_GOV_Now = Reading_GOV_Config_Now = false; BlockWasReading = false; BlockSeen = 0; BlockShown = false;
    RATES_Loaded = RATES_ADV_Loaded = PIDS_Loaded = PIDS_ADV_Loaded = GOV_Loaded = false; Rates_Were_Edited = Rates_Advanced_Were_Edited = PIDS_Were_Edited = PIDS_Advanced_Were_Edited = GOVS_PROFILE_Were_Edited = GOVS_GLOBAL_Were_Edited = false;
    fields.clear(); cmdQ.clear(); boxes = 0; questions = 0; quietSaid = 0; savedSaid = notSavedSaid = notConfSaid = 0; PipeStackN = 0; busyUp = false; SilenceMsgUntil = 0; ParametersToBeSentPointer = 0; ParamPause = true; PipeWanted = false; PipeState = 2;
    rxSend = K_NONE; rxUntil = 0; rxRatesValid = rxPidValid = rxAdvPidValid = rxGovProfValid = rxGovCfgValid = false; rxReading = false; fcDead = false; rxWriteUntil = 0; writesDone = 0; writeBank = -1; snaps.clear();
    bleTxQueue.clear(); bleMail.clear(); bleTelLast.clear(); blePollUntil = 0; bleIn = false; bleLinkDead = false; screenBusyUntil = 0; tellings = 0; mspPendingId = 0; mspMute = false; BcStep = 0; VfKind = VK_NONE; RfLeaveAfterSave = false;
    memset(Rate_Values, 0, sizeof Rate_Values); memset(Rate_Advanced_Values, 0, sizeof Rate_Advanced_Values); memset(PID_Values, 0, sizeof PID_Values); memset(PID_Boost_Values, 0, sizeof PID_Boost_Values); memset(PID_HSI_Offset_Values, 0, sizeof PID_HSI_Offset_Values);
    memset(PID_Advanced_Values, 0, sizeof PID_Advanced_Values); memset(GovAckPayload, 0, sizeof GovAckPayload);
    RfHomeBackAnswer = false; frontPages = 0; saveNowAnswer = false; confirmAnswer = true; LedGreenMoment = millis() - 60000; lastWorld = millis() - (millis() % 5);
    pendOn = landing = writeLost = false; trigAtUs = landAtUs = 0; radioBudget = -1; HelpTookRead = false; helpFrom = -1;   // (suite) e99
    copyRun = easyHold = false; blePipeShut = false; pipeJoinAt = 0; watchFront = false; frontSent.clear(); memset(&mcall, 0, sizeof mcall);   // (suite) e99c work
    for (int b = 0; b < 6; ++b) { for (int i = 0; i < 17; ++i) fcPidV[b][i] = 100 * (b + 1) + i; for (int i = 0; i < 13; ++i) fcRatesV[b][i] = 16 * (b + 1) + i; for (int i = 0; i < 15; ++i) fcAdvV[b][i] = 0x40 + 8 * b + i;
                                  for (int i = 0; i < 26; ++i) fcPidAdvV[b][i] = (i == 0) ? 1 : 0x60 + b + i; for (int i = 0; i < 60; ++i) fcGovV[b][i] = (i >= 18 ? 30 + i : 10 * (b + 1) + i) & 255; fcGovV[b][18] = 3; fcGovV[b][39] = 0; }
    RotorFlightStart(); runMs((uint32_t) rr(1500, 2500));          // the menu, as he comes to it from Model setup
}
enum { PG_PID = 0, PG_PIDADV, PG_RATES, PG_RATESADV, PG_GOV, PG_GOVCFG };
static const char *pgName[6] = {"PIDs", "PID +", "Rates", "Dynamics", "Governor", "Governor global"};
static void openPage(int pg) {
    switch (pg) { case PG_PID: StartPIDView(); break; case PG_RATES: StartRFRatesView(); break; case PG_GOV: Start_RF_Governor(); break; case PG_GOVCFG: Start_Gov_Global(); break;
                  case PG_PIDADV: StartPIDView(); runMs(1200); StartPIDAdvancedView(); break; case PG_RATESADV: StartRFRatesView(); runMs(1200); StartRatesAdvancedView(); break; }
}
static void okPage(int pg) {
    switch (pg) { case PG_PID: EndPIDView(); break; case PG_RATES: EndRFRatesView(); break; case PG_GOV: End_RF_Governor(); break; case PG_GOVCFG: End_Gov_Global(); break;
                  case PG_PIDADV: EndPIDsAdvancedView(); break; case PG_RATESADV: EndRatesAdvancedView(); break; }
}
static void edit(int pg) { switch (pg) { case PG_PID: fields["n0"] = std::to_string(atoi(fields["n0"].c_str()) + 7); PIDs_Were_edited(); break; case PG_RATES: Rate_Values[1] = (uint8_t)(Rate_Values[1] + 3); RatesWereEdited(); break;
                                         case PG_GOV: fields["n1"] = std::to_string(atoi(fields["n1"].c_str()) + 3); GOVS_P_Were_Edited(); break; case PG_GOVCFG: fields["n15"] = std::to_string(atoi(fields["n15"].c_str()) + 3); GOVS_G_Were_Edited(); break;
                                         case PG_PIDADV: fields["t2"] = std::to_string(atoi(fields["t2"].c_str()) + 3); PIDsAdvancedWereEdited(); break; case PG_RATESADV: fields["n1"] = std::to_string(atoi(fields["n1"].c_str()) + 3); RatesAdvancedWereEdited(); break; } }
static void savePage(int pg) { switch (pg) { case PG_PID: SendEditedPIDs(); break; case PG_RATES: SendEditedRates(); break; case PG_GOV: Save_RF_Governor(); break; case PG_GOVCFG: Save_Gov_Global(); break;
                                             case PG_PIDADV: SendEditedPID_Advanced(); break; case PG_RATESADV: SendEditedRatesAdvanced(); break; } }
struct Stat { std::vector<long> v; int never = 0; void add(long x) { if (x < 0) ++never; else v.push_back(x); }
    std::string str(long most) { std::sort(v.begin(), v.end()); char b[200]; const int n = (int) v.size() + never; if (v.empty()) { snprintf(b, sizeof b, "held to the end (%ld s) in %d of %d", most / 1000, never, n); return b; }
        snprintf(b, sizeof b, "freed after: least %6.2f s, median %6.2f s, most %6.2f s; STILL HELD after %ld s in %d of %d", v.front() / 1000.0, v[v.size() / 2] / 1000.0, v.back() / 1000.0, most / 1000, never, n); return b; } };
static int checks = 0, fails = 0;
// (suite) e99: what the flight controller holds in banks 1 and 2, taken before a save: which bank did the edit land in? (reviewer B's, review 20)
struct FcSnap { int pid[2][17], rates[2][13], adv[2][15], pidadv[2][26], gov[2][60]; };
static void fcTake(FcSnap &s) { for (int b = 0; b < 2; ++b) { memcpy(s.pid[b], fcPidV[b], sizeof s.pid[b]); memcpy(s.rates[b], fcRatesV[b], sizeof s.rates[b]); memcpy(s.adv[b], fcAdvV[b], sizeof s.adv[b]);
                                                               memcpy(s.pidadv[b], fcPidAdvV[b], sizeof s.pidadv[b]); memcpy(s.gov[b], fcGovV[b], sizeof s.gov[b]); } }
static int fcChanged(const FcSnap &s) { int m = 0; for (int b = 0; b < 2; ++b) { bool ch = memcmp(s.pid[b], fcPidV[b], sizeof s.pid[b]) || memcmp(s.rates[b], fcRatesV[b], sizeof s.rates[b]) || memcmp(s.adv[b], fcAdvV[b], sizeof s.adv[b])
                                                                                          || memcmp(s.pidadv[b], fcPidAdvV[b], sizeof s.pidadv[b]) || memcmp(s.gov[b], fcGovV[b], 18 * sizeof(int)); if (ch) m |= 1 << b; } return m; }
// main.cpp HelpWordCame on a word page (RfPageJobRuns is false there: their reads and saves are not held), and the return from Help ("GOTO"): the
// page sent back, its view again, and a read that Help took asked afresh
static bool RfPageJobRuns() { return false; } static bool RfPageWatchRuns() { return false; }   // (suite, e99e test work: no page job or erase watch in these scenes)
static bool blankRefused() { return BLANK_GATE_COND; }   // (Utilities.h HideScreenAgain's own condition, lifted)
static void helpTap() { HelpTookRead = Reading_PIDS_Now || Reading_RATES_Now || Reading_RATES_Advanced_Now || Reading_PIDS_Advanced_Now || Reading_GOV_Now || Reading_GOV_Config_Now; if (RfSaveHoldsBank()) HelpTookRead = true; /* (suite) e101b: main.cpp */ helpFrom = CurrentView; CurrentView = HELP_VIEW; SendCommand((char *)"page HelpView"); }
static void helpBack() { SendCommand((char *)"page back"); CurrentView = helpFrom; if (HelpTookRead) { HelpTookRead = false; if (CurrentView == PIDVIEW) ShowPIDBank(); else if (CurrentView == RATESVIEW_RF) ShowRatesBank(); else if (CurrentView == PIDADVANCEDVIEW) ShowPIDAdvancedBank();
                        else if (CurrentView == RATESADVANCEDVIEW) ShowRatesAdvancedBank(); else if (CurrentView == RFGOVERNORVIEW_PROFILE) ShowGOVBank(); else if (CurrentView == RFGOVERNORVIEW_GLOBAL) ShowGOV_Global_Bank(); } }
// (suite, e101c test work: review 23 A-3) PART QD's HELP TAP AND WAY BACK ARE THE TREE'S OWN: main.cpp HelpWordCame WHOLE, and the way back's
// "if (HelpTookRead ...) { ... }" WHOLE, lifted at test time (comments out first). The rest of the return ("page back", the view again) is the hand copy's.
HELP_LIFTED_CODE
static void reopen(int pg) {   // the same page from the menu again, at once (PID + and Dynamics through their partner's button 0.2-0.6 s on)
    switch (pg) { case PG_PID: StartPIDView(); break; case PG_RATES: StartRFRatesView(); break; case PG_GOV: Start_RF_Governor(); break; case PG_GOVCFG: Start_Gov_Global(); break;
                  case PG_PIDADV: StartPIDView(); runMs((uint32_t) rr(200, 600)); StartPIDAdvancedView(); break; case PG_RATESADV: StartRFRatesView(); runMs((uint32_t) rr(200, 600)); StartRatesAdvancedView(); break; } }
static bool KNOWN_LOSS = false;   // (suite) e99: acknowledgements lost - the "whose block" rows are KNOWN rows (B212), printed, not asserted
// (suite) e99work, 17 Nov 2026: what e99 does NOT close - asserted (the test fails, rightly); printed as OPEN instead in the break-it rounds' copy (E99_OPEN, below)
#define MUSTO(open, c, ...) do { if ((open) && E99_OPEN_KNOWN) { if (!(c)) { printf("   OPEN (e99 does not close it - the e99 test work, 17 Nov 2026): "); printf(__VA_ARGS__); printf("\n"); } } else MUST(c, __VA_ARGS__); } while (0)
#define MUSTW(c, ...) do { if (KNOWN_LOSS) { if (!(c)) { printf("   KNOWN (acknowledgements lost, B212: 'whole twice by radio' leaks when the give-away item is lost): "); printf(__VA_ARGS__); printf("\n"); } } else MUST(c, __VA_ARGS__); } while (0)
static int globalFlagsIn() { int c = 0; for (int i = 0; i < 24; ++i) c += Global_Params_Received_Flags[i] != 0; return c; }
// (suite) what a row must show. MUST(what is true, the row's name): counted, and said when it fails. Asserted for this tree only (ASSERT_ON).
#define MUST(c, ...) do { if (ASSERT_ON) { ++checks; if (!(c)) { ++fails; printf("   FAIL: "); printf(__VA_ARGS__); printf("  [%s]\n", #c); } } } while (0)
static long mostOf(std::vector<long> v) { long m = -1; for (long x : v) if (x > m) m = x; return m; }
int main(int argc, char **argv) {   // (suite) the parts, the trials a row, the radio's telling (0: none), the pipe's (0: none) - else as the script was called
    const int N = argc > 2 ? atoi(argv[2]) : NTRIALS; rnd_ = SEEDVAL; HK_US = HKVAL;
    if (argc > 3 && !strcmp(argv[3], "0")) radioOn = false;
    if (argc > 4 && !strcmp(argv[4], "0")) pipeTells = false;
    if (argc > 5) LOSS_PCT = atoi(argv[5]); KNOWN_LOSS = LOSS_PCT > 0;   // (suite) e99: reviewer A's switches
    if (argc > 6 && !strcmp(argv[6], "1")) SEND31 = true;
    if (argc > 7 && atoi(argv[7]) > 0) FHSS_data::PaceMaker = (uint8_t) atoi(argv[7]);   // the packet pace: 2 solo, 4 / 5 with a buddy
    if (argc > 8 && atoi(argv[8]) > 0) rnd_ = (uint32_t) atoi(argv[8]);
    if (LOSS_PCT || SEND31 || FHSS_data::PaceMaker != PACEMAKER) printf("(an acknowledgement lost in %d of 100; item 31 %s; a packet every %d ms)\n", LOSS_PCT, SEND31 ? "handed to the parser" : "not sent", (int) FHSS_data::PaceMaker);
    printf("(the block's items come %s)\n", radioOn && pipeTells ? "BY RADIO AND BY THE BLUETOOTH PIPE" : radioOn ? "BY RADIO ONLY (the screen tells nothing)" : pipeTells ? "BY THE BLUETOOTH PIPE ONLY (as reviewer B ran it)" : "BY NOTHING");
    #define MOST(st) mostOf((st).v)
    printf("%s   (%d trials a row, seed %u; the once-a-second round takes %d us, a loop pass %d-%d us, a packet %d-%d us every %d ms)\n", TREE_NAME, N, (unsigned) rnd_, HK_US, PASS_LO, PASS_HI, RADIO_LO, RADIO_HI, (int) FHSS_data::PaceMaker);
    const std::string part = argc > 1 ? argv[1] : PARTS;
    auto want = [&](const char *p) { return part == "all" || part.find(p) != std::string::npos; };
    // ---------------------------------------------------------------- a. a page opened, OK before its set has come; the menu stays up (a model connected, the pipe joined)
    if (want("a")) {
        printf("a. A WORD PAGE OPENED, OK %s - the menu stays up for 60 s, the model connected: how long is the bank switch held from the menu's coming?\n", "100 to 250 ms later (before its set has come)");
        for (int pg = 0; pg < 6; ++pg) { Stat st; int cameFirst = 0;
            for (int k = 0; k < N; ++k) { fresh(); openPage(pg); runMs((uint32_t) rr(100, 250)); const bool had = !BlockBankChanges; cameFirst += had; okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) { printf("   (%s: OK did not bring the menu: view %d)\n", pgName[pg], CurrentView); continue; }
                st.add(untilFree(60000)); }
            printf("   %-16s %s%s\n", pgName[pg], st.str(60000).c_str(), cameFirst ? "  (the set had come first in some)" : "");
            MUST((int) st.v.size() + st.never > N / 2, "a. (suite) %s: the row ran (%d of %d trials reached the menu)", pgName[pg], (int) st.v.size() + st.never, N);   // e99: a row with no trial fails
            MUST(st.never == 0 && MOST(st) <= 1000, "a. %s left before its set: the bank switch is free when its set has come (never held; within 1.0 s - e99: 0.7 s the most measured)", pgName[pg]); }
    }
    // ---------------------------------------------------------------- b. the flight controller silent (its read never ends): OK 0.5 to 2 s after the page opened
    if (want("b")) {
        printf("b. THE SAME WITH A FLIGHT CONTROLLER THAT DOES NOT ANSWER, OK 0.5 to 2.0 s after the page opened (he sees 'Loading ...' stand, and leaves)\n");
        for (int pg = 0; pg < 6; ++pg) { Stat st; int heldAtOk = 0, nb = 0;
            for (int k = 0; k < N; ++k) { fresh(); if (pg == PG_PIDADV || pg == PG_RATESADV) { openPage(pg); fcDead = true; rxSend = K_NONE; if (pg == PG_PIDADV) ShowPIDAdvancedBank(); else ShowRatesAdvancedBank(); } else { fcDead = true; openPage(pg); }
                runMs((uint32_t) rr(500, 2000)); ++nb;
                const bool wholeNow = pg == PG_PID ? PIDS_Loaded : pg == PG_PIDADV ? PIDS_ADV_Loaded : pg == PG_RATES ? RATES_Loaded : pg == PG_RATESADV ? RATES_ADV_Loaded : pg == PG_GOV ? GOV_Loaded : AllGlobalConfigBytesReceived();
                heldAtOk += BlockBankChanges || wholeNow;   // (PID + and Dynamics were read a moment ago: a line of that read may still come - the page's own block, and whole)
                okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) continue; st.add(untilFree(60000)); }
            MUST(nb > N / 2 && (int) st.v.size() + st.never > N / 2, "b. (suite) %s: the row ran (%d opened, %d reached the menu, of %d)", pgName[pg], nb, (int) st.v.size() + st.never, N);   // e99
            MUST(heldAtOk == nb, "b. (suite) %s, its read open: the bank switch IS held until the page's set has come whole (%d of %d) - what the block is for", pgName[pg], heldAtOk, nb);
            printf("   %-16s %s\n", pgName[pg], st.str(60000).c_str());
            MUST(st.never == 0 && MOST(st) <= (pg == PG_GOVCFG ? 4200 : 2700), "b. %s, the flight controller silent: the bank switch is free at the read's own window", pgName[pg]); }
    }
    // ---------------------------------------------------------------- c. Save, and OK while "Sent: reading back ..." stands
    if (want("c")) {
        printf("c. AN EDIT, SAVE, AND OK SOON AFTER (0.15 to 0.7 s behind the Save button: 'Sent: reading back ...' stands in most) - the menu stays up 60 s\n");
        for (int pg = 0; pg < 6; ++pg) { Stat st, stCheck; int wrote = 0, nosave = 0, q = 0, pending = 0, said = 0, early = 0, beyond = 0; long beyondMost = -100000;
            for (int k = 0; k < N; ++k) { fresh(); openPage(pg); runMs(3200); edit(pg); const bool b0 = BlockBankChanges; savePage(pg); const bool b1 = BlockBankChanges; const int st1 = BcStep; runMs((uint32_t) rr(150, 700)); saveNowAnswer = false; const int q0 = questions;
                if (SHOWIT) printf("      [%s] before Save: block %d; behind Save: block %d, check step %d, boxes %d '%s'; at OK: block %d, check step %d, read-back pending %d, flag %d, writes %d, edited %d, line '%s'\n", pgName[pg], (int) b0, (int) b1, st1, boxes, lastBox.substr(0, 50).c_str(), (int) BlockBankChanges, BcStep, (int) RfVerifyPending(), (int)(Reading_PIDS_Now || Reading_RATES_Now || Reading_RATES_Advanced_Now || Reading_PIDS_Advanced_Now || Reading_GOV_Now || Reading_GOV_Config_Now), writesDone, (int)(PIDS_Were_Edited || Rates_Were_Edited || PIDS_Advanced_Were_Edited || Rates_Advanced_Were_Edited || GOVS_PROFILE_Were_Edited || GOVS_GLOBAL_Were_Edited), fields[pg == PG_GOVCFG ? "t4" : "busy"].c_str());
                const bool pend = RfVerifyPending() || BcStep; if (!pend) continue;   // (the verdict had come: not this row's road)
                const bool checkOut = BcStep != 0;   // (suite) the check of the bank is out at OK: "Save now?", Discard - and the save goes on from the menu (KNOWN, B212)
                ++pending; const uint32_t winEnd = VfReadStart + (pg == PG_GOVCFG ? RF_VERIFY_GOVCFG_WAIT_MS : RF_VERIFY_WAIT_MS); okPage(pg); q += questions - q0;
                if (CurrentView != ROTORFLIGHTVIEW) { ++nosave; continue; } const long t = untilFree(60000); (checkOut ? stCheck : st).add(t); wrote += writesDone > 0; said += boxes + quietSaid;
                if (!checkOut) { const uint64_t freeUs = us_; runMs(1500); if (t >= 0 && (!landAtUs || freeUs < landAtUs)) ++early;   // (suite) e99: free before the write had landed?
                                 const long over = t < 0 ? 999999 : (long)(int32_t)((uint32_t)(freeUs / 1000ull) - winEnd); if (over > beyondMost) beyondMost = over; if (over > 100) ++beyond; } }
            printf("   %-16s OK came inside the save in %3d of %3d: %s   (the write reached the flight controller in %d; 'Save now?' asked %d times; the page stayed %d; boxes or log lines %d)\n", pgName[pg], pending, N, st.str(60000).c_str(), wrote, q, nosave, said);
            if (stCheck.v.size() + stCheck.never) printf("   %-16s KNOWN (the released firmware's, B212): the check of the bank was out at OK, 'Save now?' answered Discard, the save went on from the menu - %s\n", "", stCheck.str(60000).c_str());
            MUST(st.never == 0 && MOST(st) <= 5000, "c. %s: Save, OK inside its read-back - the bank switch is free when the read-back's set has come", pgName[pg]);
            // (suite) e99 (reviewer 20-B's A4: the set that freed it was the OLD block): the trials of the row; the bank switch free by the read-back's OWN window
            // (its ask + its window, the 50 ms round's step); and - on the four pages whose block is a bank's - NEVER before the write has landed
            printf("   %-16s (e99) freed before the write had landed in %d; freed at the latest %ld ms %s the read-back's window ended\n", "", early, beyondMost < 0 ? -beyondMost : beyondMost, beyondMost < 0 ? "before" : "after");
            MUST((int) st.v.size() + st.never > N / 4, "c. (suite) %s: the row ran (%d trials with OK inside the read-back, of %d)", pgName[pg], (int) st.v.size() + st.never, N);
            MUST(beyond == 0, "c. (suite) e99: %s: Save, OK inside its read-back - the bank switch free by the read-back's own window (%d beyond it, the latest %ld ms after it)", pgName[pg], beyond, beyondMost);
            if (pg == PG_RATES) { if (early) printf("   KNOWN (the released firmware's, B212 B19-B1: the Rates page's OK frees the bank switch under its own save): freed before the write had landed in %d\n", early); }
            else if (pg != PG_GOVCFG) MUST(early == 0, "c. (suite) e99: %s: Save, OK inside its read-back - the bank switch NOT free before the write has landed (%d of %d)", pgName[pg], early, (int) st.v.size() + st.never); }
    }
    // ---------------------------------------------------------------- d. ... and then the front page: how long is the bank switch dead THERE, and what does the bank do
    if (want("d")) {
        printf("d. THE BANK ITSELF. The 'Bank 4 & Motor' switch at ON (the safety on: the bank is the 'Banks 1 2 3' switch's), bank 1. PIDs opened, OK before its set (the menu);\n   3 s on, the 'Banks 1 2 3' switch to 2; 20 s on the menu; then OK on the menu (the front page)\n");
        motorPos0 = 1;
        Stat st, stAll; int heldOnMenu = 0, bank1OnMenu = 0, jumped = 0, n = 0, menuSaysBank1 = 0; long jumpLeast = 1 << 30, jumpMost = 0;
        for (int k = 0; k < N; ++k) { fresh(); if (Bank != 1) { printf("   (the bank is %d at the start)\n", Bank); continue; } openPage(PG_PID); runMs((uint32_t) rr(100, 250)); okPage(PG_PID); if (CurrentView != ROTORFLIGHTVIEW) continue;
            ++n; runMs(3000); pos[4] = 2; runMs(20000); const bool held = BlockBankChanges; heldOnMenu += held; bank1OnMenu += Bank == 1; menuSaysBank1 += fields["t14"] == "Bank 1";
            RotorFlightEnd(); const uint64_t t0 = us_; const long t = untilFree(30000); stAll.add(t); if (!held) continue; st.add(t);
            runMs(120); if (Bank == 2) { ++jumped; const long j = (long)((us_ - t0) / 1000ull); if (j < jumpLeast) jumpLeast = j; if (j > jumpMost) jumpMost = j; } }
        printf("   after 20 s on the menu with the switch at 2: the bank switch still held in %d of %d - the transmitter still on bank 1 in %d, the menu's own line still 'Bank 1' in %d\n", heldOnMenu, n, bank1OnMenu, menuSaysBank1);
        MUST(n > N / 2 && heldOnMenu == 0 && bank1OnMenu == 0 && menuSaysBank1 == 0, "d. PIDs left before its set, the bank switch moved on the menu: the bank follows, the menu's line says so (held %d, still bank 1 %d, the line %d, of %d)", heldOnMenu, bank1OnMenu, menuSaysBank1, n);
        if (heldOnMenu) printf("   those, on the FRONT PAGE: %s\n", st.str(30000).c_str());
        if (jumped) printf("   ... and the bank then went to 2 BY ITSELF, %0.2f to %0.2f s after the front page came, in %d of %d\n", jumpLeast / 1000.0, jumpMost / 1000.0, jumped, heldOnMenu);
        // the page left for the front page at once (OK, OK): the block on the front page
        Stat s2; int n2 = 0;
        for (int k = 0; k < N; ++k) { fresh(); openPage(PG_PID); runMs((uint32_t) rr(100, 250)); okPage(PG_PID); if (CurrentView != ROTORFLIGHTVIEW) continue; runMs((uint32_t) rr(600, 1500)); RotorFlightEnd(); ++n2; s2.add(untilFree(30000)); }
        printf("   PIDs, OK before its set, OK on the menu 0.6 to 1.5 s later: on the FRONT PAGE %s\n", s2.str(30000).c_str());
        MUST(n2 > N / 2 && s2.never == 0 && MOST(s2) <= 300, "d. PIDs left before its set, then the front page: the bank switch is not dead there");
        // ... and the everyday one: an edit, Save, OK while 'Sent: reading back ...' stands, OK on the menu 0.6 to 3 s later
        for (int pg : {PG_PID, PG_GOV}) { Stat s3; int n3 = 0;
            for (int k = 0; k < N; ++k) { fresh(); openPage(pg); runMs(3200); edit(pg); savePage(pg); runMs((uint32_t) rr(150, 700)); if (!RfVerifyPending()) continue; okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) continue;
                runMs((uint32_t) rr(600, 3000)); RotorFlightEnd(); ++n3; s3.add(untilFree(30000)); }
            printf("   %s: an edit, Save, OK inside its read-back (%d of %d), OK on the menu 0.6 to 3 s later: on the FRONT PAGE %s\n", pgName[pg], n3, N, s3.str(30000).c_str()); MUST(n3 > N / 2 && s3.never == 0 && MOST(s3) <= 300, "d. %s: Save, OK inside its read-back, OK on the menu: the bank switch is not dead on the front page", pgName[pg]); }
        motorPos0 = 3;
    }
    // ---------------------------------------------------------------- e. the control: the page left AFTER its set came, or its window ended - never held
    if (want("e")) {
        printf("e. THE CONTROL: OK 3.5 s after the page opened (its set come, or its window ended); and a save whose read-back ended on the page\n");
        for (int pg = 0; pg < 6; ++pg) { Stat st, st2;
            for (int k = 0; k < N; ++k) { fresh(); openPage(pg); runMs(3500); okPage(pg); if (CurrentView == ROTORFLIGHTVIEW) st.add(untilFree(60000));
                                          fresh(); openPage(pg); runMs(3200); edit(pg); savePage(pg); runMs(pg == PG_GOVCFG ? 9000 : 4500); saveNowAnswer = false; okPage(pg); if (CurrentView == ROTORFLIGHTVIEW) st2.add(untilFree(60000)); }
            printf("   %-16s read: %s\n   %-16s save: %s\n", pgName[pg], st.str(60000).c_str(), "", st2.str(60000).c_str());
            MUST((int) st.v.size() + st.never > N / 2 && (int) st2.v.size() + st2.never > N / 2, "e. (suite) %s: the rows ran (%d and %d of %d)", pgName[pg], (int) st.v.size() + st.never, (int) st2.v.size() + st2.never, N);   // e99
            MUST(st.never == 0 && MOST(st) <= 300 && st2.never == 0 && MOST(st2) <= 300, "e. %s left after its read, and after a save confirmed: never held", pgName[pg]); }
    }
    // ---------------------------------------------------------------- h. WHAT THE BLOCK IS FOR, ON EVERY PAGE THAT SAVES TO A BANK (suite, e99: the twentieth review's finding 1 / A1, and B1 / B-3)
    if (want("h")) {
        printf("h. WHAT THE BLOCK IS FOR. Bank 1 (the motor switch at ON, the safety on). Every page that saves to a bank: an edit, Save, and 0.1 to 0.6 s later OK (Discard if asked)\n"
               "   - or Help; or OK and the same page again 0.1-0.5 s on; or OK and another page 0.15-0.5 s on; or Help and back 0.1-0.6 s on. The 'Banks 1 2 3' switch to 2 [r] 0.05 to 0.6 s after\n"
               "   OK (or Help), [f] the moment it is free (from Save on). The receiver's write lands [0] at once, [1] 30-120 ms, [2] 80-250 ms after its trigger word.\n"
               "   Each cell: INTO THE OTHER BANK / FREED BEFORE THE WRITE HAD LANDED / trials with the read-back out at OK (the check of the bank out: KNOWN, below)\n");
        motorPos0 = 1; const uint32_t boxWas = BOX_MS; BOX_MS = 400;
        static const int lands[3][2] = {{0, 0}, {30, 120}, {80, 250}};
        static const int pagesH[5] = {PG_PID, PG_PIDADV, PG_GOV, PG_RATESADV, PG_RATES};
        static const char *exitName[5] = {"OK (the menu)", "Help", "OK, the same page again", "OK, another page", "Help, and back"};
        static const int pagesB[4] = {PG_PID, PG_RATES, PG_GOV, PG_GOVCFG};
        long k8N = 0, k8Wrong = 0;   // (e99d: G8, B212 5a) Dynamics, OK, the same page again
        long ckN = 0, ckWrong = 0, ckNever = 0, k5aN = 0, k5aWrong = 0, k5aEarly = 0, stale = 0, bRefused = 0, bN = 0;
        for (int pi = 0; pi < 5; ++pi) { const int pg = pagesH[pi]; const bool known = pg == PG_RATES;
            for (int ex = 0; ex < 5; ++ex) {
                std::string row; char cell[64];
                for (int li = 0; li < 3; ++li) for (int atFree = 0; atFree < 2; ++atFree) {
                    landLo = lands[li][0]; landHi = lands[li][1];
                    int n = 0, wrong = 0, early = 0, nowhere = 0, nCk = 0, wrongCk = 0, noFlip = 0, noFlipCk = 0;
                    for (int k = 0; k < N; ++k) {
                        LinkRatesToBanks = pg == PG_RATESADV || pg == PG_RATES; fresh(); if (Bank != 1) continue;
                        openPage(pg); runMs(3200); FcSnap snap; fcTake(snap); edit(pg); savePage(pg);
                        uint64_t freedAt = 0, flipAt = 0; bool flipped = false; int pgB = -1;
                        auto step = [&]() { if (!freedAt && !BlockBankChanges) freedAt = us_; if (!flipped && ((atFree && !BlockBankChanges) || (!atFree && flipAt && us_ >= flipAt))) { pos[4] = 2; flipped = true; } loopPass(); };
                        auto run = [&](uint32_t ms) { const uint64_t e = us_ + (uint64_t) ms * 1000ull; while (us_ < e) step(); };
                        run((uint32_t) rr(100, 600));
                        if (!(RfVerifyPending() || BcStep)) { if (flipped) pos[4] = 1; continue; }   // (the save was over: not this road)
                        const bool checkOut = BcStep != 0; saveNowAnswer = false;
                        if (ex == 1 || ex == 4) helpTap(); else { okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) continue; }
                        if (!atFree) flipAt = us_ + (uint64_t) rr(50, 600) * 1000ull;
                        if (ex == 2) { run((uint32_t) rr(100, 500)); reopen(pg); }
                        else if (ex == 3) { run((uint32_t) rr(150, 500)); int b = pg; while (b == pg) b = pagesB[rr(0, 3)]; pgB = b; openPage(b); }
                        else if (ex == 4) { run((uint32_t) rr(100, 600)); helpBack(); }
                        { const uint64_t e = us_ + 8000000ull; while (!flipped && us_ < e) step(); }
                        if (!flipped) { if (checkOut) ++noFlipCk; else ++noFlip; pos[4] = 2; flipped = true; }
                        run(6000);
                        stale += RfVerifyPending();   // (e99: a read-back left behind never stays for good)
                        if (pgB >= 0 && CurrentView != ROTORFLIGHTVIEW) { boxes = 0; bool ok = true;   // (e99: page B behind the save works - its own numbers, its edit taken)
                            if (pgB == PG_PID) PIDs_Were_edited(); else if (pgB == PG_RATES) RatesWereEdited(); else if (pgB == PG_GOV) GOVS_P_Were_Edited(); else ok = AllGlobalConfigBytesReceived();
                            bRefused += boxes != 0 || !ok; ++bN; PIDS_Were_Edited = Rates_Were_Edited = GOVS_PROFILE_Were_Edited = false; }
                        const int m = fcChanged(snap); const bool w = (m & 2) != 0, e = freedAt && landAtUs && freedAt < landAtUs;
                        if (checkOut) { ++nCk; wrongCk += w; } else if (pg == PG_RATESADV && pgB == PG_RATES) { ++k5aN; k5aWrong += w; k5aEarly += e; }   // (B212 5a: the Rates' and the Dynamics' blocks have the same four items)
                        else { ++n; wrong += w; early += e; nowhere += m == 0; }
                        if (SHOWIT && (w || e) && !checkOut) printf("      [%s, %s%s, land %d-%d, %s, trial %d] INTO BANK 2 %d: the bank switch freed %ld ms after the write's trigger word reached the receiver (%ld); the write landed %ld ms after it\n", pgName[pg], exitName[ex], pgB >= 0 ? pgName[pgB] : "", landLo, landHi, atFree ? "at free" : "random", k, (int) w,
                                                             freedAt ? (long)((int64_t)(freedAt - trigAtUs) / 1000) : -1, 0L, landAtUs ? (long)((int64_t)(landAtUs - trigAtUs) / 1000) : -1); }
                    snprintf(cell, sizeof cell, " | %d%c %2d/%2d/%3d", li, atFree ? 'f' : 'r', wrong, early, n); row += cell;
                    if (ex == 0 && li == 0 && !atFree && pg != PG_RATES) printf("   %-9s (the check of the bank was out at OK in %d: KNOWN below)\n", pgName[pg], nCk);
                    if (nowhere) printf("   %s%s, %s, land %d-%d, %s: THE EDIT LANDED NOWHERE in %d of %d\n", known ? "KNOWN " : "", pgName[pg], exitName[ex], landLo, landHi, atFree ? "at free" : "random", nowhere, n);
                    if (noFlip) printf("   %s%s, %s, land %d-%d: THE BANK SWITCH NEVER FREE IN 8 s in %d of %d (moved then all the same)\n", known ? "KNOWN " : "", pgName[pg], exitName[ex], landLo, landHi, noFlip, n);
                    ckNever += noFlipCk;
                    ckN += nCk; ckWrong += wrongCk;
                    if (known && ex != 1) continue;   // (the Rates page: its OK frees the switch - B19-B1, KNOWN. But Help over it does not go through OK: e99 follows that save - asserted)
                    MUST(n > (ex == 3 && pg == PG_RATESADV ? N / 3 : N / 2), "h. (suite) %s, %s, the write landing %d-%d ms late, the switch moved %s: the row ran (%d of %d with the read-back out at OK)", pgName[pg], exitName[ex], landLo, landHi, atFree ? "the moment it is free" : "0.05-0.6 s on", n, N);
                    if (pg == PG_RATESADV && ex == 2) {   // (suite, e99d: G8) B212 5a - the Rates' and the Dynamics' blocks share four items: KNOWN, printed with its count, NOT asserted
                        k8N += n; k8Wrong += wrong;
                        if (wrong) printf("   KNOWN (B212 5a: the Rates' and the Dynamics' blocks share four items): h. Dynamics, OK, the same page again, landing %d-%d ms, switch %s: INTO THE OTHER BANK %d of %d\n", landLo, landHi, atFree ? "at free" : "0.05-0.6 s on", wrong, n);
                        MUST(early == 0, "h. WHAT THE BLOCK IS FOR: %s, %s, landing %d-%d ms, switch %s: FREE BEFORE THE WRITE HAD LANDED %d, of %d - never", pgName[pg], exitName[ex], landLo, landHi, atFree ? "at free" : "0.05-0.6 s on", early, n);
                    } else
                    MUSTO(ex == 2 || ex == 4, wrong == 0 && early == 0, "h. WHAT THE BLOCK IS FOR: %s, %s, landing %d-%d ms, switch %s: INTO THE OTHER BANK %d, FREE BEFORE THE WRITE HAD LANDED %d, of %d - never, either", pgName[pg], exitName[ex], landLo, landHi, atFree ? "at free" : "0.05-0.6 s on", wrong, early, n);
                    if (pg == PG_PID && ex == 0 && li == 0 && !atFree) MUST(wrongCk == 0, "h. WHAT THE BLOCK IS FOR: a PIDs save on its way, the bank switch moved on the menu - the edit never goes into the other bank, the check of the bank out at OK too (as before e99: %d of %d)", wrongCk, nCk);
                }
                printf("   %s%-9s %-24s%s\n", known && ex != 1 ? "KNOWN (the released firmware's, B212 B19-B1: the Rates page's OK frees the switch under its save) " : "", pgName[pg], exitName[ex], row.c_str()); } }
        printf("   KNOWN (the released firmware's, B212 B19-B4): the check of the bank still out at OK ('Save now?' answered Discard - the save goes on from the menu): INTO THE OTHER BANK in %ld of %ld; the bank switch never free in 8 s in %ld\n", ckWrong, ckN, ckNever);
        printf("   (e99) a read-back still pending 6 s after the bank switch moved: %ld trials; page B behind the save refused its edit (or the Governor global not whole) in %ld of %ld\n", stale, bRefused, bN);
        MUST(stale == 0, "h. e99: a read-back left behind never stays for good (still pending 6 s on in %ld trials)", stale);
        MUST(bN > 0 && bRefused == 0, "h. e99: the page opened behind a save works - its edit taken, its set whole (refused %ld of %ld)", bRefused, bN);
        printf("   KNOWN (B212 5a: the Rates' and the Dynamics' blocks have the same four items): Dynamics saved, OK, the RATES page opened behind it: INTO THE OTHER BANK in %ld, free before the write had landed in %ld, of %ld\n", k5aWrong, k5aEarly, k5aN);
        printf("   KNOWN (B212 5a, e99d G8): Dynamics saved, OK, THE SAME PAGE AGAIN: INTO THE OTHER BANK in %ld of %ld\n", k8Wrong, k8N);
        LinkRatesToBanks = false; landLo = landHi = 0; motorPos0 = 3; BOX_MS = boxWas;
    }
    // ---------------------------------------------------------------- w. (suite, e99) HOW LONG IS THE BANK SWITCH HELD BEHIND A SAVE WHOSE PAGE WAS LEFT
    if (want("w")) {
        printf("w. (e99: a save is followed off its page) HOW LONG IS THE BANK SWITCH HELD. Bank 1; an edit, Save, OK (or Help) 0.1-0.6 s later with the read-back out; nothing moved.\n"
               "   From OK (or Help) to the bank switch free; and against the read-back's own window (its ask + %d ms; Hide_msg_if_needed ends it, every 50 ms on a Rotorflight page)\n", (int) RF_VERIFY_WAIT_MS);
        static const char *condName[4] = {"the write lands at once", "the write lands 80-250 ms late", "THE WRITE NEVER LANDS (old block told)", "THE FLIGHT CONTROLLER SILENT from Save on"};
        static const int pagesW[4] = {PG_PID, PG_PIDADV, PG_GOV, PG_RATESADV};
        static const char *exW[4] = {"OK", "HELP", "AGAIN", "HELP+B"};   // (round 23: [AGAIN] OK and the same page again 0.1-0.5 s on, [HELP+B] Help and back 0.1-0.6 s on - e99b's fresh ask: against the latest window open after it)
        for (int ex = 0; ex < 4; ++ex) for (int c = 0; c < 4; ++c) for (int pi = 0; pi < 4; ++pi) { const int pg = pagesW[pi]; Stat st; int n = 0, beyond = 0, asksMost = 0; long latest = -999999;
            for (int k = 0; k < N; ++k) { LinkRatesToBanks = pg == PG_RATESADV; fresh(); openPage(pg); runMs(3200); edit(pg);
                if (c == 1) { landLo = 80; landHi = 250; } else landLo = landHi = 0; writeLost = c >= 2;
                savePage(pg); if (c == 3) fcDead = true;
                runMs((uint32_t) rr(100, 600)); if (!RfVerifyPending() || BcStep) continue;
                uint32_t winEnd = VfReadStart + RF_VERIFY_WAIT_MS;
                if (ex == 1 || ex == 3) helpTap(); else { okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) continue; }
                const uint64_t tEx = us_; long t = 0;
                if (ex >= 2) { const long t1 = untilFree((uint32_t) rr(100, ex == 2 ? 500 : 600)); if (t1 >= 0) t = t1;   // (freed before the page came back: that is the hold)
                    else { if (ex == 2) reopen(pg); else helpBack(); auto we = [&](bool f, uint32_t s0, uint32_t d) { if (f && s0 + d > winEnd) winEnd = s0 + d; };
                        we(Reading_PIDS_Now, PID_Start_Time, PID_Send_Duration); we(Reading_PIDS_Advanced_Now, PID_Advanced_Start_Time, PID_Advanced_Send_Duration); we(Reading_GOV_Now, GOV_Start_Time, GOV_Send_Duration);
                        we(Reading_RATES_Advanced_Now, RATES_Advanced_Start_Time, Rates_Advanced_Send_Duration);
                        // (round 25, e99e) the windows opened while it is held count too - e99e's ONE more ask (G3) - and the asks are counted: at most one more
                        int moreAsks = 0; uint32_t st0 = 0; bool fl0 = false; { auto cur = [&](bool &f) { f = anyFlag(); return Reading_PIDS_Now ? PID_Start_Time : Reading_PIDS_Advanced_Now ? PID_Advanced_Start_Time : Reading_GOV_Now ? GOV_Start_Time : Reading_RATES_Advanced_Now ? RATES_Advanced_Start_Time : 0u; };
                            st0 = cur(fl0); const uint64_t e = us_ + 12000000ull; long t2 = -1; while (us_ < e) { if (!BlockBankChanges) { t2 = 0; break; } loopPass(); bool f; const uint32_t s1 = cur(f); if (f && (!fl0 || s1 != st0)) { ++moreAsks; st0 = s1; } fl0 = f;
                                we(Reading_PIDS_Now, PID_Start_Time, PID_Send_Duration); we(Reading_PIDS_Advanced_Now, PID_Advanced_Start_Time, PID_Advanced_Send_Duration); we(Reading_GOV_Now, GOV_Start_Time, GOV_Send_Duration); we(Reading_RATES_Advanced_Now, RATES_Advanced_Start_Time, Rates_Advanced_Send_Duration); }
                            t = t2 < 0 ? -1 : (long)((us_ - tEx) / 1000ull); }
                        if (moreAsks > asksMost) asksMost = moreAsks; } }
                else t = untilFree(12000);
                ++n; st.add(t);
                const long over = t < 0 ? 999999 : (long)(int32_t)(millis() - winEnd); if (over > latest) latest = over; if (over > 100) ++beyond; }
            printf("   %-6s %-42s %-9s n %3d | %s | at the latest %ld ms %s the window's end\n", exW[ex], condName[c], pgName[pg], n, st.str(12000).c_str(), latest < 0 ? -latest : latest, latest < 0 ? "before" : "after");
            MUST(n > N / 2, "w. (suite) %s, %s, %s: the row ran (%d of %d)", exW[ex], condName[c], pgName[pg], n, N);
            if (ex >= 2) { printf("          (round 25) asks after the page came back: at the most %d\n", asksMost);
                MUST(st.never == 0 && beyond == 0, "w. e99b: %s, %s, %s: the bank switch held no longer than the latest read window open after the page came back - e99e: or opened while it was held (+0.1 s): beyond %d, never %d, of %d", exW[ex], condName[c], pgName[pg], beyond, st.never, n);
                MUST(asksMost <= 1, "w. e99e (G3): %s, %s, %s: at most ONE more ask after the page came back (the most %d)", exW[ex], condName[c], pgName[pg], asksMost); continue; }
            MUSTO(ex == 1 && c >= 2, st.never == 0 && beyond == 0, "w. e99: %s, %s, %s: held beyond the read-back's own window %d, never freed in 12 s %d (of %d) - the bank switch held NO LONGER than that window", ex ? "Help over the page" : "the page left by OK", condName[c], pgName[pg], beyond, st.never, n);
            if (c <= 1) MUST(st.never == 0 && MOST(st) <= 1000, "w. e99: %s, %s, %s: the bank switch free within 1.0 s once the write has landed (the most: %.2f s)", ex ? "Help" : "OK", condName[c], pgName[pg], MOST(st) / 1000.0); }
        LinkRatesToBanks = false; landLo = landHi = 0; writeLost = false;
        // ... the motor switched on from the menu behind such a save (no safety switch; Motor_sign.h: every read put down, the front page): the front page's hold
        { const uint8_t sw = SafetySwitch; for (int pi = 0; pi < 4; ++pi) { const int pg = pagesW[pi]; Stat st; int n = 0;
            int over1 = 0, beyondW = 0, followedW = 0; for (int k = 0; k < N; ++k) { LinkRatesToBanks = pg == PG_RATESADV; fresh(); SafetySwitch = 0; openPage(pg); runMs(3200); edit(pg); savePage(pg); runMs((uint32_t) rr(100, 600)); if (!RfVerifyPending() || BcStep) continue;
                okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) continue; runMs((uint32_t) rr(50, 600)); pos[1] = 1; runMs(60); if (CurrentView != FRONTVIEW || !mcall.seen) continue; ++n; const long t = untilFree(12000); st.add(t); over1 += t < 0 || t > 1000;
                const uint64_t freeAt = t < 0 ? ~0ull : (t == 0 && !mcall.blockAfter) ? mcall.at : us_;   // (free from the call itself: untilFree begins 60 ms after the switch moved)   // (suite, e99c work: asserted) the bound: the read-back's own window when one was followed, else at once
                const uint64_t bound = mcall.winEnd ? (uint64_t)(mcall.winEnd + 100) * 1000ull : mcall.at + (uint64_t) NET_BOUND_MS * 1000ull;   // (the read-back's window when one was followed; e99d: else the released road - the five-second net)
                if (SHOWIT && freeAt > bound) printf("      [w motor %s trial %d] BEYOND: freed %ld ms after the call; at the call: read-back pending %d (kind %d), check step %d, held after %d, flags after %d, radio queue %d (no bank's words %d, a transfer %d), the latest window %ld ms after the call\n", pgName[pg], k, t < 0 ? -1L : (long)((int64_t)(freeAt - mcall.at) / 1000), (int) mcall.pend, mcall.kind, mcall.bc, (int) mcall.blockAfter, (int) mcall.flagsAfter, (int) mcall.radioQ, (int) mcall.keepAlive, (int) mcall.transfer, mcall.winEnd ? (long)((int64_t)mcall.winEnd - (int64_t)(mcall.at / 1000)) : 0L);
                beyondW += freeAt > bound && !(E23_OPEN_KNOWN && mcall.keepAlive && !mcall.winEnd); followedW += mcall.pend; }
            printf("   (e99c) MOTOR ON from the menu 0.05-0.6 s after OK (no safety switch: the front page) %-9s n %3d | held there over 1 s in %3d | %s | the read-back followed onto the front page in %d; beyond its bound in %d\n", pgName[pg], n, over1, st.str(12000).c_str(), followedW, beyondW);
            MUST(n > N / 3 && beyondW == 0 && st.never == 0, "w. e99c/e99d: the motor switched on from the menu behind 'Save, OK' (%s): the bank switch free by the read-back's own window (+0.1 s) when it is followed, by the five-second net when none is (released) - beyond %d, never %d, of %d", pgName[pg], beyondW, st.never, n); }
          SafetySwitch = sw; LinkRatesToBanks = false; }
        // ... the Governor global page is NOT followed off its page (nothing of it is a bank's; its window 8 s): Save, OK inside its read-back, Discard - the menu.
        // [0] its write lands (and restarts the flight controller: 4 x 0.9 s told nothing), [1] its write never lands (the old block told): as the unchanged tree
        for (int c = 0; c < 2; ++c) { Stat st; int n = 0; const int wr = wrMs; wrMs = c ? 250 : 900; const uint32_t boxWas = BOX_MS; BOX_MS = 400;
          for (int k = 0; k < N; ++k) { fresh(); openPage(PG_GOVCFG); runMs(3200); edit(PG_GOVCFG); writeLost = c == 1; savePage(PG_GOVCFG); runMs((uint32_t) rr(300, 900)); if (!RfVerifyPending()) continue; saveNowAnswer = false; okPage(PG_GOVCFG);
              if (CurrentView != ROTORFLIGHTVIEW) continue; ++n; st.add(untilFree(12000)); }
          const long most = c ? GOVCFG_MENU_MOST1 : GOVCFG_MENU_MOST0;
          printf("   Governor global (not followed off its page), %s: Save, OK inside its read-back, Discard - from the menu: n %3d | %s\n", c ? "ITS WRITE NEVER LANDS" : "its write lands", n, st.str(12000).c_str());
          MUST(n > N / 2 && st.never == 0 && MOST(st) <= most, "w. e99: the Governor global page is not followed off its page (%s) - the bank switch free on the menu as in the unchanged tree (within %.2f s; the most %.2f s, never %d, of %d)", c ? "its write never lands" : "its write lands", most / 1000.0, MOST(st) / 1000.0, st.never, n);
          wrMs = wr; BOX_MS = boxWas; writeLost = false; }
    }
    // ---------------------------------------------------------------- l. (suite, e99) THE GOVERNOR GLOBAL PAGE'S OWN LINE ON AN ORDINARY VISIT (the twentieth review's finding 2 / A2)
    if (want("l")) {
        printf("l. (e99) GOVERNOR GLOBAL OPENED FROM THE MENU, nothing moved, 10 s: WHAT DOES ITS LINE SAY? 'only PART came back' NEVER on a read whose 24 bytes came; when they did not,\n   the box 'Failed to read global' and a line (its own t4, or the Governor page's that the box opens); 'nothing came back' when none came\n");
        static const char *condName[3] = {"the flight controller answers", "the flight controller SILENT", "ONLY 1 to 4 OF ITS ITEMS COME (the telling cut)"};
        for (int c = 0; c < 3; ++c) { if (c == 2 && !radioOn) continue; int n = 0, whole = 0, partWhole = 0, nothingWhole = 0, partOk = 0, nothingOk = 0, someIn = 0, noneIn = 0, otherLine = 0, boxW = 0, saidLine = 0;
            for (int k = 0; k < N; ++k) { fresh(); boxes = 0; if (c == 1) fcDead = true; const bool pt = pipeTells; if (c == 2) { pipeTells = false; radioBudget = rr(1, 4); }
                openPage(PG_GOVCFG); bool sawPart = false, sawNothing = false; std::string where; const uint64_t end = us_ + 10000000ull;
                while (us_ < end) { loopPass(); for (const char *ln : {"t4", "busy"}) if (fields[std::string("vis:") + ln] == "1") { const std::string &l = fields[ln];   // (its own line t4; and - behind the box, the Governor page come - that page's line)
                        if (l.find("Governor global: only PART came back") != std::string::npos && !sawPart) { sawPart = true; where += std::string(" PART on ") + (CurrentView == RFGOVERNORVIEW_GLOBAL ? "its page" : "the Governor page"); }
                        if (l.find("Governor global: nothing came back") != std::string::npos && !sawNothing) { sawNothing = true; where += std::string(" NOTHING on ") + (CurrentView == RFGOVERNORVIEW_GLOBAL ? "its page" : "the Governor page"); } } }
                if (SHOWIT && k < 3) printf("      [%s %d] the line:%s; a box %d '%s'; the view at the end %d\n", condName[c], k, where.c_str(), boxes, lastBox.substr(0, 40).c_str(), CurrentView);
                pipeTells = pt; radioBudget = -1; ++n; const int in = globalFlagsIn(); const bool w = in == 24;
                whole += w; if (w) { partWhole += sawPart; nothingWhole += sawNothing; } else if (in) { ++someIn; partOk += sawPart && !sawNothing; saidLine += sawPart || sawNothing; } else { ++noneIn; nothingOk += sawNothing && !sawPart; }
                otherLine += boxes != 0 && lastBox.find("Failed to read global") != std::string::npos; boxW += w && boxes != 0; }
            printf("   %-48s n %3d | its 24 bytes came in %3d: 'only PART' said over them %3d, 'nothing came back' %3d | some came %3d: 'only PART' said %3d | none came %3d: 'nothing came back' said %3d | a box %d\n",
                   condName[c], n, whole, partWhole, nothingWhole, someIn, partOk, noneIn, nothingOk, otherLine);
            MUST(n > N / 2 && partWhole == 0 && nothingWhole == 0, "l. e99: Governor global, %s: no line over a read whose 24 bytes came ('only PART' %d, 'nothing' %d, of %d whole)", condName[c], partWhole, nothingWhole, whole);
            // not whole: the page says so - its box (HideGOVConfigMsg: "Failed to read global", and the Governor page comes), and the line "Governor global: ... came back"
            MUST(otherLine == n - whole && boxW == 0, "l. Governor global, %s: the box 'Failed to read global' on every visit whose 24 bytes did not come, never on one whose did (%d of %d; over a whole read %d)", condName[c], otherLine, n - whole, boxW);
            MUST(nothingOk == noneIn, "l. Governor global, %s: 'nothing came back' ALWAYS when none came (%d of %d)", condName[c], nothingOk, noneIn);
            if (partOk != someIn) printf("   KNOWN (the released firmware's - B210 alike, e99work 17 Nov, for B212): Governor global, %s: only some of its 24 bytes came in %d, and the line said 'only PART came back' in %d -\n"
                                         "         it says 'nothing came back', on the GOVERNOR page behind the box: HideGOVConfigMsg opens that page (Start_RF_Governor), whose ask clears the count before BlockSilence speaks\n", condName[c], someIn, partOk);
            MUST(someIn == 0 || saidLine == someIn, "l. Governor global, %s: a line 'Governor global: ... came back' ALWAYS when only some came (%d of %d)", condName[c], saidLine, someIn);
            if (c == 0) MUST(whole == n, "l. Governor global, the flight controller answering: its 24 bytes came on every visit (%d of %d)", whole, n);
            if (c == 1) MUST(noneIn == n, "l. Governor global, the flight controller silent: nothing came (%d of %d)", noneIn, n);
            if (c == 2) MUST(someIn == n, "l. Governor global, the telling cut: some came, never all (%d of %d)", someIn, n); }
    }
    // ---------------------------------------------------------------- j. THE STRAY BLOCK ON THE GOVERNOR PAGE (the one page of the three with a "whole" mark in B210)
    if (want("j")) {
        printf("j. THE STRAY BLOCK ON THE GOVERNOR (bank) PAGE: a page left, the menu, Governor 0.3 to 0.9 s later\n   - with a flight controller that answers, and with one that gives NOTHING FRESH (it does not answer the governor's read for 6 s: restarting, or the link poor)\n");
        static const char *srcName[7] = {"PIDs, left 0.3-1.2 s after it opened", "PID +, left 0.3-1.2 s after it opened", "Governor global, left 0.3-0.7 s after it opened", "Governor global, left 1.0-3.0 s after it opened", "Governor global, an edit saved and confirmed",
                                         "PIDs, an edit saved and CONFIRMED, then OK", "PIDs, open 4 s (its window over), then OK"};
        for (int dead = 0; dead < 2; ++dead) for (int sc = 0; sc < 7; ++sc) { int n = 0, stray = 0, wholeWrong = 0, editOnWrong = 0, refusedAtEnd = 0, savedWrong = 0, saidSaved = 0, lineUp = 0; long wrongMs = 0, wrongMost = 0;
            for (int k = 0; k < N; ++k) { fresh();
                if (sc == 0) { openPage(PG_PID); runMs((uint32_t) rr(300, 1200)); okPage(PG_PID); }
                else if (sc == 1) { openPage(PG_PIDADV); runMs((uint32_t) rr(300, 1200)); okPage(PG_PIDADV); }
                else if (sc == 2) { openPage(PG_GOVCFG); runMs((uint32_t) rr(300, 700)); okPage(PG_GOVCFG); }
                else if (sc == 3) { openPage(PG_GOVCFG); runMs((uint32_t) rr(1000, 3000)); okPage(PG_GOVCFG); }
                else if (sc == 4) { openPage(PG_GOVCFG); runMs(3200); edit(PG_GOVCFG); savePage(PG_GOVCFG); runMs(3000); if (GOVS_GLOBAL_Were_Edited) { runMs(6000); } okPage(PG_GOVCFG); }
                else if (sc == 5) { openPage(PG_PID); runMs(3200); edit(PG_PID); savePage(PG_PID); const uint64_t e2 = us_ + 6000000ull; while (us_ < e2 && (RfVerifyPending() || BcStep)) loopPass(); runMs((uint32_t) rr(300, 1200)); okPage(PG_PID); }
                else { openPage(PG_PID); runMs(4000); okPage(PG_PID); }
                if (CurrentView != ROTORFLIGHTVIEW) continue;
                runMs((uint32_t) rr(300, 900)); ++n; const int b = Bank - 1; int prof[18]; for (int i = 0; i < 18; ++i) prof[i] = fcGovV[b][i];
                if (dead) fcDead = true;
                const int t0 = tellings; openPage(PG_GOV); long w = 0; bool everWholeWrong = false;
                const uint64_t end = us_ + 2400000ull; while (us_ < end) { loopPass(); bool wrong = false; for (int i = 1; i < 16; ++i) if (GovAckPayload[i] != (uint8_t) prof[i]) wrong = true; if (GOV_Loaded && wrong) { everWholeWrong = true; ++w; } }
                bool wrongNow = false; for (int i = 1; i < 16; ++i) if (GovAckPayload[i] != (uint8_t) prof[i]) wrongNow = true;
                runMs(700);                                                       // (the window's end: its line, if any)
                wholeWrong += everWholeWrong; lineUp += busyUp;
                boxes = 0; fields["n1"] = std::to_string(atoi(fields["n1"].c_str()) + 3); GOVS_P_Were_Edited(); const bool taken = boxes == 0; if (!taken) ++refusedAtEnd;
                if (taken && wrongNow && GOV_Loaded) { ++editOnWrong; fcDead = false; runMs(4000); boxes = 0; Save_RF_Governor(); runMs(7000);
                    bool bad = false; for (int i = 3; i < 16; ++i) if (i != 3 && fcGovV[b][i] != prof[i]) bad = true; savedWrong += bad; saidSaved += bad && fields["busy"] == "Saved, and confirmed by reading it back."; }
                GOVS_PROFILE_Were_Edited = false; }
            printf("   %-9s %-46s n %3d | 'whole' on another page's bytes at some moment %3d | at the window's end: edits refused %3d, AN EDIT TAKEN ON ANOTHER PAGE'S BYTES %3d (a line stood on the page in %3d) | then saved: THE GOVERNOR'S BANK WRITTEN WITH THEM %3d, said 'Saved, and confirmed' %3d\n",
                   dead ? "NO FRESH:" : "answers:", srcName[sc], n, wholeWrong, refusedAtEnd, editOnWrong, lineUp, savedWrong, saidSaved);
            MUSTW(n > N / 2 && wholeWrong == 0 && editOnWrong == 0 && savedWrong == 0, "j. the Governor page behind '%s' (%s): never whole on another page's bytes, no edit taken on them, nothing saved from them (whole %d, edit %d, saved %d of %d)", srcName[sc], dead ? "nothing fresh" : "the flight controller answers", wholeWrong, editOnWrong, savedWrong, n);
            if (!dead) MUSTW(refusedAtEnd == 0, "j. ... and with a flight controller that answers the page works: no edit refused (%d of %d)", refusedAtEnd, n);
            if (dead) MUSTW(refusedAtEnd == n && lineUp == n, "j. ... and with nothing fresh every edit is refused and the page says so (refused %d, a line %d, of %d)", refusedAtEnd, lineUp, n); }
    }
    // ---------------------------------------------------------------- k. THE STRAY BLOCK, every page left for every page the menu opens, NOTHING FRESH
    if (want("k")) {
        printf("k. A PAGE LEFT 0.3 to 1.2 s AFTER IT OPENED (Governor global: 1.0 to 3.0 s), THE MENU, THE NEXT PAGE 0.3 to 0.9 s LATER - AND NOTHING FRESH COMES for it:\n   of %d visits, how many end with AN EDIT TAKEN while the page's numbers are not its own block (and how many with every edit refused)\n", N);
        static const int dsts[3] = {PG_PID, PG_RATES, PG_GOV};
        printf("   %-18s", "left \\ opened"); for (int d : dsts) printf(" | %-28s", pgName[d]); printf("     (Dynamics -> Rates: KNOWN, B212 - the same four items)\n");
        for (int sc = 0; sc < 6; ++sc) { printf("   %-18s", pgName[sc]);
            for (int d : dsts) { if (d == sc) { printf(" | %-28s", "-"); continue; } int taken = 0, refused = 0, n = 0;
                for (int k = 0; k < N; ++k) { fresh(); openPage(sc); runMs(sc == PG_GOVCFG ? (uint32_t) rr(1000, 3000) : (uint32_t) rr(300, 1200)); okPage(sc); if (CurrentView != ROTORFLIGHTVIEW) continue;
                    runMs((uint32_t) rr(300, 900)); ++n; fcDead = true; const int b = Bank - 1, r = DualRateInUse - 1; openPage(d); runMs(3100);
                    bool wrong = false;
                    if (d == PG_PID) { for (int i = 0; i < 12; ++i) if (PID_Values[i] != fcPidV[b][i]) wrong = true; }
                    else if (d == PG_RATES) { for (int i = 0; i < 13; ++i) if (Rate_Values[i] != (uint8_t) fcRatesV[r][i]) wrong = true; }
                    else { for (int i = 1; i < 16; ++i) if (GovAckPayload[i] != (uint8_t) fcGovV[b][i]) wrong = true; }
                    boxes = 0; if (d == PG_PID) PIDs_Were_edited(); else if (d == PG_RATES) RatesWereEdited(); else GOVS_P_Were_Edited();
                    const bool tk = boxes == 0; taken += tk && wrong; refused += !tk; PIDS_Were_Edited = Rates_Were_Edited = GOVS_PROFILE_Were_Edited = false; }
                char c[40]; snprintf(c, sizeof c, "taken %3d, refused %3d", taken, refused); printf(" | %-28s", c);
                if (sc == PG_RATESADV && d == PG_RATES) continue;   // KNOWN (B212: the Rates' and the Dynamics' blocks have the same four items - not told apart without the block's name)
                MUSTW(n > N / 2 && taken == 0, "k. %s left, %s opened, nothing fresh: no edit taken on another page's bytes (%d of %d)", pgName[sc], pgName[d], taken, n); }
            printf("\n"); }
    }
    // ---------------------------------------------------------------- i. THE GUIDE'S WAY BACK: a page opened from the guide, OK - RotorFlightStart returns at RfHomeBack, the guide's page is up (no menu, no PipeOn)
    if (want("i")) {
        printf("i. THE GUIDE'S WAY BACK (RF_Tools.h RfHomeBack: the menu's routine returns before its page): Governor / Rates / Governor global opened from the guide, OK - the guide stays up 60 s\n");
        static const int pgs[3] = {PG_GOV, PG_RATES, PG_GOVCFG};
        for (int dead = 0; dead < 2; ++dead) for (int pg : pgs) { Stat st; int flagUp = 0;
            for (int k = 0; k < N; ++k) { fresh(); runMs((uint32_t) rr(0, 5000)); CurrentView = GUIDEVIEW; runMs(1500); if (dead) fcDead = true; RfHomeBackAnswer = true; openPage(pg); runMs(dead ? (uint32_t) rr(500, 2000) : (uint32_t) rr(100, 250)); okPage(pg);
                if (CurrentView != GUIDEVIEW) { printf("   (not the guide: view %d)\n", CurrentView); continue; } st.add(untilFree(60000));
                flagUp += Reading_PIDS_Now || Reading_RATES_Now || Reading_RATES_Advanced_Now || Reading_PIDS_Advanced_Now || Reading_GOV_Now || Reading_GOV_Config_Now; }
            printf("   %s%-34s %-16s %s   (a reading flag still up on the guide after that in %d)\n", dead && pg != PG_RATES ? "KNOWN (the released firmware's, B212: no page of the guide ends a read) " : "", dead ? "the flight controller silent, OK 0.5-2 s:" : "OK before its set:", pgName[pg], st.str(60000).c_str(), flagUp);
            MUST((int) st.v.size() + st.never > N / 2, "i. (suite) the guide's way back, %s (%s): the row ran (%d of %d)", pgName[pg], dead ? "silent" : "answering", (int) st.v.size() + st.never, N);   // e99
            if (!dead) MUST(st.never == 0 && MOST(st) <= 1000, "i. the guide's way back, %s left before its set: the bank switch is free when the set has come (within 1.0 s - e99: 0.7 s the most measured)", pgName[pg]); }
    }
    // ---------------------------------------------------------------- n. THE MOTOR SWITCHED ON FROM A WORD PAGE WHOSE READ IS OPEN (Motor_sign.h B16: the front page; e99c: and the bank switch freed)
    if (want("n")) {
        printf("n. The 'Bank 4 & Motor' switch at OFF (bank 4), the 'Banks 1 2 3' switch at 1, no save. A word page opened; 100 to 250 ms later [page] the motor switch to ON (bank 1 wanted) -\n"
               "   or [menu] OK 100-250 ms after it opened (its read still open) and the motor 50-600 ms later. [safety] a safety switch: it goes off 30-300 ms before the motor.\n"
               "   e99d: no save on its way - the RELEASED firmware's road (e99c's 'free at once' taken out): the read stops, the bank switch is freed by the five-second net (asserted: bank 1 within %.1f s;\n"
               "   later than 0.2 s printed KNOWN, B212 B19-B5). A transfer under way (a bank copy, Easy tuning; a bank's word in the radio queue - there is none): the net, within 6 s\n", NET_BOUND_MS / 1000.0);
        const uint8_t sw = SafetySwitch;
        for (int safe = 0; safe < 2; ++safe) for (int menu = 0; menu < 2; ++menu) for (int pg = 0; pg < 6; ++pg) { Stat st, stQ; int motorAtOnce = 0, front = 0, n = 0, late = 0, queued = 0, flagsLeft = 0, said = 0, keep = 0, keepLate = 0;
            for (int k = 0; k < N; ++k) { SafetySwitch = safe ? 2 : 0; LinkRatesToBanks = pg == PG_RATES || pg == PG_RATESADV; fresh(); if (Bank != 4) { printf("   (bank %d at the start)\n", Bank); continue; }
                openPage(pg); uint32_t w = (uint32_t) rr(100, 250);
                if (menu) { runMs(w); okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) continue; w = (uint32_t) rr(50, 600); }
                if (safe) { const uint32_t a = (uint32_t) rr(30, 300); if (a < w) runMs(w - a); pos[2] = 3; runMs(a < w ? a : 0); } else runMs(w);
                pos[1] = 1; const uint64_t t0 = us_; runMs(60); ++n;
                motorAtOnce += MotorEnabled; front += CurrentView == FRONTVIEW;
                const uint64_t end = us_ + 30000000ull; long t = -1; while (us_ < end) { if (Bank == 1) { t = (long)((us_ - t0) / 1000ull); break; } loopPass(); }
                if (SHOWIT && mcall.seen && (mcall.transfer || mcall.keepAlive)) printf("      [%s %s %s trial %d] at the motor's call the radio queue held %d: %d %d %d %d (copy %d, easy %d); bank 1 after %ld ms\n", safe ? "safety" : "none", menu ? "menu" : "page", pgName[pg], k, (int) mcall.radioQ, mcall.q[0], mcall.q[1], mcall.q[2], mcall.q[3], (int) CopyBankRunning(), (int) EasyHoldsBanks(), t);
                if (mcall.seen && mcall.transfer) { ++queued; stQ.add(t); } else { st.add(t); late += t < 0 || t > 200; if (mcall.keepAlive) { ++keep; keepLate += t < 0 || t > 200; } }
                runMs(6000); flagsLeft += anyFlag() || RfVerifyPending(); said += boxes + questions; }
            printf("   %-6s %-4s %-16s the motor ON within 60 ms in %d of %d, the front page in %d; bank 1 %s; LATER THAN 0.2 s in %d (of them with radio words queued at that instant, none a bank's: %d of %d) | a transfer under way: %d, %s | a flag or a read-back left 6 s on: %d\n",
                   safe ? "safety" : "none", menu ? "menu" : "page", pgName[pg], motorAtOnce, n, front, st.str(30000).c_str(), late, keepLate, keep, queued, stQ.str(30000).c_str(), flagsLeft);
            if (E24_OPEN_KNOWN && pg == PG_GOVCFG && !menu && motorAtOnce == n - 1 && front == n - 1 && st.never == 0) printf("   OPEN (the e99d test work: the real tree has it too - seed 17 - the motor switch read later than 60 ms once on the Governor global page): n. %s page Governor global: %d of %d\n", safe ? "safety" : "none", motorAtOnce, n);
            else MUST(n > N / 2 && motorAtOnce == n && front == n && st.never == 0 && stQ.never == 0, "n. the motor switched on from the %s %s (%s): THE MOTOR'S OWN WORD IS NEVER HELD, the front page comes, the bank follows", pgName[pg], menu ? "page's read left open on the menu" : "page with its read open", safe ? "a safety switch" : "none");
            if (late) printf("   KNOWN (the released firmware's, B212 B19-B5 - e99d took e99c's 'free at once' out): n. %s %s %s: no save on its way, the bank later than 0.2 s in %d of %d (radio words queued at the call in %d of them)\n", safe ? "safety" : "none", menu ? "menu" : "page", pgName[pg], late, n - queued, keepLate);
            MUST(st.never == 0 && MOST(st) <= NET_BOUND_MS && (stQ.v.empty() || MOST(stQ) <= 6000), "n. e99d: %s %s %s, no save on its way - the released road: the bank follows the motor switch by the five-second net at the latest (within %.1f s; the most %.2f s, never %d)", safe ? "safety" : "none", menu ? "menu" : "page", pgName[pg], NET_BOUND_MS / 1000.0, MOST(st) / 1000.0, st.never);
            MUST(flagsLeft == 0 && said == 0, "n. e99c (%s, %s): no reading flag nor read-back left 6 s on (%d), no box, no question (%d)", pgName[pg], menu ? "menu" : "page", flagsLeft, said); }
        SafetySwitch = sw; LinkRatesToBanks = false;
    }
    // ---------------------------------------------------------------- v. (suite, e99c work) THE MOTOR SWITCHED ON BEHIND A SAVE
    if (want("v")) {
        const int NV = N / 2 > 12 ? N / 2 : 12;
        printf("v. (e99c) BANK 4 (the 'Bank 4 & Motor' switch at OFF), the 'Banks 1 2 3' switch at 1. An edit, Save, and the motor switch to ON (bank 1 wanted): [0] 0-150 ms after Save, on the page;\n"
               "   [1] 0.15-0.6 s after Save, on the page; [2] Save, OK 0.1-0.6 s on, the motor 0.05-0.6 s after OK (the menu); [3] Save, Help, the motor 0.05-0.6 s on; [4] Save, OK, ANOTHER page, the motor 0.05-0.6 s on.\n"
               "   The write lands at once / 80-250 ms late / NEVER (the old block told) / the flight controller SILENT. In odd trials the 'Banks 1 2 3' switch to 2 as well, 0.05-0.6 s after the motor.\n"
               "   [safety] a safety switch: it goes off 30-300 ms before the motor. %d trials a cell. A cell: n / INTO ANOTHER BANK / FREE BEFORE THE WRITE LANDED / BEYOND ITS BOUND (the latest window e99c kept open\n"
               "   at the motor's call - the read-back's, or a page's read kept up behind it - +0.1 s; AT ONCE (0.06 s) when nothing was kept) / read-back followed. The check of the bank out at OK (B19-B4): counted apart\n", NV);
        const uint32_t boxWas = BOX_MS; BOX_MS = 400; const uint8_t sw = SafetySwitch;
        static const char *roadName[5] = {"Save just pressed", "page, read-back out", "Save, OK (menu)", "Save, Help", "Save, OK, page B"};
        static const char *condName[4] = {"at once", "80-250 late", "NEVER", "FC SILENT"};
        static const int pagesB[4] = {PG_PID, PG_RATES, PG_GOV, PG_GOVCFG};
        long noneN = 0, noneLate = 0;   // (e99d) trials with nothing followed at the motor's call: the released road
        long ckAllN = 0, ckAllWrong = 0, allN = 0, allFollowed = 0, allSaid = 0, allSent = 0, allPend = 0, allFlags = 0, allWrong = 0, allEarly = 0, allBeyond = 0; Stat holdF[6], holdN[6]; std::string sentSeen;
        for (int safe = 0; safe < 2; ++safe) for (int pg = 0; pg < 6; ++pg) for (int road = 0; road < 5; ++road) {
            std::string row; char cell[80]; const bool known = pg == PG_RATES && road == 2;   // (B212 B19-B1: the Rates page's OK frees the switch under its own save - KNOWN, as in part h)
            for (int c = 0; c < 4; ++c) { int n = 0, wrong = 0, early = 0, beyond = 0, followed = 0, said = 0, sent = 0, pendLeft = 0, flagsLeft = 0, never = 0, nCk = 0, wrongCk = 0, earlyCk = 0, openBeyond = 0;
                for (int k = 0; k < NV; ++k) {
                    SafetySwitch = safe ? 2 : 0; LinkRatesToBanks = pg == PG_RATES || pg == PG_RATESADV; fresh(); if (Bank != 4) continue;
                    openPage(pg); runMs(3200); int fcAll[6][4]; for (int b = 0; b < 6; ++b) { fcAll[b][0] = 0; for (int i = 0; i < 17; ++i) fcAll[b][0] += fcPidV[b][i] * (i + 1); fcAll[b][1] = 0; for (int i = 0; i < 13; ++i) fcAll[b][1] += fcRatesV[b][i] * (i + 1) + fcAdvV[b][i] * (i + 7);
                                                     fcAll[b][2] = 0; for (int i = 0; i < 26; ++i) fcAll[b][2] += fcPidAdvV[b][i] * (i + 1); fcAll[b][3] = 0; for (int i = 0; i < 18; ++i) fcAll[b][3] += fcGovV[b][i] * (i + 1); }
                    edit(pg); if (c == 1) { landLo = 80; landHi = 250; } else landLo = landHi = 0; writeLost = c == 2; savePage(pg); if (c == 3) fcDead = true;
                    uint64_t safeAt = 0, bankAt = 0, freedAt = 0; bool motorDone = false;
                    auto step = [&]() { if (safeAt && us_ >= safeAt) { pos[2] = 3; safeAt = 0; } if (bankAt && us_ >= bankAt) { pos[4] = 2; bankAt = 0; } if (motorDone && !freedAt && mcall.seen && !BlockBankChanges) freedAt = us_; loopPass(); };
                    auto run = [&](uint32_t ms) { const uint64_t e = us_ + (uint64_t) ms * 1000ull; while (us_ < e) step(); };
                    auto lastWait = [&](uint32_t w) { if (safe) { const uint32_t a = (uint32_t) rr(30, 300); safeAt = us_ + (uint64_t)(a < w ? w - a : 0) * 1000ull; } run(w); if (safeAt) { pos[2] = 3; safeAt = 0; run(30); } };
                    bool skip = false, ckOut = false, blockBefore = false;
                    if (road == 0) lastWait((uint32_t) rr(0, 150));
                    else if (road == 1) lastWait((uint32_t) rr(150, 600));
                    else { run((uint32_t) rr(100, 600)); if (!(RfVerifyPending() || BcStep)) skip = true;
                        else { saveNowAnswer = false; ckOut = BcStep != 0;   // (the check of the bank still out at OK / Help: the B19-B4 class - KNOWN in part h; here counted apart)
                            if (road == 3) helpTap(); else { okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) skip = true; }
                            if (!skip && road == 4) { run((uint32_t) rr(150, 500)); int b = pg; while (b == pg) b = pagesB[rr(0, 3)]; openPage(b); }
                            if (!skip) lastWait((uint32_t) rr(50, 600)); } }
                    if (skip) continue;
                    blockBefore = BlockBankChanges; pos[1] = 1; motorDone = true; watchFront = true; if (k & 1) bankAt = us_ + (uint64_t) rr(50, 600) * 1000ull;
                    run(12000);
                    if (!mcall.seen || CurrentView != FRONTVIEW) { watchFront = false; continue; }   // (the motor's front page did not come: a box was up - not this road)
                    ++n; followed += mcall.pend; if (!freedAt && !BlockBankChanges) freedAt = us_; if (BlockBankChanges) ++never;
                    said += (boxes - boxes0) + (questions - questions0) + (sounds - sounds0); sent += (int) frontSent.size(); if (!frontSent.empty() && sentSeen.size() < 300) sentSeen += " [" + frontSent[0] + "]";
                    pendLeft += RfVerifyPending(); flagsLeft += anyFlag();
                    if (SHOWIT && anyFlag()) printf("      [%s %s %s %s trial %d] A FLAG UP 12 s on: PIDs %d PID+ %d Rates %d Dyn %d Gov %d GovCfg %d; VfKind %d; view %d; followed at the call %d\n", safe ? "safety" : "none", pgName[pg], roadName[road], condName[c], k,
                                                    (int) Reading_PIDS_Now, (int) Reading_PIDS_Advanced_Now, (int) Reading_RATES_Now, (int) Reading_RATES_Advanced_Now, (int) Reading_GOV_Now, (int) Reading_GOV_Config_Now, (int) VfKind, CurrentView, (int) mcall.pend);
                    const uint64_t bound = mcall.winEnd ? (uint64_t)(mcall.winEnd + 100) * 1000ull : mcall.at + (uint64_t) NET_BOUND_MS * 1000ull;   // (the latest window of what e99c kept open at the call - the read-back's; e99d: nothing kept - the released road, the five-second net)
                    if (!mcall.winEnd && !ckOut) { ++noneN; noneLate += !freedAt || freedAt > mcall.at + 200000ull; }
                    const bool openKeep = E23_OPEN_KNOWN && mcall.keepAlive && !mcall.winEnd; if ((!freedAt || freedAt > bound) && openKeep) ++openBeyond;
                    beyond += (!freedAt || freedAt > bound) && !openKeep;
                    if (SHOWIT && (!freedAt || freedAt > bound)) printf("      [%s %s %s %s trial %d] BEYOND: freed %ld ms after the call, bound %ld ms after it; at the call: read-back pending %d (kind %d), check step %d, held after %d, flags after %d, radio queue %d (keep-alive only %d, a transfer %d)\n", safe ? "safety" : "none", pgName[pg], roadName[road], condName[c], k,
                                                                    freedAt ? (long)((int64_t)(freedAt - mcall.at) / 1000) : -1, (long)((int64_t)(bound - mcall.at) / 1000), (int) mcall.pend, mcall.kind, mcall.bc, (int) mcall.blockAfter, (int) mcall.flagsAfter, (int) mcall.radioQ, (int) mcall.keepAlive, (int) mcall.transfer);
                    if (freedAt) (mcall.pend ? holdF[pg] : holdN[pg]).add((long)((freedAt - mcall.at) / 1000ull)); else (mcall.pend ? holdF[pg] : holdN[pg]).add(-1);
                    const bool e1 = pg != PG_GOVCFG && landAtUs && freedAt && freedAt < landAtUs; if (ckOut) { ++nCk; earlyCk += e1; } else early += e1;
                    watchFront = false;
                    // ... then he lands: the motor OFF (bank 4 again), the safety on, the menu, 15 s there (a save left half way must not go on into another bank)
                    pos[1] = 3; pos[2] = 1; run(400); RotorFlightStart(); run(15000);
                    if (pg != PG_GOVCFG) { bool w = false; for (int b = 0; b < 6; ++b) { if (b == 3) continue; int v[4] = {0, 0, 0, 0}; for (int i = 0; i < 17; ++i) v[0] += fcPidV[b][i] * (i + 1); for (int i = 0; i < 13; ++i) v[1] += fcRatesV[b][i] * (i + 1) + fcAdvV[b][i] * (i + 7);
                                                                                                for (int i = 0; i < 26; ++i) v[2] += fcPidAdvV[b][i] * (i + 1); for (int i = 0; i < 18; ++i) v[3] += fcGovV[b][i] * (i + 1); for (int q = 0; q < 4; ++q) if (v[q] != fcAll[b][q]) w = true; }
                                           if (ckOut) wrongCk += w; else wrong += w;
                                           if (SHOWIT && w) printf("      [%s %s %s %s trial %d] INTO ANOTHER BANK: the check of the bank out at OK %d; held just before the motor %d; at the motor's call: read-back pending %d, check step %d, held after the call %d; freed %ld ms after the call, the write landed %ld ms after it\n", safe ? "safety" : "none", pgName[pg], roadName[road], condName[c], k, (int) ckOut, (int) blockBefore, (int) mcall.pend, mcall.bc, (int) mcall.blockAfter, freedAt ? (long)((int64_t)(freedAt - mcall.at) / 1000) : -1, landAtUs ? (long)((int64_t)(landAtUs - mcall.at) / 1000) : -99999); }
                }
                snprintf(cell, sizeof cell, " | %s %2d/%d/%d/%d/%2d", condName[c], n, wrong, early, beyond, followed); row += cell;
                if (nCk) { char ck[90]; snprintf(ck, sizeof ck, " (check out at OK: %d, %d wrong, %d early)", nCk, wrongCk, earlyCk); row += ck; } ckAllN += nCk; ckAllWrong += wrongCk;
                allN += n; allFollowed += followed; allSaid += said; allSent += sent; allPend += pendLeft; allFlags += flagsLeft; if (!known) { allWrong += wrong; allEarly += early; allBeyond += beyond; }
                if (known) continue;
                MUST(n >= (road <= 1 ? NV * 2 / 3 : 1), "v. (suite) %s, %s, %s, the write %s: the row ran (%d of %d)", safe ? "a safety switch" : "no safety switch", pgName[pg], roadName[road], condName[c], n, NV);
                MUST(wrong == 0 && early == 0, "v. e99c, THE MOTOR BEHIND A SAVE: %s, %s, %s, the write %s: INTO ANOTHER BANK %d, FREE BEFORE THE WRITE HAD LANDED %d, of %d - never, either", safe ? "safety" : "no safety", pgName[pg], roadName[road], condName[c], wrong, early, n);
                MUST(beyond == 0 && never == 0, "v. e99c/e99d: %s, %s, %s, the write %s: the bank switch free by the read-back's own window (+0.1 s) when one is followed, by the five-second net when none is (released) - beyond it %d, still held after 12 s %d, of %d", safe ? "safety" : "no safety", pgName[pg], roadName[road], condName[c], beyond, never, n);
                MUST(said == 0 && sent == 0, "v. e99c: %s, %s, %s, the write %s: on the front page with the motor running NO box, question or sound (%d) and nothing written to it (%d:%s)", safe ? "safety" : "no safety", pgName[pg], roadName[road], condName[c], said, sent, sentSeen.c_str());
                if (E24_OPEN_KNOWN && pg == PG_GOVCFG) { if (flagsLeft) printf("   OPEN (the e99d test work: G6 not closed for the Governor global page - its read-back dropped off its page by a plain set, its flag left up): v. %s %s %s: %d of %d\n", safe ? "safety" : "none", roadName[road], condName[c], flagsLeft, n); }
                else MUST(flagsLeft == 0, "v. e99d (G6): %s, %s, %s, the write %s: no reading flag left up on the front page 12 s after the motor switch (%d of %d)", safe ? "safety" : "no safety", pgName[pg], roadName[road], condName[c], flagsLeft, n);
                if (E23_OPEN_KNOWN && (openBeyond || (pendLeft && road == 4))) printf("   OPEN (the e99bc test work): v. %s %s %s %s: beyond the bound with radio words queued %d; a read-back left pending behind page B %d\n", safe ? "safety" : "none", pgName[pg], roadName[road], condName[c], openBeyond, road == 4 ? pendLeft : 0);
                MUST((E23_OPEN_KNOWN && road == 4) || pendLeft == 0, "v. e99c: %s, %s, %s, the write %s: no read-back left pending 12 s on (%d)", safe ? "safety" : "no safety", pgName[pg], roadName[road], condName[c], pendLeft); }
            printf("   %s%-6s %-15s %-19s%s\n", known ? "KNOWN (B212 B19-B1: the Rates page's OK frees the switch under its save) " : "", safe ? "safety" : "none", pgName[pg], roadName[road], row.c_str()); }
        printf("   (e99c) %ld trials: a read-back followed onto the front page in %ld; into another bank %ld, free before the write landed %ld, beyond the bound %ld (KNOWN rows out); boxes, questions, sounds there %ld; writes to the front page %ld; a reading flag LEFT UP 12 s on %ld; a read-back left pending %ld\n",
               allN, allFollowed, allWrong, allEarly, allBeyond, allSaid, allSent, allFlags, allPend);
        printf("   KNOWN (the released firmware's, B212 B19-B4 - as part h): the check of the bank still out at OK or Help, then the motor: INTO ANOTHER BANK in %ld of %ld\n", ckAllWrong, ckAllN);
        printf("   KNOWN (the released firmware's, B212 B19-B5 - e99d): nothing followed at the motor's call, the check of the bank in: the bank switch later than 0.2 s in %ld of %ld\n", noneLate, noneN);
        MUST(ckAllN < 100 || ckAllWrong * 100 <= ckAllN * 5 + 300, "v. e99d (G1): the check of the bank out at OK or Help, then the motor - INTO ANOTHER BANK no more often than without e99c (noe99c: 25 of 875, 6 of 350) with noise, at most 5 %% + 3: %ld of %ld", ckAllWrong, ckAllN);
        for (int pg = 0; pg < 6; ++pg) printf("   (e99c) %-16s held after the motor's call - a read-back followed: %s\n   %-24s none followed: %s\n", pgName[pg], holdF[pg].str(12000).c_str(), "", holdN[pg].str(12000).c_str());
        // ... a TRANSFER under way at the motor switch: the block stays
        printf("v2. (e99c) A TRANSFER UNDER WAY at the motor switch, no save: [radio] parameters queued (the PIDs page's read open), [copy] a bank copy (Copy a bank), [easy] Easy tuning - the bank switch must stay held\n");
        for (int safe = 0; safe < 2; ++safe) for (int t = 0; t < 3; ++t) { int n = 0, freedAtCall = 0, freedWhile = 0; Stat st;
            for (int k = 0; k < NV; ++k) { SafetySwitch = safe ? 2 : 0; fresh(); if (Bank != 4) continue;
                if (t == 0) { openPage(PG_PID); runMs((uint32_t) rr(100, 250)); } else { CurrentView = t == 1 ? COPYBANKVIEW : EASYVIEW; BlockBankChanges = true; if (t == 1) copyRun = true; else easyHold = true; runMs((uint32_t) rr(100, 1500)); }
                if (safe) { pos[2] = 3; runMs((uint32_t) rr(30, 300)); }
                if (t == 0) { AddParameterstoQueue(GEAR_RATIO); LedGreenMoment = millis(); }   // (the queue held a moment: PAUSE_BEFORE_PARAMETER_SEND)
                if (!BlockBankChanges) continue;   // (nothing held just before the motor: not this road)
                pos[1] = 1; runMs(60); if (!mcall.seen) continue; ++n; freedAtCall += !mcall.blockAfter;
                const uint64_t e = us_ + 1500000ull; while (us_ < e) { if (!BlockBankChanges && (t == 0 ? ParametersToBeSentPointer != 0 : true)) { ++freedWhile; break; } loopPass(); }
                if (t) { if (t == 1) copyRun = false; else easyHold = false; BlockBankChanges = false; }   // (the transfer's own end frees it)
                st.add(untilFree(12000)); }
            printf("   %-6s %-5s n %3d | freed at the motor's call %d, freed while the transfer ran %d | then %s\n", safe ? "safety" : "none", t == 0 ? "radio" : t == 1 ? "copy" : "easy", n, freedAtCall, freedWhile, st.str(12000).c_str());
            if (t == 0) { printf("   (radio: PRINTED, not asserted - the radio queue never holds a bank's words (RfParamOverPipe): e99c keeps the block for them, and part n finds that costs the net's 5-6 s)\n"); MUST(n > NV / 2, "v2. (suite) radio parameters queued at the motor switch (%s): the row ran (%d)", safe ? "safety" : "no safety", n); continue; }
            MUST(n > NV / 2 && freedAtCall == 0 && freedWhile == 0, "v2. e99c: a transfer under way at the motor switch (%s, %s): the bank switch STAYS held (freed at the call %d, while it ran %d, of %d)", t == 1 ? "a bank copy" : "Easy tuning", safe ? "safety" : "no safety", freedAtCall, freedWhile, n); }
        SafetySwitch = sw; LinkRatesToBanks = false; landLo = landHi = 0; writeLost = false; BOX_MS = boxWas;
    }
    // ---------------------------------------------------------------- x. (suite, e99b work 17 Nov 2026) THE FRESH ASK OF ITS OWN PAGE BEHIND A SAVE (RF_Verify.h VfSaveLeftBehind, its second half)
    if (want("x")) {
        printf("x. (e99b) A SAVE WHOSE WRITE NEVER LANDS (the old block told), and the page asked afresh: what does the pilot see? 6 s on the page: whole (an edit taken), the line, a box at the edit.\n"
               "   [1] Help and back 0.1-0.6 s after Save; [2] OK, the same page again 0.1-0.5 s on; [3] OK, the Governor page 0.15-0.5 s on with the flight controller SILENT for it, OK, the menu 5-30 s,\n"
               "   then the page again (the read-back left from long ago); [4] as [3] with the motor switched on from the Governor page (no safety switch), 12 s, off, the menu 5-30 s, the page again;\n"
               "   [5] OK, the 'bank' moved to 2 behind it (as a freed switch would), the same page again; [6] Rates (not linked to the banks): Help, the RATE moved to 2, back;\n"
               "   (e99d) [7] OK, the menu 1-3.5 s (the save still followed there), the page again; [8] Help 1-3.5 s, back. ASSERTED on every road: whole, no edit refused, no false line\n");
        const uint32_t boxWas = BOX_MS; BOX_MS = 400; const uint8_t sw = SafetySwitch;
        static const char *roadName[9] = {"", "Help and back", "OK, the same page again", "OK, Governor (silent), the menu, LATER the page", "... the motor from the Governor page, LATER the page", "OK, BANK 2, the same page", "Rates: Help, RATE 2, back", "OK, the menu 1-3.5 s, the page again", "Help 1-3.5 s, back"};
        Stat toWhole[9], held6[9];   // (e99d) from the fresh ask to the page whole; (round 25) to the bank switch free
        static const int pagesX[3] = {PG_PID, PG_PIDADV, PG_GOV};
        for (int road = 1; road <= 8; ++road) for (int pi = 0; pi < (road == 6 ? 1 : 3); ++pi) { const int pg = road == 6 ? PG_RATES : pagesX[pi]; int n = 0, whole = 0, refused = 0, partLine = 0, nothingLine = 0, pendAtOpen = 0, mended = 0, ownBlock = 0, verdictSaid = 0, asksMoreMost = 0;
            for (int k = 0; k < N; ++k) { motorPos0 = road == 4 ? 3 : 1; SafetySwitch = road == 4 ? 0 : sw; LinkRatesToBanks = false; fresh(); motorPos0 = 3;
                openPage(pg); runMs(3200); edit(pg); writeLost = true; savePage(pg); runMs((uint32_t) rr(100, 600)); if (!RfVerifyPending()) { writeLost = false; continue; }
                saveNowAnswer = false;
                if (road == 1) { helpTap(); runMs((uint32_t) rr(100, 600)); helpBack(); }
                else if (road == 8) { helpTap(); runMs((uint32_t) rr(1000, 3500)); helpBack(); }
                else if (road == 6) { helpTap(); runMs((uint32_t) rr(100, 400)); DualRateInUse = 2; runMs((uint32_t) rr(50, 200)); helpBack(); }
                else { okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) { writeLost = false; continue; }
                    if (road == 2) { runMs((uint32_t) rr(100, 500)); reopen(pg); }
                    else if (road == 7) { runMs((uint32_t) rr(1000, 3500)); reopen(pg); }
                    else if (road == 5) { runMs((uint32_t) rr(100, 500)); Bank = PreviousBank = 2; reopen(pg); }
                    else { runMs((uint32_t) rr(150, 500)); fcDead = true; openPage(PG_GOV); runMs(road == 3 ? 4000 : (uint32_t) rr(300, 900));
                        if (road == 4) { pos[1] = 1; runMs(12000); pos[1] = 3; runMs(400); fcDead = false; if (CurrentView != FRONTVIEW) { writeLost = false; continue; } RotorFlightStart(); }
                        else { fcDead = false; okPage(PG_GOV); }
                        if (CurrentView != ROTORFLIGHTVIEW) { writeLost = false; continue; } runMs((uint32_t) rr(5000, 30000)); pendAtOpen += RfVerifyPending(); reopen(pg); } }
                ++n; { const uint64_t tAsk = us_, e = us_ + 6000000ull; long wAt = -1;   // (e99d) how long from the fresh ask until whole
                  auto kst = [&](bool &f) { f = pg == PG_PID ? Reading_PIDS_Now : pg == PG_PIDADV ? Reading_PIDS_Advanced_Now : pg == PG_GOV ? Reading_GOV_Now : Reading_RATES_Now; return pg == PG_PID ? PID_Start_Time : pg == PG_PIDADV ? PID_Advanced_Start_Time : pg == PG_GOV ? GOV_Start_Time : RATES_Start_Time; };
                  bool f0; uint32_t s0k = kst(f0); int more = 0; const uint64_t heldFrom = us_; long heldUntil = BlockBankChanges ? -1 : 0;   // (round 25, e99e) the asks after the fresh one, and how long the bank switch stays held
                  while (us_ < e) { loopPass(); bool f; const uint32_t s1 = kst(f); if (f && (!f0 || s1 != s0k)) { ++more; s0k = s1; } f0 = f; if (heldUntil < 0 && !BlockBankChanges) heldUntil = (long)((us_ - heldFrom) / 1000ull);
                      if (wAt < 0 && (pg == PG_PID ? PIDS_Loaded : pg == PG_PIDADV ? PIDS_ADV_Loaded : pg == PG_GOV ? GOV_Loaded : RATES_Loaded)) wAt = (long)((us_ - tAsk) / 1000ull); }
                  toWhole[road].add(wAt); if (more > asksMoreMost) asksMoreMost = more; held6[road].add(heldUntil); }
                verdictSaid += notSavedSaid + notConfSaid + savedSaid;
                const std::string line = fields[pg == PG_GOVCFG ? "t4" : "busy"]; const bool up = fields["vis:busy"] == "1";
                partLine += up && line.find("only PART") != std::string::npos; nothingLine += up && line.find("nothing came back") != std::string::npos;
                const bool w = pg == PG_PID ? PIDS_Loaded : pg == PG_PIDADV ? PIDS_ADV_Loaded : pg == PG_GOV ? GOV_Loaded : RATES_Loaded; whole += w;
                { bool own = true; const int b = Bank - 1, rt = DualRateInUse - 1;   // the page's numbers are the flight controller's own (the old block: the write never landed)
                  if (pg == PG_PID) { for (int i = 0; i < 12; ++i) if (PID_Values[i] != fcPidV[b][i]) own = false; } else if (pg == PG_RATES) { for (int i = 0; i < 13; ++i) if (Rate_Values[i] != (uint8_t) fcRatesV[rt][i]) own = false; }
                  else if (pg == PG_GOV) { for (int i = 1; i < 16; ++i) if (GovAckPayload[i] != (uint8_t) fcGovV[b][i]) own = false; } else { for (int i = 0; i < 26; ++i) if (PID_Advanced_Values[i] != (uint8_t) fcPidAdvV[b][i]) own = false; }
                  ownBlock += own; }
                boxes = 0; if (pg == PG_PID) PIDs_Were_edited(); else if (pg == PG_PIDADV) PIDsAdvancedWereEdited(); else if (pg == PG_GOV) GOVS_P_Were_Edited(); else RatesWereEdited(); refused += boxes != 0;
                PIDS_Were_Edited = PIDS_Advanced_Were_Edited = GOVS_PROFILE_Were_Edited = Rates_Were_Edited = false;
                if (!w) { okPage(pg); runMs(800); reopen(pg); runMs(4000); mended += pg == PG_PID ? PIDS_Loaded : pg == PG_PIDADV ? PIDS_ADV_Loaded : pg == PG_GOV ? GOV_Loaded : RATES_Loaded; }
                writeLost = false; }
            printf("   %-52s %-9s n %3d | whole 6 s on %3d | AN EDIT REFUSED %3d | the line 'only PART came back' %3d, 'nothing came back' %3d | its numbers the controller's own %3d | a read-back pending as the page opened %d | not whole, then leave and return: whole %d | a verdict said %d\n",
                   roadName[road], pgName[pg], n, whole, refused, partLine, nothingLine, ownBlock, pendAtOpen, mended, verdictSaid);
            if (road != 5 && road != 6) MUST(whole == n && refused == 0 && partLine == 0 && nothingLine == 0, "x. e99d (G3, G4): %s (%s): a save whose write never lands, the page asked afresh - WHOLE, no edit refused, no 'only PART' / 'nothing came back' line (whole %d, refused %d, 'only PART' %d, 'nothing' %d, of %d)", roadName[road], pgName[pg], whole, refused, partLine, nothingLine, n);
            MUST(n > N / 3, "x. (suite) %s, %s: the row ran (%d of %d)", roadName[road], pgName[pg], n, N);
            printf("          (round 25) asks after the fresh one, at the most: %d\n", asksMoreMost);
            MUST(asksMoreMost <= 1, "x. e99e (G3): %s (%s): at most ONE more ask after the fresh one - never a loop of asks (the most %d)", roadName[road], pgName[pg], asksMoreMost);
            if (road >= 5) MUST(whole == n && refused == 0 && ownBlock == n, "x. e99b: %s (%s): a fresh ask on ANOTHER bank or rate drops the read-back as ever - the page whole on its own block (whole %d, refused %d, own %d, of %d)", roadName[road], pgName[pg], whole, refused, ownBlock, n);
            if (E23_OPEN_KNOWN && (road == 3 || road == 4) && !(whole == n && refused == 0 && partLine == 0)) printf("   OPEN (the e99bc test work): x. %s (%s): not whole %d, refused %d, 'only PART' %d, of %d\n", roadName[road], pgName[pg], n - whole, refused, partLine, n);
            MUST(n == 0 || mended == n - whole, "x. e99b: %s (%s): a page left not whole is whole again when he leaves and returns (%d of %d)", roadName[road], pgName[pg], mended, n - whole); }
        for (int road = 1; road <= 8; ++road) printf("   (e99d) %-52s from the fresh ask until whole: %s\n", roadName[road], toWhole[road].str(6000).c_str());
        for (int road = 1; road <= 8; ++road) printf("   (round 25) %-52s from the fresh ask until the bank switch is free: %s\n", roadName[road], held6[road].str(6000).c_str());
        SafetySwitch = sw; motorPos0 = 3; BOX_MS = boxWas; LinkRatesToBanks = false;
    }
    // ---------------------------------------------------------------- X. (round 26, e99f test work 18 Nov 2026) THE ONE MORE ASK IS FOLLOWED TOO (RF_Verify.h RfVerifyEnd, VfAfresh branch:
    //    VfKind kept while the save is younger than RF_VERIFY_WAIT_MS). How many asks can follow one another; how long until whole and free; the page left DURING that ask;
    //    a second Save during it. Asked by name (--part X); the suite's run has it beside part x.
    if (part.find('X') != std::string::npos) {
        const int NX = N / 2 > 10 ? N / 2 : 10;
        const uint32_t boxWas = BOX_MS; BOX_MS = 400; const uint8_t sw = SafetySwitch;
        static const int pagesXX[4] = {PG_PID, PG_PIDADV, PG_GOV, PG_RATESADV};
        auto FLAGX = [&](int pg, uint32_t &st) { st = pg == PG_PID ? PID_Start_Time : pg == PG_PIDADV ? PID_Advanced_Start_Time : pg == PG_GOV ? GOV_Start_Time : RATES_Advanced_Start_Time;
            return pg == PG_PID ? Reading_PIDS_Now : pg == PG_PIDADV ? Reading_PIDS_Advanced_Now : pg == PG_GOV ? Reading_GOV_Now : Reading_RATES_Advanced_Now; };
        auto LOADEDX = [&](int pg) { return pg == PG_PID ? PIDS_Loaded : pg == PG_PIDADV ? PIDS_ADV_Loaded : pg == PG_GOV ? GOV_Loaded : RATES_ADV_Loaded; };
        auto VIEWX = [&](int pg) { return pg == PG_PID ? PIDVIEW : pg == PG_PIDADV ? PIDADVANCEDVIEW : pg == PG_GOV ? RFGOVERNORVIEW_PROFILE : RATESADVANCEDVIEW; };
        auto OWNX = [&](int pg) { bool own = true; const int b = Bank - 1;
            if (pg == PG_PID) { for (int i = 0; i < 12; ++i) if (PID_Values[i] != fcPidV[b][i]) own = false; } else if (pg == PG_GOV) { for (int i = 1; i < 16; ++i) if (GovAckPayload[i] != (uint8_t) fcGovV[b][i]) own = false; }
            else if (pg == PG_PIDADV) { for (int i = 0; i < 26; ++i) if (PID_Advanced_Values[i] != (uint8_t) fcPidAdvV[b][i]) own = false; } else { const int rt = DualRateInUse - 1; for (int i = 0; i < 15; ++i) if (Rate_Advanced_Values[i] != (uint8_t) fcAdvV[rt][i]) own = false; }
            return own; };
        // one trial: the page pg, [H] Help 0.1-0.6 s on and back 0.1-0.6 s later or [A] OK and the same page again; mode: 0 the write never lands / 1 never lands, BOTH CARRIERS CUT the moment the
        // more ask's old block has come (if before the save's 4 s), back when the next ask is made or 5 s on / 2 never lands, THE CONTROLLER SILENT from the more ask on / 3 the write LANDS during
        // the more ask's window (50 ms - 2.5 s after it); act at the more ask: 0 nothing, 1 OK (the menu), 2 Help, 3 the motor on (no safety switch: the front page), 4 OK and another page, 5 an edit and a SECOND SAVE
        struct XR { bool ran = false; int asks = 0, asksOff = 0; long held = -1, whole = -1, vfGone = -1, landAfterSave = -1; bool more = false, cutBefore4 = false, flagEnd = false, heldEnd = false, vfEnd = false, wholeEnd = false, ownEnd = false, wrong = false, falseLine = false; int box = 0, said = 0, savedOk = 0, secondArmed = 0; };
        auto trialX = [&](int pg, int ex, int mode, int act) { XR r; LinkRatesToBanks = pg == PG_RATESADV; motorPos0 = act == 3 ? 3 : 1; SafetySwitch = act == 3 ? 0 : sw; fresh(); motorPos0 = 3; if (Bank != 1 && act != 3) return r; const int bank0 = Bank;   // (no safety switch, the motor switch off: the 'Bank 4 & Motor' switch says bank 4 - as part z1's MOTOR road)
            openPage(pg); runMs(3200); FcSnap snap; fcTake(snap); edit(pg); if (mode == 3) landLo = landHi = 600000; else writeLost = true; savePage(pg);
            { const uint64_t e = us_ + 2000000ull; while (us_ < e && !(RfVerifyPending() && !BcStep)) loopPass(); } if (!(RfVerifyPending() && !BcStep)) { if (SHOWIT) printf("      [X skip at save] pending %d, check step %d, boxes %d '%s', view %d\n", (int) RfVerifyPending(), (int) BcStep, boxes, lastBox.c_str(), CurrentView); writeLost = false; landLo = landHi = 0; pendOn = false; SafetySwitch = sw; return r; }
            const uint32_t saveMs = SAVE_MS_OF_TREE; const uint64_t saveUs = (uint64_t) saveMs * 1000ull; bool armedFlip = false, flipped = false, cut = false, restored = false, left = false, backFromHelp = false; uint64_t cutAt = 0, moreAt = 0; int s0 = savedSaid + notSavedSaid + notConfSaid, b0 = boxes, sv0 = savedSaid;
            uint32_t st0 = 0; bool f0 = false;
            auto step = [&]() { if (armedFlip && !flipped && !BlockBankChanges) { pos[4] = 2; flipped = true; } loopPass();
                if (r.held < 0 && armedFlip && !BlockBankChanges) r.held = (long)((us_ - saveUs) / 1000ull); if (r.whole < 0 && armedFlip && LOADEDX(pg) && CurrentView == VIEWX(pg)) r.whole = (long)((us_ - saveUs) / 1000ull);
                if (r.vfGone < 0 && VfKind == VK_NONE) r.vfGone = (long)((us_ - saveUs) / 1000ull);
                if (!armedFlip) return;
                uint32_t s1; const bool f = FLAGX(pg, s1); if (f && (!f0 || s1 != st0) && !flipped) { if (CurrentView == VIEWX(pg)) ++r.asks; else ++r.asksOff; st0 = s1;
                    if (r.asks == 1 && !r.more) { r.more = true;   // THE MORE ASK has been made
                        moreAt = us_; if (mode == 2) fcDead = true;
                        if (mode == 3) { if (pendOn) pendAt = millis() + (uint32_t) rr(50, 2500); }
                        if (act == 1) { saveNowAnswer = false; okPage(pg); left = true; } else if (act == 2) { helpTap(); left = true; } else if (act == 3) { pos[1] = 1; left = true; }
                        else if (act == 4) { saveNowAnswer = false; okPage(pg); if (CurrentView == ROTORFLIGHTVIEW) openPage(pg == PG_GOV ? PG_PID : PG_GOV); left = true; }
                        else if (act == 5) { const int bb = boxes; writeLost = false; edit(pg); savePage(pg); r.box += boxes - bb; r.secondArmed = SAVE_MS_OF_TREE != saveMs && RfVerifyPending(); } }
                    else if (cut && !restored) { radioOn = true; pipeTells = true; restored = true; } }
                f0 = f;
                if (mode == 1 && r.more && !cut && us_ - moreAt > 300000ull) { cut = true; cutAt = us_; r.cutBefore4 = (uint32_t)(millis() - saveMs) < RF_VERIFY_WAIT_MS; radioOn = false; pipeTells = false; }
                if (mode == 2 && r.more && fcDead && us_ - moreAt > 6000000ull) fcDead = false;
                if (act == 2 && left && !backFromHelp && us_ - moreAt > 3000000ull) { helpBack(); backFromHelp = true; }
                if (cut && !restored && us_ - cutAt > 5000000ull) { radioOn = true; pipeTells = true; restored = true; } };
            auto run = [&](uint32_t ms) { const uint64_t e = us_ + (uint64_t) ms * 1000ull; while (us_ < e) step(); };
            run((uint32_t) rr(100, 600)); saveNowAnswer = false;
            if (ex == 0) { helpTap(); run((uint32_t) rr(100, 600)); helpBack(); } else { okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) { writeLost = false; landLo = landHi = 0; pendOn = false; SafetySwitch = sw; return r; } run((uint32_t) rr(100, 500)); reopen(pg); }
            if (CurrentView != VIEWX(pg) || (mode == 3 && !pendOn)) { if (SHOWIT) printf("      [X skip] view %d, pendOn %d\n", CurrentView, (int) pendOn); writeLost = false; landLo = landHi = 0; pendOn = false; radioOn = true; pipeTells = true; SafetySwitch = sw; return r; }
            f0 = FLAGX(pg, st0); armedFlip = true; r.ran = true; b0 = boxes;
            run(12000); if (!restored) { radioOn = true; pipeTells = true; } fcDead = false;
            if (act == 3) { pos[1] = 3; run(400); }
            r.flagEnd = anyFlag(); r.heldEnd = BlockBankChanges; r.vfEnd = VfKind != VK_NONE || HAS_AFRESH_NOTE;
            r.wholeEnd = (left && act != 5 && act != 2) ? true : (LOADEDX(pg) && CurrentView == VIEWX(pg)); r.ownEnd = (left && act != 2) ? true : OWNX(pg); r.wrong = (fcChanged(snap) & 3 & ~(bank0 <= 2 ? 1 << (bank0 - 1) : 0)) != 0;
            r.landAfterSave = landAtUs ? (long)(landAtUs / 1000ull) - (long) saveMs : -1;
            { const std::string l = fields["busy"]; r.falseLine = fields["vis:busy"] == "1" && (l.find("only PART") != std::string::npos || l.find("nothing came back") != std::string::npos); }
            r.box += boxes - b0; r.savedOk = savedSaid - sv0; r.said = savedSaid + notSavedSaid + notConfSaid - s0 - (act == 5 ? r.savedOk : 0);
            writeLost = false; landLo = landHi = 0; pendOn = false; radioOn = true; pipeTells = true; fcDead = false; SafetySwitch = sw; pos[1] = 3; return r; };
        static const char *modeX[4] = {"the write never lands", "never lands, BOTH CARRIERS CUT 0.3-5.3 s after the more ask", "never lands, THE CONTROLLER SILENT 6 s from the more ask", "the write LANDS in the more ask's window"};
        printf("X1. (round 26, e99f) Bank 1. An edit, Save; [H] Help and back or [A] OK and the same page again 0.2-1.2 s on; the 'Banks 1 2 3' switch to 2 the moment it is free. %d trials a row:\n"
               "    asks after the fresh one (0/1/2/3+) | from the SAVE: free / whole at the latest; VfKind gone at the latest | 12 s on: a flag up, held, a read-back or its note left, not whole, not its own numbers | boxes, verdicts, false lines | into the other bank (landing inside 4 s / later)\n", NX);
        long longestHold = 0, latestWhole = 0, latestGone = 0; int asksMostAll = 0;
        for (int mode = 0; mode < 4; ++mode) for (int pi = 0; pi < 4; ++pi) for (int ex = 0; ex < 2; ++ex) { const int pg = pagesXX[pi]; if (pg == PG_RATESADV && ex == 1) continue;   // (Dynamics [A]: B212 5a, the Rates page's block first - KNOWN, part h)
            int n = 0, hist[4] = {0, 0, 0, 0}, flagEnd = 0, heldEnd = 0, vfEnd = 0, notWhole = 0, notOwn = 0, box = 0, said = 0, falseL = 0, wIn = 0, nIn = 0, wOut = 0, nOut = 0, cut4 = 0, noFree = 0; long heldMost = 0, wholeMost = 0, goneMost = 0;
            for (int k = 0; k < NX; ++k) { const XR r = trialX(pg, ex, mode, 0); if (!r.ran) continue; ++n; ++hist[r.asks > 3 ? 3 : r.asks]; flagEnd += r.flagEnd; heldEnd += r.heldEnd; vfEnd += r.vfEnd; notWhole += !r.wholeEnd; notOwn += !r.ownEnd && mode != 3; box += r.box; said += r.said; falseL += r.falseLine; cut4 += r.cutBefore4;
                if (r.held < 0) ++noFree; else if (r.held > heldMost) heldMost = r.held; if (r.whole > wholeMost) wholeMost = r.whole; if (r.vfGone > goneMost) goneMost = r.vfGone;
                if (mode == 3) { const bool in = r.landAfterSave >= 0 && r.landAfterSave < (long) RF_VERIFY_WAIT_MS; if (in) { ++nIn; wIn += r.wrong; } else { ++nOut; wOut += r.wrong; } } }
            char cutNote[48] = ""; if (mode == 1) snprintf(cutNote, sizeof cutNote, " (cut before 4 s in %d)", cut4);
            printf("   %-58s %-9s %s n %3d | asks %3d/%3d/%3d/%3d%s | free %5.2f s, whole %5.2f s, VfKind gone %5.2f s | end: flag %d held %d note %d not whole %d not own %d | box %d said %d false %d | wrong in %d/%d later %d/%d\n",
                   modeX[mode], pgName[pg], ex ? "[A]" : "[H]", n, hist[0], hist[1], hist[2], hist[3], cutNote, heldMost / 1000.0, wholeMost / 1000.0, goneMost / 1000.0, flagEnd, heldEnd, vfEnd, notWhole, notOwn, box, said, falseL, wIn, nIn, wOut, nOut);
            if (heldMost > longestHold) longestHold = heldMost; if (wholeMost > latestWhole) latestWhole = wholeMost; if (goneMost > latestGone) latestGone = goneMost; for (int a = 3; a >= 0; --a) if (hist[a]) { if (a > asksMostAll) asksMostAll = a; break; }
            MUST(n > NX / 3, "X1. (suite) %s, %s %s: the row ran (%d of %d)", modeX[mode], pgName[pg], ex ? "[A]" : "[H]", n, NX);
            if (mode == 1 || mode == 2) MUST(flagEnd == 0 && heldEnd == 0 && vfEnd == 0 && noFree == 0 && box == 0 && said == 0, "X1. e99f: %s, %s %s: 12 s on no flag up (%d), free (held %d, never freed %d), no read-back or note left (%d), nothing said (boxes %d, verdicts %d) - the page NOT whole in %d, its line 'nothing came back' (true: nothing came in that window) in %d: printed", modeX[mode], pgName[pg], ex ? "[A]" : "[H]", flagEnd, heldEnd, noFree, vfEnd, box, said, notWhole, falseL);
            else MUST(flagEnd == 0 && heldEnd == 0 && vfEnd == 0 && notWhole == 0 && notOwn == 0 && noFree == 0, "X1. e99f: %s, %s %s: 12 s on no flag up (%d), free (held %d, never freed %d), no read-back or note left (%d), whole (not %d) on the controller's own numbers (not %d)", modeX[mode], pgName[pg], ex ? "[A]" : "[H]", flagEnd, heldEnd, noFree, vfEnd, notWhole, notOwn);
            if (mode == 0 || mode == 3) MUST(box == 0 && said == 0 && falseL == 0, "X1. e99f: %s, %s %s: nothing said - boxes %d, verdicts %d, a false line %d", modeX[mode], pgName[pg], ex ? "[A]" : "[H]", box, said, falseL);
            MUST(goneMost <= (long) RF_VERIFY_WAIT_MS + 100, "X1. e99f (G4/G5): %s, %s %s: VfKind gone 4.1 s after the save at the latest (%.2f s)", modeX[mode], pgName[pg], ex ? "[A]" : "[H]", goneMost / 1000.0);
            MUST(hist[3] == 0, "X1. e99f: %s, %s %s: never more than TWO asks after the fresh one (3 or more in %d)", modeX[mode], pgName[pg], ex ? "[A]" : "[H]", hist[3]);
            if (mode == 0 || mode == 3) MUST(hist[2] == 0, "X1. e99f: %s, %s %s: at most ONE more ask while the block goes on being told (two in %d)", modeX[mode], pgName[pg], ex ? "[A]" : "[H]", hist[2]);
            if (mode == 3) MUST(nIn == 0 || wIn == 0, "X1. e99f: %s, %s %s: a write landing inside the save's 4 s never into the other bank (%d of %d)", modeX[mode], pgName[pg], ex ? "[A]" : "[H]", wIn, nIn); }
        printf("   (round 26, e99f) X1 all rows: the most asks after the fresh one %d; the bank switch free %.2f s after the save at the latest; whole %.2f s; VfKind gone %.2f s\n", asksMostAll, longestHold / 1000.0, latestWhole / 1000.0, latestGone / 1000.0);
        static const char *actX[6] = {"", "OK (the menu)", "Help (back 3 s later)", "the motor on (no safety switch)", "OK and another page", "an edit and a SECOND SAVE"};
        printf("X2. (round 26, e99f) the same, the write never lands; AT THE MORE ASK: OK / Help / the motor on (no safety switch) / OK and another page (Governor; from Governor PIDs) / an edit and a second Save.\n"
               "    12 s on: asks of the page made while it was not showing | a flag up, held, a read-back or its note left | boxes, verdicts (a second Save: its boxes, its read-back armed, 'Saved' said) | into the other bank\n");
        long g5Long = vfDownLong; uint64_t g5Most = vfDownMost; long boxG5 = 0; uint64_t boxG5Most = 0;   // (the second Save's boxes hold the loop - their own time: counted apart from the G5 monitor, printed)
        for (int act = 1; act <= 5; ++act) for (int pi = 0; pi < 4; ++pi) for (int ex = 0; ex < 2; ++ex) { const int pg = pagesXX[pi]; if (pg == PG_RATESADV && ex == 1) continue;
            if (act == 5) { g5Long = vfDownLong; g5Most = vfDownMost; }
            int n = 0, off = 0, flagEnd = 0, heldEnd = 0, vfEnd = 0, box = 0, said = 0, wrong = 0, armed = 0, savedOk = 0, notWhole = 0; long goneMost = 0, freeLo = -1, freeHi = -1;
            for (int k = 0; k < NX; ++k) { const XR r = trialX(pg, ex, 0, act); if (!r.ran || !r.more) continue; ++n; off += r.asksOff; flagEnd += r.flagEnd; heldEnd += r.heldEnd; vfEnd += r.vfEnd; box += r.box; said += r.said; wrong += r.wrong; armed += r.secondArmed; savedOk += r.savedOk; notWhole += !r.wholeEnd; if (r.vfGone > goneMost) goneMost = r.vfGone;
                if (r.held >= 0) { if (freeLo < 0 || r.held < freeLo) freeLo = r.held; if (r.held > freeHi) freeHi = r.held; } }
            char wn[64] = ""; if (act == 5 || act == 2) snprintf(wn, sizeof wn, " not whole %d", notWhole); else if (act == 3) snprintf(wn, sizeof wn, " (free %.2f-%.2f s after the save)", freeLo / 1000.0, freeHi / 1000.0);   // (round 27, e99g: the motor at the more ask - free by the five-second net)
            printf("   %-34s %-9s %s n %3d | asks off the page %d | end: flag %d held %d note %d%s | boxes %d, verdicts %d, second save armed %d, 'Saved' %d | wrong %d | VfKind gone %.2f s after the save\n", actX[act], pgName[pg], ex ? "[A]" : "[H]", n, off, flagEnd, heldEnd, vfEnd, wn, box, said, armed, savedOk, wrong, goneMost / 1000.0);
            MUST(n > NX / 3, "X2. (suite) %s, %s %s: the row ran (%d of %d)", actX[act], pgName[pg], ex ? "[A]" : "[H]", n, NX);
            MUST(off == 0 && flagEnd == 0 && heldEnd == 0 && vfEnd == 0 && said == 0 && wrong == 0, "X2. e99f: %s at the more ask, %s %s: no ask of a page not showing (%d), 12 s on no flag up (%d), free (held %d), no read-back or note left (%d), nothing said (%d), never into the other bank (%d)", actX[act], pgName[pg], ex ? "[A]" : "[H]", off, flagEnd, heldEnd, vfEnd, said, wrong);
            if (act == 5) { boxG5 += vfDownLong - g5Long; if (vfDownMost > boxG5Most) boxG5Most = vfDownMost; vfDownLong = g5Long; vfDownMost = g5Most; }
            if (act == 5 || act == 2) MUST(notWhole == 0, "X2. e99f: %s at the more ask, %s %s: the page whole 12 s on (not %d)", actX[act], pgName[pg], ex ? "[A]" : "[H]", notWhole); else MUST(box == 0, "X2. e99f: %s at the more ask, %s %s: no box (%d)", actX[act], pgName[pg], ex ? "[A]" : "[H]", box); }
        printf("   (round 26) X2, the second Save: its boxes (%d ms each) hold the loop - a read-back held past its save's 4.1 s in %ld trials (the oldest %.3f s): PRINTED, not G5's (the boxes' own time)\n", (int) BOX_MS, boxG5, boxG5Most / 1e6);
        SafetySwitch = sw; BOX_MS = boxWas; motorPos0 = 3; LinkRatesToBanks = false; landLo = landHi = 0; writeLost = false;
    }
    // ---------------------------------------------------------------- M. (round 27, e99g test work 18 Nov 2026) THE MOTOR SWITCH AT EVERY MOMENT BEHIND A SAVE AND A FRESH ASK OF ITS PAGE
    //    (RF_Verify.h RfVerifyFollows: only the read the read-back itself asked is followed at the motor switch). Not in the suite's run (about 29,000 trials a page):
    //    asked by name, --part M (all four pages) or M0..M3 for some (0 PIDs, 1 PID +, 2 Governor, 3 Dynamics). No safety switch; the motor off = the 'Bank 4 & Motor'
    //    switch at OFF (bank 4); the 'Banks 1 2 3' switch to 2 the moment the bank switch is free.
    if (part.find('M') != std::string::npos) {
        std::string ps; { const size_t mp = part.find('M'); for (size_t i = mp + 1; i < part.size() && isdigit((unsigned char) part[i]); ++i) ps += part[i]; } if (ps.empty()) ps = "0123";
        static const int pagesM[4] = {PG_PID, PG_PIDADV, PG_GOV, PG_RATESADV};
        static const char *roadM[2] = {"Help at 0.1 s, back at d", "OK at 0.1 s, the same page again at d"};
        static const int landM[4] = {200, 1000, 3000, -1}; static const char *landName[4] = {"lands 0.2 s", "lands 1 s", "lands 3 s", "NEVER lands"};
        const uint8_t sw = SafetySwitch; const uint32_t boxWas = BOX_MS; BOX_MS = 400;
        printf("M. (round 27, e99g) Bank 4 (the motor off), no safety switch. An edit, Save; the page left 0.1 s on and asked afresh at d = 0.1-3 s (100 ms steps); THE MOTOR ON at m = 0-6 s after the save (100 ms steps);\n"
               "   the write landing at 0.2 / 1 / 3 s / never; the controller answering / silent from the save. A cell's counts: n | (a) a reading flag up 12 s after the motor | (b) VfKind or VfAfresh left at the save's 4.1 s |\n"
               "   (c) the bank switch free BEFORE THE WRITE LANDED with the save younger than 4 s (and at any age) | into banks 1/2 | (d) drawn / said on the front page | the bank switch free after the save: earliest-latest\n");
        long allN = 0, allA = 0, allB = 0, allC = 0, allW = 0, allD = 0;
        for (char pc : ps) { const int pi = pc - '0'; if (pi < 0 || pi > 3) continue; const int pg = pagesM[pi];
            for (int road = 0; road < 2; ++road) for (int c = 0; c < 2; ++c) for (int li = 0; li < 4; ++li) {
                long nBa = 0, nBaPre = 0, nBaOpen = 0; auto afreshOpen = [&]() { return AFRESH_READING; };
                long n = 0, nA = 0, nB = 0, nC4 = 0, nCany = 0, nW = 0, nD = 0, skipped = 0, freeLo = -1, freeHi = -1, notFront = 0; std::string firstA, firstC;
                for (int d = 1; d <= 30; ++d) for (int m = 0; m <= 60; ++m) {
                    motorPos0 = 3; SafetySwitch = 0; LinkRatesToBanks = pg == PG_RATESADV; fresh(); if (Bank != 4) { ++skipped; continue; }
                    openPage(pg); runMs(3200); FcSnap snap; fcTake(snap); edit(pg); if (landM[li] < 0) writeLost = true; else landLo = landHi = 600000; savePage(pg); if (c) fcDead = true;
                    { const uint64_t e = us_ + 2000000ull; while (us_ < e && !(RfVerifyPending() && !BcStep)) loopPass(); }
                    if (!(RfVerifyPending() && !BcStep)) { ++skipped; writeLost = false; landLo = landHi = 0; pendOn = false; fcDead = false; continue; }
                    const uint32_t saveMs = SAVE_MS_OF_TREE; const uint32_t M_ = (uint32_t) m * 100u, D = (uint32_t) d * 100u;
                    bool pendSet = false, flipped = false, motorDone = false, at41 = false, left = false, back = false; uint64_t freedAt = 0, motorAt = 0;
                    auto step = [&]() { if (!pendSet && pendOn && landM[li] >= 0) { const uint32_t want_ = saveMs + (uint32_t) landM[li]; pendAt = (int32_t)(want_ - millis()) > 0 ? want_ : millis(); pendSet = true; }
                        if (!freedAt && !BlockBankChanges && millis() - saveMs > 50) freedAt = us_; if (!flipped && !BlockBankChanges && millis() - saveMs > 50) { pos[4] = 2; flipped = true; }
                        if (!left && millis() - saveMs >= 100 && CurrentView != FRONTVIEW) { left = true; saveNowAnswer = false; if (road == 0) helpTap(); else okPage(pg); }
                        if (left && !back && millis() - saveMs >= (D > 150 ? D : 150)) { back = true; if (road == 0 ? CurrentView == HELP_VIEW : CurrentView == ROTORFLIGHTVIEW) { if (road == 0) helpBack(); else reopen(pg); } }   // (the page's own moves first: reopen() runs its own passes - PID + and Dynamics through the partner's button - and a motor set before it in the same step was
                                                                                                                                        //  seen inside it: the partner's button then tapped over the front page - not a road)
                        if (!motorDone && millis() - saveMs >= M_) { pos[1] = 1; motorDone = true; motorAt = us_; watchFront = true; }
                        loopPass();
                        if (!at41 && millis() - saveMs >= RF_VERIFY_WAIT_MS + 100) { at41 = true; if (VfKind != VK_NONE) ++nB; if (HAS_AFRESH_NOTE) { ++nBa; if (!motorDone) ++nBaPre; if (afreshOpen()) ++nBaOpen; } } };
                    auto run = [&](uint32_t ms) { const uint64_t e = us_ + (uint64_t) ms * 1000ull; while (us_ < e) step(); };
                    while (!motorDone) step();
                    run(12000); if (!at41) run(RF_VERIFY_WAIT_MS + 200);
                    if (!mcall.seen || CurrentView != FRONTVIEW) ++notFront;
                    ++n; const bool a = anyFlag(); nA += a; if (a && firstA.size() < 200) { char t[64]; snprintf(t, sizeof t, " [d %.1f m %.1f]", d / 10.0, m / 10.0); firstA += t; }
                    const long freeMs = freedAt ? (long)(freedAt / 1000ull) - (long) saveMs : -1, landMs = landAtUs ? (long)(landAtUs / 1000ull) - (long) saveMs : -1;
                    if (freeMs >= 0) { if (freeLo < 0 || freeMs < freeLo) freeLo = freeMs; if (freeMs > freeHi) freeHi = freeMs; }
                    const bool early = freedAt && landAtUs && freedAt < landAtUs; nCany += early; if (early && freeMs < (long) RF_VERIFY_WAIT_MS) { ++nC4; if (firstC.size() < 200) { char t[80]; snprintf(t, sizeof t, " [d %.1f m %.1f free %.2f land %.2f]", d / 10.0, m / 10.0, freeMs / 1000.0, landMs / 1000.0); firstC += t; } }
                    nW += (fcChanged(snap) & 3) != 0;
                    nD += (boxes - boxes0) + (questions - questions0) + (sounds - sounds0) + (int) frontSent.size();
                    watchFront = false; writeLost = false; landLo = landHi = 0; pendOn = false; fcDead = false; pos[1] = 3; }
                printf("   %-9s %-38s %-9s %-12s n %4ld | (a) %4ld | (b) VfKind %4ld, VfAfresh %4ld (motor not yet on %ld, its fresh read open %ld) | (c) <4 s %4ld, any %4ld | into 1/2 %4ld | (d) %4ld | free %5.2f-%5.2f s | (no front page %ld, skipped %ld)%s%s\n", pgName[pg], roadM[road], c ? "SILENT" : "answering", landName[li], n, nA, nB, nBa, nBaPre, nBaOpen, nC4, nCany, nW, nD, freeLo / 1000.0, freeHi / 1000.0, notFront, skipped,
                       firstA.empty() ? "" : (" flags:" + firstA).c_str(), firstC.empty() ? "" : (" early:" + firstC).c_str());
                allN += n; allA += nA; allB += nB; allC += nC4; allW += nW; allD += nD;
                MUST(n > 1500 && notFront == 0, "M. (suite) %s, %s, %s, %s: the row ran (%ld; no front page %ld)", pgName[pg], roadM[road], c ? "silent" : "answering", landName[li], n, notFront);
                MUST(nA == 0 && nB == 0 && nBa == nBaOpen && nD == 0, "M. e99g: %s, %s, %s, %s: (a) no reading flag up 12 s after the motor (%ld), (b) VfKind gone by the save's 4.1 s (%ld) and VfAfresh too unless its fresh read is still open (%ld of %ld), (d) nothing on the front page (%ld)", pgName[pg], roadM[road], c ? "silent" : "answering", landName[li], nA, nB, nBa - nBaOpen, nBa, nD);
                MUST(nC4 == 0 && nW == 0, "M. e99g: %s, %s, %s, %s: (c) the bank switch never free before the write landed while the save is younger than 4 s (%ld), nothing into banks 1/2 (%ld)", pgName[pg], roadM[road], c ? "silent" : "answering", landName[li], nC4, nW); }
        }
        printf("   (round 27, e99g) M all rows: %ld trials; (a) %ld, (b) %ld, (c) %ld, into 1/2 %ld, (d) %ld\n", allN, allA, allB, allC, allW, allD);
        SafetySwitch = sw; BOX_MS = boxWas; motorPos0 = 3; LinkRatesToBanks = false; landLo = landHi = 0; writeLost = false;
    }
    // ---------------------------------------------------------------- u. (suite, e99d test work) A SAVE THAT STAYS ON ITS PAGE: ITS VERDICT, EXACTLY AS BEFORE e99d
    if (want("u")) {
        const int NU = N / 2 > 10 ? N / 2 : 10;
        printf("u. (e99d: RfVerifyPending lets go of a read-back whose flag is down) An edit, Save, and the page stays through the three asks (3 windows + 4 s). The write at once / 80-250 ms late / NEVER / FC SILENT / the PIPE DROPPED at the first window's end +-0.4 s\n"
               "   (the re-ask refused) / the pipe dropped 0.3-3 s on and back 1-3 s later / NEVER, with items 33 and 34 of another block told between. %d trials a row: Saved / NOT SAVED / NOT CONFIRMED / nothing / pending at the end / held at the end\n", NU);
        const uint32_t boxWas = BOX_MS; BOX_MS = 400;
        static const char *condU[7] = {"at once", "80-250 late", "NEVER", "FC SILENT", "pipe gone at re-ask", "pipe gone, back", "NEVER, other block told"};
        static const int pagesU[6] = {PG_PID, PG_PIDADV, PG_RATES, PG_RATESADV, PG_GOV, PG_GOVCFG};
        for (int pi = 0; pi < 6; ++pi) for (int c = 0; c < 7; ++c) { const int pg = pagesU[pi]; int n = 0, sv = 0, ns = 0, nc = 0, none = 0, pend = 0, held = 0, multi = 0;
            for (int k = 0; k < NU; ++k) { LinkRatesToBanks = pg == PG_RATES || pg == PG_RATESADV; fresh(); openPage(pg); runMs(pg == PG_GOVCFG ? 4000 : 3200); edit(pg);
                if (c == 1) { landLo = 80; landHi = 250; } else landLo = landHi = 0; writeLost = c == 2 || c == 6; savePage(pg); if (c == 3) fcDead = true;
                const int s0 = savedSaid, n0 = notSavedSaid, c0 = notConfSaid;
                { const uint64_t e = us_ + 2000000ull; while (us_ < e && !RfVerifyPending()) loopPass(); }   // (the bank check first: the read-back is armed behind it)
                if (!RfVerifyPending()) { writeLost = false; landLo = landHi = 0; continue; } ++n; const uint32_t W = pg == PG_GOVCFG ? RF_VERIFY_GOVCFG_WAIT_MS : RF_VERIFY_WAIT_MS, ALL = 3 * W + 4000;
                if (c == 4) { runMs((uint32_t) rr(W - 400, W + 400)); PipeState = 0; runMs(ALL - W); PipeState = 2; }
                else if (c == 5) { runMs((uint32_t) rr(300, 3000)); PipeState = 0; runMs((uint32_t) rr(1000, 3000)); PipeState = 2; runMs(ALL); }
                else if (c == 6) { runMs((uint32_t) rr(300, 1500)); for (int t = 0; t < 4; ++t) { BlockItemSeen(33); BlockItemSeen(34); runMs(30); } runMs(ALL); }   // (items 33, 34: no block's but the PIDs' - BlockNotMine on the others; never a whole set by themselves)
                else runMs(ALL);
                const int a = savedSaid - s0, b = notSavedSaid - n0, d = notConfSaid - c0; sv += a > 0; ns += b > 0; nc += d > 0; none += a + b + d == 0; multi += a + b + d > 1; pend += RfVerifyPending(); held += BlockBankChanges;
                fcDead = false; writeLost = false; landLo = landHi = 0; }
            printf("   %-16s %-26s n %3d | Saved %3d / NOT SAVED %3d / NOT CONFIRMED %3d / nothing %3d (more than one %d) | pending %d / held %d\n", pgName[pg], condU[c], n, sv, ns, nc, none, multi, pend, held);
            MUST(n > NU / 2 && pend == 0 && held == 0 && multi == 0, "u. e99d: %s, %s: the save stayed on its page - no read-back pending at the end (%d), the bank switch free (held %d), never two verdicts (%d), of %d", pgName[pg], condU[c], pend, held, multi, n);
            if (c <= 3) MUST(none == 0, "u. e99d: %s, %s: the save stayed on its page - its verdict said (nothing said in %d of %d)", pgName[pg], condU[c], none, n); }
        BOX_MS = boxWas; LinkRatesToBanks = false;
    }
    // ---------------------------------------------------------------- y. (suite, e99d test work 18 Nov 2026) THE WRITE LANDS LATE, BEHIND A FRESH ASK OF ITS OWN PAGE
    if (want("y")) {
        const int NY = N / 2 > 10 ? N / 2 : 10;
        printf("y. (e99d: the save followed behind a fresh ask for 1.5 s only) Bank 1, the motor switch at ON (the safety on). An edit, Save; [H] Help 0.1-0.6 s on and back 0.1-0.6 s later, or [A] OK 0.1-0.6 s on and the\n"
               "   same page again 0.1-0.5 s later. THE WRITE LANDS LATE: 0.5-1.0 / 1.0-1.5 / 1.5-2.0 / 2.0-2.5 s after the fresh ask. The 'Banks 1 2 3' switch to 2 [f] the moment it is free, [r] 0.05-0.6 s after\n"
               "   the fresh ask, [-] never. %d trials a cell. A cell: INTO THE OTHER BANK / FREE BEFORE THE WRITE HAD LANDED / THE PAGE WHOLE ON THE OLD NUMBERS 6 s after the write landed / n\n", NY);
        motorPos0 = 1; const uint32_t boxWas = BOX_MS; BOX_MS = 400;
        static const int pagesY[4] = {PG_PID, PG_PIDADV, PG_GOV, PG_RATESADV};
        static const int lateLo[6] = {500, 1000, 1500, 2000, 2500, 3000};   // (round 25: two more columns, the write landing up to 4.7 s after the save)
        long tW = 0, tE = 0, tS = 0, tN = 0; long inFreeMin = 999999, inLandMax = -1; long inW[4][2] = {{0}}, inN[4][2] = {{0}}, outW[4][2] = {{0}}, outN[4][2] = {{0}}, inE[4][2] = {{0}};   // (round 25, e99e) by where the write lands against the SAVE: inside its 4 s, or later
        for (int pi = 0; pi < 4; ++pi) for (int ex = 0; ex < 2; ++ex) for (int mv = 0; mv < 3; ++mv) { const int pg = pagesY[pi]; std::string row; char cell[64];
            for (int li = 0; li < 6; ++li) { int n = 0, wrong = 0, early = 0, stale = 0;
                for (int k = 0; k < NY; ++k) {
                    LinkRatesToBanks = pg == PG_RATESADV; fresh(); if (Bank != 1) continue;
                    openPage(pg); runMs(3200); FcSnap snap; fcTake(snap); edit(pg); landLo = landHi = 600000; const uint32_t saveMs = millis(); savePage(pg);   // (the write held back: it lands where this trial says)
                    uint64_t freedAt = 0; bool flipped = false, armed = false; uint64_t flipAt = 0;
                    auto step = [&]() { if (armed && !freedAt && !BlockBankChanges) freedAt = us_; if (armed && !flipped && ((mv == 0 && !BlockBankChanges) || (mv == 1 && us_ >= flipAt))) { pos[4] = 2; flipped = true; } loopPass(); };
                    auto run = [&](uint32_t ms) { const uint64_t e = us_ + (uint64_t) ms * 1000ull; while (us_ < e) step(); };
                    run((uint32_t) rr(100, 600)); if (!RfVerifyPending() || BcStep) { landLo = landHi = 0; pendOn = false; continue; }
                    saveNowAnswer = false;
                    if (ex == 0) { helpTap(); run((uint32_t) rr(100, 600)); helpBack(); } else { okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) { landLo = landHi = 0; pendOn = false; continue; } run((uint32_t) rr(100, 500)); reopen(pg); }
                    if (!pendOn) { landLo = landHi = 0; continue; }   // (no trigger word reached the receiver yet: not this road)
                    armed = true; flipAt = us_ + (uint64_t) rr(50, 600) * 1000ull; pendAt = millis() + (uint32_t) rr(lateLo[li], lateLo[li] + 500);
                    const bool inside = (int32_t)(pendAt - saveMs) < (int32_t) RF_VERIFY_WAIT_MS;   // (round 25: the write lands inside the save's own 4 s)
                    run(3500); run(6000); ++n;
                    const int m = fcChanged(snap); wrong += (m & 2) != 0; early += freedAt && landAtUs && freedAt < landAtUs;
                    if (mv <= 1) { if (inside) { ++inN[pi][ex]; inW[pi][ex] += (m & 2) != 0; if ((m & 2) && freedAt) { const long fa = (long)(freedAt / 1000ull) - (long) saveMs, la = (long) pendAt - (long) saveMs; if (fa < inFreeMin) inFreeMin = fa; if (la > inLandMax) inLandMax = la; if (SHOWIT) printf("      [y inside] %s %s: freed %ld ms after the save, the write landed %ld ms after it\n", pgName[pg], ex ? "[A]" : "[H]", fa, la); } inE[pi][ex] += freedAt && landAtUs && freedAt < landAtUs; } else { ++outN[pi][ex]; outW[pi][ex] += (m & 2) != 0; } }
                    { const bool loaded = pg == PG_PID ? PIDS_Loaded : pg == PG_PIDADV ? PIDS_ADV_Loaded : pg == PG_GOV ? GOV_Loaded : RATES_ADV_Loaded; bool own = true; const int b = Bank - 1;
                      if (pg == PG_PID) { for (int i = 0; i < 12; ++i) if (PID_Values[i] != fcPidV[b][i]) own = false; } else if (pg == PG_GOV) { for (int i = 1; i < 16; ++i) if (GovAckPayload[i] != (uint8_t) fcGovV[b][i]) own = false; }
                      else if (pg == PG_PIDADV) { for (int i = 0; i < 26; ++i) if (PID_Advanced_Values[i] != (uint8_t) fcPidAdvV[b][i]) own = false; } else { const int rt = DualRateInUse - 1; for (int i = 0; i < 15; ++i) if (Rate_Advanced_Values[i] != (uint8_t) fcAdvV[rt][i]) own = false; }
                      stale += loaded && !own && CurrentView == (pg == PG_PID ? PIDVIEW : pg == PG_PIDADV ? PIDADVANCEDVIEW : pg == PG_GOV ? RFGOVERNORVIEW_PROFILE : RATESADVANCEDVIEW); }
                    landLo = landHi = 0; }
                snprintf(cell, sizeof cell, " | %.1f-%.1f s %2d/%2d/%2d/%2d", lateLo[li] / 1000.0, (lateLo[li] + 500) / 1000.0, wrong, early, stale, n); row += cell; tW += wrong; tE += early; tS += stale; tN += n;
                // (round 24) the write landing 0.5-1.5 s after the fresh ask, the switch moved: ASSERTED never into the other bank - the follow (RF_FOLLOW_AFRESH_MS) covers it.
                // KNOWN: Dynamics, OK and the same page again (B212 5a: the Rates page's block first). OPEN in the base: PID +, OK and the same page again (the PIDs page's ask
                // puts its flag down on the way and e99d's let-go drops the read-back - this round's finding)
                if (G5_E99E && li <= 3 && mv <= 1) MUST(wrong == 0, "y. e99e: %s, %s, the switch %s, the write landing %.1f-%.1f s after the fresh ask: never into the other bank (%d of %d)", pgName[pg], ex ? "OK, the same page again" : "Help and back", mv ? "0.05-0.6 s on" : "at free", lateLo[li] / 1000.0, (lateLo[li] + 500) / 1000.0, wrong, n);   // (round 25: e99e - 0.5-2.5 s, Dynamics behind Rates too)
                if (li <= 1 && mv <= 1 && !(pg == PG_RATESADV && ex == 1) && !G5_E99E) {   // (round 25: under e99e the rules above and below - by the SAVE's 4 s - replace this one)
                    if (E24_OPEN_KNOWN && pg == PG_PIDADV && ex == 1) { if (wrong) printf("   OPEN (the e99d test work: the partner page's ask lets the read-back go): y. PID +, [A] %c, landing %.1f-%.1f s: INTO THE OTHER BANK %d of %d\n", "fr-"[mv], lateLo[li] / 1000.0, (lateLo[li] + 500) / 1000.0, wrong, n); }
                    else MUST(wrong == 0, "y. e99d: %s, %s, the switch %s, the write landing %.1f-%.1f s after the fresh ask: never into the other bank (%d of %d)", pgName[pg], ex ? "OK, the same page again" : "Help and back", mv ? "0.05-0.6 s on" : "at free", lateLo[li] / 1000.0, (lateLo[li] + 500) / 1000.0, wrong, n); } }
            printf("   %-9s %s %c%s\n", pgName[pg], ex ? "[A]" : "[H]", "fr-"[mv], row.c_str()); }
        printf("   (round 25, e99e) the switch moved [f]/[r]; by where the write lands against the save - INSIDE its 4 s: into the other bank / free before it landed / n; LATER: into the other bank / n\n");
        for (int pi = 0; pi < 4; ++pi) for (int ex = 0; ex < 2; ++ex) { const int pg = pagesY[pi];
            printf("   %-9s %s inside %3ld/%3ld/%3ld | later %3ld/%3ld\n", pgName[pg], ex ? "[A]" : "[H]", inW[pi][ex], inE[pi][ex], inN[pi][ex], outW[pi][ex], outN[pi][ex]);
            if (G5_E99E && !(pg == PG_RATESADV && ex == 1) && 0 /* (e99f: closed - no longer OPEN in any base, round 26) */ && E25_OPEN_KNOWN) { if (inW[pi][ex]) printf("   OPEN (the e99e test work, round 25: the one more ask is plain before the save is 4 s old, RF_Verify.h RfVerifyEnd): y. %s %s: a write inside the save's 4 s into the other bank %ld of %ld\n", pgName[pg], ex ? "[A]" : "[H]", inW[pi][ex], inN[pi][ex]); }
            else if (G5_E99E && !(pg == PG_RATESADV && ex == 1)) MUST(inN[pi][ex] > 0 && inW[pi][ex] == 0, "y. e99e: %s, %s, the switch moved: a write landing INSIDE the save's 4 s never goes into the other bank (%ld of %ld)", pgName[pg], ex ? "OK, the same page again" : "Help and back", inW[pi][ex], inN[pi][ex]); }
        if (inFreeMin < 999999) printf("   (round 25) a write landing INSIDE the save's 4 s that went into the other bank: the bank switch freed %ld ms after the save at the earliest; such a write landed up to %ld ms after the save\n", inFreeMin, inLandMax);
        printf("   (e99d) the write landing 0.5-3.5 s after the fresh ask: INTO THE OTHER BANK %ld, free before it landed %ld, the page whole on the old numbers %ld - of %ld trials (PRINTED: the trees side by side; the 0.5-1.5 s columns ASSERTED)\n", tW, tE, tS, tN);
        motorPos0 = 3; BOX_MS = boxWas; LinkRatesToBanks = false; landLo = landHi = 0;
    }
    // ---------------------------------------------------------------- o. (round 25, e99e test work: A SECOND SAVE WHILE THE FIRST IS KEPT - not in the suite's run; --part o)
    if (part.find('o') != std::string::npos) {
        const uint32_t boxWas = BOX_MS; BOX_MS = 400; motorPos0 = 1;
        printf("o1. (round 25) Bank 1. PIDs: an edit, Save (the write landing 1.5-3.5 s after it); OK; the GOVERNOR GLOBAL page 0.1-0.4 s on; when whole, an edit and SAVE there; OK; PIDs again; the bank switch to 2 the moment it is free\n");
        { int n = 0, refused = 0, armed = 0, confirmed = 0, wrong = 0, pidsWhole = 0, staleShown = 0;
            for (int k = 0; k < N; ++k) { fresh(); if (Bank != 1) continue; openPage(PG_PID); runMs(3200); FcSnap snap; fcTake(snap); edit(PG_PID); landLo = landHi = 600000; savePage(PG_PID);
                { const uint64_t e = us_ + 2000000ull; while (us_ < e && !(RfVerifyPending() && !BcStep)) loopPass(); } if (!(RfVerifyPending() && !BcStep)) { landLo = landHi = 0; pendOn = false; continue; }
                const uint32_t saveMs = millis(); const uint32_t L = (uint32_t) rr(1500, 3500); bool pendSet = false, flipped = false, armedFlip = false;
                auto step = [&]() { if (!pendSet && pendOn) { const uint32_t w = saveMs + L; pendAt = (int32_t)(w - millis()) > 0 ? w : millis(); pendSet = true; } if (armedFlip && !flipped && !BlockBankChanges) { pos[4] = 2; flipped = true; } loopPass(); };
                auto run = [&](uint32_t ms) { const uint64_t e = us_ + (uint64_t) ms * 1000ull; while (us_ < e) step(); };
                run(100); saveNowAnswer = false; okPage(PG_PID); if (CurrentView != ROTORFLIGHTVIEW) { landLo = landHi = 0; pendOn = false; continue; }
                run((uint32_t) rr(100, 400)); openPage(PG_GOVCFG); { const uint64_t e = us_ + 3000000ull; while (us_ < e && !AllGlobalConfigBytesReceived()) step(); } run(100);
                ++n; const int b0 = boxes, s0 = savedSaid; fields["n14"] = "2"; edit(PG_GOVCFG); savePage(PG_GOVCFG); run(50);   // (a mode the page accepts: the model's byte is no mode) const bool arm = VfKind == VK_GOV_CFG; armed += arm; refused += boxes > b0 && !arm; if (SHOWIT && !arm) printf("      [o1] not armed: box %s | VfKind %d, Gov global flag %d, all bytes %d, view %d\n", boxes > b0 ? lastBox.c_str() : "(none)", (int) VfKind, (int) Reading_GOV_Config_Now, (int) AllGlobalConfigBytesReceived(), CurrentView);
                run(9000); confirmed += savedSaid > s0; saveNowAnswer = false; okPage(PG_GOVCFG); armedFlip = true; if (CurrentView == ROTORFLIGHTVIEW) { openPage(PG_PID); run(8000); }
                wrong += (fcChanged(snap) & 2) != 0; pidsWhole += PIDS_Loaded && CurrentView == PIDVIEW; if (!pendSet && pendOn) pendAt = millis(); landLo = landHi = 0; pendOn = false; }
            printf("   n %3d | the Governor global save ALLOWED (read back) %d, refused %d | 'Saved, and confirmed' %d | PIDs whole at the end %d | the PIDs write INTO THE OTHER BANK %d\n", n, armed, refused, confirmed, pidsWhole, wrong); }
        printf("o2. (round 25) Bank 1. PIDs: an edit, Save (the write landing 1.0-3.0 s after it); Help 0.1-0.4 s on and back 0.1-0.4 s later; a SECOND edit and SAVE the moment the page is whole (or a box); what is said\n");
        { int n = 0, secondArmed = 0, secondRefused = 0, confirmed = 0, notSaved = 0, wrong = 0, holdsSecond = 0;
            for (int k = 0; k < N; ++k) { fresh(); if (Bank != 1) continue; openPage(PG_PID); runMs(3200); FcSnap snap; fcTake(snap); edit(PG_PID); landLo = landHi = 600000; savePage(PG_PID);
                { const uint64_t e = us_ + 2000000ull; while (us_ < e && !(RfVerifyPending() && !BcStep)) loopPass(); } if (!(RfVerifyPending() && !BcStep)) { landLo = landHi = 0; pendOn = false; continue; }
                const uint32_t saveMs = millis(); const uint32_t L = (uint32_t) rr(1000, 3000); bool pendSet = false;
                auto step = [&]() { if (!pendSet && pendOn) { const uint32_t w = saveMs + L; pendAt = (int32_t)(w - millis()) > 0 ? w : millis(); pendSet = true; } loopPass(); };
                auto run = [&](uint32_t ms) { const uint64_t e = us_ + (uint64_t) ms * 1000ull; while (us_ < e) step(); };
                run((uint32_t) rr(100, 400)); helpTap(); run((uint32_t) rr(100, 400)); helpBack();
                { const uint64_t e = us_ + 6000000ull; while (us_ < e && !PIDS_Loaded) step(); }
                ++n; const int b0 = boxes, s0 = savedSaid, ns0 = notSavedSaid + notConfSaid; landLo = landHi = 0;   // (the second write lands at once)
                edit(PG_PID); savePage(PG_PID); { const uint64_t e = us_ + 2000000ull; while (us_ < e && !(RfVerifyPending() && !BcStep) && boxes == b0) step(); }
                const bool arm = RfVerifyPending(); secondArmed += arm; secondRefused += !arm && boxes > b0;
                run(14000); confirmed += savedSaid > s0; notSaved += notSavedSaid + notConfSaid > ns0; wrong += (fcChanged(snap) & 2) != 0;
                { bool same = true; for (int i = 0; i < 12; ++i) if (PID_Values[i] != fcPidV[0][i]) same = false; holdsSecond += same; }
                pendOn = false; }
            printf("   n %3d | the second Save read back %d, refused %d | 'Saved, and confirmed' %d, NOT SAVED / NOT CONFIRMED %d | the page = what bank 1 holds at the end %d | into the other bank %d\n", n, secondArmed, secondRefused, confirmed, notSaved, holdsSecond, wrong); }
        BOX_MS = boxWas; motorPos0 = 3; landLo = landHi = 0;
    }
    // ---------------------------------------------------------------- t. (round 25, e99e test work: THE ATTACK GRID - not in the suite's run; asked by name: --part t, or t0..t3 for some roads)
    if (part.find('t') != std::string::npos) {
        std::string rs; { const size_t tp = part.find('t'); for (size_t i = tp + 1; i < part.size() && isdigit((unsigned char) part[i]); ++i) rs += part[i]; } if (rs.empty()) rs = "0123";
        static const char *roadT[4] = {"OK, the same page again at d", "Help, back at d", "OK, another page, OK and the page again at d", "OK, the motor on (no safety switch), off at d, the menu, the page"};
        static const int pagesT[5] = {PG_PID, PG_PIDADV, PG_GOV, PG_RATESADV, PG_RATES};
        printf("t. (round 25) THE 4 s GRID. Bank 1. An edit, Save; the page left 0.1 s on and asked afresh at d = 0-5 s after the save (100 ms steps); the write landing L = 0-4.5 s after the save (100 ms steps);\n"
               "   the 'Banks 1 2 3' switch to 2 the moment it is free. 9 s after the fresh ask: INTO THE OTHER BANK (L inside the save's 4 s / later), free before the write landed, the page whole on old numbers, not whole\n");
        const uint8_t sw = SafetySwitch; const uint32_t boxWas = BOX_MS; BOX_MS = 400;
        for (char rc : rs) { const int road = rc - '0'; if (road < 0 || road > 3) continue; long mat[11][10] = {{0}}, matL[11][10] = {{0}};
            for (int pi = 0; pi < 5; ++pi) { const int pg = pagesT[pi]; long n = 0, wIn = 0, nIn = 0, wOut = 0, nOut = 0, early = 0, stale = 0, notWhole = 0, skipped = 0;
                for (int d = 0; d <= 50; ++d) for (int L = 0; L <= 45; ++L) {
                    motorPos0 = road == 3 ? 3 : 1; SafetySwitch = road == 3 ? 0 : sw; LinkRatesToBanks = pg == PG_RATESADV || pg == PG_RATES; fresh(); motorPos0 = 3; if (Bank != 1) { ++skipped; continue; }
                    openPage(pg); runMs(3200); FcSnap snap; fcTake(snap); edit(pg); landLo = landHi = 600000; savePage(pg);
                    { const uint64_t e = us_ + 2000000ull; while (us_ < e && !(RfVerifyPending() && !BcStep)) loopPass(); }   // (the bank check first: the read-back armed - the save's own moment)
                    if (!(RfVerifyPending() && !BcStep)) { ++skipped; landLo = landHi = 0; pendOn = false; pos[1] = 3; continue; }
                    const uint32_t saveMs = millis();
                    bool pendSet = false, flipped = false; uint64_t freedAt = 0;
                    auto step = [&]() { if (!pendSet && pendOn) { const uint32_t want = saveMs + (uint32_t) L * 100u; pendAt = (int32_t)(want - millis()) > 0 ? want : millis(); pendSet = true; }
                        if (!freedAt && !BlockBankChanges && millis() - saveMs > 50) freedAt = us_; if (!flipped && !BlockBankChanges && millis() - saveMs > 50) { pos[4] = 2; flipped = true; } loopPass(); };
                    auto until = [&](uint32_t at) { while ((int32_t)(millis() - (saveMs + at)) < 0) step(); };
                    auto run = [&](uint32_t ms) { const uint64_t e = us_ + (uint64_t) ms * 1000ull; while (us_ < e) step(); };
                    const uint32_t D = (uint32_t) d * 100u; bool ok = true;
                    until(100); saveNowAnswer = false;
                    if (road == 1) { helpTap(); until(D > 150 ? D : 150); helpBack(); }
                    else { okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) ok = false;
                        else if (road == 0) { until(D > 150 ? D : 150); reopen(pg); }
                        else if (road == 2) { const int other = pg == PG_GOV ? PG_PID : PG_GOV; until(150); openPage(other); until(D > 300 ? D : 300); saveNowAnswer = false; okPage(other); if (CurrentView != ROTORFLIGHTVIEW) ok = false; else reopen(pg); }
                        else { until(150); pos[1] = 1; run(60); if (CurrentView != FRONTVIEW) { ok = false; if (SHOWIT) printf("      [t 3 skip] view %d, ModalWaits %d, mode %d, MotorEnabled %d, SafetySwitch %d\n", CurrentView, (int) ModalWaits, CurrentMode, (int) MotorEnabled, (int) SafetySwitch); } else { until(D > 300 ? D : 300); pos[1] = 3; run(400); RotorFlightStart(); run(2500); reopen(pg); } } }
                    if (!ok) { ++skipped; pos[1] = 3; landLo = landHi = 0; pendOn = false; continue; }
                    run(9000); if (!pendSet && pendOn) { pendAt = millis(); } run(pendSet ? 0 : 3000);
                    ++n; const int m = fcChanged(snap); const bool w = (m & 2) != 0; const bool inside = L * 100 < (int) RF_VERIFY_WAIT_MS;
                    if (inside) { ++nIn; wIn += w; } else { ++nOut; wOut += w; } if (w) { if (inside) ++mat[d / 5][L / 5]; else ++matL[d / 5][L / 5]; }
                    early += freedAt && landAtUs && freedAt < landAtUs;
                    { const bool loaded = pg == PG_PID ? PIDS_Loaded : pg == PG_PIDADV ? PIDS_ADV_Loaded : pg == PG_GOV ? GOV_Loaded : pg == PG_RATES ? RATES_Loaded : RATES_ADV_Loaded; bool own = true; const int b = Bank - 1, rt = DualRateInUse - 1;
                      if (pg == PG_PID) { for (int i = 0; i < 12; ++i) if (PID_Values[i] != fcPidV[b][i]) own = false; } else if (pg == PG_GOV) { for (int i = 1; i < 16; ++i) if (GovAckPayload[i] != (uint8_t) fcGovV[b][i]) own = false; }
                      else if (pg == PG_PIDADV) { for (int i = 0; i < 26; ++i) if (PID_Advanced_Values[i] != (uint8_t) fcPidAdvV[b][i]) own = false; } else if (pg == PG_RATES) { for (int i = 0; i < 13; ++i) if (Rate_Values[i] != (uint8_t) fcRatesV[rt][i]) own = false; }
                      else { for (int i = 0; i < 15; ++i) if (Rate_Advanced_Values[i] != (uint8_t) fcAdvV[rt][i]) own = false; }
                      const int view = pg == PG_PID ? PIDVIEW : pg == PG_PIDADV ? PIDADVANCEDVIEW : pg == PG_GOV ? RFGOVERNORVIEW_PROFILE : pg == PG_RATES ? RATESVIEW_RF : RATESADVANCEDVIEW;
                      stale += loaded && !own && CurrentView == view; notWhole += !(loaded && CurrentView == view);
                      if (SHOWIT && (w || (loaded && !own) || !loaded)) printf("      [t %d %s d %.1f L %.1f] wrong %d, freed %ld ms after the save, landed %ld ms after it, loaded %d own %d view %d\n", road, pgName[pg], d / 10.0, L / 10.0, (int) w, freedAt ? (long)(freedAt / 1000ull) - (long) saveMs : -1L, landAtUs ? (long)(landAtUs / 1000ull) - (long) saveMs : -1L, (int) loaded, (int) own, CurrentView); }
                    pos[1] = 3; landLo = landHi = 0; pendOn = false; }
                printf("   %-62s %-9s n %5ld | INTO THE OTHER BANK: L inside 4 s %4ld of %5ld, L later %4ld of %4ld | free before it landed %5ld | whole on OLD numbers %4ld | NOT WHOLE %4ld | (skipped %ld)\n", roadT[road], pgName[pg], n, wIn, nIn, wOut, nOut, early, stale, notWhole, skipped);
                // (round 26, e99f) ASSERTED: on its own page asked afresh (roads 0, 1) a write landing INSIDE the save's 4 s never goes into the other bank, and the page is whole
                // (the Rates page by OK: KNOWN, B212 B19-B1 - its OK frees the switch under its own save). Road 2 (by way of another page): DECLARED not held (RF_Verify.h, e99f's
                // comment; e99e's tests finding 2) - printed. Road 3 never runs (the 'Bank 4 & Motor' switch: not bank 1 - a hole of round 25's grid, the motor road is part v's and X2's)
                if (road <= 1 && !(pg == PG_RATES && road == 0)) MUST(nIn > 0 && wIn == 0 && notWhole == 0, "t. e99f: %s, %s: a write landing inside the save's 4 s never into the other bank (%ld of %ld), the page whole 9 s on (not %ld)", roadT[road], pgName[pg], wIn, nIn, notWhole);
                else if (road == 2 && wIn) printf("   DECLARED (RF_Verify.h: not held by way of another page - e99e's tests, finding 2): t. %s, %s: inside the save's 4 s into the other bank %ld of %ld\n", roadT[road], pgName[pg], wIn, nIn); }
            printf("   %s - INTO THE OTHER BANK with L INSIDE the save's 4 s (all pages), rows d (0.5 s), columns L (0.5 s):\n", roadT[road]);
            for (int r = 0; r < 11; ++r) { printf("     d %.1f-%.1f:", r / 2.0, r / 2.0 + 0.5); for (int c = 0; c < 8; ++c) printf(" %4ld", mat[r][c]); printf("   | later:"); for (int c = 8; c < 10; ++c) printf(" %4ld", matL[r][c]); printf("\n"); } }
        SafetySwitch = sw; BOX_MS = boxWas; motorPos0 = 3; LinkRatesToBanks = false; landLo = landHi = 0;
    }
    // ---------------------------------------------------------------- z. (suite, e99d test work) G6: A FOLLOWED SAVE ENDED OFF ITS PAGE; HELP AND BACK AT EVERY DELAY; G7: THE BLANK SCREEN
    if (want("z")) {
        const int NZ = N / 2 > 10 ? N / 2 : 10;
        const uint32_t boxWas = BOX_MS; BOX_MS = 400; const uint8_t sw = SafetySwitch;
        static const int pagesZ[4] = {PG_PID, PG_PIDADV, PG_GOV, PG_RATESADV};
        auto LOADED = [&](int pg) { return pg == PG_PID ? PIDS_Loaded : pg == PG_PIDADV ? PIDS_ADV_Loaded : pg == PG_GOV ? GOV_Loaded : RATES_ADV_Loaded; };
        auto VIEWOF = [&](int pg) { return pg == PG_PID ? PIDVIEW : pg == PG_PIDADV ? PIDADVANCEDVIEW : pg == PG_GOV ? RFGOVERNORVIEW_PROFILE : RATESADVANCEDVIEW; };
        auto OWN = [&](int pg) { bool own = true; const int b = Bank - 1;
            if (pg == PG_PID) { for (int i = 0; i < 12; ++i) if (PID_Values[i] != fcPidV[b][i]) own = false; } else if (pg == PG_GOV) { for (int i = 1; i < 16; ++i) if (GovAckPayload[i] != (uint8_t) fcGovV[b][i]) own = false; }
            else if (pg == PG_PIDADV) { for (int i = 0; i < 26; ++i) if (PID_Advanced_Values[i] != (uint8_t) fcPidAdvV[b][i]) own = false; } else { const int rt = DualRateInUse - 1; for (int i = 0; i < 15; ++i) if (Rate_Advanced_Values[i] != (uint8_t) fcAdvV[rt][i]) own = false; }
            return own; };
        auto EDIT_TAKEN = [&](int pg) { boxes = 0; if (pg == PG_PID) PIDs_Were_edited(); else if (pg == PG_PIDADV) PIDsAdvancedWereEdited(); else if (pg == PG_GOV) GOVS_P_Were_Edited(); else RatesAdvancedWereEdited();
            const bool ok = boxes == 0 && (PIDS_Were_Edited || PIDS_Advanced_Were_Edited || GOVS_PROFILE_Were_Edited || Rates_Advanced_Were_Edited); PIDS_Were_Edited = PIDS_Advanced_Were_Edited = GOVS_PROFILE_Were_Edited = Rates_Advanced_Were_Edited = false; return ok; };
        // [1] G6
        printf("z1. (e99d G6) Bank 1. An edit, Save; [OK] OK 0.1-0.6 s on (the menu), [HELP] Help 0.1-0.6 s on, [MOTOR] OK and the motor from the menu 0.05-0.6 s on (no safety switch); the write lands 80-250 ms late\n"
               "    (what was sent comes back OFF the page). Where the read-back ended by that set: 0.1 s on no reading flag up, the bank switch free, nothing said; then the page again (Help left; reopened;\n"
               "    the motor off and the page from the menu): whole, the controller's numbers (the edit), an edit taken. %d trials a row.\n", NZ);
        static const char *leaveName[3] = {"OK", "HELP", "MOTOR"};
        for (int lv = 0; lv < 3; ++lv) for (int pi = 0; pi < 4; ++pi) { const int pg = pagesZ[pi]; int n = 0, bySet = 0, flagUp = 0, held = 0, said = 0, whole = 0, own = 0, taken = 0, wrong = 0;
            for (int k = 0; k < NZ; ++k) { motorPos0 = lv == 2 ? 3 : 1; SafetySwitch = lv == 2 ? 0 : sw; LinkRatesToBanks = pg == PG_RATESADV; fresh(); motorPos0 = 3;
                openPage(pg); runMs(3200); FcSnap snap; fcTake(snap); edit(pg); landLo = 80; landHi = 250; const int bank0 = Bank; savePage(pg); runMs((uint32_t) rr(100, 600));
                if (!RfVerifyPending() || BcStep) { landLo = landHi = 0; continue; }
                const int s0 = savedSaid + notSavedSaid + notConfSaid; const uint8_t kind = VfKind; const uint32_t win = VfReadStart + RF_VERIFY_WAIT_MS; saveNowAnswer = false;
                if (lv == 1) helpTap(); else { okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) { landLo = landHi = 0; continue; } if (lv == 2) { runMs((uint32_t) rr(50, 600)); pos[1] = 1; runMs(60); if (CurrentView != FRONTVIEW) { pos[1] = 3; landLo = landHi = 0; continue; } } }
                ++n; bool ended = false, endedBySet = false; { const uint64_t e = us_ + 6000000ull; while (us_ < e && !ended) { loopPass(); if (VfKind == VK_NONE) { ended = true; endedBySet = (int32_t)(millis() - win) < 0; } } }
                if (endedBySet) { ++bySet; runMs(100); flagUp += anyFlag(); held += BlockBankChanges; }
                runMs(500); said += savedSaid + notSavedSaid + notConfSaid - s0;
                if (lv == 1) helpBack(); else if (lv == 0) reopen(pg); else { pos[1] = 3; runMs(400); RotorFlightStart(); runMs(2500); reopen(pg); }   // (the pipe let go by the motor's front page joins again 0.4-1.5 s after the menu)
                runMs(4000); whole += LOADED(pg) && CurrentView == VIEWOF(pg); own += OWN(pg); taken += EDIT_TAKEN(pg); wrong += (fcChanged(snap) & 3 & ~(1 << (bank0 - 1))) != 0; landLo = landHi = 0; (void) kind; }
            printf("   %-6s %-9s n %3d | ended by its set off the page %3d: 0.1 s on a flag up %d, the bank switch held %d | a verdict said %d | the page again: whole %3d, the controller's numbers %3d, an edit taken %3d | into another bank %d\n", leaveName[lv], pgName[pg], n, bySet, flagUp, held, said, whole, own, taken, wrong);
            MUST(n > NZ / 2 && bySet > 0, "z1. (suite) %s, %s: the row ran (%d of %d; ended by its set off the page %d)", leaveName[lv], pgName[pg], n, NZ, bySet);
            MUST(flagUp == 0 && held == 0 && said == 0, "z1. e99d (G6): %s, %s: a followed save ended by its set off its page - no reading flag left up (%d), the bank switch free (held %d), nothing said off the page (%d)", leaveName[lv], pgName[pg], flagUp, held, said);
            MUST(whole == n && own == n && taken == n && wrong == 0, "z1. e99d (G6): %s, %s: the page visited again reads afresh - whole %d, the controller's numbers %d, an edit taken %d, into another bank %d, of %d", leaveName[lv], pgName[pg], whole, own, taken, wrong, n); }
        SafetySwitch = sw; LinkRatesToBanks = false;
        // [2] Help and back at every delay
        printf("z2. (e99d) Bank 1 (the motor switch at ON, the safety on). An edit, Save, Help 0.1-0.6 s on, BACK after 0-0.25 / 0.25-0.5 / 0.5-1 / 1-1.5 / 1.5-2 / 2-3 s; the write at once / 80-250 ms late / NEVER;\n"
               "    the 'Banks 1 2 3' switch to 2 the moment it is free (and 9 s on in any case). 8 s after back: never into the other bank, never free before the write landed, the page whole on what the controller\n"
               "    holds, no 'only PART' / 'nothing came back' line. A cell: wrong / early / not whole / not its own numbers / a false line / n\n");
        motorPos0 = 1;
        static const int backLo[6] = {0, 250, 500, 1000, 1500, 2000}, backHi[6] = {250, 500, 1000, 1500, 2000, 3000};
        static const char *condZ[3] = {"at once", "80-250 late", "NEVER"};
        for (int pi = 0; pi < 4; ++pi) for (int c = 0; c < 3; ++c) { const int pg = pagesZ[pi]; std::string row; char cell[64]; int rn = 0, rw = 0, re = 0, rnw = 0, rno = 0, rl = 0;
            for (int di = 0; di < 6; ++di) { int n = 0, wrong = 0, early = 0, notWhole = 0, notOwn = 0, falseLine = 0;
                for (int k = 0; k < NZ; ++k) { LinkRatesToBanks = pg == PG_RATESADV; fresh(); if (Bank != 1) continue;
                    openPage(pg); runMs(3200); FcSnap snap; fcTake(snap); edit(pg); if (c == 1) { landLo = 80; landHi = 250; } else landLo = landHi = 0; writeLost = c == 2; savePage(pg);
                    uint64_t freedAt = 0; bool flipped = false, armed = false;
                    auto step = [&]() { if (armed && !freedAt && !BlockBankChanges) freedAt = us_; if (armed && !flipped && !BlockBankChanges) { pos[4] = 2; flipped = true; } loopPass(); };
                    auto run = [&](uint32_t ms) { const uint64_t e = us_ + (uint64_t) ms * 1000ull; while (us_ < e) step(); };
                    run((uint32_t) rr(100, 600)); if (!RfVerifyPending() || BcStep) { writeLost = false; landLo = landHi = 0; continue; }
                    helpTap(); armed = true; run((uint32_t) rr(backLo[di], backHi[di])); helpBack(); run(8000); if (!flipped) { pos[4] = 2; flipped = true; run(1000); }
                    ++n; const int m = fcChanged(snap); wrong += (m & 2) != 0; early += freedAt && landAtUs && freedAt < landAtUs;
                    notWhole += !(LOADED(pg) && CurrentView == VIEWOF(pg)); notOwn += !OWN(pg);
                    { const std::string l = fields["busy"]; falseLine += fields["vis:busy"] == "1" && (l.find("only PART") != std::string::npos || l.find("nothing came back") != std::string::npos); }
                    writeLost = false; landLo = landHi = 0; }
                snprintf(cell, sizeof cell, " | %.2f-%.2f %d/%d/%d/%d/%d/%2d", backLo[di] / 1000.0, backHi[di] / 1000.0, wrong, early, notWhole, notOwn, falseLine, n); row += cell; rn += n; rw += wrong; re += early; rnw += notWhole; rno += notOwn; rl += falseLine; }
            printf("   %-9s %-12s%s\n", pgName[pg], condZ[c], row.c_str());
            MUST(rn > NZ * 3 && rw == 0 && re == 0 && rnw == 0 && rno == 0 && rl == 0, "z2. e99d: %s, the write %s, Help and back at every delay 0-3 s: into the other bank %d, free before the write landed %d, not whole %d, not the controller's numbers %d, a false line %d, of %d", pgName[pg], condZ[c], rw, re, rnw, rno, rl, rn); }
        // [3] G7, the blank screen
        printf("z3. (e99d G7) Bank 1 (the motor switch at ON, the safety on). An edit, Save, and the SCREEN BLANK 0.1-3.5 s later (the screen saver, Utilities.h HideScreenAgain - it is not refused over a word page), for\n"
               "    1-20 s; then the page back as it was (SaveOrRestoreScreen: no fresh ask), 12 s. The write at once / 80-250 ms late / NEVER / the flight controller SILENT. The 'Banks 1 2 3' switch to 2 the\n"
               "    moment it is free. Counted: a VERDICT said (Saved / NOT SAVED / NOT CONFIRMED), into the other bank, the bank switch held on the blank (the longest), the page whole at the end\n");
        static const char *condB[4] = {"at once", "80-250 late", "NEVER", "FC SILENT"};
        for (int pi = 0; pi < 4; ++pi) for (int c = 0; c < 4; ++c) { const int pg = pagesZ[pi]; int n = 0, outAtBlank = 0, verdict = 0, verdictOut = 0, wrong = 0, whole = 0, freedOnBlank = 0, stuck = 0, bankMoved = 0; long heldMost = 0;
            int pendWant = 0, verdictBefore = 0, neverBlank = 0, droppedBank = 0; long putOffMost = 0, afterEndMost = 0;
            for (int k = 0; k < NZ; ++k) { LinkRatesToBanks = pg == PG_RATESADV; fresh(); if (Bank != 1) continue;
                openPage(pg); runMs(3200); FcSnap snap; fcTake(snap); edit(pg); if (c == 1) { landLo = 80; landHi = 250; } else landLo = landHi = 0; writeLost = c == 2; const int s0 = savedSaid + notSavedSaid + notConfSaid; savePage(pg); if (c == 3) fcDead = true;
                bool flipped = false, netFreed = false; auto step = [&]() { if (!flipped && !BlockBankChanges) { netFreed = VfKind != VK_NONE; pos[4] = 2; flipped = true; } loopPass(); };   // (netFreed: the switch freed with the read-back still pending - the five-second net under a long read-back, not its end)
                auto run = [&](uint32_t ms) { const uint64_t e = us_ + (uint64_t) ms * 1000ull; while (us_ < e) step(); };
                run((uint32_t) rr(100, 3500)); if (BcStep) { writeLost = false; landLo = landHi = 0; continue; }
                // (round 25, e99e) THE SCREEN SAVER'S MOMENT: HideScreenAgain is refused while its gate stands (e99e: a read-back pending) and tried again a second later
                const bool pendAtWant = RfVerifyPending(); pendWant += pendAtWant; { const uint64_t tW = us_; uint64_t tEnd = pendAtWant ? 0 : tW; int tries = 0; while (blankRefused() && tries < 60) { const uint64_t e = us_ + 1000000ull; while (us_ < e) { step(); if (!tEnd && !RfVerifyPending()) tEnd = us_; } ++tries; }
                    const long off = (long)((us_ - tW) / 1000ull); if (off > putOffMost) putOffMost = off; if (tries >= 60) ++neverBlank; if (tEnd) { const long a = (long)((us_ - tEnd) / 1000ull); if (a > afterEndMost) afterEndMost = a; } }
                if (pendAtWant) { if (savedSaid + notSavedSaid + notConfSaid - s0 > 0) ++verdictBefore; else if (Bank != 1) ++droppedBank; }   // (dropped by a bank change: the five-second net freed the switch under the on-page read-back - the released rule, nothing said)
                const bool out = RfVerifyPending(); const int view = CurrentView; ++n; outAtBlank += out;
                CurrentView = BLANKVIEW; SendCommand((char *)"page BlankView"); const uint64_t tB = us_; long freed = -1;   // (HideScreenAgain)
                { const uint64_t e = us_ + (uint64_t) rr(1000, 20000) * 1000ull; while (us_ < e) { if (freed < 0 && !BlockBankChanges) freed = (long)((us_ - tB) / 1000ull); step(); } }
                if (out && freed < 0) { const long h = (long)((us_ - tB) / 1000ull); if (h > heldMost) heldMost = h; } else if (out && freed > heldMost) heldMost = freed; freedOnBlank += out && freed >= 0;
                SendCommand((char *)"page back"); CurrentView = view; fcDead = false; run(12000);
                const int said = savedSaid + notSavedSaid + notConfSaid - s0; verdict += said > 0; if (out && netFreed && Bank != 1 && said == 0) ++bankMoved; else verdictOut += out && said > 0;   // (the bank switch freed by the five-second net under the read-back, on the blank or after the wake, and moved: a bank change read afresh drops the read-back, nothing said - the released rule)
                { const std::string l = fields["busy"]; stuck += fields["vis:busy"] == "1" && (l.find("Sent: reading back") == 0 || l.find("Reading back again") == 0); }
                wrong += (fcChanged(snap) & 2) != 0; whole += LOADED(pg) || (Rates_Were_Edited || PIDS_Were_Edited || PIDS_Advanced_Were_Edited || GOVS_PROFILE_Were_Edited || Rates_Advanced_Were_Edited);
                writeLost = false; landLo = landHi = 0; }
            printf("   %-9s %-12s n %3d | the read-back out at the blank %3d: a verdict said %3d (all trials %3d) | the bank switch freed on the blank %3d, held there at the most %5.2f s | into the other bank %d | whole or Save shown at the end %3d | 'reading back' LEFT STANDING 12 s after the wake %d | dropped by a bank change (the net freed the switch under the read-back) %d\n",
                   pgName[pg], condB[c], n, outAtBlank, verdictOut, verdict, freedOnBlank, heldMost / 1000.0, wrong, whole, stuck, bankMoved);
            printf("          (round 25, e99e) the read-back pending at the saver's moment %d: its verdict said before the blank %d (dropped by a bank change %d) | the blank put off at the most %.2f s, after the read-back's end at the most %.2f s | never blanked in 60 s %d\n", pendWant, verdictBefore, droppedBank, putOffMost / 1000.0, afterEndMost / 1000.0, neverBlank);
            if (G5_E99E) { MUST(outAtBlank == 0 && neverBlank == 0 && afterEndMost <= 1100, "z3. e99e: %s, the write %s: the screen never blanked over a read-back (%d), blanked within 1.1 s after it ended (the most %.2f s), always blanked in the end (never %d)", pgName[pg], condB[c], outAtBlank, afterEndMost / 1000.0, neverBlank);
                MUST(c < 2 || verdictBefore + droppedBank == pendWant, "z3. e99e: %s, the write %s: the verdict said on the page before the blank (%d of %d; dropped by a bank change %d)", pgName[pg], condB[c], verdictBefore, pendWant, droppedBank); }
            MUST(n > NZ / 2 && (c < 2 || verdictOut == outAtBlank - bankMoved), "z3. e99d (G7): %s, the write %s: a read-back out when the screen went blank gives its verdict on its page (at the wake, at the latest) - %d of %d (dropped by a bank change %d)", pgName[pg], condB[c], verdictOut, outAtBlank - bankMoved, bankMoved);
            if (E24_OPEN_KNOWN) { if (stuck) printf("   OPEN (the e99d test work, 18 Nov 2026: a followed save ended by its set on the BLANK screen leaves its line up after the wake): z3. %s, %s: %d of %d\n", pgName[pg], condB[c], stuck, n); }
            else MUST(stuck == 0, "z3. e99d: %s, the write %s, the screen blank: no 'Sent: reading back ...' line left standing on the page 12 s after the wake (%d of %d)", pgName[pg], condB[c], stuck, n);
            MUST(wrong == 0, "z3. e99d (G7): %s, the write %s, the screen blank: never into the other bank (%d)", pgName[pg], condB[c], wrong); }
        // ... the motor road blanked (printed)
        motorPos0 = 3;   // (bank 4: the 'Bank 4 & Motor' switch at OFF)
        printf("z3m. Save (the write NEVER lands), OK, the motor from the menu 0.05-0.6 s on (no safety switch: the front page, the save followed), the screen BLANK 0-2 s later for 20 s, then the front page again: the bank switch on the blank (the motor running) - asserted free by the five-second net (6.5 s)\n");
        for (int pi = 0; pi < 4; ++pi) { const int pg = pagesZ[pi]; int n = 0, pend = 0, flagsLeft = 0, wrong = 0, heldAll = 0; Stat st; long putOffM = 0;
            for (int k = 0; k < NZ; ++k) { SafetySwitch = 0; LinkRatesToBanks = pg == PG_RATESADV; fresh(); openPage(pg); runMs(3200); FcSnap snap; fcTake(snap); edit(pg); writeLost = true; savePage(pg); runMs((uint32_t) rr(100, 600));   // (the write NEVER lands: the save still followed at the blank)
                if (!RfVerifyPending() || BcStep) { writeLost = false; continue; } saveNowAnswer = false; okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) { landLo = landHi = 0; continue; }
                runMs((uint32_t) rr(50, 600)); pos[1] = 1; runMs(60); if (CurrentView != FRONTVIEW) { pos[1] = 3; landLo = landHi = 0; continue; } runMs((uint32_t) rr(0, 2000)); ++n; pend += RfVerifyPending();
                { const uint64_t tW = us_; int tries = 0; while (blankRefused() && tries < 60) { runMs(1000); ++tries; } const long off = (long)((us_ - tW) / 1000ull); if (off > putOffM) putOffM = off; }   // (round 25, e99e: the saver's gate)
                CurrentView = BLANKVIEW; const uint64_t tB = us_; long freed = -1; { const uint64_t e = us_ + 20000000ull; while (us_ < e) { if (freed < 0 && !BlockBankChanges) freed = (long)((us_ - tB) / 1000ull); loopPass(); } }   // (blank for 20 s)
                st.add(freed); heldAll += freed < 0; GotoFrontView(); runMs(6000); flagsLeft += anyFlag() + RfVerifyPending(); wrong += (fcChanged(snap) & 3) != 0; pos[1] = 3; writeLost = false; }
            printf("   %-9s n %3d | read-back pending at the blank %d | the bank switch on the blank: %s | HELD THE WHOLE 20 s %d | a flag or a read-back left 6 s after the wake %d | into another bank %d | (round 25) the blank put off at the most %.2f s\n", pgName[pg], n, pend, st.str(20000).c_str(), heldAll, flagsLeft, wrong, putOffM / 1000.0);
            MUST(n > NZ / 2 && st.never == 0 && MOST(st) <= NET_BOUND_MS, "z3m. e99d (G7): %s: the save followed onto the front page (the motor running), the screen blank - the bank switch free by the five-second net at the latest (within %.1f s; the most %.2f s, held the whole 20 s %d of %d)", pgName[pg], NET_BOUND_MS / 1000.0, MOST(st) / 1000.0, heldAll, n); }
        SafetySwitch = sw; LinkRatesToBanks = false; motorPos0 = 3; BOX_MS = boxWas; landLo = landHi = 0; writeLost = false;
    }
    // ---------------------------------------------------------------- m. B18-1 ITSELF, through the REAL RotorFlightStart (the menu, and the guide's way back): is every edit still refused?
    if (want("m")) {
        printf("m. B18-1 ITSELF BY THE REAL MENU ROUTINE: a page left inside its window, the next page opened 0.3 to 0.9 s later, the flight controller answering - of %d visits, in how many is AN EDIT REFUSED 6 s on\n", N);
        struct Road { int a, b; bool guide; int lo, hi; const char *name; };
        static const Road roads[] = { {PG_GOVCFG, PG_RATES, false, 300, 700, "Governor global -> OK -> menu -> Rates"}, {PG_PID, PG_RATES, false, 300, 1200, "PIDs -> OK -> menu -> Rates"}, {PG_PID, PG_GOV, false, 300, 1200, "PIDs -> OK -> menu -> Governor"},
            {PG_GOVCFG, PG_GOV, false, 300, 700, "Governor global -> OK -> menu -> Governor"}, {PG_RATESADV, PG_PID, false, 300, 1200, "Dynamics -> OK -> menu -> PIDs"}, {PG_PIDADV, PG_RATES, false, 300, 1200, "PID + -> OK -> menu -> Rates"},
            {PG_GOV, PG_RATES, true, 300, 1200, "the GUIDE: Governor -> OK -> the guide -> Rates"}, {PG_GOVCFG, PG_GOV, true, 300, 700, "the GUIDE: Governor global -> OK -> the guide -> Governor"}, {PG_GOV, PG_RATES, true, 20000, 40000, "the GUIDE: Governor (a slow look: 20 to 40 s) -> OK -> the guide -> Rates"},
            {PG_GOVCFG, PG_RATES, true, 300, 700, "the GUIDE: Governor global -> OK -> the guide, A MINUTE THERE -> Rates"},
            {PG_GOVCFG, PG_RATES, false, 1800, 3500, "Governor global, A LOOK OF 1.8 to 3.5 s -> OK -> menu -> Rates ('walking pace')"}, {PG_GOVCFG, PG_GOV, false, 1800, 3500, "Governor global, A LOOK OF 1.8 to 3.5 s -> OK -> menu -> Governor"},
            {PG_PID, PG_RATES, false, 1500, 2300, "PIDs, a look of 1.5 to 2.3 s -> OK -> menu -> Rates"} };
        int k0 = 0;
        for (const Road &r : roads) { int refused = 0, n = 0, wrong = 0;
            for (int k = 0; k < N; ++k) { fresh(); RfHomeBackAnswer = r.guide; if (r.guide) { CurrentView = GUIDEVIEW; runMs(800); }
                openPage(r.a); runMs((uint32_t) rr(r.lo, r.hi)); okPage(r.a); if (CurrentView != (r.guide ? GUIDEVIEW : ROTORFLIGHTVIEW)) continue;
                runMs(k0 == 9 ? 60000 : (uint32_t) rr(300, 900)); ++n; openPage(r.b); runMs(6000);
                boxes = 0; if (r.b == PG_PID) PIDs_Were_edited(); else if (r.b == PG_RATES) RatesWereEdited(); else GOVS_P_Were_Edited(); refused += boxes != 0;
                const int b = Bank - 1, rt = DualRateInUse - 1; bool w = false;
                if (r.b == PG_PID) { for (int i = 0; i < 12; ++i) if (PID_Values[i] != fcPidV[b][i]) w = true; } else if (r.b == PG_RATES) { for (int i = 0; i < 13; ++i) if (Rate_Values[i] != (uint8_t) fcRatesV[rt][i]) w = true; } else { for (int i = 1; i < 16; ++i) if (GovAckPayload[i] != (uint8_t) fcGovV[b][i]) w = true; }
                wrong += w; PIDS_Were_Edited = Rates_Were_Edited = GOVS_PROFILE_Were_Edited = false; }
            printf("   %-74s refused %3d of %3d   (the page's numbers not its own at the end: %d)\n", r.name, refused, n, wrong); ++k0;
            MUSTW(n > N / 2 && refused == 0 && wrong == 0, "m. B18-1 by the real menu routine, '%s': no edit refused, the numbers the page's own (refused %d, wrong %d, of %d)", r.name, refused, wrong, n); }
    }
    // ---------------------------------------------------------------- p. "DISCARD" BEHIND A SAVE WHOSE BANK CHECK IS STILL OUT
    if (want("p")) {
        printf("p. PIDs: AN EDIT, SAVE, AND OK 20 to 120 ms LATER (the check of the bank is out: 'Save now?' is asked) - DISCARD, 0.4 s on. What became of the save?\n");
        const uint32_t boxWas = BOX_MS; BOX_MS = 400; int n = 0, asked = 0, wrote = 0, held60 = 0, soundDone = 0; Stat st;
        for (int k = 0; k < N; ++k) { fresh(); openPage(PG_PID); runMs(3200); const int was = fcPidV[Bank - 1][0]; edit(PG_PID); savePage(PG_PID); runMs((uint32_t) rr(20, 120)); if (!BcStep) continue;
            ++n; saveNowAnswer = false; const int q0 = questions; okPage(PG_PID); asked += questions - q0; if (CurrentView != ROTORFLIGHTVIEW) continue;
            const int s0 = sounds; const long t = untilFree(60000); st.add(t); runMs(3000); wrote += fcPidV[Bank - 1][0] != was; soundDone += sounds > s0; }
        printf("   KNOWN (the released firmware's, B212): the check was out at OK in %d of %d; 'Save now?' asked %d times, Discard answered: THE EDIT WAS WRITTEN INTO THE FLIGHT CONTROLLER ALL THE SAME in %d (no read-back: its page had gone); the bank switch behind it: %s\n", n, N, asked, wrote, st.str(60000).c_str());
        // ... and the governor's GLOBAL page: Save, OK while its read-back runs ('Save now?' - the edited flag stands until the verdict), Discard at once
        { int n2 = 0, q = 0; Stat s2; const int wr = wrMs; wrMs = 900;   // (its write restarts the flight controller: the verdict takes seconds)
          for (int k = 0; k < N; ++k) { fresh(); openPage(PG_GOVCFG); runMs(3200); edit(PG_GOVCFG); savePage(PG_GOVCFG); runMs((uint32_t) rr(300, 900)); if (!RfVerifyPending()) continue; ++n2; saveNowAnswer = false; const int q0 = questions; okPage(PG_GOVCFG); q += questions - q0;
              if (CurrentView != ROTORFLIGHTVIEW) continue; s2.add(untilFree(60000)); }
          printf("   Governor global: Save, OK inside its read-back ('Save now?' asked %d times of %d), Discard 0.4 s on - the menu: %s\n", q, n2, s2.str(60000).c_str()); MUST(n2 > N / 2 && s2.never == 0 && MOST(s2) <= 8500, "p. Governor global: Save, OK inside its read-back, Discard - the bank switch is free at the read-back's own window"); wrMs = wr; }
        BOX_MS = boxWas;
    }
    // ---------------------------------------------------------------- q. THE MENU REFUSED WITH A READ OPEN (the safety put off on the page, then OK): the page stays - does its read still end?
    if (want("q")) {
        printf("q. THE MENU REFUSED WITH A READ OPEN: a page opened, the flight controller slow or silent; 0.3 s on the SAFETY IS PUT OFF, 0.3 s later OK (the menu refuses without a word: a model is connected)\n");
        for (int pg : {PG_PID, PG_GOV, PG_GOVCFG}) for (int dead = 0; dead < 2; ++dead) { int stayed = 0, n = 0, lineLoading = 0, lineNothing = 0, flagUp = 0, whole = 0, blockHeld = 0;
            for (int k = 0; k < N; ++k) { fresh(); if (dead) fcDead = true; else fcMs = 700; openPage(pg); runMs(300); pos[2] = 3; runMs(300); const int v = CurrentView; okPage(pg); fcMs = 25; ++n; stayed += CurrentView == v;
                runMs(7000); const std::string l = fields[pg == PG_GOVCFG ? "t4" : "busy"]; const bool up = fields[pg == PG_GOVCFG ? "vis:t4" : "vis:busy"] == "1";
                lineLoading += up && l.find("Loading") == 0; lineNothing += up && (l.find("nothing came back") != std::string::npos || l.find("only PART") != std::string::npos);
                flagUp += Reading_PIDS_Now || Reading_GOV_Now || Reading_GOV_Config_Now; whole += pg == PG_PID ? PIDS_Loaded : pg == PG_GOV ? GOV_Loaded : 0; blockHeld += BlockBankChanges; pos[2] = 1; }
            printf("   %-16s %-34s the page stayed in %3d of %3d; 7 s on: 'Loading ...' STILL STANDS in %3d, 'nothing came back' stands in %3d, marked whole %3d, the bank switch still held %3d\n", pgName[pg], dead ? "(the flight controller silent)" : "(its set 0.7 s late)", stayed, n, lineLoading, lineNothing, whole, blockHeld);
            MUST(stayed == n && lineLoading == 0 && blockHeld == 0 && flagUp == 0, "q. the menu refused with the %s page's read open: the page stays and its read ends (stayed %d, 'Loading' left %d, held %d, a flag up %d, of %d)", pgName[pg], stayed, lineLoading, blockHeld, flagUp, n);
            if (pg != PG_GOVCFG && E25_OPEN_KNOWN && !dead && whole >= n - 1) { if (whole != n) printf("   OPEN (pre-existing, seed-dependent - the real tree too): q. %s: whole %d of %d\n", pgName[pg], whole, n); }
            else if (pg != PG_GOVCFG) MUST(dead ? (whole == 0 && lineNothing == n) : whole == n, "q. ... %s: marked whole when its set came late (%d), 'nothing came back' when none came (%d), of %d", pgName[pg], whole, lineNothing, n); }
    }
    // ---------------------------------------------------------------- g. PID + and Dynamics with the partner page's own window OVER (3.5 s on PIDs / Rates first)
    if (want("g")) {
        printf("g. PID + AND DYNAMICS, THE PARTNER PAGE OPEN 3.5 s FIRST (its window over): the page opened, OK 100 to 250 ms later - the menu stays up 60 s\n");
        for (int pg : {PG_PIDADV, PG_RATESADV}) { Stat st;
            for (int k = 0; k < N; ++k) { fresh(); if (pg == PG_PIDADV) { StartPIDView(); runMs(3500); StartPIDAdvancedView(); } else { StartRFRatesView(); runMs(3500); StartRatesAdvancedView(); }
                runMs((uint32_t) rr(100, 250)); okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) continue; st.add(untilFree(60000)); }
            printf("   %-16s %s\n", pgName[pg], st.str(60000).c_str());
            MUST((int) st.v.size() + st.never > N / 2, "g. (suite) %s: the row ran (%d of %d)", pgName[pg], (int) st.v.size() + st.never, N);   // e99
            MUST(st.never == 0 && MOST(st) <= 1000, "g. %s (the partner's window over) left before its set: the bank switch is free when the set has come (within 1.0 s - e99: 0.7 s the most measured) - its Hide routine frees it wherever it is called", pgName[pg]); }
        printf("g2. (suite) ... AND THE PARTNER PAGE OPEN ONLY 0.3 to 1.2 s (ITS READ STILL OPEN: its block on the bank switch is handed to this page's read), with a flight controller that answers, and with a silent one\n");
        for (int dead = 0; dead < 2; ++dead) for (int pg : {PG_PIDADV, PG_RATESADV}) { Stat st;
            for (int k = 0; k < N; ++k) { fresh(); if (pg == PG_PIDADV) { StartPIDView(); runMs((uint32_t) rr(300, 1200)); if (dead) fcDead = true; StartPIDAdvancedView(); } else { StartRFRatesView(); runMs((uint32_t) rr(300, 1200)); if (dead) fcDead = true; StartRatesAdvancedView(); }
                runMs(dead ? (uint32_t) rr(500, 2000) : (uint32_t) rr(100, 250)); okPage(pg); if (CurrentView != ROTORFLIGHTVIEW) continue; st.add(untilFree(60000)); }
            printf("   %-16s %-32s %s\n", pgName[pg], dead ? "(the flight controller silent)" : "", st.str(60000).c_str());
            MUST((int) st.v.size() + st.never > N / 2, "g2. (suite) %s (%s): the row ran (%d of %d)", pgName[pg], dead ? "silent" : "answering", (int) st.v.size() + st.never, N);   // e99
            MUST(st.never == 0 && MOST(st) <= 2700, "g2. %s opened inside its partner's read, left early (%s): the bank switch is free at this read's own end", pgName[pg], dead ? "silent" : "answering"); }
    }
    // ---------------------------------------------------------------- s. (suite) THE PARTNER'S BUTTON: PIDs -> "Advanced" (PID +), Rates -> "Advanced" (Dynamics), inside the first page's read
    if (want("s")) {
        printf("s. (suite) THE PARTNER'S BUTTON 0.3 to 1.2 s AFTER THE PAGE OPENED (its read still open; the seventeenth review's road): of %d visits, 6 s on -\n", N);
        for (int dead = 0; dead < 2; ++dead) for (int pg : {PG_PIDADV, PG_RATESADV}) { int n = 0, refused = 0, wrong = 0, takenWrong = 0;
            for (int k = 0; k < N; ++k) { fresh(); if (pg == PG_PIDADV) StartPIDView(); else StartRFRatesView(); runMs((uint32_t) rr(300, 1200)); if (dead) fcDead = true;
                if (pg == PG_PIDADV) StartPIDAdvancedView(); else StartRatesAdvancedView();
                if (CurrentView != (pg == PG_PIDADV ? PIDADVANCEDVIEW : RATESADVANCEDVIEW)) continue;
                runMs(6000); ++n; const int b = Bank - 1, r = DualRateInUse - 1; bool w = false;
                if (pg == PG_PIDADV) { for (int i = 0; i < 26; ++i) if (PID_Advanced_Values[i] != (uint8_t) fcPidAdvV[b][i]) w = true; } else { for (int i = 0; i < 15; ++i) if (Rate_Advanced_Values[i] != (uint8_t) fcAdvV[r][i]) w = true; }
                boxes = 0; if (pg == PG_PIDADV) PIDsAdvancedWereEdited(); else RatesAdvancedWereEdited(); const bool taken = boxes == 0;
                refused += !taken; wrong += w; takenWrong += taken && w; PIDS_Advanced_Were_Edited = Rates_Advanced_Were_Edited = false; }
            const bool known = dead && pg == PG_RATESADV;   // (B212: the Rates' and the Dynamics' blocks have the same four items)
            printf("   %s%-9s %-9s n %3d | an edit refused %3d | the page's numbers not its own block %3d | AN EDIT TAKEN ON THEM %3d\n", known ? "KNOWN (B212: the same four items) " : "", dead ? "NO FRESH:" : "answers:", pgName[pg], n, refused, wrong, takenWrong);
            if (!dead) MUSTW(n > N / 2 && refused == 0 && wrong == 0, "s. %s opened from its partner inside the partner's read, the flight controller answering: its own numbers, no edit refused (refused %d, wrong %d, of %d)", pgName[pg], refused, wrong, n);
            else if (!known) MUSTW(n > N / 2 && takenWrong == 0 && refused == n, "s. %s opened from its partner inside the partner's read, nothing fresh: no edit taken on the partner's bytes (taken %d, refused %d, of %d)", pgName[pg], takenWrong, refused, n); }
    }
    // ---------------------------------------------------------------- r. (suite) THE GOVERNOR GLOBAL PAGE BEHIND THE PIDs / PID + PAGE: KNOWN, the released firmware's (B212)
    if (want("r")) {
        printf("r. (suite) KNOWN (the released firmware's, B212): THE GOVERNOR GLOBAL PAGE counts its own 24 bytes (items 25-30) and ends its read with the 24th - it keeps no mark of BlockItemSeen's.\n   A page left, the menu, Governor global 0.3 to 0.9 s later: of %d visits, in how many do its numbers stand as ANOTHER PAGE'S BYTES 5 s on (its read over, no line, no box)\n", N);
        static const char *srcName[4] = {"PIDs, left 0.3-1.2 s after it opened", "PID +, left 0.3-1.2 s after it opened", "PIDs, an edit saved and CONFIRMED, then OK", "PIDs, open 4 s (its window over), then OK"};
        for (int dead = 0; dead < 2; ++dead) for (int sc = 0; sc < 4; ++sc) { int n = 0, wrongEnd = 0, box = 0;
            for (int k = 0; k < N; ++k) { fresh();
                if (sc == 0) { openPage(PG_PID); runMs((uint32_t) rr(300, 1200)); okPage(PG_PID); }
                else if (sc == 1) { openPage(PG_PIDADV); runMs((uint32_t) rr(300, 1200)); okPage(PG_PIDADV); }
                else if (sc == 2) { openPage(PG_PID); runMs(3200); edit(PG_PID); savePage(PG_PID); const uint64_t e2 = us_ + 6000000ull; while (us_ < e2 && (RfVerifyPending() || BcStep)) loopPass(); runMs((uint32_t) rr(300, 1200)); okPage(PG_PID); }
                else { openPage(PG_PID); runMs(4000); okPage(PG_PID); }
                if (CurrentView != ROTORFLIGHTVIEW) continue;
                runMs((uint32_t) rr(300, 900)); ++n; const int b = Bank - 1; if (dead) fcDead = true; boxes = 0;
                openPage(PG_GOVCFG); runMs(5000);
                bool wrong = false; for (int i = 18; i < 42; ++i) if (GovAckPayload[i] != (uint8_t) fcGovV[b][i]) wrong = true;
                wrongEnd += wrong && CurrentView == RFGOVERNORVIEW_GLOBAL && !Reading_GOV_Config_Now && boxes == 0; box += boxes != 0; }
            printf("   %-9s %-46s n %3d | another page's bytes stand as the governor's global setup, nothing said: %3d   (a box 'Failed to read global' instead: %d)\n", dead ? "NO FRESH:" : "answers:", srcName[sc], n, wrongEnd, box);
            if (sc == 3) MUSTW(n > N / 2 && wrongEnd == 0, "r. the Governor global page behind a PIDs page whose window is over: its own bytes (%d of %d)", wrongEnd, n); }
    }
    // ---------------------------------------------------------------- QD. (suite, e101c test work; review 22 B's scene, review 23 A-3) Save on a bank page, the bank switch moved INSIDE the save's
    // hold, Help before the hold ends, the bank changes UNDER Help, back. The tap and the way back are main.cpp's OWN lines (lifted, above): the page must be read again on the
    // way back - never shown whole with the old bank's block, never that block saved into the new bank. Every bank page, by the radio and the pipe.
    if (want("QD")) {
        const uint32_t boxWas = BOX_MS; BOX_MS = 400;
        static const int pagesD[5] = {PG_PID, PG_PIDADV, PG_GOV, PG_RATESADV, PG_RATES};
        static const char *roadD[2] = {"Help 50-150 ms on, back 1 s on", "Help, back; an edit, Save"};
        auto bank2Has1 = [&](int pg) { switch (pg) { case PG_PID: return fcPidV[1][5] == fcPidV[0][5]; case PG_PIDADV: return fcPidAdvV[1][5] == fcPidAdvV[0][5]; case PG_GOV: return fcGovV[1][5] == fcGovV[0][5];
                                                     case PG_RATESADV: return fcAdvV[1][5] == fcAdvV[0][5]; default: return fcRatesV[1][5] == fcRatesV[0][5]; } };
        auto loaded = [&](int pg) { return pg == PG_PID ? PIDS_Loaded : pg == PG_PIDADV ? PIDS_ADV_Loaded : pg == PG_RATES ? RATES_Loaded : pg == PG_RATESADV ? RATES_ADV_Loaded : GOV_Loaded; };
        auto viewOf = [&](int pg) { return pg == PG_PID ? PIDVIEW : pg == PG_PIDADV ? PIDADVANCEDVIEW : pg == PG_RATES ? RATESVIEW_RF : pg == PG_RATESADV ? RATESADVANCEDVIEW : RFGOVERNORVIEW_PROFILE; };
        auto anyFlagD = [&]() { return Reading_PIDS_Now || Reading_RATES_Now || Reading_RATES_Advanced_Now || Reading_PIDS_Advanced_Now || Reading_GOV_Now; };
        printf("QD. Bank 1. An edit, Save, the write at once. The 'Banks 1 2 3' switch to 2 at 0.6-1.3 s after the save, ON THE PAGE; Help (main.cpp's own HelpWordCame), back (main.cpp's own way back).\n"
               "    A row: trials | Help taken | the save still held the bank switch at the tap | STALE: on bank 2, the page whole, no read asked since the bank changed | after an edit and Save: BANK 2 HOLDS BANK 1's BLOCK\n");
        for (int pi = 0; pi < 5; ++pi) for (int road = 0; road < 2; ++road) { const int pg = pagesD[pi];
            int n = 0, tapped = 0, heldAtTap = 0, stale = 0, wrote = 0;
            for (int k = 0; k < N; ++k) {
                motorPos0 = 1; LinkRatesToBanks = pg == PG_RATESADV || pg == PG_RATES; fresh(); motorPos0 = 3; SavedCurrentView = -1; if (Bank != 1) continue;
                openPage(pg); runMs(3200); edit(pg); landLo = landHi = 0;
                savePage(pg);
                { const uint64_t e = us_ + 2000000ull; while (us_ < e && !(RfVerifyPending() && !BcStep)) loopPass(); }
                if (!(RfVerifyPending() && !BcStep)) { writeLost = false; landLo = landHi = 0; pendOn = false; continue; }
                const uint32_t saveMs = SAVE_MS_OF_TREE; const uint32_t t1 = (uint32_t) rr(600, 1300);
                while ((uint32_t)(millis() - saveMs) < t1) loopPass();
                ++n; pos[4] = 2;
                bool asked = false, bankMoved = false;
                auto step = [&]() { const int b0 = Bank; loopPass(); if (Bank != b0) bankMoved = true; if (bankMoved && anyFlagD()) asked = true; };
                auto run = [&](uint32_t ms) { const uint64_t e = us_ + (uint64_t) ms * 1000ull; while (us_ < e) step(); };
                run((uint32_t) rr(50, 150));
                if (CurrentView == viewOf(pg)) { heldAtTap += RfSaveHoldsBank(); LiftedHelpWordCame();
                    if (CurrentView == HELP_VIEW) { ++tapped; run(1000); liftedHelpBack(); } }
                run(4000);
                stale += Bank == 2 && CurrentView == viewOf(pg) && loaded(pg) && !asked;
                if (road == 1 && CurrentView == viewOf(pg)) { edit(pg); savePage(pg); run(8000); wrote += bank2Has1(pg); }
                writeLost = false; landLo = landHi = 0; pendOn = false; }
            printf("   %-9s %-32s | %3d | Help taken %3d | held at the tap %3d | STALE %3d | BANK 2 = BANK 1's %3d\n", pgName[pg], roadD[road], n, tapped, heldAtTap, stale, wrote);
            MUST(n > N / 2 && tapped == n && heldAtTap > n / 2, "QD. %s, %s: the scene ran - trials %d of %d, Help taken (main.cpp HelpWordCame) %d, the save's hold standing at the tap %d", pgName[pg], roadD[road], n, N, tapped, heldAtTap);
            MUST(stale == 0 && wrote == 0, "QD. %s, %s: STALE %d of %d, bank 1's block saved into bank 2: %d (the bank changed under Help; main.cpp's own tap + way back must read the page again)", pgName[pg], roadD[road], stale, n, wrote); }
        LinkRatesToBanks = false; landLo = landHi = 0; BOX_MS = boxWas; motorPos0 = 3; writeLost = false;
    }
    // ---------------------------------------------------------------- f. what is MINE in this: the times. The same road (PIDs, OK before its set) against the once-a-second round's own time
    if (want("f")) {
        printf("f. PIDs OPENED, OK BEFORE ITS SET - against what the once-a-second round costs (mine; the board's own is a millisecond or two on the menu: no card, no clock, one voltage read)\n");
        static const int hk[] = {200, 800, 1500, 3000, 6000, 10000, 15000, 22000, 30000, 45000, 70000};
        for (int h : hk) { HK_US = h; Stat st; int by6 = 0, by30 = 0;
            for (int k = 0; k < N; ++k) { fresh(); openPage(PG_PID); runMs((uint32_t) rr(100, 250)); okPage(PG_PID); const long t = untilFree(180000); st.add(t); by6 += t >= 0 && t < 6000; by30 += t >= 0 && t < 30000; }
            printf("   the round takes %5.1f ms: freed within 6 s in %3d of %3d, within 30 s in %3d; %s\n", h / 1000.0, by6, N, by30, st.str(180000).c_str()); }
        HK_US = HKVAL;
        printf("   ... and against a loop pass and a packet twice as slow / half as slow (the round at %d us):\n", HK_US);
        static const int var[4][4] = {{15, 45, 200, 350}, {30, 90, 400, 700}, {60, 180, 800, 1400}, {120, 400, 900, 1500}};
        for (auto &v : var) { PASS_LO = v[0]; PASS_HI = v[1]; RADIO_LO = v[2]; RADIO_HI = v[3]; Stat st; int by6 = 0;
            for (int k = 0; k < N; ++k) { fresh(); openPage(PG_PID); runMs((uint32_t) rr(100, 250)); okPage(PG_PID); const long t = untilFree(180000); st.add(t); by6 += t >= 0 && t < 6000; }
            printf("   a pass %3d-%3d us, a packet %4d-%4d us: freed within 6 s in %3d of %3d; %s\n", v[0], v[1], v[2], v[3], by6, N, st.str(180000).c_str()); }
        PASS_LO = 30; PASS_HI = 90; RADIO_LO = 400; RADIO_HI = 700;
    }
    MUST(!HAS_RULE || twoFlags == 0, "never two reading flags up at once (%ld passes of the loop found two)", twoFlags);
#if G5_E99E
    printf("   (e99e G4/G5) a read-back not its own read's, held past its save's 4.1 s: %ld episodes (the oldest %.3f s); pending with its flag down: %ld passes\n", vfDownLong, vfDownMost / 1e6, vfPendFlagDown);
    MUST(vfDownLong == 0 && vfPendFlagDown == 0, "e99e (G4/G5): every read-back whose own read is not open is let go by 4.1 s after its save (%ld episodes; the oldest %.3f s), and none is pending with its flag down (%ld)", vfDownLong, vfDownMost / 1e6, vfPendFlagDown);
#else
    printf("   (e99d G5) a read-back pending with its kind's flag down: the longest %.3f s; over 0.1 s in %ld episodes\n", vfDownMost / 1e6, vfDownLong);
    MUST(vfDownLong == 0, "e99d (G5): no read-back stays pending more than 100 ms after its kind's flag went down (%ld episodes; the longest %.3f s)", vfDownLong, vfDownMost / 1e6);
#endif
    printf("   (the radio told %ld items of a block)\n", radioItemsTold);
    if (G5_E99E) { printf("   (round 25, e99e) a bank page's save followed at the motor switch's call, its read stopped there: %ld\n", followDropped);
        MUST(followDropped == 0, "e99e: a bank page's save being followed is not stopped by the motor switch (Motor_sign.h RfVerifyFollows) - stopped %ld times", followDropped);
        printf("   (round 27, e99g) a bank page's save behind a FRESH ask of its page at the motor switch's call, that read's flag kept up by the call: %ld\n", freshKept);
        MUST(freshKept == 0, "e99g: at the motor switch only the read the read-back itself asked is followed - a fresh ask of the page behind a save is stopped there (six flags down) - kept up %ld times", freshKept); }
    MUST(modelReads == 0 && PreviousModelNumber == ModelNumber, "e100b: no model read by the motor switch off the Models page (%ld)", modelReads);
    printf("test_bankblock: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
GOVCFG_MENU_MOST0, GOVCFG_MENU_MOST1 = 3700, 1000   # (suite) e99, part w: the Governor global save left by OK - the unchanged tree (the real tree, e99 out) measured 3.38 s and 0.74 s at the most (4 x 80 trials), with a margin
UT = src('include/Utilities.h'); _hs = lift(UT, 'void HideScreenAgain()'); _i = _hs.index('if (RfPageJobRuns()') + 3; _d = 0
for _k in range(_i, len(_hs)):
    if _hs[_k] == '(': _d += 1
    elif _hs[_k] == ')':
        _d -= 1
        if _d == 0: break
BLANK_GATE = _hs[_i:_k + 1]   # (suite, e99e test work) the condition that refuses the blank ("not over a page's job, its watch - e99e: nor a read-back")
E25_OPEN = False   # (suite) the e99e test work, 18 Nov 2026: True only in the break-it base e99work/W_open25 - part y's 'a write inside the save's 4 s' rows (this round's finding) and part q's one pre-existing trial printed as OPEN there
# (round 26, e99f: part y's 'inside the save's 4 s' rows are ASSERTED in every base now - E25_OPEN keeps only part q's one pre-existing trial)
E24_OPEN = False   # (suite) the e99d test work, 18 Nov 2026: True only in the break-it base e99work/W_open24 - the two rows that fail RIGHTLY on W (z3: a "reading back" line left up after the wake from a blank screen; v: G6's flag left up behind the Governor global page) printed as OPEN there, narrowly
E23_OPEN = False   # (suite) the e99bc test work, 17 Nov 2026: True only in the break-it base e99work/W_open23 - the rows that fail RIGHTLY on W (radio words at the motor's call, a read-back left pending behind page B, one left from long ago holding a later visit) printed as OPEN there, narrowly
E99_OPEN = False   # (suite) e99work, 17 Nov: the rows e99 does NOT close (the e99 test work, 17 Nov 2026) are ASSERTED - the test fails on them, rightly. True only in the break-it rounds' own copy (mut6/mut22.py, MUTSRC: a base that passes)
prog = prog.replace('SAVE_MS_OF_TREE', 'VfArmMs' if 'VfArmMs' in src('include/RF_Verify.h') else 'VfReadStart')   # (round 26: part X in trees before e99e - the read-back's own start)
prog = prog.replace('AFRESH_READING', '(VfAfresh != VK_NONE && VfReading(VfAfresh))' if 'VfAfresh' in src('include/RF_Verify.h') else 'false')   # (round 27: part M)
prog = prog.replace('HAS_AFRESH_NOTE', 'VfAfresh != VK_NONE' if 'VfAfresh' in src('include/RF_Verify.h') else 'false')   # (round 26: part X in trees before e99e)
prog = prog.replace('G5_E99E', '1' if 'VfArmMs' in src('include/RF_Verify.h') else '0').replace('BLANK_GATE_COND', BLANK_GATE)
prog = prog.replace('NTRIALS', str(N)).replace('SEEDVAL', str(SEED)).replace('HKVAL', str(HK)).replace('PARTS', '"%s"' % PART).replace('SHOWIT', '1' if SHOW else '0').replace('OTHER_READS_OVER_LINE', OTHER_READS_OVER).replace('ASSERT_ON', '1' if ASSERT else '0').replace('HAS_RULE', '1' if OTHER_READS_OVER else '0').replace('E99_OPEN_KNOWN', '1' if E99_OPEN else '0').replace('E23_OPEN_KNOWN', '1' if E23_OPEN else '0').replace('E24_OPEN_KNOWN', '1' if E24_OPEN else '0').replace('E25_OPEN_KNOWN', '1' if E25_OPEN else '0').replace('GOVCFG_MENU_MOST0', str(GOVCFG_MENU_MOST0)).replace('GOVCFG_MENU_MOST1', str(GOVCFG_MENU_MOST1)).replace('TREE_NAME', '"%s"' % {'now': 'THE TREE UNDER REVIEW', 'r18': 'AS THE EIGHTEENTH REVIEW SAW IT', 'head': 'GIT HEAD (B210)'}.get(tree, tree))
# (suite, e101c test work; review 23 A-3) PART QD: THE HELP TAP AND THE WAY BACK, LIFTED FROM main.cpp - not a hand copy. Comments go first (// and /* */,
# strings kept), so a copy of a line left inside a comment is no line. Not found, or not as one place: the test FAILS here (no part runs).
def _nocomments(t):
    out = []; i = 0; n = len(t)
    while i < n:
        ch = t[i]
        if ch in '"\'':
            j = i + 1
            while j < n and t[j] != ch:
                j += 2 if t[j] == '\\' else 1
            out.append(t[i:j + 1]); i = j + 1
        elif t.startswith('//', i):
            j = t.find('\n', i); i = n if j < 0 else j
        elif t.startswith('/*', i):
            j = t.find('*/', i + 2)
            if j < 0: raise SystemExit('test_bankblock: FAILED - main.cpp: a /* comment without its end')
            out.append('\n' * t.count('\n', i, j)); i = j + 2
        else:
            out.append(ch); i += 1
    return ''.join(out)
def _qd_fail(why):
    print('FAIL (part QD, lifting from main.cpp): ' + why); print('test_bankblock: FAILED'); sys.exit(1)
_mn = _nocomments(MAIN)
if len(re.findall(r'\bvoid\s+HelpWordCame\s*\(\s*\)\s*\{', _mn)) != 1: _qd_fail('the routine "void HelpWordCame()" (the Help tap) is not found, or not once')
_tap = lift(_mn, 'void HelpWordCame()', must=False)
if not _tap or 'CurrentView = HELP_VIEW;' not in _tap: _qd_fail('HelpWordCame: no "CurrentView = HELP_VIEW;" in it')
_tap = _tap.replace('void HelpWordCame()', 'static void LiftedHelpWordCame()', 1)
_wb = [m.start() for m in re.finditer(r'\bif\s*\(\s*HelpTookRead\b', _mn)]
if len(_wb) != 1: _qd_fail('the way back from Help ("if (HelpTookRead ...) { ... }") is found %d times, not once' % len(_wb))
_i = _mn.index('(', _wb[0]); _dp = 0
for _k in range(_i, len(_mn)):
    _dp += {'(': 1, ')': -1}.get(_mn[_k], 0)
    if _dp == 0: break
_j = _k + 1
while _mn[_j] in ' \t\r\n': _j += 1
if _mn[_j] != '{': _qd_fail('the way back: "if (HelpTookRead ...)" is not followed by a block { ... }')
_dp = 0
for _k in range(_j, len(_mn)):
    _dp += {'{': 1, '}': -1}.get(_mn[_k], 0)
    if _dp == 0: break
_back = _mn[_wb[0]:_k + 1]
_views = re.findall(r'CurrentView\s*==\s*([A-Z_0-9]+)', _back)
print('(part QD) the Help tap = main.cpp HelpWordCame, %d lines; the way back = main.cpp\'s, %d lines, its pages: %s' % (_tap.count('\n'), _back.count('\n') + 1, ' '.join(_views) or 'NONE'))
prog = prog.replace('HELP_LIFTED_CODE', 'static char TextIn[64]; static int SavedCurrentView = -1;   // (what main.cpp HelpWordCame names that this harness has not got)\n'
                    'static bool HelpNameFrom(char *) { return false; } static void ReadRXOptionsView() {} static void SendHelp() { SendCommand((char *)"page HelpView"); }\n'
                    + _tap + '\nstatic void liftedHelpBack() { SendCommand((char *)"page back"); CurrentView = SavedCurrentView;\n' + _back + '\n}\n', 1)
d = tempfile.mkdtemp(); atexit.register(shutil.rmtree, d, True)
src_bad = []
if ASSERT and not os.environ.get('LDRC_RUNS_ONLY'):   # (suite) THE RULE, BY READING - a tree that has it (LDRC_RUNS_ONLY, the scenes' own switch: the runs alone - what do THEY notice?)
    def nc(t): return re.sub(r'//[^\n]*', '', t)
    files = {f: nc(src('include/' + f)) for f in ('RF_PIDs.h', 'RF_PID_Advanced.h', 'RF_Rates.h', 'RF_Rates_Advanced.h', 'RF_Governor_Profile.h', 'RF_Governor_Global.h', 'RF_RotorFlight.h', 'RF_Save_Restore.h', 'Motor_sign.h', 'Parameters.h', 'RF_Backup.h', 'RF_Verify.h')}
    allsrc = {f: nc(src('include/' + f)) for f in sorted(os.listdir(os.path.join(TC, 'include'))) if f.endswith('.h')}; allsrc['main.cpp'] = nc(MAIN)
    FLAGS = ('Reading_PIDS_Now', 'Reading_PIDS_Advanced_Now', 'Reading_RATES_Now', 'Reading_RATES_Advanced_Now', 'Reading_GOV_Now', 'Reading_GOV_Config_Now')
    raised = {}
    for f, t in allsrc.items():
        for m in re.finditer(r'(\S[^\n;]*;)?\s*\b(Reading_\w+_Now) = true;', t):
            raised.setdefault(f, []).append((m.group(2), (m.group(1) or '').strip()))
    want_places = {'RF_PIDs.h': ['Reading_PIDS_Now'], 'RF_PID_Advanced.h': ['Reading_PIDS_Advanced_Now'], 'RF_Rates.h': ['Reading_RATES_Now'], 'RF_Rates_Advanced.h': ['Reading_RATES_Advanced_Now'],
                   'RF_Governor_Profile.h': ['Reading_GOV_Now'], 'RF_Governor_Global.h': ['Reading_GOV_Config_Now', 'Reading_GOV_Config_Now']}
    for f, flags in want_places.items():
        got = raised.get(f, [])
        if [g[0] for g in got] != flags or any(g[1] != 'RfOtherReadsOver();' for g in got):
            src_bad.append('%s: its flag is raised in %d place(s), each right behind "RfOtherReadsOver();" (a page\'s read is over when another page\'s begins: ONE read at a time) - found %r' % (f, len(flags), got))
    others = sorted(f for f in raised if f not in want_places)
    if others != ['RF_Save_Restore.h'] or len(re.findall(r'(?<!void )\bSave_SOME_RF_Parameters\(', '\n'.join(allsrc.values()))) != 0 or any(g[0] not in FLAGS for g in raised.get('RF_Save_Restore.h', [])) \
            or 'void Save_SOME_RF_Parameters(' not in allsrc['RF_Save_Restore.h'] or allsrc['RF_Save_Restore.h'].index('void Save_SOME_RF_Parameters(') > allsrc['RF_Save_Restore.h'].index('Reading_PIDS_Now = true;'):
        src_bad.append('no other file raises a reading flag - but the old sweep (RF_Save_Restore.h Save_SOME_RF_Parameters), which nothing calls: its name stands only at its own head and in its prototype (found: %r)' % others)
    one = re.search(r'^inline void RfOtherReadsOver\(\) \{([^\n]*)\}', nc(D1), re.M)
    if not one or sorted(re.findall(r'Reading_\w+_Now', one.group(1))) != sorted(FLAGS) or not one.group(1).strip().endswith('= false;'):
        src_bad.append('1Definitions.h RfOtherReadsOver: all six flags, down')
    menu = lift(files['RF_RotorFlight.h'], 'FLASHMEM void RotorFlightStart()')
    if 'Reading_' in menu or 'RfOtherReadsOver' in menu or 'RfReadsOver' in files['RF_RotorFlight.h'] or 'BlockBankChanges' in menu:
        src_bad.append('RF_RotorFlight.h RotorFlightStart: the menu touches no reading flag and not the bank switch\'s block (a flag left up ends by itself, and its end frees the block)')
    for f, h in (('RF_PIDs.h', 'FLASHMEM void HidePIDMsg()'), ('RF_PID_Advanced.h', 'FLASHMEM void HidePID_Advanced_Msg()'), ('RF_Rates.h', 'FLASHMEM void HideRATESMsg()'), ('RF_Rates_Advanced.h', 'FLASHMEM void Hide_Advanced_Rates_Msg()'),
                 ('RF_Governor_Profile.h', 'FLASHMEM void HideGOVMsg()'), ('RF_Governor_Global.h', 'FLASHMEM void HideGOVConfigMsg()')):
        body = lift(files[f], h); depth = 0; ok = False
        for line in body.split('\n')[1:]:
            if 'BlockBankChanges = false;' in line and depth == 1: ok = True
            depth += line.count('{') - line.count('}')
        if not ok: src_bad.append('%s %s: "BlockBankChanges = false;" outside every condition - the end of a read frees the bank switch on whatever page it finds (ALWAYS clear)' % (f, h.split()[-1]))
    trn = nc(TR)
    if len(re.findall(r'0x3BF', trn)) != 1 or 'static uint16_t BlockWant()' not in trn or len(re.findall(r'\bBlockWant\(\)', trn)) != 3 \
            or not re.search(r'const uint16_t want = BlockWant\(\);\s*if \(want && item != 31 && !\(want & \(uint16_t\)\(1 << \(item - 25\)\)\)\) \{ BlockNotMine\(\); return; \}', trn) \
            or not re.search(r'if \(!BlockTelling && !\(BlockSeen & BLOCK_ONCE\)\) \{ BlockSeen = BLOCK_ONCE; return; \}', trn) \
            or not re.search(r'if \(told && told != want\)\s*\{\s*if \(told & ~want\)\s*BlockNotMine\(\);\s*return;\s*\}', trn):
        src_bad.append('transceiver.h: the blocks\' item lists stand ONCE (BlockWant), for the item\'s rule and the telling\'s; an item the page\'s block has not got -> BlockNotMine; by radio whole twice (BLOCK_ONCE); a telling taken only when it holds exactly the page\'s items')
    # (e101b; the twenty-second review, B) Help tapped while a bank page's save holds the bank switch counts as a read taken: the bank changes under Help, the page is read again on the way back
    if not re.search(r'HelpTookRead = Reading_PIDS_Now \|\|[^;]*;\s*if \(RfSaveHoldsBank\(\)\)\s*HelpTookRead = true;\s*CurrentView = HELP_VIEW;', nc(MAIN)):
        src_bad.append('main.cpp, the Help tap: "if (RfSaveHoldsBank()) HelpTookRead = true;" between the reading flags\' line and CurrentView = HELP_VIEW')
    for b in src_bad: print('FAIL (by reading): ' + b)
    print('test_bankblock (by reading): 7 checks, %d failures' % len(src_bad))
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-O1', '-w', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:12000]); sys.exit('test_bankblock: DID NOT COMPILE')
XARGS = [arg('--loss', '0'), '1' if '--send31' in sys.argv else '0', arg('--pace', '0'), arg('--seed', '0')]   # (suite) e99: reviewer A's switches; a seed of the run's own
if '--part' in sys.argv or not ASSERT:   # (one run, as asked)
    sys.exit(subprocess.run([os.path.join(d, 't'), PART, str(N), '0' if '--noradio' in sys.argv else '1', '0' if '--nopipe' in sys.argv else '1'] + XARGS).returncode | (1 if src_bad else 0))
# (suite) no part named: the suite's run - every part but the sweep of my own times (f), by both carriers; then the parts about WHOSE BLOCK IT IS by
# the radio alone and by the Bluetooth pipe alone (as reviewer B ran it)
rc = 1 if src_bad else 0
# (suite) e99: the runs side by side; part h also at the buddy's 5 ms pace and with three seeds (SEED, SEED+1000, SEED+2000), parts h and w also with
# 3 in 100 acknowledgements lost (there the "whose block" rows are KNOWN rows)
NH = arg('--nh', str(max(20, N // 2)))
RUNS = [('1', '1', 'a,b,c,d,e,g,i,j,k,l,m,n,p,q,r,s,v,w,x', str(N), ['0', '0', '0', '0']), ('1', '0', 'a,g,j,k,l,m,s', str(N), ['0', '0', '0', '0']), ('0', '1', 'a,c,g,j,k,l,m,s', str(N), ['0', '0', '0', '0'])] \
     + [('1', '1', 'h', NH, ['0', '0', pace, str(SEED + 1000 * i)]) for pace in ('2', '5') for i in range(3)] + [('1', '1', 'h,w,j,n,v', NH, ['3', '0', '0', str(SEED + 7)])] \
     + [('1', '1', 'u,z', NH, ['0', '0', '0', '0']), ('1', '1', 'x', NH, ['0', '0', '5', str(SEED + 3)]), ('1', '1', 'x,z', NH, ['3', '0', '0', str(SEED + 11)]), ('1', '1', 'y', str(max(20, N // 3)), ['0', '0', '0', str(SEED + 5)])] \
     + [('1', '1', 't0', '1', ['0', '0', '0', '0']), ('1', '1', 't1', '1', ['0', '0', '0', '0']), ('1', '1', 'X', NH, ['0', '0', '0', str(SEED + 13)]), ('1', '1', 'QD', str(max(20, N // 3)), ['0', '0', '0', str(SEED + 17)])]   # (e101c test work: part QD, the Help tap and the way back lifted from main.cpp)   # (round 26, e99f test work: the 4 s grid's roads 0 and 1 - the whole grid by name, --part t; part X)   # (suite, e99d test work: parts u, z; part x at the 5 ms pace and at 3 in 100 lost)
procs = [subprocess.Popen([os.path.join(d, 't'), parts, n_, radio, pipe] + xa, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for radio, pipe, parts, n_, xa in RUNS]
for (radio, pipe, parts, n_, xa), p in zip(RUNS, procs):
    o, _ = p.communicate()
    out = o.split('\n')
    if xa != ['0', '0', '0', '0']: print('(part %s, %s trials a row, seed %s, a packet every %s ms, acknowledgements lost: %s in 100)' % (parts, n_, xa[3], xa[2] if xa[2] != '0' else '2', xa[0]))
    print('\n'.join(l[:230] for l in out if l.startswith('(the block') or 'FAIL' in l or ('KNOWN' in l and 'left \\ opened' not in l) or l.startswith('test_bankblock:') or l.startswith('   OPEN') or l.startswith('   DECLARED') or "stand as the governor's global setup" in l)[:9000])
    rc |= p.returncode
print('test_bankblock: ' + ('FAILED' if rc else 'all three runs passed'))
sys.exit(rc)
