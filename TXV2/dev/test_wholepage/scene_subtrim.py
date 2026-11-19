#!/usr/bin/env python3
"""THE SUB-TRIM PAGE: A CHANGE IS TAKEN ONLY WHEN IT STARTS FROM WHAT THE MODEL HAS (the eleventh, twelfth and thirteenth reviews, 15 Nov 2026).
The page (the card's 32.json) works by itself: a channel's number tapped sets s0, says "StCH" and puts the slider on that channel's number; the
slider, Zero, "+" and "-" set the slider's number n0, copy it into the chosen channel's own box (n00, n1 .. n15) and say "StEDIT". As released it
said neither WHICH channel a "StEDIT" was made on nor WHAT it made, and a tapped channel did not put its own number into n0. Three cures asked the
page afterwards; each time a reviewer found a road by which the answer was no longer true when it came (the thirteenth review's reviewer B: the
channel left asked last on a screen a quarter second behind; the page come back from Help; a finger resting on the slider).
NOW THE PAGE SAYS WHAT IT DID - "StEDIT", the channel, the slider's number AS IT STOOD, what the touch made of it, and that once more, in one burst
of 22 bytes; a tapped channel puts its own box into the slider's number; "+", "-" and the slider stop at 117 - and Trims.h SubTrimWord takes the
change only when "as it stood" is exactly what the model has for that channel, the two last numbers agree, and the page has said THIS model's
numbers done. Else: not taken, the channel put right on the page. It asks the screen nothing.

 A. THE RULE. A0 the page put up   A1 a drag, a "+", a "-", Zero: each taken, nothing asked of the screen, no wait   A2 a channel tapped, "+" at once
    (every delay): the channel's own number and one - never the channel before's   A3 a change that does not start from the model's number: not
    taken, the channel put right; the next touch taken   A4 "StCH" tells nothing: nothing asked, nothing written
 B. THE THIRTEENTH REVIEW'S ROADS. B1 (his A1, the trace x22b) a screen 250 ms behind, touches 300 ms apart: drag channel 3, tap 7, tap 3, "+"
    B2 (his A2, x18) the page comes back from a box put up over it, two touches thrown away with the page command, its own word lost: "+" on channel 1
    B3 (his A3, x17) A FINGER RESTING ON THE SLIDER: the screen puts the slider back under the finger 40 ms after any write of it, and says the word
    again - one round, and the number is taken; no storm of writes   B4 (his A10) two taps never heard around a slider's word that is heard
    B5 (his A9) a tap between two answers: there are no answers any more - a tap and a "+" in any order
 C. WHAT IS LOST, AND FOUND AGAIN. C1 a word never heard: the page is ahead; the next touch on that channel is refused, the channel put right, the
    one after taken   C2 a write of this board's that never lands   C3 another model read into memory under the open page, a "+" in every order
    with the writes   C4 words not kept for want of room (a wait elsewhere while the finger drags)
 D. THE PAGE FILE FROM BEFORE (its word alone): nothing is taken, ever; the title says so once, and the log.
 E. WHAT THE WORD MAY BE. E1 a channel the page has not got, a burst of another length, the word not at its head, a number beyond what the card
    keeps: nothing taken   E2 EVERY BYTE: all sixteen channels and numbers whose bytes are a reply's head, a frame's mark, a newline, FF FF FF FF -
    read by the main loop, kept through a box's wait, and glued behind a reply: the burst is read by its length, whole
 F. THE CARD'S RULE: 117 either way is what SDcard.h's reader keeps.
 G. THE FOURTEENTH REVIEW. G1 the last number is said twice: a byte more, or a byte lost, at every place of either burst is never another number
    G2 nothing is taken until the page has said THIS model's numbers done (another model read under the open page; the page first put up)
    G3 Help (the screen saver) with a writing-out owed: the page comes back as the model has it   G4 OK stays while a putting-right is owed, or on
    its way, or the page has just come back - and saves when the page has said it done; a "done" lost holds it two seconds; a page that never
    says "done" lets go at once   G5 the page's "done" is no press   G6 the log's line, once a visit   G7 a burst with no channel of the page's
The page's own scripts are run by the pretend screen AT THE MOMENT OF THE TOUCH, in its own time - as 32.json has them (checked below, word for
word, for the page file that stands beside this tree: the one before, or this release's); main.cpp's own lines for the two words and the REAL
Trims.h run over it."""
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
MAINC = m.release(m.src('src/main.cpp')); TRIMS = m.release(m.src('include/Trims.h'))
def block(head):
    i = MAINC.index(head); d = 0; j = MAINC.index('{', i)
    for k in range(j, len(MAINC)):
        if MAINC[k] == '{': d += 1
        elif MAINC[k] == '}':
            d -= 1
            if d == 0: return MAINC[i:k + 1]
    raise SystemExit('no block ' + head)
B1, B2 = block('if (InStrng(StCH, TextIn))'), block('if (InStrng(StEDIT, TextIn))')
B0 = block('if (TextInFramed && TextInLen == SUBTRIM_DONE_BYTES && !memcmp(TextIn, "StEDIT", 6))')   # (the fourteenth review: the page's "done", served in front of everything a press does)
# ---- the source's own lines this scene stands in for
bad = []
mc, tr = re.sub(r'//[^\n]*', '', MAINC), re.sub(r'//[^\n]*', '', TRIMS)
if not re.search(r'if \(CurrentView == SUBTRIMVIEW\)\s*\{\s*SubTrimPageOut\(\);\s*for \(int i = 0; i < 16; \+\+i\)\s*SendText\(fsch_labels\[i\], ChannelNames\[i\]\);\s*\}', mc):
    bad.append('main.cpp UpdateButtonLabels: on the Sub-trim page SubTrimPageOut() and the sixteen names; no box written by another line')
if not re.search(r'void StartSubTrimView\(\)\s*\{\s*SendCommand\(pSubTrimView\);\s*SubTrimToEdit = 0;\s*SubTrimOldPageSaid = false;\s*SubTrimStarts\(\);\s*CurrentView = SUBTRIMVIEW;\s*UpdateButtonLabels\(\);\s*UpdateModelsNameEveryWhere\(\);\s*\}', tr):
    bad.append('Trims.h StartSubTrimView: the page command, "the older page file" not yet said, nothing owed from the last visit (SubTrimStarts), UpdateButtonLabels()')
if re.search(r'SendValue\(\s*(?:n0|h0)\b|"n0"|"h0"', tr[tr.index('#define SUBTRIM_MOST'):tr.index('void EndSubTrimView()')]):
    bad.append('Trims.h, the Sub-trim page: this board writes the channels\' boxes only - never the slider or the slider\'s number (the page sets those by its own channel: "click rs,0")')
if 'SubTrimWord(' in B1 or 'SendValue' in B1 + B2 or 'GetValue' in B1 + B2 or 'SubTrimWord((const uint8_t *)TextIn, TextInLen, TextInFramed);' not in B2:
    bad.append('main.cpp ButtonWasPressed: "StCH" does nothing; "StEDIT" hands its burst to Trims.h SubTrimWord; nothing else asks or writes there')
_poll = tr[tr.index('void SubTrimPoll()'):tr.rindex('static void SubTrimStarts()')]
if len(re.findall(r'\bSubTrimPoll\(\);', mc)) != 1 or re.search(r'\b(?:GetValue|GetText|GetOtherValue|DelayWithDog|CollectReply|while)\b', _poll) \
        or not re.search(r'if \(!SubTrimSettleDue \|\| PendingCount \|\| NEXTION\.available\(\) \|\| \(SubTrimWordMs && \(int32_t\)\(millis\(\) - SubTrimWordMs\) < SUBTRIM_REST_MS\)\)\s*return;\s*SubTrimSettleDue = false;\s*SubTrimPageOut\(false\);', _poll):
    bad.append('Trims.h SubTrimPoll, called once from the main loop: the page written out ONCE when that is due, no word waits and the pilot has paused; it asks nothing and waits for nothing')
# (the fourteenth review) the page's "done" in front of everything a press does; the page put up again is written out (both roads); OK with a writing-out owed stays
_bwp = mc[mc.index('void ButtonWasPressed()'):]
if not (0 < _bwp.find('if (TextInFramed && TextInLen == SUBTRIM_DONE_BYTES && !memcmp(TextIn, "StEDIT", 6))') < _bwp.find('HandleChannelNameEvents();') < _bwp.find('StartInactvityTimeout();')) \
        or not re.fullmatch(r'if \(TextInFramed && TextInLen == SUBTRIM_DONE_BYTES && !memcmp\(TextIn, "StEDIT", 6\)\)\s*\{\s*if \(CurrentView == SUBTRIMVIEW\)\s*SubTrimWord\(\(const uint8_t \*\)TextIn, TextInLen, TextInFramed\);\s*ClearText\(\);\s*return;\s*\}', re.sub(r'//[^\n]*', '', B0)):
    bad.append('main.cpp ButtonWasPressed: the Sub-trim page\'s "done" (framed, SUBTRIM_DONE_BYTES, "StEDIT") is handed to SubTrimWord and ends there - in front of the names\' events and of the idle and screen saver clocks')
_ut = re.sub(r'//[^\n]*', '', m.release(m.src('include/Utilities.h')))
if len(re.findall(r'if \(CurrentView == SUBTRIMVIEW\)\s*SubTrimPageBack\(\);', mc)) != 1 or len(re.findall(r'case SUBTRIMVIEW:\s*SubTrimPageBack\(\);\s*break;', _ut)) != 1 \
        or not re.search(r'void SubTrimPageBack\(\)\s*\{\s*SubTrimStarts\(\);\s*UpdateButtonLabels\(\);\s*if \(SubTrimOldPageSaid\)\s*SendCommand\(\(char \*\)"vis ModelName,0"\);\s*\}', tr):
    bad.append('the Sub-trim page put up again without its Start (main.cpp, Help\'s way back; Utilities.h SaveOrRestoreScreen) is written out as the model has it: SubTrimPageBack() - nothing owed, UpdateButtonLabels()')
if not re.search(r'void EndSubTrimView\(\)\s*\{\s*if \(PendingDropped != SubTrimDropsSeen\)\s*\{\s*SubTrimDropsSeen = PendingDropped;\s*SubTrimSettleDue = true;\s*\}\s*if \(SubTrimSettleDue\)\s*\{\s*SubTrimSettleDue = false;\s*SubTrimPageOut\(false\);\s*PlaySound\(WHAHWHAHMSG\);\s*return;\s*\}\s*'
                 r'if \(SubTrimSaysDone && SubTrimDone != SubTrimAsked\)\s*\{\s*if \(\(uint32_t\)\(millis\(\) - SubTrimAskedMs\) < SUBTRIM_DONE_WAIT_MS\)\s*\{\s*PlaySound\(WHAHWHAHMSG\);\s*return;\s*\}\s*'
                 r'if \(SubTrimAskedAgain < SUBTRIM_ASK_AGAIN_MOST\)\s*\{\s*const uint8_t again = SubTrimAskedAgain;\s*SubTrimResync\(\);\s*SubTrimAskedAgain = \(uint8_t\)\(again \+ 1\);\s*PlaySound\(WHAHWHAHMSG\);\s*return;\s*\}\s*\}\s*char page_RXSetupView', tr) \
        or len(re.findall(r'SubTrimSaysDone = true;', tr)) != 3 or re.search(r'SubTrimSaysDone = false;', tr[tr.index('static bool SubTrimSaysDone = false;') + 40:]) \
        or not re.search(r'SubTrimDone = SubTrimAsked;\s*SubTrimShown = true;\s*SubTrimSaysDone = true;\s*SubTrimAskedAgain = 0;', tr) \
        or len(re.findall(r'SubTrimAskedAgain = 0;', tr)) != 5 or len(re.findall(r'\+\+SubTrimAskedAgain', tr)) != 0 or not re.search(r'#define SUBTRIM_ASK_AGAIN_MOST 2\b', tr) \
        or not re.search(r'static void SubTrimStarts\(\)\s*\{\s*SubTrimWordMs = 0;\s*SubTrimSettleDue = false;\s*SubTrimNoteSaid = false;\s*SubTrimAskedAgain = 0;\s*SubTrimDropsSeen = PendingDropped;\s*\}', tr) \
        or not re.search(r'SubTrimSettleDue = true;\s*return;\s*\}\s*SubTrimSaysDone = true;\s*const int32_t ch = SubTrimNumberAt\(w \+ 6\)', tr) \
        or len(re.findall(r'SubTrimAskedMs = millis\(\);', tr)) != 1 or not re.search(r'SubTrimAsked = 1;\s*SubTrimAskedAgain = 0;\s*SubTrimAskedMs = millis\(\);\s*SendValue\(\(char \*\)"rsn", SubTrimAsked\);', tr):
    bad.append('Trims.h EndSubTrimView: OK while a writing-out is owed writes the page out and STAYS; OK before the page has said this board\'s last click done (within SUBTRIM_DONE_WAIT_MS of that click) stays too - and past that time clicks "rs" ONCE MORE and stays, SUBTRIM_ASK_AGAIN_MOST times at most (counted from EVERY NEW CLICK of this board\'s - SubTrimResync, the seventeenth review; OK\'s own click is counted behind it - and from the last "done", the page being put up and a fresh writing-out) - on every page that says "done" at all '
               '(SubTrimSaysDone: set by a "done" and by a burst in this release\'s form, served or let go; never cleared) - nothing is saved behind a number the page shows and the model has not got')
if len(re.findall(r'\bSubTrimPageOut\(\);', tr + mc + _ut)) != 1 or not re.search(r'void SubTrimPageOut\(bool fresh\)\s*\{\s*if \(fresh\)\s*SubTrimAskedAgain = 0;\s*if \(fresh\)\s*SubTrimShown = false;', tr) \
        or len(re.findall(r'SubTrimShown = true;', tr)) != 1 or not re.search(r'if \(framed && done == SubTrimNumberAt\(w \+ 10\) && done == \(int32_t\)SubTrimAsked\)\s*\{\s*SubTrimDone = SubTrimAsked;\s*SubTrimShown = true;\s*SubTrimSaysDone = true;\s*SubTrimAskedAgain = 0;\s*\}', tr) \
        or not re.search(r'if \(made == again && SubTrimShown && stood == \(int32_t\)SubTrims\[c\] - 127 && made >= -SUBTRIM_MOST && made <= SUBTRIM_MOST\)', tr):
    bad.append('Trims.h: a FRESH writing-out (main.cpp UpdateButtonLabels - the one SubTrimPageOut() with no word) takes "the page shows this model" away; only the page\'s "done" of this board\'s last click, framed, its number said twice alike, gives it back; '
               'and a touch is taken only then, when its two last numbers agree, it started from the model\'s number and stays within the most')
