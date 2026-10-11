"""Polish of the Transmitter setup pages (10 Oct 2026; Malcolm: "make the screens look more beautiful, well designed and easy to
use ... Don't change the logic anywhere"): 33 Transmitter setup, 25 / 24 / 23 System (General, Clock, Advanced), 22 Calibration,
55 Sounds and brightness, 51 Batteries, 17 Background picture, 16 Wireless buddy, 18 Buddy channels, 45 Raining (Pong).

Only places, sizes, fonts, colours, fixed words and new plain labels (hmi/logic_guard.py checks it). Every value is set
absolutely, so this can run after islands.py and the restyle scripts any number of times. The words the main board writes
(Calibration's t11 and b0, Bind's b0, the date) have boxes sized for today's words AND the reworded ones of the Teensy text pass.

- 22 Calibration was the last page here in Version 1 dress: the title strip, a centred island, the instructions box above the
  button they talk about, Calibrate trims ... under it and Reset transmitter at the bottom left (far from OK); the eight bars
  labelled Ch 1 .. Ch 8 and growing from the middle (as on the front page), so "centre all channels" is easy to judge.
- 23 Advanced on page 1's columns (labels 41, values 484 in page 1's font, units 614); the three log settings together at
  the top; "Hold power button for" (it was "Switch-off countdown"). All nine rows stay.
- 24 Clock: the five +/- columns fill the island evenly, the widest date shows whole, the time-zone row's box and Reset clock
  over Next and OK.
- 25 General: "Transmitter battery low at" (it only watches the transmitter's battery). The three System pages share one
  label column (41, 16 px inside the island) and the multi-page words of the Rotorflight sets: "< Previous", "Next >".
- 55 Sounds: a real gutter between the switches and the vario column; the vario's units in their own grey column;
  "Screen brightness" (not the LED's).
- 16 Buddy: which transmitter is which ("Pupil (Buddy)", "Instructor (Master)"), "Buddy switch", and Buddy channels ... on
  the bottom row beside OK.
- 17 Background picture (the name of Appearance's button): a frameless island with OK inside it; - left of +, as everywhere.
- 18 Buddy channels: the channel names empty until the main board writes the model's own (no made-up "(Aileron)").
- 33 Transmitter setup: the bottom row on the grid's columns (Workshop door under Raining + WiFi, OK under Buddy).
- 45 Pong: Help and OK as on every page, OK clear of the court (the screen's court layer ends at y 423).
- 51 Batteries: the headings white (yellow is for the model's name and warnings), the choices in the labels' font under them.
- Help titles "<page> help" (System's three pages share one help: "System help", after the button that opens them); keypad
  questions name the setting as its label does, with its unit; the model's name 20 px clear of the title."""
from polish import comp, put, rect, add_text, ev_title
from fontw import width

NAVY, STRIP, WHITE, SOFT = 4426, 2214, 65535, 50712
CARRY_ON = {'r': 'print "UKRULES"'}          # a page's own "someone is here" touch: what a tap on the bare page did there


def retitle(pg, name, key, olds, new):
    """ev_title from whichever earlier words the page has (the generators' own, or an earlier polish's)."""
    for old in olds:
        try:
            ev_title(pg, name, key, old, new); return
        except KeyError:
            pass
    raise KeyError(f"{pg['name']}.{name}: none of {olds!r} in its {key} event")


def label_w(font, text):
    return width(font, text) + 14


def words(pg, name, text, **kw):
    """New words for a fixed label (its txt_maxl raised to hold them, never lowered), and its place."""
    c = comp(pg, name)
    put(pg, name, txt=text, a={'txt_maxl': max(c.get('a', {}).get('txt_maxl', 0), len(text) + 2)}, **kw)


def model_name_clear(pg, title='t0'):
    """The model's name top left in the strip (font 2, y 16 h 26), ending 20 px before the centred title's words."""
    t = comp(pg, title); left = t['x'] + (t['w'] - width(t['font'], t['txt'])) // 2
    put(pg, 'ModelName', x=10, y=16, w=min(270, left - 20 - 10), h=26, font=2)


