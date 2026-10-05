# Rev-B: widen the power tracks (0.2 -> 0.4 mm) where the board allows.
# Usage: <kicad python> widen.py <pcb> <drc-json-from-last-pass>   (loop this with kicad-cli drc between passes)
# First pass (no json): set every segment of the power nets to 0.4 mm.
# Later passes: every segment named in a clearance/shorting/crossing violation
# goes back to 0.2 mm; repeat until DRC is clean.
import sys, json, pcbnew
from pcbnew import FromMM as MM
NETS = {'VBAT_RAW', 'VBAT_SW', '+5V', '+5V_NEXT', '+3V3_RF'}
BAD = {'clearance', 'shorting_items', 'tracks_crossing', 'hole_clearance', 'copper_edge_clearance', 'solder_mask_bridge'}
pcb = sys.argv[1]; b = pcbnew.LoadBoard(pcb)
changed = 0
if len(sys.argv) < 3:
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_TRACK' and t.GetNetname() in NETS and t.GetWidth() < MM(0.4):
            t.SetWidth(MM(0.4)); changed += 1
    print('widened', changed)
else:
    d = json.load(open(sys.argv[2]))
    hits = set()
    for v in d.get('violations', []):
        if v.get('type') not in BAD: continue
        for it in v.get('items', []):
            desc = it.get('description', ''); pos = it.get('pos', {})
            if desc.startswith('Track [') and 'pos' in it:
                hits.add((round(pos['x'], 3), round(pos['y'], 3)))
    for t in b.GetTracks():
        if t.GetClass() != 'PCB_TRACK' or t.GetNetname() not in NETS or t.GetWidth() != MM(0.4): continue
        s, e = t.GetStart(), t.GetEnd()
        ps = (round(s.x/1e6, 3), round(s.y/1e6, 3)); pe = (round(e.x/1e6, 3), round(e.y/1e6, 3))
        if any(abs(h[0]-q[0]) < 0.01 and abs(h[1]-q[1]) < 0.01 for h in hits for q in (ps, pe)):
            t.SetWidth(MM(0.2)); changed += 1
    print('reverted', changed, 'of', len(hits), 'flagged positions')
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(pcb, b)
