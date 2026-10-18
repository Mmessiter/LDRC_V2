#!/usr/bin/env python3
"""Film LOG: the transmitter's log, a tour, and how to use it. The facts are LOG.TXT's (gaps up to about 100 ms are not
noticed by most pilots, longer ones might point to a problem; 'Keep log files' is on Transmitter setup, System, Next twice;
SD cards last longer when rarely written to). The log is scenario 44_log: its fifth line is "10:21:07 Gap: 142 ms".
Made with dev/video/filmkit.py.
18 Oct 2026: starts on Model setup, no closing line, and an "In practice" part (Malcolm: "look beyond the simple
functions' description and also describe how to use for solving real-world flying issues")."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, prefix, at, comp
from common import model_route, model_route_play
from illus import Art
f = Film('LOG', 'The log', 'What happened each day the transmitter was used')
model_route(f, 'Log')
f.shot('p', prefix('44.txt', '44_log'))
ENDS = {0: 380, 4: 225}                                            # (where those lines' words end, measured on the rendered page)
def line_end(i):
    """just after the end of the log's line i (from 0), so its words stay in sight: the lines are 24 pixels apart, the first
    centred 20 below the box's top"""
    x, y, w, h = comp('LogView', 'LogText')
    return ENDS[i] + 28, y + 20 + 24 * i
f.line('title', "The log. What happened, each day you used the transmitter.")
f.line('page', "This is today's log, named at the top.")
f.line('what', 'It records connections, disconnections and gaps in the radio link, the model found, bank and rate changes, the motor and safety switches, and the batteries. Each event has its time.')
f.line('scroll', 'Drag the text up or down to scroll. Top and Bottom jump to the start and the end.')
f.line('files', 'Files lists all the log files, to view or delete them. Switch the model off first.')
f.line('ok', 'OK goes to the Telemetry page.')
f.line('twitch', "Here's a handy one. Felt a twitch in flight? It may have been a short gap in the radio link, and the log will tell you.")
f.line('find', "Look for a gap at about that time. Here's one: a hundred and forty two milliseconds, at twenty one minutes past ten.")
f.line('gaps', "Gaps up to about a hundred milliseconds usually go unnoticed. Longer ones might point to a problem, so check the receiver's aerials.")
f.line('card', "S D cards last longer when they're rarely written to. So switch logging off when you don't need it: Transmitter setup, System, then Next twice.")
f.line('copy', "And copy the card's files to your computer now and then.")
f.prepare()
f.begin(); f.say('title', after=1.2)
model_route_play(f, 'Log', 'p')
f.say('page', "Today's log.")
f.point(*line_end(0), 'what', 'What it records, and when.')
f.point(*at('LogView', 'b1'), 'scroll', 'Drag to scroll; Top, Bottom.')
f.point(*at('LogView', 'b0'), 'files', 'Files.')
f.point(*at('LogView', 'b10'), 'ok', 'OK: Telemetry.')
art = Art(f); f.show(art.glitch(0)); f.anim(art.glitch, 1.4); f.say('twitch', 'Tip: a twitch? Maybe a gap.')   # (ends inside the gap: "nothing arrives")
f.show('p'); f.point(*line_end(4), 'find', 'Tip: look for a gap.')
f.cap = None; f.say('gaps', 'Tip: long gaps? Check the aerials.')
f.cap = None; f.say('card', 'Tip: logging off when not needed.')
f.cap = None; f.say('copy', 'Tip: keep a copy of the card.')
f.end(); f.finish()
