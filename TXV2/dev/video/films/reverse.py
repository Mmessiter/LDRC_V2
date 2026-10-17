#!/usr/bin/env python3
"""Film REVERSE: reversing a channel. The words are REVERSE.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('REVERSE', 'Reverse', 'A channel that moves the wrong way')
model_route(f, 'Reverse')
opn = prefix('37.txt', '37_open')
f.shot('p', opn); f.shot('p2', opn + 'fs2.val=1\n')
f.line('title', 'Reverse. For a channel that moves the wrong way.')
f.line('page', 'This is the Reverse page.')
f.line('tick', "If a channel moves the wrong way, tick its box to reverse it.")
f.line('names', 'Reversing comes last, so each box reverses the receiver output of that number. The name beside it is the channel routed there.')
f.line('throttle', 'The motor off value is not reversed. If you reverse the throttle, change that value to match.')
f.line('ok', 'Nothing changes until you press OK.')
f.line('end', "That's the Reverse page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Reverse', 'p')
f.say('page', 'Reverse.')
f.cap = None; f.say('tick', 'Tick to reverse.', after=0.3); f.tap(*at('ReverseView', 'fs2')); f.under('p2'); f.hold(0.8)
f.point(*at('ReverseView', 'ch2'), 'names', "The output's channel.")
f.cap = None; f.say('throttle', 'Throttle: change Motor off value.')
f.point(*at('ReverseView', 'b10'), 'ok', 'OK.')
f.end('end'); f.finish()
