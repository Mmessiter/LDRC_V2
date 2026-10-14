// The floating Save bar vs the on-screen keyboard (data/app.js, the
// "Keyboard-aware action bar"). Malcolm 2026-10-14, the Travel page: "the save
// to flight controller button sometimes annoyingly vanishes and cannot be
// restored when I have just edited a value". The bar must hide only while a
// box is being typed in AND the keyboard covers the window, and come back the
// moment either stops - zoomed in or not.
const fs = require('fs'), path = require('path'), vm = require('vm');
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
const src = fs.readFileSync(path.join(__dirname, '..', 'data', 'app.js'), 'utf8');
const m = src.match(/\/\/ ── Keyboard-aware action bar[\s\S]*?\n\}\)\(\);\n/);
ok(!!m, 'app.js has the keyboard-aware action bar');
ok(!/fab\.style\.transform = lift \?/.test(src), 'the old 2026-08-06 ride-up (transform on every visual-viewport scroll) is gone');

const bar = { style: {} };
let active = { tagName: 'BODY' };
const vvL = {}, winL = {}, timers = [];
const vv = { height: 664, scale: 1, offsetTop: 0, addEventListener(ev, fn) { (vvL[ev] = vvL[ev] || []).push(fn); } };
const sandbox = { console, Math, innerHeight: 664, visualViewport: vv,
    document: { querySelector: s => (s === '.fabBar' ? bar : null), get activeElement() { return active; } },
    addEventListener(ev, fn) { (winL[ev] = winL[ev] || []).push(fn); },
    setTimeout(fn, ms) { timers.push({ fn, ms }); return timers.length; } };
sandbox.window = sandbox;
vm.runInNewContext(m[0], sandbox);
const fire = (list, ev) => (list[ev] || []).forEach(fn => fn());
const runTimers = () => { const t = timers.splice(0).sort((a, b) => a.ms - b.ms); t.forEach(x => x.fn()); return t.length; };
const vis = () => bar.style.visibility === 'hidden' ? 'hidden' : 'visible';

ok(vvL.resize && vvL.resize.length === 1 && winL.focusin && winL.focusout && winL.resize, 'it listens to the viewport, the window and focus changes');

// 1. keyboard up while typing in a box -> hidden
active = { tagName: 'INPUT', type: 'number' };
fire(winL, 'focusin'); runTimers();
ok(vis() === 'visible', 'tapping a box (keyboard not up yet) leaves the bar visible');
vv.height = 364; fire(vvL, 'resize');
ok(vis() === 'hidden', 'keyboard up (300 px) while typing -> the bar steps aside');

// 2. tap ✓: focus leaves while the keyboard is still sliding away -> back at once
active = { tagName: 'BODY' };
fire(winL, 'focusout');
ok(timers.length === 3, 'leaving a box looks again three times (250, 600, 1200 ms)');
runTimers();
ok(vis() === 'visible', 'focus gone, keyboard still covering -> the bar is back (nothing is being typed)');
vv.height = 664; fire(vvL, 'resize');
ok(vis() === 'visible', '...and stays back once the keyboard has gone');

// 3. keyboard dismissed with the box still focused (iOS keeps focus) -> back
active = { tagName: 'INPUT', type: 'number' };
vv.height = 364; fire(vvL, 'resize'); ok(vis() === 'hidden', 'keyboard up again -> hidden');
vv.height = 664; fire(vvL, 'resize'); ok(vis() === 'visible', 'keyboard down, box still focused -> visible');

// 4. the page zoomed in (pinch, or iOS zooming on a small box), no keyboard -> visible
active = { tagName: 'BODY' }; vv.scale = 1.5; vv.height = 664 / 1.5; vv.offsetTop = 120;
fire(vvL, 'resize');
ok(vis() === 'visible', 'zoomed in with no keyboard -> visible (the old sum called this "covered")');
// 5. zoomed in, typing, keyboard up -> hidden; keyboard down -> visible
active = { tagName: 'INPUT', type: 'text' }; vv.height = (664 - 300) / 1.5; fire(vvL, 'resize');
ok(vis() === 'hidden', 'zoomed in, keyboard up while typing -> hidden');
vv.height = 664 / 1.5; fire(vvL, 'resize');
ok(vis() === 'visible', 'zoomed in, keyboard down -> visible');

// 6. a checkbox or a button in focus is not typing: the bar never hides for them
vv.scale = 1; active = { tagName: 'INPUT', type: 'checkbox' }; vv.height = 364; fire(vvL, 'resize');
ok(vis() === 'visible', 'a focused checkbox never hides the bar');
active = { tagName: 'BUTTON' }; fire(vvL, 'resize');
ok(vis() === 'visible', 'a focused button never hides the bar');
active = { tagName: 'SELECT' }; fire(vvL, 'resize');
ok(vis() === 'hidden', 'a select with its picker covering the window does hide it');
active = { tagName: 'BODY' }; vv.height = 664; fire(vvL, 'resize');
ok(vis() === 'visible' && bar.style.transform === '' && bar.style.paddingBottom === '', 'at rest: visible, no transform, no padding');

console.log(fails ? 'FAIL ' + fails : 'ALL PASS');
process.exit(fails ? 1 : 0);
