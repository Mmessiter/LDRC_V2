// The first-run naming gate must attach its Save handler on a RECEIVER and on
// a DONGLE. On a dongle it rewrites #gateNextSteps, which deletes the three
// echo elements; until 0.9.821 the next line then threw, the handler was never
// attached, and the form fell back to a plain reload - the box came straight
// back with no error (Malcolm's first home-built dongle, 2026-09-22).
// page_test.js could not see it: its stand-in DOM returns an element for any
// id. This one behaves like a browser where it matters: innerHTML= removes the
// children, and getElementById returns null for what is gone.
const fs = require('fs'), path = require('path'), vm = require('vm');
const html = fs.readFileSync(path.join(__dirname, '..', 'data', 'index.html'), 'utf8');
let fails = 0;
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };

// A DOM just big enough: elements by id, parent links, innerHTML that prunes.
function makeDom() {
    const els = {};
    const mk = (id, tag, parent) => {
        const el = { id, tagName: tag, style: {}, listeners: {}, children: [], parent, value: '',
            textContent: '', _html: '',
            addEventListener(ev, fn) { (this.listeners[ev] = this.listeners[ev] || []).push(fn); },
            querySelector(sel) { const t = sel.replace('form > ', '').toUpperCase(); return this.children.find(c => c.tagName === t) || null; },
            get innerHTML() { return this._html; },
            set innerHTML(v) { const drop = c => { delete els[c.id]; c.children.forEach(drop); }; this.children.forEach(drop); this.children = []; this._html = v; },
            get previousElementSibling() { return null; }, get nextElementSibling() { return null; },
            focus() {}, remove() {}, after() {} };
        els[id] = el; if (parent) parent.children.push(el); return el;
    };
    const gate = mk('nameGate', 'DIV'); mk('gateH2', 'H2', gate); mk('gateIntro', 'P', gate);
    const form = mk('nameGateForm', 'FORM', gate); mk('formLabel', 'P', form);
    mk('nameGateInput', 'INPUT', form); mk('nameGateErr', 'P', form); mk('gateSsid', 'INPUT', form); mk('gatePass', 'INPUT', form);
    const next = mk('gateNextSteps', 'P', form); mk('gateNameEcho', 'CODE', next); mk('gateHostEcho', 'SPAN', next); mk('gateApEcho', 'CODE', next);
    mk('mainMenu', 'DIV'); mk('modelName', 'H1');
    return { els, form,
        document: { getElementById: id => els[id] || null, querySelector: () => null, title: '', addEventListener() {} } };
}

// Lift paintModelName out of the page and run it for each role.
const src = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');
const start = src.indexOf('function paintModelName(');
ok(start >= 0, 'paintModelName is in index.html');
for (const role of ['receiver', 'dongle']) {
    const dom = makeDom();
    const sandbox = { document: dom.document, setTimeout: () => 0, console, URLSearchParams, fetch: async () => ({ ok: true, text: async () => '' }),
        LDRC: { setText() {}, viaBle: false }, saveFrontHint() {}, alert() {}, window: {} };
    sandbox.window = sandbox;
    vm.createContext(sandbox);
    let threw = null;
    try {
        vm.runInContext(src.slice(start), sandbox, { filename: 'index.html' });
        vm.runInContext(`paintModelName({ dongle: ${role === 'dongle'}, info: { name: 'RXV2', name_custom: false } })`, sandbox);
    } catch (e) { threw = e; }
    ok(!threw, role + ': naming gate script runs' + (threw ? ' — threw: ' + threw.message : ''));
    ok((dom.form.listeners.submit || []).length === 1, role + ': the Save handler is attached (no fall-back page reload)');
}
console.log(fails ? 'FAILED: ' + fails : 'ALL PASS');
process.exit(fails ? 1 : 0);
