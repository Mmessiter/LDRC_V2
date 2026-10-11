"""Helpers for the polish modules (hmi/polish/<group>.py). Every helper sets ABSOLUTE values, so a polish can run any number of
times and the page comes out the same (hmi/polish_pages.py --check proves it)."""
import copy

def comp(pg, name):
    for c in pg['comps']:
        if c['n'] == name: return c
    raise KeyError(f"{pg['name']}: no component {name}")

def has(pg, name):
    return any(c['n'] == name for c in pg['comps'])

def put(pg, name, **kw):
    """Set fields of a component: put(pg, 'b0', x=14, y=414, w=180, h=56, font=6, txt='OK', c={'bco': 4426}, a={'xcen': 1}).
    c and a are MERGED into the component's own dicts (other keys kept)."""
    c = comp(pg, name)
    for k, v in kw.items():
        if k in ('c', 'a'): c.setdefault(k, {}).update(v)
        else: c[k] = v
    return c

def rect(pg, name, x, y, w, h):
    return put(pg, name, x=x, y=y, w=w, h=h)

def park(pg, name):
    """Never drawn, never touched (the screen's rule for a part a page no longer shows)."""
    return put(pg, name, x=-2000, y=-2000)

def add_text(pg, name, after=None, first=False, **kw):
    """A plain static text (a card, a strip, a label). Placed right after component `after` in the draw order, or first, or last.
    If it is already there (a second run) only its fields are set again. Pass ev={'r': 'print "UKRULES"'} for a card that would
    otherwise swallow the page's own touches."""
    base = {'n': name, 't': 'text', 'g': 'l', 'x': 0, 'y': 0, 'w': 10, 'h': 10, 'font': 2, 'sta': 1,
            'c': {'bco': 4426, 'pco': 65535, 'borderc': 0}, 'txt': '',
            'a': {'style': 0, 'borderw': 0, 'xcen': 1, 'ycen': 1, 'isbr': 0, 'txt_maxl': 40, 'key': 255, 'pw': 0}}
    if has(pg, name):
        c = comp(pg, name); pg['comps'].remove(c)
    else:
        c = copy.deepcopy(base); c['i'] = max(x['i'] for x in pg['comps']) + 1
    for k, v in kw.items():
        if k in ('c', 'a'): c.setdefault(k, {}).update(v)
        else: c[k] = v
    if first: pg['comps'].insert(0, c)
    elif after is not None: pg['comps'].insert(pg['comps'].index(comp(pg, after)) + 1, c)
    else: pg['comps'].append(c)
    return c

def move_after(pg, name, after):
    """Change only the DRAW ORDER (list order): `name` is drawn right after `after`."""
    c = comp(pg, name); pg['comps'].remove(c); pg['comps'].insert(pg['comps'].index(comp(pg, after)) + 1, c); return c

def ev_title(pg, name, key, old, new):
    """Change the WORDS of a help-viewer title or keypad question inside an event (LogView.t0.txt / keybdA.t1.txt / keybdB.t1.txt).
    Refuses anything else. Idempotent: if `new` is already there nothing happens."""
    c = comp(pg, name); s = c['ev'][key]
    for target in ('LogView.t0.txt=', 'keybdA.t1.txt=', 'keybdB.t1.txt='):
        if f'{target}"{new}"' in s: return
        if f'{target}"{old}"' in s:
            c['ev'][key] = s.replace(f'{target}"{old}"', f'{target}"{new}"'); return
    raise KeyError(f"{pg['name']}.{name}: no title {old!r} in its {key} event")
