#!/usr/bin/env python3
"""The remaining pages in the System pages' style, batch 1 (Malcolm, 2026-10-03: "please would you implement 'The
same clean style on the remaining pages'"): the menus and the small single-purpose pages. Each page is restyled from
its original (hmi/originals) and checked by pagestyle.verify(): names, ids, types, events, keyboards, rules and
starting values are untouched, so the Teensy sees no difference. Menus keep every button in its old row and column.
Run: python3 hmi/restyle_batch1.py [page ids...]"""
import sys
from pagestyle import *

def model_setup():                                          # 4 RXSetupView
    pg = load_original(4)
    title(pg, 't0', 'Model setup'); card(pg, 't0'); help_button(comp(pg, 'b17'))
    text_on_card(comp(pg, 'ModelName'), 34, 72, 732, 42, font=0, colour=YELLOW, xcen=1)
    g = grid(3, 6, 34, 120, 236, 40, 12, 7)
    rows = [('b12', 'b6', 'b10'), ('b1', 'b3', 'b19'), ('b4', 'b16', 'b8'), ('b15', 'b13', 'b18'), ('b0', 'b5', 'b14'), ('b11', 'b7', 'b9')]
    for r, names in enumerate(rows):
        for col, nm in enumerate(names):
            button(comp(pg, nm), *g[r][col])
    button(comp(pg, 'ldrcRxUpdate'), SLOTS[0][0], SLOTS[0][1], SLOTS[1][0] + SLOTS[1][2] - SLOTS[0][0], SLOTS[0][3])
    slot(comp(pg, 'b2'), 3)
    return 4, pg

def transmitter_setup():                                    # 33 TXSetupView (its 1.4.1 grid, approved by Malcolm, kept)
    pg = load_original(33)
    title(pg, 't0', 'Transmitter setup'); card(pg, 't0', page_touch(pg)); help_button(comp(pg, 'b17'))
    cols = [34, 222, 410, 598]; rows = [80, 162, 244]; W, H = 168, 70
    layout = [('b0', 'b11', 'b6', 'b15'), ('ldrcAppearance', 'b10', 'b5', 'b19'), ('b3', 'ldrcWifi', None, None)]
    for r, names in enumerate(layout):
        for col, nm in enumerate(names):
            if nm: button(comp(pg, nm), cols[col], rows[r], W, H)
    button(comp(pg, 'ldrcUpdate'), cols[2], rows[2], cols[3] + W - cols[2], H)
    comp(pg, 'ldrcUpdate')['txt'] = 'Transmitter updates'
    park(comp(pg, 'b7'))                                    # (screen 1.8.0: Appearance in its place; its page presses it for the pilot: "Background picture")
    text_on_card(comp(pg, 'ModelName'), 34, 336, 732, 56, font=0, colour=YELLOW, xcen=1)
    slot(comp(pg, 'b2'), 3)
    return 33, pg

def toggle_label(c, x, y, w, h, font, text):
    """A label that the page's own scripts recolour (grey = off, white = on): it stays a box, with black words."""
    place(c, x, y, w, h); c['sta'] = 1; c['font'] = font; c['txt'] = text; c['a']['txt_maxl'] = max(c['a'].get('txt_maxl', 0), len(text) + 2)
    c['c'].update({'pco': BLACK, 'borderc': 0}); c['a'].update({'xcen': 0, 'ycen': 1, 'style': 0, 'borderw': 0})

