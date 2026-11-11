#!/bin/zsh
# Host test of the receiver's hold (0.9.922, src/1Defs.h OUTPUT_FAILSAFE_MS = 3000) and of the ages of silence counted
# from it, against the REAL code: the block is cut out of 1Defs.h, compiled, and run. Then the sources are read:
# nothing that writes flash, or takes the flight controller, may still wait for a bare 2000 or 3000 ms of silence -
# written beside a hold of 1500, those would now fall inside the hold, with the model flying on its held sticks.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
SRC="$HERE/../src"
T=$(mktemp -d)
awk '/^\/\/ LINK-AGES-BEGIN/{p=1} /^\/\/ LINK-AGES-END/{p=0} p' "$SRC/1Defs.h" > "$T/link_block.h"
[[ -s "$T/link_block.h" ]] || { echo "FAILED: LINK-AGES block not found in src/1Defs.h"; exit 1; }
num() { sed -n -E "s/^constexpr uint32_t $1 *= *([0-9]+);.*/\1/p" "$SRC/1Defs.h" | head -1; }
WIFI=$(num WIFI_REENABLE_AFTER_LOST_MS); SAVE=$(num FLIGHT_SAVE_AFTER_MS)
[[ -n "$WIFI" && -n "$SAVE" ]] || { echo "FAILED: WIFI_REENABLE_AFTER_LOST_MS or FLIGHT_SAVE_AFTER_MS not found in src/1Defs.h"; exit 1; }
# The transmitter's own timeout, when its source is on this Mac: the working project first, else the public snapshot.
TXDEF=""
for f in "$HOME/Documents/GitHub/TXV1B/TransmitterCode/include/1Definitions.h" "$HERE/../../TXV2/TransmitterCode/include/1Definitions.h"; do
    [[ -f "$f" ]] && { TXDEF="$f"; break; }
done
TXFLAG=()
if [[ -n "$TXDEF" ]]; then
    RED=$(sed -n -E 's/^#define RED_LED_ON_TIME ([0-9]+).*/\1/p' "$TXDEF" | head -1)
    [[ -n "$RED" ]] || { echo "FAILED: RED_LED_ON_TIME not found in $TXDEF"; exit 1; }
    TXFLAG=(-DTX_RED_LED_ON_TIME=$RED)
fi
c++ -std=c++17 -Wall -Werror -DLINK_BLOCK="\"$T/link_block.h\"" -DWIFI_REENABLE=$WIFI -DFLIGHT_SAVE_AFTER=$SAVE $TXFLAG -o "$T/t" "$HERE/link_hold_test.cpp"
"$T/t" > "$T/out" || { cat "$T/out"; exit 1; }
sed '$d' "$T/out" | sed '$d'            # (its own last lines are said once more below, after the reading of the sources)
bad=0
# 1. The output stage and the sim's failsafe posture compare with the constant, not with a number of their own.
grep -q 'age > OUTPUT_FAILSAFE_MS' "$SRC/Output.h" && echo "PASS Output.h: the hold is OUTPUT_FAILSAFE_MS" || { echo "FAIL Output.h no longer compares the link's age with OUTPUT_FAILSAFE_MS"; bad=1; }
grep -q '(millis() - linkRef) > OUTPUT_FAILSAFE_MS' "$SRC/main.cpp" && echo "PASS main.cpp: the sim's failsafe posture waits for the same hold" || { echo "FAIL main.cpp: the sim's failsafe posture no longer waits for OUTPUT_FAILSAFE_MS"; bad=1; }
# 2. The files whose waits end in a flash write or in taking the flight controller: no bare 2000 or 3000 of silence.
for f in FlightLog.h MspFc.h main.cpp BlackboxCheck.h; do
    hits=$(grep -n -E 'rx\.lastMillis\) *(<|>|<=|>=) *(2000|3000)\b' "$SRC/$f" || true)
    if [[ -n "$hits" ]]; then echo "FAIL $f still waits for a bare 2000 or 3000 ms of silence (use LINK_QUIET_MS / LINK_DEAD_MS):"; echo "$hits"; bad=1
    else echo "PASS $f: no bare 2000 or 3000 ms of silence"; fi
done
grep -q 'fltSaveAsapActive() ? LINK_DEAD_MS : FLIGHT_SAVE_AFTER_MS' "$SRC/FlightLog.h" && echo "PASS FlightLog.h: a flight asked for at once is still not saved inside the hold" || { echo "FAIL FlightLog.h: the save 'at once' no longer waits for LINK_DEAD_MS"; bad=1; }
# 3. Each use that was moved is there (a deleted wait would pass the reading above).
want() { local n=$(grep -c "$2" "$SRC/$1" || true); [[ "$n" -ge "$3" ]] && echo "PASS $1: $2 x$n" || { echo "FAIL $1: $2 found $n times, wanted at least $3"; bad=1; }; }
want FlightLog.h LINK_DEAD_MS 4
want FlightLog.h LINK_QUIET_MS 1
want MspFc.h LINK_QUIET_MS 2
want MspFc.h LINK_DEAD_MS 1
want main.cpp LINK_QUIET_MS 1
want BlackboxCheck.h LINK_DEAD_MS 1
[[ $bad -eq 0 ]] || { echo; echo "FAILED"; exit 1; }
echo
echo "ALL PASS"
