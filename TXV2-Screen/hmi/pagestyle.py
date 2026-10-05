"""The screen's page style (the System pages of 2026-10-03, approved by Malcolm), as a toolkit for restyling the
Nextion pages WITHOUT changing what they do.

Rules every restyle obeys (verify() checks them against the original page):
  - every component keeps its name, id, type, g, events, keyboard (a.key) and 'need' rule;
  - the page keeps its name, id, background, events and nav; the pilot's own background picture stays;
  - only places, sizes, fonts, colours, styles and the words of FIXED labels change; new components are plain
    labels or the card, with new ids above the page's highest.
Each page is restyled from its ORIGINAL (hmi/originals/<id>.json), so a script can be run again and again.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, '..', 'sd', 'hmi', 'pages')
ORIG = os.path.join(HERE, 'originals')

NAVY, STRIP, WHITE, SOFT, BLACK, BTN, GREEN, GREY, YELLOW, RED = 4426, 2214, 65535, 50712, 0, 54938, 2016, 33808, 65504, 63488
STRIP_H = 58
CARD = (14, 66, 772, 340)                                  # x, y, w, h
SLOTS = [(14 + i * 197, 414, 180, 56) for i in range(4)]   # Back, Bind/second, Next, OK
HELP = (620, 4, 170, 50)
FONT_H = {0: 32, 1: 64, 2: 24, 3: 24, 4: 16, 5: 32, 6: 28}


def load_original(pid):
    return json.load(open(os.path.join(ORIG, f'{pid}.json')))

def save(pid, pg):
    json.dump(pg, open(os.path.join(PAGES, f'{pid}.json'), 'w'), separators=(',', ':'))

def comp(pg, name):
    for c in pg['comps']:
        if c['n'] == name:
            return c
    sys.exit(f'{pg["name"]}: no component {name}')

def has(pg, name):
    return any(c['n'] == name for c in pg['comps'])

def place(c, x, y, w, h):
    c['x'], c['y'], c['w'], c['h'] = x, y, w, h

def _maxl(c, text):
    c.setdefault('a', {})
    c['a']['txt_maxl'] = max(c['a'].get('txt_maxl', 0), len(text) + 2)

def title(pg, name, text=None):
    """The navy strip along the top, its words centred."""
    t = comp(pg, name); place(t, 0, 0, 800, STRIP_H)
    t['sta'] = 1; t['font'] = 0
    if text is not None:
        t['txt'] = text; _maxl(t, text)
    t['c'].update({'bco': STRIP, 'pco': WHITE})
    t.setdefault('a', {}).update({'xcen': 1, 'ycen': 1, 'style': 0, 'borderw': 0})

def card(pg, after, ev=None, rect=CARD):
    """One plain navy card, drawn just after `after` (a touch on it does what a touch on the page did: ev)."""
    pg['comps'] = [c for c in pg['comps'] if c['n'] != 'card']
    newid = max(c['i'] for c in pg['comps']) + 1
    x, y, w, h = rect
    c = {'n': 'card', 'i': newid, 't': 'text', 'g': 'l', 'x': x, 'y': y, 'w': w, 'h': h, 'font': 6, 'sta': 1,
         'c': {'pco': WHITE, 'borderc': WHITE, 'bco': NAVY}, 'txt': '',
         'a': {'style': 1, 'key': 255, 'borderw': 2, 'xcen': 0, 'ycen': 1, 'pw': 0, 'txt_maxl': 1, 'isbr': 0}}
    if ev:
        c['ev'] = ev
    pg['comps'].append(c)
    backgrounds_first(pg, after)

def backgrounds_first(pg, strip_name):
    """The strip and the card are drawn FIRST, everything else after them in its original order (the screen draws in
    list order: a Help button listed before the title was painted over by the strip)."""
    first = ([c for c in pg['comps'] if c['n'] == strip_name] if strip_name else []) + [c for c in pg['comps'] if c['n'] == 'card']
    pg['comps'] = first + [c for c in pg['comps'] if c['n'] not in (strip_name, 'card')]

def strip_of(pg):
    return next((c for c in pg['comps'] if c['t'] == 'text' and c.get('x') == 0 and c.get('y') == 0 and c.get('w') == 800), None)

def ground(pg):
    """Blue everywhere under the title strip: the card becomes the whole page below it, with no frame (Malcolm,
    2026-10-03: on most pages only slivers of the background picture showed - "it might be simpler simply to forget
    the background image and put the dark blue background everywhere ... it doesn't have to be the same for every
    screen"). Pages with little on them keep a smaller card with the picture round it instead (compact)."""
    s = strip_of(pg); top = s['h'] if s else 0
    if not has(pg, 'card'): card(pg, s['n'] if s else None)
    c = comp(pg, 'card'); place(c, 0, top, 800, 480 - top); c['a'].update({'style': 0, 'borderw': 0})

def compact(pg, rect):
    """A card just big enough for what is on it, framed, with the pilot's picture round it."""
    place(comp(pg, 'card'), *rect)

def page_touch(pg):
    """The page's own touch events, for a card that covers it."""
    ev = pg.get('ev', {}); out = {}
    if ev.get('touch_press'): out['p'] = ev['touch_press']
    if ev.get('touch_release'): out['r'] = ev['touch_release']
    return out or None

def add_label(pg, name, text, x, y, w, h, font=6, colour=WHITE, xcen=0, bco=NAVY):
    pg['comps'] = [c for c in pg['comps'] if c['n'] != name]
    newid = max(c['i'] for c in pg['comps']) + 1
    pg['comps'].append({'n': name, 'i': newid, 't': 'text', 'g': 'l', 'x': x, 'y': y, 'w': w, 'h': h, 'font': font, 'sta': 1,
                        'c': {'pco': colour, 'borderc': 0, 'bco': bco}, 'txt': text,
                        'a': {'style': 0, 'key': 255, 'borderw': 0, 'xcen': xcen, 'ycen': 1, 'pw': 0, 'txt_maxl': len(text) + 2, 'isbr': 0}})

def tile(c, x, y, w, h, font=6, text=None):
    """A text the pilot touches (it has its own touch events): a raised tile, so it looks like what it is."""
    place(c, x, y, w, h); c['sta'] = 1; c['font'] = font
    c['c'].update({'bco': BTN, 'pco': BLACK, 'borderc': 0})
    c.setdefault('a', {}).update({'xcen': 1, 'ycen': 1, 'style': 3, 'borderw': 2})
    if text is not None:
        c['txt'] = text; _maxl(c, text)

def text_on_card(c, x, y, w, h, font=6, colour=WHITE, xcen=0, text=None):
    """A label (or a text the Teensy writes) on the navy card: no box, no frame."""
    place(c, x, y, w, h); c['sta'] = 1; c['font'] = font
    c['c'].update({'bco': NAVY, 'pco': colour, 'borderc': 0})
    c.setdefault('a', {}).update({'xcen': xcen, 'ycen': 1, 'style': 0, 'borderw': 0})
    if text is not None:
        c['txt'] = text; _maxl(c, text)

def entry(c, x, y, w, h, font=6, xcen=1):
    """A box the pilot types into (or a value the Teensy shows): white, sunken."""
    place(c, x, y, w, h); c['sta'] = 1; c['font'] = font
    c['c'].update({'bco': WHITE, 'pco': BLACK, 'borderc': 0})
    c.setdefault('a', {}).update({'xcen': xcen, 'ycen': 1, 'style': 2, 'borderw': 2})

def button(c, x, y, w, h, text=None, font=6):
    place(c, x, y, w, h); c['font'] = font
    c['c'].update({'bco': BTN, 'pco': BLACK})
    c.setdefault('a', {}).update({'style': 4, 'borderw': 2, 'xcen': 1, 'ycen': 1})
    if text is not None:
        c['txt'] = text; _maxl(c, text)

def slot(c, i, text=None):
    button(c, *SLOTS[i], text=text)

def help_button(c):
    button(c, *HELP)

def slider(c):
    """A slider in the switches' colours: a grey track, a white knob (they were yellow with a red knob)."""
    c['c'].update({'bco': GREY, 'pco': WHITE})

def ring(pg, name, colour=STRIP, width=3):
    """A dark ring just outside a dialog's white edge, so the edge shows over white boxes as well as over the navy card:
    a plain label drawn just before the dialog."""
    pg['comps'] = [c for c in pg['comps'] if c['n'] != name + '_ring']
    d = comp(pg, name); newid = max(c['i'] for c in pg['comps']) + 1
    r = {'n': name + '_ring', 'i': newid, 't': 'text', 'g': 'l', 'x': d['x'] - width, 'y': d['y'] - width, 'w': d['w'] + 2 * width, 'h': d['h'] + 2 * width,
         'font': 6, 'sta': 1, 'c': {'pco': colour, 'borderc': colour, 'bco': colour}, 'txt': '',
         'a': {'style': 0, 'key': 255, 'borderw': 0, 'xcen': 0, 'ycen': 1, 'pw': 0, 'txt_maxl': 1, 'isbr': 0}}
    at = pg['comps'].index(d); pg['comps'].insert(at, r)

def sunken_list(c):
    """A scrolling list framed like every other white box (sunk), not in the old red or yellow line."""
    c['a']['style'] = 2; c['a']['borderw'] = max(2, c['a'].get('borderw', 2))

def switch(c, x, y, w, h):
    place(c, x, y, w, h)
    c['c'].update({'bco': GREY, 'bco2': GREEN, 'pco': WHITE})

def park(c):
    c['x'] = -2000; c['y'] = -2000

def grid(n_cols, n_rows, x0, y0, w, h, gx, gy):
    return [[(x0 + col * (w + gx), y0 + row * (h + gy), w, h) for col in range(n_cols)] for row in range(n_rows)]


def verify(pid, pg, fixes=None):
    """Nothing the Teensy or the pilot can notice in behaviour has changed (see the top of this file) - except the named
    FIXES: a function that makes the same deliberate repairs (a page script's typo, say) to the original first."""
    a = load_original(pid); ok = True; problems = []
    if fixes: fixes(a)
    for k in ('name', 'id', 'bg', 'ev', 'nav'):
        if a.get(k) != pg.get(k): ok = False; problems.append(f'page {k} changed')
    new = {c['n']: c for c in pg['comps']}
    for c in a['comps']:
        n = new.get(c['n'])
        if not n: ok = False; problems.append(f'{c["n"]} missing'); continue
        for k in ('i', 't', 'g', 'ev', 'need'):
            if c.get(k) != n.get(k): ok = False; problems.append(f'{c["n"]} {k} changed')
        if c.get('a', {}).get('key') != n.get('a', {}).get('key'): ok = False; problems.append(f'{c["n"]} keyboard changed')
        for k in ('maxval', 'minval', 'lenth', 'format', 'tim', 'en', 'dir', 'mode'):
            if c.get('a', {}).get(k) != n.get('a', {}).get(k): ok = False; problems.append(f'{c["n"]} {k} changed')
        if c.get('t') in ('textselect', 'combobox') and c.get('opt') != n.get('opt'): ok = False; problems.append(f'{c["n"]} options changed')
        if c.get('t') in ('number', 'switch', 'checkbox', 'radio', 'slider', 'dual-state button', 'progress bar') and c.get('val') != n.get('val'):
            ok = False; problems.append(f'{c["n"]} starting value changed')
    added = [c['n'] for c in pg['comps'] if c['n'] not in {x['n'] for x in a['comps']}]
    for nm in added:
        c = new[nm]
        if c['t'] != 'text' or c.get('ev') and nm != 'card': ok = False; problems.append(f'added {nm} is not a plain label')
    ids = [c['i'] for c in pg['comps']]; names = [c['n'] for c in pg['comps']]
    if len(ids) != len(set(ids)): ok = False; problems.append('duplicate ids')
    if len(names) != len(set(names)): ok = False; problems.append('duplicate names')
    was = {c['n']: c for c in a['comps']}
    for c in pg['comps']:
        if c.get('x') is None or c['x'] < 0: continue
        o = was.get(c['n'])
        if o and (o['x'], o['y'], o['w'], o['h']) == (c['x'], c['y'], c['w'], c['h']) and (o['x'] + o['w'] > 800 or o['y'] + o['h'] > 480): continue  # kept off the glass on purpose, where the original had it
        if c['x'] + c['w'] > 800 or c['y'] + c['h'] > 480: ok = False; problems.append(f'{c["n"]} off the glass')
    print(f'{pid:2d} {pg["name"]:<16} ' + ('kept: names, ids, types, events, keyboards, rules, values' + (f'; added {added}' if added else '') if ok else 'PROBLEMS: ' + '; '.join(problems)))
    return ok
