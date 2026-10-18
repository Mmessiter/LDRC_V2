#!/usr/bin/env python3
"""Film REVERSE: reversing a channel, a tour, and the checks that matter. The facts are REVERSE.TXT's ('Motor off value':
RXSETUP1.TXT; a Rotorflight helicopter's swash and tail directions: TRAVEL.TXT and TRAVEL3.TXT, the Rotorflight menu's
Travel extents pages). The page opens with no box ticked (scenario 37_open had Elevator and Rudder ticked: un-ticked
here, so the box touched is seen to change). Made with dev/video/filmkit.py.
18 Oct 2026: starts on Model setup, no closing line, and an "In practice" part (Malcolm: "look beyond the simple
functions' description and also describe how to use for solving real-world flying issues")."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('REVERSE', 'Reverse', 'A channel that moves the wrong way')
model_route(f, 'Reverse')
opn = prefix('37.txt', '37_open') + 'fs2.val=0\nfs4.val=0\n'
f.shot('p', opn); f.shot('p2', opn + 'fs2.val=1\n')
f.shot('thr', opn + 'fs3.val=1\n')                                 # (the throttle reversed: Motor off value to match)
f.line('title', 'Reverse. For a channel that moves the wrong way.')
f.line('page', 'This is the Reverse page. There is a box for every channel.')
f.line('tick', "If a channel moves the wrong way, just tick its box to reverse it.")
f.line('names', 'Reversing comes last, after mixes, trims and subtrim. So each box reverses the receiver output of that number. The name beside it is the channel sent there.')
f.line('ok', "Don't worry: nothing changes until you press OK. OK keeps the changes, and takes you back to Model setup.")
f.line('check', "Now, the most important check of all. Before a first flight, stand behind the model and move each stick in turn. Every control must move the right way.")
f.line('check2', 'On an aeroplane, for example, pull the elevator stick back, and the elevator should go up. If it goes down, tick its box.')
f.line('throttle', "Reversing the throttle? Then change Motor off value, on the Options page, to match. It isn't reversed with the channel.")
f.line('throttle2', 'Then, with the propeller off, check that the motor stays still with the motor switched off.')
f.line('rf', "On a Rotorflight helicopter, a swash or tail that moves the wrong way is usually put right on the Rotorflight menu's Travel extents pages, not here.")
f.line('rf2', 'Take the blades off, and check every control on the bench before you fly.')
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Reverse', 'p')
f.say('page', 'Reverse.')
f.cap = None; f.say('tick', 'Tick to reverse.', after=0.3); f.tap(*at('ReverseView', 'fs2')); f.under('p2'); f.hold(0.8)
f.point(*at('ReverseView', 'ch2'), 'names', "The output's channel.")
f.point(*at('ReverseView', 'b10'), 'ok', 'Nothing changes until OK.')
f.point(*at('ReverseView', 'fs1'), 'check', 'Tip: check every control.')
f.point(*at('ReverseView', 'fs2'), 'check2', 'Stick back: elevator up.')
f.show('thr'); f.point(*at('ReverseView', 'ch3'), 'throttle', 'Tip: throttle? Motor off value.')
f.cap = None; f.say('throttle2', 'Propeller off: check it.')
f.show('p'); f.point(*at('ReverseView', 'fs4'), 'rf', 'Tip: Rotorflight? Travel extents.')
f.cap = None; f.say('rf2', 'Blades off: check on the bench.')
f.end(); f.finish()
