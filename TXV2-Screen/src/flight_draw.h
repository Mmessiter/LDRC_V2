// The flight screen's drawing (lib/LdrcFlight is the thinking, src/flight_device.h the rest). Drawn with whatever gfx
// points at - our own layer on the transmitter, the picture on the Mac (hmi/render_host draws it with this file).
#pragma once
#include "LdrcFlight.h"

// (FL_ON_GROUND: the quieter words on the pages' black ground - light grey in every theme: a light theme's own quieter
// colour is dark, made for its light panels, and did not read on black)
static const uint16_t FL_GROUND = 0x0000, FL_DIM = 0x8410, FL_ON_GROUND = 0xC618, FL_YELLOW = 0xFFE0, FL_GREEN = 0x87F0, FL_AMBER = 0xFD20,
                      FL_RED = 0xD800, FL_BUTTON = 0xD69A, FL_CHOSEN = 0xFFF3;
#define FL_STRIP OUR_STRIP                                      // the pilot's colours (src/theme_device.h): navy and white unless chosen
#define FL_FACE OUR_PANEL
#define FL_EDGE (theme.edge())
#define FL_INK OUR_INK
#define FL_SOFT OUR_SOFT
#define FL_LINE OUR_INK
#define FL_ACCENT (theme.accent())                              // yellow on a dark theme; on a light one (white, yellow, sky) its text colour: yellow does not read there

static void flClip(const ldrc::FlightRect &r) { clipX0 = max(0, (int) r.x); clipY0 = max(0, (int) r.y); clipX1 = min(W, r.x + r.w); clipY1 = min(H, r.y + r.h); }
static void flUnclip() { clipX0 = 0; clipY0 = 0; clipX1 = W; clipY1 = H; }
static void flText(int x, int y, int font, uint16_t col, const std::string &s) { gfx->startWrite(); drawGlyphs(x, y, font, col, s); gfx->endWrite(); }
static std::string flCut(const std::string &s, int font, int maxW) {                    // what fits, with dots if something had to go
    if (textWidth(font, s) <= maxW) return s;
    std::string t = s;
    while (!t.empty() && textWidth(font, t + "...") > maxW) t.erase(t.size() - 1);
    return t + "...";
}
// The screen's letters, measured for the flight screen's sizes (each box's number as big as the box allows)
struct ScreenFonts : public ldrc::FlightFonts {
    int width(int font, const std::string &s) override { return textWidth(font, s); }
    int height(int font) override { return fontHeight(font); }
};
static ScreenFonts flightFonts;
// A number at its box's size (s16: 16ths of the 64-pixel font, worked out by the flight screen from the widest value the
// box can expect, so it does not jump as the value changes), its unit after it at half that size, both in the middle of
// the area; smaller only if this value is wider than expected (a timer past the hour, a long bank name).
static void flNumber(const ldrc::FlightRect &a, const std::string &big, const std::string &unit, int s16, uint16_t ink, uint16_t unitInk) {
    const int nf = ldrc::FLIGHT_NUMBER_FONT, uf = ldrc::FLIGHT_UNIT_FONT;
    const int natural = textWidth(nf, big) + (unit.empty() ? 0 : 8 + textWidth(uf, unit));
    if (natural > 0 && natural * s16 / 16 > a.w) s16 = a.w * 16 / natural;
    if (s16 == 17) s16 = 16;                                      // (a sixteenth bigger is not worth the font's own crisp letters)
    if (s16 < 8) {                                                // too small for the big letters: the plain 28-pixel ones, cut to fit
        const int uw = unit.empty() ? 0 : textWidth(2, unit) + 6;
        const int bf = textWidth(6, big) <= a.w - uw ? 6 : 2;        // (28 px where it fits, else 24 px: "RAW 420 MCM" whole, not "RAW 420 M...")
        const std::string b = flCut(big, bf, a.w - uw); const int bw = textWidth(bf, b);
        const int x0 = a.x + (a.w - bw - uw) / 2, y0 = a.y + (a.h - fontHeight(bf)) / 2;
        flText(x0, y0, bf, ink, b);
        if (uw) flText(x0 + bw + 6, y0 + fontHeight(bf) - fontHeight(2), 2, unitInk, unit);
        return;
    }
    // the 64-pixel font from three quarters of its size up; below that the 32-pixel one, enlarged (smoother than shrunk)
    const int font = s16 >= 12 ? nf : 0, fs16 = font == nf ? s16 : s16 * 2;
    const int bw = textWidth(font, big) * fs16 / 16, gap = unit.empty() ? 0 : 8 * s16 / 16, uw = unit.empty() ? 0 : textWidth(uf, unit) * s16 / 16;
    const int fh = fontHeight(font) * fs16 / 16, x0 = a.x + (a.w - (bw + gap + uw)) / 2, y0 = a.y + (a.h - fh) / 2;
    gfx->startWrite();
    drawGlyphsScaled(x0, y0, font, ink, big, fs16);
    if (uw) drawGlyphsScaled(x0 + bw + gap, y0 + fh - fontHeight(uf) * s16 / 16 - 6 * s16 / 16, uf, unitInk, unit, s16);
    gfx->endWrite();
}

