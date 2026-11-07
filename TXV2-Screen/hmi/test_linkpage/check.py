#!/usr/bin/env python3
"""Source checks of 1.11.177 (B179, 5 Nov 2026): the Teensy keeps the file link shut while the pilot is on a page, and the screen
does not even queue a job from the Mac then. Malcolm, on the Governor page: "I just saw it jump again to the front screen" - a
knock from the screen opened the link, whose end draws the front page afresh.
   python3 hmi/test_linkpage/check.py"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
def src(rel): return open(os.path.join(PROJ, rel), encoding='utf-8', errors='replace').read()
checks = fails = 0
def check(cond, what):
    global checks, fails
    checks += 1
    if not cond: fails += 1; print('FAIL: ' + what)

m = src('src/main.cpp')
check('static bool linkPageAllows() { return page.name.empty() || page.name == "FrontView" || page.name == "BlankView" || page.name == "TXSetupView"; }' in m,
      "main.cpp: the pages on which the Teensy lets the link open, by the names the Teensy sends")
ls = m[m.index('static bool linkStart() {'):m.index('return teensyLink.start();')]
check('if (flyingNow()) { teensyLink.clear(); linkWhyNot = ' in ls and 'if (!linkPageAllows()) { teensyLink.clear(); linkWhyNot = ' in ls,
      "main.cpp: linkStart() queues nothing while flying or on a page, and says why")
check(m.count('linkReply(') >= 12 and 'linkStart() ? 200 : 500' not in m, "main.cpp: every door job answers through linkReply (200 what was queued, 500 why not)")
check(m.index('static void linkReply(') < m.index('static void webBegin() {') and 'web.send(500, "text/plain", linkWhyNot.length() ? linkWhyNot : String("not started"))' in m,
      "main.cpp: linkReply is defined before the routes and gives the reason")
u = src('lib/LdrcUpdate/LdrcUpdate.cpp')
asked = u[u.index('void Updater::asked()'):u.index('void Updater::decide()')]
check('case LE_PAGE_OPEN:      message("A page is open on the transmitter", "Go to its front page,", "then check again."); return;' in asked,
      "LdrcUpdate.cpp: a check refused for a page says so in the panel")
h = src('lib/LdrcLink/LdrcLink.h'); c = src('lib/LdrcLink/LdrcLink.cpp')
check('LE_PAGE_OPEN = 18' in h and 'case LE_PAGE_OPEN: return "a page is open on the transmitter. Go to its front page and try again";' in c,
      "the link library: the code and its words")
sim = src('hmi/test_link/sim.h')
check('pageOpen ? LE_PAGE_OPEN' in sim, "test_link's fake Teensy refuses for a page in LinkRefusal()'s order")
# 1.11.178: the quiet look at power-up asks the main board only on a page that lets the link open (it knocked 52 s after every power-up)
uh = src('lib/LdrcUpdate/LdrcUpdate.h')
check('virtual bool linkPageOk() { return true; }' in uh and 'P_PAGE_WAIT' in uh, "the host says whether the main board's page lets the link open; the look has a phase to wait in")
check('if (quiet_ && !host_.linkPageOk()) { note("quiet look: a page is open on the transmitter: waiting for its front page"); since_ = now; phase_ = P_PAGE_WAIT; return; }' in u
      and 'case P_PAGE_WAIT:' in u and 'now - since_ > 600000' in u, "LdrcUpdate.cpp: the quiet look waits for the front page, ten minutes at most, and knocks only then")
begin = u[u.index('void Updater::begin()'):u.index('note("---- check for update')]
check('if (!quiet_ || link_.running()) return;' in begin and 'quietEnd(3);' in begin, "the pilot's own Check for update is not ignored while a quiet look waits")
d = src('src/update_device.h')
# (1.11.181/182: the QUIET look asks only on the front page, or the screen saver over it - a look on Transmitter setup threw the
# pilot off it; the pilot's own Check for update still goes by linkPageAllows)
check('bool linkPageOk() override { return page.name == "FrontView" || (page.name == "BlankView" && saverPage == "FrontView"); }' in d,
      "the device's quiet look answers only from the front page (or the screen saver over it)")
# 1.11.178: the loop task on the task watchdog
check('#include <esp_task_wdt.h>' in m and 'esp_task_wdt_init(20, true);\n    enableLoopWDT();' in m, "main.cpp: the loop task goes on the task watchdog, 20 s, panic (a core dump)")
setup_hold = m.index('holdWatchBegin();                                      // (1.11.164) the hold watch')
check(m.index('enableLoopWDT();', setup_hold) < m.index('void loop() {'), "switched on at the end of setup(), after the card's build and the page")
check('disableLoopWDT(); gfx->fillRect(0, 0, W, 30, 0xF800);' in m and 'ArduinoOTA.onEnd([]() { enableLoopWDT(); });' in m and 'ArduinoOTA.onError([](ota_error_t) { enableLoopWDT(); });' in m,
      "firmware pushed by espota (one long pass of loop) takes the loop task off the watchdog, and puts it back")
br = m[m.index('static void breathe() {'):m.index('in = true; pumpSerial();')]
check('esp_task_wdt_reset();' in br, "breathe() feeds the watchdog: a file sent through the door, an upload, a screenshot")
teensy = os.path.expanduser('~/Documents/GitHub/TXV1B/TransmitterCode/lib/LdrcLink')
if os.path.isdir(teensy):
    for f in ('LdrcLink.h', 'LdrcLink.cpp'):
        check(open(os.path.join(PROJ, 'lib', 'LdrcLink', f), 'rb').read() == open(os.path.join(teensy, f), 'rb').read(), "the Teensy's copy of the link library is this one, byte for byte: " + f)
    fg = open(os.path.join(os.path.dirname(teensy), '..', 'include', 'FlightGuard.h'), encoding='utf-8', errors='replace').read()
    check('return ldrc::LE_PAGE_OPEN;' in fg and 'CurrentView == FRONTVIEW || CurrentView == TXSETUPVIEW || CurrentView == BLANKVIEW || CurrentView == 254' in fg,
          "the Teensy's LinkRefusal() refuses for a page, and names the same pages as linkPageAllows()")
# 1.11.179: the block's items line ends with a newline and is sent again every 600 ms while the read window is open (B181 reads a pipe line to its newline)
b = src('src/ble_device.h')
check('bleMailPost(tel + "\\n")' in b and 'if (tel == bleTelLast && millis() - bleTelAt < 600) return;' in b, "ble_device.h: the items line ends with a newline and is repeated every 600 ms while unchanged")
print('%d checks, %d failures' % (checks, fails))
sys.exit(1 if fails else 0)
