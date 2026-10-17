// The LDRC film's sums (screen 1.11.85), apart from the card, the decoder and the panel so the Mac can test them
// (hmi/test_film). The film: "LDRCFILM", then version 1, width, height, frames a second (u16 each, little-endian) and the
// number of frames (u32); then each frame's offset in the file and size (u32 each) - size 0: the same picture as the
// frame before, nothing to decode; then the pictures, baseline JPEG. Written by TXV1B dev/video (LDRC_TARGET=screen),
// played by src/film_device.h from /hmi/films, its sound beside it (<name>.wav, 22.05 kHz). Why a film at all: film_device.h.
#pragma once
#include <stdint.h>
#include <string.h>

namespace ldrcfilm {
struct Header { uint16_t version = 0, w = 0, h = 0, fps = 0; uint32_t frames = 0; };
static const uint32_t HEADER_BYTES = 20, MAX_FRAMES = 20000, MAX_PICTURE = 400000;
inline uint16_t rd16(const uint8_t *p) { return (uint16_t) (p[0] | (p[1] << 8)); }
inline uint32_t rd32(const uint8_t *p) { return (uint32_t) p[0] | ((uint32_t) p[1] << 8) | ((uint32_t) p[2] << 16) | ((uint32_t) p[3] << 24); }
// Ours, version 1, the screen's own size, 1 to 30 frames a second, 1 to MAX_FRAMES frames
inline bool parseHeader(const uint8_t *b, uint32_t n, Header &h, uint16_t screenW, uint16_t screenH) {
    if (n < HEADER_BYTES || memcmp(b, "LDRCFILM", 8) != 0) return false;
    h.version = rd16(b + 8); h.w = rd16(b + 10); h.h = rd16(b + 12); h.fps = rd16(b + 14); h.frames = rd32(b + 16);
    return h.version == 1 && h.w == screenW && h.h == screenH && h.fps >= 1 && h.fps <= 30 && h.frames >= 1 && h.frames <= MAX_FRAMES;
}
// The table sound: the first frame a picture, every picture inside the file and after the table, none too big. maxSize: the largest.
inline bool tableSound(const uint8_t *t, const Header &h, uint32_t fileSize, uint32_t &maxSize) {
    maxSize = 0;
    const uint32_t dataStart = HEADER_BYTES + 8 * h.frames;
    if (fileSize < dataStart) return false;
    for (uint32_t i = 0; i < h.frames; ++i) {
        const uint32_t off = rd32(t + 8 * i), size = rd32(t + 8 * i + 4);
        if (size == 0) { if (i == 0) return false; continue; }
        if (off < dataStart || off > fileSize || size > fileSize - off || size > MAX_PICTURE) return false;
        if (size > maxSize) maxSize = size;
    }
    return true;
}
// The frame due ms after the start; -1 once the film is over
inline int32_t frameAt(uint32_t ms, const Header &h) { const uint64_t f = (uint64_t) ms * h.fps / 1000; return f < h.frames ? (int32_t) f : -1; }
inline uint32_t lengthMs(const Header &h) { return (uint32_t) (((uint64_t) h.frames * 1000 + h.fps - 1) / h.fps); }
// The picture to decode so that frame `want` shows, `last` being the picture decoded last (-1: none yet): the latest picture
// at or before `want` - pictures missed on the way are skipped, so a slow decode never falls behind the sound - or -1 when
// the one on the glass is still the right one.
inline int32_t pictureFor(int32_t want, int32_t last, const uint8_t *t) {
    if (want < 0) return -1;
    int32_t k = want;
    while (k > last && k > 0 && rd32(t + 8 * k + 4) == 0) --k;
    return k > last ? k : -1;
}
// Where two rows of pixels differ: first .. last (last < first when they are the same)
inline void rowDiff(const uint16_t *a, const uint16_t *b, int n, int &first, int &last) {
    first = 0; last = -1;
    while (first < n && a[first] == b[first]) ++first;
    if (first == n) return;
    last = n - 1;
    while (last > first && a[last] == b[last]) --last;
}
} // namespace ldrcfilm
