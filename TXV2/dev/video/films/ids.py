#!/usr/bin/env python3
"""Film IDS: storing the model's receiver ID. The words are IDS.TXT's; the question and the message are Model_IDs.h's
("Store ID for <name>?", "Model ID stored."). Before, the model's number shows in square brackets: no ID stored yet.
Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, FRONT_CONNECTED
f = Film('IDS', 'Model IDs', "Storing this model's receiver ID")
model_route(f, 'Model IDs', spoken='Model I Ds', front_shot=FRONT_CONNECTED.replace('RAW 420 MCM (3)', 'RAW 420 MCM [3]'),
            setup_shot=prefix('4.txt', '4_open').replace('RAW 420 MCM (3)', 'RAW 420 MCM [3]'))
before = 'Screen_Background=8\n@model 1\npage IDsStartView\nt1.txt="RAW 420 MCM"\nt4.txt="No ID stored"\nt5.txt="4C11AE8D2F30"\n'
f.shot('p', before)
f.shot('ask', before + 'page PopupView\nDialog.txt="Store ID for RAW 420 MCM?"\n')
f.shot('msg', before + 'page PopupView\nvis b1,0\nDialog.txt="Model ID stored."\n')
f.shot('done', prefix('3.txt', '3_open'))
f.line('title', "Model I Ds. Storing this model's receiver I D.")
f.line('page', "This is the Model I Ds page. Every receiver has its own I D. With automatic model selection on, the transmitter loads the model memory that holds the I D of the model as it connects.")
f.line('stored', "Stored I D: the I D kept with this model memory. No I D stored means it has none yet. The square brackets round the model's number said so too.")
f.line('this', "This model's I D: the I D of the receiver connected now.")
f.line('store', "To store it, load the model, switch it on, and let it connect. Then press Store this model's I D.")
f.line('ask', 'It asks first. Press OK.')
f.line('msg', 'Model I D stored. Press OK.')
f.line('done', 'Now the stored I D matches the receiver.')
f.line('dupes', 'Check for duplicates lists the I D of every model memory, and finds any I D stored twice. Use it after moving a receiver.')
f.line('end', "That's how to store a model's I D.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Model IDs', 'p')
f.say('page', 'Model IDs.')
f.point(*at('IDsStartView', 't4'), 'stored', 'Stored ID: none yet.')
f.point(*at('IDsStartView', 't5'), 'this', "This model's ID.")
f.cap = None; f.say('store', "Press 'Store this model's ID'.", after=0.3); f.tap(*at('IDsStartView', 'b11'), 'ask')
f.say('ask', 'Press OK.', after=0.3); f.tap(*at('PopupView', 'b0'), 'msg')
f.say('msg', 'Model ID stored.', after=0.3); f.tap(*at('PopupView', 'b0'), 'done')
f.say('done', 'Stored.')
f.point(*at('IDsStartView', 'b3'), 'dupes', 'Check for duplicates.')
f.end('end'); f.finish()
