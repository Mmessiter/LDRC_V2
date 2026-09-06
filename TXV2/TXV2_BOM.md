# TXV2 Revision A — Bill of Materials (shopping list)
*by Claude and Malcolm — July 2026 · quantities are PER BOARD*

## Modules (plug into sockets)
| Qty | Part | Notes |
|---|---|---|
| 1 | **Teensy 4.1** | PJRC — the main MCU |
| 1 | **ESP32-S3-DevKitC-1** (N16R8) | WiFi / BLE sidecar — OTA + phone config. **MUST be DevKitC-1 format**: 2×22 pins, rows 22.86 mm apart, board ~25.5 mm — order official Espressif `ESP32-S3-DevKitC-1-N16R8`; some clones are wider and don't fit (verified on the 1:1 print, 2026-07-24) |
| 1 | **EBYTE E01-ML01DP5** (nRF24L01+ PA/LNA, SMA) | the RF link module you already use |
| 1 | **Pololu 2808** (PSW03C push-button power switch) | soft power latch |
| 2 | **Pololu 5V buck-boost regulator** (7805 pinout: VIN/GND/VOUT) | one for Nextion, one for everything else |

## Sockets & headers (solder to board)
| Qty | Part | For |
|---|---|---|
| 2 | 24-pin machined/female header strip (2.54mm) | Teensy 4.1 |
| 2 | 22-pin female header strip | ESP32 DevKitC |
| 1 | 2×4 female header | nRF24 module |
| 1 | 7-pin + 1 | 6-pin female strip (or cut from stock) | Pololu 2808 (keyed 6+7) |
| 2 | 3-pin female strip | the two bucks |
| 2 | 1×12 pin header (male, 2.54mm) | ESP spare GPIO A/B |
| 1 | 1×5 pin header (male) | Nextion / FTDI lead (V1 style) |

## Connectors
| Qty | Part | For |
|---|---|---|
| 1 | **AMASS XT30U-F** (female, PCB vertical) | battery |
| 3 | JST-XH 2-pin vertical | BAL · BTN · RTC |
| 2 | JST-XH 3-pin | RGB LED · TX MODULE (JR bay) |
| 1 | JST-XH 4-pin | I2C |
| 4 | **JST-PH 3-pin (B3B-PH-K)** | gimbal axes — the M9 plugs click straight in |
| 1 | JST-XH 6-pin | KNOBS |
| 2 | JST-XH 9-pin | SWITCHES · TRIMS |
| 1 | JST-SH 4-pin (BM04B-SRSS-TB) | QWIIC I2C |
| 1 | **USB-C 16-pin receptacle** (HRO TYPE-C-31-M-12) | charging |
| 1 | CR2032 holder, vertical (Panasonic VS1N style) + CR2032 cell | Teensy clock backup |
| — | matching JST-XH housings + crimp pins for the looms | |

## Charger circuit (hand-solder SMD, back side)
| Qty | Part | Ref |
|---|---|---|
| 1 | **TI BQ25887RGER** (VQFN-24) | U7 — 2-cell charger + balancer |
| 1 | **1µH power inductor, Vishay IHLP-2020** (≥3A) | L1 |
| 1 | AMS1117-3.3 (SOT-223) | U8 — nRF 3.3V rail |

## Diodes & LEDs
| Qty | Part | Ref |
|---|---|---|
| 2 | **Schottky in SMA package (SS14 / 1N5819W)** — Rev-B choice; 1N4001-type works too | D3, D4 — soft-power OR (low drop on the 2808's A pin) |
| 2 | 0805 LED (suggest green + amber) | D1 PWR, D2 CHG |
| 1 | WS2812 RGB LED (panel-mount / breakout with 3-wire lead) | the status light |

## Capacitors
| Qty | Value | Size | Ref |
|---|---|---|---|
| 3 | 10µF 25V | 1206 | C2 C3 C4 (PMID/BAT) |
| 1 | 10µF | 1206 | C9 (RF rail) |
| 1 | 10µF 25V | 0805 | **C12 (AMS1117 input) — Rev-B only** |
| 1 | 1µF | 0805 | C1 (VBUS) |
| 1 | 4.7µF | 0805 | C7 (REGN) |
| 1 | 47nF | 0805 | C6 (BTST) |
| 1 | 47pF | 0805 | C5 |
| 2 | 100nF | 0805 | C10, C11 |
| 1 | 220µF electrolytic SMD (6.3mm can) | — | C8 (RF bulk) |

## Resistors
| Qty | Value | Size | Ref |
|---|---|---|---|
| 2 | 68R | 1206 | R2 R3 (balance, parallel pair) |
| 2 | 330R | 0805 | R1 (MID), R14 (WS2812 data) |
| 1 | 374R | 0805 | R6 (ILIM) |
| 2 | 470R | 0805 | R9 R10 (LEDs) |
| 1 | 5.11k | 0805 | R4 (TS upper) |
| 1 | 7.5k | 0805 | R5 (TS lower) |
| 2 | 5.1k | 0805 | R7 R8 (USB-C CC) |
| 2 | 4.7k | 0805 | R12 R13 (I2C pullups) |
| 1 | 47k | 0805 | R15 (VBAT divider) |
| 1 | 15k | 0805 | R16 (VBAT divider) |

## Off-board
- RadioMaster 2S 5000mAh pack (male XT30) — you have it
- Nextion NX8048P050 display — from V1
- 16mm vandal momentary button — the power button
- Gimbals / knobs / switches / trims — from the V1 hardware plan
- M3 standoffs ×4 (~5mm) — as V1

## The board itself
**JLCPCB: 4-layer, 1.6mm, 83.3 × 91.7mm, qty 100** — upload `TXV2_MAIN_gerbers.zip` (Rev-A, in hand) or `kicad/revB/TXV2_MAIN_revB_gerbers.zip` (Rev-B, 2026-09-06: errata 1-3 fixed, C12 added, power tracks widened), defaults for everything else.
