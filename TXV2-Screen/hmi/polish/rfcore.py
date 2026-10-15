"""POLISH, the Rotorflight core pages (10 Oct 2026, Malcolm: "make the screens look more beautiful, well designed and easy to
use ... Don't change the logic anywhere"): Rates 1, Rates + 42, PIDs 40, PID + 7, Governor 6 and Governor (global) 5.
(The menu 8 and its settings page 61 are made whole by hmi/rfmenu_pages.py, which carries their polish.)

These pages come out of hmi/islands.py (from hmi/pre_islands); this runs after it and sets every place, size, colour and word
it touches to an ABSOLUTE value, so it can run any number of times. What the house style asks, page by page:
  - the axes in their pale shades with black words, the same hue on every page: Roll pink, Pitch green, Yaw lavender,
    Collective yellow (they were saturated red, green, purple and yellow - the hardest black words to read in sunlight);
  - a table's heads as white words on the card (they were khaki boxes, a fourth kind of thing beside labels and values);
  - labels that open their value as pale boxes, one shade a group, units in square brackets after the words;
  - a bar that only repeated the title (PIDs' "PID Controller Gains") gone; the rates type a line that says what it is;
  - the help's title the page's title + "help"; a keypad's question in the words of the label that opened it.
Never a name, an id, an event's action, a keyboard, or anything the Teensy reads or writes (hmi/logic_guard.py checks)."""
from . import comp, put, rect, park, add_text, ev_title

NAVY, WHITE, BLACK, SOFT = 4426, 65535, 0, 50712
ROLL, PITCH, YAW, COLL = 65341, 59323, 61215, 65497          # pale pink, green, lavender, yellow (rescue_pages.PALE)
PALE_YELLOW, PALE_BLUE, PALE_GREEN = 65497, 57215, 59323
BTN_GREY = 54938

# 11 Oct 2026 (the reviewers of the merged polish): a page's default words are empty or exactly what the Teensy writes, since
# a screen-only restart shows them - so no "Model name" in the model-name yellow as if it were a model (page 8 keeps its
# t11 "Model name": src/cli_device.h modelName() reads the open page's t11 for the command line's file names, "" = not known).
# The message boxes ("busy", page 5's t4) span whole columns, edge to edge, so no label is cut mid-word - but each only where
# it hides no touchable part more than it did before the polish (hmi/touch_audit.py: while it shows it takes their taps).


def head(pg, name, **kw):
    """A table's head: white words on the card."""
    return put(pg, name, c={'bco': NAVY, 'pco': WHITE}, **kw)


def label_box(pg, name, shade, **kw):
    """A label that opens its value: a pale box, black words in the middle."""
    return put(pg, name, c={'bco': shade, 'pco': BLACK}, a={'xcen': 1}, **kw)


def words(pg, name, txt):
    """New words for a label; its txt_maxl never lower than the words (the logic guard lets it only go up)."""
    c = put(pg, name, txt=txt)
    a = c.setdefault('a', {})
    if a.get('txt_maxl', 0) < len(txt): a['txt_maxl'] = len(txt)
    return c


def keypad(pg, name, old, new):
    """The keypad's question (keybdB.t1) in the label's words. Idempotent."""
    ev_title(pg, name, 'r', old, new)


