#!/usr/bin/env python3
"""Film PID_A: PID + (advanced) - a tour, then four common tail and servo problems and the setting for each: a tail that
bounces at the end of a pirouette (yaw stop firmness raised a little, typed and saved), a nose that kicks round on
collective (yaw push from collective), buzzing or hot servos (D smoothing lower), a lean on the ground (relax on the
ground). The facts are PID_A.TXT's; the values are scenario 7's (RAW 420 MCM, bank 1); the keypad's question is the value
box's own touch event (t20: "Yaw stop firmness, anticlockwise"); the save is SendEditedPID_Advanced's (RF_PID_Advanced.h:
the boxes grey, "Sending edited advanced PIDs ...", then back). Made with dev/video/filmkit.py.
18 Oct 2026: starts on the Rotorflight menu, through the PIDs page; livelier words; "In practice" after the tour; no
closing line (Malcolm)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, keypad_shots, KEY
from illus import Art
f = Film('PID_A', 'PID + (advanced)', 'The rest of the PID settings')
art = Art(f)
rf_route(f, 'PIDs ...')
f.shot('pid', prefix('40.txt', '40_open'))
opn = prefix('7.txt', '7_open')
BOXES = ['sw0'] + ['t%d' % i for i in range(1, 26)]
GREY = ''.join('%s.pco=33840\n' % b for b in BOXES)
BLACK = ''.join('%s.pco=0\n' % b for b in BOXES)
f.shot('p', opn)
keypad_shots(f, opn, 7, 't20', 21, ['80', '8', '85'])                 # (anticlockwise stop firmness: 80 to 85)
f.shot('e', opn + 't20.txt="85"\nvis b3,1\n')
f.shot('s', opn + 't20.txt="85"\n' + GREY + 'busy.txt="Sending edited advanced PIDs ..."\nvis busy,1\nvis b3,0\n')
f.shot('d', opn + 't20.txt="85"\n' + BLACK + 'vis busy,0\nvis b3,0\n')
f.line('title', 'P I D plus. The finer points of the P I D settings, for when you need them.')
f.line('pid', 'This is the P I Ds page. Press P I D plus.')
f.line('page', "This is the P I D plus page, for the same bank. Most models fly well on Rotorflight's own values, so change one only when you know why.")
f.line('piro', 'Piro compensation is a switch: touch it to turn it on or off.')
f.line('relax', "Relax on the ground: while it's on the ground, built-up corrections drain away, so the swash doesn't lean.")
f.line('axes', 'Then, for roll, pitch and yaw: wind-up relief, a correction cap, and the response speed.')
f.line('dsmooth', 'D smoothing: lower it if the servos buzz or run hot.')
f.line('stop', 'Yaw stop firmness: how firmly the tail stops when you centre the stick. There is one for each direction.')
f.line('push', "Yaw push: extra tail, added as the load rises, before the nose can swing. Collective is the main one.")
f.line('ok', 'Save appears once you change a value. OK leaves, and asks first if a change is not saved.')
f.line('bounce', "Now, real problems. Does the tail bounce back at the end of a pirouette, like this? Raise the stop firmness on the side that bounces.")
f.line('try', "Here, anticlockwise is eighty. Try a little more: eighty five.")
f.line('check', "The keypad shows the name of the value you're changing. Check it: on this crowded page it's easy to touch the wrong one. If it is, press Cancel.")
f.line('type', 'Delete, type the new value, and press OK.')
f.line('save', "Then Save. It's written, read back to check, and stored. Now fly it, and see.")
f.line('kick', 'Does the nose kick round when you pump the collective? Raise Yaw push from collective, a little at a time.')
f.line('buzz', 'Servos buzzing, or running hot? Lower the D smoothing.')
f.line('lean', "And if it leans on the ground before take-off, Relax on the ground is the one that helps.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'PIDs ...', 'pid')
f.say('pid', 'Press PID +.', after=0.3); f.tap(*at('PIDView', 'b2'), 'p')
f.say('page', 'PID + (advanced).')
f.point(*at('PID_A_View', 'sw0'), 'piro', 'Piro compensation.')
f.point(*at('PID_A_View', 't29'), 'relax', 'Relax on the ground.')
f.point(*at('PID_A_View', 't30'), 'axes', 'Roll, pitch and yaw.')
f.point(*at('PID_A_View', 't41'), 'dsmooth', 'D smoothing.')
f.point(*at('PID_A_View', 't47'), 'stop', 'Yaw stop firmness.')
f.point(*at('PID_A_View', 't51'), 'push', 'Yaw push.')
f.point(*at('PID_A_View', 'b1'), 'ok', 'Save; OK.')
# ---- in practice: a bounce at the end of a pirouette, cured on this page; then three more
f.show(art.tail_bounce(0)); f.anim(art.tail_bounce, 3.0); f.say('bounce', 'Tip: tail bounces? Firmer stop.')
f.show('p'); f.point(*at('PID_A_View', 't48'), 'try', 'Anticlockwise: 80 to 85.', after=0.3)
f.tap(*at('PID_A_View', 't20'), 'kp0'); f.say('check', 'Tip: check the name.')
f.say('type', 'Delete, type, OK.', after=0.3)
f.tap(*KEY['Delete']); f.under('kp1'); f.hold(0.4); f.tap(*KEY['5']); f.under('kp2'); f.hold(0.6); f.tap(*KEY['OK'], 'e')
f.cap = None; f.say('save', 'Save, then fly it.', after=0.3)
f.tap(*at('PID_A_View', 'b3')); f.under('s'); f.hold(1.4); f.under('d'); f.hold(0.6)
f.point(*at('PID_A_View', 't23'), 'kick', 'Tip: nose kicks? More push.')
f.point(*at('PID_A_View', 't13'), 'buzz', 'Tip: buzzing? Lower D smoothing.')
f.point(*at('PID_A_View', 't1'), 'lean', 'Tip: leans on the ground?')
f.end(); f.finish()
