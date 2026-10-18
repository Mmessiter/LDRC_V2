#!/usr/bin/env python3
"""Film MACROS: a macro, a tour, and three ways pilots use them. The facts are MACROS.TXT's; the default channel names
(Ch 6 AUX1 ... Ch 9 AUX4) are TXV1B 1Definitions.h's ChannelNames. Made with dev/video/filmkit.py.
18 Oct 2026, Malcolm: "Let's add in some real uses people might not think of. For example a macro can do multiple things in
sequence for example by using one trigger channel for two macros where the WAIT on one macro is the same length as the
DURATION of another. These will run sequentially." """
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('MACROS', 'Macros', 'One flick of a switch, a timed move')
model_route(f, 'Macros')
opn = prefix('27.txt', '27_open')
def page(mno, tch, mch, name, pos, dl, du):
    return opn + 'Mno.val=%d\nTch.val=%d\nMch.val=%d\nchM.txt="%s"\nPos.val=%d\nDel.val=%d\nDur.val=%d\n' % (mno, tch, mch, name, pos, dl, du)
f.shot('p', opn)
f.shot('rescue', page(1, 7, 9, 'AUX4', 180, 0, 40))
f.shot('seq1', page(2, 8, 10, 'AUX5', 180, 0, 20))
f.shot('seq2', page(3, 8, 11, 'AUX6', 180, 20, 20))
f.line('title', 'Macros. One flick of a switch, and a channel moves by itself, for as long as you choose.')
f.line('page', "This is the Macros page. A macro moves one channel to a set position, for a set time, when you flick a switch.")
f.line('number', 'First, choose which macro to set up. There are eight of them.')
f.line('trigger', "The trigger channel starts it. That's usually a switch. When it reaches the very top of its travel, the macro runs. Nought turns the macro off.")
f.line('move', "Next, the channel to move. Its name appears beside it, so you can check it's the right one.")
f.line('position', 'Then where it moves to: from nought to a hundred and eighty. Ninety is the middle.')
f.line('times', 'Delay is how long it waits before moving. Duration is how long it stays there. Both are in tenths of a second, so thirty means three seconds.')
f.line('ok', 'Press OK to keep it.')
f.line('rescue', "Now, a real use. Here, the switch on channel seven moves channel nine to the top for four seconds. Give Rotorflight's rescue to channel nine, and one flick rescues the model, then hands it back to you by itself.")
f.line('rescue2', 'Set which channel rescue listens to with Switches, on the Rotorflight menu. And test it high up first.')
f.line('together', 'One switch can start several macros. Give them the same trigger, and they all run at once.')
f.line('seq1', "Here's a neat trick that many pilots never think of. Two macros can run one after the other. Macro two runs for two seconds.")
f.line('seq2', "Macro three has the same trigger, and its delay is two seconds: just as long as macro two runs. So the moment macro two finishes, macro three begins.")
f.line('seq3', 'For more than two, add each delay and duration together for the next one.')
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Macros', 'p')
f.say('page', 'Macros.')
f.point(*at('MacrosView', 'Mno'), 'number', 'Macro number.')
f.point(*at('MacrosView', 'Tch'), 'trigger', 'Trigger channel.')
f.point(*at('MacrosView', 'Mch'), 'move', 'Channel to move.')
f.point(*at('MacrosView', 'Pos'), 'position', 'Position.')
f.point(*at('MacrosView', 'Del'), 'times', 'Delay and Duration.')
f.point(*at('MacrosView', 'b10'), 'ok', 'OK keeps it.')
f.show('rescue'); f.say('rescue', 'Tip: a rescue that hands back.')
f.cap = None; f.say('rescue2', 'Rotorflight: Switches.')
f.say('together', 'One switch, several macros.')
f.show('seq1'); f.point(*at('MacrosView', 'Dur'), 'seq1', 'Macro 2: 2 seconds.')
f.show('seq2'); f.point(*at('MacrosView', 'Del'), 'seq2', 'Macro 3 waits 2 seconds.')
f.cap = None; f.say('seq3', 'One after the other.')
f.end(); f.finish()