def model_options():                                        # 9 RXOptionsView
    pg = load_original(9)
    title(pg, 't0', 'Model options'); card(pg, 't0'); help_button(comp(pg, 'b17'))
    LX, LW, BX, BW, H = 26, 296, 330, 84, 28
    rows = [('t8', 'n3', 'Trim multiplier (0 = off)'), ('t7', 't10', "Receiver 'stop flying' volts"), ('t11', 't12', 'Max safe ESC current (A)'),
            ('t5', 'n0', 'Motor off value (-67)'), ('t6', 'n1', 'Throttle channel'), ('t9', 'n4', 'Countdown timer minutes'),
            ('t1', 'n2', 'Receiver battery correction'), ('t3', 'c1', 'Copy trims to all banks'), ('t4', 'c0', 'Use motor kill switch'),
            ('t2', 'c2', 'Timer counts down')]
    for i, (lab, val, text) in enumerate(rows):
        y = 78 + i * 32                                     # (10 rows, 12 px clear of the card at the top and the bottom)
        if lab in ('t2', 't3', 't4'):                       # the switches' scripts shade these labels grey or white: they go out of sight
            park(comp(pg, lab)); add_label(pg, 'l_' + lab, text, LX, y, LW, H, font=2)   # and a plain label stands in their place
        else: text_on_card(comp(pg, lab), LX, y, LW, H, font=2, text=text)
        v = comp(pg, val)
        if v['t'] == 'switch': switch(v, BX + 2, y, BW - 4, H)
        else: entry(v, BX, y, BW, H, font=2)
    e = comp(pg, 'exp0'); place(e, 452, 78, 320, 200)
    button(comp(pg, 'b3'), 452, 290, 320, 48, 'Model picture...')
    text_on_card(comp(pg, 'ModelName'), 452, 346, 320, 48, font=0, colour=YELLOW, xcen=1)
    place(comp(pg, 'Progress'), 14, 407, 772, 5)
    slot(comp(pg, 'b0'), 0, 'Servos...'); slot(comp(pg, 'b2'), 3, 'OK')
    return 9, pg

def sounds():                                               # 55 AudioView
    pg = load_original(55)
    title(pg, 't0', 'Sounds and brightness'); card(pg, 't0', page_touch(pg)); help_button(comp(pg, 'b0'))
    left = [('t7', 'c3', 'Timer voice'), ('t8', 'c4', 'Bank voice'), ('t10', 'c5', 'Connected voice'), ('t3', 'c0', 'Start and close sounds'), ('t4', 'c1', 'Trim change clicks')]
    right = [('t5', 'c2', 'Vario tones'), ('t11', 'n2', 'Vario bank (0 = all)'), ('t9', 'n0', 'Vario threshold (fpm)'), ('t12', 'n3', 'Vario spacing (fpm)')]
    for col, rows in ((0, left), (1, right)):
        for i, (lab, val, text) in enumerate(rows):
            y = 78 + i * 44; x = 28 if col == 0 else 410
            text_on_card(comp(pg, lab), x, y, 262, 38, font=2, text=text)
            v = comp(pg, val)
            if v['t'] == 'switch': switch(v, x + 270, y + 2, 84, 34)
            else: entry(v, x + 270, y, 84, 38, font=2)
    text_on_card(comp(pg, 't1'), 28, 310, 150, 40, font=2, text='Brightness')
    place(comp(pg, 'h0'), 190, 310, 570, 40); slider(comp(pg, 'h0'))
    text_on_card(comp(pg, 't2'), 28, 356, 150, 40, font=2, text='Volume')
    place(comp(pg, 'Ex1'), 190, 356, 570, 40); slider(comp(pg, 'Ex1'))
    slot(comp(pg, 'b10'), 3, 'OK')
    return 55, pg

