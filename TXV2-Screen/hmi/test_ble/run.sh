#!/bin/sh
# Host test of the Bluetooth bridge framing (lib/LdrcBle).
set -e
cd "$(dirname "$0")"
clang++ -std=c++11 -fno-exceptions -fno-rtti -Wall -Wextra -O1 -I../../lib/LdrcBle -o test_ble test_ble.cpp ../../lib/LdrcBle/LdrcBle.cpp
./test_ble
