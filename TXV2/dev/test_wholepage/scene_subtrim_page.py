#!/usr/bin/env python3
"""THE PRETEND SUB-TRIM PAGE IS THE REAL ONE (the author's, for the thirteenth review's cure; 15 Nov 2026).

scene_subtrim and scene_subtrim_storm run Trims.h over a PRETEND page: a few lines of C++ that do what the page file's scripts do (stTap, stLoad,
the part "rs"). Every rule those tests hold is only as true as that pretence - and twice a review found the page doing what nobody had modelled.
Here the page file's OWN scripts (the card's 32.json: the one before, and this release's) are run by the screen's OWN interpreter (its
lib/NextionScript, the source beside this tree) and, step for step, by the pretend page - thousands of random steps: a channel tapped, the slider
put somewhere (held to its limits as the screen's sliderTo holds it), the slider's release, "+", "-", Zero, the page loaded again, the main board's
writes of any box, of the slider and its number, its click of "rs". After every step the two must agree on everything: the page's channel, the
slider, its number, all sixteen boxes - and on every byte the page said (this release's: 22 bytes a touch, its last number twice; 14 its "done").
(The finger itself - its landing, its moves 40 ms apart, its release 80 ms behind it - is scene_subtrim_real's: the page file under the screen's own
touch rules, with nothing pretended.)

   python3 scene_subtrim_page.py [--show]"""
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
import scene_subtrim as base
m = lib.m
LIBDIR = os.path.join(os.path.dirname(m.ROOT), 'ESP32-board2', 'board4', 'nextion-emulator', 'lib', 'NextionScript')
H, CPP = os.path.join(LIBDIR, 'NextionScript.h'), os.path.join(LIBDIR, 'NextionScript.cpp')
PAGES = [p for p in (base.PAGE, base.NEWPAGE) if os.path.exists(p)]
if not (os.path.exists(H) and os.path.exists(CPP) and PAGES):
    print('NOT RUN: the screen project\'s script interpreter (lib/NextionScript) is not beside this repository - the pretend page was NOT held against the real one'); sys.exit(0)   # (the fifteenth review: said so, and no "ALL GOOD")
hdr = open(H, encoding='utf-8', errors='replace').read(); cpp = open(CPP, encoding='utf-8', errors='replace').read()
incs = sorted(set(re.findall(r'^\s*#\s*include\s*<[^>]+>', hdr + '\n' + cpp, re.M)))
cpp = re.sub(r'^\s*#\s*include\s*[<"][^>"]+[>"][^\n]*\n', '', cpp, flags=re.M); hdr = re.sub(r'^\s*#\s*include\s*<[^>]+>[^\n]*\n', '', hdr, flags=re.M)
def lit(s): return 'R"LDRC(' + s + ')LDRC"'
def page_cpp(path, k):
    """the page file's scripts and numbers, as C++ for the real interpreter's host"""
    pg = json.load(open(path)); out = ['static void realLoad%d(RealPage &r)\n{\n    r.clear(); r.pre = %s;\n' % (k, lit((pg.get('ev') or {}).get('preinitialize', '')))]
    for c in pg['comps']:
        ev = c.get('ev') or {}
        for e in ('p', 'r', 'm'):
            if e in ev: out.append('    r.ev["%s.%s"] = %s;\n' % (c['n'], e, lit(ev[e])))
        out.append('    r.has.insert("%s");\n' % c['n'])
        if c['n'] == 'h0': out.append('    r.minval = %d; r.maxval = %d;\n' % ((c.get('a') or {}).get('minval', 0), (c.get('a') or {}).get('maxval', 100)))
    return ''.join(out) + '}\n'
