// ElrsCrsf.h - an ExpressLRS transmitter module INSIDE the transmitter, driven by CRSF (Malcolm, 11 Nov 2026: "My vote is
// for ELRS, internally, switchable, and by serial link so that we get a higher frame rate and telemetry ... maybe we can
// address this by soldering one wire to the Teensy?").
//
// THE WIRE. Teensy 4.1 pin 24 is Serial6's transmit pin, and on the main board its pad goes nowhere (the board's netlist,
// Circuits/Transmitter - CADCAM: T1-24 is on the "no connection" net). One wire from it, through a ~1 kOhm resistor (the
// Teensy's pins do not take 5 V), to the module's signal pin. A module bay's CRSF line is ONE wire used both ways, and the
// Teensy core does exactly that (SERIAL_HALF_DUPLEX: the receiver listens on the transmit pin between frames, and pin 25,
// Serial6's own receive pin, is left alone - it belongs to a switch). Ground, and the battery's 6.5-8.4 V, from the
// TX_MODULE header; that header's own signal pin (Teensy pin 6, the old PPM) is not touched.
//
// WHAT THE MODULE EXPECTS (read from ExpressLRS's source, src/lib/Handset/CRSFHandset.cpp, 11 Nov 2026): frames that start
// with 0xEE (its address) or 0xC8, a good CRC, and enough of them, or it looks for us at its next baud rate and polarity
// (400000 first, then 115200, 5250000, 3750000, 1870000, 921600, 2250000; inverted and not). Its own frames to us start
// with 0xC8. Every 200 ms it says its packet interval and how early or late our frames arrive (a 0x3A frame, subcommand
// 0x10, both in tenths of a microsecond).
//
// PHASE 1 = THE BENCH TEST, in TEST BUILDS ONLY (-DELRS_TEST, flashed to one transmitter; never in a release): the
// channels the LDRC link sends (SendBuffer, 500..2500 us) also go out as CRSF channel frames, at the module's own packet
// interval once it has said it; what the module sends back (its link statistics, the receiver's telemetry, its timing) is
// read and written to the log every 5 s. The LDRC link is untouched, so BOTH radios transmit: bench only, blades off.
// Phase 2 (a model setting, LDRC's radio quiet while ELRS flies, the module's power switched by pin 10, the telemetry in
// the usual front-screen boxes) comes after the bench test says the wire and the frames are right.
// THE BENCH SAID SO ON 12 NOV 2026 (the yellow transmitter, a Ranger Nano on ExpressLRS 3.6.4, Bthundr 1's Nexus-XR):
// 268,868 frames out and 38,611 back without one bad CRC, the sticks moving Rotorflight's Receiver page and the heli's
// telemetry coming back. It also showed what phase 1 did badly: see PHASE 2, STEP 1 below (the frames from a timer).
// PHASE 2, STEP 2 (13 Nov 2026, Malcolm: "Add to the model setup screen the option 'LDRC or ELRS receiver?' ... Do what's
// needed to the code so that when connected on ELRS we can get full telemetry"). Still TEST BUILDS ONLY. See THE MODEL'S
// OWN LINK below: a model set to ELRS on Model options flies on the module ALONE (LDRC's radio says nothing for it), its
// link counts as the transmitter's connection (the green light, "Connected", the log, the front page), and what the model
// sends back goes into the transmitter's usual telemetry boxes by the usual code.
// TO REMOVE IT (Malcolm, 11 Nov 2026: "In case of unexpected failure, please do the code in such a way that if necessary,
// it could be easily removed again!"): delete this file, dev/test_elrs, and every block marked ELRS in the other files
// (each inside #ifdef ELRS_TEST; where one has an #else, the #else's lines are the transmitter as it was: keep them).
// dev/test_elrs lists them all and fails if any ELRS line is found elsewhere. Nothing else in the transmitter knows of
// ELRS, and a release build does not contain it. A model saved as ELRS flies on LDRC under a firmware without this (the
// setting is one bit that such a firmware does not read, and drops at its next save). The Model options page keeps its
// switch hidden unless this code shows it.
#pragma once
#include <stdint.h>
#include <string.h>

// What of the block below is used only now and then (the module's own settings) is kept out of the fast memory that
// every pass of loop() runs from: on the Teensy such a function is kept whole (not folded into its caller) and in
// flash. (Found by review, 14 Nov 2026: RAM1's code had come within 1,880 bytes of taking another 32 kB of the stack's
// room.) Each gets a flash section of its own name: these are inline functions, which the compiler will not put beside
// ordinary ones in the one section FLASHMEM names ("section type conflict"); the Teensy's linker file takes every
// section whose name begins .flashmem. On the Mac, where the block is compiled by itself, the word means nothing.
#if defined(__IMXRT1062__)
#define ELRS_COLD(name) __attribute__((noinline, section(".flashmem.elrs_" #name)))
#endif
// ELRS-CRSF-BEGIN (dev/test_elrs/test_elrs.py compiles this block on the Mac)
#ifndef ELRS_COLD
#define ELRS_COLD(name)
#endif
namespace ElrsCrsf
{
constexpr uint8_t ADDR_MODULE = 0xEE;   // CRSF_ADDRESS_CRSF_TRANSMITTER: the module - where our channel frames go
constexpr uint8_t ADDR_HANDSET = 0xEA;  // CRSF_ADDRESS_RADIO_TRANSMITTER: us
constexpr uint8_t SYNC_BYTE = 0xC8;     // the module starts its frames to us with this (CRSFHandset.cpp: data[0] = CRSF_SYNC_BYTE)
constexpr uint8_t T_BATTERY = 0x08, T_RPM = 0x0C, T_TEMP = 0x0D, T_LINK_STATS = 0x14, T_RC = 0x16, T_ATTITUDE = 0x1E,
                  T_FLIGHT_MODE = 0x21, T_HANDSET = 0x3A;
constexpr uint8_t T_DEVICE_PING = 0x28, T_DEVICE_INFO = 0x29, T_CUSTOM = 0x88;   // "who is there?", its answer, and Rotorflight's own telemetry
constexpr uint8_t T_PARAM_ENTRY = 0x2B, T_PARAM_READ = 0x2C, T_PARAM_WRITE = 0x2D;   // a piece of one of the module's own settings, our asking for it, our changing it
constexpr uint8_t ADDR_FC = 0xC8, ADDR_RX = 0xEC, ADDR_BROADCAST = 0x00;         // the flight controller, the receiver, everyone
constexpr uint8_t SUB_TIMING = 0x10;    // CRSF_HANDSET_SUBCMD_TIMING
constexpr uint8_t RC_FRAME_LEN = 26;    // address, length 24, type, 22 bytes of channels, CRC
constexpr uint8_t MAX_FRAME = 64;       // a CRSF frame is at most 64 bytes, its length byte at most 62
constexpr uint32_t DEFAULT_PERIOD_US = 4000;  // 250 Hz until the module has told us its interval

// CRC-8/DVB-S2 (polynomial 0xD5), over the type and the payload - the same as the receiver's crsfCrc8 (RXV2 Output.h).
inline uint8_t crc8(const uint8_t *d, uint8_t n)
{
    uint8_t crc = 0;
    for (uint8_t i = 0; i < n; ++i)
    {
        crc ^= d[i];
        for (uint8_t b = 0; b < 8; ++b)
            crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0xD5) : (uint8_t)(crc << 1);
    }
    return crc;
}
// Microseconds to CRSF's 11-bit value: EXACTLY the receiver's rc11bit (RXV2 Output.h), so Rotorflight sees the same
// microseconds whichever link carried them: 1000 -> 173, 1500 -> 992, 2000 -> 1811, clamped to 172..1811.
inline uint16_t usToTicks(uint16_t us)
{
    long v = ((long)us - 1500) * 819L / 500L + 992L;
    if (v < 172) v = 172;
    if (v > 1811) v = 1811;
    return (uint16_t)v;
}
// The 16 channels as one CRSF channel frame to the module: 11 bits each, the lowest bits first.
inline void buildRcFrame(const uint16_t *us, uint8_t *out)
{
    out[0] = ADDR_MODULE;
    out[1] = 24;   // type + 22 + CRC
    out[2] = T_RC;
    uint32_t bits = 0;
    uint8_t nbits = 0, k = 3;
    for (uint8_t c = 0; c < 16; ++c)
    {
        bits |= ((uint32_t)usToTicks(us[c]) & 0x7FFu) << nbits;
        nbits += 11;
        while (nbits >= 8)
        {
            out[k++] = (uint8_t)(bits & 0xFFu);
            bits >>= 8;
            nbits -= 8;
        }
    }
    out[25] = crc8(&out[2], 23);
}

// ---- THE MODULE'S OWN SETTINGS: ITS LIST, READ THE WAY ITS HANDSET SCRIPT READS IT (14 Nov 2026) -----------------------
// Packet rate, telemetry ratio, switch mode, power: on other radios the module's Lua script sets these. They are the
// module's "parameters", numbered from 1, and its answer to "who is there?" says how many it has. (ExpressLRS 3.6.4:
// lib/LUA/lua.cpp sendCRSFparam, lib/LUA/tx_devLUA.cpp, lua/elrsV3.lua, CRSFHandset.cpp processInternalCrsfPackage.)
//   we ask       EE 06 2C EE EA [number][chunk] crc         "that chunk of that parameter, please"
//   it answers   EA len 2B EA EE [number][chunks still to come][data ...] crc
// The data of all of a parameter's chunks, end to end: [parent folder][kind; +0x80 = hidden][name]0, then by kind -
//   a choice (9):     [the choices, ';' between them]0 [value][min][max][default] [units]0    (an empty choice: not offered)
//   a number (0-3):   [value][min][max][default], a byte each or two, [units]0
//   a text (10, 12):  [the text]0
//   a folder (11):    [its parameters' numbers] FF
//   a command (13):   [step][its timeout, in 10 ms] [what it says]0
// A chunk carries what fits the module's frame (56 bytes at 250 packets a second: the packet rates' list comes in
// three). Its script waits half a second for an answer and then asks for the same chunk again; so does this.
// The list is read, and the log gets it (the first run with real telemetry, 14 Nov 2026, showed each value only every
// 5 s: the module's telemetry ratio is one of these settings, and its web page does not offer it). Changing one is the
// part after this (THE SETTINGS THE TRANSMITTER'S PAGE SHOWS).
constexpr uint8_t P_UINT8 = 0, P_INT8 = 1, P_UINT16 = 2, P_INT16 = 3, P_CHOICE = 9, P_STRING = 10, P_FOLDER = 11, P_INFO = 12, P_COMMAND = 13;
constexpr uint8_t PARAM_FRAME_LEN = 8;
constexpr uint8_t MAX_PARAMS = 64;          // the module's own limit (LUA_MAX_PARAMS)
constexpr uint32_t PARAM_ANSWER_MS = 500;
constexpr uint8_t PARAM_TRIES = 4;          // askings without an answer, in all, before a parameter is left and the next is read
ELRS_COLD(buildParamRead) inline void buildParamRead(uint8_t *out, uint8_t number, uint8_t chunk)
{
    out[0] = ADDR_MODULE;
    out[1] = 6;   // type, destination, origin, number, chunk, CRC
    out[2] = T_PARAM_READ;
    out[3] = ADDR_MODULE;
    out[4] = ADDR_HANDSET;
    out[5] = number;
    out[6] = chunk;
    out[7] = crc8(&out[2], 5);
}
struct Param
{
    uint8_t number = 0, parent = 0, kind = 0xFF;   // kind: P_...; 0xFF = nothing read
    bool hidden = false;
    bool cut = false;                       // something of it did not fit here, or its data ended early: not to be relied on
    uint16_t value = 0, min = 0, max = 0;   // a choice's are positions in its list; a command's value is its step
    char name[32] = {0};
    char text[200] = {0};                   // a choice's choices; a text's text; what a command says
    char units[20] = {0};
};
// A string out of a parameter's data, from k: what can be printed, up to its 0. Returns where the next thing begins.
ELRS_COLD(paramText) inline uint16_t paramText(const uint8_t *d, uint16_t n, uint16_t k, char *dst, uint16_t room, bool &cut)
{
    uint16_t w = 0;
    while (k < n && d[k])
    {
        if (w + 1 < room) dst[w++] = (d[k] >= 0x20 && d[k] <= 0x7E) ? (char)d[k] : '?';
        else cut = true;
        ++k;
    }
    dst[w] = 0;
    if (k >= n) cut = true;   // no 0: the data ended inside the string
    return (uint16_t)(k + 1);
}
ELRS_COLD(paramParse) inline void paramParse(const uint8_t *d, uint16_t n, Param &o)
{
    const uint8_t number = o.number;
    o = Param();
    o.number = number;
    if (n < 3) { o.cut = true; return; }
    o.parent = d[0];
    o.kind = (uint8_t)(d[1] & 0x7F);
    o.hidden = (d[1] & 0x80) != 0;
    const uint16_t k = paramText(d, n, 2, o.name, sizeof(o.name), o.cut);
    switch (o.kind)
    {
    case P_CHOICE:
    {
        const uint16_t v = paramText(d, n, k, o.text, sizeof(o.text), o.cut);
        if ((uint32_t)v + 4 > n) { o.cut = true; return; }
        o.value = d[v]; o.min = d[v + 1]; o.max = d[v + 2];
        paramText(d, n, (uint16_t)(v + 4), o.units, sizeof(o.units), o.cut);
        break;
    }
    case P_UINT8:
    case P_INT8:
        if ((uint32_t)k + 4 > n) { o.cut = true; return; }
        o.value = d[k]; o.min = d[k + 1]; o.max = d[k + 2];
        paramText(d, n, (uint16_t)(k + 4), o.units, sizeof(o.units), o.cut);
        break;
    case P_UINT16:
    case P_INT16:
        if ((uint32_t)k + 8 > n) { o.cut = true; return; }
        o.value = (uint16_t)((d[k] << 8) | d[k + 1]); o.min = (uint16_t)((d[k + 2] << 8) | d[k + 3]); o.max = (uint16_t)((d[k + 4] << 8) | d[k + 5]);
        paramText(d, n, (uint16_t)(k + 8), o.units, sizeof(o.units), o.cut);
        break;
    case P_STRING:
    case P_INFO:
        paramText(d, n, k, o.text, sizeof(o.text), o.cut);
        break;
    case P_COMMAND:
        if ((uint32_t)k + 2 > n) { o.cut = true; return; }
        o.value = d[k]; o.min = d[k + 1];
        paramText(d, n, (uint16_t)(k + 2), o.text, sizeof(o.text), o.cut);
        break;
    case P_FOLDER:
        break;   // (the numbers of what is in it follow, to FF: each of those names this folder as its parent, which is enough)
    default:
        break;   // a kind not known here: its name is enough
    }
}
// The reading of the whole list, one parameter after another, one chunk after another.
struct ParamReader
{
    uint8_t count = 0;          // how many the module has; 0: not known, or none
    uint8_t number = 0;         // the one being read (1..count); 0: none
    uint8_t chunk = 0;          // the chunk asked for
    uint8_t remainWanted = 0;   // (chunk > 0) how many chunks the awaited one must say are still to come
    uint8_t tries = 0, failed = 0;
    bool waiting = false;       // a request is out and its answer has not come
    bool done = false;          // every one has been read, or left
    bool ready = false;         // `one` is a whole parameter: the caller takes it and clears this (nothing more is asked meanwhile)
    uint32_t askedMs = 0;
    uint16_t len = 0;
    uint32_t asked = 0, chunks = 0, stray = 0;   // requests sent, chunks taken, chunks that were not the one awaited
    uint8_t data[256];          // (the module's own buffer for one parameter is 256 bytes)
    Param one;

