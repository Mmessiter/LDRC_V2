# TXV2 main board Rev-B — surgical edits on the fabbed Rev-A .kicad_pcb.
# Run with KiCad's own python (it needs the pcbnew module):
#   /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 revb_edit.py <in.kicad_pcb> <out.kicad_pcb>
# Changes (2026-09-06, after the pre-assembly review):
#   1. Erratum 1 — Pololu 2808 (U4) footprint un-mirrored: the two pin rows
#      swap (7-pin row VIN..CTRL now at the row nearer the board's bottom
#      edge, y=181; 6-pin row VOUT..B at y=168.7), so the module goes on
#      the TOP right-side-up. The five nets that lost their pads are
#      re-routed locally (VBAT_RAW, VBAT_SW, PWR_A, LATCH_OFF; CTRL is a
#      test pad).
#   2. Erratum 3 — the VBAT_SENSE/GND short: C1's ground stub + its via
#      removed (C1 keeps ground through the pour).
#   3. Erratum 2 — silk: "< USB end" at the ANTENNA end becomes
#      "ANTENNA end ^"; a "USB end v" is added at the other end.
#   4. New C12 10 uF input capacitor for the AMS1117 (U8).
#   5. Revision text.
# Track widening of the power nets is done by widen.py afterwards (DRC-gated).
import sys, pcbnew
from pcbnew import VECTOR2I, FromMM as MM
src, dst = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(src)
def net(name): return b.FindNet(name)
def layer(name): return b.GetLayerID(name)
def P(x, y): return VECTOR2I(MM(x), MM(y))
def seg(net_name, lay, x1, y1, x2, y2, w=0.2):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(x1, y1)); t.SetEnd(P(x2, y2)); t.SetWidth(MM(w)); t.SetLayer(layer(lay)); t.SetNet(net(net_name)); b.Add(t); return t
def find_seg(net_name, lay, x1, y1, x2, y2, tol=0.05):
    for t in b.GetTracks():
        if t.GetClass() != 'PCB_TRACK' or t.GetNetname() != net_name or t.GetLayerName() != lay: continue
        s, e = t.GetStart(), t.GetEnd()
        pts = {(round(s.x/1e6, 2), round(s.y/1e6, 2)), (round(e.x/1e6, 2), round(e.y/1e6, 2))}
        want = {(round(x1, 2), round(y1, 2)), (round(x2, 2), round(y2, 2))}
        if all(any(abs(a[0]-c[0]) <= tol and abs(a[1]-c[1]) <= tol for c in pts) for a in want): return t
    raise SystemExit(f'segment not found: {net_name} {lay} ({x1},{y1})-({x2},{y2})')
def find_via(net_name, x, y, tol=0.05):
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA' and t.GetNetname() == net_name and abs(t.GetPosition().x/1e6 - x) <= tol and abs(t.GetPosition().y/1e6 - y) <= tol: return t
    raise SystemExit(f'via not found: {net_name} ({x},{y})')

# ---- 1. U4: swap the rows (local x' = 12.3 - x; the rows are 12.3 mm apart) ----
u4 = b.FindFootprintByReference('U4')
for p in u4.Pads():
    r = p.GetFPRelativePosition()
    p.SetFPRelativePosition(VECTOR2I(MM(12.3) - r.x, r.y))
# sanity: pad 1 (VIN) must now sit at (112.0, 181.0), pad 8 (VOUT) at (112.0, 168.7)
chk = {p.GetNumber(): (round(p.GetPosition().x/1e6, 2), round(p.GetPosition().y/1e6, 2)) for p in u4.Pads()}
assert chk['1'] == (112.0, 181.0) and chk['8'] == (112.0, 168.7) and chk['7'] == (127.24, 181.0) and chk['13'] == (124.7, 168.7), chk

