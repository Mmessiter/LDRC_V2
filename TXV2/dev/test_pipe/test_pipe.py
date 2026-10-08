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
static uint16_t BlockSeen = 0x3FF; static bool BlockShown = true;
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
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
