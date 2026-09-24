#!/bin/bash
# One-command RXV2 release. Malcolm 2026-09-17, after fourteen releases run
# by hand in a day: "By all means do it now!"
#
#   dev/release.sh <x.y.z-slug> "<release note>" [options]
#
#     --fw-only              firmware changed, pages did not: no asset bump,
#                            no app builds (receivers skip the fs flash since
#                            the image is byte-identical)
#     --android-note "..."   short note for the APK manifest (default: the
#                            first sentence of the release note)
#     --no-install           build the iOS app but do not install it
#     --trailer "..."        commit-message trailer (Claude's attribution
#                            lines); absent = a human release, no trailer
#     --withdraw <x.y.z-slug>  pull a bad release off both trees and re-publish
#     --install-ios          just install the last iOS build to both devices
#
# What a full release does, in order, stopping hard at the first failure:
#   1 bump FW_VERSION          6 build fw + fs, check the fs image is whole
#   2 prepend release notes    7 copy images to both release trees
#   3 bump page asset versions 8 Android: bump, build, publish (syncs webroots)
#   4 rebuild the search index 9 stage + publish to messiter.com, verify live
#   5 run every publish gate  10 iOS: bump, build, install to both devices
#                            11 restart the fleet watcher
#                            12 commit + push        13 ping the watch
#
# Two trees, deliberately: NewWebSite/public_html/rxv2/release/vX.Y.Z is what
# stage_website.py reads (it also rebuilds version dirs from dev/RXV2-*.bin -
# which is why --withdraw must delete that .bin), and
# /Users/Shared/rxv2-firmware-server/ is the LaunchAgent the fleet watcher
# fetches from, with a ROOT-level <ver>.bin and littlefs-<ver>.bin twin.
#
# 2026-09-17, by hand, the firmware once went to the wrong tree and a full
# LittleFS shipped a partial image with app.js as ZERO bytes - both are gates
# here (stage_website warns on a missing fs; check_fs_image refuses).
# No pipefail: every `... | grep -q` here would otherwise fail on the SIGPIPE
# grep sends upstream when it quits early (the first run stopped on a firmware
# that DID carry its version). Every command that matters has its own || die.
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"          # .../RXV2/dev
RXV2="$(dirname "$HERE")"
ROOT="$(dirname "$RXV2")"
APPS="$ROOT/RXV2App"
ANDROID="$APPS/android/RXV2App"
SHARED=/Users/Shared/rxv2-firmware-server
RELEASE="$RXV2/NewWebSite/public_html/rxv2/release"
DD_IOS="/Volumes/2TB SSD/claude-build/dd_ios"
IOS_APP="$DD_IOS/Build/Products/Debug-iphoneos/RXV2App.app"
IPHONE=231C09B7-A959-5004-912A-87E10C57FA46
IPAD=9D04D980-E5A6-51B0-924E-CD303DD85A41
MANIFEST_URL=https://messiter.com/rxv2/release/manifest.json

BOLD=$'\e[1m'; DIM=$'\e[2m'; RED=$'\e[31m'; GRN=$'\e[32m'; YEL=$'\e[33m'; OFF=$'\e[0m'
step() { echo; echo "${BOLD}── $*${OFF}"; }
ok()   { echo "   ${GRN}✓${OFF} $*"; }
warn() { echo "   ${YEL}! $*${OFF}"; WARNINGS+="   - $*"$'\n'; }
die()  { echo; echo "${RED}STOPPED: $*${OFF}" >&2; exit 1; }
WARNINGS=""

# ---------------------------------------------------------------- arguments
MODE=release; VER=""; NOTE=""; FW_ONLY=0; ANDROID_NOTE=""; NO_INSTALL=0; TRAILER=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --fw-only)       FW_ONLY=1 ;;
    --no-install)    NO_INSTALL=1 ;;
    --android-note)  ANDROID_NOTE="$2"; shift ;;
    --trailer)       TRAILER="$2"; shift ;;
    --withdraw)      MODE=withdraw; VER="$2"; shift ;;
    --install-ios)   MODE=install-ios ;;
    -h|--help)       sed -n '2,32p' "$0"; exit 0 ;;
    --*)             die "unknown option $1" ;;
    *) if [[ -z "$VER" ]]; then VER="$1"; elif [[ -z "$NOTE" ]]; then NOTE="$1"; else die "too many arguments"; fi ;;
  esac
  shift