def batteries():                                            # 51 TypeView
    pg = load_original(51)
    title(pg, 't0', 'Batteries'); card(pg, 't0', page_touch(pg)); help_button(comp(pg, 'b15'))
    text_on_card(comp(pg, 't2'), 40, 74, 330, 40, font=0, colour=YELLOW, text='Model battery')
    text_on_card(comp(pg, 't3'), 430, 74, 340, 40, font=0, colour=YELLOW, text='Transmitter battery')
    for i, (r, t, text) in enumerate([('r2s', 't6', '2S LiPo'), ('r3s', 't7', '3S LiPo'), ('r4s', 't8', '4S LiPo'), ('r5s', 't9', '5S LiPo'), ('r6s', 't10', '6S LiPo'), ('r12s', 't1', '12S LiPo')]):
        y = 120 + i * 46
        place(comp(pg, r), 50, y, 40, 40)
        text_on_card(comp(pg, t), 104, y, 260, 40, font=0, text=text)
    for i, (r, t, text) in enumerate([('r0', 't4', '2S LiFePO4'), ('r1', 't5', '2S LiPo / Li-ion')]):
        y = 120 + i * 46
        place(comp(pg, r), 440, y, 40, 40)
        text_on_card(comp(pg, t), 494, y, 280, 40, font=0, text=text)
    text_on_card(comp(pg, 'ModelName'), 430, 346, 340, 50, font=0, colour=YELLOW, xcen=1)   # (yellow, as on the other pages)
    slot(comp(pg, 'b10'), 3, 'OK')
    return 51, pg

def switches():                                             # 53 SwitchesView: 1-4 laid out as the switches are on the transmitter
    pg = load_original(53)
    title(pg, 't0', 'Switches on top'); card(pg, 't0', page_touch(pg)); help_button(comp(pg, 'b15'))
    for (num, sw), (y, left) in zip((('t1', 'sw1'), ('t2', 'sw2'), ('t3', 'sw3'), ('t4', 'sw4')), ((92, True), (172, True), (92, False), (172, False))):
        if left: tile(comp(pg, num), 34, y, 64, 64, font=0); tile(comp(pg, sw), 108, y, 280, 64)
        else: tile(comp(pg, sw), 412, y, 280, 64); tile(comp(pg, num), 702, y, 64, 64, font=0)
    t = comp(pg, 't'); text_on_card(t, 34, 256, 732, 76, font=2, colour=SOFT, xcen=1,
        text='Seen from above, with the sticks towards you,\r\neach number shows where its switch is.\r\nTouch a number or its job to set up that switch.')
    t['a']['ycen'] = 1
    text_on_card(comp(pg, 'ModelName'), 34, 340, 732, 50, font=0, colour=YELLOW, xcen=1)
    slot(comp(pg, 'b10'), 3, 'OK')
    return 53, pg

def one_switch():                                           # 54 OneSwitchView
    pg = load_original(54)
    title(pg, 'title', 'Switch'); card(pg, 'title', page_touch(pg)); help_button(comp(pg, 'b15'))
    sw = comp(pg, 'Sw'); place(sw, 458, 0, 70, 57); sw['sta'] = 1; sw['font'] = 0
    sw['c'].update({'bco': STRIP, 'pco': WHITE}); sw['a'].update({'xcen': 0, 'ycen': 1})
    left = [('r0', 't0'), ('r1', 't1'), ('r2', 't2'), ('r7', 't7'), ('r8', 't8')]
    right = [('r3', 't3'), ('r4', 't4'), ('r5', 't5'), ('r6', 't6'), ('r9', 't9')]
    for col, rows in ((0, left), (1, right)):
        for i, (r, t) in enumerate(rows):
            x = 40 if col == 0 else 420; y = 76 + i * 46
            place(comp(pg, r), x, y, 40, 40)
            text_on_card(comp(pg, t), x + 54, y, 300, 40, font=0)
    place(comp(pg, 'Progress'), 14, 407, 772, 5)               # (shown while OK saves: the thin strip under the card, as on the other pages)
    switch(comp(pg, 'c_revd'), 40, 356, 90, 40)
    text_on_card(comp(pg, 't99'), 144, 356, 220, 40, font=0, text='Reversed')
    text_on_card(comp(pg, 'ModelName'), 400, 356, 370, 40, font=0, colour=YELLOW, xcen=2)
    slot(comp(pg, 'b10'), 3, 'OK')
    return 54, pg

