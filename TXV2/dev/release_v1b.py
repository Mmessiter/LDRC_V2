#!/usr/bin/env python3
"""Releases of Transmitter Version 1B for messiter.com: what the button "Check for update" finds.

   dev/release_v1b.py stage "what is new"     build both firmwares, collect EVERY file the transmitter needs,
                                              and write the release under NewWebSite/public_html/txv1b/release
   dev/release_v1b.py publish                 upload it (the files first, the description last), then fetch
                                              everything back from messiter.com and compare byte for byte
   dev/release_v1b.py status                  what is live, what is staged
   dev/release_v1b.py latest NAME             make an earlier release the latest again (withdraw a bad one), then publish
   dev/release_v1b.py purge files/X.bin ...   take files OFF the website, and out of every release that names them

   NOTHING PRIVATE GOES TO THE WEBSITE.
     1. The screen's firmware is built in a COPY of its project that has no secrets.h in it (dev/out/screen_build):
        what is not there cannot be compiled in.
     2. Every file that is to go to the website - this release's and every earlier one's - is searched for every
        text of the screen project's include/secrets.h, at stage and again at publish. One that holds any is refused.

   stage takes  --no-build         use the firmware already built (Teensy: dev/out/TXFW.BIN, screen: .pio/build/ota/firmware.bin)
                --without-screen   a release that leaves the screen's firmware as it is

   A release is four parts. The screen compares each with what the transmitter has and fetches what differs:
     teensy        the Teensy's firmware, as an update package (dev/make_fw_package.py)     compared by version
     screen        the screen's firmware                                                    compared by version
     teensy_files  the files for the Teensy's SD card: the help texts, to /help             compared by the list's checksum
     screen_files  the files for the screen's card: pages, pictures, fonts, sounds, images  compared by the list's checksum
   Never the pilot's own data: no models, no logs (the screen refuses a list that names one, and so does the Teensy).

   On the website:
     latest.txt                  what the screen reads: key=value lines, the last one end=1
     recent.txt                  the latest release and the three before it that are whole: what "Earlier versions" offers
     manifest.json               the same for people and other tools, with the history of releases
     v/<release>/release.txt     each release's own description (for going back)
     files/<CRC32>-<size>.bin    every file, under the name of its content: uploaded once, shared by all releases"""
import argparse, datetime, json, os, re, shutil, subprocess, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEENSY = os.path.join(ROOT, 'TransmitterCode')
SCREEN = os.path.expanduser('~/Documents/GitHub/ESP32-board2/board4/nextion-emulator')
SITE = os.path.join(ROOT, 'NewWebSite', 'public_html')
REL = os.path.join(SITE, 'txv1b', 'release')
BASE = 'https://messiter.com/txv1b/release/'
FTP_CREDENTIALS = os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/RXV2/dev/ftp_credentials.sh')   # exports LFTP_PASSWORD, LDRC_FTP_HOST, LDRC_FTP_USER
PIO = shutil.which('pio') or os.path.expanduser('~/.platformio/penv/bin/pio')

def crc(b): return zlib.crc32(b) & 0xFFFFFFFF
def blob_name(b): return f'files/{crc(b):08X}-{len(b)}.bin'
def run(cmd, cwd):
    print('  $', ' '.join(cmd))
    r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode: sys.exit(r.stdout[-3000:] + f'\nFAILED: {" ".join(cmd)}')
    return r.stdout

# ---------------------------------------------------------------- the parts
def teensy_package(build):
    pkg = os.path.join(HERE, 'out', 'TXFW.BIN')
    if build:
        print('Building the Teensy firmware ...')
        run([PIO, 'run', '-e', 'teensy41'], TEENSY)
        print(run([sys.executable, os.path.join(HERE, 'make_fw_package.py')], ROOT).strip())
    b = open(pkg, 'rb').read()
    if b[:8] != b'LDRCFW01': sys.exit(f'{pkg} is not an update package')
    size, c = int.from_bytes(b[8:12], 'little'), int.from_bytes(b[12:16], 'little')
    if size != len(b) - 64 or c != crc(b[64:]): sys.exit(f'{pkg} is damaged')
    if b[48:64].split(b'\0')[0] != b'fw_teensy41': sys.exit(f'{pkg} is not for the Teensy 4.1')
    return b, b[16:48].split(b'\0')[0].decode()