// ------------------------------------------------------------------ round dials (1.11.102)
// (Malcolm, 21 Oct 2026: "optionally allow some or even all of the numeric displays to be analogue in a round dial for
// those who like things to look traditional") A gauge: a rim two thirds of the way round, numbered ticks, a needle from
// the pivot. A clock: a full face with hour and minute hands; a timer: a minute hand and a seconds hand. No digits with a
// dial (1.11.103, Malcolm: "Where a round dial imparts the needed information, there's no need to put the nominal digits
// there as well. Just the dial and its name"): a gauge is drawn as big as its arc allows - one and a half radii tall, not
// two. Lines, circles and triangles only: the Mac renders it with the same code (hmi/render_host).
static const int FL_DIAL_MIN_R = 52;                              // (smaller than this an instrument cannot be read: the box keeps its digits)
static void flBatteryBeside(const ldrc::FlightTile &t, int part, int x, int y, int nameH, int room, uint16_t edge, uint16_t fill);   // (below: the little battery, drawn on a face too)
static const float FL_PI = 3.14159265f, FL_SWEEP = 120.0f;        // a gauge's scale: from 120 degrees before the top to 120 after (eight o'clock to four)
static float flDialAngle(const ldrc::FlightDial &d, float v) {   // where a gauge's scale puts a value: from the top, clockwise
    float f = d.hi > d.lo ? (v - d.lo) / (d.hi - d.lo) : 0; if (f < 0) f = 0; if (f > 1) f = 1;
    return (-FL_SWEEP + 2 * FL_SWEEP * f) * FL_PI / 180.0f;
}
static void flPolar(int cx, int cy, float r, float a, int &x, int &y) { x = cx + (int) lroundf(r * sinf(a)); y = cy - (int) lroundf(r * cosf(a)); }
static void flTick(int cx, int cy, float a, float r1, float r2, int thick, uint16_t col) {   // a line along a radius, thick px wide
    int x1, y1, x2, y2; flPolar(cx, cy, r1, a, x1, y1); flPolar(cx, cy, r2, a, x2, y2);
    gfx->drawLine(x1, y1, x2, y2, col);
    if (thick >= 2) { const int ox = (int) lroundf(cosf(a)), oy = (int) lroundf(sinf(a)); gfx->drawLine(x1 + ox, y1 + oy, x2 + ox, y2 + oy, col); }   // (its neighbour across)
}
static void flArc(int cx, int cy, float r, float a0, float a1, int thick, uint16_t col) {   // part of a circle, as chords of about four pixels
    const float step = r > 4 ? 4.0f / r : 1.0f;
    for (int k = 0; k < 2 * thick - 1; ++k) {                         // (rings half a pixel apart: no holes between them on the diagonals)
        const float rk = r - k * 0.5f;
        int px, py; flPolar(cx, cy, rk, a0, px, py);
        for (float a = a0 + step; a < a1 + step; a += step) {
            int x, y; flPolar(cx, cy, rk, a > a1 ? a1 : a, x, y);
            gfx->drawLine(px, py, x, y, col); px = x; py = y;
        }
    }
}
static void flHand(int cx, int cy, float a, float len, float tail, int w, uint16_t col) {   // from the pivot: w px wide there, pointed, a tail behind
    int tx, ty, bx, by; flPolar(cx, cy, len, a, tx, ty); flPolar(cx, cy, -tail, a, bx, by);
    const int px = (int) lroundf(cosf(a) * w / 2.0f), py = (int) lroundf(sinf(a) * w / 2.0f);   // (across the hand)
    gfx->fillTriangle(tx, ty, cx + px, cy + py, cx - px, cy - py, col);
    if (tail > 0) gfx->fillTriangle(bx, by, cx + px, cy + py, cx - px, cy - py, col);
}
static void flTextBold(int x, int y, int font, uint16_t col, const std::string &s) {   // the letters again a pixel over: bold, as an instrument's numerals are (fonts 0 and 1 are bold already)
    flText(x, y, font, col, s); if (font != 0 && font != 1) flText(x + 1, y, font, col, s);
}
// A bar along a radius, w pixels wide (a tick); one wide, a line
static void flRadialBar(int cx, int cy, float a, float r1, float r2, int w, uint16_t col) {
    int x1, y1, x2, y2; flPolar(cx, cy, r1, a, x1, y1); flPolar(cx, cy, r2, a, x2, y2);
    if (w <= 1) { gfx->drawLine(x1, y1, x2, y2, col); return; }
    const float ax = cosf(a) * w / 2.0f, ay = sinf(a) * w / 2.0f;    // (half the width, across the radius)
    const int p1x = (int) lroundf(x1 + ax), p1y = (int) lroundf(y1 + ay), p2x = (int) lroundf(x1 - ax), p2y = (int) lroundf(y1 - ay);
    const int p3x = (int) lroundf(x2 - ax), p3y = (int) lroundf(y2 - ay), p4x = (int) lroundf(x2 + ax), p4y = (int) lroundf(y2 + ay);
    gfx->fillTriangle(p1x, p1y, p2x, p2y, p3x, p3y, col); gfx->fillTriangle(p1x, p1y, p3x, p3y, p4x, p4y, col);
}
// A watch hand: a long diamond, widest a third of the way out, pointed at both ends, a short tail behind the pivot
static void flDauphine(int cx, int cy, float a, float len, float tail, int w, uint16_t col) {
    int tx, ty, bx, by, mx, my; flPolar(cx, cy, len, a, tx, ty); flPolar(cx, cy, -tail, a, bx, by); flPolar(cx, cy, len * 0.3f, a, mx, my);
    const int px = (int) lroundf(cosf(a) * w / 2.0f), py = (int) lroundf(sinf(a) * w / 2.0f);
    gfx->fillTriangle(tx, ty, mx + px, my + py, mx - px, my - py, col);
    gfx->fillTriangle(bx, by, mx + px, my + py, mx - px, my - py, col);
}
// The instrument (1.11.104, Malcolm: "a bit more bold ... more 'real' - like a speedometer on a classic car or an expensive
// watch"): a chrome bezel lit from the upper left, a black face on a dark theme (its own colour on a light one, or when it
// warns), bold ticks and numerals, a needle with a halo and a hub cap, the name in a window above the six, the unit (and
// the LDRC mark on a big face) under the twelve. It fills its box: the box's name line goes, the face carries the name.
struct FlInstrument {
    int cx = 0, cy = 0, R = 0, bz = 0, majorLen = 0, minorLen = 0, labelFont = 4, lh = 16, hubR = 6; float labelR = 0;
    uint16_t face = 0, ink = 0, soft = 0, light = 0, dark = 0;    // the face and its markings; the bezel's chrome and its edges
};
static bool flInstrumentIn(const ldrc::FlightRect &a, FlInstrument &g) {   // false: no room for one (the digits go there instead)
    g.R = min(a.w, a.h) / 2 - 2; if (g.R < FL_DIAL_MIN_R) return false;
    g.cx = a.x + a.w / 2; g.cy = a.y + a.h / 2;
    g.bz = max(5, g.R / 14); g.majorLen = max(10, g.R / 7); g.minorLen = max(6, g.majorLen * 11 / 20); g.hubR = max(6, g.R / 8);
    g.labelFont = g.R >= 150 ? 0 : g.R >= 80 ? 2 : 4; g.lh = fontHeight(g.labelFont);   // the numerals: 32 px bold, 24 px, or the 16 px typewriter ones on a small face
    g.labelR = g.R - g.bz - 2 - g.majorLen - 4 - g.lh / 2.0f;    // (just inside the ticks)
    return true;
}
static void flInstrumentColours(FlInstrument &g, uint16_t boxFace, uint16_t ink, ldrc::FlightState state) {
    const bool warn = state == ldrc::FS_WARN || state == ldrc::FS_ALARM;
    g.face = warn || ldrc::themeIsLight(boxFace) ? boxFace : ldrc::themeBlend(boxFace, 0x0000, 30);   // (a warning: the whole box says so)
    g.ink = ink; g.soft = ldrc::themeBlend(ink, g.face, 72);
    const bool lightFace = ldrc::themeIsLight(g.face);
    g.light = lightFace ? 0x8C71 : 0xC618; g.dark = lightFace ? 0x2104 : 0x4208;   // (steel on a light face, chrome on a dark one)
}
static void flBezel(const FlInstrument &g) {                      // a chrome ring with dark edges, lit from the upper left; the face inside it
    gfx->fillCircle(g.cx, g.cy, g.R, g.dark);
    gfx->fillCircle(g.cx, g.cy, g.R - 1, g.light);
    gfx->fillCircle(g.cx, g.cy, g.R - g.bz + 1, g.dark);
    gfx->fillCircle(g.cx, g.cy, g.R - g.bz, g.face);
    const int th = g.bz - 3; if (th < 1) return;
    flArc(g.cx, g.cy, g.R - 2, -125 * FL_PI / 180, -15 * FL_PI / 180, th, shade(g.light, 45));   // the highlight, ten to eleven o'clock
    flArc(g.cx, g.cy, g.R - 2, 55 * FL_PI / 180, 165 * FL_PI / 180, th, shade(g.light, -40));    // the shadow opposite
}
static void flHub(const FlInstrument &g) {                        // the cap over the pivot
    gfx->fillCircle(g.cx, g.cy, g.hubR, g.dark);
    gfx->drawCircle(g.cx, g.cy, g.hubR, g.light); gfx->drawCircle(g.cx, g.cy, g.hubR - 1, g.light);
    gfx->fillCircle(g.cx, g.cy, max(2, g.hubR / 3), g.light);
}
// The words on a face: the box's name (its short name, or its unit, where the name is too wide), the unit, a battery's tag
// ("62 %") with its picture, and the small line that says why there is no number ("no model")
struct FlFaceWords { std::string name, shortName, unit, tag, note; const ldrc::FlightTile *tile = nullptr; int part = 0; uint16_t battFill = 0; };
static const char *flFaceShort(int item) {                        // a shorter name for a small face, where there is one worth having
    switch (item) { case ldrc::FL_ESC: return "ESC"; case ldrc::FL_AMPS: return "Amps"; case ldrc::FL_FPS: return "Frames"; default: return ""; }
}
// Under the twelve: the LDRC mark and/or the unit, quiet, between the numerals and the hub, in the 24 px sans letters (the
// 16 px typewriter ones have no degree sign); the mark is the first to go when there is room for one line only
static void flFaceTop(const FlInstrument &g, const char *mark, const std::string &unit) {
    const int yTop = g.cy - (int) (g.labelR - g.lh / 2.0f) + 2, yBot = g.cy - g.hubR - 2, h = yBot - yTop;
    const int font = 2, fh = fontHeight(font);
    std::vector<std::string> lines; if (mark && *mark) lines.push_back(mark); if (!unit.empty()) lines.push_back(unit);
    while (!lines.empty() && (int) lines.size() * fh > h + 4) lines.erase(lines.begin());
    const int y0 = yTop + (h - (int) lines.size() * fh) / 2;
    for (size_t i = 0; i < lines.size(); ++i) flText(g.cx - textWidth(font, lines[i]) / 2, y0 + (int) i * fh, font, g.soft, lines[i]);
}
// The window at the foot of the face (above the six): the name, and the tag or the note under it where two lines fit, else
// after it on the one line if that fits; a battery's picture after the words where there is room. The name in the biggest
// sans letters the window takes (28 px on a big face, else 24), failing those its short name, then its unit; the 16 px
// typewriter letters only when nothing else fits. true: the unit stood in for the name (it is not then written under the
// twelve as well)
static bool flFaceWindow(const FlInstrument &g, const FlFaceWords &w, int yTop, int yBot, bool noValue) {
    const int h = yBot - yTop; if (h < 14) return false;
    const int ym = (yTop + yBot) / 2 - g.cy, inner = g.R - g.bz;
    const int chord = 2 * (int) sqrtf(max(0.0f, (float) inner * inner - (float) ym * ym)) - 12;
    if (chord < 20) return false;
    const std::string second = noValue ? "--" : w.tag;            // (no number: "--" after the name; the note would not fit a face)
    auto nameAt = [&](int f, int reserve, bool &unitUsed) -> std::string {   // the name in these letters with this much kept beside it, or its short name, or its unit ("": none fits)
        unitUsed = false;
        if (textWidth(f, w.name) + reserve <= chord) return w.name;
        if (!w.shortName.empty() && textWidth(f, w.shortName) + reserve <= chord) return w.shortName;
        if (!w.unit.empty() && textWidth(f, w.unit) + reserve <= chord) { unitUsed = true; return w.unit; }
        return std::string();
    };
    const int fonts[3] = { g.R >= 150 ? 6 : 2, 2, 4 };
    int font = 4; std::string name; bool unitForName = false;
    for (int i = 0; i < 3 && name.empty(); ++i) {                   // the name alone, in the biggest letters that take it
        if (i == 1 && fonts[0] == 2) continue;
        bool u; const std::string n = nameAt(fonts[i], 0, u); if (n.empty()) continue;
        name = n; font = fonts[i]; unitForName = u;
    }
    if (name.empty()) name = flCut(w.name, 4, chord);
    int sf = font == 4 ? 4 : (fontHeight(font) + fontHeight(2) <= h + 2 ? 2 : 4);
    bool two = false, inline1 = false;
    if (!second.empty()) {
        if (fontHeight(font) + fontHeight(sf) <= h + 2) two = true;   // the second under the name
        else for (int f = 2; f <= 4 && !inline1; f += 2) {           // or beside it, in the biggest letters that take the pair
            bool u; const std::string n = nameAt(f, 10 + textWidth(f, second), u); if (n.empty()) continue;
            name = n; font = f; sf = f; unitForName = u; inline1 = true;
        }
    }
    if (font == 4) { size_t at; while ((at = name.find('\xB0')) != std::string::npos) name.erase(at, 1); }   // (no degree sign in that font)
    const int nh = fontHeight(font), sh = fontHeight(sf);
    const int nw = textWidth(font, name), sw = second.empty() ? 0 : textWidth(sf, second), iw = w.tile ? ldrc::flightGlyphW(nh) + 8 : 0;
    const bool icon = iw && nw + (inline1 ? 10 + sw : 0) + iw <= chord;   // (a battery's picture last: its percent matters more)
    const int total = nw + (inline1 ? 10 + sw : 0) + (icon ? iw : 0);
    const int y0 = yTop + (h - nh - (two ? sh : 0)) / 2, x0 = g.cx - total / 2;
    flText(x0, y0, font, g.ink, name);
    int x = x0 + nw;
    if (inline1) { flText(x + 10, y0 + nh - sh, sf, g.soft, second); x += 10 + sw; }
    if (icon) flBatteryBeside(*w.tile, w.part, x + 8, y0, nh, iw, g.soft, w.battFill);
    if (two) flText(g.cx - sw / 2, y0 + nh, sf, g.soft, second);
    return unitForName;
}
// A gauge: the scale round the top two thirds of the face, its numerals inside the ticks, the needle
static bool flGauge(const ldrc::FlightRect &a, const ldrc::FlightDial &d, const FlFaceWords &w, uint16_t boxFace, uint16_t ink, ldrc::FlightState state, uint16_t needle) {
    FlInstrument g; if (!flInstrumentIn(a, g)) return false;
    flInstrumentColours(g, boxFace, ink, state);
    flBezel(g);
    const float a0 = flDialAngle(d, d.lo), a1 = flDialAngle(d, d.hi), tickR = g.R - g.bz - 2;
    const bool lightFace = ldrc::themeIsLight(g.face);
    auto band = [&](float from, float to, uint16_t col) {           // (1.11.105) a zone on the scale, under the ticks: amber where the box would turn amber, red where red (pale on a light face)
        const float f0 = max(from, d.lo), f1 = min(to, d.hi); if (!(f1 > f0)) return;
        flArc(g.cx, g.cy, tickR, flDialAngle(d, f0), flDialAngle(d, f1), g.majorLen, lightFace ? ldrc::themeBlend(col, g.face, 45) : col);
    };
    band(d.amberFrom, d.amberTo, FL_AMBER); band(d.redFrom, d.redTo, FL_RED);
    flArc(g.cx, g.cy, tickR - g.majorLen - 1, a0, a1, 1, g.soft);    // the ring the ticks stand on
    const int majors = max(1, (int) lroundf((d.hi - d.lo) / d.major)), majorW = max(3, g.R / 25), minorW = max(1, g.R / 60);
    const bool endsOnly = g.R < 58;                                   // (a small gauge: its two ends numbered, nothing else - the numerals would touch)
    char b[16]; snprintf(b, sizeof(b), d.decimals ? "%.1f" : "%.0f", (double) d.hi);
    const bool everyOther = textWidth(g.labelFont, b) + 2 > (a1 - a0) * g.labelR / majors * 0.85f;   // (numerals wider than their room: every other one)
    for (int m = 0; m <= majors; ++m) {                               // the ticks: numbered every major, five between
        const float v = d.lo + m * d.major, am = flDialAngle(d, v);
        flRadialBar(g.cx, g.cy, am, tickR, tickR - g.majorLen, majorW, g.ink);
        if (m < majors) for (int k = 1; k < 5; ++k) flRadialBar(g.cx, g.cy, flDialAngle(d, v + d.major * k / 5), tickR, tickR - g.minorLen, minorW, g.ink);
        if (endsOnly ? (m == 0 || m == majors) : (!everyOther || (majors - m) % 2 == 0)) {   // (every other one: the top of the scale always numbered)
            snprintf(b, sizeof(b), d.decimals ? "%.1f" : "%.0f", (double) v);
            int x, y; flPolar(g.cx, g.cy, g.labelR, am, x, y); flTextBold(x - (textWidth(g.labelFont, b) + 1) / 2, y - g.lh / 2, g.labelFont, g.ink, b);
        }
    }
    const int yTop = g.cy + (int) (g.labelR / 2 + g.lh / 2) + 3, yBot = g.cy + g.R - g.bz - 4;   // the window: under the scale's ends
    const bool unitUsed = flFaceWindow(g, w, yTop, yBot, !d.has);
    if (g.R >= 80) flFaceTop(g, g.R >= 120 ? "LDRC" : "", unitUsed ? std::string() : w.unit);   // (no number: "--" in the window says so; a note up here ran into the numerals)
    if (d.has) {                                                      // the needle: to the ticks' inner ends, a halo of the face round it, a counterweight behind
        const float len = tickR - g.majorLen - 2, am = flDialAngle(d, d.value); const int nw = max(5, g.R / 10), tail = g.R / 5;
        flHand(g.cx, g.cy, am, len + 1, tail + 1, nw + 2, g.face);
        flHand(g.cx, g.cy, am, len, tail, nw, needle);
    }
    flHub(g);
    return true;
}
// A clock's face (a timer's: seconds round it): 12 3 6 9 (60 15 30 45), every hour on a big face; the minutes between; the hands
static bool flClockFace(const ldrc::FlightRect &a, const ldrc::FlightDial &d, bool timer, const FlFaceWords &w, uint16_t boxFace, uint16_t ink, ldrc::FlightState state, uint16_t needle) {
    FlInstrument g; if (!flInstrumentIn(a, g)) return false;
    flInstrumentColours(g, boxFace, ink, state);
    flBezel(g);
    const float tickR = g.R - g.bz - 2;
    gfx->drawCircle(g.cx, g.cy, (int) (tickR - g.majorLen - 1), g.soft);   // the ring the markers stand on
    const int majorW = max(3, g.R / 22), minorW = max(1, g.R / 60);
    const bool allNumbers = g.R >= 100, six = g.R >= 80;             // (a small face: 12 3 9 and the name where the six would be)
    for (int m = 0; m < 12; ++m) {
        const float am = m * FL_PI / 6;
        flRadialBar(g.cx, g.cy, am, tickR, tickR - g.majorLen, majorW, g.ink);
        if (g.R >= 56) for (int k = 1; k < 5; ++k) flRadialBar(g.cx, g.cy, am + k * FL_PI / 30, tickR, tickR - g.minorLen, minorW, g.ink);
        if ((allNumbers || m % 3 == 0) && (six || m != 6)) {
            const std::string s = std::to_string(timer ? (m == 0 ? 60 : m * 5) : (m == 0 ? 12 : m));
            int x, y; flPolar(g.cx, g.cy, g.labelR, am, x, y); flTextBold(x - (textWidth(g.labelFont, s) + 1) / 2, y - g.lh / 2, g.labelFont, g.ink, s);
        }
    }
    if (g.R >= 80) flFaceTop(g, "LDRC", "");
    flFaceWindow(g, w, g.cy + g.hubR + 4, six ? g.cy + (int) (g.labelR - g.lh / 2.0f) - 3 : g.cy + (int) (tickR - g.majorLen) - 3, !d.has);   // the window: between the hub and the six (or the ticks)
    if (d.has) {                                                      // the hands, each with a halo of the face
        if (timer) {                                                  // a minute hand, and the seconds hand sweeping
            const float secs = fmodf(d.value, 60.0f), mins = fmodf(d.value / 60.0f, 60.0f), ma = mins / 60.0f * 2 * FL_PI, sa = secs / 60.0f * 2 * FL_PI;
            const float ml = g.R * 0.55f, sl = tickR - g.majorLen - 2; const int mw = max(5, g.R / 10), sw = max(2, g.R / 30);
            flDauphine(g.cx, g.cy, ma, ml + 1, g.R / 8.0f + 1, mw + 2, g.face); flDauphine(g.cx, g.cy, ma, ml, g.R / 8.0f, mw, g.ink);
            flHand(g.cx, g.cy, sa, sl + 1, g.R / 5.0f + 1, sw + 2, g.face); flHand(g.cx, g.cy, sa, sl, g.R / 5.0f, sw, needle);
        } else {                                                      // the hour hand and the minute hand
            const float mins = fmodf(d.value, 60.0f), hours = fmodf(d.value / 60.0f, 12.0f), ha = hours / 12.0f * 2 * FL_PI, ma = mins / 60.0f * 2 * FL_PI;
            const float hl = g.R * 0.5f, ml = tickR - g.majorLen - 3; const int hw = max(6, g.R / 9), mw = max(4, g.R / 13);
            flDauphine(g.cx, g.cy, ha, hl + 1, g.R / 8.0f + 1, hw + 2, g.face); flDauphine(g.cx, g.cy, ha, hl, g.R / 8.0f, hw, g.ink);
            flDauphine(g.cx, g.cy, ma, ml + 1, g.R / 7.0f + 1, mw + 2, g.face); flDauphine(g.cx, g.cy, ma, ml, g.R / 7.0f, mw, g.ink);
        }
    }
    flHub(g);
    return true;
}
// A box's instrument in an area. false: the area is too small for one (the digits go there instead)
static bool flDial(const ldrc::FlightRect &a, const ldrc::FlightDial &d, const FlFaceWords &w, uint16_t boxFace, uint16_t ink, ldrc::FlightState state, uint16_t needle) {
    if (d.kind == ldrc::FD_GAUGE) return flGauge(a, d, w, boxFace, ink, state, needle);
    if (d.kind == ldrc::FD_CLOCK || d.kind == ldrc::FD_TIMER) return flClockFace(a, d, d.kind == ldrc::FD_TIMER, w, boxFace, ink, state, needle);
    return false;
}
static bool flDialFits(const ldrc::FlightRect &a) { FlInstrument g; return flInstrumentIn(a, g); }   // room for an instrument in this area?

