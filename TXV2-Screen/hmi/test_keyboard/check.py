#!/usr/bin/env python3
"""(1.11.198) The page under the keyboard, the touch that comes too soon after a page, the main board's chatter.
   python3 hmi/test_keyboard/check.py <the renderer>          (run.sh builds it)"""
import os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
R = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'render_host', 'gen', 'render')
checks = fails = 0
def check(cond, what):
    global checks, fails
    checks += 1
    if not cond: fails += 1; print('   FAIL:', what)
def play(lines):
    """The scene's lines through the screen's own handle() (and @finger / @say); what the @say lines printed, in order."""
    d = tempfile.mkdtemp(); f = os.path.join(d, 'scene.txt'); open(f, 'w').write('\n'.join(lines) + '\n')
    r = subprocess.run([R, os.path.join(ROOT, 'sd'), f, os.path.join(d, 'out_')], capture_output=True, text=True)
    if r.returncode: print(r.stderr[-2000:]); sys.exit('test_keyboard: the renderer failed')
    return [l for l in r.stdout.split('\n') if ' = ' in l or l.startswith('page ')], r.stderr

DRAW = ['page RXOptionsView', 'n3.val=5', 'n4.val=6', 't10.txt="3.50"', 'n1.val=5', 't12.txt="120"']
# ---- 1. THE FAULT'S SCENE: Model options drawn; a finger on the trim step's box - the keyboard comes up by itself; the main board,
#         which knows nothing of it, writes the page's boxes afresh (a read that came back, a bank changed); 9 is typed, OK.
said, err = play(DRAW + ['@say page', '@say n3.val', '@finger n3', '@say page',
                         'n3.val=7', 'n4.val=12', 't10.txt="3.90"', 'n1.val=4', 't12.txt="80"',
                         't0.txt="Model"', 'b1.txt="x"', 'vis b2,0', 'click b3,0',          # (names the keyboard has too: its own parts must stay as they are)
                         '@say page', '@say b1.txt', '@say t0.txt', '@say b2.vis', '@say input.txt',
                         '@say RXOptionsView.n4.val', '@say RXOptionsView.t10.txt',
                         '@finger b200', '@finger b9', '@finger b210',                      # Delete, 9, OK
                         '@say page', '@say n3.val', '@say n4.val', '@say t10.txt', '@say n1.val', '@say t12.txt'])
want = ['page RXOptionsView', 'n3.val = 5', 'page keybdB',
        'page keybdB', 'b1.txt = "1"', 't0.txt = ""', None, 'input.txt = "5"',
        'RXOptionsView.n4.val = 12', 'RXOptionsView.t10.txt = "3.90"',
        'page RXOptionsView', 'n3.val = 9', 'n4.val = 12', 't10.txt = "3.90"', 'n1.val = 4', 't12.txt = "80"']
check(len(said) == len(want), 'scene 1 said %d things, %d were looked for: %r' % (len(said), len(want), said))
for i, (s, w) in enumerate(zip(said, want)):
    if w is not None: check(s == w, 'scene 1, line %d: %r (wanted %r)' % (i + 1, s, w))
check('not understood' not in err, 'scene 1: every command was understood (%s)' % err.strip()[-200:])
# ---- 2. Cancel instead of OK: the page comes back with what the main board wrote under the keyboard - the trim step too
said, _ = play(DRAW + ['@finger n3', 'n3.val=7', 'n4.val=12', '@finger b251', '@say page', '@say n3.val', '@say n4.val', '@say t10.txt'])
check(said == ['page RXOptionsView', 'n3.val = 7', 'n4.val = 12', 't10.txt = "3.50"'], 'scene 2 (Cancel): %r' % said)
# ---- 3. a text box's keyboard, the same; and a write that NAMES its page goes where it says, keyboard or not
said, _ = play(DRAW + ['@finger t10', '@say page', 't12.txt="60"', 'FrontView.t0.txt="x"', 'RXOptionsView.n4.val=9', '@finger b251', '@say page', '@say t12.txt', '@say n4.val', '@say FrontView.t0.txt'])
check(said == ['page keybdB', 'page RXOptionsView', 't12.txt = "60"', 'n4.val = 9', 'FrontView.t0.txt = "x"'], 'scene 3 (a text box; pages named): %r' % said)
# ---- 4. with no keyboard up nothing has changed: a write with no page named is the showing page's
said, _ = play(DRAW + ['n4.val=11', 'x9.val=3', '@say n4.val', '@say RXOptionsView.x9.val', 'page FrontView', '@say RXOptionsView.n4.val'])
check(said == ['n4.val = 11', 'RXOptionsView.x9.val = 3', 'RXOptionsView.n4.val = 11'], 'scene 4 (no keyboard): %r' % said)
# ---- 5. an old main board's "bt0.txt=Motor is ON" is heard whatever page shows - under a keyboard too (setTxt listens for it by name)
said, _ = play(DRAW + ['@say FrontView.bt0.txt', '@finger n3', 'bt0.txt="Motor is ON (test)"', '@say FrontView.bt0.txt', '@say RXOptionsView.bt0.txt'])
check(len(said) == 3 and said[0] != 'FrontView.bt0.txt = "Motor is ON (test)"' and said[1] == 'FrontView.bt0.txt = "Motor is ON (test)"' and said[2] == 'RXOptionsView.bt0.txt = ""', 'scene 5 (an old main board\'s motor word): %r' % said)

