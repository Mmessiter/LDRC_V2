#!/usr/bin/env python3
"""Film EASY: Easy tuning from the transmitter (Rotorflight). The route and the words are the firmware's: front page > Model >
Rotorflight > Easy tuning (RF_Easy.h StartEasyView needs the model connected); a Cyclic change saves the PIDs, reported as
"Saved, and read back the same: Feel." (EzWords). Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, knob

f = Film('EASY', 'Easy tuning', 'Rotorflight, from the LDRC transmitter')
front = prefix('13.txt', '13_conn', [
    ('bt0.txt="Motor is ON"\nbt0.bco=2016\nbt0.bco2=2016\nbt0.pco=0\nbt0.pco2=0', 'bt0.txt="Motor is OFF"\nbt0.bco=63488\nbt0.bco2=63488\nbt0.pco=65535\nbt0.pco2=65535'),
    ('RPM: 2150', 'RPM: 0'), ('Amps: 12.4', 'Amps: 0.3'), ('mAh: 345', 'mAh: 0'), ('ESC: 52.3', 'ESC: 21.5')])
f.shot('a_front', front)
f.shot('a_model', prefix('4.txt', '4_open'))
f.shot('a_rf', prefix('8.txt', '8_open'))
easy = prefix('81.txt', '81_open', [('t11.txt="Havok"', 't11.txt="RAW 420 MCM"'), ('t14.txt="Bank 2"', 't14.txt="Bank 1"'), ('t8.txt="Rate 2"', 't8.txt="Rate 1"')])
box_on = 'lvb.bco=59323\nlv0.bco=59323\nlv1.bco=59323\nlv2.bco=59323\nlv3.bco=59323\nlv4.bco=59323\nlv0.txt=""\nlv1.txt=""\nlv2.txt=""\nlv3.txt=""\nlv4.txt=""\nvis lvb,1\nvis lv0,1\nvis lv1,1\nvis lv2,1\nvis lv3,1\nvis lv4,1\n'
numbers = 'lv0.txt="Cyclic +10 %\\r\\nRoll\\r\\nPitch"\nlv1.txt="P\\r\\n50 -> 53\\r\\n52 -> 57"\nlv2.txt="I\\r\\n100 -> 110\\r\\n104 -> 114"\nlv3.txt="D\\r\\n40 -> 44\\r\\n44 -> 48"\nlv4.txt="F\\r\\n100 -> 110\\r\\n100 -> 110"\n'
box_off = 'vis lv4,0\nvis lv3,0\nvis lv2,0\nvis lv1,0\nvis lv0,0\nvis lvb,0\n'
steps = [('e_open', ''), ('e_touch', box_on), ('e_7', 's3.val=7\nvis b3,1\n'), ('e_8', 's3.val=8\n' + numbers), ('e_lift', box_off),
         ('e_busy', 'vis busy,1\nbusy.txt="Writing the PIDs ..."\n'), ('e_saved', 'vis b3,0\nbusy.txt="Saved, and read back the same: Feel."\n')]
acc = easy
for k, cmds in steps: acc += cmds; f.shot(k, acc)
f.line('title', 'Easy tuning. How to tune a Rotorflight helicopter from the transmitter.')
f.line('front1', "This is the transmitter's front page. First, switch on the helicopter, and leave it disarmed, with the safety on.")
f.line('front2', 'Then press Model.')
f.line('model', 'This is the Model setup page. Press Rotorflight.')
f.line('rf', 'This is the Rotorflight menu. Press Easy tuning.')
f.line('open', 'Easy tuning changes how the helicopter flies, without any numbers. Each slider changes one thing: softer to the left, sharper to the right.')
f.line('drag', 'To make the cyclic a little sharper, slide Cyclic to the right.')
f.line('numbers', 'While your finger is on the slider, the box at the top shows each P, I, D and F value, before and after.')
f.line('save', 'Lift your finger, then press Save.')
f.line('saved', "The transmitter writes the new values to the helicopter's flight controller, reads them back to check, and tells you they match.")
f.line('end', "That's all there is to it.")
f.prepare()

f.begin(); f.say('title', after=1.6)
f.show('a_front'); f.say('front1', 'Helicopter on, safety on.'); f.say('front2', 'Press Model.', after=0.3); f.tap(*at('FrontView', 'b1'), 'a_model')
f.say('model', 'Press Rotorflight.', after=0.3); f.tap(*at('RXSetupView', 'b7'), 'a_rf')
f.say('rf', 'Press Easy tuning.', after=0.3); f.tap(*at('RFView', 'Easy'), 'e_open')
f.say('open', 'Softer to the left, sharper to the right.')
f.say('drag', 'Slide Cyclic to the right.', after=0.3)
k6, k7, k8 = knob('EasyView', 's3', 6), knob('EasyView', 's3', 7), knob('EasyView', 's3', 8)
f.glide(*k6); f.hold(0.3); f.press(); f.under('e_touch'); f.hold(0.5); f.slide([('e_7', k7[0]), ('e_8', k8[0])], k6[1]); f.hold(0.8)
f.say('numbers', 'The box shows each value, before and after.')
f.say('save', 'Lift your finger, then press Save.', after=0.3)
f.lift(); f.under('e_lift'); f.hold(0.6); f.tap(*at('EasyView', 'b3'))
f.show('e_busy', look=0.2); f.cap = 'Writing ...'; f.hold(1.4)
f.show('e_saved', look=0.3); f.say('saved', 'Saved, and read back to check.', after=1.4)
f.end('end')
f.finish()
