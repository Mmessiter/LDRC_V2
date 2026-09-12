#!/bin/bash
# Build the decoder/analyser on the Mac, run it over synthetic logs, check the peaks with the page's own analysis (data/bbcheck.js).
set -e
cd "$(dirname "$0")/.."
T=${TMPDIR:-/tmp}/bbcheck; mkdir -p $T
clang++ -std=c++17 -O2 -Wall -Wextra -o $T/bbcheck_test dev/bbcheck_test.cpp
python3 dev/bb_synth.py $T/rec.bbl --seconds 20 --fields rec >/dev/null
python3 dev/bb_synth.py $T/all.bbl --seconds 8 --fields all >/dev/null
python3 dev/bb_synth.py $T/two.bbl --seconds 6 --fields min --logs 2 >/dev/null
python3 dev/bb_synth.py $T/trunc.bbl --seconds 6 --fields rec --truncate --pad 4096 >/dev/null
python3 dev/bb_synth.py $T/corrupt.bbl --seconds 12 --fields rec --corrupt 6 >/dev/null
for f in rec all two trunc corrupt; do $T/bbcheck_test $T/$f.bbl > $T/$f.json 2>/dev/null; done
$T/bbcheck_test $T/two.bbl 1 > $T/two1.json 2>/dev/null
$T/bbcheck_test $T/rec.bbl 0 4096 > $T/rec4k.json 2>/dev/null
node dev/bbcheck_test.js $T
