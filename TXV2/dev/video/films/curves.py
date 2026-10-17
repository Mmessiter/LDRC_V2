#!/usr/bin/env python3
"""Film CURVES: a channel's curve, with 3, 5, 7 or 9 points (B118-B122). The route and the drawing are the firmware's: front
page > Model > Channels > a channel's button > the curve page (DisplayCurve's commands: the box, the reference lines at the
centre, straight lines point to point, the dots, the chosen point's rings, CurveLayoutShow's boxes and the Points radios);
Points 9 places the new points on the curve as it is; a touch above a point moves it there (MovePoint: half the pixels in
degrees, 2 pixels a degree). Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix

ALL = ['n1', 'n2', 'n3', 'n4', 'n5', 'k2', 'k3', 'k5', 'k6', 'm1', 'm2', 'm3', 'm4', 'm5', 'm6', 'm7', 'm8', 'm9']
BOXES = {3: ['n1', 'n3', 'n5'], 5: ['n1', 'n2', 'n3', 'n4', 'n5'], 7: ['n1', 'k2', 'k3', 'n3', 'k5', 'k6', 'n5'], 9: ['m%d' % k for k in range(1, 10)]}
PTS = ['lpt', 'pt3', 'lpt3', 'pt5', 'lpt5', 'pt7', 'lpt7', 'pt9', 'lpt9']
def us(d): return (d * 2000 + 90) // 180 + 500                       # (the Teensy's map: it rounds)
def curve_page(degs, cur):
    n = len(degs); xs = [35 + (360 * k) // (n - 1) for k in range(n)]; ys = [max(39, min(391, 395 - 2 * d)) for d in degs]
    c = ['page GraphView', 'fill 36,36,360,360,0', 'draw 35,35,395,395,65504', 'line 35,217,395,217,63488', 'line 215,35,215,395,63488']
    c += ['line %d,%d,%d,%d,65535' % (xs[k], ys[k], xs[k + 1], ys[k + 1]) for k in range(n - 1)]
    c += ['cirs %d,%d,4,65535' % (xs[k], ys[k]) for k in range(n)]
    x, y = xs[cur - 1], ys[cur - 1]
    c += ['cirs %d,%d,10,65535' % (x, y), 'cirs %d,%d,8,65504' % (x, y), 'cirs %d,%d,6,65504' % (x, y), 'cirs %d,%d,7,0' % (x, y)]
    c += ['vis %s,%d' % (b, 1 if b in BOXES[n] else 0) for b in ALL]
    c += ['%s.val=%d' % (b, us(degs[k])) for k, b in enumerate(BOXES[n])]
    c += ['pt%d.val=%d' % (k, 1 if k == n else 0) for k in (3, 5, 7, 9)]
    c += ['Lines.val=1', 'Smooth.val=0', 'Exp.val=0', 'vis t3,0', 'vis b13,0', 'vis b12,0', 'vis Expo,0', 'vis Ex1,0'] + ['vis %s,1' % p for p in PTS]
    c += ['ModelName.txt="RAW 420 MCM (3)"', 'Channel.txt="Aileron"', 'fmode.txt="Bank 1"', 'callfm.val=0', 'Input.val=1500', 'Output.val=1500', 'line 216,38,216,392,65504']
    return 'Screen_Background=8\n@model 1\n' + '\n'.join(c) + '\n'

f = Film('CURVES', 'Curves of 3 to 9 points', 'Shaping how a channel moves')
f.shot('v_front', prefix('13.txt', '13_conn', [
    ('bt0.txt="Motor is ON"\nbt0.bco=2016\nbt0.bco2=2016\nbt0.pco=0\nbt0.pco2=0', 'bt0.txt="Motor is OFF"\nbt0.bco=63488\nbt0.bco2=63488\nbt0.pco=65535\nbt0.pco2=65535'),
    ('RPM: 2150', 'RPM: 0'), ('Amps: 12.4', 'Amps: 0.3'), ('mAh: 345', 'mAh: 0'), ('ESC: 52.3', 'ESC: 21.5')]))
f.shot('v_model', prefix('4.txt', '4_open'))
f.shot('v_chan', prefix('26.txt', '26_open'))
five = [30, 60, 90, 120, 150]; nine = [30, 45, 60, 75, 90, 105, 120, 135, 150]
f.shot('v_c5', curve_page(five, 1))
f.shot('v_c9', curve_page(nine, 1))
up = list(nine); up[2] = 90; f.shot('v_c9up', curve_page(up, 3))          # a touch at y 215 above point 3 (60 degrees, y 275): 60 + 60 / 2
for d in range(91, 96):                                                  # five presses of +: a degree each (the touch left the ring on point 3)
    up2 = list(up); up2[2] = d; f.shot('v_c9plus%d' % d, curve_page(up2, 3))
f.shot('v_c9next', curve_page(up2, 4))                                   # Next point: the ring on to point 4 (PointSelect: one on)
f.line('title', 'Curves of 3 to 9 points. Shaping how a channel moves.')
f.line('front', "This is the transmitter's front page. Press Model.")
f.line('model', 'This is the Model setup page. Press Channels.')
f.line('chan', 'This is the Channels page: every channel, with its bar and its microseconds. Press the channel to shape. Here, Aileron.')
f.line('curve', 'This is the curve page. Across is the stick, from one end to the other. Up is where the servo goes. Each dot is a point you can move.')
f.line('points', 'Choose how many points: three, five, seven or nine. Press nine.')
f.line('nine', 'Now there are nine points, all on the same line, so nothing has moved yet.')
f.line('touch', 'To move a point, touch the graph just above or below it. The point moves to your finger.')
f.line('small', 'For small steps, press minus or plus. The point with the ring moves a little each time.')
f.line('next', 'Next point moves the ring on to the next point.')
f.line('remember', 'Every point keeps its height. Change the number of points and back, and your points return as you left them.')
f.line('ok', 'Press OK to save.')
f.line('end', "That's all there is to it.")
f.prepare()

f.begin(); f.say('title', after=1.6)
f.show('v_front'); f.say('front', 'Press Model.', after=0.3); f.tap(652, 425, 'v_model')
f.say('model', 'Press Channels.', after=0.3); f.tap(170, 165, 'v_chan')
f.say('chan', 'Press Aileron.', after=0.3); f.tap(111, 84, 'v_c5')
f.say('curve', 'Across: the stick. Up: the servo.')
f.say('points', 'Press 9.', after=0.3); f.tap(738, 356); f.under('v_c9'); f.hold(0.6)
f.say('nine', 'Nine points, nothing moved.')
f.say('touch', 'Touch just above a point.', after=0.3); f.tap(125, 215); f.under('v_c9up'); f.hold(0.8)
f.say('small', "'-' or '+': small steps.", after=0.3)
f.tap(343, 442); f.under('v_c9plus91'); f.hold(0.3)
for d in range(92, 96): f.press(0.3); f.lift(0.2); f.under('v_c9plus%d' % d); f.hold(0.3)
f.hold(0.6)
f.say('next', "'Next point': the next one.", after=0.3)
f.tap(105, 442); f.under('v_c9next'); f.hold(0.8)
f.say('remember', 'Every point keeps its height.')
f.say('ok', 'Press OK to save.', after=0.3); f.tap(695, 442)
f.end('end')
f.finish()
