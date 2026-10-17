#!/usr/bin/env python3
"""Film MIXES: setting up a mix, a tour. The words are MIXES.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('MIXES', 'Mixes', 'One channel following another')
model_route(f, 'Mixes')
f.shot('p', prefix('29.txt', '29_open'))
f.line('title', 'Mixes. One channel following another.')
f.line('page', 'This is the Mixes page. A mix makes one channel, the slave, follow another, the master: rudder that follows the ailerons, say.')
f.line('number', 'First choose a mix number, with its minus and plus.')
f.line('onoff', 'Turn on Mix input or Mix output. With both off, the mix does nothing.')
f.line('bank', 'Set the bank: nought means all banks.')
f.line('master', 'Set the master channel and the slave channel. Their names show on the right.')
f.line('percent', "Percent: how much of the master's movement the slave gets. A hundred is all of it.")
f.line('ok', 'Each minus or plus works at once: watch the servos as you go. Press OK to save.')
f.line('end', "That's how to set up a mix.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Mixes', 'p')
f.say('page', 'Mixes.')
f.point(*at('MixesView', 'b0'), 'number', 'Mix number.')
f.point(*at('MixesView', 'c0'), 'onoff', 'Mix input or output.')
f.point(*at('MixesView', 'FlightMode'), 'bank', 'Bank: 0 = all.')
f.point(*at('MixesView', 'MasterChannel'), 'master', 'Master and slave.')
f.point(*at('MixesView', 'Percent'), 'percent', 'Percent.')
f.point(*at('MixesView', 'b10'), 'ok', 'OK saves.')
f.end('end'); f.finish()
