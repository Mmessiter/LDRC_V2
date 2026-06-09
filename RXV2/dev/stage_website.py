#!/usr/bin/env python3
"""
Stage RXV2 firmware (and, when present, the matching littlefs.bin) into the
messiter.com website tree, then publish with dev/publish_website.sh.

For each dev/RXV2-x.y.z-*.bin it ensures
    NewWebSite/public_html/rxv2/release/vX.Y.Z/firmware.bin
and regenerates release/manifest.json (newest first) in the shape the receiver's
/api/firmware/check expects:

    { "versions": [ {
        "name":  "RXV2-0.9.82-tx-happy",
        "url":   "https://messiter.com/rxv2/release/v0.9.82/firmware.bin",
        "fs_url":"https://messiter.com/rxv2/release/v0.9.82/littlefs.bin",   # only if present
        "notes": "..." }, ... ] }

KEY behaviours:
- NOTES are PRESERVED from the existing manifest (the hand-written entries keep
  their text); a new version takes its note from dev/release_notes.json (name->note).
- fs_url is added automatically for any version dir that contains a littlefs.bin.
  So to ship the web UI with a release, drop the built FS image into that dir first:
      cp .pio/build/xiao_s3_ota/littlefs.bin NewWebSite/public_html/rxv2/release/vX.Y.Z/
  (The OTA installer flashes the FS too when an entry has fs_url — see WebPages.h.)

Usage:  python3 dev/stage_website.py   then   dev/publish_website.sh
"""
import json
import re
import shutil
from pathlib import Path

HERE     = Path(__file__).parent.resolve()                 # .../RXV2/dev
ROOT     = HERE.parent                                     # .../RXV2
SITE     = "https://messiter.com"
PRODUCT  = "rxv2"
RELEASE  = ROOT / "NewWebSite" / "public_html" / PRODUCT / "release"
MANIFEST = RELEASE / "manifest.json"
NOTES_FILE = HERE / "release_notes.json"
VER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def ver_of(s: str):
    m = VER_RE.search(s or "")
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def main() -> int:
    RELEASE.mkdir(parents=True, exist_ok=True)

    # 1. Preserve names + notes from the existing manifest, keyed by version tuple.
    name_by_ver, note_by_ver = {}, {}
    if MANIFEST.exists():
        for e in json.loads(MANIFEST.read_text()).get("versions", []):
            v = ver_of(e.get("url", "")) or ver_of(e.get("name", ""))
            if v:
                name_by_ver[v] = e.get("name", "")
                note_by_ver[v] = e.get("notes", "")
    new_notes = json.loads(NOTES_FILE.read_text()) if NOTES_FILE.exists() else {}

    # 2. Sync dev firmware bins -> release tree (firmware.bin per version dir).
    for b in sorted(HERE.glob("RXV2-*.bin")):
        v = ver_of(b.stem)
        if not v:
            continue
        name_by_ver[v] = b.stem                      # dev bin stem is the canonical name
        vdir = RELEASE / f"v{v[0]}.{v[1]}.{v[2]}"
        vdir.mkdir(exist_ok=True)
        dest = vdir / "firmware.bin"
        if not dest.exists() or dest.stat().st_size != b.stat().st_size:
            shutil.copy2(b, dest)

    # 3. Regenerate the manifest from every version dir in the release tree.
    versions = []
    for vdir in RELEASE.glob("v*"):
        v = ver_of(vdir.name)
        if not v or not (vdir / "firmware.bin").exists():
            continue
        tag = f"v{v[0]}.{v[1]}.{v[2]}"
        entry = {
            "name": name_by_ver.get(v) or f"RXV2-{v[0]}.{v[1]}.{v[2]}",
            "url":  f"{SITE}/{PRODUCT}/release/{tag}/firmware.bin",
        }
        if (vdir / "littlefs.bin").exists():
            entry["fs_url"] = f"{SITE}/{PRODUCT}/release/{tag}/littlefs.bin"
        entry["notes"] = note_by_ver.get(v) or new_notes.get(entry["name"], "")
        entry["_v"] = v
        versions.append(entry)

    versions.sort(key=lambda e: e["_v"], reverse=True)
    for e in versions:
        e.pop("_v")
    MANIFEST.write_text(json.dumps({"versions": versions}, indent=2) + "\n")

    fs_count = sum(1 for e in versions if "fs_url" in e)
    print(f"Staged {len(versions)} versions -> {RELEASE}")
    if versions:
        print(f"  newest: {versions[0]['name']}")
    print(f"  versions shipping a littlefs.bin (fs_url): {fs_count}")
    print("  next: dev/publish_website.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
