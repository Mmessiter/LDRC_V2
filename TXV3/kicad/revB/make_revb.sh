#!/bin/zsh
# Rebuild TXV2 Rev-B from the fabbed Rev-A board file, verify, export.
#   zsh make_revb.sh
# Needs KiCad 10 (kicad-cli + its python). Output: ~/Documents/KiCad/TXV2_MAIN_revB/
set -e
SRC=~/Documents/KiCad/TXV2_MAIN/TXV2_MAIN.kicad_pcb
RB=~/Documents/KiCad/TXV2_MAIN_revB
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p $RB && cp $SRC $RB/TXV2_MAIN.kicad_pcb && cp ~/Documents/KiCad/TXV2_MAIN/TXV2_MAIN.kicad_pro $RB/ 2>/dev/null || true
$PY $HERE/revb_edit.py $RB/TXV2_MAIN.kicad_pcb $RB/TXV2_MAIN.kicad_pcb 2>&1 | grep -v "wxApp\|stdpbase"
drc() { $K pcb drc --output $RB/drc.json --format json --severity-all --schematic-parity $RB/TXV2_MAIN.kicad_pcb > /dev/null 2>&1 || true
  python3 - $RB/drc.json <<'PY'
import json,sys,collections
d=json.load(open(sys.argv[1]))
c=collections.Counter((i.get('severity'),i.get('type')) for i in d.get('violations',[]))
err={t:n for (s,t),n in c.items() if s=='error'}
real=[1 for i in d.get('unconnected_items',[]) if not all('Zone' in it.get('description','') for it in i.get('items',[]))]
print('DRC errors:', err, '| real unconnected:', len(real))
bad=[t for t in err if t!='starved_thermal']
if bad or real: sys.exit('DRC NOT CLEAN: '+str(bad)+' unconnected '+str(len(real)))
PY
}
$PY $HERE/widen.py $RB/TXV2_MAIN.kicad_pcb 2>&1 | grep -v "wxApp\|stdpbase"
for i in 1 2 3 4; do
  $K pcb drc --output $RB/drc.json --format json --severity-all --schematic-parity $RB/TXV2_MAIN.kicad_pcb > /dev/null 2>&1 || true
  $PY $HERE/widen.py $RB/TXV2_MAIN.kicad_pcb $RB/drc.json 2>&1 | grep -v "wxApp\|stdpbase"
done
drc
rm -rf $RB/gerbers && mkdir -p $RB/gerbers
$K pcb export gerbers --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts --output $RB/gerbers/ $RB/TXV2_MAIN.kicad_pcb > /dev/null
$K pcb export drill --format excellon --drill-origin absolute --excellon-units mm --excellon-zeros-format decimal --output $RB/gerbers/ $RB/TXV2_MAIN.kicad_pcb > /dev/null
(cd $RB/gerbers && rm -f ../TXV2_MAIN_revB_gerbers.zip && zip -q ../TXV2_MAIN_revB_gerbers.zip *)
$K pcb render --side top --output $RB/revB_top.png --width 1600 --height 1200 --quality basic $RB/TXV2_MAIN.kicad_pcb > /dev/null 2>&1
$K pcb render --side bottom --output $RB/revB_bottom.png --width 1600 --height 1200 --quality basic $RB/TXV2_MAIN.kicad_pcb > /dev/null 2>&1
echo "Rev-B built: $RB/TXV2_MAIN_revB_gerbers.zip"