# ------------------------------------------------------------------ Rates (page 1)
def rates(pg):
    for n, col in (('t1', ROLL), ('t2', PITCH), ('t3', YAW), ('t8', COLL)):
        put(pg, n, c={'bco': col})
    for n in ('t4', 't5', 't6', 't7'):   # (the Teensy writes t4-t6's words: Rates/Axis, Rate/Centre..., Shape/Max...; the keypads read t5-t7)
        head(pg, n)
    # (defaults: what the Teensy writes for Rotorflight 2.3 - "Centre Sens." and "Maximum" it never writes; the keypads
    # read these heads, so they are words, not empty)
    put(pg, 't5', txt='Rate'); put(pg, 't6', txt='Shape')
    # The rates TYPE (the Teensy writes its name: Actual, Rotorflight 2.3 ...): it decides what the columns mean, so a line
    # that says so - "Rates type:" in the quieter shade, the name in white - not an olive bar that read like a version
    add_text(pg, 'rtl', after='t10', x=52, y=119, w=344, h=36, font=2, txt='Rates type:',
             c={'bco': NAVY, 'pco': SOFT, 'borderc': 0}, a={'xcen': 2, 'ycen': 1, 'txt_maxl': 12})
    put(pg, 't10', x=402, y=119, w=346, h=36, txt='', c={'bco': NAVY, 'pco': WHITE}, a={'xcen': 0, 'style': 0})   # (no type shown before the Teensy says which: it said Actual)
    put(pg, 't9', txt='')                # (the Teensy writes "Rate n" here; "Bank 1" was the wrong kind of word to show before it does)
    put(pg, 't11', txt='')
    words(pg, 'b2', 'Dynamics ...')      # (15 Oct 2026, the phone app's words: the page it opens is "Rates: dynamics", the
    # phone's "Dynamics" card on its Rates page; "Rates + ..." before)
    words(pg, 't7', 'Expo')              # (the phone's column; "Exponential" before. The keypads read it: "Roll Expo")
    put(pg, 't4', txt='')                # (the phone's corner is empty; the Teensy writes "" there too since 15 Oct)
    # the message box over the rates-type line and the heads, the island's whole inner width: only words that are never
    # touched lie there (in the table it cut the axis names, and wider there it would take the right column's taps)
    put(pg, 'busy', x=52, y=119, w=696, h=76, txt='')
    ev_title(pg, 'b0', 'r', 'Rates setup help', 'Rates (Rotorflight) help')


# ------------------------------------------------------------------ Rates + (page 42)
# The rhythm of Rates (page 1): rows 36 high, 40 apart (they were 32 high, 34 apart - fifteen small targets for a finger),
# the four value columns 5 px apart (they touched, 2 px); the island 10 px wider so the longest label has room in its box,
# and 40 px taller (25 px of picture still shows above and below it).
R42_CARD = (24, 83, 752, 372)
R42_LX, R42_LW = 40, 295                             # the label column, 6 px before the first value
R42_X = [341 + 106 * k for k in range(4)]; R42_W = 101
R42_Y0, R42_P, R42_H = 99, 40, 36
R42_ROW = {'t4': 0, 't1': 1, 't2': 2, 't3': 3, 't10': 4, 't12': 5, 't13': 6}
R42_KEYS = {   # the keypad's question in the words of the row and the column (they were "Roll RT", "Col SPGF" ...)
    # (15 Oct 2026: the phone app's words; each first old form is the HMI's, the second the 10 Oct polish's)
    'n0': (('Roll RT', 'Roll response time [ms]'), 'Roll response time (ms)'), 'n1': (('Pitch RT', 'Pitch response time [ms]'), 'Pitch response time (ms)'),
    'n2': (('Yaw RT', 'Yaw response time [ms]'), 'Yaw response time (ms)'), 'n3': (('Col RT', 'Collective response time [ms]'), 'Collective response time (ms)'),
    'n4': (('Roll SPG', 'Roll boost gain'), 'Roll stick sharpening (boost gain)'), 'n5': (('Pitch SPG', 'Pitch boost gain'), 'Pitch stick sharpening (boost gain)'),
    'n6': (('Yaw SPG', 'Yaw boost gain'), 'Yaw stick sharpening (boost gain)'), 'n7': (('Col SPGF', 'Collective boost gain'), 'Collective stick sharpening'),
    'n8': (('Roll SPC', 'Roll boost cutoff [Hz]'), 'Roll sharpening smoothing (Hz)'), 'n9': (('Pitch SPC', 'Pitch boost cutoff [Hz]'), 'Pitch sharpening smoothing (Hz)'),
    'n10': (('Yaw SPC', 'Yaw boost cutoff [Hz]'), 'Yaw sharpening smoothing (Hz)'), 'n11': (('Col SPC', 'Collective boost cutoff [Hz]'), 'Collective sharpening smoothing (Hz)'),
    'n12': (('Yaw DCG', 'Yaw dynamic ceiling gain'), 'Yaw fast-move headroom (ceiling)'), 'n13': (('Yaw DDG', 'Yaw dynamic deadband gain'), 'Yaw stick-centre quieting'),
    't14': (('Yaw DDF', 'Yaw deadband filter [Hz]'), 'Yaw quieting smoothing (Hz)'),
}


