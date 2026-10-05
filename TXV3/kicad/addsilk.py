import pcbnew, math
b = pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
mm = pcbnew.FromMM; V = pcbnew.VECTOR2I
FS, BS = pcbnew.F_SilkS, pcbnew.B_SilkS
cx, cy = mm(141.5), mm(146)   # board centre

def text(s, x, y, size=0.7, layer=FS, rot=0, mirror=False, bold=False):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(s); t.SetPosition(V(int(x), int(y))); t.SetLayer(layer)
    t.SetTextSize(V(mm(size), mm(size))); t.SetTextThickness(mm(0.12*(1.6 if bold else 1)))
    t.SetTextAngle(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
    if mirror or layer == BS: t.SetMirrored(True)
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    b.Add(t)

def dot(x, y, r=0.45, layer=FS):
    c = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_CIRCLE)
    c.SetLayer(layer); c.SetCenter(V(int(x), int(y)))
    c.SetEnd(V(int(x + mm(r)), int(y))); c.SetWidth(mm(0.15)); c.SetFilled(True)
    b.Add(c)

# net -> short silk label
SHORT = {"GND":"G","+5V":"5V","+3V3_T":"3V3","+3V3_RF":"3V3","NEXTION_RX":"RX","NEXTION_TX":"TX",
    "CELL_MID":"MID","PWRBTN":"BTN","BUZZER":"BUZ","WS2812_OUT":"LED","I2C_SDA":"SDA","I2C_SCL":"SCL",
    "RTC_VBAT":"VB","VBAT_RAW":"+","VBAT_SW":"VSW","+5V ":"5V",
    "GIMBAL1":"1","GIMBAL2":"2","GIMBAL3":"3","GIMBAL4":"4",
    "KNOB5":"5","KNOB6":"6","KNOB7":"7","KNOB8":"8",
    "SW1":"1","SW2":"2","SW3":"3","SW4":"4","SW5":"5","SW6":"6","SW7":"7","SW8":"8",
    "TRIM1":"1","TRIM2":"2","TRIM3":"3","TRIM4":"4","TRIM5":"5","TRIM6":"6","TRIM7":"7","TRIM8":"8"}

def label_connector(ref, special=None):
    fp = b.FindFootprintByReference(ref)
    if not fp: return
    back = fp.GetLayer() == pcbnew.B_Cu
    layer = BS if back else FS
    pads = [(p.GetNumber(), p.GetPosition(), b.GetNetInfo().GetNetItem(p.GetNetCode()).GetNetname())
            for p in fp.Pads()]
    # orientation: labels offset outward from board centre
    for num, pos, net in pads:
        lab = (special or {}).get(num) or SHORT.get(net, net.replace("ESP_G","G"))
        if lab is None: continue
        dx = pos.x - cx; dy = pos.y - cy
        d = math.hypot(dx, dy) or 1
        ox = pos.x + int(mm(1.7) * dx / d); oy = pos.y + int(mm(1.7) * dy / d)
        text(lab, ox, oy, 0.65, layer, mirror=back)
    # pin-1 dot
    p1 = next((p for n, p, _ in pads if n == "1"), None)
    if p1: dot(p1.x - mm(1.0) if not back else p1.x + mm(1.0), p1.y, 0.4, layer)

# connectors
for ref in ["J3","J4","J5","J6","J7","J8","J9","J10","J11","J12","J13","J14","J17"]:
    label_connector(ref)
# Nextion: explicit end labels + FTDI reminder
label_connector("J2", special={"1":"GND","3":"5V","4":"RX","5":"TX","2":"(skip)"})
# 5V buck
label_connector("U5", special={"1":"VIN","2":"GND","3":"VOUT"})
# XT30 polarity
label_connector("J3", special={"1":"+","2":"-"})

# ── MCU orientation: USB-end arrow + pin-1 marker ──
for ref, name in [("U1","TEENSY"), ("U2","ESP32")]:
    fp = b.FindFootprintByReference(ref)
    p1 = next(p for p in fp.Pads() if p.GetNumber() == "1")
    pos = p1.GetPosition()
    # pin-1 solid marker + "1"
    dot(pos.x - mm(1.4), pos.y, 0.5)
    text("1", pos.x - mm(2.6), pos.y, 0.9, FS, bold=True)
    # USB end arrow across the top
    top = min(pd.GetPosition().y for pd in fp.Pads())
    midx = sum(pd.GetPosition().x for pd in fp.Pads()) / len(list(fp.Pads()))
    text(f"<<< USB END ({name})", int(midx), top - mm(2.0), 1.0, FS, bold=True)

# rename the spare-header silk from SP-A/SP-B / ESP-A/ESP-B to something clear
for ref, newname in [("J15","ESP32 SPARE GPIO (A)"), ("J16","ESP32 SPARE GPIO (B)")]:
    fp = b.FindFootprintByReference(ref)
    fp.Value().SetText(newname)
    fp.Value().SetTextSize(V(mm(0.8), mm(0.8)))

# clarify the Pololu is provisional right on the silk
fp = b.FindFootprintByReference("U4")
text("PWR LATCH (2808)", fp.GetPosition().x, fp.GetPosition().y + mm(8.5), 0.8, FS, bold=True)

pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb', b)
print("silk added")
