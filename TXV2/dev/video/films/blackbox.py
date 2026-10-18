#!/usr/bin/env python3
"""Film BLACKBOX: the flight recorder - a tour, then recording a flight to chase a wobble or a governor problem. The facts are
BLACKBOX.TXT's (1 in 8 is plenty for tuning and governor problems; every loop or 1 in 2 for vibration; Keep after disarm keeps
the landing; download with the Configurator before erasing; Where and How often restart the flight controller). The rate in
brackets is RF_FcSetup.h BbShow's, at the loop of Malcolm's photo (1 in 2 = 1012/s, so 1 in 8 = 253/s). Made with
dev/video/filmkit.py.
18 Oct 2026: starts on the Rotorflight menu; livelier words; "In practice" after the tour; no closing line (Malcolm)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
from illus import Art
f = Film('BLACKBOX', 'Black box', "The flight controller's flight recorder")
rf_route(f, 'Black box ...')
opn = rfs('73.txt', '73_blackbox')
f.shot('p', opn); f.shot('tune', opn + 'tn2.txt="1 in 8 (253/s)"\n' + SAVE_SHOWN)
f.shot('vib', opn + 'tn2.txt="Every loop (2024/s)"\n' + SAVE_SHOWN)   # (BbShow's words for 1 in 1, at the same loop)
f.line('title', "Black box. The flight controller's own flight recorder, for finding out what really happened.")
f.line('page', "This is the Black box page. It sets up the flight controller's flight recorder, the same in every bank.")
f.line('when', 'When to record. Whenever armed records every flight, with no switch needed. Tap a box to step through its choices.')
f.line('where', "Where: usually the flight controller's own memory.")
f.line('often', 'How often: one record every so many control loops. The brackets show how many a second.')
f.line('memory', "Memory shows how much is used, and whether it's ready to record.")
f.line('erase', 'Erase all flight logs deletes every log for good, after a question.')
f.line('wob', "Here's where it really earns its keep. A wobble you can't explain, or a governor that hunts? A recording shows exactly what happened.")
f.line('tune', "Set How often to one in eight, and record a flight or two. That's plenty for tuning, and for the governor.")
f.line('vib', 'Hunting vibration? Then every loop, or one in two. But the memory fills that much faster.')
f.line('keep', "Keep after disarm carries on recording for a few seconds after you disarm, so the landing's kept in the log.")
f.line('after', 'Afterwards, download the log with the Configurator, and look at it on a computer. Then erase, ready for the next one.')
f.line('save', "Save appears once something's changed. A change to Where, or How often, restarts the flight controller.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Black box ...', 'p')
f.say('page', 'Black box.')
f.point(*at('BlackboxView', 'tn0'), 'when', 'When.')
f.point(*at('BlackboxView', 'tn1'), 'where', 'Where.')
f.point(*at('BlackboxView', 'tn2'), 'often', 'How often.')
f.point(*at('BlackboxView', 'tn5'), 'memory', 'Memory.')
f.point(*at('BlackboxView', 'b2'), 'erase', 'Erase all flight logs.')
art = Art(f); f.show(art.wobble(0)); f.anim(art.wobble, 2.5); f.say('wob', 'Tip: a wobble? Record it.')
f.show('tune'); f.point(*at('BlackboxView', 'tn2'), 'tune', 'Tip: 1 in 8 for tuning.')
f.show('vib'); f.point(*at('BlackboxView', 'tn2'), 'vib', 'Tip: vibration? Every loop.')
f.show('tune')
f.point(*at('BlackboxView', 'tn3'), 'keep', 'Tip: keep the landing.')
f.point(*at('BlackboxView', 'b2'), 'after', 'Tip: download, then erase.')
f.point(*at('BlackboxView', 'b3'), 'save', 'Save.')
f.end(); f.finish()