def rates_plus(pg):
    rect(pg, 'card', *R42_CARD)
    y = lambda r: R42_Y0 + r * R42_P
    for k, (n, col) in enumerate((('t5', ROLL), ('t6', PITCH), ('t7', YAW), ('t8', COLL))):
        put(pg, n, x=R42_X[k], y=y(0), w=R42_W, h=R42_H, c={'bco': col})
    head(pg, 't4', x=R42_LX, y=y(0), w=R42_LW, h=R42_H, a={'xcen': 0})
    grid = (('n0', 'n1', 'n2', 'n3'), ('n4', 'n5', 'n6', 'n7'), ('n8', 'n9', 'n10', 'n11'))
    for r, row in enumerate(grid):
        for k, n in enumerate(row): rect(pg, n, R42_X[k], y(r + 1), R42_W, R42_H)
    for r, n in enumerate(('n12', 'n13', 't14')):
        rect(pg, n, R42_X[2], y(r + 4), R42_W, R42_H)
    words(pg, 't0', 'Rates: dynamics')   # (15 Oct 2026: the phone app's "Dynamics" card on its Rates page; "Rates + (Rotorflight)" before)
    for n, txt in (('t1', 'Response time (ms)'), ('t2', 'Stick sharpening (boost gain)'), ('t3', 'Sharpening smoothing (Hz)'),
                   ('t10', 'Fast-move headroom'), ('t12', 'Stick-centre quieting'), ('t13', 'Quieting smoothing (Hz)')):
        words(pg, n, txt)
        label_box(pg, n, PALE_BLUE, x=R42_LX, y=y(R42_ROW[n]), w=R42_LW, h=R42_H)
    by = R42_CARD[1] + R42_CARD[3] - 16 - 50          # the bottom row on the island's foot: Save beside OK, OK at the right
    rect(pg, 'b1', R42_CARD[0] + R42_CARD[2] - 16 - 160, by, 160, 50)
    rect(pg, 'b3', R42_CARD[0] + R42_CARD[2] - 16 - 160 - 12 - 160, by, 160, 50)
    # the message box the island's whole inner width, over rows 4-5 (the dynamics: labels and the Yaw values only - the
    # Collective column has nothing there, so it takes no tap it did not take before the polish)
    rect(pg, 'busy', R42_LX, y(4), R42_X[3] + R42_W - R42_LX, 2 * R42_P - (R42_P - R42_H))
    for n, (old, new) in R42_KEYS.items(): keypad(pg, n, old, new)
    put(pg, 't9', txt='')                # (the Teensy writes "Rate n")
    put(pg, 't11', txt='')
    ev_title(pg, 'b0', 'r', ('Rates Advanced setup help', 'Rates + (Rotorflight) help'), 'Rates: dynamics help')


# ------------------------------------------------------------------ PIDs (page 40)
# The olive "PID Controller Gains" bar only repeated the title: parked, and the island 44 px shorter. The columns 5 px apart,
# as on Rates (they touched, 1 px), and 5 px between the rows too (they were 2 and 3).
P40_CARD = (37, 133, 726, 271)
P40_LX, P40_LW = 53, 82
P40_X = [140 + 102 * k for k in range(6)]; P40_W = 97
P40_HEAD_Y, P40_ROW_Y, P40_H = 149, (194, 239, 284), 40


