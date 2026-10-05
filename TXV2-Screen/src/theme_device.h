// The pilot's themes on the transmitter (lib/LdrcTheme does the thinking, src/theme_draw.h the drawing). The Themes page
// is our own, on our layer, opened by "ldrc colours" (the Teensy's Background page has the button); it is drawn in the
// colours as they are chosen, and the page underneath takes them when OK is pressed. The choice is kept in the chip
// (preferences "theme"), written when the wire is quiet. Nothing goes to the main board but the touch word that keeps
// its screen saver away while the page is being used.
// Included by main.cpp after flight_device.h.
#include "theme_draw.h"

static const int COLOURS_WHO = 7;                               // the layer's owner (main.cpp topWho)
static ldrc::ColoursPage colours;
static std::string coloursOver;                                 // the page it was opened over: it goes when the main board leaves it
static uint32_t coloursTouchedAt = 0;
static bool themeSaveWanted = false; static uint32_t themeSaveAt = 0;

static bool coloursUp() { return topOn && topWho == COLOURS_WHO; }
static void themeLoad() {
    const std::string s = prefs.getString("theme", "").c_str();
    if (!s.empty() && !theme.load(s)) blog("theme", "setting not understood: " + s);
}
static void coloursTouch(bool pressed, int x, int y, uint32_t now) {
    static uint32_t lastDown = 0;
    if (pressed) { coloursTouchedAt = now; lastDown = now; }
    if (touchLockout) {                                         // the finger that opened the page, or woke the screen, is still down: it is not for us
        if (!pressed && (int32_t) (now - lastDown) > 80) touchLockout = false;
        return;
    }
    colours.touch(pressed, x, y, now);
}
// The colours chosen: the page underneath in them at once (its components were coloured when it was loaded).
static void themeRepaint() {
    for (auto &c : page.comps) { themeComp(c); c.damaged = true; }
    drawPage();
}
static void coloursPoll() {
    static uint32_t drawnLayout = 0, lastBuild = 0, lastPoke = 0; static bool wasUp = false;
    static std::map<int, uint32_t> drawn;
    const uint32_t now = millis();
    if (coloursRequested) {
        coloursRequested = false;
        if (!colours.isOpen() && !updShowing() && !wifiPage.showing() && !flight.setupOpen() && !armedNow) { colours.open(theme); coloursOver = page.name; coloursTouchedAt = now; }
    }
    // It goes (nothing changed) when the main board leaves the page it was over, when another page of ours is asked for,
    // and when flying begins.
    if (colours.isOpen() && ((page.name != coloursOver && page.name != "BlankView") || updShowing() || wifiPage.showing() || armedNow)) colours.close(false);
    bool kept = false;
    if (colours.takeClosed(kept) && kept && colours.chosen() != theme) {
        theme = colours.chosen(); themeSaveWanted = true; themeSaveAt = now;
        if (topWho == COLOURS_WHO) { topOn = false; topWho = 0; }   // our page goes, and the page underneath is drawn in the new colours
        themeRepaint(); wasUp = false; drawn.clear(); drawnLayout = 0; touchPainted = true;
    }
    if (themeSaveWanted) {                                      // (a flash write stalls the chip: when the wire is quiet, and never in flight)
        if (teensyLink.running() || armedNow) themeSaveAt = now;
        else if ((int32_t) (now - lastRxMs) > 300 || now - themeSaveAt > 3000) {
            themeSaveWanted = false;
            const std::string s = theme.save();
            if (std::string(prefs.getString("theme", "").c_str()) != s) prefs.putString("theme", s.c_str());
        }
    }
    const bool layerFree = !topOn || topWho == COLOURS_WHO, blank = page.name == "BlankView";
    const bool up = colours.isOpen() && layerFree && !blank && topReady();
    if (up) {
        if (wasUp && now - lastBuild < 50) return;
        lastBuild = now;
        const ldrc::ColoursScene &sc = colours.scene();
        if (!wasUp || sc.layout != drawnLayout) {
            { TopDraw on; themeDrawAll(sc); }
            drawn.clear(); for (auto &t : sc.tiles) drawn[t.id] = t.serial;
            drawnLayout = sc.layout;
            topX = 0; topY = 0; topW = W; topH = H; topWho = COLOURS_WHO; topOn = true;
            dirty(0, 0, W, H); touchPainted = true;
        } else {
            for (auto &t : sc.tiles) {
                auto d = drawn.find(t.id); if (d != drawn.end() && d->second == t.serial) continue;
                { TopDraw on; themeDrawTile(t, sc.theme); }
                drawn[t.id] = t.serial; dirty(t.r.x, t.r.y, t.r.w, t.r.h); touchPainted = true;
            }
        }
        // (the main board cannot see touches on our pages: its screen saver is told someone is here, as the other pages of ours tell it)
        if (now - coloursTouchedAt < 180000 && now - lastPoke > 20000 && !teensyLink.running()) { lastPoke = now; flushOut(); Serial.write((const uint8_t *) "UKRULES", 7); }
    } else if (wasUp) {
        if (topWho == COLOURS_WHO) { topOn = false; topWho = 0; }
        dirty(0, 0, W, H); touchPainted = true;                 // the page, as the main board has drawn it meanwhile
        drawn.clear(); drawnLayout = 0;
    }
    wasUp = up;
}
static void coloursPageLoaded() { if (colours.isOpen() || coloursUp()) coloursPoll(); }

