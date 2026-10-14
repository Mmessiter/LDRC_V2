// gear.js (the Rotorflight gear-ratio widget): the plain-English verdicts and
// the box-to-pair scaling, run in node. Malcolm 2026-10-14, the SAB Havoc
// (direct drive): 1 : 1 on the main ratio was called "Not set" - it is valid.
const fs = require('fs'), path = require('path'), vm = require('vm');
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
const els = {};
const mk = id => ({ id, value: '', textContent: '', style: {}, listeners: {}, addEventListener(ev, fn) { (this.listeners[ev] = this.listeners[ev] || []).push(fn); } });
const doc = { getElementById: id => (id === 'gwCss' ? null : (els[id] || (els[id] = mk(id)))), createElement: () => ({ style: {} }), head: { appendChild() {} } };
const sandbox = { console, document: doc, Math, parseFloat, window: {} };
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'data', 'gear.js'), 'utf8'), sandbox, { filename: 'gear.js' });
const G = sandbox.LDRCGear;
ok(G && typeof G.verdict === 'function' && typeof G.pair === 'function', 'gear.js runs and exports verdict + pair');

// main ratio verdicts
let v = G.verdict('main', '1', '1');
ok(v.bad === false, 'main 1 : 1 is NOT refused (direct drive)');
ok(v.warn === true, 'main 1 : 1 is an amber note');
ok(/direct drive/.test(v.text) && !/Not set/.test(v.text), 'main 1 : 1 says direct drive, not "Not set": ' + v.text);
ok(/factory/.test(v.text), 'main 1 : 1 still warns that a fresh flight controller reads 1 : 1 too');
v = G.verdict('main', '10', '1');
ok(v.bad === true && /Backwards/.test(v.text), 'main 10 : 1 is backwards');
v = G.verdict('main', '1', '10.2');
ok(v.bad === false && !v.warn && /1 : 10.2/.test(v.text), 'main 1 : 10.2 is right: ' + v.text);
v = G.verdict('main', '399', '4080');
ok(v.bad === false && /10.23/.test(v.text), 'main 399 : 4080 reads as 1 : 10.23');
v = G.verdict('main', '', '5');
ok(v.bad === true && /Enter both/.test(v.text), 'a blank box is refused');
v = G.verdict('main', '0', '5');
ok(v.bad === true, 'a zero is refused');

// tail ratio verdicts
v = G.verdict('tail', '1', '1');
ok(v.bad === false && /motorised tail/.test(v.text), 'tail 1 : 1 is allowed (motorised tail)');
v = G.verdict('tail', '5', '1');
ok(v.bad === true && /Backwards/.test(v.text), 'tail 5 : 1 is backwards');
v = G.verdict('tail', '1', '4.7');
ok(v.bad === false && /4.7/.test(v.text), 'tail 1 : 4.7 is right');

// box values -> the whole-number pair the FC stores
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
ok(eq(G.pair('1', '1'), [1, 1]), 'pair 1 : 1 -> [1, 1]');
ok(eq(G.pair('1', '10.2'), [10, 102]), 'pair 1 : 10.2 -> [10, 102]');
ok(eq(G.pair('399', '4080'), [399, 4080]), 'pair 399 : 4080 unchanged');
ok(G.pair('', '5') === null && G.pair('0', '5') === null && G.pair('1', '70000') === null, 'blank, zero and > 65535 are unusable');

// the live hint under the boxes: colour by verdict
const paint = G.attachHint('n', 'd', 'o', 'main');
ok(typeof paint === 'function', 'attachHint returns its repaint');
els.n.value = '1'; els.d.value = '1'; paint();
ok(els.o.style.color === '#7a5412' && /direct drive/.test(els.o.textContent), 'hint for 1 : 1 is amber and says direct drive');
els.d.value = '10.2'; paint();
ok(els.o.style.color === '#2f6b3a', 'hint for 1 : 10.2 is green');
els.n.value = '10'; els.d.value = '1'; paint();
ok(els.o.style.color === '#8a2f2f' && els.o.style.fontWeight === '600', 'hint for 10 : 1 is red and bold');

console.log(fails ? 'FAIL ' + fails : 'ALL PASS');
process.exit(fails ? 1 : 0);