    ELRS_COLD(readerStart) void start(uint8_t howMany)
    {
        count = howMany > MAX_PARAMS ? MAX_PARAMS : howMany;
        number = count ? 1 : 0;
        chunk = remainWanted = tries = failed = 0;
        waiting = ready = false;
        done = !count;
        len = 0;
        asked = chunks = stray = 0;
    }
    void toNext()
    {
        chunk = 0;
        len = 0;
        tries = 0;
        waiting = false;
        if (number >= count) { number = 0; done = true; }
        else ++number;
    }
    // The request to send now (PARAM_FRAME_LEN bytes into out), or 0: none is due.
    ELRS_COLD(readerNext) uint8_t next(uint32_t nowMs, uint8_t *out)
    {
        if (!number || done || ready) return 0;
        if (waiting)
        {
            if ((uint32_t)(nowMs - askedMs) < PARAM_ANSWER_MS) return 0;
            // No answer: THE SAME PIECE is asked for again, as the module's own script does (elrsV3.lua) - never the
            // parameter from its beginning: an answer still on its way would then be taken for its first piece, and a
            // wrong setting read without a mark (found by review, 14 Nov 2026). After PARAM_TRIES askings in all, the
            // parameter is left and the next is read; an answer of its that comes late then has the wrong number.
            waiting = false;
            if (++tries >= PARAM_TRIES)
            {
                ++failed;
                toNext();
                if (done) return 0;
            }
        }
        buildParamRead(out, number, chunk);
        waiting = true;
        askedMs = nowMs;
        ++asked;
        return PARAM_FRAME_LEN;
    }
    // The request just made never went out (the caller took it back): it is asked again, and was no try.
    void notSent() { waiting = false; }
    // The request went out only now (it lay in the timer's place a while): its half second runs from here.
    void sentAt(uint32_t nowMs) { if (waiting) askedMs = nowMs; }
    // A chunk from the module: [number][chunks still to come][data ...]
    ELRS_COLD(readerChunkIn) void chunkIn(const uint8_t *p, uint8_t n)
    {
        if (n < 2 || !waiting || p[0] != number || (chunk > 0 && p[1] != remainWanted)) { ++stray; return; }
        bool over = false;
        for (uint8_t i = 2; i < n; ++i)
        {
            if (len < sizeof(data)) data[len++] = p[i];
            else over = true;
        }
        ++chunks;
        waiting = false;
        if (p[1] && !over && chunk < 250)
        {   // more of it to come: the next chunk is asked for at once
            ++chunk;
            remainWanted = (uint8_t)(p[1] - 1);
            return;
        }
        one.number = number;
        paramParse(data, len, one);
        if (over || p[1]) one.cut = true;
        ready = true;
        toNext();
    }
};

// ---- THE SETTINGS THE TRANSMITTER'S PAGE SHOWS, AND CHANGING ONE (14 Nov 2026, the second step) ------------------------
// Of the module's list the page takes four, BY THEIR NAMES (a setting's number differs from module to module and from
// one ExpressLRS to the next): how often the sticks are sent, how much of the air time is the model's replies, how the
// channels after the fourth are carried, and the most power. Each is a choice: its list has ';' between the choices,
// and an EMPTY one is a choice this module does not offer just now (a packet rate our line is too slow for) - its
// place still counts, because what is written to the module is the place.
//   we write    EE 06 2D EE EA [number][the choice's place] crc
// The module answers nothing to that. It takes the change or it does not (tx_devLUA.cpp: the switch mode only while NO
// model is connected; a packet rate at any time, unless it would change the switch mode's NUMBER) and says the new
// value only once it has told the receiver and saved it, so the setting is READ AGAIN afterwards - more than once if
// need be - and what the module then says is what the page shows.
// THE SWITCH MODE'S NUMBER MEANS ANOTHER MODE AT ANOTHER KIND OF PACKET RATE: 0 is "Wide" or "8ch", 1 is "Hybrid" or
// "16ch Rate/2" (the second of each at the "Full" rates). So a change of packet rate can change the switch mode without
// a word - and with it whether channel 5 is carried whole (carriesChannel5 below).
constexpr uint8_t SET_RATE = 0, SET_TELEM = 1, SET_SWITCH = 2, SET_POWER = 3, SET_COUNT = 4;
inline const char *setName(uint8_t k)
{
    static const char *const names[SET_COUNT] = {"Packet Rate", "Telem Ratio", "Switch Mode", "Max Power"};
    return k < SET_COUNT ? names[k] : "";
}
struct Setting
{
    bool known = false;      // the module has said it (in this reading of its list)
    bool cut = false;        // ... but not all of it fitted here: shown, never changed
    uint8_t number = 0;      // its number in this module's list
    uint8_t value = 0, max = 0;
    char options[200] = {0};
    char units[20] = {0};
};
ELRS_COLD(buildParamWrite) inline void buildParamWrite(uint8_t *out, uint8_t number, uint8_t value)
{
    out[0] = ADDR_MODULE;
    out[1] = 6;   // type, destination, origin, number, value, CRC
    out[2] = T_PARAM_WRITE;
    out[3] = ADDR_MODULE;
    out[4] = ADDR_HANDSET;
    out[5] = number;
    out[6] = value;
    out[7] = crc8(&out[2], 5);
}
// The choice at a place of a list, without the receiver sensitivity ExpressLRS adds to a packet rate ("250Hz(-108dBm)"
// is shown as "250Hz"). False: no such place, or the choice there is empty (not offered).
ELRS_COLD(optionText) inline bool optionText(const char *list, uint8_t place, char *dst, uint8_t room)
{
    const char *p = list;
    for (uint8_t k = 0; k < place; ++k)
    {
        while (*p && *p != ';') ++p;
        if (!*p) { dst[0] = 0; return false; }
        ++p;
    }
    uint8_t w = 0;
    const char *q = p;
    while (*q && *q != ';') ++q;                     // q: the choice's end
    const char *e = q;
    if (e - p > 5 && e[-1] == ')' && e[-2] == 'm' && e[-3] == 'B' && e[-4] == 'd')
    {   // "...(-108dBm)": cut at its bracket
        const char *b = e - 5;
        while (b > p && *b != '(') --b;
        if (*b == '(' && b > p) e = b;
    }
    while (p < e) { if (w + 1 < room) dst[w++] = *p; ++p; }
    dst[w] = 0;
    return w > 0;
}
// The k-th choice that IS offered: its place in the list (255: there are not so many).
ELRS_COLD(offeredPlace) inline uint8_t offeredPlace(const char *list, uint8_t k)
{
    uint8_t place = 0, seen = 0;
    const char *p = list;
    for (;;)
    {
        if (*p && *p != ';')
        {
            if (seen == k) return place;
            ++seen;
        }
        while (*p && *p != ';') ++p;
        if (!*p || place == 254) return 255;
        ++p;
        ++place;
    }
}
// ... and the other way: the place's rank among the offered ones (255: that place is not offered, or is not there).
ELRS_COLD(offeredRank) inline uint8_t offeredRank(const char *list, uint8_t place)
{
    for (uint8_t k = 0; k < 255; ++k)
    {
        const uint8_t at = offeredPlace(list, k);
        if (at == place) return at == 255 ? 255 : k;
        if (at == 255 || at > place) return 255;
    }
    return 255;
}
// A parameter just read: if it is one of the four, kept (true).
ELRS_COLD(keepSetting) inline bool keepSetting(const Param &p, Setting *set)
{
    if (p.kind != P_CHOICE) return false;
    for (uint8_t k = 0; k < SET_COUNT; ++k)
    {
        if (strcmp(p.name, setName(k)) != 0) continue;
        Setting &s = set[k];
        s.known = true;
        s.cut = p.cut;
        s.number = p.number;
        s.value = (uint8_t)(p.value > 255 ? 255 : p.value);
        s.max = (uint8_t)(p.max > 255 ? 255 : p.max);
        uint8_t i = 0;
        for (; p.text[i] && (size_t)i + 1 < sizeof(s.options); ++i) s.options[i] = p.text[i];
        s.options[i] = 0;
        for (i = 0; p.units[i] && (size_t)i + 1 < sizeof(s.units); ++i) s.units[i] = p.units[i];
        s.units[i] = 0;
        return true;
    }
    return false;
}
// What a setting is now, as words for the page: its choice and the module's own unit ("Std (1:64)", "50 mW"); "" when
// the module has not said it.
ELRS_COLD(settingWords) inline void settingWords(const Setting &s, char *dst, uint8_t room)
{
    dst[0] = 0;
    if (!s.known || room < 2) return;
    char o[40];
    if (!optionText(s.options, s.value, o, sizeof(o))) { o[0] = '?'; o[1] = 0; }
    uint8_t w = 0;
    for (uint8_t i = 0; o[i] && w + 1 < room; ++i) dst[w++] = o[i];
    uint8_t u = 0;
    while (s.units[u] == ' ') ++u;                   // the module's unit, one space before it, none after
    uint8_t ue = (uint8_t)strlen(s.units);
    while (ue > u && s.units[ue - 1] == ' ') --ue;
    if (ue > u)
    {
        if (w + 1 < room) dst[w++] = ' ';
        for (; u < ue && w + 1 < room; ++u) dst[w++] = s.units[u];
    }
    dst[w] = 0;
}
// Is this a change the page asks for only while no model is connected? The switch mode (the module itself refuses it
// otherwise) and the packet rate (the module would take most of them - and the switch mode's meaning with them: not
// behind a connected model's back).
inline bool needsNoModel(uint8_t k) { return k == SET_RATE || k == SET_SWITCH; }
// The choices of a setting that the PAGE puts on its wheel: those the module offers, less two of the telemetry ratio's -
// "Off" (the transmitter knows a model is there only by its replies: with none it could never be connected - found by
// review, 14 Nov 2026) and "Race" (replies only while disarmed, and ExpressLRS takes channel 5 high - an LDRC model's
// throttle - for "armed": no telemetry with the motor running).
ELRS_COLD(pageOffers) inline bool pageOffers(uint8_t k, const char *list, uint8_t place)
{
    char o[40];
    if (!optionText(list, place, o, sizeof(o))) return false;
    if (k == SET_TELEM && (!strcmp(o, "Off") || !strcmp(o, "Race"))) return false;
    return true;
}
// The wheel's rank -> the place in the module's list (255: there are not so many on the wheel) ...
ELRS_COLD(pagePlace) inline uint8_t pagePlace(uint8_t k, const char *list, uint8_t rank)
{
    uint8_t seen = 0;
    for (uint8_t r = 0; r < 255; ++r)
    {
        const uint8_t place = offeredPlace(list, r);
        if (place == 255) return 255;
        if (!pageOffers(k, list, place)) continue;
        if (seen == rank) return place;
        ++seen;
    }
    return 255;
}
// ... and a place's rank on the wheel (255: it is not on the wheel).
ELRS_COLD(pageRank) inline uint8_t pageRank(uint8_t k, const char *list, uint8_t place)
{
    for (uint8_t rank = 0; rank < 255; ++rank)
    {
        const uint8_t at = pagePlace(k, list, rank);
        if (at == 255 || at > place) return 255;
        if (at == place) return rank;
    }
    return 255;
}
// DOES THIS SWITCH MODE CARRY CHANNEL 5 WHOLE? Only "16ch Rate/2" does (ExpressLRS 3.6.4 OTA.cpp, GenerateChannelData8ch12ch
// and UnpackChannelData8ch: every channel at 10 bits, half of them in each packet). In "Wide", "Hybrid", "8ch" and "12ch
// Mixed" channel 5 is ONE BIT - off or on: it is ExpressLRS's arming channel. An LDRC model's THROTTLE is channel 5.
// False too when the module has not said its switch mode (or not all of it).
ELRS_COLD(carriesChannel5) inline bool carriesChannel5(const Setting &sw)
{
    char o[40];
    return sw.known && !sw.cut && optionText(sw.options, sw.value, o, sizeof(o)) && !strcmp(o, "16ch Rate/2");
}
// THE THROTTLE HELD, as a rule (the driver's ElrsHeld). What the module LAST SAID of its switch mode is one of three
// things, and "it has not said" is not "it carries channel 5": a model whose throttle is channel 5 has its throttle held
// at motor-off until the module has said the one mode that carries it whole. (Review, 14 Nov 2026: held only when the
// mode was known to be wrong, the first seconds of every link - the list not read yet - and every reading-back of the
// list - "known" cleared for a moment - were unheld: on "Hybrid" that is full throttle above half stick.)
constexpr uint8_t CH5_UNKNOWN = 0, CH5_CARRIED = 1, CH5_ONE_BIT = 2;
// A reading of "Switch Mode": what it says. A setting not read just now (the list is being read again), or not read
// whole, says nothing new: what was known stays.
inline uint8_t channel5Said(const Setting &sw, uint8_t was)
{
    if (!sw.known || sw.cut) return was;
    return carriesChannel5(sw) ? CH5_CARRIED : CH5_ONE_BIT;
}
inline bool throttleHeld(bool throttleIsChannel5, uint8_t ch5) { return throttleIsChannel5 && ch5 != CH5_CARRIED; }

// What the module tells us. Each part has the millis() it last came (0 = never).
struct Telemetry
{
    // link statistics (0x14): the receiver's view of us (up) and ours of it (down)
    int16_t upRssi1 = 0, upRssi2 = 0;   // dBm (negative)
    uint8_t upLq = 0;                   // % of packets the receiver got
    int8_t upSnr = 0;
    uint8_t antenna = 0, rfMode = 0, txPower = 0;   // txPower: CRSF's enum (0 0 mW, 1 10, 2 25, 3 100, 4 500, 5 1000, 6 2000, 7 250, 8 50 mW)
    int16_t downRssi = 0;
    uint8_t downLq = 0;
    int8_t downSnr = 0;
    uint32_t linkMs = 0;
    // the model's battery (0x08), from the flight controller or the receiver
    uint16_t battDeciVolts = 0, battDeciAmps = 0;
    uint32_t battMah = 0;
    uint8_t battPct = 0;
    uint32_t battMs = 0;
    // head speed (0x0C, the first value; Rotorflight's is already the head's) and the first temperature (0x0D)
    int32_t rpm = 0;
    uint32_t rpmMs = 0;
    int16_t tempDeciC = 0;
    uint32_t tempMs = 0;
    // attitude (0x1E, CRSF's units) and the flight mode (0x21)
    int16_t pitch = 0, roll = 0, yaw = 0;
    char flightMode[16] = {0};
    // the module's timing (0x3A / 0x10), tenths of a microsecond
    int32_t intervalTenthsUs = 0, offsetTenthsUs = 0;
    uint32_t timingMs = 0;
    uint32_t timingFrames = 0;   // how many have come: 5 a second when our frames are in step, one more for every packet it had to send without us
    // counts
    uint32_t framesOk = 0, badCrc = 0, badLength = 0, unknownType = 0;
    uint32_t ownEcho = 0;   // our own frames heard on the one wire (see Parser): never counted as the module's
    // ---- PHASE 2, STEP 2: the model's telemetry in ONE set of units, whichever frame brought it (the standard frames
    // above, or Rotorflight's own 0x88), and which of them have come since loop() last took them (the F_ bits)
    uint32_t fresh = 0;
    uint16_t voltsCenti = 0, ampsCenti = 0;   // the flight pack: hundredths of a volt, hundredths of an amp
    uint32_t mah = 0;                         // milliamp-hours used
    uint8_t pct = 0, cells = 0;
    int32_t headRpm = 0, tailRpm = 0;
    int16_t escTempDeciC = 0, mcuTempDeciC = 0;   // tenths of a degree
    // who is there (0x29, the answers to our "who is there?")
    char fcName[24] = {0}, rxName[24] = {0}, moduleName[24] = {0};
    bool rotorflight = false;                 // the flight controller is Rotorflight: it said so by name, or sent its own 0x88 frames
    uint8_t rfMajor = 0, rfMinor = 0;         // its version as it said it ("Rotorflight 4.6.0": 4 and 6); 0 = not said
    // Rotorflight's own telemetry
    uint8_t govState = 255, armFlags = 255, pidProfile = 0, ratesProfile = 0;   // (255 = never said)
    uint32_t armDisable = 0;
    uint32_t customFrames = 0, customSensors = 0, customUnknown = 0;   // frames, values read, frames cut short by an id not in its table
    // how many of each kind have come (the log says, so the bench can see what a flight controller really sends)
    uint32_t nBattery = 0, nRpm = 0, nTemp = 0, nMode = 0, nAttitude = 0, nInfo = 0;
    // the module's own settings: how many it says it has (its answer to "who is there?"), and the reading of them
    uint8_t moduleParams = 0;
    uint32_t nModuleInfo = 0;
    ParamReader params;
};
constexpr uint32_t F_VOLTS = 1, F_AMPS = 2, F_MAH = 4, F_RPM = 8, F_ESC_TEMP = 16, F_KIND = 32;   // Telemetry::fresh

