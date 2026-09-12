// The "checks kept on this phone" behaviour, exercised in the page's own code.
const path = require('path');
const H = require(path.join(__dirname, 'page_test.js'));
const S = H.sandbox, ok = H.ok, store = H.store, run = H.run;
const fs = require('fs');
const T = (process.env.TMPDIR || '/tmp') + '/bbcheck';
const real = JSON.parse(fs.readFileSync(T + '/rec.json', 'utf8'));
const parts = { summary: real.summary, fly: real.fly, gnd: real.gnd, order: real.order, timeline: real.timeline, orderFilt: real.orderFilt, flight: real.flight };

// a finished check keeps itself
S.__parts = parts;
run('parts = globalThis.__parts; analysis = BBCHECK.analyse(parts, { filters: { lpf1Hz: 100, rpmPreset: 2, rpmMinHz: 20, dynCount: 0, n1: 0, n2: 0 }, gearMain: 9.4, gearTail: 4.7 }); keepThis();');
let list = JSON.parse(store['bbcheck.kept:Goblin770'] || '[]');
ok(list.length === 1 && list[0].seconds === parts.summary.seconds, 'a finished check keeps itself (' + list.length + ' kept, ' + list[0].seconds + ' s)');
ok(Math.round(list[0].hs) === Math.round(parts.summary.hs.median), 'it remembers the head speed (' + list[0].hs + ')');

// the same flight is not kept twice
run('keepThis();');
ok(JSON.parse(store['bbcheck.kept:Goblin770']).length === 1, 'the same flight is not kept twice');

// the newest is first and only KEEP_MAX survive
for (let i = 0; i < 9; i++) run("analysis.signature = 'sig" + i + "'; keepThis();");
list = JSON.parse(store['bbcheck.kept:Goblin770']);
ok(list.length === 6, 'only the last six are kept (' + list.length + ')');
ok(list[0].sig === 'sig8', 'the newest is first (' + list[0].sig + ')');

// a full phone drops the oldest rather than losing everything
const realSet = S.localStorage.setItem; let calls = 0;
S.localStorage.setItem = (k, v) => { if (k.startsWith('bbcheck.kept') && v.length > 20000 && calls++ < 20) { const e = new Error('QuotaExceededError'); throw e; } realSet(k, v); };
run("analysis.signature = 'big'; keepThis();");
S.localStorage.setItem = realSet;
list = JSON.parse(store['bbcheck.kept:Goblin770']);
ok(list.length >= 1 && list.length < 7, 'a full phone drops the oldest instead of throwing (' + list.length + ' left)');

// opening a kept check shows it and forbids changing a filter
run('parts = null; analysis = null; openKept(0);');
ok(run('!!(parts && parts.summary)'), 'opening a kept check restores its data');
ok(run('viewingSaved') === 0, 'it is marked as a kept check');
const gate = run('applyAllowed()');
ok(!gate.ok && /kept check/.test(gate.why), 'no filter can be changed from a kept check (' + gate.why + ')');
ok(S.document.getElementById('savedBanner').style.display === '' , 'the "not live" banner is shown');

// a new live result clears that state
ok(run("typeof showResult") === 'function', 'showResult exists to clear it');
console.log(H.fails() ? 'FAILED: ' + H.fails() : 'ALL PASS');
process.exit(H.fails() ? 1 : 0);
