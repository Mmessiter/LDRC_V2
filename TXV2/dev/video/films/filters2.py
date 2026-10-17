#!/usr/bin/env python3
"""Film FILTERS2: Filters expert mode, a tour. The words are FILTERS2.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
f = Film('FILTERS2', 'Filters: expert mode', 'The rarely needed extras')
rf_route(f, 'Filters ...')
f.shot('fl', rfs('64.txt', '64_loaded')); f.shot('p', rfs('65.txt', '65_allon')); f.shot('e', rfs('65.txt', '65_allon', SAVE_SHOWN))
f.line('title', 'Filters expert mode. The rarely needed extras.')
f.line('fl', 'This is the Filters page. Press Next.')
f.line('page', "This page has the extra filters of the phone app's expert mode. Rarely needed: the defaults suit most helicopters.")
f.line('dyn', "Dynamic cutoff: the first page's lowpass cutoff follows the head speed, instead of staying fixed.")
f.line('lp2', 'A second lowpass filter, and two notch filters, each with its own Enable.')
f.line('prev', 'Previous goes back to the first page, with your changes kept.')
f.line('save', 'Save writes both filter pages.')
f.line('end', "That's the expert mode page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Filters ...', 'fl')
f.say('fl', 'Press Next.', after=0.3); f.tap(*at('FilterView', 'b2'), 'p')
f.say('page', 'Expert mode.')
f.point(*at('Filter2View', 'h1'), 'dyn', 'Dynamic cutoff.')
f.point(*at('Filter2View', 'h2'), 'lp2', 'Lowpass 2; notches 1 and 2.')
f.point(*at('Filter2View', 'b2'), 'prev', '< Previous.')
f.under('e'); f.hold(0.6); f.point(*at('Filter2View', 'b3'), 'save', 'Save.')
f.end('end'); f.finish()