static void flRaised(const ldrc::FlightRect &r, uint16_t face, bool down) {             // the buttons' face and their 3D edge
    const uint16_t hi = shade(face, 60), lo = shade(face, -45);
    gfx->fillRect(r.x, r.y, r.w, r.h, face);
    for (int k = 0; k < 2; ++k) {
        gfx->drawFastHLine(r.x + k, r.y + k, r.w - 2 * k, down ? lo : hi); gfx->drawFastVLine(r.x + k, r.y + k, r.h - 2 * k, down ? lo : hi);
        gfx->drawFastHLine(r.x + k, r.y + r.h - 1 - k, r.w - 2 * k, down ? hi : lo); gfx->drawFastVLine(r.x + r.w - 1 - k, r.y + k, r.h - 2 * k, down ? hi : lo);
    }
}

// Channel bars, eight to a column: each grows from the centre line, the normal travel (1000 to 2000 us: 25 to 75 of the
// front page's 0 to 100) reaching the side. No channel numbers (1.11.107: Malcolm, "simpler without and easy enough to count").
static void flBars(const ldrc::FlightRect &a, const std::vector<uint8_t> &bars, size_t from, uint16_t track, uint16_t fill, uint16_t ink) {
    const int rows = 8, rowH = a.h / rows, barH = max(3, rowH - (rowH >= 12 ? 5 : 2));
    const int y0 = a.y + (a.h - rows * rowH) / 2;                 // (the eight rows centred in the room given)
    const int cx = a.x + a.w / 2, half = a.w / 2;
    for (int i = 0; i < rows && from + i < bars.size(); ++i) {
        const int y = y0 + i * rowH + (rowH - barH) / 2;
        gfx->fillRect(a.x, y, a.w, barH, track);
        float d = ((int) bars[from + i] - 50) / 25.0f; if (d > 1) d = 1; if (d < -1) d = -1;
        const int len = (int) (d * half);
        if (len > 0) gfx->fillRect(cx, y, len, barH, fill); else if (len < 0) gfx->fillRect(cx + len, y, -len, barH, fill);
    }
    gfx->drawFastVLine(cx, y0, rows * rowH, ink);              // the centre line
}