// A link-statistics RSSI byte as dBm. CRSF's own word is "dBm times -1" (45 = -45 dBm), but ExpressLRS sends the dBm
// itself as a signed byte (-50 dBm = 206: seen on the yellow transmitter's first link, 12 Nov 2026, which this code then
// logged as "-206 dBm"; its tx_main.cpp LinkStatsFromOta says "OpenTX's value is signed"). Read either way round: no
// radio hears +128 dBm, so a byte over 127 can only be the signed form.
inline int16_t rssiDbm(uint8_t b) { return (b > 127) ? (int16_t)((int16_t)b - 256) : (int16_t)(-(int16_t)b); }
inline int32_t be32(const uint8_t *p) { return (int32_t)(((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3]); }
inline uint16_t be16(const uint8_t *p) { return (uint16_t)(((uint16_t)p[0] << 8) | p[1]); }
inline int32_t s24(const uint8_t *p)
{
    int32_t r = ((int32_t)p[0] << 16) | ((int32_t)p[1] << 8) | p[2];
    if (r & 0x800000) r |= ~0xFFFFFF;
    return r;
}

// ---- ROTORFLIGHT'S OWN TELEMETRY (frame 0x88, when its "ELRS custom telemetry" is on): [destination][origin][frame
// number], then one value after another, each [its id, 2 bytes][the value]. The values have no length of their own, so a
// frame can be read only with Rotorflight's table of them - copied here from the firmware that sends it (rotorflight-
// firmware 4.6.0 = Rotorflight 2.3, src/main/telemetry/crsf.c, crsfCustomTelemetrySensors; dev/test_elrs holds the same
// table as that file has it, and tries every entry). How many bytes follow the id; -1 = an id not in the table (a newer
// Rotorflight's): the rest of that frame cannot be read, and is left.
ELRS_COLD(customWidth) inline int customWidth(uint16_t id, const uint8_t *d, uint8_t left)
{
    switch (id)
    {
    case 0x1000: return 0;                                              // nothing
    case 0x1001: return 2;                                              // heartbeat
    case 0x1011: case 0x1012: case 0x1013: return 2;                    // battery volts, amps, mAh
    case 0x1014: return 1;                                              // battery charge, %
    case 0x1020: case 0x1021: return 1;                                 // cell count, a cell's volts
    case 0x102F: return (left && d[0] <= 16) ? 1 + d[0] : -1;           // every cell: a count, then one byte each
    case 0x1030: return 6;                                              // the four controls, packed
    case 0x1031: case 0x1032: case 0x1033: case 0x1034: return 2;       // pitch, roll, yaw, collective
    case 0x1035: return 1;                                              // throttle
    case 0x1041: case 0x1042: case 0x1043: return 2;                    // ESC 1: volts, amps, mAh
    case 0x1044: return 3;                                              // ... its eRPM
    case 0x1045: case 0x1046: return 2;                                 // ... power, throttle
    case 0x1047: case 0x1048: return 1;                                 // ... its two temperatures
    case 0x1049: case 0x104A: return 2;                                 // ... its BEC's volts and amps
    case 0x104E: return 4;                                              // ... status
    case 0x104F: return 1;                                              // ... model
    case 0x1051: case 0x1052: case 0x1053: return 2;                    // ESC 2
    case 0x1054: return 3;
    case 0x1057: case 0x105F: return 1;
    case 0x1080: case 0x1081: case 0x1082: case 0x1083: return 2;       // ESC, BEC, bus, processor volts
    case 0x1090: case 0x1091: case 0x1092: case 0x1093: return 2;       // ... and amps
    case 0x10A0: case 0x10A1: case 0x10A3: return 1;                    // ESC, BEC, processor temperature
    case 0x10B1: return 2;                                              // heading
    case 0x10B2: return 3;                                              // altitude
    case 0x10B3: return 2;                                              // climb
    case 0x10C0: case 0x10C1: return 2;                                 // head speed, tail speed
    case 0x1100: return 6;                                              // attitude, all three
    case 0x1101: case 0x1102: case 0x1103: return 2;
    case 0x1110: return 6;                                              // acceleration, all three
    case 0x1111: case 0x1112: case 0x1113: return 2;
    case 0x1121: case 0x1122: case 0x1123: case 0x1124: return 1;       // GPS: satellites, the three DOPs
    case 0x1125: return 8;                                              // ... where
    case 0x1126: case 0x1127: case 0x1128: case 0x1129: case 0x112A: return 2;
    case 0x1141: case 0x1142: case 0x1143: return 1;                    // the three loads
    case 0x1200: return 1;                                              // model id
    case 0x1201: return 2;                                              // flight mode
    case 0x1202: return 1;                                              // arming flags
    case 0x1203: return 4;                                              // why it will not arm
    case 0x1204: case 0x1205: return 1;                                 // rescue state, governor state
    case 0x1211: case 0x1212: case 0x1213: case 0x1214: return 1;       // PID, rates, LED, battery profile
    case 0x1220: return 6;                                              // the adjustment in hand
    default: return (id >= 0xDB00 && id <= 0xDB07) ? 4 : -1;            // its eight debug values
    }
}
// One of its values, into the common set (d = the bytes after the id; their number is customWidth's).
ELRS_COLD(customTake) inline void customTake(uint16_t id, const uint8_t *d, Telemetry &t, uint32_t nowMs)
{
    switch (id)
    {
    case 0x1011: t.voltsCenti = be16(d); t.fresh |= F_VOLTS; t.battMs = nowMs ? nowMs : 1; break;   // Rotorflight's own unit: 0.01 V
    case 0x1012: t.ampsCenti = be16(d); t.fresh |= F_AMPS; break;                                     // 0.01 A
    case 0x1013: t.mah = be16(d); t.fresh |= F_MAH; break;
    case 0x1014: t.pct = d[0]; break;
    case 0x1020: t.cells = d[0]; break;
    case 0x1047:                                                                                      // (ESC 1's own, where the combined one is not asked for)
    case 0x10A0: t.escTempDeciC = (int16_t)(d[0] * 10); t.fresh |= F_ESC_TEMP; t.tempMs = nowMs ? nowMs : 1; break;   // whole degrees
    case 0x10A3: t.mcuTempDeciC = (int16_t)(d[0] * 10); break;
    case 0x10C0: t.headRpm = be16(d); t.rpm = t.headRpm; t.fresh |= F_RPM; t.rpmMs = nowMs ? nowMs : 1; break;
    case 0x10C1: t.tailRpm = be16(d); break;
    case 0x1202: t.armFlags = d[0]; break;
    case 0x1203: t.armDisable = (uint32_t)be32(d); break;
    case 0x1205: t.govState = d[0]; break;
    case 0x1211: t.pidProfile = d[0]; break;
    case 0x1212: t.ratesProfile = d[0]; break;
    default: break;                                                                                   // read past, not used
    }
}
// A name out of a frame: what can be printed, up to its 0, the frame's end, or the room.
ELRS_COLD(takeName) inline void takeName(const uint8_t *p, uint8_t n, char *dst, uint8_t room)
{
    uint8_t k = 0;
    while (k < n && k + 1 < room && p[k]) { dst[k] = (p[k] >= 0x20 && p[k] <= 0x7E) ? (char)p[k] : '?'; ++k; }
    dst[k] = 0;
}
// "Rotorflight 4.6.0": is it, and its first two numbers (0 0 where it gives none).
ELRS_COLD(rotorflightName) inline bool rotorflightName(const char *s, uint8_t &major, uint8_t &minor)
{
    major = minor = 0;
    if (strncmp(s, "Rotorflight", 11) != 0) return false;
    const char *q = s + 11;
    while (*q == ' ') ++q;
    unsigned a = 0, b = 0;
    bool any = false;
    while (*q >= '0' && *q <= '9' && a < 100) { a = a * 10 + (unsigned)(*q - '0'); ++q; any = true; }
    if (!any || *q != '.') return true;
    ++q;
    any = false;
    while (*q >= '0' && *q <= '9' && b < 100) { b = b * 10 + (unsigned)(*q - '0'); ++q; any = true; }
    if (any && a < 100 && b < 100) { major = (uint8_t)a; minor = (uint8_t)b; }
    return true;
}

// One whole, checked frame: type and payload (n = the payload's length).
inline void decode(uint8_t type, const uint8_t *p, uint8_t n, Telemetry &t, uint32_t nowMs)
{
    switch (type)
    {
    case T_LINK_STATS:
        if (n < 10) return;
        t.upRssi1 = rssiDbm(p[0]);
        t.upRssi2 = rssiDbm(p[1]);
        t.upLq = p[2];
        t.upSnr = (int8_t)p[3];
        t.antenna = p[4];
        t.rfMode = p[5];
        t.txPower = p[6];
        t.downRssi = rssiDbm(p[7]);
        t.downLq = p[8];
        t.downSnr = (int8_t)p[9];
        t.linkMs = nowMs ? nowMs : 1;
        break;
    case T_BATTERY:
        if (n < 8) return;
        t.battDeciVolts = be16(p);
        t.battDeciAmps = be16(p + 2);
        t.battMah = ((uint32_t)p[4] << 16) | ((uint32_t)p[5] << 8) | p[6];
        t.battPct = p[7];
        t.battMs = nowMs ? nowMs : 1;
        t.voltsCenti = (uint16_t)(t.battDeciVolts > 6553 ? 65530 : t.battDeciVolts * 10);   // (the frame's unit is 0.1 V and 0.1 A)
        t.ampsCenti = (uint16_t)(t.battDeciAmps > 6553 ? 65530 : t.battDeciAmps * 10);
        t.mah = t.battMah;
        t.pct = t.battPct;
        t.fresh |= F_VOLTS | F_AMPS | F_MAH;
        ++t.nBattery;
        break;
    case T_RPM: // [source][int24 BE] x N: the first is the head's (Rotorflight sends the head's, then the tail's)
        if (n < 4) return;
        t.rpm = t.headRpm = s24(p + 1);
        if (n >= 7) t.tailRpm = s24(p + 4);
        t.rpmMs = nowMs ? nowMs : 1;
        t.fresh |= F_RPM;
        ++t.nRpm;
        break;
    case T_TEMP: // [source][int16 BE, tenths of a degree] x N. One value is "the" temperature; two are Rotorflight's: its
                 // processor's, then the speed controller's (crsfFrameTemp in its crsf.c)
        if (n < 3) return;
        t.tempDeciC = (int16_t)be16(p + 1);
        if (n >= 5) { t.mcuTempDeciC = t.tempDeciC; t.escTempDeciC = (int16_t)be16(p + 3); }
        else t.escTempDeciC = t.tempDeciC;
        t.tempMs = nowMs ? nowMs : 1;
        t.fresh |= F_ESC_TEMP;
        ++t.nTemp;
        break;
    case T_ATTITUDE:
        if (n < 6) return;
        t.pitch = (int16_t)be16(p);
        t.roll = (int16_t)be16(p + 2);
        t.yaw = (int16_t)be16(p + 4);
        ++t.nAttitude;
        break;
    case T_FLIGHT_MODE:
    {
        uint8_t k = 0;
        while (k < n && k < sizeof(t.flightMode) - 1 && p[k]) { t.flightMode[k] = (p[k] >= 0x20 && p[k] <= 0x7E) ? (char)p[k] : '?'; ++k; }
        t.flightMode[k] = 0;
        ++t.nMode;
        break;
    }
    case T_CUSTOM: // Rotorflight's own telemetry (see customWidth above)
    {
        if (n < 3 || p[1] != ADDR_FC) return;
        ++t.customFrames;
        uint8_t k = 3;
        while (k + 2 <= n)
        {
            const uint16_t id = be16(p + k);
            k = (uint8_t)(k + 2);
            const int w = customWidth(id, p + k, (uint8_t)(n - k));
            if (w < 0 || k + w > n) { ++t.customUnknown; break; }   // (what came before it in the frame has been taken)
            customTake(id, p + k, t, nowMs);
            k = (uint8_t)(k + w);
            ++t.customSensors;
            if (!t.rotorflight) { t.rotorflight = true; t.fresh |= F_KIND; }   // only Rotorflight sends these
        }
        break;
    }
    case T_DEVICE_INFO: // the answer to "who is there?": [destination][origin][its name, ended by 0][...]
    {
        if (n < 3) return;
        char *dst = p[1] == ADDR_FC ? t.fcName : p[1] == ADDR_RX ? t.rxName : p[1] == ADDR_MODULE ? t.moduleName : nullptr;
        if (!dst) return;
        takeName(p + 2, (uint8_t)(n - 2), dst, sizeof(t.fcName));
        ++t.nInfo;
        if (p[1] == ADDR_MODULE)
        {   // after its name's 0: a serial number, its hardware's and its software's versions (4 bytes each), HOW MANY SETTINGS IT HAS, their protocol's version
            uint8_t z = 2;
            while (z < n && p[z]) ++z;
            if ((uint16_t)z + 14 <= n) t.moduleParams = p[z + 13];
            ++t.nModuleInfo;
        }
        if (p[1] == ADDR_FC)
        {
            uint8_t a, b;
            if (rotorflightName(dst, a, b)) { t.rotorflight = true; t.rfMajor = a; t.rfMinor = b; t.fresh |= F_KIND; }
        }
        break;
    }
    case T_PARAM_ENTRY: // a piece of one of the module's own settings: [destination][origin][number][chunks still to come][data ...]
        if (n < 4 || p[1] != ADDR_MODULE) return;   // (a receiver's or a flight controller's settings are not asked for)
        t.params.chunkIn(p + 2, (uint8_t)(n - 2));
        break;
    case T_HANDSET: // an extended frame: [destination][origin][subcommand][...]
        if (n < 11 || p[2] != SUB_TIMING) return;
        t.intervalTenthsUs = be32(p + 3);
        t.offsetTenthsUs = be32(p + 7);
        t.timingMs = nowMs ? nowMs : 1;
        ++t.timingFrames;
        break;
    default:
        ++t.unknownType;   // fine: the router passes on whatever the receiver sends
        break;
    }
}

// Assembles frames from the bytes as they come. Anything that is not a frame is skipped, a byte at a time.
struct Parser
{
    uint8_t buf[MAX_FRAME];
    uint8_t len = 0;
    // One byte. True when it completed a good frame FROM THE MODULE (decoded into t).
    bool feed(uint8_t b, Telemetry &t, uint32_t nowMs)
    {
        if (len == 0)
        {
            if (b == SYNC_BYTE || b == ADDR_HANDSET || b == ADDR_MODULE || b == 0xEC)
                buf[len++] = b;
            return false;
        }
        if (len == 1)
        {
            if (b < 2 || b > MAX_FRAME - 2)
            {   // not a length. If it is itself a start (200, 234, 236, 238 are all too long to be one), the frame it begins is not lost with it
                ++t.badLength;
                len = 0;
                if (b == SYNC_BYTE || b == ADDR_HANDSET || b == ADDR_MODULE || b == 0xEC)
                    buf[len++] = b;
                return false;
            }
            buf[len++] = b;
            return false;
        }
        buf[len++] = b;
        const uint8_t total = (uint8_t)(buf[1] + 2);
        if (len < total) return false;
        len = 0;
        if (crc8(&buf[2], (uint8_t)(total - 3)) != buf[total - 1]) { ++t.badCrc; return false; }
        // A good frame that starts with the MODULE'S address is one of OURS, heard back on the one wire (whether a
        // Teensy 4.1 hears its own half-duplex bytes is for the bench to say). The module's own frames start with 0xC8 or
        // our address. Counted apart and not read, so "frames back" in the log can only mean the module answered.
        if (buf[0] == ADDR_MODULE) { ++t.ownEcho; return false; }
        ++t.framesOk;
        decode(buf[2], &buf[3], (uint8_t)(total - 4), t, nowMs);
        return true;
    }
};

// ---- PHASE 2, STEP 1: THE FRAMES FROM A TIMER, IN STEP WITH THE MODULE, AND NEVER STALE --------------------------------
// (12 Nov 2026, the evening of the first link.) Phase 1 sent a frame from loop() whenever one was due. loop() is paced by
// the LDRC radio (about 4.5 ms a pass with no model), so the yellow transmitter sent 222 frames a second. The module
// sends 250 packets a second whatever we do: 28 a second went out with the channels of the packet before, and for each
// of those it sent a "you are late" timing frame at once - 138 timing frames in 5 s where 25 are due (dev/test_elrs
// gets that very figure out of a model of the module's code, which is how the model is known to be right).
//
// THE MODULE'S TIMING FRAME, exactly (ExpressLRS 3.6.4, CRSFHandset.cpp, JustSentRFpacket and sendSyncPacketToTX): at
// each radio packet it takes delta = now - when our last frame came. If delta is under its interval it averages delta
// over the packets of 20 ms; if not ("missing/late packet") it says -(delta % interval) at once. What it sends is that,
// less 100 us, in tenths of a microsecond: PLUS = our frame came that much earlier than it needs (it wants it 100 us
// before the packet), MINUS = that much late. The handset's part (EdgeTX, ModuleSyncStatus): make ONE period that much
// longer (or shorter), then go on at the module's interval. Pacer does that, with three cautions of its own:
//  - A period is never shortened by more than an eighth at a time: the module answers on the same wire after every
//    frame of ours (up to 64 bytes, 1.6 ms), and a frame sent much too soon would talk over it. A large "sooner" is
//    spread over the following periods. "Later" is given at once (it is never more than one interval).
//  - After a correction no other is taken until the module's average has forgotten the old timing (settleMs): two
//    timing frames measured before the first correction showed would otherwise both be acted on.
//  - Under DEAD_US nothing is done: its figure is an average of a few packets, and that close is as good as it gets.
//
// NEVER STALE (sticksFresh): the timer sends only a FINISHED copy of the channels, made by loop() at the end of its
// pass - never the transmitter's own send buffer, which loop() fills in stages (the mixes, then the buddy, then the
// safety switch that puts the throttle low: a timer reading it mid-pass could send the throttle the safety switch was
// about to cancel). And if loop() has made no copy for STICKS_STALE_MS (it is in another mode, or stuck), the timer
// sends NOTHING: the module then drops the link and the receiver's failsafe acts, which is right - a transmitter that
// goes on sending the last sticks it knew is the worst kind of failure.
constexpr int32_t DEAD_US = 10;
constexpr uint32_t STICKS_STALE_MS = 100;
inline bool sticksFresh(uint32_t lastCopyMs, uint32_t nowMs) { return lastCopyMs != 0 && (uint32_t)(nowMs - lastCopyMs) < STICKS_STALE_MS; }
// How long the module's word is left alone after a correction: the two periods the timer needs to take it up, the
// eight a large "sooner" may be spread over, and the 20 ms of the module's average.
inline uint32_t settleMs(uint32_t intervalUs) { return 20 + (10 * intervalUs + 999) / 1000; }

struct Pacer
{
    uint32_t intervalUs = DEFAULT_PERIOD_US; // the module's packet interval as it last said (4 ms until it has)
    int32_t lagUs = 0;                       // still to be put into (+) or taken out of (-) the periods to come
    uint32_t usedTimingFrames = 0;           // Telemetry::timingFrames when we last looked: each timing frame is used once
    uint32_t settleUntilMs = 0;              // no new correction before this
    bool settling = false;
    uint32_t corrections = 0;                // how many timing frames were acted on (for the log)

    // loop()'s part, whenever a timing frame may have come (on the Teensy: with interrupts off, the timer shares this).
    // True when a new one was acted on.
    bool onTiming(const Telemetry &t, uint32_t nowMs)
    {
        if (t.timingFrames == usedTimingFrames) return false;
        usedTimingFrames = t.timingFrames;
        if (t.intervalTenthsUs < 10000 || t.intervalTenthsUs > 200000) return false; // 1 to 20 ms, whatever a frame might say
        const uint32_t iv = (uint32_t)(t.intervalTenthsUs / 10);
        if (iv != intervalUs)
        {   // a new packet rate: its interval from now, and its offset only once it has measured us at it
            intervalUs = iv;
            lagUs = 0;
            settling = true;
            settleUntilMs = nowMs + settleMs(iv);
            return true;
        }
        if (settling)
        {
            if ((int32_t)(nowMs - settleUntilMs) < 0) return false; // measured before our last correction had shown
            settling = false;
        }
        int32_t off = t.offsetTenthsUs / 10;
        const int32_t lim = (int32_t)intervalUs;
        if (off > lim) off = lim;
        if (off < -lim) off = -lim;
        if (off > -DEAD_US && off < DEAD_US) return false; // close enough
        lagUs = off;
        settling = true;
        settleUntilMs = nowMs + settleMs(intervalUs);
        ++corrections;
        return true;
    }
    // The timer's part, once per frame: the period to load for the one after next.
    uint32_t nextPeriodUs()
    {
        int32_t step = lagUs;
        const int32_t most = (int32_t)(intervalUs / 8);
        if (step < -most) step = -most;
        lagUs -= step;
        return (uint32_t)((int32_t)intervalUs + step);
    }
};

// THE MODULE'S POWER SWITCH (12 Nov 2026: Malcolm builds it for the bench tests, then it goes on the revised board).
// Teensy pin 10 (the BUDDY header's outer pins) -> 10k -> a BC547B's base (4.7k and 100 nF from base to ground); its
// collector -> 47k -> the gate of an AO3401A (P-channel MOSFET) in the battery line to the module, with 100k and 1 uF from
// gate to source (the soft start) and 4.7k from the switched side to ground. HIGH = on. Low, or a pin nobody drives (the
// Teensy starting up; a release, which never touches pin 10) = off: the 14.7k to ground beats the pin's keeper. By
// simulation the module's supply is up about 11 ms after the pin rises (0.6 to 1.5 A at most, where a bare switch would
// take 10 to 19 A) and gone about 0.13 s after it falls. The serial line is left alone until the module has had power
// for POWER_SETTLE_MS: an unpowered module must not be fed through its signal pin.
constexpr uint8_t POWER_PIN = 10;
constexpr uint32_t POWER_SETTLE_MS = 300;
inline bool lineMayStart(bool powerOn, uint32_t powerOnMs, uint32_t nowMs)
{
    return powerOn && (uint32_t)(nowMs - powerOnMs) >= POWER_SETTLE_MS; // the subtraction is right across millis()'s roll-over
}

// ---- PHASE 2, STEP 2: THE MODEL'S OWN LINK ---------------------------------------------------------------------------
// (13 Nov 2026.) A model set to ELRS on Model options flies on the module alone. What the transmitter then has to know:
//
// IS THE MODEL THERE? The module says so itself: it sends its link statistics (frame 0x14) only while it hears the
// receiver, every 240 ms (ExpressLRS tx_main.cpp: "if ((connectionState == connected) ... tlm_report_interval"). So the
// link is HEARD while a 0x14 is under LINK_LOST_MS old. But hearing is not control: the model's replies are the weaker
// half of an ExpressLRS link, and far out they stop while the sticks still arrive. So, unlike LDRC:
//  - Nothing that is sent ever depends on what is heard. The channel frames go out while loop() runs, heard or not.
//  - Heard for the first time: connected (the green light, "Connected", the log, the boxes) - exactly as an LDRC model.
//  - No longer heard: SILENT - the front page says "No telemetry", the battery warnings stop (their figures are old),
//    and NOTHING ELSE changes: still connected, the motor switch still works (a bail-out must).
//  - Given up ("Disconnected", the red light, the motor switch refused until the model is heard again - LDRC's own rule
//    for a model that is not there) only when silent AND the motor switch is off - and, once the motor switch has been
//    on at all, has been off for MOTOR_OFF_GRACE_MS. On the bench that is at once. In the air it cannot happen with the
//    motor running, nor in the half minute after it is switched off (an autorotation: the switch must still bring the
//    motor back).
constexpr uint32_t LINK_LOST_MS = 2000;
constexpr uint32_t MOTOR_OFF_GRACE_MS = 30000;
inline bool linkHeard(const Telemetry &t, uint32_t nowMs) { return t.linkMs != 0 && (uint32_t)(nowMs - t.linkMs) < LINK_LOST_MS; }
struct LinkState
{
    bool green = false;       // connected, as the rest of the transmitter means it
    bool silent = false;      // ... but nothing is heard from the model just now
    bool motorEverOn = false; // the motor switch has been on at some time since this began
    bool motorOff = true;     // ... and is off now, since:
    uint32_t motorOffSinceMs = 0;
    // Once a pass. +1: just connected. -1: just given up. 0: neither.
    int step(bool heard, bool motorOn, uint32_t nowMs)
    {
        if (motorOn) { motorOff = false; motorEverOn = true; }
        else if (!motorOff) { motorOff = true; motorOffSinceMs = nowMs; }
        if (heard)
        {
            silent = false;
            if (green) return 0;
            green = true;
            return 1;
        }
        if (!green) return 0;
        silent = true;
        if (motorOff && (!motorEverOn || (uint32_t)(nowMs - motorOffSinceMs) >= MOTOR_OFF_GRACE_MS))
        {
            green = silent = false;
            return -1;
        }
        return 0;
    }
};

// WHAT IT SAYS, INTO THE USUAL BOXES. The transmitter already has one place that knows what a model's telemetry means:
// ParseTelemetryItem (transceiver.h), fed by an LDRC receiver's acknowledgements - an item number and four bytes. The
// model's ELRS telemetry is turned into the same items, so the front page, the Telemetry page, the warnings and the log
// treat it exactly as they treat LDRC's. The items used (their numbers are LDRC's own):
constexpr uint8_t ITEM_VOLTS = 5, ITEM_RPM = 20, ITEM_AMPS = 21, ITEM_MAH = 22, ITEM_ESC_TEMP = 24, ITEM_ROTORFLIGHT = 31;
constexpr uint8_t MAX_ITEMS = 6;
struct Item { uint8_t id; uint8_t b[4]; };
inline void itemFloat(Item &it, uint8_t id, float v) { it.id = id; memcpy(it.b, &v, 4); }   // (as GetFloatFromAckPayload reads it)
inline void itemU32(Item &it, uint8_t id, uint32_t v) { it.id = id; it.b[0] = (uint8_t)v; it.b[1] = (uint8_t)(v >> 8); it.b[2] = (uint8_t)(v >> 16); it.b[3] = (uint8_t)(v >> 24); }
inline uint32_t rpmForItem(int32_t r) { return r < 0 ? 0u : (r > 65534 ? 65534u : (uint32_t)r); }   // (65535 and over is "no reading" to the transmitter)
// Which of the transmitter's two kinds of Rotorflight (RFVersions, 1Definitions.h: 1 = 2.2 and before, 2 = 2.3): by the
// version it gave ("4.6" is 2.3, "4.5" 2.2), else what the model's file knew, else the newer.
inline uint8_t rotorflightKind(const Telemetry &t, uint8_t fromFile)
{
    if (t.rfMajor == 4 && t.rfMinor) return t.rfMinor >= 6 ? 2 : 1;
    if (t.rfMajor > 4) return 2;
    return (fromFile == 1 || fromFile == 2) ? fromFile : 2;
}
// What has come since the last call, as items (out has room for MAX_ITEMS). "It is Rotorflight" goes first: the
// transmitter takes head speed, amps and mAh only from a model it knows to be one. halveVolts: the model is set to 12
// cells - an LDRC receiver measures such a pack through a divider and the transmitter doubles what it is told.
inline uint8_t takeItems(Telemetry &t, bool halveVolts, uint8_t kindFromFile, Item *out)
{
    uint8_t n = 0;
    const uint32_t f = t.fresh;
    t.fresh = 0;
    if ((f & F_KIND) && t.rotorflight) itemU32(out[n++], ITEM_ROTORFLIGHT, rotorflightKind(t, kindFromFile));
    if (f & F_VOLTS) itemFloat(out[n++], ITEM_VOLTS, (float)t.voltsCenti / (halveVolts ? 200.0f : 100.0f));
    if (f & F_RPM) itemU32(out[n++], ITEM_RPM, rpmForItem(t.headRpm));
    if (f & F_AMPS) itemFloat(out[n++], ITEM_AMPS, (float)t.ampsCenti / 100.0f);
    if (f & F_MAH) itemFloat(out[n++], ITEM_MAH, (float)t.mah);
    if (f & F_ESC_TEMP) itemFloat(out[n++], ITEM_ESC_TEMP, (float)t.escTempDeciC / 10.0f);
    return n;
}

// "WHO IS THERE?" (frame 0x28 to everyone, from us). The module answers for itself, and passes it on to the receiver and
// the flight controller once it hears them (CRSFHandset.cpp, ForwardDevicePings); each answers with its name (0x29). A
// flight controller named "Rotorflight ..." is how a model never flown on LDRC is known to be one. It goes out in place
// of ONE channel frame (as EdgeTX sends it), and only with the motor switch off.
constexpr uint8_t PING_LEN = 6;
constexpr uint32_t PING_EVERY_MS = 3000;
constexpr uint8_t PING_TRIES = 8;
inline void buildPing(uint8_t *out)
{
    out[0] = ADDR_MODULE;
    out[1] = 4;   // type, destination, origin, CRC
    out[2] = T_DEVICE_PING;
    out[3] = ADDR_BROADCAST;
    out[4] = ADDR_HANDSET;
    out[5] = crc8(&out[2], 3);
}
// A model's setting must stand this long before the link is changed (a search through the model memories reads one
// after another; none of them is "the model" until the reading stops). While a model set to ELRS waits out this time,
// LDRC's radio is already silent (ElrsLink): not one LDRC packet is sent for such a model, from the first pass on.
constexpr uint32_t MODEL_SETTLE_MS = 100;
// When loop() has been away from the module's line this long (another mode, a long wait), what the line then holds is
// old: it is thrown away, not read as news.
constexpr uint32_t LINE_STALE_MS = 250;
} // namespace ElrsCrsf
// ELRS-CRSF-END

