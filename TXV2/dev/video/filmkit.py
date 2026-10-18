#!/usr/bin/env python3
"""The LDRC film kit (17 Oct 2026): what every instructional film shares, so that a film is a short script (films/*.py).
Every screen is drawn by the transmitter screen's own code (ESP32-board2 hmi/render_pages.py, from its scenarios), the voice
is Kokoro (an open speech model run on this Mac: nothing sent anywhere) or the Mac's own, the finger and the captions are
drawn here, and the result is an MP4 (phones, computers) or, with LDRC_TARGET=screen, an LDRC film for the transmitter's
own screen (sd/hmi/films/<NAME>.ldf + .ima, played from the help pages' Films menu, screen 1.11.87; the .ima and the
fades the screen makes itself from screen 1.11.93 - the animations' update had taken Malcolm's transmitter 1 h 50 min).

Malcolm's rules for the pace (17 Oct): "a little bit more slow ... the viewer probably understands nothing at the start";
"the redrawing of the screen is not terribly fast ... make sure that the pace of the video and of the talking is no
quicker than that"; and "do the video animations and the audio non-simultaneously". So: each new page is shown in
silence first; the voice speaks only over a still picture; the finger moves, presses and the page changes only in silence.

   PY/bin/python dev/video/films/<film>.py [OUTDIR]
   LDRC_TARGET=screen  the film for the transmitter (else an MP4 in OUTDIR, default dev/out/video/<NAME>)
   LDRC_VOICE=cbox:emma (the default: Emma made livelier, 18 Oct) | qwen:emma | kokoro:bf_emma | kokoro:bm_george | say:Daniel
              cbox and qwen speak in the voice of voices/<who>.wav (voice_clone.py)     LDRC_SPEED (0.9 for Kokoro)
   LDRC_EMOTION (cbox: 0.25 to 1, how lively; 0.75, Malcolm's choice)
   TTS_PY (default /Volumes/2TB SSD/ClaudeScratch/tts/venv/bin/python: a Python with mlx-audio, for cbox and qwen)
   KOKORO_DIR (default /Volumes/2TB SSD/ClaudeScratch/kokoro-model: kokoro-v1.0.onnx, voices-v1.0.bin)
   LDRC_COLLECT=<file.json>: only add this film's lines to that list, and stop (speak_all.py then speaks them all at once)
A Python with Pillow, imageio-ffmpeg and kokoro-onnx."""
import io, os, struct, subprocess, sys, wave
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