done

install_ios() {
  [[ -d "$IOS_APP" ]] || die "no iOS build at $IOS_APP"
  local v; v=$(/usr/libexec/PlistBuddy -c "Print CFBundleShortVersionString" "$IOS_APP/Info.plist")
  for D in "$IPHONE:iPhone" "$IPAD:iPad"; do
    local id="${D%%:*}" name="${D##*:}" out
    out=$(xcrun devicectl device install app --device "$id" "$IOS_APP" 2>&1 || true)
    if grep -q installationURL <<<"$out"; then ok "$name has $v"
    else warn "$name NOT installed ($(grep -oE 'error [0-9]+' <<<"$out" | head -1 || echo 'no reply') - locked or off the network). Later: dev/release.sh --install-ios"
    fi
  done
}

if [[ $MODE == install-ios ]]; then step "Install iOS"; install_ios; exit 0; fi

[[ -n "$VER" ]] || die "usage: dev/release.sh <x.y.z-slug> \"<release note>\"  (see --help)"
[[ "$VER" =~ ^[0-9]+\.[0-9]+\.[0-9]+-[a-z0-9-]+$ ]] || die "version must look like 0.9.755-short-slug (got '$VER')"
XYZ="${VER%%-*}"; NAME="RXV2-$VER"

# ---------------------------------------------------------------- withdraw
if [[ $MODE == withdraw ]]; then
  step "Withdraw $NAME from both trees"
  rm -rf "$RELEASE/v$XYZ" "$SHARED/v$XYZ"
  rm -f "$HERE/$NAME.bin" "$SHARED/$NAME.bin" "$SHARED/littlefs-$NAME.bin"
  ok "removed v$XYZ dirs, dev/$NAME.bin (or stage_website would rebuild it), and the server twins"
  cd "$RXV2"; source "$HERE/ftp_credentials.sh"
  python3 "$HERE/stage_website.py" | tail -3
  bash "$HERE/publish_website.sh" | grep -E "Done|REFUS" || die "publish failed"
  # The watcher must not go on wanting a version that no longer exists.
  LEFT=$(python3 -c "import json; v=json.load(open('$RELEASE/manifest.json'))['versions'][0]; print(v['name'], v.get('fs_md5',''))")
  LEFT_NAME="${LEFT% *}"; LEFT_MD5="${LEFT#* }"
  pkill -f "fleet_watch.sh" 2>/dev/null || true; sleep 1
  nohup zsh "$HERE/fleet_watch.sh" "$LEFT_NAME" "$LEFT_MD5" >> "$HERE/fleet_watch.log" 2>&1 &
  sleep 2; pgrep -f "zsh .*fleet_watch.sh" >/dev/null && ok "watcher now wants $LEFT_NAME" || warn "watcher did not restart"
  echo "   ${DIM}Not touched: git history and the app stores. Commit a fix and release the next number.${OFF}"
  exit 0
fi

# ---------------------------------------------------------------- preflight
[[ -n "$NOTE" ]] || die "a release note is required (it goes in release_notes.json and the commit)"
[[ -f "$HERE/ftp_credentials.sh" ]] || die "dev/ftp_credentials.sh missing (gitignored - restore it)"
# The marker is the release-tree dir (made in step 7), NOT dev/$NAME.bin: the
# PlatformIO post-build hook drops that on every BUILD, released or not.
[[ -e "$RELEASE/v$XYZ/firmware.bin" ]] && die "$NAME was already released (release tree has v$XYZ). Pick a new number, or --withdraw it first."
cd "$RXV2"
for t in pio node python3 xcodegen xcrun curl md5; do command -v "$t" >/dev/null || die "$t not on PATH"; done
FIRST_SENTENCE=$(python3 -c "import sys,re; n=sys.argv[1].strip(); m=re.match(r'(.+?[.!?])(\s|$)', n); print((m.group(1) if m else n)[:140])" "$NOTE")
[[ -n "$ANDROID_NOTE" ]] || ANDROID_NOTE="$FIRST_SENTENCE"
echo "${BOLD}Release $NAME${OFF}  ${DIM}($( [[ $FW_ONLY == 1 ]] && echo firmware only || echo pages + apps ))${OFF}"

