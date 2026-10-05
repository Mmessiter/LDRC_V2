# Page scenarios

What the Teensy sends to each page (one command a line, `\r` `\n` escapes), written from the Teensy's code
(TXV1B/TransmitterCode) on 2026-10-03 with realistic values and worst cases (`_long`), for the Mac renderer:

    python3 hmi/render_pages.py OUTDIR hmi/scenarios/*.txt     # one PNG per @shot

`@shot NAME` saves the screen, `@model 0|1` = no model / a model connected. Pages with no background of their own
(dialogs, the yes/no question) are drawn over the page they appear on. Re-render after any change to a page or to
the drawing code and look at the pictures before publishing (hmi/render_host/render.cpp, hmi/lint_pages.py).

`flight.txt`: the flight screen (screen 1.6.0) over a Rotorflight heli's front page - its boxes, warnings, no model,
the setup page and its chooser (renderer lines `@flying 1`, `@flight CONFIG|default`, `@flightsetup CONFIG [@box N]`).

`colours.txt`: the pilot's colours (screen 1.7.0; 1.7.6: Edit colours, a white page) - the Colours page, the Background page that opens it, Transmitter setup,
and the channel bars that grow from the middle (renderer lines `@theme PANEL TEXT`, e.g. `@theme wine cream`, and
`@colours [NAME ...]`, the Colours page with those colours touched first).

`flight_sizes.txt`: the flight screen's box sizes (screen 1.7.1) - all twelve layouts, numbers as big as their boxes, the
setup page and its choice of sizes (`@flightsetup CONFIG @sizes`).
Renderer words for the Colours page (1.7.6): `@colours edit red hsv:200,80,70`, `@colours white ink:burgundy`; a box's colour page: `@flightsetup CONFIG @box N @boxcolour F I`.