# ------------------------------------------------------------------ 33 Transmitter setup
def tx_setup(pg):
    model_name_clear(pg)
    # the menu is 4 columns x 46/226/406/586, 168 wide: the bottom row takes them (column 3 stays empty, so the bench
    # tool is not beside OK)
    rect(pg, 'ldrcDoor', 46, 354, 348, 50)
    rect(pg, 'b2', 586, 354, 168, 50)
    ev_title(pg, 'b17', 'r', 'TX setup help', 'Transmitter setup help')


# ------------------------------------------------------------------ 25 / 24 / 23 System (one island: card 25,74,750,390)
PAGING = {'b0': '< Previous', 'b13': 'Next >'}   # (the words every multi-page set uses: Rescue, Mixer, Filters)


def paging(pg, *names):
    for n in names: words(pg, n, PAGING[n])


def general(pg):
    words(pg, 't10', 'Transmitter battery low at', x=41, y=234, w=label_w(6, 'Transmitter battery low at'), h=44)
    for n in ('t5', 'ST', 't2', 't4', 't6'): put(pg, n, x=41)     # (labels 16 px inside the island, as on Clock: paging
                                                                  #  Next / Back no longer moves the label column)
    put(pg, 'TxName', x=324, w=435)                              # (its right edge on OK's; the same size, so it takes no more
                                                                 #  of the card's own "someone is here" touch)
    paging(pg, 'b13')
    ev_title(pg, 'b12', 'r', 'Options help', 'System help')
    # keypad questions: the setting as its label names it, with its unit
    retitle(pg, 'Sto', 'p', ('Screen timeout', 'Screen timeout (seconds)'), 'Screen goes dark after (seconds)')
    retitle(pg, 'Pto', 'p', ('Inactivity timeout', 'Inactivity timeout (minutes)'), 'Switch off when unused for (minutes)')
    retitle(pg, 'Bwn', 'p', ('Low battery warning', 'Transmitter battery low (%)'), 'Transmitter battery low at (%)')
    ev_title(pg, 'n0', 'p', 'Transmitter mode', 'Stick mode (1 or 2)')


CLOCK_X = [41 + 146 * k for k in range(5)]     # the island's inner width (41 .. 759) in five columns of 134, 12 apart
def clock(pg):
    for k, (plus, minus, lab) in enumerate((('b9', 'b11', 'lb0'), ('b7', 'b8', 'lb1'), ('b6', 'b5', 'lb2'), ('b4', 'b3', 'lb3'), ('b1', 'b2', 'lb4'))):
        x = CLOCK_X[k]
        rect(pg, plus, x, 164, 134, 54)
        rect(pg, minus, x, 266, 134, 54)
        put(pg, lab, x=x, y=220, w=134, h=44, a={'xcen': 1})      # (centred over its column)
    put(pg, 'DateTime', x=41, y=90, w=718, h=64, txt='')         # (the widest date ReadTime builds is 620 px in font 1, 610 with
                                                                 #  ShortMonth's trailing space gone; no made-up
                                                                 #  date while the first second's comes)
    rect(pg, 't8', 41, 330, 341, 44)
    rect(pg, 'dGMT', 467, 330, 120, 44)                          # (its right edge on Next's)
    rect(pg, 'b12', 599, 330, 160, 44)                           # (OK's x and width: 14 px clear each side of its words)
    paging(pg, 'b0', 'b13')


# Advanced: nine rows on page 1's columns, the three log settings first. 90 .. 384 (the buttons are at 398): rows 30 high,
# 32 apart, and 10 between the log settings and the rest.
ADVANCED = [('t5', 'sw0', None, None), ('t11', 'sw1', None, None), ('t10', 'n0', 'u_gap', None),
            ('t6', 'n1', 'u_led', None), ('t1', 't2', 'u_volt', '0.01 V/cell'), ('t8', 'n2', 'u_warn', None),
            ('t9', 'n3', 'u_conn', None), ('t4', 'n4', 'u_scan', None), ('t7', 'Qnh', 'u_qnh', None)]
