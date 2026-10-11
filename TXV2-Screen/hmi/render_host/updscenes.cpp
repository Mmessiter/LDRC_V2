// The update panel's states for the renderer ("@update STATE", "@rxupdate STATE"), made by the REAL Updater
// (lib/LdrcUpdate) driven through the host tests' make-believe website, card and Teensy (hmi/test_update, whose
// Teensy runs the real LinkServer). What the panel says is therefore what the screen would say; own.h draws it with
// the screen's own updDrawPanel. A translation unit of its own: the tests' names stay out of the renderer's.
#define main test_update_main
#include "../test_update/test_update.cpp"
#undef main

// Realistic releases (the names are in the shape TXV1B dev/release_v1b.py gives them, 10-10-2026).
static const char *TX_OLD = "2.5.6 B92 10/10/26", *TX_NEW = "2.5.6 B93 11/10/26";
static Release relOld() {
    Release r = releaseOf("V2 B92 (screen 1.11.56) front page V2, picture back after updates", TX_OLD, "1.11.56", 0);
    r.notes = "Front page title says LockDownRadioControl V2. After an update restarts the screen, the front page shows the model's picture again.";
    return r;
}
static Release relNew() {
    Release r = releaseOf("V2 B93 (screen 1.11.57) clearer help pages", TX_NEW, "1.11.57", 1);
    r.notes = "Help pages rewritten in plainer words. The WiFi page and the update panel tidied.";
    return r;
}
static Release relOlder() {
    Release r = releaseOf("V2 B91 (screen 1.11.56) Black box answers in full", "2.5.6 B91 10/10/26", "1.11.56", 0);
    r.notes = "Black box page: When, Where, How often and the memory line now show their words in full.";
    r.screenFiles["/hmi/pages/33.json"] = blob(4100, 556);
    return r;
}
// until the view's title starts with `title` (and, if want > 0, its bar is that far, in thousandths)
static bool untilTitle(Bench &b, const char *title, uint32_t limit, int want = 0) {
    const uint32_t end = nowMs + limit;
    for (; nowMs < end; b.step()) {
        const UpdView &v = b.upd->view();
        if (v.title.rfind(title, 0) != 0) continue;
        if (want <= 0) return true;
        if (v.bar && v.barTotal && (uint64_t) v.barDone * 1000 >= (uint64_t) v.barTotal * (uint64_t) want) return true;
    }
    return false;
}
static bool untilLine(Bench &b, const char *text, uint32_t limit) {
    const uint32_t end = nowMs + limit;
    for (; nowMs < end; b.step()) if (b.has(text)) return true;
    return false;
}
static void offer(Bench &b) { b.run(3000); b.upd->begin(); b.untilKind(UpdView::OFFER, 30000); }
static void rxBench(Bench &b, uint32_t rx = 0x00090374u) {      // a model connected whose receiver runs 0.9.884; the website has 0.9.885
    install(b, relOld()); publish(b.site, relOld()); publishReceivers(b.site, "RXV2-0.9.885-quicker-bind", "Binding is quicker, and the receiver's own page shows the model's name.");
    b.host.model = true; b.host.rxRelease = rx;
}

