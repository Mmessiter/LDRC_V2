#!/usr/bin/env python3
"""Speak every film's lines at once (18 Oct 2026), so that the films' own builds find each one in the voice cache: the
models are loaded once, not once a film. First collect the lines:
   for f in films/*.py; do LDRC_COLLECT=/path/lines.json PY $f /tmp/x; done
then:  TTS_PY speak_all.py /path/lines.json [VOICE] [EMOTION]      (VOICE as LDRC_VOICE, default filmkit's)
Lines spoken before (the same voice and words) are not spoken again."""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
lines = json.load(open(sys.argv[1]))
src = open(os.path.join(HERE, 'filmkit.py')).read()
voice = sys.argv[2] if len(sys.argv) > 2 else src.split("VOICE = '")[1].split("'")[0]
emotion = float(sys.argv[3] if len(sys.argv) > 3 else src.split("EMOTION = '")[1].split("'")[0])
cache = src.split("VOICE_CACHE = '")[1].split("'")[0]
engine, who = voice.split(':', 1)
seen, todo = set(), []
with tempfile.TemporaryDirectory() as d:
    for i, l in enumerate(lines):
        if l['text'] in seen: continue
        seen.add(l['text']); todo.append({'text': l['text'], 'out': os.path.join(d, '%05d.wav' % i)})
    job = os.path.join(d, 'job.json')
    json.dump({'engine': engine, 'voice': os.path.join(HERE, 'voices', who + '.wav'), 'emotion': emotion, 'cache': cache, 'lines': todo}, open(job, 'w'))
    print('%d lines (%d different), %s, emotion %.2f' % (len(lines), len(todo), voice, emotion), flush=True)
    env = dict(os.environ); env.setdefault('HF_HOME', '/Volumes/2TB SSD/ClaudeScratch/hf')
    sys.exit(subprocess.run([sys.executable, os.path.join(HERE, 'voice_clone.py'), job], env=env).returncode)