def advanced(pg):
    words(pg, 't8', 'Hold power button for')
    for k, (lab, val, unit, new) in enumerate(ADVANCED):
        y = 90 + 32 * k + (10 if k >= 3 else 0)
        put(pg, lab, x=41, y=y, w=label_w(6, comp(pg, lab)['txt']), h=30)   # (16 px inside the island, as on pages 1 and 2)
        if comp(pg, val)['t'] == 'switch':
            rect(pg, val, 494, y + 2, 100, 26)                   # (page 1's switch column)
        else:
            put(pg, val, x=484, y=y, w=120, h=30, font=6)        # (page 1's value boxes and font)
        if unit:
            if new: words(pg, unit, new)
            put(pg, unit, x=614, y=y, w=label_w(6, comp(pg, unit)['txt']), h=30)
    words(pg, 'b13', '< Previous')                               # (here b13 goes back: PAGING's b0 words)
    retitle(pg, 't2', 'p', ('TX Lipo correction', 'Correction (0.01 V per cell)'), 'Battery correction (0.01 V per cell)')
    ev_title(pg, 'n1', 'p', 'LED brightness', 'LED brightness (15 - 254)')
    retitle(pg, 'n2', 'p', ('Power off warning time', 'Hold power button (seconds)'), 'Hold power button for (seconds)')
    ev_title(pg, 'Qnh', 'p', 'QNH', 'Sea-level pressure (hPa)')
    retitle(pg, 'n4', 'p', ('Scanner sensitivity', 'Scanner sensitivity (1 - 255)'), 'Radio scanner sensitivity (1 - 255)')
    ev_title(pg, 'n0', 'p', 'Minimum logged gap', 'Log gaps longer than (ms)')


# ------------------------------------------------------------------ 22 Calibration
def calibration(pg):
    put(pg, 't0', x=0, y=0, w=800, h=58, sta=1, font=0, c={'bco': STRIP, 'pco': WHITE}, a={'style': 0, 'borderw': 0, 'xcen': 1, 'ycen': 1})
    add_text(pg, 'card', after='t0', x=32, y=109, w=736, h=320, font=6, txt='', ev=dict(CARRY_ON),
             c={'bco': NAVY, 'pco': WHITE, 'borderc': WHITE}, a={'xcen': 0, 'txt_maxl': 1})
    rect(pg, 'b17', 620, 4, 170, 50)
    # left: what to do (the main board writes it at every step), the button it talks about, then the other two jobs;
    # Reset transmitter at the bottom left, as far from OK as the island allows
    words(pg, 't11', "Press 'Calibrate sticks etc.',\r\nthen follow the steps here.", x=48, y=125, w=360, h=96)
    rect(pg, 'b0', 48, 233, 360, 50)
    words(pg, 'b1', 'Calibrate trims ...', x=48, y=295, w=360, h=50)      # (it opens the trims' own page)
    rect(pg, 'b3', 48, 363, 360, 50)
    rect(pg, 'b2', 592, 363, 160, 50)
    # right: the eight channels, labelled, from the middle out
    for k in range(8):
        y = 125 + 28 * k                                         # (125 .. 345: level with the box and Calibrate trims)
        put(pg, f'Ch{k + 1}', x=496, y=y, w=256, h=24, centre=True)
        add_text(pg, f'lch{k + 1}', after=f'Ch{k + 1}', x=436, y=y, w=56, h=24, font=2, txt=f'Ch {k + 1}', ev=dict(CARRY_ON),
                 c={'bco': NAVY, 'pco': WHITE}, a={'xcen': 0, 'txt_maxl': 6})
    rect(pg, 'Progress', 48, 351, 704, 8)                        # (Reset transmitter's progress, across the island)


# ------------------------------------------------------------------ 55 Sounds and brightness (island 46,84,708,370)
def sounds(pg):
    # the two sliders on a 40 px pitch right under the switches' 38 (their knobs are 40 across, so 38 would make them
    # touch; their touch areas stay 40 high): no wider gap above Volume
    words(pg, 't1', 'Screen brightness', x=62, y=288, w=label_w(2, 'Screen brightness'), h=40)
    put(pg, 'h0', x=254, y=288, w=484, h=40)
    put(pg, 't2', y=328, h=40)
    put(pg, 'Ex1', x=254, y=328, w=484, h=40)
    # the vario column 36 px clear of the switches (they end at 394); values and units in columns
    rows = (('t5', 'c2', 'Vario tones', None), ('t11', 'n2', 'Vario in bank', '0 = all'),
            ('t9', 'n0', 'First tone at', 'ft/min'), ('t12', 'n3', 'Next tone every', 'ft/min'))
    for k, (lab, val, text, unit) in enumerate(rows):
        y = 100 + 38 * k
        words(pg, lab, text, x=430, y=y, w=label_w(2, text), h=34)
        if comp(pg, val)['t'] == 'switch':
            rect(pg, val, 600, y, 84, 34)
        else:
            rect(pg, val, 600, y, 66, 34)                        # ("1000", the most the Teensy sends, is 48 px)
            add_text(pg, f'u_{val}', after=val, x=672, y=y, w=66, h=34, font=2, txt=unit, ev=dict(CARRY_ON),
                     c={'bco': NAVY, 'pco': SOFT}, a={'xcen': 0, 'txt_maxl': len(unit) + 2})
    ev_title(pg, 'b0', 'r', 'Audio help', 'Sounds and brightness help')
    ev_title(pg, 'n2', 'p', 'Variometer bank', 'Vario in bank (0 = all)')
    ev_title(pg, 'n0', 'p', 'Variometer threshold', 'First tone at (ft/min)')
    ev_title(pg, 'n3', 'p', 'Variometer spacing', 'Next tone every (ft/min)')


