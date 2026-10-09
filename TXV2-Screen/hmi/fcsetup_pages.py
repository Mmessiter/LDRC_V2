#!/usr/bin/env python3
"""The flight controller's setup pages of the transmitter (screen 1.11.40, B88): sd/hmi/pages/72.json (BatteryView),
73.json (BlackboxView), 74.json (LevelView: the V1 stick calibration page is CalibrateView) - the last of the Rotorflight settings the transmitter can make over
the pipe (Malcolm, 9 Oct: "implement all the remaining possible Rotorflight configuration options"), in the style of
the Rescue pages, worded as the receiver's own pages (rotorflight-firsttime.html's battery, rotorflight-blackbox.html,
rotorflight-calibrate.html). Re-run after a change here: python3 hmi/fcsetup_pages.py (then hmi/rfmenu_pages.py)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp
# codes (the main board's NumberedFunctions1): 155 Battery open, 156 OK, 157 Save, 158 a number typed, 159 voltage from,
# 160 current from, 176 Sensors > (B90), 177 < Battery; 161 Black box open, 162 OK, 163 Save, 164 a number typed, 165 when, 166 where, 167 how often,
# 168 overwrite the oldest, 169 erase; 170 Calibrate open, 171 OK, 172 calibrate level, 173 Save, 174 a trim typed
# B90: the FC pads' sensors on a page of their own (75), reached by "Sensors >", which the main board shows only while a
# source is FC pads - so the battery page has five rows and lays out compact (rescue_pages.compact_plan), as Malcolm asked
rp.series_begin()   # (B91: the battery and its sensors, one island)
rp.page(72, 'BatteryView', 'Battery (Rotorflight)', [
    ('h0', 'Flight pack', 0, 0, 'head', 0),
    ('tn0', 'Cells (0 = automatic)', 0, 1, 'num', 158, 'Cells'),
    ('tn1', 'Capacity [mAh]', 0, 2, 'num', 158, 'Capacity mAh'),
    ('tn2', 'Voltage from', 0, 3, 'wide', 159, 'ESC telemetry'),
    ('tn3', 'Current from', 0, 4, 'wide', 160, 'ESC telemetry'),
    ('h1', 'Each cell [V]', 1, 0, 'head', 0),
    ('tn4', 'Full', 1, 1, 'num', 158, 'Full cell volts'),
    ('tn5', 'Warning', 1, 2, 'num', 158, 'Warning cell volts'),
    ('tn6', 'Empty', 1, 3, 'num', 158, 'Empty cell volts'),
    ('tn7', 'Highest allowed', 1, 4, 'num', 158, 'Highest cell volts'),
], [('b2', 'Sensors >', 0, 0, 176), ('b3', 'Save', 0, 0, 157), ('b1', 'OK', 0, 0, 156)], 'BATTERY.TXT')
rp.page(75, 'BatSensorsView', 'Battery sensors (FC pads)', [
    ('h2', 'Voltage sensor', 0, 0, 'head', 0),
    ('tn8', 'Scale', 0, 1, 'num', 158, 'Voltage scale'),
    ('h3', 'Current sensor', 1, 0, 'head', 0),
    ('tn9', 'Scale', 1, 1, 'num', 158, 'Current scale'),
    ('tn10', 'Offset', 1, 2, 'num', 158, 'Current offset'),
], [('b2', '< Battery', 0, 0, 177), ('b3', 'Save', 0, 0, 157), ('b1', 'OK', 0, 0, 156)], 'BATTERY.TXT')
rp.series_end()
rp.page(73, 'BlackboxView', 'Black box (Rotorflight)', [
    ('h0', 'Recording', 0, 0, 'head', 0),
    ('tn0', 'When', 0, 1, 'wide', 165),
    ('tn1', 'Where', 0, 2, 'wide', 166),
    ('tn2', 'How often', 0, 3, 'wide', 167),
    ('tn3', 'After disarm [s]', 0, 4, 'num', 164, 'Seconds after disarm'),
    ('tn4', 'Overwrite oldest', 0, 5, 'switch', 168),
    ('h1', 'Memory', 1, 0, 'head', 0),
    ('tn5', '', 1, 1, 'info', 0),
    ('tn6', '', 1, 2, 'info', 0),
], [('b2', 'Erase all logs', 0, 0, 169), ('b3', 'Save', 0, 0, 163), ('b1', 'OK', 0, 0, 162)], 'BLACKBOX.TXT', busy_rect=(110, 336, 580, 70))   # (the erase's progress below the rows)
rp.page(74, 'LevelView', 'Calibrate (Rotorflight)', [
    ('h0', 'Level (accelerometer)', 0, 0, 'head', 0),
    ('tn0', '', 0, 1, 'info', 0, 'Roll -12.3   Pitch -12.3 deg'),
    ('tn1', '', 0, 2, 'info', 0, 'Not level: level it, then Calibrate'),
    ('h1', 'Level trims', 1, 0, 'head', 0),
    ('tn2', 'Pitch trim [deg]', 1, 1, 'num', 174, 'Pitch trim degrees'),
    ('tn3', 'Roll trim [deg]', 1, 2, 'num', 174, 'Roll trim degrees'),
], [('b2', 'Calibrate level', 0, 0, 172), ('b3', 'Save', 0, 0, 173), ('b1', 'OK', 0, 0, 171)], 'RFCALIB.TXT')
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
have = {x['id'] for x in idx['pages']}
for pid, name in ((72, 'BatteryView'), (75, 'BatSensorsView'), (73, 'BlackboxView'), (74, 'LevelView')):
    n = len(json.load(open(os.path.join(rp.PAGES, '%d.json' % pid)))['comps'])
    if pid not in have: idx['pages'].append({'id': pid, 'name': name, 'n': n})
    for x in idx['pages']:
        if x['id'] == pid: x['n'] = n; x['name'] = name   # (B90: 74 was renamed LevelView)
idx['pages'].sort(key=lambda x: x['id'])
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
