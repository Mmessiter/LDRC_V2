"""Pixel width of a text in the screen's real fonts (lib/NextionFonts/nextion_fonts.h): will a message fit its box?
Run: python3 hmi/fontw.py FONT "text" ["text" ...]   e.g. python3 hmi/fontw.py 0 "Loading governor values ..." (378 px)"""
import os, re, sys
H = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib', 'NextionFonts', 'nextion_fonts.h')
src = open(H).read()
W = {}
for f in range(7):
    m = re.search(r'nextion_font%d_glyphs\[\d*\][^=]*=\s*\{(.*?)\};' % f, src, re.S)
    gl = re.findall(r'\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}', m.group(1))
    first = int(re.search(r'nextion_font%d = \{\d+, (\d+),' % f, src).group(1))
    W[f] = {first + i: int(g[1]) for i, g in enumerate(gl)}
def width(font, text):
    return sum(W[font].get(b, 0) for b in text.encode('latin1', 'replace'))
if __name__ == '__main__':
    font = int(sys.argv[1])
    for t in sys.argv[2:]: print(width(font, t), t)
