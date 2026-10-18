#!/usr/bin/env python3
"""Film TRAVEL3: Travel extents, the tail - a tour, then real uses: which way the tail moves (Rudder reversed), a tail that
blows out (more tail travel, if nothing binds), and tail wag (the linkage, then the yaw gain: the PIDs animation). The facts
are TRAVEL3.TXT's; the tail-wag cure is the PIDs film's (PID.TXT). Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the setup pages, real uses, "the likely cure for tail-wag", livelier words, no closing line):
starts on the Rotorflight menu, then Travel extents, Next, Next."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
from illus import Art
f = Film('TRAVEL3', 'Travel extents: tail', 'How the rudder stick reaches the tail')
art = Art(f)
rf_route(f, 'Travel extents ...')
p3 = rfs('66.txt', '66_vp')                          # (variable pitch tail, travel 45.0 each way)
f.shot('t', rfs('62.txt', '62_loaded')); f.shot('t2', rfs('63.txt', '63_loaded')); f.shot('p', p3); f.shot('e', p3 + SAVE_SHOWN)
f.shot('more', p3 + 'tn3.txt="50.0"\ntn4.txt="50.0"\n' + SAVE_SHOWN)   # (the tips point at a row's name: its value in sight)
f.line('title', 'Travel extents, tail. How the rudder stick reaches the tail.')
f.line('t', 'This is the first Travel extents page. Press Next.')
f.line('t2', 'This is the swash page. Press Next again.')
f.line('page', 'And this is Travel extents, tail: how the rudder stick reaches the tail.')
f.line('type', 'Tail rotor type shows what the flight controller has. To change it, use Settings, then First time basics. The rows below change with it.')
f.line('reversed', 'Rudder reversed: green is reversed.')
f.line('trim', 'Tail centre trim: the tail blade angle with the rudder stick centred.')
f.line('gain', 'Tail gain: how much of a full stick reaches the tail.')
f.line('travel', 'Tail travel, stick right and stick left: the most blade angle each way.')
f.line('save', "Save appears once something's changed. It writes all four Travel extents pages, after a question.")
f.line('next', 'Next goes on to the bench measure.')
f.line('revtip', 'Check the tail on the bench, blades off. Move the rudder stick, and watch the tail blades: they must push the nose the way you steer. Backwards? Tap Rudder reversed.')
f.line('blowtip', 'Tail blows out in fast pirouettes, or hard climbs? It may be short of travel. Raise Tail travel a little, as long as nothing binds at full stick.')
f.line('wagtip', "Tail wags from side to side? First, blades off, check the tail linkage moves freely, with no slop. Then it's usually the yaw gain, a little too high: the P I Ds animation shows the cure.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Travel extents ...', 't')
f.say('t', 'Press Next.', after=0.3); f.tap(*at('TravelView', 'b2'), 't2')
f.say('t2', 'Press Next again.', after=0.3); f.tap(*at('Travel2View', 'b2'), 'p')
f.say('page', 'Travel extents: tail.')
f.point(*at('Travel3View', 'i0'), 'type', 'Tail rotor type.')
f.point(*at('Travel3View', 'tn0'), 'reversed', 'Rudder reversed.')
f.point(*at('Travel3View', 'tn1'), 'trim', 'Tail centre trim.')
f.point(*at('Travel3View', 'tn2'), 'gain', 'Tail gain.')
f.point(*at('Travel3View', 'tn3'), 'travel', 'Tail travel, each way.')
f.under('e'); f.hold(0.6); f.point(*at('Travel3View', 'b3'), 'save', 'Save: all four pages.')
f.point(*at('Travel3View', 'b2'), 'next', 'Next >: the bench measure.')
f.show('p'); f.point(*at('Travel3View', 'ltn0'), 'revtip', "Tip: check the tail's way.")
f.show('more'); f.point(*at('Travel3View', 'ltn3'), 'blowtip', 'Tip: blow-outs? More travel.')
f.show(art.tail_wag(0)); f.anim(art.tail_wag, 2.5); f.say('wagtip', 'Tip: tail wag? The yaw gain.')
f.end(); f.finish()
