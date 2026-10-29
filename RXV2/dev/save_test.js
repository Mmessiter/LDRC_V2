// Every app page that WRITES to the flight controller, run in node over the demo's own fake flight controller
// (RXV2App/demo/demo-shim.js: realistic Rotorflight 2.3 blocks, writes kept), the day after a save wrote roll rate 0
// (28 Oct 2026, Mehul's RAW 420). Four properties, page by page:
//   1. ROUND TRIP: load, then Save with nothing edited, writes back exactly the bytes it read - no field shift, no unit
//      drift (tenths, deci-Hz, signed), no shorter or longer block.
//   2. A BLANK BOX stops the save: with every number box emptied, nothing is written (0.9.909's rule, LDRC.numOf).
//   3. A REFUSED WRITE stops the sequence: when the receiver answers 409 (armed) to the first write, no EEPROM write
//      (250) follows, and the page does not go on as if it had saved.
//   4. A SHORT BLOCK (an older Rotorflight answering fewer bytes) never becomes a longer write, nor one with NaN.
//   node dev/save_test.js            (all pages)      node dev/save_test.js pid gov-profile   (some)
const fs = require('fs'), path = require('path'), vm = require('vm');
const DATA = path.join(__dirname, '..', 'data');
const SHIM = path.join(__dirname, '..', '..', 'RXV2App', 'demo', 'demo-shim.js');
let fails = 0, passes = 0;
const ok = (c, m) => { if (c) passes++; else { fails++; console.log('FAIL ' + m); } };
const settle = async (n) => { for (let i = 0; i < (n || 60); i++) await new Promise(r => setImmediate(r)); };

// ---------------------------------------------------------------- the fake flight controller (the demo's)
function makeFc() {
    const store = {};
    const sb = { console, Response, URL, URLSearchParams, JSON, Math, Date, Promise, Array, Object, String, Number, Boolean, parseInt, parseFloat, isNaN, isFinite,
        setTimeout, clearTimeout, setInterval: () => 0, clearInterval() {}, encodeURIComponent, decodeURIComponent, Error, RegExp, Uint8Array, Map, Set,
        localStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } },
        sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
        location: { pathname: '/', search: '', hostname: 'demo', href: 'http://demo/' }, navigator: { userAgent: 'save_test' }, document: { cookie: '', addEventListener() {} },
        history: { replaceState() {}, pushState() {} } };
    sb.window = sb; sb.globalThis = sb; sb.self = sb;
    sb.window.fetch = async () => new Response('not the demo', { status: 404 });
    vm.createContext(sb);
    vm.runInContext(fs.readFileSync(SHIM, 'utf8'), sb, { filename: 'demo-shim.js' });
    return { fetch: url => sb.window.fetch(url), store };
}

// ---------------------------------------------------------------- the page in node
// the real LDRC.numOf, lifted from app.js so the test checks the rule the phones run
const appJs = fs.readFileSync(path.join(DATA, 'app.js'), 'utf8');
const numOfSrc = (() => { const i = appJs.indexOf('        numOf(id, what) {'); if (i < 0) throw new Error('numOf not found in app.js');
    const j = appJs.indexOf('\n        },\n', i); return appJs.slice(i, j + '\n        }'.length).replace(/^\s*numOf\(id, what\)/, 'function numOf(id, what)'); })();

