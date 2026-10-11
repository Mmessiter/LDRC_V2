#!/usr/bin/env python3
"""TOUCH AUDIT (10 Oct 2026, with hmi/logic_guard.py): for every page, compares with a base commit which component WINS a tap at
each pixel (the screen's hit(): the topmost visible component in list order), and reports touchable things that got covered,
removed or shrunk, and areas that no longer reach the page's own touch. Needs numpy.  Run: python3 hmi/touch_audit.py [BASE]"""
import json, os, re, subprocess, sys
import numpy as np
ROOT = os.path.expanduser('~/Documents/GitHub/ESP32-board2/board4/nextion-emulator')
BASE = sys.argv[1] if len(sys.argv) > 1 else 'a084386'
W, H = 800, 480
TITLE_LIT = re.compile(r'((?:LogView\.t0|keybdA\.t1|keybdB\.t1)\.txt=)"[^"\n]*"')
GEOM = {'x', 'y', 'w', 'h', 'font', 'c', 'txt'}
NOHIT = {'variable', 'timer', 'audio'}
INTER = {'slider', 'textselect', 'combobox', 'checkbox', 'radio', 'dual-state button', 'switch', 'sltext', 'rangebar'}

def old_page(pid):
    r = subprocess.run(['git', 'show', f'{BASE}:board4/nextion-emulator/sd/hmi/pages/{pid}.json'], cwd=ROOT, capture_output=True, text=True)
    return json.loads(r.stdout)

def touchy(c):
    ev = c.get('ev') or {}
    if any(v.strip() for k, v in ev.items() if k in ('p', 'r', 'm')): return True
    if (c.get('a') or {}).get('key', 255) not in (255, None): return True
    return c['t'] in INTER

def winner_map(p):
    m = np.full((H, W), -1, dtype=np.int32)
    for i, c in enumerate(p['comps']):
        if c['t'] in NOHIT or 'x' not in c: continue
        x0, y0 = max(0, c['x']), max(0, c['y']); x1, y1 = min(W, c['x'] + c['w']), min(H, c['y'] + c['h'])
        if x1 > x0 and y1 > y0: m[y0:y1, x0:x1] = i
    return m

def area(c):
    if 'x' not in c: return 0
    x0, y0 = max(0, c['x']), max(0, c['y']); x1, y1 = min(W, c['x'] + c['w']), min(H, c['y'] + c['h'])
    return max(0, x1 - x0) * max(0, y1 - y0)

def ovl(a, b):
    if 'x' not in a or 'x' not in b: return False
    return a['x'] < b['x'] + b['w'] and b['x'] < a['x'] + a['w'] and a['y'] < b['y'] + b['h'] and b['y'] < a['y'] + a['h']

def rect(c): return f"({c.get('x')},{c.get('y')},{c.get('w')},{c.get('h')})" if 'x' in c else '(no rect)'

