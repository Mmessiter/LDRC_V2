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
h = rp.comp(rp.by['b0'], n='b0'); h['ev'] = {'r': 'print "HelpView:BACKUP.TXT"\nLogView.t0.txt="Backup (Rotorflight) help"\nLogView.return.txt="RFBackUpView"'}; add(h)   # (polish: the help's title is the page's title + " help")
# B91: an island - the two lines of fact across it; under them the guidance, and beside it the four things to do with the
# backup as a block of two by three (Back up, Restore all / Diff to card, Execute diff / Write edits, Forget edits); OK
# alone at the foot, at the right
W = 704; BW = 176; GW = 2 * BW + rp.C_BTN_GAP; GH = 3 * rp.C_BTN_H + 2 * 10
# Fix (11 Oct, review of the merged polish): the edits line is TWO lines high and wraps - the main board writes
# "Edits waiting: %.80s" (RF_Backup.h BakShowPage), up to about 930 px of words; five edited items already measure 770 px
# and were cut in a one-line 704 box. 56 = two lines of font 2 (24 px each) and a little air.
I1_H = 56; GY = 40 + I1_H + 12   # (GY: where the guidance and the block start, under the two lines of fact)
isl = rp.island(W, GY + GH, [('b1', 'OK', 115)])   # (BW: the block's buttons a little wider than the row's, for "Command line"; GH: the block of six, three rows)
comps[1].update(x=isl['card'][0], y=isl['card'][1], w=isl['card'][2], h=isl['card'][3])
X, Y = isl['x0'], isl['y0']
for nm, y, h, txt in (('i0', Y, 36, 'No backup of this model on the card yet'), ('i1', Y + 40, I1_H, 'No edits waiting')):
    f = rp.comp(rp.LABEL_L, n=nm, x=X, y=y, w=W, h=h, txt=txt, g='g')
    f['c'] = dict(f['c'], pco=0, bco=rp.PALE[0]); f['a'] = dict(f['a'], txt_maxl=90)
    if nm == 'i1': f['a']['isbr'] = 1   # (wraps at a space: the list of edits on two lines)
    add(f)
# Fix (11 Oct): the guidance is the one thing to do; the why (the pages edit this backup with no model connected, Write
# edits sends them later) is BACKUP.TXT's "Without the model" and "Write edits" paragraphs - explanations live in the help
g = rp.comp(rp.LABEL_L, n='i2', x=X, y=Y + GY, w=W - GW - 16, h=GH, g='g', font=2,
            txt='Back up after every setup you are happy with.')   # (1.11.40: do first, why second, and shorter)
g['c'] = {'pco': 65535, 'borderc': rp.CARD['c']['bco'], 'bco': rp.CARD['c']['bco']}; g['a'] = dict(g['a'], borderw=0, xcen=0, ycen=0, txt_maxl=300, isbr=1); add(g)
gx = X + W - GW
# screen 1.11.41/42: the third row is the screen's own - "Diff to card" (diff all onto the screen's card, as a text file the
# configurator can replay) and "Execute diff" (the newest such file of the model, every command of it to the command
# line, then save - Malcolm, 10 Oct): the words "ldrc diff" / "ldrc exec" open the screen's page and never reach the
# main board (the command line itself is on the Rotorflight menu, "ldrc cli")
# Polish (10 Oct): the pair that comes and goes (Write edits / Forget edits: the main board hides Write edits when no edits
# wait) is the block's LAST row, so a hidden button leaves its gap at the foot, by OK, not in the middle of the block -
# rows: Back up / Restore all, Diff to card / Execute diff, Write edits / Forget edits. (The list keeps its order: the
# buttons keep their ids; only the rows change.)
for nm, txt, col, row, code in (('b3', 'Back up', 0, 0, 111), ('b2', 'Restore all', 1, 0, 112), ('b4', 'Write edits', 0, 2, 113), ('b5', 'Forget edits', 1, 2, 114), ('ldrcDiff', 'Diff to card', 0, 1, 'ldrc diff'), ('ldrcExec', 'Execute diff', 1, 1, 'ldrc exec')):
    b = rp.comp(rp.BUTTON, n=nm, x=gx + col * (BW + rp.C_BTN_GAP), y=Y + GY + row * (rp.C_BTN_H + 10), w=BW, h=rp.C_BTN_H, txt=txt)
    b['ev'] = {'r': code} if isinstance(code, str) else {'r': 'va0.val=%d<<8\nprint va0.val' % code}; add(b)
for (nm, txt, x, y, w, code) in isl['btn']:
    b = rp.comp(rp.BUTTON, n=nm, x=x, y=y, w=w, h=rp.C_BTN_H, txt=txt); b['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}; add(b)
# Fix (11 Oct, touch audit): the progress ("Reading 12 of 65: bank 3, advanced PIDs", BakBusy / BakProgress) in the
# guidance's place, beside the block - over words only. Over the island's middle it took the taps of Diff to card and
# Execute diff while it showed (the screen's hit(): the topmost visible part wins, events or not)
add(rp.message_box(rect=(X, Y + GY, W - GW - 16, GH)))
out = {'name': 'RFBackUpView', 'id': 12, 'w': 800, 'h': 480, 'bg': rp.rates['bg'], 'nav': rp.rates['nav'], 'ev': {'preinitialize': 'vis busy,0\nRFBackUpView.pic=Screen_Background'}, 'comps': comps}
json.dump(out, open(os.path.join(rp.PAGES, '12.json'), 'w'), indent=1)
idx = json.load(open(os.path.join(rp.PAGES, '..', 'index.json')))
for x in idx['pages']:
    if x['id'] == 12: x['n'] = len(comps)
json.dump(idx, open(os.path.join(rp.PAGES, '..', 'index.json'), 'w'), indent=1)
print(12, 'RFBackUpView', len(comps), 'components')
