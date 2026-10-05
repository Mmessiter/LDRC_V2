#!/usr/bin/env python3
"""The three System pages (Transmitter > System): OptionsView, OptionView2 (the clock), OptionView3, redesigned
(Malcolm, 2026-10-03: "functional ... but it looks less good than it should. Please would you redesign it to be nicer
looking and easier to understand and use, without altering its functionality.")

What does NOT change: every component's name, id, type and events, so the Teensy writes and reads exactly what it did
(MenuOptions.h: SystemPage1Start/End, OptionView2Start, OptionView3Start/End, ResetClock). What changes: places,
sizes, colours, fonts and the words of the fixed labels; one navy card behind each page's settings; on the clock
page a label over each pair of + and - buttons; the footnote of page 3 becomes the unit beside its box.
The user's own background picture stays (the pages' preinitialize is untouched).

Run once on sd/hmi/pages/{23,24,25}.json (it starts from the files as they are and is safe to run again).
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, '..', 'sd', 'hmi', 'pages')
NAVY, STRIP, WHITE, SOFT, BLACK, BTN, GREEN, GREY = 4426, 2214, 65535, 50712, 0, 54938, 2016, 33808

# Where things go (800 x 480): the title strip, the card, and four equal button slots along the bottom.
STRIP_H = 58
CARD = (14, 66, 772, 340)                              # x, y, w, h
SLOTS = [(14 + i * 197, 414, 180, 56) for i in range(4)]   # 0: Back, 1: Bind, 2: Next, 3: OK (the same place on every page)
LABEL_X, LABEL_W, BOX_X, BOX_W, UNIT_X, UNIT_W = 30, 444, 484, 120, 614, 166

def load(pid): return json.load(open(os.path.join(PAGES, f'{pid}.json')))
def save(pid, pg): json.dump(pg, open(os.path.join(PAGES, f'{pid}.json'), 'w'), separators=(',', ':'))
def comp(pg, name):
    for c in pg['comps']:
        if c['n'] == name: return c
    sys.exit(f'{pg["name"]}: no component {name}')
def place(c, x, y, w, h): c['x'], c['y'], c['w'], c['h'] = x, y, w, h

def title(pg, text):
    t = comp(pg, 't0'); place(t, 0, 0, 800, STRIP_H)
    t['sta'] = 1; t['font'] = 0; t['txt'] = text; t['c'].update({'bco': STRIP, 'pco': WHITE})
    t['a'].update({'xcen': 1, 'ycen': 1, 'style': 0, 'borderw': 0})
    t['a']['txt_maxl'] = max(t['a'].get('txt_maxl', 0), len(text))

def card(pg, after, ev):
    """One plain navy card behind the settings: a text component with nothing in it, drawn just after the title.
    (A touch on it does what a touch on the page did: the page's own events.)"""
    if any(c['n'] == 'card' for c in pg['comps']): pg['comps'] = [c for c in pg['comps'] if c['n'] != 'card']
    newid = max(c['i'] for c in pg['comps']) + 1
    c = {'n': 'card', 'i': newid, 't': 'text', 'g': 'l', 'x': CARD[0], 'y': CARD[1], 'w': CARD[2], 'h': CARD[3], 'font': 6, 'sta': 1,
         'c': {'pco': WHITE, 'borderc': WHITE, 'bco': NAVY}, 'txt': '', 'a': {'style': 1, 'key': 255, 'borderw': 2, 'xcen': 0, 'ycen': 1, 'pw': 0, 'txt_maxl': 1, 'isbr': 0}}
    if ev: c['ev'] = ev
    at = next(i for i, x in enumerate(pg['comps']) if x['n'] == after) + 1
    pg['comps'].insert(at, c)

def add_label(pg, name, text, x, y, w, h, font=6, colour=WHITE, xcen=0):
    pg['comps'] = [c for c in pg['comps'] if c['n'] != name]
    newid = max(c['i'] for c in pg['comps']) + 1
    pg['comps'].append({'n': name, 'i': newid, 't': 'text', 'g': 'l', 'x': x, 'y': y, 'w': w, 'h': h, 'font': font, 'sta': 1,
                        'c': {'pco': colour, 'borderc': 0, 'bco': NAVY}, 'txt': text,
                        'a': {'style': 0, 'key': 255, 'borderw': 0, 'xcen': xcen, 'ycen': 1, 'pw': 0, 'txt_maxl': len(text) + 2, 'isbr': 0}})

def label(pg, name, text, y, h, xcen=0, colour=WHITE):
    c = comp(pg, name); place(c, LABEL_X, y, LABEL_W, h)
    c['sta'] = 1; c['font'] = 6; c['txt'] = text; c['c'].update({'bco': NAVY, 'pco': colour, 'borderc': 0})
    c['a'].update({'xcen': xcen, 'ycen': 1, 'style': 0, 'borderw': 0}); c['a']['txt_maxl'] = max(c['a'].get('txt_maxl', 0), len(text) + 2)

def unit(pg, name, text, y, h):
    c = comp(pg, name); place(c, UNIT_X, y, UNIT_W, h)
    c['sta'] = 1; c['font'] = 6; c['txt'] = text; c['c'].update({'bco': NAVY, 'pco': SOFT, 'borderc': 0})
    c['a'].update({'xcen': 0, 'ycen': 1, 'style': 0, 'borderw': 0}); c['a']['txt_maxl'] = max(c['a'].get('txt_maxl', 0), len(text) + 2)

def box(pg, name, y, h, w=BOX_W):
    c = comp(pg, name); place(c, BOX_X, y, w, h)
    c['sta'] = 1; c['font'] = 6; c['c'].update({'bco': WHITE, 'pco': BLACK, 'borderc': 0})
    c['a'].update({'xcen': 1, 'ycen': 1, 'style': 2, 'borderw': 2})

def switch(pg, name, y, h):
    c = comp(pg, name); place(c, BOX_X + 10, y + 3, BOX_W - 20, h - 6)
    c['c'].update({'bco': GREY, 'bco2': GREEN, 'pco': WHITE})

def button(pg, name, slot, text=None):
    c = comp(pg, name); place(c, *SLOTS[slot])
    c['font'] = 6; c['c'].update({'bco': BTN, 'pco': BLACK})
    if text is not None: c['txt'] = text; c['a']['txt_maxl'] = max(c['a'].get('txt_maxl', 0), len(text) + 2)

def park(pg, name):                                    # out of sight: the screen draws nothing off the glass, and nothing there can be touched
    c = comp(pg, name); c['x'] = -2000; c['y'] = -2000

def rows(start, step, n): return [start + i * step for i in range(n)]

def ground(pg):                                        # blue everywhere under the strip (Malcolm, 10-03: only slivers of the picture showed)
    c = comp(pg, 'card'); place(c, 0, STRIP_H, 800, 480 - STRIP_H); c['a'].update({'style': 0, 'borderw': 0})

# ------------------------------------------------------------------ page 1: OptionsView
p1 = load(25)
title(p1, 'General  (1 of 3)')
card(p1, 't0', {'r': 'print "UKRULES"'})               # (the page's own touch_release: a keep-awake)
H1 = 44; y = rows(78, 51, 6)
label(p1, 't5', 'Automatic model selection (AMS)', y[0], H1); switch(p1, 'c0', y[0], H1)   # (AMS: the front page says "AMS is on")
label(p1, 'ST', 'Screen goes dark after', y[1], H1); box(p1, 'Sto', y[1], H1); unit(p1, 't1', 'seconds', y[1], H1)
label(p1, 't2', 'Switch off when unused for', y[2], H1); box(p1, 'Pto', y[2], H1); unit(p1, 't3', 'minutes', y[2], H1)
label(p1, 't10', 'Low battery warning at', y[3], H1); box(p1, 'Bwn', y[3], H1); unit(p1, 't11', '%', y[3], H1)
c = comp(p1, 't11'); c['font'] = 6
label(p1, 't4', 'Stick mode', y[4], H1); box(p1, 'n0', y[4], H1)
add_label(p1, 'u_mode', '1 or 2', UNIT_X, y[4], UNIT_W, H1, colour=SOFT)
label(p1, 't6', "Owner's name", y[5], H1); box(p1, 'TxName', y[5], H1, w=CARD[0] + CARD[2] - 16 - BOX_X)
comp(p1, 't6')['w'] = 190; c = comp(p1, 'TxName'); c['x'] = 230; c['w'] = CARD[0] + CARD[2] - 16 - 230   # (30 letters: "Malcolm Messiter's transmitter" is 345 px)
pr = comp(p1, 'Progress'); place(pr, CARD[0] + 16, CARD[1] + CARD[3] - 20, CARD[2] - 32, 10)   # (shown only while OK saves)
button(p1, 'b12', 0); place(comp(p1, 'b12'), 620, 4, 170, 50)   # Help, in the strip where every page has it
button(p1, 'b0', 1)                                    # Bind ("Stop Bind" while binding): never where Back is on the other pages
button(p1, 'b13', 2, 'Next  >')
button(p1, 'b10', 3, 'OK')
ground(p1); save(25, p1)

# ------------------------------------------------------------------ page 2: OptionView2, the clock
p2 = load(24)
title(p2, 'Clock  (2 of 3)')
card(p2, 't0', None)
dt = comp(p2, 'DateTime'); place(dt, CARD[0] + 4, CARD[1] + 6, CARD[2] - 8, 76)
dt['sta'] = 1; dt['font'] = 1; dt['c'].update({'bco': NAVY, 'pco': WHITE}); dt['a'].update({'xcen': 1, 'ycen': 1, 'style': 0, 'borderw': 0})
# + above and - below each part of the time, a label between: Day, Month, Year, Hour, Minute (left to right, as the time reads)
cols = [('b9', 'b11', 'Day'), ('b7', 'b8', 'Month'), ('b6', 'b5', 'Year'), ('b4', 'b3', 'Hour'), ('b1', 'b2', 'Minute')]
CW, GAP = 132, 18; X0 = (800 - (5 * CW + 4 * GAP)) // 2
for i, (plus, minus, name) in enumerate(cols):
    x = X0 + i * (CW + GAP)
    for nm, yy, txt in ((plus, 160, '+'), (minus, 262, '-')):
        b = comp(p2, nm); place(b, x, yy, CW, 54); b['font'] = 0; b['txt'] = txt; b['c'].update({'bco': BTN, 'pco': BLACK})
    add_label(p2, f'lb{i}', name, x, 216, CW, 44, colour=WHITE, xcen=1)
label(p2, 't8', 'Time zone (hours from GMT)', 336, 46); comp(p2, 't8')['a']['xcen'] = 0
box(p2, 'dGMT', 336, 46)
rc = comp(p2, 'b12'); place(rc, 614, 336, 156, 46); rc['font'] = 6; rc['txt'] = 'Reset clock'; rc['c'].update({'bco': BTN, 'pco': BLACK})
button(p2, 'b0', 0, '<  Back')
button(p2, 'b13', 2, 'Next  >')
button(p2, 'b10', 3, 'OK')
ground(p2); save(24, p2)

# ------------------------------------------------------------------ page 3: OptionView3
p3 = load(23)
title(p3, 'Advanced  (3 of 3)')
card(p3, 't0', None)
H3 = 32; y = rows(76, 36, 9)                       # (9 rows, 10 px clear of the card at the top and the bottom)
label(p3, 't5', 'Keep log files', y[0], H3); switch(p3, 'sw0', y[0], H3)
label(p3, 't11', 'Log receiver radio swaps', y[1], H3); switch(p3, 'sw1', y[1], H3)
label(p3, 't6', 'LED brightness', y[2], H3); box(p3, 'n1', y[2], H3); add_label(p3, 'u_led', '15 - 254', UNIT_X, y[2], UNIT_W, H3, colour=SOFT)   # (MenuOptions.h keeps it there)
label(p3, 't1', 'Transmitter battery correction', y[3], H3); box(p3, 't2', y[3], H3); add_label(p3, 'u_volt', '0.01 V / cell', UNIT_X, y[3], UNIT_W, H3, colour=SOFT)
label(p3, 't8', 'Switch-off countdown', y[4], H3); box(p3, 'n2', y[4], H3); add_label(p3, 'u_warn', 'seconds', UNIT_X, y[4], UNIT_W, H3, colour=SOFT)   # (hold the power button this long while a model is connected)
label(p3, 't9', 'Connection quality measured over', y[5], H3); box(p3, 'n3', y[5], H3); add_label(p3, 'u_conn', 'seconds', UNIT_X, y[5], UNIT_W, H3, colour=SOFT)   # (the front page's connection meter)
label(p3, 't4', 'Radio scanner sensitivity', y[6], H3); box(p3, 'n4', y[6], H3); add_label(p3, 'u_scan', '1 - 255', UNIT_X, y[6], UNIT_W, H3, colour=SOFT)
label(p3, 't7', 'Sea-level pressure (QNH)', y[7], H3); box(p3, 'Qnh', y[7], H3); add_label(p3, 'u_qnh', 'hPa', UNIT_X, y[7], UNIT_W, H3, colour=SOFT)
label(p3, 't10', 'Log gaps longer than', y[8], H3); box(p3, 'n0', y[8], H3); add_label(p3, 'u_gap', 'ms', UNIT_X, y[8], UNIT_W, H3, colour=SOFT)
park(p3, 't3')                                         # the footnote: now the unit beside its box
button(p3, 'b13', 0, '<  Back')
button(p3, 'b10', 3, 'OK')
for nm in ('b13', 'b10'): comp(p3, nm)['c']['pco'] = BLACK
ground(p3); save(23, p3)
print('System pages 1-3 redesigned')
