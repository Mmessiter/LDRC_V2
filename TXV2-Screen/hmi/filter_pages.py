#!/usr/bin/env python3
"""The Gyro filters pages of the transmitter (screen 1.11.30, B61): sd/hmi/pages/64.json (FilterView) and 65.json
(Filter2View), laid out as the configurator 2.3's Gyro tab - its section names, field names, order and units, the plain
view on page 1 and its expert-mode items on page 2 (Malcolm, 7 Oct: "use the same names in the same places").
Every section has the configurator's Enable: for a lowpass or a notch that is its values (type 0 / 0 Hz = off), for the
dynamic filter and the RPM filter it is Rotorflight's feature bit, which only a restart applies. Re-run after a change."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp
# codes (the main board's NumberedFunctions1): 92 open, 93 OK, 94 save, 95 a number edited, 96 lowpass 1 type, 97 lowpass 2 type,
# 98 RPM strength, 99 lowpass 1 enable, 100 RPM filter enable, 101 dynamic filter enable, 102 next page, 103 previous page,
# 104 lowpass 2 enable, 105 dynamic cutoff enable, 106 notch 1 enable, 107 notch 2 enable
rp.series_begin()   # (B91: one island, one size of row, for the series)
rp.page(64, 'FilterView', 'Gyro filters (Rotorflight)', [
    ('h0', 'Lowpass Filter', 0, 0, 'head', 0),
    ('tn0', 'Enable', 0, 1, 'switch', 99), ('tn1', 'Filter type', 0, 2, 'cycle', 96),
    ('tn2', 'Cutoff frequency [Hz]', 0, 3, 'num', 95, 'Lowpass cutoff [Hz]'),
    ('h1', 'RPM Filter', 0, 4, 'head', 0),
    ('tn3', 'Enable', 0, 5, 'switch', 100), ('tn4', 'Strength', 0, 6, 'cycle', 98),
    ('tn5', 'Minimum frequency [Hz]', 0, 7, 'num', 95, 'RPM filter minimum [Hz]'),
    ('h2', 'Dynamic Filter', 1, 0, 'head', 0),
    ('tn6', 'Enable', 1, 1, 'switch', 101), ('tn7', 'Notch count', 1, 2, 'num', 95),
    ('tn8', 'Notch Q', 1, 3, 'num', 95), ('tn9', 'Notch minimum [Hz]', 1, 4, 'num', 95),
    ('tn10', 'Notch maximum [Hz]', 1, 5, 'num', 95),
], [('b3', 'Save', 14, 180, 94), ('b2', 'Next >', 408, 180, 102), ('b1', 'OK', 605, 180, 93)], 'FILTERS.TXT')
rp.page(65, 'Filter2View', 'Gyro filters: expert', [   # in the configurator's expert order (Malcolm, 8 Oct: "grouped differently"): lowpass 1's dynamic cutoff, lowpass 2, the notches
    ('h1', 'Lowpass 1: Dynamic Cutoff', 0, 0, 'head', 0),
    ('tn3', 'Enable', 0, 1, 'switch', 105), ('tn4', 'Min cutoff [Hz]', 0, 2, 'num', 95, 'Dynamic min cutoff [Hz]'),
    ('tn5', 'Max cutoff [Hz]', 0, 3, 'num', 95, 'Dynamic max cutoff [Hz]'),
    ('h0', 'Lowpass Filter 2', 0, 4, 'head', 0),
    ('tn0', 'Enable', 0, 5, 'switch', 104), ('tn1', 'Filter type', 0, 6, 'cycle', 97),
    ('tn2', 'Cutoff frequency [Hz]', 0, 7, 'num', 95, 'Lowpass 2 cutoff [Hz]'),
    ('h2', 'Notch Filter 1', 1, 0, 'head', 0),
    ('tn6', 'Enable', 1, 1, 'switch', 106), ('tn7', 'Center frequency [Hz]', 1, 2, 'num', 95, 'Notch 1 center [Hz]'),
    ('tn8', 'Cutoff frequency [Hz]', 1, 3, 'num', 95, 'Notch 1 cutoff [Hz]'),
    ('h3', 'Notch Filter 2', 1, 4, 'head', 0),
    ('tn9', 'Enable', 1, 5, 'switch', 107), ('tn10', 'Center frequency [Hz]', 1, 6, 'num', 95, 'Notch 2 center [Hz]'),
    ('tn11', 'Cutoff frequency [Hz]', 1, 7, 'num', 95, 'Notch 2 cutoff [Hz]'),
], [('b3', 'Save', 14, 180, 94), ('b2', '< Previous', 408, 180, 103), ('b1', 'OK', 605, 180, 93)], 'FILTERS2.TXT')
rp.series_end()
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
have = {x['id']: x for x in idx['pages']}
for pid, name in ((64, 'FilterView'), (65, 'Filter2View')):
    n = len(json.load(open(os.path.join(rp.PAGES, '%d.json' % pid)))['comps'])
    if pid in have: have[pid]['n'] = n
    else: idx['pages'].append({'id': pid, 'name': name, 'n': n})
idx['pages'].sort(key=lambda x: x['id'])
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
