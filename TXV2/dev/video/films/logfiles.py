#!/usr/bin/env python3
"""Film LOGFILES: the log files, a tour. The words are LOGFILES.TXT's; the list is refused while a model is connected
(LogFilesList.h), so the model is off. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, FRONT_NO_MODEL
f = Film('LOGFILES', 'Log files', "The transmitter's log files")
model_route(f, 'Log', front_shot=FRONT_NO_MODEL, setup_shot=prefix('4.txt', '4_nomodel'))
f.shot('log', prefix('44.txt', '44_log')); f.shot('p', prefix('19.txt', '19_open'))
f.line('title', "Log files. Seeing and deleting the transmitter's log files.")
f.line('log', "This is today's log. Press Files.")
f.line('page', "This is the Log files page. Each file is one day's log, named by its date: day, month, year.")
f.line('view', 'Touch a file, then press View to read it, or Delete to remove it. You are asked first.')
f.line('space', "Below the list, the card's total size, the space used, and the space free.")
f.line('ok', 'OK goes back to the log viewer.')
f.line('end', "That's the Log files page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Log', 'log')
f.say('log', 'Press Files.', after=0.3); f.tap(*at('LogView', 'b0'), 'p')
f.say('page', 'Log files.')
f.point(*at('LogFiles', 'b0'), 'view', 'View, or Delete.')
f.point(*at('LogFiles', 't1'), 'space', 'The card: total, used, free.')
f.point(*at('LogFiles', 'b10'), 'ok', 'OK.')
f.end('end'); f.finish()
