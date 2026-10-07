#!/usr/bin/env python3
"""The Rotorflight menu (sd/hmi/pages/8.json, RFView) and its settings page (61.json, RFSetupView): screen 1.11.26, B56.
Malcolm, 7 Oct: "The backup and restore option should be at the bottom ... I suspect this screen will become a bit
overcrowded" - so the four settings (link rates and banks, version, arming channel, main RPM ratio) go to a page of
their own, and the menu is a grid of up to nine buttons. The main board addresses components by NAME: the menu keeps
t0, card, b0 (Help), t11 (model name), va0, b4 (OK), Progress, t14 (bank), t8 (rate), pipe; the settings page keeps
t3/sw0, t4/t5, t6/Arming, t1/Ratio with their events. Re-run after a change here: python3 hmi/rfmenu_pages.py"""
import json, os, copy
HERE = os.path.dirname(os.path.abspath(__file__)); PAGES = os.path.join(HERE, '..', 'sd', 'hmi', 'pages')
menu = json.load(open(os.path.join(PAGES, '8.json')))
by = {c['n']: c for c in menu['comps']}
if os.path.exists(os.path.join(PAGES, '61.json')):          # the settings' components live on the settings page once it exists
    for c in json.load(open(os.path.join(PAGES, '61.json')))['comps']: by.setdefault(c['n'], c)
def comp(proto, **kw):
    c = copy.deepcopy(proto); c.update(kw); return c

# ---- the settings page, from the menu's own components
settings = []; i = [1]
def add(lst, c): c['i'] = i[0]; i[0] += 1; lst.append(c); return c
add(settings, comp(by['t0'], txt='Rotorflight settings'))
add(settings, comp(by['card']))
add(settings, comp(by['t14'])); add(settings, comp(by['t8']))
add(settings, comp(by['t11'], x=34, y=352, w=732, h=46))
add(settings, comp(by['va0']))
h = comp(by['b0']); h['ev'] = {'r': 'print "HelpView:RFSETUP.TXT"\nLogView.t0.txt="Rotorflight settings help"\nLogView.return.txt="RFSetupView"'}; add(settings, h)
for lab, val in (('t3', 'sw0'), ('t4', 't5'), ('t6', 'Arming'), ('t1', 'Ratio')):
    add(settings, comp(by[lab]))
    add(settings, comp(by[val]))
ok = comp(by['b4']); ok['ev'] = {'r': 'va0.val=82<<8\nprint va0.val'}; add(settings, ok)
page61 = {'name': 'RFSetupView', 'id': 61, 'w': 800, 'h': 480, 'bg': menu['bg'], 'nav': menu['nav'], 'ev': {'preinitialize': 'RFSetupView.pic=Screen_Background'}, 'comps': settings}
json.dump(page61, open(os.path.join(PAGES, '61.json'), 'w'), indent=1)

# ---- the menu: a grid of buttons
i = [1]; comps = []
add(comps, comp(by['t0']))
add(comps, comp(by['card']))
add(comps, comp(by['b0']))
add(comps, comp(by['t14'])); add(comps, comp(by['t8']))
add(comps, comp(by['va0']))
BUTTONS = [  # (name, words, code) in the order they sit, three to a row: the pages with values to edit first, the settings last
    ('Pid', 'PIDs ...', 18), ('b1', 'Rates ...', 22), ('b2', 'Governor ...', 50),
    ('Rescue', 'Rescue ...', 64), ('Servos', 'Servos ...', 73), ('Travel', 'Travel extents ...', 83),
    ('Setup', 'Settings ...', 81),
]
proto = by['Pid']
for k, (name, words, code) in enumerate(BUTTONS):
    b = comp(proto, n=name, x=34 + 246 * (k % 3), y=84 + 66 * (k // 3), w=240, h=56, txt=words); b['ev'] = {'r': 'va0.val=%d<<8\nprint va0.val' % code}
    add(comps, b)
add(comps, comp(by['t11'], x=34, y=300, w=480, h=40))
add(comps, comp(by['pipe'], x=524, y=300, w=242, h=40))
add(comps, comp(by['Progress']))
bk = comp(by['b3'], n='b3', x=14, y=414, w=260, h=56, txt='Backup / Restore ...'); bk['ev'] = {'r': 'va0.val=48<<8\nprint va0.val'}; add(comps, bk)
add(comps, comp(by['b4']))
menu['comps'] = comps
json.dump(menu, open(os.path.join(PAGES, '8.json'), 'w'), indent=1)
idx = json.load(open(os.path.join(PAGES, '..', 'index.json')))
have = {x['id'] for x in idx['pages']}
if 61 not in have: idx['pages'].append({'id': 61, 'name': 'RFSetupView', 'n': len(settings)})
for x in idx['pages']:
    if x['id'] == 8: x['n'] = len(comps)
idx['pages'].sort(key=lambda x: x['id'])
json.dump(idx, open(os.path.join(PAGES, '..', 'index.json'), 'w'), indent=1)
print('8 RFView:', len(comps), 'components;', '61 RFSetupView:', len(settings))
