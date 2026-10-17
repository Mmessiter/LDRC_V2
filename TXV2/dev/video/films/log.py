#!/usr/bin/env python3
"""Film LOG: the transmitter's log, a tour. The words are LOG.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, rf_route, rf_route_play, rfs, SAVE_SHOWN, FRONT_NO_MODEL
f = Film('LOG', 'The log', 'What happened each day the transmitter was used')
model_route(f, 'Log')
f.shot('p', prefix('44.txt', '44_log'))
f.line('title', "The log. What happened each day the transmitter was used.")
f.line('page', "Log on Model setup opens today's log, named at the top.")
f.line('what', 'It records connections, disconnections and gaps in the radio link, the model memory found, bank and rate changes, the motor and safety switches, and the batteries.')
f.line('scroll', 'Drag the text up or down to scroll. Top and Bottom jump to the start and the end.')
f.line('files', 'Files lists all the log files, to view or delete them.')
f.line('ok', 'OK goes to the Telemetry page.')
f.line('end', "That's the log.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Log', 'p')
f.say('page', "Today's log.")
f.cap = None; f.say('what', 'What it records.')
f.point(*at('LogView', 'b1'), 'scroll', 'Drag to scroll; Top, Bottom.')
f.point(*at('LogView', 'b0'), 'files', 'Files.')
f.point(*at('LogView', 'b10'), 'ok', 'OK.')
f.end('end'); f.finish()