function makePage(name, fc, opts) {
    opts = opts || {};
    const file = path.join(DATA, 'rotorflight-' + name + '.html');
    const html = fs.readFileSync(file, 'utf8');
    const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
    const numberIds = [...html.matchAll(/<input[^>]*type=number[^>]*>/g)].map(m => (m[0].match(/\bid=(?:"([^"]+)"|'([^']+)'|([A-Za-z0-9_-]+))/) || [])).map(m => m && (m[1] || m[2] || m[3])).filter(Boolean);
    const selectIds = [...html.matchAll(/<select[^>]*\bid=(?:"([^"]+)"|'([^']+)'|([A-Za-z0-9_-]+))/g)].map(m => m[1] || m[2] || m[3]);
    const checkIds = [...html.matchAll(/<input[^>]*type=checkbox[^>]*>/g)].map(m => (m[0].match(/\bid=(?:"([^"]+)"|'([^']+)'|([A-Za-z0-9_-]+))/) || [])).map(m => m && (m[1] || m[2] || m[3])).filter(Boolean);
    const ids = new Set([...html.matchAll(/\bid=(?:"([^"]+)"|'([^']+)'|([A-Za-z0-9_-]+))/g)].map(m => m[1] || m[2] || m[3]));
    const els = {};
    const mkEl = id => ({ id, style: {}, textContent: '', innerHTML: '', value: '', checked: false, disabled: false, hidden: false, className: '', title: '',
        dataset: {}, children: [], options: [], selectedIndex: -1, classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
        appendChild(c) { this.children.push(c); return c; }, insertBefore(c) { this.children.push(c); return c; }, removeChild() {}, remove() {},
        addEventListener() {}, removeEventListener() {}, scrollIntoView() {}, focus() {}, blur() {}, click() {}, matches: () => false, closest: () => null,
        setAttribute(k, v) { this.dataset[k] = v; }, getAttribute(k) { return this.dataset[k] == null ? null : this.dataset[k]; }, removeAttribute() {}, hasAttribute: () => false,
        querySelector(sel) { return els['q:' + sel] || (els['q:' + sel] = mkEl(String(sel))); }, querySelectorAll() { return []; },
        getElementsByTagName() { return []; }, getBoundingClientRect() { return { width: 300, height: 200, top: 0, left: 0 }; },
        getContext: () => new Proxy({}, { get: () => () => 0 }), width: 300, height: 200, clientWidth: 300, clientHeight: 200 });
    for (const id of ids) els[id] = mkEl(id);
    const doc = {
        getElementById: id => els[id] || (els[id] = mkEl(id)),
        querySelector: sel => els['q:' + sel] || (els['q:' + sel] = mkEl(sel)), querySelectorAll: () => [],
        getElementsByTagName: () => [], getElementsByClassName: () => [], createElement: t => mkEl('new-' + t), createTextNode: t => ({ textContent: t }),
        addEventListener(ev, fn) { (doc.listeners[ev] = doc.listeners[ev] || []).push(fn); }, listeners: {},
        documentElement: { classList: { add() {}, remove() {} }, style: {} }, body: mkEl('body'), head: mkEl('head'), hidden: false, visibilityState: 'visible',
    };
    const log = [];                       // every MSP exchange: {fn, hex (sent), reply}
    const state = { armedOnWrite: false, shortRead: null };   // shortRead: {fn, drop} - the fake FC's answer cut short
    const WRITE = new Set([33, 35, 37, 39, 43, 45, 55, 65, 68, 74, 81, 93, 95, 143, 147, 149, 171, 175, 202, 204, 205, 212, 216, 222, 250]);
    const LDRC = {
        replay: false, replayReady: Promise.resolve(), dirty: false, state: { info: { name: 'Test' }, fcinfo: { api_major: 12, api_minor: 9 } }, BANKS_MAX: 6,
        bankInfo: () => ({ pid: 6, rate: 6, shown: 0, tx_banks: 0 }), bankClamp: (i, k, v) => v || 0, bankCount: () => 6, bankMax: () => 6, bankRow() {}, followSwitch() {},
        fetchBanks: async () => ({ pid: 6, rate: 6, shown: 0, tx_banks: 0 }), startBank: async (k, r) => ({ bank: r || 0, info: { pid: 6, rate: 6, shown: 0, tx_banks: 0 }, tx: false }),
        markStale() {}, clearStale() {}, fetchState: async () => ({ rf: { armed: false }, usb: { device: true, host: true }, fcinfo: { api_major: 12, api_minor: 9, rf_major: 2, rf_minor: 3, detected: true }, info: { name: 'Test' } }),
        markDirty() { LDRC.dirty = true; }, clearDirty() { LDRC.dirty = false; },
        baseFor: (k, b, now) => now, baseNotice: () => '', baseClear() {}, baseFresh: () => false, relScale: (b, v) => b, relPos: () => 50, clamp5: v => v, clamp: v => v, endHint: () => '',
        showHelp() {}, hideHelp() {}, alert: async () => {}, rfVersionAlert: () => null, govThrottleBanner() {}, setText() {}, teachTime() {}, startPolling() {}, stopPolling() {},
        selectorPositions: () => ({ options: [4, 6], locked: false, tx: 0 }), selectorCount: (i, k, r) => (r === 4 || r === 6) ? r : 4,
        feelModel: () => null, feelRateOf: () => 0, feelExpoOf: () => 0, feelSetRate() {}, feelSetExpo() {},
        confirms: [], confirm: async (m) => { LDRC.confirms.push(typeof m === 'string' ? m : (m && m.text) || JSON.stringify(m)); return true; }, confirmLoseChanges: async () => true,
        async msp(fn, hex) {
            fn = Number(fn); const e = { fn, hex: hex || '', reply: '' }; log.push(e);
            if (state.armedOnWrite && WRITE.has(fn)) { e.reply = '409'; throw new Error('Not while armed: the model is armed.'); }
            const r = await fc.fetch('/api/msp?fn=' + fn + (hex ? '&data=' + hex : ''));
            let t = (await r.text()).trim();
            if (state.shortRead && state.shortRead.fn === fn && !hex) t = t.slice(0, Math.max(0, t.length - 2 * state.shortRead.drop));
            e.reply = t; return t;
        },
    };
    const known = LDRC;
    const ldrc = new Proxy(known, { get(t, k) { if (k in t) return t[k]; if (typeof k !== 'string') return undefined; return async () => undefined; }, has() { return true; } });
    const sandbox = { console: { log() {}, warn() {}, error() {} }, document: doc, LDRC: ldrc, Math, JSON, Date, Promise, Array, Object, String, Number, Boolean, parseInt, parseFloat, isNaN, isFinite,
        Error, RegExp, Uint8Array, Int16Array, Float32Array, ArrayBuffer, Map, Set, Symbol, encodeURIComponent, decodeURIComponent, URLSearchParams, URL, Intl,
        setTimeout: (f, ms) => { setImmediate(() => { try { f(); } catch (e) { sandbox.__timerError = e; } }); return 0; }, clearTimeout() {}, setInterval: () => 0, clearInterval() {},
        requestAnimationFrame: (f) => { setImmediate(f); return 0; }, cancelAnimationFrame() {}, devicePixelRatio: 1,
        addEventListener() {}, removeEventListener() {}, dispatchEvent: () => true, matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
        history: { pushState() {}, replaceState() {}, back() {}, length: 1 }, navigator: { userAgent: 'save_test', clipboard: { writeText: async () => {} }, vibrate() {} },
        alert() {}, confirm: () => true, prompt: () => '', performance: { now: () => Date.now() },
        localStorage: { getItem: () => null, setItem() {}, removeItem() {} }, sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
        location: { pathname: '/rotorflight-' + name, search: '', hash: '', protocol: 'http:', hostname: 'rxv2.local', href: 'http://rxv2.local/rotorflight-' + name, replace() {} },
        fetch: async (url) => fc.fetch(url), innerWidth: 390, innerHeight: 800, scrollTo() {},
    };
    sandbox.window = sandbox; sandbox.globalThis = sandbox; sandbox.self = sandbox;
    vm.createContext(sandbox);
    // the real numOf into the LDRC stub, run inside the page's own context (it reaches document)
    vm.runInContext('(' + numOfSrc + ')', sandbox, { filename: 'app.js:numOf' });
    known.numOf = vm.runInContext('(' + numOfSrc + ')', sandbox);
    for (const s of scripts) vm.runInContext(s, sandbox, { filename: 'rotorflight-' + name + '.html' });
    const run = expr => vm.runInContext(expr, sandbox, { filename: 'test' });
    const fire = async ev => { for (const fn of (doc.listeners[ev] || [])) await fn({ target: {} }); };
    return { name, els, doc, log, state, LDRC: known, run, fire, numberIds, selectIds, checkIds, html, sandbox };
}

async function loadPage(name, fc, opts) {
    const p = makePage(name, fc, opts);
    await p.fire('DOMContentLoaded'); await settle(80);
    return p;
}

// ---------------------------------------------------------------- the pages and their write pairs
// pairs: [readFn, writeFn, how] - how: 'same' (the write is the read, byte for byte); a function (readHex, writeHex) => true/false
const PAGES = {
    'pid':         { save: 'save()', pairs: [[112, 202, 'same']] },
    'pidplus':     { save: 'save()', pairs: [[94, 95, 'same']] },
    'rates':       { save: 'save()', pairs: [[111, 204, 'same']] },
    'gov-profile': { save: 'save()', pairs: [[148, 149, 'same']] },
    'rescue':      { save: 'save()', pairs: [[146, 147, 'same']] },
    'travel':      { save: 'save()', pairs: [[42, 43, 'same']] },
};
// Not yet run by default (29 Oct 2026): each needs a fixture or a stub the harness does not have yet - gov-global (its mode
// <select> is read by selectedIndex), filters (the demo answers MSP 92 with nothing: the page then writes an EMPTY 93 and says
// Saved - a length check is wanted there), servos (saveServo(i) wants a servo picked), modes (save() lives in an IIFE:
// saveRow(i)), txchannels (loads from renderAll, not DOMContentLoaded), easy (needs fcinfo.rotorflight_capable). Run one
// with   node dev/save_test.js --all gov-global
const PENDING = {
    'gov-global':  { save: 'save()', pairs: [[142, 143, 'same']] },
    'filters':     { save: 'save()', pairs: [[92, 93, 'same']] },
    'servos':      { save: 'saveServo(0)', pairs: [[120, 212, (r, w) => w.length === 2 + 32 && r.slice(2, 2 + 32) === w.slice(2)]] },   // servo 1 of the table
    'modes':       { save: 'saveRow(0)', pairs: [[34, 35, (r, w) => r.startsWith(w.slice(2))]] },                                         // one slot: idx + its 4 bytes
    'txchannels':  { save: 'saveAll()', pairs: [[64, 65, 'same']] },
    'easy':        { save: 'save()', pairs: [[111, 204, 'same'], [112, 202, 'same']] },
};
const first = (log, fn, sent) => log.find(e => e.fn === fn && (sent ? e.hex : !e.hex));
const hexOk = h => /^([0-9a-f]{2})*$/i.test(h);

async function testPage(name) {
    const cfg = PAGES[name] || PENDING[name];
    // 1. round trip
    let fc = makeFc(); let p;
    try { p = await loadPage(name, fc); } catch (e) { ok(false, name + ': the page did not load in node: ' + e.message); return; }
    const reads = p.log.filter(e => !e.hex).map(e => e.fn);
    ok(reads.length > 0, name + ': load reads the flight controller (' + reads.join(',') + ')');
    try { await p.run(cfg.save); } catch (e) { ok(false, name + ': ' + cfg.save + ' threw: ' + e.message); }
    await settle(120);
    const writes = p.log.filter(e => e.hex || e.fn === 250);
    ok(writes.some(e => e.fn !== 250 && e.fn !== 210), name + ': Save with nothing edited writes (' + writes.map(e => e.fn).join(',') + ')' + (p.els.status ? ' status: ' + (p.els.status.textContent || p.els.status.innerHTML) : ''));
    for (const [rf, wf, how] of cfg.pairs) {
        const r = first(p.log, rf), w = first(p.log, wf, true);
        if (!r || !w) { ok(false, name + ': no read ' + rf + ' / write ' + wf + ' pair seen'); continue; }
        const same = how === 'same' ? r.reply.toLowerCase() === w.hex.toLowerCase() : how(r.reply.toLowerCase(), w.hex.toLowerCase());
        ok(same, name + ': ROUND TRIP ' + rf + ' -> ' + wf + ' byte for byte' + (same ? '' : '\n      read  ' + r.reply + '\n      wrote ' + w.hex));
        ok(hexOk(w.hex), name + ': write ' + wf + ' is clean hex (' + w.hex.length / 2 + ' bytes)');
    }
    const READ_WITH_DATA = new Set([174, 210, 120]);   // reads that carry an index are not writes
    const eeprom = p.log.findIndex(e => e.fn === 250), lastWrite = p.log.map((e, i) => (e.hex && !READ_WITH_DATA.has(e.fn) ? i : -1)).filter(i => i >= 0).pop();
    ok(eeprom < 0 || lastWrite == null || eeprom > lastWrite, name + ': EEPROM write (250) comes after the block write');

    // 2. a blank box
    if (p.numberIds.length) {
        fc = makeFc(); p = await loadPage(name, fc);
        for (const id of p.numberIds) p.els[id].value = '';
        const before = p.log.length;
        try { await p.run(cfg.save); } catch (e) { /* a throw out of save is a page bug too: counted below */ p.__threw = e; }
        await settle(120);
        const after = p.log.slice(before).filter(e => (e.hex && e.fn !== 210 && e.fn !== 174) || e.fn === 250);
        ok(after.length === 0, name + ': BLANK BOXES: nothing written (' + after.map(e => e.fn).join(',') + ')');
        ok(!p.__threw, name + ': a blank box is caught by the page (' + (p.__threw && p.__threw.message) + ')');
    }

    // 3. the receiver refuses the first write (armed)
    fc = makeFc(); p = await loadPage(name, fc); p.state.armedOnWrite = true;
    { const before = p.log.length;
      try { await p.run(cfg.save); } catch (e) { p.__threw = e; }
      await settle(120);
      const after = p.log.slice(before);
      ok(!after.some(e => e.fn === 250), name + ': REFUSED WRITE: no EEPROM write follows (' + after.map(e => e.fn + (e.reply === '409' ? '!' : '')).join(',') + ')');
      ok(!p.__threw, name + ': the refusal is caught by the page (' + (p.__threw && p.__threw.message) + ')');
      const st = p.els.status ? (p.els.status.textContent || p.els.status.innerHTML || '') : '';
      ok(!/saved|✓/i.test(st) || /not/i.test(st), name + ': the page does not say Saved after a refusal (status: ' + st + ')'); }

    // 4. a short block from an older flight controller
    for (const [rf, wf] of cfg.pairs) {
        fc = makeFc(); p = makePage(name, fc); p.state.shortRead = { fn: rf, drop: 4 };
        try { await p.fire('DOMContentLoaded'); await settle(80); } catch (e) { ok(false, name + ': short block: load threw ' + e.message); continue; }
        const r = first(p.log, rf);
        try { await p.run(cfg.save); } catch (e) { p.__threw = e; }
        await settle(120);
        const w = first(p.log, wf, true);
        if (!w) { ok(true, name + ': SHORT BLOCK ' + rf + ': the save is refused or writes nothing'); continue; }
        ok(hexOk(w.hex) && w.hex.length <= (r ? r.reply.length : 0) + (typeof PAGES[name].pairs[0][2] === 'string' ? 0 : 2), name + ': SHORT BLOCK ' + rf + ' -> ' + wf + ': the write is no longer than the read and clean (' + w.hex.length / 2 + ' vs ' + (r ? r.reply.length / 2 : 0) + ' bytes)');
    }
}

(async () => {
    const want = process.argv.slice(2).filter(a => a !== '--all');
    if (process.argv.includes('--all')) Object.assign(PAGES, PENDING);
    for (const name of Object.keys(PAGES)) {
        if (want.length && !want.includes(name)) continue;
        try { await testPage(name); } catch (e) { ok(false, name + ': test crashed: ' + (e.stack || e.message)); }
    }
    console.log((fails ? 'FAILED: ' + fails + ' of ' : 'ALL PASS: ') + (passes + fails) + ' checks');
    process.exit(fails ? 1 : 0);
})();
