#!/usr/bin/env python3
"""A film's compressed sound on the Mac (screen 1.11.93): the screen's own IMA ADPCM code - src/ima_adpcm.h, and
audioFillBlock and ringPushSamples lifted by name out of src/main.cpp - compiled with a stand-in card and ring, run over a
film's sound encoded as the film kit encodes it (TXV1B dev/video/filmkit.py), from the start and from moments part way in
(Play after a pause, the slider). Every sample must be ffmpeg's own decoding of the same file, bit for bit; and the
loss against the 16-bit sound it came from is reported.
   PY/bin/python hmi/test_film/ima_test.py sd/hmi/films/EASY.wav        (a Python with imageio-ffmpeg, or ffmpeg on the PATH)
   PY/bin/python hmi/test_film/ima_test.py sd/hmi/films/EASY.ima        (a film's sound as made: decoded, and compared)"""
import os, re, struct, subprocess, sys, tempfile, wave, array, math
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
try:
    import imageio_ffmpeg; FF = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError: FF = 'ffmpeg'
src = os.path.abspath(sys.argv[1])
main = open(os.path.join(ROOT, 'src', 'main.cpp')).read()
def lift(name):
    m = re.search(r'\nstatic [a-z]+ ' + name + r'\(.*?\n\}\n', main, re.S)
    assert m, name + ' not found in main.cpp'
    return m.group(0)
