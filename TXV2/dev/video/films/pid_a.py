#!/usr/bin/env python3
"""Film PID_A: PID + (advanced), a tour. The words are PID_A.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, rf_route, rf_route_play, keypad_shots, KEY
f = Film('PID_A', 'PID + (advanced)', 'The rest of the PID settings')
rf_route(f, 'PIDs ...')
f.shot('pid', prefix('40.txt', '40_open')); f.shot('p', prefix('7.txt', '7_open')); f.shot('e', prefix('7.txt', '7_edited'))
f.line('title', 'P I D plus. The rest of the P I D settings.')
f.line('pid', 'This is the P I Ds page. Press P I D plus.')
f.line('page', 'This page has the rest of the P I D settings, for the bank shown at the top left. Most models fly well on Rotorflight\'s own values. Change one only when you know why.')
f.line('touch', 'Touch a value, or its name, and type the new value.')
f.line('check', 'The keypad shows the name of the value you are changing. Check it: the wrong one is easy to touch on this crowded page.')
f.line('save', 'Save appears once you change a value. It writes, reads back to check, and stores.')
f.line('ok', 'OK leaves the page. With unsaved changes it asks first.')
f.line('end', "That's the P I D plus page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'PIDs ...', 'pid')
f.say('pid', 'Press PID +.', after=0.3); f.tap(*at('PIDView', 'b2'), 'p')
f.say('page', 'PID + (advanced).')
f.point(*at('PID_A_View', 't29'), 'touch', 'Touch a value or its name.')
f.cap = None; f.say('check', 'Check the name on the keypad.')
f.under('e'); f.hold(0.6); f.point(*at('PID_A_View', 'b3'), 'save', 'Save.')
f.point(*at('PID_A_View', 'b1'), 'ok', 'OK.')
f.end('end'); f.finish()
