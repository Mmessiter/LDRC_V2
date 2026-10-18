#!/usr/bin/env python3
"""Film TRAVEL2: Travel extents, the swash - a tour, then real uses: linkages that bind at full stick (a lower cyclic pitch
limit), and collective pitch not equal up and down (Up/down balance). The facts are TRAVEL2.TXT's. (Not the total pitch
limit for binding: Rotorflight keeps it at least 6 degrees above the collective limit, and this model's is exactly that.)
Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the setup pages, real uses, livelier words, no closing line): starts on the Rotorflight menu,
then Travel extents, then Next."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
f = Film('TRAVEL2', 'Travel extents: swash', 'How far the swash may move, and its gains')
rf_route(f, 'Travel extents ...')
p2 = rfs('63.txt', '63_loaded')                      # (cyclic pitch limit 10.0, collective 12.0, total 18.0, balance 3.0)
f.shot('t', rfs('62.txt', '62_loaded')); f.shot('p', p2); f.shot('e', p2 + SAVE_SHOWN)
f.shot('bind', p2 + 'tn3.txt="9.0"\n' + SAVE_SHOWN)   # (the tips point at a row's name: its value stays in sight)
f.line('title', 'Travel extents, swash. How far the swash may move, and its gains.')
f.line('t', 'This is the first Travel extents page. Press Next.')
f.line('page', 'This is Travel extents, swash: how far the swash may move, and its gains.')
f.line('gains', 'Cyclic gain and Collective gain: how much of a full stick reaches the swash. Cyclic gain is one box, for roll and pitch together.')
f.line('balance', 'Up down balance evens out the collective, so up and down give the same pitch.')
f.line('limits', 'Cyclic pitch limit and Collective pitch limit: the most blade pitch each may give, either way. Total pitch limit is for the two together.')
f.line('phase', 'Swash phase angle turns the cyclic a little round the mast.')
f.line('tilt', 'Tilt correction, plus and minus: for a swash that tilts as the collective moves.')
f.line('save', "Save appears once something's changed. It writes all four Travel extents pages, after a question.")
f.line('nav', 'Previous and Next move between the pages, with your changes kept.')
f.line('bindtip', "Here's a check worth making, blades off. Give full stick in every direction. If a linkage binds, lower Cyclic pitch limit a little, then check again.")
f.line('baltip', 'Pitch gauge shows more pitch at the top of the stick than at the bottom? A little Up down balance evens them out. Small steps, then measure again.')
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Travel extents ...', 't')
f.say('t', 'Press Next.', after=0.3); f.tap(*at('TravelView', 'b2'), 'p')
f.say('page', 'Travel extents: swash.')
f.point(*at('Travel2View', 'tn0'), 'gains', 'Cyclic and Collective gain.')
f.point(*at('Travel2View', 'tn2'), 'balance', 'Up/down balance.')
f.point(*at('Travel2View', 'tn3'), 'limits', 'Pitch limits.')
f.point(*at('Travel2View', 'tn6'), 'phase', 'Swash phase angle.')
f.point(*at('Travel2View', 'tn7'), 'tilt', 'Tilt correction + and -.')
f.under('e'); f.hold(0.6); f.point(*at('Travel2View', 'b3'), 'save', 'Save: all four pages.')
f.point(*at('Travel2View', 'b4'), 'nav', '< Previous, Next >.')
f.show('bind'); f.point(*at('Travel2View', 'ltn3'), 'bindtip', 'Tip: binding? Lower the limit.')
f.point(*at('Travel2View', 'ltn2'), 'baltip', 'Tip: uneven pitch? Balance.')
f.end(); f.finish()
