# Nextion `.zi` fonts from TX_NEXTION.HMI — decoded (2026-09-28)

Re-run:

    python3 decode_zi.py ["<path to TX_NEXTION.HMI>"] [output dir]

It reads the HMI (read-only), needs no third-party modules, and rewrites everything in this
directory except this README and itself. Format reference: the community ZI v5/v6 specifications
in <https://github.com/hagronnestad/nextion-font-editor> (Docs/), verified against every glyph here.

## Result

All seven fonts are **ZI version 6** and decode cleanly: every one of the 1 200 glyphs expands to
exactly `bitmap_width × height` pixels (0 overruns, 0 underruns), and the previews
`N_preview.png` ("Black Thunder 2 RX 24.1V 0123456789", top = 1-bpp, bottom = anti-aliased) read
correctly. Confidence: high for all seven.

| id | name (member) | h | chars | glyphs | glyph modes | 1-bpp bytes | confidence |
|---|---|---|---|---|---|---|---|
| 0 | Arial32B (`0.zi`) | 32 | 32..255 | 224 | 213 anti-aliased, 11 b/w | 18 048 | high |
| 1 | Arial64B (`1.zi`) | 64 | 32..255 | 224 | 188 aa, 36 b/w | 66 432 | high |
| 2 | Arial24 (`2.zi`) | 24 | 32..255 | 224 | 211 aa, 13 b/w | 10 776 | high |
| 3 | 24ascii (`3.zi`) | 24 | 32..126 | 95 | 95 b/w (fixed 12 px wide) | 4 560 | high |
| 4 | 16ascii (`4.zi`) | 16 | 32..126 | 95 | 95 b/w (fixed 8 px wide) | 1 520 | high |
| 5 | Courier32B (`8.zi`) | 32 | 32..255 | 224 | 188 aa, 36 b/w (all 17 px advance) | 21 344 | high |
| 6 | Arial28 (`5.zi`) | 28 | 32..255 | 224 | 208 aa, 16 b/w | 14 196 | high |

Caveat for "pixel-identical": the five Arial/Courier fonts are **anti-aliased** on the real
display (3-bit alpha, 8 levels). `N.bin` is a 1-bpp threshold (alpha ≥ 4 → set), which is what
the brief asked for and is what `nextion_fonts.h` carries; `N_aa.bin` keeps the full alpha so the
renderer can blend later if the edges matter. Fonts 3 and 4 are pure 1-bpp in the source, so
they are exactly identical either way.

## ZI v6 container (each `NN.zi` member)

Header, 0x2C bytes, little-endian:

| offset | size | value here | meaning |
|---|---|---|---|
| 0x00 | 3 | `04 FF 00` | magic |
| 0x03 | u8 | 0x0A | orientation (10 = vertical) |
| 0x04 | u16 | 1 = ASCII, 3 = ISO-8859-1 | encoding / code page |
| 0x06 | u8 | 0 | fixed character width (0 = proportional; the "ascii" fonts still say 0 but every glyph is the same width) |
| 0x07 | u8 | 16..64 | character height (pixels) |
| 0x08 | u8, u8 | 0, 0 | multibyte first-byte range (unused) |
| 0x0A | u8, u8 | 0x20, 0x7E / 0xFF | first / last character code |
| 0x0C | u32 | 95 / 224 | glyph count |
| 0x10 | u8 | 6 | ZI format version |
| 0x11 | u8 | 12..20 | font-name length |
| 0x14 | u32 | | bytes of name + character map + glyph data (= file size − 0x2C) |
| 0x18 | u32 | 0x2C | offset of the font name |
| 0x1C | u8 / u8 | 0 / height | width / height again |
| 0x2C | name_len | `Arial32Biso-8859-1` … | font name (name + code page, no separator) |

Then the **character map**: `glyph_count × 10 bytes`, starting at `0x2C + name_len`
(call this `T`). One entry per glyph, in code order:

    u16 code · u8 width · u8 kern_left · u8 kern_right · u24 offset · u16 length

`offset` is relative to `T` (the first glyph sits at `T + 10 × glyph_count`); v6 has an
"offsets ÷ 8" flag for very large files — not set in any of these seven (the decoder detects it).
`width` is the **advance**; the glyph's bitmap is `width + kern_left + kern_right` pixels wide
and is drawn at `pen_x − kern_left` (e.g. bold `j`'s hook overhangs 2 px to the left, `r`'s arm
1 px to the right). Only 11–36 glyphs per Arial font and ~40 of Courier's have non-zero kerning.

## Glyph data (per-pixel run-length, row-major, runs may cross rows)

Byte 0 = mode: `0x01` black/white, `0x03` anti-aliased (3-bit alpha, 0 = transparent, 7 = opaque).
Each following byte, by its top bits (`x` = 5-bit count, `www/bbb/ccc/ddd` = 3-bit fields):

| byte | mode 01 (b/w) | mode 03 (anti-aliased) |
|---|---|---|
| `000xxxxx` | x transparent | same |
| `001xxxxx` | x opaque | same |
| `010xxxxx` | x transparent, then 1 opaque | same |
| `011xxxxx` | x transparent, then 2 opaque | same |
| `100xxxxx` | x transparent, then 3 opaque | `10 xxx ccc`: xxx transparent, then one pixel of alpha ccc |
| `101xxxxx` | x transparent, then 4 opaque | (same as above — `10` prefix is a 2-bit mode) |
| `11wwwbbb` | www transparent, then bbb opaque | `11 ccc ddd`: two pixels, alpha ccc then ddd |

The stream stops when `bitmap_width × height` pixels have been produced (it always comes out
exact in this file). Pixel order is left-to-right, top-to-bottom.

## Output files

- `N.json` — `height`, `first_char`, `last_char`, `glyph_count`, and `glyphs[]` with
  `code, char, width (advance), bitmap_width, kern_left, kern_right, row_bytes, offset, bytes`
  (into `N.bin`), `aa_row_bytes, aa_offset, aa_bytes` (into `N_aa.bin`), plus the source
  `zi_mode/zi_offset/zi_length`. Glyphs are in code order, so glyph index = `code − first_char`.
- `N.bin` — 1-bpp bitmaps: for each glyph `height` rows of `row_bytes = (bitmap_width+7)/8`
  bytes, top row first, MSB = leftmost pixel, set bit = ink (alpha ≥ 4).
- `N_aa.bin` — the same glyphs at 4 bits/pixel (two pixels per byte, high nibble = left pixel,
  value 0..7 = Nextion alpha, rows padded to whole bytes).
- `N_preview.png` — the check string, 1-bpp above the grey rule, anti-aliased below.
- `nextion_fonts.h` — the `N.bin` data as `PROGMEM` arrays (`nextion_font<N>_bits`),
  `NextionGlyph {uint32 offset; uint8 width, bitmap_width, kern_left, kern_right}` tables and
  `NextionFont` descriptors, `nextion_fonts[7]` indexed by font id. 137 kB of bitmap data in
  total; compiles with `clang++ -std=c++11 -Wall`.

Rendering rule for the emulator: `g = font.glyphs[c − font.first]`; blit `g.bitmap_width × height`
at `(x − g.kern_left, y)`; `x += g.width`. Nextion's own text placement (xcen/ycen inside the
component box) is a separate matter for the page renderer.
