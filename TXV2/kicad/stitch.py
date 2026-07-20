import pcbnew, math, sys
b = pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
FCu, BCu = pcbnew.F_Cu, pcbnew.B_Cu
mm = pcbnew.FromMM
V = pcbnew.VECTOR2I
gnd = b.GetNetcodeFromNetname('GND')
def width_of(t):
    try: return t.GetWidth()
    except Exception:
        try: return t.GetWidth(FCu)
        except Exception: return mm(0.7)
def seg_dist(p, a, c):
    ax, ay, cx, cy, px, py = a.x, a.y, c.x, c.y, p.x, p.y
    dx, dy = cx - ax, cy - ay
    L2 = dx*dx + dy*dy
    if L2 == 0: return math.hypot(px-ax, py-ay)
    t = max(0, min(1, ((px-ax)*dx + (py-ay)*dy) / L2))
    return math.hypot(px-(ax+t*dx), py-(ay+t*dy))
tracks = [(t.GetStart(), t.GetEnd(), t.GetLayerSet(), t.GetNetCode(), width_of(t)) for t in b.Tracks()]
pads = [(p.GetPosition(), p.GetNetCode()) for f in b.Footprints() for p in f.Pads()]
def free_spot(pos):
    for r in (1.6, 2.0, 2.6, 3.2):
        for ang in range(0, 360, 30):
            c = V(pos.x + int(mm(r)*math.cos(math.radians(ang))), pos.y + int(mm(r)*math.sin(math.radians(ang))))
            ok = all(seg_dist(c, s, e) >= mm(0.65) + w/2 for s, e, ls, net, w in tracks if net != gnd)
            if ok: ok = all(math.hypot(pp.x-c.x, pp.y-c.y) >= mm(1.3) for pp, net in pads if net != gnd)
            if ok and 100.8 < c.x/1e6 < 182.5 and 100.8 < c.y/1e6 < 190.9: return c
    return None
def track_clear(a, c, layer):
    for s, e, ls, net, w in tracks:
        if net == gnd or not ls.Contains(layer): continue
        if min(seg_dist(a,s,e), seg_dist(c,s,e), seg_dist(s,a,c), seg_dist(e,a,c)) < mm(0.45) + w/2:
            return False
    return True
added, failed = 0, []
targets = [("C1","2"),("U7","3"),("U7","19"),("U7","20"),("U7","24"),("R8","2"),("J6","4"),
           ("J14","2"),("R16","2"),("C8","2"),("D1","2"),("J9","9"),("J1","A1"),("U2","22"),
           ("U1","39"),("R5","2"),("R6","2"),("R7","2"),("C7","2"),("J10","9"),("J5","2"),
           ("J17","2"),("J13","1"),("J3","2"),("J4","2"),("U4","2"),("U5","2")]
for ref, num in targets:
    fp = b.FindFootprintByReference(ref)
    if not fp: failed.append(ref); continue
    pad = next((p for p in fp.Pads() if p.GetNumber() == num), None)
    if not pad or pad.GetNetCode() != gnd: continue
    pos = pad.GetPosition()
    spot = free_spot(pos)
    if spot is None: failed.append(ref+"?"); continue
    layer = BCu if (pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and pad.IsOnLayer(BCu)) else FCu
    if not track_clear(pos, spot, layer): failed.append(ref+"!"); continue
    t = pcbnew.PCB_TRACK(b); t.SetStart(pos); t.SetEnd(spot); t.SetLayer(layer)
    t.SetWidth(mm(0.35)); t.SetNetCode(gnd); b.Add(t)
    v = pcbnew.PCB_VIA(b); v.SetPosition(spot); v.SetDrill(mm(0.35)); v.SetWidth(mm(0.7))
    v.SetLayerPair(FCu, BCu); v.SetNetCode(gnd); b.Add(v)
    tracks.append((pos, spot, None, gnd, mm(0.35)))
    added += 1
fixed = 0
for f in b.Footprints():
    for item in f.GraphicalItems():
        if isinstance(item, pcbnew.PCB_TEXT) and item.GetLayer() in (pcbnew.B_SilkS, pcbnew.B_Fab):
            if not item.IsMirrored(): item.SetMirrored(True); fixed += 1
    for fld in [f.Reference(), f.Value()]:
        if fld.GetLayer() in (pcbnew.B_SilkS, pcbnew.B_Fab) and not fld.IsMirrored():
            fld.SetMirrored(True); fixed += 1
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb', b)
sys.stdout.write(f"RESULT stitches={added} failed={failed} texts={fixed}\n")
