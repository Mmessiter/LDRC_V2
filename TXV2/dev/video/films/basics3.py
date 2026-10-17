#!/usr/bin/env python3
"""Film BASICS3: the flight controller's ports, a tour. The words are BASICS3.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, rf_route, rf_route_play, rfs, SAVE_SHOWN, FRONT_NO_MODEL
f = Film('BASICS3', 'Ports', "The flight controller's serial ports")
rf_route(f, 'Settings ...')
f.shot('s', rfs('61.txt', '61_open')); f.shot('b', rfs('77.txt', '77_ready')); f.shot('b2', rfs('77.txt', '78_ready')); f.shot('p', rfs('77.txt', '79_ready')); f.shot('e', rfs('77.txt', '79_ready', SAVE_SHOWN))
f.line('title', "Ports. The flight controller's serial ports, and what each one does.")
f.line('s', 'This is the Rotorflight settings page. Press First time basics, then Next, twice.')
f.line('page', 'Each row is a socket on the flight controller.')
f.line('row', 'Tap a row to step its job: nothing, E S C telemetry, G P S, a dongle on a wire, telemetry out, or a black box logger.')
f.line('rx', 'Receiver is the port your receiver is wired to. It cannot be changed here.')
f.line('save', 'Save writes all the first time basics pages, then restarts the flight controller.')
f.line('end', "That's the Ports page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Settings ...', 's')
f.say('s', 'First-time basics, then Next twice.', after=0.3); f.tap(*at('RFSetupView', 'b5'), 'b'); f.tap(*at('BasicsView', 'b2'), 'b2'); f.tap(*at('Basics2View', 'b2'), 'p')
f.say('page', 'Ports.')
f.point(*at('PortsView', 'ltn1'), 'row', 'Tap a row: its job.')
f.cap = None; f.say('rx', 'The Receiver port stays.')
f.under('e'); f.hold(0.6); f.point(*at('PortsView', 'b3'), 'save', 'Save.')
f.end('end'); f.finish()
