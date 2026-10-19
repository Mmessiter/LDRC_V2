#!/usr/bin/env python3
"""BankNameView (page 20): SIX bank names (Teensy B130, Malcolm 19 Oct 2026: six banks, as Rotorflight has). Three columns by two
rows, each box with its bank's label above it; boxes 5 and 6 (BK5, BK6, labels t5, t6) show only when the model uses six banks -
the main board sends vis for them and for t7, the note in their place ("Six banks: see Model options"). The presets set all six.
Names, ids, types and events of what was there are untouched; new components take ids above the page's old maximum. Safe to run
again. Applied to sd/hmi/pages/20.json (the card) and, the same components, to hmi/originals/20.json (what pagestyle verifies against)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = ['Flight mode 1', 'Flight mode 2', 'Flight mode 3', 'Flight mode 4', 'Bank 1', 'Bank 2', 'Bank 3', 'Bank 4', 'Aerobatics', 'Auto',
         'Cruise', 'Flaps', 'Hover', 'Idle up 1', 'Idle up 2', 'Landing', 'Launch', 'Normal', 'Speed', 'Take off', 'Thermal', 'Hold', '3D',
         'Brakes', 'Stunt 1', 'Stunt 2', 'Gear down', 'Gear up', 'Profile 1', 'Profile 2', 'Profile 3', 'Profile 4',
         'Flight mode 5', 'Flight mode 6', 'Bank 5', 'Bank 6', 'Profile 5', 'Profile 6']   # (1Definitions.h BankNames, the same order)
PRESETS = {'b0': [0, 1, 2, 3, 32, 33], 'b1': [4, 5, 6, 7, 34, 35], 'b4': [12, 13, 14, 21, 34, 35], 'b2': [16, 17, 18, 20, 34, 35]}  # Default, VBar, Heli, Glider
CARD, STRIP, SOFT, INK = 4426, 2214, 50712, 65535
COL_X = (32, 284, 536); BOX_W, BOX_H, LAB_H = 232, 121, 26
ROW_LAB_Y = (70, 232); ROW_BOX_Y = (98, 260)
BTN_Y = 398
def one(path, layout):
    pg = json.load(open(path))
    def comp(n): return next((c for c in pg['comps'] if c['n'] == n), None)
    nextId = max(c['i'] for c in pg['comps']) + 1
    def clone(src, n, after):
        nonlocal nextId
        if comp(n): return comp(n)
        d = json.loads(json.dumps(comp(src))); d['n'] = n; d['i'] = nextId; nextId += 1
        pg['comps'].insert(pg['comps'].index(comp(after)) + 1, d); return d
    for k in (5, 6):                                   # the two new boxes and their labels, from bank 4's
        clone('BK4', 'BK%d' % k, 'BK4'); clone('t4', 't%d' % k, 't4')
    if not comp('t7'):
        d = {'n': 't7', 'i': nextId, 't': 'text', 'g': 'l', 'x': 284, 'y': 260, 'w': 484, 'h': 121, 'font': 2, 'sta': 1,
             'c': {'pco': SOFT, 'borderc': 0, 'bco': CARD}, 'txt': "Six banks? Turn on 'Six banks' on Model options.",
             'a': {'style': 0, 'key': 255, 'borderw': 0, 'xcen': 1, 'ycen': 1, 'pw': 0, 'txt_maxl': 60, 'isbr': 0}}
        nextId += 1; pg['comps'].append(d)
    for k in range(1, 7):
        comp('BK%d' % k)['opt'] = list(NAMES)
        comp('t%d' % k)['txt'] = 'Bank %d' % k
    for n, vals in PRESETS.items():
        comp(n)['ev'] = {'r': '\n'.join('BK%d.val=%d' % (k + 1, v) for k, v in enumerate(vals))}
    if layout:
        comp('card').update({'x': 24, 'y': 62, 'w': 752, 'h': 408})
        for k in range(1, 7):
            col, row = (k - 1) % 3, (k - 1) // 3
            comp('BK%d' % k).update({'x': COL_X[col], 'y': ROW_BOX_Y[row], 'w': BOX_W, 'h': BOX_H})
            lab = comp('t%d' % k); lab.update({'x': COL_X[col], 'y': ROW_LAB_Y[row], 'w': BOX_W, 'h': LAB_H, 'font': 2})
            lab['c'].update({'pco': INK, 'bco': CARD}); lab['a'].update({'xcen': 0, 'ycen': 1})
        comp('t7').update({'x': 284, 'y': 260, 'w': 484, 'h': 121})
        for n, x in (('b0', 40), ('b1', 162), ('b4', 284), ('b2', 406), ('b3', 528), ('b10', 650)):
            comp(n).update({'x': x, 'y': BTN_Y, 'w': 110, 'h': 50})
    json.dump(pg, open(path, 'w'), separators=(',', ':') if layout else None, indent=None if layout else 1)
    return len(pg['comps']), nextId - 1
print('sd:', one(os.path.join(HERE, '..', 'sd', 'hmi', 'pages', '20.json'), True))
print('originals:', one(os.path.join(HERE, 'originals', '20.json'), False))
