#!/usr/bin/env python3
"""Film GPS: the GPS page, a tour. The words are GPS.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, rf_route, rf_route_play, rfs, SAVE_SHOWN, FRONT_NO_MODEL
f = Film('GPS', 'GPS', 'Where the model is, how fast and how high')
model_route(f, 'Telemetry', setup_shot=prefix('4.txt', '4_open'))
f.shot('d', prefix('30.txt', '30_open')); f.shot('p', prefix('52.txt', '52_open'))
f.line('title', 'G P S. Where the model is, how fast, and how high.')
f.line('d', 'This is the Telemetry page. Press G P S.')
f.line('page', 'This page needs a G P S sensor in the model, on a Version one receiver. The Version two receiver does not send G P S data.')
f.line('mark', 'Mark here remembers where the model is now. Mark the take off spot before you fly: the page then tells you how far the model went, and which way is back.')
f.line('yards', 'Yards to mark, and heading to mark.')
f.line('zero', 'Zero alt makes the present altitude zero. Press it with the model on the ground.')
f.line('ok', 'OK goes back.')
f.line('end', "That's the G P S page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Telemetry', 'd')
f.say('d', 'Press GPS.', after=0.3); f.tap(*at('DataView', 'b1'), 'p')
f.say('page', 'GPS: a Version 1 receiver.')
f.point(*at('GPSView', 'b1'), 'mark', 'Mark here.')
f.point(*at('GPSView', 't26'), 'yards', 'Yards and heading to mark.')
f.point(*at('GPSView', 'b2'), 'zero', 'Zero alt.')
f.point(*at('GPSView', 'b10'), 'ok', 'OK.')
f.end('end'); f.finish()
