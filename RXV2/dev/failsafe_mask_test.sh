#!/bin/zsh
# Host test of B29 (13 Oct 2026): the failsafe ticks. The transmitter's Failsafe page sends
# 16 flags with parameter 1; only the ticked channels move on signal loss, the rest hold.
# The block between B29-FAILSAFE-MASK-BEGIN/END in src/1Defs.h is cut out, compiled with
# stubs and run against V1's own MakeTwobytes (TX) and RebuildFlags (RX), copied verbatim.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d)
awk '/B29-FAILSAFE-MASK-BEGIN/{p=1} p{print} /B29-FAILSAFE-MASK-END/{p=0}' "$HERE/../src/1Defs.h" > "$T/fs_block.h"
[[ -s "$T/fs_block.h" ]] || { echo "FAILED: failsafe block not found in src/1Defs.h"; exit 1; }
c++ -std=c++17 -Wall -DFS_BLOCK="\"$T/fs_block.h\"" -o "$T/t" "$HERE/failsafe_mask_test.cpp"
"$T/t"
