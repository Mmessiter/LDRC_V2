"""POLISH, the models group (10 Oct 2026): the Models page and the pages it opens - Model IDs, the duplicates list, the log and
help files, the help viewer, both keyboards, the backup, file-exchange and rename dialogs, and the picture page.
Malcolm: "make the screens look more beautiful, well designed and easy to use ... Don't change the logic anywhere".

Only places, sizes, fonts, colours, frames, draw order, static words and new plain texts change (hmi/logic_guard.py). Inside
events only a help title (LogView.t0.txt=) or a keyboard question (keybdA.t1.txt=) changes its words. Every value here is
ABSOLUTE, so this runs any number of times with the same result.

What the Teensy writes into these pages (and the new words the Teensy-text change gives some of them) was measured in the
screen's fonts (hmi/fontw.py) against the boxes below: BackupView t0 "Filename?" / "New filename?" / "File name" / "New file
name" (<= 138 px, font 2, label 210), Modelname "(i.e. just change its filename)" 375 / "Only the file name changes" (font 0,
480), t3 "Rename this backup" / "Rename backup file" / "Create backup file for"; FileExchView t0 "File receive" / "Receiving
file" 187, filename "TIMEOUT" / "Nothing received" 236 (font 0, 480); LogFiles t0 "All log files" / "Log files" / "All help
files" / "Help files" (strip, 800); LogFiles rows "01-08-26.LOG12345.67 KB" 391 px in Courier 32 (the list has 398)."""
from polish import comp, put, rect, park, add_text, move_after, ev_title

PANEL, STRIP, INK, SOFT, YELLOW, BLACK = 4426, 2214, 65535, 50712, 65504, 0
GREY = 54938                     # the pages' button face (Cancel, OK, Help)
KEY, FKEY, GO, PRESSED = 61309, 46518, 65523, 40147   # the screen's own keyboards (WiFi, command line): 0xEF7D a letter, 0xB5B6 a
#                                  function key, 0xFFF3 the pale yellow key that acts, 0x9CD3 a key held down


def key(pg, name, x, y, w, h, face=KEY, font=0, txt=None):
    """A key or button in the house look: a raised face, black words, a darker face while held."""
    kw = dict(x=x, y=y, w=w, h=h, font=font, c={'bco': face, 'pco': BLACK, 'bco2': PRESSED, 'pco2': BLACK, 'borderc': 0},
              a={'style': 4, 'borderw': 2})
    if txt is not None: kw['txt'] = txt
    return put(pg, name, **kw)


# ------------------------------------------------------------------ 15 ModelsView (models.0 - 4)
def models_page(pg):
    # A symmetric grid: 12 px of picture at both sides, the two columns level, the middle column centred (x 310..490), and
    # the whole page 7 px from the top and 6 px from the bottom of the glass (fix pass: it sat 2 px from the top, 11 from
    # the bottom). The headings are solid strips at last (sta 3 drew them see-through on the picture), in sentence case.
    put(pg, 't0', x=12, y=7, w=290, h=40, sta=1, txt='Models loaded')
    put(pg, 't1', x=498, y=7, w=290, h=40, sta=1, txt='Backup files')
    rect(pg, 'MMems', 12, 47, 290, 181)                  # 5 whole rows of 35 inside a 3 px frame (179 cut 1 px off two rows)
    rect(pg, 'Mfiles', 498, 47, 290, 181)
    for i, n in enumerate(('b15', 'b4', 'b5')):          # Help, > Backup >, < Restore <: three equal buttons, the lists' height
        rect(pg, n, 310, 47 + 62 * i, 180, 57)
    rect(pg, 'Progress', 12, 232, 776, 6)                # (shown only while a backup or restore runs)
    for i, n in enumerate(('b0', 'b12', 'b11', 'b3')):   # the model memory's buttons, left
        rect(pg, n, 12, 241 + 61 * i, 210, 50)
    for i, n in enumerate(('b9', 'b2', 'b1', 'b10')):    # the backup file's buttons, right; OK bottom right
        rect(pg, n, 578, 241 + 61 * i, 210, 50)
    put(pg, 'b3', txt='Check IDs')                       # (was "IDs check": the verb first, as the other buttons)
    rect(pg, 'exp0', 240, 241, 320, 200)                 # the picture: its top level with the first row of buttons
    # The model's name on a solid plate joined under the picture (it was yellow on the see-through picture); the plate ends
    # level with the buttons' bottoms. Themes recolour it as every panel.
    put(pg, 'modelname', x=240, y=441, w=320, h=33, sta=1, txt='', c={'bco': PANEL}, a={'borderw': 0})
    # "File error!" (135 px in font 0): a message box in the picture's middle (it was red on a yellow stripe). 188 x 50, so it
    # covers no more of the picture (whose touch opens the picture chooser) than the old 190 x 50 stripe did.
    put(pg, 'error', x=306, y=316, w=188, h=50, c={'bco': PANEL, 'pco': INK, 'borderc': INK}, a={'style': 5, 'borderw': 0, 'isbr': 1})


