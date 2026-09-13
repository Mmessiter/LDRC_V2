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
    className: '', title: '', href: '', firstChild: null, children: [], classList: { add() {}, remove() {}, contains: () => false },
    appendChild(c) { this.children.push(c); return c; }, insertBefore(c) { this.children.push(c); return c; },
    addEventListener() {}, removeEventListener() {}, scrollIntoView() {}, focus() {}, click() {}, remove() {},
    setAttribute() {}, getAttribute() { return null; }, removeAttribute() {},
    // A created element must answer these too: a page that builds a card and
    // then looks inside it is normal, and a missing stub fails the page, not the code.
    // Same reasoning as document.querySelector: a stub, not null, so a page that
    // builds a card and then reaches inside it keeps running.
    querySelector(sel) { return mkEl(String(sel)); }, querySelectorAll() { return []; },
    getElementsByTagName() { return []; }, getBoundingClientRect() { return { width: 0, height: 0, top: 0, left: 0 }; } });
const els = {}; for (const id of ids) els[id] = mkEl(id);
const store = {};
const doc = {
    getElementById: id => els[id] || (els[id] = mkEl(id)),
    // Return a stub rather than null: the point is to RUN the page, and a null
    // here just stops the script at the first lookup instead of exercising it.
    querySelectorAll: () => [], querySelector: sel => els['sel:' + sel] || (els['sel:' + sel] = mkEl(sel)),
    getElementsByTagName: () => [], getElementsByClassName: () => [],
    createElement: t => mkEl('new-' + t),
    addEventListener: (ev, fn) => { if (ev === 'DOMContentLoaded') doc._ready = fn; },
    documentElement: { classList: { add() {}, remove() {} } }, body: mkEl('body'),
};
const calls = [];
const sandbox = {
    console, document: doc, setTimeout: (f) => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
    requestAnimationFrame: () => 0, cancelAnimationFrame: () => {},
    Date, Math, JSON, Promise, Array, Object, String, Number, Boolean, isFinite, isNaN, parseInt, parseFloat,
    encodeURIComponent, decodeURIComponent, RegExp, Error, Uint8Array, Int16Array, Float32Array, ArrayBuffer, Map, Set,
    URLSearchParams, URL, TextEncoder, TextDecoder, AbortController, Intl,
    addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => true,
    matchMedia: () => ({ matches: false, addEventListener: () => {}, addListener: () => {} }),
    history: { pushState: () => {}, replaceState: () => {}, back: () => {}, length: 1 },
    navigator: { userAgent: 'page_test', clipboard: { writeText: async () => {} } },
    alert: () => {}, confirm: () => true, prompt: () => '',
    sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    performance: { now: () => 0 }, btoa: s => Buffer.from(s, 'binary').toString('base64'),
    atob: s => Buffer.from(s, 'base64').toString('binary'),
    localStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } },
    location: { pathname: '/rotorflight-filtercheck', protocol: 'http:', hostname: 'rxv2.local' },
    fetch: async (url, o) => { calls.push((o && o.method || 'GET') + ' ' + url); return { ok: true, status: 200, text: async () => '', json: async () => ({}) }; },
    window: {},
};
sandbox.window = sandbox; sandbox.globalThis = sandbox;
// the shared helpers the page relies on
// Known members behave; anything else the page reaches for becomes a harmless
// async no-op, so one unstubbed helper cannot fail a page that is really fine.
const ldrcKnown = { state: { info: { name: 'Goblin770' } }, viaBle: false, replayReady: null, RF_API_VERIFIED: 1209,
    msp: async () => '', fetchState: async () => ({ rf: { armed: false }, usb: { device: true, host: true }, fcinfo: {}, info: { name: 'Goblin770' } }),
    confirm: async () => true, confirmLoseChanges: async () => true, showHelp() {}, markDirty() {}, clearDirty() {},
    rfVersionAlert: () => null, setText() {}, teachTime() {}, startPolling() {}, stopPolling() {} };
sandbox.LDRC = new Proxy(ldrcKnown, {
    get(t, k) { if (k in t) return t[k]; if (typeof k !== 'string') return undefined; return async () => undefined; },
    has() { return true; },
});
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
