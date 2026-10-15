#!/usr/bin/env python3
"""The Model basics pages of the transmitter (screen 1.11.62, B99): sd/hmi/pages/77.json (BasicsView) and 78.json
(Basics2View, the gear ratios), reached from the Rotorflight settings page (hmi/rfmenu_pages.py, "Model basics ...").
What the Mixer pages only tell, and the phone app's First-time basics set: the swashplate type, which way the rotor turns,
the tail rotor type (the configurator's Mixer tab selects), the ESC signal (motor protocol), the ESC brand (its telemetry
protocol), the motor's pole count, and the main and tail gear ratios as the configurator's two numbers each (Motor tab).
The five choices are 'wide' rows: a tap steps to the next (RF_Basics.h); the longest words sit in the 7th element.
Re-run after a change here: python3 hmi/basics_pages.py"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp
# codes (the main board's NumberedFunctions1): 183 open (from the settings page), 184 OK, 185 save, 186 swashplate type tapped,
# 187 rotor direction, 188 tail type, 189 ESC signal, 190 ESC brand, 191 a number typed, 192 Next > (1>2), 193 < Previous (2>1)
rp.series_begin()
rp.page(77, 'BasicsView', 'Model basics', [
    ('tn0', 'Swash type', 0, 0, 'wide', 186, 'CCPM 120 deg'),
    ('tn1', 'Rotor turns', 0, 1, 'wide', 187, 'Anticlockwise'),
    ('tn2', 'Tail type', 0, 2, 'wide', 188, 'Bi-directional'),
    ('tn3', 'ESC signal', 0, 3, 'wide', 189, 'PWM (most heli ESCs)'),
    ('tn4', 'ESC brand', 0, 4, 'wide', 190, 'Hobbywing V5'),
    ('tn5', 'Motor pole count', 0, 5, 'num', 191),
], [('b3', 'Save', 14, 180, 185), ('b2', 'Next >', 408, 180, 192), ('b1', 'OK', 605, 180, 184)], 'BASICS.TXT')
rp.page(78, 'Basics2View', 'Model basics: gear ratios', [
    ('tn0', 'Main gear ratio: rotor', 0, 0, 'num', 191),
    ('tn1', 'Main gear ratio: motor', 0, 1, 'num', 191),
    ('tn2', 'Tail gear ratio: rotor', 0, 2, 'num', 191),
    ('tn3', 'Tail gear ratio: tail', 0, 3, 'num', 191),
], [('b3', 'Save', 14, 180, 185), ('b2', '< Previous', 408, 180, 193), ('b1', 'OK', 605, 180, 184)], 'BASICS2.TXT')
rp.series_end()
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
have = {x['id']: x for x in idx['pages']}
for pid, name in ((77, 'BasicsView'), (78, 'Basics2View')):
    n = len(json.load(open(os.path.join(rp.PAGES, '%d.json' % pid)))['comps'])
    if pid in have: have[pid]['n'] = n
    else: idx['pages'].append({'id': pid, 'name': name, 'n': n})
idx['pages'].sort(key=lambda x: x['id'])
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
