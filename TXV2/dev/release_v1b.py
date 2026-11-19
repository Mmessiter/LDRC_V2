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

   stage takes  --no-build         use the firmware already built (Teensy: dev/out/TXFW.BIN, screen: dev/out/screen_build/.pio/build/ota and ota_full)
                                   - the Teensy's package must be the SOURCE'S version, newer than every file of its source, and the very one
                                     THIS script's build made from the source as it is now (the build says so beside it: dev/out/TXFW.BIN.source)
                                   - the screen's two images likewise: the very ones THIS script's build made, from the screen's source as it is
                                     now (the build says so beside its log: dev/out/screen_build/.pio/build/release_build.source)
                --without-screen   a release that leaves the screen's firmware as it is
                --teensy-source-unchanged   (a release of the screen alone, once) the Teensy's source has NOT changed since the earlier release that
                                   has this Teensy version and was made before the releases recorded their source: see teensy_version_checked

   A release is four parts, and a fifth since 23 Oct 2026. The screen compares each with what the transmitter has and fetches what differs:
     teensy        the Teensy's firmware, as an update package (dev/make_fw_package.py)     compared by version
     screen        the screen's firmware, STANDARD: fits the 4 MB boards' 1.9 MB slot      compared by version (and build)
     screen_full   the same source built FULL for the 16 MB boards' 6.25 MB slots           a screen on the 16 MB layout takes only this
     teensy_files  the files for the Teensy's SD card: the help texts, to /help             compared by the list's checksum
     screen_files  the files for the screen's card: pages, pictures, fonts, sounds, images  compared by the list's checksum
   Never the pilot's own data: no models, no logs (the screen refuses a list that names one, and so does the Teensy).

   On the website:
     latest.txt                  what the screen reads: key=value lines, the last one end=1
     recent.txt                  the latest release and the three before it that are whole: what "Earlier versions" offers
     manifest.json               the same for people and other tools, with the history of releases
     v/<release>/release.txt     each release's own description (for going back)
     files/<CRC32>-<size>.bin    every file, under the name of its content: uploaded once, shared by all releases
     flash-screen.json           (3 Nov 2026) the browser flasher's list (messiter.com/ldrc/flash-screen.html): for a screen
                                 on USB, each build's bootloader, partition table, boot_app0 and firmware, at their offsets
     ldrc-v2-teensy41.hex        (10 Nov 2026) the latest release's Teensy firmware as an Intel HEX file, for a new Teensy's
                                 FIRST flash with PJRC's Teensy Loader: no PlatformIO, nothing to compile (teensy_hex)"""
import argparse, datetime, json, os, re, shutil, subprocess, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEENSY = os.path.join(ROOT, 'TransmitterCode')
SCREEN = os.path.expanduser('~/Documents/GitHub/ESP32-board2/board4/nextion-emulator')
SITE = os.path.join(ROOT, 'NewWebSite', 'public_html')
REL = os.path.join(SITE, 'txv1b', 'release')
BASE = 'https://messiter.com/txv1b/release/'
PARTS = ('teensy', 'screen', 'teensy_files', 'screen_files', 'screen_full')    # every part a release may have (screen_full since 23 Oct 2026: optional, for the 16 MB boards)
FTP_CREDENTIALS = os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/RXV2/dev/ftp_credentials.sh')   # exports LFTP_PASSWORD, LDRC_FTP_HOST, LDRC_FTP_USER
PIO = shutil.which('pio') or os.path.expanduser('~/.platformio/penv/bin/pio')

def crc(b): return zlib.crc32(b) & 0xFFFFFFFF
def blob_name(b): return f'files/{crc(b):08X}-{len(b)}.bin'
def build_env():
    """B211 (the thirteenth review, reviewer A's finding 3): A RELEASE IS BUILT FROM ITS platformio.ini ALONE. PlatformIO adds what the shell's PLATFORMIO_*
       variables say to what the ini says (PLATFORMIO_BUILD_FLAGS, _BUILD_UNFLAGS, _LIB_EXTRA_DIRS, _EXTRA_SCRIPTS) and takes others INSTEAD of it
       (_LIBDEPS_DIR, _BUILD_DIR): the test builds are made with PLATFORMIO_BUILD_FLAGS=-DELRS_TEST, and that variable left in the shell built the RELEASE
       with the ELRS driver in it - the same version text, every check passed; for the screen, -DEMU_ECHO echoes every command down the wire, and
       another library folder is taken while the pin hashes the untouched one. No pin looks at the environment: so no such variable reaches a build."""
    left = sorted(k for k in os.environ if k.upper().startswith('PLATFORMIO_'))
    if left: print('  (NOT passed on to the build: ' + ', '.join(left) + ' - a release is built from its platformio.ini alone)')
    return {k: v for k, v in os.environ.items() if not k.upper().startswith('PLATFORMIO_')}
def run(cmd, cwd):
    print('  $', ' '.join(cmd))
    r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=build_env())
    if r.returncode: sys.exit(r.stdout[-3000:] + f'\nFAILED: {" ".join(cmd)}')
    return r.stdout

# ---------------------------------------------------------------- the parts
def teensy_source_files():
    """Every file the Teensy's firmware is built from: TransmitterCode/src, include, lib (all of them) and platformio.ini. {path below TransmitterCode: full path}"""
    out = {}
    for top in ('src', 'include', 'lib'):
        for d, dirs, names in os.walk(os.path.join(TEENSY, top)):
            dirs[:] = sorted(x for x in dirs if not x.startswith('.'))
            for n in sorted(names):
                if not n.startswith('.'): out[os.path.relpath(os.path.join(d, n), TEENSY).replace(os.sep, '/')] = os.path.join(d, n)
    ini = os.path.join(TEENSY, 'platformio.ini')
    if os.path.isfile(ini): out['platformio.ini'] = ini
    return out

def teensy_source_hash():
    """One number for the Teensy's whole source (the names and the bytes of teensy_source_files): recorded with every release - teensy_version_checked."""
    import hashlib
    h = hashlib.sha256()
    for rel_path, full in sorted(teensy_source_files().items()):
        b = open(full, 'rb').read(); h.update(rel_path.encode() + b'\0' + str(len(b)).encode() + b'\0' + b)
    return h.hexdigest()[:32]

def source_version():
    """The version text the Teensy's source says (1Definitions.h TXVERSION_*) - as dev/make_fw_package.py puts it into a package's header."""
    text = open(os.path.join(TEENSY, 'include', '1Definitions.h'), encoding='latin1').read()
    def grab(name):
        m = re.search(r'#define\s+' + name + r'\s+(?:"([^"\n]*)"|(\S+))', text)
        if not m: sys.exit(f'{name} not found in 1Definitions.h')
        return (m.group(1) if m.group(1) is not None else m.group(2)).strip()
    return f"{grab('TXVERSION_MAJOR')}.{grab('TXVERSION_MINOR')}.{grab('TXVERSION_MINIMUS')} {grab('TXVERSION_EXTRA')}"

