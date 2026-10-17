#!/usr/bin/env python3
"""Film ADJUST: in-flight adjustments, a tour. The words are ADJUST.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
f = Film('ADJUST', 'Adjustments', 'A knob or switch changes a setting in flight')
rf_route(f, 'Adjustments ...')
f.shot('p', rfs('67.txt', '67_knob')); f.shot('e', rfs('67.txt', '67_knob', SAVE_SHOWN))
f.line('title', 'Adjustments. A knob or a switch changes a Rotorflight setting in flight.')
f.line('page', 'This is the Adjustments page. Each adjustment is one setting, worked by one channel.')
f.line('usb', 'It needs the U S B C cable from the receiver to the flight controller. Rotorflight cannot send adjustments over the receiver\'s lead.')
f.line('step', 'The arrows beside the title step through the adjustments.')
f.line('setting', 'Tap the setting box beside Changes to choose what it changes.')
f.line('add', 'Add makes a new one. Remove deletes the one showing, after a question.')
f.line('save', 'Save writes them to the flight controller.')
f.line('ok', 'OK leaves.')
f.line('end', "That's the Adjustments page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Adjustments ...', 'p')
f.say('page', 'Adjustments.')
f.point(*at('AdjustView', 't9'), 'usb', 'The USB-C cable.')
f.point(*at('AdjustView', 'bnext'), 'step', '< and >.')
f.point(*at('AdjustView', 'tn0'), 'setting', 'What it changes.')
f.point(*at('AdjustView', 'b5'), 'add', 'Add, Remove.')
f.under('e'); f.hold(0.6); f.point(*at('AdjustView', 'b3'), 'save', 'Save.')
f.point(*at('AdjustView', 'b1'), 'ok', 'OK.')
f.end('end'); f.finish()
