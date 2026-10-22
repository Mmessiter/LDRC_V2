#!/usr/bin/env python3
"""Film APPEAR: the Appearance page (Transmitter setup > Appearance) - its three doors (the background picture, the themes,
the defined front screens), Help, OK, and the rule that it closes while the safety is off. The facts are APPEAR.TXT's; the
page is the screen's own (ESP32-board2 lib/LdrcTheme), not one of the main board's, so its buttons' places come from
films/drawn.py, not a page JSON. 22 Oct 2026, Malcolm: "The appearance screen and the themes screen and the defined front
screens screen all need help buttons, help text and animations". Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix
from common import tx_route, tx_route_play
from drawn import APPEAR

f = Film('APPEAR', 'Appearance', 'How the screens look')
tx_route(f, 'Appearance')
f.shot('app', prefix('33.txt', '33_open') + '@appearance\n')
f.line('title', 'Appearance. How the screens look: the background picture, the colours, and your own front screens.')
f.line('page', 'This is the Appearance page. Three doors: the background picture, the themes, and your own front screens. Each has a page of its own.')
f.line('background', 'Background picture is the picture behind the pages. Minus and plus step through forty-three of them, and OK keeps the one showing.')
f.line('themes', 'Themes: twelve panel colours, each with its own text colour. Touch one, and every page wears it at once. The Themes page has a film of its own.')
f.line('front', 'Defined front screens: your own front screen, with big, clear numbers while you fly. You can design six of them. That page has a film of its own too.')
f.line('help', "Help, top right, opens this page's help. Films, on the help page, plays the animations.")
f.line('ok', 'OK goes back to Transmitter setup.')
f.line('rule', "One rule. While the safety is off, or the motor is on, these pages close, and won't open. Design on the ground, with the safety on.")
f.prepare()

f.begin(); f.say('title', after=1.2)
tx_route_play(f, 'Appearance', 'app'); f.say('page', 'The Appearance page.')
f.point(*APPEAR['Background picture'], 'background', 'The picture behind the pages.')
f.point(*APPEAR['Themes'], 'themes', 'Twelve themes: its own film.')
f.point(*APPEAR['Defined front screens'], 'front', 'Your own front screens: its own film.')
f.point(*APPEAR['Help'], 'help', 'Help, and the films.')
f.point(*APPEAR['OK'], 'ok', 'Back to Transmitter setup.')
f.show('app'); f.say('rule', 'Design on the ground, safety on.')
f.end(); f.finish()
