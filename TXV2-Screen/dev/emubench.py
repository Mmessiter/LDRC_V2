#!/usr/bin/env python3
"""Bench helpers for the V1B screen over WiFi (import or exec): get/post/cmd/one/shot/tap.
   SCREEN=192.168.1.195 python3 dev/emubench.py            # status
   ... shot out.png | tap X Y | cmd 'page FrontView' 'Sto.val=120' | one 'LogText.txt="a\r\nb"'
   shot reads what the PANEL shows (screenFb); tap presses the screen from the Mac (POST /tap)."""
import os
import sys, time, zlib, struct, urllib.request
HOST=os.environ.get('SCREEN', '192.168.1.195')
def get(p): return urllib.request.urlopen(f'http://{HOST}{p}', timeout=20).read()
def post(p, data): r=urllib.request.Request(f'http://{HOST}{p}', data=data, headers={'Content-Type':'text/plain', 'X-LDRC': '1'}); return urllib.request.urlopen(r, timeout=60).read()
def cmd(*cs):
    for c in cs: post('/cmd', c.encode('latin1'))
def one(c): post('/cmd?one=1', c.encode('latin1'))
def shot(name):
    raw=get('/fb'); W,H=800,480; assert len(raw)==W*H*2
    rows=bytearray()
    for y in range(H):
        rows.append(0)
        row=raw[y*W*2:(y+1)*W*2]
        for i in range(0,W*2,2):
            v=row[i]|(row[i+1]<<8)
            rows+=bytes((((v>>11)&31)<<3, ((v>>5)&63)<<2, (v&31)<<3))
    def chunk(t,d): return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',W,H,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(rows),6))+chunk(b'IEND',b'')
    open(name,'wb').write(png); print('shot', name)

def tap(x, y, ms=120): post(f'/tap?x={x}&y={y}&ms={ms}', b''); time.sleep(0.6)
if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] == 'status': print(get('/status').decode())
    elif a[0] == 'shot': shot(a[1] if len(a) > 1 else '/tmp/screen.png')
    elif a[0] == 'tap': tap(int(a[1]), int(a[2]))
    elif a[0] == 'cmd': cmd(*a[1:])
    elif a[0] == 'one': one(a[1])

# ---- walking the live transmitter's menus with the remote finger
import json as _json, os as _os
_HMI = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'sd', 'hmi')
def status(): return _json.loads(get('/status'))
def button(page, text):
    """Centre of the button with that label on that page (from the page data)."""
    ids = {p['name']: p['id'] for p in _json.load(open(_os.path.join(_HMI, 'index.json')))['pages']}
    for c in _json.load(open(_os.path.join(_HMI, 'pages', f"{ids[page]}.json")))['comps']:
        if c['t'] == 'button' and (c.get('txt') or '').strip() == text: return c['x'] + c['w'] // 2, c['y'] + c['h'] // 2
    return None
def press(text, wait=1.8):
    p = status()['page']; xy = button(p, text)
    if not xy: return False
    post(f'/tap?x={xy[0]}&y={xy[1]}&ms=120', b''); time.sleep(wait); return True
def go_home(max_hops=8):
    """Press OK until the transmitter is back on its front page (wakes the screen saver first)."""
    for _ in range(max_hops):
        p = status()['page']
        if p == 'FrontView': return True
        if p == 'BlankView': post('/tap?x=400&y=240&ms=120', b''); time.sleep(2.5); continue
        if not press('OK'): return False
    return status()['page'] == 'FrontView'