def buddy():                                                # 16 BuddyView (its show-and-hide script untouched)
    pg = load_original(16)
    title(pg, 't0', 'Wireless buddy'); comp(pg, 't0')['font'] = 0
    card(pg, 't0'); help_button(comp(pg, 'b15'))
    text_on_card(comp(pg, 't5'), 40, 84, 200, 40, font=6, text='Buddy'); switch(comp(pg, 'BuddyP'), 250, 86, 90, 36)
    text_on_card(comp(pg, 't4'), 40, 136, 200, 40, font=6, text='Master'); switch(comp(pg, 'BuddyM'), 250, 138, 90, 36)
    for nm, x in (('t1', 300), ('t2', 430), ('t3', 560)): text_on_card(comp(pg, nm), x, 200, 120, 34, font=6, colour=SOFT, xcen=1)
    text_on_card(comp(pg, 't6'), 40, 238, 250, 42, font=6, text='Switch positions')
    for nm, x in (('cb0', 300), ('cb1', 430), ('cb2', 560)): entry(comp(pg, nm), x, 238, 120, 42, xcen=1)   # (the choice centred, clear of the box's edge)
    button(comp(pg, 'b0'), 40, 304, 640, 50, 'Select channels to pass to buddy')
    slot(comp(pg, 'b10'), 3, 'OK')
    return 16, pg

def background():                                           # 17 BackGroundView: the page IS the preview, so no card over it
    pg = load_original(17)
    card(pg, None, rect=(150, 190, 500, 110))                # (screen 1.8.0: Colours moved to the Appearance page)
    text_on_card(comp(pg, 't1'), 166, 206, 250, 78, font=0, text='Background')
    for nm, x, txt in (('b0', 420, '+'), ('b1', 494, '-')): button(comp(pg, nm), x, 210, 64, 70, txt, font=0)
    entry(comp(pg, 'n0'), 568, 210, 70, 70, font=0)
    slot(comp(pg, 'b2'), 3, 'OK'); comp(pg, 'b2')['font'] = 6
    return 17, pg

def dialog(pg, frame, rect, head, head_text):
    """A small navy dialog over the page underneath (these pages have no background of their own)."""
    x, y, w, h = rect
    f = comp(pg, frame); place(f, x, y, w, h); f['sta'] = 1; f['txt'] = ''
    f['c'].update({'bco': NAVY, 'borderc': WHITE}); f['a'].update({'style': 1, 'borderw': 2})
    hd = comp(pg, head); place(hd, x + 2, y + 2, w - 4, 46); hd['sta'] = 1; hd['font'] = 0; hd['txt'] = head_text
    hd['c'].update({'bco': STRIP, 'pco': WHITE}); hd['a'].update({'xcen': 1, 'ycen': 1, 'style': 0, 'borderw': 0}); hd['a']['txt_maxl'] = max(hd['a'].get('txt_maxl', 0), len(head_text) + 2)
    pg['comps'] = [f] + [c for c in pg['comps'] if c['n'] != frame]

def trim_directions():                                      # 49 TrimDefView
    pg = load_original(49)
    title(pg, 't0', 'Set trim directions'); card(pg, 't0')
    for i, (nm, text) in enumerate((('ail', 'Push the AILERON trim button RIGHT'), ('ele', 'Push the ELEVATOR trim button DOWN'),
                                    ('thr', 'Push the THROTTLE trim button DOWN'), ('rud', 'Push the RUDDER trim button RIGHT'))):
        entry(comp(pg, nm), 60, 86 + i * 62, 680, 52, font=6); comp(pg, nm)['txt'] = text
        comp(pg, nm)['fresh'] = True                        # (the Teensy writes '... is defined!' here and never puts the instruction back)
    text_on_card(comp(pg, 't1'), 60, 342, 680, 44, font=2, colour=SOFT, xcen=1, text='Push them one at a time, in any order.')
    slot(comp(pg, 'b2'), 3, 'OK')
    return 49, pg

