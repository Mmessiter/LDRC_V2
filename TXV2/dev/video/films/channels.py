#!/usr/bin/env python3
"""Film CHANNELS: the Channels page, a tour. The words are CHANNELS.TXT's; a channel's button opens its curve page (the
curve page's own animation shows the editing). Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import FRONT_CONNECTED

f = Film('CHANNELS', 'Channels', 'All sixteen channels, live')
f.shot('ch_front', FRONT_CONNECTED)
f.shot('ch_setup', prefix('4.txt', '4_open'))
f.shot('ch_page', prefix('26.txt', '26_open'))
f.shot('ch_curve', prefix('21.txt', '21_straight'))
f.line('title', 'Channels. All sixteen channels, live.')
f.line('front', "This is the transmitter's front page. Press Model.")
f.line('setup', 'This is the Model setup page. Press Channels.')
f.line('page', 'This is the Channels page. It shows where all sixteen channels are now, live.')
f.line('bars', 'Each bar grows from the middle line: to the left below centre, to the right above.')
f.line('buttons', 'Odd channels have their buttons on the left, even ones on the right. The arrow on each button points to its bar.')
f.line('numbers', 'Beside each button, what that channel sends now, in microseconds. Fifteen hundred is the middle.')
f.line('range', "At the bottom, the range this model's channels can use. Touch one to choose: it asks first.")
f.line('curve', "To edit a channel's curve, press its button.")
f.line('curvepage', "This is that channel's curve page. Its own animation shows how to edit the curve.")
f.line('end', "That's the Channels page.")
f.prepare()

f.begin(); f.say('title', after=1.6)
f.show('ch_front'); f.say('front', 'Press Model.', after=0.3); f.tap(*at('FrontView', 'b1'), 'ch_setup')
f.say('setup', 'Press Channels.', after=0.3); f.tap(*at('RXSetupView', txt='Channels'), 'ch_page')
f.say('page', 'Channels.')
f.point(400, 200, 'bars', 'Each channel, live.')
f.point(*at('SticksView', 'Sch1'), 'buttons', 'Odd channels left, even right.')
f.point(*at('SticksView', 'us1'), 'numbers', 'Microseconds: 1500 is the middle.')
f.point(*at('SticksView', 'mr1'), 'range', 'Max range.')
f.cap = None; f.say('curve', "Press a channel's button.", after=0.3); f.tap(*at('SticksView', 'Sch1'), 'ch_curve')
f.say('curvepage', 'The curve page.', after=1.0)
f.end('end')
f.finish()
