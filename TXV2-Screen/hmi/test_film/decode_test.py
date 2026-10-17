#!/usr/bin/env python3
"""The film through the screen's own decoder, on the Mac (screen 1.11.85). JPEGDEC (the library the screen uses, from
.pio/libdeps) and src/film_device.h's own filmDraw (lifted out by name) are compiled with a stand-in screen; every picture
of a real film is decoded twice - on top of the one before, as the player does (only changed pixels copied), and onto a
clean screen - and the two must be identical; then a few are compared with Pillow's decode of the same JPEG.
   PY/bin/python hmi/test_film/decode_test.py sd/films/EASY.ldf      (a Python with Pillow)"""
import io, os, re, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
LIB = os.path.join(ROOT, '.pio', 'libdeps', 'ota', 'JPEGDEC', 'src')
if not os.path.isdir(LIB): sys.exit('JPEGDEC not found in .pio/libdeps/ota (build the screen once: pio run -e ota)')
film = os.path.abspath(sys.argv[1])
dev = open(os.path.join(ROOT, 'src', 'film_device.h')).read()
m = re.search(r'\nstatic int filmDraw\(JPEGDRAW \*p\) \{.*?\n\}\n', dev, re.S)
assert m, 'filmDraw not found in film_device.h'
DRAW = m.group(0)
PROG = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <algorithm>
#include "JPEGDEC.h"
#include "../../src/film_core.h"
static const int W = 800, H = 480;
static uint16_t *topFb = nullptr;
static long dirtyPx = 0; static int dirtyCalls = 0;
static void dirty(int, int, int w, int h) { dirtyPx += (long) w * h; ++dirtyCalls; }
@DRAW@
static JPEGDEC jpeg;
static bool decodeInto(uint16_t *fb, uint8_t *data, int size) {
    topFb = fb;
    if (!jpeg.openRAM(data, size, filmDraw)) return false;
    jpeg.setPixelType(RGB565_LITTLE_ENDIAN);
    const bool ok = jpeg.decode(0, 0, 0) != 0; jpeg.close(); return ok;
}
int main(int argc, char **argv) {
    FILE *fp = fopen(argv[1], "rb"); if (!fp) return 2;
    std::vector<uint8_t> f; uint8_t b[65536]; size_t n; while ((n = fread(b, 1, sizeof b, fp)) > 0) f.insert(f.end(), b, b + n); fclose(fp);
    ldrcfilm::Header h; uint32_t mx = 0;
    if (!ldrcfilm::parseHeader(f.data(), (uint32_t) f.size(), h, W, H) || !ldrcfilm::tableSound(f.data() + ldrcfilm::HEADER_BYTES, h, (uint32_t) f.size(), mx)) { printf("BAD FILM\n"); return 1; }
    const uint8_t *t = f.data() + ldrcfilm::HEADER_BYTES;
    std::vector<uint16_t> inc(W * H, 0), fresh(W * H);
    int pictures = 0, mismatched = 0, failed = 0, still = 0; long totalDirty = 0;
    int32_t last = -1;
    for (uint32_t frame = 0; frame < h.frames; ++frame) {
        const int32_t k = ldrcfilm::pictureFor((int32_t) frame, last, t);
        if (k < 0) { ++still; continue; }
        const uint32_t off = ldrcfilm::rd32(t + 8 * k), size = ldrcfilm::rd32(t + 8 * k + 4);
        std::vector<uint8_t> pic(f.begin() + off, f.begin() + off + size), pic2 = pic;
        dirtyPx = 0; dirtyCalls = 0;
        if (!decodeInto(inc.data(), pic.data(), (int) size)) { ++failed; continue; }
        totalDirty += dirtyPx;
        std::fill(fresh.begin(), fresh.end(), 0xF81F);   // (a colour no picture has, so nothing is left unwritten unseen)
        const long keepDirty = dirtyPx; int keepCalls = dirtyCalls;
        if (!decodeInto(fresh.data(), pic2.data(), (int) size)) { ++failed; continue; }
        dirtyPx = keepDirty; dirtyCalls = keepCalls;
        if (memcmp(inc.data(), fresh.data(), W * H * 2) != 0) ++mismatched;
        ++pictures; last = k;
        if (argc > 2 && (pictures == 1 || pictures == 40 || pictures == 90 || pictures == 145)) {
            char path[512]; snprintf(path, sizeof path, "%s/pic_%u.565", argv[2], (unsigned) k);
            FILE *o = fopen(path, "wb"); fwrite(inc.data(), 2, W * H, o); fclose(o);
            printf("SAVED %u\n", (unsigned) k);
        }
    }
    printf("pictures %d, frames still %d, failed %d, incremental != fresh %d, average marked for the panel %ld px a picture\n",
           pictures, still, failed, mismatched, pictures ? totalDirty / pictures : 0);
    return (failed || mismatched || !pictures) ? 1 : 0;
}
'''.replace('@DRAW@', DRAW)
with tempfile.TemporaryDirectory() as d:
    cpp = os.path.join(d, 'decode.cpp'); exe = os.path.join(d, 'decode')
    open(cpp, 'w').write(PROG.replace('"../../src/film_core.h"', '"%s"' % os.path.join(os.path.abspath(ROOT), 'src', 'film_core.h')))
    r = subprocess.run(['clang++', '-std=c++17', '-O2', '-w', '-I', LIB, '-o', exe, cpp, os.path.join(LIB, 'JPEGDEC.cpp')], capture_output=True, text=True)
    if r.returncode: print(r.stdout[-3000:], r.stderr[-3000:]); sys.exit('does not compile')
    r = subprocess.run([exe, film, d], capture_output=True, text=True)
    print(r.stdout.strip())
    ok = r.returncode == 0
    # the colours: JPEGDEC against Pillow, for the pictures saved
    from PIL import Image
    data = open(film, 'rb').read()
    worst = 0
    for line in r.stdout.split('\n'):
        if not line.startswith('SAVED '): continue
        k = int(line.split()[1]); off, size = struct.unpack('<II', data[20 + 8 * k: 28 + 8 * k])
        ref = Image.open(io.BytesIO(data[off:off + size])).convert('RGB').tobytes()
        raw = open(os.path.join(d, 'pic_%d.565' % k), 'rb').read()
        px = struct.unpack('<%dH' % (len(raw) // 2), raw)
        for i in range(0, len(px), 97):
            v = px[i]; r5, g6, b5 = (v >> 11) & 31, (v >> 5) & 63, v & 31
            rr, gg, bb = ref[3 * i], ref[3 * i + 1], ref[3 * i + 2]
            worst = max(worst, abs((r5 << 3) - (rr & 0xF8)), abs((g6 << 2) - (gg & 0xFC)), abs((b5 << 3) - (bb & 0xF8)))
    print('colours against Pillow: the largest difference %d of 255 (a step of RGB565 is 4 or 8)' % worst)
    ok = ok and worst <= 24
print('decode test:', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
