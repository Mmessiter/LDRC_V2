#!/usr/bin/env python3
"""Generate the LDRC Rotorflight dongle PCB (Malcolm 2026-09-08: "the PCB needs
only the ESP32-S3 and the connector"): a XIAO ESP32-S3 soldered flat on its
castellations + one JST GH 4-pin (SM04B-GHS-TB) that takes the Nexus pigtail.
Run with KiCad's python:  <kicad python> make_dongle.py <out.kicad_pcb>
ORDER below = the Nexus port's pin order (pin 1..4) - CONFIRM ON THE BOARD
before ordering (RadioMaster's text manual does not state it)."""
import sys, os, shutil, tempfile
import pcbnew
from pcbnew import VECTOR2I, FromMM as MM

ORDER = ['GND', '5V', 'TX', 'RX']        # Nexus port pin 1..4  ->  TX = the flight controller's TX (into our D5), RX = its RX (from our D6)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/Documents/KiCad/RXV2_DONGLE/RXV2_DONGLE.kicad_pcb')
W, H = 23.5, 36.0                         # board mm
XO, YO = 2.5, 25.0                        # XIAO footprint origin (its own origin is bottom-left of the module)
JX, JY = 11.75, 31.1                      # JST GH centre (pads at JY-1.85, housing to JY+3.2, opening at the bottom edge)

b = pcbnew.BOARD()
b.GetDesignSettings().SetCopperLayerCount(2)

# --- footprints: XIAO castellated (Malcolm's library) + JST GH from KiCad's library
tmp = tempfile.mkdtemp(); lib = os.path.join(tmp, 'dongle.pretty'); os.makedirs(lib)
shutil.copy(os.path.expanduser('~/Documents/KiCad/XIAO_ESP32_S3/XIAO-ESP32-S3-SMD_PAD.kicad_mod'), lib)
xiao = pcbnew.FootprintLoad(lib, 'XIAO-ESP32-S3-SMD_PAD')
jst  = pcbnew.FootprintLoad('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/Connector_JST.pretty', 'JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal')
assert xiao and jst, 'footprint load failed'
xiao.SetReference('U1'); xiao.SetValue('XIAO ESP32-S3'); xiao.SetPosition(VECTOR2I(MM(XO), MM(YO))); b.Add(xiao)
jst.SetReference('J1');  jst.SetValue('to Nexus port'); jst.SetPosition(VECTOR2I(MM(JX), MM(JY))); b.Add(jst)

# --- nets
nets = {}
for n in ['GND', '5V', 'FC_TX', 'FC_RX']:
    ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni); nets[n] = ni
def pad(fp, name):
    for p in fp.Pads():
        if p.GetNumber() == name: return p
    raise KeyError(name)
# XIAO: pad 6 = D5 (our RX in <- FC TX), pad 7 = D6 (our TX -> FC RX), 13 = GND, 14 = 5V
pad(xiao, '6').SetNet(nets['FC_TX']); pad(xiao, '7').SetNet(nets['FC_RX']); pad(xiao, '13').SetNet(nets['GND']); pad(xiao, '14').SetNet(nets['5V'])
sig = {'GND': 'GND', '5V': '5V', 'TX': 'FC_TX', 'RX': 'FC_RX'}
for i, s in enumerate(ORDER): pad(jst, str(i + 1)).SetNet(nets[sig[s]])
# copy the MP pads to GND is unnecessary (mechanical)

P = {}                                   # absolute pad centres (mm)
for fp in (xiao, jst):
    for p in fp.Pads():
        pos = p.GetPosition(); P[(fp.GetReference(), p.GetNumber())] = (pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y))
jpin = {s: P[('J1', str(i + 1))] for i, s in enumerate(ORDER)}
print('XIAO D5', P[('U1','6')], 'D6', P[('U1','7')], 'GND', P[('U1','13')], '5V', P[('U1','14')])
print('JST pins', jpin)

