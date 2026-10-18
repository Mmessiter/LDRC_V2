#!/usr/bin/env python3
"""Film BASICS: first-time basics, the first page - a tour, then a head speed that reads wrong (the pole count) and the ESC
signal most helicopter ESCs want. The facts are BASICS.TXT's (the pole count = the magnets in the bell, needed to turn
electrical RPM into true RPM; helicopter ESCs use Normal PWM, DShot is for drone-style ESCs); the words on the page are
RF_Basics.h's. The RAW 420: a variable-pitch tail, the rotor clockwise from above. Made with dev/video/filmkit.py.
18 Oct 2026: starts on the Rotorflight menu (Settings, then First-time basics); livelier words; "In practice"; no closing line."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
f = Film('BASICS', 'First-time basics', 'What kind of helicopter, and its ESC')
rf_route(f, 'Settings ...')
bas = rfs('77.txt', '77_ready', 'tn1.txt="Clockwise"\ntn2.txt="Variable pitch"\n')   # (as read; Save hidden)
f.shot('s', rfs('61.txt', '61_open'))
f.shot('p', bas + 'tn5.txt="8"\n')                                                     # a pole count typed wrongly ...
f.shot('fixed', bas + 'tn5.txt="10"\n' + SAVE_SHOWN)                                   # ... put right: Save shows
f.line('title', 'First time basics. What kind of helicopter the flight controller is flying, and how it talks to the E S C.')
f.line('s', 'This is the Rotorflight settings page. Press First time basics.')
f.line('page', 'This is the First time basics page. You set these once, when a model is new. Tap a choice to step to the next one, or tap a number to type.')
f.line('swash', 'Swash type, which way the rotor turns, seen from above, and the tail type.')
f.line('esc', 'E S C signal is how the throttle is sent, not the brand.')
f.line('brand', "E S C brand is the language on the E S C's telemetry wire. None, if there's no telemetry wire.")
f.line('poles', "Motor pole count: the number of magnets in the motor's bell.")
f.line('next', 'Next goes on to Gear ratio, then Ports, then Throttle calibration, with your changes kept.')
f.line('wrong', "Does the head speed read wrong? Check the pole count first. Count the magnets, or look on the motor's sheet.")
f.line('fixed', 'Here, the motor has ten magnets, so type ten. With the wrong count, the governor holds the wrong head speed too.')
f.line('pwm', 'And most helicopter E S Cs want Normal P W M here. D shot is for drone style E S Cs.')
f.line('save', 'Save writes all the first time basics pages, then restarts the flight controller. It asks first.')
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Settings ...', 's')
f.say('s', 'Press First-time basics.', after=0.3); f.tap(*at('RFSetupView', 'b5'), 'p')
f.say('page', 'First-time basics.')
f.point(*at('BasicsView', 'ltn0'), 'swash', 'Swash, rotor, tail.')
f.point(*at('BasicsView', 'ltn3'), 'esc', 'ESC signal.')
f.point(*at('BasicsView', 'ltn4'), 'brand', 'ESC brand.')
f.point(*at('BasicsView', 'ltn5'), 'poles', 'Motor poles.')
f.point(*at('BasicsView', 'b2'), 'next', 'Next >.')
f.point(*at('BasicsView', 'tn5'), 'wrong', 'Tip: odd head speed? Poles.')
f.show('fixed'); f.point(*at('BasicsView', 'tn5'), 'fixed', 'Tip: 10 magnets, type 10.')
f.point(*at('BasicsView', 'tn3'), 'pwm', 'Tip: most heli ESCs: Normal PWM.')
f.point(*at('BasicsView', 'b3'), 'save', 'Save: then a restart.')
f.end(); f.finish()
