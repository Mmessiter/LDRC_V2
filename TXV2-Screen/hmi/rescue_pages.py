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

# 1.11.40 (Malcolm, 9 Oct: "The groups of buttons should look tidy, centred, and lined up wherever possible"; 4 Oct: OK at
# the bottom right, as on every page): the bottom row sits in the system pages' four slots (x 14, 211, 408, 605, 180
# wide), the same on every page: OK always in the last, Save always just left of it, the page's other buttons in the
# slots to their left, side by side - no gaps, and Save and OK where the finger expects them. A label too wide for a slot
# takes two; five buttons share the width.
SLOT_X, SLOT_W, SLOT_PITCH = 14, 180, 197
def bottom_row(buttons, y=414, h=56, minw=180):
    """buttons: (name, words, code) -> (name, words, x, w, code), in the order they sit"""
    from fontw import width
    ok = [b for b in buttons if b[1] == 'OK']; save = [b for b in buttons if b[1] == 'Save']
    ordered = [b for b in buttons if b not in ok and b not in save] + save + ok
    need = [2 if width(6, t) + 16 > minw else 1 for _, t, _ in ordered]   # (8 px either side of the words, inside the bevel)
    if sum(need) > 4:   # (five or more: the width shared alike, centred)
        n = len(ordered); gap = 12; w = (772 - (n - 1) * gap) // n; x0 = (800 - (n * w + (n - 1) * gap)) // 2
        return [(nm, t, x0 + k * (w + gap), w, code) for k, (nm, t, code) in enumerate(ordered)]
    out, end = [], 4
    for (nm, t, code), k in reversed(list(zip(ordered, need))):
        start = end - k
        out.append((nm, t, SLOT_X + start * SLOT_PITCH, k * SLOT_W + (k - 1) * (SLOT_PITCH - SLOT_W), code)); end = start
    return list(reversed(out))

# 1.11.40 (Malcolm, 9 Oct: "Information and warning banners should look like message boxes rather than yellow text
# stripes"): the page's "busy" banner in the message box's own dress (the screen's text style 5: a dark ring, a white
# frame, the panel's colour, white words wrapped inside), over the middle of the page, last so it lies on top.
MSGBOX = (110, 168, 580, 124)
def message_box(name='busy', rect=MSGBOX, font=2):
    b = comp(BUSY, n=name, x=rect[0], y=rect[1], w=rect[2], h=rect[3], txt='', font=font)
    b['sta'] = 1; b['c'] = {'pco': 65535, 'borderc': 65535, 'bco': CARD['c']['bco']}
    b['a'] = dict(b.get('a', {}), style=5, borderw=0, xcen=1, ycen=1, isbr=1, txt_maxl=200)
    return b

