#!/bin/sh
# Host tests for LdrcLink: the screen's LinkMaster against the Teensy's LinkServer over a wire that
# drops and corrupts bytes, with a make-believe Teensy that restarts, rolls back, or is too old.
set -e
cd "$(dirname "$0")"
SCREEN=../../lib/LdrcLink
TEENSY="$HOME/Documents/GitHub/TXV1B/TransmitterCode/lib/LdrcLink"
cmp "$SCREEN/LdrcLink.h" "$TEENSY/LdrcLink.h" && cmp "$SCREEN/LdrcLink.cpp" "$TEENSY/LdrcLink.cpp" || { echo "THE TWO COPIES OF LdrcLink DIFFER - run dev/sync_link.sh"; exit 1; }
clang++ -std=c++11 -fno-exceptions -fno-rtti -Wall -Wextra -O1 -I"$SCREEN" -I"$TEENSY" -o test_link \
    test_link.cpp "$SCREEN/LdrcLink.cpp" "$SCREEN/LinkMaster.cpp" "$TEENSY/LinkServer.cpp"
./test_link "$@"
# ... and the restore of the pilot's files on the REAL SdFat (skipped when PlatformIO's Teensy package is not there)
[ $# -eq 0 ] && ./sdfat/run.sh
