#!/usr/bin/env bash
# Commission a fresh RECEIVER from a XIAO ESP32-S3 on USB, in one go
# (2026-09-14). Malcolm has five helicopters flying, two test rigs and "at
# least another half a dozen helicopters waiting to have our system installed",
# so each new board wants to arrive named, on the WiFi, and current:
#
#   dev/flash_receiver.sh "<wifi ssid>" "<wifi password>" "<model name>"
#
# Builds the latest firmware + pages, then writes bootloader, partitions, a
# SETTINGS image (WiFi + the model's name), the app and the pages. The board
# comes up on your network under that name, ready to bind - and from then on
# the fleet watcher and the app both keep it up to date by themselves.
#
# Dongle mode is deliberately NOT set: a board with transceivers works itself
# out as a receiver. See dev/flash_dongle.sh for the dongle version.
# Needs: pip install esp-idf-nvs-partition-gen (into ~/.platformio/penv).
set -e
cd "$(dirname "$0")/.."
SSID="${1:?wifi ssid}"; PASS="${2:?wifi password}"; NAME="${3:?a name for this model, e.g. Goblin770}"
PIO="${PIO:-$(command -v pio || echo "$HOME/.platformio/penv/bin/pio")}"
PY="$HOME/.platformio/penv/bin/python"
ESPTOOL="$HOME/.platformio/packages/tool-esptoolpy/esptool.py"
BD=.pio/build/xiao_s3_ota
BOOT_APP0=$(ls "$HOME"/.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin | head -1)
echo ">> building latest firmware + filesystem ..."
"$PIO" run -e xiao_s3_ota > /tmp/rxv2_receiver_build.log 2>&1 && "$PIO" run -e xiao_s3_ota -t buildfs >> /tmp/rxv2_receiver_build.log 2>&1 || { tail -20 /tmp/rxv2_receiver_build.log; exit 1; }
echo ">> firmware: $(grep -oE 'RXV2-[0-9][0-9.a-z-]+' src/1Defs.h | head -1)"
mkdir -p dev/nvs
CSV=$(mktemp /tmp/receiver_nvs.XXXXXX.csv); NVS=$(mktemp /tmp/receiver_nvs.XXXXXX.bin)
printf 'key,type,encoding,value\nrxv2,namespace,,\nssid,data,string,%s\npass,data,string,%s\nnm,data,string,%s\n' "$SSID" "$PASS" "$NAME" > "$CSV"
"$PY" -m esp_idf_nvs_partition_gen generate "$CSV" "$NVS" 0x5000 > /dev/null
PORT=$(ls /dev/cu.* 2>/dev/null | grep -iE 'usbmodem|usbserial' | grep -v '3262395A32341' | head -1)
[ -z "$PORT" ] && { echo "!! no XIAO on USB (data cable? hold B, tap R, release B)"; exit 1; }
echo ">> port: $PORT   receiver name: $NAME   wifi: $SSID"
"$PY" "$ESPTOOL" --chip esp32s3 --port "$PORT" --baud 921600 --before default_reset --after hard_reset --connect-attempts 5 \
  write_flash -z --flash_mode dio --flash_freq 80m --flash_size 8MB \
  0x0 "$BD/bootloader.bin" 0x8000 "$BD/partitions.bin" 0x9000 "$NVS" 0xe000 "$BOOT_APP0" \
  0x10000 "$BD/firmware.bin" 0x670000 "$BD/littlefs.bin" | grep -E 'Hash of data verified|fatal|error'
rm -f "$CSV" "$NVS"
echo ">> DONE: '$NAME' will come up on '$SSID'."
echo "   Next: bind it to the transmitter, then wire D6 -> the flight controller's"
echo "   CRSF RX (and a short USB-C data cable to the FC for everything else)."
echo "   It keeps itself updated from messiter.com from now on."
