#!/usr/bin/env python3
"""Film AUDIO: Sounds and brightness - a tour, then how the voices, the volume and the vario help in flight. The words are
AUDIO.TXT's (the vario: sine waves climbing, sawtooth sinking; it needs a pressure sensor in the model's receiver, which a
Version 2 receiver has not, so a Version 1 receiver with one fitted). Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the model or transmitter screen; real uses): it starts on Transmitter setup ('Sounds etc.').
In practice: Timer voice and Bank voice keep your eyes on the model; the volume up at a noisy field (the sliders work at once:
shown sliding); the vario lets a glider pilot hear lift."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, knob
from common import tx_route, tx_route_play

f = Film('AUDIO', 'Sounds and brightness', 'What the transmitter says, and how loud')
tx_route(f, 'Sounds etc.', spoken='Sounds, et cetera')
base = prefix('55.txt', '55_open')                                   # (volume 60, the vario off)
f.shot('p', base)
f.shot('v75', base + 'Ex1.val=75\n'); f.shot('v90', base + 'Ex1.val=90\n')
f.shot('vario', base + 'Ex1.val=90\nc2.val=1\n')                       # (the vario switched on)
f.line('title', 'Sounds and brightness. What the transmitter says, how loud it is, and how bright the screen is.')
f.line('page', 'This is the Sounds and brightness page. Touch a switch to turn a sound on or off. The sliders work at once.')
f.line('timer', 'Timer voice says each minute of the motor timer, up to ten.')
f.line('bank', 'Bank voice says the bank or rate when you change it. And motor on or off, and safety on or off.')
f.line('connected', 'Connected voice says when the model connects and disconnects.')
f.line('start', 'Start and close sounds: a little tune as you switch on and off.')
f.line('clicks', 'Trim change clicks: a click for each trim step, with a different beep at the centre and the end.')
f.line('vario', 'Vario tones tell you whether the model is climbing or sinking.')
f.line('bright', "Then the screen's brightness, and the volume.")
f.line('ok', 'OK keeps all your choices.')
f.line('eyes', "Here's why the voices matter. With Timer voice on, you hear each minute, so you never need to look down at the timer.")
f.line('eyes2', 'Bank voice does the same for your switches: you hear every bank change. So your eyes stay on the model, where they belong.')
f.line('noisy', 'Flying at a noisy field? Turn the volume up.')
f.line('glider', "Fly a glider? Vario tones let you hear lift. Climbing sounds smooth; sinking sounds harsh. You'll need a Version one receiver with a pressure sensor.")
f.prepare()

f.begin(); f.say('title', after=1.2)
tx_route_play(f, 'Sounds etc.', 'p')
f.say('page', 'Sounds and brightness.')
f.point(*at('AudioView', 'c3'), 'timer', 'Timer voice.')
f.point(*at('AudioView', 'c4'), 'bank', 'Bank voice.')
f.point(*at('AudioView', 'c5'), 'connected', 'Connected voice.')
f.point(*at('AudioView', 'c0'), 'start', 'Start and close sounds.')
f.point(*at('AudioView', 'c1'), 'clicks', 'Trim change clicks.')
f.point(*at('AudioView', 'c2'), 'vario', 'Vario tones.')
f.point(*knob('AudioView', 'h0', 80), 'bright', 'Brightness and volume.')   # (on the brightness knob, at 80)
f.point(*at('AudioView', 'b10'), 'ok', 'OK keeps your choices.')
f.point(*at('AudioView', 'c3'), 'eyes', 'Tip: eyes on the model.')
f.point(*at('AudioView', 'c4'), 'eyes2', 'Hear the bank, too.')
k60, k75, k90 = knob('AudioView', 'Ex1', 60), knob('AudioView', 'Ex1', 75), knob('AudioView', 'Ex1', 90)
f.point(*k60, 'noisy', 'Tip: louder at a noisy field.', after=0.3)
f.press(); f.hold(0.3); f.slide([('v75', k75[0]), ('v90', k90[0])], k60[1]); f.hold(0.4); f.lift(); f.hold(0.8)
f.show('vario'); f.point(*at('AudioView', 'c2'), 'glider', 'Tip: hear the lift.')
f.end(); f.finish()
