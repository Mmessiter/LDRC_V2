"""POLISH, group "front" (10 Oct 2026): the front page and the pages it leads to for watching the link.
13 FrontView, 26 SticksView (Channels), 38 GapsView (Reconnection times), 2 FhssView (Interference scan), 41 PopupView
(the yes/no question and message box), 30 DataView (Telemetry), 52 GPSView. (0 BlankView and 43 SplashView: left as they are.)

Only places, sizes, fonts, colours, static words, draw order, help-viewer titles and new plain texts (cards, strips) - nothing a
page DOES changes (hmi/logic_guard.py). Every value is absolute, so running this twice gives the same page.
Solid text everywhere (Malcolm's rule): the theme's strip 2214 along the top, its panel 4426 behind the words, white writing;
yellow for the model's name. New cards carry the page's own touch script (print "UKRULES") only where the page has one."""
from polish import add_text, comp, ev_title, put, rect

STRIP, PANEL, WHITE, BLACK, YELLOW, BTN, SLATE = 2214, 4426, 65535, 0, 65504, 54938, 25490
CARRY_ON = {'r': 'print "UKRULES"'}


# ------------------------------------------------------------------ 13 FrontView
# One grid: a 30 px margin each side, the left column (bank, rate, chips) 30..220, the right column (bars, Motor box, Help)
# 580..770, the model's picture centred 240..560; the strip 0..64 (two lines: bank and rate), the content 72..304, the
# dashboard 312..392 (batteries, timer, link), the three buttons 400..450, the bottom trims at 460 as they were.
L, R = 30, 770                       # the content's left and right edges
COL_W = 190                          # the left and right columns
RX0 = R - COL_W                      # 580: the right column
TOP, FOOT = 72, 304                  # the content between the strip and the dashboard
DASH_Y, DASH_H = 312, 80


