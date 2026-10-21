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
// those who like things to look traditional") A gauge: a rim three quarters of the way round, numbered ticks, a needle from
// the pivot, the number small below the pivot. A clock: a full face with hour and minute hands; a timer: a minute hand and
// a seconds hand. Lines, circles and triangles only: the Mac renders it with the same code (hmi/render_host).
static const int FL_DIAL_MIN_R = 46;                              // (smaller than this a dial cannot be read: the box keeps its digits)
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
static int flDialLabelFont(int R) { return R >= 110 ? 2 : 4; }   // the scale's numbers: 24 px on a big dial, else 16 (a small gauge numbers only its two ends)
static void flDialLabel(int cx, int cy, float r, float a, int font, uint16_t col, const std::string &s) {   // a scale's number, its middle this far out on the radius
    int x, y; flPolar(cx, cy, r, a, x, y);
    flText(x - textWidth(font, s) / 2, y - fontHeight(font) / 2, font, col, s);
}
// The number under the pivot: the big letters where they fit at 24 px or more, else the plain 24- or 16-pixel ones (the unit
// dropped if it must be: the box's name says what the number is)
static void flDialNumber(int cx, int yTop, int yBot, int maxW, const std::string &big, const std::string &unit, uint16_t ink, uint16_t soft) {
    const int h = yBot - yTop; if (h < 12 || maxW < 20) return;
    const int natural = textWidth(1, big) + (unit.empty() ? 0 : 8 + textWidth(0, unit));
    const int s16 = min(h * 16 / 64, natural > 0 ? maxW * 16 / natural : 48);
    if (s16 >= 8) { flNumber(ldrc::FlightRect(cx - maxW / 2, yTop, maxW, h), big, unit, s16, ink, soft); return; }
    for (int font = 2; font <= 4; font += 2) {
        const int bw = textWidth(font, big); if (bw > maxW || fontHeight(font) > h + 4) continue;   // (a 16 px line may hang 4 px over: the letters' own space)
        const int uw = unit.empty() ? 0 : textWidth(font, unit) + 6; const bool withUnit = uw && bw + uw <= maxW;
        const int tw = bw + (withUnit ? uw : 0), x0 = cx - tw / 2, y0 = yTop + (h - fontHeight(font)) / 2;
        flText(x0, y0, font, ink, big); if (withUnit) flText(x0 + bw + 6, y0, font, soft, unit);
        return;
    }
}
// A gauge: the scale round the top two thirds, its numbers inside the ticks, the needle, and the number below the scale's
// ends at the bottom of the face (a real instrument's readout window)
static bool flGauge(const ldrc::FlightRect &a, const ldrc::FlightDial &d, const std::string &big, const std::string &unit,
                    uint16_t ink, uint16_t soft, uint16_t needle, uint16_t valueInk, uint16_t face) {
    const int R = min((a.w - 4) / 2, (a.h - 4) / 2);
    if (R < FL_DIAL_MIN_R) return false;
    const int cx = a.x + a.w / 2, cy = a.y + a.h / 2;
    const float a0 = flDialAngle(d, d.lo), a1 = flDialAngle(d, d.hi);
    flArc(cx, cy, R, a0, a1, 3, soft);                                 // the rim
    const int majors = max(1, (int) lroundf((d.hi - d.lo) / d.major)), labelFont = flDialLabelFont(R);
    const int lh = labelFont >= 0 ? fontHeight(labelFont) : 0; const float labelR = R - (labelFont == 4 ? 20 : 18) - lh / 2.0f;   // (the 16 px numbers a little further in: clear of the ticks on a small dial)
    const bool endsOnly = R < 58;                                     // (a small gauge: its two ends numbered, nothing else - the numbers would touch)
    bool everyOther = false;                                          // (numbers wider than their room: every other one)
    if (labelFont >= 0) {
        char b[16]; snprintf(b, sizeof(b), d.decimals ? "%.1f" : "%.0f", (double) d.hi);
        everyOther = textWidth(labelFont, b) > (a1 - a0) * labelR / majors * 0.85f;
    }
    for (int m = 0; m <= majors; ++m) {                               // the ticks: numbered every major, five between
        const float v = d.lo + m * d.major, am = flDialAngle(d, v);
        flTick(cx, cy, am, R - 4, R - 15, 2, ink);
        if (m < majors) for (int k = 1; k < 5; ++k) flTick(cx, cy, flDialAngle(d, v + d.major * k / 5), R - 4, R - 10, 1, soft);
        if (labelFont >= 0 && (endsOnly ? (m == 0 || m == majors) : (!everyOther || (majors - m) % 2 == 0))) { char b[16]; snprintf(b, sizeof(b), d.decimals ? "%.1f" : "%.0f", (double) v); flDialLabel(cx, cy, labelR, am, labelFont, ink, b); }   // (every other one: the top of the scale always numbered)
    }
    flHand(cx, cy, flDialAngle(d, d.value), R - 20, R / 6, max(4, R / 12), needle);   // the needle, its pivot
    gfx->fillCircle(cx, cy, max(4, R / 10), ink); gfx->fillCircle(cx, cy, max(1, R / 24), face);
    // the number: below the scale's ends (their numbers, or their ticks), as wide as the face is there
    const float endsY = labelFont >= 0 ? labelR * 0.5f + lh / 2.0f : (R - 15) * 0.5f;   // (cos 120 = -1/2)
    const int yTop = cy + (int) endsY + 4, yBot = cy + R - 2;
    const int chord = 2 * (int) sqrtf((float) R * R - endsY * endsY) - 8;
    flDialNumber(cx, yTop, yBot, chord, big, unit, valueInk, soft);
    return true;
}
// A clock's face (a timer's: seconds round it). The number sits where the six would be: a timer's hands are hard to read to the
// second, and the words say it exactly
static bool flClockFace(const ldrc::FlightRect &a, const ldrc::FlightDial &d, bool timer, const std::string &big,
                        uint16_t ink, uint16_t soft, uint16_t needle, uint16_t valueInk, uint16_t face) {
    const int R = min((a.w - 4) / 2, (a.h - 4) / 2);
    if (R < FL_DIAL_MIN_R) return false;
    const int cx = a.x + a.w / 2, cy = a.y + a.h / 2;
    for (int k = 0; k < 3; ++k) gfx->drawCircle(cx, cy, R - k, soft);   // the rim
    const int labelFont = flDialLabelFont(R), lh = labelFont >= 0 ? fontHeight(labelFont) : 0; const float labelR = R - 18 - lh / 2.0f;
    for (int m = 0; m < 12; ++m) {                                    // the hours (a timer: every five seconds), the minutes between where there is room
        const float am = m * FL_PI / 6;
        flTick(cx, cy, am, R - 4, R - 14, 2, ink);
        if (R >= 56) for (int k = 1; k < 5; ++k) flTick(cx, cy, am + k * FL_PI / 30, R - 4, R - 9, 1, soft);
        if (labelFont >= 0 && m % 3 == 0 && m != 6) flDialLabel(cx, cy, labelR, am, labelFont, ink, std::to_string(timer ? (m == 0 ? 60 : m * 5) : (m == 0 ? 12 : m)));   // 12 3 9; a timer 60 15 45
    }
    if (timer) {                                                      // a minute hand, and the seconds hand sweeping
        const float secs = fmodf(d.value, 60.0f), mins = fmodf(d.value / 60.0f, 60.0f);
        flHand(cx, cy, mins / 60.0f * 2 * FL_PI, R * 0.55f, R / 7.0f, max(4, R / 12), ink);
        flHand(cx, cy, secs / 60.0f * 2 * FL_PI, R - 18.0f, R / 5.0f, max(2, R / 30), needle);
    } else {
        const float mins = fmodf(d.value, 60.0f), hours = fmodf(d.value / 60.0f, 12.0f);
        flHand(cx, cy, hours / 12.0f * 2 * FL_PI, R * 0.52f, R / 7.0f, max(5, R / 11), ink);
        flHand(cx, cy, mins / 60.0f * 2 * FL_PI, R - 20.0f, R / 6.0f, max(3, R / 16), ink);
    }
    gfx->fillCircle(cx, cy, max(4, R / 11), ink); gfx->fillCircle(cx, cy, max(1, R / 26), face);
    const int yTop = cy + R / 4 + 2, yBot = cy + R - 16;              // between the pivot and the ticks at the bottom
    flDialNumber(cx, yTop, yBot, 2 * (int) sqrtf((float) R * R - (float) (yBot - cy) * (yBot - cy)) + R / 3, big, "", valueInk, soft);
    return true;
}
// A box's dial in the area its number would have had. false: the area is too small for one (the digits go there instead)
static bool flDial(const ldrc::FlightRect &a, const ldrc::FlightDial &d, const std::string &big, const std::string &unit,
                   uint16_t ink, uint16_t soft, uint16_t needle, uint16_t valueInk, uint16_t face) {
    if (d.kind == ldrc::FD_GAUGE) return flGauge(a, d, big, unit, ink, soft, needle, valueInk, face);
    if (d.kind == ldrc::FD_CLOCK || d.kind == ldrc::FD_TIMER) return flClockFace(a, d, d.kind == ldrc::FD_TIMER, big, ink, soft, needle, valueInk, face);
    return false;
}

