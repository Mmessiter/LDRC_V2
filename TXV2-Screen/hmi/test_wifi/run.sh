#!/bin/sh
# Host tests for LdrcWifi (the WiFi page): the screen's WifiSetup against make-believe networks.
set -e
cd "$(dirname "$0")"
clang++ -std=c++11 -fno-exceptions -fno-rtti -Wall -Wextra -O1 -I../../lib/LdrcWifi -o test_wifi test_wifi.cpp ../../lib/LdrcWifi/LdrcWifi.cpp
./test_wifi "$@"