# ---------------------------------------------------------------- 1 version
step "1  FW_VERSION → $NAME"
OLD=$(grep -o 'FW_VERSION = "RXV2-[^"]*"' src/1Defs.h | head -1)
[[ -n "$OLD" ]] || die "FW_VERSION not found in src/1Defs.h"
sed -i '' "s|FW_VERSION = \"RXV2-[^\"]*\"|FW_VERSION = \"$NAME\"|" src/1Defs.h
[[ $(grep -c "FW_VERSION = \"$NAME\"" src/1Defs.h) == 1 ]] || die "version bump did not take"
ok "was ${OLD#FW_VERSION = }"

# ---------------------------------------------------------------- 2 notes
step "2  Release notes"
NAME="$NAME" NOTE="$NOTE" python3 - <<'EOF'
import json, os
p = 'dev/release_notes.json'
s = open(p, encoding='utf-8').read()
name, note = os.environ['NAME'], os.environ['NOTE'].strip()
if '"%s"' % name in s: print('   (note already present - a re-run)'); raise SystemExit(0)
s = s.replace('{\n', '{\n  ' + json.dumps(name) + ': ' + json.dumps(note, ensure_ascii=False) + ',\n', 1)
open(p, 'w', encoding='utf-8').write(s)
json.load(open(p, encoding='utf-8'))
EOF
ok "prepended"

# ---------------------------------------------------------------- 3-4 pages
if [[ $FW_ONLY == 0 ]]; then
  step "3  Page asset versions"
  NEWV=$(python3 - <<'EOF'
import glob, re
cur = int(re.search(r'app\.js\?v=(\d+)', open('data/index.html', encoding='utf-8').read()).group(1))
new = cur + 1; n = 0
for p in glob.glob('data/*.html'):
    t = open(p, encoding='utf-8').read(); o = t
    t = re.sub(r'app\.js\?v=\d+', 'app.js?v=%d' % new, t)
    t = re.sub(r'style\.css\?v=\d+', 'style.css?v=%d' % new, t)
    if t != o: open(p, 'w', encoding='utf-8').write(t); n += 1
print('%d %d' % (new, n))
EOF
)
  ok "v${NEWV% *} on ${NEWV#* } pages"
  step "4  Search index"
  python3 dev/build_search_index.py | tail -1
fi

# ---------------------------------------------------------------- 5 gates
step "5  Gates"
for g in check_page_syntax check_links check_page_order check_banks name_gate_test help_test lane_test; do
  node "dev/$g.js" | tail -1 | grep -q "ALL PASS" || die "dev/$g.js failed - run it to see why"
  ok "$g"
done
zsh dev/prelink_hold_test.sh | tail -1 | grep -q "ALL PASS" || die "dev/prelink_hold_test.sh failed - run it to see why"
ok "prelink_hold_test"
# Every page against a real recording, as the app's review serves it (0.9.839).
# The recording is personal data: gitignored under dev/private/, so this gate
# runs only where one exists (Malcolm's Mac) and is skipped elsewhere.
REC=$(ls dev/private/session-*.json 2>/dev/null | head -1)
if [[ -n "$REC" ]]; then
  node dev/replay_test.js "$REC" | tail -1 | grep -q "ALL PASS" || die "dev/replay_test.js failed against $REC - run it to see why"
  ok "replay_test ($(basename "$REC"))"
else
  warn "replay_test skipped - no dev/private/session-*.json"
fi

