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
| 6 | Link handshake A | moved from 24; (JR-bay PPM dropped — wireless buddy replaced it) |
| 7 (RX2) | **ESP32-S3 link RX** | Serial2 @ 2 Mbaud |
| 8 (TX2) | **ESP32-S3 link TX** | |
| 9 | nRF24 CE | |
| 10 | nRF24 CSN | |
| 11/12/13 | SPI MOSI/MISO/SCK | |
| 14–17 (A0–A3) | Gimbal axes CH1–4 | |
| 18/19 | I2C SDA/SCL | INA219 battery monitor + expansion header |
| 20–23 (A6–A9) | Knobs/sliders CH5–8 | |
| 24 (A10) | **Battery voltage divider** | 47k/15k from the switched rail (INA219 dropped 2026-07-19) |
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

- Battery → soft-latch (**Pololu 2808 PSW03C**, 2x7 pin grid) → VBAT_SW.
- **TWO Pololu buck-boost 5V regulators** (3-pin, 7805 pinout
  VIN/GND/VOUT; buck-boost so they hold 5 V even as the pack sags
  below 5 V) fed in parallel from VBAT_SW (Malcolm 2026-07-20):
  - **Buck-N -> +5V_NEXT: Nextion display ONLY** (isolates display
    switching noise from the RF/logic supply).
  - **Buck-M -> +5V: Teensy, DevKitC, servos rail, WS2812, LEDs.**
- Separate 3.3 V rail for the radio (AMS1117 from +5V); each processor
  board uses its own on-board 3.3 V regulator.

**Soft-power wiring (2808 PSW03C — CONFIRM against V1 before fab):**
top row VIN VIN GND GND ON OFF CTRL; bottom row VOUT VOUT GND GND.
VIN<-VBAT_RAW, VOUT->VBAT_SW, GND. Proposed: button (J_BTN) between
VBAT_RAW and ON (press = turn on); OFF<-Teensy pin5 LATCH_OFF (MCU
shutdown); Teensy pin4 senses the button via a 47k/15k divider off the
ON node; CTRL to a test pad. Row spacing 10.16mm to be confirmed by
1:1 paper test-fit.
- **Crash-proof power-off (Malcolm 2026-08-03):** the graceful off runs
  through the Teensy, so a crashed program strands the vandal button (and
  the 2808's own hardware button is buried by the flip-mount). Fit a small
  RECESSED pinhole button on the case wired to the 2808's **A/B button
  pads** — a pure-hardware power toggle, code not consulted. Recessing
  (pen-tip access) makes accidental in-flight presses impossible. Hierarchy:
  vandal press = graceful software off with countdown; hung code = watchdog
  reboot (DelayWithDog); all else = the pinhole. Add 1x miniature momentary
  button to the shopping list.
- Battery voltage via **47k/15k divider** from the switched rail into
  Teensy pin 24/A10 (Malcolm 2026-07-19: INA219 dropped; no current
  readout — the BQ25887 ADC reports pack/per-cell volts while charging).
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
| I2C expansion | **Qwiic (JST-SH 1.0 mm)** + XH 4-pin twin | Qwiic opens the whole plug-and-play sensor ecosystem; XH twin for hand-made looms |
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

## Rev-A erratum 1 — Pololu 2808 footprint mirrored (2026-07-25)

The 2808 pad grid on Rev-A boards is a mirror image of the real module.
**Two equivalent rescues (no respin)** — a mirror is cured either by the
board's other face or by flipping the module; both are the same reflection:

**A (preferred, Malcolm 2026-08-03): TOP side, module UPSIDE-DOWN on
headers.** The 6+7 keying still admits only the correct orientation (the
flipped-on-top presentation is geometrically identical to right-side-up
underneath). Components hang downward with ~8 mm header clearance — nothing
touches. The on-board switch/button faces the PCB and is inaccessible: set
it ON before installation (the vandal button on BTN is the power control).
Bonus: the board underside stays flat — **no 6 mm standoffs needed**.

**B (original): board UNDERSIDE, right-side-up**, flush on plain male pins;
requires the 6 mm standoffs (~5.5 mm module below the board; the USB case
slot absorbs the 1 mm shift).

Either way, before first power-up: continuity-beep VIN/GND from the XT30 to
the module — the ten-second test that beats every mirror.

## Rev-A erratum 2 — ESP32 "< USB end" silkscreen is BACKWARDS (2026-07-25)

Full footprint mirror audit (prompted by erratum 1) of every socket on
Rev-A, each checked against its official pin card / datasheet drawing:

| Part | Verdict |
|---|---|
| Teensy 4.1 socket (U1) | ✅ CORRECT — matches PJRC card; silk arrows ("USB v", "microSD ^") right |
| ESP32-S3-DevKitC socket (U2) | ⚠️ pads/nets CORRECT, **silk arrow WRONG** — see below |
| nRF24 E01-ML01DP5 socket (U3) | ✅ CORRECT — matches EBYTE mechanical drawing; square pad = GND, antenna exits LEFT |
| Pololu 2808 (U4) | erratum 1 (underside mount rescue) |
| 2× 3-pin bucks (U5/U9) | ✅ IN/GND/OUT silk labels match nets; insert per labels |
| XT30 (J3) | ✅ pad 2 = keyed '+' = VBAT_RAW (the 2026-07-21 fix is in the fabbed file; no stray polarity silk) |
| BQ25887 / USB-C / AMS1117 (back side) | ✅ standard KiCad library footprints — cannot be hand-mirrored |

**The erratum:** the fabbed silk near the TOP of the ESP32 socket reads
"< USB end". That is BACKWARDS. Pad 1 (top, y102 end, next to the nRF
corner) carries 3V3 — and on the real DevKitC-1 the 3V3/RST pins are at
the **ANTENNA** end (official Espressif pin layout, verified against the
v1.1 figure). The 5V + GND pins are at the USB end.

**Correct insertion: ANTENNA toward the board's top edge (same edge the
E01 overhangs), the two USB-C connectors toward the Teensy.** If inserted
per the silk, +5V lands on GPIO43 (TX) and the module's 3V3 pins are
grounded — likely fatal to the DevKitC.

