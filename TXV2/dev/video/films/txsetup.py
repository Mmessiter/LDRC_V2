#!/usr/bin/env python3
"""Film TXSETUP: the Transmitter setup page - every button, in the order a new transmitter wants them, and two that help at
the field. The facts are TXSETUP.TXT's (with OPTIONS.TXT and CALIB.TXT: the stick mode is set before calibrating); every place
pointed at is a button's centre from the page's own definition (sd/hmi/pages/33.json). Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: "Let's start most at model or transmitter screen" and "describe how to use for solving real-world flying
issues"): it starts on Transmitter setup, saying once that Transmitter on the front page opens it. The four buttons a new
transmitter needs are shown in their order (System for the stick mode, Calibrate, Switches, Batteries), so each button is
pointed at once; then the rest, with the phone's hotspot for updates at the field and Scan RF for a busy band (never while
flying: the link stops while it scans). Workshop door (for workshop tools) is left out, as before."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at

f = Film('TXSETUP', 'Transmitter setup', 'The settings of the transmitter itself')
f.shot('t_setup', prefix('33.txt', '33_open'))
f.line('title', 'Transmitter setup. Everything about the transmitter itself, whichever model you fly.')
f.line('setup', "This is the Transmitter setup page. Transmitter, on the front page, opens it. These settings belong to the transmitter itself, so they're the same for every model.")
f.line('system', 'Setting up a new transmitter? Go in this order. First, System: set your stick mode, and your name. Binding and the clock are there too.')
f.line('calib', 'Then Calibrate. It teaches the transmitter where the sticks and switches end and centre, and which way the trims work.')
f.line('switches', 'Then Switches, to give each switch its job.')
f.line('batteries', "Then Batteries: the transmitter battery's type, and the model's cells. Now you're ready for your first model!")
f.line('sounds', 'Sounds, et cetera: the voices, the vario, brightness and volume.')
f.line('appearance', 'Appearance: the background picture, the themes, and your own front screens.')
f.line('buddy', 'Buddy: an instructor and a pupil fly one model, with a transmitter each.')
f.line('raining', "And Raining? That's Pong: a game for a day too wet to fly!")
f.line('wifi', "WiFi: choose your network, and type its password just once. Here's a handy one: at the field, your phone's hotspot works too.")
f.line('updates', 'So you can update the transmitter right there: the model switched off, and the safety on. Nothing installs until you press Install now.')
f.line('scan', "Scan R F shows how busy each two point four gigahertz channel is: handy at a new field. The link to the model stops while it scans, so never scan while it's flying.")
f.line('ok', 'OK goes back to the front page.')
f.prepare()

f.begin(); f.say('title', after=1.2)
f.show('t_setup'); f.say('setup', 'Transmitter setup.')
f.point(*at('TXSetupView', txt='System'), 'system', 'Tip: 1. System: stick mode.')
f.point(*at('TXSetupView', txt='Calibrate'), 'calib', '2. Calibrate.')
f.point(*at('TXSetupView', txt='Switches'), 'switches', '3. Switches.')
f.point(*at('TXSetupView', txt='Batteries'), 'batteries', '4. Batteries.')
f.point(*at('TXSetupView', txt='Sounds etc.'), 'sounds', 'Sounds, brightness, volume.')
f.point(*at('TXSetupView', txt='Appearance'), 'appearance', 'Pictures, themes, front screens.')
f.point(*at('TXSetupView', txt='Buddy'), 'buddy', 'Instructor and pupil.')
f.point(*at('TXSetupView', txt='Raining'), 'raining', 'Pong!')
f.point(*at('TXSetupView', txt='WiFi'), 'wifi', "Tip: your phone's hotspot.")
f.point(*at('TXSetupView', txt='Transmitter updates'), 'updates', 'Updates, even at the field.')
f.point(*at('TXSetupView', txt='Scan RF'), 'scan', 'Tip: how busy is the band?')
f.point(*at('TXSetupView', txt='OK'), 'ok', 'Back to the front page.')
f.end(); f.finish()
