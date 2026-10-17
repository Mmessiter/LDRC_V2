#!/usr/bin/env python3
"""Film BASICS4: the ESC's throttle calibration. The words are BASICS4.TXT's; held is scenario 80_held. Made with
dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, rf_route, rf_route_play, rfs, SAVE_SHOWN, FRONT_NO_MODEL
f = Film('BASICS4', 'Throttle calibration', "Teaching the ESC the throttle range")
rf_route(f, 'Settings ...')
f.shot('s', rfs('61.txt', '61_open')); f.shot('b', rfs('77.txt', '77_ready')); f.shot('b2', rfs('77.txt', '78_ready')); f.shot('b3', rfs('77.txt', '79_ready'))
held = rfs('77.txt', '80_held'); ready = held.replace('tn3.txt="FULL THROTTLE held: plug the flight battery in"\nb2.txt="Minimum"', 'tn3.txt="Ready: tap Full throttle to begin"\nb2.txt="Full throttle"')
assert ready != held
f.shot('p', ready); f.shot('held', held)
f.shot('ask', ready + 'page PopupView\nDialog.txt="Blades OFF or pinion out? Flight pack\\r\\nUNPLUGGED? Flight controller on USB power?\\r\\nIt holds FULL throttle until you tap\\r\\n\'Minimum\'. Plug the flight battery in\\r\\nonce it is held."\n')
f.line('title', 'Throttle calibration. Teaching the E S C the throttle range Rotorflight sends.')
f.line('s', 'This is the Rotorflight settings page. Press First time basics, then Next, three times.')
f.line('before', 'Before you start: blades off, or the pinion out of the main gear. The flight pack unplugged, the flight controller on U S B power. Safety on, and nobody at the sticks.')
f.line('full', 'Tap Full throttle.')
f.line('ask', 'It asks you to check. Press OK.')
f.line('heldnow', 'The fourth line says full throttle held.')
f.line('plug', 'Plug the flight pack in. The E S C sees full throttle as it wakes, and beeps to say it has learned the top.')
f.line('min', 'Then tap Minimum. The E S C learns the bottom.')
f.line('end', "That's the throttle calibration.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Settings ...', 's')
f.say('s', 'First-time basics, then Next three times.', after=0.3); f.tap(*at('RFSetupView', 'b5'), 'b'); f.tap(*at('BasicsView', 'b2'), 'b2'); f.tap(*at('Basics2View', 'b2'), 'b3'); f.tap(*at('PortsView', 'b2'), 'p')
f.say('before', 'Blades off; pack unplugged; safety on.')
f.cap = None; f.say('full', "Tap 'Full throttle'.", after=0.3); f.tap(*at('EscCalView', 'b2'), 'ask')
f.say('ask', 'Check, then OK.', after=0.3); f.tap(*at('PopupView', 'b0'), 'held')
f.point(*at('EscCalView', 'tn3'), 'heldnow', 'Full throttle, held.')
f.cap = None; f.say('plug', 'Plug the pack in: the ESC beeps.')
f.point(*at('EscCalView', 'b2'), 'min', 'Minimum.')
f.end('end'); f.finish()
