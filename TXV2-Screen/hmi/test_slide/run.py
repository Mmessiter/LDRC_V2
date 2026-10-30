#!/usr/bin/env python3
"""(1.11.142/144) The slide text through the slab - under a finger (slideDrag) and in an ordinary redraw (slideFill) - draws the same pixels as the old full redraw.

slideDrag (src/main.cpp) letters the help/log viewer's box through a slab of internal RAM; drawTextIn is the old way. Both
are rendered on the Mac with the screen's own code (hmi/render_host): for every scroll offset V the box is first drawn the
old way at some OTHER offset A, then dragged to V through the slab, and the picture must equal the old way's own picture at
V, byte for byte - so every pixel the drag must change is proved, not only the ones it leaves. Left, centred and
right-aligned text, a vertically centred short text, a border, wrapped long lines, and offsets from 0 to the end.
   python3 hmi/test_slide/run.py            (builds the renderer when src/main.cpp is newer)"""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
RENDER = os.path.join(ROOT, 'hmi', 'render_host', 'gen', 'render')
SD = os.path.join(ROOT, 'sd')

def build():
    if os.path.exists(RENDER) and os.path.getmtime(RENDER) >= os.path.getmtime(os.path.join(ROOT, 'src', 'main.cpp')) \
            and os.path.getmtime(RENDER) >= os.path.getmtime(os.path.join(ROOT, 'hmi', 'render_host', 'render.cpp')):
        return
    r = subprocess.run(['sh', os.path.join(ROOT, 'hmi', 'render_host', 'build.sh')], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stdout[-2000:] + r.stderr[-4000:] + '\ntest_slide: the renderer did not build')

def lines_text(n, long_every=5, blank_every=7, width=100):
    out = []
    for i in range(n):
        if i and i % blank_every == 0: out.append(''); continue
        if i and i % long_every == 0:
            out.append(('Line %02d: ' % i) + ('a long line of text that runs on and on past the right edge of the box %d ' % i) * 3)
        else:
            out.append('Line %02d: head speed 2100 rpm, P 50 I 100 D 20 F 80  (the %dth line)   ' % (i, i))
    return out

def main():
    build()
    tests = []   # (name, setup lines, text lines, offsets)
    long30 = lines_text(30)
    short4 = ['One line', 'Two lines of text', '', 'Four']
    maxv = 30 * 24 - 370           # LogText: 747 x 370, font 2 = 24 px, no border -> maxval_y 350
    offs = [0, 1, 7, 8, 9, 23, 24, 25, 37, 100, 101, 177, 240, 333, maxv - 1, maxv]
    tests.append(('left', [], long30, offs))
    tests.append(('centred', ['@compint LogText xcen 1'], long30, offs))
    tests.append(('right', ['@compint LogText xcen 2'], long30, offs))
    tests.append(('vcentred_short', ['@compint LogText ycen 1'], short4, [0]))
    tests.append(('hcentred_short', ['@compint LogText xcen 1', '@compint LogText ycen 1'], short4, [0]))
    tests.append(('border3', ['@compint LogText borderw 3'], long30, [0, 5, 24, 200, maxv - 6 - 1]))
    tests.append(('wrapped', ['@compint LogText isbr 1'], long30, [0, 13, 24, 300]))
    out = tempfile.mkdtemp(prefix='slide_')
    cmds, shots = [], []
    for name, setup, text, offsets in tests:
        cmds.append('page LogView')
        cmds += setup
        cmds.append('LogText.txt="' + '\\r\\n'.join(text) + '"')
        for v in offsets:
            cmds.append('@slidefill 0'); cmds.append('LogText.val_y=%d' % v); cmds.append('@shot %s_std_%d' % (name, v))   # the reference: drawTextIn
            for a in (0, 999999, 24):                       # from the top, from the very end (clamped), from one line down
                if a == v: continue
                cmds.append('@slidefill 0'); cmds.append('LogText.val_y=%d' % a)
                cmds.append('@slide LogText %d' % v); cmds.append('@shot %s_fast_%d_from_%d' % (name, v, a)); shots.append((name, v, a, 'fast'))
                cmds.append('@slidefill 1'); cmds.append('LogText.val_y=%d' % a); cmds.append('LogText.val_y=%d' % v); cmds.append('@shot %s_fill_%d_from_%d' % (name, v, a)); shots.append((name, v, a, 'fill'))
    cf = os.path.join(out, 'cmds.txt'); open(cf, 'w').write('\n'.join(cmds) + '\n')
    r = subprocess.run([RENDER, SD, cf, out + '/'], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stdout[-2000:] + r.stderr[-2000:] + '\ntest_slide: the renderer failed')
    fallbacks = [l for l in r.stdout.splitlines() if l.startswith('@slide') and l.endswith('fallback')]
    checks = fails = 0
    for name, v, a, how in shots:
        checks += 1
        ref = open(os.path.join(out, '%s_std_%d.ppm' % (name, v)), 'rb').read()
        got = open(os.path.join(out, '%s_%s_%d_from_%d.ppm' % (name, how, v, a)), 'rb').read()
        if ref != got:
            fails += 1
            hdr = ref.find(b'255\n') + 4
            diff = [i for i in range(hdr, min(len(ref), len(got))) if ref[i] != got[i]][:1]
            where = ''
            if diff:
                px = (diff[0] - hdr) // 3; where = ' first at x %d y %d' % (px % 800, px // 800)
            print('FAIL %s: %s to %d from %d differs from the old full draw at %d%s' % (name, 'dragged' if how == 'fast' else 'slab-filled', v, a, v, where))
    for l in fallbacks: print('FAIL ' + l + ' (the slab path was not taken)'); fails += 1
    checks += 1 if not fallbacks else 0
    print('test_slide: %d checks, %d failures (%d pictures in %s)' % (checks, fails, len(shots), out))
    if not fails:
        print('ALL PASS')
        for f in os.listdir(out): os.remove(os.path.join(out, f))
        os.rmdir(out)
    return 1 if fails else 0

if __name__ == '__main__': sys.exit(main())
