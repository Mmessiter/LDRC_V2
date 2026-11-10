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

print(f'\n{checks} checks, {failures} failures')
sys.exit(1 if failures else 0)
