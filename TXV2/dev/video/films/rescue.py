#!/usr/bin/env python3
"""Film RESCUE: Rotorflight's rescue - a tour, then real uses: lost orientation, more height from a longer climb, and rescue
run by a macro. The facts are RESCUE.TXT's (and MACROS.TXT's for the macro). Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the setup pages, real uses, livelier words, no closing line): starts on the Rotorflight menu."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
from illus import Art
f = Film('RESCUE', 'Rescue', 'Your safety net: level, then climb')
art = Art(f)
rf_route(f, 'Rescue ...')
opn = rfs('58.txt', '58_loaded')                     # (Climb time tn5 4.0 s)
f.shot('p', opn); f.shot('e', opn + SAVE_SHOWN)
f.shot('climb', opn + 'tn5.txt="6.0"\n' + SAVE_SHOWN)   # (a tip points at a row's name: its new value stays in sight)
f.line('title', 'Rescue. Your safety net: flick a switch, and Rotorflight levels the model and climbs.')
f.line('page', 'This is the Rescue page. Flick the rescue switch, and Rotorflight takes over: it levels the model, and climbs.')
f.line('bank', 'The values are for the bank shown at the top left. Move the bank switch, and the page reads that bank.')
f.line('enable', 'Enable rescue turns it on or off. Tap a switch to change it: green is on.')
f.line('flip', "Flip upright if inverted: an upside down model is turned the right way up first. It's best left on.")
f.line('stages', 'Rescue works in stages: pull up, flip, climb, hover, then exit, each with its own collective or time. Tap a number to type a new one.')
f.line('next', 'Next opens the second page: rescue mode, and hold height.')
f.line('save', "Save appears once something's changed. It writes both rescue pages to the flight controller, then reads them back.")
f.line('ok', 'OK leaves. With unsaved changes, it asks first.')
f.line('lost', "Here's when it saves the day. Lost your orientation? Flick rescue: it levels the model and climbs. Let go of the switch, and it hands control back to you.")
f.line('first', "Before you rely on it, check three things. Enable rescue is on. Rescue has a switch, on Rotorflight's Switches page. And the level's calibrated, in Settings. Then try it high up.")
f.line('climb', 'Flying near tall trees? A longer Climb time gains more height before it hovers. Here, six seconds instead of four.')
f.line('macro', "And here's a neat trick. A macro can hold rescue on for a set time, then hand the model back by itself. The Macros animation shows you how.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Rescue ...', 'p')
f.say('page', 'Rescue.')
f.point(*at('RescueView', 't9'), 'bank', 'For the bank shown here.')
f.point(*at('RescueView', 'tn0'), 'enable', 'Enable rescue: green is on.')
f.point(*at('RescueView', 'tn1'), 'flip', 'Flip upright: best left on.')
f.point(*at('RescueView', 'tn2'), 'stages', 'Numbers: tap to type.')
f.point(*at('RescueView', 'b2'), 'next', 'Next >.')
f.under('e'); f.hold(0.6); f.point(*at('RescueView', 'b3'), 'save', 'Save.')
f.point(*at('RescueView', 'b1'), 'ok', 'OK.')
f.show(art.rescue(0)); f.anim(art.rescue, 3.0); f.say('lost', 'Tip: lost it? Flick rescue.')
f.show('p'); f.point(*at('RescueView', 'ltn0'), 'first', 'Tip: test it high up first.')
f.show('climb'); f.point(*at('RescueView', 'ltn5'), 'climb', 'Tip: more height? Climb time.')
f.show('climb', look=0.4); f.say('macro', 'Tip: rescue on a macro.')
f.end(); f.finish()