#ifdef ELRS_TEST
// ---------------------------------------------------------------------------------------------------------------------
// THE DRIVER (test builds only). Serial6 (TX6 = pin 24), one wire, 400000 baud, not inverted (in half duplex the Teensy
// holds the line up with its pad's pull-up between bytes, which is a non-inverted line's idle; the module tries both
// polarities). It runs only for a model set to ELRS (ElrsModel: Model options), and then INSTEAD of LDRC's radio:
// SendData (transceiver.h) hands each of its calls to ElrsLink() and sends nothing itself. So the module's link is kept
// going wherever LDRC's is: in loop(), and through the transmitter's waits (DelayWithDog). ElrsLink() keeps a finished
// copy of the channels and reads what the module says; a hardware timer sends that copy, one frame per packet of the
// module's (PHASE 2, STEP 1 above). The timer never waits and never reads SendBuffer.
static ElrsCrsf::Parser ElrsParser;
static ElrsCrsf::Telemetry ElrsTelem;
static ElrsCrsf::Pacer ElrsPacer;          // the timer's and loop()'s: loop() touches it only with interrupts off
static ElrsCrsf::LinkState ElrsState;      // connected, silent, given up (THE MODEL'S OWN LINK above)
static IntervalTimer ElrsTimer;
static volatile uint16_t ElrsChannels[16]; // the FINISHED channels of loop()'s last pass: all the timer ever sends
static volatile uint32_t ElrsCopyMs = 0;   // when loop() made that copy (0 = never)
static volatile uint32_t ElrsSent = 0, ElrsSkipped = 0, ElrsHeldBack = 0, ElrsOtherSent = 0;
static volatile uint8_t ElrsOther[8];      // one frame of ours that is not the channels ("who is there?"): loop() leaves it here ...
static volatile uint8_t ElrsOtherLen = 0;  // ... and the timer sends it once, in place of one channel frame
static_assert(sizeof(ElrsOther) >= ElrsCrsf::PING_LEN && sizeof(ElrsOther) >= ElrsCrsf::PARAM_FRAME_LEN, "the timer's place for a frame that is not the channels must hold a ping and a request for a setting");
static uint32_t ElrsLoadedUs = 0;          // the period the timer was last given (the timer's own)
static uint32_t ElrsLastLogMs = 0, ElrsPowerOnMs = 0, ElrsLoggedTiming = 0;
static uint32_t ElrsBytesIn = 0; // every byte the line gave us, frame or not: bytes but no frames = the wrong speed or polarity; no bytes = nothing answers
static bool ElrsOn = false;      // the module is this model's link: this driver runs, and LDRC's radio says nothing
static bool ElrsStarted = false, ElrsPowered = false, ElrsLineHasRoom = false;
static bool ElrsWantLast = false;
static bool ElrsBusy = false;    // the link is being begun, ended or read: a wait inside it that comes back to ElrsLink() does not begin that again
static uint32_t ElrsNotRedMs = 0; // since when no model is heard and the light is not red (0 = not so)
static uint32_t ElrsWantSinceMs = 0, ElrsLastPassMs = 0, ElrsSecondMs = 0, ElrsRpmItemMs = 0, ElrsPingMs = 0, ElrsSentSeen = 0;
static uint8_t ElrsPings = 0, ElrsNamesSaid = 0, ElrsLogNext = 4; // (ElrsLogNext: which of the bench's four lines is next; 4 = none due)
static uint8_t ElrsModulePings = 0, ElrsListLine = 0;             // the module asked how many settings it has; which line of the setting in hand the log gets next
static bool ElrsListBegun = false, ElrsListSaid = false;          // the reading of the module's settings: begun, and its last line written
static bool ElrsListInBox = false;                                // a request for a setting lies in the timer's place and has not gone out yet
// THE PAGE "ELRS settings" (ElrsView) AND A CHANGE ASKED OF THE MODULE. A change goes in three steps, each on the ground
// only: written (one frame, through the timer's place), a moment for the module to take it, and the list read again -
// what the module then says is what counts.
static ElrsCrsf::Setting ElrsSet[ElrsCrsf::SET_COUNT];            // the four settings the page shows, as the module last said them (NOT in RAM2: that is not given its initial values at the start)
static uint8_t ElrsChange = 255, ElrsChangeTo = 0;                // the setting a change is asked for, and the place of the choice wanted
static uint8_t ElrsChangeStep = 0;                                // 0 none; 1 to be written; 2 written, the module has its moment; 3 being read back
static uint8_t ElrsChangeResult = 0;                              // of the last change: 0 nothing to say; 1 taken; 2 the module kept what it had
static uint8_t ElrsChangeReads = 0;                               // how often it has been read back without the module saying the new value
static bool ElrsChangeInBox = false;                              // the frame that writes it lies in the timer's place and has not gone out yet
static bool ElrsListQuiet = false;                                // the reading in hand is a reading-back: its lines are not written to the log again
static bool ElrsListWanted = false;                               // the page was opened: the list is to be read again (the module may have been changed elsewhere)
static uint32_t ElrsChangeMs = 0, ElrsChangeAskedMs = 0, ElrsViewSig = 0; // when it was written; when it was asked for; what the page last showed (drawn again only when that changes)
static uint8_t ElrsPickFor = 255;                                 // the setting the picker is open for
static const uint32_t ELRS_CHANGE_SETTLE_MS = 400;                // the module's moment before the first reading-back (it tells the receiver and saves before it says the new value) ...
static const uint32_t ELRS_CHANGE_AGAIN_MS = 1000;                // ... and before each further one
static const uint8_t ELRS_CHANGE_READS = 3;                       // readings-back before "the module kept what it had" is said
static const uint32_t ELRS_CHANGE_ASK_MS = 5000;                  // a change not written within this of being asked for is dropped
// THE THROTTLE HELD. An LDRC model's throttle is channel 5, which ExpressLRS carries as ONE BIT in every switch mode but
// "16ch Rate/2" (carriesChannel5): the motor switch would be all or nothing. So for a model whose throttle is channel 5,
// every frame carries "motor off" on it UNTIL THE MODULE HAS SAID that its switch mode is that one (ElrsCrsf::
// throttleHeld): from the moment the module takes the link (ElrsBegin), through every reading of its list, and whenever
// it says another mode. The front page says "Throttle held", the settings page says what to choose, and the motor
// switch put on while it is held is answered with the warning sound.
// IT CHANGES ON THE GROUND ONLY (ElrsOnTheGround): nothing here can take a running motor away, and nothing gives a
// throttle back in the air. One thing is carried over a restart IN FLIGHT (FlightGuard.h, the clock chip's stamp): that
// the module had said the one mode two seconds before - or the restart would stop the motor of a model that was flying.
// And one thing is done wherever the model is: when the model's THROTTLE CHANNEL itself changes (Model options; another
// of the module's models chosen) the rule is applied at once, in the copy (ElrsLink) - nothing runs on a throttle that
// has just moved, and a throttle moved ONTO channel 5 with the safety off would else be live on one bit.
// While a change of packet rate or switch mode is being written and read back, the module's word is "not known" (it
// may still say the old mode for a moment): held until the change is taken or kept.
// (Found by review, 14 Nov 2026: a change of packet rate turns "16ch Rate/2" into "Hybrid"; and, the same day: not known
// must mean held.)
static bool ElrsHeld = false;
static uint8_t ElrsCh5 = ElrsCrsf::CH5_UNKNOWN; // what the module last said of its switch mode (never forgotten while the list is read again)
static uint32_t ElrsBeganMs = 0;                // when the module took the link
static uint8_t ElrsThrottleWas = 255;           // the model's throttle channel as the rule last took it (255: none)
static bool ElrsHeldSaid = false, ElrsMotorWas = false;
FLASHMEM static void ElrsViewShow();
static const uint8_t ElrsLinePin = 24; // Serial6's transmit pin: the one wire
// Serial6's own receive buffer is 64 bytes: one long frame of the module's. loop() can be away for some milliseconds
// (the screen, the card), so the port is given this as well - a full buffer would show in the log as bad CRCs that are
// not the wire's fault.
DMAMEM static uint8_t ElrsRxMore[512];