# ---- the source: the finger that lands too soon after a page; the main board's chatter kept out of the notes
src = open(os.path.join(ROOT, 'src', 'main.cpp'), encoding='utf-8', errors='replace').read()
m = re.search(r'static void pollTouch\(\) \{(.*?)\n\}\n', src, re.S); body = m.group(1) if m else ''
check(m is not None, 'pollTouch found')
i = body.find('if (pressed && !down) {'); seg = body[i:i + 1600]
check(i >= 0 and re.search(r'if \(touchLockout\) return;[^\n]*\n(?:\s*//[^\n]*\n)*\s*if \(pageUpMs && \(int32_t\) \(now - pageUpMs\) < \(int32_t\) TOUCH_AFTER_PAGE_MS\) \{ touchLockout = true; lastSeen = now; return; \}', seg) is not None,   # (19 Nov 2026: the line as it has stood since 15 Nov - counted with a sign; this pattern still looked for the line before)
      'a press that begins within TOUCH_AFTER_PAGE_MS of a page being UP (the end of its load) is not taken, and nothing is until that finger has lifted')
check(re.search(r'static const uint32_t TOUCH_AFTER_PAGE_MS = (\d+);', src) is not None and 200 <= int(re.search(r'static const uint32_t TOUCH_AFTER_PAGE_MS = (\d+);', src).group(1)) <= 300, 'TOUCH_AFTER_PAGE_MS is a quarter of a second or so')
lp = re.search(r'static bool loadPage\(const std::string &name\) \{(.*?)\n\}\n', src, re.S)
check(lp is not None and 'pageLoadedMs = millis();' in lp.group(1) and 'pageUpMs = millis() | 1;' in lp.group(1) and 'touchLockout = true;' in lp.group(1), 'loadPage stamps the moment it begins (the radios keep still) and the moment the page is UP (the touch), and locks the touch out')
h = re.search(r'static void handle\(const std::string &cmd\) \{(.*?)\n\}\n', src, re.S); hb = h.group(1) if h else ''
check('const bool quiet = chatter(cmd);' in hb and 'if (!quiet) lmCmdNote(' in hb and 'if (!quiet) recent[' in hb and re.search(r'if \(!quiet && cmd\.rfind\("Ch", 0\) != 0', hb) is not None,
      'the main board\'s markers, "sendme" and the session\'s number are kept out of the last twelve commands, the recent ring and the bench log')
ch = re.search(r'static bool chatter\(const std::string &cmd\) \{(.*?)\n\}\n', src, re.S)
check(ch is not None and all(w in ch.group(1) for w in ('cmd == "sendme"', '"ldrcsync="', 'cmd == "get ldrcsync"', '"ldrcup="', 'cmd == "get ldrcup"')), 'chatter() names exactly the five')
check(hb.count('pageUnderKeyboard()') == 3, 'handle(): vis, click and a write with no page named ask for the page under the keyboard (three places)')
check(re.search(r'if \(cmd\.rfind\("get ", 0\) == 0\) \{(.*?)\n    \}\n', hb, re.S) is not None and 'pageUnderKeyboard' not in re.search(r'if \(cmd\.rfind\("get ", 0\) == 0\) \{(.*?)\n    \}\n', hb, re.S).group(1),
      'a get is answered from the page showing, as ever (the main board tells by "sendme" that a keyboard is up)')
print('test_keyboard: %d checks, %d failures' % (checks, fails))
sys.exit(1 if fails else 0)
