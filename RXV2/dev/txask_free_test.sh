#!/bin/zsh
# Host test of the rule that lets a silent phone app go when a transmitter's screen asks for Bluetooth (0.9.921,
# src/BleConfig.h txAskFreesSilentApp) against the REAL code: the block is cut out of BleConfig.h, compiled, and run.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d)
awk '/^\/\/ TXASK-FREE-BEGIN/{p=1} /^\/\/ TXASK-FREE-END/{p=0} p' "$HERE/../src/BleConfig.h" > "$T/txask_block.h"
[[ -s "$T/txask_block.h" ]] || { echo "FAILED: TXASK-FREE block not found in src/BleConfig.h"; exit 1; }
c++ -std=c++17 -Wall -Werror -DTXASK_BLOCK="\"$T/txask_block.h\"" -o "$T/t" "$HERE/txask_free_test.cpp"
"$T/t"
