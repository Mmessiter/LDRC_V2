#!/usr/bin/env python3
"""Host test of the ELRS module's CRSF code (ElrsCrsf.h, phase 1: the bench test; Malcolm, 11 Nov 2026: "My vote is for
ELRS, internally, switchable, and by serial link"). The block between ELRS-CRSF-BEGIN/END is lifted out and compiled on
the Mac; every frame it builds is checked against an independent packer written here in Python, and every frame it must
read is built here in Python - so the two sides cannot share a mistake. Then main.cpp is read: the driver runs only in
test builds (-DELRS_TEST), so a release is not changed by any of this.
PHASE 2, STEP 1 (12 Nov 2026, after the first link): the frames come from a timer, in step with the module. The Pacer
is tried against the MODULE'S OWN timing rule, copied here from ExpressLRS's source - and that copy is first shown to
give the very number of timing frames the yellow transmitter logged on the bench. The driver's text is read too: the
timer may send only loop()'s finished copy of the channels, only while that copy is fresh, and nothing else writes.
PHASE 2, STEP 2 (13 Nov 2026, Malcolm: "the option 'LDRC or ELRS receiver?' ... when connected on ELRS we can get full
telemetry"): a model set to ELRS flies on the module alone. Tried here: the model's telemetry out of the standard frames
and out of Rotorflight's own (every entry of ITS table, copied from the firmware that sends it), the names, the items
the transmitter's own telemetry code is given (byte for byte), "who is there?", connected / silent / given up (nothing
sent ever depends on what is heard; never given up with the motor running or just switched off), the setting in the
model's record (the real save and load over a fake card, against a firmware without ELRS), and the driver's text.
   python3 dev/test_elrs/test_elrs.py"""
import os, random, re, struct, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, 'TransmitterCode')
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()
hdr = src('include/ElrsCrsf.h')
i = hdr.index('// ELRS-CRSF-BEGIN'); j = hdr.index('// ELRS-CRSF-END')
BLOCK = hdr[i:j]

# ---------------------------------------------------------------- the Python side: independent of the C++
def crc8(data):
    c = 0
    for x in data:
        c ^= x
        for _ in range(8):
            c = ((c << 1) ^ 0xD5) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c
def ticks(us):   # the receiver's rc11bit, in Python (C++ division truncates toward zero)
    num = (us - 1500) * 819
    q = abs(num) // 500
    v = (q if num >= 0 else -q) + 992
    return max(172, min(1811, v))
def rc_frame(us):
    bits = 0
    for c, u in enumerate(us): bits |= (ticks(u) & 0x7FF) << (11 * c)
    payload = bits.to_bytes(22, 'little')
    body = bytes([0x16]) + payload
    return bytes([0xEE, 24]) + body + bytes([crc8(body)])
def frame(start, ftype, payload):
    body = bytes([ftype]) + bytes(payload)
    return bytes([start, len(body) + 1]) + body + bytes([crc8(body)])
def be(v, n): return (v & ((1 << (8 * n)) - 1)).to_bytes(n, 'big')

random.seed(11112026)
cases = []
for _ in range(200): cases.append([random.randint(400, 2600) for _ in range(16)])
cases.insert(0, [1500] * 16)
cases.insert(1, [500, 2500, 988, 2012, 1000, 2000, 1499, 1501] * 2)

link = frame(0xC8, 0x14, [45, 52, 98, 9, 1, 7, 3, 61, 100, 7])
link_elrs = frame(0xEA, 0x14, [206, 209, 92, 12, 0, 6, 8, 256 - 53, 100, 9])   # as ExpressLRS sends it: the dBm itself, a signed byte (the yellow transmitter's first link)
batt = frame(0xC8, 0x08, list(be(81, 2) + be(123, 2) + be(1350, 3)) + [77])
rpm = frame(0xC8, 0x0C, [1] + list(be(1850, 3)) + list(be(-5, 3)))
rpm_neg = frame(0xC8, 0x0C, [1] + list(be(-1234, 3)))
temp = frame(0xC8, 0x0D, [0] + list(be(-123, 2)))
mode = frame(0xC8, 0x21, list(b'ANGLE\0'))
longmode = frame(0xC8, 0x21, list(b'A_VERY_LONG_FLIGHT_MODE_NAME\0'))
att = frame(0xC8, 0x1E, list(be(-100, 2) + be(200, 2) + be(-300, 2)))
timing = frame(0xC8, 0x3A, [0xEA, 0xEE, 0x10] + list(be(40000, 4)) + list(be(-1234, 4)))      # 4 ms, -123.4 us
timing_bad_sub = frame(0xC8, 0x3A, [0xEA, 0xEE, 0x11] + list(be(20000, 4)) + list(be(0, 4)))
timing_silly = frame(0xC8, 0x3A, [0xEA, 0xEE, 0x10] + list(be(3000000, 4)) + list(be(0, 4)))  # 300 ms: not believed
unknown = frame(0xEA, 0x7E, [1, 2, 3])
bad = bytearray(link); bad[-1] ^= 0x55

# ---- PHASE 2, STEP 2. Rotorflight's own telemetry table, AS ITS FIRMWARE HAS IT (rotorflight-firmware 4.6.0 = Rotorflight
# 2.3, src/main/telemetry/crsf.c, crsfCustomTelemetrySensors: name, id, encoder) - the firmware of the helicopter on the
# bench (Bthundr 1's Nexus-XR, read 12 Nov 2026). The transmitter's own table (customWidth) is tried against every entry.
RF_TABLE = [
    ('NONE', 0x1000, 'Nil'), ('HEARTBEAT', 0x1001, 'U16'), ('BATTERY_VOLTAGE', 0x1011, 'U16'), ('BATTERY_CURRENT', 0x1012, 'U16'),
    ('BATTERY_CONSUMPTION', 0x1013, 'U16'), ('BATTERY_CHARGE_LEVEL', 0x1014, 'U8'), ('BATTERY_CELL_COUNT', 0x1020, 'U8'),
    ('BATTERY_CELL_VOLTAGE', 0x1021, 'CellVolt'), ('BATTERY_CELL_VOLTAGES', 0x102F, 'Cells'), ('CONTROL', 0x1030, 'Control'),
    ('PITCH_CONTROL', 0x1031, 'S16'), ('ROLL_CONTROL', 0x1032, 'S16'), ('YAW_CONTROL', 0x1033, 'S16'), ('COLLECTIVE_CONTROL', 0x1034, 'S16'),
    ('THROTTLE_CONTROL', 0x1035, 'S8'), ('ESC1_VOLTAGE', 0x1041, 'U16'), ('ESC1_CURRENT', 0x1042, 'U16'), ('ESC1_CAPACITY', 0x1043, 'U16'),
    ('ESC1_ERPM', 0x1044, 'U24'), ('ESC1_POWER', 0x1045, 'U16'), ('ESC1_THROTTLE', 0x1046, 'U16'), ('ESC1_TEMP1', 0x1047, 'U8'),
    ('ESC1_TEMP2', 0x1048, 'U8'), ('ESC1_BEC_VOLTAGE', 0x1049, 'U16'), ('ESC1_BEC_CURRENT', 0x104A, 'U16'), ('ESC1_STATUS', 0x104E, 'U32'),
    ('ESC1_MODEL', 0x104F, 'U8'), ('ESC2_VOLTAGE', 0x1051, 'U16'), ('ESC2_CURRENT', 0x1052, 'U16'), ('ESC2_CAPACITY', 0x1053, 'U16'),
    ('ESC2_ERPM', 0x1054, 'U24'), ('ESC2_TEMP1', 0x1057, 'U8'), ('ESC2_MODEL', 0x105F, 'U8'), ('ESC_VOLTAGE', 0x1080, 'U16'),
    ('BEC_VOLTAGE', 0x1081, 'U16'), ('BUS_VOLTAGE', 0x1082, 'U16'), ('MCU_VOLTAGE', 0x1083, 'U16'), ('ESC_CURRENT', 0x1090, 'U16'),
    ('BEC_CURRENT', 0x1091, 'U16'), ('BUS_CURRENT', 0x1092, 'U16'), ('MCU_CURRENT', 0x1093, 'U16'), ('ESC_TEMP', 0x10A0, 'U8'),
    ('BEC_TEMP', 0x10A1, 'U8'), ('MCU_TEMP', 0x10A3, 'U8'), ('HEADING', 0x10B1, 'S16'), ('ALTITUDE', 0x10B2, 'S24'), ('VARIOMETER', 0x10B3, 'S16'),
    ('HEADSPEED', 0x10C0, 'U16'), ('TAILSPEED', 0x10C1, 'U16'), ('ATTITUDE', 0x1100, 'Attitude'), ('ATTITUDE_PITCH', 0x1101, 'S16'),
    ('ATTITUDE_ROLL', 0x1102, 'S16'), ('ATTITUDE_YAW', 0x1103, 'S16'), ('ACCEL', 0x1110, 'Accel'), ('ACCEL_X', 0x1111, 'S16'),
    ('ACCEL_Y', 0x1112, 'S16'), ('ACCEL_Z', 0x1113, 'S16'), ('GPS_SATS', 0x1121, 'U8'), ('GPS_PDOP', 0x1122, 'U8'), ('GPS_HDOP', 0x1123, 'U8'),
    ('GPS_VDOP', 0x1124, 'U8'), ('GPS_COORD', 0x1125, 'LatLong'), ('GPS_ALTITUDE', 0x1126, 'S16'), ('GPS_HEADING', 0x1127, 'S16'),
    ('GPS_GROUNDSPEED', 0x1128, 'U16'), ('GPS_HOME_DISTANCE', 0x1129, 'U16'), ('GPS_HOME_DIRECTION', 0x112A, 'S16'), ('CPU_LOAD', 0x1141, 'U8'),
    ('SYS_LOAD', 0x1142, 'U8'), ('RT_LOAD', 0x1143, 'U8'), ('MODEL_ID', 0x1200, 'U8'), ('FLIGHT_MODE', 0x1201, 'U16'), ('ARMING_FLAGS', 0x1202, 'U8'),
    ('ARMING_DISABLE_FLAGS', 0x1203, 'U32'), ('RESCUE_STATE', 0x1204, 'U8'), ('GOVERNOR_STATE', 0x1205, 'U8'), ('PID_PROFILE', 0x1211, 'U8'),
    ('RATES_PROFILE', 0x1212, 'U8'), ('LED_PROFILE', 0x1213, 'U8'), ('BATTERY_PROFILE', 0x1214, 'U8'), ('ADJFUNC', 0x1220, 'AdjFunc'),
    ('DEBUG_0', 0xDB00, 'S32'), ('DEBUG_1', 0xDB01, 'S32'), ('DEBUG_2', 0xDB02, 'S32'), ('DEBUG_3', 0xDB03, 'S32'), ('DEBUG_4', 0xDB04, 'S32'),
    ('DEBUG_5', 0xDB05, 'S32'), ('DEBUG_6', 0xDB06, 'S32'), ('DEBUG_7', 0xDB07, 'S32')]
# what each encoder writes (the same file's crsfSensorEncode... functions); Cells writes a count and then that many bytes
RF_WIDTH = {'Nil': 0, 'U8': 1, 'S8': 1, 'U16': 2, 'S16': 2, 'U24': 3, 'S24': 3, 'U32': 4, 'S32': 4, 'CellVolt': 1, 'Control': 6, 'Attitude': 6, 'Accel': 6, 'LatLong': 8, 'AdjFunc': 6}
RF_SOURCE = '/Volumes/2TB SSD/ClaudeScratch/rf460/src/main/telemetry/crsf.c'   # the firmware's own file, when this Mac has it: the copy above must be it
rf_source_note = 'the copy of 13 Nov 2026 (the firmware file is not on this Mac now)'
if os.path.exists(RF_SOURCE):
    t_ = open(RF_SOURCE, encoding='utf-8', errors='replace').read()
    a_ = t_.index('static telemetrySensor_t crsfCustomTelemetrySensors[]'); b_ = t_.index('};', a_)
    rows_ = [(n, int(i, 16), e) for n, i, e in re.findall(r'TLM_SENSOR\((\w+),\s*(0x[0-9A-Fa-f]+),\s*\d+,\s*\d+,\s*\d+,\s*(\w+)\)', t_[a_:b_])]
    if rows_ != RF_TABLE: print('FAIL the table here is not the one in', RF_SOURCE); sys.exit(1)
    rf_source_note = 'checked against the firmware file itself just now'
def custom(sensors, origin=0xC8):   # [destination][origin][frame number], then [id][value] ...
    payload = [0xEA, origin, 7]
    for sid, data in sensors: payload += list(be(sid, 2)) + list(data)
    return frame(0xC8, 0x88, payload)
custom1 = custom([(0x1011, be(2512, 2)), (0x1012, be(1234, 2)), (0x1013, be(987, 2)), (0x1014, [66]), (0x10C0, be(2150, 2)), (0x10A0, [58]), (0x1205, [4]), (0x1203, be(0x00010002, 4))])
custom_unknown = custom([(0x10C0, be(1111, 2)), (0x1FFF, [1, 2, 3]), (0x1011, be(999, 2))])
custom_cut = custom([(0x10C0, be(1300, 2)), (0x1203, [1, 2])])
custom_notfc = custom([(0x10C0, be(4444, 2))], origin=0xEC)
custom_cells_bad = custom([(0x102F, [17] + [1] * 17), (0x10C0, be(4321, 2))])
custom_esc1 = custom([(0x1047, [71])])
every, every_len, every_mark = [], [], []
for k, (name, sid, enc) in enumerate(RF_TABLE):
    filler = [3, 10, 20, 30] if enc == 'Cells' else [0xA5] * RF_WIDTH[enc]
    f = custom([(sid, filler), (0x10C0, be(1000 + k, 2))])      # the head speed AFTER it is read right only if its width is right
    every += list(f); every_len.append(len(f)); every_mark.append(1000 + k)
temp2 = frame(0xC8, 0x0D, [0] + list(be(415, 2)) + list(be(623, 2)))
def info(origin, name, start=0xC8, ended=True): return frame(start, 0x29, [0xEA, origin] + list(name) + ([0] if ended else []) + [0] * 12 + [0, 1])
info_fc = info(0xC8, b'Rotorflight 4.6.0'); info_fc_old = info(0xC8, b'Rotorflight 4.5.2'); info_fc_bare = info(0xC8, b'Rotorflight')
info_bf = info(0xC8, b'Betaflight 4.5.1'); info_rx = info(0xEC, b'RP4TD-M', start=0xEA); info_mod = info(0xEE, b'RM Ranger Nano', start=0xEA)
info_long = frame(0xC8, 0x29, [0xEA, 0xC8] + list(b'A' * 40)); info_odd = info(0xEC, bytes([0x52, 0x01, 0xFF, 0x58])); info_other = info(0x10, b'Somebody')
ping = bytes([0xEE, 4, 0x28, 0x00, 0xEA, crc8([0x28, 0x00, 0xEA])])
if ping[-1] != 0x54: print('FAIL the ping is not the one every CRSF handset sends (its CRC is 0x54)'); sys.exit(1)

def carr(b): return '{' + ','.join(str(x) for x in b) + '}'
# ---- THE MODULE'S OWN SETTINGS, as ExpressLRS 3.6.4 sends them (lib/LUA/lua.cpp sendCRSFparam and the ...StructToArray
# functions; the list is tx_devLUA.cpp's for a 2.4 GHz module under the EU's rules): each parameter's data built as that
# code builds it, and cut into the chunks its frame holds at 250 packets a second (64 bytes, less 6 of frame and 2 of
# chunk header = 56 - CRSFHandset.cpp adjustMaxPacketSize)
CHUNK = 56
def p_choice(opts, value, units=b' '): return opts + b'\0' + bytes([value, 0, opts.count(b';'), 0]) + units + b'\0'
def p_u8(value, lo, hi, units=b' '): return bytes([value, lo, hi, 0]) + units + b'\0'
def p_text(text): return text + b'\0'
def p_cmd(step=0, info=b' '): return bytes([step, 200]) + info + b'\0'
AUXUD = b';'.join(b'AUX%d' % k + a for k in range(1, 11) for a in (b'\xc0', b'\xc1'))     # (its arrow symbols: not printable here)
RATES = b'50Hz(-115dBm);100Hz Full(-112dBm);150Hz(-112dBm);250Hz(-108dBm);333Hz Full(-105dBm);500Hz(-105dBm);D250(-104dBm);D500(-104dBm);F500(-104dBm);F1000(-104dBm)'   # all ten (a faster line than ours offers them all): 155 characters, more than one line of the log holds
PARAMS = [  # name, parent, kind, hidden, the data after the name (for a folder: its parameters' numbers and FF)
    (b'Packet Rate', 0, 9, False, p_choice(RATES, 3)),
    (b'Telem Ratio', 0, 9, False, p_choice(b'Std;Off;;1:64;1:32;1:16;1:8;1:4;1:2;Race', 0, b' (1:64)')),   # (1:128 not offered: an EMPTY place - what is written to the module is the place, not the rank on the wheel)
    (b'Switch Mode', 0, 9, False, p_choice(b'Wide;Hybrid', 0)),
    (b'Link Mode', 0, 9, False, p_choice(b'Normal;MAVLink', 0)),
    (b'Model Match', 0, 9, False, p_choice(b'Off;On', 0, b' (ID: 0)')),
    (b'TX Power (50 Dynamic)', 0, 11, False, bytes([7, 8, 9, 10, 0xFF])),
    (b'Max Power', 6, 9, False, p_choice(b'10;25;50;100', 2, b'mW')),
    (b'Dynamic', 6, 9, False, p_choice(b'Off;Dyn;AUX9;AUX10;AUX11;AUX12', 1)),
    (b'Fan Thresh', 6, 9, False, p_choice(b'10mW;25mW;50mW;100mW;250mW;500mW;1000mW;2000mW;Never', 4)),
    (b'100mW 2G4 CE LIMIT', 6, 12, False, p_text(b' ')),
    (b'VTX Administrator', 0, 11, False, bytes([12, 13, 14, 15, 16, 0xFF])),
    (b'Band', 11, 9, False, p_choice(b'Off;A;B;E;F;R;L', 0)),
    (b'Channel', 11, 0, False, p_u8(1, 1, 8)),
    (b'Pwr Lvl', 11, 9, False, p_choice(b'-;1;2;3;4;5;6;7;8', 0)),
    (b'Pitmode', 11, 9, True, p_choice(b'Off;On;' + AUXUD, 0)),
    (b'Send VTx', 11, 13, False, p_cmd()),
    (b'WiFi Connectivity', 0, 11, False, bytes([18, 19, 0xFF])),
    (b'Enable WiFi', 17, 13, False, p_cmd()),
    (b'Enable Rx WiFi', 17, 13, False, p_cmd()),
    (b'BLE Joystick', 0, 13, False, p_cmd()),
    (b'Bind', 0, 13, False, p_cmd()),
    (b'Bad/Good', 0, 12, False, p_text(b'0/250')),
    (b'3.6.4 CE_2400', 0, 12, False, p_text(b'abc123')),
]
def p_data(name, parent, kind, hidden, body): return bytes([parent, kind | (0x80 if hidden else 0)]) + name + b'\0' + body
def p_chunks(number, data):
    n = (len(data) + CHUNK - 1) // CHUNK
    return [frame(0xEA, 0x2B, [0xEA, 0xEE, number, n - 1 - c] + list(data[c * CHUNK:(c + 1) * CHUNK])) for c in range(n)]
PDATA = [p_data(*q) for q in PARAMS]
PCH = [p_chunks(k + 1, d) for k, d in enumerate(PDATA)]
if max(len(d) for d in PDATA) > 255 or max(len(f) for c in PCH for f in c) > 64: print('FAIL the test\'s own list is not one the module could send'); sys.exit(1)
if len(PCH[0]) != 4 or len(RATES) <= 150 or [len(c) for c in PCH].count(1) < 15: print('FAIL the test\'s own list should have the packet rates in four chunks and longer than a log line, and most settings in one chunk'); sys.exit(1)
def printable(b): return ''.join(chr(x) if 0x20 <= x <= 0x7E else '?' for x in b)
def cstr(t): return '"' + t.replace('\\', '\\\\').replace('"', '\\"') + '"'
def p_want(q):   # what the transmitter should have of it: by this file's own reading of the same data
    name, parent, kind, hidden, body = q
    text = units = ''; value = lo = hi = 0
    if kind == 9:
        opts, rest = body.split(b'\0', 1); text = printable(opts); value, lo, hi = rest[0], rest[1], rest[2]; units = printable(rest[4:].split(b'\0')[0])
    elif kind == 0: value, lo, hi = body[0], body[1], body[2]; units = printable(body[4:].split(b'\0')[0])
    elif kind == 12: text = printable(body.split(b'\0')[0])
    elif kind == 13: value, lo = body[0], body[1]; text = printable(body[2:].split(b'\0')[0])
    return '{%s, %s, %s, %d, %d, %d, %d, %d, %s}' % (cstr(printable(name)), cstr(text), cstr(units), kind, parent, value, lo, hi, 'true' if hidden else 'false')
PWANT = '{' + ', '.join(p_want(q) for q in PARAMS) + '}'
PCH_C = '{' + ', '.join('{' + ', '.join(carr(f) for f in c) + '}' for c in PCH) + '}'
info_mod_n = frame(0xEA, 0x29, [0xEA, 0xEE] + list(b'RM Ranger Nano') + [0] + list(b'ELRS') + [0] * 8 + [len(PARAMS), 0])
info_mod_short = frame(0xEA, 0x29, [0xEA, 0xEE] + list(b'RM Ranger Nano') + [0] + list(b'ELRS') + [0] * 8)      # ends before the count
info_mod_bare = frame(0xEA, 0x29, [0xEA, 0xEE] + list(b'RM Ranger Nano'))                                         # ends inside its name
read_1_0 = bytes([0xEE, 6, 0x2C, 0xEE, 0xEA, 1, 0, crc8([0x2C, 0xEE, 0xEA, 1, 0])])
long_opts = b';'.join(b'Choice%02d' % k for k in range(30))                                                       # 269 bytes: more than the room here
long_data = p_data(b'Long One', 0, 9, False, p_choice(long_opts[:230], 7, b'x'))
timing_ok = frame(0xEA, 0x3A, [0xEA, 0xEE, 0x10] + list(be(40000, 4)) + list(be(0, 4)))                          # 4 ms, in step
write_2_6 = bytes([0xEE, 6, 0x2D, 0xEE, 0xEA, 2, 6, crc8([0x2D, 0xEE, 0xEA, 2, 6])])
# for the play's module, which takes changes as ExpressLRS 3.6.4 does (tx_devLUA.cpp): each setting's data whole (it cuts
# the pieces itself), where a choice's value stands in it, which packet rates are "Full" ones, and the switch modes of each family
PDATA_C = '{' + ', '.join(carr(d) for d in PDATA) + '}'
PVAL_AT = '{' + ', '.join(str(len(q[0]) + 3 + q[4].index(b'\0') + 1) if q[2] == 9 else '-1' for q in PARAMS) + '}'
RATE_FULL = '{' + ', '.join('1' if b'Full' in o else '0' for o in RATES.split(b';')) + '}'
P3_STD = carr(p_data(b'Switch Mode', 0, 9, False, p_choice(b'Wide;Hybrid', 0)))
P3_FULL = carr(p_data(b'Switch Mode', 0, 9, False, p_choice(b'8ch;16ch Rate/2;12ch Mixed', 0)))
for q, d in zip(PARAMS, PDATA):
    if q[2] == 9:
        at = len(q[0]) + 3 + q[4].index(b'\0') + 1
        assert d[at] == q[4][q[4].index(b'\0') + 1] and d[at + 1] == 0 and d[at + 2] == q[4].split(b'\0')[0].count(b';'), 'the value\'s place in the test\'s own data'
def f32(x): return list(struct.pack('<f', x))
items_want = [[31, 2, 0, 0, 0], [5] + f32(25.12), [20] + list((2150).to_bytes(4, 'little')), [21] + f32(12.34), [22] + f32(987.0), [24] + f32(62.3)]
item_half = [5] + f32(12.56)

PROG = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <vector>
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
''' + BLOCK + r'''
using namespace ElrsCrsf;
static void feedAll(Parser &p, Telemetry &t, const uint8_t *b, unsigned n, uint32_t now) { for (unsigned i = 0; i < n; ++i) p.feed(b[i], t, now); }