# ------------------------------------------------------------------ 3 IDsStartView (models.5)
def model_ids(pg):
    # A compact island (it was 348 px tall for two rows), centred under the strip; "Check for duplicates" opens another page,
    # so it joins the bottom row, two slots just left of OK; the model's name top left in the strip, as on Model setup.
    rect(pg, 'card', 30, 166, 740, 206)
    rect(pg, 't2', 46, 182, 121, 50); put(pg, 't4', x=246, y=182, w=230, h=50, txt=''); rect(pg, 'b7', 488, 182, 266, 50)
    rect(pg, 't3', 46, 242, 188, 50); put(pg, 't5', x=246, y=242, w=230, h=50, txt=''); rect(pg, 'b11', 488, 242, 266, 50)
    rect(pg, 'b3', 246, 306, 336, 50)                    # (its left edge under the ID fields', 12 px before OK)
    rect(pg, 'b4', 594, 306, 160, 50)
    # (ends 22 px before "Model IDs", 137 px of font 0 centred: a 30-letter name ends in "..." at 300 px)
    put(pg, 't1', x=10, y=16, w=300, h=26, font=2, txt='', c={'bco': STRIP}, a={'xcen': 0})
    ev_title(pg, 'b17', 'r', 'RX setup help', 'Model IDs help')


# ------------------------------------------------------------------ 46 IDsView (models.10)
def id_list(pg):
    # The list as wide as the island allows (room 670 px, was 606): "(4)  Goblin 700 Comp 7CDFA1B2C3D4>Duplicate:9<" (597 px)
    # keeps its marker. (A 30-letter name still pushes it off: the Teensy's order of words, reported, not changed.)
    rect(pg, 'card', 32, 88, 736, 361)
    rect(pg, 'MMems', 48, 104, 704, 265)                 # 7 whole rows of 37
    rect(pg, 't1', 48, 385, 170, 46); rect(pg, 'n0', 224, 385, 90, 46)
    rect(pg, 'b10', 592, 383, 160, 50)
    ev_title(pg, 'b17', 'r', 'ID Check help', 'Model IDs: duplicates help')


# ------------------------------------------------------------------ 19 LogFiles (models.6)
def log_files(pg):
    # The list wide enough for its own rows: every size showed as "9.7..." (a row needs 374-391 px of Courier 32; the list
    # now has 398). View and Delete the islands' 160 x 50, at the list's top.
    put(pg, 't0', txt='')                                # (the Teensy writes "Log files" or "Help files"; the default was "Files")
    rect(pg, 'card', 47, 95, 706, 347)
    rect(pg, 'FilesBox', 63, 111, 432, 201)              # 5 whole rows of 39
    rect(pg, 'b0', 577, 111, 160, 50); rect(pg, 'b1', 577, 171, 160, 50); rect(pg, 'b10', 577, 376, 160, 50)
    rect(pg, 't3', 63, 330, 69, 32); put(pg, 't4', x=133, y=330, w=140, h=32, txt='')
    rect(pg, 't1', 285, 330, 70, 32); put(pg, 't5', x=355, y=330, w=140, h=32, txt='')
    rect(pg, 't2', 507, 330, 66, 32); put(pg, 't6', x=577, y=330, w=140, h=32, txt='')


