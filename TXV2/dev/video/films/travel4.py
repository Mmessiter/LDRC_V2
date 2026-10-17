#!/usr/bin/env python3
"""Film TRAVEL4: the bench measure. The words are TRAVEL4.TXT's; holding is scenario 76_held. Made with
dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
f = Film('TRAVEL4', 'Bench measure', 'Checking the blade angles with a pitch gauge')
rf_route(f, 'Travel extents ...')
f.shot('t', rfs('62.txt', '62_loaded')); f.shot('t2', rfs('63.txt', '63_loaded')); f.shot('t3', rfs('66.txt', '66_vp'))
f.shot('p', rfs('76.txt', '76_ready')); f.shot('held', rfs('76.txt', '76_held'))
f.line('title', 'Bench measure. Checking the real blade angles with a pitch gauge.')
f.line('t', 'This is the first Travel extents page. Press Next, three times.')
f.line('page', 'The bench measure holds the swash at an exact angle, so a pitch gauge can check the real blade angles. Motor off, blades clear: it moves the swash.')
f.line('axis', 'Tap Axis to choose roll or pitch, and set the angle. Eight degrees is a good one.')
f.line('hold', 'Press Hold swash.')
f.line('held', 'The swash goes to that angle. Put the gauge on one blade, turn the head slowly by hand, and note the highest reading.')
f.line('peak', 'Type that reading into Peak gauge reading. Then tap Suggested gain: it works out the gain that makes the gauge agree, and Save writes it.')
f.line('release', 'Release lets the swash go.')
f.line('end', "That's the bench measure.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Travel extents ...', 't')
f.say('t', 'Press Next, three times.', after=0.3); f.tap(*at('TravelView', 'b2'), 't2'); f.tap(*at('Travel2View', 'b2'), 't3'); f.tap(*at('Travel3View', 'b2'), 'p')
f.say('page', 'Motor off, blades clear.')
f.point(*at('Travel4View', 'ltn0'), 'axis', 'Axis and angle.')
f.cap = None; f.say('hold', 'Press Hold swash.', after=0.3); f.tap(*at('Travel4View', 'b2')); f.under('held'); f.hold(0.8)
f.say('held', 'Gauge on a blade: the highest reading.')
f.point(*at('Travel4View', 'ltn2'), 'peak', 'Peak reading; Suggested gain.')
f.point(*at('Travel4View', 'b2'), 'release', 'Release.')
f.end('end'); f.finish()
