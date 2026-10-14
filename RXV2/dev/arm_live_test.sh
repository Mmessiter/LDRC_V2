#!/bin/zsh
# Host test of 0.9.886 (14 Oct 2026): MSP_RC answered by the receiver itself while the model is armed, on the flight
# controller's own scale. The block between ARM-LIVE-BEGIN/END in src/1Defs.h is cut out, compiled and run against
# Rotorflight's decode and Output.h's encode, both copied verbatim into dev/arm_live_test.cpp.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d)
awk '/ARM-LIVE-BEGIN/{p=1} p{print} /ARM-LIVE-END/{p=0}' "$HERE/../src/1Defs.h" > "$T/arm_block.h"
[[ -s "$T/arm_block.h" ]] || { echo "FAILED: arm-live block not found in src/1Defs.h"; exit 1; }
c++ -std=c++17 -Wall -DARM_BLOCK="\"$T/arm_block.h\"" -o "$T/t" "$HERE/arm_live_test.cpp"
"$T/t"
