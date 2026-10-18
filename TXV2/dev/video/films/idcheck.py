#!/usr/bin/env python3
"""Film IDCHECK: checking the stored IDs, a tour, then a duplicate found and cleared. The words are IDCHECK.TXT's; the way in
is Model setup > Model IDs > Check for duplicates; the duplicate is the scenario's own (46_dups: models 4 and 9 share one
ID), the list turned to show both. Made with dev/video/filmkit.py.
18 Oct 2026, Malcolm: start on Model setup; real uses (why a duplicate matters, and its cure)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at, comp
from common import model_route, model_route_play
f = Film('IDCHECK', 'Checking the model IDs', 'Every stored ID, and any stored twice')
model_route(f, 'Model IDs', spoken='Model I Ds')
f.shot('ids', prefix('3.txt', '3_open')); f.shot('p', prefix('46.txt', '46_open'))
f.shot('dups', prefix('46.txt', '46_dups') + 'MMems.val=6\n')            # (the list turned to show models 4 and 9 both)
f.shot('fixed', prefix('46.txt', '46_dups', [('(4)  Goblin 700 Comp 7CDFA1B2C3D4 (same as 9)', '(4)  Goblin 700 Comp 7CDFA1B2C3D4 (ID OK)'),
    ('(9)  Black Thunder 7CDFA1B2C3D4 (same as 4)', '(9)  Black Thunder'), ('n0.val=2', 'n0.val=0')]) + 'MMems.val=6\n')   # (model 9's ID deleted: its name only)
def row(to, now=6, bw=3, rh=37):
    """the centre of the list's row 'to' (0 = model 1), the middle band holding row 'now' (the wheel: border 3, rows of 37)"""
    x, y, w, h = comp('IDsView', 'MMems'); band = y + bw + (h - 2 * bw - rh) // 2
    return x + w // 2, band + (to - now) * rh + rh // 2
f.line('title', 'Checking the model I Ds. Every stored I D, and any stored twice.')
f.line('ids', 'This is the Model I Ds page. Press Check for duplicates.')
f.line('page', "This is Model I Ds: duplicates. It lists every model memory, with its number, its name, and its stored I D. I D OK means no other model has that I D.")
f.line('dups', 'Duplicates counts the models whose I D is stored with another model too. It should be nought.')
f.line('ok', 'OK goes to the Model I Ds page, to store or delete an I D.')
f.line('found', "Now, here's what a problem looks like. Model four says same as nine.")
f.line('found9', 'And model nine says same as four. They share one I D.')
f.line('found2', 'So Duplicates says two.')
f.line('why', 'That matters, because a duplicate can make A M S load the wrong model memory. It often comes from moving a receiver, or restoring a backup into a second memory.')
f.line('cure', "The cure is easy. Say the receiver's now in model four. Load model nine, the one that shouldn't have it. Then, on the Model I Ds page, press Delete stored I D.")
f.line('again', 'Check again. Model nine shows its name only, with no I D.')
f.line('again2', "And Duplicates is back to nought. All's well!")
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Model IDs', 'ids')
f.say('ids', 'Press Check for duplicates.', after=0.3); f.tap(*at('IDsStartView', 'b3'), 'p')
f.say('page', 'Every stored ID.')
f.point(*at('IDsView', 'n0'), 'dups', 'Duplicates: should be 0.')
f.point(*at('IDsView', 'b10'), 'ok', 'OK: Model IDs.')
f.show('dups'); f.point(*row(3), 'found', 'Tip: 4 says same as 9.')
f.point(*row(8), 'found9', 'Tip: and 9 says same as 4.')
f.point(*at('IDsView', 'n0'), 'found2', 'Tip: so Duplicates: 2.')
f.cap = None; f.say('why', 'Tip: it can load the wrong model.')
f.point(*at('IDsView', 'b10'), 'cure', 'Tip: delete the extra ID.')
f.show('fixed'); f.point(*row(8), 'again', 'Tip: model 9: no ID now.')
f.point(*at('IDsView', 'n0'), 'again2', 'Tip: Duplicates: 0 again.')
f.end(); f.finish()
