#!/usr/bin/env python3
"""Film FRONT: the front page - what everything on it means, then what to glance at before each flight, and what the motor
timer tells you after it. The facts are FRONT.TXT's (the front page's help) and RXSETUP1.TXT's (the count-down timer, Model
setup > Options); every place pointed at is a component's centre from the page's own definition (sd/hmi/pages/13.json), or a
point inside one. The battery bar is the Teensy's own sum (Telemetry.h CheckRXVolts: 3.4 to 4.2 V a cell = 0 to 100).
Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: "describe how to use for solving real-world flying issues"): the front page's own film still starts on
the front page. In practice: before take-off, the model's name, the link quality and the battery per cell (a freshly charged
LiPo about 4.2 V a cell; about 3.8 is a pack still at storage charge); after landing, the motor timer as the way to find a
safe time for a count-down timer."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, at
from common import FRONT_CONNECTED

f = Film('FRONT', 'The front page', 'What everything on it means')
def page(mins, secs, rx, jrx, mah, esc):
    """the front page with this motor timer, model battery (its bar as the Teensy works it out), capacity used and ESC
    temperature; the link all green"""
    return FRONT_CONNECTED + ('Mins.val=%d\nSecs.val=%d\nRXBV.txt="%s"\nJRX.val=%d\nwb.txt="mAh: %d"\nWarning.txt="ESC: %.1f"\n'
                              'Quality.val=100\n' % (mins, secs, rx, jrx, mah, esc))
f.shot('fr_front', FRONT_CONNECTED)
f.shot('before', page(0, 0, '25.08V (4.18V per cell)', 97, 0, 21.5))      # (just connected: a fresh 6S pack, the timer at nought)
f.shot('after', page(5, 30, '22.62V (3.77V per cell)', 46, 1140, 38.5))   # (landed: 5 min 30 of motor, at the in-flight 12.4 A)
f.line('title', "The front page. Here's what everything on it means, and what to glance at before every flight.")
f.line('front', "This is the transmitter's front page. Keep it in view while you fly: everything that matters is here.")
f.line('bank', 'Top left, the bank and the rate that your switches have chosen.')
f.line('picture', "In the middle, the model's picture, with its name and number underneath. Touch the picture to choose a different one.")
f.line('bars', 'Top right, a bar for every channel. Each one grows from the middle line as its control moves.')
f.line('motor', "Under them, the motor box. It tells you whether the motor's on or off.")
f.line('left', 'On the left, your name. With Rotorflight, the head speed, the current, the capacity used, and the E S C temperature.')
f.line('timer', "The big numbers are the motor timer. It runs while the motor's on, and pauses while it's off.")
f.line('batteries', "Bottom left, the batteries: T X is the transmitter's, R X the model's. Each shows its voltage, and its voltage per cell.")
f.line('link', 'Beside Connected, the link quality. Green is the data that arrived, and red is any that was lost.')
f.line('trims', 'The yellow lines down the sides and along the bottom are the four trims. The red dot on each one shows where it is.')
f.line('setups', 'In the bottom corners, Transmitter and Model open the two setups.')
f.line('defined', 'And Defined screens swaps this page for your own front screen, with the numbers you choose, big and clear.')
f.line('habit', "Now, a habit worth having. Before every flight, glance at three things. First, the model's name and picture. Is the right model loaded?")
f.line('link2', 'Second, the link quality. It should be green all the way, or very nearly.')
f.line('cells', "Third, the model's battery, per cell. A freshly charged LiPo shows about four point two volts. Nearer three point eight? That pack probably hasn't been charged!")
f.line('flew', 'After landing, the motor timer shows how long the motor ran on that pack. Here, five and a half minutes.')
f.line('countdown', "Fly a few packs, and you'll know a safe time. Then set a count-down timer to it, on Model setup, Options. It counts the last ten seconds aloud.")
f.prepare()

f.begin(); f.say('title', after=1.2)
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
f.show('before'); f.point(*at('FrontView', 'exp0'), 'habit', 'Tip: the right model?')   # (on the picture: the name under it left clear)
f.point(*at('FrontView', 'Quality'), 'link2', 'Green all the way.')
f.point(318, 356, 'cells', 'About 4.2 volts a cell.')                     # (at the RX line's end: its volts per cell left clear)
f.show('after'); f.point(*at('FrontView', 'Hours'), 'flew', 'Tip: how long that pack flew.')   # (the minutes and seconds left clear)
f.say('countdown', 'Count down: Model setup, Options.')
f.end(); f.finish()
