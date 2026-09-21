#!/usr/bin/env python3
"""Print an App Store Connect API token (ES256 JWT).

    asc_token.py <KEY_ID> <ISSUER_ID> [p8 path]

Uses /usr/bin/openssl and the standard library only. The Swift version needs
`xcrun`, which stops dead whenever Xcode wants a new licence agreed - that
silenced the review watcher overnight on 2026-09-21. Nothing here can.
"""
import base64, json, subprocess, sys, time, os

def b64(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def der_to_raw(der):
    """DER SEQUENCE{INTEGER r, INTEGER s} -> the 64 raw bytes JWS wants."""
    if der[0] != 0x30: raise ValueError("not a DER sequence")
    i = 2 + (2 if der[1] & 0x80 else 0)          # skip long-form length if present
    out = b""
    for _ in range(2):
        if der[i] != 0x02: raise ValueError("expected INTEGER")
        ln = der[i + 1]; v = der[i + 2:i + 2 + ln]; i += 2 + ln
        v = v.lstrip(b"\x00")                     # DER sign byte
        out += v.rjust(32, b"\x00")
    return out

def token(key_id, issuer, p8):
    now = int(time.time())
    head = json.dumps({"alg": "ES256", "kid": key_id, "typ": "JWT"}, separators=(",", ":"))
    load = json.dumps({"iss": issuer, "iat": now, "exp": now + 1200,
                       "aud": "appstoreconnect-v1"}, separators=(",", ":"))
    signing = b64(head.encode()) + "." + b64(load.encode())
    der = subprocess.run(["/usr/bin/openssl", "dgst", "-sha256", "-sign", p8],
                         input=signing.encode(), capture_output=True, check=True).stdout
    return signing + "." + b64(der_to_raw(der))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: asc_token.py <KEY_ID> <ISSUER_ID> [p8]")
    k, iss = sys.argv[1], sys.argv[2]
    p8 = sys.argv[3] if len(sys.argv) > 3 else \
         os.path.expanduser(f"~/.appstoreconnect/private_keys/AuthKey_{k}.p8")
    print(token(k, iss, p8))
