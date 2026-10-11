"""Polish of the Rotorflight tools pages (10 Oct 2026; Malcolm: "make the screens look more beautiful, well designed and easy to
use ... Don't change the logic anywhere"): 12 Backup, 67/68 Adjustments, 69/70 Switches, 71 Copy a bank, 72/75 Battery,
73 Black box. Most of it is in the pages' own scripts (hmi/backup_pages.py, adjust_pages.py, switch_pages.py,
fcsetup_pages.py); here only what hmi/rescue_pages.page() decides for every page it makes, for these pages alone:

- the header's word (t9) is the page family's own, the one the main board writes there - "Bluetooth" (Copy a bank), "All
  banks" (Battery, its sensors, Black box) - not page()'s "Bank 1", which showed until the main board wrote;
- the model name stops 20 px short of the title (Battery sensors' title is the widest of them);
- Copy a bank: From and To are empty until the main board writes "Bank n" in them (page() gives a tapped box "0");
- Black box: Overwrite oldest is in the Memory column (fcsetup_pages.py), so its label takes the Memory shade, and Erase
  all logs stands under it, in that column, a row high - with the memory it erases, away from Save. Save and OK stay in
  the foot. The notes (busy) sit over the Memory column's words, clear of every box and button."""
from polish import comp, put, rect
MEMORY_SHADE = 57215   # (hmi/rescue_pages.py PALE[1], pale blue: the Memory group's shade; not imported - importing rescue_pages re-makes pages 58/59)
NAME_W = 200           # (the model name's box as rescue_pages.page() makes it)

def header_word(word):
    def fn(pg): put(pg, 't9', txt=word)
    return fn

def name_clear_of_title(pg):
    """t11 stops 20 px before the title's words (t0 is centred across the screen in font 0)."""
    from fontw import width
    t0 = comp(pg, 't0'); left = t0['x'] + (t0['w'] - width(t0['font'], t0['txt'])) // 2
    put(pg, 't11', w=min(NAME_W, left - 20 - comp(pg, 't11')['x']))

def copybank(pg):
    put(pg, 'tn0', txt=''); put(pg, 'tn1', txt='')   # (CbShow writes "Bank n"; nothing reads them back)

def blackbox(pg):
    put(pg, 'ltn4', c={'bco': MEMORY_SHADE})   # (the Memory column's shade: tn5 and tn6 are its info lines)
    m, row = comp(pg, 'tn5'), comp(pg, 'ltn3')   # (the Memory column's left edge, width and row height; the fifth row's top)
    rect(pg, 'b2', m['x'], row['y'], m['w'], m['h'])
    # Fix (11 Oct, touch audit): the page's notes and progress (busy: "Reading from the flight controller ...", "Erasing
    # the flight logs: 12 s ...", BbDone's 5-s verdicts) over the Memory column's heading and its two lines - words only.
    # page()'s box over the island's middle took the taps of Where, Overwrite oldest and Erase all logs while it showed
    # (the screen's hit(): the topmost visible part wins). 142 px holds four lines of font 2 in the message box's
    # padding: the longest note, "Still not erased after 2 minutes: is Where set to FC memory, and restarted since?"
    # (784 px), is four lines in the 288 px it leaves for words.
    head, last = comp(pg, 'h1'), comp(pg, 'tn6')
    rect(pg, 'busy', m['x'], head['y'], m['w'], last['y'] + last['h'] - head['y'])

EDITS = {
    71: [header_word('Bluetooth'), copybank],
    72: header_word('All banks'),
    73: [header_word('All banks'), blackbox],
    75: [header_word('All banks'), name_clear_of_title],
}
