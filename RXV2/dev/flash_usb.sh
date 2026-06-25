#!/usr/bin/env bash
# Flash the latest RXV2 firmware + filesystem onto a fresh XIAO ESP32-S3 over USB.
#
#   dev/flash_usb.sh            flash a board (auto-reset; works for most fresh boards)
#   dev/flash_usb.sh --dance    use AFTER the BOOT/RESET dance (hold B, tap R, release B)
#
# It ALWAYS rebuilds first (incremental, so fast) -> it always flashes the LATEST
# firmware, even right after you edit or bump the version. No flags to remember.
set -e
cd "$(dirname "$0")/.."
PIO="${PIO:-$(command -v pio || echo "$HOME/.platformio/penv/bin/pio")}"
PY="$HOME/.platformio/penv/bin/python"
ESPTOOL="$HOME/.platformio/packages/tool-esptoolpy/esptool.py"
BD=.pio/build/xiao_s3_ota
BOOT_APP0=$(ls "$HOME"/.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin | head -1)
GEN=$(ls "$HOME"/.platformio/packages/framework-arduinoespressif32/tools/gen_esp32part.py | head -1)

BEFORE=default_reset
for a in "$@"; do
  [ "$a" = "--dance" ] && BEFORE=no_reset
done

# Always (re)build first. PlatformIO is incremental, so this is fast when nothing
# changed -- and it GUARANTEES the freshly-edited/-bumped firmware every time.
echo ">> building latest firmware + filesystem ..."
if ! "$PIO" run -e xiao_s3_ota > /tmp/rxv2_flash_build.log 2>&1 \
   || ! "$PIO" run -e xiao_s3_ota -t buildfs >> /tmp/rxv2_flash_build.log 2>&1; then
  echo "!! BUILD FAILED -- fix the firmware. Last lines:"; tail -25 /tmp/rxv2_flash_build.log; exit 1
fi
echo ">> firmware: $(grep -oE 'RXV2-[0-9][0-9.a-z-]+' src/1Defs.h | head -1)"

# Filesystem offset read from the freshly-built partition table (robust to layout changes).
FS_OFFSET=$("$PY" "$GEN" "$BD/partitions.bin" 2>/dev/null | awk -F, '/spiffs|littlefs/{gsub(/[ \t]/,"",$4);print $4;exit}')
[ -z "$FS_OFFSET" ] && FS_OFFSET=0x670000
echo ">> littlefs offset: $FS_OFFSET"

PORT=$(ls /dev/cu.* 2>/dev/null | grep -iE 'usbmodem|usbserial' | head -1 || true)
if [ -z "$PORT" ]; then
  echo "!! no USB port found. Check it's a DATA cable (not charge-only)."
  echo "   A blank XIAO usually auto-appears; otherwise hold B, tap R, release B, then run:"
  echo "      dev/flash_usb.sh --dance"
  exit 1
fi
echo ">> port: $PORT   (reset: $BEFORE)"

if "$PY" "$ESPTOOL" --chip esp32s3 --port "$PORT" --baud 921600 --before "$BEFORE" --after hard_reset --connect-attempts 5 \
     write_flash -z --flash_mode dio --flash_freq 80m --flash_size 8MB \
     0x0 "$BD/bootloader.bin" 0x8000 "$BD/partitions.bin" 0xe000 "$BOOT_APP0" \
     0x10000 "$BD/firmware.bin" "$FS_OFFSET" "$BD/littlefs.bin"; then
  echo ">> DONE - flashed + verified. Board will boot as its LDRC_RX access point."
else
  echo ">> FLASH FAILED."
  echo "   If it said 'No serial data received': hold B, tap R, release B, then run:"
  echo "      dev/flash_usb.sh --dance"
  exit 1
fi