out = []
pids = sorted(int(f[:-5]) for f in os.listdir(os.path.join(ROOT, 'sd/hmi/pages')) if f.endswith('.json'))
for pid in pids:
    old = old_page(pid); new = json.load(open(os.path.join(ROOT, f'sd/hmi/pages/{pid}.json')))
    L = []
    for k in ('name', 'id', 'nav', 'bg', 'w', 'h', 'ev'):
        if old.get(k) != new.get(k): L.append(f'PAGE {k} changed: {old.get(k)!r} -> {new.get(k)!r}')
    on = {c['n']: c for c in old['comps']}; nn = {c['n']: c for c in new['comps']}
    oi = {c['n']: i for i, c in enumerate(old['comps'])}; ni = {c['n']: i for i, c in enumerate(new['comps'])}
    for n in on:
        if n not in nn: L.append(f'REMOVED {n}')
    # ids
    oid = {c['i']: c['n'] for c in old['comps']}
    for c in new['comps']:
        o = on.get(c['n'])
        if o is None:
            L.append(f"NEW {c['n']} id{c['i']} {c['t']} @{ni[c['n']]}/{len(new['comps'])} {rect(c)} ev={c.get('ev')} key={(c.get('a') or {}).get('key')} txt={c.get('txt','')[:40]!r} bco={(c.get('c') or {}).get('bco')} sta={c.get('sta')}"
                     + (f" ID-CLASH-with-old {oid[c['i']]}" if c['i'] in oid else ''))
            continue
        for k in sorted(set(o) | set(c)):
            if k in GEOM: continue
            if k == 'ev':
                if o.get('ev') != c.get('ev'):
                    for ek in sorted(set(o.get('ev') or {}) | set(c.get('ev') or {})):
                        a, b = (o.get('ev') or {}).get(ek, ''), (c.get('ev') or {}).get(ek, '')
                        if a != b:
                            same = TITLE_LIT.sub(r'\1"*"', a) == TITLE_LIT.sub(r'\1"*"', b)
                            L.append(f"EV {'title-only' if same else 'LOGIC'} {c['n']}.{ek}: {TITLE_LIT.findall(a) and re.findall(TITLE_LIT.pattern.replace('(?:','(?:'), a)} :: {a!r} -> {b!r}" if not same else f"EV title {c['n']}.{ek}: {[m.group(0) for m in TITLE_LIT.finditer(a)]} -> {[m.group(0) for m in TITLE_LIT.finditer(b)]}")
            elif k == 'a':
                oa, na = o.get('a') or {}, c.get('a') or {}
                for ak in sorted(set(oa) | set(na)):
                    if oa.get(ak) != na.get(ak): L.append(f"ATTR {c['n']} a.{ak}: {oa.get(ak)!r} -> {na.get(ak)!r}")
            elif o.get(k) != c.get(k):
                L.append(f"FIELD {c['n']} {k}: {o.get(k)!r} -> {c.get(k)!r}")
        if o.get('txt') != c.get('txt'):
            L.append(f"TXT {c['n']} ({c['t']}): {o.get('txt')!r} -> {c.get('txt')!r}")
        if 'x' in o and o.get('x', 0) > -1000 and c.get('x', 0) <= -1000:
            L.append(f"PARKED {c['n']} {c['t']} touchy={touchy(c)} was {rect(o)}")
        if 'x' in o and o.get('x', 0) <= -1000 and c.get('x', 0) > -1000:
            L.append(f"UNPARKED {c['n']} {c['t']} now {rect(c)}")
    # order changes among old comps
    common = [c['n'] for c in old['comps'] if c['n'] in nn]
    for a_i in range(len(common)):
        for b_i in range(a_i + 1, len(common)):
            a, b = common[a_i], common[b_i]
            if ni[a] > ni[b]:
                ca, cb = nn[a], nn[b]
                if ovl(ca, cb) or ovl(on[a], on[b]):
                    L.append(f"REORDER {a} now above {b} (overlap new={ovl(ca,cb)} old={ovl(on[a],on[b])}) touchy {a}={touchy(ca)} {b}={touchy(cb)}")
    # touch coverage
    mo, mn = winner_map(old), winner_map(new)
    for c in new['comps']:
        if not touchy(c) or c['t'] in NOHIT: continue
        o = on.get(c['n'])
        ar = area(c)
        if ar == 0: continue
        i = ni[c['n']]
        wins_new = int((mn == i).sum())
        if o is not None and area(o):
            wins_old = int((mo == oi[c['n']]).sum()); fo = wins_old / area(o)
        else: fo = None
        fn = wins_new / ar
        if fn < 0.999 and (fo is None or fn < fo - 0.001):
            x0, y0 = max(0, c['x']), max(0, c['y']); x1, y1 = min(W, c['x'] + c['w']), min(H, c['y'] + c['h'])
            sub = mn[y0:y1, x0:x1]
            cov = {}
            for j in np.unique(sub):
                if j != i and j >= 0: cov[new['comps'][j]['n']] = int((sub == j).sum())
            L.append(f"COVERED {c['n']} ({c['t']}) {rect(c)} wins {fn:.1%} (old {fo if fo is None else f'{fo:.1%}'}) covered by {cov}")
    # page-level touch area
    if any((new.get('ev') or {}).get(k, '').strip() for k in ('touch_press', 'touch_release')):
        po, pn = int((mo == -1).sum()), int((mn == -1).sum())
        # pixels where the page got touches before but now some component
        stolen = (mo == -1) & (mn != -1)
        thieves = {}
        for j in np.unique(mn[stolen]):
            cc = new['comps'][j]; thieves[cc['n']] = (int((mn[stolen] == j).sum()), (cc.get('ev') or {}))
        L.append(f"PAGE-TOUCH {(new.get('ev') or {}).get('touch_release','')!r}/{(new.get('ev') or {}).get('touch_press','')!r} empty area old {po} new {pn}; taken by {thieves}")
    if L:
        out.append(f"===== {pid} {new['name']}")
        out += ['  ' + l for l in L]
print('\n'.join(out))
