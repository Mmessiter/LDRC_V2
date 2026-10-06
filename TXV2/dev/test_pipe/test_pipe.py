#!/usr/bin/env python3
"""Host test of the Teensy's pipe parsing (B41): TelemetryFromPipe() as it is in include/transceiver.h, compiled on the
Mac with a fake ack payload and a counting parser round it, and SendParameterByPipe()'s wording checked by eye of code.
   python3 dev/test_pipe/test_pipe.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'transceiver.h')).read()
m = re.search(r'void TelemetryFromPipe\(const char \*list\)\n\{.*?\n\}\n', src, re.S)
assert m, 'TelemetryFromPipe not found'
prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cctype>
#include <cstdint>
struct Payload { uint8_t Ack_Payload_byte[32]; } AckPayload;
static int seen = 0; static uint8_t last[5];
void ParseTelemetryItem() { ++seen; for (int i = 0; i < 5; ++i) last[i] = AckPayload.Ack_Payload_byte[i]; }
#define FASTRUN
''' + m.group(0) + r'''
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
    printf("test_pipe: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++11', '-Wall', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
