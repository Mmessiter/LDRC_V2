#!/usr/bin/env python3
"""Film RFGOVG: the governor settings shared by every bank, a tour. The words are RFGOVG.TXT's. Made with
dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, rf_route, rf_route_play, keypad_shots, KEY
f = Film('RFGOVG', 'Governor (global)', 'The mode, the throttle and the timings')
rf_route(f, 'Governor ...')
f.shot('g', prefix('6.txt', '6_open')); f.shot('p', prefix('5.txt', '5_open')); f.shot('e', prefix('5.txt', '5_edited'))
f.line('title', 'Governor global. The mode, the throttle and the timings, shared by every bank.')
f.line('g', 'This is the Governor page. Press Global.')
f.line('page', 'This page has the governor settings shared by every bank.')
f.line('mode', 'Governor mode: nought to four. Three, ELECTRIC, is the full governor for an electric helicopter.')
f.line('handover', 'Handover: above this throttle the governor takes over, and spools up to the bank\'s head speed.')
f.line('ttype', 'Throttle type: nought, NORMAL, is the usual.')
f.line('spool', 'Spool up: the time to reach head speed. Higher is gentler.')
f.line('save', 'Save writes the values, checks and stores them. Then the flight controller restarts, because Rotorflight reads these only as it starts.')
f.line('copy', 'Keep a copy stores these values in the model\'s file on the transmitter\'s card. Restore writes that copy back.')
f.line('ok', 'OK goes back to the Rotorflight page.')
f.line('end', "That's the Governor global page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Governor ...', 'g')
f.say('g', 'Press Global.', after=0.3); f.tap(*at('RFGovView', 'b2'), 'p')
f.say('page', 'Governor (global).')
f.point(*at('RFGovViewGlbl', 'n14'), 'mode', 'Governor mode.')
f.point(*at('RFGovViewGlbl', 'n15'), 'handover', 'Handover.')
f.point(*at('RFGovViewGlbl', 'n28'), 'ttype', 'Throttle type.')
f.point(*at('RFGovViewGlbl', 'n17'), 'spool', 'Spool-up.')
f.under('e'); f.hold(0.6); f.point(*at('RFGovViewGlbl', 'b3'), 'save', 'Save, then a restart.')
f.point(*at('RFGovViewGlbl', 'b2'), 'copy', 'Keep a copy; Restore.')
f.point(*at('RFGovViewGlbl', 'b1'), 'ok', 'OK.')
f.end('end'); f.finish()