CLEAN = os.path.join(HERE, 'out', 'screen_build')       # the screen's project WITHOUT its secrets.h: the firmware that is published is built here

def clean_copy():
    """The screen's project, copied without secrets.h (and without what is not source). What is built here cannot hold a password."""
    os.makedirs(CLEAN, exist_ok=True)
    run(['rsync', '-a', '--delete', '--delete-excluded', '--exclude', 'secrets.h', '--exclude', '/.pio', '--exclude', '/sd', '--exclude', '/hmi/test_*', '--exclude', '.DS_Store', '--exclude', '__pycache__',
         '--filter', 'P /.pio', SCREEN + '/', CLEAN + '/'], ROOT)
    for d, dirs, names in os.walk(CLEAN):
        if '.pio' in dirs: dirs.remove('.pio')
        for n in names:
            if 'secret' in n.lower(): sys.exit(f'REFUSED: {os.path.join(d, n)} is in the copy the firmware is built from')

def screen_firmware(build):
    src = open(os.path.join(SCREEN, 'src', 'main.cpp'), encoding='utf-8').read()
    m = re.search(r'#define\s+SCREEN_VERSION\s+"([^"]+)"', src)
    if not m: sys.exit('SCREEN_VERSION not found in the screen\'s main.cpp')
    image = os.path.join(CLEAN, '.pio', 'build', 'ota', 'firmware.bin')
    if build:
        print('Building the screen firmware (in a copy of its project that holds no secrets.h) ...')
        clean_copy()
        run([PIO, 'run', '-e', 'ota'], CLEAN)
    if not os.path.exists(image): sys.exit('the screen firmware has not been built yet: leave out --no-build')
    b = open(image, 'rb').read()
    found = re.findall(rb'LDRCSCREEN=([^;\0]{1,31});', b)
    if len(set(found)) != 1: sys.exit('the screen firmware does not say which version it is (LDRCSCREEN=...;)')
    version = found[0].decode()
    if version != m.group(1): sys.exit(f'the screen firmware that is built is {version}, the source says {m.group(1)}: build it (leave out --no-build)')
    if b[0] != 0xE9: sys.exit('the screen firmware is not an ESP32 image')
    if len(b) > 0x1E0000: sys.exit('the screen firmware is too big for its half of the flash')
    return b, version

def teensy_files():
    """The help texts: TXV1B/"Help files for SD" -> /help/NAME.TXT on the Teensy's card."""
    folder = os.path.join(ROOT, 'Help files for SD'); out = {}
    for n in sorted(os.listdir(folder)):
        if n.upper().endswith('.TXT') and not n.startswith('.'): out['/help/' + n.upper()] = open(os.path.join(folder, n), 'rb').read()
    return out

def screen_files():
    """Everything on the screen's card: <screen project>/sd -> the same paths on the card."""
    root = os.path.join(SCREEN, 'sd'); out = {}
    for d, dirs, names in os.walk(root):
        dirs[:] = sorted(x for x in dirs if not x.startswith('.'))
        for n in sorted(names):
            if n.startswith('.'): continue
            full = os.path.join(d, n)
            out['/' + os.path.relpath(full, root).replace(os.sep, '/')] = open(full, 'rb').read()
    return out

def check_paths(files, roots, what):
    for p in files:
        if not re.fullmatch(r'/[A-Za-z0-9 _.()+,\-/]{1,94}', p) or '..' in p or '//' in p or p.endswith('/'): sys.exit(f'{what}: "{p}" is not a name the screen will accept (95 characters at most)')
        # FAT drops a space at the start of a name, and dots and spaces at its end: "/models.dat." IS models.dat
        if any(part != part.strip(' ') or part.endswith('.') for part in p.split('/')[1:]): sys.exit(f'{what}: "{p}": no part of a name may begin with a space, or end with a space or a dot')
        if p.lower().startswith('/link.'): sys.exit(f'{what}: "{p}" is a name the file link keeps for itself')
        if not any(p.startswith(r) for r in roots): sys.exit(f'{what}: "{p}" is outside {roots}')
        low = p.lower()
        if low == '/models.dat' or low.startswith('/mod/') or low.startswith('/log/') or low.startswith('/fw/') or low.endswith(('.mod', '.log', '.dat')): sys.exit(f'{what}: "{p}" is the pilot\'s own data, or the firmware area: never in a release')

