#!/usr/bin/env python3
"""The transmitter V2 to the public repository (github.com/Mmessiter/LDRC_V2), as SNAPSHOTS.

   dev/publish_public.py            copy the two working trees into the LDRC_V2 clone and commit there
   dev/publish_public.py --push     ... and push to GitHub (main)

   TXV1B  (this repository)                       -> LDRC_V2/TXV2         the transmitter: Teensy code, help, sounds, case, circuits, HEX
   ESP32-board2/board4/nextion-emulator           -> LDRC_V2/TXV2-Screen  the screen: firmware, pages, pictures, fonts, tools, tests

   Snapshots, not history: the working repositories stay private, and nothing that was ever in them can leak. What is
   copied is listed here, by name; what is left out is listed too. Every copied file is searched for every text of the
   screen's include/secrets.h (as the release tool searches what goes to the website) and the copy is refused if one holds any.
   Run it after dev/release_v1b.py publish, so that the public copy is the release that is live."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from release_v1b import private_values, refuse_private, SCREEN, ROOT
PUBLIC = os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL')

TX_INCLUDE = ['TransmitterCode', 'Help files for SD', 'Noises', 'Circuits', 'STL files', 'Images', 'dev', 'V1B-UPDATES.md']
TX_EXCLUDE = ['.pio', '.git', '.DS_Store', '__pycache__', 'TransmitterCode/.vscode', 'dev/out', 'dev/notify.sh', 'HEX_Files/*_log.txt',
              'TransmitterCode/include/ADC-master/docs', '*.HMI', 'TransmitterCode/SD Examples/Teensy SD Example/log',
              'TransmitterCode/SD Examples/Teensy SD Example/help', 'TransmitterCode/SD Examples/Nextion SD Example', '*.workspace']
# (ADC-master/docs = 16 MB of the ADC library's generated web pages; *.HMI = the Version 1 screen's own files; the example
#  card's log folder = Malcolm's flights, its help folder = replaced by "Help files for SD" below, the Nextion example = Version 1's
#  screen; HEX_Files = Version 1's firmware (built Version 2 firmware is what messiter.com/txv1b/release serves); *.workspace =
#  Proteus session files)
# (left out on purpose: NewWebSite = the release staging; Nextion files = the Version 1 screen's HMI, in the Version 1
#  repository; ReceiverCode, Tx_sd_read, Quadcopter = Version 1 leftovers; reviews = working notes; LICENSE etc. = the
#  public repository has its own; README.md = replaced by TXV2/README.md, kept in the public repository itself)
SCREEN_INCLUDE = ['src', 'lib', 'include', 'hmi', 'sd', 'dev', 'platformio.ini']
SCREEN_EXCLUDE = ['.pio', '.DS_Store', '__pycache__', 'include/secrets.h', 'hmi/render_host/gen', 'hmi/test_*/test_*', '!hmi/test_*/test_*.cpp', 'hmi/fonts/*_aa.bin', 'hmi/fonts/*.bin', 'sd/.DS_Store']
# (the screen's card folder sd/ goes whole, its font tables included: a builder copies it to a card and is done)
KEEP_IN_PUBLIC = ['README.md', 'LICENSE']   # files of the public folders that are the public repository's own, never overwritten by the copy

def run(cmd, cwd=None): subprocess.run(cmd, cwd=cwd, check=True)
def rsync(src, dst, include, exclude):
    os.makedirs(dst, exist_ok=True)
    args = ['rsync', '-a', '--delete', '--delete-excluded', '--prune-empty-dirs']
    for k in KEEP_IN_PUBLIC: args += ['--exclude', '/' + k]
    for e in exclude: args += (['--include', e[1:]] if e.startswith('!') else ['--exclude', e])
    for i in include: args += ['--include', '/' + i + ('/***' if os.path.isdir(os.path.join(src, i)) else '')]
    args += ['--exclude', '*', src.rstrip('/') + '/', dst.rstrip('/') + '/']
    run(args)

def scan(folder, private):
    n = 0
    for d, dirs, names in os.walk(folder):
        dirs[:] = [x for x in dirs if x != '.git']
        for f in names:
            full = os.path.join(d, f); refuse_private(os.path.relpath(full, PUBLIC), open(full, 'rb').read(), private); n += 1
    return n

def main():
    push = '--push' in sys.argv
    if not os.path.isdir(os.path.join(PUBLIC, '.git')): sys.exit(f'{PUBLIC} is not the LDRC_V2 clone')
    private = private_values()
    print(f'{len(private)} private texts of the screen\'s secrets.h will be searched for')
    rsync(ROOT, os.path.join(PUBLIC, 'TXV2'), TX_INCLUDE, TX_EXCLUDE)
    rsync(SCREEN, os.path.join(PUBLIC, 'TXV2-Screen'), SCREEN_INCLUDE, SCREEN_EXCLUDE)
    # The example card gets the help texts as released (its own copy had grown old)
    rsync(os.path.join(ROOT, 'Help files for SD'), os.path.join(PUBLIC, 'TXV2', 'TransmitterCode', 'SD Examples', 'Teensy SD Example', 'help'), ['*.TXT'], ['.DS_Store'])
    n = scan(os.path.join(PUBLIC, 'TXV2'), private) + scan(os.path.join(PUBLIC, 'TXV2-Screen'), private)
    print(f'{n} files copied and searched: nothing private in any of them')
    tx = subprocess.run(['git', 'log', '-1', '--format=%s'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    sc = subprocess.run(['git', 'log', '-1', '--format=%s'], cwd=SCREEN, capture_output=True, text=True).stdout.strip()
    run(['git', 'add', '-A', 'TXV2', 'TXV2-Screen'], cwd=PUBLIC)
    changed = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=PUBLIC).returncode != 0
    if not changed: print('the public copy is already current'); return
    msg = f'TXV2 + TXV2-Screen: the transmitter as released\n\nTransmitter: {tx}\nScreen: {sc}\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n'
    run(['git', 'commit', '-q', '-m', msg], cwd=PUBLIC)
    print('committed in', PUBLIC)
    if push: run(['git', 'push', '-q', 'origin', 'HEAD:main'], cwd=PUBLIC); print('pushed to GitHub (main)')
    else: print('not pushed: dev/publish_public.py --push when it is to go public')

if __name__ == '__main__': main()
