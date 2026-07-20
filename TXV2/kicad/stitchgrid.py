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
count = 0
for xi in range(0, 23):
    for yi in range(0, 26):
        c = V(int(mm(104 + xi * 3.5)), int(mm(104 + yi * 3.4)))
        if not (mm(101.2) < c.x < mm(182.1) and mm(101.2) < c.y < mm(190.5)): continue
        ok = all(seg_dist(c, s, e) >= mm(0.62) + w/2 for s, e, net, w in tracks if net != gnd)
        if ok: ok = all(math.hypot(pp.x-c.x, pp.y-c.y) >= mm(0.85) + r for pp, net, r in pads if net != gnd)
        if ok: ok = all(math.hypot(pp.x-c.x, pp.y-c.y) >= mm(0.8) for pp, net, r in pads if net == gnd)
        if ok:
            v = pcbnew.PCB_VIA(b); v.SetPosition(c); v.SetDrill(mm(0.35)); v.SetWidth(mm(0.7))
            v.SetLayerPair(FCu, BCu); v.SetNetCode(gnd); b.Add(v)
            tracks.append((c, c, gnd, mm(0.7)))
            count += 1
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb', b)
print("RESULT vias", count)
