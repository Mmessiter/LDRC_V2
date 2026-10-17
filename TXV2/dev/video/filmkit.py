#!/usr/bin/env python3
"""The LDRC film kit (17 Oct 2026): what every instructional film shares, so that a film is a short script (films/*.py).
Every screen is drawn by the transmitter screen's own code (ESP32-board2 hmi/render_pages.py, from its scenarios), the voice
is Kokoro (an open speech model run on this Mac: nothing sent anywhere) or the Mac's own, the finger and the captions are
drawn here, and the result is an MP4 (phones, computers) or, with LDRC_TARGET=screen, an LDRC film for the transmitter's
own screen (sd/hmi/films/<NAME>.ldf + .wav, played from the help pages' Films menu, screen 1.11.87).

Malcolm's rules for the pace (17 Oct): "a little bit more slow ... the viewer probably understands nothing at the start";
"the redrawing of the screen is not terribly fast ... make sure that the pace of the video and of the talking is no
quicker than that"; and "do the video animations and the audio non-simultaneously". So: each new page is shown in
silence first; the voice speaks only over a still picture; the finger moves, presses and the page changes only in silence.

   PY/bin/python dev/video/films/<film>.py [OUTDIR]
   LDRC_TARGET=screen  the film for the transmitter (else an MP4 in OUTDIR, default dev/out/video/<NAME>)
   LDRC_VOICE=kokoro:bf_emma (default) | kokoro:bm_george | say:Daniel     LDRC_SPEED (0.9 for Kokoro)
   KOKORO_DIR (default /Volumes/2TB SSD/ClaudeScratch/kokoro-model: kokoro-v1.0.onnx, voices-v1.0.bin)
A Python with Pillow, imageio-ffmpeg and kokoro-onnx."""
import io, os, struct, subprocess, sys, wave
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

EMU = os.path.expanduser('~/Documents/GitHub/ESP32-board2/board4/nextion-emulator')
SCN = os.path.join(EMU, 'hmi', 'scenarios')
FF = imageio_ffmpeg.get_ffmpeg_exe()
LOOK, GLIDE, REST, PRESS, FADE, AFTER = 1.2, 0.9, 0.5, 0.45, 0.8, 0.7   # seconds: a page looked at; the finger's way; ...

def prefix(scenario, shot, edits=()):
    """A scenario's commands up to one of its shots (they are cumulative), the other shots left out, with edits (old, new)."""
    out = []
    for l in open(os.path.join(SCN, scenario)).read().split('\n'):
        if l.startswith('@shot '):
            if l.strip() == '@shot ' + shot: break
            continue
        out.append(l)
    text = '\n'.join(out) + '\n'
    for old, new in edits:
        assert old in text, '%s: "%s" not found' % (scenario, old[:60])
        text = text.replace(old, new)
    return text

import json
_PAGES = {}
def _page(page):
    """a page's definition, by its number or its name (ESP32-board2 sd/hmi/pages/<id>.json)"""
    if page not in _PAGES:
        pid = page
        if not isinstance(page, int):
            idx = json.load(open(os.path.join(EMU, 'sd', 'hmi', 'index.json')))
            pid = next(p['id'] for p in idx['pages'] if p['name'] == page)
        _PAGES[page] = json.load(open(os.path.join(EMU, 'sd', 'hmi', 'pages', '%d.json' % pid)))
    return _PAGES[page]
def comp(page, name=None, txt=None):
    """a component of a page, by its name or by the words on it: its rectangle (x, y, w, h)"""
    for c in _page(page)['comps']:
        if c.get('x') is None: continue
        if (name is not None and c['n'] == name) or (txt is not None and (c.get('txt') or '').strip() == txt):
            return c['x'], c['y'], c['w'], c['h']
    raise SystemExit('no component %s on page %s' % (name or txt, page))
def at(page, name=None, txt=None):
    """(1.11.88: Malcolm, "the indication of the pointer hitting a button was frequently rather inaccurate") the exact centre
    of a button, from the page's own definition - never a number typed by hand"""
    x, y, w, h = comp(page, name, txt)
    return x + w // 2, y + h // 2
