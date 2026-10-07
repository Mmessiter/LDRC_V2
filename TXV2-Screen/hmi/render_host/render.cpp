// Render the transmitter's screen on the Mac with the screen's OWN code: the drawing, the fonts (anti-aliased, off
// the card), the page loader, the page scripts and the command handler are cut out of src/main.cpp by extract.py.
// Usage: gen/render <sd folder> <commands file> <output prefix>
// The commands file holds what the Teensy sends, one command a line ("page RatesView", t9.txt="Bank 1", vis busy,0),
// with \r \n escapes, and lines of our own:
//   @shot NAME   the screen as it is now, to <output prefix>NAME.ppm
//   @model 0|1   no model connected / a model connected (buttons with a rule grey out as on the transmitter)
// Build and run: hmi/render_host/build.sh; hmi/render_pages.py does the rest (scenarios, PNGs, sheets).
#include "shim.h"
std::string sdRoot; SDClass SD; SerialStub Serial;
#include <ArduinoJson.h>
#include "NextionScript.h"
#include "nextion_fonts.h"
#include "LdrcTheme.h"
#include "tooth_icon.h"                                  // (1.11.17) the Rotorflight menu's blue tooth
constexpr int W = 800, H = 480;
static Gfx gfxObj; static Gfx *gfx = &gfxObj;
static uint16_t *fbNow = nullptr, *screenFb = nullptr, *pageFb = nullptr;
static void present(int, int, int, int) {}
static bool sdOk = true;
#include "gen/main_parts.inc"
#include "flight_source.h"
#include "flight_draw.h"
#include "theme_draw.h"
#include "pong_draw.h"

// "@flight CONFIG" / "@flightsetup CONFIG [@box N]": the flight screen (as it shows in flight) or its setup page, drawn
// over whatever is on the glass with the front page's values as they stand. CONFIG: "default" or FlightConfig::save().
// "... @sizes": the setup page's choice of box sizes. "... @box N @boxcolour [T]": box N's theme page, with theme T
// (1-12) touched (0: not; a second number, 1.7.6-1.8.3's text colour, is ignored).
static void flightShot(const std::string &arg, bool setup) {
    std::string cfg = arg; int box = -1; bool sizes = false, colourPage = false; int cf = 0, ci = 0;
    const size_t cz = cfg.find(" @boxcolour"); if (cz != std::string::npos) { colourPage = true; sscanf(cfg.c_str() + cz + 11, "%d %d", &cf, &ci); cfg = cfg.substr(0, cz); }
    const size_t z = cfg.find(" @sizes"); if (z != std::string::npos) { sizes = true; cfg = cfg.substr(0, z); }
    const size_t b = cfg.find(" @box ");
    if (b != std::string::npos) { box = atoi(cfg.c_str() + b + 6) - 1; cfg = cfg.substr(0, b); }
    ldrc::FlightScreen fs; ScreenFront src; fs.themeFace = theme.panel(); fs.themeInk = theme.ink();
    for (int k = 0; k < ldrc::THEME_COUNT; ++k) { fs.palPanels[k] = theme.panels[k]; fs.palInks[k] = theme.inks[k]; }
    if (cfg != "default" && !fs.cfg.load(cfg)) fprintf(stderr, "render: not a flight screen setting: %s\n", cfg.c_str());
    if (setup) {
        fs.openSetup(); const ldrc::FlightScene &sc = fs.scene(src, &flightFonts);
        if (box >= 0 && box < (int) sc.tiles.size()) { const ldrc::FlightRect r = sc.tiles[box].r; fs.touch(true, r.x + r.w / 2, r.y + r.h / 2, 0); fs.scene(src); fs.touch(false, 0, 0, 200); }
        uint32_t t = 2000;
        auto tapId = [&](bool (*want)(const ldrc::FlightButton &, int), int arg2) { for (auto &bt : fs.scene(src).buttons) if (want(bt, arg2)) { fs.touch(true, bt.r.x + 5, bt.r.y + 5, t); fs.touch(false, 0, 0, t + 200); t += 1000; return; } };
        if (colourPage) {
            tapId([](const ldrc::FlightButton &bt, int) { return bt.text == "Theme"; }, 0);
            if (cf > 0) tapId([](const ldrc::FlightButton &bt, int k) { return bt.swatch == k; }, cf);
            (void) ci;
        }
        if (sizes) for (auto &bt : fs.scene(src).buttons) if (bt.text == "Box sizes") { fs.touch(true, bt.r.x + 5, bt.r.y + 5, 1000); fs.touch(false, 0, 0, 1200); break; }
    } else fs.poll(0, true, true, false);
    flightDrawAll(fs.scene(src, &flightFonts));
}

