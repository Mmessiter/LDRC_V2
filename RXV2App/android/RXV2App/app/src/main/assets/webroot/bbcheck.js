// bbcheck.js — turns the receiver's black-box check (spectra of the gyro,
// raw and filtered, over a flight) into plain-English filter advice and
// small SVG charts. Pure functions, no DOM: dev/bbcheck_test.js runs the
// same code in node over synthetic logs. Used by rotorflight-filtercheck.html.
(function (root) {
'use strict';
const BB = {};

// ---- helpers --------------------------------------------------------
const med = a => { const s = a.slice().sort((x, y) => x - y); return s.length ? s[s.length >> 1] : 0; };
const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
const r1 = v => Math.round(v * 10) / 10;

// Running-median floor of a dB spectrum (window ±w bins).
BB.floor = (db, w) => db.map((_, k) => { const a = db.slice(Math.max(0, k - w), Math.min(db.length, k + w + 1)); return med(a); });

// Peaks: local maxima standing `prom` dB above the running floor, at least minHz.
BB.peaks = (db, rate, N, opts) => {
    opts = opts || {};
    const prom = opts.prom || 8, minHz = opts.minHz || 8, w = opts.w || 24, maxHz = opts.maxHz || rate / 2;
    const fl = BB.floor(db, w), df = rate / N, out = [];
    for (let k = 2; k < db.length - 2; k++) {
        const f = k * df; if (f < minHz || f > maxHz) continue;
        if (db[k] >= db[k - 1] && db[k] > db[k + 1] && db[k] >= db[k - 2] && db[k] >= db[k + 2] && db[k] - fl[k] >= prom) {
            // refine the frequency with a parabolic fit on the three bins
            const y0 = db[k - 1], y1 = db[k], y2 = db[k + 1]; const den = y0 - 2 * y1 + y2;
            const dx = den ? clamp(0.5 * (y0 - y2) / den, -0.5, 0.5) : 0;
            out.push({ k, f: (k + dx) * df, db: db[k], prom: db[k] - fl[k] });
        }
    }
    out.sort((a, b) => b.db - a.db);
    return out;
};

// Attenuation raw→filtered around bin k (best of ±1 bins).
// A rotor-speed notch is narrow (Q 3-8) and the head speed wanders, so the cut
// can fall between FFT bins: take the best of +/-2 bins or a narrow notch looks
// ineffective when it is working (seen on the Goblin, 1/rev at 21 Hz).
const atten = (raw, filt, k) => { let best = -99; for (let j = Math.max(0, k - 2); j <= Math.min(raw.length - 1, k + 2); j++) best = Math.max(best, raw[j] - filt[j]); return best; };

// Name the source of a vibration line from its order (multiples of the head speed).
BB.source = (order, ctx) => {
    if (!(order > 0)) return { kind: 'unknown', label: 'not tied to the rotor' };
    const tol = Math.max(0.12, 1.5 * (ctx.hsSpread || 0));
    const blades = ctx.blades || 2, tailBlades = ctx.tailBlades || 2;
    const near = (o, t) => Math.abs(o - t) <= tol * Math.min(1.5, Math.max(1, t / 4));   // wider at high orders, but capped
    for (let k = 1; k <= 8; k++) if (near(order, k)) {
        if (k === 1) return { kind: 'rotor', order: 1, label: '1 per rev: main rotor out of balance or out of track' };
        if (k === blades) return { kind: 'rotor', order: k, label: k + ' per rev: main blades passing' };
        return { kind: 'rotor', order: k, label: k + ' per rev of the main rotor' };
    }
    if (ctx.gearMain > 1) for (let m = 1; m <= 2; m++) if (near(order, ctx.gearMain * m)) return { kind: 'motor', order: ctx.gearMain * m, label: (m === 1 ? 'motor speed (1 per motor rev)' : '2 per motor rev') };
    if (ctx.gearTail > 1) for (let m = 1; m <= tailBlades; m++) if (near(order, ctx.gearTail * m)) return { kind: 'tail', order: ctx.gearTail * m, label: (m === 1 ? 'tail rotor (1 per tail rev)' : 'tail blades passing') };
    return { kind: 'fixed', label: 'not a multiple of the head speed: something else vibrating (tail boom, canopy, a wire, a bearing)' };
};

// Which harmonics each rotor-speed preset actually notches, read from
// rpmFilterPreset[] in Rotorflight 4.6 (rpm_filter.c): notch_source 11..18 =
// main rotor harmonics 1..8, 21..28 = tail rotor harmonics 1..8, 10 = main
// motor. Roll and pitch get the full list; yaw's "high" is the same as normal.
// Without this the check advised "set the notches to high" for a 1/rev that
// normal already notches - it would have changed nothing (Goblin, 2026-09-12).
BB.PRESETS = {
    1: { name: 'low',    main: [1, 2, 4],          mainYaw: [1, 2],       tail: [1],    motor: false },
    2: { name: 'normal', main: [1, 2, 3, 4],       mainYaw: [1, 2, 3, 4], tail: [1, 2], motor: true },
    3: { name: 'high',   main: [1, 2, 3, 4, 5, 6], mainYaw: [1, 2, 3, 4], tail: [1, 2], motor: true },
};
BB.covers = (preset, src, harmonic, axis) => {
    const P = BB.PRESETS[preset]; if (!P) return false;
    if (src === 'motor') return P.motor;
    if (src === 'tail')  return P.tail.indexOf(harmonic) >= 0;
    return (axis === 2 ? P.mainYaw : P.main).indexOf(harmonic) >= 0;
};
// The lowest preset above `from` that would notch this line, or 0 if none does.
BB.presetThatCovers = (from, src, harmonic, axis) => {
    for (let p = Math.max(1, from + 1); p <= 3; p++) if (BB.covers(p, src, harmonic, axis)) return p;
    return 0;
};

// Head-speed spread (relative) from the histogram: how smeared the rotor lines are.
// Robust (median absolute deviation): the spool-up ramp must not widen it.
const hsSpread = hs => {
    if (!hs || !hs.hist || !(hs.median > 0)) return 0;
    let tot = 0; hs.hist.forEach(c => { tot += c; });
    if (tot < 2) return 0;
    const dev = []; hs.hist.forEach((c, i) => { if (c) dev.push([Math.abs(i * 50 + 25 - hs.median), c]); });
    dev.sort((a, b) => a[0] - b[0]);
    let acc = 0; for (const [d, c] of dev) { acc += c; if (acc * 2 >= tot) return d / hs.median; }
    return 0;
};

// ---- the analysis -----------------------------------------------------
// parts: {summary, fly, gnd, order, orderFilt, timeline} as the receiver sends them (dB × 10 ints).
// ctx: {filters:{lpf1Hz,lpf1Type,rpmPreset,rpmMinHz,dynCount,dynQ,dynMin,dynMax,n1,n1c,n2,n2c}, gearMain, gearTail, blades, tailBlades}
BB.analyse = (parts, ctx) => {
    ctx = ctx || {}; const F = ctx.filters || {};
    const S = parts.summary || {};
    const rate = S.rate || 0, N = S.n || 512;
    const res = { ok: true, rate, seconds: S.seconds || 0, frames: S.frames || 0, flyWin: S.flyWin || 0, gndWin: S.gndWin || 0,
                  fields: S.fields || {}, hsMedian: (S.hs && S.hs.median) || 0, hsMax: (S.hs && S.hs.max) || 0, hsSpread: hsSpread(S.hs),
                  logs: S.logs || [], verdicts: [], peaks: [], axes: [], notes: [] };
    const fRot = res.hsMedian / 60;
    res.fRot = fRot;
    // Apply buttons only when the flight controller's filters were actually read (the advice still stands)
    const haveF = !!(F && F.rpmPreset != null && F.lpf1Hz != null);
    const v = (kind, title, why, action) => { const o = { kind, title, why }; if (action) { if (haveF) o.action = action; else o.why += ' (The filters could not be read from the flight controller, so make the change on the Filters page.)'; } res.verdicts.push(o); if (!res.primary) res.primary = o; return o; };

    // 1. is the recording usable?
    if (!res.logs.length || !res.frames) { v('data', 'No flight in the memory', 'The black box holds no flight log. On the Flight recorder page check that recording is on (When: whenever armed, Where: flight-controller memory), tick Gyro raw, Gyro and Head speed, then fly and check again.'); res.ok = false; return res; }
    if (!res.fields.gyro && !res.fields.raw) { v('data', 'Record the gyro first', 'The log has no gyro data. On the Flight recorder page tick Gyro raw and Gyro (and Head speed), erase, fly, then check again.'); res.ok = false; return res; }
    if (!res.fields.raw) res.notes.push('No "Gyro raw" in the log: only the filtered gyro was recorded, so the raw and filtered traces are the same and the filters’ effect cannot be seen. Tick Gyro raw on the Flight recorder page for the next flight.');
    if (!res.fields.gyro) res.notes.push('No filtered gyro in the log (Gyro): the raw trace is shown alone. Tick Gyro on the Flight recorder page for the next flight.');
    if (rate && rate < 900) res.notes.push('Recorded at ' + Math.round(rate) + ' samples a second: fine up to ' + Math.round(rate / 2) + ' Hz, but vibrations above that are invisible. For a full picture set How often to 1 in 2 (2000 a second).');
    if (!res.fields.hs) v('data', 'No head speed in the log', 'Without a head-speed signal the rotor-speed notches cannot work and the lines below cannot be named. Check that the ESC telemetry (or an RPM sensor) reaches the flight controller and that Head speed is ticked on the Flight recorder page.');
    else if (res.hsMedian < 300) {
        const maxAll = Math.round((S.hs && S.hs.maxAll) || res.hsMax);
        if (maxAll < 300 && res.seconds > 20) v('data', 'The head speed stayed at ' + maxAll + ' rpm for ' + Math.round(res.seconds) + ' s', 'Either this log is a bench arm, or the RPM signal (ESC telemetry or an RPM sensor) is not reaching the flight controller — then the rotor-speed notches cannot work either. Check the head speed on the front page with the motor running, then fly and check again.');
        else v('data', 'No flight in this log', 'The head speed never rose above ' + maxAll + ' rpm, so there is no rotor vibration to look at. Fly (a hover and a few brisk moves), then check again.');
        res.ok = false; return res;
    }
    if (res.flyWin < 8) { v('data', 'Too short to judge', 'Only ' + r1(res.flyWin * N / 2 / (rate || 1)) + ' s of flight with the rotor turning. Fly longer, then check again.'); res.ok = false; return res; }

    // 2. spectra, floors and peaks per axis
    const fly = parts.fly || {}, gnd = parts.gnd || {};
    const df = rate / N;
    const bandIdx = (a, b) => [Math.max(1, Math.round(a / df)), Math.min(N / 2, Math.round(b / df))];
    const bandMed = (db, a, b) => { const [i, j] = bandIdx(a, b); return med(db.slice(i, j + 1)); };
    const AX = ['Roll', 'Pitch', 'Yaw'];
    let worstResidual = null, broadband = false, lpfAdvice = null;
    for (let a = 0; a < 3; a++) {
        const raw = (fly.raw && fly.raw[a] || []).map(x => x / 10), filt = (fly.filt && fly.filt[a] || []).map(x => x / 10);
        const graw = (gnd.raw && gnd.raw[a] || []).map(x => x / 10);
        if (!raw.length) continue;
        const floorRaw = bandMed(raw, 100, Math.min(500, rate / 2 - 10)), floorFilt = bandMed(filt, 100, Math.min(500, rate / 2 - 10));
        const floorGnd = graw.length && res.gndWin ? bandMed(graw, 100, Math.min(500, rate / 2 - 10)) : null;
        const pk = BB.peaks(raw, rate, N, { prom: 8, minHz: 8 }).slice(0, 8);
        const lines = pk.map(p => {
            const order = fRot > 0 ? p.f / fRot : 0;
            const src = BB.source(order, { hsSpread: res.hsSpread, gearMain: ctx.gearMain, gearTail: ctx.gearTail, blades: ctx.blades, tailBlades: ctx.tailBlades });
            const att = filt.length ? atten(raw, filt, p.k) : 0;
            const after = filt.length ? Math.max(filt[p.k - 1] || -99, filt[p.k], filt[p.k + 1] || -99) : p.db;
            return { axis: a, axisName: AX[a], f: r1(p.f), order: r1(order), dbRaw: r1(p.db), dbAfter: r1(after), atten: r1(att), aboveFloor: r1(after - floorFilt), prom: r1(p.prom), src: src.kind, label: src.label, srcOrder: src.order };
        });
        res.axes.push({ axis: a, name: AX[a], floorRaw: r1(floorRaw), floorFilt: r1(floorFilt), floorGnd: floorGnd == null ? null : r1(floorGnd), lines });
        res.peaks.push(...lines);
        // residual lines: still standing >= 10 dB above the filtered floor with little attenuation
        for (const L of lines) if (L.aboveFloor >= 10 && L.atten < 10 && (!worstResidual || L.dbAfter > worstResidual.dbAfter)) worstResidual = L;
        if (floorGnd != null && floorFilt - floorGnd > 15) broadband = true;
    }
    res.peaks.sort((x, y) => y.dbRaw - x.dbRaw);

    // 3. verdicts — only when the log can support them: raw AND filtered gyro (else the
    // filters' effect is invisible) AND a head speed (else rotor lines cannot be told from fixed ones)
    const canAdvise = res.fields.raw && res.fields.gyro && res.fields.hs;
    const preset = F.rpmPreset == null ? -1 : F.rpmPreset;            // 0 custom 1 low 2 normal 3 high
    const presetName = ['custom', 'low', 'normal', 'high'];
    if (!canAdvise) {
        const miss = []; if (!res.fields.raw) miss.push('Gyro raw'); if (!res.fields.gyro) miss.push('Gyro'); if (!res.fields.hs) miss.push('Head speed');
        v('data', 'Record ' + miss.join(', ') + ' for filter advice', 'The lines below are shown, but no filter change is offered: without ' + miss.join(' and ') + ' the check cannot tell what the filters removed' + (!res.fields.hs ? ' or which lines follow the rotor' : '') + '. Tick ' + (miss.length > 1 ? 'them' : 'it') + ' on the Flight recorder page, fly, then check again.');
    }
    if (worstResidual && canAdvise) {
        const L = worstResidual;
        if (L.src === 'rotor' || L.src === 'motor' || L.src === 'tail') {
            // Which harmonic is it? (1/rev = the rotor turning once, 2/rev = the two blades passing)
            const h = L.srcOrder ? Math.round(L.src === 'rotor' ? L.srcOrder : (L.src === 'motor' ? L.srcOrder / (ctx.gearMain || 1) : L.srcOrder / (ctx.gearTail || 1))) : 0;
            const nextP = BB.presetThatCovers(preset, L.src, h, L.axis);
            if (L.src === 'rotor' && h === 1) {
                // A notch at 1/rev sits inside the control band and Rotorflight already
                // has one there in every preset: a strong 1/rev is the rotor itself.
                v('mech', 'A strong once per rev: check blade tracking and balance', 'The biggest shake on ' + L.axisName.toLowerCase() + ' is ' + L.f + ' Hz, exactly once per rotor revolution, and the filters barely touch it (' + L.atten + ' dB). No filter can fix that: the rotor-speed notches already have a notch there in every preset, and anything wider would slow the controls. If the model shakes in the hover, check blade tracking, blade balance, and the head and shaft for a bend; if it flies smoothly this is normal once-per-rev motion and nothing needs doing.');
            }
            else if (!res.fields.hs) v('rpm', 'Get the head-speed signal to the flight controller', L.f + ' Hz on ' + L.axisName.toLowerCase() + ' (' + L.label + ') is still ' + L.aboveFloor + ' dB above the filtered floor. The rotor-speed notches remove exactly this, but only with a head-speed signal.');
            else if (F.rpmMinHz && L.f < F.rpmMinHz) v('rpm', 'Lower the lowest rotor frequency', L.f + ' Hz (' + L.label + ') is below the ' + F.rpmMinHz + ' Hz where the rotor-speed notches start, so they leave it alone. Set Lowest rotor frequency to ' + Math.max(10, Math.floor(L.f * 0.8)) + ' Hz.', { set: 'rpmMinHz', value: Math.max(10, Math.floor(L.f * 0.8)), text: 'Set lowest rotor frequency to ' + Math.max(10, Math.floor(L.f * 0.8)) + ' Hz' });
            else if (preset === 0) v('rpm', 'Switch the rotor-speed notches to a preset', L.f + ' Hz on ' + L.axisName.toLowerCase() + ' (' + L.label + ') gets through the filters (' + L.atten + ' dB taken out). The rotor-speed notches are set to custom, and this harmonic is missing from your table. The normal preset covers the rotor, its blades and the tail.', { set: 'rpmPreset', value: 2, text: 'Set the rotor-speed notches to normal' });
            else if (nextP) v('rpm', 'Set the rotor-speed notches to ' + BB.PRESETS[nextP].name, L.f + ' Hz on ' + L.axisName.toLowerCase() + ' (' + L.label + ') gets through the filters: only ' + L.atten + ' dB taken out, still ' + L.aboveFloor + ' dB above the rest. ' + (BB.PRESETS[preset] ? BB.PRESETS[preset].name.charAt(0).toUpperCase() + BB.PRESETS[preset].name.slice(1) : 'This preset') + ' does not notch that harmonic; ' + BB.PRESETS[nextP].name + ' does.', { set: 'rpmPreset', value: nextP, text: 'Set rotor-speed notches to ' + BB.PRESETS[nextP].name });
            else if (BB.covers(preset, L.src, h, L.axis)) {
                const spread = res.hsSpread > 0.06 ? ' The head speed also varied by about ' + Math.round(res.hsSpread * 100) + ' %, which smears a narrow notch.' : '';
                v('rpm', 'The notch for ' + L.f + ' Hz is there but not biting', L.label.charAt(0).toUpperCase() + L.label.slice(1) + ' on ' + L.axisName.toLowerCase() + ' is still ' + L.aboveFloor + ' dB above the rest, and the ' + BB.PRESETS[preset].name + ' preset does notch that harmonic. So the vibration is bigger than the notch can swallow, or the flight controller has the wrong speed for it: check the gear ratios on the First-time basics page and that the head speed on the front page matches the real one.' + spread + ' Mechanically, look for what is shaking at ' + Math.round(L.f) + ' Hz.');
            }
            else v('rpm', 'No preset notches ' + Math.round(L.f) + ' Hz', L.label.charAt(0).toUpperCase() + L.label.slice(1) + ' on ' + L.axisName.toLowerCase() + ' is ' + L.aboveFloor + ' dB above the rest, and none of the three presets covers that harmonic. A custom rotor-speed notch table can (Filters page, or the Rotorflight Configurator), or find the mechanical cause.');
        } else if (L.f < 80) {
            v('mech', 'Find what shakes at ' + Math.round(L.f) + ' Hz', L.f + ' Hz on ' + L.axisName.toLowerCase() + ' does not follow the head speed and is still ' + L.aboveFloor + ' dB above the rest. That low, a notch would sit inside the control range and slow the response, so no filter change is offered: look for the cause (tail boom, canopy, battery tray, a wire) and fly again.');
        } else {
            const cut = Math.round(L.f * 0.7);
            if (!F.n1) v('notch', 'Add a fixed notch at ' + Math.round(L.f) + ' Hz', L.f + ' Hz on ' + L.axisName.toLowerCase() + ' does not follow the head speed, so the rotor-speed notches cannot touch it (' + L.atten + ' dB taken out, still ' + L.aboveFloor + ' dB above the rest). A fixed notch at ' + Math.round(L.f) + ' Hz (cutoff ' + cut + ') removes it. Better still, find what is loose at that frequency.', { set: 'notch1', value: Math.round(L.f), cutoff: cut, text: 'Add fixed notch 1 at ' + Math.round(L.f) + ' Hz' });
            else if (!F.n2) v('notch', 'Add a second fixed notch at ' + Math.round(L.f) + ' Hz', L.f + ' Hz on ' + L.axisName.toLowerCase() + ' does not follow the head speed and notch 1 (' + F.n1 + ' Hz) is elsewhere. A second fixed notch at ' + Math.round(L.f) + ' Hz (cutoff ' + cut + ') removes it.', { set: 'notch2', value: Math.round(L.f), cutoff: cut, text: 'Add fixed notch 2 at ' + Math.round(L.f) + ' Hz' });
            else if (!F.dynCount) v('dyn', 'Turn on a dynamic notch', L.f + ' Hz on ' + L.axisName.toLowerCase() + ' does not follow the head speed and both fixed notches are in use. One dynamic notch will hunt it down by itself.', { set: 'dynCount', value: 1, text: 'Turn on 1 dynamic notch' });
            else v('dyn', 'Add another dynamic notch', L.f + ' Hz on ' + L.axisName.toLowerCase() + ' is still there with ' + F.dynCount + ' dynamic notch' + (F.dynCount > 1 ? 'es' : '') + ' and both fixed notches in use. Add one more, and look for what is loose at ' + Math.round(L.f) + ' Hz.', { set: 'dynCount', value: Math.min(8, F.dynCount + 1), text: 'Set dynamic notches to ' + Math.min(8, F.dynCount + 1) });
        }
    }
    if (broadband && canAdvise) {
        const cur = F.lpf1Hz || 0;
        if (F.dynLpfMin > 0) res.notes.push('Broadband noise in flight. Lowpass 1 follows the head speed here (dynamic, ' + F.dynLpfMin + ' to ' + F.dynLpfMax + ' Hz), so lower that range a little on the Filters page, never below 60 Hz.');
        else if (cur > 60) { const to = Math.max(60, Math.round(cur * 0.8 / 5) * 5); lpfAdvice = v('lpf', 'Lower Lowpass 1 to ' + to + ' Hz', 'Between 100 and 500 Hz the filtered gyro in flight sits well above the same gyro on the ground (grass, not lines). Lowpass 1 at ' + cur + ' Hz lets it through; ' + to + ' Hz smooths it. Never below 60 Hz.', { set: 'lpf1Hz', value: to, text: 'Set Lowpass 1 to ' + to + ' Hz' }); }
        else res.notes.push('Broadband noise in flight, but Lowpass 1 is already at ' + cur + ' Hz (Rotorflight advises not lower). Look for the mechanical cause: bearings, a bent shaft, blade balance.');
    }
    if (!res.verdicts.length && canAdvise) {
        const top = res.peaks[0];
        v('ok', 'The filters are doing their job: leave them alone', top ? 'Every vibration line is taken down to the floor. Strongest in flight: ' + top.f + ' Hz on ' + top.axisName.toLowerCase() + ' (' + top.label + '), ' + top.atten + ' dB removed.' : 'No strong vibration lines and a quiet floor.');
    }
    res.primary = res.verdicts[0];
    // signature of the flight analysed: the one-change-per-flight rule keys on it
    const idx = (S.log || res.logs.length) - (S.logsFirst || 1);
    const last = res.logs[idx] || null;
    res.signature = last ? [last.addr, last.end, last.frames].join(':') : (S.frames + ':' + S.seconds);
    res.log = S.log || 0; res.logsTotal = S.logsTotal || res.logs.length; res.keptFlying = !!S.keptFlying;
    return res;
};

// ---- charts (SVG strings; solid backgrounds) ----------------------------
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
BB.svgSpectrum = (parts, an, axis, opts) => {
    opts = opts || {};
    const S = parts.summary, rate = S.rate, N = S.n, df = rate / N;
    const raw = (parts.fly.raw[axis] || []).map(x => x / 10), filt = (parts.fly.filt && parts.fly.filt[axis] || []).map(x => x / 10);
    const maxHz = Math.min(opts.maxHz || 600, rate / 2);
    const kMax = Math.min(raw.length - 1, Math.floor(maxHz / df));
    const W = 640, H = 240, L = 40, R = 10, T = 14, B = 30;
    const vals = raw.slice(1, kMax + 1).concat(filt.slice(1, kMax + 1)).filter(v => v > -50);
    let yMin = Math.floor(Math.min.apply(null, vals) / 10) * 10 - 5, yMax = Math.ceil(Math.max.apply(null, vals) / 10) * 10 + 5;
    if (!(isFinite(yMin) && isFinite(yMax))) { yMin = -10; yMax = 60; }
    if (yMax - yMin < 30) yMax = yMin + 30;
    const x = f => L + (f / maxHz) * (W - L - R), y = d => T + (1 - (d - yMin) / (yMax - yMin)) * (H - T - B);
    const path = arr => { let d = ''; for (let k = 1; k <= kMax; k++) d += (k === 1 ? 'M' : 'L') + x(k * df).toFixed(1) + ' ' + y(clamp(arr[k], yMin, yMax)).toFixed(1); return d; };
    let g = '<svg viewBox="0 0 ' + W + ' ' + H + '" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;display:block">';
    g += '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#f4f7f9"/>';
    // grid
    const step = maxHz > 300 ? 100 : 50;
    for (let f = 0; f <= maxHz; f += step) g += '<line x1="' + x(f) + '" y1="' + T + '" x2="' + x(f) + '" y2="' + (H - B) + '" stroke="#d7dee4" stroke-width="1"/><text x="' + x(f) + '" y="' + (H - B + 14) + '" font-size="11" fill="#3a5165" text-anchor="middle">' + f + '</text>';
    for (let d = Math.ceil(yMin / 10) * 10; d <= yMax; d += 10) g += '<line x1="' + L + '" y1="' + y(d) + '" x2="' + (W - R) + '" y2="' + y(d) + '" stroke="#d7dee4" stroke-width="1"/><text x="' + (L - 4) + '" y="' + (y(d) + 4) + '" font-size="11" fill="#3a5165" text-anchor="end">' + d + '</text>';
    // rotor harmonics, motor, tail
    if (an && an.fRot > 0) {
        for (let k = 1; k <= 8; k++) { const f = k * an.fRot; if (f > maxHz) break; g += '<line x1="' + x(f) + '" y1="' + T + '" x2="' + x(f) + '" y2="' + (H - B) + '" stroke="#c98a4a" stroke-width="1" stroke-dasharray="4 3"/><text x="' + (x(f) + 2) + '" y="' + (T + 10) + '" font-size="10" fill="#8a5a24">' + k + '/rev</text>'; }
        if (opts.gearMain > 1) { const f = opts.gearMain * an.fRot; if (f <= maxHz) g += '<line x1="' + x(f) + '" y1="' + T + '" x2="' + x(f) + '" y2="' + (H - B) + '" stroke="#8e6cab" stroke-width="1" stroke-dasharray="2 3"/><text x="' + (x(f) + 2) + '" y="' + (T + 22) + '" font-size="10" fill="#5c3d7a">motor</text>'; }
        if (opts.gearTail > 1) { const f = opts.gearTail * an.fRot; if (f <= maxHz) g += '<line x1="' + x(f) + '" y1="' + T + '" x2="' + x(f) + '" y2="' + (H - B) + '" stroke="#3f8f6a" stroke-width="1" stroke-dasharray="2 3"/><text x="' + (x(f) + 2) + '" y="' + (T + 34) + '" font-size="10" fill="#2a5e45">tail</text>'; }
    }
    g += '<path d="' + path(raw) + '" fill="none" stroke="#8a97a3" stroke-width="1.2"/>';
    if (filt.length) g += '<path d="' + path(filt) + '" fill="none" stroke="#2f6fb0" stroke-width="1.6"/>';
    g += '<text x="' + (W - R) + '" y="' + (H - 4) + '" font-size="11" fill="#3a5165" text-anchor="end">Hz</text>';
    g += '<text x="' + (L + 6) + '" y="' + (H - B - 6) + '" font-size="11" fill="#8a97a3">grey: before filters</text><text x="' + (L + 6) + '" y="' + (H - B - 18) + '" font-size="11" fill="#2f6fb0">blue: after filters (what the PIDs see)</text>';
    g += '</svg>';
    return g;
};
BB.svgOrder = (parts, an, axis, opts) => {
    opts = opts || {};
    const O = parts.order, OF = parts.orderFilt; if (!O || !O.raw) return '';
    const raw = O.raw[axis].map(x => x / 10), filt = OF && OF.filt ? OF.filt[axis].map(x => x / 10) : [], cnt = O.cnt;
    const step = parts.summary.ordStep || 0.1, maxO = opts.maxOrder || 12, kMax = Math.min(raw.length - 1, Math.floor(maxO / step));
    const W = 640, H = 200, L = 40, R = 10, T = 14, B = 30;
    const vals = []; for (let k = 1; k <= kMax; k++) if (cnt[k] > 0) { vals.push(raw[k]); if (filt.length) vals.push(filt[k]); }
    if (!vals.length) return '';
    let yMin = Math.floor(Math.min.apply(null, vals) / 10) * 10 - 5, yMax = Math.ceil(Math.max.apply(null, vals) / 10) * 10 + 5; if (yMax - yMin < 30) yMax = yMin + 30;
    const x = o => L + (o / maxO) * (W - L - R), y = d => T + (1 - (d - yMin) / (yMax - yMin)) * (H - T - B);
    const path = arr => { let d = '', pen = false; for (let k = 1; k <= kMax; k++) { if (!(cnt[k] > 0)) { pen = false; continue; } d += (pen ? 'L' : 'M') + x(k * step).toFixed(1) + ' ' + y(clamp(arr[k], yMin, yMax)).toFixed(1); pen = true; } return d; };
    let g = '<svg viewBox="0 0 ' + W + ' ' + H + '" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;display:block"><rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#f4f7f9"/>';
    for (let o = 0; o <= maxO; o++) g += '<line x1="' + x(o) + '" y1="' + T + '" x2="' + x(o) + '" y2="' + (H - B) + '" stroke="' + (o ? '#e0c9a6' : '#d7dee4') + '" stroke-width="1"/><text x="' + x(o) + '" y="' + (H - B + 14) + '" font-size="11" fill="#3a5165" text-anchor="middle">' + o + '</text>';
    for (let d = Math.ceil(yMin / 10) * 10; d <= yMax; d += 10) g += '<line x1="' + L + '" y1="' + y(d) + '" x2="' + (W - R) + '" y2="' + y(d) + '" stroke="#d7dee4" stroke-width="1"/><text x="' + (L - 4) + '" y="' + (y(d) + 4) + '" font-size="11" fill="#3a5165" text-anchor="end">' + d + '</text>';
    if (opts.gearMain > 1 && opts.gearMain <= maxO) g += '<text x="' + x(opts.gearMain) + '" y="' + (T + 10) + '" font-size="10" fill="#5c3d7a" text-anchor="middle">motor</text>';
    if (opts.gearTail > 1 && opts.gearTail <= maxO) g += '<text x="' + x(opts.gearTail) + '" y="' + (T + 22) + '" font-size="10" fill="#2a5e45" text-anchor="middle">tail</text>';
    g += '<path d="' + path(raw) + '" fill="none" stroke="#8a97a3" stroke-width="1.2"/>';
    if (filt.length) g += '<path d="' + path(filt) + '" fill="none" stroke="#2f6fb0" stroke-width="1.6"/>';
    g += '<text x="' + (W - R) + '" y="' + (H - 4) + '" font-size="11" fill="#3a5165" text-anchor="end">times the head speed (per rev)</text></svg>';
    return g;
};
BB.svgTimeline = parts => {
    const TLn = parts.timeline; if (!TLn || !TLn.rows || TLn.rows.length < 2) return '';
    const rows = TLn.rows, W = 640, H = 180, L = 40, R = 44, T = 12, B = 28;
    const tMax = rows[rows.length - 1][0] || 1, hsMax = Math.max(100, Math.max.apply(null, rows.map(r => r[1])));
    const rr = rows.map(r => (r[2] + r[3] + r[4]) / 3), fr = rows.map(r => (r[5] + r[6] + r[7]) / 3);
    const vMax = Math.max(1, Math.max.apply(null, rr));
    const x = t => L + (t / tMax) * (W - L - R), yh = h => T + (1 - h / hsMax) * (H - T - B), yv = v => T + (1 - v / vMax) * (H - T - B);
    const path = (arr, yf, key) => rows.map((r, i) => (i ? 'L' : 'M') + x(r[0]).toFixed(1) + ' ' + yf(key ? r[key] : arr[i]).toFixed(1)).join('');
    let g = '<svg viewBox="0 0 ' + W + ' ' + H + '" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;display:block"><rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#f4f7f9"/>';
    const ts = tMax > 120 ? 30 : tMax > 40 ? 10 : 5;
    for (let t = 0; t <= tMax; t += ts) g += '<line x1="' + x(t) + '" y1="' + T + '" x2="' + x(t) + '" y2="' + (H - B) + '" stroke="#d7dee4"/><text x="' + x(t) + '" y="' + (H - B + 14) + '" font-size="11" fill="#3a5165" text-anchor="middle">' + Math.round(t) + ' s</text>';
    g += '<path d="' + path(null, yh, 1) + '" fill="none" stroke="#3f8f6a" stroke-width="1.6"/>';
    g += '<path d="' + path(rr, yv) + '" fill="none" stroke="#8a97a3" stroke-width="1.2"/>';
    g += '<path d="' + path(fr, yv) + '" fill="none" stroke="#2f6fb0" stroke-width="1.6"/>';
    g += '<text x="' + (W - 2) + '" y="' + (T + 10) + '" font-size="11" fill="#2a5e45" text-anchor="end">head speed</text><text x="' + (W - 2) + '" y="' + (T + 22) + '" font-size="11" fill="#2a5e45" text-anchor="end">' + Math.round(hsMax) + ' rpm</text>';
    g += '<text x="' + (L + 6) + '" y="' + (T + 10) + '" font-size="11" fill="#8a97a3">grey: shake before filters</text><text x="' + (L + 6) + '" y="' + (T + 22) + '" font-size="11" fill="#2f6fb0">blue: after</text>';
    g += '</svg>';
    return g;
};

root.BBCHECK = BB;
if (typeof module !== 'undefined' && module.exports) module.exports = BB;
})(typeof window !== 'undefined' ? window : globalThis);