// ---- THE MODULE, AS ITS OWN CODE HAS IT (ExpressLRS 3.6.4, src/lib/Handset/CRSFHandset.cpp: JustSentRFpacket() and
// sendSyncPacketToTX(), copied line for line with its names shortened), so the Pacer is tried against the real rule and
// not against what we think the rule is. Time is in microseconds.
struct Module {
    int64_t interval, lastRecv = 0;      // RequestedRCpacketInterval, dataLastRecv
    int32_t off = 0, window = 0, windowSize;   // OpenTXsyncOffset, OpenTXsyncWindow, OpenTXsyncWindowSize
    int64_t syncLastSentMs = -1000;      // OpenTXsyncLastSent
    long missed = 0, reports = 0;
    explicit Module(int64_t iv) : interval(iv), windowSize((int32_t)((20000 / iv) < 1 ? 1 : (20000 / iv))) {}
    void justSentRF(int64_t nowUs) {
        const int64_t delta = nowUs - lastRecv;
        if (delta >= interval) { off = -(int32_t)(delta % interval) * 10; window = 0; syncLastSentMs -= 200; ++missed; }   // "missing/late packet, force resync"
        else { window = (window + 1 < windowSize) ? window + 1 : windowSize; off = (int32_t)((((int64_t)off * (window - 1)) + delta * 10) / window); }
    }
    bool syncDue(int64_t nowUs) const { return nowUs / 1000 - syncLastSentMs >= 200; }      // OpenTXsyncPacketInterval
    int32_t sync(int64_t nowUs) { syncLastSentMs = nowUs / 1000; ++reports; return off - 1000; }   // OpenTXsyncOffsetSafeMargin
};
struct SimOut { long missedLate = 0, reportsLast5s = 0, sentLast10s = 0, corrections = 0; double minPeriod = 1e9, maxPeriod = 0, meanDelta = 0, minDelta = 1e9; };
static uint32_t rngState = 1;
static double rnd() { rngState = rngState * 1664525u + 1013904223u; return (double)(rngState >> 8) / 16777216.0; }
// Our timer and the module's radio, each on its own crystal (ppm), for some seconds. paced: the Pacer sets the period
// (taken up one tick late, as the Teensy's timer takes it); else every freeUs, as phase 1's loop() sent them. dropEvery:
// one frame in so many never arrives (two frames talking at once on the wire).
static SimOut simulate(int ivUs, double phaseUs, double ppmUs, double ppmModule, bool paced, double freeUs, int dropEvery, double seconds, uint32_t seed)
{
    rngState = seed;
    Module mod(ivUs); Pacer pacer; Telemetry tel; SimOut o;
    const double endUs = seconds * 1e6, warmUs = 3e6;
    double tRf = phaseUs, tTick = 0, cur = paced ? (double)DEFAULT_PERIOD_US : freeUs;
    double frameArrives = -1, reportAt = -1; int32_t reportOff = 0;
    long frames = 0, missedAtWarm = -1, reportsAt5 = -1, deltaN = 0; double deltaSum = 0;
    for (;;) {
        double t = tRf; int what = 0;
        if (tTick < t) { t = tTick; what = 1; }
        if (frameArrives >= 0 && frameArrives < t) { t = frameArrives; what = 2; }
        if (reportAt >= 0 && reportAt < t) { t = reportAt; what = 3; }
        if (t > endUs) break;
        if (missedAtWarm < 0 && t >= warmUs) missedAtWarm = mod.missed;
        if (reportsAt5 < 0 && t >= endUs - 5e6) reportsAt5 = mod.reports;
        if (what == 0) {                       // the module sends a radio packet
            const int64_t delta = (int64_t)t - mod.lastRecv;
            mod.justSentRF((int64_t)t);
            if (t >= warmUs && delta < ivUs) { deltaSum += (double)delta; ++deltaN; if ((double)delta < o.minDelta) o.minDelta = (double)delta; }
            tRf += ivUs * (1 + ppmModule * 1e-6);
        } else if (what == 1) {                // our timer: a frame, and the period for the one after next
            const double running = cur;
            if (paced) cur = (double)pacer.nextPeriodUs();
            if (t >= 1e6) { if (running < o.minPeriod) o.minPeriod = running; if (running > o.maxPeriod) o.maxPeriod = running; }   // (in the first second we send at 250 whatever its rate, until it says)
            ++frames; if (t >= endUs - 10e6) ++o.sentLast10s;
            if (!(dropEvery && frames % dropEvery == 0)) frameArrives = t + 650 + 40 + 60 * rnd();   // 26 bytes at 400000 baud, then the module's own loop
            tTick += running * (1 + ppmUs * 1e-6);
        } else if (what == 2) {                // our frame has reached the module: its chance to answer
            mod.lastRecv = (int64_t)t; frameArrives = -1;
            if (reportAt < 0 && mod.syncDue((int64_t)t)) { reportOff = mod.sync((int64_t)t); reportAt = t + 500 + 4500 * rnd(); }   // its answer on the wire, and loop() getting round to it
        } else {                               // loop() reads the timing frame
            tel.intervalTenthsUs = ivUs * 10; tel.offsetTenthsUs = reportOff; ++tel.timingFrames; tel.timingMs = (uint32_t)(t / 1000) + 1;
            if (paced) pacer.onTiming(tel, (uint32_t)(t / 1000));
            reportAt = -1;
        }
    }
    o.missedLate = mod.missed - (missedAtWarm < 0 ? 0 : missedAtWarm);
    o.reportsLast5s = mod.reports - (reportsAt5 < 0 ? 0 : reportsAt5);
    o.corrections = (long)pacer.corrections;
    o.meanDelta = deltaN ? deltaSum / (double)deltaN : -1;
    return o;
}
int main() {
    // the CRC: CRC-8/DVB-S2's published check value, "123456789" -> 0xBC
    CHECK(crc8((const uint8_t *)"123456789", 9) == 0xBC);
    // the conversion: the receiver's own figures
    CHECK(usToTicks(1500) == 992); CHECK(usToTicks(1000) == 173); CHECK(usToTicks(2000) == 1811);
    CHECK(usToTicks(500) == 172); CHECK(usToTicks(2500) == 1811); CHECK(usToTicks(988) == 172); CHECK(usToTicks(0) == 172);
    // channel frames: byte for byte as the Python packer has them
    static const uint16_t cases[][16] = {''' + ','.join(carr(c) for c in cases) + r'''};
    static const uint8_t want[][26] = {''' + ','.join(carr(rc_frame(c)) for c in cases) + r'''};
    int same = 0;
    for (unsigned k = 0; k < sizeof(cases) / sizeof(cases[0]); ++k) {
        uint8_t f[RC_FRAME_LEN]; buildRcFrame(cases[k], f);
        if (!memcmp(f, want[k], RC_FRAME_LEN)) ++same;
    }
    CHECK(same == (int)(sizeof(cases) / sizeof(cases[0])));
    printf("PASS %d channel frames byte for byte as an independent packer builds them\n", same);
    // the module's frames, built in Python
    static const uint8_t linkElrs[] = ''' + carr(link_elrs) + r''';
    static const uint8_t link[] = ''' + carr(link) + r''', batt[] = ''' + carr(batt) + r''', rpm[] = ''' + carr(rpm) + r''', rpmneg[] = ''' + carr(rpm_neg) + r''',
        temp[] = ''' + carr(temp) + r''', mode[] = ''' + carr(mode) + r''', longmode[] = ''' + carr(longmode) + r''', att[] = ''' + carr(att) + r''',
        timing[] = ''' + carr(timing) + r''', timingBadSub[] = ''' + carr(timing_bad_sub) + r''', timingSilly[] = ''' + carr(timing_silly) + r''',
        unknown[] = ''' + carr(unknown) + r''', bad[] = ''' + carr(bad) + r''';
    {   Parser p; Telemetry t;
        feedAll(p, t, link, sizeof link, 1000);
        CHECK(t.framesOk == 1 && t.linkMs == 1000);
        CHECK(t.upRssi1 == -45 && t.upRssi2 == -52 && t.upLq == 98 && t.upSnr == 9 && t.antenna == 1 && t.rfMode == 7 && t.txPower == 3);
        CHECK(t.downRssi == -61 && t.downLq == 100 && t.downSnr == 7);
        printf("PASS link statistics: LQ 98%%, RSSI -45/-52 dBm, power code 3 (100 mW), down -61 dBm 100%%\n"); }
    {   Parser p; Telemetry t;
        feedAll(p, t, linkElrs, sizeof linkElrs, 2000);
        CHECK(t.framesOk == 1 && t.linkMs == 2000);
        CHECK(t.upRssi1 == -50 && t.upRssi2 == -47 && t.upLq == 92 && t.txPower == 8 && t.downRssi == -53);
        CHECK(rssiDbm(0) == 0 && rssiDbm(1) == -1 && rssiDbm(127) == -127 && rssiDbm(128) == -128 && rssiDbm(255) == -1);
        printf("PASS link statistics the way ExpressLRS sends them (signed bytes): RSSI -50/-47 dBm, down -53 dBm, power code 8 (50 mW)\n"); }
    {   Parser p; Telemetry t;
        feedAll(p, t, batt, sizeof batt, 5); feedAll(p, t, rpm, sizeof rpm, 6); feedAll(p, t, temp, sizeof temp, 7);
        feedAll(p, t, mode, sizeof mode, 8); feedAll(p, t, att, sizeof att, 9);
        CHECK(t.battDeciVolts == 81 && t.battDeciAmps == 123 && t.battMah == 1350 && t.battPct == 77 && t.battMs == 5);
        CHECK(t.rpm == 1850 && t.rpmMs == 6);
        CHECK(t.tempDeciC == -123 && t.tempMs == 7);
        CHECK(!strcmp(t.flightMode, "ANGLE"));
        CHECK(t.pitch == -100 && t.roll == 200 && t.yaw == -300);
        CHECK(t.framesOk == 5 && t.badCrc == 0);
        feedAll(p, t, rpmneg, sizeof rpmneg, 10); CHECK(t.rpm == -1234);
        feedAll(p, t, longmode, sizeof longmode, 11); CHECK(strlen(t.flightMode) == 15 && !strncmp(t.flightMode, "A_VERY_LONG_FLI", 15));
        printf("PASS battery 8.1 V 12.3 A 1350 mAh 77%%, rpm 1850 (and -1234), -12.3 C, ANGLE, attitude, a long mode name cut to 15\n"); }
    {   Parser p; Telemetry t;
        feedAll(p, t, timing, sizeof timing, 2000);
        CHECK(t.intervalTenthsUs == 40000 && t.offsetTenthsUs == -1234 && t.timingMs == 2000);
        CHECK(t.timingFrames == 1);
        Parser q; Telemetry v; feedAll(q, v, timingBadSub, sizeof timingBadSub, 3000);
        CHECK(v.timingMs == 0 && v.timingFrames == 0 && v.framesOk == 1);   // another subcommand: not our timing
        Parser r; Telemetry w; feedAll(r, w, timingSilly, sizeof timingSilly, 4000);
        CHECK(w.timingMs == 4000 && w.timingFrames == 1);
        Pacer silly; CHECK(!silly.onTiming(w, 4001) && silly.intervalUs == DEFAULT_PERIOD_US && silly.nextPeriodUs() == DEFAULT_PERIOD_US);   // 300 ms: not believed
        printf("PASS timing: 4 ms and -123.4 us read and counted; another subcommand is not timing; a silly interval is not believed\n"); }
    {   // THE PACER, piece by piece
        Pacer p; Telemetry t;
        CHECK(p.intervalUs == 4000 && p.nextPeriodUs() == 4000 && p.nextPeriodUs() == 4000);      // nothing said yet: 250 a second
        CHECK(!p.onTiming(t, 10));                                                                // no timing frame has come
        auto say = [&](int32_t ivTenths, int32_t offTenths) { t.intervalTenthsUs = ivTenths; t.offsetTenthsUs = offTenths; ++t.timingFrames; };
        say(40000, -1234); CHECK(p.onTiming(t, 1000) && p.corrections == 1);                       // 123 us late: sooner by 123, once
        CHECK(!p.onTiming(t, 1001));                                                               // the same frame is not used twice
        CHECK(p.nextPeriodUs() == 3877 && p.nextPeriodUs() == 4000 && p.nextPeriodUs() == 4000);
        say(40000, 5000); CHECK(!p.onTiming(t, 1030));                                             // inside the settling time (60 ms at 4 ms): left alone
        CHECK(p.nextPeriodUs() == 4000);
        say(40000, 25000); CHECK(p.onTiming(t, 1060));                                             // settled: 2.5 ms early = later by 2.5 ms, at once
        CHECK(p.nextPeriodUs() == 6500 && p.nextPeriodUs() == 4000);
        say(40000, -30000); CHECK(p.onTiming(t, 2000));                                            // 3 ms late: sooner, but an eighth at a time
        uint32_t total = 0; int shortOnes = 0; for (int k = 0; k < 10; ++k) { const uint32_t x = p.nextPeriodUs(); CHECK(x >= 3500 && x <= 4000); total += x; if (x < 4000) ++shortOnes; }
        CHECK(total == 10 * 4000 - 3000 && shortOnes == 6);
        say(40000, 90); CHECK(!p.onTiming(t, 3000) && p.nextPeriodUs() == 4000);                   // 9 us: close enough
        say(40000, -90); CHECK(!p.onTiming(t, 3001) && p.nextPeriodUs() == 4000);
        say(40000, 100); CHECK(p.onTiming(t, 3002) && p.nextPeriodUs() == 4010);                   // 10 us: acted on
        say(40000, 900000); CHECK(p.onTiming(t, 4000) && p.nextPeriodUs() == 8000 && p.nextPeriodUs() == 4000);   // never more than one interval
        say(40000, -900000); CHECK(p.onTiming(t, 5000)); total = 0; for (int k = 0; k < 12; ++k) total += p.nextPeriodUs(); CHECK(total == 12 * 4000 - 4000);
        say(20000, 7000); CHECK(p.onTiming(t, 6000) && p.intervalUs == 2000 && p.nextPeriodUs() == 2000);   // a new packet rate: its interval at once, its offset not yet
        say(20000, 7000); CHECK(!p.onTiming(t, 6039) && p.nextPeriodUs() == 2000);                 // (40 ms to settle at 2 ms)
        say(20000, 7000); CHECK(p.onTiming(t, 6040) && p.nextPeriodUs() == 2700 && p.nextPeriodUs() == 2000);
        const uint32_t late = 0xFFFFFFF0u;                                                         // millis() rolls over inside a settling time
        Pacer r; Telemetry u; u.intervalTenthsUs = 40000; u.offsetTenthsUs = 10000; ++u.timingFrames; CHECK(r.onTiming(u, late));
        u.offsetTenthsUs = 10000; ++u.timingFrames; CHECK(!r.onTiming(u, late + 59)); ++u.timingFrames; CHECK(r.onTiming(u, late + 60));
        CHECK(settleMs(4000) == 60 && settleMs(2000) == 40 && settleMs(20000) == 220);
        printf("PASS the pacer: sooner an eighth at a time, later at once, never more than an interval, each frame once, a settling time, a new rate\n"); }
    {   // never stale: the timer sends only while loop() keeps copying the finished channels
        CHECK(!sticksFresh(0, 0) && !sticksFresh(0, 50) && !sticksFresh(0, 0xFFFFFFFFu));          // never copied: never
        CHECK(sticksFresh(1000, 1000) && sticksFresh(1000, 1000 + STICKS_STALE_MS - 1));
        CHECK(!sticksFresh(1000, 1000 + STICKS_STALE_MS) && !sticksFresh(1000, 60000));
        const uint32_t late = 0xFFFFFFC0u;                                                         // across millis()'s roll-over
        CHECK(sticksFresh(late, late + 99) && !sticksFresh(late, late + 100));
        CHECK(STICKS_STALE_MS >= 20 && STICKS_STALE_MS <= 250);
        printf("PASS never stale: no copy from loop() for %u ms and the timer says nothing (the receiver's failsafe acts)\n", (unsigned)STICKS_STALE_MS); }
    {   // THE MODEL IS RIGHT: phase 1 as it ran on the yellow transmitter (12 Nov 2026: 1111-1113 frames in 5 s, and
        // 137-140 timing frames in 5 s in its log) - the module's own rule, copied above, gives the same figure
        const SimOut y = simulate(4000, 1234, 0, 0, false, 5e6 / 1112.0, 0, 20, 7);
        CHECK(y.reportsLast5s >= 133 && y.reportsLast5s <= 144);
        printf("PASS the model of the module: frames every %.0f us as phase 1 sent them -> %ld timing frames in 5 s (the yellow transmitter's log: 137 to 140)\n", 5e6 / 1112.0, y.reportsLast5s);
        // THE PACER AGAINST IT: every starting phase, crystals 40 ppm apart either way, four packet rates
        long worstMiss = 0, worstReports = 0; double lo = 1e9, hi = 0, dLo = 1e9, dLo250 = 1e9, pMin = 1e9, pMax = 0; int runs = 0;
        static const int rates[] = {4000, 2000, 10000, 20000};
        for (int iv : rates) for (int ph = 0; ph < 8; ++ph) for (int pp = -1; pp <= 1; ++pp) {
            const SimOut o = simulate(iv, iv * ph / 8.0 + 3, 20.0 * pp, -20.0 * pp, true, 0, 0, 30, 100u + (uint32_t)(ph * 7 + pp + iv));
            ++runs; if (o.missedLate > worstMiss) worstMiss = o.missedLate;
            const long want = 10000000 / iv;                                      // frames in the last 10 s
            CHECK(o.sentLast10s >= want - 1 && o.sentLast10s <= want + 1);
            if (iv == 4000) { if (o.reportsLast5s > worstReports) worstReports = o.reportsLast5s; if (o.minPeriod < pMin) pMin = o.minPeriod; if (o.maxPeriod > pMax) pMax = o.maxPeriod; }
            if (o.meanDelta < lo) lo = o.meanDelta; if (o.meanDelta > hi) hi = o.meanDelta;
            if (o.minDelta < dLo) dLo = o.minDelta;
            if (iv == 4000 && o.minDelta < dLo250) dLo250 = o.minDelta;
            CHECK(o.minPeriod >= iv - iv / 8 && o.maxPeriod <= 2 * iv);          // never sooner than seven eighths, never later than two
        }
        CHECK(worstMiss == 0);                                                    // after the first 3 s not ONE packet goes out without a fresh frame
        CHECK(worstReports >= 24 && worstReports <= 26);                          // and the module asks 5 times a second, no more
        CHECK(lo >= 80 && hi <= 120 && dLo250 >= 30 && dLo > 0);                  // about 100 us before each packet, as it asks; with 60 us of jitter put in, at 250 a second never under 30 (at 50 a second its figure is one packet's, and noisier)
        printf("PASS the pacer against the module's own rule: %d runs (4 rates, 8 phases, crystals 40 ppm apart): no packet without a fresh frame, %ld timing frames in 5 s, frames %.0f to %.0f us before the packet on average (at 250 a second never under %.0f, at any rate never under %.0f), periods %.0f to %.0f us\n",
               runs, worstReports, lo, hi, dLo250, dLo, pMin, pMax);
        // a frame lost on the wire now and then (one in 250): that packet is lost, and the pacer's answer loses no other
        const SimOut d = simulate(4000, 777, 15, -15, true, 0, 250, 60, 99);
        CHECK(d.missedLate >= 55 && d.missedLate <= 59);                          // the 57 that were dropped after the first 3 s, and no more
        CHECK(d.sentLast10s >= 2499 && d.sentLast10s <= 2501 && d.minPeriod >= 3500);
        printf("PASS a frame lost on the wire each second: %ld packets without a fresh frame in 57 s - the lost ones, and none of the pacer's making\n", d.missedLate); }
    {   Parser p; Telemetry t;
        // noise, a frame cut in two, a bad CRC, an impossible length, then a good frame - one byte at a time
        static const uint8_t noise[] = {0x00, 0xFF, 0x13, 0x37};
        feedAll(p, t, noise, sizeof noise, 1);
        feedAll(p, t, link, 7, 2); feedAll(p, t, link + 7, sizeof link - 7, 3);
        CHECK(t.framesOk == 1 && t.linkMs == 3);
        feedAll(p, t, bad, sizeof bad, 4);
        CHECK(t.badCrc == 1 && t.framesOk == 1 && t.linkMs == 3);
        static const uint8_t badLen[] = {0xC8, 63};
        feedAll(p, t, badLen, sizeof badLen, 5); CHECK(t.badLength == 1);
        static const uint8_t badLen2[] = {0xC8, 1};
        feedAll(p, t, badLen2, sizeof badLen2, 5); CHECK(t.badLength == 2);
        feedAll(p, t, unknown, sizeof unknown, 6); CHECK(t.framesOk == 2 && t.unknownType == 1);
        feedAll(p, t, batt, sizeof batt, 7); CHECK(t.framesOk == 3 && t.battMs == 7);
        // a start byte where a length should be (a frame cut off after its first byte): it begins the NEXT frame, which is not lost
        static const uint8_t lone[] = {0xC8};
        feedAll(p, t, lone, 1, 8); feedAll(p, t, link, sizeof link, 9); CHECK(t.badLength == 3 && t.framesOk == 4 && t.linkMs == 9);
        static const uint8_t lone2[] = {0xEA, 0xEE, 0xEC};          // three in a row, then a good frame
        feedAll(p, t, lone2, 3, 10); feedAll(p, t, batt, sizeof batt, 11); CHECK(t.badLength == 6 && t.framesOk == 5 && t.battMs == 11);
        printf("PASS a stream: noise skipped, a frame in two pieces, a bad CRC and impossible lengths refused, frames after them read\n"); }
    {   // our own frames, read back by the same parser (as the module's would read them: start 0xEE, the CRC)
        Parser p; Telemetry t; uint8_t f[RC_FRAME_LEN]; const uint16_t us[16] = {1500,1500,1500,1500,1000,2000,1500,1500,1500,1500,1500,1500,1500,1500,1500,1500};
        buildRcFrame(us, f); feedAll(p, t, f, sizeof f, 1);
        CHECK(t.ownEcho == 1 && t.badCrc == 0 && t.badLength == 0);     // whole and good ...
        CHECK(t.framesOk == 0 && t.unknownType == 0 && t.linkMs == 0);  // ... and NOT counted as the module's: it is our own, heard back on the one wire
        // echoes and the module's frames mixed, as on a wire that echoes: each counted in its own place, nothing lost
        feedAll(p, t, link, sizeof link, 50); feedAll(p, t, f, sizeof f, 51); feedAll(p, t, timing, sizeof timing, 52); feedAll(p, t, f, sizeof f, 53);
        CHECK(t.ownEcho == 3 && t.framesOk == 2 && t.linkMs == 50 && t.timingMs == 52 && t.badCrc == 0);
        // a frame of the module's that only LOOKS like ours in its payload is still the module's (the first byte decides)
        static const uint8_t fromModule[] = ''' + carr(frame(0xC8, 0x16, list(range(22)))) + r''';
        feedAll(p, t, fromModule, sizeof fromModule, 54); CHECK(t.ownEcho == 3 && t.framesOk == 3 && t.unknownType == 1);
        // the driver's two lines for it: the log names the echo, and the port has room
        printf("PASS our channel frame is a whole, good CRSF frame, and heard back it is counted as our own echo, never as the module's\n"); }
    {   // the module's power switch (pin 10): the serial line waits until the module has had power for a moment
        CHECK(POWER_PIN == 10 && POWER_SETTLE_MS >= 100 && POWER_SETTLE_MS <= 1000);
        CHECK(!lineMayStart(false, 0, 0) && !lineMayStart(false, 0, 100000));              // no power: never
        CHECK(!lineMayStart(true, 5000, 5000) && !lineMayStart(true, 5000, 5000 + POWER_SETTLE_MS - 1));
        CHECK(lineMayStart(true, 5000, 5000 + POWER_SETTLE_MS) && lineMayStart(true, 5000, 9000));
        const uint32_t late = 0xFFFFFF00u;                                                  // across millis()'s roll-over
        CHECK(!lineMayStart(true, late, late + POWER_SETTLE_MS - 1) && lineMayStart(true, late, late + POWER_SETTLE_MS));
        printf("PASS the power switch: no line without power, none in the first %u ms, right across the clock's roll-over\n", (unsigned)POWER_SETTLE_MS); }
    // ================================================================= PHASE 2, STEP 2 =================================
    static const uint8_t temp2[] = ''' + carr(temp2) + r''', custom1[] = ''' + carr(custom1) + r''', customUnknown[] = ''' + carr(custom_unknown) + r''',
        customCut[] = ''' + carr(custom_cut) + r''', customNotFc[] = ''' + carr(custom_notfc) + r''', customCellsBad[] = ''' + carr(custom_cells_bad) + r''',
        customEsc1[] = ''' + carr(custom_esc1) + r''', infoFc[] = ''' + carr(info_fc) + r''', infoFcOld[] = ''' + carr(info_fc_old) + r''',
        infoFcBare[] = ''' + carr(info_fc_bare) + r''', infoBf[] = ''' + carr(info_bf) + r''', infoRx[] = ''' + carr(info_rx) + r''', infoMod[] = ''' + carr(info_mod) + r''',
        infoLong[] = ''' + carr(info_long) + r''', infoOdd[] = ''' + carr(info_odd) + r''', infoOther[] = ''' + carr(info_other) + r''';
    {   // the model's telemetry in one set of units, whichever frame brought it, and which of it is new
        Parser p; Telemetry t;
        CHECK(t.fresh == 0 && !t.rotorflight);
        feedAll(p, t, batt, sizeof batt, 5);
        CHECK(t.voltsCenti == 810 && t.ampsCenti == 1230 && t.mah == 1350 && t.pct == 77 && t.nBattery == 1);
        CHECK(t.fresh == (F_VOLTS | F_AMPS | F_MAH));
        feedAll(p, t, rpm, sizeof rpm, 6);                    // two values: the head's, then the tail's
        CHECK(t.headRpm == 1850 && t.tailRpm == -5 && t.rpm == 1850 && (t.fresh & F_RPM) && t.nRpm == 1 && t.rpmMs == 6);
        feedAll(p, t, temp, sizeof temp, 7);                  // one value: "the" temperature
        CHECK(t.escTempDeciC == -123 && (t.fresh & F_ESC_TEMP) && t.nTemp == 1);
        feedAll(p, t, temp2, sizeof temp2, 8);                // two: Rotorflight's processor, then its speed controller
        CHECK(t.mcuTempDeciC == 415 && t.escTempDeciC == 623 && t.tempDeciC == 415 && t.nTemp == 2);
        feedAll(p, t, mode, sizeof mode, 9); feedAll(p, t, att, sizeof att, 10);
        CHECK(t.nMode == 1 && t.nAttitude == 1 && !t.rotorflight && t.unknownType == 0 && t.badCrc == 0);
        // a battery frame whose volts would not fit the common unit is held at its top, never wrapped round
        static const uint8_t big[] = ''' + carr(frame(0xC8, 0x08, list(be(60000, 2) + be(60000, 2) + be(5, 3)) + [1])) + r''';
        feedAll(p, t, big, sizeof big, 11); CHECK(t.voltsCenti == 65530 && t.ampsCenti == 65530);
        printf("PASS the standard frames into one set of units: 8.10 V 12.30 A 1350 mAh, head 1850 and tail -5 rpm, one temperature or Rotorflight's two (41.5 and 62.3 C), each marked new\n"); }
    {   // ROTORFLIGHT'S OWN TELEMETRY (0x88)
        Parser p; Telemetry t;
        feedAll(p, t, custom1, sizeof custom1, 100);
        CHECK(t.customFrames == 1 && t.customSensors == 8 && t.customUnknown == 0 && t.unknownType == 0 && t.framesOk == 1);
        CHECK(t.voltsCenti == 2512 && t.ampsCenti == 1234 && t.mah == 987 && t.pct == 66 && t.headRpm == 2150 && t.escTempDeciC == 580);
        CHECK(t.govState == 4 && t.armDisable == 0x00010002u && t.rotorflight);
        CHECK(t.fresh == (F_VOLTS | F_AMPS | F_MAH | F_RPM | F_ESC_TEMP | F_KIND) && t.battMs == 100 && t.rpmMs == 100);
        feedAll(p, t, customUnknown, sizeof customUnknown, 101);        // an id that is not in its table: what came before is taken, the rest left
        CHECK(t.headRpm == 1111 && t.customUnknown == 1 && t.voltsCenti == 2512 && t.customSensors == 9);
        feedAll(p, t, customCut, sizeof customCut, 102);                // a value cut short by the frame's end
        CHECK(t.headRpm == 1300 && t.customUnknown == 2 && t.armDisable == 0x00010002u);
        feedAll(p, t, customCellsBad, sizeof customCellsBad, 103);      // seventeen cells: not believed, and nothing after it read
        CHECK(t.customUnknown == 3 && t.headRpm == 1300);
        feedAll(p, t, customEsc1, sizeof customEsc1, 104); CHECK(t.escTempDeciC == 710);   // (ESC 1's own temperature, where the combined one is not asked for)
        Parser q; Telemetry u; feedAll(q, u, customNotFc, sizeof customNotFc, 5);   // not from the flight controller: not read
        CHECK(u.customFrames == 0 && !u.rotorflight && u.headRpm == 0 && u.fresh == 0 && u.framesOk == 1);
        // EVERY entry of Rotorflight's table: a head speed AFTER it is read right only if its width here is right
        static const uint8_t every[] = ''' + carr(every) + r''';
        static const uint16_t everyLen[] = ''' + carr(every_len) + r''', everyMark[] = ''' + carr(every_mark) + r''';
        unsigned at = 0; int good = 0; const int N = (int)(sizeof(everyLen) / sizeof(everyLen[0]));
        for (int k = 0; k < N; ++k) {
            Parser r; Telemetry v; feedAll(r, v, every + at, everyLen[k], 1); at += everyLen[k];
            if (v.headRpm == everyMark[k] && v.customUnknown == 0 && v.customSensors == 2 && v.framesOk == 1 && v.rotorflight) ++good;
            else fprintf(stderr, "table entry %d is read wrongly\n", k);
        }
        CHECK(good == N && N == ''' + str(len(RF_TABLE)) + r''');
        CHECK(customWidth(0x1FFF, nullptr, 0) == -1 && customWidth(0x0011, nullptr, 0) == -1 && customWidth(0xDB08, nullptr, 0) == -1 && customWidth(0x102F, nullptr, 0) == -1);
        printf("PASS Rotorflight's own telemetry: 25.12 V 12.34 A 987 mAh 66%%, head 2150, ESC 58 C, governor 4; an unknown id, a cut value, 17 cells and another sender are left; all %d entries of its firmware's table read at the right width\n", N); }
    {   // "who is there?" and the answers
        uint8_t f[PING_LEN]; buildPing(f);
        static const uint8_t pingWant[] = ''' + carr(ping) + r''';
        CHECK(sizeof(pingWant) == PING_LEN && !memcmp(f, pingWant, PING_LEN));
        Parser pp; Telemetry tp; feedAll(pp, tp, f, sizeof f, 1); CHECK(tp.ownEcho == 1 && tp.badCrc == 0 && tp.framesOk == 0);   // (a whole frame; heard back, it is our own)
        Parser p; Telemetry t;
        feedAll(p, t, infoMod, sizeof infoMod, 1); feedAll(p, t, infoRx, sizeof infoRx, 2);
        CHECK(!strcmp(t.moduleName, "RM Ranger Nano") && !strcmp(t.rxName, "RP4TD-M") && !t.fcName[0] && !t.rotorflight && t.fresh == 0 && t.nInfo == 2);
        feedAll(p, t, infoFc, sizeof infoFc, 3);
        CHECK(!strcmp(t.fcName, "Rotorflight 4.6.0") && t.rotorflight && t.rfMajor == 4 && t.rfMinor == 6 && t.fresh == F_KIND && t.unknownType == 0);
        CHECK(rotorflightKind(t, 0) == 2 && rotorflightKind(t, 1) == 2);
        Telemetry o; Parser po; feedAll(po, o, infoFcOld, sizeof infoFcOld, 1);
        CHECK(o.rotorflight && o.rfMajor == 4 && o.rfMinor == 5 && rotorflightKind(o, 0) == 1 && rotorflightKind(o, 2) == 1);
        Telemetry b; Parser pb; feedAll(pb, b, infoFcBare, sizeof infoFcBare, 1);
        CHECK(b.rotorflight && b.rfMajor == 0 && b.rfMinor == 0 && rotorflightKind(b, 0) == 2 && rotorflightKind(b, 1) == 1 && rotorflightKind(b, 2) == 2 && rotorflightKind(b, 9) == 2);
        Telemetry bf; Parser pbf; feedAll(pbf, bf, infoBf, sizeof infoBf, 1);
        CHECK(!bf.rotorflight && bf.fresh == 0 && !strcmp(bf.fcName, "Betaflight 4.5.1"));
        Telemetry lg; Parser pl; feedAll(pl, lg, infoLong, sizeof infoLong, 1);
        CHECK(strlen(lg.fcName) == sizeof(lg.fcName) - 1 && lg.fcName[0] == 'A' && !lg.rotorflight);     // a name with no end: cut to the room
        Telemetry od; Parser pod; feedAll(pod, od, infoOdd, sizeof infoOdd, 1); CHECK(!strcmp(od.rxName, "R??X"));
        Telemetry ot; Parser pot; feedAll(pot, ot, infoOther, sizeof infoOther, 1); CHECK(!ot.fcName[0] && !ot.rxName[0] && !ot.moduleName[0] && ot.nInfo == 0);
        uint8_t a, c; CHECK(rotorflightName("Rotorflight 12.34.5", a, c) && a == 12 && c == 34); CHECK(!rotorflightName("rotorflight 4.6.0", a, c) && !rotorflightName("", a, c));
        CHECK(rotorflightName("Rotorflight 4.", a, c) && a == 0 && c == 0); CHECK(rotorflightName("Rotorflight 999999999.6", a, c) && a == 0 && c == 0);
        CHECK(PING_EVERY_MS >= 1000 && PING_TRIES >= 3 && PING_TRIES <= 20);
        printf("PASS who is there: the ping every handset sends (EE 04 28 00 EA 54); the module's, the receiver's and the flight controller's names; 'Rotorflight 4.6.0' is Rotorflight 2.3, '4.5.2' is 2.2, 'Betaflight' is not\n"); }
    {   // into the transmitter's own telemetry items, byte for byte as its code reads them
        Telemetry t; Item it[MAX_ITEMS];
        CHECK(takeItems(t, false, 0, it) == 0);
        t.voltsCenti = 2512; t.ampsCenti = 1234; t.mah = 987; t.headRpm = 2150; t.escTempDeciC = 623; t.rotorflight = true; t.rfMajor = 4; t.rfMinor = 6;
        t.fresh = F_VOLTS | F_AMPS | F_MAH | F_RPM | F_ESC_TEMP | F_KIND;
        static const uint8_t want[6][5] = {''' + ','.join(carr(x) for x in items_want) + r'''};
        uint8_t n = takeItems(t, false, 0, it);
        CHECK(n == 6 && t.fresh == 0);
        for (int k = 0; k < 6 && k < n; ++k) CHECK(it[k].id == want[k][0] && !memcmp(it[k].b, want[k] + 1, 4));
        CHECK(it[0].id == ITEM_ROTORFLIGHT);                    // "it is Rotorflight" FIRST: head speed, amps and mAh are taken only from a model known to be one
        CHECK(takeItems(t, false, 0, it) == 0);                 // each once
        static const uint8_t half[5] = ''' + carr(item_half) + r''';
        t.fresh = F_VOLTS; n = takeItems(t, true, 0, it);       // a 12-cell model: the transmitter doubles what it is told
        CHECK(n == 1 && it[0].id == ITEM_VOLTS && !memcmp(it[0].b, half + 1, 4));
        Telemetry u; u.fresh = F_KIND; CHECK(takeItems(u, false, 2, it) == 0);   // never "it is Rotorflight" from a model that has not said so
        CHECK(rpmForItem(-5) == 0 && rpmForItem(0) == 0 && rpmForItem(65534) == 65534 && rpmForItem(65535) == 65534 && rpmForItem(700000) == 65534);
        CHECK(ITEM_VOLTS == 5 && ITEM_RPM == 20 && ITEM_AMPS == 21 && ITEM_MAH == 22 && ITEM_ESC_TEMP == 24 && ITEM_ROTORFLIGHT == 31 && MAX_ITEMS >= 6);
        printf("PASS the transmitter's own items: Rotorflight first, then volts, head speed, amps, mAh, ESC temperature - the bytes its telemetry code reads; a 12-cell pack halved; each once\n"); }
    {   // CONNECTED, SILENT, GIVEN UP
        Telemetry t; CHECK(!linkHeard(t, 0) && !linkHeard(t, 5000));                       // never heard
        t.linkMs = 1000; CHECK(linkHeard(t, 1000) && linkHeard(t, 1000 + LINK_LOST_MS - 1) && !linkHeard(t, 1000 + LINK_LOST_MS));
        const uint32_t late = 0xFFFFFF00u; t.linkMs = late; CHECK(linkHeard(t, late + LINK_LOST_MS - 1) && !linkHeard(t, late + LINK_LOST_MS));
        CHECK(LINK_LOST_MS >= 1000 && LINK_LOST_MS <= 3000 && MOTOR_OFF_GRACE_MS >= 20000 && MODEL_SETTLE_MS >= 20 && MODEL_SETTLE_MS <= 250 && LINE_STALE_MS >= STICKS_STALE_MS);
        // the bench, the motor switch never on: heard = connected; silent = given up at once; heard again = connected again
        LinkState s; CHECK(s.step(false, false, 10) == 0 && !s.green && !s.silent);
        CHECK(s.step(true, false, 20) == 1 && s.green && !s.silent);
        CHECK(s.step(true, false, 30) == 0 && s.green);
        CHECK(s.step(false, false, 40) == -1 && !s.green && !s.silent);
        CHECK(s.step(false, false, 50) == 0 && !s.green);
        CHECK(s.step(true, false, 60) == 1 && s.green);
        // in the air: the motor running, nothing heard for ten minutes - silent, and NEVER given up
        CHECK(s.step(true, true, 1000) == 0);
        int given = 0, notSilent = 0;
        for (uint32_t ms = 2000; ms < 600000; ms += 500) { if (s.step(false, true, ms) != 0 || !s.green) ++given; if (!s.silent) ++notSilent; }
        CHECK(given == 0 && notSilent == 0);
        CHECK(s.step(true, true, 600000) == 0 && s.green && !s.silent);                     // heard again: no second "Connected"
        // an autorotation: the motor switched off, heard; then silent - not given up for half a minute, so the switch brings the motor back
        CHECK(s.step(true, false, 700000) == 0);
        CHECK(s.step(false, false, 705000) == 0 && s.green && s.silent);
        CHECK(s.step(false, false, 700000 + MOTOR_OFF_GRACE_MS - 1) == 0 && s.green);
        CHECK(s.step(false, true, 700000 + MOTOR_OFF_GRACE_MS - 1) == 0 && s.green);        // the bail-out: the motor again, still connected
        CHECK(s.step(false, true, 900000) == 0 && s.green);
        // landed, the motor off, still silent: given up half a minute after the switch went off, not before
        CHECK(s.step(false, false, 1000000) == 0 && s.green);
        CHECK(s.step(false, false, 1000000 + MOTOR_OFF_GRACE_MS - 1) == 0 && s.green);
        CHECK(s.step(false, false, 1000000 + MOTOR_OFF_GRACE_MS) == -1 && !s.green && !s.silent);
        // on the bench after that flight (the motor off since long): at once again
        CHECK(s.step(true, false, 2000000) == 1 && s.step(false, false, 2000100) == -1);
        // the clock's roll-over inside the half minute
        LinkState r; CHECK(r.step(true, true, late) == 1); CHECK(r.step(false, false, late + 10) == 0);
        CHECK(r.step(false, false, late + 10 + MOTOR_OFF_GRACE_MS - 1) == 0 && r.step(false, false, late + 10 + MOTOR_OFF_GRACE_MS) == -1);
        // the motor switch on before anything is heard (the transmitter refuses it then, but were it on): heard = connected, silent = stays
        LinkState m; CHECK(m.step(false, true, 5) == 0 && m.step(true, true, 6) == 1 && m.step(false, true, 9000) == 0 && m.green && m.silent);
        printf("PASS connected, silent, given up: heard = connected; silent with the motor running is never given up (ten minutes tried); an autorotation keeps its half minute; on the bench given up at once\n"); }
    {   // THE MODULE'S OWN SETTINGS: asked for, and put together, as its handset script does it
        static const std::vector<std::vector<std::vector<uint8_t>>> PCH = ''' + PCH_C + r''';
        struct Want { const char *name, *text, *units; int kind, parent, value, min, max; bool hidden; };
        static const Want WANT[] = ''' + PWANT + r''';
        const int NP = (int)PCH.size();
        uint8_t f[PARAM_FRAME_LEN]; buildParamRead(f, 1, 0);
        static const uint8_t readWant[] = ''' + carr(read_1_0) + r''';
        CHECK(sizeof(readWant) == PARAM_FRAME_LEN && !memcmp(f, readWant, PARAM_FRAME_LEN));
        { Parser pe; Telemetry te; feedAll(pe, te, f, sizeof f, 1); CHECK(te.ownEcho == 1 && te.badCrc == 0 && te.framesOk == 0); }   // a whole frame; heard back it is our own
        // how many it has: in its answer to "who is there?" - and an answer that ends early is read no further than it goes
        static const uint8_t infoN[] = ''' + carr(info_mod_n) + r''', infoShort[] = ''' + carr(info_mod_short) + r''', infoBare[] = ''' + carr(info_mod_bare) + r''',
            infoOld[] = ''' + carr(info_mod) + r''';
        Parser p; Telemetry t;
        feedAll(p, t, infoN, sizeof infoN, 1);
        CHECK(t.moduleParams == NP && t.nModuleInfo == 1 && !strcmp(t.moduleName, "RM Ranger Nano") && NP == 23);
        { Parser q; Telemetry u; feedAll(q, u, infoShort, sizeof infoShort, 1); CHECK(u.moduleParams == 0 && u.nModuleInfo == 1 && u.framesOk == 1); }
        { Parser q; Telemetry u; feedAll(q, u, infoBare, sizeof infoBare, 1); CHECK(u.moduleParams == 0 && u.nModuleInfo == 1 && !strcmp(u.moduleName, "RM Ranger Nano")); }
        { Parser q; Telemetry u; feedAll(q, u, infoOld, sizeof infoOld, 1); CHECK(u.moduleParams == 0 && u.nModuleInfo == 1); }       // a module that says it has none
        // the whole list, piece by piece: each asked for by number and chunk, one request at a time, each setting read right
        ParamReader &r = t.params; r.start(t.moduleParams);
        uint32_t now = 1000; uint32_t asked = 0; bool allRight = true, oneAtATime = true, askedRight = true;
        for (int n = 1; n <= NP; ++n) {
            for (unsigned c = 0; c < PCH[n - 1].size(); ++c) {
                uint8_t q[PARAM_FRAME_LEN], w[PARAM_FRAME_LEN];
                if (r.next(now, q) != PARAM_FRAME_LEN) askedRight = false;
                ++asked; buildParamRead(w, (uint8_t)n, (uint8_t)c);
                if (memcmp(q, w, PARAM_FRAME_LEN)) askedRight = false;
                if (r.next(now + 10, q) != 0) oneAtATime = false;
                feedAll(p, t, PCH[n - 1][c].data(), (unsigned)PCH[n - 1][c].size(), now + 12); now += 20;
            }
            const Want &w = WANT[n - 1]; const Param &o = r.one;
            if (!(r.ready && o.number == n && !o.cut && !strcmp(o.name, w.name) && !strcmp(o.text, w.text) && !strcmp(o.units, w.units) && o.kind == w.kind && o.parent == w.parent
                  && o.value == w.value && o.min == w.min && o.max == w.max && o.hidden == w.hidden)) { allRight = false; fprintf(stderr, "setting %d ('%s') was not read as sent\n", n, w.name); }
            uint8_t q[PARAM_FRAME_LEN]; if (r.next(now, q) != 0) oneAtATime = false;       // nothing more is asked until this one has been taken
            r.ready = false;
        }
        CHECK(allRight); CHECK(oneAtATime); CHECK(askedRight);
        CHECK(r.done && r.failed == 0 && r.stray == 0 && r.asked == asked && r.chunks == asked && t.badCrc == 0 && t.unknownType == 0 && asked > (uint32_t)NP);
        { uint8_t q[PARAM_FRAME_LEN]; CHECK(r.next(now + 100000, q) == 0); }                // read: nothing more is ever asked
        CHECK(!strcmp(WANT[0].name, "Packet Rate") && strlen(WANT[0].text) > 150 && PCH[0].size() == 4 && WANT[14].hidden && strchr(WANT[14].text, '?'));   // (the list here has what it is meant to try)
        // a piece that is not the one awaited is left where it is: one never asked for, another setting's, an earlier one again, a later one
        { Telemetry t2; Parser p2; ParamReader &r2 = t2.params; r2.start((uint8_t)NP); uint8_t q[PARAM_FRAME_LEN];
          feedAll(p2, t2, PCH[0][0].data(), (unsigned)PCH[0][0].size(), 5); CHECK(r2.stray == 1 && r2.len == 0 && r2.chunks == 0);
          CHECK(r2.next(100, q) == PARAM_FRAME_LEN && q[5] == 1 && q[6] == 0);
          feedAll(p2, t2, PCH[1][0].data(), (unsigned)PCH[1][0].size(), 101); CHECK(r2.stray == 2 && r2.len == 0);
          feedAll(p2, t2, PCH[0][0].data(), (unsigned)PCH[0][0].size(), 102); CHECK(r2.chunk == 1 && r2.len == ''' + str(CHUNK) + r''' && !r2.ready);
          CHECK(r2.next(120, q) == PARAM_FRAME_LEN && q[5] == 1 && q[6] == 1);
          feedAll(p2, t2, PCH[0][0].data(), (unsigned)PCH[0][0].size(), 121); CHECK(r2.stray == 3 && r2.chunk == 1 && r2.len == ''' + str(CHUNK) + r''');
          feedAll(p2, t2, PCH[0][2].data(), (unsigned)PCH[0][2].size(), 122); CHECK(r2.stray == 4 && r2.chunk == 1 && !r2.ready);
          // the very piece awaited, but from the receiver (or the flight controller): theirs are not asked for, and not taken for the module's
          { std::vector<uint8_t> o(PCH[0][1]); o[4] = 0xEC; o[o.size() - 1] = crc8(&o[2], (uint8_t)(o.size() - 3));
            feedAll(p2, t2, o.data(), (unsigned)o.size(), 123); CHECK(r2.chunk == 1 && r2.len == ''' + str(CHUNK) + r''' && r2.chunks == 1 && t2.badCrc == 0); }
          // no answer for half a second: THE SAME PIECE is asked for again (never the setting from its beginning: found by review) ...
          CHECK(r2.next(120 + PARAM_ANSWER_MS - 1, q) == 0);
          CHECK(r2.next(120 + PARAM_ANSWER_MS, q) == PARAM_FRAME_LEN && q[5] == 1 && q[6] == 1 && r2.len == ''' + str(CHUNK) + r''' && r2.tries == 1);
          // ... and after PARAM_TRIES askings it is left, and the next is asked for
          uint32_t tt = 120 + PARAM_ANSWER_MS;
          for (int k = 1; k < PARAM_TRIES; ++k) { tt += PARAM_ANSWER_MS; r2.next(tt, q); }
          CHECK(q[5] == 2 && q[6] == 0 && r2.failed == 1 && r2.tries == 0 && !r2.done);
          // the second answers (in its two pieces): read, though the first never was
          feedAll(p2, t2, PCH[1][0].data(), (unsigned)PCH[1][0].size(), tt + 5);
          CHECK(!r2.ready && r2.next(tt + 6, q) == PARAM_FRAME_LEN && q[5] == 2 && q[6] == 1 && PCH[1].size() == 2);
          feedAll(p2, t2, PCH[1][1].data(), (unsigned)PCH[1][1].size(), tt + 9);
          CHECK(r2.ready && r2.one.number == 2 && !strcmp(r2.one.name, "Telem Ratio") && !strcmp(r2.one.units, " (1:64)") && r2.one.max == 9 && !r2.one.cut); }
        // THE LATE ANSWER (found by review): the second piece of a two-piece setting is asked, half a second passes, it is asked
        // again - and then BOTH answers come. The first is taken, the second left; the setting is read as sent. (Begun again from
        // its first piece instead, the late second piece was taken for a whole setting: 'e', kind 99.)
        { Telemetry t4; Parser p4; ParamReader &r4 = t4.params; r4.start((uint8_t)NP); uint8_t q[PARAM_FRAME_LEN];
          r4.one = Param(); r4.number = 2;                                                    // (straight to the two-piece one)
          CHECK(r4.next(10, q) == PARAM_FRAME_LEN && q[5] == 2 && q[6] == 0);
          feedAll(p4, t4, PCH[1][0].data(), (unsigned)PCH[1][0].size(), 12);
          CHECK(r4.next(20, q) == PARAM_FRAME_LEN && q[6] == 1);
          CHECK(r4.next(20 + PARAM_ANSWER_MS, q) == PARAM_FRAME_LEN && q[5] == 2 && q[6] == 1);
          feedAll(p4, t4, PCH[1][1].data(), (unsigned)PCH[1][1].size(), 530); feedAll(p4, t4, PCH[1][1].data(), (unsigned)PCH[1][1].size(), 534);
          CHECK(r4.ready && !r4.one.cut && r4.one.kind == P_CHOICE && !strcmp(r4.one.name, "Telem Ratio") && !strcmp(r4.one.text, WANT[1].text) && r4.stray == 1 && r4.number == 3);
          // and the first piece's answer come twice: the second copy is not the piece awaited
          r4.ready = false; r4.number = 2; r4.chunk = 0; r4.len = 0; r4.waiting = false; r4.tries = 0;
          CHECK(r4.next(1000, q) == PARAM_FRAME_LEN && q[6] == 0);
          feedAll(p4, t4, PCH[1][0].data(), (unsigned)PCH[1][0].size(), 1002); feedAll(p4, t4, PCH[1][0].data(), (unsigned)PCH[1][0].size(), 1004);
          CHECK(r4.chunk == 1 && r4.len == ''' + str(CHUNK) + r''' && r4.stray == 2 && !r4.ready); }
        // a request that never went out (taken back: the model may be flying) is asked again and was no try; one that lay waiting a
        // while has its half second from when it went
        { ParamReader d; d.start(3); uint8_t q[PARAM_FRAME_LEN];
          CHECK(d.next(0, q) == PARAM_FRAME_LEN); d.notSent(); CHECK(d.next(1, q) == PARAM_FRAME_LEN && q[5] == 1 && q[6] == 0 && d.tries == 0 && d.asked == 2);
          d.sentAt(400); CHECK(d.next(1 + PARAM_ANSWER_MS, q) == 0 && d.next(400 + PARAM_ANSWER_MS - 1, q) == 0 && d.next(400 + PARAM_ANSWER_MS, q) == PARAM_FRAME_LEN && d.tries == 1); }
        // a module that never answers: each setting is left in its turn and the reading ends - it does not go round for ever
        { ParamReader d; d.start(3); uint8_t q[PARAM_FRAME_LEN]; uint32_t tt = 0; int sent = 0;
          for (int k = 0; k < 200 && !d.done; ++k) { if (d.next(tt, q)) ++sent; tt += PARAM_ANSWER_MS; }
          CHECK(d.done && d.failed == 3 && sent == 3 * PARAM_TRIES && d.next(tt + 5000, q) == 0); }
        // more settings than there can be: no more than the module's own limit are asked for; none: nothing to read
        { ParamReader d; d.start(200); CHECK(d.count == MAX_PARAMS && !d.done); ParamReader e; e.start(0); uint8_t q[PARAM_FRAME_LEN]; CHECK(e.done && e.next(1, q) == 0); }
        // data that ends early is marked and never read past (the sanitizer watches): every length of four kinds of setting
        static const std::vector<std::vector<uint8_t>> WHOLE = {''' + ', '.join(carr(PDATA[k]) for k in (0, 12, 15, 21)) + r'''};
        { bool marked = true, wholeRight = true;
          for (auto &w : WHOLE) {
              for (size_t L = 0; L < w.size(); ++L) { std::vector<uint8_t> part(w.begin(), w.begin() + (long)L); Param o; paramParse(part.data(), (uint16_t)L, o); if (!o.cut) marked = false; }
              Param o; paramParse(w.data(), (uint16_t)w.size(), o); if (o.cut) wholeRight = false; }
          CHECK(marked); CHECK(wholeRight); }
        // a list of choices longer than the room here: cut to the room and marked, and the value after it still read right
        static const uint8_t longData[] = ''' + carr(long_data) + r''';
        { Param o; paramParse(longData, sizeof longData, o);
          CHECK(o.cut && strlen(o.text) == sizeof(o.text) - 1 && !strncmp(o.text, "Choice00;Choice01;", 18) && o.value == 7 && !strcmp(o.units, "x") && !strcmp(o.name, "Long One")); }
        // more data than one setting can have (a module gone wrong): taken as far as the room, marked, and the reading goes on
        { Telemetry t3; Parser p3; ParamReader &r3 = t3.params; r3.start(2); uint8_t q[PARAM_FRAME_LEN]; uint32_t tt = 10;
          for (int c = 0; c < 6 && !r3.ready; ++c) {
              CHECK(r3.next(tt, q) == PARAM_FRAME_LEN);
              uint8_t pl[60]; pl[0] = 0xEA; pl[1] = 0xEE; pl[2] = 1; pl[3] = (uint8_t)(9 - c); memset(pl + 4, 'A', 56);
              uint8_t fr[64]; fr[0] = 0xEA; fr[1] = 62; fr[2] = 0x2B; memcpy(fr + 3, pl, 60); fr[63] = crc8(&fr[2], 61);
              feedAll(p3, t3, fr, 64, tt + 1); tt += 20; }
          CHECK(r3.ready && r3.one.cut && r3.one.number == 1 && r3.number == 2); }
        CHECK(PARAM_ANSWER_MS >= 300 && PARAM_TRIES >= 2 && MAX_PARAMS == 64);
        // THE FOUR SETTINGS THE PAGE SHOWS: kept by NAME whatever their number, their choices as the page lists them, the one frame that changes one
        { uint8_t wf[PARAM_FRAME_LEN]; buildParamWrite(wf, 2, 6);
          static const uint8_t writeWant[] = ''' + carr(write_2_6) + r''';
          CHECK(sizeof(writeWant) == PARAM_FRAME_LEN && !memcmp(wf, writeWant, PARAM_FRAME_LEN) && wf[2] == T_PARAM_WRITE);
          const char *rates = "50Hz(-115dBm);100Hz Full(-112dBm);150Hz(-112dBm);250Hz(-108dBm);333Hz Full(-105dBm);500Hz(-105dBm);D250(-104dBm);D500(-104dBm);F500(-104dBm)";   // his module's, 14 Nov 2026
          char o[40];
          CHECK(optionText(rates, 3, o, sizeof o) && !strcmp(o, "250Hz")); CHECK(optionText(rates, 4, o, sizeof o) && !strcmp(o, "333Hz Full"));
          CHECK(optionText(rates, 0, o, sizeof o) && !strcmp(o, "50Hz")); CHECK(optionText(rates, 8, o, sizeof o) && !strcmp(o, "F500")); CHECK(!optionText(rates, 9, o, sizeof o) && !o[0]);
          for (uint8_t k = 0; k < 9; ++k) CHECK(offeredPlace(rates, k) == k && offeredRank(rates, k) == k);
          CHECK(offeredPlace(rates, 9) == 255 && offeredRank(rates, 9) == 255);
          const char *gaps = "A;;C;;;F";                                    // places 0, 2 and 5 are offered; the empty ones still count as places
          CHECK(offeredPlace(gaps, 0) == 0 && offeredPlace(gaps, 1) == 2 && offeredPlace(gaps, 2) == 5 && offeredPlace(gaps, 3) == 255);
          CHECK(offeredRank(gaps, 0) == 0 && offeredRank(gaps, 2) == 1 && offeredRank(gaps, 5) == 2 && offeredRank(gaps, 1) == 255 && offeredRank(gaps, 4) == 255 && offeredRank(gaps, 6) == 255);
          CHECK(!optionText(gaps, 1, o, sizeof o) && optionText(gaps, 5, o, sizeof o) && !strcmp(o, "F") && !optionText(gaps, 6, o, sizeof o));
          CHECK(offeredPlace("", 0) == 255 && offeredPlace(";;", 0) == 255 && offeredRank("", 0) == 255 && offeredRank(";;", 1) == 255);
          char tiny[4]; CHECK(optionText("ABCDEFG;x", 0, tiny, sizeof tiny) && !strcmp(tiny, "ABC"));          // cut to the room, never past it
          CHECK(optionText("A(b);(-1dBm);X(dBm)", 0, o, sizeof o) && !strcmp(o, "A(b)"));                    // only a sensitivity's bracket is cut ...
          CHECK(optionText("A(b);(-1dBm);X(dBm)", 1, o, sizeof o) && !strcmp(o, "(-1dBm)"));                 // ... and never the whole choice
          CHECK(optionText("A(b);(-1dBm);X(dBm)", 2, o, sizeof o) && !strcmp(o, "X"));
          Setting set[SET_COUNT]; Param p1; p1.number = 7; p1.kind = P_CHOICE; strcpy(p1.name, "Max Power"); strcpy(p1.text, "25;50;100"); strcpy(p1.units, "mW"); p1.value = 1; p1.max = 2;
          CHECK(keepSetting(p1, set) && set[SET_POWER].known && set[SET_POWER].number == 7 && set[SET_POWER].value == 1 && set[SET_POWER].max == 2 && !set[SET_RATE].known && !set[SET_TELEM].known);
          char w[32]; settingWords(set[SET_POWER], w, sizeof w); CHECK(!strcmp(w, "50 mW"));
          Param p2; p2.number = 2; p2.kind = P_CHOICE; strcpy(p2.name, "Telem Ratio"); strcpy(p2.text, "Std;Off;1:128;1:64;1:32;1:16;1:8;1:4;1:2;Race"); strcpy(p2.units, " (1:64)"); p2.value = 0; p2.max = 9;
          CHECK(keepSetting(p2, set)); settingWords(set[SET_TELEM], w, sizeof w); CHECK(!strcmp(w, "Std (1:64)"));
          p2.value = 6; strcpy(p2.units, " (1094bps) "); p2.number = 12; CHECK(keepSetting(p2, set) && set[SET_TELEM].number == 12); settingWords(set[SET_TELEM], w, sizeof w); CHECK(!strcmp(w, "1:8 (1094bps)"));
          Param p3 = p1; strcpy(p3.name, "Max Power "); CHECK(!keepSetting(p3, set));                         // not its name
          Param p4 = p1; p4.kind = P_INFO; CHECK(!keepSetting(p4, set));                                      // not a choice
          Param p5 = p1; p5.cut = true; CHECK(keepSetting(p5, set) && set[SET_POWER].cut);                    // cut short: kept to be shown, marked (never changed)
          Setting none; settingWords(none, w, sizeof w); CHECK(!w[0]);
          Setting odd = set[SET_TELEM]; odd.value = 20; settingWords(odd, w, sizeof w); CHECK(!strncmp(w, "? ", 2));       // a value with no choice: said so, nothing invented
          char small[6]; settingWords(set[SET_TELEM], small, sizeof small); CHECK(strlen(small) == 5);        // into a small room: cut, not past it
          CHECK(needsNoModel(SET_RATE) && needsNoModel(SET_SWITCH) && !needsNoModel(SET_TELEM) && !needsNoModel(SET_POWER));
          // THE WHEEL: what the module offers, less the telemetry ratio's "Off" (no replies: the model could never be connected)
          // and "Race" (no replies with channel 5 high - an LDRC model's throttle); the rank on the wheel and the place in the list
          const char *tl = "Std;Off;1:128;1:64;1:32;1:16;1:8;1:4;1:2;Race";          // his module's, 14 Nov 2026
          { const uint8_t wantPlace[] = {0, 2, 3, 4, 5, 6, 7, 8};
            for (uint8_t r = 0; r < 8; ++r) CHECK(pagePlace(SET_TELEM, tl, r) == wantPlace[r] && pageRank(SET_TELEM, tl, wantPlace[r]) == r);
            CHECK(pagePlace(SET_TELEM, tl, 8) == 255 && pageRank(SET_TELEM, tl, 1) == 255 && pageRank(SET_TELEM, tl, 9) == 255 && pageRank(SET_TELEM, tl, 10) == 255);
            CHECK(!pageOffers(SET_TELEM, tl, 1) && !pageOffers(SET_TELEM, tl, 9) && pageOffers(SET_TELEM, tl, 0) && pageOffers(SET_TELEM, tl, 6) && !pageOffers(SET_TELEM, tl, 10));
            CHECK(pageOffers(SET_POWER, "Off;Race", 0) && pageOffers(SET_RATE, "Off;Race", 1));                // (only the telemetry ratio's are left off)
            CHECK(pagePlace(SET_TELEM, "Std;Off;;1:64;Race", 0) == 0 && pagePlace(SET_TELEM, "Std;Off;;1:64;Race", 1) == 3 && pagePlace(SET_TELEM, "Std;Off;;1:64;Race", 2) == 255);
            CHECK(pagePlace(SET_RATE, rates, 4) == 4 && pageRank(SET_RATE, rates, 8) == 8 && pagePlace(SET_SWITCH, gaps, 2) == 5 && pageRank(SET_SWITCH, gaps, 5) == 2); }
          // DOES THE SWITCH MODE CARRY CHANNEL 5 WHOLE? Only "16ch Rate/2" - and never when the module has not said (or not all of it)
          { Setting sw; Param ps; ps.number = 3; ps.kind = P_CHOICE; strcpy(ps.name, "Switch Mode"); strcpy(ps.text, "Wide;Hybrid"); ps.value = 0; ps.max = 1;
            CHECK(!carriesChannel5(sw));                                                                      // not said
            Setting four[SET_COUNT]; CHECK(keepSetting(ps, four) && !carriesChannel5(four[SET_SWITCH]));      // Wide
            ps.value = 1; keepSetting(ps, four); CHECK(!carriesChannel5(four[SET_SWITCH]));                   // Hybrid
            strcpy(ps.text, "8ch;16ch Rate/2;12ch Mixed"); ps.max = 2;
            ps.value = 0; keepSetting(ps, four); CHECK(!carriesChannel5(four[SET_SWITCH]));                   // 8ch
            ps.value = 1; keepSetting(ps, four); CHECK(carriesChannel5(four[SET_SWITCH]));                    // 16ch Rate/2: the one that does
            ps.value = 2; keepSetting(ps, four); CHECK(!carriesChannel5(four[SET_SWITCH]));                   // 12ch Mixed
            ps.value = 1; ps.cut = true; keepSetting(ps, four); CHECK(!carriesChannel5(four[SET_SWITCH]));    // cut short: not relied on
            ps.cut = false; ps.value = 7; keepSetting(ps, four); CHECK(!carriesChannel5(four[SET_SWITCH]));   // a value with no choice
            // THE THROTTLE HELD, the rule: "the module has not said" is not "it carries channel 5" - held until it says the one mode
            CHECK(throttleHeld(true, CH5_UNKNOWN) && throttleHeld(true, CH5_ONE_BIT) && !throttleHeld(true, CH5_CARRIED));
            CHECK(!throttleHeld(false, CH5_UNKNOWN) && !throttleHeld(false, CH5_ONE_BIT) && !throttleHeld(false, CH5_CARRIED));   // (a throttle that is not channel 5: never)
            // ... and what a reading says: the mode that carries it, a mode that does not, and - not read just now (the list is
            // being read again), or not read whole - NOTHING NEW: what was known stays, whichever it was
            ps.value = 1; keepSetting(ps, four); for (uint8_t was = 0; was < 3; ++was) CHECK(channel5Said(four[SET_SWITCH], was) == CH5_CARRIED);
            ps.value = 0; keepSetting(ps, four); for (uint8_t was = 0; was < 3; ++was) CHECK(channel5Said(four[SET_SWITCH], was) == CH5_ONE_BIT);
            ps.value = 7; keepSetting(ps, four); for (uint8_t was = 0; was < 3; ++was) CHECK(channel5Said(four[SET_SWITCH], was) == CH5_ONE_BIT);   // (a value with no choice: not the one mode)
            ps.value = 1; ps.cut = true; keepSetting(ps, four); for (uint8_t was = 0; was < 3; ++was) CHECK(channel5Said(four[SET_SWITCH], was) == was);
            ps.cut = false; keepSetting(ps, four); four[SET_SWITCH].known = false; for (uint8_t was = 0; was < 3; ++was) CHECK(channel5Said(four[SET_SWITCH], was) == was);
            CHECK(channel5Said(Setting(), CH5_CARRIED) == CH5_CARRIED && channel5Said(Setting(), CH5_UNKNOWN) == CH5_UNKNOWN); }
          CHECK(!strcmp(setName(SET_RATE), "Packet Rate") && !strcmp(setName(SET_SWITCH), "Switch Mode") && !setName(9)[0]); }
        printf("PASS the module's own settings: asked for as its handset script asks (EE 06 2C EE EA ...), %d of them put together from %u pieces and each read as sent; a piece out of turn left; no answer = asked again, then left; data cut short marked, never read past; the four the page shows kept by name, their choices as it lists them, one frame to change one (EE 06 2D EE EA ...)\n", NP, (unsigned)asked); }
    printf("%d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
problems = []
with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 't.cpp'), 'w').write(PROG)
    r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-fsanitize=address,undefined',
                        '-o', os.path.join(d, 't'), os.path.join(d, 't.cpp')], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[:4000]); print('FAILED to compile'); sys.exit(1)
    r = subprocess.run([os.path.join(d, 't')], capture_output=True, text=True)
    sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
    if r.returncode: problems.append('the host checks failed')