def c_bytes(raw):
    """The bytes a C compiler makes of what stands between the quotes of a string literal."""
    simple = {'n': 10, 't': 9, 'r': 13, '0': 0, 'a': 7, 'b': 8, 'f': 12, 'v': 11, '\\': 92, '"': 34, "'": 39, '?': 63}
    raw = raw.encode('utf-8'); b = bytearray(); i = 0
    while i < len(raw):
        c = raw[i:i + 1]
        if c != b'\\' or i + 1 >= len(raw): b += c; i += 1; continue
        n = chr(raw[i + 1])
        if n == 'x':
            j = i + 2
            while j < len(raw) and chr(raw[j]) in '0123456789abcdefABCDEF': j += 1
            if j > i + 2: b.append(int(raw[i + 2:j], 16) & 255)
            i = j
        elif n in '01234567':
            j = i + 1
            while j < len(raw) and j < i + 4 and chr(raw[j]) in '01234567': j += 1
            b.append(int(raw[i + 1:j], 8) & 255); i = j
        else: b.append(simple.get(n, raw[i + 1])); i += 2
    return bytes(b)

def private_values(path=None):
    """Every text of the screen project's include/secrets.h (if there is one), as the bytes a compiler would put into a
       program. Used ONLY to make sure that none of them is inside anything that goes to the website.
       EVERY string literal of the file counts, whatever the line looks like (#define, const char *, a comment behind it, a
       literal in two halves, a line carried on with a backslash): of 8 bytes or more whatever it is called, of 4 bytes or
       more when the name before it has PASS, KEY, SECRET or TOKEN in it. (Shorter ones would be found in any text.)
       The values are never printed: a file is refused by the NAME of what it holds."""
    path = path or os.path.join(SCREEN, 'include', 'secrets.h'); out = {}
    if not os.path.exists(path): return out
    text = open(path, encoding='utf-8', errors='replace').read().replace('\\\r\n', '').replace('\\\n', '')      # lines carried on
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)                                                          # /* comments */ (a // comment cannot hide a literal that stands before it)
    quoted = r'"((?:[^"\\\n]|\\.)*)"'
    literals = 0
    for line in text.splitlines():
        found = list(re.finditer(quoted, line))
        if not found: continue
        name = re.search(r'([A-Za-z_]\w*)\W*$', line[:found[0].start()])          # the word before the first literal: what it is called
        name = name.group(1) if name else f'a text in line {literals + 1}'
        secret = any(w in name.upper() for w in ('PASS', 'KEY', 'SECRET', 'TOKEN', 'PSK', 'PWD'))
        parts = [c_bytes(m.group(1)) for m in found]
        joined = b''; prev = None
        for m, b in zip(found, parts):                                           # "abc" "def" is one text to the compiler
            joined = joined + b if prev is not None and line[prev:m.start()].strip() == '' else b
            prev = m.end()
            for k, v in ((name, b), (name + ' (joined)', joined)):
                if len(v) < (4 if secret else 8) or v in out.values(): continue
                out[k if k not in out else f'{k} #{len(out)}'] = v
        literals += len(found)
    if not literals: sys.exit(f'REFUSING: {path} is there, and not one text could be read in it. Nothing is staged or published until it can be read.')
    return out

def refuse_private(name, b, private):
    """29 Sep 2026: the first four screen firmwares went to the website with the house WiFi password compiled into them.
       Never again: a file that holds any value of secrets.h is refused, by name of the value, never by the value."""
    found = [k for k, v in private.items() if v in b]
    if found: sys.exit(f'REFUSED: {name} contains {", ".join(found)} of include/secrets.h. It must not go to the website.')

def refuse_private_everywhere(private):
    """Everything below the staging folder goes to the website sooner or later (publish mirrors files/ and v/ whole):
       every file of it is searched, not only those of the release in hand."""
    n = 0
    for d, dirs, names in os.walk(REL):
        for f in sorted(names):
            if f.startswith('.'): continue
            full = os.path.join(d, f); refuse_private(os.path.relpath(full, REL), open(full, 'rb').read(), private); n += 1
    return n

def list_text(files): return ''.join(f'{crc(b):08X} {len(b)} {p}\n' for p, b in sorted(files.items())).encode()

