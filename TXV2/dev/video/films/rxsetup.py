#!/usr/bin/env python3
"""Film RXSETUP: the Model setup page, a tour of its main buttons. The words are RXSETUP.TXT's (and MODELS.TXT's for
Models); every place pointed at is a button's centre from the page's own definition (sd/hmi/pages/4.json). Made with
dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at

f = Film('RXSETUP', 'Model setup', 'Every setting of the model in use')
f.shot('m_front', prefix('13.txt', '13_conn', [
    ('bt0.txt="Motor is ON"\nbt0.bco=2016\nbt0.bco2=2016\nbt0.pco=0\nbt0.pco2=0', 'bt0.txt="Motor is OFF"\nbt0.bco=63488\nbt0.bco2=63488\nbt0.pco=65535\nbt0.pco2=65535'),
    ('RPM: 2150', 'RPM: 0'), ('Amps: 12.4', 'Amps: 0.3'), ('mAh: 345', 'mAh: 0'), ('ESC: 52.3', 'ESC: 21.5')]))
f.shot('m_setup', prefix('4.txt', '4_open'))
f.line('title', 'Model setup. Every setting of the model in use.')
f.line('front', "This is the transmitter's front page. Press Model.")
f.line('setup', 'This is the Model setup page. Every setting of the model in use starts here. Each button opens a page with its own help.')
f.line('models', 'Models: choose the model to use, and back models up.')
f.line('options', "Options: the trims, the motor switch, the timer, warnings, and the model's picture.")
f.line('channels', 'Channels: watch each channel move, and edit its curves.')
f.line('inputs', 'Inputs: what moves each channel, its name, and its output.')
f.line('servo', 'Servo speed slows a servo down, for flaps or an undercarriage.')
f.line('banks', 'Bank names: a name for each of the four banks.')
f.line('ids', "Model I Ds stores the I D of this model's receiver.")
f.line('rf', "Rotorflight: the flight controller's settings.")
f.line('rxupd', 'Receiver updates checks messiter dot com for the receiver. Nothing is installed until you press Install now.')
f.line('ok', 'OK goes back to the front page.')
f.line('end', "That's the Model setup page.")
f.prepare()

f.begin(); f.say('title', after=1.6)
f.show('m_front'); f.say('front', 'Press Model.', after=0.3); f.tap(*at('FrontView', 'b1'), 'm_setup')
f.say('setup', 'Model setup.')
f.point(*at('RXSetupView', txt='Models'), 'models', 'Choose a model.')
f.point(*at('RXSetupView', txt='Options'), 'options', 'Trims, motor, timer, warnings.')
f.point(*at('RXSetupView', txt='Channels'), 'channels', 'Channels and curves.')
f.point(*at('RXSetupView', txt='Inputs'), 'inputs', 'What moves each channel.')
f.point(*at('RXSetupView', txt='Servo speed'), 'servo', 'Slower servos.')
f.point(*at('RXSetupView', txt='Bank names'), 'banks', 'Names for the banks.')
f.point(*at('RXSetupView', txt='Model IDs'), 'ids', "The receiver's ID.")
f.point(*at('RXSetupView', txt='Rotorflight'), 'rf', 'The flight controller.')
f.point(*at('RXSetupView', txt='Receiver updates'), 'rxupd', 'Receiver updates.')
f.point(*at('RXSetupView', txt='OK'), 'ok', 'Back to the front page.')
f.end('end')
f.finish()
