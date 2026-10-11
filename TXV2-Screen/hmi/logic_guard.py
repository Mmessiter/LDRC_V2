#!/usr/bin/env python3
"""LOGIC GUARD for page restyles (10 Oct 2026, Malcolm: "make the screens look more beautiful ... Don't change the logic anywhere").

Compares every page in sd/hmi/pages with the same page at a base commit and refuses anything that could change what a page DOES:
  python3 hmi/logic_guard.py [--base COMMIT] [ids ...]      (default base: the commit before the polish, BASE below)

What may change on a component that was there:  x y w h, font, colours (c), sta, the default txt, centre, fresh, and in a{} only
  style borderw xcen ycen isbr hig dis psta wid, txt_maxl only UPWARDS.
In events (ev, on components and on the page) only the words inside  LogView.t0.txt="..."  keybdA.t1.txt="..."  keybdB.t1.txt="..."
  may change (the help viewer's title and the keypad's question: display text). Everything else in every script is byte-identical.
Never: a different name / id / type / global flag / keyboard key / value / options; a component removed (park it at x -2000 instead);
  a page's name, id, nav, background or size.
New components: plain 'text' only, a new id and name, and either no events or the page's own "carry on" touch (print "UKRULES").
Also warned (not refused): a component the Teensy writes into (its name is a string in the Teensy's code) that got NARROWER."""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
BASE = '1e117c7'                       # ESP32-board2: the renderer commit, just before the polish of 10 Oct 2026
TEENSY = os.path.expanduser('~/Documents/GitHub/TXV1B/TransmitterCode')
FREE = {'x', 'y', 'w', 'h', 'font', 'c', 'sta', 'txt', 'centre', 'fresh'}
FREE_A = {'style', 'borderw', 'xcen', 'ycen', 'isbr', 'hig', 'dis', 'psta', 'wid'}
TITLE_LIT = re.compile(r'((?:LogView\.t0|keybdA\.t1|keybdB\.t1)\.txt=)"[^"\n]*"')
CARRY_ON = {'print "UKRULES"'}

def norm(ev):
    return {k: TITLE_LIT.sub(r'\1"*"', v) for k, v in (ev or {}).items()}

def base_page(pid, base):
    rel = f'board4/nextion-emulator/sd/hmi/pages/{pid}.json'
    r = subprocess.run(['git', 'show', f'{base}:{rel}'], cwd=ROOT, capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else None

_teensy_names = None
def teensy_writes(name):
    global _teensy_names
    if _teensy_names is None:
        txt = ''
        for d, _, fs in os.walk(TEENSY):
            if '.pio' in d: continue
            for f in fs:
                if f.endswith(('.h', '.cpp')):
                    try: txt += open(os.path.join(d, f), errors='ignore').read()
                    except OSError: pass
        _teensy_names = set(re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)[".]', txt))
    return name in _teensy_names

def check(pid, base=BASE):
    errs, warns = [], []
    old = base_page(pid, base)
    new = json.load(open(os.path.join(ROOT, 'sd', 'hmi', 'pages', f'{pid}.json')))
    if old is None: return [f'{pid}: no base page'], []
    for k in ('name', 'id', 'nav', 'bg', 'w', 'h'):
        if old.get(k) != new.get(k): errs.append(f'{pid}: page {k} changed')
    if norm(old.get('ev')) != norm(new.get('ev')): errs.append(f'{pid}: page events changed')
    on = {c['n']: c for c in old['comps']}
    seen_n, seen_i = set(), set()
    for c in new['comps']:
        if c['n'] in seen_n: errs.append(f'{pid}: duplicate name {c["n"]}')
        if c['i'] in seen_i: errs.append(f'{pid}: duplicate id {c["i"]} ({c["n"]})')
        seen_n.add(c['n']); seen_i.add(c['i'])
        o = on.get(c['n'])
        if o is None:
            if c['t'] != 'text': errs.append(f'{pid}: new {c["n"]} is a {c["t"]} (only plain text may be added)')
            if any(x['i'] == c['i'] for x in old['comps']): errs.append(f'{pid}: new {c["n"]} reuses id {c["i"]}')
            for k, v in (c.get('ev') or {}).items():
                if v.strip() not in CARRY_ON: errs.append(f'{pid}: new {c["n"]} has an event ({k}: {v[:40]!r})')
            if (c.get('a') or {}).get('key', 255) not in (255, None): errs.append(f'{pid}: new {c["n"]} opens a keyboard')
            continue
        for k in set(o) | set(c):
            if k in FREE or k == 'a': continue
            if k == 'ev':
                if norm(o.get('ev')) != norm(c.get('ev')): errs.append(f'{pid}: {c["n"]} events changed')
            elif o.get(k) != c.get(k): errs.append(f'{pid}: {c["n"]} {k} changed ({o.get(k)!r} -> {c.get(k)!r})')
        oa, na = o.get('a') or {}, c.get('a') or {}
        for k in set(oa) | set(na):
            if k in FREE_A: continue
            if k == 'txt_maxl':
                if (na.get(k) or 0) < (oa.get(k) or 0): errs.append(f'{pid}: {c["n"]} txt_maxl lowered')
            elif oa.get(k) != na.get(k): errs.append(f'{pid}: {c["n"]} a.{k} changed ({oa.get(k)!r} -> {na.get(k)!r})')
        if 'w' in o and 'w' in c and c['w'] < o['w'] and c.get('x', 0) > -1000 and teensy_writes(c['n']) and c['t'] in ('text', 'button', 'number'):
            warns.append(f'{pid}: {c["n"]} (written by the Teensy) narrower {o["w"]} -> {c["w"]}')
    for n in on:
        if n not in seen_n: errs.append(f'{pid}: {n} removed (park it at x -2000 instead)')
    return errs, warns

if __name__ == '__main__':
    args = sys.argv[1:]; base = BASE
    if args[:1] == ['--base']: base = args[1]; args = args[2:]
    ids = [int(a) for a in args] or sorted(int(f[:-5]) for f in os.listdir(os.path.join(ROOT, 'sd', 'hmi', 'pages')) if f.endswith('.json'))
    bad = 0
    for pid in ids:
        e, w = check(pid, base)
        for m in e: print('REFUSED', m)
        for m in w: print('warning', m)
        bad += len(e)
    print(f'logic guard: {len(ids)} page(s), {bad} refusal(s)')
    sys.exit(1 if bad else 0)
