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
BARY = re.search(r'FILM_BAR_Y = (\d+)', dev).group(1)
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
static bool filmStripKept = false; static uint16_t *filmStrip = nullptr; static const int FILM_BAR_Y = @BARY@;   // (1.11.89: the paused bar's keeping; not used here)
static long dirtyPx = 0; static int dirtyCalls = 0;
static void dirty(int, int, int w, int h) { dirtyPx += (long) w * h; ++dirtyCalls; }
@DRAW@
static JPEGDEC jpeg;
int main(int argc, char **argv) {
    FILE *fp = fopen(argv[1], "rb"); if (!fp) return 2;
    std::vector<uint8_t> f; uint8_t b[65536]; size_t n; while ((n = fread(b, 1, sizeof b, fp)) > 0) f.insert(f.end(), b, b + n); fclose(fp);
    ldrcfilm::Header h; uint32_t mx = 0;
    if (!ldrcfilm::parseHeader(f.data(), (uint32_t) f.size(), h, W, H)) { printf("BAD FILM\n"); return 1; }
    const uint8_t *t = f.data() + ldrcfilm::HEADER_BYTES;
    uint32_t nsec = 1, extra = 0; const uint8_t *secs = nullptr; static uint8_t one[4] = {0, 0, 0, 0};
    if (h.version >= 3) { nsec = ldrcfilm::rd32(t + 8 * h.frames); secs = t + 8 * h.frames + 4; extra = 4 + 4 * nsec;
        if (!ldrcfilm::sectionsSound(secs, nsec, h)) { printf("BAD SECTIONS\n"); return 1; } } else secs = one;
    if (!ldrcfilm::tableSound(t, h, (uint32_t) f.size(), mx, extra)) { printf("BAD TABLE\n"); return 1; }
    auto decodeOne = [&](int32_t k) -> bool {                      // a picture onto the framebuffer topFb points at
        const uint32_t off = ldrcfilm::rd32(t + 8 * k), size = ldrcfilm::sizeOf(t, k);
        std::vector<uint8_t> pic(f.begin() + off, f.begin() + off + size);
        uint16_t x, y, w, hh; uint32_t jo;
        if (!ldrcfilm::pictureAt(pic.data(), size, h, x, y, w, hh, jo)) return false;
        if (ldrcfilm::isKey(t, k) && (x || y || w != W || hh != H)) return false;   // (a key must be the whole screen)
        if (!jpeg.openRAM(pic.data() + jo, (int) (size - jo), filmDraw)) return false;
        jpeg.setPixelType(RGB565_LITTLE_ENDIAN); const bool ok = jpeg.decode(x, y, 0) != 0; jpeg.close(); return ok;
    };
    std::vector<uint16_t> fb(W * H, 0xF81F); topFb = fb.data();
    int pictures = 0, failed = 0, still = 0, jumps = 0, badJumps = 0; long totalDirty = 0, totalArea = 0;
    int32_t last = -1;
    for (uint32_t frame = 0; frame < h.frames; ++frame) {
        const int32_t k = ldrcfilm::pictureFor((int32_t) frame, last, t);
        if (k < 0) { ++still; continue; }
        const uint32_t off = ldrcfilm::rd32(t + 8 * k), size = ldrcfilm::sizeOf(t, k);
        uint16_t x, y, w, hh; uint32_t jo;
        if (!ldrcfilm::pictureAt(f.data() + off, size, h, x, y, w, hh, jo)) { ++failed; continue; }
        dirtyPx = 0;
        if (!decodeOne(k)) { ++failed; printf("FAILED picture %d at frame %u: %u,%u %ux%u, %u bytes, key %d, JPEGDEC error %d\n", (int) k, (unsigned) frame, x, y, w, hh, (unsigned) size, (int) ldrcfilm::isKey(t, k), jpeg.getLastError()); continue; }
        totalDirty += dirtyPx; totalArea += (long) w * hh; ++pictures; last = k;
        // (1.11.88) at each section's start: a jump there - its key picture, then every picture after it - gives the same screen
        for (uint32_t s = 0; s < nsec; ++s) if ((int32_t) ldrcfilm::rd32(secs + 4 * s) == (int32_t) frame) {
            std::vector<uint16_t> jumped(W * H, 0x1234); uint16_t *keep = topFb; topFb = jumped.data();
            const int32_t k0 = ldrcfilm::keyAtOrBefore((int32_t) frame, t, h.version); bool ok = k0 >= 0 && decodeOne(k0);
            for (int32_t i = k0 + 1; ok && i <= (int32_t) frame; ++i) if (ldrcfilm::sizeOf(t, i)) ok = decodeOne(i);
            topFb = keep; ++jumps;
            if (!ok || memcmp(jumped.data(), fb.data(), W * H * 2) != 0) ++badJumps;
        }
        if (pictures == 1 || pictures % 40 == 0 || frame + 1 == h.frames) {
            char path[512]; snprintf(path, sizeof path, "%s/pic_%u.565", argv[2], (unsigned) k);
            FILE *o = fopen(path, "wb"); fwrite(fb.data(), 2, W * H, o); fclose(o); printf("SAVED %u\n", (unsigned) k);
        }
    }
    { char path[512]; snprintf(path, sizeof path, "%s/pic_%d.565", argv[2], (int) last); FILE *o = fopen(path, "wb"); fwrite(fb.data(), 2, W * H, o); fclose(o); printf("SAVED %d\n", (int) last); }
    long unwritten = 0; for (uint16_t v : fb) if (v == 0xF81F) ++unwritten;
    printf("version %u: pictures %d, frames still %d, failed %d, unwritten pixels %ld; a picture covers %ld px on average, %ld of them changed; %u sections, %d jumps to them, %d wrong\n",
           h.version, pictures, still, failed, unwritten, pictures ? totalArea / pictures : 0, pictures ? totalDirty / pictures : 0, (unsigned) nsec, jumps, badJumps);
    return (failed || unwritten || !pictures || badJumps || (h.version >= 3 && jumps != (int) nsec)) ? 1 : 0;
}
'''.replace('@BARY@', BARY).replace('@DRAW@', DRAW).replace('@CORE@', os.path.join(os.path.abspath(ROOT), 'src', 'film_core.h'))
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
    ref = Image.new('RGB', (fw, fh), (255, 0, 255)); worst = 0; compared = 0; last = -1; total = 0; samples = 0; big = 0
    def size_of(i): o, s = struct.unpack('<II', data[20 + 8 * i: 28 + 8 * i]); return o, s & 0x7FFFFFFF
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
                dd = max(abs((r5 << 3) - (rb[3 * i] & 0xF8)), abs((g6 << 2) - (rb[3 * i + 1] & 0xFC)), abs((b5 << 3) - (rb[3 * i + 2] & 0xF8)))
                worst = max(worst, dd); total += dd; samples += 1; big += dd > 24
            compared += 1
    mean = total / max(1, samples)
    print('the screen against Pillow, the whole film applied picture by picture: %d moments compared, on average %.2f of 255 apart, the largest %d (a step of RGB565 is 4 or 8), %d of %d points more than 24 apart' % (compared, mean, worst, big, samples))
    # (17 Oct 2026: two decoders round a sharp edge of text differently - one point in ten thousand, 32 apart - so the test is
    # the average and the share of points far apart; a picture misplaced or corrupt moves both a long way)
    ok = ok and compared >= 2 and mean <= 4.0 and big * 1000 <= samples and worst <= 64
    # (17 Oct 2026) every picture alone, as JPEGDEC draws it, against Pillow: JPEGDEC 1.8.4 can draw a picture wrongly without
    # a word (the System film had one 82 % wrong) - a moment above may never see it if the next page covers it
    one = os.path.join(d, 'one.cpp'); one_exe = os.path.join(d, 'one')
    open(one, 'w').write(r'''