# ---------------------------------------------------------------- 6 build
step "6  Build"
LOGF=$(mktemp)
pio run -e xiao_s3_ota > "$LOGF" 2>&1 || { tail -25 "$LOGF"; die "firmware build failed"; }
grep -q "SUCCESS" "$LOGF" || { tail -25 "$LOGF"; die "firmware build did not report SUCCESS"; }
ok "firmware"
if [[ $FW_ONLY == 1 ]]; then
  # mklittlefs is NOT deterministic (same data/, different bytes every build -
  # found 0.9.756), so a rebuilt image always carries a new fs_md5 and every
  # receiver re-flashes 1.5 MB of unchanged pages. A firmware-only release
  # therefore REUSES the last release's image - after unpacking it and proving
  # it matches data/ byte for byte. Differs = the pages did change: no --fw-only.
  PREV=$(python3 -c "import json; print(json.load(open('$RELEASE/manifest.json'))['versions'][0]['name'])")
  PREV_FS="$RELEASE/v${PREV#RXV2-}"; PREV_FS="${PREV_FS%%-*}/littlefs.bin"
  [[ -f "$PREV_FS" ]] || die "no previous image at $PREV_FS to reuse"
  MK=~/.platformio/packages/tool-mklittlefs/mklittlefs; UNP=$(mktemp -d)
  "$MK" -u "$UNP" -b 4096 -p 256 -s "$(stat -f%z "$PREV_FS")" "$PREV_FS" > /dev/null 2>&1 || die "could not unpack $PREV_FS"
  if diff -rq "$UNP" data/ > "$LOGF" 2>&1; then
    cp "$PREV_FS" .pio/build/xiao_s3_ota/littlefs.bin; touch .pio/build/xiao_s3_ota/littlefs.bin
    ok "filesystem: pages identical to $PREV - reusing its image, so receivers skip the fs flash"
  else
    head -5 "$LOGF"; die "data/ differs from the last release's pages (above) - this is not a firmware-only release: drop --fw-only"
  fi
  rm -rf "$UNP"
else
  pio run -e xiao_s3_ota -t buildfs > "$LOGF" 2>&1 || { tail -25 "$LOGF"; die "filesystem build failed (full? see dev/check_fs_image.py)"; }
  python3 dev/check_fs_image.py | tail -1 | grep -q "ALL PASS" || die "filesystem image is not whole - a full partition leaves a PARTIAL image behind"
  ok "filesystem (whole)"
fi
strings .pio/build/xiao_s3_ota/firmware.bin | grep -q "$NAME" || die "built firmware does not carry $NAME"
FW=.pio/build/xiao_s3_ota/firmware.bin; FS=.pio/build/xiao_s3_ota/littlefs.bin
MD5=$(md5 -q "$FS")

# ---------------------------------------------------------------- 7 copies
step "7  Both release trees"
mkdir -p "$RELEASE/v$XYZ" "$SHARED/v$XYZ"
cp "$FW" "$RELEASE/v$XYZ/firmware.bin"; cp "$FS" "$RELEASE/v$XYZ/littlefs.bin"
cp "$FW" "$HERE/$NAME.bin"
cp "$FW" "$SHARED/v$XYZ/firmware.bin"; cp "$FS" "$SHARED/v$XYZ/littlefs.bin"
cp "$FW" "$SHARED/v$XYZ/$NAME.bin"; md5 -q "$SHARED/v$XYZ/$NAME.bin" > "$SHARED/v$XYZ/$NAME.bin.md5"
cp "$FW" "$SHARED/$NAME.bin"; cp "$FS" "$SHARED/littlefs-$NAME.bin"

