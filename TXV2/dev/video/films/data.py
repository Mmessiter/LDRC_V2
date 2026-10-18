#!/usr/bin/env python3
"""Film DATA: the Telemetry page, a tour, then how pilots use it after every flight. The facts are DATA.TXT's; OK goes back
to Model setup (TXV1B main.cpp "DataEnd"); Clear zeroes the lost packets and the gaps (main.cpp ZeroDataScreen).
Made with dev/video/filmkit.py.
18 Oct 2026, Malcolm: "let's look beyond the simple functions' description and also describe how to use for solving
real-world flying issues." """
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
from illus import Art, METAL, WHITE, YELLOW
f = Film('DATA', 'Telemetry', 'How well the radio link is working')
art = Art(f)
def aerials(t=0.0):
    """(illus.py's Art.aerials runs off the top of the transmitter's screen, its "90" under the title: drawn here smaller,
    with the same parts) a receiver, its two aerials ninety degrees apart, clear of carbon and metal"""
    im, d = art._canvas()
    art.poly(d, [(-80, 30), (80, 30), (80, 110), (-80, 110)], (52, 58, 72))
    art.text(d, 0, 70, 'RECEIVER', size=24)
    for sx in (-1, 1):
        art.line(d, [(sx * 60, 30), (sx * 60, -10), (sx * 160, -110)], METAL, 5)
        art.line(d, [(sx * 160, -110), (sx * 184, -134)], WHITE, 7)      # (the bare tips)
    art.arc_arrow(d, 0, -10, 70, -135, -45, fill=YELLOW, width=5)
    art.text(d, 0, -112, '90 degrees', size=28, fill=YELLOW)
    art.text(d, 0, 165, 'clear of carbon and metal', size=24, fill=(200, 210, 225), bold=False)
    art.title(d, 'Aerials at right angles')
    return art._done(im)
model_route(f, 'Telemetry')
opn = prefix('30.txt', '30_open')                                    # (16 minutes into a RAW 420 session: longest gap 24 ms)
f.shot('p', opn)
f.shot('bad', opn + 'lps.val=412\nLs.val=640\nAg.val=11\n')         # (a worrying flight: an aerial badly placed)
f.shot('clr', opn + 'lps.val=0\nLs.val=0\nAg.val=0\n')               # (Clear: the counts start again)
f.line('title', "Telemetry. Your radio link's health check, and what the model reports.")
f.line('page', "This is the Telemetry page. It's best read after a flight, before you switch off.")
f.line('rate', 'On the left, the radio link. Frame rate: how many packets arrive each second.')
f.line('lost', "Lost data packets: the ones that didn't arrive.")
f.line('gap', 'Longest comms gap: the longest wait, in milliseconds, before the link came back. This is the one to watch.')
f.line('model', 'On the right, what the model reports: head speed and E S C temperature from Rotorflight, and the battery volts per cell.')
f.line('clear', 'Clear sets the counts back to nought.')
f.line('gaps', 'Gaps shows how long each reconnection took, and G P S opens the G P S page.')
f.line('ok', 'OK goes back to Model setup.')
f.line('habit', "Here's a habit worth forming. After every flight, glance at the longest comms gap. Below about two hundred and fifty, all's well. It's normally well below a hundred.")
f.line('high', "Much higher, like this? Move the receiver's aerials, and check them for damage. Dipole aerials are recommended.")
f.line('aerials', 'As a rule, keep the aerials at right angles to each other, and clear of carbon and metal.')
f.line('try1', "And here's a neat trick for finding the best place for an aerial. Press Clear, fly one pack, and note the longest gap.")
f.line('try2', 'Then move the aerial, and fly another pack. Now you can compare the two, and keep the better place.')
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Telemetry', 'p')
f.say('page', 'Telemetry.')
f.point(*at('DataView', 't29'), 'rate', 'Frame rate.')
f.point(*at('DataView', 't1'), 'lost', 'Lost data packets.')
f.point(*at('DataView', 't10'), 'gap', 'Longest comms gap.')
f.point(*at('DataView', 't4'), 'model', 'What the model reports.')
f.point(*at('DataView', 'b0'), 'clear', 'Clear.')
f.point(*at('DataView', 'b13'), 'gaps', 'Gaps; GPS.')
f.point(*at('DataView', 'b10'), 'ok', 'OK: back to Model setup.')
f.point(*at('DataView', 't10'), 'habit', 'Tip: check it after every flight.')   # (the label: the finger must not hide the number)
f.show('bad'); f.point(*at('DataView', 't10'), 'high', 'Tip: much higher? Check aerials.')
f.show(aerials()); f.say('aerials', 'Tip: aerials at right angles.')
f.show('bad'); f.point(*at('DataView', 'b0'), 'try1', 'Tip: test aerial positions.', after=0.3)
f.tap(*at('DataView', 'b0')); f.under('clr'); f.hold(0.8)
f.cap = None; f.say('try2', 'Tip: compare, keep the better.')
f.end(); f.finish()
