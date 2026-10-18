#!/usr/bin/env python3
"""Film EASY: Easy tuning from the transmitter (Rotorflight) - a tour of the sliders, then the cures pilots use it for: a
wobble (Cyclic a step softer, done and saved), a sluggish model (a step sharper), a wagging tail (Tail a step softer).
The facts are EASY.TXT's; the route is the firmware's (Rotorflight menu > Easy tuning: RF_Easy.h StartEasyView needs the
model connected). The numbers are TXV1B RF_Easy.h's: a Cyclic step is 5 % (s3 0..12, the centre 6), the box's words are
EzLive's, its sums EzNudged's (floor(x + 0.5)) on RAW 420 MCM's own PIDs (scenario 40, RXV2 dev/snapshots
raw420_snapshot_20260817: roll 50 100 20 100, pitch 130 140 50 100); Save asks first (SaveEasy: "Write to the flight
controller?" / "Feel (PIDs, bank 1)") and ends "Saved, and read back the same: Feel." (EzFinish).
Made with dev/video/filmkit.py.
18 Oct 2026: starts on the Rotorflight menu; livelier words; "In practice" after the tour; no closing line (Malcolm)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, knob
from common import rf_route, rf_route_play
from illus import Art

f = Film('EASY', 'Easy tuning', 'Rotorflight, from the LDRC transmitter')
art = Art(f)
def wobble(t, title='It wobbles'):
    """illus.py's Art.wobble, the helicopter drawn smaller (at 1.5 its rotor runs off both sides of the transmitter's
    screen): a fast roll wobble, from the front"""
    import math
    im, d = art._canvas()
    roll = 8.0 * math.sin(2 * math.pi * 3.6 * t) * min(1.0, t / 0.4)
    art.shadow(d, 0, 150, 200); art.heli_front(d, 0, 40, roll=roll, s=1.0)
    art.title(d, title)
    return art._done(im)
rf_route(f, 'Easy tuning ...')
EASY = prefix('81.txt', '81_open', [('t11.txt="Havok"', 't11.txt="RAW 420 MCM"'), ('t14.txt="Bank 2"', 't14.txt="Bank 1"'),
                                    ('t8.txt="Rate 2"', 't8.txt="Rate 1"')])
def box(cols, shade=59323):
    """the numbers box above the sliders, as the slider's press script shows it and EzLive fills it"""
    names = ('lvb', 'lv0', 'lv1', 'lv2', 'lv3', 'lv4')
    return (''.join('%s.bco=%d\n' % (n, shade) for n in names) + ''.join('vis %s,1\n' % n for n in names) +
            ''.join('lv%d.txt="%s"\n' % (i, c) for i, c in enumerate(cols)))
SOFT = 's3.val=5\nvis b3,1\n'                                         # (Cyclic one step softer: -5 %)
f.shot('e_open', EASY)
f.shot('e_touch', EASY + box(['Cyclic 0 %\\r\\nRoll\\r\\nPitch', 'P\\r\\n50\\r\\n130', 'I\\r\\n100\\r\\n140', 'D\\r\\n20\\r\\n50', 'F\\r\\n100\\r\\n100']))
f.shot('e_5', EASY + SOFT + box(['Cyclic -5 %\\r\\nRoll\\r\\nPitch', 'P\\r\\n50 -> 48\\r\\n130 -> 124', 'I\\r\\n100 -> 95\\r\\n140 -> 133',
                                  'D\\r\\n20 -> 19\\r\\n50 -> 48', 'F\\r\\n100 -> 95\\r\\n100 -> 95']))
f.shot('e_lift', EASY + SOFT)
f.shot('e_ask', EASY + SOFT + 'page PopupView\nDialog.txt="Write to the flight controller?\\r\\nFeel (PIDs, bank 1)"\n')
f.shot('e_busy', EASY + SOFT + 'vis busy,1\nbusy.txt="Writing the PIDs ..."\n')
f.shot('e_saved', EASY + 's3.val=5\nvis b3,0\nvis busy,1\nbusy.txt="Saved, and read back the same: Feel."\n')
f.shot('e_after', EASY + 's3.val=5\nvis b3,0\n')                    # (the word gone: the slider stays where it was left)

