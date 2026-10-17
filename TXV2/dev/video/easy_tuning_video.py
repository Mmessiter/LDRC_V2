#!/usr/bin/env python3
"""A sample instructional film: Easy tuning from the LDRC V2 transmitter (17 Oct 2026; Malcolm: "Perhaps you could create an
animation?"). Every screen is drawn by the screen's own code (ESP32-board2 hmi/render_pages.py, from its scenarios, with the
model's name and the motor's state set for the story); a British voice (macOS `say`, Daniel); captions; a finger for each
tap; encoded to MP4 (1280 x 720, 30 fps, H.264 + AAC). The route and the words are the firmware's: front page > Model >
Rotorflight > Easy tuning; a Cyclic change saves the PIDs, reported as "Saved, and read back the same: Feel." (RF_Easy.h).
   PY/bin/python dev/video/easy_tuning_video.py [OUTDIR]      (a Python with Pillow and imageio-ffmpeg; default OUTDIR dev/out/video)
The voice: LDRC_VOICE=say:Daniel (the Mac's own, the default) or kokoro:bf_emma / kokoro:bm_george (Kokoro, an open
neural speech model run on this Mac - nothing sent anywhere: pip install kokoro-onnx, and its two model files in
KOKORO_DIR, default /Volumes/2TB SSD/ClaudeScratch/kokoro-model). Malcolm, of the Mac's voice: "does not sound natural
... sometimes places the emphasis on the wrong part of the word or the wrong part of the sentence".
A new film: copy this, change the scenario prefixes (section 1), the lines (section 2) and the timeline (section 3)."""
import os, re, subprocess, sys, wave, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
SP = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'out', 'video')
EMU = os.path.expanduser('~/Documents/GitHub/ESP32-board2/board4/nextion-emulator')
SCN = os.path.join(EMU, 'hmi', 'scenarios')
FF = imageio_ffmpeg.get_ffmpeg_exe()
os.makedirs(SP, exist_ok=True); os.makedirs(os.path.join(SP, 'scripts'), exist_ok=True); os.makedirs(os.path.join(SP, 'shots'), exist_ok=True); os.makedirs(os.path.join(SP, 'voice'), exist_ok=True)

# ---------------------------------------------------------------- 1. the screens, from the scenarios
def prefix(name, shot):
    out = []
    for l in open(os.path.join(SCN, name)).read().split('\n'):
        if l.startswith('@shot '):
            if l.strip() == '@shot ' + shot: break
            continue
        out.append(l)
    return '\n'.join(out) + '\n'
scripts = {
    'a_front': (prefix('13.txt', '13_conn') + '@shot a_front\n')   # (the motor OFF, as for tuning: disarmed, the head still)
        .replace('bt0.txt="Motor is ON"\nbt0.bco=2016\nbt0.bco2=2016\nbt0.pco=0\nbt0.pco2=0', 'bt0.txt="Motor is OFF"\nbt0.bco=63488\nbt0.bco2=63488\nbt0.pco=65535\nbt0.pco2=65535')
        .replace('RPM: 2150', 'RPM: 0').replace('Amps: 12.4', 'Amps: 0.3').replace('mAh: 345', 'mAh: 0').replace('ESC: 52.3', 'ESC: 21.5'),
    'a_model': prefix('4.txt', '4_open') + '@shot a_model\n',
    'a_rf': prefix('8.txt', '8_open') + '@shot a_rf\n',
}
easy = prefix('81.txt', '81_open').replace('t11.txt="Havok"', 't11.txt="RAW 420 MCM"').replace('t14.txt="Bank 2"', 't14.txt="Bank 1"').replace('t8.txt="Rate 2"', 't8.txt="Rate 1"')
assert 't11.txt="RAW 420 MCM"' in easy and 's3.val=6' in easy
box_on = 'lvb.bco=59323\nlv0.bco=59323\nlv1.bco=59323\nlv2.bco=59323\nlv3.bco=59323\nlv4.bco=59323\nlv0.txt=""\nlv1.txt=""\nlv2.txt=""\nlv3.txt=""\nlv4.txt=""\nvis lvb,1\nvis lv0,1\nvis lv1,1\nvis lv2,1\nvis lv3,1\nvis lv4,1\n'
numbers = 'lv0.txt="Cyclic +10 %\\r\\nRoll\\r\\nPitch"\nlv1.txt="P\\r\\n50 -> 53\\r\\n52 -> 57"\nlv2.txt="I\\r\\n100 -> 110\\r\\n104 -> 114"\nlv3.txt="D\\r\\n40 -> 44\\r\\n44 -> 48"\nlv4.txt="F\\r\\n100 -> 110\\r\\n100 -> 110"\n'
box_off = 'vis lv4,0\nvis lv3,0\nvis lv2,0\nvis lv1,0\nvis lv0,0\nvis lvb,0\n'
seq = easy + '@shot e_open\n' + box_on + '@shot e_touch\n' + 's3.val=7\nvis b3,1\n' + '@shot e_7\n' + 's3.val=8\n' + numbers + '@shot e_8\n' + box_off + '@shot e_lift\n'
seq += 'vis busy,1\nbusy.txt="Writing the PIDs ..."\n@shot e_busy\n'
seq += 'vis b3,0\nbusy.txt="Saved, and read back the same: Feel."\n@shot e_saved\n'
scripts['easy'] = seq
assert 'Motor is OFF' in scripts['a_front'] and 'RPM: 0' in scripts['a_front'], 'the front page motor-off edit'
for k, v in scripts.items(): open(os.path.join(SP, 'scripts', k + '.txt'), 'w').write(v)
py = sys.executable   # (the renderer saves PNGs with Pillow: this same Python)
r = subprocess.run([py, os.path.join(EMU, 'hmi', 'render_pages.py'), os.path.join(SP, 'shots')] + [os.path.join(SP, 'scripts', k + '.txt') for k in scripts], capture_output=True, text=True, cwd=EMU)
print(r.stdout.strip()[-300:], r.stderr.strip()[-300:])
shot = lambda n: Image.open(os.path.join(SP, 'shots', n + '.png')).convert('RGB')

