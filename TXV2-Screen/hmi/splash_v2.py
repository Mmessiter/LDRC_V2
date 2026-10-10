"""The start-up picture (hmi/pictures/0.png, card picture 0, page SplashView) says "LockDownRadioControl V2".

Malcolm, 10 Oct 2026: "is it possible for you to edit this image such that it declares LockDownRadioControl V2".
Run once on the Version 1 picture (git history has it); running it again on its own output gives the same picture.
Needs Pillow and macOS's SF font (/System/Library/Fonts/SFNS.ttf):

    python3 hmi/splash_v2.py hmi/pictures/0.png hmi/pictures/0.png 41 1 740 97

then hmi/build_sd.py (or the card's 0.565 alone) and a release. The settings chosen: capitals 41 px tall (the old
title's were 44: " V2" had to fit), 1 px between letters, weight 740 (the old letters' strokes), width 97 %.
"""
# The splash (screen card picture 0) with the title "LockDownRadioControl V2": the old title painted out with the sky
# above and below it, the new one drawn in the same face (SF Pro semibold), size, colour and dark edge as "is loading...".
import sys, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
SRC, OUT = sys.argv[1], sys.argv[2]
CAP = float(sys.argv[3]) if len(sys.argv) > 3 else 44      # cap height in px (the original title's)
TRACK = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0   # extra px between letters
WGHT = float(sys.argv[5]) if len(sys.argv) > 5 else 740     # SF weight axis (590 semibold, 700 bold): the original's stems are ~10.5 px at cap 44
WDTH = float(sys.argv[6]) if len(sys.argv) > 6 else 100     # SF width axis (100 normal)
TEXT = "LockDownRadioControl V2"
im = Image.open(SRC).convert('RGB'); W, H = im.size; px = im.load()

# (the title is drawn with its capitals from row 60, as the old one's; ~37 px margins either side, as the old one's)
# 1. the old title out: each column's sky drawn straight from rows 49-52 to rows 112-115 (clear sky both sides;
#    the helicopter starts at row 122), with the sky's own grain (sd ~1.4)
Y0, Y1, A, B = 53, 112, (49, 53), (112, 116)
rnd = random.Random(2)
def avg(x, ys): ps = [px[x, y] for y in range(*ys)]; return [sum(p[i] for p in ps) / len(ps) for i in range(3)]
for x in range(W):
    a, b = avg(x, A), avg(x, B)
    for y in range(Y0, Y1):
        t = (y - (A[0] + A[1] - 1) / 2) / ((B[0] + B[1] - 1) / 2 - (A[0] + A[1] - 1) / 2)
        n = rnd.gauss(0, 1.3)
        px[x, y] = tuple(max(0, min(255, int(round(a[i] + (b[i] - a[i]) * t + n)))) for i in range(3))

# 2. the new title, 4x over-sampled for clean edges
S = 4
def font(size):
    f = ImageFont.truetype('/System/Library/Fonts/SFNS.ttf', size)
    f.set_variation_by_axes([WDTH, 28, 400, WGHT])   # width, optical size, grade, weight
    return f
size = 62
for _ in range(20):                                   # the size whose capital L is CAP px tall
    f = font(size * S); bb = f.getbbox('L'); cap = (bb[3] - bb[1]) / S
    if abs(cap - CAP) < 0.25: break
    size *= CAP / cap
f = font(size * S)
adv = [f.getlength(c) for c in TEXT]
kern = [f.getlength(TEXT[i:i + 2]) - adv[i] - adv[i + 1] for i in range(len(TEXT) - 1)] + [0]
width = sum(adv) + sum(kern) + TRACK * S * (len(TEXT) - 1)
mask = Image.new('L', (W * S, H * S), 0); d = ImageDraw.Draw(mask)
bbL = f.getbbox('L'); top = 60 * S                    # the capitals start on row 60, as the old title's did
x = (W * S - width) / 2 - f.getbbox(TEXT[0])[0] + 0.5 * S
for i, c in enumerate(TEXT):
    d.text((x, top - bbL[1]), c, font=f, fill=255)
    x += adv[i] + kern[i] + TRACK * S
mask = mask.resize((W, H), Image.LANCZOS)
bb = mask.getbbox(); print(f'size {size:.1f}px cap {CAP} track {TRACK}: title x {bb[0]}..{bb[2]} y {bb[1]}..{bb[3]}')

# 3. the dark edge the original letters have (red falls most: a deeper blue), then the letters (253, 254, 254)
halo = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
mp, hp = mask.load(), halo.load()
for y in range(Y0 - 2, Y1 + 2):
    for x in range(W):
        h, m = hp[x, y] / 255, mp[x, y] / 255
        if not h and not m: continue
        r, g, b = px[x, y]
        r, g = r * (1 - 0.55 * h), g * (1 - 0.06 * h)
        px[x, y] = tuple(int(round(v * (1 - m) + w * m)) for v, w in zip((r, g, b), (253, 254, 254)))
im.save(OUT)
