# TXV2 rev-A — hardware specification (draft for sign-off)

The V2 transmitter: **Teensy 4.1** does everything fast and physical
(RC link, sticks, switches, display, SD, power); **ESP32-S3** is the
connectivity co-processor (WiFi web portal, Bluetooth LE for the phone
app, OTA for both processors). No breadboard phase — this document
freezes the connections so rev-A PCB layout and software can start at
once. Both processors are SOCKETED on rev-A: replaceable, USB
accessible, no reflow needed.

## Processor choices

### ESP32-S3 — **ESP32-S3-DevKitC-1U-N16R8** (socketed, 2×22 headers)
- Carries the **ESP32-S3-WROOM-1U-N16R8** module: 16 MB flash, 8 MB
  (octal) PSRAM — the largest mainstream S3 configuration; plenty for
  the web portal + BLE bridge + OTA staging of both firmwares.
- **-1U = u.FL external antenna.** RXV2 taught us the desense lesson:
  the WiFi/BLE whip mounts away from the nRF24 PAs.
- DevKitC exposes every module GPIO, has EN/BOOT buttons (the S3
  bootloader quirk we met on RXV2 is a button-press away, never a
  crisis) and TWO USB-C ports (UART console + native USB/JTAG).
- rev-B production swaps in the bare WROOM-1U-N16R8 module — firmware
  unchanged.
- (Considered: WROOM-2 N32R16V — more flash/PSRAM but patchier
  availability and tooling; N16R8 is the sweet spot. Revisit at rev-B.)

### Teensy 4.1 (socketed, edge pins 0–41 + power)
Same part as V1 — six years of proven code. Bottom pads (48–54) are
not available in a socket, so the budget is edge pins only.

## Teensy 4.1 pin map (rev-A)

| Pin | Function | Notes |
|-----|----------|-------|
| 0 (RX1) | Nextion TX | Serial1 @ 921600, as V1 |
| 1 (TX1) | Nextion RX | |
| 2 | **WS2812 status LED chain** | one pin drives any number of RGB LEDs (V1 used 3 pins) |
| 3 | Buzzer / spare PWM | reserved |
| 4 | **Power-button sense** | V1 pin 33 |
| 5 | Power-latch OFF (Pololu 2808) | as V1 |
| 6 | JR-bay PPM out | reserved, optional bay |
| 7 (RX2) | **ESP32-S3 link RX** | Serial2 @ 2 Mbaud |
| 8 (TX2) | **ESP32-S3 link TX** | |
| 9 | nRF24 **#1 CE** | |
| 10 | nRF24 **#1 CSN** | |
| 11/12/13 | SPI MOSI/MISO/SCK | shared by both radios |
| 14–17 (A0–A3) | Gimbal axes CH1–4 | |
| 18/19 | I2C SDA/SCL | INA219 battery monitor + expansion header |
| 20–23 (A6–A9) | Knobs/sliders CH5–8 | |
| 24 | Link handshake A | ESP32→Teensy "ready/busy" |
| 25 | Link handshake B | Teensy→ESP32 "attention" |
| 26–33 | **Switches ×8** | V1 had 25–32; shifted one |
| 34–41 | **Trim contacts ×8** | populated — hardware trims confirmed |

Every edge pin allocated; pin 3 is the single spare (buzzer optional).

## ESP32-S3 pin usage (DevKitC-1U)

| GPIO | Function |
|------|----------|
| 17 (U1RXD) | Link RX ← Teensy TX2 |
| 18 (U1TXD) | Link TX → Teensy RX2 |
| 8 | Link handshake A (ESP→Teensy "busy/ready") |
| 9 | Link handshake B (Teensy→ESP "attention") |
| 38 | On-board RGB LED (DevKitC) — link/portal status |
| — | All remaining GPIOs to a labelled spare header |

Strapping pins (0, 3, 45, 46) left unconnected. The S3's own USB-C
ports face an access cutout: development flashing without opening the
case (and the RXV2 USB-trap lesson documented: after esptool over USB,
tap EN).

## Inter-processor protocol (design intent)

- UART, 2 Mbaud, framed packets (COBS or length-prefixed + CRC16).
- Teensy → ESP32: live state (channels, telemetry, battery, model
  info) at ~50 Hz; replies to config reads.
- ESP32 → Teensy: config writes from web/BLE UI, model selection,
  bind commands.
- **OTA for BOTH processors**: ESP32 updates itself (as RXV2 does);
  for the Teensy, ESP32 downloads the .hex, streams it over the link,
  and the Teensy self-reflashes with **FlasherX** — the whole
  transmitter updates from the phone, no cables.
- The web/BLE UI reuses the RXV2 architecture wholesale: same
  HTTP-over-BLE bridge, same page framework, same iPhone app pattern
  (the app already scans by service UUID — a TXV2 service joins it).

## Radio

- **One nRF24L01+PA+LNA module, socketed**, SMA/RP-SMA to the case —
  as V1 (Malcolm's call: RX-side dual diversity already covers it).
- The radio gets its **own 3.3 V regulator** (PA modules are hungry
  and noise-sensitive) with generous bulk capacitance; its antenna
  separated from the ESP32's u.FL whip.

## Power

- Battery → soft-latch (Pololu 2808 pattern, as V1) → 5 V buck
  (socketed module) → Teensy VIN + DevKitC 5V.
- Separate 3.3 V rail for the radios (above); each processor board
  uses its own on-board 3.3 V regulator.
- **INA219** on I2C measures battery voltage + current (as V1).
- **2S Li-ion, charged externally** (Malcolm's call): XT30/XT60 or
  barrel input on the case, balance charging outside the transmitter.
  No charger circuitry on the PCB.

## Retained from V1

- **Same Nextion display as V1** (Serial1 @ 921600 — zero display-code
  changes), built-in SD on the Teensy, sounds via display, JR module
  bay (PPM reserved on pin 6), I2C expansion for future sensors.

## Decisions (Malcolm, 2026-07-06)

1. **Display** — same Nextion as V1.
2. **Radio** — one, as V1.
3. **Trims** — hardware trims stay, all 8 populated.
4. **Battery** — 2S Li-ion, external charging, no onboard charger.

---
*rev-A draft 2026-07-06 — written with Claude during the RXV2 BLE
bring-up session; pin map derived from V1 TransmitterCode main.cpp
and 1Definitions.h.*
