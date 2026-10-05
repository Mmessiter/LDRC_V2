// The screen's colours: see LdrcTheme.h.
#include "LdrcTheme.h"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace ldrc {

// Eight dark themes with white text, then four bright ones (Malcolm, 10-04: "some brighter options - eg red with white
// text; white with burgundy text"). Navy and white first: the colours of the pages as they were made.
const ThemePair THEME_PAIRS[THEME_COUNT] = {
    { "Navy", "navy", 0x114A, 0x08A6, 0x31F2, 0xFFFF, 0xC618 },     { "Royal", "royal", 0x19D2, 0x08E9, 0x3B38, 0xFFFF, 0xC618 },
    { "Teal", "teal", 0x028B, 0x0146, 0x2C72, 0xFFFF, 0xC618 },     { "Forest", "forest", 0x1A65, 0x0942, 0x3C09, 0xFFFF, 0xC618 },
    { "Wine", "wine", 0x68A5, 0x3842, 0xA9EA, 0xFFFF, 0xC618 },     { "Plum", "plum", 0x50EC, 0x2866, 0x8232, 0xFFFF, 0xC618 },
    { "Grey", "grey", 0x31A7, 0x18C3, 0x632D, 0xFFFF, 0xC618 },     { "Black", "black", 0x0000, 0x2945, 0x4A4A, 0xFFFF, 0xC618 },   // (black: a strip lighter than the panel)
    { "Red", "red", 0xD0A2, 0x7841, 0xEBCF, 0xFFFF, 0xC618 },       { "White", "white", 0xFFFF, 0xCE7A, 0x94B3, 0x8004, 0x9A8C },
    { "Yellow", "yellow", 0xF680, 0xBCA0, 0x8320, 0x0000, 0x52AB }, { "Sky", "sky", 0x863E, 0x6D5B, 0x3B73, 0x114A, 0x32AF } };   // (sky: a quieter navy that still reads, 4.2)
// What screens 1.7.6 to 1.8.3 offered as text colours of their own ("t2 P I ..."): read as the screens' theme's text colour
static const uint16_t OLD_T2_INKS[6] = { 0xFFFF, 0xFFBA, 0xFFD2, 0x0000, 0x8004, 0x114A };

// What screens 1.7.0 to 1.7.5 called their colours ("t1 plum white"): read as the nearest colour on offer now
static const struct { const char *key; uint16_t colour; } OLD_PANELS[] = {
    { "navy", 0x114A }, { "royal", 0x19D2 }, { "slate", 0x3A4C }, { "teal", 0x028B }, { "forest", 0x1A65 }, { "olive", 0x4A42 },
    { "brown", 0x59C3 }, { "wine", 0x68A5 }, { "plum", 0x50EC }, { "grey", 0x31A7 }, { "midnight", 0x0865 }, { "black", 0x0000 } };
static const struct { const char *key; uint16_t colour; } OLD_INKS[] = {
    { "white", 0xFFFF }, { "cream", 0xFFBA }, { "lemon", 0xFFD2 }, { "mint", 0xBFF9 }, { "sky", 0xBF1F }, { "silver", 0xCE7A } };

