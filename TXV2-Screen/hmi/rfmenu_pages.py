#!/usr/bin/env python3
"""The Rotorflight menu (sd/hmi/pages/8.json, RFView) and its settings page (61.json, RFSetupView): screen 1.11.26, B56.
Malcolm, 7 Oct: "The backup and restore option should be at the bottom ... I suspect this screen will become a bit
overcrowded" - so the four settings (link rates and banks, version, arming channel, main RPM ratio) go to a page of
their own, and the menu is a grid of up to nine buttons. The main board addresses components by NAME: the menu keeps
t0, card, b0 (Help), t11 (model name), va0, b4 (OK), Progress, t14 (bank), t8 (rate), pipe; the settings page keeps
t3/sw0, t4/t5, t6/Arming, t1/Ratio with their events. Re-run after a change here: python3 hmi/rfmenu_pages.py"""
import json, os, copy
HERE = os.path.dirname(os.path.abspath(__file__)); PAGES = os.path.join(HERE, '..', 'sd', 'hmi', 'pages')
menu = json.load(open(os.path.join(PAGES, '8.json')))
by = {c['n']: c for c in menu['comps']}
if os.path.exists(os.path.join(PAGES, '61.json')):          # the settings' components live on the settings page once it exists
    for c in json.load(open(os.path.join(PAGES, '61.json')))['comps']: by.setdefault(c['n'], c)
def comp(proto, **kw):
    c = copy.deepcopy(proto); c.update(kw); return c

# 1.11.40 (Malcolm, 9 Oct: "look critically at the UI design of all our new pages ... groups of buttons tidy, centred, and
# lined up"): the header as on the other Rotorflight pages (bank and rate on its first line, the model's name under them),
# the settings as label boxes and values in the Rescue pages' rows, the buttons by the shared row rule.
import rescue_pages as rp
def header(lst):
    add(lst, comp(by['t14'], x=10, y=3, w=86, h=26))
    add(lst, comp(by['t8'], x=100, y=3, w=110, h=26))
    m = comp(rp.MODEL, n='t11', txt='Model name'); add(lst, m)

