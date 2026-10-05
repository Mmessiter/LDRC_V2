#!/usr/bin/env python3
"""The transmitter's Teensy, updated through its screen over WiFi (Transmitter Version 1B).

   dev/teensy_ota.py hello                       who is there: the Teensy's firmware version and state
   dev/teensy_ota.py install [package]           firmware: keep the models, send, install, restart, check, confirm
                                                 (package defaults to TXV1B/dev/out/TXFW.BIN - make it with TXV1B/dev/make_fw_package.py)
   dev/teensy_ota.py help-files [folder]         the help texts (default: TXV1B/"Help files for SD") to /help on the Teensy's card
   dev/teensy_ota.py put LOCAL /remote/path      one file to the Teensy's card       (--user to replace the pilot's own data)
   dev/teensy_ota.py get /remote/path LOCAL      one file from the Teensy's card
   dev/teensy_ota.py backup [folder]             the pilot's own files to the screen's card AND to the Mac: models.dat (the models and
                                                 the transmitter's settings) and every *.MOD of /mod, a new folder each time; and
                                                 the logs of /log, into one folder that grows (only what is new is fetched).
   dev/teensy_ota.py sets                        the copies on the screen's card (one is made before every firmware update)
   dev/teensy_ota.py restore "SET"               put one of them back on the Teensy's card (models.dat and its *.MOD files)
   dev/teensy_ota.py list [/folder]              what is in a folder of the Teensy's card
   dev/teensy_ota.py rollback                    put the previous firmware back
   dev/teensy_ota.py confirm                     accept the firmware that is running (clears "rolledback")
   dev/teensy_ota.py status                      the last job's story
   dev/teensy_ota.py perf                        where the time went while a model was connected (B15+): fetches /PERF.TXT
                                                 (written when the link opens) to TXV1B/dev/perf/, keeps it, and prints it

   SCREEN=192.168.1.195 (the default) is the screen. Nothing is sent while a model is connected (or was a minute ago),
   nor while the transmitter's radios must be off (the safety off; or, with no safety switch defined, the motor on).
   Every job ends with one line: DONE ... or FAILED at <stage>: <why>. Exit status 0 only for DONE.

   THE WORKSHOP DOOR. A screen that runs published firmware answers none of this until its door is opened: hold the
   TOP RIGHT corner of the screen for three seconds, while it is on the WiFi (it stays open on that network).
   Bench builds (pio run -e ota_dev) have it open always.

   A copy on the Mac is never emptied or written over by a file that is not the same file grown: what the Mac held
   stays, as <name>.older."""
import sys, os, json, time, subprocess, datetime, urllib.request, urllib.parse, urllib.error

HOST = os.environ.get('SCREEN', '192.168.1.195')
TXV1B = os.path.expanduser('~/Documents/GitHub/TXV1B')

def get(path, timeout=20):
    try: return urllib.request.urlopen(f'http://{HOST}{path}', timeout=timeout).read()
    except urllib.error.HTTPError as e: sys.exit(f'refused: {e.read().decode() or e.reason}')
def post(path, **args):
    q = ('?' + urllib.parse.urlencode(args)) if args else ''
    r = urllib.request.Request(f'http://{HOST}{path}{q}', data=b'', headers={'Content-Type': 'text/plain', 'X-LDRC': '1'})
    try: return urllib.request.urlopen(r, timeout=30).read().decode()
    except urllib.error.HTTPError as e: sys.exit(f'refused: {e.read().decode() or e.reason}')
def upload(local, remote):
    subprocess.run(['curl', '-s', '-S', '-f', '-H', 'X-LDRC: 1', '-F', f'file=@{local}', f'http://{HOST}/put?path={urllib.parse.quote(remote)}'], check=True, stdout=subprocess.DEVNULL)

