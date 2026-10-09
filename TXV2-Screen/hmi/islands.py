#!/usr/bin/env python3
"""ISLANDS (screen card files for TX B91, 9 Oct 2026). Malcolm, of the first compact pages (B90): "It's fabulous! I
especially like a centered island of solid background colour with buttons contained within, surrounded by the background
image. This idea could be implemented on more screens maybe by making buttons a little smaller to make the island
smaller. This would give it a greater sense of unity." (And on 3 Oct, of the first restyle, where only slivers of the
picture showed between things: "it doesn't have to be the same for every screen" - so a page whose contents cannot
leave a real margin of picture round them keeps its card across the whole page.)

The rule, for a page with the navy card on the pilot's picture:
  - what is on the card keeps its arrangement; the empty space between its rows and its columns closes up (ROW_GAP,
    SECTION_GAP down; COL_GAP, BLOCK_GAP across), and a fixed label on the card narrows to its words;
  - the island: the card, PAD round what is on it, centred under the title strip; at least MARGIN_X / MARGIN_Y of
    picture must show round it, else the page is left as it was;
  - the bottom row: smaller buttons (BTN_W x BTN_H, the same font) along the island's foot, in the same slots counted
    from the right (OK last, Save beside it; an EMPTY slot stays empty, so a finger tapping "< Back" twice through a
    series never lands on "Bind"); a word too long for one slot takes two; with five or more the slots narrow to fit;
  - pages in a SERIES (Next / < Back) share one island, so their buttons are in the same places;
  - a progress strip lies across the island just above the buttons; the busy message box over the island's middle.
Each page starts from hmi/pre_islands/<id>.json (the page before islands, kept the first time), so this can be run
again and again. Only places and sizes change: names, ids, types, events, keyboards, texts are the page's own (check()).
Run: python3 hmi/islands.py [--report] [ids...]"""
import copy, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PAGES = os.path.join(HERE, '..', 'sd', 'hmi', 'pages'); PRE = os.path.join(HERE, 'pre_islands')
sys.path.insert(0, HERE)
from fontw import width

TOP, BOTTOM = 58, 480
PAD = 16
BTN_W, BTN_H, BTN_GAP, BTN_ABOVE = 160, 50, 12, 14
MARGIN_X, MARGIN_Y = 24, 16
ROW_GAP, SECTION_GAP, SECTION_AT = 10, 18, 24       # down: a gap over SECTION_AT is a section break, kept as SECTION_GAP
COL_GAP, BLOCK_GAP, BLOCK_AT = 12, 28, 40           # across: likewise between blocks of columns
FLOAT = 0.40                                        # (wider than this share of the page: floats - see close_up)
NAVY = 4426
SKIP_T = ('variable', 'timer', 'audio', 'hotspot')
PLACEHOLDERS = ('model name', 'please wait', 'unknown', 'untitled')

# the pages, and the series that share an island (their bottom rows must line up)
PAGES_WANTED = [1, 3, 4, 5, 6, 7, 9, 16, 18, 19, 20, 23, 24, 25, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 39, 40, 42, 46, 49, 50, 51, 52, 53, 54, 55]
SERIES = [[25, 24, 23]]
# a label the Teensy writes whose words are not in its source as a literal (seen on the bench): never narrowed
KEEP_WIDE = {}

def squeeze(pg, y0, y1, x0, x1, cols):
    """A table in [x0, x1] x [y0, y1]: its columns narrower, cols = [(left edge, right edge, new width)] left to right;
    a cell in a column takes the column's new place and width (a cell across several columns spans their new extent)."""
    newx = {}; x = x0
    for a, b, w in cols: newx[a] = (x, w); x += w + (cols[1][0] - cols[0][1] if len(cols) > 1 else 2)
    def col_at(px):
        return min(cols, key=lambda c: abs(c[0] - px))
    def col_end(px):
        return min(cols, key=lambda c: abs(c[1] - px))
    for c in pg['comps']:
        if c.get('x') is None or not (y0 <= c['y'] < y1 and x0 - 4 <= c['x'] and c['x'] + c['w'] <= x1 + 4): continue
        a = col_at(c['x']); b = col_end(c['x'] + c['w'])
        nx, _ = newx[a[0]]; bx, bw = newx[b[0]]
        c['x'] = nx; c['w'] = bx + bw - nx

