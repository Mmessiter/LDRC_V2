#!/usr/bin/env python3
"""Film RESCUE2: rescue's second page, a tour. The words are RESCUE2.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, rf_route, rf_route_play, keypad_shots, KEY
f = Film('RESCUE2', 'Rescue: hold height', 'Climb, or climb and hold a height')
rf_route(f, 'Rescue ...')
f.shot('r', prefix('58.txt', '58_loaded', [('Black Thunder 2', 'RAW 420 MCM')])); f.shot('p', prefix('59.txt', '59_loaded', [('Black Thunder 2', 'RAW 420 MCM')])); f.shot('e', prefix('59.txt', '59_loaded', [('Black Thunder 2', 'RAW 420 MCM')]) + 'vis b3,1\n')
f.line('title', 'Rescue hold height. What rescue does once the model is level.')
f.line('r', 'This is the Rescue page. Press Next.')
f.line('page', 'This page says what rescue does once the model is level: climb, or climb and hold a height.')
f.line('mode', 'Rescue mode: tap it to step through Off, Level and climb, and Level and hold height. Holding a height needs the flight controller\'s barometer.')
f.line('height', 'Hold height: the height rescue climbs to, and holds.')
f.line('maxcol', 'Max collective: the most collective rescue may ever use.')
f.line('prev', 'Previous goes back to the first page, with your changes kept, but not yet saved.')
f.line('ok', 'Save writes both pages. OK leaves.')
f.line('end', "That's the Rescue hold height page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Rescue ...', 'r')
f.say('r', 'Press Next.', after=0.3); f.tap(*at('RescueView', 'b2'), 'p')
f.say('page', 'Rescue: hold height.')
f.point(*at('Rescue2View', 'tn0'), 'mode', 'Rescue mode.')
f.point(*at('Rescue2View', 'tn1'), 'height', 'Hold height.')
f.point(*at('Rescue2View', 'tn5'), 'maxcol', 'Max collective.')
f.point(*at('Rescue2View', 'b2'), 'prev', '< Previous.')
f.under('e'); f.hold(0.6); f.point(*at('Rescue2View', 'b3'), 'ok', 'Save; OK.')
f.end('end'); f.finish()