// ------------------------------------------------------------------ colour maths
static void rgbOf(uint16_t c, int &r, int &g, int &b) { r = ((c >> 11) & 31) * 255 / 31; g = ((c >> 5) & 63) * 255 / 63; b = (c & 31) * 255 / 31; }
static uint16_t to565(int r, int g, int b) { return (uint16_t) ((((r * 31 + 127) / 255) << 11) | (((g * 63 + 127) / 255) << 5) | ((b * 31 + 127) / 255)); }
ThemeHsv themeToHsv(uint16_t c) {
    int r, g, b; rgbOf(c, r, g, b);
    const int mx = r > g ? (r > b ? r : b) : (g > b ? g : b), mn = r < g ? (r < b ? r : b) : (g < b ? g : b), d = mx - mn;
    ThemeHsv o; o.v = (int8_t) ((mx * 100 + 127) / 255); o.s = (int8_t) (mx ? (d * 100 + mx / 2) / mx : 0);
    int h = 0;
    if (d) { if (mx == r) h = 60 * (g - b) / d; else if (mx == g) h = 120 + 60 * (b - r) / d; else h = 240 + 60 * (r - g) / d; if (h < 0) h += 360; }
    o.h = (int16_t) (h % 360); return o;
}
uint16_t themeFromHsv(int h, int s, int v) {
    h = ((h % 360) + 360) % 360; s = s < 0 ? 0 : s > 100 ? 100 : s; v = v < 0 ? 0 : v > 100 ? 100 : v;
    const int V = v * 255 / 100, C = V * s / 100, hh = h % 120, X = C * (60 - (hh > 60 ? hh - 60 : 60 - hh)) / 60, m = V - C;
    int r = 0, g = 0, b = 0;
    switch (h / 60) { case 0: r = C; g = X; break; case 1: r = X; g = C; break; case 2: g = C; b = X; break; case 3: g = X; b = C; break; case 4: r = X; b = C; break; default: r = C; b = X; break; }
    return to565(r + m, g + m, b + m);
}
uint16_t themeBlend(uint16_t a, uint16_t b, int pctA) {
    int ar, ag, ab, br, bg, bb; rgbOf(a, ar, ag, ab); rgbOf(b, br, bg, bb);
    return to565((ar * pctA + br * (100 - pctA)) / 100, (ag * pctA + bg * (100 - pctA)) / 100, (ab * pctA + bb * (100 - pctA)) / 100);
}
static int lum255(uint16_t c) { int r, g, b; rgbOf(c, r, g, b); return (r * 30 + g * 59 + b * 11) / 100; }
bool themeIsLight(uint16_t c) { return lum255(c) > 140; }
static double linear(double v) { v /= 255; return v <= 0.03928 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4); }
static double relLum(uint16_t c) { int r, g, b; rgbOf(c, r, g, b); return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b); }
double themeContrast(uint16_t a, uint16_t b) { const double x = relLum(a) + 0.05, y = relLum(b) + 0.05; return x > y ? x / y : y / x; }
uint16_t themeReadable(uint16_t ink, uint16_t face) {
    if (themeContrast(ink, face) >= 3.0) return ink;
    return themeContrast(0x0000, face) >= themeContrast(0xFFFF, face) ? 0x0000 : 0xFFFF;
}
static int nearest(const uint16_t *list, int n, uint16_t c) {
    int best = 0; long bestD = -1, cr, cg, cb;
    { int r, g, b; rgbOf(c, r, g, b); cr = r; cg = g; cb = b; }
    for (int i = 0; i < n; ++i) { int r, g, b; rgbOf(list[i], r, g, b); const long d = (r - cr) * (r - cr) + (g - cg) * (g - cg) + (b - cb) * (b - cb); if (bestD < 0 || d < bestD) { bestD = d; best = i; } }
    return best;
}