def teensy_package_is_the_sources(version, pkg, built_now):
    """B211 (the fourteenth review, reviewer A's finding 5): THE PACKAGE THAT IS STAGED IS THIS SOURCE'S. With --no-build whatever lay in dev/out/TXFW.BIN
       was taken - a package of ANOTHER version (an older build), or one built by hand: only its header and the ELRS mark were looked at. Its version
       must be the source's, and a package kept from before must be newer than every file of the Teensy's source."""
    want = source_version()
    if version != want: sys.exit(f'REFUSING TO PUBLISH: the Teensy package {pkg} is version "{version}" and the source says "{want}": build it (leave out --no-build)')
    if built_now: return
    made = os.path.getmtime(pkg)
    newer = sorted((os.path.getmtime(full), rel_path) for rel_path, full in teensy_source_files().items() if os.path.getmtime(full) > made + 2)
    if newer: sys.exit(f'REFUSING --no-build: the Teensy package {pkg} is OLDER than the Teensy\'s source ({len(newer)} file(s) were changed since it was built, the last of them '
                       f'TransmitterCode/{newer[-1][1]}): build it (leave out --no-build)')

TEENSY_BUILT_FROM = '.source'    # dev/out/TXFW.BIN.source: what THIS script's build says of the package beside it - teensy_package_is_the_builds
def package_hash(b):
    import hashlib
    return hashlib.sha256(b).hexdigest()[:32]

def teensy_build_noted(pkg, b, source):
    """The build's own word, written beside its package: the hash of the source it was built from, and which package it made."""
    open(pkg + TEENSY_BUILT_FROM, 'w').write(f'source={source}\npackage={package_hash(b)}\n')

def teensy_package_is_the_builds(b, pkg, source):
    """B211 (the fifteenth review): "NEWER THAN EVERY FILE OF THE SOURCE" IS NOT "BUILT FROM THIS SOURCE" (--no-build). A package made again by hand from
       the build before (dev/make_fw_package.py, nothing built) is newer than a source cured since; a source file copied in with its old time
       (rsync -a, cp -p) is older than the package of the build before. Both were taken - and the hash recorded with the old firmware was the new source's.
       THIS script's build writes beside its package what it built it from - the source's hash - and which package it made (teensy_build_noted).
       --no-build takes a package only by that word: the source as it is now, the package as it was made. No word (built by hand, or before this
       rule), another source, another package: refused. The files' times are still looked at, before this (teensy_package_is_the_sources)."""
    p = pkg + TEENSY_BUILT_FROM
    said = dict(l.split('=', 1) for l in open(p, encoding='utf-8', errors='replace').read().splitlines() if '=' in l) if os.path.isfile(p) else {}
    if not said.get('source') or not said.get('package'):
        sys.exit(f'REFUSING --no-build: nothing beside the Teensy package {pkg} says which source it was built from ({os.path.basename(p)} is not there, or says nothing: '
                 f'the package was built by hand, or before B211): build it (leave out --no-build)')
    if said['package'] != package_hash(b):
        sys.exit(f'REFUSING --no-build: the Teensy package {pkg} is NOT the one this script\'s build made (it was made again since, by hand): build it (leave out --no-build)')
    if said['source'] != source:
        sys.exit(f'REFUSING --no-build: the Teensy\'s source is NOT the one the package {pkg} was built from, whatever the files\' times say (a file was changed, put back, '
                 f'or copied in with its old time): build it (leave out --no-build)')

def teensy_package(build):
    """-> the package, its version text, and the hash of the Teensy's source it was built from (teensy_source_hash: stage records it with the release)"""
    pkg = os.path.join(HERE, 'out', 'TXFW.BIN')
    if build:
        print('Building the Teensy firmware ...')
        if os.path.exists(pkg + TEENSY_BUILT_FROM): os.remove(pkg + TEENSY_BUILT_FROM)   # (what an earlier build said is not said of this one, whatever becomes of it)
        source = teensy_source_hash()                                                    # B211 (the fifteenth review): what it is built from - teensy_package_is_the_builds
        run([PIO, 'run', '-e', 'teensy41'], TEENSY)
        print(run([sys.executable, os.path.join(HERE, 'make_fw_package.py')], ROOT).strip())
        if teensy_source_hash() != source: sys.exit('REFUSING TO PUBLISH: the Teensy\'s source was CHANGED WHILE its firmware was being built: which of the two the package holds is not known - build it again')
    else: source = teensy_source_hash()
    if not os.path.isfile(pkg): sys.exit(f'the Teensy firmware has not been built yet ({pkg}): leave out --no-build')
    b, version = checked_teensy_package(open(pkg, 'rb').read(), pkg)
    teensy_package_is_the_sources(version, pkg, build)
    if build: teensy_build_noted(pkg, b, source)
    else: teensy_package_is_the_builds(b, pkg, source)
    return b, version, source

def teensy_version_checked(version, package, name, source, said_unchanged=False):
    """B211 (the fourteenth review, reviewer A's finding 11): A TEENSY FIRMWARE THAT HAS CHANGED HAS A VERSION TEXT OF ITS OWN. The transmitters compare the
       Teensy's part BY ITS VERSION ("Check for update"): a release staged from a tree that still says an earlier release's version would install the new
       screen and the new page files and LEAVE THE OLD FIRMWARE in the Teensy - a mixture nobody tested (B211's new Sub-trim page file beside B210).
       Every release records a hash of the Teensy's source (release.json: teensy.source). This one's version against every EARLIER release:
       the same version with another source is refused. An earlier release from before this gate recorded none: then the very same package passes, and
       a rebuilt one passes only when it is SAID that the source has not changed since (--teensy-source-unchanged: a release of the screen alone).
       B211 (the fifteenth review): WHATEVER THE EARLIER RELEASE IS CALLED - THIS RELEASE'S OWN NAME TOO. One of this name was passed over as "the same
       release staged again" - and the name a release gets by itself is made of the Teensy's version and the screen's: a Teensy source changed under its
       old version text had the earlier release's own name, was taken, and wrote over that release's record. A NAME PROVES NOTHING: the same release
       staged again is the one whose RECORDED source is the tree's now; one of this name that recorded none is held as any other from before this gate."""
    vdir = os.path.join(REL, 'v')
    for n in sorted(os.listdir(vdir)) if os.path.isdir(vdir) else []:
        jp = os.path.join(vdir, n, 'release.json')
        if not os.path.exists(jp): continue
        r = json.load(open(jp))
        if r.get('teensy', {}).get('version') != version: continue
        own = ' (staged before, under this very name)' if r.get('name') == name else ''
        was = r['teensy'].get('source')
        if was is not None:
            if was != source: sys.exit(f'REFUSING TO PUBLISH: the Teensy\'s source has CHANGED since the release "{r["name"]}"{own}, and its version text is still "{version}". Transmitters compare the Teensy\'s '
                                       f'firmware by its version: they would take this release\'s screen and files and KEEP the old firmware. Give the firmware its own version (TXVERSION_EXTRA in 1Definitions.h).')
        elif r['teensy'].get('crc') != f'{crc(package):08X}':
            if not said_unchanged:
                sys.exit(f'REFUSING TO PUBLISH: the release "{r["name"]}"{own} has a Teensy firmware of this version, "{version}", and this package is not that one. Transmitters compare the Teensy\'s firmware by its '
                         f'version: one that has it would KEEP it. If the Teensy\'s source has changed since: give the firmware its own version (TXVERSION_EXTRA in 1Definitions.h). If it has NOT '
                         f'(a release of the screen alone, built again - the build\'s time is in the image): say --teensy-source-unchanged. (That release was made before the releases recorded their source.)')
            print(f'  (the Teensy firmware has the version of the release "{r["name"]}"{own}, made before the releases recorded their source: taken as unchanged since, as said)')

