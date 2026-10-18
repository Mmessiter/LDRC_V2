#!/usr/bin/env python3
"""Film HEADSAG ("Fix a problem", 18 Oct 2026): the head speed sags when you climb or pump the collective - the likely cause
(the governor reacting too late), and the cure on the Governor page. Malcolm: "Let's include the likely cure for tail-wag
and other common set up issues."
The facts: RFGOVP.TXT (Anticipate yaw, cyclic and collective: "how much each stick adds throttle before the load arrives";
F gain: the strength of the three; Master gain scales P, I, D and F; P, I and D: how the governor corrects a head speed
error; 'Save' is refused while the model could be armed; it needs Rotorflight 2.3). The values are scenario 6's, RAW 420
MCM's own (2200 rpm, Master 50, Anticipate collective 60), and 60 -> 70 is the RFGOVP film's own change; a connected Save
only hides Save (RF_Governor_Profile.h SendEditedGovValues). The pictures are illus.py's head_sag and governor_hold.
Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play
from illus import Art

f = Film('HEADSAG', 'Head speed sags', 'The likely cause, and the cure')
art = Art(f)
rf_route(f, 'Governor ...')
opn = prefix('6.txt', '6_open')
f.shot('p', opn)
f.shot('antic', opn + 'n13.val=70\nvis b3,1\n')                     # (Anticipate collective 60 to 70: Save shows)
f.shot('saved', opn + 'n13.val=70\nvis b3,0\n')

f.line('title', "The head speed sags. Here's the likely cause, and the cure.")
f.line('symptom', "You climb, or pump the collective, and the head speed drops away. The tail may kick as it does.")
f.line('cause', "The governor is reacting too late. It can add throttle before the load arrives, if you let it.")
f.line('page', "This is the Governor page, for the bank in its title. It needs Rotorflight two point three.")
f.line('antic', "Anticipate collective adds throttle as the collective rises, before the head slows. Raise it a little.")
f.line('value', "Here, sixty becomes seventy. Then press Save, with the safety on: Save is refused while the model could be armed.")
f.line('gains', "Still sagging? Raise Master gain, or P and I, in small steps. And if the head speed surges or hunts, lower them instead.")
f.line('also', "Also worth checking: a tired or too small battery, and the gearing.")
f.line('hold', "Get it right, and the head speed holds steady, right through the climb.")
f.line('test', "One change, one flight.")
f.prepare()

f.begin(); f.say('title', after=1.2)
f.show(art.head_sag(0), look=0.3); f.anim(art.head_sag, 1.5); f.say('symptom')   # (it ends near the bottom of the sag: the needle low)
f.show(f.card('Likely cause', 'the governor reacts too late')); f.say('cause')
rf_route_play(f, 'Governor ...', 'p')
f.say('page', 'Governor.')
f.point(*at('RFGovView', 't41'), 'antic', 'Anticipate collective: raise it.', after=0.2)
f.under('antic'); f.hold(0.6)
f.say('value', '60 -> 70, then Save, safety on.', after=0.3)
f.tap(*at('RFGovView', 'b3')); f.under('saved'); f.hold(0.8)
f.point(*at('RFGovView', 't29'), 'gains', 'Tip: surges or hunts? Lower gains.')
f.show(f.card('Also worth checking', 'the battery, and the gearing')); f.say('also')
f.show(art.governor_hold(0), look=0.3); f.anim(art.governor_hold, 3.0); f.say('hold')
f.say('test', 'Tip: one change, one flight.')
f.end(); f.finish()
