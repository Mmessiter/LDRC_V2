#!/usr/bin/env python3
"""THE SET CAME WHOLE, OR NOTHING IS SAVED - the Advanced rates and the Advanced PIDs pages (B211, 16 Nov 2026; released code had it).
The PIDs and the Governor pages have the rule since B40 and B41; the Rates, Advanced rates and Advanced PIDs pages had none: a read whose window
ended with nothing, or with a part, took the "Loading ..." away over the numbers of the set BEFORE (another rate's, another bank's) - and one edit
and Save sent those into the flight controller's new set.
Here the REAL routines of RF_Rates_Advanced.h and RF_PID_Advanced.h (the page's read, its copy without the model, its edit, its Save) and
RF_PIDs.h's RfBlockNotLoaded (the box) are run. The Rates page itself: dev/test_rates. The flag set by the whole set, and by nothing less:
dev/test_pipe (transceiver.h BlockItemSeen)."""
import os, re, subprocess, sys, tempfile, shutil, atexit
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
D1 = src('1Definitions.h'); RA = src('RF_Rates_Advanced.h'); PA = src('RF_PID_Advanced.h'); PD = src('RF_PIDs.h'); KP = src('RF_Kept.h')
def define(n): return re.search(r'^#define %s[ \t]+(\S+)' % n, D1, re.M).group(0)
prog = r'''
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
#define FLASHMEM
#define Gray 1
#define WHAHWHAHMSG 1
#define BEEPMIDDLE 2
''' + '\n'.join(define(n) for n in ('MSP_WAIT_TIME', 'SEND_RATES_ADVANCED_VALUES', 'SEND_PID_ADVANCED_VALUES', 'RATESADVANCEDVIEW', 'PIDADVANCEDVIEW', 'MAX_RATES_ADVANCED_BYTES', 'MAX_PIDS_ADVANCED_BYTES')) + '\n' \
  + re.search(r'enum : uint8_t \{ KEPT_PIDS[^\n]*', KP).group(0) + r'''
static int CurrentView = 0; static uint8_t Bank = 1, DualRateInUse = 1, PreviousBank = 1;
static bool live = true; static bool RfLive() { return live; }
static bool BlockBankChanges = false, Rates_Advanced_Were_Edited = false, PIDS_Advanced_Were_Edited = false, Rates_Were_Edited = false, PIDS_Were_Edited = false;
static bool RATES_ADV_Loaded = false, PIDS_ADV_Loaded = false, Reading_RATES_Advanced_Now = false, Reading_PIDS_Advanced_Now = false;
static bool Reading_RATES_Now = false, Reading_PIDS_Now = false;
static bool Reading_GOV_Now = false, Reading_GOV_Config_Now = false;   // (the nineteenth review: the rule names all six)
''' + re.search(r'^inline void RfOtherReadsOver\(\)[^\n]*', open(os.path.join(ROOT, 'TransmitterCode', 'include', '1Definitions.h'), encoding='utf-8').read(), re.M).group(0) + r'''
//   // (the pages these two are opened FROM: their read is over with their page - the seventeenth review; dev/test_ratesflag, dev/test_pidsflag run the whole road)
static uint32_t Rates_Advanced_Send_Duration = 0, RATES_Advanced_Start_Time = 0, PID_Advanced_Send_Duration = 0, PID_Advanced_Start_Time = 0;
static uint32_t now_ = 1000; static uint32_t millis() { return now_; }
static std::vector<int> queued; static void AddParameterstoQueue(int id) { queued.push_back(id); }
static std::vector<std::string> cmds; static void SendCommand(char *c) { cmds.push_back(c); }
static int texts = 0, values = 0; static void SendText(char *, char *) { ++texts; } static void SendValue(char *, int) { ++values; }
static int boxes = 0, sounds = 0; static std::string lastBox, lastBoxPage; static void MsgBox(char *p, char *m) { ++boxes; lastBox = m; lastBoxPage = p; }
static void PlaySound(int) { ++sounds; }
static char *Str(char *s, int n, int) { sprintf(s, "%d", n); return s; }
static bool keptAnswer = true; static bool KeptCopy(uint8_t, uint8_t) { return keptAnswer; } static const char *KeptNoneText(uint8_t) { return "No copy kept on the card"; }
static uint8_t Saved_Rate_Advanced_Values[MAX_RATES_ADVANCED_BYTES][6], Saved_PID_Advanced_Values[MAX_PIDS_ADVANCED_BYTES][6];
static char RatesAWindows[15][5], PID_Advanced_Labels[26][4], BankNames[8][16]; static uint8_t BanksInUse[6];
static int hidesR = 0, msgsR = 0, hidesP = 0, msgsP = 0;
static void Hide_Advanced_Rates_Msg() { ++hidesR; } static void RatesAdvancedMsg(const char *, uint16_t) { ++msgsR; }
static void HidePID_Advanced_Msg() { ++hidesP; } static void PIDAdvancedMsg(const char *, uint16_t) { ++msgsP; }
static int keptR = 0, keptP = 0; static void SaveLocalRatesAdvancedBank() { ++keptR; } static void SaveToLocalABank() { ++keptP; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static void DelayWithDog(int) {} static void RfGatherStart() {}
static int gathers = 0; static void ReadRatesAdvanced() { ++gathers; } static void ReadEditedPIDAdvancedValues() { ++gathers; }
static bool RfFieldsMissed(const char *) { return false; }
static int bankChecks = 0; static void RatesAdvQueueWrite() {} static void PidAdvQueueWrite() {}
static void BankCheck(bool, int, void (*)(), const char *) { ++bankChecks; }
''' + lift(PD, 'FLASHMEM bool RfBlockNotLoaded(bool loaded, const char *page, const char *what)') \
    + lift(RA, 'FLASHMEM void RatesAdvancedWereEdited()') + lift(RA, 'FLASHMEM void ShowLocalRatesAdvancedBank()') + lift(RA, 'FLASHMEM static void RatesAdvAskValues()') \
    + lift(RA, 'FLASHMEM void ShowRatesAdvancedBank()') + lift(RA, 'FLASHMEM void SendEditedRatesAdvanced()') \
    + lift(PA, 'FLASHMEM void PIDsAdvancedWereEdited()') + lift(PA, 'FLASHMEM void ShowLocalPIDsAdvancedBank()') + lift(PA, 'FLASHMEM static void PidAdvAskValues()') \
    + lift(PA, 'FLASHMEM void ShowPIDAdvancedBank()') + lift(PA, 'FLASHMEM void SendEditedPID_Advanced()') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
