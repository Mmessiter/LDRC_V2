#!/usr/bin/env python3
"""Film BASICS3: the flight controller's ports - a tour, then no head speed: the ESC's telemetry socket given its job. The
facts are BASICS3.TXT's (a tap steps a row's job; Receiver cannot be changed here; a port given a job it is not wired for is
simply silent; Save restarts the flight controller, asking first) and BASICS.TXT's (ESC brand = the telemetry language); the
job words are RF_Basics.h's BasPortWords. Made with dev/video/filmkit.py.
18 Oct 2026: starts on the Rotorflight menu (Settings, First-time basics, Next, Next); livelier words; "In practice"; no closing line."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
f = Film('BASICS3', 'Ports', "The flight controller's serial ports")
rf_route(f, 'Settings ...')
ports = rfs('77.txt', '79_ready')                                    # (TELEM (UART 2) = ESC telemetry; Save hidden)
f.shot('s', rfs('61.txt', '61_open'))
f.shot('b', rfs('77.txt', '77_ready', 'tn1.txt="Clockwise"\ntn2.txt="Variable pitch"\n'))
f.shot('b2', rfs('77.txt', '78_ready'))
f.shot('p', ports + 'tn1.txt="Nothing"\n')                           # the ESC's telemetry socket with no job ...
f.shot('esc', ports + SAVE_SHOWN)                                    # ... one tap: ESC telemetry, and Save shows
f.line('title', "Ports. The flight controller's sockets, and the job each one does.")
f.line('s', 'This is the Rotorflight settings page. Press First time basics.')
f.line('b', 'This is the First time basics page. Press Next.')
f.line('b2', 'This is the Gear ratio page. Press Next again.')
f.line('page', "This is the Ports page. Each row is a socket on the flight controller, named as it's printed on the board.")
f.line('row', 'Tap a row to step its job: nothing, E S C telemetry, G P S, a dongle on a wire, telemetry out, or a black box logger.')
f.line('rx', "Receiver is the socket your receiver is wired to. It can't be changed here, or the transmitter would lose the flight controller.")
f.line('nohs', "No head speed on the transmitter? Or won't the model arm, for want of an R P M signal? Often, the E S C's telemetry socket has no job.")
f.line('fix', "Tap its row until it says E S C telemetry. And on the first page, choose the E S C's brand.")
f.line('wired', "Pick the socket the wire is really plugged into. A port given a job it isn't wired for is simply silent.")
f.line('save', 'Save writes all the first time basics pages, and restarts the flight controller. It asks first.')
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Settings ...', 's')
f.say('s', 'Press First-time basics.', after=0.3); f.tap(*at('RFSetupView', 'b5'), 'b')
f.say('b', 'Press Next.', after=0.3); f.tap(*at('BasicsView', 'b2'), 'b2')
f.say('b2', 'Press Next.', after=0.3); f.tap(*at('Basics2View', 'b2'), 'p')
f.say('page', 'Ports.')
f.point(*at('PortsView', 'tn2'), 'row', 'Tap a row: its job.')
f.point(*at('PortsView', 'tn0'), 'rx', 'The Receiver port stays.')
f.point(*at('PortsView', 'tn1'), 'nohs', 'Tip: no head speed?')
f.tap(*at('PortsView', 'tn1'), 'esc'); f.say('fix', 'Tip: ESC telemetry, and brand.')
f.cap = None; f.say('wired', 'Tip: match the wiring.')
f.point(*at('PortsView', 'b3'), 'save', 'Save: then a restart.')
f.end(); f.finish()
