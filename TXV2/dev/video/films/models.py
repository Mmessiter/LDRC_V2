#!/usr/bin/env python3
"""Film MODELS: choosing a model, then backing it up, restoring it and sharing it. The words are MODELS.TXT's; Models is
opened with no model connected (GotoModelsView asks first otherwise). The wheel rows tapped are worked out from the wheel's
own geometry (main.cpp drawList: rows of 'hig' px round the middle band; a tap turns the wheel to that row). Made with
dev/video/filmkit.py.
18 Oct 2026, Malcolm: start on Model setup; real uses (a backup before any experiment, Restore, Send to a friend)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, comp
from common import model_route, model_route_play, MODEL_PICTURE

f = Film('MODELS', 'Models', 'Choose, back up, restore and share')
model_route(f, 'Models', setup_shot=prefix('4.txt', '4_nomodel'))      # (no model connected: Models opens with no question)
models = prefix('15.txt', '15_open') + 'exp0.path="%s"\n' % MODEL_PICTURE   # (the wheel at RAW 420 MCM (3): MMems.val=2; its picture as on the front page)
f.shot('p', models)
edge = models + 'MMems.val=4\nexp0.path="sd0/images/Edge540.jpg"\nModelName.txt="Edge 540"\nmodelname.txt="Edge 540"\n'   # (the page's own box: modelname)
f.shot('edge', edge)
f.shot('edgefile', edge + 'Mfiles.val=1\nfilename.txt="EDGE540.MOD"\n')   # (its backup file chosen on the right)
def row(name, now, to, bw=3, rh=35):
    """the centre of the wheel's row 'to' places from the middle band's row 'now'"""
    x, y, w, h = comp('ModelsView', name); band = y + bw + (h - 2 * bw - rh) // 2
    return x + w // 2, band + (to - now) * rh + rh // 2
f.line('title', 'The Models page: choose a model, and keep its settings safe.')
f.line('page', 'This is the Models page. On the left, your ninety model memories. Each name ends with its number.')
f.line('files', "On the right, the backup files on the transmitter's card.")
f.line('choose', 'To fly another model, just touch it.')
f.line('chosen', 'Its picture and name show in the middle.')
f.line('ok', "Then press OK. It asks first, so you can't change model by accident.")
f.line('backup', "Now, here's a habit worth having. Once a model flies well, choose it and press Backup. Do it again before any experiment.")
f.line('restore1', 'If an experiment goes wrong, no problem. Choose its backup file, on the right.')
f.line('restore2', 'Then press Restore. It asks first, then puts the model back just as it was.')
f.line('send', 'Want to share a set-up with a friend? Send passes a backup file to their transmitter. The help shows the steps.')
f.line('check', 'And whoever gets a model should check every control before flying it.')
f.prepare()

f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Models', 'p')
f.say('page', 'Models loaded.')
f.point(*at('ModelsView', 'Mfiles'), 'files', 'Backup files.')
f.point(*row('MMems', 2, 4), 'choose', 'Touch a model.', after=0.3); f.tap(*row('MMems', 2, 4)); f.under('edge'); f.hold(0.8)
f.point(*at('ModelsView', 'exp0'), 'chosen', 'Its picture and name.')
f.point(*at('ModelsView', 'b10'), 'ok', 'OK. It asks first.')
f.point(*at('ModelsView', 'b4'), 'backup', 'Tip: back up when it flies well.')
f.point(*row('Mfiles', 0, 1), 'restore1', 'Tip: choose its backup file.', after=0.3); f.tap(*row('Mfiles', 0, 1)); f.under('edgefile'); f.hold(0.8)
f.point(*at('ModelsView', 'b5'), 'restore2', 'Tip: Restore puts it back.')
f.point(*at('ModelsView', 'b1'), 'send', 'Tip: share it with Send.')
f.cap = None; f.say('check', 'Check every control first.')
f.end(); f.finish()
