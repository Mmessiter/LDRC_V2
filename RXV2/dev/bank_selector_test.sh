#!/bin/zsh
# Host test of src/BankSelector.h (0.9.904): the position count of the flight controller's selector lines, as the
# receiver reads it off its copy of the adjustment lines for banks.json and /api/tx/banks.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d)
c++ -std=c++17 -Wall -Wextra -o "$T/t" "$HERE/bank_selector_test.cpp"
"$T/t"
