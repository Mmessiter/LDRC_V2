#!/usr/bin/env python3
# A preview of a page as the screen draws it, on the Mac: python3 dev/preview_page.py sd/hmi/pages/25.json /tmp/p.png [background picture id]
# Approximate (TrueType Arial for the HMI bitmap fonts), good for judging a layout before it goes to a transmitter.
# Needs Pillow: python3 -m venv /tmp/pv && /tmp/pv/bin/pip install pillow && /tmp/pv/bin/python dev/preview_page.py ...
import json, sys, struct, os
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'hmi')
FONTS = {0: ('Arial Bold.ttf', 32), 1: ('Arial Bold.ttf', 64), 2: ('Arial.ttf', 24), 3: ('Arial.ttf', 22), 4: ('Arial.ttf', 15), 5: ('Courier New Bold.ttf', 32), 6: ('Arial.ttf', 28)}
_cache = {}
def font(i):
    if i not in _cache:
        f, h = FONTS.get(i, FONTS[6]); _cache[i] = ImageFont.truetype('/System/Library/Fonts/Supplemental/' + f, int(h * 0.82))
    return _cache[i]
def c565(v):
    v = int(v or 0); return (((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31)
def shade(v, pct):
    r, g, b = c565(v)
    if pct > 0: r, g, b = [x + (255 - x) * pct // 100 for x in (r, g, b)]
    else: r, g, b = [x * (100 + pct) // 100 for x in (r, g, b)]
    return (r, g, b)
def load_pic(pid):
    p = os.path.join(ROOT, 'pic', f'{pid}.565')
    if not os.path.exists(p): return None
    raw = open(p, 'rb').read(); w, h = struct.unpack('<HH', raw[:4])
    im = Image.new('RGB', (w, h)); px = im.load()
    for y in range(h):
        row = raw[4 + y * w * 2: 4 + (y + 1) * w * 2]
        for x in range(w):
            v = row[2 * x] | (row[2 * x + 1] << 8); px[x, y] = c565(v)
    return im
def text_in(d, x, y, w, h, f, col, s, xc, yc):
    if not s: return
    ft = font(f); lines = s.replace('\r\n', '\n').split('\n')
    lh = FONTS.get(f, FONTS[6])[1]; total = lh * len(lines)
    ty = y + (h - total) // 2 if yc == 1 else (y + h - total if yc == 2 else y)
    for i, line in enumerate(lines):
        tw = d.textlength(line, font=ft)
        tx = x + (w - tw) / 2 if xc == 1 else (x + w - tw - 4 if xc == 2 else x + 4)
        d.text((tx, ty + i * lh + lh * 0.12), line, font=ft, fill=col)
def frame(d, c, bg, down):
    x, y, w, h = c['x'], c['y'], c['w'], c['h']; a = c.get('a', {}); st = a.get('style', 0); bw = a.get('borderw', 0)
    if st == 1:
        for i in range(max(1, bw)): d.rectangle([x + i, y + i, x + w - 1 - i, y + h - 1 - i], outline=c565(c.get('c', {}).get('borderc', 0)))
        return
    if st < 2: return
    sunk = st == 2 or (st == 4 and down)
    tl = shade(bg, -45) if sunk else shade(bg, 60); br = shade(bg, 60) if sunk else shade(bg, -45)
    for i in range(2):
        d.line([x + i, y + i, x + w - 1 - i, y + i], fill=tl); d.line([x + i, y + i, x + i, y + h - 1 - i], fill=tl)
        d.line([x + i, y + h - 1 - i, x + w - 1 - i, y + h - 1 - i], fill=br); d.line([x + w - 1 - i, y + i, x + w - 1 - i, y + h - 1 - i], fill=br)
def render(page_file, out, bgpic=None, values=None):
    pg = json.load(open(page_file)); values = values or {}
    im = Image.new('RGB', (800, 480), (0, 0, 0))
    bg = pg.get('bg', {})
    if bg.get('mode') == 'image':
        p = load_pic(bgpic if bgpic is not None else bg.get('picture', 3))
        if p: im.paste(p, (0, 0))
    elif bg.get('mode') == 'solid colour': im.paste(c565(bg.get('rgb565', 0)), [0, 0, 800, 480])
    d = ImageDraw.Draw(im)
    for c in pg['comps']:
        t = c.get('t'); 
        if t in ('variable', 'timer', 'audio') or c.get('x') is None: continue
        if c['x'] >= 800 or c['y'] >= 480 or c['x'] + c['w'] <= 0: continue
        col = c.get('c', {}); a = c.get('a', {}); x, y, w, h = c['x'], c['y'], c['w'], c['h']
        sta = c.get('sta', 1); txt = values.get(c['n'], c.get('txt', ''))
        if t in ('text', 'number'):
            if sta == 1: d.rectangle([x, y, x + w - 1, y + h - 1], fill=c565(col.get('bco', 0)))
            frame(d, c, col.get('bco', 0), False)
            s = str(values.get(c['n'], c.get('val', 0))) if t == 'number' else txt
            text_in(d, x, y, w, h, c.get('font', 0), c565(col.get('pco', 65535)), s, a.get('xcen', 0), a.get('ycen', 0))
        elif t in ('button', 'dual-state button'):
            if sta != 3: d.rectangle([x, y, x + w - 1, y + h - 1], fill=c565(col.get('bco', 0))); frame(d, c, col.get('bco', 0), False)
            text_in(d, x, y, w, h, c.get('font', 0), c565(col.get('pco', 0)), txt, a.get('xcen', 1) or 1, a.get('ycen', 1) or 1)
        elif t == 'textselect':                          # a wheel: the chosen row in the middle band, rows above and below it
            bw = a.get('borderw', 0); rowh = a.get('hig', 35)
            d.rectangle([x, y, x + w - 1, y + h - 1], fill=c565(col.get('bco', 65535)))
            for i in range(bw): d.rectangle([x + i, y + i, x + w - 1 - i, y + h - 1 - i], outline=c565(col.get('borderc', 0)))
            ix, iy, iw, ih = x + bw, y + bw, w - 2 * bw, h - 2 * bw
            band = iy + (ih - rowh) // 2
            opts = values.get(c['n'] + '.options', c.get('opt', []) or ['(empty)']); sel = values.get(c['n'] + '.sel', 0)
            layer = Image.new('RGB', (iw, ih)); ld = ImageDraw.Draw(layer); ld.rectangle([0, 0, iw, ih], fill=c565(col.get('bco', 65535)))
            ft = font(c.get('font', 6)); pad = 14
            for k in range(-6, 7):
                i = sel + k
                if i < 0 or i >= len(opts): continue
                ry = band - iy + k * rowh
                s = opts[i]
                while ld.textlength(s, font=ft) > iw - 2 * pad and len(s) > 1: s = s[:-4] + '...' if not s.endswith('...') else s[:-4] + '...'
                ld.text((pad, ry + (rowh - FONTS.get(c.get('font', 6), FONTS[6])[1]) / 2 + 3), s, font=ft, fill=c565(col.get('pco2', 0) if k == 0 else col.get('pco', 0)))
            if a.get('dis'):
                ld.line([0, band - iy, iw, band - iy], fill=c565(col.get('pco1', 0))); ld.line([0, band - iy + rowh - 1, iw, band - iy + rowh - 1], fill=c565(col.get('pco1', 0)))
            im.paste(layer, (ix, iy))
        elif t in ('checkbox', 'radio'):
            sz = min(w, h); on = values.get(c['n'], c.get('val', 0))
            if t == 'radio':
                r = sz // 2 - 1; cx, cy = x + w // 2, y + h // 2
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c565(col.get('bco', 65535)), outline=shade(col.get('bco', 65535), -25))
                if on: rr = max(3, r * 45 // 100); d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=c565(col.get('pco', 0)))
            else:
                d.rectangle([x, y, x + sz - 1, y + sz - 1], fill=c565(col.get('bco', 65535)), outline=shade(col.get('bco', 65535), -40))
                if on: i2 = max(3, sz // 4); d.rectangle([x + i2, y + i2, x + sz - 1 - i2, y + sz - 1 - i2], fill=c565(col.get('pco', 0)))
        elif t == 'slider':
            d.rectangle([x, y + h // 2 - 3, x + w - 1, y + h // 2 + 3], fill=c565(col.get('bco', 50712)))
            v = c.get('val', 50); mx = max(1, a.get('maxval', 100) - a.get('minval', 0)); kx = x + (w - 20) * (v - a.get('minval', 0)) // mx
            d.rectangle([kx, y, kx + 20, y + h - 1], fill=c565(col.get('pco', 0)))
        elif t == 'combobox':
            d.rectangle([x, y, x + w - 1, y + h - 1], fill=c565(col.get('bco', 65535))); frame(d, c, col.get('bco', 65535), False)
            opts = c.get('opt', []); s0 = opts[c.get('val', 0)] if opts and 0 <= c.get('val', 0) < len(opts) else txt
            text_in(d, x, y, w - h, h, c.get('font', 6), c565(col.get('pco', 0)), s0, 0, 1)
            d.polygon([(x + w - h * 0.75, y + h * 0.4), (x + w - h * 0.25, y + h * 0.4), (x + w - h / 2, y + h * 0.65)], fill=c565(col.get('pco', 0)))
        elif t == 'external picture':
            d.rectangle([x, y, x + w - 1, y + h - 1], outline=(120, 120, 120)); text_in(d, x, y, w, h, 2, (160, 160, 160), '(model picture)', 1, 1)
        elif t == 'progress bar':
            if c.get('vis', 1) == 0: continue
            d.rectangle([x, y, x + w - 1, y + h - 1], fill=c565(col.get('bco', 0)))
            v = c.get('val', 0); d.rectangle([x, y, x + w * v // 100 - 1, y + h - 1], fill=c565(col.get('pco', 0)))
        elif t == 'switch':
            r = h // 2; on = values.get(c['n'], c.get('val', 0))
            d.rounded_rectangle([x, y, x + w - 1, y + h - 1], r, fill=c565(col.get('bco2', 2016) if on else col.get('bco', 50712)))
            cx = x + w - r if on else x + r; rr = max(2, r - 3); d.ellipse([cx - rr, y + r - rr, cx + rr, y + r + rr], fill=c565(col.get('pco', 65535)))
    im.save(out)
if __name__ == '__main__':
    vals = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None
    render(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != '-' else None, vals)
