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
NAMES[1], NAMES[2] = 'Rates selector', 'Bank (Profile) selector'   # the phone app's Switches page words, as the main board names them (15 Oct)
ORDER = [2, 1] + list(range(5, 26)) + [3, 4] + list(range(26, 82))   # the main board's AdjOrder: the two selectors first (B136, 20 Oct), then rates and PIDs (RF_Adjust.h must agree)

# Polish (10 Oct, Malcolm: "make the screens look more beautiful, well designed and easy to use ... Don't change the logic"):
# link = the header's word for how the page reaches the model, as the main board writes it there (the switches' pages
# go by Bluetooth: their picker's main board never writes t9, so the page's own word is what shows); help_title = the
# help viewer's title when the page's own title changes as it is used ("Adjustment 3 of 10": its help is "Adjustments
# help"); name_w = the model name's box, stopped 20 px short of the title's arrows.
def header(name, title, help_file, comps, i, link='USB cable', help_title=None, name_w=None):
    def add(c): c['i'] = i[0]; i[0] += 1; comps.append(c); return c
    add(comp(rp.TITLE, n='t0', txt=title)); add(comp(rp.CARD, n='card')); add(comp(rp.BANK, n='t9', txt=link)); m = add(comp(rp.MODEL, n='t11', txt='Model name')); add(comp(rp.VA0, n='va0'))
    if name_w: m['w'] = name_w
    hb = comp(rp.by['b0'], n='b0'); hb['ev'] = {'r': 'print "HelpView:%s"\nLogView.t0.txt="%s"\nLogView.return.txt="%s"' % (help_file, (help_title or title) + ' help', name)}; add(hb)
    return add
# The arrows beside a title that counts ("< Adjustment 3 of 10 >"): symmetric about the middle of the screen, 288 px of
# title between them - the widest titles the main board writes there ("Adjustment 12 of 42", "No adjustments yet",
# "Adjustments: none yet" is the one that cannot fit: reworded on the main board) clear them; 44 x 44 is still a whole
# thumb. The model name's box stops 20 px short of the left one.
ARROW_W, TITLE_ROOM = 44, 288
ARROW_PREV_X, ARROW_NEXT_X = 400 - TITLE_ROOM // 2 - ARROW_W, 400 + TITLE_ROOM // 2
NAME_W = ARROW_PREV_X - 20 - rp.MODEL['x']
def arrows(add, prev_code, next_code):
    bp = comp(rp.BUTTON, n='bprev', x=ARROW_PREV_X, y=7, w=ARROW_W, h=44, txt='<'); bp['ev'] = ev(prev_code); add(bp)
    bn = comp(rp.BUTTON, n='bnext', x=ARROW_NEXT_X, y=7, w=ARROW_W, h=44, txt='>'); bn['ev'] = ev(next_code); add(bn)
# The page's notes and progress (the main board's "busy", shown 3-8 s while the page is in use: "Press Save: ...",
# "Type the first and last positions ...", "Saved ...") as wide as the bar, BETWEEN the bar and the buttons: over the live
# line and the hint, which are words only. Fix (11 Oct, touch audit): over the two lines above the bar it took the taps
# of the setting, kind, bank and channel boxes while it showed (the screen's hit(): the topmost visible part wins);
# here the boxes, the bar and the four buttons all stay live (a note that says "press Save" never covers Save).
# 4 px clear of the bar (Y + 160) and of the buttons (the island's foot, Y + 236 + C_BTN_ABOVE): 82 px, two lines of
# font 2 in the message box's padding - the longest note, AdjBankWhy's "Banks 1 to 6; bank 7 has no value of its own on
# channel 16 (2012 us).", is 672 px: two lines in the 648 px the box leaves for words
def note_box(X, Y, W):
    top, foot = Y + 164, Y + 236 + rp.C_BTN_ABOVE
    return rp.message_box(rect=(X, top, W, foot - 4 - top))
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
comps = []; i = [1]; add = header('AdjustView', 'Adjustment 1 of 1', 'ADJUST.TXT', comps, i, help_title='Adjustments', name_w=NAME_W)
shade = PALE[0]
def label(nm, x, y, w, txt, h=36, pale=True):
    l = comp(rp.LABEL_L, n=nm, x=x, y=y, w=w, h=h, txt=txt, g='g')
    if pale: l['c'] = dict(l['c'], pco=0, bco=shade)
    else: l['c'] = {'pco': 65535, 'borderc': rp.CARD['c']['bco'], 'bco': rp.CARD['c']['bco']}; l['a'] = dict(l['a'], borderw=0)
    return add(l)
def tapbox(nm, x, y, w, code, h=36, maxl=40):
    f = comp(rp.FIELD, n=nm, x=x, y=y, w=w, h=h, txt='', g='g'); f['a'] = dict(f['a'], key=255, txt_maxl=maxl); f['ev'] = ev(code); return add(f)
