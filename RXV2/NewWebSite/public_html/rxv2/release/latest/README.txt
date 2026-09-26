These five files flash a bare Seeed XIAO ESP32-S3 into an LDRC dongle or receiver.
Build: RXV2-0.9.859-startup-is-only-the-first-stir

esptool write_flash offsets:
  0x0       bootloader.bin
  0x8000    partitions.bin
  0xe000    boot_app0.bin
  0x10000   firmware.bin
  0x670000  littlefs.bin

Instructions: https://messiter.com/rotorflight/dongle.html#firmware
