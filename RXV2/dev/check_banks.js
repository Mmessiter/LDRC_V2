// Unit test for LDRC.bankCount / bankClamp (0.9.742) — the rules that decide
// how many bank buttons a tuning page draws.
const fs = require('fs'), vm = require('vm');
const ctx = {
  location:{protocol:'http:',hostname:'x',href:'',search:'',pathname:'/'},
  localStorage:{getItem:()=>null,setItem:()=>{}},
  sessionStorage:{getItem:()=>null,setItem:()=>{}},
  navigator:{userAgent:'node'}, console,
  document:{addEventListener(){},getElementById:()=>null,querySelectorAll:()=>[],
            createElement:()=>({style:{},classList:{add(){},remove(){}},dataset:{}}),
            body:{appendChild(){}},documentElement:{},head:{appendChild(){}}},
  fetch:()=>Promise.reject(new Error('offline')), setTimeout, setInterval:()=>0, clearTimeout,
};
ctx.window = ctx; ctx.globalThis = ctx;
vm.createContext(ctx);
try { vm.runInContext(fs.readFileSync('data/app.js','utf8'), ctx); }
catch (e) { console.log('(app.js load note: ' + e.message + ')'); }
const L = ctx.LDRC;
if (!L) { console.log('FAIL  LDRC did not load'); process.exit(1); }
let bad = 0;
const t = (info,kind,cur,want,why) => {
  const g = L.bankCount(info,kind,cur);
  if (g !== want) bad++;
  console.log((g===want?'PASS':'FAIL') + '  ' + why + ' -> ' + g + ' (want ' + want + ')');
};
t({pid:6,rate:6,shown:0},'pid',0,6,'6-bank FC, no cap');
t({pid:6,rate:6,shown:2},'pid',0,2,'cap 2');
t({pid:6,rate:6,shown:2},'pid',4,5,'cap 2 but the FC is on bank 5');
t({pid:3,rate:6,shown:0},'pid',0,3,'small board: 3 PID banks');
t({pid:3,rate:6,shown:0},'rate',0,6,'same board: 6 rate banks');
t({pid:3,rate:6,shown:0},'pid',4,3,'stale bank 5 on a 3-bank FC invents nothing');
t({},'pid',0,4,'no answer yet -> the old 4');
t({pid:6,rate:6,shown:9},'pid',0,6,'junk cap ignored');
t({pid:6,rate:6,shown:1},'pid',0,1,'cap 1');
t({pid:6,rate:6,shown:6},'pid',0,6,'cap equals the real count');
t({fcinfo:{pid_banks:6,rate_banks:6,banks_shown:3}},'pid',0,3,'whole state object accepted');
// The transmitter's bank count (0.9.904): a V2 transmitter's word beats the pilot's cap; the rates pages follow it too (0.9.906)
t({pid:6,rate:6,shown:2,tx_banks:6},'pid',0,6,'TX says 6: the cap of 2 is for a V1 transmitter');
t({pid:6,rate:6,shown:0,tx_banks:4},'pid',0,4,'TX says 4 on a 6-bank FC');
t({pid:3,rate:6,shown:0,tx_banks:6},'pid',0,3,'TX says 6, the FC has 3: never invent one');
t({pid:6,rate:6,shown:0,tx_banks:4},'pid',5,6,'TX says 4 but the FC is on bank 6: never hide the bank we are on');
t({pid:6,rate:6,shown:2,tx_banks:4},'rate',0,4,'rates follow the TX count too (0.9.906), not the old cap');
t({pid:6,rate:6,shown:0,tx_banks:4},'rate',0,4,'TX says 4, its rates on a switch of their own: 4 rate banks, not 6 (Malcolm 22 Oct)');
t({pid:6,rate:6,shown:0,tx_banks:4},'rate',5,6,'rates: the FC on rate bank 6 still shows');
t({pid:6,rate:6,shown:2},'rate',0,2,'no word from the transmitter: rates keep the pilot cap (V1)');
t({pid:6,rate:6,shown:2,tx_banks:4,tx_rates_follow:true},'rate',0,4,'rates follow the banks: the TX count');
t({pid:6,rate:6,shown:2,tx_banks:9},'pid',0,2,'junk TX count ignored');
t({fcinfo:{pid_banks:6,rate_banks:6,banks_shown:2,tx_banks:6}},'pid',0,6,'whole state object: tx_banks read');
// selectorPositions / selectorCount (0.9.904): 4 or 6 until the transmitter says, then its count only; rates 2..6 unless they follow
const sp = (info,kind,want,why) => {
  const g = JSON.stringify(L.selectorPositions(info,kind).options), w = JSON.stringify(want);
  if (g !== w) bad++;
  console.log((g===w?'PASS':'FAIL') + '  ' + why + ' -> ' + g + ' (want ' + w + ')');
};
sp({},'pid',[4,6],'no word from the transmitter: 4 or 6');
sp({tx_banks:6},'pid',[6],'TX says 6');
sp({tx_banks:4},'pid',[4],'TX says 4');
sp({tx_banks:6},'rate',[2,3,4,5,6],'rates selector free');
sp({tx_banks:6,tx_rates_follow:true},'rate',[6],'rates follow the banks');
sp({tx_banks:7},'pid',[4,6],'junk count: 4 or 6');
sp({fcinfo:{tx_banks:4}},'pid',[4],'whole state object');
const sc = (info,kind,r,want,why) => {
  const g = L.selectorCount(info,kind,r);
  if (g !== want) bad++;
  console.log((g===want?'PASS':'FAIL') + '  ' + why + ' -> ' + g + ' (want ' + want + ')');
};
sc({},'pid',3,4,'a remembered 3 becomes 4');
sc({},'pid',5,6,'a remembered 5 becomes 6');
sc({},'pid',6,6,'a remembered 6 stays');
sc({},'pid',4,4,'a remembered 4 stays');
sc({tx_banks:4},'pid',6,4,'locked to the transmitter');
sc({tx_banks:6},'rate',3,3,'a rates switch of 3 stays');
sc({tx_banks:6,tx_rates_follow:true},'rate',3,6,'rates following the banks');
sc({},'rate',0,4,'nothing remembered: 4');
sc({},'rate',9,6,'junk remembered: 6');
// bankMax — Copy a bank ignores the cap so a hidden bank can be used to PARK
// a known-good tune (0.9.745).
const m = (info,kind,want,why) => {
  const g = L.bankMax(info,kind);
  if (g !== want) bad++;
  console.log((g===want?'PASS':'FAIL') + '  ' + why + ' -> ' + g + ' (want ' + want + ')');
};
m({pid:6,rate:6,shown:2},'pid',6,'bankMax ignores a cap of 2');
m({pid:6,rate:6,shown:0},'pid',6,'bankMax with no cap');
m({pid:3,rate:6,shown:1},'pid',3,'bankMax still respects a small board');
m({pid:3,rate:6,shown:1},'rate',6,'bankMax rate side of the same board');
m({},'pid',4,'bankMax with no answer yet -> the old 4');

