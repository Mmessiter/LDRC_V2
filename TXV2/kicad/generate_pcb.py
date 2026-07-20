#!/usr/bin/env python3
# TXV2 rev-A board — PLACEMENT stage (routing follows Malcolm's review).
# Outline 83.3 x 91.7, M3 holes 76.0 x 84.3 (V1 case). Edges mirror V1.
import re, uuid, os

SS = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
HERE = os.path.expanduser("~/Documents/KiCad/TXV2_MAIN")
OUT = f"{HERE}/TXV2_MAIN.kicad_pcb"
def U(): return str(uuid.uuid4())

SCH = dict(line.split() for line in open(f"{HERE}/uuids.txt"))

def match_paren(s, i):
    d = 0
    for j in range(i, len(s)):
        if s[j] == '(': d += 1
        elif s[j] == ')':
            d -= 1
            if d == 0: return j
    raise ValueError

def pad_blocks(fp):
    return [(m.start(), match_paren(fp, m.start()), m.group(1))
            for m in re.finditer(r'\(pad\s+"([^"]+)"', fp)]

NETS = {}
def N(name):
    if name not in NETS:
        NETS[name] = len(NETS) + 1
    return NETS[name]

def read_mod(path):
    for p in (f"{HERE}/TXV2.pretty/{path}.kicad_mod", f"{SS}/{path}.kicad_mod"):
        if os.path.exists(p): return open(p).read()
    raise FileNotFoundError(path)

def place(libref, ref, value, x, y, rot, nets, key, layer="F.Cu", hide_ref=False):
    """libref 'Lib:Name' or 'TXV2:Name'; nets: dict pad->netname (missing = none)."""
    lib, name = libref.split(":")
    fp = read_mod(name if lib == "TXV2" else f"{lib}.pretty/{name}")
    fp = re.sub(r'\n\s*\(version [^)]*\)', '', fp)
    fp = re.sub(r'\n\s*\(generator(_version)? "[^"]*"\)', '', fp)
    fp = re.sub(r'^\(footprint\s+"[^"]+"', f'(footprint "{libref}"', fp)
    if layer == "B.Cu":   # mirror to back: swap every front/back layer name
        for a, b in [("F.Cu","B.Cu"),("F.SilkS","B.SilkS"),("F.Mask","B.Mask"),
                     ("F.Paste","B.Paste"),("F.CrtYd","B.CrtYd"),("F.Fab","B.Fab")]:
            fp = fp.replace(f'"{a}"', f'"XTMP{b}"').replace(f'"XTMP{b}"', f'"{b}"')
    rr = f" {rot}" if rot else ""
    fp = fp.replace(f'(layer "{layer}")',
                    f'(layer "{layer}")\n\t(uuid "{U()}")\n\t(at {x} {y}{rr})\n\t(path "/{SCH.get(key, U())}")', 1)
    fp = fp.replace('(property "Reference" "REF**"', f'(property "Reference" "{ref}"', 1)
    if hide_ref:
        i = fp.index(f'(property "Reference" "{ref}"')
        j = match_paren(fp, i)
        blk = fp[i:j].replace('(at ', '(hide yes)\n\t\t(at ', 1)
        fp = fp[:i] + blk + fp[j:]
    fp = re.sub(r'\(property "Value" "[^"]*"', f'(property "Value" "{value}"', fp, count=1)
    # rotate pads with footprint rotation (in-board pads carry absolute angle)
    if rot:
        def rot_pad(m):
            blk = m.group(0)
            a = re.search(r'\(at ([-\d.]+) ([-\d.]+)( ([-\d.]+))?\)', blk)
            ang = (float(a.group(4) or 0) + rot) % 360
            return blk.replace(a.group(0), f'(at {a.group(1)} {a.group(2)} {ang})', 1)
        out = []
        last = 0
        for a, b, num in pad_blocks(fp):
            out.append(fp[last:a]); out.append(rot_pad(re.match(r'[\s\S]*', fp[a:b+1])))
            last = b + 1
        fp = "".join(out) + fp[last:]
    for a, b, num in reversed(pad_blocks(fp)):
        if num in nets:
            fp = fp[:b] + f'\n\t\t(net {N(nets[num])} "{nets[num]}")\n\t' + fp[b:]
    return fp

fps = []
def P(*a, **k): fps.append(place(*a, **k))