# Per page, what must change before its island fits - each one a small, deliberate choice (sizes, the odd place or word):
#  w: new widths (a centred text keeps its centre); put: a component moved and restyled; txt: new words for a button;
#  squeeze: a table's columns narrower; row_gap: the page's rows closer than the rule; foot: a body button to the bottom row
TWEAKS = {
    3: dict(w={'t1': 520}),                                               # the model's name (centred) not across the page
    4: dict(w={n: 210 for n in ('b12', 'b6', 'b10', 'b1', 'b3', 'b19', 'b4', 'b16', 'b8', 'b15', 'b13', 'b18', 'b0', 'b5', 'b14', 'b11', 'b7', 'b9')},
            put={'ModelName': dict(x=10, y=16, w=270, h=26, font=2, a=dict(xcen=0), c=dict(bco=2214))}),   # the model's name top left in the strip, as on the Rotorflight pages
    6: dict(foot=['b2'], txt={'b2': 'Global ...'}),                       # (Global governor parameters ...: beside Save, as Advanced ... is on Rates and PIDs)
    19: dict(w={'FilesBox': 420, 't4': 140, 't5': 140, 't6': 140}),
    25: dict(w={'TxName': 470}),
    27: dict(w={'chM': 180}),
    29: dict(w={'chM': 120, 't10': 120, 'chS': 120}),
    31: dict(dy=dict([(n, -2) for n in ('t8', 'n0', 't14', 'n4')] + [(n, -4) for n in ('t11', 'n1', 't15', 'n5')] + [(n, -6) for n in ('t13', 'n3', 't17', 'n7')] + [('t3', -16), ('t7', -18)]),   # (the channels' rows 44 apart, not 46, the two lines under them closer)
             h={'rate': 3 * 35 + 6}, w={'t12': 70, 't8': 70, 't11': 70, 't13': 70, 't16': 70, 't14': 70, 't15': 70, 't17': 70, 't3': 340, 't7': 340}),
    40: dict(squeeze=(90, 300, 40, 773, [(40, 130, 82)] + [(131 + 107 * k, 236 + 107 * k, 101) for k in range(6)])),
    42: dict(squeeze=(100, 360, 324, 770, [(324 + 112 * k, 434 + 112 * k, 104) for k in range(4)])),
    46: dict(w={'MMems': 640}, h={'MMems': 7 * 37 + 6}),                 # (the list: 7 whole rows, not 9 - an odd number, as every list)
    5: dict(narrow_cols=(80, 400, [(33, 269), (281, 517), (528, 765)], 6)),
    23: dict(w={'u_warn': 147, 'u_conn': 147, 'u_gap': 147}, row_h=(32, 30), row_gap=3, font={n: 2 for n in ('t2', 'n1', 'n2', 'n3', 'Qnh', 'n4', 'n0')}),   # (nine rows: the framed numbers in 24 px, to fit 30 px rows)
    24: dict(w={'DateTime': 660, 'b12': 140}, h={'DateTime': 64}),   # (the date in its 64 px font, no taller; Reset clock as wide as its words)
    27: dict(w={'chM': 180}, row_h=(46, 40)),
    29: dict(w={'chM': 120, 't10': 120, 'chS': 120}, row_gap=4, dy={n: -8 for n in ('t12', 't6', 't8', 't4', 'c0', 'Enabled', 'od', 'Reversed')}),   # (the switches' rows on the same lines as the numbers')
    33: dict(row_h=(70, 62), put={'ModelName': dict(x=10, y=16, w=270, h=26, font=2, a=dict(xcen=0), c=dict(bco=2214))}),
    51: dict(row_gap=4, row_h=(40, 36), put={'ModelName': dict(x=10, y=16, w=270, h=26, font=2, a=dict(xcen=0), c=dict(bco=2214))}),
    55: dict(w={'h0': 500, 'Ex1': 500}, row_gap=4, row_h=(38, 34)),
}
TWEAKS[19] = dict(w={'FilesBox': 420, 't4': 140, 't5': 140, 't6': 140}, h={'FilesBox': 5 * 39 + 6})   # (5 whole rows, not 7)
TWEAKS[25] = dict(w={'TxName': 470, 't1': 110, 't3': 110, 't11': 110, 'u_mode': 110}, row_gap=4)
ALLOWED = {}   # per page: the components whose font, attributes or words a tweak changes (check() lets those through)

