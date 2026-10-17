#!/bin/sh
# Host test of src/film_core.h: the LDRC film's header, table, timing and picture choice (screen 1.11.85).
set -e
cd "$(dirname "$0")"
clang++ -std=c++11 -Wall -Wextra -O1 -o test_film test_film.cpp
./test_film "$@"
