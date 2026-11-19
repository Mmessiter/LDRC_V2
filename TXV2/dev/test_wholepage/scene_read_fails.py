#!/usr/bin/env python3
"""THE FIFTEENTH REVIEW'S RULES OF THE ROTORFLIGHT PAGES, HELD BY THE SOURCE - and the log's "may it be written now?" by a run (16 Nov 2026).
 1. A READ THAT FAILS LEAVES NOTHING IN HAND, AND THE PAGE IS LEFT (released code had it; reviewer B's B1): each of the five pages forgets what it has
    as its read begins, and its failure routine leaves the page while nothing is in hand - RF_SaveNow.h RfLeaveNotRead - or, the menu shut, puts the
    page up again with the standing line "NOT READ ...". (Run: test_basics, test_servos, scene_stale_block, scene_travel_dir.)
 2. THE PARTS THAT TURN BY THEMSELVES ARE WRITTEN AS THEY ARE IN HAND behind a failure's box: Travel's four direction switches, Rescue's two and
    page 2's word, the Servos page's two. (Run: scene_travel_dir, scene_rescue_switch, scene_save_fails, test_servos.)
 3. Filters: a tap while a read runs does nothing. Easy tuning: OK asks every slider first while edits wait (run: test_easy).
 4. A LINE FOR THE LOG WAITS WHILE THE MODEL MAY FLY - AND, WITH NO SAFETY SWITCH, WHILE A MODEL IS CONNECTED AT ALL: FlightGuard.h LogMustWait, the
    REAL routine run here over every case; every note of this release asks it.
 5. THE RATES, ADVANCED RATES AND ADVANCED PIDS PAGES: THE SET CAME WHOLE, OR NOTHING IS SAVED (released code had it; the author's find while the
    sixteenth review ran) - as the PIDs and the Governor pages since B40 and B41. Each has its flag: false as a read of the page begins, true when
    the set has come whole (transceiver.h BlockItemSeen: dev/test_pipe runs it) or the model file's own copy is shown; an edit and Save are refused
    while it is false. (Run: dev/test_rates for the Rates page; the other two are held here, by their text.)"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
def code(rel): return re.sub(r'//[^\n]*', '', m.release(m.src(rel)))
bad = []
NOT_READ = '"NOT READ. Safety on, motor off - then OK."'
PAGES = (('RF_Basics.h', 'BasRead', 'BasFail', 'BasHave', 'BasBusy', r'SendCommand\(\(char \*\)BasPageWord\(\)\);\s*BasPageHead\(\);'),
         ('RF_Filters.h', 'FltRead', 'FltFail', 'FltHave', 'FltBusy', r'SendCommand\(\(char \*\)FltPageWord\(\)\);\s*FltHead\(\);'),
         ('RF_Travel.h', 'TravRead', 'TravFail', 'TravHave', 'TravBusy', r'SendCommand\(\(char \*\)TravPageWord\(\)\);\s*TravPageHead\(\);'),
         ('RF_Rescue.h', 'RescueRead', 'RescueFail', 'RescueHave', 'RescueBusy', r'char b\[16\];\s*snprintf\(b, sizeof\(b\), "Bank %d", Bank\);\s*SendCommand\(\(char \*\)\(CurrentView == RESCUE2VIEW \? "page Rescue2View" : "page RescueView"\)\);\s*SendText\(\(char \*\)"t11", ModelName\);\s*SendText\(\(char \*\)"t9", b\);\s*SendCommand\(\(char \*\)"vis b3,0"\);'),
         ('RF_Servos.h', 'ServoRead', 'ServoFail', 'ServoHave', 'ServoBusy', r'SendCommand\(\(char \*\)"page ServoView"\);\s*SendText\(\(char \*\)"t11", ModelName\);\s*SendText\(\(char \*\)"t9", \(char \*\)"All banks"\);\s*SendCommand\(\(char \*\)"vis b3,0"\);'))
for rel, read, fail, have, busy, again in PAGES:
    t = code('include/' + rel)
    if not re.search(r'static void %s\(\)\s*\{\s*%s = false;' % (read, have), t):
        bad.append('%s %s: nothing is in hand while a read runs - its first line is "%s = false;"' % (rel, read, have))
    if len(re.findall(r'\b%s = true;' % have, t)) != 1:
        bad.append('%s: "%s = true" stands once - where a read has ended whole' % (rel, have))
    f = t[t.index('static void %s(const char *what)' % fail):]; f = f[:f.index('\n}\n')]
    if not re.search(r'PlaySound\(WHAHWHAHMSG\);\s*if \(!%s\)\s*\{\s*if \(!RfLeaveNotRead\(msg\)\)\s*\{\s*%s\s*%s\(RF_NOT_READ_LINE\);\s*\}\s*return;\s*\}\s*const bool quiet = RfMayFly\(\);\s*RfBoxOrQuiet\(' % (have, again, busy), f) \
            or not re.search(r'if \(quiet\)\s*\{\s*%s\(RF_NOT_SAVED_LINE\);\s*\w+MsgUntil = millis\(\) \+ 6000;\s*\}\s*$' % busy, f):
        bad.append('%s %s: while nothing is in hand - the READ failed - the page is LEFT (RfLeaveNotRead(msg): the box, then the menu); where the menu will not open, the page is put up again with its standing line %s - '
                   'and only behind that the box of a save that failed, which stays on the page (on the quiet road - no box while the model may fly - the page itself says NOT SAVED for six seconds: the seventeenth review)' % (rel, fail, NOT_READ))
sn = code('include/RF_SaveNow.h')
if not re.search(r'bool RfLeaveNotRead\(char \*msg\)\s*\{\s*const uint8_t was = CurrentView;\s*if \(RfMayFly\(\)\)\s*\{\s*RfSayQuietly\(msg\);\s*return false;\s*\}\s*MsgBox\(\(char \*\)"page RFView", msg\);\s*if \(QuestionOvertaken\)\s*return true;\s*RfHomeNotRead = true;\s*RotorFlightStart\(\);\s*RfHomeNotRead = false;\s*return CurrentView != was \|\| QuestionOvertaken;\s*\}', sn) \
        or 'bool RfLeaveNotRead(char *msg);' not in m.DEFS:
    bad.append('RF_SaveNow.h RfLeaveNotRead: the box (its way back the menu), nothing over a page that came over the box, then RotorFlightStart - true when the page was left (or another page stands)')
tv = code('include/RF_Travel.h')
if len(re.findall(r'\bTravDirectionsFromBlock\(\);', tv)) != 4 or len(re.findall(r'if \(!RfKeepTyped\)\s*TravDirectionsFromBlock\(\);', tv)) != 2 \
        or not re.search(r'if \(!RfKeepTyped\)\s*TravDirectionsFromBlock\(\);\s*SendValue\(\(char \*\)"tn6", TravRevAil \? 1 : 0\);\s*SendValue\(\(char \*\)"tn7", TravRevEle \? 1 : 0\);\s*SendValue\(\(char \*\)"tn8", TravRevColl \? 1 : 0\);', tv) \
        or not re.search(r'if \(!RfKeepTyped\)\s*TravDirectionsFromBlock\(\);\s*SendValue\(\(char \*\)"tn0", TravRevYaw \? 1 : 0\);', tv) \
        or len(re.findall(r'memcpy\(TravInWant, TravIn, sizeof\(TravIn\)\);\s*(?:TravHave = true; )?TravStep = TRV_IDLE; Trav_Was_Edited = false; TravPage2Edited = false; TravPage4Edited = false;\s*TravDirectionsFromBlock\(\);', tv)) != 2 \
        or len(re.findall(r'\bTravRev(?:Ail|Ele|Coll|Yaw) = [^=]', tv)) != 4 + 4 + 4:
    bad.append('RF_Travel.h: the four direction switches are written AS THEY ARE IN HAND, always (pages 1 and 3); what is in hand is taken from the block only where the page is drawn from it (not under RfKeepTyped) '
               'and at the end of a read and of a save, on whichever page - TravDirectionsFromBlock, nowhere else but the four taps')
rs = code('include/RF_Rescue.h')
if not re.search(r'static void RescueShow\(\)\s*\{\s*if \(RfKeepTyped\)\s*\{\s*if \(CurrentView == RESCUEVIEW\)\s*\{\s*SendValue\(\(char \*\)"tn0", RescueMode \? 1 : 0\);\s*SendValue\(\(char \*\)"tn1", RescueFlip \? 1 : 0\);\s*\}\s*'
                 r'else if \(CurrentView == RESCUE2VIEW\)\s*RescueField\("tn0", RescueModeWords\[RescueMode <= 2 \? RescueMode : 0\]\);\s*return;\s*\}', rs) \
        or not re.search(r'SendCommand\(\(char \*\)"vis b3,0"\);\s*RescueHave = false;\s*if \(RescueStep == RSC_SELECT \|\| RescueStep == RSC_READ\)\s*RescueStep = RSC_IDLE;\s*RescueRereadWanted = true;', rs):
    bad.append('RF_Rescue.h: under RfKeepTyped the two switches (page 2: its word) are written as they are in hand, and no number; the bank switch moved under the page: nothing is in hand from that moment (RescueBankChanged) - and a read under way is dropped there (the sixteenth review; run: dev/test_rescuebank)')
sv = code('include/RF_Servos.h')
if not re.search(r'if \(ServoCount >= 1\)\s*ServoTitle\(\);\s*SendValue\(\(char \*\)"tn7", ServoRev \? 1 : 0\);\s*SendValue\(\(char \*\)"tn8", ServoGeo \? 1 : 0\);\s*if \(quiet\)', sv):
    bad.append('RF_Servos.h ServoFail, behind a save that failed: the two switches are written as they are in hand (no number is)')
fl = code('include/RF_Filters.h')
if not re.search(r'static bool FltEdited\(\)\s*\{\s*if \(!FltHave\)\s*return false;\s*FltGather\(\);', fl):
    bad.append('RF_Filters.h FltEdited: a tap while a read runs (nothing in hand) does nothing - the features just read are not turned over under the read that follows them')
ez = code('include/RF_Easy.h')
if not re.search(r'void EndEasyView\(\)\s*\{\s*if \(EzStep != EZ_IDLE\) return;\s*if \(Ez_Was_Edited && EzHave && !EzSyncSliders\(\)\) return;\s*if \(Ez_Was_Edited && EzHave && EzAnything\(\)\)', ez):
    bad.append('RF_Easy.h EndEasyView: while edits wait, every slider and the switch are asked BEFORE "Save now?" (one unanswered: the page stays)')
texts = [len(re.findall(r'Busy\(RF_NOT_READ_LINE\);', code('include/' + r))) for r, *_ in PAGES]
if texts != [1, 1, 1, 1, 1] or ('#define RF_NOT_READ_LINE %s' % NOT_READ) not in m.src('include/RF_SaveNow.h'):
    bad.append('the five pages say the same standing line, once each (RF_SaveNow.h RF_NOT_READ_LINE: %s - the sixteenth review: it said "Press OK." where OK does nothing): %s' % (NOT_READ, texts))
# (the sixteenth review) NO BOX THAT WAITS WHILE THE MODEL MAY FLY: the five failure routines' box is RfBoxOrQuiet (PipeHttp.h), and RfLeaveNotRead asks RfMayFly first;
# the guide does not tick the step of a page that could not be read. (Runs: dev/test_basics; the other four pages are held here, by their text.)
for r, *_ in PAGES:
    t = code('include/' + r); fn = {'RF_Basics.h': 'BasFail', 'RF_Filters.h': 'FltFail', 'RF_Travel.h': 'TravFail', 'RF_Rescue.h': 'RescueFail', 'RF_Servos.h': 'ServoFail'}[r]
    i = t.index('static void %s(' % fn); body = t[i:t.index('\n}\n', i)]
    if 'MsgBox(' in body or len(re.findall(r'\bRfBoxOrQuiet\(', body)) != 1 or len(re.findall(r'\bRfLeaveNotRead\(msg\)', body)) != 1:
        bad.append('%s %s: its one box is RfBoxOrQuiet (no box that waits while the model may fly), and a failed read goes to RfLeaveNotRead' % (r, fn))
sn = re.sub(r'//[^\n]*', '', m.src('include/RF_SaveNow.h')); tl = re.sub(r'//[^\n]*', '', m.src('include/RF_Tools.h'))
if not re.search(r'bool RfLeaveNotRead\(char \*msg\)\s*\{\s*const uint8_t was = CurrentView;\s*if \(RfMayFly\(\)\)\s*\{\s*RfSayQuietly\(msg\);\s*return false;\s*\}\s*MsgBox\(\(char \*\)"page RFView", msg\);\s*if \(QuestionOvertaken\)\s*return true;\s*'
                 r'RfHomeNotRead = true;\s*RotorFlightStart\(\);\s*RfHomeNotRead = false;', sn) or len(re.findall(r'RfHomeNotRead = true;', sn)) != 1 \
        or not re.search(r'RfShowHome\(RfHome\[--RfHomeN\], !RfHomeNotRead\);', tl) or 'bool RfHomeNotRead = false;' not in m.DEFS:
    bad.append('RF_SaveNow.h RfLeaveNotRead: while the model may fly a line for the log and no box (false: the page stands under its line); else the box, and the menu opened with "this page could not be read" said for its length '
               '(RfHomeNotRead: RF_Tools.h RfHomeBack does not tick the guide\'s step)')
# ---- 4: the log's question
fg, lg, nx, tr = code('include/FlightGuard.h'), code('include/LogFiles.h'), code('include/Nextion.h'), code('include/Trims.h')
_fgall = re.sub(r'//[^\n]*', '', m.src('include/FlightGuard.h'))
if not re.search(r'#ifdef ELRS_TEST\s*bool LogMustWait\(\) \{ return RadiosMustBeOff\(\) \|\| \(!SafetyIsDefined\(\) && \(\(BoundFlag && ModelMatched\) \|\| ElrsFlies\(\)\)\); \}\s*#else\s*'
                 r'bool LogMustWait\(\) \{ return RadiosMustBeOff\(\) \|\| \(!SafetyIsDefined\(\) && BoundFlag && ModelMatched\); \}\s*#endif', _fgall) or 'bool LogMustWait();' not in m.DEFS:
    bad.append('FlightGuard.h LogMustWait: the radios\' rule - or, with no safety switch, a model connected at all (a test build with the ELRS module: or flown by the module - inside #ifdef ELRS_TEST)')
if 'RadiosMustBeOff' in lg or 'RadiosMustBeOff' in tr or len(re.findall(r'\bLogMustWait\(\)', lg)) != 10 or len(re.findall(r'\bLogMustWait\(\)', tr)) != 2 or len(re.findall(r'\bLogMustWait\(\)', nx)) != 2 \
        or not re.search(r'static void NoteLateReply\(const char \*cmd, uint32_t ms, bool got\)\s*\{\s*if \(got && ms <= 400\)\s*return;\s*char m\[80\];\s*if \(LogMustWait\(\)\)', nx) or not re.search(r'last = millis\(\);\s*if \(LogMustWait\(\)\)\s*\{\s*KeepScreenNote\("Pipe line over 511 bytes: dropped", false\);', nx):
    bad.append('every note of this release and every line of the screen\'s own asks LogMustWait() before it goes to the card (LogFiles.h: ten places; Trims.h: two; Nextion.h: the late reply, the pipe line too long)')
# ---- 5: the set came whole, or nothing is saved
tx = code('include/transceiver.h')
for rel, flag, page, what, edit, send, ask, local, reading, hide in (
        ('RF_Rates.h', 'RATES_Loaded', 'page RatesView', 'rates', 'RatesWereEdited', 'SendEditedRates', 'RatesAskValues', 'ShowRatesLocalBank', 'Reading_RATES_Now', 'HideRATESMsg'),
        ('RF_Rates_Advanced.h', 'RATES_ADV_Loaded', 'page Rates_A_View', 'advanced rates', 'RatesAdvancedWereEdited', 'SendEditedRatesAdvanced', 'RatesAdvAskValues', 'ShowLocalRatesAdvancedBank', 'Reading_RATES_Advanced_Now', 'Hide_Advanced_Rates_Msg'),
        ('RF_PID_Advanced.h', 'PIDS_ADV_Loaded', 'page PID_A_View', 'advanced PIDs', 'PIDsAdvancedWereEdited', 'SendEditedPID_Advanced', 'PidAdvAskValues', 'ShowLocalPIDsAdvancedBank', 'Reading_PIDS_Advanced_Now', 'HidePID_Advanced_Msg')):
    t = code('include/' + rel)
    guard = r'if \(RfBlockNotLoaded\(%s, "%s", "%s"\)\)\s*return;' % (flag, re.escape(page), re.escape(what))
    lf = t[t.index('void %s()' % local):]; lf = lf[:lf.index('\n}\n')]
    if not re.search(r'void %s\(\)\s*\{\s*%s' % (edit, guard), t) or not re.search(r'void %s\(\)\s*\{\s*%s' % (send, guard), t):
        bad.append('%s: %s and %s begin with "the set never came whole: its box, and nothing more" - RfBlockNotLoaded(%s, ...)' % (rel, edit, send, flag))
    if len(re.findall(r'\b%s = false;' % flag, t)) != 1 or not re.search(r'%s = false;\s*%s\(\);' % (flag, ask), t) or len(re.findall(r'^\s*%s\(\);' % ask, t, re.M)) != 1:
        bad.append('%s: the page\'s read begins in ONE place, and "%s = false;" stands in front of it (the read-back behind a save asks through RfVerifyArm: what was whole stays whole)' % (rel, flag))
    askf = t[t.index('void %s()' % ask):]; askf = askf[:askf.index('\n}\n')]
    if not re.search(r'RfOtherReadsOver\(\);\s*%s = true;' % reading, askf) or len(re.findall(r'\b%s = true;' % reading, t)) != 1:
        bad.append('%s %s: the page\'s flag is raised in ONE place, behind "RfOtherReadsOver();" (the nineteenth review: a page\'s read is over when another page\'s begins - one read at a time)' % (rel, ask))
    if len(re.findall(r'\b%s = true;' % flag, t)) != 1 or ('%s = true;' % flag) not in lf:
        bad.append('%s %s: the model file\'s own copy is whole by itself - "%s = true;", there and nowhere else in the page\'s file' % (rel, local, flag))
    notmine = tx[tx.index('static void BlockNotMine()'):]; notmine = notmine[:notmine.index('\n}\n')]
    if len(re.findall(r'\b%s = true;' % flag, tx)) != 1 or not re.search(r'else if \(%s\) \{ %s\(\); %s = true; \}' % (reading, hide, flag), tx) or len(re.findall(r'\b%s = false;' % flag, tx)) != 1 or not re.search(r'if \(%s\) %s = false;' % (reading, flag), notmine):
        bad.append('transceiver.h BlockItemSeen: "%s = true;" where the %s set has come whole (its "Loading ..." taken away there), and nowhere else; taken back in ONE place, BlockNotMine (the nineteenth review: the block counted was another page\'s)' % (flag, what))
if 'bool RATES_Loaded = false, RATES_ADV_Loaded = false, PIDS_ADV_Loaded = false;' not in m.DEFS: bad.append('1Definitions.h: the three flags, false at the start')
# ---- 7 (the seventeenth review: three of the 23 places were named by a test): THE WORDS OF A SAVE'S FAILURE, COUNTED FILE BY FILE. Every write step behind a
#      page's first says "PART WRITTEN, NOT STORED (...)", every store step "Written, but NOT STORED", "No answer" goes through RfNoAnswerWords; the
#      old words stand at each page's FIRST write only. A place put back to the old words, or a new step with them, changes a count.
import glob as _g
_inc = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'TransmitterCode', 'include')
for _what, _pat, _pinned in (
        ('"PART WRITTEN, NOT STORED ("', r'PART WRITTEN, NOT STORED \(', {'RF_Basics.h': 5, 'RF_Beeper.h': 1, 'RF_FcSetup.h': 2, 'RF_Filters.h': 1, 'RF_Travel.h': 1}),
        ('"Written, but NOT STORED"', r'Written, but NOT STORED', {'RF_Adjust.h': 1, 'RF_Basics.h': 1, 'RF_Beeper.h': 1, 'RF_CopyBank.h': 1, 'RF_Direction.h': 1, 'RF_FcSetup.h': 3, 'RF_Filters.h': 1, 'RF_Rescue.h': 1, 'RF_SaveNow.h': 1, 'RF_Servos.h': 1, 'RF_Switches.h': 1, 'RF_Travel.h': 1}),
        ('a failure called "Not written" (a page\'s FIRST write)', r'Fail\("Not written', {'RF_Basics.h': 1, 'RF_Beeper.h': 1, 'RF_Direction.h': 1, 'RF_FcSetup.h': 3, 'RF_Filters.h': 1, 'RF_Rescue.h': 1, 'RF_Servos.h': 1, 'RF_Travel.h': 1}),
        ('a failure called "Not stored"', r'Fail\("Not stored"', {}),
        ('RfNoAnswerWords(', r'RfNoAnswerWords\(', {'RF_Adjust.h': 1, 'RF_Basics.h': 1, 'RF_Beeper.h': 1, 'RF_FcSetup.h': 3, 'RF_Filters.h': 1, 'RF_Rescue.h': 1, 'RF_SaveNow.h': 1, 'RF_Servos.h': 1, 'RF_Switches.h': 1, 'RF_Travel.h': 1}),
        ('a plain "No answer" (Copy a bank, the Direction check: their boxes have words of their own)', r'Fail\("No answer"', {'RF_CopyBank.h': 1, 'RF_Direction.h': 1})):
    _now = {os.path.basename(f): len(re.findall(_pat, open(f, encoding='utf-8').read())) for f in sorted(_g.glob(os.path.join(_inc, '*.h')))}; _now = {f: n for f, n in _now.items() if n}
    if _now != _pinned: bad.append('the words of a save\'s failure: %s stands %s - it was %s when the words were last read through (RF_SaveNow.h says which step says what)' % (_what, _now, _pinned))
# ---- 8 (the break-it round of 16 Nov 2026, mut19 QR2 to QR6): THE FIVE PAGES' WAY TO THE MENU IS RfMenuFromPage(what is in hand) - a page that could
#      not be read does not tick the guide's step (RF_SaveNow.h; the run is dev/test_quietroad's, on the Basics page). A page that calls the menu
#      its own way again ticks a step that was never read.
for _h, _have in (('RF_Basics.h', 'BasHave'), ('RF_Filters.h', 'FltHave'), ('RF_Travel.h', 'TravHave'), ('RF_Rescue.h', 'RescueHave'), ('RF_Servos.h', 'ServoHave')):
    _t = re.sub(r'//[^\n]*', '', open(os.path.join(_inc, _h), encoding='utf-8').read())
    if _t.count('RfMenuFromPage(%s);' % _have) != 1 or _t.count('RfMenuFromPage(') != 1 or len(re.findall(r'\bRotorFlightStart\(\)', _t)) != 0:
        bad.append('%s: its one way to the menu is RfMenuFromPage(%s) - found %d such, %d calls of RfMenuFromPage, %d of RotorFlightStart()' % (_h, _have, _t.count('RfMenuFromPage(%s);' % _have), _t.count('RfMenuFromPage('), len(re.findall(r'\bRotorFlightStart\(\)', _t))))
for b in bad: print('FAIL: ' + b)
if bad: sys.exit(1)
_FG = m.release(m.src('include/FlightGuard.h'))
def one_line(head):   # (a routine of one line, as it stands in FlightGuard.h)
    ls = [l for l in _FG.split('\n') if l.startswith(head)]
    if len(ls) != 1 or not ls[0].rstrip().endswith('}'): raise SystemExit('FlightGuard.h: no one-line routine ' + head)
    return ls[0] + '\n'
EXTRA = r'''
namespace guard {
static bool safetyDefined = false, safetyOn = true, MotorEnabled = false, BoundFlag = false, ModelMatched = false;
static bool SafetyIsDefined() { return safetyDefined; } static bool SafetyIsOff() { return SafetyIsDefined() && !safetyOn; }
''' + one_line('bool RadiosMustBeOff()') + one_line('bool LogMustWait()') + r'''
}
'''
SCENES = r'''
    int wrong = 0, cases = 0;
    for (int sd = 0; sd < 2; ++sd) for (int on = 0; on < 2; ++on) for (int motor = 0; motor < 2; ++motor) for (int bound = 0; bound < 2; ++bound) for (int matched = 0; matched < 2; ++matched)
    {
        guard::safetyDefined = sd; guard::safetyOn = on; guard::MotorEnabled = motor; guard::BoundFlag = bound; guard::ModelMatched = matched; ++cases;
        // WITH a safety switch: its "off" alone (its "on" is the pilot's word that the model is on the ground - written at once, a model connected or not).
        // WITH NONE: the motor switch on - or a model connected at all (a glider on the glide, a helicopter in an autorotation, has the motor switch OFF)
        const bool want = sd ? !on : (motor || (bound && matched));
        if (guard::LogMustWait() != want) ++wrong;
        if (guard::RadiosMustBeOff() != (sd ? !on : (bool) motor)) ++wrong;                // (the radios' own rule is as it was)
    }
    say("L. a line for the log waits: %d cases of the safety switch, the motor switch and the model, wrong %d\n", cases, wrong);
    CHECK(cases == 32 && wrong == 0);
    guard::safetyDefined = false; guard::MotorEnabled = false; guard::BoundFlag = guard::ModelMatched = true;
    CHECK(guard::LogMustWait() && !guard::RadiosMustBeOff());                              // the case the fifteenth review found: no safety switch, the motor switch off, a model in the air
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('read_fails', SCENES, extra=EXTRA))
