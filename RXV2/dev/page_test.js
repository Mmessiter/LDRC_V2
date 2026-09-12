// Execute a page's script in node with a small DOM/localStorage/fetch stub, so a
// ReferenceError is caught here rather than on the helicopter (the lesson of the
// 0.9.351 stuck-install bug: node --check is not enough, the page must RUN).
// Usage: node dev/page_test.js data/rotorflight-filtercheck.html
const fs = require('fs'), path = require('path'), vm = require('vm');
const file = process.argv[2] || 'data/rotorflight-filtercheck.html';
const html = fs.readFileSync(file, 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const ids = new Set([...html.matchAll(/\bid=(?:"([^"]+)"|'([^']+)'|([A-Za-z0-9_-]+))/g)].map(m => m[1] || m[2] || m[3]));

let fails = 0;
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };

// ---- the smallest DOM that lets the page's own code run ----
const mkEl = id => ({ id, style: {}, textContent: '', innerHTML: '', value: '', checked: false, disabled: false,
    className: '', title: '', firstChild: null, children: [],
    appendChild(c) { this.children.push(c); }, addEventListener() {}, scrollIntoView() {}, remove() {}, setAttribute() {}, getAttribute() { return null; } });
const els = {}; for (const id of ids) els[id] = mkEl(id);
const store = {};
const doc = {
    getElementById: id => els[id] || (els[id] = mkEl(id)),
    querySelectorAll: () => [], querySelector: () => null,
    createElement: t => mkEl('new-' + t),
    addEventListener: (ev, fn) => { if (ev === 'DOMContentLoaded') doc._ready = fn; },
    documentElement: { classList: { add() {}, remove() {} } }, body: mkEl('body'),
};
const calls = [];
const sandbox = {
    console, document: doc, setTimeout: (f) => 0, clearTimeout: () => {}, setInterval: () => 0, Date, Math, JSON, Promise, Array, Object, String, Number, isFinite, parseInt, parseFloat, encodeURIComponent, RegExp, Error, Uint8Array,
    localStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } },
    location: { pathname: '/rotorflight-filtercheck', protocol: 'http:', hostname: 'rxv2.local' },
    fetch: async (url, o) => { calls.push((o && o.method || 'GET') + ' ' + url); return { ok: true, status: 200, text: async () => '', json: async () => ({}) }; },
    window: {},
};
sandbox.window = sandbox; sandbox.globalThis = sandbox;
// the shared helpers the page relies on
sandbox.LDRC = { state: { info: { name: 'Goblin770' } }, viaBle: false, replayReady: null,
    msp: async () => '', fetchState: async () => ({ rf: { armed: false }, usb: { device: true, host: true }, fcinfo: {} }),
    confirm: async () => true, showHelp() {}, markDirty() {}, clearDirty() {}, rfVersionAlert: () => null };
const bb = require(path.join(__dirname, '..', 'data', 'bbcheck.js'));
sandbox.BBCHECK = bb;
vm.createContext(sandbox);
try { for (const src of scripts) vm.runInContext(src, sandbox, { filename: file }); ok(true, 'page script runs with no ReferenceError'); }
catch (e) { ok(false, 'page script threw: ' + e.message); process.exit(1); }

// every function the HTML calls via onclick/onchange must exist
const handlers = [...html.matchAll(/on(?:click|change)="([A-Za-z_$][\w$]*)\(/g)].map(m => m[1]);
const missing = [...new Set(handlers)].filter(f => typeof sandbox[f] !== 'function' && !/^LDRC\./.test(f));
ok(missing.length === 0, 'every onclick handler exists (' + [...new Set(handlers)].join(', ') + ')' + (missing.length ? ' MISSING: ' + missing : ''));

// Top-level `let` in a page lives in the context's lexical scope, not on the
// global object, so a test must run code IN the context to reach it.
const run = code => vm.runInContext(code, sandbox, { filename: 'test' });
module.exports = { sandbox, run, ok: (c, m) => ok(c, m), fails: () => fails, store, calls, els };
if (require.main === module) { console.log(fails ? 'FAILED: ' + fails : 'ALL PASS'); process.exit(fails ? 1 : 0); }
