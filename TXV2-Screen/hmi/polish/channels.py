"""POLISH, the channel pages (10 Oct 2026): Model setup (4), Model options (9), Inputs (39), Reverse (37), Subtrim (32),
Trims (28), Set trim directions (49), Failsafe (36), PWM servo types (34), Servo speed (35).
Places, sizes, colours, static words, help titles and keypad questions only (hmi/logic_guard.py). The review behind it:
the channels group's proposals 0-3, 7-9, 12-16 (proposal 9: the page's own words; the Teensy's "... trim: done" is the
Teensy-text change). Every function sets ABSOLUTE values, so it can run again and again (polish_pages.py --check)."""
from . import comp, put, rect, add_text, ev_title

STRIP, PANEL, WHITE, SOFT, YELLOW = 2214, 4426, 65535, 50712, 65504


# ------------------------------------------------------------------ shared by the pages
def name_alone(pg, w):
    """The model's name alone in the title strip: top left, centred in the strip's height, stopping at least 20 px before
    the title (as on Model setup). No page text of its own: the Teensy writes it as the page opens."""
    put(pg, 'ModelName', x=10, y=16, w=w, h=26, font=2, sta=1, txt='', c={'bco': STRIP, 'pco': YELLOW}, a={'xcen': 0, 'ycen': 1})

def name_and_bank(pg, bank, w):
    """The bank (white) over the model's name (yellow), both at the left of the strip, as wide as the title allows."""
    put(pg, bank, x=10, y=4, w=w, h=25, txt='')
    put(pg, 'ModelName', x=10, y=30, w=w, h=25, txt='')

def help_title(pg, button, old, new):
    ev_title(pg, button, 'r', old, new)

def questions(pg, names, key, fn):
    """Keypad questions (keybdA/B.t1): fn(old words) -> new words, for each named box."""
    for n in names:
        s = comp(pg, n)['ev'][key]
        for target in ('keybdA.t1.txt="', 'keybdB.t1.txt="'):
            if target in s:
                old = s.split(target, 1)[1].split('"', 1)[0]
                new = fn(old)
                if new != old: ev_title(pg, n, key, old, new)

def no_default_names(pg, names):
    """Channel names: the Teensy writes them as the page opens. Its page text was '(Aileron)', '(AUX4)' ... - names a
    renamed channel no longer has; empty is what a screen-only restart should show (design rule: page texts are empty or
    exactly what the Teensy writes)."""
    for n in names: put(pg, n, txt='')

CH16 = ['ch%d' % i for i in range(1, 17)]


# ------------------------------------------------------------------ 4 Model setup
GRID = [['b12', 'b1', 'b4', 'b15', 'b0', 'b11'],      # Models, Channels, Trims, Rates, Bank names, Model IDs
        ['b6', 'b3', 'b16', 'b13', 'b5', 'b7'],       # Options, Failsafe, Inputs, Subtrim, Servo speed, Rotorflight
        ['b10', 'b19', 'b8', 'b18', 'b14', 'b9']]     # Batteries, Log, Telemetry, Macros, Reverse, Mixes
GRID_COLS = [(62, 217), (291, 218), (521, 217)]       # (the grid's outer edges on the bottom row's: 62 .. 738, 12 px apart)

def model_setup(pg):
    for (x, w), col in zip(GRID_COLS, GRID):
        for r, n in enumerate(col): rect(pg, n, x, 99 + 47 * r, w, 40)
    put(pg, 'b7', txt='Rotorflight'); put(pg, 'b5', txt='Servo speed'); put(pg, 'b0', txt='Bank names')   # (the titles of the pages they open)
    # The bottom row on the grid's columns, as on Transmitter setup ('Workshop door' over two columns, OK in the last):
    # 'Receiver updates' over columns 1 + 2 (it was 332 wide: it stopped halfway under 'Rotorflight' and is not made
    # smaller), OK fills column 3.
    rect(pg, 'ldrcRxUpdate', GRID_COLS[0][0], 388, GRID_COLS[1][0] + GRID_COLS[1][1] - GRID_COLS[0][0], 50)
    rect(pg, 'b2', GRID_COLS[2][0], 388, GRID_COLS[2][1], 50)
    name_alone(pg, 285)                                # (ends at 295, 20 px before 'Model setup' at 315: a 280 px name shows whole)
    help_title(pg, 'b17', 'RX setup help', 'Model setup help')


# ------------------------------------------------------------------ 9 Model options
# Grouped by topic (trims, motor, timer, warnings): the timer switch now sits right over the minutes box it greys.
OPTION_GROUPS = [
    [('t8', 'n3', 'Trim multiplier (0 = off)'), ('l_t3', 'c1', 'Copy trims to all banks')],
    [('t6', 'n1', 'Throttle channel'), ('t5', 'n0', 'Motor off value (usually -67)'), ('l_t4', 'c0', 'Use motor kill switch')],
    [('l_t2', 'c2', 'Timer counts down'), ('t9', 'n4', 'Count down from (minutes)')],
    [('t7', 't10', 'Stop flying volts (per cell)'), ('t1', 'n2', 'Volts correction (0.01 V/cell)'), ('t11', 't12', 'Current warning (A, 0 = off)')]]