# ---------------------------------------------------------------- stage
def put_blob(b):
    name = blob_name(b); path = os.path.join(REL, name)
    if os.path.exists(path):
        if open(path, 'rb').read() != b: sys.exit(f'two different files want the name {name}: a CRC-32 collision. Change one of them by a byte.')
        return name, False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'wb').write(b)
    return name, True

def slug(name): return re.sub(r'[^A-Za-z0-9.]+', '-', name).strip('-')

def stage(notes, build, name, with_screen=True):
    tp, tv = teensy_package(build)
    sf, sv = screen_firmware(build) if with_screen else (None, None)
    tf, scf = teensy_files(), screen_files()
    private = private_values()
    print(f'  looking for {len(private)} private texts of secrets.h in everything that is to be published' if private else '  (there is no secrets.h: nothing private to look for)')
    for label, b in [('the Teensy firmware', tp)] + ([('the screen firmware', sf)] if with_screen else []) + list(tf.items()) + list(scf.items()): refuse_private(label, b, private)
    check_paths(tf, ['/help/'], 'the Teensy\'s files'); check_paths(scf, ['/hmi/', '/images/'], 'the screen\'s files')
    if not tf or len(scf) < 100: sys.exit('files are missing: the help texts or the screen\'s card folder')
    name = name or (f"{' '.join(tv.split(' ')[:2])} (screen {sv})" if with_screen else f"{' '.join(tv.split(' ')[:2])} (screen as it is)")
    if '\n' in notes or len(notes) > 300: sys.exit('the notes: one line, 300 characters at most')
    new = 0
    names = {}
    for label, b in (('teensy', tp), ('screen', sf), ('teensy_list', list_text(tf)), ('screen_list', list_text(scf))):
        if b is None: continue
        names[label], fresh = put_blob(b); new += fresh
    for files in (tf, scf):
        for b in files.values(): new += put_blob(b)[1]
    d = {'name': name, 'date': datetime.date.today().isoformat(), 'notes': notes, 'base': BASE,
         'teensy': {'version': tv, 'file': names['teensy'], 'size': len(tp), 'crc': f'{crc(tp):08X}'},
         'teensy_files': {'file': names['teensy_list'], 'size': len(list_text(tf)), 'crc': f'{crc(list_text(tf)):08X}', 'count': len(tf), 'bytes': sum(map(len, tf.values()))},
         'screen_files': {'file': names['screen_list'], 'size': len(list_text(scf)), 'crc': f'{crc(list_text(scf)):08X}', 'count': len(scf), 'bytes': sum(map(len, scf.values()))}}
    if with_screen: d['screen'] = {'version': sv, 'file': names['screen'], 'size': len(sf), 'crc': f'{crc(sf):08X}'}
    write_release(d)
    gone = tidy()
    if gone: print(f'  {gone} files that no release names any more were taken out of the staging folder')
    searched = refuse_private_everywhere(private)
    print(f'  {searched} files in the staging folder searched: nothing private in any of them')
    print(f'\nStaged release "{name}"\n  Teensy firmware  {tv}  ({len(tp) // 1024} kB)\n  screen firmware  ' + (f'{sv}  ({len(sf) // 1024} kB)' if with_screen else 'not in this release: screens keep what they have') +
          f'\n  Teensy files     {len(tf)}  ({d["teensy_files"]["bytes"] // 1024} kB)\n  screen files     {len(scf)}  ({d["screen_files"]["bytes"] / 1048576:.1f} MB)'
          f'\n  {new} files are new to the website\n  notes: {notes}\nNext: dev/release_v1b.py publish')

def release_text(d):
    t = f"# Transmitter Version 1B: a release. Read by the screen (\"Check for update\").\nldrc-release=1\nname={d['name']}\ndate={d['date']}\nnotes={d['notes']}\nbase={d['base']}\n"
    for part in ('teensy', 'teensy_files', 'screen', 'screen_files'):
        for k in ('version', 'file', 'size', 'crc', 'count', 'bytes'):
            if part in d and k in d[part]: t += f'{part}.{k}={d[part][k]}\n'
    return t + 'end=1\n'

RECENT = 4          # the latest and the three before it: what the panel's "Earlier versions" offers

def whole(r):
    """A release that can be gone back to: all four parts, every one of its files still in the staging folder."""
    if not all(part in r for part in ('teensy', 'screen', 'teensy_files', 'screen_files')): return False
    return all(os.path.exists(os.path.join(REL, r[part]['file'])) for part in ('teensy', 'screen', 'teensy_files', 'screen_files'))

