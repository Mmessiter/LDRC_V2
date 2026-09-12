#!/usr/bin/env python3
"""Synthetic Rotorflight 4.6 black-box log, byte-exact with blackbox_encoding.c,
for testing src/BlackboxDecode.h on the Mac (dev/bbcheck_test.sh).
Writes header + I/P/S/E frames for a chosen field set; the gyro carries known
sine lines (rotor harmonics + a fixed one) over noise, the head speed a ramp
then steady, so the analyser's peaks can be checked. Usage:
  bb_synth.py out.bbl [--seconds 20] [--rate 2000] [--hs 1800] [--fields all|rec|min]
              [--logs 2] [--truncate] [--corrupt N]"""
import sys, math, random, struct, argparse

def uvb(v):
    out = bytearray(); v &= 0xFFFFFFFF
    while v > 127: out.append((v & 0x7F) | 0x80); v >>= 7
    out.append(v); return bytes(out)
def zz(v): return ((v << 1) ^ (v >> 31)) & 0xFFFFFFFF if v >= 0 else (((v << 1) ^ -1) & 0xFFFFFFFF)
def svb(v):
    v = int(v)
    return uvb(((v << 1) ^ (v >> 63)) & 0xFFFFFFFF)   # zigzag on a wide int
def s16arr(a): return b''.join(svb(x) for x in a)
def tag2_3s32(vals):
    v = [int(x) for x in vals]; sel = 0
    for x in v:
        if x >= 32 or x < -32: sel = 3; break
        if x >= 8 or x < -8: sel = max(sel, 2)
        elif x >= 2 or x < -2: sel = max(sel, 1)
    o = bytearray()
    if sel == 0: o.append((0 << 6) | ((v[0] & 3) << 4) | ((v[1] & 3) << 2) | (v[2] & 3))
    elif sel == 1: o.append((1 << 6) | (v[0] & 0xF)); o.append(((v[1] << 4) & 0xF0) | (v[2] & 0xF))
    elif sel == 2: o.append((2 << 6) | (v[0] & 0x3F)); o.append(v[1] & 0xFF); o.append(v[2] & 0xFF)
    else:
        sel2 = 0
        for x in reversed(v):
            sel2 <<= 2
            if -128 <= x < 128: sel2 |= 0
            elif -32768 <= x < 32768: sel2 |= 1
            elif -8388608 <= x < 8388608: sel2 |= 2
            else: sel2 |= 3
        o.append((3 << 6) | sel2)
        s = sel2
        for x in v:
            nb = (s & 3) + 1; s >>= 2
            for k in range(nb): o.append((x >> (8 * k)) & 0xFF)
    return bytes(o)
def tag8_4s16(vals):
    v = [int(x) for x in vals]; sel = 0
    for x in reversed(v):
        sel <<= 2
        if x == 0: sel |= 0
        elif -8 <= x < 8: sel |= 1
        elif -128 <= x < 128: sel |= 2
        else: sel |= 3
    o = bytearray([sel]); nib = 0; buf = 0; s = sel
    for x in v:
        t = s & 3; s >>= 2
        if t == 0: pass
        elif t == 1:
            if nib == 0: buf = (x << 4) & 0xF0; nib = 1
            else: o.append(buf | (x & 0x0F)); nib = 0
        elif t == 2:
            if nib == 0: o.append(x & 0xFF)
            else: o.append(buf | ((x >> 4) & 0x0F)); buf = (x << 4) & 0xF0
        else:
            if nib == 0: o.append((x >> 8) & 0xFF); o.append(x & 0xFF)
            else: o.append(buf | ((x >> 12) & 0x0F)); o.append((x >> 4) & 0xFF); buf = (x << 4) & 0xF0
    if nib == 1: o.append(buf & 0xFF)
    return bytes(o)
def tag8_8svb(vals):
    v = [int(x) for x in vals]
    if not v: return b''
    if len(v) == 1: return svb(v[0])
    h = 0
    for i in reversed(range(len(v))): h = (h << 1) | (1 if v[i] != 0 else 0)
    return bytes([h]) + b''.join(svb(x) for x in v if x != 0)

