const fs = require('fs'), vm = require('vm');
// The "Install over" choice on the update page (0.9.834): WiFi while the
// receiver is joining, Bluetooth only when WiFi cannot come, the pilot's tap
// always wins, and the card hides during an install. Release gate.
const html = fs.readFileSync(process.argv[2] || 'data/firmware.html', 'utf8');
const i = html.indexOf('function paintLanes(st) {');
let depth = 0, j = i;
for (; j < html.length; j++) { if (html[j] === '{') depth++; if (html[j] === '}') { depth--; if (depth === 0) break; } }
const src = html.slice(i, j + 1);
function run(state, opts = {}) {
  const els = {};
  const el = id => els[id] || (els[id] = { id, hidden: true, innerHTML: '', style: {}, disabled: false });
  const ctx = { document: { getElementById: el }, window: { __preferBle: opts.pref }, LDRC: { viaBle: true },
                installing: !!opts.installing, WEAK_WIFI_DBM: -70, setTimeout: () => {}, fetch: () => Promise.reject() };
  vm.createContext(ctx);
  vm.runInContext(src + '; paintLanes(' + JSON.stringify(state) + ');', ctx);
  return { ble: ctx.window.__laneBle, card: el('laneCard').hidden, wifiBtn: el('laneWifi').innerHTML, why: el('laneWhy').innerHTML, wifiDisabled: el('laneWifi').disabled };
}
const st = (mode, sta, rssi = -55) => ({ info: { rssi }, net: { mode, sta_status: sta } });
const cases = [
  ['joining, home in range (the bug)', st('connecting WiFi', 6), {}, false],
  ['boot window',                      st('waiting for TX', -1), {}, false],
  ['init',                             st('init', -1), {}, false],
  ['joining, home not in range',       st('connecting WiFi', 1), {}, true],
  ['WiFi up',                          st('WiFi up', -1), {}, false],
  ['RF-only',                          st('RF-only (no WiFi)', -1), {}, true],
  ['AP mode',                          st('AP mode', -1), {}, true],
  ['pilot chose Bluetooth, WiFi up',   st('WiFi up', -1), { pref: true }, true],
  ['pilot chose Bluetooth, joining',   st('connecting WiFi', 6), { pref: true }, true],
  ['pilot chose WiFi, joining',        st('connecting WiFi', 6), { pref: false }, false],
];
let fail = 0;
for (const [name, s, o, wantBle] of cases) {
  const r = run(s, o);
  const ok = r.ble === wantBle && r.card === false;
  if (!ok) fail++;
  console.log((ok ? 'PASS ' : 'FAIL ') + name + ' -> ' + (r.ble ? 'Bluetooth' : 'WiFi') + ' | ' + r.why.replace(/<[^>]+>/g, ''));
}
const inst = run(st('WiFi up', -1), { installing: true });
console.log((inst.card === true && inst.ble === undefined ? 'PASS' : 'FAIL') + ' installing hides the card and changes nothing');
if (inst.card !== true) fail++;
console.log(fail ? fail + ' FAILED' : 'ALL PASS');
process.exit(fail ? 1 : 0);
