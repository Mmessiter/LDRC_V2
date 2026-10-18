#!/usr/bin/env python3
"""Film RATES_A: Rates: dynamics - a tour, then the feel it sets: a longer response time for a smooth, scale-like feel, a
short one (or none) for crisp aerobatics. The facts are RATES_A.TXT's; the values are scenario 42's (RAW 420 MCM, rate 1:
every response time nought); the longer one (60 ms on roll, pitch and yaw) is an example. Made with dev/video/filmkit.py.
18 Oct 2026: starts on the Rotorflight menu, through the Rates page; livelier words; "In practice" after the tour; no
closing line (Malcolm)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play
from illus import Art
f = Film('RATES_A', 'Rates: dynamics', 'How the model follows the stick')
art = Art(f)
rf_route(f, 'Rates ...')
f.shot('r', prefix('1.txt', '1_open'))
opn = prefix('42.txt', '42_open')
f.shot('p', opn)
f.shot('scale', opn + 'n0.val=60\nn1.val=60\nn2.val=60\nvis b3,1\n')     # (a longer response time, typed: Save shows)
f.line('title', 'Rates dynamics. Not how fast it turns, but how it gets there.')
f.line('r', 'This is the Rates page. Press Dynamics.')
f.line('page', "This is the Dynamics page, for the rate shown at the top left. It's the phone app's Dynamics card.")
f.line('resp', 'Response time, in milliseconds: how long the model takes to reach the rate the stick asks for. Higher feels softer. Nought is off.')
f.line('sharp', 'Stick sharpening: extra response on quick stick moves. Sharpening smoothing is the filter on it: lower is smoother.')
f.line('yaw', 'And for yaw only: fast-move headroom, stick-centre quieting, and its smoothing.')
f.line('ok', "OK leaves the page, and asks first if a change isn't saved.")
f.line('feel', "So, how do you want it to feel? Snappy and instant, or smooth and gentle? Response time is the one that decides.")
f.line('scale', 'For a smooth, scale-like feel, try a longer response time on roll, pitch and yaw. The model eases into each move, like a full-size helicopter.')
f.line('save', 'Touch a box, type the new value, and press Save. Save before you move the Rates or bank switch.')
f.line('crisp', "For crisp aerobatics, keep it short, or at nought, and the model follows the stick at once.")
f.line('steps', "Whichever you like, change it a little at a time, and fly between changes.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Rates ...', 'r')
f.say('r', 'Press Dynamics.', after=0.3); f.tap(*at('RatesView', 'b2'), 'p')
f.say('page', 'Rates: dynamics.')
f.point(*at('Rates_A_View', 't1'), 'resp', 'Response time.')
f.point(*at('Rates_A_View', 't2'), 'sharp', 'Stick sharpening.')
f.point(*at('Rates_A_View', 't10'), 'yaw', 'Yaw only.')
f.point(*at('Rates_A_View', 'b1'), 'ok', 'OK.')
# ---- in practice
f.show(art.feel(0)); f.anim(art.feel, 2.3); f.say('feel', 'Snappy, or smooth?')
f.show('scale'); f.point(*at('Rates_A_View', 't1'), 'scale', 'Tip: smooth, scale feel? Longer.')
f.point(*at('Rates_A_View', 'b3'), 'save', 'Type, then Save.')
f.show('p'); f.point(*at('Rates_A_View', 't1'), 'crisp', 'Tip: crisp aerobatics? Short.')
f.cap = None; f.say('steps', 'Tip: a little at a time.')
f.end(); f.finish()
