#!/bin/sh
# (1.11.198) THE PAGE UNDER THE KEYBOARD: what the main board writes while a keyboard is up (it does not know one is) is
# kept for the page beneath, not filed under the keyboard's page; a finger that lands within a quarter of a second of a
# page coming up is not taken; the main board's markers stay out of the last-commands notes. The scenes run on the
# screen's own code (hmi/render_host: handle, the page loader, the keyboard, the card's real pages).
cd "$(dirname "$0")"
R=../render_host/gen/render
if [ ! -x "$R" ] || [ ../../src/main.cpp -nt "$R" ] || [ ../render_host/render.cpp -nt "$R" ] || [ ../render_host/extract.py -nt "$R" ]; then
    (cd ../render_host && ./build.sh >/dev/null 2>&1) || { echo "test_keyboard: the renderer did not build"; exit 1; }
fi
python3 check.py "$R"
