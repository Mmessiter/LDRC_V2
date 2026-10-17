#!/bin/sh
# Build the Mac renderer from the screen's own code (see render.cpp).
set -e
cd "$(dirname "$0")"
python3 extract.py
printf '#pragma once\n' > gen/pgmspace.h                 # (nextion_fonts.h asks for it on the ESP32)
# The screen's own pages (own.h): their libraries, the QR encoder the ESP32's framework has (Project Nayuki's, MIT), and
# the update panel's states, made by the real Updater on the host tests' bench (updscenes.cpp: it needs the Teensy's
# LinkServer, TXV1B/TransmitterCode/lib/LdrcLink, as hmi/test_update does).
LIB=../../lib
TEENSY="${TEENSY_LINK:-$HOME/Documents/GitHub/TXV1B/TransmitterCode/lib/LdrcLink}"
[ -f "$TEENSY/LinkServer.cpp" ] || { echo "build.sh: no $TEENSY/LinkServer.cpp (set TEENSY_LINK)"; exit 1; }
clang -O2 -w -c qrcodegen/qrcodegen.c -o gen/qrcodegen.o
clang++ -std=c++17 -O2 -w -I"$LIB/LdrcLink" -I"$LIB/LdrcUpdate" -I"$TEENSY" -I../test_link -I../test_update -c updscenes.cpp -o gen/updscenes.o
clang++ -std=c++17 -O2 -w -I. -I$LIB/NextionScript -I$LIB/NextionFonts -I$LIB/LdrcFlight -I$LIB/LdrcTheme -I$LIB/LdrcWifi -I$LIB/LdrcCli -I$LIB/LdrcPics -I$LIB/LdrcUpdate -I$LIB/LdrcLink -Iqrcodegen \
    -I../../src -Igen -I"../../.pio/libdeps/ota/ArduinoJson/src" -I"../../.pio/libdeps/ota/JPEGDEC/src" \
    render.cpp $LIB/NextionScript/NextionScript.cpp $LIB/LdrcFlight/LdrcFlight.cpp $LIB/LdrcTheme/LdrcTheme.cpp \
    $LIB/LdrcWifi/LdrcWifi.cpp $LIB/LdrcCli/LdrcCli.cpp $LIB/LdrcPics/LdrcPics.cpp \
    $LIB/LdrcUpdate/LdrcUpdate.cpp $LIB/LdrcLink/LdrcLink.cpp $LIB/LdrcLink/LinkMaster.cpp "$TEENSY/LinkServer.cpp" \
    "../../.pio/libdeps/ota/JPEGDEC/src/JPEGDEC.cpp" gen/updscenes.o gen/qrcodegen.o -o gen/render
echo "built hmi/render_host/gen/render"
