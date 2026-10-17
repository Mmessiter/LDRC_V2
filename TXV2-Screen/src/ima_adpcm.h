// IMA ADPCM as WAV files hold it (format 0x11), mono (screen 1.11.93): a film's voice in a quarter of the bytes. The
// animations' sound was 16-bit samples, 224 MB of the 509 MB that took Malcolm's transmitter 1 h 50 min to fetch (17 Oct).
// A block: its first sample (int16), the step's index (u8) and a spare byte, then two samples a byte, the low nibble first.
// Each step as ffmpeg's encoder (the film kit's) reckons it, (2d + 1) x step / 8 - the reference's four shifts round a little
// lower, and the voice would wander from what was meant - and so as ffmpeg decodes it: the Mac checks it bit for bit (hmi/test_film).
#pragma once
#include <stdint.h>
#include <stddef.h>

namespace ldrcaudio {
static const int16_t IMA_STEP[89] = {
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
    130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166,
    1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845,
    8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767 };
static const int8_t IMA_INDEX[16] = { -1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8 };
// The samples in a block of `align` bytes (mono): the head's one, then two a byte
inline uint32_t imaSamples(uint32_t align) { return align > 4 ? (align - 4) * 2 + 1 : 0; }
// A start part way in (Play after a pause, the slider): the block that holds the moment ms - its place in the samples' bytes -
// and how many of its samples come before that moment
inline void imaFrom(uint32_t ms, uint32_t rate, uint32_t align, uint64_t &bytes, uint32_t &skip) {
    const uint64_t at = (uint64_t) ms * rate / 1000, per = imaSamples(align), block = per ? at / per : 0;
    bytes = block * align; skip = (uint32_t) (at - block * per);
}
struct Ima {
    int32_t pred = 0, index = 0;
    // A block's head: its first sample, and where the steps start. False: not a head (its step out of the table)
    bool head(const uint8_t *b, int16_t &first) {
        if (b[2] > 88) return false;
        pred = (int16_t) (b[0] | (b[1] << 8)); index = b[2];
        first = (int16_t) pred; return true;
    }
    int16_t nibble(uint8_t n) {
        const int32_t diff = ((2 * (n & 7) + 1) * IMA_STEP[index]) >> 3;
        pred += (n & 8) ? -diff : diff;
        if (pred > 32767) pred = 32767; else if (pred < -32768) pred = -32768;
        index += IMA_INDEX[n & 15]; if (index < 0) index = 0; else if (index > 88) index = 88;
        return (int16_t) pred;
    }
    // n bytes of a block after its head: 2n samples
    void body(const uint8_t *b, size_t n, int16_t *out) { for (size_t i = 0; i < n; ++i) { out[2 * i] = nibble(b[i] & 15); out[2 * i + 1] = nibble(b[i] >> 4); } }
};
} // namespace ldrcaudio
