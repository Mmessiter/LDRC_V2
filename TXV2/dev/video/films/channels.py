#!/usr/bin/env python3
"""Film CHANNELS: the Channels page, a tour, then a pre-flight check and the max range for Rotorflight. The words are
CHANNELS.TXT's; the example is the aileron stick pushed right (Ch1's bar and microseconds: us = 500 + 20 x the bar's value).
A channel's button opens its curve page (the Curves animation shows the editing). Made with dev/video/filmkit.py.
18 Oct 2026, Malcolm: start on Model setup; real uses (move each stick and switch before a first flight; 945 to 2055 for
Rotorflight)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play

f = Film('CHANNELS', 'Channels', 'All sixteen channels, live')
model_route(f, 'Channels')
opn = prefix('26.txt', '26_open')
f.shot('p', opn)
f.shot('stick', opn + 'Ch1.val=85\nus1.txt="2200"\n')               # the aileron stick pushed to the right
f.line('title', 'Channels. All sixteen channels, live.')
f.line('page', "This is the Channels page. It shows where all sixteen channels are, right now.")
f.line('bars', 'Each bar grows from the middle line: to the left below centre, to the right above.')
f.line('buttons', 'Odd channels have their buttons on the left, even ones on the right. The arrow on each button points to its bar. Press one to shape that channel\'s curve.')
f.line('numbers', 'Beside each button, what that channel sends now, in microseconds. Fifteen hundred is the middle.')
f.line('range', "At the bottom, Max range: the range this model's channels can use. Touch one to choose. It asks first.")
f.line('check', "Now, a check worth doing before every first flight. Move each stick and switch in turn, and watch for its bar. Here, the aileron stick, pushed right.")
f.line('check2', "Is it the right channel? Then check the model itself moves the right way, too. It's a quick way to catch a mistake on the ground.")
f.line('rf', 'Flying Rotorflight? Choose nine hundred and forty-five to two thousand and fifty-five. It sits just past the one thousand to two thousand that Rotorflight reads.')
f.line('rf2', 'So a curve taken to the top gives full travel, even with a stick that stops a little short. After any change, check every channel before you fly.')
f.prepare()

f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Channels', 'p')
f.say('page', 'Channels.')
f.point(*at('SticksView', 'Ch3'), 'bars', 'Each channel, live.')
f.point(*at('SticksView', 'Sch1'), 'buttons', 'Odd channels left, even right.')
f.point(*at('SticksView', 'us1'), 'numbers', 'Microseconds: 1500 is the middle.')
f.point(*at('SticksView', 'mr1'), 'range', 'Max range.')
f.show('stick'); f.point(445, at('SticksView', 'Ch1')[1], 'check', 'Tip: move each stick, watch.')
f.cap = None; f.say('check2', 'Tip: then check the model.')
f.point(*at('SticksView', 'mr2'), 'rf', 'Tip: Rotorflight? 945 to 2055.')
f.cap = None; f.say('rf2', 'Tip: full travel at the top.')
f.end(); f.finish()
