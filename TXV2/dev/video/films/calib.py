#!/usr/bin/env python3
"""Film CALIB: calibrating the sticks. The route and the words are the firmware's and CALIB.TXT's: front page > Transmitter >
Calibrate (refused while a model is connected) > "Calibrate sticks etc." > move everything to its ends > Next > centre
everything, the four top edge switches AWAY from you > Finish > "Calibration saved." Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix

f = Film('CALIB', 'Calibrating the sticks', 'The first job on a new transmitter')
f.shot('c_front', prefix('13.txt', '13_nomodel'))
f.shot('c_setup', prefix('33.txt', '33_open'))
f.shot('c_cal', prefix('22.txt', '22_open'))
s1 = prefix('22.txt', '22_step1')
f.shot('c_s1a', s1)
f.shot('c_s1b', s1 + 'Ch1.val=0\nCh2.val=100\nCh3.val=0\nCh4.val=100\nCh5.val=0\nCh6.val=0\nCh7.val=100\nCh8.val=100\n')
f.shot('c_s1c', s1 + 'Ch1.val=80\nCh2.val=20\nCh3.val=65\nCh4.val=35\nCh5.val=100\nCh6.val=50\nCh7.val=0\nCh8.val=50\n')
f.shot('c_s2', prefix('22.txt', '22_step2'))
f.shot('c_done', prefix('22.txt', '22_done'))
f.line('title', 'Calibrating the sticks. The first job on a new transmitter.')
f.line('front', "This is the transmitter's front page. Switch off any model first: calibration will not start while one is connected.")
f.line('presstx', 'Press Transmitter.')
f.line('setup', 'This is the Transmitter setup page. Press Calibrate.')
f.line('cal', 'This is the Calibration page. Press Calibrate sticks, et cetera.')
f.line('step1', 'Now move both sticks, and the front switches or knobs, to all their extreme positions, several times. The bars show each one moving.')
f.line('next', 'Then press Next.')
f.line('step2', 'Now centre both sticks, the throttle stick too, and the front switches or knobs. Push the four switches on the top edge away from you.')
f.line('finish', 'Then press Finish.')
f.line('done', 'The box says Calibration saved. The transmitter now knows where every control ends, and where its centre is.')
f.line('end', "That's all there is to it.")
f.prepare()

f.begin(); f.say('title', after=1.6)
f.show('c_front'); f.say('front', 'No model switched on.'); f.say('presstx', 'Press Transmitter.', after=0.3); f.tap(148, 425, 'c_setup')
f.say('setup', 'Press Calibrate.', after=0.3); f.tap(130, 164, 'c_cal')
f.say('cal', "Press 'Calibrate sticks etc.'", after=0.3); f.tap(228, 258, 'c_s1a')
f.say('step1', 'Every stick and knob to its ends, several times.', after=0.3)
for k in ('c_s1b', 'c_s1c', 'c_s1a', 'c_s1b', 'c_s1c', 'c_s1a'): f.under(k); f.hold(0.6)   # (the bars, in silence)
f.say('next', 'Press Next.', after=0.3); f.tap(228, 258, 'c_s2')
f.say('step2', 'Centre everything; top switches away from you.', after=0.3)
f.say('finish', 'Press Finish.', after=0.3); f.tap(228, 258, 'c_done')
f.say('done', 'Calibration saved.', after=1.4)
f.end('end')
f.finish()
