import pcbnew, math
b = pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
FCu, BCu = pcbnew.F_Cu, pcbnew.B_Cu
mm = pcbnew.FromMM; V = pcbnew.VECTOR2I
gnd = b.GetNetcodeFromNetname('GND')
def width_of(t):
    try: return t.GetWidth()
    except Exception:
        try: return t.GetWidth(FCu)
        except Exception: return mm(0.7)
# remove the C10 stitch that crosses +3V3_RF (track start 110.4,124.2-ish) and its via
removed = 0
for t in list(b.Tracks()):
    p = t.GetStart()
    if abs(p.x - mm(110.4)) < mm(0.3) and abs(p.y - mm(125.2)) < mm(1.6) and t.GetNetCode() == gnd:
        b.Remove(t); removed += 1
# remove the via at 144.8,183.2 (too close to USB shell)
for t in list(b.Tracks()):
    if t.GetClass() == 'PCB_VIA':
        p = t.GetPosition()
        if abs(p.x - mm(144.8)) < mm(0.15) and abs(p.y - mm(183.2)) < mm(0.15):
            b.Remove(t); removed += 1
def seg_dist(p, a, c):
    ax, ay, cx, cy, px, py = a.x, a.y, c.x, c.y, p.x, p.y
    dx, dy = cx-ax, cy-ay
    L2 = dx*dx+dy*dy
    if L2 == 0: return math.hypot(px-ax, py-ay)
    t = max(0, min(1, ((px-ax)*dx+(py-ay)*dy)/L2))
    return math.hypot(px-(ax+t*dx), py-(ay+t*dy))
tracks = [(t.GetStart(), t.GetEnd(), t.GetNetCode(), width_of(t)) for t in b.Tracks()]
pads = [(p.GetPosition(), p.GetNetCode(), max(p.GetBoundingBox().GetWidth(), p.GetBoundingBox().GetHeight())/2)
        for f in b.Footprints() for p in f.Pads()]
added = 0
for x, y in [(133.5,120.2),(136,124.6),(130,124.6),(137,129),(133,131.5),(172.5,158.8),(130.5,120.2)]:
    c = V(int(mm(x)), int(mm(y)))
    ok = all(seg_dist(c, s, e) >= mm(0.62) + w/2 for s, e, net, w in tracks if net != gnd)
    if ok: ok = all(math.hypot(pp.x-c.x, pp.y-c.y) >= mm(0.85) + r for pp, net, r in pads if net != gnd)
    if ok:
        v = pcbnew.PCB_VIA(b); v.SetPosition(c); v.SetDrill(mm(0.35)); v.SetWidth(mm(0.7))
        v.SetLayerPair(FCu, BCu); v.SetNetCode(gnd); b.Add(v)
        added += 1
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb', b)
print("RESULT removed", removed, "added", added)
