#!/usr/bin/env python3
# TXV2 rev-A main board — schematic generator.
# Sources of truth: netlist.py (this dir) + TXV2/HARDWARE.md.
# Style: every pin gets a short stub + local label; blocks are placed on
# a loose grid. All inter-block connectivity is by net label, which keeps
# a 200-pin schematic generatable and ERC-clean.
import re, uuid, os

SY = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"
OUT = os.path.expanduser("~/Documents/KiCad/TXV2_MAIN/TXV2_MAIN.kicad_sch")

def U(): return str(uuid.uuid4())

# stable uuids
SCH = {}
ufile = os.path.expanduser("~/Documents/KiCad/TXV2_MAIN/uuids.txt")
if os.path.exists(ufile):
    for line in open(ufile):
        k, v = line.split()
        SCH[k] = v
def uid(key):
    if key not in SCH:
        SCH[key] = U()
    return SCH[key]

def match_paren(s, i):
    d = 0
    for j in range(i, len(s)):
        if s[j] == '(': d += 1
        elif s[j] == ')':
            d -= 1
            if d == 0: return j
    raise ValueError

def extract_symbol(lib, name):
    s = open(f"{SY}/{lib}.kicad_sym", encoding="utf-8").read()
    m = re.search(r'\(symbol\s+"%s"' % re.escape(name), s)
    j = match_paren(s, m.start())
    block = s[m.start():j+1]
    return block.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)

# ── custom box symbols ─────────────────────────────────────────────
def box_symbol(name, left, right, width=30.48):
    """left/right: list of (pinnum, pinname). Pins on 2.54 grid."""
    n = max(len(left), len(right))
    half_h = (n + 1) * 2.54 / 2
    hw = width / 2
    pins = []
    for i, (num, nm) in enumerate(left):
        y = half_h - (i + 1) * 2.54
        pins.append((num, nm, -hw - 2.54, y, 0))
    for i, (num, nm) in enumerate(right):
        y = half_h - (i + 1) * 2.54
        pins.append((num, nm, hw + 2.54, y, 180))
    ptxt = "\n".join(f'''			(pin passive line
				(at {x} {y} {ang})
				(length 2.54)
				(name "{nm}" (effects (font (size 1.0 1.0))))
				(number "{num}" (effects (font (size 1.0 1.0))))
			)''' for num, nm, x, y, ang in pins)
    return (f'''		(symbol "TXV2:{name}"
			(pin_numbers (hide yes))
			(pin_names (offset 0.508))
			(exclude_from_sim no)
			(in_bom yes)
			(on_board yes)
			(property "Reference" "U" (at 0 {half_h + 1.5} 0) (effects (font (size 1.27 1.27))))
			(property "Value" "{name}" (at 0 {-half_h - 1.8} 0) (effects (font (size 1.27 1.27))))
			(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27))) (hide yes))
			(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27))) (hide yes))
			(property "Description" "" (at 0 0 0) (effects (font (size 1.27 1.27))) (hide yes))
			(symbol "{name}_0_1"
				(rectangle (start {-hw} {half_h}) (end {hw} {-half_h})
					(stroke (width 0.254) (type default)) (fill (type background)))
{ptxt}
			)
		)''', {num: (x, y, ang) for num, nm, x, y, ang in pins})

# ── module pin tables (VERIFIED) ───────────────────────────────────
import importlib.util
spec = importlib.util.spec_from_file_location("netlist", os.path.expanduser("~/Documents/KiCad/TXV2_MAIN/netlist.py"))
NL = importlib.util.module_from_spec(spec); spec.loader.exec_module(NL)

# Teensy 4.1 edge order, PJRC card11a rev4 (USB end = top of symbol).
TEENSY_LEFT = ["GND","0","1","2","3","4","5","6","7","8","9","10","11","12",
               "3V3","24","25","26","27","28","29","30","31","32"]
TEENSY_RIGHT = ["VIN","GND2","3V3_2","23","22","21","20","19","18","17","16","15","14","13",
                "GND3","41","40","39","38","37","36","35","34","33"]

def teensy_net(label):
    if label in ("GND", "GND2", "GND3"): return "GND"
    if label == "4": return "PWRBTN"        # sense shares the button junction net
    if label in ("3V3", "3V3_2"): return "+3V3_T"
    if label == "VIN": return "+5V"
    return NL.TEENSY[label]

