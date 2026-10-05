#!/usr/bin/env python3
"""
decode_zi.py - decode the Nextion ZI (version 6) bitmap fonts embedded in TX_NEXTION.HMI.

Usage:
    python3 decode_zi.py ["<path to TX_NEXTION.HMI>"] [output dir]

Reads the HMI (read-only) and writes, for every font id N (order = main.HMI 'zi' table):
    N.json          height, first/last char, per-glyph advance width, bitmap width, kerning, offset
    N.bin           1-bpp glyph bitmaps, row-major, each row padded to whole bytes,
                    top row first, MSB = leftmost pixel (alpha >= 4 of 7 -> set).
                    A glyph bitmap is bitmap_width = width + kern_left + kern_right pixels wide;
                    draw it at pen_x - kern_left, then advance pen_x by width.
    N_aa.bin        the same glyphs at 4 bits/pixel (value 0..7 = Nextion alpha, 7 = opaque),
                    two pixels per byte, high nibble = left pixel, each row padded to whole bytes
    N_preview.png   "Black Thunder 2 RX 24.1V 0123456789" rendered from the decoded data
                    (top: 1-bpp; bottom: anti-aliased)
    nextion_fonts.h C header with the 1-bpp data as PROGMEM arrays

See README.md next to this file for the format.  Format reference:
https://github.com/hagronnestad/nextion-font-editor (ZI v5/v6 specifications).
"""
import json
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from extract_hmi import read_directory, parse_main       # noqa: E402

DEFAULT_HMI = '/Users/malcolmmessiter/Documents/GitHub/LockDownRadioControl/Nextion files/TX_NEXTION.HMI'
PREVIEW_TEXT = 'Black Thunder 2 RX 24.1V 0123456789'


# ---------------------------------------------------------------------------
# ZI v6 container
# ---------------------------------------------------------------------------

def parse_zi(blob):
    """Return (info, glyphs). glyphs = list of dicts with code/width/kern/offset/length/data."""
    if blob[:3] != b'\x04\xff\x00':
        raise ValueError('bad ZI magic %r' % blob[:3])
    info = {
        'orientation': blob[3],
        'encoding': struct.unpack_from('<H', blob, 4)[0],
        'fixed_width': blob[6],
        'height': blob[7],
        'first_char': blob[0x0a],
        'last_char': blob[0x0b],
        'glyph_count': struct.unpack_from('<I', blob, 0x0c)[0],
        'zi_version': blob[0x10],
        'data_bytes': struct.unpack_from('<I', blob, 0x14)[0],
    }
    name_len = blob[0x11]
    name_off = struct.unpack_from('<I', blob, 0x18)[0]
    info['name'] = blob[name_off:name_off + name_len].decode('latin1')
    # v6 "align to 8" flag: offsets are stored /8 when set. Detect it from the first glyph:
    # the first glyph's data starts right after the character map.
    table = name_off + name_len
    map_len = 10 * info['glyph_count']
    first_off = blob[table + 5] | (blob[table + 6] << 8) | (blob[table + 7] << 16)
    scale = 8 if first_off * 8 == map_len and first_off != map_len else 1
    info['offset_scale'] = scale
    glyphs = []
    for i in range(info['glyph_count']):
        e = table + 10 * i
        code, w, kl, kr, o0, o1, o2, ln = struct.unpack_from('<HBBBBBBH', blob, e)
        off = (o0 | (o1 << 8) | (o2 << 16)) * scale
        glyphs.append({'code': code, 'width': w, 'kern_left': kl, 'kern_right': kr,
                       'offset': off, 'length': ln, 'data': blob[table + off: table + off + ln]})
    return info, glyphs


# ---------------------------------------------------------------------------
# glyph run-length decoding  (alpha 0 = transparent .. 7 = opaque)
# ---------------------------------------------------------------------------

def decode_glyph(data, width, height):
    """Return (alpha list of width*height values 0..7, mode byte, overrun pixels)."""
    n = width * height
    px = []
    mode = data[0] if data else 0
    for b in data[1:]:
        t = b >> 5
        k = b & 0x1f
        if t == 0:                          # 000 xxxxx: k transparent
            px.extend([0] * k)
        elif t == 1:                        # 001 xxxxx: k opaque
            px.extend([7] * k)
        elif t in (2, 3):                   # 01x xxxxx: k transparent then 1/2 opaque
            px.extend([0] * k + [7] * (t - 1))
        elif mode == 3:
            if t in (4, 5):                 # 10 xxx ccc: xxx transparent then one alpha pixel
                px.extend([0] * ((b >> 3) & 7) + [b & 7])
            else:                           # 11 ccc ddd: two alpha pixels
                px.extend([(b >> 3) & 7, b & 7])
        else:
            if t in (4, 5):                 # 10x xxxxx: k transparent then 3/4 opaque
                px.extend([0] * k + [7] * (t - 1))
            else:                           # 11 www bbb: www transparent then bbb opaque
                px.extend([0] * ((b >> 3) & 7) + [7] * (b & 7))
    overrun = len(px) - n
    if len(px) < n:
        px.extend([0] * (n - len(px)))
    return px[:n], mode, overrun