# ---- re-route the nets that lost their pads ----
# VBAT_RAW: keep the long B.Cu run along y=171.01; it now drops to the new row
b.Remove(find_seg('VBAT_RAW', 'B.Cu', 116.85, 171.01, 114.54, 168.70))
s = find_seg('VBAT_RAW', 'B.Cu', 112.00, 168.70, 114.54, 168.70); s.SetNet(net('VBAT_SW'))     # row-A link now joins the VOUT pads
s = find_seg('VBAT_SW',  'B.Cu', 112.00, 181.00, 114.54, 181.00); s.SetNet(net('VBAT_RAW'))    # row-B link now joins the VIN pads
seg('VBAT_RAW', 'B.Cu', 116.85, 171.01, 116.85, 178.69)
seg('VBAT_RAW', 'B.Cu', 116.85, 178.69, 114.54, 181.00)
# VBAT_SW: buck U9 feed on In2 stops at the new VOUT row; the south branch (U5/J17) climbs on B.Cu
b.Remove(find_seg('VBAT_SW', 'In2.Cu', 113.27, 165.42, 113.27, 179.73))
b.Remove(find_seg('VBAT_SW', 'In2.Cu', 113.27, 179.73, 114.54, 181.00))
seg('VBAT_SW', 'In2.Cu', 113.27, 165.42, 113.27, 167.43)
seg('VBAT_SW', 'In2.Cu', 113.27, 167.43, 114.54, 168.70)
b.Remove(find_seg('VBAT_SW', 'B.Cu', 116.80, 183.26, 114.54, 181.00))
seg('VBAT_SW', 'B.Cu', 116.80, 183.26, 116.00, 183.26)
v = pcbnew.PCB_VIA(b); v.SetPosition(P(116.00, 183.26)); v.SetDrill(MM(0.3)); v.SetWidth(MM(0.6)); v.SetNet(net('VBAT_SW')); b.Add(v)
seg('VBAT_SW', 'In2.Cu', 116.00, 183.26, 113.27, 183.26)
seg('VBAT_SW', 'In2.Cu', 113.27, 183.26, 113.27, 167.43)     # the old In2 climb between the VIN pads, extended
# PWR_A: the In2 drop now ends at the new A pin in the upper row
b.Remove(find_seg('PWR_A', 'In2.Cu', 123.45, 166.13, 123.45, 179.71))
b.Remove(find_seg('PWR_A', 'In2.Cu', 123.45, 179.71, 122.16, 181.00))
seg('PWR_A', 'In2.Cu', 123.45, 166.13, 123.45, 167.40)
seg('PWR_A', 'In2.Cu', 123.45, 167.40, 122.16, 168.70)
# LATCH_OFF: F.Cu, round the east side of the (now unused) hole at 124.7/168.7, down to the new OFF pin
d = find_seg('LATCH_OFF', 'F.Cu', 130.70, 162.75, 124.75, 168.70)
# every little LATCH_OFF stub that ended on the old pin (124.7, 168.7) goes
for t in list(b.GetTracks()):
    if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == 'LATCH_OFF' and t.GetLayerName() == 'F.Cu' and t is not d:
        pts = [t.GetStart(), t.GetEnd()]
        if all(124.55 <= q.x/1e6 <= 124.9 and 168.55 <= q.y/1e6 <= 168.85 for q in pts): b.Remove(t)
# keep the diagonal's exact upper end (its clearance to the +3V3_T via is at the limit); shorten the lower end on the same line
s0, e1 = d.GetStart(), d.GetEnd()
top = s0 if s0.y < e1.y else e1
e0 = VECTOR2I(top.x - MM(4.5), top.y + MM(4.5))
d.SetStart(top); d.SetEnd(e0)
ex, ey = e0.x / 1e6, e0.y / 1e6
seg('LATCH_OFF', 'F.Cu', ex, ey, ex, 170.20)
seg('LATCH_OFF', 'F.Cu', ex, 170.20, ex - 1.5, 171.70)
seg('LATCH_OFF', 'F.Cu', ex - 1.5, 171.70, 124.70, 171.70 + (ex - 1.5 - 124.70))   # tiny 45° step onto x = 124.70
seg('LATCH_OFF', 'F.Cu', 124.70, 171.70 + (ex - 1.5 - 124.70), 124.70, 181.00)

# SW2: the diagonal (122.3,185.82)->(131.95,176.17) passes through the new pad-7 hole at (127.24,181)
b.Remove(find_seg('SW2', 'B.Cu', 122.30, 185.82, 131.95, 176.17))
seg('SW2', 'B.Cu', 122.30, 185.82, 124.30, 183.82)
seg('SW2', 'B.Cu', 124.30, 183.82, 129.74, 183.82)
seg('SW2', 'B.Cu', 129.74, 183.82, 129.74, 178.38)
seg('SW2', 'B.Cu', 129.74, 178.38, 131.95, 176.17)

