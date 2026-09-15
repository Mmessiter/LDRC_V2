// Syntax-check the inline <script> of EVERY page, and app.js.
//
// WHY THIS EXISTS: 0.9.725 shipped a firmware.html whose script was missing a
// catch block — a regex edit had matched an earlier, similar line and swallowed
// 85 lines with it. The page loaded, the script threw at parse time, and the
// update screen simply never filled in. dev/page_test.js takes ONE file as an
// argument, so it never looked at the page that broke. Nothing else did either.
//
// Runs over all pages, costs a second, and is wired into publish_website.sh.
const fs = require('fs'), path = require('path'), vm = require('vm');
const dir = path.join(__dirname, '..', 'data');
let bad = 0, n = 0;

const check = (label, src) => {
    n++;
    try { new vm.Script(src, { filename: label }); }
    catch (e) { bad++; console.log('FAIL  ' + label + '\n        ' + e.message); }
};

for (const f of fs.readdirSync(dir).sort()) {
    const p = path.join(dir, f);
    if (f.endsWith('.js')) { check(f, fs.readFileSync(p, 'utf8')); continue; }
    if (!f.endsWith('.html')) continue;
    const html = fs.readFileSync(p, 'utf8');
    // Inline blocks only — a src= tag has no body to parse. Numbered, so a
    // failure names which block on the page.
    const blocks = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)];
    blocks.forEach((m, i) => check(f + ' [script ' + (i + 1) + '/' + blocks.length + ']', m[1]));
}
console.log(bad ? `\n${bad} BROKEN of ${n} checked` : `\nALL PASS  (${n} scripts)`);
process.exit(bad ? 1 : 0);
