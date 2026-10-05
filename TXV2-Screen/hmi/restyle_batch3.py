#!/usr/bin/env python3
"""The remaining pages in the System pages' style, batch 3: the Rotorflight pages, telemetry, GPS, the bank copy
pages, bank names, log files and the yes/no popup (Malcolm, 2026-10-03). Same rules and checks as batches 1 and 2.
The Rotorflight tables were already neatly aligned: they keep their cells, their coloured headers and axes (Roll red,
Pitch green, Yaw purple, Collective yellow, as in the Rotorflight configurator) and their white value boxes (the
Teensy hides values while it reads them by turning their figures white: RF_PIDs.h, RF_Rates*.h, RF_Governor*.h).
Run: python3 hmi/restyle_batch3.py [page ids...]"""
import sys
from pagestyle import *
from restyle_batch2 import strip_left, thin_progress

def navy_labels(pg, names, xcen=0):
    for nm in names:
        c = comp(pg, nm); c['sta'] = 1
        c['c'].update({'bco': NAVY, 'pco': WHITE, 'borderc': 0}); c['a'].update({'xcen': xcen, 'ycen': 1, 'style': 0, 'borderw': 0})

def white_values(pg, names):
    for nm in names:
        c = comp(pg, nm); c['sta'] = 1
        c['c'].update({'bco': WHITE, 'pco': BLACK}); c['a'].update({'style': 2, 'borderw': 2})

def bottom_middle(pg, name, font=6, colour=WHITE, x0=SLOTS[1][0], x1=SLOTS[2][0] + SLOTS[2][2], y=SLOTS[1][1], h=SLOTS[1][3]):
    """Between Save and OK: 'Reading values ...' while the Teensy reads (its longest messages were measured in the
    screen's own fonts: 'Loading governor values ...' is 378 px in font 0, too wide for this 377 px gap)."""
    c = comp(pg, name); place(c, x0, y, x1 - x0, h)
    c['sta'] = 1; c['font'] = font; c['c'].update({'bco': NAVY, 'pco': colour}); c['a'].update({'xcen': 1, 'ycen': 1, 'style': 0, 'borderw': 0})

def rf_rates():                                             # 1 RatesView
    pg = load_original(1)
    title(pg, 't0', 'Rates (Rotorflight)'); card(pg, 't0'); help_button(comp(pg, 'b0'))
    strip_left(pg, [('t9', WHITE), ('t11', YELLOW)])
    white_values(pg, ['tn%d' % i for i in range(12)])
    c = comp(pg, 'busy'); place(c, 40, 340, 720, 44); c['sta'] = 1; c['c'].update({'bco': NAVY, 'pco': WHITE}); c['a'].update({'xcen': 1})
    slot(comp(pg, 'b3'), 0, 'Save'); slot(comp(pg, 'b2'), 2, 'Advanced ...'); slot(comp(pg, 'b1'), 3, 'OK')
    return 1, pg

def rf_rates_plus():                                        # 42 Rates_A_View
    pg = load_original(42)
    title(pg, 't0', 'Rates + (Rotorflight)'); card(pg, 't0'); help_button(comp(pg, 'b0'))
    strip_left(pg, [('t9', WHITE), ('t11', YELLOW)])
    navy_labels(pg, ['t1', 't2', 't3', 't10', 't12', 't13'])
    white_values(pg, ['n%d' % i for i in range(14)] + ['t14'])
    c = comp(pg, 'busy'); place(c, 40, 354, 720, 44); c['sta'] = 1; c['c'].update({'bco': NAVY, 'pco': WHITE}); c['a'].update({'xcen': 1})
    slot(comp(pg, 'b3'), 0, 'Save'); slot(comp(pg, 'b1'), 3, 'OK')
    return 42, pg

