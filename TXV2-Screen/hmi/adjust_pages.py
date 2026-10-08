#!/usr/bin/env python3
"""The In-flight adjustments page of the transmitter (screen 1.11.35, B72): sd/hmi/pages/67.json (AdjustView), one
adjustment at a time, in the style of the Rescue pages (hmi/rescue_pages.py). The Setting and the Channel are 'pick'
rows (< and > through a long list); the values' labels are set by the main board for the kind in hand. Re-run after a
change here: python3 hmi/adjust_pages.py (then hmi/rfmenu_pages.py for the menu's button)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp   # (importing it re-makes the rescue pages: harmless)
# codes (the main board's NumberedFunctions1): 116 open, 117 OK, 118 save, 119 a number edited, 120 setting >, 121 setting <,
# 122 channel >, 123 channel <, 124 kind tapped, 125 bank tapped, 126 previous, 127 next, 128 add, 129 remove
rp.page(67, 'AdjustView', 'Adjustment 1 of 1', [
    ('tn0', 'Setting', 0, 0, 'pick', 120, 121), ('tn1', 'Channel', 0, 1, 'pick', 122, 123),
    ('tn2', 'Kind', 0, 2, 'cycle', 124), ('tn3', 'In bank', 1, 2, 'cycle', 125),
    ('tn4', 'Low end value', 0, 3, 'num', 119, 'Value'), ('tn5', 'High end value', 1, 3, 'num', 119, 'Value'),
    ('tn6', 'Position 3 value', 0, 4, 'num', 119, 'Value'), ('tn7', 'Now', 1, 4, 'info', 0),
    ('tn8', 'Channel now', 0, 5, 'info', 0),
], [('b3', 'Save', 14, 120, 118), ('b4', '< Prev', 142, 120, 126), ('b2', 'Next >', 270, 120, 127), ('b5', 'Add', 398, 120, 128), ('b6', 'Remove', 526, 120, 129), ('b1', 'OK', 654, 120, 117)], 'ADJUST.TXT')
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
pg = json.load(open(os.path.join(rp.PAGES, '67.json')))
if 67 not in {x['id'] for x in idx['pages']}: idx['pages'].append({'id': 67, 'name': 'AdjustView', 'n': len(pg['comps'])}); idx['pages'].sort(key=lambda x: x['id'])
for x in idx['pages']:
    if x['id'] == 67: x['n'] = len(pg['comps'])
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