def pids(pg):
    rect(pg, 'card', *P40_CARD)
    park(pg, 't10')
    heads = ('t5', 't6', 't7', 't8', 't12', 't13')
    for k, (n, txt) in enumerate(zip(heads, ('P', 'I', 'D', 'FF', None, None))):
        head(pg, n, x=P40_X[k], y=P40_HEAD_Y, w=P40_W, h=P40_H)
        if txt: put(pg, n, txt=txt)
    head(pg, 't4', x=P40_LX, y=P40_HEAD_Y, w=P40_LW, h=P40_H)
    for r, (n, col) in enumerate((('t1', ROLL), ('t2', PITCH), ('t3', YAW))):
        put(pg, n, x=P40_LX, y=P40_ROW_Y[r], w=P40_LW, h=P40_H, c={'bco': col})
    grid = (('n0', 'n1', 'n2', 'n3', 'n12', 'n15'), ('n4', 'n5', 'n6', 'n7', 'n13', 'n16'), ('n8', 'n9', 'n10', 'n11', 'n14'))
    for r, row in enumerate(grid):
        for k, n in enumerate(row): rect(pg, n, P40_X[k], P40_ROW_Y[r], P40_W, P40_H)
    by = P40_CARD[1] + P40_CARD[3] - 16 - 50          # the bottom row on the island's foot, its three slots as before
    for n, x in (('b2', 243), ('b3', 415), ('b1', 587)):
        rect(pg, n, x, by, 160, 50)
    # the message box over the five middle columns, P to Boost, its edges in the gaps beside them (the axis names and HSI
    # offset stay whole); up and down it keeps the place it had over the rows before the polish (8 px of Roll above it)
    rect(pg, 'busy', P40_X[0], P40_ROW_Y[0] + 8, P40_X[4] + P40_W - P40_X[0], 90)
    put(pg, 't11', txt='')
    words(pg, 'b2', 'PID + ...')         # (the page it opens is "PID + (advanced)", the phone app's name)
    # 15 Oct 2026, the phone app's words: "PIDs", its corner empty, "HSI gain" (it was "HSI offset": the limit is PID +'s cap)
    words(pg, 't0', 'PIDs (Rotorflight)')
    put(pg, 't4', txt='')
    words(pg, 't13', 'HSI gain')
    keypad(pg, 'n15', 'HSI offset Roll', 'Roll HSI gain'); keypad(pg, 'n16', 'HSI offset Pitch', 'Pitch HSI gain')
    ev_title(pg, 'b0', 'r', ('PID setup help', 'PID (Rotorflight) help'), 'PIDs (Rotorflight) help')


