// REVIEW HARNESS (0.9.839). Runs a page with the REAL app.js against a real
// recording (a session-<model>.json copied off the phone), answering fetch the
// way the app's "Review last session" does: recorded reads by key (bank-aware),
// polite echoes for bank selects and EEPROM writes, 409 for other writes, 404
// for anything not recorded. Reports what the page's status banner says.
// Malcolm 2026-09-24: "The review allows me to see the PID and rates, but it
// does not allow me to see the travel extents ... And anything else that's missing".
// Usage: node dev/replay_test.js <session.json> [page.html ...]   (no pages = every rotorflight page + flight)
const fs = require('fs'), path = require('path'), vm = require('vm');
const sessionFile = process.argv[2];
if (!sessionFile) { console.error('usage: node dev/replay_test.js <session.json> [pages...]'); process.exit(2); }
const session = JSON.parse(fs.readFileSync(sessionFile, 'utf8'));
const entries = {};
for (const [k, e] of Object.entries(session.entries)) entries[k] = { type: e.type, body: Buffer.from(e.body, 'base64').toString('utf8') };
const pages = process.argv.slice(3).length ? process.argv.slice(3)
    : fs.readdirSync('data').filter(f => /^rotorflight-.*\.html$/.test(f) || ['flight.html', 'index.html', 'events.html', 'diagnostics.html'].includes(f)).map(f => 'data/' + f).sort();

