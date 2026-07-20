import pcbnew, math, json
b = pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
FCu,BCu = pcbnew.F_Cu, pcbnew.B_Cu
mm=pcbnew.FromMM; V=pcbnew.VECTOR2I
gnd=b.GetNetcodeFromNetname('GND')
def wof(t):
    try:return t.GetWidth()
    except:
        try:return t.GetWidth(FCu)
        except:return mm(0.7)
def seg_dist(p,a,c):
    ax,ay,cx,cy,px,py=a.x,a.y,c.x,c.y,p.x,p.y; dx,dy=cx-ax,cy-ay; L2=dx*dx+dy*dy
    if L2==0:return math.hypot(px-ax,py-ay)
    t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/L2));return math.hypot(px-(ax+t*dx),py-(ay+t*dy))
d=json.load(open('drc.json'))
tracks=[(t.GetStart(),t.GetEnd(),t.GetNetCode(),wof(t)) for t in b.Tracks() if t.GetClass()=='PCB_TRACK']
pads=[(p.GetPosition(),p.GetNetCode()) for f in b.Footprints() for p in f.Pads()]
def free(pos):
    for r in [1.2+0.2*i for i in range(10)]:
        for a in range(0,360,20):
            c=V(pos.x+int(mm(r)*math.cos(math.radians(a))),pos.y+int(mm(r)*math.sin(math.radians(a))))
            if all(seg_dist(c,s,e)>=mm(0.6)+w/2 for s,e,net,w in tracks if net!=gnd) and \
               all(math.hypot(pp.x-c.x,pp.y-c.y)>=mm(0.85) for pp,net in pads if net!=gnd) and \
               mm(101)<c.x<mm(182) and mm(101)<c.y<mm(190): return c
    return None
def via(p):
    v=pcbnew.PCB_VIA(b);v.SetPosition(p);v.SetDrill(mm(0.35));v.SetWidth(mm(0.7));v.SetLayerPair(FCu,BCu);v.SetNetCode(gnd);b.Add(v)
def track(a,c,layer):
    t=pcbnew.PCB_TRACK(b);t.SetStart(a);t.SetEnd(c);t.SetLayer(layer);t.SetWidth(mm(0.3));t.SetNetCode(gnd);b.Add(t)
n=0
for v in d.get('unconnected_items',[]):
    for it in v['items']:
        if 'Pad' not in it.get('description','') or 'GND' not in it.get('description',''): continue
        px,py=mm(it['pos']['x']),mm(it['pos']['y'])
        # find the pad
        pad=None
        for f in b.Footprints():
            for p in f.Pads():
                if abs(p.GetPosition().x-px)<mm(0.06) and abs(p.GetPosition().y-py)<mm(0.06) and p.GetNetCode()==gnd:
                    pad=p
        if not pad: continue
        pos=pad.GetPosition()
        if pad.GetAttribute()!=pcbnew.PAD_ATTRIB_SMD:
            via(pos)  # THT pad: via at pad connects to In1 GND plane
        else:
            spot=free(pos)
            if spot:
                lay=BCu if pad.IsOnLayer(BCu) else FCu
                track(pos,spot,lay); via(spot)
        n+=1; break
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb',b)
print("RESULT stitched",n)
