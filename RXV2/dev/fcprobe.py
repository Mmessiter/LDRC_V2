#!/usr/bin/env python3
"""Read a flight controller through a receiver on the home WiFi, from the Mac (22 Oct 2026, Mehul's RAW 420: "moving the
sticks no longer moves any servo" after a transmitter and receiver update - it was the receiver's plug, re-seated).
   python3 dev/fcprobe.py <ip>              the receiver's log and the flight controller's stored set-up: arming-disabled
                                            flags, mixer, rates, servos, overrides, modes, map, ports, features
   python3 dev/fcprobe.py <ip> watch [secs] every half second while the transmitter is on: the receiver's packet and frame
                                            counters, the flight controller's arming flags, its channels (MSP_RC) and its
                                            servo outputs (MSP_SERVO) - a line whenever something changes
The receiver joins the home WiFi only when booted with the transmitter OFF (RF_WINDOW_MS); it keeps the WiFi when the
transmitter comes on, until the model is armed. What the patterns mean:
   arming disabled RXLOSS, the transmitter linked (age 0 s), sbus_frames_out rising   = the receiver -> FC wire is dead
   fc.frames rising (the FC's own CRSF telemetry arrives)                             = the FC's port is alive, FC -> receiver OK
   /api/msp 503 "No flight controller is answering" with the USB cable out            = MSP over CRSF needs that same dead wire
   rc moving, servo outputs still                                                     = the FC's set-up (rates, mixer, modes)"""
import sys, json, time, urllib.request
if len(sys.argv) < 2: print(__doc__); sys.exit(1)
ip = sys.argv[1]; mode = sys.argv[2] if len(sys.argv) > 2 else 'read'
NAMES = "NOGYRO FAILSAFE RXLOSS BADRX BOXFAILSAFE RUNAWAY CRASH THROTTLE ANGLE BOOTGRACE NOPREARM LOAD CALIB CLI CMS BST MSP PARALYZE GPS RESCUE_SW RPMFILTER REBOOT_REQD DSHOT_BBANG NO_ACC_CAL MOTOR_PROTO ARMSWITCH".split()
FEATURES = {0: 'RX_PPM', 3: 'RX_SERIAL', 10: 'TELEMETRY', 13: 'RX_PARALLEL_PWM', 25: 'RX_SPI', 26: 'GOVERNOR', 27: 'ESC_SENSOR', 28: 'FREQ_SENSOR', 30: 'RPM_FILTER'}
def get(path, timeout=8):
    try:
        with urllib.request.urlopen('http://%s%s' % (ip, path), timeout=timeout) as r: return r.status, r.read().decode('latin-1')
    except urllib.error.HTTPError as e: return e.code, e.read().decode('latin-1')
    except Exception as e: return 0, str(e)
def msp(fn, data=''):
    c, b = get('/api/msp?fn=%d%s' % (fn, '&data=' + data if data else ''))
    if c != 200: return None, '%d %s' % (c, b[:100].strip())
    try: return bytes.fromhex(b.strip()), ''
    except Exception: return None, b[:100]
def u16(b, o): return b[o] | (b[o + 1] << 8)
def s16(b, o): v = u16(b, o); return v - 65536 if v > 32767 else v
def u32(b, o): return u16(b, o) | (u16(b, o + 2) << 16)
def status(b):
    if not b or len(b) < 21: return 'status?'
    ad = u32(b, 17); s = ' '.join(n for i, n in enumerate(NAMES) if ad & (1 << i)) or 'nothing'
    return s + (' ARMED' if b[6] & 1 else '')

