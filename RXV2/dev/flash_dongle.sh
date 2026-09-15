#!/usr/bin/env bash
# Make a Rotorflight DONGLE out of a XIAO ESP32-S3 on USB, in one go (2026-09-08):
#   dev/flash_dongle.sh "<wifi ssid>" "<wifi password>" ["<name>"]
# Builds the latest firmware + pages, then writes bootloader, partitions, a
# SETTINGS image (WiFi, name, dongle mode ON at 115200), the app and the pages.
# The board boots straight into dongle mode on your WiFi - no app steps.
# Needs: pip install esp-idf-nvs-partition-gen (into ~/.platformio/penv).
set -e
cd "$(dirname "$0")/.."
SSID="${1:?wifi ssid}"; PASS="${2:?wifi password}"; NAME="${3:-Dongle}"
PIO="${PIO:-$(command -v pio || echo "$HOME/.platformio/penv/bin/pio")}"
PY="$HOME/.platformio/penv/bin/python"
ESPTOOL="$HOME/.platformio/packages/tool-esptoolpy/esptool.py"
BD=.pio/build/xiao_s3_ota
BOOT_APP0=$(ls "$HOME"/.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin | head -1)
echo ">> building latest firmware + filesystem ..."
"$PIO" run -e xiao_s3_ota > /tmp/rxv2_dongle_build.log 2>&1 && "$PIO" run -e xiao_s3_ota -t buildfs >> /tmp/rxv2_dongle_build.log 2>&1 || { tail -20 /tmp/rxv2_dongle_build.log; exit 1; }
echo ">> firmware: $(grep -oE 'RXV2-[0-9][0-9.a-z-]+' src/1Defs.h | head -1)"
mkdir -p dev/nvs
CSV=$(mktemp /tmp/dongle_nvs.XXXXXX.csv); NVS=$(mktemp /tmp/dongle_nvs.XXXXXX.bin)
printf 'key,type,encoding,value\nrxv2,namespace,,\nssid,data,string,%s\npass,data,string,%s\nnm,data,string,%s\ndongle,data,u8,1\ndbaud,data,u32,115200\n' "$SSID" "$PASS" "$NAME" > "$CSV"
"$PY" -m esp_idf_nvs_partition_gen generate "$CSV" "$NVS" 0x5000 > /dev/null
PORT=$(ls /dev/cu.* 2>/dev/null | grep -iE 'usbmodem|usbserial' | grep -v '3262395A32341' | head -1)
[ -z "$PORT" ] && { echo "!! no XIAO on USB (data cable? hold B, tap R, release B)"; exit 1; }
echo ">> port: $PORT   name: $NAME   wifi: $SSID"
"$PY" "$ESPTOOL" --chip esp32s3 --port "$PORT" --baud 921600 --before default_reset --after hard_reset --connect-attempts 5 \
  write_flash -z --flash_mode dio --flash_freq 80m --flash_size 8MB \
  0x0 "$BD/bootloader.bin" 0x8000 "$BD/partitions.bin" 0x9000 "$NVS" 0xe000 "$BOOT_APP0" \
  0x10000 "$BD/firmware.bin" 0x670000 "$BD/littlefs.bin" | grep -E 'Hash of data verified|fatal|error'
rm -f "$CSV" "$NVS"
echo ">> DONE: the board boots as '$NAME' in dongle mode on '$SSID'."
echo "   Wire 5V, GND, D5<-FC TX, D6->FC RX to a UART set to MSP 115200."
echo "   If you also run a USB-C cable to the FC, D5/D6 become a fallback (USB wins),"
echo "   and the 5V MUST come from the flight controller - the dongle drives VBUS down"
echo "   that cable, so a separate supply would meet the FC's own 5V through it."
