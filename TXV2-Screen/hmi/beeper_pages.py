#!/usr/bin/env python3
"""B195 (Malcolm, 6 Nov 2026: the Rotorflight gap list, Phase 1, "for 16meg screens only"): page 84 BeeperView,
'Beeper & name' - Rotorflight's own name for the model (MSP 10/11) and its beeper (MSP 184/185: the buzzer's
events, and the DShot motor beacon). The Teensy's side is TXV1B include/RF_Beeper.h (codes 232-235).
Also the Rotorflight menu's button for it (page 8, the free slot of row 5), hidden by the page's own script on a
4 MB screen (screen 1.11.186: ldrcmb = 16 on the FULL build), and index.json's part counts.
Run from the project: python3 hmi/beeper_pages.py"""
import copy, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, '..', 'sd', 'hmi', 'pages')
INDEX = os.path.join(HERE, '..', 'sd', 'hmi', 'index.json')
PAGE_ID, NAME = 84, 'BeeperView'


def load(i):
    return json.load(open(os.path.join(PAGES, '%d.json' % i)))


def save(i, p):
    json.dump(p, open(os.path.join(PAGES, '%d.json' % i), 'w'), indent=1)


def code(n):
    return 'va0.val=%d<<8\nprint va0.val' % n


bat = load(72)
B = {c['n']: c for c in bat['comps']}
SW = {'t': 'switch', 'g': 'g', 'font': 2, 'c': {'pco1': 0, 'bco2': 2016, 'pco': 65535, 'bco': 33808, 'pco2': 65535},
      'txt': 'off/on', 'val': 0, 'a': {'dez': 0, 'dis': 100, 'txt_maxl': 24}}

comps = []
def add(c):
    c = copy.deepcopy(c); c['i'] = len(comps) + 1; comps.append(c); return c

t0 = add(B['t0']); t0['txt'] = 'Beeper & name'
add(dict(B['card'], y=66, h=404))
add(B['t9']); add(B['t11']); add(B['va0'])
b0 = add(B['b0']); b0['ev'] = {'r': 'print "HelpView:BEEPER.TXT"\nLogView.t0.txt="Beeper & name help"\nLogView.return.txt="BeeperView"'}
# the name
l = add(B['ltn0']); l.update(n='ltn0', x=49, y=78, w=250, h=40, txt='Name in Rotorflight')
t = add(B['tn0']); t.update(n='tn0', x=305, y=78, w=445, h=40, txt='')
t['a'] = dict(t['a'], key=1, txt_maxl=16); t['ev'] = {'p': 'keybdA.t1.txt="Rotorflight\'s name for the model (up to 16)"', 'r': code(235)}
# the buzzer: eight events, a switch each (on = it beeps)
h0 = add(B['h0']); h0.update(n='h0', x=49, y=126, w=366, h=36, txt='Buzzer beeps')
BUZZ = ['Power on', 'Arming', 'Disarming', 'Armed, motor stopped', 'Link lost', 'Battery low', 'Battery very low', 'The Beeper switch']
for k, words in enumerate(BUZZ):
    y = 168 + 34 * k
    a = add(B['ltn0']); a.update(n='lsw%d' % (k + 1), x=49, y=y, w=250, h=30, font=2, txt=words); a['ev'] = {'p': 'click sw%d,1\nclick sw%d,0' % (k + 1, k + 1)}
    s = add(dict(SW, n='sw%d' % (k + 1), x=315, y=y, w=80, h=30)); s['ev'] = {'r': code(235)}
# the motor beacon
h1 = add(B['h1']); h1.update(n='h1', x=435, y=126, w=315, h=36, txt='Motor beeps (DShot)')
for k, words in enumerate(['The Beeper switch', 'Link lost']):
    y = 168 + 34 * k
    a = add(B['ltn4']); a.update(n='lsw%d' % (k + 9), x=435, y=y, w=220, h=30, font=2, txt=words); a['ev'] = {'p': 'click sw%d,1\nclick sw%d,0' % (k + 9, k + 9)}
    s = add(dict(SW, n='sw%d' % (k + 9), x=670, y=y, w=80, h=30)); s['ev'] = {'r': code(235)}
a = add(B['ltn4']); a.update(n='ltn1', x=435, y=236, w=220, h=30, font=2, txt='Tone (1 - 5)')
t = add(B['tn4']); t.update(n='tn1', x=670, y=236, w=80, h=30, font=2, txt='1')
t['ev'] = {'r': 'keybdB.t1.txt="Motor beep tone (1 - 5)"\n' + code(235)}
s3 = add(B['b3']); s3.update(x=418, y=396, ev={'r': code(234)})
s1 = add(B['b1']); s1.update(x=590, y=396, ev={'r': code(233)})
add(B['busy'])

page = {'name': NAME, 'id': PAGE_ID, 'w': 800, 'h': 480, 'bg': bat['bg'], 'nav': bat['nav'], 'ev': {'preinitialize': 'vis busy,0\nBeeperView.pic=Screen_Background'}, 'comps': comps}
save(PAGE_ID, page)

# the Rotorflight menu: 'Beeper & name ...' in row 5's free slot, 16 MB screens only
m = load(8)
M = {c['n']: c for c in m['comps']}
if 'bBeep' not in M:
    ref = next(c for c in m['comps'] if c.get('txt', '').startswith('Black box'))
    row5 = next(c for c in m['comps'] if c.get('txt', '').startswith('Command line'))
    nb = copy.deepcopy(ref); nb.update(n='bBeep', i=max(c['i'] for c in m['comps']) + 1, y=row5['y'], txt='Beeper & name ...', ev={'r': code(232)})
    m['comps'].insert(m['comps'].index(ref) + 1, nb)
    m['ev']['preinitialize'] = m['ev'].get('preinitialize', '') + '\nif(ldrcmb<16)\n{\n  vis bBeep,0\n}'
    save(8, m)

# index.json: page 84 added (the part count "n" is kept by hand: +2 on pages 5 and 6 for B195's tabs/switch, +1 on page 8)
ix = json.load(open(INDEX))
if not any(p['id'] == PAGE_ID for p in ix['pages']):
    ix['pages'].append({'id': PAGE_ID, 'name': NAME, 'n': len(comps)})
    for p in ix['pages']:
        p['n'] += {5: 2, 6: 2, 8: 1}.get(p['id'], 0)
    json.dump(ix, open(INDEX, 'w'), indent=1)
print('page %d %s: %d parts; menu button; index %d pages' % (PAGE_ID, NAME, len(comps), len(ix['pages'])))
