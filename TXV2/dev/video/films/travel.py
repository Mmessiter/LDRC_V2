#!/usr/bin/env python3
"""Film TRAVEL: Travel extents, the first page - a tour, then real uses: a control that moves the wrong way (reverse it here,
or a single servo on the Servos page), and a swash not quite level (a small swash trim). The facts are TRAVEL.TXT's and
SERVOS.TXT's (Reversed: one servo). Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the setup pages, real uses, livelier words, no closing line): starts on the Rotorflight menu."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
f = Film('TRAVEL', 'Travel extents', 'How the sticks reach the swash and the tail')
rf_route(f, 'Travel extents ...')
opn = rfs('62.txt', '62_loaded')                     # (Elevator reversed on, Roll trim -1.5)
f.shot('p', opn); f.shot('e', opn + SAVE_SHOWN)
f.shot('rev', opn + 'tn6.val=1\n' + SAVE_SHOWN)       # (Aileron reversed ticked; the tips point at a row's name: its value in sight)
f.line('title', 'Travel extents. How the sticks reach the swash and the tail.')
f.line('page', "This is the first Travel extents page: how the sticks reach the swash and the tail. It's the same in every bank.")
f.line('rotor', 'Main rotor settings: the swashplate type and the rotor direction. They show what the flight controller has. You change them in First time basics.')
f.line('reversed', 'Aileron, Elevator and Collective reversed: green is reversed. Each one reverses that control, and nothing else.')
f.line('trims', 'Swash trims: small corrections that level the swash. Tap a number to type a new one.')
f.line('next', 'There are four pages: this one, the swash, the tail, and the bench measure, for a pitch gauge. Next and Previous move between them, with your changes kept.')
f.line('save', "Save appears once something's changed. It asks first, because it changes how far the swash and tail move.")
f.line('ok', 'OK leaves. With a change not saved, it asks first.')
f.line('revtip', "Here's the check to make before a first flight, blades off. Move each stick, and watch the swash. If it tilts the wrong way for one stick, reverse that control here.")
f.line('servotip', 'But if the swash tilts when it should simply rise and fall, one servo is the wrong way round. Reverse that servo on the Servos page instead.')
f.line('trimtip', "Swash not quite level with the sticks centred? A small swash trim levels it: here, roll trim is minus one point five. Anything bigger? Adjust the servo centres instead.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Travel extents ...', 'p')
f.say('page', 'Travel extents.')
f.point(*at('TravelView', 'i0'), 'rotor', 'Main rotor settings.')
f.point(*at('TravelView', 'tn7'), 'reversed', 'Reversed: green.')
f.point(*at('TravelView', 'tn9'), 'trims', 'Swash trims.')
f.point(*at('TravelView', 'b2'), 'next', 'Four pages: Next >.')
f.under('e'); f.hold(0.6); f.point(*at('TravelView', 'b3'), 'save', 'Save: it asks first.')
f.point(*at('TravelView', 'b1'), 'ok', 'OK.')
f.show('rev'); f.point(*at('TravelView', 'ltn6'), 'revtip', 'Tip: wrong way? Reverse it here.')
f.cap = None; f.say('servotip', 'Tip: one servo? The Servos page.')
f.point(*at('TravelView', 'ltn9'), 'trimtip', 'Tip: level it with a small trim.')
f.end(); f.finish()
