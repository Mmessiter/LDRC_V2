// The screen's colours: twelve THEMES, each a panel colour with its own text colour, chosen and edited by the pilot.
// Malcolm, 2026-10-04: "Because the dark blue and white are becoming ubiquitous around this firmware, let's make these
// colours user-definable somewhere." Then, of the front screen's boxes: "I'd like to use some brighter options - eg red
// with white text; white with burgundy text… but we mustn't have too many options... can we have an area that allows
// our selection of colour options to be itself defined from infinite colour options?" And: "I had thought the option
// to define the colours would occur on this screen so that it can affect all of the backgrounds, and these options would
// simply be reused for the individual boxes on the defined front screen." And (1.8.4): "I don't think we need both panels
// and text because the text is displayed within the panels ... We have here 12 themes that can be edited each with a
// foreground and background colour ... Perhaps it's good to call them themes rather than colours, because each has two
// colours."
//
// So the Themes page offers twelve themes, the pilot's own: one is the screens', and the front screen's boxes choose from
// the same twelve. Edit themes changes either colour of any of them (colour, strength and light: three bars).
//
// The pages were restyled (hmi/pagestyle.py) with a navy panel (0x114A), a darker navy strip along the top (0x08A6),
// white writing, light grey (0xC618) for the quieter words and yellow for the model's name. The two navies are used for
// nothing else, so a component whose background is one of them is part of the style: its background follows the chosen
// theme's panel colour, its white, light grey and yellow writing the theme's text colour, its quieter shade and its accent
// (yellow, or on a light panel the text colour: yellow does not read on white). Everything else stays as it is: the
// buttons, the white boxes that are typed into, red and green, the pictures. The screen's own pages take the same colours.
//
// Portable: no Arduino, tested on the Mac (hmi/test_theme). The drawing is src/theme_draw.h, the rest src/theme_device.h.
#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace ldrc {

static const uint16_t STYLE_PANEL = 0x114A, STYLE_STRIP = 0x08A6, STYLE_INK = 0xFFFF, STYLE_SOFT = 0xC618, STYLE_ACCENT = 0xFFE0;

// The themes as they come. A colour as it came keeps its tuned shades (the strip and the outline for a panel, the quieter
// words for a text colour); one the pilot has changed gets shades worked out from it.
struct ThemePair { const char *name, *key; uint16_t panel, strip, edge, ink, soft; };
static const int THEME_COUNT = 12, THEME_PANEL_COUNT = THEME_COUNT;   // (THEME_PANEL_COUNT: the older name, used by the front screen)
extern const ThemePair THEME_PAIRS[THEME_COUNT];   // eight dark with white text, then red/white, white/burgundy, yellow/black, sky/navy

// Colour maths (RGB565)
struct ThemeHsv { int16_t h; int8_t s, v; };           // colour 0..359 round the rainbow, strength (grey to vivid) and light (black to bright) 0..100
ThemeHsv themeToHsv(uint16_t c);
uint16_t themeFromHsv(int h, int s, int v);
uint16_t themeBlend(uint16_t a, uint16_t b, int pctA); // pctA % of a, the rest of b
bool themeIsLight(uint16_t c);                         // dark words read on it
double themeContrast(uint16_t a, uint16_t b);          // the web's measure: 4.5 reads well, 3 for big or quiet words
uint16_t themeReadable(uint16_t ink, uint16_t face);   // ink if it reads on face, else black or white, whichever does

struct Theme {
    uint8_t no = 0;                                    // the screens' theme
    uint16_t panels[THEME_COUNT], inks[THEME_COUNT];   // each theme's panel and text colour (as they came, until the pilot changes them)
    Theme();
    int which() const { return no < THEME_COUNT ? no : 0; }
    uint16_t panel() const { return panels[which()]; }
    uint16_t ink() const { return inks[which()]; }
    uint16_t strip() const { return stripOf(which()); }
    uint16_t edge() const { return edgeOf(which()); }
    uint16_t soft() const { return softOf(which()); }
    uint16_t accent() const { return themeIsLight(panel()) ? ink() : STYLE_ACCENT; }
    uint16_t stripOf(int t) const;                     // the strip along the top of a page in theme t
    uint16_t edgeOf(int t) const;                      // a box's outline in theme t
    uint16_t softOf(int t) const;                      // theme t's quieter words
    bool changed(int kind, int t) const;               // kind 0: theme t's panel, 1: its text colour - not as it came
    bool custom() const;                               // any colour not as it came
    void defaults();                                   // every colour as it came (which theme is the screens' is kept)
    std::string save() const;                          // "t3 5" (+ " p:...,... i:...,..." when any colour is the pilot's own)
    bool load(const std::string &s);                   // false (and nothing changed) if not one of ours; screens 1.7.6-1.8.3's "t2 P I ..." and 1.7.0-1.7.5's "t1 name name" too
    bool operator==(const Theme &o) const;
    bool operator!=(const Theme &o) const { return !(*this == o); }
};
// Which of a component's colours belong to the style, worked out from its page's own colours when the page is loaded:
// two bits a colour, 0 not the style's; a background 1 the panel, 2 the strip; writing 1 the text, 2 the quieter, 3 the accent.
enum ThemeField { TF_BCO = 0, TF_BCO2, TF_PCO, TF_PCO2, TF_BORDER, TF_COUNT };
uint16_t themeRoles(uint16_t bco, uint16_t bco2, uint16_t pco, uint16_t pco2, uint16_t borderc);
int themeRole(uint16_t roles, int field);
uint16_t themeRoleWritten(uint16_t roles, int field, uint16_t v);   // the main board (or a page's script) has set this colour: its role, from what was written
uint16_t themeColour(const Theme &t, int field, int role);          // the colour now, for a colour with this role

