import pcbnew, sys
b = pcbnew.LoadBoard('TXV2_MAIN.kicad_pcb')
FCu, BCu = pcbnew.F_Cu, pcbnew.B_Cu
mm = pcbnew.FromMM; V = pcbnew.VECTOR2I
gnd = b.GetNetcodeFromNetname('GND')
def width_of(t):
    try: return t.GetWidth()
    except Exception:
        try: return t.GetWidth(FCu)
        except Exception: return mm(0.7)
# remove my thin GND helper tracks inside the charger box (they caused crossings)
removed = 0
for t in list(b.Tracks()):
    if t.GetClass() != 'PCB_TRACK' or t.GetNetCode() != gnd or t.GetLayer() != BCu: continue
    if width_of(t) not in (mm(0.2), mm(0.25), mm(0.3)): continue
    p = t.GetStart()
    if 124e6 < p.x < 146e6 and 116e6 < p.y < 164e6:
        b.Remove(t); removed += 1
# fine-pitch GND zone over the charger region, back layer, higher priority
z = pcbnew.ZONE(b)
z.SetLayer(BCu); z.SetNetCode(gnd); z.SetAssignedPriority(1)
z.SetLocalClearance(mm(0.25)); z.SetMinThickness(mm(0.15))
z.SetThermalReliefGap(mm(0.3)); z.SetThermalReliefSpokeWidth(mm(0.3))
pts = [(124.5,116),(146,116),(146,164),(124.5,164)]
ol = z.Outline(); ol.NewOutline()
for x, y in pts: ol.Append(int(mm(x)), int(mm(y)))
b.Add(z)
pcbnew.SaveBoard('TXV2_MAIN.kicad_pcb', b)
print("RESULT removed", removed, "zone added")
