#!/usr/bin/env python3
"""The Rates page's rates TYPE, chosen on the transmitter (screen 1.11.78, B106; Malcolm, 16 Oct 2026, a photo of the Rates
page: "On the transmitter, we can see the rates type, but we cannot edit it. Please can we add that in?"): on 1.json
(RatesView) the type's box (t10) is tapped - the main board (TXV1B RF_Rates.h RatesTypeTapped) opens 82.json
(RatesTypeView), a wheel of Rotorflight's seven types in the phone app's words, at the bank's own type; OK puts the bank's
rates to the chosen type's starting values (as Rotorflight's Configurator does), Cancel changes nothing, and the Rates
page's Save writes them. The box's look is the polish's (hmi/polish/rfcore.py rates: a white box like the numbers'), its
tap is set here. Re-run after a change here: python3 hmi/ratestype_pages.py, then python3 hmi/polish_pages.py 1."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp   # (importing it re-makes the rescue pages: harmless)
from fontw import width
from adjust_pages import header, ev, finish   # (importing it re-makes the adjustments' pages: harmless)
comp = rp.comp
# codes (the main board's NumberedFunctions1): 214 the type tapped (its picker), 215 the picker's OK, 216 its Cancel
TAP, OK, CANCEL = 214, 215, 216
TYPES = ['0 - NONE', '1 - BETAFLIGHT', '2 - RACEFLIGHT', '3 - KISS', '4 - ACTUAL', '5 - QUICKRATES', '6 - ROTORFLIGHT']   # (TXV1B 1Definitions.h Rate_Types: the phone's words)
NOTE = "OK sets the rates to this type's starting values."

# ---- page 1: the type's box opens the picker
p1 = os.path.join(rp.PAGES, '1.json'); pg = json.load(open(p1))
t10 = [c for c in pg['comps'] if c['n'] == 't10'][0]
t10['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % TAP}
t10['a'] = dict(t10['a'], key=255)
json.dump(pg, open(p1, 'w'), indent=1)

# ---- page 82: the picker - a wheel of the seven types, the note on what OK does, Cancel and OK
comps = []; i = [1]; add = header('RatesTypeView', 'Rates type', 'RATES1.TXT', comps, i, link='Rate 1', help_title='Rates (Rotorflight)')
proto = [c for c in json.load(open(os.path.join(rp.PAGES, '68.json')))['comps'] if c['t'] == 'textselect'][0]   # (the adjustments' wheel)
ROW = 36; LH = len(TYPES) * ROW + 6          # (seven whole rows: every type in sight when the wheel is in the middle)
NOTE_GAP, NOTE_H = 8, 28
LW = max(width(2, NOTE), max(width(6, t) for t in TYPES) + 120)
isl = rp.island(LW, LH + NOTE_GAP + NOTE_H, [('b1', 'Cancel', CANCEL), ('b3', 'OK', OK)])
comps[1].update(x=isl['card'][0], y=isl['card'][1], w=isl['card'][2], h=isl['card'][3])
wheel = comp(proto, n='list', x=isl['x0'], y=isl['y0'], w=LW, h=LH, txt='', val=4, opt=TYPES); wheel['a'] = dict(wheel['a'], hig=ROW); wheel['ev'] = {}
add(wheel)
note = comp(rp.LABEL_L, n='t1', x=isl['x0'], y=isl['y0'] + LH + NOTE_GAP, w=LW, h=NOTE_H, txt=NOTE, g='l', font=2)
note['c'] = {'pco': 65535, 'borderc': rp.CARD['c']['bco'], 'bco': rp.CARD['c']['bco']}
note['a'] = dict(note['a'], borderw=0, xcen=1, ycen=1, txt_maxl=len(NOTE) + 10, key=255)
add(note)
for (nm, txt, x, y, w, code) in isl['btn']:
    b = comp(rp.BUTTON, n=nm, x=x, y=y, w=w, h=rp.C_BTN_H, txt=txt); b['ev'] = ev(code); add(b)
add(rp.message_box(rect=isl['box']))
finish(82, 'RatesTypeView', comps)
print('card', isl['card'], 'wheel', LW, 'x', LH)
