#!/usr/bin/env python3
"""Film MIXES: setting up a mix, a tour, and three classic mixes. The facts are MIXES.TXT's; mix 1 (Mix output, Aileron to
Rudder at 25 %) is scenario 29_open's own; a V tail's elevator-into-rudder mix and a throttle-to-elevator mix with an Offset
are shown as mixes 2 and 3 (an Offset of 8 centres the slave at 10 % with the throttle closed: Mixes.h adds Offset x 8 to
the master's output of about -667 x 10 %). Made with dev/video/filmkit.py.
18 Oct 2026: starts on Model setup, no closing line, and an "In practice" part (Malcolm: "look beyond the simple
functions' description and also describe how to use for solving real-world flying issues")."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('MIXES', 'Mixes', 'One channel following another')
model_route(f, 'Mixes')
opn = prefix('29.txt', '29_open')
def page(mix, master, mname, slave, sname, pct, offset=0):
    """a Mix output mix in every bank, as the Teensy sends it (ReadMixValues, FixCHNames)"""
    return opn + ('MixNumber.val=%d\nEnabled.val=1\nc0.val=0\nFlightMode.val=0\nMasterChannel.val=%d\nSlaveChannel.val=%d\nReversed.val=0\n'
                  'Percent.val=%d\nod.val=0\nOffset.val=%d\nchM.txt="%s"\nchS.txt="%s"\nt10.txt="All banks"\n') % (mix, master, slave, pct, offset, mname, sname)
f.shot('p', opn)
f.shot('vtail', page(2, 2, 'Elevator', 4, 'Rudder', 100))
f.shot('thr', page(3, 3, 'Throttle', 2, 'Elevator', 10, 8))
f.line('title', 'Mixes. One channel following another.')
f.line('page', 'This is the Mixes page. A mix makes one channel, the slave, follow another, the master.')
f.line('number', 'First, choose a mix number, with its minus and plus. There are thirty two of them.')
f.line('onoff', 'Then turn on Mix input or Mix output. With both off, the mix does nothing.')
f.line('inout', "Mix input adds the master's stick movement, before the slave's curve. Mix output adds the master's output, after its own curve.")
f.line('bank', 'Bank: which bank the mix works in. Nought means all of them.')
f.line('master', 'Then the master channel and the slave channel. Their names show on the right, so you can check them.')
f.line('percent', "Percent: how much of the master's movement the slave gets. A hundred is all of it.")
f.line('dir', 'One direction moves the slave one way only. Reversed moves it the other way.')
f.line('ok', 'Each minus or plus works at once, so watch the servos as you go. Then press OK to save.')
f.line('rudder', "Here's a classic for an aeroplane: a little rudder with the ailerons, for smoother turns. This mix gives the rudder a quarter of the aileron movement. Start small, and adjust after a flight.")
f.line('vtail', "A V tail, flaperons or a delta wing need two mixes, each channel the other's master. Here's one of a V tail's pair. Use Mix output for these.")
f.line('vtail2', 'Then check that every surface moves the right way for each stick.')
f.line('offset', 'Some models pitch up with power, and a throttle to elevator mix can help. But a throttle rests at the bottom, not in the middle.')
f.line('offset2', "So use Offset: try values until the elevator is centred with the throttle closed. If you change Percent, check Offset again.")
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Mixes', 'p')
f.say('page', 'Mixes.')
f.point(*at('MixesView', 'MixNumber'), 'number', 'Mix number.')
f.point(*at('MixesView', 'c0'), 'onoff', 'Mix input or Mix output.')
f.cap = None; f.say('inout', 'Before, or after, the curve.')
f.point(*at('MixesView', 'FlightMode'), 'bank', 'Bank: 0 = all.')
f.point(*at('MixesView', 'MasterChannel'), 'master', 'Master and slave.')
f.point(*at('MixesView', 'Percent'), 'percent', 'Percent.')
f.point(*at('MixesView', 'od'), 'dir', 'One direction, Reversed.')
f.point(*at('MixesView', 'b10'), 'ok', 'Watch the servos; OK saves.')
f.point(*at('MixesView', 't5'), 'rudder', 'Tip: rudder with the ailerons.')
f.show('vtail'); f.point(*at('MixesView', 'Enabled'), 'vtail', 'Tip: V tail? Use Mix output.')
f.cap = None; f.say('vtail2', 'Check every surface.')
f.show('thr'); f.point(*at('MixesView', 't9'), 'offset', 'Tip: a throttle master? Offset.')
f.cap = None; f.say('offset2', 'Centred with the throttle closed.')
f.end(); f.finish()
