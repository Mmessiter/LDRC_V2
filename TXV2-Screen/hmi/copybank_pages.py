#!/usr/bin/env python3
"""The Copy a bank page of the transmitter (screen card files, B78): sd/hmi/pages/71.json (CopyBankView) - the
receiver's own page (rotorflight-copybank.html) on the transmitter: the source and target banks (tap to step), the five
switches (flight tuning, rates, governor gains, head speed too, adjust gains for head speed), and the button that names
the copy. Re-run after a change here: python3 hmi/copybank_pages.py (then hmi/rfmenu_pages.py for the menu's button)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp
# codes (the main board's NumberedFunctions1): 145 open, 146 OK, 147 copy, 148 the source bank, 149 the target bank,
# 150 flight tuning, 151 rates, 152 governor gains, 153 head speed too, 154 adjust gains for head speed
rp.page(71, 'CopyBankView', 'Copy a bank', [
    ('tn0', 'From', 0, 0, 'cycle', 148), ('tn1', 'To', 1, 0, 'cycle', 149),
    ('h0', 'What to copy', 0, 1, 'head', 0),
    ('tn2', 'PIDs, PID+ and rescue', 0, 2, 'switch', 150), ('tn3', 'Rates', 1, 2, 'switch', 151),
    ('tn4', 'Governor gains', 0, 3, 'switch', 152), ('tn5', 'Head speed too', 1, 3, 'switch', 153),
    ('tn6', 'Scale gains to rpm', 0, 4, 'switch', 154),
], [('b3', 'Copy bank 1 to bank 2', 14, 420, 147), ('b1', 'OK', 605, 180, 146)], 'COPYBANK.TXT')
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
pg = json.load(open(os.path.join(rp.PAGES, '71.json')))
if 71 not in {x['id'] for x in idx['pages']}: idx['pages'].append({'id': 71, 'name': 'CopyBankView', 'n': len(pg['comps'])}); idx['pages'].sort(key=lambda x: x['id'])
for x in idx['pages']:
    if x['id'] == 71: x['n'] = len(pg['comps'])
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
