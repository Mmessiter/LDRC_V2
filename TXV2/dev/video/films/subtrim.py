#!/usr/bin/env python3
"""Film SUBTRIM: subtrim, a tour, and how pilots use it. The facts are SUBTRIM.TXT's (Rotorflight's own servo centres:
SERVOS.TXT, 'Centre (subtrim)' on the Rotorflight menu's Servos page); a channel chosen is the page's own code (a box
touched: white, the slider at its value + 127), as scenario 32_ch4. Made with dev/video/filmkit.py.
18 Oct 2026: starts on Model setup, no closing line, and an "In practice" part (Malcolm: "look beyond the simple
functions' description and also describe how to use for solving real-world flying issues")."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, knob
from common import model_route, model_route_play
f = Film('SUBTRIM', 'Subtrim', 'The exact centre of each servo')
model_route(f, 'Subtrim')
opn = prefix('32.txt', '32_open')
BOX = lambda ch: 'n00' if ch == 1 else 'n%d' % (ch - 1)          # (each channel's box: Ch 1 is n00, Ch 2 n1 ... Ch 16 n15)
def page(vals, ch):
    """the page with these subtrims ({channel: value}) and channel ch chosen, as the page's own code draws it"""
    return opn + ''.join('%s.val=%d\n' % (BOX(c), v) for c, v in vals.items()) + 'click %s,0\nn0.val=%d\n' % (BOX(ch), vals.get(ch, 0))
f.shot('p', opn); f.shot('p4', prefix('32.txt', '32_ch4'))
f.shot('big', page({4: 85}, 4))                                   # (a rudder needing far too much: 85 of 127)
f.shot('rf', page({1: 0, 2: 0, 3: 0, 4: 0}, 1))                   # (a Rotorflight helicopter: every subtrim nought)
f.line('title', "Subtrim. Getting each servo's centre exactly right.")
f.line('page', "This is the Subtrim page. It sets the exact centre of each servo, for this model. It's the same in every bank.")
f.line('choose', 'Touch a channel to choose it. Its box turns white.')
f.line('move', 'Then move the slider, or press minus and plus. The servo moves as you go, so you can watch it.')
f.line('zero', 'Zero puts the chosen channel back to nought.')
f.line('ok', 'OK keeps the changes, and takes you back to Model setup.')
f.line('level', "Here's how to use it. Centre the sticks, and look at each servo arm: it should usually sit square to its pushrod. If one's a touch out, a few clicks here put it right.")
f.line('big', "Needs a big subtrim? Adjust the linkage instead: move the arm round a spline, or change the pushrod's length. A big subtrim can make the movement uneven.")
f.line('rf', "On a Rotorflight helicopter, keep every subtrim at nought. To the flight controller, a subtrim just looks like a stick held a little off centre.")
f.line('rf2', "Centre its servos on the Rotorflight menu instead: Servos, then Centre. Blades off for that, of course.")
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Subtrim', 'p')
f.say('page', 'Subtrim.')
f.cap = None; f.say('choose', 'Touch a channel.', after=0.3); f.tap(*at('SubTrimView', 'n3')); f.under('p4'); f.hold(0.8)
f.point(*knob('SubTrimView', 'h0', 12 + 127), 'move', 'The slider, or - and +.')
f.point(*at('SubTrimView', 'b2'), 'zero', 'Zero.')
f.point(*at('SubTrimView', 'b10'), 'ok', 'OK keeps the changes.')
f.point(*at('SubTrimView', 'b0'), 'level', 'Tip: arms square, sticks centred.')
f.show('big'); f.point(*knob('SubTrimView', 'h0', 85 + 127), 'big', 'Tip: big? Adjust the linkage.')
f.show('rf'); f.point(*at('SubTrimView', 'n00'), 'rf', 'Tip: Rotorflight? All nought.')
f.cap = None; f.say('rf2', 'Rotorflight menu: Servos, Centre.')
f.end(); f.finish()
