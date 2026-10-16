#!/usr/bin/env python3
"""The curve page (GraphView, page 21) in microseconds (Teensy B110). Malcolm, 16 Oct 2026: "we see on the right stick
input and servo output and then numbers which are a percentage - not a very useful number. I think probably it should say
more simply input and output, and probably the numbers should be microseconds." The words become "Input" and "Output";
the Teensy now writes microseconds into Input, Output and the points along the top (n1-n5), so each box is checked for
the widest (2500), and Input and Output start at the middle (1500) rather than 100 until the Teensy writes them.
Safe to run again."""
import json, os
from fontw import width
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'hmi', 'pages', '21.json')
pg = json.load(open(P))
assert pg['name'] == 'GraphView'
by = {c['n']: c for c in pg['comps']}
by['t1']['txt'], by['t2']['txt'] = 'Input', 'Output'
for n in ('Input', 'Output'):
    by[n]['val'] = 1500
for n in ('Input', 'Output', 'n1', 'n2', 'n3', 'n4', 'n5'):
    c = by[n]
    assert c['t'] == 'number' and width(c['font'], '2500') <= c['w'] - 2, (n, width(c['font'], '2500'), c['w'])
for n in ('t1', 't2'):
    assert width(by[n]['font'], by[n]['txt']) <= by[n]['w'], n
json.dump(pg, open(P, 'w'), separators=(',', ':'))
print('GraphView: "Input" / "Output", numbers in microseconds')
