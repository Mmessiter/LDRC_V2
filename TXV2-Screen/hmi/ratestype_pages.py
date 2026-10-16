#!/usr/bin/env python3
"""The Rates page's rates TYPE, chosen on the transmitter (screen 1.11.78, B106; Malcolm, 16 Oct 2026, a photo of the Rates
page: "On the transmitter, we can see the rates type, but we cannot edit it. Please can we add that in?"): on 1.json
(RatesView) the type's box (t10) is tapped - the main board (TXV1B RF_Rates.h RatesTypeTapped) opens 82.json
(RatesTypeView), a wheel of Rotorflight's seven types in the phone app's words, at the bank's own type; OK puts the bank's
rates to the chosen type's starting values (as Rotorflight's Configurator does), Cancel changes nothing, and the Rates
page's Save writes them. The box's look is the polish's (hmi/polish/rfcore.py rates: a white box like the numbers'), its
tap is set here. Screen 1.11.79 (B107; Malcolm, a photo of the phone's Rates curves: "I wonder if it might be possible to
have these curves on the transmitter!?"): "Curves ..." on the Rates page (b4, the bottom row's free slot) opens 83.json
(RatesCurveView): the four curves, which the main board draws on the plot (RF_Rates.h RatesCurvePoll) with Rotorflight's
own formulas - the legend down the left in the Rates page's pale axis shades, the type under it, the plot to the right
(PLOT: RF_Rates.h RC_PLOT_* must agree - TXV1B dev/test_rates checks). Its postinitialize prints "ldrcrcv" so the main
board draws the curves whenever the page comes back. Re-run after a change here: python3 hmi/ratestype_pages.py, then
python3 hmi/polish_pages.py 1."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp   # (importing it re-makes the rescue pages: harmless)
from fontw import width
from adjust_pages import header, ev, finish   # (importing it re-makes the adjustments' pages: harmless)
comp = rp.comp
# codes (the main board's NumberedFunctions1): 214 the type tapped (its picker), 215 the picker's OK, 216 its Cancel,
# 217 "Curves ...", 218 the curves page's OK
TAP, OK, CANCEL, CURVES, CURVES_OK = 214, 215, 216, 217, 218
TYPES = ['0 - NONE', '1 - BETAFLIGHT', '2 - RACEFLIGHT', '3 - KISS', '4 - ACTUAL', '5 - QUICKRATES', '6 - ROTORFLIGHT']   # (TXV1B 1Definitions.h Rate_Types: the phone's words)
NOTE = "OK sets the rates to this type's starting values."

# ---- page 1: the type's box opens the picker
p1 = os.path.join(rp.PAGES, '1.json'); pg = json.load(open(p1))
t10 = [c for c in pg['comps'] if c['n'] == 't10'][0]
t10['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % TAP}
t10['a'] = dict(t10['a'], key=255)
# ... and "Curves ..." in the bottom row's free slot, left of "Dynamics ...", dressed as it is (B107)
b2 = [c for c in pg['comps'] if c['n'] == 'b2'][0]
pg['comps'] = [c for c in pg['comps'] if c['n'] != 'b4']
b4 = json.loads(json.dumps(b2)); b4.update(n='b4', i=max(c['i'] for c in pg['comps']) + 1, x=b2['x'] - 172, txt='Curves ...')
b4['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % CURVES}
pg['comps'].append(b4)
assert b4['x'] >= [c for c in pg['comps'] if c['n'] == 'card'][0]['x'] + 16, 'Curves ... runs off the card'
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

# ---- page 83: the curves - the legend down the left (each axis in the Rates page's pale shade, black words: the main board
# writes "Roll 250 deg/s" ...), the rates type under it, the plot to the right (white; the main board draws on it), OK
comps = []; i = [1]; add = header('RatesCurveView', 'Rates curves', 'RATES1.TXT', comps, i, link='Rate 1', help_title='Rates (Rotorflight)')
CW, CH = 712, 294                      # (the largest island's content)
isl = rp.island(CW, CH, [('b1', 'OK', CURVES_OK)])
comps[1].update(x=isl['card'][0], y=isl['card'][1], w=isl['card'][2], h=isl['card'][3])
x0, y0 = isl['x0'], isl['y0']
LEG_W, LEG_H, LEG_GAP, PLOT_GAP = 196, 30, 8, 10
LEG_WORDS = ['Roll', 'Pitch', 'Yaw', 'Collective']
SHADES = [65341, 59323, 61215, 65497]   # (the Rates page's pale axis labels: hmi/polish/rfcore.py ROLL, PITCH, YAW, COLL)
assert max(width(2, w + ' 2000 deg/s') for w in LEG_WORDS[:3]) + 8 <= LEG_W and width(2, 'Collective 50.0 deg') + 8 <= LEG_W, 'a legend runs out of its box'
for k, (w, shade) in enumerate(zip(LEG_WORDS, SHADES)):
    l = comp(rp.LABEL_L, n='lg%d' % k, x=x0, y=y0 + k * (LEG_H + LEG_GAP), w=LEG_W, h=LEG_H, txt=w, g='l', font=2)
    l['c'] = dict(l['c'], pco=0, bco=shade); l['a'] = dict(l['a'], xcen=1, ycen=1, txt_maxl=32, key=255)
    add(l)
tt = comp(rp.LABEL_L, n='tt', x=x0, y=y0 + 4 * (LEG_H + LEG_GAP), w=LEG_W, h=LEG_H, txt='', g='l', font=2)
tt['c'] = {'pco': 65535, 'borderc': rp.CARD['c']['bco'], 'bco': rp.CARD['c']['bco']}; tt['a'] = dict(tt['a'], borderw=0, xcen=1, ycen=1, txt_maxl=24, key=255)
add(tt)
PLOT = (x0 + LEG_W + PLOT_GAP, y0, CW - LEG_W - PLOT_GAP, CH)
plot = comp(rp.LABEL_L, n='plot', x=PLOT[0], y=PLOT[1], w=PLOT[2], h=PLOT[3], txt='', g='l', font=2)
plot['c'] = {'pco': 0, 'borderc': 65535, 'bco': 65535}; plot['a'] = dict(plot['a'], borderw=0, key=255, txt_maxl=1)
add(plot)
for (nm, txt, x, y, w, code) in isl['btn']:
    b = comp(rp.BUTTON, n=nm, x=x, y=y, w=w, h=rp.C_BTN_H, txt=txt); b['ev'] = ev(code); add(b)
add(rp.message_box(rect=isl['box']))
finish(83, 'RatesCurveView', comps)
p83 = os.path.join(rp.PAGES, '83.json'); pg = json.load(open(p83)); pg['ev']['postinitialize'] = 'print "ldrcrcv"'; json.dump(pg, open(p83, 'w'), indent=1)
print('card', isl['card'], 'PLOT', PLOT)
