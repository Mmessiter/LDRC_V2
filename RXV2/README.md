# The Version 2 receiver

The Version 2 receiver is a **Seeed XIAO ESP32-S3** with one to three **nRF24L01+ radio
modules** (Ebyte ML01SP4, or any 2.4 GHz nRF24 module) for antenna diversity. It binds to a
Version 1 or Version 2 transmitter exactly as the Version 1 receiver does, and adds what
that one could not do:

- It drives a flight controller over **CRSF, SBUS, IBUS or PPM**, and brings Rotorflight
  telemetry (battery, head speed, ESC temperature and more) back to the transmitter.
- It has a **WiFi portal** and talks to the **phone app over Bluetooth**, which set up
  **Rotorflight** on the flight controller in plain English: rates, PIDs, governor, mixer,
  backups on the phone, flight recordings, black box checks.
- It **updates itself over the air** from [messiter.com/rxv2/release](https://messiter.com/rxv2/release/),
  from the app, or through a Version 2 transmitter.
- The same board, without radio modules, is a **dongle**: Rotorflight from your phone on
  any helicopter, whatever radio flies it. And a **simulator interface**: a receiver of
  almost any make on one pin becomes a USB joystick for RealFlight or neXt.

The user guide, the dongle, and the one-click flash in the browser are at
[messiter.com/rotorflight](https://messiter.com/rotorflight/). This README is for building
from source.

## What is in this folder

| | |
|---|---|
| `src/` | The firmware: the radio link (`1Defs.h`, the radios), the flight-controller output, MSP to Rotorflight, the web and Bluetooth bridges, the sim-over-USB joystick |
| `data/` | The web pages, served by the receiver and bundled in the apps; written to the chip's LittleFS |
| `lib/` | Libraries kept with the project |
| `kicad/dongle/` | A carrier board for the dongle (its first batch had an error; the dongle is now a bare XIAO and four wires) |
| `dev/` | Tools: `flash_usb.sh` and `flash_receiver.sh` for a fresh board, `release.sh` for a release, the host tests (`*_test.js`, `*_test.cpp`), `stage_fs.py` (compresses the pages into the filesystem image) |
| `Connections.txt` | The wiring of the radio modules and the flight controller |
| `*.md` | Specifications worked out along the way: the black box format, MSP details, the ESC telemetry |

## Build and flash, once

Install [PlatformIO](https://platformio.org/) and Node.js (the page tests and the build's
gates use it). The XIAO on USB:

```
cd RXV2
dev/flash_usb.sh
```

That builds the firmware and the pages and writes bootloader, partitions, firmware and
filesystem. By hand it is `pio run -e xiao_s3_usb -t upload` and
`pio run -e xiao_s3_usb -t uploadfs`. A fresh board that will not take the first flash
wants the BOOT/RESET dance: hold BOOT, tap RESET, let go, then `dev/flash_usb.sh --dance`.

`dev/flash_receiver.sh "<ssid>" "<password>" "<model name>"` does the same and also writes
the WiFi network and the model's name, so the board comes up on your network ready to bind.

**Wiring** is in [Connections.txt](Connections.txt): the three radio modules share SPI and
each has its own CE and CSN pair; the flight controller is on D5 (telemetry in) and D6
(SBUS, CRSF, IBUS or PPM out). Fit one, two or three modules; the firmware finds them.

**First start.** A fresh receiver calls itself *Untitled* and makes a WiFi access point of
that name, with the portal at its address; or install the app, which finds it over
Bluetooth. Give it a name and your WiFi there, and it updates itself from then on. Bind it
from the transmitter as a Version 1 receiver is bound.

## Tests

The host tests run on a Mac or Linux without a board: `dev/page_test.js`,
`dev/replay_test.js`, `dev/bbcheck_test.sh`, `dev/prelink_hold_test.sh` and their
neighbours in `dev/`. `dev/release.sh` runs all of them before anything is published.

## Licence

Code GPL-3.0-or-later, boards CERN-OHL-S-2.0, pages and help CC BY-SA 4.0:
[../LICENSING.md](../LICENSING.md). Copyright (C) 2026 Malcolm Messiter.
