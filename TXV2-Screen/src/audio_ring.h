// The audio ring's two ends (screen 1.11.95): loop() writes at the head, the audio task on the other core reads at the tail.
// Until 1.11.95 a stop set head = tail from loop() - and the task, half way through advancing the tail for one DMA buffer,
// could move the tail PAST that head a moment later: its next count of what was waiting came out as the whole ring less a
// few bytes, and it played 5.9 s of whatever the ring held - the last several announcements over again, with old sound
// between them (Malcolm, 19 Oct 2026, as a stick calibration finished: "it made many announcements one after the other,
// with some background noise"). Finish is a moment when two or three sounds follow within a few milliseconds, each
// stopping the one before: the window was there every time, and one day it was hit.
// Now each end is written by ONE core only. A stop is a note from loop(): the generation goes up and the head of that
// moment is kept; the task, at the top of its next buffer, moves its own tail to that head. Host-tested with two threads
// and with the old protocol beside it (hmi/test_audio).
#pragma once
#include <cstddef>
#include <cstdint>
namespace ldrcring {
struct Ends {
    volatile size_t head = 0, tail = 0;           // head: the producer's (loop); tail: the consumer's (the audio task)
    volatile uint32_t flushGen = 0, flushAt = 0;  // the producer's note: from generation flushGen on, nothing before flushAt counts
    uint32_t seenGen = 0;                         // the consumer's: the last note it acted on
};
inline void barrier() { __sync_synchronize(); }
// ---- the producer
inline void stop(Ends &e) { e.flushAt = (uint32_t) e.head; barrier(); e.flushGen = e.flushGen + 1; barrier(); }
inline size_t used(const Ends &e, size_t ring) { return (e.head + ring - e.tail) % ring; }   // (a stop not yet acted on: a little less room for a moment, never the wrong room)
inline size_t space(const Ends &e, size_t ring) { return ring - 1 - used(e, ring); }
inline void push(Ends &e, uint8_t *buf, size_t ring, const uint8_t *src, size_t n) {   // the bytes first, the head once they are all there
    size_t h = e.head;
    for (size_t i = 0; i < n; ++i) { buf[h] = src[i]; h = (h + 1) % ring; }
    barrier(); e.head = h;
}
// ---- the consumer: at the top of a buffer, a stop is acted on; then how many bytes wait
inline size_t begin(Ends &e, size_t ring) {
    const uint32_t g = e.flushGen;
    if (g != e.seenGen) { barrier(); e.tail = e.flushAt; e.seenGen = g; }
    return (e.head + ring - e.tail) % ring;
}
inline void took(Ends &e, size_t ring, size_t n) { e.tail = (e.tail + n) % ring; }
}
