#!/usr/bin/env python3
"""Film SLOWSERV: servo speed, a tour, and how pilots use it. The facts are SLOWSERV.TXT's (10 takes about one and a half
seconds from end to end; halve the number and the move takes twice as long, so 5 about three seconds); Ch 5 (Gear) shown
at 10, then 5, for the undercarriage. Made with dev/video/filmkit.py.
18 Oct 2026: starts on Model setup, no closing line, and an "In practice" part (Malcolm: "look beyond the simple
functions' description and also describe how to use for solving real-world flying issues")."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('SLOWSERV', 'Servo speed', 'Slowing a servo down')
model_route(f, 'Servo speed')
opn = prefix('35.txt', '35_open')
f.shot('p', opn)
f.shot('g10', opn + 'n4.val=10\n'); f.shot('g5', opn + 'n4.val=5\n')
f.line('title', 'Servo speed. Slowing a servo down, for flaps, airbrakes or undercarriage.')
f.line('page', 'This is the Servo speed page.')
f.line('box', "Touch a channel's box, and type its speed, from one to a hundred. A hundred is full speed, and most channels stay there. One is the slowest.")
f.line('half', 'Halve the number, and the move takes twice as long.')
f.line('bank', 'Each bank has its own speeds. The bank in use is shown at the top left. Move the bank switch to set another bank.')
f.line('reset', "Reset puts this bank's speeds back to a hundred.")
f.line('ok', 'OK keeps the changes, and takes you back to Model setup.')
f.line('gear', "Here's where it shines. Undercarriage or flaps that move slowly look just like the real thing. With the usual end points, ten takes about one and a half seconds, from end to end.")
f.line('gear2', 'Want it slower still? Halve the number. Five takes about three seconds.')
f.line('banks', "One to remember: each bank keeps its own speeds. So set the speed in every bank you fly in, or the undercarriage may move at full speed in one of them.")
f.line('main', "And keep aileron, elevator, throttle and rudder at a hundred. Slowing them would make the model slow to answer you.")
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Servo speed', 'p')
f.say('page', 'Servo speed.')
f.point(*at('SlowServoView', 'n4'), 'box', '1 to 100: 100 is full speed.')
f.cap = None; f.say('half', 'Half the number: twice as long.')
f.point(*at('SlowServoView', 't14'), 'bank', 'The bank in use.')
f.point(*at('SlowServoView', 'b0'), 'reset', 'Reset.')
f.point(*at('SlowServoView', 'b10'), 'ok', 'OK keeps the changes.')
f.show('g10'); f.point(*at('SlowServoView', 'ch5'), 'gear', 'Tip: 10 is about 1.5 seconds.')   # (on the name: its box stays in sight)
f.under('g5'); f.hold(0.6); f.say('gear2', 'Tip: 5 is about 3 seconds.')
f.point(*at('SlowServoView', 't14'), 'banks', 'Tip: set every bank you fly in.')
f.point(*at('SlowServoView', 'n0'), 'main', 'Tip: flying controls at 100.')
f.end(); f.finish()