def rf_pid():                                               # 40 PIDView
    pg = load_original(40)
    title(pg, 't0', 'PID (Rotorflight)'); card(pg, 't0'); help_button(comp(pg, 'b0')); comp(pg, 'b0')['font'] = 6
    strip_left(pg, [('t9', WHITE), ('t11', YELLOW)])
    white_values(pg, ['n%d' % i for i in range(17)])
    c = comp(pg, 'busy'); place(c, 40, 330, 720, 44); c['sta'] = 1; c['c'].update({'bco': NAVY, 'pco': WHITE}); c['a'].update({'xcen': 1})
    slot(comp(pg, 'b3'), 0, 'Save'); slot(comp(pg, 'b2'), 2, 'Advanced ...'); slot(comp(pg, 'b1'), 3, 'OK')
    for nm in ('b3', 'b2', 'b1'): comp(pg, nm)['font'] = 6
    return 40, pg

def rf_pid_plus():                                          # 7 PID_A_View: 14 rows a side, so a slimmer strip and lower buttons
    pg = load_original(7)
    title(pg, 't0', 'PID + (Rotorflight)'); place(comp(pg, 't0'), 0, 0, 800, 42)
    card(pg, 't0', rect=(14, 43, 772, 384))
    b = comp(pg, 'b0'); button(b, 630, 2, 160, 38, font=6)
    c = comp(pg, 't26'); place(c, 10, 8, 200, 26); c['sta'] = 1; c['font'] = 2; c['c'].update({'bco': STRIP, 'pco': WHITE}); c['a'].update({'xcen': 0, 'ycen': 1})
    navy_labels(pg, ['t28', 't29', 't30', 't31', 't32', 't33', 't34', 't35', 't36', 't37', 't38', 't39', 't40'] + ['t%d' % i for i in range(41, 54)])
    white_values(pg, ['t%d' % i for i in range(1, 26)])
    orig = load_original(7)                                 # the rows in their original order, top to bottom, column by column
    cellnames = ['t%d' % i for i in range(1, 26)] + ['t%d' % i for i in range(28, 54)] + ['sw0']
    for left_side in (True, False):
        cells = sorted((c for c in orig['comps'] if c['n'] in cellnames and (c['x'] < 400) == left_side), key=lambda c: c['y'])
        bands = []                                          # rows: y within 4 px of the row's first cell
        for c in cells:
            if not bands or c['y'] - bands[-1][0] > 4: bands.append([c['y'], []])
            bands[-1][1].append(c['n'])
        assert len(bands) == 13, (left_side, len(bands))
        for r, (_, names) in enumerate(bands):
            for nm in names:
                n = comp(pg, nm); n['y'] = 54 + r * 28 + (1 if nm == 'sw0' else 0); n['h'] = 23 if nm == 'sw0' else 25
                if not left_side: n['x'] = next(c['x'] for c in cells if c['n'] == nm) + 16
                elif nm.startswith('t') and int(nm[1:]) >= 28: n['x'] = 36   # (two of them were a pixel out)
    button(comp(pg, 'b3'), 14, 430, 150, 44, 'Save'); button(comp(pg, 'b1'), 636, 430, 150, 44, 'OK')
    bottom_middle(pg, 't27', font=0, colour=YELLOW, x0=174, x1=626, y=430, h=44)  # the model's name, under the message
    bottom_middle(pg, 'busy', font=2, x0=174, x1=626, y=430, h=44)  # 'Sending edited PID Advanced values ...' is 384 px in font 2
    return 7, pg

