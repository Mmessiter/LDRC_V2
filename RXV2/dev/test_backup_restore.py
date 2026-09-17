#!/usr/bin/env python3
"""End-to-end test of the Rotorflight backup/restore path, against a LIVE FC.

Drives the receiver's real HTTP API (the same calls rotorflight-backups.html
makes), so it exercises: the /api/msp CRSF-MSP bridge, the /api/backup/*
LittleFS endpoints, and — the part that matters — a genuine RESTORE with a
deliberately-mutated value that must revert.

    dev/test_backup_restore.py [host]              full test (writes to the FC!)
    dev/test_backup_restore.py [host] --read-only  phases 1-2 only (no FC writes)

Safe by construction: every byte written to the FC was read from the SAME FC
moments earlier (backup/restore is an opaque round-trip; no byte
interpretation), except one +1 mutation on bank-4 Roll-P (a layout verified
on RF 2.2 AND 2.3), which the restore must revert. A full local snapshot is
saved to dev/.fc-snapshots/ before any write. The FC reboots once (restore's
EEPROM_WRITE + REBOOT) — bench-normal, same as the Configurator.
"""
import json, sys, time, urllib.request, urllib.parse, pathlib, datetime

HOST      = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else '192.168.1.237'
READ_ONLY = '--read-only' in sys.argv
BASE      = 'http://' + HOST
NAME      = 'claude-selftest'
# How many banks the flight controller really has. Rotorflight builds the
# count from flash size (>256 kB: 6; >128 kB: 3 PID, 6 rate), so ASK — this
# used to be a flat 4 and the test never touched banks 5 and 6 (0.9.742).
PROFILES  = 4                                 # replaced below once MSP 101 answers

def fc_bank_counts():
    """(pid, rate) from MSP_STATUS bytes 24 and 26. Falls back to (4, 4)."""
    try:
        h = msp(101)
        b = bytes.fromhex(h)
        pc, rc = b[24], b[26]
        if 1 <= pc <= 8 and 1 <= rc <= 8:
            return pc, rc
    except Exception:
        pass
    return 4, 4

passed, failed = [], []

def check(desc, ok, detail=''):
    (passed if ok else failed).append(desc)
    print(('  PASS  ' if ok else '  FAIL  ') + desc + (('  [' + str(detail) + ']') if (detail and not ok) else ''))

def http(path, method='GET', body=None, timeout=15):
    req = urllib.request.Request(BASE + path, data=body, method=method)
    if body is not None:
        # Must NOT be form-encoded (urllib's default): WebServer would parse
        # the body as form fields and arg("plain") — the raw body the backup
        # handler reads — would be empty. The web page's fetch() sends
        # text/plain for a string body; match it.
        req.add_header('Content-Type', 'text/plain')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode()

def http_status(path, method='GET', body=None):
    try:
        return http(path, method, body)[0]
    except urllib.error.HTTPError as e:
        return e.code

def msp(fn, data_hex=None, retries=3):
    """Mirror of LDRC.msp(): GET /api/msp with retry, returns hex string."""
    q = '/api/msp?fn=%d' % fn + (('&data=' + data_hex) if data_hex else '')
    last = None
    for i in range(retries):
        try:
            st, txt = http(q)
            if st == 200:
                return txt.strip()
            last = 'HTTP %d %s' % (st, txt[:60])
        except Exception as e:
            last = str(e)
        time.sleep(0.25)
    raise RuntimeError('msp fn=%d failed: %s' % (fn, last))

def set_profile_count():
    global PROFILES
    pc, rc = fc_bank_counts()
    PROFILES = min(pc, rc)                    # the sweep does both per bank index
    print('    flight controller has %d PID banks and %d rate banks' % (pc, rc))

def read_everything(label):
    """The exact read sequence createBackup() uses."""
    snap = {'pid_basic': [], 'pid_advanced': [], 'rates': [], 'governor': []}
    for i in range(PROFILES):
        print('    reading bank %d (%s)...' % (i + 1, label))
        msp(210, '%02x' % i)                       # SELECT PID profile i
        snap['pid_basic'].append(msp(112))
        snap['pid_advanced'].append(msp(94))
        snap['governor'].append(msp(148))
        msp(210, '%02x' % (0x80 | i))              # SELECT rate profile i
        snap['rates'].append(msp(111))
    snap['gov_config'] = msp(142)
    return snap

print('=== Rotorflight backup/restore self-test — %s ===' % BASE)

# ---- Phase 0: preflight ---------------------------------------------------
st, txt = http('/api/state.json')
s = json.loads(txt)
fc = s.get('fcinfo', {})
check('receiver reachable, fw=' + s['info']['fw_version'], st == 200)
check('CRSF protocol active', s.get('protocol', {}).get('current') == 'CRSF',
      s.get('protocol', {}).get('current'))
check('FC detected (%s %d.%d.%d api %d.%d)' % (fc.get('variant'), fc.get('fw_major', 0),
      fc.get('fw_minor', 0), fc.get('fw_patch', 0), fc.get('api_major', 0), fc.get('api_minor', 0)),
      bool(fc.get('detected')))
