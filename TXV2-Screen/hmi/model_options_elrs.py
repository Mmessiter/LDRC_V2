#!/usr/bin/env python3
"""RXOptionsView (page 9, "Model options"): the switch "ELRS receiver (off: LDRC)" (Malcolm, 13 Nov 2026: "Add to the model
setup screen the option 'LDRC or ELRS receiver?'" - a model flown through the ExpressLRS module inside the transmitter instead
of an LDRC receiver). The switch c4 and its label l_t6 are HIDDEN BY THE PAGE ITSELF (its start-up lines: vis l_t6,0 and
vis c4,0) and shown only by a main board whose firmware has ELRS in it (TXV1B ElrsCrsf.h, ElrsOptionShow: test builds for now).
A transmitter without that firmware shows nothing of it, and nothing can be touched there.
The right-hand column gets one more row: 'Six banks' moves up to y 338 and the new row takes y 369, the two rows the left-hand
column already ends with. Names, ids, types and events of what was there are untouched; the new components take ids above the
page's old maximum. Safe to run again. Applied to sd/hmi/pages/9.json (the card) and, the same components, to
hmi/originals/9.json (what pagestyle verifies against)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
LABEL = 'ELRS receiver (off: LDRC)'
HIDE = 'vis l_t6,0\nvis c4,0'
def one(path, layout):
    pg = json.load(open(path))
    def comp(n): return next((c for c in pg['comps'] if c['n'] == n), None)
    nextId = max(c['i'] for c in pg['comps']) + 1
    def clone(src, n, after):
        nonlocal nextId
        if comp(n): return comp(n)
        d = json.loads(json.dumps(comp(src))); d['n'] = n; d['i'] = nextId; nextId += 1
        pg['comps'].insert(pg['comps'].index(comp(after)) + 1, d); return d
    lab = clone('l_t5', 'l_t6', 'c3'); sw = clone('c3', 'c4', 'l_t6')
    lab['txt'] = LABEL; lab['a']['txt_maxl'] = 30
    sw['val'] = 0; sw.pop('ev', None)
    if layout:
        comp('l_t5').update({'y': 338}); comp('c3').update({'y': 338})
        lab.update({'x': 418, 'y': 369, 'w': 266, 'h': 28}); sw.update({'x': 692, 'y': 369, 'w': 80, 'h': 28})
    else:
        lab.update({'y': comp('l_t5')['y'] + 31}); sw.update({'y': comp('c3')['y'] + 31})
    pre = pg['ev'].get('preinitialize', '')
    if 'vis c4,0' not in pre: pg['ev']['preinitialize'] = (pre + '\n' if pre else '') + HIDE
    json.dump(pg, open(path, 'w'), separators=(',', ':') if layout else None, indent=None if layout else 1)
    return len(pg['comps']), nextId - 1
if __name__ == '__main__':
    print('sd:', one(os.path.join(HERE, '..', 'sd', 'hmi', 'pages', '9.json'), True))
    print('originals:', one(os.path.join(HERE, 'originals', '9.json'), False))
