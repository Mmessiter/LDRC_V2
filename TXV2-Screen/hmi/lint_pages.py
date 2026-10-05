#!/usr/bin/env python3
"""Look for visual flaws in the pages the screen shows, using the screen's own font widths (hmi/fontw.py):
text wider or taller than its box (as main.cpp drawTextIn lays it out), parts that overlap without one holding the other,
and parts that cross the edge of the navy card. Run: python3 hmi/lint_pages.py [page ids...] (default: every restyled page)."""
import json, os, sys
from fontw import width, W as WIDTHS
HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, '..', 'sd', 'hmi', 'pages')
FONT_H = {0: 32, 1: 64, 2: 24, 3: 24, 4: 16, 5: 32, 6: 28}
RESTYLED = [23, 24, 25, 4, 33, 9, 55, 51, 53, 54, 16, 17, 49, 50, 48, 3, 47, 8, 12, 46, 34, 35, 36, 37, 32, 39, 18, 29, 27, 31, 28,
            1, 42, 40, 7, 6, 5, 30, 52, 11, 10, 20, 19, 41, 15]
TEXTY = ('text', 'button', 'dual-state button', 'number')

def lines_of(s, font, maxw, wrap):                     # main.cpp textLines()
    out = []
    for line in s.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        if not wrap or width(font, line) <= maxw: out.append(line); continue
        while line:
            if width(font, line) <= maxw: out.append(line); break
            cut = None; pos = 0
            while True:
                sp = line.find(' ', pos)
                if sp < 0 or (sp > 0 and width(font, line[:sp]) > maxw): break
                cut = sp; pos = sp + 1
            if not cut:
                sp = line.find(' ', 1)
                if sp < 0: out.append(line); break
                cut = sp
            out.append(line[:cut]); line = line[cut:].lstrip(' ')
    while len(out) > 1 and not out[-1].strip(): out.pop()
    return out or ['']

def text_of(c):
    if c['t'] == 'number': return str(c.get('val', 0)).zfill(c.get('a', {}).get('lenth', 0) or 0)
    return c.get('txt', '')

def lint(pid):
    pg = json.load(open(os.path.join(PAGES, f'{pid}.json'))); found = []
    comps = [c for c in pg['comps'] if c.get('x') is not None and c['x'] >= 0 and c['t'] not in ('variable', 'timer', 'audio', 'hotspot')]
    for c in comps:
        if c['t'] not in TEXTY: continue
        a = c.get('a', {}); s = text_of(c)
        if not s: continue
        f = c.get('font', 0); fh = FONT_H.get(f, 28); bw = a.get('borderw', 0) if a.get('style', 0) in (1, 2, 3, 4) else 0
        wrap = c['t'] == 'text' and a.get('isbr', 0)
        ls = lines_of(s, f, c['w'], wrap)
        widest = max(width(f, l) for l in ls)
        room = c['w'] - 2 * bw - (0 if a.get('xcen', 0) == 1 or c['t'] in ('button', 'dual-state button') else 2)
        if widest > room: found.append(f'{c["n"]}: "{max(ls, key=lambda l: width(f, l))[:40]}" is {widest} px wide in font {f}, the box has {room}')
        if len(ls) * fh > c['h'] - 2 * bw: found.append(f'{c["n"]}: {len(ls)} line(s) of font {f} need {len(ls) * fh} px, the box is {c["h"]} high')
    for c in comps:                                           # words that run up against the next thing on their row
        if c['t'] != 'text' or not text_of(c) or '\r' in text_of(c) or '\n' in text_of(c): continue
        a = c.get('a', {}); f = c.get('font', 0); tw = width(f, text_of(c).rstrip()); xc = a.get('xcen', 0)   # (a trailing space is no ink)
        end = c['x'] + 2 + tw if xc == 0 else c['x'] + (c['w'] + tw) // 2 if xc == 1 else c['x'] + c['w'] - 2
        for o in comps:
            if o is c or o['n'] == 'card' or o['x'] < c['x'] + 4: continue
            ov = min(c['y'] + c['h'], o['y'] + o['h']) - max(c['y'], o['y'])
            if ov < min(c['h'], o['h']) // 2: continue
            if o['x'] - end < 8 and o['x'] + o['w'] > end - 1 and not (o['x'] <= c['x'] and o['x'] + o['w'] >= c['x'] + c['w']):
                found.append(f'{c["n"]}: its words end {o["x"] - end} px before {o["n"]}')
                break
    card = next((c for c in comps if c['n'] == 'card'), None)
    if card:
        cx0, cy0, cx1, cy1 = card['x'], card['y'], card['x'] + card['w'], card['y'] + card['h']
        for c in comps:
            if c['n'] == 'card': continue
            x0, y0, x1, y1 = c['x'], c['y'], c['x'] + c['w'], c['y'] + c['h']
            inside = x0 >= cx0 and y0 >= cy0 and x1 <= cx1 and y1 <= cy1
            apart = x1 <= cx0 or x0 >= cx1 or y1 <= cy0 or y0 >= cy1
            if not inside and not apart: found.append(f'{c["n"]} ({x0},{y0},{c["w"]},{c["h"]}) crosses the card edge')
            elif inside and min(x0 - cx0, cx1 - x1, y0 - cy0, cy1 - y1) < 4: found.append(f'{c["n"]} ({x0},{y0},{c["w"]},{c["h"]}) is {min(x0 - cx0, cx1 - x1, y0 - cy0, cy1 - y1)} px from the card edge')
    for i, a in enumerate(comps):
        for b in comps[i + 1:]:
            if 'card' in (a['n'], b['n']): continue
            ax1, ay1, bx1, by1 = a['x'] + a['w'], a['y'] + a['h'], b['x'] + b['w'], b['y'] + b['h']
            if a['x'] >= bx1 or b['x'] >= ax1 or a['y'] >= by1 or b['y'] >= ay1: continue
            a_holds = a['x'] <= b['x'] and a['y'] <= b['y'] and ax1 >= bx1 and ay1 >= by1
            b_holds = b['x'] <= a['x'] and b['y'] <= a['y'] and bx1 >= ax1 and by1 >= ay1
            kind = 'holds' if a_holds or b_holds else 'OVERLAPS'
            found.append(f'{a["n"]} ({a["x"]},{a["y"]},{a["w"]},{a["h"]}) {kind} {b["n"]} ({b["x"]},{b["y"]},{b["w"]},{b["h"]})')
    return pg['name'], found

if __name__ == '__main__':
    ids = [int(a) for a in sys.argv[1:]] or RESTYLED
    for pid in ids:
        name, found = lint(pid)
        print(f'== {pid} {name}: ' + ('nothing found' if not found else f'{len(found)}'))
        for f in found: print('   ' + f)
