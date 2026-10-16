#!/usr/bin/env python3
"""The Channels page (SticksView, page 26) shows each channel's microseconds (screen 1.11.80, Teensy B109). Malcolm,
16 Oct 2026: "On the screen which I did years ago, which shows the channels on a full screen, I forgot to include the
numeric indication of how many microseconds that channel is at. Can you think of a good way to include this by making a
small change to the screen?"
Beside each bar, by its own button, a box of the buttons' size (us1 .. us16: odd channels between the left buttons and
the bars, even ones between the bars and the right buttons), white words on the card (the theme's colours), in the
buttons' font. The bars give up the room: 364 -> 248 pixels, their middle line where it was (x 400), their rows as they
were. The Teensy writes us<n>.txt (main.cpp ShowChannelMicros). B111/B112: "Stick ends:" 944 to 2055 or 500 to 2500,
bottom left (main.cpp StickEndsChosen). Safe to run again."""
import json, os
from fontw import width
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'hmi', 'pages', '26.json')
IDX = os.path.join(os.path.dirname(P), '..', 'index.json')
BAR_X, BAR_W = 276, 248        # (was 218, 364)
NUM_W, FONT = 64, 2            # a box between a button and the bars: 212..275 on the left, 524..587 on the right
pg = json.load(open(P))
assert pg['name'] == 'SticksView'
by = {c['n']: c for c in pg['comps']}
for i in range(1, 17):
    b = by['Ch%d' % i]
    b['x'], b['w'] = BAR_X, BAR_W
assert BAR_X + BAR_W // 2 == 400
pg['comps'] = [c for c in pg['comps'] if not c['n'].startswith('us')]
nid = max(c['i'] for c in pg['comps']) + 1
for i in range(1, 17):
    s = by['Sch%d' % i]
    left = i % 2 == 1
    x = s['x'] + s['w'] if left else s['x'] - NUM_W
    assert (x + NUM_W == BAR_X) if left else (x == BAR_X + BAR_W), i
    pg['comps'].append({'n': 'us%d' % i, 'i': nid, 't': 'text', 'g': 'l', 'x': x, 'y': s['y'], 'w': NUM_W, 'h': s['h'], 'font': FONT, 'sta': 1,
                        'c': {'pco': 65535, 'borderc': 0, 'bco': 4426}, 'txt': '',
                        'a': {'style': 0, 'key': 255, 'borderw': 0, 'xcen': 1, 'ycen': 1, 'pw': 0, 'txt_maxl': 6, 'isbr': 0}})
    nid += 1
assert width(FONT, '2500') + 8 <= NUM_W
# Teensy B111 (Malcolm: "switching to your restricted range ought to be a user option please rather than permanent or
# automatic") and B112 ("The current max range is 500-2500 and I think this should be one of the two selectable ranges"):
# bottom left, beside OK, "Stick ends:" and two choices as the Batteries page has them (radio buttons, their words
# beside them): se1 "944 to 2055" (code 219) and se2 "500 to 2500" (code 220). A choice or its words touched marks it and
# asks the Teensy, which asks the pilot, changes the curves or not, and marks the choice as things then are (neither,
# when the curves end elsewhere). Global, so a page back from a curve keeps what the Teensy last showed.
pg['comps'] = [c for c in pg['comps'] if c['n'] not in ('se', 'lse', 'se1', 'se2', 'lse1', 'lse2')]
nid = max(c['i'] for c in pg['comps']) + 1
ok = by['b10']
R_W, R_H, R_GAP, W_GAP = 40, 36, 4, 12          # (the Batteries page's radio buttons: 40 x 36, the words 4 px on)
def words(n, txt, x, w, ev=None):
    c = {'n': n, 'i': 0, 't': 'text', 'g': 'l', 'x': x, 'y': ok['y'], 'w': w, 'h': ok['h'], 'font': 6, 'sta': 1,
         'c': {'pco': 65535, 'borderc': 0, 'bco': 4426}, 'txt': txt,
         'a': {'style': 0, 'key': 255, 'borderw': 0, 'xcen': 0, 'ycen': 1, 'pw': 0, 'txt_maxl': 25, 'isbr': 0}}
    if ev: c['ev'] = {'r': ev}
    assert width(6, txt) <= w, txt
    return c
def pick(k, code): return 'se1.val=%d\nse2.val=%d\nva0.val=%d<<8\nprint va0.val' % (k == 1, k == 2, code)
x = 10
row = [words('lse', 'Stick ends:', x, width(6, 'Stick ends:') + 4)]
x += row[-1]['w'] + 8
for k, (txt, code) in enumerate((('944 to 2055', 219), ('500 to 2500', 220)), start=1):
    row.append({'n': 'se%d' % k, 'i': 0, 't': 'radio', 'g': 'g', 'x': x, 'y': ok['y'] + (ok['h'] - R_H) // 2, 'w': R_W, 'h': R_H,
                'c': {'pco': 53248, 'bco': 65535}, 'val': 0, 'ev': {'r': pick(k, code)}})
    x += R_W + R_GAP
    row.append(words('lse%d' % k, txt, x, width(6, txt) + 6, pick(k, code)))
    x += row[-1]['w'] + W_GAP
assert x - W_GAP <= ok['x'] - 8, x
for c in row:
    c['i'] = nid; nid += 1
    pg['comps'].append(c)
# the right-hand buttons' words start at the left, as they always did on the Nextion (the left ones end at the right)
for i in range(2, 17, 2): by['Sch%d' % i]['a']['xcen'] = 0
for i in range(1, 17, 2): by['Sch%d' % i]['a']['xcen'] = 2
json.dump(pg, open(P, 'w'), separators=(',', ':'))
idx = json.load(open(IDX))
for x in idx['pages']:
    if x['id'] == 26: x['n'] = len(pg['comps'])
json.dump(idx, open(IDX, 'w'), indent=1)
print('SticksView: %d components; bars %d..%d, numbers %d wide in font %d' % (len(pg['comps']), BAR_X, BAR_X + BAR_W - 1, NUM_W, FONT))