# the driver only in test builds; releases untouched
main = src('src/main.cpp'); trx = src('include/transceiver.h'); util = src('include/Utilities.h'); sdc = src('include/SDcard.h')
menu = src('include/MenuOptions.h'); msign = src('include/Motor_sign.h'); defs = src('include/1Definitions.h')
if not re.search(r'#ifdef ELRS_TEST\s*\n\s*#include "ElrsCrsf.h"', main): problems.append('main.cpp: ElrsCrsf.h must be included only under #ifdef ELRS_TEST')
if 'ElrsTestTick' in main or 'ElrsLink' in main: problems.append('main.cpp: loop() must not call the driver itself - SendData does, so the waits keep the link too')
if 'Serial6' in BLOCK or 'IntervalTimer' in BLOCK or 'noInterrupts' in BLOCK: problems.append('ElrsCrsf.h: the hardware must stay outside the tested block')
if '#ifdef ELRS_TEST' not in hdr[j:]: problems.append('ElrsCrsf.h: the driver must be under #ifdef ELRS_TEST')
drv = hdr[j:]
def body(name):   # a function of the driver: what stands between its heading's { and the } at a line's start
    m = re.search(r'\n[^\n;]*\b' + name + r'\([^)\n]*\)[^\n;]*\n\{(.*?)\n\}', drv, re.S)
    return m.group(1) if m else None