const c = (info,kind,rem,want,why) => {
  const g = L.bankClamp(info,kind,rem);
  if (g !== want) bad++;
  console.log((g===want?'PASS':'FAIL') + '  ' + why + ' -> ' + g + ' (want ' + want + ')');
};
c({pid:3,rate:6,shown:0},'pid',5,0,'clamp a stale bank 6 on a 3-bank FC');
c({pid:6,rate:6,shown:0},'pid',4,4,'clamp keeps a valid bank 5');
c({pid:6,rate:6,shown:2},'pid',4,0,'clamp respects the cap');
// The bank rows are drawn at run time by LDRC.bankRow(container, prefix,
// 'fnName', n), so page_test.js's "every onclick handler exists" check never
// sees them. Check here that each named function is really defined on the
// page that names it (0.9.756 - a rename would otherwise ship a row of
// buttons that do nothing).
const path = require('path');
const dir = process.env.PAGES_DIR || path.join(__dirname, '..', 'data');
let rows = 0;
for (const f of fs.readdirSync(dir).filter(x => x.endsWith('.html'))) {
  const html = fs.readFileSync(path.join(dir, f), 'utf8');
  const re = /LDRC\.bankRow\(\s*[^,]+,\s*'[^']*',\s*'([A-Za-z_$][\w$]*)'/g;
  let m;
  while ((m = re.exec(html))) {
    rows++;
    const fn = m[1];
    const defined = new RegExp('(^|[^\\w$.])(async\\s+)?function\\s+' + fn + '\\s*\\(|(^|[^\\w$.])(const|let|var)\\s+' + fn + '\\s*=').test(html);
    if (!defined) { bad++; console.log('FAIL  ' + f + ': LDRC.bankRow names ' + fn + '() but the page does not define it'); }
  }
}
console.log((bad ? 'FAIL' : 'PASS') + '  every LDRC.bankRow callback is defined on its page (' + rows + ' rows)');
console.log(bad ? ('\n' + bad + ' FAILED') : '\nALL PASS');
process.exit(bad ? 1 : 0);
