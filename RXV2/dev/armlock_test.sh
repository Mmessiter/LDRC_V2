#!/bin/zsh
# Host test of 0.9.923 (11 Nov 2026): the lock on an armed model asks the flight controller, and no longer goes by the
# arm switch alone (Malcolm, Test1: "frequently the iOS app has warned me that arming is on when it was not"). The block
# between ARMLOCK-BEGIN/END in src/1Defs.h is cut out, compiled and run (dev/armlock_test.cpp): the rule, what the app is
# shown, the arm switch followed, and that morning on Test1 played through millisecond by millisecond - with a real
# arming beside it, where the door must never open. Then the sources are read: every gate goes through the rule.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
SRC="$HERE/../src"
T=$(mktemp -d)
awk '/^\/\/ ARMLOCK-BEGIN/{p=1} p{print} /^\/\/ ARMLOCK-END/{p=0}' "$SRC/1Defs.h" > "$T/armlock_block.h"
[[ -s "$T/armlock_block.h" ]] || { echo "FAILED: ARMLOCK block not found in src/1Defs.h"; exit 1; }
# The ages of radio silence (the hold, 'transmitter off'): a confirmed arming is kept through a gap up to LINK_DEAD_MS.
awk '/^\/\/ LINK-AGES-BEGIN/{p=1} /^\/\/ LINK-AGES-END/{p=0} p' "$SRC/1Defs.h" > "$T/link_block.h"
[[ -s "$T/link_block.h" ]] || { echo "FAILED: LINK-AGES block not found in src/1Defs.h"; exit 1; }
# What the radios call fresh (fcArmedWordFresh, 0.9.917): the app must be shown by the same number.
FRESH=$(sed -n -E 's/^inline bool fcArmedWordFresh\(\).*< ([0-9]+); \}.*/\1/p' "$SRC/1Defs.h" | head -1)
[[ -n "$FRESH" ]] || { echo "FAILED: fcArmedWordFresh() not found in src/1Defs.h"; exit 1; }
c++ -std=c++17 -Wall -Werror -fsanitize=address,undefined -DARMLOCK_BLOCK="\"$T/armlock_block.h\"" -DLINK_BLOCK="\"$T/link_block.h\"" -DRADIOS_FRESH_MS=$FRESH -o "$T/t" "$HERE/armlock_test.cpp"
"$T/t" > "$T/out" || { cat "$T/out"; exit 1; }
sed '$d' "$T/out" | sed '$d'            # (its own last lines are said once more below, after the reading of the sources)
bad=0
has() { grep -q -- "$2" "$SRC/$1" && echo "PASS $1: $3" || { echo "FAIL $1: $3"; bad=1; }; }
hasnt() { grep -q -- "$2" "$SRC/$1" && { echo "FAIL $1: $3"; bad=1; } || echo "PASS $1: $3"; }
# 1. The gates the app and the transmitter's screen come through all use the rule.
has WebPages.h 'const ArmLock lock = armLockNow();' "the app's flight controller requests go by the rule"
has WebPages.h 'if (armLockNow(true) != ARMLOCK_OPEN)' "the transmitter's words over Bluetooth go by the rule, with its last word"
# 2. Neither of them decides on the arming channel alone any more.
hasnt WebPages.h 'const bool linkArmed = armLink && armingChannel' "neither of those two doors goes by the arming channel alone"
# 3. What restarts the receiver, stalls it on a flash write or saves the failsafe positions (refuseIfArmed) still looks
#    at the SWITCH itself, whatever the flight controller says: a restart shows it the switch off, then on again.
body=$(awk '/^inline bool refuseIfArmed\(const char\* what\) \{/{p=1} p{print} /^}/{if(p)exit}' "$SRC/WebPages.h")
echo "$body" | grep -q 'if (armSwitchReadsOn()) {' && echo "PASS WebPages.h: a restart, a flash write or saving the failsafe is still refused with the arm switch on" || { echo "FAIL WebPages.h: refuseIfArmed no longer looks at the arm switch itself"; bad=1; }
echo "$body" | grep -q 'armLockNow(' && { echo "FAIL WebPages.h: refuseIfArmed must not be opened by the flight controller's word"; bad=1; } || echo "PASS WebPages.h: ... and the flight controller's 'not armed' does not open that door"
n=$(grep -c 'refuseIfArmed("' "$SRC/WebPages.h" || true)
[[ "$n" -ge 19 ]] && echo "PASS WebPages.h: $n doors still go through refuseIfArmed" || { echo "FAIL WebPages.h: only $n doors go through refuseIfArmed, there were 19"; bad=1; }
# 4. What the app is shown comes from the same place, on WiFi and on Bluetooth.
has WebPages.h ': armShownNow();' "the state the red banner hangs on"
has BleConfig.h 'bool armedNow = armShownNow();' "the ARMED dot on the channels page (the Bluetooth stream)"
# 5. The switch is followed on every pass and inside the waits; the follow keeps the word fresh while it is on.
has main.cpp '^    armSwitchTick();' "the arm switch is followed on every pass of loop()"
has 1Defs.h '^    armSwitchTick();   ' "... and inside the waits (keepLinkTick)"
has MspFc.h 'armSwitch.onSinceMs ? 1000 : 2000' "the flight controller is asked every second while the arm switch is on and it says not armed"
# 6. The question itself: never on a dongle or in simulator mode, never while the line is somebody else's; put and
#    bounded by the tested block (armAsk), not by the long wait of a page's own request.
has WebPages.h 'if (dongleEnabled || simEnabled || !fcInfo.detected) return -1;' "the question is never put on a dongle or in simulator mode"
has WebPages.h 'if (UsbHostMsp::cliMode || mspBridgeActive || bbCheckActive || bleOtaActive || outputDetachedForFailsafe) return -1;' "... nor while the line is somebody else's"
has WebPages.h 'return armAsk(fcArmedAskState, io, renewing);' "the question goes through the bounded armAsk"
body=$(awk '/^inline int fcArmedAsk\(bool renewing\) \{/{p=1} p{print} /^}/{if(p)exit}' "$SRC/WebPages.h")
echo "$body" | grep -q 'mspRequestAndWait' && { echo "FAIL WebPages.h: the question must not use mspRequestAndWait (it can wait 2.7 s)"; bad=1; } || echo "PASS WebPages.h: ... and not through the page-request wait, which can take 2.7 s"
has WebPages.h 'const ArmLock lock = armLockWaiting(' "a request at the moment of switching on waits out the settle time, by the tested block"
has WebPages.h 'if (lock == ARMLOCK_ASKING) {' "an answer still on its way is 'busy, try again' to a page, never ARMED"
# 7. A confirmed arming is kept through a gap in the radio link, up to the time the transmitter is taken to be off.
has 1Defs.h 'return quietMs >= 1000 && quietMs < LINK_DEAD_MS;' "a confirmed arming is kept through radio silence up to LINK_DEAD_MS"
has 1Defs.h 'armSwitchStep(armSwitch, armSwitchReadsOn(), armSwitchQuietButLastOn(), fcInfo.armed, fcInfo.armedMs, millis());' "... by the tracker the test runs"
[[ $bad -eq 0 ]] || { echo; echo "FAILED"; exit 1; }
echo
echo "ALL PASS"
