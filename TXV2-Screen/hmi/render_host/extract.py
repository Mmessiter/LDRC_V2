#!/usr/bin/env python3
"""Cut the screen's drawing, page-loading, script-host and command code out of src/main.cpp (by marker lines, so it
follows main.cpp as it changes) into gen/main_parts.inc for render.cpp. The parts in between (the panel, touch, WiFi,
audio, the backlight ...) are replaced by the stubs in render.cpp.

The pages of the screen's OWN (the WiFi page, the update panel, the picture chooser, the command line, the link's
panel, the banners) are cut out of src/*.h the same way, into gen/own_*.inc for own.h: their drawing code only - the
radios, the card and the web around them are own.h's make-believe."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', '..', 'src')
MAIN = os.path.join(SRC, 'main.cpp')
PARTS = [  # (first line starts with, the line that ends the part starts with)
    ('struct Rect16 {', 'TouchDrvGT911 touch;'),
    ('// ------------------------------------------------------------------ fonts', '// Nextion component type codes'),
    ('// Nextion component type codes', 'static Page page;'),
    ('static Page page;', '// What the transmitter is doing'),
    ('@STUBS', None),
    ('static Comp *find(const std::string &nm)', '// ------------------------------------------------------------------ pages of our own'),
]
_files = {}
def lines_of(name):
    if name not in _files: _files[name] = open(os.path.join(SRC, name)).read().split('\n')
    return _files[name]
def at(name, prefix, after=0, strip=False):
    ls = lines_of(name)
    for i in range(after, len(ls)):
        if (ls[i].lstrip() if strip else ls[i]).startswith(prefix): return i
    sys.exit(f'extract.py: no line in {name} starts with {prefix!r}' + (f' after line {after + 1}' if after else ''))
def cut(name, start, end, after=None, inclusive=False, strip=False):
    """The lines of src/NAME from the one starting with START to the one starting with END (that one too if inclusive);
    AFTER: look only after the line starting with it (a part inside a function). Indented lines match with strip=True."""
    a0 = at(name, after) if after else 0
    a = at(name, start, a0, strip); b = at(name, end, a + 1, strip) + (1 if inclusive else 0)
    return [f'#line {a + 1} "src/{name}"'] + lines_of(name)[a:b]

# ---- main.cpp's own parts, for render.cpp
lines = lines_of('main.cpp')
out = []
for start, end in PARTS:
    if start == '@STUBS': out.append('#include "stubs.h"'); continue
    a = at('main.cpp', start); b = at('main.cpp', end, a + 1)
    out.append(f'#line {a + 1} "src/main.cpp"'); out.extend(lines[a:b])
os.makedirs(os.path.join(HERE, 'gen'), exist_ok=True)
open(os.path.join(HERE, 'gen', 'main_parts.inc'), 'w').write('\n'.join(out) + '\n')
print(f'gen/main_parts.inc: {sum(1 for l in out if not l.startswith("#line"))} lines of main.cpp')

# ---- the screen's own pages, for own.h (each file is included where own.h has made what it needs)
def frame(signature, part):     # lines from inside a poll function (its "draw everything" block), as a function of their own
    return [signature + ' {'] + part + ['}']
OWN = {
    # the layer's text helpers, the two-second banner along the top, the link's panel
    'own_base.inc': cut('main.cpp', 'static void topText(', '// ------------------------------------------------------------------ the Teensy\'s card')
                  + cut('main.cpp', 'static const int BANNER_H', 'static void applyRadios(')
                  + cut('main.cpp', 'static void linkPanel(bool result)', 'static void linkPanelGone()'),
    # the WiFi page: its drawing, and wifiPoll's "draw it all"
    'own_wifi.inc': cut('wifi_device.h', '#define WF_BACK', 'static bool wifiPageUp()')
                  + frame('static void wifiFrame(const ldrc::WifiScene &sc)', ['std::map<int, uint32_t> drawn;'] + cut('wifi_device.h', 'wifiStrip = WF_STRIP;', 'for (auto &it : sc.items) { wifiDrawItem(it);', after='static void wifiPoll()', inclusive=True, strip=True)),
    # "Check for update" / "Receiver update": the panel
    'own_update.inc': cut('update_device.h', 'static const int UPD_X', 'static bool updPanelUp()'),
    # the picture chooser: the names of the card's folders, the thumbnails (before the host) ...
    'own_pics_cache.inc': cut('pics_device.h', 'static const char PIC_MINE_DIR', '// ------------------------------------------------------------------ the card')
                        + cut('pics_device.h', 'static std::vector<ldrc::PicEntry> picCardList', '// ------------------------------------------------------------------ the chooser\'s host'),
    # ... and the drawing, picPoll's "draw it all", and the "Opening..." frame (after it)
    'own_pics.inc': cut('pics_device.h', '// ------------------------------------------------------------------ drawing', '// ------------------------------------------------------------------ the finger')
                  + frame('static void picFrame()', ['std::map<int, std::string> drawn;'] + cut('pics_device.h', 'picChooseFont();', 'for (int id : PIC_PARTS) { picDrawPart(id);', after='static void picPoll()', inclusive=True, strip=True))
                  + cut('pics_device.h', 'static uint32_t picSoonUntil', 'static void picSoonPoll()'),
    # the command line: its console, and cliPoll's "draw it all" (the rest is the WiFi page's drawing)
    'own_cli.inc': cut('cli_device.h', 'static void cliDrawConsole(', 'static void cliTouch(')
                 + frame('static void cliFrame(const ldrc::WifiScene &sc)', ['std::map<int, uint32_t> drawn;'] + cut('cli_device.h', 'wifiStrip = WF_STRIP;', 'for (auto &it : sc.items) { if (it.id == ldrc::CLI_ID_CONSOLE)', after='static void cliPoll()', inclusive=True, strip=True)),
    # "Connecting Bluetooth" over the Rotorflight menu
    'own_ble.inc': cut('ble_device.h', 'static bool pipeNoticeUp', 'static void pipeNoticeClear()'),
}
for name, part in OWN.items():
    open(os.path.join(HERE, 'gen', name), 'w').write('\n'.join(part) + '\n')
print(f'gen/own_*.inc: {sum(sum(1 for l in p if not l.startswith("#line")) for p in OWN.values())} lines of the screen\'s own pages')
