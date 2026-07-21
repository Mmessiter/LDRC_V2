import pcbnew
b=pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
mm=pcbnew.FromMM; V=pcbnew.VECTOR2I
# ref: (x, y, size) — label positions chosen clear of bodies/neighbours
MOVES={
 # back charger cluster: row1 caps above, row2 caps below, resistor row alternating
 'C1':(129,119.8,0.65),'C2':(132,119.8,0.65),'C3':(135,119.8,0.65),'C4':(138,119.8,0.65),
 'C5':(129,128.4,0.65),'C6':(132,128.4,0.65),'C7':(135,128.4,0.65),
 'R6':(129,130.8,0.65),'R4':(132,135.2,0.65),'R5':(135,130.8,0.65),'R1':(138,135.2,0.65),
 'R9':(136,152.9,0.65),'R10':(139,157.3,0.65),'R7':(138,160.8,0.65),'R8':(129,161.3,0.65),
 'R12':(152,152.9,0.65),'R13':(156,157.3,0.65),'R2':(129,152.9,0.65),'R3':(140.6,150,0.65),
 'R14':(171.4,112,0.65),
 'L1':(132,153.9,0.8),
 'D3':(154,134.3,0.8),'D4':(154,125.7,0.8),
 'J1':(150,182.9,0.8),          # USB-C name back on the board
 # front
 'U3':(110.7,116.2,0.8),        # nRF24L01 under its socket, clear
 'U8':(116.5,123.8,0.7),        # AMS1117 above its body, off the TRIMS housing
 'C8':(119,141.6,0.8),          # 220uF below the can
}
HIDE=['H1','H2','H3','H4']       # M3 labels: obvious holes, labels fell off-board
moved=0
for f in b.Footprints():
    r=f.GetReference()
    if r in MOVES:
        x,y,s=MOVES[r]; v=f.Value()
        v.SetPosition(V(int(mm(x)),int(mm(y))))
        v.SetTextSize(V(int(mm(s)),int(mm(s)))); v.SetTextThickness(int(mm(0.13)))
        v.SetTextAngle(pcbnew.EDA_ANGLE(0))     # horizontal, readable
        moved+=1
    if r in HIDE:
        f.Value().SetVisible(False); moved+=1
# move the E01 overhang note clear of the nRF24L01 name
for d in b.GetDrawings():
    if isinstance(d,pcbnew.PCB_TEXT) and 'E01' in d.GetText():
        d.SetPosition(V(int(mm(104)),int(mm(118.7)))); moved+=1
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb',b); print('adjusted',moved,'labels')
