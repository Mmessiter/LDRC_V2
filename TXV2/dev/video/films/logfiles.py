#!/usr/bin/env python3
"""Film LOGFILES: the log files, a tour, and keeping them tidy. The facts are LOGFILES.TXT's (and LOG.TXT's: with a model
connected, Files says 'Switch it off to see the files.' - LogFilesList.h - so the model is off: Model setup is 4_nomodel).
The list is scenario 19_open: 01-10-26.LOG, the first of October 2026, chosen. Made with dev/video/filmkit.py.
18 Oct 2026: starts on Model setup (then Log, then Files), no closing line, and an "In practice" part (Malcolm: "look
beyond the simple functions' description and also describe how to use for solving real-world flying issues")."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at, comp
from common import model_route, model_route_play
f = Film('LOGFILES', 'Log files', "The transmitter's log files")
model_route(f, 'Log', setup_shot=prefix('4.txt', '4_nomodel'))
f.shot('log', prefix('44.txt', '44_log')); f.shot('p', prefix('19.txt', '19_open'))
x, y, w, h = comp('LogFiles', 'FilesBox'); ROW = (x + w - 18, y + h // 2)   # (the chosen file's row, at its right-hand end: its name and size stay in sight)
f.line('title', "Log files. Seeing and deleting the transmitter's log files.")
f.line('log', "This is today's log. With the model switched off, press Files.")
f.line('page', 'This is the Log files page.')
f.line('list', "Each file is one day's log, named by its date: day, month, year. Its size is beside it.")
f.line('view', "Touch a file, then press View to read it, or Delete to remove it. Don't worry: it asks first.")
f.line('space', "Below the list: the card's total size, the space used, and the space free.")
f.line('ok', 'OK goes back to the log viewer.')
f.line('day', "Here's how to find a flight. There's one file a day, so pick the day you flew, and press View. This one is the first of October.")
f.line('tidy', "Tidy up now and then: delete old logs you don't need. Copy any you'd like to keep to your computer first.")
f.line('auto', 'And if you forget, no harm done. With more than ninety files at switch-on, the oldest are deleted, leaving the newest eighty.')
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Log', 'log')
f.say('log', 'Press Files.', after=0.3); f.tap(*at('LogView', 'b0'), 'p')
f.say('page', 'Log files.')
f.point(*ROW, 'list', 'One file a day: day, month, year.')
f.point(*at('LogFiles', 'b0'), 'view', 'View, or Delete.')
f.point(*at('LogFiles', 't1'), 'space', 'The card: total, used, free.')
f.point(*at('LogFiles', 'b10'), 'ok', 'OK.')
f.point(*at('LogFiles', 'b0'), 'day', 'Tip: pick the day you flew.')
f.point(*at('LogFiles', 'b1'), 'tidy', 'Tip: delete old ones.')
f.cap = None; f.say('auto', 'Tip: it keeps the newest 80.')
f.end(); f.finish()