// "@theme THEME [IGNORED]" (a theme's key as it came, "wine", or its number): the screens' theme, for the page showing and
// every page after it (1.7.0-1.8.3's second word, a text colour, is ignored). "@colours [WORD ...]": the Themes page,
// with those touched first - a theme (its key or number; "ink:X" presses Text colour), "edit" (Edit themes),
// "panel_colour", "text_colour", "ok", "cancel", "defaults", "hsv:H,S,V" (the three bars slid there, -1 leaves one).
static int themeByWord(const std::string &w) {
    for (int k = 0; k < ldrc::THEME_COUNT; ++k) if (w == ldrc::THEME_PAIRS[k].key || w == std::to_string(k + 1)) return k;
    return -1;
}
static void themeSet(const std::string &arg) {
    char a[16] = "";
    const int k = sscanf(arg.c_str(), "%15s", a) == 1 ? themeByWord(a) : -1;
    if (k < 0) { fprintf(stderr, "render: not a theme: %s\n", arg.c_str()); return; }
    theme.no = (uint8_t) k;
    for (auto &c : page.comps) themeComp(c);
    drawPage();
}
static void coloursShot(const std::string &arg) {
    ldrc::ColoursPage p; p.open(theme); uint32_t t = 1000;
    auto tapTile = [&](const ldrc::ThemeTile &tile) { p.touch(true, tile.r.x + tile.r.w / 2, tile.r.y + tile.r.h / 2, t); p.touch(false, 0, 0, t + 200); t += 1000; };
    size_t i = 0;
    while (i < arg.size()) {
        size_t e = arg.find(' ', i); if (e == std::string::npos) e = arg.size();
        std::string word = arg.substr(i, e - i); i = e + 1;
        if (word.empty()) continue;
        if (word.rfind("hsv:", 0) == 0) {
            int v[3] = { -1, -1, -1 }; sscanf(word.c_str() + 4, "%d,%d,%d", &v[0], &v[1], &v[2]);
            for (int k = 0; k < 3; ++k) if (v[k] >= 0) for (auto &tile : p.scene().tiles) if (tile.slider == k + 1) {
                const int x = tile.r.x + v[k] * (tile.r.w - 1) / (k == 0 ? 359 : 100);
                p.touch(true, x, tile.r.y + 5, t); p.scene(); p.touch(true, x, tile.r.y + 5, t + 50); p.touch(false, 0, 0, t + 250); t += 1000; break;
            }
            continue;
        }
        if (word.rfind("ink:", 0) == 0) word = "text_colour";         // (1.7.6-1.8.3: a text colour of its own; now the theme's)
        std::string want = word == "edit" ? "edit themes" : word; for (auto &ch : want) if (ch == '_') ch = ' ';   // ("text_colour": the Text colour button)
        const int th = themeByWord(want); if (th >= 0) want = std::to_string(th + 1);
        bool found = false;
        for (auto &tile : p.scene().tiles) {
            if (tile.slider || tile.preview) continue;
            std::string low = tile.text; for (auto &ch : low) ch = (char) tolower(ch);
            if (low != want) continue;
            tapTile(tile); found = true; break;
        }
        if (!found) fprintf(stderr, "render: nothing called %s on the Themes page\n", word.c_str());
    }
    themeDrawAll(p.scene());
}

// "@pong x,y,ly,ry": Pong's court (screen 1.9.3) as the screen draws it over the Pong page, the ball and paddles there
static void pongShot(const std::string &arg) { int v[4] = { 405, 235, 235, 235 }; sscanf(arg.c_str(), "%d,%d,%d,%d", &v[0], &v[1], &v[2], &v[3]); pongDrawAll(v[0], v[1], v[2], v[3], true); }

// "@appearance": the Appearance page (screen 1.8.0), over the page showing
static void appearanceShot() { ldrc::AppearancePage p; ldrc::AppearanceWorld w; w.page = page.name; p.request(w); appearanceDrawAll(p.scene(), theme); }

