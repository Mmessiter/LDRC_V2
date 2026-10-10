#!/bin/sh
# Host tests for LdrcCli (the command line page): the screen's CliPage against a make-believe receiver and card.
set -e
cd "$(dirname "$0")"
clang++ -std=c++11 -fno-exceptions -fno-rtti -Wall -Wextra -O1 -I../../lib/LdrcCli -I../../lib/LdrcWifi -o test_cli test_cli.cpp ../../lib/LdrcCli/LdrcCli.cpp ../../lib/LdrcWifi/LdrcWifi.cpp
./test_cli "$@"
