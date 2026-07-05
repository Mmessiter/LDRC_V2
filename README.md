# LDRC V2 — LockDown Radio Control, Version 2

Private monorepo for the **version-2** hardware and firmware, kept separate from
the version-1 code (which stays in the `LockDownRadioControl` repo).

## Projects

- **RXV2** — the V2 receiver (Seeed XIAO ESP32-S3). Triple-nRF24L01+ diversity,
  CRSF / SBUS / IBUS / PPM output to a flight controller, a WiFi config portal
  with over-the-air updates, and a **"Drive simulator over USB"** mode that turns
  the receiver into a USB HID joystick for a PC flight sim (neXt / RX2SIM). Built
  with PlatformIO (`xiao_s3_ota` / `xiao_s3_usb`).

- **LDRC2SIM** — a standalone USB flight-sim adapter (XIAO ESP32-S3): auto-detects
  CRSF / SBUS / IBUS / PPM on one pin and presents an 8-axis USB joystick, with a
  WiFi portal and OTA updates from messiter.com. Built with PlatformIO.

- **RXV2App** — iOS app that configures the receiver over **Bluetooth LE**
  (no WiFi network-switching on the phone). It shows the receiver's own web
  UI in a WebView with the static pages bundled in-app; only the JSON/POST
  calls cross BLE, served by the same firmware handlers as the portal.
  Built with xcodegen + Xcode; runs on-device with a free Apple ID.

- **TXV2** — the V2 transmitter. **Not started yet** (placeholder — first
  job is to freeze the rev-A PCB design).

## Notes

- Build each subproject with PlatformIO; see its own `README` / `RESUME` for details.
- Build output (`.pio/`), IDE caches and `.DS_Store` are gitignored. The
  messiter.com FTP password (`dev/ftp_credentials.sh`) is gitignored and must
  never be committed.
- LDRC2SIM's pre-V2 local git history (it was a standalone repo before this
  monorepo) was preserved as `LDRC2SIM_pre-v2_history.bundle` outside this tree.
