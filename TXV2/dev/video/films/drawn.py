"""Where the screen's own drawn pages put their buttons (22 Oct 2026): the Appearance page, the Themes and Edit themes pages
(ESP32-board2 lib/LdrcTheme/LdrcTheme.cpp), the design page of the defined front screens and the defined front screen itself
(lib/LdrcFlight/LdrcFlight.cpp). These pages are not in sd/hmi/pages (the main board's pages), so at() cannot find their
buttons: the centres here are worked out from the rectangles in the code, and every touch is checked against the page as
drawn (filmkit's self-check) - a wrong number here fails the build, a wrong page would too."""

# ---- the Appearance page (AppearancePage::scene): an island 200,118 400x302; three buttons 62 high at 72 px; OK bottom right
APPEAR = {'Background picture': (400, 165), 'Themes': (400, 237), 'Defined front screens': (400, 309), 'OK': (504, 379), 'Help': (705, 29)}

# ---- the Themes page: twelve tiles 180 x 92 at 14 + (i % 4) * 197, 80 + (i // 4) * 106; the row of four at y 414 (slot(i): 14 + i * 197, 180 wide)
def theme_tile(i): return (104 + (i % 4) * 197, 126 + (i // 4) * 106)
THEMES = {'Cancel': (104, 442), 'Edit themes ...': (301, 442), 'Help': (498, 442), 'OK': (695, 442)}
# ---- Edit themes: twelve tiles 120 x 68 at 14 + (i % 3) * 126, 92 + (i // 3) * 78; Panel colour 400,210 189x44; Text colour 597,210; bars 400, 262 + k * 46, 282 wide
def edit_tile(i): return (74 + (i % 3) * 126, 126 + (i // 3) * 78)
EDIT = {'Panel colour': (494, 232), 'Text colour': (691, 232), 'Cancel': (104, 442), 'Defaults': (301, 442), 'Help': (498, 442), 'OK': (695, 442)}
def edit_bar(k, v):
    """bar k (0 Colour 0..359, 1 Strength 0..100, 2 Light 0..100) at value v"""
    return (400 + v * 281 // (359 if k == 0 else 100), 282 + k * 46)

# ---- the design page (FlightScreen::build, setup): tabs 38 x 42 at 546 + 42k, 8; boxes over 6,92 788x312; the row of four at y 414 (182 wide, 201 apart from x 6)
def design_tab(k): return (565 + 42 * k, 29)
def design_box6(i): return ((137, 399, 662)[i % 3], (170, 326)[i // 3])   # the six-box layout: 262 x 156 each
DESIGN = {'Box sizes': (97, 442), 'Stays lit': (298, 442), 'Help': (499, 442), 'OK': (700, 442)}
# a box's chooser: 18 choices 189 x 58 at 14 + (k % 4) * 194, 92 + (k // 4) * 63 (k = the thing's number - 1: Timer 0 ... Channels 1-16 16, Nothing 17)
def chooser_item(k): return (108 + (k % 4) * 194, 121 + (k // 4) * 63)
ITEM = {n: k for k, n in enumerate(['Timer', 'Batteries', 'Link', 'Frame rate', 'Head speed', 'ESC temperature', 'Current', 'Capacity used', 'Bank', 'Rate', 'Motor',
                                    'AMS and trims', 'Clock', 'Model name', 'Model image', 'Channels 1-8', 'Channels 1-16', 'Nothing'])}
CHOOSER = {'Theme': (108, 442), 'Round dial': (302, 442), 'Red zone': (496, 442), 'OK': (690, 442)}
# the box's theme page: twelve swatches 120 x 80 at 14 + (k % 4) * 126, 100 + (k // 4) * 90 (k = the theme's number - 1); Same as screens 14,414 246x56; OK slot(3)
def colour_swatch(n): k = n - 1; return (74 + (k % 4) * 126, 140 + (k // 4) * 90)
COLOUR = {'Same as screens': (137, 442), 'OK': (695, 442)}
# the red zone page: four steps 114 x 70 at 14 + k * 124, 262; None slot(0); OK slot(3)
def zone_step(k): return (71 + 124 * k, 297)
ZONE = {'None': (104, 442), 'OK': (695, 442)}
# Box sizes: twelve 185 x 97 at 14 + (k % 4) * 195, 92 + (k // 4) * 107, in FLIGHT_LAYOUTS' order; OK 599,414 186x56
def sizes_layout(k): return (106 + (k % 4) * 195, 140 + (k // 4) * 107)
SIZES_OK = (692, 442)

# ---- the defined front screen itself (FlightScreen::build, in flight): boxes over 6,56 788x362; Help 674,4 120x42; the tabs; the three buttons at y 424, 50 high
def flight_box6(i): return ((137, 399, 662)[i % 3], (146, 327)[i // 3])
FLIGHT_HELP = (734, 25)
