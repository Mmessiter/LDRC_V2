#!/usr/bin/env python3
"""The Servos page of the transmitter (screen 1.11.24, B55): sd/hmi/pages/60.json (ServoView), one servo at a time, in
the style of the Rescue pages (hmi/rescue_pages.py, which also keeps the Rotorflight menu). Re-run after a change here."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp   # (importing it re-makes the rescue pages and the menu: harmless)
# codes (the main board's NumberedFunctions1): 73 open, 74 OK, 75 save, 76 a number edited, 77 Reverse tapped, 78 Geometry tapped, 79 previous servo, 80 next servo
# Polish (10 Oct 2026): sentence case and British spelling, the keypad asking in the same words. 15 Oct 2026 (Malcolm: "use
# the same terminology that we used in the phone app"): the phone's Servos page's words, its long ones in the keypad's question; the title "Servos (Rotorflight)" until the main board writes "Servo 1 of 4 (Rotorflight)" (and so
# the help is "Servos (Rotorflight) help": it is the help for every servo, not servo 1's)
rp.page(60, 'ServoView', 'Servos (Rotorflight)', [
    ('tn0', 'Centre (subtrim)', 0, 0, 'num', 76, 'Centre (subtrim) (us)'),
    ('tn1', 'Travel limit low', 0, 1, 'num', 76, 'Travel limit, low side (us)'),
    ('tn2', 'Travel limit high', 0, 2, 'num', 76, 'Travel limit, high side (us)'),
    ('tn3', 'Throw low side', 0, 3, 'num', 76, 'Throw for full input, low side (us)'),
    ('tn4', 'Throw high side', 0, 4, 'num', 76, 'Throw for full input, high side (us)'),
    ('tn5', 'Update rate (Hz)', 1, 0, 'num', 76), ('tn6', 'Slow-motion (ms)', 1, 1, 'num', 76, 'Slow-motion time (ms)'),
    ('tn7', 'Reversed', 1, 2, 'switch', 77), ('tn8', 'Geometry correction', 1, 3, 'switch', 78),   # (the phone's "Swash geometry correction" does not fit the large rows)
], [('b3', 'Save', 14, 180, 75), ('b4', '< Servo', 214, 180, 79), ('b2', 'Servo >', 414, 180, 80), ('b1', 'OK', 605, 180, 74)], 'SERVOS.TXT')
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
if 60 not in {x['id'] for x in idx['pages']}: idx['pages'].append({'id': 60, 'name': 'ServoView', 'n': 28}); idx['pages'].sort(key=lambda x: x['id'])
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
