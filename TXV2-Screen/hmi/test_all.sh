#!/bin/sh
# Every host test of the screen's project, and the release tool's gate. One line for each; the whole story with -v.
cd "$(dirname "$0")"
bad=0
for t in test_link test_update test_wifi test_device test_pics test_flight test_theme; do
    out=$(./$t/run.sh 2>&1); code=$?
    if [ "$1" = "-v" ]; then echo "$out"; fi
    echo "$t: $(echo "$out" | grep -E 'checks, [0-9]+ failures' | tr '\n' ' ')"
    echo "$out" | grep -E "FAIL|error:" | head -20
    [ $code -ne 0 ] && bad=1
done
gate="$HOME/Documents/GitHub/TXV1B/dev/test_release_gate.py"
if [ -f "$gate" ]; then out=$(python3 "$gate" 2>&1); code=$?; echo "release gate: $(echo "$out" | tail -1)"; echo "$out" | grep FAIL; [ $code -ne 0 ] && bad=1; fi
[ $bad -eq 0 ] && echo "ALL GOOD" || echo "SOMETHING FAILED"
exit $bad
