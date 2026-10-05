#!/usr/bin/env python3
"""The front page's bottom row (screen 1.7.3). Malcolm, 2026-10-04: "On the original screen let's add 'use defined' as a
middle button" - between Transmitter and Model, as the flight screen has "Original screen" between its setups (Malcolm,
10-04, screen 1.8.6: "Transmitter  Defined screen  Model" / "Transmitter  Original screen  Model").

The middle of that row held the link: the word "Connected" (or "Sending Parameters ...") over the green quality bar.
Both move up into the band between the batteries/timer and the buttons, side by side: the word on the left, ending
where the bar begins, the bar out to the Model button's right edge (the row's edges, 38 to 765); the buttons come
down 4 pixels to make room. (Text over the bar does not work: a see-through text shows the page's picture, as on a
Nextion.) The main board writes the same boxes by the same names as before. Also in hmi/overrides.json, for a rebuild
from the HMI. Safe to run again."""
import json, os, copy
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'hmi', 'pages', '13.json')
pg = json.load(open(P)); assert pg['name'] == 'FrontView'
by = {c['n']: c for c in pg['comps']}
Y, H, BW = 394, 53, 229                                     # the bottom row (was 390, 57): three equal buttons, 38 to 765 (screen 1.8.6: "Defined screen" wants the room)
for n, x in (('b0', 38), ('b1', 536)): by[n]['x'], by[n]['y'], by[n]['w'], by[n]['h'] = x, Y, BW, H
btn = copy.deepcopy(by['b0'])
btn.update({'n': 'ldrcDefined', 'i': 90, 'x': 287, 'y': Y, 'w': BW, 'h': H, 'txt': 'Defined screen', 'ev': {'r': 'ldrc defined'}})
btn['a']['txt_maxl'] = max(btn['a'].get('txt_maxl', 0), len(btn['txt']) + 2)
assert all(c['i'] != 90 for c in pg['comps'] if c['n'] != 'ldrcDefined'), 'id 90 is taken'
q, w = by['Quality'], by['Connected']
q.update({'x': 305, 'y': 377, 'w': 460, 'h': 13})
w.update({'x': 38, 'y': 370, 'w': 262, 'h': 24, 'font': 2})
w['c']['pco'] = 65535; w.setdefault('a', {}).update({'xcen': 2, 'ycen': 1})   # (white, as it was; ending where the bar begins)
comps = [c for c in pg['comps'] if c['n'] != 'ldrcDefined']
comps.append(btn)
pg['comps'] = comps
json.dump(pg, open(P, 'w'), separators=(',', ':'))
print('FrontView: Defined screen in the middle; the link bar above the buttons, its word on it')
