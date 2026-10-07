#!/usr/bin/env python3
"""The Servos page of the transmitter (screen 1.11.24, B55): sd/hmi/pages/60.json (ServoView), one servo at a time, in
the style of the Rescue pages (hmi/rescue_pages.py, which also keeps the Rotorflight menu). Re-run after a change here."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp   # (importing it re-makes the rescue pages and the menu: harmless)
# codes (the main board's NumberedFunctions1): 73 open, 74 OK, 75 save, 76 a number edited, 77 Reverse tapped, 78 Geometry tapped, 79 previous servo, 80 next servo
rp.page(60, 'ServoView', 'Servo 1 (Rotorflight)', [
    ('tn0', 'Center [us]', 0, 0, 'num', 76), ('tn1', 'Min [us]', 0, 1, 'num', 76), ('tn2', 'Max [us]', 0, 2, 'num', 76),
    ('tn3', 'Scale Neg [us]', 0, 3, 'num', 76), ('tn4', 'Scale Pos [us]', 0, 4, 'num', 76),
    ('tn5', 'Rate [Hz]', 1, 0, 'num', 76), ('tn6', 'Speed [ms]', 1, 1, 'num', 76),
    ('tn7', 'Reverse', 1, 2, 'cycle', 77), ('tn8', 'Geometry Corr.', 1, 3, 'cycle', 78),
], [('b3', 'Save', 14, 180, 75), ('b4', '< Servo', 214, 180, 79), ('b2', 'Servo >', 414, 180, 80), ('b1', 'OK', 605, 180, 74)], 'SERVOS.TXT')
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
if 60 not in {x['id'] for x in idx['pages']}: idx['pages'].append({'id': 60, 'name': 'ServoView', 'n': 28}); idx['pages'].sort(key=lambda x: x['id'])
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
