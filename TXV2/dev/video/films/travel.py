#!/usr/bin/env python3
"""Film TRAVEL: Travel extents, the first page, a tour. The words are TRAVEL.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
f = Film('TRAVEL', 'Travel extents', 'How the sticks reach the swash and the tail')
rf_route(f, 'Travel extents ...')
f.shot('p', rfs('62.txt', '62_loaded')); f.shot('e', rfs('62.txt', '62_loaded', SAVE_SHOWN))
f.line('title', 'Travel extents. How the sticks reach the swash and the tail.')
f.line('page', "This is the first Travel extents page: the phone app's names, the same in every bank.")
f.line('rotor', 'The main rotor set up: the swashplate type and the rotor direction.')
f.line('switch', 'Tap a switch to change it: green is on. Tap a number to type a new one.')
f.line('trims', 'Swash trims: small corrections of roll, pitch and collective.')
f.line('next', "There are four pages: this one, the swash, the tail, and the bench measure for a pitch gauge. Next and Previous move between them, with your changes kept.")
f.line('save', 'Save writes all four pages. It asks first, because it changes how far the swash and tail move. Check them on the bench, blades off.')
f.line('ok', 'OK leaves. With a change not saved it asks first.')
f.line('end', "That's the first Travel extents page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Travel extents ...', 'p')
f.say('page', 'Travel extents.')
f.point(*at('TravelView', 'i0'), 'rotor', 'Main rotor set-up.')
f.point(*at('TravelView', 'tn6'), 'switch', 'Switches and numbers.')
f.point(*at('TravelView', 'h1'), 'trims', 'Swash trims.')
f.point(*at('TravelView', 'b2'), 'next', 'Four pages: Next >.')
f.under('e'); f.hold(0.6); f.point(*at('TravelView', 'b3'), 'save', 'Save: check on the bench.')
f.point(*at('TravelView', 'b1'), 'ok', 'OK.')
f.end('end'); f.finish()
