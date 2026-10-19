// Every web route must go through the Bluetooth/WiFi router (BleConfig.h's g_bleRouter): a route registered on the bare
// WebServer answers over WiFi and is "not found" from the phone over Bluetooth. WebPages.h does it with
// `#define server g_bleRouter` ... `#undef server`; a header included AFTER WebPages.h (main.cpp's order) starts outside
// that alias, so its `server.` calls must sit inside an alias of its own, or name g_bleRouter outright.
// 0.9.661 to 0.9.898: BlackboxCheck.h's five routes were on the WiFi server only (Malcolm, 19 Oct 2026, at the bench:
// the phone could not start a black box read).
//   node dev/route_gate.js
const fs = require('fs'), path = require('path');
const SRC = path.join(__dirname, '..', 'src');
let n = 0, bad = 0;
const ok = (c, m) => { n++; if (!c) { bad++; console.log('FAIL ' + m); } else console.log('PASS ' + m); };

const main = fs.readFileSync(path.join(SRC, 'main.cpp'), 'utf8');
const includes = [...main.matchAll(/^#include "([^"]+)"/gm)].map(m => m[1]);
const iWeb = includes.indexOf('WebPages.h');
ok(iWeb >= 0, 'main.cpp includes WebPages.h');
const web = fs.readFileSync(path.join(SRC, 'WebPages.h'), 'utf8');
ok(/^#define server g_bleRouter$/m.test(web) && /^#undef server$/m.test(web), 'WebPages.h routes through the router and takes the alias back');

// what a file does with `server.` outside its own alias
function bareServerLines(file) {
    const lines = fs.readFileSync(path.join(SRC, file), 'utf8').split('\n');
    let aliased = false; const out = [];
    lines.forEach((l, i) => {
        if (/^\s*#define server g_bleRouter\b/.test(l)) aliased = true;
        else if (/^\s*#undef server\b/.test(l)) aliased = false;
        else if (!aliased && /(^|[^:\w.])server\.(on|send|sendHeader|arg|hasArg|args|argName|method|uri|client|streamFile|setContentLength|sendContent|collectHeaders|header|hasHeader)\s*\(/.test(l) && !/^\s*\/\//.test(l)) out.push((i + 1) + ': ' + l.trim().slice(0, 100));
    });
    return out;
}
// the files after WebPages.h, and main.cpp itself
const after = includes.slice(iWeb + 1).filter(f => fs.existsSync(path.join(SRC, f)));
for (const f of after.concat(['main.cpp'])) {
    const bare = bareServerLines(f);
    ok(bare.length === 0, f + ' (after WebPages.h): no bare server. call outside a g_bleRouter alias' + (bare.length ? '\n   ' + bare.join('\n   ') : ''));
}
// and a file that registers routes must register them all through the router
for (const f of fs.readdirSync(SRC).filter(f => /\.h$/.test(f))) {
    const t = fs.readFileSync(path.join(SRC, f), 'utf8');
    if (!/\bserver\.on\s*\(/.test(t) && !/g_bleRouter\.on\s*\(/.test(t)) continue;
    const bare = bareServerLines(f).filter(l => /server\.on\s*\(/.test(l));
    ok(bare.length === 0, f + ': every route goes through the router' + (bare.length ? '\n   ' + bare.join('\n   ') : ''));
}
// the black box routes, by name: the ones the phone must find over Bluetooth
const bb = fs.readFileSync(path.join(SRC, 'BlackboxCheck.h'), 'utf8');
const reg = bb.slice(bb.indexOf('#define server g_bleRouter'), bb.indexOf('#undef server'));
for (const r of ['/rotorflight-filtercheck', '/api/blackbox/check', '/api/blackbox/cancel', '/api/blackbox/status', '/api/blackbox/result'])
    ok(reg.indexOf('server.on("' + r + '"') >= 0, 'BlackboxCheck.h registers ' + r + ' through the router');
console.log(bad ? `\n${bad} FAILED of ${n} checks` : `\nALL PASS  (${n} checks)`);
process.exit(bad ? 1 : 0);
