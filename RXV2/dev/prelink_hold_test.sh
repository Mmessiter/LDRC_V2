#!/bin/zsh
# Host test of the receiver's pre-link safety hold (src/Output.h,
# preLinkHold/applyPreLinkHolds) against the REAL code: the block is cut
# out of Output.h, compiled with stubs, and run. Release gate since 0.9.834.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d)
awk '/^constexpr uint16_t CH_FLOOR_US/{p=1} /^inline void sbusTick\(\)/{p=0} p' "$HERE/../src/Output.h" > "$T/hold_block.h"
[[ -s "$T/hold_block.h" ]] || { echo "FAILED: hold block not found in src/Output.h"; exit 1; }
c++ -std=c++17 -Wall -DHOLD_BLOCK="\"$T/hold_block.h\"" -o "$T/t" "$HERE/prelink_hold_test.cpp"
"$T/t"
