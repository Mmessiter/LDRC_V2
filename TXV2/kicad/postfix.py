import pcbnew, json
b=pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
mm=pcbnew.FromMM; V=pcbnew.VECTOR2I; FCu,BCu=pcbnew.F_Cu,pcbnew.B_Cu
snap=json.load(open('label_snapshot.json'))
OVR={'U4':(119.6,174.85,0.9),'L1':(127.8,148.5,0.7),'J5':(158.4,183.9,0.9),
     'J13':(132.8,168.5,0.8),'J3':(171.2,179.5,0.9),
     'J14':(119.5,123.9,0.7),'U3':(112.6,106.3,0.7),'U8':(113.8,131.2,0.7),'R6':(130.5,143.5,0.6),'U7':(136.9,144.2,0.8),'R14':(174,115.4,0.65),'J17':(170.7,182.8,0.7)}
SKIP={'J6','J7','J11'}   # names live in board gr_texts, values stay hidden
for f in b.Footprints():
    r=f.GetReference(); v=f.Value()
    if r in SKIP: continue
    if r in OVR:
        x,y,s=OVR[r]; v.SetVisible(True)
        v.SetLayer(pcbnew.B_SilkS if f.GetLayer()==pcbnew.B_Cu else pcbnew.F_SilkS)
        v.SetPosition(V(int(mm(x)),int(mm(y))))
        v.SetTextSize(V(int(mm(s)),int(mm(s)))); v.SetTextThickness(int(mm(0.13)))
        v.SetTextAngle(pcbnew.EDA_ANGLE(0))
    elif r in snap['values']:
        sv=snap['values'][r]
        if sv.get('vis'):
            v.SetVisible(True)
            v.SetPosition(V(int(mm(sv['x'])),int(mm(sv['y']))))
            v.SetTextSize(V(int(mm(sv['size'])),int(mm(sv['size'])))); v.SetTextThickness(int(mm(0.13)))
            v.SetTextAngle(pcbnew.EDA_ANGLE(0))
        else:
            v.SetVisible(False)
# back-cluster labels track their (shifted) parts in x
BACKROW={'C1','C2','C3','C4','C5','C6','C7','R1','R4','R5','R6'}
for f in b.Footprints():
    r=f.GetReference()
    if r in BACKROW and r in snap['values'] and snap['values'][r].get('vis'):
        v=f.Value()
        v.SetPosition(V(f.GetPosition().x,int(mm(snap['values'][r]['y']))))
def gt(txt,x,y,s=0.5,left=True,right=False):
    t=pcbnew.PCB_TEXT(b);t.SetText(txt);t.SetPosition(V(int(mm(x)),int(mm(y))))
    t.SetLayer(pcbnew.F_SilkS);t.SetTextSize(V(int(mm(s)),int(mm(s))));t.SetTextThickness(int(mm(0.1)))
    if right: t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    elif left: t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    b.Add(t)
# nRF marker
gt("square pad = GND",105.2,114.6,0.5)
# buck pin marks (bucks now at x113 -> marks at x114.4)
for y1,y2,y3 in [(156,153.46,150.92),(164,161.46,158.92)]:
    gt("IN",114.7,y1,0.55); gt("GND",114.7,y2,0.55); gt("OUT",114.7,y3,0.55)
# per-pin labels — left-edge connectors (labels right of pads at x110.4)
for y,txt in zip([147,149.5,152,154.5],["3V3","V","H","GND"]): gt(txt,110.3,y,0.5,right=True)   # GIMBAL R (J6)
for i,txt in enumerate(["3V3","5","6","7","8","GND"]): gt(txt,110.3,162+2.5*i,0.5,right=True)   # KNOBS
TRIMN=["1L","1R","2U","2D","3U","3D","4R","4L"]
for i in range(8): gt(TRIMN[i],110.3,120+2.5*i,0.45,right=True)                          # TRIMS by channel
gt("GND",110.3,140,0.45,right=True)                                                          # TRIMS GND
# right-edge connectors (labels left of pads)
for y,txt in zip([124,126.5,129,131.5],["3V3","V","H","GND"]): gt(txt,172.9,y,0.5)          # GIMBAL L (J7)
for y,txt in zip([111,113.5,116],["5V","DAT","GND"]): gt(txt,174.6,y,0.45,right=True)       # RGB LED
for y,txt in zip([139,141.54,144.08,146.62,149.16],["GND","-","5V","RX","TX"]): gt(txt,172.6,y,0.5)  # NEXTION
# SWITCHES pin digits + GND
for i in range(8): gt(str(i+1),119.6+2.525*i,183.5,0.45)
gt("GND",138.9,183.5,0.45)
# C9/C10 + divider values (hidden footprint values -> explicit marks)
gt("10uF",110.9,117.3,0.5,right=True)
gt("100n",114.6,119.6,0.5,left=False)
gt("47k",116,144.6,0.55); gt("15k",119,144.6,0.55); gt("100n",122.2,144.6,0.55)
# TX MODULE pin marks
gt("SIG",167.9,184.2,0.45); gt("BAT",170.4,184.2,0.45); gt("GND",172.8,184.2,0.45)
# ESP spare GPIO numbers
GA=["4","5","6","7","15","16","3","46","10","11","12","13"]
GB=["14","1","2","42","41","40","39","21","45","47","48","3V"]
for i in range(12):
    t=pcbnew.PCB_TEXT(b);t.SetText(GA[i]);t.SetPosition(V(int(mm(145.8+2.536*i)),int(mm(161.7))))
    t.SetLayer(pcbnew.F_SilkS);t.SetTextSize(V(int(mm(0.45)),int(mm(0.45))));t.SetTextThickness(int(mm(0.1)));b.Add(t)
    t=pcbnew.PCB_TEXT(b);t.SetText(GB[i]);t.SetPosition(V(int(mm(145.8+2.536*i)),int(mm(168.5))))
    t.SetLayer(pcbnew.F_SilkS);t.SetTextSize(V(int(mm(0.45)),int(mm(0.45))));t.SetTextThickness(int(mm(0.1)));b.Add(t)
# I2C + BAL + RTC pin marks
for y,txt in zip([172.5,175,177.5,180],["G","3V","SD","SC"]): gt(txt,134.4,y,0.45)
gt("MID",139.6,170.6,0.5); gt("GND",142.6,170.6,0.5)
gt("+",117.4,117.5,0.5)   # RTC pin1 = coin-cell +
# LED anodes
gt("+",144.8,180.2,0.7); gt("+",150.7,180.2,0.7)
# QFN thermal drills + islands + back mirror
u7=b.FindFootprintByReference('U7')
for p in u7.Pads():
    if p.GetNumber()=='25' and p.GetDrillSize().x<mm(0.3):
        p.SetDrillSize(V(int(mm(0.3)),int(mm(0.3))))
        if p.GetSizeX()<mm(0.5): p.SetSize(V(int(mm(0.5)),int(mm(0.5))))
for z in b.Zones(): z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
BACK={pcbnew.B_SilkS,pcbnew.B_Fab,pcbnew.B_Cu}
for f in b.Footprints():
    for it in [f.Reference(),f.Value()]+list(f.GraphicalItems()):
        if isinstance(it,(pcbnew.PCB_TEXT,pcbnew.PCB_FIELD)) and it.GetLayer() in BACK and not it.IsMirrored():
            it.SetMirrored(True)
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb',b); print('POSTFIX DONE')
