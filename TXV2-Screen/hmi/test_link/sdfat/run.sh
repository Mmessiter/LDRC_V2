#!/bin/sh
# The restore of models.dat, as the TEENSY carries it out, on the REAL SdFat of Teensyduino (built for the Mac, on a
# FAT32 volume in memory) with the REAL LinkServer. Found by review on 29-9-2026: a file replaced under a handle
# that the firmware held open was written through that handle at power-off, into clusters that by then belonged
# to other files. This test runs the sequence as it WAS (and must see the damage) and as it IS (and must see none).
#
# SdFat is not kept in this project: it is taken from PlatformIO's Teensy package at build time, into ./build.
set -e
cd "$(dirname "$0")"
SDFAT="$HOME/.platformio/packages/framework-arduinoteensy/libraries/SdFat/src"
TEENSY="$HOME/Documents/GitHub/TXV1B/TransmitterCode/lib/LdrcLink"
if [ ! -d "$SDFAT/FatLib" ]; then echo "test_sdfat: SKIPPED (no SdFat at $SDFAT)"; exit 0; fi
rm -rf build && mkdir -p build/src
cp -R "$SDFAT/common" "$SDFAT/FatLib" build/src/
cp "$SDFAT/SdFatConfig.h" build/src/
# as on the Teensy 4.1 (an ARM with long file names), without Arduino's Serial and String
sed -i '' -e 's/#define ENABLE_ARDUINO_FEATURES 1/#define ENABLE_ARDUINO_FEATURES 0/' \
          -e 's/#define ENABLE_ARDUINO_SERIAL 1/#define ENABLE_ARDUINO_SERIAL 0/' \
          -e 's/#define ENABLE_ARDUINO_STRING 1/#define ENABLE_ARDUINO_STRING 0/' \
          -e 's/#elif defined(__arm__)/#elif 1/' \
          -e 's/#if defined(__arm__)/#if 1/' \
          -e 's/#ifdef __arm__/#if 1/' \
          -e 's/#if defined(__MK64FX512__) || defined(__MK66FX1M0__) || defined(__IMXRT1062__)/#if 1/' build/src/SdFatConfig.h
cat > build/src/common/FsBlockDevice.h <<'EOT'
// (test build: there is no SD card driver here; a block device is whatever implements the interface)
#ifndef FsBlockDevice_h
#define FsBlockDevice_h
#include "FsBlockDeviceInterface.h"
typedef FsBlockDeviceInterface FsBlockDevice;
#endif
EOT
SD="build/src/FatLib/FatFile.cpp build/src/FatLib/FatFileLFN.cpp build/src/FatLib/FatName.cpp build/src/FatLib/FatPartition.cpp build/src/FatLib/FatVolume.cpp build/src/FatLib/FatFormatter.cpp build/src/FatLib/FatFilePrint.cpp build/src/common/FsCache.cpp build/src/common/FsName.cpp build/src/common/FsStructs.cpp build/src/common/FsUtf.cpp build/src/common/upcase.cpp build/src/common/FsDateTime.cpp build/src/common/FmtNumber.cpp build/src/common/PrintBasic.cpp"
clang++ -std=c++11 -O1 -w -include host_shim.h -Ibuild/src -Ibuild/src/FatLib -I"$TEENSY" -o build/test_sdfat test_sdfat.cpp $SD "$TEENSY/LdrcLink.cpp" "$TEENSY/LinkServer.cpp"
./build/test_sdfat "$@"