I, L, S, B, E, C, G = (body(n) for n in ('ElrsSendIsr', 'ElrsLink', 'ElrsService', 'ElrsBegin', 'ElrsEnd', 'ElrsConnected', 'ElrsGivenUp'))
gyn = src('include/Utilities.h'); buddy = src('include/BuddyWireless.h')
if None in (I, L, S, B, E, C, G): problems.append('ElrsCrsf.h: ElrsSendIsr, ElrsLink, ElrsService, ElrsBegin, ElrsEnd, ElrsConnected and ElrsGivenUp must all be there')
else:
    # THE HOOK: SendData hands every call to ElrsLink() first, before its own pacing and its own silences
    if not re.search(r'FASTRUN void SendData\(\)\s*\{\s*CRUMB\(CRUMB_SENDDATA\);\s*#ifdef ELRS_TEST[^\n]*\n\s*if \(ElrsLink\(\)\)\s*\n\s*return;\s*\n#endif\s*\n\s*if \(\(millis\(\) - LastPacketSentTime\) < FHSS_data::PaceMaker\)', trx):
        problems.append('transceiver.h: SendData must begin with the guarded "if (ElrsLink()) return;", before its pacing')
    # the power switch: pin 10 goes high BEFORE the serial line starts, the line waits for lineMayStart()
    a_, b_, c_, d_ = S.find('ElrsPowerOn();'), S.find('lineMayStart('), S.find('Serial6.begin('), S.find('ElrsTimer.begin(ElrsSendIsr')
    if not (0 <= a_ < b_ < c_ < d_): problems.append('ElrsCrsf.h: the driver must switch the power on, wait for lineMayStart(), start Serial6, and only then the timer')
    if 'digitalWriteFast(ElrsCrsf::POWER_PIN, HIGH)' not in drv: problems.append('ElrsCrsf.h: the driver must raise POWER_PIN')
    m_, n_ = S.find('Serial6.addMemoryForRead('), S.find('Serial6.begin(')
    if not (0 <= m_ < n_): problems.append('ElrsCrsf.h: the driver must give Serial6 its extra receive memory before begin()')
    # THE TIMER sends, only the finished copy, only while it is fresh - and never asks what is heard
    if 'SendBuffer' in I: problems.append('ElrsCrsf.h: the timer must NEVER read SendBuffer (loop() fills it in stages: the safety switch comes last)')
    if 'ElrsChannels[i]' not in I or 'sticksFresh(ElrsCopyMs' not in I or 'ElrsPacer.nextPeriodUs()' not in I: problems.append('ElrsCrsf.h: the timer must send the finished copy, only while fresh, at the pacer\'s period')
    if I.find('sticksFresh(') > I.find('Serial6.write(') or I.count('Serial6.write(') != 1: problems.append('ElrsCrsf.h: the timer must ask sticksFresh() before it writes')
    if not re.search(r'\n    if \(!ElrsCrsf::sticksFresh\(ElrsCopyMs, millis\(\)\)\)\s*\{\s*\+\+ElrsHeldBack;[^}]*?return;\s*\}', I): problems.append('ElrsCrsf.h: when the copy is not fresh the timer must count it and RETURN, with no other condition')
    if re.search(r'delay|while\s*\(|LogText|ElrsSay|Serial6\.flush', I): problems.append('ElrsCrsf.h: the timer must never wait, loop or log')
    if drv.count('Serial6.write(') != 1: problems.append('ElrsCrsf.h: only the timer writes to the module')
    if re.search(r'ElrsState|ElrsTelem|Connected|LedWasGreen|MotorEnabled|linkHeard|SendNoData|SafetyHold', I): problems.append('ElrsCrsf.h: what the timer sends must not depend on what is heard, nor on any switch')
    # THE COPY: before anything that reads the module, with interrupts off, after the motor switch's and the safety switch's word
    k0, k1, k1b, k2, k3 = L.find('return false;', L.find('if (!ElrsOn)')), L.find('FixArmingChannel();'), L.find('FixMotorChannel();'), L.find('noInterrupts();'), L.find('ElrsChannels[i] = SendBuffer[i]')   # (the 'return false' of an LDRC model once setup is over: the one before it is setup's own gate)
    k4, k5, k6 = L.find('interrupts();', k3), L.find('ElrsService();'), L.find('LastPacketSentTime = now;')
    if not (0 <= k0 < k1b < k1 < k2 < k3 < k4 < k5) or k6 < 0: problems.append('ElrsCrsf.h: ElrsLink must return false for an LDRC model, then FixMotorChannel, FixArmingChannel, the copy with interrupts off, and the reading after it')
    if 'ElrsCopyMs = ' not in L[k2:k4]: problems.append('ElrsCrsf.h: the copy and its time must be made together, with interrupts off')
    # The copy is made on EVERY call for an ELRS model but for the few cases its comment names - and never by what is heard:
    # binding (switched off, this pass's channels not used), the model in memory not an ELRS one, a mode loop() sends nothing
    # in, channels not worked out afresh, and the transmitter's own "the motor switch is ON" box.
    between = re.sub(r'//[^\n]*', '', L[k0 + len('return false;'):k4])
    conds = re.findall(r'\bif\s*\((.*)\)\s*$', between, re.M)
    if conds != ['BindingEnabled', 'ElrsModel && sendingMode && NewCompressNeeded && !(SendNoData && MotorEnabled)', 'MotorChannel != ElrsThrottleWas', '(ElrsHeld || !MotorEnabled) && MotorChannel < 16']: problems.append('ElrsCrsf.h: the copy has its named conditions only: found ' + repr(conds))
    # THE THROTTLE HELD (14 Nov 2026, found by review, twice): in the copy itself, after the channels, the motor's channel is
    # "motor off" while ElrsHeld - and whenever the motor switch is off, whatever the buddy switch says. ElrsHeld is the RULE
    # (ElrsCrsf::throttleHeld: the throttle is channel 5 and the module has NOT said the mode that carries it) of what the module
    # LAST SAID (ElrsCh5: kept while its list is read again). It is set when the module takes the link (held, not known - but for
    # a restart in flight whose stamp says it was not), in the ground's routine, and "no" at the link's ending: nowhere else, so
    # it can neither begin nor end in the air.
    if not re.search(r'ElrsChannels\[i\] = SendBuffer\[i\];\s*if \(\(ElrsHeld \|\| !MotorEnabled\) && MotorChannel < 16\)\s*ElrsChannels\[MotorChannel\] = motorOff;', between) or 'const uint16_t motorOff = IntoHigherRes(MotorChannelZero);' not in between:
        problems.append('ElrsCrsf.h: while the throttle is held, and whenever the motor switch is off, the copy carries "motor off" on the motor\'s channel')
    nocom = re.sub(r'//[^\n]*', '', drv)
    held_sets = re.findall(r'\bElrsHeld = ([^;]+);', nocom)
    GR = re.sub(r'//[^\n]*', '', body('ElrsOnTheGround') or '')
    RULE = 'ElrsCrsf::throttleHeld(MotorChannel == 4, ElrsCh5)'
    if sorted(held_sets) != sorted(['false', 'held', 'false', RULE, RULE, RULE]) or 'ElrsHeld = held;' not in GR or GR.count('ElrsHeld = ' + RULE + ';') != 1 or 'ElrsHeld = false;' not in E or 'ElrsHeld = ' + RULE + ';' not in B \
            or not re.search(r'if \(MotorChannel != ElrsThrottleWas\)\s*\{\s*ElrsThrottleWas = MotorChannel;\s*ElrsHeld = ' + re.escape(RULE) + r';', re.sub(r'//[^\n]*', '', L)):
        problems.append('ElrsCrsf.h: whether the throttle is held is set when the module takes the link, in the ground\'s routine (the rule, and at a write of rate or switch mode), at the link\'s ending - and in the copy only when the throttle\'s channel itself has changed: found ' + repr(held_sets))
    ch5_sets = re.findall(r'\bElrsCh5 = ([^;]+);', nocom)
    if sorted(ch5_sets) != sorted(['ElrsCrsf::CH5_UNKNOWN', '(FlightRestart && FlightRestartElrsCarried) ? ElrsCrsf::CH5_CARRIED : ElrsCrsf::CH5_UNKNOWN', 'ElrsCrsf::CH5_UNKNOWN', 'said', 'ElrsCrsf::CH5_UNKNOWN']) \
            or 'ElrsCh5 = (FlightRestart && FlightRestartElrsCarried) ? ElrsCrsf::CH5_CARRIED : ElrsCrsf::CH5_UNKNOWN;' not in B or 'ElrsCh5 = ElrsCrsf::CH5_UNKNOWN;' not in E \
            or 'ElrsCh5 = said;' not in GR or GR.count('ElrsCh5 = ElrsCrsf::CH5_UNKNOWN;') != 1:
        problems.append('ElrsCrsf.h: what the module last said of its switch mode is set at the link\'s beginning and ending and in the ground\'s routine only: found ' + repr(ch5_sets))
    if not re.search(r'const bool changing = \(ElrsChangeStep == 2 \|\| ElrsChangeStep == 3\) && \(ElrsChange == ElrsCrsf::SET_RATE \|\| ElrsChange == ElrsCrsf::SET_SWITCH\);\s*const uint8_t said = changing \? ElrsCh5 : ElrsCrsf::channel5Said\(ElrsSet\[ElrsCrsf::SET_SWITCH\], ElrsCh5\);', GR) or not re.search(r'const bool held = ElrsCrsf::throttleHeld\(MotorChannel == 4, ElrsCh5\);', GR):
        problems.append('ElrsCrsf.h: on the ground the hold is the rule of what the module last said (channel5Said, throttleHeld)')
    if not re.search(r'if \(ElrsChange == ElrsCrsf::SET_RATE \|\| ElrsChange == ElrsCrsf::SET_SWITCH\)\s*\{\s*ElrsSet\[ElrsCrsf::SET_SWITCH\]\.known = false;\s*ElrsCh5 = ElrsCrsf::CH5_UNKNOWN;\s*ElrsHeld = ElrsCrsf::throttleHeld\(MotorChannel == 4, ElrsCh5\);\s*\}\s*ElrsCrsf::buildParamWrite\(f, number, ElrsChangeTo\);', GR):
        problems.append('ElrsCrsf.h: a change of packet rate or switch mode is written: from then the module\'s word is not known (held until it says)')
    if 'ElrsState.step(heard, MotorEnabled && !ElrsHeld, now)' not in drv: problems.append('ElrsCrsf.h: a held throttle\'s motor switch has not "been on" for the link\'s state')
    if not re.search(r'bool ElrsModuleCarries\(\) \{ return ElrsOn && ElrsCh5 == ElrsCrsf::CH5_CARRIED; \}', drv): problems.append('ElrsCrsf.h: ElrsModuleCarries is "the module has the link and HAS SAID the mode that carries channel 5" (not "the throttle is not held")')
    FG = src('include/FlightGuard.h')
    if not re.search(r'#ifdef ELRS_TEST[^\n]*\n\s*if \(ElrsModuleCarries\(\)\)\s*b\[5\] \|= 2;\s*#endif', FG) or not re.search(r'#ifdef ELRS_TEST[^\n]*\n\s*FlightRestartElrsCarried = \(b\[5\] & 2\) != 0;\s*#endif', FG) \
            or not re.search(r'#ifdef ELRS_TEST[^\n]*\nbool FlightRestartElrsCarried = false;\s*#endif', FG):
        problems.append('FlightGuard.h: a flying ELRS model\'s "throttle not held" goes into the stamp\'s second bit and is read back at a restart in flight (test builds only)')
    if not re.search(r'if \(BindingEnabled\)\s*\{\s*BindingEnabled = false;\s*LedIsBlinking = false;\s*\}\s*else if \(ElrsModel && sendingMode', between): problems.append('ElrsCrsf.h: with binding found on, it is switched off and THAT pass is not copied')
    if 'const bool sendingMode = CurrentMode == NORMAL || CurrentMode == SAVE_RF_SETTINGS || CurrentMode == RESTORE_RF_SETTINGS;' not in between: problems.append('ElrsCrsf.h: the copy only in the modes loop() itself sends in')
    if re.search(r'ElrsState|ElrsTelem|Connected|LedWasGreen|linkHeard|SafetyHold', between): problems.append('ElrsCrsf.h: the copy must never depend on what is heard')
    # THE STICKS ARE READ AGAIN FOR EVERY COPY: GetNewChannelValues works only once NewCompressNeeded is cleared, and LDRC's
    # SendData (which cleared it with each packet) no longer runs for such a model (found by review, 13 Nov 2026: without this
    # the channels were worked out once and never again)
    if not re.search(r'if \(!NewCompressNeeded\)\s*\{\s*NewCompressNeeded = true;\s*GetAllInputs\(\);', main): problems.append('main.cpp: GetNewChannelValues is no longer as this test knows it (it must work only when NewCompressNeeded is clear)')
    after = L[k4:]
    if not re.search(r'^\s*NewCompressNeeded = false;', re.sub(r'//[^\n]*', '', after), re.M) or after.find('NewCompressNeeded = false;') > after.find('ElrsService();'): problems.append('ElrsCrsf.h: ElrsLink must clear NewCompressNeeded on every call, so the channels are worked out afresh for the next copy')
    switch = L[:k0]
    if not re.search(r'ElrsBusy = false;\s*NewCompressNeeded = false;[^\n]*\n\s*return true;', switch): problems.append('ElrsCrsf.h: in the pass where the link is begun or ended nothing is copied (RedLedOn has emptied the channels), and they are worked out afresh')
    if not re.search(r'if \(!ElrsBusy\)\s*\{[^}]*ElrsBusy = true;\s*ElrsService\(\);\s*ElrsBusy = false;\s*\}', L) or L.find('if (!ElrsBusy)') < k4: problems.append('ElrsCrsf.h: the reading is never begun twice (a wait inside it comes back for the copy alone), and the copy comes first')
    if not re.search(r'if \(ElrsModel != ElrsOn && !ElrsBusy && ', L): problems.append('ElrsCrsf.h: the link is not changed from inside its own beginning or ending')
    # A model set to ELRS whose link has not begun yet (the settle time; a beginning in hand): LDRC says nothing (14 Nov 2026)
    if not re.search(r'if \(!ElrsOn\)\s*\{\s*if \(!ElrsModel\)\s*return false;\s*NewCompressNeeded = false;\s*return true;\s*\}', re.sub(r'//[^\n]*', '', L)): problems.append('ElrsCrsf.h: for a model set to ELRS, LDRC must be silent from the first pass (before the link has begun too), and the channels still worked out')
    if drv.count('SendBuffer[') != 1: problems.append('ElrsCrsf.h: SendBuffer is read in one place only: the copy')
    if not re.search(r'noInterrupts\(\);\s*ElrsPacer\.onTiming\(ElrsTelem, now\);\s*interrupts\(\);', S): problems.append('ElrsCrsf.h: loop() must give the pacer the timing word with interrupts off')
    if 'Serial6.clear();' not in S or 'LINE_STALE_MS' not in S: problems.append('ElrsCrsf.h: what the line holds after loop() was away must be thrown away, not read as news')
    # connected / given up by the transmitter's own code, each in its one place; given up only when the link's rule says so
    if drv.count('GreenLedOn();') != 1 or 'GreenLedOn();' not in C: problems.append('ElrsCrsf.h: GreenLedOn only when the model is first heard (ElrsConnected)')
    if drv.count('RedLedOn();') != 4 or 'RedLedOn();' not in B or 'RedLedOn();' not in E or 'RedLedOn();' not in G: problems.append('ElrsCrsf.h: RedLedOn in four places only: the link begun, the link ended, the model given up, and no model with the light not red')
    if not re.search(r'if \(!ElrsState\.green && !LedWasRed && !LedWasGreen\)\s*\{[^}]*\}?[^}]*>= RED_LED_ON_TIME\)\s*\{\s*ElrsNotRedMs = 0;\s*RedLedOn\(\);', S): problems.append('ElrsCrsf.h: no model and the light not red: red after RED_LED_ON_TIME, as LDRC has it (red refuses the motor switch)')
    if not re.search(r'const int change = ElrsState\.step\(heard, MotorEnabled && !ElrsHeld, now\);\s*if \(change > 0\)\s*ElrsConnected\(\);\s*else if \(change < 0\)\s*ElrsGivenUp\(\);', re.sub(r'//[^\n]*', '', S)): problems.append('ElrsCrsf.h: connected and given up only as LinkState::step says')
    if len(re.findall(r'\bElrsGivenUp\(\)', drv)) != 2 or len(re.findall(r'\bElrsConnected\(\)', drv)) != 3: problems.append('ElrsCrsf.h: ElrsGivenUp is called once; ElrsConnected twice (first heard, and the transmitter\'s own light put out)')
    if not all(x in C for x in ('BoundFlag = true;', 'ModelMatched = true;', 'UsingDefaultPipeAddress = false;', 'ParametersToBeSentPointer = 0;')): problems.append('ElrsCrsf.h: connected = the transmitter\'s own flags, and no LDRC settings queued')
    # the telemetry goes in by the transmitter's own door, and LDRC's own business is kept out
    if 'takeItems(ElrsTelem, RXCellCount == 12, RotorFlight_V, items)' not in S or drv.count('ParseTelemetryItem();') != 1: problems.append('ElrsCrsf.h: the telemetry must go in as items through ParseTelemetryItem, in one place')
    if 'BindingEnabled = false;' not in L or 'ParametersToBeSentPointer = 0;' not in S: problems.append('ElrsCrsf.h: binding and the LDRC receiver\'s settings must be kept out of an ELRS model')
    # found by review, 13 Nov 2026:
    if not re.search(r'bool heard = ElrsCrsf::linkHeard\(ElrsTelem, now\);\s*if \(!ElrsState\.green && SendNoData\)\s*heard = false;', S): problems.append('ElrsCrsf.h: no model is CONNECTED while the motor switch stands refused (SendNoData) - or the switch, still on, would start the motor at the connection')
    if 'LostContactFlag = false;' not in C: problems.append('ElrsCrsf.h: connected must clear LostContactFlag (the motor timer waits for it)')
    if not re.search(r'const uint32_t now = millis\(\);', S) or 'ElrsService(uint32_t' in drv: problems.append('ElrsCrsf.h: ElrsService must look at the clock itself (the power\'s moment is stamped after ElrsLink looked: the 0.3 s was skipped)')
    if not re.search(r'else if \(ElrsState\.green && !LedWasGreen\)\s*ElrsConnected\(\);', S) or 'ElrsState.green = ElrsState.silent = false; // (the transmitter ended' in S: problems.append('ElrsCrsf.h: when the transmitter puts its own light out, the model is connected again - never dropped (only LinkState gives a model up)')
    if not re.search(r'Serial6\.clear\(\);\s*ElrsParser\.len = 0;\s*if \(ElrsState\.green && !ElrsState\.silent\)\s*ElrsTelem\.linkMs = now \? now : 1;', S): problems.append('ElrsCrsf.h: a model heard when loop() left is not called silent for the absence')
    if not re.search(r'noInterrupts\(\);[^\n]*\n\s*ElrsTimer\.end\(\);\s*interrupts\(\);', E): problems.append('ElrsCrsf.h: the timer is ended with interrupts off')
    GR, SAY, MF, LL, LS = (body(n) for n in ('ElrsOnTheGround', 'ElrsSay', 'ElrsMayFly', 'ElrsLogLine', 'ElrsListLog'))
    nocom = lambda t: re.sub(r'//[^\n]*', '', t)
    if None in (GR, SAY, MF, LL, LS): problems.append('ElrsCrsf.h: ElrsOnTheGround, ElrsSay, ElrsMayFly, ElrsLogLine and ElrsListLog must all be there'); GR = SAY = MF = LL = LS = ''
    # MAY THE MODEL BE FLYING? (found by review, 14 Nov 2026: "the motor switch is off" is not "on the ground" - an autorotation
    # is a motor-off.) The safety switch off, or the motor switch on; with no safety switch, the motor switch on or having been on
    # in this connection. Then: no line to the card (it is kept), no frame of ours in a channel frame's place (one waiting is taken back).
    if not re.fullmatch(r'\s*if \(SafetyIsDefined\(\)\)\s*return SafetyIsOff\(\) \|\| MotorEnabled;\s*return MotorEnabled \|\| \(ElrsState\.green && ElrsState\.motorEverOn\);\s*', nocom(MF)):
        problems.append('ElrsCrsf.h: "may the model be flying?" = the safety off or the motor switch on; with no safety switch, the motor switch on or having been on in this connection')
    if not re.match(r'\s*if \(ElrsMayFly\(\)\)\s*\{\s*if \(ElrsKept < ELRS_KEEP_MAX\)\s*\{\s*\+\+ElrsKept;\s*DeferLogText\(text, true\);\s*\}\s*else if \(ElrsNotKept < 65535\)\s*\+\+ElrsNotKept;\s*return;\s*\}', nocom(SAY)):
        problems.append('ElrsCrsf.h: a line said while the model may be flying is kept for later (DeferLogText), never written to the card - and only a few are kept (the transmitter\'s store writes itself out, in the air, when full)')
    m_keep = re.search(r'static const uint8_t ELRS_KEEP_MAX = (\d+);', drv)
    if not m_keep or not 2 <= int(m_keep.group(1)) <= 8: problems.append('ElrsCrsf.h: the lines kept in the air are a few of the 24 places the transmitter has for them')
    rest = nocom(drv)
    for t_ in (GR, SAY, LL, LS): rest = rest.replace(nocom(t_), '')
    if 'LogText(' in rest.replace('DeferLogText(', ''): problems.append('ElrsCrsf.h: a line is written to the card only on the ground (ElrsOnTheGround and the two routines it calls for a line) or through ElrsSay')
    if nocom(drv).count('ElrsLogLine(') != 2 or 'ElrsLogLine(' not in GR or nocom(drv).count('ElrsListLog(') != 2 or 'ElrsListLog(' not in GR: problems.append('ElrsCrsf.h: the bench\'s lines and the settings\' lines are written only from the ground\'s routine')
    if nocom(drv).count('ElrsOnTheGround(') != 2 or not re.search(r'if \(ElrsMayFly\(\)\)\s*\{.*?\n        return;\s*\}\s*ElrsOnTheGround\(now, second\);\s*$', nocom(S), re.S):
        problems.append('ElrsCrsf.h: what is only for the ground is reached only past "may the model be flying?", at the service\'s end')
    if nocom(drv).count('ElrsOther[i] = f[i];') != 3 or nocom(GR).count('ElrsOther[i] = f[i];') != 3: problems.append('ElrsCrsf.h: a frame of ours is left for the timer only on the ground ("who is there?", a request for a setting, a change of one)')
    if not re.search(r'if \(ElrsMayFly\(\)\)\s*\{\s*noInterrupts\(\);\s*const bool tookBack = ElrsOtherLen != 0;\s*ElrsOtherLen = 0;\s*interrupts\(\);\s*if \(ElrsListInBox\)\s*\{\s*ElrsListInBox = false;\s*if \(tookBack\)\s*ElrsTelem\.params\.notSent\(\);\s*else\s*ElrsTelem\.params\.sentAt\(now\);\s*\}', nocom(S)):
        problems.append('ElrsCrsf.h: when the model may fly, a frame of ours still waiting for the timer is taken back - looked at and emptied in one piece - and a request so taken back is asked again later, as no try (one that had gone keeps its wait)')
    if not re.search(r'if \(ElrsLogNext < 4\)\s*\{\s*if \(!wrote\)\s*wrote = ElrsLogLine\(ElrsLogNext\+\+\);\s*\}\s*else if \(\(uint32_t\)\(now - ElrsLastLogMs\) >= 5000\)', nocom(GR)): problems.append('ElrsCrsf.h: the bench\'s lines one a pass')
    # never two lines to the card in one pass of the ground's routine: each write is under "!wrote" or is the first that can come
    if nocom(GR).count('LogText(') != 5 or nocom(GR).count('!wrote') < 6 or nocom(GR).find('LogText(') > nocom(GR).find('!wrote'): problems.append('ElrsCrsf.h: on the ground no more than one line goes to the card in a pass (the first write that can come, then each under "!wrote")')
    if 'bool ElrsCarries() { return ElrsOn || ElrsModel; }' not in drv: problems.append('ElrsCrsf.h: "the module carries this model" from the moment the model in memory is an ELRS one (LDRC must not ping or hold it back in the tenth of a second before its link begins)')
    if 'static_assert(sizeof(ElrsOther) >= ElrsCrsf::PING_LEN && sizeof(ElrsOther) >= ElrsCrsf::PARAM_FRAME_LEN' not in drv: problems.append('ElrsCrsf.h: the timer\'s place for another frame is checked for size by the compiler')
    if not re.search(r'#ifdef ELRS_TEST[^\n]*\n\s*if \(\(BoundFlag && ModelMatched\) \|\| ElrsFlies\(\)\)\s*\n#else\s*\n\s*if \(BoundFlag && ModelMatched\)\s*\n#endif', gyn): problems.append('Utilities.h: GetYesOrNo (every box on the screen) must keep an ELRS model\'s frames going, heard or not')
    if not re.search(r'void GetBuddyData\(\)[^\n]*\n\{\s*#ifdef ELRS_TEST[^\n]*\n[^\n]*\n\s*if \(ElrsCarries\(\)\)\s*\n\s*return;\s*\n#endif', buddy): problems.append('BuddyWireless.h: no wireless buddy for an ELRS model (the pupil is asked by LDRC\'s radio, which is silent)')
    if not (re.search(r'const bool askNames = Connected && !ElrsTelem\.fcName\[0\] && ElrsPings < ElrsCrsf::PING_TRIES;', GR)
            and re.search(r'const bool askModule = !ElrsTelem\.nModuleInfo && ElrsTelem\.framesOk && ElrsModulePings < ElrsCrsf::PING_TRIES;', GR)
            and re.search(r'if \(\(askNames \|\| askModule\) && \(uint32_t\)\(now - ElrsPingMs\) >= ElrsCrsf::PING_EVERY_MS && !ElrsOtherLen\)', GR)):
        problems.append('ElrsCrsf.h: "who is there?" only on the ground and a few times: while a model is heard, until its flight controller has answered; and until the module has said how many settings it has')
    # THE MODULE'S SETTINGS ARE ONLY READ (14 Nov 2026): no frame that writes one is ever built, a request goes only on the ground
    # and in the timer's one place for a frame that is not the channels, and the log's lines only then too
    # A SETTING OF THE MODULE'S IS WRITTEN IN ONE PLACE ONLY: the ground's routine (so never while the model may fly), when a
    # change has been asked for on the page, no reading is in hand and the timer's place is free; and a change not yet written
    # when the model may fly is DROPPED, not kept for later
    if nocom(drv).count('buildParamWrite(') != 1 or nocom(GR).count('buildParamWrite(') != 1 or re.search(r'0x2D|PARAMETER_WRITE', nocom(drv)): problems.append('ElrsCrsf.h: a setting of the module\'s is written in one place only, in the ground\'s routine')
    if not re.search(r'if \(ElrsChangeStep == 1 && \(\(uint32_t\)\(now - ElrsChangeAskedMs\) > ELRS_CHANGE_ASK_MS \|\| ElrsChange >= ElrsCrsf::SET_COUNT \|\| \(ElrsCrsf::needsNoModel\(ElrsChange\) && ElrsState\.green\)\)\)\s*\{\s*ElrsChangeStep = 0;\s*ElrsChangeResult = 2;\s*\}\s*else if \(ElrsChangeStep == 1 && !ElrsOtherLen && !list\.ready && \(!ElrsListBegun \|\| list\.done\) && ElrsSet\[ElrsChange\]\.known\)\s*\{\s*uint8_t f\[ElrsCrsf::PARAM_FRAME_LEN\];\s*const uint8_t number = ElrsSet\[ElrsChange\]\.number;\s*if \(ElrsChange == ElrsCrsf::SET_RATE \|\| ElrsChange == ElrsCrsf::SET_SWITCH\)\s*\{[^}]*\}\s*ElrsCrsf::buildParamWrite\(f, number, ElrsChangeTo\);', nocom(GR)):
        problems.append('ElrsCrsf.h: a change is written only when one was asked for, no reading is in hand, the timer\'s place is free and the module has named the setting - and is dropped when its time has run out, or a model has connected since (the rate, the switch mode)')
    if not re.search(r'if \(ElrsChangeStep == 1 \|\| \(ElrsChangeInBox && tookBack\)\)\s*\{\s*if \(ElrsChangeInBox\)\s*ElrsListWanted = true;\s*ElrsChangeStep = 0;\s*ElrsChangeResult = 2;\s*\}\s*else if \(ElrsChangeInBox\)\s*ElrsChangeMs = now;\s*ElrsChangeInBox = false;', nocom(S)):
        problems.append('ElrsCrsf.h: a change asked for and NOT YET WRITTEN when the model may fly is dropped, never done later; one whose frame had gone is read back on the ground (not called "kept" unread)')
    if not re.search(r'if \(!taken && \+\+ElrsChangeReads < ELRS_CHANGE_READS\)\s*\{\s*ElrsChangeStep = 2;\s*ElrsChangeMs = now;\s*\}', nocom(GR)): problems.append('ElrsCrsf.h: a change the module does not yet say is read back again before "kept" is said')
    SV, EV = body('StartElrsView') or '', body('EndElrsView') or ''
    if not re.match(r'\s*if \(CurrentView != RXSETUPVIEW1\)\s*return;\s*ReadRXOptionsView\(\);\s*SaveOneModel\(ModelNumber\);', nocom(SV)) or not re.match(r'\s*if \(CurrentView != ELRSVIEW\)\s*return;', nocom(EV)):
        problems.append('ElrsCrsf.h: the settings page is opened ONLY from Model options (a second tap served on another page would read that page\'s boxes as Model options\' and zero them), its values read and saved first; and left only from itself')
    if 'DMAMEM static ElrsCrsf::Setting' in drv or 'static ElrsCrsf::Setting ElrsSet[ElrsCrsf::SET_COUNT];' not in drv: problems.append('ElrsCrsf.h: the four settings are not kept in RAM2 (it is not given its initial values at the start)')
    if re.search(r'offeredPlace\(|offeredRank\(', nocom(drv)) or nocom(drv).count('ElrsCrsf::pagePlace(') != 2 or nocom(drv).count('ElrsCrsf::pageRank(') != 1: problems.append('ElrsCrsf.h: the picker\'s wheel and its OK use the page\'s own choices (no telemetry "Off" or "Race")')
    if nocom(drv).count('ElrsChangeStep = 1;') != 1 or 'ElrsChangeStep = 1;' not in (body('ElrsPickOk') or ''): problems.append('ElrsCrsf.h: a change is asked for in one place only: the picker\'s OK')
    PK = body('ElrsPickOk') or ''
    if not re.search(r'if \(st\.known && !st\.cut && place != 255 && place != st\.value && !ElrsMayFly\(\) && !ElrsChangeStep && !\(ElrsCrsf::needsNoModel\(k\) && ElrsState\.green\)\)', PK): problems.append('ElrsCrsf.h: the picker\'s OK asks for a change only of a setting the module named in full, to a choice it offers and has not already, on the ground, one at a time - and the rate and the switch mode only with no model connected')
    if nocom(GR).count('ElrsOtherLen = ElrsCrsf::PARAM_FRAME_LEN;') != 2 or 'ElrsListInBox = true;' not in GR or not re.search(r'else if \(ElrsListBegun && !list\.done && !ElrsOtherLen\)', GR) or 'Serial6.write' in GR:
        problems.append('ElrsCrsf.h: a request for a setting goes by the timer\'s one place for another frame, when it is free - never written from loop()')
    if not re.search(r'if \(ElrsListInBox && !ElrsOtherLen\)\s*\{\s*ElrsListInBox = false;\s*list\.sentAt\(now\);', nocom(GR)): problems.append('ElrsCrsf.h: the half second for an answer runs from when the request went out, not from when it was left for the timer')
    # the link ended: the timer first, then the line let go, the power off
    e0, e1, e2 = E.find('ElrsTimer.end();'), E.find('Serial6.end();'), E.find('pinMode(ElrsLinePin, INPUT);')
    if not (0 <= e0 < e1 < e2) or 'digitalWriteFast(ElrsCrsf::POWER_PIN, LOW);' not in E: problems.append('ElrsCrsf.h: ending the link = the timer stopped, then the line let go, and the power off')
    # Serial6.end() rewrites the function of Serial6's RECEIVE pin too (pin 25, a switch's): put back as the transmitter set it
    e3 = E.find('pinMode(SWITCH7, INPUT_PULLUP);')
    if not (e1 < e3) or e3 < 0 or not re.search(r'#define SWITCH7 25\b', defs) or 'pinMode(SwitchNumber[i], INPUT_PULLUP);' not in main: problems.append('ElrsCrsf.h: after Serial6.end() the switch pin 25 (SWITCH7, Serial6\'s receive pin) must be put back to INPUT_PULLUP, as InitSwitchesAndTrims sets it')
if re.search(r'pinMode|digitalWrite', BLOCK): problems.append('ElrsCrsf.h: the tested block must not touch a pin')
# the echo is named in the log, and so is every byte the line gave, the timing frames, and what kinds of frame came
for want in ('own echo %lu', 'ElrsTelem.ownEcho', 'bytes in %lu', '++ElrsBytesIn', 'timing frames %lu', 'frames by kind'):
    if want not in drv: problems.append('ElrsCrsf.h: the log must have "' + want + '"')
# the other files' parts, each as it must stand (and each #else the transmitter as it was)
if not re.search(r'void SimplePing\(\)\s*\{\s*#ifdef ELRS_TEST[^\n]*\n\s*if \(ElrsCarries\(\)\)\s*\n\s*return;\s*\n#endif', trx): problems.append('transceiver.h: SimplePing must say nothing for an ELRS model')
if not re.search(r'uint16_t GetSuccessRate\(\)\s*\{\s*#ifdef ELRS_TEST[^\n]*\n\s*if \(ElrsCarries\(\)\)\s*\n\s*return ElrsQuality\(\);\s*\n#endif', util): problems.append('Utilities.h: the quality bar must show the module\'s figure for an ELRS model')
if 'static bool ElrsSetupDone = false;' not in hdr or 'bool ElrsFlies() { return ElrsSetupDone && (ElrsOn || ElrsModel); }' not in hdr or 'void ElrsSetupOver() { ElrsSetupDone = true; }' not in hdr \
        or hdr.count('ElrsSetupDone = ') != 2 or not re.search(r'FASTRUN bool ElrsLink\(\)\s*\{\s*if \(!ElrsSetupDone\)\s*\{\s*if \(!ElrsModel\)\s*return false;\s*NewCompressNeeded = false;\s*return true;\s*\}', re.sub(r'//[^\n]*', '', hdr)):
    problems.append('ElrsCrsf.h: nothing of the module\'s before setup() is over - ElrsLink returns at once (LDRC silent for an ELRS model), ElrsFlies() is false, and only ElrsSetupOver() ends it')
if not re.search(r'Look\(TXBuildAge\);\s*StashPendingEventBytes\(\);[^\n]*\n\s*ScreenStartupOver = true;[^\n]*\n#ifdef ELRS_TEST[^\n]*\n\s*ElrsSetupOver\(\);\s*#endif\s*\}', src('src/main.cpp')): problems.append('main.cpp: setup() must end with the guarded ElrsSetupOver()')
# THE MODULE'S POWER AT ONCE (the sixth review, 14 Nov 2026): setup() switches it on for a model set to ELRS as soon as the pins are set - the module
# starts while setup goes on - and the link's beginning does not switch it "on" again (the moment stands, the line may start at once)
_h = re.sub(r'//[^\n]*', '', hdr)
if not re.search(r'FLASHMEM void ElrsPowerEarly\(\)\s*\{\s*if \(ElrsModel && !ElrsPowered\)\s*ElrsPowerOn\(\);\s*\}', _h) or not re.search(r'Connected = false;\s*if \(!ElrsPowered\)\s*ElrsPowerOn\(\);\s*\}', _h) or _h.count('ElrsPowerOn();') != 3:
    problems.append('ElrsCrsf.h: ElrsPowerEarly() powers an ELRS model\'s module in setup(); ElrsBegin and the line\'s start power it only if it is not powered yet')
if not re.search(r'InitRadio\(DefaultPipe\);\s*#ifdef ELRS_TEST[^\n]*\n\s*ElrsPowerEarly\(\);\s*#endif\s*delay\(WARMUPDELAY\);', src('src/main.cpp')) or src('src/main.cpp').count('ElrsPowerEarly();') != 1:
    problems.append('main.cpp: setup() must call the guarded ElrsPowerEarly() once, right behind InitRadio (the pins are set, the model is known)')
if not re.search(r'#ifdef ELRS_TEST[^\n]*\n\s*if \(\(\(ModelMatched && BoundFlag\) \|\| ElrsFlies\(\)\) && !ModelMemoryBusy\)\s*\n#else\s*\n\s*if \(ModelMatched && BoundFlag && !ModelMemoryBusy\)[^\n]*\n#endif', util): problems.append('Utilities.h: DelayWithDog must keep an ELRS model\'s frames going, heard or not')
if not re.search(r'#ifdef ELRS_TEST[^\n]*\n\s*!ReceiverUpdateBusy\(\) && CurrentMode == NORMAL && !ElrsCarries\(\);\s*\n#else\s*\n\s*!ReceiverUpdateBusy\(\) && CurrentMode == NORMAL;\s*\n#endif', msign): problems.append('Motor_sign.h: an ELRS model is not held back')
if not re.search(r'#ifdef ELRS_TEST[^\n]*\n\s*ElrsOptionShow\(\);\s*\n#endif', menu) or not re.search(r'const uint32_t lostBefore = BoxesLost;\s*\n\s*const uint32_t six = GetValue\(\(char \*\)"c3"\);[^\n]*\n#ifdef ELRS_TEST[^\n]*\n\s*const uint32_t elrs = GetValue\(\(char \*\)"c4"\);\s*\n#endif\s*\n\s*if \(BoxesLost == lostBefore\)\s*\{\s*if \(six <= 1\)\s*SixBanksSet\(six == 1\);\s*\n#ifdef ELRS_TEST[^\n]*\n\s*ElrsOptionSet\(elrs\);\s*\n#endif\s*\}', menu) or menu.count('SixBanksSet(six == 1)') != 1 or menu.count('ElrsOptionSet(') != 1: problems.append('MenuOptions.h: Model options must show the switch, and read it with its own last boxes (asked first, set only when every box had its answer)')
if "vis l_t6,1" not in drv or "vis c4,1" not in drv or not re.search(r'FLASHMEM void ElrsOptionSet\(uint32_t v\)[^\n]*\n\{\s*\n\s*if \(v <= 1\)[^\n]*\n\s*ElrsModel = \(v == 1\);\s*\n\}', drv) or 'GetValue((char *)"c4")' in drv: problems.append('ElrsCrsf.h: the switch is c4 with its label l_t6, shown by this code; its answer is asked by Model options (not here), and a reply that never came changes nothing')
if not re.search(r'bool ElrsModel = false;', defs) or not re.search(r'#define ELRS_MODEL_FLAG 2\b', defs): problems.append('1Definitions.h: a model is LDRC unless its record says ELRS (bit 1)')
if not re.search(r'SixBanks = false;[^\n]*\n#ifdef ELRS_TEST[^\n]*\n\s*ElrsModel = false;\s*\n#endif', main): problems.append('main.cpp: a new model\'s receiver is LDRC')
if not re.search(r'#else\s*\n\s*if \(MaxRangeNarrow \|\| curves \|\| had2 \|\| size > a \|\| SixBanks\)\s*\n#endif', sdc) or not re.search(r'#else\s*\n\s*if \(SixBanks \|\| hadC7\)\s*\n\s*\{\s*\n\s*const uint8_t flags = SixBanks \? 1 : 0;\s*\n#endif', sdc): problems.append('SDcard.h: each #else must be the transmitter as it was')
# ---- THE DRIVER ITSELF, RUN ON THE MAC (13 Nov 2026, after the review found what reading the text had not: with LDRC's
# SendData no longer running for an ELRS model, the channels were worked out once and never again). The whole of ElrsCrsf.h
# is compiled with -DELRS_TEST beside the transmitter's OWN routines, lifted from its files as they stand - GetNewChannelValues,
# FixMotorChannel, FixArmingChannel, GetBank, MotorEnabledHasChanged, EnsureMotorIsOff, RedLedOn, GreenLedOn,
# ClearMostParameters, DelayWithDog, GetYesOrNo - over a clock, a serial port, a timer and a module that are made up here.
# Then the bench's day is played through, a millisecond a pass, and every frame the timer "sends" is read back.
def lift_fn(text, head):
    lines = text.split('\n')
    for a_, l in enumerate(lines):
        if l.startswith(head):
            for b_ in range(a_ + 1, len(lines)):
                if lines[b_] == '}': return '\n'.join(lines[a_:b_ + 1]) + '\n'
    raise SystemExit('cannot lift ' + head)