# ------------------------------------------------------------------ 51 Batteries
def batteries(pg):
    model_name_clear(pg)
    for n in ('t2', 't3'): put(pg, n, c={'pco': WHITE})          # (headings white: yellow is the model's name and warnings)
    for n in ('t6', 't7', 't8', 't9', 't10', 't1', 't4', 't5'):     # (the choices in the labels' font, under the bold headings)
        put(pg, n, font=6, w=label_w(6, comp(pg, n)['txt']))
    ev_title(pg, 'b15', 'r', 'Type help', 'Batteries help')


# ------------------------------------------------------------------ 17 Background picture (no strip: the island centred on the glass)
def background(pg):
    put(pg, 'card', x=110, y=157, w=580, h=166, a={'style': 0, 'borderw': 0})
    words(pg, 't1', 'Background picture', x=126, y=173, w=290, h=70)    # (the name of Appearance's button; 275 px)
    rect(pg, 'b1', 460, 173, 64, 70)      # -
    rect(pg, 'b0', 534, 173, 64, 70)      # +
    rect(pg, 'n0', 608, 173, 66, 70)
    put(pg, 'b2', x=514, y=257, w=160, h=50, font=6)


# ------------------------------------------------------------------ 16 Wireless buddy (island 71,131,658,276)
def buddy(pg):
    words(pg, 't5', 'Pupil (Buddy)', x=87, y=147, w=label_w(6, 'Pupil (Buddy)'), h=40)
    words(pg, 't4', 'Instructor (Master)', x=87, y=197, w=label_w(6, 'Instructor (Master)'), h=40)
    rect(pg, 'BuddyP', 333, 149, 90, 36)
    rect(pg, 'BuddyM', 333, 199, 90, 36)
    for head, box, x in (('t1', 'cb0', 333), ('t2', 'cb1', 463), ('t3', 'cb2', 593)):
        put(pg, head, x=x, y=247, w=120, h=34, c={'pco': WHITE})   # (column heads: white, as every table's)
        rect(pg, box, x, 285, 120, 42)
    words(pg, 't6', 'Buddy switch', x=87, y=285, w=label_w(6, 'Buddy switch'), h=42)
    words(pg, 'b0', 'Buddy channels ...', x=209, y=341, w=332, h=50)
    rect(pg, 'b10', 553, 341, 160, 50)
    put(pg, 'card', x=71, y=131, w=658, h=276, a={'style': 0, 'borderw': 0})
    ev_title(pg, 'b15', 'r', 'Buddy help', 'Wireless buddy help')


# ------------------------------------------------------------------ 18 Buddy channels
def buddy_channels(pg):
    for k in range(1, 17): put(pg, f'ch{k}', txt='')           # (the main board writes the model's own channel names)


# ------------------------------------------------------------------ 45 Raining (Pong): the court is the screen's (y 56 .. 423)
def pong(pg):
    put(pg, 'b17', x=620, y=4, w=170, h=50, font=6)
    put(pg, 'b2', x=630, y=426, w=160, h=50, font=6)            # (its right edge on Help's and the court's)


EDITS = {33: tx_setup, 25: general, 24: clock, 23: advanced, 22: calibration, 55: sounds, 51: batteries, 17: background,
         16: buddy, 18: buddy_channels, 45: pong}
