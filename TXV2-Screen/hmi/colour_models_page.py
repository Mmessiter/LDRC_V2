#!/usr/bin/env python3
"""ModelsView (page 15): two sides, two colours (Malcolm, 2026-10-05: "the heading Models should become Models Loaded ... Backups
should become Backup Files ... the left-hand side should adopt a colour for the headings and the buttons and the models, which
looks unified. The right-hand side, which handles the backup files ... a unified colour, but a different one").
Left = the models in the transmitter, blue; right = the backup files on the card, amber. Each side: its heading a solid strip
in the deep colour with white words, its list bordered in the deep colour on the pale tint, its buttons the pale tint (the deep
colour while pressed). The middle column (Help, Backup, Restore), the picture, the name and OK stay as they are: OK is the
page's button, grey like every page's. Names, ids, types, places and events untouched. Safe to run again."""
import json, os
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'hmi', 'pages', '15.json')
pg = json.load(open(P))
def comp(n): return next(c for c in pg['comps'] if c['n'] == n)
def rgb(r, g, b): return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
SIDES = {  # heading, list, buttons, (deep, pale)
    'left':  ('t0', 'Models Loaded', 'MMems',  ('b0', 'b12', 'b11', 'b3'), (rgb(30, 90, 160), rgb(205, 225, 245))),
    'right': ('t1', 'Backup Files',  'Mfiles', ('b9', 'b2', 'b1'),         (rgb(170, 100, 20), rgb(250, 230, 190))),
}
for side, (heading, words, lst, buttons, (deep, pale)) in SIDES.items():
    h = comp(heading); h['txt'] = words; h['a']['style'] = 1; h['a']['borderw'] = 0
    h['c'].update({'bco': deep, 'pco': 65535, 'borderc': deep})
    l = comp(lst); l['c'].update({'bco': pale, 'borderc': deep}); l['a']['borderw'] = 3   # (pco grey, pco2 black for the chosen row: as before)
    for b in buttons: comp(b)['c'].update({'bco': pale, 'bco2': deep, 'pco': 0, 'pco2': 65535})
comp('t1')['y'] = comp('t0')['y']                                                       # (both headings level, flush on their lists)
json.dump(pg, open(P, 'w'), separators=(',', ':'))
print('ModelsView coloured:', {s: (hex(v[4][0]), hex(v[4][1])) for s, v in SIDES.items()})
