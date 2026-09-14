#!/usr/bin/env python3
"""Warn when the web pages have changed but the phone apps still ship the old ones.

The apps do NOT fetch pages from the receiver: BleSchemeHandler serves them from
a copy bundled inside the app (RXV2App/webroot, and the Android assets). So a
page fix published to the receiver's LittleFS reaches WiFi users and NOBODY on a
phone until the apps are rebuilt and republished.

That cost a real bug on 2026-09-14: 0.9.711 fixed View channels starving its own
Bluetooth stream, the receiver got it, and the iPhone kept the old page — so the
fix appeared to do nothing.

Run after dev/publish_website.sh. Exits 1 if they differ, so it is usable in a
chain; prints exactly which files.
"""
import hashlib, pathlib, sys, gzip

ROOT = pathlib.Path(__file__).resolve().parent.parent          # RXV2/
DATA = ROOT / "data"
WEBROOTS = [ROOT.parent / "RXV2App" / "webroot",
            ROOT.parent / "RXV2App" / "android" / "RXV2App" / "app" / "src" / "main" / "assets" / "webroot"]

def digest(p: pathlib.Path) -> str:
    b = p.read_bytes()
    if p.suffix == ".gz":                 # the apps ship these unpacked
        try: b = gzip.decompress(b)
        except Exception: pass
    return hashlib.md5(b).hexdigest()

def canonical(name: str) -> str:
    return name[:-3] if name.endswith(".gz") else name

want = {canonical(p.name): digest(p) for p in DATA.iterdir() if p.is_file()}

bad = False
for wr in WEBROOTS:
    if not wr.exists():
        print(f"  ?  {wr} missing — skipped"); continue
    have = {p.name: digest(p) for p in wr.iterdir() if p.is_file()}
    diff  = sorted(n for n, h in want.items() if have.get(n) != h)
    extra = sorted(set(have) - set(want))
    if diff or extra:
        bad = True
        print(f"  !! {wr.relative_to(ROOT.parent)} is OUT OF STEP with RXV2/data")
        for n in diff[:12]:
            print(f"       differs/missing: {n}")
        if len(diff) > 12: print(f"       ... and {len(diff)-12} more")
        for n in extra[:5]: print(f"       stale extra:     {n}")
    else:
        print(f"  ok {wr.relative_to(ROOT.parent)} matches RXV2/data")

if bad:
    print()
    print("  The phone apps bundle their own pages and NEVER fetch them from the")
    print("  receiver, so this difference means your page fix reaches WiFi users")
    print("  only. Bump the app versions and run RXV2App/android/publish_app.sh")
    print("  (it re-syncs both webroots), then rebuild and install the iOS app.")
    sys.exit(1)