# ESP32-S3-DevKitC-1 v1.1 headers, Espressif user guide.
DEVKIT_J1 = ["3V3","3V3_B","EN","G4","G5","G6","G7","G15","G16","G17","G18",
             "G8","G3","G46","G9","G10","G11","G12","G13","G14","5V","GNDA"]
DEVKIT_J3 = ["GNDB","TX","RX","G1","G2","G42","G41","G40","G39","G38","G37",
             "G36","G35","G0","G45","G48","G47","G21","G20","G19","GNDC","GNDD"]

def devkit_net(label):
    NC = {"EN", "TX", "RX", "G35", "G36", "G37", "G0", "G19", "G20", "G38"}
    if label in NC: return None   # EN/console/RGB on the DevKitC itself; 35-37 = octal PSRAM; 19/20 = USB; 0 = boot strap
    m = {"3V3": "ESP_3V3", "3V3_B": "ESP_3V3",
         "5V": "+5V", "GNDA": "GND", "GNDB": "GND", "GNDC": "GND", "GNDD": "GND",
         "G17": "LINK_TX2",   # U1RXD <- Teensy TX2
         "G18": "LINK_RX2",   # U1TXD -> Teensy RX2
         "G8": "HANDSHAKE_A", "G9": "HANDSHAKE_B",
         }
    if label in m: return m[label]
    return "ESP_" + label          # spare GPIOs -> labelled nets -> spare headers

BQ_LEFT = [("23","VBUS"),("24","PSEL"),("21","PMID"),("22","PMID2"),
           ("17","SW"),("18","SW2"),("12","BTST"),("11","REGN"),
           ("4","SDA"),("5","SCL"),("6","INT")]
BQ_RIGHT = [("13","BAT"),("14","BAT2"),("15","SNS"),("16","SNS2"),
            ("9","MID"),("10","CBSET"),("1","PG"),("2","STAT"),
            ("7","TS"),("8","ILIM"),("3","CD"),("24x","PSEL_dup")]  # placeholder fixed below

# (PSEL already on left; right column ends with grounds)
BQ_RIGHT = [("13","BAT"),("14","BAT2"),("15","SNS"),("16","SNS2"),
            ("9","MID"),("10","CBSET"),("1","PG"),("2","STAT"),
            ("7","TS"),("8","ILIM"),("3","CD"),("19","GND"),("20","GND2"),("25","PAD")]

# ── build lib_symbols ──────────────────────────────────────────────
lib_parts = {}
pinmaps = {}
for name, L, R, w in [
    ("TEENSY41", [(str(i+1), n) for i, n in enumerate(TEENSY_LEFT)],
                 [(str(i+25), n) for i, n in enumerate(TEENSY_RIGHT)], 33.02),
    ("ESP32_DEVKITC", [(str(i+1), n) for i, n in enumerate(DEVKIT_J1)],
                      [(str(i+23), n) for i, n in enumerate(DEVKIT_J3)], 33.02),
    ("NRF24_SOCKET", [("1","GND"),("3","CE"),("5","SCK"),("7","MISO")],
                     [("2","VCC"),("4","CSN"),("6","MOSI"),("8","IRQ")], 20.32),
    ("POLOLU_2808", [("1","VIN"),("2","GND"),("3","VOUT")],
                    [("4","A"),("5","B"),("6","ON"),("7","OFF"),("8","CTRL")], 22.86),
    ("BUCK_5V", [("1","VIN"),("2","GND")], [("3","VOUT"),("4","EN")], 17.78),
    ("REG_3V3", [("3","VIN"),("1","GND")], [("2","VOUT")], 17.78),
    ("BQ25887", BQ_LEFT, BQ_RIGHT, 27.94),
]:
    text, pm = box_symbol(name, L, R, w)
    lib_parts[name] = text
    pinmaps[name] = pm

LIBSYMS = {
    "Device:R": extract_symbol("Device", "R"),
    "Device:C": extract_symbol("Device", "C"),
    "Device:C_Polarized": extract_symbol("Device", "C_Polarized"),
    "Device:L": extract_symbol("Device", "L"),
    "Device:LED": extract_symbol("Device", "LED"),
    "Device:Battery_Cell": extract_symbol("Device", "Battery_Cell"),
    "Connector:USB_C_Receptacle_USB2.0_16P": extract_symbol("Connector", "USB_C_Receptacle_USB2.0_16P"),
    "power:GND": extract_symbol("power", "GND"),
    "power:PWR_FLAG": extract_symbol("power", "PWR_FLAG"),
}
for n in ["Conn_01x02","Conn_01x03","Conn_01x04","Conn_01x05","Conn_01x06","Conn_01x09","Conn_01x12"]:
    LIBSYMS[f"Connector_Generic:{n}"] = extract_symbol("Connector_Generic", n)