def recent_text():
    """recent.txt: release=name|date|Teensy version|screen version|path of its description|notes, the latest first."""
    mpath = os.path.join(REL, 'manifest.json')
    versions = json.load(open(mpath))['versions'] if os.path.exists(mpath) else []
    t = '# Transmitter Version 1B: the releases that can be installed, the latest first. Read by the screen ("Earlier versions").\nldrc-recent=1\n'; n = 0
    for v in versions:
        jp = os.path.join(REL, 'v', slug(v['name']), 'release.json')
        if not os.path.exists(jp): continue
        r = json.load(open(jp))
        if not whole(r): continue
        if any('|' in str(x) for x in (r['name'], r['date'], r['teensy']['version'], r['screen']['version'])): sys.exit(f'a "|" in the name or a version of {r["name"]}')
        t += f"release={r['name']}|{r['date']}|{r['teensy']['version']}|{r['screen']['version']}|v/{slug(r['name'])}/release.txt|{r['notes']}\n"; n += 1
        if n >= RECENT: break
    return t + 'end=1\n', n

def write_release(d, history=True):
    text = release_text(d)
    os.makedirs(os.path.join(REL, 'v', slug(d['name'])), exist_ok=True)
    open(os.path.join(REL, 'v', slug(d['name']), 'release.txt'), 'w').write(text)
    json.dump(d, open(os.path.join(REL, 'v', slug(d['name']), 'release.json'), 'w'), indent=1)
    open(os.path.join(REL, 'latest.txt'), 'w').write(text)
    mpath = os.path.join(REL, 'manifest.json')
    versions = json.load(open(mpath))['versions'] if os.path.exists(mpath) else []
    versions = [v for v in versions if v['name'] != d['name']]
    versions.insert(0, {'name': d['name'], 'date': d['date'], 'notes': d['notes'], 'teensy': d['teensy']['version'], 'screen': d.get('screen', {}).get('version', 'as it is'),
                        'description': BASE + 'v/' + slug(d['name']) + '/release.txt'})
    pretty = dict(d); pretty['description'] = BASE + 'latest.txt'
    for part in ('teensy', 'screen', 'teensy_files', 'screen_files'):
        if part in d: pretty[part] = dict(d[part], url=BASE + d[part]['file'])
    json.dump({'product': 'txv1b', 'what': 'LDRC Transmitter Version 1B: releases for the button "Check for update"', 'latest': pretty, 'versions': versions}, open(mpath, 'w'), indent=1)
    open(os.path.join(REL, 'recent.txt'), 'w').write(recent_text()[0])

def referenced():
    """Every file below files/ that a release names: its four parts, and every file of its two lists."""
    names = set()
    vdir = os.path.join(REL, 'v')
    for folder in sorted(os.listdir(vdir)) if os.path.isdir(vdir) else []:
        jp = os.path.join(vdir, folder, 'release.json')
        if not os.path.exists(jp): continue
        r = json.load(open(jp))
        for part in ('teensy', 'screen', 'teensy_files', 'screen_files'):
            if part not in r: continue
            names.add(r[part]['file'])
            lp = os.path.join(REL, r[part]['file'])
            if part.endswith('_files') and os.path.exists(lp):
                for line in open(lp, 'rb').read().decode(errors='replace').splitlines():
                    f = line.split(' ', 2)
                    if len(f) == 3: names.add(f'files/{f[0]}-{f[1]}.bin')
    return names

def tidy():
    """Files in the staging folder that no release names (what an earlier staging of the same release built) are removed:
       the upload takes the whole folder along, and nothing goes to the website that no release stands for."""
    keep = referenced(); gone = 0
    folder = os.path.join(REL, 'files')
    for n in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if 'files/' + n not in keep: os.remove(os.path.join(folder, n)); gone += 1
    return gone

# ---------------------------------------------------------------- publish
def staged():
    p = os.path.join(REL, 'latest.txt')
    if not os.path.exists(p): sys.exit('nothing is staged: dev/release_v1b.py stage "notes" first')
    text = open(p).read()
    d = dict(l.split('=', 1) for l in text.splitlines() if '=' in l and not l.startswith('#'))
    if d.get('end') != '1': sys.exit('the staged description is incomplete')
    return text, d