def tweak(pg):
    t = TWEAKS.get(pg['id'], {}); by = {c['n']: c for c in pg['comps']}; allowed = ALLOWED.setdefault(pg['id'], set())
    for n, w in t.get('w', {}).items():
        c = by[n]
        if c.get('a', {}).get('xcen') == 1: c['x'] += (c['w'] - w) // 2
        c['w'] = w
    for n, props in t.get('put', {}).items():
        c = by[n]
        for k, v in props.items():
            if k in ('a', 'c'): c[k] = dict(c.get(k, {}), **v)
            else: c[k] = v
        allowed.add(n)
    for n, words in t.get('txt', {}).items():
        by[n]['txt'] = words; allowed.add(n)
    if 'squeeze' in t: squeeze(pg, *t['squeeze'])
    for n in t.get('foot', []):
        by[n]['y'] = 414; by[n]['h'] = 56
    for n, h in t.get('h', {}).items():
        by[n]['h'] = h
    for n, dy in t.get('dy', {}).items():
        by[n]['y'] += dy
    for n, f in t.get('font', {}).items():
        by[n]['font'] = f; allowed.add(n)
    if 'row_h' in t:   # every body row of one height made lower
        old_h, new_h = t['row_h']
        for c in pg['comps']:
            if c.get('h') == old_h and c.get('y', 0) > TOP and c.get('y', 0) < 396: c['y'] += (old_h - new_h) // 2; c['h'] = new_h
    if 'narrow_cols' in t:   # side-by-side columns [(left, right)] each d narrower: what spans a column narrows, what sits at its right moves in
        y0, y1, cols, d = t['narrow_cols']
        for k, (a, b) in enumerate(cols):
            for c in pg['comps']:
                if c.get('x') is None or not (y0 <= c['y'] < y1 and a - 2 <= c['x'] and c['x'] + c['w'] <= b + 2): continue
                if c['w'] >= (b - a) - 4: c['w'] -= d
                elif c['x'] + c['w'] >= b - 4: c['x'] -= d
                c['x'] -= k * d

_lits = None
def teensy_literals():
    global _lits
    if _lits is None:
        src = ''
        root = os.path.expanduser('~/Documents/GitHub/TXV1B/TransmitterCode')
        for dp, _, fs in os.walk(os.path.join(root, 'include')):
            for f in fs:
                if f.endswith('.h'): src += open(os.path.join(dp, f), errors='replace').read()
        src += open(os.path.join(root, 'src', 'main.cpp'), errors='replace').read()
        _lits = set(m.strip() for m in re.findall(r'"((?:[^"\\]|\\.)*)"', src))
    return _lits

def preinit_hidden(pg):
    return set(re.findall(r'vis (\w+),0', pg.get('ev', {}).get('preinitialize', '')))

def parts(pg):
    head, foot, body = [], [], []
    for c in pg['comps']:
        if c['n'] == 'card' or c.get('t') in SKIP_T: continue
        if c.get('x', 0) <= -1000 or c.get('x', 0) >= 800 or c.get('y', 0) >= BOTTOM: continue   # parked
        if c['n'] == 'busy' or c.get('a', {}).get('style') == 5: continue                        # the message box
        if c['y'] + c['h'] <= TOP + 2: head.append(c); continue
        if c['y'] >= 396 or c['t'] == 'progress bar': foot.append(c); continue
        body.append(c)
    return head, foot, body

