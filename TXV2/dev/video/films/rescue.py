#!/usr/bin/env python3
"""Film RESCUE: Rotorflight's rescue, a tour. The words are RESCUE.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, rf_route, rf_route_play, keypad_shots, KEY
f = Film('RESCUE', 'Rescue', 'What happens when you flick the rescue switch')
rf_route(f, 'Rescue ...')
f.shot('p', prefix('58.txt', '58_loaded', [('Black Thunder 2', 'RAW 420 MCM')])); f.shot('e', prefix('58.txt', '58_loaded', [('Black Thunder 2', 'RAW 420 MCM')]) + 'vis b3,1\n')   # (Save shows once something is changed)
f.line('title', 'Rescue. What Rotorflight does when you flick the rescue switch.')
f.line('page', 'This is the Rescue page. When you flick the rescue switch, Rotorflight takes over, levels the model, and climbs.')
f.line('enable', 'Tap a switch to change it: green is on.')
f.line('number', 'Tap a number to type a new one.')
f.line('next', 'Next opens the second page: rescue mode, and hold height.')
f.line('save', 'Save appears once something is changed. It writes both rescue pages to the flight controller, and reads them back.')
f.line('switch', "Rescue also needs a switch: set one with Switches, on the Rotorflight page. And calibrate the level first.")
f.line('ok', 'OK leaves. With unsaved changes it asks first.')
f.line('end', "That's the Rescue page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Rescue ...', 'p')
f.say('page', 'Rescue.')
f.point(*at('RescueView', 'ltn0'), 'enable', 'Switches: green is on.')
f.point(*at('RescueView', 'tn2'), 'number', 'Numbers: tap to type.')
f.point(*at('RescueView', 'b2'), 'next', 'Next >.')
f.under('e'); f.hold(0.6); f.point(*at('RescueView', 'b3'), 'save', 'Save.')
f.cap = None; f.say('switch', 'A rescue switch; level calibrated.')
f.point(*at('RescueView', 'b1'), 'ok', 'OK.')
f.end('end'); f.finish()
