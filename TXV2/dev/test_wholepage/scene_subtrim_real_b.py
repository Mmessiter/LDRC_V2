#!/usr/bin/env python3
"""THE REAL PAGE FILE, RUN BY THE SCREEN'S OWN INTERPRETER, UNDER THE SCREEN'S OWN TOUCH RULES, against the REAL Trims.h (B211; written by reviewer A of
the fourteenth review as his experiment - it found the slider's silent press - and taken into the suite with this release's page, 16 Nov 2026).

scene_subtrim / scene_subtrim_storm run Trims.h over a PRETEND page; scene_subtrim_page holds the pretend page against the page file's scripts. Here
nothing of the page is pretended: every script is the page FILE's, run by the screen project's lib/NextionScript. The screen (src/main.cpp pollTouch)
does this with a finger on the slider:
  - the finger LANDS: sliderTo() moves the slider (h0) to the finger, and the PRESS script runs (this release's page: the word. The page before had a
    comment there - no word, and a write of the main board's landing before the release undid the tap);
  - while it is down, every pass of the screen's loop: if 40 ms have gone since the last drag draw and the slider is not where the finger is, the slider
    is put there and the MOVE script runs (the word);
  - 80 ms after the finger has gone: the RELEASE script runs - always, whether anything moved or not (a word once more, often "from X to X").
Here those three are events of their own; "+", "-", Zero and the channels' taps run their release scripts; the board's "click rs,0" runs the part's
script; the page's load runs its preinitialize.

   python3 scene_realpage.py [--n trials] [--seed first] [--show]"""
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
import scene_subtrim as base
m = lib.m
LIBDIR = os.path.join(os.path.dirname(m.ROOT), 'ESP32-board2', 'board4', 'nextion-emulator', 'lib', 'NextionScript')
H, CPP = os.path.join(LIBDIR, 'NextionScript.h'), os.path.join(LIBDIR, 'NextionScript.cpp')
NEWPAGE = base.NEWPAGE
if not (os.path.exists(H) and os.path.exists(CPP)):
    # (the fifteenth review: this said "ALL GOOD". A scene that did not run says so, and the release's gate does not pass without it: dev/test_release_gate.py)
    print('NOT RUN: the screen project\'s script interpreter (lib/NextionScript) is not beside this repository - the real page file was run by nothing'); sys.exit(0)
assert base.page_kind(NEWPAGE) == 'new'
hdr = open(H, encoding='utf-8', errors='replace').read(); cpp = open(CPP, encoding='utf-8', errors='replace').read()
incs = sorted(set(re.findall(r'^\s*#\s*include\s*<[^>]+>', hdr + '\n' + cpp, re.M)))
cpp = re.sub(r'^\s*#\s*include\s*[<"][^>"]+[>"][^\n]*\n', '', cpp, flags=re.M); hdr = re.sub(r'^\s*#\s*include\s*<[^>]+>[^\n]*\n', '', hdr, flags=re.M)
def lit(s): return 'R"LDRC(' + s + ')LDRC"'
def page_cpp(path, name='rpLoadFile'):
    pg = json.load(open(path)); out = ['static void ' + name + '(RealPg &r)\n{\n    r.ev.clear(); r.has.clear(); r.pre = %s;\n' % lit((pg.get('ev') or {}).get('preinitialize', ''))]
    for c in pg['comps']:
        ev = c.get('ev') or {}
        for e in ('p', 'r', 'm'):
            if e in ev: out.append('    r.ev["%s.%s"] = %s;\n' % (c['n'], e, lit(ev[e])))
        out.append('    r.has.insert("%s");\n' % c['n'])
        if c['n'] == 'h0': out.append('    r.minval = %d; r.maxval = %d;\n' % ((c.get('a') or {}).get('minval', 0), (c.get('a') or {}).get('maxval', 100)))
    return ''.join(out) + '}\n'