# ---------------------------------------------------------------- 2. the voice
# Malcolm, 17 Oct 2026, of the Kokoro version: "a little bit more slow to give people time to understand what's been going
# on ... the viewer probably understands nothing at the start." So each page is named as it appears, the voice is a little
# slower (LDRC_SPEED, 0.9 by default for Kokoro), and the timeline below gives each new page a moment before a word is said.
lines = [
    ('title', 'Easy tuning. How to tune a Rotorflight helicopter from the transmitter.'),
    ('front1', "This is the transmitter's front page. First, switch on the helicopter, and leave it disarmed."),
    ('front2', 'Then press Model.'),
    ('model', 'This is the Model setup page. Press Rotorflight.'),
    ('rf', 'This is the Rotorflight menu. Press Easy tuning.'),
    ('open', 'Easy tuning changes how the helicopter flies, without any numbers. Each slider changes one thing: softer to the left, sharper to the right.'),
    ('drag', 'To make the cyclic a little sharper, slide Cyclic to the right.'),
    ('numbers', 'While your finger is on the slider, the box at the top shows each P, I, D and F value, before and after.'),
    ('save', 'Lift your finger, then press Save.'),
    ('saved', "The transmitter writes the new values to the helicopter's flight controller, reads them back to check, and tells you they match."),
    ('end', "That's all there is to it."),
]
VOICE = os.environ.get('LDRC_VOICE', 'say:Daniel')
engine, voice_name = VOICE.split(':', 1)
kokoro = None
if engine == 'kokoro':
    from kokoro_onnx import Kokoro
    import numpy as np
    KD = os.environ.get('KOKORO_DIR', '/Volumes/2TB SSD/ClaudeScratch/kokoro-model')
    from kokoro_onnx import EspeakConfig
    import espeakng_loader, shutil
    # eSpeak (the pronunciation library inside) takes a data path of under 160 characters, and a longer one - a venv deep in
    # a temporary folder - is silently ignored for the path its library was built with, where it then exits the program.
    # So its data is kept beside the model, on a short path.
    ED = os.path.join(KD, 'espeak-ng-data')
    if not os.path.isdir(ED): shutil.copytree(espeakng_loader.get_data_path(), ED)
    assert len(ED) < 150, ED
    kokoro = Kokoro(os.path.join(KD, 'kokoro-v1.0.onnx'), os.path.join(KD, 'voices-v1.0.bin'),
                    espeak_config=EspeakConfig(lib_path=espeakng_loader.get_library_path(), data_path=ED))