def hidden(nm, klabel, code=119):   # a box the keypad edits, out of sight (one pixel in the header's corner); opened by the main board's click
    # Fix (11 Oct): flat (style 0) and in the strip's own colour (0x08A6, which every theme recolours as the strip), so the
    # pixel is invisible - its sunken frame (style 2) drew a grey speck in the strip's corner. It keeps its place: the
    # pixel it wins stays its own (not parked), so nothing a touch reaches changes.
    f = comp(rp.FIELD, n=nm, x=1, y=1, w=1, h=1, txt='0', g='g'); f['a'] = dict(f['a'], borderw=0, style=0); f['c'] = dict(f['c'], bco=rp.TITLE['c']['bco'], pco=rp.TITLE['c']['bco'], borderc=rp.TITLE['c']['bco'])
    f['ev'] = {'r': 'keybdB.t1.txt="%s"\nva0.val=%d<<8\nprint va0.val' % (klabel, code)}; return add(f)
arrows(add, 126, 127)
# B91: an island (rescue_pages.island) - the two lines, the bar, the live line and the hint 680 wide, the buttons at its foot
W = 680; isl = rp.island(W, 236, [('b5', 'Add', 128), ('b6', 'Remove', 129), ('b3', 'Save', 118), ('b1', 'OK', 117)])
comps[1].update(x=isl['card'][0], y=isl['card'][1], w=isl['card'][2], h=isl['card'][3])
X, Y = isl['x0'], isl['y0']
label('ltn0', X, Y, 140, 'Changes'); tapbox('tn0', X + 146, Y, 380, 120); tapbox('tn3', X + 532, Y, 148, 125, maxl=16)
tapbox('tn2', X, Y + 46, 360, 124, maxl=24); label('lon', X + 366, Y + 46, 44, 'on', pale=False); tapbox('tn1', X + 416, Y + 46, 264, 122, maxl=24)   # (B76: no 'Control' label - the line reads as a sentence)
bar = {'n': 'bar', 't': 'rangebar', 'g': 'g', 'x': X, 'y': Y + 100, 'w': W, 'h': 60, 'font': 2, 'txt': '', 'val': 0,
       'c': {'pco': 65535, 'bco': rp.CARD['c']['bco'], 'borderc': 0, 'pco2': 65535, 'bco2': 0},
       'a': {'lo': 875, 'hi': 2125, 'n': 2, 'kind': 0, 'mk': -1, 'd0': 1500, 'd1': 1700, 'd2': 1900, 'd3': 2000, 'd4': 2100, 'txt_maxl': 160}, 'ev': ev(130)}
add(bar)
live = label('tn8', X, Y + 168, W, '', 30, pale=False); live['a'] = dict(live['a'], txt_maxl=60)   # (polish: the live line white on the card - live data, not a label; no empty box with no adjustment)
hint = label('hint', X, Y + 206, W, '', 30, pale=False); hint['font'] = 2; hint['c']['pco'] = 50712   # (worded per kind by the main board; polish: empty until it does - the page's default is no hint, as with no adjustment)
for k in range(6): hidden('tp%d' % k, 'Position %d' % (k + 1))
hidden('tk0', 'Low end value'); hidden('tk1', 'High end value'); hidden('ts0', 'Step size'); hidden('ts1', 'Lowest value'); hidden('ts2', 'Highest value')
for (nm, txt, x, y, w, code) in isl['btn']:
    b = comp(rp.BUTTON, n=nm, x=x, y=y, w=w, h=rp.C_BTN_H, txt=txt); b['ev'] = ev(code); add(b)
add(note_box(X, Y, W))
finish(67, 'AdjustView', comps)

# ---- page 68: the picker
comps = []; i = [1]; add = header('AdjPickView', 'What it changes', 'ADJUST.TXT', comps, i)
proto = None
for pg in (46,):
    for c in json.load(open(os.path.join(rp.PAGES, '%d.json' % pg)))['comps']:
        if c['t'] == 'textselect': proto = c
LW, LH = 460, 7 * 37 + 6   # (B91: the wheel on an island: as wide as the longest setting needs, seven whole rows)
isl = rp.island(LW, LH, [('b1', 'Cancel', 132), ('b3', 'OK', 131)])
comps[1].update(x=isl['card'][0], y=isl['card'][1], w=isl['card'][2], h=isl['card'][3])
wheel = comp(proto, n='list', x=isl['x0'], y=isl['y0'], w=LW, h=LH, txt='', val=0, opt=[NAMES[f] for f in ORDER]); wheel['a'] = dict(wheel['a'], hig=37); wheel['ev'] = {}
add(wheel)
for (nm, txt, x, y, w, code) in isl['btn']:
    b = comp(rp.BUTTON, n=nm, x=x, y=y, w=w, h=rp.C_BTN_H, txt=txt); b['ev'] = ev(code); add(b)
add(rp.message_box(rect=isl['box']))
finish(68, 'AdjPickView', comps)
