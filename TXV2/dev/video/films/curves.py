#!/usr/bin/env python3
"""Film CURVES: a channel's curve, with 3, 5, 7 or 9 points (B118-B122), then three real uses. The route and the drawing
are the firmware's: Model setup > Channels > a channel's button > the curve page (DisplayCurve's commands: the box, the
reference lines at the centre, straight lines point to point, the dots, the chosen point's rings, CurveLayoutShow's boxes
and the Points radios); Points 9 places the new points on the curve as it is; a touch above a point moves it there
(MovePoint: half the pixels in degrees, 2 pixels a degree). The expo example is the scenario's own (21_expo, Expo 30: a
gentler middle). Made with dev/video/filmkit.py.
18 Oct 2026, Malcolm: start on Model setup; real uses (each bank its own curve; a governed throttle flat at full - with
Rotorflight's governor the transmitter's throttle should be full in every bank, the head speed set per bank in the flight
controller (Malcolm's Goblin 770, 3 Sep: a throttle parked at 50 % never let the governor engage); Copy to all banks; a
gentler middle with Exponential)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at, comp
from common import model_route, model_route_play

ALL = ['n1', 'n2', 'n3', 'n4', 'n5', 'k2', 'k3', 'k5', 'k6', 'm1', 'm2', 'm3', 'm4', 'm5', 'm6', 'm7', 'm8', 'm9']
BOXES = {3: ['n1', 'n3', 'n5'], 5: ['n1', 'n2', 'n3', 'n4', 'n5'], 7: ['n1', 'k2', 'k3', 'n3', 'k5', 'k6', 'n5'], 9: ['m%d' % k for k in range(1, 10)]}
PTS = ['lpt', 'pt3', 'lpt3', 'pt5', 'lpt5', 'pt7', 'lpt7', 'pt9', 'lpt9']
def us(d): return (d * 2000 + 90) // 180 + 500                       # (the Teensy's map: it rounds)
def curve_page(degs, cur, channel='Aileron', bank='Bank 1', out=1500, copy=0):
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
    c += ['ModelName.txt="RAW 420 MCM (3)"', 'Channel.txt="%s"' % channel, 'fmode.txt="%s"' % bank, 'callfm.val=%d' % copy, 'Input.val=1500', 'Output.val=%d' % out, 'line 216,38,216,392,65504']
    return 'Screen_Background=8\n@model 1\n' + '\n'.join(c) + '\n'

f = Film('CURVES', 'Curves of 3 to 9 points', 'Shaping how a channel moves')
model_route(f, 'Channels')
f.shot('v_chan', prefix('26.txt', '26_open'))
five = [30, 60, 90, 120, 150]; nine = [30, 45, 60, 75, 90, 105, 120, 135, 150]
f.shot('v_c5', curve_page(five, 1))
f.shot('v_c9', curve_page(nine, 1))
up = list(nine); up[2] = 90; f.shot('v_c9up', curve_page(up, 3))          # a touch at y 215 above point 3 (60 degrees, y 275): 60 + 60 / 2
for d in range(91, 94):                                                  # three presses of +: a degree each (the touch left the ring on point 3)
    up2 = list(up); up2[2] = d; f.shot('v_c9plus%d' % d, curve_page(up2, 3))
f.shot('v_c9next', curve_page(up2, 4))                                   # Next: the ring on to point 4 (PointSelect: one on)
flat9 = [up2[3]] * 9; f.shot('v_flat', curve_page(flat9, 4))              # B135 Flat: every point the ringed point's height (CurveSetStraight h, h)
fresh9 = [(180 * k + 4) // 8 for k in range(9)]; f.shot('v_reset', curve_page(fresh9, 4))   # B135 Reset: CurveSetStraight 0 .. 180 (its rounding), no expo
FLAT = 150   # a governed throttle: full (150 degrees = 2167 us, a new model's top end; Rotorflight on CRSF reads it as full) all the way across
f.shot('thr', curve_page([FLAT] * 5, 1, 'Throttle', 'Bank 1', us(FLAT)))
f.shot('thr_copy', curve_page([FLAT] * 5, 1, 'Throttle', 'Bank 1', us(FLAT), copy=1))   # Copy to all banks turned on
f.shot('expo', prefix('21.txt', '21_expo', [('fmode.txt="Bank 2"', 'fmode.txt="Bank 1"')]))   # Exponential, Expo 30: a gentler middle
f.line('title', 'Curves of three to nine points. Shape exactly how a channel moves.')
f.line('chan', 'This is the Channels page. Press the channel you want to shape: here, Aileron.')
f.line('curve', "This is Aileron's curve page. Across is the stick, from one end to the other. Up is where the servo goes. Each dot's a point you can move.")
f.line('points', 'First, choose how many points: three, five, seven or nine. Press nine.')
f.line('nine', "Now there are nine, all on the same line, so nothing's moved yet.")
f.line('touch', 'To move a point, touch the graph just above or below it. The point jumps to your finger.')
f.line('small', 'For small steps, press minus or plus. The point with the ring moves a little each time.')
f.line('next', 'Next moves the ring along to the next point.')
f.line('flat', "Flat gives every point the height of the one with the ring: a level line, in one press.")
f.line('reset', "Reset starts again: a straight line from corner to corner, and no expo.")
f.line('ok', 'And OK saves it.')
f.line('banks', "Now, some real uses. Here's the throttle's curve page. Each bank has its own curve: the bank's name is just under the channel's. Move the bank switch to shape another bank's.")
f.line('gov', "Here's one worth knowing. With Rotorflight's governor, the throttle curve is usually a flat line at full throttle, like this. Rotorflight's Governor page sets each bank's head speed.")
f.line('copy', "A curve like this one belongs in every bank. So turn on Copy to all banks, then press OK.")
f.line('expo', "Flying an aeroplane? For a gentler feel round the centre, choose Exponential with a little expo, as on this elevator. Small stick moves do less, but the ends still reach full travel.")
f.line('rfexpo', "On a Rotorflight helicopter, though, that's usually better done on Rotorflight's Rates page.")
f.prepare()

f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Channels', 'v_chan')
f.say('chan', 'Press Aileron.', after=0.3); f.tap(*at('SticksView', 'Sch1'), 'v_c5')
f.say('curve', 'Across: the stick. Up: the servo.')
f.say('points', 'Press 9.', after=0.3); f.tap(*at('GraphView', 'pt9')); f.under('v_c9'); f.hold(0.6)
f.say('nine', 'Nine points, nothing moved.')
px3 = 35 + (360 * 2) // 8; py90 = 395 - 2 * 90                       # (point 3 of 9 across; 90 degrees up: DisplayCurve's own sums)
f.point(px3, py90, 'touch', 'Touch just above a point.', after=0.3); f.tap(px3, py90); f.under('v_c9up'); f.hold(0.8)
f.point(*at('GraphView', 'b5'), 'small', "'-' or '+': small steps.", after=0.3)
f.tap(*at('GraphView', 'b5')); f.under('v_c9plus91'); f.hold(0.3)
for d in range(92, 94): f.press(0.3); f.lift(0.2); f.under('v_c9plus%d' % d); f.hold(0.3)
f.hold(0.6)
f.point(*at('GraphView', 'b1'), 'next', "'Next': the next point.", after=0.3)
f.tap(*at('GraphView', 'b1')); f.under('v_c9next'); f.hold(0.8)
f.point(*at('GraphView', 'flat'), 'flat', "'Flat': a level line.", after=0.3)
f.tap(*at('GraphView', 'flat')); f.under('v_flat'); f.hold(0.8)
f.point(*at('GraphView', 'restart'), 'reset', "'Reset': straight, no expo.", after=0.3)
f.tap(*at('GraphView', 'restart')); f.under('v_reset'); f.hold(0.8)
f.point(*at('GraphView', 'b0'), 'ok', 'OK saves it.')
f.show('thr'); f.point(comp('GraphView', 'fmode')[0] + 28, at('GraphView', 'fmode')[1], 'banks', 'Tip: each bank, its own curve.')
f.point(215, 395 - 2 * FLAT, 'gov', 'Tip: governor? Flat, at full.')
f.point(*at('GraphView', 'callfm'), 'copy', 'Tip: one curve, every bank.')
f.tap(*at('GraphView', 'callfm')); f.under('thr_copy'); f.hold(1.0)
f.show('expo'); f.point(*at('GraphView', 'Expo'), 'expo', 'Tip: a gentler middle.')
f.cap = None; f.say('rfexpo', 'Rotorflight: its Rates page.')
f.end()
f.finish()