KINDS = [base.page_kind(p) for p in PAGES]
EXTRA = base.EXTRA + '\n'.join(incs) + '\n#include <map>\n#include <set>\nnamespace realscript {\n' + hdr + '\n' + cpp + '\n}\n' + r'''
// THE REAL PAGE: its file's scripts, run by the screen's interpreter. What the screen's own host does around them is done here as it does it: a part's
// number is an int by its name; "click" runs the part's press or release script (a part the page has not got: nothing); print appends to the burst.
struct RealPage : realscript::NextionHost
{
    std::map<std::string, int32_t> num; std::map<std::string, std::string> ev; std::set<std::string> has; std::string pre; std::vector<uint8_t> out; int minval = 0, maxval = 254; int errors = 0;
    void clear() { num.clear(); ev.clear(); has.clear(); out.clear(); errors = 0; }
    int32_t getInt(const std::string &, const std::string &comp, const std::string &attr) override { return attr == "val" ? num[comp] : 0; }
    void setInt(const std::string &, const std::string &comp, const std::string &attr, int32_t v) override { if (attr == "val") num[comp] = v; }
    std::string getTxt(const std::string &, const std::string &) override { return ""; }
    void setTxt(const std::string &, const std::string &, const std::string &) override {}
    void send(const uint8_t *d, size_t n) override { out.insert(out.end(), d, d + n); }
    void click(const std::string &, const std::string &comp, bool press) override { if (has.count(comp)) run(comp + (press ? ".p" : ".r")); }
    void runCode(const std::string &code) { realscript::NextionScript s(*this, "SubTrimView"); if (!s.run(code)) { ++errors; printf("   the page's script did not run: %s (line %d)\n", s.lastError().c_str(), s.lastErrorLine()); } }
    void run(const std::string &what) { auto it = ev.find(what); if (it != ev.end()) runCode(it->second); }
    void slider(int to) { to = to < minval ? minval : to > maxval ? maxval : to; num["h0"] = to; run("h0.m"); }   // (the screen's sliderTo: the finger's place, held to the slider's limits; then its move script)
};
''' + ''.join(page_cpp(p, k) for k, p in enumerate(PAGES)) + r'''
static uint32_t ps = 1; static uint32_t pr(uint32_t k) { ps = ps * 1664525u + 1013904223u; return k ? (ps >> 8) % k : 0; }
static std::string hex9(const std::vector<uint8_t> &b) { std::string s; char t[4]; for (uint8_t x : b) { snprintf(t, sizeof t, "%02X ", x); s += t; } return s; }
'''
SCENES = r'''
    static const bool kindNew[] = { ''' + ', '.join('true' if k == 'new' else 'false' for k in KINDS) + r''' };
    for (int file = 0; file < ''' + str(len(PAGES)) + r'''; ++file)
    {
        long steps = 0, differ = 0, said = 0, saidNumbers = 0, saidDone = 0; std::string first;
        for (int trial = 0; trial < 400; ++trial)
        {
            more(); addSubTrim(); pageNew = kindNew[file]; ps = 9000 + trial * 7 + file; doneToWire = false;
            RealPage real; ''' + ''.join('if (file == %d) realLoad%d(real); ' % (k, k) for k in range(len(PAGES))) + r'''
            SendCommand((char *) "page SubTrimView"); loopFor(300); CHECK(screen.page == "SubTrimView");
            // both begin with the same numbers in every box (what the last visit left), then the page comes up: its preinitialize
            for (const char *n : { "n0", "h0", "s0", "rsn" }) { const long v = (long) pr(255) - 127; B(n) = v; real.num[n] = (int32_t) v; }
            for (int ch = 1; ch <= 16; ++ch) { const long v = (long) pr(255) - 127; B(boxOf(ch)) = v; real.num[boxOf(ch)] = (int32_t) v; }
            stLoad("SubTrimView"); real.out.clear(); real.runCode(real.pre); real.out.clear();
            for (int step = 0; step < 60; ++step)
            {
                const uint32_t pick = pr(100); char what[60]; std::vector<uint8_t> model;
                real.out.clear();
                if (pick < 22) { const int ch = 1 + pr(16); char b[8]; snprintf(b, sizeof b, "ch%d", ch); stTap(b); model = P().buttons[b]; real.click("", boxOf(ch), false); snprintf(what, sizeof what, "channel %d tapped", ch); }
                else if (pick < 36) { const int to = (int) pr(300) - 20; slideTo.push_back(to); stTap("slider"); model = P().buttons["slider"]; real.slider(to); snprintf(what, sizeof what, "the slider put at %d", to); }
                else if (pick < 42) { lastSliderUs = screen.at - 100000; fingerDown = false; stTap("lift"); model = P().buttons["lift"]; real.run("h0.r"); snprintf(what, sizeof what, "the slider's release"); }   // (85 ms behind the finger's going: the same words once more)
                else if (pick < 55) { stTap("plus"); model = P().buttons["plus"]; real.run("b0.r"); snprintf(what, sizeof what, "+"); }
                else if (pick < 70) { stTap("minus"); model = P().buttons["minus"]; real.run("b1.r"); snprintf(what, sizeof what, "-"); }
                else if (pick < 76) { stTap("zero"); model = P().buttons["zero"]; real.run("b2.r"); snprintf(what, sizeof what, "Zero"); }
                else if (pick < 80) { stLoad("SubTrimView"); real.runCode(real.pre); model = P().loadPrint; snprintf(what, sizeof what, "the page loaded again"); }
                else if (pick < 90) { const int ch = 1 + pr(16); const long v = (long) pr(255) - 127; B(boxOf(ch)) = v; real.num[boxOf(ch)] = (int32_t) v; snprintf(what, sizeof what, "the board writes channel %d's box: %ld", ch, v); }
                else if (pick < 94) { const long v = (long) pr(255) - 127; B("n0") = v; real.num["n0"] = (int32_t) v; snprintf(what, sizeof what, "the board writes the slider's number: %ld", v); }
                else if (pick < 96) { const long v = pr(255); B("h0") = v; real.num["h0"] = (int32_t) v; snprintf(what, sizeof what, "the board writes the slider: %ld", v); }
                else if (pick < 98) { stCmd("click rs,0"); model = lastDone; real.click("", "rs", false); snprintf(what, sizeof what, "the board clicks rs"); }
                else { const long v = (long) pr(70000) - 100; B("rsn") = v; real.num["rsn"] = (int32_t) v; snprintf(what, sizeof what, "the board writes the click's number: %ld", v); }
                screen.taps.clear();                                                                                      // (the pretend slider's own release, 85 ms on: not waited for here - the release is a step of its own, above)
                ++steps; said += !real.out.empty(); saidNumbers += real.out.size() == SUBTRIM_WORD_BYTES; saidDone += real.out.size() == SUBTRIM_DONE_BYTES;
                bool same = model == real.out && B("s0") == real.num["s0"] && B("n0") == real.num["n0"] && B("h0") == real.num["h0"] && B("rsn") == real.num["rsn"] && real.errors == 0;
                for (int ch = 1; ch <= 16 && same; ++ch) same = B(boxOf(ch)) == real.num[boxOf(ch)];
                if (!same && ++differ == 1)
                {
                    char t[400]; snprintf(t, sizeof t, "trial %d, step %d (%s): the pretend page s0 %ld n0 %ld h0 %ld said [%s]; the real page s0 %d n0 %d h0 %d said [%s]", trial, step, what, B("s0"), B("n0"), B("h0"), hex9(model).c_str(),
                                         (int) real.num["s0"], (int) real.num["n0"], (int) real.num["h0"], hex9(real.out).c_str()); first = t;
                }
                if (!same) break;
            }
        }
        say("the pretend Sub-trim page against the page file %d (%s) run by the screen's own interpreter: %ld steps, %ld bursts said (%ld with their numbers); they differed %ld time(s)%s%s\n",
            file, kindNew[file] ? "this release's" : "the one before", steps, said, saidNumbers, differ, differ ? " - first: " : "", first.c_str());
        if (differ) printf("   %s\n", first.c_str());
        CHECK(differ == 0 && steps > 20000 && said > 5000 && (kindNew[file] ? saidNumbers > 5000 && saidDone > 200 : saidNumbers == 0 && saidDone == 0));   // (this release's page says "done" behind every click of "rs"; the one before never)
    }
    wordHook = nullptr; tapScript = nullptr; loadScript = nullptr; cmdScript = nullptr;
'''
if __name__ == '__main__':
    if 'new' not in KINDS: print('NOTE: this release\'s Sub-trim page file was not found: only the one before was held against the pretend page')
    sys.exit(lib.build_run('subtrim_page', SCENES, extra=EXTRA, more_defines=('SUBTRIMVIEW',)))
