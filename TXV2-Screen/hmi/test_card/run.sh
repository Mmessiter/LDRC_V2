#!/bin/sh
# Host tests for LdrcCard (the card's own start, when the SD library will not mount it): make-believe cards in SPI mode.
set -e
cd "$(dirname "$0")"
clang++ -std=c++11 -fno-exceptions -fno-rtti -Wall -Wextra -O1 -I../../lib/LdrcCard -o test_card test_card.cpp ../../lib/LdrcCard/LdrcCard.cpp
./test_card "$@"
