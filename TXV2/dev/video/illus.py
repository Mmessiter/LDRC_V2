#!/usr/bin/env python3
"""Drawn illustrations for the films (18 Oct 2026): a helicopter from above, from the side and from the front, a dial, a
servo, radio waves, a timeline - so that a film can SHOW a flying problem (a wagging tail, a wobble, a sagging head speed)
before it shows the cure on the transmitter's pages. Malcolm: "Take your time with this job because it needs to be
imaginative, well executed, informative and entertaining! We have ALL DAY!!"

Every drawing is made at twice the film's size and shrunk (smooth edges), on the cards' own background, and comes back as
a picture of the film's size marked as a card (filmkit.Film._frame shows it whole). Movement is a function of time, for
Film.anim (in silence: the voice speaks over the last picture, as Malcolm's rule for the films says).

   from illus import Art
   art = Art(f)                        # f: the Film
   f.show(art.tail_wag(0)); f.anim(art.tail_wag, 3.0)   # each drawing is a function of t (seconds) -> picture
"""
import json, math, os
from PIL import Image, ImageDraw, ImageFilter, ImageFont
HELI3D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'heli3d')   # (the rendered helicopter: heli3d/make_sprites.py)
_SPRITES = {}
ROTOR_R = 1.42 / 1.2                                              # (the renders' model, in its own units: the main rotor's radius as
ROTOR_Y, TAIL_XY, TAIL_R = 0.58, (-1.42, 0.08), 0.29              #  lengthened by make_sprites.py; its height above the shaft's foot; the
VIEW_TILT = 7.0                                                   #  tail rotor's centre and radius; side and front seen from 7 degrees up)

WHITE, INK, YELLOW, RED, GREEN, BLUE = (242, 244, 248), (24, 30, 42), (255, 214, 64), (236, 84, 72), (96, 200, 120), (93, 168, 255)
CANOPY, BOOM, METAL, DISC = (64, 118, 182), (226, 230, 238), (176, 184, 198), (255, 255, 255)
SKID = (150, 160, 178)
SS = 2                                                            # (drawn at twice the size, then shrunk: smooth edges)

