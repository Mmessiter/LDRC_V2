#!/usr/bin/env python3
"""A FRESH SCREEN, OVER USB (23 Oct 2026, the three 16 MB boards): which board is on the cable, a copy of its factory flash,
and the right bench build flashed with the right partition table - the one time a screen needs a cable.

   python3 dev/usb_setup.py                  find the board on USB and read its chip: which build fits it
   python3 dev/usb_setup.py backup           ... and copy its whole flash to ../factory-backup/ first (256 kB at a time at
                                             230400 baud, each piece tried again on its own; ~12 min for 16 MB)
   python3 dev/usb_setup.py flash            ... and flash the bench build: usb_seed (4 MB chip) or usb_seed_full (16 MB chip);
                                             the chip is erased first when a factory copy of its size is kept
   python3 dev/usb_setup.py find             ... and look for it on the house WiFi afterwards (its /status, matched by its MAC)
   --wait                                    wait (up to 60 min) for the board to be plugged in
   --only-16mb                               leave a 4 MB board alone (an unattended run: it may be a transmitter's screen)
   --backup-once                             back up only when no factory copy of this flash size is kept yet (one is enough:
                                             the boards of one kind come with the same factory firmware)
   --first N                                 copy only the first N MB (boot loader, partition table, settings, the factory program)
   --port /dev/cu.usbserial-XXXX             when more than one serial device is plugged in

The chip decides (esptool reads its id): a 4 MB chip gets the 4 MB layout (two 1.9 MB slots, env usb_seed), a 16 MB
chip the 16 MB layout (two 6.25 MB slots, env usb_seed_full). The bench builds hold the networks of include/secrets.h
and are NEVER published; once the screen is on the WiFi, the panel that opens by itself on an empty card (or a
transmitter's "Transmitter updates") replaces them with the published firmware - STANDARD or FULL, by the slot the board
has. The firmware itself tells the two boards apart at start-up (src/board.h), so a 16 MB board flashed with the 4 MB
layout still shows a picture; only its "Check for update" would then fetch STANDARD for ever.

After the flash: the screen joins the house WiFi and answers http://<ip>/status - "board", "flash_mb", "slot" and
"build" say what it found. Card in BEFORE power (it is mounted at power-up only)."""
import glob, json, os, re, subprocess, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
BACKUPS = os.path.join(os.path.dirname(PROJECT), 'factory-backup')
PIO = os.path.expanduser('~/.platformio/penv/bin/pio')
ESPTOOL = os.path.expanduser('~/.platformio/packages/tool-esptoolpy/esptool.py')
PYTHON = os.path.expanduser('~/.platformio/penv/bin/python3')
MB = 1024 * 1024

def say(*a): print(*a, flush=True)

def ports():   # the screens' USB chip is a CH340: macOS names it usbserial (Apple's driver) or wchusbserial (WCH's). Never a Teensy (usbmodem).
    return sorted(glob.glob('/dev/cu.usbserial*') + glob.glob('/dev/cu.wchusbserial*'))

def esptool(port, args, baud=460800, after='hard_reset', timeout=900):
    cmd = [PYTHON, ESPTOOL, '--chip', 'esp32s3', '--port', port, '--baud', str(baud), '--before', 'default_reset', '--after', after] + list(args)
    try: r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    except subprocess.TimeoutExpired: return 1, f'(no answer in {timeout} s)'
    return r.returncode, r.stdout

def read_chip(port):
    code, out = esptool(port, ['flash_id'], timeout=90)
    if code: return None, out
    g = lambda rx: (re.search(rx, out) or [None, None])[1]
    size = g(r'Detected flash size: (\d+)MB')
    if not size: return None, out
    return {'chip': g(r'Chip is ([^\n]+)') or '?', 'features': g(r'Features: ([^\n]+)') or '', 'mac': g(r'MAC: ([0-9a-fA-F:]+)') or '', 'mb': int(size)}, out

