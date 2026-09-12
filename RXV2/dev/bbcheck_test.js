// node dev/bbcheck_test.js <dir with *.json from bbcheck_test> — checks the decoder's stats and the page's analysis.
const fs = require('fs'), path = require('path');
const BB = require('../data/bbcheck.js');
const dir = process.argv[2] || '/tmp/bbcheck';
let fails = 0;
const ok = (cond, msg) => { console.log((cond ? 'PASS ' : 'FAIL ') + msg); if (!cond) fails++; };
const load = n => JSON.parse(fs.readFileSync(path.join(dir, n + '.json'), 'utf8'));
const parts = d => ({ summary: d.summary, fly: d.fly, gnd: d.gnd, order: d.order, orderFilt: d.orderFilt, timeline: d.timeline });
const ctx = { filters: { lpf1Hz: 100, rpmPreset: 2, rpmMinHz: 20, dynCount: 0, n1: 0, n2: 0 }, gearMain: 9.4, gearTail: 4.7, blades: 2, tailBlades: 2 };

// 1. the recommended field set, 20 s at 2 kHz
{
    const d = load('rec'), s = d.stats;
    ok(s.bad === 0 && s.resyncs === 0, 'rec: decoded with no bad frames (' + s.i + ' I, ' + s.p + ' P, ' + s.s + ' S, ' + s.e + ' E)');
    ok(s.i === 1250 && s.p === 38750, 'rec: every frame accounted for');
    ok(Math.abs(d.summary.rate - 2000) < 1, 'rec: rate measured 2000 (' + d.summary.rate + ')');
    ok(d.summary.logs.length === 1 && d.summary.logs[0].clean, 'rec: one clean log');
    const an = BB.analyse(parts(d), ctx);
    ok(an.ok, 'rec: analysis ran');
    const fixed = an.peaks.find(p => Math.abs(p.f - 190) < 3 && p.src === 'fixed');
    ok(!!fixed, 'rec: the 190 Hz fixed line is found and named "fixed" (' + JSON.stringify(fixed && { f: fixed.f, src: fixed.src, atten: fixed.atten }) + ')');
    // attenuation is the best of +/-2 bins (a narrow rotor notch must not look useless),
    // so a little of the neighbouring rotor line's attenuation leaks in: still far below a notched line
    ok(fixed && fixed.atten < 8, 'rec: the fixed line is seen to pass the filters (' + (fixed && fixed.atten) + ' dB vs ~20 for a notched one)');
    const rot2 = an.peaks.find(p => p.src === 'rotor' && p.srcOrder === 2);
    ok(!!rot2 && rot2.atten > 12, 'rec: 2/rev found and seen attenuated (' + JSON.stringify(rot2 && { f: rot2.f, atten: rot2.atten }) + ')');
    ok(an.primary && an.primary.kind === 'notch' && an.primary.action && Math.abs(an.primary.action.value - 190) <= 3, 'rec: primary advice = fixed notch near 190 Hz (' + (an.primary && an.primary.title) + ')');
    const svg = BB.svgSpectrum(parts(d), an, 0, ctx) + BB.svgOrder(parts(d), an, 0, ctx) + BB.svgTimeline(parts(d));
    ok(svg.length > 2000 && !/NaN/.test(svg), 'rec: charts render without NaN (' + svg.length + ' chars)');
    // with notch 1 already at 143: advice moves to notch 2; with both: dynamic notch
    const an2 = BB.analyse(parts(d), Object.assign({}, ctx, { filters: Object.assign({}, ctx.filters, { n1: 190 }) }));
    ok(an2.primary.kind === 'notch' && an2.primary.action.set === 'notch2', 'rec: with notch 1 taken → notch 2');
    const an3 = BB.analyse(parts(d), Object.assign({}, ctx, { filters: Object.assign({}, ctx.filters, { n1: 190, n2: 250 }) }));
    ok(an3.primary.kind === 'dyn', 'rec: with both notches taken → dynamic notch');
}
// 2. every field on
{
    const d = load('all'), s = d.stats;
    ok(s.bad === 0 && s.resyncs === 0 && s.i + s.p === 16000, 'all: every-field log decodes cleanly (' + (s.i + s.p) + ' frames)');
    ok(d.summary.header.nFields >= 70, 'all: header has ' + d.summary.header.nFields + ' fields');
}
// 3. two logs back to back, padding between: the LAST is analysed by default, the first on request
{
    const d = load('two'), s = d.stats;
    ok(s.logs === 2 && d.summary.logs.length === 2, 'two: both logs found');
    ok(d.summary.logs[1].addr > d.summary.logs[0].end, 'two: second log starts after the first ends (' + d.summary.logs[0].end + ' → ' + d.summary.logs[1].addr + ')');
    ok(d.summary.frames === 12000, 'two: the reported spectra are from one 6 s log (' + d.summary.frames + ' frames)');
    const d1 = load('two1');
    ok(d1.summary.wantLog === 1 && d1.summary.frames === 12000 && d1.stats.logs === 1, 'two: asking for log 1 stops after it');
}
// 4. a log cut off by a power cut, then erased flash
{
    const d = load('trunc');
    ok(d.summary.logs.length === 1 && d.summary.logs[0].clean === false, 'trunc: unfinished log reported as not clean');
    ok(d.stats.bad === 0, 'trunc: no bad frames');
}
// 5. corrupted bytes: resyncs but most frames survive
{
    const d = load('corrupt'), s = d.stats;
    ok(s.resyncs > 0 && s.resyncs <= 12, 'corrupt: resynced ' + s.resyncs + ' times');
    ok(s.i + s.p > 24000 * 0.95, 'corrupt: ' + (s.i + s.p) + ' of 24000 frames kept');
}
// 7. two TAG8_8SVB groups touching in the header (rssi | Tmcu): must not merge
{
    const d = load('gap'), s = d.stats;
    ok(s.bad === 0 && s.resyncs === 0 && s.i + s.p === 12000, 'gap: rssi|Tmcu adjacent groups decode cleanly (' + (s.i + s.p) + ' frames, ' + s.bad + ' bad)');
}
// 8. a bench arm after the flight: the flight's spectra must survive
{
    const d = load('bench');
    ok(d.summary.logsTotal === 2 && d.summary.log === 1 && d.summary.keptFlying === true, 'bench: newest FLYING log reported (log ' + d.summary.log + ' of ' + d.summary.logsTotal + ', keptFlying ' + d.summary.keptFlying + ')');
    ok(d.summary.hs.median > 1500 && d.summary.flyWin > 20, 'bench: its head speed and windows are the flight\'s (' + d.summary.hs.median + ' rpm, ' + d.summary.flyWin + ' windows)');
    const an = BB.analyse(parts(d), ctx);
    ok(an.signature === [d.summary.logs[0].addr, d.summary.logs[0].end, d.summary.logs[0].frames].join(':'), 'bench: signature is the flying log');
}
// 9. head speed present but never rose: a data verdict WITH a primary
{
    const d = load('zero');
    const an = BB.analyse(parts(d), ctx);
    ok(an.primary && an.primary.kind === 'data' && /stayed at/.test(an.primary.title), 'zero: primary verdict names the missing RPM signal (' + (an.primary && an.primary.title) + ')');
    const e = BB.analyse({ summary: { rate: 2000, n: 512, frames: 0, logs: [], fields: {} }, fly: {}, gnd: {} }, ctx);
    ok(e.primary && e.primary.kind === 'data', 'empty: early return still sets a primary verdict');
}
// 6. chunk size must not matter
{
    const a = load('rec'), b = load('rec4k');
    ok(a.stats.i === b.stats.i && a.stats.p === b.stats.p && JSON.stringify(a.fly) === JSON.stringify(b.fly), '4 kB chunks give the same result as 512 B');
}
// 10. THE REAL THING: 90 s of a SAB Goblin 770 at 1325 rpm, Rotorflight 4.6 on a Nexus-X,
//     read over USB by the receiver on 2026-09-12. The captured result parts and the
//     helicopter's own filter settings are the fixture: this is what the pilot sees.
{
    const parts = JSON.parse(fs.readFileSync(path.join(__dirname, 'goblin_flight_parts.json'), 'utf8'));
    const gctx = JSON.parse(fs.readFileSync(path.join(__dirname, 'goblin_flight_ctx.json'), 'utf8'));
    const an = BB.analyse(parts, gctx);
    ok(an.ok && Math.abs(an.hsMedian - 1325) < 60 && Math.abs(an.rate - 1000) < 1, 'goblin: real flight read (' + an.seconds + ' s, ' + an.hsMedian + ' rpm, ' + an.rate + '/s)');
    ok(an.fields.raw && an.fields.gyro && an.fields.hs, 'goblin: gyro raw, gyro and head speed all present');
    const rev = an.peaks.find(p => p.src === 'rotor' && p.srcOrder === 1 && p.axis === 0);
    ok(rev && rev.atten < 3, 'goblin: the 1/rev line is seen to pass the filters (' + (rev && rev.atten) + ' dB)');
    const blades = an.peaks.find(p => p.src === 'rotor' && p.srcOrder === 2);
    ok(blades && blades.atten > 12, 'goblin: the blade-passing line IS notched (' + (blades && blades.atten) + ' dB) — the filters work');
    // preset 2 already notches 1/rev, so raising it would change nothing: the advice must be mechanical
    ok(an.primary.kind === 'mech' && !an.primary.action, 'goblin: advice is mechanical, with no filter button (' + an.primary.title + ')');
    ok(!/rotor-speed notches to/.test(an.primary.title), 'goblin: does NOT advise a preset that already covers the harmonic');
    // and the preset table itself
    ok(BB.covers(2, 'rotor', 1, 0) && BB.covers(2, 'rotor', 4, 0) && !BB.covers(2, 'rotor', 5, 0), 'presets: normal covers main 1..4, not 5');
    ok(BB.presetThatCovers(2, 'rotor', 5, 0) === 3 && BB.presetThatCovers(2, 'rotor', 8, 0) === 0, 'presets: main 5 needs high; main 8 is in no preset');
    ok(BB.covers(1, 'tail', 1, 0) && !BB.covers(1, 'tail', 2, 0) && BB.presetThatCovers(1, 'tail', 2, 0) === 2, 'presets: tail 2 needs normal');
    const svg = BB.svgSpectrum(parts, an, 0, gctx) + BB.svgOrder(parts, an, 0, gctx) + BB.svgTimeline(parts);
    ok(svg.length > 4000 && !/NaN|undefined/.test(svg), 'goblin: charts render from real data (' + svg.length + ' chars)');
}
// 11. the flight traces (part 6): the channels, the summary wording and the charts
{
    const d = load('rec');
    const fl = BB.flight({ flight: d.flight });
    ok(fl && fl.rows.length > 100, 'flight: traces decoded (' + (fl && fl.rows.length) + ' rows over ' + (fl && fl.seconds) + ' s)');
    ok(fl.seen.hs && fl.seen.throttle && fl.seen.volts && fl.seen.amps && fl.seen.roll && fl.seen.govTarget, 'flight: head speed, throttle, volts, amps, attitude and governor all present');
    ok(!fl.seen.escTemp, 'flight: a channel the log does not hold is reported as absent');
    const up = fl.rows.filter(r => r[fl.idx.hs] > 1500);
    ok(up.length > 50 && Math.abs(up[up.length - 1][fl.idx.hs] - 1800) < 120, 'flight: head speed reaches the synthetic 1800 rpm (' + up[up.length - 1][fl.idx.hs] + ')');
    ok(Math.abs(fl.rows[fl.rows.length - 1][fl.idx.throttle] - 80) < 2, 'flight: throttle read as per cent (' + fl.rows[fl.rows.length - 1][fl.idx.throttle] + ')');
    ok(fl.volts.first > 24 && fl.volts.first < 26 && fl.volts.last < fl.volts.first, 'flight: battery falls over the flight (' + fl.volts.first.toFixed(1) + ' -> ' + fl.volts.last.toFixed(1) + ' V)');
    const sum = BB.flightSummary(fl);
    ok(sum.length >= 3 && /Head speed averaged \d+ rpm/.test(sum[0]), 'flight: summary leads with head speed (' + sum[0] + ')');
    ok(!/dipping to (2\d\d|[01]\d\d)\b/.test(sum[0]), 'flight: the spool-up is not reported as a dip');
    ok(/Battery 2[45]\.\d V/.test(sum.join(' ')), 'flight: volts keep their decimal');
    ok(fl.events.some(e => e.id === 52), 'flight: the airborne event is marked with a time');
    const svg = BB.svgTraces(fl, {});
    ok(svg.length > 8000 && !/NaN|undefined/.test(svg), 'flight: traces render (' + svg.length + ' chars)');
    ok((svg.match(/<svg/g) || []).length >= 5, 'flight: one panel per recorded channel group plus the time axis');
    ok(BB.flight({}) === null && BB.svgTraces(null, {}) === '', 'flight: a log without the new part is handled, not crashed');
}
console.log(fails ? ('FAILED: ' + fails) : 'ALL PASS');
process.exit(fails ? 1 : 0);
