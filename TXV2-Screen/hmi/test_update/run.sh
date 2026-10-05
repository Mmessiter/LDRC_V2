#!/bin/sh
# Host tests for LdrcUpdate ("Check for update"): the screen's Updater and LinkMaster against a make-believe
# website, the screen's card, and a make-believe Teensy that runs the REAL LinkServer (../test_link/sim.h).
set -e
cd "$(dirname "$0")"
LINK=../../lib/LdrcLink
UPD=../../lib/LdrcUpdate
TEENSY="$HOME/Documents/GitHub/TXV1B/TransmitterCode/lib/LdrcLink"
cmp "$LINK/LdrcLink.h" "$TEENSY/LdrcLink.h" && cmp "$LINK/LdrcLink.cpp" "$TEENSY/LdrcLink.cpp" || { echo "THE TWO COPIES OF LdrcLink DIFFER - run dev/sync_link.sh"; exit 1; }
clang++ -std=c++11 -fno-exceptions -fno-rtti -Wall -Wextra -O1 -I"$LINK" -I"$UPD" -I"$TEENSY" -I../test_link -o test_update \
    test_update.cpp "$LINK/LdrcLink.cpp" "$LINK/LinkMaster.cpp" "$UPD/LdrcUpdate.cpp" "$TEENSY/LinkServer.cpp"
./test_update "$@"
