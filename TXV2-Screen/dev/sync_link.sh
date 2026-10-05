#!/bin/sh
# LdrcLink.h/.cpp exist twice (the Teensy's project and the screen's). The Teensy's copy is the master.
set -e
T="$HOME/Documents/GitHub/TXV1B/TransmitterCode/lib/LdrcLink"
S="$(cd "$(dirname "$0")/.." && pwd)/lib/LdrcLink"
cp "$T/LdrcLink.h" "$T/LdrcLink.cpp" "$S/"
echo "copied LdrcLink.h and LdrcLink.cpp from the Teensy's project to the screen's"
