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
    dx, dy = cx-ax, cy-ay
    L2 = dx*dx + dy*dy
    if L2 == 0: return math.hypot(px-ax, py-ay)
    t = max(0, min(1, ((px-ax)*dx + (py-ay)*dy)/L2))
    return math.hypot(px-(ax+t*dx), py-(ay+t*dy))
tracks = [(t.GetStart(), t.GetEnd(), t.GetLayerSet(), t.GetNetCode(), width_of(t)) for t in b.Tracks()]
def clear(a, c, layer, margin=0.4):
    for s, e, ls, net, w in tracks:
        if net == gnd: continue
        if ls is not None and not ls.Contains(layer): continue
        if min(seg_dist(a,s,e), seg_dist(c,s,e), seg_dist(s,a,c), seg_dist(e,a,c)) < mm(margin) + w/2:
            return False
    return True
def pad(ref, num):
    fp = b.FindFootprintByReference(ref)
    return next(p for p in fp.Pads() if p.GetNumber() == num)
def add_track(a, c, layer, w=0.25):
    t = pcbnew.PCB_TRACK(b); t.SetStart(a); t.SetEnd(c); t.SetLayer(layer)
    t.SetWidth(mm(w)); t.SetNetCode(gnd); b.Add(t)
    tracks.append((a, c, None, gnd, mm(w)))
# QFN corner GND pads -> the exposed pad (all on B.Cu, tiny direct runs)
ep = pad('U7','25').GetPosition()
done, skip = [], []
for num in ('3','19','20','24'):
    p = pad('U7', num).GetPosition()
    if clear(p, ep, BCu, 0.15):
        add_track(p, ep, BCu, 0.25); done.append('U7.'+num)
    else: skip.append('U7.'+num)
# nearby passives' GND ends -> chain toward the EP or one another
links = [('C1','2','C7','2'), ('C7','2','U7','25'), ('R5','2','R6','2'), ('R6','2','U7','25'), ('R7','2','R8','2')]
for r1, n1, r2, n2 in links:
    a, c = pad(r1,n1).GetPosition(), pad(r2,n2).GetPosition()
    if pad(r1,n1).GetNetCode() != gnd or pad(r2,n2).GetNetCode() != gnd: skip.append(r1); continue
    if clear(a, c, BCu, 0.3):
        add_track(a, c, BCu, 0.3); done.append(f'{r1}-{r2}')
    else: skip.append(f'{r1}-{r2}')
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb', b)
sys.stdout.write(f"RESULT done={done} skip={skip}\n")
