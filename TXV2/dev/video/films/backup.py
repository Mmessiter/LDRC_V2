#!/usr/bin/env python3
"""Film BACKUP: Backup & restore, a tour. The words are BACKUP.TXT's. Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play, tx_route, tx_route_play, rf_route, rf_route_play, rfs, SAVE_SHOWN, FRONT_NO_MODEL
f = Film('BACKUP', 'Backup & restore', "This model's Rotorflight set-up, kept on the card")
rf_route(f, 'Backup & restore ...')
f.shot('p', rfs('12.txt', '12_noedits'))
f.line('title', "Backup and restore. A copy of this model's Rotorflight set-up, on the transmitter's card.")
f.line('page', 'This is the Backup and restore page. There is one backup for each model. The lines at the top say which backup is on the card, and which edits are waiting.')
f.line('backup', 'Connect the model, then press Back up, and OK to the question. It reads everything from the flight controller: about a minute. Do not move the bank switch while it runs.')
f.line('restore', 'Restore all writes every setting in the backup to the flight controller. Be sure it is the backup you mean.')
f.line('diff', 'Diff to card keeps all the settings as text on the screen\'s card. The Rotorflight configurator can replay that file.')
f.line('ok', 'OK goes back to the Rotorflight page.')
f.line('end', "That's the Backup and restore page.")
f.prepare()
f.begin(); f.say('title', after=1.6)
rf_route_play(f, 'Backup & restore ...', 'p')
f.say('page', 'Backup & restore.')
f.point(*at('RFBackUpView', 'b3'), 'backup', 'Back up.')
f.point(*at('RFBackUpView', 'b2'), 'restore', 'Restore all.')
f.point(*at('RFBackUpView', 'ldrcDiff'), 'diff', 'Diff to card.')
f.point(*at('RFBackUpView', 'b1'), 'ok', 'OK.')
f.end('end'); f.finish()
