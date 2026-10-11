"""Polish of the mixing pages (10 Oct 2026; Malcolm: "make the screens look more beautiful, well designed and easy to use ...
Don't change the logic anywhere"): 20 Bank names, 21 Curves, 27 Macros, 29 Mixes, 31 Rates, 53 Switches, 54 Switch N.
Places, sizes, fonts, colours and static words only; every name, id, event and key is the page's own (hmi/logic_guard.py).

- Mixes: the columns re-gridded inside the island's own card (29 .. 771) so the names the Teensy writes fit ("Ru..." for
  Rudder, "Flight mo..." for a bank); those names white like all live data, the range hints grey.
- Rates: on a card as wide as Mixes', names 155 px wide (were 70: "Aile...", "Not..." on every row; "Smoke pump" is 149),
  numbers 64; "Refresh" is "Save" (it reads every box and SAVES the model - DualRates.h ReadDualRatesFromScreen), just left of
  OK; the line under it leads with the action.
- Curves: the last page in the Version 1 look. Navy panels round the Teensy's graph box (never over it: a card under the
  drawing is repainted whole when the Teensy hides the expo controls, and wiped the curve), solid words, the scale numbers
  over their points, the bottom row lined up under the graph and the right-hand column, minus left of plus.
- Macros: ranges in the grey hint column ("0 - 16 (0 = off)", "tenths of a second"), the channel's name white in its font.
- Switches: short headings, an even rhythm, the guidance left-aligned under them. Switch N: one font, three columns 35 px from
  both edges, rows in line, the number one space after "Switch". Bank names: the lists in line with the buttons under them.
- Everywhere: the model's name top left in the strip (yellow, font 2), page default texts empty where the Teensy writes
  them (a screen-only restart shows the defaults), help titles "<page title> help", purple V1 button text black.
- Touch (hmi/touch_audit.py, 11 Oct 2026): no card covers more of a page's own touch (its "keep awake" tap) than before, and a
  new panel where that touch used to land carries it (print "UKRULES")."""
from polish import comp, put, add_text, ev_title
from fontw import width

NAVY, STRIP, WHITE, SOFT, YELLOW, GREY, BLACK = 4426, 2214, 65535, 50712, 65504, 33808, 0

def model_name(pg, title='t0'):
    """The model's name top left in the strip, alone there: font 2, yellow, y 16 h 26, stopping 20 px before the title."""
    t = comp(pg, title)
    left = t['x'] + (t['w'] - width(t['font'], t['txt'])) // 2
    put(pg, 'ModelName', x=10, y=16, w=min(270, left - 20 - 10), h=26, font=2, sta=1, txt='',
        c={'bco': STRIP, 'pco': YELLOW}, a={'xcen': 0, 'ycen': 1})

# ------------------------------------------------------------------------------------------------------------ 29 Mixes
def mixes(pg):
    """The card keeps the island's own place (29 .. 771): a wider card took 5 px a side of the page's own touch, which keeps the
    screen awake (print "UKRULES"). Inside it, 16 px from both edges (45 .. 755): labels 134 ("One direction" 130 px), switches,
    labels 156 ("Master channel" 149, 9 px before its number), numbers 64, - and + 6 px apart, the right-hand column 134
    ("Flight mode 1" 132; the Teensy's channel names, "Smoke pump" 128)."""
    for n in ('t12', 't6', 't8', 't4'): put(pg, n, x=45, w=134)                    # Mix input / Mix output / One direction / Reversed
    for n in ('c0', 'Enabled', 'od', 'Reversed'): put(pg, n, x=187)                # their switches (84: 187 .. 271)
    for n in ('t7', 't3', 't1', 't2', 't9', 't5'): put(pg, n, x=279, w=156)        # Mix number ... Percent
    for n in ('MixNumber', 'FlightMode', 'MasterChannel', 'SlaveChannel', 'Offset', 'Percent'): put(pg, n, x=439)
    for n in ('b1', 'b3', 'b5', 'b7', 'b18', 'b9'): put(pg, n, x=509)              # -
    for n in ('b0', 'b2', 'b4', 'b6', 'b19', 'b8'): put(pg, n, x=565)              # + (6 px after -, as on Macros and Curves)
    for n in ('t11', 't10', 'chM', 'chS', 't13', 't14'): put(pg, n, x=621, w=134)  # the right column, to the card's edge - 16
    for n in ('chM', 'chS', 't10'):                                                # the Teensy's live names: white, empty until written
        put(pg, n, txt='', c={'pco': WHITE})
    card = put(pg, 'card', x=29, w=742)                                            # (y 79 h 380: the island's)
    put(pg, 'b10', x=card['x'] + card['w'] - 16 - 160)                             # OK: its right edge on the column's
    put(pg, 'b22', x=45)                                                           # (hidden helper the page clicks)
    model_name(pg)

