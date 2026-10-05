#!/usr/bin/env python3
"""Render pages with the screen's own code (hmi/render_host) to PNG files, to look at them on the Mac.
  python3 hmi/render_pages.py OUTDIR SCRIPT.txt [...]   run command scripts (see render_host/render.cpp), one PNG per @shot
  python3 hmi/render_pages.py OUTDIR --bare [ids...]     each page as it loads, before the Teensy fills it (default: the restyled pages)
Needs Pillow (any Python that has it: set PY=...)."""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
RENDER = os.path.join(HERE, 'render_host', 'gen', 'render')
from lint_pages import RESTYLED

def to_png(ppm):
    from PIL import Image
    png = ppm[:-4] + '.png'; Image.open(ppm).save(png); os.remove(ppm); return png

def run(script, outdir):
    r = subprocess.run([RENDER, os.path.join(ROOT, 'sd'), script, outdir + '/'], capture_output=True, text=True)
    if r.returncode or r.stderr.strip(): print(f'{os.path.basename(script)}: {r.stderr.strip() or r.stdout.strip()}')
    return [to_png(os.path.join(outdir, f)) for f in sorted(os.listdir(outdir)) if f.endswith('.ppm')]

if __name__ == '__main__':
    if not os.path.exists(RENDER): subprocess.run([os.path.join(HERE, 'render_host', 'build.sh')], check=True)
    outdir = sys.argv[1]; os.makedirs(outdir, exist_ok=True); args = sys.argv[2:]
    if args and args[0] == '--bare':
        names = {p['id']: p['name'] for p in json.load(open(os.path.join(ROOT, 'sd', 'hmi', 'index.json')))['pages']}
        ids = [int(a) for a in args[1:]] or RESTYLED
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as t:
            t.write('Screen_Background=8\n')
            for i in ids: t.write(f'page {names[i]}\n@shot {i}_bare\n')
        made = run(t.name, outdir); os.remove(t.name)
    else:
        made = []
        for s in args: made += run(s, outdir)
    print(f'{len(made)} picture(s) in {outdir}')
