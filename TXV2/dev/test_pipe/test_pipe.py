#!/usr/bin/env python3
"""Host test of the Teensy's pipe parsing (B41): TelemetryFromPipe() as it is in include/transceiver.h, compiled on the
Mac with a fake ack payload and a counting parser round it, and SendParameterByPipe()'s wording checked by eye of code.
   python3 dev/test_pipe/test_pipe.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'transceiver.h')).read()
m = re.search(r'void TelemetryFromPipe\(const char \*list\)\n\{.*?\n\}\n', src, re.S)
assert m, 'TelemetryFromPipe not found'
# B71: the words wait on a stack and go out last in first out (the trigger part of a write LAST): PipeFlush and
# AddParameterstoQueue as they are in include/Parameters.h
psrc = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'Parameters.h')).read()
mq = re.search(r'static const uint8_t PIPE_STACK_MAX = 8;.*?\nbool RfLive\(\) \{[^\n]*\n', psrc, re.S)
assert mq, 'PipeFlush not found'
ma = re.search(r'void AddParameterstoQueue\(uint8_t ID\)[^\n]*\n\{.*?\n\}\n', psrc, re.S)
assert ma, 'AddParameterstoQueue not found'
prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cctype>
#include <cstdint>
#include <string>
#include <vector>
struct Payload { uint8_t Ack_Payload_byte[32]; } AckPayload;
static int seen = 0; static uint8_t last[5];
void ParseTelemetryItem() { ++seen; for (int i = 0; i < 5; ++i) last[i] = AckPayload.Ack_Payload_byte[i]; }
#define FASTRUN
static bool LedWasGreen = false, ModelMatched = true, BoundFlag = true, BakOfflineNow = false;
#define SEND_PID_VALUES 9
#define SEND_RATES_VALUES 12
#define SEND_RATES_ADVANCED_VALUES 15
#define SEND_PID_ADVANCED_VALUES 18
#define SEND_GOV_VALUES 27
#define SEND_GOV_CONFIG_VALUES 28
static uint16_t BlockSeen = 0x3FF; static bool BlockShown = true; static uint32_t FcBankAskAt = 0, FcBankAskAt2 = 0; static uint32_t millis() { return 1000; }
static bool PipeReadRefused = false, Reading_PIDS_Now = false, Reading_RATES_Now = false, Reading_RATES_Advanced_Now = false, Reading_PIDS_Advanced_Now = false, Reading_GOV_Now = false, Reading_GOV_Config_Now = false, BlockBankChanges = false;
static int CurrentView = 45;
#define RFGOVERNORVIEW_GLOBAL 55
static std::vector<std::string> texts; static void SendText(char *n, char *t) { texts.push_back(std::string(n) + "=" + t); } static void SendCommand(char *c) { texts.push_back(c); }
static int PipeState = 2, ParametersToBeSentPointer = 0, ParameterRepeats = 0;
#define PARAMETER_SEND_REPEATS 1
#define PARAMETER_QUEUE_MAXIMUM 32
static uint8_t ParametersToBeSent[40];
static int sentOrder[16], sentN = 0, fileOrder[16], fileN = 0;
bool RfParamOverPipe(uint8_t id) { return (id >= 9 && id <= 21) || (id >= 27 && id <= 33); }
void SendParameterByPipe(uint8_t id) { if (sentN < 16) sentOrder[sentN++] = id; }
bool BakOffline() { return BakOfflineNow; }
bool BakOfflineWords(uint8_t id) { if (fileN < 16) fileOrder[fileN++] = id; return true; }
''' + m.group(0) + mq.group(0) + ma.group(0) + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
int main() {
    TelemetryFromPipe("25:AABBCCDD 26:EEFF0011 34:01020000");
    CHECK(seen == 3); CHECK(last[0] == 34 && last[1] == 0x01 && last[2] == 0x02 && last[3] == 0 && last[4] == 0);
    seen = 0; TelemetryFromPipe("25:AABBCCDD"); CHECK(seen == 1); CHECK(last[0] == 25 && last[1] == 0xAA && last[4] == 0xDD);
    seen = 0; TelemetryFromPipe("  28:0102"); CHECK(seen == 1); CHECK(last[0] == 28 && last[1] == 1 && last[2] == 2 && last[3] == 0);   // (two bytes: the rest zero)
    seen = 0; TelemetryFromPipe(""); CHECK(seen == 0);
    seen = 0; TelemetryFromPipe("junk"); CHECK(seen == 0);
    seen = 0; TelemetryFromPipe("25:AABBCCDD 999:00000000"); CHECK(seen == 1);                     // (an item out of range stops it)
    seen = 0; TelemetryFromPipe("25:A"); CHECK(seen == 0);                                          // (half a byte: nothing)
    seen = 0; TelemetryFromPipe("25:AABBCCDD 26:EEFF0011x"); CHECK(seen == 2);
    // B71: a write queued as the pages queue it (the trigger part first) goes out trigger LAST, and nothing goes before the flush
    AddParameterstoQueue(11); AddParameterstoQueue(10); CHECK(sentN == 0); PipeFlush(); CHECK(sentN == 2 && sentOrder[0] == 10 && sentOrder[1] == 11);
    sentN = 0; AddParameterstoQueue(21); AddParameterstoQueue(20); AddParameterstoQueue(19); PipeFlush(); CHECK(sentN == 3 && sentOrder[0] == 19 && sentOrder[1] == 20 && sentOrder[2] == 21);
    sentN = 0; AddParameterstoQueue(33); AddParameterstoQueue(32); AddParameterstoQueue(31); PipeFlush(); CHECK(sentN == 3 && sentOrder[0] == 31 && sentOrder[2] == 33);
    sentN = 0; PipeState = 1; Reading_PIDS_Now = true; BlockBankChanges = true; AddParameterstoQueue(9); PipeFlush(); CHECK(sentN == 0);   // (no pipe: dropped, never the radio)
    CHECK(PipeReadRefused && !Reading_PIDS_Now && !BlockBankChanges && texts.size() == 2 && texts[0].find("busy=Bluetooth is joining") == 0 && texts[1] == "vis busy,1");   // B80: the page is told, and freed
    PipeState = 3; texts.clear(); AddParameterstoQueue(12); CHECK(texts[0].find("busy=No Bluetooth to the receiver") == 0);
    PipeState = 2; sentN = 0; AddParameterstoQueue(10); PipeFlush(); CHECK(sentN == 1); sentN = 0;   // (a write part: not a block ask, nothing said)
    PipeState = 2; ModelMatched = false; AddParameterstoQueue(9); PipeFlush(); CHECK(sentN == 0 && fileN == 0); // (no model, no file: dropped)
    BakOfflineNow = true; AddParameterstoQueue(14); AddParameterstoQueue(13); PipeFlush(); CHECK(sentN == 0 && fileN == 2 && fileOrder[0] == 13 && fileOrder[1] == 14);   // (no model, a file: to the file, in order)
    ModelMatched = true; BakOfflineNow = false; AddParameterstoQueue(9); CHECK(BlockSeen == 0);   // (B79: a block asked for: the set is awaited afresh)
    AddParameterstoQueue(2); CHECK(ParametersToBeSentPointer == 1 && ParametersToBeSent[1] == 2);   // (the others still queue for the radio)
    printf("test_pipe: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++11', '-Wall', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr); sys.exit(1)
if subprocess.run([os.path.join(d, 't')]).returncode: sys.exit(1)

# B89: ParseTelemetryItem counts an item for the "set complete" hide AFTER its bytes are stored. B79 counted first, so the
# hide ran with the last item's bytes still to come; the governor global page counts its 24 bytes before it believes a
# read and said "Failed to read global (config) bytes" with 20 of them (Malcolm, 9 Oct, offline from the backup).
# (1) the shape of the real ParseTelemetryItem: the mask tick before the switch, the count after it
mp = re.search(r'FASTRUN void ParseTelemetryItem\(\)\n\{.*?\n\}\n', src, re.S)
assert mp, 'ParseTelemetryItem not found'
body = mp.group(0)
assert body.index('BlockMaskTick()') < body.index('switch ('), 'the mask tick belongs before the switch'
assert body.index('BlockItemSeen(') > body.rindex('\n    }\n'), 'the item must be counted AFTER the switch has stored its bytes (B89)'
# (2) the real counter, byte store and governor global page, fed the six items as the file (or the receiver) sends them
mb = re.search(r'static bool BlockWasReading = false;.*?\nstatic void BlockItemSeen\(uint8_t item\)\n\{.*?\n\}\n', src, re.S)
assert mb, 'BlockItemSeen not found'
mg = re.search(r'void ReadGovBytesFromAckPayload\(uint8_t n, uint8_t m\)\n\{.*?\n\}\n', src, re.S)
assert mg, 'ReadGovBytesFromAckPayload not found'
gsrc = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Governor_Global.h')).read()
mh = re.search(r'FLASHMEM void HideGOVConfigMsg\(\)\n\{.*?\n\}\n', gsrc, re.S)
mall = re.search(r'FLASHMEM bool AllGlobalConfigBytesReceived\(\)\n\{.*?\n\}\n', gsrc, re.S)
md = re.search(r'FLASHMEM void DisplayGovConfigValues\(uint8_t n, uint8_t m\)\n\{.*?\n\}\n', gsrc, re.S)
assert mh and mall and md, 'the governor global page functions not found'
prog2 = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
#define FLASHMEM
#define GOV_ACK_PAYLOAD_SIZE 59
#define RFGOVERNORVIEW_PROFILE 54
#define RFGOVERNORVIEW_GLOBAL 55
#define RESTORE_RF_SETTINGS 8
#define Black 0
struct Payload { uint8_t Ack_Payload_byte[32]; } AckPayload;
static uint8_t GovAckPayload[GOV_ACK_PAYLOAD_SIZE] = {0};
static uint8_t Global_Params_Received_Flags[24] = {0};
static uint32_t GOV_Global_Start_Time = 1000;
static int CurrentView = RFGOVERNORVIEW_GLOBAL, CurrentMode = 0;
static uint16_t BlockSeen = 0; static bool BlockShown = false, BlockBankChanges = true;
static bool Reading_PIDS_Now = false, Reading_RATES_Now = false, Reading_RATES_Advanced_Now = false, Reading_PIDS_Advanced_Now = false, Reading_GOV_Now = false, Reading_GOV_Config_Now = true;
static int hides = 0, boxes = 0, restarts = 0, values = 0; static std::string lastBox;
static void SendCommand(char *) {}
static void SendValue(char *, int) { ++values; }
static void ForegroundColourGOVConfigLabels(int) {}
static bool RfLive() { return true; }
static void MsgBox(char *, char *m) { ++boxes; lastBox = m; }
static void Start_RF_Governor() { ++restarts; }
static void AddWords() {}
static void DisplayGovValues(uint8_t, uint8_t) {}
static void HidePIDMsg() {} static void HidePID_Advanced_Msg() {} static void HideGOVMsg() {} static void HideRATESMsg() {} static void Hide_Advanced_Rates_Msg() {}
bool AllGlobalConfigBytesReceived();
void DisplayGovConfigValues(uint8_t n, uint8_t m);
void HideGOVConfigMsg();
''' + mall.group(0) + md.group(0) + mh.group(0).replace('FLASHMEM void HideGOVConfigMsg()', 'FLASHMEM void HideGOVConfigMsgReal();\nFLASHMEM void HideGOVConfigMsg() { ++hides; HideGOVConfigMsgReal(); }\nFLASHMEM void HideGOVConfigMsgReal()') + mg.group(0) + mb.group(0) + r'''
// the gov-config part of ParseTelemetryItem for items 25..30: bytes 18..41, four per item
static void Store(uint8_t item) { ReadGovBytesFromAckPayload((uint8_t)(18 + 4 * (item - 25)), (uint8_t)(22 + 4 * (item - 25))); }
static void Item(uint8_t item, bool countFirst)
{
    AckPayload.Ack_Payload_byte[0] = item; for (int i = 1; i <= 4; ++i) AckPayload.Ack_Payload_byte[i] = (uint8_t)(item * 10 + i);
    BlockMaskTick();
    if (countFirst) { BlockItemSeen(item); Store(item); } else { Store(item); BlockItemSeen(item); }
}
static void Fresh() { memset(Global_Params_Received_Flags, 0, sizeof(Global_Params_Received_Flags)); memset(GovAckPayload, 0, sizeof(GovAckPayload)); BlockSeen = 0; BlockShown = false; BlockWasReading = false; GOV_Global_Start_Time = 1000; hides = boxes = restarts = values = 0; }
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
int main() {
    // B79's order, kept here as the record of the fault: the hide after item 30 ran with bytes 38..41 still to come
    Fresh(); for (uint8_t it = 25; it <= 30; ++it) Item(it, true);
    CHECK(hides == 1 && boxes == 1 && lastBox.find("Failed to read global") != std::string::npos && restarts == 1);
    // B89's order: every byte is in before the set counts as complete; the page believes the read, no box, no restart
    Fresh(); for (uint8_t it = 25; it <= 30; ++it) { Item(it, false); CHECK(hides == (it == 30 ? 1 : 0)); }
    CHECK(boxes == 0 && restarts == 0 && BlockShown && BlockSeen == 0x3F && AllGlobalConfigBytesReceived());
    CHECK(GovAckPayload[18] == 251 && GovAckPayload[41] == 304 % 256 && GOV_Global_Start_Time == 0);   // (the bytes landed where the page reads them; the window is told to end)
    CHECK(values == SHOWN_FIELDS);   // (every field the page shows was sent once)
    // the same set again (a fresh read within the window) updates the numbers without a second hide
    hides = 0; for (uint8_t it = 25; it <= 30; ++it) Item(it, false);
    CHECK(hides == 0 && boxes == 0);
    printf("test_pipe (telemetry items): %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
prog2 = prog2.replace('SHOWN_FIELDS', str(md.group(0).count('SendValue(')))
cpp2 = os.path.join(d, 't2.cpp'); open(cpp2, 'w').write(prog2)
r = subprocess.run(['clang++', '-std=c++11', '-Wall', '-o', os.path.join(d, 't2'), cpp2], capture_output=True, text=True)
if r.returncode: print(r.stderr); sys.exit(1)
if subprocess.run([os.path.join(d, 't2')]).returncode: sys.exit(1)

# B90: a read sent to the receiver inside the two seconds before the model is declared lost is answered from the backup
# file at the moment of the loss (PipeModelGoneTick); a write is not; a word page with its read still open reads the
# file (RfModelGone). The real PipeHttp.h request bookkeeping and the two B90 functions, compiled with a fake file.
hsrc = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'PipeHttp.h')).read()
mh1 = re.search(r'static int PipeReqId = 0;.*?\nint PipeReplyBytes\(uint8_t \*out, int max\)\n\{.*?\n\}\n', hsrc, re.S)
mh2 = re.search(r'static void RfReadBlockAgain\(\).*?\nvoid RfModelGone\(\)[^\n]*\n\{.*?\n\}\n', hsrc, re.S)
assert mh1 and mh2, 'the pipe bookkeeping or the B90 functions not found'
bsrc = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Backup.h')).read()
mb1 = re.search(r'FLASHMEM static bool BakIndexed\(uint8_t fn\)[^\n]*\n', bsrc)
mb2 = re.search(r'FLASHMEM bool BakOfflineRead\(uint8_t fn, int len\)[^\n]*\n', bsrc)
assert mb1 and mb2, 'BakIndexed / BakOfflineRead not found'
prog3 = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>
#define FLASHMEM
#define PIDVIEW 45
#define RATESVIEW_RF 46
#define RATESADVANCEDVIEW 48
#define PIDADVANCEDVIEW 49
#define RFGOVERNORVIEW_PROFILE 54
#define RFGOVERNORVIEW_GLOBAL 55
#define NORMAL 0
#define SAVE_RF_SETTINGS 7
#define RESTORE_RF_SETTINGS 8
static uint32_t now = 10000; static uint32_t millis() { return now; }
static int CurrentView = 67, CurrentMode = NORMAL;
static bool offline = false, haveFile = true, PipeReadRefused = false;
static bool Reading_PIDS_Now = false, Reading_RATES_Now = false, Reading_RATES_Advanced_Now = false, Reading_PIDS_Advanced_Now = false, Reading_GOV_Now = false, Reading_GOV_Config_Now = false;
static std::vector<std::string> sent; static void SendCommand(char *c) { sent.push_back(c); }
static int answered = 0, lastFn = -1, lastLen = -1, lastIdx = -1, pipeShown = 0, pidReads = 0, govReads = 0;
static void ShowPipeState() { ++pipeShown; }
void ShowPIDBank() { ++pidReads; } void ShowRatesBank() {} void ShowRatesAdvancedBank() {} void ShowPIDAdvancedBank() {} void ShowGOVBank() { ++govReads; } void ShowGOV_Global_Bank() {}
bool BakOffline() { return offline; }
bool BakHaveFile() { return haveFile; }
bool BakOfflineRead(uint8_t fn, int len);
''' + mb1.group(0) + mb2.group(0) + r'''
static int PipeRepCodeSet = 200;
void PipeRepSet(int code, const char *body);
bool BakOfflineAnswer(uint8_t fn, const uint8_t *data, int len) { ++answered; lastFn = fn; lastLen = len; lastIdx = (data && len >= 1) ? data[0] : -1; PipeRepSet(PipeRepCodeSet, "AABB"); return true; }
''' + mh1.group(0) + mh2.group(0) + r'''
void PipeRepSet(int code, const char *body) { PipeRepCode = code; snprintf(PipeRepBody, sizeof(PipeRepBody), "%s", body); }
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
int main() {
    // a read asked of the receiver with the model there; the model is declared lost 1.5 s later: the file answers it
    offline = false; const int r1 = MspAsk(111, nullptr, 0);
    CHECK(sent.size() == 1 && sent[0].find("ldrcreq") == 0 && PipeRepId == -1);
    PipeModelGoneTick(); CHECK(PipeRepId == -1 && answered == 0);                    // (the model is still there)
    now += 1500; offline = true; RfModelGone(); CHECK(pipeShown == 1 && pidReads == 0);   // (no word read open: nothing re-read, the menu word only)
    PipeModelGoneTick(); CHECK(answered == 1 && lastFn == 111 && lastLen == 0 && PipeReplyReady(r1) && PipeRepCode == 200);
    PipeModelGoneTick(); CHECK(answered == 1);                                        // (once)
    // a write (53, 15 bytes) left unanswered is NOT answered by the file: the page reports it as not done
    offline = false; uint8_t line[15] = {3, 1, 2}; const int r2 = MspAsk(53, line, 15); CHECK(PipeRepId == -1);
    offline = true; PipeModelGoneTick(); CHECK(answered == 1 && !PipeReplyReady(r2));
    // an indexed read (174 with its index) is answered, with its index
    offline = false; uint8_t idx[1] = {2}; const int r3 = MspAsk(174, idx, 1); offline = true; PipeModelGoneTick();
    CHECK(answered == 2 && lastFn == 174 && lastLen == 1 && lastIdx == 2 && PipeReplyReady(r3));
    // too late (the page has given up at 9 s): not answered
    offline = false; const int r4 = MspAsk(52, nullptr, 0); now += 9500; offline = true; PipeModelGoneTick(); CHECK(answered == 2 && !PipeReplyReady(r4));
    // a backup or restore in progress says for itself that the model went: not answered
    offline = false; const int r5 = MspAsk(52, nullptr, 0); offline = true; CurrentMode = SAVE_RF_SETTINGS; PipeModelGoneTick(); CHECK(answered == 2 && !PipeReplyReady(r5));
    CurrentMode = NORMAL; PipeModelGoneTick(); CHECK(answered == 3 && PipeReplyReady(r5));
    // a request already answered by the file (asked with no model) leaves nothing for the tick
    offline = true; const int r6 = MspAsk(101, nullptr, 0); CHECK(answered == 4 && PipeReplyReady(r6)); PipeModelGoneTick(); CHECK(answered == 4);
    // a word page with its read still open when the model goes reads the file; one whose read is done keeps its numbers
    CurrentView = PIDVIEW; Reading_PIDS_Now = true; RfModelGone(); CHECK(pidReads == 1);
    Reading_PIDS_Now = false; RfModelGone(); CHECK(pidReads == 1);
    PipeReadRefused = true; RfModelGone(); CHECK(pidReads == 2 && !PipeReadRefused);   // (B80: refused for want of the pipe: reads now)
    CurrentView = RFGOVERNORVIEW_PROFILE; Reading_GOV_Now = true; RfModelGone(); CHECK(govReads == 1 && pidReads == 2);
    // no backup file: nothing happens at all
    haveFile = false; pipeShown = 0; Reading_GOV_Now = true; RfModelGone(); CHECK(pipeShown == 0 && govReads == 1);
    printf("test_pipe (model gone): %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
cpp3 = os.path.join(d, 't3.cpp'); open(cpp3, 'w').write(prog3)
r = subprocess.run(['clang++', '-std=c++11', '-Wall', '-o', os.path.join(d, 't3'), cpp3], capture_output=True, text=True)
if r.returncode: print(r.stderr); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't3')]).returncode)
