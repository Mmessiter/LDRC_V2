#!/usr/bin/env python3
"""The remaining pages in the System pages' style, batch 2: the channel pages (Malcolm, 2026-10-03). Same rules as
batch 1 (hmi/pagestyle.py verify()): only places, sizes, fonts and colours change. The 16-channel tables become two
columns of eight rows: the channel, its control, its name. A cell whose colour means something (a grey box for a
channel that shares a timer) keeps its colour. Run: python3 hmi/restyle_batch2.py [page ids...]"""
import sys
from pagestyle import *

CH_LABELS = ['t3', 't1', 't2', 't4', 't5', 't6', 't7', 't8', 't17', 't18', 't19', 't20', 't10', 't11', 't12', 't13']
CH_NAMES = ['ch%d' % i for i in range(1, 17)]

def strip_left(pg, items):
    """Small words at the left of the title strip: the model's name, the bank (two lines at most)."""
    for (nm, colour), y in zip(items, (4, 30)):
        c = comp(pg, nm); place(c, 10, y, 200, 25); c['sta'] = 1; c['font'] = 2
        c['c'].update({'bco': STRIP, 'pco': colour}); c['a'].update({'xcen': 0, 'ycen': 1, 'style': 0, 'borderw': 0})

def thin_progress(pg):
    if has(pg, 'Progress'): place(comp(pg, 'Progress'), 14, 407, 772, 5)

def keep_colour(c, fn, *args, **kw):
    """Style it, but keep a background colour that is not plain white (it means something)."""
    bco = c['c'].get('bco'); fn(c, *args, **kw)
    if bco not in (None, WHITE): c['c']['bco'] = bco

