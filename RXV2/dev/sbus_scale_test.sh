#!/bin/zsh
# Host test of the SBUS scale (0.9.898, 17 Oct 2026): the 11-bit value SBUS, CRSF and FBUS send is the one a flight
# controller turns into microseconds as us = value * 5/8 + 880 (172 = 988, 992 = 1500, 1811 = 2012). The block between
# SBUS-CRSF-SCALE-BEGIN/END in src/Output.h is cut out and compiled with stubs. The simulator interface's SBUS reader
# (src/RcInput.h) must keep the same scale, so an RXV2's SBUS into another RXV2 reads as a flight controller would.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d)
awk '/SBUS-CRSF-SCALE-BEGIN/{p=1} p{print} /SBUS-CRSF-SCALE-END/{p=0}' "$HERE/../src/Output.h" > "$T/scale_block.h"
[[ -s "$T/scale_block.h" ]] || { echo "FAILED: scale block not found in src/Output.h"; exit 1; }
grep -q '((int32_t)raw - 992) \* 5 / 8 + 1500' "$HERE/../src/RcInput.h" || { echo "FAILED: the simulator interface's SBUS reader no longer uses the standard scale (RcInput.h)"; exit 1; }
[[ $(grep -c 'rc11bit(channelMicros\[c\])' "$HERE/../src/Output.h") -eq 3 ]] || { echo "FAILED: SBUS, CRSF and FBUS should all take their value from rc11bit (3 uses)"; exit 1; }
grep -q '2047L' "$HERE/../src/Output.h" && { echo "FAILED: the V1 mapping (0..2047) is still in src/Output.h"; exit 1; }
c++ -std=c++17 -Wall -DSCALE_BLOCK="\"$T/scale_block.h\"" -o "$T/t" "$HERE/sbus_scale_test.cpp"
"$T/t"