SPEED = float(os.environ.get('LDRC_SPEED', '0.9' if engine == 'kokoro' else '1.0'))
dur = {}
for k, text in lines:
    raw = os.path.join(SP, 'voice', k + ('.aiff' if engine == 'say' else '.raw.wav')); wav = os.path.join(SP, 'voice', k + '.wav')
    if engine == 'say':
        subprocess.run(['say', '-v', voice_name, '-r', str(int(172 * SPEED)), '-o', raw, text], check=True)
    else:
        samples, sr = kokoro.create(text, voice=voice_name, speed=SPEED, lang='en-gb')
        pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
        with wave.open(raw, 'w') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm)
    subprocess.run([FF, '-y', '-loglevel', 'error', '-i', raw, '-ar', '44100', '-ac', '1', wav], check=True)
    with wave.open(wav) as w: dur[k] = w.getnframes() / w.getframerate()
print({k: round(v, 2) for k, v in dur.items()})

# ---------------------------------------------------------------- 3. the picture
# LDRC_TARGET=screen: the film for the transmitter's own screen (screen 1.11.85: the help page's Film button plays it) -
# 800 x 480, the page at 0.9 with a band under it for the words, written as an LDRC film (.ldf, below) and its sound
# (22.05 kHz WAV) into the screen's card folder, sd/hmi/films/<NAME>.ldf + .wav. Otherwise the MP4 for phones and computers.
TARGET = os.environ.get('LDRC_TARGET', 'mp4')
if TARGET == 'screen':
    W, H, FPS = 800, 480, 30
    SCALE = 0.9; SX, SY = (W - int(800 * SCALE)) // 2, 0
else:
    W, H, FPS = 1280, 720, 30
    SCALE = 1.25; SX, SY = (W - int(800 * SCALE)) // 2, 18
