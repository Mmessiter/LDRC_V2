#!/usr/bin/env python3
"""B196 (Malcolm, 8 Nov 2026: "Please do all five ... Take your time!"): GUIDE & CHECKS, 16 MB screens only.
Pages 85 RFToolsView (the five tools and the command line), 86 RFCheckView (Check my setup), 87 RFDirView (the
Direction check), 88 RFChangesView (What changed?), 89 RFGuideView (the New helicopter guide). The Teensy's side is
TXV1B include/RF_Tools.h, RF_Check.h, RF_Direction.h, RF_Changes.h, RF_Guide.h, RF_Undo.h (codes 236-260).
The Rotorflight menu (page 8): "Guide & checks ..." in Command line's place on a 16 MB screen (the page's own script
- ldrcmb, screen 1.11.186 - hides it on a 4 MB one, where the menu stays exactly as it was), and index.json.
Every fixed word is measured with the screen's own font widths (fontw.py) before the page is written.
Run from the project: python3 hmi/tools_pages.py"""
import copy, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fontw import width

PAGES = os.path.join(HERE, '..', 'sd', 'hmi', 'pages')
INDEX = os.path.join(HERE, '..', 'sd', 'hmi', 'index.json')
def load(i): return json.load(open(os.path.join(PAGES, '%d.json' % i)))
def save(i, p): json.dump(p, open(os.path.join(PAGES, '%d.json' % i), 'w'), indent=1)
def code(n, row=None): return ('va0.val=%d<<24+(%d<<8)\nprint va0.val' % (row, n)) if row else ('va0.val=%d<<8\nprint va0.val' % n)

B = {c['n']: c for c in load(84)['comps']}       # Beeper & name (B195): the house style of these pages
bg, nav = load(84)['bg'], load(84)['nav']
WHITE, YELLOW, NAVY, GREY = 65535, 65504, 4426, 33808
BUTTON_C = dict(B['b1']['c'])

def fits(txt, font, w, what):
    px = width(font, txt)
    assert px <= w - 8, '%s: "%s" is %d px in font %d, the box %d' % (what, txt, px, font, w)

class Page:
    def __init__(self, pid, name, title, helpfile, helptitle):
        self.pid, self.name, self.comps = pid, name, []
        t0 = self.add(B['t0']); t0['txt'] = title; fits(title, 0, 800 - 2 * 220, name + ' title')
        self.add(B['card'])
        self.add(B['t9']); self.add(B['t11']); self.add(B['va0'])
        b0 = self.add(B['b0']); b0['ev'] = {'r': 'print "HelpView:%s"\nLogView.t0.txt="%s"\nLogView.return.txt="%s"' % (helpfile, helptitle, name)}
    def add(self, c, **kw):
        c = copy.deepcopy(c); c.update(kw); c['i'] = len(self.comps) + 1; self.comps.append(c); return c
    def text(self, n, x, y, w, h, font=2, colour=WHITE, txt='', xcen=0, wrap=0, bco=NAVY, maxl=120):
        return self.add({'n': n, 't': 'text', 'g': 'g', 'x': x, 'y': y, 'w': w, 'h': h, 'font': font, 'sta': 1,
                         'c': {'pco': colour, 'borderc': bco, 'bco': bco}, 'txt': txt,
                         'a': {'style': 0, 'key': 255, 'borderw': 0, 'xcen': xcen, 'ycen': 1, 'pw': 0, 'txt_maxl': maxl, 'isbr': wrap}})
    def button(self, n, x, y, w, h, txt, script, font=6, maxl=30):
        if txt: fits(txt, font, w, self.name + ' ' + n)
        return self.add({'n': n, 't': 'button', 'g': 'l', 'x': x, 'y': y, 'w': w, 'h': h, 'font': font, 'sta': 1, 'c': dict(BUTTON_C),
                         'txt': txt, 'val': 0, 'a': {'style': 4, 'borderw': 2, 'xcen': 1, 'ycen': 1, 'txt_maxl': maxl, 'isbr': 0},
                         'ev': {'r': script}})
    def marker(self, n, x, y, w, h, txt=''):
        return self.add({'n': n, 't': 'text', 'g': 'g', 'x': x, 'y': y, 'w': w, 'h': h, 'font': 2, 'sta': 1,
                         'c': {'pco': 0, 'borderc': GREY, 'bco': GREY}, 'txt': txt,
                         'a': {'style': 0, 'key': 255, 'borderw': 0, 'xcen': 1, 'ycen': 1, 'pw': 0, 'txt_maxl': 4, 'isbr': 0}})
    def ok(self, n_code): self.button('b1', 590, 396, 160, 50, 'OK', code(n_code))
    def finish(self, pre=''):
        self.add(B['busy'])
        return {'name': self.name, 'id': self.pid, 'w': 800, 'h': 480, 'bg': bg, 'nav': nav,
                'ev': {'preinitialize': 'vis busy,0\n%s.pic=Screen_Background%s' % (self.name, pre)}, 'comps': self.comps}

