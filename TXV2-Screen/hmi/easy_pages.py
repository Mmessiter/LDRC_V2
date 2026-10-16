#!/usr/bin/env python3
"""The Easy tuning page of the transmitter (screen card files, B104): sd/hmi/pages/81.json (EasyView) - the phone app's
page (rotorflight-easy.html) on the transmitter, in the phone's words: Start (Very gentle .. Very fierce) and its switch
"Also switch on PID spool-up in every bank (recommended)", Agility (Docile .. Acrobatic) and Stick feel (Soft centre ..
Direct), Cyclic and Tail (Softer .. Sharper). Dense, so the largest island. The sliders stand on the phone's steps of 5:
Start, Agility and Stick feel 0..20 (x 5 = 0..100), Cyclic and Tail 0..12 (x 5 - 30 = -30..30 %). The main board (TXV1B
RF_Easy.h) does the sums and writes the words.
Screen 1.11.76 (B105; Malcolm, 16 Oct: "please move it to the bottom of the options and change the colour because it
looks rather like a divider. ... add a temporary display of affected pid etc values in the space below ... appear when
finger lands, update as it slides, vanish on finger lift"): the switch's row is the last, its words white on the card
like the sliders' end words; under the rows, a box of numbers (lvb, with five columns lv0-lv4 that the main board fills)
that the sliders' own scripts show as the finger lands - in the row's shade, emptied - and hide as it lifts. Each slider
word carries the slider's place: va0.val = (place + 1) << 24 + code << 8, 64 more in the top byte when it is let go (the
main board's ButtonWasPressed: ScreenEventArg). Re-run after a change here: python3 hmi/easy_pages.py (then
hmi/rfmenu_pages.py for the menu's button)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp
from fontw import width
# codes (the main board's NumberedFunctions1): 205 open, 206 OK, 207 Save, 208-212 a slider touched, dragged or let go
# (Start, Agility, Stick feel, Cyclic, Tail), 213 the switch
PID, NAME, HELP = 81, 'EasyView', 'EASY.TXT'
ROWS = [  # (label box, its words, shade, left word, slider, right word, top, code); None: the switch's row (B105: the last)
    ('lS', 'Start', 0, ('e0L', 'Very gentle'), 's0', ('e0R', 'Very fierce'), 20, 208),
    ('lA', 'Agility', 1, ('e1L', 'Docile'), 's1', ('e1R', 'Acrobatic'), 20, 209),
    ('lE', 'Stick feel', 1, ('e2L', 'Soft centre'), 's2', ('e2R', 'Direct'), 20, 210),
    ('lC', 'Cyclic', 2, ('e3L', 'Softer'), 's3', ('e3R', 'Sharper'), 12, 211),
    ('lT', 'Tail', 2, ('e4L', 'Softer'), 's4', ('e4R', 'Sharper'), 12, 212),
    None,
]
LIVE = ['lvb', 'lv0', 'lv1', 'lv2', 'lv3', 'lv4']   # B105: the numbers box and its five columns (names; four of numbers)
LIVE_MX, LIVE_MY, LIVE_W0, LIVE_W = 8, 8, 140, 139   # (the margins; the names' column: Cyclic +30 % and 13 px; a column of numbers: 1000 -> 1300 and 10 px)
SPOOL = 'Also switch on PID spool-up in every bank (recommended)'
FONT, ROW_H, PITCH, NOTE_H, GAP = 2, 36, 40, 52, 8
CONTENT_W = 712
CONTENT_H = len(ROWS) * PITCH - (PITCH - ROW_H) + 6 + NOTE_H
LW = max(width(FONT, r[1]) for r in ROWS if r) + 20
EL = max(width(FONT, r[3][1]) for r in ROWS if r) + 4
ER = max(width(FONT, r[5][1]) for r in ROWS if r) + 4
SW = CONTENT_W - LW - EL - ER - 3 * GAP
CARD_BCO = rp.CARD['c']['bco']

isl = rp.island(CONTENT_W, CONTENT_H, [('b3', 'Save', 207), ('b1', 'OK', 206)])
menu = json.load(open(os.path.join(rp.PAGES, '8.json')))
mby = {c['n']: c for c in menu['comps']}
comps = []; i = [1]
def add(c): c['i'] = i[0]; i[0] += 1; comps.append(c); return c
add(rp.comp(rp.TITLE, n='t0', txt='Easy tuning'))
add(rp.comp(rp.CARD, n='card', x=isl['card'][0], y=isl['card'][1], w=isl['card'][2], h=isl['card'][3]))
add(rp.comp(mby['t14'], x=10, y=3, w=86, h=26, txt=''))      # (the menu's header: "Bank n" and "Rate n", the model's name under them)
add(rp.comp(mby['t8'], x=100, y=3, w=110, h=26, txt=''))
add(rp.comp(rp.MODEL, n='t11', txt='Model name'))
add(rp.comp(rp.VA0, n='va0'))
hb = rp.comp(rp.by['b0'], n='b0'); hb['ev'] = {'r': 'print "HelpView:%s"\nLogView.t0.txt="Easy tuning help"\nLogView.return.txt="%s"' % (HELP, NAME)}
add(hb)

def words(n, txt, x, y, w, h, xcen, font=FONT, maxl=30):   # white words on the card
    t = rp.comp(rp.LABEL_L, n=n, x=x, y=y, w=w, h=h, txt=txt, g='g', font=font)
    t['c'] = {'pco': 65535, 'borderc': CARD_BCO, 'bco': CARD_BCO}
    t['a'] = dict(t['a'], borderw=0, xcen=xcen, ycen=1, txt_maxl=maxl, key=255)
    return add(t)
def label(n, txt, x, y, w, shade):   # a pale label box, black words (one shade a group)
    l = rp.comp(rp.LABEL_L, n=n, x=x, y=y, w=w, h=ROW_H, txt=txt, g='g', font=FONT)
    l['c'] = dict(l['c'], pco=0, bco=rp.PALE[shade]); l['a'] = dict(l['a'], xcen=1, ycen=1, key=255)
    return add(l)
x0, y0 = isl['x0'], isl['y0']
xe1 = x0 + LW + GAP; xs = xe1 + EL + GAP; xe2 = xs + SW + GAP
for r, row in enumerate(ROWS):
    y = y0 + r * PITCH
    if row is None:   # the switch: PID spool-up in every bank (the phone's tick, on at first); B105: white words, no bar
        words('lP', SPOOL, x0, y, CONTENT_W - 80 - GAP, ROW_H, 0, maxl=60)
        add({'n': 'sw', 't': 'switch', 'g': 'g', 'x': x0 + CONTENT_W - 80, 'y': y + (ROW_H - 34) // 2, 'w': 80, 'h': 34, 'font': 0,
             'c': {'pco1': 0, 'bco2': 2016, 'pco': 65535, 'bco': 33808, 'pco2': 65535}, 'txt': ' / ', 'val': 1, 'a': {'dez': 0, 'dis': 100, 'txt_maxl': 24},
             'ev': {'r': 'va0.val=213<<8\nprint va0.val'}})
        continue
    ln, lt, shade, (el, et), sn, (er, rt), top, code = row
    label(ln, lt, x0, y, LW, shade)
    words(el, et, xe1, y, EL, ROW_H, 2)
    def word(lifted): return 'va0.val=%s.val+%d<<24+(%d<<8)\nprint va0.val' % (sn, 65 if lifted else 1, code)   # (left to right, as the Nextion counts)
    press = '\n'.join(['%s.bco=%d' % (n, rp.PALE[shade]) for n in LIVE] + ['%s.txt=""' % n for n in LIVE[1:]] + ['vis %s,1' % n for n in LIVE])
    lift = '\n'.join('vis %s,0' % n for n in reversed(LIVE))
    add({'n': sn, 't': 'slider', 'g': 'g', 'x': xs, 'y': y + (ROW_H - 32) // 2, 'w': SW, 'h': 32, 'sta': 1,
         'c': {'pco': 65535, 'bco': 33808, 'bco1': 65504}, 'val': top // 2,
         'a': {'mode': 0, 'psta': 0, 'wid': 255, 'hig': 255, 'dis': 100, 'maxval': top, 'minval': 0},
         'ev': {'p': press + '\n' + word(False), 'm': word(False), 'r': lift + '\n' + word(True)}})
    words(er, rt, xe2, y, ER, ROW_H, 0)
note = words('note', '', x0, y0 + len(ROWS) * PITCH - (PITCH - ROW_H) + 6, CONTENT_W, NOTE_H, 0, maxl=230)
note['a'] = dict(note['a'], ycen=0, isbr=1)
for (nm, txt, x, y, w, code) in isl['btn']:
    b = rp.comp(rp.BUTTON, n=nm, x=x, y=y, w=w, h=rp.C_BTN_H, txt=txt); b['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}; add(b)
# B105: the numbers box - over the space under the rows, the note and the buttons too (nothing there is wanted while a finger
# is on a slider), above them all but the message box; hidden until a slider is touched
def live(n, x, y, w, h):
    t = rp.comp(rp.LABEL_L, n=n, x=x, y=y, w=w, h=h, txt='', g='g', font=FONT)
    t['c'] = {'pco': 0, 'borderc': rp.PALE[0], 'bco': rp.PALE[0]}
    t['a'] = dict(t['a'], borderw=0, xcen=0, ycen=1, isbr=0, txt_maxl=80, key=255)
    return add(t)
ly0 = y0 + len(ROWS) * PITCH - (PITCH - ROW_H) + 6; ly1 = isl['btn'][0][3] + rp.C_BTN_H
live('lvb', x0, ly0, CONTENT_W, ly1 - ly0)
for j, n in enumerate(LIVE[1:]):
    live(n, x0 + LIVE_MX + (0 if j == 0 else LIVE_W0 + (j - 1) * LIVE_W), ly0 + LIVE_MY, LIVE_W0 if j == 0 else LIVE_W, ly1 - ly0 - 2 * LIVE_MY)
add(rp.message_box(rect=isl['box']))
out = {'name': NAME, 'id': PID, 'w': 800, 'h': 480, 'bg': rp.rates['bg'], 'nav': rp.rates['nav'],
       'ev': {'preinitialize': 'vis busy,0\n%s\n%s.pic=Screen_Background' % ('\n'.join('vis %s,0' % n for n in LIVE), NAME)}, 'comps': comps}
json.dump(out, open(os.path.join(rp.PAGES, '%d.json' % PID), 'w'), indent=1)
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
if PID not in {x['id'] for x in idx['pages']}: idx['pages'].append({'id': PID, 'name': NAME, 'n': len(comps)})
for x in idx['pages']:
    if x['id'] == PID: x['n'] = len(comps)
idx['pages'].sort(key=lambda x: x['id'])
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
print(PID, NAME, len(comps), 'components; card %dx%d at %d,%d; label %d, words %d / %d, slider %d px' % (isl['card'][2], isl['card'][3], isl['card'][0], isl['card'][1], LW, EL, ER, SW))
