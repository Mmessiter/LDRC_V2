#!/usr/bin/env python3
"""Film BANKNAME: naming the banks. The words are BANKNAME.TXT's; "Heli" sets Hover, Idle up 1, Idle up 2 and Hold (the
wheels' list, page 20: indexes 12, 13, 14, 21). Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('BANKNAME', 'Bank names', 'A name for each bank')
model_route(f, 'Bank names')
opn = prefix('20.txt', '20_open')
f.shot('p', opn); f.shot('heli', opn + 'BK1.val=12\nBK2.val=13\nBK3.val=14\nBK4.val=21\n')
f.line('title', 'Bank names. A name for each of the four banks.')
f.line('page', 'This is the Bank names page. Each name shows on the front page, and is spoken when you change bank.')
f.line('wheel', "Scroll each bank's list to the name you want.")
f.line('sets', 'Or press a set of four. For a helicopter, press Heli.')
f.line('heli', 'Hover, Idle up one, Idle up two, and Hold.')
f.line('listen', 'Listen plays the four names in turn.')
f.line('ok', 'Press OK to save.')
f.line('end', "That's how to name the banks.")
f.prepare()
f.begin(); f.say('title', after=1.6)
model_route_play(f, 'Bank names', 'p')
f.say('page', 'Bank names.')
f.point(*at('BankNameView', 'BK1'), 'wheel', 'Scroll to a name.')
f.cap = None; f.say('sets', "Or a set: press 'Heli'.", after=0.3); f.tap(*at('BankNameView', 'b4')); f.under('heli'); f.hold(0.8)
f.say('heli', 'Hover, Idle up 1, Idle up 2, Hold.')
f.point(*at('BankNameView', 'b3'), 'listen', 'Listen.')
f.point(*at('BankNameView', 'b10'), 'ok', 'OK saves.')
f.end('end'); f.finish()