_nx = re.sub(r'//[^\n]*', '', m.release(m.src('include/Nextion.h')))
if not re.search(r'void SubTrimWordLetGo\(const uint8_t \*f, uint16_t n, bool framed\)\s*\{\s*if \(n < 6 \|\| n == SUBTRIM_DONE_BYTES \|\| memcmp\(f, "StEDIT", 6\)\)\s*return;\s*'
                 r'if \(framed && n == SUBTRIM_WORD_BYTES\)\s*SubTrimSaysDone = true;\s*if \(CurrentView != SUBTRIMVIEW\)\s*return;\s*SubTrimWordMs = millis\(\) \| 1;\s*SubTrimSettleDue = true;\s*\}', tr) \
        or len(re.findall(r'\bSubTrimWordLetGo\(f, n, framed\);', _nx)) != 3 or len(re.findall(r'\bSubTrimWordLetGo\(', _nx)) != 4 \
        or not re.search(r'if \(IsPress\(\(const uint8_t \*\)PendingEvent \+ from, n, PendingFramedFlags\[i\]\)\)\s*\{\s*NoteStalePress\(\(const uint8_t \*\)PendingEvent \+ from, n\);\s*SubTrimWordLetGo\(\(const uint8_t \*\)PendingEvent \+ from, n, PendingFramedFlags\[i\]\);\s*\}', _nx) \
        or not re.search(r'if \(ScreenMarkOldPage\)\s*\{\s*NoteStalePress\(f, n\);\s*SubTrimWordLetGo\(f, n, framed\);\s*return true;\s*\}\s*if \(IsLoadPrint\(f, n, framed\)\)\s*return false;\s*if \(LoadPrintsLetGo < 65535\)\s*\+\+LoadPrintsLetGo;\s*SubTrimWordLetGo\(f, n, framed\);\s*return true;', _nx) \
        or not re.search(r'\+\+PendingDropped;\s*SubTrimWordLetGo\(f, n, framed\);\s*return;', _nx) or 'void SubTrimWordLetGo(const uint8_t *f, uint16_t n, bool framed);' not in m.DEFS:
    bad.append('a frame this board lets go unserved (Nextion.h DropUnconfirmedPress, both ways out; PendingPush with no room) - and a kept press purged with its page (PurgeKeptPresses, the seventeenth review) - is told to Trims.h SubTrimWordLetGo: a touch\'s burst of the Sub-trim page\'s - not its "done" - says what kind of page file said it ON WHATEVER PAGE this board is (the sixteenth review), and on that page '
               'owes the page its writing-out (SubTrimSettleDue, behind the pause), and one in this release\'s form says that the page says "done"')
# (the fifteenth review, both reviewers: nothing held these lines - each taken out, or a plausible new routine beside them, passed every test)
_sd = re.sub(r'//[^\n]*', '', m.release(m.src('include/SDcard.h')))
_rom = _sd[_sd.index('bool ReadOneModel('):]; _rom = _rom[:_rom.index('\n}\n')]
if len(re.findall(r'\breturn true;', _rom)) != 1 or not re.search(r'UpdateButtonLabels\(\);\s*CheckMacrosBuffer\(\);\s*return true;\s*$', _rom) \
        or len(re.findall(r'\breturn false;', _rom)) != len(re.findall(r'\breturn false;', _rom[:_rom.index('SubTrims[')])):
    bad.append('SDcard.h ReadOneModel: its ONE "return true" stands behind UpdateButtonLabels() - the line that turns a model\'s read into the Sub-trim page\'s fresh writing-out ("another model read under the open page") - and no way out behind the first sub trim read goes round it')
import glob as _glob
_writers = {}
for _f in sorted(_glob.glob(os.path.join(m.ROOT, 'TransmitterCode', 'include', '*.h'))) + [os.path.join(m.ROOT, 'TransmitterCode', 'src', 'main.cpp')]:
    _t = re.sub(r'//[^\n]*', '', open(_f, encoding='utf-8', errors='replace').read())
    _n = len(re.findall(r'\bSubTrims\s*\[[^\]]*\]\s*(?:=[^=]|[-+*/|&^]=|\+\+|--)|(?:\+\+|--)\s*SubTrims\s*\[|\bmem(?:set|cpy|move)\s*\(\s*SubTrims\b|\bstrcpy\s*\(\s*\(char \*\)\s*SubTrims\b', _t))
    if _n: _writers[os.path.basename(_f)] = _n
if _writers != {'Trims.h': 2, 'SDcard.h': 2, 'Utilities.h': 1, 'main.cpp': 1}:
    bad.append('THE WRITERS OF SubTrims[] ARE ON A LIST - Trims.h (the page\'s one taking; the trims moved into sub trim, on the Trim page), SDcard.h (the model\'s read: UpdateButtonLabels behind it), Utilities.h and main.cpp (a model set to its defaults, from the models\' pages). '
               'A new writer that can run with the Sub-trim page up must write the page out FRESH (SubTrimPageOut()) - and be put on this list: found %s' % sorted(_writers.items()))
_all = ''.join(re.sub(r'//[^\n]*', '', open(_f, encoding='utf-8', errors='replace').read()) for _f in sorted(_glob.glob(os.path.join(m.ROOT, 'TransmitterCode', 'include', '*.h'))) + [os.path.join(m.ROOT, 'TransmitterCode', 'src', 'main.cpp')])
if len(re.findall(r'\bpSubTrimView\b', _all)) != 2 or _all.count('page SubTrimView') != 1 or not re.search(r'void StartSubTrimView\(\)\s*\{\s*SendCommand\(pSubTrimView\);', tr):
    bad.append('THE SUB-TRIM PAGE\'S PAGE COMMAND STANDS IN ONE PLACE - Trims.h StartSubTrimView (its text in 1Definitions.h, once). Whatever else puts the page up again does so by the page\'s own road and writes it out: SubTrimPageBack()')
if len(re.findall(r'\bSubTrimBoxOut\(', _all)) != 3 or len(re.findall(r'\bSubTrimBoxOut\(', tr)) != 3 \
        or not re.search(r'for \(uint8_t ch = 0; ch < 16; \+\+ch\)\s*SubTrimBoxOut\(ch\);\s*SubTrimResync\(\);', tr) or not re.search(r'SubTrimBoxOut\(c\);\s*SubTrimResync\(\);\s*SubTrimSettleDue = true;\s*\}', tr):
    bad.append('Trims.h: a channel\'s box is written in two places only - the page\'s writing-out (all sixteen, then the click) and a change not taken (that channel, then the click): every write of a box is followed by a click of "rs"')
if 'void SubTrimPageOut(bool fresh = true);' not in m.DEFS or 'void SubTrimPageBack();' not in m.DEFS: bad.append('1Definitions.h: SubTrimPageOut(bool fresh = true) and SubTrimPageBack() (this scene says the same two lines)')
# (the sixteenth review, reviewer A: the checks above read FORMS - and saw none of five natural next-week ones: a writer "for (uint8_t &s : SubTrims) s = 127;",
#  a way back made of parts "page %s" with "SubTrimView", a box written by SubTrimBoxName + SendValue, a way out "return ModelDefined != 0;" behind the
#  sub trims ...) So THE NAMES ARE COUNTED, file by file, with the comments taken out: a new use of the sub trims, of the page's name, or of a box's
#  name - in whatever form - stops here until it has been looked at (does it write the page out? does it owe a writing-out?) and its count put in.
import glob as _glob
_TC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'TransmitterCode')
def _bare(path):
    t = open(os.path.join(_TC, path), encoding='utf-8', errors='replace').read()
    return re.sub(r'//[^\n]*', '', re.sub(r'/\*.*?\*/', '', t, flags=re.S))
_files = sorted(os.path.relpath(f, _TC) for f in _glob.glob(os.path.join(_TC, 'include', '*.h'))) + ['src/main.cpp']
for _what, _pat, _pinned in (('the sub trims (SubTrims)', r'\bSubTrims\b', {'include/1Definitions.h': 1, 'include/FlightGuard.h': 1, 'include/RF_Adjust.h': 1, 'include/SDcard.h': 5, 'include/Trims.h': 7, 'include/Utilities.h': 1, 'src/main.cpp': 2}),
                              ('the page\'s name ("...SubTrimView")', r'SubTrimView"', {'include/1Definitions.h': 1, 'include/Utilities.h': 1}),
                              ('a box\'s name (SubTrimBoxName()', r'\bSubTrimBoxName\(', {'include/Trims.h': 2}),
                              ('the page\'s own number (SUBTRIMVIEW)', r'\bSUBTRIMVIEW\b', {'include/Trims.h': 3, 'include/Utilities.h': 2, 'src/main.cpp': 4})):
    _now = {f: len(re.findall(_pat, _bare(f))) for f in _files}; _now = {f: n for f, n in _now.items() if n}
    if _now != _pinned:
        bad.append('%s: named %s - it was %s when the Sub-trim rule was last read through. A new use, in whatever form: look at it (a writer of the sub trims writes the page out; a way back to the page writes it out; '
                   'a box written owes the slider its number), then put the new count into dev/test_wholepage/scene_subtrim.py' % (_what, _now, _pinned))
_sd = _bare('include/SDcard.h'); _m = re.search(r'\n[^\n;]*\bReadOneModel\([^)]*\)\s*\{', _sd); _j = _sd.index('{', _m.start()); _d = 0
for _k in range(_j, len(_sd)):
    _d += _sd[_k] == '{'; _d -= _sd[_k] == '}'
    if _d == 0: break
_body = _sd[_j:_k + 1]
if len(re.findall(r'\breturn\b', _body[_body.index('SubTrims['):])) != 1 or not re.search(r'return true;\s*\}\s*$', _body):
    bad.append('SDcard.h ReadOneModel: behind the first sub trim it has read there is ONE way out - its last line, "return true;" (a way out of any form in between leaves the open Sub-trim page '
               'showing the model before: the page is written out behind the whole read)')
