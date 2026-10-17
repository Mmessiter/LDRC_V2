#!/usr/bin/env python3
"""Film SUBTRIM: subtrim, a tour. The words are SUBTRIM.TXT's; a channel chosen is scenario 32_ch4. Made with
dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('SUBTRIM', 'Subtrim', 'The exact centre of each servo')
model_route(f, 'Subtrim')
f.shot('p', prefix('32.txt', '32_open')); f.shot('p4', prefix('32.txt', '32_ch4'))
f.line('title', 'Subtrim. The exact centre of each servo.')
f.line('page', 'This is the Subtrim page. It sets the exact centre of each servo, for this model, the same in every bank.')
f.line('choose', 'Touch a channel to choose it. Its box turns white.')
f.line('move', 'Then move the slider, or press minus and plus. The servo moves as you go.')
f.line('zero', 'Zero puts the chosen channel back to nought.')
f.line('big', 'Very large subtrims should not be needed. If one is, change the linkage so that a small amount is enough.')
f.line('ok', 'OK keeps the changes, and goes back to Model setup.')
f.line('end', "That's the Subtrim page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Subtrim', 'p')
f.say('page', 'Subtrim.')
f.cap = None; f.say('choose', 'Touch a channel.', after=0.3); f.tap(*at('SubTrimView', 'ch4')); f.under('p4'); f.hold(0.8)
f.point(*at('SubTrimView', 'h0'), 'move', 'The slider, or - and +.')
f.point(*at('SubTrimView', 'b2'), 'zero', 'Zero.')
f.cap = None; f.say('big', 'Large subtrim: change the linkage.')
f.point(*at('SubTrimView', 'b10'), 'ok', 'OK keeps the changes.')
f.end('end'); f.finish()
