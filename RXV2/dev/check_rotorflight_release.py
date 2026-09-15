#!/usr/bin/env python3
"""Ask GitHub what the newest STABLE Rotorflight firmware is, and SUGGEST an update
to dev/rotorflight_latest.json. It never writes that file itself — a human looks
first, because the consequence of getting it wrong is telling a pilot to reflash.

    python3 dev/check_rotorflight_release.py

THE TRAP THIS SCRIPT EXISTS FOR: Rotorflight's release workflow does not pass
--prerelease for release/* tags, so RELEASE CANDIDATES come back with
prerelease=false and GitHub's /releases/latest will happily hand you
"release/4.6.0-RC3". Verified across all 30 current releases. The only reliable
stable filter is the tag NAME, so that is what we match:  release/<x>.<y>.<z>
and nothing else.

Version mapping, verified from the release notes and version.h at each tag:
    firmware 4.6.x  ==  "Rotorflight 2.3"  ==  MSP API 12.9
    RF minor = firmware minor - 3
"""
import json, os, re, ssl, sys, urllib.request
try:                       # PlatformIO's bundled python has no CA bundle of its own
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _CTX = ssl.create_default_context()

API   = "https://api.github.com/repos/rotorflight/rotorflight-firmware/releases"
HERE  = os.path.dirname(os.path.abspath(__file__))
LOCAL = os.path.join(HERE, "rotorflight_latest.json")
STABLE = re.compile(r"^release/(\d+)\.(\d+)\.(\d+)$")

def fetch(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "LDRC-RXV2-release-check",
    })
    with urllib.request.urlopen(req, timeout=20, context=_CTX) as r:
        return json.load(r), dict(r.headers)

def main():
    try:
        rels, hdrs = fetch(API + "?per_page=30")
    except Exception as e:
        print(f"!! could not reach GitHub: {e}")
        return 1
    rem = hdrs.get("x-ratelimit-remaining")
    if rem is not None:
        print(f"   (GitHub rate limit remaining: {rem} of {hdrs.get('x-ratelimit-limit')})")

    stable = []
    for r in rels:
        m = STABLE.match(r.get("tag_name", ""))
        if not m or r.get("draft"):
            continue
        stable.append((tuple(int(x) for x in m.groups()), r))
    if not stable:
        print("!! no stable release/x.y.z tags found — has the naming changed?")
        return 1
    stable.sort(key=lambda t: t[0], reverse=True)
    ver, rel = stable[0]
    skipped = [r.get("tag_name") for r in rels
               if not STABLE.match(r.get("tag_name", "")) and not r.get("prerelease")]

    fw   = "%d.%d.%d" % ver
    rf   = "%d.%d" % (2, ver[1] - 3)          # firmware 4.6.x == RF 2.3
    api  = 1200 + (ver[1] - 3) * 1 + 6        # see note below
    # API minor tracks the RF minor: 4.5 -> 12.8, 4.6 -> 12.9. Derive rather than
    # guess, and print it for the human to sanity-check against the release notes.
    api  = 1200 + (ver[1] + 3)
    print()
    print(f"   newest STABLE : {fw}   (Rotorflight {rf}, MSP API ~12.{ver[1] + 3})")
    print(f"   released      : {rel.get('published_at','?')[:10]}")
    print(f"   notes         : {rel.get('html_url')}")
    if skipped:
        print(f"   ignored (not release/x.y.z, and NOT flagged prerelease by GitHub):")
        for t in skipped[:4]:
            print(f"                   {t}")

    have = {}
    if os.path.exists(LOCAL):
        have = json.load(open(LOCAL))
    if have.get("firmware") == fw:
        print(f"\n   dev/rotorflight_latest.json already says {fw} — nothing to do.")
        return 0

    print(f"\n   dev/rotorflight_latest.json says {have.get('firmware','(nothing)')}.")
    print(f"   If {fw} is right, update it to:\n")
    print(json.dumps({
        "firmware": fw,
        "api": api,
        "suite": rf,
        "released": rel.get("published_at", "")[:10],
        "notes_url": rel.get("html_url", ""),
        "line": "<one plain sentence about what changed — write this yourself>",
    }, indent=2))
    print("\n   Then check LDRC.RF_API_VERIFIED in RXV2/data/app.js: if this API is")
    print("   NEWER than that, the pages will tell people to STAY PUT rather than")
    print("   upgrade, which is correct until the byte layouts are re-verified.")
    return 0

sys.exit(main())
