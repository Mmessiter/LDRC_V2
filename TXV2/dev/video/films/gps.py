#!/usr/bin/env python3
"""Film GPS: the GPS page, a tour, then how a pilot uses it: mark the take-off spot, bring a model home from out of sight,
find one that came down. The facts are GPS.TXT's ('Heading' is the way the model is moving, 'Heading to mark' the way from
the model back to the mark; 'Telemetry ...' goes back to Telemetry, OK to Model setup: TXV1B main.cpp "DataEnd"). The
Telemetry page here shows a Version 1 receiver (the V2 receiver sends no GPS) and so no Rotorflight numbers.
Made with dev/video/filmkit.py. 18 Oct 2026, Malcolm: "describe how to use for solving real-world flying issues." """
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('GPS', 'GPS', 'Where the model is, how fast and how high')
model_route(f, 'Telemetry')
f.shot('d', prefix('30.txt', '30_open') + 'Sbus.txt="TRX:2 PWM:8"\nalt.txt="0 RPM"\nMaxAlt.txt="0.0 C"\nTemp.txt="0.0 C"\n')
opn = prefix('52.txt', '52_open')                 # (heading 214.6, heading to mark 34.6: flying straight away from the mark)
f.shot('p', opn)
f.shot('home', opn + 'Bear.txt="35.8"\nDist.txt="48.3"\nSped.txt="18.1"\n')   # (turned for home: the two headings agree)
f.line('title', 'G P S. Where the model is, how fast, and how high.')
f.line('d', 'This is the Telemetry page. Press G P S.')
f.line('page', "This is the G P S page. It needs a G P S sensor in the model, wired to a Version one receiver. The Version two receiver doesn't send G P S data.")
f.line('fix', 'G P S fix says Yes once it has a fix. The first one can take a few minutes, so be patient.')
f.line('where', "Below: where the model is, which way it's moving, and how fast. Distances are in yards, speeds in miles an hour, and heights in feet.")
f.line('mark', 'Mark here remembers where the model is now.')
f.line('yards', 'From then on, these measure from the mark: how far away the model is, the way back, and the furthest it went.')
f.line('zero', 'Zero alt makes the present height nought. Press it with the model on the ground, and the heights then show how far above that spot it is.')
f.line('back', 'Telemetry goes back to the Telemetry page, and OK to Model setup.')
f.line('habit', "Here's a good habit. Before take-off, with the model on its spot, press Mark here, and Zero alt too.")
f.line('lost1', "Then, if a model ever drifts out of sight, this page can bring it home. Heading to mark is the way from the model back to the mark.")
f.line('lost2', "Steer until the model's own Heading matches it. Now Yards to mark falls: it's coming home.")
f.line('ground', "And if it comes down out of sight, while it's still connected, Latitude and Longitude show where it is. Your phone's map will lead you there.")
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Telemetry', 'd')
f.say('d', 'Press GPS.', after=0.3); f.tap(*at('DataView', 'b1'), 'p')
f.say('page', 'GPS: a Version 1 receiver.')
f.point(*at('GPSView', 't20'), 'fix', 'GPS fix.')
f.point(*at('GPSView', 't22'), 'where', 'Where, which way, how fast.')
f.point(*at('GPSView', 'b1'), 'mark', 'Mark here.')
f.point(*at('GPSView', 't26'), 'yards', 'Measured from the mark.')
f.point(*at('GPSView', 'b2'), 'zero', 'Zero alt.')
f.point(*at('GPSView', 'b0'), 'back', 'Telemetry; OK.')
f.point(*at('GPSView', 'b1'), 'habit', 'Tip: mark the take-off spot.')
f.point(*at('GPSView', 't6'), 'lost1', 'Tip: out of sight?')
f.under('home'); f.hold(0.6)
f.point(*at('GPSView', 't17'), 'lost2', 'Tip: match the two headings.')
f.point(*at('GPSView', 't22'), 'ground', 'Tip: down out of sight?')
f.end(); f.finish()
