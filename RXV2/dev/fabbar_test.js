// The floating Save bar vs the on-screen keyboard (data/app.js, the
// "Keyboard-aware action bar"). Malcolm 2026-10-14, the Travel page: "the save
// to flight controller button sometimes annoyingly vanishes and cannot be
// restored when I have just edited a value" and then "I should be able to
// save it without getting rid of the keyboard". So: while a box is being typed
// in AND the keyboard covers the window (zoom-proof), the bar LANDS in the
// page flow (class 'landed') - never hidden - and floats again the moment
// either stops.
const fs = require('fs'), path = require('path'), vm = require('vm');
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
const src = fs.readFileSync(path.join(__dirname, '..', 'data', 'app.js'), 'utf8');
const m = src.match(/\/\/ ── Keyboard-aware action bar[\s\S]*?\n\}\)\(\);\n/);
ok(!!m, 'app.js has the keyboard-aware action bar');
ok(!/fab\.style\.transform = lift \?/.test(src), 'the old 2026-08-06 ride-up (transform on every visual-viewport scroll) is gone');
ok(!/bar\.style\.visibility = \(covered/.test(src), 'the bar is never hidden any more');
const css = fs.readFileSync(path.join(__dirname, '..', 'data', 'style.css'), 'utf8');
ok(/\.fabBar\.landed\{position:static/.test(css), 'style.css: a landed bar is in the page flow (position:static)');

const classes = new Set();
const bar = { style: {}, classList: { toggle(c, on) { if (on) classes.add(c); else classes.delete(c); return on; }, contains: c => classes.has(c) } };
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
const where = () => (bar.style.visibility === 'hidden') ? 'hidden' : classes.has('landed') ? 'landed' : 'floating';

ok(vvL.resize && vvL.resize.length === 1 && winL.focusin && winL.focusout && winL.resize, 'it listens to the viewport, the window and focus changes');

// 1. keyboard up while typing in a box -> the bar lands in the page (not hidden)
active = { tagName: 'INPUT', type: 'number' };
fire(winL, 'focusin'); runTimers();
ok(where() === 'floating', 'tapping a box (keyboard not up yet) leaves the bar floating');
vv.height = 364; fire(vvL, 'resize');
ok(where() === 'landed', 'keyboard up (300 px) while typing -> the bar lands in the page flow');

// 2. tap ✓: focus leaves while the keyboard is still sliding away -> floating at once
active = { tagName: 'BODY' };
fire(winL, 'focusout');
ok(timers.length === 3, 'leaving a box looks again three times (250, 600, 1200 ms)');
runTimers();
ok(where() === 'floating', 'focus gone, keyboard still covering -> floating again (nothing is being typed)');
vv.height = 664; fire(vvL, 'resize');
ok(where() === 'floating', '...and stays floating once the keyboard has gone');

// 3. keyboard dismissed with the box still focused (iOS keeps focus) -> floating
active = { tagName: 'INPUT', type: 'number' };
vv.height = 364; fire(vvL, 'resize'); ok(where() === 'landed', 'keyboard up again -> landed');
vv.height = 664; fire(vvL, 'resize'); ok(where() === 'floating', 'keyboard down, box still focused -> floating');

// 4. the page zoomed in (pinch, or iOS zooming on a small box), no keyboard -> floating
active = { tagName: 'BODY' }; vv.scale = 1.5; vv.height = 664 / 1.5; vv.offsetTop = 120;
fire(vvL, 'resize');
ok(where() === 'floating', 'zoomed in with no keyboard -> floating (the old sum called this "covered")');
// 5. zoomed in, typing, keyboard up -> landed; keyboard down -> floating
active = { tagName: 'INPUT', type: 'text' }; vv.height = (664 - 300) / 1.5; fire(vvL, 'resize');
ok(where() === 'landed', 'zoomed in, keyboard up while typing -> landed');
vv.height = 664 / 1.5; fire(vvL, 'resize');
ok(where() === 'floating', 'zoomed in, keyboard down -> floating');

// 6. Android: the window itself shrinks for the keyboard -> nothing to do, it floats above it
vv.scale = 1; sandbox.innerHeight = 364; vv.height = 364; fire(vvL, 'resize');
ok(where() === 'floating', 'a window that shrinks with the keyboard (Android) keeps the bar floating');
sandbox.innerHeight = 664; vv.height = 664;

// 7. a checkbox or a button in focus is not typing: the bar never lands for them
active = { tagName: 'INPUT', type: 'checkbox' }; vv.height = 364; fire(vvL, 'resize');
ok(where() === 'floating', 'a focused checkbox never lands the bar');
active = { tagName: 'BUTTON' }; fire(vvL, 'resize');
ok(where() === 'floating', 'a focused button never lands the bar');
active = { tagName: 'SELECT' }; fire(vvL, 'resize');
ok(where() === 'landed', 'a select with its picker covering the window does land it');
active = { tagName: 'BODY' }; vv.height = 664; fire(vvL, 'resize');
ok(where() === 'floating' && bar.style.transform === '' && bar.style.paddingBottom === '', 'at rest: floating, no transform, no padding');

// 8. every page with the bar keeps it inside the container, before the footer: landed = under the last card
const dataDir = path.join(__dirname, '..', 'data');
let placed = 0, pages = 0;
for (const f of fs.readdirSync(dataDir).filter(f => f.endsWith('.html'))) {
    const h = fs.readFileSync(path.join(dataDir, f), 'utf8');
    const i = h.indexOf('class=fabBar'); if (i < 0) continue; pages++;
    const c = h.indexOf('class=container'), foot = h.indexOf('class=footer');
    if (c > -1 && c < i && foot > i) placed++;
}
ok(pages >= 11 && placed === pages, 'all ' + pages + ' pages keep the bar inside the container before the footer (' + placed + ')');

console.log(fails ? 'FAIL ' + fails : 'ALL PASS');
process.exit(fails ? 1 : 0);
