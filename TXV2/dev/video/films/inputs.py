#!/usr/bin/env python3
"""Film INPUTS: what moves each channel, a tour. The words are INPUTS.TXT's; with the model connected, Inputs asks first
(scenario 4_q_inputs: "The model is connected. Changes here move its controls. Open Inputs anyway?"). Made with
dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, FRONT_CONNECTED
f = Film('INPUTS', 'Inputs', 'What moves each channel')
model_route(f, 'Inputs')
f.shot('ask', prefix('4.txt', '4_q_inputs'))
f.shot('p', prefix('39.txt', '39_open'))
f.line('title', 'Inputs. What moves each channel, its name, and its output.')
f.line('ask', 'With the model connected, it asks first: changes here move its controls. Press OK.')
f.line('page', 'This is the Inputs page. Touch a number or a name to change it.')
f.line('in', 'In: the stick, switch or knob that moves this channel. One is the aileron stick, two elevator, three throttle, four rudder.')
f.line('name', "Name: the channel's name, up to ten letters. Other pages show it too.")
f.line('trim', 'Trim out: which channels each trim moves.')
f.line('ok', 'OK keeps the changes, and goes back to Model setup.')
f.line('end', "That's the Inputs page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
f.show('r_front'); f.say('front', 'Press Model.', after=0.3); f.tap(*at('FrontView', 'b1'), 'r_setup')
f.say('setup', 'Press Inputs.', after=0.3); f.tap(*at('RXSetupView', txt='Inputs'), 'ask')
f.say('ask', 'Press OK.', after=0.3); f.tap(*at('PopupView', 'b0'), 'p')
f.say('page', 'Inputs.')
f.point(*at('InputsView', 'c1'), 'in', 'In: what moves it.')
f.point(*at('InputsView', 'ch1'), 'name', 'Its name.')
f.point(*at('InputsView', 'n0'), 'trim', 'Trim out.')
f.point(*at('InputsView', 'b10'), 'ok', 'OK keeps the changes.')
f.end('end'); f.finish()
