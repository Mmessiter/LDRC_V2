import pcbnew, math
b=pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
mm=pcbnew.FromMM; V=pcbnew.VECTOR2I; FCu,BCu=pcbnew.F_Cu,pcbnew.B_Cu
gnd=b.GetNetcodeFromNetname('GND')
def wof(t):
    try:return t.GetWidth()
    except:
        try:return t.GetWidth(FCu)
        except:return mm(0.7)
# ground the USB shield pads (correct electrically, kills the graze error)
j1=b.FindFootprintByReference('J1'); shp=[]
for p in j1.Pads():
    if p.GetNumber()=='SH': p.SetNetCode(gnd); shp.append(1)
print('shield pads grounded:',len(shp))
POS={}
for f in b.Footprints():
    r=f.GetReference()
    if r in ('R7','C7'):
        for p in f.Pads(): POS[(r,p.GetNumber())]=p.GetPosition()
TR=[(t.GetStart(),t.GetEnd(),t.GetNetCode(),wof(t)) for t in b.Tracks() if t.GetClass()=='PCB_TRACK']
VI=[(t.GetPosition(),t.GetNetCode()) for t in b.Tracks() if t.GetClass()=='PCB_VIA']
PD=[(p.GetPosition(),p.GetNetCode()) for f in b.Footprints() for p in f.Pads()]
def sd(p,a,c):
    ax,ay,cx,cy,px,py=a.x,a.y,c.x,c.y,p.x,p.y;dx,dy=cx-ax,cy-ay;L2=dx*dx+dy*dy
    if L2==0:return math.hypot(px-ax,py-ay)
    t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/L2));return math.hypot(px-(ax+t*dx),py-(ay+t*dy))
def via_ok(c):
    return (all(sd(c,s,e)>=mm(0.55)+w/2 for s,e,nc,w in TR if nc!=gnd) and
            all(math.hypot(vp.x-c.x,vp.y-c.y)>=mm(0.98) for vp,nc in VI if nc!=gnd) and
            all(math.hypot(pp.x-c.x,pp.y-c.y)>=mm(1.33) for pp,nc in PD if nc!=gnd) and
            mm(101)<c.x<mm(182.3) and mm(101)<c.y<mm(190.7))
def seg_ok(a,c,w=mm(0.28)):
    for s,e,nc,tw in TR:
        if nc==gnd: continue
        if min(sd(a,s,e),sd(c,s,e),sd(s,a,c),sd(e,a,c))<mm(0.24)+w/2+tw/2: return False
    for pp,nc in PD:
        if nc==gnd: continue
        if sd(pp,a,c)<mm(0.72): return False
    return True
def add(a,c,w=0.28):
    t=pcbnew.PCB_TRACK(b);t.SetStart(a);t.SetEnd(c);t.SetLayer(BCu);t.SetWidth(mm(w));t.SetNetCode(gnd);b.Add(t); TR.append((a,c,gnd,mm(w)))
def via(p):
    v=pcbnew.PCB_VIA(b);v.SetPosition(p);v.SetDrill(mm(0.3));v.SetWidth(mm(0.55));v.SetLayerPair(FCu,BCu);v.SetNetCode(gnd);b.Add(v); VI.append((p,gnd))
for r in ('R7','C7'):
    pos=POS[(r,'2')]; done=False
    for rad in [0.9+0.12*i for i in range(45)]:
        for ang in range(0,360,10):
            c=V(pos.x+int(mm(rad)*math.cos(math.radians(ang))),pos.y+int(mm(rad)*math.sin(math.radians(ang))))
            if not via_ok(c): continue
            # straight or L-dogleg
            paths=[[pos,c],[pos,V(c.x,pos.y),c],[pos,V(pos.x,c.y),c]]
            for path in paths:
                if all(seg_ok(a,cc) for a,cc in zip(path,path[1:])):
                    for a,cc in zip(path,path[1:]): add(a,cc)
                    via(c); print(r,'via @',round(c.x/1e6,1),round(c.y/1e6,1)); done=True; break
            if done: break
        if done: break
    if not done: print(r,'FAILED')
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb',b); print('SAVED')