def plain_label(c):
    """Words on the card with no box of their own (a tap on some opens the value beside them: the words stay the target)."""
    a = c.get('a', {}); col = c.get('c', {})
    return c['t'] == 'text' and col.get('bco') == NAVY and (a.get('borderw', 0) == 0 or a.get('style', 0) == 0) and a.get('style', 0) in (0, 1)

def original_names(pid):
    path = os.path.join(HERE, 'originals', '%d.json' % pid)
    return {c['n'] for c in json.load(open(path))['comps']} if os.path.exists(path) else None

def narrow_labels(pg, body):
    """A fixed label on the card narrows to its words (+ a little). Fixed: a label the restyle ADDED (not on the Version 1
    page, so the Teensy cannot know it), or words the Teensy never sends (not a literal in its source) that are not a
    placeholder; never one the page knows to keep wide."""
    lits = teensy_literals(); keep = KEEP_WIDE.get(pg['id'], ()); orig = original_names(pg['id'])
    for c in body:
        if not plain_label(c) or c['n'] in keep: continue
        t = c.get('txt', '')
        added = orig is not None and c['n'] not in orig
        if not t or (not added and (t in lits or any(p in t.lower() for p in PLACEHOLDERS))): continue
        need = width(c['font'], t) + 14
        if need >= c['w']: continue
        xc = c.get('a', {}).get('xcen', 0)
        if xc == 1: c['x'] += (c['w'] - need) // 2
        elif xc == 2: c['x'] += c['w'] - need
        c['w'] = need

def bands(comps, axis):
    lo = (lambda c: c['y']) if axis == 'y' else (lambda c: c['x'])
    hi = (lambda c: c['y'] + c['h']) if axis == 'y' else (lambda c: c['x'] + c['w'])
    out = []
    for c in sorted(comps, key=lo):
        if out and lo(c) < out[-1][1]:
            out[-1][1] = max(out[-1][1], hi(c)); out[-1][2].append(c)
        else:
            out.append([lo(c), hi(c), [c]])
    return out

def close_up(comps, axis, small_gap=None):
    """Close the gaps between the bands (rows down, columns across). Across, a component wider than FLOAT of the whole
    (a slider, a list, a model's name over everything) would join every column into one band: it FLOATS - left out of
    the bands, its two edges then moved as the columns under them moved."""
    small, big, at = (ROW_GAP, SECTION_GAP, SECTION_AT) if axis == 'y' else (COL_GAP, BLOCK_GAP, BLOCK_AT)
    if small_gap is not None: small = small_gap
    floats = bridges(comps) if axis == 'x' else []
    rest = [c for c in comps if c not in floats] or comps
    reach = {id(c) for c in floats if c['t'] != 'text' and c['x'] + c['w'] >= max(o['x'] + o['w'] for o in comps) - 80}   # (a slider that ran to the right edge runs to it still)
    bs = bands(rest, axis); shift = 0; sh = [0]
    for k in range(1, len(bs)):
        gap = bs[k][0] - bs[k - 1][1]
        new = gap if gap <= small and small_gap is None else (small if gap <= at else big)
        shift += gap - new; sh.append(shift)
    # a floater is an obstacle: a column to its right, in its rows, never comes nearer to it than COL_GAP
    for k in range(1, len(bs)):
        for f in floats:
            if f['x'] >= bs[k][0] or not any(c['y'] < f['y'] + f['h'] and f['y'] < c['y'] + c['h'] for c in bs[k][2]): continue
            if f['x'] + f['w'] <= bs[k][0] - COL_GAP and True:
                before = max([j for j in range(len(bs)) if bs[j][0] <= f['x'] + f['w'] - 1] or [0])
                right = f['x'] + f['w'] - sh[before] if before < k else f['x'] + f['w']
                allowed = bs[k][0] - (right + COL_GAP)
                if sh[k] > allowed and allowed >= 0:
                    d = sh[k] - allowed
                    for j in range(k, len(bs)): sh[j] -= d
    moves = [(bs[k][2], sh[k]) for k in range(1, len(bs))]; edges = [(bs[k][0], sh[k]) for k in range(1, len(bs))]
    shifts = [(bs[0][0], bs[0][1], 0)] + [(bs[k][0], bs[k][1], s) for k, (_, s) in enumerate(edges, start=1)]
    def moved(px, left):   # how far a point moved: with the band it is in; in a gap, a left edge goes with the band after it, a right edge with the band before
        for k, (a, b, s) in enumerate(shifts):
            if a <= px < b: return s
            if px < a: return s if left else (shifts[k - 1][2] if k else 0)
        return shifts[-1][2]
    for c in floats:
        a = c['x'] - moved(c['x'], True); b = c['x'] + c['w'] - moved(c['x'] + c['w'] - 1, False)
        need = width(c['font'], c.get('txt', '')) + 14 if c['t'] == 'text' and c.get('txt') else 20
        if c['t'] == 'text' and c.get('a', {}).get('xcen') == 1 and b - a < c['w']:   # (a centred text: centred over what it spanned)
            w = max(need, b - a); c['x'], c['w'] = (a + b - w) // 2, w
        else:
            c['x'], c['w'] = a, max(need, b - a)
    for cs, s in moves:
        for c in cs: c[axis] -= s
    if reach:
        right = max(c['x'] + c['w'] for c in rest)
        for c in floats:
            if id(c) in reach: c['w'] = max(c['w'], right - c['x'])

