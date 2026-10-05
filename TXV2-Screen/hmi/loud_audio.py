#!/usr/bin/env python3
"""The transmitter's sound clips, made louder WITHOUT distortion: hmi/audio/<file> -> sd/hmi/audio/<id>.wav

Why: the screen's amplifier (NS4168) runs from 3.3 V on the CrowPanel (R10 fitted, R45 not: at 5 V its inputs would
need 3.5 V, more than the ESP32 gives), so it has less power than the Nextion's. The clips are speech with tall, thin
peaks (peak 18 dB above the average), and the screen used to multiply them by up to 3 and squash whatever came out too
big, sample by sample (screen 1.0-1.4.6): that squashing IS the distortion Malcolm heard as he turned the volume up
(19 % of the sound bent at volume 20, 45 % at 100). Here, once, on the Mac, the clips get what broadcast speech gets:
  1. a high-pass at 100 Hz: what no small speaker plays (250 Hz on 10-03 morning took the body out of the voice);
  2. a gentle compressor (the loud syllables come down slowly, over milliseconds, not sample by sample);
  3. a look-ahead limiter: the gain is already down when a peak arrives, so nothing is ever clipped;
  4. the tone put back: evening out the loudness lifts the quiet consonants, which are treble, so a treble cut
     (-8 dB shelf at 2.5 kHz) and a low-pass at 6 kHz follow (Malcolm, 10-03: "extremely toppy", then "less top");
then the clips peak just below full scale with their average about 8 dB higher, and the screen plays them at a gain
of at most 1 (volume 100), so no sample is ever bent.  Pure Python, no packages: `python3 hmi/loud_audio.py [--stats]`
"""
import array, collections, json, math, os, sys, wave

RATE = 22050
HPF_HZ = 120.0                                       # only what no small speaker plays: the voice keeps its body
ROTATOR_HZ, ROTATOR_STAGES = 200.0, 4                # all-pass sections: the ear cannot hear phase, the peaks can
COMP_THRESH_DB, COMP_RATIO, COMP_KNEE_DB = -26.0, 3.0, 6.0
COMP_ATTACK_MS, COMP_RELEASE_MS, COMP_SMOOTH_MS = 10.0, 120.0, 5.0   # slow enough not to bend a low note
DRIVE_DB = 14.0                                      # into the limiter, after the compressor's own make-up
TONE_CREST_DB = 10.0                                 # a click or a beep (peak within 10 dB of its average) is left as it was
CEILING = 10 ** (-1.0 / 20)                          # -1 dBFS: the loudest sample
LOOKAHEAD_MS, LIMIT_RELEASE_MS = 5.0, 80.0           # the gain eases down over 5 ms, as a triangle
TREBLE_HZ, TREBLE_DB = 2500.0, -8.0                  # after the limiter: evening out the loudness lifts the quiet "s" and "t"
LOWPASS_HZ = 6000.0                                  #   sounds, which are treble (Malcolm 10-03: "extremely toppy", then "less top")

def highpass(x, fs, fc):
    w0 = 2 * math.pi * fc / fs; c = math.cos(w0); alpha = math.sin(w0) / (2 * (1 / math.sqrt(2)))
    a0 = 1 + alpha; b0 = (1 + c) / 2 / a0; b1 = -(1 + c) / a0; b2 = b0; a1 = -2 * c / a0; a2 = (1 - alpha) / a0
    y = [0.0] * len(x); x1 = x2 = y1 = y2 = 0.0
    for i, v in enumerate(x):
        o = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, v, y1, o; y[i] = o
    return y

def allpass(x, fs, f0, q=0.7071):
    w0 = 2 * math.pi * f0 / fs; c = math.cos(w0); alpha = math.sin(w0) / (2 * q); a0 = 1 + alpha
    b0 = (1 - alpha) / a0; b1 = -2 * c / a0; b2 = 1.0; a1 = b1; a2 = b0
    y = [0.0] * len(x); x1 = x2 = y1 = y2 = 0.0
    for i, v in enumerate(x):
        o = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, v, y1, o; y[i] = o
    return y

def highshelf(x, fs, f0, gain_db, slope=1.0):
    A = 10 ** (gain_db / 40); w0 = 2 * math.pi * f0 / fs; c = math.cos(w0); sn = math.sin(w0)
    alpha = sn / 2 * math.sqrt((A + 1 / A) * (1 / slope - 1) + 2); sa = 2 * math.sqrt(A) * alpha
    b0 = A * ((A + 1) + (A - 1) * c + sa); b1 = -2 * A * ((A - 1) + (A + 1) * c); b2 = A * ((A + 1) + (A - 1) * c - sa)
    a0 = (A + 1) - (A - 1) * c + sa; a1 = 2 * ((A - 1) - (A + 1) * c); a2 = (A + 1) - (A - 1) * c - sa
    return biquad(x, b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)

