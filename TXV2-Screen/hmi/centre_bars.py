#!/usr/bin/env python3
"""Channel bars that grow from the middle, on the front page and the Channels page (screen 1.7.0). Malcolm, 2026-10-04,
after the flight screen's bars: "your style of making the channel bars move out from the centre instead of always from
the left to right is better and perhaps should be imitated on the default front screen as well as the channels screen."
The screen draws a progress bar with "centre": true from its middle to its value; the value, and where the bar's end
falls, are as before. (Also in hmi/overrides.json, for a rebuild from the HMI.) Safe to run again."""
import json, os
PAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sd', 'hmi', 'pages')
for pid, name in ((13, 'FrontView'), (26, 'SticksView')):
    p = os.path.join(PAGES, f'{pid}.json'); pg = json.load(open(p))
    assert pg['name'] == name, (pid, pg['name'])
    bars = [c for c in pg['comps'] if c['t'] == 'progress bar' and c['n'] in {f'Ch{i}' for i in range(1, 17)}]
    assert len(bars) == 16, (name, len(bars))
    for c in bars: c['centre'] = True
    json.dump(pg, open(p, 'w'), separators=(',', ':'))
    print(f'{name}: 16 channel bars from the middle')