# ------------------------------------------------------------------------------------------------------------ 31 Rates
def rates(pg):
    """The card as wide as the Mixes page's (29 .. 771, inside 45 .. 755), so the channels' names get 155 px ("Smoke pump" 149,
    "Bomb doors" 137, "Flaps down" 129 in font 6; the Teensy writes the whole name, ChannelNames[16][11]) while every number
    keeps its 64 x 40 and each rate its 90 x 40. Left: labels 126 ("Rate 1 (%)" 121), the rates, the rate-choice list under them
    (222). Right, from 285: two columns of name 155 + number 64, 24 apart; the head and the two lines under them span both."""
    card = put(pg, 'card', x=29, w=742)                                            # (y 74 h 390: the island's)
    x0, x1 = card['x'] + 16, card['x'] + card['w'] - 16                             # 45 .. 755
    for n, words in (('t9', 'Rate 1 (%)'), ('t10', 'Rate 2 (%)'), ('t2', 'Rate 3 (%)')): put(pg, n, x=x0, w=126, txt=words)
    for n in ('rate1', 'rate2', 'rate3'): put(pg, n, x=x0 + 132, w=90)
    for n in ('rate1', 'rate2', 'rate3'):                                          # the keypad says the unit too
        k = n[-1]; ev_title(pg, n, 'p', f'Rate {k}', f'Rate {k} (%)')
    put(pg, 'rate', x=x0, w=222)
    xr = x0 + 222 + 18                                                             # 285: the channels' block
    put(pg, 'chhead', x=xr, w=x1 - xr, c={'pco': WHITE})                           # (a table head: white words on the card)
    for col, (names, nums) in enumerate(((('t12', 't8', 't11', 't13'), ('n2', 'n0', 'n1', 'n3')),      # the two columns of
                                         (('t16', 't14', 't15', 't17'), ('n6', 'n4', 'n5', 'n7')))):   # channel name + number
        for n in names: put(pg, n, x=xr + 247 * col, w=155, txt='')
        for n in nums: put(pg, n, x=xr + 159 + 247 * col, w=64)                    # 0 to 16
    ev_title(pg, 'n3', 'p', 'Forth channel', 'Fourth channel')
    ev_title(pg, 'n7', 'p', '8th channel', 'Eighth channel')
    put(pg, 't3', x=xr, w=x1 - xr, txt='')                                         # "'Flight mode 1' will use rate switch" 331 px
    put(pg, 't7', x=xr, w=x1 - xr, txt='Move the bank switch to edit another bank', c={'pco': SOFT}, a={'txt_maxl': 60})
    put(pg, 'b10', x=x1 - 160)                                                     # OK: bottom right of the island
    put(pg, 'b0', x=x1 - 160 - 12 - 160, txt='Save')                               # (16<<8: reads every box and saves the model)
    put(pg, 'b22', x=x0, y=399)                                                    # (hidden helper the list clicks)
    put(pg, 't1', w=200, txt='')                                                   # the bank's name over the model's (two lines in the
    put(pg, 'ModelName', w=200, txt='')                                            # strip): 200 wide as before - wider, they would
                                                                                   # cover more of the title, which keeps the screen awake
    ev_title(pg, 'b17', 'r', 'Dual Rates help', 'Rates help')