def wanted(d):
    """Every file of the staged release: {name on the site: bytes}."""
    out = {}
    for part in ('teensy', 'screen', 'teensy_files', 'screen_files'):
        if part + '.file' not in d: continue
        name = d[part + '.file']; b = open(os.path.join(REL, name), 'rb').read()
        if len(b) != int(d[part + '.size']) or f'{crc(b):08X}' != d[part + '.crc']: sys.exit(f'{name} is not what the description says: stage again')
        out[name] = b
        if part.endswith('_files'):
            for line in b.decode().splitlines():
                c, size, _path = line.split(' ', 2); n = f'files/{c}-{size}.bin'
                fb = open(os.path.join(REL, n), 'rb').read()
                if len(fb) != int(size) or f'{crc(fb):08X}' != c: sys.exit(f'{n} is damaged in the staging folder: stage again')
                out[n] = fb
    return out

def tls():
    """The site's certificate is checked, whichever Python runs this (PlatformIO's brings no root certificates: macOS's are used)."""
    import ssl
    return ssl.create_default_context(cafile='/etc/ssl/cert.pem') if os.path.exists('/etc/ssl/cert.pem') else ssl.create_default_context()

def fetch(conn, path):
    import http.client
    for attempt in range(3):
        try:
            if conn[0] is None: conn[0] = http.client.HTTPSConnection('messiter.com', timeout=60, context=tls())
            conn[0].request('GET', '/txv1b/release/' + path, headers={'Cache-Control': 'no-cache'})
            r = conn[0].getresponse(); body = r.read()
            return r.status, body
        except Exception as e:
            conn[0] = None; last = e
    return 0, str(last).encode()

