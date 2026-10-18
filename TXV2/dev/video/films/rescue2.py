#!/usr/bin/env python3
"""Film RESCUE2: rescue's second page - a tour, then which mode to choose (a barometer), a hold height clear of the trees,
and Max collective for a gentler climb. The facts are RESCUE2.TXT's; Rotorflight's rescue.c caps its height-hold collective
at Max collective (rescueApplyAltitudePID), and its height is measured from where the model was armed (position.c).
Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the setup pages, real uses, livelier words, no closing line): starts on the Rotorflight menu,
then Rescue, then Next."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
f = Film('RESCUE2', 'Rescue: hold height', 'Climb, or climb and hold a height')
rf_route(f, 'Rescue ...')
p2 = rfs('59.txt', '59_loaded')                      # (Level & climb, 25.00 m, Max collective 65.5)
f.shot('r', rfs('58.txt', '58_loaded')); f.shot('p', p2); f.shot('e', p2 + SAVE_SHOWN)
f.shot('hh', p2 + 'tn0.txt="Level & hold height"\n' + SAVE_SHOWN)   # (the tips point at a row's name: its value stays in sight)
f.line('title', 'Rescue, hold height. What rescue does once the model is level.')
f.line('r', 'This is the Rescue page. Press Next.')
f.line('page', "This is Rescue hold height: what rescue does once the model is level. It climbs, or climbs and holds a height. It's for the bank shown at the top left.")
f.line('mode', 'Rescue mode: tap it to step through Off, Level and climb, and Level and hold height.')
f.line('height', 'Hold height, in metres: the height rescue climbs to, and holds.')
f.line('pid', "Height hold P, I and D: how firmly it holds that height. Rotorflight's defaults suit most models, so change them in small steps.")
f.line('maxcol', 'Max collective: the most collective rescue may ever use.')
f.line('prev', 'Previous goes back to the first page, with your changes kept, but not yet saved.')
f.line('save', "Save appears once something's changed. It writes both rescue pages. And OK leaves.")
f.line('which', 'So which mode? With a barometer in your flight controller, Level and hold height climbs to the hold height, and stays there. No barometer? Choose Level and climb.')
f.line('trees', "Choose a hold height well clear of the trees round your field. It's measured from where you armed the model. Here, twenty five metres. And test it high up first.")
f.line('gentle', 'In this mode, Max collective keeps the climb in check. Lower it for a gentler climb, but leave enough for the model to hover.')
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Rescue ...', 'r')
f.say('r', 'Press Next.', after=0.3); f.tap(*at('RescueView', 'b2'), 'p')
f.say('page', 'Rescue: hold height.')
f.point(*at('Rescue2View', 'tn0'), 'mode', 'Rescue mode.')
f.point(*at('Rescue2View', 'tn1'), 'height', 'Hold height.')
f.point(*at('Rescue2View', 'tn2'), 'pid', 'Height hold P, I and D.')
f.point(*at('Rescue2View', 'tn5'), 'maxcol', 'Max collective.')
f.point(*at('Rescue2View', 'b2'), 'prev', '< Previous.')
f.under('e'); f.hold(0.6); f.point(*at('Rescue2View', 'b3'), 'save', 'Save; OK.')
f.show('hh'); f.point(*at('Rescue2View', 'ltn0'), 'which', 'Tip: hold height? A barometer.')
f.point(*at('Rescue2View', 'ltn1'), 'trees', 'Tip: clear of the trees.')
f.point(*at('Rescue2View', 'ltn5'), 'gentle', 'Tip: a gentler climb.')
f.end(); f.finish()