// ------------------------------------------------------------------ the Themes page
struct ThemeRect {
    int16_t x = 0, y = 0, w = 0, h = 0;
    ThemeRect() {}
    ThemeRect(int x_, int y_, int w_, int h_) : x((int16_t) x_), y((int16_t) y_), w((int16_t) w_), h((int16_t) h_) {}
    bool has(int px, int py) const { return px >= x && px < x + w && py >= y && py < y + h; }
};
// A theme to touch (its number in its text colour on its panel colour), a button, one of Edit themes' bars (slider 1
// colour, 2 strength, 3 light, with the colour being made), or the sample page (preview: a small page in face and ink).
struct ThemeTile {
    int id = 0; ThemeRect r; std::string text; uint16_t face = 0, ink = 0;
    bool button = false, chosen = false, pressed = false, preview = false; uint8_t slider = 0; ThemeHsv hsv = { 0, 0, 0 };
    uint32_t serial = 0;
};
struct ColoursScene {
    uint32_t layout = 0;                               // changes when everything must be drawn again: a theme chosen (the page shows it)
    Theme theme;                                       // the page is drawn in these: the theme chosen so far (Edit themes: as they were when it opened)
    bool editing = false;                              // Edit themes (else the choice of the screens' theme)
    std::string title, hint;
    std::vector<ThemeTile> tiles;
};
static const int THEME_W = 800, THEME_H = 480, THEME_STRIP = 58;

class ColoursPage {
public:
    void open(const Theme &inUse);
    void close(bool keep);                             // OK keeps what was chosen; Cancel, another page, flying: the theme in use stays
    bool isOpen() const { return openNow; }
    bool editing() const { return edit; }
    bool takeClosed(bool &kept);                       // true once after it has closed (kept: with OK)
    const Theme &chosen() const { return pick; }
    void touch(bool pressed, int x, int y, uint32_t now);   // at every pass while it is open: a lift counts after 80 ms with no samples
    const ColoursScene &scene();
private:
    bool openNow = false, closed = false, keptIt = false, edit = false;
    Theme pick, before;                                // the theme being chosen (and the colours being made); (Edit themes) as they were when it opened
    int editKind = 0, editIndex = 0; ThemeHsv editHsv = { 0, 0, 100 };   // Edit themes: which theme, its panel (0) or its text colour (1), and the colour being made
    int pressedId = -1; bool down = false, slidOff = false; uint32_t lastSeen = 0;
    int slideX = 0, slidePend = -1; bool slideHave = false;   // (a bar being slid: the finger's last place taken, and a far reading waiting for a second)
    ColoursScene sc;
    void build();
    int idAt(int x, int y) const;
    void releaseOn(int id);
    bool isSlider(int id) const;
    void slide(int id, int x);
    void editPick();
};

// ------------------------------------------------------------------ the Appearance page (screen 1.8.0)
// Malcolm, 10-04: "Background and colours, and flight screen, are very closely associated, and yet they are separated on
// the transmitter set up screen. I think they merit their own subcategory: appearance." One button on Transmitter setup
// opens it: the background picture (the main board's own page), Themes, and the front screen of the pilot's own; Help at
// the top right, as on the other pages. Each comes back here when it is done (src/theme_device.h).
enum AppearanceAction : uint8_t { APP_NONE = 0, APP_BACKGROUND, APP_COLOURS, APP_FRONT, APP_BACK, APP_HELP };   // (APP_BACK: its OK)
// What the screen sees at every pass. The page goes (nothing changed) when the main board leaves the page it was opened
// over, another page of ours shows (an update, WiFi) or flying begins; it comes back when a page it opened is done.
struct AppearanceWorld {
    std::string page;                                  // the main board's page now
    bool coloursBusy = false;                          // the Colours page asked for, or open
    bool frontBusy = false;                            // the front screen's setup asked for, or open
    bool otherUp = false;                              // the update panel or the WiFi page showing
    bool armed = false;                                // flying
    uint32_t now = 0;
};
struct AppearanceScene { uint32_t layout = 0; std::string title; std::vector<ThemeTile> tiles; };
class AppearancePage {
public:
    bool request(const AppearanceWorld &w);            // "ldrc appearance": opens over the page showing (not while flying, or over another page of ours)
    void close() { openNow = false; waitFor = APP_NONE; pressedId = -1; down = slidOff = false; }   // OK: gone, nothing to come back from
    bool isOpen() const { return openNow; }
    bool waiting() const { return waitFor != APP_NONE; }
    const std::string &over() const { return overPage; }
    int takeAction() { const int a = action; action = APP_NONE; return a; }   // once, after a button was let go
    // A button's page has been asked for: one of ours (Colours, the front screen) takes the screen at once, so this page
    // goes; the main board's (the background picture, the help) takes a moment to come, so this page stays until it does
    // (no glimpse of Transmitter setup in between) - or, if it never comes, stays to be pressed again. Back here after.
    void handOff(int act, uint32_t now);
    void poll(const AppearanceWorld &w);               // at every pass
    void touch(bool pressed, int x, int y, uint32_t now);   // while it shows: a lift counts after 80 ms with no samples
    const AppearanceScene &scene();
private:
    bool openNow = false; int action = APP_NONE;
    std::string overPage, awayPage; int waitFor = APP_NONE; bool sawAway = false; uint32_t askedAt = 0;
    int pressedId = -1; bool down = false, slidOff = false; uint32_t lastSeen = 0;
    AppearanceScene sc;
    void show() { openNow = true; action = APP_NONE; pressedId = -1; down = slidOff = false; }
};

}  // namespace ldrc
