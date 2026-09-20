#!/bin/zsh
# Capture App Store screenshots from the simulator in demo mode.
#   appstore/shoot.sh <simulator-udid> <out-subdir>
# Pages are opened with the app's own --demo / --page launch arguments.
set -e
HERE=$(cd "$(dirname $0)" && pwd)
UDID=$1; OUT=$2
APP="/Volumes/2TB SSD/claude-build/dd_sim/Build/Products/Release-iphonesimulator/RXV2App.app"
BID=com.messiter.rxv2app
D=$HERE/screenshots/$OUT
mkdir -p $D
xcrun simctl boot $UDID 2>/dev/null || true
xcrun simctl bootstatus $UDID -b >/dev/null 2>&1 || true
xcrun simctl install $UDID "$APP"
# Apple wants a tidy status bar and no notification banners in store shots.
xcrun simctl status_bar $UDID override --time "9:41" --batteryState charged \
  --batteryLevel 100 --cellularBars 4 --wifiBars 3 2>/dev/null || true
flatten() {   # App Store rejects screenshots with an alpha channel, and sips
              # cannot strip it. CoreGraphics can, and needs nothing installed.
  xcrun swift "$HERE/flatten_png.swift" "$1"
}
shoot() {   # shoot <name> <page-path-or-none>
  xcrun simctl terminate $UDID $BID 2>/dev/null || true
  if [[ "$2" == "none" ]]; then
    xcrun simctl launch $UDID $BID --demo >/dev/null
  else
    xcrun simctl launch $UDID $BID --demo --page "$2" >/dev/null
  fi
  sleep 10
  xcrun simctl io $UDID screenshot --type=png "$D/$1.png" >/dev/null 2>&1
  # App Store rejects screenshots with an alpha channel. sips will not strip it;
  # flatten onto white and write back as 8-bit RGB.
  flatten "$D/$1.png"
  echo "  $1.png"
}
# The app's own first screen — four doors, drawn in SwiftUI. It only appears
# without --demo, so it gets its own launch rather than the shoot() helper.
xcrun simctl terminate $UDID $BID 2>/dev/null || true
xcrun simctl launch $UDID $BID >/dev/null
sleep 8
xcrun simctl io $UDID screenshot --type=png "$D/1-front.png" >/dev/null 2>&1
flatten "$D/1-front.png"; echo "  1-front.png"

shoot 2-home           /
shoot 3-newheli        /rotorflight-newheli
shoot 4-easytuning     /rotorflight-easy
shoot 5-blackbox       /rotorflight-filtercheck
shoot 6-traces         /flight
shoot 7-governor       /rotorflight-gov-profile
xcrun simctl terminate $UDID $BID 2>/dev/null || true
echo "done -> $D"
