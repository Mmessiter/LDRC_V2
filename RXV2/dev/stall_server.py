#!/usr/bin/env python3
"""OTA-resume test server (2026-09-02, proved 0.9.544 on the Goblin). Serve a release folder, but break the first request for each file part-way:
send CUT bytes, then close the socket. Later requests honour Range (206) — exactly
what a flaky WiFi link + LiteSpeed look like to the receiver. Second mode: --norange
ignores Range and always sends 200 + whole file (tests the skip path).

    python3 stall_server.py <dir> <port> [--cut BYTES] [--norange] [--breaks N]
"""
import http.server, os, socketserver, sys

d = sys.argv[1]; port = int(sys.argv[2])
CUT = 300_000; NORANGE = False; BREAKS = 1
a = sys.argv[3:]
while a:
    x = a.pop(0)
    if x == '--cut': CUT = int(a.pop(0))
    elif x == '--norange': NORANGE = True
    elif x == '--breaks': BREAKS = int(a.pop(0))
served = {}

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    def do_GET(self):
        p = os.path.join(d, self.path.lstrip('/'))
        if not os.path.isfile(p):
            self.send_response(404); self.end_headers(); return
        data = open(p, 'rb').read()
        n = served.get(self.path, 0); served[self.path] = n + 1
        start = 0
        rng = self.headers.get('Range')
        if rng and not NORANGE:
            start = int(rng.split('=')[1].split('-')[0])
            self.send_response(206)
            self.send_header('Content-Range', f'bytes {start}-{len(data)-1}/{len(data)}')
        else:
            self.send_response(200)
        body = data[start:]
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Accept-Ranges', 'bytes')
        self.end_headers()
        if n < BREAKS:
            cut = min(CUT, len(body))
            self.wfile.write(body[:cut]); self.wfile.flush()
            self.log_message('BREAK %s after %d bytes (request %d, start %d)', self.path, cut, n + 1, start)
            self.connection.close()   # RST/FIN mid-body
            return
        self.wfile.write(body)
        self.log_message('FULL %s from %d (%d bytes)', self.path, start, len(body))

socketserver.TCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(('0.0.0.0', port), H) as s:
    print(f'stall server on :{port} dir={d} cut={CUT} norange={NORANGE} breaks={BREAKS}', flush=True)
    s.serve_forever()