# ------------------------------------------------------------------ 44 LogView, the help and log viewer (models.7, adapted)
def viewer(pg):
    """The house look: the title in the page's strip, Help where every page has it, the four bottom slots, and the text on
    white paper laid on the navy card - with 774 px for each line (the widest wrapped help line is 763; 741 cut them).

    The text box is also 30 px shorter (14 whole lines, was 15 and a quarter). Proof that the Teensy follows (TXV1B
    TransmitterCode/include/LogFilesDisplay.h, B92): it never assumes the height. LogReleasedNEW, on every release of the text,
    learns it from the screen's own report: LogViewHeight = LastShownLines x 24 - maxval_y, and the screen reports maxval_y as
    lines x 24 - (h - 2 x borderw) (src/main.cpp getInt) - so it learns exactly 336. Scrolling to the next or the previous
    window compares val_y with maxval_y x 0.75 / 0.25 and moves by whole lines (24 px, font 2, unchanged): no height in it.
    Top sends val_y 0. Bottom sends lines x 24 - LogViewHeight: exact once learnt; before the first touch it uses its guess,
    10 x 24 = 240, which was already not the box (366 before, 336 now): the last line then stands 96 px above the box's foot
    instead of 126 (reported as a bug, not fixed). The screen keeps any val_y the Teensy sends (no clamp) and a finger's drag
    clamps to maxval_y - also no height assumed."""
    add_text(pg, 'card', first=True, x=0, y=58, w=800, h=422, font=2, c={'bco': PANEL, 'pco': INK, 'borderc': 0})
    put(pg, 't0', x=0, y=0, w=800, h=58, c={'bco': STRIP, 'pco': INK}, a={'borderw': 0})
    put(pg, 'b15', x=620, y=4, w=170, h=50, font=6)
    put(pg, 'LogText', x=6, y=62, w=788, h=348, a={'borderw': 6})
    for i, n in enumerate(('b0', 'b1', 'b4', 'b10')):   # Files, Top, Bottom, OK
        put(pg, n, x=14 + 197 * i, y=414, w=180, h=56, font=6)


# ------------------------------------------------------------------ 56 keybdA, the full keyboard (models.8, adapted)
def keyboard(pg):
    """The screen's own keyboards (WiFi, command line, 1.11.45) made four: the question in the strip, the field in Courier 32
    with Delete at its right end, 78 x 84 keys on the 80 px grid (2 px apart both ways, as the house keys), every word on
    a key in bold (font 0), and the pale yellow OK at the bottom right.
    The strip (fix pass): the question at the left (font 0, 490 px: the longest, "Name for channel 16", is 283), then
    "Hide" (b249, back in reach: its release toggles show.pw, which on a Nextion masks the typed text as the WiFi keys' Hide
    does - this screen does not draw pw, reported) and Cancel at the right, both clear of the two corners the screen keeps
    for a long press (x < 48 or x >= 752, y < 48: radios at 1.5 s, the workshop door at 3 s) - holding Cancel at the top
    left would have switched the radios and swallowed Cancel. refshow (the scripts' "click refshow,0"; a
    finger's tap there only puts the same key words back) is again where it always was, (4,4,33,35), invisible over the
    question's first letters: the question is drawn right after the strip so that refshow, not it, takes that tap.
    Kept for the page's scripts: CAPS and 123 keep their words (the scripts test them) and b0's face (they put it back);
    every letter key's words are the scripts' own."""
    add_text(pg, 'card', first=True, x=0, y=58, w=800, h=422, font=2, c={'bco': PANEL, 'pco': INK, 'borderc': 0})
    add_text(pg, 'strip', after='card', x=0, y=0, w=800, h=58, font=2, c={'bco': STRIP, 'pco': INK, 'borderc': 0})
    put(pg, 't1', x=12, y=4, w=490, h=50, font=0, c={'bco': STRIP, 'pco': INK, 'borderc': 0}, a={'borderw': 0, 'xcen': 0})
    move_after(pg, 't1', 'strip')
    put(pg, 'refshow', x=4, y=4, w=33, h=35)
    key(pg, 'b249', 510, 4, 88, 50, GREY, 0, 'Hide')
    key(pg, 'b251', 606, 4, 140, 50, GREY, 0, 'Cancel')
    order = [c['n'] for c in pg['comps']]
    before_show = order[order.index('show') - 1] if order[order.index('show') - 1] != 'field' else order[order.index('show') - 2]
    add_text(pg, 'field', after=before_show, x=6, y=66, w=660, h=58, font=2, c={'bco': INK, 'pco': BLACK, 'borderc': BLACK},
             a={'style': 1, 'borderw': 2})
    put(pg, 'show', x=18, y=70, w=640, h=50, font=5, c={'bco': INK, 'pco': BLACK, 'borderc': INK}, a={'style': 0, 'borderw': 0})
    key(pg, 'b200', 672, 66, 122, 58, FKEY, 0, 'Delete')
    Y, H = (134, 220, 306, 392), 84
    for r, row in enumerate((('b0', 'b1', 'b2', 'b3', 'b4', 'b5', 'b6', 'b7', 'b8', 'b9'),
                             ('b20', 'b21', 'b22', 'b23', 'b24', 'b25', 'b26', 'b27', 'b28', 'b244'),
                             ('b40', 'b41', 'b42', 'b43', 'b44', 'b45', 'b46', 'b230', 'b231', 'b232'))):
        for c_, n in enumerate(row): key(pg, n, 1 + 80 * c_, Y[r], 78, H)
    x = 1
    for n, w, face, font, txt in (('b220', 118, KEY, 0, None), ('b240', 78, KEY, 0, None), ('b201', 78, KEY, 0, 'Tab'),
                                  ('b241', 78, KEY, 0, None), ('b242', 198, KEY, 0, 'Space'), ('b243', 78, KEY, 0, None),
                                  ('b210', 158, GO, 0, None)):
        key(pg, n, x, Y[3], w, H, face, font, txt); x += w + 2