// MAY THE MODEL BE FLYING? Then nothing in this file writes to the card (a line of the log is tens of milliseconds in
// which loop() makes no new copy of the sticks) and nothing of ours takes a channel frame's place. "The motor switch is
// off" is NOT that test: an autorotation is a motor-off (LogFiles.h, B47/B48). Found by review on 14 Nov 2026, before
// any of this had flown: the bench's lines, "who is there?" and the reading of the module's settings all went by the
// motor switch alone. The transmitter's own test is the safety switch, which changes on the ground (RadiosMustBeOff,
// FlightGuard.h). Where no safety switch is defined the motor switch is all there is to go by: there, a model that is
// connected and has had its motor switch on since this link began may be flying until it is given up.
static bool ElrsMayFly()
{
    if (SafetyIsDefined())
        return SafetyIsOff() || MotorEnabled;
    return MotorEnabled || (ElrsState.green && ElrsState.motorEverOn);
}
// One line into the log. On the ground it is written now (LogText empties the text it is given, so: a copy). While the
// model may be flying it is kept, with its time, for the transmitter's own quiet moment (DeferLogText: the safety's next
// change, the disconnection, power-off) - which keeps its first 36 characters: what may be said in the air begins with
// what matters. That store has 24 places for everything the transmitter has to say, and when it is full it writes them
// all at once, in the air: so this file takes ELRS_KEEP_MAX of them at most between two times on the ground, and counts
// what found no place (the count is said on the ground).
static const uint8_t ELRS_KEEP_MAX = 6;
static uint8_t ElrsKept = 0;
static uint16_t ElrsNotKept = 0;
FLASHMEM static void ElrsSay(const char *text, bool stamp = true)
{
    if (ElrsMayFly())
    {
        if (ElrsKept < ELRS_KEEP_MAX)
        {
            ++ElrsKept;
            DeferLogText(text, true);
        }
        else if (ElrsNotKept < 65535)
            ++ElrsNotKept;
        return;
    }
    char line[200];
    snprintf(line, sizeof(line), "%s", text);
    LogText(line, (uint16_t)strlen(line), stamp);
}

// What the rest of the transmitter asks (their prototypes are in 1Definitions.h, each use inside #ifdef ELRS_TEST):
// "is this model's link the module's?" - from the moment the model in memory is an ELRS one (before its link has begun
// too: LDRC must not ping, hold the model back for the safety switch, or count its packets in that tenth of a second).
bool ElrsCarries() { return ElrsOn || ElrsModel; }
// A WAIT MAY FLY THE MODEL (DelayWithDog, a question box's loop: the sticks read and sent through it) - but not before setup()
// is over: the switches have not been read and the sticks' converter is not started (ElrsLink says the rest).
static bool ElrsSetupDone = false;
bool ElrsFlies() { return ElrsSetupDone && (ElrsOn || ElrsModel); }
void ElrsSetupOver() { ElrsSetupDone = true; }
// For the stamp of a model that is flying (FlightGuard.h): THE MODULE HAS SAID the one switch mode that carries channel 5. (Not
// "the throttle is not held": a throttle that is not channel 5 is never held, whatever the mode - and after a restart in flight
// that word was taken for the module's, so a throttle then moved onto channel 5 was live on one bit. The fourth review, 14 Nov 2026.)
bool ElrsModuleCarries() { return ElrsOn && ElrsCh5 == ElrsCrsf::CH5_CARRIED; }
// The front page's quality bar for such a model: the module's own figure - of the packets it sent, how many the receiver
// got, in per cent. Nothing heard: nothing.
uint16_t ElrsQuality() { return (ElrsState.green && !ElrsState.silent) ? (uint16_t)(ElrsTelem.upLq > 100 ? 100 : ElrsTelem.upLq) : 0; }
// Model options (MenuOptions.h): the page keeps the switch and its label hidden by itself (its own start-up lines), so a
// transmitter without this code shows nothing of it.
FLASHMEM void ElrsOptionShow()
{
    SendCommand((char *)"vis l_t6,1");
    SendCommand((char *)"vis c4,1");
    SendValue((char *)"c4", ElrsModel ? 1 : 0);
    if (ElrsModel)
        SendCommand((char *)"vis bElrs,1"); // "ELRS settings ..." (the page hides it by itself: an older page file has none, and nothing happens)
}
FLASHMEM void ElrsOptionSet(uint32_t v) // (the box's answer, asked by Model options with its own last boxes: MenuOptions.h ReadRXOptionsView)
{
    if (v <= 1) // (a reply that never came, 65535, keeps it as it was)
        ElrsModel = (v == 1);
}

// The module's power, on (pin 10 high works the switch; with no switch fitted nothing happens, and the module's own
// supply does the job). Said in the log, so the bench can see it.
FLASHMEM static void ElrsPowerOn()
{
    pinMode(ElrsCrsf::POWER_PIN, OUTPUT);
    digitalWriteFast(ElrsCrsf::POWER_PIN, HIGH);
    ElrsPowered = true;
    ElrsPowerOnMs = millis();
    ElrsSay(PSTR("ELRS test: module power ON (pin 10 high); the serial line starts in 0.3 s"));
}
// setup(), as soon as the model in memory is known and the clock is read: THE POWER of a model set to ELRS, at once. The
// link itself waits for setup's end (ElrsLink says why), but the module takes a second or two of its own to start - and
// after a restart IN FLIGHT, with its power worked by pin 10, that time came on top of setup's (the sixth review, 14 Nov
// 2026). Nothing is sent to it meanwhile: a module with power and no frames does nothing.
FLASHMEM void ElrsPowerEarly()
{
    if (ElrsModel && !ElrsPowered)
        ElrsPowerOn();
}

// THE TIMER: one frame, from the finished copy only, and the period for the frame after next. A few microseconds; it
// never waits (a frame that would not fit the serial buffer whole is skipped and counted, not queued).
FASTRUN void ElrsSendIsr()
{
    const uint32_t p = ElrsPacer.nextPeriodUs();
    if (p != ElrsLoadedUs)
    {
        ElrsTimer.update(p); // the timer takes it up at its next reload
        ElrsLoadedUs = p;
    }
    if (!ElrsCrsf::sticksFresh(ElrsCopyMs, millis()))
    {
        ++ElrsHeldBack; // loop() is away: nothing is sent, and the receiver's failsafe is left to act
        return;
    }
    uint8_t f[ElrsCrsf::RC_FRAME_LEN];
    uint8_t len = ElrsOtherLen;
    const bool other = len != 0;
    if (other)
    {   // "who is there?", once, in place of this period's channels (loop() left it; the next period has the channels again)
        if (len > sizeof(ElrsOther))
            len = sizeof(ElrsOther);
        for (uint8_t i = 0; i < len; ++i)
            f[i] = ElrsOther[i];
        ElrsOtherLen = 0;
    }
    else
    {
        uint16_t ch[16];
        for (uint8_t i = 0; i < 16; ++i)
            ch[i] = ElrsChannels[i];
        ElrsCrsf::buildRcFrame(ch, f);
        len = ElrsCrsf::RC_FRAME_LEN;
    }
    if (Serial6.availableForWrite() >= (int)len)
    {
        Serial6.write(f, len);
        if (other)
            ++ElrsOtherSent;
        else
            ++ElrsSent;
    }
    else
        ++ElrsSkipped;
}