def rename():                                               # 50 RenameView
    pg = load_original(50)
    title(pg, 't0', 'Rename model'); card(pg, 't0', rect=(40, 121, 720, 230))   # (a small card, the picture round it, in the middle between the strip and OK)
    entry(comp(pg, 'NewName'), 60, 137, 680, 140, font=1); comp(pg, 'NewName')['a']['isbr'] = 1   # (two lines: a 30-letter name is 1016 px in font 1)
    add_label(pg, 'hint', 'Touch the name to change it.', 60, 295, 680, 40, font=2, colour=SOFT, xcen=1)
    slot(comp(pg, 'b10'), 3, 'OK')
    return 50, pg

def backup_dialog():                                        # 48 BackupView: a dialog over the Models page
    pg = load_original(48)
    dialog(pg, 'Dialog', (140, 112, 520, 240), 't3', 'Model memory backup'); ring(pg, 'Dialog')   # (the ring: its edge shows over the Models page's white lists)
    text_on_card(comp(pg, 'Modelname'), 160, 168, 480, 40, font=0, colour=YELLOW, xcen=1)
    text_on_card(comp(pg, 't0'), 160, 220, 210, 44, font=2, text='File name (.MOD)')
    entry(comp(pg, 't1'), 380, 220, 260, 44, font=2)
    button(comp(pg, 'b1'), 160, 284, 200, 54, 'Cancel'); button(comp(pg, 'b0'), 440, 284, 200, 54, 'OK')
    return 48, pg

def model_ids():                                            # 3 IDsStartView
    pg = load_original(3)
    title(pg, 't0', 'Model IDs'); card(pg, 't0'); help_button(comp(pg, 'b17'))
    text_on_card(comp(pg, 't2'), 34, 90, 210, 50, text='Stored ID'); entry(comp(pg, 't4'), 250, 90, 230, 50)
    button(comp(pg, 'b7'), 500, 90, 266, 50, 'Delete stored ID')
    text_on_card(comp(pg, 't3'), 34, 160, 210, 50, text="This model's ID"); entry(comp(pg, 't5'), 250, 160, 230, 50)
    button(comp(pg, 'b11'), 500, 160, 266, 50, "Store this model's ID")
    button(comp(pg, 'b3'), 500, 240, 266, 50, 'Check for duplicates')
    text_on_card(comp(pg, 't1'), 34, 330, 732, 56, font=0, colour=YELLOW, xcen=1)
    slot(comp(pg, 'b4'), 3, 'OK')
    return 3, pg

def file_exchange():                                        # 47 FileExchView: a dialog
    pg = load_original(47)
    dialog(pg, 'Dialog', (140, 120, 520, 240), 't0', 'File exchange'); ring(pg, 'Dialog')
    comp(pg, 't1')['fresh'] = True                          # (the Teensy never clears it: 'Sent 2716 bytes.' from the last transfer showed under 'Waiting ...')
    text_on_card(comp(pg, 'filename'), 160, 176, 480, 36, font=0, colour=YELLOW, xcen=1)
    text_on_card(comp(pg, 't1'), 160, 214, 480, 32, font=2, colour=WHITE, xcen=1)
    place(comp(pg, 'Progress'), 160, 254, 480, 26)
    button(comp(pg, 'b0'), 300, 292, 200, 54, 'Cancel'); comp(pg, 'b0')['font'] = 6
    return 47, pg

def bank_rate_in_strip(pg):                                 # the Rotorflight pages say which bank and rate, top left
    for nm, y in (('t14', 3), ('t8', 29)):
        c = comp(pg, nm); place(c, 10, y, 170, 26); c['sta'] = 1; c['font'] = 2
        c['c'].update({'bco': STRIP, 'pco': WHITE}); c['a'].update({'xcen': 0, 'ycen': 1, 'style': 0, 'borderw': 0})

