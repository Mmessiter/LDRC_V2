#!/bin/bash
# Fetch a day's log from the Teensy's card through the screen's file link, and print the lines that matter
# (B172 "Front page by itself", B173 "Started ...", Connected/Disconnected, model matched). Needs the transmitter on
# the WiFi with its workshop door OPEN (the TX button). Door-only POSTs carry X-LDRC: 1. Nothing is tapped.
#   teensy_log.sh <last byte of the IP> [DD-MM-YY]     (default: today)
ip=${1:?ip last byte}; day=${2:-$(date +%d-%m-%y)}
base="http://192.168.1.$ip"; remote="/log/$day.LOG"; local="/teensy/fetched/$day.LOG"
out="$(dirname "$0")/teensylog_${ip}_$day.txt"
say() { echo "$(date +%H:%M:%S) $*"; }
st=$(curl -s -m 4 "$base/status" | LC_ALL=C tr -cd '\11\12\15\40-\176')
[ -z "$st" ] && { say "no answer from .$ip"; exit 1; }
door=$(echo "$st" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('door'), d.get('page'), d.get('fw'))" 2>/dev/null)
say "status: door/page/fw = $door"
r=$(curl -s -m 6 -X POST -H "X-LDRC: 1" "$base/teensy/get?remote=$remote&local=$local")
say "asked: $r"
echo "$r" | grep -qi "door\|closed\|403" && { say "the door is shut: press the TX button, then run again"; exit 2; }
for i in $(seq 1 60); do
    s=$(curl -s -m 4 "$base/teensy/status" | LC_ALL=C tr -cd '\11\12\15\40-\176')
    fin=$(echo "$s" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print('F' if d.get('finished') else 'X' if d.get('failed') else 'R', d.get('stage'), d.get('result'), d.get('done'), d.get('size'))" 2>/dev/null)
    case "$fin" in F*) say "fetched: $fin"; break;; X*) say "FAILED: $fin"; exit 3;; esac
    sleep 1
done
case "$fin" in F*) ;; *) say "the job did not run in 60 s (the Teensy refuses the link while a model is connected): CANCELLED, so it cannot run later and throw the transmitter to the front page"; curl -s -m 5 -X POST -H "X-LDRC: 1" "$base/teensy/cancel"; echo; exit 4;; esac
curl -s -m 20 "$base/file?path=$local" > "$out"
say "$(wc -c < "$out") bytes -> $out"
echo "----- lines that matter -----"
grep -n -i "front page\|started\|watchdog\|fault\|reset\|connected\|matched\|found\|bank\|B172\|B173\|Time since boot\|switched\|power" "$out" | head -80
