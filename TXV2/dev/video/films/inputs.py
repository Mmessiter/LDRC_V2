#!/usr/bin/env python3
"""Film INPUTS: what moves each channel, a tour, and three uses. The facts are INPUTS.TXT's; with the model connected,
Inputs asks first (scenario 4_q_inputs: "The model is connected. Changes here move its controls. Open Inputs anyway?").
The examples are the help's own: swap two Out numbers (Ch 4 Out 5, Ch 5 Out 4); one input moving two channels (two aileron
servos, Ch 6 In 1); a switch given the job 'Channel 9' as input 9 (Ch 9, named Lights). Made with dev/video/filmkit.py.
18 Oct 2026: starts on Model setup, no closing line, and an "In practice" part (Malcolm: "look beyond the simple
functions' description and also describe how to use for solving real-world flying issues")."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route
f = Film('INPUTS', 'Inputs', 'What moves each channel')
model_route(f, 'Inputs')
f.shot('ask', prefix('4.txt', '4_q_inputs'))
opn = prefix('39.txt', '39_open')
f.shot('p', opn)
f.shot('swap', opn + 'n7.val=5\nn8.val=4\n')                        # (Ch 4 Out 5, Ch 5 Out 4: n4..n19 are the Out boxes)
f.shot('ail2', opn + 'c6.val=1\nch6.txt="Aileron 2"\n')            # (Ch 6 takes In 1, the aileron stick)
f.shot('lights', opn + 'ch9.txt="Lights"\n')                       # (Ch 9 takes In 9: the switch with the job 'Channel 9')
# (the tips point at each row's 'Ch n' label, so its In, Name and Out stay in sight)
f.line('title', 'Inputs. What moves each channel, its name, and where it goes.')
f.line('ask', 'With the model connected, it asks first, because changes here move its controls. Press OK.')
f.line('page', 'This is the Inputs page. Touch any number or name to change it.')
f.line('in', 'In: the stick, switch or knob that moves this channel. One is the aileron stick, two elevator, three throttle and four rudder. Five to eight are the front switches and knobs.')
f.line('name', "Name: the channel's name, up to ten letters. Other pages show it too.")
f.line('out', 'Out: the receiver output this channel goes to. Each Out number can be used only once.')
f.line('trim', 'Trim out: which channels each trim moves. Most models keep these at one, two, three and four.')
f.line('ok', 'OK keeps the changes, and takes you back to Model setup. After any change here, test on the ground before you fly!')
f.line('swap', "Here's a lifesaver. A receiver output stopped working? Move that channel to a spare one by swapping two Out numbers. Here, channel four goes to output five, and channel five to output four.")
f.line('swap2', 'Then plug each servo into its new output, and check them on the ground.')
f.line('ail2', 'Two aileron servos? Give a spare channel In one, the aileron stick. Both then follow it, both take the aileron trim, and each can be reversed on its own.')
f.line('lights', 'And a spare switch can work your lights. Give it the job Channel nine, in Transmitter setup, Switches. Channel nine then follows that switch. Name it Lights, and every page says so.')
f.prepare()
f.begin(); f.say('title', after=1.2)
f.show('r_setup'); f.say('setup', 'Press Inputs.', after=0.3); f.tap(*at('RXSetupView', txt='Inputs'), 'ask')
f.say('ask', 'Press OK.', after=0.3); f.tap(*at('PopupView', 'b0'), 'p')
f.say('page', 'Inputs.')
f.point(*at('InputsView', 'c1'), 'in', 'In: what moves it.')
f.point(*at('InputsView', 'ch1'), 'name', 'Its name.')
f.point(*at('InputsView', 'n4'), 'out', 'Out: the receiver output.')
f.point(*at('InputsView', 'n0'), 'trim', 'Trim out.')
f.point(*at('InputsView', 'b10'), 'ok', 'Test on the ground!')
f.show('swap'); f.point(*at('InputsView', 't4'), 'swap', 'Tip: a dead output? Swap Outs.')
f.cap = None; f.say('swap2', 'Then check on the ground.')
f.show('ail2'); f.point(*at('InputsView', 't6'), 'ail2', 'Tip: two aileron servos.')
f.show('lights'); f.point(*at('InputsView', 't17'), 'lights', 'Tip: a switch for lights.')
f.end(); f.finish()