# 1.11.34 (Malcolm, 8 Oct: "the red background colour chosen has insufficient contrast with the text ... very pale shades
# ... and black text ... the different colours should suggest the groupings"): a label's box is a pale shade, black words,
# one shade per group (each heading starts the next), the first shade for a page without headings.
PALE = (65497, 57215, 59323, 61215, 65402, 65341)   # pale yellow, blue, green, lavender, peach, pink (RGB565)
def page(pid, name, title, fields, buttons, help_file, busy_rect=MSGBOX):
    """fields: (name, label, column, row, kind, code[, keypad label]) with kind 'num' (the keypad), 'cycle' (a tap), 'switch' (on/off), 'info' (told, not changed),
    'head' (a group heading, no value) or 'pick' (1.11.35: a choice from a long list, the whole row: label, a < button, the choice, a > button;
    code = the > button's, the 7th element = the < button's)"""
    comps = []; i = [1]
    def add(c): c['i'] = i[0]; i[0] += 1; comps.append(c); return c
    add(comp(TITLE, n='t0', txt=title))
    add(comp(CARD, n='card'))
    add(comp(BANK, n='t9', txt='Bank 1'))
    add(comp(MODEL, n='t11', txt='Model name'))
    add(comp(VA0, n='va0'))
    help_btn = comp(by['b0'], n='b0'); help_btn['ev'] = {'r': 'print "HelpView:%s"\nLogView.t0.txt="%s"\nLogView.return.txt="%s"' % (help_file, title + ' help', name)}
    add(help_btn)
    group = -1
    def shade(): return PALE[max(group, 0) % len(PALE)]
    for field in fields:
        (nm, label, col, row, kind, code), klabel = field[:6], (field[6] if len(field) > 6 else field[1])   # klabel: what the keypad calls it (1.11.30)
        y = 94 + row * 40
        lx, lw, vx, vw = (34, 254, 294, 120) if col == 0 else (430, 236, 672, 94)
        if kind == 'head':   # 1.11.30: a group heading across the column, white on the card, as the configurator's sections (no value)
            group += 1
            h = comp(LABEL_L, n=nm, x=lx, y=y, w=lw + vw + (vx - lx - lw), h=36, txt=label, g='g', font=6)
            h['c'] = {'pco': 65535, 'borderc': CARD['c']['bco'], 'bco': CARD['c']['bco']}; h['a'] = dict(h['a'], borderw=0, xcen=0, txt_maxl=30)
            add(h); continue
        if kind == 'pick':   # 1.11.35: a choice from a long list (the adjustments' settings), across the page: label, <, the choice, >
            lab = comp(LABEL_L, n='l' + nm, x=34, y=y, w=150, h=36, txt=label, g='g'); lab['c'] = dict(lab['c'], pco=0, bco=shade()); add(lab)
            bp = comp(BUTTON, n='p' + nm, x=190, y=y - 2, w=50, h=40, txt='<'); bp['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % int(klabel)}; add(bp)
            f = comp(FIELD, n=nm, x=246, y=y, w=464, h=36, txt='', g='g'); f['a'] = dict(f['a'], key=255, txt_maxl=40); add(f)
            bn = comp(BUTTON, n='n' + nm, x=716, y=y - 2, w=50, h=40, txt='>'); bn['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}; add(bn)
            continue
        if kind == 'wide':   # 1.11.40: a value stepped by a tap whose words need room ("Whenever armed"): a shorter label, a wider box
            lw2, vx2, vw2 = (150, 190, 224) if col == 0 else (150, 586, 180)
            lab = comp(LABEL_L, n='l' + nm, x=lx, y=y, w=lw2, h=36, txt=label, g='g'); lab['c'] = dict(lab['c'], pco=0, bco=shade()); add(lab)
            f = comp(FIELD, n=nm, x=vx2, y=y, w=vw2, h=36, txt='', g='g'); f['a'] = dict(f['a'], key=255, txt_maxl=30); f['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}; add(f)
            continue
        if kind == 'info':   # 1.11.34: a row that only tells (the configurator's selects the transmitter does not change): label box across the column, the main board sets its text
            f = comp(LABEL_L, n=nm, x=lx, y=y, w=lw + vw + (vx - lx - lw), h=36, txt=label, g='g')
            f['c'] = dict(f['c'], pco=0, bco=shade()); f['a'] = dict(f['a'], txt_maxl=40); add(f); continue
        lab = comp(LABEL_L, n='l' + nm, x=lx, y=y, w=lw, h=36, txt=label, g='g')
        lab['c'] = dict(lab['c'], pco=0, bco=shade())
        add(lab)
        if kind == 'switch':   # 1.11.34 (Malcolm, 8 Oct: "the yes/no boxes should be switches"): the screen's own switch, grey off / green on, its val set by the main board
            sw = {'n': nm, 't': 'switch', 'g': 'g', 'x': vx + (vw - 80) // 2, 'y': y + 1, 'w': 80, 'h': 34, 'font': 0,
                  'c': {'pco1': 0, 'bco2': 2016, 'pco': 65535, 'bco': 33808, 'pco2': 65535}, 'txt': ' / ', 'val': 0, 'a': {'dez': 0, 'dis': 100, 'txt_maxl': 24},
                  'ev': {'r': 'va0.val=%d<<8\nprint va0.val' % code}}
            add(sw); continue
        f = comp(FIELD, n=nm, x=vx, y=y, w=vw, h=36, txt='0', g='g')
        if kind == 'num': f['ev'] = {'r': 'keybdB.t1.txt="%s"\nva0.val=%d<<8\nprint va0.val' % (klabel, code)}
        else: f['a'] = dict(f['a'], key=255); f['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}
        add(f)
    for (nm, txt, x, w, code) in bottom_row([(b[0], b[1], b[4]) for b in buttons]):   # (1.11.40: the x and w given are not used: the row is laid out by its rule)
        b = comp(BUTTON, n=nm, x=x, y=414, w=w, h=56, txt=txt); b['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}; add(b)
    add(message_box(rect=busy_rect))   # (vis 0 the rest of the time; 1.11.22's yellow stripe became a message box in 1.11.40)
    out = {'name': name, 'id': pid, 'w': 800, 'h': 480, 'bg': rates['bg'], 'nav': rates['nav'], 'ev': {'preinitialize': 'vis busy,0\n%s.pic=Screen_Background' % name}, 'comps': comps}
    json.dump(out, open(os.path.join(PAGES, '%d.json' % pid), 'w'), indent=1)
    print(pid, name, len(comps), 'components')

# codes (the main board's NumberedFunctions1): 64 open, 65 OK, 66 save, 67 a number edited, 68 the mode tapped, 69 flip tapped, 70 page 2, 71 back to page 1
page(58, 'RescueView', 'Rescue (Rotorflight)', [          # the configurator's names, order and units (Malcolm, 7 Oct: "use the same names in the same places")
    ('tn0', 'Enable Rescue', 0, 0, 'switch', 68), ('tn1', 'Flip to upright', 0, 1, 'switch', 69),
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