# ---------------------------------------------------------------------------
# packing
# ---------------------------------------------------------------------------

def pack_1bpp(px, width, height, threshold=4):
    rb = (width + 7) // 8
    out = bytearray(rb * height)
    for y in range(height):
        for x in range(width):
            if px[y * width + x] >= threshold:
                out[y * rb + (x >> 3)] |= 0x80 >> (x & 7)
    return bytes(out)


def pack_4bpp(px, width, height):
    rb = (width + 1) // 2
    out = bytearray(rb * height)
    for y in range(height):
        for x in range(width):
            v = px[y * width + x] & 0xf
            out[y * rb + (x >> 1)] |= v << 4 if (x & 1) == 0 else v
    return bytes(out)


# ---------------------------------------------------------------------------
# preview PNG (grey, no PIL needed)
# ---------------------------------------------------------------------------

def write_png(path, width, height, rows):
    raw = b''.join(b'\x00' + bytes(r) for r in rows)

    def chunk(tag, body):
        c = tag + body
        return struct.pack('>I', len(body)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0)) \
        + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)


def render_line(text, font, aa):
    """font = {'height', 'glyphs': {code: (width, kl, kr, alpha)}}; returns list of rows (0..255).
       Bitmaps are width+kl+kr wide, drawn at pen-kl; the pen advances by width."""
    h = font['height']
    pen = 2
    cells = []
    for ch in text:
        g = font['glyphs'].get(ord(ch))
        if g is None:
            pen += h // 2
            continue
        w, kl, kr, px = g
        cells.append((pen - kl, w + kl + kr, px))
        pen += w
    width = max(pen + 2, 1)
    canvas = [[255] * width for _ in range(h)]
    for x0, bw, px in cells:
        for y in range(h):
            for x in range(bw):
                a = px[y * bw + x]
                if not aa:
                    a = 7 if a >= 4 else 0
                if a and 0 <= x0 + x < width:
                    canvas[y][x0 + x] = min(canvas[y][x0 + x], 255 - (a * 255) // 7)
    return canvas


def write_preview(path, font):
    top = render_line(PREVIEW_TEXT, font, aa=False)
    bot = render_line(PREVIEW_TEXT, font, aa=True)
    w = max(len(top[0]), len(bot[0])) + 8
    gap = [[200] * w for _ in range(4)]

    def pad(rows):
        return [[255] * 4 + r + [255] * (w - len(r) - 4) for r in rows]
    rows = [[255] * w for _ in range(4)] + pad(top) + gap + pad(bot) + [[255] * w for _ in range(4)]
    write_png(path, w, len(rows), rows)


# ---------------------------------------------------------------------------

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HMI
    out = sys.argv[2] if len(sys.argv) > 2 else HERE
    os.makedirs(out, exist_ok=True)
    with open(src, 'rb') as f:
        data = f.read()
    live, _ = read_directory(data)

    def member(name):
        off, size = live[name]
        return data[off:off + size]

    ids = parse_main(member('main.HMI'))
    header = ['// nextion_fonts.h - generated by decode_zi.py from TX_NEXTION.HMI; do not edit.',
              '// 1-bpp glyph bitmaps, row-major, rows padded to whole bytes, MSB = leftmost pixel.',
              '#pragma once', '#include <stdint.h>', '#ifdef ARDUINO', '#include <pgmspace.h>', '#else',
              '#define PROGMEM', '#endif', '',
              '// Glyph bitmap is bitmap_width = width + kern_left + kern_right pixels wide, row_bytes = (bitmap_width+7)/8;',
              '// draw it at x - kern_left, then advance x by width.',
              'struct NextionGlyph { uint32_t offset; uint8_t width; uint8_t bitmap_width; uint8_t kern_left; uint8_t kern_right; };',
              'struct NextionFont { uint8_t height; uint8_t first; uint8_t last; uint16_t count;',
              '                     const NextionGlyph *glyphs; const uint8_t *bits; uint32_t bits_len; };', '']
    font_index = []
    summary = []
    for fid, mname in enumerate(ids['zi']):
        info, glyphs = parse_zi(member(mname))
        h = info['height']
        table = []
        bits = bytearray()
        aabits = bytearray()
        modes = {}
        overruns = 0
        underruns = 0
        fontpx = {'height': h, 'glyphs': {}}
        for g in glyphs:
            adv = g['width']
            w = adv + g['kern_left'] + g['kern_right']     # the bitmap covers the kerning too
            px, mode, over = decode_glyph(g['data'], w, h)
            modes[mode] = modes.get(mode, 0) + 1
            overruns += over > 0
            underruns += over < 0
            fontpx['glyphs'][g['code']] = (adv, g['kern_left'], g['kern_right'], px)
            b1 = pack_1bpp(px, w, h)
            b4 = pack_4bpp(px, w, h)
            table.append({'code': g['code'], 'char': chr(g['code']), 'width': adv, 'bitmap_width': w,
                          'kern_left': g['kern_left'], 'kern_right': g['kern_right'],
                          'row_bytes': (w + 7) // 8, 'offset': len(bits), 'bytes': len(b1),
                          'aa_row_bytes': (w + 1) // 2, 'aa_offset': len(aabits), 'aa_bytes': len(b4),
                          'zi_mode': mode, 'zi_offset': g['offset'], 'zi_length': g['length'],
                          'pixel_overrun': over})
            bits += b1
            aabits += b4
        meta = {
            'id': fid, 'member': mname, 'name': info['name'], 'zi_version': info['zi_version'],
            'encoding': info['encoding'], 'height': h,
            'first_char': info['first_char'], 'last_char': info['last_char'],
            'glyph_count': info['glyph_count'],
            'bitmap_format': '1-bpp row-major, rows padded to whole bytes, top row first, MSB = leftmost; '
                             'bitmap_width = width + kern_left + kern_right; draw at x - kern_left, advance width',
            'bin_file': '%d.bin' % fid, 'bin_bytes': len(bits),
            'aa_file': '%d_aa.bin' % fid, 'aa_bytes': len(aabits),
            'aa_format': '4-bpp, value 0..7 = alpha (7 opaque), high nibble = left pixel, rows padded to bytes',
            'glyph_modes': {'%d' % k: v for k, v in sorted(modes.items())},
            'glyphs_with_overrun': overruns, 'glyphs_with_underrun': underruns,
            'glyphs': table,
        }
        with open(os.path.join(out, '%d.json' % fid), 'w') as f:
            json.dump(meta, f, indent=1)
        with open(os.path.join(out, '%d.bin' % fid), 'wb') as f:
            f.write(bits)
        with open(os.path.join(out, '%d_aa.bin' % fid), 'wb') as f:
            f.write(aabits)
        write_preview(os.path.join(out, '%d_preview.png' % fid), fontpx)

        # C header
        header.append('// font %d: %s  h=%d  chars %d..%d  (%d bytes)' % (
            fid, info['name'], h, info['first_char'], info['last_char'], len(bits)))
        header.append('static const uint8_t nextion_font%d_bits[%d] PROGMEM = {' % (fid, len(bits)))
        for i in range(0, len(bits), 24):
            header.append('  ' + ','.join('0x%02x' % b for b in bits[i:i + 24]) + ',')
        header.append('};')
        header.append('static const NextionGlyph nextion_font%d_glyphs[%d] PROGMEM = {' % (fid, len(table)))
        for t in table:
            header.append('  {%d,%d,%d,%d,%d},  // %d %s' % (
                t['offset'], t['width'], t['bitmap_width'], t['kern_left'], t['kern_right'], t['code'],
                repr(t['char']) if 32 < t['code'] < 127 else ''))
        header.append('};')
        header.append('static const NextionFont nextion_font%d = {%d, %d, %d, %d, nextion_font%d_glyphs, '
                      'nextion_font%d_bits, %d};' % (fid, h, info['first_char'], info['last_char'],
                                                     len(table), fid, fid, len(bits)))
        header.append('')
        font_index.append('nextion_font%d' % fid)
        summary.append((fid, info['name'], h, len(glyphs), modes, overruns, underruns, len(bits)))

    header.append('static const NextionFont *const nextion_fonts[%d] = { %s };' % (
        len(font_index), ', '.join('&' + n for n in font_index)))
    header.append('')
    with open(os.path.join(out, 'nextion_fonts.h'), 'w') as f:
        f.write('\n'.join(header))

    for fid, name, h, n, modes, over, under, nb in summary:
        print('font %d %-22s h=%2d glyphs=%3d modes=%s overrun=%d underrun=%d 1bpp=%d bytes' % (
            fid, name, h, n, modes, over, under, nb))


if __name__ == '__main__':
    main()
