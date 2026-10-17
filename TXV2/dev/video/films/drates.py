#!/usr/bin/env python3
"""Film DRATES: the transmitter's own rates, a tour. The words are DRATES.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('DRATES', 'Rates', 'Less, or more, movement for the same stick')
model_route(f, 'Rates')
f.shot('p', prefix('31.txt', '31_open'))
f.line('title', 'Rates. Less, or more, movement for the same stick.')
f.line('page', 'This is the Rates page. There are three rates, each from zero to two hundred per cent. One is normally a hundred.')
f.line('rates', 'Touch the box beside each rate, and type its percentage.')
f.line('channels', 'Under Channels using these rates, touch a box and type a channel number: up to eight, usually aileron, elevator and rudder.')
f.line('switch', 'The switch with the Rates job picks the rate: away is rate one, middle is rate two, near is rate three.')
f.line('list', 'This list lets each bank follow the rates switch, or always use one rate.')
f.line('rf', 'A Rotorflight model does not use these percentages. Set its rates on the Rotorflight page.')
f.line('save', 'Save keeps your changes and stays. OK keeps them and leaves.')
f.line('end', "That's the Rates page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Rates', 'p')
f.say('page', 'Rates.')
f.point(*at('DualRatesView', 'rate1'), 'rates', 'Rates 1, 2 and 3.')
f.point(*at('DualRatesView', 'n2'), 'channels', 'Channels using these rates.')
f.cap = None; f.say('switch', 'The Rates switch.')
f.point(*at('DualRatesView', 'rate'), 'list', 'Each bank: switch, or one rate.')
f.cap = None; f.say('rf', 'Rotorflight: its own rates.')
f.point(*at('DualRatesView', 'b0'), 'save', 'Save, or OK.')
f.end('end'); f.finish()
