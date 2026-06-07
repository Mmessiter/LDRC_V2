#!/usr/bin/env python3
"""
Stage LDRC2SIM firmware releases into the messiter.com website tree.

Mirrors the layout the RXV2 / ReedsV2 projects use for their OTA areas, so the
device's Firmware page can pull updates from the public site instead of only the
local dev server. Scans dev/LDRC2SIM-*.bin and, for each, writes

    NewWebSite/public_html/ldrc2sim/release/vX.Y.Z/firmware.bin

then regenerates release/manifest.json (newest-first) in the shape the device's
/api/firmware/check expects:

    { "versions": [ { "name":  "LDRC2SIM-1.0.11",
                      "url":   "https://messiter.com/ldrc2sim/release/v1.0.11/firmware.bin",
                      "size":  1008016,
                      "mtime": 1733570000,
                      "notes": "..." }, ... ] }

The device only reads `name` (must parse as LDRC2SIM-x.y.z) and `url`; size /
mtime / notes are for humans and the website. Keep notes SHORT — the whole
manifest is loaded into the ESP32's RAM on every check. Per-release notes are
read from dev/release_notes.json (a { "LDRC2SIM-x.y.z": "note" } map) if present.

After staging, push to the live site with dev/publish_website.sh.

Usage:
    python3 dev/stage_website.py
"""
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent.resolve()                  # .../LDRC2SIM/dev
ROOT = HERE.parent                                      # .../LDRC2SIM
PRODUCT = "ldrc2sim"
SITE = "https://messiter.com"
STAGE = ROOT / "NewWebSite" / "public_html" / PRODUCT / "release"
NOTES_FILE = HERE / "release_notes.json"
VER_RE = re.compile(r"LDRC2SIM-(\d+)\.(\d+)\.(\d+)")


def ver_tuple(name: str):
    m = VER_RE.search(name)
    return (int(m[1]), int(m[2]), int(m[3])) if m else (0, 0, 0)


def main() -> int:
    bins = sorted(HERE.glob("LDRC2SIM-*.bin"))
    if not bins:
        print("No dev/LDRC2SIM-*.bin files found — nothing to stage.", file=sys.stderr)
        return 1

    notes = {}
    if NOTES_FILE.exists():
        notes = json.loads(NOTES_FILE.read_text())

    STAGE.mkdir(parents=True, exist_ok=True)
    versions = []
    for b in bins:
        name = b.stem                                   # LDRC2SIM-1.0.11
        maj, mnr, pat = ver_tuple(name)
        if (maj, mnr, pat) == (0, 0, 0):
            print(f"  skip (unparseable name): {b.name}")
            continue
        vdir = STAGE / f"v{maj}.{mnr}.{pat}"
        vdir.mkdir(parents=True, exist_ok=True)
        dest = vdir / "firmware.bin"
        # Copy only when the bytes differ, so unchanged releases keep a stable
        # mtime (and lftp skips re-uploading them).
        if not dest.exists() or dest.stat().st_size != b.stat().st_size:
            shutil.copy2(b, dest)
        st = dest.stat()
        versions.append({
            "name": name,
            "url": f"{SITE}/{PRODUCT}/release/v{maj}.{mnr}.{pat}/firmware.bin",
            "size": st.st_size,
            "mtime": int(st.st_mtime),
            "notes": notes.get(name, ""),
            "_v": (maj, mnr, pat),
        })

    versions.sort(key=lambda v: v["_v"], reverse=True)
    for v in versions:
        v.pop("_v")

    manifest = STAGE / "manifest.json"
    manifest.write_text(json.dumps({"versions": versions}, indent=2) + "\n")

    print(f"Staged {len(versions)} version(s) -> {STAGE}")
    if versions:
        print(f"Newest:   {versions[0]['name']}")
    print(f"Manifest: {manifest}")
    print("Next:     dev/publish_website.sh   (uploads to messiter.com)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
