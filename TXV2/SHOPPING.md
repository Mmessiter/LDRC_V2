# TXV2 rev-A — shopping list

Prices are rough GBP; sources are the usual UK-friendly ones.
(The PCB itself gets ordered from JLCPCB once the layout is done —
not on this list yet.)

## Buy now — the new-for-V2 parts

| Item | Qty | ~£ | Where / notes |
|------|-----|----|---------------|
| **ESP32-S3-DevKitC-1U-N16R8** (genuine Espressif) | 2 | 14 ea | Mouser / Farnell / DigiKey. Must be **-1U** (u.FL socket) and **N16R8** (16 MB flash + 8 MB PSRAM). Clones often lie about PSRAM — buy genuine. Two: one to use, one spare/dev. |
| 2.4 GHz antenna, RP-SMA, + **u.FL→RP-SMA pigtail** | 2 sets | 4 | For the DevKitC's external antenna; any WiFi stubby is fine |
| **Pololu 2808** pushbutton power switch | 2 | 5 ea | Technobots / HobbyTronics UK carry Pololu; same part as V1 |
| **Pololu D24V50F5** 5 V 5 A step-down | 1–2 | 12 ea | Powers Teensy + DevKitC + Nextion with headroom; socketed on the PCB |
| **Pololu D24V10F3** 3.3 V step-down (radio's private rail) | 1–2 | 6 ea | The PA/LNA radio gets its own clean supply — RXV2 desense lesson |
| **JST-XH assortment kit** (2/3/4/5-pin housings, PCB headers, pre-crimped 20–30 cm leads) | 1 kit | 12 | Amazon/AliExpress "JST-XH kit 2.54". Pre-crimped leads spare you the crimping |
| **XT30 connector pairs** | 5 pairs | 5 | Battery in-line |
| **Qwiic / JST-SH 4-pin cables** | 3 | 5 | The Pi Hut / Pimoroni — I2C expansion |
| **INA219 breakout** (Qwiic version if possible) | 1–2 | 5 ea | Adafruit original or SparkFun Qwiic; battery volts/amps as V1 |
| **WS2812 through-hole 5 mm NeoPixel** (or 8 mm) | pack of 10 | 6 | The panel status LED chain, Teensy pin 2 |
| 3 mm **light pipe**, panel mount | pack | 4 | Brings the DevKitC's onboard pixel to the case front |
| **Machined-pin (round) socket strips** 2.54 mm | 10 strips | 8 | Sockets for Teensy (2×24), DevKitC (2×22), buck modules |
| 2×4 socket for nRF24 module | 3 | 3 | The radio seats here |
| **Engineer PA-09 crimper** (optional if using pre-crimped leads) | 1 | 40 | The one crimper that actually works for XH/PH/GH |
| Electrolytic caps 470–1000 µF low-ESR, 6.3–10 V | few | 3 | Radio rail bulk capacitance (if not in stock) |

**Rough total: £120–170** depending on spares and whether the crimper
joins the family.

## Probably already in your stock (check before buying)

| Item | Notes |
|------|-------|
| **Teensy 4.1** | Same as V1 — if no spare on the shelf: ~£30, The Pi Hut / Cool Components |
| **nRF24L01+PA+LNA module** + SMA antenna | V1/RXV2 stock |
| **Nextion display** | Same model as V1 — you have the fleet |
| Toggle switches ×8, pot knobs ×4 | V1 pattern |
| Trim buttons/rockers ×8 | As V1 wired them |
| Momentary power button | Drives the Pololu 2808 |
| 2S Li-ion pack + external charger | Your chosen arrangement |
| Hook-up wire, heatshrink, M3 standoffs | The usual |

## DECIDE FIRST — the one open item

**Gimbals.** V1 used potentiometer joysticks. For V2 the choice shapes
panel cutouts and the ADC wiring, so it must be settled before pcbnew:

- **Reuse/salvage V1-style pot gimbals** — zero surprises, the ADC
  code carries over.
- **Upgrade to hall-effect gimbals** (e.g. RadioMaster AG01, FrSky
  M9/M10) — smoother, no pot wear, still analogue out (same 3-wire
  ADC interface, so the pin map is unchanged either way). ~£30–60/pair.

Both work with the frozen pin map — it only changes what we buy and
the mounting holes we draw.

---
*Companion to HARDWARE.md — rev-A, 2026-07-06.*
