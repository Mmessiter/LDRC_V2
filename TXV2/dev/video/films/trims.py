#!/usr/bin/env python3
"""Film TRIMS: the Trims page, a tour, then how pilots use trims. The words are TRIMS.TXT's; the centred trims are the
scenario's own state after Move to subtrim (28_after_subtrim's values). Made with dev/video/filmkit.py.
18 Oct 2026, Malcolm: start on Model setup; real uses (flybarless: trims off; an aeroplane: trim, then Move to subtrim;
clicks and a centre beep). The plane's trims are the scenario's (28_open); after Move to subtrim, centred. TRIMS.TXT's TAKE CARE (Mode 2, a second servo on one stick) is pointed to, not repeated."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play

f = Film('TRIMS', 'Trims', 'The four trims, on screen')
model_route(f, 'Trims')
opn = prefix('28.txt', '28_open')
f.shot('p', opn)
f.shot('centred', opn + 'ch1.val=80\nn1.val=0\nch2.val=80\nn2.val=0\nch4.val=80\nn4.val=0\nch3.val=80\nn3.val=0\n')   # every trim at centre
f.line('title', 'Trims. The four trims, on screen.')
f.line('page', 'This is the Trims page. Use it instead of the trim levers, or just to see your trims clearly.')
f.line('plus', 'Press plus or minus to move a trim. Each one has forty steps either side of centre.')
f.line('reset', "Reset centres this bank's trims.")
f.line('move', "Move to subtrim moves this bank's four trims into the subtrims. It asks first.")
f.line('multiplier', "The trims only work when Trim multiplier, on Model setup's Options page, is above nought. Five is a very good start.")
f.line('ok', 'OK keeps your changes, and goes back to Model setup.')
f.line('plane', "Now, some real uses. On an aeroplane, trim it in flight, like this. Then, back on the ground, press Move to subtrim.")
f.line('moved', "The trims go into the subtrims, and they're centred again. The subtrims work in every bank alike, so this bank flies just as before.")
f.line('fbl', "Flying a flybarless helicopter? Turn the trims off: set Trim multiplier to nought, and every subtrim to nought too. The flight controller holds it steady.")
f.line('care', "Before you use Move to subtrim, read Take care, in this page's help. And check every control before you fly.")
f.line('clicks', 'Here\'s a neat one: turn on Trim change clicks, in Sounds etc., on Transmitter setup. Each step clicks, and a beep marks the centre and each end, so you can trim without looking down.')
f.prepare()

f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Trims', 'p')
f.say('page', 'Trims.')
f.point(*at('TrimView', 'b2'), 'plus', 'Plus and minus.')
f.point(*at('TrimView', 'b8'), 'reset', 'Reset.')
f.point(*at('TrimView', 'b9'), 'move', 'Move to subtrim.')
f.cap = None; f.say('multiplier', 'Trim multiplier above 0.')
f.point(*at('TrimView', 'b10'), 'ok', 'OK keeps the changes.')
f.point(*at('TrimView', 'b9'), 'plane', 'Tip: plane? Trim, then subtrim.')
f.show('centred'); f.point(*at('TrimView', 'n4'), 'moved', 'Tip: centred, and flies the same.')
f.cap = None; f.say('care', 'Read Take care in the help.')
f.point(*at('TrimView', 'n1'), 'fbl', 'Tip: flybarless? Trims off.')
f.point(*at('TrimView', 'b3'), 'clicks', 'Tip: trim by ear.')
f.end()
f.finish()
