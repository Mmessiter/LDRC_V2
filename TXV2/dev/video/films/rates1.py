#!/usr/bin/env python3
"""Film RATES1: Rotorflight's rates - a tour, then three real uses: a gentle rate for practice and a livelier one for sport
on the Rates switch, the Curves page to see what the numbers do before you fly, and a little less collective for gentler
climbs and descents. The facts are RATES1.TXT's; the numbers are RAW 420 MCM's own (scenario 1, RXV2 dev/snapshots
raw420_snapshot_20260817: 6 - ROTORFLIGHT, roll and pitch 160, yaw 400, collective 6.00); rate 2's livelier numbers are an
example. The Curves page is drawn by the Teensy's own code: CURVES below are the commands RatesCurvePoll sends for these
numbers (TXV1B dev/test_rates/test_rates.py run with RC_SCENARIO and its Havok bytes swapped for RAW 420 MCM's
{6, 32, 20, 20, 32, 20, 20, 80, 20, 20, 48, 48, 0}; the legend is RatesCurvesPageBack's for them), zlib + base64.
Made with dev/video/filmkit.py.
18 Oct 2026: starts on the Rotorflight menu; livelier words; "In practice" after the tour; no closing line (Malcolm)."""
import base64, os, sys, zlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play
f = Film('RATES1', 'Rates (Rotorflight)', 'How fast the sticks turn the helicopter')
rf_route(f, 'Rates ...')
CURVES = zlib.decompress(base64.b64decode(''.join('''
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
'''.split()))).decode()
opn = prefix('1.txt', '1_open')
f.shot('p', opn)
f.shot('sport', opn + 't9.txt="Rate 2"\ntn0.txt="320"\ntn3.txt="320"\ntn6.txt="500"\n')   # (an example sport rate)
f.shot('curves', 'Screen_Background=8\n@model 1\npage RatesCurveView\nt9.txt="Rate 1"\nt11.txt="RAW 420 MCM"\nlg0.txt="Roll 160 deg/s"\n'
       'lg1.txt="Pitch 160 deg/s"\nlg2.txt="Yaw 400 deg/s"\nlg3.txt="Collective 6.0 deg"\ntt.txt="6 - ROTORFLIGHT"\n' + CURVES)
f.shot('coll', opn + 'tn9.txt="5.00"\nvis b3,1\n')                  # (a little less collective, typed: Save shows)
f.line('title', 'Rates. How fast the sticks turn your helicopter, and how much pitch the collective gives.')
f.line('page', 'This is the Rates page, for the rate shown at the top left.')
f.line('switch', 'The Rates switch chooses the rate, or the bank switch, if Link rates and banks is on. Wait a moment while it loads.')
f.line('type', 'The columns follow the rates type, shown on this line.')
f.line('numbers', 'Roll, pitch and yaw are in degrees per second, which the flight controller will seek. Collective is degrees of blade pitch.')
f.line('cols', 'With this type, Rate is how fast it turns at full stick. Shape and Expo set the feel around the centre.')
f.line('dyn', 'Dynamics has how the model follows the stick.')
f.line('ok', 'OK goes back to the Rotorflight menu.')
f.line('gentle', "Here's a great way to use rates. Keep a gentle one for practice, like rate one here.")
f.line('sport', "And a livelier one for sport, like this rate two. One flick of the switch, and the whole feel changes.")
f.line('curves', "Not sure what your numbers mean? Press Curves.")
f.line('draw', "This is the Rates curves page. It draws your numbers with Rotorflight's own sums. Across: the stick, from one end to the other. Up: how fast the model turns.")
f.line('draw2', 'The boxes on the left give each one at full stick. So you see the feel before you fly.')
f.line('back', 'OK goes back to the numbers.')
f.line('coll', 'Climbs and descents a bit too lively? A little less collective pitch makes them gentler.')
f.line('save', "Touch a box, type the new value, and press Save. Save before you move the switch, or the change is lost.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Rates ...', 'p')
f.say('page', 'Rates.')
f.point(*at('RatesView', 't9'), 'switch', 'The rate.')
f.point(*at('RatesView', 't10'), 'type', 'Rates type.')
f.point(*at('RatesView', 't1'), 'numbers', 'Degrees per second.')
f.point(*at('RatesView', 't5'), 'cols', 'Rate; Shape and Expo.')
f.point(*at('RatesView', 'b2'), 'dyn', 'Dynamics ...')
f.point(*at('RatesView', 'b1'), 'ok', 'OK.')
# ---- in practice
f.point(*at('RatesView', 't5'), 'gentle', 'Tip: a gentle rate to practise.')
f.show('sport'); f.point(*at('RatesView', 't5'), 'sport', 'Tip: a livelier one for sport.')
f.show('p'); f.point(*at('RatesView', 'b4'), 'curves', 'Curves ...', after=0.3)
f.tap(*at('RatesView', 'b4'), 'curves'); f.say('draw', 'Tip: see it before you fly.')
f.point(*at('RatesCurveView', 'lg0'), 'draw2', 'At full stick.')
f.point(*at('RatesCurveView', 'b1'), 'back', 'OK: back to the numbers.', after=0.3)
f.tap(*at('RatesCurveView', 'b1'), 'p')
f.point(*at('RatesView', 't8'), 'coll', 'Tip: less collective, gentler.', after=0.3)
f.under('coll'); f.hold(0.8)
f.point(*at('RatesView', 'b3'), 'save', 'Type, then Save.')
f.end(); f.finish()
