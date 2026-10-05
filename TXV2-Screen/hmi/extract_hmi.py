#!/usr/bin/env python3
"""
extract_hmi.py - reverse-engineered reader for Nextion Editor .HMI project files
(Intelligent series, editor build 1.6x, as used for the LDRC V1 transmitter).

Usage:
    python3 extract_hmi.py "<path to TX_NEXTION.HMI>" [output dir]

Writes (into the output dir, default = the directory of this script):
    pages.json      every page: name, id, background, components, event code
    fonts.json      font id -> name / height / charset
    pictures/NN.png original PNG for picture id NN (from the *.is members)
    audio/NN.wav    audio id NN (from the *.wav members)
    resources.json  the raw member directory + the resource-id tables

See README.md next to this file for the file-format description.
The source file is opened read-only and never modified.
"""
import json
import os
import struct
import sys

# ---------------------------------------------------------------------------
# 1. Container (the .HMI itself)
# ---------------------------------------------------------------------------

DIR_ENTRY = 28          # bytes per directory entry
DIR_NAME = 16           # name field (NUL padded); deleted entries have name[0] == 0


def read_directory(data):
    """Return {name: (offset, size)} for live members, plus a list of all entries."""
    count = struct.unpack_from('<I', data, 0)[0]
    live, entries = {}, []
    for i in range(count):
        o = 4 + DIR_ENTRY * i
        raw = data[o:o + DIR_NAME]
        off, size = struct.unpack_from('<II', data, o + DIR_NAME)
        flags = data[o + DIR_NAME + 8:o + DIR_ENTRY]
        deleted = flags[0] != 0
        name = raw.rstrip(b'\0').decode('latin1')
        entries.append({'index': i, 'name': name, 'offset': off, 'size': size,
                        'flags': flags.hex(), 'deleted': deleted})
        if not deleted:
            live[name] = (off, size)
    return live, entries


# ---------------------------------------------------------------------------
# 2. main.HMI - resource id tables (picture / font / audio / page order)
# ---------------------------------------------------------------------------

def parse_main(blob):
    """main.HMI: 0x60-byte header then N x 16-byte entries:
       8 bytes extension (NUL padded, byte 7 = flag), 8 bytes member file name."""
    table_off, count = struct.unpack_from('<II', blob, 0x18)
    ids = {'i': [], 'zi': [], 'wav': [], 'pa': []}
    for n in range(count):
        e = blob[table_off + 16 * n: table_off + 16 * n + 16]
        ext = e[:7].rstrip(b'\0').decode('latin1')
        name = e[8:16].rstrip(b'\0').decode('latin1')
        ids.setdefault(ext, []).append(name)
    return ids


# ---------------------------------------------------------------------------
# 3. Page files (NN.pa)
# ---------------------------------------------------------------------------

def parse_page(blob):
    """NN.pa: 0x38 header, object table (12 bytes/object), then objects.
       Object = u32 len + 'att-N' + N attribute records + code sections + u32 0.
       Attribute record = u32 len, 16-byte NUL-padded name, (len-16) value bytes.
       Code section = u32 len + 'codes<event>-<lines>' + <lines> x (u32 len + text)."""
    size, hdr, nobj = struct.unpack_from('<III', blob, 4)
    page_name = blob[0x18:0x28].rstrip(b'\0').decode('latin1')
    table = [struct.unpack_from('<III', blob, 0x38 + 12 * i) for i in range(nobj)]
    objs = []
    for rel, sz, _ in table:
        p = 0x38 + rel
        end = p + sz
        L = struct.unpack_from('<I', blob, p)[0]; p += 4
        tag = blob[p:p + L]; p += L
        if not tag.startswith(b'att-'):
            raise ValueError('expected att- tag at 0x%x, got %r' % (p - L, tag))
        attrs = []
        for _ in range(int(tag[4:])):
            L = struct.unpack_from('<I', blob, p)[0]; p += 4
            name = blob[p:p + 16].rstrip(b'\0').decode('latin1')
            attrs.append((name, blob[p + 16:p + L]))
            p += L
        codes = {}
        while True:
            L = struct.unpack_from('<I', blob, p)[0]; p += 4
            if L == 0:
                break
            s = blob[p:p + L].decode('latin1'); p += L
            if not s.startswith('codes'):
                raise ValueError('expected codes tag at 0x%x, got %r' % (p - L, s))
            key, cnt = s[5:].rsplit('-', 1)
            lines = []
            for _ in range(int(cnt)):
                L = struct.unpack_from('<I', blob, p)[0]; p += 4
                lines.append(blob[p:p + L].decode('utf-8', 'replace')); p += L
            codes[key] = lines
        if p != end:
            raise ValueError('object end mismatch 0x%x != 0x%x' % (p, end))
        objs.append((attrs, codes))
    return page_name, objs


