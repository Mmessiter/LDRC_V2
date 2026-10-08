#!/usr/bin/env python3
"""The Mixer pages of the transmitter (screen 1.11.34, B66; the "Travel extents" of B57): sd/hmi/pages/62.json (TravelView),
63.json (Travel2View) and 66.json (Travel3View), laid out as the Rotorflight configurator 2.3's Mixer tab - its four
sections, their names, their order (Malcolm, 8 Oct: photographs of the two side by side). Page 1: Main Rotor Settings and
Swashplate Trims; page 2: Main Rotor Geometry; page 3: Tail Rotor Settings. Swashplate type, main rotor direction and the
tail rotor type are told, not changed, as on the configurator's selects. Re-run after a change here."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp
# codes: 83 open, 84 OK, 85 save, 86 a number edited, 87/88/89 aileron / elevator / collective reversed, 90 next (1>2),
# 91 previous (2>1), 108 yaw reversed, 109 next (2>3), 110 previous (3>2)
rp.page(62, 'TravelView', 'Mixer (Rotorflight)', [
    ('h0', 'Main Rotor Settings', 0, 0, 'head', 0),
    ('i0', 'Swashplate Type', 0, 1, 'info', 0), ('i1', 'Main Rotor Direction', 0, 2, 'info', 0),
    ('tn6', 'Aileron reversed', 0, 3, 'switch', 87), ('tn7', 'Elevator reversed', 0, 4, 'switch', 88),
    ('tn8', 'Collective reversed', 0, 5, 'switch', 89),
    ('h1', 'Swashplate Trims', 1, 0, 'head', 0),
    ('tn9', 'Roll trim [%]', 1, 1, 'num', 86), ('tn10', 'Pitch trim [%]', 1, 2, 'num', 86), ('tn11', 'Collective trim [%]', 1, 3, 'num', 86),
], [('b3', 'Save', 14, 180, 85), ('b2', 'Next >', 408, 180, 90), ('b1', 'OK', 605, 180, 84)], 'TRAVEL.TXT')
rp.page(63, 'Travel2View', 'Mixer: main rotor geometry', [
    ('h0', 'Main Rotor Geometry', 0, 0, 'head', 0),
    ('tn0', 'Cyclic calibration [%]', 0, 1, 'num', 86), ('tn1', 'Collective calib. [%]', 0, 2, 'num', 86, 'Collective calibration [%]'),
    ('tn2', 'Geometry correction [%]', 0, 3, 'num', 86, 'Collective geometry correction [%]'),
    ('tn3', 'Cyclic pitch limit [deg]', 0, 4, 'num', 86, 'Cyclic blade pitch limit [deg]'),
    ('tn4', 'Collective pitch limit [deg]', 0, 5, 'num', 86, 'Collective blade pitch limit [deg]'),
    ('tn5', 'Total pitch limit [deg]', 0, 6, 'num', 86, 'Total blade pitch limit [deg]'),
    ('tn6', 'Swash phase angle [deg]', 0, 7, 'num', 86, 'Swashplate phase angle [deg]'),
    ('tn7', 'Positive tilt corr. [%]', 1, 1, 'num', 86, 'Positive collective tilt correction'),
    ('tn8', 'Negative tilt corr. [%]', 1, 2, 'num', 86, 'Negative collective tilt correction'),
], [('b3', 'Save', 14, 180, 85), ('b4', '< Previous', 208, 180, 91), ('b2', 'Next >', 402, 180, 109), ('b1', 'OK', 596, 180, 84)], 'TRAVEL2.TXT')
rp.page(66, 'Travel3View', 'Mixer: tail rotor', [
    ('h0', 'Tail Rotor Settings', 0, 0, 'head', 0),
    ('i0', 'Tail rotor type', 0, 1, 'info', 0),
    ('tn0', 'Yaw reversed', 0, 2, 'switch', 108),
    ('tn1', 'Yaw center trim', 0, 3, 'num', 86), ('tn2', 'Yaw calibration [%]', 0, 4, 'num', 86),
    ('tn3', 'Yaw limit CW [deg]', 0, 5, 'num', 86, 'CW yaw blade angle limit [deg]'),
    ('tn4', 'Yaw limit CCW [deg]', 0, 6, 'num', 86, 'CCW yaw blade angle limit [deg]'),
    ('tn5', 'Motor idle throttle [%]', 0, 7, 'num', 86),
], [('b3', 'Save', 14, 180, 85), ('b2', '< Previous', 408, 180, 110), ('b1', 'OK', 605, 180, 84)], 'TRAVEL3.TXT')
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
have = {x['id']: x for x in idx['pages']}
for pid, name in ((62, 'TravelView'), (63, 'Travel2View'), (66, 'Travel3View')):
    n = len(json.load(open(os.path.join(rp.PAGES, '%d.json' % pid)))['comps'])
    if pid in have: have[pid]['n'] = n
    else: idx['pages'].append({'id': pid, 'name': name, 'n': n})
idx['pages'].sort(key=lambda x: x['id'])
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
