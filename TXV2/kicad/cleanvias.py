import pcbnew, json, math
b = pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
mm = pcbnew.FromMM
d = json.load(open('drc.json'))
bad = []
for v in d.get('violations', []):
    if v['type'] in ('via_dangling', 'hole_to_hole', 'hole_clearance'):
        for it in v['items']:
            if 'Via' in it['description']:
                bad.append((it['pos']['x'], it['pos']['y']))
# also drop vias implicated in unconnected pairs (isolated islands)
for v in d.get('unconnected_items', []):
    for it in v['items']:
        if 'Via' in it.get('description',''):
            bad.append((it['pos']['x'], it['pos']['y']))
removed = 0
for t in list(b.Tracks()):
    if t.GetClass() != 'PCB_VIA': continue
    p = t.GetPosition()
    for x, y in bad:
        if abs(p.x - mm(x)) < mm(0.05) and abs(p.y - mm(y)) < mm(0.05):
            b.Remove(t); removed += 1; break
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb', b)
print("RESULT removed", removed)
