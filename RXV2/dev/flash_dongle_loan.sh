#!/usr/bin/env bash
# Make a LEND-OUT Rotorflight dongle from a XIAO ESP32-S3 on USB (2026-09-10):
#   dev/flash_dongle_loan.sh "<name>"          e.g. "Dongle 2"
# Like flash_dongle.sh but with NO WiFi credentials baked in: the board runs
# its own hotspot + Bluetooth (the app uses Bluetooth), so a borrower never
# carries our home password and the board never hunts for a network that is
# not there. Uses the images already in .pio/build (build first if stale).
set -e
cd "$(dirname "$0")/.."
NAME="${1:?dongle name}"
PY="$HOME/.platformio/penv/bin/python"
ESPTOOL="$HOME/.platformio/packages/tool-esptoolpy/esptool.py"
BD=.pio/build/xiao_s3_ota
BOOT_APP0=$(ls "$HOME"/.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin | head -1)
echo ">> firmware: $(grep -oE 'RXV2-[0-9][0-9.a-z-]+' src/1Defs.h | head -1)  (images: $(date -r $BD/firmware.bin '+%d %b %H:%M'))"
CSV=$(mktemp /tmp/dongle_nvs.XXXXXX.csv); NVS=$(mktemp /tmp/dongle_nvs.XXXXXX.bin)
printf 'key,type,encoding,value\nrxv2,namespace,,\nnm,data,string,%s\ndongle,data,u8,1\ndbaud,data,u32,115200\n' "$NAME" > "$CSV"
"$PY" -m esp_idf_nvs_partition_gen generate "$CSV" "$NVS" 0x5000 > /dev/null
PORT=$(ls /dev/cu.* 2>/dev/null | grep -iE 'usbmodem|usbserial' | grep -v '3262395A32341' | head -1)
[ -z "$PORT" ] && { echo "!! no XIAO on USB (data cable? hold B, tap R, release B)"; exit 1; }
echo ">> port: $PORT   name: $NAME   wifi: none (hotspot + Bluetooth)"
"$PY" "$ESPTOOL" --chip esp32s3 --port "$PORT" --baud 921600 --before default_reset --after hard_reset --connect-attempts 5 \
  write_flash -z --flash_mode dio --flash_freq 80m --flash_size 8MB \
  0x0 "$BD/bootloader.bin" 0x8000 "$BD/partitions.bin" 0x9000 "$NVS" 0xe000 "$BOOT_APP0" \
  0x10000 "$BD/firmware.bin" 0x670000 "$BD/littlefs.bin" | grep -E 'Hash of data verified|fatal|error'
rm -f "$CSV" "$NVS"
echo ">> flashed. Listening to the boot log for 20 s ..."
sleep 2
"$PY" - "$PORT" <<'PYEOF'
import sys, time, serial
p = sys.argv[1]
try:
    s = serial.Serial(p, 115200, timeout=1)
except Exception as e:
    print("   (no serial log:", e, ")"); sys.exit(0)
t0 = time.time(); seen = []
while time.time() - t0 < 20:
    line = s.readline().decode(errors="replace").strip()
    if line and any(k in line for k in ("Dongle", "dongle", "advertising", "Radios", "boot]", "BLE", "AP mode", "ssid", "Boot")):
        seen.append(line)
for l in seen[:14]: print("   ", l[:110])
if not seen: print("   (board said nothing on USB - normal for a quiet USB; check for the hotspot / Bluetooth name instead)")
PYEOF
echo ">> DONE: '$NAME' is a dongle with no WiFi. Plug it into a Rotorflight port set to MSP 115200 and choose it in the app."
