#!/bin/sh
# Host tests for LdrcPics (the model pictures' chooser): the screen's Pictures against a make-believe card and Teensy.
set -e
cd "$(dirname "$0")"
clang++ -std=c++11 -fno-exceptions -fno-rtti -Wall -Wextra -O1 -I../../lib/LdrcPics -o test_pics test_pics.cpp ../../lib/LdrcPics/LdrcPics.cpp
./test_pics "$@"