pages = {}
# ---- 85 Guide & checks
p = Page(85, 'RFToolsView', 'Guide & checks', 'TOOLS.TXT', 'Guide & checks help')
for (n, x, y, txt, scr) in (('bGuide', 49, 84, 'New helicopter guide ...', code(238)), ('bCheck', 411, 84, 'Check my setup ...', code(239)),
                            ('bDir', 49, 156, 'Direction check ...', code(240)), ('bChg', 411, 156, 'What changed? ...', code(241)),
                            ('bUndo', 49, 228, 'Undo the last save', code(242)), ('bCli', 411, 228, 'Command line ...', 'ldrc cli')):
    p.button(n, x, y, 340, 60, txt, scr)
p.text('tU', 49, 300, 702, 36, txt='Nothing to undo yet')
p.ok(237)
pages[85] = p.finish()

# ---- 86 Check my setup: a header, six rows (a mark, the words, a button), < > Check again OK
p = Page(86, 'RFCheckView', 'Check my setup', 'CHECK.TXT', 'Check my setup help')
p.text('hd', 49, 72, 702, 34, txt='Reading the flight controller ...')
for k in range(6):
    y = 112 + 46 * k
    p.marker('mk%d' % k, 49, y + 6, 16, 28)
    p.text('r%d' % k, 73, y, 516, 40)
    p.button('f%d' % k, 597, y, 154, 40, 'Calibrate ...', code(243, k + 1), font=2)
p.button('bP', 49, 396, 80, 50, '<', code(246))
p.button('bN', 139, 396, 80, 50, '>', code(247))
p.button('bA', 418, 396, 160, 50, 'Check again', code(244), font=2)
p.ok(245)
pages[86] = p.finish('\nvis bP,0\nvis bN,0' + ''.join('\nvis mk%d,0\nvis f%d,0' % (k, k) for k in range(6)))

# ---- 87 the Direction check
p = Page(87, 'RFDirView', 'Direction check', 'DIRCHECK.TXT', 'Direction check help')
p.text('do', 49, 72, 702, 40, font=6, txt='Stand the model level, then press Start.')
p.text('lv', 49, 116, 702, 30, colour=YELLOW, txt='')
for k in range(1, 4):
    y = 158 + 46 * (k - 1)
    p.marker('m%d' % k, 49, y + 6, 16, 28)
    p.text('s%d' % k, 73, y, 678, 40)
p.text('rs', 49, 300, 702, 88, wrap=1, maxl=160)
p.button('bT', 49, 396, 240, 50, 'Turn it round', code(249))
p.button('bS', 418, 396, 160, 50, 'Start', code(248))
p.ok(250)
pages[87] = p.finish('\nvis bT,0')

# ---- 88 What changed?
p = Page(88, 'RFChangesView', 'What changed?', 'CHANGES.TXT', 'What changed? help')
p.text('hd', 49, 72, 702, 34, txt='Comparing with the backup ...')
for k in range(6):
    y = 112 + 46 * k
    p.text('c%d' % k, 49, y, 548, 40)
    p.button('p%d' % k, 605, y, 146, 40, 'Put back', code(251, k + 1), font=2)
p.button('bP', 49, 396, 80, 50, '<', code(254))
p.button('bN', 139, 396, 80, 50, '>', code(255))
p.button('bA', 418, 396, 160, 50, 'Read again', code(252), font=2)
p.ok(253)
pages[88] = p.finish('\nvis bP,0\nvis bN,0' + ''.join('\nvis p%d,0' % k for k in range(6)))

