#!/usr/bin/env python3
"""ELRS settings (Malcolm, 14 Nov 2026: "should we not perhaps finish our configuration of ELRS because I think there is
more to be done"): page 90 ElrsView and its picker, page 91 ElrsPickView - the ExpressLRS module's own settings from the
transmitter's screen, where other radios need the module's Lua script: how often the sticks are sent (packet rate), how
much of the air time is the model's replies (telemetry ratio), how the channels after the fourth are carried (switch
mode), and the most power. The main board's side is TXV1B include/ElrsCrsf.h (test builds only for now; codes 261-268):
it writes each row's value as the module says it, a row tapped opens the picker with the choices the module offers, and
the one line under the rows says what stands in the way of a change, if anything does.
Also Model options (page 9): the button 'ELRS ...' in the bottom row's second place, HIDDEN BY THE PAGE ITSELF
(its start-up line vis bElrs,0) and shown only by a main board that has the code, for a model set to ELRS.
The parts are copies of pages 67 and 68's (the island, the pale labels, the tap boxes, the wheel), so the two new pages
look as those do. No Help button yet: the main board's way back from Help keeps a page only below view 90.
Safe to run again. Run from the project: python3 hmi/elrs_pages.py"""
import copy, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, '..', 'sd', 'hmi', 'pages')
INDEX = os.path.join(HERE, '..', 'sd', 'hmi', 'index.json')
VIEW, PICK = (90, 'ElrsView'), (91, 'ElrsPickView')
ROWS = ['Stick updates a second (packet rate)', 'Telemetry share (telem ratio)', 'Channel detail (switch mode)', 'Most power (max power)']
CODE_OPEN, CODE_OK, CODE_ROW0, CODE_PICK_OK, CODE_PICK_CANCEL = 261, 262, 263, 267, 268


def load(i, folder=PAGES):
    return json.load(open(os.path.join(folder, '%d.json' % i)))


def code(n):
    return {'r': 'va0.val=%d<<8\nprint va0.val' % n}


adj, pick = load(67), load(68)
A = {c['n']: c for c in adj['comps']}
P = {c['n']: c for c in pick['comps']}


def page(pid, name, comps):
    out = {'name': name, 'id': pid, 'w': 800, 'h': 480, 'bg': adj['bg'], 'nav': adj['nav'], 'ev': {'preinitialize': '%s.pic=Screen_Background' % name}, 'comps': comps}
    json.dump(out, open(os.path.join(PAGES, '%d.json' % pid), 'w'), indent=1)
    return len(comps)


def adder(comps):
    def add(c, **kw):
        c = copy.deepcopy(c); c.update(kw); c['i'] = len(comps) + 1; comps.append(c); return c
    return add


# ---- page 90: the four rows on an island, the line under them, OK at the bottom right
PAD, ROW_H, PITCH, LABEL_W, GAP, VALUE_W, HINT_H, BTN_ABOVE, BTN_W, BTN_H = 16, 36, 46, 372, 8, 260, 30, 14, 160, 50
W = LABEL_W + GAP + VALUE_W
content_h = 3 * PITCH + ROW_H + 10 + HINT_H
card_w, card_h = W + 2 * PAD, PAD + content_h + BTN_ABOVE + BTN_H + PAD
card_x, card_y = (800 - card_w) // 2, 58 + (422 - card_h) // 2
X, Y = card_x + PAD, card_y + PAD
comps = []; add = adder(comps)
add(A['t0'], txt='ELRS settings')
add(A['card'], x=card_x, y=card_y, w=card_w, h=card_h)
t9 = add(A['t9'], txt='ELRS module'); t9['a'] = dict(t9['a'], txt_maxl=30)
add(A['t11'], w=200)
add(A['va0'])
for k, words in enumerate(ROWS):
    lab = add(A['ltn0'], n='ltn%d' % k, x=X, y=Y + k * PITCH, w=LABEL_W, h=ROW_H, txt=words); lab['a'] = dict(lab['a'], txt_maxl=40)
    lab['ev'] = {'p': 'click tn%d,1\nclick tn%d,0' % (k, k)}                       # (the label is the row too: a tap on it is a tap on its value)
    val = add(A['tn0'], n='tn%d' % k, x=X + LABEL_W + GAP, y=Y + k * PITCH, w=VALUE_W, h=ROW_H, txt=''); val['a'] = dict(val['a'], txt_maxl=40)
    val['ev'] = code(CODE_ROW0 + k)
