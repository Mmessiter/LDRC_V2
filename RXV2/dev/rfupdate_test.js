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
  console.log(all ? '\nALL PASS' : '\nFAILURES');
  process.exit(all ? 0 : 1);
})();
