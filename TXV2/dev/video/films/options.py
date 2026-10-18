#!/usr/bin/env python3
"""Film OPTIONS: the System pages' first page (General), and binding. The words are OPTIONS.TXT's (the System pages' help);
Bind turns into "Stop binding" (scenario 25_bind: Enable_Binding, Utilities.h). Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the model or transmitter screen; real uses): it starts on Transmitter setup. "Press OK on each
page you change ... Next and Back may lose changes" is said where Next is shown. In practice: AMS with each model's ID stored
(Model setup > Model IDs) loads the right model by itself (with AMS off the loaded memory stays, whichever model connects);
the transmitter battery warning set quite high, as the help says, to land with power to spare."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import tx_route, tx_route_play

f = Film('OPTIONS', 'System', 'General settings, and binding')
tx_route(f, 'System')
f.shot('o_sys', prefix('25.txt', '25_open'))
f.shot('o_bind', prefix('25.txt', '25_bind'))
f.line('title', "System. The transmitter's general settings, and how to bind a receiver.")
f.line('page', 'This is the first of three System pages: General.')
f.line('ams', 'Automatic model selection, or A M S. When a model connects, the transmitter loads the model memory that holds its I D.')
f.line('dark', 'Screen goes dark after: the screen turns off to save the battery. Touch it anywhere to wake it up.')
f.line('off', "Switch off when unused: this switches off a transmitter left on by mistake. But never while a model's connected.")
f.line('battery', "Transmitter battery low at: you're warned when the transmitter's battery falls this low.")
f.line('mode', 'Stick mode, one or two. Set this first, then calibrate the sticks and trims again.')
f.line('owner', "Owner's name: it's shown at the top left of the front page.")
f.line('bindhow', 'To bind a receiver, first get the receiver ready to bind. Then, with no model connected, press Bind.')
f.line('binding', 'It changes to Stop binding. The receiver binds and connects, and then binding stops by itself.')
f.line('next', "Next goes on to the clock, and the advanced settings. Changed something here? Press OK first, or Next may lose it.")
f.line('ok', 'OK saves this page, and goes back to Transmitter setup.')
f.line('ams2', "Here's why A M S is worth having. Store each model's I D once, on Model setup, Model I Ds. Then the right model loads by itself, whenever it connects.")
f.line('ams3', "With A M S off, the loaded memory stays, whichever model you switch on. So leave it on, and you won't fly with another model's settings by mistake.")
f.line('battery2', 'And set the battery warning quite high. Then it comes with plenty of power to spare, so you can land without hurrying.')
f.prepare()

f.begin(); f.say('title', after=1.2)
tx_route_play(f, 'System', 'o_sys')
f.say('page', 'System: General.')
f.point(*at('OptionsView', 'c0'), 'ams', 'Automatic model selection.')
f.point(*at('OptionsView', 'ST'), 'dark', 'Screen goes dark after.')
f.point(*at('OptionsView', 't2'), 'off', 'Switch off when unused.')
f.point(*at('OptionsView', 't10'), 'battery', 'Battery warning.')
f.point(*at('OptionsView', 't4'), 'mode', 'Stick mode.')
f.point(*at('OptionsView', 'TxName'), 'owner', "Owner's name.")
f.point(*at('OptionsView', 'b0'), 'bindhow', 'Binding: press Bind.', after=0.3); f.tap(*at('OptionsView', 'b0')); f.under('o_bind'); f.hold(0.8)
f.say('binding', 'Stop binding.')
f.point(*at('OptionsView', 'b13'), 'next', 'Changed something? OK first.')
f.point(*at('OptionsView', 'b10'), 'ok', 'OK saves this page.')
f.show('o_sys'); f.point(*at('OptionsView', 'c0'), 'ams2', 'Tip: the right model, always.')
f.cap = None; f.say('ams3', 'Never the wrong settings.')
f.point(*at('OptionsView', 'Bwn'), 'battery2', 'Tip: set it quite high.')
f.end(); f.finish()
