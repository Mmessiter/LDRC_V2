"""Polish (10 Oct 2026) of the "rfmore" Rotorflight pages: 58/59 Rescue, 60 Servos, 62/63/66 Mixer, 64/65 Gyro filters,
74 Calibrate. Malcolm: "make the screens look more beautiful, well designed and easy to use ... Don't change the logic".
Their words, rows and keypad questions are made by their generators (hmi/rescue_pages.py, servo_pages.py, travel_pages.py,
filter_pages.py; 74 by fcsetup_pages.py); this module only moves and recolours what those make. Every value is absolute or
worked out from an edge the polish keeps, so a second run changes nothing."""
from polish import comp, park, put

STRIP_TEXT_X = 10   # t9 (the bank) and t11 (the model's name), top left in the title strip
ROW_H, PITCH = 36, 40   # the Rescue / Rates row (hmi/rescue_pages.TIERS[2]): 36 high, 4 px apart

def regrid(pg, rows, y0):
    """Each entry of `rows` is one row of the page: the components standing in it go to y0 + row * PITCH, ROW_H high (a
    switch keeps its height, centred in the row)."""
    for r, names in enumerate(rows):
        y = y0 + r * PITCH
        for n in names:
            c = comp(pg, n)
            if c['t'] == 'switch': put(pg, n, y=y + (ROW_H - c['h']) // 2)
            else: put(pg, n, y=y, h=ROW_H)

def message_box(pg, first, rows, pitch, right=None):
    """The "busy" message box (reading, writing, the 4-s "Saved ..." words; it takes the taps where it lies while it shows)
    over `rows` whole rows of `pitch` from the row of component `first`, from the island's inner left edge to `right`
    (default the inner right edge). (Touch audit, 10 Oct 2026: the polish moved the rows but not the box, so the box lay
    over fields it used to leave free. Each page's box now lies only where it took the taps before - fields it already
    covered, labels, headings, bare card - with its edges between rows and columns, so it cuts no word in half. The
    words: one line of font 2 needs 28 px, two lines 68.)"""
    card, f = comp(pg, 'card'), comp(pg, first)
    x = card['x'] + 16; x1 = right if right is not None else card['x'] + card['w'] - 16
    put(pg, 'busy', x=x, y=f['y'] - (pitch - f['h']) // 2, w=x1 - x, h=rows * pitch)

def widen_values(pg, names, w):
    """The value boxes of one column (fields `names`) made `w` wide, growing to the LEFT: their right edge stays where it
    is, each label box gives up the room (still 6 px from its value), and a switch stays centred in its value's place."""
    texts = [comp(pg, n) for n in names if comp(pg, n)['t'] == 'text']
    right = max(c['x'] + c['w'] for c in texts)
    vx = right - w
    for n in names:
        c, lab = comp(pg, n), comp(pg, 'l' + n)
        if c['t'] == 'switch': put(pg, n, x=vx + (w - c['w']) // 2)
        else: put(pg, n, x=vx, w=w)
        put(pg, 'l' + n, w=vx - 6 - lab['x'])

def strip_clear_of_title(pg, title_w):
    """Design system: the model's name (and the bank above it) stop at least 20 px before the title, whose longest text
    is `title_w` px wide in the strip's font, centred on the 800-px strip."""
    w = min(200, (800 - title_w) // 2 - 20 - STRIP_TEXT_X)
    put(pg, 't9', w=w); put(pg, 't11', w=w)

def all_banks(pg):
    """Design system: a page's default text is what the main board writes there (a screen-only restart shows it). The
    filters and the calibration are the same for every bank: the main board writes "All banks" (RF_Filters.h:134,
    RF_FcSetup.h:573), not the generator's "Bank 1"."""
    put(pg, 't9', txt='All banks')

def rescue1(pg):
    # The message box over the climb rows (4 and 5): the left column and the right column's labels, which it covered
    # before; the right column's values (it left about half of them free) and the rows above stay free
    lab = comp(pg, 'ltn11')
    message_box(pg, 'ltn4', 2, PITCH, right=lab['x'] + lab['w'])

def rescue2(pg):
    # rfmore.0: "Hold height" (110 px in font 2, RF_Rescue.h:32) was cut to "Hold he..." in a 100-px box: the six value
    # boxes 130 wide, so they still line up
    widen_values(pg, ['tn0', 'tn1', 'tn2', 'tn3', 'tn4', 'tn5'], 130)
    # the message box over rows 4 and 5 (the two fields it covered before), across the island
    message_box(pg, 'ltn4', 2, PITCH)

def filters1(pg):
    all_banks(pg)
    # The filter types the main board writes (RF_Filters.h:29, "2nd order" 94 px) had 1 px to spare in a 100-px box:
    # 110, on both filter pages, every row of each column
    widen_values(pg, ['tn0', 'tn1', 'tn2', 'tn3', 'tn4', 'tn5'], 110)
    widen_values(pg, ['tn6', 'tn7', 'tn8', 'tn9', 'tn10'], 110)
    # the message box over rows 4 and 5 (the RPM filter's heading and Enable, which it covered before), to the end of
    # the right column's labels: the wider values reached under the old box
    lab = comp(pg, 'ltn9')
    message_box(pg, 'ltn9', 2, 37, right=lab['x'] + lab['w'])

def filters2(pg):
    all_banks(pg)
    widen_values(pg, ['tn3', 'tn4', 'tn5', 'tn0', 'tn1', 'tn2'], 110)
    widen_values(pg, ['tn6', 'tn7', 'tn8', 'tn9', 'tn10', 'tn11'], 110)
    # rfmore.10: one shade per filter FAMILY across the two pages (page 64: pale yellow lowpass, pale blue RPM, pale green
    # dynamic notches): lowpass 2 pale yellow as lowpass 1 (it was blue, page 64's RPM colour), notch 2 pale green as notch 1
    for n in ('ltn0', 'ltn1', 'ltn2'): put(pg, n, c={'bco': 65497})
    for n in ('ltn9', 'ltn10', 'ltn11'): put(pg, n, c={'bco': 59323})
    # the message box as on page 64: rows 4 and 5 (Lowpass filter 2's heading and Enable, notch 2's heading and label)
    lab = comp(pg, 'ltn9')
    message_box(pg, 'h0', 2, 37, right=lab['x'] + lab['w'])

def mixer1(pg):
    # The told rows i0/i1 hold the main board's whole line (RF_Travel.h:57-59). Today's "Main Rotor Direction:
    # Counter-clockwise" is 392 px, the sentence-case "Main rotor direction: Counter-clockwise" 380, the polish's
    # "Main rotor direction: Anticlockwise" 332: the trims column only as wide as its words need (the generator's rule,
    # rescue_pages.compact_plan: words + 20, 6, the value), the rest of the island's width to the left column, so
    # every one of the three fits (the left column 398 px: 21 more than the generator gives it)
    from fontw import width
    val = comp(pg, 'tn9'); right = val['x'] + val['w']
    lw1 = max(width(comp(pg, n)['font'], comp(pg, n)['txt']) for n in ('ltn9', 'ltn10', 'ltn11')) + 20
    x1 = right - val['w'] - 6 - lw1                       # the trims column's left edge
    put(pg, 'h1', x=x1, w=right - x1)
    for n in ('ltn9', 'ltn10', 'ltn11'): put(pg, n, x=x1, w=lw1)
    x0 = comp(pg, 'h0')['x']; w0 = x1 - 20 - x0          # the left column, 20 px short of the trims (C_COLGAP)
    for n in ('h0', 'i0', 'i1'): put(pg, n, w=w0)
    for n in ('tn6', 'tn7', 'tn8'):
        put(pg, 'l' + n, w=w0 - 6 - val['w'])
        put(pg, n, x=x0 + w0 - val['w'] + (val['w'] - comp(pg, n)['w']) // 2)   # (centred in its value's place, as the generator does)
    # The three Mixer pages were made in the series' smallest row (35 high, 37 apart: page 2 has eight rows), so the pale
    # boxes almost touched: the Rescue / Rates row (36 high, 40 apart) on one grid from the card's top for all three,
    # each heading in the first row, the buttons where they were
    regrid(pg, [['h0', 'h1'], ['i0', 'ltn9', 'tn9'], ['i1', 'ltn10', 'tn10'], ['ltn6', 'tn6', 'ltn11', 'tn11'],
                ['ltn7', 'tn7'], ['ltn8', 'tn8']], comp(pg, 'card')['y'] + 16)
    # the message box over rows 4 and 5 (the elevator and collective switches, which it covered before), across the island
    message_box(pg, 'ltn7', 2, PITCH)

def servos(pg):
    # the title the main board writes, "Servo 8 of 8 (Rotorflight)" (RF_Servos.h:30), is 342 px in font 0
    strip_clear_of_title(pg, 342)

def mixer2(pg):
    # "Mixer: main rotor geometry" is 374 px in font 0: the name stopped 3 px before it
    strip_clear_of_title(pg, 374)
    # The heading "Main rotor geometry" said the title again ("Mixer: main rotor geometry"): parked, and the rows on the
    # series' grid (mixer1) from the first row - seven rows of the Rescue page's size now fit where eight small ones stood
    park(pg, 'h0')
    left = [['ltn%d' % i, 'tn%d' % i] for i in range(7)]
    left[0] += ['ltn7', 'tn7']; left[1] += ['ltn8', 'tn8']
    regrid(pg, left, comp(pg, 'card')['y'] + 16)
    # the message box over rows 3 and 4 (the cyclic and collective pitch limits, which it covered before)
    message_box(pg, 'ltn3', 2, PITCH)

def mixer3(pg):
    # The heading "Tail rotor settings" said the title again ("Mixer: tail rotor"): parked, the rows on the series' grid
    park(pg, 'h0')
    regrid(pg, [['i0']] + [['ltn%d' % i, 'tn%d' % i] for i in range(6)], comp(pg, 'card')['y'] + 16)
    # the message box over rows 3 and 4 (the yaw calibration and CW limit, which it covered before)
    message_box(pg, 'ltn2', 2, PITCH)

def level(pg):
    all_banks(pg)
    # rfmore.5: "Calibrate level" from the left edge of the column above it (the level lines), up to 12 px before Save
    lx = comp(pg, 'tn0')['x']
    put(pg, 'b2', x=lx, w=comp(pg, 'b3')['x'] - 12 - lx)
    # ... and the trims in the order the level line reads, "Roll ... Pitch ...": roll first (the main board writes them
    # by name, tn2 pitch and tn3 roll, RF_FcSetup.h:592)
    y1, y2 = sorted((comp(pg, 'tn2')['y'], comp(pg, 'tn3')['y']))
    for n in ('ltn3', 'tn3'): put(pg, n, y=y1)
    for n in ('ltn2', 'tn2'): put(pg, n, y=y2)
    # The message box ("Calibrating: keep it still ...", "Calibrated: roll ..") sat across the top 9 px of the buttons on
    # this short island (design system: a message box never covers the bottom row): centred on the rows above them instead
    top, foot = comp(pg, 'h0')['y'], comp(pg, 'b1')['y'] - 14
    box = comp(pg, 'busy'); put(pg, 'busy', y=top + (foot - top - box['h']) // 2)

EDITS = {58: rescue1, 59: rescue2, 60: servos, 62: mixer1, 63: mixer2, 66: mixer3, 64: filters1, 65: filters2, 74: level}
