#!/usr/bin/env node
// Refuse a page whose inline script touches LDRC at load time.
//
// Why (0.9.748, 2026-09-17): app.js is loaded with `defer`, which means it
// runs AFTER every inline <script> in the page has already executed. So at
// the moment a page's own top-level code runs, `LDRC` does not exist yet.
// 0.9.742 put `let bankInfo = LDRC.bankInfo();` at the top level of SEVEN
// tuning pages: ReferenceError, the whole inline script aborted, and the
// pages lost every function they define — no bank buttons, no Save, nothing.
// Malcolm: "the copy from and the copy to boxes are both empty!"
//
// check_page_syntax.js parses; page_test.js executes with LDRC already
// present. Neither sees ORDER. This one does: it runs each page's inline
// scripts exactly as the browser would at parse time — with a DOM stub and
// NO LDRC — and fails on any ReferenceError. Function bodies are not run,
// so `const f = () => LDRC.x()` (lazy, fine) passes and `let v = LDRC.x()`
// (eager, broken) fails.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const DATA = process.env.PAGES_DIR || path.join(__dirname, '..', 'data');
const pages = fs.readdirSync(DATA).filter(f => f.endsWith('.html')).sort();

function domStub() {
    const el = () => ({
        style: {}, dataset: {}, classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
        addEventListener() {}, removeEventListener() {}, appendChild() {}, removeChild() {}, remove() {},
        setAttribute() {}, getAttribute() { return null; }, querySelector() { return null; },
        querySelectorAll() { return []; }, insertAdjacentHTML() {}, focus() {}, blur() {},
        children: [], childNodes: [], innerHTML: '', textContent: '', value: '', hidden: false,
    });
    const document = {
        addEventListener() {}, removeEventListener() {},
        getElementById() { return el(); }, querySelector() { return el(); }, querySelectorAll() { return []; },
        createElement() { return el(); }, createTextNode() { return el(); },
        body: el(), head: el(), documentElement: el(), readyState: 'loading', hidden: false, title: '',
        cookie: '', location: { protocol: 'http:', hostname: 'x', pathname: '/', search: '', hash: '', href: 'http://x/' },
    };
    const storage = { getItem() { return null; }, setItem() {}, removeItem() {}, clear() {} };
    const ctx = {
        document, localStorage: storage, sessionStorage: storage,
        location: document.location, navigator: { userAgent: 'check_page_order' },
        console: { log() {}, warn() {}, error() {}, info() {}, debug() {} },
        setTimeout() { return 0; }, clearTimeout() {}, setInterval() { return 0; }, clearInterval() {},
        requestAnimationFrame() { return 0; }, cancelAnimationFrame() {},
        fetch() { return new Promise(() => {}); },
        Promise, Math, JSON, Date, Number, String, Array, Object, RegExp, Error, Map, Set, parseInt, parseFloat,
        isNaN, isFinite, encodeURIComponent, decodeURIComponent, atob() { return ''; }, btoa() { return ''; },
        URLSearchParams: class { constructor() {} get() { return null; } toString() { return ''; } },
        Response: class {}, Headers: class {}, FormData: class {},
        alert() {}, confirm() { return false; }, prompt() { return null; },
        performance: { now() { return 0; } },
        matchMedia() { return { matches: false, addEventListener() {} }; },
        innerWidth: 400, innerHeight: 800, devicePixelRatio: 2,
        // NO LDRC — that is the whole point.
    };
    // A GUARDED look (`if (window.LDRC && LDRC.viaBle)`) at top level does not
    // throw - it just silently does nothing, for ever. diagnostics.html armed
    // its Bluetooth channel stream that way and never did (0.9.776: View
    // channels polled at 5/s for weeks). So consulting window.LDRC at load
    // time is a failure too. An accessor on the sandbox is invisible through
    // vm's global proxy, hence a Proxy standing in for `window`.
    const guard = new Proxy(ctx, {
        get(t, p) {
            if (p === 'LDRC') throw new ReferenceError('LDRC is not defined (window.LDRC consulted at top level - it is always undefined there)');
            return Reflect.get(t, p);
        },
    });
    ctx.window = guard; ctx.globalThis = guard; ctx.self = guard;
    return ctx;
}

let fails = 0, scripts = 0;
for (const page of pages) {
    const html = fs.readFileSync(path.join(DATA, page), 'utf8');
    const re = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi;
    let m, n = 0;
    while ((m = re.exec(html))) {
        n++; scripts++;
        const ctx = vm.createContext(domStub());
        try {
            vm.runInContext(m[1], ctx, { filename: page + '#script' + n, timeout: 2000 });
        } catch (e) {
            const msg = String(e && e.message || e);
            if (/LDRC is not defined/.test(msg)) {
                fails++;
                console.log('FAIL  ' + page + ' (script ' + n + '): ' + msg);
                console.log('      top-level code runs BEFORE app.js (defer). Move the LDRC call into');
                console.log('      the DOMContentLoaded handler, or make it a function body.');
            }
            // Any other error at load is out of scope here: a stub cannot run
            // every page fully, and page_test.js covers real execution.
        }
    }
}
if (fails) { console.log('\n' + fails + ' FAILED'); process.exit(1); }
console.log('ALL PASS  (' + pages.length + ' pages, ' + scripts + ' inline scripts run before app.js)');
