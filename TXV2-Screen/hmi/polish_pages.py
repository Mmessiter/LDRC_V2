#!/usr/bin/env python3
"""POLISH (10 Oct 2026). Malcolm: "make the screens look more beautiful, well designed and easy to use ... Don't change the logic".
The LAST step for the pages: every page generator (restyle_batch*, islands.py, *_pages.py, apply_overrides.py ...) first, then this.
islands.py runs it by itself at its end. Each group of pages has its edits in hmi/polish/<group>.py:
    EDITS = {13: front_page, 26: channels, ...}      # page id -> function(page dict), setting ABSOLUTE values (hmi/polish helpers)
Run:  python3 hmi/polish_pages.py [ids ...]          apply (all pages that have edits, or just these)
      python3 hmi/polish_pages.py --check [ids ...]  change nothing; fail if any page is not as the polish makes it
Then: python3 hmi/logic_guard.py (nothing a page DOES has changed), hmi/lint_pages.py, and render the pictures."""
import copy, glob, importlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PAGES = os.path.join(HERE, '..', 'sd', 'hmi', 'pages')
sys.path.insert(0, HERE)

def edits():
    out = {}
    for f in sorted(glob.glob(os.path.join(HERE, 'polish', '*.py'))):
        mod = os.path.basename(f)[:-3]
        if mod.startswith('_'): continue
        m = importlib.import_module('polish.' + mod)
        for pid, fn in getattr(m, 'EDITS', {}).items():
            fns = fn if isinstance(fn, (list, tuple)) else [fn]
            out.setdefault(pid, []).extend((mod, f) for f in fns)
    return out

COMPACT = {0, 2, 9, 10, 11, 13, 14, 15, 17, 18, 21, 22, 26, 28, 30, 32, 34, 35, 36, 37, 38, 39, 41, 43, 44, 45, 47, 48, 52, 53, 54, 56, 57}
                                    # (the pages that were one compact line on 10 Oct 2026; islands.py rewrites some with indent=1)
def write(path, pg):
    """Keep the file's own form: a page that was one compact line (pagestyle.py's pages) stays one line, so the card and the
    screen's page loads do not grow; the others keep indent=1."""
    pid = int(os.path.basename(path)[:-5])
    compact = pid in COMPACT
    if compact: json.dump(pg, open(path, 'w'), separators=(',', ':'))
    else: json.dump(pg, open(path, 'w'), indent=1)

def run(ids=None, check=False):
    todo = edits(); bad = []
    for pid in sorted(todo):
        if ids and pid not in ids: continue
        path = os.path.join(PAGES, f'{pid}.json'); pg = json.load(open(path)); before = copy.deepcopy(pg)
        for mod, fn in todo[pid]: fn(pg)
        again = copy.deepcopy(pg)
        for mod, fn in todo[pid]: fn(again)
        if again != pg: bad.append(f'{pid}: the polish is not idempotent (a second run changes it)')
        if check:
            if pg != before: bad.append(f'{pid}: not polished (run python3 hmi/polish_pages.py {pid})')
        elif pg != before or (pid in COMPACT) != (b'\n' not in open(path, 'rb').read(4096)):
            write(path, pg)
    return bad

if __name__ == '__main__':
    args = sys.argv[1:]; check = '--check' in args
    ids = [int(a) for a in args if a.isdigit()]
    bad = run(ids or None, check)
    for b in bad: print('PROBLEM', b)
    print(f'polish: {len(edits())} page(s) have edits, {len(bad)} problem(s)')
    sys.exit(1 if bad else 0)
