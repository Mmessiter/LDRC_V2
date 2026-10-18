#!/usr/bin/env python3
"""Film TRAVEL4: the bench measure - a tour, then one real measurement worked through (roll at 8 degrees, the gauge reads 7.4,
Suggested gain 93.5, hold again to check), and the collective, set the direct way. The facts are TRAVEL4.TXT's; the numbers
are the Teensy's own sum (TransmitterCode RF_Travel.h BenchSuggestTapped: gain x angle / gauge, 86.5 x 8.0 / 7.4 = 93.5; the
held line and button as BenchStatus writes them; Save shows once the suggestion is put in, TravelWasEdited).
Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the setup pages, real uses, livelier words, no closing line): starts on the Rotorflight menu,
then Travel extents, Next, Next, Next."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
f = Film('TRAVEL4', 'Bench measure', 'Checking the blade angles with a pitch gauge')
rf_route(f, 'Travel extents ...')
p4 = rfs('76.txt', '76_ready')                       # (Roll, 8.0 degrees, cyclic gain 86.5)
HELD = 'i0.txt="SWASH HELD: Roll at 8.0 deg (gyros bypassed)"\nb2.txt="Release"\n'
f.shot('t', rfs('62.txt', '62_loaded')); f.shot('t2', rfs('63.txt', '63_loaded')); f.shot('t3', rfs('66.txt', '66_vp'))
f.shot('p', p4)
f.shot('held', p4 + HELD)
f.shot('gauge', p4 + HELD + 'tn2.txt="7.4"\n')
f.shot('sugg', p4 + HELD + 'tn2.txt="7.4"\ntn4.txt="93.5"\ntn3.txt="93.5"\n' + SAVE_SHOWN)
f.line('title', 'Bench measure. Checking the real blade angles with a pitch gauge.')
f.line('t', 'This is the first Travel extents page. Press Next.')
f.line('t2', 'This is the swash page. Press Next again.')
f.line('t3', 'And the tail page. Next, once more.')
f.line('page', 'This is the Bench measure. It holds the swash at an exact angle, so a pitch gauge can check the real blade angles.')
f.line('safety', "It moves the swash. So the motor's off, the safety's on, and everyone's clear of the blades. It needs the model itself, switched on.")
f.line('axis', 'Axis: tap it to choose roll or pitch.')
f.line('angle', 'Angle: the angle to hold, up to twelve degrees either way.')
f.line('peak', 'Peak gauge reading: what your gauge says, typed in.')
f.line('suggest', 'Suggested gain works out the gain that makes the gauge agree, and puts it in the Cyclic gain box.')
f.line('ex', "Let's measure one. Roll, at eight degrees: that's a good angle to use.")
f.line('hold', 'Press Hold swash.')
f.line('held', 'The swash goes to eight degrees. Put the gauge on one blade, turn the head slowly by hand, and note the highest reading.')
f.line('gauge', 'Say it reads seven point four. Type that into Peak gauge reading.')
f.line('tapsugg', 'Now tap Suggested gain.')
f.line('sugg', "Ninety three point five makes the gauge agree, and it's put in the Cyclic gain box for you.")
f.line('savesugg', 'Press Save to write it.')
f.line('check', 'Then Release, and hold again to check. The gauge should now read eight.')
f.line('coll', "Collective isn't measured here. Set it the direct way: full stick, measure the pitch, then adjust Collective gain on the swash page.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Travel extents ...', 't')
f.say('t', 'Press Next.', after=0.3); f.tap(*at('TravelView', 'b2'), 't2')
f.say('t2', 'Press Next again.', after=0.3); f.tap(*at('Travel2View', 'b2'), 't3')
f.say('t3', 'Next, once more.', after=0.3); f.tap(*at('Travel3View', 'b2'), 'p')
f.say('page', 'Bench measure.')
f.point(*at('Travel4View', 'i0'), 'safety', 'Motor off, blades clear.')
f.point(*at('Travel4View', 'tn0'), 'axis', 'Axis.')
f.point(*at('Travel4View', 'tn1'), 'angle', 'Angle.')
f.point(*at('Travel4View', 'tn2'), 'peak', 'Peak gauge reading.')
f.point(*at('Travel4View', 'tn4'), 'suggest', 'Suggested gain.')
f.point(*at('Travel4View', 'ltn1'), 'ex', 'Tip: roll, eight degrees.')
f.cap = None; f.say('hold', 'Press Hold swash.', after=0.3); f.tap(*at('Travel4View', 'b2')); f.under('held'); f.hold(0.8)
f.say('held', 'Gauge on a blade: the highest.')
f.point(*at('Travel4View', 'ltn2'), 'gauge', 'Type in the reading.'); f.under('gauge'); f.hold(1.0)
f.cap = None; f.say('tapsugg', 'Tap Suggested gain.', after=0.3); f.tap(*at('Travel4View', 'tn4')); f.under('sugg'); f.hold(0.8)
f.point(*at('Travel4View', 'ltn4'), 'sugg', 'Suggested: 93.5.')
f.point(*at('Travel4View', 'b3'), 'savesugg', 'Save writes it.')
f.point(*at('Travel4View', 'b2'), 'check', 'Tip: hold again to check.')
f.show('sugg', look=0.4); f.say('coll', 'Tip: collective: full stick.')
f.end(); f.finish()
