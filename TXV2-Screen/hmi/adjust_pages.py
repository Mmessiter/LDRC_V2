#!/usr/bin/env python3
"""The In-flight adjustments pages of the transmitter (screen 1.11.36, B75; 1.11.38, B83: a switch is ONE Rotorflight line, its
ends dragged and its zones Rotorflight's even divisions; a bank switch is matched to the transmitter's own banks): sd/hmi/pages/67.json (AdjustView) and
68.json (AdjPickView). Malcolm, 8 Oct, on the first try: the arrows must move between the adjustments defined, Add
makes a new one; the value boxes, the "Now" box and the Kind / In bank row were "mysterious": so the page is the BAR
(the screen's 'rangebar': zones coloured and labelled with their values, TAP a zone to type its value, DRAG a blob to
move a divider, the channel's marker) under two lines worded as the phone page: "Changes [Pitch P gain] [in bank 1]"
and "Control [Switch, 3 positions] on [Channel 7: AUX2]" - each box tapped to change (the setting opens the picker
page, a wheel of every setting). The arrows beside the title move between the adjustments. The value boxes the keypad
edits are kept, one pixel wide, out of sight. Re-run after a change here: python3 hmi/adjust_pages.py (then
hmi/rfmenu_pages.py for the menu's button)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp   # (importing it re-makes the rescue pages: harmless)
comp, PALE = rp.comp, rp.PALE
# codes (the main board's NumberedFunctions1): 116 open, 117 OK, 118 save, 119 a value typed, 120 the setting (opens the picker),
# 122 the channel (next), 124 the kind (next), 125 the bank (next), 126 previous adjustment, 127 next, 128 add, 129 remove,
# 130 the bar touched (a tap or a drag), 131 picker OK, 132 picker cancel
NAMES = ["(nothing)", "Rates bank switch (1 to 6)", "PID bank switch (1 to 6)", "Led profile", "Battery profile", "Pitch rate curve shape (Shape)", "Roll rate curve shape (Shape)", "Yaw rate curve shape (Shape)", "Pitch top rotation speed (Rate)", "Roll top rotation speed (Rate)", "Yaw top rotation speed (Rate)", "Pitch expo", "Roll expo", "Yaw expo", "Pitch P gain", "Pitch I gain", "Pitch D gain", "Pitch F gain", "Roll P gain", "Roll I gain", "Roll D gain", "Roll F gain", "Yaw P gain", "Yaw I gain", "Yaw D gain", "Yaw F gain", "Yaw clockwise gain", "Yaw anticlockwise gain", "Yaw cyclic feedforward", "Yaw collective feedforward", "Yaw collective dynamic", "Yaw collective decay", "Pitch collective feedforward", "Pitch gyro cutoff", "Roll gyro cutoff", "Yaw gyro cutoff", "Pitch d-term cutoff", "Roll d-term cutoff", "Yaw d-term cutoff", "Rescue climb collective", "Rescue hover collective", "Rescue hover altitude", "Rescue altitude P gain", "Rescue altitude I gain", "Rescue altitude D gain", "Angle level gain", "Horizon level gain", "Acro trainer gain", "Governor gain", "Governor P gain", "Governor I gain", "Governor D gain", "Governor F gain", "Governor tail torque assist gain", "Governor cyclic feedforward", "Governor collective feedforward", "Pitch B gain", "Roll B gain", "Yaw B gain", "Pitch O gain", "Roll O gain", "Cross coupling gain", "Cross coupling ratio", "Cross coupling cutoff", "Level trim pitch", "Level trim roll", "Inertia precomp gain", "Inertia precomp cutoff", "Pitch setpoint boost gain", "Roll setpoint boost gain", "Yaw setpoint boost gain", "Collective setpoint boost gain", "Yaw dynamic ceiling gain", "Yaw dynamic deadband gain", "Yaw dynamic deadband filter", "Yaw precomp cutoff", "Governor idle throttle", "Governor auto throttle", "Governor max throttle", "Governor min throttle", "Governor headspeed", "Governor yaw feedforward"]
ORDER = list(range(5, 26)) + [3, 4] + list(range(26, 82))   # the main board's AdjNextFn order: rates and PIDs first (RF_Adjust.h must agree)

def header(name, title, help_file, comps, i):
    def add(c): c['i'] = i[0]; i[0] += 1; comps.append(c); return c
    add(comp(rp.TITLE, n='t0', txt=title)); add(comp(rp.CARD, n='card')); add(comp(rp.BANK, n='t9', txt='USB cable')); add(comp(rp.MODEL, n='t11', txt='Model name')); add(comp(rp.VA0, n='va0'))
    hb = comp(rp.by['b0'], n='b0'); hb['ev'] = {'r': 'print "HelpView:%s"\nLogView.t0.txt="%s"\nLogView.return.txt="%s"' % (help_file, title + ' help', name)}; add(hb)
    return add
def ev(code): return {'r': 'va0.val=%d<<8\nprint va0.val' % code}
def finish(pid, name, comps, extra_pre=''):
    out = {'name': name, 'id': pid, 'w': 800, 'h': 480, 'bg': rp.rates['bg'], 'nav': rp.rates['nav'], 'ev': {'preinitialize': 'vis busy,0\n%s.pic=Screen_Background%s' % (name, extra_pre)}, 'comps': comps}
    if pid == 67: out['ev']['postinitialize'] = 'print "ldrcadj"'   # (the page is back from the keypad, a question, or just opened: the main board draws the bar again)
    json.dump(out, open(os.path.join(rp.PAGES, '%d.json' % pid), 'w'), indent=1)
    print(pid, name, len(comps), 'components')
    idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
    if pid not in {x['id'] for x in idx['pages']}: idx['pages'].append({'id': pid, 'name': name, 'n': len(comps)}); idx['pages'].sort(key=lambda x: x['id'])
    for x in idx['pages']:
        if x['id'] == pid: x['n'] = len(comps)
    json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)

# ---- page 67: the adjustment
comps = []; i = [1]; add = header('AdjustView', 'Adjustment 1 of 1', 'ADJUST.TXT', comps, i)
shade = PALE[0]
def label(nm, x, y, w, txt, h=36, pale=True):
    l = comp(rp.LABEL_L, n=nm, x=x, y=y, w=w, h=h, txt=txt, g='g')
    if pale: l['c'] = dict(l['c'], pco=0, bco=shade)
    else: l['c'] = {'pco': 65535, 'borderc': rp.CARD['c']['bco'], 'bco': rp.CARD['c']['bco']}; l['a'] = dict(l['a'], borderw=0)
    return add(l)
def tapbox(nm, x, y, w, code, h=36, maxl=40):
    f = comp(rp.FIELD, n=nm, x=x, y=y, w=w, h=h, txt='', g='g'); f['a'] = dict(f['a'], key=255, txt_maxl=maxl); f['ev'] = ev(code); return add(f)
def hidden(nm, klabel, code=119):   # a box the keypad edits, out of sight (one pixel in the header's corner); opened by the main board's click
    f = comp(rp.FIELD, n=nm, x=1, y=1, w=1, h=1, txt='0', g='g'); f['a'] = dict(f['a'], borderw=0); f['c'] = dict(f['c'], bco=0, pco=0, borderc=0)
    f['ev'] = {'r': 'keybdB.t1.txt="%s"\nva0.val=%d<<8\nprint va0.val' % (klabel, code)}; return add(f)
bp = comp(rp.BUTTON, n='bprev', x=215, y=7, w=56, h=44, txt='<'); bp['ev'] = ev(126); add(bp)
bn = comp(rp.BUTTON, n='bnext', x=540, y=7, w=56, h=44, txt='>'); bn['ev'] = ev(127); add(bn)
label('ltn0', 34, 94, 150, 'Changes'); tapbox('tn0', 190, 94, 420, 120); tapbox('tn3', 616, 94, 150, 125, maxl=16)
tapbox('tn2', 34, 140, 396, 124, maxl=24); label('lon', 436, 140, 50, 'on', pale=False); tapbox('tn1', 492, 140, 274, 122, maxl=24)   # (B76: no 'Control' label - the line reads as a sentence)
bar = {'n': 'bar', 't': 'rangebar', 'g': 'g', 'x': 34, 'y': 194, 'w': 732, 'h': 60, 'font': 2, 'txt': '', 'val': 0,
       'c': {'pco': 65535, 'bco': rp.CARD['c']['bco'], 'borderc': 0, 'pco2': 65535, 'bco2': 0},
       'a': {'lo': 875, 'hi': 2125, 'n': 2, 'kind': 0, 'mk': -1, 'd0': 1500, 'd1': 1700, 'd2': 1900, 'd3': 2000, 'd4': 2100, 'txt_maxl': 160}, 'ev': ev(130)}
add(bar)
live = label('tn8', 34, 262, 732, '', 30); live['a'] = dict(live['a'], txt_maxl=60)
hint = label('hint', 34, 350, 732, 'Tap a zone to type its value. Drag the round ends.', 30, pale=False); hint['font'] = 2; hint['c']['pco'] = 50712   # (worded per kind by the main board)
for k in range(6): hidden('tp%d' % k, 'Position %d' % (k + 1))
hidden('tk0', 'Low end value'); hidden('tk1', 'High end value'); hidden('ts0', 'Step size'); hidden('ts1', 'Lowest value'); hidden('ts2', 'Highest value')
for (nm, txt, x, w, code) in rp.bottom_row([('b5', 'Add', 128), ('b6', 'Remove', 129), ('b3', 'Save', 118), ('b1', 'OK', 117)]):
    b = comp(rp.BUTTON, n=nm, x=x, y=414, w=w, h=56, txt=txt); b['ev'] = ev(code); add(b)
add(rp.message_box(rect=(110, 300, 580, 104)))   # (1.11.40: a message box, under the bar so the bar stays in sight)
finish(67, 'AdjustView', comps)

# ---- page 68: the picker
comps = []; i = [1]; add = header('AdjPickView', 'What it changes', 'ADJUST.TXT', comps, i)
proto = None
for pg in (46,):
    for c in json.load(open(os.path.join(rp.PAGES, '%d.json' % pg)))['comps']:
        if c['t'] == 'textselect': proto = c
wheel = comp(proto, n='list', x=14, y=66, w=772, h=333, txt='', val=0, opt=[NAMES[f] for f in ORDER]); wheel['a'] = dict(wheel['a'], hig=37); wheel['ev'] = {}
add(wheel)
for (nm, txt, x, w, code) in rp.bottom_row([('b1', 'Cancel', 132), ('b3', 'OK', 131)]):
    b = comp(rp.BUTTON, n=nm, x=x, y=414, w=w, h=56, txt=txt); b['ev'] = ev(code); add(b)
add(rp.message_box())
finish(68, 'AdjPickView', comps)
