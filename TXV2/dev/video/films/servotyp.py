#!/usr/bin/env python3
"""Film SERVOTYP: servo types, a tour, then a narrow-pulse tail servo. The words are SERVOTYP.TXT's; the way in is Model
setup > Options > Servo types; the example is channel 4 (Rudder) with a 760 us centre (the page's own box n11). One drawing (illus.py buzz):
a hot servo, for the analogue warning. Made with dev/video/filmkit.py.
18 Oct 2026, Malcolm: start on Model setup; real uses (a narrow-pulse tail servo; the shared rate; analogue servos)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
from illus import Art
f = Film('SERVOTYP', 'Servo types', 'Pulse rate and centre, for unusual servos')
model_route(f, 'Options')
f.shot('opt', prefix('9.txt', '9_open') + 'n1.val=3\n')   # (throttle on channel 3, as in the Model options film)
f.shot('p', prefix('34.txt', '34_open'))
f.shot('tail', prefix('34.txt', '34_open') + 'n11.val=760\n')         # channel 4, the rudder: a narrow-pulse tail servo's centre
f.line('title', 'Servo types. Pulse rate and centre, for unusual servos.')
f.line('opt', 'This is the Model options page. Press Servo types.')
f.line('page', "This is the P W M servo types page. It's for servos that need something other than the usual fifty hertz, and a fifteen hundred microsecond centre.")
f.line('v1', "Good to know: it's for the servo outputs of a Version one receiver. A Version two receiver ignores it.")
f.line('box', 'Touch a box to type a new value: the rate in hertz, or the centre in microseconds.')
f.line('pairs', 'Pairs marked with stars share one timer in the receiver, so each pair runs at one rate.')
f.line('defaults', 'Defaults puts fifty hertz and fifteen hundred back on every channel.')
f.line('ok', 'OK saves the values, sends them to the receiver, and goes to the front page.')
f.line('tail', "Now, a real example. A narrow-pulse tail servo needs a centre below a thousand: often seven hundred and sixty, like this. Check its instructions for the centre and the rate.")
f.line('shared', 'Remember, channels three and four share one rate. To give the rudder its own, move it to another output, on the Inputs page.')
f.line('analogue', "And take care. Too fast a rate can harm an analogue servo: it buzzes, and runs hot.")
f.line('safe', "So check what your servo can take. If in doubt, fifty hertz is the safe choice.")
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Options', 'opt')
f.say('opt', 'Press Servo types.', after=0.3); f.tap(*at('RXOptionsView', 'b0'), 'p')
f.say('page', 'Servo types.')
f.cap = None; f.say('v1', 'Version 1 receivers only.')
f.point(*at('ServosTypeView', 'n0'), 'box', 'Touch a box.')
f.point(*at('ServosTypeView', 'legend'), 'pairs', 'Shared timers.')
f.point(*at('ServosTypeView', 'b0'), 'defaults', 'Defaults.')
f.point(*at('ServosTypeView', 'b10'), 'ok', 'OK saves and sends.')
f.show('tail'); f.point(*at('ServosTypeView', 'n11'), 'tail', 'Tip: narrow pulse? Centre 760.')
f.point(*at('ServosTypeView', 't4'), 'shared', 'Tip: 3 and 4 share a rate.')
art = Art(f); hot = lambda t: art.buzz(t, title='Too fast a rate: a hot servo')
f.show(hot(0)); f.anim(hot, 3.0); f.say('analogue', 'Tip: analogue? Take care.')
f.show('tail'); f.point(*at('ServosTypeView', 'n4'), 'safe', 'Tip: if in doubt, 50 Hz.')
f.end(); f.finish()
