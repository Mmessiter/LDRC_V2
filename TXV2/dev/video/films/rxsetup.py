#!/usr/bin/env python3
"""Film RXSETUP: the Model setup page, a tour of its main buttons, then how pilots use it. The words are RXSETUP.TXT's (and
MODELS.TXT's for Models); every place pointed at is a button's centre from the page's own definition (sd/hmi/pages/4.json).
Made with dev/video/filmkit.py.
18 Oct 2026, Malcolm: start on Model setup, not the front page; real uses; no "That's ..." at the end."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at

f = Film('RXSETUP', 'Model setup', 'Every setting of the model in use')
f.shot('p', prefix('4.txt', '4_open'))
f.line('title', "Model setup. Every setting of the model you're flying starts here.")
f.line('page', "This is the Model setup page. You'll find it behind Model, on the front page. Each button opens a page with its own help.")
f.line('models', 'Models: choose the model to fly, and back your models up.')
f.line('options', "Options: the trims, the motor switch, the timer, the warnings, and the model's picture.")
f.line('inputs', 'Inputs: what moves each channel, its name, and its output.')
f.line('channels', 'Channels: watch every channel move, live, and shape its curve.')
f.line('ids', "Model I Ds: store the I D of this model's receiver.")
f.line('rf', "Rotorflight: the flight controller's own settings, right here on the transmitter.")
f.line('rxupd', "Receiver updates finds new software for a Version two receiver. The model must be on and connected, with the safety on. Don't worry: nothing's installed until you press Install now.")
f.line('ok', 'And OK takes you back to the front page.')
f.line('name', "Now, some real uses. Before every flight, glance up here, top left. That's the model now loaded: make sure it's the one you're about to fly!")
f.line('new1', "Setting up a new model? Here's a good order. Start with Options: set the timer and the warnings.")
f.line('new2', 'Next, Inputs and Channels. Move every stick and switch, and check each one moves the right channel.')
f.line('new3', "Flying Rotorflight? Finish with Rotorflight, for the flight controller's own settings.")
f.line('field', "Here's one many pilots miss: receiver updates work at the field, with your phone's hotspot. Add it to the transmitter's WiFi, and give it to the receiver once, with the phone app.")
f.prepare()

f.begin(); f.say('title', after=1.2)
f.show('p'); f.say('page', 'Model setup.')
f.point(*at('RXSetupView', txt='Models'), 'models', 'Choose a model, back it up.')
f.point(*at('RXSetupView', txt='Options'), 'options', 'Trims, motor, timer, warnings.')
f.point(*at('RXSetupView', txt='Inputs'), 'inputs', 'What moves each channel.')
f.point(*at('RXSetupView', txt='Channels'), 'channels', 'Channels, live, and curves.')
f.point(*at('RXSetupView', txt='Model IDs'), 'ids', "The receiver's ID.")
f.point(*at('RXSetupView', txt='Rotorflight'), 'rf', 'The flight controller.')
f.point(*at('RXSetupView', 'ldrcRxUpdate'), 'rxupd', 'Nothing until Install now.')
f.point(*at('RXSetupView', txt='OK'), 'ok', 'Back to the front page.')
f.point(*at('RXSetupView', 'ModelName'), 'name', 'Tip: check the name first.')
f.point(*at('RXSetupView', txt='Options'), 'new1', 'Tip: a new model? 1. Options')
f.point(*at('RXSetupView', txt='Inputs'), 'new2', '2. Inputs and Channels')
f.point(*at('RXSetupView', txt='Rotorflight'), 'new3', '3. Rotorflight')
f.point(*at('RXSetupView', 'ldrcRxUpdate'), 'field', 'Tip: update at the field.')
f.end(); f.finish()
