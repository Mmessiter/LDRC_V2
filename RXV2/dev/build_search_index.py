#!/usr/bin/env python3
"""Build data/search.js for the "Find a setting" page (Malcolm 2026-09-07:
"even I sometimes don't remember where to find a particular setting").

Walks every page in data/, collecting every labelled setting (label +
data-help + the input's id + the card heading), every page title and every
menu tile, plus a hand-kept list of settings the pages build in JavaScript.
Run it whenever a page changes:  python3 dev/build_search_index.py
The apps and the receiver both serve the resulting data/search.js."""
import glob, html, json, os, re
from html.parser import HTMLParser

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
SKIP = {'search.html', 'events.html', 'firmware.html', 'fly.html', 'flight.html', 'protocol.html', 'retest.html', 'rollback.html'}

def clean(t):
    t = html.unescape(re.sub(r'<[^>]+>', '', t or ''))
    t = re.sub(r'[\U0001F000-\U0001FFFF☀-➿️‍]+', '', t)   # emoji
    return re.sub(r'\s+', ' ', t).strip(' :—-')

def hint_of(h, n=100):
    h = clean(h)
    if len(h) <= n: return h
    m = re.match(r'(.{20,%d}?[.;!?])\s+(?=[A-Z0-9(])' % n, h)      # a real sentence end, not "e.g."
    if m and not m.group(1).lower().endswith(('e.g.', 'i.e.', 'etc.')): return m.group(1).strip()
    cut = h[:n]
    return cut[:cut.rfind(' ')].rstrip(' ,;:(-') + '\u2026' if ' ' in cut else cut

class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path = path; self.title = ''; self.heading = ''; self.entries = []
        self.cap = None            # ('title'|'h'|'label'|'tile', attrs, [text])
        self.pending = None        # label waiting for its input id
        self.depth = 0; self.in_script = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'script': self.in_script = True; return
        if self.cap and self.cap[0] in ('h', 'title') and tag in ('span', 'small', 'i', 'em'):
            self.cap[2].append('\x00'); return          # a heading's subtitle is not the heading
        if self.cap and self.cap[0] == 'tile':
            self.cap[2].append('\x01'); return          # tile title / subtitle boundary (no space in the markup)
        if tag in ('h1', 'title') and not self.title: self.cap = ('title', a, [])
        elif tag in ('h2', 'h3'): self.cap = ('h', a, [])
        elif tag in ('label', 'b', 'span', 'th') and a.get('data-help') is not None:
            if tag == 'th': return
            self.cap = ('label', a, [])
        elif tag == 'a' and a.get('href', '').startswith('/') and 'btn' in a.get('class', ''):
            self.cap = ('tile', a, [])
        elif tag in ('input', 'select', 'textarea') and a.get('type') not in ('hidden', 'submit', 'button'):
            if self.cap and self.cap[0] == 'label':
                self.cap[1]['_id'] = a.get('id', '')                  # nested inside its label
            elif self.pending is not None:
                self.pending['id'] = a.get('id', ''); self.pending = None
    def handle_endtag(self, tag):
        if tag == 'script': self.in_script = False; return
        if not self.cap: return
        kind, a, text = self.cap
        t = clean(''.join(x for x in text if x not in ('\x00', '\x01')))
        if kind == 'title' and tag in ('h1', 'title'):
            self.title = t.split('·')[0].strip() if t else ''
        elif kind == 'h' and tag in ('h2', 'h3'):
            self.heading = t
            if a.get('data-help') is not None and t:
                self.entries.append({'l': t, 'h': '', 'id': a.get('id', ''), 'k': hint_of(a['data-help'])})
        elif kind == 'label' and tag in ('label', 'b', 'span'):
            if t and len(t) < 80:
                e = {'l': t, 'h': self.heading, 'id': a.get('_id', ''), 'k': hint_of(a['data-help'])}
                self.entries.append(e); self.pending = None if a.get('_id') else e
        elif kind == 'tile' and tag == 'a':
            parts = [clean(x) for x in ''.join(text).split('\x01')]
            parts = [x for x in parts if x]
            if parts:
                self.entries.append({'l': parts[0][:90], 'h': '', 'id': '', 'k': ' '.join(parts[1:])[:100],
                                     'href': a['href'], 'tile': True})
        else:
            return
        self.cap = None
    def handle_data(self, d):
        if self.cap and '\x00' not in self.cap[2]: self.cap[2].append(d)