# ------------------------------------------------------------------------------------------------------------ 21 Curves
# The Teensy draws its graph in 35..395 x 35..395 (BOXLEFT/BOXTOP 35, BOXWIDTH/BOXHEIGHT 395) and acts on a touch only there
# (MovePoint). Five panels surround that square without touching it, drawn first; nothing else is over the square either.
# The right-hand column has a panel of its own from the top (424 ..), so nothing straddles two panels and hiding the expo
# controls repaints only that column - never the end point's ring, which reaches 10 px outside the square.
# That column's panel is cut in two (cardRtop 0 .. 55 over cardR 56 ..): when the two-second banner along the top ends, the
# screen repaints every component that starts above y 34 (main.cpp netPoll), and one panel from y 0 to 480 was repainted
# whole, over the bank, the model's name, the switches, Zero expo and OK. The cut is under the channel's name and Help (both
# repainted then too, after cardRtop), so neither straddles two panels. (cardRtop is made after cardR: a fresh run gives both
# the same ids.)
# Every panel carries the page's "carry on" touch (print "UKRULES"): there the page's own touch only ever reached the Teensy
# as a tap outside the graph (ClickX/ClickY, which MovePoint ignores) - what is left of it is that a tap keeps the screen
# awake, and UKRULES does just that. (A new component may carry no other script: hmi/logic_guard.py.)
PANELS = (('cardT', 0, 0, 424, 35), ('cardL', 0, 35, 35, 361), ('cardB', 0, 396, 424, 84), ('cardG', 396, 35, 28, 361),
          ('cardR', 424, 56, 376, 424))
X = 424                                                                            # the right-hand column: 424 .. 786
CARRY_ON = {'r': 'print "UKRULES"'}

def solid(pg, name, **kw):
    """Solid words on the panel (the Version 1 page had them see-through, framed, over the pilot's picture)."""
    put(pg, name, sta=1, c={'bco': NAVY, 'pco': WHITE}, a={'borderw': 0})
    return put(pg, name, **kw)

def label(pg, name, x, y, h, words):
    """A fixed label as wide as its words (+ 8): the panel behind, the same colour, takes the rest of the row's taps, and those
    keep the screen awake (a label has no touch of its own)."""
    return solid(pg, name, x=x, y=y, w=width(6, words) + 2 + 8, h=h, txt=words)

