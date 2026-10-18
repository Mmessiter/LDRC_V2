#!/usr/bin/env python3
"""Film TAILWAG ("Fix a problem", 18 Oct 2026): the tail wags - the likely cause, and the cure on the transmitter's own
Rotorflight pages. Malcolm: "Let's include the likely cure for tail-wag and other common set up issues."
The facts: EASY.TXT (Tail: softer or sharper, P I D F of yaw times 0.7 to 1.3; small steps, one flight each; Save asks
first), PID.TXT (Yaw P; Save writes, reads back and stores), TXV1B RF_Easy.h (a slider step is 5 %: EzSlider; the box's
words, EzLive, a single number until the slider has moved; the question "Write to the flight controller?\r\nFeel (PIDs,
bank 1)"; "Writing the PIDs ..."; "Saved, and read back the same: Feel."). The gains are RAW 420 MCM's own, as the PID
and EASY films show them (scenario 40, RXV2 dev/snapshots raw420_snapshot_20260817: yaw 150 165 25 0); the box's numbers
are EzNudged's (floor(x + 0.5)); yaw P 150 -> 135 is the PID film's own ten per cent. The symptom is illus.py's tail_wag.
Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, knob
from common import rf_route, rf_route_play
from illus import Art

f = Film('TAILWAG', 'Tail wags', 'The likely cause, and the cure')
art = Art(f)
rf_route(f, 'Easy tuning ...')

# ---- Easy tuning (page 81): this model, bank 1, rate 1; the box while the finger is on the Tail slider (RF_Easy.h EzLive)
EASY = prefix('81.txt', '81_open', [('t11.txt="Havok"', 't11.txt="RAW 420 MCM"'), ('t14.txt="Bank 2"', 't14.txt="Bank 1"'),
                                    ('t8.txt="Rate 2"', 't8.txt="Rate 1"')])
def box(shade, cols):
    """the numbers box above the sliders, as the slider's press script shows it and EzLive fills it"""
    names = ('lvb', 'lv0', 'lv1', 'lv2', 'lv3', 'lv4')
    return (''.join('%s.bco=%d\n' % (n, shade) for n in names) + ''.join('vis %s,1\n' % n for n in names) +
            ''.join('lv%d.txt="%s"\n' % (i, c) for i, c in enumerate(cols)))
MOVED = 's4.val=5\nvis b3,1\n'
f.shot('e_open', EASY)
f.shot('e_touch', EASY + box(59323, ['Tail 0 %\\r\\nYaw', 'P\\r\\n150', 'I\\r\\n165', 'D\\r\\n25', 'F\\r\\n0']))
f.shot('e_5', EASY + MOVED + box(59323, ['Tail -5 %\\r\\nYaw', 'P\\r\\n150 -> 143', 'I\\r\\n165 -> 157', 'D\\r\\n25 -> 24', 'F\\r\\n0']))
f.shot('e_lift', EASY + MOVED)
f.shot('e_ask', EASY + MOVED + 'page PopupView\nDialog.txt="Write to the flight controller?\\r\\nFeel (PIDs, bank 1)"\n')
f.shot('e_busy', EASY + MOVED + 'vis busy,1\nbusy.txt="Writing the PIDs ..."\n')
f.shot('e_saved', EASY + 's4.val=5\nvis b3,0\nvis busy,1\nbusy.txt="Saved, and read back the same: Feel."\n')
f.shot('e_done', EASY + 's4.val=5\nvis b3,0\n')

# ---- PIDs (page 40): the same gains; Yaw P about ten per cent lower (150 -> 135, typed: the PID film shows the keypad), Save, sent
PID = prefix('40.txt', '40_open')
GREY = ''.join('n%d.pco=33840\n' % i for i in range(17))
BLACK = ''.join('n%d.pco=0\n' % i for i in range(17))
f.shot('p_open', PID)
f.shot('p_edit', PID + 'n8.val=135\nvis b3,1\n')
f.shot('p_send', PID + 'n8.val=135\n' + GREY + 'busy.txt="Sending edited PIDs ..."\nvis busy,1\nvis b2,0\nvis b3,0\n')
f.shot('p_done', PID + 'n8.val=135\n' + BLACK + 'vis busy,0\nvis b2,1\nvis b3,0\n')

f.line('title', "The tail wags. Here's the likely cause, and the cure.")
f.line('symptom', "Does your tail do this? A quick twitch, side to side, in the hover or in fast flight. That's tail wag.")
f.line('cause', "Most often, the tail's gain is simply too high. The gyro over-corrects: one way, then the other.")
f.line('mech', "But first, blades off: check the tail's linkage, belt and servo for play or binding.")
f.line('easy', "This is Easy tuning: the quickest cure. Slide Tail one step towards Softer.")
f.line('box', "While your finger's down, the box shows the tail's gains. Each one is five per cent lower.")
f.line('save', "Lift your finger, and press Save. It asks first: press OK.")
f.line('or', "Or, instead of the slider, exact numbers. This is the P I Ds page.")
f.line('yawp', "Touch Yaw P, and type a value about ten per cent lower.")
f.line('yawp2', "Here, a hundred and thirty five instead of a hundred and fifty. Then press Save.")
f.line('test', "Now fly one pack. Wag gone, but the tail feels soft, or drifts after a stop? Come back a little.")
f.line('piro', "A bounce only at the end of a pirouette? See Tail kicks or bounces.")
f.prepare()

f.begin(); f.say('title', after=1.2)
f.show(art.tail_wag(0)); f.anim(art.tail_wag, 3.0); f.say('symptom')
f.show(f.card('Likely cause', 'the tail gain is too high')); f.say('cause')
f.say('mech', 'Blades off: check the tail first.')
rf_route_play(f, 'Easy tuning ...', 'e_open')
f.say('easy', 'Tail: one step softer.', after=0.3)
k6, k5 = knob('EasyView', 's4', 6), knob('EasyView', 's4', 5)
f.glide(*k6); f.hold(0.3); f.press(); f.under('e_touch'); f.hold(0.6); f.slide([('e_5', k5[0])], k6[1], secs_each=0.7); f.hold(0.8)
f.say('box', 'Each tail gain 5 % lower.')
f.lift(); f.under('e_lift'); f.hold(0.4)
f.say('save', 'Save, then OK.', after=0.3)
f.tap(*at('EasyView', 'b3'), 'e_ask'); f.hold(0.4)
f.tap(*at('PopupView', 'b0'), 'e_busy'); f.cap = 'Writing ...'; f.hold(1.0); f.under('e_saved'); f.cap = 'Saved, and checked.'; f.hold(1.6)
f.show('p_open'); f.say('or', 'Or: the PIDs page.')
f.point(*at('PIDView', 'n8'), 'yawp', 'Yaw P: about 10 % lower.', after=0.2)
f.under('p_edit'); f.hold(0.4); f.point(*at('PIDView', 't3'), 'yawp2', 'Here: 150 becomes 135.', after=0.3)   # (off the box: the new value in sight)
f.tap(*at('PIDView', 'b3')); f.under('p_send'); f.hold(1.2); f.under('p_done'); f.hold(0.8)
f.show(f.card('Then fly it', 'one step, one flight')); f.say('test', 'Tip: one step, one flight.')
f.say('piro', 'See: Tail kicks or bounces.')
f.end(); f.finish()
