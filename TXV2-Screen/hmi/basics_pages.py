#!/usr/bin/env python3
"""The Model basics pages of the transmitter (screen 1.11.62, B99): sd/hmi/pages/77.json (BasicsView) and 78.json
(Basics2View, the gear ratios), reached from the Rotorflight settings page (hmi/rfmenu_pages.py, "Model basics ..."); then
(screen 1.11.63, B100) 79.json (PortsView: the flight controller's UART ports, their labels and functions written by the
main board, RF_Basics.h) and 80.json (EscCalView: the ESC throttle calibration, RF_EscCal.h - told rows, a status line
the main board writes, one button whose words it changes: "Full throttle" / "Minimum").
What the Mixer pages only tell, and the phone app's First-time basics set: the swashplate type, which way the rotor turns,
the tail rotor type (the configurator's Mixer tab selects), the ESC signal (motor protocol), the ESC brand (its telemetry
protocol), the motor's pole count, and the main and tail gear ratios as the configurator's two numbers each (Motor tab).
The five choices are 'wide' rows: a tap steps to the next (RF_Basics.h); the longest words sit in the 7th element.
Re-run after a change here: python3 hmi/basics_pages.py"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp
# codes (the main board's NumberedFunctions1): 183 open (from the settings page), 184 OK, 185 save, 186 swashplate type tapped,
# 187 rotor direction, 188 tail type, 189 ESC signal, 190 ESC brand, 191 a number typed, 192 Next > (1>2), 193 < Previous (2>1);
# B100: 194 Next > (2>3), 195 < Previous (3>2), 196-201 a port's function tapped (rows 1-6), 202 Next > (3>4), 203 < Previous (4>3),
# 204 Full throttle / Minimum
rp.series_begin()
rp.page(77, 'BasicsView', 'First-time basics', [
    ('tn0', 'Swash type', 0, 0, 'wide', 186, 'CCPM 120 deg'),
    ('tn1', 'Rotor turns', 0, 1, 'wide', 187, 'Anticlockwise'),
    ('tn2', 'Tail type', 0, 2, 'wide', 188, 'Bi-directional'),
    ('tn3', 'ESC signal', 0, 3, 'wide', 189, 'Normal PWM (most heli ESCs)'),
    ('tn4', 'ESC brand', 0, 4, 'wide', 190, 'Hobbywing V5'),   # (the phone's "ESC telemetry protocol" does not fit; its own help says "brand")
    ('tn5', 'Motor pole count', 0, 5, 'num', 191),
], [('b3', 'Save', 14, 180, 185), ('b2', 'Next >', 408, 180, 192), ('b1', 'OK', 605, 180, 184)], 'BASICS.TXT')
rp.page(78, 'Basics2View', 'Gear ratio', [
    ('tn0', 'Main gear ratio: rotor', 0, 0, 'num', 191),
    ('tn1', 'Main gear ratio: motor', 0, 1, 'num', 191),
    ('tn2', 'Tail gear ratio: rotor', 0, 2, 'num', 191),
    ('tn3', 'Tail gear ratio: tail', 0, 3, 'num', 191),
], [('b3', 'Save', 14, 180, 185), ('b4', '< Previous', 208, 180, 193), ('b2', 'Next >', 402, 180, 194), ('b1', 'OK', 596, 180, 184)], 'BASICS2.TXT')
rp.page(79, 'PortsView', 'Ports', [
    ('tn%d' % r, 'TELEM (UART 2)', 0, r, 'wide', 196 + r, 'Dongle on a wire (MSP)') for r in range(6)   # (the label's words set its width: the main board writes each row's real name, in the phone app's words since 15 Oct 2026 - "TELEM (UART 2)" the widest)
], [('b3', 'Save', 14, 180, 185), ('b4', '< Previous', 208, 180, 195), ('b2', 'Next >', 402, 180, 202), ('b1', 'OK', 596, 180, 184)], 'BASICS3.TXT', wide_cap=220)
rp.page(80, 'EscCalView', 'Throttle calibration', [
    ('tn0', 'Blades OFF or pinion out', 0, 0, 'info', 0),
    ('tn1', 'Flight pack UNPLUGGED. Flight controller on USB power.', 0, 1, 'info', 0),
    ('tn2', 'Safety on, nobody at the sticks', 0, 2, 'info', 0),
    ('tn3', 'Ready: tap Full throttle to begin', 0, 3, 'info', 0, 'FULL THROTTLE held: plug the flight battery in'),
], [('b2', 'Full throttle', 14, 180, 204), ('b4', '< Previous', 408, 180, 203), ('b1', 'OK', 605, 180, 184)], 'BASICS4.TXT')
rp.series_end()
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
have = {x['id']: x for x in idx['pages']}
for pid, name in ((77, 'BasicsView'), (78, 'Basics2View'), (79, 'PortsView'), (80, 'EscCalView')):
    n = len(json.load(open(os.path.join(rp.PAGES, '%d.json' % pid)))['comps'])
    if pid in have: have[pid]['n'] = n
    else: idx['pages'].append({'id': pid, 'name': name, 'n': n})
idx['pages'].sort(key=lambda x: x['id'])
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