EMU = os.path.expanduser('~/Documents/GitHub/ESP32-board2/board4/nextion-emulator')
SCN = os.path.join(EMU, 'hmi', 'scenarios')
FF = imageio_ffmpeg.get_ffmpeg_exe()
HERE = os.path.dirname(os.path.abspath(__file__))
VOICE = 'cbox:emma'                                          # (the voice unless LDRC_VOICE says another: 18 Oct, Malcolm chose "Emma, number three")
EMOTION = '0.75'                                              # (how lively, for cbox: his number three was 0.75; number two 0.5)
VOICE_CACHE = '/Volumes/2TB SSD/ClaudeScratch/tts/cache'     # (lines already spoken, by voice and words: a film rebuilt speaks only what changed)
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
static std::vector<unsigned short> out; static int OW, OH;
static int draw(JPEGDRAW *p) { for (int r = 0; r < p->iHeight; ++r) for (int c = 0; c < p->iWidth; ++c) { const int x = p->x + c, y = p->y + r; if (x < OW && y < OH) out[y * OW + x] = p->pPixels[r * p->iWidth + c]; } return 1; }
static JPEGDEC j;
int main(int argc, char **argv) {   // argv[1]: pictures (u32 w, u32 h, u32 length, the JPEG); argv[2]: each one as JPEGDEC draws it (w*h RGB565)
    FILE *f = fopen(argv[1], "rb"), *o = fopen(argv[2], "wb"); if (!f || !o) return 2;
    unsigned h[3]; int i = 0;
    while (fread(h, 4, 3, f) == 3) {
        std::vector<unsigned char> b(h[2]); if (fread(b.data(), 1, h[2], f) != h[2]) return 3;
        OW = (int) h[0]; OH = (int) h[1]; out.assign((size_t) OW * OH, 0xF81F);
        const int ok = j.openRAM(b.data(), (int) h[2], draw) && (j.setPixelType(RGB565_LITTLE_ENDIAN), j.decode(0, 0, 0));
        j.close(); if (!ok) printf("%d\n", i);
        fwrite(out.data(), 2, out.size(), o); ++i;
    }
    fclose(o); return 0;
}
'''
def _checker(outdir):
    """the screen's own JPEG decoder, built on the Mac (1.11.88). JPEGDEC 1.8.4 refuses some pictures ('decode error') that
    other decoders read, and (17 Oct, found by the System film's 82 % wrong picture) decodes a few others WRONGLY without
    a word - both depending on the exact bytes - so every picture is decoded by it and compared with Pillow's decode"""
    exe = os.path.join(outdir, 'jpegdec_check2')
    if not os.path.exists(exe):
        if not os.path.isdir(JPEGDEC_SRC): sys.exit('JPEGDEC not found in %s (build the screen once: pio run -e ota)' % JPEGDEC_SRC)
        src = os.path.join(outdir, 'jpegdec_check2.cpp'); open(src, 'w').write(_CHECKER)
        subprocess.run(['clang++', '-std=c++17', '-O1', '-w', '-I', JPEGDEC_SRC, '-o', exe, src, os.path.join(JPEGDEC_SRC, 'JPEGDEC.cpp')], check=True)
    return exe
def _refused(exe, outdir, jpegs, sizes):
    """the pictures the screen's decoder refuses, or draws unlike Pillow (more than one point in a thousand over 24 apart)"""
    path, got = os.path.join(outdir, 'check.bin'), os.path.join(outdir, 'check.565')
    with open(path, 'wb') as f:
        for j, (w, h) in zip(jpegs, sizes): f.write(struct.pack('<III', w, h, len(j)) + j)
    r = subprocess.run([exe, path, got], capture_output=True, text=True, check=True)
    bad = set(int(x) for x in r.stdout.split())
    raw = open(got, 'rb').read(); at = 0
    for i, (j, (w, h)) in enumerate(zip(jpegs, sizes)):
        px = struct.unpack_from('<%dH' % (w * h), raw, at); at += 2 * w * h
        if i in bad: continue
        ref = Image.open(io.BytesIO(j)).convert('RGB').tobytes(); far = tot = 0
        for k in range(0, w * h, 7):
            v = px[k]
            d = max(abs((((v >> 11) & 31) << 3) - (ref[3 * k] & 0xF8)), abs((((v >> 5) & 63) << 2) - (ref[3 * k + 1] & 0xFC)), abs(((v & 31) << 3) - (ref[3 * k + 2] & 0xF8)))
            tot += 1; far += d > 24
        if far * 1000 > tot: bad.add(i)
    for pth in (path, got):
        try: os.remove(pth)
        except OSError: pass
    return bad

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
        self.fades = []                                       # (the frame each page starts fading in at, the frames it takes): the screen makes the steps itself
        self.page = None; self.cap = None; self.fx = self.fy = None; self.fpress = 0.0
        self.touches = []                                     # (the frame, x, y, the page) at every press and slider stop: finish() checks each
        self._layout()

    # ------------------------------------------------------------ the screens and the voice
    def shot(self, key, text): self.scripts[key] = text if text.rstrip().endswith('@shot ' + key) else text.rstrip('\n') + '\n@shot %s\n' % key
    def line(self, key, text): self.lines.append((key, text))
    def prepare(self):
        if os.environ.get('LDRC_COLLECT'):                    # (18 Oct) only this film's words, added to a list: one run of voice_clone.py then speaks
            p = os.environ['LDRC_COLLECT']                     # every film's lines with its models loaded once, and the films' own builds find them all
            have = json.load(open(p)) if os.path.exists(p) else []   # in the cache
            have += [{'film': self.name, 'key': k, 'text': t} for k, t in self.lines]
            json.dump(have, open(p, 'w'), indent=0); print('%s: %d lines collected' % (self.name, len(self.lines))); sys.exit(0)
        for k, v in self.scripts.items(): open(os.path.join(self.out, 'scripts', k + '.txt'), 'w').write(v)
        r = subprocess.run([sys.executable, os.path.join(EMU, 'hmi', 'render_pages.py'), os.path.join(self.out, 'shots')] + [os.path.join(self.out, 'scripts', k + '.txt') for k in self.scripts], capture_output=True, text=True, cwd=EMU)
        for k in self.scripts:
            p = os.path.join(self.out, 'shots', k + '.png')
            if not os.path.exists(p): sys.exit('shot %s was not drawn: %s %s' % (k, r.stdout[-400:], r.stderr[-400:]))
            self.img[k] = Image.open(p).convert('RGB')
        voice = os.environ.get('LDRC_VOICE', VOICE); engine, vname = voice.split(':', 1)
        self.voice_name = vname
        speed = float(os.environ.get('LDRC_SPEED', '0.9' if engine == 'kokoro' else '1.0'))
        kokoro = None
        if engine in ('cbox', 'qwen'):                        # (18 Oct) every line at once, by the voice's own Python; checked by ear (Whisper) there
            job = os.path.join(self.out, 'voice', 'job.json')
            json.dump({'engine': engine, 'voice': os.path.join(HERE, 'voices', vname + '.wav'), 'cache': VOICE_CACHE,
                       'emotion': float(os.environ.get('LDRC_EMOTION', EMOTION)),
                       'lines': [{'text': text, 'out': os.path.join(self.out, 'voice', k + '.raw.wav')} for k, text in self.lines]}, open(job, 'w'))
            env = dict(os.environ); env.setdefault('HF_HOME', '/Volumes/2TB SSD/ClaudeScratch/hf')
            r = subprocess.run([os.environ.get('TTS_PY', '/Volumes/2TB SSD/ClaudeScratch/tts/venv/bin/python'), os.path.join(HERE, 'voice_clone.py'), job], env=env, capture_output=True, text=True)
            for l in r.stdout.splitlines():
                if l.startswith('VOICE FAULT') or l.startswith('   heard'): print(l)
            if r.returncode: sys.exit('%s: the voice failed (%s)' % (self.name, (r.stdout + r.stderr)[-600:]))
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
            elif engine in ('cbox', 'qwen'): pass             # (spoken above)
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
    def card(self, big, small, art=True):
        """a card of the film's own: a big line and a small one (18 Oct: with a little helicopter drawn above them, illus.py)"""
        if art:
            from illus import Art
            f = Art(self).title_heli(); f.ldrc_card = False
        else: f = self.BG.copy()
        d = ImageDraw.Draw(f)
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
        self.fades.append((len(self.frames), n))
        for i in range(n): self.frames.append(Image.blend(a, b, self._ease((i + 1) / n)))
        self.hold(look)
    def anim(self, draw, secs, t0=0.0):
        """(18 Oct) a drawing that moves (illus.py), in silence: draw(t) is the picture t seconds in; the last one stays as
        the page, for the voice that follows - Malcolm's rule for the films: movement in silence, the voice over a still"""
        self.cap = None; self.fx = None; self.fpress = 0.0
        for i in range(self._n(secs)):
            self.page = draw(t0 + (i + 1) / float(self.FPS)); self.frames.append(self._now())
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
    def point(self, x, y, key, cap=None, after=AFTER):
        """(a tour, 17 Oct) in silence the finger glides to a part of the page and rests on it, not pressing; then the voice
        says what it is"""
        self.cap = None                                       # (the last part's words go as the finger moves on: the next come with the voice)
        self.glide(x, y); self.hold(REST); self.touches.append((len(self.frames) - 1, self.fx, self.fy, self.page))   # (checked as a press is)
        self.say(key, cap, after)
    def tap(self, x, y, nxt=None):
        """in silence: the finger glides to (x, y), rests, presses, lifts; the next page (if any) fades in"""
        self.glide(x, y); self.hold(REST); self.press(); self.hold(0.3); self.lift()
        if nxt: self.show(nxt)
    def begin(self):
        self.page = self.card(self.title, self.subtitle); self.cap = None
        self.hold(0.8)
    def end(self, key=None):
        """the film's own card again, in silence (18 Oct, Malcolm: "Let's remove 'That's all there is to it' from the end" -
        the films used to end on a card saying "That's all." and a line such as that one)"""
        assert key is None, 'end() says nothing now: put a last line of use before it'
        self.cap = None; self.show(self.card(self.title, 'LockDownRadioControl V2'), look=2.0)

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
            # Version 4 (screen 1.11.93): each picture only the rectangle that changed since the frame before (8-pixel steps:
            # whole JPEG blocks); a whole screen is a key (the top bit of its size: the slider starts there); the sections - each
            # spoken line, from the frame its voice starts - mark the slider's track. A page fading in is sent ONCE, whole, bits
            # 24-30 of its size the frames the screen takes to blend into it: the eight whole pictures of each fade had been
            # three quarters of the bytes. (Version 3 also sent a whole screen at each section, for Back and Next, gone in 1.11.90.)
            from PIL import ImageChops
            sections = sorted(set([0] + [s // STEP for s, _ in self.segments if s // STEP >= SFPS]))   # (a line in the first second belongs to the first section)
            fadeAt, inFade = {}, set()                                # (in kept frames: a fade's first, and the rest of it)
            for s, n in self.fades:
                j0 = (s + STEP - 1) // STEP; L = min(max(1, int(round(n / STEP))), len(keep) - j0)
                if L < 1: continue
                assert j0 not in fadeAt and j0 not in inFade and not inFade.intersection(range(j0, j0 + L)), 'two fades at once'
                fadeAt[j0] = (L, self.frames[s + n - 1]); inFade.update(range(j0 + 1, j0 + L))
            blobs, keys, fadeN, prev = [], [], [], None
            crops = []                                                # (index, rectangle, the picture cut out)
            whole = self.W * self.H; since = 0                         # (the area decoded since the last whole picture)
            for i, f in enumerate(keep):
                if i in fadeAt:                                       # the page that fades in, whole; the steps are the screen's
                    L, page = fadeAt[i]; crops.append(((0, 0, self.W, self.H), page.convert('RGB'))); fadeN.append(L); prev = page; since = 0; continue
                fadeN.append(0)
                if i in inFade: crops.append(None); continue
                full = prev is None
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
                bad = _refused(exe, self.out, [jp[i] for i in idx], [crops[i][1].size for i in idx])
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
            print('every picture checked with the screen\'s own decoder against Pillow: %d saved again' % redone)
            head = b'LDRCFILM' + struct.pack('<HHHHI', 4, self.W, self.H, SFPS, len(keep))
            secbytes = struct.pack('<I', len(sections)) + b''.join(struct.pack('<I', s) for s in sections)
            table, data, off = b'', b'', len(head) + 8 * len(keep) + len(secbytes)
            for bl, k, fn in zip(blobs, keys, fadeN):
                assert len(bl) < 1 << 24 and fn < 128
                table += struct.pack('<II', off if bl else 0, len(bl) | (0x80000000 if k else 0) | (fn << 24)); data += bl; off += len(bl)
            table += secbytes
            ldf = os.path.join(DEST, self.name + '.ldf'); open(ldf, 'wb').write(head + table + data)
            want = {n // STEP: n for n, _, _, _ in self.touches}; got = {}; fb = Image.new('RGB', (self.W, self.H))
            for j, bl in enumerate(blobs):                        # (the file read back as the screen reads it: each picture where it says)
                if bl:
                    l, t0, w_, h_ = struct.unpack('<HHHH', bl[:8]); fb.paste(Image.open(io.BytesIO(bl[8:])).convert('RGB').crop((0, 0, w_, h_)), (l, t0))
                if j in want: got[want[j]] = (fb.copy(), j * STEP)   # (kept frame j is frame j * STEP)
            self.check_touches(lambda n: got.get(n), 'in ' + os.path.basename(ldf), 4.0, 1.0)
            import json as _json                                  # (for a review: each touch's kept frame, to look at - pointsheet.py)
            open(os.path.join(self.out, 'touches.json'), 'w').write(_json.dumps([{'frame': n // STEP, 'x': round(x), 'y': round(y)} for n, x, y, _ in self.touches]))
            # The sound: IMA ADPCM (screen 1.11.93, src/ima_adpcm.h), a quarter of the bytes of 16-bit samples; trellis-searched
            # (some 2.5 dB better than ffmpeg's plain search). The screen's decoding is ffmpeg's to the bit (hmi/test_film/ima_test.py).
            wav = os.path.join(DEST, self.name + '.ima')
            subprocess.run([FF, '-y', '-loglevel', 'error', '-i', tw, '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '22050', '-ac', '1', '-c:a', 'adpcm_ima_wav', '-trellis', '8',
                            '-fflags', '+bitexact', '-map_metadata', '-1', '-f', 'wav', wav], check=True)
            old = os.path.join(DEST, self.name + '.wav')
            if os.path.exists(old): os.remove(old)                # (the 16-bit sound of before: a screen plays the .ima when there is one)
            real = sum(1 for bl in blobs if bl)
            print('film %s: %d frames at %d a second (%.1f s), %d pictures (%d keys, %d fades), %d sections, %d kB; the largest %d kB; sound %d kB' % (ldf, len(keep), SFPS, len(keep) / SFPS, real, sum(keys), sum(1 for x in fadeN if x), len(sections), os.path.getsize(ldf) // 1024, max(len(bl) for bl in blobs) // 1024, os.path.getsize(wav) // 1024))
            return ldf
        out = os.path.join(self.out, 'LDRC-%s-%s.mp4' % (self.name.lower(), self.voice_name.replace('_', '-')))
        p = subprocess.Popen([FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (self.W, self.H), '-r', str(FPS), '-i', '-', '-i', tw,
                              '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '44100', '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
        for f in self.frames: p.stdin.write(f.tobytes())
        p.stdin.close(); p.wait()
        print('mp4 %s: %.1f s, %d kB' % (out, total, os.path.getsize(out) // 1024))
        return out