def knob(page, name, val):
    """the centre of a slider's knob at a value (as the screen draws it: the track inset by the knob's radius)"""
    c = next(c for c in _page(page)['comps'] if c['n'] == name)
    a = c.get('a') or {}; lo, hi = a.get('minval', 0), a.get('maxval', 100); r = c['h'] // 2
    return int(round(c['x'] + r + (c['w'] - 2 * r) * (val - lo) / float(hi - lo))), c['y'] + r

JPEGDEC_SRC = os.path.join(EMU, '.pio', 'libdeps', 'ota', 'JPEGDEC', 'src')
_CHECKER = r'''
#include <cstdio>
#include <vector>
#include "JPEGDEC.h"
static int draw(JPEGDRAW *) { return 1; }
static JPEGDEC j;
int main(int argc, char **argv) {   // a file of pictures, each a u32 length then the JPEG: prints the number of each one JPEGDEC will not decode
    FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
    std::vector<unsigned char> b; unsigned char c[65536]; size_t n; while ((n = fread(c, 1, sizeof c, f)) > 0) b.insert(b.end(), c, c + n); fclose(f);
    size_t at = 0; int i = 0;
    while (at + 4 <= b.size()) {
        const unsigned len = b[at] | (b[at + 1] << 8) | (b[at + 2] << 16) | ((unsigned) b[at + 3] << 24); at += 4;
        const int ok = j.openRAM(&b[at], (int) len, draw) && (j.setPixelType(RGB565_LITTLE_ENDIAN), j.decode(0, 0, 0));
        j.close(); if (!ok) printf("%d\n", i);
        at += len; ++i;
    }
    return 0;
}
'''
def _checker(outdir):
    """the screen's own JPEG decoder, built on the Mac (1.11.88): JPEGDEC 1.8.4 refuses some pictures ('decode error') that
    other decoders read - a few in a film, depending on what is in them - so every picture is tried with it before it goes in"""
    exe = os.path.join(outdir, 'jpegdec_check')
    if not os.path.exists(exe):
        if not os.path.isdir(JPEGDEC_SRC): sys.exit('JPEGDEC not found in %s (build the screen once: pio run -e ota)' % JPEGDEC_SRC)
        src = os.path.join(outdir, 'jpegdec_check.cpp'); open(src, 'w').write(_CHECKER)
        subprocess.run(['clang++', '-std=c++17', '-O1', '-w', '-I', JPEGDEC_SRC, '-o', exe, src, os.path.join(JPEGDEC_SRC, 'JPEGDEC.cpp')], check=True)
    return exe
def _refused(exe, outdir, jpegs):
    path = os.path.join(outdir, 'check.bin')
    with open(path, 'wb') as f:
        for j in jpegs: f.write(struct.pack('<I', len(j)) + j)
    r = subprocess.run([exe, path], capture_output=True, text=True, check=True)
    return set(int(x) for x in r.stdout.split())

class _Frames(list):
    """the film's pictures, and where the finger was drawn in each one (so a check can look for the dot in any of them)"""
    def __init__(self, film): super().__init__(); self.film = film; self.pos = []
    def append(self, f): super().append(f); self.pos.append((self.film.fx, self.film.fy))

