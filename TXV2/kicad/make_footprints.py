#!/usr/bin/env python3
# TXV2.pretty socket footprints — plain 2.54 mm through-hole grids.
# Teensy/DevKitC/nRF24 geometry is standard; the Pololu 2808 and buck
# grids are PROVISIONAL until measured against Malcolm's real modules.
import uuid, os

OUT = os.path.expanduser("~/Documents/KiCad/TXV2_MAIN/TXV2.pretty")
os.makedirs(OUT, exist_ok=True)
def U(): return str(uuid.uuid4())

def pad(num, x, y, first=False):
    shape = "rect" if first else "circle"
    return (f'\t(pad "{num}" thru_hole {shape} (at {x} {y}) (size 1.7 1.7) '
            f'(drill 1.0) (layers "*.Cu" "*.Mask") (remove_unused_layers no) (uuid "{U()}"))')

def footprint(name, descr, pads, outline):
    x0 = min(p[1] for p in pads) - 1.6; x1 = max(p[1] for p in pads) + 1.6
    y0 = min(p[2] for p in pads) - 1.6; y1 = max(p[2] for p in pads) + 1.6
    ptxt = "\n".join(pad(n, x, y, first=(str(n) == "1")) for n, x, y in pads)
    body = f'''(footprint "{name}"
	(version 20260206)
	(generator "make_footprints")
	(generator_version "10.0")
	(layer "F.Cu")
	(attr through_hole)
	(property "Reference" "REF**" (at {round((x0+x1)/2,2)} {y0 - 1.6} 0) (layer "F.SilkS") (uuid "{U()}") (effects (font (size 1 1) (thickness 0.15))))
	(property "Value" "{name}" (at {round((x0+x1)/2,2)} {y1 + 1.6} 0) (layer "F.Fab") (uuid "{U()}") (effects (font (size 1 1) (thickness 0.15))))
	(property "Footprint" "" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid "{U()}") (effects (font (size 1.27 1.27))))
	(property "Datasheet" "" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid "{U()}") (effects (font (size 1.27 1.27))))
	(property "Description" "{descr}" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid "{U()}") (effects (font (size 1.27 1.27))))
	(fp_rect (start {round(x0,2)} {round(y0,2)}) (end {round(x1,2)} {round(y1,2)}) (stroke (width 0.12) (type solid)) (fill no) (layer "F.SilkS") (uuid "{U()}"))
	(fp_rect (start {round(x0-0.25,2)} {round(y0-0.25,2)}) (end {round(x1+0.25,2)} {round(y1+0.25,2)}) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd") (uuid "{U()}"))
{ptxt}
)'''
    open(f"{OUT}/{name}.kicad_mod", "w").write(body)
    print("wrote", name)

# Teensy 4.1 socket: 2 x 24, 15.24 mm row spacing, symbol pins 1-24 left / 25-48 right
pads = [(i + 1, 0.0, round(i * 2.54, 2)) for i in range(24)] + \
       [(i + 25, 15.24, round(i * 2.54, 2)) for i in range(24)]
footprint("Teensy41_Socket", "Teensy 4.1 in machined-pin sockets, 0.6in rows, pin1=GND top-left (USB end up)", pads, None)

# ESP32-S3-DevKitC-1 socket: 2 x 22, 22.86 mm row spacing (J1 left 1-22, J3 right 23-44)
pads = [(i + 1, 0.0, round(i * 2.54, 2)) for i in range(22)] + \
       [(i + 23, 22.86, round(i * 2.54, 2)) for i in range(22)]
footprint("DevKitC1_Socket", "ESP32-S3-DevKitC-1U in sockets; J1 pin1 (3V3) top-left, USB end up", pads, None)

# nRF24 PA/LNA socket: 2 x 4, pins 1|2 / 3|4 / 5|6 / 7|8 top-down
pads = [(1, 0, 0), (2, 2.54, 0), (3, 0, 2.54), (4, 2.54, 2.54),
        (5, 0, 5.08), (6, 2.54, 5.08), (7, 0, 7.62), (8, 2.54, 7.62)]
footprint("NRF24_Socket_2x4", "nRF24L01+PA/LNA 2x4 socket, pin1=GND (square)", pads, None)

# Pololu 2808 socket — PROVISIONAL grid, verify vs the real module
pads = [(1, 0, 0), (2, 0, 2.54), (3, 0, 5.08),                     # VIN GND VOUT
        (4, 15.24, 0), (5, 15.24, 2.54), (6, 15.24, 5.08),         # A B ON
        (7, 15.24, 7.62), (8, 15.24, 10.16)]                       # OFF CTRL
footprint("Pololu2808_Socket", "PROVISIONAL - measure the real Pololu 2808 hole grid before fab", pads, None)

# 5V buck module socket — PROVISIONAL 1x4 (VIN GND VOUT EN), verify vs the real module
pads = [(1, 0, 0), (2, 2.54, 0), (3, 5.08, 0), (4, 7.62, 0)]
footprint("Buck5V_Socket", "PROVISIONAL - match the chosen buck module (e.g. Pololu D24V22F5) before fab", pads, None)

# ── 3-pin buck-boost regulator (Pololu, 7805-style: VIN GND VOUT inline) ──
pads = [(1, 0, 0), (2, 2.54, 0), (3, 5.08, 0)]   # VIN, GND, VOUT
footprint("Buck3pin_VGV", "Pololu buck-boost 3-pin: 1=VIN 2=GND 3=VOUT (7805 pinout)", pads, None)

# ── Pololu 2808 PSW03C: 2 rows x 7, 2.54mm pitch, 10.16mm (0.4in) rows ──
# TOP row (pins 1-7):  VIN VIN GND GND ON OFF CTRL
# BOT row (pins 8-14): VOUT VOUT GND GND - - -
pads = [(i + 1, i * 2.54, 0) for i in range(7)] + \
       [(i + 8, i * 2.54, 10.16) for i in range(7)]
footprint("Pololu2808_PSW03C", "Pololu 2808 PSW03C 2x7 - VERIFY ROW SPACING 10.16mm by paper test-fit", pads, None)