msign_src = src('include/Motor_sign.h')
SIM = r'''
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <string>
#define FLASHMEM
#define FASTRUN
#define DMAMEM
#define PSTR(x) x
#define CRUMB(x)
bool RfVerifyFollows();   // (e99e, 18 Nov 2026: Motor_sign.h asks it - defined below)
#define INPUT 0
#define OUTPUT 1
#define INPUT_PULLUP 2
#define HIGH 1
#define LOW 0
#define SERIAL_8N1_HALF_DUPLEX 0x200
#define ELRS_MODEL_FLAG 2
#define SWITCH7 25
#define CHANNELSUSED 16
#define NORMAL 0
#define CALIBRATELIMITS 1
#define LISTENMODE 6
#define SAVE_RF_SETTINGS 7
#define RESTORE_RF_SETTINGS 8
#define FRONTVIEW 1
#define RXSETUPVIEW1 9
#define ELRSVIEW 90
#define ELRSPICKVIEW 91
#define RED_LED_ON_TIME 3000
#define GREENLED 1
#define BLUELED 2
#define REDLED 3
enum { WHAHWHAHMSG = 25, CONNECTEDMSG = 20, DISCONNECTEDMSG = 21, MOTORON = 30, MOTOROFF = 31, PLSTURNOFF = 32 };
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)

// ---------------------------------------------------------------- a clock, a timer, a serial port, pins: made up
static uint32_t fakeMs = 5000; static double nowUs = 0;
uint32_t millis() { return fakeMs; }
void noInterrupts() {}
void interrupts() {}
static int pinModes[64], pinLevels[64]; static uint32_t pin10HighMs = 0;
void pinMode(int p, int m) { pinModes[p] = m; }
void digitalWriteFast(int p, int v) { pinLevels[p] = v; if (p == 10 && v == HIGH) pin10HighMs = fakeMs; }
void analogWrite(int, int) {}
struct IntervalTimer {
    void (*fn)() = nullptr; uint32_t periodUs = 0, pendingUs = 0; double nextUs = 0; int begins = 0, ends = 0;
    bool begin(void (*f)(), uint32_t us) { fn = f; periodUs = us; nextUs = nowUs + us; ++begins; return true; }
    void end() { fn = nullptr; ++ends; }
    void update(uint32_t us) { pendingUs = us; }
};
// IN THE AIR, by the play's own word (a scene says when the model takes off and when it is down again): whatever is
// written to the card then, and whatever is sent that is not the channels, is counted - and must be nothing at the end.
static bool airborne = false; static int cardWritesInAir = 0, otherInAir = 0;
struct FakeSerial {
    bool open = false; int begins = 0, ends = 0, clears = 0, mem = 0; uint32_t beginMs = 0; bool timerRanAtEnd = false;
    std::vector<uint8_t> in; size_t inPos = 0;
    std::vector<std::vector<uint8_t>> out; std::vector<uint32_t> outMs;
    void addMemoryForRead(void *, size_t) { ++mem; }
    void begin(uint32_t, uint32_t) { open = true; ++begins; beginMs = fakeMs; }
    void end();
    void clear() { in.clear(); inPos = 0; ++clears; }
    int available() { return open ? (int)(in.size() - inPos) : 0; }
    int read() { return in[inPos++]; }
    int availableForWrite() { return 39; }
    size_t write(const uint8_t *b, size_t n) { if (airborne && !(n == 26 && b[2] == 0x16)) ++otherInAir; out.emplace_back(b, b + n); outMs.push_back(fakeMs); return n; }
    void feed(const uint8_t *b, size_t n) { if (open) in.insert(in.end(), b, b + n); }
} Serial6;

// ---------------------------------------------------------------- the transmitter's own names, as its routines need them
bool ElrsModel = false; bool ElrsCarries(); bool ElrsFlies(); void ElrsSetupOver(); bool ElrsLink(); uint16_t ElrsQuality(); void ElrsOptionShow(); void ElrsOptionSet(uint32_t v);
uint16_t SendBuffer[CHANNELSUSED + 1], PreviousBuffer[CHANNELSUSED + 1], BuddyBuffer[CHANNELSUSED + 1], ShownBuffer[CHANNELSUSED + 1], RawDataBuffer[CHANNELSUSED + 1], LastBuffer[CHANNELSUSED + 1], PreMixBuffer[CHANNELSUSED + 1];
bool NewCompressNeeded = true, SendNoData = false, BindingEnabled = false, LedIsBlinking = false, MotorEnabled = false, MotorWasEnabled = false, Connected = false;
bool LedWasGreen = false, LedWasRed = false, BoundFlag = false, ModelMatched = false, UsingDefaultPipeAddress = true, DontChangePipeAddress = false;
bool LostContactFlag = true, AnnounceConnected = true, UseLog = false, First_RPM_Data = true, RXVoltsDetected = false, ModelIdentified = false, VersionsCompared = false;
bool BuddyPupilOnWireless = false, BuddyHasAllSwitches = false, FlightRestart = false, FlightRestartElrsCarried = false, UseMotorKill = true, SafetyON = false, SafetyWasOn = false, Armed = false, Force_Early_Sound = false;
bool Reconnected = false, ForceVoltDisplay = false, AnnounceBanks = false, BlockBankChanges = false, SafetyHold = false;
#define MODELSVIEW 5   // (e100b, 18 Nov 2026: Motor_sign.h MotorEnabledHasChanged puts the Models page's earlier model back - never here: no Models page; dev/test_modelsarmed runs it)
uint32_t PreviousModelNumber = 3; static int modelReads = 0; static bool ReadOneModel(uint32_t) { ++modelReads; return true; }
bool RfVerifyPending() { return false; } bool RfVerifyFollows() { return false; } bool CopyBankRunning() { return false; } bool EasyHoldsBanks() { return false; }   // (e99c, 17 Nov 2026: Motor_sign.h MotorEnabledHasChanged asks them - no save, no copy, no Easy tuning here)
bool Reading_PIDS_Now = false, Reading_PIDS_Advanced_Now = false, Reading_RATES_Now = false, Reading_RATES_Advanced_Now = false, Reading_GOV_Now = false, Reading_GOV_Config_Now = false;
uint8_t Connect_MMmsg = 0, ParametersToBeSentPointer = 0, RotorFlight_V = 0, RXCellCount = 6, CurrentMode = NORMAL, CurrentView = FRONTVIEW, MotorChannel = 4, MotorChannelZero = 30, ArmingChannel = 6, BuddyState = 0, Bank = 1, PreviousBank = 1, ModalWaits = 0;
float RotorFlight_Version = 0;
uint16_t RecentGoodPacketsCount = 0, LastConnectionQuality = 0;
uint32_t LastPacketSentTime = 0, LedGreenMoment = 0, LastShowTime = 0, TotalGoodPackets = 0, LogLineNumber = 0, RXSuccessfulPackets = 0, TotalLostPackets = 0, RecentPacketsLost = 0, TotalPacketsAttempted = 0, GapStart = 0, ThisGap = 0;
uint32_t MotorStartTime = 0, PausedSecs = 0, MotorOnSeconds = 0, LastSeconds = 0, MacHalfSeen[2] = {0, 0}; uint8_t MacHalfStable = 0;
char ReceiverVersionNumber[20] = "", TextFileName[20] = "", LogWriteName[20] = "", TxName[20] = "Owner", na[] = "---", Confirmed[2] = "?", WarnNow[] = "vis Warning,1", WarnOff[] = "vis Warning,0", Warning[] = "Warning", err_MotorOn[] = "MOTOR IS ON!", pFrontView[] = "page FrontView";
union { uint64_t Val64; uint32_t Val32[2]; } ModelsMacUnion;
struct Payload { uint8_t Ack_Payload_byte[6]; } AckPayload;
static bool armingManaged = false; bool ArmingManaged() { return armingManaged; }
uint16_t IntoHigherRes(uint8_t) { return 1000; }                      // "motor off" in microseconds, for this play (CRSF carries 988 to 2012)
int GetLEDBrightness() { return 100; }
bool ReceiverUpdateBusy() { return false; }

// ---------------------------------------------------------------- what the routines call, noted or made harmless
static std::vector<std::string> logLines, texts; static std::vector<int> sounds; static int greenCalls = 0, redCalls = 0, boxes = 0, ldrcPackets = 0, fronts = 0;
void LogText(char *t, uint16_t n, bool) { if (airborne) { ++cardWritesInAir; fprintf(stderr, "  (written to the card in the air: %.70s)\n", t); } logLines.emplace_back(t, n); }      // a write to the card
static int deferredN = 0; static std::vector<std::string> deferred;
void DeferLogText(const char *t, bool) { ++deferredN; deferred.emplace_back(t); logLines.emplace_back(std::string(t).substr(0, 36)); }   // kept, cut to its room, for the transmitter's quiet moment: no card now
static bool safetyDefined = false;                                     // (the play begins with a transmitter that has no safety switch; the last scenes have one)
bool SafetyIsDefined() { return safetyDefined; }
bool SafetyIsOff() { return safetyDefined && !SafetyON; }
void SendCommand(char *c) { texts.emplace_back(c); }
void SendText(char *box, char *w) { texts.emplace_back(std::string(box) + "=" + w); }
void SendValue(char *box, int v) { texts.emplace_back(std::string(box) + "=" + std::to_string(v)); }
static uint32_t valueC4 = 65535, valueList = 65535; uint32_t GetValue(char *n) { return strcmp(n, "list") ? valueC4 : valueList; }
char ModelName[] = "B Thundr1"; static int optionsRead = 0, optionsShown = 0, modelsSaved = 0; uint32_t ModelNumber = 3;
void SaveOneModel(uint32_t) { ++modelsSaved; }
void ReadRXOptionsView() { ++optionsRead; }                            // (Model options' values into memory)
void RXOptionsViewStart() { ++optionsShown; CurrentView = RXSETUPVIEW1; }
void PlaySound(uint16_t s) { sounds.push_back(s); }
void PerfSilent() {}
void LogDisConnection() {} void LogConnection() {} void NoteConnectionLost() {} void RfModelGone() {} void ShowComms() {} void SafetyOffAtConnect() {} void ResetMotorTimer() {}
void SendInitialSetupParams() { ParametersToBeSentPointer = 5; }      // (an LDRC receiver's settings, queued at every connection)
void LogFrontPageReason(const char *, const char *, const char * = nullptr) {} void GotoFrontView() { ++fronts; } void ShowMotor() {} void LogMotor(int) {} void ShowMotorTimer() {}
void SafetyHoldUpdate() {} void ReadSafetySwitch() {} void ReadBuddySwitch() {} void ReadBankSwitch() {} void ReadDualRateSwitch() {} void SafetySwitchChanged() {} void ReadChannelSwitches9to12() {} void BankHasChanged() {}
void CheckPowerOffButton() {}
// the sticks, the motor switch, and the model (the module's link statistics, 240 ms apart while it "hears" the model)
static uint16_t stick[CHANNELSUSED]; static bool motorSwitchOn = false, modelHeard = false, rampOn = true; static uint32_t lastStatsMs = 0, computes = 0;
void ReadAutoAndMotorSwitch() { MotorEnabled = motorSwitchOn; }
void CheckMotorOff() { MotorEnabled = motorSwitchOn && !SafetyON; }
void GetAllInputs() { ++computes; for (int i = 0; i < CHANNELSUSED; ++i) SendBuffer[i] = stick[i]; }
void MixInputs() {} void CalculateAllOutputs() {} void SlowAnyServos() {} void MixOutputs() {} void DoTrimsAndSubtrims() {} void RerouteOutputs() {} void ServoReverse() {}
static IntervalTimer *theTimer = nullptr;
static const uint8_t LINKSTATS[] = ''' + carr(link_elrs) + r''';
static void (*boxHook)() = nullptr; static uint32_t boxAnswerAtMs = 0;
static void stopThePlay(const char *why);
// THE MODULE ITSELF, for the play: it answers "who is there?" with its name and how many settings it has (none, until a
// scene says otherwise), and each request for a piece of one as ExpressLRS 3.6.4 does - the pieces are this test's own,
// built from the rules of its code (PARAMS above). It counts what it is asked, and above all anything WRITTEN to it.
static std::vector<std::vector<uint8_t>> PDATA = ''' + PDATA_C + r''';     // each setting's data, whole (a change is made in it)
static const std::vector<int> PVAL_AT = ''' + PVAL_AT + r''';                 // where a choice's value stands in its data
static const std::vector<int> RATE_FULL = ''' + RATE_FULL + r''';
static const std::vector<uint8_t> P3_STD = ''' + P3_STD + r''', P3_FULL = ''' + P3_FULL + r''';
static const std::vector<uint8_t> INFO_NONE = ''' + carr(info_mod) + r''', INFO_N = ''' + carr(info_mod_n) + r''';
static const uint8_t TIMING_OK[] = ''' + carr(timing_ok) + r''';
static bool moduleLists = false, moduleDeaf = false, moduleKeepsNext = false; static int moduleDropNth = 0, moduleReads = 0, moduleAnswered = 0, moduleWrites = 0, moduleTook = 0, moduleKept = 0, moduleOddWrites = 0, modulePings = 0;
static uint32_t moduleDelayMs = 6, moduleTimingMs = 0; static size_t moduleSeen = 0; static int lastWriteNumber = -1, lastWriteValue = -1;
static std::vector<std::pair<uint32_t, std::vector<uint8_t>>> moduleDue;
static size_t modulePieces(unsigned n) { return (PDATA[n - 1].size() + 55) / 56; }
static uint8_t moduleCrc(const uint8_t *d, size_t n) { uint8_t c = 0; for (size_t i = 0; i < n; ++i) { c ^= d[i]; for (int b = 0; b < 8; ++b) c = (uint8_t)((c & 0x80) ? ((c << 1) ^ 0xD5) : (c << 1)); } return c; }   // (its own: not the driver's)
static std::vector<uint8_t> modulePiece(unsigned n, unsigned c) {      // as lua.cpp sendCRSFparam cuts it: 56 bytes of data a frame
    const std::vector<uint8_t> &d = PDATA[n - 1]; const size_t total = modulePieces(n), from = (size_t)c * 56, to = std::min(d.size(), from + 56);
    std::vector<uint8_t> f = {0xEA, (uint8_t)(to - from + 6), 0x2B, 0xEA, 0xEE, (uint8_t)n, (uint8_t)(total - 1 - c)};
    f.insert(f.end(), d.begin() + (long)from, d.begin() + (long)to);
    f.push_back(moduleCrc(&f[2], f.size() - 2));
    return f;
}
// A change, by tx_devLUA.cpp's rules: the telemetry ratio, the power and the packet rate at any time; the switch mode only
// with no model connected. A packet rate of the other kind (Full or not) KEEPS THE SWITCH MODE'S NUMBER, which then means
// another mode: 0 Wide / 8ch, 1 Hybrid / 16ch Rate/2 (from 2, 12ch Mixed, it goes to 0).
static uint32_t moduleSlowMs = 0; static std::vector<std::pair<uint32_t, std::pair<unsigned, unsigned>>> moduleLater;
static int valueAt(const std::vector<uint8_t> &d) { int at = 2; while (d[(size_t)at]) ++at; ++at; while (d[(size_t)at]) ++at; return at + 1; }
// THE TRUTH, for the storm at the end of the play: does the module's switch mode, as it stands this millisecond, carry channel 5
// whole? ("16ch Rate/2": the second choice of the Full rates' list.) Noted with its time whenever the module's settings change.
static bool moduleCarries() { const std::vector<uint8_t> &d = PDATA[2]; static const char w[] = "16ch Rate/2"; return std::search(d.begin(), d.end(), w, w + 11) != d.end() && d[(size_t)valueAt(d)] == 1; }
static std::vector<std::pair<uint32_t, bool>> truthLog;
static void truthNote() { truthLog.push_back({fakeMs, moduleCarries()}); }
static void moduleSet(unsigned n, unsigned v) {
    std::vector<uint8_t> &d = PDATA[n - 1];
    if (n == 1) {
        const bool was = RATE_FULL[d[(size_t)valueAt(d)]] != 0, is = RATE_FULL[v] != 0;
        if (was != is) { const uint8_t sw = PDATA[2][(size_t)valueAt(PDATA[2])]; PDATA[2] = is ? P3_FULL : P3_STD; PDATA[2][(size_t)valueAt(PDATA[2])] = (uint8_t)(sw > 1 ? 0 : sw); }
    }
    d[(size_t)valueAt(d)] = (uint8_t)v;
    truthNote();
}
static void moduleWrite(unsigned n, unsigned v) {
    ++moduleWrites; lastWriteNumber = (int)n; lastWriteValue = (int)v;
    if (n < 1 || n > PDATA.size() || PVAL_AT[n - 1] < 0) { ++moduleOddWrites; return; }
    std::vector<uint8_t> &d = PDATA[n - 1];
    int at = 2; while (d[(size_t)at]) ++at; ++at; while (d[(size_t)at]) ++at; ++at;     // past its name and its choices: its value (the switch modes' list changes with the rate's family)
    if (moduleKeepsNext || v > d[(size_t)at + 2]) { moduleKeepsNext = false; ++moduleKept; return; }
    if (n == 3 && modelHeard) { ++moduleKept; return; }
    if (n == 1 && modelHeard && PDATA[2][(size_t)valueAt(PDATA[2])] > 1 && !RATE_FULL[v]) { ++moduleKept; return; }   // (from 12ch Mixed to a rate that has no such mode: only with no model connected)
    if (n != 1 && n != 2 && n != 3 && n != 7) { ++moduleOddWrites; return; }
    ++moduleTook;
    if (moduleSlowMs) { moduleLater.push_back({fakeMs + moduleSlowMs, {n, v}}); return; }     // (it says the new value only once it has told the receiver and saved it)
    moduleSet(n, v);
}
static void moduleStep() {
    for (; moduleSeen < Serial6.out.size(); ++moduleSeen) {
        const std::vector<uint8_t> &f = Serial6.out[moduleSeen];
        if (f.size() == 8 && f[2] == 0x2D && f[3] == 0xEE && f[4] == 0xEA) moduleWrite(f[5], f[6]);
        else if (f.size() >= 3 && f[2] == 0x2D) { ++moduleWrites; ++moduleOddWrites; }
        if (f.size() == 6 && f[2] == 0x28) { ++modulePings; moduleDue.push_back({fakeMs + 6, moduleLists ? INFO_N : INFO_NONE}); }
        else if (f.size() == 8 && f[2] == 0x2C && f[3] == 0xEE && f[4] == 0xEA) {
            ++moduleReads;
            const unsigned n = f[5], c = f[6];
            if (moduleDeaf || (moduleDropNth && moduleReads % moduleDropNth == 0)) continue;
            if (n >= 1 && n <= PDATA.size() && c < modulePieces(n)) { ++moduleAnswered; moduleDue.push_back({fakeMs + moduleDelayMs, modulePiece(n, c)}); }
        }
    }
    if (moduleLists && fakeMs - moduleTimingMs >= 200) { moduleTimingMs = fakeMs; Serial6.feed(TIMING_OK, sizeof TIMING_OK); }
    for (size_t i = 0; i < moduleLater.size();) { if (fakeMs >= moduleLater[i].first) { moduleSet(moduleLater[i].second.first, moduleLater[i].second.second); moduleLater.erase(moduleLater.begin() + (long)i); } else ++i; }
    for (size_t i = 0; i < moduleDue.size();) {
        if (fakeMs >= moduleDue[i].first) { Serial6.feed(moduleDue[i].second.data(), moduleDue[i].second.size()); moduleDue.erase(moduleDue.begin() + (long)i); }
        else ++i;
    }
}
static void tick1ms() {
    ++fakeMs; nowUs += 1000;
    if (fakeMs > 12000000u) stopThePlay("its clock ran away (a wait that never ends)");
    if (rampOn) { stick[0] = (uint16_t)(1000 + (fakeMs % 1000)); stick[1] = (uint16_t)(2000 - (fakeMs % 1000)); }
    if (modelHeard && fakeMs - lastStatsMs >= 240) { lastStatsMs = fakeMs; Serial6.feed(LINKSTATS, sizeof LINKSTATS); }
    while (theTimer && theTimer->fn && nowUs >= theTimer->nextUs) {
        theTimer->nextUs += theTimer->periodUs;
        if (theTimer->pendingUs) { theTimer->periodUs = theTimer->pendingUs; theTimer->pendingUs = 0; }
        theTimer->fn();
    }
    moduleStep();
}
void KickTheDog() { tick1ms(); if (boxHook) boxHook(); }               // (every wait of the transmitter's kicks the dog: time passes there)
void CheckForNextionButtonPress() { if (boxAnswerAtMs && fakeMs >= boxAnswerAtMs) { Confirmed[0] = 'Y'; boxAnswerAtMs = 0; } }
uint8_t ModelMemoryBusy = 0;   // (B211: 1Definitions.h - nothing is flown from a memory that is being read into; dev/test_modelmemory)
uint8_t ScreenRestartSeen = 0; uint16_t ScreenMarkCount = 0; bool InsideDelayWithDog = false, NextionGetPending = false, ScreenAnswerOwed = false, ScreenSaysPage = false; uint16_t ScreenPageSaidCount = 0; void NoteQuestionClosed(uint8_t) {} void ScreenAskPage() {} void ScreenOwesAnswer() {} void ScreenOwedStep() {} bool QuestionClosedItself = false, QuestionOvertaken = false;
#define QUESTION_ASK_MS 1000
#define QUESTION_SILENT_MS 3500   // (B211, Nextion.h: a question that waits when the SCREEN restarts, or
static bool ScreenCaughtUp() { return false; } void ScreenHasRestarted() {} void StashPendingEventBytes() {} void delayMicroseconds(int) {}   //  is covered by another page, is closed - dev/test_stalepress and dev/test_noanswer are its tests)
void GetNewChannelValues(); void FixMotorChannel(); void FixArmingChannel(); void DelayWithDog(uint32_t); void GetYesOrNo(uint16_t asked = 0); void RedLedOn(); void GreenLedOn(); void SendData();
static void stopThePlay(const char *why) { fprintf(stderr, "FAIL the play was stopped: %s\n", why); printf("%d checks, %d failures (and the play stopped)\n", checks, fails + 1); exit(1); }
void MsgBox(char *, char *) { if (++boxes > 12) stopThePlay("the transmitter's box came again and again (the motor switch never seen off?)"); if (!boxAnswerAtMs) boxAnswerAtMs = fakeMs + 2000; GetYesOrNo(); }
static std::vector<std::pair<uint8_t, std::vector<uint8_t>>> items;
void ParseTelemetryItem() {                                           // (what the transmitter's own telemetry code is handed; and its word on Rotorflight)
    const uint8_t id = AckPayload.Ack_Payload_byte[0];
    items.emplace_back(id, std::vector<uint8_t>(AckPayload.Ack_Payload_byte + 1, AckPayload.Ack_Payload_byte + 5));
    if (id == 31 && AckPayload.Ack_Payload_byte[1]) { RotorFlight_V = AckPayload.Ack_Payload_byte[1]; RotorFlight_Version = 2.3f; }
}
void FakeSerial::end() { timerRanAtEnd = theTimer && theTimer->fn; open = false; ++ends; in.clear(); inPos = 0; }
// LDRC's own SendData, as far as this play needs it: the ELRS part first (the real file's first lines - read by the text checks
// above), else a "packet" at its pace, which is what lets the channels be worked out again
void SendData() {
    if (ElrsLink()) return;
    if ((millis() - LastPacketSentTime) < 2) return;
    LastPacketSentTime = millis();
    if (SendNoData || SafetyHold) return;
    ++ldrcPackets; NewCompressNeeded = false;
}
''' + lift_fn(main, 'void ClearMostParameters()') + lift_fn(main, 'FLASHMEM void EnsureMotorIsOff()') + lift_fn(main, 'void RedLedOn()').replace('void RedLedOn() // heer\n{', 'void RedLedOn()\n{\n    ++redCalls;') \
    + lift_fn(main, 'void GreenLedOn()').replace('void GreenLedOn()\n{', 'void GreenLedOn()\n{\n    ++greenCalls;') + lift_fn(main, 'FASTRUN void GetNewChannelValues()') \
    + lift_fn(main, 'void FixMotorChannel()') + lift_fn(main, 'void FixArmingChannel()') + lift_fn(util, 'void DelayWithDog(uint32_t HowLong)') + lift_fn(util, 'FLASHMEM void GetYesOrNo(uint16_t asked)') \
    + lift_fn(msign_src, 'void MotorEnabledHasChanged()') + lift_fn(main, 'void GetBank()') + hdr + r'''
using namespace ElrsCrsf;
// one pass of loop(), a millisecond long: the 20-a-second switch reading, the channels, the motor's and the safety's word, the link
static uint32_t lastBankMs = 0;
static void pass() {
    tick1ms();
    if (fakeMs - lastBankMs >= 50) { lastBankMs = fakeMs; GetBank(); }
    GetNewChannelValues();
    if (CurrentMode == NORMAL) { FixMotorChannel(); FixArmingChannel(); }
    if (CurrentMode == NORMAL) SendData();
}
static void run(int ms) { const uint32_t until = fakeMs + (uint32_t)ms; while ((int32_t)(until - fakeMs) > 0) pass(); }
static int ticksToUs(int t) { return (int)lround((t - 992) * 500.0 / 819.0 + 1500.0); }
static bool isRc(const std::vector<uint8_t> &f) { return f.size() == 26 && f[0] == 0xEE && f[2] == 0x16; }
static int chan(const std::vector<uint8_t> &f, int c) { uint64_t bits = 0; int at = 11 * c, by = 3 + at / 8; for (int k = 0; k < 4; ++k) bits |= (uint64_t)f[by + k] << (8 * k); return ticksToUs((int)((bits >> (at % 8)) & 0x7FF)); }
static size_t mark() { return Serial6.out.size(); }
struct Seen { int rc = 0, other = 0, follow = 0, distinct = 0, motorLow = 0, motorFollows = 0, longestGapMs = 0; };
// the frames sent since a mark: how many, whether channel 1 is the stick of that very moment (within 3 ms: the ramp climbs 1 us a ms),
// how many different values it took, the motor channel held low (1000) or following its stick, the longest silence
static Seen seen(size_t from) {
    Seen s; int last = -1; uint32_t lastMs = from < Serial6.outMs.size() ? Serial6.outMs[from] : 0; std::vector<bool> got(3000, false);
    for (size_t i = from; i < Serial6.out.size(); ++i) {
        const auto &f = Serial6.out[i]; const uint32_t at = Serial6.outMs[i];
        if ((int)(at - lastMs) > s.longestGapMs) s.longestGapMs = (int)(at - lastMs);
        lastMs = at;
        if (!isRc(f)) { ++s.other; continue; }
        ++s.rc;
        const int v = chan(f, 0), want = 1000 + (int)(at % 1000), d = (want - v + 1000) % 1000;
        if (d <= 4) ++s.follow;
        if (v != last && v >= 0 && v < 3000 && !got[v]) { got[v] = true; ++s.distinct; }
        last = v;
        const int m = chan(f, MotorChannel);
        if (abs(m - 1000) <= 1) ++s.motorLow;
        if (abs(m - stick[MotorChannel]) <= 1) ++s.motorFollows;
    }
    return s;
}
static int countSound(int s) { int n = 0; for (int x : sounds) if (x == s) ++n; return n; }
static bool logHas(const char *w) { for (auto &l : logLines) if (l.find(w) != std::string::npos) return true; return false; }
static void motorOffInBox() { if (boxAnswerAtMs && fakeMs + 500 >= boxAnswerAtMs) motorSwitchOn = false; }   // the pilot switches the motor off while the box shows
static bool freeNow() { return ElrsOn && !ElrsHeld; }   // (what the scenes look at: the module has the link and the throttle is NOT held)
int main() {
    theTimer = &ElrsTimer;
    for (int i = 0; i < 64; ++i) pinModes[i] = pinLevels[i] = -1;
    for (int i = 0; i < CHANNELSUSED; ++i) stick[i] = 1500;
    MotorChannel = 3;                                                  // (a model whose throttle is NOT channel 5, for the link's own scenes: a throttle on channel 5 is HELD until the module has said its switch mode - its scenes are further down)
    stick[MotorChannel] = 1700;                                        // the throttle stick up: only the motor switch holds the motor
    // ---- BEFORE setup() IS OVER (its waits call the same code that flies a model through every wait): for a model set to ELRS
    // nothing of the module's begins, not a frame goes, the sticks are not even read - and LDRC says nothing either
    { ElrsModel = true; const int ldrc0 = ldrcPackets; const uint32_t c0 = computes;
      for (int k = 0; k < 40; ++k) DelayWithDog(50);
      CHECK(ElrsCarries() && !ElrsFlies() && Serial6.begins == 0 && ElrsTimer.begins == 0 && Serial6.out.empty() && pinModes[10] == -1 && ldrcPackets == ldrc0 && computes == c0 && redCalls == 0);
      ElrsModel = false; ElrsPowerEarly(); CHECK(pinModes[10] == -1 && pinLevels[10] == -1);   // (setup()'s early power is for a model set to ELRS only: an LDRC model's pin is not touched)
      ElrsSetupOver(); CHECK(!ElrsFlies()); ElrsModel = true; CHECK(ElrsFlies()); ElrsModel = false; }
    // ---- an LDRC model: nothing of ELRS happens, and LDRC goes on as ever
    run(500);
    CHECK(!ElrsCarries() && Serial6.begins == 0 && ElrsTimer.begins == 0 && Serial6.out.empty() && pinModes[10] == -1 && ldrcPackets > 200 && redCalls == 0);
    printf("PASS (the driver run on the Mac) an LDRC model: no line, no timer, no pin touched; LDRC sends as ever\n");
    // ---- the model is set to ELRS (Model options): the link begins once the setting has stood, the power first, the line 0.3 s later
    const int ldrcBefore = ldrcPackets; const uint32_t setAt = fakeMs;
    ElrsModel = true;
    pass(); CHECK(ElrsCarries() && Serial6.begins == 0 && ldrcPackets == ldrcBefore);   // from the first pass the model is the module's (LDRC neither sends nor pings nor holds it back), before the link has begun
    run(1000);
    CHECK(ElrsCarries() && redCalls == 1 && LedWasRed && !LedWasGreen && pinLevels[10] == HIGH && Serial6.begins == 1 && Serial6.mem == 1 && ElrsTimer.begins == 1);
    CHECK(pin10HighMs - setAt >= MODEL_SETTLE_MS && pin10HighMs - setAt <= MODEL_SETTLE_MS + 5);
    CHECK(Serial6.beginMs - pin10HighMs >= POWER_SETTLE_MS && Serial6.beginMs - pin10HighMs <= POWER_SETTLE_MS + 5);       // (found by review: the 0.3 s was skipped)
    CHECK(ldrcPackets == ldrcBefore && logHas("ELRS test: model's receiver is ELRS"));                                           // LDRC's radio: NOT ONE packet from the moment the model is an ELRS one, the settle time included (the yellow, 14 Nov 2026: in that tenth of a second the heli's LDRC receiver answered - "Model memory matched")
    // ---- THE STICKS REACH THE MODULE: 250 frames a second, each with the stick of its own moment (found by review: they did not)
    size_t m0 = mark(); const uint32_t c0 = computes;
    run(2000);
    Seen s = seen(m0);
    CHECK(s.rc >= 498 && s.rc <= 502 && s.other == 0 && s.follow == s.rc && s.distinct >= 240 && s.longestGapMs <= 5);   // (the stick climbs 1 us a ms and begins again each second: 250 values)
    CHECK(computes - c0 >= 1990);                                      // the channels are worked out afresh on every pass
    CHECK(s.motorLow == s.rc);                                         // the motor switch is off: the throttle is held low whatever its stick says
    CHECK(!Connected && !BoundFlag && !ModelMatched && ParametersToBeSentPointer == 0 && ldrcPackets == ldrcBefore);
    printf("PASS the sticks reach the module: %d frames in 2 s, every one with the stick of its own moment (%d different values), the throttle held low by the motor switch; the line started %u ms after the power\n", s.rc, s.distinct, (unsigned)(Serial6.beginMs - pin10HighMs));
    // ---- the model is heard: connected, by the transmitter's own code
    modelHeard = true;
    run(600);
    CHECK(greenCalls == 1 && LedWasGreen && !LedWasRed && BoundFlag && ModelMatched && Connected && !LostContactFlag && ParametersToBeSentPointer == 0);
    CHECK(countSound(CONNECTEDMSG) == 1 && logHas("LINK UP") && ElrsQuality() == 92 && !strcmp(ReceiverVersionNumber, "ELRS"));
    // its telemetry: the battery, head speed and two temperatures, then its name - into the transmitter's own items
    static const uint8_t batt[] = ''' + carr(batt) + r''', rpm[] = ''' + carr(rpm) + r''', temp2[] = ''' + carr(temp2) + r''', infoFc[] = ''' + carr(info_fc) + r''', infoRx[] = ''' + carr(info_rx) + r''';
    items.clear();
    Serial6.feed(batt, sizeof batt); Serial6.feed(rpm, sizeof rpm); Serial6.feed(temp2, sizeof temp2);
    run(50);
    { bool volts = false, temp = false; int rpms = 0; for (auto &it : items) { if (it.first == 5) { float v; memcpy(&v, it.second.data(), 4); volts = fabsf(v - 8.1f) < 0.001f; } if (it.first == 24) { float v; memcpy(&v, it.second.data(), 4); temp = fabsf(v - 62.3f) < 0.001f; } if (it.first == 20) ++rpms; }
      CHECK(volts && temp && rpms == 1 && RotorFlight_Version == 0); }
    // "who is there?" goes out (the motor switch is off, the name not known), in place of one channel frame; the answer is Rotorflight
    m0 = mark(); run(4500); s = seen(m0);
    { int pings = 0; for (size_t i = m0; i < Serial6.out.size(); ++i) { const auto &f = Serial6.out[i]; if (f.size() == 6 && f[0] == 0xEE && f[2] == 0x28 && f[5] == 0x54) ++pings; }
      CHECK(pings >= 1 && pings <= 2 && s.other == pings && s.rc + s.other >= 1123 && s.rc + s.other <= 1127 && s.follow == s.rc && s.longestGapMs <= 9); }
    items.clear();
    Serial6.feed(infoFc, sizeof infoFc); Serial6.feed(infoRx, sizeof infoRx); Serial6.feed(rpm, sizeof rpm);
    run(1200);
    { bool rf = false; int rpms = 0; for (auto &it : items) { if (it.first == 31 && it.second[0] == 2) rf = true; if (it.first == 20) ++rpms; }
      CHECK(rf && RotorFlight_V == 2 && rpms >= 9 && rpms <= 13 && logHas("flight controller 'Rotorflight 4.6.0' = Rotorflight") && !strcmp(ReceiverVersionNumber, "RP4TD-M")); }   // head speed ten times a second from now
    m0 = mark(); run(8000); s = seen(m0); CHECK(s.other == 0);         // its name is known: no more questions
    printf("PASS the model heard: connected by the transmitter's own code, once; its battery, head speed and ESC temperature handed to the transmitter's telemetry; 'who is there?' asked, 'Rotorflight 4.6.0' taken, and not asked again\n");
    // ---- IN THE AIR: the motor switch on (accepted: a model is connected), then the model's replies stop for a minute
    airborne = true; const int deferred0 = deferredN;
    motorSwitchOn = true; run(200);
    CHECK(MotorEnabled && !SendNoData);
    m0 = mark(); modelHeard = false; const int red0 = redCalls, green0 = greenCalls;
    run(60000);
    s = seen(m0);
    CHECK(redCalls == red0 && LedWasGreen && BoundFlag && ModelMatched && !Connected && s.rc >= 14990 && s.follow == s.rc && s.motorFollows == s.rc && s.longestGapMs <= 12);
    CHECK(logHas("NO TELEMETRY") && countSound(WHAHWHAHMSG) == 1 && ElrsQuality() == 0);
    { bool said = false; for (auto &t : texts) if (t == "Connected=No telemetry") said = true; CHECK(said); }
    // the transmitter puts its own light out meanwhile (a setting redrawn - found by review: it led to "no model" and the motor box)
    LedWasGreen = false; m0 = mark(); run(5000); s = seen(m0);
    CHECK(redCalls == red0 && greenCalls == green0 + 1 && LedWasGreen && boxes == 0 && s.rc >= 1248 && s.follow == s.rc && s.motorFollows == s.rc);
    // an autorotation: the motor switched off, still silent - the switch brings the motor back
    motorSwitchOn = false; run(10000); CHECK(redCalls == red0 && LedWasGreen && !MotorEnabled);
    m0 = mark(); motorSwitchOn = true; run(300); s = seen(m0);
    CHECK(MotorEnabled && !SendNoData && redCalls == red0 && countSound(PLSTURNOFF) == 0 && s.rc >= 73 && s.follow == s.rc);
    // heard again: no second "Connected", the front page told to draw its word afresh
    modelHeard = true; run(600);
    CHECK(Connected && greenCalls == green0 + 1 && countSound(CONNECTEDMSG) == 2 && logHas("telemetry back") && LastConnectionQuality == 0xFFFF);
    printf("PASS in the air: a minute with no reply from the model and every frame still sent with its own stick and a live throttle; never 'no model' - not when the transmitter puts its own light out, not in an autorotation\n");
    // ---- landed: the motor off, the model switched off - given up half a minute after the motor switch, not before
    motorSwitchOn = false; run(100); const uint32_t offAt = fakeMs;
    CHECK(cardWritesInAir == 0 && otherInAir == 0 && deferredN - deferred0 == 3);   // the whole flight: not a line to the card (the three things to be said are kept: the silence, the light lit again, the silence's end), not one frame that was not the sticks
    { int k = 0; for (auto &l : deferred) if (l.find("NO TELEMETRY") != std::string::npos || l.find("LINK UP") != std::string::npos || l.find("telemetry back") != std::string::npos) ++k; CHECK(k >= 3); }
    airborne = false;                                                  // (the play's own word: down, and about to be switched off)
    modelHeard = false; run(MOTOR_OFF_GRACE_MS - 2000); CHECK(redCalls == red0 && LedWasGreen);
    m0 = mark(); run(4000); s = seen(m0);
    CHECK(redCalls == red0 + 1 && LedWasRed && !LedWasGreen && !BoundFlag && !ModelMatched && countSound(DISCONNECTEDMSG) == 1 && logHas("given up") && fakeMs - offAt < MOTOR_OFF_GRACE_MS + 4200);

    CHECK(s.rc >= 998 && s.follow == s.rc && s.motorLow == s.rc);      // ... and the frames go on through it, with fresh sticks (RedLedOn empties the channels: none of that is sent)
    // ---- no model, and the motor switch put on: refused, the throttle held low, the sticks still sent - and NO model connected
    // until the switch has been seen off (found by review: it connected, and the motor would have started with no new flick)
    m0 = mark(); motorSwitchOn = true; run(1000);
    CHECK(!MotorEnabled && SendNoData && countSound(PLSTURNOFF) >= 1);
    modelHeard = true; const int green1 = greenCalls; run(6000); s = seen(m0);
    CHECK(greenCalls == green1 && !LedWasGreen && !MotorEnabled && s.rc >= 1740 && s.follow == s.rc && s.motorLow == s.rc && s.longestGapMs <= 12);
    motorSwitchOn = false; run(400);
    CHECK(!SendNoData && greenCalls == green1 + 1 && LedWasGreen && Connected);                      // the switch off: now it connects
    m0 = mark(); airborne = true; motorSwitchOn = true; run(400); s = seen(m0);
    CHECK(MotorEnabled && s.rc >= 98 && s.motorFollows >= s.rc - 14 && s.follow == s.rc);            // a new flick: the motor is the pilot's
    motorSwitchOn = false; run(200);
    printf("PASS no model and the motor switch on: refused, the throttle low in every frame, the sticks still sent, and no model connected until the switch has been off; then a new flick gives the motor\n");
    // ---- a box on the screen while no model is heard (found by review: the frames stopped)
    CHECK(cardWritesInAir == 0 && otherInAir == 0); airborne = false;  // (down again, and switched off)
    modelHeard = false; run(MOTOR_OFF_GRACE_MS + 3000); CHECK(LedWasRed && !BoundFlag);
    m0 = mark(); boxAnswerAtMs = fakeMs + 3000; { char a[] = "page", b[] = "A question"; MsgBox(a, b); } s = seen(m0);
    CHECK(s.rc >= 745 && s.follow == s.rc && s.longestGapMs <= 6);
    m0 = mark(); DelayWithDog(2000); s = seen(m0); CHECK(s.rc >= 495 && s.follow == s.rc);          // ... and through a wait
    // binding pressed (LDRC's): switched off at once, and THAT pass's channels are not used (found by review)
    run(50); m0 = mark(); const uint32_t copyBefore = ElrsCopyMs;
    BindingEnabled = true; LedIsBlinking = true; pass();
    CHECK(!BindingEnabled && !LedIsBlinking && ElrsCopyMs == copyBefore);
    pass(); CHECK(ElrsCopyMs == fakeMs);
    // loop() away for three seconds while the model is heard (a mode of its own): not called silent for it (found by review)
    modelHeard = true; run(600); CHECK(LedWasGreen && Connected);
    int silences = 0; for (auto &l : logLines) if (l.find("NO TELEMETRY") != std::string::npos) ++silences;
    const int red2 = redCalls; for (int k = 0; k < 3000; ++k) tick1ms();
    run(300); CHECK(redCalls == red2 && LedWasGreen && Connected);
    { int n = 0; for (auto &l : logLines) if (l.find("NO TELEMETRY") != std::string::npos) ++n; CHECK(n == silences && silences == 3); }   // (the three real silences above: none for the absence)
    printf("PASS a box and a wait with no model heard: the frames go on; binding is switched off and its pass not used; an absence of loop() is not a silence of the model\n");
    // ---- the frames stop only where they must: another model's values in memory, a mode loop() sends nothing in, the motor box
    m0 = mark(); ElrsModel = false; DelayWithDog(60); s = seen(m0);    // (a calibration or the game loads the defaults: not an ELRS model)
    CHECK(s.rc <= 26 && ElrsCarries());                                // at most the last copy's 100 ms; never the other model's channels
    for (size_t i = m0; i < Serial6.out.size(); ++i) if (isRc(Serial6.out[i])) CHECK(Serial6.outMs[i] - (fakeMs - 60) <= STICKS_STALE_MS + 4);
    ElrsModel = true; run(300);
    CurrentMode = CALIBRATELIMITS; m0 = mark(); DelayWithDog(400); s = seen(m0); CHECK(s.rc <= 26); CurrentMode = NORMAL; run(300);
    m0 = mark(); SendNoData = true; motorSwitchOn = true; MotorEnabled = true; MotorWasEnabled = true; DelayWithDog(400); s = seen(m0);   // as inside "The motor switch is ON. Switch it off"
    CHECK(s.rc <= 26); SendNoData = false; motorSwitchOn = false; run(300);
    // ---- back to an LDRC model: the timer first, then the line let go, pin 25 as the transmitter had it, the power off, LDRC again
    const int ldrc3 = ldrcPackets;
    ElrsModel = false; run(600);
    CHECK(!ElrsCarries() && ElrsTimer.ends == 1 && Serial6.ends == 1 && !Serial6.timerRanAtEnd && pinModes[24] == INPUT && pinModes[25] == INPUT_PULLUP && pinLevels[10] == LOW);
    CHECK(!LedWasGreen && LedWasRed && !BoundFlag && !ModelMatched && !Connected && ldrcPackets - ldrc3 > 200 && logHas("ELRS test: model's receiver is LDRC"));
    m0 = mark(); run(500); CHECK(mark() == m0);                        // nothing more on the wire
    // ---- the transmitter switched on with an ELRS model AND the motor switch on: its own box, and nothing sent until the switch is off
    ElrsModel = true; LedWasRed = false; LedWasGreen = false; motorSwitchOn = true; MotorEnabled = true; MotorWasEnabled = true; modelHeard = false;
    const int boxes0 = boxes, red3 = redCalls; boxHook = motorOffInBox; m0 = mark();
    run(1000); boxHook = nullptr;                                     // (the box alone takes two seconds: the pass that met it ends after them)
    CHECK(Serial6.begins == 1 && mark() == m0);                       // through the box: no line, nothing sent
    run(600);
    CHECK(boxes == boxes0 + 1 && redCalls == red3 + 1 && !motorSwitchOn && !SendNoData && Serial6.begins == 2 && Serial6.mem == 1 && ElrsTimer.begins == 2);
    { size_t firstRc = 0; for (size_t i = m0; i < Serial6.out.size(); ++i) if (isRc(Serial6.out[i])) { firstRc = i; break; }
      CHECK(firstRc > 0 && Serial6.outMs[firstRc] >= Serial6.beginMs && Serial6.beginMs - pin10HighMs >= POWER_SETTLE_MS && chan(Serial6.out[firstRc], MotorChannel) == 1000); }
    m0 = mark(); run(1000); s = seen(m0); CHECK(s.rc >= 248 && s.follow == s.rc && s.motorLow == s.rc);
    printf("PASS the frames stop where they must (another model in memory, a mode that sends nothing, the motor-switch box) and nowhere else; back to LDRC the line is let go and pin 25 put back; switched on with the motor switch on, nothing is sent until it is off\n");
    // ---- THE MODULE'S OWN SETTINGS: once it has said how many it has, its list is read and the log gets it. Nothing is written.
    {
        CHECK(ElrsCarries() && !MotorEnabled && !modelHeard && moduleReads == 0);          // (as the scene before left it: an ELRS model, its link begun, no model heard, the motor switch off)
        const int NP = (int)PDATA.size(); int pieces = 0; for (unsigned n = 1; n <= PDATA.size(); ++n) pieces += (int)modulePieces(n);
        auto count = [&](size_t from, const char *w) { int n = 0; for (size_t i = from; i < logLines.size(); ++i) if (logLines[i].find(w) != std::string::npos) ++n; return n; };
        auto sentOfType = [&](size_t from, uint8_t type) { int n = 0; for (size_t i = from; i < Serial6.out.size(); ++i) if (Serial6.out[i].size() >= 3 && Serial6.out[i][2] == type) ++n; return n; };
        // (a) a transmitter WITH a safety switch, a model connected, the module slow to answer (150 ms a piece) - and in the middle of
        // the reading the pilot flies: the safety off, the motor on, AN AUTOROTATION (the motor switch off, in the air), the motor on
        // again, down, and only then the safety on. (Found by review, 14 Nov 2026: the reading went by the motor switch alone, and
        // would have gone on in the autorotation - requests in place of the sticks' frames, and line after line to the card.)
        safetyDefined = true; SafetyON = true;
        MotorChannel = 3; stick[3] = 1700; stick[4] = 1500;            // (a model whose throttle is NOT channel 5: the throttle held on ExpressLRS's one-bit channel has its own scene, below)
        moduleLists = true; moduleDelayMs = 150; modelHeard = true; size_t l0 = logLines.size(); m0 = mark();
        run(4500);
        CHECK(LedWasGreen && count(l0, "ELRS test: the module 'RM Ranger Nano' has 23 settings - reading them (nothing is changed)") == 1);
        CHECK(moduleReads >= 3 && moduleReads < pieces && count(l0, "the module's settings:") == 0);
        const int card0 = cardWritesInAir, other0 = otherInAir;
        SafetyON = false; run(2);                                       // THE SAFETY OFF: the model may be flying from here ...
        airborne = true;                                                // (... by the play's own word from the pass after: a frame of ours the timer already had may go in that very pass)
        const size_t linesUp = logLines.size(); const size_t mUp = mark();
        run(1500);                                                      // the safety off, the motor not yet on
        motorSwitchOn = true; run(3000); CHECK(MotorEnabled && !SendNoData);
        motorSwitchOn = false; run(4000); CHECK(!MotorEnabled && LedWasGreen);          // THE AUTOROTATION: four seconds with the motor switch off, in the air
        motorSwitchOn = true; run(1000); CHECK(MotorEnabled);
        // far out: the model's replies lost and found again ten times - twenty things to say, and the transmitter's store for such
        // lines has 24 places for all it has to say (full, it writes them out in the air): a few are kept, the rest counted
        const int kept0 = deferredN;
        for (int k = 0; k < 10; ++k) { modelHeard = false; run(LINK_LOST_MS + 400); modelHeard = true; run(600); }
        CHECK(deferredN - kept0 == 6 && LedWasGreen && Connected);
        motorSwitchOn = false; run(500);                                // down: the motor off, the safety still off
        s = seen(mUp);
        CHECK(cardWritesInAir == card0 && otherInAir == other0 && sentOfType(mUp, 0x2C) == 0 && sentOfType(mUp, 0x28) == 0 && s.other == 0 && s.rc >= 9990 && s.follow == s.rc);
        CHECK(count(linesUp, "ELRS test: setting") == 0 && count(linesUp, "module's settings") == 0 && count(linesUp, "ELRS test: sent ") == 0 && moduleReads < pieces && count(linesUp, "had no place") == 0);
        SafetyON = true; airborne = false; run(200);                    // THE SAFETY ON: on the ground, and the reading goes on where it was
        CHECK(count(linesUp, "ELRS test: 14 more lines had no place to be kept while the model could be flying") == 1);
        run(9000);
        CHECK(count(l0, "ELRS test: the module's settings: 23 read, 0 not answered") == 1 && moduleReads == pieces && moduleAnswered == pieces);
        CHECK(logHas("ELRS test: setting 1 'Packet Rate' (choice, kind 9, in 0): value 3, min 0, max 9, units ' '") && logHas("ELRS test: setting 1 says (more): "));
        CHECK(logHas("ELRS test: setting 2 'Telem Ratio' (choice, kind 9, in 0): value 0, min 0, max 9, units ' (1:64)'") && logHas("ELRS test: setting 2 says: Std;Off;;1:64;1:32;1:16;1:8;1:4;1:2;Race"));
        CHECK(logHas("ELRS test: setting 3 'Switch Mode' (choice, kind 9, in 0): value 0, min 0, max 1") && logHas("ELRS test: setting 3 says: Wide;Hybrid"));
        CHECK(logHas("ELRS test: setting 7 'Max Power' (choice, kind 9, in 6): value 2, min 0, max 3, units 'mW'") && logHas("ELRS test: setting 7 says: 10;25;50;100"));
        CHECK(logHas("ELRS test: setting 6 'TX Power (50 Dynamic)' (folder, kind 11, in 0)") && logHas("ELRS test: setting 15 'Pitmode' (choice, kind 9, in 11, hidden)"));
        CHECK(logHas("ELRS test: setting 13 'Channel' (number, kind 0, in 11): value 1, min 1, max 8") && logHas("ELRS test: setting 21 'Bind' (command, kind 13, in 0): value 0, min 200"));
        CHECK(logHas("ELRS test: setting 23 '3.6.4 CE_2400' (text, kind 12, in 0)") && logHas("ELRS test: setting 23 says: abc123"));
        // the packet rates' list is longer than a line of the log may be: two lines, and nothing of it lost
        { std::string all; const std::string a = "ELRS test: setting 1 says: ", b = "ELRS test: setting 1 says (more): ";
          for (auto &l : logLines) { if (!l.compare(0, a.size(), a)) all += l.substr(a.size()); else if (!l.compare(0, b.size(), b)) all += l.substr(b.size()); }
          CHECK(all == ''' + cstr(printable(RATES)) + r'''); }
        { size_t longest = 0; int heads = 0;
          for (size_t i = l0; i < logLines.size(); ++i) { longest = std::max(longest, logLines[i].size()); if (!logLines[i].compare(0, 19, "ELRS test: setting ") && logLines[i].find(" says") == std::string::npos) ++heads; }
          CHECK(longest < 200 && heads == NP); }                                           // every line within a line's length; each setting once
        // the sticks went on all the while: each request, and each "who is there?", in place of ONE channel frame
        s = seen(m0);
        CHECK(sentOfType(m0, 0x2C) == pieces && s.other == pieces + sentOfType(m0, 0x28) && sentOfType(m0, 0x28) >= 1 && s.follow == s.rc && s.longestGapMs <= 9);
        m0 = mark(); run(6000); s = seen(m0);
        CHECK(sentOfType(m0, 0x2C) == 0 && moduleReads == pieces);                         // read: nothing more of it is asked
        // (b) a new beginning of the link (the list is read once for each), and every fifth request left unanswered: asked again, all read
        modelHeard = false; ElrsModel = false; run(400); CHECK(!ElrsCarries());
        int reads1 = moduleReads; moduleDelayMs = 6; moduleDropNth = 5; l0 = logLines.size();
        ElrsModel = true; run(30000);
        CHECK(ElrsCarries() && moduleReads - reads1 > pieces && count(l0, "ELRS test: the module's settings: 23 read, 0 not answered") == 1 && count(l0, "has 23 settings") == 1);
        { int heads = 0; for (size_t i = l0; i < logLines.size(); ++i) if (!logLines[i].compare(0, 19, "ELRS test: setting ") && logLines[i].find(" says") == std::string::npos) ++heads; CHECK(heads == NP); }
        // (c) a module that names itself but answers no request: each setting left after its tries, the reading ends, the sticks go on
        ElrsModel = false; run(400); moduleDropNth = 0; moduleDeaf = true; reads1 = moduleReads; l0 = logLines.size();
        ElrsModel = true; m0 = mark(); run(8000 + NP * (int)PARAM_TRIES * (int)PARAM_ANSWER_MS);
        s = seen(m0);
        CHECK(moduleReads - reads1 == NP * (int)PARAM_TRIES && count(l0, "ELRS test: the module's settings: 0 read, 23 not answered") == 1 && count(l0, "ELRS test: setting") == 0);
        CHECK(s.follow == s.rc && s.longestGapMs <= 9 && s.other == NP * (int)PARAM_TRIES + sentOfType(m0, 0x28));
        m0 = mark(); run(5000); CHECK(sentOfType(m0, 0x2C) == 0);
        moduleDeaf = false;
        // (d) a module that says it has no settings: nothing is asked
        ElrsModel = false; run(400); moduleLists = false; reads1 = moduleReads; l0 = logLines.size(); modelHeard = true;
        ElrsModel = true; run(9000);
        CHECK(LedWasGreen && moduleReads == reads1 && count(l0, "settings") == 0 && modulePings >= 1);
        // and in the whole play up to here not one setting was WRITTEN - and in the air not one line went to the card, not one frame that was not the sticks'
        CHECK(moduleWrites == 0);
        CHECK(cardWritesInAir == 0 && otherInAir == 0 && deferredN > 0);
        printf("PASS the module's own settings: asked how many (%d), all read piece by piece (%d pieces) and written to the log, each request in place of one channel frame; in the air (the safety off: an autorotation too) none asked and not a line written; an unanswered request asked again; a module that never answers is left; nothing written to the module\n", NP, pieces);
    }
    // ---- THE PAGE "ELRS settings": the four rows as the module says them; a change asked for, written ONCE, and read back;
    // and THE THROTTLE HELD while the module's switch mode carries channel 5 - an LDRC model's throttle - as off or on only
    {
        auto last = [&](const char *box) { std::string v = "<never>"; const std::string k = std::string(box) + "="; for (auto &t : texts) if (!t.compare(0, k.size(), k)) v = t.substr(k.size()); return v; };
        auto sent = [&](const char *cmd) { for (auto &t : texts) if (t == cmd) return true; return false; };
        auto count = [&](size_t from, const char *w) { int n = 0; for (size_t i = from; i < logLines.size(); ++i) if (logLines[i].find(w) != std::string::npos) ++n; return n; };
        auto kept = [&](size_t from, const char *w) { for (size_t i = from; i < deferred.size(); ++i) if (deferred[i].find(w) != std::string::npos) return true; return false; };
        auto newLink = [&]() { ElrsModel = false; run(400); modelHeard = false; ElrsModel = true; run(9000); };   // the link begun afresh, its list read
        auto open = [&]() { CurrentView = RXSETUPVIEW1; texts.clear(); StartElrsView(); run(3000); };            // the page opened (its list is read once more as it opens)
        int pieces = 0; for (unsigned n = 1; n <= PDATA.size(); ++n) pieces += (int)modulePieces(n);
        const char *HELD = "Throttle is channel 5: it needs 333Hz Full, then 16ch Rate/2.";
        MotorChannel = 4; stick[4] = 1700; stick[3] = 1500;             // THIS model's throttle is channel 5, as an LDRC model's is
        moduleLists = true; moduleDelayMs = 6; moduleDropNth = 0; SafetyON = true; size_t l0 = logLines.size();
        newLink();
        CHECK(ElrsCarries() && !LedWasGreen && moduleWrites == 0 && moduleOddWrites == 0);       // (in all the play so far nothing was written to the module)
        // the module's switch mode is "Wide": said in the log, once
        CHECK(count(l0, "ELRS test: THROTTLE HELD - this model's throttle is channel 5, and switch mode 'Wide' carries it as off or on only (it needs '16ch Rate/2')") == 1);
        // ONLY FROM MODEL OPTIONS: a second tap, kept and served when another page shows, reads nothing and saves nothing (found by review:
        // that page's boxes came back as 0 for Model options' - the motor kill switch, the stop-flying volts, six banks - and its OK saved them)
        { const int r0 = optionsRead, sv0 = modelsSaved, sh0 = optionsShown; CurrentView = FRONTVIEW; texts.clear();
          StartElrsView(); CHECK(CurrentView == FRONTVIEW && optionsRead == r0 && modelsSaved == sv0 && texts.empty());
          EndElrsView(); CHECK(CurrentView == FRONTVIEW && optionsShown == sh0); }
        // opened from Model options (whose values are read AND SAVED first, as its other ways out do): the rows, the module's name,
        // whose settings they are (every ELRS model's), and the line that says why the throttle is held
        CurrentView = RXSETUPVIEW1; const int read0 = optionsRead, saved0 = modelsSaved; texts.clear(); int reads0 = moduleReads;
        StartElrsView();
        CHECK(CurrentView == ELRSVIEW && optionsRead == read0 + 1 && modelsSaved == saved0 + 1 && sent("page ElrsView"));
        CHECK(last("tn0") == "250Hz" && last("tn1") == "Std (1:64)" && last("tn2") == "Wide" && last("tn3") == "50 mW" && last("t9") == "RM Ranger Nano" && last("t11") == "All ELRS models" && last("hint") == HELD);
        // ... and as it opens the list is read once more, quietly (the module may have been changed elsewhere): nothing changed, nothing drawn again
        { const size_t n0 = texts.size(), g0 = logLines.size(); run(3000); CHECK(texts.size() == n0 && moduleReads - reads0 == pieces && count(g0, "ELRS test: setting") == 0 && count(g0, "module's settings:") == 0); }
        // THE HOLD ITSELF: a model connected, the safety off, the motor switch ON - and every frame still says "motor off", the front
        // page says "Throttle held", it is heard, a line is kept; the sticks go on
        { modelHeard = true; run(1500); CHECK(LedWasGreen && Connected);
          const int whah0 = countSound(WHAHWHAHMSG); const size_t d0 = deferred.size();
          SafetyON = false; run(50); airborne = true; CurrentView = FRONTVIEW; texts.clear();
          m0 = mark(); motorSwitchOn = true; run(3000); s = seen(m0);
          CHECK(MotorEnabled && !SendNoData && s.rc >= 745 && s.motorLow == s.rc && s.motorFollows == 0 && s.follow == s.rc && countSound(WHAHWHAHMSG) == whah0 + 1);
          CHECK(sent("Connected=Throttle held") && kept(d0, "THROTTLE HELD (ch5 1 bit)"));
          motorSwitchOn = false; run(300); SafetyON = true; airborne = false; run(300); }
        // (a link begun afresh, with no model, for what follows: the motor switch has not been on in it)
        newLink(); open();
        CHECK(CurrentView == ELRSVIEW && last("hint") == HELD && moduleWrites == 0);
        // A ROW TAPPED: the picker, with the choices the module offers in its order - and for the telemetry share WITHOUT "Off" (the
        // model could never be connected: the transmitter knows it by its replies) and "Race" (found by review); on the one it has
        texts.clear(); ElrsRow1Tapped();
        CHECK(CurrentView == ELRSPICKVIEW && sent("page ElrsPickView") && last("t0") == "Telemetry share" && last("t11") == "All ELRS models" && last("list") == "0");
        CHECK(sent("list.path=\"Std\r\n1:64\r\n1:32\r\n1:16\r\n1:8\r\n1:4\r\n1:2\""));
        ElrsPickCancel(); run(1500); CHECK(CurrentView == ELRSVIEW && moduleWrites == 0);        // Cancel: back, nothing asked
        // OK on "1:8" - the FIFTH on the wheel, the SEVENTH place of the module's list: ONE frame to the module, with the place;
        // then its list is read again, quietly; the row says what the module then says
        ElrsRow1Tapped(); valueList = 4; l0 = logLines.size(); m0 = mark(); reads0 = moduleReads;
        ElrsPickOk();
        CHECK(CurrentView == ELRSVIEW && last("hint") == "Asking the module ...");
        run(4000);
        CHECK(moduleWrites == 1 && moduleTook == 1 && lastWriteNumber == 2 && lastWriteValue == 6 && moduleOddWrites == 0 && moduleReads - reads0 == pieces);
        CHECK(last("tn1") == "1:8 (1:64)" && last("hint") == HELD && last("tn0") == "250Hz");
        CHECK(count(l0, "ELRS test: 'Telem Ratio' asked to be '1:8': the module now says '1:8 (1:64)'") == 1 && count(l0, "ELRS test: setting") == 0 && count(l0, "module's settings:") == 0);
        s = seen(m0); CHECK(s.follow == s.rc && s.longestGapMs <= 9 && s.other == 1 + pieces);   // the sticks went on; the write and each request in place of one frame
        // the choice it already has, and a reply from the screen that never came: nothing is written
        texts.clear(); ElrsRow1Tapped(); CHECK(last("list") == "4");                             // (the wheel opens on what the module has: its rank on the wheel)
        valueList = 4; ElrsPickOk(); run(1500); CHECK(moduleWrites == 1 && CurrentView == ELRSVIEW);
        ElrsRow1Tapped(); valueList = 65535; ElrsPickOk(); run(1500); CHECK(moduleWrites == 1 && CurrentView == ELRSVIEW);
        // THE MODULE KEEPS WHAT IT HAD (it is the judge): asked, read back three times, and then the row shows what it says and the line says so
        moduleKeepsNext = true; texts.clear(); ElrsRow3Tapped();
        CHECK(sent("list.path=\"10\r\n25\r\n50\r\n100\"") && last("t0") == "Most power" && last("list") == "2");
        valueList = 3; l0 = logLines.size(); reads0 = moduleReads; ElrsPickOk(); run(8000);
        CHECK(moduleWrites == 2 && moduleKept == 1 && lastWriteNumber == 7 && lastWriteValue == 3 && last("tn3") == "50 mW" && last("hint") == "The module kept what it had." && moduleReads - reads0 == 3 * pieces);
        CHECK(count(l0, "ELRS test: 'Max Power' asked to be '100': the module KEPT '50 mW'") == 1);
        // A MODULE SLOW TO SAY ITS NEW VALUE (it tells the receiver and saves first - found by review: 400 ms was taken for all it needs):
        // read back again, and "taken" is said when it is true
        moduleSlowMs = 1200; ElrsRow3Tapped(); valueList = 3; l0 = logLines.size(); reads0 = moduleReads; ElrsPickOk(); run(8000); moduleSlowMs = 0;
        CHECK(moduleWrites == 3 && lastWriteNumber == 7 && lastWriteValue == 3 && last("tn3") == "100 mW" && last("hint") == HELD && moduleReads - reads0 == 2 * pieces);
        CHECK(count(l0, "ELRS test: 'Max Power' asked to be '100': the module now says '100 mW'") == 1 && count(l0, "KEPT") == 0);
        // a model connected: the rate and the channel detail are not offered for change; the others are
        modelHeard = true; run(1500);
        CHECK(LedWasGreen && Connected); ElrsRow1Tapped(); ElrsPickCancel(); run(1200);          // (a tap clears "kept"; the line then says what stands in the way)
        CHECK(last("hint") == HELD);                                                               // (the hold comes before "model connected": it is the graver)
        ElrsRow0Tapped(); CHECK(CurrentView == ELRSVIEW); ElrsRow2Tapped(); CHECK(CurrentView == ELRSVIEW);
        ElrsRow3Tapped(); CHECK(CurrentView == ELRSPICKVIEW); ElrsPickCancel(); CHECK(CurrentView == ELRSVIEW && moduleWrites == 3);
        // the model off: the packet rate to "333Hz Full" - the switch mode's number then means "8ch" (still one bit for channel 5: held)
        modelHeard = false; run(4000); CHECK(!LedWasGreen && LedWasRed);
        texts.clear(); ElrsRow0Tapped();
        CHECK(CurrentView == ELRSPICKVIEW && last("t0") == "Stick updates a second" && last("list") == "3");
        CHECK(sent("list.path=\"50Hz\r\n100Hz Full\r\n150Hz\r\n250Hz\r\n333Hz Full\r\n500Hz\r\nD250\r\nD500\r\nF500\r\nF1000\""));
        valueList = 4; ElrsPickOk(); run(4000);
        CHECK(moduleWrites == 4 && lastWriteNumber == 1 && lastWriteValue == 4 && last("tn0") == "333Hz Full" && last("tn2") == "8ch" && last("hint") == HELD);
        // ... and the channel detail to "16ch Rate/2": every channel whole - THE HOLD ENDS
        texts.clear(); ElrsRow2Tapped();
        CHECK(sent("list.path=\"8ch\r\n16ch Rate/2\r\n12ch Mixed\"") && last("t0") == "Channel detail" && last("list") == "0");
        valueList = 1; ElrsPickOk(); run(4000);
        CHECK(moduleWrites == 5 && moduleTook == 4 && lastWriteNumber == 3 && lastWriteValue == 1 && last("tn2") == "16ch Rate/2" && last("hint") == "" && moduleOddWrites == 0);
        // the motor is the pilot's again: a model connected, the safety off, the motor switch on - the throttle follows its stick
        { modelHeard = true; run(1500); CHECK(LedWasGreen && Connected);
          const int whah0 = countSound(WHAHWHAHMSG); SafetyON = false; run(50); airborne = true; CurrentView = FRONTVIEW; texts.clear();
          m0 = mark(); motorSwitchOn = true; run(3000); s = seen(m0);
          CHECK(MotorEnabled && s.rc >= 745 && s.motorFollows >= s.rc - 14 && s.follow == s.rc && countSound(WHAHWHAHMSG) == whah0 && !sent("Connected=Throttle held"));
          // IN THE AIR THE HOLD CANNOT BEGIN: were the module's word to change now (it cannot be read in the air), nothing is taken from a running motor
          PDATA[2] = P3_STD; run(5000); s = seen(m0); CHECK(s.motorFollows >= s.rc - 14 && s.motorLow <= 14); PDATA[2] = P3_FULL; PDATA[2][(size_t)valueAt(PDATA[2])] = 1;
          motorSwitchOn = false; run(300); SafetyON = true; airborne = false; modelHeard = false; run(MOTOR_OFF_GRACE_MS + 3000); CHECK(!LedWasGreen); }
        // A CHANGE OF PACKET RATE TURNS "16ch Rate/2" INTO "Hybrid" WITHOUT A WORD (the same number, another meaning - found by review):
        // the page shows it, the line says the throttle is held, the log says it - and the hold is on again
        open(); l0 = logLines.size(); ElrsRow0Tapped(); valueList = 3; ElrsPickOk(); run(4000);
        CHECK(moduleWrites == 6 && lastWriteNumber == 1 && lastWriteValue == 3 && last("tn0") == "250Hz" && last("tn2") == "Hybrid" && last("hint") == HELD);
        CHECK(count(l0, "ELRS test: THROTTLE HELD - this model's throttle is channel 5, and switch mode 'Hybrid' carries it as off or on only") == 1);
        // WRITTEN, AND THEN THE SAFETY GOES OFF BEFORE IT IS READ BACK (found by review: it was called "kept", unread, and the list left stale):
        // the frame has gone, so the module has the change - it is read back on the ground, and then said true
        ElrsRow1Tapped(); valueList = 5; ElrsPickOk();                  // "1:4" asked for ...
        { const int w0 = moduleWrites; int passes = 0; while (!ElrsOtherLen && passes < 50) { pass(); ++passes; }      // ... its frame left for the timer ...
          CHECK(ElrsOtherLen == PARAM_FRAME_LEN && moduleWrites == w0);
          for (int k = 0; k < 20 && moduleWrites == w0; ++k) tick1ms();                             // ... and SENT by the timer, loop() not having been round since ...
          CHECK(moduleWrites == w0 + 1 && lastWriteNumber == 2 && lastWriteValue == 7 && ElrsOtherLen == 0); }
        reads0 = moduleReads; SafetyON = false; airborne = true; run(3000);                       // ... when the model may fly: before it is read back
        CHECK(moduleReads == reads0 && otherInAir == 0);
        SafetyON = true; airborne = false; run(4000);
        CHECK(last("tn1") == "1:4 (1:64)" && last("hint") == HELD && moduleWrites == 7 && moduleReads - reads0 == pieces);
        // ASKED FOR, AND THE SAFETY GOES OFF BEFORE IT IS WRITTEN: dropped - not written then, and not written later behind the pilot's back
        ElrsRow1Tapped(); CHECK(CurrentView == ELRSPICKVIEW); valueList = 3; ElrsPickOk();        // "1:16" asked for ...
        SafetyON = false; airborne = true;                              // ... and before the next pass the safety is off
        run(3000); SafetyON = true; airborne = false; run(4000);
        CHECK(moduleWrites == 7 && last("tn1") == "1:4 (1:64)" && last("hint") == "The module kept what it had." && cardWritesInAir == 0 && otherInAir == 0);
        // the picker open when the safety goes off: its OK asks for nothing; and with the safety off a row opens no picker
        ElrsRow1Tapped(); CHECK(CurrentView == ELRSPICKVIEW);
        SafetyON = false; valueList = 2; ElrsPickOk(); run(1500);
        CHECK(moduleWrites == 7 && CurrentView == ELRSVIEW && last("hint") == "Safety on first: nothing is changed while the model may fly.");
        ElrsRow1Tapped(); CHECK(CurrentView == ELRSVIEW);
        SafetyON = true; run(1200);
        // NOT WRITTEN WITHIN ITS TIME (the module is being read and does not answer): dropped after five seconds, and said
        moduleDeaf = true; open();                                      // (the page opens: the list is to be read again - and the module says nothing)
        ElrsRow1Tapped(); CHECK(CurrentView == ELRSPICKVIEW); valueList = 2; ElrsPickOk(); run(7000);
        CHECK(moduleWrites == 7 && last("hint") == "The module kept what it had."); moduleDeaf = false;
        newLink(); open();
        // its OK: back to Model options, drawn afresh; the codes of its rows and its picker from another page do nothing; and for a
        // model not set to ELRS the page is not opened
        const int shown0 = optionsShown; EndElrsView(); CHECK(optionsShown == shown0 + 1 && CurrentView == RXSETUPVIEW1);
        ElrsRow1Tapped(); ElrsPickOk(); ElrsPickCancel(); EndElrsView(); CHECK(CurrentView == RXSETUPVIEW1 && moduleWrites == 7 && optionsShown == shown0 + 1);
        ElrsModel = false; StartElrsView(); CHECK(CurrentView == RXSETUPVIEW1 && optionsShown == shown0 + 2);
        run(600); CHECK(!ElrsCarries() && cardWritesInAir == 0 && otherInAir == 0);
        printf("PASS the page 'ELRS settings': opened only from Model options; the four rows as the module says them; a row's choices in the module's order (no telemetry 'Off'); OK = one frame written, the list read again (and again, for a slow module), the row says what the module says; THE THROTTLE HELD while the switch mode carries channel 5 as one bit - and never begun in the air; a change dropped while the model may fly, one already written read back afterwards; %d changes written in the whole play\n", moduleWrites);
    }
    // ---- THE THROTTLE IS HELD UNTIL THE MODULE HAS SAID ITS SWITCH MODE (the third review, 14 Nov 2026: "not known" was "not
    // held" - the first seconds of every link, and a moment in every reading-back of the list, were unheld: on "Hybrid" that
    // is full throttle above half stick), MOTOR OFF WHENEVER THE MOTOR SWITCH IS OFF (a buddy master's buddy switch took that
    // away), and a restart in flight that flies on
    {
        auto sent = [&](const char *cmd) { for (auto &t : texts) if (t == cmd) return true; return false; };
        auto count = [&](size_t from, const char *w) { int n = 0; for (size_t i = from; i < logLines.size(); ++i) if (logLines[i].find(w) != std::string::npos) ++n; return n; };
        auto kept = [&](size_t from, const char *w) { for (size_t i = from; i < deferred.size(); ++i) if (deferred[i].find(w) != std::string::npos) return true; return false; };
        auto setMode = [&](bool whole) { PDATA[0][(size_t)valueAt(PDATA[0])] = whole ? 4 : 3; PDATA[2] = whole ? P3_FULL : P3_STD; PDATA[2][(size_t)valueAt(PDATA[2])] = whole ? 1 : 0; };   // "333Hz Full" and "16ch Rate/2", or "250Hz" and "Wide"
        int pieces = 0; for (unsigned n = 1; n <= PDATA.size(); ++n) pieces += (int)modulePieces(n);
        auto down = [&]() { motorSwitchOn = false; run(300); SafetyON = true; airborne = false; run(300); };
        auto away = [&]() { down(); modelHeard = false; ElrsModel = false; run(600); };
        MotorChannel = 4; stick[4] = 1700; stick[3] = 1500; safetyDefined = true; SafetyON = true; airborne = false;
        moduleLists = true; moduleDeaf = false; moduleDropNth = 0; moduleDelayMs = 6; moduleSlowMs = 0; CurrentView = FRONTVIEW;
        const int air0 = cardWritesInAir, other0 = otherInAir;
        // 1. THE PILOT IS QUICKER THAN THE LIST: the module would say "16ch Rate/2", but the safety is off from the first moment,
        //    so nothing is read - not known is HELD: the motor switch starts nothing, and that is heard, said and shown
        setMode(true); away(); const int readsA = moduleReads;
        SafetyON = false; airborne = true; modelHeard = true; ElrsModel = true; run(3000);
        CHECK(ElrsCarries() && LedWasGreen && Connected && moduleReads == readsA && !freeNow());
        { const int whah0 = countSound(WHAHWHAHMSG); const size_t d0 = deferred.size(); texts.clear();
          size_t m1 = mark(); motorSwitchOn = true; run(3000); Seen s1 = seen(m1);
          CHECK(MotorEnabled && !SendNoData && s1.rc >= 745 && s1.motorLow == s1.rc && s1.motorFollows == 0 && s1.follow == s1.rc && countSound(WHAHWHAHMSG) == whah0 + 1);
          CHECK(kept(d0, "THROTTLE HELD (not read)") && sent("Connected=Throttle held") && !freeNow() && moduleReads == readsA); }
        //    ... down, the safety on: now the list is read, the module says the one mode, and the hold ends without a word
        { const size_t l1 = logLines.size(); down(); run(6000);
          CHECK(moduleReads > readsA && freeNow() && count(l1, "THROTTLE HELD -") == 0);
          const int whah0 = countSound(WHAHWHAHMSG); SafetyON = false; run(50); airborne = true; texts.clear();
          size_t m1 = mark(); motorSwitchOn = true; run(2000); Seen s1 = seen(m1);
          CHECK(MotorEnabled && s1.rc >= 495 && s1.motorFollows >= s1.rc - 14 && countSound(WHAHWHAHMSG) == whah0 && !sent("Connected=Throttle held"));
          down(); }
        // 2. THE LIST READ AGAIN (the page opened; a slow module): what the module last said stands at every pass - a free
        //    throttle stays free, a held one stays held (it was let go for as long as the reading took)
        { moduleDelayMs = 40; CurrentView = RXSETUPVIEW1; const int r1 = moduleReads; StartElrsView();
          int notFree = 0; for (int k = 0; k < 9000; ++k) { pass(); if (!freeNow()) ++notFree; }
          CHECK(moduleReads - r1 == pieces && notFree == 0); EndElrsView(); CurrentView = FRONTVIEW; moduleDelayMs = 6; }
        away(); setMode(false); ElrsModel = true; run(9000); CHECK(!freeNow());            // "Wide": held
        { moduleDelayMs = 40; CurrentView = RXSETUPVIEW1; const int r1 = moduleReads; StartElrsView();
          int freeMoments = 0; for (int k = 0; k < 9000; ++k) { pass(); if (freeNow()) ++freeMoments; }
          CHECK(moduleReads - r1 == pieces && freeMoments == 0); EndElrsView(); CurrentView = FRONTVIEW; moduleDelayMs = 6; }
        // 3. A CHANGE OF PACKET RATE IS WRITTEN: from that frame the module's word is not known - held until it says what it now
        //    has (the same number means another switch mode). A change of the telemetry share leaves a free throttle free.
        away(); setMode(true); ElrsModel = true; run(9000); CHECK(freeNow());
        { CurrentView = RXSETUPVIEW1; StartElrsView(); run(3000); CHECK(CurrentView == ELRSVIEW && freeNow());
          ElrsRow1Tapped(); valueList = 4; const int w1 = moduleWrites; ElrsPickOk();               // the telemetry share to "1:8"
          int notFree = 0; for (int k = 0; k < 5000; ++k) { pass(); if (!freeNow()) ++notFree; }
          CHECK(moduleWrites == w1 + 1 && notFree == 0);
          ElrsRow0Tapped(); CHECK(CurrentView == ELRSPICKVIEW); valueList = 3; ElrsPickOk();        // the packet rate to "250Hz"
          int k = 0; while (moduleWrites == w1 + 1 && k < 3000) { pass(); ++k; }
          pass();                                                                                   // (the frame was left for the timer in one pass; the hold is worked out in the next)
          CHECK(moduleWrites == w1 + 2 && lastWriteNumber == 1 && !freeNow());            // written: held from here ...
          int freeMoments = 0; for (k = 0; k < 5000; ++k) { pass(); if (freeNow()) ++freeMoments; }
          CHECK(freeMoments == 0 && !freeNow());                                         // ... and the module says "Hybrid": held on
          EndElrsView(); CurrentView = FRONTVIEW; }
        // 4. A MODULE THAT SAYS WHO IT IS AND NEVER ITS LIST: held, and once the list has been given up the log says why, once.
        //    A module that says nothing at all (its power switch off): held too - there is nothing to fly with, and no line
        away(); setMode(true); moduleDeaf = true; { const size_t l1 = logLines.size(); ElrsModel = true; run(15000);
          CHECK(!freeNow() && count(l1, "THROTTLE HELD -") == 0);                        // (still asking: nothing said yet)
          run(60000);
          CHECK(!freeNow() && count(l1, "ELRS test: THROTTLE HELD - this model's throttle is channel 5, and the module has not said its switch mode (it must be '16ch Rate/2')") == 1);
          run(20000); CHECK(count(l1, "THROTTLE HELD -") == 1);
          auto last = [&](const char *box) { std::string v = "<never>"; const std::string k = std::string(box) + "="; for (auto &t : texts) if (!t.compare(0, k.size(), k)) v = t.substr(k.size()); return v; };
          CurrentView = RXSETUPVIEW1; texts.clear(); StartElrsView(); run(1500);                   // ... and the settings page says it in its line
          CHECK(CurrentView == ELRSVIEW && last("hint") == "Throttle held: the module has not said its channel detail."); EndElrsView(); CurrentView = FRONTVIEW; }
        moduleDeaf = false;
        away(); moduleLists = false; { const size_t l1 = logLines.size(); ElrsModel = true; run(15000); CHECK(!freeNow() && count(l1, "THROTTLE HELD -") == 0); }
        moduleLists = true;
        // 5. A THROTTLE THAT IS NOT CHANNEL 5 is never held by this - and MOTOR OFF MEANS MOTOR OFF on a buddy master with its buddy
        //    switch on: the transmitter's own rule leaves the throttle alone there (the pupil's channels are flown), an ELRS model
        //    has no pupil, and the master's stick flew the motor with its motor switch off
        away(); MotorChannel = 3; stick[3] = 1700; stick[4] = 1500; setMode(false); ElrsModel = true; run(600); CHECK(ElrsCarries() && freeNow());
        run(8000); modelHeard = true; run(1500); CHECK(LedWasGreen && Connected && freeNow());
        { SafetyON = false; run(50); airborne = true; BuddyState = 1;
          size_t m1 = mark(); run(2000); Seen s1 = seen(m1);
          CHECK(!MotorEnabled && s1.rc >= 495 && s1.motorLow == s1.rc && s1.motorFollows == 0 && s1.follow == s1.rc);
          motorSwitchOn = true; run(300); m1 = mark(); run(2000); s1 = seen(m1);
          CHECK(MotorEnabled && s1.rc >= 495 && s1.motorFollows >= s1.rc - 14);                    // (the motor switch on: the master's own stick, as ever)
          BuddyState = 0; down(); }
        // 6. A RESTART IN FLIGHT: the stamp said the throttle was not held two seconds before - it flies on from the first frame,
        //    with nothing asked and nothing written; without that word in the stamp it is held; and the word without a restart
        //    in flight frees nothing
        MotorChannel = 4; stick[4] = 1700; stick[3] = 1500; setMode(true);
        for (int freeBefore = 1; freeBefore >= 0; --freeBefore)
        {
            away(); modelHeard = true;
            FlightRestart = true; FlightRestartElrsCarried = freeBefore != 0; SafetyON = false; airborne = true; motorSwitchOn = true; MotorEnabled = true; MotorWasEnabled = true;
            const int r1 = moduleReads; ElrsModel = true; run(1500); size_t m1 = mark(); run(2000); Seen s1 = seen(m1);
            CHECK(MotorEnabled && s1.rc >= 495 && moduleReads == r1 && freeNow() == (freeBefore != 0));
            if (freeBefore) CHECK(s1.motorFollows >= s1.rc - 14 && s1.motorLow <= 14); else CHECK(s1.motorLow == s1.rc && s1.motorFollows == 0);
            FlightRestart = false; FlightRestartElrsCarried = false;
        }
        away(); FlightRestartElrsCarried = true; ElrsModel = true; run(600); CHECK(ElrsCarries() && !freeNow()); FlightRestartElrsCarried = false;
        run(9000); CHECK(freeNow() && ElrsModuleCarries());                                 // (and then the list is read, on the ground: free - and the stamp may say so)
        //    AS setup() REALLY GOES (the fifth review: the scenes above put the motor switch "on" by hand before the first frame): the
        //    transmitter starts with the motor switch and the arming at "off", its setup waits for seconds - flying nothing - and
        //    takes the switches as they stand in its last lines. Not one frame says "motor off" to a model that was flying.
        { away(); modelHeard = true;
          ElrsSetupDone = false; FlightRestart = true; FlightRestartElrsCarried = true; SafetyON = false; airborne = true; motorSwitchOn = true; MotorEnabled = false; MotorWasEnabled = false;
          const size_t m0s = mark(); const int r1 = moduleReads; ElrsModel = true;
          CHECK(pinLevels[10] != HIGH); ElrsPowerEarly(); const uint32_t poweredAt = fakeMs; CHECK(pinLevels[10] == HIGH && pin10HighMs == poweredAt);   // (the sixth review) THE MODULE'S POWER AT ONCE, as setup() gives it: it starts while setup goes on
          for (int k = 0; k < 60; ++k) DelayWithDog(50);                                     // setup's waits: three seconds
          CHECK(mark() == m0s && Serial6.begins == Serial6.ends && !freeNow());              // not a frame; the line not even begun
          MotorEnabled = true; MotorWasEnabled = true; ElrsSetupOver();                        // FlightRestartArm (the motor switch as it stands), and setup's last line
          { const uint32_t overAt = fakeMs; const int begins0 = Serial6.begins; run(MODEL_SETTLE_MS + 40);
            CHECK(Serial6.begins == begins0 + 1 && Serial6.beginMs - overAt <= MODEL_SETTLE_MS + 10 && pin10HighMs == poweredAt && pinLevels[10] == HIGH); }   // the line at once (the power has stood for three seconds): not another 0.3 s, and the power not "switched on" again
          run(1500); size_t m1 = mark(); run(2000); Seen s1 = seen(m1); Seen all = seen(m0s);
          CHECK(MotorEnabled && freeNow() && s1.rc >= 495 && s1.motorFollows >= s1.rc - 14 && all.motorLow <= 14 && moduleReads == r1);
          FlightRestart = false; FlightRestartElrsCarried = false; }
        //    THE STAMP'S WORD IS THE MODULE'S, not "this throttle was not held" (the fourth review): a model whose throttle is NOT
        //    channel 5 flies unheld on "Wide" - and its stamp says nothing for the module. After a restart in flight it flies on
        //    (its throttle is not channel 5), and its throttle moved onto channel 5 in that link is HELD: it was live on one bit
        away(); MotorChannel = 3; stick[3] = 1700; stick[4] = 1500; setMode(false); ElrsModel = true; run(9000); modelHeard = true; run(1500);
        CHECK(LedWasGreen && Connected && freeNow() && !ElrsModuleCarries());
        { SafetyON = false; run(50); airborne = true; motorSwitchOn = true; run(800); CHECK(MotorEnabled && !ElrsModuleCarries());
          const bool stamp = ElrsModuleCarries();
          FlightRestart = true; FlightRestartElrsCarried = stamp; ElrsModel = false; run(450); MotorEnabled = true; MotorWasEnabled = true; ElrsModel = true;   // the restart
          run(1500); size_t m1 = mark(); run(1000); Seen s1 = seen(m1);
          CHECK(MotorEnabled && freeNow() && s1.rc >= 245 && s1.motorFollows >= s1.rc - 14);     // it flies on
          MotorChannel = 4; stick[4] = 1700; stick[3] = 1500; pass(); pass(); m1 = mark(); run(1500); s1 = seen(m1);
          CHECK(!freeNow() && s1.rc >= 370 && s1.motorLow == s1.rc && s1.motorFollows == 0);     // onto channel 5, the module's word not known: held
          FlightRestart = false; FlightRestartElrsCarried = false; MotorChannel = 3; stick[3] = 1700; stick[4] = 1500; }
        //    ... and what the stamp is given: the module's word, whatever the throttle's channel
        away(); MotorChannel = 3; setMode(true); ElrsModel = true; run(9000); CHECK(freeNow() && ElrsModuleCarries());          // not channel 5, "16ch Rate/2": said
        away(); MotorChannel = 4; stick[4] = 1700; stick[3] = 1500; setMode(false); ElrsModel = true; run(9000); CHECK(!freeNow() && !ElrsModuleCarries());   // channel 5, "Wide": held, not said
        away(); CHECK(!ElrsModuleCarries()); setMode(true);                                 // (no link: nothing said)
        // 7. NO SAFETY SWITCH, and the motor switch put on before the list is read (a slow module): held - and when it is put
        //    off again the model has NOT "had its motor on": the ground's work goes on, the list is read, the throttle is the pilot's
        away(); safetyDefined = false; SafetyON = false; moduleDelayMs = 150; ElrsModel = true; modelHeard = true; run(2500); CHECK(LedWasGreen && Connected && !freeNow());
        { size_t m1 = mark(); motorSwitchOn = true; airborne = true; run(1500); Seen s1 = seen(m1);
          CHECK(MotorEnabled && s1.rc >= 370 && s1.motorLow == s1.rc && !freeNow());
          motorSwitchOn = false; airborne = false; moduleDelayMs = 6; run(9000); CHECK(!MotorEnabled && freeNow());
          m1 = mark(); motorSwitchOn = true; airborne = true; run(1500); s1 = seen(m1);
          CHECK(MotorEnabled && s1.rc >= 370 && s1.motorFollows >= s1.rc - 14);
          motorSwitchOn = false; airborne = false; modelHeard = false; run(MOTOR_OFF_GRACE_MS + 3000); CHECK(!LedWasGreen); }
        safetyDefined = true; SafetyON = true; ElrsModel = false; run(600);
        // 8. THE THROTTLE'S CHANNEL ITSELF IS CHANGED (Model options) WITH THE SAFETY OFF: moved ONTO channel 5 while the module
        //    says "Wide", it is held from the very next frame - in the air or not: nothing was running on it; moved off again, free
        MotorChannel = 3; stick[3] = 1700; stick[4] = 1500; setMode(false); ElrsModel = true; run(9000); modelHeard = true; run(1500);
        CHECK(LedWasGreen && Connected && freeNow());
        { SafetyON = false; run(50); airborne = true; motorSwitchOn = true; run(600); size_t m1 = mark(); run(1000); Seen s1 = seen(m1);
          CHECK(MotorEnabled && s1.rc >= 245 && s1.motorFollows >= s1.rc - 14);
          MotorChannel = 4; stick[4] = 1700; stick[3] = 1500; pass(); pass(); m1 = mark(); run(2000); s1 = seen(m1);
          CHECK(!freeNow() && s1.rc >= 495 && s1.motorLow == s1.rc && s1.motorFollows == 0 && s1.follow == s1.rc);
          MotorChannel = 3; stick[3] = 1700; stick[4] = 1500; pass(); pass(); m1 = mark(); run(1000); s1 = seen(m1);
          CHECK(freeNow() && s1.motorFollows >= s1.rc - 14);
          down(); }
        // 9. A MODULE SLOW TO TAKE A CHANGE OF PACKET RATE (it says the OLD rate - and the old switch mode - for a second more):
        //    from the write until the change is taken, held at every pass; a module that KEEPS its rate: held while it is asked,
        //    and free again when it has said, three times, what it kept
        away(); MotorChannel = 4; stick[4] = 1700; stick[3] = 1500; setMode(true); ElrsModel = true; run(9000); CHECK(freeNow());
        { CurrentView = RXSETUPVIEW1; StartElrsView(); run(3000); CHECK(CurrentView == ELRSVIEW && freeNow());
          moduleSlowMs = 1200; const int w1 = moduleWrites; ElrsRow0Tapped(); valueList = 3; ElrsPickOk();     // "250Hz", applied 1.2 s after it is asked
          int k = 0; while (moduleWrites == w1 && k < 3000) { pass(); ++k; }
          int freeMoments = 0; for (k = 0; k < 8000; ++k) { if (freeNow()) ++freeMoments; pass(); }
          CHECK(moduleWrites == w1 + 1 && freeMoments == 0 && !freeNow()); moduleSlowMs = 0;         // (it is "Hybrid" now: held on)
          setMode(true); EndElrsView(); CurrentView = FRONTVIEW; }
        away(); ElrsModel = true; run(9000); CHECK(freeNow());
        { CurrentView = RXSETUPVIEW1; StartElrsView(); run(3000);
          moduleKeepsNext = true; const int w1 = moduleWrites, kept1 = moduleKept; ElrsRow0Tapped(); valueList = 3; ElrsPickOk();
          int k = 0; while (moduleWrites == w1 && k < 3000) { pass(); ++k; }
          CHECK(moduleWrites == w1 + 1 && moduleKept == kept1 + 1 && !freeNow());                    // asked: held ...
          run(8000); CHECK(freeNow());                                                              // ... kept, and said so: free again
          EndElrsView(); CurrentView = FRONTVIEW; }
        // 10. A CHANGE OF RATE WHOSE FRAME NEVER WENT (the safety off while it lay in the timer's place): the switch mode was
        //     forgotten for it - held; back on the ground the list is read again and the throttle is free
        { bool tookBack = false;
          for (int attempt = 0; attempt < 12 && !tookBack; ++attempt)
          {
              CurrentView = RXSETUPVIEW1; StartElrsView(); run(3000 + attempt);                              // (another moment of the timer's round each time)
              const int w1 = moduleWrites, r1 = moduleReads; ElrsRow0Tapped(); valueList = 3; ElrsPickOk();
              int k = 0; while (!ElrsOtherLen && k < 50) { pass(); ++k; }
              if (ElrsOtherLen && moduleWrites == w1)
              {
                  SafetyON = false; airborne = true; pass(); pass();
                  if (moduleWrites == w1 && !ElrsOtherLen)
                  {   // taken back, not sent
                      tookBack = true; run(2000);
                      CHECK(!freeNow() && moduleReads == r1 && moduleWrites == w1);
                      SafetyON = true; airborne = false; run(6000);
                      CHECK(freeNow() && moduleReads - r1 == pieces && moduleWrites == w1);
                  }
                  SafetyON = true; airborne = false;
              }
              run(9000); setMode(true); EndElrsView(); CurrentView = FRONTVIEW;
              if (!tookBack) { away(); ElrsModel = true; run(9000); }
          }
          CHECK(tookBack); }
        // 11. THE MODULE CHANGED ELSEWHERE while this link stood (its own WiFi page, another handset) from the one mode to "Wide":
        //     nothing here knows - until its list is read again, which opening the page does. Then: held, said in the log, and the
        //     page's line says what to choose. (The reading-back on opening the page exists for this.)
        away(); MotorChannel = 4; stick[4] = 1700; stick[3] = 1500; setMode(true); ElrsModel = true; run(9000); CHECK(freeNow());
        { const size_t l1 = logLines.size(); setMode(false); run(3000); CHECK(freeNow());            // (not read: not known to have changed)
          CurrentView = RXSETUPVIEW1; texts.clear(); StartElrsView(); run(4000);
          auto last = [&](const char *box) { std::string v = "<never>"; const std::string k = std::string(box) + "="; for (auto &t : texts) if (!t.compare(0, k.size(), k)) v = t.substr(k.size()); return v; };
          CHECK(!freeNow() && last("tn2") == "Wide" && last("hint") == "Throttle is channel 5: it needs 333Hz Full, then 16ch Rate/2.");
          CHECK(count(l1, "ELRS test: THROTTLE HELD - this model's throttle is channel 5, and switch mode 'Wide' carries it as off or on only") == 1);
          EndElrsView(); CurrentView = FRONTVIEW; }
        ElrsModel = false; run(600);
        CHECK(!ElrsCarries() && cardWritesInAir == air0 && otherInAir == other0);
        printf("PASS THE THROTTLE HELD UNTIL THE MODULE HAS SAID: quicker than the list = held (heard, said, shown), and free once it is read; what was said stands through every reading-back; a packet rate written = not known = held; a module with no list = held, said once; motor off is motor off with the buddy switch on; a restart in flight flies on by its stamp only; no safety switch and no dead end\n");
    }
    // ---- A STORM: links begun and ended, the safety and the motor switch thrown, the model coming and going, the settings page
    // opened and its rows changed, the throttle's channel moved, a module quick, slow, deaf or refusing - all at random, for
    // hours of flying time. ONE RULE must hold through all of it: a frame carries a LIVE throttle on channel 5 only while the
    // module's switch mode, as it truly stands at that millisecond, carries channel 5 whole. And while the safety is off
    // nothing is written to the card and nothing but channel frames is sent.
    {
        uint32_t seed = 14112026u; auto rnd = [&](uint32_t n) { seed = seed * 1664525u + 1013904223u; return (seed >> 8) % n; };
        auto setMode = [&](bool whole) { PDATA[0][(size_t)valueAt(PDATA[0])] = whole ? 4 : 3; PDATA[2] = whole ? P3_FULL : P3_STD; PDATA[2][(size_t)valueAt(PDATA[2])] = whole ? 1 : (uint8_t)rnd(2); truthNote(); };
        long framesCh5 = 0, liveOk = 0, liveWrong = 0, heldWhileCarried = 0, steps = 0; int shown = 0, restarts = 0; uint32_t restartAt = 0;
        const int air0 = cardWritesInAir, other0 = otherInAir; uint32_t chMovedMs = 0;
        FlightRestart = false; FlightRestartElrsCarried = false; moduleKeepsNext = false; moduleSlowMs = 0; moduleDropNth = 0; moduleDeaf = false;
        for (int trial = 0; trial < 72; ++trial)
        {
            FlightRestart = false; FlightRestartElrsCarried = false;
            motorSwitchOn = false; airborne = false; SafetyON = true; modelHeard = false; BuddyState = 0; CurrentView = FRONTVIEW; ElrsModel = false; run(700);
            boxes = 0; safetyDefined = rnd(4) != 0; SafetyON = safetyDefined;
            MotorChannel = rnd(4) ? 4 : 3; stick[3] = stick[4] = 1500; stick[MotorChannel] = 1700; chMovedMs = fakeMs;
            setMode(rnd(4) != 0); moduleLists = rnd(8) != 0; moduleDeaf = rnd(12) == 0; moduleDelayMs = rnd(3) == 0 ? 150 : rnd(2) ? 40 : 6; moduleSlowMs = 0; moduleKeepsNext = false;
            ElrsModel = true;
            for (int step = 0; step < 36; ++step, ++steps)
            {
                boxes = 0; boxHook = motorOffInBox;            // (the transmitter's own box "The motor switch is ON": the pilot switches it off, as he must)
                if (FlightRestart && (LedWasGreen || fakeMs - restartAt > 60000)) { FlightRestart = false; FlightRestartElrsCarried = false; }   // (as FlightGuard.h ends it: connected again, or a minute)
                switch (rnd(16))
                {
                case 0: case 1: if (safetyDefined) { const bool off = rnd(5) < 3; if (off && SafetyON) { SafetyON = false; run(50); airborne = true; } else if (!off && !SafetyON) { SafetyON = true; airborne = false; } } break;
                case 2: case 3: motorSwitchOn = rnd(5) < 3; break;
                case 4: modelHeard = rnd(5) < 4; break;
                case 5: if (CurrentView == FRONTVIEW) { CurrentView = RXSETUPVIEW1; StartElrsView(); if (CurrentView == RXSETUPVIEW1) CurrentView = FRONTVIEW; } break;
                case 6: case 7: if (CurrentView == ELRSVIEW) { switch (rnd(4)) { case 0: ElrsRow0Tapped(); break; case 1: ElrsRow1Tapped(); break; case 2: ElrsRow2Tapped(); break; default: ElrsRow3Tapped(); } } break;
                case 8: case 9: if (CurrentView == ELRSPICKVIEW) { valueList = (int)rnd(10); ElrsPickOk(); } break;
                case 10: if (CurrentView == ELRSPICKVIEW) ElrsPickCancel(); else if (CurrentView == ELRSVIEW) { EndElrsView(); CurrentView = FRONTVIEW; } break;
                case 11: moduleDelayMs = rnd(3) == 0 ? 150 : rnd(2) ? 40 : 6; moduleSlowMs = rnd(3) == 0 ? 1200 : 0; moduleKeepsNext = rnd(6) == 0; moduleDropNth = rnd(5) == 0 ? 7 : 0; break;
                case 12: if (rnd(3) == 0) { MotorChannel = MotorChannel == 4 ? 3 : 4; stick[3] = stick[4] = 1500; stick[MotorChannel] = 1700; chMovedMs = fakeMs; }
                         else if (rnd(4) == 0) moduleDeaf = !moduleDeaf; break;
                case 13: if (rnd(5) == 0) { ElrsModel = false; run(400 + rnd(300)); ElrsModel = true; } break;   // the option off and on again: the link begins afresh
                default:
                    if (LedWasGreen && (safetyDefined ? !SafetyON : MotorEnabled))
                    {   // A RESTART IN FLIGHT: the stamp (written while it flew) says what the module had said; the motor switch as it stands
                        const bool stamp = ElrsModuleCarries();
                        FlightRestart = true; FlightRestartElrsCarried = stamp; ElrsModel = false; run(450);
                        MotorEnabled = motorSwitchOn; MotorWasEnabled = motorSwitchOn; ElrsModel = true; restartAt = fakeMs; ++restarts;
                    }
                    break;
                }
                const size_t m1 = mark(); run(20 + rnd(3) * rnd(1500));
                if (MotorChannel != 4) continue;
                size_t ti = 0;
                for (size_t i = m1; i < Serial6.out.size(); ++i)
                {
                    const auto &f = Serial6.out[i]; const uint32_t at = Serial6.outMs[i];
                    if (!isRc(f) || at < chMovedMs + 10) continue;                 // (the copies made before the channel moved are still on their way out)
                    while (ti + 1 < truthLog.size() && truthLog[ti + 1].first <= at) ++ti;
                    while (ti > 0 && truthLog[ti].first > at) --ti;
                    const bool carried = truthLog[ti].second, live = abs(chan(f, 4) - 1000) > 1;
                    ++framesCh5;
                    if (live && carried) ++liveOk;
                    if (!live && carried) ++heldWhileCarried;
                    if (live && !carried)
                    {
                        ++liveWrong;
                        if (shown++ < 6) fprintf(stderr, "  (storm, trial %d step %d, at %u ms: a LIVE throttle on channel 5 (%d us) while the module's switch mode does not carry it; the truth last changed at %u ms)\n", trial, step, (unsigned)at, chan(f, 4), (unsigned)truthLog[ti].first);
                    }
                }
            }
        }
        FlightRestart = false; FlightRestartElrsCarried = false;
        motorSwitchOn = false; run(300); safetyDefined = true; SafetyON = true; airborne = false; modelHeard = false; moduleDeaf = false; moduleKeepsNext = false; moduleSlowMs = 0; moduleDropNth = 0; ElrsModel = false; CurrentView = FRONTVIEW; run(600);
        boxHook = nullptr;
        CHECK(liveWrong == 0);
        CHECK(cardWritesInAir == air0 && otherInAir == other0);
        CHECK(framesCh5 > 100000 && liveOk > 1500 && heldWhileCarried > 1500 && restarts > 10);   // (not an empty storm: the throttle was live often, and held often; restarts in flight among it)
        printf("PASS a storm (%ld random steps, %d restarts in flight among them, %ld frames of a channel-5 throttle looked at): a live throttle only while the module's switch mode truly carried it (%ld frames live, never wrongly); nothing written to the card and nothing but channels sent with the safety off\n", steps, restarts, framesCh5, liveOk);
    }
    printf("%d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'sim.cpp'), 'w').write(SIM)
    if os.environ.get('ELRS_SIM_KEEP'): open(os.environ['ELRS_SIM_KEEP'], 'w').write(SIM)   # (to look at the play's program itself)
    r = subprocess.run(['clang++', '-std=c++17', '-O1', '-w', '-DELRS_TEST', '-fsanitize=address,undefined', '-o', os.path.join(d, 'sim'), os.path.join(d, 'sim.cpp')], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[:6000]); print('FAILED to compile the driver for its run on the Mac'); sys.exit(1)
    try:
        r = subprocess.run([os.path.join(d, 'sim')], capture_output=True, text=True, timeout=120)
        sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
        if r.returncode: problems.append('the driver\'s run on the Mac failed')
    except subprocess.TimeoutExpired:
        problems.append('the driver\'s run on the Mac did not end within two minutes (a wait that never ends)')
# ---- THE SETTING IN THE MODEL'S RECORD: the real ReadModelExtension / SaveModelExtension (SDcard.h) over a fake card, built
# twice - with ELRS (-DELRS_TEST) and as a release has them - and each given the other's records. (The card behaves as
# SdFat does; the harness is dev/test_banks's, cut down to what these two functions need.)
def lift_from(text, head):
    lines = text.split('\n')
    for a_, l in enumerate(lines):
        if l.startswith(head):
            for b_ in range(a_ + 1, len(lines)):
                if lines[b_] == '}': return '\n'.join(lines[a_:b_ + 1]) + '\n'
    raise SystemExit('cannot lift ' + head)
def one_liner(text, head):
    for l in text.split('\n'):
        if l.startswith(head): return l + '\n'
    raise SystemExit('cannot find ' + head)
DEFS = '\n'.join(l for l in defs.split('\n') if re.match(r'#define (TX_EXT_MAGIC|TX_EXT_MAGIC2|TX_EXT_MAGIC3|TX_EXT_MAGIC4|TX_EXT_MAGIC9|CURVE_POINTS_MAX|CURVE_STORE_MAX|CURVE_UNSET|BANKS_USED|BANKS_IN_FILE|BANK_NAMES_N|CHANNELSUSED|MAXMODELNUMBER|TXSIZE|MODELSIZE|DEFAULT_EXPO|EXPONENTIALCURVES|ELRS_MODEL_FLAG) ', l)) + '\n'
DEFS += '\n'.join(l for l in sdc.split('\n') if l.startswith(('#define MODEL_EXT_OFFSET_B113 ', '#define MODEL_EXT2_', '#define TX_EXT_MAGIC7', '#define TX_EXT_MAGIC8', '#define BANKS_BLOCK_LEN', '#define MODEL_MARK_LEN'))) + '\n'
REC = r"""
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>
#include <map>
#define FLASHMEM
#define FASTRUN
#define DMAMEM
""" + DEFS + r"""
int Trims[BANKS_USED + 1][CHANNELSUSED + 1];
uint8_t Exponential[BANKS_USED + 1][CHANNELSUSED + 1], InterpolationTypes[BANKS_USED + 1][CHANNELSUSED + 1], ServoSpeed[BANKS_USED + 1][CHANNELSUSED + 1];
uint8_t CurvePointCount[CHANNELSUSED + 1], CurvePoint[BANKS_USED + 1][CHANNELSUSED + 1][CURVE_POINTS_MAX], CurveStore[BANKS_USED + 1][CHANNELSUSED + 1][CURVE_STORE_MAX];
uint8_t BanksInUse[BANKS_USED] = {0, 1, 2, 3, 32, 33}, DualRateRate[BANKS_USED + 1];
char ModelName[40] = "Bthundr 1"; uint32_t ModelNumber = 1;
bool SixBanks = false, SingleModelFlag = false; uint8_t MaxRangeNarrow = 0;
static bool ModelCrcOn = false, MarkBackedUp = false; static uint32_t ModelCrcAcc = 0xFFFFFFFFu, ModelContentCrc = 0, ModelBackupCrc = 0, ModelBackupEpoch = 0;
#ifdef ELRS_TEST
bool ElrsModel = false;
#endif
static std::vector<uint8_t> card; static long FileCheckSum = 0; static bool DoingCheckSm = false; static int StartLocation = 0, SDCardAddress = 0;
static size_t cardPos = 0; static int seekWriteFails = 0;
struct FakeFile { size_t size() { return card.size(); } };
static FakeFile ModelsFileNumber;
static bool cardSeek(size_t a) { if (a > card.size()) return false; cardPos = a; return true; }
static uint8_t SDRead8BITS(int a) { cardSeek((size_t) a); const uint8_t r = cardPos < card.size() ? card[cardPos++] : 255; if (!DoingCheckSm) FileCheckSum += r * (a + 1); return r; }
static void SDUpdate8BITS(int a, uint8_t v) { if (!cardSeek((size_t) a)) ++seekWriteFails; if (!DoingCheckSm) FileCheckSum += v * (a + 1); if (cardPos >= card.size()) card.resize(cardPos + 1, 0); card[cardPos++] = v; }
static std::map<int, std::vector<uint8_t>> bankFiles;
bool BanksFileRead(uint8_t slot, uint8_t *blk, int n) { auto it = bankFiles.find(slot); if (it == bankFiles.end() || (int) it->second.size() != n) return false; memcpy(blk, it->second.data(), n); return true; }
bool BanksFileWrite(uint8_t slot, const uint8_t *blk, int n) { bankFiles[slot] = std::vector<uint8_t>(blk, blk + n); return true; }
static bool CurveCountOk(uint8_t n) { return n == 3 || n == 5 || n == 7 || n == 9; }
""" + lift_from(util, 'uint8_t CurveN(uint8_t ch)') + 'uint8_t CurveMid(uint8_t n) { return (n - 1) / 2; }\n' \
    + lift_from(util, 'uint8_t CurveStorePos(uint8_t n, uint8_t k)') + lift_from(util, 'void CurveStoreSync(uint8_t b, uint8_t ch)') + lift_from(util, 'void CurveStoreClear(uint8_t b, uint8_t ch)') \
    + lift_from(sdc, 'static uint8_t Ext2Sum(') + lift_from(sdc, 'static void ModelCrcByte(') + lift_from(sdc, 'static void ModelCrcFold(') + 'static uint32_t BackupEpochNow() { return 0; }\n' \
    + one_liner(sdc, 'static uint8_t BanksSlot()') + lift_from(sdc, 'FLASHMEM void BanksCopy(') + lift_from(sdc, 'FLASHMEM static void BanksFromFour()') \
    + lift_from(sdc, 'FLASHMEM static int BanksBlockBuild(') + lift_from(sdc, 'FLASHMEM static bool BanksBlockTake(') \
    + lift_from(sdc, 'FLASHMEM void ReadModelExtension()') + lift_from(sdc, 'FLASHMEM void SaveModelExtension()') + r"""
static const int SEQ = 2111;   // the checked sequence and its checksum, as measured on a real models.dat
static uint32_t seed = 13112026;
static uint32_t rnd() { seed = seed * 1103515245u + 12345u; return seed >> 8; }
static void model(bool curves, bool six, bool narrow) {   // a model in memory, the same every time
    seed = 13112026;
    for (int ch = 0; ch < CHANNELSUSED; ++ch) {
        CurvePointCount[ch] = (curves && ch == 3) ? 7 : 5;
        for (int b = 1; b <= BANKS_USED; ++b) { for (int k = 0; k < CURVE_POINTS_MAX; ++k) CurvePoint[b][ch][k] = k < CurvePointCount[ch] ? (uint8_t)(rnd() % 181) : 0; CurveStoreClear(b, ch); CurveStoreSync(b, ch); for (int s = 0; s <= 8; s += 2) if (CurveStore[b][ch][s] == CURVE_UNSET) CurveStore[b][ch][s] = 90; }
    }
    for (int b = 0; b <= BANKS_USED; ++b) for (int i = 0; i < CHANNELSUSED + 1; ++i) { Trims[b][i] = 40 + rnd() % 81; ServoSpeed[b][i] = 1 + rnd() % 100; Exponential[b][i] = 1 + rnd() % 200; InterpolationTypes[b][i] = rnd() % 3; }
    for (int b = 0; b < BANKS_USED; ++b) { BanksInUse[b] = rnd() % BANK_NAMES_N; DualRateRate[b] = rnd() % 4; }
    MaxRangeNarrow = narrow; SixBanks = six;
}
static void asTheSequenceLeavesIt() {   // ReadOneModel before the extension: five points a channel, the five of old in the store, nothing else remembered
    seed = 4242;
    for (int ch = 0; ch < CHANNELSUSED; ++ch) { CurvePointCount[ch] = 5; for (int b = 1; b <= BANKS_USED; ++b) { for (int k = 0; k < CURVE_POINTS_MAX; ++k) CurvePoint[b][ch][k] = k < 5 ? (uint8_t)(rnd() % 181) : 0; CurveStoreClear(b, ch); CurveStoreSync(b, ch); } }
    MaxRangeNarrow = 0; SixBanks = false;
}
static uint32_t hashFour() { uint32_t h = 2166136261u; auto f = [&](uint8_t v) { h = (h ^ v) * 16777619u; }; for (int c = 0; c < CHANNELSUSED; ++c) { f(CurvePointCount[c]); for (int b = 1; b <= 4; ++b) { for (int k = 0; k < CURVE_POINTS_MAX; ++k) f(CurvePoint[b][c][k]); for (int s = 0; s < CURVE_STORE_MAX; ++s) f(CurveStore[b][c][s]); } } f(MaxRangeNarrow); return h; }
static uint32_t hashFiveSix() { uint32_t h = 2166136261u; auto f = [&](uint8_t v) { h = (h ^ v) * 16777619u; }; for (int b = 5; b <= 6; ++b) for (int c = 0; c < CHANNELSUSED; ++c) { f((uint8_t)Trims[b][c]); f(ServoSpeed[b][c]); f(Exponential[b][c]); for (int s = 0; s < CURVE_STORE_MAX; ++s) f(CurveStore[b][c][s]); } return h; }
static void load(const char *path) { card.clear(); FILE *f = fopen(path, "rb"); if (f) { int c; while ((c = fgetc(f)) != EOF) card.push_back((uint8_t)c); fclose(f); } }
static void store(const char *path) { FILE *f = fopen(path, "wb"); fwrite(card.data(), 1, card.size(), f); fclose(f); }
static void place(int kind) { SingleModelFlag = kind == 1; StartLocation = kind == 1 ? 0 : TXSIZE + 2 * (MODELSIZE); SDCardAddress = StartLocation + SEQ; FileCheckSum = 0; }
static int headerAt() {   // where the six-banks header is, or -1
    const int a = StartLocation + SEQ; if ((int)card.size() < a + 3 || card[a] != 0x5A) return -1;
    int pos = a + 3; if ((int)card.size() >= pos + 2 && card[pos] == 0x5A && (card[pos + 1] == 0xC6 || card[pos + 1] == 0xC5)) pos += card[pos + 1] == 0xC6 ? MODEL_EXT2_LEN : MODEL_EXT2_LEN_B118;
    return ((int)card.size() >= pos + 4 && card[pos] == 0x5A && card[pos + 1] == 0xC7) ? pos : -1;
}
int main(int argc, char **argv)
{
    if (argc < 4) return 2;
    const std::string what = argv[1]; const char *path = argv[2]; const int kind = atoi(argv[3]);
    if (what == "new") {            // new <file> <kind> <curves> <six> <narrow> <elrs> <bare>: a record never saved by any extension
        card.clear();
        if (kind == 1) { seed = 99; for (int i = 0; i < SEQ; ++i) card.push_back((uint8_t)rnd()); }
        else { card.assign(TXSIZE + 5 * (MODELSIZE), 0); seed = 99; for (int i = 0; i < SEQ; ++i) card[TXSIZE + 2 * (MODELSIZE) + i] = (uint8_t)rnd(); }
        store(path); return 0;
    }
    load(path); place(kind);
    if (what == "save") {           // save <file> <kind> <curves> <six> <narrow> <elrs>
        model(atoi(argv[4]), atoi(argv[5]), atoi(argv[6]));
#ifdef ELRS_TEST
        ElrsModel = atoi(argv[7]) != 0;
#endif
        ModelCrcOn = true; ModelCrcAcc = 0xFFFFFFFFu;
        SaveModelExtension();
        store(path);
    } else if (what == "resave") {  // read it, and save it again as a firmware does when the model is saved
        asTheSequenceLeavesIt(); ReadModelExtension(); place(kind);
        ModelCrcOn = true; ModelCrcAcc = 0xFFFFFFFFu;
        SaveModelExtension();
        store(path);
    } else if (what == "flip") {    // spoil the header's checksum
        const int h = headerAt(); if (h >= 0) { card[h + 3] ^= 0x10; store(path); }
        return 0;
    } else { asTheSequenceLeavesIt(); ReadModelExtension(); }
    const int h = headerAt();
    int elrs = -1;
#ifdef ELRS_TEST
    elrs = ElrsModel ? 1 : 0;
#endif
    printf("six=%d elrs=%d narrow=%d four=%08x fivesix=%08x crc=%08x header=%d flags=%d size=%d seekfails=%d\n", SixBanks ? 1 : 0, elrs, MaxRangeNarrow, hashFour(), hashFiveSix(), ModelContentCrc,
           h >= 0 ? h - (StartLocation + SEQ) : -1, h >= 0 ? card[h + 2] : -1, (int)card.size(), seekWriteFails);
    return 0;
}
"""
rec_checks = 0
def rcheck(c, what):
    global rec_checks
    rec_checks += 1
    if not c: problems.append('the model record: ' + what)
with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'rec.cpp'), 'w').write(REC)
    exe = {}
    for name, flags in (('elrs', ['-DELRS_TEST']), ('release', [])):
        r = subprocess.run(['clang++', '-std=c++17', '-O1', '-w'] + flags + ['-o', os.path.join(d, name), os.path.join(d, 'rec.cpp')], capture_output=True, text=True)
        if r.returncode: print(r.stderr[:4000]); print('FAILED to compile the model record test (' + name + ')'); sys.exit(1)
        exe[name] = os.path.join(d, name)
    def run(build, *args):
        r = subprocess.run([exe[build]] + [str(a) for a in args], capture_output=True, text=True)
        if r.returncode: raise SystemExit('the model record test fell over: ' + ' '.join(str(a) for a in args) + ' ' + r.stderr[:300])
        return dict(kv.split('=') for kv in r.stdout.split()) if r.stdout.strip() else {}
    def data(f): return open(f, 'rb').read()
    for kind in (0, 1):                       # models.dat's slot, and a .MOD
        for curves in (0, 1):                 # with the curves' block, and without
            f1, f2, f3 = (os.path.join(d, n) for n in ('a.bin', 'b.bin', 'c.bin'))
            tag = ('.MOD' if kind else 'models.dat') + (' with curves' if curves else '')
            # an LDRC model: this build writes EXACTLY what a release writes
            run('elrs', 'new', f1, kind); run('release', 'new', f2, kind)
            a_ = run('elrs', 'save', f1, kind, curves, 0, 1, 0); b_ = run('release', 'save', f2, kind, curves, 0, 1, 0)
            rcheck(data(f1) == data(f2) and a_['crc'] == b_['crc'], tag + ': an LDRC model is saved byte for byte as a release saves it')
            rcheck(run('elrs', 'read', f1, kind)['elrs'] == '0', tag + ': an LDRC model reads as LDRC')
            # an ELRS model: the header with bit 1, read back as ELRS; a release reads the same model and knows nothing of it
            run('elrs', 'new', f1, kind)
            e_ = run('elrs', 'save', f1, kind, curves, 0, 1, 1)
            rcheck(e_['flags'] == '2' and e_['header'] == str(3 + (851 if curves else 0)) and e_['seekfails'] == '0', tag + ': an ELRS model writes the header, flags 2, after the curves')
            rcheck(e_['crc'] != a_['crc'], tag + ': its content CRC says the setting changed')
            r1 = run('elrs', 'read', f1, kind); r2 = run('release', 'read', f1, kind)
            rcheck(r1['elrs'] == '1' and r1['six'] == '0' and r1['narrow'] == '1' and r1['crc'] == e_['crc'] and (r1['four'] == a_['four'] or not curves), tag + ': read back as ELRS, four banks, the same curves')
            rcheck(r2['six'] == '0' and r2['narrow'] == '1' and r2['four'] == r1['four'] and r2['crc'] == e_['crc'], tag + ': a release reads the same curves, range and mark from an ELRS model\'s record')
            # a release SAVES it: the bit goes, everything else stays; then it is LDRC here too
            import shutil; shutil.copy(f1, f3)
            s_ = run('release', 'resave', f3, kind)
            rcheck(s_['flags'] == '0' and s_['four'] == r1['four'] and s_['narrow'] == '1' and len(data(f3)) == len(data(f1)), tag + ': a release\'s save drops the bit and nothing else')
            rcheck(run('elrs', 'read', f3, kind)['elrs'] == '0', tag + ': after a release\'s save it is an LDRC model')
            # saved again here as ELRS (the header is there): the bit comes back in the same place, the file no longer
            shutil.copy(f1, f3); t_ = run('elrs', 'resave', f3, kind)
            cut = (0 if kind else 512 + 2 * 3072) + 2111 + int(e_['header']) + 4    # up to the mark (whose CRC is of the curves in memory: with no curves' block this harness has not the saved model's, as the real sequence would give)
            rcheck(t_['flags'] == '2' and t_['elrs'] == '1' and len(data(f3)) == len(data(f1)) and data(f3)[:cut] == data(f1)[:cut] and (data(f3) == data(f1) or not curves), tag + ': saved again unchanged, byte for byte')
            # set back to LDRC here: the header stays, saying nothing
            u_ = run('elrs', 'save', f1, kind, curves, 0, 1, 0)
            rcheck(u_['flags'] == '0' and run('elrs', 'read', f1, kind)['elrs'] == '0', tag + ': set back to LDRC')
            # a header whose checksum is wrong is not believed
            run('elrs', 'new', f1, kind); run('elrs', 'save', f1, kind, curves, 0, 0, 1); run('elrs', 'flip', f1, kind)
            rcheck(run('elrs', 'read', f1, kind)['elrs'] == '0', tag + ': a header that is not sound means LDRC')
        # a record nobody has added to: LDRC, and saved as LDRC nothing is added to it
        f1 = os.path.join(d, 'n.bin'); run('elrs', 'new', f1, kind); before = data(f1)
        rcheck(run('elrs', 'read', f1, kind)['elrs'] == '0', 'a record with nothing after its checksum is an LDRC model')
        if kind == 1:
            run('elrs', 'save', f1, kind, 0, 0, 0, 0); rcheck(data(f1) == before, 'a bare .MOD saved as LDRC is not made longer')
            g_ = run('elrs', 'save', f1, kind, 0, 0, 0, 1); rcheck(g_['flags'] == '2' and len(data(f1)) == len(before) + 3 + 4 + 15 and g_['seekfails'] == '0', 'a bare .MOD saved as ELRS gains the three parts, by appending')
    # six banks AND ELRS, in a .MOD (the banks' block in-line): both read back, banks 5 and 6 whole; a release reads six banks
    f1 = os.path.join(d, 's.bin'); run('elrs', 'new', f1, 1); x_ = run('elrs', 'save', f1, 1, 1, 1, 0, 1)
    y_ = run('elrs', 'read', f1, 1); z_ = run('release', 'read', f1, 1)
    rcheck(x_['flags'] == '3' and y_['six'] == '1' and y_['elrs'] == '1' and y_['fivesix'] == x_['fivesix'] and y_['four'] == x_['four'], 'six banks and ELRS together: flags 3, both read back, banks 5 and 6 whole')
    rcheck(z_['six'] == '1' and z_['fivesix'] == x_['fivesix'] and z_['four'] == x_['four'], 'a release reads the six banks of an ELRS model\'s .MOD')
if not any(p_.startswith('the model record') for p_ in problems):
    print('PASS the setting in the model\'s record (%d checks, the real save and load, built with ELRS and as a release): an LDRC model is saved byte for byte as a release saves it; an ELRS model is read as one here and flies on LDRC under a release, whose save drops the bit and nothing else' % rec_checks)
# THE PAGE (the screen's own project, when it is beside this one): Model options has the switch and its label, and HIDES
# both by itself at every load - so a transmitter whose firmware has no ELRS shows nothing of them, and cannot be touched there
import json
SCREEN = os.path.join(ROOT, '..', 'ESP32-board2', 'board4', 'nextion-emulator')
pg9_path = os.path.join(SCREEN, 'sd', 'hmi', 'pages', '9.json')
if os.path.exists(pg9_path):
    pg9 = json.load(open(pg9_path)); by9 = {c['n']: c for c in pg9['comps']}
    pre = pg9.get('ev', {}).get('preinitialize', '').split('\n')
    if not ('c4' in by9 and by9['c4']['t'] == 'switch' and 'l_t6' in by9 and by9['l_t6']['t'] == 'text' and by9['l_t6']['txt'] == 'ELRS receiver (off: LDRC)'): problems.append('page 9: the switch c4 and its label l_t6 "ELRS receiver (off: LDRC)"')
    elif 'vis c4,0' not in pre or 'vis l_t6,0' not in pre: problems.append('page 9: its own start-up lines must hide c4 and l_t6 (a firmware without ELRS never shows them)')
    elif by9['c4'].get('ev') or by9['l_t6'].get('ev'): problems.append('page 9: the switch and its label carry no script of their own')
    elif len({c['i'] for c in pg9['comps']}) != len(pg9['comps']) or len(by9) != len(pg9['comps']): problems.append('page 9: every component its own id and name')
    else:
        def over(a, b): return a['x'] < b['x'] + b['w'] and b['x'] < a['x'] + a['w'] and a['y'] < b['y'] + b['h'] and b['y'] < a['y'] + a['h']
        clash = [c['n'] for c in pg9['comps'] if c['n'] not in ('c4', 'l_t6', 'card', 't0') and 'x' in c and c['x'] >= 0 and (over(c, by9['c4']) or over(c, by9['l_t6']))]
        if clash: problems.append('page 9: the new row lies over ' + ', '.join(clash))
        else: print('PASS page 9 (Model options): the switch "ELRS receiver (off: LDRC)" is there, hidden by the page itself until this firmware shows it, and lies over nothing')
else:
    print('NOTE the screen\'s project is not beside this one: page 9 not looked at')
# THE PAGE "ELRS settings" AND THE CODES THAT REACH IT (14 Nov 2026). The button table of main.cpp, as a TEST build's compiler
# sees it and as a RELEASE's does: a release keeps its 261 entries; a test build has 269, the last eight the page's, in the
# order of their codes. And the screen's pages send exactly those codes, from parts with the names the main board writes to.
main_raw = src('src/main.cpp')
def view(text, test):   # the lines a compiler sees, with (test) or without ELRS_TEST
    out, state = [], None
    for l in text.split('\n'):
        t = l.strip()
        if state is None and t.startswith('#ifdef ELRS_TEST'): state = 'test'; continue
        if state == 'test' and t.startswith('#else'): state = 'else'; continue
        if state is not None and t.startswith('#endif'): state = None; continue
        if state == ('else' if test else 'test'): continue
        out.append(l)
    return '\n'.join(out)
ELRS_CODES = ['StartElrsView', 'EndElrsView', 'ElrsRow0Tapped', 'ElrsRow1Tapped', 'ElrsRow2Tapped', 'ElrsRow3Tapped', 'ElrsPickOk', 'ElrsPickCancel']
for test, want in ((True, 269), (False, 261)):
    v = view(main_raw, test); t0 = v.index('void (*NumberedFunctions1[LASTFUNCTION1])(){')
    entries = [e.strip() for e in re.sub(r'//[^\n]*', '', v[v.index('){', t0) + 2:v.index('};', t0)]).split(',') if e.strip()]
    last = int(re.search(r'#define LASTFUNCTION1 (\d+)', v).group(1))
    if last != want or len(entries) != last: problems.append('main.cpp: as a %s build sees it the button table has %d entries and LASTFUNCTION1 is %d (both should be %d)' % ('test' if test else 'release', len(entries), last, want))
    elif test and entries[261:] != ELRS_CODES: problems.append('main.cpp: the test build\'s last eight button codes (261-268) are the ELRS page\'s, in order: found ' + repr(entries[261:]))
    elif not test and any(e.startswith('Elrs') or 'Elrs' in e for e in entries): problems.append('main.cpp: a release has none of the ELRS page\'s codes')
defs = src('include/1Definitions.h')
if not re.search(r'#define ELRSVIEW 90\b', view(defs, True)) or not re.search(r'#define ELRSPICKVIEW 91\b', view(defs, True)) or 'ELRSVIEW' in view(defs, False): problems.append('1Definitions.h: the page\'s two view numbers (90, 91), in test builds only')
if '{ELRSVIEW, "ElrsView"}, {ELRSPICKVIEW, "ElrsPickView"}' not in view(util, True) or 'ELRSVIEW' in view(util, False): problems.append('Utilities.h: the page and its picker, each by its own name (the screen puts a page back as it was after its screen saver), in test builds only')
p90, p91 = os.path.join(SCREEN, 'sd', 'hmi', 'pages', '90.json'), os.path.join(SCREEN, 'sd', 'hmi', 'pages', '91.json')
if os.path.exists(pg9_path) and os.path.exists(p90) and os.path.exists(p91):
    def codes_of(pg): return {c['n']: int(m.group(1)) for c in pg['comps'] for m in [re.search(r'va0\.val=(\d+)<<8\s*\nprint va0\.val', c.get('ev', {}).get('r', ''))] if m}
    g90, g91, g9 = json.load(open(p90)), json.load(open(p91)), json.load(open(pg9_path))
    n90, n91 = {c['n']: c for c in g90['comps']}, {c['n']: c for c in g91['comps']}
    want90 = {'tn0': 263, 'tn1': 264, 'tn2': 265, 'tn3': 266, 'b1': 262}
    bad = []
    if g90.get('name') != 'ElrsView' or g90.get('id') != 90 or codes_of(g90) != want90: bad.append('page 90 ElrsView: its four rows send 263-266 and its OK 262, and nothing else sends a code (found %r)' % codes_of(g90))
    if not {'t0', 't9', 't11', 'hint', 'va0', 'tn0', 'tn1', 'tn2', 'tn3'} <= set(n90): bad.append('page 90: the parts the main board writes to (t9, t11, tn0-tn3, hint)')
    if g91.get('name') != 'ElrsPickView' or g91.get('id') != 91 or codes_of(g91) != {'b3': 267, 'b1': 268} or n91.get('list', {}).get('t') != 'textselect' or n91['b3'].get('txt') != 'OK' or n91['b1'].get('txt') != 'Cancel':
        bad.append('page 91 ElrsPickView: a wheel "list", OK sends 267 and Cancel 268')
    b9 = {c['n']: c for c in g9['comps']}
    if 'bElrs' not in b9 or codes_of(g9).get('bElrs') != 261 or 'vis bElrs,0' not in g9['ev'].get('preinitialize', '').split('\n'): bad.append('page 9: the button bElrs sends 261 and is hidden by the page itself until this firmware shows it')
    else:
        def over2(a, b): return a['x'] < b['x'] + b['w'] and b['x'] < a['x'] + a['w'] and a['y'] < b['y'] + b['h'] and b['y'] < a['y'] + a['h']
        clash = [c['n'] for c in g9['comps'] if c['n'] not in ('bElrs', 'card', 't0') and 'x' in c and c.get('x') is not None and c['x'] >= 0 and over2(c, b9['bElrs'])]
        if clash: bad.append('page 9: the button lies over ' + ', '.join(clash))
    for pg in (g90, g91):
        if len({c['i'] for c in pg['comps']}) != len(pg['comps']) or len({c['n'] for c in pg['comps']}) != len(pg['comps']): bad.append('page %d: every part its own id and name' % pg['id'])
    ix = json.load(open(os.path.join(SCREEN, 'sd', 'hmi', 'index.json')))
    names = {q['id']: q['name'] for q in ix['pages']}
    if names.get(90) != 'ElrsView' or names.get(91) != 'ElrsPickView': bad.append('the screen\'s index names pages 90 and 91 (it finds a page by its name there)')
    if '"vis bElrs,1"' not in drv or 'page ElrsView' not in drv or 'page ElrsPickView' not in drv: bad.append('ElrsCrsf.h: the page, its picker and the button are called by the names the screen has')
    problems += bad
    if not bad: print('PASS the page "ELRS settings" on the screen (pages 90 and 91, the button on Model options): the codes the pages send are the test build\'s 261-268 and nothing else; a release\'s button table is its own 261 entries')
else:
    print('NOTE the screen\'s project is not beside this one: pages 90 and 91 not looked at')
# EASILY REMOVED (Malcolm, 11 Nov 2026): every mention of ELRS outside ElrsCrsf.h sits inside #ifdef ELRS_TEST, so the
# whole thing comes out with this file, ElrsCrsf.h and those blocks. Each one is listed, and any other is a failure.
touch = []
for root, _, files in os.walk(TC):
    if os.sep + '.pio' in root: continue
    for fn in files:
        if not fn.endswith(('.h', '.cpp', '.ino', '.c')) or fn == 'ElrsCrsf.h': continue
        path = os.path.join(root, fn); lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
        depth = 0; guard = []
        for n, line in enumerate(lines, 1):
            s = line.strip()
            if s.startswith('#if'): guard.append('ELRS_TEST' in s)
            elif s.startswith('#endif') and guard: guard.pop()
            if re.search(r'elrs', line, re.I):
                rel = os.path.relpath(path, TC)
                if any(guard): touch.append(f'{rel}:{n}')
                else: problems.append(f'{rel}:{n} mentions ELRS outside #ifdef ELRS_TEST: {s[:80]}')
print('PASS the ELRS lines outside ElrsCrsf.h, all inside #ifdef ELRS_TEST:', ', '.join(touch) if touch else 'none')
if problems:
    for p in problems: print('FAIL', p)
    print('FAILED'); sys.exit(1)
print('PASS main.cpp: the driver is in test builds only (-DELRS_TEST); a release is unchanged')
print('ALL PASS')
