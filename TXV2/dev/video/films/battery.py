#!/usr/bin/env python3
"""Film BATTERY: the flight pack, a tour. The words are BATTERY.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
f = Film('BATTERY', 'Battery (Rotorflight)', 'The flight pack, for warnings and telemetry')
rf_route(f, 'Battery ...')
f.shot('p', rfs('72.txt', '72_open')); f.shot('e', rfs('72.txt', '72_edited'))
f.line('title', 'Battery. Telling the flight controller about the flight pack.')
f.line('page', 'This is the Battery page, the same in every bank. It is for the flight controller\'s warnings and the telemetry.')
f.line('cells', 'Cell count: how many cells the pack has. Nought counts them by the voltage.')
f.line('capacity', 'Capacity: the size of the pack, for the fuel gauge.')
f.line('from', 'Voltage from and Current from: usually E S C telemetry. Tap the box to step through the choices.')
f.line('volts', 'Cell voltages: full, warning, empty, and the highest allowed. Three point five volts is a common warning.')
f.line('save', 'Save appears once something is changed. It writes, stores, and reads back.')
f.line('ok', 'OK leaves. With a change not saved it asks first.')
f.line('end', "That's the Battery page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Battery ...', 'p')
f.say('page', 'Battery.')
f.point(*at('BatteryView', 'ltn0'), 'cells', 'Cell count.')
f.point(*at('BatteryView', 'ltn1'), 'capacity', 'Capacity.')
f.point(*at('BatteryView', 'ltn2'), 'from', 'Voltage and current from.')
f.point(*at('BatteryView', 'h1'), 'volts', 'Cell voltages.')
f.under('e'); f.hold(0.6); f.point(*at('BatteryView', 'b3'), 'save', 'Save.')
f.point(*at('BatteryView', 'b1'), 'ok', 'OK.')
f.end('end'); f.finish()
