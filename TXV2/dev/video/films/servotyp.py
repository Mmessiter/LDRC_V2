#!/usr/bin/env python3
"""Film SERVOTYP: servo types, a tour. The words are SERVOTYP.TXT's; the way in is Model setup > Options > Servo types.
Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, FRONT_NO_MODEL
f = Film('SERVOTYP', 'Servo types', 'Pulse rate and centre, for unusual servos')
model_route(f, 'Options')
f.shot('opt', prefix('9.txt', '9_open')); f.shot('p', prefix('34.txt', '34_open'))
f.line('title', 'Servo types. Pulse rate and centre, for unusual servos.')
f.line('opt', 'This is the Model options page. Press Servo types.')
f.line('page', "This page is for servos that need a pulse rate or a centre pulse other than the usual fifty hertz and fifteen hundred microseconds. Check the servo's instructions.")
f.line('box', 'Touch a box to type a new value.')
f.line('defaults', 'Defaults sets fifty hertz and fifteen hundred microseconds on every channel.')
f.line('pairs', 'Pairs marked with stars share one timer in the receiver, so each pair runs at one rate.')
f.line('v1', 'These are for the servo outputs of a Version one receiver. A Version two receiver ignores them.')
f.line('ok', 'OK saves the values, sends them to the receiver, and goes to the front page.')
f.line('end', "That's the Servo types page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Options', 'opt')
f.say('opt', 'Press Servo types.', after=0.3); f.tap(*at('RXOptionsView', 'b0'), 'p')
f.say('page', 'Servo types.')
f.point(*at('ServosTypeView', 'n0'), 'box', 'Touch a box.')
f.point(*at('ServosTypeView', 'b0'), 'defaults', 'Defaults.')
f.point(*at('ServosTypeView', 'legend'), 'pairs', 'Shared timers.')
f.cap = None; f.say('v1', 'Version 1 receivers only.')
f.point(*at('ServosTypeView', 'b10'), 'ok', 'OK saves and sends.')
f.end('end'); f.finish()
