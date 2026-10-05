// The Themes page's drawing (lib/LdrcTheme is the thinking, src/theme_device.h the rest): drawn in the theme chosen, so
// the page shows it - its strip, its panel, its writing. Edit themes: the twelve themes, a sample page, and three bars
// (colour, strength, light). Drawn with whatever gfx points at (our own layer on the transmitter, the picture on the Mac).
// Uses src/flight_draw.h's helpers.
#pragma once
#include "LdrcTheme.h"

// The yellow frame of the one chosen, black inside it: seen on a yellow or a white colour too
static void themeChosenFrame(const ldrc::ThemeRect &r, int radius) {
    for (int k = 0; k < 3; ++k) gfx->drawRoundRect(r.x + k, r.y + k, r.w - 2 * k, r.h - 2 * k, radius, FL_YELLOW);
    gfx->drawRoundRect(r.x + 3, r.y + 3, r.w - 6, r.h - 6, radius > 1 ? radius - 1 : radius, 0x0000);
}

// A bar of Edit themes: what each place along it would make, the finger's place marked
static void themeDrawSlider(const ldrc::ThemeTile &t, uint16_t ground) {
    const ldrc::ThemeRect &r = t.r; const ldrc::ThemeHsv &c = t.hsv;
    gfx->fillRect(r.x, r.y, r.w, r.h, ground);
    const int span = r.w > 1 ? r.w - 1 : 1;
    for (int x = 0; x < r.w; ++x) {
        const uint16_t col = t.slider == 1 ? ldrc::themeFromHsv(x * 359 / span, 100, 100)        // colour: the rainbow
                           : t.slider == 2 ? ldrc::themeFromHsv(c.h, x * 100 / span, c.v)        // strength: grey to vivid
                                           : ldrc::themeFromHsv(c.h, c.s, x * 100 / span);       // light: black to bright
        gfx->drawFastVLine(r.x + x, r.y + 5, r.h - 10, col);
    }
    gfx->drawRect(r.x, r.y + 5, r.w, r.h - 10, 0xC618);
    const int at = t.slider == 1 ? c.h * span / 359 : t.slider == 2 ? c.s * span / 100 : c.v * span / 100, kx = r.x + at - 4;
    gfx->fillRect(kx, r.y, 9, r.h, 0xFFFF); gfx->drawRect(kx, r.y, 9, r.h, 0x0000); gfx->drawRect(kx + 1, r.y + 1, 7, r.h - 2, 0x0000);
}

// The sample: a little page in the colour being made - its strip, some words, a model's name
static void themeDrawPreview(const ldrc::ThemeTile &t, const ldrc::Theme &th) {
    const ldrc::ThemeRect &r = t.r;
    const uint16_t strip = ldrc::themeIsLight(t.face) ? ldrc::themeBlend(t.face, 0x0000, 80) : (ldrc::themeContrast(t.face, 0x0000) < 1.3 ? ldrc::themeBlend(t.face, 0xFFFF, 84) : ldrc::themeBlend(t.face, 0x0000, 55));
    const uint16_t accent = ldrc::themeIsLight(t.face) ? t.ink : 0xFFE0;
    (void) th;
    gfx->fillRoundRect(r.x, r.y, r.w, r.h, 8, t.face);
    gfx->fillRect(r.x + 1, r.y + 1, r.w - 2, 34, strip);
    gfx->drawRoundRect(r.x, r.y, r.w, r.h, 8, 0xC618);
    flClip(ldrc::FlightRect(r.x + 2, r.y + 2, r.w - 4, r.h - 4));
    flText(r.x + (r.w - textWidth(6, "Title")) / 2, r.y + 3, 6, t.ink, "Title");
    flText(r.x + 14, r.y + 44, 6, t.ink, "Example text");             // (Malcolm, 10-04: not "Words  a hint")
    flText(r.x + 14, r.y + 82, 6, accent, "Model name");
    flUnclip();
}

static void themeDrawTile(const ldrc::ThemeTile &t, const ldrc::Theme &th) {
    const ldrc::ThemeRect &r = t.r;
    if (t.button) {                                               // as the pages' buttons
        flRaised(ldrc::FlightRect(r.x, r.y, r.w, r.h), t.pressed ? shade(t.face, -30) : t.face, t.pressed);
        const int d = t.pressed ? 1 : 0;
        flText(r.x + (r.w - textWidth(6, t.text)) / 2 + d, r.y + (r.h - fontHeight(6)) / 2 + d, 6, t.ink, t.text);
        return;
    }
    if (t.slider) { themeDrawSlider(t, th.panel()); return; }
    if (t.preview) { gfx->fillRect(r.x, r.y, r.w, r.h, th.panel()); themeDrawPreview(t, th); return; }
    gfx->fillRect(r.x, r.y, r.w, r.h, th.panel());                // (the page's own ground round the corners)
    const uint16_t face = t.pressed ? shade(t.face, ldrc::themeIsLight(t.face) ? -20 : 25) : t.face;
    gfx->fillRoundRect(r.x, r.y, r.w, r.h, 8, face);
    if (t.chosen) themeChosenFrame(r, 8);
    else gfx->drawRoundRect(r.x, r.y, r.w, r.h, 8, th.soft());    // (a black panel shows on a black page)
    flClip(ldrc::FlightRect(r.x + 4, r.y + 2, r.w - 8, r.h - 4));
    const int font = r.h >= 80 ? 1 : r.h >= 60 ? 0 : r.h >= 40 ? 6 : 2;   // (a theme's number in its text colour: the bigger the swatch, the bigger the number)
    flText(r.x + (r.w - textWidth(font, t.text)) / 2, r.y + (r.h - fontHeight(font)) / 2, font, t.ink, t.text);
    flUnclip();
}

static void themeDrawAll(const ldrc::ColoursScene &sc) {
    using namespace ldrc;
    const Theme &th = sc.theme;
    gfx->fillRect(0, 0, W, THEME_STRIP, th.strip());
    gfx->fillRect(0, THEME_STRIP, W, H - THEME_STRIP, th.panel());
    flText((W - textWidth(0, sc.title)) / 2, (THEME_STRIP - fontHeight(0)) / 2, 0, th.ink(), sc.title);
    if (sc.editing) {
        if (!sc.hint.empty()) flText((W - textWidth(6, sc.hint)) / 2, THEME_STRIP + 2, 6, th.ink(), sc.hint);
        static const char *names[3] = { "Colour", "Strength", "Light" };   // the bars' names, to their right
        for (auto &t : sc.tiles) if (t.slider) flText(t.r.x + t.r.w + 10, t.r.y + (t.r.h - fontHeight(2)) / 2, 2, th.ink(), names[t.slider - 1]);
    }
    for (auto &t : sc.tiles) themeDrawTile(t, th);
}

// The Appearance page: in the screens' colours, its three buttons in the middle, Back below
static void appearanceDrawAll(const ldrc::AppearanceScene &sc, const ldrc::Theme &th) {
    using namespace ldrc;
    gfx->fillRect(0, 0, W, THEME_STRIP, th.strip());
    gfx->fillRect(0, THEME_STRIP, W, H - THEME_STRIP, th.panel());
    flText((W - textWidth(0, sc.title)) / 2, (THEME_STRIP - fontHeight(0)) / 2, 0, th.ink(), sc.title);
    for (auto &t : sc.tiles) themeDrawTile(t, th);
}
