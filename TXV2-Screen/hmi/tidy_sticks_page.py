#!/usr/bin/env python3
"""SticksView (the Channels page, not restyled): its bank name sat in a see-through box with a raised frame, so it
looked like a hollow button (Malcolm, 2026-10-03: "It might look better if it were button-coloured, even though it
isn't really a button"). Now it has the buttons' colour. Nothing else changes. Safe to run again."""
import json, os
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'hmi', 'pages', '26.json')
pg = json.load(open(P))
c = next(c for c in pg['comps'] if c['n'] == 't1')
c['sta'] = 1; c['c'].update({'bco': 54938, 'pco': 0})     # the buttons' grey, black words (the Teensy writes only its text)
json.dump(pg, open(P, 'w'), separators=(',', ':'))
print('SticksView: bank name on a button-coloured box')
