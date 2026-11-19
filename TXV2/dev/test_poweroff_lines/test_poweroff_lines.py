#!/usr/bin/env python3
"""THE LINES KEPT FOR A QUIET MOMENT ARE WRITTEN AT EVERY POWER-OFF (B211, the thirteenth review - and the seventeenth, reviewer A: the power-off for
idleness did not write them). Source checks - the break-it round of 16 Nov 2026 (mut19: IF1, EF1) found that nothing held these two places:
 1. every place that switches the transmitter off (POWER_OFF_PIN put HIGH) has FlushDeferredLog() in front of it in its own routine, behind
    NoteWhyOff() - and there are as many such places as were last read through (a new road to "off" is added here knowingly);
 2. the once-a-second writing of the kept lines (main.cpp) follows FlightGuard.h LogMustWait's own rule in BOTH kinds of build: in a test build
    with the ELRS module, "no safety switch, and an ELRS model flown by the module" waits too (a card write is a gap in the sticks' copies)."""
import os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, 'TransmitterCode')
def src(n): return open(os.path.join(TC, n), encoding='utf-8').read()
def bare(t): return re.sub(r'//[^\n]*', '', re.sub(r'/\*.*?\*/', '', t, flags=re.S))
bad = []; checks = 0
files = ['src/main.cpp'] + sorted('include/' + f for f in os.listdir(os.path.join(TC, 'include')) if f.endswith('.h'))
offs = []
for f in files:
    t = bare(src(f))
    for m in re.finditer(r'digitalWrite(?:Fast)?\(POWER_OFF_PIN, HIGH\)', t):
        # the routine it stands in: from the last line that begins a routine (no indent, ends with ")") to here
        heads = [h for h in re.finditer(r'^[A-Za-z_][^\n;{}]*\)[ \t]*\n\{', t[:m.start()], re.M)]
        body = t[heads[-1].start():m.start()] if heads else ''
        name = re.search(r'(\w+)\s*\([^()]*\)\s*\n\{', body).group(1) if body else '?'
        offs.append((f, name))
        checks += 1
        a, b = body.find('NoteWhyOff('), body.find('FlushDeferredLog();')
        if not (0 <= a < b): bad.append('%s %s: the power is cut with no FlushDeferredLog() behind NoteWhyOff() in front of it - the lines kept for a quiet moment never reach the card' % (f, name))
checks += 1
if sorted(offs) != [('include/transceiver.h', 'CheckInactivityTimeout'), ('src/main.cpp', 'Close_TX_Down')]:
    bad.append('the places that switch the transmitter off are %s - they were Close_TX_Down (main.cpp) and CheckInactivityTimeout (transceiver.h) when last read through' % sorted(offs))
M = src('src/main.cpp'); FG = src('include/FlightGuard.h')
checks += 1
if not re.search(r'#ifdef ELRS_TEST\n\s*if \(!\(BoundFlag && ModelMatched\) && !RadiosMustBeOff\(\) && !\(!SafetyIsDefined\(\) && ElrsFlies\(\)\)\)[^\n]*\n#else\n\s*if \(!\(BoundFlag && ModelMatched\) && !RadiosMustBeOff\(\)\)\n#endif\n\s*FlushDeferredLog\(\);', M):
    bad.append('main.cpp: the once-a-second writing of the kept lines is not "no model connected, nothing may fly" in a release and "... nor an ELRS model flown by the module with no safety switch" in a test build')
checks += 1
if not re.search(r'#ifdef ELRS_TEST\n(?:[^\n]*\n){0,3}?bool LogMustWait\(\) \{ return RadiosMustBeOff\(\) \|\| \(!SafetyIsDefined\(\) && \(\(BoundFlag && ModelMatched\) \|\| ElrsFlies\(\)\)\); \}[^\n]*\n#else\nbool LogMustWait\(\) \{ return RadiosMustBeOff\(\) \|\| \(!SafetyIsDefined\(\) && BoundFlag && ModelMatched\); \}\n#endif', FG):
    bad.append('FlightGuard.h: LogMustWait is not the rule this test knows in its two kinds of build')
for b in bad: print('FAIL: ' + b)
print('test_poweroff_lines: %d checks, %d failures' % (checks, len(bad)))
if bad: sys.exit(1)
print('ALL GOOD')