# release/latest/ — the five images a person needs to flash a BARE XIAO by
# cable, for anyone building their own dongle. The dongle page links straight
# to these by name, so they must never go stale (added 2026-09-21).
LATEST="$RELEASE/latest"; mkdir -p "$LATEST"
cp "$FW" "$LATEST/firmware.bin"; cp "$FS" "$LATEST/littlefs.bin"
cp .pio/build/xiao_s3_ota/bootloader.bin "$LATEST/bootloader.bin"
cp .pio/build/xiao_s3_ota/partitions.bin "$LATEST/partitions.bin"
BOOT_APP0=$(ls "$HOME"/.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin 2>/dev/null | head -1)
[[ -f "$BOOT_APP0" ]] && cp "$BOOT_APP0" "$LATEST/boot_app0.bin"
printf 'These five files flash a bare Seeed XIAO ESP32-S3 into an LDRC dongle or receiver.\nBuild: %s\n\nesptool write_flash offsets:\n  0x0       bootloader.bin\n  0x8000    partitions.bin\n  0xe000    boot_app0.bin\n  0x10000   firmware.bin\n  0x670000  littlefs.bin\n\nInstructions: https://messiter.com/rotorflight/dongle.html#firmware\n' "$NAME" > "$LATEST/README.txt"
# The browser flasher (messiter.com/rotorflight/flash.html) reads this manifest
# and writes the five images itself, so it must name the current version.
python3 - "$LATEST" "$XYZ" <<'PYEOF'
import json, io, sys
latest, ver = sys.argv[1], sys.argv[2]
io.open(latest + '/manifest-esp.json', 'w').write(json.dumps({
    "name": "LockDownRadioControl RXV2", "version": ver,
    "new_install_prompt_erase": False,   # one dialog fewer; it then always erases, which is what the page promises
    "builds": [{"chipFamily": "ESP32-S3", "parts": [
        {"path": "bootloader.bin", "offset": 0x0},
        {"path": "partitions.bin", "offset": 0x8000},
        {"path": "boot_app0.bin",  "offset": 0xe000},
        {"path": "firmware.bin",   "offset": 0x10000},
        {"path": "littlefs.bin",   "offset": 0x670000}]}]}, indent=1))
PYEOF

for f in bootloader.bin partitions.bin boot_app0.bin firmware.bin littlefs.bin manifest-esp.json; do
  [[ -s "$LATEST/$f" ]] || die "release/latest/$f missing — the dongle build page and the browser flasher link to it"
done

ok "NewWebSite v$XYZ, dev/$NAME.bin, firmware-server v$XYZ + root twins (fs md5 $MD5), release/latest refreshed"

# ---------------------------------------------------------------- 8 android
AND_V="(unchanged)"
if [[ $FW_ONLY == 0 ]]; then
  step "8  Android"
  AND_V=$(python3 - <<'EOF'
import re
p = '../RXV2App/android/RXV2App/app/build.gradle.kts'
s = open(p).read()
code = int(re.search(r'versionCode = (\d+)', s).group(1)) + 1
name = re.search(r'versionName = "(\d+)\.(\d+)"', s)
new = '%s.%d' % (name.group(1), int(name.group(2)) + 1)
s = re.sub(r'versionCode = \d+', 'versionCode = %d' % code, s, 1)
s = re.sub(r'versionName = "[^"]*"', 'versionName = "%s"' % new, s, 1)
open(p, 'w').write(s); print(new)
EOF
)
  bash "$APPS/android/publish_app.sh" "$ANDROID_NOTE" > "$LOGF" 2>&1 || { tail -25 "$LOGF"; die "Android publish failed"; }
  grep -q "Done. Live manifest" "$LOGF" || { tail -15 "$LOGF"; die "Android publish did not finish"; }
  ok "$AND_V built + published (it synced both app webroots)"
fi
python3 dev/check_app_sync.py > "$LOGF" 2>&1 || { grep -E "OUT OF STEP|differs" "$LOGF"; die "app webroots do not match data/ - the pages changed on a --fw-only release? (drop --fw-only)"; }
ok "app webroots match data/"