static std::string unescape(const std::string &s) {
    std::string o;
    for (size_t i = 0; i < s.size(); ++i) {
        if (s[i] == '\\' && i + 1 < s.size() && (s[i + 1] == 'r' || s[i + 1] == 'n')) { o += s[i + 1] == 'r' ? '\r' : '\n'; ++i; }
        else o += s[i];
    }
    return o;
}
static bool shot(const std::string &path) {
    FILE *f = fopen(path.c_str(), "wb"); if (!f) return false;
    fprintf(f, "P6\n%d %d\n255\n", W, H);
    for (int i = 0; i < W * H; ++i) { const uint16_t v = fbNow[i]; const uint8_t rgb[3] = { (uint8_t) (((v >> 11) & 31) * 255 / 31), (uint8_t) (((v >> 5) & 63) * 255 / 63), (uint8_t) ((v & 31) * 255 / 31) }; fwrite(rgb, 1, 3, f); }
    fclose(f); return true;
}
int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "usage: render <sd folder> <commands file> <output prefix>\n"); return 2; }
    sdRoot = argv[1]; if (!sdRoot.empty() && sdRoot.back() == '/') sdRoot.pop_back();
    static uint16_t fb[W * H]; gfx->fb = fb; fbNow = screenFb = pageFb = fb;
    loadAaFonts();
    for (int i = 0; i < 7; ++i) if (!aaBits[i]) fprintf(stderr, "render: font %d has no anti-aliased table (1-bit drawing)\n", i);
    { File f = SD.open("/hmi/index.json");
      if (f) { JsonDocument doc; if (!deserializeJson(doc, f)) for (JsonObject p : doc["pages"].as<JsonArray>()) { int id = p["id"] | 0; std::string nm = p["name"] | ""; if ((int) pageNames.size() <= id) pageNames.resize(id + 1); pageNames[id] = nm; pageIds[nm] = id; } f.close(); } }
    if (pageNames.empty()) { fprintf(stderr, "render: no pages in %s/hmi/index.json\n", sdRoot.c_str()); return 1; }
    host.sys["sys0"] = 0; host.sys["sys1"] = 0; host.sys["sys2"] = 0; host.sys["sys3"] = 0;
    host.sys["Screen_Background"] = 3; host.sys["Button_BackGround"] = 54938; host.sys["Button_ForeGround"] = 0;
    FILE *in = fopen(argv[2], "r"); if (!in) { fprintf(stderr, "render: cannot read %s\n", argv[2]); return 1; }
    char line[8192]; int shots = 0; const uint32_t bad0 = badCount;
    while (fgets(line, sizeof(line), in)) {
        std::string s = line; while (!s.empty() && (s.back() == '\n' || s.back() == '\r')) s.pop_back();
        if (s.empty() || s[0] == '#') continue;
        if (s.rfind("@shot ", 0) == 0) { if (!shot(argv[3] + s.substr(6) + ".ppm")) { fprintf(stderr, "render: cannot write %s\n", (argv[3] + s.substr(6)).c_str()); return 1; } shots++; continue; }
        if (s.rfind("@model ", 0) == 0) { txStatus = (s[7] == '1' ? TX_MODEL : 0) | (txStatus > 0 ? (txStatus & TX_RADIOS_OFF) : 0); continue; }
        if (s.rfind("@flying ", 0) == 0) { if (txStatus < 0) txStatus = 0; txStatus = s[8] == '1' ? (txStatus | TX_RADIOS_OFF) : (txStatus & ~TX_RADIOS_OFF); tx.armed = s[8] == '1'; continue; }
        if (s.rfind("@flightsetup ", 0) == 0) { flightShot(s.substr(13), true); continue; }
        if (s.rfind("@flight ", 0) == 0) { flightShot(s.substr(8), false); continue; }
        if (s.rfind("@theme ", 0) == 0) { themeSet(s.substr(7)); continue; }
        if (s == "@appearance") { appearanceShot(); continue; }
        if (s.rfind("@pong ", 0) == 0) { pongShot(s.substr(6)); continue; }
        if (s == "@colours" || s.rfind("@colours ", 0) == 0) { coloursShot(s.size() > 9 ? s.substr(9) : std::string()); continue; }
        handle(unescape(s));
    }
    fclose(in);
    if (badCount != bad0) fprintf(stderr, "render: %u command(s) not understood: %s\n", (unsigned) (badCount - bad0), oddTrace.c_str());
    printf("%d picture(s)\n", shots);
    return 0;
}