def lib_pins(libblock):
    pins = {}
    for m in re.finditer(r'\(pin\s+\S+\s+\S+\s*\n?\s*\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)', libblock):
        seg = libblock[m.start():]
        nm = re.search(r'\(number\s+"([^"]+)"', seg[:700])
        if nm:
            pins[nm.group(1)] = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
    return pins

LIBPINS = {k: lib_pins(v) for k, v in LIBSYMS.items()}

def pin_pos(sym_at, rot, px, py):
    x, y = px, -py
    if rot == 0:    rx, ry = x, y
    elif rot == 90: rx, ry = y, -x
    elif rot == 180: rx, ry = -x, -y
    elif rot == 270: rx, ry = -y, x
    return (round(sym_at[0] + rx, 3), round(sym_at[1] + ry, 3))

# ── emit helpers ───────────────────────────────────────────────────
body = []

def wire(a, b):
    body.append(f'\t(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid "{U()}"))')

def label(text, p, rot=0, just="left bottom"):
    body.append(f'\t(label "{text}" (at {p[0]} {p[1]} {rot}) (effects (font (size 1.0 1.0)) (justify {just})) (uuid "{U()}"))')

def prop(name, val, x, y, hide=False, size=1.27):
    h = "\n\t\t\t(hide yes)" if hide else ""
    return (f'\t\t(property "{name}" "{val}"\n\t\t\t(at {x} {y} 0){h}\n'
            f'\t\t\t(effects (font (size {size} {size})))\n\t\t)')

def snap(v): return round(round(v / 1.27) * 1.27, 2)

def instance(lib_id, ref, value, at, rot, footprint, key, pinnums,
             ref_off=(0, -3), val_off=(0, 3), descr=""):
    px, py = snap(at[0]), snap(at[1])
    pins = "\n".join(f'\t\t(pin "{n}" (uuid "{U()}"))' for n in pinnums)
    body.append(f'''	(symbol
		(lib_id "{lib_id}")
		(at {px} {py} {rot})
		(unit 1)
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
		(dnp no)
		(uuid "{uid(key)}")
{prop("Reference", ref, px + ref_off[0], py + ref_off[1])}
{prop("Value", value, px + val_off[0], py + val_off[1])}
{prop("Footprint", footprint, px, py, hide=True)}
{prop("Datasheet", "", px, py, hide=True)}
{prop("Description", descr, px, py, hide=True)}
{pins}
		(instances (project "TXV2_MAIN" (path "/{uid('ROOT')}" (reference "{ref}") (unit 1))))
	)''')

def no_connect(p):
    body.append(f'\t(no_connect (at {p[0]} {p[1]}) (uuid "{U()}"))')

def stub_and_label(p, ang, net):
    """2.54 stub outward from pin at angle ang (pin's own angle: 0=points right into symbol => stub goes LEFT)."""
    if ang == 0:      q = (p[0] - 2.54, p[1]); just = "right bottom"
    elif ang == 180:  q = (p[0] + 2.54, p[1]); just = "left bottom"
    elif ang == 90:   q = (p[0], p[1] + 2.54); just = "left bottom"
    else:             q = (p[0], p[1] - 2.54); just = "left bottom"
    wire(p, q)
    label(net, q, 0, just)

def place_box(name, ref, value, key, at, netfn, footprint):
    at = (snap(at[0]), snap(at[1]))
    pm = pinmaps[name]
    half_h = max(abs(y) for (_, y, _) in pm.values()) + 2.54
    instance(f"TXV2:{name}", ref, value, at, 0, footprint, key, list(pm.keys()),
             ref_off=(0, -half_h - 2.5), val_off=(0, half_h + 2.5))
    for num, (px, py, ang) in pm.items():
        p = pin_pos(at, 0, px, py)
        net = netfn(num)
        if net is None:
            no_connect(p)
            continue
        stub_and_label(p, ang, net)