// ------------------------------------------------------------------ the pilot's themes
Theme::Theme() { defaults(); }
void Theme::defaults() {
    for (int i = 0; i < THEME_COUNT; ++i) { panels[i] = THEME_PAIRS[i].panel; inks[i] = THEME_PAIRS[i].ink; }
}
bool Theme::changed(int kind, int t) const {
    if (t < 0 || t >= THEME_COUNT) return false;
    return kind == 0 ? panels[t] != THEME_PAIRS[t].panel : inks[t] != THEME_PAIRS[t].ink;
}
bool Theme::custom() const {
    for (int i = 0; i < THEME_COUNT; ++i) if (changed(0, i) || changed(1, i)) return true;
    return false;
}
uint16_t Theme::stripOf(int t) const {
    if (t < 0 || t >= THEME_COUNT) t = 0;
    if (!changed(0, t)) return THEME_PAIRS[t].strip;
    const uint16_t c = panels[t]; const int l = lum255(c);
    if (l < 24) return themeBlend(c, 0xFFFF, 84);       // very dark: a strip a little lighter
    return themeBlend(c, 0x0000, l > 140 ? 80 : 55);     // else darker (a light panel: a little)
}
uint16_t Theme::edgeOf(int t) const {
    if (t < 0 || t >= THEME_COUNT) t = 0;
    if (!changed(0, t)) return THEME_PAIRS[t].edge;
    const uint16_t c = panels[t];
    return themeBlend(c, themeIsLight(c) ? 0x0000 : 0xFFFF, 70);
}
uint16_t Theme::softOf(int t) const {
    if (t < 0 || t >= THEME_COUNT) t = 0;
    if (!changed(0, t) && !changed(1, t)) return THEME_PAIRS[t].soft;
    return themeBlend(inks[t], panels[t], 72);
}
std::string Theme::save() const {
    char b[64]; snprintf(b, sizeof(b), "t3 %u", (unsigned) no);
    std::string s = b;
    if (custom()) {
        s += " p:"; for (int i = 0; i < THEME_COUNT; ++i) { snprintf(b, sizeof(b), "%s%04X", i ? "," : "", panels[i]); s += b; }
        s += " i:"; for (int i = 0; i < THEME_COUNT; ++i) { snprintf(b, sizeof(b), "%s%04X", i ? "," : "", inks[i]); s += b; }
    }
    return s;
}
static void readColours(const std::string &s, const char *tag, uint16_t *out, int n) {   // "p:114A,19D2,...": a colour that does not read stays as it was
    const size_t at = s.find(tag); if (at == std::string::npos) return;
    size_t a = at + strlen(tag); int k = 0;
    while (k < n && a < s.size()) {
        size_t e = s.find_first_of(", ", a); if (e == std::string::npos) e = s.size();
        const std::string one = s.substr(a, e - a); unsigned v = 0; char tail = 0;
        if (one.size() == 4 && sscanf(one.c_str(), "%4x%c", &v, &tail) == 1) out[k] = (uint16_t) v;
        ++k; if (e >= s.size() || s[e] == ' ') break; a = e + 1;
    }
}
bool Theme::load(const std::string &s) {
    Theme t;
    unsigned p = 99, i = 99; char a[16] = "", b[16] = "", more[4] = "";
    if (sscanf(s.c_str(), "t3 %u", &p) == 1 && s.compare(0, 3, "t3 ") == 0) {
        if (p >= (unsigned) THEME_COUNT) return false;
        t.no = (uint8_t) p;
        readColours(s, " p:", t.panels, THEME_COUNT); readColours(s, " i:", t.inks, THEME_COUNT);
    } else if (sscanf(s.c_str(), "t2 %u %u", &p, &i) == 2 && s.compare(0, 3, "t2 ") == 0) {   // (1.7.6 to 1.8.3: twelve panels and six text colours of their own)
        if (p >= (unsigned) THEME_COUNT || i >= 6) return false;
        t.no = (uint8_t) p;
        uint16_t oldInks[6]; for (int k = 0; k < 6; ++k) oldInks[k] = OLD_T2_INKS[k];
        readColours(s, " p:", t.panels, THEME_COUNT); readColours(s, " i:", oldInks, 6);
        t.inks[p] = oldInks[i];                        // the screens look as they did; the other themes keep the text colours they came with
    } else if (sscanf(s.c_str(), "t1 %15s %15s %3s", a, b, more) == 2) {   // (1.7.0 to 1.7.5: by name, as the nearest theme on offer now)
        int pc = -1;
        for (auto &o : OLD_PANELS) if (!strcmp(a, o.key)) pc = o.colour;
        bool inkKnown = false; for (auto &o : OLD_INKS) if (!strcmp(b, o.key)) inkKnown = true;
        if (pc < 0 || !inkKnown) return false;
        t.no = (uint8_t) nearest(t.panels, THEME_COUNT, (uint16_t) pc);
    } else return false;
    *this = t; return true;
}
bool Theme::operator==(const Theme &o) const {
    if (no != o.no) return false;
    for (int i = 0; i < THEME_COUNT; ++i) if (panels[i] != o.panels[i] || inks[i] != o.inks[i]) return false;
    return true;
}

