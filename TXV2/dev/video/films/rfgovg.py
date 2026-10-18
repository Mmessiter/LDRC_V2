#!/usr/bin/env python3
"""Film RFGOVG: the governor settings every bank shares - a tour, then two real uses: a gentler spool-up, and autorotation
practice with a quick bail-out. The facts are RFGOVG.TXT's. Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the setup pages, real uses, livelier words, no closing line): starts on the Rotorflight menu.
Autorotation practice: the motor switch sends the model's Motor off value (TransmitterCode main.cpp FixMotorChannel), below
Rotorflight's off throttle (rc.c offThrottle), and its governor (governor.c) goes from ACTIVE to THROTTLE_HOLD on that - so a
bail-out with the motor switch is ready for the Hold timeout. Autorot. timeout counts only for a throttle low but NOT off."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, SAVE_SHOWN
f = Film('RFGOVG', 'Governor (global)', 'The mode, the throttle and the timings')
rf_route(f, 'Governor ...')
opn = prefix('5.txt', '5_open')                      # (Spool-up n17 20 s, Hold timeout n21 5 s: the RAW 420's own)
def page(**vals):
    """Governor global with example values typed in (Save shows once something is changed)"""
    return opn + ''.join('%s.val=%d\n' % kv for kv in sorted(vals.items())) + SAVE_SHOWN
f.shot('g', prefix('6.txt', '6_open')); f.shot('p', opn); f.shot('e', prefix('5.txt', '5_edited'))
f.shot('spool', page(n17=25))
f.shot('hold', page(n21=20))                        # (the tips point at a row's name: its new value stays in sight)
f.line('title', 'Governor global. The settings every bank shares: the mode, the throttle, and the timings.')
f.line('g', "This is the Governor page, with each bank's head speed and gains. Press Global.")
f.line('page', "And here's Governor global. These settings are shared by every bank, and they need Rotorflight two point three.")
f.line('mode', 'Governor mode, from nought to four. The box above names it. Three, Electric, is the full governor for an electric helicopter.')
f.line('handover', "Handover: above this throttle, the governor takes over, and spools up to the bank's head speed.")
f.line('ttype', "Throttle type: nought, Normal, is the usual one.")
f.line('spool', "The timings are in seconds. Spool-up is the time it takes to reach head speed. Higher is gentler.")
f.line('save', "Change a value, and Save appears. It stores the values, then restarts the flight controller, because Rotorflight reads them only as it starts. And it won't save while the model could be armed.")
f.line('copy', "Keep a copy stores these values in the model's file, on the transmitter's card. Restore sends that copy back to the flight controller.")
f.line('ok', 'OK takes you back to the Rotorflight menu.')
f.line('spooltip', "Here's a real use. A big model, or one that twists on its skids as it spools up, usually likes a gentler start. Add a few seconds to Spool-up.")
f.line('holdtip', "Practising autorotations? To Rotorflight, your motor switch is a throttle hold, so Hold timeout is the one that counts. Set it longer than the whole descent, and switching back on gives a quick restart.")
f.line('bailout', "That's your bail-out. Try it high up first. And once you've landed, put the safety on.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Governor ...', 'g')
f.say('g', 'Press Global.', after=0.3); f.tap(*at('RFGovView', 'b2'), 'p')
f.say('page', 'Governor (global).')
f.point(*at('RFGovViewGlbl', 'n14'), 'mode', 'Governor mode.')
f.point(*at('RFGovViewGlbl', 'n15'), 'handover', 'Handover.')
f.point(*at('RFGovViewGlbl', 'n28'), 'ttype', 'Throttle type.')
f.point(*at('RFGovViewGlbl', 'n17'), 'spool', 'Spool-up: higher is gentler.')
f.under('e'); f.hold(0.6); f.point(*at('RFGovViewGlbl', 'b3'), 'save', 'Save, then a restart.')
f.point(*at('RFGovViewGlbl', 'b2'), 'copy', 'Keep a copy; Restore.')
f.point(*at('RFGovViewGlbl', 'b1'), 'ok', 'OK.')
f.show('spool'); f.point(*at('RFGovViewGlbl', 't45'), 'spooltip', 'Tip: a gentler spool-up.')
f.show('hold'); f.point(*at('RFGovViewGlbl', 't49'), 'holdtip', 'Tip: autos? Hold timeout.')
f.cap = None; f.say('bailout', 'Tip: bail-outs high up first.')
f.end(); f.finish()
