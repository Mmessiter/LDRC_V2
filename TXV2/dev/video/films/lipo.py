#!/usr/bin/env python3
"""Film LIPO: the Batteries page - a tour, then why every new model needs its cells set here. The words are LIPO.TXT's ('Model
battery' is for the model now loaded, named at the top left; each model keeps its own; 12S with a Version 2 receiver needs
nothing more). Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the model or transmitter screen; real uses): it starts on Transmitter setup ('Batteries').
In practice: check the model's name; set the cells for every new model, or the volts per cell and the warnings are wrong;
12S with a Version 2 receiver. LiFePO4 is spoken "lithium iron phosphate", Li-ion "lithium ion"."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import tx_route, tx_route_play
from illus import Art

f = Film('LIPO', 'Batteries', 'Telling the transmitter which batteries you use')
art = Art(f)
tx_route(f, 'Batteries')
f.shot('p', prefix('51.txt', '51_open'))
f.line('title', 'Batteries. Telling the transmitter which batteries you use.')
f.line('page', "This is the Batteries page. The transmitter needs it for the percentage left, and the voltage per cell. Touch a choice, and it's saved at once.")
f.line('model', 'Model battery: two to six cells, or twelve, for the model now loaded. Each model keeps its own.')
f.line('tx', "Transmitter battery: two cells, lithium iron phosphate, or LiPo and lithium ion. That one's the same for every model.")
f.line('ok', 'OK goes back to Transmitter setup.')
f.line('name', "Here's the one to remember. The model battery is for the model named at the top left. So check the name first.")
f.line('new', 'Then, for every new model, come here and set its cells. Get it wrong, and the volts per cell, and the warnings, will be wrong too.')
f.line('why1', "Here's what can go wrong. This six-cell pack reads twenty-two point eight volts. That's three point eight volts a cell.")
f.line('why2', "Set five cells by mistake, and the transmitter thinks it's four point five six volts a cell! So your Stop flying warning would come far too late.")
f.line('twelve', "Flying on twelve cells? Choose twelve S. With a Version two receiver, that's all you need to do.")
f.prepare()

f.begin(); f.say('title', after=1.2)
tx_route_play(f, 'Batteries', 'p')
f.say('page', 'Batteries.')
f.point(*at('TypeView', 'r6s'), 'model', "The model's battery.")
f.point(*at('TypeView', 'r0'), 'tx', "The transmitter's battery.")
f.point(*at('TypeView', 'b10'), 'ok', 'OK: back to Transmitter setup.')
f.point(*at('TypeView', 'ModelName'), 'name', "Tip: check the model's name.")
f.point(*at('TypeView', 'r6s'), 'new', 'Tip: every new model.')
f.show(art.battery(0, cells=6, volts=3.8)); f.say('why1', 'Tip: 6 cells, 3.8 volts each.')
f.show(art.battery(0, cells=5, volts=4.56, title='Set to 5 cells by mistake')); f.say('why2', 'Wrong cells: a late warning.')
f.show('p'); f.point(*at('TypeView', 'r12s'), 'twelve', 'Tip: 12S, Version 2 receiver.')
f.end(); f.finish()