TYPE_NAMES = {          # 'type' attribute byte -> component kind (Nextion Intelligent series)
    121: 'page',
    116: 'text',
    54: 'number',
    98: 'button',
    53: 'dual-state button',
    112: 'picture',
    106: 'progress bar',
    1: 'slider',
    109: 'hotspot',
    51: 'timer',
    52: 'variable',
    56: 'checkbox',
    57: 'radio',
    4: 'audio',
    60: 'external picture',
    61: 'combobox',
    62: 'sltext',            # scrollable multi-line text box (val_y / maxval_y)
    67: 'switch',
    68: 'textselect',        # list box: options in 'path', row height 'hig', selected 'val'
    # not present in this project, from the Nextion docs:
    55: 'scrolling text', 59: 'xfloat', 58: 'crop', 122: 'gauge', 0: 'waveform', 5: 'video',
}

STRING_ATTRS = {'objname', 'txt', 'path'}
SIGNED16 = {'x', 'y', 'movex', 'movey', 'endx', 'endy'}   # negative = parked off-screen
COLOUR_ATTRS = {'bco', 'pco', 'bco1', 'pco1', 'bco2', 'pco2', 'pco3', 'borderc'}
EVENT_NAMES = {
    'load': 'preinitialize', 'loadend': 'postinitialize',
    'down': 'touch_press', 'up': 'touch_release', 'unload': 'page_exit',
    'slide': 'touch_move', 'timer': 'timer', 'playend': 'play_end',
}
PAGE_STA = {0: 'no background', 1: 'solid colour', 2: 'image'}   # 0 = overlay, previous page stays
COMP_STA = {0: 'crop image', 1: 'solid colour', 2: 'image', 3: 'none'}


