#!/bin/zsh
# Poll both Apple review queues and ping Malcolm's watch when either MOVES.
# Runs from a LaunchAgent so it survives sleep, wake and logout — a nohup job
# does not (see the session-drops note). Read-only: it only ever GETs.
#
# THIS FILE IS THE SOURCE. It runs from a COPY in /Users/Shared/ldrc-watch/,
# because ~/Documents is TCC-protected and a LaunchAgent cannot read a thing in
# there — it failed on every run for a whole night, logging only
# "can't open input file", which looks nothing like a permissions problem.
# Same reason the dev firmware server lives in /Users/Shared. After editing:
#   dev/sync_watchers.sh
APP=/Users/malcolmmessiter/Documents/GitHub/LDRC_V2_ALL/RXV2App
NOTIFY=/Users/malcolmmessiter/Documents/GitHub/LDRC_V2_ALL/RXV2/dev/notify.sh
STATE=$HOME/.appstoreconnect/rxv2_review_state
KEY=KLS4GZ93JB
ISS=69a6de80-5be5-47e3-e053-5b8c7c11a4d1
SUB=32bc8253-72a9-42e3-b221-e08b47859459   # 5.173 store update, submitted 2026-09-25 (5.160 went live that morning)
BUILD=b0df7402-a97e-4314-9241-e1aaf6faac8a   # TestFlight build 443 = app 5.173 (approved 2026-09-24)

# /usr/bin/python3 is an Xcode shim and refuses to run until the licence is
# agreed - and the LaunchAgent's PATH finds exactly that one. Pick the first
# python3 that actually executes (2026-09-21: this is what killed the watcher).
PY=""
for c in /Users/malcolmmessiter/.platformio/penv/bin/python3 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  [[ -x $c ]] && $c -c "pass" >/dev/null 2>&1 && { PY=$c; break; }
done
[[ -z "$PY" ]] && exit 0

T=$($PY "$APP/appstore/asc_token.py" $KEY $ISS 2>/dev/null) || exit 0
get() { curl -s -m 30 -H "Authorization: Bearer $T" "https://api.appstoreconnect.apple.com$1"; }

STORE=$(get "/v1/reviewSubmissions/$SUB" | $PY -c "
import json,sys
try: print(json.load(sys.stdin)['data']['attributes'].get('state') or '?')
except Exception: print('?')")
BETA=$(get "/v1/builds/$BUILD/betaAppReviewSubmission" | $PY -c "
import json,sys
try:
    d=json.load(sys.stdin).get('data')
    print(d['attributes'].get('betaReviewState') if d else '?')
except Exception: print('?')")

[[ "$STORE" == "?" && "$BETA" == "?" ]] && exit 0     # network wobble: say nothing
NOW="store=$STORE beta=$BETA"
WAS=$(cat $STATE 2>/dev/null)
[[ "$NOW" == "$WAS" ]] && exit 0
print -r -- "$NOW" > $STATE
[[ -z "$WAS" ]] && exit 0                              # first run just records

MSG="Apple moved: App Store $STORE, TestFlight $BETA."
[[ "$BETA" == "APPROVED" ]] && MSG="$MSG TestFlight link is LIVE: https://testflight.apple.com/join/6yzhGxae"
[[ "$STORE" == "COMPLETE" ]] && MSG="$MSG App Store submission cleared - it releases itself."
[[ "$STORE" == *REJECT* || "$BETA" == *REJECT* ]] && MSG="REJECTED. $NOW - check App Store Connect for the reason."
# -f, not -x: notify.sh is not executable and we invoke it via bash anyway.
# Testing -x meant the very first real state change recorded itself and pinged
# NOTHING (caught 2026-09-21, the morning TestFlight was approved).
if [[ -f $NOTIFY ]]; then
  bash $NOTIFY "$MSG" || echo "notify failed: $MSG"
else
  echo "notify.sh missing: $MSG"
fi
exit 0