def _font(size, bold=False):
    for f in (('/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold else '/System/Library/Fonts/Supplemental/Arial.ttf'), '/System/Library/Fonts/Helvetica.ttc'):
        try: return ImageFont.truetype(f, size)
        except OSError: pass
    return ImageFont.load_default()

def rot(pts, deg, cx=0.0, cy=0.0):
    """points turned by deg (clockwise on the screen, y down) about (cx, cy)"""
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in pts]

def capsule(cx, cy, length, width, n=10):
    """a rounded fuselage along y (nose up, at cy - length/2), as a polygon"""
    r = width / 2; top, bot = cy - length / 2 + r, cy + length / 2 - r * 0.6
    pts = [(cx + r * math.cos(math.pi + math.pi * i / n), top + r * math.sin(math.pi + math.pi * i / n)) for i in range(n + 1)]
    pts += [(cx + r * 0.8, bot), (cx + r * 0.35, cy + length / 2), (cx - r * 0.35, cy + length / 2), (cx - r * 0.8, bot)]
    return pts

def ease(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)


class Art:
    """the drawings, at the film's size (f.W x f.H), leaving its caption band free"""
    def __init__(self, film):
        self.f = film; self.W, self.H = film.W, film.H
        self.k = self.H / 480.0                                   # (1 on the transmitter, 1.5 for an MP4)
        self.area_h = (432 if film.target == 'screen' else 624) * self.k / (1 if film.target == 'screen' else 1.5)   # (above the caption)
        self.cx, self.cy = self.W / 2, self.area_h / 2 + (0 if film.target == 'screen' else 18)

    # ------------------------------------------------------------ the canvas
    def _canvas(self):
        im = self.f.BG.resize((self.W * SS, self.H * SS), Image.BILINEAR)
        return im, ImageDraw.Draw(im, 'RGBA')
    def _done(self, im):
        out = im.resize((self.W, self.H), Image.LANCZOS); out.ldrc_card = True; return out
    def u(self, v): return v * self.k * SS                        # (a length in screen pixels, on the big canvas)
    def p(self, x, y): return (self.cx * SS + self.u(x), self.cy * SS + self.u(y))
    def text(self, d, x, y, s, size=30, fill=WHITE, bold=True, anchor='mm'):
        d.text(self.p(x, y), s, font=_font(int(self.u(size)), bold), fill=fill, anchor=anchor)
    def label(self, d, x, y, s, size=30, fill=INK, back=YELLOW, anchor='lm'):
        """a word on a pale pill (the kit's caption look, smaller); x is its left end unless anchor says otherwise"""
        fnt = _font(int(self.u(size)), True); x0, y0 = self.p(x, y)
        l, t, r, b = d.textbbox((x0, y0), s, font=fnt, anchor=anchor); pad = self.u(10)
        d.rounded_rectangle([l - pad, t - pad * 0.7, r + pad, b + pad * 0.7], radius=self.u(10), fill=back)
        d.text((x0, y0), s, font=fnt, fill=fill, anchor=anchor)
    def title(self, d, s):                                         # (each problem picture's name, top left)
        self.label(d, -self.W / (2 * self.k) + 30, -self.area_h / (2 * self.k) + 34, s)
    def poly(self, d, pts, fill, outline=INK, width=3):
        q = [self.p(x, y) for x, y in pts]; d.polygon(q, fill=fill)
        if outline: d.line(q + [q[0]], fill=outline, width=int(self.u(width)), joint='curve')
    def circle(self, d, x, y, r, fill=None, outline=INK, width=3):
        (X, Y) = self.p(x, y); R = self.u(r)
        d.ellipse([X - R, Y - R, X + R, Y + R], fill=fill, outline=outline, width=int(self.u(width)) if outline else 0)
    def line(self, d, pts, fill=INK, width=3):
        d.line([self.p(x, y) for x, y in pts], fill=fill, width=int(self.u(width)), joint='curve')
    def arc_arrow(self, d, x, y, r, a0, a1, fill=YELLOW, width=6):
        """a curved arrow round (x, y) from angle a0 to a1 (degrees, clockwise from east), its head at a1"""
        n = 24; pts = [(x + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), y + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        self.line(d, pts, fill, width)
        a = math.radians(a1); dirn = 1 if a1 > a0 else -1
        tx, ty = -math.sin(a) * dirn, math.cos(a) * dirn             # (the way the arc runs at its end)
        hx, hy = pts[-1]; s = width * 2.6
        self.poly(d, [(hx + tx * s, hy + ty * s), (hx - ty * s * 0.7, hy + tx * s * 0.7), (hx + ty * s * 0.7, hy - tx * s * 0.7)], fill, outline=None)
    def arrow(self, d, x0, y0, x1, y1, fill=YELLOW, width=6):
        self.line(d, [(x0, y0), (x1, y1)], fill, width)
        a = math.atan2(y1 - y0, x1 - x0); s = width * 2.6
        self.poly(d, [(x1 + math.cos(a) * s, y1 + math.sin(a) * s), (x1 - math.sin(a) * s * 0.7, y1 + math.cos(a) * s * 0.7), (x1 + math.sin(a) * s * 0.7, y1 - math.cos(a) * s * 0.7)], fill, outline=None)

    # ------------------------------------------------------------ the films' title cards
    def _flat_title_heli(self):
        """the cards' background with a helicopter in forward flight above where the title goes"""
        im, d = self._canvas()
        self._flat_heli_side(d, 18, -112, pitch=7, s=0.46)
        return self._done(im)

    # ------------------------------------------------------------ helicopters
    def _blades(self, d, x, y, R, phase, s, blur=4):
        """two main blades seen from above, turning: a few faint copies behind each (the blur of a spinning rotor)"""
        for k in range(blur, -1, -1):
            a0 = phase - k * 9
            for b in (0, 180):
                a = math.radians(a0 + b); c, sn = math.cos(a), math.sin(a)
                w = 7 * s; tip = (x + R * c, y + R * sn)
                pts = [(x - sn * w, y + c * w), (tip[0] - sn * w * 0.7, tip[1] + c * w * 0.7), (tip[0] + sn * w * 0.7, tip[1] - c * w * 0.7), (x + sn * w, y - c * w)]
                col = (54, 60, 76, 230) if k == 0 else (210, 220, 236, 34)
                self.poly(d, pts, col, outline=None)
    def _flat_heli_top(self, d, x, y, yaw=0.0, s=1.0, phase=0.0, disc=True):
        """from above, nose up; turned by yaw degrees about the main shaft at (x, y). Proportions of a 420-size helicopter:
        the cabin a third of the rotor's width, the tail rotor just beyond the main blades' tips"""
        R = 200 * s; T = lambda pts: rot(pts, yaw, x, y)
        if disc: self.circle(d, x, y, R, fill=(255, 255, 255, 16), outline=(200, 212, 228, 100), width=2)
        self.poly(d, T([(x - 6 * s, y + 40 * s), (x + 6 * s, y + 40 * s), (x + 4 * s, y + 222 * s), (x - 4 * s, y + 222 * s)]), BOOM, width=2)            # boom
        self.poly(d, T([(x - 32 * s, y + 168 * s), (x + 32 * s, y + 168 * s), (x + 28 * s, y + 178 * s), (x - 28 * s, y + 178 * s)]), BOOM, width=2)          # stabiliser
        self.poly(d, T([(x - 6 * s, y + 204 * s), (x + 6 * s, y + 204 * s), (x + 6 * s, y + 232 * s), (x - 6 * s, y + 232 * s)]), METAL, width=2)            # tail case
        self.line(d, T([(x + 15 * s, y + 182 * s), (x + 15 * s, y + 254 * s)]), (232, 238, 248), 6 * s)                                                     # tail rotor, edge on
        body = [(x, y - 104 * s), (x + 16 * s, y - 92 * s), (x + 28 * s, y - 62 * s), (x + 32 * s, y - 10 * s), (x + 28 * s, y + 36 * s), (x + 12 * s, y + 52 * s),
                (x - 12 * s, y + 52 * s), (x - 28 * s, y + 36 * s), (x - 32 * s, y - 10 * s), (x - 28 * s, y - 62 * s), (x - 16 * s, y - 92 * s)]
        self.poly(d, T(body), WHITE)
        self.poly(d, T([(x, y - 96 * s), (x + 13 * s, y - 84 * s), (x + 22 * s, y - 58 * s), (x - 22 * s, y - 58 * s), (x - 13 * s, y - 84 * s)]), CANOPY, width=2)
        self.line(d, T([(x - 24 * s, y - 34 * s), (x - 20 * s, y + 34 * s)]), YELLOW, 5 * s); self.line(d, T([(x + 24 * s, y - 34 * s), (x + 20 * s, y + 34 * s)]), YELLOW, 5 * s)
        if disc: self._blades(d, x, y, R, phase + yaw, s)
        self.circle(d, x, y, 12 * s, fill=METAL, width=2)          # the head
    def _rotor_edge(self, d, P, x, y, R, s):
        """the main rotor seen edge on, spinning: a pale blurred disc with the blade across it, and the head"""
        self.poly(d, P([(x - R, y), (x - R * 0.7, y - 7 * s), (x + R * 0.7, y - 7 * s), (x + R, y), (x + R * 0.7, y + 7 * s), (x - R * 0.7, y + 7 * s)]), (220, 228, 242, 70), outline=None)
        self.poly(d, P([(x - R, y - 2.5 * s), (x + R, y - 2.5 * s), (x + R, y + 2.5 * s), (x - R, y + 2.5 * s)]), (196, 206, 222), outline=None)
        self.circle(d, *P([(x, y)])[0], 10 * s, fill=METAL, width=2)
    def shadow(self, d, x, y, w, h=None):
        h = h or w * 0.14; X, Y = self.p(x, y); W2, H2 = self.u(w / 2), self.u(h / 2)
        d.ellipse([X - W2, Y - H2, X + W2, Y + H2], fill=(0, 0, 0, 70))
    def _flat_heli_side(self, d, x, y, pitch=0.0, s=1.0, rotor=True):
        """from the side, nose right; pitched by pitch degrees (nose down positive) about the main shaft at (x, y)"""
        P = lambda pts: rot(pts, pitch, x, y)
        self.poly(d, P([(x - 50 * s, y - 10 * s), (x - 286 * s, y - 16 * s), (x - 286 * s, y - 7 * s), (x - 50 * s, y + 10 * s)]), BOOM, width=2)              # boom
        self.poly(d, P([(x - 262 * s, y - 14 * s), (x - 282 * s, y - 62 * s), (x - 298 * s, y - 62 * s), (x - 292 * s, y - 8 * s)]), BOOM, width=2)            # fin
        self.poly(d, P([(x - 226 * s, y - 5 * s), (x - 258 * s, y - 5 * s), (x - 258 * s, y + 2 * s), (x - 226 * s, y + 2 * s)]), METAL, width=1)              # stabiliser
        hx, hy = P([(x - 296 * s, y - 28 * s)])[0]
        self.circle(d, hx, hy, 36 * s, fill=(255, 255, 255, 22), outline=(200, 212, 228, 150), width=2)                                                    # tail rotor disc
        self.line(d, [(hx - 30 * s, hy + 18 * s), (hx + 30 * s, hy - 18 * s)], (54, 60, 76), 5 * s)
        self.circle(d, hx, hy, 6 * s, fill=METAL, width=2)
        pod = [(x - 62 * s, y + 12 * s), (x - 56 * s, y - 24 * s), (x - 10 * s, y - 38 * s), (x + 50 * s, y - 38 * s), (x + 104 * s, y - 20 * s), (x + 136 * s, y + 4 * s),
               (x + 130 * s, y + 14 * s), (x + 96 * s, y + 34 * s), (x + 20 * s, y + 42 * s), (x - 40 * s, y + 38 * s)]
        self.poly(d, P(pod), WHITE)
        self.poly(d, P([(x + 48 * s, y - 32 * s), (x + 100 * s, y - 17 * s), (x + 126 * s, y + 4 * s), (x + 84 * s, y + 6 * s), (x + 42 * s, y - 4 * s)]), CANOPY, width=2)
        self.line(d, P([(x - 50 * s, y + 16 * s), (x + 36 * s, y + 22 * s), (x + 104 * s, y + 18 * s)]), YELLOW, 5 * s)                                     # stripe
        for a, b in (((x - 30 * s, y + 38 * s), (x - 44 * s, y + 68 * s)), ((x + 58 * s, y + 36 * s), (x + 68 * s, y + 68 * s))): self.line(d, P([a, b]), SKID, 5 * s)
        self.line(d, P([(x - 96 * s, y + 68 * s), (x + 104 * s, y + 68 * s), (x + 126 * s, y + 56 * s)]), SKID, 6 * s)                                    # skid
        self.line(d, P([(x, y - 38 * s), (x, y - 66 * s)]), SKID, 7 * s)                                                                                      # mast
        self.poly(d, P([(x - 15 * s, y - 50 * s), (x + 15 * s, y - 50 * s), (x + 15 * s, y - 44 * s), (x - 15 * s, y - 44 * s)]), METAL, width=1)            # swashplate
        if rotor: self._rotor_edge(d, P, x, y - 69 * s, 250 * s, s)
    def _flat_heli_front(self, d, x, y, roll=0.0, s=1.0):
        """from the front; rolled by roll degrees (right side down positive) about the main shaft at (x, y)"""
        P = lambda pts: rot(pts, roll, x, y)
        for sx in (-1, 1):
            self.line(d, P([(x + sx * 24 * s, y + 38 * s), (x + sx * 72 * s, y + 74 * s)]), SKID, 5 * s)
            self.circle(d, *P([(x + sx * 76 * s, y + 76 * s)])[0], 7 * s, fill=SKID, outline=None)
        self.poly(d, P([(x - 40 * s, y - 40 * s), (x + 40 * s, y - 40 * s), (x + 50 * s, y - 6 * s), (x + 42 * s, y + 30 * s), (x + 24 * s, y + 44 * s), (x - 24 * s, y + 44 * s), (x - 42 * s, y + 30 * s), (x - 50 * s, y - 6 * s)]), WHITE)
        self.poly(d, P([(x - 32 * s, y - 32 * s), (x + 32 * s, y - 32 * s), (x + 40 * s, y - 2 * s), (x - 40 * s, y - 2 * s)]), CANOPY, width=2)
        self.line(d, P([(x - 44 * s, y + 14 * s), (x + 44 * s, y + 14 * s)]), YELLOW, 5 * s)
        self.line(d, P([(x, y - 40 * s), (x, y - 70 * s)]), SKID, 7 * s)
        self._rotor_edge(d, P, x, y - 73 * s, 290 * s, s)


    # ------------------------------------------------------------ the helicopter, rendered (18 Oct 2026)
    # heli3d/make_sprites.py renders the receiver's own 3D model (the Goblin of the View channels page) from above, the side
    # and the front; these place, turn and scale those pictures where the flat drawings went (same arguments, same pivot:
    # the main shaft), and draw the spinning rotor discs themselves (the model's own disc is dark, for a pale page).
    def _spr(self, view):
        if view not in _SPRITES:
            meta = json.load(open(os.path.join(HELI3D, 'sprites.json')))[view]
            _SPRITES[view] = (Image.open(os.path.join(HELI3D, view + '.png')).convert('RGBA'), meta)
        return _SPRITES[view]
    def _place(self, d, layer, X, Y, deg):
        """layer: an RGBA picture with the pivot at its centre; turned deg clockwise and laid on the canvas with the pivot at X, Y"""
        if deg: layer = layer.rotate(-deg, resample=Image.BICUBIC)
        halo = layer.getchannel('A').filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(3))   # (a faint pale edge: the black
        glow = Image.new('RGBA', layer.size, (150, 165, 190, 0)); glow.putalpha(halo.point(lambda a: a * 50 // 255))   #  frame and blades show on the navy)
        canvas = d._image; at = (int(round(X - layer.width / 2)), int(round(Y - layer.height / 2)))   # (the canvas is RGB: pasted through
        canvas.paste(glow, at, glow); canvas.paste(layer, at, layer)                                      #  each layer's own alpha)
    def _body(self, view, scale):
        """the rendered view at scale (canvas px per sprite px), on a square layer whose centre is the main shaft"""
        im, meta = self._spr(view)
        w, h = max(1, int(round(im.width * scale))), max(1, int(round(im.height * scale)))
        sm = im.resize((w, h), Image.LANCZOS); sx, sy = meta['shaft'][0] * scale, meta['shaft'][1] * scale
        L = int(2 * max(math.hypot(sx, sy), math.hypot(w - sx, sy), math.hypot(sx, h - sy), math.hypot(w - sx, h - sy))) + 8
        layer = Image.new('RGBA', (L, L), (0, 0, 0, 0)); layer.alpha_composite(sm, (int(round(L / 2 - sx)), int(round(L / 2 - sy))))
        return layer, meta['ppu'] * scale                         # (and canvas px per model unit)
    def _disc_top(self, layer, R, phase):
        """the main rotor from above, spinning clockwise: a faint disc, the white tips and orange chevrons as rings, and the
        blades' blur trailing the place they are now (phase, degrees clockwise from east)"""
        g = Image.new('RGBA', layer.size, (0, 0, 0, 0)); d = ImageDraw.Draw(g, 'RGBA'); c = layer.width / 2
        def ring(r0, r1, col):
            d.ellipse([c - r1, c - r1, c + r1, c + r1], fill=col); d.ellipse([c - r0, c - r0, c + r0, c + r0], fill=(0, 0, 0, 0))
        d.ellipse([c - R, c - R, c + R, c + R], fill=(230, 238, 250, 22))
        sub = Image.new('RGBA', layer.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sub, 'RGBA')
        for k in range(14):                                       # (each blade's sweep: darkest where it is now, fading behind it)
            a = 4.0 * (k + 1)
            for b in (0, 180):
                sd.pieslice([c - R, c - R, c + R, c + R], phase + b - a, phase + b - a + 4.0, fill=(8, 10, 16, max(0, 70 - 5 * k)))
        g = Image.alpha_composite(g, sub); d = ImageDraw.Draw(g, 'RGBA')
        for (r0, r1, col) in ((0.88 * R, 0.97 * R, (255, 255, 255, 30)), (0.67 * R, 0.70 * R, (242, 85, 28, 36))):
            band = Image.new('RGBA', layer.size, (0, 0, 0, 0)); bd = ImageDraw.Draw(band, 'RGBA')
            bd.ellipse([c - r1, c - r1, c + r1, c + r1], fill=col); bd.ellipse([c - r0, c - r0, c + r0, c + r0], fill=(0, 0, 0, 0))
            g = Image.alpha_composite(g, band)
        d = ImageDraw.Draw(g, 'RGBA')
        for b in (0, 180):                                        # (the blades themselves, faint: where they are now)
            a = math.radians(phase + b); d.line([(c, c), (c + R * math.cos(a), c + R * math.sin(a))], fill=(10, 12, 18, 120), width=max(1, int(R * 0.035)))
        return g
    def heli_top(self, d, x, y, yaw=0.0, s=1.0, phase=0.0, disc=True):
        """from above, nose up; turned by yaw degrees (clockwise) about the main shaft at (x, y); the rotor's radius 200 s"""
        try: self._spr('top')
        except (OSError, KeyError, ValueError): return self._flat_heli_top(d, x, y, yaw, s, phase, disc)
        R = self.u(200 * s); scale = R / (ROTOR_R * self._spr('top')[1]['ppu'])
        layer, ppu = self._body('top', scale)
        if disc:
            if layer.width < 2 * R + 8:                            # (room for the disc)
                big = Image.new('RGBA', (int(2 * R + 8),) * 2, (0, 0, 0, 0)); big.alpha_composite(layer, (int((big.width - layer.width) / 2), int((big.height - layer.height) / 2))); layer = big
            layer = Image.alpha_composite(layer, self._disc_top(layer, R, phase))   # (the rotor turns with the helicopter: _place turns both)
        X, Y = self.p(x, y); self._place(d, layer, X, Y, yaw)
    def _disc_edge(self, layer, cx, cy, R, tilt, tail=None):
        """a spinning rotor seen nearly edge on, from tilt degrees above: a pale flat ellipse round the blade; tail: (x, y, r)
        of a tail rotor seen face on, drawn as a pale disc"""
        g = Image.new('RGBA', layer.size, (0, 0, 0, 0)); d = ImageDraw.Draw(g, 'RGBA')
        h = max(2.0, R * math.sin(math.radians(tilt)))
        d.ellipse([cx - R, cy - h, cx + R, cy + h], fill=(230, 238, 250, 34), outline=(255, 255, 255, 70), width=max(1, int(R * 0.008)))
        if tail:
            tx, ty, tr = tail
            d.ellipse([tx - tr, ty - tr, tx + tr, ty + tr], fill=(230, 238, 250, 40), outline=(255, 255, 255, 80), width=max(1, int(tr * 0.05)))
        return Image.alpha_composite(g, layer)                  # (the disc behind the helicopter's own parts)
    def heli_side(self, d, x, y, pitch=0.0, s=1.0, rotor=True):
        """from the side, nose right; pitched by pitch degrees (nose down positive) about the main shaft at (x, y)"""
        try: self._spr('side')
        except (OSError, KeyError, ValueError): return self._flat_heli_side(d, x, y, pitch, s, rotor)
        R = self.u(200 * s); scale = R / (ROTOR_R * self._spr('side')[1]['ppu'])
        layer, ppu = self._body('side', scale); c = layer.width / 2; cos = math.cos(math.radians(VIEW_TILT))
        if rotor:
            layer = self._disc_edge(layer, c, c - ROTOR_Y * ppu * cos, R, VIEW_TILT, tail=(c + TAIL_XY[0] * ppu, c - TAIL_XY[1] * ppu * cos, TAIL_R * ppu))
        X, Y = self.p(x, y); self._place(d, layer, X, Y, pitch)
    def heli_front(self, d, x, y, roll=0.0, s=1.0):
        """from the front; rolled by roll degrees (clockwise on the screen) about the main shaft at (x, y)"""
        try: self._spr('front')
        except (OSError, KeyError, ValueError): return self._flat_heli_front(d, x, y, roll, s)
        R = self.u(230 * s); scale = R / (ROTOR_R * self._spr('front')[1]['ppu'])
        layer, ppu = self._body('front', scale); c = layer.width / 2; cos = math.cos(math.radians(VIEW_TILT))
        layer = self._disc_edge(layer, c, c - ROTOR_Y * ppu * cos, R, VIEW_TILT)
        X, Y = self.p(x, y); self._place(d, layer, X, Y, roll)
    def title_heli(self):
        """the cards' background with the helicopter (three-quarter view, rendered) above where the title goes"""
        try: im0, meta = self._spr('card')
        except (OSError, KeyError, ValueError): return self._flat_title_heli()
        im, d = self._canvas()
        scale = self.u(290) / im0.width; sm = im0.resize((int(im0.width * scale), int(im0.height * scale)), Image.LANCZOS)
        X, Y = self.p(0, -122)
        layer = Image.new('RGBA', (sm.width + 20, sm.height + 20), (0, 0, 0, 0)); layer.alpha_composite(sm, (10, 10))
        self._place(d, layer, X, Y, 0)
        return self._done(im)

    # ------------------------------------------------------------ instruments
    def dial(self, d, x, y, r, value, lo, hi, label, unit='', good=None):
        """a round gauge: an arc from lo to hi, its needle at value, the value under it; good: (from, to) drawn green"""
        a0, a1 = 150, 390                                         # (degrees clockwise from east: bottom left round to bottom right)
        self.circle(d, x, y, r, fill=(14, 18, 26), outline=METAL, width=4)
        def ang(v): return a0 + (a1 - a0) * (max(lo, min(hi, v)) - lo) / float(hi - lo)
        if good:
            n = 30; g0, g1 = ang(good[0]), ang(good[1])
            self.line(d, [(x + r * 0.82 * math.cos(math.radians(g0 + (g1 - g0) * i / n)), y + r * 0.82 * math.sin(math.radians(g0 + (g1 - g0) * i / n))) for i in range(n + 1)], GREEN, 10)
        for i in range(11):
            a = math.radians(a0 + (a1 - a0) * i / 10.0); r0 = r * (0.70 if i % 5 == 0 else 0.76)
            self.line(d, [(x + r0 * math.cos(a), y + r0 * math.sin(a)), (x + r * 0.9 * math.cos(a), y + r * 0.9 * math.sin(a))], WHITE, 3)
        a = math.radians(ang(value))
        self.line(d, [(x - r * 0.12 * math.cos(a), y - r * 0.12 * math.sin(a)), (x + r * 0.84 * math.cos(a), y + r * 0.84 * math.sin(a))], RED, 7)
        self.circle(d, x, y, r * 0.08, fill=METAL, width=2)
        self.text(d, x, y + r * 0.45, '%d%s' % (round(value), unit), size=r * 0.22, fill=WHITE)
        self.text(d, x, y + r + 26, label, size=24, fill=(200, 210, 225), bold=False)
    def servo(self, d, x, y, arm=0.0, s=1.0, hot=0.0):
        """a servo seen from the side: case, mounting tabs, output spline and arm turned by arm degrees, its lead; hot 0..1
        reddens the case"""
        body = (int(52 + 170 * hot), int(58 - 18 * hot), int(70 - 34 * hot))
        self.line(d, [(x - 70 * s, y + 30 * s), (x - 110 * s, y + 40 * s), (x - 150 * s, y + 70 * s)], (200, 60, 50), 5 * s)            # the lead
        self.line(d, [(x - 70 * s, y + 36 * s), (x - 108 * s, y + 47 * s), (x - 148 * s, y + 78 * s)], (230, 200, 60), 5 * s)
        self.poly(d, [(x - 70 * s, y - 44 * s), (x + 70 * s, y - 44 * s), (x + 70 * s, y + 52 * s), (x - 70 * s, y + 52 * s)], body)
        self.poly(d, [(x - 96 * s, y - 14 * s), (x + 96 * s, y - 14 * s), (x + 96 * s, y - 4 * s), (x - 96 * s, y - 4 * s)], (86, 92, 108))   # tabs
        for hx in (-84, 84): self.circle(d, x + hx * s, y - 9 * s, 4 * s, fill=(20, 24, 32), outline=None)
        self.poly(d, [(x - 52 * s, y + 10 * s), (x + 52 * s, y + 10 * s), (x + 52 * s, y + 34 * s), (x - 52 * s, y + 34 * s)], (230, 232, 238), width=1)   # its label
        self.text(d, x, y + 22 * s, 'SERVO', size=16 * s, fill=INK)
        cx, cy = x + 34 * s, y - 56 * s
        self.poly(d, [(cx - 18 * s, y - 44 * s), (cx + 18 * s, y - 44 * s), (cx + 14 * s, cy), (cx - 14 * s, cy)], body, width=2)
        self.poly(d, rot([(cx - 9 * s, cy), (cx + 9 * s, cy), (cx + 7 * s, cy - 92 * s), (cx - 7 * s, cy - 92 * s)], arm, cx, cy), WHITE)
        self.circle(d, *rot([(cx, cy - 82 * s)], arm, cx, cy)[0], 4 * s, fill=INK, outline=None)
        self.circle(d, cx, cy, 11 * s, fill=METAL)
    def transmitter(self, d, x, y, s=1.0, sticks=(0, 0, 0, 0)):
        """a radio transmitter seen from the front (a generic one: two sticks, a screen, an aerial); sticks = (left x, left y,
        right x, right y), each -1..1"""
        self.line(d, [(x + 70 * s, y - 64 * s), (x + 96 * s, y - 150 * s)], METAL, 8 * s)                                                  # aerial
        self.poly(d, [(x - 120 * s, y - 70 * s), (x + 120 * s, y - 70 * s), (x + 140 * s, y + 40 * s), (x + 110 * s, y + 90 * s), (x - 110 * s, y + 90 * s), (x - 140 * s, y + 40 * s)], (60, 66, 82))
        self.poly(d, [(x - 52 * s, y - 56 * s), (x + 52 * s, y - 56 * s), (x + 52 * s, y - 4 * s), (x - 52 * s, y - 4 * s)], (30, 60, 110), width=2)   # its screen
        self.line(d, [(x - 40 * s, y - 40 * s), (x + 30 * s, y - 40 * s)], (120, 170, 230), 4 * s); self.line(d, [(x - 40 * s, y - 24 * s), (x + 10 * s, y - 24 * s)], (120, 170, 230), 4 * s)
        for i, gx in enumerate((-82, 82)):
            cxg, cyg = x + gx * s, y + 34 * s
            self.circle(d, cxg, cyg, 30 * s, fill=(36, 40, 52), outline=METAL, width=2)
            sx, sy = sticks[2 * i], sticks[2 * i + 1]
            self.line(d, [(cxg, cyg), (cxg + 20 * s * sx, cyg - 20 * s * sy)], (210, 216, 228), 9 * s)
            self.circle(d, cxg + 20 * s * sx, cyg - 20 * s * sy, 9 * s, fill=(210, 216, 228), outline=INK, width=2)
        for gx in (-110, -86, 86, 110): self.line(d, [(x + gx * s, y - 70 * s), (x + gx * s, y - 88 * s)], METAL, 5 * s)                   # switches

    # ------------------------------------------------------------ the problems, shown (each: t in seconds -> a picture)
    def tail_wag(self, t, title='The tail wags'):
        im, d = self._canvas()
        yaw = 9.0 * math.sin(2 * math.pi * 3.2 * t) * min(1.0, t / 0.4)
        self.heli_top(d, 0, -36, yaw=yaw, s=0.72, phase=t * 1500)
        for side in (-1, 1):                                       # motion marks either side of the tail
            self.arc_arrow(d, 0, -36, 200, 90 - side * 6, 90 - side * 20, fill=(255, 214, 64, 230), width=6)
        self.title(d, title)
        return self._done(im)
    def tail_kick(self, t, title='The nose kicks round'):
        """collective pumped at 0.5 s: a climb bar, the nose kicks 24 degrees then comes back"""
        im, d = self._canvas()
        k = 0.0
        if t > 0.5: u = t - 0.5; k = 24.0 * math.sin(min(1.0, u / 0.35) * math.pi / 2) * math.exp(-max(0.0, u - 0.35) * 3.0)
        self.heli_top(d, -60, -30, yaw=k, s=0.72, phase=t * 1500)
        lv = ease((t - 0.3) / 0.3) if t < 1.6 else 1.0 - ease((t - 1.6) / 0.4)
        self.poly(d, [(250, 90), (290, 90), (290, -140), (250, -140)], (14, 18, 26), outline=METAL)
        self.poly(d, [(254, 86), (286, 86), (286, 86 - 222 * lv), (254, 86 - 222 * lv)], GREEN, outline=None)
        self.text(d, 270, 120, 'Collective', size=22, fill=(200, 210, 225), bold=False)
        if k > 4: self.arc_arrow(d, -60, -30, 112, -90, -90 + min(30, k + 6), fill=YELLOW, width=7)   # (only while the nose is round)
        self.title(d, title)
        return self._done(im)
    def tail_bounce(self, t, title='It bounces at the stop'):
        """a pirouette stopping at 1.2 s, overshooting, bouncing back"""
        im, d = self._canvas()
        if t < 1.2: yaw = 360 * (t / 1.2) ** 0.8
        else: u = t - 1.2; yaw = 360 + 22 * math.sin(2 * math.pi * 1.6 * u) * math.exp(-u * 2.2)
        self.heli_top(d, 0, -30, yaw=yaw, s=0.72, phase=t * 1500)
        self.title(d, title)
        return self._done(im)
    def wobble(self, t, title='It wobbles'):
        im, d = self._canvas()
        roll = 8.0 * math.sin(2 * math.pi * 3.6 * t) * min(1.0, t / 0.4)
        self.shadow(d, 0, 160, 260); self.heli_front(d, 0, 46, roll=roll, s=1.0)
        self.title(d, title)
        return self._done(im)
    def drift(self, t, title='It drifts off the spot'):
        im, d = self._canvas()
        self.line(d, [(20, 150), (60, 190)], YELLOW, 7); self.line(d, [(60, 150), (20, 190)], YELLOW, 7)   # (the spot)
        e = ease(t / 3.0); self.shadow(d, 40 + 140 * e, 170, 330); self.heli_side(d, 40 + 140 * e, 30 - 8 * math.sin(t * 3), pitch=-4 * e, s=0.75)
        self.title(d, title)
        return self._done(im)
    def flip_bounce(self, t, title='It bounces back after a flip'):
        im, d = self._canvas()
        if t < 1.1: p = -360 * ease(t / 1.1)
        else: u = t - 1.1; p = -360 + 26 * math.sin(2 * math.pi * 1.5 * u) * math.exp(-u * 2.2)
        self.heli_side(d, 30, 10, pitch=p, s=0.75)
        self.title(d, title)
        return self._done(im)
    def head_sag(self, t, title='The head speed sags'):
        """a climb from 0.6 s: the needle drops from 2100 to 1750, then slowly comes back"""
        im, d = self._canvas()
        c = ease((t - 0.6) / 0.5)
        rpm = 2100 - 350 * c * math.exp(-max(0.0, t - 1.4) * 1.2)
        self.heli_side(d, -160, 50 - 90 * c, pitch=-4 * c, s=0.58)
        if t > 0.6: self.arrow(d, -160, 150, -160, 90 - 60 * c, YELLOW, 7)
        self.dial(d, 190, -10, 120, rpm, 1500, 2300, 'Head speed (rpm)', good=(2050, 2150))
        self.title(d, title)
        return self._done(im)
    def buzz(self, t, title='Servos buzz or run hot'):
        im, d = self._canvas()
        jit = 2.5 * math.sin(2 * math.pi * 11 * t) + 1.5 * math.sin(2 * math.pi * 17 * t)
        hot = min(1.0, t / 3.0)
        self.servo(d, -40, 70, arm=jit, s=1.3, hot=hot)
        for i, r in enumerate((150, 180, 210)):                    # buzz marks
            a = (t * 8 + i) % 1.0
            self.arc_arrow(d, -4, -2, r, -60, -30, fill=(255, 214, 64, int(220 * (1 - a))), width=4)
        self.poly(d, [(200, -90), (230, -90), (230, 90), (200, 90)], (14, 18, 26), outline=METAL)   # a thermometer
        self.poly(d, [(204, 86), (226, 86), (226, 86 - 170 * (0.3 + 0.7 * hot)), (204, 86 - 170 * (0.3 + 0.7 * hot))], RED, outline=None)
        self.text(d, 215, 120, 'Hot', size=22, fill=(200, 210, 225), bold=False)
        self.title(d, title)
        return self._done(im)
    def glitch(self, t, title='A gap in the link'):
        """waves from the transmitter to the model; between 1.0 and 1.6 s nothing gets through, and the model twitches"""
        im, d = self._canvas()
        self.transmitter(d, -250, 40, s=0.75)
        gap = 1.0 <= t < 1.6
        tw = 6 * math.sin(2 * math.pi * 7 * t) if gap else 0.0
        self.heli_side(d, 258, 10 + tw, pitch=tw * 1.5, s=0.46)
        for i in range(5):                                         # the waves, travelling right
            x = -150 + ((t * 160 + i * 52) % 260)
            lost = gap and x > -100
            col = (RED if lost else YELLOW) + ((90 if lost else 230),)
            self.line(d, [(x, -36), (x + 12, 4), (x, 44)], col, 6)
        if gap: self.text(d, 0, 120, 'nothing arrives', size=28, fill=RED)
        self.title(d, title)
        return self._done(im)
    def feel(self, t, title='Too twitchy, or too slow'):
        """two of them, the same stick: one rolls in a flash, the other takes its time"""
        im, d = self._canvas()
        u = (t % 2.0)
        fast = -60 * ease(u / 0.22) if u < 1.2 else -60 * (1 - ease((u - 1.2) / 0.22))
        slow = -60 * ease(u / 1.2) if u < 1.2 else -60 * (1 - ease((u - 1.2) / 0.8))
        self.heli_front(d, -190, 30, roll=fast, s=0.62); self.heli_front(d, 190, 30, roll=slow, s=0.62)
        self.text(d, -190, 150, 'Twitchy', size=28, fill=YELLOW); self.text(d, 190, 150, 'Slow', size=28, fill=YELLOW)
        self.title(d, title)
        return self._done(im)
    def timeline(self, t, bars, length, title='One after the other'):
        """bars: [(name, start, end)] in seconds on a time line of length seconds; a playhead moves along with t, and a bar
        it is inside lights up"""
        im, d = self._canvas()
        x0, x1 = -300, 300; y0 = -60
        def X(sec): return x0 + (x1 - x0) * sec / float(length)
        self.line(d, [(x0, y0 + 150), (x1, y0 + 150)], METAL, 3)
        for sec in range(int(length) + 1):
            self.line(d, [(X(sec), y0 + 144), (X(sec), y0 + 156)], METAL, 3); self.text(d, X(sec), y0 + 178, '%d s' % sec, size=20, fill=(200, 210, 225), bold=False)
        for i, (name, a, b) in enumerate(bars):
            y = y0 + i * 70; on = a <= t < b
            self.poly(d, [(X(a), y - 22), (X(b), y - 22), (X(b), y + 22), (X(a), y + 22)], YELLOW if on else (70, 80, 100), outline=WHITE if on else METAL)
            self.text(d, (X(a) + X(b)) / 2, y, name, size=24, fill=INK if on else WHITE)
        px = X(min(t, length)); self.line(d, [(px, y0 - 50), (px, y0 + 160)], RED, 4)
        self.title(d, title)
        return self._done(im)

    # ------------------------------------------------------------ for the films of the pages (18 Oct, the second pass)
    def sticks_calib(self, t, title='Every stick to every end'):
        """both sticks round the edges of their travel, twice, then back to the middle"""
        im, d = self._canvas()
        if t < 3.0:
            a = 2 * math.pi * t / 1.5; r = min(1.0, t / 0.3)
            sx, sy = math.cos(a), math.sin(a); m = max(abs(sx), abs(sy)); sx, sy = r * sx / m, r * sy / m    # (round the square: to every corner)
            sticks = (sx, sy, -sx, sy)
        else: k = 1 - ease((t - 3.0) / 0.5); sticks = (k, 0, -k, 0)
        self.transmitter(d, 0, 30, s=1.45, sticks=sticks)
        self.title(d, title)
        return self._done(im)
    def rescue(self, t, title='Rescue: upright, level, climb'):
        """upside down; the flip upright (0.4 to 1.2 s); then the climb"""
        im, d = self._canvas()
        roll = 180 * (1 - ease((t - 0.4) / 0.8))
        up = 100 * ease((t - 1.4) / 1.4)
        self.heli_front(d, 0, 70 - up, roll=roll, s=0.75)
        if t > 1.4: self.arrow(d, 230, 130, 230, 70 - up * 0.9, YELLOW, 8)
        self.title(d, title)
        return self._done(im)
    def governor_hold(self, t, title='The governor holds the head speed'):
        """the same climb as head_sag, the needle barely moving: what a well-set governor does"""
        im, d = self._canvas()
        c = ease((t - 0.6) / 0.5)
        rpm = 2100 - 40 * c * math.exp(-max(0.0, t - 1.0) * 4.0)
        self.heli_side(d, -160, 50 - 90 * c, pitch=-4 * c, s=0.58)
        if t > 0.6: self.arrow(d, -160, 150, -160, 90 - 60 * c, YELLOW, 7)
        self.dial(d, 190, -10, 120, rpm, 1500, 2300, 'Head speed (rpm)', good=(2050, 2150))
        self.title(d, title)
        return self._done(im)
    def servo_centre(self, t=0.0, title='Arm at right angles, sticks centred'):
        """a servo, its arm square to the pushrod at the centre: equal travel each way"""
        im, d = self._canvas()
        self.servo(d, -60, 90, arm=0.0, s=1.3)
        cx, cy = -60 + 34 * 1.3, 90 - 56 * 1.3; tip = (cx, cy - 82 * 1.3)
        self.line(d, [tip, (tip[0] + 290, tip[1])], METAL, 6)                                              # the pushrod
        self.circle(d, tip[0] + 290, tip[1], 8, fill=METAL)
        self.line(d, [(tip[0] + 26, tip[1]), (tip[0] + 26, tip[1] + 26), (tip[0], tip[1] + 26)], YELLOW, 4)   # the square corner
        self.text(d, tip[0] + 90, tip[1] + 44, '90 degrees', size=26, fill=YELLOW)
        self.title(d, title)
        return self._done(im)
    def buddy(self, t, title='Instructor and pupil'):
        """the pupil's transmitter talks to the instructor's, which flies the model; the switch decides whose sticks count"""
        im, d = self._canvas()
        pupil = (t % 4.0) >= 1.2
        self.transmitter(d, -250, 70, s=0.62, sticks=((0.5 * math.sin(t * 3), 0, 0, 0) if pupil else (0, 0, 0, 0)))
        self.transmitter(d, 20, 70, s=0.62, sticks=((0, 0, 0.5 * math.sin(t * 3), 0) if not pupil else (0, 0, 0, 0)))
        self.text(d, -250, 160, 'Pupil', size=26, fill=YELLOW if pupil else (160, 170, 186)); self.text(d, 20, 160, 'Instructor', size=26, fill=YELLOW if not pupil else (160, 170, 186))
        self.heli_side(d, 300, 0, pitch=0, s=0.36)
        for i in range(3):
            x = -170 + ((t * 120 + i * 30) % 90); self.line(d, [(x, 0), (x + 8, 24), (x, 48)], (YELLOW if pupil else METAL) + (230,), 5)
            x = 110 + ((t * 120 + i * 30) % 90); self.line(d, [(x, -10), (x + 8, 14), (x, 38)], YELLOW + (230,), 5)
        self.title(d, title)
        return self._done(im)
    def aerials(self, t=0.0, title='Aerials at right angles'):
        """a receiver with its two aerials ninety degrees apart (their lines meet inside the receiver: the arc is drawn there)"""
        im, d = self._canvas()
        self.poly(d, [(-80, 30), (80, 30), (80, 110), (-80, 110)], (52, 58, 72))
        self.text(d, 0, 70, 'RECEIVER', size=24, fill=WHITE)
        for sx in (-1, 1):
            self.line(d, [(sx * 60, 30), (sx * 60, 0), (sx * 160, -100)], METAL, 5)
            self.line(d, [(sx * 160, -100), (sx * 188, -128)], WHITE, 7)          # (the bare tips)
        self.arc_arrow(d, 0, 60, 150, -135, -45, fill=YELLOW, width=5)
        self.text(d, 0, -60, '90 degrees', size=26, fill=YELLOW)
        self.title(d, title)
        return self._done(im)
    def battery(self, t=0.0, cells=6, volts=3.5, title='Volts per cell'):
        """a flight pack of so many cells, each showing its voltage"""
        im, d = self._canvas()
        w = 64; x0 = -cells * w / 2
        for i in range(cells):
            x = x0 + i * w; lvl = max(0.0, min(1.0, (volts - 3.0) / 1.2))
            self.poly(d, [(x + 4, -60), (x + w - 4, -60), (x + w - 4, 100), (x + 4, 100)], (40, 46, 60), outline=METAL)
            col = GREEN if volts >= 3.7 else YELLOW if volts >= 3.5 else RED
            self.poly(d, [(x + 10, 94), (x + w - 10, 94), (x + w - 10, 94 - 148 * lvl), (x + 10, 94 - 148 * lvl)], col, outline=None)
        self.text(d, 0, 150, '%dS: %.2f volts a cell, %.1f volts in all' % (cells, volts, cells * volts), size=26, fill=WHITE)
        self.title(d, title)
        return self._done(im)