def rgb565_hex(v):
    r = (v >> 11) & 0x1f
    g = (v >> 5) & 0x3f
    b = v & 0x1f
    return '#%02x%02x%02x' % ((r * 255 + 15) // 31, (g * 255 + 31) // 63, (b * 255 + 15) // 31)


def decode_value(name, raw):
    if name in STRING_ATTRS:
        return raw.decode('utf-8', 'replace')
    n = len(raw)
    if n == 1:
        return raw[0]
    if n == 2:
        if name in SIGNED16:
            return struct.unpack('<h', raw)[0]
        return struct.unpack('<H', raw)[0]
    if n == 4:
        return struct.unpack('<i', raw)[0]
    return raw.hex()


def component_json(attrs, codes):
    a = {name: decode_value(name, raw) for name, raw in attrs}
    t = a['type']
    c = {
        'name': a['objname'],
        'id': a['id'],
        'type': TYPE_NAMES.get(t, 'unknown-%d' % t),
        'type_code': t,
        'scope': 'global' if a.get('vscope') == 1 else 'local',
    }
    for k in ('x', 'y', 'w', 'h'):
        if k in a:
            c[k] = a[k]
    colours = {}
    for k in COLOUR_ATTRS:
        if k in a:
            colours[k] = {'rgb565': a[k], 'hex': rgb565_hex(a[k])}
    if colours:
        c['colours'] = colours
    if 'font' in a:
        c['font'] = a['font']
    if 'txt' in a:
        c['txt'] = a['txt']
    if 'val' in a:
        c['val'] = a['val']
    pics = {k: (None if a[k] == 0xffff else a[k])
            for k in ('pic', 'picc', 'pic1', 'picc1', 'pic2', 'picc2', 'bpic', 'ppic') if k in a}
    if pics:
        c['pictures'] = pics
    if 'sta' in a:
        c['sta'] = a['sta']
        c['sta_name'] = (PAGE_STA if t == 121 else COMP_STA).get(a['sta'], str(a['sta']))
    # everything else, raw (style, xcen, ycen, borderw, key, pw, isbr, spax, spay, lenth,
    # format, dez, dis, mode, wid, hig, maxval, minval, tim, en, path, path_m, ...)
    skip = {'type', 'id', 'objname', 'vscope', 'x', 'y', 'w', 'h', 'font', 'txt', 'val', 'sta',
            'drag', 'sendkey', 'aph', 'movex', 'movey', 'endx', 'endy', 'effect', 'first',
            'time', 'lockobj', 'groupid0', 'groupid1'} | COLOUR_ATTRS | set(pics)
    other = {k: v for k, v in a.items() if k not in skip}
    if other:
        c['attrs'] = other
    if 'path' in a and t in (61, 68):
        c['options'] = [s for s in a['path'].replace('\r\n', '\n').split('\n')]
    c['visible'] = True          # no visibility attribute exists in the file; 'vis' is runtime
    ev = {}
    for k, lines in codes.items():
        ev[EVENT_NAMES.get(k, k)] = '\n'.join(lines)
    c['events'] = ev
    return c


# ---------------------------------------------------------------------------
# 4. Fonts (NN.zi) and pictures (NN.is / NN.i)
# ---------------------------------------------------------------------------

def parse_font(blob):
    name_len = blob[0x11]
    name_off = struct.unpack_from('<I', blob, 0x18)[0]
    return {
        'name': blob[name_off:name_off + name_len].decode('latin1'),
        'height': blob[7],
        'fixed_width': blob[6] or None,
        'first_char': blob[0x0a],
        'last_char': blob[0x0b],
        'glyphs': struct.unpack_from('<I', blob, 0x0c)[0],
        'data_bytes': struct.unpack_from('<I', blob, 0x14)[0],
        'encoding_byte': blob[4],
    }


def image_source(blob):
    """NN.is: 27-byte header (u32 hdr_len @8, u16 w @12, u16 h @14, u32 size @16,
       3-char format tag @24) then the original image file."""
    hdr = struct.unpack_from('<I', blob, 8)[0]
    w, h = struct.unpack_from('<HH', blob, 12)
    fmt = blob[24:27].decode('latin1').strip('\0')
    return w, h, fmt, blob[hdr:]


# ---------------------------------------------------------------------------

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else \
        '/Users/malcolmmessiter/Documents/GitHub/LockDownRadioControl/Nextion files/TX_NEXTION.HMI'
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(out, 'pictures'), exist_ok=True)
    os.makedirs(os.path.join(out, 'audio'), exist_ok=True)

    with open(src, 'rb') as f:
        data = f.read()
    live, entries = read_directory(data)

    def member(name):
        off, size = live[name]
        return data[off:off + size]

    ids = parse_main(member('main.HMI'))
    program_s = member('Program.s').decode('utf-8', 'replace')

    # fonts
    fonts = {}
    for fid, fname in enumerate(ids['zi']):
        fonts[fid] = dict(member=fname, **parse_font(member(fname)))

    # pictures
    pictures = {}
    for pid, iname in enumerate(ids['i']):
        stem = iname[:-2]
        entry = {'member': iname}
        if stem + '.is' in live:
            w, h, fmt, body = image_source(member(stem + '.is'))
            ext = 'png' if fmt == 'png' else (fmt or 'bin')
            path = os.path.join(out, 'pictures', '%d.%s' % (pid, ext))
            with open(path, 'wb') as f:
                f.write(body)
            entry.update(w=w, h=h, format=fmt, file='pictures/%d.%s' % (pid, ext))
        else:
            blob = member(iname)
            w, h = struct.unpack_from('<HH', blob, 12)
            path = os.path.join(out, 'pictures', '%d.i.bin' % pid)
            with open(path, 'wb') as f:
                f.write(blob)
            entry.update(w=w, h=h, format='nextion-i', file='pictures/%d.i.bin' % pid)
        pictures[pid] = entry

    # audio
    audio = {}
    for aid, wname in enumerate(ids['wav']):
        with open(os.path.join(out, 'audio', '%d.wav' % aid), 'wb') as f:
            f.write(member(wname))
        audio[aid] = {'member': wname, 'file': 'audio/%d.wav' % aid, 'bytes': live[wname][1]}

    # pages
    pages = []
    for page_id, pname in enumerate(ids['pa']):
        name, objs = parse_page(member(pname))
        comps = [component_json(a, c) for a, c in objs]
        page_comp = comps[0]
        assert page_comp['type'] == 'page' and page_comp['name'] == name
        bg = {'sta': page_comp['sta'], 'mode': page_comp['sta_name']}
        if page_comp['sta'] == 1:
            bg['colour'] = page_comp['colours']['bco']['hex']
            bg['rgb565'] = page_comp['colours']['bco']['rgb565']
        else:
            bg['picture'] = page_comp['pictures']['pic']
        pages.append({
            'name': name, 'id': page_id, 'member': pname,
            'w': page_comp['w'], 'h': page_comp['h'],
            'background': bg,
            'events': page_comp['events'],
            'page_attrs': page_comp.get('attrs', {}),
            'components': comps[1:],
        })

    with open(os.path.join(out, 'pages.json'), 'w') as f:
        json.dump({'source': os.path.basename(src), 'display': {'w': pages[0]['w'], 'h': pages[0]['h']},
                   'program_s': program_s, 'pages': pages}, f, indent=1)
    with open(os.path.join(out, 'fonts.json'), 'w') as f:
        json.dump(fonts, f, indent=1)
    with open(os.path.join(out, 'resources.json'), 'w') as f:
        json.dump({'directory': entries, 'id_tables': ids, 'pictures': pictures,
                   'audio': audio}, f, indent=1)

    print('pages: %d  components: %d  fonts: %d  pictures: %d  audio: %d' % (
        len(pages), sum(len(p['components']) for p in pages), len(fonts), len(pictures), len(audio)))


if __name__ == '__main__':
    main()
