#!/usr/bin/env python3
"""Film BUZZ ("Fix a problem", 18 Oct 2026): servos buzz or run hot - the likely causes (the D term passing noise to the
servos, an update rate above the servo's specification, a binding linkage, vibration), and the cures on PID + (advanced) and
the Servos page. Malcolm: "Let's include the likely cure for tail-wag and other common set up issues."
The facts: PID_A.TXT ("D smoothing (D-term cutoff, Hz): lower it if servos buzz or run hot."; the keypad shows the name -
check it; Save writes, reads back, stores), SERVOS.TXT ("Update rate (Hz): how often the servo is sent a new position (25 to
5000). Never more than the servo's specification allows."), FILTERS.TXT (the R P M filter, the main defence against
vibration). The values are scenario 7's (roll and pitch D smoothing 25) and scenario 60's (servo 1 of 4, swashplate, 333 Hz);
the keypad's name is the page's own ("Roll D smoothing (D-term cutoff) "); the save is RF_PID_Advanced.h's. The symptom is
illus.py's buzz. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, _page
from common import rf_route, rf_route_play, keypad_shots, KEY, rfs
from illus import Art

f = Film('BUZZ', 'Servos buzz or run hot', 'The likely cause, and the cure')
art = Art(f)
rf_route(f, 'PIDs ...')
def cid(page, name): return next(c['i'] for c in _page(page)['comps'] if c['n'] == name)
def key(f, k, shot):
    """a keypad key, pressed a little more briskly than a page's button (the pad redraws only its box)"""
    f.glide(*KEY[k], secs=0.6); f.hold(0.2); f.press(); f.under(shot); f.lift(); f.hold(0.3)

f.shot('pid', prefix('40.txt', '40_open'))
A = prefix('7.txt', '7_open')                                     # (PID + for bank 1: roll and pitch D smoothing 25)
BOXES = ['sw0'] + ['t%d' % i for i in range(1, 26)]
GREY = ''.join('%s.pco=33840\n' % n for n in BOXES); BLACK = ''.join('%s.pco=0\n' % n for n in BOXES)
EDIT1 = 't13.txt="20"\nvis b3,1\n'; EDIT2 = EDIT1 + 't14.txt="20"\n'
f.shot('a', A)
keypad_shots(f, A, 7, 't13', cid('PID_A_View', 't13'), ['25', '2', '20'])
f.shot('a1', A + EDIT1)
f.shot('a2', A + EDIT2)
f.shot('a_send', A + EDIT2 + GREY + 'busy.txt="Sending edited advanced PIDs ..."\nvis busy,1\nvis b3,0\n')
f.shot('a_done', A + EDIT2 + BLACK + 'vis busy,0\nvis b3,0\n')
f.shot('servo', rfs('60.txt', '60_loaded'))                      # (servo 1 of 4, swashplate: update rate 333 Hz)

f.line('title', "Servos buzz, or run hot. Here's the likely cause, and the cure.")
f.line('symptom', "Servos buzzing or chattering, even in the hover? Or warm to the touch after a flight?")
f.line('cause', "Most often, the D term passes vibration noise on to the servos. Or a servo is updated faster than it should be, or a linkage binds.")
f.line('mech', "First, blades off: move the swash gently by hand. It should move freely, with no tight spots.")
f.line('pid', "This is the P I Ds page. Press P I D plus.")
f.line('page', "This is P I D plus. Change one thing at a time.")
f.line('dsm', "D smoothing filters the D term before it reaches the servos. Lower it a little, if servos buzz or run hot.")
f.line('pad', "The keypad names the value: check it. Here, roll goes from twenty five to twenty.")
f.line('pitch', "Pitch the same, then press Save.")
f.line('servo', "Next, this is the Servos page, from the Rotorflight menu. Check each servo's Update rate is within its specification. Its instructions will say.")
f.line('vib', "And if vibration is the cause, see It wobbles or shakes.")
f.line('test', "One change, one flight. Feel the servos after landing: warm is fine, too hot to hold is not.")
f.prepare()

f.begin(); f.say('title', after=1.2)
f.show(art.buzz(0), look=0.3); f.anim(art.buzz, 3.0); f.say('symptom')
f.show(f.card('Likely causes', 'D term noise, update rate, binding')); f.say('cause')
f.say('mech', 'Blades off: is the swash free?')
rf_route_play(f, 'PIDs ...', 'pid')
f.say('pid', 'Press PID +.', after=0.3); f.tap(*at('PIDView', 'b2'), 'a')
f.say('page', 'PID + (advanced).')
f.point(*at('PID_A_View', 't41'), 'dsm', 'D smoothing: a little lower.', after=0.3)
f.tap(*at('PID_A_View', 't13'), 'kp0'); f.say('pad', 'Check the name: then 25 -> 20.', after=0.3)
key(f, 'Delete', 'kp1'); key(f, '0', 'kp2'); f.tap(*KEY['OK'], 'a1')
f.point(*at('PID_A_View', 't42'), 'pitch', 'Pitch the same, then Save.', after=0.2)
f.under('a2'); f.hold(0.6)
f.tap(*at('PID_A_View', 'b3')); f.under('a_send'); f.hold(1.2); f.under('a_done'); f.hold(0.8)
f.show('servo'); f.point(*at('ServoView', 'ltn5'), 'servo', "Update rate: the servo's spec.")
f.cap = None; f.say('vib', 'See: Wobbles or shakes.')
f.show(f.card('Then fly it', 'one step, one flight')); f.say('test', 'Tip: feel the servos after landing.')
f.end(); f.finish()
