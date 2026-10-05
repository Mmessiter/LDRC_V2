#!/bin/sh
# Build and run the NextionScript host tests (macOS clang++; same flags an ESP32 build uses).
set -e
cd "$(dirname "$0")"
clang++ -std=c++11 -fno-exceptions -fno-rtti -Wall -Wextra -O1 -o test_script test_script.cpp ../../lib/NextionScript/NextionScript.cpp
./test_script "${1:-../pages.json}"
