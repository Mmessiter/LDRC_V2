#!/bin/zsh
# Capture App Store screenshots from the simulator in demo mode.
#   appstore/shoot.sh <simulator-udid> <out-subdir>
# Pages are opened with the app's own --demo / --page launch arguments.
set -e
UDID=$1; OUT=$2
APP="/Volumes/2TB SSD/claude-build/dd_sim/Build/Products/Release-iphonesimulator/RXV2App.app"
BID=com.messiter.rxv2app
D=$(dirname $0)/screenshots/$OUT
mkdir -p $D
xcrun simctl boot $UDID 2>/dev/null || true
xcrun simctl bootstatus $UDID -b >/dev/null 2>&1 || true
xcrun simctl install $UDID "$APP"
# Apple wants a tidy status bar and no notification banners in store shots.
xcrun simctl status_bar $UDID override --time "9:41" --batteryState charged \
  --batteryLevel 100 --cellularBars 4 --wifiBars 3 2>/dev/null || true
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
  python3 -c "
from PIL import Image
import sys
p = sys.argv[1]
im = Image.open(p)
if im.mode in ('RGBA', 'LA', 'P'):
    im = im.convert('RGBA')
    bg = Image.new('RGB', im.size, (255, 255, 255))
    bg.paste(im, mask=im.split()[-1])
    im = bg
else:
    im = im.convert('RGB')
im.save(p)
" "$D/$1.png"
  echo "  $1.png"
}
shoot 1-front          /
shoot 2-newheli        /rotorflight-newheli
shoot 3-easytuning     /rotorflight-easy
shoot 4-blackbox       /rotorflight-filtercheck
shoot 5-traces         /flight
shoot 6-governor       /rotorflight-gov-profile
xcrun simctl terminate $UDID $BID 2>/dev/null || true
echo "done -> $D"
