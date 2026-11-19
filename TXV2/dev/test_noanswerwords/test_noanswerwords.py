#!/usr/bin/env python3
"""WHAT A PAGE SAYS WHEN THE FLIGHT CONTROLLER GAVE NO ANSWER (B211, the seventeenth review, reviewer B's finding 6: the words).
A step of a SAVE that got no answer may have left a part written and nothing stored: its page says so ("No answer - PART MAY BE WRITTEN, NOT
STORED: try again, or switch the model off and on" - RF_SaveNow.h RfNoAnswerWords). A read, or a reading-back behind the store, says "No answer".
Eleven pages ask RfNoAnswerWords with a test of their own step. HERE EVERY STEP OF EVERY PAGE IS PUT TO THE PAGE'S OWN TEST (lifted from its
source, compiled with the page's own list of steps) and held against this table: which steps lie between the first write and the store.
The break-it round of 16 Nov 2026 (mut19: NA3 to NA13 - each page's test made "false") found that nothing held these eleven places."""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INC = os.path.join(ROOT, 'TransmitterCode', 'include')
def src(n): return open(os.path.join(INC, n), encoding='utf-8').read()
def steps(header, first):
    t = re.sub(r'//[^\n]*', '', src(header)); i = t.index(first); a = t.rfind('enum', 0, i); return t[a:t.index('}', i) + 1]
def names(enum): return [x.split('=')[0].strip() for x in enum[enum.index('{') + 1:enum.index('}')].split(',') if x.strip()]
# page: (its header, its first step, its step's name in the code, the routine that says the failure, HOW its saving steps lie:
#        'run' = every step from the first write to the store (its save goes through them in this order);
#        'named' = the steps named WRITE or STORE only (other work lies between them: a reading of the attitude, a wait))
PAGES = (('Basics', 'RF_Basics.h', 'BAS_IDLE', 'BasStep', 'BasFail', 'run'), ('Filters', 'RF_Filters.h', 'FLT_IDLE', 'FltStep', 'FltFail', 'run'), ('Travel', 'RF_Travel.h', 'TRV_IDLE', 'TravStep', 'TravFail', 'run'),
         ('Rescue', 'RF_Rescue.h', 'RSC_IDLE', 'RescueStep', 'RescueFail', 'run'), ('Servos', 'RF_Servos.h', 'SRV_IDLE', 'ServoStep', 'ServoFail', 'run'), ('Battery', 'RF_FcSetup.h', 'BAT_IDLE', 'BatStep', 'BatFail', 'run'),
         ('Black box', 'RF_FcSetup.h', 'BB_IDLE', 'BbStep', 'BbFail', 'run'), ('Level', 'RF_FcSetup.h', 'CAL_IDLE', 'CalStep', 'CalFail', 'named'), ('Beeper & name', 'RF_Beeper.h', 'BP_IDLE', 'BpStep', 'BpFail', 'run'),
         ('Switches', 'RF_Switches.h', 'SW_IDLE', 'SwStep', 'SwFail', 'run'), ('Knobs', 'RF_Adjust.h', 'ADJ_IDLE', 'AdjStep_', 'AdjFail', 'run'))
def the_test(header, fail):   # the page's own test: what stands inside RfNoAnswerWords( ... ) in its call of its failure routine
    t = src(header); k = t.index(fail + '(RfNoAnswerWords('); assert t.count(fail + '(RfNoAnswerWords(') == 1, (header, fail)
    i = k + len(fail + '(RfNoAnswerWords('); d = 1; j = i
    while d:
        d += {'(': 1, ')': -1}.get(t[j], 0); j += 1
    return t[i:j - 1]
