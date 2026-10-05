// The flight screen's drawing (lib/LdrcFlight is the thinking, src/flight_device.h the rest). Drawn with whatever gfx
// points at - our own layer on the transmitter, the picture on the Mac (hmi/render_host draws it with this file).
#pragma once
#include "LdrcFlight.h"

static const uint16_t FL_GROUND = 0x0000, FL_DIM = 0x8410, FL_YELLOW = 0xFFE0, FL_GREEN = 0x87F0, FL_AMBER = 0xFD20,
                      FL_RED = 0xD800, FL_BUTTON = 0xD69A, FL_CHOSEN = 0xFFF3;
#define FL_STRIP OUR_STRIP                                      // the pilot's colours (src/theme_device.h): navy and white unless chosen
#define FL_FACE OUR_PANEL
#define FL_EDGE (theme.edge())
#define FL_INK OUR_INK
#define FL_SOFT OUR_SOFT
#define FL_LINE OUR_INK

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
        const std::string b = flCut(big, 6, a.w - uw); const int bw = textWidth(6, b);
        const int x0 = a.x + (a.w - bw - uw) / 2, y0 = a.y + (a.h - fontHeight(6)) / 2;
        flText(x0, y0, 6, ink, b);
        if (uw) flText(x0 + bw + 6, y0 + fontHeight(6) - fontHeight(2), 2, unitInk, unit);
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
    const int numW = numbers ? 28 : 0, tx = a.x + numW, tw = a.w - numW, cx = tx + tw / 2, half = tw / 2;
    for (int i = 0; i < rows && from + i < bars.size(); ++i) {
        const int y = a.y + i * rowH + (rowH - barH) / 2;
        if (numbers) { char n[4]; snprintf(n, sizeof(n), "%d", firstChannel + i); flText(a.x, a.y + i * rowH + (rowH - fontHeight(4)) / 2, 4, ink, n); }
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
static void flightDrawTile(const ldrc::FlightTile &t, bool setup) {
    using namespace ldrc;
    const FlightRect &r = t.r; const FlightValue &v = t.v;
    gfx->fillRect(r.x, r.y, r.w, r.h, FL_GROUND);
    if (v.state == FS_EMPTY) {                                    // nothing chosen: a dim outline on the setup page, nothing in flight
        if (setup) {
            for (int k = 0; k < 2; ++k) gfx->drawRect(r.x + k, r.y + k, r.w - 2 * k, r.h - 2 * k, t.pressed ? FL_SOFT : FL_DIM);
            flClip(r);
            const std::string s = "Nothing";
            flText(r.x + (r.w - textWidth(6, s)) / 2, r.y + (r.h - fontHeight(6)) / 2, 6, FL_DIM, s);
            flUnclip();
        }
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
    if (v.state == FS_NORMAL || v.state == FS_GOOD || v.state == FS_STALE) {
        gfx->drawRoundRect(r.x, r.y, r.w, r.h, 10, setup ? FL_SOFT : edge);
    }
    // (green for "ON" and grey for "--" on a dark box; on a light one, its own text colour and its quieter blend)
    const uint16_t valueInk = v.state == FS_STALE ? (own ? soft : FL_DIM) : v.state == FS_GOOD ? (own && ldrc::themeIsLight(face) ? ink : FL_GREEN) : ink;
    flClip(FlightRect(r.x + 2, r.y + 2, r.w - 4, r.h - 4));
    const int pad = FLIGHT_PAD, tf = t.textFont, labelH = fontHeight(tf), smallH = labelH;   // (room for the small line in every box: the numbers of a row line up)
    flText(r.x + pad, r.y + 8, tf, soft, flCut(v.label, tf, r.w - 2 * pad));
    if (!v.image.empty()) {                                       // the model's picture instead of a number, as big as the box allows: the whole box but its edge (1.9.11)
        const int top = r.y + 5;
        if (!flImage(FlightRect(r.x + 5, top, r.w - 10, r.h - 10), v.image)) {   // (no such picture on the card: say which)
            flNumber(FlightRect(r.x + pad, top, r.w - 2 * pad, r.y + r.h - 10 - top - smallH - 4), "--", "", t.scale, FL_DIM, FL_DIM);
            std::string base = v.image.substr(v.image.find_last_of("/\\") == std::string::npos ? 0 : v.image.find_last_of("/\\") + 1);
            const size_t dot = base.find_last_of('.'); if (dot != std::string::npos) base = base.substr(0, dot);
            flText(r.x + pad, r.y + r.h - smallH - 8, tf, soft, flCut(base + ": no picture", tf, r.w - 2 * pad));
        }
        flUnclip();
        return;
    }
    if (!v.bars.empty()) {                                        // channel bars instead of a number: one column of eight, or two
        const int top = r.y + 8 + labelH + 6, h = r.h - (top - r.y) - 10;   // (as tall as the box: a big box, big bars)
        if (v.bars.size() <= 8) flBars(FlightRect(r.x + pad, top, r.w - 2 * pad, h), v.bars, 0, 1, FL_STRIP, FL_YELLOW, soft);
        else {
            const int colW = (r.w - 2 * pad - 14) / 2;
            flBars(FlightRect(r.x + pad, top, colW, h), v.bars, 0, 1, FL_STRIP, FL_YELLOW, soft);
            flBars(FlightRect(r.x + pad + colW + 14, top, colW, h), v.bars, 8, 9, FL_STRIP, FL_YELLOW, soft);
        }
        flUnclip();
        return;
    }
    if (!v.small.empty()) flText(r.x + pad, r.y + r.h - smallH - 8, tf, soft, flCut(v.small, tf, r.w - 2 * pad));
    // the number: as big as the box allows (Malcolm, 10-04: "Box size should be linked to font size"), its unit after it
    const int top = r.y + 8 + labelH, bottom = r.y + r.h - 8 - smallH;
    flNumber(FlightRect(r.x + pad, top, r.w - 2 * pad, bottom - top), v.big, v.unit, t.scale, valueInk, v.state == FS_STALE ? FL_DIM : soft);
    flUnclip();
}

static void flightDrawButton(const ldrc::FlightButton &b) {
    if (b.label) {                                                // words on the page (a box's colour page: "Box colour", "Text colour")
        gfx->fillRect(b.r.x, b.r.y, b.r.w, b.r.h, FL_GROUND);
        flText(b.r.x, b.r.y + (b.r.h - fontHeight(6)) / 2, 6, FL_SOFT, b.text);
        return;
    }
    uint16_t face = b.chosen ? FL_CHOSEN : FL_BUTTON;
    if (b.pressed) face = shade(face, -30);
    flRaised(b.r, face, b.pressed);
    if (b.swatch) {                                               // a pair to touch: its box colour, a sample of its text colour on it, the box's own marked
        const ldrc::FlightRect &r = b.r;
        gfx->fillRect(r.x, r.y, r.w, r.h, FL_GROUND);                 // (undo the button face drawn above)
        gfx->fillRoundRect(r.x, r.y, r.w, r.h, 6, b.pressed ? shade(b.face, ldrc::themeIsLight(b.face) ? -20 : 25) : b.face);
        if (b.chosen) {                                           // yellow, with black inside it: seen on a yellow pair too
            for (int k = 0; k < 3; ++k) gfx->drawRoundRect(r.x + k, r.y + k, r.w - 2 * k, r.h - 2 * k, 6, FL_YELLOW);
            gfx->drawRoundRect(r.x + 3, r.y + 3, r.w - 6, r.h - 6, 5, 0x0000);
        } else gfx->drawRoundRect(r.x, r.y, r.w, r.h, 6, FL_SOFT);   // (black shows on the black page)
        if (!b.text.empty()) {
            const int font = r.h >= 60 && textWidth(0, b.text) <= r.w - 12 ? 0 : 2;
            flClip(r); flText(r.x + (r.w - textWidth(font, b.text)) / 2, r.y + (r.h - fontHeight(font)) / 2, font, b.ink, b.text); flUnclip();
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
    const int room = b.r.w - 16, d = b.pressed ? 1 : 0;
    std::vector<std::string> lines;
    if (textWidth(6, b.text) <= room) lines.push_back(b.text);
    else {                                                        // two lines where the button is tall enough ("Transmitter" / "battery")
        const size_t sp = b.text.find(' ');
        if (sp != std::string::npos && b.r.h >= 2 * fontHeight(6) + 2 && textWidth(6, b.text.substr(0, sp)) <= room && textWidth(6, b.text.substr(sp + 1)) <= room) {
            lines.push_back(b.text.substr(0, sp)); lines.push_back(b.text.substr(sp + 1));
        }
    }
    if (!lines.empty()) {
        const int fh = fontHeight(6), y0 = b.r.y + (b.r.h - fh * (int) lines.size()) / 2;
        for (size_t i = 0; i < lines.size(); ++i) flText(b.r.x + (b.r.w - textWidth(6, lines[i])) / 2 + d, y0 + (int) i * fh + d, 6, 0x0000, lines[i]);
    } else {
        const std::string s = flCut(b.text, 2, b.r.w - 12);
        flText(b.r.x + (b.r.w - textWidth(2, s)) / 2 + d, b.r.y + (b.r.h - fontHeight(2)) / 2 + d, 2, 0x0000, s);
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
        if (!sc.left.empty()) flText(12, y, 6, alert ? FL_INK : FL_YELLOW, flCut(sc.left, 6, third - 20));
        if (alert) flText((W - textWidth(0, sc.alert)) / 2, (FLIGHT_STRIP - fontHeight(0)) / 2, 0, FL_INK, sc.alert);
        else if (!sc.middle.empty()) { const std::string m = flCut(sc.middle, 6, third); flText((W - textWidth(6, m)) / 2, y, 6, FL_INK, m); }
        if (!sc.right.empty()) flText(sc.stripRight - 6 - textWidth(6, sc.right), y, 6, FL_INK, sc.right);   // (the Help button beyond it)
        flUnclip();
        return;
    }
    gfx->fillRect(0, 0, W, FLIGHT_SETUP_STRIP, FL_STRIP); gfx->drawFastHLine(0, FLIGHT_SETUP_STRIP, W, FL_LINE);
    flText((W - textWidth(0, sc.title)) / 2, (FLIGHT_SETUP_STRIP - fontHeight(0)) / 2, 0, FL_INK, sc.title);
    gfx->fillRect(0, FLIGHT_SETUP_STRIP + 1, W, 32, FL_GROUND);
    if (!sc.hint.empty()) flText((W - textWidth(6, sc.hint)) / 2, FLIGHT_SETUP_STRIP + 4, 6, FL_SOFT, sc.hint);
}

static void flightDrawAll(const ldrc::FlightScene &sc) {
    gfx->fillRect(0, 0, W, H, FL_GROUND);
    flightDrawStrip(sc);
    for (auto &t : sc.tiles) flightDrawTile(t, sc.setup);
    for (auto &b : sc.buttons) flightDrawButton(b);
}
