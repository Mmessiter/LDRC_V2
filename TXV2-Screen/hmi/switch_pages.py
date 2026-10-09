#!/usr/bin/env python3
"""The Switches pages of the transmitter (screen card files, B77): sd/hmi/pages/69.json (SwitchView) and 70.json
(SwitchPickView) - what each switch of the transmitter makes the flight controller do (the configurator's Modes tab),
one action at a time, laid out as the adjustments page: "Does [Rescue - the safety net] on [Channel 8: AUX3]", the bar
with its one ON zone (blobs at the ends, the switch's marker), the line under it, Add / Remove / Save / OK. The picker
is a wheel of the actions, in the main board's order (RF_Switches.h SwModes). Re-run after a change here:
python3 hmi/switch_pages.py (then hmi/rfmenu_pages.py for the menu's button)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp
import adjust_pages as ap   # (the header/finish helpers; importing it re-makes the adjustments pages: harmless)
comp, PALE = rp.comp, rp.PALE
# codes (the main board's NumberedFunctions1): 133 open, 134 OK, 135 save, 136 the action (the picker), 137 the channel,
# 138 previous, 139 next, 140 add, 141 remove, 142 the bar's blobs dragged, 143 picker OK, 144 picker cancel
MODES = ["Arm - motor enable (ARM)", "Rescue - the safety net (RESCUE)", "Self-level (ANGLE)", "Self-level, blended (HORIZON)",
    "Altitude hold (ALTHOLD)", "Acro trainer (TRAINER)", "GPS rescue (GPS RESCUE)", "Failsafe test (FAILSAFE)",
    "Beeper on (BEEPER)", "Beeper mute (BEEPER MUTE)", "Black box recording (BLACKBOX)", "Black box erase (BLACKBOX ERASE)",
    "Pre-arm safety (PREARM)", "Lock the model - anti-tamper (PARALYZE)", "Governor fallback (GOVERNOR FALLBACK)",
    "Governor suspend (GOVERNOR SUSPEND)", "Governor bypass (GOVERNOR BYPASS)", "Calibrate (CALIB)", "Telemetry on/off (TELEMETRY)",
    "Stick commands off (STICK COMMANDS DISABLE)", "User switch 1 (USER1)", "User switch 2 (USER2)", "User switch 3 (USER3)", "User switch 4 (USER4)"]

comps = []; i = [1]; add = ap.header('SwitchView', 'Switch 1 of 1', 'SWITCHES.TXT', comps, i)
shade = PALE[1]
def label(nm, x, y, w, txt, h=36, pale=True):
    l = comp(rp.LABEL_L, n=nm, x=x, y=y, w=w, h=h, txt=txt, g='g')
    if pale: l['c'] = dict(l['c'], pco=0, bco=shade)
    else: l['c'] = {'pco': 65535, 'borderc': rp.CARD['c']['bco'], 'bco': rp.CARD['c']['bco']}; l['a'] = dict(l['a'], borderw=0)
    return add(l)
def tapbox(nm, x, y, w, code, h=36, maxl=40):
    f = comp(rp.FIELD, n=nm, x=x, y=y, w=w, h=h, txt='', g='g'); f['a'] = dict(f['a'], key=255, txt_maxl=maxl); f['ev'] = ap.ev(code); return add(f)
bp = comp(rp.BUTTON, n='bprev', x=215, y=7, w=56, h=44, txt='<'); bp['ev'] = ap.ev(138); add(bp)
bn = comp(rp.BUTTON, n='bnext', x=540, y=7, w=56, h=44, txt='>'); bn['ev'] = ap.ev(139); add(bn)
# B91: an island, as the adjustments page
W = 680; isl = rp.island(W, 236, [('b5', 'Add', 140), ('b6', 'Remove', 141), ('b3', 'Save', 135), ('b1', 'OK', 134)])
comps[1].update(x=isl['card'][0], y=isl['card'][1], w=isl['card'][2], h=isl['card'][3])
X, Y = isl['x0'], isl['y0']
label('ltn0', X, Y, 140, 'Does'); tapbox('tn0', X + 146, Y, W - 146, 136, maxl=48)
label('lon', X, Y + 46, 140, 'on'); tapbox('tn1', X + 146, Y + 46, W - 146, 137, maxl=24)
bar = {'n': 'bar', 't': 'rangebar', 'g': 'g', 'x': X, 'y': Y + 100, 'w': W, 'h': 60, 'font': 2, 'txt': '|ON|', 'val': 0,
       'c': {'pco': 65535, 'bco': rp.CARD['c']['bco'], 'borderc': 0, 'pco2': 65535, 'bco2': 0},
       'a': {'lo': 875, 'hi': 2125, 'n': 3, 'kind': 1, 'mk': -1, 'd0': 1700, 'd1': 2125, 'd2': 1900, 'd3': 2000, 'd4': 2100, 'txt_maxl': 40}, 'ev': ap.ev(142)}
add(bar)
live = label('tn8', X, Y + 168, W, '', 30); live['a'] = dict(live['a'], txt_maxl=40)
hint = label('hint', X, Y + 206, W, 'Drag the blobs to set where the switch turns it on.', 30, pale=False); hint['font'] = 2; hint['c']['pco'] = 50712; hint['a']['txt_maxl'] = 90
for (nm, txt, x, y, w, code) in isl['btn']:
    b = comp(rp.BUTTON, n=nm, x=x, y=y, w=w, h=rp.C_BTN_H, txt=txt); b['ev'] = ap.ev(code); add(b)
add(rp.message_box(rect=(isl['box'][0], Y + 168, isl['box'][2], 104)))   # (a message box under the bar, so the bar stays in sight)
ap.finish(69, 'SwitchView', comps)

comps = []; i = [1]; add = ap.header('SwitchPickView', 'What the switch does', 'SWITCHES.TXT', comps, i)
proto = None
for c in json.load(open(os.path.join(rp.PAGES, '46.json')))['comps']:
    if c['t'] == 'textselect': proto = c
LW, LH = 640, 7 * 37 + 6   # (B91: the wheel on an island: as wide as the longest action needs, seven whole rows)
isl = rp.island(LW, LH, [('b1', 'Cancel', 144), ('b3', 'OK', 143)])
comps[1].update(x=isl['card'][0], y=isl['card'][1], w=isl['card'][2], h=isl['card'][3])
wheel = comp(proto, n='list', x=isl['x0'], y=isl['y0'], w=LW, h=LH, txt='', val=0, opt=MODES); wheel['a'] = dict(wheel['a'], hig=37); wheel['ev'] = {}
add(wheel)
for (nm, txt, x, y, w, code) in isl['btn']:
    b = comp(rp.BUTTON, n=nm, x=x, y=y, w=w, h=rp.C_BTN_H, txt=txt); b['ev'] = ap.ev(code); add(b)
add(rp.message_box(rect=isl['box']))
ap.finish(70, 'SwitchPickView', comps)