// ---- the app's replay rules ----
let pidBank = 0, rateBank = 0;
const pidFns = new Set(['112', '94', '148', '146']);
function keyFor(pq) {
    if (!pq.startsWith('/api/msp?') || pq.includes('data=')) return pq;
    const fn = (pq.split('?')[1] || '').split('&').find(x => x.startsWith('fn='));
    const f = fn ? fn.slice(3) : '';
    if (pidFns.has(f)) return pq + '&bank=' + pidBank;
    if (f === '111') return pq + '&bank=' + rateBank;
    return pq;
}
function flightId(o) { return (o && o.count !== undefined && o.dur_ms !== undefined) ? 'flight#' + (o.saved_at || 0) + '-' + o.count + '-' + o.dur_ms : null; }
const captured = new Set([204, 202, 95, 143, 149]);
function replay(method, url) {
    const u = url.startsWith('/') ? url : '/' + url.replace(/^ble:\/\/[^/]*\//, '');
    const [p, q] = u.split('?');
    if (p === '/app/snapshot/progress') return [200, 'application/json', '{"phase":"replay","done":0,"total":0}'];
    if (p.startsWith('/app/')) return [404, 'text/plain', ''];
    if (p === '/api/msp') {
        const items = Object.fromEntries((q || '').split('&').map(x => x.split('=')));
        const fn = parseInt(items.fn || '-1');
        if (fn === 210) { const b = parseInt((items.data || '').slice(0, 2), 16); if (b & 0x80) rateBank = b & 0x7f; else pidBank = b; return [200, 'text/plain', '']; }
        // 174/154 carry an index in data= but are READS - the apps' indexedReadFns (BleSchemeHandler.swift / MainActivity.kt); keep the three in step
        if (items.data && !['174', '154'].includes(items.fn)) return captured.has(fn) ? [200, 'text/plain', ''] : [409, 'text/plain', 'receiver offline — this change cannot be made in review'];
        if (fn === 250 || fn === 68) return [200, 'text/plain', ''];
    }
    if (method === 'GET') {
        if (p === '/api/flightlog.json') {
            const n = parseInt(((q || '').split('&').find(x => x.startsWith('f=')) || 'f=0').slice(2));
            if (n > 0) {
                const list = entries['/api/flights.json'];
                try { const f = JSON.parse(list.body).find(x => x.i === n); const id = flightId(f); const hit = id && entries[id]; if (hit) return [200, hit.type, hit.body]; } catch (e) {}
                const old = entries[u]; if (old) { try { if (flightId(JSON.parse(old.body)) === flightId(JSON.parse(entries['/api/flights.json'].body).find(x => x.i === n))) return [200, old.type, old.body]; } catch (e) {} }
                return [404, 'application/json', '{"ok":false,"error":"receiver offline — reviewing the last session"}'];
            }
        }
        const hit = entries[keyFor(u)];
        if (hit) return [200, hit.type, hit.body];
    }
    if (method === 'POST' && p === '/api/time') return [200, 'application/json', '{"ok":true}'];
    return [method === 'GET' ? 404 : 409, 'application/json', '{"ok":false,"error":"receiver offline — reviewing the last session"}'];
}

// ---- a small DOM, as in page_test.js, plus real timers ----
function mkEl(id) {
    return { id, style: {}, textContent: '', innerHTML: '', value: '', checked: false, disabled: false, hidden: false, dataset: {},
        width: 300, height: 150, clientWidth: 300, clientHeight: 150, offsetWidth: 300, offsetHeight: 150, parentElement: null, parentNode: null,
        className: '', title: '', href: '', children: [], classList: { add() {}, remove() {}, contains: () => false, toggle() {} },
        get firstChild() { return this._fc || (this._fc = mkEl(this.id + ':first')); }, get lastChild() { return this.firstChild; },
        appendChild(c) { this.children.push(c); return c; }, insertBefore(c) { this.children.push(c); return c; }, prepend() {}, append() {},
        addEventListener() {}, removeEventListener() {}, scrollIntoView() {}, focus() {}, click() {}, remove() {}, closest(sel) { return mkEl('closest:' + sel); },
        setAttribute() {}, getAttribute() { return null; }, removeAttribute() {}, hasAttribute() { return false; },
        querySelector(sel) { return mkEl(String(sel)); }, querySelectorAll() { return []; }, getElementsByTagName() { return []; },
        getBoundingClientRect() { return { width: 0, height: 0, top: 0, left: 0 }; }, getContext() { return new Proxy({}, { get: (t, k) => k === 'measureText' ? () => ({ width: 10 }) : k === 'createLinearGradient' || k === 'createRadialGradient' ? () => ({ addColorStop() {} }) : () => {} }); } };
}
function runPage(file) {
    return new Promise(resolve => {
        const html = fs.readFileSync(file, 'utf8');
        const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
        const ids = new Set([...html.matchAll(/\bid=(?:"([^"]+)"|'([^']+)'|([A-Za-z0-9_-]+))/g)].map(m => m[1] || m[2] || m[3]));
        const els = {}; for (const id of ids) els[id] = mkEl(id);
        const listeners = {};
        const doc = {
            getElementById: id => els[id] || (els[id] = mkEl(id)),
            querySelectorAll: () => [], querySelector: sel => els['sel:' + sel] || (els['sel:' + sel] = mkEl(sel)),
            getElementsByTagName: () => [], getElementsByClassName: () => [], createElement: t => mkEl('new-' + t),
            addEventListener: (ev, fn) => { (listeners[ev] = listeners[ev] || []).push(fn); }, removeEventListener() {},
            documentElement: { classList: { add() {}, remove() {}, toggle() {}, contains: () => false }, style: {}, clientWidth: 400 }, body: mkEl('body'), head: mkEl('head'),
            hidden: false, visibilityState: 'visible', title: '', readyState: 'loading', cookie: '',
        };
        const errors = [], calls = [];
        const store = {};
        const sandbox = {
            console: { log() {}, warn() {}, error: (...a) => errors.push(a.join(' ')), info() {}, debug() {} },
            document: doc,
            // Real timers, capped and caught: a page that chains its load through
            // setTimeout must still run, and one page's late throw must not
            // take the whole run down.
            setTimeout: (fn, ms, ...a) => setTimeout(() => { try { const r = fn(...a); if (r && r.catch) r.catch(e => errors.push('timer: ' + e.message)); } catch (e) { errors.push('timer: ' + e.message); } }, Math.min(ms || 0, 1500)),
            clearTimeout, setInterval: () => 0, clearInterval: () => {},
            requestAnimationFrame: () => 0, cancelAnimationFrame: () => {},
            Date, Math, JSON, Promise, Array, Object, String, Number, Boolean, isFinite, isNaN, parseInt, parseFloat,
            encodeURIComponent, decodeURIComponent, encodeURI, decodeURI, RegExp, Error, Uint8Array, Int16Array, Uint16Array, Int32Array, Uint32Array, Float32Array, Float64Array, ArrayBuffer, DataView, Map, Set, WeakMap,
            URLSearchParams, URL, TextEncoder, TextDecoder, AbortController, Intl, Symbol,
            addEventListener: (ev, fn) => { (listeners['w:' + ev] = listeners['w:' + ev] || []).push(fn); }, removeEventListener: () => {}, dispatchEvent: () => true,
            matchMedia: () => ({ matches: false, addEventListener: () => {}, addListener: () => {} }),
            history: { pushState: () => {}, replaceState: () => {}, back: () => {}, length: 1 },
            navigator: { userAgent: 'replay_test', clipboard: { writeText: async () => {} }, wakeLock: null },
            alert: () => {}, confirm: () => true, prompt: () => '',
            sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
            performance: { now: () => Date.now() }, btoa: s => Buffer.from(s, 'binary').toString('base64'), atob: s => Buffer.from(s, 'base64').toString('binary'),
            localStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } },
            location: { pathname: '/' + path.basename(file, '.html').replace(/^index$/, ''), protocol: 'ble:', hostname: 'rxv2.local', search: '', hash: '', href: 'ble://rxv2.local/' + path.basename(file, '.html') },
            fetch: async (url, o) => {
                const m = (o && o.method) || 'GET';
                const [code, type, body] = replay(m, String(url));
                calls.push(m + ' ' + url + ' -> ' + code);
                return { ok: code >= 200 && code < 300, status: code, headers: { get: () => type }, text: async () => body, json: async () => JSON.parse(body) };
            },
            innerWidth: 400, innerHeight: 800, devicePixelRatio: 2, scrollTo() {}, scrollY: 0, getComputedStyle: () => ({ getPropertyValue: () => '' }),
            Image: function () { return mkEl('img'); }, screen: { width: 400, height: 800 },
        };
        sandbox.window = sandbox; sandbox.globalThis = sandbox; sandbox.self = sandbox;
        vm.createContext(sandbox);
        try { sandbox.BBCHECK = require(path.join(__dirname, '..', 'data', 'bbcheck.js')); } catch (e) {}
        const appjs = fs.readFileSync('data/app.js', 'utf8');
        let threw = null;
        try {
            for (const m of html.matchAll(/<script src="\/([a-z0-9_.-]+\.js)[^"]*"[^>]*><\/script>/g))   // e.g. /gear.js — before the inline ones, as in the browser
                if (m[1] !== 'app.js' && fs.existsSync('data/' + m[1])) vm.runInContext(fs.readFileSync('data/' + m[1], 'utf8'), sandbox, { filename: m[1] });
            for (const src of scripts) vm.runInContext(src, sandbox, { filename: file });   // inline scripts run first (defer)
            vm.runInContext(appjs, sandbox, { filename: 'app.js' });
            for (const fn of (listeners['DOMContentLoaded'] || [])) { try { const r = fn(); if (r && r.catch) r.catch(e => errors.push('DOMContentLoaded: ' + e.message)); } catch (e) { errors.push('DOMContentLoaded: ' + e.message); } }
            for (const fn of (listeners['w:load'] || [])) { try { fn(); } catch (e) { errors.push('load: ' + e.message); } }
        } catch (e) { threw = e.message; }
        setTimeout(() => {
            const st = els['status'] || {};
            resolve({ file, threw, status: (st.textContent || st.innerHTML || '').replace(/<[^>]+>/g, '').slice(0, 140), statusClass: st.className || '', errors: errors.slice(0, 3),
                      misses: calls.filter(c => / -> (404|409)$/.test(c)).map(c => c.replace(/ -> \d+$/, '')).slice(0, 6) });
        }, 2500);
    });
}
process.on('uncaughtException', e => { console.log('      (uncaught: ' + e.message + ')'); });
process.on('unhandledRejection', e => { console.log('      (unhandled: ' + (e && e.message || e) + ')'); });
// Pages that need the model LIVE by design (they move servos, copy between
// banks, or read something unsafe to record) - they must say so, plainly.
const LIVE_ONLY = { 'rotorflight-copybank.html': /connect/i, 'rotorflight-easy.html': /connected/i, 'rotorflight-adjustments.html': /not in the recording/i };
(async () => {
    let bad = 0;
    for (const f of pages) {
        const r = await runPage(f);
        const base = path.basename(f);
        const okLoad = LIVE_ONLY[base] ? LIVE_ONLY[base].test(r.status)
                     : !r.threw && !/failed|error|cannot|no answer|offline/i.test(r.status) && !/bad|warn/.test(r.statusClass);
        if (!okLoad) bad++;
        console.log((okLoad ? 'PASS ' : 'FAIL ') + path.basename(f).padEnd(34) + ' ' + (r.threw ? 'THREW ' + r.threw : (r.status || '(no status text)')) +
                    (r.misses.length ? '\n      not in the recording: ' + r.misses.join(', ') : '') + (r.errors.length ? '\n      console: ' + r.errors.join(' | ') : ''));
    }
    console.log(bad ? bad + ' page(s) do not load from this recording' : 'ALL PASS');
    process.exit(bad ? 1 : 0);
})();