// The bench's lines, every 5 s: ONE LINE A PASS (a line is a write to the card, some milliseconds during which loop() makes
// no new copy of the channels). k = which of the four; false when that one has nothing to say.
FLASHMEM static bool ElrsLogLine(uint8_t k)
{
    using namespace ElrsCrsf;
    char line[300];
    const uint32_t now = millis();
    const bool link = linkHeard(ElrsTelem, now);
    if (k == 0)
        snprintf(line, sizeof(line), PSTR("ELRS test: sent %lu (skipped %lu), bytes in %lu, frames back %lu (bad CRC %lu, bad length %lu, own echo %lu), %s LQ %u%% RSSI %d dBm power code %u, rate %ld us (offset %ld/10 us)"),
                 (unsigned long)ElrsSent, (unsigned long)ElrsSkipped, (unsigned long)ElrsBytesIn, (unsigned long)ElrsTelem.framesOk, (unsigned long)ElrsTelem.badCrc,
                 (unsigned long)ElrsTelem.badLength, (unsigned long)ElrsTelem.ownEcho,
                 link ? "LINK" : "no link", (unsigned)ElrsTelem.upLq, (int)ElrsTelem.upRssi1, (unsigned)ElrsTelem.txPower,
                 (long)(ElrsTelem.intervalTenthsUs / 10), (long)ElrsTelem.offsetTenthsUs);
    else if (k == 1)
    {   // in step or not: 25 timing frames in 5 s when our frames come as the module wants them, more when it had to send without us
        snprintf(line, sizeof(line), PSTR("ELRS test: timing frames %lu (%lu in the last 5 s; 25 = in step), corrections %lu, held back %lu"),
                 (unsigned long)ElrsTelem.timingFrames, (unsigned long)(ElrsTelem.timingFrames - ElrsLoggedTiming), (unsigned long)ElrsPacer.corrections,
                 (unsigned long)ElrsHeldBack);
        ElrsLoggedTiming = ElrsTelem.timingFrames;
    }
    else if (!link)
        return false;
    else if (k == 2) // what the model says, in the common units (whichever frames brought it) ...
        snprintf(line, sizeof(line), PSTR("ELRS test: model battery %u.%02u V, %u.%02u A, %lu mAh, rpm %ld, ESC %d.%d C, mode %s, down LQ %u%% RSSI %d dBm"),
                 ElrsTelem.voltsCenti / 100, ElrsTelem.voltsCenti % 100, ElrsTelem.ampsCenti / 100, ElrsTelem.ampsCenti % 100,
                 (unsigned long)ElrsTelem.mah, (long)ElrsTelem.headRpm, ElrsTelem.escTempDeciC / 10, abs(ElrsTelem.escTempDeciC % 10), ElrsTelem.flightMode,
                 (unsigned)ElrsTelem.downLq, (int)ElrsTelem.downRssi);
    else // ... and which frames they were: what this flight controller really sends
        snprintf(line, sizeof(line), PSTR("ELRS test: frames by kind: battery %lu, rpm %lu, temperature %lu, mode %lu, attitude %lu, names %lu, Rotorflight's own %lu (values %lu, cut short %lu), other %lu; our frames that were not the channels %lu"),
                 (unsigned long)ElrsTelem.nBattery, (unsigned long)ElrsTelem.nRpm, (unsigned long)ElrsTelem.nTemp, (unsigned long)ElrsTelem.nMode, (unsigned long)ElrsTelem.nAttitude,
                 (unsigned long)ElrsTelem.nInfo, (unsigned long)ElrsTelem.customFrames, (unsigned long)ElrsTelem.customSensors, (unsigned long)ElrsTelem.customUnknown,
                 (unsigned long)ElrsTelem.unknownType, (unsigned long)ElrsOtherSent);
    LogText(line, strlen(line), false);
    return true;
}

// One of the module's own settings into the log, a line a call (each is a write to the card): what it is, then what it
// says in pieces a log line can hold. True: it has more lines.
FLASHMEM static bool ElrsListLog(const ElrsCrsf::Param &q, uint8_t part)
{
    char line[200];
    const uint16_t textLen = (uint16_t)strlen(q.text);
    const uint16_t piece = 150;
    if (part == 0)
    {
        const char *kind = q.kind == ElrsCrsf::P_CHOICE ? "choice" : q.kind == ElrsCrsf::P_FOLDER ? "folder" : q.kind == ElrsCrsf::P_COMMAND ? "command"
                         : (q.kind == ElrsCrsf::P_INFO || q.kind == ElrsCrsf::P_STRING) ? "text" : q.kind <= ElrsCrsf::P_INT16 ? "number" : "other";
        snprintf(line, sizeof(line), PSTR("ELRS test: setting %u '%s' (%s, kind %u, in %u%s%s): value %u, min %u, max %u, units '%s'"), (unsigned)q.number, q.name, kind,
                 (unsigned)q.kind, (unsigned)q.parent, q.hidden ? ", hidden" : "", q.cut ? ", CUT SHORT" : "", (unsigned)q.value, (unsigned)q.min, (unsigned)q.max, q.units);
        LogText(line, strlen(line), false);
        return textLen > 0;
    }
    const uint16_t from = (uint16_t)((part - 1) * piece);
    if (from >= textLen)
        return false;
    snprintf(line, sizeof(line), PSTR("ELRS test: setting %u says%s: %.150s"), (unsigned)q.number, from ? " (more)" : "", q.text + from);
    LogText(line, strlen(line), false);
    return (uint16_t)(from + piece) < textLen;
}

// One of the transmitter's own telemetry items, to the code that reads an LDRC receiver's (transceiver.h): the same
// buffer, the same switch - as the Bluetooth pipe's items go (TelemetryFromPipe). LDRC's radio is silent meanwhile, so
// the buffer is ours.
static void ElrsItem(const ElrsCrsf::Item &it)
{
    AckPayload.Ack_Payload_byte[0] = it.id;
    for (uint8_t i = 0; i < 4; ++i)
        AckPayload.Ack_Payload_byte[1 + i] = it.b[i];
    ParseTelemetryItem();
}

// This model's link becomes the module: LDRC's "no model" first (the red light; "Disconnected" if an LDRC model was
// connected; the motor switch refused until a model is heard - RedLedOn's own rules), then the module's power.
FLASHMEM static void ElrsBegin()
{
    ElrsOn = true;
    ElrsTelem = ElrsCrsf::Telemetry();
    ElrsParser.len = 0;
    ElrsState = ElrsCrsf::LinkState();
    noInterrupts();
    ElrsPacer = ElrsCrsf::Pacer();
    ElrsCopyMs = 0;
    ElrsOtherLen = 0;
    ElrsSent = ElrsSkipped = ElrsHeldBack = ElrsOtherSent = 0;
    interrupts();
    ElrsBytesIn = ElrsLoggedTiming = ElrsSentSeen = 0;
    ElrsPings = ElrsNamesSaid = 0;
    ElrsModulePings = ElrsListLine = 0;
    ElrsListBegun = ElrsListSaid = ElrsListInBox = false;
    for (uint8_t k = 0; k < ElrsCrsf::SET_COUNT; ++k)
        ElrsSet[k] = ElrsCrsf::Setting();
    ElrsChange = 255;
    ElrsChangeStep = ElrsChangeResult = ElrsChangeReads = 0;
    ElrsChangeInBox = ElrsListQuiet = ElrsListWanted = false;
    // THE THROTTLE: held from this moment if it is channel 5 (the module has said nothing yet) - but for a restart in
    // flight of a transmitter whose module HAD said the one mode two seconds before (its stamp, FlightGuard.h): that one
    // flies on
    ElrsCh5 = (FlightRestart && FlightRestartElrsCarried) ? ElrsCrsf::CH5_CARRIED : ElrsCrsf::CH5_UNKNOWN;
    ElrsHeld = ElrsCrsf::throttleHeld(MotorChannel == 4, ElrsCh5);
    ElrsThrottleWas = MotorChannel;
    ElrsHeldSaid = false;
    ElrsBeganMs = millis();
    ElrsLogNext = 4;
    ElrsLastLogMs = ElrsSecondMs = ElrsPingMs = millis();
    ElrsSay(PSTR("ELRS test: model's receiver is ELRS - the module has the link, LDRC's radio is silent"));
    if (LedWasGreen || !LedWasRed)
        RedLedOn();
    BoundFlag = false; // (LDRC's search leaves this up half the time: until the module hears the model, no model is connected)
    ModelMatched = false;
    Connected = false;
    if (!ElrsPowered)
        ElrsPowerOn(); // (setup() has done it already for the model it found in memory: ElrsPowerEarly - its moment stands, and the line may start at once)
}

// ... and LDRC's radio again: no more frames, the line let go (a module with its power off must not be fed through its
// signal pin), the module's power off where pin 10 works its switch, and the ELRS model's connection ended.
FLASHMEM static void ElrsEnd()
{
    noInterrupts(); // (the Teensy's IntervalTimer::end() forgets the routine BEFORE it stops the timer: a tick between the two would never be answered)
    ElrsTimer.end();
    interrupts();
    if (ElrsStarted)
    {
        Serial6.end();
        pinMode(ElrsLinePin, INPUT);
        // Serial6.end() also rewrites the function of ITS RECEIVE PIN, pin 25 (the Teensy's HardwareSerial.cpp: "= 5" on
        // both pins) - which this driver never used (half duplex), and which is a SWITCH's (SWITCH7). Put back exactly as
        // the transmitter set it at its start (InitSwitchesAndTrims).
        pinMode(SWITCH7, INPUT_PULLUP);
    }
    digitalWriteFast(ElrsCrsf::POWER_PIN, LOW);
    ElrsStarted = ElrsPowered = false;
    ElrsOn = false;
    noInterrupts();
    ElrsCopyMs = 0;
    ElrsOtherLen = 0;
    interrupts();
    ElrsState = ElrsCrsf::LinkState();
    ElrsHeld = false;
    ElrsCh5 = ElrsCrsf::CH5_UNKNOWN;
    ElrsThrottleWas = 255;
    ElrsChangeStep = 0;
    ElrsChangeInBox = ElrsListWanted = false;
    ElrsSay(PSTR("ELRS test: model's receiver is LDRC - the module's line is let go, LDRC's radio has the link"));
    if (LedWasGreen || !LedWasRed || (BoundFlag && ModelMatched))
        RedLedOn(); // (the ELRS model's connection ends here, whatever state a mode of the transmitter's own left it in: LDRC begins from "no model")
    Connected = false;
}

// The model is heard for the first time: connected, by the transmitter's own code for it (GreenLedOn: the green light,
// "Connected", the log, the safety-off warning, the motor timer, the front page).
FLASHMEM static void ElrsConnected()
{
    BoundFlag = true;
    ModelMatched = true;
    UsingDefaultPipeAddress = false;
    Connect_MMmsg = 0; // (no "Model matched": nothing was searched for)
    snprintf(ReceiverVersionNumber, sizeof(ReceiverVersionNumber), "%.19s", ElrsTelem.rxName[0] ? ElrsTelem.rxName : "ELRS"); // the Telemetry page's "receiver" line
    GreenLedOn();
    ParametersToBeSentPointer = 0; // (GreenLedOn queued an LDRC receiver's settings: they have nowhere to go)
    if (!LedWasGreen)
    {   // (it did not take: the next pass tries again)
        ElrsState.green = ElrsState.silent = false;
        return;
    }
    LostContactFlag = false; // (the motor timer and its spoken minutes wait for this: LDRC's first good packet says it - SuccessfulPacket)
    ElrsPings = 0;
    ElrsPingMs = millis() - ElrsCrsf::PING_EVERY_MS + 1000; // the first "who is there?" a second from now
    if (RotorFlight_V == 1 || RotorFlight_V == 2)
    {   // Rotorflight at this model's last connection (its file): its head speed, amps and mAh are taken from the start
        ElrsCrsf::Item it;
        ElrsCrsf::itemU32(it, ElrsCrsf::ITEM_ROTORFLIGHT, RotorFlight_V);
        ElrsItem(it);
    }
    char line[120];
    snprintf(line, sizeof(line), PSTR("ELRS test: LINK UP - connected (LQ %u%%, RSSI %d dBm, power code %u)"), (unsigned)ElrsTelem.upLq, (int)ElrsTelem.upRssi1, (unsigned)ElrsTelem.txPower);
    ElrsSay(line); // (a connection can come in the air - after the transmitter's own restart: kept for later then)
}

// Silent, the motor switch off: given up, by the transmitter's own code for it (RedLedOn: "Disconnected", the log, the
// boxes cleared, the motor switch refused until a model is heard again).
FLASHMEM static void ElrsGivenUp()
{
    ElrsSay(PSTR("ELRS test: given up - nothing heard and the motor switch off (Disconnected)"));
    RedLedOn();
}

