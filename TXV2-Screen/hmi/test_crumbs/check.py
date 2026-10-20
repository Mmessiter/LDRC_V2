#!/usr/bin/env python3
"""The curve page's crumbs (screen 1.11.99): in the BEFORE shot the edge dots and rings reach the cards round the box; in the
AFTER shot (the same clear again, the ring elsewhere) every such pixel shows its card again, and nothing white is left on the
cards. python3 check.py before.ppm after.ppm"""
import sys
def ppm(path):
    b = open(path, 'rb').read(); toks = []; i = 0
    while len(toks) < 4:                                   # P6 W H MAX, any whitespace between
        while b[i:i + 1].isspace(): i += 1
        j = i
        while not b[j:j + 1].isspace(): j += 1
        toks.append(b[i:j]); i = j
    i += 1
    return int(toks[1]), int(toks[2]), b[i:]
def px(img, x, y):
    w, h, d = img; o = (y * w + x) * 3; return tuple(d[o:o + 3])
before, after = ppm(sys.argv[1]), ppm(sys.argv[2])
checks = fails = 0
def check(c, what):
    global checks, fails
    checks += 1
    if not c: fails += 1; print('FAIL:', what)
white = lambda p: min(p) >= 200
cardL, cardT, cardG, cardB = px(after, 10, 200), px(after, 5, 20), px(after, 410, 200), px(after, 10, 440)
check(not white(cardL) and not white(cardT) and not white(cardG) and not white(cardB), 'the cards are not white (%s %s %s %s)' % (cardL, cardT, cardG, cardB))
crumbs = [(31, 391, cardL, 'left dot'), (26, 391, cardL, 'left ring'), (28, 395, cardL, 'left ring, lower'), (35, 400, cardB, 'ring below the box'),
          (398, 39, cardG, 'right dot'), (404, 39, cardG, 'right ring'), (395, 31, cardT, 'ring above the box'), (400, 32, cardT, 'ring above, right')]
for x, y, card, what in crumbs:
    check(px(before, x, y) != card, 'before: %s lies on the card at %d,%d (%s, card %s)' % (what, x, y, px(before, x, y), card))   # (white, or the ring's yellow or black)
    check(px(after, x, y) == card, 'after: %s put back to its card at %d,%d (%s, card %s)' % (what, x, y, px(after, x, y), card))
# nothing white anywhere on the cards round the box after the clear (the box is 35..395; the numbers above it are white digits: skip y < 30)
left = sum(1 for y in range(36, 396) for x in range(0, 35) if white(px(after, x, y)))
right = sum(1 for y in range(36, 396) for x in range(396, 424) if white(px(after, x, y)))
top = sum(1 for y in range(30, 35) for x in range(0, 424) if white(px(after, x, y)))
bottom = sum(1 for y in range(396, 412) for x in range(0, 424) if white(px(after, x, y)))
check(left == 0 and right == 0 and top == 0 and bottom == 0, 'no white crumb on the cards after the clear (left %d right %d top %d bottom %d)' % (left, right, top, bottom))
# the box itself is drawn again: the new ring and the outline
check(white(px(after, 215, 205)) and px(after, 35, 215) != cardL and white(px(after, 35, 391)) is False, 'the new ring is there, the outline too, the old left dot gone (%s %s %s)' % (px(after, 215, 205), px(after, 35, 215), px(after, 35, 391)))
print('test_crumbs: %d checks, %d failures' % (checks, fails))
sys.exit(1 if fails else 0)
