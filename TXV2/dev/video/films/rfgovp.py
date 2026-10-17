#!/usr/bin/env python3
"""Film RFGOVP: the governor of each bank, a tour. The words are RFGOVP.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, rf_route, rf_route_play, keypad_shots, KEY
f = Film('RFGOVP', 'Governor', 'The head speed, and how it is held')
rf_route(f, 'Governor ...')
f.shot('p', prefix('6.txt', '6_open')); f.shot('e', prefix('6.txt', '6_edited'))
f.line('title', 'Governor. The head speed, and how the governor holds it.')
f.line('page', 'This is the Governor page, for the bank shown at the top left. It needs Rotorflight two point three.')
f.line('head', 'Headspeed: the head speed this bank holds.')
f.line('gains', 'Master gain: the overall strength. P, I and D gain: how the governor corrects a head speed error.')
f.line('throttle', 'Max and min throttle: the most and the least throttle the governor may use.')
f.line('global', 'Global has the settings shared by every bank: the mode, the throttle, and the timings.')
f.line('save', 'Touch a value, type the new one, then press Save. Save is refused while the model could be armed.')
f.line('ok', 'OK goes back to the Rotorflight page.')
f.line('end', "That's the Governor page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Governor ...', 'p')
f.say('page', 'Governor.')
f.point(*at('RFGovView', 'n0'), 'head', 'Headspeed.')
f.point(*at('RFGovView', 't29'), 'gains', 'Master gain; P, I, D.')
f.point(*at('RFGovView', 't32'), 'throttle', 'Max and min throttle.')
f.point(*at('RFGovView', 'b2'), 'global', 'Global ...')
f.under('e'); f.hold(0.6); f.point(*at('RFGovView', 'b3'), 'save', 'Save.')
f.point(*at('RFGovView', 'b1'), 'ok', 'OK.')
f.end('end'); f.finish()
