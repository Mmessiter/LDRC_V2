#!/usr/bin/env python3
"""Film GLITCH ("Fix a problem", 18 Oct 2026): radio glitches - a twitch, or a moment without control: how to find the
cause after landing (Telemetry, Reconnection times, the log), and the cure (the receiver's aerials; Scan RF for a busy band).
Malcolm: "Let's include the likely cure for tail-wag and other common set up issues."
The facts: DATA.TXT (look after a flight, before you switch off; Longest comms gap below about 250 ms all should be well,
normally well below 100; much higher: move the receiver's aerials and check them for damage; Clear sets the counts back to
zero), GAPS.TXT (green under 100 ms normal; amber 100 to 249, red 250 or more; many above 100 or 250: move the aerials, and
check those on the receiver and the transmitter for damage; not while flying), LOG.TXT (gaps in the radio link, each event
with its time), TXSETUP.TXT (Scan RF: how busy each 2.4 GHz channel is; the link stops while it runs; never while the model
flies). The pages: scenario 30 (a worrying flight, as the DATA film shows it: lost 412, longest 640 ms), scenario 38 made as
the Teensy makes it (the GAPS film's page(): many amber and red), scenario 33 and 2. Every page is on Model setup or
Transmitter setup, so the film starts on Model setup. The pictures are illus.py's glitch and aerials.
Made with dev/video/filmkit.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from filmkit import Film, prefix, at
from common import model_route, model_route_play
from illus import Art

f = Film('GLITCH', 'Radio glitches', 'The likely cause, and the cure')
art = Art(f)
model_route(f, 'Telemetry')
f.shot('bad', prefix('30.txt', '30_open') + 'lps.val=412\nLs.val=640\nAg.val=11\n')   # (a worrying flight: an aerial badly placed)
base = prefix('38.txt', '38_open')
def page(counts, longest, average, shortest):
    """the Reconnection times page with these eleven counts, left to right (under 4 ms ... over 500 ms), as the Teensy's
    PopulateGapsView sends them (the GAPS film's own sums: the bar n x 6 up to 10, then 60 + ((n - 10) x 40 + 20) / 40)"""
    bars, pcts, tot = ['j0', 'j10', 'j11', 'j6', 'j5', 'j4', 'j3', 'j9', 'j2', 'j8', 'j7'], ['t13', 't15'] + ['t%d' % i for i in range(17, 26)], sum(counts)
    s = base
    for i, n in enumerate(counts):
        bar = 0 if n == 0 else n * 6 if n <= 10 else min(100, 60 + ((n - 10) * 40 + 20) // 40)
        pc = ' ' if n == 0 else ('< 1%' if n * 100 // tot == 0 else '%d%%' % (n * 100 // tot))
        s += 'n%d.val=%d\nvis n%d,%d\n%s.val=%d\n%s.txt="%s"\n' % (i, n, i, 1 if n else 0, bars[i], bar, pcts[i], pc)
    return s + 'n13.val=%d\nn12.val=%d\nn11.val=%d\n' % (longest, average, shortest)
f.shot('many', page([520, 260, 60, 40, 30, 28, 22, 18, 45, 20, 6], 742, 24, 2))   # (the GAPS film's "aerial in a poor place")
f.shot('tx', prefix('33.txt', '33_open'))
f.shot('scan', prefix('2.txt', '2_scan'))

f.line('title', "Radio glitches. Here's how to find the cause, and the cure.")
f.line('symptom', "A sudden twitch? Or a moment when the model doesn't answer the sticks?")
f.line('cause', "That's usually a short gap in the radio link. Check after landing, before you switch off.")
f.line('gap', "This is the Telemetry page. Longest comms gap: below about two hundred and fifty milliseconds, all's well. Normally it's well below a hundred.")
f.line('high', "Much higher, like this? Then it's time to look at the aerials.")
f.line('log', "The log, on Model setup, notes every gap with its time. Look for one at the moment of the twitch.")
f.line('many', "This is the Reconnection times page. Mostly green is normal. Lots of amber and red, like this? The aerials again.")
f.line('aerials', "The cure: the receiver's aerials. Move them apart, at right angles, away from carbon and metal. And check them, and the transmitter's, for damage.")
f.line('tx', "Glitches only at one field? This is Transmitter setup. Scan R F shows how busy the two point four gigahertz band is.")
f.line('scan', "The link stops while it scans, so never scan while the model flies.")
f.line('test', "Then press Clear on the Telemetry page, fly a pack, and compare the longest gap with before.")
f.prepare()

f.begin(); f.say('title', after=1.2)
f.show(art.glitch(0), look=0.3); f.anim(art.glitch, 3.0); f.say('symptom')
f.say('cause', 'Check after landing.')
model_route_play(f, 'Telemetry', 'bad')
f.point(*at('DataView', 't10'), 'gap', 'Longest comms gap: under 250.')   # (the label: the finger must not hide the number)
f.cap = None; f.say('high', 'Much higher? The aerials.')
f.cap = None; f.say('log', 'Tip: the log has the time.', after=0.3)
f.tap(*at('DataView', 'b13'), 'many')
f.point(*at('GapsView', 'n8'), 'many', 'Lots of amber and red? Aerials.')
f.show(art.aerials()); f.say('aerials', 'Apart, at right angles, undamaged.')
f.show('tx'); f.point(*at('TXSetupView', txt='Scan RF'), 'tx', 'Scan RF: how busy is the band?', after=0.3)
f.tap(*at('TXSetupView', txt='Scan RF'), 'scan'); f.say('scan', 'Never while the model flies.')
f.show(f.card('Then fly it', 'Clear, fly, compare')); f.say('test', 'Tip: Clear, fly, compare.')
f.end(); f.finish()
