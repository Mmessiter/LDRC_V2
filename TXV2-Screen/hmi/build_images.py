#!/usr/bin/env python3
"""Model photos for the FrontView frame (exp0 is 320x200): JPG/PNG in -> sd/images/<NAME>.565 out
   usage: build_images.py <folder with the Nextion card's images>   (names kept, extension dropped, upper-cased as the Teensy sends them)"""
import os, struct, sys
from PIL import Image, ImageOps
src = sys.argv[1]; here = os.path.dirname(os.path.abspath(__file__)); out = os.path.join(here, '..', 'sd', 'images'); os.makedirs(out, exist_ok=True)
n = 0
for fn in sorted(os.listdir(src)):
    if not fn.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')): continue
    im = ImageOps.exif_transpose(Image.open(os.path.join(src, fn))).convert('RGB')
    im = ImageOps.fit(im, (320, 200))
    px = im.tobytes(); buf = bytearray(320 * 200 * 2)
    for i in range(320 * 200):
        r, g, b = px[3*i], px[3*i+1], px[3*i+2]; v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3); buf[2*i] = v & 0xFF; buf[2*i+1] = v >> 8
    base = os.path.splitext(fn)[0]
    with open(os.path.join(out, base + '.565'), 'wb') as f: f.write(struct.pack('<HH', 320, 200)); f.write(buf)
    n += 1
print(n, 'images ->', out)
