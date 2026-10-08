#!/usr/bin/env python3
"""The In-flight adjustments page of the transmitter (screen 1.11.35, B74): sd/hmi/pages/67.json (AdjustView), one
adjustment at a time, laid out as the phone page is (Malcolm, 8 Oct: "On the iPhone, I like being able to drag the blob
and see where the channel is ... make this version look more similar"): the Setting and the Channel as 'pick' rows, the
Kind and the bank by tap, then the BAR - the screen's own 'rangebar' type: the regions coloured and labelled, the
dividers as handles the finger drags, the channel's position as a marker - a line under it saying where the channel is
now and what that gives, and the values, one box per position, below. Re-run after a change here:
python3 hmi/adjust_pages.py (then hmi/rfmenu_pages.py for the menu's button)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp   # (importing it re-makes the rescue pages: harmless)
comp, PALE = rp.comp, rp.PALE
# codes (the main board's NumberedFunctions1): 116 open, 117 OK, 118 save, 119 a number edited, 120 setting >, 121 setting <,
# 122 channel >, 123 channel <, 124 kind tapped, 125 bank tapped, 126 previous, 127 next, 128 add, 129 remove, 130 a handle moved
name, title, help_file = 'AdjustView', 'Adjustment 1 of 1', 'ADJUST.TXT'
comps = []; i = [1]
def add(c): c['i'] = i[0]; i[0] += 1; comps.append(c); return c
def ev(code): return {'r': 'va0.val=%d<<8\nprint va0.val' % code}
add(comp(rp.TITLE, n='t0', txt=title)); add(comp(rp.CARD, n='card')); add(comp(rp.BANK, n='t9', txt='USB cable')); add(comp(rp.MODEL, n='t11', txt='Model name')); add(comp(rp.VA0, n='va0'))
hb = comp(rp.by['b0'], n='b0'); hb['ev'] = {'r': 'print "HelpView:%s"\nLogView.t0.txt="%s"\nLogView.return.txt="%s"' % (help_file, title + ' help', name)}; add(hb)
shade = PALE[0]
def label(nm, x, y, w, txt, h=36):
    l = comp(rp.LABEL_L, n=nm, x=x, y=y, w=w, h=h, txt=txt, g='g'); l['c'] = dict(l['c'], pco=0, bco=shade); return add(l)
def pick(row, nm, txt, code_next, code_prev):
    y = 94 + row * 40
    label('l' + nm, 34, y, 150, txt)
    bp = comp(rp.BUTTON, n='p' + nm, x=190, y=y - 2, w=50, h=40, txt='<'); bp['ev'] = ev(code_prev); add(bp)
    f = comp(rp.FIELD, n=nm, x=246, y=y, w=464, h=36, txt='', g='g'); f['a'] = dict(f['a'], key=255, txt_maxl=40); add(f)
    bn = comp(rp.BUTTON, n='n' + nm, x=716, y=y - 2, w=50, h=40, txt='>'); bn['ev'] = ev(code_next); add(bn)
def cycle(nm, lx, lw, vx, vw, y, txt, code):
    label('l' + nm, lx, y, lw, txt)
    f = comp(rp.FIELD, n=nm, x=vx, y=y, w=vw, h=36, txt='', g='g'); f['a'] = dict(f['a'], key=255); f['ev'] = ev(code); add(f)
def num(nm, x, y, w, code, klabel, h=34):
    f = comp(rp.FIELD, n=nm, x=x, y=y, w=w, h=h, txt='0', g='g'); f['ev'] = {'r': 'keybdB.t1.txt="%s"\nva0.val=%d<<8\nprint va0.val' % (klabel, code)}; add(f)
pick(0, 'tn0', 'Setting', 120, 121)
pick(1, 'tn1', 'Channel', 122, 123)
cycle('tn2', 34, 254, 294, 120, 174, 'Kind', 124)
cycle('tn3', 430, 236, 672, 94, 174, 'In bank', 125)
bar = {'n': 'bar', 't': 'rangebar', 'g': 'g', 'x': 34, 'y': 214, 'w': 732, 'h': 56, 'font': 2, 'txt': '', 'val': 0,
       'c': {'pco': 65535, 'bco': rp.CARD['c']['bco'], 'borderc': 0, 'pco2': 65535, 'bco2': 0},
       'a': {'lo': 875, 'hi': 2125, 'n': 2, 'kind': 0, 'mk': -1, 'd0': 1500, 'd1': 1700, 'd2': 1900, 'd3': 2000, 'd4': 2100, 'txt_maxl': 120}, 'ev': ev(130)}
add(bar)
live = label('tn8', 34, 276, 480, 'Channel now', 30); live['a'] = dict(live['a'], txt_maxl=48)
nowb = label('tn7', 524, 276, 242, 'Now: ?', 30); nowb['a'] = dict(nowb['a'], txt_maxl=24)
for k, x in enumerate((34, 278, 522)):
    label('ltn%d' % (4 + k), x, 342, 244, 'Position %d' % (k + 1), 32)
    num('tn%d' % (4 + k), x, 377, 244, 119, 'Value')
for (nm, txt, x, w, code) in [('b3', 'Save', 14, 120, 118), ('b4', '< Prev', 142, 120, 126), ('b2', 'Next >', 270, 120, 127), ('b5', 'Add', 398, 120, 128), ('b6', 'Remove', 526, 120, 129), ('b1', 'OK', 654, 120, 117)]:
    b = comp(rp.BUTTON, n=nm, x=x, y=414, w=w, h=56, txt=txt); b['ev'] = ev(code); add(b)
b = comp(rp.BUSY, n='busy', x=40, y=296, w=720, h=44, txt='', font=2); b['c'] = {'pco': 0, 'borderc': 0, 'bco': 65504}; b['a'] = dict(b['a'], borderw=2); add(b)
out = {'name': name, 'id': 67, 'w': 800, 'h': 480, 'bg': rp.rates['bg'], 'nav': rp.rates['nav'], 'ev': {'preinitialize': 'vis busy,0\n%s.pic=Screen_Background' % name}, 'comps': comps}
json.dump(out, open(os.path.join(rp.PAGES, '67.json'), 'w'), indent=1)
print(67, name, len(comps), 'components')
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
if 67 not in {x['id'] for x in idx['pages']}: idx['pages'].append({'id': 67, 'name': name, 'n': len(comps)}); idx['pages'].sort(key=lambda x: x['id'])
for x in idx['pages']:
    if x['id'] == 67: x['n'] = len(comps)
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
