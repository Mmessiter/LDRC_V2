# LDRC V2 — LockDown Radio Control, Version 2

Private monorepo for the **version-2** hardware and firmware, kept separate from
the version-1 code (which stays in the `LockDownRadioControl` repo).

## Projects

- **RXV2** — the V2 receiver (Seeed XIAO ESP32-S3). Triple-nRF24L01+ diversity,
  CRSF / SBUS / IBUS / PPM output to a flight controller, a WiFi config portal
  with over-the-air updates, and a **"Drive simulator over USB"** mode that turns
  the receiver into a USB HID joystick for a PC flight sim (neXt / RX2SIM). Built
  with PlatformIO (`xiao_s3_ota` / `xiao_s3_usb`).

- **LDRC2SIM** — *retired 2026-09-18, and removed from this tree.* A standalone
  USB flight-sim adapter (XIAO ESP32-S3) that auto-detected CRSF / SBUS / IBUS /
  PPM on one pin and presented an 8-axis USB joystick. The RXV2 dongle now does
  the same job in its **Simulator interface** role — same chip, same decoder
  (`RXV2/src/RcInput.h` is the port), and maintained. The project as it stood is
  at the **`ldrc2sim-final`** tag, and <https://messiter.com/ldrc2sim/> still
  serves updates to anyone running it.

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

## Licence and credits

Free for other flyers, and derivatives must stay free: code is
**GPL-3.0-or-later** (see [LICENSE](LICENSE)); boards CERN-OHL-S-2.0; manuals
CC BY-SA 4.0. Built by Malcolm Messiter with Claude (Anthropic's AI) as pair
programmer. Details in [LICENSING.md](LICENSING.md).