class Film:
    def __init__(self, name, title, subtitle):
        self.name, self.title, self.subtitle = name, title, subtitle
        self.target = os.environ.get('LDRC_TARGET', 'mp4')
        self.out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'video', name)
        for d in ('scripts', 'shots', 'voice'): os.makedirs(os.path.join(self.out, d), exist_ok=True)
        self.scripts, self.lines, self.img, self.dur = {}, [], {}, {}
        self.frames, self.segments = _Frames(self), []
        self.page = None; self.cap = None; self.fx = self.fy = None; self.fpress = 0.0
        self.touches = []                                     # (the frame, x, y, the page) at every press and slider stop: finish() checks each
        self._layout()

    # ------------------------------------------------------------ the screens and the voice
    def shot(self, key, text): self.scripts[key] = text if text.rstrip().endswith('@shot ' + key) else text.rstrip('\n') + '\n@shot %s\n' % key
    def line(self, key, text): self.lines.append((key, text))
    def prepare(self):
        for k, v in self.scripts.items(): open(os.path.join(self.out, 'scripts', k + '.txt'), 'w').write(v)
        r = subprocess.run([sys.executable, os.path.join(EMU, 'hmi', 'render_pages.py'), os.path.join(self.out, 'shots')] + [os.path.join(self.out, 'scripts', k + '.txt') for k in self.scripts], capture_output=True, text=True, cwd=EMU)
        for k in self.scripts:
            p = os.path.join(self.out, 'shots', k + '.png')
            if not os.path.exists(p): sys.exit('shot %s was not drawn: %s %s' % (k, r.stdout[-400:], r.stderr[-400:]))
            self.img[k] = Image.open(p).convert('RGB')
        voice = os.environ.get('LDRC_VOICE', 'kokoro:bf_emma'); engine, vname = voice.split(':', 1)
        self.voice_name = vname
        speed = float(os.environ.get('LDRC_SPEED', '0.9' if engine == 'kokoro' else '1.0'))
        kokoro = None
        if engine == 'kokoro':
            import numpy as np
            from kokoro_onnx import Kokoro, EspeakConfig
            import espeakng_loader, shutil
            KD = os.environ.get('KOKORO_DIR', '/Volumes/2TB SSD/ClaudeScratch/kokoro-model')
            ED = os.path.join(KD, 'espeak-ng-data')   # (eSpeak ignores a data path of 160 characters or more: kept short, beside the model)
            if not os.path.isdir(ED): shutil.copytree(espeakng_loader.get_data_path(), ED)
            kokoro = Kokoro(os.path.join(KD, 'kokoro-v1.0.onnx'), os.path.join(KD, 'voices-v1.0.bin'),
                            espeak_config=EspeakConfig(lib_path=espeakng_loader.get_library_path(), data_path=ED))
        for k, text in self.lines:
            raw = os.path.join(self.out, 'voice', k + ('.aiff' if engine == 'say' else '.raw.wav')); wav = os.path.join(self.out, 'voice', k + '.wav')
            if engine == 'say':
                subprocess.run(['say', '-v', vname, '-r', str(int(172 * speed)), '-o', raw, text], check=True)
            else:
                samples, sr = kokoro.create(text, voice=vname, speed=speed, lang='en-gb')
                pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
                with wave.open(raw, 'w') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm)
            subprocess.run([FF, '-y', '-loglevel', 'error', '-i', raw, '-ar', '44100', '-ac', '1', wav], check=True)
            with wave.open(wav) as w: self.dur[k] = w.getnframes() / w.getframerate()

    # ------------------------------------------------------------ the picture
    def _layout(self):
        if self.target == 'screen': self.W, self.H, self.SCALE = 800, 480, 0.9; self.SX, self.SY = 40, 0
        else: self.W, self.H, self.SCALE = 1280, 720, 1.25; self.SX, self.SY = 140, 18
        self.FPS = 30; FS = max(self.SCALE / 1.25, 0.72); self.FS = FS
        def font(size, bold=False):
            for f in (('/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold else '/System/Library/Fonts/Supplemental/Arial.ttf'), '/System/Library/Fonts/Helvetica.ttc'):
                if os.path.exists(f): return ImageFont.truetype(f, size)
            return ImageFont.load_default()
        self.F_CAP, self.F_TITLE, self.F_SUB = font(int(36 * FS), True), font(int(64 * FS), True), font(int(34 * FS))
        self.BG = Image.new('RGB', (self.W, self.H), (22, 28, 38)); d = ImageDraw.Draw(self.BG)
        for y in range(self.H): d.line([(0, y), (self.W, y)], fill=(22 + y // 40, 28 + y // 40, 38 + y // 30))
        self._framed = {}
    def _frame(self, page):
        if getattr(page, 'ldrc_card', False): return page.copy()   # (a card: made at the film's own size by card())
        # (until 17 Oct a picture of the film's own size counted as a card - and on the transmitter (800 x 480) every page is
        # that size: the pages went in whole while the finger was placed for the page at 90 %, a tenth too high and towards
        # the middle. Malcolm's photos showed it: "The pointer is still not accurate. It's usually rather too high.")
        key = id(page)
        if key not in self._framed:
            f = self.BG.copy(); s = page.resize((int(800 * self.SCALE), int(480 * self.SCALE)), Image.LANCZOS)
            if self.target != 'screen': ImageDraw.Draw(f).rounded_rectangle([self.SX - 14, self.SY - 14, self.SX + s.width + 14, self.SY + s.height + 14], radius=18, fill=(8, 8, 10))
            f.paste(s, (self.SX, self.SY)); self._framed[key] = (page, f)
        return self._framed[key][1].copy()
    def _caption(self, f, text):
        if not text: return f
        d = ImageDraw.Draw(f, 'RGBA'); tw = d.textlength(text, font=self.F_CAP)
        y0 = self.SY + int(480 * self.SCALE) + (26 if self.target != 'screen' else 10); ph = int(58 * self.FS)
        d.rounded_rectangle([(self.W - tw) / 2 - 24, y0 - 8, (self.W + tw) / 2 + 24, y0 - 8 + ph], radius=12, fill=(255, 255, 255, 235))
        d.text(((self.W - tw) / 2, y0), text, font=self.F_CAP, fill=(20, 24, 32)); return f
    def _finger(self, f, x, y, press=0.0, ripple=None):
        d = ImageDraw.Draw(f, 'RGBA'); cx, cy = self.SX + x * self.SCALE, self.SY + y * self.SCALE; k = max(self.FS, 0.8); r = (26 - 6 * press) * k
        if ripple is not None:
            rr = (28 + 60 * ripple) * k; a = int(200 * (1 - ripple)); d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(255, 214, 64, a), width=5)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 150), outline=(255, 214, 64, 255), width=5)
        d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(230, 40, 40, 255))   # (1.11.88) the exact point it touches
        return f
    def _sign(self, f):
        """(screen 1.11.89) a pause sign in the corner, in every picture of a film for the transmitter - Malcolm: "how to inform
        the user that a press on the video will bring this option" (a tap pauses it: the slider and Back, Play, Next, Films)"""
        if self.target != 'screen': return f
        d = ImageDraw.Draw(f); x0, y0 = self.W - 52, self.H - 40
        d.rounded_rectangle([x0, y0, x0 + 38, y0 + 34], radius=8, fill=(44, 52, 68), outline=(150, 160, 178), width=2)
        d.rectangle([x0 + 11, y0 + 9, x0 + 16, y0 + 25], fill=(235, 235, 235)); d.rectangle([x0 + 22, y0 + 9, x0 + 27, y0 + 25], fill=(235, 235, 235))
        return f
    def _now(self, ripple=None):
        f = self._caption(self._frame(self.page), self.cap)
        if self.fx is not None: f = self._finger(f, self.fx, self.fy, self.fpress, ripple)
        return self._sign(f)
    def _n(self, secs): return max(1, int(round(secs * self.FPS)))
    def _ease(self, t): return t * t * (3 - 2 * t)
    def card(self, big, small):
        f = self.BG.copy(); d = ImageDraw.Draw(f)
        tw = d.textlength(big, font=self.F_TITLE); d.text(((self.W - tw) / 2, self.H * 0.375), big, font=self.F_TITLE, fill=(255, 255, 255))
        sw = d.textlength(small, font=self.F_SUB); d.text(((self.W - sw) / 2, self.H * 0.5), small, font=self.F_SUB, fill=(255, 214, 64))
        f.ldrc_card = True; return f

    # ------------------------------------------------------------ the timeline: the voice over stillness, movement in silence
    def hold(self, secs):
        f = self._now()
        for _ in range(self._n(secs)): self.frames.append(f)
    def show(self, page, look=LOOK):
        """the next page (a shot's key, or a card): faded in, in silence, the finger gone; then looked at"""
        a = self._now(); self.page = self.img[page] if isinstance(page, str) else page; self.cap = None; self.fx = None; self.fpress = 0.0
        b = self._now(); n = self._n(FADE)
        for i in range(n): self.frames.append(Image.blend(a, b, self._ease((i + 1) / n)))
        self.hold(look)
    def say(self, key, cap=None, after=AFTER):
        """the voice, over the still picture (the caption with it); then a moment"""
        self.segments.append((len(self.frames), key)); self.cap = cap if cap is not None else self.cap
        self.hold(self.dur[key] + after)
    def glide(self, x, y, secs=GLIDE):
        x0, y0 = (self.fx, self.fy) if self.fx is not None else (x, 530)   # (from below the page, straight up: never across another button)
        n = self._n(secs)
        for i in range(n):
            e = self._ease((i + 1) / n); self.fx, self.fy = x0 + (x - x0) * e, y0 + (y - y0) * e; self.frames.append(self._now())
        self.fx, self.fy = x, y
    def press(self, secs=PRESS):
        n = self._n(secs)
        for i in range(n): self.fpress = (i + 1) / n; self.frames.append(self._now(ripple=(i + 1) / n))
        self.fpress = 1.0; self.touches.append((len(self.frames) - 1, self.fx, self.fy, self.page))
    def lift(self, secs=0.3):
        n = self._n(secs)
        for i in range(n): self.fpress = 1.0 - (i + 1) / n; self.frames.append(self._now())
        self.fpress = 0.0
    def under(self, page):
        """the page under the finger changes at once (a slider's next step, a box appearing)"""
        self.page = self.img[page]
    def slide(self, steps, y, secs_each=0.5):
        """the finger, pressed, moves through slider positions: steps = [(page key, x), ...]. The knob follows the finger: the
        next position's page from the moment the finger is past half way (17 Oct: it jumped ahead as the finger set off)"""
        for key, x in steps:
            x0 = self.fx; n = self._n(secs_each)
            for i in range(n):
                e = self._ease((i + 1) / n); self.fx = x0 + (x - x0) * e; self.fy = y
                if e >= 0.5: self.page = self.img[key]
                self.frames.append(self._now())
            self.touches.append((len(self.frames) - 1, self.fx, self.fy, self.page))
    def tap(self, x, y, nxt=None):
        """in silence: the finger glides to (x, y), rests, presses, lifts; the next page (if any) fades in"""
        self.glide(x, y); self.hold(REST); self.press(); self.hold(0.3); self.lift()
        if nxt: self.show(nxt)
    def begin(self):
        self.page = self.card(self.title, self.subtitle); self.cap = None
        self.hold(0.8)
    def end(self, key):
        self.show(self.card("That's all.", 'LockDownRadioControl V2'), look=0.4)
        self.say(key, cap=None, after=2.0)

    # ------------------------------------------------------------ the check (17 Oct, after Malcolm's photos of the transmitter)
    def check_touches(self, frame_of, what, page_tol, dot_tol):
        """Every touch, in the pictures themselves: the page around the finger must be the page as drawn at the film's scale and
        place (so the finger's point is the page's point), and the red dot must sit where the finger's sums put it. frame_of(n)
        gives (the picture standing for frame n, the frame it really is), or None: not checked. Stops the build on any fault."""
        import numpy as np
        pw, ph = int(800 * self.SCALE), int(480 * self.SCALE); ring = 40 * max(self.FS, 0.8)
        yy, xx = np.mgrid[0:ph, 0:pw]; worst_page = worst_dot = 0.0; n_checked = 0
        for n, x, y, page in self.touches:
            got_n = frame_of(n)
            if got_n is None: continue
            f, k = got_n; x, y = self.frames.pos[k]                # (where the finger was drawn in that very frame)
            cx, cy = self.SX + x * self.SCALE, self.SY + y * self.SCALE
            exp = np.asarray(page.resize((pw, ph), Image.LANCZOS), dtype=np.int16)
            got = np.asarray(f.convert('RGB').crop((self.SX, self.SY, self.SX + pw, self.SY + ph)), dtype=np.int16)
            away = (xx + self.SX - cx) ** 2 + (yy + self.SY - cy) ** 2 > ring ** 2
            diff = float(np.abs(exp - got).mean(axis=2)[away].mean())
            r = 10; win = np.asarray(f.convert('RGB').crop((int(cx) - r, int(cy) - r, int(cx) + r + 1, int(cy) + r + 1)), dtype=np.int16)
            wy, wx = np.mgrid[0:2 * r + 1, 0:2 * r + 1]; inside = (wx - r) ** 2 + (wy - r) ** 2 <= r * r
            red = inside & (win[:, :, 0] > 170) & (win[:, :, 1] < 110) & (win[:, :, 2] < 110)
            if red.sum() < 25: sys.exit('%s %s: touch at frame %d (%d, %d): no red dot where the finger should be' % (self.name, what, n, x, y))
            ys, xs = np.nonzero(red); dx = xs.mean() + int(cx) - r - cx; dy = ys.mean() + int(cy) - r - cy
            if diff > page_tol: sys.exit('%s %s: touch at frame %d (%d, %d): the page around the finger is not the page at the finger\'s scale (differs by %.1f)' % (self.name, what, n, x, y, diff))
            if abs(dx) > dot_tol or abs(dy) > dot_tol: sys.exit('%s %s: touch at frame %d (%d, %d): the dot is %.1f, %.1f pixels away' % (self.name, what, n, x, y, dx, dy))
            worst_page, worst_dot = max(worst_page, diff), max(worst_dot, abs(dx), abs(dy)); n_checked += 1
        print('%s %s: %d touches checked - each dot on its point (worst %.2f px), the page under it right (worst %.1f)' % (self.name, what, n_checked, worst_dot, worst_page))

    # ------------------------------------------------------------ out
    def finish(self):
        self.check_touches(lambda n: (self.frames[n], n), 'as drawn', 0.5, 1.0)   # (a dot of 9 pixels round a point between pixels: within one)
        FPS = self.FPS; total = len(self.frames) / FPS; rate = 44100
        track = bytearray(int(total * rate) * 2)
        for start, k in self.segments:
            with wave.open(os.path.join(self.out, 'voice', k + '.wav')) as w: pcm = w.readframes(w.getnframes())
            o = int(start / FPS * rate) * 2; n = min(len(pcm), len(track) - o); track[o:o + n] = pcm[:n]
        tw = os.path.join(self.out, 'track.wav')
        with wave.open(tw, 'w') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(bytes(track))
        if self.target == 'screen':
            DEST = os.environ.get('LDRC_FILM_DIR', os.path.join(EMU, 'sd', 'hmi', 'films')); os.makedirs(DEST, exist_ok=True)
            STEP = 3; SFPS = FPS // STEP; keep = self.frames[::STEP]
            # Version 3: each picture only the rectangle that changed since the frame before (8-pixel steps: whole JPEG blocks);
            # the sections - each spoken line, from the frame its voice starts - with a key picture (the whole screen, the top
            # bit of its size) at each, so the screen's Back and Next can start there; and a whole screen anywhere is a key too.
            from PIL import ImageChops
            sections = sorted(set([0] + [s // STEP for s, _ in self.segments if s // STEP >= SFPS]))   # (a line in the first second belongs to the first section)
            secset = set(sections)
            blobs, keys, prev = [], [], None
            crops = []                                                # (index, rectangle, the picture cut out)
            whole = self.W * self.H; since = 0                         # (the area decoded since the last whole picture)
            for i, f in enumerate(keep):
                full = prev is None or i in secset
                box = (0, 0, self.W, self.H) if full else ImageChops.difference(prev, f).getbbox()
                if box is None: crops.append(None)
                else:
                    l, t0, r, b = box; l, t0 = l // 8 * 8, t0 // 8 * 8; r, b = min(self.W, (r + 7) // 8 * 8), min(self.H, (b + 7) // 8 * 8)
                    # (1.11.89, the slider: a jump decodes from the whole picture at or before it) a big change - a page fading
                    # in - goes in whole, and so does any change once those since the last whole picture add up to a screen:
                    # a jump never decodes more than about two screens' worth
                    area = (r - l) * (b - t0)
                    if area * 2 > whole or since + area > whole: l, t0, r, b = 0, 0, self.W, self.H
                    since = 0 if (l, t0, r, b) == (0, 0, self.W, self.H) else since + area
                    crops.append(((l, t0, r, b), f.crop((l, t0, r, b)).convert('RGB')))
                prev = f
            # Every picture tried with the screen's own decoder; one it refuses is saved again a little differently until it
            # decodes (4:4:4 always - its 4:2:0 at an x not on 16 pixels overran on the Mac).
            def enc(im, q, opt): bio = io.BytesIO(); im.save(bio, 'JPEG', quality=q, subsampling=0, optimize=opt, progressive=False); return bio.getvalue()
            tries = [(86, True), (86, False), (85, True), (84, False), (83, True), (82, False), (80, True), (78, False), (75, True)]
            jp = [enc(c[1], 86, True) if c else None for c in crops]; attempt = [0] * len(crops)
            exe = _checker(self.out); redone = 0
            while True:
                idx = [i for i, c in enumerate(crops) if c]
                bad = _refused(exe, self.out, [jp[i] for i in idx])
                if not bad: break
                for b in bad:
                    i = idx[b]; attempt[i] += 1
                    if attempt[i] >= len(tries): sys.exit('picture %d of %s: the screen\'s decoder refuses it however it is saved' % (i, self.name))
                    q, opt = tries[attempt[i]]; jp[i] = enc(crops[i][1], q, opt); redone += 1
            for c, j in zip(crops, jp):
                if not c: blobs.append(b''); keys.append(False)
                else:
                    (l, t0, r, b), _ = c
                    blobs.append(struct.pack('<HHHH', l, t0, r - l, b - t0) + j); keys.append((l, t0, r, b) == (0, 0, self.W, self.H))
            if redone: print('(%d pictures saved again for the screen\'s decoder)' % redone)
            head = b'LDRCFILM' + struct.pack('<HHHHI', 3, self.W, self.H, SFPS, len(keep))
            secbytes = struct.pack('<I', len(sections)) + b''.join(struct.pack('<I', s) for s in sections)
            table, data, off = b'', b'', len(head) + 8 * len(keep) + len(secbytes)
            for bl, k in zip(blobs, keys): table += struct.pack('<II', off if bl else 0, len(bl) | (0x80000000 if k else 0)); data += bl; off += len(bl)
            table += secbytes
            ldf = os.path.join(DEST, self.name + '.ldf'); open(ldf, 'wb').write(head + table + data)
            want = {n // STEP: n for n, _, _, _ in self.touches}; got = {}; fb = Image.new('RGB', (self.W, self.H))
            for j, bl in enumerate(blobs):                        # (the file read back as the screen reads it: each picture where it says)
                if bl:
                    l, t0, w_, h_ = struct.unpack('<HHHH', bl[:8]); fb.paste(Image.open(io.BytesIO(bl[8:])).convert('RGB').crop((0, 0, w_, h_)), (l, t0))
                if j in want: got[want[j]] = (fb.copy(), j * STEP)   # (kept frame j is frame j * STEP)
            self.check_touches(lambda n: got.get(n), 'in ' + os.path.basename(ldf), 4.0, 1.0)
            wav = os.path.join(DEST, self.name + '.wav')
            subprocess.run([FF, '-y', '-loglevel', 'error', '-i', tw, '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '22050', '-ac', '1', '-c:a', 'pcm_s16le', wav], check=True)
            real = sum(1 for bl in blobs if bl)
            print('film %s: %d frames at %d a second (%.1f s), %d pictures (%d keys), %d sections, %d kB; the largest %d kB; sound %d kB' % (ldf, len(keep), SFPS, len(keep) / SFPS, real, sum(keys), len(sections), os.path.getsize(ldf) // 1024, max(len(bl) for bl in blobs) // 1024, os.path.getsize(wav) // 1024))
            return ldf
        out = os.path.join(self.out, 'LDRC-%s-%s.mp4' % (self.name.lower(), self.voice_name.replace('_', '-')))
        p = subprocess.Popen([FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (self.W, self.H), '-r', str(FPS), '-i', '-', '-i', tw,
                              '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '44100', '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
        for f in self.frames: p.stdin.write(f.tobytes())
        p.stdin.close(); p.wait()
        print('mp4 %s: %.1f s, %d kB' % (out, total, os.path.getsize(out) // 1024))
        return out
