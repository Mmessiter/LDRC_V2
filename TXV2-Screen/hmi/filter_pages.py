#!/usr/bin/env python3
"""The Filters page of the transmitter (screen 1.11.28, B58): sd/hmi/pages/64.json (FilterView), in the style of the
Rescue pages, with the configurator's Gyro Filters names. Re-run after a change here."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp
# codes: 92 open, 93 OK, 94 save, 95 a number edited, 96 lowpass 1 type tapped, 97 lowpass 2 type tapped, 98 RPM preset tapped
rp.page(64, 'FilterView', 'Gyro filters (Rotorflight)', [
    ('tn0', 'Lowpass 1 type', 0, 0, 'cycle', 96), ('tn1', 'Lowpass 1 cutoff [Hz]', 0, 1, 'num', 95),
    ('tn2', 'Lowpass 2 type', 0, 2, 'cycle', 97), ('tn3', 'Lowpass 2 cutoff [Hz]', 0, 3, 'num', 95),
    ('tn12', 'RPM filter preset', 0, 4, 'cycle', 98), ('tn13', 'RPM filter min [Hz]', 0, 5, 'num', 95),
    ('tn4', 'Notch 1 center [Hz]', 0, 6, 'num', 95), ('tn5', 'Notch 1 cutoff [Hz]', 0, 7, 'num', 95),
    ('tn6', 'Notch 2 center [Hz]', 1, 0, 'num', 95), ('tn7', 'Notch 2 cutoff [Hz]', 1, 1, 'num', 95),
    ('tn8', 'Dyn notch count', 1, 2, 'num', 95), ('tn9', 'Dyn notch Q', 1, 3, 'num', 95),
    ('tn10', 'Dyn notch min [Hz]', 1, 4, 'num', 95), ('tn11', 'Dyn notch max [Hz]', 1, 5, 'num', 95),
], [('b3', 'Save', 14, 180, 94), ('b1', 'OK', 605, 180, 93)], 'FILTERS.TXT')
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
if 64 not in {x['id'] for x in idx['pages']}: idx['pages'].append({'id': 64, 'name': 'FilterView', 'n': 37}); idx['pages'].sort(key=lambda x: x['id'])
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
