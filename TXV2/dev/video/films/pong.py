#!/usr/bin/env python3
"""Film PONG: a game for a day too wet to fly. The words are PONG.TXT's; Pong will not start with a model connected, so the
model is off. The court is the screen's own drawing (renderer line "@pong x,y,ly,ry": the ball, then the left and right
paddles' heights; the paddles at x 60 and 750, src/pong_draw.h), so a short rally is drawn in silence. Made with
dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the model or transmitter screen; real uses): it starts on Transmitter setup ('Raining'). In
practice, kept light: a wet day, or while a pack charges; two players, one stick each."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import tx_route, tx_route_play

f = Film('PONG', 'Pong', 'A game for a day too wet to fly')
tx_route(f, 'Raining')
play = prefix('45.txt', '45_play')                                  # (3 : 7; the ball at 600,140, the paddles at 300 and 180)
f.shot('p', play)
rally = []                                                           # the ball to the left paddle, which rises to meet it, then back
for i in range(1, 8):
    t = i / 7.0; rally.append((600 - 528 * t, 140 + 110 * t, 300 - 50 * t, 180 + 30 * t))
for i in range(1, 5):
    t = i / 4.0; rally.append((72 + 308 * t, 250 - 130 * t, 250, 210 - 60 * t))
for i, (x, y, ly, ry) in enumerate(rally): f.shot('r%d' % i, play + '@pong %d,%d,%d,%d\n' % (x, y, ly, ry))
LEFT, RIGHT = (60, 250), (750, 150)                                  # (the paddles where the rally leaves them)
f.line('title', 'Pong. A game for a day too wet to fly.')
f.line('page', "And here's Pong! It won't start while a model is connected, and the radio stays off while you play.")
f.line('paddle', 'Move each stick up and down, and the paddle on its side moves with it.')
f.line('score', 'First to ten points wins. Then a new game starts by itself.')
f.line('ok', 'Press OK to stop playing, and go back to the front page.')
f.line('tip', "It's just the thing for a wet day, or while a pack charges. Two players, one stick each. Or take yourself on: left hand against right!")
f.prepare()

f.begin(); f.say('title', after=1.2)
tx_route_play(f, 'Raining', 'p')
f.say('page', 'Pong!')
f.cap = None
for i in range(len(rally)): f.under('r%d' % i); f.hold(0.3)        # (a rally, in silence)
f.hold(0.4)
f.point(*LEFT, 'paddle', 'A stick moves its paddle.')
f.point(*at('PongView', 'n0'), 'score', 'First to ten wins.')
f.point(*at('PongView', 'b2'), 'ok', 'OK stops the game.')
f.point(*RIGHT, 'tip', 'Tip: two players, a stick each.')
f.end(); f.finish()
