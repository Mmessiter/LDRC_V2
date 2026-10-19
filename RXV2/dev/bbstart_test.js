// The Read black box page's start and progress, in the page's own code (0.9.899). Malcolm, 19 Oct 2026: he came from the
// Black box page's button, saw the guidance and a green button, and sat waiting for a read that had not begun; "if I
// needed to wait longer, then I think we need a progress bar here."
const path = require('path'), fs = require('fs');
const H = require(path.join(__dirname, 'page_test.js'));
const S = H.sandbox, ok = H.ok, run = H.run, calls = H.calls, els = H.els;
const D = path.join(__dirname, '..', 'data');

// ---- the progress in words
let p = run('progressWords({state:"summary"})');
ok(/flight controller/.test(p.phase) && p.pct === 0 && p.line === '', 'summary: asking the flight controller (' + p.phase + ')');
p = run('progressWords({state:"reading", start:0, end:12582912, bytes:3145728, pct:25, eta:140, window:12582912, logs:0})');
ok(/last 12.0 MB/.test(p.phase) && p.pct === 25 && /3.0 MB of 12.0 MB/.test(p.line) && /25 %/.test(p.line) && /about 2 min left/.test(p.line), 'reading: how far and how long (' + p.line + ')');
p = run('progressWords({state:"reading", start:0, end:12582912, bytes:12000000, pct:95, eta:9, window:12582912, logs:2, hs:1325})');
ok(/2 flights found/.test(p.phase) && /1325 rpm/.test(p.phase) && /9 s left/.test(p.line), 'the flights found so far and the head speed (' + p.phase + ')');
p = run('progressWords({state:"reading", start:0, end:50331648, bytes:1000, pct:0, eta:0, window:50331648, logs:0})');
ok(/No flight in the last 12.0 MB/.test(p.phase) && /48.0 MB/.test(p.phase) && p.pct === 0 && !/left/.test(p.line), 'widened: says so and starts the bar again (' + p.phase + ')');
p = run('progressWords({state:"reading", start:0, end:1000, bytes:2000, eta:0})');
ok(p.pct === 100, 'never past 100 % (' + p.pct + ')');

// ---- a running read takes the card over
run('setBusy(true)');
ok(els.startBtn.style.display === 'none' && els.progWrap.style.display === '', 'busy: the button becomes the progress');
ok(els.recLink.className === 'recLink held' && els.recHold.style.display === '', 'busy: the What-to-record link waits, and says why');
ok(run('polling') === true, 'busy: the page knows a read runs');
run('setBusy(false)');
ok(els.startBtn.style.display === '' && els.progWrap.style.display === 'none' && els.recLink.className === 'recLink' && els.recHold.style.display === 'none', 'idle: the button and the link are back');

// ---- the pages' words and order
const pg = fs.readFileSync(path.join(D, 'rotorflight-filtercheck.html'), 'utf8');
ok(/id=startBtn[^>]*>[^<]*Read the black box now/.test(pg), 'the button says what it does');
ok(pg.indexOf('id=startBtn') < pg.indexOf('id=progWrap') && pg.indexOf('id=progWrap') < pg.indexOf('id=recNote'), 'button, then progress, then the guidance');
ok(!/Check the last flight/.test(pg), 'the old name is gone from the page');
const bb = fs.readFileSync(path.join(D, 'rotorflight-blackbox.html'), 'utf8');
ok(/href="\/rotorflight-filtercheck\?start=1"/.test(bb) && /Read the black box now/.test(bb), "the Black box page's button asks for the read to start");

// ---- arriving with ?start=1 starts the read by itself; without it, the page waits for the button
(async () => {
    calls.length = 0;
    await S.document._ready();
    ok(!calls.some(c => c === 'POST /api/blackbox/check'), 'without the flag the page waits for the button');
    S.history.replaceState = (st, t, url) => { S.location.search = ''; S.location.replaced = url; };
    S.location.search = '?start=1';
    calls.length = 0;
    await S.document._ready();
    ok(calls.some(c => c === 'POST /api/blackbox/check'), 'with ?start=1 the read starts at once');
    ok(S.location.search === '' && S.location.replaced === '/rotorflight-filtercheck', 'the flag is dropped from the address: a reload does not read again');
    // no USB: nothing starts, the banner says what to connect
    const realState = S.LDRC.fetchState;
    S.LDRC.fetchState = async () => ({ usb: { device: false, host: true }, rf: {}, fcinfo: {}, info: { name: 'Goblin770' } });
    S.location.search = '?start=1'; calls.length = 0;
    await S.document._ready();
    ok(!calls.some(c => c === 'POST /api/blackbox/check') && /USB cable/.test(els.needUsb.textContent), 'no cable: nothing starts, the banner says what to connect');
    S.LDRC.fetchState = realState;
    console.log(H.fails() ? 'FAILED: ' + H.fails() : 'ALL PASS');
    process.exit(H.fails() ? 1 : 0);
})();