f.line('title', "Easy tuning. Make your helicopter fly the way you like, without a single number.")
f.line('page', "This is Easy tuning: the phone app's sliders, right here on the transmitter. Each one moves the real numbers on the Governor, Rates or P I Ds page.")
f.line('needs', "It needs the model connected, with the safety on. And don't worry: nothing changes until you press Save.")
f.line('start', "Start: how gently or fiercely the head spools up. It's the same for every bank. Saving it restarts the flight controller, so take the blades off first.")
f.line('agility', 'Agility: how fast it rolls, flips and pirouettes at full stick.')
f.line('feel', 'Stick feel: the expo. A soft centre to the left, more direct to the right.')
f.line('cyclic', 'Cyclic and Tail: softer or sharper. They scale the P I D gains of the cyclic, or of the tail, together.')
f.line('centre', "Each slider's centre is your model's numbers at its last backup. So after a save, the slider shows how far you've come.")
f.line('spool', 'The switch at the bottom is P I D spool-up: a smoother spool-up that ends exactly on your head speed.')
f.line('ok', 'OK goes back to the Rotorflight menu.')
f.line('wobble', "Now, the real use. Does your model wobble or shake, like this? Try the cyclic one step softer.")
f.line('drag', 'Put your finger on the Cyclic slider, and move it one step to the left.')
f.line('box', "While your finger's down, this box shows what Save would write: every cyclic gain, five per cent lower.")
f.line('save', "Lift your finger, and press Save. It asks first, so you can check what's going.")
f.line('saved', "Written, read back to check, and stored. Now go and fly it.")
f.line('sharp', "Is it the opposite: sluggish, drifting, or a bit mushy? Then go a step towards Sharper.")
f.line('tail', "And if the tail wags, with a fast twitch from side to side, move Tail a step towards Softer.")
f.line('steps', "Whatever you try, take small steps: one step, then one flight. You'll soon find the sweet spot.")
f.prepare()

f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Easy tuning ...', 'e_open')
f.say('page', 'Easy tuning.')
f.cap = None; f.say('needs', 'Nothing changes until Save.')
f.point(*at('EasyView', 'lS'), 'start', 'Start: blades off to save it.')
f.point(*at('EasyView', 'lA'), 'agility', 'Agility.')
f.point(*at('EasyView', 'lE'), 'feel', 'Stick feel.')
f.point(*at('EasyView', 'lC'), 'cyclic', 'Cyclic and Tail.')
f.point(*knob('EasyView', 's3', 6), 'centre', 'The centre: your last backup.')
f.point(*at('EasyView', 'sw'), 'spool', 'PID spool-up.')
f.point(*at('EasyView', 'b1'), 'ok', 'OK.')
# ---- in practice: a wobble, cured and saved
f.show(wobble(0)); f.anim(wobble, 3.0); f.say('wobble', 'Tip: wobbles? A step softer.')
f.show('e_open'); f.say('drag', 'Cyclic: one step left.', after=0.3)
k6, k5 = knob('EasyView', 's3', 6), knob('EasyView', 's3', 5)
f.glide(*k6); f.hold(0.3); f.press(); f.under('e_touch'); f.hold(0.6); f.slide([('e_5', k5[0])], k6[1], secs_each=0.7); f.hold(0.8)
f.say('box', 'Each cyclic gain 5 % lower.')
f.say('save', 'Lift, then Save.', after=0.3)
f.lift(); f.under('e_lift'); f.hold(0.6); f.tap(*at('EasyView', 'b3'), 'e_ask'); f.cap = 'It asks first.'; f.hold(0.8)
f.tap(*at('PopupView', 'b0'), 'e_busy'); f.hold(0.6); f.under('e_saved'); f.hold(0.4)
f.say('saved', 'Saved, and checked.', after=1.0)
f.under('e_after')
f.point(*at('EasyView', 'e3R'), 'sharp', 'Tip: sluggish? A step sharper.')
f.point(*at('EasyView', 'e4L'), 'tail', 'Tip: tail wag? Tail softer.')
f.cap = None; f.say('steps', 'Tip: one step, one flight.')
f.end(); f.finish()
