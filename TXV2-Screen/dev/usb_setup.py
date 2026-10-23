#!/usr/bin/env python3
"""A FRESH SCREEN, OVER USB (23 Oct 2026, the three 16 MB boards): which board is on the cable, a copy of its factory flash,
and the right bench build flashed with the right partition table - the one time a screen needs a cable.

   python3 dev/usb_setup.py                  find the board on USB and read its flash chip: which build fits it
   python3 dev/usb_setup.py backup           ... and read its whole flash into ../factory-backup/ first (a 16 MB chip: ~6 min)
   python3 dev/usb_setup.py flash            ... and flash the bench build: usb_seed (4 MB chip) or usb_seed_full (16 MB chip)
   python3 dev/usb_setup.py backup flash     both, in that order
   --port /dev/cu.usbserial-XXXX             when more than one serial device is plugged in

The chip decides (esptool reads its id): a 4 MB chip gets the 4 MB layout (two 1.9 MB slots, env usb_seed), a 16 MB
chip the 16 MB layout (two 6.25 MB slots, env usb_seed_full). The bench builds hold the networks of include/secrets.h
and are NEVER published; once the screen is on the WiFi, the transmitter's "Transmitter updates" (or the panel that
opens by itself on a screen with an empty card) replaces them with the published firmware - STANDARD or FULL, by the
slot the board has. The firmware itself tells the two boards apart at start-up (src/board.h), so a 16 MB board may be
flashed with the 4 MB layout and still show a picture; only its "Check for update" would then fetch STANDARD for ever.

After the flash: the screen joins the house WiFi and answers http://<ip>/status - "board", "flash_mb", "slot" and
"build" say what it found. Card in BEFORE power (it is mounted at power-up only)."""
import glob, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
BACKUPS = os.path.join(os.path.dirname(PROJECT), 'factory-backup')
PIO = os.path.expanduser('~/.platformio/penv/bin/pio')
ESPTOOL = os.path.expanduser('~/.platformio/packages/tool-esptoolpy/esptool.py')
PYTHON = os.path.expanduser('~/.platformio/penv/bin/python')

def ports():
    return sorted(glob.glob('/dev/cu.usbserial*') + glob.glob('/dev/cu.wchusbserial*') + glob.glob('/dev/cu.usbmodem*'))

def esptool(port, *args, timeout=900):
    cmd = [PYTHON, ESPTOOL, '--chip', 'esp32s3', '--port', port, '--baud', '460800'] + list(args)
    print('  $', ' '.join(cmd))
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    return r.returncode, r.stdout

def main():
    args = sys.argv[1:]
    port = None
    if '--port' in args: i = args.index('--port'); port = args[i + 1]; del args[i:i + 2]
    for a in args:
        if a not in ('backup', 'flash'): sys.exit(__doc__)
    if not port:
        found = ports()
        if not found: sys.exit('no serial device: plug the screen in by USB-C (and give the Mac a moment)')
        if len(found) > 1: sys.exit('more than one serial device: say which with --port\n  ' + '\n  '.join(found))
        port = found[0]
    print(f'Reading the chip on {port} ...')
    code, out = esptool(port, 'flash_id', timeout=60)
    if code: sys.exit(out[-1500:] + '\nFAILED: the chip did not answer (a charge-only cable? the wrong port?)')
    chip = re.search(r'Chip is (\S+)', out); size = re.search(r'Detected flash size: (\d+)MB', out); mac = re.search(r'MAC: (\S+)', out)
    if not size: sys.exit(out[-1500:] + '\nFAILED: the flash size was not read')
    mb = int(size.group(1))
    env = 'usb_seed_full' if mb >= 16 else 'usb_seed'
    layout = 'the 16 MB layout: two 6.25 MB slots, default_16MB.csv' if mb >= 16 else 'the 4 MB layout: two 1.9 MB slots, min_spiffs.csv'
    board = 'the 16 MB twin (Elecrow DLE06050B, pixel clock IO42, speaker bit clock IO0)' if mb >= 16 else 'a CrowPanel 5.0 (DIS07050H, pixel clock IO0, speaker bit clock IO42)'
    print(f'  {chip.group(1) if chip else "?"}, flash {mb} MB, MAC {mac.group(1) if mac else "?"}\n  => {board}\n  => env {env} ({layout})')
    if 'backup' in args:
        os.makedirs(BACKUPS, exist_ok=True)
        name = os.path.join(BACKUPS, f'factory_{mb}MB_{(mac.group(1) if mac else "unknown").replace(":", "")}.bin')
        if os.path.exists(name): print(f'  backup already here: {name}')
        else:
            print(f'Reading the whole flash ({mb} MB) into {name} - about {mb * 25 // 60} min ...')
            t = time.time(); code, out = esptool(port, 'read_flash', '0', hex(mb * 1024 * 1024), name, timeout=3600)
            if code or not os.path.exists(name) or os.path.getsize(name) != mb * 1024 * 1024:
                if os.path.exists(name): os.remove(name)
                sys.exit(out[-1500:] + '\nFAILED: the backup')
            print(f'  backed up in {int(time.time() - t)} s')
    if 'flash' in args:
        print(f'Flashing {env} (bootloader, partition table, the bench build) ...')
        r = subprocess.run([PIO, 'run', '-e', env, '-t', 'upload', '--upload-port', port], cwd=PROJECT)
        if r.returncode: sys.exit('FAILED: the flash')
        print('\nDone. Power the screen with its card in; it joins the house WiFi (include/secrets.h) and answers /status:\n'
              '  curl -s http://ldrc-screen.local/status   (or the IP the router gave it)\n'
              '  "board", "flash_mb", "slot" and "build" say what it found; "touch":1 means the touch chip answered.\n'
              'With an empty card the update panel opens by itself and offers the files; a transmitter\'s "Transmitter updates"\n'
              'replaces this bench build with the published one.')
    elif 'backup' not in args: print('Nothing changed. Add "flash" to flash it, "backup" to copy its factory flash first.')

if __name__ == '__main__':
    main()
