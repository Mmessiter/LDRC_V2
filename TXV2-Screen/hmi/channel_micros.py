#!/usr/bin/env python3
"""The Channels page (SticksView, page 26) shows each channel's microseconds (screen 1.11.80, Teensy B109). Malcolm,
16 Oct 2026: "On the screen which I did years ago, which shows the channels on a full screen, I forgot to include the
numeric indication of how many microseconds that channel is at. Can you think of a good way to include this by making a
small change to the screen?"
Beside each bar, by its own button, a box of the buttons' size (us1 .. us16: odd channels between the left buttons and
the bars, even ones between the bars and the right buttons), white words on the card (the theme's colours), in the
buttons' font. The bars give up the room: 364 -> 248 pixels, their middle line where it was (x 400), their rows as they
were. The Teensy writes us<n>.txt (main.cpp ShowChannelMicros). Safe to run again."""
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
# the right-hand buttons' words start at the left, as they always did on the Nextion (the left ones end at the right)
for i in range(2, 17, 2): by['Sch%d' % i]['a']['xcen'] = 0
for i in range(1, 17, 2): by['Sch%d' % i]['a']['xcen'] = 2
json.dump(pg, open(P, 'w'), separators=(',', ':'))
idx = json.load(open(IDX))
for x in idx['pages']:
    if x['id'] == 26: x['n'] = len(pg['comps'])
json.dump(idx, open(IDX, 'w'), indent=1)
print('SticksView: %d components; bars %d..%d, numbers %d wide in font %d' % (len(pg['comps']), BAR_X, BAR_X + BAR_W - 1, NUM_W, FONT))
