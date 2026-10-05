#!/bin/sh
# Host tests for LdrcFlight (the flight screen): its words, its settings, its boxes, when it shows, its setup page.
set -e
cd "$(dirname "$0")"
clang++ -std=c++11 -fno-exceptions -fno-rtti -Wall -Wextra -O1 -I../../lib/LdrcFlight -I../../lib/LdrcTheme -o test_flight test_flight.cpp ../../lib/LdrcFlight/LdrcFlight.cpp ../../lib/LdrcTheme/LdrcTheme.cpp
./test_flight "$@"
