#!/usr/bin/env python3
"""Film FLIPBNC ("Fix a problem", 18 Oct 2026): it bounces back at the end of a flip or roll - the likely cause (the I term
winding up during the move), and the cure on PID + (advanced). Malcolm: "Let's include the likely cure for tail-wag and
other common set up issues."
The facts: PID_A.TXT ("wind-up relief (I-term relax cutoff): holds back the I term in fast moves, so it cannot snap back.
Lower: more relief."; the keypad shows the name - check it; Save appears once a value is touched, writes, reads back,
stores; "Most models fly well on Rotorflight's own values. Change one only when you know why."), PID.TXT ("D: damping,
against overshoot."). The values are scenario 7's (roll wind-up relief 15, pitch 12); the keypad's name is the page's own
("Pitch wind-up relief (I-term relax) "); the save is RF_PID_Advanced.h's ("Sending edited advanced PIDs ..."). The
symptom is illus.py's flip_bounce. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, _page
from common import rf_route, rf_route_play, keypad_shots, KEY
from illus import Art

f = Film('FLIPBNC', 'Bounces after a flip', 'The likely cause, and the cure')
art = Art(f)
rf_route(f, 'PIDs ...')
def cid(page, name): return next(c['i'] for c in _page(page)['comps'] if c['n'] == name)
def key(f, k, shot):
    """a keypad key, pressed a little more briskly than a page's button (the pad redraws only its box)"""
    f.glide(*KEY[k], secs=0.6); f.hold(0.2); f.press(); f.under(shot); f.lift(); f.hold(0.3)

f.shot('pid', prefix('40.txt', '40_open'))
A = prefix('7.txt', '7_open')                                     # (PID + for bank 1: roll wind-up relief 15, pitch 12)
BOXES = ['sw0'] + ['t%d' % i for i in range(1, 26)]
GREY = ''.join('%s.pco=33840\n' % n for n in BOXES); BLACK = ''.join('%s.pco=0\n' % n for n in BOXES)
EDIT = 't3.txt="10"\nvis b3,1\n'
f.shot('a', A)
keypad_shots(f, A, 7, 't3', cid('PID_A_View', 't3'), ['12', '1', '10'])
f.shot('a1', A + EDIT)
f.shot('a_send', A + EDIT + GREY + 'busy.txt="Sending edited advanced PIDs ..."\nvis busy,1\nvis b3,0\n')
f.shot('a_done', A + EDIT + BLACK + 'vis busy,0\nvis b3,0\n')

f.line('title', "It bounces back after a flip. Here's the likely cause, and the cure.")
f.line('symptom', "At the end of a fast flip or roll, does it bounce back a little, instead of stopping clean?")
f.line('cause', "Usually, the I term winds up during the move, then springs it back at the end.")
f.line('pid', "This is the P I Ds page. Press P I D plus.")
f.line('page', "This is P I D plus. Most models fly well on Rotorflight's own values, so change one thing at a time.")
f.line('relief', "Wind-up relief holds the I term back in fast moves, so it can't snap back. A lower number gives more relief.")
f.line('axis', "A flip is pitch, a roll is roll. Lower the one that bounces, a little.")
f.line('pad', "The keypad names the value: check it, as this page is crowded. Here, pitch goes from twelve to ten.")
f.line('save', "Then press Save. It's written, read back to check, and stored.")
f.line('d', "Or does it overshoot past the stop, rather than bounce back? Then a little more D, on the P I Ds page, may help. D is the damping.")
f.line('test', "Small steps, one flight each, and try it high up.")
f.prepare()

f.begin(); f.say('title', after=1.2)
f.show(art.flip_bounce(0), look=0.3); f.anim(art.flip_bounce, 3.0); f.say('symptom')
f.show(f.card('Likely cause', 'the I term winds up')); f.say('cause')
rf_route_play(f, 'PIDs ...', 'pid')
f.say('pid', 'Press PID +.', after=0.3); f.tap(*at('PIDView', 'b2'), 'a')
f.say('page', 'PID + (advanced).')
f.point(*at('PID_A_View', 't30'), 'relief', 'Wind-up relief: lower = more.')
f.point(*at('PID_A_View', 't31'), 'axis', 'A flip: pitch. A roll: roll.', after=0.3)
f.tap(*at('PID_A_View', 't3'), 'kp0'); f.say('pad', 'Check the name: then 12 -> 10.', after=0.3)
key(f, 'Delete', 'kp1'); key(f, '0', 'kp2'); f.tap(*KEY['OK'], 'a1')
f.cap = None; f.say('save', 'Save: written, checked, stored.', after=0.3)
f.tap(*at('PID_A_View', 'b3')); f.under('a_send'); f.hold(1.2); f.under('a_done'); f.hold(0.8)
f.show(f.card('Overshoots instead?', 'a little more D, on the PIDs page')); f.say('d')
f.show(f.card('Then fly it', 'one step, one flight')); f.say('test', 'Tip: small steps, high up.')
f.end(); f.finish()
