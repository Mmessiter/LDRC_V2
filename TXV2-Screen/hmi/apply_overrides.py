#!/usr/bin/env python3
"""Apply hmi/overrides.json to the built pages in sd/hmi/pages: {page: {component: {field: value | {sub: value}}}},
   and {"+": {page: [components to add]}}.
   Run after build_sd.py (build_sd.py calls it), or alone to re-tweak without rebuilding the pictures."""
import json, os
here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, '..', 'sd', 'hmi')
ov = json.load(open(os.path.join(here, 'overrides.json')))
ids = {p['name']: p['id'] for p in json.load(open(os.path.join(out, 'index.json')))['pages']}
changed = []
# "+": components added to a page (our own buttons). Put in again on every run: the same name is replaced, not doubled.
for pname, extra in ov.get('+', {}).items():
    if pname not in ids: print('no such page', pname); continue
    path = os.path.join(out, 'pages', f'{ids[pname]}.json')
    page = json.load(open(path))
    names = {c['n'] for c in extra}
    used = {c['i'] for c in page['comps'] if c['n'] not in names}
    for c in extra:
        if c['i'] in used: raise SystemExit(f"{pname}: id {c['i']} of {c['n']} is taken")
    page['comps'] = [c for c in page['comps'] if c['n'] not in names] + extra
    json.dump(page, open(path, 'w'), separators=(',', ':'))
    changed.append(f'{pname} (+{len(extra)})')
for pname, comps in ov.items():
    if pname.startswith('_') or pname == '+' or pname not in ids: continue
    path = os.path.join(out, 'pages', f'{ids[pname]}.json')
    page = json.load(open(path))
    byname = {c['n']: c for c in page['comps']}
    for cname, fields in comps.items():
        c = byname.get(cname)
        if not c: print('no such component', pname, cname); continue
        for k, v in fields.items():
            if isinstance(v, dict): c.setdefault(k, {}).update(v)
            else: c[k] = v
    json.dump(page, open(path, 'w'), separators=(',', ':'))
    changed.append(f'{pname} ({ids[pname]}.json)')
print('overrides applied:', ', '.join(changed))
