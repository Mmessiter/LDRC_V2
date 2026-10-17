// The LDRC film's sums (screen 1.11.85), apart from the card, the decoder and the panel so the Mac can test them
// (hmi/test_film). The film: "LDRCFILM", then version 1, width, height, frames a second (u16 each, little-endian) and the
// number of frames (u32); then each frame's offset in the file and size (u32 each) - size 0: the same picture as the
// frame before, nothing to decode; then the pictures, baseline JPEG. Version 2 (1.11.87): each picture is only the
// rectangle that changed since the frame before - x, y, width, height (u16 each), then its JPEG, drawn there - so a
// moving finger is a small picture, quick to decode, and a still page costs nothing. Written by TXV1B dev/video (LDRC_TARGET=screen),
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
    return (h.version == 1 || h.version == 2) && h.w == screenW && h.h == screenH && h.fps >= 1 && h.fps <= 30 && h.frames >= 1 && h.frames <= MAX_FRAMES;
}
// The table sound: the first frame a picture, every picture inside the file and after the table, none too big. maxSize: the largest.
inline bool tableSound(const uint8_t *t, const Header &h, uint32_t fileSize, uint32_t &maxSize) {
    maxSize = 0;
    const uint32_t dataStart = HEADER_BYTES + 8 * h.frames;
    if (fileSize < dataStart) return false;
    for (uint32_t i = 0; i < h.frames; ++i) {
        const uint32_t off = rd32(t + 8 * i), size = rd32(t + 8 * i + 4);
        if (size == 0) { if (i == 0) return false; continue; }
        if (off < dataStart || off > fileSize || size > fileSize - off || size > MAX_PICTURE || (h.version >= 2 && size <= 8)) return false;
        if (size > maxSize) maxSize = size;
    }
    return true;
}
// Where a picture goes, and where its JPEG starts in it: version 1 the whole screen; version 2 its rectangle (inside the
// screen, at least 8 x 8). False: not a picture this player can place.
inline bool pictureAt(const uint8_t *blob, uint32_t size, const Header &h, uint16_t &x, uint16_t &y, uint16_t &w, uint16_t &hh, uint32_t &jpegOff) {
    if (h.version < 2) { x = 0; y = 0; w = h.w; hh = h.h; jpegOff = 0; return size > 0; }
    if (size <= 8) return false;
    x = rd16(blob); y = rd16(blob + 2); w = rd16(blob + 4); hh = rd16(blob + 6); jpegOff = 8;
    return w >= 8 && hh >= 8 && x + w <= h.w && y + hh <= h.h;
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
// Which film a help page offers (1.11.86). /hmi/films/films.txt holds lines "<help name>=<film name>" (a # starts a
// note); a help page named in it offers that film, any other offers the film of its own name, if there is one. Malcolm
// could not reach Easy tuning's help without the helicopter on (the page needs the model), so the Rotorflight menu's help
// (RFLIGHT), which opens without one, offers Easy tuning's film too. Names are compared without regard to case; the
// answer is upper case, at most 12 characters, letters, digits, '_' and '-' only (it becomes a path).
inline void filmFor(const char *list, const char *topic, char *out, int outSize) {
    auto up = [](char c) { return (char) (c >= 'a' && c <= 'z' ? c - 32 : c); };
    auto ok = [](char c) { return (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_' || c == '-'; };
    int n = 0;
    for (const char *s = topic; *s && n < outSize - 1 && n < 12; ++s) { const char c = up(*s); if (!ok(c)) break; out[n++] = c; }
    out[n] = 0;
    if (!list || !n) return;
    const char *line = list;
    while (*line) {
        const char *end = line; while (*end && *end != '\n') ++end;
        const char *p = line; while (p < end && (*p == ' ' || *p == '\t')) ++p;
        if (p < end && *p != '#') {
            const char *eq = p; while (eq < end && *eq != '=') ++eq;
            if (eq < end) {
                const char *a = p, *ae = eq; while (ae > a && (ae[-1] == ' ' || ae[-1] == '\t' || ae[-1] == '\r')) --ae;
                bool same = (int) (ae - a) == n;
                for (int i = 0; same && i < n; ++i) if (up(a[i]) != out[i]) same = false;
                if (same) {
                    const char *b = eq + 1; while (b < end && (*b == ' ' || *b == '\t')) ++b;
                    char name[16]; int m = 0;
                    while (b < end && m < 12 && m < outSize - 1) { const char c = up(*b); if (!ok(c)) break; name[m++] = c; ++b; }
                    if (m > 0) { memcpy(out, name, (size_t) m); out[m] = 0; }
                    return;
                }
            }
        }
        line = *end ? end + 1 : end;
    }
}
// The films menu (1.11.87). films.txt also holds lines "<film name>: <title>", the menu's entries in their order (a film
// whose .ldf is not on the card is left out by the caller). Names as filmFor's; a title is up to 40 printable characters.
struct Entry { char name[13]; char title[41]; };
inline int parseFilms(const char *list, Entry *out, int max) {
    auto up = [](char c) { return (char) (c >= 'a' && c <= 'z' ? c - 32 : c); };
    auto ok = [](char c) { return (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_' || c == '-'; };
    int n = 0;
    if (!list) return 0;
    const char *line = list;
    while (*line && n < max) {
        const char *end = line; while (*end && *end != '\n') ++end;
        const char *p = line; while (p < end && (*p == ' ' || *p == '\t')) ++p;
        if (p < end && *p != '#') {
            Entry e; int m = 0;
            while (p < end && m < 12 && ok(up(*p))) e.name[m++] = up(*p++);
            e.name[m] = 0;
            while (p < end && (*p == ' ' || *p == '\t')) ++p;
            if (m > 0 && p < end && *p == ':') {
                ++p; while (p < end && (*p == ' ' || *p == '\t')) ++p;
                const char *te = end; while (te > p && (te[-1] == ' ' || te[-1] == '\t' || te[-1] == '\r')) --te;
                int k = 0; bool good = te > p;
                for (const char *q = p; q < te && good; ++q) { if (*q < 32 || *q > 126 || *q == '"') good = false; else if (k < 40) e.title[k++] = *q; }
                e.title[k] = 0;
                bool dup = false; for (int i = 0; i < n; ++i) if (!strcmp(out[i].name, e.name)) dup = true;
                if (good && k > 0 && !dup) out[n++] = e;
            }
        }
        line = *end ? end + 1 : end;
    }
    return n;
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
