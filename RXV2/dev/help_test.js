// The shared help overlay (data/app.js): the way out must be at the TOP as well
// as the bottom, and every way of closing it must work.
const fs = require('fs'), path = require('path'), vm = require('vm');
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
const mk = (tag) => { const e = { tag, className: '', style: {}, children: [], _html: '', listeners: {},
    set innerHTML(v) { this._html = v; }, get innerHTML() { return this._html; },
    appendChild(c) { this.children.push(c); c.parent = this; },
    addEventListener(ev, fn) { (this.listeners[ev] = this.listeners[ev] || []).push(fn); },
    removeEventListener() {}, remove() { if (this.parent) this.parent.children = this.parent.children.filter(x => x !== this); this.removed = true; },
    querySelector(sel) { return this._sel(sel)[0] || null; },
    querySelectorAll(sel) { return this._sel(sel); },
    _sel(sel) { const cls = sel.replace('.', ''); const n = (this._html.match(new RegExp('class="?[^">]*' + cls, 'g')) || []).length;
                return Array.from({ length: n }, () => ({ addEventListener: (ev, fn) => { this._closers = this._closers || []; this._closers.push(fn); } })); } };
    return e; };
const body = mk('body'); const docListeners = {};
const doc = { body, head: mk('head'), documentElement: mk('html'), readyState: 'complete',
    createElement: mk, createTextNode: (t) => ({ t }),
    getElementById: (id) => (id === 'helpContent' ? { innerHTML: '<h2>Ports</h2>' + '<p>x</p>'.repeat(200) } : null),
    querySelector: () => null, querySelectorAll: () => [], getElementsByTagName: () => [],
    addEventListener: (ev, fn) => { (docListeners[ev] = docListeners[ev] || []).push(fn); }, removeEventListener: () => {} };
const sandbox = { console, document: doc, location: { pathname: '/rotorflight-ports', protocol: 'http:', hostname: 'rxv2.local' },
    window: {}, navigator: { userAgent: '' }, setTimeout: () => 0, setInterval: () => 0, clearTimeout: () => {}, fetch: async () => ({ ok: true, text: async () => '', json: async () => ({}) }),
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} }, performance: { now: () => 0 }, Date, Math, JSON, Promise };
sandbox.addEventListener = () => {}; sandbox.removeEventListener = () => {};
sandbox.matchMedia = () => ({ matches: false, addEventListener: () => {} });
sandbox.history = { pushState: () => {}, replaceState: () => {} };
sandbox.sessionStorage = sandbox.localStorage;
sandbox.window = sandbox; sandbox.globalThis = sandbox; sandbox.self = sandbox;
vm.createContext(sandbox);
try { vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'data', 'app.js'), 'utf8'), sandbox, { filename: 'app.js' }); ok(true, 'app.js runs'); }
catch (e) { ok(false, 'app.js threw: ' + e.message); process.exit(1); }
ok(typeof sandbox.LDRC === 'object' && typeof sandbox.LDRC.showHelp === 'function', 'LDRC.showHelp exists');
sandbox.LDRC.showHelp();
const overlay = body.children[body.children.length - 1];
ok(!!overlay, 'the overlay is added to the page');
const h = overlay.innerHTML;
ok(/class=helpBack/.test(h), 'there is a round Back button');
ok(!/class="helpClose helpBack"/.test(h), 'it does NOT also carry helpClose, whose width:100% teal styling would win the cascade');
const topIdx = h.indexOf('helpBack'), gotItIdx = h.lastIndexOf('Got it');
ok(topIdx > -1 && topIdx < gotItIdx, 'the Back button comes BEFORE the help text, not only at the bottom');
ok(/\u2B05\uFE0F/.test(h), 'it carries the same left arrow as every page');
ok(!/helpTop|Back<\/button>/.test(h), 'no wide bar and no text label: it is the small round button');
ok(/Got it/.test(h), 'the bottom button is still there for people who read to the end');
ok((h.match(/class=helpBack|class=helpClose/g) || []).length === 2, 'there are exactly two ways out');
ok(!!docListeners.keydown && docListeners.keydown.length > 0, 'Escape is listened for');
// Escape closes it
docListeners.keydown[0]({ key: 'Escape' });
ok(overlay.removed === true, 'Escape removes the overlay');
// the CSS makes the bar stick
const css = fs.readFileSync(path.join(__dirname, '..', 'data', 'style.css'), 'utf8');
ok(/\.helpBack\{[^}]*position:fixed/.test(css), 'it is fixed, so it stays put while the help scrolls');
const hb = css.match(/\.helpBack\{[^}]*\}/)[0], bb = css.match(/\.backBtn\{[^}]*\}/)[0];
for (const rule of ['width:3em', 'height:3em', 'border-radius:50%', 'background:#f4f7f9', 'font-size:1.55em'])
    ok(hb.includes(rule) && bb.includes(rule), 'it matches the page back button on ' + rule);
ok(/z-index:101/.test(hb), 'it sits above the help overlay (z-index 101 vs the modal 100)');
// source order decides between two single-class rules: .helpBack must come last
ok(css.indexOf('.helpBack{') > css.indexOf('.helpClose{'), '.helpBack is declared AFTER .helpClose, so nothing overrides the round shape');
ok(/overlay\.querySelectorAll\('\.helpClose, \.helpBack'\)/.test(fs.readFileSync(path.join(__dirname,'..','data','app.js'),'utf8')), 'both are wired to close');
ok(/\.helpPanel\{[^}]*background:#ffffff/.test(css), 'the help panel is a solid colour (the doctrine)');
console.log(fails ? 'FAILED: ' + fails : 'ALL PASS');
process.exit(fails ? 1 : 0);
