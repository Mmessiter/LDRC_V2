#!/usr/bin/env python3
"""The gate that keeps private texts off the website (dev/release_v1b.py private_values, refuse_private), tried
   against a MAKE-BELIEVE secrets.h written here, in a temporary folder. The real include/secrets.h is never opened:
   the tool is pointed at the temporary folder before anything of it is called.

   Found by review on 29-9-2026: the gate read only lines of the form  #define NAME "value"  with nothing behind them,
   only names with PASS, KEY, SECRET or TOKEN in them, only values of 8 bytes or more. Everything else was published."""
import sys, os, tempfile, importlib.util
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('rel', os.path.join(HERE, 'release_v1b.py'))
rel = importlib.util.module_from_spec(spec); spec.loader.exec_module(rel)

FAKE = r'''// a make-believe secrets.h: every form a line can take
#define WIFI_SSID "Make Believe"
#define WIFI_PASS "horse-battery-1"
#define HOTSPOT_PASS "staple-99-xyz"   // my phone
#define CLUB_PASS "club-field-26" /* the club */
#define HOTSPOT_PW "pw-not-named-so"
#define HOUSE_WIFI "just-the-house-1"
#define OTA_PASS "short7!"
#  define SPACED_PASS   "spaced-define-1"
#define SPLIT_PASS "first-half-" "second"
static const char *CONST_PASS = "const-char-pass";
#define UTF_PASS "caf\xC3\xA9-au-lait"
#define TAB_PASS "tab\there-12"
#define QUOTE_PASS "with\"quote-123"
#define CONT_PASS \
    "continued-line-1"
#define PAREN_PASS ("in-brackets-12")
#define OCTAL_PASS "oct\101l-pass-1"
'''
COMPILED = {   # what a C compiler puts into the program
    'WIFI_PASS': b'horse-battery-1', 'HOTSPOT_PASS': b'staple-99-xyz', 'CLUB_PASS': b'club-field-26', 'HOTSPOT_PW': b'pw-not-named-so', 'HOUSE_WIFI': b'just-the-house-1',
    'OTA_PASS': b'short7!', 'SPACED_PASS': b'spaced-define-1', 'SPLIT_PASS': b'first-half-second', 'CONST_PASS': b'const-char-pass',
    'UTF_PASS': 'café-au-lait'.encode(), 'TAB_PASS': b'tab\there-12', 'QUOTE_PASS': b'with"quote-123', 'CONT_PASS': b'continued-line-1', 'PAREN_PASS': b'in-brackets-12',
    'OCTAL_PASS': b'octAl-pass-1', 'WIFI_SSID': b'Make Believe' }

failures = checks = 0
def check(ok, what):
    global failures, checks
    checks += 1
    if not ok: failures += 1; print('   FAIL:', what)
not_run = []
def did_not_run(what):
    """B211 (the sixteenth review, reviewer A's finding 1): A PART OF THIS TEST THAT COULD NOT RUN SAYS SO, AND THE TEST HAS NOT PASSED. A file it needs that
       was not there was passed over with a line in brackets: six checks fewer, "0 failures", the return code 0 - and the release's gate took that for a pass.
       The line begins "NOT RUN:" (what release_v1b.py test_passed looks for); the last line says it again, and this script does not end with 0."""
    not_run.append(what); print('NOT RUN: ' + what)

with tempfile.TemporaryDirectory() as tmp:
    os.makedirs(os.path.join(tmp, 'screen', 'include')); os.makedirs(os.path.join(tmp, 'empty', 'include')); os.makedirs(os.path.join(tmp, 'odd', 'include'))
    open(os.path.join(tmp, 'screen', 'include', 'secrets.h'), 'w', encoding='utf-8').write(FAKE)
    open(os.path.join(tmp, 'odd', 'include', 'secrets.h'), 'w').write('#define WIFI_PASS password_without_quotes\n')
    rel.SCREEN = os.path.join(tmp, 'screen')
    private = rel.private_values()
    print('- every text of a make-believe secrets.h is watched for, whatever its line looks like')
    for name, value in COMPILED.items():
        firmware = b'\xE9' + os.urandom(4000) + b'\0' + value + b'\0' + os.urandom(4000)
        try: rel.refuse_private('the screen firmware', firmware, private); caught = False
        except SystemExit: caught = True
        check(caught, f'a firmware that holds {name} is refused')
    print('- a firmware that holds none of them is not refused')
    try: rel.refuse_private('the screen firmware', b'\xE9' + bytes(range(256)) * 40, private); check(True, '')
    except SystemExit: check(False, 'a clean firmware was refused')
    print('- the refusal names what was found, and never says the value')
    try: rel.refuse_private('f', b'x' + COMPILED['WIFI_PASS'] + b'y', private); said = ''
    except SystemExit as e: said = str(e)
    check('WIFI_PASS' in said and COMPILED['WIFI_PASS'].decode() not in said, 'the name is given, the value is not')
    print('- a secrets.h in which nothing can be read stops everything')
    rel.SCREEN = os.path.join(tmp, 'odd')
    try: rel.private_values(); check(False, 'it went on')
    except SystemExit: check(True, '')
    print('- no secrets.h at all: nothing to look for (the firmware is built from a copy without one in any case)')
    rel.SCREEN = os.path.join(tmp, 'empty')
    check(rel.private_values() == {}, 'an empty set')
    print('- names the transmitter must refuse are refused at staging')
    for bad in ('/help/AUDIO.TXT.', '/help/AUDIO.TXT ', '/help /AUDIO.TXT', '/ help/AUDIO.TXT', '/help./AUDIO.TXT', '/help/' + 'A' * 90 + '.TXT', '/LINK.TMP', '/link.old'):
        try: rel.check_paths({bad: b''}, ['/help/', '/LINK', '/link', '/ help', '/help'], 'test'); check(False, f'"{bad}" was accepted')
        except SystemExit: check(True, '')
    try: rel.check_paths({'/help/AUDIO.TXT': b'', '/help/RF GOV (1).TXT': b''}, ['/help/'], 'test'); check(True, '')
    except SystemExit: check(False, 'an ordinary name was refused')

# (10 Nov 2026) The Teensy's HEX file for a first flash with Teensy Loader: read back by ANOTHER reader (the one that makes
# the update package from PlatformIO's own HEX file, dev/make_fw_package.py) it must give the package's image again.
print('- the Teensy firmware as a HEX file: read back by the package maker\'s own reader, it is the package\'s image')
import zlib, struct
spec2 = importlib.util.spec_from_file_location('pkg', os.path.join(HERE, 'make_fw_package.py'))
pkg = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(pkg)
image = bytearray(b'\xFF' * (3 * 65536 + 4096))
image[0:512] = bytes(range(256)) * 2                       # the flash configuration block
image[0x1000:0x1040] = b'\xD1\x00\x20\x43' * 16           # the vector table, after a gap of FF
image[65530:65550] = bytes(range(20))                      # across a 64 kB boundary
image[2 * 65536 + 17:2 * 65536 + 18] = b'\x00'             # one byte alone in its row
image[-16:] = b'the last 16 byte'
image = bytes(image)
package = b'LDRCFW01' + struct.pack('<II', len(image), zlib.crc32(image) & 0xFFFFFFFF) + b'2.5.6 test'.ljust(32, b'\0') + b'fw_teensy41'.ljust(16, b'\0') + image
hexfile = rel.teensy_hex(package)
with tempfile.TemporaryDirectory() as tmp2:
    hp = os.path.join(tmp2, 't.hex'); open(hp, 'wb').write(hexfile)
    mem = pkg.read_hex(hp)
