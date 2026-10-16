// rotorflight-diff.html (0.9.895, Malcolm 16 Oct 2026: "I think diff to sd is great too - and we don't yet have this on
// the phones (diff and execute) maybe we could ?"): the phone's Diff & execute page run in node against a make-believe
// receiver (its command line: /api/cli, /api/cli/out, /api/cli/leave) and a make-believe app (/app/diff/*, /app/awake) -
// every way a diff or an execute goes, and comes back out of the command line; then the page's sums against the
// transmitter's own (ESP32-board2 lib/LdrcCli, compiled here with dev/diff_parity.cpp) on thousands of random cases.
//   node dev/diff_test.js
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm'), cp = require('child_process'), os = require('os');
let fails = 0, checks = 0;
const ok = (c, m) => { checks++; if (!c) { fails++; console.log('FAIL ' + m); } };
const html = fs.readFileSync(path.join(__dirname, '..', 'data', 'rotorflight-diff.html'), 'utf8');
const script = html.slice(html.lastIndexOf('<script>') + 8, html.lastIndexOf('</script>'));

// ---- a Rotorflight 4.6 diff all, as the receiver hands it on (begins "# version", ends "save" - no "batch end")
const DIFF = ['# version', '# Rotorflight / STM32F7X2 (S7X2) 4.6.0 Oct  1 2025 / 12:00:00 (abc123) MSP API: 12.8', '', '# start the command batch', 'batch start', '',
    'board_name NEXUSX', '', '# feature', 'feature -RX_PARALLEL_PWM', '', '# master', 'set gov_mode = ELECTRIC', 'set gov_spoolup_time = 100',
    '', 'profile 0', '', '# profile 0', 'set pid_roll_p = 50', 'set pid_pitch_p = 52', '', 'rateprofile 0', 'set roll_rc_rate = 18', '', 'save', '# '].join('\r\n');

