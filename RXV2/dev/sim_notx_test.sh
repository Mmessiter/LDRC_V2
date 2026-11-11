#!/bin/zsh
# Host test of 0.9.924 (11 Nov 2026): in simulator mode the saved failsafe positions are given from the start, not only
# after a transmitter has been heard and lost (Malcolm, Test1: an update restarted the receiver with the transmitter off
# and "suddenly and unexpectedly it turned on the sim motor"). The blocks SIM-NOTX and B29-FAILSAFE-MASK of src/1Defs.h
# are cut out, compiled and run (dev/sim_notx_test.cpp); then main.cpp is read: the simulator part uses them, and the
# part that feeds a REAL flight controller is untouched.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
SRC="$HERE/../src"
T=$(mktemp -d)
awk '/^\/\/ SIM-NOTX-BEGIN/{p=1} p{print} /^\/\/ SIM-NOTX-END/{p=0}' "$SRC/1Defs.h" > "$T/sim_block.h"
[[ -s "$T/sim_block.h" ]] || { echo "FAILED: SIM-NOTX block not found in src/1Defs.h"; exit 1; }
awk '/inline bool failsafeDrive\(\) \{/{p=1} p{print} /^}/{if(p)exit}' "$SRC/1Defs.h" > "$T/fs_block.h"
[[ -s "$T/fs_block.h" ]] || { echo "FAILED: failsafeDrive() not found in src/1Defs.h"; exit 1; }
c++ -std=c++17 -Wall -Werror -fsanitize=address,undefined -DSIM_BLOCK="\"$T/sim_block.h\"" -DFS_BLOCK="\"$T/fs_block.h\"" -o "$T/t" "$HERE/sim_notx_test.cpp"
"$T/t" > "$T/out" || { cat "$T/out"; exit 1; }
sed '$d' "$T/out" | sed '$d'
bad=0
grep -q 'const bool lost = simGivenFailsafe(everHeard, (uint32_t)(millis() - linkRef), OUTPUT_FAILSAFE_MS);' "$SRC/main.cpp" && echo "PASS main.cpp: the simulator part goes by simGivenFailsafe" || { echo "FAIL main.cpp: the simulator part no longer uses simGivenFailsafe"; bad=1; }
grep -q 'const uint16_t offUs = simMotorOffUs(everHeard, driven, simMotorChannel, simMotorInverted);' "$SRC/main.cpp" && echo "PASS main.cpp: ... and holds the motor channel off when nothing is saved" || { echo "FAIL main.cpp: simMotorOffUs is not used"; bad=1; }
# Both uses sit inside `if (simEnabled) {` - a real model's output (Output.h) must never be given the saved positions at power-up.
n=$(awk '/^    if \(simEnabled\) \{/{p=1} /^    \} else \{/{p=0} p' "$SRC/main.cpp" | grep -c -E 'simGivenFailsafe|simMotorOffUs' || true)
[[ "$n" -eq 2 ]] && echo "PASS main.cpp: both only inside the simulator part of loop()" || { echo "FAIL main.cpp: simGivenFailsafe/simMotorOffUs found $n times inside the simulator part, wanted 2"; bad=1; }
m=$(grep -c -E 'simGivenFailsafe|simMotorOffUs' "$SRC/Output.h" || true)
[[ "$m" -eq 0 ]] && echo "PASS Output.h: the real model's output does not use them (never the saved positions at power-up)" || { echo "FAIL Output.h uses the simulator's rule"; bad=1; }
grep -q 'everConnected' "$SRC/Output.h" && echo "PASS Output.h: its everConnected gate is still there" || { echo "FAIL Output.h: the everConnected gate is gone"; bad=1; }
[[ $bad -eq 0 ]] || { echo; echo "FAILED"; exit 1; }
echo
echo "ALL PASS"
