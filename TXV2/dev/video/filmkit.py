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

class Film:
    def __init__(self, name, title, subtitle):
        self.name, self.title, self.subtitle = name, title, subtitle
        self.target = os.environ.get('LDRC_TARGET', 'mp4')
        self.out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'video', name)
        for d in ('scripts', 'shots', 'voice'): os.makedirs(os.path.join(self.out, d), exist_ok=True)
        self.scripts, self.lines, self.img, self.dur = {}, [], {}, {}
        self.frames, self.segments = [], []
        self.page = None; self.cap = None; self.fx = self.fy = None; self.fpress = 0.0
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
        if isinstance(page, Image.Image) and page.size == (self.W, self.H): return page.copy()   # (a card)
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
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 150), outline=(255, 214, 64, 255), width=5); return f
    def _now(self, ripple=None):
        f = self._caption(self._frame(self.page), self.cap)
        if self.fx is not None: f = self._finger(f, self.fx, self.fy, self.fpress, ripple)
        return f
    def _n(self, secs): return max(1, int(round(secs * self.FPS)))
    def _ease(self, t): return t * t * (3 - 2 * t)
    def card(self, big, small):
        f = self.BG.copy(); d = ImageDraw.Draw(f)
        tw = d.textlength(big, font=self.F_TITLE); d.text(((self.W - tw) / 2, self.H * 0.375), big, font=self.F_TITLE, fill=(255, 255, 255))
        sw = d.textlength(small, font=self.F_SUB); d.text(((self.W - sw) / 2, self.H * 0.5), small, font=self.F_SUB, fill=(255, 214, 64)); return f

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
        x0, y0 = (self.fx, self.fy) if self.fx is not None else (min(780, x + 150), min(470, y + 120))
        n = self._n(secs)
        for i in range(n):
            e = self._ease((i + 1) / n); self.fx, self.fy = x0 + (x - x0) * e, y0 + (y - y0) * e; self.frames.append(self._now())
        self.fx, self.fy = x, y
    def press(self, secs=PRESS):
        n = self._n(secs)
        for i in range(n): self.fpress = (i + 1) / n; self.frames.append(self._now(ripple=(i + 1) / n))
        self.fpress = 1.0
    def lift(self, secs=0.3):
        n = self._n(secs)
        for i in range(n): self.fpress = 1.0 - (i + 1) / n; self.frames.append(self._now())
        self.fpress = 0.0
    def under(self, page):
        """the page under the finger changes at once (a slider's next step, a box appearing)"""
        self.page = self.img[page]
    def slide(self, steps, y, secs_each=0.5):
        """the finger, pressed, moves through slider positions: steps = [(page key, x), ...]"""
        for key, x in steps:
            x0 = self.fx; n = self._n(secs_each); self.page = self.img[key]
            for i in range(n): self.fx = x0 + (x - x0) * self._ease((i + 1) / n); self.fy = y; self.frames.append(self._now())
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

    # ------------------------------------------------------------ out
    def finish(self):
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
            # (version 2) each picture is only the rectangle that changed since the frame before, on 8-pixel steps (whole JPEG blocks)
            from PIL import ImageChops
            blobs, prev = [], None
            for f in keep:
                box = (0, 0, self.W, self.H) if prev is None else ImageChops.difference(prev, f).getbbox()
                if box is None: blobs.append(b'')
                else:
                    l, t0, r, b = box; l, t0 = l // 8 * 8, t0 // 8 * 8; r, b = min(self.W, (r + 7) // 8 * 8), min(self.H, (b + 7) // 8 * 8)
                    bio = io.BytesIO(); f.crop((l, t0, r, b)).convert('RGB').save(bio, 'JPEG', quality=86, subsampling=0, optimize=True, progressive=False)
                    blobs.append(struct.pack('<HHHH', l, t0, r - l, b - t0) + bio.getvalue())
                prev = f
            head = b'LDRCFILM' + struct.pack('<HHHHI', 2, self.W, self.H, SFPS, len(keep))
            table, data, off = b'', b'', len(head) + 8 * len(keep)
            for bl in blobs: table += struct.pack('<II', off if bl else 0, len(bl)); data += bl; off += len(bl)
            ldf = os.path.join(DEST, self.name + '.ldf'); open(ldf, 'wb').write(head + table + data)
            wav = os.path.join(DEST, self.name + '.wav')
            subprocess.run([FF, '-y', '-loglevel', 'error', '-i', tw, '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '22050', '-ac', '1', '-c:a', 'pcm_s16le', wav], check=True)
            real = sum(1 for bl in blobs if bl)
            print('film %s: %d frames at %d a second (%.1f s), %d pictures, %d kB; the largest %d kB; sound %d kB' % (ldf, len(keep), SFPS, len(keep) / SFPS, real, os.path.getsize(ldf) // 1024, max(len(bl) for bl in blobs) // 1024, os.path.getsize(wav) // 1024))
            return ldf
        out = os.path.join(self.out, 'LDRC-%s-%s.mp4' % (self.name.lower(), self.voice_name.replace('_', '-')))
        p = subprocess.Popen([FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (self.W, self.H), '-r', str(FPS), '-i', '-', '-i', tw,
                              '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '44100', '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
        for f in self.frames: p.stdin.write(f.tobytes())
        p.stdin.close(); p.wait()
        print('mp4 %s: %.1f s, %d kB' % (out, total, os.path.getsize(out) // 1024))
        return out
