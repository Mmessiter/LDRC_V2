// The Rates page's rates TYPE (0.9.896; Malcolm, 16 Oct 2026: "I changed it to actual using the iPhone, but I didn't
// change the numbers" - the Havok's Rotorflight-type Rate 250 / Shape 12 / Expo 40 then flew as ACTUAL's Centre 500 /
// Max Rate 120). data/rotorflight-rates.html run in node over a fake page and a fake flight controller: a new type asks
// first, then puts the bank's rates to its starting values (RATES_START, the Configurator's) - No changes nothing; Save
// writes the type and those values and keeps every other byte; ROTORFLIGHT is not offered before Rotorflight 2.3; a type
// Rotorflight does not have is never written back. And the starting values: the transmitter's table (TXV1B RF_Rates.h
// RatesStart) is the same, and Rotorflight's own formulas give 240-250 / 400 deg/s and 12.5 deg at full stick.
// 0.9.897: the curves - the page's rfRate against Rotorflight 4.6's formulas (fc/rc_rates.c, ported below) for every type
// and 4000 random settings (the transmitter's RfRatesCurve is checked against the same formulas: TXV1B dev/test_rates);
// the read-only Max Vel is the true full-stick speed (the Havok's ACTUAL Centre 500 / Max Rate 120 flew 500, and said 120).
//   node dev/ratestype_test.js
const fs = require('fs'), path = require('path'), vm = require('vm');
let fails = 0, passes = 0; const ok = (c, m) => { if (c) passes++; else { fails++; console.log('FAIL ' + m); } };
const html = fs.readFileSync(path.join(__dirname, '..', 'data', 'rotorflight-rates.html'), 'utf8');
const script = html.split('<script>')[1].split('</script>')[0];

function makePage(opts) {
    const els = {}, docListeners = {};
    const anything = () => new Proxy(function () {}, { get: (t, k) => (k === Symbol.toPrimitive ? () => 0 : anything()), apply: () => anything() });
    const mk = id => ({ id, value: '', textContent: '', innerHTML: '', style: {}, disabled: false, hidden: false, checked: false, classList: { add() {}, remove() {}, toggle() {} },
        listeners: {}, addEventListener(ev, fn) { (this.listeners[ev] = this.listeners[ev] || []).push(fn); }, setAttribute() {}, getAttribute() { return null; },
        querySelector: () => null, querySelectorAll: () => [], appendChild() {}, getContext: () => anything(), getBoundingClientRect: () => ({ width: 300, height: 200 }),
        clientWidth: 300, clientHeight: 200, width: 300, height: 200, matches: () => false });
    // the type list, as a browser's select: a value not among the options is ''
    const sel = mk('ratesType');
    sel.options = ['0 — NONE', '1 — BETAFLIGHT', '2 — RACEFLIGHT', '3 — KISS', '4 — ACTUAL', '5 — QUICKRATES', '6 — ROTORFLIGHT'].map((text, i) => ({ value: String(i), text, disabled: false }));
    let selIdx = -1;
    Object.defineProperty(sel, 'value', { get: () => (selIdx >= 0 ? sel.options[selIdx].value : ''), set: v => { selIdx = sel.options.findIndex(o => o.value === String(v)); } });
    Object.defineProperty(sel, 'selectedIndex', { get: () => selIdx });
    sel.querySelector = q => { const m = /option\[value="(\d+)"\]/.exec(q); return m ? sel.options.find(o => o.value === m[1]) || null : null; };
    els.ratesType = sel;
    const document = {
        getElementById: id => els[id] || (els[id] = mk(id)),
        querySelector: q => (q.startsWith('#ratesType') ? sel.querySelector(q) : mk('q')),
        querySelectorAll: () => [], createElement: () => mk('new'), body: mk('body'), head: mk('head'),
        addEventListener(ev, fn) { (docListeners[ev] = docListeners[ev] || []).push(fn); },
    };
    const fc = { bytes: opts.bytes.slice(), writes: [], api: opts.api };
    const toHex = b => Array.from(b, x => x.toString(16).padStart(2, '0')).join('');
    const answers = opts.answers || [];
    const LDRC = {
        replay: false, replayReady: Promise.resolve(), dirty: false, confirmed: [],
        bankInfo: () => ({}), bankClamp: (i, k, v) => v || 0, bankCount: () => 6, bankRow: () => '', followSwitch() {}, fetchBanks: () => Promise.resolve({}),
        markStale() {}, clearStale() {}, fetchState: () => Promise.resolve({}), markDirty() { LDRC.dirty = true; }, clearDirty() { LDRC.dirty = false; },
        baseFor: (k, b, now) => now, baseNotice: () => '', relScale: (b, v) => b, relPos: () => 50, clamp5: v => v, clamp: (v) => v, endHint: () => '', showHelp() {},
        confirm: async (msg) => { LDRC.confirmed.push(msg); return answers.length ? answers.shift() : true; }, confirmLoseChanges: async () => true,
        msp: async (fn, hex) => {
            if (fn === 111) return toHex(fc.bytes);
            if (fn === 204) { const b = hex.match(/../g).map(h => parseInt(h, 16)); fc.writes.push(b); fc.bytes = b; return ''; }
            return '';
        },
    };
    const sandbox = { console, document, LDRC, Math, JSON, parseInt, parseFloat, isNaN, Number, String, Array, Uint8Array, Object, Promise, Error, Date,
        setTimeout: () => 0, clearTimeout() {}, requestAnimationFrame: () => 0, devicePixelRatio: 1,
        localStorage: { getItem: () => null, setItem() {} },
        fetch: async () => ({ ok: true, json: async () => ({ fcinfo: { api_major: 12, api_minor: fc.api } }) }) };
    sandbox.window = sandbox;
    vm.createContext(sandbox);
    vm.runInContext(script, sandbox, { filename: 'rotorflight-rates.html' });
    const fire = async (ev) => { for (const fn of (docListeners[ev] || [])) await fn({ target: {} }); };
    const run = expr => vm.runInContext(expr, sandbox);
    return { els, sel, fc, LDRC, fire, run, change: async v => { sel.value = v; for (const fn of sel.listeners.change) await fn({ target: sel }); } };
}
const settle = () => new Promise(r => setImmediate(r));
async function loaded(opts) { const p = makePage(opts); await p.fire('DOMContentLoaded'); for (let i = 0; i < 20; i++) await settle(); return p; }

