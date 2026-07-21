import pcbnew, json, math
b=pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
mm=pcbnew.FromMM; V=pcbnew.VECTOR2I; FCu,BCu=pcbnew.F_Cu,pcbnew.B_Cu
gnd=b.GetNetcodeFromNetname('GND')
snap=json.load(open('label_snapshot.json'))
# label overrides (Malcolm's latest round) — win over the snapshot
OVR={'U4':(119.6,174.85,0.9),'J14':(121.4,111.3,0.8),'U3':(115.5,116.3,0.8),'L1':(132,144.3,0.8),'J5':(158.4,183.9,0.9),
     'J17':(168.6,183.9,0.9),'J13':(132.8,168.5,0.8),'J3':(171.2,179.5,0.9)}
UNHIDE={'J13'}
for f in b.Footprints():
    r=f.GetReference(); v=f.Value()
    if r in OVR:
        x,y,s=OVR[r]; v.SetVisible(True)
        v.SetPosition(V(int(mm(x)),int(mm(y))))
        v.SetTextSize(V(int(mm(s)),int(mm(s)))); v.SetTextThickness(int(mm(0.13)))
        v.SetTextAngle(pcbnew.EDA_ANGLE(-f.GetOrientation().AsDegrees()))
    elif r in snap['values']:
        sv=snap['values'][r]
        if sv.get('vis'):
            v.SetVisible(True)
            v.SetPosition(V(int(mm(sv['x'])),int(mm(sv['y']))))
            v.SetTextSize(V(int(mm(sv['size'])),int(mm(sv['size'])))); v.SetTextThickness(int(mm(0.13)))
            v.SetTextAngle(pcbnew.EDA_ANGLE(-f.GetOrientation().AsDegrees()))
        else:
            v.SetVisible(False)
# gr_text moves + adds
for d in b.GetDrawings():
    if isinstance(d,pcbnew.PCB_TEXT) and 'E01' in d.GetText():
        d.SetPosition(V(int(mm(107)),int(mm(102.4))))
def gt(txt,x,y,s=0.55):
    t=pcbnew.PCB_TEXT(b);t.SetText(txt);t.SetPosition(V(int(mm(x)),int(mm(y))))
    t.SetLayer(pcbnew.F_SilkS);t.SetTextSize(V(int(mm(s)),int(mm(s))));t.SetTextThickness(int(mm(0.11)))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT); b.Add(t)
gt("square pad = GND",110.5,118.3)
gt("3V3",110.2,147); gt("GND",110.2,154.7)      # GIMBAL R (J6) rail ends
gt("3V3",110.2,162); gt("GND",110.2,174.7)      # KNOBS rail ends
gt("GND",110.2,140.2)                            # TRIMS GND end
gt("GND",139.2,183.3,0.5)                        # SWITCHES GND end
gt("3V3",173.2,124,0.55); gt("GND",173.2,131.7,0.55)  # GIMBAL L (J7) rail ends
gt("+",144.8,180.2,0.7); gt("+",150.7,180.2,0.7)      # LED anodes (pad 2 side)
for y1,y2,y3 in [(156,153.46,150.92),(164,161.46,158.92)]:
    gt("IN",112.4,y1); gt("GND",112.4,y2); gt("OUT",112.4,y3)
# QFN thermal vias to JLC 0.3 + islands
u7=b.FindFootprintByReference('U7')
for p in u7.Pads():
    if p.GetNumber()=='25' and p.GetDrillSize().x<mm(0.3):
        p.SetDrillSize(V(int(mm(0.3)),int(mm(0.3))))
        if p.GetSizeX()<mm(0.5): p.SetSize(V(int(mm(0.5)),int(mm(0.5))))
for z in b.Zones(): z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
# mirror all back text
BACK={pcbnew.B_SilkS,pcbnew.B_Fab,pcbnew.B_Cu}
for f in b.Footprints():
    for it in [f.Reference(),f.Value()]+list(f.GraphicalItems()):
        if isinstance(it,(pcbnew.PCB_TEXT,pcbnew.PCB_FIELD)) and it.GetLayer() in BACK and not it.IsMirrored():
            it.SetMirrored(True)
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb',b); print('POSTFIX DONE')
