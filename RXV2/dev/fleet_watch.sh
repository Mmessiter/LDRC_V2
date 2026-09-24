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

typeset -A IDLE                      # per-board consecutive idle observations (negative = backing off after a failure)
typeset -A FAILS                     # per-board consecutive failed installs
typeset -A PREVPK                    # per-board last packet count

probe(){ curl -s -m 2 http://$1/api/state.json 2>/dev/null }

vernum() {   # RXV2-0.9.820-anything -> 000009820 as a plain integer; 0 if it is not a version
  local v; v=$(print -r -- "$1" | sed -nE 's/^RXV2-([0-9]+)\.([0-9]+)\.([0-9]+).*/\1 \2 \3/p')
  [[ -z "$v" ]] && { print 0; return; }
  set -- ${=v}; print $(( $1 * 1000000 + $2 * 1000 + $3 ))
}

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
          m.get('connections',0), int(bool((s.get('ble') or {}).get('client'))), int(bool(s.get('dongle'))),
          (s.get('protocol') or {}).get('thr_ch',0), (s.get('fcinfo') or {}).get('throttle_ch',0),
          int(bool((s.get('protocol') or {}).get('fc_telem'))),
          int(not (0 <= rf.get('last_pkt_ms', -1) < 3000)))
except Exception: pass" 2>/dev/null)
    [[ -z "$R" ]] && continue
    set -- ${=R}; NAME=$1; FW=$2; RSSI=$3; PK=$4; ARMED=$5; HS=$6; MACT=$7; MCON=$8; BLEC=$9; DON=${10}
    THR=${11:-0}; FCTHR=${12:-0}; FCT=${13:-0}; TXOFF=${14:-0}
    [[ "$FW" != RXV2-* ]] && continue                     # not one of ours
    SEEN="$SEEN $NAME"
    [[ "$FW" == "$WANT" ]] && { IDLE[$IP]=0; CURRENT="$CURRENT $NAME"; continue }
    # NEVER DOWNGRADE (2026-09-22). During a release the OLD watcher is still
    # running while release.sh builds the apps, and it saw a board already on
    # the new version as "wrong" and put the old one back. A board ahead of us
    # is someone else's business - most likely the release now in progress.
    if (( $(vernum "$FW") > $(vernum "$WANT") )); then
      log "$NAME @ $IP is on $FW, AHEAD of $WANT - leaving it alone"
      IDLE[$IP]=0; continue
    fi

    # THROTTLE HOLD ON THE RIGHT CHANNEL, at first sight (2026-09-24).
    # Firmware before 0.9.834 holds the thr_ch setting (default 3) low until a
    # transmitter is heard - on a Rotorflight heli that is the COLLECTIVE,
    # parked past full negative (Black Thunder 2's swash hit its stops), and
    # every stall of an install made it jump. Point it at the FC's own
    # throttle channel at once: transmitter off, disarmed, rotor still only.
    # fc_telem=1 rides along - those builds read a missing box as "off".
    if (( DON == 0 && FCT == 1 && FCTHR >= 1 && FCTHR <= 16 && THR != FCTHR && ARMED == 0 && HS == 0 && TXOFF == 1 )); then
      OUTT=$(curl -s -m 10 -X POST http://$IP/protocol --data-urlencode thr_ch=$FCTHR --data-urlencode fc_telem=1)
      log "$NAME @ $IP: throttle hold moved ch$THR -> ch$FCTHR (the FC's throttle channel): ${OUTT:0:60}"
    fi

    # A dongle has no radio, so the PACKET COUNT means nothing there - but
    # RSSI certainly does: it downloads the images over the same WiFi. Without
    # this it retried at -83 dBm over and over, rebooting the board each time
    # (DongleSim, 2026-09-18). Same -70 floor as a receiver.
    if (( DON == 1 )); then
      QUIET=$(( ARMED == 0 && MACT == 0 && MCON == 0 && BLEC == 0 && RSSI > -70 ))
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
              --data-urlencode fs_md5=$FSMD5 \
              --data-urlencode name=$WANT)          # the update record's target: never leave it to guess
      log "$NAME install reply: ${OUT:0:70}"
      IDLE[$IP]=0
      sleep 45
      for t in 1 2 3 4 5 6; do
        V=$(probe $IP | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['fw_version'])" 2>/dev/null)
        [[ -n "$V" ]] && break; sleep 15
      done
      if [[ "$V" == "$WANT" ]]; then
        FAILS[$IP]=0
        log "$NAME: SUCCESS on $WANT"
        ping_watch "$NAME updated to ${WANT#RXV2-} automatically."
      else
        log "$NAME: FAILED (reads ${V:-no answer})"
        # Back off after a failure: retrying at once just reboots the board on
        # a loop. Each failure doubles the wait, to a ceiling of ~16 sweeps.
        FAILS[$IP]=$(( ${FAILS[$IP]:-0} + 1 ))
        local_backoff=$(( 1 << ${FAILS[$IP]} )); (( local_backoff > 16 )) && local_backoff=16
        IDLE[$IP]=$(( -local_backoff ))
        log "$NAME: backing off $local_backoff sweeps (failure ${FAILS[$IP]})"
        (( ${FAILS[$IP]} == 1 )) && ping_watch "$NAME did NOT take ${WANT#RXV2-} (reads ${V:-no answer}) - signal was ${RSSI} dBm. Move it nearer the router."
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