def bridges(comps):
    """The components that join columns which would otherwise stand apart (sliders under three columns, a heading over
    two, a model's name across the page): left out of the columns, they float. In each band the widest go, one at a
    time, until what is left falls apart into columns (a band that never does is one column, and keeps them all)."""
    floats = []
    for lo, hi, cs in bands(comps, 'x'):
        if len(cs) < 3: continue
        order = sorted(cs, key=lambda c: -c['w']); gone = []
        while len(gone) < len(cs) // 2:
            gone.append(order[len(gone)])
            rest = [c for c in cs if c not in gone]
            if len(bands(rest, 'x')) >= 2:
                floats += gone + bridges(rest); break   # (and again within what is left: a label over three of five columns)
    return floats

def bbox(cs):
    return (min(c['x'] for c in cs), min(c['y'] for c in cs), max(c['x'] + c['w'] for c in cs), max(c['y'] + c['h'] for c in cs))

def slots_of(buttons):
    """The bottom row as slots counted from the right (0 = OK's): [(comp, slot, span)] - from the four fixed slots
    (x 14/211/408/605) where the row used them, else in order (five or more, or odd widths)."""
    fixed = {14: 3, 211: 2, 408: 1, 605: 0}
    if all(b['x'] in fixed and b['w'] in (180, 377) for b in buttons):
        out = []
        for b in buttons:
            span = 2 if b['w'] == 377 else 1
            out.append((b, fixed[b['x']] - (span - 1), span))
        return out
    out = []; s = 0
    for b in sorted(buttons, key=lambda b: -b['x']):
        span = 2 if width(b['font'], b.get('txt', '')) + 16 > BTN_W and len(buttons) <= 4 else 1
        out.append((b, s, span)); s += span
    return out


def row_width(slots, w):
    n = max(s + span for _, s, span in slots) if slots else 0
    return n * w + (n - 1) * BTN_GAP if n else 0

def button_w(slots, max_inner):
    w = BTN_W
    while row_width(slots, w) > max_inner and w > 80: w -= 2
    for b, s, span in slots:
        if span == 1 and width(b['font'], b.get('txt', '')) + 16 > w and len(b.get('txt', '')) > 1: return None   # (words no longer fit)
    return w

