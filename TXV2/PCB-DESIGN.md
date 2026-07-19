# TXV2 rev-A main board — PCB design brief

Companion to HARDWARE.md (the electrical spec). This captures the
mechanical facts and placement plan agreed 2026-07-19, from Malcolm's
V1 board photos + measurements. The new board drops into the V1 case.

## Mechanical

- **Outline:** 83.3 × 91.7 mm rectangle (width × height as viewed with
  the Nextion connector on the right, matching the V1 photo).
- **Mounting holes:** 4× M3 at the corners, **76.0 mm apart across ×
  84.3 mm apart vertically** → each hole centre inset 3.65 mm from the
  side edges and 3.7 mm from top/bottom.
- **Standoffs:** ~5 mm today, giving usable clearance for components
  on the BACK of the board (V1 already does this: SMD passives + power
  diodes live underneath). Height can be raised with a small 3D-print
  edit if we ever need more.
- Height budget: back side ≤ ~4 mm (SMD, inductors, small clusters);
  top side unlimited within the case (sockets, modules, connectors).

## Placement plan (from the V1 board, so existing looms reach)

| Region | Contents |
|---|---|
| Right edge | Nextion XH-4 |
| Lower-left | Battery XT30 + INA219 socket + power chain (latch, buck) |
| Bottom edge | Power-button XH, GND test point |
| Top edge | JR module bay pins, buddy XH |
| Centre field | Teensy 4.1 socket (orthogonal, not V1's diagonal), DevKitC socket, trims/switches/channels XH looms |
| Top-right area | nRF24 PA/LNA socket, SMA pigtail toward case wall, its 3.3 V regulator |
| Back side | Charger cluster (BQ25887 + inductor + passives) near the battery corner; decoupling under sockets |
| Case wall (TBC) | **USB-C charge socket + amber CHARGE LED — position awaiting Malcolm's decision** (bottom edge near battery corner suggested) |

USB access cutouts for Teensy USB and the DevKitC's two USB-C ports:
orientation to be chosen with the sockets so the cutouts land on a
reachable case wall (V1 precedent: development access without full
disassembly).

## Sequence (agreed)

1. **Schematic** — generated from HARDWARE.md's frozen pin map +
   the approved charging amendment; ERC-clean; PDF for Malcolm's
   sign-off. ← next step
2. **Placement** — footprints inside the 83.3 × 91.7 outline per the
   table above; render for approval against the case BEFORE routing.
3. **Routing + DRC + schematic-parity**, then gerbers for JLC.

Toolchain: same generator-script + kicad-cli verify pipeline proven on
the RXV2 VBAT divider paddle (see ~/Documents/KiCad/RXV2_VDIV).

## Notes carried from the photos

- V1 rear side hosts: 1N4001s, 1N5406s, 330 µF, 10 µF, 100 nF/4.7 µF
  clusters — precedent for under-board population.
- V1's TinyRTC (DS1307) and 7805 do NOT carry over: Teensy 4.1's
  built-in RTC + a CR2032 holder replaces the former; the socketed
  5 V buck module replaces the latter.
