// The ESC settings page (rotorflight-escprog.html) and the brand the flight
// controller is set to: only a Scorpion is read and changed there, and every
// other brand must get a true answer, not "set it to Scorpion" (Malcolm
// 2026-10-14, the Havoc's Hobbywing Platinum 60A V4).
const fs = require('fs'), path = require('path'), vm = require('vm');
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
const html = fs.readFileSync(path.join(__dirname, '..', 'data', 'rotorflight-escprog.html'), 'utf8');
const m = html.match(/const PROTO_NAMES=[\s\S]*?\nfunction escProtoVerdict\(p\)\{[\s\S]*?\n\}\n/);
ok(!!m, 'the page defines PROTO_NAMES + escProtoVerdict');
const G = vm.runInNewContext(m[0] + ';({escProtoVerdict, PROTO_NAMES})', {});
ok(G.PROTO_NAMES.length === 14 && G.PROTO_NAMES[2] === 'Hobbywing V4' && G.PROTO_NAMES[4] === 'Scorpion' && G.PROTO_NAMES[12] === 'XDFly',
   'the names follow Rotorflight 4.6 esc_sensor_protocol order (0 none .. 13 record)');
let v = G.escProtoVerdict(4);
ok(v.ok === true, 'Scorpion (4) is the brand this page changes');
v = G.escProtoVerdict(2);
ok(v.ok === false && /Hobbywing V4/.test(v.text) && /LCD box/.test(v.text) && /not from here/.test(v.text), 'Hobbywing V4: read-only for Rotorflight, LCD box / WiFi module: ' + v.text);
ok(!/set it/.test(v.text) && !/Scorpion/.test(v.text), 'Hobbywing V4 is NOT told to switch to Scorpion');
v = G.escProtoVerdict(3);
ok(v.ok === false && /Hobbywing V5/.test(v.text) && /does not know it yet/.test(v.text), 'Hobbywing V5: programmable, not here yet');
v = G.escProtoVerdict(0);
ok(v.ok === false && /First-time basics/.test(v.text), 'no protocol: sent to First-time basics');
for (const [p, name] of [[9, 'OpenYGE'], [10, 'FlyRotor'], [12, 'XDFly']]) {
    v = G.escProtoVerdict(p);
    ok(v.ok === false && v.text.includes(name) && /own programmer/.test(v.text), name + ': Rotorflight can, this page cannot yet');
}
v = G.escProtoVerdict(5);
ok(v.ok === false && /Kontronik/.test(v.text) && /own programmer/.test(v.text), 'Kontronik: its own programmer');
v = G.escProtoVerdict(99);
ok(v.ok === false && /protocol 99/.test(v.text), 'an unknown number does not throw');

// the page wiring: the probe asks the brand (MSP 123) before the telemetry (MSP 139)
const probe = html.slice(html.indexOf('async function probe(){'), html.indexOf('let probeGen=0;'));
ok(probe.includes("LDRC.msp(123") && probe.indexOf('LDRC.msp(123') < probe.indexOf('escTelem()'), 'probe() reads the brand before the Scorpion checks');
ok(probe.includes("applyState('notscorpion',escProto)"), 'a brand this page cannot change stops the probe at its verdict');
ok(html.includes("case 'notscorpion':") && /case 'notscorpion':[\s\S]*?setButton\('🔌 Read the ESC',false\)/.test(html), 'the notscorpion state greys the Read button');
ok(!html.includes('not Scorpion — set it in First-time basics'), 'the old "set it to Scorpion" message is gone');
ok(html.includes('escProtoVerdict(b[0])'), 'checkWiring() uses the same verdict');
ok(/<li><b>Other brands<\/b>:[^<]*Hobbywing Platinum V5/.test(html) && /Hobbywing Platinum V4 or a Kontronik cannot be changed/.test(html), 'help says which brands Rotorflight can program and which it cannot');
const wiring = fs.readFileSync(path.join(__dirname, '..', 'data', 'rotorflight-wiring.html'), 'utf8');
ok(/Hobbywing Platinum V4: the <b>signal<\/b> pin of its programming port/.test(wiring) && /leave its red pin out/.test(wiring), 'wiring page: programming-port signal pin, never the red pin');
console.log(fails ? 'FAIL ' + fails : 'ALL PASS');
process.exit(fails ? 1 : 0);
