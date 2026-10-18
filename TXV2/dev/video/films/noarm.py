#!/usr/bin/env python3
"""Film NOARM ("Fix a problem", 18 Oct 2026): the model will not arm - how to find out why (the Rotorflight menu's arming
line), and the usual cures. Malcolm: "Let's include the likely cure for tail-wag and other common set up issues."
The facts: RFLIGHT.TXT (the arming line: 'Ready to arm' green, 'Armed' red, 'Will not arm:' and the main reason yellow, such
as 'Throttle is not at idle'; touch it to list the reasons, up to four; it shows only with the model connected and Bluetooth
joined; Bluetooth is off while the safety is off; the menu opens only with the safety on), RXSETUP1.TXT (Throttle channel,
usually 3; Motor off value: what the throttle channel is sent while the motor is off or the safety is on, -67 nearly always
right; not reversed with the channel: if you reverse the throttle, change it to match), RFSETUP.TXT (Arming channel: the
channel the safety switch drives, usually 6; Rotorflight version 0.0: no version known yet, and the safety switch does not
drive the arming channel), SWITCHES.TXT (the arm action is kept on the arming channel). The arming line's words and the list
are the Teensy's own (TXV1B RF_FcSetup.h ArmWhy / ArmShow / ArmingWhy: "Tilted too far: stand it level", " (and 1 more)",
"Why it will not arm:"). Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, comp
from common import model_route, model_route_play

f = Film('NOARM', 'Will not arm', 'The likely cause, and the cure')
model_route(f, 'Rotorflight')
opn = prefix('8.txt', '8_open')                                       # (Ready to arm, in green; By Bluetooth)
why = opn + 'arm.txt="Will not arm: Throttle is not at idle (and 1 more)"\narm.pco=65504\n'
f.shot('why', why)
f.shot('list', why + 'page PopupView\nvis b1,0\nDialog.txt="Why it will not arm:\\r\\n- Throttle is not at idle\\r\\n- Tilted too far: stand it level"\n')
f.shot('opt', prefix('9.txt', '9_open') + 'n1.val=3\n')              # (Model options: throttle channel 3, motor off value -67)
f.shot('ready', opn)
f.shot('set', prefix('61.txt', '61_open'))                           # (Rotorflight settings: version 2.3, arming channel 6)
x, y, w, h = comp('RFView', 'arm'); ARM = (x + 70, y + h // 2)       # (the line's words start at its left)

f.line('title', "It won't arm. Here's how to find out why, and the cure.")
f.line('symptom', "You flick the safety off, and nothing happens. Don't guess! Put the safety back on, and ask the Rotorflight menu.")
f.line('arm', "This is the Rotorflight menu. This line says whether the model will arm. Yellow means it won't, with the main reason.")
f.line('list', "Touch it, and you get every reason, up to four. Here, there are two.")
f.line('tilt', "Tilted too far? Stand it level, on flat ground.")
f.line('thr', "Throttle not at idle? With the safety on, the transmitter sends its Motor off value on the throttle channel.")
f.line('opt', "Both are on the Options page, on Model setup. Throttle channel: usually three.")
f.line('off', "Motor off value: minus sixty seven is nearly always right. Reversed the throttle? Then change this to match.")
f.line('ready', "Back on the Rotorflight menu: Ready to arm, in green. But the safety still won't arm it? Press Settings.")
f.line('chan', "This is the Settings page. Arming channel: the channel your safety switch drives, usually six. Rotorflight's arm switch must be on that channel too: its Switches page puts it there.")
f.line('ver', "And the Rotorflight version mustn't be nought point nought. Until a version is known, the safety doesn't drive the arming channel.")
f.line('test', "Then try again: motor switch off, and everyone clear of the blades.")
f.prepare()

f.begin(); f.say('title', after=1.2)
f.show(f.card("It won't arm", 'safety off, and nothing happens')); f.say('symptom')
model_route_play(f, 'Rotorflight', 'why')
f.point(*ARM, 'arm', 'Will not arm: the main reason.', after=0.3)
f.tap(*ARM, 'list'); f.say('list', 'Every reason, up to four.')
f.say('tilt', 'Tilted? Stand it level.')
f.say('thr', 'Throttle not at idle?', after=0.3)
f.tap(*at('PopupView', 'b0'), 'why')
f.show('opt'); f.point(*at('RXOptionsView', 't6'), 'opt', 'Throttle channel: usually 3.')
f.point(*at('RXOptionsView', 't5'), 'off', 'Motor off value: usually -67.')
f.show('ready'); f.point(*ARM, 'ready', 'Ready to arm, but it still won\'t?', after=0.3)
f.tap(*at('RFView', 'Setup'), 'set')
f.point(*at('RFSetupView', 't6'), 'chan', 'Arming channel: usually 6.')
f.point(*at('RFSetupView', 't4'), 'ver', 'Version: not 0.0.')
f.show(f.card('Then try again', 'motor off, blades clear')); f.say('test', 'Tip: motor off, blades clear.')
f.end(); f.finish()
