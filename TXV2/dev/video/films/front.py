#!/usr/bin/env python3
"""Film FRONT: the front page, a tour of what everything on it means. The words are FRONT.TXT's (the front page's help);
every place pointed at is a component's centre from the page's own definition (sd/hmi/pages/13.json). Made with
dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at

f = Film('FRONT', 'The front page', 'What everything on it means')
f.shot('fr_front', prefix('13.txt', '13_conn', [
    ('bt0.txt="Motor is ON"\nbt0.bco=2016\nbt0.bco2=2016\nbt0.pco=0\nbt0.pco2=0', 'bt0.txt="Motor is OFF"\nbt0.bco=63488\nbt0.bco2=63488\nbt0.pco=65535\nbt0.pco2=65535'),
    ('RPM: 2150', 'RPM: 0'), ('Amps: 12.4', 'Amps: 0.3'), ('mAh: 345', 'mAh: 0'), ('ESC: 52.3', 'ESC: 21.5')]))
f.line('title', 'The front page. What everything on it means.')
f.line('front', "This is the transmitter's front page. Keep it in view while you fly.")
f.line('bank', 'Top left, the bank and the rate that your switches have chosen.')
f.line('picture', "In the middle, the model's picture. Touch it to choose another. Under it, the model's name and its number.")
f.line('bars', 'Top right, the channel bars. Each bar grows from the middle line as its control moves.')
f.line('motor', 'Under them, the motor box. It says whether the motor is on or off.')
f.line('left', 'On the left, your name. With Rotorflight, the head speed, the current, the capacity used, and the E S C temperature.')
f.line('timer', 'The big numbers are the motor timer. It runs while the motor is on, and pauses while it is off.')
f.line('batteries', "Bottom left, the batteries. T X is the transmitter's, R X the model's. Each shows its voltage, and the voltage per cell.")
f.line('link', 'Beside Connected, the link quality. Green is the data that arrived. Red is any that was lost.')
f.line('trims', 'The yellow lines down the sides and along the bottom are the four trims. The red dot on each shows where that trim is.')
f.line('setups', 'At the bottom corners, Transmitter and Model open the setups.')
f.line('defined', 'Defined screens shows your own front screen instead, with the numbers you choose, big and clear.')
f.line('end', "That's the front page.")
f.prepare()

f.begin(); f.say('title', after=1.6)
f.show('fr_front'); f.say('front', 'The front page.')
f.point(125, 32, 'bank', 'Bank and rate.')
f.point(*at('FrontView', 'exp0'), 'picture', "The model's picture and name.")
f.point(*at('FrontView', 'barcard'), 'bars', 'The channel bars.')
f.point(*at('FrontView', 'bt0'), 'motor', 'The motor box.')
f.point(125, 200, 'left', 'Your name; Rotorflight numbers.')
f.point(*at('FrontView', 'Mins'), 'timer', 'The motor timer.')
f.point(117, 343, 'batteries', 'The batteries.')
f.point(*at('FrontView', 'Quality'), 'link', 'The link quality.')
f.point(*at('FrontView', 'ch4'), 'trims', 'The four trims.')
f.point(*at('FrontView', 'b0'), 'setups', 'Transmitter and Model: the setups.')
f.point(*at('FrontView', 'ldrcDefined'), 'defined', 'Your own front screen.')
f.end('end')
f.finish()
