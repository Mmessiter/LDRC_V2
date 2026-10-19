#!/bin/sh
# The audio ring's two ends (src/audio_ring.h) under the race of 19 Oct 2026 and under two threads: hmi/test_audio/test_audio.cpp
cd "$(dirname "$0")"
clang++ -std=c++17 -O2 -Wall -Wextra -pthread -o test_audio test_audio.cpp || exit 1
./test_audio "$@"