# ------------------------------------------------------------------ PID + (page 7)
P7_RIGHT = {   # sentence case (each keeps its trailing space); its keypad's question the same words
    't41': ('t13', 'Roll D-Term cutoff ', 'Roll D-term cutoff '), 't42': ('t14', 'Pitch D-Term cutoff ', 'Pitch D-term cutoff '),
    't43': ('t15', 'Yaw D-Term cutoff ', 'Yaw D-term cutoff '), 't44': ('t16', 'Roll B-Term cutoff ', 'Roll B-term cutoff '),
    't45': ('t17', 'Pitch B-Term cutoff ', 'Pitch B-term cutoff '), 't46': ('t18', 'Yaw B-Term cutoff ', 'Yaw B-term cutoff '),
    't47': ('t19', 'CW Yaw stop gain ', 'CW yaw stop gain '), 't48': ('t20', 'CCW Yaw stop gain ', 'CCW yaw stop gain '),
    't49': ('t21', 'Yaw Precomp cutoff ', 'Yaw precomp cutoff '),
}
# 15 Oct 2026 (Malcolm: "use the same terminology that we used in the phone app"): the phone's plain words, which lead with
# what each does, short enough for the label (the left labels 230 wide from x 16, the right 271 from x 400: the columns used
# only 36-246 and 451-671); its keypad's question the phone's words in full where they fit, the firmware's name in brackets.
# label: (its words, its value, the value's keypad question then: the HMI's or the polish's, the question now)
P7_PHONE = {
    't34': ('Piro compensation ', 'sw0', None, None),
    't29': ('Relax on the ground ', 't1', 'Ground error decay ', 'Relax corrections on the ground '),
    't30': ('Roll wind-up relief ', 't2', 'Cutoff point for Roll ', 'Roll wind-up relief (I-term relax) '),
    't31': ('Pitch wind-up relief ', 't3', 'Cutoff point for Pitch ', 'Pitch wind-up relief (I-term relax) '),
    't28': ('Yaw wind-up relief ', 't4', 'Cutoff point for Yaw ', 'Yaw wind-up relief (I-term relax) '),
    't35': ('Roll correction cap ', 't5', 'Error limit Roll ', 'Roll correction cap (error limit) '),
    't36': ('Pitch correction cap ', 't6', 'Error limit Pitch ', 'Pitch correction cap (error limit) '),
    't37': ('Yaw correction cap ', 't7', 'Error limit Yaw ', 'Yaw correction cap (error limit) '),
    't32': ('Roll trim cap (HSI) ', 't8', 'HSI offset limit Roll ', 'Roll high-speed trim cap (HSI) '),
    't33': ('Pitch trim cap (HSI) ', 't9', 'HSI offset limit Pitch ', 'Pitch high-speed trim cap (HSI) '),
    't38': ('Roll response speed ', 't10', 'Roll bandwidth ', 'Roll response speed (bandwidth) '),
    't39': ('Pitch response speed ', 't11', 'Pitch bandwidth ', 'Pitch response speed (bandwidth) '),
    't40': ('Yaw response speed ', 't12', 'Yaw bandwidth ', 'Yaw response speed (bandwidth) '),
    't41': ('Roll D smoothing ', 't13', 'Roll D-term cutoff ', 'Roll D smoothing (D-term cutoff) '),
    't42': ('Pitch D smoothing ', 't14', 'Pitch D-term cutoff ', 'Pitch D smoothing (D-term cutoff) '),
    't43': ('Yaw D smoothing ', 't15', 'Yaw D-term cutoff ', 'Yaw D smoothing (D-term cutoff) '),
    't44': ('Roll boost smoothing ', 't16', 'Roll B-term cutoff ', 'Roll boost smoothing (B-term cutoff) '),
    't45': ('Pitch boost smoothing ', 't17', 'Pitch B-term cutoff ', 'Pitch boost smoothing (B-term) '),
    't46': ('Yaw boost smoothing ', 't18', 'Yaw B-term cutoff ', 'Yaw boost smoothing (B-term cutoff) '),
    't47': ('Yaw stop firmness CW ', 't19', 'CW yaw stop gain ', 'Yaw stop firmness, clockwise '),
    't48': ('Yaw stop firmness CCW ', 't20', 'CCW yaw stop gain ', 'Yaw stop firmness, anticlockwise '),
    't49': ('Yaw precomp smoothing ', 't21', 'Yaw precomp cutoff ', 'Yaw pre-correction smoothing '),
    't50': ('Yaw push from cyclic ', 't22', 'Cyclic FF gain ', 'Yaw push from cyclic load '),
    't51': ('Yaw push from collective ', 't23', 'Collective FF gain ', 'Yaw push from collective load '),
    't52': ('Yaw push from speed-ups ', 't24', 'Inertia precomp gain ', 'Yaw push from rotor speed-ups '),
    't53': ('Speed-up push smoothing ', 't25', 'Inertia precomp cutoff ', 'Rotor speed-up push smoothing '),
}


# The house strip, as on every other Rotorflight page (it was 42 high, Help 160 x 38, the model's name at the card's foot), so
# going PIDs -> PID + nothing jumps: bank and model name top left, Help (620,4,170,50); the 13 rows 27 apart from y 64 (they
# were 28 apart from 54: the last one now ends at 413), Save and OK under them.
P7_LEFT_LABELS = ('t34', 't29', 't30', 't31', 't28', 't35', 't36', 't37', 't32', 't33', 't38', 't39', 't40')
P7_LEFT_VALUES = ('sw0',) + tuple('t%d' % k for k in range(1, 13))
P7_RIGHT_LABELS = tuple('t%d' % k for k in range(41, 54))
P7_RIGHT_VALUES = tuple('t%d' % k for k in range(13, 26))
P7_Y = lambda k: 64 + 27 * k


