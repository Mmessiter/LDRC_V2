#!/bin/sh
# Build the Mac renderer from the screen's own code (see render.cpp).
set -e
cd "$(dirname "$0")"
python3 extract.py
printf '#pragma once\n' > gen/pgmspace.h                 # (nextion_fonts.h asks for it on the ESP32)
clang++ -std=c++17 -O2 -w -I. -I../../lib/NextionScript -I../../lib/NextionFonts -I../../lib/LdrcFlight -I../../lib/LdrcTheme -I../../src -Igen -I"../../.pio/libdeps/ota/ArduinoJson/src" \
    render.cpp ../../lib/NextionScript/NextionScript.cpp ../../lib/LdrcFlight/LdrcFlight.cpp ../../lib/LdrcTheme/LdrcTheme.cpp -o gen/render
echo "built hmi/render_host/gen/render"