// ------------------------------------------------------------------ which colours are the style's
static int backRole(uint16_t c) { return c == STYLE_PANEL ? 1 : c == STYLE_STRIP ? 2 : 0; }
static int inkRole(uint16_t c) { return c == STYLE_INK ? 1 : c == STYLE_SOFT ? 2 : c == STYLE_ACCENT ? 3 : 0; }
static uint16_t at(int field, int role) { return (uint16_t) ((role & 3) << (2 * field)); }
static const uint16_t INKS = (uint16_t) ((3u << (2 * TF_PCO)) | (3u << (2 * TF_PCO2)) | (3u << (2 * TF_BORDER)));

uint16_t themeRoles(uint16_t bco, uint16_t bco2, uint16_t pco, uint16_t pco2, uint16_t borderc) {
    const int back = backRole(bco);
    uint16_t r = (uint16_t) (at(TF_BCO, back) | at(TF_BCO2, backRole(bco2)));
    if (back) r |= (uint16_t) (at(TF_PCO, inkRole(pco)) | at(TF_PCO2, inkRole(pco2)) | at(TF_BORDER, inkRole(borderc)));   // (writing on anything else is not the style's)
    return r;
}
int themeRole(uint16_t roles, int field) { return (roles >> (2 * field)) & 3; }
uint16_t themeRoleWritten(uint16_t roles, int field, uint16_t v) {
    roles &= (uint16_t) ~(3u << (2 * field));
    if (field == TF_BCO || field == TF_BCO2) {
        const int b = backRole(v);
        roles |= at(field, b);
        if (field == TF_BCO && !b) roles &= (uint16_t) ~INKS;          // writing on a colour of the main board's is its own
    } else if (themeRole(roles, TF_BCO)) roles |= at(field, inkRole(v));   // white put back on a panel: the chosen writing again
    return roles;
}
uint16_t themeColour(const Theme &t, int field, int role) {
    if (field == TF_BCO || field == TF_BCO2) return role == 2 ? t.strip() : t.panel();
    return role == 2 ? t.soft() : role == 3 ? t.accent() : t.ink();
}

// ------------------------------------------------------------------ the Themes page
static const int ID_THEME = 300, ID_CANCEL = 104, ID_OK = 103, ID_EDIT = 105, ID_DEFAULTS = 106, ID_KIND_PANEL = 107, ID_KIND_INK = 108, ID_SLIDE = 130, ID_PREVIEW = 140;
static ThemeRect slot(int i) { return ThemeRect(14 + i * 197, 414, 180, 56); }   // the pages' button places (Back ... OK)
static uint32_t hashOf(const std::string &s, uint32_t h) { for (unsigned char c : s) h = (h ^ c) * 16777619u; return h; }
// The themes go by number, not name (Malcolm, 10-04: "if I define green to be blue instead, the name will look a bit
// wrong!"): 1 to 12, each number in the theme's text colour on its panel colour - the theme itself, in little.

void ColoursPage::open(const Theme &inUse) { openNow = true; closed = false; keptIt = false; edit = false; pick = inUse; pressedId = -1; down = slidOff = false; }
void ColoursPage::close(bool keep) { if (!openNow) return; openNow = false; closed = true; keptIt = keep; edit = false; pressedId = -1; down = slidOff = false; }
bool ColoursPage::takeClosed(bool &kept) { if (!closed) return false; closed = false; kept = keptIt; return true; }