# ── PLACE THE BLOCKS ───────────────────────────────────────────────
# Teensy
def teensy_netfn(num):
    i = int(num)
    lbl = TEENSY_LEFT[i - 1] if i <= 24 else TEENSY_RIGHT[i - 25]
    return teensy_net(lbl)
place_box("TEENSY41", "U1", "Teensy 4.1 (socket)", "U1", (80, 100), teensy_netfn, "TXV2:Teensy41_Socket")

# DevKitC
def devkit_netfn(num):
    i = int(num)
    lbl = DEVKIT_J1[i - 1] if i <= 22 else DEVKIT_J3[i - 23]
    return devkit_net(lbl)
place_box("ESP32_DEVKITC", "U2", "ESP32-S3-DevKitC-1U (socket)", "U2", (170, 100), devkit_netfn, "TXV2:DevKitC1_Socket")

# nRF24 socket
NRF_NET = {"1": "GND", "2": "+3V3_RF", "3": "NRF_CE", "4": "NRF_CSN",
           "5": "SPI_SCK", "6": "SPI_MOSI", "7": "SPI_MISO", "8": None}
place_box("NRF24_SOCKET", "U3", "nRF24L01+PA/LNA (socket)", "U3", (250, 60), lambda n: NRF_NET[n], "TXV2:NRF24_Socket_2x4")

# Pololu 2808 latch
P2808_NET = {"1": "VBAT_RAW", "2": "GND", "3": "VBAT_SW",
             "4": "PWRBTN", "5": None, "6": None, "7": "LATCH_OFF", "8": None}
place_box("POLOLU_2808", "U4", "Pololu 2808 latch (socket)", "U4", (250, 105), lambda n: P2808_NET[n], "TXV2:Pololu2808_Socket")

# Buck module
BUCK_NET = {"1": "VBAT_SW", "2": "GND", "3": "+5V", "4": None}
place_box("BUCK_5V", "U5", "5V buck module (socket)", "U5", (250, 140), lambda n: BUCK_NET[n], "TXV2:Buck5V_Socket")

# BQ25887 charger
BQ_NET = {"23": "VBUS_USB", "24": "GND", "21": "PMID", "22": "PMID",
          "17": "SW_CHG", "18": "SW_CHG", "12": "BTST", "11": "REGN",
          "4": "I2C_SDA", "5": "I2C_SCL", "6": None,
          "13": "VBAT_RAW", "14": "VBAT_RAW", "15": "VBAT_RAW", "16": "VBAT_RAW",
          "9": "MID_SENSE", "10": "CB_PATH", "1": None, "2": "CHG_STAT",
          "7": "CHG_TS", "8": "CHG_ILIM", "3": "GND", "19": "GND", "20": "GND", "25": "GND"}
place_box("BQ25887", "U7", "BQ25887 charger", "U7", (95, 205), lambda n: BQ_NET[n], "Package_DFN_QFN:HVQFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm_ThermalVias")

# ── generic 2-pin part placer (R/C/L/LED etc) ─────────────────────
def two_pin(lib_id, ref, value, key, at, net1, net2, footprint, vertical=True, descr=""):
    at = (snap(at[0]), snap(at[1]))
    rot = 0 if vertical else 90
    pins = LIBPINS[lib_id]
    instance(lib_id, ref, value, at, rot, footprint, key, ["1", "2"],
             ref_off=(-4, 0), val_off=(3.2, 0), descr=descr)
    for num, net in [("1", net1), ("2", net2)]:
        px, py, pang = pins[num]
        p = pin_pos(at, rot, px, py)
        ang = (pang + rot) % 360
        stub_and_label(p, (ang + 180) % 360, net)   # stub continues outward beyond pin end

R0805 = "Resistor_SMD:R_0805_2012Metric"
R1206 = "Resistor_SMD:R_1206_3216Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
LED0805 = "LED_SMD:LED_0805_2012Metric"