Assembly-day safeguards:
1. Scratch out / sharpie over the "< USB end" text; write "ANTENNA ^".
2. Before seating the module, meter socket pad 21 (left column, 2nd from
   bottom, net +5V) and confirm it will meet the module pin silk-labelled
   "5V" (2nd from bottom on the module's 3V3-row side… i.e. simply: the
   module's 5V pin must be at the BOTTOM end).
3. nRF24 quick check after insertion: SMA shell ↔ socket square pad
   (pin 1) must beep (both GND).

Rev-B: fix the silk text in generate_pcb.py (move "USB end" to the y155
end or replace with "ANTENNA" at y102).

## Rev-A erratum 3 — VBAT_SENSE shorted to GND on the back copper (found 2026-09-06)

A fresh `kicad-cli pcb drc` on the fabbed `TXV2_MAIN.kicad_pcb` (same
mtime as the gerbers) reports one **tracks_crossing** error, and the copper
confirms it: on **B.Cu** the VBAT_SENSE track (Teensy pin 24 → the 47k/15k
divider) runs along y = 120.25 mm and crosses the short GND stub that
joins **C1 pad 2** (the 1 µF VBUS cap, at 130.4/121.05) to a GND via at
130.66/119.55. They intersect at **(130.54, 120.25)** — a hard short. The
July-22 DRC had the same error; it was missed. Effect: the Teensy would
read the battery as 0 V forever (nothing burns: 47k to ground).

**Fix on every board before assembly — two scalpel cuts, no wire:** cut
the GND stub either side of the crossing (at about y = 120.6 and
y = 119.9, i.e. between C1's ground pad and the crossing, and between the
crossing and the via). C1 keeps its ground through the zone's thermal
spokes; the via is a plain stitch via. **Verify:** R16 pad 1 (or Teensy
socket pad 16 / pin 24) to GND must read ~15 kΩ, not 0 Ω; C1 pad 2 to GND
must still beep.

Rev-B: move the VBAT_SENSE route (or the C1 ground stub) in
generate_pcb.py and make `tracks_crossing` a hard stop in the verify step.

## Rev-B (2026-09-06) — the three errata fixed, plus small improvements

Built from the fabbed Rev-A board file by `kicad/revB/make_revb.sh`
(surgical edits with KiCad's Python API, then DRC-gated track widening,
export, render). Not a re-route: everything that was proven on Rev-A is
byte-identical except the items below. DRC clean (the same ten
cosmetic "starved thermal" notes as Rev-A; no crossings, no clearance
errors, no unconnected copper). Files: `kicad/revB/TXV2_MAIN_revB.kicad_pcb`,
`kicad/revB/TXV2_MAIN_revB_gerbers.zip` (JLCPCB: 4-layer, 1.6 mm, same
outline), renders `revB_top.png` / `revB_bottom.png`.

1. **Erratum 1 fixed — Pololu 2808 (U4) un-mirrored.** The two pin rows
   swap: the 7-pin row (VIN VIN GND GND ON OFF CTRL) is now the row
   nearer the board's bottom edge, the 6-pin row (VOUT VOUT GND GND A B)
   the upper one. **Mount the module right-side-up on the TOP, on
   headers, VIN row at the bottom (silk says so).** Its own switch and
   button now face up. Standoffs can go back to ~5 mm. Five nets were
   re-routed locally: VBAT_RAW, VBAT_SW (via a new In2 climb + one via),
   PWR_A, LATCH_OFF, and SW2 (its diagonal ran through the new CTRL
   hole; it now detours south of the row).
2. **Erratum 3 fixed — VBAT_SENSE no longer crosses C1's ground stub.**
   The sense track now passes over the top of that ground via (the stub
   is C1's only ground, fenced in by the sense track and GIMBAL3, so it
   stays). No cuts needed on Rev-B.
3. **Erratum 2 fixed — silk.** "ANTENNA end ^" at the DevKitC's pin-1
   end, "USB end v" at the other. Revision text "TXV2 Revision B 2026-09".
4. **C12 added: 10 µF (0805, 25 V) input capacitor for the AMS1117**
   (U8), between its IN (+5V) and GND pins. The RF regulator had none.
5. **Power tracks widened 0.2 → 0.4 mm where the board allows** —
   43 of the 108 VBAT_RAW / VBAT_SW / +5V / +5V_NEXT / +3V3_RF segments;
   the rest stay 0.2 mm where they squeeze past pads (all DRC-clean).
6. BOM: D3/D4 as SMA Schottky (SS14) rather than 1N4001 type (lower drop
   on the 2808's A pin); everything else unchanged.

**Case:** TXV16's 6 mm bosses and the pinhole for the 2808's A/B stubs
were placed for the upside-down/underside module — with the module
right-side-up on top, re-check the pinhole position and the boss height
before printing the next case.

Not changed on purpose: the Teensy VBAT (RTC) still needs the flying lead
from J14; the WS2812 is still driven by 3.3 V logic (a Schottky in its 5 V
feed cures flicker if seen); gimbal PH-3 order remains +3V3 / signal / GND.

**Rev-B silkscreen pass (2026-09-06, "abundantly clear which component goes
where and which way round"):** every small label raised to ≥0.6 mm / 0.12 mm
stroke (the Rev-A 0.45 mm labels are near the printable limit); the 2808
socket carries its pin names on both rows (VIN VIN GND GND ON OFF CTRL below,
VOUT VOUT GND GND A B above) plus "2808 right way up"; C12 labelled "C12
10uF"; the charger chip's pin 1 spelled out beside the footprint's own
corner mark; D3/D4 read "SS14"; back-side value labels moved off pad edges
(no silk-over-copper left); the LED "+" marks confirmed beside the anode
pads and the CR2032 / 220 µF / RTC "+" marks checked. What silk cannot show:
the modules' orientation is by text ("ANTENNA end ^", "USB end v", "microSD
end ^", "USB (program) v", "square pad = GND", "E01 antenna overhang ^") and
by the square pad-1 on each socket.