def rf_governor():                                          # 6 RFGovView (profile)
    pg = load_original(6)
    title(pg, 't0', 'Governor (profile)'); card(pg, 't0'); help_button(comp(pg, 'b0')); comp(pg, 'b0')['font'] = 6
    strip_left(pg, [('t26', WHITE), ('t27', YELLOW)])
    left = [('t34', 'n0'), ('t29', 'n1'), ('t30', 'n2'), ('t31', 'n3'), ('t28', 'n4'), ('t35', 'n5'), ('t36', 'n6')]
    right = [('t37', 'n7'), ('t32', 'n8'), ('t33', 'n9'), ('t38', 'n10'), ('t39', 'n11'), ('t40', 'n12'), ('t41', 'n13')]
    navy_labels(pg, [a for a, _ in left + right]); white_values(pg, [b for _, b in left + right])
    for i in range(7):                                      # (labels from the card's margin, as on the System pages: they used to end 10 px before their boxes)
        y = 80 + i * 38
        for (lab, val), lx, lw, vx in ((left[i], 30, 280, 318), (right[i], 424, 264, 696)):
            place(comp(pg, lab), lx, y, lw, 32); place(comp(pg, val), vx, y, 76, 32)
    button(comp(pg, 'b2'), 200, 352, 400, 42, 'Global governor parameters ...')
    slot(comp(pg, 'b3'), 0, 'Save'); slot(comp(pg, 'b1'), 3, 'OK')
    bottom_middle(pg, 'busy')
    return 6, pg

def rf_governor_global():                                   # 5 RFGovViewGlbl (its filter fields beyond the right edge stay there)
    pg = load_original(5)
    title(pg, 't0', 'Governor (global)'); card(pg, 't0'); help_button(comp(pg, 'b0')); comp(pg, 'b0')['font'] = 6
    navy_labels(pg, ['t42', 't43', 't45', 't46', 't47', 't48', 't49', 't50', 't69', 't70', 't71'])
    white_values(pg, ['n14', 'n15', 'n17', 'n18', 'n19', 'n20', 'n21', 'n22', 'n28', 'n29', 'n30'])
    for nm in ('n14', 'n21', 'n22'): c = comp(pg, nm); c['x'] = 211; c['w'] = 58   # ('Hold timeout x10' is 163 px: 10 px clear of its box)
    for nm in ('n15', 'n28', 'n29', 'n30'): c = comp(pg, nm); c['x'] = 462; c['w'] = 56   # ('Handover throttle' is 168 px)
    slot(comp(pg, 'b3'), 0, 'Save'); slot(comp(pg, 'b1'), 3, 'OK')
    for nm in ('b3', 'b1'): comp(pg, nm)['font'] = 6
    strip_left(pg, [('t27', YELLOW)])
    bottom_middle(pg, 't4')  # the Teensy's messages on this page go to t4
    park(comp(pg, 'busy'))  # a 2-pixel strip the Teensy never uses on this page
    for nm, text in (('b4', 'Restore SD to FC'), ('b2', 'Save FC to SD')): comp(pg, nm)['txt'] = text   # (they had two spaces before the last word)
    for nm in ('t44', 't45', 't46', 't47', 't48', 't53', 't70', 't71'):  # '\u00d7' (Latin-1 D7) was lost turning the HMI into pages: plain x, as 'Hold timeout x10'
        c = comp(pg, nm); c['txt'] = c['txt'].replace('\ufffd', 'x')
    return 5, pg

def rows(pairs, x_label, w_label, x_value, w_value, y0, pitch, h, font=2, value_font=None):
    """Label + value rows on the card: the label in white on navy, the value in a white box the Teensy fills."""
    for i, (lab, val) in enumerate(pairs):
        y = y0 + i * pitch
        if lab: text_on_card(lab, x_label, y, w_label, h, font=font)
        if val: entry(val, x_value, y, w_value, h, font=value_font if value_font is not None else font)

