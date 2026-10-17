#!/usr/bin/env python3
"""Film TXSETUP: the Transmitter setup page, a tour of its buttons. The words are TXSETUP.TXT's; every place pointed at is a
button's centre from the page's own definition (sd/hmi/pages/33.json). Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at

f = Film('TXSETUP', 'Transmitter setup', 'The settings of the transmitter itself')
f.shot('t_front', prefix('13.txt', '13_conn', [
    ('bt0.txt="Motor is ON"\nbt0.bco=2016\nbt0.bco2=2016\nbt0.pco=0\nbt0.pco2=0', 'bt0.txt="Motor is OFF"\nbt0.bco=63488\nbt0.bco2=63488\nbt0.pco=65535\nbt0.pco2=65535'),
    ('RPM: 2150', 'RPM: 0'), ('Amps: 12.4', 'Amps: 0.3'), ('mAh: 345', 'mAh: 0'), ('ESC: 52.3', 'ESC: 21.5')]))
f.shot('t_setup', prefix('33.txt', '33_open'))
f.line('title', 'Transmitter setup. The settings of the transmitter itself.')
f.line('front', "This is the transmitter's front page. Press Transmitter.")
f.line('setup', "This is the Transmitter setup page. Most of its settings are the same for every model. A model's own settings are on Model setup.")
f.line('calib', 'Calibrate sets up the sticks, switches and trims. Do this first, and again after new gimbals or a new stick mode.')
f.line('system', 'System: general settings and binding, the clock, and the advanced settings.')
f.line('sounds', 'Sounds, et cetera: the voices, sounds, the vario, brightness and volume.')
f.line('switches', 'Switches: the job of each switch.')
f.line('appearance', 'Appearance: the background picture, the themes, and your own front screen.')
f.line('batteries', "Batteries: the cells in the model's battery, and the transmitter battery's type.")
f.line('scan', 'Scan R F shows how busy each two point four gigahertz channel is. Never scan while the model flies.')
f.line('buddy', 'Buddy: an instructor and a pupil fly one model, with a transmitter each.')
f.line('raining', 'Raining is Pong, a game for a day too wet to fly.')
f.line('wifi', "WiFi: choose your network and type its password, once. At the field, your phone's hotspot will do.")
f.line('updates', 'Transmitter updates asks messiter dot com for the latest version. Nothing is installed unless you press Install now.')
f.line('ok', 'OK goes back to the front page.')
f.line('end', "That's the Transmitter setup page.")
f.prepare()

f.begin(); f.say('title', after=1.6)
f.show('t_front'); f.say('front', 'Press Transmitter.', after=0.3); f.tap(*at('FrontView', 'b0'), 't_setup')
f.say('setup', 'Transmitter setup.')
f.point(*at('TXSetupView', txt='Calibrate'), 'calib', 'Calibrate: do this first.')
f.point(*at('TXSetupView', txt='System'), 'system', 'System: settings and binding.')
f.point(*at('TXSetupView', txt='Sounds etc.'), 'sounds', 'Sounds, brightness, volume.')
f.point(*at('TXSetupView', txt='Switches'), 'switches', 'Each switch\'s job.')
f.point(*at('TXSetupView', txt='Appearance'), 'appearance', 'Pictures, themes, front screens.')
f.point(*at('TXSetupView', txt='Batteries'), 'batteries', 'The batteries.')
f.point(*at('TXSetupView', txt='Scan RF'), 'scan', 'The radio band, scanned.')
f.point(*at('TXSetupView', txt='Buddy'), 'buddy', 'Instructor and pupil.')
f.point(*at('TXSetupView', txt='Raining'), 'raining', 'Pong.')
f.point(*at('TXSetupView', txt='WiFi'), 'wifi', 'WiFi, once.')
f.point(*at('TXSetupView', txt='Transmitter updates'), 'updates', 'Updates from messiter.com.')
f.point(*at('TXSetupView', txt='OK'), 'ok', 'Back to the front page.')
f.end('end')
f.finish()
