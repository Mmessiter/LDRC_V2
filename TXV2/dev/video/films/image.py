#!/usr/bin/env python3
"""Film IMAGE: choosing the model's picture. The words are IMAGE.TXT's; the chooser is the screen's own (lib/LdrcPics), its
places from its own geometry (picTile: 49 + col x 178, 72 + row x 144, a thumbnail of 160 x 100 in a border of 4; picButton:
14 + i x 197, 414, 180 x 56; picArrow +1: 754, 110, 44 x 190). The front page's picture opens it. Made with
dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import FRONT_CONNECTED

def tile(slot): col, row = slot % 4, slot // 4; return 49 + col * 178 + 84, 72 + row * 144 + 54
def button(i): return 14 + i * 197 + 90, 414 + 28
f = Film('IMAGE', 'Model picture', 'Choosing the picture shown for this model')
f.shot('front', FRONT_CONNECTED)
chooser = prefix('14.txt', '14_chooser')                          # (page 3 of 4: Raw420 chosen, Tri770 in slot 5)
f.shot('c', chooser); f.shot('c_tri', chooser + '@pics pick Tri770\n')
f.shot('done', FRONT_CONNECTED + 'exp0.path="sd0/images/Tri770.jpg"\n')
f.line('title', 'Model picture. Choosing the picture shown for this model.')
f.line('front', "This is the front page. Touch the model's picture to choose another.")
f.line('page', 'This is the picture chooser.')
f.line('arrows', 'The arrows at the sides turn the pages, numbered at the top.')
f.line('add', 'To add your own photo, press Add photo, and follow the steps on the screen. The phone must be on the same WiFi as the transmitter.')
f.line('choose', 'Touch a picture.')
f.line('ok', 'Then press OK. Cancel keeps the picture the model had.')
f.line('done', 'The front page shows the new picture.')
f.line('end', "That's how to choose a model's picture.")
f.prepare()
f.begin(); f.say('title', after=1.6)
f.show('front'); f.say('front', 'Touch the picture.', after=0.3); f.tap(*at('FrontView', 'exp0'), 'c')
f.say('page', 'The picture chooser.')
f.point(754 + 22, 110 + 95, 'arrows', 'The pages.')
f.point(*button(0), 'add', 'Your own photo: Add photo.')
f.cap = None; f.say('choose', 'Touch a picture.', after=0.3); f.tap(*tile(5)); f.under('c_tri'); f.hold(0.8)
f.say('ok', 'Press OK.', after=0.3); f.tap(*button(3), 'done')
f.say('done', 'The new picture.', after=1.0)
f.end('end'); f.finish()