# ---- the settings page, from the menu's own components
settings = []; i = [1]
def add(lst, c): c['i'] = i[0]; i[0] += 1; lst.append(c); return c
add(settings, comp(by['t0'], txt='Rotorflight settings'))
ROWS = (('t3', 'sw0', 'Link rates and banks', None), ('t4', 't5', 'Rotorflight version', None), ('t6', 'Arming', 'Arming channel', 'Arming channel'), ('t1', 'Ratio', 'Main RPM ratio', 'Rotor to motor RPM ratio'))
# B90: four rows lay out compact (rescue_pages.compact_plan): a card their size, centred on the background picture, the rows in the larger font
plan = rp.compact_plan([(lab, words, 0, r, 'switch' if val == 'sw0' else 'num', 0) for r, (lab, val, words, klabel) in enumerate(ROWS)], [('b4', 'OK', 82)])
add(settings, comp(by['card'], x=plan['card'][0], y=plan['card'][1], w=plan['card'][2], h=plan['card'][3]))
header(settings)
add(settings, comp(by['va0']))
h = comp(by['b0']); h['ev'] = {'r': 'print "HelpView:RFSETUP.TXT"\nLogView.t0.txt="Rotorflight settings help"\nLogView.return.txt="RFSetupView"'}; add(settings, h)
lx, cw = plan['col'][0]; VW, RH, FT = plan['val_w'], plan['row_h'], plan['font']; lw = cw - rp.C_LVGAP - VW; vx = lx + lw + rp.C_LVGAP
for r, (lab, val, words, klabel) in enumerate(ROWS):
    y = plan['y'](r)
    l = comp(by[lab], x=lx, y=y, w=lw, h=RH, txt=words, font=FT); l['c'] = dict(l['c'], pco=0, bco=rp.PALE[0]); l['a'] = dict(l['a'], xcen=1, ycen=1); add(settings, l)
    v = by[val]
    if v['t'] == 'switch': v = comp(v, x=vx + (VW - 80) // 2, y=y + (RH - 34) // 2, w=80, h=34)
    else:
        v = comp(v, x=vx, y=y, w=VW, h=RH, font=FT)
        if klabel: v['ev'] = {'p': 'keybdB.t1.txt="%s"' % klabel}   # (the arming channel's keypad was titled "Rotor to motor RPM ratio")
    add(settings, v)
for nm, txt, x, y, w, code in plan['btn']:
    ok = comp(by['b4'], x=x, y=y, w=w, h=rp.C_BTN_H); ok['ev'] = {'r': 'va0.val=82<<8\nprint va0.val'}; add(settings, ok)
page61 = {'name': 'RFSetupView', 'id': 61, 'w': 800, 'h': 480, 'bg': menu['bg'], 'nav': menu['nav'], 'ev': {'preinitialize': 'RFSetupView.pic=Screen_Background'}, 'comps': settings}
json.dump(page61, open(os.path.join(PAGES, '61.json'), 'w'), indent=1)

# ---- the menu: a grid of buttons, three by five, the arming line under it (B88)
i = [1]; comps = []
add(comps, comp(by['t0']))
# B91: the menu on an island - the grid 232 wide a button (the arming line's longest words, 705 px, fit under it), 44 high,
# the arming line under it, the Bluetooth word against OK at the foot
BW, BH, GX, GY = 232, 44, 8, 6
GRID_W = 3 * BW + 2 * GX
isl = rp.island(GRID_W, 5 * BH + 4 * GY + 8 + 40, [('b4', 'OK', 0)])
add(comps, comp(by['card'], x=isl['card'][0], y=isl['card'][1], w=isl['card'][2], h=isl['card'][3]))
add(comps, comp(by['b0']))
header(comps)
add(comps, comp(by['va0']))
BUTTONS = [  # (name, words, code) in the order they sit, three to a row: the pages with values to edit first, the settings last
    ('Pid', 'PIDs ...', 18), ('b1', 'Rates ...', 22), ('b2', 'Governor ...', 50),
    ('Rescue', 'Rescue ...', 64), ('Servos', 'Servos ...', 73), ('Travel', 'Mixer ...', 83),
    ('Filters', 'Filters ...', 92), ('Adjust', 'Adjustments ...', 116), ('Switches', 'Switches ...', 133),
    ('CopyBank', 'Copy a bank ...', 145), ('Battery', 'Battery ...', 155), ('Blackbox', 'Black box ...', 161),
    ('Calibrate', 'Calibrate ...', 170), ('Setup', 'Settings ...', 81), ('Cli', 'Command line ...', 'ldrc cli'),
]   # (screen 1.11.42, Malcolm 10 Oct: "Command line" in the grid - the screen's own page, the word never reaches the main
    # board; Backup / Restore at the island's foot, far left, opposite OK)
proto = by['Pid']
for k, (name, words, code) in enumerate(BUTTONS):
    b = comp(proto, n=name, x=isl['x0'] + (BW + GX) * (k % 3), y=isl['y0'] + (BH + GY) * (k // 3), w=BW, h=BH, txt=words)
    b['ev'] = {'r': code} if isinstance(code, str) else {'r': 'va0.val=%d<<8\nprint va0.val' % code}
    add(comps, b)
# B88 "why it will not arm": the flight controller's arming blocks in plain words, a tap for all of them (code 175)
arm = comp(rp.LABEL_L, n='arm', x=isl['x0'], y=isl['y0'] + 5 * BH + 4 * GY + 8, w=GRID_W, h=40, txt='', g='g', font=6)   # (the longest, "Will not arm: Arm switch on too soon: off, then on (and 9 more)", is 705 px)
arm['c'] = {'pco': 65535, 'borderc': rp.CARD['c']['bco'], 'bco': rp.CARD['c']['bco']}; arm['a'] = dict(arm['a'], borderw=0, xcen=0, ycen=1, txt_maxl=90, key=255)
arm['ev'] = {'r': 'va0.val=175<<8\nprint va0.val'}
add(comps, arm)
okx = isl['btn'][0][2]
bk = comp(proto, n='b3', x=isl['card'][0] + rp.C_PAD, y=isl['foot_y'], w=240, h=rp.C_BTN_H, txt='Backup / Restore ...'); bk['ev'] = {'r': 'va0.val=48<<8\nprint va0.val'}   # (far left of the foot)
add(comps, bk)
pw = comp(by['pipe'], x=bk['x'] + bk['w'] + rp.C_BTN_GAP, y=isl['foot_y'], w=okx - rp.C_BTN_GAP - (bk['x'] + bk['w'] + rp.C_BTN_GAP), h=rp.C_BTN_H, font=2); pw['a'] = dict(pw['a'], xcen=2)   # (the Bluetooth word or its tooth, against OK, which keeps the bottom right)
add(comps, pw)
add(comps, comp(by['Progress'], x=isl['card'][0] + rp.C_PAD, y=isl['foot_y'] - 10, w=isl['card'][2] - 2 * rp.C_PAD, h=5))
for nm, txt, x, y, w, code in isl['btn']:
    add(comps, comp(by['b4'], x=x, y=y, w=w, h=rp.C_BTN_H))
menu['comps'] = comps
json.dump(menu, open(os.path.join(PAGES, '8.json'), 'w'), indent=1)
idx = json.load(open(os.path.join(PAGES, '..', 'index.json')))
have = {x['id'] for x in idx['pages']}
if 61 not in have: idx['pages'].append({'id': 61, 'name': 'RFSetupView', 'n': len(settings)})
for x in idx['pages']:
    if x['id'] == 8: x['n'] = len(comps)
idx['pages'].sort(key=lambda x: x['id'])
json.dump(idx, open(os.path.join(PAGES, '..', 'index.json'), 'w'), indent=1)
print('8 RFView:', len(comps), 'components;', '61 RFSetupView:', len(settings))
