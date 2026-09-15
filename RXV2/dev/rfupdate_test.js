// Exercise LDRC.rotorflightUpdateCard's decision table. The wrong answer here
// means telling a pilot to reflash a flight controller that is already right,
// or steering them onto layouts our pages cannot write — so it gets a test.
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/../data/app.js', 'utf8');

let el;
global.window = { addEventListener(){}, removeEventListener(){}, matchMedia: () => ({ matches:false, addEventListener(){} }) }; global.location = { protocol: 'http:', hostname: 'x', pathname: '/' };
global.localStorage = { _d: {}, getItem(k){return this._d[k]||null;}, setItem(k,v){this._d[k]=v;}, removeItem(k){delete this._d[k];} };
global.document = {
  getElementById: (id) => (id === 'rfUpdate' ? el : { onclick: null, style: {}, innerHTML: '' }),
  addEventListener(){}, querySelector(){return null;}, querySelectorAll(){return [];},
  createElement(){return {style:{},setAttribute(){},appendChild(){},classList:{add(){},contains(){return false;}}};},
  body:{appendChild(){},children:[],classList:{add(){},contains(){return false;}}}, readyState:'complete', documentElement:{classList:{add(){},toggle(){},contains(){return false;}}}
};
global.fetch = async () => ({ ok: false });
global.setInterval = () => 0; global.setTimeout = (f) => 0; global.clearInterval = () => {}; global.clearTimeout = () => {};
global.performance = { now: () => 0 };
Object.defineProperty(global, 'LDRC', { get: () => global.window.LDRC, configurable: true });
eval(src);
const L = window.LDRC;
const REAL_rfLatest = L.rfLatest;   // the decision tests stub this out

async function run(name, fcinfo, feed, verified, expect) {
  el = { style: { display: '', cssText: '' }, innerHTML: '' };
  L.replay = false;
  L.RF_API_VERIFIED = verified;
  L.rfLatest = async () => feed;
  await L.rotorflightUpdateCard({ fcinfo, rf: { armed: false }, info: { name: 'T' } }, 'rfUpdate');
  const shown = el.style.display !== 'none';
  const text  = el.innerHTML || '';
  let got = 'silent';
  if (shown && /newer Rotorflight is available/.test(text)) got = 'upgrade';
  else if (shown && /Stay on Rotorflight/.test(text)) got = 'hold';
  else if (shown) got = 'shown-but-unrecognised';
  const ok = got === expect;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}\n        expected ${expect}, got ${got}`);
  return ok;
}

const fc = (maj, min, patch, apiMin) => ({
  detected: true, version_known: true, variant: 'RTFL',
  api_major: 12, api_minor: apiMin, fw_major: maj, fw_minor: min, fw_patch: patch,
  rf_major: 2, rf_minor: min - 3,
});
const feed = (v, api, suite) => ({ firmware: v, api, suite, released: '2026-06-30' });

(async () => {
  let all = true;
  all &= await run("Malcolm's Goblin today: FC 4.6.0, newest 4.6.0, verified 1209",
                   fc(4,6,0,9), feed('4.6.0',1209,'2.3'), 1209, 'silent');
  all &= await run("one release behind, and we have verified the new one",
                   fc(4,5,1,8), feed('4.6.0',1209,'2.3'), 1209, 'upgrade');
  all &= await run("newest is AHEAD of what our pages were checked against",
                   fc(4,6,0,9), feed('4.7.0',1210,'2.4'), 1209, 'hold');
  all &= await run("pilot already on the unverified newer one (rfVersionAlert's job)",
                   fc(4,7,0,10), feed('4.7.0',1210,'2.4'), 1209, 'silent');
  all &= await run("no feed at all — must be indistinguishable from nothing to say",
                   fc(4,5,1,8), null, 1209, 'silent');
  all &= await run("not a Rotorflight board",
                   {detected:true,version_known:true,variant:'BTFL',api_major:1,api_minor:44}, feed('4.6.0',1209,'2.3'), 1209, 'silent');
  global.__decisionsOk = !!all;
})().then(() => global.__cacheTests());

// --- once-a-day caching -------------------------------------------------
// Proves the check happens on the first run of a calendar DAY and not again,
// and that a failure does not claim the day.
global.__cacheTests = async () => {
  const L2 = window.LDRC;
  L2.rfLatest = REAL_rfLatest;        // put the real one back
  let fetches = 0;
  const feedJson = { rotorflight: { firmware: '4.6.0', api: 1209, suite: '2.3' } };
  global.fetch = async () => { fetches++; return { ok: true, json: async () => feedJson }; };
  global.localStorage._d = {};

  const a = await L2.rfLatest();                       // first ever: must fetch and wait
  const n1 = fetches;
  const b = await L2.rfLatest();                       // same day: must NOT fetch
  const n2 = fetches;
  // roll the stored day back a day
  const KEY = 'rfLatest.v2';
  const c = JSON.parse(global.localStorage.getItem(KEY));
  c.day = '2000-01-01';
  global.localStorage.setItem(KEY, JSON.stringify(c));
  const d = await L2.rfLatest();                       // new day: returns cache AT ONCE, refreshes behind
  await new Promise(r => setImmediate(r));
  const n3 = fetches;

  const ok1 = a && n1 >= 1;
  const ok2 = b && n2 === n1;
  const ok3 = d && n3 > n2;
  console.log(`${ok1 ? 'PASS' : 'FAIL'}  first run fetches and returns a feed (${n1} fetch${n1===1?'':'es'})`);
  console.log(`${ok2 ? 'PASS' : 'FAIL'}  same day does NOT fetch again (still ${n2})`);
  console.log(`${ok3 ? 'PASS' : 'FAIL'}  a new day refreshes in the background (${n3}) without blocking`);

  // a failure must not claim the day
  global.localStorage._d = {};
  global.fetch = async () => ({ ok: false });
  const e = await L2.rfLatest();
  const stored = JSON.parse(global.localStorage.getItem(KEY) || 'null');
  const ok4 = e === null && (!stored || stored.day !== new Date().toISOString().slice(0,10));
  console.log(`${ok4 ? 'PASS' : 'FAIL'}  a failed check does not claim the day`);
  const all = global.__decisionsOk && ok1 && ok2 && ok3 && ok4;
  console.log(all ? '\nALL PASS' : '\nFAILURES');
  process.exit(all ? 0 : 1);
};
