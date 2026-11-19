"""The scenes of dev/test_stallscreen are built as dev/test_wholepage's are (on dev/test_noanswer, which is built on dev/test_stalepress):
the REAL routines lifted out of the headers over the pretend screen - here with the real screen's port (screen.realUart)."""
import importlib.util, os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('wholepage_lib_for_stallscreen', os.path.join(os.path.dirname(HERE), 'test_wholepage', 'lib.py'))
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
n, m = w.n, w.m

# what every scene here uses: bytes said by hand, and the storms' own dice
COMMON = r'''
static std::vector<uint8_t> by9(const char *w) { return std::vector<uint8_t>(w, w + strlen(w)); }
static std::vector<uint8_t> cat9(std::initializer_list<std::vector<uint8_t>> parts) { std::vector<uint8_t> v; for (auto &p : parts) v.insert(v.end(), p.begin(), p.end()); return v; }
static const std::vector<uint8_t> END9 = { 0xFF, 0xFF, 0xFF }, PAGE9 = { 0x66, 9, 0xFF, 0xFF, 0xFF };
static uint32_t rs9 = 20261115u; static uint32_t rnd9(uint32_t k) { rs9 = rs9 * 1664525u + 1013904223u; return k ? (rs9 >> 8) % k : 0; }
// A STALL OF THE SCREEN'S LOOP, planted once a chosen number of boxes has been asked for (or at a chosen moment): how long, when its other core's
// line begins (185 to 250 ms into the silence, should the loop still be silent then), the rest of the loop's pass before its serial job, and
// how long the shouting core is held after its first piece
static int plantAt9 = -1; static bool planted9 = false; static uint32_t stallUs9 = 0, shoutAfterUs9 = 0, holdUs9 = 0, wakeRoundUs9 = 0; static uint64_t stallAt9 = 0;
static int getsAsked9() { int k = screen.gets; for (auto &c : screen.cmds) k += c.second.rfind("get ", 0) == 0 && c.second.find('.') != std::string::npos; return k; }
static void stallNow9()
{
    const uint64_t at = nowUs;
    screen.busyUntil = std::max(screen.busyUntil, at + stallUs9); screen.cmdHoldUntil = std::max(screen.cmdHoldUntil, screen.busyUntil + wakeRoundUs9);
    if (shoutAfterUs9 < stallUs9 + wakeRoundUs9) { screen.lastShout = screen.shoutText(shoutAfterUs9 / 1000 + rnd9(40), at + shoutAfterUs9); screen.shoutBegin(at + shoutAfterUs9, screen.lastShout, holdUs9); ++screen.shouts; }
}
static void plant9() { if (planted9 || plantAt9 < 0 || getsAsked9() < plantAt9) return; planted9 = true; stallNow9(); }
static void stallDue9() { if (!stallAt9 || nowUs < stallAt9) return; stallAt9 = 0; stallNow9(); }
static void draw9(int mode)   // this trial's stall: (0) the loop wakes near the line, (1) anywhere, (2) inside the line, mostly
{
    static const unsigned long ups[] = { 23456, 81234, 381234, 981234, 1381234, 4381234, 9381234, 14381234 };
    screen.upMs = (uint32_t) (ups[rnd9(8)] + rnd9(9000));
    shoutAfterUs9 = 185000 + rnd9(65000);
    if (mode == 0) stallUs9 = shoutAfterUs9 - 2000 + rnd9(8000);
    else if (mode == 1) stallUs9 = 150000 + rnd9(1050000);
    else stallUs9 = shoutAfterUs9 + 100 + rnd9(900);
    wakeRoundUs9 = rnd9(3) ? rnd9(2500) : 0;
    holdUs9 = rnd9(100) < 15 ? 1500 + rnd9(4500) : 0;
    planted9 = false; screen.lastShout.clear();
}
'''

def build_run(name, scenes, extra='', **kw):
    return w.build_run(name, scenes, extra=COMMON + extra, label='test_stallscreen', **kw)
