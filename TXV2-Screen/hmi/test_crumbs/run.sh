#!/bin/sh
# (1.11.99) The curve page's edge dots and rings reach past the box: the next clear must repair the cards around it.
# Renders hmi/scenarios/21_crumbs.txt with the screen's own drawing code (hmi/render_host) and checks the pixels.
cd "$(dirname "$0")"
R=../render_host/gen/render
if [ ! -x "$R" ] || [ ../../src/main.cpp -nt "$R" ]; then (cd ../render_host && ./build.sh >/dev/null 2>&1) || { echo "test_crumbs: the renderer did not build"; exit 1; }; fi
OUT="${TMPDIR:-/tmp}/crumbs_$$_"
"$R" ../../sd ../scenarios/21_crumbs.txt "$OUT" >/dev/null 2>&1 || { echo "test_crumbs: the renderer failed"; exit 1; }
python3 check.py "${OUT}21_crumbs_before.ppm" "${OUT}21_crumbs_after.ppm"
code=$?; rm -f "${OUT}"*.ppm; exit $code
