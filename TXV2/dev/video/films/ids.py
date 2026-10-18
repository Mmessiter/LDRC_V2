#!/usr/bin/env python3
"""Film IDS: storing the model's receiver ID, then why it pays. The words are IDS.TXT's; the question and the message are
Model_IDs.h's ("Store ID for <name>?", "Model ID stored."). Before, the model's number shows in square brackets: no ID
stored yet. Made with dev/video/filmkit.py.
18 Oct 2026, Malcolm: start on Model setup; real uses (AMS loads the right model; after moving a receiver)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('IDS', 'Model IDs', "Storing this model's receiver ID")
model_route(f, 'Model IDs', spoken='Model I Ds', setup_shot=prefix('4.txt', '4_open').replace('RAW 420 MCM (3)', 'RAW 420 MCM [3]'))
before = 'Screen_Background=8\n@model 1\npage IDsStartView\nt1.txt="RAW 420 MCM"\nt4.txt="No ID stored"\nt5.txt="4C11AE8D2F30"\n'
f.shot('p', before)
f.shot('ask', before + 'page PopupView\nDialog.txt="Store ID for RAW 420 MCM?"\n')
f.shot('msg', before + 'page PopupView\nvis b1,0\nDialog.txt="Model ID stored."\n')
f.shot('done', prefix('3.txt', '3_open'))
f.line('title', "Model I Ds. Teach the transmitter to recognise this model.")
f.line('page', "This is the Model I Ds page. Every receiver has its own I D, and this page keeps it with the model memory.")
f.line('stored', "Stored I D: the I D kept with this model. No I D stored means it hasn't got one yet. That's what the square brackets round the model's number meant.")
f.line('this', "This model's I D: the receiver that's connected right now.")
f.line('store', "To store it, load the model, switch it on, and let it connect. Then press Store this model's I D.")
f.line('ask', 'It asks first. Press OK.')
f.line('msg', 'Model I D stored. Press OK.')
f.line('done', 'And there it is: the stored I D now matches the receiver.')
f.line('dupes', 'Check for duplicates lists every stored I D, and finds any I D stored twice.')
f.line('ams', "Here's why it's worth doing. Store it once, and with A M S on, this model loads by itself whenever it connects. No more flying with the wrong model's settings!")
f.line('amson', 'A M S is switched on in Transmitter setup, under System.')
f.line('moved', 'Moved a receiver to another model? Store its I D again with the new one. Storing it here does not remove it from the old model.')
f.line('moved2', 'So then press Check for duplicates, and delete the I D from the model that should not have it.')
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Model IDs', 'p')
f.say('page', 'Model IDs.')
f.point(*at('IDsStartView', 't4'), 'stored', 'Stored ID: none yet.')
f.point(*at('IDsStartView', 't5'), 'this', "This model's ID.")
f.point(*at('IDsStartView', 'b11'), 'store', "Press 'Store this model's ID'.", after=0.3); f.tap(*at('IDsStartView', 'b11'), 'ask')
f.say('ask', 'Press OK.', after=0.3); f.tap(*at('PopupView', 'b0'), 'msg')
f.say('msg', 'Model ID stored.', after=0.3); f.tap(*at('PopupView', 'b0'), 'done')
f.say('done', 'Stored.')
f.point(*at('IDsStartView', 'b3'), 'dupes', 'Check for duplicates.')
f.point(*at('IDsStartView', 't4'), 'ams', 'Tip: store it once.')
f.cap = None; f.say('amson', 'AMS: Transmitter setup, System.')
f.point(*at('IDsStartView', 'b11'), 'moved', 'Tip: moved it? Store it again.')
f.point(*at('IDsStartView', 'b3'), 'moved2', 'Tip: then check for duplicates.')
f.end(); f.finish()
