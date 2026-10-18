#!/usr/bin/env python3
"""Film FEEL ("Fix a problem", 18 Oct 2026): too twitchy, or too slow - not a fault but the rates: Easy tuning's Agility and
Stick feel, then the exact numbers on the Rates page. Malcolm: "Let's include the likely cure for tail-wag and other common
set up issues."
The facts: EASY.TXT (Agility: how fast roll, pitch and yaw turn at full stick, from half to double the centre; Stick feel:
the expo, from 35 softer to 35 more direct; they work with the Rotorflight, Actual and Quickrates types; Save asks first),
RATES1.TXT (Roll, Pitch and Yaw in degrees per second; the 'Rates' switch chooses the rate). TXV1B RF_Easy.h: Agility and
Stick feel 0..20, the centre 10; Agility scales by EZ_TWO (2 to the (v - 50) / 50: one step down is x 0.933) and rounds to
the type's step (Rotorflight's own type: 5 degrees a second); Stick feel: expo = base - (v - 50) x 0.7 (one step left is
3.5 more); the box is EzLive's (for the Rotorflight type one row, "Rate"; "Expo"); the question "Agility (rates, rate 1)";
"Writing the rates ..."; "Saved, and read back the same: Agility.". RAW 420 MCM's rates are scenario 1's (6 - ROTORFLIGHT:
roll and pitch 160, yaw 400, shape 20, expo 20), as the RATES1 film shows them. The symptom is illus.py's feel.
Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, knob
from common import rf_route, rf_route_play
from illus import Art

f = Film('FEEL', 'Too twitchy or too slow', 'The likely cause, and the cure')
art = Art(f)
rf_route(f, 'Easy tuning ...')

# ---- Easy tuning (page 81): Agility one step towards Docile (s1 10 -> 9), Stick feel one step towards Soft centre (s2 10 -> 9)
EASY = prefix('81.txt', '81_open', [('t11.txt="Havok"', 't11.txt="RAW 420 MCM"'), ('t14.txt="Bank 2"', 't14.txt="Bank 1"'),
                                    ('t8.txt="Rate 2"', 't8.txt="Rate 1"')])
def box(cols, shade=57215):
    """the numbers box above the sliders, as the slider's press script shows it and EzLive fills it (the rates rows' shade)"""
    names = ('lvb', 'lv0', 'lv1', 'lv2', 'lv3', 'lv4')
    return (''.join('%s.bco=%d\n' % (n, shade) for n in names) + ''.join('vis %s,1\n' % n for n in names) +
            ''.join('lv%d.txt="%s"\n' % (i, c) for i, c in enumerate(cols)))
AG = 's1.val=9\nvis b3,1\n'; BOTH = 's1.val=9\ns2.val=9\nvis b3,1\n'
f.shot('e_open', EASY)
f.shot('a_touch', EASY + box(['Agility\\r\\nRate', 'Roll\\r\\n160', 'Pitch\\r\\n160', 'Yaw\\r\\n400', '']))
f.shot('a_9', EASY + AG + box(['Agility\\r\\nRate', 'Roll\\r\\n160 -> 150', 'Pitch\\r\\n160 -> 150', 'Yaw\\r\\n400 -> 375', '']))
f.shot('a_lift', EASY + AG)
f.shot('s_touch', EASY + AG + box(['Stick feel\\r\\nExpo', 'Roll\\r\\n20', 'Pitch\\r\\n20', 'Yaw\\r\\n20', '']))
f.shot('s_9', EASY + BOTH + box(['Stick feel\\r\\nExpo', 'Roll\\r\\n20 -> 24', 'Pitch\\r\\n20 -> 24', 'Yaw\\r\\n20 -> 24', '']))
f.shot('s_lift', EASY + BOTH)
f.shot('e_ask', EASY + BOTH + 'page PopupView\nDialog.txt="Write to the flight controller?\\r\\nAgility (rates, rate 1)"\n')
f.shot('e_busy', EASY + BOTH + 'vis busy,1\nbusy.txt="Writing the rates ..."\n')
f.shot('e_saved', EASY + 's1.val=9\ns2.val=9\nvis b3,0\nvis busy,1\nbusy.txt="Saved, and read back the same: Agility."\n')
# ---- the Rates page (1) after that save: roll and pitch 150, yaw 375, expo 24
f.shot('rates', prefix('1.txt', '1_open') + 'tn0.txt="150"\ntn3.txt="150"\ntn6.txt="375"\ntn2.txt="24"\ntn5.txt="24"\ntn8.txt="24"\n')

f.line('title', "Too twitchy, or too slow? Here's the likely cause, and the cure.")
f.line('symptom', "Does it flick round faster than you'd like? Or take its time, even at full stick?")
f.line('cause', "Usually, that's not a fault: it's the rates. How fast it turns at full stick, and how it feels round the centre.")
f.line('easy', "This is Easy tuning. Agility sets how fast it turns at full stick. Too twitchy? One step towards Docile. Too slow? Towards Acrobatic.")
f.line('abox', "The box shows the full stick rates, in degrees per second: each one a little lower.")
f.line('feel', "Stick feel is the expo. A step towards Soft centre makes small moves gentler, while full stick stays the same.")
f.line('save', "Lift your finger, and press Save. It asks first: press OK.")
f.line('rates', "For exact numbers, this is the Rates page. Rate is how fast it turns at full stick, in degrees per second.")
f.line('switch', "Here's a neat idea: a gentle rate for practice, and a lively one for sport, just a flick of a switch apart.")
f.line('test', "Try each change high up, and give it a whole flight before you judge it.")
f.prepare()

f.begin(); f.say('title', after=1.2)
f.show(art.feel(0), look=0.3); f.anim(art.feel, 2.3); f.say('symptom')   # (it ends 0.3 s into a roll: the twitchy one over, the slow one setting off)
f.show(f.card("It's the rates", 'not a fault')); f.say('cause')
rf_route_play(f, 'Easy tuning ...', 'e_open')
f.say('easy', 'Agility: Docile or Acrobatic.', after=0.3)
k10, k9 = knob('EasyView', 's1', 10), knob('EasyView', 's1', 9)
f.glide(*k10); f.hold(0.3); f.press(); f.under('a_touch'); f.hold(0.6); f.slide([('a_9', k9[0])], k10[1], secs_each=0.7); f.hold(0.8)
f.say('abox', 'Full-stick rates, a step lower.')
f.lift(); f.under('a_lift'); f.hold(0.4); f.cap = None
k10, k9 = knob('EasyView', 's2', 10), knob('EasyView', 's2', 9)
f.glide(*k10); f.hold(0.3); f.press(); f.under('s_touch'); f.hold(0.6); f.slide([('s_9', k9[0])], k10[1], secs_each=0.7); f.hold(0.8)
f.say('feel', 'Stick feel: a softer centre.')
f.lift(); f.under('s_lift'); f.hold(0.4)
f.say('save', 'Save, then OK.', after=0.3)
f.tap(*at('EasyView', 'b3'), 'e_ask'); f.hold(0.4)
f.tap(*at('PopupView', 'b0'), 'e_busy'); f.cap = 'Writing ...'; f.hold(1.0); f.under('e_saved'); f.cap = 'Saved, and checked.'; f.hold(1.6)
f.show('rates'); f.point(*at('RatesView', 't5'), 'rates', 'Rate: degrees a second.')
f.point(*at('RatesView', 't9'), 'switch', 'Tip: a gentle rate, a lively one.')
f.show(f.card('Then fly it', 'high up, one change at a time')); f.say('test', 'Tip: one change, one flight.')
f.end(); f.finish()