TEST_BUILD_MARKS = (b'ELRS test', b'LDRC TEST BUILD')    # what only a TEST build of the Teensy's firmware holds (ElrsCrsf.h: every line the ELRS driver says begins "ELRS test" - a release holds no "ELRS" at all;
                                                         # main.cpp: the build that falls over on purpose, -DLDRC_TEST_FALL_OVER, holds "LDRC TEST BUILD: falls over")
def checked_teensy_package(b, pkg):
    """The Teensy's update package, looked at before it is staged - built just now, or kept from before (--no-build).
       (The thirteenth review: nothing looked INTO it for what it was built with. A package built with -DELRS_TEST - by a variable left in the shell, or a
       test package left in dev/out/TXFW.BIN - has the release's version text, magic, size, CRC and target: it would have been published as the release.)"""
    if b[:8] != b'LDRCFW01': sys.exit(f'{pkg} is not an update package')
    size, c = int.from_bytes(b[8:12], 'little'), int.from_bytes(b[12:16], 'little')
    if size != len(b) - 64 or c != crc(b[64:]): sys.exit(f'{pkg} is damaged')
    if b[48:64].split(b'\0')[0] != b'fw_teensy41': sys.exit(f'{pkg} is not for the Teensy 4.1')
    for mark in TEST_BUILD_MARKS:
        if mark in b[64:]: sys.exit(f'REFUSING TO PUBLISH: {pkg} is a TEST build of the Teensy firmware (it holds "{mark.decode()}"): a release is built without -DELRS_TEST and without -DLDRC_TEST_FALL_OVER - build it (leave out --no-build)')
    return b, b[16:48].split(b'\0')[0].decode()

TEENSY_HEX = 'ldrc-v2-teensy41.hex'      # its name on the website: one name, always the latest release's firmware
def teensy_hex(package):
    """(10 Nov 2026) A NEW TEENSY'S FIRST FLASH WITHOUT A TOOLCHAIN (Malcolm: a builder must be able to do it easily
       from the repository; until now the Teensy's first flash needed PlatformIO and a build from source).
       The release's own Teensy image - the update package without its 64-byte header, which is the image as it sits in
       the Teensy's flash from 0x60000000 - as an Intel HEX file for PJRC's free Teensy Loader. Written the way PlatformIO
       writes its firmware.hex: 16 bytes a record, an address record for every 64 kB, CR LF. Rows that are all FF are left
       out (erased flash is FF, and the loader skips blank blocks anyway).
       It is read back here, record by record, every checksum checked, and must give the package's image again: what is
       published is proven to be the release's firmware, byte for byte."""
    image = package[64:]; lines = []; upper = None
    def record(addr, kind, data):
        body = bytes([len(data), addr >> 8 & 255, addr & 255, kind]) + data
        return ':' + (body + bytes([-sum(body) & 255])).hex().upper()
    for off in range(0, len(image), 16):
        row = image[off:off + 16]
        if not row.strip(b'\xFF'): continue
        addr = 0x60000000 + off
        if addr >> 16 != upper: upper = addr >> 16; lines.append(record(0, 4, upper.to_bytes(2, 'big')))
        lines.append(record(addr & 0xFFFF, 0, row))
    lines.append(record(0, 1, b''))
    text = ('\r\n'.join(lines) + '\r\n').encode()
    back = bytearray(b'\xFF' * len(image)); upper = 0; ended = False
    for line in text.decode().split('\r\n')[:-1]:
        b = bytes.fromhex(line[1:])
        if line[0] != ':' or sum(b) & 255 or b[0] != len(b) - 5 or ended: sys.exit('the Teensy HEX file: a record that does not read back')
        addr, kind, data = b[1] << 8 | b[2], b[3], b[4:-1]
        if kind == 4: upper = int.from_bytes(data, 'big')
        elif kind == 1: ended = True
        elif kind == 0:
            at = (upper << 16 | addr) - 0x60000000
            if at < 0 or at + len(data) > len(image): sys.exit('the Teensy HEX file: a record outside the image')
            back[at:at + len(data)] = data
    if not ended or bytes(back) != image or not lines[0].startswith(':020000046000'): sys.exit('the Teensy HEX file does not read back as the package\'s image')
    return text

def write_teensy_hex(file):
    """The HEX file of the Teensy firmware that latest.txt names, into the staging folder. Staging, going back to an
       earlier release and publishing all come through here: the file always stands for the latest release."""
    package = open(os.path.join(REL, file), 'rb').read()
    if package[:8] != b'LDRCFW01' or int.from_bytes(package[8:12], 'little') != len(package) - 64 or int.from_bytes(package[12:16], 'little') != crc(package[64:]):
        sys.exit(f'{file} is not a whole Teensy update package: no HEX file made of it')
    b = teensy_hex(package)
    open(os.path.join(REL, TEENSY_HEX), 'wb').write(b)
    return b

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