def channel_rows(pg, controls, name_w=210, labels=CH_LABELS, pitch=41, h=36, y0=74):
    """16 channels in two columns of eight: 'Ch n', its control, its name."""
    for i in range(16):
        col, r = divmod(i, 8)
        x0 = 26 if col == 0 else 410; y = y0 + r * pitch
        text_on_card(comp(pg, labels[i]), x0, y, 72, h, font=6)
        c = comp(pg, controls[i])
        if c['t'] == 'checkbox': place(c, x0 + 82, y + (h - 34) // 2, 34, 34)
        elif c['t'] == 'switch': switch(c, x0 + 80, y + 3, 72, h - 6)
        else: keep_colour(c, entry, x0 + 80, y, 72, h)
        text_on_card(comp(pg, CH_NAMES[i]), x0 + 162, y, name_w, h, font=6, colour=SOFT)

def keep_ink(c, fn, *args, **kw):
    """Style it, but keep the colour of its figures (blue input, red output: it tells the columns apart)."""
    pco = c['c'].get('pco'); fn(c, *args, **kw); c['c']['pco'] = pco

def subtrim():                                              # 32 SubTrimView (its scripts colour the cells: grey, or white with red for the chosen one)
    pg = load_original(32)
    title(pg, 't0', 'Subtrim'); card(pg, 't0'); help_button(comp(pg, 'b3'))
    strip_left(pg, [('ModelName', YELLOW)])
    labels = ['t3', 't1', 't2', 't4', 't6', 't7', 't8', 't9', 't17', 't18', 't19', 't20', 't10', 't11', 't12', 't13']
    channel_rows(pg, ['n00'] + ['n%d' % i for i in range(1, 16)], labels=labels, pitch=34, h=30, y0=76)
    place(comp(pg, 'h0'), 26, 352, 740, 40); slider(comp(pg, 'h0'))
    park(comp(pg, 'n0'))                                    # (the value the scripts work with: never shown legibly, still there)
    slot(comp(pg, 'b2'), 0, 'Zero'); slot(comp(pg, 'b1'), 1, '-'); slot(comp(pg, 'b0'), 2, '+'); slot(comp(pg, 'b10'), 3, 'OK')
    for nm in ('b1', 'b0'): comp(pg, nm)['font'] = 0
    return 32, pg

def inputs():                                               # 39 InputsView: input, name (touch to rename), output; and the trims
    pg = load_original(39)
    title(pg, 't0', 'Inputs'); card(pg, 't0'); help_button(comp(pg, 'b15'))
    strip_left(pg, [('ModelName', YELLOW)])
    labels = ['t3', 't1', 't2', 't4', 't5', 't6', 't7', 't8', 't17', 't18', 't19', 't20', 't12', 't11', 't10', 't9']
    outs = ['n%d' % i for i in range(4, 20)]
    # Each block: Ch label 70 (Ch10 is 60 px in font 6), In 46, Name 142, Out 48, 2 px apart; the trims at the right.
    for side, x0 in ((0, 30), (1, 352)):
        for nm, dx, w, text in (('hIn%d' % side, 72, 46, 'In'), ('hName%d' % side, 120, 142, 'Name'), ('hOut%d' % side, 264, 48, 'Out')):
            add_label(pg, nm, text, x0 + dx, 74, w, 24, font=2, colour=SOFT, xcen=1)
    add_label(pg, 'hTrim', 'Trim out', 676, 74, 94, 24, font=2, colour=SOFT, xcen=1)
    for i in range(16):
        side, r = divmod(i, 8); x0 = 30 if side == 0 else 352; y = 100 + r * 37
        text_on_card(comp(pg, labels[i]), x0, y, 70, 33, font=6)
        keep_ink(comp(pg, 'c%d' % (i + 1)), entry, x0 + 72, y, 46, 33)
        entry(comp(pg, 'ch%d' % (i + 1)), x0 + 120, y, 142, 33)
        keep_ink(comp(pg, outs[i]), entry, x0 + 264, y, 48, 33)
    for r in range(4):
        y = 100 + r * 37
        text_on_card(comp(pg, 'tr%d' % (r + 1)), 676, y, 48, 33, font=6)
        keep_ink(comp(pg, 'n%d' % r), entry, 726, y, 44, 33)
    thin_progress(pg)
    slot(comp(pg, 'b10'), 3, 'OK'); comp(pg, 'b10')['font'] = 6
    return 39, pg

def buddy_channels():                                       # 18 BuddyChView
    pg = load_original(18)
    title(pg, 't0', 'Buddy channels'); card(pg, 't0')
    channel_rows(pg, ['fs%d' % i for i in range(1, 17)], pitch=36, h=32, y0=74)
    switch(comp(pg, 'mSwitch'), 106, 364, 72, 30)
    text_on_card(comp(pg, 't14'), 188, 361, 580, 36, font=6, colour=WHITE, text='Top switches too (motor, safety, bank and rates)')
    thin_progress(pg)
    slot(comp(pg, 'b1'), 0, 'All'); slot(comp(pg, 'b2'), 1, 'None'); slot(comp(pg, 'b10'), 3, 'OK')
    return 18, pg

def servo_types():                                          # 34 ServosTypeView: 11 channels, frequency and centre pulse
    pg = load_original(34)
    title(pg, 't0', 'PWM servo types'); card(pg, 't0'); help_button(comp(pg, 'b17'))
    strip_left(pg, [('ModelName', YELLOW)])
    text_on_card(comp(pg, 't9'), 200, 72, 120, 26, font=2, colour=SOFT, xcen=1, text='Hz')
    text_on_card(comp(pg, 't15'), 330, 72, 120, 26, font=2, colour=SOFT, xcen=1, text='Centre (us)')
    labels = ['t3', 't1', 't2', 't4', 't5', 't6', 't7', 't8', 't10', 't11', 't12']
    hz = ['n0', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7', 'n16', 'n18', 'n20']
    us = ['n8', 'n9', 'n10', 'n11', 'n12', 'n13', 'n14', 'n15', 'n17', 'n19', 'n21']
    names = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5', 'ch6', 'ch7', 'ch8', 't13', 't14', 't16']
    for i in range(11):
        y = 100 + i * 27                                    # (the last row ends 11 px above the card's edge)
        text_on_card(comp(pg, labels[i]), 40, y, 150, 25, font=2)
        keep_colour(comp(pg, hz[i]), entry, 210, y, 100, 25, font=2)
        keep_colour(comp(pg, us[i]), entry, 340, y, 100, 25, font=2)
        text_on_card(comp(pg, names[i]), 470, y, 290, 25, font=2, colour=SOFT)
    thin_progress(pg)
    slot(comp(pg, 'b0'), 0, 'Defaults'); slot(comp(pg, 'b10'), 3, 'OK')
    return 34, pg

def servo_speed():                                          # 35 SlowServoView
    pg = load_original(35)
    title(pg, 't0', 'Servo speed'); card(pg, 't0'); help_button(comp(pg, 'b17'))
    strip_left(pg, [('t14', WHITE), ('ModelName', YELLOW)])
    channel_rows(pg, ['n%d' % i for i in range(16)])
    t9 = comp(pg, 't9'); text_on_card(t9, SLOTS[1][0], 414, SLOTS[2][0] + SLOTS[2][2] - SLOTS[1][0], 56, font=2, colour=SOFT, xcen=1, text='Speed: 1 (slow) to 100')
    thin_progress(pg)
    slot(comp(pg, 'b0'), 0, 'Reset'); slot(comp(pg, 'b10'), 3, 'OK')
    return 35, pg

def failsafe():                                             # 36 FailSafeView
    pg = load_original(36)
    title(pg, 't0', 'Failsafe'); card(pg, 't0', page_touch(pg)); help_button(comp(pg, 'b15'))
    strip_left(pg, [('ModelName', YELLOW)])
    channel_rows(pg, ['fs%d' % i for i in range(1, 17)])
    thin_progress(pg)
    slot(comp(pg, 'b1'), 0, 'All'); slot(comp(pg, 'b2'), 1, 'None'); slot(comp(pg, 'b0'), 2, 'Save'); slot(comp(pg, 'b10'), 3, 'OK')
    return 36, pg

def reverse():                                              # 37 ReverseView
    pg = load_original(37)
    title(pg, 't0', 'Reverse'); card(pg, 't0'); help_button(comp(pg, 'b15'))
    strip_left(pg, [('ModelName', YELLOW)])
    channel_rows(pg, ['fs%d' % i for i in range(1, 17)])
    thin_progress(pg)
    slot(comp(pg, 'b10'), 3, 'OK')
    return 37, pg

def stepper_row(pg, y, h, label, text, value, minus, plus, info=None, info_text=None, lx=316, lw=170, vx=490):
    """A setting with - and + beside its box, and its range (or a name) after them."""
    text_on_card(comp(pg, label), lx, y, lw, h, font=2, text=text)
    v = comp(pg, value); entry(v, vx, y, 64, h)
    button(comp(pg, minus), vx + 70, y, 50, h, '-'); button(comp(pg, plus), vx + 124, y, 50, h, '+')
    if info: text_on_card(comp(pg, info), vx + 182, y, 776 - (vx + 182), h, font=2, colour=SOFT, text=info_text)

def mixes():                                                # 29 MixesView
    pg = load_original(29)
    title(pg, 't0', 'Mixes'); card(pg, 't0'); help_button(comp(pg, 'b15'))
    strip_left(pg, [('ModelName', YELLOW)])
    for i, (lab, sw, text) in enumerate((('t12', 'c0', 'Mix input'), ('t6', 'Enabled', 'Mix output'), ('t8', 'od', 'One direction'), ('t4', 'Reversed', 'Reversed'))):
        y = 84 + i * 54
        text_on_card(comp(pg, lab), 28, y, 150, 44, font=2, text=text); switch(comp(pg, sw), 180, y + 4, 84, 36)
    rows = [('t7', 'Mix number', 'MixNumber', 'b1', 'b0', 't11', '1 - 32'), ('t3', 'Bank (0 = all)', 'FlightMode', 'b3', 'b2', 't10', None),
            ('t1', 'Master channel', 'MasterChannel', 'b5', 'b4', 'chM', None), ('t2', 'Slave channel', 'SlaveChannel', 'b7', 'b6', 'chS', None),
            ('t9', 'Offset', 'Offset', 'b18', 'b19', 't13', '-90 to +90'), ('t5', 'Percent', 'Percent', 'b9', 'b8', 't14', '1 - 200')]
    for i, (lab, text, val, mi, pl, info, itext) in enumerate(rows):
        stepper_row(pg, 76 + i * 54, 44, lab, text, val, mi, pl, info, itext, lx=296, lw=156, vx=456)   # (the names after the + have 138 px: 'Flight mode 1' is 132; 'Master channel' ends 9 px before its box)
    slot(comp(pg, 'b22'), 0, 'Test ...'); slot(comp(pg, 'b10'), 3, 'OK')
    return 29, pg

def macros():                                               # 27 MacrosView
    pg = load_original(27)
    title(pg, 't0', 'Macros'); card(pg, 't0'); help_button(comp(pg, 'b15')); comp(pg, 'b15')['font'] = 6
    strip_left(pg, [('ModelName', YELLOW)])
    rows = [('t7', 'Macro number', 'Mno', 'b1', 'b0', '1 - 8'), ('t3', 'Trigger channel', 'Tch', 'b3', 'b2', '0 - 16'),
            ('t1', 'Channel to move (1 - 16)', 'Mch', 'b5', 'b4', None), ('t5', 'Move to position', 'Pos', 'b8', 'b9', '0 - 180'),
            ('t2', 'Delay', 'Del', 'b7', 'b6', '0 - 255 (x 0.1 s)'), ('t4', 'Duration', 'Dur', 'b14', 'b13', '1 - 255 (x 0.1 s)')]
    for i, (lab, text, val, mi, pl, rng) in enumerate(rows):
        y = 78 + i * 54
        text_on_card(comp(pg, lab), 30, y, 300, 46, font=6, text=text)
        entry(comp(pg, val), 340, y, 70, 46)
        button(comp(pg, mi), 418, y, 56, 46, '-'); button(comp(pg, pl), 480, y, 56, 46, '+')
        if rng: add_label(pg, 'rng_' + val, rng, 546, y, 230, 46, font=2, colour=SOFT)
    text_on_card(comp(pg, 'chM'), 546, 78 + 2 * 54, 230, 46, font=6, colour=YELLOW)
    slot(comp(pg, 'b10'), 3, 'OK'); comp(pg, 'b10')['font'] = 6
    return 27, pg

def dual_rates():                                           # 31 DualRatesView (b22: a hidden helper, left as it was)
    pg = load_original(31)
    title(pg, 't0', 'Rates'); card(pg, 't0', page_touch(pg)); help_button(comp(pg, 'b17'))
    strip_left(pg, [('t1', WHITE), ('ModelName', YELLOW)])
    for i, (lab, val) in enumerate((('t9', 'rate1'), ('t10', 'rate2'), ('t2', 'rate3'))):
        y = 76 + i * 44
        text_on_card(comp(pg, lab), 30, y, 130, 40, font=6); entry(comp(pg, val), 170, y, 90, 40)
    lst = comp(pg, 'rate'); place(lst, 30, 214, 250, lst['h']); sunken_list(lst)
    add_label(pg, 'chhead', 'Channels using these rates', 300, 72, 470, 30, font=2, colour=SOFT, xcen=1)
    pairs = [('t12', 'n2'), ('t8', 'n0'), ('t11', 'n1'), ('t13', 'n3'), ('t16', 'n6'), ('t14', 'n4'), ('t15', 'n5'), ('t17', 'n7')]
    for i, (lab, val) in enumerate(pairs):                  # (the Teensy writes the channels' NAMES here, "Elevator", "Not used": 150 px)
        col, r = divmod(i, 4); x = 300 if col == 0 else 540; y = 106 + r * 46
        text_on_card(comp(pg, lab), x, y, 150, 40, font=6); entry(comp(pg, val), x + 154, y, 74, 40)
    text_on_card(comp(pg, 't3'), 300, 300, 470, 40, font=2, colour=WHITE, xcen=1)
    text_on_card(comp(pg, 't7'), 300, 344, 470, 40, font=2, colour=WHITE, xcen=1)
    slot(comp(pg, 'b0'), 0, 'Refresh'); slot(comp(pg, 'b10'), 3, 'OK')
    return 31, pg

def trims():                                                # 28 TrimView: laid out as the trims are on the transmitter (kept)
    pg = load_original(28)
    title(pg, 't8', 'Trims'); card(pg, 't8', page_touch(pg), rect=(109, 66, 600, 340)); help_button(comp(pg, 'b17'))   # (a card as wide as the trims: the picture each side)
    strip_left(pg, [('t1', WHITE), ('ModelName', YELLOW)])
    for c in pg['comps']:                                   # everything of the trims a little lower: the card starts at 66
        if c['n'] in ('n1', 'n2', 'n3', 'n4', 'b0', 'b1', 'b2', 'b3', 'b4', 'b5', 'b6', 'b7', 'ch1', 'ch2', 'ch3', 'ch4', 'c1', 'c2', 'c3', 'c4'):
            c['y'] += 10
    for c in pg['comps']:                                   # the lower half 4 px higher again: its labels end 8 px above the card's edge
        if c['n'] in ('ch1', 'ch3', 'b2', 'b3', 'b4', 'b6', 'n1', 'n3', 'c1', 'c4'):
            c['y'] -= 4
    for nm in ('c1', 'c2', 'c3', 'c4'):
        c = comp(pg, nm); c['sta'] = 1; c['c'].update({'bco': NAVY, 'pco': WHITE}); c['a'].update({'xcen': 1, 'ycen': 1})
    for nm in ('ch1', 'ch2', 'ch3', 'ch4'): slider(comp(pg, nm))
    for nm in ('n1', 'n2', 'n3', 'n4'):
        c = comp(pg, nm); c['sta'] = 1; c['c'].update({'bco': NAVY, 'pco': WHITE})
    slot(comp(pg, 'b8'), 0, 'Reset')
    button(comp(pg, 'b9'), SLOTS[1][0], SLOTS[1][1], SLOTS[2][0] + SLOTS[2][2] - SLOTS[1][0], SLOTS[1][3], 'Move to subtrim')
    slot(comp(pg, 'b10'), 3, 'OK')
    return 28, pg

def fix_failsafe_all_none(pg):   # 36: All and None listed channels 9 and 10 as "sf9sg10" (sic), so OK did not save those two
    for nm in ('b1', 'b2'):
        c = comp(pg, nm); c['ev']['r'] = c['ev']['r'].replace('fs8sf9sg10fs11', 'fs8fs9fs10fs11')
FIXES = {36: fix_failsafe_all_none}

GROUND = {34, 35, 36, 37, 32, 39, 18, 29, 27, 31}   # blue everywhere; 28 (the trims) has a card as wide as the trims, the picture each side

PAGES = {34: servo_types, 35: servo_speed, 36: failsafe, 37: reverse, 32: subtrim, 39: inputs, 18: buddy_channels, 29: mixes, 27: macros, 31: dual_rates, 28: trims}

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