for b in bad: print(('FAIL: ' if not os.environ.get('LDRC_RUNS_ONLY') else '(a source check, not held in this run: LDRC_RUNS_ONLY) ') + b)
if bad and not os.environ.get('LDRC_RUNS_ONLY'): sys.exit(1)   # (LDRC_RUNS_ONLY: the break-it round's second look - does a RUN notice a rule taken out, with the text checks set aside?)
# ---- the page's own scripts, as the card has them (the screen's repository beside this one): THE ONE BEFORE, or THIS RELEASE'S
from page32 import page_kind   # (the page file, word for word: 'old' or 'new' - one definition, the release's too)
# (the fifteenth review, reviewer A: this release's page file was read from a scratch folder, the one before from the screen's repository - with either
#  gone, or the repository's page become this release's, the scenes that run the REAL page said "ALL GOOD" without running. BOTH PAGE FILES ARE KEPT
#  HERE, beside the tests, each held to its pin (page32.py); the screen's repository's own page - whichever of the two it is by now - is looked at too.)
PAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pages')
PAGE = os.path.join(PAGES_DIR, '32_before_b211.json')                                   # the page file from before this release (the field's: screens to 1.11.197)
NEWPAGE = os.environ.get('LDRC_NEW_PAGE32', os.path.join(PAGES_DIR, '32_b211.json'))    # this release's
REPO_PAGE = os.path.join(os.path.dirname(m.ROOT), 'ESP32-board2', 'board4', 'nextion-emulator', 'sd', 'hmi', 'pages', '32.json')
if page_kind(PAGE) != 'old' or page_kind(NEWPAGE) != 'new': print('FAIL: dev/test_wholepage/pages: the two Sub-trim page files are not "the one before" and "this release\'s"'); sys.exit(1)
if os.path.exists(REPO_PAGE): page_kind(REPO_PAGE)                                      # (an AssertionError when it is neither of the two, word for word)
KINDS = ['old', 'new']
assert TRIMS.count('    UpdateButtonLabels(); // (SubTrimPageOut, fresh; and the sixteen names)') == 1
BLOCK = TRIMS[TRIMS.index('#define SUBTRIM_MOST 117'):TRIMS.index('/******', TRIMS.index('FLASHMEM void SubTrimPoll()'))].replace('    UpdateButtonLabels(); // (SubTrimPageOut, fresh; and the sixteen names)', '    SubTrimPageOut(); // (main.cpp UpdateButtonLabels, on this page: SubTrimPageOut and the sixteen names - held from the source, above)').replace('extern uint16_t PendingDropped; // (Nextion.h: the frames not kept for want of room)\nextern uint8_t PendingCount;\n', '')
assert 'extern' not in BLOCK
assert BLOCK.count('FLASHMEM void SubTrimWordLetGo(') == 1   # (the harness has a stand-in of that name, which hands on to this one: the real routine, under another name here)
BLOCK = BLOCK.replace('FLASHMEM void SubTrimWordLetGo(', 'FLASHMEM void RealSubTrimWordLetGo(')
EXTRA = r'''
static uint8_t SubTrims[16]; static uint8_t SubTrimToEdit = 0; static bool SubTrimOldPageSaid = false; static void SubTrimStarts();
@CARDRULE@
void SubTrimPageOut(bool fresh = true); void SubTrimPageBack();   // (1Definitions.h's own two lines - held below)
''' + BLOCK + r'''
static bool letGoHooked = (subTrimLetGo = RealSubTrimWordLetGo, true);   // (Nextion.h's calls reach Trims.h's own routine)
''' + m.lift(TRIMS, 'void EndSubTrimView()') + r'''
static void subtrimWord()   // src/main.cpp ButtonWasPressed's own lines for "StCH" and "StEDIT"
{
    char StCH[] = "StCH"; char StEDIT[] = "StEDIT";
    ''' + B0 + '\n    ' + B1 + '\n    ' + B2 + r'''
}
static long stServed = 0;
static bool stWords(const char *w) { if (strncmp(w, "St", 2)) return false; ++stServed; subtrimWord(); return true; }
static const char *boxOf(int ch) { static char b[16][6]; if (ch == 1) return "n00"; snprintf(b[ch - 1], 6, "n%d", ch - 1); return b[ch - 1]; }   // channel 1 to 16 -> n00, n1 .. n15
static Page &P() { return screen.pages["SubTrimView"]; }
static long &B(const char *n) { return P().boxes[n].val; }
// ---- THE PAGE'S OWN SCRIPTS (32.json), run by the pretend screen at the moment of the touch, in its own time: THIS RELEASE'S page file (pageNew) or the one before
static bool pageNew = true;
static long pageMost() { return pageNew ? 117 : 127; }
static std::deque<int> slideTo;                          // where the slider goes at its next touches, in their order (0 - 254)
struct Touch { int ch; long stood, made; int epoch; };   // THE BOOK: every touch the pilot made, as the page did it - on which channel, from which number, to which; and the model whose numbers the page had then (-1: none's for sure)
static std::vector<Touch> touches;
// (the fourteenth review, reviewer B's strict book) THE PAGE SHOWS THIS MODEL once it has run a click of "rs" that this board made at or behind the writing-out of this model's numbers
static uint16_t modelClick = 0; static bool pageShowsModel = false; static int modelEpoch = 0; static uint64_t lastSliderUs = 0;
static uint16_t nextClick() { const uint16_t n = (uint16_t) (SubTrimAsked + 1); return n ? n : 1; }   // (Trims.h SubTrimResync: the click's number goes round past 65535 to 1 - never 0)
static void freshOut() { ++modelEpoch; pageShowsModel = false; modelClick = nextClick(); SubTrimPageOut(); if (modelClick != SubTrimAsked) { printf("freshOut: the writing-out did not click once\n"); exit(3); } }   // the page is put up, or ANOTHER MODEL read under it (main.cpp UpdateButtonLabels)
static void pageBack() { pageShowsModel = false; modelClick = nextClick(); SubTrimPageBack(); if (modelClick != SubTrimAsked) { printf("pageBack: the writing-out did not click once\n"); exit(3); } }   // the page put up again by this board (Help's way back, the screen saver's): the same model
static bool fingerDown = false; static int fingerAt = 127;   // A FINGER RESTING ON THE SLIDER (the real screen's pollTouch: 40 ms after any write of the slider it is put back under the finger, and the page says so)
static std::vector<uint8_t> stSaid(long ch, long stood, long made)
{
    std::vector<uint8_t> b = { 'S', 't', 'E', 'D', 'I', 'T' };
    if (pageNew) for (long v : { ch, stood, made, made }) for (int k = 0; k < 4; ++k) b.push_back((uint8_t) ((uint32_t) (int32_t) v >> (8 * k)));   // print s0.val / print n0.val / ... / print n0.val / print n0.val
    return b;
}
static bool byFinger[17];   // (the fifteenth review's book) the number a channel's box shows was made by a FINGER since this board last wrote that box
static void boardWrote(const char *c) { for (int ch = 1; ch <= 16; ++ch) { const std::string nm = std::string(boxOf(ch)) + ".val="; if (!strncmp(c, nm.c_str(), nm.size())) byFinger[ch] = false; } }
static void stTap(const char *button)
{
    if (screen.page != "SubTrimView") return;
    std::string b = button; if (!b.empty() && b.back() == '!') b.pop_back();                                    // ("ch7!": the same touch, its word never heard)
    if (b.rfind("ch", 0) == 0) { const int ch = atoi(b.c_str() + 2); B("s0") = ch; if (pageNew) B("n0") = B(boxOf(ch)); B("h0") = B(boxOf(ch)) + 127; return; }   // s0.val=K  [n0.val=nK.val]  print "StCH"  h0.val=nK.val+127
    const long stood = B("n0");
    const bool unheard = std::string(button).back() == '!';
    if (b == "slider")
    {   // THE FINGER ON THE SLIDER - it lands, or moves (this release's page says the word at both; steps closer than 85 ms are one drag)
        long to = slideTo.empty() ? B("h0") : slideTo.front(); if (!slideTo.empty()) slideTo.pop_front();
        if (to < 127 - pageMost()) to = 127 - pageMost(); if (to > 127 + pageMost()) to = 127 + pageMost();     // (the slider's own limits: minval, maxval)
        B("h0") = to; B("n0") = to - 127;
        lastSliderUs = screen.at;
        if (!fingerDown) screen.taps.insert({ screen.at + 85000, unheard ? "lift!" : "lift" });                  // ... and 85 ms behind the last of them, the finger gone: the slider's RELEASE
    }
    else if (b == "lift")
    {   // THE SLIDER'S RELEASE: the same script - the slider is NOT moved, so it says "from X to X" unless something wrote the slider meanwhile
        if (fingerDown || screen.at - lastSliderUs < 84000) { P().buttons[button] = {}; P().raw.insert(button); return; }   // (the finger is still there, or has moved since: this is not its release - nothing is said)
        if (!unheard) P().raw.erase(button);
        B("n0") = B("h0") - 127;
    }
    else if (b == "plus") { long &n = B("n0"); n += 1; if (n > pageMost()) n = pageMost(); B("h0") = n + 127; }
    else if (b == "minus") { long &n = B("n0"); n -= 1; if (n < -pageMost()) n = -pageMost(); B("h0") = n + 127; }
    else if (b == "zero") { B("n0") = 0; B("h0") = 127; }
    else return;
    const long ch = B("s0");
    if (ch >= 1 && ch <= 16) { if (B(boxOf((int) ch)) != B("n0")) byFinger[ch] = true; B(boxOf((int) ch)) = B("n0"); }   // click n0,0: the chosen channel's own box = n0
    touches.push_back({ (int) ch, stood, B("n0"), pageShowsModel ? modelEpoch : -1 });
    const std::vector<uint8_t> said = stSaid(ch, stood, B("n0"));
    P().buttons[button] = unheard ? std::vector<uint8_t>() : said;                                               // (what this touch prints: the pretend screen sends the button's bytes behind this script)
}
static void stLoad(const char *page) { if (!strcmp(page, "SubTrimView")) { B("s0") = 1; if (pageNew) B("n0") = B("n00"); B("h0") = B("n00") + 127; lastSliderUs = screen.at; } }   // preinitialize: click n00,0 (s0 is the page's own: 1 again; the boxes, n0 and h0 keep their numbers)
static std::vector<std::string> writes; static std::string loseWrite; static int loseLeft = 0;
static bool (*doneLostNow)() = nullptr;                  // (a storm's knob: this "done" is said by the page and never heard)
static std::vector<uint8_t> lastDone; static bool doneToWire = true;   // what the page's part "rs" said when it last ran (scene_subtrim_page holds it against the real page's, and keeps it off the wire)
static void stFinger() { if (fingerDown && screen.page == "SubTrimView" && B("h0") != fingerAt) { slideTo.push_back(fingerAt); screen.taps.insert({ nowUs + 40000, "slider" }); } }   // the finger is still there: the slider goes back under it 40 ms on, and the page says so
static bool stCmd(const char *c)                         // every command of this board's as the screen handles it: the writes, in their order - and those that never land
{
    const bool click = !strcmp(c, "click rs,0");
    if (!click && !strstr(c, ".val=")) return false;
    if (loseLeft > 0 && !strncmp(c, loseWrite.c_str(), loseWrite.size())) { --loseLeft; return true; }
    if (!strncmp(c, "rsn.val=", 8)) return false;        // (the number of this board's next click: the page's own variable - kept by the screen as any box is; not one of the boxes' writes)
    writes.push_back(c); boardWrote(c);
    if (click)
    {   // THE PAGE'S PART "rs" (this release's page file): the slider's number and the slider on the box of the channel the page shows - and it SAYS
        // "StEDIT" and the number in "rsn": done. A page file from before has no such part: nothing happens, nothing is said
        lastDone.clear();
        if (pageNew && screen.page == "SubTrimView")
        {
            if (B("s0") >= 1 && B("s0") <= 16) B("n0") = B(boxOf((int) B("s0")));
            B("h0") = B("n0") + 127;                     // (h0.val=n0.val+127 stands outside the sixteen ifs)
            lastDone = { 'S', 't', 'E', 'D', 'I', 'T' }; for (int twice = 0; twice < 2; ++twice) for (int k = 0; k < 4; ++k) lastDone.push_back((uint8_t) ((uint32_t) (int32_t) B("rsn") >> (8 * k)));   // print "StEDIT" / print rsn.val / print rsn.val
            if ((uint16_t) ((uint16_t) B("rsn") - modelClick) < 0x8000) pageShowsModel = true;                       // (the click of this model's writing-out, or a later one: the boxes written in front of it have landed)
            if (doneToWire && !(doneLostNow && doneLostNow())) screen.burst(nowUs + 200, lastDone);
            stFinger();
        }
        return true;
    }
    if (!strncmp(c, "h0.val=", 7)) { const long v = atol(c + 7); if (v != fingerAt && fingerDown) { slideTo.push_back(fingerAt); screen.taps.insert({ nowUs + 40000, "slider" }); } }
    return false;
}
static void addSubTrim()
{
    Page s; s.id = 32;
    for (const char *t : { "s0", "n0", "h0", "rsn" }) s.boxes[t] = { false, 0, "" };
    for (int ch = 1; ch <= 16; ++ch) s.boxes[boxOf(ch)] = { false, 0, "" };
    s.boxes["t0"] = { true, 0, "Subtrim" }; s.boxes["ModelName"] = { true, 0, "" };
    const char *st = "StCH";
    for (int ch = 1; ch <= 16; ++ch) { char n[8]; snprintf(n, sizeof n, "ch%d", ch); s.buttons[n] = std::vector<uint8_t>(st, st + 4); snprintf(n, sizeof n, "ch%d!", ch); s.buttons[n] = {}; s.raw.insert(n); }
    for (const char *b : { "slider", "plus", "minus", "zero", "lift" }) { s.buttons[b] = {}; std::string q = std::string(b) + "!"; s.buttons[q] = {}; s.raw.insert(q); }
    s.loadPrint = std::vector<uint8_t>(st, st + 4);      // (the page taps its first channel by itself as it comes up, and says so)
    screen.pages["SubTrimView"] = s; screen.pages0 = screen.pages;
    for (int i = 0; i < 16; ++i) SubTrims[i] = 127;
    SubTrims[6] = 97;                                    // channel 7's sub trim: -30
    SubTrimToEdit = 0; SubTrimOldPageSaid = false; stServed = 0; SubTrimStarts();
    wordHook = stWords; tapScript = stTap; loadScript = stLoad; cmdScript = stCmd; slideTo.clear(); writes.clear(); loseWrite.clear(); loseLeft = 0; touches.clear(); fingerDown = false; modelClick = SubTrimAsked; pageShowsModel = false; lastSliderUs = 0;
}
static void stLoop(uint32_t ms) { const uint64_t until = nowUs + (uint64_t) ms * 1000; while (nowUs < until) { const uint64_t t0 = nowUs; LoopPass(); SubTrimPoll(); if (gapWatch && nowUs - t0 > maxPassUs) maxPassUs = nowUs - t0; nowUs += 500; } }   // the main loop: the look for a press, and Trims.h SubTrimPoll
static void openSubTrim()                                // Trims.h StartSubTrimView (main.cpp UpdateButtonLabels: SubTrimPageOut and the names)
{
    SendCommand((char *) "page SubTrimView"); SubTrimToEdit = 0; SubTrimOldPageSaid = false; SubTrimStarts(); CurrentView = SUBTRIMVIEW;
    freshOut();
    stLoop(700);
}
static void tapCh(uint32_t ms, int ch, bool heard = true) { char n[8]; snprintf(n, sizeof n, heard ? "ch%d" : "ch%d!", ch); tapAt(ms, n); }
static void slide(uint32_t ms, int to, bool heard = true) { slideTo.push_back(to + 127); tapAt(ms, heard ? "slider" : "slider!"); }   // (to: the sub trim, -127 to 127)
static int trim(int ch) { return SubTrims[ch - 1] - 127; }
static int shown(int ch) { return (int) B(boxOf(ch)); }
static bool pageIsModel() { for (int ch = 1; ch <= 16; ++ch) if (shown(ch) != trim(ch)) return false; return true; }   // every box shows what the model has
static bool sliderIsShown() { const long ch = B("s0"); return ch >= 1 && ch <= 16 && B("n0") == shown((int) ch) && B("h0") == shown((int) ch) + 127; }   // ... and the slider and its number are the shown channel's
static bool othersAre(int a, int b = 0, int c = 0) { for (int ch = 1; ch <= 16; ++ch) if (ch != a && ch != b && ch != c && SubTrims[ch - 1] != (ch == 7 ? 97 : 127)) return false; return true; }
static bool wasMade(int ch, long from, long to) { for (auto &t : touches) if (t.ch == ch && t.stood == from && t.made == to) return true; return false; }   // the pilot made that change, on that channel
static bool wasMadeOnModel(int ch, long from, long to) { for (auto &t : touches) if (t.epoch == modelEpoch && t.ch == ch && t.stood == from && t.made == to) return true; return false; }   // ... on a page that had THIS model's numbers
static void fingerUp() { if (fingerDown && screen.page == "SubTrimView") { lastSliderUs = nowUs; screen.taps.insert({ nowUs + 85000, "lift" }); } fingerDown = false; }   // the finger that rested on the slider goes: its release, 85 ms on
static void burstNow(const std::vector<uint8_t> &payload) { std::vector<uint8_t> f = { 0x7E, 0x7E, (uint8_t) payload.size(), (uint8_t) (payload.size() >> 8) }; f.insert(f.end(), payload.begin(), payload.end()); screen.emit(nowUs + 200, f); }   // a framed burst, said by hand
'''
SCENES = r'''
  for (int kind = 1; kind >= 0; --kind)
  {
  pageNew = kind != 0;
  if (!pageNew) goto olderPage;
  // ===================================================================================================== A. THE RULE
  // A0. THE PAGE IS PUT UP: every box, the slider and its number as the model has them; nothing is asked of the screen
  {
    more(); addSubTrim(); openSubTrim();
    CHECK(pageIsModel() && sliderIsShown() && B("s0") == 1 && boxesLostTold == 0 && writes.size() == 17 && writes[0] == "n00.val=0" && writes[6] == "n6.val=-30" && writes[15] == "n15.val=0" && writes[16] == "click rs,0");   // the sixteen boxes, then the page told to set its slider by its own box
    const int gets0 = screen.gets; SubTrimPageOut(); stLoop(300);            // (the page's writes themselves: no question among them - the page command's own markers are not this page's)
    say("A0. the page put up: channel 7 shows %d (the model has -30), the slider %ld and its number %ld are channel 1's; asked of the screen by the page's writes: %d\n", shown(7), B("h0"), B("n0"), screen.gets - gets0);
    CHECK(pageIsModel() && sliderIsShown() && screen.gets == gets0);
  }
  // A1. a drag, "+", "-", Zero on channel 1: each taken as it comes - and NOTHING ASKED of the screen, no wait (each word cost two questions and more)
  {
    more(); addSubTrim(); openSubTrim(); const int gets0 = screen.gets; gapWatch = true; lastRadioUs = nowUs; maxRadioGapUs = 0; maxPassUs = 0;
    for (int i = 1; i <= 20; ++i) slide(10 + i * 30, i);                        // a drag: a step every 30 ms
    stLoop(900); CHECK(trim(1) == 20 && pageIsModel() && sliderIsShown());
    tapAt(10, "plus"); tapAt(150, "plus"); tapAt(290, "minus"); stLoop(600); CHECK(trim(1) == 21 && pageIsModel());
    tapAt(10, "zero"); stLoop(300); CHECK(trim(1) == 0 && pageIsModel() && sliderIsShown());
    say("A1. a drag of 20 steps, + + -, Zero on channel 1: taken each; asked of the screen %d, the loop's longest pass %.1f ms, the radio's longest silence %.1f ms; words served %ld\n", screen.gets - gets0, maxPassUs / 1e3, radioGapUs() / 1e3, stServed);
    CHECK(screen.gets == gets0 && maxPassUs < 5000 && radioGapUs() < 5000 && othersAre(1) && stServed >= 24);
    for (auto &t : touches) CHECK(t.ch == 1);
  }
  // A2. A CHANNEL TAPPED, "+" AT ONCE - at every delay from 0 to 400 ms (the twelfth review's HIGH: until this board's answer to the tap had landed, "+"
  //     counted on from the channel BEFORE's number - 91 steps in one press). The page puts the tapped channel's own number into its slider by itself now
  for (uint32_t delay : { 0u, 1u, 5u, 20u, 60u, 120u, 250u, 400u })
    for (uint32_t late : { 300u, 150000u, 400000u })
    {
      more(); addSubTrim(); openSubTrim(); screen.latencyUs = late;
      slide(10, 60); stLoop(700); CHECK(trim(1) == 60);
      tapCh(10, 7); tapAt(10 + delay, "plus"); stLoop(1500);
      if (trim(7) != -29 || trim(1) != 60) say("A2 (+ %u ms behind the tap, the screen %u ms behind): channel 7 %d, channel 1 %d\n", delay, late / 1000, trim(7), trim(1));
      CHECK(trim(7) == -29 && trim(1) == 60 && othersAre(1, 7) && pageIsModel() && sliderIsShown());
    }
  // A3. A CHANGE THAT DOES NOT START FROM THE MODEL'S NUMBER (the page shows 40 for channel 5, the model has 0 - a word was lost; here: the box written
  //     by hand): "+" makes 41 of it - NOT TAKEN, and the channel is put right: its box written, the page told to set its slider by it. The next "+" is
  //     taken: 1. And 0.6 s after the last touch the page is written out once more (whatever landed on top of whatever)
  {
    more(); addSubTrim(); openSubTrim();
    tapCh(10, 5); stLoop(300); B("n4") = 40; B("n0") = 40; B("h0") = 167; writes.clear();
    tapAt(10, "plus"); stLoop(400);
    say("A3. the page shows 40 for channel 5 (the model has 0), +: the model %d; the page shows %d, its slider's number %ld; written:", trim(5), shown(5), B("n0")); for (auto &w : writes) say(" [%s]", w.c_str()); say("\n");
    CHECK(trim(5) == 0 && shown(5) == 0 && sliderIsShown() && pageIsModel() && wasMade(5, 40, 41));
    CHECK(writes.size() == 2 && writes[0] == "n4.val=0" && writes[1] == "click rs,0");                           // the channel put right: its box, and the page's slider by it - no more (and never the slider itself)
    tapAt(10, "plus"); stLoop(400); CHECK(trim(5) == 1 && pageIsModel() && sliderIsShown() && othersAre(5) && writes.size() == 2);
    stLoop(400); CHECK(writes.size() == 2 + 17 && writes.back() == "click rs,0" && pageIsModel() && sliderIsShown());   // the pilot has paused: the page once more
    stLoop(3000); CHECK(writes.size() == 2 + 17);                                                                // ... once
  }
  // A4. "StCH" TELLS THIS BOARD NOTHING: sixteen taps - nothing asked, nothing written, nothing changed
  {
    more(); addSubTrim(); openSubTrim(); const int gets0 = screen.gets; writes.clear(); const long served0 = stServed;
    for (int ch = 1; ch <= 16; ++ch) tapCh(10 + ch * 60, ch);
    stLoop(1500);
    CHECK(screen.gets == gets0 && writes.empty() && stServed - served0 == 16 && othersAre(0) && trim(7) == -30 && pageIsModel() && sliderIsShown() && B("s0") == 16);
  }
  // ===================================================================================================== B. THE THIRTEENTH REVIEW'S ROADS
  // B1 (reviewer B's A1, his trace x22b): THE SCREEN 250 ms BEHIND, touches 300 ms apart. He drags channel 3 from +60 to +30, taps channel 7 (-30), taps
  //     channel 3 again, presses "+". Channel 3 went 60 -> 30 -> -29: "the channel left gives its box once" was asked last, after this board had put
  //     channel 7's number into the slider. Now: 31
  for (uint32_t late : { 250000u, 150000u, 400000u, 2000u })
  {
    more(); addSubTrim(); SubTrims[2] = 187; openSubTrim(); screen.latencyUs = late;
    tapCh(10, 3); stLoop(1200);
    for (int i = 0; i < 6; ++i) slide(10 + i * 40, 55 - i * 5);                 // the drag: 55, 50 ... 30
    tapCh(10 + 240 + 300, 7); tapCh(10 + 240 + 600, 3); tapAt(10 + 240 + 900, "plus");
    stLoop(4000);
    say("B1. the screen %u ms behind; channel 3 dragged 60 -> 30, channel 7 tapped, channel 3 tapped, +: channel 3 %d, channel 7 %d\n", late / 1000, trim(3), trim(7));
    CHECK(trim(3) == 31 && trim(7) == -30 && othersAre(3, 7) && pageIsModel() && sliderIsShown());
  }
  // B2 (his A2, x18a): in step on channel 1 (+5). Channel 7 tapped, its slider to +40; BEFORE those two words are served a page command goes out (a box
  //     put up over the page; its way back) - they are thrown away with it. The page comes back on channel 1, and its own "StCH" is lost. Six quiet
  //     seconds, then "+" once: channel 1 went from +5 to +41 (the slider's number still stood at channel 7's 40). Now +6 - and channel 7 as it was:
  //     its box shows the 40 nobody stored, and a "+" there is refused and the channel put right
  {
    more(); addSubTrim(); SubTrims[0] = 132; openSubTrim();
    tapCh(10, 7); slide(40, 40);
    nowUs += 60000; screen.run(nowUs);                                           // (the screen has done both; this board has read neither)
    SendCommand((char *) "page PopupView"); nowUs += 30000; SendCommand((char *) "page SubTrimView"); CurrentView = SUBTRIMVIEW;   // (a box and its way back: two page commands of this board's)
    P().loadPrint.clear();                                                       // (... and the page's own word as it comes back is lost: a field screen's line fell on it)
    stLoop(6000);
    // (the fifteenth review) ... AND THE TOUCH THROWN AWAY OWED THE PAGE ITS WRITING-OUT (Trims.h SubTrimWordLetGo): the page showed the 40 nobody had
    // stored until that channel was next touched - it shows what the model has
    CHECK(trim(1) == 5 && trim(7) == -30 && B("s0") == 1 && shown(7) == -30 && B("n0") == 5 && pageIsModel() && sliderIsShown() && wordsLetGo > 0);
    tapAt(10, "plus"); stLoop(500);
    say("B2. the page back from a box, two touches thrown away with the page command: + on channel 1 gives %d (it was 5); channel 7 the model %d, the page %d\n", trim(1), trim(7), shown(7));
    CHECK(trim(1) == 6 && trim(7) == -30 && othersAre(1, 7));
    tapCh(10, 7); tapAt(200, "plus"); stLoop(600);
    CHECK(trim(7) == -29 && shown(7) == -29 && wasMade(7, -30, -29) && pageIsModel() && sliderIsShown());         // taken: the page had been put right
    tapAt(10, "plus"); stLoop(400); CHECK(trim(7) == -28 && pageIsModel());
  }
  // B3 (his A3, x17): A FINGER RESTING ON THE SLIDER while what it shows is not what the model has. The screen puts the slider back under the finger 40 ms
  //     after any write of it and says the word again: this board wrote the slider back, the screen put it back under the finger, this board wrote it
  //     back ... 18 passes of a quarter second in 5 s, no switch read in them. Now: ONE round - the word that does not start from the model's number is
  //     refused and the channel put right; the screen's own word, from the right number now, is taken. Then quiet
  {
    more(); addSubTrim(); openSubTrim(); const int gets0 = screen.gets;
    tapCh(10, 5); stLoop(300); B("n4") = 40; B("n0") = 40; B("h0") = 167;       // (the page ahead of the model on channel 5: 40 shown, 0 stored)
    writes.clear(); const long served0 = stServed; gapWatch = true; lastRadioUs = nowUs; maxRadioGapUs = 0; maxPassUs = 0;
    fingerDown = true; fingerAt = 127 + 90; slide(10, 90);                      // the finger lands on the slider at +90 and stays there
    stLoop(5000);
    say("B3. a finger resting on the slider at +90 for 5 s, the page ahead of the model: the model %d; words served %ld, writes of this board's %d, asked %d; the loop's longest pass %.1f ms\n", trim(5), stServed - served0, (int) writes.size(), screen.gets - gets0, maxPassUs / 1e3);
    CHECK(trim(5) == 90 && pageIsModel() && sliderIsShown());
    CHECK(stServed - served0 == 4 && writes.size() == 2 + 17 && screen.gets == gets0 && maxPassUs < 5000 && radioGapUs() < 5000);   // one refusal, one round, the page once more at rest - no storm (four words: his two, and the page's "done" behind each of this board's two clicks)
    fingerDown = false;
  }
  // B4 (his A10): TWO TAPS NEVER HEARD, around a slider's word that is heard - channel 3 took channel 2's number. The word says its channel now
  {
    more(); addSubTrim(); openSubTrim();
    tapCh(10, 3); stLoop(400);
    tapCh(10, 2, false); slide(150, -105); tapCh(300, 3, false); tapAt(450, "minus"); stLoop(1500);
    say("B4. channel 2 tapped (never heard), its slider to -105, channel 3 tapped (never heard), -: channel 2 %d, channel 3 %d\n", trim(2), trim(3));
    CHECK(trim(2) == -105 && trim(3) == -1 && othersAre(2, 3) && pageIsModel() && sliderIsShown());
  }
  // B5 (his A9, and every order of two touches): a tap and a "+" 0 to 120 ms apart, the tap first or the "+" first - each change belongs to the channel
  //     the page showed as it was made
  for (int first = 0; first < 2; ++first)
    for (uint32_t gap : { 0u, 2u, 20u, 60u, 120u })
    {
      more(); addSubTrim(); openSubTrim(); tapCh(10, 5); stLoop(400);
      if (first) { tapAt(10, "plus"); tapCh(10 + gap + 1, 9); } else { tapCh(10, 9); tapAt(10 + gap + 1, "plus"); }
      stLoop(900);
      CHECK(first ? (trim(5) == 1 && trim(9) == 0) : (trim(5) == 0 && trim(9) == 1));
      CHECK(pageIsModel() && sliderIsShown() && othersAre(5, 9));
    }
  // ===================================================================================================== C. WHAT IS LOST, AND FOUND AGAIN
  // C1. A WORD NEVER HEARD: the page is one step ahead. The next "+" there is refused - the pilot sees both undone - and the one after is taken
  {
    more(); addSubTrim(); openSubTrim(); tapCh(10, 4); stLoop(300);
    tapAt(10, "plus!"); stLoop(400); CHECK(trim(4) == 0 && shown(4) == 1);       // (the page ahead)
    tapAt(10, "plus"); stLoop(400);
    say("C1. a + never heard, then a +: the model %d, the page %d\n", trim(4), shown(4));
    CHECK(trim(4) == 0 && pageIsModel() && sliderIsShown() && wasMade(4, 1, 2));
    tapAt(10, "plus"); stLoop(400); CHECK(trim(4) == 1 && pageIsModel() && othersAre(4));
    stLoop(2000);                                                               // (he pauses: the page is written out once more, and nothing more is owed)
    // ... and the SLIDER after a word never heard: its own first word is refused too (it does not start from the model's number) - with the finger
    // still on it the screen says it again, and that is taken
    tapAt(10, "minus!"); stLoop(300); CHECK(trim(4) == 1 && shown(4) == 0);
    fingerDown = true; fingerAt = 127 + 30; slide(10, 30); stLoop(600); fingerDown = false;
    CHECK(trim(4) == 30 && pageIsModel() && sliderIsShown());
    stLoop(2000);
    // ... a tap of the slider (the finger gone at once) after a word never heard: refused, put right - he sees it - and his next one is taken
    tapAt(10, "minus!"); stLoop(300); CHECK(trim(4) == 30 && shown(4) == 29);
    slide(10, 50); stLoop(500); CHECK(trim(4) == 30 && pageIsModel() && sliderIsShown());
    slide(10, 50); stLoop(500); CHECK(trim(4) == 50 && pageIsModel());
    // ... and a word never heard with NOTHING behind it: the page stays one step ahead (nothing can tell this board) - until the next touch there
    stLoop(2000); tapAt(10, "plus!"); stLoop(5000); CHECK(trim(4) == 50 && shown(4) == 51);
  }
  // C2. A WRITE OF THIS BOARD'S THAT NEVER LANDS - as the page is put up, channel 7's box (it shows 0, the model has -30). "+" there is refused (1 is not
  //     one step from -30) and the channel put right - that write lost too: the box shows the 1. He pauses: the page is written out once more, and is
  //     right. Then "+" is taken: -29
  {
    more(); addSubTrim(); loseWrite = "n6.val="; loseLeft = 2; openSubTrim(); CHECK(shown(7) == 0 && trim(7) == -30);
    tapCh(10, 7); tapAt(200, "plus"); stLoop(400); CHECK(trim(7) == -30 && shown(7) == 1 && loseLeft == 0);      // (refused; the putting-right's write lost)
    stLoop(1500);
    say("C2. channel 7's box never written (twice): the model %d; after a refused + and a pause the page shows %d\n", trim(7), shown(7));
    CHECK(trim(7) == -30 && pageIsModel() && sliderIsShown());
    tapAt(10, "plus"); stLoop(400); CHECK(trim(7) == -29 && pageIsModel() && sliderIsShown() && othersAre(7));
    // ... every write of that box lost five times running: refused, refused - never a number that is not one step from the model's - until one lands
    more(); addSubTrim(); loseWrite = "n6.val="; loseLeft = 5; openSubTrim(); tapCh(10, 7); stLoop(300);
    for (int i = 0; i < 4 && loseLeft > 0; ++i) { tapAt(10, "plus"); stLoop(2500); CHECK(trim(7) == -30); }
    CHECK(loseLeft == 0);
    tapAt(10, "plus"); stLoop(2500); CHECK(trim(7) == -30 && pageIsModel() && sliderIsShown());                   // (the last refusal: its putting-right lands)
    tapAt(10, "plus"); stLoop(400); CHECK(trim(7) == -29 && pageIsModel() && othersAre(7));
  }
  // C3. ANOTHER MODEL READ INTO MEMORY UNDER THE OPEN PAGE (main.cpp UpdateButtonLabels: SubTrimPageOut), a "+" on channel 7 landing at every moment
  //     around this board's writes: the new model's channel 7 (12) is 12, or 13 - never "the old model's number and one" (-29)
  for (int us = -3000; us <= 12000; us += 500)
  {
    more(); addSubTrim(); openSubTrim(); tapCh(10, 7); stLoop(400);
    for (int i = 0; i < 16; ++i) SubTrims[i] = 127; SubTrims[6] = 139;           // the new model: channel 7 at +12
    if (us < 0) { tapAt(1, "plus"); nowUs += (uint64_t) (1000 - us); screen.run(nowUs); }
    else screen.taps.insert({ nowUs + (uint64_t) us, "plus" });
    SubTrimPageOut(); stLoop(1200);
    if (trim(7) != 12 && trim(7) != 13) say("C3 (+ %d us from the writes): channel 7 %d\n", us, trim(7));
    CHECK(trim(7) == 12 || trim(7) == 13);
    for (int ch = 1; ch <= 16; ++ch) if (ch != 7) CHECK(trim(ch) == 0);
    tapCh(10, 7); tapAt(200, "plus"); stLoop(600);                               // (whatever the page was left showing: a tap, a touch - right again)
    tapAt(10, "plus"); stLoop(400); CHECK(pageIsModel() && sliderIsShown() && (trim(7) == 13 || trim(7) == 14 || trim(7) == 15));
  }
  // C4. WORDS NOT KEPT FOR WANT OF ROOM: the finger drags while this board waits two seconds elsewhere (a box of another page's work that does not
  //     answer) - eight frames are kept, the rest are not. Nothing is taken that does not follow from the model's number: the chain breaks at the
  //     first word not kept, the channel is put right, and with the finger still down the screen's own word sets it where the finger is
  {
    more(); addSubTrim(); openSubTrim(); tapCh(10, 6); stLoop(300);
    fingerDown = true;
    for (int i = 1; i <= 40; ++i) { slideTo.push_back(127 + i); screen.taps.insert({ nowUs + 5000 + (uint64_t) i * 40000, "slider" }); }
    fingerAt = 127 + 40;
    screen.mute.insert("n3"); GetValue((char *) "n3"); screen.mute.clear();     // (two seconds in which the main loop serves nothing; the words pile up)
    const uint16_t dropped = (uint16_t) (PendingDropped - SubTrimDropsSeen);
    PageChangedUnderGet = false; ScreenAnswerOwed = false; stLoop(3000); fingerDown = false;
    bool chain = true; for (size_t i = 0; i < touches.size(); ++i) if (touches[i].ch != 6) chain = false;
    say("C4. a drag of 40 steps under a wait of two seconds (%u words not kept): the model %d (the finger rests at 40), the page %d\n", (unsigned) dropped, trim(6), shown(6));
    CHECK(chain && dropped > 10 && trim(6) == 40 && pageIsModel() && sliderIsShown() && othersAre(6));
    // ... the same with the finger GONE at the drag's end: the page is written out as the model has it - the pilot sees where his drag was heard to
    more(); addSubTrim(); openSubTrim(); tapCh(10, 6); stLoop(300);
    for (int i = 1; i <= 40; ++i) { slideTo.push_back(127 + i); screen.taps.insert({ nowUs + 5000 + (uint64_t) i * 40000, "slider" }); }
    screen.mute.insert("n3"); GetValue((char *) "n3"); screen.mute.clear();
    PageChangedUnderGet = false; ScreenAnswerOwed = false; stLoop(3000);
    say("C4. ... the finger gone at the drag's end: the model %d, the page %d\n", trim(6), shown(6));
    CHECK(trim(6) >= 1 && trim(6) < 40 && pageIsModel() && sliderIsShown() && othersAre(6) && wasMade(6, trim(6) - 1, trim(6)));
  }
  // C5. THE PAGE IS LEFT WITH A WRITING-OUT OWED (a change not taken, and the page left before he has paused): NOTHING is written onto the page that
  //     comes next - a writing-out there would put sixteen sub trims into another page's boxes "n1" to "n15" - and nothing is owed to the next visit
  {
    more(); addSubTrim(); openSubTrim(); tapCh(10, 4); stLoop(300);
    tapAt(10, "plus!"); stLoop(300); tapAt(10, "plus"); stLoop(120);            // (a + never heard, then a + refused: the page is owed its writing-out - 0.6 s on)
    CHECK(SubTrimSettleDue && trim(4) == 0);
    SendCommand((char *) "page FrontView"); CurrentView = FRONTVIEW; stLoop(30); writes.clear();   // (he leaves the page at once)
    stLoop(3000);
    say("C5. the page left with a writing-out owed: written onto the next page %d command(s); still owed %d\n", (int) writes.size(), (int) SubTrimSettleDue);
    CHECK(writes.empty() && !SubTrimSettleDue);
    openSubTrim(); writes.clear(); stLoop(2000); CHECK(writes.empty() && !SubTrimSettleDue && pageIsModel());   // the next visit: the page as the model has it, nothing more owed
  }
  // C6. THE SCREEN STANDS STILL WITH THIS BOARD'S WRITES WAITING (the author's storm, run with other seeds: one trial in 54000 with nothing lost ended
  //     with the page and the model apart). A change is not taken; the page's writing-out, owed 0.6 s on, goes to a screen whose loop stands still
  //     for two seconds. As it wakes the pilot touches ANOTHER channel - taken, as it should be: it starts from the model's number - and only then
  //     does the screen read the old writing-out, which puts that channel's box back to the number it had when the writing-out was sent. "A write of
  //     this board's has landed within a second, or never will" was the rule: it had not. THE PAGE SAYS WHEN IT HAS DONE what this board asked.
  {
    more(); addSubTrim(); openSubTrim(); tapCh(10, 4); stLoop(300);
    tapAt(10, "plus!"); stLoop(300); tapAt(10, "plus"); stLoop(200);            // (a + never heard, then a + refused: channel 4 is put right at once; the writing-out is owed)
    CHECK(trim(4) == 0 && shown(4) == 0 && SubTrimSettleDue);
    screen.stall(nowUs + 100000, 2000, false, 30000);                           // the screen's loop stands still from 0.1 s on, for two seconds: the writing-out waits in it
    tapAt(2105, "ch7"); tapAt(2110, "plus"); tapAt(2115, "plus");               // as it wakes (a touch is looked at before the commands are read): channel 7, "+", "+"
    stLoop(2400);
    const int shownAtOnce = shown(7);
    stLoop(2500);                                                               // ... and two quiet seconds
    say("C6. the screen stands still for 2 s with the writing-out waiting, two + on channel 7 as it wakes: the model %d; the page showed %d when the old writing-out had landed, and shows %d after his pause\n", trim(7), shownAtOnce, shown(7));
    CHECK(trim(7) == -28 && wasMade(7, -30, -29) && wasMade(7, -29, -28));      // both taken: each started from the model's number
    CHECK(pageIsModel() && sliderIsShown());                                    // the page shows what the model has (it showed -30)
  }
  // C7. A SCREEN 0.7 s BEHIND: ONLY THE "DONE" OF THIS BOARD'S LAST CLICK COUNTS. A change not taken: its putting-right (click 2) lands 0.7 s on, and the
  //     page's writing-out (click 3, sent 0.6 s on) 1.3 s on. The "done" of click 2 arrives when click 3 is already on its way: it says nothing of
  //     the writing-out. Two "+" on another channel at 0.9 s are taken - and the writing-out, sent before them, lands on top of them at 1.3 s: with
  //     "a done is a done" nothing more was owed, and the page showed the old number for good.
  {
    more(); addSubTrim(); openSubTrim(); tapCh(10, 4); stLoop(300);
    tapAt(10, "plus!"); stLoop(300);
    screen.latencyUs = 700000;                                                  // from here the screen reads each command 0.7 s after it was said
    tapAt(10, "plus"); tapAt(900, "ch7"); tapAt(905, "plus"); tapAt(910, "plus");
    stLoop(1400);
    const int shownMeanwhile = shown(7);                                        // (the old writing-out has landed on top of his two touches)
    stLoop(4000);
    say("C7. a screen 0.7 s behind, a change refused on channel 4, two + on channel 7 between this board's two batches landing: the model %d; the page showed %d meanwhile, and shows %d after his pause\n", trim(7), shownMeanwhile, shown(7));
    CHECK(trim(4) == 0 && trim(7) == -28 && wasMade(7, -30, -29) && wasMade(7, -29, -28) && shownMeanwhile == -30);
    CHECK(pageIsModel() && sliderIsShown() && SubTrimDone == SubTrimAsked);
    screen.latencyUs = 1500;
  }
  // ===================================================================================================== E. WHAT THE WORD MAY BE
  // E1. said by hand: a channel the page has not got, a burst of another length, the word not at its head, a number beyond what the card keeps
  {
    more(); addSubTrim(); openSubTrim(); writes.clear();
    auto numbers = [](long a, long b, long c) { std::vector<uint8_t> v = { 'S', 't', 'E', 'D', 'I', 'T' }; for (long x : { a, b, c, c }) for (int k = 0; k < 4; ++k) v.push_back((uint8_t) ((uint32_t) (int32_t) x >> (8 * k))); return v; };
    for (long ch : { 0L, 17L, -1L, 256L, 65536L + 3 }) { burstNow(numbers(ch, 0, 5)); stLoop(50); }
    CHECK(othersAre(0) && trim(7) == -30 && writes.empty() && !SubTrimOldPageSaid);                              // no channel of the page's: nothing, not even a write
    {   // THE PAGE'S "DONE", said to the routine directly (fourteen bytes: the word and a click's number, twice): only this board's LAST click's, and only framed
        auto done = [](long n) { std::vector<uint8_t> v = { 'S', 't', 'E', 'D', 'I', 'T' }; for (int twice = 0; twice < 2; ++twice) for (int k = 0; k < 4; ++k) v.push_back((uint8_t) ((uint32_t) (int32_t) n >> (8 * k))); return v; };
        SubTrimPageOut(); SubTrimPageOut();                                                                      // (two writings-out said, none read by the screen yet: two clicks out)
        const uint16_t last = SubTrimAsked; CHECK(SubTrimDone != last && last >= 3);
        { const std::vector<uint8_t> v = done(last - 1); SubTrimWord(v.data(), (uint16_t) v.size(), true); CHECK(SubTrimDone != last); }      // the click before's: it says nothing of the last
        { const std::vector<uint8_t> v = done(last + 1); SubTrimWord(v.data(), (uint16_t) v.size(), true); CHECK(SubTrimDone != last); }      // a number this board never gave
        { const std::vector<uint8_t> v = done(last); SubTrimWord(v.data(), (uint16_t) v.size(), false); CHECK(SubTrimDone != last); }         // the last one's, UNFRAMED: not believed
        CHECK(!SubTrimOldPageSaid && othersAre(0) && trim(7) == -30);                                            // (a "done" is no word of a page file from before, and changes nothing)
        { const std::vector<uint8_t> v = done(last); SubTrimWord(v.data(), (uint16_t) v.size(), true); CHECK(SubTrimDone == last); }          // the last one's, framed: done
        stLoop(900); writes.clear();
    }
    { std::vector<uint8_t> v = numbers(3, 0, 5);                                                                 // the burst as this release's page says it - but UNFRAMED: how it came is part of the rule
      SubTrimWord(v.data(), (uint16_t) v.size(), false); CHECK(trim(3) == 0 && othersAre(0) && SubTrimOldPageSaid);
      SubTrimOldPageSaid = false; SubTrimWord(v.data(), (uint16_t) v.size(), true); CHECK(trim(3) == 5 && !SubTrimOldPageSaid);   // (the same bytes framed: taken)
      SubTrims[2] = 127; stLoop(900); writes.clear(); }
    { std::vector<uint8_t> v = numbers(3, 0, 5); v.push_back(0); burstNow(v); stLoop(50); v.pop_back(); v.pop_back(); burstNow(v); stLoop(50); }
    CHECK(othersAre(0) && SubTrimOldPageSaid);                                                                   // another length: not this release's word - nothing taken (said as "an older page file")
    stLoop(900); CHECK(!writes.empty() && pageIsModel());                                                        // ... and the page is written out as the model has it, when he has paused
    SubTrimOldPageSaid = false; writes.clear();
    { std::vector<uint8_t> v = numbers(3, 0, 5); v.insert(v.begin(), 'x'); v.pop_back(); burstNow(v); stLoop(50); }
    CHECK(othersAre(0) && writes.empty());                                                                       // the word not at the burst's head
    { std::vector<uint8_t> v = numbers(3, 0, 5); v[0] = 'x'; SubTrimWord(v.data(), (uint16_t) v.size(), true);   // ... said to the routine itself: eighteen bytes, framed, a channel, the model's number - but not BEGINNING with the word
      CHECK(trim(3) == 0 && othersAre(0) && writes.empty() && !SubTrimOldPageSaid); }
    for (long made : { 118L, -118L, 127L, 200L, -100000L }) { burstNow(numbers(3, 0, made)); stLoop(50); CHECK(trim(3) == 0); }
    CHECK(othersAre(0) && writes.size() >= 10 && writes[0] == "n2.val=0" && writes[1] == "click rs,0");           // beyond what the card keeps: not taken, the channel put right each time
    burstNow(numbers(3, 0, 117)); stLoop(50); burstNow(numbers(3, 117, -117)); stLoop(50); CHECK(trim(3) == -117 && othersAre(3));   // the limits themselves are taken
    burstNow(numbers(3, -116, 5)); stLoop(50); CHECK(trim(3) == -117);                                           // not from the model's number
  }
  // E2. EVERY BYTE. The burst holds numbers now - bytes that begin a reply (p, q, f), a frame's mark, a newline, zeros, FF FF FF FF: it is read by its
  //     LENGTH, whole - by the main loop; kept through another box's wait and served behind it; and right behind a reply, a marker and a bare word
  {
    more(); addSubTrim(); openSubTrim();
    auto numbers = [](long a, long b, long c) { std::vector<uint8_t> v = { 'S', 't', 'E', 'D', 'I', 'T' }; for (long x : { a, b, c, c }) for (int k = 0; k < 4; ++k) v.push_back((uint8_t) ((uint32_t) (int32_t) x >> (8 * k))); return v; };
    static const long vals[] = { 0, 1, -1, 10, 13, 102, 112, 113, 117, -117, 126 - 9, 0x66 - 127, 'p' - 127, -2, 64, -64, 100, -100, 31, -32 };   // (10: a newline; 102, 112, 113: f, p, q; -1 and -2: FF FF FF FF, FE FF FF FF)
    long taken = 0, sent = 0;
    for (int way = 0; way < 3; ++way)
      for (int ch = 1; ch <= 16; ++ch)
        for (long v : vals)
        {
            const long from = trim(ch);
            const std::vector<uint8_t> w = numbers(ch, from, v);
            if (way == 0) { burstNow(w); stLoop(30); }                                                           // read by the main loop
            else if (way == 1)
            {   // said while ANOTHER page's box is being asked: kept through that wait, served behind it
                std::vector<uint8_t> f = { 0x7E, 0x7E, (uint8_t) w.size(), 0 }; f.insert(f.end(), w.begin(), w.end());
                screen.emit(nowUs + 20000, f); const uint32_t got = GetValue((char *) "s0"); CHECK(got == (uint32_t) B("s0")); stLoop(30);
            }
            else
            {   // glued right behind a value reply nobody waits for, a page's marker and a bare word of the screen's own
                std::vector<uint8_t> f = { 'q', 9, 0, 0, 0, 0xFF, 0xFF, 0xFF, 0x66, 32, 0xFF, 0xFF, 0xFF, 0x7E, 0x7E, (uint8_t) w.size(), 0 }; f.insert(f.end(), w.begin(), w.end());
                screen.emit(nowUs + 200, f); stLoop(30);
            }
            ++sent; taken += trim(ch) == v;
            if (trim(ch) != v) say("E2 (way %d): channel %d from %ld to %ld: the model has %d\n", way, ch, from, v, trim(ch));
            CHECK(trim(ch) == v);
        }
    say("E2. %ld bursts - every channel, numbers whose bytes are a reply's head, a frame's mark, a newline, FF FF FF FF - by three ways in: %ld taken as said\n", sent, taken);
    CHECK(sent == 3 * 16 * 20 && taken == sent && !ScreenAnswerOwed && !ScreenRestartSeen && boxesLostTold == 0);
  }
  // ===================================================================================================== G. THE FOURTEENTH REVIEW
  // G1. THE LAST NUMBER IS SAID TWICE, and nothing is taken when the two do not agree: a character of the screen's own that fell into the burst
  {
    more(); addSubTrim(); openSubTrim(); tapCh(10, 7); stLoop(300);
    auto four = [](long a, long b, long c, long d) { std::vector<uint8_t> v = { 'S', 't', 'E', 'D', 'I', 'T' }; for (long x : { a, b, c, d }) for (int k = 0; k < 4; ++k) v.push_back((uint8_t) ((uint32_t) (int32_t) x >> (8 * k))); return v; };
    CHECK(four(7, -30, 0, 0).size() == SUBTRIM_WORD_BYTES && SUBTRIM_WORD_BYTES == 22 && SUBTRIM_DONE_BYTES == 14 && SubTrimShown);
    const size_t w0 = writes.size(), log0 = logLines.size();
    burstNow(four(7, -30, 0, 32)); stLoop(200);                                  // Zero on channel 7 - and its second saying reads 32
    CHECK(trim(7) == -30 && writes.size() == w0 + 2 && writes[w0] == "n6.val=-30" && writes[w0 + 1] == "click rs,0");
    CHECK(logLines.size() == log0 + 1 && logLines.back().find("Sub-trim page: channel 7 not taken - its two last numbers differ, 0 and 32 (the page made 0 of -30; the model has -30); put right on the page B211") == 0);   // (the fifteenth review: WHICH rule refused - and both numbers)
    burstNow(four(7, -30, 32, 0)); stLoop(200); CHECK(trim(7) == -30 && logLines.size() == log0 + 1);                 // (and the other way round; the log has its one line of this visit)
    { std::vector<uint8_t> w = four(7, -30, 0, 0); w.insert(w.begin() + 18, ' '); w.pop_back(); burstNow(w); stLoop(200); CHECK(trim(7) == -30); }   // the reviewer's very case, as the 22 bytes are read: a space in front of the last number
    { std::vector<uint8_t> w = four(7, -30, 0, 0); w.insert(w.begin() + 14, ' '); w.pop_back(); burstNow(w); stLoop(200); CHECK(trim(7) == -30); }   // ... and in front of the one before it (18 bytes as they were: that made 32 of it, taken)
    B("n6") = 0; B("n0") = 0; B("h0") = 127; burstNow(four(7, -30, 0, 0)); stLoop(200); CHECK(trim(7) == 0 && pageIsModel());   // (the burst whole, as the page's Zero says it: taken)
    // EVERY PLACE a character can fall into a burst, every printable character (and 0, 255), a byte lost at every place: the model never holds a number
    // the page did not make - and what the main board then shows is the model's
    long wrong = 0, took = 0, tried = 0;
    for (long from : { 0L, -30L, 5L, -1L, 117L }) for (long made : { 0L, 5L, -1L, 32L, -117L, 100L })
      for (int at = 0; at <= 22; ++at) for (int x = 0; x < 256; x += (x >= 31 && x < 127) ? 1 : (x == 0 ? 31 : 128))
        for (int lose = 0; lose < 2; ++lose)
        {
            SubTrims[6] = (uint8_t) (127 + from); std::vector<uint8_t> w = four(7, from, made, made);
            if (lose) { if (at >= 22) continue; w.erase(w.begin() + at); w.push_back((uint8_t) x); }                 // a byte lost: the next byte on the wire is read as the burst's last
            else { w.insert(w.begin() + at, (uint8_t) x); w.pop_back(); }                                            // a byte more: the burst's own last byte is left on the wire
            SubTrimWord(w.data(), (uint16_t) w.size(), true); ++tried;
            if (trim(7) != from) { ++took; if (trim(7) != made) { if (++wrong <= 5) say("G1: from %ld the page made %ld; a byte %s at %d (%d): the model has %d\n", from, made, lose ? "lost" : "more", at, x, trim(7)); } }
            if (tried % 64 == 0) stLoop(2);
        }
    stLoop(900);
    say("G1. a byte more, or a byte lost, at every place of a burst: %ld bursts, %ld taken (each exactly as the page made it), the model wrong %ld time(s); the page shows the model: %d\n", tried, took, wrong, (int) pageIsModel());
    CHECK(wrong == 0 && tried > 20000 && took > 0 && pageIsModel() && sliderIsShown());
    // ... and the "done": only its number said twice alike, framed, this board's last click
    {
        more(); addSubTrim(); SendCommand((char *) "page SubTrimView"); CurrentView = SUBTRIMVIEW; SubTrimStarts(); doneToWire = false; freshOut(); stLoop(300);
        CHECK(!SubTrimShown && SubTrimDone != SubTrimAsked && lastDone.size() == SUBTRIM_DONE_BYTES);               // (the page has run the click; its "done" was kept off the wire)
        auto done2 = [](long a, long b) { std::vector<uint8_t> v = { 'S', 't', 'E', 'D', 'I', 'T' }; for (long x : { a, b }) for (int k = 0; k < 4; ++k) v.push_back((uint8_t) ((uint32_t) (int32_t) x >> (8 * k))); return v; };
        CHECK(done2(SubTrimAsked, SubTrimAsked) == lastDone);
        long believed = 0;
        for (int at = 0; at <= 14; ++at) for (int x = 0; x < 256; ++x) for (int lose = 0; lose < 2; ++lose)
        {
            std::vector<uint8_t> w = lastDone;
            if (lose) { if (at >= 14) continue; if (w[at] == (at + 1 < 14 ? w[at + 1] : (uint8_t) x) && (at + 1 >= 14 || std::equal(w.begin() + at + 1, w.end() - 1, w.begin() + at + 2)) && x == w[13]) continue; w.erase(w.begin() + at); w.push_back((uint8_t) x); }
            else { w.insert(w.begin() + at, (uint8_t) x); w.pop_back(); }
            if (w == lastDone) continue;                                                                             // (the same bytes again: nothing fell in)
            SubTrimWord(w.data(), 14, true); if (SubTrimShown) { ++believed; SubTrimShown = false; SubTrimDone = (uint16_t) (SubTrimAsked - 1); }
        }
        CHECK(believed == 0);
        SubTrimWord(done2(SubTrimAsked - 1, SubTrimAsked - 1).data(), 14, true); CHECK(!SubTrimShown);              // an older click's
        SubTrimWord(done2(SubTrimAsked, SubTrimAsked + 1).data(), 14, true); CHECK(!SubTrimShown);
        SubTrimWord(lastDone.data(), 14, false); CHECK(!SubTrimShown);                                               // not framed
        SubTrimWord(lastDone.data(), 14, true); CHECK(SubTrimShown && SubTrimDone == SubTrimAsked);                  // the page's own
        doneToWire = true;
    }
  }
  // G2. NOTHING IS TAKEN UNTIL THE PAGE HAS SAID THIS MODEL'S NUMBERS DONE. Another model is read under the open page (a pupil's transmitter) with the
  //     SAME number on the channel he is touching: the touch was made on the OLD model's page - it is not taken into the new one (it was)
  for (uint32_t late : { 2000u, 40000u, 150000u, 400000u })
    for (int when = 0; when < 3; ++when)
    {
        more(); addSubTrim(); openSubTrim(); screen.latencyUs = late; tapCh(10, 7); stLoop(900);
        CHECK(SubTrimShown && trim(7) == -30 && pageIsModel());
        if (when == 0) { tapAt(1, "plus"); stLoop(3); }                                    // the touch just BEFORE the read: its word waits, served behind the read
        const int oldModels = trim(7);                                                     // (when 0: the OLD model took it, or its word still waits)
        SubTrims[6] = 97; SubTrims[2] = 167; SubTrims[9] = 100; freshOut();                // THE OTHER MODEL: -30 on channel 7 as well; 40 on channel 3, -27 on channel 10
        CHECK(!SubTrimShown);
        if (when == 1) tapAt(1, "plus");                                                   // the touch right BEHIND the read: the page still shows the old model
        if (when == 2) tapAt(late / 2000 + 1, "plus");                                     // ... or half way through the writing-out's landing
        stLoop(late / 1000 + 1500);
        if (!(trim(3) == 40 && trim(10) == -27 && pageIsModel() && sliderIsShown() && SubTrimShown) || (trim(7) != -30 && !wasMadeOnModel(7, -30, -29))) say("G2 (the screen %u ms behind, the touch %s): the new model's channel 7 is %d (the old model had %d at the read), the page shows %d, shown %d, owed %d\n", late / 1000, when == 0 ? "before the read" : when == 1 ? "right behind it" : "half way", trim(7), oldModels, shown(7), (int) SubTrimShown, (int) SubTrimSettleDue);
        const bool onNew = wasMadeOnModel(7, -30, -29);                                    // (the touch came as the writing-out had just landed - a screen 2 ms behind: it was made on the NEW model's page)
        CHECK((trim(7) == -30 || (trim(7) == -29 && onNew && when == 2 && late == 2000u)) && trim(3) == 40 && trim(10) == -27 && pageIsModel() && sliderIsShown() && SubTrimShown);
        const int before = trim(7);
        tapAt(10, "plus"); stLoop(late / 1000 + 900); CHECK(trim(7) == before + 1 && pageIsModel() && wasMadeOnModel(7, before, before + 1));   // the same touch on the new model's page: taken
    }
  // ... and the page first put up: a touch before its numbers have landed is not taken (the boxes are the last visit's - another model's, perhaps)
  {
    more(); addSubTrim(); screen.latencyUs = 200000; for (int ch = 1; ch <= 16; ++ch) B(boxOf(ch)) = 0;
    B("n00") = 0; SubTrims[0] = 127; SendCommand((char *) "page SubTrimView"); SubTrimToEdit = 0; SubTrimOldPageSaid = false; SubTrimStarts(); CurrentView = SUBTRIMVIEW; freshOut();
    tapAt(60, "plus"); stLoop(1500);                                                       // the page is up (its load is quick), the sixteen writes not yet there: "+" on channel 1 - 0 to 1, and the model has 0 there too
    CHECK(trim(1) == 0 && pageIsModel() && sliderIsShown() && SubTrimShown);
  }
  // G3. HELP (the screen saver likewise) WITH A WRITING-OUT OWED: the page comes back as the model has it (the owed writing-out was forgotten, and the
  //     page showed a number the model had not got until that channel was next touched)
  for (int road = 0; road < 2; ++road)
  {
    more(); addSubTrim(); openSubTrim(); tapCh(10, 4); stLoop(300);
    tapAt(10, "plus!"); stLoop(200);                                                       // a + never heard: the page one ahead on channel 4
    tapAt(10, "plus"); stLoop(150);                                                        // a + refused: channel 4 put right, a writing-out owed when he has paused
    CHECK(trim(4) == 0 && shown(4) == 0 && SubTrimSettleDue);
    tapCh(10, 7); tapAt(60, "plus!"); stLoop(200);                                         // channel 7, a + never heard: the page shows -29, the model has -30 - the owed writing-out would put it right
    CHECK(shown(7) == -29 && trim(7) == -30 && SubTrimSettleDue);
    CurrentView = LOGVIEW; SendCommand((char *) "page LogView"); stLoop(1500);           // Help inside the 0.6 s (the screen saver: page BlankView - the same for this page)
    CHECK(!SubTrimSettleDue);                                                              // (SubTrimPoll lets go of it on another page)
    SendCommand((char *) "page SubTrimView"); CurrentView = SUBTRIMVIEW;
    if (road == 0) pageBack();                                                             // main.cpp "GOTO:" / Utilities.h SaveOrRestoreScreen: SubTrimPageBack()
    stLoop(900);
    if (road == 0) CHECK(pageIsModel() && sliderIsShown() && shown(7) == -30 && SubTrimShown && B("s0") == 1);
    else { CHECK(shown(7) == -29 && trim(7) == -30); say("G3. (without SubTrimPageBack the page shows %d on channel 7 and the model has %d: the fault as it was)\n", shown(7), trim(7)); }
  }
  // G4. OK WHILE A WRITING-OUT IS OWED: the page is put right and STAYS - nothing is saved behind a number that was never seen as it is
  {
    more(); addSubTrim(); openSubTrim(); tapCh(10, 4); stLoop(300);
    tapAt(10, "plus!"); stLoop(200); tapAt(10, "plus"); stLoop(150);
    tapCh(10, 7); tapAt(60, "plus!"); stLoop(200);
    CHECK(shown(7) == -29 && trim(7) == -30 && SubTrimSettleDue);
    const int saves0 = (int) saves.size(), sounds0 = soundsPlayed;
    EndSubTrimView();                                                                      // OK, inside the 0.6 s
    CHECK((int) saves.size() == saves0 && CurrentView == SUBTRIMVIEW && soundsPlayed == sounds0 + 1 && !SubTrimSettleDue);
    stLoop(600); CHECK(screen.page == "SubTrimView" && pageIsModel() && sliderIsShown() && shown(7) == -30);
    EndSubTrimView();                                                                      // OK again: saved, and the page left
    CHECK((int) saves.size() == saves0 + 1 && CurrentView == RXSETUPVIEW && soundsPlayed == sounds0 + 1);
    stLoop(300);
  }
  // ... AND WHILE THE PUTTING-RIGHT IS STILL ON ITS WAY (a screen 300 ms behind): the pause over, the writing-out gone, nothing owed - OK pressed before it
  //     has landed stays too; when the page has said it done, OK saves. A "done" that never comes holds OK for two seconds, no longer
  for (int lostDone = 0; lostDone < 2; ++lostDone)
  {
    more(); addSubTrim(); openSubTrim(); tapCh(10, 4); stLoop(300);
    tapAt(10, "plus!"); stLoop(200); tapAt(10, "plus"); stLoop(150);
    tapCh(10, 7); tapAt(60, "plus!"); stLoop(200);
    screen.latencyUs = 300000; doneToWire = !lostDone;
    while (SubTrimSettleDue) stLoop(5);                                                    // the pause is over: the writing-out has gone (and has not landed)
    CHECK(shown(7) == -29 && trim(7) == -30 && SubTrimDone != SubTrimAsked && SubTrimShown);
    const int saves0 = (int) saves.size(), sounds0 = soundsPlayed;
    EndSubTrimView();                                                                      // OK: the page still shows -29
    CHECK((int) saves.size() == saves0 && CurrentView == SUBTRIMVIEW && soundsPlayed == sounds0 + 1);
    const size_t w0 = writes.size(); stLoop(700); CHECK(pageIsModel() && sliderIsShown() && shown(7) == -30 && writes.size() == w0 + 17);   // (the one writing-out lands; OK wrote nothing more)
    if (!lostDone) { CHECK(SubTrimDone == SubTrimAsked); EndSubTrimView(); CHECK((int) saves.size() == saves0 + 1 && CurrentView == RXSETUPVIEW && soundsPlayed == sounds0 + 1); }
    else
    {
        CHECK(SubTrimDone != SubTrimAsked); EndSubTrimView(); CHECK((int) saves.size() == saves0 && CurrentView == SUBTRIMVIEW && soundsPlayed == sounds0 + 2);   // 0.7 s on, no "done": it stays
        // (the fifteenth review) TWO SECONDS BEHIND THE CLICK AND NO "DONE": it left here, on the clock alone - and a screen that had only stood still was
        // left with the putting-right unread. "rs" is CLICKED ONCE MORE and OK stays; that click said done, OK saves
        const uint16_t asked0 = SubTrimAsked; const size_t w2 = writes.size();
        stLoop(1400); EndSubTrimView();
        CHECK((int) saves.size() == saves0 && CurrentView == SUBTRIMVIEW && soundsPlayed == sounds0 + 3 && SubTrimAsked == (uint16_t) (asked0 + 1) && SubTrimAskedAgain == 1 && !SubTrimSettleDue);
        doneToWire = true; stLoop(700);                                                                        // (this one is heard)
        CHECK(writes.size() == w2 + 1 && writes.back() == "click rs,0" && SubTrimDone == SubTrimAsked && SubTrimAskedAgain == 0 && pageIsModel());
        EndSubTrimView(); CHECK((int) saves.size() == saves0 + 1 && CurrentView == RXSETUPVIEW && soundsPlayed == sounds0 + 3);
    }
    stLoop(300); doneToWire = true;
  }
  // ... A PAGE THAT SAYS "DONE" NO LONGER (every one lost): OK stays inside the two seconds, clicks once more past them - SUBTRIM_ASK_AGAIN_MOST times -
  //     and is then obeyed: OK IS NEVER REFUSED FOR GOOD (the fifteenth review)
  {
    more(); addSubTrim(); openSubTrim(); tapCh(10, 4); stLoop(300); CHECK(SubTrimSaysDone && SubTrimDone == SubTrimAsked && SUBTRIM_ASK_AGAIN_MOST == 2);
    doneToWire = false; freshOut(); stLoop(300);                                              // (another model read under the page: this writing-out's "done" is lost - and every one behind it)
    const int saves0 = (int) saves.size(), sounds0 = soundsPlayed; const uint16_t asked0 = SubTrimAsked;
    EndSubTrimView(); CHECK((int) saves.size() == saves0 && CurrentView == SUBTRIMVIEW && soundsPlayed == sounds0 + 1 && SubTrimAsked == asked0);                    // inside the two seconds: it stays, nothing written
    stLoop(1900); EndSubTrimView(); CHECK((int) saves.size() == saves0 && soundsPlayed == sounds0 + 2 && SubTrimAsked == (uint16_t) (asked0 + 1) && SubTrimAskedAgain == 1);   // past them: clicked once more
    stLoop(500); EndSubTrimView(); CHECK((int) saves.size() == saves0 && soundsPlayed == sounds0 + 3 && SubTrimAsked == (uint16_t) (asked0 + 1));                    // inside that click's two seconds: it stays
    stLoop(1700); EndSubTrimView(); CHECK((int) saves.size() == saves0 && soundsPlayed == sounds0 + 4 && SubTrimAsked == (uint16_t) (asked0 + 2) && SubTrimAskedAgain == 2);   // the second click
    // THE PAGE PUT UP AGAIN (Help's way back) BEGINS THE COUNT AFRESH: its "done" lost as the others - OK clicks once more, twice, and is then obeyed
    // (the break-it round's second look: nothing but a text check held this)
    SendCommand((char *) "page SubTrimView"); pageBack(); CHECK(SubTrimAskedAgain == 0); const uint16_t asked1 = SubTrimAsked;
    stLoop(2100); EndSubTrimView(); CHECK((int) saves.size() == saves0 && CurrentView == SUBTRIMVIEW && soundsPlayed == sounds0 + 5 && SubTrimAsked == (uint16_t) (asked1 + 1) && SubTrimAskedAgain == 1);
    stLoop(2100); EndSubTrimView(); CHECK((int) saves.size() == saves0 && CurrentView == SUBTRIMVIEW && soundsPlayed == sounds0 + 6 && SubTrimAsked == (uint16_t) (asked1 + 2) && SubTrimAskedAgain == 2);
    stLoop(2100); EndSubTrimView(); CHECK((int) saves.size() == saves0 + 1 && CurrentView == RXSETUPVIEW && soundsPlayed == sounds0 + 6 && SubTrimAsked == (uint16_t) (asked1 + 2));   // ... and no third: obeyed
    stLoop(300); doneToWire = true;
    // the count begins afresh with the page put up again, and with a "done" heard
    openSubTrim(); CHECK(SubTrimAskedAgain == 0 && SubTrimDone == SubTrimAsked);
  }
  // ... A PAGE JUST PUT UP, OK AT ONCE (its numbers not yet landed on a screen 300 ms behind): it stays until the page has said them done -
  //     the page may be showing the last visit's numbers, or (put up AGAIN, by Help's way back) a number from before a change that was taken
  {
    more(); addSubTrim(); screen.latencyUs = 300000; SendCommand((char *) "page SubTrimView"); SubTrimToEdit = 0; SubTrimOldPageSaid = false; SubTrimStarts(); CurrentView = SUBTRIMVIEW; freshOut();
    stLoop(50); const int saves0 = (int) saves.size(), sounds0 = soundsPlayed; CHECK(!SubTrimShown && SubTrimDone != SubTrimAsked && SubTrimSaysDone);
    EndSubTrimView(); CHECK((int) saves.size() == saves0 && CurrentView == SUBTRIMVIEW && soundsPlayed == sounds0 + 1);
    stLoop(900); CHECK(SubTrimShown && SubTrimDone == SubTrimAsked && pageIsModel());
    EndSubTrimView(); CHECK((int) saves.size() == saves0 + 1 && CurrentView == RXSETUPVIEW && othersAre(0) && trim(7) == -30); stLoop(300);
  }
  //     (the fifteenth review; SU24 of the break-it list was noticed by a text check alone) ... AND A "DONE" BY ITSELF MAKES THIS A PAGE THAT SAYS "DONE":
  //     the first visit since power-on, no touch made yet - no burst heard -, another model read under the page: OK at once stays until the page has
  //     said THAT model's numbers done
  {
    more(); addSubTrim(); SubTrimSaysDone = false; SubTrimShown = false; SubTrimAsked = SubTrimDone = 0;                    // (as at this board's start)
    screen.latencyUs = 200; SendCommand((char *) "page SubTrimView"); SubTrimToEdit = 0; SubTrimOldPageSaid = false; SubTrimStarts(); CurrentView = SUBTRIMVIEW; freshOut(); stLoop(600);
    CHECK(SubTrimSaysDone && SubTrimShown && SubTrimDone == SubTrimAsked && pageIsModel() && trim(7) == -30);                // the page's first "done" has been heard - and nothing else
    screen.latencyUs = 300000; SubTrims[6] = 127 + 12; freshOut(); stLoop(40);                                               // another model read (channel 7: +12): its writing-out is on its way
    const int saves0 = (int) saves.size(), sounds0 = soundsPlayed; CHECK(shown(7) == -30 && !SubTrimShown);
    EndSubTrimView(); CHECK((int) saves.size() == saves0 && CurrentView == SUBTRIMVIEW && soundsPlayed == sounds0 + 1);   // OK: the page still shows the model before - it stays
    stLoop(900); CHECK(pageIsModel() && shown(7) == 12); EndSubTrimView(); CHECK((int) saves.size() == saves0 + 1 && CurrentView == RXSETUPVIEW); stLoop(300);
    screen.latencyUs = 200;
  }
  //     THE STORM'S OWN ROAD (trial 118771 of seed 4242001), by hand: a change taken, a stale writing-out landed on top of it (the putting-right owed),
  //     Help inside the pause (what is owed is forgotten), the way back - and OK in the milliseconds in which the page is being written out
  {
    more(); addSubTrim(); openSubTrim(); screen.latencyUs = 60000; tapCh(10, 7); stLoop(400);
    SubTrimPageOut(false); stLoop(30);                                                     // a writing-out of this board's is on its way (60 ms) ...
    tapAt(1, "plus"); stLoop(20);                                                          // ... "+" in front of its landing: -30 to -29, TAKEN (it started from the model's number) - and owed, the click not yet said done
    CHECK(trim(7) == -29 && SubTrimSettleDue);
    stLoop(100); CHECK(shown(7) == -30);                                                   // the stale writing-out has landed on top of it: the page shows -30, the model has -29
    CurrentView = LOGVIEW; SendCommand((char *) "page LogView"); stLoop(700); CHECK(!SubTrimSettleDue);   // Help: what was owed is forgotten
    SendCommand((char *) "page SubTrimView"); CurrentView = SUBTRIMVIEW; pageBack(); stLoop(20);            // the way back: the page is being written out (60 ms behind)
    const int saves0 = (int) saves.size(), sounds0 = soundsPlayed; const int showsAtOk = shown(7);
    EndSubTrimView();                                                                      // OK - he sees -30
    say("G4. OK as the page comes back from Help, still showing %d (the model has %d): saved %d, the page %s\n", showsAtOk, trim(7), (int) saves.size() - saves0, CurrentView == SUBTRIMVIEW ? "stays" : "was LEFT");
    CHECK(showsAtOk == -30 && trim(7) == -29 && (int) saves.size() == saves0 && CurrentView == SUBTRIMVIEW && soundsPlayed == sounds0 + 1);
    stLoop(600); CHECK(pageIsModel() && shown(7) == -29); EndSubTrimView(); CHECK((int) saves.size() == saves0 + 1 && CurrentView == RXSETUPVIEW); stLoop(300);
  }
  //     ... and a page that has never said "done" (a page file from before; this board just started): nothing can have been taken - OK is obeyed at once
  {
    more(); addSubTrim(); screen.latencyUs = 300000; SendCommand((char *) "page SubTrimView"); SubTrimToEdit = 0; SubTrimOldPageSaid = false; SubTrimStarts(); CurrentView = SUBTRIMVIEW; freshOut();
    SubTrimSaysDone = false;                                                              // (as at this board's start)
    stLoop(50); const int saves0 = (int) saves.size();
    EndSubTrimView(); CHECK((int) saves.size() == saves0 + 1 && CurrentView == RXSETUPVIEW && othersAre(0) && trim(7) == -30); stLoop(900);
    CHECK(!SubTrimSaysDone);                                                              // (its "done" came when the page had been left: not this page's business any more)
    SubTrimSaysDone = true;                                                               // (the scenes behind this one are of a page that says "done")
  }
  // G5. THE PAGE'S "DONE" IS NO PRESS: the page left while a click's "done" is on its way - nothing is logged "not obeyed", and on the page it is served
  {
    more(); addSubTrim(); openSubTrim(); screen.latencyUs = 40000; tapCh(10, 4); stLoop(400);
    tapAt(10, "plus!"); stLoop(300);
    const int stale0 = stale;
    tapAt(10, "plus"); stLoop(14);                                                         // a + refused: the box, the click's number, the click - on their way to a screen 40 ms behind
    SendCommand((char *) "page FrontView"); CurrentView = FRONTVIEW;                       // ... and the page is left
    stLoop(1500);
    if (stale != stale0) { say("G5. presses 'not obeyed': %d;", stale - stale0); for (auto &c : staleCodes) say(" [%s]", c.c_str()); say("\n"); }
    CHECK(stale == stale0);
    { uint8_t d[14] = { 'S', 't', 'E', 'D', 'I', 'T', 9, 0, 0, 0, 9, 0, 0, 0 }; uint8_t e[22] = { 'S', 't', 'E', 'D', 'I', 'T' }; CHECK(IsPageOwnWord(d, 14) && !IsPageOwnWord(d, 13) && !IsPageOwnWord(e, 22) && !IsPageOwnWord(d, 6)); }
  }
  // G6. THE LOG: a change not taken, and words not kept, leave one line a visit - kept for a quiet moment while the model may fly
  {
    more(); addSubTrim(); openSubTrim(); tapCh(10, 4); stLoop(300);
    const size_t log0 = logLines.size();
    tapAt(10, "plus!"); stLoop(200); tapAt(10, "plus"); stLoop(900); tapAt(10, "plus!"); stLoop(200); tapAt(10, "plus"); stLoop(900);    // two changes not taken in one visit
    CHECK(logLines.size() == log0 + 1 && logLines.back().find("Sub-trim page: channel 4 not taken - it did not start from the model's number (the page made 2 of 1; the model has 0); put right on the page B211") == 0 && trim(4) == 0 && pageIsModel());
    mayFly = true; SendCommand((char *) "page SubTrimView"); pageBack(); stLoop(700);                                                    // the next visit, the model flying
    tapAt(10, "plus!"); stLoop(200); tapAt(10, "plus"); stLoop(900);
    CHECK(logLines.size() == log0 + 2 && logLines.back() == "(kept for later) Sub-trim ch 1: a change not taken");
    mayFly = false;
  }
  // G6b. WORDS NOT KEPT FOR WANT OF ROOM (the main loop held elsewhere while a finger dragged): said in the log, once; the page written out when he has
  //      paused - and OK pressed BEFORE the main loop has looked (EndSubTrimView looks for itself) stays, and writes the page out
  {
    more(); addSubTrim(); openSubTrim(); tapCh(10, 7); stLoop(300);
    B("n6") = -12; B("n0") = -12; B("h0") = 115;                                           // (touches whose words were not kept: the page shows -12, the model has -30)
    const size_t log0 = logLines.size(), w0 = writes.size();
    PendingDropped = (uint16_t) (PendingDropped + 3); stLoop(300);                         // the main loop's look (SubTrimPoll) sees it: no word of the slider's has been served - no pause to wait out
    CHECK(logLines.size() == log0 + 1 && logLines.back().find("Sub-trim page: frames from the screen were not kept for want of room with the page up") == 0 && writes.size() == w0 + 17 && pageIsModel() && sliderIsShown());
    B("n6") = -11; PendingDropped = (uint16_t) (PendingDropped + 2); stLoop(300);          // (again in the same visit: written out again, no second line)
    CHECK(logLines.size() == log0 + 1 && pageIsModel() && writes.size() == w0 + 34);
    B("n6") = -9; B("n0") = -9; B("h0") = 118;                                             // ... once more, and OK at once - before any pass of the main loop
    PendingDropped = (uint16_t) (PendingDropped + 1);
    const int saves0 = (int) saves.size(), sounds0 = soundsPlayed; const size_t w1 = writes.size();
    EndSubTrimView();
    CHECK((int) saves.size() == saves0 && CurrentView == SUBTRIMVIEW && soundsPlayed == sounds0 + 1 && !SubTrimSettleDue);
    stLoop(600); CHECK(pageIsModel() && shown(7) == -30 && writes.size() == w1 + 17);
    EndSubTrimView(); CHECK((int) saves.size() == saves0 + 1 && CurrentView == RXSETUPVIEW); stLoop(300);
  }
  // G6c. (the fifteenth review) THE LINE SAYS WHICH RULE REFUSED: beyond what the card keeps; the page had not yet said this model's numbers done
  {
    auto four = [](long a, long b, long c, long d) { std::vector<uint8_t> v = { 'S', 't', 'E', 'D', 'I', 'T' }; for (long x : { a, b, c, d }) for (int k = 0; k < 4; ++k) v.push_back((uint8_t) ((uint32_t) (int32_t) x >> (8 * k))); return v; };
    more(); addSubTrim(); openSubTrim(); tapCh(10, 7); stLoop(300);
    size_t log0 = logLines.size();
    burstNow(four(7, -30, 118, 118)); stLoop(200);
    CHECK(trim(7) == -30 && logLines.size() == log0 + 1 && logLines.back().find("Sub-trim page: channel 7 not taken - it went beyond what the card keeps (the page made 118 of -30; the model has -30); put right on the page B211") == 0);
    more(); addSubTrim(); openSubTrim(); tapCh(10, 7); stLoop(300); log0 = logLines.size();
    screen.latencyUs = 300000; freshOut(); CHECK(!SubTrimShown);                             // (another model read under the page: its writing-out is on its way to a screen that is behind)
    burstNow(four(7, -30, -29, -29)); stLoop(100);                                           // a touch that starts from the model's own number - before the page has said the writing-out done
    CHECK(trim(7) == -30 && logLines.size() == log0 + 1 && logLines.back().find("Sub-trim page: channel 7 not taken - the page had not yet said this model's numbers done (the page made -29 of -30; the model has -30); put right on the page B211") == 0);
    CHECK(logLines.back().size() < 189);                                                     // (the longest of the four fits the line whole)
    stLoop(1500); screen.latencyUs = 200;
  }
  // G8 (the fifteenth review; the break-it round's second look: these were held by the text alone). Trims.h SubTrimWordLetGo, BY ITSELF and through
  //    Nextion.h's own PendingPush
  {
    auto four = [](long a, long b, long c, long d) { std::vector<uint8_t> v = { 'S', 't', 'E', 'D', 'I', 'T' }; for (long x : { a, b, c, d }) for (int k = 0; k < 4; ++k) v.push_back((uint8_t) ((uint32_t) (int32_t) x >> (8 * k))); return v; };
    more(); addSubTrim(); openSubTrim(); stLoop(300);
    const std::vector<uint8_t> touch = four(1, 0, 1, 1), done = { 'S', 't', 'E', 'D', 'I', 'T', 5, 0, 0, 0, 5, 0, 0, 0 };
    // (a) the page's "done" let go is no touch: nothing is owed for it; a touch's burst let go OWES THE PAGE ITS WRITING-OUT
    SubTrimSettleDue = false; RealSubTrimWordLetGo(done.data(), (uint16_t) done.size(), true); CHECK(!SubTrimSettleDue);
    RealSubTrimWordLetGo(touch.data(), (uint16_t) touch.size(), true); CHECK(SubTrimSettleDue);
    // (b) on ANOTHER page nothing is owed - but THE BURST'S FORM SAYS WHAT KIND OF PAGE FILE SAID IT, on whatever page this board is (the sixteenth
    //     review: a touch landed on the page as it went, its burst came on the next page and taught nothing - the next showing's first OK left at once)
    SubTrimSettleDue = false; SubTrimSaysDone = false; CurrentView = RXSETUPVIEW; RealSubTrimWordLetGo(touch.data(), (uint16_t) touch.size(), true);
    CHECK(!SubTrimSettleDue && SubTrimSaysDone);
    //     ... the word alone, a burst not framed, the page's "done", another page's frame: nothing is concluded there
    SubTrimSaysDone = false; RealSubTrimWordLetGo((const uint8_t *) "StEDIT", 6, false); RealSubTrimWordLetGo(touch.data(), (uint16_t) touch.size(), false);
    RealSubTrimWordLetGo(done.data(), (uint16_t) done.size(), true); RealSubTrimWordLetGo((const uint8_t *) "XxEDIT0123456789abcdef", 22, true);
    CHECK(!SubTrimSettleDue && !SubTrimSaysDone); CurrentView = SUBTRIMVIEW;
    // (c) the word alone (a page file from before) owes the writing-out and says nothing of "done"; a burst in this release's form says that the page says it
    RealSubTrimWordLetGo((const uint8_t *) "StEDIT", 6, false); CHECK(SubTrimSettleDue && !SubTrimSaysDone);
    SubTrimSettleDue = false; RealSubTrimWordLetGo(touch.data(), (uint16_t) touch.size(), true); CHECK(SubTrimSettleDue && SubTrimSaysDone);
    // (d) THROUGH THE READER: the store of kept frames is full - a touch's burst finds no room (Nextion.h PendingPush): counted there, and told here
    SubTrimSaysDone = false; SubTrimSettleDue = false; stLoop(50);
    { const uint8_t code[4] = { 0x80 + 99, 0, 0, 0 }; int guard = 0; while (PendingCount < MAXPENDINGFRAMES && ++guard < 40) PendingPush(code, 4, false); }
    CHECK(PendingCount == MAXPENDINGFRAMES);
    const uint16_t d0 = PendingDropped; PendingPush(touch.data(), (uint16_t) touch.size(), true);
    CHECK((uint16_t) (PendingDropped - d0) == 1 && SubTrimSaysDone && SubTrimSettleDue && PendingCount == MAXPENDINGFRAMES);
    PendingCount = 0; PendingEventLen = 0; stLoop(1500); CHECK(pageIsModel() && sliderIsShown());
  }
  // G9. THE PAGE'S SECOND MARKER LOST ON THE WIRE (the first heard): for this board the page is "coming up" until it has found the marker lost - and a
  //     touch made meanwhile is let go without a word (Nextion.h DropUnconfirmedPress, its second way out). IT OWES THE PAGE ITS WRITING-OUT: the page
  //     showed the touch, the model had not got it, and nothing was owed (the break-it round's second look: no run noticed this way out)
  {
    more(); addSubTrim(); openSubTrim(); stLoop(300); screen.latencyUs = 20000; screen.loadUs = 400000;
    CurrentView = LOGVIEW; SendCommand((char *) "page LogView"); stLoop(900);                 // Help ...
    SendCommand((char *) "page SubTrimView"); CurrentView = SUBTRIMVIEW; pageBack();          // ... and its way back
    { int guard = 0; while (ScreenMarkOldPage && ++guard < 3000) stLoop(1); }                 // the first marker has been heard (the page is still loading)
    screen.sysMute.insert("ldrcsync");                                                        // ... the second never is
    stLoop(800); screen.sysMute.clear();
    const bool between = ScreenMarkAwaited != 0 && !ScreenMarkOldPage;
    CHECK(between && SubTrimShown && pageIsModel());                                          // the page is up and written out, its "done" heard - and for this board still coming up
    const uint16_t let0 = LoadPrintsLetGo; const int had = trim(1);
    tapAt(5, "plus"); stLoop(150);
    say("G9. the page's second marker lost: '+' made the page show %d (the model has %d); let go between the markers %u; a writing-out owed %d\n", shown(1), trim(1), (unsigned) (uint16_t) (LoadPrintsLetGo - let0), (int) SubTrimSettleDue);
    CHECK((uint16_t) (LoadPrintsLetGo - let0) == 1 && shown(1) == had + 1 && trim(1) == had && SubTrimSettleDue);
    stLoop(4000); CHECK(pageIsModel() && sliderIsShown() && trim(1) == had);
    screen.latencyUs = 200; screen.loadUs = 90000;
  }
  // G7. a burst of the right length whose channel is none of the page's: nothing is taken, and the page is written out when he has paused
  {
    more(); addSubTrim(); openSubTrim(); tapCh(10, 7); stLoop(300);
    auto four = [](long a, long b, long c, long d) { std::vector<uint8_t> v = { 'S', 't', 'E', 'D', 'I', 'T' }; for (long x : { a, b, c, d }) for (int k = 0; k < 4; ++k) v.push_back((uint8_t) ((uint32_t) (int32_t) x >> (8 * k))); return v; };
    B("n6") = -12; B("n0") = -12; B("h0") = 115;                                           // (the page made -12 of it ...)
    const size_t w0 = writes.size();
    burstNow(four(7 + 32 * 256, -30, -12, -12)); stLoop(100);                              // ... and a space fell into the channel's number
    CHECK(trim(7) == -30 && writes.size() == w0 && SubTrimSettleDue);
    stLoop(900); CHECK(pageIsModel() && sliderIsShown() && writes.size() == w0 + 17);
  }
  // ===================================================================================================== F. THE CARD'S RULE
  // F1. 117 either way is exactly what SDcard.h's reader keeps (it centres a sub trim it finds beyond) - and the page stops there by itself
  {
    CHECK(!cardCentres((uint8_t) (127 + SUBTRIM_MOST)) && !cardCentres((uint8_t) (127 - SUBTRIM_MOST)) && cardCentres((uint8_t) (127 + SUBTRIM_MOST + 1)) && cardCentres((uint8_t) (127 - SUBTRIM_MOST - 1)));
    more(); addSubTrim(); openSubTrim(); tapCh(10, 5); stLoop(300);
    slide(10, 127); stLoop(300); CHECK(trim(5) == 117 && pageIsModel() && sliderIsShown());                      // the slider's own end
    for (int i = 0; i < 5; ++i) tapAt(10 + i * 120, "plus"); stLoop(900); CHECK(trim(5) == 117 && pageIsModel());
    slide(10, -127); stLoop(300); for (int i = 0; i < 5; ++i) tapAt(10 + i * 120, "minus"); stLoop(900); CHECK(trim(5) == -117 && pageIsModel() && othersAre(5));
  }
  continue;
  olderPage:
  // ===================================================================================================== D. THE PAGE FILE FROM BEFORE
  // D1. its word comes alone (and a tapped channel does not put its number into the slider's): NOTHING IS TAKEN, whatever is touched - the title says
  //     so once, the log says so once, the pilot hears it once; and nothing is asked of the screen
  {
    more(); addSubTrim(); openSubTrim(); const int gets0 = screen.gets, sounds0 = soundsPlayed; const size_t log0 = logLines.size();
    slide(10, 60); tapAt(200, "plus"); tapCh(400, 7); tapAt(520, "plus"); tapAt(700, "zero"); tapCh(900, 3); slide(1000, -40); tapAt(1200, "minus");
    stLoop(2500);
    say("D1. the page file from before, eight touches: the model unchanged %d; the title '%s'; said in the log %d time(s), heard %d time(s); asked of the screen %d\n", (int) (othersAre(0) && trim(7) == -30), P().boxes["t0"].txt.c_str(), (int) (logLines.size() - log0), soundsPlayed - sounds0, screen.gets - gets0);
    CHECK(othersAre(0) && trim(7) == -30 && SubTrimOldPageSaid);
    CHECK(P().boxes["t0"].txt == "Subtrim: run Check for update first" && logLines.size() == log0 + 1 && logLines.back().find("older than this firmware") != std::string::npos && soundsPlayed == sounds0 + 1 && screen.gets == gets0);
    // (the author's, the fourteenth review's brief) ... the model's name, which stands over the left of the title's bar, is taken out of the way - once;
    // and THE PAGE DOES NOT GO ON SHOWING NUMBERS THE MODEL HAS NOT GOT: when he has paused, every channel's box is the model's again (it showed 60, 61,
    // 1, 0 and -41 of his touches until the page was left)
    { int hidden = 0; for (const std::string &v : screen.visSaid) hidden += v.find("vis ModelName,0") != std::string::npos;
      bool boxesRight = true; for (int ch = 1; ch <= 16; ++ch) boxesRight &= shown(ch) == trim(ch);
      say("     ... the model's name out of the title's way %d time(s); when he has paused every channel's box shows the model's number: %d\n", hidden, (int) boxesRight);
      CHECK(hidden == 1 && boxesRight);
      // ... HELP AND BACK (the fourteenth review): the title's message is still there - the screen keeps a text - and the model's name is taken out of
      //     its way again, at once: no second sound, no second line in the log; and the page is written out
      const int sounds1 = soundsPlayed; const size_t log1 = logLines.size();
      slide(10, 33); stLoop(100);                                                             // (a touch whose number the model does not take: the page shows 33)
      CurrentView = LOGVIEW; SendCommand((char *) "page LogView"); stLoop(700);
      SendCommand((char *) "page SubTrimView"); CurrentView = SUBTRIMVIEW; pageBack(); stLoop(900);
      hidden = 0; for (const std::string &v : screen.visSaid) hidden += v.find("vis ModelName,0") != std::string::npos;
      boxesRight = true; for (int ch = 1; ch <= 16; ++ch) boxesRight &= shown(ch) == trim(ch);
      CHECK(hidden == 2 && boxesRight && soundsPlayed == sounds1 && logLines.size() == log1 && SubTrimOldPageSaid && P().boxes["t0"].txt == "Subtrim: run Check for update first"); }
    // ... while he is still touching, nothing is written (the writing-out waits for his pause)
    { openSubTrim(); stLoop(700); writes.clear(); for (int i = 0; i < 6; ++i) tapAt(10 + i * 300, "plus"); stLoop(1700); const size_t during = writes.size(); stLoop(900);
      bool boxesRight = true; for (int ch = 1; ch <= 16; ++ch) boxesRight &= shown(ch) == trim(ch);
      CHECK(during == 0 && writes.size() == 17 && boxesRight && othersAre(0) && trim(7) == -30); }
    // ... and while the model may fly the line is kept for a quiet moment, short; said again when the page is put up again
    openSubTrim(); mayFly = true; const size_t log1 = logLines.size(); tapAt(10, "plus"); stLoop(300); mayFly = false;
    CHECK(logLines.size() == log1 + 1 && logLines.back() == "(kept for later) Sub-trim page file old: not taken" && othersAre(0));
  }
  }
  wordHook = nullptr; tapScript = nullptr; loadScript = nullptr; cmdScript = nullptr;
'''
SDC = m.release(m.src('include/SDcard.h'))
_mo = re.search(r'SubTrims\[i\] = SDRead8BITS\(SDCardAddress\);\s*if \(\(SubTrims\[i\] < (\d+)\) \|\| \(SubTrims\[i\] > (\d+)\)\)\s*SubTrims\[i\] = 127;', SDC)
if not _mo:
    print('FAIL: SDcard.h ReadOneModel: the rule that centres a sub trim it takes for undefined is not there as this scene knows it (Trims.h SUBTRIM_MOST is held against it)'); sys.exit(1)
EXTRA = EXTRA.replace('@CARDRULE@', 'static bool cardCentres(uint8_t v) { return (v < %s) || (v > %s); }   // (SDcard.h ReadOneModel\'s own rule, with its numbers as they stand there)\n' % _mo.groups())
if __name__ == '__main__':   # (scene_subtrim_storm takes this file's pretend page and helpers)
    if 'new' not in KINDS: print('NOTE: this release\'s Sub-trim page file was not found (the screen\'s repository has the one before; LDRC_NEW_PAGE32 names no file): its scripts are taken as this scene has them')
    sys.exit(lib.build_run('subtrim', SCENES, extra=EXTRA, more_defines=('SUBTRIMVIEW',)))
