#!/usr/bin/env python3
"""Refuse a filesystem image that does not hold every page.

Why this exists (0.9.742, 2026-09-17): `pio run -t buildfs` printed

    lfs_write error(-28): File system is full.
    error adding file!
    [FAILED]

and LEFT A PARTIAL littlefs.bin BEHIND. That image still looked plausible —
right size, newest pages inside — so it would have flashed onto the fleet
with some files simply missing. A page that is not there is a page that
404s on the chip: the receiver comes up, the app opens, and one screen is
gone. LittleFS has been close to full for months (the 3D helicopter's
three.min.js is 166 kB of it), so this is a trap that will spring again.

Run it after every buildfs. It checks two things:
  1. the image is newer than every file in data/ (not a stale leftover), and
  2. every file name in data/ appears inside the image.

Exit 1 and say what is missing if either fails.
"""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
IMAGE = os.path.join(ROOT, ".pio", "build", "xiao_s3_ota", "littlefs.bin")


def fs_listing(blob):
    """{name: size} read out of the image by mklittlefs, or None."""
    tool = os.path.expanduser("~/.platformio/packages/tool-mklittlefs/mklittlefs")
    if not os.path.exists(tool):
        return None
    try:
        out = subprocess.run([tool, "-l", "-b", "4096", "-p", "256",
                              "-s", str(len(blob)), IMAGE],
                             capture_output=True, text=True, timeout=60)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    found = {}
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].strip().isdigit():
            found[parts[1].lstrip("/")] = int(parts[0].strip())
    return found or None


def main() -> int:
    if not os.path.exists(IMAGE):
        print("NO IMAGE: %s — run `pio run -e xiao_s3_ota -t buildfs`" % IMAGE)
        return 1

    blob = open(IMAGE, "rb").read()
    img_mtime = os.path.getmtime(IMAGE)

    files = [f for f in sorted(glob.glob(os.path.join(DATA, "*")))
             if os.path.isfile(f)]
    if not files:
        print("NO FILES in %s" % DATA)
        return 1

    stale = [os.path.basename(f) for f in files
             if os.path.getmtime(f) > img_mtime + 1]
    # Read the image with the tool that made it — mklittlefs -l walks the
    # real directory structure, so it cannot be fooled the way scanning for
    # byte patterns can (LittleFS splits a file across non-contiguous 4 kB
    # blocks, so a file IS there without its bytes ever appearing in one run).
    listing = fs_listing(blob)
    if listing is None:
        print("Could not list %s with mklittlefs — is tool-mklittlefs installed?" % IMAGE)
        return 1
    on_disk = {os.path.basename(f): os.path.getsize(f) for f in files}
    missing = []
    for name, size in sorted(on_disk.items()):
        if name not in listing:
            missing.append("%s (not in the image)" % name)
        elif listing[name] != size:
            missing.append("%s (%d bytes on the chip, %d in data/)"
                           % (name, listing[name], size))
    for name in sorted(set(listing) - set(on_disk)):
        missing.append("%s (in the image but not in data/ — stale)" % name)

    if stale:
        print("STALE IMAGE — these are newer than littlefs.bin:")
        for n in stale:
            print("   %s" % n)
        print("Rebuild it: pio run -e xiao_s3_ota -t buildfs")
        return 1

    if missing:
        print("IMAGE DOES NOT MATCH data/ — %d problem(s):" % len(missing))
        for n in missing:
            print("   %s" % n)
        print("")
        print("The filesystem partition is full. buildfs may have printed")
        print("`lfs_write error(-28)` and left this partial image behind.")
        print("Free space in data/ (the .gz twins are served as-is — see")
        print("serveLittleFsFile in src/WebPages.h) and build again.")
        return 1

    total = sum(os.path.getsize(f) for f in files)
    print("ALL PASS  (%d files, %d bytes of content, image %d bytes)"
          % (len(files), total, len(blob)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
