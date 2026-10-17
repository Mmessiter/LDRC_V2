#!/usr/bin/env python3
"""Film GAPS: reconnection times, a tour. The words are GAPS.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, rf_route, rf_route_play, rfs, SAVE_SHOWN, FRONT_NO_MODEL
f = Film('GAPS', 'Reconnection times', 'A quick way to judge the link')
model_route(f, 'Telemetry', setup_shot=prefix('4.txt', '4_open'))
f.shot('d', prefix('30.txt', '30_open')); f.shot('p', prefix('38.txt', '38_open'))
f.line('title', 'Reconnection times. How long the radio link took to come back each time it was lost.')
f.line('d', 'This is the Telemetry page. Press Gaps.')
f.line('page', 'Look at this after landing, not while flying.')
f.line('column', 'Each column is one range of times, in milliseconds, written under it. The number under a column: how many reconnections took that long.')
f.line('percent', 'The per cent above a column: its share of all reconnections.')
f.line('colours', 'Green columns, under a hundred milliseconds, are normal. Amber and red are long gaps.')
f.line('times', 'Along the bottom: the shortest, average and longest times. The longest may have happened only once or twice.')
f.line('end', "That's the reconnection times page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Telemetry', 'd')
f.say('d', 'Press Gaps.', after=0.3); f.tap(*at('DataView', 'b13'), 'p')
f.say('page', 'After landing.')
f.point(*at('GapsView', 't1'), 'column', 'Each range of times.')
f.point(*at('GapsView', 't13'), 'percent', 'Its share.')
f.cap = None; f.say('colours', 'Green is normal.')
f.point(*at('GapsView', 't14'), 'times', 'Shortest, average, longest.')
f.end('end'); f.finish()