// The model's picture (the front page's: 320 x 200 on the card), read once into memory: the same picture in two boxes, or
// a box drawn again, does not go back to the card (Malcolm, 10-04: in two boxes "I only get the image in the first").
// Forgotten when the flight screen goes (flPicForget), so a new photo of the same name is read afresh next time.
static std::string flPicPath; static uint16_t *flPicPx = nullptr; static int flPicW = 0, flPicH = 0;
static void flPicForget() { free(flPicPx); flPicPx = nullptr; flPicPath.clear(); flPicW = flPicH = 0; }
// A picture that would not come (the card over SPI gives the odd failed read; a file not there yet) is asked for again a
// few times, a little apart: a box is only drawn again when something in it changes, so one failure would otherwise
// stand until the model changed (Malcolm, 10-04: "just occasionally, when I select a new model, which has an image, when
// I return to the front screen, it says there's no image. I can reselect it and then it's okay again").
static const int FL_PIC_TRIES = 8;
static std::string flPicFailPath; static int flPicFails = 0; static uint32_t flPicFailAt = 0; static bool flPicFailed = false;
static void flPicFail(const std::string &path, const char *why) {
    if (path != flPicFailPath) { flPicFailPath = path; flPicFails = 0; }
    ++flPicFails; flPicFailAt = millis(); flPicFailed = true;
    if (flPicFails <= 2 || flPicFails == FL_PIC_TRIES) blog("flight", "picture not read (" + std::string(why) + ", try " + std::to_string(flPicFails) + "): " + path);
}
static bool flPicRetryDue(uint32_t now) {               // the screen asks at each pass: time to try that picture again?
    if (!flPicFailed || flPicFails >= FL_PIC_TRIES || now - flPicFailAt < 600) return false;
    flPicFailed = false; return true;
}
static bool flPicLoad(const std::string &base) {
    const std::string path = imagePath(base);
    if (flPicPx && path == flPicPath) return true;
    File f = sdOpenChecked(path.c_str());
    if (!f) { flPicFail(path, "no such file"); return false; }
    uint16_t wh[2] = { 0, 0 };
    if (f.read((uint8_t *) wh, 4) != 4 || !wh[0] || !wh[1] || wh[0] > 800 || wh[1] > 480) { f.close(); flPicFail(path, "header"); return false; }
    const size_t bytes = (size_t) wh[0] * wh[1] * 2;
    uint16_t *px = (uint16_t *) psMallocRoom(bytes);   // (1.11.131: room made by giving up a resident background if need be)
    if (!px) { f.close(); flPicFail(path, "no memory"); return false; }
    const size_t got = sdReadPaced(f, (uint8_t *) px, bytes);   // (1.11.120: in paced slabs - main.cpp)
    f.close();
    if (got != bytes) { free(px); flPicFail(path, "short read"); return false; }
    flPicForget(); flPicPx = px; flPicW = wh[0]; flPicH = wh[1]; flPicPath = path;
    if (flPicFails) blog("flight", "picture read at try " + std::to_string(flPicFails + 1) + ": " + path);
    flPicFailPath.clear(); flPicFails = 0; flPicFailed = false;
    return true;
}
// That picture fitted to the area, its shape kept, in the middle
static bool flImage(const ldrc::FlightRect &a, const std::string &fromTeensy) {
    std::string base = fromTeensy.substr(fromTeensy.find_last_of("/\\") == std::string::npos ? 0 : fromTeensy.find_last_of("/\\") + 1);
    const size_t dot = base.find_last_of('.'); if (dot != std::string::npos) base = base.substr(0, dot);
    if (base.empty() || !sdOk || a.w < 8 || a.h < 8 || !flPicLoad(base)) return false;
    const int sw = flPicW, sh = flPicH;
    int dw = a.w, dh = a.w * sh / sw; if (dh > a.h) { dh = a.h; dw = a.h * sw / sh; }
    const int ox = a.x + (a.w - dw) / 2, oy = a.y + (a.h - dh) / 2;
    std::vector<uint16_t> out(dw);
    for (int y = 0; y < dh; ++y) {
        const uint16_t *src = flPicPx + (size_t) (y * sh / dh) * sw;
        for (int x = 0; x < dw; ++x) out[x] = src[x * sw / dw];
        gfx->draw16bitRGBBitmap(ox, oy + y, out.data(), dw, 1);
    }
    return true;
}

