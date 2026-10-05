#!/usr/bin/env python3
"""SwitchesView (page 53): EIGHT switches (Teensy B32, Malcolm 2026-10-05: "Ideally, it should be possible to designate any of
these eight to any of those functions"). The top edge's four as before (1, 2 left; 3, 4 right; seen from above with the sticks
towards you) and the front four below them (5, 6 left; 7, 8 right), each row: its number, its job, and where it is now
("up", "mid", "down": the main board writes p1..p8 while the page shows, so a front switch is told from the others by moving it).
Names, ids, types and events of what was there are untouched; new components take ids above the page's old maximum. Safe to
run again."""
import json, os
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'hmi', 'pages', '53.json')
pg = json.load(open(P))
def comp(n): return next((c for c in pg['comps'] if c['n'] == n), None)
def place(n, x, y, w, h): c = comp(n); c['x'], c['y'], c['w'], c['h'] = x, y, w, h
CARD, STRIP, SOFT, INK = 4426, 2214, 50712, 65535
ROW_H, GAP = 46, 6
TOP_Y, FRONT_Y = 92, 258                       # the first row of each group
COLS = {0: (34, 88, 326), 1: (410, 464, 702)}  # number x, job x, position x
NUM_W, JOB_W, POS_W = 48, 232, 64
def row(sw):                                   # switch 1-8 -> (column, y)
    group, k = (0, sw - 1) if sw <= 4 else (1, sw - 5)
    col, r = (0, k) if k < 2 else (1, k - 2)
    return col, (TOP_Y if group == 0 else FRONT_Y) + r * (ROW_H + GAP)
nextId = max(c['i'] for c in pg['comps']) + 1
def add(n, t, x, y, w, h, font, txt, c, a, ev=None, after=None):
    global nextId
    if comp(n): return comp(n)
    d = {'n': n, 'i': nextId, 't': t, 'g': 'l', 'x': x, 'y': y, 'w': w, 'h': h, 'font': font, 'sta': 1, 'c': c, 'txt': txt, 'a': a}
    if ev: d['ev'] = ev
    nextId += 1
    pg['comps'].insert(pg['comps'].index(comp(after)) + 1 if after else len(pg['comps']), d); return d
comp('t0')['txt'] = 'Switches'
m = comp('ModelName'); m.update({'x': 10, 'y': 4, 'w': 200, 'h': 25, 'font': 2}); m['c'].update({'pco': 65504, 'bco': STRIP}); m['a'].update({'xcen': 0, 'txt_maxl': 20})
hint = comp('t'); place('t', 34, 360, 732, 50); hint['txt'] = 'Touch a number or its job to set up that switch.\r\nMove a switch to see which one it is: near (towards you), mid or away.'
hint['a']['txt_maxl'] = 300
for sw in range(1, 9):
    col, y = row(sw); nx, jx, px = COLS[col]
    tn, jn, pn = f't{sw}', f'sw{sw}', f'p{sw}'
    if comp(tn): place(tn, nx, y, NUM_W, ROW_H); comp(tn)['font'] = 0
    else: add(tn, 'text', nx, y, NUM_W, ROW_H, 0, str(sw), {'pco': 0, 'borderc': 0, 'bco': 54938},
              {'style': 3, 'key': 255, 'borderw': 2, 'xcen': 1, 'ycen': 1, 'pw': 0, 'txt_maxl': 25, 'isbr': 0}, {'r': f'print "OneSwitchView {sw}"'}, after='sw4')
    if comp(jn): place(jn, jx, y, JOB_W, ROW_H)
    else: add(jn, 'text', jx, y, JOB_W, ROW_H, 6, 'Not used', {'pco': 0, 'borderc': 0, 'bco': 54938},
              {'style': 3, 'key': 255, 'borderw': 2, 'xcen': 1, 'ycen': 1, 'pw': 0, 'txt_maxl': 25, 'isbr': 0}, {'r': f'print "OneSwitchView {sw}"'}, after='sw4')
    if comp(pn): place(pn, px, y, POS_W, ROW_H)
    else: add(pn, 'text', px, y, POS_W, ROW_H, 6, '', {'pco': INK, 'borderc': 0, 'bco': CARD},
              {'style': 0, 'key': 255, 'borderw': 0, 'xcen': 1, 'ycen': 1, 'pw': 0, 'txt_maxl': 8, 'isbr': 0})
add('h0', 'text', 34, 64, 732, 26, 2, 'On the top edge, seen from above with the sticks towards you', {'pco': SOFT, 'borderc': 0, 'bco': CARD},
    {'style': 0, 'key': 255, 'borderw': 0, 'xcen': 0, 'ycen': 1, 'pw': 0, 'txt_maxl': 80, 'isbr': 0})
add('h1', 'text', 34, 230, 732, 26, 2, 'On the front (the inputs of channels 5 to 8: a knob there reads as a switch)', {'pco': SOFT, 'borderc': 0, 'bco': CARD},
    {'style': 0, 'key': 255, 'borderw': 0, 'xcen': 0, 'ycen': 1, 'pw': 0, 'txt_maxl': 90, 'isbr': 0})
json.dump(pg, open(P, 'w'), separators=(',', ':'))
print('SwitchesView: eight switches;', len(pg['comps']), 'components, ids to', nextId - 1)
