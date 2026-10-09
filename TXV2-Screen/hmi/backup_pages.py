#!/usr/bin/env python3
"""The Rotorflight Backup page of the transmitter (screen 1.11.34, B70): sd/hmi/pages/12.json (RFBackUpView), in the style of
the Rescue pages. Two lines of fact (the backup on the card, the edits waiting), one patch of guidance, five buttons.
Re-run after a change here: python3 hmi/backup_pages.py"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue_pages as rp
# codes (the main board's NumberedFunctions1): 48 open (the menu), 111 Back up, 112 Restore all, 113 Write edits, 114 Forget edits, 115 OK
comps = []; i = [1]
def add(c): c['i'] = i[0]; i[0] += 1; comps.append(c); return c
add(rp.comp(rp.TITLE, n='t0', txt='Backup (Rotorflight)'))
add(rp.comp(rp.CARD, n='card'))
add(rp.comp(rp.BANK, n='t9', txt='No model'))
add(rp.comp(rp.MODEL, n='t11', txt='Model name'))
add(rp.comp(rp.VA0, n='va0'))
h = rp.comp(rp.by['b0'], n='b0'); h['ev'] = {'r': 'print "HelpView:BACKUP.TXT"\nLogView.t0.txt="Backup help"\nLogView.return.txt="RFBackUpView"'}; add(h)
for nm, y, txt in (('i0', 94, 'No backup of this model on the card yet'), ('i1', 134, 'No edits waiting')):
    f = rp.comp(rp.LABEL_L, n=nm, x=34, y=y, w=732, h=36, txt=txt, g='g')
    f['c'] = dict(f['c'], pco=0, bco=rp.PALE[0]); f['a'] = dict(f['a'], txt_maxl=90); add(f)
g = rp.comp(rp.LABEL_L, n='i2', x=34, y=186, w=732, h=96, g='g', font=2,
            txt='Back up after every setup you are happy with. With no model connected, the Rotorflight pages edit this backup; Write edits sends those edits to the model when it is connected.')   # (1.11.40: do first, why second, and shorter)
g['c'] = {'pco': 65535, 'borderc': rp.CARD['c']['bco'], 'bco': rp.CARD['c']['bco']}; g['a'] = dict(g['a'], borderw=0, xcen=0, ycen=0, txt_maxl=300, isbr=1); add(g)
for nm, txt, x, w, code in rp.bottom_row([('b3', 'Back up', 111), ('b2', 'Restore all', 112), ('b4', 'Write edits', 113), ('b5', 'Forget edits', 114), ('b1', 'OK', 115)]):
    b = rp.comp(rp.BUTTON, n=nm, x=x, y=414, w=w, h=56, txt=txt); b['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}; add(b)
add(rp.message_box(rect=(110, 296, 580, 108)))   # (1.11.40: the progress in a message box, below the two lines of fact)
out = {'name': 'RFBackUpView', 'id': 12, 'w': 800, 'h': 480, 'bg': rp.rates['bg'], 'nav': rp.rates['nav'], 'ev': {'preinitialize': 'vis busy,0\nRFBackUpView.pic=Screen_Background'}, 'comps': comps}
json.dump(out, open(os.path.join(rp.PAGES, '12.json'), 'w'), indent=1)
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
for x in idx['pages']:
    if x['id'] == 12: x['n'] = len(comps)
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
print(12, 'RFBackUpView', len(comps), 'components')
