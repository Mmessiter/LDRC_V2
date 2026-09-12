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
ok(/class=helpTop/.test(h), 'there is a sticky top bar');
const topIdx = h.indexOf('helpBack'), gotItIdx = h.lastIndexOf('Got it');
ok(topIdx > -1 && topIdx < gotItIdx, 'the Back button comes BEFORE the help text, not only at the bottom');
ok(/&#8592; Back/.test(h), 'it is labelled Back with an arrow');
ok(/Got it/.test(h), 'the bottom button is still there for people who read to the end');
ok((h.match(/class="helpClose helpBack"|class=helpClose/g) || []).length === 2, 'both buttons carry the close class, so both are wired');
ok(!!docListeners.keydown && docListeners.keydown.length > 0, 'Escape is listened for');
// Escape closes it
docListeners.keydown[0]({ key: 'Escape' });
ok(overlay.removed === true, 'Escape removes the overlay');
// the CSS makes the bar stick
const css = fs.readFileSync(path.join(__dirname, '..', 'data', 'style.css'), 'utf8');
ok(/\.helpTop\{[^}]*position:sticky/.test(css), 'the top bar is position:sticky, so it stays put while the help scrolls');
ok(/\.helpPanel\{[^}]*background:#ffffff/.test(css), 'the help panel is a solid colour (the doctrine)');
console.log(fails ? 'FAILED: ' + fails : 'ALL PASS');
process.exit(fails ? 1 : 0);
