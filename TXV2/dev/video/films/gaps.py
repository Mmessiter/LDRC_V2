#!/usr/bin/env python3
"""Film GAPS: the Reconnection times page, a tour, then how to read it: what is normal, one long gap, and many. The facts are
GAPS.TXT's; the example pages are made as the Teensy makes them (TXV1B Telemetry.h PopulateGapsView: the count, its bar -
n x 6 up to 10, then 60 + ((n - 10) x 40 + 20) / 40, at most 100 - and the per cent, cut to a whole number, "< 1%" under
one). OK goes back to the Telemetry page (the page's own "DataView"). Made with dev/video/filmkit.py.
18 Oct 2026, Malcolm: "describe how to use for solving real-world flying issues." """
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
from illus import Art
f = Film('GAPS', 'Reconnection times', 'A quick way to judge the link')
art = Art(f)
model_route(f, 'Telemetry')
f.shot('d', prefix('30.txt', '30_open'))
base = prefix('38.txt', '38_open')
def page(counts, longest, average, shortest):
    """the page with these eleven counts, left to right (under 4 ms ... over 500 ms), as PopulateGapsView sends them"""
    bars, pcts, tot = ['j0', 'j10', 'j11', 'j6', 'j5', 'j4', 'j3', 'j9', 'j2', 'j8', 'j7'], ['t13', 't15'] + ['t%d' % i for i in range(17, 26)], sum(counts)
    s = base
    for i, n in enumerate(counts):
        bar = 0 if n == 0 else n * 6 if n <= 10 else min(100, 60 + ((n - 10) * 40 + 20) // 40)
        pc = ' ' if n == 0 else ('< 1%' if n * 100 // tot == 0 else '%d%%' % (n * 100 // tot))
        s += 'n%d.val=%d\nvis n%d,%d\n%s.val=%d\n%s.txt="%s"\n' % (i, n, i, 1 if n else 0, bars[i], bar, pcts[i], pc)
    return s + 'n13.val=%d\nn12.val=%d\nn11.val=%d\n' % (longest, average, shortest)
NORMAL = [812, 301, 40, 22, 9, 6, 3, 1, 0, 0, 0]                    # (scenario 38's own: all green, longest 86 ms)
f.shot('p', page(NORMAL, 86, 5, 2))
f.shot('one', page(NORMAL[:9] + [1, 0], 318, 5, 2))                 # (the same flight with one red gap)
f.shot('many', page([520, 260, 60, 40, 30, 28, 22, 18, 45, 20, 6], 742, 24, 2))   # (an aerial in a poor place)
f.line('title', 'Reconnection times. Each time the radio link dropped, how quickly it came back.')
f.line('d', 'This is the Telemetry page. Press Gaps.')
f.line('page', "This is the Reconnection times page. Like the Telemetry page, it's for after landing, not while flying.")
f.line('column', 'Each column is a range of times, in milliseconds, written underneath. This first one means under four.')
f.line('count', 'The number below a column: how many reconnections took that long.')
f.line('percent', 'And the per cent above it: its share of them all.')
f.line('colours', 'Green columns, under a hundred milliseconds, are normal. Amber, from a hundred, and red, from two hundred and fifty, are long gaps.')
f.line('times', 'Along the bottom: the shortest, the average, and the longest time.')
f.line('ok', 'OK goes back to the Telemetry page.')
f.line('glitch', "Each gap is a moment when nothing gets through. Lots of models hop between frequencies at once, so brief collisions can't be avoided. The system reconnects as fast as it can.")
f.line('normal', "So what's normal? Mostly green, like this. With this system, most reconnections take under eight milliseconds. You'd never notice them.")
f.line('one', "See this single red gap? One long gap on its own is usually nothing to worry about. You only notice gaps above about a third of a second.")
f.line('many', 'But lots of amber and red, like this? Move the aerials, and check those on the receiver and the transmitter for damage.')
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Telemetry', 'd')
f.say('d', 'Press Gaps.', after=0.3); f.tap(*at('DataView', 'b13'), 'p')
f.say('page', 'Reconnection times.')
f.point(*at('GapsView', 't1'), 'column', 'A range of times.')
f.point(*at('GapsView', 'n0'), 'count', 'How many.')
f.point(*at('GapsView', 't13'), 'percent', 'Its share.')
f.point(*at('GapsView', 'j0'), 'colours', 'Green is normal.')
f.point(*at('GapsView', 't12'), 'times', 'Shortest, average, longest.')
f.point(*at('GapsView', 'b0'), 'ok', 'OK: back to Telemetry.')
f.show(art.glitch(0)); f.anim(art.glitch, 1.5); f.say('glitch', 'A gap in the link.')
f.show('p'); f.point(*at('GapsView', 't2'), 'normal', 'Tip: mostly green is normal.')
f.show('one'); f.point(*at('GapsView', 'n9'), 'one', "Tip: one long gap? Don't worry.")
f.show('many'); f.point(*at('GapsView', 'n8'), 'many', 'Tip: lots of amber? Aerials.')
f.end(); f.finish()
