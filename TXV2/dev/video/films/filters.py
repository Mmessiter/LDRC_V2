#!/usr/bin/env python3
"""Film FILTERS: Rotorflight's filters - a tour, then real uses: the R P M filter is the main defence against vibration and
needs a head-speed signal (E S C telemetry: a port with that job, BASICS3.TXT); a model that shakes or servos that buzz:
check the R P M filter is on, and cure the vibration at its source too (blade tracking and balance). The facts are
FILTERS.TXT's. Made with dev/video/filmkit.py.
18 Oct 2026 (Malcolm: start at the setup pages, real uses, livelier words, no closing line): starts on the Rotorflight menu."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from filmkit import Film, at, comp
from common import rf_route, rf_route_play, rfs, SAVE_SHOWN
from illus import Art
f = Film('FILTERS', 'Filters', 'Cleaning vibration out of the gyro signal')
art = Art(f)
rf_route(f, 'Filters ...')
opn = rfs('64.txt', '64_loaded')                     # (lowpass 2nd order 100 Hz; R P M filter on, Medium, 20 Hz; dynamic on, 4 notches)
f.shot('p', opn); f.shot('e', opn + SAVE_SHOWN)
def shake(t): return art.wobble(t, title='It shakes')
def words(name, half):
    """a section's heading: its words are at the left of its box (half: half their width, measured on the drawn page)"""
    x, y, w, h = comp('FilterView', name); return x + 4 + half, y + h // 2
f.line('title', 'Filters. How Rotorflight cleans vibration out of the gyro signal.')
f.line('page', "This is the Filters page. It's the same in every bank.")
f.line('lowpass', 'The lowpass filter smooths everything above its cutoff. Lower is smoother, but adds delay. A hundred hertz is usual.')
f.line('enable', 'Each section has an Enable: green is on. Turn one off, and its rows hide.')
f.line('rpm', 'The R P M filter follows the head speed, and removes the rotor and motor vibrations, wherever they are.')
f.line('strength', 'Strength: Low, Medium or High. More removes more, but adds a little delay. Tap it to step through them.')
f.line('dynamic', 'The dynamic filter: notches that hunt down the strongest vibrations by themselves.')
f.line('next', "Next opens the expert mode: the extras you'll rarely need.")
f.line('save', "Save appears once something's changed. It writes both filter pages. Turning the R P M or dynamic filter on or off restarts the flight controller.")
f.line('ok', 'OK leaves. With a change not saved, it asks first.')
f.line('main', "Here's the one that matters most. On a helicopter, the R P M filter is your main defence against vibration.")
f.line('signal', "But it needs a head speed signal: E S C telemetry, or an R P M sensor. For E S C telemetry, give a port that job, on the Ports page in First time basics.")
f.line('shake', 'Model shakes in the hover, or servos buzz?')
f.line('check', "First, check the R P M filter's Enable is green.")
f.line('source', "Then cure the vibration at its source, too. Check that nothing's loose, and that the blades are balanced and tracking true. A filter hides vibration. It can't mend the cause.")
f.prepare()
f.begin(); f.say('title', after=1.2)
rf_route_play(f, 'Filters ...', 'p')
f.say('page', 'Filters.')
f.point(*words('h0', 76), 'lowpass', 'Lowpass filter.')
f.point(*at('FilterView', 'tn0'), 'enable', 'Enable: green is on.')
f.point(*words('h1', 54), 'rpm', 'RPM filter.')
f.point(*at('FilterView', 'tn4'), 'strength', 'Strength.')
f.point(*words('h2', 75), 'dynamic', 'Dynamic filter.')
f.point(*at('FilterView', 'b2'), 'next', 'Next >: expert mode.')
f.under('e'); f.hold(0.6); f.point(*at('FilterView', 'b3'), 'save', 'Save.')
f.point(*at('FilterView', 'b1'), 'ok', 'OK.')
f.show('p'); f.point(*words('h1', 54), 'main', 'Tip: the RPM filter matters most.')
f.cap = None; f.say('signal', 'Tip: it needs a head-speed signal.')
f.show(shake(0)); f.anim(shake, 2.5); f.say('shake', 'Tip: it shakes, or servos buzz?')
f.show('p'); f.point(*at('FilterView', 'tn3'), 'check', 'Tip: is the RPM filter on?')
f.show('p', look=0.4); f.say('source', 'Tip: track and balance the blades.')
f.end(); f.finish()