# ---- 2. the VBAT_SENSE short: route the sense track NORTH of C1's ground via ----
# C1's ground stub + via are that pad's only ground (it is fenced in by the
# sense track and GIMBAL3), so they stay; the sense track that used to squeeze
# between the via and the pad — and crossed the stub — now goes over the top.
b.Remove(find_seg('VBAT_SENSE', 'B.Cu', 132.385, 121.529, 131.104, 120.247))
b.Remove(find_seg('VBAT_SENSE', 'B.Cu', 131.104, 120.247, 129.696, 120.247))
b.Remove(find_seg('VBAT_SENSE', 'B.Cu', 129.696, 120.247, 128.691, 121.253))
vert = find_seg('VBAT_SENSE', 'B.Cu', 128.691, 121.253, 128.691, 130.389)
a, c = vert.GetStart(), vert.GetEnd()
if a.y > c.y: a, c = c, a
vert.SetStart(VECTOR2I(a.x, MM(119.385))); vert.SetEnd(c)
vx = a.x / 1e6
seg('VBAT_SENSE', 'B.Cu', 132.385, 121.529, 131.900, 121.044)
seg('VBAT_SENSE', 'B.Cu', 131.900, 121.044, 131.900, 119.385)
seg('VBAT_SENSE', 'B.Cu', 131.900, 119.385, 131.415, 118.900)
seg('VBAT_SENSE', 'B.Cu', 131.415, 118.900, vx + 0.485, 118.900)
seg('VBAT_SENSE', 'B.Cu', vx + 0.485, 118.900, vx, 119.385)

# ---- 3. silk ----
for t in list(b.Drawings()):
    if t.GetClass() != 'PCB_TEXT': continue
    if t.GetText() == '< USB end': t.SetText('ANTENNA end ^')
    if t.GetText() == 'TXV2 Revision A': t.SetText('TXV2 Revision B  2026-09')
ref = [t for t in b.Drawings() if t.GetClass() == 'PCB_TEXT' and t.GetText() == 'ANTENNA end ^'][0]
nt = pcbnew.PCB_TEXT(b); nt.SetText('USB end v'); nt.SetPosition(P(159.4, 152.0)); nt.SetLayer(layer('F.SilkS'))
nt.SetTextSize(ref.GetTextSize()); nt.SetTextThickness(ref.GetTextThickness()); b.Add(nt)
u4t = pcbnew.PCB_TEXT(b); u4t.SetText('2808 right way up, VIN row at the bottom'); u4t.SetPosition(P(119.6, 177.6)); u4t.SetLayer(layer('F.SilkS'))
u4t.SetTextSize(VECTOR2I(MM(0.8), MM(0.8))); u4t.SetTextThickness(MM(0.12)); b.Add(u4t)

# ---- 4. C12: 10 uF input cap for the AMS1117 (U8 pin 3 = +5V, pin 1 = GND) ----
lib = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/Capacitor_SMD.pretty'
c12 = pcbnew.FootprintLoad(lib, 'C_0805_2012Metric')
c12.SetReference('C12'); c12.SetValue('10uF 25V'); c12.SetPosition(P(110.9, 127.0)); c12.SetOrientationDegrees(90)
b.Add(c12)
c12.Reference().SetPosition(P(110.9, 124.9)); c12.Reference().SetTextSize(VECTOR2I(MM(0.7), MM(0.7))); c12.Reference().SetTextThickness(MM(0.1))
pads = sorted(c12.Pads(), key=lambda p: p.GetPosition().y)      # rot 90: pad on the smaller y first
pads[0].SetNet(net('GND')); pads[1].SetNet(net('+5V'))
pa = (pads[0].GetPosition().x/1e6, pads[0].GetPosition().y/1e6); pb = (pads[1].GetPosition().x/1e6, pads[1].GetPosition().y/1e6)
seg('GND', 'F.Cu', pa[0], pa[1], 111.9, 125.05); seg('GND', 'F.Cu', 111.9, 125.05, 112.9, 124.9)
seg('+5V', 'F.Cu', pb[0], pb[1], 111.9, 128.95); seg('+5V', 'F.Cu', 111.9, 128.95, 112.9, 129.1)
print('C12 pads at', pa, pb)

# ---- zones + save ----
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
print('saved', dst)
