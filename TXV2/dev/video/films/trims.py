#!/usr/bin/env python3
"""Film TRIMS: the Trims page, a tour. The words are TRIMS.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import FRONT_CONNECTED

f = Film('TRIMS', 'Trims', 'The four trims, on screen')
f.shot('tr_front', FRONT_CONNECTED)
f.shot('tr_setup', prefix('4.txt', '4_open'))
f.shot('tr_page', prefix('28.txt', '28_open'))
f.line('title', 'Trims. The four trims, on screen.')
f.line('front', "This is the transmitter's front page. Press Model.")
f.line('setup', 'This is the Model setup page. Press Trims.')
f.line('page', 'This is the Trims page. Use it instead of the trim levers, or just to see the trims clearly.')
f.line('plus', 'Press plus or minus to move a trim. Each trim has forty steps either side of centre.')
f.line('reset', "Reset centres this bank's trims.")
f.line('move', "Once the trims are right, Move to subtrim moves this bank's four trims into the subtrims. It asks first.")
f.line('multiplier', "The trims act only when the trim multiplier, on Model setup's Options page, is above zero. Five is a very good start.")
f.line('heli', 'For a helicopter with a flybarless system, turn the trims off: set the trim multiplier to zero.')
f.line('ok', 'OK keeps the changes, and goes back to Model setup.')
f.line('end', "That's the Trims page.")
f.prepare()

f.begin(); f.say('title', after=1.6)
f.show('tr_front'); f.say('front', 'Press Model.', after=0.3); f.tap(*at('FrontView', 'b1'), 'tr_setup')
f.say('setup', 'Press Trims.', after=0.3); f.tap(*at('RXSetupView', txt='Trims'), 'tr_page')
f.say('page', 'Trims.')
f.point(*at('TrimView', 'b2'), 'plus', 'Plus and minus.')
f.point(*at('TrimView', 'b8'), 'reset', 'Reset.')
f.point(*at('TrimView', 'b9'), 'move', 'Move to subtrim.')
f.cap = None; f.say('multiplier', 'Trim multiplier above 0.')
f.say('heli', 'Flybarless: multiplier 0.')
f.point(*at('TrimView', 'b10'), 'ok', 'OK keeps the changes.')
f.end('end')
f.finish()