struct PageUnderTest
{
    const char *name, *pageWord, *what; int view, ask;
    bool *loaded, *reading, *edited; int *kept;
    void (*show)(); void (*showLocal)(); void (*typed)(); void (*save)();
};
static bool has(const char *c) { for (auto &x : cmds) if (x == c) return true; return false; }
int main()
{
    for (int i = 0; i < 8; ++i) snprintf(BankNames[i], sizeof BankNames[i], "Bank %d", i); for (int i = 0; i < 6; ++i) BanksInUse[i] = (uint8_t) i;
    const PageUnderTest pages[] = {
        { "Advanced rates", "page Rates_A_View", "advanced rates", RATESADVANCEDVIEW, SEND_RATES_ADVANCED_VALUES, &RATES_ADV_Loaded, &Reading_RATES_Advanced_Now, &Rates_Advanced_Were_Edited, &keptR,
          ShowRatesAdvancedBank, ShowLocalRatesAdvancedBank, RatesAdvancedWereEdited, SendEditedRatesAdvanced },
        { "Advanced PIDs", "page PID_A_View", "advanced PIDs", PIDADVANCEDVIEW, SEND_PID_ADVANCED_VALUES, &PIDS_ADV_Loaded, &Reading_PIDS_Advanced_Now, &PIDS_Advanced_Were_Edited, &keptP,
          ShowPIDAdvancedBank, ShowLocalPIDsAdvancedBank, PIDsAdvancedWereEdited, SendEditedPID_Advanced } };
    for (const PageUnderTest &p : pages)
    {
        // 1. the page's read begins (the page opened, a bank or rate switch moved, the model came): NOTHING IS WHOLE until the set has come
        live = true; CurrentView = p.view; *p.loaded = true; *p.reading = false; *p.edited = false; queued.clear(); cmds.clear(); boxes = 0;
        Reading_RATES_Now = Reading_PIDS_Now = true;                                    // (the page it was opened from is still inside its read's two and a half seconds)
        p.show();
        CHECK(!*(p.view == RATESADVANCEDVIEW ? &Reading_RATES_Now : &Reading_PIDS_Now)); Reading_RATES_Now = Reading_PIDS_Now = false;   // ... that read is over with its page
        CHECK(!*p.loaded && *p.reading && queued.size() == 1 && queued[0] == p.ask && BlockBankChanges && boxes == 0);
        // 2. the window ends with nothing, or a part (transceiver.h Hide_msg_if_needed takes the message away: the numbers of the set BEFORE stand there)
        *p.reading = false; BlockBankChanges = false;
        boxes = sounds = 0; cmds.clear(); p.typed();                                    // he types a number: no Save button - and the box says why
        CHECK(boxes == 1 && sounds == 1 && lastBoxPage == p.pageWord && !*p.edited && !has("vis b3,1"));
        CHECK(lastBox.find(std::string("The ") + p.what + " did not all come") == 0 && lastBox.find("nothing can be\r\nsaved") != std::string::npos);
        // 3. Save, should it be reached all the same: nothing asked of the page, nothing sent - with the model, and without it nothing KEPT as its copy
        *p.edited = true; boxes = 0; gathers = bankChecks = *p.kept = 0; queued.clear(); p.save();
        CHECK(boxes == 1 && gathers == 0 && bankChecks == 0 && queued.empty() && *p.kept == 0 && !*p.reading);
        live = false; boxes = 0; p.save(); CHECK(boxes == 1 && *p.kept == 0 && gathers == 0);
        fprintf(stdout, "%s, the set never came: an edit and Save each get the box \"%.*s ...\", nothing is sent, nothing kept\n", p.name, (int) lastBox.find('\r'), lastBox.c_str());
        // 4. the set came whole (transceiver.h BlockItemSeen sets the flag: dev/test_pipe): edits and Save as ever
        live = true; *p.loaded = true; *p.edited = false; boxes = 0; cmds.clear(); p.typed();
        CHECK(boxes == 0 && *p.edited && has("vis b3,1"));
        gathers = bankChecks = 0; p.save(); CHECK(boxes == 0 && gathers == 1 && bankChecks == 1 && *p.kept == 0);
        // 5. WITHOUT the model the page shows the model file's own copy - whole by itself (a copy kept, or none: he may type one and keep it, as ever)
        for (int kept = 0; kept < 2; ++kept)
        {
            live = false; keptAnswer = kept; *p.loaded = false; *p.reading = false; *p.edited = false; queued.clear(); p.show();
            CHECK(*p.loaded && !*p.reading && queued.empty());
            boxes = 0; cmds.clear(); p.typed(); CHECK(boxes == 0 && *p.edited && has("vis b3,1"));
            *p.kept = 0; p.save(); CHECK(boxes == 0 && *p.kept == 1 && bankChecks == 1);   // (kept as the model file's copy; nothing more asked of the flight controller)
        }
        *p.loaded = false; p.showLocal(); CHECK(*p.loaded);
        // 6. another page up: the page's read does nothing, and says nothing whole
        live = true; CurrentView = 0; *p.loaded = false; *p.reading = false; queued.clear(); p.show(); CHECK(!*p.loaded && !*p.reading && queued.empty());
    }
    printf("test_setwhole: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); atexit.register(shutil.rmtree, d, True)
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-fsanitize=address,undefined', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit('test_setwhole: DID NOT COMPILE')
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
