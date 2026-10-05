#!/usr/bin/env python3
"""Turn a Teensy build (Intel HEX) into an update package for Transmitter Version 1B.

   dev/make_fw_package.py                      # the PlatformIO build -> dev/out/TXFW.BIN
   dev/make_fw_package.py some.hex -o out.bin --version "2.5.7 A 30/09/26"

   The package: a 64-byte header (magic LDRCFW01, size, CRC-32, version, target), then the image exactly
   as it sits in the Teensy's flash from 0x60000000, gaps filled with FF. The Teensy checks all of it
   again (lib/LdrcLink checkFirmwarePackage) before it touches its flash."""
import argparse, os, re, struct, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', 'TransmitterCode')
BASE = 0x60000000
TARGET = b'fw_teensy41'
STAGE_MAX = 0x003C0000

def read_hex(path):
    data = {}; upper = 0
    for n, line in enumerate(open(path), 1):
        line = line.strip()
        if not line: continue
        if line[0] != ':': sys.exit(f'{path}:{n}: not an Intel HEX line')
        raw = bytes.fromhex(line[1:])
        if sum(raw) & 0xFF: sys.exit(f'{path}:{n}: checksum wrong')
        count, addr, kind, body = raw[0], (raw[1] << 8) | raw[2], raw[3], raw[4:-1]
        if len(body) != count: sys.exit(f'{path}:{n}: length wrong')
        if kind == 0:
            for i, b in enumerate(body): data[upper + addr + i] = b
        elif kind == 1: break
        elif kind == 2: upper = ((body[0] << 8) | body[1]) << 4
        elif kind == 4: upper = ((body[0] << 8) | body[1]) << 16
        elif kind in (3, 5): pass
        else: sys.exit(f'{path}:{n}: record type {kind} not understood')
    return data

def version_from_source():
    text = open(os.path.join(ROOT, 'include', '1Definitions.h'), encoding='latin1').read()
    def grab(name):
        m = re.search(r'#define\s+' + name + r'\s+(?:"([^"\n]*)"|(\S+))', text)
        if not m: sys.exit(f'{name} not found in 1Definitions.h')
        return (m.group(1) if m.group(1) is not None else m.group(2)).strip()
    return f"{grab('TXVERSION_MAJOR')}.{grab('TXVERSION_MINOR')}.{grab('TXVERSION_MINIMUS')} {grab('TXVERSION_EXTRA')}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('hex', nargs='?', default=os.path.join(ROOT, '.pio', 'build', 'teensy41', 'firmware.hex'))
    ap.add_argument('-o', '--out', default=os.path.join(HERE, 'out', 'TXFW.BIN'))
    ap.add_argument('--version', default=None, help='default: TXVERSION_* in 1Definitions.h')
    a = ap.parse_args()
    version = a.version or version_from_source()
    if len(version.encode()) > 31: sys.exit('version text longer than 31 characters')
    data = read_hex(a.hex)
    lo, hi = min(data), max(data) + 1
    if lo != BASE: sys.exit(f'the image starts at {lo:#x}, not {BASE:#x}: not a Teensy 4.1 build')
    size = (hi - lo + 3) & ~3
    if size > STAGE_MAX: sys.exit(f'{size} bytes will not fit the staging area ({STAGE_MAX})')
    image = bytearray(b'\xFF' * size)
    for addr, b in data.items(): image[addr - lo] = b
    if TARGET not in image: sys.exit(f'{TARGET.decode()} is not in the image: this build has no LinkMode.h, it could never be updated again')
    if version.encode() not in image: sys.exit(f'the version text "{version}" is not in the image: is the build up to date with 1Definitions.h?')
    crc = zlib.crc32(bytes(image)) & 0xFFFFFFFF
    header = b'LDRCFW01' + struct.pack('<II', size, crc) + version.encode().ljust(32, b'\0') + TARGET.ljust(16, b'\0')
    assert len(header) == 64
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, 'wb').write(header + image)
    print(f'{a.out}\n  version  {version}\n  image    {size} bytes ({size / 1024:.0f} kB), CRC-32 {crc:08X}\n  package  {64 + size} bytes')

if __name__ == '__main__':
    main()
