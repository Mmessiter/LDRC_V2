#!/usr/bin/env python3
"""Film SWITCHES: the Switches page, a tour. The words are SWITCHES.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, FRONT_NO_MODEL
f = Film('SWITCHES', 'Switches', 'A job for each of the eight switches')
tx_route(f, 'Switches')
f.shot('p', prefix('53.txt', '53_open')); f.shot('one', prefix('54.txt', '54_open'))
f.line('title', 'Switches. A job for each of the eight switches.')
f.line('page', 'This is the Switches page. Any of the eight switches can do any job.')
f.line('top', 'Switches one to four are on the top edge, shown as seen from above, with the sticks towards you.')
f.line('front2', 'Switches five to eight are on the front: the inputs of channels five to eight.')
f.line('where', 'Beside each job is where that switch is now: near, mid or away. Move a switch to see which number it is.')
f.line('touch', "Touch a switch's number or its job to choose its job.")
f.line('one', "This page chooses that switch's job. Its own animation shows the jobs.")
f.line('end', "That's the Switches page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
tx_route_play(f, 'Switches', 'p')
f.say('page', 'Switches.')
f.point(*at('SwitchesView', 'h0'), 'top', 'Top edge: 1 to 4.')
f.point(*at('SwitchesView', 'h1'), 'front2', 'Front: 5 to 8.')
f.point(*at('SwitchesView', 'sw1'), 'where', 'Each job, and where the switch is.')
f.cap = None; f.say('touch', 'Touch a switch to choose its job.', after=0.3); f.tap(*at('SwitchesView', 'sw3'), 'one')
f.say('one', "That switch's job.", after=1.0)
f.end('end'); f.finish()