hint = add(A['hint'], x=X, y=Y + 3 * PITCH + ROW_H + 10, w=W, h=HINT_H, txt=''); hint['a'] = dict(hint['a'], txt_maxl=70)
ok = add(A['b1'], x=card_x + card_w - PAD - BTN_W, y=card_y + card_h - PAD - BTN_H, w=BTN_W, h=BTN_H, txt='OK'); ok['ev'] = code(CODE_OK)
n_view = page(VIEW[0], VIEW[1], comps)

# ---- page 91: the picker - a wheel of the setting's choices (the main board writes them: list.path), Cancel and OK
comps = []; add = adder(comps)
t0 = add(P['t0'], txt='ELRS setting')
add(P['card'])
t9 = add(P['t9'], txt='ELRS module'); t9['a'] = dict(t9['a'], txt_maxl=30)
add(P['t11'])
add(P['va0'])
wheel = add(P['list'], txt='', val=0); wheel['opt'] = []; wheel['ev'] = {}
c = add(P['b1'], txt='Cancel'); c['ev'] = code(CODE_PICK_CANCEL)
o = add(P['b3'], txt='OK'); o['ev'] = code(CODE_PICK_OK)
n_pick = page(PICK[0], PICK[1], comps)

# ---- Model options (page 9): 'ELRS settings ...' in the bottom row's second place, hidden by the page itself. On the card
# (compact, the style laid over it) and in hmi/originals (what pagestyle verifies against), the same part.
for folder, compact in ((PAGES, True), (os.path.join(HERE, 'originals'), False)):
    path = os.path.join(folder, '9.json')
    pg = json.load(open(path))
    by = {c['n']: c for c in pg['comps']}
    added = 'bElrs' not in by
    if not added: by['bElrs']['txt'] = 'ELRS ...'   # ('ELRS settings ...' is 189 px in font 6: the button has 176)
    if added:
        nb = copy.deepcopy(by['b0']); nb.update(n='bElrs', i=max(c['i'] for c in pg['comps']) + 1, txt='ELRS ...', ev=code(CODE_OPEN))
        nb['x'] = by['b0']['x'] + (by['b2']['x'] - by['b0']['x']) // 3 if compact else by['b0']['x'] + by['b0']['w'] + 17
        pg['comps'].insert(pg['comps'].index(by['b0']) + 1, nb)
    pre = pg['ev'].get('preinitialize', '')
    if 'vis bElrs,0' not in pre: pg['ev']['preinitialize'] = (pre + '\n' if pre else '') + 'vis bElrs,0'
    json.dump(pg, open(path, 'w'), separators=(',', ':') if compact else None, indent=None if compact else 1)
    if compact: nine_added = added; slot = next(c for c in pg['comps'] if c['n'] == 'bElrs')

# ---- index.json: the two pages, and page 9's count
ix = json.load(open(INDEX))
have = {p['id']: p for p in ix['pages']}
for (pid, name), n in ((VIEW, n_view), (PICK, n_pick)):
    if pid in have: have[pid].update(name=name, n=n)
    else: ix['pages'].append({'id': pid, 'name': name, 'n': n})
have[9]['n'] += 1 if nine_added else 0   # (the count there is kept by hand, as hmi/beeper_pages.py keeps page 8's: one more for the part added)
ix['pages'].sort(key=lambda p: p['id'])
json.dump(ix, open(INDEX, 'w'), indent=1)
print('page %d %s: %d parts, island %dx%d at %d,%d; page %d %s: %d parts; page 9: count %d in the index, the button at x %d y %d w %d; index %d pages'
      % (VIEW[0], VIEW[1], n_view, card_w, card_h, card_x, card_y, PICK[0], PICK[1], n_pick, have[9]['n'], slot['x'], slot['y'], slot['w'], len(ix['pages'])))
