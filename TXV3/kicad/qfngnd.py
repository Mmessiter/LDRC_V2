import pcbnew, math
b=pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
FCu,BCu=pcbnew.F_Cu,pcbnew.B_Cu; mm=pcbnew.FromMM; V=pcbnew.VECTOR2I
gnd=b.GetNetcodeFromNetname('GND')
u7=b.FindFootprintByReference('U7')
pads={p.GetNumber():p for p in u7.Pads()}
ep=pads['25'].GetPosition()
def track(a,c,w=0.25):
    t=pcbnew.PCB_TRACK(b);t.SetStart(a);t.SetEnd(c);t.SetLayer(BCu);t.SetWidth(mm(w));t.SetNetCode(gnd);b.Add(t)
def via(p,drill=0.3,w=0.55):
    v=pcbnew.PCB_VIA(b);v.SetPosition(p);v.SetDrill(mm(drill));v.SetWidth(mm(w));v.SetLayerPair(FCu,BCu);v.SetNetCode(gnd);b.Add(v)
# tie each stranded QFN GND pin to the exposed pad
for n in ('3','19','20','24'):
    if n in pads: track(pads[n].GetPosition(), ep, 0.25)
# vias on the EP into the In1 plane (EP is ~2.6mm, room for a couple)
via(ep)
via(V(ep.x+int(mm(0.7)), ep.y+int(mm(0.7))))
via(V(ep.x-int(mm(0.7)), ep.y-int(mm(0.7))))
# J1 USB shield GND: via next to pad A1
j1=b.FindFootprintByReference('J1')
a1=next((p for p in j1.Pads() if p.GetNumber()=='A1'), None)
if a1:
    pos=a1.GetPosition(); via(V(pos.x, pos.y+int(mm(1.2))))
    track(pos, V(pos.x, pos.y+int(mm(1.2))), 0.3)
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb',b)
print("RESULT qfn+ep+j1 grounded")
