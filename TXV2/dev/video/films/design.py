#!/usr/bin/env python3
"""Film DESIGN: the design page of the defined front screens (Transmitter setup > Appearance > Defined front screens) - the
six tabs, a box's chooser, a round dial and its red zone, a box's theme, the box sizes, Stays lit, Help, OK; then the screen
in use from the front page. The facts are DESIGN.TXT's; the page is the screen's own (ESP32-board2 lib/LdrcFlight), drawn by
the renderer's "@flightsetup CONFIG [@box N] [@boxcolour T] [@boxzone] [@sizes]", so its places come from films/drawn.py.
Every change is kept as it is made, so the film's settings build up: box 3 the current, as a dial, red from 50 A, theme 5;
then nine boxes. 22 Oct 2026, Malcolm: "... the defined front screens screen ... need help buttons, help text and animations".
Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import tx_route, tx_route_play, FRONT_CONNECTED
from drawn import APPEAR, DESIGN, CHOOSER, COLOUR, ZONE, SIZES_OK, ITEM, design_tab, design_box6, chooser_item, zone_step, colour_swatch, sizes_layout

C1 = 'f2 w1 grid6 s1 timer,batts,rpm,link,esc,mah'            # six boxes, as the page opens
C2 = 'f2 w1 grid6 s1 timer,batts,amps,link,esc,mah'           # box 3: the current
C3 = C2 + ' d:,,1'                                            # ... as a dial
C3Z = C3 + ' z:,,50'                                          # ... red from 50 A
C4 = C3Z + ' b:,,5'                                           # ... in theme 5
C9 = 'f2 w1 grid9 s1 timer,batts,amps,link,esc,mah,rpm,clock,bank d:,,1 z:,,50 b:,,5'   # nine boxes
C9S = C9.replace(' s1 ', ' s0 ')                              # Stays lit: no
f = Film('DESIGN', 'Defined front screens', 'Designing your own front screen')
tx_route(f, 'Appearance')
base = prefix('33.txt', '33_open')
f.shot('app', base + '@appearance\n')
def setup(key, cfg, more=''): f.shot(key, FRONT_CONNECTED + '@flightsetup %s%s\n' % (cfg, more))
setup('design', C1); setup('chooser', C1, ' @box 3'); setup('chosen', C2); setup('chooser2', C2, ' @box 3'); setup('chooser3', C3, ' @box 3')
setup('design3', C3); setup('zonepage', C3, ' @box 3 @boxzone'); setup('zone50', C3Z, ' @box 3 @boxzone'); setup('chooser4', C3Z, ' @box 3')
setup('themepage', C3Z, ' @box 3 @boxcolour 0'); setup('theme5', C3Z, ' @box 3 @boxcolour 5'); setup('chooser5', C4, ' @box 3'); setup('design4', C4)
setup('sizes', C4, ' @sizes'); setup('sizes9', C9, ' @sizes'); setup('nine', C9); setup('stay', C9S)
f.shot('front', FRONT_CONNECTED)
f.shot('inflight', FRONT_CONNECTED + '@flight %s\n' % C9S)
f.line('title', "Defined front screens. Your own front screen: big, clear numbers while you fly. Here's the page that designs it.")
f.line('app', 'This is the Appearance page. Press Defined front screens.')
f.line('page', "This is the design page. It shows your front screen as it is now, live, with the model's own numbers.")
f.line('tabs', "The tabs, top right, are your six screens: one for the simulator, say, one for a helicopter, one for a glider. The yellow tab is the one in use. Touch another, and it's in use at once.")
f.line('box', "Touch a box to choose what it shows. Let's change box three, the head speed.")
f.line('chooser', "The chooser: seventeen things, or Nothing. A thing another box already shows is darker, with that box's number. Press Current.")
f.line('chosen', "Box three shows the current now. Changes are kept as you make them: there's nothing to save.")
f.line('dial', 'Any number can be a round dial. Touch the box again, then Round dial.')
f.line('dialon', 'A needle over a scale, and no digits. The scale grows to hold the biggest value seen.')
f.line('zone', 'Red zone marks where the red starts, for the head speed, the current, the capacity used and the frame rate. Batteries, the link and the E S C temperature have their zones built in. Press it.')
f.line('zonepage', 'Step the number with the four buttons; None takes the zone away. Plus twenty-five, then OK.')
f.line('theme', 'Theme gives the box a theme of its own, any of the twelve. Press it.')
f.line('themepage', "Touch a theme. Same as screens gives the box the screens' theme again. Then OK.")
f.line('back', 'And OK takes you back to the page.')
f.line('sizes', 'Box sizes offers twelve layouts, from one big box to nine small ones. Press it.')
f.line('sizespage', "The numbers grow with their boxes. Box one, top left, is always one of the biggest: put what matters most there. Let's take nine boxes.")
f.line('nine', 'Nine boxes. Boxes seven to nine show what you last gave them.')
f.line('stay', 'Stays lit stops the screen going dark while your screen shows and a model is connected.')
f.line('help', "Help opens this page's help, and its film.")
f.line('ok', 'OK closes the page. Then, on the front page, Defined screens brings your screen, and Original screen brings the original back.')
f.line('inflight', "And here it is, in flight. Six of these, a touch apart. Design them on the ground, with the safety on: while the safety's off, the design page closes.")
f.prepare()

f.begin(); f.say('title', after=1.2)
tx_route_play(f, 'Appearance', 'app'); f.say('app', 'Press Defined front screens.', after=0.3); f.tap(*APPEAR['Defined front screens'], 'design')
f.say('page', 'The design page: your screen, live.')
f.point(*design_tab(0), 'tabs', 'Six screens: the tabs.')
f.say('box', 'Touch box three.', after=0.3); f.tap(*design_box6(2), 'chooser')
f.say('chooser', 'Press Current.', after=0.3); f.tap(*chooser_item(ITEM['Current']), 'chosen')
f.say('chosen', 'Kept as you go.')
f.say('dial', 'Box three, then Round dial.', after=0.3); f.tap(*design_box6(2), 'chooser2'); f.tap(*CHOOSER['Round dial']); f.under('chooser3'); f.hold(0.6); f.tap(*CHOOSER['OK'], 'design3')
f.say('dialon', 'A dial: no digits.')
f.tap(*design_box6(2), 'chooser3'); f.say('zone', 'Press Red zone.', after=0.3); f.tap(*CHOOSER['Red zone'], 'zonepage')
f.say('zonepage', 'Plus 25, then OK.', after=0.3); f.tap(*zone_step(3)); f.under('zone50'); f.hold(0.6); f.tap(*ZONE['OK'], 'chooser4')
f.say('theme', 'Press Theme.', after=0.3); f.tap(*CHOOSER['Theme'], 'themepage')
f.say('themepage', 'Touch a theme, then OK.', after=0.3); f.tap(*colour_swatch(5)); f.under('theme5'); f.hold(0.6); f.tap(*COLOUR['OK'], 'chooser5')
f.say('back', 'OK: back to the page.', after=0.3); f.tap(*CHOOSER['OK'], 'design4')
f.say('sizes', 'Press Box sizes.', after=0.3); f.tap(*DESIGN['Box sizes'], 'sizes')
f.say('sizespage', 'Nine boxes.', after=0.3); f.tap(*sizes_layout(4)); f.under('sizes9'); f.hold(0.6); f.tap(*SIZES_OK, 'nine')
f.say('nine', 'Nine boxes.')
f.tap(*DESIGN['Stays lit']); f.under('stay'); f.hold(0.6); f.say('stay', 'Stays lit: no screen saver.')
f.point(*DESIGN['Help'], 'help', 'Help, and the film.')
f.point(*DESIGN['OK'], 'ok', 'OK closes the page.')
f.show('front'); f.tap(*at('FrontView', 'ldrcDefined'), 'inflight'); f.say('inflight', 'Your screen, in flight.')
f.end(); f.finish()
