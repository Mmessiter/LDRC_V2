#!/usr/bin/env python3
"""Film RFCALIB: calibrating the level. The words are RFCALIB.TXT's; the question is RF_FcSetup.h's ("Is the model level and
perfectly still? (Best done on a flat desk, before the board goes into the model.)"). Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, rf_route, rf_route_play, rfs, SAVE_SHOWN, FRONT_NO_MODEL
f = Film('RFCALIB', 'Calibrate the level', 'Which way is level, for self-levelling and rescue')
rf_route(f, 'Settings ...')
f.shot('s', rfs('61.txt', '61_open')); lvl = rfs('74.txt', '74_level')
f.shot('p', lvl); f.shot('ask', lvl + 'page PopupView\nDialog.txt="Is the model level and perfectly still?\\r\\n(Best done on a flat desk, before\\r\\nthe board goes into the model.)"\n')
f.shot('done', rfs('74.txt', '74_calibrated'))
f.line('title', 'Calibrate the level. Which way is level, for self levelling and rescue.')
f.line('s', 'This is the Rotorflight settings page. Press Calibrate.')
f.line('page', 'This page teaches the flight controller which way is level. The live level is on the left. The level trims are on the right.')
f.line('flat', 'Stand the board, or the helicopter, flat and perfectly still. Best done on a flat desk, before the board goes into the model.')
f.line('press', 'Tap Calibrate level.')
f.line('ask', 'Answer OK.')
f.line('done', 'Keep it still for a few seconds, until it says Calibrated. The new level is stored in the flight controller.')
f.line('end', "That's how to calibrate the level.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Settings ...', 's')
f.say('s', 'Press Calibrate.', after=0.3); f.tap(*at('RFSetupView', 'b6'), 'p')
f.say('page', 'Calibrate.')
f.cap = None; f.say('flat', 'Flat and perfectly still.')
f.say('press', "Tap 'Calibrate level'.", after=0.3); f.tap(*at('LevelView', 'b2'), 'ask')
f.say('ask', 'Press OK.', after=0.3); f.tap(*at('PopupView', 'b0'), 'done')
f.say('done', 'Calibrated.', after=1.0)
f.end('end'); f.finish()