void ColoursPage::build() {
    // (Edit themes is drawn in the colours it opened with: the work shows in the sample and the swatches, the page shows
    // it after OK. Malcolm, 10-04: the page repainting itself in a panel being made, at the next touch, was "very strange")
    sc = ColoursScene(); sc.theme = edit ? before : pick; sc.editing = edit;
    ThemeTile b; b.button = true; b.face = 0xD69A; b.ink = 0x0000;
    if (!edit) {                                        // the screens' theme: twelve to touch, the page drawn in the one chosen
        sc.layout = 5000u + pick.no;
        sc.title = "Themes";
        for (int i = 0; i < THEME_COUNT; ++i) {         // four to a row, three rows, the page's width
            ThemeTile t; t.id = ID_THEME + i; t.r = ThemeRect(14 + (i % 4) * 197, 80 + (i / 4) * 106, 180, 92); t.text = std::to_string(i + 1);
            t.face = pick.panels[i]; t.ink = pick.inks[i]; t.chosen = i == pick.no; sc.tiles.push_back(t);
        }
        b.id = ID_CANCEL; b.r = slot(0); b.text = "Cancel"; sc.tiles.push_back(b);
        b.id = ID_EDIT; b.r = slot(1); b.text = "Edit themes"; sc.tiles.push_back(b);
        b.id = ID_OK; b.r = slot(3); b.text = "OK"; sc.tiles.push_back(b);
    } else {                                            // Edit themes: either colour of any of the twelve made from any colour
        sc.layout = 7000u + (uint32_t) editKind * 100u + (uint32_t) editIndex;
        sc.title = "Edit themes"; sc.hint = "Touch a theme, then slide the bars.";
        for (int i = 0; i < THEME_COUNT; ++i) {         // three to a row, four rows, on the left
            ThemeTile t; t.id = ID_THEME + i; t.r = ThemeRect(14 + (i % 3) * 126, 92 + (i / 3) * 78, 120, 68); t.text = std::to_string(i + 1);
            t.face = pick.panels[i]; t.ink = pick.inks[i]; t.chosen = editIndex == i; sc.tiles.push_back(t);
        }
        ThemeTile pv; pv.id = ID_PREVIEW; pv.preview = true; pv.r = ThemeRect(400, 92, 386, 110);   // the theme as it will look
        pv.face = pick.panels[editIndex]; pv.ink = pick.inks[editIndex];
        sc.tiles.push_back(pv);
        // which of its two colours is being made (Malcolm, 10-04: "it lacks a button to define the text colour")
        ThemeTile kb; kb.button = true; kb.face = 0xD69A; kb.ink = 0x0000;
        kb.id = ID_KIND_PANEL; kb.r = ThemeRect(400, 210, 189, 44); kb.text = "Panel colour"; kb.chosen = editKind == 0; if (kb.chosen) kb.face = 0xFFF3; sc.tiles.push_back(kb);
        kb.id = ID_KIND_INK; kb.r = ThemeRect(597, 210, 189, 44); kb.text = "Text colour"; kb.chosen = editKind == 1; kb.face = kb.chosen ? 0xFFF3 : 0xD69A; sc.tiles.push_back(kb);
        // (their names to their right: Colour, Strength, Light. Malcolm, 10-04: against the right-hand edge of the glass, a bar
        // was hard to slide all the way - and the touch chip's readings go astray at the edge)
        for (int k = 0; k < 3; ++k) { ThemeTile s; s.id = ID_SLIDE + k; s.r = ThemeRect(400, 262 + k * 46, 282, 40); s.slider = (uint8_t) (k + 1); s.hsv = editHsv; sc.tiles.push_back(s); }
        b.id = ID_CANCEL; b.r = slot(0); b.text = "Cancel"; sc.tiles.push_back(b);
        b.id = ID_DEFAULTS; b.r = slot(1); b.text = "Defaults"; sc.tiles.push_back(b);
        b.id = ID_OK; b.r = slot(3); b.text = "OK"; sc.tiles.push_back(b);
    }
    for (auto &t : sc.tiles) {
        t.pressed = t.id == pressedId && !slidOff;
        t.serial = hashOf(t.text, 2166136261u) ^ ((uint32_t) t.face << 8) ^ ((uint32_t) t.ink << 3) ^ (t.chosen ? 2u : 0u) ^ (t.pressed ? 1u : 0u);
        if (t.slider) t.serial = ((t.serial ^ (uint32_t) t.hsv.h) * 16777619u ^ (uint32_t) t.hsv.s) * 16777619u ^ (uint32_t) t.hsv.v;
        if (t.preview) t.serial = (t.serial * 16777619u) ^ pick.softOf(editIndex) ^ ((uint32_t) pick.stripOf(editIndex) << 16);
    }
}
const ColoursScene &ColoursPage::scene() { build(); return sc; }

