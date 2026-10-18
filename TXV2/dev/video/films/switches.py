#!/usr/bin/env python3
"""Film SWITCHES: the Switches page - a tour, then three ways to choose the jobs well. The words are SWITCHES.TXT's (with
ONESWICH.TXT and INPUTS.TXT: a switch with the job 'Channel 9' is input 9, channel 9's own input by default; MACROS.TXT: a
macro's trigger is usually a switch). Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the model or transmitter screen; real uses): it starts on Transmitter setup. The page as a
heli's would be: the safety ON (switch 1 away) and the motor OFF (switch 3 near), and switch 6 its own channel's input
(the scenario's "Flaps R" is a plane's). In practice: Safety on a switch the finger finds without looking; Buddy on a
spring-return switch (let go, and the instructor flies again at once); a spare switch given the job 'Channel 9' becomes an
input, for lights or a macro's trigger."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import tx_route, tx_route_play

f = Film('SWITCHES', 'Switches', 'A job for each of the eight switches')
tx_route(f, 'Switches')
sw = prefix('53.txt', '53_open', [('p1.txt="near"', 'p1.txt="away"'), ('p3.txt="away"', 'p3.txt="near"'),
                                  ('sw6.txt="Flaps  R"', 'sw6.txt="Channel 6  "')])
f.shot('p', sw)
f.shot('p9', sw + 'sw8.txt="Channel 9  "\n')                        # (the spare switch 8 given the job Channel 9)
f.line('title', 'Switches. Give each of the eight switches its own job.')
f.line('page', 'This is the Switches page. Any of the eight switches can do any job.')
f.line('top', 'Switches one to four are on the top edge, shown as seen from above, with the sticks towards you.')
f.line('front2', "Switches five to eight are on the front. They're the inputs of channels five to eight.")
f.line('where', "Beside each job is where that switch is now: near, mid or away. Move a switch, and you'll see which number it is.")
f.line('rev', 'An R after a job means that switch is reversed.')
f.line('touch', "Touch a switch's number or its job to choose its job. That page has an animation of its own.")
f.line('ok', 'The jobs belong to the transmitter, so they stay the same whichever model you fly. OK goes back to Transmitter setup.')
f.line('safety', "Here's a tip worth knowing. Put Safety on a switch your finger finds without looking. When you need it, you'll need it fast.")
f.line('buddy', "Teaching a beginner? Give Buddy to a spring-return switch. Let go of it, and you're flying again at once.")
f.line('spare', 'Got a spare switch? Here, switch eight has no job.')
f.line('chan9', "Give it the job Channel nine, and it becomes channel nine's input. Use it for lights, or to start a macro.")
f.prepare()

f.begin(); f.say('title', after=1.2)
tx_route_play(f, 'Switches', 'p')
f.say('page', 'Switches.')
f.point(*at('SwitchesView', 'h0'), 'top', 'Top edge: 1 to 4.')
f.point(*at('SwitchesView', 'h1'), 'front2', 'Front: 5 to 8.')
f.point(*at('SwitchesView', 'p1'), 'where', 'Where each switch is now.')
f.point(*at('SwitchesView', 'sw4'), 'rev', 'R: reversed.')
f.point(*at('SwitchesView', 't3'), 'touch', 'Touch a switch to choose its job.')
f.point(*at('SwitchesView', 'b10'), 'ok', 'OK keeps the jobs.')
f.point(*at('SwitchesView', 't1'), 'safety', 'Tip: Safety within easy reach.')   # (on its number: the job beside it left clear)
f.show('p'); f.say('buddy', 'Tip: a spring switch for Buddy.')    # (the finger gone: no switch in particular)
f.point(*at('SwitchesView', 't8'), 'spare', 'Tip: a spare switch.')
f.show('p9'); f.point(*at('SwitchesView', 't8'), 'chan9', 'Lights, or a macro trigger.')
f.end(); f.finish()
