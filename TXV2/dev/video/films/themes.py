#!/usr/bin/env python3
"""Film THEMES: the Themes page (Transmitter setup > Appearance > Themes) - twelve themes to touch, OK and Cancel, what keeps
its own colours; then Edit themes: a theme, Panel colour or Text colour, the three bars, Defaults, OK; the themes by number;
Help. The facts are THEMES.TXT's; the pages are the screen's own (ESP32-board2 lib/LdrcTheme): their buttons' places come
from films/drawn.py, and the renderer's "@colours WORD ..." draws them with those touched first. The edit ends on Defaults,
so that the theme the film leaves the screens in is theme 7 as it came (the renderer's "@theme 7" afterwards is the stock
one). 22 Oct 2026, Malcolm: "... the themes screen ... need help buttons, help text and animations". Made with filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, REST
from common import tx_route, tx_route_play
from drawn import APPEAR, THEMES, EDIT, theme_tile, edit_bar

f = Film('THEMES', 'Themes', 'The colours of every page')
tx_route(f, 'Appearance')
base = prefix('33.txt', '33_open')
f.shot('app', base + '@appearance\n')
f.shot('themes', base + '@colours\n')
f.shot('pick7', base + '@colours 7\n')
f.shot('edit', base + '@colours 7 edit\n')
for h in (30, 120, 210): f.shot('edit_h%d' % h, base + '@colours 7 edit hsv:%d,-1,-1\n' % h)
f.shot('edit_def', base + '@colours 7 edit hsv:210,-1,-1 defaults\n')
f.shot('edit_ok', base + '@colours 7 edit hsv:210,-1,-1 defaults ok\n')
f.shot('after', base + '@theme 7\n')
f.line('title', 'Themes. The colours of every page: twelve to choose from, and any colour you like.')
f.line('app', 'This is the Appearance page. Press Themes.')
f.line('page', 'This is the Themes page. Twelve themes: each a panel colour with its own text colour. The yellow frame marks the theme in use.')
f.line('touch', 'Touch a theme, and the page wears it at once. Here, number seven.')
f.line('ok', "OK makes it the screens' theme. Cancel leaves things as they were.")
f.line('keep', 'Buttons, the white boxes you type into, and red and green words keep their own colours, whatever the theme.')
f.line('box', "A box on your own front screen can wear a theme of its own: Theme, in the box's chooser.")
f.line('edit', 'Edit themes changes either colour of any theme to any colour. Press it.')
f.line('editpage', 'This is the Edit themes page. Touch a theme on the left; the sample shows it as it will look.')
f.line('kind', "Panel colour, or Text colour: which of its two colours you're making. The panel first.")
f.line('bars', 'Then slide the three bars: Colour; Strength, from grey to vivid; and Light, from black to bright. Slide Colour.')
f.line('slid', 'The sample follows, and so will every page.')
f.line('defaults', 'Defaults puts all twelve back as they came. Press it.')
f.line('editok', 'OK takes you back to Themes, and OK there keeps the new colours. Cancel, on either page, forgets them.')
f.line('number', 'The themes go by number, one to twelve, not by name: a name might not match a colour you made.')
f.line('help', "Help opens this page's help, and its film.")
f.line('done', 'Press OK, and every page wears your theme.')
f.line('rule', "While the safety is off, or the motor is on, this page closes, and won't open. Choose on the ground.")
f.prepare()

f.begin(); f.say('title', after=1.2)
tx_route_play(f, 'Appearance', 'app'); f.say('app', 'Press Themes.', after=0.3); f.tap(*APPEAR['Themes'], 'themes')
f.say('page', 'The Themes page.')
f.tap(*theme_tile(6), 'pick7'); f.say('touch', 'Touch a theme: the page wears it.')
f.point(*THEMES['OK'], 'ok', 'OK keeps it; Cancel does not.')
f.show('pick7'); f.say('keep', 'Buttons and boxes keep their colours.')
f.say('box', 'A box of your own can wear its own theme.')
f.say('edit', 'Press Edit themes.', after=0.3); f.tap(*THEMES['Edit themes ...'], 'edit'); f.say('editpage', 'The Edit themes page.')
f.point(*EDIT['Panel colour'], 'kind', 'Panel colour, or Text colour.')
f.say('bars', 'Slide Colour.', after=0.3)
f.glide(*edit_bar(0, 30)); f.hold(REST); f.press(); f.under('edit_h30'); f.slide([('edit_h120', edit_bar(0, 120)[0]), ('edit_h210', edit_bar(0, 210)[0])], edit_bar(0, 0)[1]); f.lift()
f.say('slid', 'The sample follows.')
f.say('defaults', 'Press Defaults.', after=0.3); f.tap(*EDIT['Defaults']); f.under('edit_def'); f.hold(0.6)
f.say('editok', 'OK: back to Themes.', after=0.3); f.tap(*EDIT['OK'], 'edit_ok')
f.say('number', 'By number, not by name.')
f.point(*THEMES['Help'], 'help', 'Help, and the film.')
f.say('done', 'Press OK.', after=0.3); f.tap(*THEMES['OK'], 'after')
f.say('rule', 'Choose on the ground, safety on.')
f.end(); f.finish()