def telemetry():                                            # 30 DataView
    pg = load_original(30)
    title(pg, 't0', 'Telemetry'); card(pg, 't0', ev=page_touch(pg)); help_button(comp(pg, 'b15'))
    left = [('t29', 'n0'), ('t2', 'pps'), ('t1', 'lps'), ('t10', 'Ls'), ('t15', 'Ag'), ('t14', 'rx'), ('t9', 'Sg'), ('t16', 'Gc'), ('t30', 'n1')]
    right = [('t11', 'Ts'), ('t21', 'Sbus'), ('t4', 'alt'), ('t13', 'MaxAlt'), ('t3', 'Temp'), ('t5', 't6'), ('t12', 't17'), ('t7', 'rxv'), ('t8', 'txv')]
    rows([(comp(pg, a), comp(pg, b)) for a, b in left], 26, 212, 242, 108, 80, 35, 31)  # ('Average comms gap' is 200 px in font 2)
    rows([(comp(pg, a), comp(pg, b)) for a, b in right], 370, 198, 572, 200, 80, 35, 31)  # 'TX firmware' is 177 px: 2.5.6B22 03/10/26
    slot(comp(pg, 'b0'), 0, 'Clear'); slot(comp(pg, 'b13'), 1, 'Gaps ...'); slot(comp(pg, 'b1'), 2, 'GPS ...'); slot(comp(pg, 'b10'), 3, 'OK')
    return 30, pg  # b2 'Zero alt' stays below the glass, where it always was

def gps():                                                  # 52 GPSView
    pg = load_original(52)
    title(pg, 't0', 'GPS'); card(pg, 't0'); help_button(comp(pg, 'b15'))
    left = [('t20', 'Fix'), ('t18', 'Sat'), ('t5', 'Lon'), ('t22', 'Lat'), ('t17', 'Bear'), ('t6', 'BTo')]
    right = [('t19', 'Mxd'), ('t27', 'Sped'), ('t12', 'MxS'), ('t23', 'ALT'), ('t24', 'MALT')]
    rows([(comp(pg, a), comp(pg, b)) for a, b in left], 26, 176, 206, 182, 93, 42, 34)   # (longitude and latitude are always 14 characters: up to 170 px)
    rows([(comp(pg, 't26'), comp(pg, 'Dist'))], 26, 176, 206, 182, 93 + 6 * 42, 42, 34, font=6)  # the distance to the mark stays larger, as it was
    rows([(comp(pg, a), comp(pg, b)) for a, b in right], 402, 210, 616, 156, 93, 42, 34)
    slot(comp(pg, 'b2'), 0, 'Zero alt'); slot(comp(pg, 'b1'), 1, 'Mark here'); slot(comp(pg, 'b0'), 2, 'Data ...'); slot(comp(pg, 'b10'), 3, 'OK')
    return 52, pg

DEEP_RED, DEEP_GREEN = 45056, 1024