def front_page(pg):
    # The strip and the dashboard: plain navy texts drawn first (everything live sits on them), carrying the page's own touch.
    add_text(pg, 'strip', first=True, x=0, y=0, w=800, h=64, c={'bco': STRIP}, ev=dict(CARRY_ON))
    add_text(pg, 'dash', after='strip', x=L, y=DASH_Y, w=R - L, h=DASH_H, c={'bco': PANEL}, ev=dict(CARRY_ON))
    # The 16 channel bars on a card of their own: no slivers of the picture between them.
    add_text(pg, 'barcard', after='dash', x=RX0, y=TOP, w=COL_W, h=190, c={'bco': PANEL}, ev=dict(CARRY_ON))

    # The strip: bank over rate at the left, the title over the date in the middle, Help at the right.
    # Bank and rate in font 6: in font 0 "Flight mode 1" (189 px) ended 8 px before the title and read as one line with it;
    # in font 6 it is 153 px (the widest BankNames entry), 26 px clear. The defined front screen shows the bank in font 6 too.
    put(pg, 't4', x=L, y=0, w=COL_W, h=32, font=6, sta=1, c={'bco': STRIP}, txt='')
    put(pg, 'rate', x=L, y=32, w=COL_W, h=32, font=6, sta=1, c={'bco': STRIP}, txt='')   # (the Teensy writes "Rate n" or hides it)
    put(pg, 'Title', x=225, y=2, w=380, h=34, sta=1, c={'bco': STRIP})                 # ("LockDownRadioControl V2": 375 px font 0)
    put(pg, 'DateTime', x=225, y=36, w=380, h=26, sta=1, c={'bco': STRIP}, txt='')    # ("28 September 2026 23:59:59": 281 px)
    put(pg, 'b17', x=610, y=7, w=160, h=50, font=6)                                     # (610 w160: clear of the right trim)
    ev_title(pg, 'b17', 'r', 'LDRC help', 'Front screen help')

    # The left column: seven chips, solid, 34 px apart (Owner in font 2: "Malcolm Messiter" is 170 px, cut in font 6).
    for k, n in enumerate(('Owner', 'ams', 'trall', 'rpm', 'StillConnected', 'wb', 'Warning')):
        put(pg, n, x=L, y=TOP + 34 * k, w=COL_W, h=28, sta=1, c={'bco': PANEL})
    put(pg, 'Owner', font=2)
    # Default words: empty where the Teensy writes something else ("TURN OFF?! n" / "Amps: x", "RPM: n"); the boxes are hidden
    # at preinitialize or written at once, and the flight screen's readers treat '' exactly as they treated the old words.
    for n in ('Owner', 'StillConnected', 'rpm'):
        put(pg, n, txt='')

    # The model's picture and its name below it (the model's name is yellow, as on every page).
    rect(pg, 'exp0', 240, TOP, 320, 200)
    put(pg, 'ModelName', x=240, y=TOP + 202, w=320, h=FOOT - TOP - 202, sta=1, c={'bco': PANEL, 'pco': YELLOW}, txt='')

    # The right column: four groups of four bars on their card (8 high, 2 apart, the groups 12-13 apart), then the Motor box.
    for g, gy in enumerate((TOP, TOP + 51, TOP + 102, TOP + 152)):
        for i in range(4):
            rect(pg, f'Ch{4 * g + i + 1}', RX0, gy + 10 * i, COL_W, 8)
    put(pg, 'bt0', x=RX0, y=FOOT - 36, w=COL_W, h=36, txt='Motor is OFF')             # (the Teensy's words: "Motor is ON/OFF")

    # The dashboard: TX and RX batteries at the left, the motor timer at the right, the link along the foot.
    for n, y in (('tx', DASH_Y + 6), ('rx', DASH_Y + 31)):
        put(pg, n, x=L + 8, y=y, w=46, h=25, sta=1, c={'bco': PANEL})
    # The battery's nub: just right of its bar (which ends at 148), 8 high, centred on it.
    rect(pg, 'JTX', L + 56, DASH_Y + 7, 62, 23); rect(pg, 't1', L + 118, DASH_Y + 15, 4, 8)
    rect(pg, 'JRX', L + 56, DASH_Y + 32, 62, 23); rect(pg, 't0', L + 118, DASH_Y + 40, 4, 8)
    for n, y in (('TXBV', DASH_Y + 6), ('RXBV', DASH_Y + 31)):
        put(pg, n, x=L + 132, y=y, w=330, h=25, sta=1, c={'bco': PANEL}, txt='')       # ("50.40V (4.20V per cell)": 225 px)
    # The timer, right-aligned in the dashboard. The colons in boxes as wide as a font-1 colon (19 px): a narrower box cut
    # them to "." (the screen ends a too-wide text in dots), and the timer read 00.04.07.
    x = R - 8
    for n, w in (('Secs', 66), ('t2', 21), ('Mins', 66), ('t3', 21), ('Hours', 66)):
        x -= w
        put(pg, n, x=x, y=DASH_Y + 4, w=w, h=56, sta=1, c={'bco': PANEL})
    put(pg, 'Connected', x=L + 8, y=DASH_Y + 56, w=262, h=22, sta=1, c={'bco': PANEL})  # ("Sending Parameters ...": 224 px)
    rect(pg, 'Quality', L + 276, DASH_Y + 61, R - 8 - (L + 276), 13)

    # The buttons: the dashboard's width, three equal.
    for n, bx in (('b0', L), ('ldrcDefined', 282), ('b1', 534)):
        rect(pg, n, bx, 400, 236, 50)

    # The side trims start below the strip (they cut notches into it) and end with the buttons. All four trims 8 px in from
    # the edges, mirror images: the bottom pair 385 wide each (as wide as the right one was; neither gets narrower) with a
    # 14 px gap centred on 400.
    rect(pg, 'ch4', 8, TOP, 15, 378)
    rect(pg, 'ch2', 777, TOP, 15, 378)
    rect(pg, 'ch3', 8, 460, 385, 15)
    rect(pg, 'ch1', 407, 460, 385, 15)


