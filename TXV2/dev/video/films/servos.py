#!/usr/bin/env python3
"""Film SERVOS: Rotorflight's servos, a tour. The words are SERVOS.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, rf_route, rf_route_play, keypad_shots, KEY
f = Film('SERVOS', 'Servos (Rotorflight)', 'Each servo, one at a time')
rf_route(f, 'Servos ...')
f.shot('p', prefix('60.txt', '60_loaded', [('Black Thunder 2', 'RAW 420 MCM')])); f.shot('e', prefix('60.txt', '60_loaded', [('Black Thunder 2', 'RAW 420 MCM')]) + 'vis b3,1\n')
f.line('title', "Servos. Rotorflight's settings for each servo, one at a time.")
f.line('page', 'This is the Servos page. The same in every bank. The title says which servo you are on, and its job.')
f.line('step', 'Servo back and Servo on step through the servos. Servos one, two and three are usually the swashplate, four the tail.')
f.line('centre', 'Centre, the subtrim: where the arm sits with the sticks centred. Adjust it so the linkages are level.')
f.line('limits', 'Travel limit low and high: the stops. The servo never moves past them.')
f.line('save', 'Save appears once something is changed. Save each servo before you move on.')
f.line('ok', 'OK leaves. With a change not saved it asks first.')
f.line('end', "That's the Servos page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Servos ...', 'p')
f.say('page', 'Servos.')
f.point(*at('ServoView', 'b2'), 'step', '< Servo, Servo >.')
f.point(*at('ServoView', 'tn0'), 'centre', 'Centre.')
f.point(*at('ServoView', 'tn1'), 'limits', 'Travel limits.')
f.under('e'); f.hold(0.6); f.point(*at('ServoView', 'b3'), 'save', 'Save each servo.')
f.point(*at('ServoView', 'b1'), 'ok', 'OK.')
f.end('end'); f.finish()
