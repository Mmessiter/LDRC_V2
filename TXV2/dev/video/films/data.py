#!/usr/bin/env python3
"""Film DATA: Telemetry, a tour. The words are DATA.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, rf_route, rf_route_play, rfs, SAVE_SHOWN, FRONT_NO_MODEL
f = Film('DATA', 'Telemetry', 'How well the radio link is working')
model_route(f, 'Telemetry', setup_shot=prefix('4.txt', '4_open'))
f.shot('p', prefix('30.txt', '30_open'))
f.line('title', 'Telemetry. How well the radio link is working, and what the model reports.')
f.line('page', 'This is the Telemetry page. Look at it after a flight, before you switch off.')
f.line('rate', 'Frame rate: packets received each second.')
f.line('lost', 'Lost data packets: packets that did not arrive.')
f.line('gap', 'Longest comms gap: the most milliseconds before the link came back. Below about two hundred and fifty, all should be well. Normally it is well below a hundred.')
f.line('clear', 'Clear sets the counts back to nought.')
f.line('gaps', 'Gaps shows how long each reconnection took. G P S opens the G P S page.')
f.line('end', "That's the Telemetry page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Telemetry', 'p')
f.say('page', 'Telemetry.')
f.point(*at('DataView', 't2'), 'rate', 'Frame rate.')
f.point(*at('DataView', 't1'), 'lost', 'Lost packets.')
f.point(*at('DataView', 't10'), 'gap', 'Longest comms gap.')
f.point(*at('DataView', 'b0'), 'clear', 'Clear.')
f.point(*at('DataView', 'b13'), 'gaps', 'Gaps; GPS.')
f.end('end'); f.finish()