# ------------------------------------------------------------------ 26 SticksView (Channels)
# Dense page: the full card. Each channel button centred on its own bar (odd at the left, even at the right), all 40 high;
# the columns 10 px from the edges, 202 wide, so a ten-letter name keeps its number and arrow ("Smoke pump (13) >" is
# 193 px in font 2; 194 px of room). OK under the right column, its right edge on Help's.
# The bank and the model's name top-left in the strip, as on Trims, Rates and Servo speed (the bank was a raised grey box,
# Malcolm 10-03 "button-coloured, even though it isn't really a button"; beside Help it looked like a second button). Both
# keep their own touch (print "UKRULES", the same as the strip under them), and stop at 246, before the title's box at 250.
def channels(pg):
    add_text(pg, 'strip', first=True, x=0, y=0, w=800, h=58, c={'bco': STRIP}, ev=dict(CARRY_ON))
    add_text(pg, 'card', after='strip', x=0, y=58, w=800, h=422, c={'bco': PANEL}, ev=dict(CARRY_ON))
    put(pg, 't0', x=250, y=0, w=300, h=58, sta=1, c={'bco': STRIP})
    put(pg, 't1', x=10, y=4, w=236, h=25, font=2, sta=1, c={'bco': STRIP, 'pco': WHITE},
        a={'style': 0, 'borderw': 0, 'xcen': 0})                                      # ("Flight mode 1": 132 px font 2)
    put(pg, 'ModelName', x=10, y=30, w=236, h=25, font=2, sta=1, c={'bco': STRIP, 'pco': YELLOW},
        a={'style': 0, 'borderw': 0, 'xcen': 0}, txt='')                              # ("RAW 420 MCM (3)": 186 px font 2)
    rect(pg, 'b17', 620, 4, 170, 50)
    for k in range(16):
        rect(pg, f'Ch{k + 1}', 218, 74 + 21 * k, 364, 20)                              # (the centre line stays at 400)
    for k in range(8):
        rect(pg, f'Sch{2 * k + 1}', 10, 64 + 42 * k, 202, 40)
        rect(pg, f'Sch{2 * k + 2}', 588, 85 + 42 * k, 202, 40)
    rect(pg, 'b10', 588, 424, 202, 50)


# ------------------------------------------------------------------ 38 GapsView (Reconnection times)
# Full card. Eleven columns: the share on top, the bar, the count below it, the length under that. A bar fills green up to
# 100 ms, amber to 250, red beyond (what the help says: over 100 worth a look, over 250 act); empty columns stay quiet slate.
GREEN, AMBER, RED = 1056, 64512, 53248
BARS = ('j0', 'j10', 'j11', 'j6', 'j5', 'j4', 'j3', 'j9', 'j2', 'j8', 'j7')           # left to right, as the Teensy fills them
SHARES = ('t13', 't15', 't17', 't18', 't19', 't20', 't21', 't22', 't23', 't24', 't25')
LENGTHS = ('< 4', '< 8', '< 10', '< 12', '< 15', '< 25', '< 50', '< 100', '< 250', '< 500', '> 500')   # (the Teensy's own words)


def gaps(pg):
    put(pg, 't0', x=0, y=0, w=800, h=58, sta=1, c={'bco': STRIP}, txt='Reconnection times (ms)')
    add_text(pg, 'card', after='t0', x=0, y=58, w=800, h=422, c={'bco': PANEL})        # (the page has no touch of its own)
    for k in range(11):
        x, fill = 15 + 71 * k, GREEN if k < 8 else AMBER if k == 8 else RED
        put(pg, SHARES[k], x=x, y=66, w=65, h=28, c={'bco': PANEL, 'pco': WHITE})
        put(pg, BARS[k], x=x, y=98, w=65, h=228, c={'bco': SLATE, 'pco': fill})
        # The count: white on the card. (Coloured boxes made an empty column's leftover '0' amber or red on a second visit,
        # when the Teensy does not hide it again; the colour stays in the bars.)
        put(pg, f'n{k}', x=x, y=330, w=65, h=26, c={'bco': PANEL, 'pco': WHITE})       # ("12345": 60 px)
        put(pg, f't{k + 1}', x=x, y=360, w=65, h=30, c={'bco': PANEL, 'pco': WHITE}, txt=LENGTHS[k])
    # The bottom row on the page's slots: Shortest / Average / Longest, each a label and its figure, then OK.
    for k, (lab, val, txt) in enumerate((('t12', 'n11', 'Shortest'), ('t14', 'n12', 'Average'), ('t16', 'n13', 'Longest'))):
        x = 14 + 197 * k
        put(pg, lab, x=x, y=426, w=96, h=32, c={'bco': PANEL, 'pco': WHITE}, txt=txt, a={'xcen': 0})
        put(pg, val, x=x + 98, y=426, w=82, h=32, a={'style': 2, 'borderw': 2})
    put(pg, 'b0', x=605, y=414, w=180, h=56, font=6, c={'bco': BTN, 'bco2': 1024})
    put(pg, 'b15', x=620, y=4, w=170, h=50, font=6, c={'bco': BTN, 'bco2': 1024})


