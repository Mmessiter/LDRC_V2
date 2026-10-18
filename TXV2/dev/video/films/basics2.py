#!/usr/bin/env python3
"""Film BASICS2: the gear ratios - a tour, then a head speed far from the truth: a ratio typed backwards, which Save spots.
The facts are BASICS2.TXT's (rotor : motor; whole numbers are the teeth, pinion 10 : main gear 102; two-stage drives multiply,
21x19 : 60x68 = 399 : 4080; the tail 1 : 4 to 1 : 5.5; backwards makes Save warn); the warning's words are RF_Basics.h
SaveBasics'. Made with dev/video/filmkit.py.
18 Oct 2026: starts on the Rotorflight menu (Settings, First-time basics, Next); livelier words; "In practice"; no closing line."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
f = Film('BASICS2', 'Gear ratio', 'For the true head speed')
rf_route(f, 'Settings ...')
gear = rfs('77.txt', '78_ready')                                                    # (399 : 4080, tail 475 : 2516; Save hidden)
back = gear + 'tn0.txt="4080"\ntn1.txt="399"\n' + SAVE_SHOWN                         # the main ratio typed backwards
f.shot('s', rfs('61.txt', '61_open'))
f.shot('b', rfs('77.txt', '77_ready', 'tn1.txt="Clockwise"\ntn2.txt="Variable pitch"\n'))
f.shot('p', gear); f.shot('back', back); f.shot('fixed', gear + SAVE_SHOWN)
f.shot('warn', back + 'page PopupView\nDialog.txt="The main gear ratio looks backwards:\\r\\nrotor 4080 : motor 399 - the rotor would turn\\r\\n'
                      'faster than the motor, and the governor\\r\\nwould sit at minimum throttle. Save anyway?"\n')
f.line('title', 'Gear ratio. So the governor knows the true head speed.')
f.line('s', 'This is the Rotorflight settings page. Press First time basics.')
f.line('b', 'This is the First time basics page. Press Next.')
f.line('page', 'This is the Gear ratio page: how many turns the rotor makes, for how many turns of the motor, or of the tail. With the pole count, they give the true head speed.')
f.line('main', 'Main gear ratio: rotor, then motor. Whole numbers are the teeth. For a pinion of ten, and a main gear of a hundred and two, type ten, then a hundred and two.')
f.line('two', "A two stage drive, a belt and then gears, multiplies the teeth: motor pulley times pinion, then big pulley times main gear. That's where big numbers like these come from.")
f.line('tail', "Tail gear ratio: rotor, then tail. It's usually between one to four and one to five and a half.")
f.line('nav', 'Previous and Next move between the pages, with your changes kept.')
f.line('back', "A head speed far from the truth? The ratio may be typed backwards. The rotor turns slower than the motor, so the rotor's number should never be the bigger one.")
f.line('spot', "Typed them backwards? Don't worry: Save spots it.")
f.line('warn', 'Backwards, the governor would sit at minimum throttle. So press Cancel.')
f.line('swap', 'Then type the two numbers the other way round.')
f.line('save', "That's better. Now Save writes all the first time basics pages, and restarts the flight controller. It asks first.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Settings ...', 's')
f.say('s', 'Press First-time basics.', after=0.3); f.tap(*at('RFSetupView', 'b5'), 'b')
f.say('b', 'Press Next.', after=0.3); f.tap(*at('BasicsView', 'b2'), 'p')
f.say('page', 'Gear ratio.')
f.point(*at('Basics2View', 'ltn0'), 'main', 'Main gear ratio.')
f.point(*at('Basics2View', 'tn0'), 'two', 'Two stages: multiply.')
f.point(*at('Basics2View', 'ltn2'), 'tail', 'Tail gear ratio.')
f.point(*at('Basics2View', 'b2'), 'nav', '< Previous, Next >.')
f.show('back'); f.point(*at('Basics2View', 'tn0'), 'back', 'Tip: rotor = the smaller number.')
f.say('spot', 'Tip: Save spots it.', after=0.3); f.tap(*at('Basics2View', 'b3'), 'warn')
f.say('warn', 'Press Cancel.', after=0.3); f.tap(*at('PopupView', 'b1'), 'back')
f.say('swap', 'Swap them round.', after=0.3); f.show('fixed')
f.point(*at('Basics2View', 'b3'), 'save', 'Save: then a restart.')
f.end(); f.finish()
