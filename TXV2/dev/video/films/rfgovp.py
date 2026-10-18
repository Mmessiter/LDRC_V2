#!/usr/bin/env python3
"""Film RFGOVP: the governor of each bank - a tour, then three real uses: head speed that sags in a climb (Anticipate
collective raised a little, saved; F gain strengthens all three), head speed that surges or hunts (lower the gains), and a
calm hover bank beside a livelier sport bank. The facts are RFGOVP.TXT's; the values are scenario 6's (RAW 420 MCM's own,
RXV2 dev/snapshots raw420_snapshot_20260817: 2200 rpm, Master 50, F 190, Anticipate collective 60); bank 2's 2500 rpm is
an example. A connected Save only hides Save (RF_Governor_Profile.h SendEditedGovValues). Made with dev/video/filmkit.py.
18 Oct 2026: starts on the Rotorflight menu; livelier words; "In practice" after the tour; no closing line (Malcolm)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play
from illus import Art
f = Film('RFGOVP', 'Governor', 'The head speed, and how it is held')
art = Art(f)
rf_route(f, 'Governor ...')
opn = prefix('6.txt', '6_open')
f.shot('p', opn)
f.shot('antic', opn + 'n13.val=70\nvis b3,1\n')                     # (Anticipate collective 60 to 70: Save shows)
f.shot('saved', opn + 'n13.val=70\nvis b3,0\n')
f.shot('bank2', opn + 'n13.val=70\nt0.txt="Governor (bank 2)"\nt26.txt="Bank 2"\nn0.val=2500\n')   # (an example sport bank)
f.line('title', 'Governor. Your head speed, held steady, whatever you do with the sticks.')
f.line('page', 'This is the Governor page, for the bank in its title. It needs Rotorflight two point three.')
f.line('head', 'Headspeed: the head speed this bank holds, in R P M.')
f.line('gains', 'Master gain: the overall strength. P, I and D gain: how the governor corrects a head speed error.')
f.line('ff', 'F gain, feed forward: the strength of the three Anticipate values.')
f.line('tta', 'Tail-torque strength and limit: the head speed may rise a little, to help the tail in hard yaw.')
f.line('throttle', 'Max and min throttle: the most and the least throttle the governor may use. Fall-back drop: how far the throttle drops if the head speed signal is lost.')
f.line('antic', 'And Anticipate: how much each stick adds throttle, before the load arrives.')
f.line('global', 'Global has the settings every bank shares.')
f.line('ok', 'OK goes back to the Rotorflight menu.')
f.line('sag', 'Now, the classic problem. Does the head speed sag when you climb, like this? The governor is reacting too late.')
f.line('fix', 'Raise Anticipate collective a little, so the throttle comes in with the collective, before the head slows. Here, sixty becomes seventy.')
f.line('save', "Touch the value, type the new one, and press Save. Save is refused while the model could be armed, so safety on first.")
f.line('more', 'Still sagging? F gain strengthens all three Anticipate values. Small steps, one flight each.')
f.line('hunt', 'The opposite: a head speed that surges, or hunts up and down? The gains are too high. Lower them a little. Master gain scales them all.')
f.line('bank1', 'And each bank holds its own head speed. Bank one here, at two thousand two hundred, is lovely for calm hovering.')
f.line('bank2', 'Flick the bank switch, and bank two holds two thousand five hundred: livelier, for sport.')
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Governor ...', 'p')
f.say('page', 'Governor.')
f.point(*at('RFGovView', 't34'), 'head', 'Headspeed.')
f.point(*at('RFGovView', 't29'), 'gains', 'Master gain; P, I, D.')
f.point(*at('RFGovView', 't35'), 'ff', 'F gain.')
f.point(*at('RFGovView', 't36'), 'tta', 'Tail torque.')
f.point(*at('RFGovView', 't32'), 'throttle', 'Throttle; fall-back drop.')
f.point(*at('RFGovView', 't39'), 'antic', 'Anticipate.')
f.point(*at('RFGovView', 'b2'), 'global', 'Global ...')
f.point(*at('RFGovView', 'b1'), 'ok', 'OK.')
# ---- in practice
f.show(art.head_sag(0)); f.anim(art.head_sag, 1.8); f.say('sag', 'Tip: head speed sags?')
f.show('p'); f.point(*at('RFGovView', 't41'), 'fix', 'Tip: more Anticipate collective.')
f.under('antic'); f.hold(0.8)
f.point(*at('RFGovView', 'b3'), 'save', 'Save: safety on.', after=0.3)
f.tap(*at('RFGovView', 'b3')); f.under('saved'); f.hold(0.6)
f.point(*at('RFGovView', 't35'), 'more', 'Tip: still sagging? F gain.')
f.point(*at('RFGovView', 'n1'), 'hunt', 'Tip: hunts? Lower the gains.')
f.point(*at('RFGovView', 't34'), 'bank1', 'Tip: a calm hover bank.')
f.show('bank2'); f.point(*at('RFGovView', 't34'), 'bank2', 'Tip: a livelier sport bank.')
f.end(); f.finish()