# Settings the pages draw in JavaScript (no static label to find), and pages
# whose purpose deserves a plain-English entry of its own.
EXTRA = [
 ('/rotorflight-pid', 'PIDs', 'P, I, D and F gains for roll, pitch and yaw', 'p_roll', 'The main flight tuning numbers, one row per axis; softer or sharper sliders above them'),
 ('/rotorflight-pid', 'PIDs', 'Boost and HSI gain (O)', '', 'Extra kick on fast stick movements; how strongly the high-speed trim builds up (O gain). The trim cap (HSI offset limit) is on the PID+ page'),
 ('/rotorflight-rates', 'Rates', 'Roll, pitch and yaw rate, expo and max velocity', 'r_rate', 'How fast the model rotates at full stick and how soft the centre feels'),
 ('/rotorflight-servos', 'Servos', 'Servo centre, minimum, maximum, rate and reverse', 's0c', 'Per servo: centre position, travel limits, pulse rate, direction and geometry correction'),
 ('/rotorflight-modes', 'Switches', 'What each transmitter switch does (arm, rescue, bank selector) and which channel', 'm0', 'Assign flight-controller functions to transmitter switches with their live channel bars'),
 ('/rotorflight-txchannels', 'Transmitter channels', 'Which channel is throttle, collective, arm, rescue, bank selector', '', 'Channel map and the detect-by-wiggling helper'),
 ('/rotorflight-travel', 'Travel extents', 'Pitch gauge calibration and collective/cyclic limits', '', 'Bench hold drives the swash to exact angles for a pitch gauge'),
 ('/rotorflight-copybank', 'Copy a bank', 'Copy PIDs, rates and governor from one bank to another, scaled for head speed', '', 'The head-speed tick adjusts the gains for the target bank'),
 ('/rotorflight-backup', 'Backup & restore', 'Back up, restore, share or import the whole Rotorflight setup', '', 'The whole setup safe on the phone; restore to this or another model'),
 ('/rotorflight-easy', 'Easy tuning', 'All the plain-English sliders in one place', 'e_start', 'Start hardness, agility, stick feel, cyclic and tail softer/sharper'),
 ('/rotorflight-gov-profile', 'Governor (per bank)', 'Head speed for this bank (RPM)', 'g_hs', 'The rotor speed the governor holds in the selected bank'),
 ('/rotorflight-gov-global', 'Governor (global)', 'Spool-up, start-up, spool-down and speed-change (tracking) times', 'g_spool', 'Timings in seconds for every bank'),
 ('/rotorflight-firsttime', 'First-time basics', 'Battery cell count and capacity', 'b_cells', 'Tell Rotorflight the pack size so warnings and telemetry read true'),
 ('/rotorflight-firsttime', 'First-time basics', 'Motor poles, gear ratio and ESC brand', '', 'Motor & ESC card: the numbers the head-speed reading depends on'),
 ('/rotorflight-firsttime', 'First-time basics', 'Which telemetry readings go to the transmitter', '', 'Flight mode, battery, head speed, temperature, attitude, altitude, GPS'),
 ('/rotorflight-blackbox', 'Flight recorder', 'Rotorflight blackbox logging rate and fields', '', 'What the flight controller records to its own card'),
 ('/rotorflight-escprog', 'ESC programming', 'Scorpion ESC settings (soft start, governor gains, BEC voltage, timing)', '', 'Read and change the ESC parameters over the telemetry wire'),
 ('/rotorflight-rescue', 'Rescue', 'Rescue mode: pull-up strength, climb and level', '', 'The panic switch that rights the model'),
 ('/rotorflight-filters', 'Filters', 'Gyro lowpass, rotor-speed (RPM) notches, dynamic and fixed notches', 'lpf1', 'Take the vibration out of the gyro signal; the help says how to read the black box for it'),
 ('/rotorflight-filtercheck', 'Vibration check', 'Reads the black box over USB, shows the gyro spectrum before and after the filters, says which filter to change and applies it', '', 'Rotor, motor, tail or a loose part: the peaks are named from the head speed'),
 ('/rotorflight-ports', 'Ports', 'Which flight-controller port carries the receiver (CRSF), a dongle wire (MSP) or ESC telemetry', '', 'Rotorflight Ports tab: set a UART once, the flight controller restarts'),
 ('/rotorflight-esc', 'ESC', 'ESC telemetry protocol and status', '', 'What the ESC reports over its telemetry wire'),
 ('/rxsettings', 'Receiver settings', 'Arming channel, auto fly mode, landing wiggle', 'armch', 'The receiver-side switches: which channel arms, radios off in flight, servo wiggle on landing'),
 ('/rxsettings', 'Receiver settings', 'Battery voltage divider pin, ratio and cells', 'vbatPin', 'The receiver\'s own volts wire for models without a flight controller'),
 ('/rxsettings', 'Receiver settings', 'Output protocol (CRSF, SBUS, IBUS, PPM, FBUS) and CRSF frame rate', '', 'How the receiver talks to the flight controller or servos'),
 ('/wifi', 'WiFi', 'Home WiFi name (SSID) and password', 'ssid', 'Join your home network so the receiver updates over the air'),
 ('/firmware', 'Update', 'Receiver firmware update (over the air)', '', 'Install the newest receiver version from messiter.com'),
 ('/bind', 'Bind', 'Bind the receiver to the transmitter', '', 'Pairing: the transmitter\'s ID becomes the receiver\'s address'),
 ('/blackbox', 'Black box', 'Live status, flight analysis graph, event log, save session', '', 'Volts per cell, head speed, current, ESC temperature and the link statistics'),
 ('/flight', 'Flight analysis', 'Head speed, volts and current graph for each flight', '', 'The last 20 flights, one-second samples'),
 ('/sim', 'Simulator', 'Drive a PC simulator over USB (RealFlight, neXt)', '', 'The receiver becomes a USB joystick and keyboard'),
 ('/views', 'Simulator keys', 'Camera views and simulator keys from the phone', '', 'RealFlight menu and camera keys; neXt keys; realistic spool-up'),
 ('/map', 'Remap channels', 'Receiver channels to simulator outputs, reversed if needed', '', 'Which channel drives which joystick axis'),
 ('/rotorflight', 'Rotorflight', 'Telemetry speed: fast or standard', '', 'How quickly Rotorflight answers the phone and the transmitter'),
 ('/setup', 'Setup', 'One-time receiver configuration menu', '', 'WiFi, protocol, bind, receiver settings, diagnostics'),
 ('/setup', 'Setup', 'USB socket: flight controller over USB (like the dongle), or off', 'usbfcbtn', 'A USB-C cable from the receiver to the flight controller gives the app every Rotorflight setting; the simulator uses the socket instead'),
 ('/diagnostics', 'Diagnostics', 'Channel bars, radio statistics, raw values', '', 'See every channel live and the link quality'),
]

