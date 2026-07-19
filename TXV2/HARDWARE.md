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
| 6 | spare | JR-bay PPM dropped 2026-07-19 — module + buddy pins unused on V1, wireless buddy-box replaced them |
| 7 (RX2) | **ESP32-S3 link RX** | Serial2 @ 2 Mbaud |
| 8 (TX2) | **ESP32-S3 link TX** | |
| 9 | nRF24 CE | |
| 10 | nRF24 CSN | |
| 11/12/13 | SPI MOSI/MISO/SCK | |
| 14–17 (A0–A3) | Gimbal axes CH1–4 | |
| 18/19 | I2C SDA/SCL | INA219 battery monitor + expansion header |
| 20–23 (A6–A9) | Knobs/sliders CH5–8 | |
| 24 | Link handshake A | ESP32→Teensy "ready/busy" |
| 25 | Link handshake B | Teensy→ESP32 "attention" |
| 26–33 | **Switches ×8** | V1 had 25–32; shifted one |
| 34–41 | **Trim contacts ×8** | populated — hardware trims confirmed |

Every edge pin allocated; pins 3 and 6 are the spares (buzzer optional).

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

## Connectors (rev-A standard — goodbye DuPont)

V1's DuPont headers work but don't lock, don't polarise, and creep
loose. Rev-A standardises on ONE lockable family for every panel loom:

| What | Connector | Why |
|------|-----------|-----|
| Gimbals (per gimbal loom) | **JST-XH** (2.5 mm) | polarised + friction-locked, sturdy, easy to crimp or buy pre-crimped; the RC-world workhorse |
| Switches ×8 loom | **JST-XH** | same family everywhere = one crimper, one housing stock |
| Trims ×8 loom | **JST-XH** | |
| Power button + latch | **JST-XH** 2/3-pin | |
| Nextion display | **5-pin 0.1" header, V1 order** (GND, skip, 5V, RX, TX) | the V1 loom doubles as the FTDI-upload lead (skip = FTDI CTS, DTR left outside the housing) — deliberate Dupont survivor, do not convert to XH |
| Battery (2S Li-ion) | **XT30** | polarised, solid, the RC standard for this current class |
| I2C expansion | **Qwiic (JST-SH 1.0 mm)** + XH 4-pin twin | Qwiic opens the whole plug-and-play sensor ecosystem (INA219 boards included); XH twin for hand-made looms |
| nRF24 PA/LNA module | 2×4 socket, direct | no loom — module seats on the PCB |
| Teensy 4.1 / DevKitC | machined-pin sockets | replaceable processors |

Premium alternative if positive latching is wanted: **JST-GH**
(1.25 mm, the Pixhawk standard — pre-crimped cables everywhere).
Suggested tooling either way: Engineer PA-09 crimper, or simply buy
pre-crimped XH leads and solder the loose ends at the panel parts.

## Status LEDs — two truth-tellers

V1's RGB semantics stay: **blue = booting/processing, red = trying to
connect, green = connected.** Rev-A improves on it by letting each
processor tell its own truth:

1. **Primary panel LED = WS2812 chain on Teensy pin 2** — shows the
   RC-link state exactly as V1 did (the Teensy owns that link, so this
   LED never lies, even if the ESP32 is rebooting). One pin, and the
   "chain" means we can add a second pixel later without wiring.
2. **ESP32 DevKitC's onboard addressable RGB** (Malcolm spotted it!) —
   shows WiFi/BLE/portal state (blue booting, red portal down, green
   app/browser connected). The DevKitC mounts so this LED is visible
   through a small window or a cheap 3 mm **light pipe** to the panel.
   NB the onboard pixel is GPIO48 on DevKitC v1.0 and GPIO38 on v1.1 —
   firmware handles both via a build flag.

If a single visible LED is preferred later, the Teensy chain can mirror
ESP32 status sent over the link — but two honest lights beat one
occasionally-lying light.

## Retained from V1

- **Same Nextion display as V1** (Serial1 @ 921600 — zero display-code
  changes), built-in SD on the Teensy, sounds via display, I2C
  expansion for future sensors. NOT retained (2026-07-19): the JR
  module bay and buddy port — both unused on V1, and buddy-boxing is
  wireless now.

## Decisions (Malcolm, 2026-07-06)

1. **Display** — same Nextion as V1.
2. **Radio** — one, as V1.
3. **Trims** — hardware trims stay, all 8 populated.
4. **Battery** — 2S Li-ion, external charging, no onboard charger.
   *(superseded by the amendment below — APPROVED by Malcolm 2026-07-19)*

## Amendment — on-board USB-C balance charging (APPROVED 2026-07-19)

Replaces decision 4. **BQ25887** (TI, QFN-24) on the main PCB: a
standalone 2-cell boost charger running from a USB-C 5 V socket —
CC/CV with termination, ~1.5 A charge, **built-in cell balancing**
through the pack's centre tap, safety timer, battery OVP, thermal
shutdown, optional pack NTC. It charges autonomously — no firmware
involvement needed for safety — so a hung Teensy can never spoil a
charge.

**The reason it moved on-board (Malcolm's insight):** the BQ25887 has
I2C + a telemetry ADC. On the shared I2C bus (Teensy pins 18/19, with
the INA219) the Teensy can read per-cell voltages and charge current
and show on the Nextion: live cell volts, estimated time to full, and
a "battery tired — cells won't balance" warning when the cells sit
persistently apart. The switcher only runs while charging (never in
flight), so the RF-noise objection evaporates.

Additions to the board: USB-C 16-pin receptacle (charge-only, 5.1 k
CC pulldowns) facing a case cutout; BQ25887 + 1 uH IHLP-2020 inductor
+ small passives; balance tap = 3rd wire on the battery loom (XT30
stays for the main pair; centre tap joins the power-button/aux XH loom
or its own XH-2); amber CHARGE LED next to the USB socket (on =
charging, off = full, blink = fault) — Nextion shows the detail.
Circuit lifted from the proven Balancer 5 Click reference (values
verified against TI datasheet + slua938).

A standalone copy of the same circuit can become a tiny spare-pack
charger board later — same design, transplanted.

---
*rev-A draft 2026-07-06 — written with Claude during the RXV2 BLE
bring-up session; pin map derived from V1 TransmitterCode main.cpp
and 1Definitions.h. Charging amendment drafted 2026-07-19.*