// WHAT IS ONLY FOR THE GROUND (ElrsService calls it when the model cannot be flying - ElrsMayFly): "who is there?", the
// reading of the module's own settings, and the bench's lines for the log. A request of ours goes out in place of ONE
// channel frame, through the timer's one place for such a frame; a line of the log is a write to the card, and there is
// never more than one of those in a pass. And the one place where a setting of the module's is WRITTEN (a change asked
// for on the page), so that never happens while the model may fly either.
FLASHMEM static void ElrsOnTheGround(uint32_t now, bool second)
{
    ElrsCrsf::ParamReader &list = ElrsTelem.params;
    bool wrote = false; // a line has gone to the card in this pass
    if (ElrsNotKept)
    {   // what had no place to be kept while the model could be flying: how many
        char line[96];
        snprintf(line, sizeof(line), PSTR("ELRS test: %u more lines had no place to be kept while the model could be flying"), (unsigned)ElrsNotKept);
        LogText(line, strlen(line), false);
        wrote = true;
        ElrsNotKept = 0;
    }
    ElrsKept = 0;
    if (ElrsListInBox && !ElrsOtherLen)
    {   // the request has gone out: its half second for an answer runs from now, not from when it was left for the timer
        ElrsListInBox = false;
        list.sentAt(now);
    }
    if (second)
    {
        // "who is there?" - a few times: until the flight controller has said its name; and, model or no model, until the
        // module (once anything has come from it) has said how many settings it has.
        const bool askNames = Connected && !ElrsTelem.fcName[0] && ElrsPings < ElrsCrsf::PING_TRIES;
        const bool askModule = !ElrsTelem.nModuleInfo && ElrsTelem.framesOk && ElrsModulePings < ElrsCrsf::PING_TRIES;
        if ((askNames || askModule) && (uint32_t)(now - ElrsPingMs) >= ElrsCrsf::PING_EVERY_MS && !ElrsOtherLen)
        {
            uint8_t f[ElrsCrsf::PING_LEN];
            ElrsCrsf::buildPing(f);
            noInterrupts();
            for (uint8_t i = 0; i < ElrsCrsf::PING_LEN; ++i)
                ElrsOther[i] = f[i];
            ElrsOtherLen = ElrsCrsf::PING_LEN;
            interrupts();
            if (askNames)
                ++ElrsPings;
            else
                ++ElrsModulePings;
            ElrsPingMs = now;
        }
        const uint8_t names = (uint8_t)((ElrsTelem.moduleName[0] ? 1 : 0) | (ElrsTelem.rxName[0] ? 2 : 0) | (ElrsTelem.fcName[0] ? 4 : 0));
        if (names != ElrsNamesSaid && !wrote)
        {
            ElrsNamesSaid = names;
            char line[200];
            snprintf(line, sizeof(line), PSTR("ELRS test: module '%s', receiver '%s', flight controller '%s'%s"), ElrsTelem.moduleName, ElrsTelem.rxName, ElrsTelem.fcName,
                     ElrsTelem.rotorflight ? " = Rotorflight" : "");
            LogText(line, strlen(line), false);
            wrote = true;
            if (ElrsTelem.rxName[0])
                snprintf(ReceiverVersionNumber, sizeof(ReceiverVersionNumber), "%.19s", ElrsTelem.rxName); // the Telemetry page's "receiver" line
        }
    }
    // The bench's four lines every 5 s, one a pass (their counts go on in the air, and are said on the ground again).
    if (ElrsLogNext < 4)
    {
        if (!wrote)
            wrote = ElrsLogLine(ElrsLogNext++);
    }
    else if ((uint32_t)(now - ElrsLastLogMs) >= 5000)
    {
        ElrsLastLogMs = now;
        ElrsLogNext = 0;
    }
    // THE MODULE'S OWN SETTINGS: its list, read once after each beginning of the link and written to the log.
    if (ElrsTelem.moduleParams && !ElrsListBegun)
    {
        if (!wrote)
        {
            ElrsListBegun = true;
            list.start(ElrsTelem.moduleParams);
            char line[120];
            snprintf(line, sizeof(line), PSTR("ELRS test: the module '%s' has %u settings - reading them (nothing is changed)"), ElrsTelem.moduleName, (unsigned)ElrsTelem.moduleParams);
            LogText(line, strlen(line), false);
        }
    }
    else if (list.ready)
    {   // a whole setting has come: kept if it is one of the page's four; its lines for the log, one a pass (not when it is read back)
        if (ElrsListLine == 0)
            ElrsCrsf::keepSetting(list.one, ElrsSet);
        if (ElrsListQuiet)
            list.ready = false;
        else if (!wrote && !ElrsListLog(list.one, ElrsListLine++))
        {
            ElrsListLine = 0;
            list.ready = false;
        }
    }
    else if (ElrsListBegun && !list.done && !ElrsOtherLen)
    {
        uint8_t f[ElrsCrsf::PARAM_FRAME_LEN];
        if (list.next(now, f))
        {
            noInterrupts();
            for (uint8_t i = 0; i < ElrsCrsf::PARAM_FRAME_LEN; ++i)
                ElrsOther[i] = f[i];
            ElrsOtherLen = ElrsCrsf::PARAM_FRAME_LEN;
            interrupts();
            ElrsListInBox = true;
        }
    }
    else if (ElrsListBegun && list.done && !ElrsListSaid && !wrote)
    {
        ElrsListSaid = true;
        char line[200];
        line[0] = 0;
        if (ElrsListQuiet && ElrsChangeStep == 3 && ElrsChange < ElrsCrsf::SET_COUNT)
        {   // read back after a change: what the module now says is what counts
            const ElrsCrsf::Setting &st = ElrsSet[ElrsChange];
            const bool taken = st.known && st.value == ElrsChangeTo;
            if (!taken && ++ElrsChangeReads < ELRS_CHANGE_READS)
            {   // not (yet): the module says a new value only once it has told the receiver and saved it - read again in a moment
                ElrsChangeStep = 2;
                ElrsChangeMs = now;
            }
            else
            {
                char want[40], has[48];
                if (!ElrsCrsf::optionText(st.options, ElrsChangeTo, want, sizeof(want)))
                    snprintf(want, sizeof(want), "choice %u", (unsigned)ElrsChangeTo);
                ElrsCrsf::settingWords(st, has, sizeof(has));
                ElrsChangeResult = taken ? 1 : 2;
                snprintf(line, sizeof(line), PSTR("ELRS test: '%s' asked to be '%s': the module %s '%s'"), ElrsCrsf::setName(ElrsChange), want,
                         taken ? "now says" : "KEPT", has[0] ? has : "(no answer)");
                ElrsChangeStep = 0;
            }
        }
        else if (!ElrsListQuiet)
            snprintf(line, sizeof(line), PSTR("ELRS test: the module's settings: %u read, %u not answered (asked %lu times, %lu pieces came, %lu were not the piece awaited)"),
                     (unsigned)(list.count - list.failed), (unsigned)list.failed, (unsigned long)list.asked, (unsigned long)list.chunks, (unsigned long)list.stray);
        ElrsListQuiet = false;
        if (line[0])
            LogText(line, strlen(line), false);
    }
    // THE THROTTLE HELD OR NOT (see ElrsHeld): changed here and nowhere else - on the ground. What the module last said of
    // its switch mode stays while its list is read again (channel5Said), and "it has not said" holds.
    {
        // (a change of packet rate or switch mode written and not yet read back to its end: the module may still say the old
        //  mode for a moment - no word is taken until the change is taken or kept)
        const bool changing = (ElrsChangeStep == 2 || ElrsChangeStep == 3) && (ElrsChange == ElrsCrsf::SET_RATE || ElrsChange == ElrsCrsf::SET_SWITCH);
        const uint8_t said = changing ? ElrsCh5 : ElrsCrsf::channel5Said(ElrsSet[ElrsCrsf::SET_SWITCH], ElrsCh5);
        if (said != ElrsCh5)
        {
            ElrsCh5 = said;
            ElrsHeldSaid = false; // (held for another reason than before: said again)
        }
        const bool held = ElrsCrsf::throttleHeld(MotorChannel == 4, ElrsCh5);
        if (held != ElrsHeld)
        {
            ElrsHeld = held;
            ElrsHeldSaid = false;
            LastConnectionQuality = 0xFFFF; // (the front page writes its word afresh)
        }
        // Said in the log once: at once when the module has said a mode that does not carry channel 5; when it has said
        // nothing, only once its list has been read to the end without it, or it has not answered at all - on an
        // ordinary start the hold ends by itself a few seconds after the module wakes
        const bool noWord = ElrsCh5 == ElrsCrsf::CH5_UNKNOWN;
        const bool listOver = (ElrsListBegun && list.done) || (ElrsTelem.nModuleInfo && !ElrsTelem.moduleParams) || (!ElrsTelem.nModuleInfo && ElrsModulePings >= ElrsCrsf::PING_TRIES);
        if (ElrsHeld && !ElrsHeldSaid && !wrote && (!noWord || listOver))
        {
            ElrsHeldSaid = true;
            char line[200], mode[40];
            ElrsCrsf::settingWords(ElrsSet[ElrsCrsf::SET_SWITCH], mode, sizeof(mode));
            if (noWord)
                snprintf(line, sizeof(line), PSTR("ELRS test: THROTTLE HELD - this model's throttle is channel 5, and the module has not said its switch mode (it must be '16ch Rate/2')"));
            else
                snprintf(line, sizeof(line), PSTR("ELRS test: THROTTLE HELD - this model's throttle is channel 5, and switch mode '%s' carries it as off or on only (it needs '16ch Rate/2')"), mode);
            LogText(line, strlen(line), false);
            wrote = true;
        }
    }
    // The page was opened: the list once more, quietly (the module may have been changed elsewhere - its own WiFi page).
    if (ElrsListWanted && ElrsListBegun && list.done && !list.ready && ElrsListSaid && !ElrsChangeStep && ElrsTelem.moduleParams)
    {
        ElrsListWanted = false;
        list.start(ElrsTelem.moduleParams);
        ElrsListSaid = false;
        ElrsListQuiet = true;
        ElrsListLine = 0;
    }
    // A CHANGE ASKED OF THE MODULE (the page's picker). THE ONE PLACE IN THIS FILE WHERE A SETTING OF THE MODULE'S IS
    // WRITTEN: one frame, when no reading is in hand, through the timer's place.
    if (ElrsChangeInBox && !ElrsOtherLen)
    {   // it has gone out: the module has its moment from now
        ElrsChangeInBox = false;
        ElrsChangeMs = now;
    }
    if (ElrsChangeStep == 1 && ((uint32_t)(now - ElrsChangeAskedMs) > ELRS_CHANGE_ASK_MS || ElrsChange >= ElrsCrsf::SET_COUNT || (ElrsCrsf::needsNoModel(ElrsChange) && ElrsState.green)))
    {   // not written within its time (the module was being read, or says nothing), or a model has connected since it was asked for: dropped
        ElrsChangeStep = 0;
        ElrsChangeResult = 2;
    }
    else if (ElrsChangeStep == 1 && !ElrsOtherLen && !list.ready && (!ElrsListBegun || list.done) && ElrsSet[ElrsChange].known)
    {
        uint8_t f[ElrsCrsf::PARAM_FRAME_LEN];
        const uint8_t number = ElrsSet[ElrsChange].number;
        if (ElrsChange == ElrsCrsf::SET_RATE || ElrsChange == ElrsCrsf::SET_SWITCH)
        {   // a packet rate brings another switch mode with it: what was read of the switch mode is no longer the module's word -
            // not known, so held (the rule above, from the next pass) until it has said what it now has
            ElrsSet[ElrsCrsf::SET_SWITCH].known = false;
            ElrsCh5 = ElrsCrsf::CH5_UNKNOWN;
            ElrsHeld = ElrsCrsf::throttleHeld(MotorChannel == 4, ElrsCh5); // (held from this pass, not the next)
        }
        ElrsCrsf::buildParamWrite(f, number, ElrsChangeTo);
        noInterrupts();
        for (uint8_t i = 0; i < ElrsCrsf::PARAM_FRAME_LEN; ++i)
            ElrsOther[i] = f[i];
        ElrsOtherLen = ElrsCrsf::PARAM_FRAME_LEN;
        interrupts();
        ElrsChangeInBox = true;
        ElrsChangeStep = 2;
        ElrsChangeReads = 0;
        ElrsChangeMs = now;
    }
    else if (ElrsChangeStep == 2 && !ElrsChangeInBox && (uint32_t)(now - ElrsChangeMs) >= (ElrsChangeReads ? ELRS_CHANGE_AGAIN_MS : ELRS_CHANGE_SETTLE_MS) && ElrsTelem.moduleParams
             && (!ElrsListBegun || list.done) && !list.ready)
    {   // ... and the whole list is read again, quietly: a packet rate brings other switch modes and another telemetry figure with it
        for (uint8_t k = 0; k < ElrsCrsf::SET_COUNT; ++k)
            ElrsSet[k].known = false;
        list.start(ElrsTelem.moduleParams);
        ElrsListBegun = true;
        ElrsListSaid = false;
        ElrsListQuiet = true;
        ElrsListLine = 0;
        ElrsChangeStep = 3;
    }
    if (second && CurrentView == ELRSVIEW)
        ElrsViewShow(); // (drawn again only when what it shows has changed)
}

// Every pass: the line started when the module has had its power for a moment, what the module says read, its timing
// word to the pacer, the model heard or not, its telemetry into the transmitter's own boxes. Never waits.
FASTRUN static void ElrsService()
{
    const uint32_t now = millis(); // (its own look at the clock: the power's moment was stamped after ElrsLink() looked)
    if (!ElrsStarted)
    {
        if (!ElrsPowered)
            ElrsPowerOn(); // power first ...
        if (!ElrsCrsf::lineMayStart(ElrsPowered, ElrsPowerOnMs, now))
            return; // ... and the line only when the module has had it for a moment (never a wait: the next pass looks again)
        if (!ElrsLineHasRoom)
        {
            Serial6.addMemoryForRead(ElrsRxMore, sizeof(ElrsRxMore));
            ElrsLineHasRoom = true;
        }
        Serial6.begin(400000, SERIAL_8N1_HALF_DUPLEX);
        ElrsLoadedUs = ElrsCrsf::DEFAULT_PERIOD_US;
        if (!ElrsTimer.begin(ElrsSendIsr, ElrsCrsf::DEFAULT_PERIOD_US))
            ElrsSay(PSTR("ELRS test: NO TIMER FREE - no frame will be sent")); // (the Teensy has four such timers and the transmitter uses none: this should never be seen)
        ElrsStarted = true;
        ElrsLastPassMs = now;
    }
    if ((uint32_t)(now - ElrsLastPassMs) > ElrsCrsf::LINE_STALE_MS)
    {   // loop() has been away (another mode, a box on the screen): what the line holds is old - thrown away, not read as news.
        // And a model that was heard when loop() left is not called silent for the absence: the line gets its time to say.
        Serial6.clear();
        ElrsParser.len = 0;
        if (ElrsState.green && !ElrsState.silent)
            ElrsTelem.linkMs = now ? now : 1;
    }
    ElrsLastPassMs = now;
    for (uint16_t k = 0; k < 512 && Serial6.available(); ++k)
    {
        ++ElrsBytesIn;
        ElrsParser.feed((uint8_t)Serial6.read(), ElrsTelem, now);
    }
    noInterrupts();
    ElrsPacer.onTiming(ElrsTelem, now);
    interrupts();

    // heard or not, and what follows from it (THE MODEL'S OWN LINK above)
    bool heard = ElrsCrsf::linkHeard(ElrsTelem, now);
    if (!ElrsState.green && SendNoData)
        heard = false; // The motor switch was refused ("please turn it off") and has not been seen off since. LDRC connects no model
                       // until it has (it sends nothing); here the sticks go on, the throttle held low, but no model is CONNECTED
                       // until then either - or the switch, still on, would start the motor at the connection.
    const bool wasSilent = ElrsState.silent;
    const int change = ElrsState.step(heard, MotorEnabled && !ElrsHeld, now); // (a held throttle's motor switch starts nothing: it has not "been on")
    if (change > 0)
        ElrsConnected();
    else if (change < 0)
        ElrsGivenUp();
    else if (ElrsState.green && !LedWasGreen)
        ElrsConnected(); // The transmitter put its own light out (a setting redrawn, a mode of its own): connected again, as LDRC's next
                         // packet would say. Never "no model" from here: only LinkState gives a model up, and never with the motor running.
    else if (ElrsState.silent != wasSilent)
    {
        if (ElrsState.silent)
        {
            ElrsSay(PSTR("ELRS test: NO TELEMETRY - nothing heard from the model; the sticks are still sent"));
            if (AnnounceConnected)
                PlaySound(WHAHWHAHMSG);
        }
        else
        {
            ElrsSay(PSTR("ELRS test: telemetry back"));
            LastConnectionQuality = 0xFFFF; // (the front page writes "Connected" and its bar afresh at its next second, whatever the figure)
        }
    }
    Connected = ElrsState.green && !ElrsState.silent; // (the battery warnings ask this: no warning from old figures)
    // No model, and the light not red (a mode of the transmitter's own put it out - a calibration, the link to the Mac):
    // red after RED_LED_ON_TIME, as LDRC has it (CheckGap) - red is what refuses the motor switch while there is no model.
    if (!ElrsState.green && !LedWasRed && !LedWasGreen)
    {
        if (!ElrsNotRedMs)
            ElrsNotRedMs = now ? now : 1;
        else if ((uint32_t)(now - ElrsNotRedMs) >= RED_LED_ON_TIME)
        {
            ElrsNotRedMs = 0;
            RedLedOn();
        }
    }
    else
        ElrsNotRedMs = 0;

    // the model's telemetry, as the items an LDRC receiver would send
    if (ElrsState.green)
    {
        ElrsCrsf::Item items[ElrsCrsf::MAX_ITEMS];
        const uint8_t n = ElrsCrsf::takeItems(ElrsTelem, RXCellCount == 12, RotorFlight_V, items);
        for (uint8_t i = 0; i < n; ++i)
            ElrsItem(items[i]);
        // The head speed again ten times a second while it is fresh: the transmitter smooths it for an LDRC receiver,
        // which sends it about that often - ELRS brings it once or twice a second, and the figure would crawl.
        if (RotorFlight_Version && ElrsTelem.rpmMs && (uint32_t)(now - ElrsTelem.rpmMs) < 3000 && (uint32_t)(now - ElrsRpmItemMs) >= 100)
        {
            ElrsRpmItemMs = now;
            ElrsCrsf::Item it;
            ElrsCrsf::itemU32(it, ElrsCrsf::ITEM_RPM, ElrsCrsf::rpmForItem(ElrsTelem.headRpm));
            ElrsItem(it);
        }
    }

    ParametersToBeSentPointer = 0; // an LDRC receiver's settings: nowhere to send them
    {
        const uint32_t s = ElrsSent; // the front page's frame rate: the frames sent while the model is heard
        if (Connected)
            RecentGoodPacketsCount += (s - ElrsSentSeen);
        ElrsSentSeen = s;
    }

    if (MotorEnabled && !ElrsMotorWas && ElrsHeld)
    {   // the motor switch put on while the throttle is held: nothing starts - and that is said and heard
        ElrsSay(ElrsCh5 == ElrsCrsf::CH5_UNKNOWN ? PSTR("ELRS test: THROTTLE HELD (not read)") : PSTR("ELRS test: THROTTLE HELD (ch5 1 bit)"));
        if (AnnounceConnected)
            PlaySound(WHAHWHAHMSG);
    }
    ElrsMotorWas = MotorEnabled;
    bool second = false;
    if ((uint32_t)(now - ElrsSecondMs) >= 1000)
    {
        ElrsSecondMs = now;
        second = true;
        if (ElrsState.green && ElrsState.silent && CurrentView == FRONTVIEW)
        {
            char box[] = "Connected", words[] = "No telemetry";
            SendText(box, words);
        }
        else if (ElrsState.green && ElrsHeld && CurrentView == FRONTVIEW
                 && (ElrsCh5 != ElrsCrsf::CH5_UNKNOWN || MotorEnabled || (uint32_t)(now - ElrsBeganMs) > 10000))
        {   // (held for want of the module's word: said only when the motor switch is on, or after ten seconds - on an ordinary
            //  start the word comes within a few)
            char box[] = "Connected", words[] = "Throttle held";
            SendText(box, words);
        }
    }
    // FROM HERE, WHAT IS ONLY FOR THE GROUND: "who is there?", the reading of the module's own settings, the bench's
    // lines for the log. While the model may be flying none of it happens - and a frame of ours still waiting in the
    // timer's place is taken back: from that moment nothing takes a channel frame's place.
    if (ElrsMayFly())
    {
        noInterrupts();
        const bool tookBack = ElrsOtherLen != 0; // (looked at and emptied in one piece: the timer may be about to take it)
        ElrsOtherLen = 0;
        interrupts();
        if (ElrsListInBox)
        {
            ElrsListInBox = false;
            if (tookBack)
                ElrsTelem.params.notSent(); // (asked again on the ground; it was no try)
            else
                ElrsTelem.params.sentAt(now); // (it had gone: its answer is taken when it comes)
        }
        if (ElrsChangeStep == 1 || (ElrsChangeInBox && tookBack))
        {   // a change asked for and NOT YET WRITTEN: dropped - it is not done later, behind the pilot's back
            if (ElrsChangeInBox)
                ElrsListWanted = true; // (its frame was made and never went: what was forgotten for it - the switch mode - is read again on the ground)
            ElrsChangeStep = 0;
            ElrsChangeResult = 2;
        }
        else if (ElrsChangeInBox)
            ElrsChangeMs = now; // (its frame HAD gone: the module has the change, and it is read back on the ground - found by review: it was called "kept" unread)
        ElrsChangeInBox = false;
        if (second && CurrentView == ELRSVIEW)
            ElrsViewShow(); // (its line says why nothing can be changed)
        return;
    }
    ElrsOnTheGround(now, second);
}

