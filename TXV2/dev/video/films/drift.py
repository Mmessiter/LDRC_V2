#!/usr/bin/env python3
"""Film DRIFT ("Fix a problem", 18 Oct 2026): it feels mushy, or drifts - the likely cause (the cyclic gains too low), and
the cures on the transmitter's own Rotorflight pages. Malcolm: "Let's include the likely cure for tail-wag and other common
set up issues."
The facts: EASY.TXT ("Sluggish, drifting or mushy: sharper."; small steps, one flight each; Save asks first), PID.TXT ("I: how
firmly it holds against drift and wind."; Save writes, reads back, stores; 'PID + ...' opens PID + for the same bank),
PID_A.TXT ("Relax on the ground (ground error decay): on the ground, built-up corrections drain away, so the swash does not
lean."), TRAVEL.TXT (swash trims: "small corrections that level the swash"). TXV1B RF_Easy.h: a Cyclic step is 5 %, the box is
EzLive's, its sums EzNudged's (floor(x + 0.5)) on RAW 420 MCM's own PIDs as the PID and EASY films show them (scenario 40: roll
50 100 20 100, pitch 130 140 50 100); "Write to the flight controller?" / "Feel (PIDs, bank 1)"; "Writing the PIDs ...";
"Saved, and read back the same: Feel.". The PIDs page after that save shows the new numbers; I about ten per cent more
(roll 105 -> 116, pitch 147 -> 162). The symptom is illus.py's drift. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, knob
from common import rf_route, rf_route_play
from illus import Art

f = Film('DRIFT', 'Mushy or drifts', 'The likely cause, and the cure')
art = Art(f)
rf_route(f, 'Easy tuning ...')

# ---- Easy tuning (page 81): RAW 420 MCM, bank 1, rate 1; Cyclic one step sharper (s3 6 -> 7: +5 %)
EASY = prefix('81.txt', '81_open', [('t11.txt="Havok"', 't11.txt="RAW 420 MCM"'), ('t14.txt="Bank 2"', 't14.txt="Bank 1"'),
                                    ('t8.txt="Rate 2"', 't8.txt="Rate 1"')])
def box(cols, shade=59323):
    """the numbers box above the sliders, as the slider's press script shows it and EzLive fills it"""
    names = ('lvb', 'lv0', 'lv1', 'lv2', 'lv3', 'lv4')
    return (''.join('%s.bco=%d\n' % (n, shade) for n in names) + ''.join('vis %s,1\n' % n for n in names) +
            ''.join('lv%d.txt="%s"\n' % (i, c) for i, c in enumerate(cols)))
SHARP = 's3.val=7\nvis b3,1\n'
f.shot('e_open', EASY)
f.shot('e_touch', EASY + box(['Cyclic 0 %\\r\\nRoll\\r\\nPitch', 'P\\r\\n50\\r\\n130', 'I\\r\\n100\\r\\n140', 'D\\r\\n20\\r\\n50', 'F\\r\\n100\\r\\n100']))
f.shot('e_7', EASY + SHARP + box(['Cyclic +5 %\\r\\nRoll\\r\\nPitch', 'P\\r\\n50 -> 53\\r\\n130 -> 137', 'I\\r\\n100 -> 105\\r\\n140 -> 147',
                                   'D\\r\\n20 -> 21\\r\\n50 -> 53', 'F\\r\\n100 -> 105\\r\\n100 -> 105']))