PROG = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <algorithm>
#include "@ROOT@/src/ima_adpcm.h"
struct CardFile { FILE *f = nullptr; int read(uint8_t *b, size_t n) { return (int) fread(b, 1, n, f); } } audioFile;
static uint32_t audioBlock = 0, audioBlockSamples = 0, audioSkip = 0, audioDataLeft = 0;
static std::vector<uint8_t> ring;
static void ringPush(const uint8_t *src, size_t n) { ring.insert(ring.end(), src, src + n); }
@LIFT@
int main(int argc, char **argv) {           // FILE MS OUT: the samples from MS on, as the screen plays them
    audioFile.f = fopen(argv[1], "rb"); if (!audioFile.f) return 2;
    uint8_t h[12]; if (fread(h, 1, 12, audioFile.f) != 12 || memcmp(h, "RIFF", 4) || memcmp(h + 8, "WAVE", 4)) return 3;
    uint32_t rate = 0, tag = 0, chans = 0, bits = 0, align = 0, dataStart = 0, dataSize = 0;
    for (;;) {                               // (the chunks, as the screen's wavOpenPath reads them)
        uint8_t ch[8]; if (fread(ch, 1, 8, audioFile.f) != 8) return 4;
        const uint32_t sz = ch[4] | (ch[5] << 8) | (ch[6] << 16) | ((uint32_t) ch[7] << 24);
        if (!memcmp(ch, "fmt ", 4)) { uint8_t f[16]; if (fread(f, 1, 16, audioFile.f) != 16) return 5; tag = f[0] | (f[1] << 8); chans = f[2] | (f[3] << 8); rate = f[4] | (f[5] << 8) | (f[6] << 16) | ((uint32_t) f[7] << 24); align = f[12] | (f[13] << 8); bits = f[14] | (f[15] << 8); fseek(audioFile.f, sz - 16, SEEK_CUR); }
        else if (!memcmp(ch, "data", 4)) { dataStart = (uint32_t) ftell(audioFile.f); dataSize = sz; break; }
        else fseek(audioFile.f, sz + (sz & 1), SEEK_CUR);
    }
    if (tag != 0x11 || chans != 1 || bits != 4 || align <= 4 || align > 1024) { fprintf(stderr, "not a film's IMA ADPCM (tag %u, %u channels, %u bits, blocks of %u)\n", tag, chans, bits, align); return 6; }
    audioBlock = align; audioBlockSamples = ldrcaudio::imaSamples(align); audioDataLeft = dataSize;
    const uint32_t ms = (uint32_t) atol(argv[2]);
    if (ms) { uint64_t skip; uint32_t samples; ldrcaudio::imaFrom(ms, rate, audioBlock, skip, samples); fseek(audioFile.f, dataStart + (long) skip, SEEK_SET); audioDataLeft -= (uint32_t) skip; audioSkip = samples; }
    static uint8_t tmp[4096];
    while (audioDataLeft > 0) if (!audioFillBlock(tmp)) { fprintf(stderr, "a block failed\n"); return 7; }
    FILE *o = fopen(argv[3], "wb"); fwrite(ring.data(), 1, ring.size(), o); fclose(o);
    printf("%u\n", rate);
    return 0;
}
'''
fails = 0
def check(ok, what):
    global fails
    print(('  ok    ' if ok else '  FAIL  ') + what)
    if not ok: fails += 1
with tempfile.TemporaryDirectory() as t:
    ima, ref, exe = os.path.join(t, 'film.ima'), os.path.join(t, 'ref.raw'), os.path.join(t, 'ima')
    # the film kit's encoding (filmkit.py): IMA ADPCM in a WAV, 22.05 kHz mono, trellis-searched (or the film's own .ima)
    if src.lower().endswith('.ima'): ima = src
    else: subprocess.run([FF, '-y', '-loglevel', 'error', '-i', src, '-ar', '22050', '-ac', '1', '-c:a', 'adpcm_ima_wav', '-trellis', '8', '-fflags', '+bitexact', '-map_metadata', '-1', '-f', 'wav', ima], check=True)
    subprocess.run([FF, '-y', '-loglevel', 'error', '-i', ima, '-f', 's16le', '-c:a', 'pcm_s16le', ref], check=True)
    open(os.path.join(t, 'ima.cpp'), 'w').write(PROG.replace('@ROOT@', ROOT).replace('@LIFT@', lift('ringPushSamples') + lift('audioFillBlock')))
    subprocess.run(['clang++', '-std=c++11', '-O1', '-Wall', '-o', exe, os.path.join(t, 'ima.cpp')], check=True)
    want = array.array('h'); want.frombytes(open(ref, 'rb').read())
    print('%s: %d samples (%.1f s), %d kB as IMA ADPCM (%d kB as 16-bit)' % (os.path.basename(src), len(want), len(want) / 22050, os.path.getsize(ima) // 1024, len(want) * 2 // 1024))
    for ms in (0, 1, 999, 4321, 30000, int(len(want) / 22.05) - 50):
        out = os.path.join(t, 'got%d.raw' % ms)
        r = subprocess.run([exe, ima, str(ms), out], capture_output=True, text=True)
        if r.returncode: check(False, 'from %d ms: the screen\'s decoding stopped (%s)' % (ms, r.stderr.strip())); continue
        got = array.array('h'); got.frombytes(open(out, 'rb').read())
        at = ms * 22050 // 1000
        same = got.tolist() == want[at:at + len(got)].tolist() and len(got) == len(want) - at
        if not same:
            first = next((i for i in range(min(len(got), len(want) - at)) if got[i] != want[at + i]), None)
            if first is not None: print('    the first difference: sample %d (block %d, sample %d of it): the screen %d, ffmpeg %d' % (at + first, (at + first) // 2041, (at + first) % 2041, got[first], want[at + first]))
        check(same, 'from %d ms: %d samples, every one ffmpeg\'s from sample %d' % (ms, len(got), at))
    r0 = 0
    if ima != src:
        with wave.open(src) as w:                 # what was lost: against the 16-bit sound
            orig = array.array('h'); orig.frombytes(w.readframes(w.getnframes())); r0 = w.getframerate()
    if r0 == 22050:
        n = min(len(orig), len(want)); sig = sum(x * x for x in orig[:n]); err = sum((a - b) ** 2 for a, b in zip(orig[:n], want[:n]))
        print('  the sound against its 16-bit self: %.1f dB signal to noise' % (10 * math.log10(sig / max(err, 1))))
print('ima_test: %d failures' % fails)
sys.exit(1 if fails else 0)
