#!/usr/bin/env python3
"""The curve page (GraphView, page 21): how many points (Teensy B118). Malcolm, 17 Oct 2026: "Might it be possible for us now
to allow the user to choose 3 points, 5 points, 7 points, or 9 points?" A "Points:" row of four radio buttons (3 5 7 9, codes
221-224) where the Expo controls sit - the Teensy shows this row for Straight and Smooth and the Expo controls for
Exponential (updateInterpolationTypes) - and number boxes along the top for the extra points: k2 k3 k5 k6 (font 2, with
n1 n3 n5, 60 pixels apart) for seven, m1-m9 (font 4, smaller, 45 apart) for nine. The Teensy shows the right set and their
values (CurveLayoutShow). Safe to run again."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontw import width
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'hmi', 'pages', '21.json')
pg = json.load(open(P))
assert pg['name'] == 'GraphView'
NEW = {'k2', 'k3', 'k5', 'k6', 'm1', 'm2', 'm3', 'm4', 'm5', 'm6', 'm7', 'm8', 'm9', 'lpt', 'pt3', 'lpt3', 'pt5', 'lpt5', 'pt7', 'lpt7', 'pt9', 'lpt9'}
pg['comps'] = [c for c in pg['comps'] if c['n'] not in NEW]
by = {c['n']: c for c in pg['comps']}
nid = max(c['i'] for c in pg['comps']) + 1
def add(c):
    global nid
    c['i'] = nid; nid += 1
    pg['comps'].append(c); by[c['n']] = c
def copy(c): return json.loads(json.dumps(c))
n1 = by['n1']
assert n1['t'] == 'number' and n1['font'] == 2 and n1['w'] == 52
# seven points: 60 pixels apart from x 35 - points 1, 4 and 7 take n1, n3 and n5; the other four are new, the same font
for k in (2, 3, 5, 6):
    c = copy(n1); c['n'] = 'k%d' % k; c['x'] = 35 + 60 * (k - 1) - 26; add(c)
# nine points: 45 apart, in the smaller font (16 pixels; "2500" is 32 wide) so nine fit
for k in range(1, 10):
    c = copy(n1); c['n'] = 'm%d' % k; c['font'] = 4; c['w'] = 40; c['h'] = 20; c['y'] = 6; c['x'] = 35 + 45 * (k - 1) - 20; add(c)
for c in pg['comps']:
    if c['t'] == 'number' and c['n'][0] in 'nkm' and c['n'][1:].isdigit():
        assert width(c['font'], '2500') <= c['w'] - 2, (c['n'], width(c['font'], '2500'), c['w'])
# the Points row where the Expo controls are (y 338): a label and four radios with their numbers
label = copy(by['t3'])   # "Expo": the same text style
label['n'] = 'lpt'; label['txt'] = 'Points:'; label['w'] = width(6, 'Points:') + 8; label.pop('ev', None); add(label)
assert label['x'] == 424 and label['y'] == 338
x = 528
for n, code in ((3, 221), (5, 222), (7, 223), (9, 224)):
    ev = 'pt3.val=%d\npt5.val=%d\npt7.val=%d\npt9.val=%d\nva0.val=%d<<8\nprint va0.val' % (n == 3, n == 5, n == 7, n == 9, code)
    r = {'n': 'pt%d' % n, 't': 'radio', 'g': 'l', 'x': x, 'y': 338, 'w': 40, 'h': 36, 'c': {'pco': 53248, 'bco': 65535}, 'val': 1 if n == 5 else 0, 'ev': {'r': ev}}
    add(r)
    l = copy(by['t3']); l['n'] = 'lpt%d' % n; l['txt'] = str(n); l['x'] = x + 44; l['w'] = width(6, str(n)) + 8; l['ev'] = {'r': ev}; add(l)
    x += 66
assert x - 66 + 44 + by['lpt9']['w'] <= 800, x
# nothing of the row overlaps anything else that is shown with it (the Expo controls share the spot: never both)
def box(c): return (c['x'], c['y'], c['x'] + c['w'], c['y'] + c['h'])
def overlap(a, b): A, B = box(a), box(b); return A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]
row = [by[n] for n in ('lpt', 'pt3', 'lpt3', 'pt5', 'lpt5', 'pt7', 'lpt7', 'pt9', 'lpt9')]
expo = {'t3', 'Expo', 'Ex1', 'b12', 'b13'}
for a in row:
    for c in pg['comps']:
        if c is a or c['n'] in expo or c['n'].startswith('card') or 'x' not in c: continue
        assert not overlap(a, c), (a['n'], c['n'])
for i, a in enumerate(row):
    for b in row[i + 1:]: assert not overlap(a, b), (a['n'], b['n'])
json.dump(pg, open(P, 'w'), separators=(',', ':'))
print('GraphView: Points row (3 5 7 9) and number boxes for 7 and 9 points; %d components' % len(pg['comps']))