// The states. Returns false (and why) if the state is not known or was not reached.
bool updScene(const std::string &name, UpdView &out, std::string &why) {
    Bench b; install(b, relOld()); publish(b.site, relNew());
    bool ok = true;
    if (name == "checking") { b.run(3000); b.upd->begin(); b.run(200); }
    else if (name == "checking_teensy") { b.run(3000); b.upd->begin(); ok = untilLine(b, "transmitter", 20000) || untilLine(b, "Asking", 20000); }
    else if (name == "uptodate") { publish(b.site, relOld()); b.run(3000); b.upd->begin(); ok = b.untilVerdict(30000) && b.has("Up to date"); }
    else if (name == "offer") { offer(b); ok = b.upd->view().kind == UpdView::OFFER; }
    else if (name == "fetching") { b.site.bytesPerSecond = 60000; offer(b); b.upd->press(1); ok = untilLine(b, "Fetching 1 of", 120000) && untilTitle(b, "Fetching the update", 120000, 300); }
    else if (name == "copying") { offer(b); b.upd->press(1); ok = untilTitle(b, "Updating the transmitter", 400000) && untilLine(b, "Fetching /", 60000); }
    else if (name == "teensy") { offer(b); b.upd->press(1); ok = untilTitle(b, "Updating the transmitter", 400000) && untilLine(b, "Sending", 400000); for (int i = 0; i < 1500; ++i) b.step(); }
    else if (name == "trial") { offer(b); b.upd->press(1); ok = untilLine(b, "New firmware on trial", 400000); for (int i = 0; i < 2000; ++i) b.step(); }
    else if (name == "screenfiles") { offer(b); b.upd->press(1); ok = untilTitle(b, "Updating the screen", 400000); }
    else if (name == "screenflash") { offer(b); b.upd->press(1); ok = untilTitle(b, "Updating the screen", 400000) && untilLine(b, "Writing the screen's firmware", 400000); for (int i = 0; i < 1200; ++i) b.step(); }
    else if (name == "finishing") {
        offer(b); b.upd->press(1);
        { const uint32_t end = nowMs + 400000; while (nowMs < end && !b.host.restarted && b.upd->view().kind != UpdView::BAD) b.step(); }
        b.restartScreen(); b.run(50); ok = b.upd->view().title.rfind("Finishing", 0) == 0;
    }
    else if (name == "done") {
        offer(b); b.upd->press(1);
        { const uint32_t end = nowMs + 400000; while (nowMs < end && !b.host.restarted && b.upd->view().kind != UpdView::BAD) b.step(); }
        b.restartScreen(); ok = b.untilVerdict(120000) && b.upd->view().kind == UpdView::GOOD;
    }
    else if (name == "failed") {
        b.site.spoil = std::string(BASE) + "files/" + hex8(crcOf(relNew().teensyFiles.find("/help/RFGOVP.TXT")->second)) + "-4700.bin";
        offer(b); b.upd->press(1); ok = b.untilVerdict(400000) && b.upd->view().kind == UpdView::BAD;
    }
    else if (name == "cardfull") { b.host.freeKbNow = 3000; offer(b); b.upd->press(1); ok = b.untilVerdict(400000) && b.upd->view().kind == UpdView::BAD; }
    else if (name == "donotfly") {
        b.w.teensy.reads[TX_NEW] = 2; b.w.teensy.safetyDefined = true; b.host.safetyDefined = true;
        offer(b); b.upd->press(1);
        { const uint32_t end = nowMs + 400000; while (nowMs < end && b.w.master.stage() != "waiting for the transmitter to restart") b.step(); }
        b.w.teensy.safetyOff = true; b.host.safetyOff = true;
        UNTIL_END(b)
        ok = b.has("DO NOT FLY");
    }
    else if (name == "fellback") {                        // the new Teensy firmware falls over: the Teensy puts the old one back
        b.w.teensy.brokenNew = true; offer(b); b.upd->press(1); UNTIL_END(b) ok = b.upd->view().kind == UpdView::BAD || b.upd->view().kind == UpdView::GOOD;
    }
    else if (name == "noserver") { b.site.down = true; b.run(3000); b.upd->begin(); ok = b.untilVerdict(90000); }
    else if (name == "nowifi") { b.host.network = false; b.run(3000); b.upd->begin(); ok = b.untilVerdict(90000); }
    else if (name == "nowifiyet") { b.host.anyKnown = false; b.run(3000); b.upd->begin(); }
    else if (name == "motor") { b.host.motor = true; b.run(3000); b.upd->begin(); }
    else if (name == "safety") { b.host.safetyDefined = true; b.host.safetyOff = true; b.run(3000); b.upd->begin(); }
    else if (name == "model") { b.host.model = true; b.run(3000); b.upd->begin(); }
    else if (name == "modeljustnow") { b.host.modelJustNow = true; b.run(3000); b.upd->begin(); }
    else if (name == "room") { b.host.room = 17396; b.run(3000); b.upd->begin(); ok = untilTitle(b, "Restarting the screen first", 10000); }
    else if (name == "versions" || name == "installed" || name == "older" || name == "picking") {
        std::vector<Release> all; all.push_back(relOlder()); all.push_back(relOld()); all.push_back(relNew());
        Bench &c = b; install(c, relNew()); publishAll(c.site, all);
        c.run(3000); c.upd->begin(); c.untilVerdict(30000); c.upd->press(2);
        ok = c.untilKind(UpdView::CHOOSE, 30000);
        if (ok && name == "installed") { c.upd->press(10); ok = c.untilKind(UpdView::NOTE, 30000); }
        if (ok && name == "older") { c.upd->press(11); ok = c.untilKind(UpdView::OFFER, 30000); }
        if (ok && name == "picking") { c.upd->press(11); c.run(50); ok = c.upd->view().kind == UpdView::BUSY; }
    }
    else if (name == "again") {                           // "Install again" (the same release)
        publish(b.site, relOld()); b.run(3000); b.upd->begin(); b.untilVerdict(30000);
        ok = false; for (int k = 1; k <= 3 && !ok; ++k) { const UpdView &v = b.upd->view(); const std::string &l = k == 1 ? v.button1 : k == 2 ? v.button2 : v.button3; if (l.find("again") != std::string::npos) { b.upd->press(k); ok = b.untilKind(UpdView::OFFER, 30000); } }
        if (!ok) why = "no 'again' button on the Up to date panel";
    }
    // the receiver, through the main board
    else if (name == "rx_checking") { Bench c; rxBench(c); c.run(3000); c.upd->beginReceiver(); c.run(200); out = c.upd->view(); return true; }
    else if (name == "rx_offer") { Bench c; rxBench(c); c.run(3000); c.upd->beginReceiver(); ok = c.untilKind(UpdView::OFFER, 30000); out = c.upd->view(); if (!ok) why = "no offer"; return ok; }
    else if (name == "rx_working" || name == "rx_waiting") {
        Bench c; rxBench(c); c.run(3000); c.upd->beginReceiver(); c.untilKind(UpdView::OFFER, 30000); c.upd->press(1);
        c.run(name == "rx_working" ? 30000 : 95000); out = c.upd->view(); return true;
    }
    else if (name == "rx_done") { Bench c; rxBench(c); c.run(3000); c.upd->beginReceiver(); c.untilKind(UpdView::OFFER, 30000); c.upd->press(1); ok = c.untilVerdict(200000); out = c.upd->view(); return ok; }
    else if (name == "rx_uptodate") { Bench c; rxBench(c, 0x00090375u); c.run(3000); c.upd->beginReceiver(); ok = c.untilVerdict(30000); out = c.upd->view(); return ok; }
    else if (name == "rx_nomodel") { Bench c; rxBench(c); c.host.model = false; c.run(3000); c.upd->beginReceiver(); out = c.upd->view(); return true; }
    else if (name == "rx_noversion") { Bench c; rxBench(c, 0); c.run(3000); c.upd->beginReceiver(); ok = c.untilVerdict(30000); out = c.upd->view(); return ok; }
    else if (name == "rx_armed") { Bench c; rxBench(c); c.host.rxAnswer = 2; c.run(3000); c.upd->beginReceiver(); c.untilKind(UpdView::OFFER, 30000); c.upd->press(1); ok = c.untilVerdict(30000); out = c.upd->view(); return ok; }
    else if (name == "rx_nowifi") { Bench c; rxBench(c); c.host.rxAnswer = 3; c.run(3000); c.upd->beginReceiver(); c.untilKind(UpdView::OFFER, 30000); c.upd->press(1); ok = c.untilVerdict(30000); out = c.upd->view(); return ok; }
    else if (name == "rx_failed") { Bench c; rxBench(c); c.host.rxOutcome = 2; c.run(3000); c.upd->beginReceiver(); c.untilKind(UpdView::OFFER, 30000); c.upd->press(1); ok = c.untilVerdict(200000); out = c.upd->view(); return ok; }
    else if (name == "rx_noanswer") { Bench c; rxBench(c); c.host.rxAnswer = -1; c.run(3000); c.upd->beginReceiver(); c.untilKind(UpdView::OFFER, 30000); c.upd->press(1); ok = c.untilVerdict(30000); out = c.upd->view(); return ok; }
    else if (name == "rx_safety") { Bench c; rxBench(c); c.host.safetyDefined = true; c.host.safetyOff = true; c.run(3000); c.upd->beginReceiver(); out = c.upd->view(); return true; }
    else { why = "no such state"; return false; }
    out = b.upd->view();
    if (!ok && why.empty()) why = "not reached (the panel says: " + b.said() + ")";
    return ok;
}
// (for the record: everything the panel says, in one line)
std::string updSaid(const UpdView &v) {
    std::string s = v.title;
    for (size_t i = 0; i < v.choices.size(); ++i) s += " | (" + v.choices[i].name + (v.choices[i].current ? ", installed" : "") + ")";
    for (size_t i = 0; i < v.rows.size(); ++i) s += " | " + v.rows[i].what + ": " + v.rows[i].now + (v.rows[i].next.empty() ? "" : " -> " + v.rows[i].next);
    for (size_t i = 0; i < v.lines.size(); ++i) s += " | " + v.lines[i];
    if (!v.warning.empty()) s += " | (" + v.warning + ")";
    if (!v.hint.empty()) s += " | (" + v.hint + ")";
    if (!v.button1.empty()) s += " [" + v.button1 + "]";
    if (!v.button2.empty()) s += " [" + v.button2 + "]";
    if (!v.button3.empty()) s += " [" + v.button3 + "]";
    return s;
}