check(all(mem.get(0x60000000 + i, 0xFF) == b for i, b in enumerate(image)) and all(0x60000000 <= a < 0x60000000 + len(image) for a in mem), 'every byte of the image, at its address in the flash, and nothing outside it')
check(hexfile.startswith(b':020000046000') and hexfile.endswith(b':00000001FF\r\n') and all(len(l) <= 43 for l in hexfile.split(b'\r\n')), 'it begins at 0x60000000, ends with the end record, 16 bytes a record at most')
check(len(mem) < len(image) // 2, 'rows of nothing but FF are left out')
try: rel.teensy_hex(package[:64] + image[:-16] + b'\xFF' * 16) and check(True, '')
except SystemExit: check(False, 'an image that ends in FF was refused')

# B211 (the twelfth review, reviewer A's finding 3): THE LIBRARIES OF THE BUILD THAT IS PUBLISHED. dev/test_stalepress pinned the BENCH builds' folder
# (other versions lay there), its "not looked at" passed, and this script's gate read exit codes only. The release script now looks itself, in the
# folder it builds in, after its build - and stops for a difference, and for a folder it cannot look at.
print('- the screen\'s libraries: the release script looks at the folder it builds in, and refuses a difference - or a folder it cannot look at')
import re as _re, json as _json, shutil as _shutil
src_rel = open(os.path.join(HERE, 'release_v1b.py'), encoding='utf-8').read(); live_rel = _re.sub(r'#[^\n]*', '', src_rel)
check(_re.search(r"built = run\(\[PIO, 'run', '-e', 'ota', '-e', 'ota_full'\], CLEAN\)\s*open\(os\.path\.join\(CLEAN, '\.pio', 'build', BUILD_LOG_KEPT\), 'w', encoding='utf-8'\)\.write\(built\)\s*else: built = kept_build_log\(\)\s*screen_libraries_checked\(built\)\s*images = \[\]", live_rel) is not None,
      'screen_firmware looks at the libraries behind its build, with that build\'s own output - kept for a later --no-build, which reads it - and before an image is taken')
check('pins.release_lib_problems(CLEAN)' in src_rel and _re.search(r"if bad:\s*sys\.exit\('REFUSING TO PUBLISH", src_rel) is not None, 'a problem stops the release')
spec3 = importlib.util.spec_from_file_location('pins', os.path.join(HERE, 'test_stalepress', 'test_stalepress.py'))
pins = importlib.util.module_from_spec(spec3); spec3.loader.exec_module(pins)
with tempfile.TemporaryDirectory() as tmp3:
    INI = '[env:crowpanel50]\nplatform = espressif32 @ 7.0.1\nlib_deps =\n' + ''.join('    someone/%s @ %s\n' % (a, b) for a, b, c in pins.LIB_PINS) + '[env:ota]\nextends = env:crowpanel50\n[env:ota_full]\nextends = env:crowpanel50\n'
    def folder(versions, envs=pins.LIB_ENVS, ini=True, more=None):
        d = tempfile.mkdtemp(dir=tmp3)
        if ini: open(os.path.join(d, 'platformio.ini'), 'w').write(INI)
        for env in envs:
            for name, ver in list(versions.items()) + list((more or {}).items()):
                q = os.path.join(d, '.pio', 'libdeps', env, name); os.makedirs(q)
                open(os.path.join(q, 'library.json'), 'w').write(_json.dumps({'name': name, 'version': ver})); open(os.path.join(q, 'a.cpp'), 'w').write('// ' + name)
        return d
    asPinned = {a: b for a, b, c in pins.LIB_PINS}
    made = pins.lib_pins(folder(asPinned), INI)                       # (a make-believe folder: its files are not the libraries' - pinned by what IT holds, for this test)
    kept, keptFw = pins.LIB_PINS, pins.framework_now
    pins.LIB_PINS = made; pins.framework_now = lambda: pins.FRAMEWORK_PIN
    check(isinstance(made, list) and len(made) == len(kept) and pins.release_lib_problems(folder(asPinned)) == [], 'a folder built with the pinned libraries and framework: nothing to say')
    moved = dict(asPinned, **{'NimBLE-Arduino': '9.9.9'})
    r = pins.release_lib_problems(folder(moved)); check(len(r) == 1 and 'NimBLE-Arduino' in r[0] and 'CHANGED' in r[0], 'a library that has moved on to another version is named')
    r = pins.release_lib_problems(folder(asPinned, envs=())); check(len(r) == 1 and 'could not be looked at' in r[0], 'a folder with no libraries in it - never built - is a problem, not a note')
    r = pins.release_lib_problems(folder(asPinned, ini=False)); check(len(r) == 1 and 'platformio.ini' in r[0], 'a folder with no platformio.ini is a problem')
    r = pins.release_lib_problems(folder(asPinned, envs=('ota',))); check(len(r) == 1, 'a folder where only one of the two builds was made is a problem')
    gone = dict(asPinned); gone.pop('JPEGDEC')
    r = pins.release_lib_problems(folder(gone)); check(any('no longer' in x and 'JPEGDEC' in x for x in r), 'a pinned library that is not in the build is named')
    pins.framework_now = lambda: '3.20017.999999+sha.0000000'
    r = pins.release_lib_problems(folder(asPinned)); check(len(r) == 1 and 'framework' in r[0], 'the Arduino framework moved on: named')
    pins.framework_now = lambda: None
    r = pins.release_lib_problems(folder(asPinned)); check(len(r) == 1 and 'not to be found' in r[0], 'the Arduino framework not to be found on this machine: a problem')
    pins.LIB_PINS, pins.framework_now = kept, keptFw
    # ... and the release script's own routine stops on it (pointed at a folder never built)
    keptClean = rel.CLEAN; rel.CLEAN = folder(asPinned, envs=()); stopped = ''
    try: rel.screen_libraries_checked()
    except SystemExit as e: stopped = str(e)
    rel.CLEAN = keptClean
    check('REFUSING TO PUBLISH' in stopped and 'could not be looked at' in stopped, 'release_v1b.py screen_libraries_checked stops the release for a folder it cannot look at')
    # ... and for a build that SAYS it used another framework than the pinned one - or does not say - though what is installed is right
    def stops(log):
        try: rel.screen_libraries_checked(log)
        except SystemExit as e: return str(e)
        return ''
    LOG = 'Processing ota\nPACKAGES: \n - framework-arduinoespressif32 @ %s \n - tool-esptoolpy @ 2.41100.0 (4.11.0) \nProcessing ota_full\nPACKAGES: \n - framework-arduinoespressif32 @ %s \n'
    rel.CLEAN = folder(asPinned)
    s1 = stops(LOG % ('3.20017.999999+sha.0000000', pins.FRAMEWORK_PIN)); check('the build used the Arduino framework 3.20017.999999+sha.0000000' in s1, 'a build that says it used another framework - in one of its two builds - stops the release')
    s2 = stops('Processing ota\nnothing said\n'); check('did not say which Arduino framework it used' in s2, 'a build that does not say which framework it used stops the release')
    s3 = stops(LOG % (pins.FRAMEWORK_PIN, pins.FRAMEWORK_PIN)); check('the build used' not in s3 and 'did not say' not in s3, 'a build that names the pinned framework twice is not stopped for its framework')
    rel.CLEAN = keptClean
# B211 (the thirteenth review, reviewer A's findings 3 and 7): THE RELEASE IS BUILT FROM ITS platformio.ini ALONE; what is staged is looked INTO; the pins tie down more
print('- no PLATFORMIO_* variable of the shell reaches a build; a TEST build of the Teensy firmware is refused; --no-build reads the log of the build that made the images')
import time as _time
keptEnv = dict(os.environ)
os.environ['PLATFORMIO_BUILD_FLAGS'] = '-DELRS_TEST'; os.environ['PLATFORMIO_LIBDEPS_DIR'] = '/somewhere/else'; os.environ['platformio_extra_scripts'] = 'pre:x.py'
with tempfile.TemporaryDirectory() as tmp4:
    import io as _io, contextlib as _ctx
    with _ctx.redirect_stdout(_io.StringIO()) as said:
        seen = rel.run([sys.executable, '-c', 'import os; print(sorted(k for k in os.environ if k.upper().startswith("PLATFORMIO_")), os.environ.get("HOME", "") != "")'], tmp4)
    check(seen.strip() == '[] True', 'a command the release script runs sees none of the shell\'s PLATFORMIO_* variables (and the rest of the environment as it is): ' + seen.strip())
    check('PLATFORMIO_BUILD_FLAGS' in said.getvalue() and 'PLATFORMIO_LIBDEPS_DIR' in said.getvalue() and '-DELRS_TEST' not in said.getvalue(), 'it says which were not passed on - their names, not what they held')
os.environ.clear(); os.environ.update(keptEnv)
check(len(_re.findall(r'subprocess\.(?:run|Popen|call|check_call|check_output)\(', live_rel)) == len(_re.findall(r'subprocess\.run\(', live_rel)) and
      all('env=build_env()' in l or 'pio' not in l.lower() for l in live_rel.split('\n') if 'subprocess.run(' in l) and "run([PIO, 'run', '-e', 'teensy41'], TEENSY)" in live_rel and live_rel.count('[PIO,') == 2,
      'both builds - the Teensy\'s and the screen\'s - are started through run(), which takes the PLATFORMIO_* variables out')
def a_package(image, version=b'2.5.7 B211 15/11/26'):
    return b'LDRCFW01' + struct.pack('<II', len(image), zlib.crc32(image) & 0xFFFFFFFF) + version.ljust(32, b'\0') + b'fw_teensy41'.ljust(16, b'\0') + image
plain = bytes(range(256)) * 64 + b'fw_teensy41\0' + b'2.5.7 B211 15/11/26\0' + b'Motor On\0' * 40
try: back = rel.checked_teensy_package(a_package(plain), 'a package'); check(back[1] == '2.5.7 B211 15/11/26', 'a release build of the Teensy firmware is taken, with its version')
except SystemExit as e: check(False, 'a release build was refused: ' + str(e))
for what, text in (('one line of the ELRS driver', b'ELRS test: module power ON (pin 10 high); the serial line starts in 0.3 s\0'), ('the mark at the image\'s very end', b'ELRS test')):
    try: rel.checked_teensy_package(a_package(plain + text), 'a package'); stopped = ''
    except SystemExit as e: stopped = str(e)
    check('REFUSING TO PUBLISH' in stopped and 'TEST build' in stopped, 'a Teensy package that holds a TEST build\'s text is refused (' + what + ')')
elrs = open(os.path.join(HERE, '..', 'TransmitterCode', 'include', 'ElrsCrsf.h'), encoding='utf-8', errors='replace').read()
check(len(_re.findall(r'"ELRS test', elrs)) >= 10 and _re.search(r'ElrsSay\(PSTR\("ELRS test: module power ON', elrs) is not None, 'the mark is what the ELRS driver says (ElrsCrsf.h): a test build holds it')
src_all = ''.join(open(os.path.join(d, f), encoding='utf-8', errors='replace').read() for top in ('include', 'src') for d, _, fs in os.walk(os.path.join(HERE, '..', 'TransmitterCode', top)) for f in sorted(fs) if f.endswith(('.h', '.cpp')) and f != 'ElrsCrsf.h')
check('ELRS test' not in src_all, 'no other file of the Teensy\'s source holds the mark: a release build cannot hold it')
with tempfile.TemporaryDirectory() as tmp5:
    keptClean = rel.CLEAN; rel.CLEAN = tmp5
    for env in ('ota', 'ota_full'): os.makedirs(os.path.join(tmp5, '.pio', 'build', env)); open(os.path.join(tmp5, '.pio', 'build', env, 'firmware.bin'), 'wb').write(b'\xE9image')
    def refused():
        try: rel.kept_build_log()
        except SystemExit as e: return str(e)
        return ''
    check('left no log' in refused(), '--no-build with no log of the build that made the images: refused')
    logp = os.path.join(tmp5, '.pio', 'build', rel.BUILD_LOG_KEPT); open(logp, 'w').write('PACKAGES:\n - framework-arduinoespressif32 @ 9.9.9\n')
    check(refused() == '' and '9.9.9' in rel.kept_build_log(), '... with it: its text is what the framework is read from')
    old = _time.time() - 3600; os.utime(logp, (old, old))
    check('newer than the log' in refused(), '... an image built again since (newer than the log): refused')
    rel.CLEAN = keptClean
with tempfile.TemporaryDirectory() as tmp6:
    def lib_folder(more=None, image_age=None):
        d = tempfile.mkdtemp(dir=tmp6); open(os.path.join(d, 'platformio.ini'), 'w').write(INI6)
        for env in pins.LIB_ENVS:
            for name, ver in list(asPinned6.items()) + list((more or {}).items()):
                q = os.path.join(d, '.pio', 'libdeps', env, name); os.makedirs(q)
                open(os.path.join(q, 'library.json'), 'w').write(_json.dumps({'name': name, 'version': ver})); open(os.path.join(q, name + '.h'), 'w').write('// ' + name)
            if image_age is not None:
                os.makedirs(os.path.join(d, '.pio', 'build', env)); img = os.path.join(d, '.pio', 'build', env, 'firmware.bin'); open(img, 'wb').write(b'\xE9image')
                when = _time.time() + image_age; os.utime(img, (when, when))
        return d
    asPinned6 = {a: b for a, b, c in pins.LIB_PINS}
    INI6 = '[env:crowpanel50]\nplatform = espressif32 @ 7.0.1\nlib_deps =\n' + ''.join('    someone/%s @ %s\n' % (a, b) for a, b, c in pins.LIB_PINS) + '[env:ota]\nextends = env:crowpanel50\n[env:ota_full]\nextends = env:crowpanel50\n'
    kept6 = (pins.LIB_PINS, pins.framework_now, pins.framework_files_now)
    pins.LIB_PINS = pins.lib_pins(lib_folder(), INI6); pins.framework_now = lambda: pins.FRAMEWORK_PIN; pins.framework_files_now = lambda top=None: pins.FRAMEWORK_FILES_PIN
    check(pins.release_lib_problems(lib_folder(image_age=60)) == [], 'the pinned libraries, the images newer than they: nothing to say')
    r = pins.release_lib_problems(lib_folder(more={'Chatty': '1.0.0'})); check(len(r) == 1 and 'NEW' in r[0] and 'Chatty' in r[0], 'a library that platformio.ini does not name and that has no built folder of its own (header-only) is seen: ' + repr(r)[:200])
    r = pins.release_lib_problems(lib_folder(image_age=-86400 * 30)); check(len(r) == 2 and all('OLDER than the libraries' in x for x in r), 'an image a month older than the libraries beside it - each of the two builds: ' + repr(r)[:200])
    pins.framework_files_now = lambda top=None: '0' * 16
    r = pins.release_lib_problems(lib_folder()); check(len(r) == 1 and 'files of the Arduino framework' in r[0], 'the framework\'s version as pinned, a file of it changed: seen')
    pins.LIB_PINS, pins.framework_now, pins.framework_files_now = kept6
    # ... and the framework's pin itself sees one changed byte of one file (a make-believe framework: its parts, as the real one has them)
    fw = os.path.join(tmp6, 'fw')
    for rel_, text in (('package.json', '{"version": "1"}'), ('cores/esp32/HardwareSerial.cpp', 'void begin() {}'), ('libraries/WiFi/src/WiFi.cpp', '//'), ('variants/esp32s3/pins_arduino.h', '//'),
                       ('tools/platformio-build.py', '#'), ('tools/platformio-build-esp32s3.py', '#'), ('tools/partitions/default.csv', 'x'), ('tools/sdk/esp32s3/lib/libdriver.a', 'AR')):
        os.makedirs(os.path.dirname(os.path.join(fw, rel_)), exist_ok=True); open(os.path.join(fw, rel_), 'w').write(text)
    h0 = pins.framework_files_now(fw); seen = 0
    for rel_ in ('cores/esp32/HardwareSerial.cpp', 'libraries/WiFi/src/WiFi.cpp', 'variants/esp32s3/pins_arduino.h', 'tools/platformio-build-esp32s3.py', 'tools/partitions/default.csv', 'tools/sdk/esp32s3/lib/libdriver.a', 'package.json'):
        was = open(os.path.join(fw, rel_)).read(); open(os.path.join(fw, rel_), 'w').write(was + ' '); seen += pins.framework_files_now(fw) != h0; open(os.path.join(fw, rel_), 'w').write(was)
    open(os.path.join(fw, 'cores', 'esp32', 'new.cpp'), 'w').write('//'); seen += pins.framework_files_now(fw) != h0; os.remove(os.path.join(fw, 'cores', 'esp32', 'new.cpp'))
    check(h0 is not None and seen == 8 and pins.framework_files_now(fw) == h0 and pins.framework_files_now(os.path.join(tmp6, 'none')) is None, 'the framework\'s pin: a byte changed in any of its parts, or a file more, is seen (%d of 8); the same files give the same pin' % seen)
if os.path.exists(os.path.join(pins.RELEASE_SCREEN, '.pio', 'libdeps')):
    r = pins.release_lib_problems(pins.RELEASE_SCREEN); check(r == [], 'the folder the LAST release was built in, beside this tree, holds the pinned libraries and framework: ' + repr(r)[:300])
elif '--gate' in sys.argv: did_not_run('no release build beside this tree (dev/out/screen_build): the last release\'s own libraries could not be looked at - AT THE GATE (release_v1b.py gate_tests says --gate) that is not passed over')
else: print('  (no release build beside this tree - dev/out/screen_build: the last release\'s own libraries were not looked at here; at the gate, --gate, this is NOT RUN)')

# B211: the Sub-trim page file that is published is THIS RELEASE'S (the firmware takes nothing from the one before) - release_v1b.py subtrim_page_checked
print('- the Sub-trim page file from before is not published beside this firmware')
import json as _json
def _refused(files):
    try: rel.subtrim_page_checked(files); return ''
    except SystemExit as e: return str(e)
# B211 (the sixteenth review, reviewer A's finding 1): BOTH PAGE FILES ARE THE ONES KEPT BESIDE THE TESTS (dev/test_wholepage/pages: byte for byte the field's and this
# release's) - AND A PAGE FILE IS WHAT page32.py SAYS IT IS, NEVER WHAT ITS PLACE SAYS. This release's was read from a scratch folder, and the screen project's own page
# was called "the one from before" because of where it lies. ON RELEASE DAY that page is this release's: this test failed, and publish with it (the gate runs this
# script). With the scratch file gone, six checks did not run, and nothing said so. A kept file that is not there: "NOT RUN: ..." (did_not_run).
spec4 = importlib.util.spec_from_file_location('gate32', os.path.join(HERE, 'test_wholepage', 'page32.py'))
gate32 = importlib.util.module_from_spec(spec4); spec4.loader.exec_module(gate32)
def _kind(page):
    try: return gate32.page_kind(page)
    except Exception as e: return 'REFUSED: ' + (str(e) or type(e).__name__)
_CALLED = {'old': 'the page file from before', 'new': 'this release\'s page file'}
_screen_beside = os.path.join(os.path.dirname(rel.ROOT), 'ESP32-board2', 'board4', 'nextion-emulator')                              # the screen project, beside this tree
_repo = os.path.join(_screen_beside, 'sd', 'hmi', 'pages', '32.json')                                                             # its own page: the one from before until release day, this release's from then on
_pages = []                                                                                                                       # every page file there is: (its path, what page32.py says it is, what to call it)
for _name, _want in (('32_before_b211.json', 'old'), ('32_b211.json', 'new')):
    _path = os.path.join(HERE, 'test_wholepage', 'pages', _name)
    if not os.path.isfile(_path): did_not_run('%s is not beside the tests (dev/test_wholepage/pages/%s is missing): the gate was not tried against it' % (_CALLED[_want], _name)); continue
    _k = _kind(_path); check(_k == _want, 'dev/test_wholepage/pages/%s is %s, word for word (page32.py): %s' % (_name, _CALLED[_want], _k[:200]))
    if _k in _CALLED: _pages.append((_path, _k, '%s (dev/test_wholepage/pages/%s)' % (_CALLED[_k], _name)))
if os.path.isfile(_repo):
    _k = _kind(_repo); check(_k in _CALLED, 'the screen project\'s own Sub-trim page file is one of the two, word for word - the one from before, or this release\'s by now: ' + _k[:200])
    if _k in _CALLED: _pages.append((_repo, _k, '%s (the screen project\'s own, as it is today)' % _CALLED[_k]))
else: did_not_run('the screen project is not beside this tree (ESP32-board2/board4/nextion-emulator/sd/hmi/pages/32.json): the Sub-trim page file a release would publish today was not looked at')
check('no Sub-trim page' in _refused({}), 'a card folder with no page 32 is refused')
import inspect as _inspect, re as _re
check(bool(_re.search(r'tf, scf = teensy_files\(\), screen_files\(\)\s*subtrim_page_checked\(scf\)', _inspect.getsource(rel.stage))), 'stage() looks at the Sub-trim page file it is about to publish, before anything else is done with the files')
check('neither the one from before nor this release' in _refused({'/hmi/pages/32.json': b'{"name":"SubTrimView","id":32,"comps":[]}'}), 'a page 32 that is no Sub-trim page as known is refused')
check('neither the one from before nor this release' in _refused({'/hmi/pages/32.json': b'not json at all'}), 'a page 32 that cannot be read is refused')
for _path, _k, _what in _pages:
    _b = open(_path, 'rb').read(); _pg = _json.loads(_b)
    _r = _refused({'/hmi/pages/32.json': _b})
    if _k == 'old': check('BEFORE B211' in _r and 'subtrim_words.py' in _r, _what + ' is refused, and the refusal says what to run: ' + _r[:120])
    else: check(_r == '', _what + ' is taken: ' + _r[:200])
    # ... and either of them with ONE script changed is neither (somebody changed the page: the rule and its tests want looking at)
    for _c in _pg['comps']:
        if _c.get('n') == 'b0': _c['ev']['r'] = _c['ev']['r'].replace('n0.val+=1', 'n0.val+=2')
    check('neither the one from before nor this release' in _refused({'/hmi/pages/32.json': _json.dumps(_pg).encode()}), _what + ' with one script changed is refused')

# B211 (the fourteenth review, reviewer A's finding 1): THE GATE IS WORD FOR WORD - a page changed in a part the gate does not NAME is refused too (eleven of
# his twelve changed pages were "this release's": the named parts' scripts were compared, nothing else)
print('- the Sub-trim page file changed in ANY part - one the gate names or not - is refused')
import copy as _copy
def _comp(pg, n): return [c for c in pg['comps'] if c['n'] == n][0]
def _m1(pg): _comp(pg, 't1')['ev']['r'] = 'click n2,0'
def _m2(pg): _comp(pg, 'ch5')['ev']['r'] = 'click n00,0'
def _m3(pg): pg['comps'].append({'n': 'tmq', 'i': 62, 't': 'timer', 'g': 'l', 'a': {'tim': 400, 'en': 1}, 'ev': {'t': 'n0.val+=1\nclick n0,0'}})
def _m4(pg): pg['comps'].append({'n': 'bz', 'i': 63, 't': 'button', 'g': 'l', 'x': 300, 'y': 60, 'w': 80, 'h': 30, 'txt': 'x2', 'ev': {'r': 'print "StEDIT"\nprint s0.val\nprint n0.val\nn0.val*=2\nprint n0.val\nprint n0.val\nclick n0,0'}})
def _m5(pg): pg['ev']['postinitialize'] = 'n3.val=55'
def _m6(pg): pg['ev']['touch_release'] = 'print "StEDIT"\nprint 3\nprint n2.val\nprint 77\nprint 77'
def _m7(pg): _comp(pg, 'h0')['x'] = 600; _comp(pg, 'h0')['w'] = 150
def _m8(pg): _comp(pg, 'b10')['ev']['r'] = 'print 150'
def _m9(pg): _comp(pg, 'n0')['fresh'] = True
def _m10(pg): _comp(pg, 'rs')['y'] = 100; _comp(pg, 'rs')['x'] = -1000; _comp(pg, 'rs')['w'] = 2000
def _m11(pg): _comp(pg, 'h0')['ev']['p'] = 'n0.val=h0.val-127'
def _m12(pg): _comp(pg, 'n0')['ev']['p'] += '\nh0.val=127'
def _m13(pg): _comp(pg, 'ModelName')['g'] = 'g'
def _m14(pg): _comp(pg, 'b3')['ev']['r'] = _comp(pg, 'b3')['ev']['r'].replace('SUBTRIM.TXT', 'TRIMS.TXT')
_CHANGES = (('the label "Ch 2" selects channel 3', _m1), ('the name of channel 5 selects channel 1', _m2), ('a timer counts the chosen channel up and says nothing', _m3), ('a new button that doubles the number and says so', _m4),
            ('the page writes a box by itself as it comes up', _m5), ('a touch on the background says a change nobody made', _m6), ('the slider at another place and size', _m7), ('OK prints another code', _m8),
            ('the slider\'s number forgets its value at a load', _m9), ('the part "rs" reaches onto the screen', _m10), ('the slider\'s press changes the number without a word', _m11), ('every tap also centres the slider', _m12),
            ('a part\'s scope changed', _m13), ('Help opens another text', _m14))
for _path, _k, _what in _pages:                                  # (the sixteenth review: each file by what it IS - _pages, above - not by where it lies)
    _base = _json.loads(open(_path, 'rb').read()); _refusedN = 0; _tried = 0
    for _name, _f in _CHANGES:
        _pg = _copy.deepcopy(_base)
        try: _f(_pg)
        except (KeyError, IndexError): continue                  # (a part the page file from before has not got: "rs")
        if _pg == _base: continue
        _tried += 1; _r = _refused({'/hmi/pages/32.json': _json.dumps(_pg, separators=(',', ':')).encode()})
        if 'neither the one from before nor this release' in _r: _refusedN += 1
        else: print('   NOT refused: %s, %s' % (_what, _name))
    check(_tried >= 11 and _refusedN == _tried, '%s with a change in any one part is refused: %d of %d' % (_what, _refusedN, _tried))
    # ... and the same page written another way (the keys in another order, other spacing) is still the page
    _again = _json.dumps(_json.loads(_json.dumps(_base, sort_keys=True)), indent=2).encode()
    _r = _refused({'/hmi/pages/32.json': _again}); check(('BEFORE B211' in _r) if _k == 'old' else _r == '', '%s written with other spacing and its keys in another order is the same page' % _what)

# B211 (the fifteenth review, reviewer A's finding 6): THE PAGE FILE IS READ AS THE SCREEN READS IT - ITS OWN BYTES. Python's json took a byte order mark and UTF-16 as they
# came, and the pin is of the page as decoded: such a file was "this release's" - and the screen's reader (ArduinoJson) cannot read it; the page does not come up.
# The gate holds the bytes to plain ASCII from the first one, "{" (page32.py page_read), as both known files are.
print('- a Sub-trim page file the screen cannot read - a byte order mark, UTF-16, not plain ASCII from its first byte "{" - is refused')
NOT_PLAIN = 'is not plain ASCII text from its first byte, "{"'       # (gate32 - page32.py - and _kind: above, where the page files are told apart)
def _other_bytes(raw):
    """the same page, written in ways the gate's own reading (Python's json) took as they came. The first five the screen cannot read (run through ArduinoJson by the
       reviewer, and again for this cure); a space or a newline in front it reads over - a page file is held to the "{" all the same"""
    t = raw.decode('ascii')
    return (('a UTF-8 byte order mark in front', b'\xef\xbb\xbf' + raw), ('UTF-16 with its mark', t.encode('utf-16')), ('UTF-16 with no mark, the low byte first', t.encode('utf-16-le')),
            ('UTF-16 with no mark, the high byte first', t.encode('utf-16-be')), ('UTF-32', t.encode('utf-32')), ('a space in front of the "{"', b' ' + raw), ('a newline in front of the "{"', b'\n' + raw))
# (a make-believe page, pinned for this test alone: the rule is tried whether or not a real page file is beside this tree)
_fake = {'name': 'SubTrimView', 'id': 32, 'comps': [{'n': 't0', 'txt': 'Sub-trim ±117'}, {'n': 'b2', 'ev': {'r': 'print "StEDIT"\nprint s0.val'}}]}
_fakeRaw = _json.dumps(_fake, separators=(',', ':')).encode('ascii')
_keptGate = (gate32.PINS, gate32.named_kind); gate32.PINS = {gate32.pin_of(_fake): 'new'}; gate32.named_kind = lambda page, path='': 'new'
check(_kind(_fakeRaw) == 'new' and _kind(bytearray(_fakeRaw)) == 'new' and _kind(_json.dumps(_fake, indent=1).encode('ascii')) == 'new', 'a page file in plain ASCII from its first byte "{" is taken, with other spacing too: ' + _kind(_fakeRaw)[:120])
for _how, _b in _other_bytes(_fakeRaw):
    _r = _kind(_b); check(_r.startswith('REFUSED') and NOT_PLAIN in _r, 'the same page with %s is refused, and the refusal says why: %s' % (_how, _r[:100]))
_r = _kind(_json.dumps(_fake, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
check(_r.startswith('REFUSED') and NOT_PLAIN in _r and 'the byte at' in _r and '0xC2' in _r, 'the same page with a letter written in UTF-8 (not as an escape) is refused, and the byte named: ' + _r[:100])
check('it is empty' in _kind(b'') and NOT_PLAIN in _kind(b'[1]') and NOT_PLAIN in _kind(_fakeRaw[:-1] + b'\x7f}') and NOT_PLAIN in _kind(_fakeRaw + b'\0'), 'an empty file, one that does not begin with "{", one with a byte that is no text: refused')
with tempfile.TemporaryDirectory() as tmp8:
    def _file(b):
        open(os.path.join(tmp8, '32.json'), 'wb').write(b); return os.path.join(tmp8, '32.json')
    check(_kind(_file(_fakeRaw)) == 'new', 'the gate handed a PATH (the scenes) reads the same bytes: the plain file is taken')
    _r = [_kind(_file(_b)) for _how, _b in _other_bytes(_fakeRaw)]
    check(all(x.startswith('REFUSED') and NOT_PLAIN in x and tmp8 in x for x in _r), '... and each of the other writings is refused by its path too, the file named: %d of %d' % (sum(NOT_PLAIN in x for x in _r), len(_r)))
    import subprocess as _sp
    def _printed(b): return _sp.run([sys.executable, '-B', os.path.join(HERE, 'test_wholepage', 'page32.py'), _file(b)], stdout=_sp.PIPE, stderr=_sp.STDOUT, text=True).stdout
    _marked = _printed(b'\xef\xbb\xbf' + _fakeRaw)
    check('   pin ' + gate32.pin_of(_fake) in _printed(_fakeRaw) and 'NOT A PAGE FILE AS THE SCREEN READS ONE' in _marked and NOT_PLAIN in _marked and '   pin ' not in _marked,
          'python3 page32.py FILE - which prints the pin of a page changed on purpose - prints none for a file the screen cannot read, and says why: ' + _marked[:80].replace('\n', ' '))
gate32.PINS, gate32.named_kind = _keptGate
# ... and the real page files, through the release's own routine: each is plain ASCII from "{", and none is taken in another writing
for _path, _k, _what in _pages:
    _b = open(_path, 'rb').read()
    check(_b[:1] == b'{' and all(32 <= c < 127 or c in (9, 10, 13) for c in _b), '%s is plain ASCII from its first byte "{"' % _what)
    _r = [_refused({'/hmi/pages/32.json': _v}) for _how, _v in _other_bytes(_b)]
    check(all('neither the one from before nor this release' in x and 'is not plain ASCII text' in x for x in _r), '%s with a byte order mark, in UTF-16 or with something in front is not published: %d of %d refused' % (_what, sum('is not plain ASCII text' in x for x in _r), len(_r)))

# B211 (the fourteenth review, reviewer A's findings 5, 11 and 13): THE TEENSY'S PACKAGE IS THIS SOURCE'S; A FIRMWARE THAT CHANGED HAS A VERSION OF ITS OWN; THE BUILD IS PINNED
print('- the Teensy package that is staged is the source\'s version, and (--no-build) newer than its source; a test build that falls over is refused')
def _stops(f, *a, **k):
    try: f(*a, **k); return ''
    except SystemExit as e: return str(e)
with tempfile.TemporaryDirectory() as tmp7:
    keptT, keptH, keptR = rel.TEENSY, rel.HERE, rel.REL
    tc = os.path.join(tmp7, 'TransmitterCode'); os.makedirs(os.path.join(tc, 'include')); os.makedirs(os.path.join(tc, 'src')); os.makedirs(os.path.join(tc, 'lib', 'LdrcLink')); os.makedirs(os.path.join(tmp7, 'dev', 'out'))
    open(os.path.join(tc, 'include', '1Definitions.h'), 'w').write('#define TXVERSION_MAJOR 2\n#define TXVERSION_MINOR 5\n#define TXVERSION_MINIMUS 6\n#define TXVERSION_EXTRA "B211 16/11/26" // the version\n')
    open(os.path.join(tc, 'src', 'main.cpp'), 'w').write('void loop() {}\n'); open(os.path.join(tc, 'lib', 'LdrcLink', 'LdrcLink.h'), 'w').write('// link\n'); open(os.path.join(tc, 'platformio.ini'), 'w').write('[env:teensy41]\n')
    rel.TEENSY = tc; rel.HERE = os.path.join(tmp7, 'dev')
    pkgp = os.path.join(tmp7, 'dev', 'out', 'TXFW.BIN')
    check(rel.source_version() == '2.5.6 B211 16/11/26', 'the source\'s version text is read as the package maker reads it: ' + rel.source_version())
    def _put(version, more=b'', age=0):
        b = a_package(plain + more, version); open(pkgp, 'wb').write(b); when = _time.time() + age; os.utime(pkgp, (when, when))
        rel.teensy_build_noted(pkgp, b, rel.teensy_source_hash())            # (... and beside it what THIS script's build leaves there: the source it was built from, the package it made - the fifteenth review)
        return b
    for f in rel.teensy_source_files().values(): os.utime(f, (_time.time() - 600, _time.time() - 600))                 # (the source: ten minutes old)
    _put(b'2.5.6 B211 16/11/26'); check(_stops(rel.teensy_package, False) == '' and rel.teensy_package(False)[1] == '2.5.6 B211 16/11/26', '--no-build, a package of the source\'s version, newer than the source: taken')
    _put(b'2.5.6 B190 01/11/26'); s = _stops(rel.teensy_package, False); check('REFUSING TO PUBLISH' in s and '"2.5.6 B190 01/11/26"' in s and 'the source says "2.5.6 B211 16/11/26"' in s, '--no-build, a package of ANOTHER version than the source (an older build left in dev/out): refused')
    _put(b'2.5.6 B211 16/11/26', age=-3600); s = _stops(rel.teensy_package, False); check('REFUSING --no-build' in s and 'OLDER than the Teensy\'s source' in s, '--no-build, a package OLDER than the source: refused: ' + s[:90])
    _put(b'2.5.6 B211 16/11/26'); later = _time.time() + 120; os.utime(os.path.join(tc, 'lib', 'LdrcLink', 'LdrcLink.h'), (later, later))
    s = _stops(rel.teensy_package, False); check('REFUSING --no-build' in s and 'lib/LdrcLink/LdrcLink.h' in s, '... one file of a library of its own changed since: refused, and the file named')
    check(_stops(rel.teensy_package_is_the_sources, '2.5.6 B211 16/11/26', pkgp, True) == '', '(a package built just now is not held against the files\' times)')
    os.utime(os.path.join(tc, 'lib', 'LdrcLink', 'LdrcLink.h'), (_time.time() - 600, _time.time() - 600))
    _put(b'2.5.6 B211 16/11/26', more=b'LDRC TEST BUILD: falls over\0'); s = _stops(rel.teensy_package, False); check('TEST build' in s and 'LDRC TEST BUILD' in s, 'a package of the build that falls over on purpose (-DLDRC_TEST_FALL_OVER) is refused')
    _put(b'2.5.6 B211 16/11/26', more=b'ELRS test: module power ON\0'); check('TEST build' in _stops(rel.teensy_package, False), '... and an ELRS test build, as before')
    os.remove(pkgp); check('has not been built yet' in _stops(rel.teensy_package, False), '--no-build with no package at all: said')
    # the source's hash: every file of src, include, lib and platformio.ini counts
    h0 = rel.teensy_source_hash(); seen = 0
    for relp in ('src/main.cpp', 'include/1Definitions.h', 'lib/LdrcLink/LdrcLink.h', 'platformio.ini'):
        was = open(os.path.join(tc, relp)).read(); open(os.path.join(tc, relp), 'w').write(was + ' '); seen += rel.teensy_source_hash() != h0; open(os.path.join(tc, relp), 'w').write(was)
    open(os.path.join(tc, 'include', 'New.h'), 'w').write('//'); seen += rel.teensy_source_hash() != h0; os.remove(os.path.join(tc, 'include', 'New.h'))
    os.rename(os.path.join(tc, 'src', 'main.cpp'), os.path.join(tc, 'src', 'main2.cpp')); seen += rel.teensy_source_hash() != h0; os.rename(os.path.join(tc, 'src', 'main2.cpp'), os.path.join(tc, 'src', 'main.cpp'))
    open(os.path.join(tc, 'include', '.DS_Store'), 'w').write('x')
    check(seen == 6 and rel.teensy_source_hash() == h0 and len(h0) == 32, 'the hash of the Teensy\'s source: a byte changed in any file, a file more, a file renamed - seen (%d of 6); the same files give the same hash' % seen)
    # B211 (the fifteenth review, reviewer A's finding 3): "NEWER THAN EVERY FILE OF THE SOURCE" IS NOT "BUILT FROM THIS SOURCE". This script's build says beside its package
    # which source it built it from and which package it made (dev/out/TXFW.BIN.source); --no-build takes a package only by that word. The files' times are a second look.
    print('- --no-build takes the Teensy package only when this script\'s own build made it, from the source as it is now - whatever the files\' times say')
    V = b'2.5.6 B211 16/11/26'; wordp = pkgp + rel.TEENSY_BUILT_FROM; trims = os.path.join(tc, 'include', 'Trims.h'); now = _time.time()
    def _aged(path, minutes): os.utime(path, (now - 60 * minutes, now - 60 * minutes))
    def _source(text, minutes):
        open(trims, 'w').write(text); _aged(trims, minutes)
    def _word(): return open(wordp).read() if os.path.isfile(wordp) else '(no word)'
    _source('// the rule as it was built: FAULTY\n', 60)
    for f in rel.teensy_source_files().values(): _aged(f, 60)                                                         # the source: an hour old
    built = _put(V, age=-1800); h_built = rel.teensy_source_hash(); word_built = _word()                              # THE BUILD, half an hour ago
    check(word_built == 'source=%s\npackage=%s\n' % (h_built, rel.package_hash(built)) and wordp == os.path.join(tmp7, 'dev', 'out', 'TXFW.BIN.source'), 'the build\'s word beside the package (dev/out/TXFW.BIN.source): the hash of the source, and the package\'s')
    check(_stops(rel.teensy_package, False) == '' and rel.teensy_package(False) == (built, V.decode(), h_built), '--no-build, the package of that build, the source untouched since: taken - and handed on with the hash of the source it was built from')
    _source('// the rule CURED\n', 10)                                                                                # the source is cured ten minutes ago - and NOT built
    s = _stops(rel.teensy_package, False); check('OLDER than the Teensy\'s source' in s and 'include/Trims.h' in s, '(A0) the source cured since the build, the package untouched: refused as before, by the files\' times, the file named')
    open(pkgp, 'wb').write(built); _aged(pkgp, 1)                                                                     # ... and the package made again BY HAND from the same (old) build: the same bytes, a new time
    s = _stops(rel.teensy_package, False); check('REFUSING --no-build' in s and 'source is NOT the one the package' in s and 'was built from' in s, 'THE REVIEW\'S CASE (A1): the package made again by hand from the build before - newer than the cured source: refused: ' + s[:70])
    open(pkgp, 'wb').write(built); _aged(pkgp, 30); _source('// another Trims.h, copied in with its own (old) time\n', 1440)   # the build's package again; a source file put there by a copy that keeps its time (rsync -a, cp -p)
    s = _stops(rel.teensy_package, False); check('REFUSING --no-build' in s and 'source is NOT the one the package' in s, 'THE REVIEW\'S CASE (B): a source file replaced by a copy that kept its old time, the package of the build before: refused: ' + s[:70])
    _source('// the rule as it was built: FAULTY\n', 60)                                                               # the source as it was built, again
    check(rel.teensy_source_hash() == h_built and _stops(rel.teensy_package, False) == '', '... the source put back as it was built: the package is this source\'s again - taken')
    if os.path.isfile(wordp): os.remove(wordp)
    s = _stops(rel.teensy_package, False)
    check('REFUSING --no-build' in s and 'says which source it was built from' in s and 'TXFW.BIN.source' in s, 'a package with no word beside it (built by hand, or before this rule) is refused, though it is newer than every file of the source: ' + s[:70])
    open(wordp, 'w').write('source=\npackage=\n'); check('says which source it was built from' in _stops(rel.teensy_package, False), '... and one beside a word that says nothing')
    open(wordp, 'w').write(word_built); check(_stops(rel.teensy_package, False) == '', '(... the build\'s own word beside it again: taken)')
    open(pkgp, 'wb').write(a_package(plain + b'built by hand, with a flag of its own\0', V)); _aged(pkgp, 1)        # ANOTHER package beside the build's word: made by hand from another build of the same source
    s = _stops(rel.teensy_package, False); check('REFUSING --no-build' in s and 'is NOT the one this script\'s build made' in s, 'a package that the build did not make, beside that build\'s word, the source untouched: refused: ' + s[:70])
    # ... and THE BUILD ITSELF leaves that word (its two commands are stood in for: no compiler runs here)
    keptRun = rel.run
    def _build(saved_meanwhile=None, fails=False):
        ran = []
        def stand_in(cmd, cwd):
            ran.append('package' if cmd[-1].endswith('make_fw_package.py') else 'compile')
            if ran[-1] == 'package': open(pkgp, 'wb').write(a_package(plain + b'built just now\0', V))
            elif fails: sys.exit('FAILED: the compiler')
            elif saved_meanwhile: _source(saved_meanwhile, 0)                                                         # (somebody saves a source file while it compiles)
            return 'made'
        rel.run = stand_in
        try:
            with _ctx.redirect_stdout(_io.StringIO()): said = _stops(rel.teensy_package, True)
        finally: rel.run = keptRun
        return said, ran
    s, ran = _build(); fresh = open(pkgp, 'rb').read()
    check(s == '' and ran == ['compile', 'package'] and fresh != built and _word() == 'source=%s\npackage=%s\n' % (h_built, rel.package_hash(fresh)), 'a build by this script writes the word beside its package: the source it built from, the package it made: ' + (s or _word())[:70].replace('\n', ' '))
    check(_stops(rel.teensy_package, False) == '' and rel.teensy_package(False) == (fresh, V.decode(), h_built), '... and --no-build takes that package after it')
    s, ran = _build(saved_meanwhile='// saved while it was compiling\n')
    check('CHANGED WHILE' in s and ran == ['compile', 'package'] and not os.path.exists(wordp), 'a source file saved WHILE the build runs: refused (which of the two the package holds is not known), and no word is left beside it: ' + s[:50])
    check('says which source it was built from' in _stops(rel.teensy_package, False), '... so --no-build does not take that package either')
    _source('// the rule as it was built: FAULTY\n', 60); _put(V); check(os.path.exists(wordp) and _stops(rel.teensy_package, False) == '', '(a build that came through: its word is there)')
    s, ran = _build(fails=True)
    check('FAILED' in s and ran == ['compile'] and not os.path.exists(wordp), 'a build that fails leaves no word of the build before: what an earlier build said is not said of this one')
    # A FIRMWARE THAT HAS CHANGED HAS A VERSION TEXT OF ITS OWN (make-believe releases)
    print('- a Teensy firmware whose version text is an earlier release\'s, with another source, is refused')
    rel.REL = os.path.join(tmp7, 'release')
    def _release(name, version, crc8, source=None):
        d = os.path.join(rel.REL, 'v', rel.slug(name)); os.makedirs(d, exist_ok=True)
        t = {'version': version, 'crc': crc8}
        if source is not None: t['source'] = source
        _json.dump({'name': name, 'teensy': t}, open(os.path.join(d, 'release.json'), 'w'))
    pk = a_package(plain, b'2.5.6 B210 11/11/26'); crc8 = '%08X' % rel.crc(pk)
    check(_stops(rel.teensy_version_checked, '2.5.6 B210 11/11/26', pk, 'a first release', 'aaaa') == '', 'no release yet: nothing to hold it against')
    _release('2.5.6 B210 (screen 1.11.197)', '2.5.6 B210 11/11/26', 'DEADBEEF')                                   # a release from before this gate: no source recorded
    s = _stops(rel.teensy_version_checked, '2.5.6 B210 11/11/26', pk, '2.5.6 B210 (screen 1.11.198)', 'aaaa')
    check('REFUSING TO PUBLISH' in s and 'KEEP' in s and '--teensy-source-unchanged' in s and 'TXVERSION_EXTRA' in s, 'THE REVIEW\'S CASE: the tree still says the live release\'s version, the firmware is another: refused, and the refusal says both ways out')
    check(_stops(rel.teensy_version_checked, '2.5.6 B210 11/11/26', pk, '2.5.6 B210 (screen 1.11.198)', 'aaaa', True) == '', '... said to be unchanged (a release of the screen alone): taken')
    check(_stops(rel.teensy_version_checked, '2.5.6 B211 16/11/26', pk, '2.5.6 B211 (screen 1.11.198)', 'aaaa') == '', '... a version text of its own: taken')
    def _quiet(f, *a, **k):
        with _ctx.redirect_stdout(_io.StringIO()): return _stops(f, *a, **k)
    s = _stops(rel.teensy_version_checked, '2.5.6 B210 11/11/26', pk, '2.5.6 B210 (screen 1.11.197)', 'aaaa')    # (the fifteenth review: this was "the same release staged again" and passed by its name alone)
    check('REFUSING TO PUBLISH' in s and 'the release "2.5.6 B210 (screen 1.11.197)" (staged before, under this very name)' in s and '--teensy-source-unchanged' in s and 'TXVERSION_EXTRA' in s,
          '... staged under that release\'s OWN name, the firmware another, no source recorded with it: A NAME PROVES NOTHING - refused like any other, both ways out said')
    check(_quiet(rel.teensy_version_checked, '2.5.6 B210 11/11/26', pk, '2.5.6 B210 (screen 1.11.197)', 'aaaa', True) == '', '... its own name, and said to be unchanged: taken')
    _release('2.5.6 B210 (screen 1.11.197)', '2.5.6 B210 11/11/26', crc8)
    check(_stops(rel.teensy_version_checked, '2.5.6 B210 11/11/26', pk, '2.5.6 B210 (screen 1.11.198)', 'aaaa') == '', '... the very package of that release (--no-build): taken')
    check(_stops(rel.teensy_version_checked, '2.5.6 B210 11/11/26', pk, '2.5.6 B210 (screen 1.11.197)', 'aaaa') == '', '... and under its own name: the same release staged again with its very package - taken')
    _release('2.5.6 B211 (screen 1.11.198)', '2.5.6 B211 16/11/26', 'DEADBEEF', source='aaaa')                    # a release that recorded its source
    pk2 = a_package(plain, b'2.5.6 B211 16/11/26')
    check(_stops(rel.teensy_version_checked, '2.5.6 B211 16/11/26', pk2, '2.5.6 B211 (screen 1.11.199)', 'aaaa') == '', 'a release of the screen alone, the Teensy\'s source as recorded (built again: another package): taken, nothing to say')
    s = _stops(rel.teensy_version_checked, '2.5.6 B211 16/11/26', pk2, '2.5.6 B211 (screen 1.11.199)', 'bbbb')
    check('REFUSING TO PUBLISH' in s and 'has CHANGED since the release "2.5.6 B211 (screen 1.11.198)"' in s, '... the source changed under the same version text: refused')
    check('REFUSING TO PUBLISH' in _stops(rel.teensy_version_checked, '2.5.6 B211 16/11/26', pk2, '2.5.6 B211 (screen 1.11.199)', 'bbbb', True), '... and "unchanged" said against a RECORDED source that differs does not pass')
    # B211 (the fifteenth review, reviewer A's finding 2): THE VERSION IS HELD AGAINST EVERY EARLIER RELEASE WHATEVER IT IS CALLED - under this release's own name too. One of the
    # same name was passed over as "the same release staged again", and the name a release gets by itself does not change with the Teensy's source.
    print('- ... under the earlier release\'s OWN name too: the same release staged again is the one whose recorded source is the tree\'s; and a release\'s folder is its own')
    NAME = '2.5.6 B211 (screen 1.11.198)'; V211 = '2.5.6 B211 16/11/26'                                            # (recorded above with the source aaaa: the only release of this version there)
    check(_stops(rel.teensy_version_checked, V211, pk2, NAME, 'aaaa') == '', 'the same release staged again - its own name, the Teensy\'s source as recorded with it: taken')
    s = _stops(rel.teensy_version_checked, V211, pk2, NAME, 'bbbb')
    check('REFUSING TO PUBLISH' in s and 'has CHANGED since the release "%s" (staged before, under this very name)' % NAME in s and 'KEEP' in s and 'TXVERSION_EXTRA' in s,
          'THE REVIEW\'S CASE (C1, C5): the Teensy\'s source changed, its version text and the release\'s name as they were: refused: ' + s[:70])
    check('REFUSING TO PUBLISH' in _stops(rel.teensy_version_checked, V211, pk2, NAME, 'bbbb', True), '... and "unchanged" said does not pass it: that release recorded its source')
    check(_stops(rel.teensy_version_checked, '2.5.6 B211 17/11/26', pk2, NAME, 'bbbb') == '', '... the firmware given a version text of its own: taken (the name may stay)')
    rel.REL = os.path.join(tmp7, 'release3'); AS_IT_IS = '2.5.6 B211 (screen as it is)'; _release(AS_IT_IS, V211, 'DEADBEEF', source='aaaa')   # (another make-believe site: its one release was made --without-screen)
    check('has CHANGED since the release "%s" (staged before' % AS_IT_IS in _stops(rel.teensy_version_checked, V211, pk2, AS_IT_IS, 'bbbb'), '(C3) --without-screen twice, the source changed between - the name is the same both times: refused')
    # two names, one folder (the reviewer's D): the second wrote over the first one's record. release_folder_checked - asked by stage(), and again by write_release() itself
    rel.REL = os.path.join(tmp7, 'release'); TWIN = '2.5.6 B211 screen 1.11.198'
    s = _stops(rel.release_folder_checked, TWIN)
    check(TWIN != NAME and rel.slug(TWIN) == rel.slug(NAME) and 'REFUSING TO PUBLISH' in s and 'has the folder of ANOTHER release, "%s"' % NAME in s, '(D) a name to which slug() gives the folder of another release is refused, and that release named: ' + s[:70])
    check(_stops(rel.release_folder_checked, NAME) == '' and _stops(rel.release_folder_checked, 'a name of its own') == '', '... the release\'s own name (staged again), and a name with a folder of its own: taken')
    if os.path.exists(os.path.join(rel.REL, 'v', rel.slug(NAME).swapcase())):                                       # (a disk that takes capitals and small letters as one - the Mac's own: the two names have one folder there)
        check('has the folder of ANOTHER release, "%s"' % NAME in _stops(rel.release_folder_checked, NAME.swapcase()), '... a name that differs from another release\'s in capitals alone, on a disk that gives the two one folder: refused')
    check(all('no folder of its own' in _stops(rel.release_folder_checked, n) for n in ('', '()', ' - ', '.', '..')), '... a name that gives no folder at all (no letter and no digit in it) is refused')
    rel.REL = os.path.join(tmp7, 'release5')                                                                        # (a make-believe site with the release's package in it: write_release makes the HEX file of it)
    def _described(name, source, notes='a make-believe release'):
        return {'name': name, 'date': '2026-11-16', 'notes': notes, 'base': rel.BASE, 'teensy': {'version': V211, 'file': rel.put_blob(pk2)[0], 'size': len(pk2), 'crc': '%08X' % rel.crc(pk2), 'source': source}}
    def _record(name): return _json.load(open(os.path.join(rel.REL, 'v', rel.slug(name), 'release.json')))
    rel.write_release(_described(NAME, 'aaaa'))
    s = _stops(rel.write_release, _described(TWIN, 'cccc'))
    check('has the folder of ANOTHER release' in s and _record(NAME)['name'] == NAME and _record(NAME)['teensy']['source'] == 'aaaa' and ('name=%s\n' % NAME) in open(os.path.join(rel.REL, 'latest.txt')).read(),
          'write_release itself writes nothing over another release\'s folder: that release\'s record stands, and it is still the latest: ' + s[:70])
    check(_stops(rel.write_release, _described(NAME, 'aaaa', 'staged again')) == '' and _record(NAME)['notes'] == 'staged again', '... the same name: written again, as before')
    # ... and THE WHOLE OF stage() on a make-believe tree (--no-build --without-screen; the Sub-trim page's own gate, tried above, is stood in for): the reviewer's C3 by the real road
    rel.REL = os.path.join(tmp7, 'release6'); keptStage = (rel.ROOT, rel.SCREEN, rel.subtrim_page_checked, rel.run)
    rel.ROOT = tmp7; rel.SCREEN = os.path.join(tmp7, 'screen'); rel.subtrim_page_checked = lambda scf: None
    def _no_command(cmd, cwd): sys.exit('a make-believe staging started a command: ' + ' '.join(cmd))
    rel.run = _no_command
    os.makedirs(os.path.join(tmp7, 'Help files for SD')); open(os.path.join(tmp7, 'Help files for SD', 'SUBTRIM.TXT'), 'w').write('Sub-trim: help')
    os.makedirs(os.path.join(tmp7, 'screen', 'sd', 'hmi', 'pages'))
    for k in range(100): open(os.path.join(tmp7, 'screen', 'sd', 'hmi', 'pages', '%d.json' % k), 'w').write('{"id":%d}' % k)
    make_believe = all((os.path.realpath(getattr(rel, k)) + os.sep).startswith(os.path.realpath(tmp7) + os.sep) for k in ('ROOT', 'TEENSY', 'HERE', 'REL', 'SCREEN'))
    check(make_believe, '(every folder stage() reads or writes is this test\'s own, in the temporary folder: nothing real is built, read, staged or sent - and it is not run otherwise)')
    def _stage(name=None, **k): return _quiet(rel.stage, 'a make-believe release', False, name, False, **k) if make_believe else 'stage() was not called: one of its folders is not this test\'s own'
    _source('// the rule as it was built: FAULTY\n', 60); _put(V); s = _stage()
    check(s == '' and _record(AS_IT_IS)['name'] == AS_IT_IS and _record(AS_IT_IS)['teensy']['source'] == h_built and _record(AS_IT_IS)['teensy']['version'] == V211,
          'stage(): staged under the name it gets by itself, and the hash of the source its package was built from recorded with it: ' + s[:100])
    s = _stage(); check(s == '', 'stage() again, nothing changed - the same release staged again: taken: ' + s[:100])
    s = _stage('2.5.6 B211 screen as it is'); check('has the folder of ANOTHER release, "%s"' % AS_IT_IS in s and _record(AS_IT_IS)['name'] == AS_IT_IS, 'stage() under a name that has that release\'s folder: refused, its record stands: ' + s[:60])
    _source('// the rule CURED\n', 60); _put(V); s = _stage()                                                        # the Teensy's source changed and BUILT (package and word are right) - its version text forgotten
    check('has CHANGED since the release "%s" (staged before, under this very name)' % AS_IT_IS in s and _record(AS_IT_IS)['teensy']['source'] == h_built and rel.teensy_source_hash() != h_built,
          'stage() again, the Teensy\'s source changed under its version text and the name unchanged with it: REFUSED, and the first one\'s record stands: ' + s[:60])
    check('has CHANGED since the release' in _stage(teensy_unchanged=True), '... --teensy-source-unchanged does not pass it')
    defs = os.path.join(tc, 'include', '1Definitions.h'); was = open(defs).read(); open(defs, 'w').write(was.replace('B211 16/11/26', 'B211 17/11/26')); _put(b'2.5.6 B211 17/11/26'); s = _stage()
    check(s == '' and was != open(defs).read() and _record(AS_IT_IS)['teensy']['version'] == '2.5.6 B211 17/11/26' and _record(AS_IT_IS)['teensy']['source'] == rel.teensy_source_hash(), '... the firmware given a version text of its own (the refusal\'s way out): staged: ' + s[:100])
    rel.ROOT, rel.SCREEN, rel.subtrim_page_checked, rel.run = keptStage
    rel.TEENSY, rel.HERE, rel.REL = keptT, keptH, keptR
# B211 (the sixteenth review, reviewer A's finding 4): --no-build AND THE SCREEN'S HALF. The Teensy's package was held to its source (above) - the screen's two images were
# not: built, then a fault cured in the screen's source under the same SCREEN_VERSION, then --no-build - the OLD images were taken, beside the new card files. The build
# now writes beside its log which source it built the images from, and which images it made (release_build.source); --no-build takes them only by that word.
# release_v1b.py screen_firmware ITSELF, on a make-believe screen project: its copy made by the real clean_copy (rsync); its compiler and the libraries' gate stood in for.
print('- --no-build takes the screen\'s two images only when this script\'s own build made them, from the screen\'s source as it is now - whatever SCREEN_VERSION says')
if _shutil.which('rsync') is None: did_not_run('rsync is not on this machine (release_v1b.py clean_copy makes the screen\'s clean copy with it): --no-build and the screen\'s images were not tried')
else:
    with tempfile.TemporaryDirectory() as tmp9:
        kept9 = (rel.SCREEN, rel.CLEAN, rel.HERE, rel.screen_libraries_checked, rel.run)
        scr = os.path.join(tmp9, 'screen'); cln = os.path.join(tmp9, 'dev', 'out', 'screen_build'); bld = os.path.join(cln, '.pio', 'build')
        def _put9(relp, text, top=scr):
            p = os.path.join(top, relp); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w').write(text); return p
        MAIN9 = '#define SCREEN_VERSION "1.11.198"\n// the wire: %s\n'
        for relp, text in (('src/main.cpp', MAIN9 % 'as it was BUILT (faulty)'), ('src/LdrcUpdate.cpp', '// the updater\n'), ('include/ca_bundle.h', '// certificates\n'),
                           ('lib/NextionScript/NextionScript.cpp', '// the scripts\n'), ('platformio.ini', '[env:ota]\n[env:ota_full]\n')): _put9(relp, text)
        # ... and what is NOT the firmware's source: a make-believe secrets.h, the card's files, the page tools and their tests, what the Mac and Python leave behind, a build made by hand
        NOT_SOURCE = (('include/secrets.h', '#define WIFI_PASS "make-believe-9"\n'), ('sd/hmi/pages/32.json', '{}'), ('hmi/subtrim_words.py', '# a page tool\n'), ('hmi/test_update/run.sh', '#!/bin/sh\n'),
                      ('dev/screen.py', '# a tool\n'), ('src/.DS_Store', 'x'), ('lib/NextionScript/__pycache__/x.pyc', 'x'), ('.newscreen_ip', '192.0.2.1\n'), ('.pio/build/ota/firmware.bin', 'built by hand, in the project itself'))
        for relp, text in NOT_SOURCE: _put9(relp, text)
        rel.SCREEN, rel.CLEAN, rel.HERE = scr, cln, os.path.join(tmp9, 'dev')
        libs9 = []; rel.screen_libraries_checked = lambda build_log=None: libs9.append(build_log)       # (the libraries' own gate, tried above: stood in for - it is handed the build's log)
        make_believe9 = all((os.path.realpath(getattr(rel, k)) + os.sep).startswith(os.path.realpath(tmp9) + os.sep) for k in ('SCREEN', 'CLEAN', 'HERE'))
        NOT_MINE = 'screen_firmware() was not called: one of its folders is not this test\'s own'
        check(make_believe9, '(every folder screen_firmware() reads or writes is this test\'s own, in the temporary folder: nothing real is copied, built or taken - and it is not run otherwise)')
        def _image9(full, says): return bytes([0xE9, 0, 0, 0x40 if full else 0x20]) + b'\0' * 64 + b'LDRCSCREEN=1.11.198;' + (b'LDRCBUILD=full;' if full else b'LDRCBUILD=standard;') + says.encode() + b'\0'
        LOG9 = 'Processing ota\n - framework-arduinoespressif32 @ 3.x \nProcessing ota_full\n - framework-arduinoespressif32 @ 3.x \n'
        def _images9(): return [open(os.path.join(bld, env, 'firmware.bin'), 'rb').read() for env in ('ota', 'ota_full')]
        def _build9(saved_meanwhile=None, fails=False, copy_kept=False):
            """screen_firmware(True): -> why it stopped ('' when it did not), and what it ran. The copy is made by the real clean_copy; the compiler is stood in for
               (each image says what the COPY's main.cpp says). copy_kept: the copy is left as it stands, the build before still in it (the rsync the release script
               asks for keeps the copy's .pio; this Mac's own clears it away with the rest - both are tried)"""
            ran = []
            def stand_in(cmd, cwd):
                if cmd[0] == 'rsync': ran.append('copy'); return '' if copy_kept else kept9[4](cmd, cwd)
                ran.append('compile')
                if fails: sys.exit('FAILED: the compiler')
                says = open(os.path.join(cln, 'src', 'main.cpp')).read().split('\n')[1]
                for env, full in (('ota', False), ('ota_full', True)):
                    os.makedirs(os.path.join(bld, env), exist_ok=True); open(os.path.join(bld, env, 'firmware.bin'), 'wb').write(_image9(full, says))
                if saved_meanwhile: _put9('src/main.cpp', saved_meanwhile, cln)                          # (a file of the copy is saved while it compiles)
                return LOG9
            rel.run = stand_in
            try:
                with _ctx.redirect_stdout(_io.StringIO()): said = _stops(rel.screen_firmware, True) if make_believe9 else NOT_MINE
            finally: rel.run = kept9[4]
            return said, ran
        def _no_build9():
            """screen_firmware(False), which is --no-build: -> why it stopped ('' when it did not), and what it took (None when it took nothing)"""
            took = []
            with _ctx.redirect_stdout(_io.StringIO()): said = _stops(lambda: took.append(rel.screen_firmware(False))) if make_believe9 else NOT_MINE
            return said, (took[0] if took else None)
        wordp = os.path.join(bld, rel.SCREEN_BUILT_FROM); logp = os.path.join(bld, rel.BUILD_LOG_KEPT)
        def _word9(): return open(wordp).read() if os.path.isfile(wordp) else '(no word)'
        def _logtime9(): return os.path.getmtime(logp) if os.path.isfile(logp) else _time.time()
        s, ran = _build9(); built9 = _images9() if not s else [b'', b'']; h9 = rel.screen_source_hash(scr); word9 = _word9()
        check(s == '' and ran == ['copy', 'compile'] and word9 == 'source=%s\nota=%s\nota_full=%s\n' % (h9, rel.package_hash(built9[0]), rel.package_hash(built9[1])) and os.path.isfile(logp) and libs9 == [LOG9],
              'a build by this script writes its word beside its log (dev/out/screen_build/.pio/build/release_build.source): the hash of the source it built from, and the two images it made: ' + (s or word9)[:70].replace('\n', ' '))
        left = [p for p in ('include/secrets.h', 'sd', 'hmi/test_update', 'src/.DS_Store', 'lib/NextionScript/__pycache__') if os.path.exists(os.path.join(cln, p))]
        check(rel.screen_source_hash(cln) == h9 and len(h9) == 32 and not left and os.path.isfile(os.path.join(cln, 'src', 'main.cpp')),
              'the clean copy, as the real clean_copy() makes it, has the hash of the screen project\'s own source - nothing that is left out of the copy counts: ' + repr(left))
        check(sorted(rel.screen_source_files(scr)) == ['include/ca_bundle.h', 'lib/NextionScript/NextionScript.cpp', 'platformio.ini', 'src/LdrcUpdate.cpp', 'src/main.cpp'],
              'the screen\'s source is src, include, lib and what lies beside platformio.ini - no secrets.h (it is never opened), no card file, no page tool, nothing the Mac or Python left: ' + repr(sorted(rel.screen_source_files(scr)))[:160])
        s, took = _no_build9(); check(s == '' and took == (built9[0], built9[1], '1.11.198'), '--no-build right behind that build: its two images are taken: ' + s[:90])
        _put9('src/main.cpp', MAIN9 % 'CURED (a fault found after the build; the version left as it was)'); old = _logtime9() - 3600; os.utime(os.path.join(scr, 'src', 'main.cpp'), (old, old))
        s, took = _no_build9()
        check('REFUSING --no-build' in s and 'source is NOT the one the screen images' in s and 'changed since: src/main.cpp' in s and took is None and _images9() == built9,
              'THE REVIEW\'S CASE: the screen\'s source changed since the build, SCREEN_VERSION as it was (and the file\'s time older than the images): the old images are NOT taken, and the file is named: ' + s[:60])
        _put9('src/main.cpp', MAIN9 % 'changed in the copy too', cln); s, took = _no_build9(); _put9('src/main.cpp', MAIN9 % 'as it was BUILT (faulty)', cln)
        check('source is NOT the one the screen images' in s and 'a file was changed, added or taken away since' in s and 'changed since:' not in s and took is None,
              '... the copy it was built in changed as well (it can no longer say which file): refused all the same, and no file is named: ' + s[-110:])
        _put9('src/main.cpp', MAIN9 % 'as it was BUILT (faulty)'); s, took = _no_build9(); check(s == '' and took is not None, '... the source put back as it was built: taken again: ' + s[:90])
        # every file the firmware is built from counts
        CHANGES9 = (('src/LdrcUpdate.cpp', '// the updater, changed\n'), ('include/ca_bundle.h', '// other certificates\n'), ('lib/NextionScript/NextionScript.cpp', '// the scripts, changed\n'),
                    ('platformio.ini', '[env:ota]\nbuild_flags = -DEMU_ECHO\n[env:ota_full]\n'), ('src/New.cpp', '// a file more\n'), ('partitions.csv', '# a partition table beside platformio.ini\n'), ('boards/panel.json', '{}'))
        seen9 = 0
        for relp, text in CHANGES9:
            p = os.path.join(scr, relp); was = open(p).read() if os.path.exists(p) else None
            _put9(relp, text); s, took = _no_build9(); seen9 += 'source is NOT the one the screen images' in s and ('changed since: ' + relp) in s and took is None
            if was is None: os.remove(p)
            else: _put9(relp, was)
        os.rename(os.path.join(scr, 'src', 'LdrcUpdate.cpp'), os.path.join(scr, 'src', 'Updater.cpp')); s, took = _no_build9(); seen9 += 'changed since: src/LdrcUpdate.cpp, src/Updater.cpp' in s and took is None
        os.rename(os.path.join(scr, 'src', 'Updater.cpp'), os.path.join(scr, 'src', 'LdrcUpdate.cpp'))
        os.remove(os.path.join(scr, 'include', 'ca_bundle.h')); s, took = _no_build9(); seen9 += 'changed since: include/ca_bundle.h' in s and took is None; _put9('include/ca_bundle.h', '// certificates\n')
        check(seen9 == len(CHANGES9) + 2 and _no_build9()[0] == '', 'a byte changed in any file of src, include or lib, or in platformio.ini; a file more (a partition table, a board of its own); a file renamed; a file gone: '
              'each refused, and named (%d of %d) - and all put back: taken' % (seen9, len(CHANGES9) + 2))
        for relp, text in NOT_SOURCE: _put9(relp, text + ' - changed')
        _put9('hmi/elrs_pages.py', '# a new page tool\n'); _put9('sd/hmi/pages/33.json', '{}'); s, took = _no_build9()
        check(rel.screen_source_hash(scr) == h9 and s == '' and took is not None, 'what no firmware is built from may change - the card\'s files, the page tools and their tests, secrets.h, a dot file, what the Mac and Python leave: --no-build still takes the images: ' + s[:90])
        if os.path.isfile(wordp): os.remove(wordp)
        s, took = _no_build9()
        check('REFUSING --no-build' in s and 'says which source they were built from' in s and 'release_build.source' in s and took is None, 'no word beside the images (built by hand, or before this rule): refused, though the log is there and the version is right: ' + s[:60])
        open(wordp, 'w').write('source=\nota=\nota_full=\n'); s1 = _no_build9()[0]; open(wordp, 'w').write('source=%s\n' % h9); s2 = _no_build9()[0]
        check('says which source they were built from' in s1 and 'says which source they were built from' in s2, '... and a word that says nothing, or names the source and no image')
        open(wordp, 'w').write(word9); check(_no_build9()[0] == '', '(... the build\'s own word beside them again: taken)')
        seen9 = 0; before = _logtime9() - 60
        for env, full, label in (('ota', False, 'STANDARD'), ('ota_full', True, 'FULL')):                 # ANOTHER image beside the build's word, put there with an older time than the log (kept_build_log does not see it)
            img = os.path.join(bld, env, 'firmware.bin'); open(img, 'wb').write(_image9(full, 'built by hand, from another source')); os.utime(img, (before, before))
            s, took = _no_build9(); seen9 += 'REFUSING --no-build' in s and ('the %s screen image' % label) in s and 'is NOT the one this script\'s build made' in s and took is None
            open(img, 'wb').write(built9[full]); os.utime(img, (before, before))
        check(seen9 == 2 and _no_build9()[0] == '', 'an image that the build did not make, beside that build\'s word - either of the two, its time older than the log: refused, and named (%d of 2); the build\'s own back: taken' % seen9)
        _put9('src/main.cpp', MAIN9 % 'CURED'); s, ran = _build9(); h9b = rel.screen_source_hash(scr); s2, took = _no_build9()
        check(s == '' and h9b != h9 and _word9().startswith('source=%s\n' % h9b) and s2 == '' and took is not None and b'the wire: CURED' in took[0] and b'the wire: CURED' in took[1],
              'the cured source BUILT by this script: a new word, and --no-build takes the new images: ' + (s or s2)[:90])
        s, ran = _build9(fails=True, copy_kept=True); s2, took = _no_build9()
        check('FAILED' in s and ran == ['copy', 'compile'] and not os.path.exists(wordp) and os.path.isfile(logp) and 'says which source they were built from' in s2 and took is None,
              'a build that fails leaves no word of the build before, though its images and its log still lie there: what an earlier build said is not said of this one, and --no-build takes nothing: ' + s2[:50])
        _build9(); s, ran = _build9(fails=True); s2, took = _no_build9()
        check('FAILED' in s and not os.path.exists(wordp) and 'REFUSING --no-build' in s2 and took is None, '... and the same with the copy made afresh by this machine\'s rsync: ' + s2[:60])
        s, ran = _build9(saved_meanwhile=MAIN9 % 'saved while it was compiling')
        check('CHANGED WHILE' in s and ran == ['copy', 'compile'] and not os.path.exists(wordp) and 'says which source they were built from' in _no_build9()[0],
              'a file of the copy saved WHILE the build runs: refused (which of the two the images hold is not known), no word is left, and --no-build takes nothing: ' + s[:50])
        rel.SCREEN, rel.CLEAN, rel.HERE, rel.screen_libraries_checked, rel.run = kept9
# ... and that hash is of ALL the screen's firmware is built from only while its platformio.ini names nothing else (as the Teensy's, below: "no scripts of its own").
# The screen project beside this tree - the one a release is built from: no build script, no folder of its own, no source filter, no file put into the image, no
# partition table in a folder, no flag that names a file or runs a command. (No screen project beside this tree: said above, "NOT RUN".)
_ini9 = os.path.join(_screen_beside, 'platformio.ini')
if os.path.isfile(_ini9):
    _live9 = '\n'.join(_re.sub(r'(^|\s)[;#].*', '', l) for l in open(_ini9, encoding='utf-8', errors='replace').read().split('\n'))
    _else9 = sorted(set(_re.findall(r'^\s*(extra_scripts|src_dir|include_dir|lib_dir|lib_extra_dirs|boards_dir|build_src_filter|src_filter|board_build\.embed_\w+)\s*=', _live9, _re.M)
                        + _re.findall(r'^\s*(board_build\.partitions\s*=\s*\S*/\S*)', _live9, _re.M) + _re.findall(r'(?<![\w.-])(-(?:I|include|L|T)\s*\S+|!\s*\S+)', _live9)))
    check('[env:ota]' in _live9 and '[env:ota_full]' in _live9 and not _else9, 'the screen\'s platformio.ini names nothing that the hash of its source leaves out (if it does one day: bring release_v1b.py screen_source_files up to date first): ' + repr(_else9)[:200])
elif os.path.isdir(_screen_beside): did_not_run('the screen project beside this tree has no platformio.ini: what else its firmware is built from was not looked at')
src_stage = _inspect.getsource(rel.stage)
check(_re.search(r'tp, tv, tsource = teensy_package\(build\)', src_stage) is not None and 'teensy_source_hash(' not in src_stage and 'teensy_version_checked(tv, tp, name, tsource, teensy_unchanged)' in src_stage and "'source': tsource" in src_stage
      and src_stage.index('teensy_version_checked(') < src_stage.index('put_blob('), 'stage() holds the version against the earlier releases before anything is put into the staging folder, and records the hash of the source the package was built from (as teensy_package hands it on: the tree is not looked at a second time)')
check(_re.search(r'release_folder_checked\(name\)[^\n]*\n\s*teensy_version_checked\(tv, tp, name, tsource, teensy_unchanged\)', src_stage) is not None and src_stage.index('release_folder_checked(') < src_stage.index('put_blob('),
      'stage() asks whose folder the name has before anything is put into the staging folder')
check('source' not in rel.release_text({'name': 'n', 'date': 'd', 'notes': 'x', 'base': 'b', 'teensy': {'version': 'v', 'file': 'f', 'size': 1, 'crc': 'c', 'source': 'hhhh'}}), 'the hash is not in release.txt (what the screen reads names its own keys)')
check(rel.TEST_BUILD_MARKS == (b'ELRS test', b'LDRC TEST BUILD'), 'the two test builds\' marks')
main_cpp = open(os.path.join(HERE, '..', 'TransmitterCode', 'src', 'main.cpp'), encoding='utf-8', errors='replace').read()
check(_re.search(r'#ifdef LDRC_TEST_FALL_OVER\s*if \(millis\(\) > 8000\)[^\n]*\n\s*\{\s*static const char mark\[\] = "LDRC TEST BUILD: falls over";[^\n]*\n[^\n]*\n\s*volatile const char \*keep = mark;', main_cpp) is not None and src_all.count('LDRC TEST BUILD') == 1,
      'the build that falls over on purpose holds its mark (main.cpp, inside its #ifdef), and no other line of the source holds it')
print('- the Teensy\'s platformio.ini pins everything the firmware is built with')
ini = open(os.path.join(HERE, '..', 'TransmitterCode', 'platformio.ini'), encoding='utf-8').read(); ini_live = '\n'.join(l for l in ini.split('\n') if not l.lstrip().startswith(';'))
deps = [l.strip() for l in ini_live[ini_live.index('lib_deps'):].split('\n')[1:] if l.strip()]
check(len(deps) >= 6 and all(_re.fullmatch(r'[\w.-]+/[\w .-]+ @ \d+\.\d+\.\d+', d) or _re.fullmatch(r'https://github\.com/[\w.-]+/[\w.-]+?(?:\.git)?#[0-9a-f]{40}', d) for d in deps),
      'every library is named with ONE version, or with the commit of its git repository: ' + repr([d for d in deps if '@' not in d and '#' not in d])[:160])
check(_re.search(r'^platform = teensy @ \d+\.\d+\.\d+$', ini_live, _re.M) is not None and _re.search(r'^platform_packages =\s*\n\s+framework-arduinoteensy @ \d+\.\d+\.\d+\s*\n\s+toolchain-gccarmnoneeabi-teensy @ \d+\.\d+\.\d+\s*$', ini_live, _re.M) is not None,
      'the platform, its framework and its compiler have a version each')
check(ini_live.count('[env:') == 1 and 'build_flags' not in ini_live and 'extra_scripts' not in ini_live, 'one build, no flags and no scripts of its own (a test build\'s flag comes from outside, and the release takes none: build_env)')

print('- a test that did NOT RUN has not passed; the gate runs this script too (the fifteenth review)')
check(rel.test_passed(0, 'test_wholepage: 44 scene files, 3900 checks, 0 failed\nALL GOOD\n') and not rel.test_passed(1, 'ALL GOOD\n'), 'a test passes by its return code')
check(not rel.test_passed(0, 'test_wholepage (subtrim): 2106 checks, 0 failures\nNOT RUN: the screen project\'s script interpreter (lib/NextionScript) is not beside this repository\nALL GOOD - but for the 2 scene(s) that did not run\n'),
      'a test that says "NOT RUN" has not passed, whatever its return code')
check(not rel.test_passed(0, '  NOT RUN: indented, as the gate prints it\n') and rel.test_passed(0, 'a line that says the scene was NOT RUN: no - only a line that begins so\n'), '... a line that BEGINS "NOT RUN"')
_tests = [os.path.relpath(t, HERE) for t in rel.gate_tests()]
check('test_release_gate.py' in _tests and os.path.join('test_wholepage', 'test_wholepage.py') in _tests and os.path.join('test_servos', 'test_servos.py') in _tests and len(_tests) == len(set(_tests)) and len(_tests) >= 48,
      'the gate runs every dev/test_*/test_*.py and dev/test_release_gate.py itself: %d scripts' % len(_tests))
_gate = open(os.path.join(HERE, 'release_v1b.py'), encoding='utf-8').read(); _gate = _gate[_gate.index('def gate():'):_gate.index('def ftp_login')]
check('for t in gate_tests():' in _gate and 'if not test_passed(r.returncode, r.stdout): sys.exit(' in _gate, 'gate() asks test_passed of every script of gate_tests()')
check('with_screen = staged_has_screen()' in _gate and "any(l.startswith('screen.file=') for l in open(os.path.join(REL, 'latest.txt'))" in src_rel and "(['--gate'] if with_screen and os.path.basename(t) == 'test_release_gate.py' else [])" in _gate and "elif '--gate' in sys.argv: did_not_run(" in open(os.path.abspath(__file__), encoding='utf-8').read(),
      'at the gate of a release WITH a screen this test is run with --gate: the part it passes over in brackets beside a working copy (no release build beside the tree) is NOT RUN there (the seventeenth review)')
_wp = open(os.path.join(HERE, 'test_wholepage', 'test_wholepage.py'), encoding='utf-8').read()
check("l.startswith('NOT RUN:')" in _wp and "print('\\n'.join(l for l in lines if l.startswith('NOT RUN:')))" in _wp, 'dev/test_wholepage hands a scene\'s "NOT RUN: ..." line on, at the head of a line')
for _sc in ('scene_subtrim_real.py', 'scene_subtrim_page.py'):
    _t = open(os.path.join(HERE, 'test_wholepage', _sc), encoding='utf-8').read()
    check("print('NOT RUN: " in _t and 'not beside' in _t and "print('ALL GOOD'); sys.exit(0)" not in _t, _sc + ': without the screen project\'s interpreter it says "NOT RUN" and no "ALL GOOD"')

# B211 (the sixteenth review, reviewer A's finding 3): A VARIABLE LEFT IN THE SHELL SWITCHED THE GATE'S CHECKS OFF WITHOUT A WORD. The tests have switches of their own
# (LDRC_RUNS_ONLY sets the Sub-trim scenes' source checks aside; TXV1B_TC makes five tests look at another tree), and gate() handed the shell's environment on.
# release_v1b.py TEST_SWITCHES is the one list of them; test_env() takes them out of what the gate hands to a test. gate() ITSELF is run here: on make-believe tests,
# and on a scene of a COPY of this tree with a rule taken out - every switch left set in the caller's environment, which is this script's own.
print('- a variable left in the shell switches none of the gate\'s checks off: no switch of the tests\' own is handed on to a test (the sixteenth review)')
import glob as _glob
keptEnv = dict(os.environ)
for _n in rel.TEST_SWITCHES: os.environ[_n] = '/somewhere/else'                                         # THE CALLER'S ENVIRONMENT: every switch left set ...
os.environ['LDRC_RUNS_ONLY'] = '1'; os.environ['ldrc_runs_only'] = '1'; os.environ['LDRC_SOMETHING_ELSE'] = 'kept'   # (... the reviewer's as he left it; one in small letters; and one that is no switch)
try:
    with _ctx.redirect_stdout(_io.StringIO()) as said: env = rel.test_env()
    check(not [k for k in env if k.upper() in rel.TEST_SWITCHES] and env.get('LDRC_SOMETHING_ELSE') == 'kept' and all(env.get(k) == v for k, v in keptEnv.items() if k.upper() not in rel.TEST_SWITCHES),
          'test_env(): none of the tests\' switches is in the environment the gate hands on (in capitals or not), and the rest of it is as it was')
    check(all(n in said.getvalue() for n in rel.TEST_SWITCHES) and '/somewhere/else' not in said.getvalue(), 'it says which were not passed on - their names, not what they held')
    with tempfile.TemporaryDirectory() as tmp10:
        keptGate = (rel.gate_tests, rel.SCREEN, rel.REL)
        SEES = 'import os, sys\nseen = sorted(k for k in os.environ if k.upper() in %r)\nprint("a make-believe test: it sees " + (", ".join(seen) or "no switch") + "; the rest of the environment: " + os.environ.get("LDRC_SOMETHING_ELSE", "GONE"))\n' % (rel.TEST_SWITCHES,)
        t_good = os.path.join(tmp10, 'test_good.py'); open(t_good, 'w').write(SEES + 'print("3 checks, 0 failures")\n')
        # (a test that sets its check aside when the switch reaches it, as scene_subtrim.py does - on a tree whose rule is taken out)
        t_aside = os.path.join(tmp10, 'test_aside.py'); open(t_aside, 'w').write(SEES + 'if os.environ.get("LDRC_RUNS_ONLY"): print("(a source check, not held in this run: LDRC_RUNS_ONLY) the rule"); print("ALL GOOD"); sys.exit(0)\nprint("FAIL: the rule"); sys.exit(1)\n')
        # (the screen's own parser - hmi/test_update/run.sh - make-believe: it says what it was called with and what it sees, and passes only when it sees no switch)
        rs = os.path.join(tmp10, 'screen', 'hmi', 'test_update', 'run.sh'); os.makedirs(os.path.dirname(rs))
        open(rs, 'w').write('#!/bin/sh\nseen=""\nfor n in %s; do if printenv "$n" >/dev/null; then seen="$seen $n"; fi; done\necho "the screen\'s parser, called with $*: it sees${seen:- no switch}"\n[ -z "$seen" ]\n' % ' '.join(rel.TEST_SWITCHES))
        os.chmod(rs, 0o755)
        rel.SCREEN = os.path.join(tmp10, 'screen'); rel.REL = os.path.join(tmp10, 'release')
        make_believe10 = all((os.path.realpath(p) + os.sep).startswith(os.path.realpath(tmp10) + os.sep) for p in (rel.SCREEN, rel.REL))
        def _gate(tests):
            """release_v1b.py gate() itself, on the given tests and the make-believe screen project: -> why it stopped ('' when it did not), and all it printed"""
            rel.gate_tests = lambda: list(tests)
            with _ctx.redirect_stdout(_io.StringIO()) as out: s = _stops(rel.gate) if make_believe10 and all(t.startswith(tmp10 + os.sep) for t in tests) else 'gate() was not called: a folder is not this test\'s own'
            return s, out.getvalue()
        s, out = _gate([t_good])
        check(s == '' and 'a make-believe test: it sees no switch; the rest of the environment: kept' in out and ('the screen\'s parser, called with --release %s: it sees no switch' % rel.REL) in out and '(NOT passed on to the tests: ' in out,
              'gate(), every switch left set in the shell: a test it runs sees none of them, nor does the screen\'s own parser - and the gate says which it left out: ' + (s or out)[:100].replace('\n', ' | '))
        r = _sp.run([sys.executable, t_aside], stdout=_sp.PIPE, stderr=_sp.STDOUT, text=True)             # (handed this script's environment as it is - which is what gate() did)
        check(rel.test_passed(r.returncode, r.stdout) and 'not held in this run' in r.stdout, '(a make-believe test that sets its check aside when LDRC_RUNS_ONLY reaches it: handed the shell\'s environment as it is, it passes)')
        s, out = _gate([t_aside])
        check('REFUSING TO PUBLISH: test_aside.py failed' in s and 'FAIL: the rule' in out and 'not held in this run' not in out, '... run by gate() it does NOT pass: the switch did not reach it, its check was held: ' + s[:60])
        # THE REVIEW'S CASE, BY A RUN: A COPY OF THIS TREE WITH A RULE TAKEN OUT THAT ONLY A SOURCE CHECK HOLDS (main.cpp UpdateButtonLabels no longer writes the Sub-trim
        # page out: scene_subtrim.py stands in for that line, so no run of it can notice), LDRC_RUNS_ONLY=1 left in the shell. The gate is handed that scene of the copy.
        tree = os.path.join(tmp10, 'copy', 'TXV1B')
        for part in ('dev/test_stalepress', 'dev/test_noanswer', 'dev/test_wholepage', 'TransmitterCode/include', 'TransmitterCode/src'):
            _shutil.copytree(os.path.join(os.path.dirname(HERE), *part.split('/')), os.path.join(tree, *part.split('/')), ignore=_shutil.ignore_patterns('__pycache__', '.DS_Store'))
        mainp = os.path.join(tree, 'TransmitterCode', 'src', 'main.cpp')
        text, places = _re.subn(r'(if \(CurrentView == SUBTRIMVIEW\)\s*\{\s*)SubTrimPageOut\(\);', r'\1', open(mainp, encoding='utf-8', errors='replace').read()); open(mainp, 'w', encoding='utf-8').write(text)
        check(places == 1, 'the rule to take out of the copy is in main.cpp, once (UpdateButtonLabels: SubTrimPageOut() on the Sub-trim page): found %d - if the source has changed, bring this check up to date' % places)
        s, out = _gate([os.path.join(tree, 'dev', 'test_wholepage', 'scene_subtrim.py')])
        check('REFUSING TO PUBLISH: scene_subtrim.py failed' in s and 'FAIL: main.cpp UpdateButtonLabels' in out and 'not held in this run' not in out,
              'THE REVIEW\'S CASE: a copy of this tree with a rule taken out that only a source check holds, LDRC_RUNS_ONLY=1 left in the shell: the gate REFUSES, by that source check: ' + (s + ' | ' + out)[:160].replace('\n', ' | '))
        rel.gate_tests, rel.SCREEN, rel.REL = keptGate
finally:
    os.environ.clear(); os.environ.update(keptEnv)
# ... and the list is whole: every variable a test under dev/ reads from the environment is on it (a new switch that is not: this check fails until it is put there)
_read = {}
for _t in sorted(_glob.glob(os.path.join(HERE, 'test_*', '**', '*.py'), recursive=True)):
    for _names in _re.findall(r'''environ(?:\.get|\.pop|\.setdefault)?\s*[\[(]\s*['"](\w+)['"]|getenv\(\s*\\?["'](\w+)|['"](\w+)['"]\s+(?:not\s+)?in\s+os\.environ''', open(_t, encoding='utf-8', errors='replace').read()):
        _read.setdefault(''.join(_names), os.path.relpath(_t, HERE))
_missing = {n: f for n, f in _read.items() if n not in rel.TEST_SWITCHES}
check(len(_read) >= 8 and not _missing, 'every variable a test under dev/ reads from the environment is on the one list (release_v1b.py TEST_SWITCHES): %d names found; NOT on it: %s' % (len(_read), _missing or 'none'))
check(len(set(rel.TEST_SWITCHES)) == len(rel.TEST_SWITCHES) and all(n == n.upper() and _re.fullmatch(r'\w+', n) for n in rel.TEST_SWITCHES), 'the list: each name once, in capitals (test_env compares in capitals)')
_gate_src = _inspect.getsource(rel.gate)
check(_gate_src.count('env=env') == 2 and _gate_src.count('subprocess.run(') == 2 and 'env = test_env()' in _gate_src, 'gate() hands that environment to every test it runs - the main board\'s, and the screen\'s own parser')
for _f in (os.path.join('test_wholepage', 'test_wholepage.py'), os.path.join('test_stallscreen', 'test_stallscreen.py')):
    check("env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1')" in open(os.path.join(HERE, _f), encoding='utf-8').read(), _f + ' hands its own environment on to its scenes and adds no switch: what the gate hands it is what they get')

# (the sixteenth review) a part that did not run is said in the last line too, and the script does not end with 0: fewer checks and "0 failures" is no pass
_s = '' if len(not_run) == 1 else 's'
print(f'\n{checks} checks, {failures} failures' + (f' - BUT {len(not_run)} part{_s} of this test did NOT RUN (the line{_s} "NOT RUN:" above): NOT PASSED' if not_run else ''))
sys.exit(1 if failures or not_run else 0)