// One box: its name at the top, the number big in the middle with its unit, a small line at the bottom.
// (1.11.70) A box of two parts (the batteries: RX above, TX below; AMS above, trims below). (1.11.73, Malcolm 15 Oct: "one box
// is made to appear as 2 smaller ones. I think one box is better - with 2 items in it") ONE box: one face, one frame, a thin
// line between its two items. A part that needs a look turns its own half amber or red, and the box's frame white, as any
// box's. ldrc::flightPartPlan says where each part's name, number and small line go - the sizing (flightSizeTiles) used the
// same sums. (1.11.103, Malcolm 21 Oct: "make the corners square and remove the tiny gap": the boxes touch, each with its
// own thin frame, so two boxes meet at a two-pixel line; nothing is rounded.)
static uint16_t flPartFace(const ldrc::FlightTile &t, ldrc::FlightState state, uint16_t face) {
    using namespace ldrc;
    if (state == FS_WARN) face = FL_AMBER;
    else if (state == FS_ALARM) face = FL_RED;
    if (t.pressed) face = shade(face, ldrc::themeIsLight(face) ? -20 : -30);
    return face;
}
static void flTwoPartBox(const ldrc::FlightTile &t, bool setup) {
    using namespace ldrc;
    const FlightRect &r = t.r; const FlightValue &v = t.v;
    const bool own = t.own;
    const uint16_t face = own ? t.face : FL_FACE, ink = own ? t.ink : FL_INK;
    FlightRect up, low; flightSplit(r, up, low);
    const int mid = up.y + up.h + (low.y - up.y - up.h) / 2;     // the line between the two items: the middle of the gap
    gfx->fillRect(r.x, r.y, r.w, r.h, flPartFace(t, FS_NORMAL, face));
    const FlightState st[2] = { v.state, v.state2 };
    bool look = false;
    for (int k = 0; k < 2; ++k) {
        if (st[k] != FS_WARN && st[k] != FS_ALARM) continue;
        look = true;
        const uint16_t c = flPartFace(t, st[k], face);
        if (k == 0) gfx->fillRect(r.x, r.y, r.w, mid - r.y, c); else gfx->fillRect(r.x, mid, r.w, r.y + r.h - mid, c);
    }
    if (look)                                                     // (as a box: a thick white frame with the colour)
        for (int k = 0; k < 4; ++k) gfx->drawRect(r.x + k, r.y + k, r.w - 2 * k, r.h - 2 * k, 0xFFFF);
    else if (setup) {                                             // (1.11.105: no frame or line in flight - Malcolm, "remove the fine line that separates one box from the next"; the setup page keeps quiet ones, its boxes are things to touch)
        gfx->drawRect(r.x, r.y, r.w, r.h, FL_SOFT);
        gfx->drawFastHLine(r.x + 1, mid, r.w - 2, FL_SOFT);
    }
}
// (1.11.97, Malcolm 19 Oct: "in the box that shows receiver and transmitter voltage, please, could we have the little picture
// of a battery, as we did on the original screen") A battery beside the part's name, filled to its per cent, where there is
// room for it (flightPartPlan keeps the room in a part 180 px wide or more; a narrower one keeps its words).
static void flBatteryBeside(const ldrc::FlightTile &t, int part, int x, int y, int nameH, int room, uint16_t edge, uint16_t fill) {
    if (t.item != ldrc::FL_BATTS) return;
    const int level = part ? t.v.level2 : t.v.level;
    const int h = ldrc::flightGlyphH(nameH), w = ldrc::flightGlyphW(nameH);
    if (level < 0 || h < 8 || room < w) return;
    y += (nameH - h) / 2;
    gfx->drawRect(x, y, w - 3, h, edge);
    gfx->fillRect(x + w - 3, y + h / 4, 3, h - 2 * (h / 4), edge);      // the terminal
    const int fw = (w - 3 - 4) * (level > 100 ? 100 : level) / 100;
    if (fw > 0) gfx->fillRect(x + 2, y + 2, fw, h - 4, fill);
}
static void flPart(const ldrc::FlightRect &p, const ldrc::FlightTile &t, int part, const std::string &label, const std::string &big,
                   const std::string &unit, const std::string &small, const std::string &tag, ldrc::FlightState state, int scale) {
    using namespace ldrc;
    const bool own = t.own;
    const uint16_t face = flPartFace(t, state, own ? t.face : FL_FACE);
    uint16_t ink = own ? t.ink : FL_INK, soft = own ? ldrc::themeBlend(t.ink, t.face, 72) : FL_SOFT;
    if (state == FS_WARN) { ink = 0x0000; soft = 0x0000; }
    else if (state == FS_ALARM) { ink = 0xFFFF; soft = 0xFFFF; }
    const bool lightFace = ldrc::themeIsLight(face);
    const uint16_t dim = own || lightFace ? soft : FL_DIM;
    const uint16_t valueInk = state == FS_STALE ? dim : state == FS_GOOD ? (lightFace ? ink : FL_GREEN) : ink;
    const uint16_t fillInk = (state == FS_WARN || state == FS_ALARM) ? ink : (lightFace ? ink : FL_GREEN);   // (1.11.97) the battery picture's charge
    const FlightPartPlan pl = flightPartPlan(p, t.item, part, &flightFonts);
    const int nameH = fontHeight(pl.font), wpad = 10;
    flClip(FlightRect(p.x + 2, p.y + 2, p.w - 4, p.h - 4));
    if (pl.row) {                                                 // the short name on the left, its tag under it (both lines, centred together)
        const std::string nm = flCut(flightPartShort(t.item, part), pl.font, pl.column);
        const bool two = pl.tagBelow && !tag.empty() && textWidth(pl.font, tag) <= pl.column;
        const int y0 = p.y + (p.h - nameH * (two ? 2 : 1)) / 2;
        flText(p.x + wpad, y0, pl.font, soft, nm);
        if (two) flText(p.x + wpad, y0 + nameH, pl.font, soft, tag);
        flBatteryBeside(t, part, p.x + wpad + textWidth(pl.font, nm) + 8, y0, nameH, pl.column - textWidth(pl.font, nm) - 8, soft, fillInk);
    } else {                                                      // the name above, its tag at the right of the same line
        const int tw = tag.empty() ? 0 : textWidth(pl.font, tag);
        if (tw) flText(p.x + p.w - wpad - tw, p.y + 8, pl.font, soft, tag);
        const std::string nm = flCut(label, pl.font, p.w - 2 * wpad - (tw ? tw + 12 : 0));
        flText(p.x + wpad, p.y + 8, pl.font, soft, nm);
        flBatteryBeside(t, part, p.x + wpad + textWidth(pl.font, nm) + 8, p.y + 8, nameH, p.w - 2 * wpad - textWidth(pl.font, nm) - 8 - (tw ? tw + 12 : 0), soft, fillInk);
    }
    const FlightDial &md = part ? t.meter2 : t.meter;             // (1.11.102) a dial, where the part has one and the room for it
    bool dialed = false;
    if (t.dial && md.kind != FD_NONE) {
        FlightRect da = pl.number; if (!pl.row && pl.small) da.h = (int16_t) (da.h + nameH + 8);   // (no small line under a dial: its room goes to the dial)
        const uint16_t needle = (state == FS_WARN || state == FS_ALARM) ? ink : state == FS_STALE ? dim : lightFace ? ink : FL_YELLOW;   // (an old value: a dim needle, as its digits would be dim)
        FlFaceWords w; w.unit = unit; w.note = small;             // (the part's name is beside the face, not on it)
        dialed = flDialFits(da) && flDial(da, md, w, face, ink, state, needle);
    }
    if (!dialed) {
        if (!pl.row && pl.small && !small.empty()) flText(p.x + wpad, p.y + p.h - nameH - 8, pl.font, soft, flCut(small, pl.font, p.w - 2 * wpad));
        flNumber(pl.number, big, unit, scale, valueInk, state == FS_STALE ? FL_DIM : soft);
    }
    flUnclip();
}