# ------------------------------------------------------------------ 57 keybdB, the number pad (models.9, adapted)
def keypad(pg):
    """The number pad as a message box over the page that opened it, in the house keys, on one grid of three 150 px columns
    8 px apart (every gap across and down is 8 px; 16 px inside the box's sides and foot).
    Its top is y 62 (fix pass): below the calling page's 58 px title strip, so the title stays whole, and below the
    banner's band (y < 34), so a banner clearing repaints nothing of the pad.
    The question: 388 px in font 2 as before (every question fits, and the other groups measured theirs against it), left
    -aligned at the field's edge, with "Hide" (b249, small, as on the full keyboard) at its right end. The field over two
    columns (17 Courier digits), Delete over the third; Cancel under the first, OK (pale yellow) under the other two.
    t2 (a black rule) is parked."""
    X, W, Y0 = (167, 325, 483), 150, 62
    put(pg, 't0', x=151, y=Y0, w=498, h=412, c={'bco': PANEL, 'pco': INK, 'borderc': INK}, a={'style': 5, 'borderw': 0})
    put(pg, 't1', x=X[0], y=Y0 + 8, w=388, h=40, font=2, c={'bco': PANEL, 'pco': INK, 'borderc': 0}, a={'borderw': 0, 'xcen': 0})
    key(pg, 'b249', 563, Y0 + 8, 70, 40, GREY, 6, 'Hide')       # (a small key: 52 px of font 6 in 70)
    park(pg, 't2')
    order = [c['n'] for c in pg['comps']]
    before_show = order[order.index('show') - 1] if order[order.index('show') - 1] != 'field' else order[order.index('show') - 2]
    add_text(pg, 'field', after=before_show, x=X[0], y=Y0 + 56, w=X[1] + W - X[0], h=50, font=2,
             c={'bco': INK, 'pco': BLACK, 'borderc': BLACK}, a={'style': 1, 'borderw': 2})
    put(pg, 'show', x=X[0] + 10, y=Y0 + 59, w=X[1] + W - X[0] - 14, h=44, font=5, c={'bco': INK, 'pco': BLACK, 'borderc': INK},
        a={'style': 0, 'borderw': 0})
    key(pg, 'b200', X[2], Y0 + 56, W, 50, FKEY, 0, 'Delete')
    for r, row in enumerate((('b1', 'b2', 'b3'), ('b4', 'b5', 'b6'), ('b7', 'b8', 'b9'), ('b0', 'b99', 'b10'))):
        for c_, n in enumerate(row): key(pg, n, X[c_], Y0 + 114 + 58 * r, W, 50)
    key(pg, 'b251', X[0], Y0 + 346, W, 50, GREY, 0, 'Cancel')
    key(pg, 'b210', X[1], Y0 + 346, X[2] + W - X[1], 50, GO, 0)