f.shot('e_lift', EASY + SHARP)
f.shot('e_ask', EASY + SHARP + 'page PopupView\nDialog.txt="Write to the flight controller?\\r\\nFeel (PIDs, bank 1)"\n')
f.shot('e_busy', EASY + SHARP + 'vis busy,1\nbusy.txt="Writing the PIDs ..."\n')
f.shot('e_saved', EASY + 's3.val=7\nvis b3,0\nvis busy,1\nbusy.txt="Saved, and read back the same: Feel."\n')
# ---- PIDs (page 40) after that save: roll 53 105 21 105, pitch 137 147 53 105; then I about ten per cent more
PID = prefix('40.txt', '40_open') + 'n0.val=53\nn1.val=105\nn2.val=21\nn3.val=105\nn4.val=137\nn5.val=147\nn6.val=53\nn7.val=105\n'
GREY = ''.join('n%d.pco=33840\n' % i for i in range(17))
BLACK = ''.join('n%d.pco=0\n' % i for i in range(17))
MORE_I = 'n1.val=116\nn5.val=162\n'
f.shot('p_open', PID)
f.shot('p_edit', PID + MORE_I + 'vis b3,1\n')
f.shot('p_send', PID + MORE_I + GREY + 'busy.txt="Sending edited PIDs ..."\nvis busy,1\nvis b2,0\nvis b3,0\n')
f.shot('p_done', PID + MORE_I + BLACK + 'vis busy,0\nvis b2,1\nvis b3,0\n')

f.line('title', "It feels mushy, or drifts. Here's the likely cause, and the cure.")
f.line('symptom', "Slow to answer the stick? Wandering off line, or it won't hold its spot in the wind?")
f.line('cause', "Usually, the cyclic gains are a little low, so it doesn't correct firmly enough.")
f.line('easy', "This is Easy tuning. Slide Cyclic one step towards Sharper.")
f.line('box', "The box shows every cyclic gain, five per cent higher: P, I, D and F, of roll and pitch.")
f.line('save', "Lift your finger, and press Save. It asks first: press OK.")
f.line('wind', "Still wanders in the wind? This is the P I Ds page. A little more I helps: it's how firmly it holds against drift.")
f.line('i', "Roll and pitch I, about ten per cent more. Then press Save.")
f.line('ground', "Leans or creeps on the ground, before lift-off? Relax on the ground, on P I D plus, drains away the corrections that build up there.")
f.line('swash', "A steady lean one way in a calm hover, with all else right? Level the swash, with the swash trims on Travel extents.")
f.line('test', "One change, one flight. Too sharp, and it starts to wobble: then come back a step.")
f.prepare()

f.begin(); f.say('title', after=1.2)
f.show(art.drift(0), look=0.3); f.anim(art.drift, 3.0); f.say('symptom')
f.show(f.card('Likely cause', 'the cyclic gains are too low')); f.say('cause')
rf_route_play(f, 'Easy tuning ...', 'e_open')
f.say('easy', 'Cyclic: one step sharper.', after=0.3)
k6, k7 = knob('EasyView', 's3', 6), knob('EasyView', 's3', 7)
f.glide(*k6); f.hold(0.3); f.press(); f.under('e_touch'); f.hold(0.6); f.slide([('e_7', k7[0])], k6[1], secs_each=0.7); f.hold(0.8)
f.say('box', 'Each cyclic gain 5 % higher.')
f.lift(); f.under('e_lift'); f.hold(0.4)
f.say('save', 'Save, then OK.', after=0.3)
f.tap(*at('EasyView', 'b3'), 'e_ask'); f.hold(0.4)
f.tap(*at('PopupView', 'b0'), 'e_busy'); f.cap = 'Writing ...'; f.hold(1.0); f.under('e_saved'); f.cap = 'Saved, and checked.'; f.hold(1.6)
f.show('p_open'); f.point(*at('PIDView', 't6'), 'wind', 'Drifts in wind? A little more I.', after=0.2)
f.under('p_edit'); f.hold(0.6); f.cap = None
f.say('i', 'Roll and pitch I: about 10 % more.', after=0.3)
f.tap(*at('PIDView', 'b3')); f.under('p_send'); f.hold(1.2); f.under('p_done'); f.hold(0.6)
f.point(*at('PIDView', 'b2'), 'ground', 'Leans on the ground? PID +.')
f.show(f.card('Leans one way?', 'level the swash: Travel extents')); f.say('swash')
f.show(f.card('Then fly it', 'one step, one flight')); f.say('test', 'Tip: one change, one flight.')
f.end(); f.finish()