int ColoursPage::idAt(int x, int y) const {
    for (auto &t : sc.tiles) if (!t.preview && t.r.has(x, y)) return t.id;
    return -1;
}
bool ColoursPage::isSlider(int id) const { return edit && id >= ID_SLIDE && id < ID_SLIDE + 3; }
void ColoursPage::slide(int id, int x) {
    for (auto &t : sc.tiles) {
        if (t.id != id) continue;
        const int span = t.r.w > 1 ? t.r.w - 1 : 1; int p = x - t.r.x; p = p < 0 ? 0 : p > span ? span : p;
        if (id == ID_SLIDE) {                           // the rainbow: a colour without strength (white, grey) or light (black) gets some, or nothing would change
            editHsv.h = (int16_t) (p * 359 / span);      // (Malcolm, 10-04: "Editing the text colour does not seem possible yet" - white stayed white)
            if (editHsv.s < 30) editHsv.s = 70;
            if (editHsv.v < 30) editHsv.v = 80;
        }
        else if (id == ID_SLIDE + 1) editHsv.s = (int8_t) (p * 100 / span);
        else editHsv.v = (int8_t) (p * 100 / span);
        (editKind == 0 ? pick.panels[editIndex] : pick.inks[editIndex]) = themeFromHsv(editHsv.h, editHsv.s, editHsv.v);
        return;
    }
}
void ColoursPage::editPick() {
    ThemeHsv n = themeToHsv(editKind == 0 ? pick.panels[editIndex] : pick.inks[editIndex]);
    if (n.s == 0 || n.v == 0) n.h = editHsv.h;          // (a grey, or black, has no colour of its own: the bar stays where it was)
    if (n.v == 0) n.s = editHsv.s;
    editHsv = n;
}
void ColoursPage::touch(bool pressed, int x, int y, uint32_t now) {
    if (!openNow) return;
    if (pressed) {
        lastSeen = now;
        const int id = idAt(x, y);
        if (!down) { down = true; pressedId = id; slidOff = false; slideHave = false; slidePend = -1; }
        else if (id != pressedId && !isSlider(pressedId)) slidOff = true;   // it has slid off: lifting it does nothing
        if (isSlider(pressedId)) {                     // a bar follows the finger, wherever it goes ...
            // ... but not a reading far from the finger's last place unless the next one agrees: the touch chip gives the
            // odd stray point, worst at the edge of the glass, and the last reading before a lift would otherwise win
            if (!slideHave || abs(x - slideX) <= 100 || (slidePend >= 0 && abs(x - slidePend) <= 24)) { slide(pressedId, x); slideX = x; slideHave = true; slidePend = -1; }
            else slidePend = x;
        }
        return;
    }
    if (!down || (int32_t) (now - lastSeen) <= 80) return;   // a sample the chip dropped mid-press, not a lift
    down = false;
    const int was = pressedId; const bool off = slidOff;
    pressedId = -1; slidOff = false;
    if (was >= 0 && !off) releaseOn(was);
}
void ColoursPage::releaseOn(int id) {
    if (!edit) {
        if (id >= ID_THEME && id < ID_THEME + THEME_COUNT) pick.no = (uint8_t) (id - ID_THEME);
        else if (id == ID_CANCEL) close(false);
        else if (id == ID_OK) close(true);
        else if (id == ID_EDIT) { edit = true; before = pick; editKind = 0; editIndex = pick.no; editPick(); }   // (the screens' theme first)
        return;
    }
    if (id >= ID_THEME && id < ID_THEME + THEME_COUNT) { editIndex = id - ID_THEME; editPick(); }
    else if (id == ID_KIND_PANEL) { editKind = 0; editPick(); }
    else if (id == ID_KIND_INK) { editKind = 1; editPick(); }
    else if (id == ID_DEFAULTS) { pick.defaults(); editPick(); }
    else if (id == ID_CANCEL) { pick = before; edit = false; }   // (the colours as they were when Edit themes opened)
    else if (id == ID_OK) edit = false;
}

