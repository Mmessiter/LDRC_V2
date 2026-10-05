// The flight screen (screen 1.6.0): what the pilot has chosen to see while flying, big and clear, in place of the
// front page. Malcolm, 2026-10-03: "could you create a user definable alternative front screen? This screen could be
// put up instead of our default front screen while flying containing those items of information that the user has
// selected."
//
// It is made of what the main board ALREADY sends to its front page (the timer, both batteries, the link, and with
// Rotorflight the head speed, the ESC's temperature, the current and the capacity used, the bank, the rate, the motor):
// the main board does nothing new in flight ("the Teensy flies, the screen talks"). The screen keeps its copy of the
// front page whatever is on the glass, and this screen is drawn on our own layer over it.
//
// Which front screen shows is the pilot's own choice, made with a button: the front page's "Defined screen" brings this
// one, its "Original screen" brings the front page back, and the choice stays, through take-offs and landings and a
// switch-off, until the other button is pressed. Nothing switches by itself (screen 1.9.8, Malcolm 10-05: "The When:
// Never etc button I think ought to go because we just hit a button to swap"). Set up on Transmitter setup >
// Appearance > Front screen: the screen as it will look, live; touch a box to choose what it shows.
//
// Portable: no Arduino, tested on the Mac (hmi/test_flight). The drawing is src/flight_draw.h, the rest
// src/flight_device.h.
#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include "LdrcTheme.h"

