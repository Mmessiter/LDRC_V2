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
    flight.startWithSlot(prefs.getInt("flightSlot", 0));      // (1.11.33: with its own stored Original / Defined choice)
    // (1.11.69) the choice of the moment has a key of its own: the definitions' copies of it (" m:") are what an older screen
    // reads, and are no longer written again at every switch
    const uint8_t m = prefs.getUChar("flightMan", 0);
    if (m == ldrc::FM_ORIGINAL || m == ldrc::FM_DEFINED) flight.cfg.manual = m;
}
// (1.11.69) Writing the flash takes the PSRAM from the panel while it lasts: the picture slips sideways. The switch between
// the original and defined front screens did that every time - all six definitions written again (~24 flash entries) only
// because each carries the choice - and no other page change writes the flash: the flicker that only this switch had. Now
// the choice is one byte of its own, a definition is written only when it really changed (the setup page), and the writing
// starts just after the panel's frame end, in the blank before its next picture.
static void flightStore() {
    std::vector<std::pair<std::string, std::string>> todo;
    for (int k = 0; k < ldrc::FlightScreen::FLIGHT_SLOTS; ++k) {
        const std::string s = flight.slotToStore(k), old = prefs.getString(flightKey(k).c_str(), "").c_str();
        if (old == s) continue;
        ldrc::FlightConfig was, now;
        if (!old.empty() && was.load(old) && now.load(s)) { was.manual = now.manual; if (was == now) continue; }   // (only the choice differs: it has its own key)
        todo.push_back({ flightKey(k), s });
    }
    const bool slotNew = prefs.getInt("flightSlot", 0) != flight.slotInUse(), manNew = prefs.getUChar("flightMan", 0) != flight.manualChoice();
    if (todo.empty() && !slotNew && !manNew) return;
    quietAtFrameEnd();
    const uint32_t t0 = micros();
    if (manNew) prefs.putUChar("flightMan", flight.manualChoice());   // (first: the switch's one byte, in the blank)
    if (slotNew) prefs.putInt("flightSlot", flight.slotInUse());
    for (auto &kv : todo) prefs.putString(kv.first.c_str(), kv.second.c_str());
    const uint32_t us = micros() - t0; quietStoreN++; if (us > quietStoreMax) quietStoreMax = us;
}
static void flightTouchCancel() { flight.cancelTouch(); }   // (B59) a corner held: not a press
static void flightTouch(bool pressed, int x, int y, uint32_t now) {
    static uint32_t lastDown = 0;
    if (pressed) { flightTouchedAt = now; lastDown = now; }
    if (touchLockout) {                                         // the finger that changed the page, or woke the screen, is still down: it is not for us
        if (!pressed && (int32_t) (now - lastDown) > 80) touchLockout = false;
        return;
    }
    const bool setupBefore = flight.setupOpen();
    flight.touch(pressed, x, y, now);
    if (!setupBefore && flight.setupOpen()) { flightSetupOver = page.name; flightTouchedAt = now; }   // opened by a long press on a box (1.10.2): over the page that is there
    std::string comp;
    if (flight.takeFrontPress(comp) && page.name == "FrontView" && !teensyLink.running()) {   // "Transmitter setup", "Model setup": the front page's own button, pressed for the pilot
        if (comp == "help") runScript("print \"HelpView:FLIGHT.TXT\"\nLogView.t0.txt=\"Defined front screen help\"\nLogView.return.txt=\"FrontView\"", "");   // (as the front page's Help asks for FRONT.TXT)
        else if (Comp *c = find(comp)) { runScript(c->evPress, c->name); runScript(c->evRelease, c->name); }   // (the main board hears what it always hears, and shows its page)
    }
}
static void flightPoll() {
    static uint32_t drawnLayout = 0, lastBuild = 0, lastPoke = 0; static int wasWho = 0;
    static bool flightDrawWaits = false; static QuietJob flightDrawJob;   // (1.11.67) a whole drawing waiting for the panel's quiet time
    static std::map<int, uint32_t> drawn; static std::string drawnStrip;
    // (1.11.68) What the layer holds while the defined screen is not showing is kept, and shown as it is next time - unless
    // another page of ours has drawn there since (topEpoch), the theme has changed, or it was another screen (the setup page).
    static int keptWho = 0; static uint32_t keptEpoch = 0; static uint16_t keptFace = 0, keptInk = 0;
    static size_t tileFrom = 0;                                 // (the boxes drawn again: two a pass at most, in turn)
    static int warm = -1; static uint32_t warmLayout = 0, warmEpoch = 0, warmAt = 0;   // (the defined screen drawn ahead, a piece at a time)
    static std::map<int, uint32_t> warmDrawn; static std::string warmStrip, onPage; static uint32_t onPageSince = 0;
    auto useTheme = [&]() {                                     // the screens' theme, and the twelve on offer (a box's choice)
        flight.themeFace = theme.panel(); flight.themeInk = theme.ink();
        for (int k = 0; k < ldrc::THEME_COUNT; ++k) { flight.palPanels[k] = theme.panels[k]; flight.palInks[k] = theme.inks[k]; }
    };
    auto stripOf = [](const ldrc::FlightScene &sc) { return sc.title + "|" + sc.left + "|" + sc.middle + "|" + sc.right + "|" + sc.hint + "|" + sc.alert; };
    auto keptFor = [&](int w) { return topFb && keptWho == w && topEpoch == keptEpoch && keptFace == theme.panel() && keptInk == theme.ink(); };
    auto keep = [&](int w) { keptWho = w; keptEpoch = topEpoch; keptFace = theme.panel(); keptInk = theme.ink(); };
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
        if (who == wasWho && !flightDrawWaits && now - lastBuild < 50) return;   // twenty times a second is plenty: the main board writes the front page ten times a second
        lastBuild = now; warm = -1;                             // (a drawing ahead stops: the screen itself is wanted)
        useTheme();
        const ldrc::FlightScene &sc = flight.scene(flightSrc, &flightFonts);
        const std::string strip = stripOf(sc);
        bool whole = false;
        if (who != wasWho && keptFor(who) && sc.layout == drawnLayout) {
            // (1.11.68) the layer still holds this screen as it was left, or as it was drawn ahead: shown at once, in the
            // panel's quiet time, as every other page is; what has changed since is drawn below, two boxes a pass
            topX = 0; topY = 0; topW = W; topH = H; topWho = who; topOn = true;
            dirty(0, 0, W, H); touchPainted = true; quietSwitch = QUIET_SWITCH; quietKeptN++;
        } else if (who != wasWho || sc.layout != drawnLayout) {
            // (1.11.67) the whole screen is drawn afresh in the panel's quiet time (src/main.cpp quietTurn), and copied to the
            // glass in the next: the fill and every box are PSRAM traffic that took scan time from the picture being shown.
            // (1.11.68: only when nothing is kept - the first time, or after another page of ours had the layer)
            if (QUIET_SWITCH && !quietTurn(flightDrawJob)) { flightDrawWaits = true; return; }
            flightDrawWaits = false;
            const uint32_t d0 = micros();
            { TopDraw on; flightDrawAll(sc); }
            quietDone(flightDrawJob, micros() - d0, true);
            drawn.clear();
            for (auto &t : sc.tiles) drawn[t.id] = t.serial;
            for (auto &b : sc.buttons) drawn[b.id] = b.serial;
            drawnLayout = sc.layout; drawnStrip = strip;
            topX = 0; topY = 0; topW = W; topH = H; topWho = who; topOn = true;
            dirty(0, 0, W, H); touchPainted = true; quietSwitch = QUIET_SWITCH; quietFullN++; whole = true;
        }
        if (!whole) {
            if (strip != drawnStrip) {
                { TopDraw on; flightDrawStrip(sc); }
                drawnStrip = strip; dirty(0, 0, W, sc.setup ? ldrc::FLIGHT_SETUP_STRIP + 33 : ldrc::FLIGHT_STRIP); touchPainted = true;
                for (auto &b : sc.buttons) if (b.r.y < (sc.setup ? ldrc::FLIGHT_SETUP_STRIP + 33 : ldrc::FLIGHT_STRIP)) drawn.erase(b.id);   // (the strip was painted over the Help button: it goes on again below)
            }
            if (flPicRetryDue(now)) for (auto &t : sc.tiles) if (!t.v.image.empty()) drawn.erase(t.id);   // (a picture that would not come: its boxes drawn again, which asks the card again)
            // (1.11.68) two boxes a pass at most, in turn: a box takes up to 20 ms, and a long run of drawing is what the
            // panel shows as a flicker (the others wait 50 ms, for the next pass)
            const size_t nT = sc.tiles.size(); int redrawn = 0;
            for (size_t k = 0; k < nT && redrawn < 2; ++k) {
                const size_t i = (tileFrom + k) % nT; const ldrc::FlightTile &t = sc.tiles[i];
                auto d = drawn.find(t.id); if (d != drawn.end() && d->second == t.serial) continue;
                const uint32_t s0 = micros();
                { TopDraw on; flightDrawTile(t, sc.setup); }
                const uint32_t us = micros() - s0; if (us > quietStepMax) quietStepMax = us;
                drawn[t.id] = t.serial; dirty(t.r.x, t.r.y, t.r.w, t.r.h); touchPainted = true;
                if (++redrawn == 2) tileFrom = (i + 1) % nT;
            }
            for (auto &b : sc.buttons) {
                auto d = drawn.find(b.id); if (d != drawn.end() && d->second == b.serial) continue;
                { TopDraw on; flightDrawButton(b); }
                drawn[b.id] = b.serial; dirty(b.r.x, b.r.y, b.r.w, b.r.h); touchPainted = true;
            }
        }
        keep(who);                                              // (the layer holds this screen, as drawn so far)
        // Someone is here: the setup page while it is being used, the flight screen if the pilot asked ("Stays lit"). The
        // main board cannot see touches on our pages: its screen saver is told, as the update panel and the WiFi page tell it.
        // (with no model connected, and none a minute ago, nothing is said: the word also resets the main board's
        // switch-off-when-unused timer, and a transmitter left on the bench with the flight screen "always" up must still
        // switch itself off. A link lost in flight keeps it lit: the strip says NO LINK.)
        const bool modelNear = flightSrc.linked() || tx.armed || (txStatus >= 0 && (txStatus & TX_MODEL_JUST_NOW));
        const bool poke = who == FLIGHT_SETUP_WHO ? now - flightTouchedAt < 180000 : flight.cfg.stayOn && modelNear;
        if (poke && now - lastPoke > 20000 && !teensyLink.running()) { lastPoke = now; flushOut(); Serial.write((const uint8_t *) "UKRULES", 7); }
    } else if (wasWho) {
        flPicForget();                                          // (the model's picture: read afresh next time it is drawn)
        if (topWho == wasWho) { topOn = false; topWho = 0; }    // (unless another page of ours has the layer now)
        dirty(0, 0, W, H); touchPainted = true;                 // the page, as the main board has drawn it meanwhile (a page of ours in our place covers less of the glass)
        if (topWho == 0) quietSwitch = QUIET_SWITCH;            // (back to the main board's own page; 1.11.67-68: in the panel's quiet time)
        // (1.11.68: drawn, drawnLayout and drawnStrip stay, with the layer's picture: the screen as it was left, for next time)
    } else {
        // (1.11.68) While the main board's own front page shows, the defined screen is drawn behind it on the layer, a piece
        // at a time 30 ms apart - the ground in eight bands, the strip, each box, the buttons - so that the switch to it is
        // only the copy, as every other page change is (Malcolm, of 1.11.67: "All of the other screen changes are just fine
        // ... Maybe we should simply use the other method?"). Drawn whole at the switch it took 0.21 s, and the panel showed
        // that as a flicker. Not while flying, nor while anything else has the layer, nor in the first 1.5 s on the page.
        if (page.name != onPage) { onPage = page.name; onPageSince = now; }
        const bool calm = page.name == "FrontView" && !topOn && topWho == 0 && !flight.setupOpen() && !updShowing() && !wifiPage.showing()
                          && !teensyLink.running() && !armedNow && now - onPageSince > 1500 && now - warmAt >= 30;
        if (calm && !keptFor(FLIGHT_WHO) && topReady()) {
            warmAt = now;
            useTheme();
            const ldrc::FlightScene &sc = flight.scene(flightSrc, &flightFonts);
            if (!sc.setup) {
                if (warm < 0 || sc.layout != warmLayout || topEpoch != warmEpoch) { warm = 0; warmLayout = sc.layout; warmDrawn.clear(); flPicForget(); }
                const int bands = 8, nT = (int) sc.tiles.size(); bool done = false;
                const uint32_t s0 = micros();
                {
                    TopDraw on;
                    if (warm < bands) { const int y0 = warm * H / bands, y1 = (warm + 1) * H / bands; gfx->fillRect(0, y0, W, y1 - y0, FL_GROUND); }
                    else if (warm == bands) { flightDrawStrip(sc); warmStrip = stripOf(sc); }
                    else if (warm - bands - 1 < nT) { const ldrc::FlightTile &t = sc.tiles[warm - bands - 1]; flightDrawTile(t, false); warmDrawn[t.id] = t.serial; }
                    else { for (auto &b : sc.buttons) { flightDrawButton(b); warmDrawn[b.id] = b.serial; } done = true; }
                }
                const uint32_t us = micros() - s0; if (us > quietStepMax) quietStepMax = us;
                ++warm; warmEpoch = topEpoch;
                if (done) { drawn = warmDrawn; drawnLayout = warmLayout; drawnStrip = warmStrip; keep(FLIGHT_WHO); warm = -1; quietWarmN++; }
            }
        }
    }
    if (!who) flightDrawWaits = false;                          // (a drawing that was waiting and is no longer wanted)
    wasWho = who;
}
static void flightPageLoaded() { if (page.name == "FrontView" || flight.setupOpen() || flightUp()) flightPoll(); }
