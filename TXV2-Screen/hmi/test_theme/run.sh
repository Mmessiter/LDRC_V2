#!/bin/sh
# Host tests for LdrcTheme (the pilot's colours): the lists, the setting, which colours are the style's, the Colours page.
set -e
cd "$(dirname "$0")"
clang++ -std=c++11 -fno-exceptions -fno-rtti -Wall -Wextra -O1 -I../../lib/LdrcTheme -o test_theme test_theme.cpp ../../lib/LdrcTheme/LdrcTheme.cpp
./test_theme "$@"
