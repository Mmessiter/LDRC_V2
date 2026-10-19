#!/usr/bin/env python3
"""Film BANKNAME: naming the banks, and why it helps in the air. 19 Oct 2026 (B130): four boxes, or six with Six banks on; the film shows four and the note where the two more would be. The facts are BANKNAME.TXT's; "Heli" sets Hover, Idle up 1,
Idle up 2 and Hold (the wheels' list, page 20: indexes 12, 13, 14, 21). The bank's name at the top left of pages that change
with the bank: Rates (DualRatesView t1) and Servo speed (SlowServoView t14). Made with dev/video/filmkit.py.
18 Oct 2026: starts on Model setup, no closing line, and an "In practice" part (Malcolm: "look beyond the simple
functions' description and also describe how to use for solving real-world flying issues")."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
f = Film('BANKNAME', 'Bank names', 'A name for each bank')
model_route(f, 'Bank names')
opn = prefix('20.txt', '20_open')
f.shot('p', opn); f.shot('heli', opn + 'BK1.val=12\nBK2.val=13\nBK3.val=14\nBK4.val=21\n')
f.line('title', 'Bank names. A name for each bank.')
f.line('page', "This is the Bank names page. Give each bank a name for what it does. The name shows on the front page, and it's spoken when you change bank.")
f.line('wheel', "Scroll each bank's list to the name you want.")
f.line('sets', 'Or press a set: Default, V Bar, Heli or Glider. For a helicopter, press Heli.')
f.line('heli', 'Now the banks are Hover, Idle up one, Idle up two, and Hold.')
f.line('listen', 'Listen plays the names in turn.')
f.line('six', "Four banks here. Turn on Six banks, on Model options, and two more boxes appear: banks five and six.")
f.line('ok', 'Press OK to save.')
f.line('voice', "Here's why it's worth doing. Flick the bank switch in flight, and you'll hear Idle up one. You know which bank you're in, without ever looking down.")
f.line('pages', "The name also shows at the top left of pages that change with the bank, such as Rates and Servo speed. So you always know which bank you're setting up.")
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Bank names', 'p')
f.say('page', 'Bank names.')
f.point(*at('BankNameView', 'BK1'), 'wheel', 'Scroll to a name.')
f.cap = None; f.say('sets', "Or a set: press 'Heli'.", after=0.3); f.tap(*at('BankNameView', 'b4')); f.under('heli'); f.hold(0.8)
f.say('heli', 'Hover, Idle up 1, Idle up 2, Hold.')
f.point(*at('BankNameView', 'b3'), 'listen', 'Listen.')
f.point(*at('BankNameView', 't7'), 'six', 'Six banks: Model options.')
f.point(*at('BankNameView', 'b10'), 'ok', 'OK saves.')
f.point(*at('BankNameView', 't2'), 'voice', 'Tip: hear it, eyes on the model.')
f.cap = None; f.say('pages', 'Tip: know which bank you set up.')
f.end(); f.finish()
