#!/usr/bin/env python3
"""Film IMAGE: choosing the model's picture, then adding your own photo from a phone. The words are IMAGE.TXT's; the chooser
is the screen's own (lib/LdrcPics), its places from its own geometry (picButton: 14 + i x 197, 414, 180 x 56; picArrow +1:
754, 110, 44 x 190; picQr: 36, 82, 256 x 256). It keeps the front page start (allowed for this film): touching the
model's picture there is the quickest way in. The model's picture on the front page is Bthundr1 (common.MODEL_PICTURE), so
the chooser opens on it; the photo received is the renderer's own photo RAW420MC (sd/images/IMG_RAW420). Made with
dev/video/filmkit.py.
18 Oct 2026, Malcolm: real uses (a picture for each model shows at a glance which model is loaded; your own photo)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import FRONT_CONNECTED

def button(i): return 14 + i * 197 + 90, 414 + 28
f = Film('IMAGE', 'Model picture', 'A picture for every model')
f.shot('front', FRONT_CONNECTED)
base = prefix('14.txt', '14_page')
f.shot('c', base + '@pics pick Bthundr1\n')                         # (the chooser on the model's own picture, page 1 of 4)
f.shot('receive', base + '@pics receive\n')                         # Add photo: the code for the phone
f.shot('received', base + '@pics received\n')                       # the photo arrived, chosen
f.shot('done', FRONT_CONNECTED + 'exp0.path="sd0/images/IMG_RAW420.jpg"\n')
f.line('title', 'Model picture. Give every model a picture of its own.')
f.line('front', "This is the front page. The quickest way to change a model's picture? Just touch it. Or press Model picture, on Model setup's Options page.")
f.line('page', 'This is the picture chooser. Touch a picture to choose it, then press OK. Cancel keeps the one the model had.')
f.line('arrows', "The arrows at the sides turn the pages. The page number's at the top.")
f.line('photo', "Best of all, use a photo of your own model. Here's how. Press Add photo.")
f.line('scan', "This is the Add a photo page. Scan the code with your phone's camera. On the phone, choose a photo, fit it in the frame, and send it to the transmitter.")
f.line('wifi', "Your phone must be on the same WiFi as the transmitter. And while the model could fly, the WiFi stays off: the page tells you what to do first.")
f.line('received', "Here it comes, already chosen. Press OK to use it.")
f.line('glance', "And here's the real use: one glance at the front page tells you which model's loaded, before you fly.")
f.prepare()
f.begin(); f.say('title', after=1.2)
f.show('front'); f.say('front', 'Touch the picture.', after=0.3); f.tap(*at('FrontView', 'exp0'), 'c')
f.say('page', 'The picture chooser.')
f.point(754 + 22, 110 + 95, 'arrows', 'The pages.')
f.point(*button(0), 'photo', 'Tip: your own photo.', after=0.3); f.tap(*button(0), 'receive')
f.point(36 + 128, 82 + 128, 'scan', 'Tip: scan it with your phone.')
f.cap = None; f.say('wifi', 'Same WiFi as the transmitter.')
f.show('received'); f.say('received', 'Press OK.', after=0.3); f.tap(*button(3), 'done')
f.point(*at('FrontView', 'exp0'), 'glance', 'Tip: one glance, the right model.')
f.end(); f.finish()
