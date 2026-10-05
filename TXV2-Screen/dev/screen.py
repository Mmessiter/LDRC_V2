#!/usr/bin/env python3
"""Talk to the V1B screen over WiFi.
   screen.py status                      what page, counters, heap
   screen.py cmd 'page FrontView' ...    send Nextion commands (as the Teensy would)
   screen.py put LOCALFILE /hmi/pages/13.json   copy a file onto the card
   screen.py sync                        push sd/hmi/pages + index.json (after build_sd.py)
   screen.py shot [out.png]              screenshot of the framebuffer
   screen.py ls [/hmi]"""
import sys, os, struct, subprocess, json, urllib.request
HOST = os.environ.get('SCREEN', 'ldrc-screen.local')
def get(path): return urllib.request.urlopen(f'http://{HOST}{path}', timeout=15).read()
def post(path, data, ctype='text/plain'):
    r = urllib.request.Request(f'http://{HOST}{path}', data=data, headers={'Content-Type': ctype, 'X-LDRC': '1'}); return urllib.request.urlopen(r, timeout=60).read()
def put(local, remote):
    subprocess.run(['curl', '-s', '-H', 'X-LDRC: 1', '-F', f'file=@{local}', f'http://{HOST}/put?path={remote}'], check=True)
cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
if cmd == 'status': print(get('/status').decode())
elif cmd == 'cmd': print(post('/cmd', '\n'.join(sys.argv[2:]).encode('latin1')).decode())
elif cmd == 'put': put(sys.argv[2], sys.argv[3]); print('put', sys.argv[3])
elif cmd == 'ls': print(get('/ls?path=' + (sys.argv[2] if len(sys.argv) > 2 else '/')).decode())
elif cmd == 'sync':
    here = os.path.dirname(os.path.abspath(__file__)); base = os.path.join(here, '..', 'sd', 'hmi')
    put(os.path.join(base, 'index.json'), '/hmi/index.json')
    for fn in sorted(os.listdir(os.path.join(base, 'pages'))): put(os.path.join(base, 'pages', fn), '/hmi/pages/' + fn)
    print('synced pages + index')
elif cmd == 'shot':
    raw = get('/fb'); W, H = 800, 480
    assert len(raw) == W * H * 2, len(raw)
    out = sys.argv[2] if len(sys.argv) > 2 else '/tmp/screen.png'
    try:
        from PIL import Image
        img = Image.new('RGB', (W, H)); px = img.load()
        for i in range(W * H):
            v = raw[2*i] | (raw[2*i+1] << 8)
            px[i % W, i // W] = (((v >> 11) & 31) << 3, ((v >> 5) & 63) << 2, (v & 31) << 3)
        img.save(out); print(out)
    except ImportError:
        open(out + '.565', 'wb').write(raw); print(out + '.565 (no PIL)')
