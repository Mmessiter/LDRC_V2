#!/usr/bin/env python3
"""Film BUDDY: the wireless buddy box, a tour. The words are BUDDY.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, FRONT_NO_MODEL
f = Film('BUDDY', 'Wireless buddy', 'Teaching a beginner to fly')
tx_route(f, 'Buddy')
f.shot('p', prefix('16.txt', '16_open')); f.shot('m', prefix('16.txt', '16_master'))   # (Instructor on: the switch positions and Buddy channels appear)
f.line('title', 'Wireless buddy. Dual control, for teaching beginners to fly.')
f.line('page', "This is the Wireless buddy page. The instructor and the pupil fly one model. The instructor's buddy switch gives the pupil control. Move it back, and the instructor flies again at once.")
f.line('first', "First, on the instructor's transmitter: store the model's I D, send the model to the pupil, and give a switch the Buddy job.")
f.line('master', "Then, here, turn Instructor on.")
f.line('positions', 'Under Buddy switch, choose who flies at Down, Middle and Up: Master, Nudge, or Buddy.')
f.line('channels', 'Buddy channels: turn on the channels the pupil may fly.')
f.line('pupil', "On the pupil's transmitter, receive the model from the instructor, then turn Pupil on here.")
f.line('ok', 'On either transmitter, OK saves, and goes to the front page.')
f.line('end', "That's the Wireless buddy page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
tx_route_play(f, 'Buddy', 'p')
f.say('page', 'Wireless buddy.')
f.cap = None; f.say('first', 'First: model ID, send the model, a Buddy switch.')
f.point(*at('BuddyView', 'BuddyM'), 'master', 'Instructor: on.'); f.tap(*at('BuddyView', 'BuddyM')); f.under('m'); f.hold(0.8)
f.point(*at('BuddyView', 'cb0'), 'positions', 'Who flies at each position.')
f.point(*at('BuddyView', 'b0'), 'channels', "The pupil's channels.")
f.point(*at('BuddyView', 'BuddyP'), 'pupil', "The pupil's transmitter: Pupil on.")
f.point(*at('BuddyView', 'b10'), 'ok', 'OK saves.')
f.end('end'); f.finish()
