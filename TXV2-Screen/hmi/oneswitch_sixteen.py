#!/usr/bin/env python3
"""OneSwitchView (page 54): a switch can be the input of any channel 5 to 16 (Teensy B33, Malcolm 2026-10-05: "Can we make
that 5 to 16, I wonder? That would be complete!"). The special jobs down the left (Not used, Banks 1 2 3, Bank 4 & Motor,
Safety, Rates, Buddy), the twelve channels in two columns on the right (5-10, 11-16): channels 9-12 keep their radios r3-r6
and labels t3-t6, the others are new (r10-r13 / t10-t13 for 5-8, r14-r17 / t14-t17 for 13-16). Every radio's release clears
the other seventeen, as before. Names, ids, types of what was there are untouched; new components take ids above the old
maximum. Safe to run again."""
import json, os
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'hmi', 'pages', '54.json')
pg = json.load(open(P))
def comp(n): return next((c for c in pg['comps'] if c['n'] == n), None)
def place(n, x, y, w, h): c = comp(n); c['x'], c['y'], c['w'], c['h'] = x, y, w, h
CARD = 4426
LEFT = [('r0', 't0', 76), ('r1', 't1', 122), ('r2', 't2', 168), ('r7', 't7', 214), ('r8', 't8', 260), ('r9', 't9', 306)]
for r, t, y in LEFT: place(r, 40, y, 40, 40); place(t, 94, y, 300, 40)
# the channels: (channel, radio, label, column, row)
CH = [(5, 'r10', 't10', 0, 0), (6, 'r11', 't11', 0, 1), (7, 'r12', 't12', 0, 2), (8, 'r13', 't13', 0, 3), (9, 'r3', 't3', 0, 4), (10, 'r4', 't4', 0, 5),
      (11, 'r5', 't5', 1, 0), (12, 'r6', 't6', 1, 1), (13, 'r14', 't14', 1, 2), (14, 'r15', 't15', 1, 3), (15, 'r16', 't16', 1, 4), (16, 'r17', 't17', 1, 5)]
COLX = {0: (416, 460, 140), 1: (606, 650, 140)}   # radio x, label x, label width
ROW0, ROWH = 76, 44
nextId = max(c['i'] for c in pg['comps']) + 1
ALL = ['r0', 'r1', 'r2', 'r7', 'r8', 'r9'] + [c[1] for c in CH]
SWV = {'r0': 0, 'r1': 1, 'r2': 2, 'r3': 3, 'r4': 4, 'r5': 5, 'r6': 6, 'r7': 7, 'r8': 8, 'r9': 9}
for ch, r, t, col, row in CH:
    if r not in SWV: SWV[r] = 10 + [c[1] for c in CH].index(r) if False else 10 + {'r10': 0, 'r11': 1, 'r12': 2, 'r13': 3, 'r14': 4, 'r15': 5, 'r16': 6, 'r17': 7}[r]
def event(me): return {'r': '\n'.join(f'{x}.val={1 if x == me else 0}' for x in ALL) + f'\nSwv.val={SWV[me]}'}
for ch, r, t, col, row in CH:
    rx, lx, lw = COLX[col]; y = ROW0 + row * ROWH
    if comp(r): place(r, rx, y, 40, 40)
    else:
        pg['comps'].insert(pg['comps'].index(comp('r9')) + 1, {'n': r, 'i': nextId, 't': 'radio', 'g': 'g', 'x': rx, 'y': y, 'w': 40, 'h': 40, 'c': {'pco': 53248, 'bco': 65535}, 'val': 0}); nextId += 1
    comp(r)['ev'] = event(r)
    if comp(t): place(t, lx, y, lw, 40); comp(t)['font'] = 6
    else:
        pg['comps'].insert(pg['comps'].index(comp('t9')) + 1, {'n': t, 'i': nextId, 't': 'text', 'g': 'g', 'x': lx, 'y': y, 'w': lw, 'h': 40, 'font': 6, 'sta': 1,
                           'c': {'pco': 65535, 'borderc': 0, 'bco': CARD}, 'txt': f'Channel {ch}', 'a': {'style': 0, 'key': 255, 'borderw': 0, 'xcen': 0, 'ycen': 1, 'pw': 0, 'txt_maxl': 24, 'isbr': 0}}); nextId += 1
for r in ['r0', 'r1', 'r2', 'r7', 'r8', 'r9']: comp(r)['ev'] = event(r)
json.dump(pg, open(P, 'w'), separators=(',', ':'))
print('OneSwitchView: channels 5-16;', len(pg['comps']), 'components, ids to', nextId - 1)