OPTION_QUESTIONS = {'Motor Channel': 'Throttle channel', 'Backwards timer': 'Count down from (minutes)',
                    'Backwards timer time': 'Count down from (minutes)', 'Stop flying volts': 'Stop flying volts (per cell)',
                    'RX lipo volts correction': 'Volts correction (0.01 V/cell)', 'Stop flying amps': 'Current warning (A, 0 = off)',
                    'Volts correction (x 0.01 V)': 'Volts correction (0.01 V/cell)'}   # (the first polish's words: per cell, as the Teensy uses it)

def model_options(pg):
    y = 72
    for g, group in enumerate(OPTION_GROUPS):
        if g: y += 6                                   # (a little more space between the groups)
        for label, box, words in group:
            put(pg, label, x=26, y=y, w=296, h=28, txt=words)
            if comp(pg, box)['t'] == 'switch': rect(pg, box, 332, y, 80, 28)
            else: rect(pg, box, 330, y, 84, 28)
            y += 31
    # The model's name in the strip, as on every model page; the picture and its button at the top of the right column.
    name_alone(pg, 271)
    rect(pg, 'exp0', 452, 72, 320, 200)
    put(pg, 'b3', x=452, y=284, w=320, h=48, txt='Model picture ...')
    put(pg, 'b0', txt='Servo types ...')
    questions(pg, ['n0', 'n1', 'n2', 'n3', 'n4', 't9', 't10', 't12'], 'p', lambda s: OPTION_QUESTIONS.get(s, s))
    help_title(pg, 'b17', 'RX setup help', 'Model options help')


# ------------------------------------------------------------------ 39 Inputs
IN_LABELS = ['t3', 't1', 't2', 't4', 't5', 't6', 't7', 't8', 't17', 't18', 't19', 't20', 't12', 't11', 't10', 't9']

IN_X0 = (26, 353)          # the two blocks: 311 px each, 16 px apart; the trims stay at 676 (12 px after the right block)

def inputs(pg):
    """Two blocks of eight channels, 16 px apart (they read as two tables, not one 640 px row), 12 px before the trims.
    'Ch n' as on every channel page ('Ch 16' is 67 px: its words end 8 px before its box). The names are 154 wide so real
    10-letter names show whole ('Smoke pump' 149 px, 'Camera pan' 139 px were cut with dots at 134); the In and Out boxes
    hold two figures (28 px) in 38."""
    for i in range(16):
        col, r = divmod(i, 8); x0 = IN_X0[col]; y = 100 + 37 * r
        put(pg, IN_LABELS[i], x=x0, y=y, w=75, h=33, txt='Ch %d' % (i + 1))
        rect(pg, 'c%d' % (i + 1), x0 + 77, y, 38, 33)
        rect(pg, 'ch%d' % (i + 1), x0 + 117, y, 154, 33)
        rect(pg, 'n%d' % (i + 4), x0 + 273, y, 38, 33)
    for k, x0 in enumerate(IN_X0):
        rect(pg, 'hIn%d' % k, x0 + 77, 74, 38, 24); rect(pg, 'hName%d' % k, x0 + 117, 74, 154, 24); rect(pg, 'hOut%d' % k, x0 + 273, 74, 38, 24)
    name_alone(pg, 320)
    no_default_names(pg, CH16)
    questions(pg, CH16, 'r', lambda s: s.replace('Name for Channel', 'Name for channel'))


# ------------------------------------------------------------------ 37 Reverse, 36 Failsafe: tick boxes
TICK_LABELS = ['t3', 't1', 't2', 't4', 't5', 't6', 't7', 't8', 't17', 't18', 't19', 't20', 't10', 't11', 't12', 't13']