def pid_plus(pg):
    rect(pg, 't0', 0, 0, 800, 58)
    rect(pg, 'card', 0, 58, 800, 422)
    rect(pg, 'b0', 620, 4, 170, 50)
    put(pg, 't26', x=10, y=4, w=200, h=25, a={'borderw': 0})
    # the model's name where every other Rotorflight page has it, in the strip under the bank (it was 32 px bold, then at
    # the card's foot)
    put(pg, 't27', x=10, y=30, w=200, h=25, font=2, txt='', c={'pco': 65504, 'bco': 2214})
    for col in (P7_LEFT_LABELS, P7_LEFT_VALUES, P7_RIGHT_LABELS, P7_RIGHT_VALUES):
        for k, n in enumerate(col):
            put(pg, n, y=P7_Y(k))
    put(pg, 'sw0', y=P7_Y(0) + 1)        # (23 high in the 25 px row)
    rect(pg, 'b3', 408, 420, 180, 50)
    rect(pg, 'b1', 605, 420, 180, 50)
    # the message box from the left values to the right labels' end, its sides in the gaps beside them (from x 110 it cut
    # the left labels mid-word; they and the right values may not lose more of their taps than before the polish), over
    # rows 4-7 down to row 8's top edge (row 4 keeps the 2 px above it that it kept before the polish)
    rect(pg, 'busy', 250, P7_Y(4) + 2, 671 - 250, P7_Y(8) - P7_Y(4) - 2)
    # the house switch: grey off, green on (it was alarm red when merely off); the Teensy sets its knob (pco)
    put(pg, 'sw0', c={'bco': 33808, 'bco2': 2016})
    for lab, (val, old, new) in P7_RIGHT.items():
        keypad(pg, val, (old, new), P7_PHONE[lab][3])
    for lab, (txt, val, old, new) in P7_PHONE.items():
        words(pg, lab, txt)
        put(pg, lab, x=16 if lab in P7_LEFT_LABELS else 400, w=230 if lab in P7_LEFT_LABELS else 271)
        if old and lab not in P7_RIGHT: keypad(pg, val, old, new)
    words(pg, 't0', 'PID + (advanced)')   # (the phone app's name; "PID + (Rotorflight)" before)
    ev_title(pg, 'b0', 'r', ('PID advanced setup help', 'PID + (Rotorflight) help'), 'PID + (advanced) help')


# ------------------------------------------------------------------ Governor (page 6)
P6_LEFT = ('t34', 't29', 't30', 't31', 't28', 't35', 't36')
P6_RIGHT = ('t37', 't32', 't33', 't38', 't39', 't40', 't41')
P6_WORDS = {   # label: (its words, its value, the keypad's old questions: the HMI's, the 10 Oct polish's; then the question now)
    # (15 Oct 2026: the phone app's words, in its round brackets; the keypads in the phone's words in full where they fit)
    't34': ('Headspeed (rpm)', 'n0', ('Headspeed (rpm)', 'Head speed [rpm]'), 'Headspeed (rpm)'),
    't35': ('F gain (feed-forward)', 'n5', ('F gain',), 'F gain (feed-forward)'),
    't36': ('Tail-torque strength', 'n6', ('TTA gain',), 'Tail-torque assist strength (TTA gain)'),
    't37': ('Tail-torque limit (%)', 'n7', ('TTA limit %', 'TTA limit [%]'), 'Tail-torque assist limit (%)'),
    't32': ('Max throttle (%)', 'n8', ('Max throttle %', 'Max throttle [%]'), 'Max throttle (%)'),
    't33': ('Min throttle (%)', 'n9', ('Min throttle %', 'Min throttle [%]'), 'Min throttle (%)'),
    't38': ('Fall-back drop (%)', 'n10', ('Fallback drop %', 'Fallback drop [%]'), 'Throttle drop if RPM signal lost (%)'),
    't39': ('Anticipate yaw', 'n11', ('Yaw weight',), 'Anticipate yaw moves (yaw weight)'),
    't40': ('Anticipate cyclic', 'n12', ('Cyclic weight',), 'Anticipate cyclic moves'),
    't41': ('Anticipate collective', 'n13', ('Collective weight',), 'Anticipate collective moves'),
}