PIECE = 256 * 1024   # (23 Oct 2026: at 460800 baud this Mac's CH340 driver lost bytes in the first MB - 'Corrupt data' - so small pieces at 230400, each tried again by itself)
def backup(port, chip, first_mb=0):
    os.makedirs(BACKUPS, exist_ok=True)
    mb, mac = chip['mb'], chip['mac'].replace(':', '')
    upto = min(first_mb, mb) if first_mb else mb
    name = os.path.join(BACKUPS, f'factory_{mb}MB_{mac or "unknown"}' + (f'_first{upto}MB' if upto < mb else '') + '.bin')
    if os.path.exists(name) and os.path.getsize(name) == upto * MB: say(f'  factory copy already kept: {name}'); return port
    say(f'Copying ' + (f'the first {upto} MB' if upto < mb else f'the whole flash ({mb} MB)') + f' to {name}, {PIECE // 1024} kB at a time ...')
    parts, t0, n = [], time.time(), upto * MB // PIECE
    for i in range(n):
        piece = f'{name}.part{i:03d}'
        if os.path.exists(piece) and os.path.getsize(piece) == PIECE: parts.append(piece); continue   # (copied by a run that was stopped: kept)
        for baud in (230400, 230400, 230400, 115200, 115200):
            code, out = esptool(port, ['read_flash', hex(i * PIECE), hex(PIECE), piece], baud=baud, after='no_reset', timeout=300)
            if code == 0 and os.path.exists(piece) and os.path.getsize(piece) == PIECE: break
            say(f'    piece {i + 1} at {baud} baud failed: {out.strip().splitlines()[-1] if out.strip() else "?"} - again')
            time.sleep(2)
            if not os.path.exists(port) and ports(): port = ports()[0]; say(f'    (the board is on {port} now)')
        else:
            for p in parts + [piece]:
                if os.path.exists(p): os.remove(p)
            sys.exit(f'FAILED: piece {i + 1} of the flash could not be read. Nothing was changed on the board.')
        parts.append(piece)
        if (i + 1) % 4 == 0 or i + 1 == n: say(f'  {(i + 1) * PIECE // MB:2d} of {upto} MB  ({int(time.time() - t0)} s)')
    with open(name, 'wb') as f:
        for p in parts: f.write(open(p, 'rb').read()); os.remove(p)
    if os.path.getsize(name) != upto * MB: os.remove(name); sys.exit('FAILED: the factory copy is not whole')
    say(f'  kept in {int(time.time() - t0)} s: {name}')
    return port   # (it may have moved to another USB port meanwhile)