# ------------------------------------------------------------------ 2 FhssView (Interference scan)
# The Teensy draws its graph on the black page inside 65..795 x 69..365; the page keeps clear of it. Below: the average in one
# band the width of the slots, Restart and OK on the slots, and between them two rows that read as words.
def scan(pg):
    put(pg, 't0', x=0, y=0, w=800, h=58, sta=1, c={'bco': STRIP})
    put(pg, 'b0', x=14, y=414, w=180, h=56, font=6, c={'bco2': 1024})                  # (pressed: white words on green, as
    put(pg, 'b10', x=605, y=414, w=180, h=56, font=6, c={'bco2': 1024})                #  everywhere; it was white on white)
    # The band split so that a two-digit count sits in the middle ("Average hits per second: 85" spans 205..592).
    put(pg, 't3', x=14, y=372, w=546, h=36, txt='Average hits per second: ', a={'xcen': 2})   # (the trailing space: a gap)
    put(pg, 'Count3', x=560, y=372, w=226, h=36)                                        # ("1234567" still fits: ends at 672)
    for row, (strip, lab, txt, ch, n, hits, colour) in enumerate(
            (('qrow', 't1', 'Quietest channel', 'Quietest', 'Count', 't4', 36848),
             ('nrow', 't2', 'Noisiest channel', 'Noisyest', 'Count1', 't5', 64365))):
        y = 414 + 29 * row
        # The row's colour as one strip behind its words, so they can sit 8 px in. A new text where the page's own touch
        # used to land, so it carries the page's touch (print "UKRULES": a tap keeps the screen awake).
        add_text(pg, strip, after='va1' if row == 0 else 'qrow', x=204, y=y, w=391, h=27,      # (drawn before the row's parts)
                 c={'bco': colour, 'pco': BLACK}, ev=dict(CARRY_ON))
        put(pg, lab, x=212, y=y, w=172, h=27, txt=txt, a={'xcen': 0})                 # (163 px font 2)
        put(pg, ch, x=390, y=y, w=52, h=27, a={'xcen': 1})                              # (channel 0-82)
        # The count and 'hits' end 6 px from the row's right end, as 'Quietest channel' starts 8 px from its left one.
        put(pg, n, x=446, y=y, w=100, h=27, a={'xcen': 2})                              # (a uint32 total: "9999999" 84 px)
        put(pg, hits, x=551, y=y, w=44, h=27, txt='hits', a={'xcen': 0})               # (34 px)


