#!/usr/bin/env python3
"""1.11.40 (Malcolm, 9 Oct: "Information and warning banners should look like message boxes rather than yellow text
stripes ... The groups of buttons should look tidy, centred, and lined up wherever possible"): the Rotorflight pages made
from Version 1's (PIDs 40, PID+ 7, Rates 1, Rates+ 42, Governor 6 and global 5) brought into line with the new ones, in
place and idempotently (their own generator, restyle_batch3.py, starts from the original Nextion pages and would undo
later work): the bottom row by the shared rule (rescue_pages.bottom_row), the reading / failure banner ("busy", "t4" on
the global governor page) a message box (text style 5) below the table where there is room, else over the middle, last
in the page so it lies on top. PID+ keeps its row: Save and OK either side of the model's name, symmetrical already.
Run: python3 hmi/tidy_rf_pages.py"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp
PAGES = rp.PAGES
PLAN = {   # page: (the bottom row's buttons left to right, OK last - None keeps the row; the banner; its rectangle)
    1: (['b3', 'b2', 'b1'], 'busy', (110, 336, 580, 70)),
    40: (['b3', 'b2', 'b1'], 'busy', (110, 316, 580, 90)),
    42: (['b3', 'b1'], 'busy', rp.MSGBOX),
    5: (['b3', 'b1'], 't4', rp.MSGBOX),
    6: (['b3', 'b1'], 'busy', rp.MSGBOX),
    7: (['b3', 'b1'], 'busy', rp.MSGBOX),   # (its lower row, y 430, kept: the rows run to 415; the model's name moves left of Save)
}
# B91: these pages are islands now (hmi/islands.py), made from their copies in hmi/pre_islands: this works on THOSE copies
# (where they exist), and hmi/islands.py must be run after it
PRE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pre_islands')
for pid, (row, banner, rect) in PLAN.items():
    path = os.path.join(PRE, '%d.json' % pid) if os.path.exists(os.path.join(PRE, '%d.json' % pid)) else os.path.join(PAGES, '%d.json' % pid)
    pg = json.load(open(path))
    by = {c['n']: c for c in pg['comps']}
    if row:
        for nm, t, x, w, code in rp.bottom_row([(n, by[n]['txt'], 0) for n in row]):
            by[nm]['x'] = x; by[nm]['w'] = w
    if pid == 7 and 't27' in by: by['t27'].update(x=14, w=380); by['t27']['a'] = dict(by['t27'].get('a', {}), xcen=0)
    b = by[banner]
    b.update(x=rect[0], y=rect[1], w=rect[2], h=rect[3], font=2, sta=1)
    b['c'] = {'pco': 65535, 'borderc': 65535, 'bco': rp.CARD['c']['bco']}
    b['a'] = dict(b.get('a', {}), style=5, borderw=0, xcen=1, ycen=1, isbr=1, txt_maxl=max(200, b.get('a', {}).get('txt_maxl', 0)))
    pg['comps'] = [c for c in pg['comps'] if c is not b] + [b]   # (on top; its id "i" is kept)
    pre = pg.setdefault('ev', {}).get('preinitialize', '')
    if 'vis %s,0' % banner not in pre: pg['ev']['preinitialize'] = 'vis %s,0\n' % banner + pre   # (6 and 42 showed theirs until the first read ended: a message box must wait to be asked for)
    json.dump(pg, open(path, 'w'), indent=1)
    print(pid, pg['name'], 'row' if row else 'row kept', banner, rect)
print('now: python3 hmi/islands.py')
