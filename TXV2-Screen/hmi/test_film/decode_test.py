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
#include "@CORE@"
static const int W = 800, H = 480;
static uint16_t *topFb = nullptr;
static long dirtyPx = 0; static int dirtyCalls = 0;
static void dirty(int, int, int w, int h) { dirtyPx += (long) w * h; ++dirtyCalls; }
@DRAW@
static JPEGDEC jpeg;
int main(int argc, char **argv) {
    FILE *fp = fopen(argv[1], "rb"); if (!fp) return 2;
    std::vector<uint8_t> f; uint8_t b[65536]; size_t n; while ((n = fread(b, 1, sizeof b, fp)) > 0) f.insert(f.end(), b, b + n); fclose(fp);
    ldrcfilm::Header h; uint32_t mx = 0;
    if (!ldrcfilm::parseHeader(f.data(), (uint32_t) f.size(), h, W, H) || !ldrcfilm::tableSound(f.data() + ldrcfilm::HEADER_BYTES, h, (uint32_t) f.size(), mx)) { printf("BAD FILM\n"); return 1; }
    const uint8_t *t = f.data() + ldrcfilm::HEADER_BYTES;
    std::vector<uint16_t> fb(W * H, 0xF81F); topFb = fb.data();
    int pictures = 0, failed = 0, still = 0; long totalDirty = 0, totalArea = 0;
    int32_t last = -1;
    for (uint32_t frame = 0; frame < h.frames; ++frame) {
        const int32_t k = ldrcfilm::pictureFor((int32_t) frame, last, t);
        if (k < 0) { ++still; continue; }
        const uint32_t off = ldrcfilm::rd32(t + 8 * k), size = ldrcfilm::rd32(t + 8 * k + 4);
        std::vector<uint8_t> pic(f.begin() + off, f.begin() + off + size);
        uint16_t x, y, w, hh; uint32_t jo;
        if (!ldrcfilm::pictureAt(pic.data(), size, h, x, y, w, hh, jo)) { ++failed; continue; }
        dirtyPx = 0;
        if (!jpeg.openRAM(pic.data() + jo, (int) (size - jo), filmDraw)) { ++failed; continue; }
        jpeg.setPixelType(RGB565_LITTLE_ENDIAN);
        if (!jpeg.decode(x, y, 0)) { ++failed; jpeg.close(); continue; }
        jpeg.close();
        totalDirty += dirtyPx; totalArea += (long) w * hh; ++pictures; last = k;
        if (pictures == 1 || pictures % 40 == 0 || frame + 1 == h.frames) {
            char path[512]; snprintf(path, sizeof path, "%s/pic_%u.565", argv[2], (unsigned) k);
            FILE *o = fopen(path, "wb"); fwrite(fb.data(), 2, W * H, o); fclose(o); printf("SAVED %u\n", (unsigned) k);
        }
    }
    { char path[512]; snprintf(path, sizeof path, "%s/pic_%d.565", argv[2], (int) last); FILE *o = fopen(path, "wb"); fwrite(fb.data(), 2, W * H, o); fclose(o); printf("SAVED %d\n", (int) last); }
    long unwritten = 0; for (uint16_t v : fb) if (v == 0xF81F) ++unwritten;
    printf("version %u: pictures %d, frames still %d, failed %d, unwritten pixels %ld; a picture covers %ld px on average, %ld of them changed\n",
           h.version, pictures, still, failed, unwritten, pictures ? totalArea / pictures : 0, pictures ? totalDirty / pictures : 0);
    return (failed || unwritten || !pictures) ? 1 : 0;
}
'''.replace('@DRAW@', DRAW).replace('@CORE@', os.path.join(os.path.abspath(ROOT), 'src', 'film_core.h'))
with tempfile.TemporaryDirectory() as d:
    cpp = os.path.join(d, 'decode.cpp'); exe = os.path.join(d, 'decode')
    open(cpp, 'w').write(PROG)
    r = subprocess.run(['clang++', '-std=c++17', '-O2', '-w', '-I', LIB, '-o', exe, cpp, os.path.join(LIB, 'JPEGDEC.cpp')], capture_output=True, text=True)
    if r.returncode: print(r.stdout[-3000:], r.stderr[-3000:]); sys.exit('does not compile')
    r = subprocess.run([exe, film, d], capture_output=True, text=True)
    print('\n'.join(l for l in r.stdout.strip().split('\n') if not l.startswith('SAVED')))
    ok = r.returncode == 0
    # the same film applied with Pillow's decoder, picture by picture: the screen's picture must match at every point saved
    from PIL import Image
    data = open(film, 'rb').read()
    ver, fw, fh, fps, frames = struct.unpack('<HHHHI', data[8:20])
    saved = sorted(int(l.split()[1]) for l in r.stdout.split('\n') if l.startswith('SAVED '))
    ref = Image.new('RGB', (fw, fh), (255, 0, 255)); worst = 0; compared = 0; last = -1
    def size_of(i): return struct.unpack('<II', data[20 + 8 * i: 28 + 8 * i])
    for k in range(frames):
        off, size = size_of(k)
        if not size: continue
        blob = data[off:off + size]
        if ver >= 2: x, y, w, h = struct.unpack('<HHHH', blob[:8]); jp = blob[8:]
        else: x = y = 0; jp = blob
        ref.paste(Image.open(io.BytesIO(jp)).convert('RGB'), (x, y))
        if k in saved:
            raw = open(os.path.join(d, 'pic_%d.565' % k), 'rb').read(); px = struct.unpack('<%dH' % (len(raw) // 2), raw); rb = ref.tobytes()
            for i in range(0, len(px), 61):
                v = px[i]; r5, g6, b5 = (v >> 11) & 31, (v >> 5) & 63, v & 31
                worst = max(worst, abs((r5 << 3) - (rb[3 * i] & 0xF8)), abs((g6 << 2) - (rb[3 * i + 1] & 0xFC)), abs((b5 << 3) - (rb[3 * i + 2] & 0xF8)))
            compared += 1
    print('the screen against Pillow, the whole film applied picture by picture: %d moments compared, the largest difference %d of 255 (a step of RGB565 is 4 or 8)' % (compared, worst))
    ok = ok and worst <= 24 and compared >= 2
print('decode test:', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