# ── net maps (mirror of generate_sch.py) ───────────────────────────
TEENSY_L = ["GND","NEXTION_TX","NEXTION_RX","WS2812_DATA","BUZZER","PWRBTN","LATCH_OFF","HANDSHAKE_A",
            "LINK_RX2","LINK_TX2","NRF_CE","NRF_CSN","SPI_MOSI","SPI_MISO","SPI_SCK","+3V3_T",
            "VBAT_SENSE","HANDSHAKE_B","SW1","SW2","SW3","SW4","SW5","SW6"]
# careful: left column order is GND,0..12,3V3,24..32
TEENSY_L = ["GND","NEXTION_TX","NEXTION_RX","WS2812_DATA","BUZZER","PWRBTN","LATCH_OFF","HANDSHAKE_A",
            "LINK_RX2","LINK_TX2","NRF_CE","NRF_CSN","SPI_MOSI","SPI_MISO","+3V3_T",
            "VBAT_SENSE","HANDSHAKE_B","SW1","SW2","SW3","SW4","SW5","SW6","SW7"]
TEENSY_R = ["+5V","GND","+3V3_T","KNOB8","KNOB7","KNOB6","KNOB5","I2C_SCL","I2C_SDA","GIMBAL4",
            "GIMBAL3","GIMBAL2","GIMBAL1","SPI_SCK","GND","TRIM8","TRIM7","TRIM6","TRIM5","TRIM4",
            "TRIM3","TRIM2","TRIM1","SW8"]
TEENSY_NETS = {str(i + 1): n for i, n in enumerate(TEENSY_L)}
TEENSY_NETS.update({str(i + 25): n for i, n in enumerate(TEENSY_R)})

DK_J1 = ["ESP_3V3","ESP_3V3",None,"ESP_G4","ESP_G5","ESP_G6","ESP_G7","ESP_G15","ESP_G16","LINK_TX2",
         "LINK_RX2","HANDSHAKE_A","ESP_G3","ESP_G46","HANDSHAKE_B","ESP_G10","ESP_G11","ESP_G12",
         "ESP_G13","ESP_G14","+5V","GND"]
DK_J3 = ["GND",None,None,"ESP_G1","ESP_G2","ESP_G42","ESP_G41","ESP_G40","ESP_G39",None,None,None,None,
         None,"ESP_G45","ESP_G48","ESP_G47","ESP_G21",None,None,"GND","GND"]
DK_NETS = {str(i + 1): n for i, n in enumerate(DK_J1) if n}
DK_NETS.update({str(i + 23): n for i, n in enumerate(DK_J3) if n})

NRF_NETS = {"1":"GND","2":"+3V3_RF","3":"NRF_CE","4":"NRF_CSN","5":"SPI_SCK","6":"SPI_MOSI","7":"SPI_MISO"}
P2808 = {"1":"VBAT_RAW","2":"VBAT_RAW","3":"GND","4":"GND","6":"LATCH_OFF","7":"CTRL_TP",
         "8":"VBAT_SW","9":"VBAT_SW","10":"GND","11":"GND","12":"PWRBTN"}
         # V1-matched: pin A(12) -> button -> GND = push-ON-only (brush-proof);
         # PWRBTN also to Teensy pin4 (digital INPUT_PULLUP, LOW=pressed);
         # OFF(6) <- Teensy pin5 drives HIGH to power off; ON(5) unused; 13=B unused
BUCK_M = {"1":"VBAT_SW","2":"GND","3":"+5V"}
BUCK_N = {"1":"VBAT_SW","2":"GND","3":"+5V_NEXT"}
BQ = {"23":"VBUS_USB","24":"GND","21":"PMID","22":"PMID","17":"SW_CHG","18":"SW_CHG","12":"BTST",
      "11":"REGN","4":"I2C_SDA","5":"I2C_SCL","13":"VBAT_RAW","14":"VBAT_RAW","15":"VBAT_RAW",
      "16":"VBAT_RAW","9":"MID_SENSE","10":"CB_PATH","2":"CHG_STAT","7":"CHG_TS","8":"CHG_ILIM",
      "3":"GND","19":"GND","20":"GND","25":"GND"}
USB = {"A1":"GND","A12":"GND","B1":"GND","B12":"GND","A4":"VBUS_USB","A9":"VBUS_USB","B4":"VBUS_USB",
       "B9":"VBUS_USB","A5":"USB_CC1","B5":"USB_CC2","S1":"GND"}

