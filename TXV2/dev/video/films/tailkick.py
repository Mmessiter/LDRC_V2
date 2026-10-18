#!/usr/bin/env python3
"""Film TAILKICK ("Fix a problem", 18 Oct 2026): the tail kicks when the collective is pumped, or bounces back at the end of a
pirouette - the likely causes, and the cures on PID + (advanced). Malcolm: "Let's include the likely cure for tail-wag and
other common set up issues."
The facts: PID_A.TXT ("Yaw push from cyclic and from collective (cyclic and collective FF gain): tail added as that load
rises, before the nose can swing. Collective is the main one."; "Yaw stop firmness CW and CCW (CW and CCW stop gain): how
firmly a yaw stops when you centre the stick. Raise the side that wags or bounces."; "Most models fly well on Rotorflight's
own values. Change one only when you know why."; the keypad shows the name - check it; Save appears once a value is touched,
writes, reads back, stores). The keypad's names are the page's own (sd/hmi/pages/7.json: "Yaw push from collective load ",
"Yaw stop firmness, anticlockwise "); the values are scenario 7's (collective push 60, stops CW 120 / CCW 80); the save
is RF_PID_Advanced.h's ("Sending edited advanced PIDs ..."). The symptoms are illus.py's tail_kick and tail_bounce.
Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, _page
from common import rf_route, rf_route_play, keypad_shots, KEY
from illus import Art

f = Film('TAILKICK', 'Tail kicks or bounces', 'The likely cause, and the cure')
art = Art(f)
rf_route(f, 'PIDs ...')
def cid(page, name): return next(c['i'] for c in _page(page)['comps'] if c['n'] == name)

f.shot('pid', prefix('40.txt', '40_open'))
A = prefix('7.txt', '7_open')                                     # (PID + for bank 1: collective push 60, stops CW 120, CCW 80)
BOXES = ['sw0'] + ['t%d' % i for i in range(1, 26)]
GREY = ''.join('%s.pco=33840\n' % n for n in BOXES); BLACK = ''.join('%s.pco=0\n' % n for n in BOXES)
EDIT1 = 't23.txt="65"\nvis b3,1\n'; EDIT2 = EDIT1 + 't20.txt="90"\n'
f.shot('a', A)
keypad_shots(f, A, 7, 't23', cid('PID_A_View', 't23'), ['60', '6', '65'])
f.shot('a1', A + EDIT1)
f.shot('a2', A + EDIT2)
f.shot('a_send', A + EDIT2 + GREY + 'busy.txt="Sending edited advanced PIDs ..."\nvis busy,1\nvis b3,0\n')
f.shot('a_done', A + EDIT2 + BLACK + 'vis busy,0\nvis b3,0\n')

def key(f, k, shot):
    """a keypad key, pressed a little more briskly than a page's button (the pad redraws only its box)"""
    f.glide(*KEY[k], secs=0.6); f.hold(0.2); f.press(); f.under(shot); f.lift(); f.hold(0.3)

f.line('title', "The tail kicks, or bounces. Here's the likely cause, and the cure.")
f.line('kick', "First kind: you pump the collective, or climb hard, and the nose kicks round, before the tail can catch up.")
f.line('bounce', "Second kind: you stop a pirouette, and the tail bounces back. That's about how firmly the tail stops.")
f.line('mech', "Either way, blades off, check first that the tail belt and linkage don't slip or bind.")
f.line('pid', "This is the P I Ds page. Press P I D plus.")
f.line('page', "This is P I D plus: both cures are here. Change one thing at a time.")
f.line('push', "For the kick: Yaw push from collective. It adds tail as the collective rises, before the nose can swing. Raise it a little.")
f.line('pad', "The keypad names the value you're changing. Check it: this page is crowded. Here, sixty becomes sixty five.")
f.line('stop', "For the bounce: Yaw stop firmness. There's one for each way the tail turns: clockwise, and anticlockwise.")
f.line('stop2', "Raise the side that bounces. Here, anticlockwise goes from eighty to ninety.")
f.line('save', "Then press Save: it's written, checked, and stored.")
f.line('test', "Small steps, one flight each. Too far, and it can kick or bounce the other way: then come back a little.")
f.prepare()

f.begin(); f.say('title', after=1.2)
f.show(art.tail_kick(0), look=0.3); f.anim(art.tail_kick, 3.0); f.say('kick')
f.show(art.tail_bounce(0), look=0.3); f.anim(art.tail_bounce, 3.0); f.say('bounce')
f.say('mech', 'Blades off: check the tail first.')
rf_route_play(f, 'PIDs ...', 'pid')
f.say('pid', 'Press PID +.', after=0.3); f.tap(*at('PIDView', 'b2'), 'a')
f.say('page', 'PID + (advanced).')
f.point(*at('PID_A_View', 't51'), 'push', 'Kick: Yaw push from collective.', after=0.3)
f.tap(*at('PID_A_View', 't23'), 'kp0'); f.say('pad', 'Check the name: then 60 -> 65.', after=0.3)
key(f, 'Delete', 'kp1'); key(f, '5', 'kp2'); f.tap(*KEY['OK'], 'a1')
f.point(*at('PID_A_View', 't47'), 'stop', 'Bounce: Yaw stop firmness.')
f.point(*at('PID_A_View', 't48'), 'stop2', 'Tip: raise the side that bounces.', after=0.2)
f.under('a2'); f.hold(0.8)
f.cap = None; f.say('save', 'Save: written, checked, stored.', after=0.3)
f.tap(*at('PID_A_View', 'b3')); f.under('a_send'); f.hold(1.2); f.under('a_done'); f.hold(0.8)
f.show(f.card('Then fly it', 'one step, one flight')); f.say('test', 'Tip: small steps, one flight each.')
f.end(); f.finish()
