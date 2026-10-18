#!/usr/bin/env python3
"""Film FAILSAFE: setting the failsafe, and what makes a good one. The facts are FAILSAFE.TXT's; Save's progress is scenario
36_saving (FailSAVE, main.cpp). The page opens with channels 1 to 3 ticked (36_open has 1 to 4: Rudder un-ticked here, so the
tick is seen to appear). Made with dev/video/filmkit.py.
18 Oct 2026: starts on Model setup, no closing line, and an "In practice" part (Malcolm: "look beyond the simple
functions' description and also describe how to use for solving real-world flying issues")."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('FAILSAFE', 'Failsafe', 'Where the controls go if the signal is lost')
model_route(f, 'Failsafe')
opn = prefix('36.txt', '36_open')
f.shot('p0', opn + 'fs4.val=0\n'); f.shot('p', opn)
f.shot('psave', prefix('36.txt', '36_saving'))
f.shot('pdone', opn + 'vis Progress,0\n')
f.line('title', 'Failsafe. Where the controls go if the receiver loses the signal.')
f.line('page', 'This is the Failsafe page. Switch the model on and connect first: the positions are saved in the receiver.')
f.line('tick', 'Tick the channels that should go to a set position.')
f.line('hold', "Now put the sticks and switches where the model should go, with the motor switched off, so the throttle's saved at Motor off value. Hold them there, and press Save.")
f.line('where', 'Save works only while the model is connected. It sends the ticks too, so after changing them, press Save again.')
f.line('what', "If the receiver hears nothing for about one and a half seconds, it moves the controls to the saved positions. When the signal comes back, you're back in control.")
f.line('all', 'All ticks every channel. None clears them all.')
f.line('ok', 'OK keeps the ticks, and takes you back to Model setup.')
f.line('plane', 'So what makes a good failsafe? On an aeroplane, many pilots choose motor off, a little up elevator, and some rudder. Then it circles down gently, rather than flying away.')
f.line('test', 'Then test it on the ground, with the propeller off. Switch the transmitter off: after a second or two, the controls should move where you set them, and the motor must stay off.')
f.line('rf', "A Rotorflight helicopter doesn't use these positions. Its flight controller's own failsafe takes over, so set it up there.")
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Failsafe', 'p0')
f.say('page', 'Failsafe. Model connected.')
f.say('tick', 'Tick the channels.', after=0.3); f.tap(*at('FailSafeView', 'fs4')); f.under('p'); f.hold(0.8)
f.say('hold', 'Hold the sticks there; press Save.', after=0.3); f.tap(*at('FailSafeView', 'b0')); f.under('psave'); f.hold(1.2); f.under('pdone'); f.hold(0.6)
f.say('where', 'Save: only while connected.')
f.cap = None; f.say('what', 'After about 1.5 s without signal.')
f.point(*at('FailSafeView', 'b1'), 'all', 'All, or None.')
f.point(*at('FailSafeView', 'b10'), 'ok', 'OK keeps the ticks.')
f.point(*at('FailSafeView', 't1'), 'plane', 'Tip: motor off, circle down.')
f.cap = None; f.say('test', 'Tip: test it, propeller off.')
f.point(*at('FailSafeView', 'fs1'), 'rf', 'Tip: Rotorflight? Its own failsafe.')
f.end(); f.finish()
