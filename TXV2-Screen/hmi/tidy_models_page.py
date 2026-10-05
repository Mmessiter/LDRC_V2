#!/usr/bin/env python3
"""ModelsView (the model select page): its two lists show whole rows only (Malcolm, 2026-10-03: "alignment and word
fitting are not quite looking neat yet ... the words are too close to the left edge and top and bottom words are
clipped by the box edge"). A scrolling list keeps its chosen row in the middle, so it looks neat only when the box
holds an ODD number of WHOLE rows: 160 px held 4.46 rows of 35. Now 5 rows (179 px), the three middle buttons spaced
to the same height, and the progress bar (shown only while a backup or restore runs) a thin strip in the gap.
Names, ids, types and events are untouched. (The left margin and the "..." for a long name are the screen's own
drawing: src/main.cpp drawList, screen 1.5.5.) Safe to run again."""
import json, os
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'hmi', 'pages', '15.json')
pg = json.load(open(P))
def comp(n): return next(c for c in pg['comps'] if c['n'] == n)
def place(n, x, y, w, h): c = comp(n); c['x'], c['y'], c['w'], c['h'] = x, y, w, h
ROWS, TOP = 5, 42
for n in ('MMems', 'Mfiles'):
    c = comp(n); bw = c['a'].get('borderw', 0); hig = c['a'].get('hig', 35)
    c['y'] = TOP; c['h'] = ROWS * hig + 2 * bw                     # 5 x 35 + 2 x 2 = 179
H = comp('MMems')['h']
gap = 7; bh = (H - 2 * gap) // 3                                # Help, > Backup >, < Restore < : the lists' height between them
for i, n in enumerate(('b15', 'b4', 'b5')):
    c = comp(n); c['y'] = TOP + i * (bh + gap); c['h'] = bh
comp('b5')['h'] = TOP + H - comp('b5')['y']                     # (the last one meets the lists' bottom edge exactly)
place('Progress', 10, TOP + H + 3, 787, 6)                      # 224..230: between the lists and the buttons below
# "File error!" sits on the model picture and was listed before it, so the picture's repaint covered it: it was never seen
# (screen 1.5.6). It now comes after the picture in the list (the screen draws in list order; ids are unchanged).
order = [c['n'] for c in pg['comps']]
if order.index('error') < order.index('exp0'):
    err = comp('error'); pg['comps'].remove(err); pg['comps'].insert(order.index('exp0'), err)
json.dump(pg, open(P, 'w'), separators=(',', ':'))
print('ModelsView: lists', TOP, '..', TOP + H, '(5 whole rows); middle buttons', [(comp(n)['y'], comp(n)['h']) for n in ('b15', 'b4', 'b5')])