XH = "Connector_JST:JST_XH_B{n}B-XH-A_1x{n:02d}_P2.50mm_Vertical"

# ── placement ──────────────────────────────────────────────────────
P("TXV2:Teensy41_Socket", "U1", "Teensy 4.1", 126, 106, 0, TEENSY_NETS, "U1")
P("TXV2:DevKitC1_Socket", "U2", "ESP32-S3-DevKitC", 148, 106, 0, DK_NETS, "U2")
P("TXV2:NRF24_Socket_2x4", "U3", "nRF24 PA/LNA", 109.5, 106, 0, NRF_NETS, "U3")
P("TXV2:Pololu2808_Socket", "U4", "Pololu 2808", 124, 168.5, 0, P2808, "U4")
P("TXV2:Buck3pin_VGV", "U5", "5V buck MAIN", 111, 164, 90, BUCK_M, "U5")
P("TXV2:Buck3pin_VGV", "U9", "5V buck NEXT", 111, 172, 90, BUCK_N, "U9")
P("Package_DFN_QFN:HVQFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", "U7", "BQ25887",
  132, 140, 0, BQ, "U7", layer="B.Cu")
P("Package_TO_SOT_SMD:SOT-223-3_TabPin2", "U8", "AMS1117-3.3", 116.5, 127, 0,
  {"1":"GND","2":"+3V3_RF","3":"+5V","4":"+3V3_RF"}, "U8")