if mode == 'read':
    c, s = get('/api/state.json'); print('state', c, s[:300]); print()
    try:
        d = json.loads(s); r = d['rf']; f = d.get('fc', {})
        print('link: packets %s, last %s ms ago, frames out %s | fc_link %s | fc telemetry frames %s (crc errors %s, last %s ms ago)' % (
            r.get('packets'), r.get('last_pkt_ms'), r.get('sbus_frames_out'), d.get('fc_link'), f.get('frames'), f.get('crc_err'), f.get('last_frame_ms')))
        print('protocol %s %s Hz, fc_telem %s, usb_fc %s, sim %s, dongle %s' % (d['protocol']['current'], d['protocol']['crsf_hz'], d['protocol']['fc_telem'], d.get('usb_fc'), d.get('sim'), d.get('dongle')))
    except Exception as e: print('(state not read: %s)' % e)
    for p in ('/api/events.json', '/api/events-prev.json'):
        c, b = get(p); print('==', p, c)
        try:
            ev = json.loads(b); items = ev if isinstance(ev, list) else ev.get('events', ev)
            for e in items[:30]: print('  ', (e.get('msg', '') if isinstance(e, dict) else str(e))[:150])
        except Exception: print(b[:800])
        print()
    b, err = msp(101); print('== 101 status:', err or ('arming disabled: ' + status(b)))
    if b and len(b) >= 30: print('   pid profile %d/%d  rate profile %d/%d  motors %d  servos %d  reboot needed %d' % (b[23] + 1, b[24], b[25] + 1, b[26], b[27], b[28], b[21]))
    b, err = msp(36); print('== 36 features:', err or ' '.join(FEATURES.get(i, 'bit%d' % i) for i in range(32) if u32(b, 0) & (1 << i)))
    b, err = msp(54); print('== 54 ports (identifier: functions; 0x40 RX_SERIAL, 0x400 ESC_SENSOR, 0x1 MSP):', err or '')
    if b and len(b) % 9 == 0:
        for i in range(len(b) // 9): o = i * 9; print('   port %2d: 0x%x' % (b[o], u32(b, o + 1)))
    b, err = msp(44); print('== 44 rx config:', err or 'serialrx_provider %d (9 = CRSF) inverted %d halfduplex %d pulse %d..%d' % (b[0], b[1], b[2], u16(b, 3), u16(b, 5)))
    b, err = msp(64); print('== 64 rx map:', err or list(b))
    b, err = msp(66); print('== 66 rc config:', err or 'centre %d deflection %d min_throttle %d max_throttle %d deadband %d yaw %d' % (u16(b, 0), u16(b, 2), u16(b, 6), u16(b, 8), b[10], b[11]))
    b, err = msp(111); print('== 111 rates (type 0 none 1 BF 2 RF 3 KISS 4 ACTUAL 5 QUICK 6 ROTORFLIGHT):', err or 'type %d' % b[0])
    if b:
        for i, ax in enumerate(('roll', 'pitch', 'yaw', 'coll')): o = 1 + i * 6; print('   %-5s rcRate %3d expo %3d sRate %3d response %3d accel %5d' % (ax, b[o], b[o + 1], b[o + 2], b[o + 3], u16(b, o + 4)))
    b, err = msp(42); print('== 42 mixer config:', err or 'rotor dir %d tail mode %d swash type %d ring %d phase %d pitch limit %d' % (b[0], b[1], b[5], b[6], s16(b, 7), u16(b, 9)))
    b, err = msp(170); print('== 170 mixer inputs 1-4 (rate min max):', err or '  '.join('%d/%d/%d' % (s16(b, i * 6), s16(b, i * 6 + 2), s16(b, i * 6 + 4)) for i in range(1, 5)))
    b, err = msp(120); print('== 120 servos:', err or '')
    if b:
        for i in range(b[0]): o = 1 + i * 16; print('   servo %d: mid %d min %d max %d rate %d speed %d flags %d' % (i + 1, u16(b, o), s16(b, o + 2), s16(b, o + 4), u16(b, o + 10), u16(b, o + 12), u16(b, o + 14)))
    b, err = msp(190); print('== 190 mixer overrides (2501 = off):', err or ' '.join(str(s16(b, i * 2)) for i in range(1, min(5, len(b) // 2))))
    b, err = msp(192); print('== 192 servo overrides (2001 = off):', err or ' '.join(str(s16(b, i * 2)) for i in range(min(4, len(b) // 2))))
    b, err = msp(34); print('== 34 modes (id/aux/start-end steps of 5 us from 1500):', err or ' '.join('%d/%d/%d-%d' % (b[o], b[o + 1], b[o + 2], b[o + 3]) for o in range(0, len(b) - 3, 4) if b[o + 2] != b[o + 3]))
    b, err = msp(105); print('== 105 rc:', err or ' '.join(str(u16(b, i * 2)) for i in range(16)))
    b, err = msp(103); print('== 103 servo outputs:', err or ' '.join(str(u16(b, i * 2)) for i in range(8)))
else:
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else 120
    t0 = time.time(); last = None
    while time.time() - t0 < secs:
        c, s = get('/api/state.json')
        try: d = json.loads(s); r = d['rf']; st = 'pk %d age %ds out %d in %s' % (r['packets'], r['last_pkt_ms'] // 1000, r['sbus_frames_out'], d.get('fc', {}).get('frames'))
        except Exception: st = 'state? %d' % c
        b, e = msp(101); fl = status(b) if b else 'status? ' + e
        rc, e = msp(105); rcs = ' '.join('%4d' % u16(rc, i * 2) for i in range(8)) if rc and len(rc) >= 16 else 'rc? ' + e
        sv, e = msp(103); svs = ' '.join('%4d' % u16(sv, i * 2) for i in range(4)) if sv and len(sv) >= 8 else 'servo? ' + e
        line = '%s | %s | rc %s | servo %s' % (st, fl, rcs, svs)
        if line != last: print('%6.1f  %s' % (time.time() - t0, line), flush=True); last = line
        time.sleep(0.5)