# Rows 36 high, 40 apart (they were 32 at 38: squeezed beside Rescue and Rates), Rescue's vertical grid exactly; the island
# 16 px taller.
P6_Y = lambda r: 99 + 40 * r
P6_H = 36


def governor(pg):
    rect(pg, 'card', 87, 83, 626, 372)
    for n in P6_LEFT + P6_RIGHT:
        x, w = (103, 218) if n in P6_LEFT else (415, 200)   # (each 6 px before its value, as on the newer Rotorflight pages)
        r = (P6_LEFT + P6_RIGHT).index(n) % 7
        label_box(pg, n, PALE_YELLOW, x=x, y=P6_Y(r), w=w, h=P6_H)
    for k in range(14):
        put(pg, 'n%d' % k, y=P6_Y(k % 7), h=P6_H)
    for n in ('b2', 'b3', 'b1'):
        put(pg, n, y=P6_Y(7) + 10)
    # the message box over rows 3-5, edge to edge between them; from x 126 to 690, because the left labels and right values
    # under it may not lose more of their taps than before the polish (it still hides every word of those rows)
    rect(pg, 'busy', 126, P6_Y(3), 690 - 126, P6_Y(5) + P6_H - P6_Y(3))
    put(pg, 't27', txt='')
    for n, (txt, val, old, q) in P6_WORDS.items():
        words(pg, n, txt)
        keypad(pg, val, old, q)
    put(pg, 't0', txt='')    # (FixHeading writes the title, with the bank's number, as soon as the page opens)
    ev_title(pg, 'b0', 'r', 'RF Governor profile help', 'Governor (Rotorflight) help')


# ------------------------------------------------------------------ Governor (global) (page 5)
# The newer Rotorflight look: three columns under white heads, each a shade - General yellow, Throttle blue, the times green
# under "Times [s]" (the receiver hands the transmitter WHOLE SECONDS since 0.9.581: RXV2 TxParams.h govAckSecs) - and the
# two copy buttons the house's grey in the bottom row, "Restore" and "Keep a copy" ("Restore SD to FC" was salmon and
# "Save FC to SD" green, the size of a row, and looked like part of the columns; "Save FC to SD" sat beside Save).
G5_X = (44, 285, 526); G5_CW, G5_VW, G5_RH = 230, 58, 40   # (15 Oct 2026: values 58 wide, 64 before: "Auto throttle x10" needs the room)
G5_LW = G5_CW - G5_VW - 6
G5_Y = (148, 194, 240, 286, 332)
G5_ROWS = {   # label: (column, row, shade, words or None, its value)
    # (15 Oct 2026: the phone app's words - Handover, Autorot., Idle and Auto throttle, Speed change, Quick restart)
    't42': (0, 1, PALE_YELLOW, 'Governor mode', 'n14'), 't43': (0, 2, PALE_YELLOW, 'Handover (%)', 'n15'),
    't50': (0, 3, PALE_YELLOW, 'Autorot. timeout', 'n22'),
    't69': (1, 1, PALE_BLUE, None, 'n28'), 't70': (1, 2, PALE_BLUE, 'Idle throttle x10', 'n29'), 't71': (1, 3, PALE_BLUE, 'Auto throttle x10', 'n30'),
    't45': (2, 0, PALE_GREEN, 'Spool-up', 'n17'), 't46': (2, 1, PALE_GREEN, 'Spool-down', 'n18'),
    't47': (2, 2, PALE_GREEN, 'Speed change', 'n19'), 't48': (2, 3, PALE_GREEN, 'Quick restart', 'n20'),
    't49': (2, 4, PALE_GREEN, 'Hold timeout', 'n21'),
}
G5_KEYS = {   # the keypad's question: the label's words with the unit (a lost multiplication sign showed as garbage in most)
    'n17': (('Spoolup \ufffd0.1%/s', 'Spool-up [s]'), 'Spool-up time (s)'), 'n18': (('Spooldown \ufffd.1% s', 'Spool-down [s]'), 'Spool-down time (s)'),
    'n19': (('Tracking \ufffd0.1%/s', 'Tracking [s]'), 'Speed-change time (s)'), 'n20': (('Recovery \ufffd0.1%/s', 'Recovery [s]'), 'Quick-restart time (s)'),
    'n21': (('Hold timeout \ufffd0.1s', 'Hold timeout [s]'), 'Throttle-hold timeout (s)'), 'n22': (('Autorot timeout s', 'Autorot timeout [s]'), 'Autorotation timeout (s)'),
    'n15': (('Handover thr %', 'Handover [%]'), 'Handover throttle (%)'),
    'n14': ('Gov mode (0 - 3)', 'Governor mode (0 - 4)'),   # (15 Oct 2026: Rotorflight 2.3 has five modes, 4 - NITRO)
    'n29': (('Idle thr \ufffd0.1%', 'Idle thr x0.1%'), 'Idle throttle (tenths of a %)'), 'n30': (('Auto thr \ufffd0.1%', 'Auto thr x0.1%'), 'Auto throttle (tenths of a %)'),
    'n16': ('Startup \ufffd0.1s', 'Startup x0.1s'), 'n25': ('D filter \ufffd0.1Hz', 'D filter x0.1Hz'),   # (parked off the glass: only the sign mended - ASCII)
}