EXTRA = base.EXTRA + '\n'.join(incs) + '\n#include <map>\n#include <set>\nnamespace realscript {\n' + hdr + '\n' + cpp + '\n}\n' + r'''
// ---- THE REAL PAGE: the page file's scripts run by the screen's interpreter; a part's number is the pretend screen's box of that name (so the board's
//      writes, which the pretend screen handles as the real one does, are what the scripts read)
struct RealPg : realscript::NextionHost
{
    std::map<std::string, std::string> ev; std::set<std::string> has; std::string pre; std::vector<uint8_t> out; int minval = 0, maxval = 254; long errors = 0; std::map<std::string, long> other;
    long &num(const std::string &c) { auto &bx = P().boxes; auto it = bx.find(c); if (it != bx.end()) return it->second.val; return other[c]; }
    int32_t getInt(const std::string &, const std::string &comp, const std::string &attr) override { return attr == "val" ? (int32_t) num(comp) : 0; }
    void setInt(const std::string &, const std::string &comp, const std::string &attr, int32_t v) override { if (attr == "val") num(comp) = v; }
    std::string getTxt(const std::string &, const std::string &) override { return ""; }
    void setTxt(const std::string &, const std::string &, const std::string &) override {}
    void send(const uint8_t *d, size_t n) override { out.insert(out.end(), d, d + n); }
    void click(const std::string &, const std::string &comp, bool press) override { if (has.count(comp)) run(comp + (press ? ".p" : ".r")); }
    void runCode(const std::string &code) { realscript::NextionScript s(*this, "SubTrimView"); if (!s.run(code)) { ++errors; printf("   the page's script did not run: %s (line %d)\n", s.lastError().c_str(), s.lastErrorLine()); } }
    void run(const std::string &what) { auto it = ev.find(what); if (it != ev.end()) runCode(it->second); }
};
''' + page_cpp(NEWPAGE) + page_cpp(base.PAGE, 'rpLoadOld') + r'''
static RealPg rp;
static uint32_t xs = 1; static uint32_t xr(uint32_t k) { xs = xs * 1664525u + 1013904223u; return k ? (xs >> 8) % k : 0; }
static std::deque<std::string> trail;
static void note(const char *f, ...) { char b[220]; va_list a; va_start(a, f); vsnprintf(b, sizeof b, f, a); va_end(a); char t[260]; snprintf(t, sizeof t, "%9.3f s  %s", nowUs / 1e6, b); trail.push_back(t); if (trail.size() > 90) trail.pop_front(); }
// THE FINGER on the slider (pollTouch): down?, where (the slider's value under it), when the slider was last drawn in a drag
static bool fDown = false; static int fPos = 127; static uint64_t fLastDrag = 0; static std::deque<int> fPath;
static int pUnheard = 0;                      // of 1000 words, how many never reach the board (lost on the wire)
static bool lossy = false; static long unheard9 = 0, bursts9 = 0, silent9 = 0, noChange9 = 0, tapsVanished9 = 0, saidBad9 = 0;
static long oks9 = 0, okStayed9 = 0, okSaved9 = 0, i5Bad = 0, i5Looked = 0, i5First9 = 0, firsts9 = 0, firstDoors9 = 0, longStalls9 = 0, wakeRounds9 = 0; static std::string i5First;
struct OkPress { long shown[16]; bool finger[16]; bool lossy; uint16_t drops; };   // what the page showed as an OK was pressed (each press its own: they are served in their order)
static std::deque<OkPress> okPresses;
static int clampSl(int v) { return v < rp.minval ? rp.minval : v > rp.maxval ? rp.maxval : v; }
static void rpTap(const char *button)
{
    if (screen.page != "SubTrimView") { fDown = false; return; }
    const std::string b = button; const long s0b = B("s0"), n0b = B("n0");
    if (b == "ok") { OkPress p; for (int c = 0; c < 16; ++c) { p.shown[c] = B(boxOf(c + 1)); p.finger[c] = byFinger[c + 1]; } p.lossy = lossy; p.drops = PendingDropped; okPresses.push_back(p); note("OK is pressed"); return; }
    rp.out.clear();
    if (b.rfind("ch", 0) == 0) rp.click("", boxOf(atoi(b.c_str() + 2)), false);          // a channel's number tapped: its release script
    else if (b == "plus") rp.run("b0.r");
    else if (b == "minus") rp.run("b1.r");
    else if (b == "zero") rp.run("b2.r");
    else if (b == "fdown")
    {   // the finger lands on the slider: the slider goes to it, and the press script runs (this release's: the word; the page before: a comment - nothing said, n0 stays)
        if (!fPath.empty()) { fPos = fPath.front(); fPath.pop_front(); }
        fDown = true; const int v = clampSl(fPos); if (v != B("h0")) B("h0") = v;
        rp.run("h0.p"); if (rp.out.empty()) ++silent9;
    }
    else if (b == "fmove") { if (!fPath.empty()) { fPos = fPath.front(); fPath.pop_front(); } }
    else if (b == "fpoll")
    {   // a pass of the screen's loop with the finger down: 40 ms since the last drag draw, and the slider not under the finger - it is put there, and the move script runs
        if (fDown && screen.at - fLastDrag > 40000) { const int v = clampSl(fPos); if (v != B("h0")) { B("h0") = v; fLastDrag = screen.at; rp.run("h0.m"); } }
    }
    else if (b == "fup") { if (fDown) { fDown = false; rp.run("h0.r"); } }            // 80 ms after the finger has gone: the release script, always
    if (rp.out.empty()) return;
    ++bursts9;
    if (rp.out.size() == SUBTRIM_WORD_BYTES && pageNew)
    {
        const std::vector<uint8_t> want = stSaid(s0b, n0b, B("n0"));
        if (want != rp.out) ++saidBad9;                                                   // the burst says: the channel, the number as it stood, the number it made, and that again - exactly
        touches.push_back({ (int) s0b, n0b, B("n0"), pageShowsModel ? modelEpoch : -1 });
        if (n0b == B("n0")) ++noChange9; else if (s0b >= 1 && s0b <= 16) byFinger[s0b] = true;                 // (a number a finger made stands in that channel's box)
        note("%s on channel %ld: %ld -> %ld", button, s0b, n0b, B("n0"));
    }
    else note("%s: the page on channel %ld (it said %d bytes)", button, B("s0"), (int) rp.out.size());
    if (pUnheard && xr(1000) < (uint32_t) pUnheard) { ++unheard9; lossy = true; note("   (that word NEVER HEARD)"); rp.out.clear(); return; }
    screen.burst(screen.at, rp.out); rp.out.clear();
}
static int pLose = 0; static long lostWrites = 0;
static bool rpCmd(const char *c)
{
    const bool click = !strcmp(c, "click rs,0");
    if (!click && !strstr(c, ".val=")) return false;
    if (pLose && xr(1000) < (uint32_t) pLose) { ++lostWrites; lossy = true; note("LOST write %s", c); return true; }
    if (!strncmp(c, "rsn.val=", 8)) return false;
    writes.push_back(c); boardWrote(c);
    if (click)
    {
        rp.out.clear();
        if (screen.page == "SubTrimView") rp.click("", "rs", false);
        if (!rp.out.empty())
        {
            lastDone = rp.out; if (rp.out.size() != SUBTRIM_DONE_BYTES) ++saidBad9;
            if (pageNew && (uint16_t) ((uint16_t) B("rsn") - modelClick) < 0x8000) pageShowsModel = true;       // (a click made at or behind the writing-out of this model's numbers has run: the page shows this model)
            screen.burst(screen.at, rp.out);
        }
        rp.out.clear();
        return true;
    }
    return false;
}
static void rpLoad(const char *page) { if (!strcmp(page, "SubTrimView")) { fDown = false; rp.out.clear(); rp.runCode(rp.pre); rp.out.clear(); okPresses.clear(); } }   // (an OK pressed on the page's EARLIER showing is thrown away by the board with that page: its picture goes too)   // the page comes up: its preinitialize (its "StCH" is the pretend screen's loadPrint)
static void addReal()
{
    addSubTrim(); rpLoadFile(rp); rp.other.clear(); pageNew = true;
    Page &s = P();
    for (const char *n : { "fdown", "fmove", "fpoll", "fup", "plus", "minus", "zero" }) { s.buttons[n] = {}; s.raw.insert(n); }
    s.buttons["ok"] = { 149, 0, 0, 0 };                                                    // the page's OK: print 149 (128+21) - the page file's own line, held below
    for (int ch = 1; ch <= 16; ++ch) { char n[8]; snprintf(n, sizeof n, "ch%d", ch); s.buttons[n] = {}; s.raw.insert(n); }   // (each event's word is sent by rpTap itself, framed)
    s.loadPrint = { 'S', 't', 'C', 'H' };
    screen.pages0 = screen.pages;
    tapScript = rpTap; cmdScript = rpCmd; loadScript = rpLoad; fDown = false; fPath.clear(); fLastDrag = 0; pUnheard = 0; pLose = 0; lossy = false; trail.clear();
}
// a finger on the slider: lands at `ms` from now on `first`, moves to each of `path` (a step every stepMs), rests restMs, lifts
static uint32_t finger(uint32_t ms, int first, const std::vector<int> &path, uint32_t stepMs, uint32_t restMs)
{
    uint64_t t = nowUs + (uint64_t) ms * 1000; const uint64_t t0 = t;
    fPath.push_back(first); screen.taps.insert({ t, "fdown" });
    for (int p : path) { t += (uint64_t) stepMs * 1000; fPath.push_back(p); screen.taps.insert({ t, "fmove" }); }
    t += (uint64_t) restMs * 1000;
    for (uint64_t q = t0 + 3000; q < t; q += 5000 + (q % 3) * 1000) screen.taps.insert({ q, "fpoll" });   // the screen's loop, pass after pass, while the finger is down
    screen.taps.insert({ t + 85000, "fup" });                                              // 80 ms of nothing: the release
    return (uint32_t) ((t + 85000 - nowUs) / 1000);
}
static long i0Bad = 0; static std::string i0First; static uint8_t prevTrims[16]; static long taken9 = 0; static uint64_t worstPassUs = 0;
static void i0Check(const char *where)
{
    for (int c = 0; c < 16; ++c)
    {
        if (SubTrims[c] == prevTrims[c]) continue;
        const long a = (long) prevTrims[c] - 127, b = (long) SubTrims[c] - 127; prevTrims[c] = SubTrims[c]; ++taken9;
        if (pageNew && wasMadeOnModel(c + 1, a, b) && b >= -SUBTRIM_MOST && b <= SUBTRIM_MOST) continue;                 // (the strict book: made on a page that had THIS model's numbers)
        ++i0Bad;
        if (i0First.empty()) { char t[260]; snprintf(t, sizeof t, "%s: channel %d went from %ld to %ld - no touch of the pilot's made that of it on that channel", where, c + 1, a, b); i0First = t; }
    }
}
static void rLoop(uint32_t ms)
{
    const uint64_t until = nowUs + (uint64_t) ms * 1000;
    while (nowUs < until) { const uint64_t t0 = nowUs; const bool on = CurrentView == SUBTRIMVIEW; LoopPass(); SubTrimPoll(); if (on && CurrentView == SUBTRIMVIEW && nowUs - t0 > worstPassUs) worstPassUs = nowUs - t0; i0Check("a pass of the main loop"); nowUs += 300 + xr(900); }
}
static uint8_t trimsAtFresh[16];
static void putUp() { SendCommand((char *) "page SubTrimView"); SubTrimToEdit = 0; SubTrimOldPageSaid = false; SubTrimStarts(); CurrentView = SUBTRIMVIEW; freshOut(); memcpy(prevTrims, SubTrims, 16); memcpy(trimsAtFresh, SubTrims, 16); okPresses.clear(); }   // Trims.h StartSubTrimView's lines
static void openReal() { putUp(); rLoop(700); }
// OK (the page's code 128+21: main.cpp's table calls Trims.h EndSubTrimView)
static void realOk(int n)
{
    if (n != 21) return;
    // WHICH press is this? The board obeys them in their order - but not every one: a press made as the page was still coming up (between its two
    // markers) is let go without a word, one from the page's earlier showing is thrown away with that page. So the save is held against EVERY press
    // still open: what OK saves must be what the page showed at ONE of them. (Each trial that found a press unserved showed the save right, and
    // the book wrong: trials 639, 60826.)
    ++oks9; std::deque<OkPress> open = okPresses; bool snap = !open.empty();
    for (auto &q : open) if (q.drops != PendingDropped || q.lossy) snap = false;              // (words were not kept since, or something was lost: not asked)
    if (CurrentView != SUBTRIMVIEW) return;
    const bool heardThen = SubTrimSaysDone;   // (this board believes the page to be one that says "done": OK waits for it - the save is held against ALL the page showed)
    EndSubTrimView();
    if (CurrentView == SUBTRIMVIEW) { ++okStayed9; note("OK: the page STAYS (a putting-right owed, or on its way)"); return; }
    ++okSaved9; note("OK: the model saved, the page left"); okPresses.clear();
    if (!pageNew || !snap) return;
    ++i5Looked; bool same = false; int first = 0; OkPress p = open.back();
    // (the fifteenth review: no excuse for "a page that has never said done" - a number A FINGER MADE must be the one saved, always: scene_subtrim_storm says more)
    for (auto &q : open) { bool all = true; for (int c = 0; c < 16; ++c) if (q.shown[c] != (long) SubTrims[c] - 127 && (heardThen || q.finger[c])) { all = false; if (&q == &open.back() && !first) first = c + 1; } if (all) same = true; }
    if (!heardThen) ++i5First9;
    if (same) return;
    ++i5Bad;
    if (i5First.empty()) { char t[260]; snprintf(t, sizeof t, "OK saved the model with %d on channel %d - the page showed %ld there when OK was pressed", (int) SubTrims[first - 1] - 127, first, p.shown[first - 1]); i5First = t; }
}
'''
SCENES = r'''
    const int N = argc > 2 ? atoi(argv[2]) : 3000; const uint32_t seed0 = argc > 3 ? (uint32_t) atoi(argv[3]) : 14000;
    // ============================================================ R0. the page put up; a tap on the slider; a drag; + - Zero: as the real screen does them
    {
        more(); addReal(); openReal();
        CHECK(pageIsModel() && sliderIsShown() && B("s0") == 1 && rp.errors == 0);
        tapAt(10, "ch7"); rLoop(300); CHECK(B("s0") == 7 && B("n0") == -30 && B("h0") == 97);
        const size_t w0 = writes.size();
        finger(10, 127 + 12, {}, 0, 60); rLoop(400);                                        // a TAP on the slider at +12: the press says -30 -> 12; the release says 12 -> 12
        say("R0. a tap on the slider at +12 (channel 7 at -30): the model %d, words %ld (silent presses %ld), writes of the board's %d\n", trim(7), bursts9, silent9, (int) (writes.size() - w0));
        CHECK(trim(7) == 12 && pageIsModel() && sliderIsShown() && writes.size() == w0 && wasMadeOnModel(7, -30, 12) && silent9 == 0 && noChange9 == 1);
        finger(10, 127 + 12, { 127 + 14, 127 + 17, 127 + 21, 127 + 26 }, 45, 100); rLoop(900);  // a drag from where it stands to +26, then the lift: its release says 26 -> 26
        say("R0. a drag to +26 and the lift: the model %d; words that changed nothing so far: %ld\n", trim(7), noChange9);
        CHECK(trim(7) == 26 && pageIsModel() && sliderIsShown() && writes.size() == w0 && noChange9 >= 1);
        tapAt(10, "plus"); tapAt(150, "plus"); tapAt(300, "minus"); tapAt(450, "zero"); rLoop(900);
        CHECK(trim(7) == 0 && pageIsModel() && sliderIsShown() && writes.size() == w0 && saidBad9 == 0 && rp.errors == 0 && i0Bad == 0);
        // the limits: a finger dragged beyond the bar's two ends
        finger(10, 400, { 600 }, 45, 60); rLoop(500); CHECK(trim(7) == 117 && pageIsModel());
        finger(10, -300, { -50 }, 45, 60); rLoop(500); CHECK(trim(7) == -117 && pageIsModel() && sliderIsShown());
        tapAt(10, "minus"); rLoop(300); CHECK(trim(7) == -117 && pageIsModel()); tapAt(10, "plus"); rLoop(300); CHECK(trim(7) == -116 && pageIsModel() && i0Bad == 0);
    }
    // ============================================================ R1. A TAP ON THE SLIDER WHILE THE BOARD'S CLICK OF "rs" LANDS BETWEEN ITS PRESS AND ITS RELEASE
    //   The page before: the press moved the slider silently; the board's click put it back on the channel's box; the release then said "from X to X" -
    //   nothing lost on the wire, nothing refused, and the pilot's tap had done nothing (16 of 16 timings). This release's press says the word: taken.
    {
        long vanished = 0, tried = 0;
        for (int gapMs = 5; gapMs <= 80; gapMs += 5)
        {
            more(); addReal(); openReal(); tapAt(10, "ch7"); rLoop(300); ++tried;
            finger(10, 127 + 40, {}, 0, 20);                                                // down for 20 ms; the release 85 ms after the lift
            rLoop(10 + gapMs);
            SubTrimPageOut(false);                                                          // (the board writes the page out in that moment - a putting-right that was due)
            rLoop(1500);
            if (trim(7) == -30) ++vanished;
            CHECK(trim(7) == 40 && pageIsModel() && sliderIsShown() && i0Bad == 0);
        }
        say("R1. a tap on the slider, the board's writing-out landing between its press and its release: the tap did nothing in %ld of %ld timings (the page and the model agree in all)\n", vanished, tried);
        tapsVanished9 = vanished;
    }
    // ============================================================ R2. HELP (or the screen saver) WITH A WRITING-OUT OWED - scene_subtrim's C6 road, then Help within the 0.6 s
    {
        for (int withHelp = 0; withHelp < 2; ++withHelp)
        {
            more(); addReal(); openReal(); tapAt(10, "ch4"); rLoop(300);
            pUnheard = 1000; tapAt(10, "plus"); rLoop(300); pUnheard = 0;                   // a + never heard: the page one ahead on channel 4
            tapAt(10, "plus"); rLoop(200);                                                  // a + refused: channel 4 put right, the writing-out owed 0.6 s on
            CHECK(trim(4) == 0 && shown(4) == 0 && SubTrimSettleDue);
            screen.stall(nowUs + 100000, 2000, false, 30000);                               // the screen's loop stands still for two seconds: the writing-out waits in it
            tapAt(2105, "ch7"); tapAt(2110, "plus"); tapAt(2115, "plus");                   // as it wakes: channel 7, +, + (taken: each starts from the model's number)
            rLoop(2400);
            const int shownAtOnce = shown(7), modelAtOnce = trim(7); const bool owed = SubTrimSettleDue;
            if (withHelp)
            {   // HELP, within the 0.6 s (main.cpp HelpWordCame / the "GOTO:" way back: CurrentView = LOGVIEW (LogVIEWNew), page LogView ... page SubTrimView, CurrentView = SUBTRIMVIEW - nothing else for this page)
                CurrentView = LOGVIEW; SendCommand((char *) "page LogView"); rLoop(1500);
                SendCommand((char *) "page SubTrimView"); CurrentView = SUBTRIMVIEW; pageBack(); rLoop(300);   // (main.cpp "GOTO:": SubTrimPageBack - the page as the model has it)
            }
            rLoop(5000);                                                                    // five quiet seconds
            say("R2. %s: the model's channel 7 is %d (it was %d when the old writing-out had landed, the page then showed %d, a writing-out owed: %d); five quiet seconds on the page shows %d; still owed %d\n",
                withHelp ? "HELP pressed inside the 0.6 s, and back" : "no Help (scene_subtrim's C6)", trim(7), modelAtOnce, shownAtOnce, (int) owed, shown(7), (int) SubTrimSettleDue);
            helpApart = helpApart || !pageIsModel();
            CHECK(pageIsModel() && sliderIsShown() && trim(7) == -28);
        }
    }
    // ============================================================ R3. A DRAG ON A SCREEN THAT IS BEHIND, ONE WORD LOST AT ITS START: how many of his moves are taken?
    for (uint32_t late : { 2000u, 60000u, 150000u, 300000u })
    {
        more(); addReal(); openReal(); screen.latencyUs = late; tapAt(10, "ch7"); rLoop(600);
        const size_t w0 = writes.size(); const size_t t0 = touches.size(); const long taken0 = taken9;
        std::vector<int> path; for (int i = 1; i <= 40; ++i) path.push_back(97 + 2 * i);    // a drag of 40 steps, one every 45 ms: -30 to +50
        pUnheard = 1000; finger(10, 97 + 1, {}, 0, 5); rLoop(150); pUnheard = 0;            // (a first tap whose word is lost: the page one step ahead)
        const uint32_t len = finger(10, 97 + 2, path, 45, 100); rLoop(len + 200);
        const int atLift = trim(7), shownAtLift = shown(7);
        rLoop(4000);
        say("R3. the screen %3u ms behind, a word lost, then a drag of 40 moves to +50: %d words said, %ld changes taken, %d commands of the board's; at the lift the model %d (the page %d); four seconds on the model %d, the page %d\n",
            late / 1000, (int) (touches.size() - t0), taken9 - taken0, (int) (writes.size() - w0), atLift, shownAtLift, trim(7), shown(7));
        CHECK(pageIsModel() && sliderIsShown() && i0Bad == 0);
        if (late == 300000u) dragEnd300 = trim(7);
    }
    // ============================================================ R9. THE STORM, with the real page and the real finger
    long i1Bad = 0, i1Looked = 0, i2Bad = 0, probes = 0, trialsBad = 0, i4Bad = 0; int shownBad = 0; uint64_t worstEver = 0; long touches9 = 0, stalls9 = 0, reloads9 = 0, modelReads9 = 0, held9 = 0, drops9 = 0, fingers9 = 0;
    for (int trial = 0; trial < N; ++trial)
    {
        const uint32_t sd = seed0 + trial;
        more(); addReal(); xs = sd * 2654435761u + 12345u; i0First.clear(); const long i0Before = i0Bad; worstPassUs = 0;
        const bool oldFile = sd % 9 == 8; if (oldFile) { rpLoadOld(rp); pageNew = false; ++oldTrials; }
        uint8_t trims0[16];
        screen.realUart = true; screen.shoutForm = (sd & 1) ? 198 : 197;
        const bool slow = sd % 4 >= 2;
        screen.latencyUs = slow ? 60000 + xr(340000) : 200 + xr(3) * xr(20000);
        const int nCh = (sd % 5 < 2) ? 2 : (sd % 5 == 2) ? 3 : 16; const int ch0 = 1 + xr(17 - nCh);
        for (int i = 0; i < 16; ++i) SubTrims[i] = (uint8_t) (127 + (xr(3) ? 0 : (int) xr(235) - 117));
        for (int ch = 1; ch <= 16; ++ch) B(boxOf(ch)) = (long) xr(235) - 117;
        B("n0") = (long) xr(255) - 127; B("h0") = xr(255); memset(byFinger, 0, sizeof byFinger);
        if (sd % 6 == 5) { SubTrimSaysDone = false; SubTrimShown = false; SubTrimAsked = SubTrimDone = 0; ++firsts9; }   // THE FIRST VISIT SINCE THIS BOARD STARTED (the fifteenth review)
        putUp(); memcpy(trims0, SubTrims, 16); extra7 = realOk; okPresses.clear(); i5First.clear();
        if (sd % 6 == 5 && !oldFile && xr(2))
        {   // REVIEWER B'S DOOR (the fifteenth review): the first visit, the page's first "done" still on its way, a touch, and OK twice close together
            rLoop(xr(3) ? 50 + xr(800) : xr(40));
            { char b[8]; snprintf(b, sizeof b, "ch%d", ch0 + (int) xr(nCh)); tapAt(1, b); } tapAt(40 + xr(200), xr(2) ? "plus" : "minus"); rLoop(50 + xr(250));
            tapAt(1 + xr(60), "ok"); tapAt(100 + xr(250), "ok"); rLoop(200 + xr(600)); ++firstDoors9;
            if (CurrentView != SUBTRIMVIEW) { putUp(); memcpy(trims0, SubTrims, 16); note("the page is put up again (Sub trim pressed)"); }
        }
        rLoop(xr(4) ? 700 : xr(80));
        pLose = (sd % 7 == 6) ? 25 : (sd % 7 == 5) ? 4 : 0; pUnheard = (sd % 6 == 5) ? 40 : 0;
        const bool rough = sd % 3 != 0; const bool hand = xr(2) != 0;
        const int actions = 10 + xr(36);
        for (int a = 0; a < actions; ++a)
        {
            const uint32_t pick = xr(100); ++touches9;
            uint32_t gap = hand ? 110 + xr(300) : xr(3) ? xr(60) : xr(5) ? 60 + xr(500) : 600 + xr(2500);
            const int ch = ch0 + xr(nCh); char cb[8]; snprintf(cb, sizeof cb, "ch%d", ch);
            if (pick < 16) tapAt(1, cb);
            else if (pick < 28) { tapAt(1, cb); const int n = 1 + xr(3); for (int s = 0; s < n; ++s) tapAt(2 + (hand ? 110 * (s + 1) + xr(200) : xr(160)), xr(2) ? "plus" : "minus"); touches9 += n; }
            else if (pick < 44) { const uint32_t len = finger(1, (int) xr(300) - 20, {}, 0, 10 + xr(150)); if (gap < len + 5) gap = len + 5; ++fingers9; }                    // a tap on the slider
            else if (pick < 58) tapAt(1, "plus");
            else if (pick < 70) tapAt(1, "minus");
            else if (pick < 74) tapAt(1, "zero");
            else if (pick < 88)
            {   // a drag, and at its end the finger rests for a while
                std::vector<int> path; int v = (int) B("h0") + (int) xr(60) - 30; const int first = v; const int steps = 3 + xr(16);
                for (int s = 0; s < steps; ++s) { v += (int) xr(11) - 5; path.push_back(v); }
                const uint32_t len = finger(1, first, path, 20 + xr(40), xr(3) ? xr(120) : 200 + xr(1500)); if (gap < len + 5) gap = len + 5; ++fingers9;
            }
            else if (pick < 91 && rough)
            {   // (the fifteenth review: one stall in twelve is longer than OK's two seconds; one in three wakes with a touch in front of its queued commands)
                const bool longOne = xr(3) == 0; const uint32_t ms = longOne ? 2100 + xr(2500) : 100 + xr(4) * xr(900), wake = xr(3) == 0 ? 0 : 3000 + xr(40000);
                longStalls9 += longOne; wakeRounds9 += wake != 0;
                screen.stall(nowUs + xr(200000), ms, xr(2) != 0, wake); ++stalls9; if (screen.shoutForm < 198) lossy = true; note("the screen's loop stands still for %u ms%s", (unsigned) ms, wake ? " (and wakes with a touch in front of its commands)" : "");
                if (longOne && xr(2)) { tapAt(ms + xr(300), "ok"); rLoop(ms + 400);
                                        if (CurrentView == SUBTRIMVIEW && xr(2)) { const uint32_t ms2 = 2100 + xr(1500); screen.stall(nowUs + xr(50000), ms2, xr(2) != 0, 3000 + xr(40000)); ++stalls9; ++longStalls9; tapAt(ms2 + xr(300), "ok"); rLoop(ms2 + 400); } }
            }
            else if (pick < 93 && rough) { CurrentView = LOGVIEW; SendCommand((char *) "page LogView"); rLoop(20 + xr(400)); SendCommand((char *) "page SubTrimView"); CurrentView = SUBTRIMVIEW; pageBack(); okPresses.clear(); ++reloads9; note("Help and its way back: the page put up again, written out"); }
            else if (pick < 96 && rough)
            {
                rLoop(xr(300)); i0Check("before another model was read");
                for (int i = 0; i < 16; ++i) SubTrims[i] = (uint8_t) (127 + (xr(3) ? 0 : (int) xr(235) - 117));
                memcpy(prevTrims, SubTrims, 16); memcpy(trims0, SubTrims, 16); freshOut(); memcpy(trimsAtFresh, SubTrims, 16); ++modelReads9; note("another model read under the page");
            }
            else if (pick < 98 && rough)
            {   // the main loop held elsewhere while the finger drags (words not kept for want of room)
                std::vector<int> path; int v = (int) B("h0"); const int steps = 20 + xr(30);
                for (int s = 0; s < steps; ++s) { v += (int) xr(5) - 2; path.push_back(v); }
                const uint32_t len = finger(1, v, path, 45, xr(200)); const uint16_t d0 = PendingDropped;
                for (int k = 0; k < steps / 2 + 2; ++k) { DelayWithDog(80); SendText((char *) "ModelName", (char *) "Storm"); }
                ++held9; drops9 += (uint16_t) (PendingDropped - d0); if (gap < 400) gap = 400; (void) len; note("the main loop held elsewhere: %u words not kept", (unsigned) (uint16_t) (PendingDropped - d0));
            }
            else tapAt(1, cb);
            if (xr(3) == 0) { tapAt(1 + xr(hand ? 700 : 120), "ok"); const int more9 = xr(4); for (int o = 0; o < more9; ++o) { const uint32_t w = xr(3) ? 30 + xr(600) : 1900 + xr(900); if (xr(3) == 0) tapAt(1 + xr(w), xr(2) ? "plus" : "minus"); tapAt(w, "ok"); rLoop(w + xr(200)); if (CurrentView != SUBTRIMVIEW) break; } }   // REVIEWER B'S MIX: OK often, in twos and threes, with touches between
            rLoop(gap);
            if (CurrentView != SUBTRIMVIEW) { rLoop(xr(300)); putUp(); if (!oldFile) memcpy(trims0, SubTrims, 16); note("the page is put up again (Sub trim pressed)"); rLoop(xr(4) ? 400 : xr(60)); }
        }
        pLose = 0; pUnheard = 0;
        while (screen.busyUntil > nowUs || !screen.taps.empty()) rLoop(100);
        rLoop(700);
        if (CurrentView != SUBTRIMVIEW) { putUp(); note("the page is put up again (Sub trim pressed)"); }
        rLoop(2200);
        if (CurrentView != SUBTRIMVIEW) { putUp(); rLoop(2200); }
        while (screen.busyUntil > nowUs || !screen.taps.empty()) rLoop(100);                                         // (a long stall still running: the trial's end waits it out)
        if (SubTrimSettleDue || SubTrimDone != SubTrimAsked) rLoop(2500);
        if (CurrentView != SUBTRIMVIEW) { putUp(); rLoop(2200); }
        const bool agree = pageIsModel() && sliderIsShown() && PendingCount == 0;
        bool healed = true;
        if (oldFile)
        {
            if (memcmp(trims0, SubTrims, 16)) ++i3Bad;
            if (!pageIsModel()) { ++oldApart; if (!lossy && ++oldApartClean <= 2) { printf("---- trial %d (seed %u): THE PAGE FILE FROM BEFORE, nothing lost, and two quiet seconds on the page does not show what the model has\n", trial, sd); for (int c = 1; c <= 16; ++c) if (shown(c) != trim(c)) printf("     channel %d: the page shows %d, the model has %d\n", c, shown(c), trim(c)); printf("     owed %d, words waiting %d, the page's channel %ld, n0 %ld\n", (int) SubTrimSettleDue, (int) PendingCount, B("s0"), B("n0")); for (auto &l : trail) printf("       %s\n", l.c_str()); } }
            tapScript = nullptr; cmdScript = nullptr; loadScript = nullptr; extra7 = nullptr; continue;
        }
        if (!lossy) { ++i1Looked; if (!agree) ++i1Bad; }
        for (int ch = 1; ch <= 16; ++ch)
        {
            if (shown(ch) == trim(ch)) continue;
            ++probes; const int had = trim(ch); char cb[8]; snprintf(cb, sizeof cb, "ch%d", ch);
            tapAt(1, cb); tapAt(150, "plus"); rLoop(700);
            if (shown(ch) != trim(ch) || (trim(ch) != had && !wasMadeOnModel(ch, had, trim(ch)))) { healed = false; note("PROBE of channel %d: the model %d (it had %d), the page %d", ch, trim(ch), had, shown(ch)); }
        }
        { char cb[8]; snprintf(cb, sizeof cb, "ch%d", B("s0") >= 1 && B("s0") <= 16 ? (int) B("s0") : 1); tapAt(1, cb); rLoop(400); }
        if (!(pageIsModel() && sliderIsShown())) healed = false;
        if (!healed) ++i2Bad;
        const bool waited = worstPassUs > 20000; if (worstPassUs > worstEver) worstEver = worstPassUs;
        const bool bad = i0Bad != i0Before || (!lossy && !agree) || !healed || waited || rp.errors || saidBad9 || !i5First.empty();
        if (bad && ++trialsBad && ++shownBad <= 3)
        {
            printf("---- trial %d (seed %u, the screen %u ms behind, %d channel(s) in play)%s%s%s%s\n", trial, sd, (unsigned) (screen.latencyUs / 1000), nCh,
                   i0Bad != i0Before ? (" | I0: " + i0First).c_str() : !i5First.empty() ? (" | I5: " + i5First).c_str() : "", (!lossy && !agree) ? " | I1: nothing was lost, and two quiet seconds on the page and the model do not agree" : "", !healed ? " | I2: a tap and a + did not put a channel right" : "", waited ? " | I4: a pass of the main loop waited" : "");
            for (int c = 1; c <= 16; ++c) if (shown(c) != trim(c)) printf("     channel %d: the page shows %d, the model has %d\n", c, shown(c), trim(c));
            printf("     the page on channel %ld, its slider's number %ld, the slider %ld; frames waiting %d; the loop's longest pass %.1f ms\n", B("s0"), B("n0"), B("h0"), (int) PendingCount, worstPassUs / 1e3);
            for (auto &l : trail) printf("       %s\n", l.c_str());
        }
        if (waited) ++i4Bad;
        tapScript = nullptr; cmdScript = nullptr; loadScript = nullptr; extra7 = nullptr;
    }
    printf("THE REAL PAGE under a storm: %d trials, %ld actions, %ld words said by the page's own scripts (%ld never heard; %ld silent presses of the slider; %ld words that changed nothing), %ld changes taken; %ld writes lost, %ld stalls, the page put up again %ld times, %ld models read, %ld fingers on the slider, the loop held %ld times (%ld words not kept)\n",
           N, touches9, bursts9, unheard9, silent9, noChange9, taken9, lostWrites, stalls9, reloads9, modelReads9, fingers9, held9, drops9);
    printf("   I0 (the model never holds a number the pilot did not make on that channel): broken %ld time(s)\n   I1 (nothing lost: the page and the model agree): broken in %ld of %ld trial(s)\n   I2 (one touch puts a channel right): broken in %ld trial(s); %ld channels probed\n"
           "   I4 (nothing waits): broken in %ld trial(s); the main loop's longest pass %.1f ms\n   the page's scripts that did not run: %ld; bursts that did not say (channel, as it stood, what it made): %ld\n", i0Bad, i1Bad, i1Looked, i2Bad, probes, i4Bad, worstEver / 1e3, rp.errors, saidBad9);
    printf("   R1: a tap on the slider that did nothing (the board's click between its press and release): %ld timings; R2: after Help the page and the model apart: %d; R3: a 40-move drag to +50 on a screen 300 ms behind ended at %d\n", tapsVanished9, (int) helpApart, dragEnd300);
    printf("   OK pressed and served %ld times: obeyed %ld, the page stayed %ld times; I5 (what OK saves is what the page showed when it was pressed): broken %ld time(s) of %ld looked at (%ld of them before anything had been heard from the page)\n   %ld trials began as the first visit since power-on (%ld of them with a touch and OK twice at once); %ld stalls longer than two seconds, %ld that woke with a touch in front of the commands\n", oks9, okSaved9, okStayed9, i5Bad, i5Looked, i5First9, firsts9, firstDoors9, longStalls9, wakeRounds9);
    CHECK(tapsVanished9 == 0 && !helpApart && i5Bad == 0); if (N >= 300) CHECK(okSaved9 > N / 4 && okStayed9 > N / 50 && i5Looked > N / 20 && silent9 < bursts9 / 20);
    printf("   I3 (the page file from before: nothing is ever taken): %ld trials, broken %ld; two quiet seconds on the page shows what the model has in all but %ld (%ld of them with nothing lost)\n", oldTrials, i3Bad, oldApart, oldApartClean);
    CHECK(i0Bad == 0); CHECK(i4Bad == 0); CHECK(i1Bad == 0); CHECK(i2Bad == 0); CHECK(rp.errors == 0 && saidBad9 == 0); CHECK(i3Bad == 0);
    wordHook = nullptr;
'''
_p32 = json.load(open(NEWPAGE)); assert [(c.get('ev') or {}).get('r') for c in _p32['comps'] if c.get('txt') == 'OK'] == ['print 149 // 128+21'], 'page 32: its OK does not print 149'
EXTRA += 'static bool helpApart = false; static int dragEnd300 = -999; static long oldTrials = 0, i3Bad = 0, oldApart = 0, oldApartClean = 0;\n'
if __name__ == '__main__':
    nn = sys.argv[sys.argv.index('--n') + 1] if '--n' in sys.argv else '1500'
    sd = sys.argv[sys.argv.index('--seed') + 1] if '--seed' in sys.argv else '14000'
    args = ['--x', nn, sd] if '--show' not in sys.argv else ['--show', nn, sd]
    sys.exit(lib.build_run('realpage', SCENES, extra=EXTRA, more_defines=('SUBTRIMVIEW',), args=args, sanitize='--san' in sys.argv, timeout=3000))