P("Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "J1", "USB-C", 150, 187.2, 0, USB, "J1", layer="B.Cu")
P("Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical", "J2", "NEXTION", 178, 139, 0,
  {"1":"GND","3":"+5V_NEXT","4":"NEXTION_RX","5":"NEXTION_TX"}, "J2")
P("Connector_AMASS:AMASS_XT30U-M_1x02_P5.0mm_Vertical", "J3", "BATT", 110.5, 186, 0,
  {"1":"VBAT_RAW","2":"GND"}, "J3")
P(XH.format(n=2), "J4", "BAL", 115, 178, 0, {"1":"CELL_MID","2":"GND"}, "J4")
P(XH.format(n=2), "J5", "BTN", 158.4, 187.7, 0, {"1":"PWRBTN","2":"GND"}, "J5")
P(XH.format(n=4), "J6", "GIMBAL L", 106, 147, 270, {"1":"+3V3_T","2":"GIMBAL1","3":"GIMBAL2","4":"GND"}, "J6")
P(XH.format(n=4), "J7", "GIMBAL R", 178, 124, 270, {"1":"+3V3_T","2":"GIMBAL3","3":"GIMBAL4","4":"GND"}, "J7")
P(XH.format(n=6), "J8", "KNOBS", 106, 162, 270,
  {"1":"+3V3_T","2":"KNOB5","3":"KNOB6","4":"KNOB7","5":"KNOB8","6":"GND"}, "J8")
P(XH.format(n=9), "J9", "SWITCHES", 121.8, 185.8, 0,
  {str(i+1): f"SW{i+1}" for i in range(8)} | {"9":"GND"}, "J9")
P(XH.format(n=9), "J10", "TRIMS", 106, 120, 270,
  {str(i+1): f"TRIM{i+1}" for i in range(8)} | {"9":"GND"}, "J10")
P(XH.format(n=3), "J11", "WS2812", 178, 111, 270, {"1":"+5V","2":"WS2812_OUT","3":"GND"}, "J11")
P("Connector_JST:JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical", "J12", "QWIIC", 178, 156, 270,
  {"1":"GND","2":"+3V3_T","3":"I2C_SDA","4":"I2C_SCL","MP":"GND"}, "J12")
P(XH.format(n=4), "J13", "I2C", 172.8, 172, 270, {"1":"GND","2":"+3V3_T","3":"I2C_SDA","4":"I2C_SCL"}, "J13")
P(XH.format(n=2), "J14", "RTC", 120, 112, 270, {"1":"RTC_VBAT","2":"GND"}, "J14")
P("Connector_PinHeader_2.54mm:PinHeader_1x12_P2.54mm_Vertical", "J15", "ESP-A", 145.8, 163.05, 90,
  {"1":"ESP_G4","2":"ESP_G5","3":"ESP_G6","4":"ESP_G7","5":"ESP_G15","6":"ESP_G16","7":"ESP_G3",
   "8":"ESP_G46","9":"ESP_G10","10":"ESP_G11","11":"ESP_G12","12":"ESP_G13"}, "J15")
P("Connector_PinHeader_2.54mm:PinHeader_1x12_P2.54mm_Vertical", "J16", "ESP-B", 145.8, 166.75, 90,
  {"1":"ESP_G14","2":"ESP_G1","3":"ESP_G2","4":"ESP_G42","5":"ESP_G41","6":"ESP_G40","7":"ESP_G39",
   "8":"ESP_G21","9":"ESP_G45","10":"ESP_G47","11":"ESP_G48","12":"ESP_3V3"}, "J16")
P(XH.format(n=2), "J17", "BUZZ", 168.6, 187.7, 0, {"1":"BUZZER","2":"GND"}, "J17")
P("Battery:Battery_Panasonic_CR2032-VS1N_Vertical_CircularHoles", "BT1", "CR2032", 153, 177, 0,
  {"1":"RTC_VBAT","2":"GND"}, "BT1")

R08 = "Resistor_SMD:R_0805_2012Metric"; R12F = "Resistor_SMD:R_1206_3216Metric"
C08 = "Capacitor_SMD:C_0805_2012Metric"; C12F = "Capacitor_SMD:C_1206_3216Metric"
LED = "LED_SMD:LED_0805_2012Metric"

# charger cluster (BACK, around U7 at 128,176)
P("Inductor_SMD:L_Vishay_IHLP-2020", "L1", "1uH", 132, 148.5, 0, {"1":"PMID","2":"SW_CHG"}, "L1", layer="B.Cu")
back = [("C1","1uF",C08,129,122,{"1":"VBUS_USB","2":"GND"}),
        ("C2","10uF",C12F,132,122,{"1":"PMID","2":"GND"}),
        ("C3","10uF",C12F,135,122,{"1":"PMID","2":"GND"}),
        ("C4","10uF",C12F,138,122,{"1":"VBAT_RAW","2":"GND"}),
        ("C5","47pF",C08,129,126,{"1":"VBAT_RAW","2":"GND"}),
        ("C6","47nF",C08,132,126,{"1":"BTST","2":"SW_CHG"}),
        ("C7","4.7uF",C08,135,126,{"1":"REGN","2":"GND"}),
        ("R1","330R",R08,138,133,{"1":"MID_SENSE","2":"CELL_MID"}),
        ("R2","68R",R12F,129,155,{"1":"CB_PATH","2":"CELL_MID"}),
        ("R3","68R",R12F,132.5,155,{"1":"CB_PATH","2":"CELL_MID"}),
        ("R4","5.11k",R08,132,133,{"1":"REGN","2":"CHG_TS"}),
        ("R5","7.5k",R08,135,133,{"1":"CHG_TS","2":"GND"}),
        ("R6","374R",R08,129,133,{"1":"CHG_ILIM","2":"GND"}),
        ("R7","5.1k",R08,138,158.5,{"1":"USB_CC1","2":"GND"}),
        ("R8","5.1k",R08,129,159,{"1":"USB_CC2","2":"GND"}),
        ("R9","470R",R08,136,155,{"1":"VBUS_USB","2":"LED_PWR_A"}),
        ("R10","470R",R08,139,155,{"1":"VBUS_USB","2":"LED_CHG_A"}),
        ("R12","4.7k",R08,152,155,{"1":"+3V3_T","2":"I2C_SDA"}),
        ("R13","4.7k",R08,156,155,{"1":"+3V3_T","2":"I2C_SCL"}),
        ("R14","330R",R08,174,112,{"1":"WS2812_DATA","2":"WS2812_OUT"})]
for ref, val, foot, x, y, nets in back:
    P(foot, ref, val, x, y, 90, nets, ref, layer="B.Cu", hide_ref=True)
# LEDs on TOP near the USB (visible)
P(LED, "D1", "PWR", 146, 181.2, 90, {"1":"LED_PWR_A","2":"GND"}, "D1")
P(LED, "D2", "CHG", 149.4, 181.2, 90, {"1":"LED_CHG_A","2":"CHG_STAT"}, "D2")
# RF rail bulk (top-left, under the elevated nRF module = low parts only)
P("Capacitor_SMD:CP_Elec_6.3x7.7", "C8", "220uF", 119, 136, 0, {"1":"+3V3_RF","2":"GND"}, "C8")
P(C12F, "C9", "10uF", 111.5, 120.5, 90, {"1":"+3V3_RF","2":"GND"}, "C9", hide_ref=True)
P(C08, "C10", "100nF", 110.4, 125.2, 90, {"1":"+3V3_RF","2":"GND"}, "C10", hide_ref=True)
# battery divider (left field)
P(R08, "R15", "47k", 116, 142, 90, {"1":"VBAT_SW","2":"VBAT_SENSE"}, "R15", hide_ref=True)
P(R08, "R16", "15k", 119, 142, 90, {"1":"VBAT_SENSE","2":"GND"}, "R16", hide_ref=True)
P(C08, "C11", "100nF", 122, 142, 90, {"1":"VBAT_SENSE","2":"GND"}, "C11", hide_ref=True)

# mounting holes
for i, (hx, hy) in enumerate([(103.65,103.7),(179.65,103.7),(103.65,188.0),(179.65,188.0)]):
    P("MountingHole:MountingHole_3.2mm_M3", f"H{i+1}", "M3", hx, hy, 0, {}, f"H{i+1}", hide_ref=True)

# ── board text/graphics ────────────────────────────────────────────
def silk(text, x, y, size=1.0, layer="F.SilkS", mirror=False, rot=0):
    j = ' (justify mirror)' if mirror else ''
    return (f'(gr_text "{text}" (at {x} {y} {rot}) (layer "{layer}") (uuid "{U()}") '
            f'(effects (font (size {size} {size}) (thickness 0.15)){j}))')

extras = [
    '(gr_rect (start 100 100) (end 183.3 191.7) (stroke (width 0.1) (type solid)) (fill no) (layer "Edge.Cuts") (uuid "%s"))' % U(),
    silk("TXV2 rev-A", 141.5, 101.5, 1.5),
    silk("USB-C CHARGE (back)", 150, 184.5, 0.8),
    silk("PWR", 146, 179.2, 0.7), silk("CHG", 149.6, 179.2, 0.7),
    silk("nRF24 module over this area", 112.5, 137.8, 0.7),
    silk("Teensy USB ^", 133.6, 103, 0.8),
    silk("ESP32 USB ^", 159.4, 103, 0.8),
]

def zone(layer):
    return f'''(zone (net {N("GND")}) (net_name "GND") (layer "{layer}") (uuid "{U()}")
	(hatch edge 0.5) (connect_pads (clearance 0.4)) (min_thickness 0.2) (filled_areas_thickness no)
	(fill yes (thermal_gap 0.4) (thermal_bridge_width 0.4))
	(polygon (pts (xy 100 100) (xy 183.3 100) (xy 183.3 191.7) (xy 100 191.7))))'''

header_top = '''(kicad_pcb
	(version 20260206)
	(generator "pcbnew")
	(generator_version "10.0")
	(general (thickness 1.6) (legacy_teardrops no))
	(paper "A3")
	(layers
		(0 "F.Cu" signal) (2 "B.Cu" signal)
		(9 "F.Adhes" user "F.Adhesive") (11 "B.Adhes" user "B.Adhesive")
		(13 "F.Paste" user) (15 "B.Paste" user)
		(5 "F.SilkS" user "F.Silkscreen") (7 "B.SilkS" user "B.Silkscreen")
		(1 "F.Mask" user) (3 "B.Mask" user)
		(17 "Dwgs.User" user "User.Drawings") (19 "Cmts.User" user "User.Comments")
		(21 "Eco1.User" user "User.Eco1") (23 "Eco2.User" user "User.Eco2")
		(25 "Edge.Cuts" user) (27 "Margin" user)
		(31 "F.CrtYd" user "F.Courtyard") (29 "B.CrtYd" user "B.Courtyard")
		(35 "F.Fab" user) (33 "B.Fab" user)
	)
	(setup (pad_to_mask_clearance 0) (allow_soldermask_bridges_in_footprints no)
		(tenting (front yes) (back yes)))
'''

body = "\n".join(fps) + "\n" + zone("F.Cu") + "\n" + zone("B.Cu") + "\n" + "\n".join(extras)
netdecl = "\n".join(f'\t(net {i} "{n}")' for n, i in sorted(NETS.items(), key=lambda kv: kv[1]))
out = header_top + '\t(net 0 "")\n' + netdecl + "\n\t" + body.replace("\n", "\n\t") + "\n)\n"
open(OUT, "w").write(out)
print("wrote", OUT, "nets:", len(NETS))
