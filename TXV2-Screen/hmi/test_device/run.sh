#!/bin/sh
# Host tests for src/wifi_device.h, the device's own half of the WiFi page: the store in the chip (and a power cut
# while it is written), joining by itself, the radio and the page together. The header is compiled AS IT IS against
# a make-believe ESP32 (sim_env.h: the WiFi library as its source reads, a radio that takes time, a flash whose
# power can be cut, a display that checks every rectangle).
set -e
cd "$(dirname "$0")"
clang++ -std=c++17 -O1 -w -I. -I../../lib/LdrcWifi -I../../lib/LdrcUpdate -I../../lib/NextionFonts -I../../src -o test_device test_device.cpp ../../lib/LdrcWifi/LdrcWifi.cpp
./test_device "$@"
