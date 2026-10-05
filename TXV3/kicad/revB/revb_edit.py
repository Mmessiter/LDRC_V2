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
u4t = pcbnew.PCB_TEXT(b); u4t.SetText('2808 right way up'); u4t.SetPosition(P(119.6, 177.6)); u4t.SetLayer(layer('F.SilkS'))
u4t.SetTextSize(VECTOR2I(MM(0.8), MM(0.8))); u4t.SetTextThickness(MM(0.12)); b.Add(u4t)

# ---- 4. C12: 10 uF input cap for the AMS1117 (U8 pin 3 = +5V, pin 1 = GND) ----
lib = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/Capacitor_SMD.pretty'
c12 = pcbnew.FootprintLoad(lib, 'C_0805_2012Metric')
c12.SetReference('C12'); c12.SetValue('10uF 25V'); c12.SetPosition(P(110.9, 127.0)); c12.SetOrientationDegrees(90)
b.Add(c12)
c12.Reference().SetVisible(False)
pads = sorted(c12.Pads(), key=lambda p: p.GetPosition().y)      # rot 90: pad on the smaller y first
pads[0].SetNet(net('GND')); pads[1].SetNet(net('+5V'))
pa = (pads[0].GetPosition().x/1e6, pads[0].GetPosition().y/1e6); pb = (pads[1].GetPosition().x/1e6, pads[1].GetPosition().y/1e6)
seg('GND', 'F.Cu', pa[0], pa[1], 111.9, 125.05); seg('GND', 'F.Cu', 111.9, 125.05, 112.9, 124.9)
seg('+5V', 'F.Cu', pb[0], pb[1], 111.9, 128.95); seg('+5V', 'F.Cu', 111.9, 128.95, 112.9, 129.1)
print('C12 pads at', pa, pb)

# ---- 5. silk clarity pass (Malcolm 2026-09-06: "abundantly clear which
#         component goes where, and which way round") ----
def text(s, x, y, size=0.6, lay='F.SilkS', mirror=False, thick=0.12):
    t = pcbnew.PCB_TEXT(b); t.SetText(s); t.SetPosition(P(x, y)); t.SetLayer(layer(lay))
    t.SetTextSize(VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(thick))
    if mirror: t.SetMirrored(True)
    b.Add(t); return t
# 5a. every small silk label: at least 0.6 mm high, 0.12 mm stroke (0.45 mm text at 0.1 mm is a smudge)
for t in b.Drawings():
    if t.GetClass() != 'PCB_TEXT' or 'Silk' not in t.GetLayerName(): continue
    if t.GetTextHeight() < MM(0.6): t.SetTextSize(VECTOR2I(MM(0.6), MM(0.6)))
    if t.GetTextThickness() < MM(0.12): t.SetTextThickness(MM(0.12))
    if t.GetText() == 'microSD exits ^ (top edge)': t.SetText('microSD end ^'); t.SetPosition(P(134.35, 105.0))   # the top pads are 2 mm from the edge: sit between the columns instead
    if t.GetText() == 'GND' and abs(t.GetPosition().x/1e6 - 110.3) < 0.05: t.SetPosition(P(110.8, t.GetPosition().y/1e6))   # 3-char label clipped the connector outline
    if t.GetText() == 'GND' and abs(t.GetPosition().x/1e6 - 174.6) < 0.05: t.SetPosition(P(175.1, t.GetPosition().y/1e6))
    if t.GetText() == '+' and abs(t.GetPosition().x/1e6 - 144.8) < 0.05: t.SetPosition(P(144.2, 180.2))   # D1's anode mark sat on the pad
    if t.GetText() == 'by Claude and Malcolm - July 2026': t.SetText('by Claude and Malcolm - 2026'); t.SetPosition(P(159.0, 159.0))
    if t.GetText() == 'ESP SPARE GPIO': t.SetPosition(P(159.0, 159.9))
    if t.GetText() == 'by Claude and Malcolm - 2026': t.SetPosition(P(159.0, 159.0))
    if t.GetText() == '10uF' and abs(t.GetPosition().x/1e6 - 110.9) < 0.05: t.SetPosition(P(110.9, 116.6))
    if t.GetText() == 'RGB LED': t.SetPosition(P(176.0, 118.9))
    # the ESP spare-header pin numbers straddled the header outlines: one row up, one row down
    if abs(t.GetPosition().y/1e6 - 161.7) < 0.05 and 145 < t.GetPosition().x/1e6 < 175: t.SetPosition(P(t.GetPosition().x/1e6, 161.1))
    if abs(t.GetPosition().y/1e6 - 168.5) < 0.05 and 145 < t.GetPosition().x/1e6 < 175: t.SetPosition(P(t.GetPosition().x/1e6, 168.9))
# 5b. the 2808 socket: every pin named on the board, both rows
for i, name in enumerate(['VIN', 'VIN', 'GND', 'GND', 'ON', 'OFF', 'CTRL']):
    text(name, 112.0 + 2.54 * i, 179.1, 0.55)
for i, name in enumerate(['VOUT', 'VOUT', 'GND', 'GND', 'A', 'B']):
    text(name, 112.0 + 2.54 * i, 170.5, 0.55)
# 5c. C12: one line, clear of the trims labels and the AMS1117 pad
text('C12 10uF', 110.9, 123.4, 0.55)
# 5d. the charger chip's pin 1, spelled out beside the footprint's own corner mark (back side, so mirrored)
text('1', 129.2, 137.2, 0.6, 'B.SilkS', mirror=True)
# 5e. D3/D4 are Schottky on Rev-B — say so where the eye lands
for ref in ('D3', 'D4'):
    b.FindFootprintByReference(ref).SetValue('SS14')
# 5f. back-side value labels that sat on a pad edge (they get clipped at the fab): three placed by hand, the rest nudged
for ref, x, y, rot in (('R3', 136.2, 150.0, 90), ('L1', 132.0, 152.1, 0), ('R10', 139.4, 152.87, 0)):
    v = b.FindFootprintByReference(ref).Value(); v.SetPosition(P(x, y)); v.SetTextAngleDegrees(rot)
pads = [(fp.GetReference(), p) for fp in b.GetFootprints() for p in fp.Pads()]
for ref in ('R7', 'R8', 'C2', 'C3', 'C4'):
    fp = b.FindFootprintByReference(ref); v = fp.Value(); vp = v.GetPosition()
    box = v.GetBoundingBox()
    for pref, pad in pads:
        pb = pad.GetBoundingBox()
        if not box.Intersects(pb): continue
        # push out along the shorter escape
        dy_up = (pb.GetTop() - box.GetBottom()) / 1e6; dy_dn = (pb.GetBottom() - box.GetTop()) / 1e6
        shift = dy_up - 0.25 if abs(dy_up) < abs(dy_dn) else dy_dn + 0.25
        v.SetPosition(VECTOR2I(vp.x, vp.y + MM(shift))); vp = v.GetPosition(); box = v.GetBoundingBox()
        print('nudged value of', ref, 'by', round(shift, 2), 'mm (was over pad', pad.GetNumber(), 'of', pref + ')')

# ---- zones + save ----
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
print('saved', dst)