static void flRaised(const ldrc::FlightRect &r, uint16_t face, bool down) {             // the buttons' face and their 3D edge
    const uint16_t hi = shade(face, 60), lo = shade(face, -45);
    gfx->fillRect(r.x, r.y, r.w, r.h, face);
    for (int k = 0; k < 2; ++k) {
        gfx->drawFastHLine(r.x + k, r.y + k, r.w - 2 * k, down ? lo : hi); gfx->drawFastVLine(r.x + k, r.y + k, r.h - 2 * k, down ? lo : hi);
        gfx->drawFastHLine(r.x + k, r.y + r.h - 1 - k, r.w - 2 * k, down ? hi : lo); gfx->drawFastVLine(r.x + r.w - 1 - k, r.y + k, r.h - 2 * k, down ? hi : lo);
    }
}

// Channel bars, eight to a column: each grows from the centre line, the normal travel (1000 to 2000 us: 25 to 75 of the
// front page's 0 to 100) reaching the side; the channel's number beside it where the rows are tall enough.
static void flBars(const ldrc::FlightRect &a, const std::vector<uint8_t> &bars, size_t from, int firstChannel, uint16_t track, uint16_t fill, uint16_t ink) {
    const int rows = 8, rowH = a.h / rows, barH = max(3, rowH - (rowH >= 12 ? 5 : 2));
    const bool numbers = rowH >= 18;
    const int numFont = rowH >= 30 ? 2 : 4;                       // (in a big box the numbers in the 24 px letters of every other word, not the 16 px ones)
    const int numW = numbers ? (numFont == 2 ? 34 : 28) : 0, tx = a.x + numW, tw = a.w - numW, cx = tx + tw / 2, half = tw / 2;
    for (int i = 0; i < rows && from + i < bars.size(); ++i) {
        const int y = a.y + i * rowH + (rowH - barH) / 2;
        if (numbers) { char n[4]; snprintf(n, sizeof(n), "%d", firstChannel + i); flText(a.x, a.y + i * rowH + (rowH - fontHeight(numFont)) / 2, numFont, ink, n); }
        gfx->fillRect(tx, y, tw, barH, track);
        float d = ((int) bars[from + i] - 50) / 25.0f; if (d > 1) d = 1; if (d < -1) d = -1;
        const int len = (int) (d * half);
        if (len > 0) gfx->fillRect(cx, y, len, barH, fill); else if (len < 0) gfx->fillRect(cx + len, y, -len, barH, fill);
    }
    gfx->drawFastVLine(cx, a.y, rows * rowH, ink);             // the centre line
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
    File f = SD.open(path.c_str());
    if (!f) { flPicFail(path, "no such file"); return false; }
    uint16_t wh[2] = { 0, 0 };
    if (f.read((uint8_t *) wh, 4) != 4 || !wh[0] || !wh[1] || wh[0] > 800 || wh[1] > 480) { f.close(); flPicFail(path, "header"); return false; }
    const size_t bytes = (size_t) wh[0] * wh[1] * 2;
    uint16_t *px = (uint16_t *) ps_malloc(bytes);
    if (!px) { f.close(); flPicFail(path, "no memory"); return false; }
    const size_t got = f.read((uint8_t *) px, bytes);
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
// line between its two items. A part that needs a look turns its own half amber or red (square at the line, round at the
// box's corners), and the box's frame white, as any box's. ldrc::flightPartPlan says where each part's name, number and
// small line go - the sizing (flightSizeTiles) used the same sums.
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
    const uint16_t edge = own ? ldrc::themeBlend(ink, face, 30) : FL_EDGE;
    FlightRect up, low; flightSplit(r, up, low);
    const int mid = up.y + up.h + (low.y - up.y - up.h) / 2;     // the line between the two items: the middle of the gap
    gfx->fillRoundRect(r.x, r.y, r.w, r.h, 10, flPartFace(t, FS_NORMAL, face));
    const FlightState st[2] = { v.state, v.state2 };
    bool look = false;
    for (int k = 0; k < 2; ++k) {
        if (st[k] != FS_WARN && st[k] != FS_ALARM) continue;
        look = true;
        const uint16_t c = flPartFace(t, st[k], face);
        if (k == 0) { gfx->fillRoundRect(r.x, r.y, r.w, mid - r.y, 10, c); gfx->fillRect(r.x, mid - 10, r.w, 10, c); }
        else { gfx->fillRoundRect(r.x, mid, r.w, r.y + r.h - mid, 10, c); gfx->fillRect(r.x, mid, r.w, 10, c); }
    }
    if (look)                                                     // (as a box: a thick white frame with the colour)
        for (int k = 0; k < 4; ++k) gfx->drawRoundRect(r.x + k, r.y + k, r.w - 2 * k, r.h - 2 * k, 10 - k, 0xFFFF);
    else {
        gfx->drawRoundRect(r.x, r.y, r.w, r.h, 10, setup ? FL_SOFT : edge);
        gfx->drawFastHLine(r.x + 10, mid, r.w - 20, setup ? FL_SOFT : edge);   // (a colour change is the line when a half needs a look)
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
        const uint16_t needle = (state == FS_WARN || state == FS_ALARM) ? ink : lightFace ? ink : FL_YELLOW;
        dialed = flDial(da, md, big, unit, ink, soft, needle, valueInk, face);
    }
    if (!dialed) {
        if (!pl.row && pl.small && !small.empty()) flText(p.x + wpad, p.y + p.h - nameH - 8, pl.font, soft, flCut(small, pl.font, p.w - 2 * wpad));
        flNumber(pl.number, big, unit, scale, valueInk, state == FS_STALE ? FL_DIM : soft);
    }
    flUnclip();
}

