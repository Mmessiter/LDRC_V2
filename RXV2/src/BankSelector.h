// The flight controller's bank and rates selector lines, read off the receiver's copy of its adjustment lines (0.9.904).
// Pure (no Arduino): dev/bank_selector_test.sh compiles it on the Mac.
//
// A Rotorflight adjustment line (MSP 52, 14 bytes): function, enable channel, enable range lo, hi, adjustment channel,
// range 1 lo, hi, range 2 lo, hi, min (2 bytes), max (2 bytes), step. Function 2 is the PID profile (the bank) selector,
// 1 the rates profile selector. Rotorflight's own form is ONE line with step 0 and min..max over range 1's travel: the
// switch has max - min + 1 positions. The old form (the pages' before 9 Oct 2026, applied once per power-up) is one line
// per position, each a fixed value (min == max): the positions are the lines. Anything else is not a selector.
#pragma once
#include <stdint.h>

// How many positions the selector line for function fn has in a set of lines; 0 = no such line, or not a selector.
inline uint8_t bankSelectorZones(const uint8_t *adj, int lines, uint8_t fn) {
    int fixed = 0;
    for (int i = 0; i < lines; ++i) {
        const uint8_t *l = adj + i * 14;
        if (l[0] != fn || l[13] != 0) continue;                              // (a step adjustment nudges a setting: not a selector)
        const unsigned mn = l[9] | (l[10] << 8), mx = l[11] | (l[12] << 8);
        if (mn == mx) { ++fixed; continue; }                                 // the old form: count the lines
        if (mx <= mn) return 0;
        const unsigned k = mx - mn + 1;
        return (uint8_t)(k > 6 ? 6 : k);
    }
    return fixed >= 2 ? (uint8_t)(fixed > 6 ? 6 : fixed) : 0;
}