function page(o) {
    o = Object.assign({ usb: true, name: 'Havok', confirm: true, refuse409: '', chunks: 3, bad: [], dropAt: -1, failAt: -1, leaveRefuse: '', neverEnds: false,
                        diff: DIFF, saveError: '', stallAt: -1, files: {} }, o || {});
    const t = { o, sent: [], leaves: [], awake: [], shared: [], alerts: [], confirms: [], store: Object.assign({}, o.files), clock: new Date(2026, 9, 16, 15, 48, 5).getTime(), outs: 0, cliOpen: false };
    let pending = null;                                       // the rest of a long reply: pieces still to come from /api/cli/out
    const resp = (status, body) => ({ status, ok: status >= 200 && status < 300, text: async () => body, json: async () => JSON.parse(body) });
    async function fetch(url, opts) {
        opts = opts || {};
        const u = new URL(url, 'ble://rx'), p = u.pathname;
        if (p === '/api/cli') {
            if (!o.usb) return resp(409, 'needs the USB connection: plug the flight controller’s USB socket into the dongle or receiver');
            if (o.refuse409) return resp(409, o.refuse409);
            const cmd = u.searchParams.get('cmd');
            ok(u.searchParams.get('wait') === '5000', 'every command asks for a 5 s wait');
            const k = t.sent.length;
            t.sent.push(cmd);
            if (k === o.stallAt) t.clock += 61000;            // (the phone slept before this reply came back)
            if (k === o.failAt) throw new Error('link lost');
            if (k === o.dropAt) return resp(504, 'no reply from the flight controller');
            t.cliOpen = true;
            if (cmd === 'diff all') {
                const lines = o.diff.split('\r\n'), size = Math.ceil(lines.length / o.chunks);
                const parts = []; for (let i = 0; i < lines.length; i += size) parts.push(lines.slice(0, i + size).join('\r\n'));
                pending = { parts, at: 0 };
                return resp(parts.length > 1 || o.neverEnds ? 202 : 200, parts[0]);
            }
            const bad = o.bad.includes(cmd);
            return resp(200, cmd + '\r\n' + (bad ? '###ERROR IN ' + cmd.split(' ')[0] + ': Invalid name###\r\n' : '') + '\r\n# ');
        }
        if (p === '/api/cli/out') {
            t.outs++;
            if (!pending) return resp(409, 'the command line is not open');
            if (o.neverEnds) return resp(202, pending.parts[0]);
            pending.at++;
            const done = pending.at >= pending.parts.length - 1;
            return resp(done ? 200 : 202, pending.parts[Math.min(pending.at, pending.parts.length - 1)]);
        }
        if (p === '/api/cli/leave') {
            const save = String(opts.body).includes('save=1');
            t.leaves.push(save ? 'save' : 'exit');
            if (o.leaveRefuse) return resp(409, o.leaveRefuse);
            const was = t.cliOpen; t.cliOpen = false;
            return resp(200, !was ? 'the command line was not open' : save ? 'saved - the flight controller is restarting' : 'left without saving - the flight controller is restarting');
        }
        if (p === '/app/awake') { t.awake.push(+u.searchParams.get('s')); return resp(200, '{"ok":true}'); }
        if (p.startsWith('/app/diff/')) {
            const name = u.searchParams.get('name') || '';
            if (p === '/app/diff/list') return resp(200, JSON.stringify({ ok: true, files: Object.keys(t.store).map(n => ({ name: n, bytes: t.store[n].length })) }));
            if (p === '/app/diff/save') { if (o.saveError) return resp(200, JSON.stringify({ ok: false, error: o.saveError })); t.store[name] = String(opts.body); return resp(200, '{"ok":true}'); }
            if (p === '/app/diff/load') return resp(200, JSON.stringify(name in t.store ? { ok: true, text: t.store[name] } : { ok: false, error: 'no such diff on this phone' }));
            if (p === '/app/diff/delete') { const had = name in t.store; delete t.store[name]; return resp(200, JSON.stringify(had ? { ok: true } : { ok: false, error: 'no such diff on this phone' })); }
            if (p === '/app/diff/share') { t.shared.push(name); return resp(200, '{"ok":true}'); }
        }
        if (p === '/api/state.json') return resp(200, JSON.stringify({ usb: { device: o.usb }, info: { name: o.name } }));
        return resp(404, 'not found');
    }
    const els = {};
    const el = id => els[id] || (els[id] = { id, style: {}, textContent: '', innerHTML: '', className: '', dataset: {}, disabled: false,
        classList: { contains: () => false }, querySelectorAll: () => [] });
    const LDRC = { viaBle: true, replay: false, replayReady: Promise.resolve(false), state: null,
        async fetchState() { this.state = JSON.parse(await (await fetch('/api/state.json')).text()); return this.state; },
        async alert(m, opts) { t.alerts.push({ m, title: (opts || {}).title }); return true; },
        async confirm(m, opts) { t.confirms.push({ m, title: (opts || {}).title }); return o.confirm; } };
    const sb = { console, document: { getElementById: el, querySelectorAll: () => [], addEventListener(ev, fn) { if (ev === 'DOMContentLoaded') t.ready = fn; } }, LDRC, location: { href: '' }, URLSearchParams, URL,
        fetch, setTimeout, setInterval: () => 0, clearInterval() {}, Date, Math, JSON, Promise, Number, String, Object, Array, encodeURIComponent, __clock: () => t.clock };
    sb.window = sb; sb.addEventListener = () => {};
    vm.createContext(sb);
    vm.runInContext(script, sb, { filename: 'rotorflight-diff.html' });
    vm.runInContext('pause = async () => {}; now = () => __clock();', sb);
    t.run = js => vm.runInContext(js, sb);
    t.els = els;
    return t;
}
const last = t => t.alerts[t.alerts.length - 1] || { m: '', title: '' };

