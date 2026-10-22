// The flight screen: see LdrcFlight.h.
#include "LdrcFlight.h"
#include "LdrcTheme.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <algorithm>

namespace ldrc {

// ------------------------------------------------------------------ the things a box can show
// ref: the widest value it is expected to show (its number's size in a box is worked out from this, so the number does
// not jump as the value changes); unit: what follows the number.
// (a box of two parts has no ref of its own: its parts' are below)
static const struct { const char *key, *name, *ref, *unit; } ITEMS[FL_ITEMS] = {
    { "none", "Nothing", "", "" }, { "timer", "Timer", "88:88", "" }, { "batts", "Batteries", "", "" },
    { "link", "Link", "100", "%" }, { "fps", "Frame rate", "888", "fps" }, { "rpm", "Head speed", "8888", "RPM" },
    { "esc", "ESC temperature", "188", "\xB0" "C" }, { "amps", "Current", "88.8", "A" }, { "mah", "Capacity used", "8888", "mAh" },
    { "bank", "Bank", "Bank 8", "" }, { "rate", "Rate", "Rate 8", "" }, { "motor", "Motor", "OFF", "" }, { "amstrim", "AMS and trims", "", "" },
    { "clock", "Clock", "88:88", "" }, { "model", "Model name", "RAW 420 MCM", "" }, { "image", "Model image", "", "" },
    { "bars8", "Channels 1-8", "", "" }, { "bars16", "Channels 1-16", "", "" } };
// The two parts of each box of two (1.11.70): the upper first. The trims' widest words: "This bank" (and "All banks").
static const struct { int item; const char *name, *shortName, *ref, *unit, *tagRef; } PARTS[] = {
    { FL_BATTS, "RX battery", "RX", "88.88", "V", "100 %" }, { FL_BATTS, "TX battery", "TX", "88.88", "V", "100 %" },
    { FL_AMSTRIM, "AMS", "AMS", "OFF", "", "" }, { FL_AMSTRIM, "Trims", "Trims", "This bank", "", "" } };
bool flightItemHasParts(int item) { return item == FL_BATTS || item == FL_AMSTRIM; }
static int partIndex(int item, int part) { for (int i = 0; i < (int) (sizeof(PARTS) / sizeof(PARTS[0])); i += 2) if (PARTS[i].item == item) return i + (part ? 1 : 0); return -1; }
const char *flightPartName(int item, int part) { const int i = partIndex(item, part); return i < 0 ? "" : PARTS[i].name; }
const char *flightPartShort(int item, int part) { const int i = partIndex(item, part); return i < 0 ? "" : PARTS[i].shortName; }
static const char *partTagRef(int item, int part) { const int i = partIndex(item, part); return i < 0 ? "" : PARTS[i].tagRef; }
const char *flightPartReference(int item, int part) { const int i = partIndex(item, part); return i < 0 ? "" : PARTS[i].ref; }
const char *flightPartUnit(int item, int part) { const int i = partIndex(item, part); return i < 0 ? "" : PARTS[i].unit; }
const char *flightItemName(int item) { return item > 0 && item < FL_ITEMS ? ITEMS[item].name : ITEMS[0].name; }
const char *flightItemKey(int item) { return item > 0 && item < FL_ITEMS ? ITEMS[item].key : ITEMS[0].key; }
const char *flightItemReference(int item) { return item > 0 && item < FL_ITEMS ? ITEMS[item].ref : ""; }
const char *flightItemUnit(int item) { return item > 0 && item < FL_ITEMS ? ITEMS[item].unit : ""; }
bool flightItemIsWords(int item) { return item == FL_BANK || item == FL_RATE || item == FL_MODEL || item == FL_MOTOR; }
// ------------------------------------------------------------------ the dials (1.11.102)
bool flightItemCanDial(int item) {
    return item == FL_TIMER || item == FL_BATTS || item == FL_LINK || item == FL_FPS || item == FL_RPM || item == FL_ESC || item == FL_AMPS || item == FL_MAH || item == FL_CLOCK;
}
// (1.11.105) The things whose danger line only the pilot knows (a head speed, a current, a capacity, a frame rate): the red
// zone page's starting value, its two steps and its most. The batteries, the link and the ESC temperature have their own.
bool flightItemTakesLimit(int item) { return item == FL_RPM || item == FL_AMPS || item == FL_MAH || item == FL_FPS; }
void flightLimitSteps(int item, int &start, int &small, int &big, int &top) {
    switch (item) {
    case FL_RPM: start = 2000; small = 100; big = 500; top = 9000; break;
    case FL_AMPS: start = 50; small = 5; big = 25; top = 500; break;
    case FL_MAH: start = 3000; small = 100; big = 500; top = 9900; break;
    default: start = 100; small = 5; big = 25; top = 500; break;      // (the frame rate: red below)
    }
}
// A gauge's scale as it starts (lo to hi, numbered every major), and the step its top grows by when a value goes beyond it
// (0: it never grows). The numbers are round ones a pilot expects: a head speed to 3000, a temperature to 120, a cell from
// 3.0 to 4.5 V (a high-voltage cell is 4.35 full).
static const struct { int item; float lo, hi, major, grow; uint8_t decimals; } SCALES[] = {
    { FL_RPM, 0, 3000, 1000, 1000, 0 }, { FL_ESC, 0, 120, 30, 30, 0 }, { FL_LINK, 0, 100, 25, 0, 0 }, { FL_FPS, 0, 200, 50, 100, 0 },
    { FL_AMPS, 0, 100, 25, 50, 0 }, { FL_MAH, 0, 5000, 1000, 1000, 0 }, { FL_BATTS, 3.0f, 4.5f, 0.5f, 0, 1 } };
static int scaleIndex(int item) { for (int i = 0; i < (int) (sizeof(SCALES) / sizeof(SCALES[0])); ++i) if (SCALES[i].item == item) return i; return -1; }
float flightDialTop(int item, float value) {
    const int i = scaleIndex(item);
    if (i < 0 || SCALES[i].grow <= 0 || !(value > SCALES[i].hi)) return 0;
    return SCALES[i].hi + std::ceil((value - SCALES[i].hi) / SCALES[i].grow) * SCALES[i].grow;
}
FlightDial flightDialOf(int item, int part, const FlightValue &v, float high, float limit) {
    FlightDial d;
    const bool has = part ? v.hasNum2 : v.hasNum; const float num = part ? v.num2 : v.num;
    if (!flightItemCanDial(item)) return d;
    d.has = has; d.value = has ? num : 0;                         // (1.11.104: no number yet - the scale all the same, the face drawn without a needle)
    if (item == FL_CLOCK) { d.kind = FD_CLOCK; d.lo = 0; d.hi = 12 * 60; d.major = 60; return d; }   // (the hands: hours round the face)
    if (item == FL_TIMER) { d.kind = FD_TIMER; d.lo = 0; d.hi = 60; d.major = 5; return d; }           // (seconds round the face)
    const int i = scaleIndex(item); if (i < 0) return d;
    d.kind = FD_GAUGE; d.lo = SCALES[i].lo; d.hi = SCALES[i].hi; d.major = SCALES[i].major; d.decimals = SCALES[i].decimals;
    const bool life = item == FL_BATTS && part == 1 && v.lifeTx;
    if (life) { d.lo = 2.8f; d.hi = 3.6f; d.major = 0.2f; }       // (1.11.105) a LiFePO4 transmitter battery: its own scale
    if (high > d.hi) d.hi = high;                                 // (grown to hold what it has shown)
    const bool ownLimit = limit > 0 && flightItemTakesLimit(item);
    if (ownLimit && item != FL_FPS && limit > d.hi) { const float top = flightDialTop(item, limit); if (top > d.hi) d.hi = top; }   // (the red zone in view: the scale grown to it)
    while (d.hi > d.lo && (d.hi - d.lo) / d.major > 6.5f) d.major *= 2;   // (never more than seven numbers round the scale)
    // (1.11.105) the zones: where the box turns amber and red (flightValue's own thresholds), or the pilot's red line
    if (item == FL_BATTS) {                                       // the main board's per cent is linear in the cell's volts (Telemetry.h): the flight battery 3.40 V (0 %) to 4.20 (100 %), the transmitter's LiPo 3.50 to 4.00, a LiFePO4 3.20 to 3.33; the box is amber at 40 %, red at 20 %
        const float v0 = part ? (life ? 3.2f : 3.5f) : 3.4f, v100 = part ? (life ? 3.33f : 4.0f) : 4.2f;
        d.redFrom = d.lo; d.redTo = v0 + (v100 - v0) * 0.2f; d.amberFrom = d.redTo; d.amberTo = v0 + (v100 - v0) * 0.4f;
    } else if (item == FL_LINK) { d.redFrom = 0; d.redTo = 50; d.amberFrom = 50; d.amberTo = 75; }
    else if (item == FL_ESC) { d.amberFrom = 80; d.amberTo = 95; d.redFrom = 95; d.redTo = d.hi; }
    else if (ownLimit) { if (item == FL_FPS) { d.redFrom = d.lo; d.redTo = limit; } else { d.redFrom = limit; d.redTo = d.hi; } }
    return d;
}
int flightItemByKey(const std::string &key) {
    for (int i = 0; i < FL_ITEMS; ++i) if (key == ITEMS[i].key) return i;
    if (key == "rxbat" || key == "txbat") return FL_BATTS;     // (before 1.11.70: a box for each battery)
    return FL_NONE;
}

// ------------------------------------------------------------------ the front page's words, read back
bool flightBattery(const std::string &s, float &total, float &perCell) {      // "7.80V (3.90V per cell)"
    float t = 0, c = 0;
    if (sscanf(s.c_str(), " %fV (%fV", &t, &c) != 2) return false;
    if (!(t > 0.1f && t < 100.0f) || !(c > 0.1f && c < 10.0f)) return false;
    total = t; perCell = c; return true;
}
bool flightNumberAfter(const std::string &s, const char *prefix, float &v) {   // "RPM: 2150" (the box's own words, nothing else)
    size_t at = s.find_first_not_of(' ');
    if (at == std::string::npos || s.compare(at, strlen(prefix), prefix) != 0) return false;
    const char *p = s.c_str() + at + strlen(prefix); char *end = nullptr;
    const double d = strtod(p, &end);
    if (end == p || !std::isfinite(d)) return false;
    v = (float) d; return true;
}
std::string flightClock(const std::string &dateTime) {                       // "3 Oct. 2026 20:31:07" -> "20:31"
    size_t c = dateTime.rfind(':');
    if (c == std::string::npos) return std::string();
    size_t c1 = dateTime.rfind(':', c - 1);
    if (c1 != std::string::npos) c = c1;                                       // HH:MM:SS: the first colon
    size_t start = dateTime.rfind(' ', c); start = start == std::string::npos ? 0 : start + 1;
    if (c < start || c + 3 > dateTime.size()) return std::string();
    return dateTime.substr(start, c + 3 - start);
}
std::string flightTimer(long hours, long mins, long secs) {
    char b[24];
    if (hours < 0 || mins < 0 || secs < 0) return "--";
    if (hours > 0) snprintf(b, sizeof(b), "%ld:%02ld:%02ld", hours, mins, secs);
    else snprintf(b, sizeof(b), "%ld:%02ld", mins, secs);
    return b;
}
static std::string fmt(const char *f, double v) { char b[32]; snprintf(b, sizeof(b), f, v); return b; }

FlightValue flightValue(int item, FlightSource &src) {
    FlightValue v; v.label = flightItemName(item);
    const bool linked = src.linked();
    auto unknown = [&](const char *small) { v.big = "--"; v.small = small ? small : ""; v.state = FS_STALE; };
    auto noModel = [&]() { return src.flying() ? "no link" : "no model"; };   // (in flight the model is there: it is the link that is not)
    float a = 0;
    switch (item) {
    case FL_NONE: v.label = ""; v.state = FS_EMPTY; break;
    case FL_TIMER: {
        const long hh = src.number("Hours", 0), mm = src.number("Mins", 0), ss = src.number("Secs", 0);
        v.big = flightTimer(hh, mm, ss);
        if (v.big != "--") { v.num = (float) (hh * 3600 + mm * 60 + ss); v.hasNum = true; }
        break;
    }
    case FL_BATTS: {                                   // (1.11.70) the flight battery above, the transmitter's below: two parts of one box
        v.twoPart = true; v.label = flightPartName(item, 0); v.label2 = flightPartName(item, 1);
        // each as the boxes of one battery were: the cell big, the whole pack below, named (1.10.9, Malcolm 10-06: "make the
        // PER CELL voltage big, and the total voltage smaller"). The small line says "total" so it cannot be read as the
        // cell (10-04: "per cell  7.82 V" below a big number had read as if the total were per cell).
        // The percentage is the part's tag, at the right of its name (or under it), so it is there in every size of box.
        auto battery = [&](bool rx, std::string &big, std::string &unit, std::string &small, std::string &tag, FlightState &state, int8_t &level, float &num, bool &hasNum) {
            float t = 0, c = 0;
            if (rx && !linked) { big = "--"; tag = noModel(); state = FS_STALE; return; }
            if (!flightBattery(src.text(rx ? "RXBV" : "TXBV"), t, c)) { big = "--"; state = FS_STALE; return; }
            const long pct = src.number(rx ? "JRX" : "JTX", -1);
            big = fmt("%.2f", c); unit = "V"; num = c; hasNum = true;
            if (!rx && pct >= 0) v.lifeTx = pct > (c - 3.5f) * 200.0f + 15.0f;   // (1.11.105) a per cent well above what a LiPo's volts would give: the main board is reading a LiFePO4 (its line 3.20 to 3.33 V)
            small = fmt("%.2f V total", t);
            if (pct >= 0 && pct <= 100) tag = fmt("%.0f %%", (double) pct);
            level = pct >= 0 && pct <= 100 ? (int8_t) pct : -1;   // (1.11.97) for the battery picture beside the name
            state = pct >= 0 && pct <= 20 ? FS_ALARM : pct >= 0 && pct <= 40 ? FS_WARN : FS_NORMAL;
            // (the front page's "Battery LOW" is for either battery: it turns the strip red, not this box)
        };
        battery(true, v.big, v.unit, v.small, v.tag, v.state, v.level, v.num, v.hasNum);
        battery(false, v.big2, v.unit2, v.small2, v.tag2, v.state2, v.level2, v.num2, v.hasNum2);
        break;
    }
    case FL_AMSTRIM: {                                 // (1.11.70) AMS above, the trims below, as the main board words them on the front page
        v.twoPart = true; v.label = flightPartName(item, 0); v.label2 = flightPartName(item, 1);
        // "AMS is on", "AMS is off"; "[AMS is on]": on, but the model in use has no receiver ID kept yet (Telemetry.h ShowAMS)
        const std::string ams = src.text("ams");
        if (ams.find("off") != std::string::npos) v.big = "OFF";
        else if (ams.find("on") != std::string::npos) { v.big = "ON"; if (ams.find('[') != std::string::npos) v.tag = "no model ID"; }
        else { v.big = "--"; v.state = FS_STALE; }
        // "Trims: all banks", "Trims: this bank" (whether a trim moves every bank's: CopyTrimsToAll); the page's own "TrimAll
        // is on" until the main board writes it
        const std::string tr = src.text("trall");
        if (tr.find("this") != std::string::npos || tr.find("off") != std::string::npos) v.big2 = "This bank";
        else if (tr.find("all") != std::string::npos || tr.find("on") != std::string::npos) v.big2 = "All banks";
        else { v.big2 = "--"; v.state2 = FS_STALE; }
        break;
    }
    case FL_LINK: {
        const long q = src.number("Quality", -1);
        if (!linked) { if (src.flying()) { v.big = "LOST"; v.state = FS_ALARM; } else unknown("no model"); break; }
        if (q < 0 || q > 100) { unknown(nullptr); break; }
        v.big = fmt("%.0f", (double) q); v.unit = "%"; v.num = (float) q; v.hasNum = true;
        v.state = q < 50 ? FS_ALARM : q < 75 ? FS_WARN : FS_NORMAL;
        break;
    }
    case FL_FPS: {                                     // packets a second (B26 writes "pps" to the front page once a second while a model is connected; the page has no such box: the screen keeps it)
        if (!linked) { unknown(noModel()); break; }
        const long p = src.number("pps", -1);
        if (p < 0 || p > 9999) { unknown(nullptr); break; }
        v.big = std::to_string(p); v.unit = "fps"; v.num = (float) p; v.hasNum = true;
        break;
    }
    case FL_RPM:
        if (!linked) { unknown(noModel()); break; }
        if (!flightNumberAfter(src.text("rpm"), "RPM:", a)) { unknown(nullptr); break; }   // (its words tell: the box is hidden at each page load until the main board shows it again)
        v.big = fmt("%.0f", a); v.unit = "RPM"; v.num = a; v.hasNum = true;
        break;
    case FL_ESC:
        if (!linked) { unknown(noModel()); break; }
        if (!flightNumberAfter(src.text("Warning"), "ESC:", a)) { unknown(nullptr); break; }   // (the same box says "Battery LOW" on other models: the words tell)
        v.big = fmt("%.0f", a); v.unit = "\xB0" "C"; v.num = a; v.hasNum = true;   // (the screen's fonts are ISO 8859-1: B0 is the degree sign)
        v.state = a >= 95 ? FS_ALARM : a >= 80 ? FS_WARN : FS_NORMAL;
        break;
    case FL_AMPS:
        if (!linked) { unknown(noModel()); break; }
        if (!flightNumberAfter(src.text("StillConnected"), "Amps:", a)) { unknown(nullptr); break; }   // ("Turning off... 5" in the same box is not a current)
        v.big = fmt("%.1f", a); v.unit = "A"; v.num = a; v.hasNum = true;
        break;
    case FL_MAH:
        if (!linked) { unknown(noModel()); break; }
        if (!flightNumberAfter(src.text("wb"), "mAh:", a)) { unknown(nullptr); break; }   // (nor is the buddy's news)
        v.big = fmt("%.0f", a); v.unit = "mAh"; v.num = a; v.hasNum = true;
        break;
    case FL_BANK: { const std::string t = src.text("t4"); if (t.empty() || t == "Bank") unknown(nullptr); else v.big = t; break; }
    case FL_RATE: { const std::string t = src.text("rate"); if (!src.shown("rate") || t.empty() || t == "Rate") unknown(nullptr); else v.big = t; break; }   // ("Rate": the page's own word, before the main board wrote any)
    case FL_MOTOR: {
        const std::string t = src.text("bt0");
        if (t.find("ON") != std::string::npos) { v.big = "ON"; v.state = FS_GOOD; }
        else if (t.find("OFF") != std::string::npos || t.find("off") != std::string::npos) v.big = "OFF";
        else unknown(nullptr);
        // 1.9.13 (Malcolm: "The Motor option in a screen box does not convey the state of Safety yet as on the original screen"):
        // the original page's motor button is coloured by the main board as the safety switch moves (red while the safety is
        // on, green when it is off, with white or black words: Motor_sign.h ShowSafety). The box takes the same colours, over
        // its theme, whenever the main board has written them.
        const long face = src.attribute("bt0", "bco", -1);
        if (face >= 0 && v.state != FS_EMPTY) {
            const long ink = src.attribute("bt0", "pco", -1);
            v.coloured = true; v.face = (uint16_t) face; v.ink = ink >= 0 ? (uint16_t) ink : (themeIsLight((uint16_t) face) ? 0x0000 : 0xFFFF);
            if (v.state == FS_GOOD) v.state = FS_NORMAL;   // (its words in the given colour, not the usual green)
        }
        break;
    }
    case FL_CLOCK: {
        const std::string t = flightClock(src.text("DateTime")); if (t.empty()) { unknown(nullptr); break; }
        v.big = t;
        int hh = 0, mm = 0;                                        // (the hands: minutes since midnight)
        if (sscanf(t.c_str(), "%d:%d", &hh, &mm) == 2 && hh >= 0 && hh < 24 && mm >= 0 && mm < 60) { v.num = (float) (hh * 60 + mm); v.hasNum = true; }
        break;
    }
    case FL_MODEL: { const std::string t = src.text("ModelName"); if (t.empty() || t == "Model name") unknown(nullptr); else v.big = t; break; }
    case FL_IMAGE: {                                   // the front page's picture (the main board names it at every visit: exp0.path), and nothing else:
        v.image = src.text("exp0");                     // no name above it (1.9.11, Malcolm: "I only want the image ... we can have a bigger image")
        if (v.image.empty()) unknown("no picture");     // (the box keeps its "Model image" label only while it has no picture to show)
        else v.label.clear();
        break;
    }
    case FL_BARS8: case FL_BARS16: {                      // the transmitter's own outputs: with a model or without
        const int n = item == FL_BARS8 ? 8 : 16;
        for (int i = 1; i <= n; ++i) {
            char nm[8]; snprintf(nm, sizeof(nm), "Ch%d", i);
            const long b = src.number(nm, 50);
            v.bars.push_back((uint8_t) (b < 0 ? 0 : b > 100 ? 100 : b));
        }
        break;
    }
    default: unknown(nullptr); break;
    }
    return v;
}

std::string flightAlert(FlightSource &src) {
    if (src.binding()) return "BINDING ENABLED";                  // B95: on every front screen, as the Original one says it
    if (src.flying() && !src.linked()) return "NO LINK";
    if (src.shown("Warning") && src.text("Warning").find("LOW") != std::string::npos) return "BATTERY LOW";
    return std::string();
}

// ------------------------------------------------------------------ the pilot's choice
// ------------------------------------------------------------------ the pilot's choice
// What screens 1.7.4 and 1.7.5 kept for a box's colour ("c:"): 1.7.4 the Colours page's names, 1.7.5 numbers of its pairs (read as themes now).
// Read as the colours on offer now that are the same (else the screens' colours).
static const struct { const char *key; uint16_t colour; } OLD_PANEL_NAMES[] = {
    { "navy", 0x114A }, { "royal", 0x19D2 }, { "slate", 0x3A4C }, { "teal", 0x028B }, { "forest", 0x1A65 }, { "olive", 0x4A42 },
    { "brown", 0x59C3 }, { "wine", 0x68A5 }, { "plum", 0x50EC }, { "grey", 0x31A7 }, { "midnight", 0x0865 }, { "black", 0x0000 } };
static const uint16_t OLD_PAIRS[12][2] = { { 0x114A, 0xFFFF }, { 0x028B, 0xFFFF }, { 0x1A65, 0xFFFF }, { 0x68A5, 0xFFFF }, { 0x50EC, 0xFFFF }, { 0x0000, 0xFFFF },
                                           { 0xD0A2, 0xFFFF }, { 0xFFFF, 0x8004 }, { 0xF680, 0x0000 }, { 0x863E, 0x114A }, { 0x2DEA, 0x0000 }, { 0xC639, 0x0000 } };
static uint8_t themeOf(uint16_t panel) { for (int i = 0; i < THEME_COUNT; ++i) if (THEME_PAIRS[i].panel == panel) return (uint8_t) (i + 1); return 0; }

std::string FlightConfig::save() const {
    char b[48]; snprintf(b, sizeof(b), "f2 w%u %s s%u ", (unsigned) when, FLIGHT_LAYOUTS[layout < FLIGHT_LAYOUT_COUNT ? layout : FLIGHT_DEFAULT_LAYOUT].key, stayOn ? 1u : 0u);
    std::string s = b;
    for (int i = 0; i < FLIGHT_MAX_BOXES; ++i) { if (i) s += ","; s += flightItemKey(items[i]); }
    bool themed = false; for (int i = 0; i < FLIGHT_MAX_BOXES; ++i) themed = themed || boxTheme[i];
    if (themed) {                                      // (a token of its own at the end: a screen before 1.7.4 reads the rest and leaves it)
        s += " b:";
        for (int i = 0; i < FLIGHT_MAX_BOXES; ++i) { if (i) s += ","; if (boxTheme[i]) s += std::to_string((int) boxTheme[i]); }
    }
    bool dials = false; for (int i = 0; i < FLIGHT_MAX_BOXES; ++i) dials = dials || boxDial[i];
    if (dials) {                                       // (1.11.102: the boxes that are dials; a screen before it leaves the token)
        s += " d:";
        for (int i = 0; i < FLIGHT_MAX_BOXES; ++i) { if (i) s += ","; if (boxDial[i]) s += "1"; }
    }
    bool zones = false; for (int i = 0; i < FLIGHT_MAX_BOXES; ++i) zones = zones || boxZone[i];
    if (zones) {                                       // (1.11.105: each box's own red zone; a screen before it leaves the token)
        s += " z:";
        for (int i = 0; i < FLIGHT_MAX_BOXES; ++i) { if (i) s += ","; if (boxZone[i]) s += std::to_string((int) boxZone[i]); }
    }
    if (manual == FM_ORIGINAL || manual == FM_DEFINED) s += manual == FM_ORIGINAL ? " m:1" : " m:2";   // (the choice of the moment: back after a switch-off)
    return s;
}
// The tokens of a list at the end ("b:9.,,10.5"), each handed over with its place
template <typename F> static void eachToken(const std::string &s, const char *tag, int n, F f) {
    const size_t at = s.find(tag); if (at == std::string::npos) return;
    const std::string l = s.substr(at + strlen(tag)); size_t a = 0; int k = 0;
    while (k < n && a <= l.size()) {
        size_t e = l.find_first_of(", ", a); if (e == std::string::npos) e = l.size();
        f(k++, l.substr(a, e - a));
        if (e >= l.size() || l[e] == ' ') break; a = e + 1;
    }
}
bool FlightConfig::load(const std::string &s) {
    FlightConfig c;
    unsigned w = 9, bx = 0, so = 9; char list[256] = { 0 }, lay[16] = { 0 };
    if (sscanf(s.c_str(), "f1 w%u b%u s%u %255s", &w, &bx, &so, list) == 4) {            // screens 1.6.0 to 1.7.0: 4, 6 or 9 equal boxes
        if (bx != 4 && bx != 6 && bx != 9) return false;
        c.layout = (uint8_t) flightLayoutByKey(bx == 4 ? "grid4" : bx == 6 ? "grid6" : "grid9");
    } else if (sscanf(s.c_str(), "f2 w%u %15s s%u %255s", &w, lay, &so, list) == 4) {
        const int l = flightLayoutByKey(lay); if (l < 0) return false;
        c.layout = (uint8_t) l;
    } else return false;
    if (w > FW_ALWAYS || so > 1) return false;
    c.when = (uint8_t) w; c.stayOn = so == 1;
    std::string l = list; size_t at = 0; int i = 0;
    bool rxbat = false; int txbatAt[FLIGHT_MAX_BOXES], txbats = 0;
    while (i < FLIGHT_MAX_BOXES && at <= l.size()) {
        size_t e = l.find(',', at); if (e == std::string::npos) e = l.size();
        const std::string key = l.substr(at, e - at);
        if (key == "rxbat") rxbat = true; else if (key == "txbat") txbatAt[txbats++] = i;
        c.items[i++] = (uint8_t) flightItemByKey(key);
        at = e + 1;
    }
    for (; i < FLIGHT_MAX_BOXES; ++i) c.items[i] = FL_NONE;
    // (1.11.70) a definition from before, with a box for each battery: the batteries' box where the flight battery's was,
    // and the box the transmitter's had shows AMS and trims (the other new box), not the batteries twice
    if (rxbat) for (int k = 0; k < txbats; ++k) c.items[txbatAt[k]] = FL_AMSTRIM;
    eachToken(s, " c:", FLIGHT_MAX_BOXES, [&](int k, const std::string &t) {   // (1.7.4: a name; 1.7.5: a pair's number): the theme with that panel colour
        if (t.empty()) return;
        if (t.find_first_not_of("0123456789") == std::string::npos) { const int n = atoi(t.c_str()); if (n >= 1 && n <= 12) c.boxTheme[k] = themeOf(OLD_PAIRS[n - 1][0]); }
        else for (auto &o : OLD_PANEL_NAMES) if (t == o.key) c.boxTheme[k] = themeOf(o.colour);
    });
    eachToken(s, " b:", FLIGHT_MAX_BOXES, [&](int k, const std::string &t) {   // "9": the box's theme ("" the screens'); 1.7.6-1.8.3's "9.5" (panel . text colour): the panel's theme
        if (t.empty() || !(t[0] >= '0' && t[0] <= '9')) return;
        const int f = atoi(t.c_str());
        c.boxTheme[k] = (uint8_t) (f >= 1 && f <= THEME_COUNT ? f : 0);
    });
    eachToken(s, " d:", FLIGHT_MAX_BOXES, [&](int k, const std::string &t) { c.boxDial[k] = t == "1" ? 1 : 0; });   // (1.11.102) "1": a dial
    eachToken(s, " z:", FLIGHT_MAX_BOXES, [&](int k, const std::string &t) {   // (1.11.105) "2400": the box's own red zone
        const int z = (!t.empty() && t[0] >= '0' && t[0] <= '9') ? atoi(t.c_str()) : 0; c.boxZone[k] = (uint16_t) (z > 0 && z <= 60000 ? z : 0); });
    { const size_t m = s.find(" m:"); if (m != std::string::npos) { const int v = atoi(s.c_str() + m + 3); if (v == FM_ORIGINAL || v == FM_DEFINED) c.manual = (uint8_t) v; } }
    *this = c; return true;
}
bool FlightConfig::operator==(const FlightConfig &o) const {
    if (when != o.when || layout != o.layout || stayOn != o.stayOn || manual != o.manual) return false;
    for (int i = 0; i < FLIGHT_MAX_BOXES; ++i) if (items[i] != o.items[i] || boxTheme[i] != o.boxTheme[i] || boxDial[i] != o.boxDial[i] || boxZone[i] != o.boxZone[i]) return false;
    return true;
}

// ------------------------------------------------------------------ the boxes
// In the order the chooser shows them. Each box is a block of a grid's cells; box 1 the biggest, then reading order.
const FlightLayoutDef FLIGHT_LAYOUTS[FLIGHT_LAYOUT_COUNT] = {
    { "one", "1 box", 1, 1, 1, { { 0, 0, 1, 1 } } },
    { "two", "2 boxes", 2, 1, 2, { { 0, 0, 1, 1 }, { 1, 0, 1, 1 } } },
    { "grid4", "4 boxes", 2, 2, 4, { { 0, 0, 1, 1 }, { 1, 0, 1, 1 }, { 0, 1, 1, 1 }, { 1, 1, 1, 1 } } },
    { "grid6", "6 boxes", 3, 2, 6, { { 0, 0, 1, 1 }, { 1, 0, 1, 1 }, { 2, 0, 1, 1 }, { 0, 1, 1, 1 }, { 1, 1, 1, 1 }, { 2, 1, 1, 1 } } },
    { "grid9", "9 boxes", 3, 3, 9, { { 0, 0, 1, 1 }, { 1, 0, 1, 1 }, { 2, 0, 1, 1 }, { 0, 1, 1, 1 }, { 1, 1, 1, 1 }, { 2, 1, 1, 1 },
                                     { 0, 2, 1, 1 }, { 1, 2, 1, 1 }, { 2, 2, 1, 1 } } },
    { "big2", "1 big, 2 small", 3, 2, 3, { { 0, 0, 2, 2 }, { 2, 0, 1, 1 }, { 2, 1, 1, 1 } } },
    { "big4", "1 big, 4 small", 4, 2, 5, { { 0, 0, 2, 2 }, { 2, 0, 1, 1 }, { 3, 0, 1, 1 }, { 2, 1, 1, 1 }, { 3, 1, 1, 1 } } },
    { "big6", "1 big, 6 small", 4, 3, 7, { { 0, 0, 2, 3 }, { 2, 0, 1, 1 }, { 3, 0, 1, 1 }, { 2, 1, 1, 1 }, { 3, 1, 1, 1 }, { 2, 2, 1, 1 }, { 3, 2, 1, 1 } } },
    { "wide3", "1 wide, 3 small", 3, 2, 4, { { 0, 0, 3, 1 }, { 0, 1, 1, 1 }, { 1, 1, 1, 1 }, { 2, 1, 1, 1 } } },
    { "wide4", "1 wide, 4 small", 4, 2, 5, { { 0, 0, 4, 1 }, { 0, 1, 1, 1 }, { 1, 1, 1, 1 }, { 2, 1, 1, 1 }, { 3, 1, 1, 1 } } },
    { "two3", "2 big, 3 small", 6, 5, 5, { { 0, 0, 3, 3 }, { 3, 0, 3, 3 }, { 0, 3, 2, 2 }, { 2, 3, 2, 2 }, { 4, 3, 2, 2 } } },
    { "two4", "2 big, 4 small", 4, 5, 6, { { 0, 0, 2, 3 }, { 2, 0, 2, 3 }, { 0, 3, 1, 2 }, { 1, 3, 1, 2 }, { 2, 3, 1, 2 }, { 3, 3, 1, 2 } } } };
int flightLayoutByKey(const std::string &key) {
    for (int i = 0; i < FLIGHT_LAYOUT_COUNT; ++i) if (key == FLIGHT_LAYOUTS[i].key) return i;
    return -1;
}
std::vector<FlightRect> flightLayout(int layout, const FlightRect &a, int gap) {
    const FlightLayoutDef &d = FLIGHT_LAYOUTS[layout >= 0 && layout < FLIGHT_LAYOUT_COUNT ? layout : FLIGHT_DEFAULT_LAYOUT];
    // the grid's lines spread evenly over the area, a gap on the far side of each cell but the last
    auto edge = [gap](int start, int size, int n, int i) { return start + i * (size + gap) / n; };
    std::vector<FlightRect> out;
    for (int k = 0; k < d.count; ++k) {
        const FlightCell &c = d.cells[k];
        const int x0 = edge(a.x, a.w, d.cols, c.c), x1 = edge(a.x, a.w, d.cols, c.c + c.cw) - gap;
        const int y0 = edge(a.y, a.h, d.rows, c.r), y1 = edge(a.y, a.h, d.rows, c.r + c.rh) - gap;
        out.push_back(FlightRect(x0, y0, x1 - x0, y1 - y0));
    }
    return out;
}

// Each box's letters: its number as big as the box allows for the widest value its thing is expected to show, at most
// three times the 64-pixel font; boxes of one size alike (the smallest of theirs); the name and the small line bigger in a
// big box. (Box size linked to font size: Malcolm, 10-04.)
// A box of two parts: two equal parts, 6 or 7 px apart (1.11.71, Malcolm 15 Oct: "RX and TX voltages should employ the same
// format. Both should have per cell volts emphasised". 1.11.70 gave the upper part 58 %: the TX's number was the smaller,
// and a small box had no room for its per cent).
void flightSplit(const FlightRect &r, FlightRect &upper, FlightRect &lower) {
    const int gap = 6, h = (r.h - gap) / 2;
    upper = FlightRect(r.x, r.y, r.w, h); lower = FlightRect(r.x, r.y + r.h - h, r.w, h);
}
// A part's number: as big as its area allows for the widest it is expected to show, at most three times the 64-pixel font
static int16_t partScale(const FlightRect &a, const char *ref, const char *unit, FlightFonts *f) {
    if (!f || a.w <= 0 || a.h <= 0) return 0;
    int s = a.h * 16 / f->height(FLIGHT_NUMBER_FONT);
    const int refW = f->width(FLIGHT_NUMBER_FONT, ref) + (*unit ? 8 + f->width(FLIGHT_UNIT_FONT, unit) : 0);
    if (refW > 0 && a.w * 16 / refW < s) s = a.w * 16 / refW;
    return (int16_t) (s < 0 ? 0 : s > FLIGHT_MAX_SCALE ? FLIGHT_MAX_SCALE : s);
}
FlightPartPlan flightPartPlan(const FlightRect &p, int item, int part, FlightFonts *f) {
    FlightPartPlan st, rw;                                             // the two forms; the one with the bigger number is taken
    st.font = rw.font = p.h >= 180 && p.w >= 240 ? 6 : 2;
    const int nameH = f ? f->height(st.font) : 24;
    st.small = p.h >= 130;                                            // (the small line only where there is room for it)
    const int top = p.y + 8 + nameH, bottom = p.y + p.h - 8 - (st.small ? nameH : 0);
    st.number = FlightRect(p.x + FLIGHT_PAD, top, p.w - 2 * FLIGHT_PAD, bottom > top ? bottom - top : 0);
    rw.row = true;                                                    // the short name on the left, its tag under it if both lines fit
    // (1.11.71) the column as wide as the wider of the box's two parts' words: both parts' numbers start at one place, and
    // the two batteries are drawn alike. Both lines fit with 4 px to spare (a 53 px part of a nine-box screen keeps its per cent).
    const int other = part ? 0 : 1;
    auto wider = [&](const char *a, const char *b) { return f ? std::max(f->width(rw.font, a), f->width(rw.font, b)) : 60; };
    int col = wider(flightPartShort(item, part), flightPartShort(item, other));
    rw.tagBelow = p.h >= 2 * nameH + 4 && *partTagRef(item, part);
    if (rw.tagBelow && f) col = std::max(col, wider(partTagRef(item, part), partTagRef(item, other)));
    if (item == FL_BATTS && f && p.w >= 180)                            // (1.11.97) room for the battery picture beside the name
        col = std::max(col, wider(flightPartShort(item, part), flightPartShort(item, other)) + 8 + flightGlyphW(nameH));
    if (col + 12 > p.w / 2) col = p.w / 2 - 12;                       // (the number keeps half the part at least)
    rw.column = col;
    rw.number = FlightRect(p.x + 10 + col + 12, p.y + 4, p.w - 20 - col - 12, p.h - 8);
    const char *ref = flightPartReference(item, part), *unit = flightPartUnit(item, part);
    const int sS = st.number.h >= 20 ? partScale(st.number, ref, unit, f) : -1, sR = partScale(rw.number, ref, unit, f);
    return sR > sS ? rw : st;
}
void flightSizeTiles(std::vector<FlightTile> &tiles, FlightFonts *f) {
    for (auto &t : tiles) t.textFont = t.r.h >= 240 && t.r.w >= 240 ? 6 : 2;
    if (!f) return;
    for (auto &t : tiles) {                                           // (1.11.70) a box of two parts: each part's number for itself
        if (!flightItemHasParts(t.item)) continue;
        FlightRect up, low; flightSplit(t.r, up, low);
        t.scale = partScale(flightPartPlan(up, t.item, 0, f).number, flightPartReference(t.item, 0), flightPartUnit(t.item, 0), f);
        t.scale2 = partScale(flightPartPlan(low, t.item, 1, f).number, flightPartReference(t.item, 1), flightPartUnit(t.item, 1), f);
        if (t.item == FL_BATTS) t.scale = t.scale2 = std::min(t.scale, t.scale2);   // (1.11.71: the two batteries' numbers alike)
    }
    for (auto &t : tiles) {
        const char *ref = flightItemReference(t.item), *unit = flightItemUnit(t.item);
        if (!*ref) continue;
        const int areaW = t.r.w - 2 * FLIGHT_PAD, areaH = t.r.h - 16 - 2 * f->height(t.textFont);   // (its name above, its small line below)
        int s = areaH > 0 ? areaH * 16 / f->height(FLIGHT_NUMBER_FONT) : 0;
        const int refW = f->width(FLIGHT_NUMBER_FONT, ref) + (*unit ? 8 + f->width(FLIGHT_UNIT_FONT, unit) : 0);
        if (refW > 0 && areaW * 16 / refW < s) s = areaW * 16 / refW;
        t.scale = (int16_t) (s < 0 ? 0 : s > FLIGHT_MAX_SCALE ? FLIGHT_MAX_SCALE : s);
    }
    // Boxes of one size show their numbers at one size, the smallest of theirs. Words (a bank's name, the model's) go as
    // big as their own box allows, but never bigger than the numbers beside them: a long model name does not shrink the clock.
    std::vector<int16_t> own(tiles.size());
    for (size_t i = 0; i < tiles.size(); ++i) own[i] = tiles[i].scale;
    for (size_t i = 0; i < tiles.size(); ++i) {
        FlightTile &t = tiles[i];
        if (!*flightItemReference(t.item)) continue;
        for (size_t j = 0; j < tiles.size(); ++j) {
            const FlightTile &o = tiles[j];
            if (j == i || !*flightItemReference(o.item) || flightItemIsWords(o.item) || std::abs(o.r.w - t.r.w) > 2 || std::abs(o.r.h - t.r.h) > 2) continue;
            if (own[j] < t.scale) t.scale = own[j];
        }
    }
}

// ------------------------------------------------------------------ the flight screen and its setup page
void FlightScreen::poll(uint32_t now, bool onFront, bool flying, bool blocked) {
    (void) now; inFlight = flying;                     // (1.9.8: taking off or landing changes nothing; the buttons choose)
    const bool want = cfg.manual == FM_DEFINED;
    const bool was = shown;
    shown = !setup && want && onFront && !blocked;
    if (shown != was && !setup) { down = false; pressedId = -1; slidOff = false; }   // a finger on the glass as it came or went was not for it
}
void FlightScreen::useDefined() { if (cfg.manual != FM_DEFINED) { cfg.manual = FM_DEFINED; saved = true; } }   // (kept: the same screen after a switch-off)
void FlightScreen::openSetup() { setup = true; shown = false; chooser = -1; colourFor = -1; zoneFor = -1; pressedId = -1; down = slidOff = false; quickEdit = false; before = cfg; }
void FlightScreen::chooseSlot(int k) {
    if (k < 0 || k >= FLIGHT_SLOTS || k == slotNo) return;
    slots[slotNo] = cfg;                               // what was being used or edited, kept in its slot
    const uint8_t m = cfg.manual;
    slotNo = k; cfg = slots[k]; cfg.manual = m;        // (the choice of the moment is the pilot's, not the slot's)
    before = cfg; saved = true;                        // (the slot in use is a setting: stored)
}
bool FlightScreen::loadSlot(int k, const std::string &s) {
    if (k < 0 || k >= FLIGHT_SLOTS) return false;
    if (k == slotNo) return cfg.load(s);
    return slots[k].load(s);
}
void FlightScreen::closeSetup() { setup = false; chooser = -1; colourFor = -1; zoneFor = -1; pressedId = -1; down = slidOff = false; quickEdit = false; if (!(cfg == before)) saved = true; }
bool FlightScreen::takeSaved() { const bool s = saved; saved = false; return s; }
bool FlightScreen::takeFrontPress(std::string &comp) { if (frontPress.empty()) return false; comp = frontPress; frontPress.clear(); return true; }

static uint32_t hashOf(const std::string &s, uint32_t h) { for (unsigned char c : s) h = (h ^ c) * 16777619u; return h; }
static const int ID_BOXES = 101, ID_STAY = 102, ID_OK = 103, ID_BACK = 104, ID_ITEM = 200, ID_LAYOUT = 300;
static const int ID_TXSETUP = 110, ID_ORIGINAL = 111, ID_MODELSETUP = 112, ID_HELP = 113;
static const int ID_COLOUR = 120, ID_COLOUR_DONE = 121, ID_SAME = 122, ID_DIAL = 123, ID_FACE = 500, ID_SLOT = 600;
static const int ID_ZONE = 124, ID_ZONE_DOWN2 = 125, ID_ZONE_DOWN = 126, ID_ZONE_UP = 127, ID_ZONE_UP2 = 128, ID_ZONE_NONE = 129, ID_ZONE_DONE = 130, ID_ZONE_VALUE = 131;   // (1.11.105) the red zone page
static const int SLOT_Y = 414, SLOT_H = 56, SLOT_W = 180;
static FlightRect slot(int i) { return FlightRect(14 + i * 197, SLOT_Y, SLOT_W, SLOT_H); }

void FlightScreen::build(FlightSource &src, FlightFonts *fonts) {
    sc = FlightScene(); sc.setup = setup;
    if (!setup) {
        sc.layout = 1000 + cfg.layout + 32 * slotNo;
        sc.left = src.text("ModelName"); if (sc.left == "Model name") sc.left.clear();
        sc.middle = src.text("t4"); if (sc.middle == "Bank") sc.middle.clear();
        sc.alert = flightAlert(src);                        // (1.10.1: no clock in the strip - the six tabs take its place; a Clock box shows the time)
        const std::vector<FlightRect> rs = flightLayout(cfg.layout, FlightRect(6, FLIGHT_STRIP + 6, FLIGHT_W - 12, FLIGHT_BUTTONS_Y - 6 - (FLIGHT_STRIP + 6)));
        for (size_t i = 0; i < rs.size(); ++i) { FlightTile t; t.id = (int) i; t.r = rs[i]; t.item = cfg.items[i]; paint(t, (int) i); t.v = flightValue(t.item, src); if (t.v.coloured) { t.own = true; t.face = t.v.face; t.ink = t.v.ink; } sc.tiles.push_back(t); }
        // along the bottom, as on the front page: the transmitter's setup on the left, the model's on the right
        // (Malcolm, 10-04: "Transmitter  Original screen  Model", as the front page's row reads "Transmitter  Defined screen  Model")
        static const struct { int id; const char *text; } BUTTONS[] = { { ID_TXSETUP, "Transmitter" }, { ID_ORIGINAL, "Original screen" }, { ID_MODELSETUP, "Model" } };
        const int bw = (FLIGHT_W - 12 - 2 * 19) / 3;
        for (int k = 0; k < 3; ++k) { FlightButton bt; bt.id = BUTTONS[k].id; bt.r = FlightRect(6 + k * (bw + 19), FLIGHT_BUTTONS_Y, bw, FLIGHT_BUTTONS_H); bt.text = BUTTONS[k].text; sc.buttons.push_back(bt); }
        // and Help at the top right, as on the front page: this screen's own help (FLIGHT.TXT on the main board's card)
        FlightButton help; help.id = ID_HELP; help.r = FlightRect(FLIGHT_W - 6 - 120, 4, 120, 42); help.text = "Help"; sc.buttons.push_back(help);   // (top and bottom in line with the tabs)
        // the six screens as small tabs before Help (1.10.1, Malcolm: "when a defined front screen is in view, please try to
        // squeeze in those 6 buttons so that a user can rapidly switch to another defined screen"): the one in use yellow
        const int tabW = 38, tabGap = 4, tabsX = help.r.x - 6 - (FLIGHT_SLOTS * tabW + (FLIGHT_SLOTS - 1) * tabGap);   // (1.10.5: as big as the setup page's, Malcolm: "a bit too small")
        for (int k = 0; k < FLIGHT_SLOTS; ++k) { FlightButton tb; tb.id = ID_SLOT + k; tb.r = FlightRect(tabsX + k * (tabW + tabGap), 4, tabW, 42); tb.text = std::to_string(k + 1); tb.chosen = k == slotNo; sc.buttons.push_back(tb); }   // (38 x 42: the setup page's)
        sc.stripRight = tabsX - 6;
    } else if (zoneFor >= 0) {                            // (1.11.105) a box's red zone: the limit big, steps either way, the box at the right as it will look
        sc.layout = 6000 + zoneFor; sc.title = "Defined front screen";
        const int item = cfg.items[zoneFor]; int start, small, big, top; flightLimitSteps(item, start, small, big, top);
        char b[80]; snprintf(b, sizeof(b), item == FL_FPS ? "Box %d: the red zone ends at" : "Box %d: the red zone starts at", zoneFor + 1); sc.hint = b;
        FlightTile t; t.id = 0; t.r = FlightRect(528, 100, 258, 260); t.item = item; paint(t, zoneFor); t.dial = true; t.v = flightValue(t.item, src); sc.tiles.push_back(t);   // (as the theme page: the box at the right, as a dial whatever was chosen)
        const int z = cfg.boxZone[zoneFor];
        FlightButton bt; bt.id = ID_ZONE_VALUE; bt.label = true; bt.centred = true; bt.font = 1; bt.r = FlightRect(14, 150, 486, 80);
        bt.text = z ? std::to_string(z) + " " + flightItemUnit(item) : "None"; sc.buttons.push_back(bt);
        static const struct { int id, sign, bigStep; } STEPS[] = { { ID_ZONE_DOWN2, -1, 1 }, { ID_ZONE_DOWN, -1, 0 }, { ID_ZONE_UP, 1, 0 }, { ID_ZONE_UP2, 1, 1 } };
        for (int k = 0; k < 4; ++k) {
            FlightButton sb; sb.id = STEPS[k].id; sb.r = FlightRect(14 + k * 124, 262, 114, 70);
            snprintf(b, sizeof(b), "%s%d", STEPS[k].sign < 0 ? "-" : "+", STEPS[k].bigStep ? big : small); sb.text = b; sc.buttons.push_back(sb);
        }
        bt = FlightButton(); bt.id = ID_ZONE_NONE; bt.r = slot(0); bt.text = "None"; sc.buttons.push_back(bt);   // (no red zone)
        bt.id = ID_ZONE_DONE; bt.r = slot(3); bt.text = "OK"; sc.buttons.push_back(bt);          // (OK at the bottom right, as on every page)
    } else if (colourFor >= 0) {                          // a box's theme: the Themes page's twelve, the box as it will look
        sc.layout = 5000 + colourFor; sc.title = "Defined front screen";
        char b[64]; snprintf(b, sizeof(b), "Choose a theme for box %d.", colourFor + 1); sc.hint = b;
        FlightTile t; t.id = 0; t.r = FlightRect(528, 100, 258, 260); t.item = cfg.items[colourFor]; paint(t, colourFor); t.v = flightValue(t.item, src);   // (top and bottom in line with the themes beside it)
        if (t.item == FL_NONE) { t.v.label = "Nothing"; t.v.state = FS_NORMAL; t.v.big = "--"; }
        sc.tiles.push_back(t);
        const int f = cfg.boxTheme[colourFor];
        int mark = f ? f - 1 : -1;                                    // (following the screens: their theme marked, where it is on offer)
        if (mark < 0) for (int k = THEME_COUNT - 1; k >= 0; --k) if (palPanels[k] == themeFace && palInks[k] == themeInk) mark = k;
        for (int k = 0; k < THEME_COUNT; ++k) {                       // four to a row, three rows, each in its own two colours
            FlightButton bt; bt.id = ID_FACE + k; bt.r = FlightRect(14 + (k % 4) * 126, 100 + (k / 4) * 90, 120, 80);
            bt.swatch = (uint8_t) (k + 1); bt.face = palPanels[k]; bt.ink = palInks[k];
            bt.text = std::to_string(k + 1); bt.chosen = k == mark;                         // (by number, as on the Themes page)
            for (int j = 0; j < cfg.boxes(); ++j)                                             // (1.9.14, Malcolm: "which themes have already been used") the other boxes wearing it
                if (j != colourFor && cfg.boxTheme[j] == k + 1) bt.usedBoxes += (bt.usedBoxes.empty() ? "" : " ") + std::to_string(j + 1);
            sc.buttons.push_back(bt);
        }
        // (OK at the bottom right, as on every page - Malcolm, 10-04; "Same as screens" on the left)
        FlightButton bt; bt.id = ID_SAME; bt.r = FlightRect(14, 414, 246, 56); bt.text = "Same as screens"; sc.buttons.push_back(bt);   // (its right edge under the second column of themes)
        bt.id = ID_COLOUR_DONE; bt.r = slot(3); bt.text = "OK"; sc.buttons.push_back(bt);
    } else if (chooser == -1) {
        sc.layout = 2000 + cfg.layout + 32 * slotNo; sc.title = "Defined front screen"; sc.hint = "Touch a box to choose what it shows."; sc.tabs = true;
        for (int k = 0; k < FLIGHT_SLOTS; ++k) {                      // the six definitions, as tabs in the strip: the one in use marked
            FlightButton tb; tb.id = ID_SLOT + k; tb.r = FlightRect(FLIGHT_W - 6 - (FLIGHT_SLOTS - k) * 42 + 4, 8, 38, 42); tb.text = std::to_string(k + 1); tb.chosen = k == slotNo; sc.buttons.push_back(tb);
        }
        const std::vector<FlightRect> rs = flightLayout(cfg.layout, FlightRect(6, 92, FLIGHT_W - 12, 312));
        for (size_t i = 0; i < rs.size(); ++i) { FlightTile t; t.id = (int) i; t.r = rs[i]; t.item = cfg.items[i]; paint(t, (int) i); t.v = flightValue(t.item, src); if (t.v.coloured) { t.own = true; t.face = t.v.face; t.ink = t.v.ink; } t.pressed = pressedId == (int) i && !slidOff;
                                                 if (t.item == FL_NONE) { t.v.label = "Nothing"; t.v.state = FS_EMPTY; } sc.tiles.push_back(t); }
        // (1.9.8: no "When" button any more - the front page's own buttons choose the screen, and the choice stays.
        // 1.9.9, Malcolm: "The three remaining buttons now look as if there's one just missing! I think they should be
        // evenly spaced and perhaps a little larger": three across the width, as the front screens' own row is.)
        const int bw = (FLIGHT_W - 12 - 2 * 19) / 3;
        auto third = [&](int i) { return FlightRect(6 + i * (bw + 19), SLOT_Y, bw, SLOT_H); };
        FlightButton bt; bt.id = ID_BOXES; bt.r = third(0); bt.text = "Box sizes"; sc.buttons.push_back(bt);
        bt.id = ID_STAY; bt.r = third(1); bt.text = cfg.stayOn ? "Stays lit: yes" : "Stays lit: no"; sc.buttons.push_back(bt);
        bt.id = ID_OK; bt.r = third(2); bt.text = "OK"; sc.buttons.push_back(bt);
    } else if (chooser == CHOOSE_SIZES) {                       // the box sizes: each choice drawn as its boxes
        sc.layout = 4000; sc.title = "Defined front screen"; sc.hint = "Choose the box sizes. Box 1 is the biggest.";
        const int cols = 4, gap = 10, x0 = 14, y0 = 92, w = (FLIGHT_W - 2 * x0 - (cols - 1) * gap) / cols, h = (312 - 2 * gap) / 3;
        for (int k = 0; k < FLIGHT_LAYOUT_COUNT; ++k) {
            FlightButton bt; bt.id = ID_LAYOUT + k; bt.r = FlightRect(x0 + (k % cols) * (w + gap), y0 + (k / cols) * (h + gap), w, h);
            bt.text = FLIGHT_LAYOUTS[k].name; bt.layout = (int8_t) k; bt.chosen = cfg.layout == k; sc.buttons.push_back(bt);
        }
        FlightButton bt; bt.id = ID_BACK; bt.r = FlightRect(x0 + (cols - 1) * (w + gap), SLOT_Y, FLIGHT_W - 15 - (x0 + (cols - 1) * (w + gap)), SLOT_H); bt.text = "OK"; sc.buttons.push_back(bt);   // (OK at the bottom right, as on every page: under the grid's last column, its right edge where it was, 785)
    } else if (chooser >= 0) {
        sc.layout = 3000 + chooser; sc.title = "Defined front screen";
        char b[48]; snprintf(b, sizeof(b), "Box %d shows:", chooser + 1); sc.hint = b;
        const int cols = 4, gap = 5, x0 = 14, y0 = 92, w = (FLIGHT_W - 2 * x0 - (cols - 1) * gap) / cols, h = 58;   // (five rows of four: 17 things)
        for (int it = 1; it <= FL_ITEMS; ++it) {                        // the things, then "Nothing" last
            const int item = it == FL_ITEMS ? FL_NONE : it, k = it - 1;
            FlightButton bt; bt.id = ID_ITEM + item; bt.r = FlightRect(x0 + (k % cols) * (w + gap), y0 + (k / cols) * (h + gap), w, h);
            bt.text = flightItemName(item); bt.chosen = cfg.items[chooser] == item;
            // (1.9.12, Malcolm: "it's easy to forget which ones have already been selected") another box already shows it: say which
            if (item != FL_NONE) for (int k = 0; k < cfg.boxes(); ++k) if (k != chooser && cfg.items[k] == item) { bt.usedBy = (uint8_t) (k + 1); break; }
            sc.buttons.push_back(bt);
        }
        // (the bottom row on the grid's first and last columns: x 14 and 596, 189 wide)
        FlightButton bt; bt.id = ID_BACK; bt.r = FlightRect(x0 + 3 * (w + gap), SLOT_Y, w, SLOT_H); bt.text = "OK"; sc.buttons.push_back(bt);   // (OK at the bottom right, as on every page)
        bt.id = ID_COLOUR; bt.r = FlightRect(x0, SLOT_Y, w, SLOT_H); bt.text = "Theme"; sc.buttons.push_back(bt);   // (its theme: a page of its own)
        if (flightItemCanDial(cfg.items[chooser])) {         // (1.11.102) a number: as a round dial, or as digits - the button says which it is now
            bt.id = ID_DIAL; bt.r = FlightRect(x0 + (w + gap), SLOT_Y, w, SLOT_H); bt.text = cfg.boxDial[chooser] ? "Round dial: yes" : "Round dial: no"; sc.buttons.push_back(bt);
        }
        if (flightItemTakesLimit(cfg.items[chooser])) {      // (1.11.105) a thing with no danger line of its own: the pilot's red zone, a page of its own (the third slot)
            bt.id = ID_ZONE; bt.r = FlightRect(x0 + 2 * (w + gap), SLOT_Y, w, SLOT_H);
            bt.text = cfg.boxZone[chooser] ? "Red zone: " + std::to_string((int) cfg.boxZone[chooser]) : "Red zone: none"; sc.buttons.push_back(bt);
        }
    }
    for (auto &b : sc.buttons) {
        b.pressed = b.id == pressedId && !slidOff && !b.label;
        b.serial = hashOf(b.text, 2166136261u) ^ ((b.chosen ? 1u : 0u) << 1) ^ (b.pressed ? 1u : 0u) ^ ((uint32_t) b.usedBy << 4) ^ hashOf(b.usedBoxes, 7u);
        if (b.swatch) b.serial = (b.serial ^ b.face) * 16777619u ^ b.ink;
    }
    flightSizeTiles(sc.tiles, fonts);
    for (auto &t : sc.tiles) {
        meter(t);                                                 // (1.11.102) a dial box: its dial
        uint32_t h = hashOf(t.v.label, 2166136261u); h = hashOf(t.v.big, h); h = hashOf(t.v.unit, h); h = hashOf(t.v.small, h); h = hashOf(t.v.image, h);
        if (t.dial) { h = (h ^ 0x5D1A1u ^ (uint32_t) t.meter.hi) * 16777619u; h = (h ^ (uint32_t) t.meter2.hi) * 16777619u;   // (a dial, and its scale as grown)
                      h = (h ^ (uint32_t) t.meter.redFrom ^ ((uint32_t) (t.meter2.lo * 100) << 16)) * 16777619u; }   // (1.11.105: its red zone, a LiFePO4 scale)
        if (t.v.twoPart) { h = hashOf(t.v.label2, h); h = hashOf(t.v.big2, h); h = hashOf(t.v.unit2, h); h = hashOf(t.v.small2, h); h = hashOf(t.v.tag, h); h = hashOf(t.v.tag2, h); h = (h ^ (uint32_t) t.v.state2) * 16777619u; }
        for (uint8_t b : t.v.bars) h = (h ^ b) * 16777619u;
        if (t.own) h = ((h ^ t.face) * 16777619u) ^ t.ink;
        t.serial = (h ^ ((uint32_t) t.v.state << 24) ^ ((uint32_t) t.item << 16) ^ ((uint32_t) t.colour << 8)) + (t.pressed ? 7u : 0u);
    }
}
const FlightScene &FlightScreen::scene(FlightSource &src, FlightFonts *fonts) { build(src, fonts); return sc; }

int FlightScreen::idAt(int x, int y) const {
    int id = -1;
    for (auto &b : sc.buttons) {
        if (b.label) continue;
        if (b.id >= ID_SLOT && b.id < ID_SLOT + FLIGHT_SLOTS) {   // a tab, near the top edge of the glass: it answers to a touch a little below its drawn edge too (1.10.7)
            FlightRect r = b.r; r.h = (int16_t) (r.h + 10); r.x = (int16_t) (r.x - 2); r.w = (int16_t) (r.w + 4);
            if (r.has(x, y)) id = b.id;
        } else if (b.r.has(x, y)) id = b.id;
    }
    if (setup && chooser == -1 && colourFor < 0 && zoneFor < 0) for (auto &t : sc.tiles) if (t.r.has(x, y)) id = t.id;
    return id;
}
void FlightScreen::touch(bool pressed, int x, int y, uint32_t now) {
    if (waitLift) {                                    // the long press's own finger, still down over the chooser that has just appeared: not a press on it
        if (pressed) lastSeen = now;
        else if ((int32_t) (now - lastSeen) > 80) waitLift = false;   // (really lifted: the next touch counts)
        return;
    }
    if (pressed) {
        lastSeen = now;
        const int id = idAt(x, y);                     // (the flight screen: its buttons only; a touch anywhere else does nothing)
        if (!down) { down = true; pressedId = id; slidOff = false; heldBox = -1; }
        else if (id != pressedId) slidOff = true;      // it has slid off: lifting it does nothing
        if (!setup && shown && !inFlight && id < 0 && !slidOff) {   // the flight screen on the ground, a finger on no button: on a box, held?
            int box = -1; for (auto &t : sc.tiles) if (t.r.has(x, y)) box = t.id;
            if (box != heldBox) { heldBox = box; heldSince = now; }
            else if (box >= 0 && now - heldSince >= LONG_PRESS_MS) {   // two seconds: that box's chooser, from here
                heldBox = -1; down = false; pressedId = -1;
                openSetup(); chooser = box; quickEdit = true; waitLift = true;   // (the finger is still down: nothing counts until it has lifted)
            }
        } else heldBox = -1;
        return;
    }
    if (!down || (int32_t) (now - lastSeen) <= 80) return;   // a sample the chip dropped mid-press, not a lift (the long press's clock runs on)
    const int tapped = heldBox; const bool quick = heldBox >= 0 && (int32_t) (now - heldSince) < (int32_t) TAP_MS;   // (1.11.97) a short press on a box
    heldBox = -1;                                              // a real lift: the long press, if any, starts again
    down = false;
    const int was = pressedId; const bool off = slidOff;
    pressedId = -1; slidOff = false;
    if (was < 0 || off) {
        if (!setup && shown && !inFlight && quick && !off) {   // (1.11.97) a second short tap on the same box, soon after the first: that box's chooser
            if (tapped == lastTapBox && (int32_t) (now - lastTapAt) <= (int32_t) DOUBLE_TAP_MS) { lastTapBox = -1; openSetup(); chooser = tapped; quickEdit = true; }
            else { lastTapBox = tapped; lastTapAt = now; }
        } else lastTapBox = -1;
        return;
    }
    lastTapBox = -1;
    if (!setup) {
        if (!shown) return;
        if (was == ID_ORIGINAL) { if (cfg.manual != FM_ORIGINAL) { cfg.manual = FM_ORIGINAL; saved = true; } shown = false; }   // the front page, until its "Defined screen" (or the next take-off or landing); kept across a switch-off
        else if (was == ID_TXSETUP) frontPress = "b0";                 // the front page's "Transmitter" button
        else if (was == ID_MODELSETUP) frontPress = "b1";              // and its "Model"
        else if (was == ID_HELP) frontPress = "help";                  // this screen's own help
        else if (was >= ID_SLOT && was < ID_SLOT + FLIGHT_SLOTS) chooseSlot(was - ID_SLOT);   // another of the six screens, now
        return;
    }
    releaseOn(was);
    if (quickEdit && setup && chooser == -1 && colourFor < 0) closeSetup();   // a long press's chooser, done (or its theme page): the flight screen again
}
FlightScreen::FlightScreen() {
    for (int i = 0; i < THEME_COUNT; ++i) { palPanels[i] = THEME_PAIRS[i].panel; palInks[i] = THEME_PAIRS[i].ink; }
}
void FlightScreen::paint(FlightTile &t, int box) const {   // its theme's two colours, else the screens' (drawn by the screen)
    if (box < 0 || box >= FLIGHT_MAX_BOXES) return;
    t.box = (int8_t) box;
    t.dial = cfg.boxDial[box] && flightItemCanDial(t.item);   // (1.11.102) a round dial, where its thing can be one
    const int f = cfg.boxTheme[box];
    t.colour = (uint8_t) f;
    if (!f || f > THEME_COUNT) return;
    t.own = true; t.face = palPanels[f - 1]; t.ink = palInks[f - 1];
}
// (1.11.102) A dial box's dial from its value. A gauge's scale grows to hold the biggest value its thing has shown since
// switch-on, and keeps that size: the needle of a scale that shrank back would swing while the pilot watched.
void FlightScreen::meter(FlightTile &t) {
    if (!t.dial || t.item <= 0 || t.item >= FL_ITEMS) { t.meter = FlightDial(); t.meter2 = FlightDial(); return; }
    float &high = dialHigh[t.item];
    if (t.v.hasNum) { const float top = flightDialTop(t.item, t.v.num); if (top > high) high = top; }
    if (t.v.hasNum2) { const float top = flightDialTop(t.item, t.v.num2); if (top > high) high = top; }
    const float limit = t.box >= 0 && t.box < FLIGHT_MAX_BOXES ? (float) cfg.boxZone[t.box] : 0;   // (1.11.105) the box's own red zone
    t.meter = flightDialOf(t.item, 0, t.v, high, limit);
    t.meter2 = t.v.twoPart ? flightDialOf(t.item, 1, t.v, high, limit) : FlightDial();
}
void FlightScreen::releaseOn(int id) {
    if (!setup) return;
    if (chooser == CHOOSE_SIZES) {
        if (id == ID_BACK) chooser = -1;
        else if (id >= ID_LAYOUT && id < ID_LAYOUT + FLIGHT_LAYOUT_COUNT) { cfg.layout = (uint8_t) (id - ID_LAYOUT); chooser = -1; }
        return;
    }
    if (zoneFor >= 0) {                                // (1.11.105) a box's red zone: kept at once; OK back to the setup page
        const int item = cfg.items[zoneFor]; int start, small, big, top; flightLimitSteps(item, start, small, big, top);
        int z = cfg.boxZone[zoneFor];
        if (id == ID_ZONE_DONE) { zoneFor = -1; return; }
        if (id == ID_ZONE_NONE) z = 0;
        else if (id == ID_ZONE_DOWN2 || id == ID_ZONE_DOWN || id == ID_ZONE_UP || id == ID_ZONE_UP2) {
            const int step = (id == ID_ZONE_DOWN2 || id == ID_ZONE_UP2) ? big : small, dir = (id == ID_ZONE_DOWN2 || id == ID_ZONE_DOWN) ? -1 : 1;
            if (!z) z = start; else { z += dir * step; z -= z % small; }   // (from none, either way: the starting value)
            if (z < small) z = 0; if (z > top) z = top;
        } else return;
        cfg.boxZone[zoneFor] = (uint16_t) z; return;
    }
    if (colourFor >= 0) {                              // a box's theme: kept at once (the screens' own theme: the box follows them)
        if (id >= ID_FACE && id < ID_FACE + THEME_COUNT) { const int k = id - ID_FACE; cfg.boxTheme[colourFor] = (uint8_t) (palPanels[k] == themeFace && palInks[k] == themeInk ? 0 : k + 1); }
        else if (id == ID_SAME) cfg.boxTheme[colourFor] = 0;
        else if (id == ID_COLOUR_DONE) colourFor = -1;  // (back to the setup page: the box in its theme)
        return;
    }
    if (chooser >= 0) {
        if (id == ID_BACK) chooser = -1;
        else if (id >= ID_ITEM && id < ID_ITEM + FL_ITEMS) { cfg.items[chooser] = (uint8_t) (id - ID_ITEM); chooser = -1; }
        else if (id == ID_COLOUR) { colourFor = chooser; chooser = -1; }   // its theme, on a page of its own
        else if (id == ID_DIAL && flightItemCanDial(cfg.items[chooser])) cfg.boxDial[chooser] = cfg.boxDial[chooser] ? 0 : 1;   // (1.11.102) a dial, or digits again: the page stays
        else if (id == ID_ZONE && flightItemTakesLimit(cfg.items[chooser])) { zoneFor = chooser; chooser = -1; }   // (1.11.105) its red zone, on a page of its own
        return;
    }
    if (id >= 0 && id < cfg.boxes()) { chooser = id; return; }       // (what the boxes beyond the layout's show is kept, for a bigger layout)
    if (id >= ID_SLOT && id < ID_SLOT + FLIGHT_SLOTS) { chooseSlot(id - ID_SLOT); return; }   // another definition, from now on
    if (id == ID_BOXES) chooser = CHOOSE_SIZES;
    else if (id == ID_STAY) cfg.stayOn = !cfg.stayOn;
    else if (id == ID_OK) closeSetup();
}

}  // namespace ldrc
