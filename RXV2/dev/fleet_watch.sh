#!/bin/zsh
# Fleet OTA watcher. Malcolm 2026-09-14: "We now have two testing set-ups and
# five helicopters installed! ... as each one is pulled out, it'll want to be
# updated."
#
# SWEEPS the subnet, finds every LDRC board that answers, and updates any that
# is on an older build AND looks idle. Safe by construction: it will not touch
# a board with a transmitter on it, an armed model, a turning rotor, a phone
# talking to it, or a weak signal - and it wants to see that twice in a row
# before it acts.
#
#   zsh dev/fleet_watch.sh <version-name> <fs-md5> [subnet]
#   (zsh ONLY - `bash fleet_watch.sh` dies at once on ${=R} and ${(f)...};
#    2026-09-15 it died silently on every restart from 0.9.723 to 0.9.727)
#
# dev/release.sh restarts it on every release. Lived in a session scratchpad
# until 2026-09-17, where it would have vanished with the session; now here.
# Pings go through dev/notify.sh (gitignored ntfy topic) when that exists.
set -u
WANT=$1; FSMD5=$2; NET=${3:-192.168.1}
SRV=http://192.168.1.193:8000
HERE=$(cd "$(dirname "$0")" && pwd)
LOG=$HERE/fleet_watch.log
log(){ echo "$(date +%H:%M:%S) $*" >> $LOG }
if [[ -f $HERE/notify.sh ]]; then source $HERE/notify.sh; else ping_watch(){ log "(no dev/notify.sh - would ping: $1)" }; fi

typeset -A IDLE                      # per-board consecutive idle observations
typeset -A PREVPK                    # per-board last packet count

probe(){ curl -s -m 2 http://$1/api/state.json 2>/dev/null }

log "fleet watch started: want $WANT on $NET.0/24"
while true; do
  # --- discover: probe the whole subnet in parallel, keep the LDRC boards ---
  FOUND=$(seq 2 254 | xargs -P 48 -I{} sh -c "curl -s -m 2 -o /dev/null -w '%{http_code} $NET.{}\n' http://$NET.{}/api/state.json 2>/dev/null" \
          | awk '$1=="200"{print $2}')
  SEEN=""; CURRENT=""
  for IP in ${(f)FOUND}; do
    R=$(probe $IP | python3 -c "
import json,sys
try:
    s=json.load(sys.stdin); i=s['info']; rf=s.get('rf',{}); m=s.get('msp',{})
    print(i.get('name','?').replace(' ','_'), i['fw_version'], i.get('rssi',-99), rf.get('packets',0),
          int(bool(rf.get('armed'))), rf.get('head_speed',0), int(bool(m.get('active'))),
          m.get('connections',0), int(bool((s.get('ble') or {}).get('client'))), int(bool(s.get('dongle'))))
except Exception: pass" 2>/dev/null)
    [[ -z "$R" ]] && continue
    set -- ${=R}; NAME=$1; FW=$2; RSSI=$3; PK=$4; ARMED=$5; HS=$6; MACT=$7; MCON=$8; BLEC=$9; DON=${10}
    [[ "$FW" != RXV2-* ]] && continue                     # not one of ours
    SEEN="$SEEN $NAME"
    [[ "$FW" == "$WANT" ]] && { IDLE[$IP]=0; CURRENT="$CURRENT $NAME"; continue }

    # A dongle has no radio, so packet count and RSSI mean nothing there.
    if (( DON == 1 )); then
      QUIET=$(( ARMED == 0 && MACT == 0 && MCON == 0 && BLEC == 0 ))
    else
      SAME=$(( PK == ${PREVPK[$IP]:--1} ))
      QUIET=$(( SAME == 1 && ARMED == 0 && HS == 0 && MACT == 0 && MCON == 0 && BLEC == 0 && RSSI > -70 ))
    fi
    PREVPK[$IP]=$PK
    if (( QUIET )); then IDLE[$IP]=$(( ${IDLE[$IP]:-0} + 1 )); else IDLE[$IP]=0; fi
    log "$NAME @ $IP fw=$FW rssi=$RSSI armed=$ARMED hs=$HS msp=$MACT/$MCON ble=$BLEC dongle=$DON idle=${IDLE[$IP]}"

    if (( ${IDLE[$IP]} >= 2 )); then
      log "$NAME @ $IP: idle twice - installing $WANT"
      OUT=$(curl -s -m 900 -X POST http://$IP/api/firmware/install \
              --data-urlencode url=$SRV/$WANT.bin \
              --data-urlencode fs_url=$SRV/littlefs-$WANT.bin \
              --data-urlencode fs_md5=$FSMD5)
      log "$NAME install reply: ${OUT:0:70}"
      IDLE[$IP]=0
      sleep 45
      for t in 1 2 3 4 5 6; do
        V=$(probe $IP | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['fw_version'])" 2>/dev/null)
        [[ -n "$V" ]] && break; sleep 15
      done
      if [[ "$V" == "$WANT" ]]; then
        log "$NAME: SUCCESS on $WANT"
        ping_watch "$NAME updated to ${WANT#RXV2-} automatically."
      else
        log "$NAME: FAILED (reads ${V:-no answer})"
        ping_watch "$NAME did NOT take ${WANT#RXV2-} (reads ${V:-no answer}) - worth a look."
      fi
    fi
  done
  # one line a sweep, so a quiet log still proves the watcher is alive
  NOW=$(date +%s)
  if (( NOW - ${LASTSUM:-0} >= 600 )); then
    LASTSUM=$NOW
    log "sweep: boards seen:${SEEN:- none}  already current:${CURRENT:- none}"
  fi
  sleep 30
done
