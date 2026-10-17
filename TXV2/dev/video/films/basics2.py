#!/usr/bin/env python3
"""Film BASICS2: the gear ratios, a tour. The words are BASICS2.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, rf_route, rf_route_play, rfs, SAVE_SHOWN, FRONT_NO_MODEL
f = Film('BASICS2', 'Gear ratio', 'For the true head speed')
rf_route(f, 'Settings ...')
f.shot('s', rfs('61.txt', '61_open')); f.shot('b', rfs('77.txt', '77_ready')); f.shot('p', rfs('77.txt', '78_ready')); f.shot('e', rfs('77.txt', '78_ready', SAVE_SHOWN))
f.line('title', 'Gear ratio. For the true head speed the governor holds.')
f.line('s', 'This is the Rotorflight settings page. Press First time basics, then Next.')
f.line('page', 'The gear ratios: how many turns the rotor makes, for how many of the motor, or the tail. With the pole count, they give the true head speed.')
f.line('main', 'Main gear ratio: rotor to motor. Whole numbers are the teeth: pinion ten, main gear a hundred and two.')
f.line('tail', 'Tail gear ratio: rotor to tail, usually one to four, up to one to five and a half.')
f.line('save', 'Save writes all the first time basics pages.')
f.line('end', "That's the Gear ratio page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Settings ...', 's')
f.say('s', 'First-time basics, then Next.', after=0.3); f.tap(*at('RFSetupView', 'b5'), 'b'); f.tap(*at('BasicsView', 'b2'), 'p')
f.say('page', 'Gear ratio.')
f.point(*at('Basics2View', 'ltn0'), 'main', 'Main gear ratio.')
f.point(*at('Basics2View', 'ltn2'), 'tail', 'Tail gear ratio.')
f.under('e'); f.hold(0.6); f.point(*at('Basics2View', 'b3'), 'save', 'Save.')
f.end('end'); f.finish()
