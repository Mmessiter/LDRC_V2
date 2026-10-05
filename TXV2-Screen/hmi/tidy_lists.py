#!/usr/bin/env python3
"""Every other scrolling list shows whole rows too (Malcolm, 2026-10-03, after the Models page: "Yes please!").
A wheel keeps its chosen row in the middle, so it is neat only when its box holds an ODD number of WHOLE rows:
inner height = rows x row height (the "hig" attribute). The smallest change for each, with nothing on the page in
the way: only the list's height and row height change (names, ids, events untouched). Safe to run again.
(ModelsView: hmi/tidy_models_page.py. ImageView's list is covered by the screen's own picture chooser.)"""
import json, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'hmi', 'pages')
FIX = {  # page id: {list: (rows, row height)}
    19: {'FilesBox': (7, 39)},                                   # LogFiles: 8.36 rows of 33 -> 7 of 39 (Courier 32 had 1 px to spare)
    20: {'BK1': (3, 39), 'BK2': (3, 39), 'BK3': (3, 39), 'BK4': (3, 39)},   # BankNameView: 2.90 rows of 40 -> 3 of 39
    31: {'rate': (5, 35)},                                       # DualRatesView: 4.89 rows of 35 -> 5 (4 px taller)
    46: {'MMems': (9, 37)},                                      # IDsView: 9.51 rows of 35 -> 9 of 37 (same box)
}
for pid, lists in FIX.items():
    p = os.path.join(D, f'{pid}.json'); pg = json.load(open(p))
    for c in pg['comps']:
        if c['n'] in lists:
            rows, hig = lists[c['n']]; bw = c['a'].get('borderw', 0)
            c['a']['hig'] = hig; c['h'] = rows * hig + 2 * bw
            print(f"{pg['name']}.{c['n']}: {rows} whole rows of {hig}, box {c['w']} x {c['h']}")
    json.dump(pg, open(p, 'w'), separators=(',', ':'))
