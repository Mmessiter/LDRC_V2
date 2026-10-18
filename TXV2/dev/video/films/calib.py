#!/usr/bin/env python3
"""Film CALIB: calibrating the sticks, then when to do it again, and the trims' directions. The route and the words are the
firmware's and CALIB.TXT's: Transmitter setup > Calibrate (refused while a model is connected) > "Calibrate sticks etc." >
move everything to its ends > Next > centre everything, the four top edge switches AWAY from you > Finish > "Calibration
saved."; then "Calibrate trims ..." > Set trim directions (push each trim the way it asks, in any order; "... trim: done").
Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the model or transmitter screen; real uses): it starts on Transmitter setup ("switch the model
off first"). In practice: calibrate again when a stick or switch acts oddly (a model that creeps with the sticks centred, a
top switch the wrong way round: the switches must be AWAY at the centre step), after new gimbals or a new stick mode (set in
System first, CALIB.TXT); "Calibrate trims" when a trim works backwards."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from illus import Art

f = Film('CALIB', 'Calibrating the sticks', 'The first job on a new transmitter')
art = Art(f)
f.shot('c_setup', prefix('33.txt', '33_open'))
f.shot('c_cal', prefix('22.txt', '22_open'))
s1 = prefix('22.txt', '22_step1')
f.shot('c_s1a', s1)
f.shot('c_s1b', s1 + 'Ch1.val=0\nCh2.val=100\nCh3.val=0\nCh4.val=100\nCh5.val=0\nCh6.val=0\nCh7.val=100\nCh8.val=100\n')
f.shot('c_s1c', s1 + 'Ch1.val=80\nCh2.val=20\nCh3.val=65\nCh4.val=35\nCh5.val=100\nCh6.val=50\nCh7.val=0\nCh8.val=50\n')
f.shot('c_s2', prefix('22.txt', '22_step2'))
f.shot('c_done', prefix('22.txt', '22_done'))
f.shot('c_trims', prefix('49.txt', '49_open'))
f.shot('c_trims1', prefix('49.txt', '49_partial').replace('thr.txt="Throttle trim: done"\n', ''))   # (aileron first)
f.shot('c_trims2', prefix('49.txt', '49_partial'))                                                     # (then throttle)
f.shot('c_trims3', prefix('49.txt', '49_long'))                                                        # (all four)
f.line('title', 'Calibrating the sticks. The first job on a new transmitter, and the cure for some odd behaviour.')
f.line('setup', "Here's the Transmitter setup page. Switch the model off first: the Calibration page won't open while a model's connected. Then press Calibrate.")
f.line('cal', "This is the Calibration page. Press Calibrate sticks, et cetera. And don't switch the transmitter off until you've finished.")
f.line('step1', 'Now move both sticks, and the front switches or knobs, to their very ends, several times. Right into every corner!')
f.line('bars', 'The bars show each one moving.')
f.line('next', 'Then press Next.')
f.line('step2', 'Now centre both sticks, the throttle stick too, and the front switches or knobs. Push all four top switches away from you.')
f.line('finish', 'Then press Finish.')
f.line('done', 'Calibration saved! The transmitter now knows where every control ends, and where its centre is.')
f.line('again', 'Calibrate again whenever a stick or switch acts oddly. A model that creeps with the sticks centred, perhaps, or a top switch that works the wrong way round.')
f.line('again2', 'Do it again after new gimbals, too, or a new stick mode. Set the new mode in System first, then calibrate.')
f.line('trims', 'And if a trim ever works backwards, press Calibrate trims.')
f.line('trimpage', 'This is the Set trim directions page. Push each trim button the way it asks, one at a time, in any order.')
f.line('trimok', 'Each line then says done. Press OK, and every trim works the right way round.')
f.prepare()

f.begin(); f.say('title', after=1.2)
f.show('c_setup'); f.say('setup', 'Model off. Press Calibrate.', after=0.3); f.tap(*at('TXSetupView', txt='Calibrate'), 'c_cal')
f.say('cal', "Press 'Calibrate sticks etc.'", after=0.3); f.tap(*at('CalibrateView', 'b0'), 'c_s1a')
f.say('step1', 'Every stick and knob to its ends.', after=0.3)
f.show(art.sticks_calib(0)); f.anim(art.sticks_calib, 3.5)          # (the sticks round every corner, in silence)
f.show('c_s1a')
for k in ('c_s1b', 'c_s1c', 'c_s1a', 'c_s1b', 'c_s1c', 'c_s1a'): f.under(k); f.hold(0.6)   # (the bars, in silence)
f.say('bars', 'The bars show each one.', after=0.3)
f.say('next', 'Press Next.', after=0.3); f.tap(*at('CalibrateView', 'b0'), 'c_s2')
f.say('step2', 'Centre everything; top switches away from you.', after=0.3)
f.say('finish', 'Press Finish.', after=0.3); f.tap(*at('CalibrateView', 'b0'), 'c_done')
f.say('done', 'Calibration saved.')
f.point(*at('CalibrateView', 'b0'), 'again', 'Tip: acting oddly? Calibrate again.')
f.cap = None; f.say('again2', 'New gimbals? New stick mode?')
f.point(*at('CalibrateView', 'b1'), 'trims', 'Tip: a trim works backwards?', after=0.3)
f.tap(*at('CalibrateView', 'b1'), 'c_trims')
f.say('trimpage', 'Each trim the way it asks.', after=0.3)
for k in ('c_trims1', 'c_trims2', 'c_trims3'): f.under(k); f.hold(0.8)   # (each trim pushed, in silence)
f.point(*at('TrimDefView', 'b2'), 'trimok', 'All done? Press OK.')
f.end(); f.finish()