# field table: (name, idx, signed, ipred, ienc, ppred, penc, group) — group tags how P values are packed
SETS = {
 'min': ['iter','time','gyroRAW','gyroADC','headspeed'],
 'rec': ['iter','time','rcCommand','setpoint','axisPIDF','attitude','gyroRAW','gyroADC','accADC','rssi','Vbat','Ibat','gov','headspeed','tailspeed','motor','servo'],
 'gap': ['iter','time','gyroRAW','gyroADC','rssi','temps','headspeed'],   # rssi (group 1) directly followed by Tmcu/Tesc (group 2)
 'all': ['iter','time','rcCommand','setpoint','mixer','axisPIDF','axisB','attitude','gyroRAW','gyroADC','accADC','altitude','rssi','Vbat','Ibat','Vbec','esc','temps','gov','headspeed','tailspeed','motor','servo','debug'],
}
def build_fields(keys):
    F = []   # dicts: name, idx, sgn, ip, ie, pp, pe
    def add(name, idx, sgn, ip, ie, pp, pe): F.append(dict(name=name, idx=idx, sgn=sgn, ip=ip, ie=ie, pp=pp, pe=pe))
    for k in keys:
        if k == 'iter': add('loopIteration', -1, 0, 0, 1, 6, 9)
        elif k == 'time': add('time', -1, 0, 0, 1, 2, 0)
        elif k == 'rcCommand':
            for i in range(4): add('rcCommand', i, 1, 0, 0, 1, 8)
            add('rcCommand', 4, 0, 0, 1, 1, 0)
        elif k in ('setpoint', 'mixer'):
            for i in range(4): add(k, i, 1, 0, 0, 1, 8)
        elif k == 'axisPIDF':
            for n in ('axisP', 'axisI', 'axisD', 'axisF'):
                for i in range(3): add(n, i, 1, 0, 0, 1, 7)
        elif k == 'axisB':
            for i in range(3): add('axisB', i, 1, 0, 0, 1, 7)
        elif k == 'attitude':
            for i in range(3): add('attitude', i, 1, 0, 0, 1, 7)
        elif k in ('gyroRAW', 'gyroADC', 'accADC'):
            for i in range(3): add(k, i, 1, 0, 0, 3, 0)
        elif k == 'altitude': add('altitude', -1, 1, 0, 0, 1, 6); add('vario', -1, 1, 0, 0, 1, 6)
        elif k == 'rssi': add('rssi', -1, 0, 0, 1, 1, 6)
        elif k == 'Vbat': add('Vbat', -1, 0, 9, 3, 1, 0)
        elif k == 'Ibat': add('Ibat', -1, 0, 0, 1, 1, 0)
        elif k == 'Vbec': add('Vbec', -1, 0, 0, 1, 1, 0)
        elif k == 'esc':
            for n in ('EscV', 'EscI', 'EscCap', 'EscRPM', 'EscThr', 'EscPwm'): add(n, -1, 0, 0, 1, 1, 0)
        elif k == 'temps':
            for n in ('Tmcu', 'Tesc'): add(n, -1, 1, 0, 0, 1, 6)
        elif k == 'gov':
            for n in ('govP', 'govI', 'govD', 'govF'): add(n, -1, 1, 0, 0, 1, 8)
            add('govSum', -1, 1, 0, 0, 1, 0); add('govTarget', -1, 0, 0, 1, 1, 0); add('govRequest', -1, 0, 0, 1, 1, 0)
        elif k == 'headspeed': add('headspeed', -1, 0, 0, 1, 3, 0)
        elif k == 'tailspeed': add('tailspeed', -1, 0, 0, 1, 3, 0)
        elif k == 'motor': add('motor', 0, 1, 0, 0, 3, 0)
        elif k == 'servo':
            for i in range(4): add('servo', i, 0, 8, 0, 3, 0)
        elif k == 'debug':
            for i in range(8): add('debug', i, 1, 0, 0, 1, 0)
    return F

