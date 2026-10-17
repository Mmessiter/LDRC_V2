#!/usr/bin/env python3
"""Film PONG: a game for a wet day. The words are PONG.TXT's; Pong will not start with a model connected, so the model is
off. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, rf_route, rf_route_play, rfs, SAVE_SHOWN, FRONT_NO_MODEL
f = Film('PONG', 'Pong', 'A game for a day too wet to fly')
tx_route(f, 'Raining', front_shot=FRONT_NO_MODEL)
f.shot('p', prefix('45.txt', '45_play'))
f.line('title', 'Pong. A game for a day too wet to fly.')
f.line('page', 'Move each stick up and down to move the paddle on its side. The first player to score ten points wins. A new game then starts by itself.')
f.line('note', 'Pong will not start while a model is connected. The radio is off while you play.')
f.line('ok', 'Press OK to stop playing, and go to the front page.')
f.line('end', 'Enjoy the rain.')
f.prepare()
f.begin(); f.say('title', after=1.6)
tx_route_play(f, 'Raining', 'p')
f.say('page', 'The sticks move the paddles.')
f.cap = None; f.say('note', 'No model connected.')
f.point(*at('PongView', 'b2'), 'ok', 'OK stops.')
f.end('end'); f.finish()
