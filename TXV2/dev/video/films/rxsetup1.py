#!/usr/bin/env python3
"""Film RXSETUP1: Model options, a tour, then four settings that solve real problems. The words are RXSETUP1.TXT's; the
throttle channel shown is 3 (the Channels page's Throttle), and the examples are the page's own boxes and switches with
other values ('click c2,0': the page's own rule greys the minutes box only while Timer counts down is off). One drawing
(illus.py battery): a 6S pack (the front page's 23.46 V at 3.91 V a cell) sagging under load, then recovering. Made with
dev/video/filmkit.py.
18 Oct 2026, Malcolm: start on Model setup; real uses (count-down timer, stop flying volts, motor kill switch, flybarless)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
from illus import Art, ease
f = Film('RXSETUP1', 'Model options', "This model's trims, motor switch, timer and warnings")
model_route(f, 'Options')
opn = prefix('9.txt', '9_open') + 'n1.val=3\n'                         # (throttle on channel 3, as the Channels page names it)
f.shot('p', opn)
f.shot('fbl', opn + 'n3.val=0\n')                                      # a flybarless helicopter: the trims off
f.shot('timer', opn + 'n3.val=0\nc2.val=1\nclick c2,0\nn4.val=5\n')     # ... and a five-minute count-down
f.line('title', "Model options. This model's trims, motor switch, timer and warnings.")
f.line('page', "This is the Model options page. Touch a box to type a new value, or a switch to turn it on or off.")
f.line('trim', 'Trim multiplier: how far each trim step moves. Five is a very good default, and nought turns the trims off.')
f.line('copy', 'Copy trims to all banks: on, a trim change goes to every bank. Off, each bank keeps its own.')
f.line('throttle', "Throttle channel: the channel your motor's E S C is on. Usually three.")
f.line('motoroff', "Motor off value, in microseconds: what the throttle channel gets while the motor's off, or the safety's on. Eight hundred and thirty-three is nearly always right.")
f.line('kill', 'Use motor kill switch: on, the transmitter checks the motor switch before the model connects.')
f.line('countdown', "Timer counts down: on, the timer counts down from the minutes just below, and says the last ten seconds.")
f.line('volts', "Stop flying volts, per cell: when the model's battery drops below this, the transmitter says Stop flying.")
f.line('ok', 'OK keeps your changes, and goes to the front page.')
f.line('fbl', "Now, some real uses. Flying a flybarless helicopter? Set Trim multiplier to nought. The flight controller holds it steady, so the trims would only get in the way.")
f.line('killuse', "Keep the motor kill switch on. If your motor switch is on as the model connects, the transmitter waits until you switch it off. So, no surprise spool-up!")
f.line('timer', "Here's a great one. Time a few flights, then count down from your pack's safe flight time. The timer only runs while the motor's on.")
f.line('timer2', "With Timer voice on, in Sounds etc., it says Stop flying when the time's up. You'll never forget to land!")
f.line('sag', "Now, Stop flying volts. Here's why it's tricky. The battery sags while the motor works hard, then recovers a little when it stops.")
f.line('voltsuse', "So set it a little lower than you might think. Then fine-tune it, flight by flight: every model's different.")
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Options', 'p')
f.say('page', 'Model options.')
f.point(*at('RXOptionsView', 'n3'), 'trim', 'Trim multiplier.')
f.point(*at('RXOptionsView', 'c1'), 'copy', 'Copy trims to all banks.')
f.point(*at('RXOptionsView', 'n1'), 'throttle', 'Throttle channel.')
f.point(*at('RXOptionsView', 'n0'), 'motoroff', 'Motor off value.')
f.point(*at('RXOptionsView', 'c0'), 'kill', 'Motor kill switch.')
f.point(*at('RXOptionsView', 'c2'), 'countdown', 'Timer counts down.')
f.point(*at('RXOptionsView', 't10'), 'volts', 'Stop flying volts.')
f.point(*at('RXOptionsView', 'b2'), 'ok', 'OK keeps the changes.')
f.show('fbl'); f.point(*at('RXOptionsView', 'n3'), 'fbl', 'Tip: flybarless? Trims at 0.')
f.point(*at('RXOptionsView', 'c0'), 'killuse', 'Tip: no surprise spool-up.')
f.show('timer'); f.point(*at('RXOptionsView', 'n4'), 'timer', 'Tip: count down a safe flight.')
f.cap = None; f.say('timer2', 'Timer voice: Sounds etc.')
art = Art(f)
def sag(t):
    """the pack's cells: 3.82 V, sagging to 3.55 V while the motor works, then recovering to 3.72 V once it stops"""
    if t < 1.6: return art.battery(t, cells=6, volts=3.82 - 0.27 * ease((t - 0.3) / 0.9), title='Motor working: it sags')
    return art.battery(t, cells=6, volts=3.55 + 0.17 * ease((t - 1.9) / 0.8), title='Motor stopped: it recovers')
f.show(sag(0)); f.anim(sag, 3.2); f.say('sag', 'Tip: it sags, then recovers.')
f.show('timer'); f.point(*at('RXOptionsView', 't10'), 'voltsuse', 'Tip: set it a little lower.')
f.end(); f.finish()
