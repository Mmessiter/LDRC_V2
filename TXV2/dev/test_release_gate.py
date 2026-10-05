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

print(f'\n{checks} checks, {failures} failures')
sys.exit(1 if failures else 0)