# ------------------------------------------------------------------ 41 PopupView (the question / the message box)
# A frame of its own gives the words a margin (a long one-line question ran edge to edge); the lines stay left-aligned in a
# centred block (easier to read than each line centred).
# The page has no background of its own, so the page underneath showed round the dialog, cut through: half an OK under the
# dialog's OK, slivers of grid buttons, 'Tim', 'ock'. A plain backdrop in the strip's colour hides it. The whole glass, not
# from y 58: Models (its lists and Help start at 42) and Rates/PID + (bank row) were still sliced at 58, and the page's own
# Help left showing in its strip does nothing while the question is up. No touch: the page has none, so a tap there did
# nothing before either.
# The question box keeps the screen's usual rule (no "fresh"): which words it starts with at a load is state, not drawing.
def popup(pg):
    add_text(pg, 'shade', first=True, x=0, y=0, w=800, h=480, font=6,
             c={'bco': STRIP, 'pco': WHITE, 'borderc': 0}, a={'xcen': 0})
    # The dialog in the middle of the glass now that nothing else shows (it sat 20 px high, under where a strip ended).
    rect(pg, 'Dialog_ring', 87, 87, 626, 306)
    add_text(pg, 'Dialog_frame', after='Dialog_ring', x=90, y=90, w=620, h=300, font=6,
             c={'bco': PANEL, 'pco': WHITE, 'borderc': WHITE}, a={'style': 1, 'borderw': 2, 'xcen': 0, 'txt_maxl': 1})
    put(pg, 'Dialog', x=112, y=100, w=576, h=218, txt='', a={'style': 0, 'borderw': 0})
    rect(pg, 'b1', 106, 326, 180, 50)                                                   # (Cancel; hidden for a message)
    rect(pg, 'b0', 514, 326, 180, 50)                                                   # (OK, rightmost)
    comp(pg, 'Dialog').pop('fresh', None)


# ------------------------------------------------------------------ 30 DataView (Telemetry)
def telemetry(pg):
    put(pg, 'rxv', txt='-')                                       # (written only while linked: no made-up version before)
    put(pg, 't6', txt='-')                                        # (RX volts: written only while a receiver reports them)
    # The Teensy writes words into these ("2214 RPM", "52.4 C", "TRX:3 V2", its version, "0:11:42"): no made-up '0' before.
    for n in ('alt', 'MaxAlt', 'Temp', 'Sbus', 'txv', 'rx', 't17', 'Sg', 'Gc', 'n1'):
        put(pg, n, txt='')
    for n in ('b0', 'b1', 'b2', 'b10', 'b13', 'b15'):            # (pressed: white words on green; they were white on pale grey)
        put(pg, n, c={'bco2': 1024})
    put(pg, 't4', txt='Max head speed')                           # (160 px font 2; "head speed" as on the front screens)
    ev_title(pg, 'b15', 'r', 'Data help', 'Telemetry help')


# ------------------------------------------------------------------ 52 GPSView
# Six rows a side: where the model is at the left (latitude before longitude), the way back to the mark and the maxima at
# the right. The distance to the mark keeps its larger font. The button names the page it opens.
def gps(pg):
    left = (('t20', 'Fix'), ('t18', 'Sat'), ('t22', 'Lat'), ('t5', 'Lon'), ('t17', 'Bear'), ('t27', 'Sped'))
    right = (('t26', 'Dist'), ('t6', 'BTo'), ('t19', 'Mxd'), ('t23', 'ALT'), ('t24', 'MALT'), ('t12', 'MxS'))
    for k, (lab, val) in enumerate(left):                         # (the rows in the middle between the strip and the buttons)
        y = 86 + 52 * k
        rect(pg, lab, 26, y, 176, 38); rect(pg, val, 206, y, 182, 38)
    for k, (lab, val) in enumerate(right):
        y = 86 + 52 * k
        rect(pg, lab, 402, y, 210, 38); rect(pg, val, 616, y, 156, 38)
    put(pg, 't26', txt='Yards to mark')                           # (the receiver sends yards: GPS.h MetresToYards; 159 px font 6)
    # Without a fix the Teensy writes only the fix and the satellites ("leave display as before"): the rest says '-' (no
    # reading yet, as Telemetry's receiver boxes do) rather than a 0 that looks real. The fix is 'Yes' or 'No', never '0'.
    put(pg, 'Fix', txt=''); put(pg, 'Sat', txt='')
    for n in ('Lat', 'Lon', 'Bear', 'Sped', 'Dist', 'BTo', 'Mxd', 'ALT', 'MALT', 'MxS'):
        put(pg, n, txt='-')
    b0 = put(pg, 'b0', txt='Telemetry ...', c={'bco2': 1024})     # (pressed: green like its row; it was 214)
    b0['a']['txt_maxl'] = max(b0['a'].get('txt_maxl', 0), 16)


EDITS = {13: front_page, 26: channels, 38: gaps, 2: scan, 41: popup, 30: telemetry, 52: gps}