def flash(port, chip):
    if not os.path.exists(port) and ports(): port = ports()[0]; say(f'  (the board is on {port} now)')
    env = 'usb_seed_full' if chip['mb'] >= 16 else 'usb_seed'
    kept = glob.glob(os.path.join(BACKUPS, f'factory_{chip["mb"]}MB_*.bin'))
    if kept:   # the factory firmware is safe: start from a clean chip (no old settings store, no old crash record in the coredump area)
        say('Erasing the chip (a factory copy is kept) ...')
        code, out = esptool(port, ['erase_flash'], after='no_reset', timeout=300)
        if code: sys.exit(out[-1500:] + '\nFAILED: the erase (the board still has its factory firmware, or part of it: flash again)')
    say(f'Flashing {env}: boot loader, partition table, the bench build ...')
    r = subprocess.run([PIO, 'run', '-e', env, '-t', 'upload', '--upload-port', port], cwd=PROJECT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode: sys.exit(r.stdout[-3000:] + '\nFAILED: the flash')
    say('  flashed; the screen starts now')

def lan():
    iface = re.search(r'interface: (\S+)', subprocess.run(['route', '-n', 'get', 'default'], stdout=subprocess.PIPE, text=True).stdout)
    ip = subprocess.run(['ipconfig', 'getifaddr', iface.group(1)], stdout=subprocess.PIPE, text=True).stdout.strip() if iface else ''
    return ip.rsplit('.', 1)[0] if ip.count('.') == 3 else '192.168.1'

def norm_mac(m): return ':'.join('%02x' % int(x, 16) for x in m.split(':')) if m and m.count(':') == 5 else ''

def status(ip, timeout=1.5):
    try:
        with urllib.request.urlopen(f'http://{ip}/status', timeout=timeout) as r: return json.loads(r.read().decode('latin-1'))
    except Exception: return None

def find(chip, wait_s=150):
    net, want = lan(), norm_mac(chip['mac'])
    say(f'Looking for the screen (MAC {want}) on {net}.x ...')
    t0 = time.time()
    while time.time() - t0 < wait_s:
        with ThreadPoolExecutor(64) as ex:
            found = [(ip, s) for ip, s in zip([f'{net}.{n}' for n in range(1, 255)], ex.map(status, [f'{net}.{n}' for n in range(1, 255)])) if s and 'fw' in s]
        for ip, s in found:
            arp = re.search(r' at ([0-9a-f:]+) ', subprocess.run(['arp', '-n', ip], stdout=subprocess.PIPE, text=True).stdout)
            if (arp and norm_mac(arp.group(1)) == want) or (s.get('board') == 'ips16' and s.get('fw', '').endswith('bench')):
                say(f'  FOUND at {ip} after {int(time.time() - t0)} s')
                keys = ('fw', 'board', 'flash_mb', 'image_mb', 'slot', 'build', 'sd', 'touch', 'psram', 'heap', 'rssi', 'page', 'rst', 'sys')
                say('  ' + json.dumps({k: s.get(k) for k in keys}))
                open(os.path.join(HERE, '..', '.newscreen_ip'), 'w').write(ip + '\n')
                return ip
        time.sleep(5)
    say('  not found on the WiFi (yet): is it showing its start-up line? Is the house WiFi in include/secrets.h?')
    return None

def main():
    args = sys.argv[1:]
    port = None
    if '--port' in args: i = args.index('--port'); port = args[i + 1]; del args[i:i + 2]
    first_mb = 0
    if '--first' in args: i = args.index('--first'); first_mb = int(args[i + 1]); del args[i:i + 2]
    wait, only16, once = '--wait' in args, '--only-16mb' in args, '--backup-once' in args
    steps = [a for a in args if not a.startswith('--')]
    for a in steps:
        if a not in ('backup', 'flash', 'find'): sys.exit(__doc__)
    if not port:
        t0 = time.time()
        if wait and not ports(): say('Waiting for a screen on USB (a CH340: /dev/cu.usbserial-...) ...')
        while wait and not ports() and time.time() - t0 < 3600: time.sleep(1)
        found = ports()
        if not found: sys.exit('no screen on USB: plug it in by USB-C (a data cable, not a charge-only one)')
        if len(found) > 1: sys.exit('more than one serial device: say which with --port\n  ' + '\n  '.join(found))
        port = found[0]
        if wait: time.sleep(2)                                   # (the driver and the board's own start-up settle)
    say(f'Reading the chip on {port} ...')
    chip, out = read_chip(port)
    if not chip: sys.exit(out[-1500:] + '\nFAILED: the chip did not answer (a charge-only cable? the wrong port?)')
    mb = chip['mb']
    board = 'the 16 MB twin (Elecrow DLE06050B: pixel clock IO42, speaker bit clock IO0)' if mb >= 16 else 'a CrowPanel 5.0 (DIS07050H: pixel clock IO0, speaker bit clock IO42)'
    say(f'  {chip["chip"]}; {chip["features"]}\n  flash {mb} MB, MAC {chip["mac"]}\n  => {board}\n  => env {"usb_seed_full (the 16 MB layout)" if mb >= 16 else "usb_seed (the 4 MB layout)"}')
    if 'PSRAM 8MB' not in chip['features']: say('  NOTE: the chip does not say "PSRAM 8MB": this firmware needs the 8 MB PSRAM of an N4R8 / N16R8')
    if only16 and mb < 16:
        say('A 4 MB board: left alone (--only-16mb). It may be a transmitter\'s screen; flash it by hand if it is a new one.'); return
    if mb not in (4, 16): sys.exit(f'a {mb} MB chip: neither of the two boards - nothing done')
    if 'backup' in steps:
        if once and glob.glob(os.path.join(BACKUPS, f'factory_{mb}MB_*.bin')): say(f'  a factory copy of a {mb} MB board is kept already: not copied again')
        else: port = backup(port, chip, first_mb)
    if 'flash' in steps: flash(port, chip)
    if 'find' in steps: find(chip)
    if not steps: say('Nothing changed. Add "flash" to flash it, "backup" to copy its factory flash first, "find" to look for it on the WiFi.')

if __name__ == '__main__':
    main()
