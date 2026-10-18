#!/usr/bin/env python3
"""Film COPYBANK: copying a bank - a tour, then tune bank 1 and copy it on, adjusted for a faster head speed. The facts are
COPYBANK.TXT's; the page as it opens in bank 1, the question, the busy line and the answer are RF_CopyBank.h's (StartCopyBankView:
From = the bank in use, To = the next; CbHsFactor: 2000 to 2200 rpm = (2000/2200)^1.5 = gains down 13 %). Made with
dev/video/filmkit.py.
18 Oct 2026: starts on the Rotorflight menu; livelier words; "In practice" after the tour; no closing line (Malcolm)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs
f = Film('COPYBANK', 'Copy a bank', "One bank's tuning into another")
rf_route(f, 'Copy a bank ...')
opn = rfs('71.txt', '71_open', 'tn0.txt="Bank 1"\ntn1.txt="Bank 2"\nb3.txt="Copy bank 1 to bank 2"\n')   # (opened in bank 1)
hs = opn + 'tn6.val=1\n'                                                                                # Adjust for head speed on
f.shot('p', opn); f.shot('hs', hs)
f.shot('ask', hs + 'page PopupView\nDialog.txt="Copy bank 1 to bank 2?\\r\\nBank 2\'s own values for what is\\r\\nswitched on are overwritten."\n')
f.shot('busy', hs + 'vis busy,1\nbusy.txt="Adjusting the gains for the head speed ..."\n')
f.shot('done', hs + 'page PopupView\nvis b1,0\nDialog.txt="Copied bank 1 to bank 2: flight tuning, rates, governor gains (head speed kept).\\r\\nRead back the same.\\r\\n'
                    'Gains down 13 % for bank 2\'s faster head speed (2000 to 2200 rpm)."\n')
f.line('title', "Copy a bank. Tune one bank, then give its tuning to the others.")
f.line('page', 'This is the Copy a bank page. It copies the tuning of one bank into another.')
f.line('from', 'Tap the box beside From bank, for the bank to copy. Each tap steps to the next bank.')
f.line('to', 'And the box beside To bank, for the bank to copy into.')
f.line('what', "Then switch on what to copy. Green is on. Flight tuning is the P I Ds, P I D plus, and rescue. Then there's the rates, and the governor's gains.")
f.line('tune1', "Here's the best way to use it. Get bank one flying just right. Then copy it into your other banks, one at a time.")
f.line('hs', "Do your banks fly at different head speeds? Switch on Adjust for head speed. A tune that's right at one head speed is too sharp at a faster one, so the gains are scaled to suit.")
f.line('hs2', "But leave Head speed too switched off. Each bank keeps its own head speed: that's usually the whole point of having banks.")
f.line('copy', 'Ready? Press Copy bank one to bank two.')
f.line('ask', "It asks first, because bank two's own values are overwritten. Press OK.")
f.line('busy', "While it runs, leave the bank switch alone.")
f.line('done', "When it's finished, it tells you what it copied, and how much it changed the gains.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Copy a bank ...', 'p')
f.say('page', 'Copy a bank.')
f.point(*at('CopyBankView', 'tn0'), 'from', 'From bank.')
f.point(*at('CopyBankView', 'tn1'), 'to', 'To bank.')
f.point(*at('CopyBankView', 'tn2'), 'what', 'What to copy.')
f.point(*at('CopyBankView', 'b3'), 'tune1', 'Tip: tune bank 1, copy it on.')
f.show('hs'); f.point(*at('CopyBankView', 'tn6'), 'hs', 'Tip: different head speeds?')
f.point(*at('CopyBankView', 'tn5'), 'hs2', 'Tip: leave Head speed too off.')
f.cap = None; f.say('copy', "Press 'Copy bank 1 to bank 2'.", after=0.3); f.tap(*at('CopyBankView', 'b3'), 'ask')
f.say('ask', 'Press OK.', after=0.3); f.tap(*at('PopupView', 'b0'), 'busy')
f.say('busy', 'Leave the bank switch alone.')
f.show('done'); f.say('done', 'What was copied, and the gains.', after=1.0)
f.end(); f.finish()
