#!/usr/bin/env python3
"""Film ADJUST: in-flight adjustments - a tour, then tuning in the air (a tail wag cured with Yaw P on a knob). The facts
are ADJUST.TXT's (the line under the bar says what the channel's position gives; Remove deletes the one showing); the
setting's name is RF_Adjust.h's AdjNames. Made with dev/video/filmkit.py.
18 Oct 2026: starts on the Rotorflight menu; livelier words; "In practice" after the tour; no closing line (Malcolm)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
from illus import Art
f = Film('ADJUST', 'Adjustments', 'A knob or switch changes a setting in flight')
rf_route(f, 'Adjustments ...')
opn = rfs('67.txt', '67_knob', 't0.txt="Adjustment 1 of 1"\nvis b3,0\n')   # (one knob, as read: Save hidden)
f.shot('p', opn)
f.shot('yaw', opn + 'tn0.txt="Yaw P gain"\n' + SAVE_SHOWN)   # (its setting changed to Yaw P gain: Save shows)
f.shot('low', opn + 'tn0.txt="Yaw P gain"\nbar.mk=1300\ntn8.txt="Knob 1300 us: 50"\n')   # (saved and flown: the knob turned down to 50, AdjLive's words)
f.line('title', 'Adjustments. Turn a knob in flight, and a Rotorflight setting changes as you fly.')
f.line('page', 'This is the Adjustments page. Each adjustment is one setting, worked by one channel: a knob or a switch on this transmitter.')
f.line('usb', "It needs the U S B C cable, from the receiver to the flight controller. Rotorflight can't send adjustments over the receiver's lead.")
f.line('step', 'The arrows beside the title step through your adjustments.')
f.line('setting', 'Tap the box beside Changes to choose the setting. The bank and rates selectors come first in the list, then rates and P I Ds.')
f.line('kind', "Below it, the kind: a knob, a switch, or a step adjustment. And beside that, the channel it's on.")
f.line('add', 'Add makes a new one. Remove deletes the one showing, after a question.')
f.line('tune', "Here's a great use: tuning in the air. Put a gain on a knob, and you can try a whole range of values in one flight.")
f.line('save', "Press Save, and it's ready to fly.")
f.line('wag', "Here's one that catches lots of pilots: tail wag. A fast side to side twitch of the tail. It's usually the yaw gain a touch too high.")
f.line('wag2', "So put Yaw P gain on a knob. Then, in a steady hover, turn it down slowly until the wag stops.")
f.line('read', 'Then land, and leave the knob where it is. This line shows the value it gives.')
f.line('keep', "Type that value on the P I Ds page. Then remove the adjustment, so a knocked knob can't change it.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Adjustments ...', 'p')
f.say('page', 'Adjustments.')
f.point(*at('AdjustView', 't9'), 'usb', 'The USB-C cable.')
f.point(*at('AdjustView', 'bnext'), 'step', '< and >.')
f.point(*at('AdjustView', 'tn0'), 'setting', 'What it changes.')
f.point(*at('AdjustView', 'tn2'), 'kind', 'Kind and channel.')
f.point(*at('AdjustView', 'b5'), 'add', 'Add, Remove.')
f.show('yaw'); f.point(*at('AdjustView', 'tn0'), 'tune', 'Tip: tune in the air.')
f.point(*at('AdjustView', 'b3'), 'save', 'Save, then fly.')
art = Art(f); f.show(art.tail_wag(0)); f.anim(art.tail_wag, 3.0); f.say('wag', 'Tip: tail wag? Often yaw gain.')
f.show('yaw'); f.point(*at('AdjustView', 'bar'), 'wag2', 'Tip: turn Yaw P down slowly.')
f.show('low'); f.point(*at('AdjustView', 'tn8'), 'read', 'Tip: read the value here.')
f.point(*at('AdjustView', 'b6'), 'keep', 'Tip: type it in, then Remove.')
f.end(); f.finish()