# Charger passives (Balancer 5 Click values, verified)
X0 = 150
two_pin("Device:L", "L1", "1uH IHLP-2020", "L1", (X0, 190), "PMID", "SW_CHG", "Inductor_SMD:L_Vishay_IHLP-2020", False)
two_pin("Device:C", "C1", "1uF 25V", "C1", (X0, 200), "VBUS_USB", "GND", C0805)
two_pin("Device:C", "C2", "10uF 25V", "C2", (X0 + 15, 200), "PMID", "GND", C1206)
two_pin("Device:C", "C3", "10uF 25V", "C3", (X0 + 30, 200), "PMID", "GND", C1206)
two_pin("Device:C", "C4", "10uF 16V", "C4", (X0 + 45, 200), "VBAT_RAW", "GND", C1206)
two_pin("Device:C", "C5", "47pF", "C5", (X0 + 60, 200), "VBAT_RAW", "GND", C0805)
two_pin("Device:C", "C6", "47nF", "C6", (X0, 212), "BTST", "SW_CHG", C0805)
two_pin("Device:C", "C7", "4.7uF", "C7", (X0 + 15, 212), "REGN", "GND", C0805)
two_pin("Device:R", "R1", "330R", "R1", (X0 + 30, 212), "MID_SENSE", "CELL_MID", R0805)
two_pin("Device:R", "R2", "68R", "R2", (X0 + 45, 212), "CB_PATH", "CELL_MID", R1206)
two_pin("Device:R", "R3", "68R", "R3", (X0 + 60, 212), "CB_PATH", "CELL_MID", R1206)
two_pin("Device:R", "R4", "5.11k", "R4", (X0, 224), "REGN", "CHG_TS", R0805)
two_pin("Device:R", "R5", "7.5k", "R5", (X0 + 15, 224), "CHG_TS", "GND", R0805, descr="30k if pack NTC fitted")
two_pin("Device:R", "R6", "374R", "R6", (X0 + 30, 224), "CHG_ILIM", "GND", R0805)
two_pin("Device:R", "R7", "5.1k", "R7", (X0 + 45, 224), "USB_CC1", "GND", R0805)
two_pin("Device:R", "R8", "5.1k", "R8", (X0 + 60, 224), "USB_CC2", "GND", R0805)
two_pin("Device:R", "R9", "470R", "R9", (X0, 236), "VBUS_USB", "LED_PWR_A", R0805)
two_pin("Device:LED", "D1", "green PWR", "D1", (X0 + 15, 236), "LED_PWR_A", "GND", LED0805)
two_pin("Device:R", "R10", "470R", "R10", (X0 + 30, 236), "VBUS_USB", "LED_CHG_A", R0805)
two_pin("Device:LED", "D2", "amber CHG", "D2", (X0 + 45, 236), "LED_CHG_A", "CHG_STAT", LED0805)
# I2C pull-ups on the 3.3V bus
two_pin("Device:R", "R12", "4.7k", "R12", (X0, 248), "+3V3_T", "I2C_SDA", R0805)
two_pin("Device:R", "R13", "4.7k", "R13", (X0 + 15, 248), "+3V3_T", "I2C_SCL", R0805)
# WS2812 data series resistor
two_pin("Device:R", "R14", "330R", "R14", (X0 + 30, 248), "WS2812_DATA", "WS2812_OUT", R0805)
# nRF24 rail bulk
two_pin("Device:C_Polarized", "C8", "220uF 10V", "C8", (X0 + 45, 248), "+3V3_RF", "GND", "Capacitor_SMD:CP_Elec_6.3x7.7")
two_pin("Device:C", "C9", "10uF 16V", "C9", (X0 + 60, 248), "+3V3_RF", "GND", C1206)
two_pin("Device:C", "C10", "100nF", "C10", (X0 + 75, 248), "+3V3_RF", "GND", C0805)
# battery voltage divider: VBAT_SW -> 47k -> VBAT_SENSE (Teensy A10) -> 15k -> GND
two_pin("Device:R", "R15", "47k", "R15", (X0 + 115, 200), "VBAT_SW", "VBAT_SENSE", R0805)
two_pin("Device:R", "R16", "15k", "R16", (X0 + 115, 212), "VBAT_SENSE", "GND", R0805)
two_pin("Device:C", "C11", "100nF", "C11", (X0 + 115, 224), "VBAT_SENSE", "GND", C0805)
# CR2032 for Teensy RTC
two_pin("Device:Battery_Cell", "BT1", "CR2032", "BT1", (X0 + 75, 236), "RTC_VBAT", "GND", "Battery:BatteryHolder_Keystone_3034_1x20mm")

# AMS1117-3.3 for the radio rail (custom box: 1 GND, 2 VOUT, 3 VIN)
REG_NET = {"1": "GND", "2": "+3V3_RF", "3": "+5V"}
place_box("REG_3V3", "U8", "AMS1117-3.3", "U8", (X0 + 115, 188), lambda n: REG_NET[n],
          "Package_TO_SOT_SMD:SOT-223-3_TabPin2")

