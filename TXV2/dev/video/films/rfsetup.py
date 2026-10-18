#!/usr/bin/env python3
"""Film RFSETUP: Rotorflight settings - a tour, then real uses: one switch for bank and rate, a model that won't arm, and a
version that reads 0.0. The facts are RFSETUP.TXT's and RFLIGHT.TXT's (the arming line); the version fills in when the
receiver's flight controller answers (TransmitterCode transceiver.h, ack 31). Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the setup pages, real uses, livelier words, no closing line): starts on the Rotorflight menu."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, at
from common import rf_route, rf_route_play, rfs
f = Film('RFSETUP', 'Rotorflight settings', 'What the transmitter needs to know')
rf_route(f, 'Settings ...')
opn = rfs('61.txt', '61_open')                       # (linked, version 2.3, arming channel 6, gear ratio 10.30)
f.shot('p', opn); f.shot('v0', opn + 't5.txt="0.0"\n')   # (the tips point at a row's name: its value stays in sight)
f.shot('b2', opn + 't14.txt="Bank 2"\nt8.txt="Rate 2"\n')   # (the bank switch moved to bank 2: with the link on, rate 2 too)
f.line('title', "Rotorflight settings. What the transmitter needs to know about this model's flight controller.")
f.line('page', 'This is the Rotorflight settings page. Touch a white box to type a new value.')
f.line('link', "Link rates and banks: when it's on, the bank switch sets the rates too. The switch is saved as soon as you touch it.")
f.line('version', "Rotorflight version: what the receiver reports from the flight controller, two point two or two point three. You can't type it.")
f.line('arming', 'Arming channel: the channel the safety switch drives, usually six. Safety off arms the flight controller.')
f.line('ratio', "Gear ratio is for a Version one receiver only. With a Version two receiver, set Rotorflight's own gear ratio in First time basics.")
f.line('basics', 'First time basics: four pages that set up a new model, from the swash type to the throttle calibration.')
f.line('calibrate', 'Calibrate teaches the flight controller which way is level, for self levelling and rescue.')
f.line('ok', 'OK saves these with the model, and takes you back to the Rotorflight menu.')
f.line('linktip', "Here's a handy one. With Link rates and banks on, one switch does both. See the top left: bank two, and rate two. So a calm bank gets calm rates, and a sporty bank lively ones.")
f.line('armtip', "Model won't arm? The arming line on the Rotorflight menu tells you why. And check that Arm, on Rotorflight's Switches page, uses this same channel.")
f.line('v0tip', "And if the version reads nought point nought, it isn't known yet, so the safety switch won't arm the model. Switch the model on: it fills in by itself once the flight controller answers.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Settings ...', 'p')
f.say('page', 'Rotorflight settings.')
f.point(*at('RFSetupView', 'sw0'), 'link', 'Link rates and banks.')
f.point(*at('RFSetupView', 't5'), 'version', 'Rotorflight version.')
f.point(*at('RFSetupView', 'Arming'), 'arming', 'Arming channel.')
f.point(*at('RFSetupView', 'Ratio'), 'ratio', 'Gear ratio: Version 1 receivers.')
f.point(*at('RFSetupView', 'b5'), 'basics', 'First-time basics.')
f.point(*at('RFSetupView', 'b6'), 'calibrate', 'Calibrate: the level.')
f.point(*at('RFSetupView', 'b4'), 'ok', 'OK saves.')
f.show('b2'); f.point(*at('RFSetupView', 't3'), 'linktip', 'Tip: one switch for both.')
f.point(*at('RFSetupView', 't6'), 'armtip', "Tip: won't arm? Check this.")
f.show('v0'); f.point(*at('RFSetupView', 't4'), 'v0tip', 'Tip: 0.0? Switch the model on.')
f.end(); f.finish()
