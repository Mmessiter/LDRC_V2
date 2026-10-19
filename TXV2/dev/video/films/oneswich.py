#!/usr/bin/env python3
"""Film ONESWICH: one switch's job - a tour of the jobs, then three things worth knowing. The words are ONESWICH.TXT's (with
RXSETUP1.TXT: 'Bank 4 & Motor' is the motor switch, near = bank 4 with the motor OFF; B130: with Six banks on, mid and near pick 4, 5 or 6 by the Banks 1 2 3 switch). One job per switch is the Teensy's
ReadNewSwitchFunction (main.cpp): the switch that had the job lets go of it, and this switch's old job is then on no switch.
Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the model or transmitter screen; real uses): Transmitter setup > Switches > switch 3, each page
named as it appears. In practice: near is motor off, so 'Bank 4 & Motor' is the throttle hold - within easy reach; one job
per switch (check the Switches page after moving one); Reversed when a switch feels the wrong way round. Switch 6's channel
is "Channel 6" here, as on a heli (the scenario's "Flaps" is a plane's); on the Switches page the safety is on (switch 1
away) and the motor off (switch 3 near)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import tx_route, tx_route_play

f = Film('ONESWICH', "A switch's job", 'Choosing what one switch does')
tx_route(f, 'Switches')
f.shot('sw', prefix('53.txt', '53_open', [('p1.txt="near"', 'p1.txt="away"'), ('p3.txt="away"', 'p3.txt="near"'),
                                          ('sw6.txt="Flaps  R"', 'sw6.txt="Channel 6  "')]))
one = prefix('54.txt', '54_open', [('t11.txt="Flaps"', 't11.txt="Channel 6"')])
f.shot('p', one)
f.shot('rev', one + 'c_revd.val=1\n')
f.line('title', "A switch's job. Choosing what one switch does.")
f.line('switches', "This is the Switches page. Touch a switch's job to change it. Let's take switch three.")
f.line('page', "This is switch three's own page. Choose its job, then press OK to save it.")
f.line('banks', 'Banks one two three: away is bank one, mid is bank two, and near is bank three.')
f.line('motor', 'Bank four and Motor: away is motor on. Mid is bank four, with the motor on. Near is bank four, with the motor off. With Six banks on, mid and near pick bank four, five or six, by the Banks one two three switch.')
f.line('safety', 'Safety: near is safety off. With a Rotorflight model, safety off arms it.')
f.line('rates', 'Rates: away, mid and near pick rates one, two and three.')
f.line('buddy', 'Buddy hands control to the pupil. A spring-return switch is best for it.')
f.line('channel', "Channel five to sixteen: the switch becomes that channel's input.")
f.line('reversed', 'Reversed turns the switch round, so near and away swap.')
f.line('ok', 'Press OK to save.')
f.line('motor2', "Here's one worth knowing. Near is motor off, so this switch is your throttle hold. Put it where your finger finds it without looking.")
f.line('onejob', 'One job per switch. Give this switch Safety, say, and the switch that had it lets go. So check the Switches page afterwards: is every job still on a switch?')
f.line('rev2', 'And if a switch feels the wrong way round to you, turn on Reversed. The job stays the same: near and away just swap over.')
f.prepare()

f.begin(); f.say('title', after=1.2)
tx_route_play(f, 'Switches', 'sw')
f.say('switches', "Touch a switch's job.", after=0.3); f.tap(*at('SwitchesView', 'sw3'), 'p')
f.say('page', 'Switch 3.')
f.point(*at('OneSwitchView', 'r1'), 'banks', 'Banks 1 2 3.')
f.point(*at('OneSwitchView', 'r2'), 'motor', 'Bank 4 & Motor.')
f.point(*at('OneSwitchView', 'r7'), 'safety', 'Safety.')
f.point(*at('OneSwitchView', 'r8'), 'rates', 'Rates.')
f.point(*at('OneSwitchView', 'r9'), 'buddy', 'Buddy.')
f.point(*at('OneSwitchView', 'r3'), 'channel', 'A channel input.')
f.point(*at('OneSwitchView', 'c_revd'), 'reversed', 'Reversed.')
f.point(*at('OneSwitchView', 'b10'), 'ok', 'OK saves.')
f.point(*at('OneSwitchView', 'r2'), 'motor2', 'Tip: motor off, within reach.')
f.point(*at('OneSwitchView', 'r7'), 'onejob', 'Tip: one job per switch.')
f.show('rev'); f.point(*at('OneSwitchView', 'c_revd'), 'rev2', 'Tip: wrong way round? Reverse.')
f.end(); f.finish()
