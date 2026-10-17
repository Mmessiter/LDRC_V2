#!/usr/bin/env python3
"""Film COPYBANK: copying a bank. The words are COPYBANK.TXT's; the question is RF_CopyBank.h's ("Copy bank 2 to bank 1?
Bank 1's own values for what is switched on are overwritten."). Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
f = Film('COPYBANK', 'Copy a bank', "One bank's tuning into another")
rf_route(f, 'Copy a bank ...')
opn = rfs('71.txt', '71_open')
f.shot('p', opn); f.shot('ask', opn + 'page PopupView\nDialog.txt="Copy bank 2 to bank 1?\\r\\nBank 1\'s own values for what is\\r\\nswitched on are overwritten."\n')
f.shot('busy', rfs('71.txt', '71_busy'))
f.line('title', "Copy a bank. One bank's tuning into another.")
f.line('page', 'This is the Copy a bank page. Tune one bank, then give its tuning to the others.')
f.line('from', 'Tap the box beside From bank for the bank to copy. Each tap steps to the next bank.')
f.line('to', 'And the box beside To bank, for the bank to copy into.')
f.line('what', 'Switch on what to copy: green is on. Flight tuning is the P I Ds, P I D plus, and rescue.')
f.line('copy', 'Then press Copy bank two to bank one.')
f.line('ask', "It asks first: bank one's own values are overwritten. Press OK.")
f.line('busy', 'Do not move the bank switch while it runs.')
f.line('end', "That's how to copy a bank.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Copy a bank ...', 'p')
f.say('page', 'Copy a bank.')
f.point(*at('CopyBankView', 'tn0'), 'from', 'From bank.')
f.point(*at('CopyBankView', 'tn1'), 'to', 'To bank.')
f.point(*at('CopyBankView', 'tn2'), 'what', 'What to copy.')
f.cap = None; f.say('copy', "Press 'Copy bank 2 to bank 1'.", after=0.3); f.tap(*at('CopyBankView', 'b3'), 'ask')
f.say('ask', 'Press OK.', after=0.3); f.tap(*at('PopupView', 'b0'), 'busy')
f.say('busy', 'Leave the bank switch alone.', after=1.0)
f.end('end'); f.finish()
