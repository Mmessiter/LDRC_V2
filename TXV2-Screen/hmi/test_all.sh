#!/bin/sh
# Every host test of the screen's project, and the release tool's gate. One line for each; the whole story with -v.
cd "$(dirname "$0")"
bad=0
for t in test_link test_update test_wifi test_device test_pics test_flight test_theme test_ble test_cli test_quiet test_film test_audio test_crumbs; do
    out=$(./$t/run.sh 2>&1); code=$?
    if [ "$1" = "-v" ]; then echo "$out"; fi
    echo "$t: $(echo "$out" | grep -E 'checks, [0-9]+ failures' | tr '\n' ' ')"
    echo "$out" | grep -E "FAIL|error:" | head -20
    [ $code -ne 0 ] && bad=1
done
for f in ../sd/hmi/films/*.ldf; do                         # (1.11.88) each film on the card, read as the screen reads it
    out=$(./test_film/test_film "$f" 2>&1); code=$?
    echo "film $(basename "$f"): $(echo "$out" | grep -E 'checks, [0-9]+ failures' | tr '\n' ' ')"; echo "$out" | grep FAIL | head -5
    [ $code -ne 0 ] && bad=1
done
FILMPY="/Volumes/2TB SSD/ClaudeScratch/films/venv/bin/python"; [ -x "$FILMPY" ] || FILMPY=python3
for f in ../sd/hmi/films/*.ima; do                         # (1.11.93) each film's sound: the screen's decoding is ffmpeg's, bit for bit
    [ -f "$f" ] || continue
    out=$("$FILMPY" test_film/ima_test.py "$f" 2>&1); code=$?
    if echo "$out" | grep -q "No such file\|ModuleNotFound\|not found"; then echo "sound $(basename "$f"): no ffmpeg here, not checked"; continue; fi
    echo "sound $(basename "$f"): $(echo "$out" | tail -1)"; echo "$out" | grep FAIL | head -5; [ $code -ne 0 ] && bad=1
done
out=$(python3 test_film/flow_test.py 2>&1); code=$?          # film_device.h itself: the menu, pause, Back, Next, the keep-awake
echo "films flow: $(echo "$out" | tail -1)"; echo "$out" | grep FAIL | head -10; [ $code -ne 0 ] && bad=1
gate="$HOME/Documents/GitHub/TXV1B/dev/test_release_gate.py"
if [ -f "$gate" ]; then out=$(python3 "$gate" 2>&1); code=$?; echo "release gate: $(echo "$out" | tail -1)"; echo "$out" | grep FAIL; [ $code -ne 0 ] && bad=1; fi
[ $bad -eq 0 ] && echo "ALL GOOD" || echo "SOMETHING FAILED"
exit $bad