def bank_copy(pid, head_text, head_bco, warning, first, second, start_text):
    """11 and 10: the Rotorflight bank copy dialogs. Their switches colour the labels black (on) or GRAY (off) by
    page script, so the body keeps its own light colour (red-pink: restore to the FC; green: backup to the card)."""
    pg = load_original(pid)
    d = comp(pg, 'Dialog'); body = d['c']['bco']; x, y, w, h = 110, 14, 580, 452
    place(d, x, y, w, h); d['c'].update({'borderc': WHITE}); d['a'].update({'style': 1, 'borderw': 2})
    hd = comp(pg, 't5'); place(hd, x + 2, y + 2, w - 4, 50); hd['sta'] = 1; hd['font'] = 0; hd['txt'] = head_text; hd['a']['txt_maxl'] = max(hd['a'].get('txt_maxl', 0), len(head_text) + 2)
    hd['c'].update({'bco': head_bco, 'pco': WHITE}); hd['a'].update({'xcen': 1, 'ycen': 1})
    t8 = comp(pg, 't8'); place(t8, x + 10, y + 60, w - 20, 30); t8['txt'] = warning; t8['a']['txt_maxl'] = max(t8['a'].get('txt_maxl', 0), len(warning) + 2); t8['a']['xcen'] = 1
    lx, lw, nx = x + 20, 250, x + 280                       # labels right-aligned up to 380, the values from 390
    for i, (label, text, num, extra) in enumerate((first, second)):
        ry = y + 104 + i * 48
        t = comp(pg, label); place(t, lx, ry + 3, lw, 30); t['txt'] = text; t['a']['txt_maxl'] = max(t['a'].get('txt_maxl', 0), len(text) + 2); t['a']['xcen'] = 2
        place(comp(pg, num), nx, ry, 64, 36)
        if extra == 'switch':
            h7 = comp(pg, 't7'); place(h7, nx + 74, ry + 3, 206, 30); h7['txt'] = 'Use the bank switch'; h7['a']['txt_maxl'] = max(h7['a'].get('txt_maxl', 0), 24); h7['a']['xcen'] = 0
        else:
            for b, bx, txt in (('b3', nx + 74, '-'), ('b2', nx + 154, '+')):
                c = comp(pg, b); place(c, bx, ry, 70, 36); c['c'].update({'bco': BTN, 'pco': BLACK}); c['a'].update({'style': 4, 'borderw': 2})
    for i, (label, text, sw) in enumerate((('t1', 'PIDs:', 'sw0'), ('t2', 'PIDs Advanced:', 'sw1'), ('t3', 'Rates:', 'sw2'), ('t4', 'Rates Advanced:', 'sw3'), ('t9', 'Governor (profile):', 'sw4'))):
        ry = y + 200 + i * 36  # the last row ends 12 px above the buttons
        t = comp(pg, label); place(t, lx, ry, lw, 32); t['txt'] = text; t['a']['xcen'] = 2
        switch(comp(pg, sw), nx, ry + 1, 100, 30)
    for b, bx, txt in (('b1', x + 14, 'Back'), ('b0', x + w - 14 - 190, start_text)):
        c = comp(pg, b); button(c, bx, y + h - 14 - 50, 190, 50, txt)
    return pid, pg

def bank_restore():                                         # 11 PickBankView1
    return bank_copy(11, 'Restore (SD card to FC)', DEEP_RED, 'This replaces the values in the flight controller!',
                     ('t0', 'From SD card bank', 'n0', 'stepper'), ('t6', 'To FC bank', 'n1', 'switch'), 'Start restore')

def bank_backup():                                          # 10 PickBankView2
    return bank_copy(10, 'Back up (FC to SD card)', DEEP_GREEN, 'This replaces the values saved on the SD card!',
                     ('t6', 'From FC bank', 'n1', 'switch'), ('t0', 'To SD card bank', 'n0', 'stepper'), 'Start backup')

def bank_names():                                           # 20 BankNameView
    pg = load_original(20)
    title(pg, 't0', 'Bank names'); card(pg, 't0'); help_button(comp(pg, 'b17'))
    strip_left(pg, [('ModelName', YELLOW)])
    for (lab, lst), (x, y) in zip((('t1', 'BK1'), ('t2', 'BK2'), ('t3', 'BK3'), ('t4', 'BK4')), ((34, 92), (34, 259), (426, 92), (426, 259))):
        text_on_card(comp(pg, lab), x, y + 44, 110, 32, font=6, xcen=2, text='Bank ' + lab[1])
        c = comp(pg, lst); c['x'], c['y'] = x + 120, y; sunken_list(c)  # the lists keep their size: 3 whole rows
    for i, b in enumerate(('b0', 'b1', 'b4', 'b2', 'b3', 'b10')):
        button(comp(pg, b), 14 + i * 130, 414, 122, 56)
    return 20, pg

