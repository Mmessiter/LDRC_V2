#!/bin/sh
# Host test of src/quiet_time.h: the front screen's switch drawn and copied in the panel's quiet time (screen 1.11.67).
set -e
cd "$(dirname "$0")"
clang++ -std=c++11 -fno-exceptions -fno-rtti -Wall -Wextra -O1 -o test_quiet test_quiet.cpp
./test_quiet "$@"