def gate():
    """The screen's own parser reads the staged release (the host tests of the screen's project): what it refuses is not published."""
    test = os.path.join(SCREEN, 'hmi', 'test_update', 'run.sh')
    r = subprocess.run([test, '--release', REL], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print('  ' + r.stdout.strip().replace('\n', '\n  '))
    if r.returncode: sys.exit('REFUSING TO PUBLISH: the screen would not accept this release (above).')

def ftp_login():
    env = dict(os.environ)
    if 'LFTP_PASSWORD' not in env:
        if not os.path.exists(FTP_CREDENTIALS): sys.exit(f'no FTP login: {FTP_CREDENTIALS} is missing')
        got = subprocess.run(['bash', '-c', f'source "{FTP_CREDENTIALS}" >/dev/null 2>&1; printf "%s\\n%s\\n%s" "$LFTP_PASSWORD" "$LDRC_FTP_HOST" "$LDRC_FTP_USER"'], stdout=subprocess.PIPE, text=True).stdout.split('\n')
        if len(got) < 3 or not got[0]: sys.exit('the FTP login could not be read')
        env['LFTP_PASSWORD'], env['LDRC_FTP_HOST'], env['LDRC_FTP_USER'] = got[0], got[1], got[2]
    return env

def lftp(script, env):
    r = subprocess.run(['lftp', '--env-password', '-u', env['LDRC_FTP_USER'], env['LDRC_FTP_HOST']], input='set ftp:ssl-allow yes\nset ssl:verify-certificate no\nset net:max-retries 3\nset net:timeout 30\n' + script + 'quit\n',
                       cwd=SITE, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return r.returncode, [l for l in r.stdout.splitlines() if l.strip()]

def purge(names):
    """Take files OFF the website (and out of the staging folder), and out of every release that names them.
       For a file that should never have been published. The latest release must not name any of them: publish one that does not, first."""
    text, d = staged()
    for n in names:
        if not re.fullmatch(r'files/[0-9A-F]{8}-[0-9]+\.bin', n): sys.exit(f'{n}: give names as files/<CRC>-<size>.bin')
        if n in text: sys.exit(f'{n} is part of the latest release. Stage and publish a release without it first.')
    env = ftp_login(); changed = []
    for folder in sorted(os.listdir(os.path.join(REL, 'v'))):
        jp = os.path.join(REL, 'v', folder, 'release.json')
        if not os.path.exists(jp): continue
        r = json.load(open(jp)); hit = [part for part in ('teensy', 'screen', 'teensy_files', 'screen_files') if part in r and r[part]['file'] in names]
        if not hit: continue
        for part in hit: del r[part]
        r['notes'] = (r['notes'] + ' ' if r['notes'] else '') + '(' + ' and '.join(hit) + ' withdrawn)'
        json.dump(r, open(jp, 'w'), indent=1); open(os.path.join(REL, 'v', folder, 'release.txt'), 'w').write(release_text(r)); changed.append(folder)
    script = ''.join(f'rm -f public_html/txv1b/release/{n}\n' for n in names)
    script += ''.join(f'put -O public_html/txv1b/release/v/{f} txv1b/release/v/{f}/release.txt\nput -O public_html/txv1b/release/v/{f} txv1b/release/v/{f}/release.json\n' for f in changed)
    code, out = lftp(script, env)
    if code: sys.exit('\n'.join(out[-15:]) + '\nFAILED: the removal')
    for n in names:
        path = os.path.join(REL, n)
        if os.path.exists(path): os.remove(path)
    conn = [None]; still = []
    for n in names:
        status, body = fetch(conn, n + '?n=' + str(os.getpid()))
        if status != 404: still.append(f'{n} ({status})')
    if still: sys.exit('STILL THERE: ' + ', '.join(still))
    print(f'{len(names)} files are off the website (each answers 404 now); {len(changed)} earlier releases no longer name them: ' + ', '.join(changed))

def publish():
    text, d = staged(); files = wanted(d)
    private = private_values()
    for n, b in files.items(): refuse_private(n, b, private)
    searched = refuse_private_everywhere(private)            # ... and every other file that the upload will take along
    print(f'  {searched} files searched for {len(private)} private texts: none holds any')
    gate()
    total = sum(map(len, files.values()))
    print(f'Release "{d["name"]}": {len(files)} files, {total / 1048576:.1f} MB. Uploading what messiter.com has not got ...')
    env = ftp_login()
    # The files and the releases' own descriptions first; latest.txt last, and only when the rest is proven to be there:
    # a transmitter that checks in the middle of this finds the previous release, whole.
    script = ('set ftp:ssl-allow yes\nset ssl:verify-certificate no\nset net:max-retries 3\nset net:timeout 30\n'
              'mkdir -p -f public_html/txv1b/release/files\nmkdir -p -f public_html/txv1b/release/v\n'
              'mirror -R --ignore-time --parallel=4 --verbose=1 txv1b/release/files public_html/txv1b/release/files\n'
              'mirror -R --parallel=2 --verbose=1 txv1b/release/v public_html/txv1b/release/v\nquit\n')
    r = subprocess.run(['lftp', '--env-password', '-u', env['LDRC_FTP_USER'], env['LDRC_FTP_HOST']], input=script, cwd=SITE, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    sent = [l for l in r.stdout.splitlines() if l.strip()]
    print(f'  {sum(1 for l in sent if "Transferring" in l or "->" in l)} files sent')
    if r.returncode: sys.exit('\n'.join(sent[-15:]) + '\nFAILED: the upload')
    print('Reading every file back from messiter.com ...')
    conn = [None]; bad = []; done = 0
    for n, b in sorted(files.items()):
        status, body = fetch(conn, n)
        if status != 200 or body != b: bad.append(f'{n} ({status}, {len(body)} bytes)')
        done += 1
        if sys.stdout.isatty(): print(f'  read back {done} of {len(files)}', end='\r')
    print(f'  {done} files read back' + ' ' * 20)
    if bad: sys.exit('NOT PUBLISHED: these are not on messiter.com as they should be:\n  ' + '\n  '.join(bad[:20]) + '\nlatest.txt was left alone: transmitters still find the previous release.')
    # Every release that "Earlier versions" offers must be there whole, too: its description and each of its four parts.
    rtext, rcount = recent_text()
    open(os.path.join(REL, 'recent.txt'), 'w').write(rtext)
    for line in rtext.splitlines():
        if not line.startswith('release='): continue
        path = line.split('|')[4]
        status, body = fetch(conn, path)
        want = open(os.path.join(REL, path)).read()
        if status != 200 or body.decode(errors='replace') != want: bad.append(f'{path} ({status})')
        rd = dict(l.split('=', 1) for l in want.splitlines() if '=' in l and not l.startswith('#'))
        for part in ('teensy', 'screen', 'teensy_files', 'screen_files'):
            n = rd[part + '.file']
            if n in files: continue                       # read back already, as part of the latest
            status, body = fetch(conn, n)
            if status != 200 or len(body) != int(rd[part + '.size']) or f'{crc(body):08X}' != rd[part + '.crc']: bad.append(f'{n} of {rd["name"]} ({status})')
    if bad: sys.exit('NOT PUBLISHED: an earlier release is not whole on messiter.com:\n  ' + '\n  '.join(bad[:20]))
    script = ('set ftp:ssl-allow yes\nset ssl:verify-certificate no\nset net:max-retries 3\n'
              'put -O public_html/txv1b/release txv1b/release/manifest.json\nput -O public_html/txv1b/release txv1b/release/recent.txt\nput -O public_html/txv1b/release txv1b/release/latest.txt\nquit\n')
    r = subprocess.run(['lftp', '--env-password', '-u', env['LDRC_FTP_USER'], env['LDRC_FTP_HOST']], input=script, cwd=SITE, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.returncode: sys.exit(r.stdout[-1500:] + '\nFAILED: the upload of latest.txt')
    status, body = fetch(conn, 'latest.txt?n=' + str(os.getpid()))
    if status != 200 or body.decode(errors='replace') != text: sys.exit(f'latest.txt on messiter.com is not the one staged ({status})')
    status, body = fetch(conn, 'recent.txt?n=' + str(os.getpid()))
    if status != 200 or body.decode(errors='replace') != rtext: sys.exit(f'recent.txt on messiter.com is not the one staged ({status})')
    print(f'{rcount} releases can be gone back to ("Earlier versions"):', ', '.join(l.split('=', 1)[1].split('|')[0] for l in rtext.splitlines() if l.startswith('release=')))
    print(f'PUBLISHED: "{d["name"]}" is the latest release.\n  Teensy {d["teensy.version"]}, screen {d.get("screen.version", "as it is")}, {d["teensy_files.count"]} help files, {d["screen_files.count"]} screen files'
          f'\n  {BASE}latest.txt')
    # The public repository (github.com/Mmessiter/LDRC_V2) gets the same release as a snapshot, committed and pushed
    # (Malcolm, 2026-10-05: "Go!" - Version 2 is public).
    r = subprocess.run([sys.executable, os.path.join(HERE, 'publish_public.py'), '--push'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(('  public repository: ' + r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else ('  public repository NOT updated:\n' + r.stdout[-1500:]))

def status():
    conn = [None]
    s, body = fetch(conn, 'latest.txt?n=' + str(os.getpid()))
    if s == 200:
        d = dict(l.split('=', 1) for l in body.decode(errors='replace').splitlines() if '=' in l and not l.startswith('#'))
        print(f'live:    "{d.get("name")}" of {d.get("date")}  Teensy {d.get("teensy.version")}, screen {d.get("screen.version", "as it is")}\n         {d.get("notes")}')
    else: print(f'live:    nothing ({s})')
    if os.path.exists(os.path.join(REL, 'latest.txt')):
        text, d = staged()
        print(f'staged:  "{d["name"]}" of {d["date"]}  Teensy {d["teensy.version"]}, screen {d.get("screen.version", "as it is")}' + ('   (the same as live)' if s == 200 and body.decode(errors='replace') == text else '   (NOT yet published)'))
    else: print('staged:  nothing')

def latest(name):
    p = os.path.join(REL, 'v', slug(name), 'release.json')
    if not os.path.exists(p): sys.exit(f'no such release: {name}. There are: ' + ', '.join(sorted(os.listdir(os.path.join(REL, 'v')))))
    d = json.load(open(p)); write_release(d)
    print(f'"{d["name"]}" is staged as the latest again. Next: dev/release_v1b.py publish')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('what', choices=['stage', 'publish', 'status', 'latest', 'purge'])
    ap.add_argument('text', nargs='*', default=[])
    ap.add_argument('--no-build', action='store_true'); ap.add_argument('--name', default=None)
    ap.add_argument('--without-screen', action='store_true', help='a release that leaves the screen\'s firmware as it is')
    a = ap.parse_intermixed_args()
    if a.what == 'stage':
        if len(a.text) != 1: sys.exit('say what is new: dev/release_v1b.py stage "what is new"')
        stage(a.text[0], not a.no_build, a.name, not a.without_screen)
    elif a.what == 'publish': publish()
    elif a.what == 'status': status()
    elif a.what == 'purge': purge(a.text)
    else: latest(a.text[0] if a.text else '')

if __name__ == '__main__':
    main()
