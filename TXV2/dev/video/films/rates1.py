#!/usr/bin/env python3
"""Film RATES1: Rotorflight's rates, a tour. The words are RATES1.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, rf_route, rf_route_play, keypad_shots, KEY
f = Film('RATES1', 'Rates (Rotorflight)', 'How fast the sticks turn the helicopter')
rf_route(f, 'Rates ...')
f.shot('p', prefix('1.txt', '1_open')); f.shot('e', prefix('1.txt', '1_edited'))
f.line('title', 'Rates. How fast the sticks turn the helicopter, and how much pitch the collective gives.')
f.line('page', 'This is the Rates page, for the rate shown at the top left. Choose the rate with its switch, and wait while it loads.')
f.line('type', "The columns follow the rate's type, on this line.")
f.line('numbers', 'Roll, pitch and yaw are in degrees per second, which the flight controller will seek. Collective is degrees of blade pitch.')
f.line('touch', 'Touch a box and type the new value.')
f.line('save', 'Then press Save. It appears once you touch a box. Save before you move the switch.')
f.line('more', 'Dynamics has how the model follows the stick. Curves draws the rates.')
f.line('ok', 'OK goes back to the Rotorflight page.')
f.line('end', "That's the Rates page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Rates ...', 'p')
f.say('page', 'Rates.')
f.point(*at('RatesView', 'rtl'), 'type', 'Rates type.')
f.point(*at('RatesView', 't1'), 'numbers', 'Degrees per second.')
f.point(*at('RatesView', 'tn0'), 'touch', 'Touch a box.')
f.under('e'); f.hold(0.6); f.point(*at('RatesView', 'b3'), 'save', 'Save.')
f.point(*at('RatesView', 'b2'), 'more', 'Dynamics; Curves.')
f.point(*at('RatesView', 'b1'), 'ok', 'OK.')
f.end('end'); f.finish()