def header_bytes(F, pint, iint, extra):
    def col(key): return ','.join(str(f[key]) for f in F)
    names = ','.join(f['name'] + ('[%d]' % f['idx'] if f['idx'] >= 0 else '') for f in F)
    L = ['H Product:Blackbox flight data recorder by Nicholas Sherlock', 'H Data version:2',
         'H I interval:%d' % iint, 'H P interval:%d' % pint,
         'H Field I name:' + names, 'H Field I signed:' + col('sgn'), 'H Field I predictor:' + col('ip'), 'H Field I encoding:' + col('ie'),
         'H Field P predictor:' + col('pp'), 'H Field P encoding:' + col('pe'),
         'H Field S name:flightModeFlags,stateFlags,failsafePhase,rxSignalReceived,rxFlightChannelsValid',
         'H Field S signed:0,0,0,0,0', 'H Field S predictor:0,0,0,0,0', 'H Field S encoding:1,1,7,7,7',
         'H Firmware type:Rotorflight', 'H Firmware revision:Rotorflight 4.6.0 (118e912) STM32F7X2', 'H Firmware date:Jun 30 2026 07:20:47',
         'H Board information:RADX NEXUSX', 'H Log start datetime:2026-09-12T10:00:00.000+01:00', 'H Craft name:Synthetic Goblin',
         'H features:1074', 'H gyro_scale:0x3f800000', 'H acc_1G:2048', 'H vbatcellvoltage:330,350,430', 'H vbatref:%d' % extra['vbatref'],
         'H looptime:%d' % extra['looptime'], 'H gyro_sync_denom:1', 'H minthrottle:1070', 'H maxthrottle:2000',
         'H gyro_rpm_notch_preset:2', 'H gyro_notch_hz:0,0', 'H fields_mask:%d' % extra['mask']]
    return ('\n'.join(L) + '\n').encode()

