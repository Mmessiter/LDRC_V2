#!/usr/bin/env python3
"""Film SLOWSERV: servo speed, a tour. The words are SLOWSERV.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('SLOWSERV', 'Servo speed', 'Slowing a servo down')
model_route(f, 'Servo speed')
f.shot('p', prefix('35.txt', '35_open'))
f.line('title', 'Servo speed. Slowing a servo down, for flaps, airbrakes or undercarriage.')
f.line('page', 'This is the Servo speed page.')
f.line('box', "Touch a channel's box and type its speed, from one to a hundred. A hundred is full speed. One is the slowest.")
f.line('half', 'Halve the number, and the move takes twice as long. Ten takes about one and a half seconds, from end to end.')
f.line('bank', 'Each bank has its own speeds. The bank in use is shown at the top left.')
f.line('reset', "Reset puts this bank's speeds back to a hundred.")
f.line('ok', 'OK keeps the changes, and goes back to Model setup.')
f.line('end', "That's the Servo speed page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Servo speed', 'p')
f.say('page', 'Servo speed.')
f.point(*at('SlowServoView', 'n4'), 'box', '1 to 100: 100 is full speed.')
f.cap = None; f.say('half', 'Half the number: twice as long.')
f.point(*at('SlowServoView', 't14'), 'bank', 'The bank in use.')
f.point(*at('SlowServoView', 'b0'), 'reset', 'Reset.')
f.point(*at('SlowServoView', 'b10'), 'ok', 'OK keeps the changes.')
f.end('end'); f.finish()