def files():                                                # 19 LogFiles
    pg = load_original(19)
    title(pg, 't0', 'Files'); card(pg, 't0'); help_button(comp(pg, 'b15'))
    c = comp(pg, 'FilesBox'); place(c, 30, 76, 540, c['h']); sunken_list(c)  # 7 whole rows, as tidied
    button(comp(pg, 'b0'), 590, 90, 180, 60, 'View'); button(comp(pg, 'b1'), 590, 166, 180, 60, 'Delete')
    for i, (lab, val, text) in enumerate((('t3', 't4', 'Total:'), ('t1', 't5', 'Used:'), ('t2', 't6', 'Free:'))):
        x = 30 + i * 250
        text_on_card(comp(pg, lab), x, 364, 70, 32, font=2, colour=SOFT, text=text)
        text_on_card(comp(pg, val), x + 70, 364, 170, 32, font=2)
    slot(comp(pg, 'b10'), 3, 'OK')
    return 19, pg

def popup():                                                # 41 PopupView: the yes/no question asked from everywhere
    pg = load_original(41)
    d = comp(pg, 'Dialog'); place(d, 90, 70, 620, 300); d['sta'] = 1
    d['c'].update({'bco': NAVY, 'pco': WHITE, 'borderc': WHITE}); d['a'].update({'style': 1, 'borderw': 2, 'xcen': 1, 'ycen': 1, 'isbr': 1})   # ('Delete ID for <a 30-letter name>?' is 603 px: it wraps)
    ring(pg, 'Dialog')
    button(comp(pg, 'b1'), 106, 306, 180, 50); button(comp(pg, 'b0'), 514, 306, 180, 50)  # Cancel (hidden for a message), OK
    return 41, pg  # five lines of the longest message (Subtrims) end at y 290, above the buttons

def fix_gov_d_gain(pg):       # 6: editing D gain never told the Teensy (I gain and F gain do), so Save never came up for it
    comp(pg, 'n4')['ev']['r'] = 'keybdB.t1.txt="D gain"\nva0.val=53<<8\nprint va0.val'
def fix_rates_plus_n7(pg):    # 42: "30<<88" for 30<<8: the Teensy never heard that this value had been edited
    c = comp(pg, 'n7'); c['ev']['r'] = c['ev']['r'].replace('30<<88', '30<<8')
def fix_pid_plus_t17(pg):     # 7: its keyboard was titled "17"
    c = comp(pg, 't17'); c['ev']['r'] = c['ev']['r'].replace('keybdB.t1.txt="17"', 'keybdB.t1.txt="Pitch B-Term cutoff "')
def fix_bank_copy_sw4(pg):    # 11, 10: the governor switch ran a copy of the rates switch's script; now it greys its own label
    comp(pg, 'sw4')['ev']['r'] = 'if(sw4.val==1)\n{\n  t9.pco=0\n}else\n{\n  t9.pco=GRAY\n}'
def fix_bank_names_blank(pg): # 20: each list ended in two empty items; the page loader drops one, the other was a blank row above "Flight mode 1"
    for nm in ('BK1', 'BK2', 'BK3', 'BK4'):
        o = comp(pg, nm)['opt']
        while len(o) >= 2 and o[-1] == '' and o[-2] == '': o.pop()
FIXES = {6: fix_gov_d_gain, 42: fix_rates_plus_n7, 7: fix_pid_plus_t17, 11: fix_bank_copy_sw4, 10: fix_bank_copy_sw4, 20: fix_bank_names_blank}

GROUND = {1, 42, 40, 7, 6, 5, 30, 52, 20, 19}   # blue everywhere (11, 10 and 41 are dialogs over other pages)

PAGES = {1: rf_rates, 42: rf_rates_plus, 40: rf_pid, 7: rf_pid_plus, 6: rf_governor, 5: rf_governor_global,
         30: telemetry, 52: gps, 11: bank_restore, 10: bank_backup, 20: bank_names, 19: files, 41: popup}

if __name__ == '__main__':
    want = [int(a) for a in sys.argv[1:]] or list(PAGES)
    good = True
    for pid in want:
        p, pg = PAGES[pid]()
        if p in FIXES: FIXES[p](pg)
        if p in GROUND: ground(pg)
        if verify(p, pg, FIXES.get(p)): save(p, pg)
        else: good = False
    sys.exit(0 if good else 1)
