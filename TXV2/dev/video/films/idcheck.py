#!/usr/bin/env python3
"""Film IDCHECK: checking the stored IDs, a tour. The words are IDCHECK.TXT's; the way in is Model setup > Model IDs >
Check for duplicates. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, FRONT_NO_MODEL
f = Film('IDCHECK', 'Checking the model IDs', 'Every stored ID, and any stored twice')
model_route(f, 'Model IDs', spoken='Model I Ds')
f.shot('ids', prefix('3.txt', '3_open')); f.shot('p', prefix('46.txt', '46_open'))
f.line('title', 'Checking the model I Ds. Every stored I D, and any stored twice.')
f.line('ids', 'This is the Model I Ds page. Press Check for duplicates.')
f.line('page', "This list shows every model memory with its stored I D. Each line shows the model's number, its name, and its stored I D. I D OK means no other model has that I D.")
f.line('dups', "Duplicates counts the models whose I D is also stored with another model. It should be nought.")
f.line('why', 'A duplicate can make automatic model selection load the wrong model memory. Best avoided!')
f.line('ok', 'OK goes to the Model I Ds page, to store or delete an I D.')
f.line('end', "That's how to check the model I Ds.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Model IDs', 'ids')
f.say('ids', 'Press Check for duplicates.', after=0.3); f.tap(*at('IDsStartView', 'b3'), 'p')
f.say('page', 'Every stored ID.')
f.point(*at('IDsView', 'n0'), 'dups', 'Duplicates: should be 0.')
f.cap = None; f.say('why', 'Duplicates: best avoided.')
f.point(*at('IDsView', 'b10'), 'ok', 'OK: Model IDs.')
f.end('end'); f.finish()
