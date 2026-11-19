#!/usr/bin/env python3
"""SubTrimView (page 32): THE PAGE'S WORD SAYS WHAT WAS DONE - the channel, the number it stood at, the number it made (main board B211, the
thirteenth review; Malcolm's transmitters, 15 Nov 2026).

The page works by itself: a channel's number tapped sets s0 and puts the slider on that channel's number; the slider, Zero, "+" and "-" set the
slider's number n0, copy it into the chosen channel's own box and print "StEDIT". Two things it did NOT do cost three reviews of the main board:
  - "StEDIT" did not say WHICH channel it was made on, nor WHAT it made: the main board had to ask the page afterwards - and by then the page could
    have been tapped on to another channel, or come back from Help;
  - a tapped channel did not put ITS OWN number into n0: "+" and "-" counted on from the channel BEFORE's number until the main board's answer to
    "StCH" had landed.
Now:
  1. a channel's tap puts that channel's own box into n0 (one line more in each of the sixteen tap scripts);
  2. the slider, Zero, "+" and "-" print  "StEDIT", s0, n0 AS IT STOOD, n0 AS IT IS NOW  - one burst of 18 bytes: the word and three numbers of four
     bytes each (print of a number). The main board takes the change only when "as it stood" is what the model has for that channel;
  3. "+", "-" and the slider stop at 117 either way: what the main board's card keeps (it centred anything beyond at the next switch-on);
  4. one part more, "rs" - a hotspot parked where no finger reaches: clicked by the main board ("click rs,0") it puts the slider's number and the
     slider on the box of the channel the page SHOWS. The main board writes the channels' boxes (each right for its channel wherever the page
     stands) and leaves the slider to the page, which alone knows its channel.
  5. ... and "rs" SAYS WHEN IT HAS RUN: "StEDIT" and the number the main board put into the variable "rsn" just before its click. The
     main board's writes can land on top of what the pilot did next; by this word it knows which of them have landed (it guessed "within a
     second" - a screen that stood still for two was its storm's find).
  6. (the fourteenth review) THE SLIDER'S PRESS SAYS THE WORD TOO: the finger landing moved the slider and said nothing (the press script was a
     comment) - the word came with the first move, or 80 ms after the lift, and a write of the main board's landing in between undid the tap.
  7. (the fourteenth review) EVERY BURST SAYS ITS LAST NUMBER TWICE (22 bytes for a touch, 14 for "done"): a character of the screen's own that
     falls into a burst (a field screen's Bluetooth library, a byte at a time from another task) moves the bytes behind it - and the main board
     takes nothing whose two last numbers do not agree.
An older main board finds "StEDIT" at the head of the burst and works as it always did (it asks the page) - better, by 1.
Names, ids, types and places of what was there are untouched; "rs" and "rsn" take the ids above the page's highest. Safe to run again.

  python3 hmi/subtrim_words.py                       sd/hmi/pages/32.json (the card) and hmi/originals/32.json (what pagestyle verifies against)
  python3 hmi/subtrim_words.py --from DIR --to DIR   read 32.json in DIR, write it to DIR (the main board's tests take the new page from there)"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
MOST = 117
SAY = 'print "StEDIT"\nprint s0.val\nprint n0.val\n'          # the word, the channel (1 to 16), the slider's number as it stood
def box(k): return 'n00' if k == 0 else 'n%d' % k
TWICE = 'print n0.val\nprint n0.val\nclick n0,0'            # what it made, said twice; then the chosen channel's own box takes it
SLIDER = SAY + 'n0.val=h0.val-127\n' + TWICE
PLUS = SAY + 'n0.val+=1\nif(n0.val>%d)\n{\n  n0.val=%d\n}\nh0.val=n0.val+127\n' % (MOST, MOST) + TWICE
MINUS = SAY + 'n0.val-=1\nif(n0.val<-%d)\n{\n  n0.val=-%d\n}\nh0.val=n0.val+127\n' % (MOST, MOST) + TWICE
ZERO = SAY + 'n0.val=0\nh0.val=127\n' + TWICE
RESYNC = ''.join('if(s0.val==%d)\n{\n  n0.val=%s.val\n}\n' % (k + 1, box(k)) for k in range(16)) + 'h0.val=n0.val+127\nprint "StEDIT"\nprint rsn.val\nprint rsn.val'   # "rs": the slider on the shown channel's own box - and "done", with the click's number (twice)
RSN = {'t': 'variable', 'g': 'l', 'sta': 0, 'txt': 'newtxt', 'val': 0, 'a': {'txt_maxl': 10}}   # "rsn": the number of the main board's click (as the page's own variable s0 is made)
def tap(k): b = box(k); return 'click n0,1\ns0.val=%d\nn0.val=%s.val\n%s.bco=WHITE\n%s.pco=RED\nprint "StCH"\nh0.val=%s.val+127' % (k + 1, b, b, b, b)
# what the page had (as the main board's B210 knew it): the script refuses a page that is neither that nor this - somebody changed it, and should look
WAS = {'h0.r': 'n0.val=h0.val-127\nprint "StEDIT"\nclick n0,0', 'h0.m': 'n0.val=h0.val-127\nprint "StEDIT"\nclick n0,0', 'h0.p': '//n0.val=h0.val-127',
       'b0.r': 'n0.val+=1\nif(n0.val>127)\n{\n  n0.val=127\n}\nh0.val=n0.val+127\nprint "StEDIT"\nclick n0,0',
       'b1.r': 'n0.val-=1\nif(n0.val<-127)\n{\n  n0.val=-127\n}\nh0.val=n0.val+127\nprint "StEDIT"\nclick n0,0',
       'b2.r': 'n0.val=0\nh0.val=127\nclick n0,0\nprint "StEDIT"'}
for k in range(16): b = box(k); WAS[b + '.r'] = 'click n0,1\ns0.val=%d\n%s.bco=WHITE\n%s.pco=RED\nprint "StCH"\nh0.val=%s.val+127' % (k + 1, b, b, b)
NOW = {'h0.r': SLIDER, 'h0.m': SLIDER, 'h0.p': SLIDER, 'b0.r': PLUS, 'b1.r': MINUS, 'b2.r': ZERO}
for k in range(16): NOW[box(k) + '.r'] = tap(k)
def one(src, dst):
    pg = json.load(open(src))
    if pg.get('name') != 'SubTrimView' or pg.get('id') != 32: sys.exit('%s is not the Sub-trim page' % src)
    comps = {c['n']: c for c in pg['comps']}; changed = 0
    for key in sorted(NOW):
        name, ev = key.split('.')
        if name not in comps: sys.exit('%s: no component %s' % (src, name))
        has = comps[name].get('ev', {}).get(ev)
        if has == NOW[key]: continue
        if has != WAS[key]: sys.exit('%s: the script %s is neither the old one nor the new one - LOOK at it:\n%s' % (src, key, has))
        comps[name]['ev'][ev] = NOW[key]; changed += 1
    a = comps['h0'].setdefault('a', {})
    if (a.get('minval'), a.get('maxval')) not in ((0, 254), (127 - MOST, 127 + MOST)): sys.exit('%s: the slider\'s limits are neither the old ones nor the new ones: %r' % (src, a))
    if (a.get('minval'), a.get('maxval')) != (127 - MOST, 127 + MOST): a['minval'], a['maxval'] = 127 - MOST, 127 + MOST; changed += 1
    if 'rs' not in comps:
        pg['comps'].append({'n': 'rs', 'i': max(c['i'] for c in pg['comps']) + 1, 't': 'hotspot', 'g': 'l', 'x': -2000, 'y': -2000, 'w': 10, 'h': 10, 'ev': {'r': RESYNC}}); changed += 1
    elif comps['rs'].get('t') != 'hotspot' or comps['rs'].get('ev') != {'r': RESYNC} or comps['rs'].get('x', 0) > -1000:
        sys.exit('%s: the part "rs" is not the hotspot this script makes - LOOK at it' % src)
    if 'rsn' not in comps:
        pg['comps'].append(dict({'n': 'rsn', 'i': max(c['i'] for c in pg['comps']) + 1}, **RSN)); changed += 1
    elif {k: v for k, v in comps['rsn'].items() if k not in ('n', 'i')} != RSN:
        sys.exit('%s: the part "rsn" is not the variable this script makes - LOOK at it' % src)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    json.dump(pg, open(dst, 'w'), separators=(',', ':'))
    print('%s -> %s: %d change(s)' % (src, dst, changed))
if __name__ == '__main__':
    if '--from' in sys.argv:
        one(os.path.join(sys.argv[sys.argv.index('--from') + 1], '32.json'), os.path.join(sys.argv[sys.argv.index('--to') + 1], '32.json'))
    else:
        for rel in (os.path.join('..', 'sd', 'hmi', 'pages', '32.json'), os.path.join('originals', '32.json')):
            p = os.path.join(HERE, rel)
            if os.path.exists(p): one(p, p)
            else: print('(not here: %s)' % rel)
