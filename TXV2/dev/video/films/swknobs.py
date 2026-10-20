#!/usr/bin/env python3
"""Film SWKNOBS: Switches and knobs (B140, 20 Oct 2026) - one page for every job a channel does: a switch job (arm, rescue,
self-level ...), a selector (the bank, the rates) or a knob that changes a setting in flight. A tour, then tuning in the
air (a tail wag cured with Yaw P on a knob). The facts are SWKNOBS.TXT's: Rotorflight keeps these on two tabs (Modes and
Adjustments); the switch jobs come over the receiver's lead, the selectors and knobs need the USB cable; Add opens the
list first; the line under the bar says what the channel's position gives; Remove deletes the one showing. The page and
its words are the former ADJUST film's (18 Oct: starts on the Rotorflight menu; livelier words; "In practice" after the
tour; no closing line). Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
from illus import Art
f = Film('SWKNOBS', 'Switches and knobs', 'A switch, a selector or a knob: what it makes the flight controller do')
rf_route(f, 'Switches & knobs ...')
opn = rfs('67.txt', '67_knob', 't0.txt="Job 1 of 1"\nvis b3,0\n')   # (one knob, as read: Save hidden)
f.shot('p', opn)
f.shot('yaw', opn + 'tn0.txt="Yaw P gain"\n' + SAVE_SHOWN)   # (its setting changed to Yaw P gain: Save shows)
f.shot('low', opn + 'tn0.txt="Yaw P gain"\nbar.mk=1300\ntn8.txt="Knob 1300 us: 50"\n')   # (saved and flown: the knob turned down to 50, AdjLive's words)
f.line('title', 'Switches and knobs. What each switch or knob of this transmitter makes the flight controller do, all on one page.')
f.line('page', "This is the Switches and knobs page. One job at a time: a switch job, like arm or rescue; a selector that picks the bank; or a knob that changes a setting as you fly.")
f.line('two', "Rotorflight keeps these on two tabs, Modes and Adjustments. Many found that confusing, so here they're together. The page writes each to its own table, out of sight.")
f.line('usb', "Switch jobs come over the receiver's lead. Selectors and knobs also need the U S B C cable, from the receiver to the flight controller.")
f.line('step', 'The arrows beside the title step through the jobs: switch jobs first, then selectors and knobs.')
f.line('setting', 'Tap the job box to choose another job. The list starts with the two selectors, then the switch jobs, then the settings.')
f.line('kind', "Below it, the kind: a knob, a switch, or a step adjustment. And beside that, the channel it's on.")
f.line('add', 'Add opens the list first. Choose what the new job does, press OK, and it goes on the next channel. Remove deletes the job showing, after a question.')
f.line('tune', "Here's a great use: tuning in the air. Put a gain on a knob, and you can try a whole range of values in one flight.")
f.line('save', "Press Save, and it's ready to fly.")
f.line('wag', "Here's one that catches lots of pilots: tail wag. A fast side to side twitch of the tail. It's usually the yaw gain a touch too high.")
f.line('wag2', "So put Yaw P gain on a knob. Then, in a steady hover, turn it down slowly until the wag stops.")
f.line('read', 'Then land, and leave the knob where it is. This line shows the value it gives.')
f.line('keep', "Type that value on the P I Ds page. Then remove the adjustment, so a knocked knob can't change it.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Switches & knobs ...', 'p')
f.say('page', 'Switches and knobs.')
f.point(*at('AdjustView', 't0'), 'two', 'Two tabs in Rotorflight: one page here.')
f.point(*at('AdjustView', 't9'), 'usb', 'Knobs: the USB-C cable.')
f.point(*at('AdjustView', 'bnext'), 'step', '< and >.')
f.point(*at('AdjustView', 'tn0'), 'setting', 'What it does.')
f.point(*at('AdjustView', 'tn2'), 'kind', 'Kind and channel.')
f.point(*at('AdjustView', 'b5'), 'add', 'Add: the list first. Remove.')
f.show('yaw'); f.point(*at('AdjustView', 'tn0'), 'tune', 'Tip: tune in the air.')
f.point(*at('AdjustView', 'b3'), 'save', 'Save, then fly.')
art = Art(f); f.show(art.tail_wag(0)); f.anim(art.tail_wag, 3.0); f.say('wag', 'Tip: tail wag? Often yaw gain.')
f.show('yaw'); f.point(*at('AdjustView', 'bar'), 'wag2', 'Tip: turn Yaw P down slowly.')
f.show('low'); f.point(*at('AdjustView', 'tn8'), 'read', 'Tip: read the value here.')
f.point(*at('AdjustView', 'b6'), 'keep', 'Tip: type it in, then Remove.')
f.end(); f.finish()
