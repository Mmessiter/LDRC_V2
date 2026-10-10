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

# B90 (Malcolm, 9 Oct, of Battery, Rotorflight settings and Calibrate: "These three screens would look better if the
# boxes were more central on the screen. They could perhaps afford to be a little larger. Also, because so much of the
# screen remains bare, we should perhaps consider using the background image instead of a plain background colour ...
# true for all screens with very little on them"): a page laid out COMPACT - each column as wide as its words need, on a
# card no bigger than they need, centred under the title strip on the pilot's background picture, the buttons along the
# card's foot with OK at its right. A field's 7th element, for an 'info' or 'wide' row, is the longest text the main
# board will put in it (the column is made wide enough).
# B91 (Malcolm, 9 Oct, of B90: "It's fabulous! I especially like a centered island of solid background colour with
# buttons contained within, surrounded by the background image. This idea could be implemented on more screens maybe by
# making buttons a little smaller to make the island smaller. This would give it a greater sense of unity."): EVERY page
# made here is an island now, in the largest of four sizes of row that fits with at least ISLAND_MX / ISLAND_MY of
# picture round it (the few rows of B90's pages in 28 px; eight rows in 24 px, as before); the buttons 160 x 50 (they
# were 180 x 56); pages in a series (Next / < Previous) share one size of island and row, so their buttons stand in the
# same places (series_begin / series_end). The same measures as hmi/islands.py, which does the Version 1 pages.
TIERS = [(6, 42, 50, 110, 160), (6, 40, 46, 110, 160), (2, 36, 40, 100, 150), (2, 35, 37, 100, 150)]   # font, row, pitch, value box, short label of a 'wide' row
C_FONT, C_ROW, C_PITCH, C_VAL_W, C_WIDE_L = TIERS[0]
C_PAD, C_COLGAP, C_LVGAP = 16, 20, 6
C_BTN_W, C_BTN_H, C_BTN_GAP, C_BTN_ABOVE = 160, 50, 12, 14
ISLAND_MX, ISLAND_MY = 24, 16
STRETCH = 60   # (a column is made at most this much wider than its words need)
def compact_plan(fields, buttons, tier=None, min_size=None):
    """fields as page() takes them; buttons: (name, words, code). None when no size of row lets the page be an island,
    else a dict: card (x, y, w, h), col[(lx, cw)], y(row), btn[(name, words, x, y, w, code)], box (the message box),
    font, row_h, val_w, wide_l, tier."""
    from fontw import width
    if any(f[4] == 'pick' for f in fields): return None
    rows = max((f[3] for f in fields), default=-1) + 1
    for t in ([tier] if tier is not None else range(len(TIERS))):
        font, row_h, pitch, val_w, wide_l = TIERS[t]
        # (B91, Malcolm of the Black box page: "The answer to the 'when' is so abbreviated, it's difficult to understand ... perhaps
        # by making the relative sizes of the boxes different"): a 'wide' row's label is no wider than its words need, so its box
        # has the room - and each 'wide' row names (7th element) the longest words the main board puts in it
        wide_l = min(wide_l, max((width(font, f[1]) + 20 for f in fields if f[4] == 'wide'), default=wide_l))
        cols = [0, 0]; minc = 300 if font == 6 else 260
        for f in fields:
            nm, label, col, row, kind = f[:5]; hint = f[6] if len(f) > 6 else None
            if kind == 'head': need = width(6, label) + 8
            elif kind == 'info': need = width(font, hint or label) + 24
            elif kind == 'wide': need = wide_l + C_LVGAP + width(font, hint or '') + 24
            else: need = width(font, label) + 20 + C_LVGAP + val_w
            cols[col] = max(cols[col], need, minc if kind != 'head' else 0)
        ncol = 2 if cols[1] else 1
        content_w = cols[0] + (C_COLGAP + cols[1] if ncol == 2 else 0)
        bw = [2 * C_BTN_W + C_BTN_GAP if width(6, tx) + 16 > C_BTN_W else C_BTN_W for _, tx, _ in buttons]
        btn_w = sum(bw) + (len(bw) - 1) * C_BTN_GAP if bw else 0
        card_w = 2 * C_PAD + max(content_w, btn_w)
        card_h = C_PAD + rows * pitch - (pitch - row_h) + C_BTN_ABOVE + C_BTN_H + C_PAD
        if card_w > 800 - 2 * ISLAND_MX or card_h > 422 - 2 * ISLAND_MY:
            if tier is not None: return None
            continue
        if min_size: card_w, card_h = max(card_w, min_size[0]), max(card_h, min_size[1])
        card_x, card_y = (800 - card_w) // 2, 58 + (422 - card_h) // 2
        inner = card_w - 2 * C_PAD; off = 0
        if content_w < inner:   # (the buttons, or the series, are the wider: the columns share some of the room, up to STRETCH each, and stand in the middle of the rest)
            extra = inner - content_w; per = min(STRETCH, extra // ncol)
            cols[0] += per; cols[1] += per if ncol == 2 else 0
            off = (extra - per * ncol) // 2
        col = [(card_x + C_PAD + off, cols[0]), (card_x + C_PAD + off + cols[0] + C_COLGAP, cols[1])]
        ok = [b for b in buttons if b[1] == 'OK']; save = [b for b in buttons if b[1] == 'Save']
        ordered = [b for b in buttons if b not in ok and b not in save] + save + ok
        by = card_y + card_h - C_PAD - C_BTN_H; x_end = card_x + card_w - C_PAD; btn = []
        for (nm, tx, code), w in reversed(list(zip(ordered, [bw[buttons.index(b)] for b in ordered]))):
            btn.append((nm, tx, x_end - w, by, w, code)); x_end -= w + C_BTN_GAP
        bwid = min(580, card_w - 20)
        return {'card': (card_x, card_y, card_w, card_h), 'col': col, 'y': (lambda row, y0=card_y + C_PAD, p=pitch: y0 + row * p),
                'btn': list(reversed(btn)), 'box': (card_x + (card_w - bwid) // 2, card_y + (card_h - 124) // 2, bwid, 124),
                'font': font, 'row_h': row_h, 'val_w': val_w, 'wide_l': wide_l, 'tier': t, 'size': (card_w, card_h)}
    return None

def island(content_w, content_h, buttons, min_size=None):
    """For a page laid out by hand (the menu, the bars, the lists): the island round content_w x content_h and its bottom
    row of buttons [(name, words, code)] (OK last, Save beside it) - a dict: card (x, y, w, h), x0 / y0 (where the content
    starts), btn [(name, words, x, y, w, code)], foot_y, box (the message box), size."""
    from fontw import width
    bw = [2 * C_BTN_W + C_BTN_GAP if width(6, tx) + 16 > C_BTN_W else C_BTN_W for _, tx, _ in buttons]
    row = sum(bw) + (len(bw) - 1) * C_BTN_GAP if bw else 0
    card_w = 2 * C_PAD + max(content_w, row)
    card_h = C_PAD + content_h + (C_BTN_ABOVE + C_BTN_H if buttons else 0) + C_PAD
    if min_size: card_w, card_h = max(card_w, min_size[0]), max(card_h, min_size[1])
    assert card_w <= 800 - 2 * ISLAND_MX and card_h <= 422 - 2 * ISLAND_MY, 'no island fits: %dx%d' % (card_w, card_h)
    card_x, card_y = (800 - card_w) // 2, 58 + (422 - card_h) // 2
    ok = [b for b in buttons if b[1] == 'OK']; save = [b for b in buttons if b[1] == 'Save']
    ordered = [b for b in buttons if b not in ok and b not in save] + save + ok
    by = card_y + card_h - C_PAD - C_BTN_H; x_end = card_x + card_w - C_PAD; btn = []
    for (nm, tx, code), w in reversed(list(zip(ordered, [bw[buttons.index(b)] for b in ordered]))):
        btn.append((nm, tx, x_end - w, by, w, code)); x_end -= w + C_BTN_GAP
    bwid = min(580, card_w - 20)
    return {'card': (card_x, card_y, card_w, card_h), 'x0': card_x + (card_w - content_w) // 2, 'y0': card_y + C_PAD, 'btn': list(reversed(btn)),
            'foot_y': by, 'box': (card_x + (card_w - bwid) // 2, card_y + (card_h - 124) // 2, bwid, 124), 'size': (card_w, card_h)}

_series = None
def series_begin():
    """The pages made until series_end() are one series: one size of row, one size of island."""
    global _series; _series = []
def series_end():
    global _series
    pending, _series = _series, None
    plans = [compact_plan(a[3], [(b[0], b[1], b[4]) for b in a[4]]) for a, k in pending]
    if any(p is None for p in plans):
        for a, k in pending: page(*a, **k)
        return
    tier = max(p['tier'] for p in plans)
    sized = [compact_plan(a[3], [(b[0], b[1], b[4]) for b in a[4]], tier=tier) for a, k in pending]
    if any(p is None for p in sized):
        for a, k in pending: page(*a, **k)
        return
    size = (max(p['size'][0] for p in sized), max(p['size'][1] for p in sized))
    for a, k in pending: page(*a, **dict(k, tier=tier, min_size=size))

def page(pid, name, title, fields, buttons, help_file, busy_rect=MSGBOX, compact=None, tier=None, min_size=None):
    """fields: (name, label, column, row, kind, code[, keypad label]) with kind 'num' (the keypad), 'cycle' (a tap), 'switch' (on/off), 'info' (told, not changed),
    'head' (a group heading, no value) or 'pick' (1.11.35: a choice from a long list, the whole row: label, a < button, the choice, a > button;
    code = the > button's, the 7th element = the < button's)"""
    if _series is not None:
        _series.append(((pid, name, title, fields, buttons, help_file), dict(busy_rect=busy_rect, compact=compact))); return
    comps = []; i = [1]
    def add(c): c['i'] = i[0]; i[0] += 1; comps.append(c); return c
    add(comp(TITLE, n='t0', txt=title))
    add(comp(CARD, n='card'))
    add(comp(BANK, n='t9', txt='Bank 1'))
    add(comp(MODEL, n='t11', txt='Model name'))
    add(comp(VA0, n='va0'))
    help_btn = comp(by['b0'], n='b0'); help_btn['ev'] = {'r': 'print "HelpView:%s"\nLogView.t0.txt="%s"\nLogView.return.txt="%s"' % (help_file, title + ' help', name)}
    add(help_btn)
    plan = compact_plan(fields, [(b[0], b[1], b[4]) for b in buttons], tier=tier, min_size=min_size) if compact is not False else None   # (None: no island fits)
    if plan:
        comps[1].update(x=plan['card'][0], y=plan['card'][1], w=plan['card'][2], h=plan['card'][3])
        busy_rect = plan['box']
    FONT, ROW_H = (plan['font'], plan['row_h']) if plan else (2, 36)
    VAL_W, WIDE_L = (plan['val_w'], plan['wide_l']) if plan else (C_VAL_W, C_WIDE_L)
    group = -1
    def shade(): return PALE[max(group, 0) % len(PALE)]
    for field in fields:
        (nm, label, col, row, kind, code), klabel = field[:6], (field[6] if len(field) > 6 else field[1])   # klabel: what the keypad calls it (1.11.30)
        if plan:
            y = plan['y'](row); lx, cw = plan['col'][col]
            lw, vw = cw - C_LVGAP - VAL_W, VAL_W; vx = lx + lw + C_LVGAP
        else:
            y = 94 + row * 40
            lx, lw, vx, vw = (34, 254, 294, 120) if col == 0 else (430, 236, 672, 94)
        if kind == 'head':   # 1.11.30: a group heading across the column, white on the card, as the configurator's sections (no value)
            group += 1
            h = comp(LABEL_L, n=nm, x=lx, y=y, w=lw + vw + (vx - lx - lw), h=ROW_H, txt=label, g='g', font=6)
            h['c'] = {'pco': 65535, 'borderc': CARD['c']['bco'], 'bco': CARD['c']['bco']}; h['a'] = dict(h['a'], borderw=0, xcen=0, txt_maxl=30)
            add(h); continue
        if kind == 'pick':   # 1.11.35: a choice from a long list (the adjustments' settings), across the page: label, <, the choice, >
            lab = comp(LABEL_L, n='l' + nm, x=34, y=y, w=150, h=36, txt=label, g='g'); lab['c'] = dict(lab['c'], pco=0, bco=shade()); add(lab)
            bp = comp(BUTTON, n='p' + nm, x=190, y=y - 2, w=50, h=40, txt='<'); bp['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % int(klabel)}; add(bp)
            f = comp(FIELD, n=nm, x=246, y=y, w=464, h=36, txt='', g='g'); f['a'] = dict(f['a'], key=255, txt_maxl=40); add(f)
            bn = comp(BUTTON, n='n' + nm, x=716, y=y - 2, w=50, h=40, txt='>'); bn['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}; add(bn)
            continue
        if kind == 'wide':   # 1.11.40: a value stepped by a tap whose words need room ("Whenever armed"): a shorter label, a wider box
            if plan: lw2, vx2, vw2 = WIDE_L, lx + WIDE_L + C_LVGAP, cw - WIDE_L - C_LVGAP
            else: lw2, vx2, vw2 = (150, 190, 224) if col == 0 else (150, 586, 180)
            lab = comp(LABEL_L, n='l' + nm, x=lx, y=y, w=lw2, h=ROW_H, txt=label, g='g', font=FONT); lab['c'] = dict(lab['c'], pco=0, bco=shade()); add(lab)
            f = comp(FIELD, n=nm, x=vx2, y=y, w=vw2, h=ROW_H, txt='', g='g', font=FONT); f['a'] = dict(f['a'], key=255, txt_maxl=30); f['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}; add(f)
            continue
        if kind == 'info':   # 1.11.34: a row that only tells (the configurator's selects the transmitter does not change): label box across the column, the main board sets its text
            f = comp(LABEL_L, n=nm, x=lx, y=y, w=lw + vw + (vx - lx - lw), h=ROW_H, txt=label, g='g', font=FONT)
            f['c'] = dict(f['c'], pco=0, bco=shade()); f['a'] = dict(f['a'], txt_maxl=40); add(f); continue
        lab = comp(LABEL_L, n='l' + nm, x=lx, y=y, w=lw, h=ROW_H, txt=label, g='g', font=FONT)
        lab['c'] = dict(lab['c'], pco=0, bco=shade())
        add(lab)
        if kind == 'switch':   # 1.11.34 (Malcolm, 8 Oct: "the yes/no boxes should be switches"): the screen's own switch, grey off / green on, its val set by the main board
            sw = {'n': nm, 't': 'switch', 'g': 'g', 'x': vx + (vw - 80) // 2, 'y': y + (ROW_H - 34) // 2, 'w': 80, 'h': 34, 'font': 0,
                  'c': {'pco1': 0, 'bco2': 2016, 'pco': 65535, 'bco': 33808, 'pco2': 65535}, 'txt': ' / ', 'val': 0, 'a': {'dez': 0, 'dis': 100, 'txt_maxl': 24},
                  'ev': {'r': 'va0.val=%d<<8\nprint va0.val' % code}}
            add(sw); continue
        f = comp(FIELD, n=nm, x=vx, y=y, w=vw, h=ROW_H, txt='0', g='g', font=FONT)
        if kind == 'num': f['ev'] = {'r': 'keybdB.t1.txt="%s"\nva0.val=%d<<8\nprint va0.val' % (klabel, code)}
        else: f['a'] = dict(f['a'], key=255); f['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}
        add(f)
    if plan:
        for (nm, txt, x, y, w, code) in plan['btn']:
            b = comp(BUTTON, n=nm, x=x, y=y, w=w, h=C_BTN_H, txt=txt); b['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}; add(b)
    else:
        for (nm, txt, x, w, code) in bottom_row([(b[0], b[1], b[4]) for b in buttons]):   # (1.11.40: the x and w given are not used: the row is laid out by its rule)
            b = comp(BUTTON, n=nm, x=x, y=414, w=w, h=56, txt=txt); b['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}; add(b)
    add(message_box(rect=busy_rect))   # (vis 0 the rest of the time; 1.11.22's yellow stripe became a message box in 1.11.40)
    out = {'name': name, 'id': pid, 'w': 800, 'h': 480, 'bg': rates['bg'], 'nav': rates['nav'], 'ev': {'preinitialize': 'vis busy,0\n%s.pic=Screen_Background' % name}, 'comps': comps}
    json.dump(out, open(os.path.join(PAGES, '%d.json' % pid), 'w'), indent=1)
    print(pid, name, len(comps), 'components', ('compact: card %dx%d at %d,%d' % (plan['card'][2], plan['card'][3], plan['card'][0], plan['card'][1])) if plan else 'full')

# codes (the main board's NumberedFunctions1): 64 open, 65 OK, 66 save, 67 a number edited, 68 the mode tapped, 69 flip tapped, 70 page 2, 71 back to page 1
series_begin()
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
series_end()

# (the Rotorflight menu itself is made by hmi/rfmenu_pages.py since 1.11.26)
idx = json.load(open(os.path.join(PAGES, '..', 'index.json')))
have = {x['id'] for x in idx['pages']}
for pid, name, n in ((58, 'RescueView', 38), (59, 'Rescue2View', 17)):
    if pid not in have: idx['pages'].append({'id': pid, 'name': name, 'n': n})
idx['pages'].sort(key=lambda x: x['id'])
json.dump(idx, open(os.path.join(PAGES, '..', 'index.json'), 'w'), indent=1)
