#!/usr/bin/env python3
"""LDRC Rotorflight dongle PCB v2 (Malcolm 2026-09-08): as small as the XIAO
itself. XIAO ESP32-S3 soldered flat on its castellations on the FRONT, the
JST GH 4-pin (SM04B-GHS-TB) on the BACK under it, opening at the bottom edge.
Pin order = the receiver board's (RXV2_2 J1): 1 GND, 2 +5V, 3 TX (our D6 ->
the Nexus RX), 4 RX (our D5 <- the Nexus TX). A 1:1 pigtail plugs straight in.
Run with KiCad's python:  <kicad python> make_dongle.py <out.kicad_pcb>"""
import sys, os, shutil, tempfile
import pcbnew
from pcbnew import VECTOR2I, FromMM as MM

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/Documents/KiCad/RXV2_DONGLE/RXV2_DONGLE.kicad_pcb')
W, H = 20.9, 24.2                         # board mm - the XIAO's castellation pads plus edge clearance, 1.2 mm for the connector's lip
XO, YO = 1.45, 23.3                        # XIAO footprint origin (its own origin: bottom-left of the module)
JX, JY = 10.45, 20.6                       # JST GH centre on the back; housing +-3.2 in y, opening toward +y (bottom edge)

b = pcbnew.BOARD()
b.GetDesignSettings().SetCopperLayerCount(2)
tmp = tempfile.mkdtemp(); lib = os.path.join(tmp, 'dongle.pretty'); os.makedirs(lib)
shutil.copy(os.path.expanduser('~/Documents/KiCad/XIAO_ESP32_S3/XIAO-ESP32-S3-SMD.kicad_mod'), lib)   # the receiver board's footprint
xiao = pcbnew.FootprintLoad(lib, 'XIAO-ESP32-S3-SMD')
jst  = pcbnew.FootprintLoad('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/Connector_JST.pretty', 'JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal')
assert xiao and jst, 'footprint load failed'
xiao.SetReference('U1'); xiao.SetValue('XIAO ESP32-S3'); xiao.SetPosition(VECTOR2I(MM(XO), MM(YO))); b.Add(xiao)
jst.SetReference('J1');  jst.SetValue('Nexus port'); jst.SetPosition(VECTOR2I(MM(JX), MM(JY))); b.Add(jst)
jst.SetLayerAndFlip(pcbnew.B_Cu)          # on the back, under the module (Flip() before Add() segfaults KiCad 10's python)
assert jst.IsFlipped()

nets = {}
for n in ['GND', '+5V', 'TX', 'RX']:
    ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni); nets[n] = ni
def pad(fp, name):
    for p in fp.Pads():
        if p.GetNumber() == name: return p
    raise KeyError(name)
# XIAO: 6 = D5 (RX in), 7 = D6 (TX out), 13 = GND, 14 = 5V   -   J1 as on the receiver board
pad(xiao, '6').SetNet(nets['RX']); pad(xiao, '7').SetNet(nets['TX']); pad(xiao, '13').SetNet(nets['GND']); pad(xiao, '14').SetNet(nets['+5V'])
for n, net in (('1', 'GND'), ('2', '+5V'), ('3', 'TX'), ('4', 'RX')): pad(jst, n).SetNet(nets[net])

P = {}
for fp in (xiao, jst):
    for p in fp.Pads():
        pos = p.GetPosition(); P[(fp.GetReference(), p.GetNumber())] = (pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y))
print('XIAO D5', P[('U1','6')], 'D6', P[('U1','7')], 'GND', P[('U1','13')], '5V', P[('U1','14')])
print('J1 pins', {n: P[('J1', n)] for n in '1234'}, 'on', 'back' if jst.IsFlipped() else 'front')

F, B = pcbnew.F_Cu, pcbnew.B_Cu
def track(net, pts, layer, w=0.4):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(VECTOR2I(MM(x1), MM(y1))); t.SetEnd(VECTOR2I(MM(x2), MM(y2)))
        t.SetWidth(MM(w)); t.SetLayer(layer); t.SetNet(nets[net]); b.Add(t)
def via(net, x, y):
    v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(MM(x), MM(y))); v.SetDrill(MM(0.4)); v.SetWidth(MM(0.8)); v.SetNet(nets[net]); b.Add(v)

d5, d6, gnd, v5 = P[('U1','6')], P[('U1','7')], P[('U1','13')], P[('U1','14')]
j = {n: P[('J1', n)] for n in '1234'}; py = j['1'][1]
# The connector pads are on B.Cu; everything runs on B.Cu to a via beside the
# XIAO pad, then a short F.Cu stub onto the castellation pad. Rows leave the
# pads upward (-y); the pin nearer a destination takes the row nearer the pads.
# RX (pin 4, the leftmost) -> D5 (upper of the two left pads)
track('RX',  [j['4'], (j['4'][0], 17.4), (5.2, 17.4), (5.2, d5[1])], B); via('RX', 5.2, d5[1]); track('RX', [(5.2, d5[1]), d5], F)
# TX (pin 3) -> D6 (lower left pad): a higher row, then down beside the RX via
track('TX',  [j['3'], (j['3'][0], 16.6), (4.3, 16.6), (4.3, d6[1])], B); via('TX', 4.3, d6[1]); track('TX', [(4.3, d6[1]), d6], F)
# +5V (pin 2) -> pad 14 (top right): the higher of the two right-going rows
track('+5V', [j['2'], (j['2'][0], 15.4), (15.3, 15.4), (15.3, v5[1])], B); via('+5V', 15.3, v5[1]); track('+5V', [(15.3, v5[1]), v5], F)
# GND (pin 1, the rightmost) -> pad 13: the lower row
track('GND', [j['1'], (j['1'][0], 16.0), (16.3, 16.0), (16.3, gnd[1])], B); via('GND', 16.3, gnd[1]); track('GND', [(16.3, gnd[1]), gnd], F)

def edge(x1, y1, x2, y2):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(VECTOR2I(MM(x1), MM(y1))); s.SetEnd(VECTOR2I(MM(x2), MM(y2)))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); b.Add(s)
edge(0, 0, W, 0); edge(W, 0, W, H); edge(W, H, 0, H); edge(0, H, 0, 0)
def text(s, x, y, size=0.8, layer=pcbnew.F_SilkS, rot=0):
    t = pcbnew.PCB_TEXT(b); t.SetText(s); t.SetPosition(VECTOR2I(MM(x), MM(y))); t.SetTextSize(VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(0.15)); t.SetLayer(layer); t.SetTextAngleDegrees(rot)
    if layer == pcbnew.B_SilkS: t.SetMirrored(True)
    b.Add(t)
text('USB ^', W / 2, 1.3, 0.8, layer=pcbnew.B_SilkS)              # back: the module hides the front
text('LDRC Rotorflight dongle', W / 2, 3.0, 0.8, layer=pcbnew.B_SilkS)
text('GND 5V TX RX', W / 2, 14.0, 0.8, layer=pcbnew.B_SilkS)     # pins 1..4 left to right as seen from the back
pcbnew.SaveBoard(OUT, b)
print('saved', OUT)