def governor_global(pg):
    for k, (n, txt) in enumerate((('t3', None), ('t2', None), ('t1', 'Timings (s)'))):   # (the phone app's "Timings (seconds)"; "Times [s]" before)
        head(pg, n, x=G5_X[k], y=102, w=G5_CW, h=40, font=6, a={'xcen': 0, 'style': 0})
        if txt: words(pg, n, txt)
    for k, n in enumerate(('GovMode', 'ThrMode')):   # (the Teensy writes the mode's meaning; a tap opens the mode's keypad)
        put(pg, n, x=G5_X[k], y=G5_Y[0], w=G5_CW, h=G5_RH, c={'bco': (PALE_YELLOW, PALE_BLUE)[k], 'pco': BLACK}, a={'style': 0})
    for lab, (col, row, shade, txt, val) in G5_ROWS.items():
        if txt: words(pg, lab, txt)
        label_box(pg, lab, shade, x=G5_X[col], y=G5_Y[row], w=G5_LW, h=G5_RH)
        rect(pg, val, G5_X[col] + G5_CW - G5_VW, G5_Y[row], G5_VW, G5_RH)
    for n, (old, new) in G5_KEYS.items(): keypad(pg, n, old, new)
    for n, x, txt in (('b4', 80, 'Restore'), ('b2', 252, 'Keep a copy'), ('b3', 424, None), ('b1', 596, None)):
        put(pg, n, x=x, y=386, w=160, h=50, font=6, c={'bco': BTN_GREY, 'pco': BLACK})
        if txt: words(pg, n, txt)
    # the model's name alone in the strip: in its middle, as far as 20 px before the title
    put(pg, 't27', x=10, y=16, w=248, h=26, txt='')
    for n in ('GovMode', 'ThrMode'): put(pg, n, txt='')   # (the Teensy writes the mode's words; it never writes "Unknown")
    # the message box over the Throttle and Times columns' rows 2-3, edge to edge between the rows, its sides in the gaps
    # beside them: everything under it was under it before the polish too (at x 109 it cut "Governor mode", "Handover"
    # and "Autorot timeout" mid-word, and took the taps of Handover's value, which the polish had moved under it)
    rect(pg, 't4', G5_X[1] - 5, G5_Y[1] + G5_RH + 1, G5_X[2] + G5_CW - G5_VW - (G5_X[1] - 5), G5_Y[4] - G5_Y[1] - G5_RH - 2)
    ev_title(pg, 'b0', 'r', 'RF Governor (global) help', 'Governor (global) help')


EDITS = {1: rates, 42: rates_plus, 40: pids, 7: pid_plus, 6: governor, 5: governor_global}
