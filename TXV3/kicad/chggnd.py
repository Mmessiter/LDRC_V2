import pcbnew, math
b=pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
FCu,BCu=pcbnew.F_Cu,pcbnew.B_Cu; mm=pcbnew.FromMM; V=pcbnew.VECTOR2I
gnd=b.GetNetcodeFromNetname('GND')
def wof(t):
    try:return t.GetWidth()
    except:
        try:return t.GetWidth(FCu)
        except:return mm(0.7)
# remove my short GND helper tracks in the charger area that cause clearance
rm=0
for t in list(b.Tracks()):
    if t.GetClass()=='PCB_TRACK' and t.GetNetCode()==gnd and t.GetLayer()==BCu and wof(t)<=mm(0.35):
        p=t.GetStart()
        if mm(127)<p.x<mm(135) and mm(135)<p.y<mm(141): b.Remove(t);rm+=1
def via(x,y):
    v=pcbnew.PCB_VIA(b);v.SetPosition(V(int(mm(x)),int(mm(y))));v.SetDrill(mm(0.3));v.SetWidth(mm(0.6));v.SetLayerPair(FCu,BCu);v.SetNetCode(gnd);b.Add(v)
# drop a via on each stranded GND pad -> reaches In1 GND plane
added=0
for f in b.Footprints():
    for p in f.Pads():
        if p.GetNetCode()!=gnd: continue
        pos=p.GetPosition(); x,y=pos.x/1e6,pos.y/1e6
        ref=f.GetReference()
        # QFN charger GND pads + 2808 + DevKitC + USB grounds in the dense back area
        if ref in('U7','U4','U2','J1','C1','C2','C3','C4','C7','R8') and 125<x<150 and 125<y<190:
            # place via slightly offset toward a clear direction (avoid the pad's own trace)
            via(x, y)  # via on pad centre connects pad(any layer) to In1 plane
            added+=1
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb',b)
print("RESULT removed",rm,"vias",added)
