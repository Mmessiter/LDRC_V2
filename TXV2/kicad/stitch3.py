import pcbnew, math, sys, json
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
def pad(ref, num):
    fp = b.FindFootprintByReference(ref)
    return next(p for p in fp.Pads() if p.GetNumber() == num)
# 1) rework the 4 EP links: delete my straight links, re-add to nearest EP corner, w=0.2
ep = pad('U7','25').GetPosition()
corners = {}
for num in ('3','19','20','24'): corners[pad('U7',num).GetPosition().__str__()] = None
todel = []
for t in b.Tracks():
    if t.GetClass() == 'PCB_TRACK' and t.GetNetCode() == gnd and t.GetLayer() == BCu and width_of(t) == mm(0.25):
        if t.GetEnd() == ep or t.GetStart() == ep: todel.append(t)
for t in todel: b.Remove(t)
for num in ('3','19','20','24'):
    p = pad('U7', num).GetPosition()
    cx = ep.x + (mm(1.1) if p.x > ep.x else -mm(1.1))
    cy = ep.y + (mm(1.1) if p.y > ep.y else -mm(1.1))
    c = V(cx, cy)
    t = pcbnew.PCB_TRACK(b); t.SetStart(p); t.SetEnd(c); t.SetLayer(BCu)
    t.SetWidth(mm(0.2)); t.SetNetCode(gnd); b.Add(t)
# 2) remaining stranded GND pads: aggressive free-spot search
tracks = [(t.GetStart(), t.GetEnd(), t.GetLayerSet(), t.GetNetCode(), width_of(t)) for t in b.Tracks()]
pads = [(p.GetPosition(), p.GetNetCode()) for f in b.Footprints() for p in f.Pads()]
def free_spot(pos):
    for r in [1.2+0.2*i for i in range(12)]:
        for ang in range(0, 360, 15):
            c = V(pos.x + int(mm(r)*math.cos(math.radians(ang))), pos.y + int(mm(r)*math.sin(math.radians(ang))))
            ok = all(seg_dist(c, s, e) >= mm(0.62) + w/2 for s, e, ls, net, w in tracks if net != gnd)
            if ok: ok = all(math.hypot(pp.x-c.x, pp.y-c.y) >= mm(1.25) for pp, net in pads if net != gnd)
            if ok and 100.8 < c.x/1e6 < 182.5 and 100.8 < c.y/1e6 < 190.9: return c
    return None
def clear(a, c, layer, margin=0.35):
    for s, e, ls, net, w in tracks:
        if net == gnd: continue
        if ls is not None and not ls.Contains(layer): continue
        if min(seg_dist(a,s,e), seg_dist(c,s,e), seg_dist(s,a,c), seg_dist(e,a,c)) < mm(margin)+w/2: return False
    return True
added, fail = [], []
for ref, num in [("C1","2"),("C7","2"),("R5","2"),("R6","2"),("R7","2"),("D2","1"),("R16","2"),
                 ("C11","2"),("C9","2"),("C10","2"),("U8","1"),("J12","1"),("BT1","2")]:
    try: p = pad(ref, num)
    except Exception: continue
    if p.GetNetCode() != gnd: continue
    pos = p.GetPosition()
    spot = free_spot(pos)
    layer = BCu if (p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and p.IsOnLayer(BCu)) else \
            (FCu if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD else FCu)
    if spot and clear(pos, spot, layer):
        t = pcbnew.PCB_TRACK(b); t.SetStart(pos); t.SetEnd(spot); t.SetLayer(layer)
        t.SetWidth(mm(0.3)); t.SetNetCode(gnd); b.Add(t)
        v = pcbnew.PCB_VIA(b); v.SetPosition(spot); v.SetDrill(mm(0.35)); v.SetWidth(mm(0.7))
        v.SetLayerPair(FCu, BCu); v.SetNetCode(gnd); b.Add(v)
        tracks.append((pos, spot, None, gnd, mm(0.3)))
        added.append(ref)
    else: fail.append(ref)
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb', b)
print("RESULT", added, fail)
