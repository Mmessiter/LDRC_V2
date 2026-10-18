#!/usr/bin/env python3
"""Film WOBBLE ("Fix a problem", 18 Oct 2026): it wobbles or shakes - the likely causes (cyclic gains too high, or
vibration), and the cures on the transmitter's own Rotorflight pages. Malcolm: "Let's include the likely cure for tail-wag
and other common set up issues."
The facts: EASY.TXT ("Wobbles or shakes: softer."; Cyclic: P, I, D and F of roll and pitch times 0.7 to 1.3; small steps,
one flight each; Save asks first), PID.TXT ("P: how hard it corrects. Too much gives a fast wobble."), FILTERS.TXT (the R P M
filter "The main filter on a helicopter"; it needs a head-speed signal, E S C telemetry or an R P M sensor; Enable, green =
on), PID_A.TXT (D smoothing: "lower it if servos buzz or run hot"). TXV1B RF_Easy.h: a step is 5 %, the box is EzLive's (one
number until the slider moves), its sums EzNudged's (floor(x + 0.5)) on RAW 420 MCM's own PIDs, as the EASY film shows them
(scenario 40: roll 50 100 20 100, pitch 130 140 50 100); "Write to the flight controller?" / "Feel (PIDs, bank 1)";
"Writing the PIDs ..."; "Saved, and read back the same: Feel.". The Filters page is scenario 64's (R P M filter on). The
symptom is illus.py's wobble. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, knob, comp
from common import rf_route, rf_route_play, rfs
from illus import Art

f = Film('WOBBLE', 'Wobbles or shakes', 'The likely cause, and the cure')
art = Art(f)
rf_route(f, 'Easy tuning ...')

# ---- Easy tuning (page 81): RAW 420 MCM, bank 1, rate 1; Cyclic one step softer (s3 6 -> 5: -5 %)
EASY = prefix('81.txt', '81_open', [('t11.txt="Havok"', 't11.txt="RAW 420 MCM"'), ('t14.txt="Bank 2"', 't14.txt="Bank 1"'),
                                    ('t8.txt="Rate 2"', 't8.txt="Rate 1"')])
def box(cols, shade=59323):
    """the numbers box above the sliders, as the slider's press script shows it and EzLive fills it"""
    names = ('lvb', 'lv0', 'lv1', 'lv2', 'lv3', 'lv4')
    return (''.join('%s.bco=%d\n' % (n, shade) for n in names) + ''.join('vis %s,1\n' % n for n in names) +
            ''.join('lv%d.txt="%s"\n' % (i, c) for i, c in enumerate(cols)))
SOFT = 's3.val=5\nvis b3,1\n'
f.shot('e_open', EASY)
f.shot('e_touch', EASY + box(['Cyclic 0 %\\r\\nRoll\\r\\nPitch', 'P\\r\\n50\\r\\n130', 'I\\r\\n100\\r\\n140', 'D\\r\\n20\\r\\n50', 'F\\r\\n100\\r\\n100']))
f.shot('e_5', EASY + SOFT + box(['Cyclic -5 %\\r\\nRoll\\r\\nPitch', 'P\\r\\n50 -> 48\\r\\n130 -> 124', 'I\\r\\n100 -> 95\\r\\n140 -> 133',
                                  'D\\r\\n20 -> 19\\r\\n50 -> 48', 'F\\r\\n100 -> 95\\r\\n100 -> 95']))
f.shot('e_lift', EASY + SOFT)
f.shot('e_ask', EASY + SOFT + 'page PopupView\nDialog.txt="Write to the flight controller?\\r\\nFeel (PIDs, bank 1)"\n')
f.shot('e_busy', EASY + SOFT + 'vis busy,1\nbusy.txt="Writing the PIDs ..."\n')
f.shot('e_saved', EASY + 's3.val=5\nvis b3,0\nvis busy,1\nbusy.txt="Saved, and read back the same: Feel."\n')
f.shot('e_after', EASY + 's3.val=5\nvis b3,0\n')
# ---- the Filters page (64): the R P M filter on
f.shot('flt', rfs('64.txt', '64_loaded'))
def words(name, half):
    """a section's heading: its words are at the left of its box (half: half their width, as the FILTERS film measured it)"""
    x, y, w, h = comp('FilterView', name); return x + 4 + half, y + h // 2

f.line('title', "It wobbles, or shakes. Here's the likely cause, and the cure.")
f.line('symptom', "A fast wobble on roll or pitch, often in fast forward flight, or coming down. Or a shake, even in the hover.")
f.line('cause', "Usually, the cyclic gains are a little too high, so it over-corrects. Or vibration is reaching the gyro.")
f.line('mech', "So check the simple things first: nothing loose, and the blades balanced and tracking true.")
f.line('easy', "This is Easy tuning. Slide Cyclic one step towards Softer.")
f.line('box', "The box shows every cyclic gain, five per cent lower: P, I, D and F, of roll and pitch.")
f.line('save', "Lift your finger, and press Save. It asks first: press OK.")
f.line('pid', "Prefer exact numbers? On the P I Ds page, lower roll and pitch P a little instead.")
f.line('flt', "Still shaking? This is the Filters page, from the Rotorflight menu. The R P M filter is the main defence against vibration.")
f.line('on', "Check its Enable is green. It needs a head speed signal: E S C telemetry, or an R P M sensor.")
f.line('buzz', "Servos buzzing too? See Servos buzz or run hot.")
f.line('test', "One step, one flight. If it starts to feel mushy, you've gone a step too far: come back one.")
f.prepare()

f.begin(); f.say('title', after=1.2)
f.show(art.wobble(0), look=0.3); f.anim(art.wobble, 3.0); f.say('symptom')
f.show(f.card('Likely causes', 'gains too high, or vibration')); f.say('cause')
f.say('mech', 'Check first: nothing loose, blades true.')
rf_route_play(f, 'Easy tuning ...', 'e_open')
f.say('easy', 'Cyclic: one step softer.', after=0.3)
k6, k5 = knob('EasyView', 's3', 6), knob('EasyView', 's3', 5)
f.glide(*k6); f.hold(0.3); f.press(); f.under('e_touch'); f.hold(0.6); f.slide([('e_5', k5[0])], k6[1], secs_each=0.7); f.hold(0.8)
f.say('box', 'Each cyclic gain 5 % lower.')
f.lift(); f.under('e_lift'); f.hold(0.4)
f.say('save', 'Save, then OK.', after=0.3)
f.tap(*at('EasyView', 'b3'), 'e_ask'); f.hold(0.4)
f.tap(*at('PopupView', 'b0'), 'e_busy'); f.cap = 'Writing ...'; f.hold(1.0); f.under('e_saved'); f.cap = 'Saved, and checked.'; f.hold(1.6)
f.under('e_after'); f.cap = None; f.say('pid', 'Or: P a little lower, on PIDs.')
f.show('flt'); f.point(*words('h1', 54), 'flt', 'The RPM filter.')
f.point(*at('FilterView', 'tn3'), 'on', 'Enable: green is on.')
f.cap = None; f.say('buzz', 'See: Servos buzz or run hot.')
f.show(f.card('Then fly it', 'one step, one flight')); f.say('test', 'Tip: one step, one flight.')
f.end(); f.finish()
