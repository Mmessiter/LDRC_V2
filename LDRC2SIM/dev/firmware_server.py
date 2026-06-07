#!/usr/bin/env python3
"""
Local firmware server for LDRC2SIM.

Drop LDRC2SIM-x.y.z.bin files in this folder and run this script. The device's
Firmware page (Check for updates) picks them up automatically and offers
update / roll-back / reinstall — no file names, no USB.

Usage:
    python3 dev/firmware_server.py            # serves on port 8001
    python3 dev/firmware_server.py 9002       # custom port

The device's compiled-in default manifest URL is:
    http://m4macmini.local:8001/manifest.json
(8001, so it doesn't clash with the RXV2 server on 8000.)
"""
import http.server
import json
import os
import re
import socket
import socketserver
import sys
from pathlib import Path

HERE = Path(__file__).parent.resolve()
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8001


def parse_version(name: str):
    m = re.match(r"LDRC2SIM-(\d+)\.(\d+)\.(\d+)(?:-(.+))?", name)
    if not m:
        return (0, 0, 0, "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4) or "")


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_GET(self):
        if self.path == "/manifest.json":
            self._send_manifest()
            return
        super().do_GET()

    def _send_manifest(self):
        versions = []
        for b in sorted(HERE.glob("LDRC2SIM-*.bin")):
            ver = parse_version(b.stem)
            versions.append({
                "name": b.stem,
                "url": f"/{b.name}",
                "size": b.stat().st_size,
                "mtime": int(b.stat().st_mtime),
                "_v": ver,
            })
        versions.sort(key=lambda v: v["_v"], reverse=True)
        for v in versions:
            v.pop("_v")
        body = json.dumps({"versions": versions}, indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def my_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


if __name__ == "__main__":
    os.chdir(HERE)
    ip = my_lan_ip()
    print(f"LDRC2SIM firmware server — {HERE}")
    print(f"Manifest:  http://{ip}:{PORT}/manifest.json")
    print(f"           (device default: http://m4macmini.local:{PORT}/manifest.json)")
    print(f"Drop LDRC2SIM-x.y.z.bin files here; the device sees them on next check.")
    print()
    with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nbye")
