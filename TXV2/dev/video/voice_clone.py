#!/usr/bin/env python3
"""The animations' voice from 18 Oct 2026, spoken on this Mac (nothing is sent anywhere) through mlx-audio by a model that
copies a voice from a recording of it. Malcolm (18 Oct): "I wonder if the voice can sound a bit more human with some
emotion?" - then, of three samples, "We like voice number one best 'Emma'. But if there is a still better one which sounds
more alive and British, so much the better", and "If she sounds bored, that's not a good thing!"

So voices/emma.wav is Emma herself (Kokoro bf_emma, the films' voice since 17 Oct) saying voices/emma.ref.txt, and an
engine speaks every line in her voice:
   cbox  Chatterbox (Resemble AI, MIT licence): her voice with its emotion turned up (LDRC_EMOTION, 0.25 to 1: how lively;
         0.75 by default: of three samples Malcolm chose "Emma, number three", 0.75). Measured on four lines: pitch spread 3.5 semitones against her own 2.2, still 0.99 like her.
   qwen  Qwen3-TTS Base (Alibaba, Apache 2.0): copies her voice and her way of speaking too (as flat as she was).
(voices/woman.wav and man.wav are two voices Qwen3-TTS designed from a description; Malcolm preferred Emma.)

A model like these can now and then babble on after the words or drop a phrase, so every line is written down again by
Whisper (also on this Mac) and compared with what it should say; a line that does not match is spoken again (another
seed), and the build stops if none of the tries match.

   TTS_PY voice_clone.py JOB.json
   JOB.json = {"engine": "cbox" | "qwen", "voice": "<voices/who.wav>", "emotion": 0.75,
               "lines": [{"text": "...", "out": "<wav>"}, ...], "cache": "<dir>"}
Lines already spoken (same engine, voice, emotion and words) come from the cache. TTS_PY = a Python with mlx-audio and
transformers; HF_HOME should be on the 2TB SSD (the models are some 8 GB)."""
import hashlib, json, os, re, sys, wave
import numpy as np

MODELS = {'qwen': 'mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16', 'cbox': 'mlx-community/Chatterbox-TTS-fp16'}
STT_MODEL = 'mlx-community/whisper-large-v3-turbo'
TRIES = 8

# ------------------------------------------------------------------ the words, compared
_ONES = {'zero': 0, 'nought': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
         'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
         'seventeen': 17, 'eighteen': 18, 'nineteen': 19}
_TENS = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90}
def _numbers(words):
    """spelled numbers as digits ("a hundred and eighty" -> 180, "twenty five point five" -> 25.5); two numbers side by side
    stay two ("eighty, ninety")"""
    out, i = [], 0
    def isnum(w): return w in _ONES or w in _TENS or w in ('hundred', 'thousand')
    while i < len(words):
        w = words[i]
        if isnum(w) or (w == 'a' and i + 1 < len(words) and words[i + 1] in ('hundred', 'thousand')):
            total, cur, j, last = 0, 0, i, None             # (last: what came before - 'ones', 'tens', 'hundred', 'thousand')
            while j < len(words):
                v = words[j]
                if v in _ONES and last not in ('ones',) and not (last == 'tens' and _ONES[v] > 9) and not (last == 'tens' and _ONES[v] == 0): cur += _ONES[v]; last = 'ones'
                elif v in _TENS and last not in ('ones', 'tens'): cur += _TENS[v]; last = 'tens'
                elif v == 'hundred' and last in (None, 'ones', 'a'): cur = max(cur, 1) * 100; last = 'hundred'
                elif v == 'thousand' and last in (None, 'ones', 'tens', 'hundred', 'a'): total += max(cur, 1) * 1000; cur = 0; last = 'thousand'
                elif v == 'a' and last is None and j + 1 < len(words) and words[j + 1] in ('hundred', 'thousand'): last = 'a'
                elif v == 'and' and last in ('hundred', 'thousand') and j + 1 < len(words) and (words[j + 1] in _ONES or words[j + 1] in _TENS): pass
                else: break
                j += 1
            n = str(total + cur)
            if j + 1 < len(words) and words[j] == 'point' and words[j + 1] in _ONES:   # (25 point 5)
                n += '.' + str(_ONES[words[j + 1]]); j += 2
            out.append(n); i = j
        else: out.append(w); i += 1
    return out
def norm(s):
    s = s.lower().replace('%', ' percent').replace('&', ' and ').replace('-', ' ')
    s = re.sub(r"(\d),(\d)", r"\1\2", s)
    out = []
    for part in re.split(r"(?<!\d)[.,;:!?]|[.,;:!?](?!\d)", s.replace("'", '')):   # (numbers never run on over a full stop or a comma)
        words = ['ok' if w == 'okay' else w for w in re.findall(r"[a-z]+|\d+(?:\.\d+)?", part)]
        out += _numbers(words)
    return ''.join(out)
def distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1): cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]
def matches(want, heard):
    """(the error, whether it will do): within 12 % of the letters, and nothing much said beyond the words"""
    a, b = norm(want), norm(heard)
    err = distance(a, b) / max(1, len(a))
    return err, err <= 0.12 and len(b) <= len(a) * 1.12 + 6

# ------------------------------------------------------------------ the sound
def read(p):
    with wave.open(p) as w: return np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float32) / 32768, w.getframerate()
def write(p, a, sr):
    tmp = p + '.part'
    with wave.open(tmp, 'w') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((np.clip(a, -1, 1) * 32767).astype('<i2').tobytes())
    os.replace(tmp, p)
def trim(a, sr, lead=0.05, tail=0.15):
    """the silence before and after the words cut to a little (the film's own pauses are its timing)"""
    hop = int(sr * 0.01); n = len(a) // hop
    if n == 0: return a
    rms = np.sqrt((a[:n * hop].reshape(n, hop) ** 2).mean(axis=1) + 1e-12)
    loud = np.nonzero(rms > max(rms.max() * 0.02, 10 ** (-48 / 20)))[0]
    if len(loud) == 0: return a
    s, e = max(0, loud[0] * hop - int(lead * sr)), min(len(a), (loud[-1] + 1) * hop + int(tail * sr))
    return a[s:e]

class Speaker:
    """one engine, loaded once, speaking a line in the voice of a recording"""
    def __init__(self, engine, voice, ref_text, emotion):
        import mlx.core as mx
        from mlx_audio.tts.utils import load_model
        self.mx, self.engine, self.emotion = mx, engine, emotion
        self.model = load_model(MODELS[engine]); self.sr = self.model.sample_rate
        ref, rsr = read(voice)
        if engine == 'qwen':
            assert rsr == 24000, 'the voice recording must be 24 kHz'
            self.ref, self.ref_text = mx.array(ref), ref_text
        else:
            self.conds = self.model.prepare_conditionals(mx.array(ref), rsr, emotion)
    def say(self, text, seed):
        self.mx.random.seed(seed)
        if self.engine == 'qwen': res = self.model.generate(text=text, ref_audio=self.ref, ref_text=self.ref_text, language='English')
        else: res = self.model.generate(text=text, conds=self.conds, exaggeration=self.emotion, cfg_weight=0.4, verbose=False)
        return trim(np.concatenate([np.array(r.audio, dtype=np.float32) for r in res]), self.sr)

def main():
    job = json.load(open(sys.argv[1]))
    engine, voice, emotion = job.get('engine', 'cbox'), job['voice'], float(job.get('emotion', 0.75))
    ref_text = open(os.path.splitext(voice)[0] + '.ref.txt').read().strip()
    vkey = hashlib.sha1(open(voice, 'rb').read() + ref_text.encode() + ('%s %s %.2f' % (engine, MODELS[engine], emotion)).encode()).hexdigest()[:12]
    cache = job.get('cache'); os.makedirs(cache, exist_ok=True) if cache else None
    todo = []
    for ln in job['lines']:
        key = hashlib.sha1((vkey + '\n' + ln['text']).encode()).hexdigest()[:20]
        hit = cache and os.path.join(cache, key + '.wav')
        if hit and os.path.exists(hit):
            a, sr = read(hit); write(ln['out'], a, sr)
        else: todo.append((ln, hit))
    if not todo: print('voice: all %d lines from the cache' % len(job['lines'])); return
    from mlx_audio.stt.utils import load_model as load_stt
    from transformers import WhisperProcessor
    sp = Speaker(engine, voice, ref_text, emotion)
    stt = load_stt(STT_MODEL)
    if getattr(stt, '_processor', None) is None: stt._processor = WhisperProcessor.from_pretrained('openai/whisper-large-v3-turbo')
    bad = []
    for ln, hit in todo:
        best = None
        for t in range(TRIES):
            a = sp.say(ln['text'], 1000 + 7919 * t)
            write(ln['out'], a, sp.sr)
            r = stt.generate(ln['out'], language='en'); heard = (r.text if hasattr(r, 'text') else str(r)).strip()
            err, ok = matches(ln['text'], heard)
            if ln.get('written'):                                 # (24 Oct: the written form - "ID" is said "eye dee" and rightly heard "ID")
                err2, ok2 = matches(ln['written'], heard)
                if (ok2, -err2) > (ok, -err): err, ok = err2, ok2
            if best is None or (ok, -err) > (best[3], -best[0]): best = (err, a, heard, ok)
            if ok: break
        err, a, heard, ok = best; write(ln['out'], a, sp.sr)
        if ok:
            if hit: write(hit, a, sp.sr)
            print('voice: "%s" (%.1f s%s)' % (ln['text'][:60], len(a) / sp.sr, ', try %d' % (t + 1) if t else ''), flush=True)
        else: bad.append((ln['text'], heard, err))
    for text, heard, err in bad: print('VOICE FAULT: "%s"\n   heard: "%s" (%.0f %% wrong)' % (text, heard, 100 * err), flush=True)
    if bad: sys.exit(1)

if __name__ == '__main__': main()