// (1.11.102) A box of two parts as two instruments side by side (the batteries: RX on the left, TX on the right; stacked,
// neither half would have the height for one). Each face carries its half's name, tag and battery picture (1.11.104).
// false: no room for two this way either (the stacked box with its digits is drawn instead)
static bool flTwoDialBox(const ldrc::FlightTile &t, bool setup) {
    using namespace ldrc;
    const FlightRect &r = t.r; const FlightValue &v = t.v;
    const int halfW = r.w / 2, dw = halfW - 6;                        // (both instruments one size, whichever half is the pixel wider)
    const FlightRect halves[2] = { FlightRect(r.x, r.y, halfW, r.h), FlightRect(r.x + halfW, r.y, r.w - halfW, r.h) };
    FlightRect areas[2];
    for (int k = 0; k < 2; ++k) { const FlightRect &h = halves[k]; areas[k] = FlightRect(h.x + (h.w - dw) / 2, r.y + 3, dw, r.h - 6); if (!flDialFits(areas[k])) return false; }
    const bool own = t.own;                                           // the face: as the stacked box's, the line between the halves upright (on the setup page)
    const uint16_t face = own ? t.face : FL_FACE, ink = own ? t.ink : FL_INK;
    const int mid = r.x + halfW;
    gfx->fillRect(r.x, r.y, r.w, r.h, flPartFace(t, FS_NORMAL, face));
    const FlightState st[2] = { v.state, v.state2 };
    bool look = false;
    for (int k = 0; k < 2; ++k) {
        if (st[k] != FS_WARN && st[k] != FS_ALARM) continue;
        look = true;
        const uint16_t c = flPartFace(t, st[k], face);
        if (k == 0) gfx->fillRect(r.x, r.y, mid - r.x, r.h, c); else gfx->fillRect(mid, r.y, r.x + r.w - mid, r.h, c);
    }
    if (look) for (int k = 0; k < 4; ++k) gfx->drawRect(r.x + k, r.y + k, r.w - 2 * k, r.h - 2 * k, 0xFFFF);
    else if (setup) { gfx->drawRect(r.x, r.y, r.w, r.h, FL_SOFT); gfx->drawFastVLine(mid, r.y + 1, r.h - 2, FL_SOFT); }
    for (int k = 0; k < 2; ++k) {                                     // each half: its instrument, its words on the face
        const FlightRect &h = halves[k]; const FlightState state = st[k];
        const uint16_t pface = flPartFace(t, state, face);
        uint16_t pink = ink, soft = own ? ldrc::themeBlend(t.ink, t.face, 72) : FL_SOFT;
        if (state == FS_WARN) { pink = 0x0000; soft = 0x0000; } else if (state == FS_ALARM) { pink = 0xFFFF; soft = 0xFFFF; }
        const bool lightFace = ldrc::themeIsLight(pface);
        const uint16_t dim = own || lightFace ? soft : FL_DIM;
        const uint16_t needle = (state == FS_WARN || state == FS_ALARM) ? pink : state == FS_STALE ? dim : lightFace ? pink : FL_YELLOW;
        FlFaceWords w; w.name = k ? v.label2 : v.label; w.shortName = flightPartShort(t.item, k); w.unit = k ? v.unit2 : v.unit;
        if (w.unit.empty()) w.unit = flightPartUnit(t.item, k);
        w.tag = k ? v.tag2 : v.tag; w.note = k ? v.small2 : v.small; w.tile = &t; w.part = k;
        w.battFill = (state == FS_WARN || state == FS_ALARM) ? pink : (lightFace ? pink : FL_GREEN);
        flClip(FlightRect(h.x + 2, h.y + 2, h.w - 4, h.h - 4));
        flDial(areas[k], k ? t.meter2 : t.meter, w, pface, pink, state, needle);
        flUnclip();
    }
    return true;
}