# ---- 89 the New helicopter guide: eight steps a half, the next step's words and its button
p = Page(89, 'RFGuideView', 'New helicopter guide', 'GUIDE.TXT', 'New helicopter guide help')
for k in range(8):
    y = 76 + 39 * k
    p.marker('k%d' % k, 49, y + 2, 40, 31)
    p.button('g%d' % k, 95, y, 300, 35, '', code(256, k + 1), font=2)
p.text('nx', 412, 76, 339, 40, font=6, txt='Next: 1. Direction check')
hn = p.text('hn', 412, 122, 339, 150, wrap=1, maxl=100); hn['a']['ycen'] = 0   # (the words from the top, under 'Next:')
p.button('bG', 412, 280, 339, 56, 'Go to step 16 ...', code(257))
p.button('bPg', 49, 396, 200, 50, 'Steps 9 - 16 >', code(258), font=2)
p.button('bR', 259, 396, 150, 50, 'Start again', code(259), font=2)
p.ok(260)
pages[89] = p.finish()

# the Teensy's longest words, measured as the screen draws them (RF_Guide.h / RF_Check.h / RF_Direction.h)
for s in ('Next: 7. Switches & knobs', 'Next: 8. Governor (global)', 'Next: 15. Check my setup', 'Every step done'):
    fits(s, 6, 339, 'guide nx')
for s in ('5. Switches & knobs', '8. Governor (global)', '15. Check my setup', '16. Back up'):
    fits(s, 2, 300, 'guide step')
for s in ('< Steps 1 - 8', 'Steps 9 - 16 >'): fits(s, 2, 200, 'guide page')
for s in ('Calibrate ...', 'Basics ...', 'Battery ...', 'Black box ...', 'Switches ...', 'Filters ...', 'Restart', 'Direction ...', 'Settings ...', 'Rescue ...'):
    fits(s, 2, 154, 'check fix')
for s in ('Stand the model level, then press Start.', '3 of 3: Turn the nose to the RIGHT about 30\xb0', 'Now stand it level again.',
          'Done: every move seen the right way.', 'Changing the mounting ...'):
    fits(s, 6, 702, 'direction do')
for s in ('Nose 89\xb0 down   Right side 179\xb0 down   Heading 359\xb0',):
    fits(s, 2, 702, 'direction live')
for s in ('1. Tilt the nose DOWN: it saw the nose go UP', '2. Tilt the RIGHT side down: it saw the LEFT side go down',
          '3. Turn the nose to the RIGHT: it saw the nose turn LEFT'):
    fits(s, 2, 678, 'direction step')

for pid, pg in pages.items():
    save(pid, pg)

# ---- the Rotorflight menu: "Guide & checks ..." over Command line's place, 16 MB only
m = load(8)
M = {c['n']: c for c in m['comps']}
if 'Tools' not in M:
    cli = M['Cli']
    nb = copy.deepcopy(cli); nb.update(n='Tools', i=max(c['i'] for c in m['comps']) + 1, txt='Guide & checks ...', ev={'r': code(236)})
    fits(nb['txt'], 6, nb['w'], 'menu Tools')
    m['comps'].insert(m['comps'].index(cli) + 1, nb)
    pre = m['ev']['preinitialize']
    assert 'vis bBeep,0' in pre, pre
    pre = pre.replace('  vis bBeep,0\n}', '  vis bBeep,0\n  vis Tools,0\n}') + '\nif(ldrcmb>=16)\n{\n  vis Cli,0\n}'
    m['ev']['preinitialize'] = pre
    save(8, m)

# ---- index.json: the five pages; page 8 one part more (the part count "n" is kept by hand)
ix = json.load(open(INDEX))
have = {p['id'] for p in ix['pages']}
if 85 not in have:
    for pid in sorted(pages):
        ix['pages'].append({'id': pid, 'name': pages[pid]['name'], 'n': len(pages[pid]['comps'])})
    for q in ix['pages']:
        if q['id'] == 8: q['n'] += 1
    json.dump(ix, open(INDEX, 'w'), indent=1)
print('pages', ', '.join('%d %s (%d parts)' % (k, v['name'], len(v['comps'])) for k, v in sorted(pages.items())), '; menu button; index', len(ix['pages']))