FS = SCALE / 1.25   # (the finger and the words in proportion)
LOOK = 1.2        # a new page, looked at before a word is said
GLIDE = 0.8       # the finger's way to a button
REST = 0.9        # the finger resting on it before the press
PRESS = 0.45
FADE = 0.6
def font(size, bold=False):
    for f in (('/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold else '/System/Library/Fonts/Supplemental/Arial.ttf'), '/System/Library/Fonts/Helvetica.ttc'):
        if os.path.exists(f): return ImageFont.truetype(f, size)
    return ImageFont.load_default()
F_CAP, F_TITLE, F_SUB = font(int(36 * max(FS, 0.72)), True), font(int(64 * max(FS, 0.72)), True), font(int(34 * max(FS, 0.72)))
BG = Image.new('RGB', (W, H), (22, 28, 38))
gd = ImageDraw.Draw(BG)
for y in range(H): gd.line([(0, y), (W, y)], fill=(22 + y // 40, 28 + y // 40, 38 + y // 30))
_framed = {}
def framed(img):
    if id(img) not in _framed:
        f = BG.copy(); s = img.resize((int(800 * SCALE), int(480 * SCALE)), Image.LANCZOS)
        d = ImageDraw.Draw(f)
        if TARGET != 'screen': d.rounded_rectangle([SX - 14, SY - 14, SX + s.width + 14, SY + s.height + 14], radius=18, fill=(8, 8, 10))
        f.paste(s, (SX, SY)); _framed[id(img)] = (img, f)
    return _framed[id(img)][1].copy()
def caption(f, text):
    if not text: return f
    d = ImageDraw.Draw(f, 'RGBA')
    tw = d.textlength(text, font=F_CAP)
    y0 = SY + int(480 * SCALE) + (26 if TARGET != 'screen' else 10)
    ph = int(58 * max(FS, 0.72))
    d.rounded_rectangle([(W - tw) / 2 - 24, y0 - 8, (W + tw) / 2 + 24, y0 - 8 + ph], radius=12, fill=(255, 255, 255, 235))
    d.text(((W - tw) / 2, y0), text, font=F_CAP, fill=(20, 24, 32))
    return f
def at(x, y): return SX + x * SCALE, SY + y * SCALE
def finger(f, x, y, press=0.0, ripple=None):
    d = ImageDraw.Draw(f, 'RGBA'); cx, cy = at(x, y); k = max(FS, 0.8); r = (26 - 6 * press) * k
    if ripple is not None:
        rr = (28 + 60 * ripple) * k; a = int(200 * (1 - ripple))
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(255, 214, 64, a), width=5)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 150), outline=(255, 214, 64, 255), width=5)
    return f
def blend(a, b, t): return Image.blend(a, b, max(0.0, min(1.0, t)))
def ease(t): return t * t * (3 - 2 * t)
frames = []
segments = []   # (start frame, voice key) for the sound track
def say_here(k): segments.append((len(frames), k))
def n_of(secs): return max(1, int(round(secs * FPS)))
def hold(img, secs):
    for _ in range(n_of(secs)): frames.append(img)
def look(img, secs, cap=None): hold(caption(framed(img), cap), secs)
def title_card(big, small):
    f = BG.copy(); d = ImageDraw.Draw(f)
    tw = d.textlength(big, font=F_TITLE); d.text(((W - tw) / 2, H * 0.375), big, font=F_TITLE, fill=(255, 255, 255))
    sw = d.textlength(small, font=F_SUB); d.text(((W - sw) / 2, H * 0.5), small, font=F_SUB, fill=(255, 214, 64))
    return f
def fade(a, b, secs=FADE):   # a, b: whole frames
    n = n_of(secs)
    for i in range(n): frames.append(blend(a, b, ease((i + 1) / n)))
def start_of(x, y): return min(780, x + 150), min(470, y + 120)   # where the finger comes from: below and to the right
def glide(img, cap, x0, y0, x1, y1, secs=GLIDE):
    n = n_of(secs)
    for i in range(n):
        e = ease((i + 1) / n); frames.append(caption(finger(framed(img), x0 + (x1 - x0) * e, y0 + (y1 - y0) * e), cap))
def rest(img, cap, x, y, secs, pressed=0.0):
    for _ in range(n_of(secs)): frames.append(caption(finger(framed(img), x, y, press=pressed), cap))
def press(img, cap, x, y, secs=PRESS):
    n = n_of(secs)
    for i in range(n): frames.append(caption(finger(framed(img), x, y, press=(i + 1) / n, ripple=(i + 1) / n), cap))
def tap_step(img, nxt, x, y, key, cap, extra=0.0):
    """the page named and the button shown: the voice starts, the finger glides in and rests while it speaks, then presses;
    a moment, then the next page fades in (with no caption: it is looked at first)"""
    say_here(key)
    glide(img, cap, *start_of(x, y), x, y)
    rest(img, cap, x, y, max(REST, dur[key] - GLIDE + 0.3) + extra)
    press(img, cap, x, y)
    rest(img, cap, x, y, 0.35, pressed=1.0)
    fade(caption(finger(framed(img), x, y, press=1.0), cap), framed(nxt))

e_open, e_touch, e_7, e_8, e_lift, e_busy, e_saved = (shot(n) for n in ('e_open', 'e_touch', 'e_7', 'e_8', 'e_lift', 'e_busy', 'e_saved'))
f_front, f_model, f_rf = shot('a_front'), shot('a_model'), shot('a_rf')
# the title
title = title_card('Easy tuning', 'Rotorflight, from the LDRC transmitter')
hold(title, 0.8)
say_here('title'); hold(title, dur['title'] + 1.6)
fade(title, framed(f_front), 0.8)
# the front page: looked at, named, the helicopter on; then Model
look(f_front, LOOK)
say_here('front1'); look(f_front, dur['front1'] + 0.9, 'Helicopter on, and disarmed.')
tap_step(f_front, f_model, 652, 425, 'front2', 'Press Model.')
# Model setup, then the Rotorflight menu
look(f_model, LOOK)
tap_step(f_model, f_rf, 400, 354, 'model', 'Press Rotorflight.')
look(f_rf, LOOK)
tap_step(f_rf, e_open, 160, 113, 'rf', 'Press Easy tuning.')
# Easy tuning: what it is
look(e_open, LOOK)
say_here('open'); look(e_open, dur['open'] + 1.2, 'Softer to the left, sharper to the right.')
# the slider
cap = 'Slide Cyclic to the right.'
say_here('drag')
glide(e_open, cap, *start_of(461, 300), 461, 300)
rest(e_open, cap, 461, 300, max(0.6, dur['drag'] - GLIDE - 1.2))
for i in range(n_of(0.35)): frames.append(caption(finger(framed(e_open), 461, 300, press=(i + 1) / n_of(0.35)), cap))
rest(e_touch, cap, 461, 300, 0.5, pressed=1.0)
n = n_of(0.6)
for i in range(n): frames.append(caption(finger(framed(e_touch), 461 + 26 * ease((i + 1) / n), 300, press=1.0), cap))
for i in range(n): frames.append(caption(finger(framed(e_7), 487 + 27 * ease((i + 1) / n), 300, press=1.0), cap))
rest(e_8, cap, 514, 300, 0.8, pressed=1.0)
# the box
say_here('numbers'); rest(e_8, 'The box shows each value, before and after.', 514, 300, dur['numbers'] + 1.8, pressed=1.0)
# lift, then Save
cap = 'Lift your finger, then press Save.'
say_here('save')
n = n_of(0.4)
for i in range(n): frames.append(caption(finger(framed(e_8), 514, 300, press=1.0 - (i + 1) / n), cap))
look(e_lift, 0.6, cap)
glide(e_lift, cap, 514, 300, 504, 423)
rest(e_lift, cap, 504, 423, max(REST, dur['save'] - 1.8))
press(e_lift, cap, 504, 423)
rest(e_lift, cap, 504, 423, 0.35, pressed=1.0)
fade(caption(finger(framed(e_lift), 504, 423, press=1.0), cap), caption(framed(e_busy), 'Writing ...'))
look(e_busy, 1.6, 'Writing ...')
# saved
say_here('saved'); fade(caption(framed(e_busy), 'Writing ...'), caption(framed(e_saved), 'Saved, and read back to check.'))
look(e_saved, dur['saved'] + 1.6 - FADE, 'Saved, and read back to check.')
# the end
end = title_card("That's all.", 'LockDownRadioControl V2')
say_here('end'); fade(caption(framed(e_saved), 'Saved, and read back to check.'), end, 0.8)
hold(end, dur['end'] + 2.0)

# ---------------------------------------------------------------- 4. the sound track and the film
total = len(frames) / FPS
rate = 44100; track = bytearray(int(total * rate) * 2)
for start, k in segments:
    with wave.open(os.path.join(SP, 'voice', k + '.wav')) as w: pcm = w.readframes(w.getnframes())
    o = int(start / FPS * rate) * 2; n = min(len(pcm), len(track) - o); track[o:o + n] = pcm[:n]
with wave.open(os.path.join(SP, 'track.wav'), 'w') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(bytes(track))
if TARGET == 'screen':
    # An LDRC film (.ldf), for the screen's player (src/film_device.h): "LDRCFILM", version 1, width, height, frames a second
    # (u16 each), the number of frames (u32); then each frame's offset and size (u32 each; size 0 = the same picture as the
    # frame before - nothing to decode); then the pictures, baseline JPEG 4:4:4 (crisp coloured words; JPEGDEC on the S3).
    import io, struct
    NAME = os.environ.get('LDRC_FILM_NAME', 'EASY')
    DEST = os.environ.get('LDRC_FILM_DIR', os.path.join(EMU, 'sd', 'hmi', 'films'))   # (under /hmi: every screen's updater takes it)
    os.makedirs(DEST, exist_ok=True)
    STEP = 3; SFPS = FPS // STEP                              # 10 frames a second on the screen
    keep = frames[::STEP]
    blobs, prev = [], None
    for f in keep:
        raw = f.tobytes()
        if prev is not None and raw == prev: blobs.append(b'')
        else:
            bio = io.BytesIO(); f.convert('RGB').save(bio, 'JPEG', quality=86, subsampling=0, optimize=True, progressive=False); blobs.append(bio.getvalue())
        prev = raw
    head = b'LDRCFILM' + struct.pack('<HHHHI', 1, W, H, SFPS, len(keep))
    table, data, off = b'', b'', len(head) + 8 * len(keep)
    for bl in blobs:
        table += struct.pack('<II', off if bl else 0, len(bl)); data += bl; off += len(bl)
    ldf = os.path.join(DEST, NAME + '.ldf')
    open(ldf, 'wb').write(head + table + data)
    wav = os.path.join(DEST, NAME + '.wav')
    subprocess.run([FF, '-y', '-loglevel', 'error', '-i', os.path.join(SP, 'track.wav'), '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '22050', '-ac', '1', '-c:a', 'pcm_s16le', wav], check=True)
    real = sum(1 for bl in blobs if bl)
    print('film', ldf, '%d frames at %d fps (%.1f s), %d pictures (the rest the same as the one before), %d kB; the largest picture %d kB; sound %d kB'
          % (len(keep), SFPS, len(keep) / SFPS, real, os.path.getsize(ldf) // 1024, max(len(bl) for bl in blobs) // 1024, os.path.getsize(wav) // 1024))
    sys.exit(0)
out = os.path.join(SP, 'LDRC-easy-tuning-%s.mp4' % voice_name.replace('_', '-').lower())
p = subprocess.Popen([FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-', '-i', os.path.join(SP, 'track.wav'),
                      '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '44100', '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
for f in frames: p.stdin.write(f.tobytes())
p.stdin.close(); p.wait()
print('frames', len(frames), 'seconds %.1f' % total, 'file', out, os.path.getsize(out) // 1024, 'kB', 'exit', p.returncode)
frames[int(len(frames) * 0.55)].save(os.path.join(SP, 'still_mid.png')); frames[segments[2][0] + 40].save(os.path.join(SP, 'still_front.png'))