# Words people type that the pages phrase differently.
SYN = [
 ('head speed', 'rpm revs headspeed rotor speed'), ('headspeed', 'rpm head speed'), ('rpm', 'head speed revs'),
 ('cell', 'cells lipo battery 6s 12s pack'), ('spool', 'spoolup spool-up soft start startup'),
 ('tracking', 'speed change bank change transition'), ('arm', 'arming motor enable safety switch'),
 ('wiggle', 'servo wiggle landing tail twitch'), ('telemetry', 'volts amps temperature readings'),
 ('bind', 'binding pair pairing link'), ('wifi', 'ssid password network hotspot'),
 ('firmware', 'update upgrade ota version install'), ('backup', 'restore save copy export import'),
 ('rescue', 'panic save me level'), ('governor', 'gov'), ('expo', 'exponential feel centre center soft'),
 ('rate', 'rates agility roll rate speed'), ('gear', 'ratio pinion teeth'), ('esc', 'speed controller scorpion hobbywing'),
 ('travel', 'pitch collective limit degrees'), ('servo', 'centre center subtrim reverse direction'),
 ('filter', 'notch vibration lowpass rpm dynamic gyro noise fft spectrum'), ('blackbox', 'log logging flight record recorder'), ('sim', 'simulator realflight next joystick usb'), ('usb', 'socket cable usb-c flight controller dongle simulator'), ('port', 'ports uart socket wire crsf msp serial'),
 ('throttle', 'motor power'), ('handover', 'takes over'), ('idle', 'tick over'), ('bank', 'profile banks flight mode'),
 ('yaw', 'tail rudder'), ('roll', 'aileron cyclic'), ('pitch', 'elevator cyclic'), ('collective', 'pitch stick'),
 ('battery', 'lipo volts voltage cells'), ('capacity', 'mah'), ('temperature', 'temp heat'), ('current', 'amps'),
 ('autorotation', 'auto autos bail-out bailout'), ('hold', 'throttle hold cut'),
]
def syn(text):
    t = text.lower(); out = []
    for k, v in SYN:
        if k in t: out.append(v)
    return ' '.join(out)

entries = []
for f in sorted(glob.glob(os.path.join(ROOT, '*.html'))):
    name = os.path.basename(f)
    if name in SKIP or name.startswith('_'): continue      # _head.html etc. are includes, not pages
    path = '/' if name == 'index.html' else '/' + name[:-5]
    p = Page(path)
    try: p.feed(open(f, encoding='utf-8').read())
    except Exception as e: print('parse', name, e); continue
    title = p.title or name[:-5]
    entries.append({'p': path, 'g': title, 'h': '', 'l': title, 'id': '', 'k': '', 'page': True})
    seen = set()
    for e in p.entries:
        key = (e['l'].lower(), e.get('href', ''))
        if key in seen: continue
        seen.add(key)
        if e.get('tile'):
            entries.append({'p': e['href'], 'g': title, 'h': 'menu', 'l': e['l'], 'id': '', 'k': e.get('k', '')})
        else:
            entries.append({'p': path, 'g': title, 'h': e['h'], 'l': e['l'], 'id': e['id'], 'k': e['k']})
for p, g, l, i, k in EXTRA:
    entries.append({'p': p, 'g': g, 'h': '', 'l': l, 'id': i, 'k': k})

rows = []
for e in entries:
    s = syn(e['l'] + ' ' + e['h'] + ' ' + e['k'] + ' ' + e['g'])
    rows.append([e['p'], e['g'], e['h'], e['l'], e['id'], e['k'], s])
js = 'window.LDRC_SEARCH=' + json.dumps(rows, ensure_ascii=False, separators=(',', ':')) + ';\n'
out = os.path.join(ROOT, 'search.js')
open(out, 'w', encoding='utf-8').write(js)
pages = len({r[0] for r in rows})
print(f'search.js: {len(rows)} entries across {pages} pages, {len(js.encode())} bytes')
