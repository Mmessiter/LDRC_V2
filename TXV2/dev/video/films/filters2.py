#!/usr/bin/env python3
"""Film FILTERS2: Filters expert mode - a tour, then when a fixed notch helps. The facts are FILTERS2.TXT's (its example:
centre 260 and cutoff 160 cover 160 to 360 Hz). Made with dev/video/filmkit.py.
18 Oct 2026: starts on the Rotorflight menu; livelier words; "In practice" after the tour; no closing line (Malcolm)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
f = Film('FILTERS2', 'Filters: expert mode', 'The rarely needed extras')
rf_route(f, 'Filters ...')
off = rfs('65.txt', '65_alloff')                                   # (every section off, Save hidden: as the page opens on many helicopters)
def notch1(centre, cutoff):
    """notch filter 1 switched on, with its two numbers typed: something changed, so Save shows"""
    return off + 'tn6.val=1\nvis ltn7,1\nvis tn7,1\nvis ltn8,1\nvis tn8,1\ntn7.txt="%d"\ntn8.txt="%d"\n' % (centre, cutoff) + SAVE_SHOWN
f.shot('fl', rfs('64.txt', '64_loaded'))
f.shot('p', off)
f.shot('n1', notch1(260, 160))
f.line('title', 'Filters, expert mode. A few extra filters, for the rare helicopter that needs them.')
f.line('fl', 'This is the Filters page. Press Next, for the expert ones.')
f.line('page', "This is the expert mode page. You'll rarely need it: the defaults suit most helicopters.")
f.line('dyn', "Dynamic cutoff makes the first page's lowpass cutoff follow the head speed, instead of staying fixed.")
f.line('lp2', "Lowpass filter two is a second lowpass, after the first. It's off on most helicopters.")
f.line('notch', 'And two notch filters. Each one takes out a narrow band of vibration, at one fixed frequency.')
f.line('enable', 'Every section has its own Enable. Green is on. Off hides its rows.')
f.line('prev', 'Previous goes back to the first page, with your changes kept.')
f.line('when', "So when does a notch help? When a vibration stays put, whatever the head speed. The R P M filter follows the head speed. A notch doesn't.")
f.line('range', 'Centre frequency is the middle of the notch, and Cutoff is where it starts. Centre two hundred and sixty, cutoff a hundred and sixty, covers a hundred and sixty to three hundred and sixty hertz.')
f.line('find', 'Find the frequency first, in a black box recording. And cure the cause if you can: every filter adds a little delay.')
f.line('save', "Save writes both filter pages. If you've changed the first page too, it asks first.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Filters ...', 'fl')
f.say('fl', 'Press Next.', after=0.3); f.tap(*at('FilterView', 'b2'), 'p')
f.say('page', 'Expert mode.')
f.point(*at('Filter2View', 'h1'), 'dyn', 'Dynamic cutoff.')
f.point(*at('Filter2View', 'h0'), 'lp2', 'Lowpass filter 2.')
f.point(*at('Filter2View', 'h2'), 'notch', 'Notch filters 1 and 2.')
f.point(*at('Filter2View', 'tn6'), 'enable', 'Enable: green is on.')
f.point(*at('Filter2View', 'b2'), 'prev', '< Previous.')
f.show('n1'); f.point(*at('Filter2View', 'h2'), 'when', 'Tip: a vibration that stays put.')
f.point(*at('Filter2View', 'tn7'), 'range', 'Tip: covers 160 to 360 Hz.')
f.cap = None; f.say('find', 'Tip: find it, cure it first.')
f.point(*at('Filter2View', 'b3'), 'save', 'Save.')
f.end(); f.finish()
