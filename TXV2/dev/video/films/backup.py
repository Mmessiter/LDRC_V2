#!/usr/bin/env python3
"""Film BACKUP: Backup & restore - a tour (with a back up run), the edits made without the model, then the habits that make
it worth having: back up before an experiment, Restore all when it goes wrong, a diff file to share a set-up. The facts are
BACKUP.TXT's (one backup per model; about a minute; the bank switch left alone; Restore all replaces what the model has;
Diff to card needs the USB cable and the configurator can replay it; Send to model writes the marked edits); the question and
the progress line are RF_Backup.h's (scenario 12.txt). Made with dev/video/filmkit.py.
18 Oct 2026: starts on the Rotorflight menu; livelier words; "In practice" after the tour; no closing line (Malcolm)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import rf_route, rf_route_play, rfs
f = Film('BACKUP', 'Backup & restore', "This model's Rotorflight set-up, kept on the card")
rf_route(f, 'Backup & restore ...', spoken='Backup and restore')
opn = rfs('12.txt', '12_noedits')                                   # (a backup on the card, nothing waiting)
f.shot('p', opn)
f.shot('ask', opn + 'page PopupView\nDialog.txt="Back up every Rotorflight setting\\r\\nof this model to the card?\\r\\n(Any backup there already is replaced.)"\n')   # (12_question's words, over this model's page)
f.shot('busy', rfs('12.txt', '12_busy'))
NEW = 'i0.txt="Backup on the card: 2026-10-18 17:40 (412 lines)"\n'   # (the backup just made: BakShowPage's line, today)
f.shot('made', opn + NEW)
f.shot('edits', rfs('12.txt', '12_edits') + NEW)                          # (edits made with no model: Send to model shows)
f.line('title', "Backup and restore. A copy of this model's whole Rotorflight set-up, kept safe on the transmitter's card.")
f.line('page', "This is the Backup and restore page. There's one backup for each model.")
f.line('lines', 'The top line says which backup is on the card, and when it was made. The next one says whether any edits are waiting.')
f.line('backup', 'To make a backup, connect the model, then press Back up.')
f.line('ask', 'It asks first, because an older backup of this model is replaced. Press OK.')
f.line('busy', "Now it reads every setting from the flight controller, every bank. It takes about a minute, so leave the bank switch alone while it runs.")
f.line('restore', "Restore all writes the backup into the flight controller. It replaces what the model has now, so be sure it's the backup you mean.")
f.line('diff', "Diff to card keeps all the settings as text, on the screen's card. It needs the U S B cable, from the receiver to the flight controller.")
f.line('exec', 'Execute diff sends one of those files back to the flight controller.')
f.line('offline', "Here's something handy. With no model connected, the Rotorflight pages show the backup, and you can still make changes. They wait here, marked as edits.")
f.line('send', 'Next time the model connects, press Send to model, and the edits are written in.')
f.line('before', "Now the golden rule. Back up whenever the model flies well, and always before you experiment. It's your safety net.")
f.line('undo', "Experiment gone wrong? Restore all puts everything back, just as it was. One press, and you're flying your good set-up again.")
f.line('share', "And a diff file is plain text that the Rotorflight Configurator can replay. That's a neat way to share a set-up with a friend who flies the same helicopter.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Backup & restore ...', 'p')
f.say('page', 'Backup & restore.')
f.point(*at('RFBackUpView', 'i0'), 'lines', 'The backup, and edits waiting.')
f.point(*at('RFBackUpView', 'b3'), 'backup', 'Back up.')
f.tap(*at('RFBackUpView', 'b3'), 'ask')
f.say('ask', 'Press OK.', after=0.3); f.tap(*at('PopupView', 'b0'), 'busy')
f.say('busy', 'About a minute: bank switch alone.')
f.show('made')
f.point(*at('RFBackUpView', 'b2'), 'restore', 'Restore all.')
f.point(*at('RFBackUpView', 'ldrcDiff'), 'diff', 'Diff to card: USB cable.')
f.point(*at('RFBackUpView', 'ldrcExec'), 'exec', 'Execute diff.')
f.show('edits'); f.point(*at('RFBackUpView', 'i1'), 'offline', 'Tip: edit with no model.')
f.point(*at('RFBackUpView', 'b4'), 'send', 'Tip: then Send to model.')
f.show('made'); f.point(*at('RFBackUpView', 'b3'), 'before', 'Tip: back up, then experiment.')
f.point(*at('RFBackUpView', 'b2'), 'undo', 'Tip: gone wrong? Restore all.')
f.point(*at('RFBackUpView', 'ldrcDiff'), 'share', 'Tip: share a set-up.')
f.end(); f.finish()
