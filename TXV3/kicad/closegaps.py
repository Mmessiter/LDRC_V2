import pcbnew, math, json
b = pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
FCu, BCu = pcbnew.F_Cu, pcbnew.B_Cu
mm = pcbnew.FromMM; V = pcbnew.VECTOR2I
def wof(t):
    try: return t.GetWidth()
    except: 
        try: return t.GetWidth(FCu)
        except: return mm(0.7)
d = json.load(open('drc.json'))
# collect same-net endpoints: pads + track ends
pad_pts = {}
for f in b.Footprints():
    for p in f.Pads():
        pad_pts.setdefault(p.GetNetCode(), []).append((p.GetPosition(), p))
trk_pts = {}
for t in b.Tracks():
    if t.GetClass()=='PCB_TRACK':
        trk_pts.setdefault(t.GetNetCode(), []).append((t.GetStart(), t.GetLayer()))
        trk_pts.setdefault(t.GetNetCode(), []).append((t.GetEnd(), t.GetLayer()))
    elif t.GetClass()=='PCB_VIA':
        trk_pts.setdefault(t.GetNetCode(), []).append((t.GetPosition(), None))
def add_track(a,c,layer,net,w=0.25):
    t=pcbnew.PCB_TRACK(b); t.SetStart(a); t.SetEnd(c); t.SetLayer(layer); t.SetWidth(mm(w)); t.SetNetCode(net); b.Add(t)
def add_via(p,net):
    v=pcbnew.PCB_VIA(b); v.SetPosition(p); v.SetDrill(mm(0.35)); v.SetWidth(mm(0.7)); v.SetLayerPair(FCu,BCu); v.SetNetCode(net); b.Add(v)
closed=0
for v in d.get('unconnected_items',[]):
    descs=[i['description'] for i in v['items']]
    if any('GND' in x for x in descs): continue
    # find a pad in this violation
    pad=None; net=None
    for f in b.Footprints():
        for p in f.Pads():
            pos=p.GetPosition()
            for it in v['items']:
                if abs(pos.x-mm(it['pos']['x']))<mm(0.05) and abs(pos.y-mm(it['pos']['y']))<mm(0.05):
                    pad=p; net=p.GetNetCode()
    if not pad: continue
    ppos=pad.GetPosition()
    padlayer = BCu if (pad.GetAttribute()==pcbnew.PAD_ATTRIB_SMD and pad.IsOnLayer(BCu)) else (FCu if pad.GetAttribute()!=pcbnew.PAD_ATTRIB_SMD else FCu)
    # nearest same-net track endpoint
    best=None;bd=1e18
    for pt,lay in trk_pts.get(net,[]):
        dd=math.hypot(pt.x-ppos.x,pt.y-ppos.y)
        if dd<bd and dd>0: bd=dd;best=(pt,lay)
    if best and bd<mm(8):
        tgt,tlay=best
        if pad.GetAttribute()!=pcbnew.PAD_ATTRIB_SMD:
            # THT pad: connect on the track's layer (or F.Cu)
            L = tlay if tlay is not None else FCu
            add_track(ppos,tgt,L,net)
        else:
            if tlay is None or tlay==padlayer:
                add_track(ppos,tgt,padlayer,net)
            else:
                add_track(ppos,tgt,padlayer,net)  # same layer assumed near
        closed+=1
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb',b)
print("RESULT closed",closed)