def screen_libraries_checked(build_log=None):
    """B211 (the twelfth review): THE LIBRARIES THE PUBLISHED SCREEN FIRMWARE IS BUILT WITH ARE THE PINNED ONES - looked at HERE, in the folder it was
       just built in, every time (built now, or kept from before: --no-build). dev/test_stalepress pinned the bench builds' folder, where other
       versions lay; its "not looked at" passed, and the gate reads exit codes only. A library can write to the wire to the main board by itself
       (the Bluetooth one does): one that has moved on, or a folder that cannot be looked at, stops the release."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('ldrc_pins', os.path.join(HERE, 'test_stalepress', 'test_stalepress.py'))
    pins = importlib.util.module_from_spec(spec); spec.loader.exec_module(pins)
    bad = pins.release_lib_problems(CLEAN)
    if build_log is not None:
        # ... and the framework THIS BUILD SAYS IT USED (PlatformIO names its packages at the head of each build): a second copy of the framework on
        # the machine, taken by a range, would not show in what is installed under the usual name
        used = re.findall(r'^\s*-\s*framework-arduinoespressif32\s*@\s*(\S+)', build_log, re.M)
        if len(used) != 2: bad.append('the build did not say which Arduino framework it used, once for each of its two builds (it said: %s)' % (', '.join(used) or 'nothing'))
        bad += ['the build used the Arduino framework %s, pinned %s' % (u, pins.FRAMEWORK_PIN) for u in sorted(set(used)) if u != pins.FRAMEWORK_PIN]
    if bad:
        sys.exit('REFUSING TO PUBLISH: the screen firmware in dev/out/screen_build is not built with what dev/test_stalepress pins (LIB_PINS, FRAMEWORK_PIN):\n  ' + '\n  '.join(bad)
                 + '\n(LOOK at what changed - can it put a byte on the wire? - then bring the pins up to date.)')
    print('  the screen\'s libraries and framework are the pinned ones')

BUILD_LOG_KEPT = 'release_build.log'
def kept_build_log():
    """--no-build (the thirteenth review, reviewer A's finding 7: the framework's name was read from the build's own output - and with --no-build there was none):
       the output of the build that MADE the images that are there, kept by that build beside them. None kept, or an image newer than it (built again by
       hand since): which framework the images were built with is not known - refused."""
    p = os.path.join(CLEAN, '.pio', 'build', BUILD_LOG_KEPT)
    if not os.path.isfile(p): sys.exit('REFUSING --no-build: the build that made the screen images in dev/out/screen_build left no log beside them (built before B211, or by hand): which Arduino framework they were built with is not known - build them (leave out --no-build)')
    for env in ('ota', 'ota_full'):
        img = os.path.join(CLEAN, '.pio', 'build', env, 'firmware.bin')
        if os.path.isfile(img) and os.path.getmtime(img) > os.path.getmtime(p) + 2: sys.exit(f'REFUSING --no-build: the {env} image in dev/out/screen_build is newer than the log of the release\'s own build: it was built again by hand - build it (leave out --no-build)')
    return open(p, encoding='utf-8', errors='replace').read()

SCREEN_BUILT_FROM = 'release_build.source'    # dev/out/screen_build/.pio/build/release_build.source: what THIS script's build says of the two images it made - screen_images_are_the_builds
def screen_source_files(top):
    """Every file the screen's firmware is built from, in the folder top - the screen's project, or the clean copy of it that the firmware is built
       in (clean_copy): all of src, include, lib and boards, and every file that lies beside them (platformio.ini; a partition table or a build
       script, should platformio.ini ever name one). As for the Teensy (teensy_source_files): no name that begins with a dot. As the clean copy is
       made: no secrets.h - NO FILE WITH "secret" IN ITS NAME IS OPENED HERE (the copy holds none: clean_copy) - and no __pycache__.
       NOT the card's files (sd) and not the page tools (hmi, dev): no firmware is built from them - dev/test_release_gate.py holds the screen's
       platformio.ini to naming nothing else (no build script, no folder of its own). {path below top: full path}"""
    out = {}
    def counts(n): return not n.startswith('.') and 'secret' not in n.lower()
    for n in sorted(os.listdir(top)) if os.path.isdir(top) else []:
        if counts(n) and os.path.isfile(os.path.join(top, n)): out[n] = os.path.join(top, n)
    for part in ('src', 'include', 'lib', 'boards'):
        for d, dirs, names in os.walk(os.path.join(top, part)):
            dirs[:] = sorted(x for x in dirs if not x.startswith('.') and x not in ('__pycache__', 'secrets.h'))
            for n in sorted(names):
                if counts(n): out[os.path.relpath(os.path.join(d, n), top).replace(os.sep, '/')] = os.path.join(d, n)
    return out

def screen_source_hash(top):
    """One number for the screen's whole source (the names and the bytes of screen_source_files): the same for the screen's project and for a clean
       copy just made of it."""
    import hashlib
    h = hashlib.sha256()
    for rel_path, full in sorted(screen_source_files(top).items()):
        b = open(full, 'rb').read(); h.update(rel_path.encode() + b'\0' + str(len(b)).encode() + b'\0' + b)
    return h.hexdigest()[:32]

def screen_build_noted(images, source):
    """The build's own word, written beside its log: the hash of the source it was built from, and which two images it made."""
    open(os.path.join(CLEAN, '.pio', 'build', SCREEN_BUILT_FROM), 'w').write(f'source={source}\nota={package_hash(images[0])}\nota_full={package_hash(images[1])}\n')

def screen_images_are_the_builds(images):
    """B211 (the sixteenth review, reviewer A's finding 4): --no-build HELD THE TEENSY'S PACKAGE TO ITS SOURCE, AND NOT THE SCREEN'S IMAGES TO THEIRS.
       The images built, then a fault cured in the screen's source under the same SCREEN_VERSION, then --no-build: the OLD images were taken, beside
       the new card files. Their version text was right, and no file's time was looked at.
       As for the Teensy (teensy_package_is_the_builds): THIS script's build writes beside its log what it built the two images from - the hash of
       the clean copy's source - and which images it made (screen_build_noted). --no-build takes the images only by that word: the screen's source
       as it is now, the images as they were made. No word (built by hand, or before this rule), another image, another source: refused."""
    p = os.path.join(CLEAN, '.pio', 'build', SCREEN_BUILT_FROM)
    said = dict(l.split('=', 1) for l in open(p, encoding='utf-8', errors='replace').read().splitlines() if '=' in l) if os.path.isfile(p) else {}
    if not said.get('source') or not said.get('ota') or not said.get('ota_full'):
        sys.exit(f'REFUSING --no-build: nothing beside the screen images in dev/out/screen_build says which source they were built from ({SCREEN_BUILT_FROM} is not there, or says nothing: '
                 f'they were built by hand, or before this rule): build them (leave out --no-build)')
    for label, env, b in (('STANDARD', 'ota', images[0]), ('FULL', 'ota_full', images[1])):
        if said[env] != package_hash(b):
            sys.exit(f'REFUSING --no-build: the {label} screen image in dev/out/screen_build is NOT the one this script\'s build made (it was made again since, by hand): build it (leave out --no-build)')
    if said['source'] != screen_source_hash(SCREEN):
        # (which files: the copy the images were built in is still there - if IT is as it was built, what differs from it is what was changed since)
        was, now = (screen_source_files(CLEAN), screen_source_files(SCREEN)) if screen_source_hash(CLEAN) == said['source'] else ({}, {})
        changed = sorted(f for f in set(was) | set(now) if f not in was or f not in now or open(was[f], 'rb').read() != open(now[f], 'rb').read())
        which = ('changed since: ' + ', '.join(changed[:3]) + (f' and {len(changed) - 3} more' if len(changed) > 3 else '')) if changed else 'a file was changed, added or taken away since'
        sys.exit(f'REFUSING --no-build: the screen\'s source is NOT the one the screen images in dev/out/screen_build were built from, whatever SCREEN_VERSION says ({which}): '
                 f'build them (leave out --no-build)')

def screen_firmware(build):
    """The screen's TWO firmwares, from the one source (23 Oct 2026, the three 16 MB screens): STANDARD (env ota) for the
       4 MB boards' 1.9 MB slot, and FULL (env ota_full, -DLDRC_FULL) for the 16 MB boards' 6.25 MB slots. Each image says
       which build it is (LDRCBUILD=standard; / LDRCBUILD=full;) and what flash it was built for (its header): both are
       checked here and again by the gate, so neither can be staged under the other's name. A screen fetches the one for
       the slot it has (the release's "screen" or "screen_full" part; the screen's LdrcUpdate.cpp screenPart())."""
    src = open(os.path.join(SCREEN, 'src', 'main.cpp'), encoding='utf-8').read()
    m = re.search(r'#define\s+SCREEN_VERSION\s+"([^"]+)"', src)
    if not m: sys.exit('SCREEN_VERSION not found in the screen\'s main.cpp')
    if build:
        print('Building the screen firmware, STANDARD and FULL (in a copy of its project that holds no secrets.h) ...')
        word = os.path.join(CLEAN, '.pio', 'build', SCREEN_BUILT_FROM)
        if os.path.exists(word): os.remove(word)                                         # (what an earlier build said is not said of this one, whatever becomes of it)
        clean_copy()
        source = screen_source_hash(CLEAN)                                               # B211 (the sixteenth review): what it is built from - screen_images_are_the_builds
        built = run([PIO, 'run', '-e', 'ota', '-e', 'ota_full'], CLEAN)
        open(os.path.join(CLEAN, '.pio', 'build', BUILD_LOG_KEPT), 'w', encoding='utf-8').write(built)   # (kept for a later --no-build: which framework THESE images were built with)
    else: built = kept_build_log()
    screen_libraries_checked(built)
    images = []
    if build and screen_source_hash(CLEAN) != source: sys.exit('REFUSING TO PUBLISH: the copy the screen\'s firmware is built in (dev/out/screen_build) was CHANGED WHILE it was being built: which of the two the images hold is not known - build them again')
    keep = os.path.join(HERE, 'out', 'elf')
    for env, label, full, limit, header_mb in (('ota', 'STANDARD', False, 0x1E0000, 4), ('ota_full', 'FULL', True, 0x640000, 16)):
        image = os.path.join(CLEAN, '.pio', 'build', env, 'firmware.bin')
        if not os.path.exists(image): sys.exit(f'the screen firmware ({label}) has not been built yet: leave out --no-build')
        b = open(image, 'rb').read()
        found = re.findall(rb'LDRCSCREEN=([^;\0]{1,31});', b)
        if len(set(found)) != 1: sys.exit(f'the screen firmware ({label}) does not say which version it is (LDRCSCREEN=...;)')
        version = found[0].decode()
        if version != m.group(1): sys.exit(f'the screen firmware ({label}) that is built is {version}, the source says {m.group(1)}: build it (leave out --no-build)')
        if b[0] != 0xE9: sys.exit(f'the screen firmware ({label}) is not an ESP32 image')
        if (b'LDRCBUILD=full;' in b) != full or (b'LDRCBUILD=standard;' in b) == full: sys.exit(f'the screen firmware ({label}) does not say it is the {label} build (LDRCBUILD=...;)')
        built_mb = 1 << (b[3] >> 4)                      # the image header: the flash it was built for (2 = 4 MB, 4 = 16 MB)
        if built_mb != header_mb: sys.exit(f'the screen firmware ({label}) is built for a {built_mb} MB flash, not {header_mb} MB: see platformio.ini')
        if len(b) > limit: sys.exit(f'the screen firmware ({label}) is too big for its slot ({len(b)} > {limit} bytes)')
        # The ELF of every screen build that is staged, for reading a crash's core dump against (screen 1.11.15: /status "crash",
        # /coredump): dev/out/elf/screen-<version>.elf and screen-<version>-full.elf
        elf = os.path.join(CLEAN, '.pio', 'build', env, 'firmware.elf')
        if os.path.exists(elf):
            os.makedirs(keep, exist_ok=True)
            shutil.copy2(elf, os.path.join(keep, f'screen-{version}{"-full" if full else ""}.elf'))
        images.append(b)
    if build: screen_build_noted(images, source)       # B211 (the sixteenth review): the build's own word beside its log - which source it built these two images from
    else: screen_images_are_the_builds(images)         # ... and --no-build takes them only by that word, and only for the screen's source as it is now
    # (17 Oct 2026: 74 of them, 32 MB each, helped fill the Mac's disk) the newest sixteen stay here; older ones go to the
    # archive on the 2TB SSD when it is plugged in (still there for an old core dump), else they wait here
    archive = '/Volumes/2TB SSD/LDRC archive/TXV1B screen ELFs'
    if os.path.isdir(archive) and os.path.isdir(keep):
        elves = sorted((e for e in os.listdir(keep) if e.endswith('.elf')), key=lambda e: os.path.getmtime(os.path.join(keep, e)), reverse=True)
        for e in elves[16:]:
            try: shutil.move(os.path.join(keep, e), os.path.join(archive, e))
            except OSError as err: print(f'  (could not move {e} to the archive: {err})')
    return images[0], images[1], version

FLASH_PARTS = (('bootloader', 0x0), ('partitions', 0x8000), ('boot_app0', 0xE000), ('firmware', 0x10000))
BOOT_APP0 = os.path.expanduser('~/.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin')

def flasher_builds(sf, sff):
    """(3 Nov 2026) THE BROWSER FLASHER (messiter.com/ldrc/flash-screen.html, Christoph: a builder should not need
       PlatformIO): everything a bare panel needs over its USB socket, for each build - the bootloader and the partition
       table of the same build as the release's firmware, Arduino's boot_app0 (the first boot choice: the first app slot),
       and the release's own firmware image. The page reads the flash size off the chip and writes the build for it."""
    out = []
    ba = open(BOOT_APP0, 'rb').read()
    if len(ba) != 8192: sys.exit('boot_app0.bin is not the 8 kB the flasher expects')
    for env, fw, mb, build in (('ota', sf, 4, 'standard'), ('ota_full', sff, 16, 'full')):
        folder = os.path.join(CLEAN, '.pio', 'build', env)
        bl = open(os.path.join(folder, 'bootloader.bin'), 'rb').read(); pt = open(os.path.join(folder, 'partitions.bin'), 'rb').read()
        if bl[0] != 0xE9 or 1 << (bl[3] >> 4) != mb: sys.exit(f'the {build} build\'s bootloader is not for a {mb} MB flash')
        if pt[:2] != b'\xAA\x50': sys.exit(f'the {build} build\'s partition table is not one')
        out.append((mb, build, (bl, pt, ba, fw)))
    return out

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

def subtrim_page_checked(scf):
    """B211: THIS FIRMWARE TAKES A CHANGE OF THE SUB-TRIM PAGE ONLY FROM THE PAGE FILE THAT SAYS WHAT IT DID ("StEDIT", the channel, the number as it stood,
    the number it made - Trims.h SubTrimWord); from a page file from before it takes NOTHING. Every release stages the screen's card files as the
    screen project has them: beside the old page 32, every transmitter that took the release would have a Sub-trim page that only shows."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('ldrc_page32', os.path.join(HERE, 'test_wholepage', 'page32.py'))
    p32 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p32)
    b = scf.get('/hmi/pages/32.json')
    if b is None: sys.exit('REFUSING TO PUBLISH: the screen\'s card folder has no Sub-trim page (hmi/pages/32.json)')
    try: kind = p32.page_kind(b)
    except Exception as e:
        sys.exit('REFUSING TO PUBLISH: the Sub-trim page file (the screen project\'s sd/hmi/pages/32.json) is neither the one from before nor this release\'s, word for word - LOOK at it: '
                 'the main board\'s rule (Trims.h) and its tests (dev/test_wholepage/scene_subtrim.py) are written for those two (%s)' % (str(e)[:200] or type(e).__name__))
    if kind != 'new':
        sys.exit('REFUSING TO PUBLISH: the Sub-trim page file in the screen project (sd/hmi/pages/32.json) is the one from BEFORE B211. This firmware takes NOTHING from that page '
                 '(its word does not say what it did): every transmitter that took this release would have a Sub-trim page that only shows. '
                 'Run hmi/subtrim_words.py in the screen project (it goes in with screen 1.11.198), then release.')

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

def release_folder_checked(name):
    """B211 (the fifteenth review): A RELEASE'S FOLDER IS ITS OWN. slug() makes ONE folder name of two release names ("2.5.6 B211 (screen 1.11.198)" and
       "2.5.6 B211 screen 1.11.198"): staging the second wrote over the first one's release.json - its record, and with it the source that
       teensy_version_checked holds every later release against - and nothing was said. A name whose folder holds a release of ANOTHER name is
       refused (looked at in the folder itself: so also two names that this disk takes as one). So is a name that gives no folder at all (no letter
       and no digit in it: its record would lie where no later release looks). The same name is the same release, staged again: written, as before."""
    folder = slug(name)
    if not folder.strip('.'): sys.exit(f'REFUSING TO PUBLISH: the name "{name}" gives the release no folder of its own (it has no letter and no digit in it): give it another name (--name)')
    jp = os.path.join(REL, 'v', folder, 'release.json')
    if not os.path.exists(jp): return
    was = json.load(open(jp)).get('name')
    if was != name: sys.exit(f'REFUSING TO PUBLISH: the name "{name}" has the folder of ANOTHER release, "{was}" (v/{folder}: a folder\'s name is the letters, digits and dots of the release\'s name). '
                             f'That release\'s record would be written over. Give this release a name of its own (--name).')

def stage(notes, build, name, with_screen=True, teensy_unchanged=False):
    tp, tv, tsource = teensy_package(build)   # (tsource: the hash of the source the package was BUILT FROM - recorded with the release, below)
    sf, sff, sv = screen_firmware(build) if with_screen else (None, None, None)
    tf, scf = teensy_files(), screen_files()
    subtrim_page_checked(scf)   # B211: the Sub-trim page file that goes out is this release's (the firmware takes nothing from the one before)
    private = private_values()
    print(f'  looking for {len(private)} private texts of secrets.h in everything that is to be published' if private else '  (there is no secrets.h: nothing private to look for)')
    for label, b in [('the Teensy firmware', tp)] + ([('the screen firmware', sf), ('the 16 MB screen firmware', sff)] if with_screen else []) + list(tf.items()) + list(scf.items()): refuse_private(label, b, private)
    check_paths(tf, ['/help/'], 'the Teensy\'s files'); check_paths(scf, ['/hmi/', '/images/'], 'the screen\'s files')
    if not tf or len(scf) < 100: sys.exit('files are missing: the help texts or the screen\'s card folder')
    name = name or (f"{' '.join(tv.split(' ')[:2])} (screen {sv})" if with_screen else f"{' '.join(tv.split(' ')[:2])} (screen as it is)")
    release_folder_checked(name)                                      # B211 (the fifteenth review): its folder is no other release's
    teensy_version_checked(tv, tp, name, tsource, teensy_unchanged)   # B211: a Teensy firmware that has changed has a version text of its own
    if '\n' in notes or len(notes) > 300: sys.exit('the notes: one line, 300 characters at most')
    new = 0
    names = {}
    for label, b in (('teensy', tp), ('screen', sf), ('screen_full', sff), ('teensy_list', list_text(tf)), ('screen_list', list_text(scf))):
        if b is None: continue
        names[label], fresh = put_blob(b); new += fresh
    for files in (tf, scf):
        for b in files.values(): new += put_blob(b)[1]
    d = {'name': name, 'date': datetime.date.today().isoformat(), 'notes': notes, 'base': BASE,
         'teensy': {'version': tv, 'file': names['teensy'], 'size': len(tp), 'crc': f'{crc(tp):08X}', 'source': tsource},   # (source: release.json only - teensy_version_checked; the screen reads release.txt, which names its own keys)
         'teensy_files': {'file': names['teensy_list'], 'size': len(list_text(tf)), 'crc': f'{crc(list_text(tf)):08X}', 'count': len(tf), 'bytes': sum(map(len, tf.values()))},
         'screen_files': {'file': names['screen_list'], 'size': len(list_text(scf)), 'crc': f'{crc(list_text(scf)):08X}', 'count': len(scf), 'bytes': sum(map(len, scf.values()))}}
    if with_screen:
        d['screen'] = {'version': sv, 'file': names['screen'], 'size': len(sf), 'crc': f'{crc(sf):08X}'}
        d['screen_full'] = {'version': sv, 'file': names['screen_full'], 'size': len(sff), 'crc': f'{crc(sff):08X}'}   # the FULL build, for the 16 MB layout (screens on it take only this)
        d['flash'] = {'version': sv, 'builds': []}             # the browser flasher's (not in release.txt: the screens never read it)
        for mb, build, blobs in flasher_builds(sf, sff):
            parts = []
            for (what, offset), b in zip(FLASH_PARTS, blobs):
                n, fresh = put_blob(b); new += fresh
                parts.append({'what': what, 'path': n, 'offset': offset, 'size': len(b), 'crc': f'{crc(b):08X}'})
            d['flash']['builds'].append({'flash_mb': mb, 'build': build, 'parts': parts})
    write_release(d)
    gone = tidy()
    if gone: print(f'  {gone} files that no release names any more were taken out of the staging folder')
    searched = refuse_private_everywhere(private)
    print(f'  {searched} files in the staging folder searched: nothing private in any of them')
    print(f'\nStaged release "{name}"\n  Teensy firmware  {tv}  ({len(tp) // 1024} kB)\n  screen firmware  ' + (f'{sv}  ({len(sf) // 1024} kB standard, {len(sff) // 1024} kB full for the 16 MB boards)' if with_screen else 'not in this release: screens keep what they have') +
          f'\n  Teensy files     {len(tf)}  ({d["teensy_files"]["bytes"] // 1024} kB)\n  screen files     {len(scf)}  ({d["screen_files"]["bytes"] / 1048576:.1f} MB)'
          f'\n  {new} files are new to the website\n  notes: {notes}\nNext: dev/release_v1b.py publish')

def release_text(d):
    t = f"# Transmitter Version 1B: a release. Read by the screen (\"Check for update\").\nldrc-release=1\nname={d['name']}\ndate={d['date']}\nnotes={d['notes']}\nbase={d['base']}\n"
    for part in PARTS:
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
    release_folder_checked(d['name'])                        # B211 (the fifteenth review): asked again HERE, where the folder is written - whoever calls
    text = release_text(d)
    os.makedirs(os.path.join(REL, 'v', slug(d['name'])), exist_ok=True)
    open(os.path.join(REL, 'v', slug(d['name']), 'release.txt'), 'w').write(text)
    json.dump(d, open(os.path.join(REL, 'v', slug(d['name']), 'release.json'), 'w'), indent=1)
    open(os.path.join(REL, 'latest.txt'), 'w').write(text)
    write_teensy_hex(d['teensy']['file'])                    # (10 Nov 2026) the same firmware as a HEX file, for a new Teensy's first flash
    if 'flash' in d:                                         # (an older release made latest again has none: the flasher keeps the newest it had)
        json.dump({'product': 'LDRC V2 screen', 'release': d['name'], 'version': d['flash']['version'], 'builds': d['flash']['builds']},
                  open(os.path.join(REL, 'flash-screen.json'), 'w'), indent=1)
    mpath = os.path.join(REL, 'manifest.json')
    versions = json.load(open(mpath))['versions'] if os.path.exists(mpath) else []
    versions = [v for v in versions if v['name'] != d['name']]
    versions.insert(0, {'name': d['name'], 'date': d['date'], 'notes': d['notes'], 'teensy': d['teensy']['version'], 'screen': d.get('screen', {}).get('version', 'as it is'),
                        'description': BASE + 'v/' + slug(d['name']) + '/release.txt'})
    pretty = dict(d); pretty['description'] = BASE + 'latest.txt'
    for part in PARTS:
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
        for build in r.get('flash', {}).get('builds', []):   # the browser flasher's parts (3 Nov 2026)
            for p in build['parts']: names.add(p['path'])
        for part in PARTS:
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

def staged_has_screen():
    """The staged release holds a screen's firmware (not: the Teensy's alone). Asked by gate(), softly - publish() has read the description already."""
    try: return any(l.startswith('screen.file=') for l in open(os.path.join(REL, 'latest.txt')).read().splitlines())
    except OSError: return False

def wanted(d):
    """Every file of the staged release: {name on the site: bytes}."""
    out = {}
    for part in PARTS:
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

def test_passed(returncode, output):
    """B211 (the fifteenth review): A TEST THAT DID NOT RUN HAS NOT PASSED. The scenes that run the Sub-trim page's REAL file need the screen project's
       script interpreter beside this repository; without it they said "ALL GOOD" and ended with 0 - and this gate read the 0. A scene that cannot
       run says "NOT RUN: ..." (dev/test_wholepage hands the line on, and still ends with 0 for whoever has only this repository): here that is a
       refusal."""
    return returncode == 0 and re.search(r'^\s*NOT RUN\b', output, re.M) is None

def gate_tests():
    """the main board's own host tests: dev/test_*/test_*.py - and dev/test_release_gate.py, this script's own, which stands beside the folders
       (B211, the fifteenth review: the pattern alone never ran it)"""
    import glob
    return sorted(glob.glob(os.path.join(HERE, 'test_*', 'test_*.py'))) + [os.path.join(HERE, 'test_release_gate.py')]

TEST_SWITCHES = (   # EVERY VARIABLE A TEST READS FROM THE ENVIRONMENT - ONE LIST. A new one goes here (dev/test_release_gate.py finds a name that is not on it).
    'LDRC_RUNS_ONLY',                                     # test_wholepage (scene_subtrim, scene_trims_box): the source checks are set aside
    'LDRC_NEW_PAGE32',                                    # test_wholepage (scene_subtrim): another file is taken as this release's Sub-trim page
    'RB_RESCUE_H', 'RB_TRAVEL_H',                         # test_wholepage (scene_rescue_switch, scene_stale_block, scene_travel_dir): another header than the tree's is run
    'TXV1B_TC', 'V2_SCREEN',                              # test_banks, test_curve_marker, test_curve_points, test_curve_type, test_models_file: ANOTHER tree is tested
    'NO_SSD',                                             # test_tools: a made-up backup in place of the real one that lies beside it
    'ELRS_SIM_KEEP', 'RC_SCENARIO', 'RC_DOTS', 'WORDS',   # test_elrs, test_rates, test_tools: a file is written where the variable says
    'A16_TELL', 'ETA_TRACE')                              # test_wholepage (scene_subtrim_door_storm), the screen project's hmi/test_update: more is printed

def test_env():
    """B211 (the sixteenth review, reviewer A's finding 3): A VARIABLE LEFT IN THE SHELL SWITCHED THE GATE'S CHECKS OFF WITHOUT A WORD. The tests have
       switches of their own, for the work on them (TEST_SWITCHES): LDRC_RUNS_ONLY sets the Sub-trim scenes' source checks aside, TXV1B_TC makes five
       tests look at another tree. gate() handed the shell's environment on: with LDRC_RUNS_ONLY=1 left set, a tree with a rule taken out that only
       a source check holds passed - "ALL GOOD", and not a line about checks set aside.
       As build_env does for the builds: no such variable reaches a test the gate runs. It says which it left out - their names, not what they held."""
    left = sorted(k for k in os.environ if k.upper() in TEST_SWITCHES)
    if left: print('  (NOT passed on to the tests: ' + ', '.join(left) + ' - the gate runs every check, and on this tree)')
    return {k: v for k, v in os.environ.items() if k.upper() not in TEST_SWITCHES}

def gate():
    """The screen's own parser reads the staged release (the host tests of the screen's project): what it refuses is not published.
       First the main board's own host tests (gate_tests, B61): one that fails - or did not run (test_passed) - stops the release.
       None of them is handed a switch of the tests' own that was left in the shell (test_env)."""
    env = test_env()
    with_screen = staged_has_screen()   # (a release of the Teensy's firmware alone builds no screen: what --gate asks of the folder the screen is built in is not asked of it)
    for t in gate_tests():
        r = subprocess.run([sys.executable, t] + (['--gate'] if with_screen and os.path.basename(t) == 'test_release_gate.py' else []), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)   # (--gate: what that test passes over in brackets beside a working copy is NOT RUN at the gate)
        print('  ' + r.stdout.strip().replace('\n', '\n  '))
        if not test_passed(r.returncode, r.stdout): sys.exit(f'REFUSING TO PUBLISH: {os.path.basename(t)} failed, or a part of it did not run (above).')
    test = os.path.join(SCREEN, 'hmi', 'test_update', 'run.sh')
    r = subprocess.run([test, '--release', REL], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
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
        r = json.load(open(jp)); hit = [part for part in PARTS if part in r and r[part]['file'] in names]
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

def flasher_files():
    """The browser flasher's list and its parts, as staged: {name on the site: bytes} (empty when there is no list)."""
    p = os.path.join(REL, 'flash-screen.json')
    if not os.path.exists(p): return {}
    out = {'flash-screen.json': open(p, 'rb').read()}
    for build in json.loads(out['flash-screen.json'])['builds']:
        for part in build['parts']:
            b = open(os.path.join(REL, part['path']), 'rb').read()
            if len(b) != part['size'] or f'{crc(b):08X}' != part['crc']: sys.exit(f'{part["path"]} (the flasher\'s {part["what"]}) is damaged in the staging folder: stage again')
            out[part['path']] = b
    return out

def publish():
    text, d = staged(); files = wanted(d)
    flasher = flasher_files()
    files.update({n: b for n, b in flasher.items() if n != 'flash-screen.json'})   # (read back with the rest, before anything points at them)
    hexfile = write_teensy_hex(d['teensy.file'])             # the Teensy's HEX file, made again from the package that is being published
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
        for part in PARTS:
            if part + '.file' not in rd: continue         # (screen_full: a release from before the two builds has none; the four others whole() has seen)
            n = rd[part + '.file']
            if n in files: continue                       # read back already, as part of the latest
            status, body = fetch(conn, n)
            if status != 200 or len(body) != int(rd[part + '.size']) or f'{crc(body):08X}' != rd[part + '.crc']: bad.append(f'{n} of {rd["name"]} ({status})')
    if bad: sys.exit('NOT PUBLISHED: an earlier release is not whole on messiter.com:\n  ' + '\n  '.join(bad[:20]))
    script = ('set ftp:ssl-allow yes\nset ssl:verify-certificate no\nset net:max-retries 3\n'
              + ('put -O public_html/txv1b/release txv1b/release/flash-screen.json\n' if flasher else '') +
              'put -O public_html/txv1b/release txv1b/release/' + TEENSY_HEX + '\n'
              'put -O public_html/txv1b/release txv1b/release/manifest.json\nput -O public_html/txv1b/release txv1b/release/recent.txt\nput -O public_html/txv1b/release txv1b/release/latest.txt\nquit\n')
    r = subprocess.run(['lftp', '--env-password', '-u', env['LDRC_FTP_USER'], env['LDRC_FTP_HOST']], input=script, cwd=SITE, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.returncode: sys.exit(r.stdout[-1500:] + '\nFAILED: the upload of latest.txt')
    status, body = fetch(conn, 'latest.txt?n=' + str(os.getpid()))
    if status != 200 or body.decode(errors='replace') != text: sys.exit(f'latest.txt on messiter.com is not the one staged ({status})')
    if flasher:
        status, body = fetch(conn, 'flash-screen.json?n=' + str(os.getpid()))
        if status != 200 or body != flasher['flash-screen.json']: sys.exit(f'flash-screen.json on messiter.com is not the one staged ({status})')
    status, body = fetch(conn, TEENSY_HEX + '?n=' + str(os.getpid()))
    if status != 200 or body != hexfile: sys.exit(f'{TEENSY_HEX} on messiter.com is not the one staged ({status}): a new Teensy would be flashed with something else')
    status, body = fetch(conn, 'recent.txt?n=' + str(os.getpid()))
    if status != 200 or body.decode(errors='replace') != rtext: sys.exit(f'recent.txt on messiter.com is not the one staged ({status})')
    print(f'{rcount} releases can be gone back to ("Earlier versions"):', ', '.join(l.split('=', 1)[1].split('|')[0] for l in rtext.splitlines() if l.startswith('release=')))
    print(f'PUBLISHED: "{d["name"]}" is the latest release.\n  Teensy {d["teensy.version"]}, screen {d.get("screen.version", "as it is")}' + (' (standard and full)' if 'screen_full.file' in d else '') + f', {d["teensy_files.count"]} help files, {d["screen_files.count"]} screen files'
          f'\n  {BASE}latest.txt\n  {BASE}{TEENSY_HEX}  (a new Teensy\'s first flash, with Teensy Loader: {len(hexfile) // 1024} kB)')
    # The public repository (github.com/Mmessiter/LDRC_V2) gets the same release as a snapshot, committed and pushed
    # (Malcolm, 2026-10-05: "Go!" - Version 2 is public).
    r = subprocess.run([sys.executable, os.path.join(HERE, 'publish_public.py'), '--push'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(('  public repository: ' + r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else ('  public repository NOT updated:\n' + r.stdout[-1500:]))

def status():
    conn = [None]
    s, body = fetch(conn, 'latest.txt?n=' + str(os.getpid()))
    if s == 200:
        d = dict(l.split('=', 1) for l in body.decode(errors='replace').splitlines() if '=' in l and not l.startswith('#'))
        print(f'live:    "{d.get("name")}" of {d.get("date")}  Teensy {d.get("teensy.version")}, screen {d.get("screen.version", "as it is")}' + (' (standard and full)' if 'screen_full.file' in d else ' (standard only: no 16 MB build)') + f'\n         {d.get("notes")}')
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
    ap.add_argument('--teensy-source-unchanged', action='store_true', help='(once, for a release of the screen alone) the Teensy\'s source has not changed since the earlier release with this Teensy version')
    a = ap.parse_intermixed_args()
    if a.what == 'stage':
        if len(a.text) != 1: sys.exit('say what is new: dev/release_v1b.py stage "what is new"')
        stage(a.text[0], not a.no_build, a.name, not a.without_screen, a.teensy_source_unchanged)
    elif a.what == 'publish': publish()
    elif a.what == 'status': status()
    elif a.what == 'purge': purge(a.text)
    else: latest(a.text[0] if a.text else '')

if __name__ == '__main__':
    main()
