#!/usr/bin/env python3
"""Film MODELS: choosing a model to fly. The words are MODELS.TXT's; the question is ModelViewEnd's (MenuOptions.h: "Select
<name>?"); Models is opened with no model connected (GotoModelsView asks first otherwise). The wheel row tapped is worked out
from the wheel's own geometry (main.cpp drawList: rows of 'hig' px round the middle band; a tap turns the wheel to that
row). Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, comp
from common import FRONT_NO_MODEL, MODEL_PICTURE

f = Film('MODELS', 'Models', 'Choosing a model to fly')
f.shot('mo_front', FRONT_NO_MODEL)
f.shot('mo_setup', prefix('4.txt', '4_nomodel'))
models = prefix('15.txt', '15_open') + 'exp0.path="%s"\n' % MODEL_PICTURE   # (the wheel at RAW 420 MCM (3): MMems.val=2; its picture as on the front page)
f.shot('mo_models', models)
edge = models + 'MMems.val=4\nexp0.path="sd0/images/Edge540.jpg"\nModelName.txt="Edge 540"\nmodelname.txt="Edge 540"\n'   # (the page's own box: modelname)
f.shot('mo_edge', edge)
f.shot('mo_ask', edge + 'page PopupView\nDialog.txt="Select Edge 540?"\n')
f.shot('mo_done', FRONT_NO_MODEL + 'ModelName.txt="Edge 540 (5)"\nexp0.path="sd0/images/Edge540.jpg"\n')
x, y, w, h = comp('ModelsView', 'MMems'); bw, row = 3, 35                # (the wheel: border 3, rows of 35)
band = y + bw + (h - 2 * bw - row) // 2
edge_row = (x + w // 2, band + (4 - 2) * row + row // 2)                # Edge 540 (5): two rows below RAW 420 MCM (3)
f.line('title', 'Models. Choosing a model to fly.')
f.line('front', 'This is the front page, with the model switched off. Press Model.')
f.line('setup', 'This is the Model setup page. Press Models.')
f.line('page', 'This is the Models page. On the left, the models loaded: ninety model memories. Each name ends with its number.')
f.line('files', "On the right, the backup files on the transmitter's card.")
f.line('backup', 'Backup copies the chosen model into a backup file. Back up each model once it is set up well.')
f.line('choose', 'To choose a model, touch it in Models loaded.')
f.line('chosen', 'Its picture and name show in the middle.')
f.line('ok', 'Then press OK.')
f.line('ask', 'It asks first. OK takes the new model. Cancel keeps the old one.')
f.line('done', 'The front page now shows the model you chose.')
f.line('end', "That's how to choose a model.")
f.prepare()

f.begin(); f.say('title', after=1.6)
f.show('mo_front'); f.say('front', 'Press Model.', after=0.3); f.tap(*at('FrontView', 'b1'), 'mo_setup')
f.say('setup', 'Press Models.', after=0.3); f.tap(*at('RXSetupView', txt='Models'), 'mo_models')
f.say('page', 'Models loaded.')
f.point(*at('ModelsView', 'Mfiles'), 'files', 'Backup files.')
f.point(*at('ModelsView', 'b4'), 'backup', 'Back up each model.')
f.cap = None; f.say('choose', 'Touch a model.', after=0.3); f.tap(*edge_row); f.under('mo_edge'); f.hold(0.8)
f.point(*at('ModelsView', 'exp0'), 'chosen', 'Its picture and name.')
f.say('ok', 'Press OK.', after=0.3); f.tap(*at('ModelsView', 'b10'), 'mo_ask')
f.say('ask', 'OK: the new model. Cancel: the old one.', after=0.3); f.tap(*at('PopupView', 'b0'), 'mo_done')
f.say('done', 'The model you chose.', after=1.0)
f.end('end')
f.finish()