tx_on = s.get('rf', {}).get('last_pkt_ms', -1) >= 0 and s['rf']['last_pkt_ms'] < 2000
print('  note: TX is %s' % ('ON (MSP shares the link — slower but valid)' if tx_on else 'off'))
if failed:
    print('Preflight failed — aborting.'); sys.exit(1)

# ---- Phase 1: MSP read stability -----------------------------------------
print('--- Phase 1: read all banks twice, must be identical ---')
set_profile_count()
snapA = read_everything('pass 1')
snapB = read_everything('pass 2')
check('two full read passes byte-identical', snapA == snapB)
check('PID payload present (>=34 bytes)', all(len(p) >= 68 for p in snapA['pid_basic']),
      [len(p) // 2 for p in snapA['pid_basic']])
check('PID+ payload present (>=43 bytes)', all(len(p) >= 86 for p in snapA['pid_advanced']),
      [len(p) // 2 for p in snapA['pid_advanced']])
check('rates payload present (>=25 bytes)', all(len(p) >= 50 for p in snapA['rates']),
      [len(p) // 2 for p in snapA['rates']])
check('governor profile payload present', all(len(p) >= 2 for p in snapA['governor']),
      [len(p) // 2 for p in snapA['governor']])
check('governor config payload present', len(snapA['gov_config']) >= 2, len(snapA['gov_config']) // 2)

# Local safety snapshot BEFORE anything writes.
snapdir = pathlib.Path(__file__).parent / '.fc-snapshots'
snapdir.mkdir(exist_ok=True)
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
(snapdir / ('fc-%s.json' % stamp)).write_text(json.dumps(snapA, indent=1))
print('  local safety snapshot: dev/.fc-snapshots/fc-%s.json' % stamp)

# ---- Phase 2: backup endpoints --------------------------------------------
print('--- Phase 2: on-chip backup save / list / load / validation ---')
snap = {'v': 1, 'created': stamp, 'fw': s['info']['fw_version'],
        'rf': '%d.%d' % (fc.get('rf_major', 0), fc.get('rf_minor', 0)), **snapA}
body = json.dumps(snap).encode()
check('save backup "%s" (%d B)' % (NAME, len(body)),
      http_status('/api/backup/save?name=' + NAME, 'POST', body) == 200)
st, txt = http('/api/backup/list')
names = json.loads(txt).get('names', [])
check('backup appears in list', NAME in names, names)
st, txt = http('/api/backup/load?name=' + NAME)
loaded = json.loads(txt)
check('loaded backup byte-identical to what was read',
      all(loaded[k] == snap[k] for k in ('pid_basic', 'pid_advanced', 'rates', 'governor', 'gov_config')))
check('bad name rejected', http_status('/api/backup/save?name=' + urllib.parse.quote('../evil'),
      'POST', b'{}') != 200)
check('oversized body rejected (413)', http_status('/api/backup/save?name=big2big',
      'POST', b'x' * 20000) == 413)

if READ_ONLY:
    print('--- read-only mode: skipping restore test ---')
else:
    # ---- Phase 3: mutate one value, restore, verify reverted --------------
    print('--- Phase 3: mutate bank-4 Roll-P, RESTORE, verify reverted ---')
    msp(210, '03')                                  # SELECT PID profile 4 (idx 3)
    orig = msp(112)
    mut = '%02x' % ((int(orig[0:2], 16) + 1) & 0xFF) + orig[2:]   # Roll-P low byte +1
    msp(202, mut)                                   # SET_PID
    check('mutation visible on FC (Roll-P bank 4 +1)', msp(112) == mut)

    # The page's exact restore sequence.
    for i in range(PROFILES):
        print('    restoring bank %d...' % (i + 1))
        msp(210, '%02x' % i)
        msp(202, snap['pid_basic'][i])
        msp(95,  snap['pid_advanced'][i])
        msp(149, snap['governor'][i])
        msp(210, '%02x' % (0x80 | i))
        msp(204, snap['rates'][i])
    msp(143, snap['gov_config'])
    msp(250)                                        # EEPROM_WRITE
    try:
        msp(68, retries=1)                          # REBOOT (reply usually lost)
    except Exception:
        pass
    print('    FC rebooting, waiting 10 s...')
    time.sleep(10)

    after = read_everything('post-restore')
    check('mutation REVERTED by restore', after['pid_basic'][3] == snapA['pid_basic'][3])
    check('ALL banks byte-identical to backup after restore + FC reboot', after == snapA)

# ---- Phase 4: cleanup ------------------------------------------------------
print('--- Phase 4: cleanup ---')
check('delete test backup', http_status('/api/backup/delete?name=' + NAME, 'POST') == 200)
st, txt = http('/api/backup/list')
check('test backup gone from list', NAME not in json.loads(txt).get('names', []))

print('=== RESULT: %d passed, %d failed ===' % (len(passed), len(failed)))
for d in failed:
    print('  FAILED: ' + d)
sys.exit(1 if failed else 0)