// ------------------------------------------------------------------ the Appearance page
bool AppearancePage::request(const AppearanceWorld &w) {
    if (openNow || w.armed || w.otherUp || w.coloursBusy || w.frontBusy || w.page.empty() || w.page == "BlankView") return false;
    overPage = w.page; waitFor = APP_NONE; show();
    return true;
}
void AppearancePage::handOff(int act, uint32_t now) {
    if (act == APP_COLOURS || act == APP_FRONT) { openNow = false; pressedId = -1; down = slidOff = false; waitFor = act; askedAt = now; }
    else if (act == APP_BACKGROUND || act == APP_HELP) { waitFor = act; sawAway = false; askedAt = now; }
}
void AppearancePage::poll(const AppearanceWorld &w) {
    const bool home = w.page == overPage, blank = w.page == "BlankView";   // (the main board blanks the screen to save power, and between pages)
    if (w.armed) { if (openNow || waitFor != APP_NONE) close(); return; }   // flying: gone, and not back
    if (waitFor == APP_COLOURS || waitFor == APP_FRONT) {
        if (!(waitFor == APP_COLOURS ? w.coloursBusy : w.frontBusy)) {      // done (or it would not open): back, if the main board is still on the same page
            waitFor = APP_NONE;
            if (home && !w.otherUp) show();
        }
    } else if (waitFor == APP_BACKGROUND || waitFor == APP_HELP) {
        if (!home && !blank) {
            if (!sawAway) { sawAway = true; awayPage = w.page; }
            else if (w.page != awayPage) waitFor = APP_NONE;              // (it went on somewhere else: not back here by surprise later)
        }
        if (waitFor != APP_NONE && sawAway && home) { waitFor = APP_NONE; if (!w.otherUp) show(); }
        else if (!sawAway && (int32_t) (w.now - askedAt) > 2500) waitFor = APP_NONE;   // the main board did not go there: this page stays, to be pressed again
    }
    if (openNow && ((!home && !blank) || w.otherUp)) {
        openNow = false; pressedId = -1; down = slidOff = false;
        if (!(waitFor == APP_BACKGROUND || waitFor == APP_HELP) || w.otherUp) waitFor = APP_NONE;   // (the main board's page asked for: back here after it)
    }
}
const AppearanceScene &AppearancePage::scene() {
    sc = AppearanceScene(); sc.layout = 9000; sc.title = "Appearance";
    static const struct { int id; const char *text; } BUTTONS[] = { { APP_BACKGROUND, "Background picture" }, { APP_COLOURS, "Themes" }, { APP_FRONT, "Front screen" } };
    for (int k = 0; k < 3; ++k) {
        ThemeTile t; t.button = true; t.face = 0xD69A; t.ink = 0x0000; t.id = BUTTONS[k].id; t.text = BUTTONS[k].text;
        t.r = ThemeRect(190, 96 + k * 96, 420, 76); sc.tiles.push_back(t);
    }
    ThemeTile b; b.button = true; b.face = 0xD69A; b.ink = 0x0000; b.id = APP_BACK; b.text = "OK"; b.r = slot(3); sc.tiles.push_back(b);   // (OK at the bottom right, as on every page - Malcolm, 10-04)
    b.id = APP_HELP; b.text = "Help"; b.r = ThemeRect(620, 4, 170, 50); sc.tiles.push_back(b);   // (where the pages have theirs)
    for (auto &t : sc.tiles) { t.pressed = t.id == pressedId && !slidOff; t.serial = hashOf(t.text, 2166136261u) ^ (t.pressed ? 1u : 0u); }
    return sc;
}
void AppearancePage::touch(bool pressed, int x, int y, uint32_t now) {
    if (!openNow || (waitFor != APP_NONE && pressed && !down)) return;   // (the main board's page is coming: no new press)
    if (pressed) {
        lastSeen = now;
        int id = -1; for (auto &t : sc.tiles) if (t.r.has(x, y)) id = t.id;
        if (!down) { down = true; pressedId = id; slidOff = false; }
        else if (id != pressedId) slidOff = true;      // it has slid off: lifting it does nothing
        return;
    }
    if (!down || (int32_t) (now - lastSeen) <= 80) return;   // a sample the chip dropped mid-press, not a lift
    down = false;
    const int was = pressedId; const bool off = slidOff;
    pressedId = -1; slidOff = false;
    if (was > 0 && !off) action = was;
}

}  // namespace ldrc
