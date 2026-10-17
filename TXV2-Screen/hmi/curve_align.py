#!/usr/bin/env python3
"""The curve page (GraphView, page 21): the numbers lined up with the words (screen 1.11.84). Malcolm, 17 Oct 2026: "the input
and output numbers and the exponential number could be lined up with the words straight smooth exponential and copy to all
banks because this would look tidier". Input, Output and the Expo number now begin at x 520, where those words begin, and
read left to right like them; the Points radios start there too. Safe to run again."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontw import width
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'hmi', 'pages', '21.json')
pg = json.load(open(P))
assert pg['name'] == 'GraphView'
by = {c['n']: c for c in pg['comps']}
WORDS_X = by['t4']['x']   # "Straight"
assert WORDS_X == 520 and by['t5']['x'] == WORDS_X and by['t6']['x'] == WORDS_X and by['t0']['x'] == WORDS_X
for n in ('Input', 'Output', 'Expo'):
    c = by[n]; assert c['t'] == 'number'
    c['x'] = WORDS_X; c['w'] = 100; c['a']['xcen'] = 0          # from the words' left edge, reading left to right
    assert width(c['font'], '2500') <= c['w'] - 2
for n in ('t1', 't2'):                                             # "Input", "Output": room up to the numbers
    c = by[n]; c['w'] = WORDS_X - c['x'] - 6
    assert width(c['font'], c['txt']) <= c['w'], (n, width(c['font'], c['txt']), c['w'])
x = WORDS_X                                                        # the Points radios, from the same edge
for n in (3, 5, 7, 9):
    by['pt%d' % n]['x'] = x; by['lpt%d' % n]['x'] = x + 44; x += 66
assert by['lpt9']['x'] + by['lpt9']['w'] <= 800
def box(c): return (c['x'], c['y'], c['x'] + c['w'], c['y'] + c['h'])
def overlap(a, b): A, B = box(a), box(b); return A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]
shown_together = [['t1', 'Input'], ['t2', 'Output'], ['t3', 'Expo', 'b13', 'b12'], ['lpt', 'pt3', 'lpt3', 'pt5', 'lpt5', 'pt7', 'lpt7', 'pt9', 'lpt9']]
for group in shown_together:
    for i, a in enumerate(group):
        for b in group[i + 1:]: assert not overlap(by[a], by[b]), (a, b)
json.dump(pg, open(P, 'w'), separators=(',', ':'))
print('GraphView: Input, Output, Expo and the Points radios lined up at x %d' % WORDS_X)