namespace ldrc {

enum FlightItem : uint8_t { FL_NONE = 0, FL_TIMER, FL_RXBAT, FL_TXBAT, FL_LINK, FL_FPS, FL_RPM, FL_ESC, FL_AMPS, FL_MAH,
                            FL_BANK, FL_RATE, FL_MOTOR, FL_CLOCK, FL_MODEL, FL_IMAGE, FL_BARS8, FL_BARS16, FL_ITEMS };
// (the settings keep the items' keys, not these numbers: a new item can go anywhere in the list)
const char *flightItemName(int item);                  // the chooser's words: "Flight battery"
const char *flightItemKey(int item);                   // the settings' words: "rxbat"
int flightItemByKey(const std::string &key);           // FL_NONE if not known
const char *flightItemReference(int item);             // the widest value it can be expected to show ("88:88"; "" for none, the bars)
const char *flightItemUnit(int item);                  // what follows its number ("V"; "" for none)
bool flightItemIsWords(int item);                      // it shows words, not a number (the bank, the rate, the model, the motor)

// The front page as the main board last wrote it. A box it shows only when it has news (the head speed, the current)
// counts only while it is shown.
struct FlightSource {
    virtual ~FlightSource() {}
    virtual bool shown(const char *comp) = 0;          // on the page and showing
    virtual std::string text(const char *comp) = 0;   // "" when never written
    virtual long number(const char *comp, long dflt) = 0;
    virtual bool linked() = 0;                         // a model is connected
    virtual bool flying() = 0;
    virtual long attribute(const char *comp, const char *attr, long dflt) { (void) comp; (void) attr; return dflt; }   // a colour the main board wrote ("bt0.bco="), -1 if never
};

enum FlightState : uint8_t { FS_NORMAL = 0, FS_GOOD, FS_WARN, FS_ALARM, FS_STALE, FS_EMPTY };
struct FlightValue {
    std::string label, big, unit, small;               // "Flight battery", "7.82", "V", "3.91 V per cell   78 %"
    FlightState state = FS_NORMAL;
    std::vector<uint8_t> bars;                         // channel bars (Malcolm, 10-03: "Channel bars (first 8 or all 16)"): each 0..100, 50 = centre, as the front page has them
    bool coloured = false; uint16_t face = 0, ink = 0; // the box takes these colours whatever its theme (1.9.13: the Motor box in the safety's colours, as the original front page's button)
    std::string image;                                 // the model's picture (Malcolm, 10-04: "can we add to the available box options 'model image'"): the front page's, by the name the main board gave it
};
FlightValue flightValue(int item, FlightSource &src);
// A warning the front page shows, for the flight screen's strip whatever its boxes: "Battery LOW", or no link in flight.
std::string flightAlert(FlightSource &src);

// The front page's words, read back
bool flightBattery(const std::string &s, float &total, float &perCell);    // "7.80V (3.90V per cell)"
bool flightNumberAfter(const std::string &s, const char *prefix, float &v); // "RPM: 2150", "ESC: 52.3"
std::string flightClock(const std::string &dateTime);                       // "3 Oct. 2026 20:31:07" -> "20:31"
std::string flightTimer(long hours, long mins, long secs);                  // 0, 4, 7 -> "4:07"

struct FlightRect {
    int16_t x = 0, y = 0, w = 0, h = 0;
    FlightRect() {}
    FlightRect(int x_, int y_, int w_, int h_) : x((int16_t) x_), y((int16_t) y_), w((int16_t) w_), h((int16_t) h_) {}
    bool has(int px, int py) const { return px >= x && px < x + w && py >= y && py < y + h; }
};

// The boxes' sizes (screen 1.7.1, Malcolm 2026-10-04: "It would also be great if a user could define the relative sizes
// of these boxes as inevitably some will be more important. Box size should be linked to font size."): a choice of
// layouts on a grid, the biggest box first - box 1 is the most important. A number is as big as its box allows.
static const int FLIGHT_MAX_BOXES = 9;
struct FlightCell { uint8_t c, r, cw, rh; };           // column, row, columns wide, rows high
struct FlightLayoutDef { const char *key, *name; uint8_t cols, rows, count; FlightCell cells[FLIGHT_MAX_BOXES]; };
static const int FLIGHT_LAYOUT_COUNT = 12, FLIGHT_DEFAULT_LAYOUT = 3;   // (six equal boxes, as before)
extern const FlightLayoutDef FLIGHT_LAYOUTS[FLIGHT_LAYOUT_COUNT];
int flightLayoutByKey(const std::string &key);         // -1 if not known
std::vector<FlightRect> flightLayout(int layout, const FlightRect &area, int gap = 6);

// The boxes' colours. Malcolm, 10-04: "When clicking a box to define its contents, can we also pick a colour for that
// box?" ... "I'd like to use some brighter options" ... and (screen 1.7.6): "I had thought the option to define the colours
// would occur on this screen [the Colours page] so that it can affect all of the backgrounds, and these options would
// simply be reused for the individual boxes on the defined front screen." So a box takes one of the Themes page's (1.8.4: twelve themes, each a panel colour with its own text colour)
// twelve panel colours and one of its six text colours (lib/LdrcTheme: the pilot's own, made on its Edit colours).

// Screens 1.6.0-1.9.7 had a rule as well ("When: never / flying / always", and a take-off or landing put the rule back):
// gone in 1.9.8. The setting is still written and read, so that older and newer screens read each other's settings,
// but nothing looks at it.
enum FlightWhen : uint8_t { FW_NEVER = 0, FW_FLYING = 1, FW_ALWAYS = 2 };
// The pilot's choice: "Original screen" keeps the front page, its "Defined screen" brings the pilot's own (screen 1.7.3,
// Malcolm 10-04: "On the original screen let's add 'use defined' as a middle button and on the defined let's add help
// button top right"). Kept with the settings (1.8.7; Malcolm: "it should boot up with whichever I was using last time").
// FM_NONE (never chosen) is the front page.
enum FlightManual : uint8_t { FM_NONE = 0, FM_ORIGINAL, FM_DEFINED };
struct FlightConfig {
    uint8_t when = FW_FLYING, layout = FLIGHT_DEFAULT_LAYOUT;   // (when: unused since 1.9.8, see above)
    bool stayOn = true;                                // while it shows, the main board's screen saver is told "someone is here"
    uint8_t manual = FM_NONE;                          // the pilot's choice (Original screen / Defined screen), kept across a switch-off
    uint8_t items[FLIGHT_MAX_BOXES] = { FL_TIMER, FL_RXBAT, FL_RPM, FL_LINK, FL_ESC, FL_MAH, FL_AMPS, FL_TXBAT, FL_BANK };
    // Each box's theme: 0 the screens' (it follows the Themes page), k the Themes page's theme k (its panel colour and its
    // text colour). Amber and red still take over a box whose value needs a look.
    uint8_t boxTheme[FLIGHT_MAX_BOXES] = { 0, 0, 0, 0, 0, 0, 0, 0, 0 };
    int boxes() const { return FLIGHT_LAYOUTS[layout < FLIGHT_LAYOUT_COUNT ? layout : FLIGHT_DEFAULT_LAYOUT].count; }
    // "f2 w1 grid6 s1 timer,rxbat,rpm,link,esc,mah,amps,txbat,bank b:,9,,10,,,,, m:1" - b: (each box's theme) only with
    // themes, m: (the choice of the moment) only with one (tokens at the end: a screen before 1.7.4 reads the rest and leaves
    // them); 1.7.6-1.8.3's "b:9.5" (panel . text colour) and 1.7.4's and 1.7.5's c: are still read
    std::string save() const;
    bool load(const std::string &s);                   // false (and the defaults kept) if it is not one of ours; screens 1.6.0-1.7.0 wrote "f1 w1 b6 s1 ..."
    bool operator==(const FlightConfig &o) const;
};

// The sizes of the screen's letters (the drawing's own, src/flight_draw.h): each box's number is as big as the box allows
struct FlightFonts {
    virtual ~FlightFonts() {}
    virtual int width(int font, const std::string &s) = 0;
    virtual int height(int font) = 0;
};
static const int FLIGHT_NUMBER_FONT = 1, FLIGHT_UNIT_FONT = 0, FLIGHT_MAX_SCALE = 48, FLIGHT_PAD = 12;   // the 64-pixel font, up to 3 times its size (in 16ths)

// What there is to draw: the flight screen, or its setup page (the boxes as they will be, a chooser, the buttons)
// A box. textFont: its name and small line (28 pixels in a big box, else 24); scale: its number's size in 16ths of the
// 64-pixel font, the same for every value it can show (worked out from the widest), and the same in boxes of one size.
// own: drawn in face and ink (a theme of its own), else in the screens' theme
struct FlightTile { int id = 0; FlightRect r; int item = FL_NONE; FlightValue v; bool pressed = false; uint32_t serial = 0; uint8_t textFont = 2; int16_t scale = 16;
                    uint8_t colour = 0; bool own = false; uint16_t face = 0, ink = 0; };
// layout: a choice of box sizes, drawn as its boxes. swatch: a colour to touch, drawn in face with its name in ink.
// label: words on the page, not a button.
struct FlightButton { int id = 0; FlightRect r; std::string text; bool chosen = false, pressed = false; uint32_t serial = 0; int8_t layout = -1;
                      uint8_t swatch = 0; uint16_t face = 0, ink = 0; bool label = false;
                      uint8_t usedBy = 0; };                   // (the chooser) this thing is already shown by box usedBy (1-9): marked, so it is not chosen twice by mistake
void flightSizeTiles(std::vector<FlightTile> &tiles, FlightFonts *fonts);
struct FlightScene {
    uint32_t layout = 0;                               // changes when everything must be drawn again
    bool setup = false;
    std::string title, left, middle, right, hint;      // the strip: (setup) the title; (flight) model, bank, clock
    std::string alert;                                 // (flight) a warning: the strip turns red and says it
    int stripRight = 800;                              // (flight) where the strip's words end on the right: the Help button is beyond
    std::vector<FlightTile> tiles;
    std::vector<FlightButton> buttons;
};
static const int FLIGHT_W = 800, FLIGHT_H = 480, FLIGHT_STRIP = 44, FLIGHT_SETUP_STRIP = 58;
// The flight screen's buttons along the bottom (screen 1.7.2, Malcolm 10-04: "any press returns to default. Instead, let's
// include 'use original' as an option, and on the defined front screen add the 'model setup' and 'transmitter setup'
// buttons"): a touch anywhere else does nothing. The setups are the front page's own buttons, pressed for the pilot.
static const int FLIGHT_BUTTONS_Y = 424, FLIGHT_BUTTONS_H = 50;

class FlightScreen {
public:
    FlightConfig cfg;
    uint16_t themeFace = 0x114A, themeInk = 0xFFFF;    // the screens' theme (the Themes page's): what a box follows
    uint16_t palPanels[THEME_COUNT], palInks[THEME_COUNT];   // the twelve themes on offer (set by the screen; as they came until then)
    FlightScreen();
    // Each pass of the screen's loop: where we are. blocked: the screen is blank, or another page of ours has it.
    void poll(uint32_t now, bool onFront, bool flying, bool blocked);
    bool showing() const { return shown; }             // the flight screen has the glass
    void useDefined();                                 // the front page's "Use defined": the flight screen, now, whatever the rule says
    void openSetup();
    void closeSetup();
    bool setupOpen() const { return setup; }
    bool takeSaved();                                  // true once after OK changed the settings: store them
    bool takeFrontPress(std::string &comp);            // true once after a button of the main board's: "b0" / "b1" (the front page's setups), "help"
    uint8_t manualChoice() const { return cfg.manual; }
    void touch(bool pressed, int x, int y, uint32_t now);   // while showing() or setupOpen(), at every pass: the chip drops samples mid-press, so a lift counts after 80 ms of none
    const FlightScene &scene(FlightSource &src, FlightFonts *fonts = nullptr);   // what to draw, now (fonts: the numbers' sizes)
private:
    bool shown = false, setup = false, saved = false;
    std::string frontPress;                            // the front page's button to press for the pilot ("b0", "b1"), "" none
    int chooser = -1;                                  // the box whose choice is being made, -1 none, CHOOSE_SIZES the box sizes
    int colourFor = -1;                                // the box whose theme is being chosen (its own page), -1 none
    static const int CHOOSE_SIZES = -2;
    void paint(FlightTile &t, int box) const;          // a box in its theme
    int pressedId = -1;                                // the button or box the finger came down on (setup)
    bool down = false, slidOff = false;                // the finger is down; it has left what it came down on (no action then)
    uint32_t lastSeen = 0;                             // the last sample with the finger on the glass: a lift is real after 80 ms of none
    int idAt(int x, int y) const;
    FlightConfig before;                               // the settings when the page opened
    FlightScene sc;
    void build(FlightSource &src, FlightFonts *fonts);
    void releaseOn(int id);
};

}  // namespace ldrc