# ── USB-C receptacle ───────────────────────────────────────────────
usb = LIBPINS["Connector:USB_C_Receptacle_USB2.0_16P"]
USB_AT = (snap(30), snap(205))
usb_pins = list(usb.keys())
instance("Connector:USB_C_Receptacle_USB2.0_16P", "J1", "USB-C charge", USB_AT, 0,
         "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "J1", usb_pins, ref_off=(0, -14), val_off=(0, 14))
USB_NET = {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND",
           "A4": "VBUS_USB", "A9": "VBUS_USB", "B4": "VBUS_USB", "B9": "VBUS_USB",
           "A5": "USB_CC1", "B5": "USB_CC2",
           "A6": None, "A7": None, "B6": None, "B7": None,
           "A8": None, "B8": None, "S1": "GND", "SH": "GND"}
for num in usb_pins:
    px, py, pang = usb[num]
    p = pin_pos(USB_AT, 0, px, py)
    net = USB_NET.get(num)
    if net is None:
        no_connect(p)
        continue
    stub_and_label(p, (pang + 180) % 360, net)

# ── connectors from netlist ────────────────────────────────────────
CONN_FOOT = {2: "Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical",
             3: "Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical",
             4: "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical",
             5: "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
             6: "Connector_JST:JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical",
             9: "Connector_JST:JST_XH_B9B-XH-A_1x09_P2.50mm_Vertical",
             12: "Connector_PinHeader_2.54mm:PinHeader_1x12_P2.54mm_Vertical"}

def connector(ref, key, value, at, nets, foot=None):
    at = (snap(at[0]), snap(at[1]))
    n = len(nets)
    lib = f"Connector_Generic:Conn_01x{n:02d}"
    pins = LIBPINS[lib]
    instance(lib, ref, value, at, 0, foot or CONN_FOOT[n], key,
             [str(i + 1) for i in range(n)], ref_off=(1.5, -(n * 1.27 + 2.6)), val_off=(1.5, n * 1.27 + 2.6))
    for i, net in enumerate(nets):
        num = str(i + 1)
        px, py, pang = pins[num]
        p = pin_pos(at, 0, px, py)
        if net == "NC":
            no_connect(p)
            continue
        stub_and_label(p, (pang + 180) % 360, net)

CY = 40
connector("J2", "J2", "NEXTION (V1 order!)", (35, CY), ["GND", "NC", "+5V", "NEXTION_RX", "NEXTION_TX"])
connector("J3", "J3", "BATTERY XT30", (35, CY + 25), ["VBAT_RAW", "GND"],
          foot="Connector_AMASS:AMASS_XT30U-M_1x02_P5.0mm_Vertical")
connector("J4", "J4", "BALANCE TAP", (35, CY + 45), ["CELL_MID", "GND"])
connector("J5", "J5", "PWR BUTTON", (35, CY + 65), ["PWRBTN", "GND"])
connector("J6", "J6", "GIMBAL L", (35, CY + 85), ["+3V3_T", "GIMBAL1", "GIMBAL2", "GND"])
connector("J7", "J7", "GIMBAL R", (35, CY + 110), ["+3V3_T", "GIMBAL3", "GIMBAL4", "GND"])
connector("J8", "J8", "KNOBS 5-8", (35, CY + 135), ["+3V3_T", "KNOB5", "KNOB6", "KNOB7", "KNOB8", "GND"])
connector("J9", "J9", "SWITCHES", (330, 40), ["SW1","SW2","SW3","SW4","SW5","SW6","SW7","SW8","GND"])
connector("J10", "J10", "TRIMS", (330, 80), ["TRIM1","TRIM2","TRIM3","TRIM4","TRIM5","TRIM6","TRIM7","TRIM8","GND"])
connector("J11", "J11", "WS2812 LED", (330, 115), ["+5V", "WS2812_OUT", "GND"])
connector("J12", "J12", "QWIIC", (330, 135), ["GND", "+3V3_T", "I2C_SDA", "I2C_SCL"],
          foot="Connector_JST:JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical")
connector("J13", "J13", "I2C XH", (330, 160), ["GND", "+3V3_T", "I2C_SDA", "I2C_SCL"])
connector("J14", "J14", "RTC VBAT LEAD", (330, 185), ["RTC_VBAT", "GND"])
connector("J17", "J17", "BUZZER (option)", (330, 200), ["BUZZER", "GND"])
connector("J15", "J15", "ESP SPARE A", (330, 224),
          ["ESP_G4","ESP_G5","ESP_G6","ESP_G7","ESP_G15","ESP_G16","ESP_G3","ESP_G46","ESP_G10","ESP_G11","ESP_G12","ESP_G13"])
connector("J16", "J16", "ESP SPARE B", (330, 266),
          ["ESP_G14","ESP_G1","ESP_G2","ESP_G42","ESP_G41","ESP_G40","ESP_G39","ESP_G21","ESP_G45","ESP_G47","ESP_G48","ESP_3V3"])

# ── power flags ────────────────────────────────────────────────────
FLAGX = 35
for i, net in enumerate(["VBAT_RAW", "VBAT_SENSE", "VBAT_SW", "+5V", "+3V3_T", "+3V3_RF",
                         "VBUS_USB", "CELL_MID", "GND", "RTC_VBAT", "PMID"]):
    at = (snap(FLAGX + i * 12), snap(262))
    instance("power:PWR_FLAG", f"#FLG{i:02d}", "PWR_FLAG", at, 0, "", f"FLG{i}", ["1"],
             ref_off=(0, -5), val_off=(0, -7))
    p = pin_pos(at, 0, *LIBPINS["power:PWR_FLAG"]["1"][:2])
    stub_and_label(p, 90, net)

# a single GND power symbol to anchor the GND net graphically
at = (snap(FLAGX + 11 * 12), snap(262))
instance("power:GND", "#PWR01", "GND", at, 0, "", "PWR01", ["1"], ref_off=(2, 1), val_off=(0, 4))
p = pin_pos(at, 0, *LIBPINS["power:GND"]["1"][:2])
stub_and_label(p, 270, "GND")

# ── notes ──────────────────────────────────────────────────────────
body.append(f'''	(text "TXV2 rev-A — Teensy 4.1 + ESP32-S3 DevKitC + nRF24 + BQ25887 USB-C balance charger.\\nAll connectivity by net label. Sources: TXV2/HARDWARE.md (frozen pin map, approved charging\\namendment), netlist.py. Teensy VBAT: flying lead from Teensy underside pad to J14.\\nJ2 keeps V1's exact 5-pin order (dual-purpose FTDI upload loom - pin 2 unused).\\nR5 7.5k = charge-without-NTC default; fit pack NTC + change to 30k for temperature guard.\\nPololu 2808 / buck socket hole grids to be verified against the real modules at layout.\\nBattery volts: 47k/15k divider from the SWITCHED rail (zero off-drain) into pin 24/A10."
		(exclude_from_sim no) (at 30 302 0)
		(effects (font (size 2.0 2.0)) (justify left bottom))
		(uuid "{U()}")
	)''')

# ── write out ──────────────────────────────────────────────────────
custom_syms = "\n".join(lib_parts.values())
libsyms = "\n".join(LIBSYMS.values())
header = f'''(kicad_sch
	(version 20260306)
	(generator "eeschema")
	(generator_version "10.0")
	(uuid "{uid('ROOT')}")
	(paper "A2")
	(title_block
		(title "TXV2 rev-A main board")
		(rev "rev-A")
		(company "Malcolm Messiter")
		(comment 1 "Teensy 4.1 + ESP32-S3 DevKitC-1U + nRF24 + BQ25887 charger")
	)
	(lib_symbols
{libsyms}
{custom_syms}
	)
'''
tail = '''	(sheet_instances
		(path "/" (page "1"))
	)
	(embedded_fonts no)
)
'''
open(OUT, "w", encoding="utf-8").write(header + "\n".join(body) + "\n" + tail)
# project symbol library (same custom symbols, names without the TXV2: prefix)
lib_out = os.path.expanduser("~/Documents/KiCad/TXV2_MAIN/TXV2.kicad_sym")
lib_body = "\n".join(v.replace('(symbol "TXV2:', '(symbol "', 1) for v in lib_parts.values())
open(lib_out, "w", encoding="utf-8").write(
    '(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "generate_sch")\n\t(generator_version "10.0")\n' + lib_body + '\n)\n')
print("wrote", lib_out)
open(ufile, "w").write("\n".join(f"{k} {v}" for k, v in SCH.items()))
print("wrote", OUT, "with", len(body), "elements")