prog = '#include <cstdio>\n'; body = ''; bad = []; table = []
for page, header, first, var, fail, how in PAGES:
    en = steps(header, first); ns = names(en); cond = the_test(header, fail)
    marked = [i for i, n in enumerate(ns) if 'WRITE' in n or 'STORE' in n]
    if not marked or 'STORE' not in ns[marked[-1]]: bad.append('%s: its list of steps has no write and store as this test knows them: %s' % (page, ns)); continue
    saving = set(range(marked[0], marked[-1] + 1)) if how == 'run' else set(marked)
    if how == 'run' and any('VERIFY' in ns[i] or 'REBOOT' in ns[i] or 'WAIT' in ns[i] for i in saving): bad.append('%s: a step that is no part of the writing lies between its first write and its store: %s' % (page, [ns[i] for i in sorted(saving)]))
    table.append((page, [ns[i] for i in sorted(saving)], cond))
    prog += 'namespace n%d { %s; static int %s; static bool t() { return %s; } }\n' % (len(table), en, var, cond)
    for i, n in enumerate(ns):
        body += '    n%d::%s = n%d::%s; if (n%d::t() != %s) { ++fails; printf("FAIL line %%d: %s: at its step %s the page says %%s\\n", __LINE__, n%d::t() ? "A PART MAY BE WRITTEN" : "the plain No answer"); } ++checks;\n' % (
            len(table), var, len(table), n, len(table), 'true' if i in saving else 'false', page, n, len(table))
prog += 'int main()\n{\n    int checks = 0, fails = 0;\n' + body + '    printf("test_noanswerwords: %d checks, %d failures\\n", checks, fails);\n    return fails ? 1 : 0;\n}\n'
# ... and the helper itself, and the two places with words of their own (a slot, a line, refused behind others that were written)
SN = src('RF_SaveNow.h')
if '#define RF_NO_ANSWER_SAVING "No answer - PART MAY BE WRITTEN, NOT STORED: try again, or switch the model off and on"' not in SN: bad.append('RF_SaveNow.h: the words of a save step that got no answer are not the ones last read through')
if 'static inline const char *RfNoAnswerWords(bool savingStep) { return savingStep ? RF_NO_ANSWER_SAVING : "No answer"; }' not in SN: bad.append('RF_SaveNow.h: RfNoAnswerWords is not "a save\'s step: a part may be written; else the plain words"')
for header, form in (('RF_Switches.h', 'snprintf(w, sizeof(w), SwWriteAt > 0 ? "Slot %d was not written - THE SLOTS BEFORE IT ARE, not stored: try again, or switch the model off and on" : "Slot %d was not written", SwWriteAt + 1);'),
                     ('RF_Adjust.h', 'snprintf(w, sizeof(w), AdjLineAt > 0 ? "Line %d was not written - THE LINES BEFORE IT ARE, not stored: try again, or switch the model off and on" : "Line %d was not written", AdjLineAt + 1);')):
    if src(header).count(form) != 1: bad.append('%s: a slot (a line) refused behind others that WERE written must say that those are written and not stored' % header)
# ... and the page's own line behind a save that failed on the quiet road (no box while the model may fly): what it tells the pilot to DO (mut19 QR15)
if '#define RF_NOT_SAVED_LINE "NOT CONFIRMED. Safety on, then Save again."' not in SN: bad.append('RF_SaveNow.h: the line a page keeps behind a save that failed quietly is not "NOT CONFIRMED. Safety on, then Save again." (the eighteenth review: "NOT SAVED." was untrue behind a failure of the read-back - all written and stored)')
for b in bad: print('FAIL: ' + b)
with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 't.cpp'), 'w').write(prog)
    r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-variable', '-o', os.path.join(d, 't'), os.path.join(d, 't.cpp')], capture_output=True, text=True)
    if r.returncode: print(r.stderr[:4000]); sys.exit('test_noanswerwords: DID NOT COMPILE')
    r = subprocess.run([os.path.join(d, 't')], capture_output=True, text=True); sys.stdout.write(r.stdout)
if '--show' in sys.argv:
    for page, sv, cond in table: print('  %-14s a part may be written at: %s   [its test: %s]' % (page, ', '.join(sv), cond))
if r.returncode or bad: sys.exit(1)
print('ALL GOOD')
