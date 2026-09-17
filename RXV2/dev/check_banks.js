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
