#!/usr/bin/env python3
"""Film BLACKBOX: the flight recorder, a tour. The words are BLACKBOX.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, rf_route, rf_route_play, rfs, SAVE_SHOWN, FRONT_NO_MODEL
f = Film('BLACKBOX', 'Black box', "The flight controller's flight recorder")
rf_route(f, 'Black box ...')
f.shot('p', rfs('73.txt', '73_blackbox')); f.shot('e', rfs('73.txt', '73_blackbox', SAVE_SHOWN))
f.line('title', "Black box. Setting up the flight controller's flight recorder.")
f.line('page', 'This is the Black box page, the same in every bank.')
f.line('when', 'Tap the box beside When, Where or How often to step through its choices. Whenever armed records every flight, with no switch needed.')
f.line('where', 'Where: the flight controller\'s own memory, or its card.')
f.line('memory', 'The memory lines show how much is used.')
f.line('erase', 'Erase all flight logs needs the model connected, and asks first.')
f.line('save', 'Save appears once something is changed.')
f.line('ok', 'OK leaves. With a change not saved it asks first.')
f.line('end', "That's the Black box page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Black box ...', 'p')
f.say('page', 'Black box.')
f.point(*at('BlackboxView', 'ltn0'), 'when', 'When to record.')
f.point(*at('BlackboxView', 'ltn1'), 'where', 'Where.')
f.point(*at('BlackboxView', 'h1'), 'memory', 'Memory.')
f.point(*at('BlackboxView', 'b2'), 'erase', 'Erase all flight logs.')
f.under('e'); f.hold(0.6); f.point(*at('BlackboxView', 'b3'), 'save', 'Save.')
f.point(*at('BlackboxView', 'b1'), 'ok', 'OK.')
f.end('end'); f.finish()
