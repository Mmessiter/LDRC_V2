#!/bin/bash
# Pull the screen's core dump through the door and decode it against the firmware's ELF.
#   coredump.sh <last byte of the IP> <screen version, e.g. 1.11.179-full>
ip=${1:?ip}; ver=${2:?version}; SC="$(dirname "$0")"
ELF=~/Documents/GitHub/TXV1B/dev/out/elf/screen-$ver.elf
[ -f "$ELF" ] || { echo "no ELF $ELF"; exit 2; }
G=$(find ~/.platformio/packages -maxdepth 3 -name "xtensa-esp32s3-elf-gdb" | head -1); [ -n "$G" ] || { echo "no xtensa gdb"; exit 3; }
export PATH="$(dirname "$G"):$PATH"
curl -s -m 30 "http://192.168.1.$ip/coredump" -o "$SC/coredump_$ip.bin" || exit 4
echo "dump: $(wc -c < "$SC/coredump_$ip.bin") bytes, sha $(shasum -a 256 "$SC/coredump_$ip.bin" | cut -c1-16)"
~/.platformio/penv/bin/esp-coredump info_corefile -t raw -c "$SC/coredump_$ip.bin" "$ELF" > "$SC/coredump_$ip.txt" 2>&1
echo "decoded to $SC/coredump_$ip.txt ($(wc -l < "$SC/coredump_$ip.txt") lines)"
grep -n -A28 "Crashed task\|==================== CURRENT THREAD STACK\|Core dump\|PC\b" "$SC/coredump_$ip.txt" | head -60
