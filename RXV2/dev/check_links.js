// Every internal link on every page must lead to a page that exists.
//
// WHY: the wizards' "Back up" steps pointed at /setup for months — the page
// existed, so nothing complained; it was simply the wrong one (0.9.687 fixed
// the New-helicopter wizard, and Malcolm found the Tuning one still wrong on
// 2026-09-17). A link checker cannot judge INTENT, but it does catch the
// cheaper half: a link to a page that is not there at all.
const fs = require('fs'), path = require('path');
const dir = path.join(__dirname, '..', 'data');
const files = fs.readdirSync(dir).filter(f => f.endsWith('.html'));
const have = new Set(files.map(f => '/' + f.replace(/\.html$/, '')));
have.add('/'); have.add('/index');
// Routes the firmware serves that are not pages in data/.
const ROUTES = new Set(['/reboot', '/fly_arm', '/fly_disarm', '/wifi']);
let bad = 0, n = 0;
for (const f of files) {
    const src = fs.readFileSync(path.join(dir, f), 'utf8');
    const links = new Set();
    for (const m of src.matchAll(/href\s*=\s*["']([^"'#?]+)["']/g)) links.add(m[1]);
    for (const m of src.matchAll(/href:\s*'([^']+)'/g)) links.add(m[1]);          // wizard step tables
    for (const m of src.matchAll(/location\.href\s*=\s*'([^']+)'/g)) links.add(m[1]);
    for (const l of links) {
        if (!l.startsWith('/') || l.startsWith('//')) continue;                    // external or relative asset
        if (/\.(css|js|json|png|jpg|jpeg|svg|ico|gz|bin|pdf)$/i.test(l)) continue;  // assets
        if (l.startsWith('/api/') || l.startsWith('/app/')) continue;              // endpoints
        n++;
        const clean = l.replace(/\.html$/, '');
        if (!have.has(clean) && !ROUTES.has(clean)) { bad++; console.log(`FAIL  ${f} -> ${l}`); }
    }
}
// And the half a link checker CAN judge: a wizard step called "Back up"
// must lead to the backup page. /setup is a real page, so nothing above
// would ever have objected — yet that is exactly where both wizards sent
// people. One rule per step whose title says what it must do.
const MUST = [[/back up/i, '/rotorflight-backup']];
for (const f of files.filter(x => /wizard|newheli|tuning/.test(x))) {
    const src = fs.readFileSync(path.join(dir, f), 'utf8');
    for (const m of src.matchAll(/\{[^}]*?t:\s*'([^']+)'[^}]*?href:\s*'([^']+)'[^}]*?\}/g)) {
        const [, title, href] = m;
        for (const [re, want] of MUST) {
            if (!re.test(title)) continue;
            n++;
            if (href !== want) { bad++; console.log(`FAIL  ${f}: step "${title}" -> ${href}, expected ${want}`); }
        }
    }
}
console.log(bad ? `\n${bad} BROKEN of ${n} checks` : `\nALL PASS  (${n} checks)`);
process.exit(bad ? 1 : 0);