def plan(pg):
    """The page as an island, or None (with why) when it cannot leave a real margin of picture."""
    pg = copy.deepcopy(pg)
    tweak(pg)
    head, foot, body = parts(pg)
    if not body: return None, 'nothing on the card'
    narrow_labels(pg, body)
    close_up(body, 'y', TWEAKS.get(pg['id'], {}).get('row_gap')); close_up(body, 'x')
    bx0, by0, bx1, by1 = bbox(body)
    bw, bh = bx1 - bx0, by1 - by0
    hid = preinit_hidden(pg)
    buttons = [c for c in foot if c['t'] in ('button', 'dual-state button') and (c['n'] not in hid or (c['x'] in (14, 211, 408, 605) and c['w'] in (180, 377)))]
    others = [c for c in foot if c not in buttons]
    max_inner = 800 - 2 * MARGIN_X - 2 * PAD
    slots = slots_of(buttons)
    w = button_w(slots, max_inner) if slots else BTN_W
    if w is None: return None, 'the buttons do not fit'
    rw = row_width(slots, w)
    inner_w = max(bw, rw)
    iw = inner_w + 2 * PAD
    ih = PAD + bh + (BTN_ABOVE + BTN_H if slots else 0) + PAD
    if iw > 800 - 2 * MARGIN_X: return None, 'too wide (%d)' % iw
    if ih > BOTTOM - TOP - 2 * MARGIN_Y: return None, 'too tall (%d)' % ih
    return dict(pg=pg, head=head, body=body, bbox=(bx0, by0, bw, bh), slots=slots, btn_w=w, others=others, size=(iw, ih)), None

