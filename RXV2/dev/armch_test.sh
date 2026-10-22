#!/bin/zsh
# Host test of 0.9.905 (22 Oct 2026): the arm switch's channel read from Rotorflight's mode ranges (MSP 34), as the
# command line now asks for it itself when the background learner has not found it yet (Mehul's RAW 420: "The command line
# did not open ... (arming channel 0 low)"). The block between ARMCH-BEGIN/END in src/MspFc.h is cut out, compiled and run
# against mode tables written as Rotorflight's 'aux' lines say them (dev/armch_test.cpp).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d)
awk '/ARMCH-BEGIN/{p=1} p{print} /ARMCH-END/{p=0}' "$HERE/../src/MspFc.h" > "$T/armch_block.h"
[[ -s "$T/armch_block.h" ]] || { echo "FAILED: armch block not found in src/MspFc.h"; exit 1; }
c++ -std=c++17 -Wall -fsanitize=address,undefined -DARMCH_BLOCK="\"$T/armch_block.h\"" -o "$T/t" "$HERE/armch_test.cpp"
"$T/t"