// The Havok's Rate 1 on 16 Oct 2026: ACTUAL (4) with Rotorflight's own numbers; response 0, accel 0; boost gains/cutoffs,
// yaw dynamics and the cyclic ring as a Rotorflight 4.6 holds them
const havok = [4, 50, 40, 12, 7, 33, 1, 50, 40, 12, 9, 0, 2, 80, 50, 12, 11, 0, 0, 100, 0, 12, 13, 0, 0, 1, 15, 2, 15, 3, 90, 4, 15, 30, 10, 60, 150, 0];
const RS = []; // the expected starting values, per axis [rcRate, srate, expo]
const START = [[[0,0,0],[0,0,0],[0,0,0],[0,0,0]], [[120,0,0],[120,0,0],[200,0,0],[203,1,0]], [[24,0,0],[24,0,0],[40,0,0],[50,0,0]],
    [[120,0,0],[120,0,0],[200,0,0],[250,0,0]], [[18,24,0],[18,24,0],[18,40,0],[50,50,0]], [[120,24,0],[120,24,0],[200,40,0],[250,50,0]], [[50,12,40],[50,12,40],[80,12,50],[100,12,0]]];

(async () => {
    // 1. the page's table is the Configurator's (QUICKRATES' collective 50: its 104 is 26 deg)
    let p = await loaded({ bytes: havok, api: 9 });
    ok(JSON.stringify(p.run('RATES_START')) === JSON.stringify(START), 'RATES_START is the Configurator\'s starting values (QUICKRATES collective 50)');
    // 2. the Havok loads: ACTUAL, Centre 500 / Max Rate 120 / Expo 0.40 - the trap
    ok(p.sel.value === '4' && p.run('ratesTypeNow') === 4, 'the Havok reads as type 4 (ACTUAL)');
    ok(p.els.r_Roll_0.value === 500 && p.els.r_Roll_1.value === 120 && p.els.r_Roll_2.value === 40, 'its roll reads Centre 500, Max Rate 120, Expo 40 (the phone shows expo 0-100): ' + [p.els.r_Roll_0.value, p.els.r_Roll_1.value, p.els.r_Roll_2.value]);
    ok(!p.sel.options[6].disabled, 'ROTORFLIGHT offered on Rotorflight 2.3 (API 12.9)');
    // 3. a new type, answered No: nothing changes, the list goes back
    p.LDRC.dirty = false;
    await (async () => { p = await loaded({ bytes: havok, api: 9, answers: [false] }); })();
    await p.change('6');
    ok(p.LDRC.confirmed.length === 1 && /ROTORFLIGHT/.test(p.LDRC.confirmed[0]) && /starting values/.test(p.LDRC.confirmed[0]), 'a new type asks first, naming it and its starting values');
    ok(p.sel.value === '4' && JSON.stringify(Array.from(p.run('cachedRaw'))) === JSON.stringify(havok) && p.els.r_Roll_0.value === 500, 'No: the list goes back to ACTUAL, the numbers as read');
    // 4. answered Yes: ROTORFLIGHT's starting values in its own columns (Rate / Shape / Expo)
    p = await loaded({ bytes: havok, api: 9, answers: [true] });
    await p.change('6');
    const raw = Array.from(p.run('cachedRaw'));
    ok(raw[0] === 6 && raw[1] === 50 && raw[3] === 12 && raw[2] === 40 && raw[13] === 80 && raw[14] === 50 && raw[19] === 100 && raw[21] === 12 && raw[20] === 0, 'Yes: the bank at ROTORFLIGHT\'s starting values (rcRate, srate, expo per axis)');
    ok(p.els.r_Roll_0.value === 250 && p.els.r_Roll_1.value === 12 && p.els.r_Roll_2.value === 40 && p.els.r_Yaw_0.value === 400 && p.els.r_Collective_0.value === 12.5, 'shown as Rate 250 / Shape 12 / Expo 40, yaw 400, collective 12.5: ' + [p.els.r_Roll_0.value, p.els.r_Roll_1.value, p.els.r_Roll_2.value, p.els.r_Yaw_0.value, p.els.r_Collective_0.value]);
    ok(p.LDRC.dirty && p.run('ratesTypeNow') === 6, 'the page is dirty (leaving asks), the type is now ROTORFLIGHT');
    // 5. Save: the type and the starting values written, every other byte as read
    await p.run('save()');
    const w = p.fc.writes[0] || [];
    ok(p.fc.writes.length === 1 && w.length === havok.length, 'Save writes one RC_TUNING of the length read');
    ok(w[0] === 6 && w[1] === 50 && w[2] === 40 && w[3] === 12 && w[7] === 50 && w[13] === 80 && w[14] === 50 && w[15] === 12 && w[19] === 100 && w[20] === 0 && w[21] === 12, 'Save writes ROTORFLIGHT and its starting values');
    const kept = [4, 5, 6, 10, 11, 12, 16, 17, 18, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37];
    ok(kept.every(i => w[i] === havok[i]), 'every other byte (response, accel, boost, yaw dynamics, cyclic ring) as read: ' + kept.filter(i => w[i] !== havok[i]));
    // 6. ACTUAL's starting values: Centre 180, Max Rate 240 (yaw 400), collective 12.5 / 12.5, expo 0
    p = await loaded({ bytes: havok.map((b, i) => (i === 0 ? 6 : b)), api: 9, answers: [true] });
    await p.change('4');
    ok(p.els.r_Roll_0.value === 180 && p.els.r_Roll_1.value === 240 && p.els.r_Roll_2.value === 0 && p.els.r_Yaw_1.value === 400 && p.els.r_Collective_0.value === 12.5 && p.els.r_Collective_1.value === 12.5, 'ACTUAL: Centre 180, Max Rate 240, Expo 0, yaw 400, collective 12.5 / 12.5');
    // 7. every type: its own starting values in the bank
    for (let t = 0; t <= 6; t++) {
        p = await loaded({ bytes: havok.map((b, i) => (i === 0 ? (t === 4 ? 6 : 4) : b)), api: 9, answers: [true] });
        await p.change(String(t));
        const r = Array.from(p.run('cachedRaw'));
        ok(r[0] === t && [0, 1, 2, 3].every(a => r[1 + a * 6] === START[t][a][0] && r[3 + a * 6] === START[t][a][1] && r[2 + a * 6] === START[t][a][2]), 'type ' + t + ': its starting values');
    }
    // 8. Rotorflight 2.2 (API 12.8): ROTORFLIGHT is not offered
    p = await loaded({ bytes: havok, api: 8 });
    ok(p.sel.options[6].disabled && p.run('typeChosen()') === 4, 'Rotorflight 2.2: ROTORFLIGHT not offered (disabled); ACTUAL still chosen');
    // ... and a 2.2 holding 6 (Rotorflight keeps any byte it is sent): not written back
    p = await loaded({ bytes: havok.map((b, i) => (i === 0 ? 6 : b)), api: 8 });
    ok(p.run('typeChosen()') === null, 'Rotorflight 2.2 holding type 6: no type to write');
    await p.run('save()');
    ok(p.fc.writes.length === 0, 'Rotorflight 2.2 holding type 6: Save refused');
    // 9. a type Rotorflight does not have (9): shown as none, never written back - Save and Copy refused
    p = await loaded({ bytes: havok.map((b, i) => (i === 0 ? 9 : b)), api: 9 });
    ok(p.sel.value === '' && p.run('typeChosen()') === null, 'type 9 shows no type');
    await p.run('save()');
    ok(p.fc.writes.length === 0 && p.LDRC.confirmed.length === 0 && /Not saved: this bank.s rates type is 9/.test(p.els.status ? p.els.status.textContent || p.els.status.innerHTML : JSON.stringify(Object.keys(p.els))), 'type 9: Save refused before its question, and said');
    await p.run('copyTo(1)');
    ok(p.fc.writes.length === 0, 'type 9: Copy to another bank refused');
    // ... until a type is chosen: then its starting values, and Save writes
    p.LDRC.confirmed.length = 0;
    await p.change('4');
    await p.run('save()');
    ok(p.fc.writes.length === 1 && p.fc.writes[0][0] === 4 && p.fc.writes[0][1] === 18, 'a type chosen: Save writes it, with its starting values');

    // 10. the transmitter's table (TXV1B RF_Rates.h RatesStart, its order: per axis Centre/Rate, Max/Shape, Expo) is the same
    const tx = path.join(__dirname, '..', '..', '..', 'TXV1B', 'TransmitterCode', 'include', 'RF_Rates.h');
    if (fs.existsSync(tx)) {
        const m = /RatesStart\[7\]\[MAX_RATES_BYTES - 1\] PROGMEM = \{([\s\S]*?)\n\};/.exec(fs.readFileSync(tx, 'utf8'));
        const rows = m ? m[1].split('\n').map(l => /\{([\d,\s]+)\}/.exec(l)).filter(Boolean).map(x => x[1].split(',').map(Number)) : [];
        ok(rows.length === 7 && rows.every((r, t) => r.length === 12 && [0, 1, 2, 3].every(a => r[a * 3] === START[t][a][0] && r[a * 3 + 1] === START[t][a][1] && r[a * 3 + 2] === START[t][a][2])),
           'the transmitter\'s RatesStart is the same table');
    } else console.log('(the transmitter\'s RF_Rates.h is not here: its table not compared)');

    // 11. Rotorflight 4.6's own formulas (fc/rc_rates.c) at full stick: roll and pitch 240-250 deg/s, yaw 400, collective
    // 12.5 deg (480 deg/s is 12 deg) - NONE ignores the numbers (500 deg/s)
    const P = (x, n) => Math.pow(x, n);
    const rfPow = (x, e) => { const b = Math.min(e, 127); let y = x * x, z = x; if (b & 16) y *= z; z *= z; if (b & 32) y *= z; z *= z; if (b & 64) y *= z;
        z = Math.sqrt(x); if (b & 8) y *= z; z = Math.sqrt(z); if (b & 4) y *= z; z = Math.sqrt(z); if (b & 2) y *= z; z = Math.sqrt(z); if (b & 1) y *= z; return y; };
    const curve = (t, rc, sr, ex, x) => {
        const e = ex / 100;
        if (t === 1) { let r = rc * 2; if (r > 400) r += 14.54 * (r - 400); const f = x * (1 - e) + P(x, 4) * e; return r * f / Math.min(Math.max(1 - x * sr / 100, 0.01), 1); }
        if (t === 2) { const r = rc * 10, s = sr / 100; let f = x * (1 - e) + P(x, 3) * e; f += f * x * s; return r * f; }
        if (t === 3) { const r = rc * 2, s = sr / 100, f = x * (1 - e) + P(x, 3) * e; return r * f / Math.min(Math.max(1 - x * s, 0.01), 1); }
        if (t === 4) { const r = rc * 10, s = sr * 10, a = Math.max(0, s - r), f = x * (1 - e) + P(x, 5) * e; return x * (r + a * f); }
        if (t === 5) { const r = rc * 2, s = sr * 10, f = x * (1 - e) + P(x, 3) * e, m = Math.max(s, r); if (m <= 0) return 0; const su = 1 - r / m; return r * x / Math.min(Math.max(1 - f * su, 0.01), 1); }
        if (t === 6) { const r = rc * 5; return r * (x * (1 - e) + rfPow(x, sr) * e); }
        return 500 * x;
    };
    const rf46 = (t, rc, sr, ex, x) => Math.min(curve(t, rc, sr, ex, x), 2000);   // (applyRatesCurve: then at most SETPOINT_RATE_LIMIT)
    for (let t = 0; t <= 6; t++) {
        const [roll, pitch, yaw, coll] = START[t].map(([rc, sr, ex]) => curve(t, rc, sr, ex, 1));
        const deg = coll * 2.083333 / 1000 * 12;
        ok(t === 0 ? roll === 500 : (roll >= 239.9 && roll <= 250.1 && pitch === roll && Math.abs(yaw - 400) < 0.5 && Math.abs(deg - 12.5) < 0.2),
           'type ' + t + ' at full stick: roll ' + roll.toFixed(1) + ', yaw ' + yaw.toFixed(1) + ' deg/s, collective ' + deg.toFixed(2) + ' deg');
    }
    // (and the Havok's trap, in the same formulas: ACTUAL read Rotorflight's numbers as a straight 500 deg/s and 25 deg)
    ok(Math.abs(curve(4, 50, 12, 40, 1) - 500) < 0.01 && Math.abs(curve(4, 50, 12, 40, 0.5) - 250) < 0.01 && Math.abs(curve(4, 100, 12, 0, 1) * 2.083333 / 1000 * 12 - 25) < 0.1, 'the Havok\'s numbers as ACTUAL: a straight 500 deg/s, 25 deg collective');

    // 12. the page's curves: rfRate against Rotorflight's formulas, every type, 4000 random settings
    p = await loaded({ bytes: havok, api: 9 });
    let seed = 7, differ = 0, worst = '';
    const rnd = () => { seed = (seed * 1103515245 + 12345) >>> 0; return (seed >>> 8) & 0xFFFF; };
    for (let n = 0; n < 4000; n++) {
        const t = rnd() % 8, rc = rnd() % 256, sr = rnd() % 256, ex = rnd() % 101, x = (rnd() % 1001) / 1000;
        const got = p.run('rfRate(' + [t, rc, sr, ex, x].join(',') + ')'), want = rf46(t, rc, sr, ex, x);
        if (!(Math.abs(got - want) <= 1e-6 + 1e-9 * Math.abs(want))) { differ++; if (!worst) worst = [t, rc, sr, ex, x, got, want].join(' '); }
    }
    ok(differ === 0, 'the page\'s curves are Rotorflight 4.6\'s formulas (4000 points' + (differ ? ', ' + differ + ' differ: ' + worst : '') + ')');
    // 13. Max Vel: the true full-stick speed - the Havok's trap says 500, not 120
    p = await loaded({ bytes: havok, api: 9 });
    ok(p.els.r_Roll_3.value === '500' && p.els.r_Yaw_3.value === '800' && p.els.r_Collective_3.value === '25', 'the Havok as ACTUAL: Max Vel 500 / 800 deg/s and 25 deg (it copied Max Rate: 120): ' + [p.els.r_Roll_3.value, p.els.r_Yaw_3.value, p.els.r_Collective_3.value]);
    p = await loaded({ bytes: havok.map((b, i) => (i === 0 ? 6 : b)), api: 9 });
    ok(p.els.r_Roll_3.value === '250' && p.els.r_Yaw_3.value === '400' && p.els.r_Collective_3.value === '12.5', 'ROTORFLIGHT 250 / 400 / 12.5: Max Vel 250, 400 and 12.5 deg');
    // ... and it follows the table as it is typed in
    p.els.r_Roll_0.value = '300'; p.run("syncCell('Roll', 0)");
    ok(p.els.r_Roll_3.value === '300', 'Rate typed 300: Max Vel 300');

    console.log(passes + ' checks, ' + fails + ' failures');
    console.log(fails ? 'FAILED' : 'ALL PASS');
    process.exit(fails ? 1 : 0);
})().catch(e => { console.log('FAIL (threw) ' + (e && e.stack || e)); console.log('FAILED'); process.exit(1); });
