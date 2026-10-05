#!/usr/bin/env python3
"""Cut the screen's drawing, page-loading, script-host and command code out of src/main.cpp (by marker lines, so it
follows main.cpp as it changes) into gen/main_parts.inc for render.cpp. The parts in between (the panel, touch, WiFi,
audio, the backlight ...) are replaced by the stubs in render.cpp."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, '..', '..', 'src', 'main.cpp')
PARTS = [  # (first line starts with, the line that ends the part starts with)
    ('struct Rect16 {', 'TouchDrvGT911 touch;'),
    ('// ------------------------------------------------------------------ fonts', '// Nextion component type codes'),
    ('// Nextion component type codes', 'static Page page;'),
    ('static Page page;', '// What the transmitter is doing'),
    ('@STUBS', None),
    ('static Comp *find(const std::string &nm)', '// ------------------------------------------------------------------ pages of our own'),
]
lines = open(MAIN).read().split('\n')
def at(prefix, after=0):
    for i in range(after, len(lines)):
        if lines[i].startswith(prefix): return i
    sys.exit(f'extract.py: no line in main.cpp starts with {prefix!r}')
out = []
for start, end in PARTS:
    if start == '@STUBS': out.append('#include "stubs.h"'); continue
    a = at(start); b = at(end, a + 1)
    out.append(f'#line {a + 1} "src/main.cpp"'); out.extend(lines[a:b])
os.makedirs(os.path.join(HERE, 'gen'), exist_ok=True)
open(os.path.join(HERE, 'gen', 'main_parts.inc'), 'w').write('\n'.join(out) + '\n')
print(f'gen/main_parts.inc: {sum(1 for l in out if not l.startswith("#line"))} lines of main.cpp')
