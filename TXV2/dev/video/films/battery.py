#!/usr/bin/env python3
"""Film BATTERY: the flight pack - a tour, then the capacity, the warning and the cell count set right. The facts are
BATTERY.TXT's (0 = auto counts the cells by the voltage; Highest allowed is used for that count; 3.50 a common warning).
The RAW 420 flies 6S packs (memory: rc-battery-cell-counts). Made with dev/video/filmkit.py.
18 Oct 2026: starts on the Rotorflight menu; livelier words; "In practice" after the tour; no closing line (Malcolm)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
from illus import Art
f = Film('BATTERY', 'Battery (Rotorflight)', 'The flight pack, for warnings and telemetry')
rf_route(f, 'Battery ...')
# as read: automatic cell count, a 2200 mAh pack, both from ESC telemetry (so no 'Sensors >'), Save hidden
opn = rfs('72.txt', '72_open', 'tn0.txt="0"\ntn1.txt="2200"\ntn3.txt="ESC telemetry"\nvis b2,0\n')
f.shot('p', opn); f.shot('six', opn + 'tn0.txt="6"\n' + SAVE_SHOWN)
f.line('title', 'Battery. Tell the flight controller about your flight pack, so its warnings and fuel gauge are right.')
f.line('page', "This is the Battery page. It's for the flight controller's warnings, and the telemetry. It's the same in every bank.")
f.line('cells', 'Cell count: how many cells the pack has. Nought means automatic: it counts them from the voltage.')
f.line('capacity', 'Capacity: the size of the pack, in milliamp hours, for the fuel gauge.')
f.line('from', 'Voltage from, and Current from: usually E S C telemetry. Tap a box to step through the choices.')
f.line('volts', 'Then the cell voltages, in volts per cell: full, warning, empty, and the highest allowed.')
f.line('cap', 'Get the capacity right, and the fuel gauge will be right too.')
f.line('warn', "A warning at about three point five volts a cell is common. That's your cue to land, with a little to spare.")
f.line('pack', "On a six cell pack, that's twenty one volts in all. The flight controller works in volts per cell, so the same numbers suit any size of pack.")
f.line('six', "So if you always fly six cell packs, type six here. Counting by voltage can be fooled by a nearly flat pack, and then the warnings can't be trusted.")
f.line('save', "Save appears once something's changed. It writes to the flight controller, stores, and reads back.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Battery ...', 'p')
f.say('page', 'Battery.')
f.point(*at('BatteryView', 'ltn0'), 'cells', 'Cell count.')
f.point(*at('BatteryView', 'ltn1'), 'capacity', 'Capacity.')
f.point(*at('BatteryView', 'ltn2'), 'from', 'Voltage and current from.')
f.point(*at('BatteryView', 'h1'), 'volts', 'Cell voltages.')
f.point(*at('BatteryView', 'tn1'), 'cap', 'Tip: capacity = fuel gauge.')
f.point(*at('BatteryView', 'tn5'), 'warn', 'Tip: warn at about 3.5 V.')
art = Art(f); f.show(art.battery(0, cells=6, volts=3.5, title='Warning: 3.5 volts a cell')); f.say('pack', 'Tip: 6 cells x 3.5 V = 21 V.')
f.show('six'); f.point(*at('BatteryView', 'tn0'), 'six', 'Tip: type the cell count.')
f.point(*at('BatteryView', 'b3'), 'save', 'Save.')
f.end(); f.finish()