#include <cstdio>
#include <vector>
#include "JPEGDEC.h"
static std::vector<unsigned short> out; static int OW, OH;
static int draw(JPEGDRAW *p) { for (int r = 0; r < p->iHeight; ++r) for (int c = 0; c < p->iWidth; ++c) { const int x = p->x + c, y = p->y + r; if (x < OW && y < OH) out[y * OW + x] = p->pPixels[r * p->iWidth + c]; } return 1; }
static JPEGDEC j;
int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb"), *o = fopen(argv[2], "wb"); if (!f || !o) return 2;
    unsigned h[3];
    while (fread(h, 4, 3, f) == 3) {
        std::vector<unsigned char> b(h[2]); if (fread(b.data(), 1, h[2], f) != h[2]) return 3;
        OW = (int) h[0]; OH = (int) h[1]; out.assign((size_t) OW * OH, 0xF81F);
        if (j.openRAM(b.data(), (int) h[2], draw)) { j.setPixelType(RGB565_LITTLE_ENDIAN); j.decode(0, 0, 0); j.close(); }
        fwrite(out.data(), 2, out.size(), o);
    }
    fclose(o); return 0;
}
''')
    subprocess.run(['clang++', '-std=c++17', '-O1', '-w', '-I', LIB, '-o', one_exe, one, os.path.join(LIB, 'JPEGDEC.cpp')], check=True)
    pics = []
    for k in range(frames):
        off, size = size_of(k)
        if not size: continue
        blob = data[off:off + size]
        if ver >= 2: x, y, w, h = struct.unpack('<HHHH', blob[:8]); pics.append((k, w, h, blob[8:]))
        else: pics.append((k, fw, fh, blob))
    with open(os.path.join(d, 'pics.bin'), 'wb') as f:
        for k, w, h, jp in pics: f.write(struct.pack('<III', w, h, len(jp)) + jp)
    subprocess.run([one_exe, os.path.join(d, 'pics.bin'), os.path.join(d, 'pics.565')], check=True)
    raw = open(os.path.join(d, 'pics.565'), 'rb').read(); at = 0; wrong = []
    for k, w, h, jp in pics:
        px = struct.unpack_from('<%dH' % (w * h), raw, at); at += 2 * w * h
        ref = Image.open(io.BytesIO(jp)).convert('RGB').tobytes(); far = tot = 0
        for i in range(0, w * h, 7):
            v = px[i]; dd = max(abs((((v >> 11) & 31) << 3) - (ref[3 * i] & 0xF8)), abs((((v >> 5) & 63) << 2) - (ref[3 * i + 1] & 0xFC)), abs(((v & 31) << 3) - (ref[3 * i + 2] & 0xF8)))
            tot += 1; far += dd > 24
        if far * 1000 > tot: wrong.append('frame %d (%.0f%% wrong)' % (k, far * 100.0 / tot))
    print('every picture alone, JPEGDEC against Pillow: %d pictures, %d drawn wrongly%s' % (len(pics), len(wrong), (': ' + ', '.join(wrong[:5])) if wrong else ''))
    ok = ok and not wrong
print('decode test:', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
