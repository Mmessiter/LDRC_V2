#!/usr/bin/env python3
"""Film LIPO: which batteries, a tour. The words are LIPO.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, FRONT_NO_MODEL
f = Film('LIPO', 'Batteries', 'Telling the transmitter which batteries you use')
tx_route(f, 'Batteries')
f.shot('p', prefix('51.txt', '51_open'))
f.line('title', 'Batteries. Telling the transmitter which batteries you use.')
f.line('page', 'This is the Batteries page. The transmitter needs this for the percentage left, and the voltage per cell. Touch a choice: it is saved at once.')
f.line('model', "Model battery: two to six cells, or twelve, for the model now loaded. Each model keeps its own.")
f.line('tx', 'Transmitter battery: two cells, LiFePO4, or LiPo and Li-ion. It is the same for every model.')
f.line('twelve', 'For twelve cells, choose twelve S. A Version two receiver needs nothing more.')
f.line('ok', 'OK goes back to Transmitter setup.')
f.line('end', "That's the Batteries page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
tx_route_play(f, 'Batteries', 'p')
f.say('page', 'Batteries.')
f.point(*at('TypeView', 'r6s'), 'model', "The model's battery.")
f.point(*at('TypeView', 'r1'), 'tx', "The transmitter's battery.")
f.point(*at('TypeView', 'r12s'), 'twelve', '12S.')
f.point(*at('TypeView', 'b10'), 'ok', 'OK.')
f.end('end'); f.finish()