def apply(p, size=None):
    pg = p['pg']; iw, ih = size or p['size']
    ix, iy = (800 - iw) // 2, TOP + (BOTTOM - TOP - ih) // 2
    bx0, by0, bw, bh = p['bbox']
    dx = ix + PAD + (iw - 2 * PAD - bw) // 2 - bx0
    dy = iy + PAD - by0
    for c in p['body']: c['x'] += dx; c['y'] += dy
    card = next(c for c in pg['comps'] if c['n'] == 'card')
    card.update(x=ix, y=iy, w=iw, h=ih); card['a'] = dict(card.get('a', {}), style=0, borderw=0)
    by = iy + ih - PAD - BTN_H; right = ix + iw - PAD; w = p['btn_w']
    taken = []
    for b, s, span in p['slots']:
        bwid = span * w + (span - 1) * BTN_GAP
        x = right - (s + span) * w - (s + span - 1) * BTN_GAP
        b.update(x=x, y=by, w=bwid, h=BTN_H); taken.append((x, x + bwid))
    ok = next((b for b, s, span in p['slots'] if s == 0), None)
    # what else was on the bottom row
    hidden = preinit_hidden(pg)
    for c in p['others']:
        if c['t'] == 'progress bar':
            c.update(x=ix + PAD, y=by - (BTN_ABOVE + c['h']) // 2 - 1 if p['slots'] else iy + ih - PAD - c['h'], w=iw - 2 * PAD)
            continue
        if c['n'] in hidden and ok is not None:   # (a helper the page clicks: beside OK, as it was)
            c.update(x=ok['x'] - (605 - c['x']), y=by + (BTN_H - c['h']) // 2); continue
    spans = []   # the empty stretches of the row, for the words that lived there
    edges = sorted(taken); x = ix + PAD
    for a, b in edges:
        if a - x >= 40: spans.append((x, a - BTN_GAP))
        x = b + BTN_GAP
    if right - x >= 40: spans.append((x, right))
    rest = [c for c in p['others'] if c['t'] != 'progress bar' and c['n'] not in hidden and c['h'] >= 30]
    if rest:
        gx0 = min(c['x'] for c in rest); gx1 = max(c['x'] + c['w'] for c in rest)
        s0, s1 = max(spans, key=lambda s: s[1] - s[0]) if spans else (ix + PAD, right)
        left = gx0 < 100
        ox = s0 if left else s0 + max(0, ((s1 - s0) - (gx1 - gx0)) // 2)
        for c in rest:
            c['x'] = ox + (c['x'] - gx0); c['y'] = by + (BTN_H - c['h']) // 2
            if c['x'] + c['w'] > s1: c['w'] = max(40, s1 - c['x'])
    for busy in [c for c in pg['comps'] if c['t'] == 'text' and c.get('a', {}).get('style') == 5 and c.get('x', 0) > -1000]:   # the message boxes
        busy['x'] = max(8, ix + (iw - busy['w']) // 2); busy['y'] = max(TOP + 4, iy + (ih - busy['h']) // 2)
    return pg

def check(before, after):
    """Only places and sizes changed (and what TWEAKS changes on purpose)."""
    probs = []; allowed = ALLOWED.get(after['id'], set())
    a = {c['n']: c for c in before['comps']}; b = {c['n']: c for c in after['comps']}
    if set(a) != set(b): probs.append('components differ')
    for n, c in a.items():
        d = b.get(n)
        if not d or n in allowed: continue
        for k in c:
            if k in ('x', 'y', 'w', 'h'): continue
            if k == 'a':
                ka = {x: y for x, y in c['a'].items() if x not in ('style', 'borderw')} if n == 'card' else c['a']
                kb = {x: y for x, y in d['a'].items() if x not in ('style', 'borderw')} if n == 'card' else d['a']
                if ka != kb: probs.append('%s attributes changed' % n)
                continue
            if c[k] != d.get(k): probs.append('%s %s changed' % (n, k))
        if 'x' not in d: continue
        if d['x'] > -1000 and (d['x'] < 0 or d['y'] < 0 or d['x'] + d['w'] > 800 or d['y'] + d['h'] > 480) and not (c['x'] + c['w'] > 800 or c['y'] + c['h'] > 480):
            probs.append('%s off the glass' % n)
    for k in ('name', 'id', 'bg', 'ev', 'nav'):
        if before.get(k) != after.get(k): probs.append('page %s changed' % k)
    return probs

def pre(pid):
    path = os.path.join(PRE, '%d.json' % pid)
    if not os.path.exists(path):
        json.dump(json.load(open(os.path.join(PAGES, '%d.json' % pid))), open(path, 'w'), indent=1)
    return json.load(open(path))

def run(ids, report=False):
    plans, why = {}, {}
    for pid in ids:
        p, w = plan(pre(pid))
        if p: plans[pid] = p
        else: why[pid] = w
    for series in SERIES:   # one island for the series: the largest of its pages
        ps = [plans[s] for s in series if s in plans]
        if len(ps) != len(series):
            for s in series: plans.pop(s, None); why.setdefault(s, 'its series cannot share an island')
            continue
        size = (max(p['size'][0] for p in ps), max(p['size'][1] for p in ps))
        for p in ps: p['size'] = size
    done = []
    for pid in ids:
        if pid not in plans:
            print('%3d %-16s full card kept: %s' % (pid, pre(pid)['name'], why[pid]))
            path = os.path.join(PAGES, '%d.json' % pid)   # (the copy here is the page's source: a change made to it reaches the card)
            if not report and json.load(open(path)) != pre(pid): json.dump(pre(pid), open(path, 'w'), indent=1)
            continue
        p = plans[pid]; out = apply(p)
        probs = check(pre(pid), out)
        iw, ih = p['size']
        print('%3d %-16s island %dx%d  margins %d / %d  buttons %d wide%s' % (pid, out['name'], iw, ih, (800 - iw) // 2, (BOTTOM - TOP - ih) // 2, p['btn_w'], ('  PROBLEMS: ' + '; '.join(probs)) if probs else ''))
        if not report and not probs:
            json.dump(out, open(os.path.join(PAGES, '%d.json' % pid), 'w'), indent=1); done.append(pid)
    return done

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    run([int(a) for a in args] or PAGES_WANTED, report='--report' in sys.argv)