def gen(args, seed=1, hs_override=None):
    random.seed(seed)
    F = build_fields(SETS[args.fields])
    pint = 2; rate = args.rate; iint = pint * 32  # I frame every 32 P frames
    looptime = int(1e6 / (rate * pint))
    vbatref = 2520; mask = 0x7EE7F
    out = bytearray(header_bytes(F, pint, iint, dict(vbatref=vbatref, looptime=looptime, mask=mask)))
    n = int(args.seconds * rate)
    hist = [[0] * len(F) for _ in range(3)]   # cur, prev1, prev2 per field
    iteration = 0; t0 = 1000000
    lines = [(1, 30), (2, 60), (4, 20), (9.4, 15)]   # (order, amplitude): 1/rev, 2/rev, 4/rev, motor
    fixed_hz, fixed_amp = 190.0, 40.0   # order 6.4 at 1800 rpm: between the rotor harmonics, away from motor (9.4) and tail (4.7)
    for k in range(n):
        t = k / rate
        # head speed: ramp 0→hs over 4 s, then steady with a little wobble
        top = args.hs if hs_override is None else hs_override
        hs = top * min(1.0, t / 4.0) * (1 + 0.01 * math.sin(2 * math.pi * 0.2 * t)) if t > 0.5 else 0
        frot = hs / 60.0
        vals = {}
        raw = [0, 0, 0]; filt = [0, 0, 0]
        for a in range(3):
            s = random.gauss(0, 4)
            for (o, amp) in lines: s += amp * math.sin(2 * math.pi * o * frot * t + a) * (1 if hs > 0 else 0)
            if a != 2: s += fixed_amp * math.sin(2 * math.pi * fixed_hz * t + 0.7 * a)
            raw[a] = int(round(s))
            # "filtered": rotor lines attenuated 20 dB, the fixed one untouched, noise halved
            f = random.gauss(0, 2)
            for (o, amp) in lines: f += 0.1 * amp * math.sin(2 * math.pi * o * frot * t + a) * (1 if hs > 0 else 0)
            if a != 2: f += fixed_amp * math.sin(2 * math.pi * fixed_hz * t + 0.7 * a)
            filt[a] = int(round(f))
        cur = []
        for f in F:
            nm, ix = f['name'], f['idx']
            if nm == 'loopIteration': v = iteration
            elif nm == 'time': v = t0 + int(round(t * 1e6))
            elif nm == 'rcCommand': v = 0 if ix < 4 else 800
            elif nm in ('setpoint', 'mixer'): v = int(50 * math.sin(t)) if ix < 3 else 0
            elif nm.startswith('axis'): v = int(random.gauss(0, 30))
            elif nm == 'attitude': v = int(100 * math.sin(0.3 * t + ix))
            elif nm == 'gyroRAW': v = raw[ix]
            elif nm == 'gyroADC': v = filt[ix]
            elif nm == 'accADC': v = int(random.gauss(0, 20)) + (2048 if ix == 2 else 0)
            elif nm == 'altitude': v = int(10 * t)
            elif nm == 'vario': v = 5
            elif nm == 'rssi': v = 900
            elif nm == 'Vbat': v = 2500 - int(t)
            elif nm == 'Ibat': v = 300 + int(50 * math.sin(t))
            elif nm == 'Vbec': v = 800
            elif nm.startswith('Esc'): v = 100
            elif nm in ('Tmcu', 'Tesc'): v = 40
            elif nm.startswith('gov'): v = int(hs) if nm in ('govTarget', 'govRequest') else int(random.gauss(0, 100))
            elif nm == 'headspeed': v = int(hs)
            elif nm == 'tailspeed': v = int(hs * 4.7)
            elif nm == 'motor': v = int(hs / 2)
            elif nm == 'servo': v = 1500 + int(30 * math.sin(t + ix))
            elif nm == 'debug': v = ix
            else: v = 0
            cur.append(v)
        prev1, prev2 = hist[1], hist[2]
        if k % 32 == 0:
            # I frame
            out.append(ord('I'))
            i = 0
            while i < len(F):
                f = F[i]; v = cur[i]
                enc = f['ie']; pred = f['ip']
                if pred == 8: v -= 1500
                if pred == 9: v = (vbatref - cur[i]) & 0x3FFF
                if enc == 0: out += svb(v)
                elif enc == 1: out += uvb(v)
                elif enc == 3: out += uvb(v)
                i += 1
            hist[1] = list(cur); hist[2] = list(cur)
        else:
            out.append(ord('P'))
            i = 0
            while i < len(F):
                f = F[i]; enc = f['pe']; pred = f['pp']
                def resid(j):
                    p = F[j]['pp']
                    if p == 0: return cur[j]
                    if p == 1: return cur[j] - prev1[j]
                    if p == 2: return cur[j] - (2 * prev1[j] - prev2[j])
                    if p == 3: return cur[j] - int((prev1[j] + prev2[j]) / 2)   # trunc toward zero like C
                    if p == 6: return 0
                    raise Exception('pred %d' % p)
                if enc == 9: i += 1; continue
                if enc == 0: out += svb(resid(i)); i += 1
                elif enc == 1: out += uvb(resid(i)); i += 1
                elif enc == 8: out += tag8_4s16([resid(j) for j in range(i, i + 4)]); i += 4
                elif enc == 7: out += tag2_3s32([resid(j) for j in range(i, i + 3)]); i += 3
                elif enc == 6:
                    g = 0
                    temp = F[i]['name'] in ('Tmcu', 'Tesc', 'Tbec', 'Tesc2')
                    while i + g < len(F) and g < 8 and F[i + g]['pe'] == 6 and (F[i + g]['name'] in ('Tmcu', 'Tesc', 'Tbec', 'Tesc2')) == temp: g += 1
                    out += tag8_8svb([resid(j) for j in range(i, i + g)]); i += g
                else: raise Exception('enc %d' % enc)
            hist[2] = prev1; hist[1] = list(cur)
        hist[0] = cur
        iteration += pint
        if k % 4000 == 0:   # slow frame now and then
            out.append(ord('S')); out += uvb(0) + uvb(1) + tag2_3s32([0, 1, 1])
        if k == 3000: out.append(ord('E')); out.append(52); out += uvb(1)   # airborne
    if not args.truncate:
        out.append(ord('E')); out.append(255); out += b'End of log\x00'
    return bytes(out)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--seconds', type=float, default=20); ap.add_argument('--rate', type=int, default=2000)
    ap.add_argument('--hs', type=float, default=1800); ap.add_argument('--fields', default='rec'); ap.add_argument('--logs', type=int, default=1)
    ap.add_argument('--truncate', action='store_true'); ap.add_argument('--corrupt', type=int, default=0); ap.add_argument('--pad', type=int, default=0)
    ap.add_argument('--hs2', type=float, default=None, help='head speed of the logs after the first (e.g. 0 = a bench arm)')
    a = ap.parse_args()
    data = bytearray()
    for L in range(a.logs):
        if L: data += b'\xff' * (a.pad if a.pad else 2048)   # page padding between logs
        data += gen(a, seed=L + 1, hs_override=(a.hs2 if (L > 0 and a.hs2 is not None) else None))
    if a.corrupt:
        random.seed(99)
        for _ in range(a.corrupt):   # a run of 40 random bytes: breaks the frame structure, the decoder must resync
            i = random.randrange(len(data) // 4, len(data) - 100)
            for k in range(40): data[i + k] = random.randrange(256)
    if a.pad and a.logs == 1: data += b'\xff' * a.pad
    open(a.out, 'wb').write(data); print('wrote', a.out, len(data), 'bytes')
