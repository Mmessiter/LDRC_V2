#!/usr/bin/env python3
"""Film RATES_A: Rates dynamics, a tour. The words are RATES_A.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, rf_route, rf_route_play, keypad_shots, KEY
f = Film('RATES_A', 'Rates: dynamics', 'How the model follows the stick')
rf_route(f, 'Rates ...')
f.shot('r', prefix('1.txt', '1_open')); f.shot('p', prefix('42.txt', '42_open')); f.shot('e', prefix('42.txt', '42_edited'))
f.line('title', 'Rates dynamics. How the model follows the stick.')
f.line('r', 'This is the Rates page. Press Dynamics.')
f.line('page', "This page is the phone app's Dynamics card, for the rate shown at the top left.")
f.line('resp', 'Response time: how long the model takes to reach the rate the stick asks for. Higher feels softer. Nought is off.')
f.line('sharp', 'Stick sharpening: extra response on quick stick moves. Sharpening smoothing: the filter on it. Lower is smoother.')
f.line('yaw', 'For yaw only: fast move headroom, and stick centre quieting.')
f.line('save', 'Touch a box, type the new value, then press Save.')
f.line('ok', 'OK leaves the page. With unsaved changes it asks first.')
f.line('end', "That's the Dynamics page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Rates ...', 'r')
f.say('r', 'Press Dynamics.', after=0.3); f.tap(*at('RatesView', 'b2'), 'p')
f.say('page', 'Rates: dynamics.')
f.point(*at('Rates_A_View', 't1'), 'resp', 'Response time.')
f.point(*at('Rates_A_View', 't2'), 'sharp', 'Stick sharpening.')
f.point(*at('Rates_A_View', 't10'), 'yaw', 'Yaw only.')
f.under('e'); f.hold(0.6); f.point(*at('Rates_A_View', 'b3'), 'save', 'Save.')
f.point(*at('Rates_A_View', 'b1'), 'ok', 'OK.')
f.end('end'); f.finish()