(async () => {
    // 1. Diff to phone: diff all (its start 202, the rest from /api/cli/out), kept as <Model>_<stamp>.txt, the line left without saving
    let t = page();
    await t.run('usbGate()'); await t.run('diffToPhone()');
    const want = 'Havok_2026-10-16_1548.txt';
    ok(t.sent.join('|') === 'diff all', 'diff: one command, diff all: ' + t.sent.join('|'));
    ok(t.outs === 2, 'diff: the rest fetched from /api/cli/out until whole (' + t.outs + ')');
    ok(Object.keys(t.store).join() === want, 'diff: kept as ' + want + ': ' + Object.keys(t.store).join());
    const kept = t.store[want] || '';
    ok(kept.startsWith('# version\n') && kept.endsWith('\nsave\n') && !kept.includes('\r') && !kept.includes('\n# \n'), 'diff: the lines as the transmitter writes them (no carriage returns, the prompt left out)');
    ok(t.leaves.join() === 'exit', 'diff: the command line left WITHOUT saving: ' + t.leaves.join());
    ok(last(t).title === 'Diff to phone: saved' && /Kept on this phone as Havok_2026-10-16_1548\.txt \(\d+ lines\)/.test(last(t).m) && /restarting \(nothing changed\)/.test(last(t).m), 'diff: said: ' + last(t).m);
    ok(t.awake[0] > 0 && t.awake[t.awake.length - 1] === 0, 'diff: the screen kept on while it ran, then let go: ' + t.awake.join());
    // ... with an ###ERROR line in it: kept (a comment to Execute), and said in plain words
    t = page({ diff: DIFF.replace('set gov_mode = ELECTRIC', '###ERROR IN diff: CORRUPTED CONFIG: gov_throttle_type = 3###') });
    await t.run('usbGate()'); await t.run('diffToPhone()');
    ok(Object.keys(t.store).length === 1 && /a setting out of range: gov_throttle_type = 3/.test(last(t).m), 'diff: the flight controller’s error said: ' + last(t).m);
    // ... refused by the receiver (the transmitter linked with the safety off): nothing opened, nothing to leave
    t = page({ refuse409: 'the transmitter is linked: the command line needs the safety on (arming channel 5 low)' });
    await t.run('usbGate()'); await t.run('diffToPhone()');
    ok(t.leaves.length === 0 && Object.keys(t.store).length === 0 && /The receiver said: the transmitter is linked/.test(last(t).m) && /NOT saved/.test(last(t).title), 'diff refused: said, nothing left or kept');
    // ... no USB: the page will not start
    t = page({ usb: false });
    await t.run('usbGate()'); await t.run('diffToPhone()');
    ok(t.sent.length === 0 && t.alerts.length === 0 && /USB cable/.test(t.els.needUsb.textContent), 'no USB: nothing asked, the page says why');
    // ... not a whole diff: not kept, the line left
    t = page({ diff: 'diff all\r\nUNKNOWN COMMAND\r\n# ', chunks: 1 });
    await t.run('usbGate()'); await t.run('diffToPhone()');
    ok(Object.keys(t.store).length === 0 && t.leaves.join() === 'exit' && /not a whole diff: 2 lines/.test(last(t).m), 'not a whole diff: not kept, left: ' + last(t).m);
    // ... the phone will not keep it: the line left, said
    t = page({ saveError: '200 diffs on this phone: delete some first' });
    await t.run('usbGate()'); await t.run('diffToPhone()');
    ok(t.leaves.join() === 'exit' && /would not keep it: 200 diffs/.test(last(t).m), 'the phone full: left, said');
    // ... a reply that never ends: given up after 90 s of /api/cli/out, left
    t = page({ neverEnds: true });
    await t.run('usbGate()'); await t.run('diffToPhone()');
    ok(t.outs === 180 && t.leaves.join() === 'exit' && /never ended/.test(last(t).m), 'a diff that never ends: 180 tries, left (' + t.outs + ')');
    // ... the link lost on the way: the line left (it may be open)
    t = page({ failAt: 0 });
    await t.run('usbGate()'); await t.run('diffToPhone()');
    ok(t.leaves.join() === 'exit' && /no answer from the receiver/.test(last(t).m) && /was left: nothing changed/.test(last(t).m), 'diff, link lost: left, said');
    // ... and a leave the receiver refuses: what to do is said
    t = page({ leaveRefuse: 'ARMED - disarm first' });
    await t.run('usbGate()'); await t.run('diffToPhone()');
    ok(/could not be closed: ARMED/.test(last(t).m) && /Leave without saving/.test(last(t).m), 'a refused leave: what to do said');

    // 2. Execute: every command but the comments, save, exit, defaults and the bootloaders, in order; then saved
    const FILE = DIFF.replace(/\r\n/g, '\n').replace('set roll_rc_rate = 18', 'set roll_rc_rate = 18\ndefaults\ndfu\nbl\nexit\n# a comment\n   set yaw_p = 7   ');
    const CMDS = ['batch start', 'board_name NEXUSX', 'feature -RX_PARALLEL_PWM', 'set gov_mode = ELECTRIC', 'set gov_spoolup_time = 100', 'profile 0', 'set pid_roll_p = 50', 'set pid_pitch_p = 52', 'rateprofile 0', 'set roll_rc_rate = 18', 'set yaw_p = 7'];
    t = page({ files: { [want]: FILE } });
    await t.run('usbGate()'); await t.run('executeDiff("' + want + '")');
    ok(t.sent.join('|') === CMDS.join('|'), 'execute: the commands in order, the rest left out: ' + t.sent.join('|'));
    ok(t.confirms.length === 1 && /Execute the diff of 16 Oct 2026, 15:48\?/.test(t.confirms[0].m) && /Its 11 commands/.test(t.confirms[0].m), 'execute: asked first: ' + (t.confirms[0] || {}).m);
    ok(t.leaves.join() === 'save' && last(t).title === 'Execute diff: saved' && /11 commands sent, 0 refused/.test(last(t).m), 'execute: saved: ' + last(t).m);
    ok(t.awake[0] === 900 && t.awake[t.awake.length - 1] === 0, 'execute: the screen kept on, then let go');
    // ... refused commands: counted, listed, the open batch closed before the save (B53)
    t = page({ files: { [want]: FILE }, bad: ['set gov_mode = ELECTRIC', 'set yaw_p = 7'] });
    await t.run('usbGate()'); await t.run('executeDiff("' + want + '")');
    ok(t.sent[t.sent.length - 1] === 'batch end' && t.sent.length === CMDS.length + 1, 'execute with refusals: the batch closed first: ' + t.sent.slice(-2).join('|'));
    ok(t.leaves.join() === 'save' && /11 commands sent, 2 refused/.test(last(t).m) && /Refused \(left out\):\nset gov_mode = ELECTRIC\n   ###ERROR/.test(last(t).m), 'execute with refusals: saved without them, listed: ' + last(t).m);
    // ... refusals with no batch open: no batch end
    t = page({ files: { [want]: 'set a = 1\nset b = 2\n' }, bad: ['set a = 1'] });
    await t.run('usbGate()'); await t.run('executeDiff("' + want + '")');
    ok(t.sent.join('|') === 'set a = 1|set b = 2' && t.leaves.join() === 'save', 'refusals without a batch: no batch end');
    // ... cancelled: nothing at all
    t = page({ files: { [want]: FILE }, confirm: false });
    await t.run('usbGate()'); await t.run('executeDiff("' + want + '")');
    ok(t.sent.length === 0 && t.leaves.length === 0 && t.awake.length === 0, 'execute cancelled: nothing sent');
    // ... a file with no commands: said, nothing sent
    t = page({ files: { [want]: '# just\n# comments\nsave\n' } });
    await t.run('usbGate()'); await t.run('executeDiff("' + want + '")');
    ok(t.sent.length === 0 && /Nothing to execute/.test(last(t).m), 'no commands: said');
    // ... refused by the receiver at the first command: not started, nothing left
    t = page({ files: { [want]: FILE }, refuse409: 'ARMED - disarm first' });
    await t.run('usbGate()'); await t.run('executeDiff("' + want + '")');
    ok(t.leaves.length === 0 && /not started/.test(last(t).title), 'execute refused at once: not started');
    // ... the flight controller silent part way: stopped, left WITHOUT saving
    t = page({ files: { [want]: FILE }, dropAt: 4 });
    await t.run('usbGate()'); await t.run('executeDiff("' + want + '")');
    ok(t.sent.length === 5 && t.leaves.join() === 'exit' && /Stopped at command 5 of 11/.test(last(t).m) && /Nothing was saved/.test(last(t).m), 'execute, silent part way: stopped, nothing saved: ' + last(t).m);
    // ... the link lost part way: likewise
    t = page({ files: { [want]: FILE }, failAt: 7 });
    await t.run('usbGate()'); await t.run('executeDiff("' + want + '")');
    ok(t.leaves.join() === 'exit' && /Stopped at command 8 of 11/.test(last(t).m), 'execute, link lost: stopped, nothing saved');
    // ... the phone asleep part way (the receiver may have left the line by itself): stopped, never a partial save
    t = page({ files: { [want]: FILE }, stallAt: 3 });
    await t.run('usbGate()'); await t.run('executeDiff("' + want + '")');
    ok(t.sent.length === 4 && t.leaves.join() === 'exit' && /stood still for 61 s/.test(last(t).m), 'execute, the phone slept: stopped, nothing saved: ' + last(t).m);
    // ... a save the receiver refuses: NOT saved, what to do said
    t = page({ files: { [want]: FILE }, leaveRefuse: 'ARMED - disarm first' });
    await t.run('usbGate()'); await t.run('executeDiff("' + want + '")');
    ok(/NOT saved/.test(last(t).title) && /NOT saved: ARMED/.test(last(t).m), 'execute, save refused: said');
    // ... another model's diff is never offered (the list is the model's own, newest first)
    t = page({ files: { 'Havok_2026-10-15_1548.txt': 'x', 'Havok_2026-10-16_0900.txt': 'x', 'Havok_7.txt': 'x', 'Havok_Big_2026-10-16_1000.txt': 'x', 'Goblin_2026-10-16_1100.txt': 'x' } });
    await t.run('usbGate()'); await t.run('refreshList()');
    const shown = [...t.els.list.innerHTML.matchAll(/data-name="([^"]+)"/g)].map(m => m[1]);
    ok(shown.join() === 'Havok_2026-10-16_0900.txt,Havok_2026-10-15_1548.txt,Havok_7.txt', 'the list: the model’s own, newest first: ' + shown.join());
    ok(/Diffs of Havok on this phone/.test(t.els.listHead.textContent), 'the list is headed with the model');
    // View, Share, Delete
    await t.run('shareDiff("Havok_7.txt")'); ok(t.shared.join() === 'Havok_7.txt', 'share: handed to the app');
    await t.run('viewDiff("Havok_7.txt")'); ok(t.els.viewBox.style.display === '' && t.els.viewBox.textContent.startsWith('Havok_7.txt'), 'view: shown');
    await t.run('deleteDiff("Havok_7.txt")'); ok(!('Havok_7.txt' in t.store) && t.els.viewBox.style.display === 'none', 'delete: gone, and its view with it');
    // out of the app (the receiver's WiFi page in a browser): the note, nothing else
    t = page(); t.run('LDRC.viaBle = false'); await t.ready();
    ok(t.els.appNote.style.display === '' && !(t.els.diffBtn && t.els.diffBtn.style.display === '') && t.sent.length === 0, 'out of the app: the note; the Diff button (hidden in the page) never shown');
    t = page({ files: { [want]: FILE } }); await t.ready();
    ok(!(t.els.appNote && t.els.appNote.style.display === '') && t.els.diffBtn.style.display === '' && /data-name="Havok_2026-10-16_1548.txt"/.test(t.els.list.innerHTML), 'in the app: Diff shown, the list drawn');
    t = page({ files: { [want]: FILE }, usb: false }); await t.ready();
    ok(/USB cable/.test(t.els.needUsb.textContent) && t.els.needUsb.style.display === '', 'in the app with no USB: said');

    // 3. the sums against the transmitter's own (lib/LdrcCli compiled here)
    const lib = path.join(os.homedir(), 'Documents', 'GitHub', 'ESP32-board2', 'board4', 'nextion-emulator', 'lib');
    if (!fs.existsSync(path.join(lib, 'LdrcCli', 'LdrcCli.cpp'))) { console.log('SKIP parity: the transmitter’s lib/LdrcCli is not on this computer'); }
    else {
        const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'diffpar')), exe = path.join(dir, 'p');
        cp.execFileSync('clang++', ['-std=c++11', '-O1', '-I' + path.join(lib, 'LdrcCli'), '-I' + path.join(lib, 'LdrcWifi'), '-o', exe,
            path.join(__dirname, 'diff_parity.cpp'), path.join(lib, 'LdrcCli', 'LdrcCli.cpp'), path.join(lib, 'LdrcWifi', 'LdrcWifi.cpp')]);
        const P = page();
        let seed = 895; const rnd = n => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed % n; };
        const pick = a => a[rnd(a.length)];
        const bits = ['set gov_mode = 3', 'save', 'SAVE', 'exit', 'defaults', 'dfu', 'bl', 'blah', 'msc', 'batch start', 'batch end', '# version', '#', '# ', 'diff all', 'feature -X',
                      'board_name NEXUS', '###ERROR IN diff: CORRUPTED CONFIG: gov_mode = 7###', '  set x = 1  ', '\t', ' ', '', 'profile 2', 'x'.repeat(170), 'Invalid name', 'a #', '##'];
        const hx = s => Buffer.from(s, 'latin1').toString('hex') || '-', un = h => Buffer.from(h, 'hex').toString('latin1');
        const cases = [];
        for (let i = 0; i < 6000; ++i) {
            const k = pick(['lines', 'cmds', 'whole', 'key', 'safe', 'err', 'when']);
            if (k === 'key') {
                const m = pick(['Havok', 'Goblin', 'Goblin_700', 'Black Thunder 2', 'model', '']);
                const stamp = pick(['2026-10-16_1548', '2026-1-16_1548', '7', '0', '123456789012345', '1234567890123456', 'x7', '', '2026-10-16-1548', '2026_10_16_1548']);
                const name = pick([m, pick(['Havok', 'Goblin', 'Goblin_700'])]).replace(/ /g, '_') + '_' + stamp + pick(['.txt', '.TXT', '.json', '']);
                cases.push([k, name, P.run('safeName(' + JSON.stringify(m) + ')') + '_', m]);
            } else if (k === 'safe') {
                let s = ''; for (let j = rnd(30); j > 0; --j) s += pick(['a', 'B', '7', ' ', '_', '-', '.', '/', 'é', 'Black Thunder']);
                cases.push([k, s]);
            } else if (k === 'when') {
                cases.push([k, 'Havok_' + pick(['2026', '1999', '20x6']) + '-' + pick(['01', '10', '12', '13', '00']) + '-' + pick(['01', '16', '31', '32', '00']) + '_' + pick(['1548', '0000', '2359']) + pick(['.txt', '.TXT'])]);
            } else {
                let s = ''; for (let j = rnd(14); j > 0; --j) s += pick(bits) + pick(['\r\n', '\n', '\r', '']);
                cases.push([k, s]);
            }
        }
        const input = cases.map(c => c[0] === 'key' ? 'key ' + hx(c[1]) + ' ' + hx(c[2]) : c[0] + ' ' + hx(c[1])).join('\n') + '\n';
        const outs = cp.execFileSync(exe, { input, maxBuffer: 64 << 20 }).toString().split('\n');
        let diff = 0;
        cases.forEach((c, i) => {
            const k = c[0], a = c[1], cpp = outs[i];
            let js, want;
            if (k === 'lines') { js = P.run('cliLines(' + JSON.stringify(a) + ')').join('\x1f'); want = un(cpp); }
            else if (k === 'cmds') { js = P.run('cliCommands(' + JSON.stringify(a) + ')').join('\x1f'); want = un(cpp).split('\x1f').filter(x => x && !/^bl/i.test(x)).join('\x1f'); }   // (the phone also leaves out "bl...": the receiver refuses those)
            else if (k === 'whole') { js = P.run('diffWhole(cliLines(' + JSON.stringify(a) + '))') ? '1' : '0'; want = cpp; }
            else if (k === 'key') { js = String(P.run('fileKey(' + JSON.stringify(a) + ',' + JSON.stringify(c[2]) + ')')); want = cpp; }
            else if (k === 'safe') { js = P.run('safeName(' + JSON.stringify(a) + ')') + '_'; want = un(cpp); }
            else if (k === 'err') { js = P.run('errorWords(' + JSON.stringify(a) + ')'); want = un(cpp); }
            else { js = P.run('diffWhen(' + JSON.stringify(a) + ')'); want = un(cpp).replace('  ', ', '); }   // (the phone writes "16 Oct 2026, 15:48")
            if (k === 'cmds' && cpp === '') want = '';
            if (js !== want) { if (++diff <= 6) console.log('DIFFERENT ' + k + ' ' + JSON.stringify(a) + '\n  phone: ' + JSON.stringify(js) + '\n  tx:    ' + JSON.stringify(want)); }
        });
        ok(diff === 0, 'the sums against the transmitter’s: ' + diff + ' of ' + cases.length + ' different');
        console.log('parity: ' + cases.length + ' random cases against the transmitter’s lib/LdrcCli: ' + diff + ' different');
    }
    console.log(fails ? fails + ' FAILED of ' + checks : 'ALL PASS  (' + checks + ' checks)');
    process.exit(fails ? 1 : 0);
})().catch(e => { console.log('FAIL ' + (e.stack || e)); console.log('FAILED'); process.exit(1); });
