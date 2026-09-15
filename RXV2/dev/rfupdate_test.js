// Exercise LDRC.rotorflightCheckUpdate's decision table. The wrong answer here
// means telling a pilot to reflash a flight controller that is already right,
// or steering them onto byte layouts our pages cannot write — so it gets a test.
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/../data/app.js', 'utf8');

let el;
global.window = { addEventListener(){}, removeEventListener(){}, matchMedia: () => ({ matches:false, addEventListener(){} }) }; global.location = { protocol: 'http:', hostname: 'x', pathname: '/' };
global.localStorage = { _d: {}, getItem(k){return this._d[k]||null;}, setItem(k,v){this._d[k]=v;}, removeItem(k){delete this._d[k];} };
global.sessionStorage = { _d: {}, getItem(k){return this._d[k]||null;}, setItem(k,v){this._d[k]=v;}, removeItem(k){delete this._d[k];} };
global.document = {
  getElementById: (id) => (id === 'rfUpdate' ? el : null),
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
const REAL_rfLatest = L.rfLatest, REAL_rfGit = L.rfGithubLatest;

let pass = 0, fail = 0;
function check(ok, name, extra) {
  if (ok) { pass++; console.log('PASS  ' + name); }
  else    { fail++; console.log('FAIL  ' + name + (extra ? '\n        ' + extra : '')); }
}

// ---- the decision table -----------------------------------------------------
async function run(name, fcinfo, feed, live, verified, expect, expectAhead) {
  el = { style: { display: 'none', cssText: '' }, innerHTML: '' };
  L.RF_API_VERIFIED = verified;
  L.rfLatest = async () => feed;
  L.rfGithubLatest = async () => live;
  await L.rotorflightCheckUpdate({ fcinfo, info: { name: 'T' } }, 'rfUpdate');
  const t = el.innerHTML || '';
  let got = '?';
  if (/newer Rotorflight is available/.test(t)) got = 'upgrade';
  else if (/Up to date/.test(t)) got = 'uptodate';
  else if (/newer than these pages/.test(t)) got = 'ahead';
  else if (/Could not check/.test(t)) got = 'nofeed';
  else if (/No flight controller/.test(t)) got = 'nofc';
  const ahead = /has since come out/.test(t);
  check(got === expect && ahead === !!expectAhead, name,
        `expected ${expect}${expectAhead ? ' +ahead' : ''}, got ${got}${ahead ? ' +ahead' : ''}`);
}

const fc = (maj, min, patch, apiMin) => ({
  detected: true, version_known: true, variant: 'RTFL',
  api_major: 12, api_minor: apiMin, fw_major: maj, fw_minor: min, fw_patch: patch,
  rf_major: 2, rf_minor: min - 3,
});
const FEED460 = { firmware: '4.6.0', api: 1209, suite: '2.3', released: '2026-06-30' };

(async () => {
  await run('same version as the curated line -> up to date',
            fc(4,6,0,9), FEED460, null, 1209, 'uptodate');
  await run('one release behind -> upgrade',
            fc(4,5,1,8), FEED460, null, 1209, 'upgrade');
  await run('patch behind -> upgrade',
            fc(4,6,0,9), { ...FEED460, firmware: '4.6.1' }, null, 1209, 'upgrade');
  await run('ahead of the curated line -> say so, do not invent advice',
            fc(4,7,0,10), FEED460, '4.7.0', 1209, 'ahead');
  await run('up to date, but Rotorflight has since released -> the extra sentence',
            fc(4,6,0,9), FEED460, '4.7.0', 1209, 'uptodate', true);
  await run('behind, and something newer still exists -> upgrade to the CHECKED one, with the caveat',
            fc(4,5,1,8), FEED460, '4.7.0', 1209, 'upgrade', true);
  await run('GitHub silent (no internet / rate limited) -> no caveat, check still works',
            fc(4,6,0,9), FEED460, null, 1209, 'uptodate', false);
  await run('GitHub not newer than the curated line -> no caveat',
            fc(4,6,0,9), FEED460, '4.6.0', 1209, 'uptodate', false);
  await run('no feed at all -> honest "could not check", never a guess',
            fc(4,6,0,9), null, '4.7.0', 1209, 'nofeed');
  await run('no flight controller -> asks for a wire, does not check',
            { detected: false }, FEED460, null, 1209, 'nofc');
  await run('a non-Rotorflight flight controller is not ours to advise',
            { detected: true, version_known: true, variant: 'BTFL', api_major: 12, api_minor: 9,
              fw_major: 4, fw_minor: 5, fw_patch: 0 }, FEED460, null, 1209, 'nofc');

  // ---- version comparison -----------------------------------------------
  check(L.vcmp('4.10.0', '4.9.0') > 0, 'vcmp: 4.10.0 is newer than 4.9.0 (a string compare says otherwise)');
  check(L.vcmp('4.6.0', '4.6.0') === 0, 'vcmp: equal versions compare equal');
  check(L.vcmp('4.6', '4.6.0') === 0, 'vcmp: a missing patch counts as zero');
  check(L.vcmp('4.5.9', '4.6.0') < 0, 'vcmp: minor beats patch');

  // ---- the GitHub source, with its two traps ----------------------------
  L.rfGithubLatest = REAL_rfGit;
  const gitReply = (list) => { global.fetch = async () => ({ ok: true, json: async () => list }); };
  const freshGit = async () => { localStorage.removeItem('rfGit.v1'); return await L.rfGithubLatest(); };

  gitReply([{ tag_name: 'release/4.6.0' }, { tag_name: 'release/4.7.0-RC3' }]);
  check(await freshGit() === '4.6.0', 'GitHub: a release candidate is NOT offered (they are not marked prerelease)');

  gitReply([{ tag_name: 'release/4.6.0' }, { tag_name: 'release/4.10.0' }, { tag_name: 'release/4.9.0' }]);
  check(await freshGit() === '4.10.0', 'GitHub: the newest stable wins, numerically');

  gitReply([{ tag_name: 'snapshot/20260901' }, { tag_name: 'v4.6.0' }]);
  check(await freshGit() === null, 'GitHub: snapshots and odd tags are ignored');

  gitReply([{ tag_name: 'release/4.7.0', draft: true }, { tag_name: 'release/4.6.0' }]);
  check(await freshGit() === '4.6.0', 'GitHub: a draft is not a release');

  global.fetch = async () => { throw new Error('offline'); };
  check(await freshGit() === null, 'GitHub: offline is null, not a crash');

  gitReply([{ tag_name: 'release/4.8.0' }]);
  let calls = 0;
  const counted = async (u) => { calls++; return { ok: true, json: async () => [{ tag_name: 'release/4.8.0' }] }; };
  localStorage.removeItem('rfGit.v1');
  global.fetch = counted;
  await L.rfGithubLatest(); await L.rfGithubLatest(); await L.rfGithubLatest();
  check(calls === 1, 'GitHub: repeated taps reuse the cached answer (60 questions an hour, and it counts 304s)', `asked ${calls} times`);

  // ---- the curated feed never guesses when offline -----------------------
  L.rfLatest = REAL_rfLatest;
  localStorage.setItem('rfLatest.v3', JSON.stringify({ at: Date.now() - 600000, rf: FEED460 }));
  global.fetch = async () => { throw new Error('offline'); };
  check(await L.rfLatest() === null, 'curated feed: offline returns null, not a stale answer from an hour ago');

  console.log(`\n${fail ? 'FAILURES: ' + fail : 'ALL PASS'}  (${pass} passed)`);
  process.exit(fail ? 1 : 0);
})();
