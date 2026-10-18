#!/usr/bin/env python3
"""Film DRATES: the transmitter's own rates, a tour, and how pilots use them. The facts are DRATES.TXT's; a bank that always
uses rate 2 is scenario 31_rate2 (the list's "Use rate 2"); rate 2 shown at 70 (the scenario's 75) for the first tip.
Made with dev/video/filmkit.py.
18 Oct 2026: starts on Model setup, no closing line, and an "In practice" part (Malcolm: "look beyond the simple
functions' description and also describe how to use for solving real-world flying issues")."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('DRATES', 'Rates', 'Less, or more, movement for the same stick')
model_route(f, 'Rates')
opn = prefix('31.txt', '31_open')
f.shot('p', opn)
f.shot('r70', opn + 'rate2.val=70\n')
f.shot('b2', prefix('31.txt', '31_rate2') + 'rate2.val=70\n')
f.line('title', 'Rates. Less, or more, movement for the same stick.')
f.line('page', 'This is the Rates page. Rates make chosen channels move less, or more, for the same stick movement.')
f.line('rates', 'There are three rates, from nought to two hundred per cent. Rate one is normally a hundred. At fifty, the servo moves half as far. Touch a box to type a new one.')
f.line('channels', 'Under Channels using these rates, type the channels they work on, up to eight. Usually aileron, elevator and rudder. Nought means not used.')
f.line('switch', 'Which rate is used? The switch with the Rates job picks it: away is rate one, middle is rate two, near is rate three. Set that job in Transmitter setup, Switches.')
f.line('noswitch', 'No Rates switch? Then every channel gets a hundred per cent.')
f.line('list', 'This list lets each bank follow the rates switch, or always use one rate. It sets the bank in use, named just below the channels.')
f.line('save', 'Save keeps your changes and stays here. OK keeps them and leaves.')
f.line('first', "Here's a good start. Rate one at a hundred per cent, and rate two at about seventy. Rate two feels gentler: great while you're learning, or for smooth, relaxed flying.")
f.line('bank', 'Each bank can follow the switch, or always use one rate. Here, bank one always uses rate two, whatever the switch says. Handy for a gentle practice bank.')
f.line('rf', "A Rotorflight model doesn't use these percentages. Set its rates on the Rotorflight menu, under Rates, instead.")
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Rates', 'p')
f.say('page', 'Rates.')
f.point(*at('DualRatesView', 'rate1'), 'rates', 'Rates 1, 2 and 3.')
f.point(*at('DualRatesView', 'n2'), 'channels', 'Channels using these rates.')
f.cap = None; f.say('switch', 'The Rates switch picks one.')
f.cap = None; f.say('noswitch', 'No Rates switch: 100%.')
f.point(*at('DualRatesView', 'rate'), 'list', 'Each bank: switch, or one rate.')
f.point(*at('DualRatesView', 'b0'), 'save', 'Save, or OK.')
f.show('r70'); f.point(*at('DualRatesView', 'rate2'), 'first', 'Tip: rate 2 at about 70%.')
f.show('b2'); f.point(*at('DualRatesView', 't3'), 'bank', 'Tip: a bank with its own rate.')
f.show('p'); f.point(*at('DualRatesView', 'rate1'), 'rf', 'Tip: Rotorflight? Its own Rates.')
f.end(); f.finish()