// (1.11.102) A box of two parts as two dials side by side (the batteries: RX on the left, TX on the right; stacked, neither
// half would have the height for a dial). Each half: its name and tag above, its dial below; a half with no number says so
// in words. false: no room for dials this way either (the stacked box with its digits is drawn instead)
static bool flTwoDialBox(const ldrc::FlightTile &t, bool setup) {
    using namespace ldrc;
    const FlightRect &r = t.r; const FlightValue &v = t.v;
    const int tf = t.textFont, nameH = fontHeight(tf), wpad = 10, halfW = r.w / 2;
    const FlightRect halves[2] = { FlightRect(r.x, r.y, halfW, r.h), FlightRect(r.x + halfW, r.y, r.w - halfW, r.h) };
    struct Plan { std::string name, tag; bool twoLines = false; FlightRect dial; } pl[2];
    for (int k = 0; k < 2; ++k) {                                     // the name line: the name with its tag at the right, or the short name with it, or two lines
        const FlightRect &h = halves[k];
        const std::string full = k ? v.label2 : v.label, shortName = flightPartShort(t.item, k), tag = k ? v.tag2 : v.tag;
        const int room = h.w - 2 * wpad, tw = tag.empty() ? 0 : textWidth(tf, tag);
        Plan &p = pl[k]; p.tag = tag;
        if (textWidth(tf, full) + (tw ? tw + 12 : 0) <= room) p.name = full;
        else if (textWidth(tf, shortName) + (tw ? tw + 12 : 0) <= room) p.name = shortName;
        else { p.name = flCut(full, tf, room); p.twoLines = !tag.empty(); }
        const int top = h.y + 8 + nameH * (p.twoLines ? 2 : 1) + 4;
        p.dial = FlightRect(h.x + 6, top, h.w - 12, h.y + h.h - 8 - top);
        if (min((p.dial.w - 4) / 2, (p.dial.h - 4) / 2) < FL_DIAL_MIN_R) return false;
    }
    const bool own = t.own;                                           // the face: as the stacked box's, the line between the halves upright
    const uint16_t face = own ? t.face : FL_FACE, ink = own ? t.ink : FL_INK;
    const uint16_t edge = own ? ldrc::themeBlend(ink, face, 30) : FL_EDGE;
    const int mid = r.x + halfW;
    gfx->fillRoundRect(r.x, r.y, r.w, r.h, 10, flPartFace(t, FS_NORMAL, face));
    const FlightState st[2] = { v.state, v.state2 };
    bool look = false;
    for (int k = 0; k < 2; ++k) {
        if (st[k] != FS_WARN && st[k] != FS_ALARM) continue;
        look = true;
        const uint16_t c = flPartFace(t, st[k], face);
        if (k == 0) { gfx->fillRoundRect(r.x, r.y, mid - r.x, r.h, 10, c); gfx->fillRect(mid - 10, r.y, 10, r.h, c); }
        else { gfx->fillRoundRect(mid, r.y, r.x + r.w - mid, r.h, 10, c); gfx->fillRect(mid, r.y, 10, r.h, c); }
    }
    if (look) for (int k = 0; k < 4; ++k) gfx->drawRoundRect(r.x + k, r.y + k, r.w - 2 * k, r.h - 2 * k, 10 - k, 0xFFFF);
    else { gfx->drawRoundRect(r.x, r.y, r.w, r.h, 10, setup ? FL_SOFT : edge); gfx->drawFastVLine(mid, r.y + 10, r.h - 20, setup ? FL_SOFT : edge); }
    for (int k = 0; k < 2; ++k) {                                     // each half: its words and its dial
        const FlightRect &h = halves[k]; const FlightState state = st[k];
        const uint16_t pface = flPartFace(t, state, face);
        uint16_t pink = ink, soft = own ? ldrc::themeBlend(t.ink, t.face, 72) : FL_SOFT;
        if (state == FS_WARN) { pink = 0x0000; soft = 0x0000; } else if (state == FS_ALARM) { pink = 0xFFFF; soft = 0xFFFF; }
        const bool lightFace = ldrc::themeIsLight(pface);
        const uint16_t dim = own || lightFace ? soft : FL_DIM;
        const uint16_t valueInk = state == FS_STALE ? dim : state == FS_GOOD ? (lightFace ? pink : FL_GREEN) : pink;
        const uint16_t needle = (state == FS_WARN || state == FS_ALARM) ? pink : lightFace ? pink : FL_YELLOW;
        const uint16_t fillInk = (state == FS_WARN || state == FS_ALARM) ? pink : (lightFace ? pink : FL_GREEN);
        flClip(FlightRect(h.x + 2, h.y + 2, h.w - 4, h.h - 4));
        const Plan &p = pl[k];
        const int tw = p.tag.empty() ? 0 : textWidth(tf, p.tag), nw = textWidth(tf, p.name);
        flText(h.x + wpad, h.y + 8, tf, soft, p.name);
        if (tw) flText(p.twoLines ? h.x + wpad : h.x + h.w - wpad - tw, h.y + 8 + (p.twoLines ? nameH : 0), tf, soft, p.tag);
        flBatteryBeside(t, k, h.x + wpad + nw + 8, h.y + 8, nameH, h.w - 2 * wpad - nw - 8 - (tw && !p.twoLines ? tw + 12 : 0), soft, fillInk);
        const FlightDial &md = k ? t.meter2 : t.meter;
        if (md.kind != FD_NONE) flDial(p.dial, md, k ? v.big2 : v.big, k ? v.unit2 : v.unit, pink, soft, needle, valueInk, pface);
        else flDialNumber(p.dial.x + p.dial.w / 2, p.dial.y, p.dial.y + p.dial.h, p.dial.w, k ? v.big2 : v.big, "", dim, dim);   // ("--": nothing to point at)
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
    const uint16_t edge = own ? ldrc::themeBlend(t.ink, t.face, 30) : FL_EDGE;
    if (v.state == FS_WARN) { face = FL_AMBER; ink = 0x0000; soft = 0x0000; }
    else if (v.state == FS_ALARM) { face = FL_RED; ink = 0xFFFF; soft = 0xFFFF; }
    if (t.pressed) face = shade(face, ldrc::themeIsLight(face) ? -20 : -30);
    gfx->fillRoundRect(r.x, r.y, r.w, r.h, 10, face);
    if (v.state == FS_WARN || v.state == FS_ALARM)               // a thick white frame as well as the colour: a red or yellow theme's boxes are almost amber and red themselves
        for (int k = 0; k < 4; ++k) gfx->drawRoundRect(r.x + k, r.y + k, r.w - 2 * k, r.h - 2 * k, 10 - k, 0xFFFF);
    if (v.state == FS_NORMAL || v.state == FS_GOOD || v.state == FS_STALE) {
        gfx->drawRoundRect(r.x, r.y, r.w, r.h, 10, setup ? FL_SOFT : edge);
    }
    // (green for "ON" and grey for "--" on a dark box; on a light one - its own theme's or the screens' - its own text colour and its quieter one)
    const bool lightFace = ldrc::themeIsLight(face);
    const uint16_t dim = own || lightFace ? soft : FL_DIM;
    const uint16_t valueInk = v.state == FS_STALE ? dim : v.state == FS_GOOD ? (lightFace ? ink : FL_GREEN) : ink;
    flClip(FlightRect(r.x + 2, r.y + 2, r.w - 4, r.h - 4));
    const int pad = FLIGHT_PAD, tf = t.textFont, labelH = fontHeight(tf), smallH = labelH;   // (room for the small line in every box: the numbers of a row line up)
    const int wpad = 10;                                          // (the words 10 px in, the number 12: "ESC temperature" whole in a 192 px box)
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
    if (!v.bars.empty()) {                                        // channel bars instead of a number: one column of eight, or two
        const int top = r.y + 8 + labelH + 6, h = r.h - (top - r.y) - 10;   // (as tall as the box: a big box, big bars)
        if (v.bars.size() <= 8) flBars(FlightRect(r.x + pad, top, r.w - 2 * pad, h), v.bars, 0, 1, FL_STRIP, FL_ACCENT, soft);
        else {
            const int colW = (r.w - 2 * pad - 14) / 2;
            flBars(FlightRect(r.x + pad, top, colW, h), v.bars, 0, 1, FL_STRIP, FL_ACCENT, soft);
            flBars(FlightRect(r.x + pad + colW + 14, top, colW, h), v.bars, 8, 9, FL_STRIP, FL_ACCENT, soft);
        }
        flUnclip();
        return;
    }
    if (t.dial && t.meter.kind != FD_NONE) {                      // (1.11.102) a round dial in the number's place, and the small line's (its room goes to the dial)
        const int top = r.y + 8 + labelH;
        const uint16_t needle = (v.state == FS_WARN || v.state == FS_ALARM) ? ink : lightFace ? ink : FL_YELLOW;
        if (flDial(FlightRect(r.x + pad, top, r.w - 2 * pad, r.y + r.h - 8 - top), t.meter, v.big, v.unit, ink, soft, needle, valueInk, face)) { flUnclip(); return; }
    }                                                             // (too small for a dial: the digits, as ever)
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
    if (b.label) {                                                // words on the page (a box's colour page: "Box colour", "Text colour")
        gfx->fillRect(b.r.x, b.r.y, b.r.w, b.r.h, FL_GROUND);
        flText(b.r.x, b.r.y + (b.r.h - fontHeight(6)) / 2, 6, FL_ON_GROUND, b.text);
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
        const std::vector<ldrc::FlightRect> qs = ldrc::flightLayout(b.layout, ldrc::FlightRect(b.r.x + 12, b.r.y + 10, b.r.w - 24, b.r.h - 20), 4);
        for (size_t i = 0; i < qs.size(); ++i) {
            const ldrc::FlightRect &q = qs[i];
            gfx->fillRoundRect(q.x, q.y, q.w, q.h, 4, FL_FACE);
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
        else if (!sc.middle.empty()) {                           // the bank, centred in what is left between the name and the tabs
            const int room = sc.stripRight - third - 8; const std::string m = flCut(sc.middle, 6, room);
            flText(third + (room - textWidth(6, m)) / 2 + 4, y, 6, FL_INK, m);
        }
        if (!sc.right.empty()) flText(sc.stripRight - 6 - textWidth(6, sc.right), y, 6, FL_INK, sc.right);   // (nothing since 1.10.1; the tabs and the Help button are beyond)
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
