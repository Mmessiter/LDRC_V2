#!/usr/bin/env python3
"""Source checks of the FRAMED BURSTS (screen 1.11.173/1.11.174; the main board's B177): the main board says "ldrcframe=1" and
from then on every script's output must leave in one write as 7E 7E len_lo len_hi bytes.

1.11.173 got this wrong without any test noticing: the enable was looked for in Host::unknownCommand, but the serial command
parser (handle) takes every "name=value" without a dot for a system variable and never gets there - the screen never framed,
the main board stayed lenient, and the ghost buttons went on (Malcolm, 4 Nov 2026, scrolling the log after the update).
These checks read src/main.cpp as it is: the enable is answered in handle() before anything else can take it, and flushOut
frames when asked.
   python3 hmi/test_frames/check.py"""
import os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src = open(os.path.join(ROOT, 'src', 'main.cpp'), encoding='utf-8', errors='replace').read()
checks = fails = 0
def check(cond, what):
    global checks, fails
    checks += 1
    if not cond:
        fails += 1
        print('   FAIL:', what)

# 1. handle(): the enable is its first test, ahead of "page ", the "get " path and the name=value path
m = re.search(r'static void handle\(const std::string &cmd\) \{(.*?)\n\}\n', src, re.S)
check(m is not None, 'handle(const std::string &cmd) found')
body = m.group(1) if m else ''
enable = body.find('if (cmd == "ldrcframe=1") { frameBursts = true; return; }')
check(enable >= 0, 'handle() answers "ldrcframe=1" by setting frameBursts')
for later in ('cmd.rfind("page ", 0)', 'cmd.rfind("get ", 0)', "cmd.find('=')", 'host.setSys(name'):
    at = body.find(later)
    check(at > enable >= 0, 'the enable comes before %s in handle()' % later)
# 2. unknownCommand must not be relied on for it (the script interpreter's path, never the serial one)
um = re.search(r'void unknownCommand\(const std::string &line\) override \{(.*?)\n    \}\n', src, re.S)
check(um is not None and 'ldrcframe' not in um.group(1), 'the enable is not left to Host::unknownCommand')
# 3. flushOut frames when asked, in one write
fm = re.search(r'static void flushOut\(\) \{(.*?)\n\}\n', src, re.S)
check(fm is not None, 'flushOut found')
fb = fm.group(1) if fm else ''
check('if (frameBursts)' in fb, 'flushOut looks at frameBursts')
check('0x7E, 0x7E' in fb and 'n & 0xFF' in fb and 'n >> 8' in fb, 'the frame is 7E 7E, the length low byte first')
check('outBuf.insert(0, h, 4)' in fb and fb.count('Serial.write(') == 1, 'the header and the bytes leave in ONE write')
check('4000' in fb, "a burst longer than the main board's buffer is cut")
# 4. the default is off: an older main board never sees a frame
check(re.search(r'static bool frameBursts = false;', src) is not None, 'frameBursts starts false')
print('test_frames (screen): %d checks, %d failures' % (checks, fails))
sys.exit(1 if fails else 0)