F, B = pcbnew.F_Cu, pcbnew.B_Cu
def track(net, pts, layer, w=0.4):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(VECTOR2I(MM(x1), MM(y1))); t.SetEnd(VECTOR2I(MM(x2), MM(y2)))
        t.SetWidth(MM(w)); t.SetLayer(layer); t.SetNet(nets[net]); b.Add(t)
def via(net, x, y):
    v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(MM(x), MM(y))); v.SetDrill(MM(0.4)); v.SetWidth(MM(0.8)); v.SetNet(nets[net]); b.Add(v)

assert ORDER == ['GND', '5V', 'TX', 'RX'], 'hand route below is for this order - re-route for another'
d5, d6, gnd, v5 = P[('U1','6')], P[('U1','7')], P[('U1','13')], P[('U1','14')]
xg, xv, xt, xr = jpin['GND'][0], jpin['5V'][0], jpin['TX'][0], jpin['RX'][0]
py = jpin['GND'][1]                      # pad row y
VY = py - 1.45                           # via line just above the pads
XR1, XR2 = 21.3, 22.2                    # the two verticals up the right edge (B.Cu)
# Two layers, no crossings: F.Cu carries the two signal rows (RX at 25.7,
# TX at 26.9 under it), B.Cu carries the two power rows (GND 25.5, 5V 26.2)
# and the TX's last leg up to its pad. Vias sit on a line 1.45 above the pads.
# FC RX (our D6, bottom-left pad): F.Cu - stub up, row left, up to the pad
track('FC_RX', [(xr, py), (xr, 25.7), (d6[0], 25.7), d6], F)
# FC TX (our D5, the pad above D6): F.Cu stub + row left, via, B.Cu up, via, stub to the pad
track('FC_TX', [(xt, py), (xt, 26.9), (5.9, 26.9)], F); via('FC_TX', 5.9, 26.9)
track('FC_TX', [(5.9, 26.9), (5.9, d5[1])], B); via('FC_TX', 5.9, d5[1])
track('FC_TX', [(5.9, d5[1]), d5], F)
# GND: stub, via, B.Cu up to 25.5 then right, up the right edge, via, stub to pad 13
track('GND', [(xg, py), (xg, VY)], F); via('GND', xg, VY)
track('GND', [(xg, VY), (xg, 25.5), (XR1, 25.5), (XR1, gnd[1])], B); via('GND', XR1, gnd[1])
track('GND', [(XR1, gnd[1]), gnd], F)
# 5V: stub, via, B.Cu up to 26.2 then right, up the outer edge, via, stub to pad 14
track('5V', [(xv, py), (xv, VY)], F); via('5V', xv, VY)
track('5V', [(xv, VY), (xv, 26.2), (XR2, 26.2), (XR2, v5[1])], B); via('5V', XR2, v5[1])
track('5V', [(XR2, v5[1]), v5], F)

# --- outline, silk
def edge(x1, y1, x2, y2):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(VECTOR2I(MM(x1), MM(y1))); s.SetEnd(VECTOR2I(MM(x2), MM(y2)))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); b.Add(s)
edge(0, 0, W, 0); edge(W, 0, W, H); edge(W, H, 0, H); edge(0, H, 0, 0)
def text(s, x, y, size=0.9, layer=pcbnew.F_SilkS, rot=0):
    t = pcbnew.PCB_TEXT(b); t.SetText(s); t.SetPosition(VECTOR2I(MM(x), MM(y))); t.SetTextSize(VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(0.15)); t.SetLayer(layer); t.SetTextAngleDegrees(rot)
    if layer == pcbnew.B_SilkS: t.SetMirrored(True)
    b.Add(t)
text('LDRC Rotorflight dongle', W / 2, 1.2, 0.8)
text('USB ^', 21.9, 4.2, 0.8, rot=90)
text(' '.join(ORDER), JX, H - 2.4, 0.8, layer=pcbnew.B_SilkS)   # pin names under the connector, read from the back
text('to Nexus port', W / 2, H - 0.9, 0.8)

pcbnew.SaveBoard(OUT, b)
print('saved', OUT)