def rotorflight_options():                                  # 8 RFView
    pg = load_original(8)
    title(pg, 't0', 'Rotorflight options'); card(pg, 't0'); help_button(comp(pg, 'b0')); bank_rate_in_strip(pg)
    rows = [('t3', 'sw0', 'Link rates and banks'), ('t4', 't5', 'Version'), ('t6', 'Arming', 'Arming channel'), ('t1', 'Ratio', 'Main RPM ratio')]
    for i, (lab, val, text) in enumerate(rows):
        y = 84 + i * 56
        text_on_card(comp(pg, lab), 34, y, 240, 46, font=6, text=text)
        v = comp(pg, val)
        if v['t'] == 'switch': switch(v, 284, y + 4, 100, 38)
        else: entry(v, 284, y, 110, 46, font=6)
    for i, (nm, text) in enumerate((('Pid', 'PIDs ...'), ('b1', 'Rates ...'), ('b2', 'Governor ...'), ('b3', 'Backup / Restore ...'))):
        button(comp(pg, nm), 430, 84 + i * 56, 336, 46, text)
    text_on_card(comp(pg, 't2'), 34, 312, 732, 36, font=6, colour=WHITE, xcen=1)   # ('Restoring Rates Advanced: LocalRates 4 to FC Rates 4' is 626 px in font 6, 761 in font 0)
    text_on_card(comp(pg, 't11'), 34, 352, 732, 46, font=0, colour=YELLOW, xcen=1)
    place(comp(pg, 'Progress'), 14, 407, 772, 5)
    slot(comp(pg, 'b4'), 3, 'OK')
    return 8, pg

def rotorflight_backup():                                   # 12 RFBackUpView (green = backup, red = restore: kept)
    pg = load_original(12)
    title(pg, 't0', 'Rotorflight backup'); card(pg, 't0', rect=(110, 86, 580, 300)); help_button(comp(pg, 'b0')); bank_rate_in_strip(pg)   # (a small card: the picture round it)
    for nm, y in (('b2', 104), ('b3', 190)):
        c = comp(pg, nm); keep = dict(c['c']); button(c, 150, y, 500, 64); c['c'].update({'bco': keep['bco'], 'pco': keep['pco']})
    text_on_card(comp(pg, 't1'), 150, 262, 500, 40, font=2, colour=YELLOW, xcen=1, text='Only press the red button if you are quite sure.')
    text_on_card(comp(pg, 't11'), 130, 320, 540, 50, font=0, colour=YELLOW, xcen=1)
    slot(comp(pg, 'b4'), 3, 'OK')
    return 12, pg

def id_check():                                             # 46 IDsView: the list is the page
    pg = load_original(46)
    title(pg, 't0', 'Model IDs: duplicates'); comp(pg, 't0')['font'] = 0; help_button(comp(pg, 'b17'))
    backgrounds_first(pg, 't0')
    lst = comp(pg, 'MMems'); place(lst, 14, 66, 772, lst['h']); sunken_list(lst)
    text_on_card(comp(pg, 't1'), 14, 419, 170, 46, font=6, text='Duplicates')   # (centred on the OK button's middle)
    entry(comp(pg, 'n0'), 190, 419, 90, 46)
    slot(comp(pg, 'b10'), 3, 'OK'); comp(pg, 'b10')['font'] = 6
    return 46, pg

GROUND = {4, 33, 9, 55, 51, 53, 54, 16, 49, 3, 8, 46}  # blue everywhere; 50 and 12 have small cards with the picture round them; 17 IS the picture; 48 and 47 are dialogs

PAGES = {4: model_setup, 33: transmitter_setup, 9: model_options, 55: sounds, 51: batteries, 53: switches, 54: one_switch, 16: buddy, 17: background,
         49: trim_directions, 50: rename, 48: backup_dialog, 3: model_ids, 47: file_exchange, 8: rotorflight_options, 12: rotorflight_backup, 46: id_check}

if __name__ == '__main__':
    want = [int(a) for a in sys.argv[1:]] or list(PAGES)
    good = True
    for pid in want:
        p, pg = PAGES[pid]()
        if p in GROUND: ground(pg)
        if verify(p, pg): save(p, pg)
        else: good = False
    sys.exit(0 if good else 1)
