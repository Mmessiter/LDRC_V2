#!/usr/bin/env python3
"""Film MACROS: setting up a macro, a tour. The words are MACROS.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, FRONT_NO_MODEL
f = Film('MACROS', 'Macros', 'A channel moved for a set time, by a switch')
model_route(f, 'Macros')
f.shot('p', prefix('27.txt', '27_open'))
f.line('title', 'Macros. A channel moved to a set position, for a set time.')
f.line('page', 'This is the Macros page. A macro moves one channel to a set position for a set time, when a trigger channel, usually a switch, reaches the top of its travel. Useful for a helicopter rescue switch.')
f.line('number', 'First choose a macro number, one to eight.')
f.line('trigger', 'Trigger channel starts the macro. Nought is off.')
f.line('move', 'Channel to move. Its name shows beside it.')
f.line('position', 'Move to position: nought to a hundred and eighty. Ninety is the centre.')
f.line('times', 'Delay and Duration, in tenths of a second. Delay nought moves at once.')
f.line('ok', 'Press OK to save.')
f.line('end', "That's how to set up a macro.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Macros', 'p')
f.say('page', 'Macros.')
f.point(*at('MacrosView', 'Mno'), 'number', 'Macro number.')
f.point(*at('MacrosView', 'Tch'), 'trigger', 'Trigger channel.')
f.point(*at('MacrosView', 'Mch'), 'move', 'Channel to move.')
f.point(*at('MacrosView', 'Pos'), 'position', 'Position.')
f.point(*at('MacrosView', 'Del'), 'times', 'Delay and Duration.')
f.point(*at('MacrosView', 'b10'), 'ok', 'OK saves.')
f.end('end'); f.finish()