def tick_rows(pg, pitch, h, y0):
    """'Ch n', its tick box, its name 14 px after the box (the right column's names end at 770, not 782)."""
    for i in range(16):
        col, r = divmod(i, 8); x0 = (26, 410)[col]; y = y0 + r * pitch
        rect(pg, TICK_LABELS[i], x0, y, 72, h)
        rect(pg, 'fs%d' % (i + 1), x0 + 82, y + (h - 34) // 2, 34, 34)
        rect(pg, 'ch%d' % (i + 1), x0 + 130, y, 230, h)

def reverse(pg):
    tick_rows(pg, 41, 36, 74)
    for i in range(16): put(pg, 'fs%d' % (i + 1), c={'pco': 0})   # (the tick black, as on Failsafe: red was the warning colour)
    name_alone(pg, 310)
    no_default_names(pg, CH16)

def failsafe(pg):
    """Rows a little closer, to make room for the one thing the page must say: Save records where the controls ARE."""
    tick_rows(pg, 37, 34, 70)
    add_text(pg, 'doline', after='ch16', x=26, y=368, w=748, h=32, font=6, txt='Hold the sticks where the model should go, then press Save.',
             c={'bco': PANEL, 'pco': WHITE, 'borderc': 0}, a={'xcen': 1, 'ycen': 1, 'txt_maxl': 80},
             ev={'r': pg['ev']['touch_release']})        # (it lies on the card, whose touch keeps the screen awake: so does it)
    name_alone(pg, 310)
    no_default_names(pg, CH16)


# ------------------------------------------------------------------ 32 Subtrim, 35 Servo speed: number rows
def subtrim(pg):
    for i in range(16): put(pg, 'ch%d' % (i + 1), w=198)          # (the right column's names end at 770, not 782)
    rect(pg, 'h0', 26, 358, 740, 40)                                # (the knob 15 px under the rows, 16 px over the buttons)
    name_alone(pg, 310)
    no_default_names(pg, CH16)

def servo_speed(pg):
    for i in range(16): put(pg, 'ch%d' % (i + 1), w=198)
    put(pg, 't9', txt='Speed in this bank: 1 (slow) to 100')       # (each bank has its own speeds: ServoSpeed[Bank - 1])
    name_and_bank(pg, 't14', 284)                                   # (ends at 294, 20 px before 'Servo speed' at 314)
    no_default_names(pg, CH16)
    help_title(pg, 'b17', 'Slowed Servos help', 'Servo speed help')


# ------------------------------------------------------------------ 34 PWM servo types
TYPE_NAMES = ['ch%d' % i for i in range(1, 9)] + ['t13', 't14', 't16']
HZ = ['n%d' % i for i in range(8)] + ['n16', 'n18', 'n20']
US = ['n%d' % i for i in range(8, 16)] + ['n17', 'n19', 'n21']

def servo_types(pg):
    put(pg, 't9', txt='Rate (Hz)')                                  # (pairs with 'Centre (us)')
    add_text(pg, 'legend', after='b0', x=211, y=414, w=377, h=56, font=2, txt='Pairs marked * or ** share one rate',
             c={'bco': PANEL, 'pco': SOFT, 'borderc': 0}, a={'xcen': 1, 'ycen': 1, 'txt_maxl': 80})
    name_alone(pg, 250)
    no_default_names(pg, TYPE_NAMES)
    questions(pg, HZ + US, 'p', lambda s: s.replace('Hz for channel  ', 'Rate (Hz) for channel ').replace('us for channel  ', 'Centre (us) for channel '))
    help_title(pg, 'b17', 'Servos type help', 'PWM servo types help')


# ------------------------------------------------------------------ 28 Trims: an island, laid out as the trims are on the transmitter
def trims(pg):
    """The card centred on the picture with its buttons inside (it was framed, 9 px off centre, the buttons outside it).
    Symmetric about x = 400; the horizontal trims beside the vertical ones, as on the transmitter's face."""
    put(pg, 'card', x=46, y=79, w=708, h=379, a={'style': 0, 'borderw': 0})
    rect(pg, 'c2', 274, 95, 124, 35); rect(pg, 'c3', 402, 95, 124, 35)                  # Elevator, Throttle (Mode 2 words)
    for n, y in (('b1', 134), ('n4', 181), ('b5', 228)): rect(pg, n, 294, y, 45, 45)    # elevator + / value / -
    rect(pg, 'ch4', 343, 134, 35, 140)
    rect(pg, 'ch2', 422, 134, 35, 140)
    for n, y in (('b0', 134), ('n2', 181), ('b7', 228)): rect(pg, n, 461, y, 45, 45)    # throttle + / value / -
    rect(pg, 'ch3', 124, 260, 140, 35); rect(pg, 'c4', 124, 343, 140, 35)               # rudder
    for n, x in (('b6', 124), ('n3', 171), ('b3', 218)): rect(pg, n, x, 296, 45, 45)
    rect(pg, 'ch1', 536, 260, 140, 35); rect(pg, 'c1', 536, 343, 140, 35)               # aileron
    for n, x in (('b4', 537), ('n1', 584), ('b2', 631)): rect(pg, n, x, 296, 45, 45)
    rect(pg, 'b8', 62, 392, 160, 50); rect(pg, 'b9', 234, 392, 332, 50); rect(pg, 'b10', 578, 392, 160, 50)   # Reset, Move to subtrim, OK
    name_and_bank(pg, 't1', 320)
    no_default_names(pg, ['c1', 'c2', 'c3', 'c4'])   # (StartTrimView -> ForceDataRedisplay: UpdateTrimView writes all four names)
    help_title(pg, 'b17', 'Trim help', 'Trims help')


# ------------------------------------------------------------------ 49 Set trim directions: a checklist, the trim first
def trim_directions(pg):
    put(pg, 'ail', txt='Aileron trim: push RIGHT'); put(pg, 'ele', txt='Elevator trim: push DOWN')
    put(pg, 'thr', txt='Throttle trim: push DOWN'); put(pg, 'rud', txt='Rudder trim: push RIGHT')


EDITS = {4: model_setup, 9: model_options, 39: inputs, 37: reverse, 36: failsafe, 32: subtrim, 35: servo_speed, 34: servo_types,
         28: trims, 49: trim_directions}
