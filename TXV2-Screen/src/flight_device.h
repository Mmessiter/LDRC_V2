// The flight screen on the transmitter (lib/LdrcFlight does the thinking, src/flight_draw.h the drawing): on our own
// layer over the front page while flying, and its setup page over Transmitter setup ("ldrc flight"). The pilot's
// choice is kept in the chip (preferences "flight"), written when the wire is quiet. Nothing goes to the main board but
// the touch word that keeps its screen saver away while the flight screen shows (if the pilot asked for that).
// Included by main.cpp after pics_device.h.
#include "flight_source.h"
#include "flight_draw.h"

static const int FLIGHT_WHO = 5, FLIGHT_SETUP_WHO = 6;         // the layer's owners (main.cpp topWho: 1 to 4 are the other pages of ours)
static ldrc::FlightScreen flight;
static ScreenFront flightSrc;
static uint32_t flightTouchedAt = 0;
static bool flightSaveWanted = false; static uint32_t flightSaveAt = 0;
static std::string flightSetupOver;                             // the page the setup page was opened over: it goes when the main board leaves it

static bool flightUp() { return topOn && (topWho == FLIGHT_WHO || topWho == FLIGHT_SETUP_WHO); }
// The six definitions (1.10.0): "flight" is slot 1 (as the one definition of 1.6.0-1.9.15 was kept, so an update keeps
// it), "flight2".."flight6" the others, "flightSlot" the one in use.
static std::string flightKey(int k) { return k == 0 ? std::string("flight") : "flight" + std::to_string(k + 1); }
static void flightLoad() {
    for (int k = 0; k < ldrc::FlightScreen::FLIGHT_SLOTS; ++k) {
        const std::string s = prefs.getString(flightKey(k).c_str(), "").c_str();
        if (!s.empty() && !flight.loadSlot(k, s)) blog("flight", "setting not understood: " + s);
    }
    flight.setSlotInUse(prefs.getInt("flightSlot", 0));
}
static void flightStore() {
    for (int k = 0; k < ldrc::FlightScreen::FLIGHT_SLOTS; ++k) {
        const std::string s = flight.slotConfig(k).save();
        if (std::string(prefs.getString(flightKey(k).c_str(), "").c_str()) != s) prefs.putString(flightKey(k).c_str(), s.c_str());
    }
    if (prefs.getInt("flightSlot", 0) != flight.slotInUse()) prefs.putInt("flightSlot", flight.slotInUse());
}
static void flightTouch(bool pressed, int x, int y, uint32_t now) {
    static uint32_t lastDown = 0;
    if (pressed) { flightTouchedAt = now; lastDown = now; }
    if (touchLockout) {                                         // the finger that changed the page, or woke the screen, is still down: it is not for us
        if (!pressed && (int32_t) (now - lastDown) > 80) touchLockout = false;
        return;
    }
    flight.touch(pressed, x, y, now);
    std::string comp;
    if (flight.takeFrontPress(comp) && page.name == "FrontView" && !teensyLink.running()) {   // "Transmitter setup", "Model setup": the front page's own button, pressed for the pilot
        if (comp == "help") runScript("print \"HelpView:FLIGHT.TXT\"\nLogView.t0.txt=\"Front screen help\"\nLogView.return.txt=\"FrontView\"", "");   // (as the front page's Help asks for FRONT.TXT)
        else if (Comp *c = find(comp)) { runScript(c->evPress, c->name); runScript(c->evRelease, c->name); }   // (the main board hears what it always hears, and shows its page)
    }
}
static void flightPoll() {
    static uint32_t drawnLayout = 0, lastBuild = 0, lastPoke = 0; static int wasWho = 0;
    static std::map<int, uint32_t> drawn; static std::string drawnStrip;
    const uint32_t now = millis();
    if (flightRequested) {
        flightRequested = false;
        if (!updShowing() && !wifiPage.showing() && !flight.setupOpen()) { flight.openSetup(); flightSetupOver = page.name; flightTouchedAt = now; }
    }
    // The setup page goes (what was chosen is kept) when the main board leaves the page it was over (a message, the
    // power-off countdown), when another page of ours is asked for, and when flying begins (the flight screen comes).
    if (flight.setupOpen() && ((page.name != flightSetupOver && page.name != "BlankView") || updShowing() || wifiPage.showing() || armedNow)) flight.closeSetup();
    if (flightDefinedRequested) { flightDefinedRequested = false; if (page.name == "FrontView") flight.useDefined(); }   // the front page's "Defined screen"
    const bool blank = page.name == "BlankView";                // the main board has put the screen out (its screen saver, switching off): nothing of ours over that
    const bool layerFree = !topOn || topWho == FLIGHT_WHO || topWho == FLIGHT_SETUP_WHO, front = page.name == "FrontView";
    // The power-off countdown ("TURN OFF?! 3", the power button held with a model connected) must be seen: the main board
    // writes it once a second while the button is held, and the flight screen stands aside until 1.5 s after the last one.
    // (not "while the box shows it": the words stay there when the button is let go, and a main board before B24 writes
    // the current into the same box between its seconds)
    const bool countdown = flightCountdownAt && now - flightCountdownAt < 1500;
    const bool blocked = blank || !layerFree || updShowing() || wifiPage.showing() || picPanelUp() || countdown;
    flight.poll(now, front, tx.armed, blocked);
    if ((flight.showing() || (flight.setupOpen() && !blank && layerFree)) && !topReady()) {   // (the layer's memory is taken only when it is wanted: none, no flight screen)
        if (flight.setupOpen()) flight.closeSetup();
        flight.poll(now, front, tx.armed, true);
    }
    if (flight.takeSaved()) { flightSaveWanted = true; flightSaveAt = now; }
    if (flightSaveWanted) {                                     // (a flash write stalls the chip: when the wire is quiet, and never in flight)
        if (teensyLink.running() || armedNow) flightSaveAt = now;   // (held back: the wait starts again when it may be written)
        else if ((int32_t) (now - lastRxMs) > 300 || now - flightSaveAt > 3000) {
            flightSaveWanted = false;
            flightStore();
        }
    }
    const int who = !layerFree || blank ? 0 : flight.setupOpen() ? FLIGHT_SETUP_WHO : flight.showing() ? FLIGHT_WHO : 0;
    if (who) {
        if (who == wasWho && now - lastBuild < 50) return;      // twenty times a second is plenty: the main board writes the front page ten times a second
        lastBuild = now;
        flight.themeFace = theme.panel(); flight.themeInk = theme.ink();   // the screens' theme, and the twelve on offer (a box's choice)
        for (int k = 0; k < ldrc::THEME_COUNT; ++k) { flight.palPanels[k] = theme.panels[k]; flight.palInks[k] = theme.inks[k]; }
        const ldrc::FlightScene &sc = flight.scene(flightSrc, &flightFonts);
        const std::string strip = sc.title + "|" + sc.left + "|" + sc.middle + "|" + sc.right + "|" + sc.hint + "|" + sc.alert;
        if (who != wasWho || sc.layout != drawnLayout) {
            { TopDraw on; flightDrawAll(sc); }
            drawn.clear();
            for (auto &t : sc.tiles) drawn[t.id] = t.serial;
            for (auto &b : sc.buttons) drawn[b.id] = b.serial;
            drawnLayout = sc.layout; drawnStrip = strip;
            topX = 0; topY = 0; topW = W; topH = H; topWho = who; topOn = true;
            dirty(0, 0, W, H); touchPainted = true;
        } else {
            if (strip != drawnStrip) {
                { TopDraw on; flightDrawStrip(sc); }
                drawnStrip = strip; dirty(0, 0, W, sc.setup ? ldrc::FLIGHT_SETUP_STRIP + 33 : ldrc::FLIGHT_STRIP); touchPainted = true;
                for (auto &b : sc.buttons) if (b.r.y < (sc.setup ? ldrc::FLIGHT_SETUP_STRIP + 33 : ldrc::FLIGHT_STRIP)) drawn.erase(b.id);   // (the strip was painted over the Help button: it goes on again below)
            }
            if (flPicRetryDue(now)) for (auto &t : sc.tiles) if (!t.v.image.empty()) drawn.erase(t.id);   // (a picture that would not come: its boxes drawn again, which asks the card again)
            for (auto &t : sc.tiles) {
                auto d = drawn.find(t.id); if (d != drawn.end() && d->second == t.serial) continue;
                { TopDraw on; flightDrawTile(t, sc.setup); }
                drawn[t.id] = t.serial; dirty(t.r.x, t.r.y, t.r.w, t.r.h); touchPainted = true;
            }
            for (auto &b : sc.buttons) {
                auto d = drawn.find(b.id); if (d != drawn.end() && d->second == b.serial) continue;
                { TopDraw on; flightDrawButton(b); }
                drawn[b.id] = b.serial; dirty(b.r.x, b.r.y, b.r.w, b.r.h); touchPainted = true;
            }
        }
        // Someone is here: the setup page while it is being used, the flight screen if the pilot asked ("Stays lit"). The
        // main board cannot see touches on our pages: its screen saver is told, as the update panel and the WiFi page tell it.
        // (with no model connected, and none a minute ago, nothing is said: the word also resets the main board's
        // switch-off-when-unused timer, and a transmitter left on the bench with the flight screen "always" up must still
        // switch itself off. A link lost in flight keeps it lit: the strip says NO LINK.)
        const bool modelNear = flightSrc.linked() || tx.armed || (txStatus >= 0 && (txStatus & TX_MODEL_JUST_NOW));
        const bool poke = who == FLIGHT_SETUP_WHO ? now - flightTouchedAt < 180000 : flight.cfg.stayOn && modelNear;
        if (poke && now - lastPoke > 20000 && !teensyLink.running()) { lastPoke = now; flushOut(); Serial.write((const uint8_t *) "UKRULES", 7); }
    } else if (wasWho) {
        flPicForget();                                          // (the model's picture: read afresh next time)
        if (topWho == wasWho) { topOn = false; topWho = 0; }    // (unless another page of ours has the layer now)
        dirty(0, 0, W, H); touchPainted = true;                 // the page, as the main board has drawn it meanwhile (a page of ours in our place covers less of the glass)
        drawn.clear(); drawnLayout = 0;
    }
    wasWho = who;
}
static void flightPageLoaded() { if (page.name == "FrontView" || flight.setupOpen() || flightUp()) flightPoll(); }
