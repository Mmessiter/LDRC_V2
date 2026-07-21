import pcbnew
b=pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
mm=pcbnew.FromMM; V=pcbnew.VECTOR2I; FCu=pcbnew.F_Cu
vraw=b.GetNetcodeFromNetname('VBAT_RAW'); gnd=b.GetNetcodeFromNetname('GND')
# SNAPSHOT everything before touching the board
tracks=[t for t in b.Tracks()]
drawings=[d for d in b.Drawings()]
j3pads=[p for p in b.FindFootprintByReference('J3').Pads()]
# edits
for d in drawings:
    if isinstance(d,pcbnew.PCB_TEXT) and d.GetText() in ("5V BUCK","5V BUCK-N"):
        d.SetPosition(V(int(mm(116.2)),d.GetPosition().y))
for p in j3pads:
    if p.GetNumber()=='1': p.SetNetCode(gnd)
    if p.GetNumber()=='2': p.SetNetCode(vraw)
removed=0
for t in tracks:
    if t.GetClass()=='PCB_TRACK' and t.GetNetCode()==vraw:
        s,e=t.GetStart(),t.GetEnd()
        if abs(s.x-mm(110.5))<mm(0.3) and abs(s.y-mm(186))<mm(0.3) and abs(e.y-mm(171.5))<mm(0.3):
            b.Remove(t); removed+=1
pts=[V(int(mm(115.5)),int(mm(186))),V(int(mm(115.5)),int(mm(183.5))),
     V(int(mm(110.5)),int(mm(183.5))),V(int(mm(110.5)),int(mm(171.5)))]
for a,c in zip(pts,pts[1:]):
    t=pcbnew.PCB_TRACK(b);t.SetStart(a);t.SetEnd(c);t.SetLayer(FCu);t.SetWidth(mm(0.2));t.SetNetCode(vraw);b.Add(t)
def gt(txt,x,y,s=0.55):
    t=pcbnew.PCB_TEXT(b);t.SetText(txt);t.SetPosition(V(int(mm(x)),int(mm(y))))
    t.SetLayer(pcbnew.F_SilkS);t.SetTextSize(V(int(mm(s)),int(mm(s))));t.SetTextThickness(int(mm(0.11)))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT); b.Add(t)
gt("square pad = GND",107.3,118.2)
for y1,y2,y3 in [(156,153.46,150.92),(164,161.46,158.92)]:
    gt("IN",112.4,y1); gt("GND",112.4,y2); gt("OUT",112.4,y3)
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb',b); print('ALL SAVED removed=%d'%removed)
