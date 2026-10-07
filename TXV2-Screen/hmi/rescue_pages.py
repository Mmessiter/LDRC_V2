#!/usr/bin/env python3
"""The Rescue pages of the transmitter (screen 1.11.19, B50): sd/hmi/pages/58.json (RescueView) and 59.json
(Rescue2View), in the style of the Rates page (1.json), and the "Rescue ..." button on the Rotorflight menu (8.json).
Re-run after a change here: python3 hmi/rescue_pages.py"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); PAGES = os.path.join(HERE, '..', 'sd', 'hmi', 'pages')
rates = json.load(open(os.path.join(PAGES, '1.json')))
by = {c['n']: c for c in rates['comps']}
TITLE, CARD, LABEL_L, LABEL_R, BUTTON, FIELD, BANK, MODEL, VA0, BUSY = (by[n] for n in ('t0', 'card', 't1', 't5', 'b1', 'tn0', 't9', 't11', 'va0', 'busy'))

def comp(proto, **kw):
    c = json.loads(json.dumps(proto)); c.update(kw); return c

def page(pid, name, title, fields, buttons, help_file):
    """fields: (name, label, column, row, kind) with kind 'num' (the keypad) or 'cycle' (a tap, code)"""
    comps = []; i = [1]
    def add(c): c['i'] = i[0]; i[0] += 1; comps.append(c); return c
    add(comp(TITLE, n='t0', txt=title))
    add(comp(CARD, n='card'))
    add(comp(BANK, n='t9', txt='Bank 1'))
    add(comp(MODEL, n='t11', txt='Model name'))
    add(comp(VA0, n='va0'))
    help_btn = comp(by['b0'], n='b0'); help_btn['ev'] = {'r': 'print "HelpView:%s"\nLogView.t0.txt="%s"\nLogView.return.txt="%s"' % (help_file, title + ' help', name)}
    add(help_btn)
    for (nm, label, col, row, kind, code) in fields:
        y = 94 + row * 40
        lx, lw, vx, vw = (34, 254, 294, 120) if col == 0 else (430, 236, 672, 94)
        add(comp(LABEL_L if col == 0 else LABEL_R, n='l' + nm, x=lx, y=y, w=lw, h=36, txt=label, g='g'))
        f = comp(FIELD, n=nm, x=vx, y=y, w=vw, h=36, txt='0', g='g')
        if kind == 'num': f['ev'] = {'r': 'keybdB.t1.txt="%s"\nva0.val=%d<<8\nprint va0.val' % (label, code)}
        else: f['a'] = dict(f['a'], key=255); f['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}
        add(f)
    for (nm, txt, x, w, code) in buttons:
        b = comp(BUTTON, n=nm, x=x, y=414, w=w, h=56, txt=txt); b['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}; add(b)
    b = comp(BUSY, n='busy', x=40, y=296, w=720, h=44, txt='', font=2)   # over rows 5-6 while it shows (vis 0 the rest of the time)
    b['c'] = {'pco': 0, 'borderc': 0, 'bco': 65504}; b['a'] = dict(b['a'], borderw=2)   # 1.11.22 (Malcolm: "more obviously a banner and a bit brighter, perhaps with a border"): yellow, black words (a flat text's border does not draw: the colour does the work)
    add(b)
    out = {'name': name, 'id': pid, 'w': 800, 'h': 480, 'bg': rates['bg'], 'nav': rates['nav'], 'ev': {'preinitialize': 'vis busy,0\n%s.pic=Screen_Background' % name}, 'comps': comps}
    json.dump(out, open(os.path.join(PAGES, '%d.json' % pid), 'w'), indent=1)
    print(pid, name, len(comps), 'components')

# codes (the main board's NumberedFunctions1): 64 open, 65 OK, 66 save, 67 a number edited, 68 the mode tapped, 69 flip tapped, 70 page 2, 71 back to page 1
page(58, 'RescueView', 'Rescue (Rotorflight)', [          # the configurator's names, order and units (Malcolm, 7 Oct: "use the same names in the same places")
    ('tn0', 'Enable Rescue', 0, 0, 'cycle', 68), ('tn1', 'Flip to upright', 0, 1, 'cycle', 69),
    ('tn2', 'Pull-up Collective [%]', 0, 2, 'num', 67), ('tn3', 'Pull-up Time [s]', 0, 3, 'num', 67),
    ('tn4', 'Climb Collective [%]', 0, 4, 'num', 67), ('tn5', 'Climb Time [s]', 0, 5, 'num', 67),
    ('tn6', 'Hover Collective [%]', 0, 6, 'num', 67), ('tn7', 'Flip Fail Time [s]', 0, 7, 'num', 67),
    ('tn8', 'Exit Time [s]', 1, 0, 'num', 67), ('tn9', 'Leveling Gain', 1, 1, 'num', 67),
    ('tn10', 'Flip-to-Upright Gain', 1, 2, 'num', 67), ('tn11', 'Max Levelling Rate', 1, 3, 'num', 67),
    ('tn12', 'Max Leveling Accel.', 1, 4, 'num', 67),
], [('b3', 'Save', 14, 180, 66), ('b2', 'Next >', 408, 180, 70), ('b1', 'OK', 605, 180, 65)], 'RESCUE.TXT')   # 1.11.22: Next / Previous between the two pages (Malcolm)
page(59, 'Rescue2View', 'Rescue: height hold', [
    ('tn0', 'Rescue mode', 0, 0, 'cycle', 72), ('tn1', 'Hover height [m]', 0, 1, 'num', 67),
    ('tn2', 'Height hold P', 0, 2, 'num', 67), ('tn3', 'Height hold I', 0, 3, 'num', 67),
    ('tn4', 'Height hold D', 0, 4, 'num', 67), ('tn5', 'Max Collective [%]', 0, 5, 'num', 67),
], [('b3', 'Save', 14, 180, 66), ('b2', '< Previous', 408, 180, 71), ('b1', 'OK', 605, 180, 65)], 'RESCUE2.TXT')

# (the Rotorflight menu itself is made by hmi/rfmenu_pages.py since 1.11.26)
idx = json.load(open(os.path.join(PAGES, '..', 'index.json')))
have = {x['id'] for x in idx['pages']}
for pid, name, n in ((58, 'RescueView', 38), (59, 'Rescue2View', 17)):
    if pid not in have: idx['pages'].append({'id': pid, 'name': name, 'n': n})
idx['pages'].sort(key=lambda x: x['id'])
json.dump(idx, open(os.path.join(PAGES, '..', 'index.json'), 'w'), indent=1)
