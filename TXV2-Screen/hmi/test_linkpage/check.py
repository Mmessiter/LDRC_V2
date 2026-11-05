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
teensy = os.path.expanduser('~/Documents/GitHub/TXV1B/TransmitterCode/lib/LdrcLink')
if os.path.isdir(teensy):
    for f in ('LdrcLink.h', 'LdrcLink.cpp'):
        check(open(os.path.join(PROJ, 'lib', 'LdrcLink', f), 'rb').read() == open(os.path.join(teensy, f), 'rb').read(), "the Teensy's copy of the link library is this one, byte for byte: " + f)
    fg = open(os.path.join(os.path.dirname(teensy), '..', 'include', 'FlightGuard.h'), encoding='utf-8', errors='replace').read()
    check('return ldrc::LE_PAGE_OPEN;' in fg and 'CurrentView == FRONTVIEW || CurrentView == TXSETUPVIEW || CurrentView == BLANKVIEW || CurrentView == 254' in fg,
          "the Teensy's LinkRefusal() refuses for a page, and names the same pages as linkPageAllows()")
print('%d checks, %d failures' % (checks, fails))
sys.exit(1 if fails else 0)
