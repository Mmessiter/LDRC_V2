#!/usr/bin/env python3
"""The Travel extents pages of the transmitter (screen 1.11.27, B57): sd/hmi/pages/62.json (TravelView: the limits,
gains, directions and swash trims) and 63.json (Travel2View: the tail and the swashplate), in the style of the Rescue
pages. The names are the Rotorflight configurator's Mixer tab's. Re-run after a change here."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp
# codes: 83 open, 84 OK, 85 save, 86 a number edited, 87/88/89 aileron / elevator / collective reversed tapped, 90 next, 91 previous
rp.page(62, 'TravelView', 'Travel extents (Rotorflight)', [
    ('tn0', 'Collective pitch limit [deg]', 0, 0, 'num', 86), ('tn1', 'Cyclic pitch limit [deg]', 0, 1, 'num', 86),
    ('tn2', 'Total pitch limit [deg]', 0, 2, 'num', 86), ('tn3', 'Collective gain [%]', 0, 3, 'num', 86),
    ('tn4', 'Cyclic gain [%]', 0, 4, 'num', 86), ('tn5', 'Yaw gain [%]', 0, 5, 'num', 86),
    ('tn6', 'Aileron reversed', 1, 0, 'switch', 87), ('tn7', 'Elevator reversed', 1, 1, 'switch', 88),
    ('tn8', 'Collective reversed', 1, 2, 'switch', 89),
    ('tn9', 'Swash trim roll [%]', 1, 3, 'num', 86), ('tn10', 'Swash trim pitch [%]', 1, 4, 'num', 86), ('tn11', 'Swash trim coll. [%]', 1, 5, 'num', 86),
], [('b3', 'Save', 14, 180, 85), ('b2', 'Next >', 408, 180, 90), ('b1', 'OK', 605, 180, 84)], 'TRAVEL.TXT')
rp.page(63, 'Travel2View', 'Tail and swash (Rotorflight)', [
    ('tn0', 'Tail yaw min [deg]', 0, 0, 'num', 86), ('tn1', 'Tail yaw max [deg]', 0, 1, 'num', 86),
    ('tn2', 'Tail center trim', 0, 2, 'num', 86), ('tn3', 'Tail motor idle [%]', 0, 3, 'num', 86),
    ('tn4', 'Phase angle [deg]', 1, 0, 'num', 86), ('tn5', 'Swash ring [%]', 1, 1, 'num', 86),
    ('tn6', 'Geo correction', 1, 2, 'num', 86), ('tn7', 'Tilt corr. pos [%]', 1, 3, 'num', 86), ('tn8', 'Tilt corr. neg [%]', 1, 4, 'num', 86),
], [('b3', 'Save', 14, 180, 85), ('b2', '< Previous', 408, 180, 91), ('b1', 'OK', 605, 180, 84)], 'TRAVEL2.TXT')
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
have = {x['id'] for x in idx['pages']}
for pid, name, n in ((62, 'TravelView', 34), (63, 'Travel2View', 28)):
    if pid not in have: idx['pages'].append({'id': pid, 'name': name, 'n': n})
idx['pages'].sort(key=lambda x: x['id'])
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