def lowpass(x, fs, fc, q=0.7071):
    w0 = 2 * math.pi * fc / fs; c = math.cos(w0); alpha = math.sin(w0) / (2 * q); a0 = 1 + alpha
    return biquad(x, (1 - c) / 2 / a0, (1 - c) / a0, (1 - c) / 2 / a0, -2 * c / a0, (1 - alpha) / a0)

def biquad(x, b0, b1, b2, a1, a2):
    y = [0.0] * len(x); x1 = x2 = y1 = y2 = 0.0
    for i, v in enumerate(x):
        o = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, v, y1, o; y[i] = o
    return y

def compress(x, fs):
    ka = 1 - math.exp(-1 / (COMP_ATTACK_MS * fs / 1000)); kr = 1 - math.exp(-1 / (COMP_RELEASE_MS * fs / 1000))
    ks = 1 - math.exp(-1 / (COMP_SMOOTH_MS * fs / 1000)); gs = 0.0
    env = 0.0; out = [0.0] * len(x); reduc = []
    for i, v in enumerate(x):
        p = v * v; env += (ka if p > env else kr) * (p - env)
        lvl = 10 * math.log10(env + 1e-12); over = lvl - COMP_THRESH_DB
        if over <= -COMP_KNEE_DB / 2: gdb = 0.0
        elif over >= COMP_KNEE_DB / 2: gdb = -over * (1 - 1 / COMP_RATIO)
        else: gdb = -(1 - 1 / COMP_RATIO) * (over + COMP_KNEE_DB / 2) ** 2 / (2 * COMP_KNEE_DB)
        gs += ks * (gdb - gs)                                    # (the detector ripples at twice a low note: smoothed away)
        out[i] = v * 10 ** ((gs - COMP_THRESH_DB * (1 - 1 / COMP_RATIO) * 0.5) / 20); reduc.append(gs)   # make-up: half the reduction at the threshold's level
    return out, reduc

