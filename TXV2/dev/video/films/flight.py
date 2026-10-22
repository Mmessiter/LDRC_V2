#!/usr/bin/env python3
"""Film FLIGHT: your own front screen (a defined front screen) in use - the top line, the boxes, the three buttons and
Help, the six tabs, the warning colours, and changing a box from the screen itself (a double tap, or a hold). The facts are
FLIGHT.TXT's; the screen is the screen's own (ESP32-board2 lib/LdrcFlight), drawn over the front page by the renderer's
"@flight CONFIG", so its places come from films/drawn.py. 22 Oct 2026 (the design page's film is DESIGN). Made with
dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, at
from common import FRONT_CONNECTED
from drawn import flight_box6, FLIGHT_HELP, CHOOSER

CFG = 'f2 w1 grid6 s1 timer,batts,rpm,link,esc,mah d:,,1,,1'            # six boxes; the head speed and the ESC temperature as dials
f = Film('FLIGHT', 'Your own front screen', 'Big, clear numbers while you fly')
f.shot('front', FRONT_CONNECTED)
f.shot('defined', FRONT_CONNECTED + '@flight %s\n' % CFG)
f.shot('warn', FRONT_CONNECTED + 'JRX.val=15\nRXBV.txt="21.40V (3.57V per cell)"\nQuality.val=60\n@flight %s\n' % CFG)   # the model's battery at 15 %: red; the link at 60: amber
f.shot('tab2', FRONT_CONNECTED + '@flight f2 w1 big4 s1 rpm,timer,clock,link,esc d:1,1,1,1,1\n')               # another design: one big dial, four small
f.shot('chooser', FRONT_CONNECTED + '@flightsetup %s @box 2\n' % CFG)                                           # box 2's chooser, from the screen itself
f.line('title', "Your own front screen. Big, clear numbers while you fly, and six designs a touch apart.")
f.line('front', 'This is the front page. Press Defined screens, bottom right.')
f.line('page', "This is your own front screen. The top line shows the model's name and the bank. Each box shows one thing, big.")
f.line('buttons', 'Transmitter and Model open the setups. Original screen brings the original front page back, and its Defined screens button brings this one again. Your choice stays, even through switching off.')
f.line('tabs', 'The tabs, top right, switch between your six screens at a touch, even in flight. The yellow tab is the one in use. Press two.')
f.line('tab2', "Here's screen two: one big dial, and four small boxes. Back to one.")
f.line('help', "Help opens this screen's help, and its film.")
f.line('colours', "A box turns amber or red, with a white frame, when its value needs a look: a battery at forty per cent or less, red at twenty; the link below seventy-five; the E S C from eighty degrees.")
f.line('topline', 'And the top line turns red for battery low, or for no link in flight.')
f.line('change', 'To change a box from here, on the ground, tap it twice quickly, or hold it for two seconds.')
f.line('chooser', 'Its chooser opens. Your choice brings the screen straight back. A single tap, or a slide, does nothing: nothing changes by accident.')
f.line('design', 'Everything else, the box sizes, the dials, the themes, is on the design page: Transmitter setup, Appearance, Defined front screens. It has a film of its own.')
f.line('rule', 'On the ground means the safety is on. With no safety switch, it means the motor is off.')
f.prepare()

f.begin(); f.say('title', after=1.2)
f.show('front'); f.say('front', 'Press Defined screens.', after=0.3); f.tap(*at('FrontView', 'ldrcDefined'), 'defined')
f.say('page', 'Your own front screen.')
f.point(400, 449, 'buttons', 'Transmitter, Original screen, Model.')
f.point(439, 25, 'tabs', 'Six screens: the tabs.', after=0.3); f.tap(481, 25, 'tab2'); f.say('tab2', 'Screen two.', after=0.3); f.tap(439, 25, 'defined')
f.point(*FLIGHT_HELP, 'help', 'Help, and the film.')
f.show('warn'); f.say('colours', 'Amber at 40 %, red at 20.')
f.say('topline', 'A red top line: look now.')
f.show('defined'); f.say('change', 'Tap twice, or hold.', after=0.3); f.tap(*flight_box6(1), 'chooser')
f.say('chooser', 'The chooser.', after=0.3); f.tap(*CHOOSER['OK'], 'defined')
f.say('design', 'The design page: its own film.')
f.say('rule', 'On the ground: the safety on.')
f.end(); f.finish()
