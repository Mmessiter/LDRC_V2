#!/usr/bin/env python3
"""The Bluetooth pipe from the Mac, through the screen's workshop door (screen 1.11.x). The screen must be on the house
WiFi with its door open (hold the top right corner 3 s).
   python3 dev/pipe_bench.py [SCREEN] status                  state, receivers seen, what is joined
   python3 dev/pipe_bench.py [SCREEN] on [NAME]               join (the strongest receiver, or the one named)
   python3 dev/pipe_bench.py [SCREEN] off
   python3 dev/pipe_bench.py [SCREEN] get /api/state.json     a request over the pipe, the reply printed
   python3 dev/pipe_bench.py [SCREEN] read 12 5000            "send me the rates block for 5 s", then the block polled
   python3 dev/pipe_bench.py [SCREEN] log                     the screen's boot log, the pipe's lines"""
import json, sys, time, urllib.request, urllib.parse
args = sys.argv[1:]
host = args.pop(0) if args and args[0][0].isdigit() else '192.168.1.195'
def call(path, method='GET', body=None):
    req = urllib.request.Request(f'http://{host}{path}', data=body.encode() if body is not None else None, method=method, headers={'X-LDRC': '1'})
    try: return urllib.request.urlopen(req, timeout=10).read().decode(errors='replace')
    except urllib.error.HTTPError as e: return f'{e.code} {e.read().decode(errors="replace")}'
def request(method, path, body='', ctype=''):
    r = call(f'/ble/req?method={method}&path={urllib.parse.quote(path, safe="/?=&,")}' + (f'&type={urllib.parse.quote(ctype)}' if ctype else ''), 'POST', body)
    if not r.strip().isdigit(): return r
    for _ in range(80):
        time.sleep(0.1); r = call('/ble/reply')
        if not r.startswith('202'): return r
    return 'no reply in 8 s'
cmd = args[0] if args else 'status'
if cmd == 'status': print(json.dumps(json.loads(call('/ble/status')), indent=1))
elif cmd == 'on': print(call('/ble/on' + (f'?name={urllib.parse.quote(args[1])}' if len(args) > 1 else ''), 'POST', '')); time.sleep(6); print(call('/ble/status'))
elif cmd == 'off': print(call('/ble/off', 'POST', ''))
elif cmd == 'get': print(request('GET', args[1]))
elif cmd == 'read':
    ident, ms = int(args[1]), int(args[2]) if len(args) > 2 else 5000
    print(request('POST', '/api/txparams', f'w={ident},321,{ms},0,0,0,0,0,0,0,0,0', 'application/x-www-form-urlencoded'))   # as a form: the bridge gives handlers no raw body
    for _ in range(6): time.sleep(0.5); print(request('GET', '/api/txparams/ack'))
elif cmd == 'log': print('\n'.join(l for l in call('/bootlog').splitlines() if ' ble ' in l))
else: print(__doc__)