def limit(x, fs):
    """Look-ahead limiter. The gain needed by a peak is held over the K samples before it, then smoothed by two box
    filters of L samples (a triangle K = 2L-1 long), so it is reached exactly at the peak, never later, and eases in."""
    n = len(x); L = max(1, int(LOOKAHEAD_MS * fs / 1000) // 2); K = 2 * L - 1
    kr = 1 - math.exp(-1 / (LIMIT_RELEASE_MS * fs / 1000))
    need = [min(1.0, CEILING / abs(v)) if v else 1.0 for v in x]
    hold = [1.0] * n; dq = collections.deque()               # the smallest gain needed in the next K samples
    for j in range(n + K - 1, -1, -1):
        if j < n:
            while dq and need[dq[-1]] >= need[j]: dq.pop()
            dq.append(j)
        while dq and dq[0] > j + K - 1: dq.popleft()
        if j < n and dq: hold[j] = need[dq[0]]
    t = [1.0] * n; prev = 1.0                                 # down at once, back up slowly
    for i in range(n): prev = min(hold[i], prev + (1 - prev) * kr); t[i] = prev
    def box(a):
        out = [1.0] * len(a); s = 0.0; win = collections.deque()
        for i, v in enumerate(a):
            win.append(v); s += v
            if len(win) > L: s -= win.popleft()
            out[i] = s / len(win)
        return out
    g = box(box(t))
    return [v * g[i] for i, v in enumerate(x)], g

def process(samples, fs=RATE, trace=None):
    x = [v / 32768.0 for v in samples]
    if not x or crest(x) < TONE_CREST_DB:                        # the chirps and beeps: already dense, and short
        if trace is not None: trace.extend([crest(x)] * 4)
        return array.array('h', samples), [0.0], [1.0]
    x = highpass(x, fs, HPF_HZ)
    if trace is not None: trace.append(crest(x))
    for _ in range(ROTATOR_STAGES): x = allpass(x, fs, ROTATOR_HZ)
    if trace is not None: trace.append(crest(x))
    x, creduc = compress(x, fs)
    if trace is not None: trace.append(crest(x))
    d = 10 ** (DRIVE_DB / 20); x = [v * d for v in x]
    x, lgain = limit(x, fs)
    x = lowpass(highshelf(x, fs, TREBLE_HZ, TREBLE_DB), fs, LOWPASS_HZ)   # the tone put back (it can only lower the peaks a little)
    pk = max((abs(v) for v in x), default=0.0)
    if pk > 0: x = [v * CEILING / pk for v in x]                 # every clip ends with its loudest sample at the ceiling
    if trace is not None: trace.append(crest(x))
    out = array.array('h', (max(-32767, min(32767, int(round(v * 32767)))) for v in x))
    return out, creduc, lgain

def crest(x):
    if not x: return 0.0
    r = math.sqrt(sum(v * v for v in x) / len(x)); p = max(abs(v) for v in x)
    return 20 * math.log10(p / r) if r > 0 and p > 0 else 0.0

def read_wav(p):
    w = wave.open(p); n = w.getnframes(); ch = w.getnchannels(); fs = w.getframerate()
    if w.getsampwidth() != 2: sys.exit(f'{p}: not 16-bit')
    a = array.array('h', w.readframes(n)); w.close()
    if sys.byteorder != 'little': a.byteswap()
    return (a[::ch] if ch > 1 else a), fs

def write_wav(p, a, fs):
    if sys.byteorder != 'little': a = array.array('h', a); a.byteswap()
    tmp = p + '.tmp'; w = wave.open(tmp, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(fs); w.writeframes(a.tobytes()); w.close()
    os.replace(tmp, p)

def save(dst, src, y, fs, a):
    """A clip left as it was is copied byte for byte; a processed one is written afresh."""
    if y == a:
        import shutil; shutil.copyfile(src, dst + '.tmp'); os.replace(dst + '.tmp', dst)
    else: write_wav(dst, y, fs)

def build_clip(src, dst):
    """One clip, for build_sd.py."""
    a, fs = read_wav(src); y, _, _ = process(a, fs); save(dst, src, y, fs, a)

def db(v): return 20 * math.log10(v) if v > 0 else -120.0

def main():
    here = os.path.dirname(os.path.abspath(__file__)); out = os.path.join(here, '..', 'sd', 'hmi', 'audio')
    res = json.load(open(os.path.join(here, 'resources.json'))); os.makedirs(out, exist_ok=True)
    stats = '--stats' in sys.argv; rows = []; traces = []
    for aid, info in sorted(res.get('audio', {}).items(), key=lambda kv: int(kv[0])):
        src = os.path.join(here, info['file']) if 'file' in info else None
        if not src or not os.path.exists(src): continue
        a, fs = read_wav(src)
        tr = [] if stats else None
        y, creduc, lgain = process(a, fs, tr)
        if stats and len(a) / fs > 0.4: traces.append(tr)
        save(os.path.join(out, f'{aid}.wav'), src, y, fs, a)
        if stats and a:
            r0 = math.sqrt(sum(v * v for v in a) / len(a)); r1 = math.sqrt(sum(v * v for v in y) / len(y))
            p0 = max(abs(v) for v in a); p1 = max(abs(v) for v in y)
            rows.append((aid, len(a) / fs, db(r0 / 32768), db(r1 / 32768), db(p0 / r0) if r0 else 0, db(p1 / r1) if r1 else 0,
                         min(creduc), min(db(g) for g in lgain), sum(1 for g in lgain if db(g) < -3) / len(lgain)))
    if stats:
        sp = [r for r in rows if r[1] > 0.4]; med = lambda k: sorted(r[k] for r in sp)[len(sp) // 2]
        print(f'{len(rows)} clips; speech ({len(sp)}): average level {med(2):.1f} -> {med(3):.1f} dBFS, '
              f'peak-to-average {med(4):.1f} -> {med(5):.1f} dB; compressor at most {med(6):.1f} dB, limiter at most {med(7):.1f} dB, '
              f'limiter beyond 3 dB {100 * med(8):.0f} % of the time')
        st = ['high-pass', 'phase rotator', 'compressor', 'limiter + lift']
        print('  peak-to-average after each step (speech, median): ' + ', '.join(f'{st[k]} {sorted(t[k] for t in traces)[len(traces) // 2]:.1f} dB' for k in range(4)))
        for r in rows[:4] + sp[:4]: print('  clip %-3s %.2f s  level %.1f -> %.1f dBFS  crest %.1f -> %.1f dB  comp %.1f  lim %.1f dB  (%.0f %% >3 dB)' % (r[:8] + (100 * r[8],)))
    print(f'{len(res.get("audio", {}))} clips -> {os.path.normpath(out)}')

if __name__ == '__main__':
    main()