def curves(pg):
    after = None
    for name, x, y, w, h in PANELS:
        where = dict(first=True) if after is None else dict(after=after)
        add_text(pg, name, x=x, y=y, w=w, h=h, font=6, txt='', c={'bco': NAVY, 'pco': WHITE}, ev=dict(CARRY_ON), **where)
        after = name
    add_text(pg, 'cardRtop', x=X, y=0, w=800 - X, h=56, font=6, txt='', c={'bco': NAVY, 'pco': WHITE}, ev=dict(CARRY_ON),
             after='cardG')
    for k, n in enumerate(('n1', 'n2', 'n3', 'n4', 'n5')):                         # each point's height over its point
        solid(pg, n, x=35 + 90 * k - 26, y=2, w=52, h=26, a={'xcen': 1})          # (points at x 35, 125, 215, 305, 395)
    solid(pg, 'Channel', x=X, y=4, w=190, h=50, font=0, txt='')                    # (the page's title, as it were)
    solid(pg, 'fmode', x=X, y=56, w=253, h=30, txt='')                             # (the bank's name, "Flight mode 1" 153 px: as wide as
                                                                                   #  it was, the panel takes the taps beyond it)
    solid(pg, 'ModelName', x=X, y=86, w=362, h=28, font=2, txt='', c={'pco': YELLOW})
    for lab, num, y, words in (('t1', 'Input', 118, 'Stick input'), ('t2', 'Output', 150, 'Servo output')):
        label(pg, lab, X, y, 30, words)                                            # ('Servo output' 144 px)
        solid(pg, num, x=580, y=y, w=80, h=30, a={'xcen': 2})
    for k, (sw, lab, words) in enumerate((('Lines', 't4', 'Straight'), ('Smooth', 't5', 'Smooth'), ('Exp', 't6', 'Exponential'),
                                         ('callfm', 't0', 'Copy to all banks'))):   # (t0 is copied to every bank on OK: WriteNewCurve)
        y = 186 + 38 * k
        put(pg, sw, x=X, y=y, w=84, h=34, c={'bco': GREY})                         # (the switches' grey on every page)
        label(pg, lab, X + 96, y, 34, words)
    # the expo row: its number under the two above (right edges at 660), - and + after it; the slider under the row
    label(pg, 't3', X, 338, 34, 'Expo')
    solid(pg, 'Expo', x=580, y=338, w=80, h=34, a={'xcen': 2})
    put(pg, 'b13', x=670, y=338, w=54, h=34)                                       # -
    put(pg, 'b12', x=732, y=338, w=54, h=34)                                       # +
    put(pg, 'Ex1', x=X, y=376, w=362, h=30, c={'pco': WHITE, 'bco': GREY, 'bco1': YELLOW})   # (as on Sounds)
    # the bottom row: Next point, - and + under the graph (35 .. 395); Zero expo and OK under the right-hand column
    put(pg, 'b1', x=35, y=414, w=140, h=56, txt='Next point')
    put(pg, 'b9', x=181, y=414, w=104, h=56)                                       # - (left of +, as on every stepper)
    put(pg, 'b5', x=291, y=414, w=104, h=56)                                       # +
    put(pg, 'reset', x=X, y=414, w=170, h=56, txt='Zero expo')
    put(pg, 'b0', x=605, y=414, w=180, h=56)                                       # OK (the full-card OK slot)
    put(pg, 'b15', x=620, y=4, w=170, h=50)                                        # Help (the house place)
    for n in ('b0', 'b1', 'b5', 'b9', 'reset', 'b12', 'b13', 'b15'): put(pg, n, c={'pco': BLACK})

# ------------------------------------------------------------------------------------------------------------ 27 Macros
MAC_LABELS = ('t7', 't3', 't1', 't5', 't2', 't4')                                 # Macro number ... Duration
MAC_VALUES = ('Mno', 'Tch', 'Mch', 'Pos', 'Del', 'Dur')
MAC_MINUS = ('b1', 'b3', 'b5', 'b8', 'b7', 'b14')
MAC_PLUS = ('b0', 'b2', 'b4', 'b9', 'b6', 'b13')
MAC_HINTS = ('rng_Mno', 'rng_Tch', 'chM', 'rng_Pos', 'rng_Del', 'rng_Dur')