// ------------------------------------------------------------------ the Appearance page (layer 8)
// Opened by "ldrc appearance" (Transmitter setup). Its buttons open the main board's background picture page (its own
// button on Transmitter setup, pressed for the pilot), the Themes page, the front screen's setup, and its help (on the
// main board, as every page's). When it goes and comes back: lib/LdrcTheme (AppearancePage::poll), tested on the Mac.
static const int APPEARANCE_WHO = 8;
static ldrc::AppearancePage appearance;
static uint32_t appearanceTouchedAt = 0;
static bool appearanceUp() { return topOn && topWho == APPEARANCE_WHO; }
static void appearanceTouch(bool pressed, int x, int y, uint32_t now) {
    static uint32_t lastDown = 0;
    if (pressed) { lastDown = now; appearanceTouchedAt = now; }
    if (touchLockout) { if (!pressed && (int32_t) (now - lastDown) > 80) touchLockout = false; return; }   // (the finger that changed the page)
    appearance.touch(pressed, x, y, now);
}
static ldrc::AppearanceWorld appearanceWorld(uint32_t now) {
    ldrc::AppearanceWorld w;
    w.page = page.name; w.coloursBusy = coloursRequested || colours.isOpen(); w.frontBusy = flightRequested || flight.setupOpen();
    w.otherUp = updShowing() || wifiPage.showing(); w.armed = armedNow; w.now = now;
    return w;
}
static void appearancePoll() {
    static uint32_t lastBuild = 0, lastPoke = 0; static bool wasUp = false; static std::map<int, uint32_t> drawn; static uint32_t drawnLayout = 0;
    const uint32_t now = millis();
    if (appearanceRequested) { appearanceRequested = false; if (appearance.request(appearanceWorld(now))) appearanceTouchedAt = now; }
    appearance.poll(appearanceWorld(now));
    int handOff = ldrc::APP_NONE;
    const bool mainBoardFree = page.name == appearance.over() && !teensyLink.running();   // (its pages are asked for with words to it: not during an update)
    switch (const int act = appearance.takeAction()) {
    case ldrc::APP_BACKGROUND:                                  // the main board's own page: its button on Transmitter setup, pressed for the pilot
        if (Comp *c = find("b7")) if (mainBoardFree) { runScript(c->evRelease, c->name); appearance.handOff(act, now); }
        break;
    case ldrc::APP_HELP:
        if (mainBoardFree) { runScript("print \"HelpView:APPEAR.TXT\"\nLogView.t0.txt=\"Appearance help\"\nLogView.return.txt=\"TXSetupView\"", ""); appearance.handOff(act, now); }
        break;
    case ldrc::APP_COLOURS: coloursRequested = true; appearance.handOff(act, now); handOff = act; break;
    case ldrc::APP_FRONT: flightRequested = true; appearance.handOff(act, now); handOff = act; break;
    case ldrc::APP_BACK: appearance.close(); break;
    default: break;
    }
    const bool layerFree = !topOn || topWho == APPEARANCE_WHO, blank = page.name == "BlankView";
    const bool up = appearance.isOpen() && layerFree && !blank && topReady();
    if (up) {
        // (the main board cannot see touches on our pages: its screen saver is told someone is here, as the other pages of ours tell it)
        if (now - appearanceTouchedAt < 180000 && now - lastPoke > 20000 && !teensyLink.running()) { lastPoke = now; flushOut(); Serial.write((const uint8_t *) "UKRULES", 7); }
        if (wasUp && now - lastBuild < 50) return;
        lastBuild = now;
        const ldrc::AppearanceScene &sc = appearance.scene();
        if (!wasUp || sc.layout != drawnLayout) {
            { TopDraw on; appearanceDrawAll(sc, theme); }
            drawn.clear(); for (auto &t : sc.tiles) drawn[t.id] = t.serial;
            drawnLayout = sc.layout;
            topX = 0; topY = 0; topW = W; topH = H; topWho = APPEARANCE_WHO; topOn = true;
            dirty(0, 0, W, H); touchPainted = true;
        } else {
            for (auto &t : sc.tiles) {
                auto d = drawn.find(t.id); if (d != drawn.end() && d->second == t.serial) continue;
                { TopDraw on; themeDrawTile(t, theme); }
                drawn[t.id] = t.serial; dirty(t.r.x, t.r.y, t.r.w, t.r.h); touchPainted = true;
            }
        }
    } else if (wasUp) {
        if (topWho == APPEARANCE_WHO) { topOn = false; topWho = 0; }
        dirty(0, 0, W, H); touchPainted = true;
        drawn.clear(); drawnLayout = 0;
    }
    wasUp = up;
    if (handOff == ldrc::APP_COLOURS) coloursPoll();            // the page it opens, drawn in this same pass: no glimpse of Transmitter setup between
    else if (handOff == ldrc::APP_FRONT) flightPoll();
}
static void appearancePageLoaded() { if (appearance.isOpen() || appearance.waiting() || appearanceUp()) appearancePoll(); }