static void flightDrawTile(const ldrc::FlightTile &t, bool setup) {
    using namespace ldrc;
    const FlightRect &r = t.r; const FlightValue &v = t.v;
    gfx->fillRect(r.x, r.y, r.w, r.h, FL_GROUND);
    if (v.state == FS_EMPTY) {                                    // nothing chosen: a dim outline on the setup page, nothing in flight
        if (setup) {
            for (int k = 0; k < 2; ++k) gfx->drawRect(r.x + k, r.y + k, r.w - 2 * k, r.h - 2 * k, t.pressed ? FL_ON_GROUND : FL_DIM);
            flClip(r);
            const std::string s = "Nothing";
            flText(r.x + (r.w - textWidth(6, s)) / 2, r.y + (r.h - fontHeight(6)) / 2, 6, FL_DIM, s);
            flUnclip();
        }
        return;
    }
    if (v.twoPart && t.dial && (t.meter.kind != FD_NONE || t.meter2.kind != FD_NONE) && flTwoDialBox(t, setup)) return;   // (1.11.102) two dials side by side
    if (v.twoPart) {                                              // (1.11.70) two items in one box (1.11.71: of one height, drawn alike; 1.11.73: one box)
        FlightRect up, low; flightSplit(r, up, low);
        flTwoPartBox(t, setup);
        flPart(up, t, 0, v.label, v.big, v.unit, v.small, v.tag, v.state, t.scale);
        flPart(low, t, 1, v.label2, v.big2, v.unit2, v.small2, v.tag2, v.state2, t.scale2);
        return;
    }
    // its own theme (a panel colour and a text colour), else the screens' theme; the quieter words a
    // blend of the two, the outline a little of the text in the box colour
    const bool own = t.own;
    uint16_t face = own ? t.face : FL_FACE, ink = own ? t.ink : FL_INK, soft = own ? ldrc::themeBlend(t.ink, t.face, 72) : FL_SOFT;
    if (v.state == FS_WARN) { face = FL_AMBER; ink = 0x0000; soft = 0x0000; }
    else if (v.state == FS_ALARM) { face = FL_RED; ink = 0xFFFF; soft = 0xFFFF; }
    if (t.pressed) face = shade(face, ldrc::themeIsLight(face) ? -20 : -30);
    gfx->fillRect(r.x, r.y, r.w, r.h, face);                      // (1.11.103: square, the boxes touching; 1.11.105: no frame in flight - Malcolm, "remove the fine line that separates one box from the next")
    if (v.state == FS_WARN || v.state == FS_ALARM)               // a thick white frame as well as the colour: a red or yellow theme's boxes are almost amber and red themselves
        for (int k = 0; k < 4; ++k) gfx->drawRect(r.x + k, r.y + k, r.w - 2 * k, r.h - 2 * k, 0xFFFF);
    else if (setup) gfx->drawRect(r.x, r.y, r.w, r.h, FL_SOFT);   // (the setup page: a quiet frame, its boxes are things to touch)
    // (green for "ON" and grey for "--" on a dark box; on a light one - its own theme's or the screens' - its own text colour and its quieter one)
    const bool lightFace = ldrc::themeIsLight(face);
    const uint16_t dim = own || lightFace ? soft : FL_DIM;
    const uint16_t valueInk = v.state == FS_STALE ? dim : v.state == FS_GOOD ? (lightFace ? ink : FL_GREEN) : ink;
    flClip(FlightRect(r.x + 2, r.y + 2, r.w - 4, r.h - 4));
    const int pad = FLIGHT_PAD, tf = t.textFont, labelH = fontHeight(tf), smallH = labelH;   // (room for the small line in every box: the numbers of a row line up)
    const int wpad = 10;                                          // (the words 10 px in, the number 12: "ESC temperature" whole in a 192 px box)
    if (t.dial && t.meter.kind != FD_NONE) {                      // (1.11.102/104) a round instrument filling the box, its name on its face: no name line
        const FlightRect ia(r.x + 3, r.y + 3, r.w - 6, r.h - 6);
        if (flDialFits(ia)) {
            const uint16_t needle = (v.state == FS_WARN || v.state == FS_ALARM) ? ink : v.state == FS_STALE ? dim : lightFace ? ink : FL_YELLOW;
            FlFaceWords w; w.name = v.label; w.shortName = flFaceShort(t.item); w.unit = v.unit.empty() ? flightItemUnit(t.item) : v.unit; w.note = v.small;
            flDial(ia, t.meter, w, face, ink, v.state, needle); flUnclip(); return;
        }
    }                                                             // (too small for one: the digits, as ever)
    if (!v.bars.empty()) {                                        // channel bars instead of a number: one column of eight, or two
        // (1.11.106) no name line: the bars have the whole box (Malcolm, 22 Oct: "they do not need the declaration of channels
        // 1 to 16, et cetera, because this is self-evident, and this would allow a little more space for the bars")
        const int top = r.y + 8, h = r.h - 16;
        if (v.bars.size() <= 8) flBars(FlightRect(r.x + pad, top, r.w - 2 * pad, h), v.bars, 0, FL_STRIP, FL_ACCENT, soft);
        else {
            const int colW = (r.w - 2 * pad - 14) / 2;
            flBars(FlightRect(r.x + pad, top, colW, h), v.bars, 0, FL_STRIP, FL_ACCENT, soft);
            flBars(FlightRect(r.x + pad + colW + 14, top, colW, h), v.bars, 8, FL_STRIP, FL_ACCENT, soft);
        }
        flUnclip();
        return;
    }
    flText(r.x + wpad, r.y + 8, tf, soft, flCut(v.label, tf, r.w - 2 * wpad));
    if (!v.image.empty()) {                                       // the model's picture instead of a number, as big as the box allows: the whole box but its edge (1.9.11)
        const int top = r.y + 5;
        if (!flImage(FlightRect(r.x + 5, top, r.w - 10, r.h - 10), v.image)) {   // (no such picture on the card: say which)
            flNumber(FlightRect(r.x + pad, top, r.w - 2 * pad, r.y + r.h - 10 - top - smallH - 4), "--", "", t.scale, dim, dim);
            std::string base = v.image.substr(v.image.find_last_of("/\\") == std::string::npos ? 0 : v.image.find_last_of("/\\") + 1);
            const size_t dot = base.find_last_of('.'); if (dot != std::string::npos) base = base.substr(0, dot);
            flText(r.x + wpad, r.y + r.h - smallH - 8, tf, soft, flCut(base + ": no picture", tf, r.w - 2 * wpad));
        }
        flUnclip();
        return;
    }
    if (!v.small.empty()) {
        std::string s = v.small;                                  // (a pack's "total" makes way before its percent - the number that turns amber - is cut)
        if (textWidth(tf, s) > r.w - 2 * wpad) { const size_t at = s.find(" total"); if (at != std::string::npos) s.erase(at, 6); }
        flText(r.x + wpad, r.y + r.h - smallH - 8, tf, soft, flCut(s, tf, r.w - 2 * wpad));
    }
    // the number: as big as the box allows (Malcolm, 10-04: "Box size should be linked to font size"), its unit after it
    const int top = r.y + 8 + labelH, bottom = r.y + r.h - 8 - smallH;
    flNumber(FlightRect(r.x + pad, top, r.w - 2 * pad, bottom - top), v.big, v.unit, t.scale, valueInk, v.state == FS_STALE ? FL_DIM : soft);
    flUnclip();
}