def macros(pg):
    """The range moves out of "Channel to move (1 - 16)" into the hint column, so the label column closes up to its widest
    words (191 px) and the island narrows round what is left - the islands' own rule, done here because the words change
    here. Columns: labels 205, value 70, - 56, + 56, hints 182 ("tenths of a second" 177 px); gaps 12 / 8 / 6 / 8."""
    put(pg, 't1', txt='Channel to move')
    put(pg, 'rng_Tch', txt='0 - 16 (0 = off)', a={'txt_maxl': 20})               # (the one fact a pilot needs, as "Bank (0 = all)")
    put(pg, 'rng_Del', txt='tenths of a second')
    put(pg, 'rng_Dur', txt='tenths of a second')
    put(pg, 'chM', txt='', font=2, c={'pco': WHITE})                               # the channel's name: live data, white, in the
                                                                                   # hints' font as on Mixes ('Smoke pump' 128 px)
    inner = 205 + 12 + 70 + 8 + 56 + 6 + 56 + 8 + 182
    card = put(pg, 'card', x=(800 - (inner + 32)) // 2, w=inner + 32)               # (y and h: the island's)
    x0 = card['x'] + 16
    for names, x, w in ((MAC_LABELS, x0, 205), (MAC_VALUES, x0 + 217, 70), (MAC_MINUS, x0 + 295, 56), (MAC_PLUS, x0 + 357, 56),
                        (MAC_HINTS, x0 + 421, 182)):
        for n in names: put(pg, n, x=x, w=w)
    put(pg, 'b10', x=x0 + inner - 160)                                             # OK: bottom right of the island
    model_name(pg)

# ------------------------------------------------------------------------------------------------------------ 53 Switches
def switches(pg):
    put(pg, 'h0', txt='Top edge (seen from above, sticks towards you)')
    put(pg, 'h1', txt='Front (channels 5 to 8; a knob reads as a switch)', y=218)
    for n in ('t5', 'sw5', 'p5', 't7', 'sw7', 'p7'): put(pg, n, y=246)
    for n in ('t6', 'sw6', 'p6', 't8', 'sw8', 'p8'): put(pg, n, y=298)
    put(pg, 't', y=352, a={'xcen': 0})                                             # (both lines start under the headings, at 37)
    model_name(pg)

# ------------------------------------------------------------------------------------------------------------ 54 Switch N
JOBS = ('0', '1', '2', '7', '8', '9')                                              # Not used, Banks 1 2 3, Bank 4 & Motor, Safety, Rates, Buddy
CH_A = ('10', '11', '12', '13', '3', '4')                                          # channels 5 6 7 8 9 10
CH_B = ('5', '6', '14', '15', '16', '17')                                          # channels 11 12 13 14 15 16
ROWS = (76, 122, 168, 214, 260, 306)
# The title is "Switch" (centred, font 0) and the switch's number (Sw, 1 - 8) after it: Sw's digit starts where it would in
# the one text "Switch 3" - the pen after "Switch" plus one space - less the number's own 2 px margin, and 2 px more so the
# box starts 8 px after the words (hmi/lint_pages.py): 454, the digit 2 px further off than in "Switch 3" (it was 6).
SW_X = (800 - width(0, 'Switch')) // 2 + width(0, 'Switch ')                     # 454

def one_switch(pg):
    for ks, rx, tx, tw in ((JOBS, 35, 85, 200), (CH_A, 305, 355, 170), (CH_B, 545, 595, 170)):   # ('Bank 4 & Motor' 175 px,
                                                                                   #  'Smoke pump' 149, 'Channel 16' 129)
        for k, y in zip(ks, ROWS):                                                 # (the three columns' rows in line)
            put(pg, 'r' + k, x=rx, y=y)
            put(pg, 't' + k, x=tx, y=y, w=tw, font=6)
    put(pg, 'c_revd', x=35)
    put(pg, 't99', x=135, font=6)
    put(pg, 'Sw', x=SW_X)                                                          # the number one space after "Switch"
    put(pg, 'Progress', y=403)                                                     # (the busy bar: 7 px under Reversed, 6 over OK)
    model_name(pg, 'title')
    ev_title(pg, 'b15', 'r', 'One switch help', 'Switch help')

# ------------------------------------------------------------------------------------------------------------ 20 Bank names
def bank_names(pg):
    """The four lists line up with the six buttons under them (110 wide, 12 apart from 40): each list spans two buttons
    (Vbar + Heli 162 .. 394, Listen + OK 528 .. 760), its label the button before them (Default 40 .. 150, Glider 406 .. 516)."""
    for n, x in (('t1', 40), ('t2', 40), ('t3', 406), ('t4', 406)): put(pg, n, x=x, w=110)
    for n, x in (('BK1', 162), ('BK2', 162), ('BK3', 528), ('BK4', 528)):
        put(pg, n, x=x, w=232, c={'pco2': BLACK})                                  # the chosen row black, as on every list
    put(pg, 'b1', txt='VBar')                                                      # (Mikado's spelling: the preset is VBar's banks)
    model_name(pg)

EDITS = {20: bank_names, 21: curves, 27: macros, 29: mixes, 31: rates, 53: switches, 54: one_switch}
