#!/usr/bin/env python3
"""Film BUDDY: the wireless buddy box - a tour, then how to start a beginner. The words are BUDDY.TXT's (Buddy channels: the
others stay with the Instructor, whoever has control; 'Top switches too' OFF for a beginner keeps motor, safety, bank and
rates with the Instructor; Nudge: the Pupil flies, the Instructor's sticks gently nudge; the Pupil's signal lost: control
back to the Instructor after about 5 seconds). Combo options (the page's own): 0 Master, 1 Nudge, 2 Buddy. Made with
dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the model or transmitter screen; real uses): it starts on Transmitter setup. In practice:
the Buddy channels page (BuddyView "Buddy channels ..." > BuddyChView, OK back) with only aileron and elevator for the pupil
and 'Top switches too' off; Nudge as the in-between; the spring-return switch is in the set-up line."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import tx_route, tx_route_play
from illus import Art

f = Film('BUDDY', 'Wireless buddy', 'Teaching a beginner to fly')
art = Art(f)
tx_route(f, 'Buddy')
f.shot('p', prefix('16.txt', '16_open')); f.shot('m', prefix('16.txt', '16_master'))   # (Instructor on: the switch positions and Buddy channels appear)
f.shot('ch', prefix('18.txt', '18_open', [('fs3.val=1', 'fs3.val=0'), ('fs4.val=1', 'fs4.val=0'), ('mSwitch.val=1', 'mSwitch.val=0')]))   # (aileron and elevator only)
f.line('title', 'Wireless buddy. Teaching a beginner to fly, with a transmitter each.')
f.line('page', "This is the Wireless buddy page. An instructor and a pupil fly one model, with a transmitter each.")
f.line('first', "First, on the instructor's transmitter: store the model's I D, send the model to the pupil, and give the Buddy job to a spring-return switch.")
f.line('master', 'Then, here, turn Instructor on.')
f.line('positions', "Under Buddy switch, choose who flies at Down, Middle and Up: Master, that's you, Nudge, or Buddy, the pupil.")
f.line('channels', 'Buddy channels chooses which controls the pupil may fly.')
f.line('pupil', "On the pupil's transmitter, receive the model from the instructor, then turn Pupil on here.")
f.line('ok', 'On either transmitter, OK saves, and goes to the front page.')
f.line('how', "Here's how it works. Only your transmitter talks to the model. The pupil's talks to yours, and your buddy switch decides whose sticks count.")
f.line('start', "Teaching a beginner? Here's a gentle way to start. Press Buddy channels.")
f.line('chpage', 'This is the Buddy channels page. Many instructors give a beginner just aileron and elevator at first, and keep the rest themselves.')
f.line('top', 'And leave Top switches too off. Then the motor, safety, bank and rates switches stay with you.')
f.line('nudge', 'Nudge is a lovely in-between. The pupil flies, but your sticks can gently help, rather than take over.')
f.line('lost', "And if the pupil's signal is ever lost, control comes back to you by itself, in about five seconds. Or take it back at once, with your buddy switch.")
f.prepare()

f.begin(); f.say('title', after=1.2)
tx_route_play(f, 'Buddy', 'p')
f.say('page', 'Wireless buddy.')
f.cap = None; f.say('first', 'First: model ID, send it, a switch.')
f.point(*at('BuddyView', 'BuddyM'), 'master', 'Instructor: on.', after=0.3); f.tap(*at('BuddyView', 'BuddyM')); f.under('m'); f.hold(0.8)
f.point(*at('BuddyView', 'cb0'), 'positions', 'Who flies at each position.')
f.point(*at('BuddyView', 'b0'), 'channels', "The pupil's controls.")
f.point(*at('BuddyView', 'BuddyP'), 'pupil', "The pupil's transmitter: Pupil on.")
f.point(*at('BuddyView', 'b10'), 'ok', 'OK saves.')
f.show(art.buddy(0)); f.anim(art.buddy, 3.0); f.say('how', 'Tip: your switch decides.')
f.show('m'); f.point(*at('BuddyView', 'b0'), 'start', 'Tip: start with two controls.', after=0.3); f.tap(*at('BuddyView', 'b0'), 'ch')
f.point(*at('BuddyChView', 'fs1'), 'chpage', 'Aileron and elevator.')
f.point(*at('BuddyChView', 'mSwitch'), 'top', 'Top switches too: off.', after=0.3)
f.tap(*at('BuddyChView', 'b10'), 'm')
f.point(*at('BuddyView', 'cb1'), 'nudge', 'Tip: Nudge helps gently.')
f.show('m'); f.say('lost', 'Signal lost? Control comes back.')   # (the finger gone: no control in particular)
f.end(); f.finish()
