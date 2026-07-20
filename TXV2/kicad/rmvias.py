import pcbnew
b = pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
mm = pcbnew.FromMM
bad = [tuple(map(float, l.split())) for l in open('badvias.txt')]
removed = 0
for t in list(b.Tracks()):
    if t.GetClass() != 'PCB_VIA': continue
    p = t.GetPosition()
    for x, y in bad:
        if abs(p.x - mm(x)) < mm(0.05) and abs(p.y - mm(y)) < mm(0.05):
            b.Remove(t); removed += 1; break
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb', b)
print("RESULT removed", removed)