// SendData's part for a model set to ELRS (transceiver.h calls this first, every time). True: the module has this
// model's link, and SendData sends nothing on LDRC's radio. False: an LDRC model - SendData goes on as it always has.
FASTRUN bool ElrsLink()
{
    if (!ElrsSetupDone)
    {   // NOT BEFORE setup() IS OVER (ElrsSetupOver, its last line). Setup's waits call this (DelayWithDog flies an ELRS model
        // through every wait), and until then the motor switch and the arming are at their power-on "off" - the switches are
        // read, and after a restart IN FLIGHT taken as they stand (FlightRestartArm), in setup's last lines - and the sticks'
        // converter is not started. A model that was flying had every frame "motor off, disarmed" for the length of setup
        // (the fifth review, 14 Nov 2026). LDRC says nothing either: the model is the module's from the first pass.
        if (!ElrsModel)
            return false;
        NewCompressNeeded = false;
        return true;
    }
    const uint32_t now = millis();
    if (ElrsModel != ElrsWantLast)
    {
        ElrsWantLast = ElrsModel;
        ElrsWantSinceMs = now;
    }
    if (ElrsModel != ElrsOn && !ElrsBusy && (uint32_t)(now - ElrsWantSinceMs) >= ElrsCrsf::MODEL_SETTLE_MS)
    {
        ElrsBusy = true; // (RedLedOn in either may wait for the motor switch: its waits come back here, and find the change already in hand)
        if (ElrsModel)
            ElrsBegin();
        else
            ElrsEnd();
        ElrsBusy = false;
        NewCompressNeeded = false; // (RedLedOn has just emptied the channels: they are worked out afresh before anything is copied or sent)
        return true;               // nothing more on either radio in this pass
    }
    if (!ElrsOn)
    {
        if (!ElrsModel)
            return false; // an LDRC model: SendData goes on as it always has
        // A model set to ELRS whose link has not begun yet (its setting has not stood MODEL_SETTLE_MS): LDRC'S RADIO SAYS
        // NOTHING MEANWHILE. (The yellow, 14 Nov 2026: in that tenth of a second at switch-on the heli's own LDRC
        // receiver, in the same model, answered - "Model memory matched", a connection, and at once "Disconnected" as
        // the module took over. Malcolm: "I heard model memory matched! That's pretty impressive, I think, if it's
        // true". It was LDRC's match, not the module's.)
        NewCompressNeeded = false; // (the channels go on being worked out, as in every pass of an ELRS model)
        return true;
    }
    // THE COPY, on every call - with these few exceptions, none of them about what is heard:
    //  - binding (LDRC's; while it is on the motor switch does not hold the throttle low, and its bytes are put among the
    //    channels): switched off here, and THIS pass's channels are not used;
    //  - the model in memory is not an ELRS one just now (another is being read, or the defaults for a calibration);
    //  - a mode in which loop() itself sends nothing (calibration, the scan, the game, a buddy pupil);
    //  - the channels have not been worked out since the last copy (GetNewChannelValues does it once NewCompressNeeded is
    //    cleared, as LDRC's own SendData clears it with each packet: a copy is only ever of channels made in this pass);
    //  - the transmitter's own box "The motor switch is ON. Switch it off" (EnsureMotorIsOff, main.cpp: no model, and the
    //    motor switch found on - the throttle would be live and the pilot is reading a box). LDRC sends nothing there
    //    (SendNoData), nor does this. With the motor switch refused (MotorEnabled false: throttle held low) the sticks go on.
    // No copy, and the timer says nothing within STICKS_STALE_MS.
    const bool sendingMode = CurrentMode == NORMAL || CurrentMode == SAVE_RF_SETTINGS || CurrentMode == RESTORE_RF_SETTINGS;
    if (BindingEnabled)
    {
        BindingEnabled = false;
        LedIsBlinking = false;
    }
    else if (ElrsModel && sendingMode && NewCompressNeeded && !(SendNoData && MotorEnabled))
    {
        if (MotorChannel != ElrsThrottleWas)
        {   // THE MODEL'S THROTTLE CHANNEL HAS CHANGED: the rule at once, wherever the model is (see ElrsHeld)
            ElrsThrottleWas = MotorChannel;
            ElrsHeld = ElrsCrsf::throttleHeld(MotorChannel == 4, ElrsCh5);
            ElrsHeldSaid = false;
            LastConnectionQuality = 0xFFFF; // (the front page writes its word afresh)
        }
        FixMotorChannel();  // (the motor switch's word on the throttle: loop() says it only in its normal mode)
        FixArmingChannel(); // (as SendData does before every packet: the safety switch's word on the arming channel)
        const uint16_t motorOff = IntoHigherRes(MotorChannelZero);
        noInterrupts();     // (a few dozen nanoseconds: the timer must see a whole copy, with its time)
        for (uint8_t i = 0; i < 16; ++i)
            ElrsChannels[i] = SendBuffer[i];
        if ((ElrsHeld || !MotorEnabled) && MotorChannel < 16)
            ElrsChannels[MotorChannel] = motorOff; // THE THROTTLE HELD (ElrsHeld) - and MOTOR OFF WHENEVER THE MOTOR SWITCH IS OFF: FixMotorChannel leaves the throttle
                                                   // alone on a buddy master whose buddy switch is on (the pupil's channels are flown), and an ELRS model has
                                                   // no pupil (BuddyWireless.h GetBuddyData): the master's own stick flew the motor with its switch off (review, 14 Nov 2026)
        ElrsCopyMs = now ? now : 1;
        interrupts();
    }
    NewCompressNeeded = false; // the next GetNewChannelValues works the channels out afresh (LDRC's SendData says so with each packet;
                               // without this the sticks would be read once and never again)
    LastPacketSentTime = now;  // (SendData's clock, moved as its own silences move it: the transmitter's chores go on - see there)
    PerfSilent();              // (LDRC is silent on purpose: no late packet for its timing report)
    if (!ElrsBusy)
    {   // (the transmitter's own "connected" and "no model" code may wait, and its waits come back here for the copy above: the reading is never begun twice)
        ElrsBusy = true;
        ElrsService();
        ElrsBusy = false;
    }
    return true;
}
// ---- THE PAGE "ELRS settings" (ElrsView) AND ITS PICKER (ElrsPickView) ---------------------------------------------------
// (14 Nov 2026. Malcolm: "should we not perhaps finish our configuration of ELRS".) Model setup > Options > "ELRS
// settings ..." (shown for a model set to ELRS). Four rows, each the module's own word for what it is set to; a row
// tapped opens the picker with the choices the module offers; OK there asks the module for the change, and the row
// then shows what the module says it has. One line under the rows says what stands in the way of a change, if
// anything does. Nothing is asked of the module while the model may be flying.
static const char *const ElrsRowTitle[ElrsCrsf::SET_COUNT] = {"Stick updates a second", "Telemetry share", "Channel detail", "Most power"};
FLASHMEM static const char *ElrsViewHint()
{
    if (ElrsChangeStep)
        return "Asking the module ...";
    if (ElrsMayFly())
        return "Safety on first: nothing is changed while the model may fly.";
    if (!ElrsOn || !ElrsTelem.nModuleInfo)
        return "The module has not answered yet.";
    if (ElrsChangeResult == 2)
        return "The module kept what it had.";
    if (ElrsHeld && ElrsCh5 == ElrsCrsf::CH5_UNKNOWN)
        return "Throttle held: the module has not said its channel detail.";
    if (ElrsHeld)
        return "Throttle is channel 5: it needs 333Hz Full, then 16ch Rate/2.";
    {
        char o[40];
        const ElrsCrsf::Setting &tl = ElrsSet[ElrsCrsf::SET_TELEM];
        if (tl.known && ElrsCrsf::optionText(tl.options, tl.value, o, sizeof(o)) && !strcmp(o, "Off"))
            return "Telemetry is off: the model cannot be heard. Choose a share.";
    }
    if (ElrsState.green)
        return "Model connected: rate and channel detail only with it off.";
    return "";
}
FLASHMEM static void ElrsViewShow()
{
    char words[ElrsCrsf::SET_COUNT][48];
    const char *hint = ElrsViewHint();
    uint32_t sig = 2166136261u; // what will be shown, as one number: drawn only when it differs from what is on the screen
    for (uint8_t k = 0; k < ElrsCrsf::SET_COUNT; ++k)
    {
        ElrsCrsf::settingWords(ElrsSet[k], words[k], sizeof(words[k]));
        if (!words[k][0])
            snprintf(words[k], sizeof(words[k]), "%s", (ElrsListBegun && !ElrsTelem.params.done) ? "reading ..." : "-");
        for (const char *c = words[k]; *c; ++c)
            sig = (sig ^ (uint8_t)*c) * 16777619u;
        sig = (sig ^ 0xFF) * 16777619u;
    }
    for (const char *c = hint; *c; ++c)
        sig = (sig ^ (uint8_t)*c) * 16777619u;
    for (const char *c = ElrsTelem.moduleName; *c; ++c)
        sig = (sig ^ (uint8_t)*c) * 16777619u;
    if (!sig)
        sig = 1;
    if (sig == ElrsViewSig)
        return;
    ElrsViewSig = sig;
    for (uint8_t k = 0; k < ElrsCrsf::SET_COUNT; ++k)
    {
        char box[8];
        snprintf(box, sizeof(box), "tn%u", (unsigned)k);
        SendText(box, words[k]);
    }
    char line[64];
    snprintf(line, sizeof(line), "%s", ElrsTelem.moduleName[0] ? ElrsTelem.moduleName : "ELRS module");
    SendText((char *)"t9", line);
    snprintf(line, sizeof(line), "%s", hint);
    SendText((char *)"hint", line);
}
FLASHMEM static void ElrsViewOpen()
{
    SendCommand((char *)"page ElrsView");
    CurrentView = ELRSVIEW;
    SendText((char *)"t11", (char *)"All ELRS models"); // (the settings are the MODULE's: every model flown through it shares them)
    ElrsViewSig = 0;
    ElrsViewShow();
}
FLASHMEM void StartElrsView() // Model options' "ELRS ..."
{
    // ONLY FROM MODEL OPTIONS. A second tap on the button is kept by the transmitter while the first is being obeyed and
    // served afterwards - when another page is showing: its boxes read from that page come back as 0, and Model options'
    // values (the motor kill switch, the stop-flying volts, six banks, this very switch) would be zeroed in memory and
    // saved by its OK. (Found by review, 14 Nov 2026, before this ran.)
    if (CurrentView != RXSETUPVIEW1)
        return;
    ReadRXOptionsView(); // what was typed on Model options goes with us, and is saved - as its other ways out do (Servo types, Model picture)
    SaveOneModel(ModelNumber);
    if (!ElrsModel)
    {   // (the switch was put off just now: there is nothing to set)
        RXOptionsViewStart();
        return;
    }
    ElrsChangeResult = 0;
    ElrsListWanted = true; // (the module may have been changed elsewhere since its list was read: read again, quietly)
    ElrsViewOpen();
}
FLASHMEM void EndElrsView() // its OK: back to Model options, drawn afresh
{
    if (CurrentView != ELRSVIEW)
        return; // (a second tap, served when the page has gone)
    RXOptionsViewStart();
}
FLASHMEM static void ElrsRowTapped(uint8_t k)
{
    if (CurrentView != ELRSVIEW || k >= ElrsCrsf::SET_COUNT)
        return;
    ElrsChangeResult = 0;
    const ElrsCrsf::Setting &st = ElrsSet[k];
    if (ElrsMayFly() || ElrsChangeStep || !st.known || st.cut || (ElrsCrsf::needsNoModel(k) && ElrsState.green))
    {   // nothing to pick just now: the line under the rows says why
        ElrsViewSig = 0;
        ElrsViewShow();
        return;
    }
    // the picker: this setting's choices - those the module offers, in its order
    char cmd[420];
    uint16_t w = (uint16_t)snprintf(cmd, sizeof(cmd), "list.path=\"");
    uint8_t shown = 0;
    for (uint8_t r = 0; r < 40; ++r)
    {
        const uint8_t place = ElrsCrsf::pagePlace(k, st.options, r);
        if (place == 255)
            break;
        char o[40];
        if (!ElrsCrsf::optionText(st.options, place, o, sizeof(o)) || w + strlen(o) + 4 >= sizeof(cmd))
            break;
        w += (uint16_t)snprintf(cmd + w, sizeof(cmd) - w, "%s%s", shown ? "\r\n" : "", o);
        ++shown;
    }
    if (!shown)
        return;
    snprintf(cmd + w, sizeof(cmd) - w, "\"");
    ElrsPickFor = k;
    SendCommand((char *)"page ElrsPickView");
    CurrentView = ELRSPICKVIEW;
    char title[32];
    snprintf(title, sizeof(title), "%s", ElrsRowTitle[k]);
    SendText((char *)"t0", title);
    SendText((char *)"t11", (char *)"All ELRS models");
    SendCommand(cmd);
    const uint8_t rank = ElrsCrsf::pageRank(k, st.options, st.value);
    SendValue((char *)"list", rank == 255 ? 0 : rank);
}
FLASHMEM void ElrsRow0Tapped() { ElrsRowTapped(ElrsCrsf::SET_RATE); }
FLASHMEM void ElrsRow1Tapped() { ElrsRowTapped(ElrsCrsf::SET_TELEM); }
FLASHMEM void ElrsRow2Tapped() { ElrsRowTapped(ElrsCrsf::SET_SWITCH); }
FLASHMEM void ElrsRow3Tapped() { ElrsRowTapped(ElrsCrsf::SET_POWER); }
FLASHMEM void ElrsPickCancel()
{
    if (CurrentView == ELRSPICKVIEW)
        ElrsViewOpen();
}
FLASHMEM void ElrsPickOk()
{
    if (CurrentView != ELRSPICKVIEW)
        return;
    const uint32_t raw = GetValue((char *)"list"); // (a reply that never came is 65535: nothing is changed)
    const uint8_t k = ElrsPickFor;
    ElrsPickFor = 255;
    if (k < ElrsCrsf::SET_COUNT && raw < 250)
    {
        const ElrsCrsf::Setting &st = ElrsSet[k];
        const uint8_t place = ElrsCrsf::pagePlace(k, st.options, (uint8_t)raw);
        if (st.known && !st.cut && place != 255 && place != st.value && !ElrsMayFly() && !ElrsChangeStep && !(ElrsCrsf::needsNoModel(k) && ElrsState.green))
        {
            ElrsChange = k;
            ElrsChangeTo = place;
            ElrsChangeStep = 1;
            ElrsChangeResult = 0;
            ElrsChangeAskedMs = millis();
        }
    }
    ElrsViewOpen();
}
#endif