def keep_on_mac(to, data):
    """`data` becomes the file `to`. What the Mac holds under that name is never emptied and never lost: the new file
       is written whole beside it first; if the Mac's file is not the beginning of the new one (a log that has grown),
       it stays, as <name>.older, .older2 ..."""
    part = to + '.part'
    with open(part, 'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    if os.path.getsize(part) != len(data): os.remove(part); sys.exit(f'{to}: the Mac did not keep what was written (is the disk full?)')
    if os.path.exists(to):
        held = open(to, 'rb').read()
        if held == data: os.remove(part); return False
        if not data.startswith(held):
            n = 1
            while os.path.exists(to + '.older' + (str(n) if n > 1 else '')): n += 1
            os.replace(to, to + '.older' + (str(n) if n > 1 else ''))
    os.replace(part, to)
    return True

def fetch_folder(remote, local, only_new=False):
    """A folder of the screen's card, and its folders, to the Mac. Returns how many files were fetched.
       only_new: a file the Mac holds in the same size is left alone (the logs: a hundred files that never change)."""
    os.makedirs(local, exist_ok=True); n = 0
    for line in get('/ls?path=' + urllib.parse.quote(remote)).decode().splitlines():
        if not line.strip(): continue
        if line.endswith('/'): n += fetch_folder(remote + '/' + line[:-1], os.path.join(local, line[:-1]), only_new); continue
        name, size = line.rsplit(' ', 1)
        if name.endswith(('.part', '.old', '.new')): continue          # a file on its way, or one moved aside for a moment
        to = os.path.join(local, name)
        if only_new and os.path.exists(to) and os.path.getsize(to) == int(size): continue
        data = get('/file?path=' + urllib.parse.quote(remote + '/' + name), timeout=120)
        if len(data) != int(size): sys.exit(f'{remote}/{name}: {len(data)} bytes arrived, the screen\'s card holds {size}. The copy on the Mac was not touched.')
        if keep_on_mac(to, data): n += 1
    return n

def follow():
    """Print the job's log as it grows; return True for DONE."""
    shown = 0; last = ''
    while True:
        try: s = json.loads(urllib.request.urlopen(f'http://{HOST}/teensy/status', timeout=20).read())
        except Exception as e:                       # the screen is busy or briefly away: keep asking
            time.sleep(1); continue
        noted = s.get('noted', len(s['log']))        # how many lines the job has written in all (the screen keeps the first 40 and the last 360)
        fresh = min(noted - shown, len(s['log']))
        if fresh > 0:
            for line in s['log'][-fresh:]: print(line)
        shown = noted
        if s['running']:
            bar = ''
            if s['size']: bar = f"  {100 * s['done'] // s['size']:3d} %"
            now = f"   ... {s['stage']}{bar}"
            if now != last: print(now, end='\r'); last = now
            time.sleep(0.5); continue
        print(' ' * 78, end='\r')
        if s['repeats']: print(f"          ({s['repeats']} requests had to be repeated)")
        for line in s.get('warnings', []): print('  NOTE:', line)
        if s.get('settings'): print('  the model\'s settings, as the firmware now running reads them:', s['settings'])
        return s['finished']

def main():
    a = sys.argv[1:]
    cmd = a[0] if a else 'status'
    if cmd == 'status':
        s = json.loads(get('/teensy/status'))
        for line in s['log']: print(line)
        print('running:' if s['running'] else 'last job:', s['stage'] if s['running'] else (s['result'] or 'none yet'))
        if s['peer']: print('transmitter:', s['peer'])
        return 0
    if cmd == 'hello': post('/teensy/hello')
    elif cmd == 'install':
        pkg = a[1] if len(a) > 1 else os.path.join(TXV1B, 'dev', 'out', 'TXFW.BIN')
        head = open(pkg, 'rb').read(64)
        if head[:8] != b'LDRCFW01': sys.exit(f'{pkg} is not a firmware package (make one with TXV1B/dev/make_fw_package.py)')
        print(f"package {pkg}: {head[16:48].split(bytes(1))[0].decode()}, {os.path.getsize(pkg) // 1024} kB - to the screen's card ...")
        upload(pkg, '/teensy/TXFW.BIN')
        print(post('/teensy/install', package='/teensy/TXFW.BIN'))
    elif cmd == 'help-files':
        folder = a[1] if len(a) > 1 else os.path.join(TXV1B, 'Help files for SD')
        names = sorted(n for n in os.listdir(folder) if n.upper().endswith('.TXT'))
        print(f"{len(names)} help files to the screen's card ...")
        for n in names: upload(os.path.join(folder, n), '/teensy/sd/help/' + n.upper())
        print(post('/teensy/sync', dir='/teensy/sd'))
    elif cmd == 'put':
        user = '--user' in a; a = [x for x in a if x != '--user']
        upload(a[1], '/teensy/one/' + os.path.basename(a[2]))
        print(post('/teensy/put', local='/teensy/one/' + os.path.basename(a[2]), remote=a[2], **({'user': '1'} if user else {})))
    elif cmd == 'backup':
        folder = a[1] if len(a) > 1 else os.path.expanduser('~/Documents/LDRC backups')
        where = post('/teensy/keep')                      # the folder on the screen's card
        print('a copy on the screen\'s card:', where)
        if not follow(): return 1
        out = os.path.join(folder, datetime.datetime.now().strftime('%Y-%m-%d %H%M ') + os.path.basename(where))
        n = fetch_folder(where, out)
        logs = fetch_folder('/teensy/backup/log', os.path.join(folder, 'log'), only_new=True)     # one folder of logs that grows
        print(f'{n} files on the Mac too: {out}\n{logs} logs new on the Mac: {os.path.join(folder, "log")}')
        return 0 if n else 1
    elif cmd == 'sets':
        print(get('/teensy/sets').decode(), end='')
        return 0
    elif cmd == 'restore':
        if len(a) < 2: sys.exit('which copy? dev/teensy_ota.py sets  shows them')
        print(post('/teensy/restore', set=a[1]))
    elif cmd == 'list':
        print(post('/teensy/list', dir=a[1] if len(a) > 1 else '/'))
        if not follow(): return 1
        for e in json.loads(get('/teensy/status'))['entries']: print(f"  {e['name'] + ('/' if e['dir'] else ''):32s} {'' if e['dir'] else e['size']}")
        return 0
    elif cmd == 'get':
        if True:
            remote, out = a[1], a[2]
        print(post('/teensy/get', remote=remote, local='/teensy/fetched/' + os.path.basename(remote)))
        if not follow(): return 1
        keep_on_mac(out, get('/file?path=' + urllib.parse.quote('/teensy/fetched/' + os.path.basename(remote)), timeout=60))
        print(f'{out}  ({os.path.getsize(out)} bytes)')
        return 0
    elif cmd == 'perf':
        # The link opens (which writes the report on the Teensy's card), then the report is fetched and kept.
        print(post('/teensy/get', remote='/PERF.TXT', local='/teensy/fetched/PERF.TXT'))
        if not follow(): return 1
        folder = os.path.join(TXV1B, 'dev', 'perf'); os.makedirs(folder, exist_ok=True)
        out = os.path.join(folder, datetime.datetime.now().strftime('PERF-%Y-%m-%d-%H%M.txt'))
        keep_on_mac(out, get('/file?path=' + urllib.parse.quote('/teensy/fetched/PERF.TXT'), timeout=60))
        print(open(out, encoding='latin-1').read())
        print(out)
        return 0
    elif cmd == 'rollback': print(post('/teensy/rollback'))
    elif cmd == 'confirm': print(post('/teensy/confirm'))
    else: sys.exit(__doc__)
    return 0 if follow() else 1

if __name__ == '__main__':
    sys.exit(main())
