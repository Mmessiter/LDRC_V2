#!/usr/bin/env python3
"""pages.json + pictures + audio  ->  sd/hmi/  (what the emulator reads from the TF card)
   sd/hmi/index.json        page names in id order, fonts, picture sizes
   sd/hmi/pages/<id>.json   compact page: bg, components (geometry, colours, font, txt/val, attrs), event code
   sd/hmi/pic/<id>.565      u16 w, u16 h, then RGB565 little-endian rows (no compression: fast to blit)
   sd/hmi/audio/<id>.wav    made louder without distortion by loud_audio.py (clicks and beeps as extracted)"""
import json, os, shutil, struct, sys
from PIL import Image
here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, '..', 'sd', 'hmi')
d = json.load(open(os.path.join(here, 'pages.json')))
res = json.load(open(os.path.join(here, 'resources.json')))
fonts = json.load(open(os.path.join(here, 'fonts.json')))
for sub in ('pages', 'pic', 'audio'): os.makedirs(os.path.join(out, sub), exist_ok=True)

KEEP_ATTRS = ('xcen', 'ycen', 'borderw', 'lenth', 'format', 'dis', 'dez', 'tim', 'en', 'maxval', 'minval', 'mode', 'wid', 'hig', 'psta', 'txt_maxl', 'isbr', 'pw', 'style', 'vvs0', 'vvs1', 'dir', 'key')
pages = []
for p in d['pages']:
    comps = []
    for c in p['components']:
        col = {k: v['rgb565'] for k, v in (c.get('colours') or {}).items()}
        pics = {k: v for k, v in (c.get('pictures') or {}).items() if v is not None}
        EVK = {'touch_press': 'p', 'touch_release': 'r', 'touch_move': 'm', 'timer': 't', 'play_end': 'e'}
        ev = {EVK.get(k, k): v for k, v in (c.get('events') or {}).items() if v}   # p / r / m / t / e
        cc = {'n': c['name'], 'i': c['id'], 't': c['type'], 'g': c.get('scope', 'local')[0]}
        for k in ('x', 'y', 'w', 'h', 'font', 'sta'):
            if k in c: cc[k] = c[k]
        if col: cc['c'] = col
        if pics: cc['pic'] = pics
        if 'txt' in c: cc['txt'] = c['txt']
        if 'val' in c: cc['val'] = c['val']
        if c.get('options'): cc['opt'] = c['options']
        a = {k: v for k, v in (c.get('attrs') or {}).items() if k in KEEP_ATTRS}
        if a: cc['a'] = a
        if ev: cc['ev'] = ev
        comps.append(cc)
    pev = {k: v for k, v in (p.get('events') or {}).items() if v}
    page = {'name': p['name'], 'id': p['id'], 'w': p['w'], 'h': p['h'], 'bg': p.get('background'), 'nav': p.get('page_attrs'), 'ev': pev, 'comps': comps}
    json.dump(page, open(os.path.join(out, 'pages', f"{p['id']}.json"), 'w'), separators=(',', ':'))
    pages.append({'id': p['id'], 'name': p['name'], 'n': len(comps)})

pics = {}
for pid, info in res['pictures'].items():
    src = os.path.join(here, info['file'])
    im = Image.open(src).convert('RGB')
    w, h = im.size
    with open(os.path.join(out, 'pic', f'{pid}.565'), 'wb') as f:
        f.write(struct.pack('<HH', w, h))
        px = im.tobytes()
        buf = bytearray(w * h * 2)
        for i in range(w * h):
            r, g, b = px[3*i], px[3*i+1], px[3*i+2]
            v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            buf[2*i] = v & 0xFF; buf[2*i+1] = v >> 8
        f.write(buf)
    pics[pid] = {'w': w, 'h': h}
sys.path.insert(0, here); import loud_audio                  # the clips, louder without distortion (see that file)
for aid, info in res.get('audio', {}).items():
    src = os.path.join(here, info['file']) if 'file' in info else None
    if src and os.path.exists(src): loud_audio.build_clip(src, os.path.join(out, 'audio', f'{aid}.wav'))
json.dump({'display': d['display'], 'pages': pages, 'fonts': {k: {'name': v['name'], 'h': v['height']} for k, v in fonts.items()}, 'pictures': pics},
          open(os.path.join(out, 'index.json'), 'w'), indent=1)
print(f"{len(pages)} pages, {len(pics)} pictures, audio {len(os.listdir(os.path.join(out,'audio')))} -> {out}")

# The anti-aliased glyphs (4-bpp alpha 0..7) sit beside the pages; the screen blends them at run time.
import shutil
for fid in range(7):
    src = os.path.join(here, 'fonts', '%d_aa.bin' % fid)
    if os.path.exists(src):
        shutil.copy(src, os.path.join(here, '..', 'sd', 'hmi', 'font%d_aa.bin' % fid))

# Malcolm's tweaks on top of the extracted HMI (colours etc.): hmi/overrides.json
import subprocess
subprocess.run([sys.executable, os.path.join(here, 'apply_overrides.py')], check=True)