# ------------------------------------------------------------------ 48 BackupView (models.12)
def backup(pg):
    # The dialog centred on the glass at y 240, level with its sibling File exchange (47) over the same Models page (fix
    # pass: it was 8 px higher).
    rect(pg, 'Dialog_ring', 137, 117, 526, 246); rect(pg, 'Dialog', 140, 120, 520, 240)
    rect(pg, 't3', 142, 122, 516, 46); rect(pg, 'Modelname', 160, 176, 480, 40)
    rect(pg, 't0', 160, 228, 210, 44); rect(pg, 't1', 380, 228, 260, 44)
    rect(pg, 'b1', 160, 292, 200, 54); rect(pg, 'b0', 440, 292, 200, 54)
    put(pg, 't0', a={'xcen': 2})                         # the label ends 12 px before its box (it floated at the far left)
    # The Teensy writes all four; the defaults were "File name (.MOD)" / "Model memory backup" / "Modelname" / "newtxt"
    # (t0 "File name" or "New file name", t3 "Create backup file for" or "Rename backup file").
    put(pg, 't0', txt=''); put(pg, 't3', txt=''); put(pg, 'Modelname', txt=''); put(pg, 't1', txt='')
    ev_title(pg, 't1', 'p', 'Filename?', 'File name')    # the keyboard's question: sentence case, no question mark


# ------------------------------------------------------------------ 47 FileExchView
def file_exchange(pg):
    put(pg, 'filename', txt='')                          # (the Teensy writes it; the default was "(file)")
    put(pg, 't0', txt='')                                # (the Teensy writes "Sending file" or "Receiving file"; was "File exchange")


# ------------------------------------------------------------------ 50 RenameView
def rename(pg):
    put(pg, 'NewName', txt='')                           # (the Teensy writes the model's name; the default was "Model Name")
    ev_title(pg, 'NewName', 'p', 'Model name?', 'Model name')


# ------------------------------------------------------------------ 14 ImageView
def picture_page(pg):
    """The screen's own chooser covers this page from its first frame; the page itself shows only when the chooser cannot
    open. Its title and the model's name were see-through on the picture: now solid, on the page's strip, Help in its place.
    The title says "Picture for <name>" as the chooser, its help ("Model picture help") and Model options' "Model picture
    ..." do (it said "Choose image for"); the name gets 436 px (was 335) and ends 12 px before Help. The list has the sunken
    frame of the other lists (19, 46), not a red one. t0's default "Modelname" stays: src/pics_device.h reads it as "no name
    yet"."""
    add_text(pg, 'strip', first=True, x=0, y=0, w=800, h=58, font=2, c={'bco': STRIP, 'pco': INK, 'borderc': 0})
    put(pg, 'Title', x=14, y=10, w=153, h=38, sta=1, txt='Picture for', c={'bco': STRIP}, a={'borderw': 0, 'xcen': 2})
    put(pg, 't0', x=172, y=10, w=436, h=38, sta=1, c={'bco': STRIP}, a={'borderw': 0})   # (one space after "for", as before)
    put(pg, 'MMems', a={'style': 2})
    put(pg, 'b17', x=620, y=4, w=170, h=50)
    ev_title(pg, 'b17', 'r', 'Image help', 'Model picture help')


EDITS = {15: models_page, 3: model_ids, 46: id_list, 19: log_files, 44: viewer, 56: keyboard, 57: keypad, 48: backup,
         47: file_exchange, 50: rename, 14: picture_page}