# ---------------------------------------------------------------- 9 publish
step "9  messiter.com"
source "$HERE/ftp_credentials.sh"
python3 dev/stage_website.py > "$LOGF" 2>&1 || { tail -10 "$LOGF"; die "stage_website failed"; }
grep -E "newest|WARNING|littlefs" "$LOGF" | sed 's/^/   /'
grep -q "WARNING" "$LOGF" && die "stage_website warned (above) - the newest release would ship without pages"
bash dev/publish_website.sh > "$LOGF" 2>&1 || { tail -20 "$LOGF"; die "publish refused (above)"; }
LIVE=$(curl -s -m 15 "$MANIFEST_URL" | python3 -c "import sys,json; v=json.load(sys.stdin)['versions'][0]; print(v['name'], v.get('fs_md5',''))")
[[ "$LIVE" == "$NAME $MD5" ]] || die "live manifest says '$LIVE', expected '$NAME $MD5'"
ok "live: $NAME, fs md5 matches"

# ---------------------------------------------------------------- 10 ios
IOS_V="(unchanged)"
if [[ $FW_ONLY == 0 ]]; then
  step "10 iOS"
  IOS_V=$(python3 - <<'EOF'
import re
p = '../RXV2App/project.yml'
s = open(p).read()
m = re.search(r'CFBundleShortVersionString: "(\d+)\.(\d+)"', s)
new = '%s.%d' % (m.group(1), int(m.group(2)) + 1)
open(p, 'w').write(s.replace(m.group(0), 'CFBundleShortVersionString: "%s"' % new, 1)); print(new)
EOF
)
  ( cd "$APPS" && xcodegen generate > "$LOGF" 2>&1 ) || { tail -10 "$LOGF"; die "xcodegen failed"; }
  ( cd "$APPS" && xcodebuild -project RXV2App.xcodeproj -scheme RXV2App -configuration Debug \
      -destination 'generic/platform=iOS' -derivedDataPath "$DD_IOS" -allowProvisioningUpdates build > "$LOGF" 2>&1 ) \
      || { grep -E "error:" "$LOGF" | head -10; die "iOS build failed"; }
  [[ $(/usr/libexec/PlistBuddy -c "Print CFBundleShortVersionString" "$IOS_APP/Info.plist") == "$IOS_V" ]] || die "iOS build is not $IOS_V"
  ok "$IOS_V built"
  if [[ $NO_INSTALL == 0 ]]; then install_ios; fi
fi

# ---------------------------------------------------------------- 11 watcher
step "11 Fleet watcher"
pkill -f "fleet_watch.sh" 2>/dev/null || true; sleep 1
nohup zsh "$HERE/fleet_watch.sh" "$NAME" "$MD5" >> "$HERE/fleet_watch.log" 2>&1 &
sleep 3
pgrep -f "zsh .*fleet_watch.sh" >/dev/null && ok "watching for $NAME" || warn "watcher did not start - nohup zsh dev/fleet_watch.sh $NAME $MD5"

# ---------------------------------------------------------------- 12 commit
step "12 Commit + push"
MSG=$(mktemp)
{
  echo "RXV2 $VER — $FIRST_SENTENCE"
  echo
  echo "$NOTE" | fold -s -w 72
  echo
  if [[ $FW_ONLY == 1 ]]; then echo "Firmware only; pages unchanged (receivers skip the fs flash)."
  else echo "Apps $IOS_V (iOS, installed to both devices) / $AND_V (Android, published)."; fi
  if [[ -n "$TRAILER" ]]; then echo; printf '%b\n' "$TRAILER"; fi
} > "$MSG"
( cd "$ROOT" && git add -A && git commit -q -F "$MSG" && git push -q origin HEAD:main ) || die "commit/push failed"
ok "pushed"

# ---------------------------------------------------------------- 13 ping
step "13 Ping"
if [[ -f "$HERE/notify.sh" ]]; then
  source "$HERE/notify.sh"
  ping_watch "$VER live — $FIRST_SENTENCE Apps $IOS_V / $AND_V."
  ok "sent"
else warn "no dev/notify.sh - not pinged"; fi

echo
echo "${BOLD}${GRN}Released $NAME${OFF}   iOS $IOS_V · Android $AND_V · fs $MD5"
if [[ -n "$WARNINGS" ]]; then echo "${YEL}Warnings:${OFF}"; printf '%s' "$WARNINGS"; fi