static void flightDrawButton(const ldrc::FlightButton &b) {
    if (b.label) {                                                // words on the page (a box's colour page: "Box colour", "Text colour"; the red zone page's number, big and centred)
        const int font = b.font ? b.font : 6;
        gfx->fillRect(b.r.x, b.r.y, b.r.w, b.r.h, FL_GROUND);
        flText(b.centred ? b.r.x + (b.r.w - textWidth(font, b.text)) / 2 : b.r.x, b.r.y + (b.r.h - fontHeight(font)) / 2, font, font == 1 ? 0xFFFF : FL_ON_GROUND, b.text);
        return;
    }
    uint16_t face = b.chosen ? FL_CHOSEN : b.usedBy ? shade(FL_BUTTON, -18) : FL_BUTTON;   // (a thing another box shows: a shade darker, and badged below)
    if (b.pressed) face = shade(face, -30);
    flRaised(b.r, face, b.pressed);
    if (b.swatch) {                                               // a pair to touch: its box colour, a sample of its text colour on it, the box's own marked
        const ldrc::FlightRect &r = b.r;
        gfx->fillRect(r.x, r.y, r.w, r.h, FL_GROUND);                 // (undo the button face drawn above)
        gfx->fillRoundRect(r.x, r.y, r.w, r.h, 6, b.pressed ? shade(b.face, ldrc::themeIsLight(b.face) ? -20 : 25) : b.face);
        if (b.chosen) {                                           // yellow, with black inside it: seen on a yellow pair too
            for (int k = 0; k < 3; ++k) gfx->drawRoundRect(r.x + k, r.y + k, r.w - 2 * k, r.h - 2 * k, 6, FL_YELLOW);
            gfx->drawRoundRect(r.x + 3, r.y + 3, r.w - 6, r.h - 6, 5, 0x0000);
        } else gfx->drawRoundRect(r.x, r.y, r.w, r.h, 6, FL_ON_GROUND);   // (black shows on the black page)
        if (!b.text.empty()) {
            const int font = r.h >= 60 && textWidth(0, b.text) <= r.w - 12 ? 0 : 2;
            flClip(r); flText(r.x + (r.w - textWidth(font, b.text)) / 2, r.y + (r.h - fontHeight(font)) / 2, font, b.ink, b.text); flUnclip();
        }
        if (!b.usedBoxes.empty()) {                               // the other boxes wearing this theme: their numbers in a dark pill, top right (1.9.14)
            const int tw = textWidth(4, b.usedBoxes), pw = tw + 12, ph = 20, px = r.x + r.w - pw - 4, py = r.y + 4;
            flClip(r);
            gfx->fillRoundRect(px, py, pw, ph, 10, 0x4A69);
            flText(px + 6, py + (ph - fontHeight(4)) / 2, 4, 0xFFFF, b.usedBoxes);
            flUnclip();
        }
        return;
    }
    if (b.layout >= 0) {                                          // a choice of box sizes: its boxes, drawn small, box 1 marked
        const std::vector<ldrc::FlightRect> qs = ldrc::flightLayout(b.layout, ldrc::FlightRect(b.r.x + 12, b.r.y + 10, b.r.w - 24, b.r.h - 20), 3);   // (3 px apart: the boxes' lines, small)
        for (size_t i = 0; i < qs.size(); ++i) {
            const ldrc::FlightRect &q = qs[i];
            gfx->fillRect(q.x, q.y, q.w, q.h, FL_FACE);
            if (i == 0 && qs.size() > 1) { flClip(q); flText(q.x + (q.w - textWidth(2, "1")) / 2, q.y + (q.h - fontHeight(2)) / 2, 2, FL_INK, "1"); flUnclip(); }
        }
        return;
    }
    flClip(b.r);
    const int room = b.r.w - (b.usedBy ? 32 : 16), d = b.pressed ? 1 : 0;   // (room beside the disc of a thing another box shows: a wider name wraps, as 'ESC temperature' does, so 8 px of edge stay)
    std::vector<std::string> lines;
    if (textWidth(6, b.text) <= room) lines.push_back(b.text);
    else {                                                        // two lines where the button is tall enough ("Transmitter" / "battery")
        const size_t sp = b.text.find(' ');
        if (sp != std::string::npos && b.r.h >= 2 * fontHeight(6) + 2 && textWidth(6, b.text.substr(0, sp)) <= room && textWidth(6, b.text.substr(sp + 1)) <= room) {
            lines.push_back(b.text.substr(0, sp)); lines.push_back(b.text.substr(sp + 1));
        }
    }
    // (a thing another box shows carries that box's number in a disc at the top right: the words keep clear of it)
    auto wordsX = [&](int tw) { int x = b.r.x + (b.r.w - tw) / 2; if (b.usedBy) x = max(b.r.x + 4, min(x, b.r.x + b.r.w - 24 - tw)); return x; };
    if (!lines.empty()) {
        const int fh = fontHeight(6), y0 = b.r.y + (b.r.h - fh * (int) lines.size()) / 2;
        for (size_t i = 0; i < lines.size(); ++i) flText(wordsX(textWidth(6, lines[i])) + d, y0 + (int) i * fh + d, 6, 0x0000, lines[i]);
    } else {
        const std::string s = flCut(b.text, 2, b.r.w - (b.usedBy ? 28 : 12));
        flText(wordsX(textWidth(2, s)) + d, b.r.y + (b.r.h - fontHeight(2)) / 2 + d, 2, 0x0000, s);
    }
    if (b.usedBy) {                                               // the box that already shows this thing: its number in a dark disc, top right
        const int cx = b.r.x + b.r.w - 13 + d, cy = b.r.y + 13 + d;
        gfx->fillCircle(cx, cy, 9, 0x4A69);
        const std::string n = std::to_string((int) b.usedBy);
        flText(cx - textWidth(4, n) / 2, cy - fontHeight(4) / 2, 4, 0xFFFF, n);
    }
    flUnclip();
}

// The flash this screen runs on (board.h on the device; the Mac's renderer has no chip and shows the 4 MB look).
static uint32_t flFlashBytes() {
#ifdef ARDUINO
    return flashChipBytes;
#else
    const char *e = getenv("LDRC_FLASH_MB");               // the Mac renderer: LDRC_FLASH_MB=16 shows the 16 MB look
    return e ? (uint32_t) atoi(e) << 20 : 0;
#endif
}
// The strip along the top. In flight: the model on the left, the bank in the middle, the time on the right. On the
// setup page: its title, and under the strip the line that says what to do.
static void flightDrawStrip(const ldrc::FlightScene &sc) {
    using namespace ldrc;
    if (!sc.setup) {
        const bool alert = !sc.alert.empty();                     // a warning of the front page's: the strip turns red and says it
        gfx->fillRect(0, 0, W, FLIGHT_STRIP, alert ? FL_RED : FL_STRIP);
        const int y = (FLIGHT_STRIP - fontHeight(6)) / 2, third = W / 3;
        flClip(FlightRect(0, 0, W, FLIGHT_STRIP));
        if (!sc.left.empty() && !alert) flText(12, y, 6, FL_ACCENT, flCut(sc.left, 6, third - 20));
        if (alert) {                                             // the warning alone, centred in the strip before the tabs (1.10.1), as big as fits
            const int room = sc.stripRight - 12, font = textWidth(0, sc.alert) <= room ? 0 : 6;
            flText(6 + (room - textWidth(font, sc.alert)) / 2, (FLIGHT_STRIP - fontHeight(font)) / 2, font, 0xFFFF, sc.alert);   // (white on the red, whatever the theme: a light theme's text colour did not read on it)
        }
        // (1.11.135) "16 MB" at the strip's right end on a 16 MB board: the two kinds of transmitter look the same from the
        // outside (Malcolm, 27 Oct 2026), and only this kind takes the FULL build. Nothing on a 4 MB board.
        const std::string tag = (!alert && flFlashBytes() >= 16u * 1024u * 1024u) ? "16 MB" : "";
        const int tagW = tag.empty() ? 0 : textWidth(6, tag) + 10, rightW = sc.right.empty() ? 0 : textWidth(6, sc.right) + 6;
        if (!alert && !sc.middle.empty()) {                      // the bank, centred in what is left between the name and the tabs (and the tag)
            const int room = sc.stripRight - third - 8 - tagW - rightW; const std::string m = flCut(sc.middle, 6, room);
            flText(third + (room - textWidth(6, m)) / 2 + 4, y, 6, FL_INK, m);
        }
        if (!sc.right.empty()) flText(sc.stripRight - 6 - textWidth(6, sc.right), y, 6, FL_INK, sc.right);   // (nothing since 1.10.1; the tabs and the Help button are beyond)
        if (!tag.empty()) flText(sc.stripRight - 6 - rightW - textWidth(6, tag), y, 6, FL_ON_GROUND, tag);
        flUnclip();
        return;
    }
    gfx->fillRect(0, 0, W, FLIGHT_SETUP_STRIP, FL_STRIP); gfx->drawFastHLine(0, FLIGHT_SETUP_STRIP, W, FL_LINE);
    flText(sc.tabs ? 14 : (W - textWidth(0, sc.title)) / 2, (FLIGHT_SETUP_STRIP - fontHeight(0)) / 2, 0, FL_INK, sc.title);   // (tabs at the right: the title on the left)
    gfx->fillRect(0, FLIGHT_SETUP_STRIP + 1, W, 32, FL_GROUND);
    if (!sc.hint.empty()) flText((W - textWidth(6, sc.hint)) / 2, FLIGHT_SETUP_STRIP + 4, 6, FL_ON_GROUND, sc.hint);
}

static void flightDrawAll(const ldrc::FlightScene &sc) {
    gfx->fillRect(0, 0, W, H, FL_GROUND);
    flightDrawStrip(sc);
    for (auto &t : sc.tiles) flightDrawTile(t, sc.setup);
    for (auto &b : sc.buttons) flightDrawButton(b);
}
